# ADR-0005 : Bus d'événements en mémoire + WebSocket
- Statut : accepté
## Contexte
Le dashboard doit suivre l'activité en temps réel. MVP mono-processus, pas d'infrastructure lourde sans justification (R10).
## Décision
`EventBus` en mémoire : tampon circulaire (1000) + files bornées par abonné. Un consommateur lent perd ses plus anciens messages, jamais le producteur. Flux via WebSocket `/ws/events`, authentifié par le cookie de session.
Garde-fous : `Origin` contrôlé (anti Cross-Site WebSocket Hijacking), session revalidée toutes les 30 s (révocation/expiration coupent le flux).
## Conséquences
- Pas de persistance ni de multi-processus : au-delà d'un worker, remplacer par Redis Streams ou PostgreSQL LISTEN/NOTIFY.
- Les alertes de quota sont dédupliquées (même niveau : silence 5 min ; escalade : immédiat).
- L'agent de démonstration émet des chiffres simulés, signalés et jamais comptabilisés (R1).
