# Événements

Tout événement respecte `schemas/event.v1.json` (R3) : `id`, `timestamp`, `source`, `agent`, `type`, `severity`, `data`, `confidence`.
Les `data` ne contiennent jamais de prompt, de secret ni de contenu de fichier. Un champ non mesuré est **absent** ou `{"value": null, "available": false}`, jamais inventé (R1).

| Type | Émis par | Sévérité | `data` |
|---|---|---|---|
| `api.request` | appel provider réussi | info | `provider`, `model`, `latency_ms`, `status` |
| `token.usage` | appel provider réussi | info | `provider`, `model`, `input_tokens`, `output_tokens` (métriques `{value, available}`) |
| `api.error` | appel provider échoué | medium | `provider`, `model`, `error_type`, `latency_ms` |
| `rate_limit.warning` | quota ≥ 80 % (medium) ou ≥ 95 % (high) | medium / high | `provider`, `used_pct`, + `unit`, `remaining`, `reset_at`, `remaining_time` **si exposés** |
| `agent.started` / `agent.completed` / `agent.failed` | agents | info / info / medium | `task_id`, + `simulated: true` pour l'agent de démonstration |
| `action.proposed` / `action.approved` / `action.executed` | file d'approbation | medium (L2) ou high (L3) / info | `action_id`, `tool`, `risk_level`, `required_role` (jamais les paramètres) |
| `action.rejected` / `action.expired` | file d'approbation | info / low | idem |
| `action.failed` | exécution échouée ou intégrité compromise | medium / critical | idem |
| `action.refused` | outil interdit (L4) ou inconnu | medium | `tool`, `risk_level`, `known` |
| `sample.uploaded` | dépôt d'un fichier | info | `sample_id`, `sha256`, `size` (jamais le nom de fichier) |
| `sample.analyzed` | résultat intégré | info | `sample_id`, `sha256`, `file_type`, `rule_hits` |
| `sample.failed` | analyse en échec ou résultat rejeté | medium | `sample_id`, `sha256`, `error` (code) |

Non implémentés (prévus) : `resource.cpu`, `resource.memory`, `security.alert`.

## Règles pour le dashboard
- Un événement avec `data.simulated = true` doit être affiché comme **SIMULÉ** et exclu des totaux.
- `rate_limit.warning` : ne jamais afficher un champ absent ; n'afficher « temps avant reset » que si `remaining_time` est présent.
- Le tampon est en mémoire (1000 événements) : un redémarrage le vide. La persistance viendra avec PostgreSQL (v1).
