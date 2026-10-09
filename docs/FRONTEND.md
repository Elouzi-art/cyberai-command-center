# Frontend

React 18 + TypeScript strict, thème Cyberboard (tokens CSS, sans CDN ni Google Fonts : CSP stricte).
Pas de bibliothèque de routage ni d'état global : routage par hash (`#/overview`, `#/agents`, `#/providers`), polling + WebSocket.

```
src/api.ts            appels REST (cookie de session HttpOnly, aucun stockage navigateur)
src/types/            miroirs des réponses backend et du schéma d'événements
src/hooks/            usePolling, useEventStream (reconnexion, validation du schéma)
src/components/       ui (Value, NA, Badge…), Layout, ProviderCard
src/pages/            Login, Overview, Agents, Providers
src/styles/           tokens.css, components.css
```

## Règles d'affichage
- **R1** : toute métrique indisponible s'affiche « N/A ». Jamais de 0, de barre de quota ni de « reset dans… » sans donnée.
- Les chiffres de l'agent de démonstration sont étiquetés **SIMULÉ** et exclus des totaux (agents actifs, tâches en cours).
- **R3** : un message WebSocket qui ne respecte pas `schemas/event.v1.json` est ignoré.
- Aucun `localStorage` / `sessionStorage` (règle ESLint) : la session est un cookie HttpOnly.
- Le texte venant du backend est rendu par React (échappé) ; pas de `dangerouslySetInnerHTML`.

## Développement
- Via Docker : `docker compose up --build` puis http://localhost:8080 (nginx proxifie `/api`, y compris le WebSocket).
- Via Vite : `cd frontend && npm install && npm run dev` (http://localhost:5173, proxy vers le backend sur :8000).
  Le backend vérifie l'en-tête `Origin` : ajouter `http://localhost:5173` à `ALLOWED_ORIGINS` dans `.env`.
- Contrôles : `npm run lint && npm run typecheck && npm test && npm run build`.

## Limites connues (Sprint 3)
Pas de page « Security Operations » ni « Agent Details » ; pas de graphiques ; mise à jour des cartes par polling (3 à 10 s), seul le journal d'événements est en temps réel.
