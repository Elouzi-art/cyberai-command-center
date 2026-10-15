# Conteneur d'analyse : lance SANS réseau, système de fichiers en lecture seule (voir docker-compose.yml).
FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app && mkdir /inbox /outbox && chown 10001 /inbox /outbox
WORKDIR /app
COPY pyproject.toml .
COPY cyberai_analyzer ./cyberai_analyzer
RUN pip install --no-cache-dir .
USER 10001
CMD ["python", "-m", "cyberai_analyzer"]
