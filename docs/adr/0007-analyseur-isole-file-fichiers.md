# ADR-0007 : Analyseur isolé, communication par fichiers
- Statut : accepté
## Contexte
Analyser un fichier hostile expose le parseur à des attaques (boucles, plantages, exploitation). Le backend détient les sessions, la base et les clés : il ne doit pas parser ces fichiers lui-même (R7).
## Décision
- Un conteneur `analyzer` séparé : `network_mode: none`, système de fichiers en lecture seule, `cap_drop: ALL`, mémoire et processus bornés, aucun secret.
- Communication par deux volumes (inbox en lecture seule pour l'analyseur, outbox) : **pas de socket Docker**, qui donnerait un accès root à l'hôte.
- Chaque fichier est analysé dans un processus enfant jetable ; résultat en JSON.
- Le résultat est une entrée non fiable : validation stricte, provenance `tool_data` uniquement.
## Conséquences
- Fonctionne avec un simple `docker compose up`, sans orchestrateur.
- Un analyseur compromis peut forger des résultats : atténué par la validation et la revue humaine, pas supprimé.
- Pas de relance automatique ni d'expiration (évolution).
## Alternatives écartées
Analyse dans le backend (surface d'attaque), conteneur lancé par le backend via le socket Docker (élévation de privilèges), appels réseau entre services (rompt l'isolation réseau).
