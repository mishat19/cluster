"""Tests du cluster MongoDB sharded (éclat/répartition et réplicats).
Exécution (cluster démarré) :
  python -m pip install pymongo
  python tests/test_cluster.py
Variables optionnelles :
  MONGO_URI=mongodb://localhost:27017,localhost:27018/
"""
import os
import sys
import time

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pymongo.read_preferences import ReadPreference

URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017,localhost:27018/")


def attendre_client(uri, essais=30, delai=2):
    dernier = None
    for _ in range(essais):
        try:
            c = MongoClient(uri, serverSelectionTimeoutMS=3000)
            c.admin.command("ping")
            return c
        except PyMongoError as e:
            dernier = e
            time.sleep(delai)
    raise RuntimeError(f"Cluster inaccessible: {dernier}")


def test_routers():
    c = attendre_client(URI)
    status = c.admin.command("serverStatus")
    assert status.get("process") == "mongos", f"attendu mongos, obtenu {status.get('process')}"
    # test routeur_2
    c2 = MongoClient("mongodb://localhost:27018/", serverSelectionTimeoutMS=5000)
    assert c2.admin.command("ping").get("ok") == 1
    print("[OK] 2 routeurs (mongos) accessibles")


def test_shards_et_replicats():
    c = MongoClient(URI, serverSelectionTimeoutMS=5000)
    shards = list(c.get_database("config").shards.find({}))
    noms = sorted(s["_id"] for s in shards)
    assert noms == ["rs_a", "rs_b", "rs_c"], f"shards inattendus: {noms}"
    for s in shards:
        # host format: "rs_x/host1:port,host2:port,host3:port"
        host = s.get("host", "")
        membres = host.split("/", 1)[1].split(",") if "/" in host else []
        assert len(membres) == 3, f"{s['_id']} doit avoir 1 principal + 2 secondaires: {host}"
    print("[OK] 3 shards, chacun avec 3 membres (1 principal + 2 secondaires)")


def test_collection_sharded():
    c = MongoClient(URI, serverSelectionTimeoutMS=5000)
    db = c.get_database("config")
    coll = db.collections.find_one({"_id": "books.books"})
    assert coll is not None, "books.books n'est pas shardée"
    assert coll.get("key") == {"_id": "hashed"}, f"clé de sharding inattendue: {coll.get('key')}"
    chunks = list(db.chunks.aggregate([{"$match": {"ns": "books.books"}}, {"$group": {"_id": "$shard", "n": {"$sum": 1}}}]))
    assert chunks, "aucun chunk trouvé pour books.books"
    print(f"[OK] books.books shardée (clé hashed), chunks: {[(x['_id'], x['n']) for x in chunks]}")


def test_eclat_donnees():
    c = MongoClient(URI, serverSelectionTimeoutMS=5000)
    col = c["books"]["books"]
    count = col.count_documents({})
    assert count > 0, "books.books est vide (import attendu)"
    # Requête via routeur
    doc = col.find_one({})
    assert doc is not None
    print(f"[OK] données accessibles via routeur ({count} documents)")


def test_replicats_secondaires():
    # Vérifie que chaque replica set expose un primary et au moins un secondary joignable en lecture
    checks = [
        ("principal_a", 27018),
        ("principal_b", 27018),
        ("principal_c", 27018),
    ]
    for host, port in checks:
        direct = MongoClient(host, port, directConnection=True, serverSelectionTimeoutMS=5000)
        st = direct.admin.command("replSetGetStatus")
        members = st.get("members", [])
        states = sorted(m["stateStr"] for m in members)
        assert "PRIMARY" in states, f"{host}: pas de PRIMARY ({states})"
        assert states.count("SECONDARY") >= 2, f"{host}: secondaires insuffisants ({states})"
    # lecture via routeur avec préférence secondaire (réplicats utilisés)
    c = MongoClient(URI, read_preference=ReadPreference.SECONDARY_PREFERRED, serverSelectionTimeoutMS=5000)
    assert c["books"]["books"].find_one({}) is not None
    print("[OK] réplicats présents (PRIMARY + >=2 SECONDARY par shard) et lecture secondaire OK")


def test_ecriture_et_distribution():
    c = MongoClient(URI, serverSelectionTimeoutMS=5000)
    col = c["test_cluster"]["probe"]
    doc = {"_msg": "probe", "ts": time.time()}
    res = col.insert_one(doc)
    found = col.find_one({"_id": res.inserted_id})
    assert found and found["_msg"] == "probe"
    col.delete_one({"_id": res.inserted_id})
    print("[OK] écriture/lecture/suppression via routeur")


def main():
    tests = [
        test_routers,
        test_shards_et_replicats,
        test_collection_sharded,
        test_eclat_donnees,
        test_replicats_secondaires,
        test_ecriture_et_distribution,
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
