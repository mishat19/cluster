"""Initialise le cluster : replica sets -> groupes (shards) -> découpage de books.books."""
import time

from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

PORT = 27017
REPLICA_SETS = {
    "rs_config": ["config_1", "config_2", "config_3"],
    "rs_a": ["principal_a", "secondaire_a_1", "secondaire_a_2"],
    "rs_b": ["principal_b", "secondaire_b_1", "secondaire_b_2"],
    "rs_c": ["principal_c", "secondaire_c_1", "secondaire_c_2"],
}
ROUTEURS = "mongodb://routeur_1:27017,routeur_2:27017/"


def reessayer(action, essais=30):
    """Relance une action tant que le serveur n'est pas prêt."""
    for _ in range(essais):
        try:
            return action()
        except PyMongoError as erreur:
            print(f"  en attente... ({erreur})")
            time.sleep(2)
    raise RuntimeError("Le cluster ne répond pas, abandon.")


def initier_replica_set(nom, membres):
    config = {
        "_id": nom,
        # Le 1er membre a une priorité plus haute : c'est lui qui devient PRIMARY
        "members": [
            {"_id": i, "host": f"{hote}:{PORT}", "priority": 2 if i == 0 else 1}
            for i, hote in enumerate(membres)
        ],
    }
    if nom == "rs_config":
        config["configsvr"] = True

    client = MongoClient(membres[0], PORT, directConnection=True)
    try:
        client.admin.command("replSetInitiate", config)
        print(f"{nom} : initialisé")
    except OperationFailure as erreur:
        if erreur.code != 23:  # 23 = déjà initialisé (relance du projet)
            raise
        print(f"{nom} : déjà initialisé")

    def est_primaire():
        if not client.admin.command("hello").get("isWritablePrimary"):
            raise PyMongoError(f"{membres[0]} pas encore PRIMARY")

    reessayer(est_primaire)
    print(f"{nom} : {membres[0]} est PRIMARY")


def ajouter_groupes():
    client = MongoClient(ROUTEURS)
    for nom in ("rs_a", "rs_b", "rs_c"):
        hotes = ",".join(f"{hote}:{PORT}" for hote in REPLICA_SETS[nom])
        reessayer(lambda: client.admin.command("addShard", f"{nom}/{hotes}", name=nom))
        print(f"groupe {nom} ajouté au cluster")

    # Sans ça, toute la collection resterait sur un seul groupe.
    # Clé "hashed" : les documents sont répartis tout de suite sur les 3 groupes.
    client.admin.command("enableSharding", "books")
    client.admin.command("shardCollection", "books.books", key={"_id": "hashed"})
    print("books.books découpée sur les 3 groupes")


if __name__ == "__main__":
    for nom, membres in REPLICA_SETS.items():
        initier_replica_set(nom, membres)
    ajouter_groupes()
    print("Cluster prêt.")
