# Politique de sécurité

## Signaler une vulnérabilité
Ne créez pas d'issue publique. Utilisez *Security > Report a vulnerability* (GitHub private advisories) ou contactez les mainteneurs : `security@example.invalid` (**à remplacer**).
Nous visons un accusé de réception sous 72 h.

## Périmètre sensible
Authentification/RBAC, file d'approbation, exécuteur d'actions, isolation des analyses de fichiers, gestion des secrets, résistance à la prompt injection.

## Règles pour les contributeurs
- Jamais de secrets, échantillons malware, logs ou pcap réels dans Git.
- Contenu extrait (strings, logs, headers réseau) = donnée non fiable, jamais instruction pour un LLM.
- Tout outil exposant une action L2+ doit être déclaré dans `policy/tools.yaml`.
