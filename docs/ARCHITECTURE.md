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

## API (Sprint 1)
| Route | Rôle min. | Rôle |
|---|---|---|
| `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | public / session | session cookie |
| `GET /providers` | viewer | providers + métriques (jamais d'URL ni de clé) |
| `POST /providers/{id}/complete` | analyst | appel IA ; refuse si la sensibilité des données n'est pas autorisée pour ce provider ; journalise tokens/latence |
| `GET /usage` | viewer | agrégats ; tokens `null` si non exposés (R1) |
| `GET /health`, `GET /metrics` | public | sondes |

## API (Sprint 2)
| Route | Rôle min. | Rôle |
|---|---|---|
| `GET /events?limit&type` | viewer | derniers événements (tampon en mémoire) |
| `WS /ws/events?replay=N` | viewer | flux temps réel ; Origin vérifié, session revalidée périodiquement |
| `GET /usage/tokens?by=agent\|model\|provider` | viewer | fenêtres 1 min / 1 h / 24 h + ventilation |
| `GET /providers` | viewer | ajoute `quota` (restant, limite, % utilisé, reset, secondes restantes) |
| `GET /agents`, `POST /agents/demo/run` | viewer / analyst | agent de démonstration (désactivé par défaut) |

## API (Sprint 4) : voir docs/APPROVALS.md
| Route | Rôle min. | Rôle |
|---|---|---|
| `GET /policy` | viewer | outils et niveaux |
| `POST /actions` | analyst | proposer une action (le niveau vient de la politique) |
| `GET /actions?status=`, `GET /actions/{id}` | analyst | file et détail |
| `POST /actions/{id}/approve` | selon le niveau (analyst L2, admin L3) | approuve le hash vu ; `dry_run` possible |
| `POST /actions/{id}/reject` | analyst | rejette |
| `POST /agents/demo/propose` | analyst | l'agent de démonstration propose une action (si activé) |

## API (Sprint 6) : voir docs/MALWARE.md
| Route | Rôle min. | Rôle |
|---|---|---|
| `POST /samples?filename=` | analyst | dépôt (corps brut `application/octet-stream`, lu en flux, taille limitée) |
| `GET /samples`, `GET /samples/{id}` | analyst | liste ; détail avec rapport |
| `DELETE /samples/{id}` | admin | supprime l'échantillon, son résultat et la ligne en base |
