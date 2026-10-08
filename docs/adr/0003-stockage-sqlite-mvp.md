# ADR-0003 : SQLite (SQLAlchemy 2) pour le MVP
- Statut : accepté
## Contexte
MVP mono-instance : utilisateurs, sessions, journal de requêtes IA, audit log. Pas d'infrastructure lourde sans justification (R10).
## Décision
SQLite via SQLAlchemy 2. Le code n'utilise que l'ORM, donc PostgreSQL reste un changement d'URL. Tables créées au démarrage (`create_all`).
## Conséquences
- **Alembic reporté** : à introduire avant la première release ou dès le premier changement de schéma en production.
- Limiteur de connexions en mémoire : valable pour un seul processus.
- Passage à PostgreSQL (et séparation métriques/événements) prévu en v1.
