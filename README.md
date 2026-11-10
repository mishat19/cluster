# Projet 1 - Mise à l'échelle (MongoDB sharded avec Docker)

Cluster MongoDB simulé avec Docker Compose :
- 2 routeurs `mongos` : `routeur_1`, `routeur_2`
- 3 serveurs de configuration : `config_1`, `config_2`, `config_3` (replica set `configRs`)
- 3 shards (1 principal + 2 secondaires chacun) :
  - `principal_a`, `secondaire_a_1`, `secondaire_a_2` (`rs_a`)
  - `principal_b`, `secondaire_b_1`, `secondaire_b_2` (`rs_b`)
  - `principal_c`, `secondaire_c_1`, `secondaire_c_2` (`rs_c`)
- 1 serveur `historique` journalisant les modifications (change streams)
- Initialisation automatique (`init_cluster`) : replica sets, ajout des shards, sharding de `books.books` et import des données

## Prérequis
- Docker Desktop / Docker Engine avec le plugin Compose (`docker compose`)
- Python 3.10+ (pour `lancer.py` et les tests locaux)

## Lancement (commande unique)
Depuis la racine du projet :
```bash
python lancer.py
```
Cela construit/démarre les conteneurs, initialise le cluster, importe `scripts/books.txt` dans `books.books` et démarre le service `historique`.

Arrêt :
```bash
python lancer.py stop
```

## Accès
- Routeur 1 : `mongodb://localhost:27017`
- Routeur 2 : `mongodb://localhost:27018`

Vérification rapide :
```bash
docker compose ps
docker logs -f init_cluster
docker logs -f historique
```

## Tests (éclat et réplicats)
Le cluster doit être démarré et initialisé :
```bash
python -m pip install pymongo
python tests/test_cluster.py
```
Le script vérifie : accessibilité des 2 routeurs, présence des 3 shards (3 membres chacun), sharding de `books.books`, accès aux données importées, présence des réplicats et opérations d'écriture/lecture via mongos.

## Structure du projet
- `docker-compose.yml` : définition de l'infrastructure
- `python/init_cluster.py` : initialisation du cluster et import des données
- `python/historique.py` : journalisation des changements
- `python/Dockerfile` : image Python utilisée par `init_cluster` et `historique`
- `scripts/books.txt` : jeu de données à importer
- `tests/test_cluster.py` : tests Python du cluster
- `lancer.py` : lancement/arrêt du projet
- `assets/b.a.-ba.txt` : définitions des directives Docker/Compose/MongoDB
- `assets/historique.txt` : difficultés, solutions et sitographie
- `documentation.html` : documentation de mise en œuvre et de maintenance

## Persistance et réinitialisation
Les données MongoDB et l'historique sont stockés dans des volumes Docker nommés. Pour repartir de zéro :
```bash
python lancer.py stop
docker compose down -v
python lancer.py
```

## Maintenance (pour débutant)
- Consulter `docker compose ps` et `docker compose logs <service>` en cas de problème.
- Ne pas modifier les noms de conteneurs/replica sets sans adapter `init_cluster.py`, les tests et la doc.
- En cas de corruption ou de changement de topologie, supprimer les volumes (`down -v`) puis relancer.
- Les routeurs exposés sont `27017` (hôte -> `routeur_1`) et `27018` (hôte -> `routeur_2`) ; les shards/config utilisent leurs ports internes dans le réseau Docker.
