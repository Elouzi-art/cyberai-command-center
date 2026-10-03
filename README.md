# CyberAI Command Center

Plateforme multi-agents IA d'assistance à l'analyste cybersécurité, avec une couche d'**observabilité** : ce que font les agents, combien ils consomment, combien les APIs permettent encore, et si le système est sain.

> **Statut : Sprint 0 (fondations).** Dépôt privé. Aucun agent métier n'est encore implémenté. Voir [docs/ROADMAP.md](docs/ROADMAP.md).

## Principes non négociables
Les 10 invariants (R1–R10) sont dans [docs/INVARIANTS.md](docs/INVARIANTS.md). Les plus importants :
- Aucune métrique inventée : indisponible → `{"value": null, "available": false}`.
- L'IA n'est pas une preuve : toute sortie est étiquetée et accompagnée d'une confiance.
- Toute action dangereuse (L2+) passe par une file d'approbation humaine.
- Les secrets ne quittent jamais le backend.

## Démarrage rapide
```bash
cp .env.example .env          # puis remplacer les placeholders
docker compose up --build     # UI: http://localhost:8080  |  API: /api/health
```
Développement local : `make test`, `make lint`. Détails dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Structure
```
backend/    FastAPI (API, providers, observabilité)
frontend/   React + TypeScript strict (thème Cyberboard)
schemas/    Contrats JSON versionnés (événement, métrique, rapport, action)
policy/     Politique de risque des outils (L0–L4)
docs/       Architecture, roadmap, invariants, ADR
.github/    CI, CodeQL, Dependabot, modèles PR/issues
```

## Sécurité
Voir [SECURITY.md](SECURITY.md). Ne jamais committer d'échantillons malware, de vrais logs ou de pcap.
