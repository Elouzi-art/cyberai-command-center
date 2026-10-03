# Contribuer

1. Une issue par sprint/tâche, rattachée à un milestone de phase.
2. Branche depuis `main`, PR obligatoire, CI verte requise.
3. La PR cite les invariants concernés (voir le modèle de PR) et la section « Hors périmètre ».
4. Tout choix technique structurant → un ADR dans `docs/adr/`.
5. Commits : [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`…).
6. Ajout d'un agent, provider ou adapter outil : suivre `docs/ARCHITECTURE.md` (§ Extensions) et ajouter ses tests, y compris le cas « métrique indisponible ».

Environnement : Python 3.12, Node 20, Docker. `pre-commit install` active le scan de secrets local.
