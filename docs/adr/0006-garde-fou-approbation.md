# ADR-0006 : File d'approbation avec politique en échec fermé
- Statut : accepté
## Contexte
Avant tout agent capable d'agir, il faut un frein que ni un LLM, ni un fichier hostile, ni une erreur de configuration ne puisse contourner (R5, R9).
## Décision
- Politique YAML chargée au démarrage ; invalide, absente ou affaiblie : pas de démarrage.
- Niveau calculé par outil ; outil inconnu = L4. La requête ne peut pas fournir de niveau.
- Paramètres immuables, liés par un hash SHA-256 canonique ; l'approbation vise ce hash.
- Prise en charge atomique en base ; expiration contrôlée au moment de la prise en charge.
- Exécuteur derrière une interface étroite, factice pour l'instant.
- Audit sans valeurs de paramètres (empreinte uniquement).
## Conséquences
- Rien ne s'exécute réellement tant que l'exécuteur n'est pas séparé et revu (Sprint ultérieur).
- Les évolutions de la politique exigent un redémarrage.
- Alternatives écartées : approbation en mémoire (perdue au redémarrage), niveau fourni par l'agent (contournable).
