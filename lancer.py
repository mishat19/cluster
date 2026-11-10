"""Lance tout le projet :   python lancer.py
Arrête tout le projet :   python lancer.py stop
"""
import subprocess
import sys

if len(sys.argv) > 1 and sys.argv[1] == "stop":
    sys.exit(subprocess.run(["docker", "compose", "down"]).returncode)

# Démarre le cluster et attend la fin de l'initialisation
resultat = subprocess.run(["docker", "compose", "up", "-d", "--build"])

if resultat.returncode == 0:
    print("Cluster démarré. Initialisation en cours (voir: docker logs -f init_cluster)")
    print("Routeurs: routeur_1 -> localhost:27017, routeur_2 -> localhost:27018")
else:
    print("Échec du démarrage, voir : docker compose logs")
    sys.exit(1)
