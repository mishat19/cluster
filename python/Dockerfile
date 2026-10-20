FROM python:3.12-slim
RUN pip install --no-cache-dir pymongo
# Affiche les print() tout de suite dans "docker logs"
ENV PYTHONUNBUFFERED=1
# Les scripts sont montés ici par docker-compose (volume ./python:/app)
WORKDIR /app
