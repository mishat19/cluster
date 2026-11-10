"""Serveur historique : écoute les changements MongoDB via change streams et les journalise."""
import json
import os
import time
from datetime import datetime, timezone

from bson import json_util
from pymongo import MongoClient
from pymongo.errors import PyMongoError

ROUTEURS = os.environ.get("MONGO_URI", "mongodb://routeur_1:27017,routeur_2:27017/")
LOG_DIR = os.environ.get("HISTORIQUE_DIR", "/data/historique")
LOG_FILE = os.path.join(LOG_DIR, "historique.log")
STATE_FILE = os.path.join(LOG_DIR, "resume_token.json")


def charger_resume_token():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f, object_hook=json_util.object_hook)
    except Exception:
        return None


def sauver_resume_token(token):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(token, f, default=json_util.default)
    os.replace(tmp, STATE_FILE)


def journaliser(evt):
    os.makedirs(LOG_DIR, exist_ok=True)
    entree = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "operation": evt.get("operationType"),
        "ns": evt.get("ns"),
        "documentKey": evt.get("documentKey"),
        "fullDocument": evt.get("fullDocument"),
        "updateDescription": evt.get("updateDescription"),
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, default=json_util.default, ensure_ascii=False) + "\n")


def boucle():
    os.makedirs(LOG_DIR, exist_ok=True)
    while True:
        try:
            client = MongoClient(ROUTEURS, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            resume = charger_resume_token()
            kwargs = {"full_document": "updateLookup"}
            if resume:
                kwargs["resume_after"] = resume
                print("historique: reprise depuis le dernier token")
            print("historique: écoute des changements sur le cluster...")
            with client.watch(**kwargs) as stream:
                for evt in stream:
                    journaliser(evt)
                    if stream.resume_token:
                        sauver_resume_token(stream.resume_token)
                    print(f"historique: {evt.get('operationType')} {evt.get('ns')}")
        except PyMongoError as e:
            print(f"historique: erreur/indisponible ({e}), nouvelle tentative dans 5s")
            time.sleep(5)
        except Exception as e:
            print(f"historique: erreur inattendue ({e}), nouvelle tentative dans 5s")
            time.sleep(5)


if __name__ == "__main__":
    boucle()
