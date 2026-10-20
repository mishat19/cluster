"""Lance tout le projet :   python lancer.py
Arrête tout le projet :   python lancer.py stop
"""
import subprocess
import sys

if len(sys.argv) > 1 and sys.argv[1] == "stop":
    subprocess.run(["docker", "compose", "down"])
    sys.exit()

# "up" attend que init_cluster ait fini avant de démarrer historique
resultat = subprocess.run(["docker", "compose", "up", "-d", "--build"])

if resultat.returncode == 0:
    print("\nCluster prêt : routeur_1 -> localhost:27017, routeur_2 -> localhost:27018")
else:
    print("\nÉchec du démarrage, voir :  docker logs init_cluster")
    sys.exit(1)
