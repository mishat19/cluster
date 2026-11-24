"""Tests du cluster MongoDB shardé : configuration ET état réel des conteneurs.

À lancer DANS le réseau Docker (les noms routeur_1, principal_a... n'existent pas sur l'hôte) :
  docker compose --profile test run --rm tests

Un test échoue dès qu'un conteneur du cluster est éteint, et le message nomme le coupable.
"""
import os
import sys
import time

from pymongo import MongoClient, WriteConcern
from pymongo.errors import PyMongoError

ROUTEURS = ["routeur_1", "routeur_2"]
URI = os.environ.get("MONGO_URI", "mongodb://routeur_1:27017,routeur_2:27017/")
LOG_HISTORIQUE = os.environ.get("HISTORIQUE_LOG", "/data/historique/historique.log")

SHARDS = {
    "rs_a": ["principal_a", "secondaire_a_1", "secondaire_a_2"],
    "rs_b": ["principal_b", "secondaire_b_1", "secondaire_b_2"],
    "rs_c": ["principal_c", "secondaire_c_1", "secondaire_c_2"],
}
CONFIG = ["config_1", "config_2", "config_3"]
PORT_SHARD = 27018
PORT_CONFIG = 27019


def etat_membre(hote, port):
    """Interroge directement un mongod : PRIMARY, SECONDARY, AUTRE ou INJOIGNABLE."""
    try:
        c = MongoClient(hote, port, directConnection=True, serverSelectionTimeoutMS=3000)
        h = c.admin.command("hello")
        if h.get("isWritablePrimary"):
            return "PRIMARY"
        return "SECONDARY" if h.get("secondary") else "AUTRE"
    except PyMongoError:
        return "INJOIGNABLE"


def verifier_replica_set(nom, hotes, port):
    etats = {h: etat_membre(h, port) for h in hotes}
    valeurs = list(etats.values())
    assert valeurs.count("PRIMARY") == 1 and valeurs.count("SECONDARY") == 2, \
        f"{nom} dégradé : {etats}"


# ---------- Santé réelle (échouent si un conteneur est éteint) ----------

def test_routeurs():
    """Chaque routeur est testé séparément, sans basculer sur l'autre."""
    en_panne = []
    for h in ROUTEURS:
        try:
            c = MongoClient(h, 27017, directConnection=True, serverSelectionTimeoutMS=3000)
            if c.admin.command("serverStatus").get("process") != "mongos":
                en_panne.append(f"{h} (pas un mongos)")
        except PyMongoError:
            en_panne.append(f"{h} (injoignable)")
    assert not en_panne, f"routeur(s) en panne : {', '.join(en_panne)}"
    print("[OK] routeur_1 et routeur_2 joignables individuellement")


def test_etat_shards():
    for rs, hotes in SHARDS.items():
        verifier_replica_set(rs, hotes, PORT_SHARD)
    print("[OK] 3 shards sains : 1 PRIMARY + 2 SECONDARY chacun (état réel)")


def test_etat_config_servers():
    verifier_replica_set("configRs", CONFIG, PORT_CONFIG)
    print("[OK] configRs sain : 1 PRIMARY + 2 SECONDARY (état réel)")


def test_historique():
    """Une insertion doit apparaître dans historique.log (donc historique est vivant)."""
    c = MongoClient(URI, serverSelectionTimeoutMS=5000)
    col = c["test_cluster"]["probe"]
    res = col.insert_one({"_msg": "historique", "ts": time.time()})
    cle = str(res.inserted_id)
    try:
        for _ in range(10):
            time.sleep(1)
            if os.path.exists(LOG_HISTORIQUE):
                with open(LOG_HISTORIQUE, encoding="utf-8") as f:
                    if cle in f.read():
                        print("[OK] l'insertion est journalisée par historique")
                        return
        raise AssertionError("insertion absente de historique.log (historique éteint ?)")
    finally:
        col.delete_one({"_id": res.inserted_id})


def test_ecriture_majoritaire():
    c = MongoClient(URI, serverSelectionTimeoutMS=5000)
    col = c["test_cluster"]["probe"].with_options(
        write_concern=WriteConcern("majority", wtimeout=5000))
    res = col.insert_one({"_msg": "probe", "ts": time.time()})
    found = col.find_one({"_id": res.inserted_id})
    assert found and found["_msg"] == "probe"
    col.delete_one({"_id": res.inserted_id})
    print("[OK] écriture/lecture/suppression via routeur (w=majority)")


# ---------- Configuration (métadonnées : ne détectent pas une panne) ----------

def test_config_shards():
    c = MongoClient(URI, serverSelectionTimeoutMS=5000)
    shards = list(c["config"].shards.find({}))
    noms = sorted(s["_id"] for s in shards)
    assert noms == ["rs_a", "rs_b", "rs_c"], f"shards inattendus : {noms}"
    for s in shards:
        host = s.get("host", "")
        membres = host.split("/", 1)[1].split(",") if "/" in host else []
        assert len(membres) == 3, f"{s['_id']} doit déclarer 3 membres : {host}"
    print("[OK] configuration : 3 shards déclarés, 3 membres chacun")


def test_config_collection_shardee():
    c = MongoClient(URI, serverSelectionTimeoutMS=5000)
    db = c["config"]
    coll = db.collections.find_one({"_id": "books.books"})
    assert coll is not None, "books.books n'est pas shardée"
    assert coll.get("key") == {"_id": "hashed"}, f"clé inattendue : {coll.get('key')}"
    # Depuis MongoDB 5.0, config.chunks est relié à la collection par son uuid (plus de champ ns)
    chunks = list(db.chunks.aggregate([
        {"$match": {"uuid": coll["uuid"]}},
        {"$group": {"_id": "$shard", "n": {"$sum": 1}}},
    ]))
    assert {x["_id"] for x in chunks} == {"rs_a", "rs_b", "rs_c"}, f"chunks mal répartis : {chunks}"
    print(f"[OK] configuration : books.books shardée (hashed), chunks : {[(x['_id'], x['n']) for x in chunks]}")


def test_donnees_books():
    c = MongoClient(URI, serverSelectionTimeoutMS=5000)
    count = c["books"]["books"].count_documents({})
    assert count > 0, "books.books est vide (import attendu)"
    print(f"[OK] données accessibles via routeur ({count} documents)")


def main():
    tests = [
        test_routeurs,
        test_etat_shards,
        test_etat_config_servers,
        test_historique,
        test_ecriture_majoritaire,
        test_config_shards,
        test_config_collection_shardee,
        test_donnees_books,
    ]
    erreurs = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            erreurs += 1
            print(f"[ECHEC] {t.__name__}: {e}")
    if erreurs:
        print(f"\n{erreurs} test(s) en échec")
        return 1
    print(f"\nTous les tests sont passés ({len(tests)}/{len(tests)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())