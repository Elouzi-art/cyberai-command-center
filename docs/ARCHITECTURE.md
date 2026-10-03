# Architecture (Sprint 0)

```text
React (TS strict) ─ REST/WebSocket ─> FastAPI ─> Agent Manager ─> Agents
                                                   │                 │
                                           AIProvider (adapters)   Tool adapters (JSON → événement unifié)
```

Flux secrets : `Frontend → Backend → Provider` (jamais de clé dans le navigateur).

## Couches
| Couche | Dossier | Règle |
|---|---|---|
| Contrats | `schemas/` | seule interface partagée entre chemins ; versionnés (`*.v1.json`) |
| API | `backend/app/main.py` | validation d'entrée, aucune logique métier |
| Providers | `backend/app/providers/` | tout fournisseur implémente `AIProvider` ; métrique absente → `MetricValue.unavailable()` |
| Politique | `policy/tools.yaml` | niveaux L0–L4, deny-by-default pour outil inconnu |
| Frontend | `frontend/` | consomme uniquement le schéma d'événements ; état « N/A » explicite |

## Extensions
- **Provider** : sous-classer `AIProvider`, ajouter test « métrique indisponible », déclarer dans `config.yaml`.
- **Outil cyber** : adapter retournant un événement conforme à `schemas/event.v1.json` ; déclarer niveau de risque dans `policy/tools.yaml`.
- **Agent** : derrière feature flag, privilèges minimaux, sorties conformes à `analysis_report.v1.json`.

## Isolation (à implémenter phases 2–3)
Analyse de fichiers : conteneur sans réseau, lecture seule. Exécuteur d'actions : processus séparé, credentials éphémères. Les agents n'ont jamais les credentials d'exécution.

Décisions : `docs/adr/`.
