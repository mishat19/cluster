# Projet 1 - Mise à l'échelle (MongoDB sharded avec Docker)

Cluster MongoDB simulé avec Docker Compose :
- 2 routeurs `mongos` : `routeur_1`, `routeur_2`
- 3 serveurs de configuration : `config_1`, `config_2`, `config_3` (replica set `configRs`)
- 3 shards (1 principal + 2 secondaires chacun) :
  - `principal_a`, `secondaire_a_1`, `secondaire_a_2` (`rs_a`)
  - `principal_b`, `secondaire_b_1`, `secondaire_b_2` (`rs_b`)
  - `principal_c`, `secondaire_c_1`, `secondaire_c_2` (`rs_c`)
- 1 serveur `historique` journalisant les modifications (change streams)
- 1 conteneur `tests` (profil `test`, lancé à la demande) qui exécute `tests/test_cluster.py`
- Initialisation automatique (`init_cluster`) : replica sets, ajout des shards, sharding de `books.books` et import des données

## Prérequis
- Docker Desktop / Docker Engine avec le plugin Compose (`docker compose`)
- Python 3 (commande `python3`, uniquement pour exécuter `lancer.py`)
- PyMongo n'a pas besoin d'être installé sur l'hôte ; il est installé dans l'image Python des conteneurs.

## Lancement (commande unique)
Depuis la racine du projet :
```bash
python3 lancer.py
```
Cela construit et démarre les conteneurs en arrière-plan. `init_cluster` initialise les replica sets, configure le sharding et importe `scripts/books.txt` dans `books.books` ; `historique` démarre après la réussite de cette initialisation.

`lancer.py` affiche `Cluster prêt.` lorsque la commande Compose de démarrage se termine, mais n'attend pas la fin de l'initialisation. Avant d'utiliser le cluster ou de lancer les tests, vérifier que `init_cluster` a terminé :
```bash
docker logs init_cluster
```
Le journal doit contenir `Cluster prêt.`. Vérifier également que le service `historique` est démarré avec `docker compose ps` ou consulter ses logs avec `docker logs historique`.

Arrêt :
```bash
python3 lancer.py stop
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
Les tests tournent dans le conteneur `tests` (profil `test`), sur le réseau `mongo-net`, car les noms `routeur_1`, `principal_a`… n'existent pas sur la machine hôte. Rien à installer localement. Le cluster doit être démarré et initialisé :
```bash
docker compose --profile test run --rm tests
```
Le script fait 8 vérifications :
- `routeur_1` et `routeur_2` joignables, chacun séparément ;
- état réel des 3 shards : 1 PRIMARY + 2 SECONDARY chacun ;
- état réel de `configRs` : 1 PRIMARY + 2 SECONDARY ;
- une insertion apparaît dans le journal de `historique` ;
- écriture/lecture/suppression via routeur avec `w=majority` ;
- 3 shards déclarés dans la configuration, 3 membres chacun ;
- `books.books` shardée sur `_id` hashé, chunks présents sur les 3 shards ;
- données `books` lisibles via routeur.

Résultat attendu : `Tous les tests sont passés (8/8)`. Si un conteneur est éteint, le test concerné échoue en le nommant.

## Structure du projet
- `docker-compose.yml` : définition de l'infrastructure
- `python/init_cluster.py` : initialisation du cluster et import des données
- `python/historique.py` : journalisation des changements
- `python/Dockerfile` : image Python utilisée par `init_cluster`, `historique` et `tests`
- `scripts/books.txt` : jeu de données à importer
- `tests/test_cluster.py` : tests Python du cluster
- `lancer.py` : lancement/arrêt du projet
- `assets/b.a.-ba.txt` : définitions des directives Docker/Compose/MongoDB
- `assets/historique.txt` : difficultés, solutions et sitographie
- `documentation.html` : documentation de mise en œuvre et de maintenance

## Persistance et réinitialisation
Les données MongoDB et l'historique sont stockés dans des volumes Docker nommés. Pour repartir de zéro :
```bash
python3 lancer.py stop
docker compose down -v
python3 lancer.py
```

## Maintenance (pour débutant)
- Consulter `docker compose ps` et `docker compose logs <service>` en cas de problème.
- Ne pas modifier les noms de conteneurs/replica sets sans adapter `init_cluster.py`, les tests et la doc.
- En cas de corruption ou de changement de topologie, supprimer les volumes (`down -v`) puis relancer.
- Les routeurs exposés sont `27017` (hôte -> `routeur_1`) et `27018` (hôte -> `routeur_2`) ; les shards/config utilisent leurs ports internes dans le réseau Docker.
