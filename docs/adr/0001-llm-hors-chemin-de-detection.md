# ADR-0001 : Le LLM n'est jamais dans le chemin de détection
- Statut : accepté
## Contexte
Volume, latence, coût en tokens, et risque de prompt injection via contenu hostile.
## Décision
Outils déterministes et modèles légers extraient/détectent ; le LLM n'intervient qu'après, sur données filtrées et étiquetées (R4, R6).
## Conséquences
Rapports séparant `tool_data`, `ml_result`, `ai_observation`, `hypothesis`.
