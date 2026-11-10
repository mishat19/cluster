"""Initialise le cluster : replica sets -> shards -> sharding + import de books.books."""
import json
import os
import time

from bson import json_util
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

REPLICA_SETS = {
    "configRs": {
        "members": ["config_1", "config_2", "config_3"],
        "port": 27019,
        "configsvr": True,
    },
    "rs_a": {"members": ["principal_a", "secondaire_a_1", "secondaire_a_2"], "port": 27018},
    "rs_b": {"members": ["principal_b", "secondaire_b_1", "secondaire_b_2"], "port": 27018},
    "rs_c": {"members": ["principal_c", "secondaire_c_1", "secondaire_c_2"], "port": 27018},
}
ROUTEURS = "mongodb://routeur_1:27017,routeur_2:27017/"
BOOKS_PATH = os.environ.get("BOOKS_PATH", "/scripts/books.txt")


def reessayer(action, essais=60, delai=2, label="action"):
    for i in range(essais):
        try:
            return action()
        except (PyMongoError, OperationFailure) as erreur:
            print(f"  en attente ({label}) {i + 1}/{essais}: {erreur}")
            time.sleep(delai)
    raise RuntimeError(f"Abandon: {label}")


def initier_replica_set(nom, spec):
    membres = spec["members"]
    port = spec["port"]
    config = {
        "_id": nom,
        "members": [
            {"_id": i, "host": f"{hote}:{port}", "priority": 2 if i == 0 else 1}
            for i, hote in enumerate(membres)
        ],
    }
    if spec.get("configsvr"):
        config["configsvr"] = True

    client = MongoClient(membres[0], port, directConnection=True, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("replSetInitiate", config)
        print(f"{nom}: replSetInitiate envoyé")
    except OperationFailure as erreur:
        if erreur.code != 23:
            raise
        print(f"{nom}: déjà initialisé")

    def est_primaire():
        hello = client.admin.command("hello")
        if not hello.get("isWritablePrimary"):
            raise PyMongoError(f"{membres[0]} pas encore PRIMARY")
        return hello

    hello = reessayer(est_primaire, label=f"PRIMARY {nom}")
    print(f"{nom}: PRIMARY = {hello.get('primary')}")


def ajouter_groupes():
    client = MongoClient(ROUTEURS, serverSelectionTimeoutMS=5000)
    for nom in ("rs_a", "rs_b", "rs_c"):
        port = REPLICA_SETS[nom]["port"]
        hotes = ",".join(f"{h}:{port}" for h in REPLICA_SETS[nom]["members"])
        shard = f"{nom}/{hotes}"

        def add():
            try:
                return client.admin.command("addShard", shard)
            except OperationFailure as e:
                if getattr(e, "code", None) == 23 or "already" in str(e).lower():
                    return {"ok": 1, "msg": "already"}
                raise

        res = reessayer(add, label=f"addShard {nom}")
        print(f"groupe {nom}: {res}")

    try:
        client.admin.command("enableSharding", "books")
        print("books: sharding activé")
    except OperationFailure as e:
        if getattr(e, "code", None) not in (23,) and "already" not in str(e).lower():
            raise
        print("books: sharding déjà activé")

    try:
        client.admin.command("shardCollection", "books.books", key={"_id": "hashed"})
        print("books.books: shardCollection OK")
    except OperationFailure as e:
        if "already" not in str(e).lower():
            raise
        print("books.books: déjà shardée")


def importer_books():
    client = MongoClient(ROUTEURS, serverSelectionTimeoutMS=5000)
    col = client["books"]["books"]
    if col.estimated_document_count() > 0:
        print(f"books.books: déjà importée ({col.count_documents({})} docs)")
        return
    if not os.path.exists(BOOKS_PATH):
        print(f"books.books: fichier introuvable ({BOOKS_PATH}), import ignoré")
        return
    with open(BOOKS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f, object_hook=json_util.object_hook)
    if isinstance(data, list) and data:
        col.insert_many(data, ordered=False)
        print(f"books.books: {col.count_documents({})} documents importés")
    else:
        print("books.books: fichier vide ou format inattendu")


if __name__ == "__main__":
    for nom, spec in REPLICA_SETS.items():
        initier_replica_set(nom, spec)
    ajouter_groupes()
    importer_books()
    print("Cluster prêt.")
