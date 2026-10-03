# Invariants (Definition of Done)

Chaque PR cite les invariants qu'elle touche. Aucun sprint n'est clos s'ils ne sont pas tous respectés.

| # | Invariant | Vérification |
|---|---|---|
| R1 | Aucune métrique inventée : `{"value": null, "available": false}` | test unitaire par adapter |
| R2 | Secrets uniquement côté backend, `.env.example` à jour | secret scanning CI |
| R3 | Le frontend ne dépend que du schéma d'événements unifié | validation de schémas CI |
| R4 | Toute sortie IA est étiquetée (`tool_data`, `ml_result`, `ai_observation`, `hypothesis`) + confiance | schéma de rapport strict |
| R5 | Toute action L2+ passe par la file d'approbation ; niveau calculé par la politique, pas par le LLM | test : pas d'auto-approbation |
| R6 | Contenu extrait = donnée non fiable, jamais instruction | jeu de tests prompt injection |
| R7 | Échantillons traités en conteneur isolé, sans réseau | test d'intégration |
| R8 | Aucun couplage à un fournisseur ou outil précis hors adapter | revue d'architecture |
| R9 | Chaque décision sensible est dans l'audit log | test d'intégration |
| R10 | Pas de complexité sans ADR | revue de PR |
