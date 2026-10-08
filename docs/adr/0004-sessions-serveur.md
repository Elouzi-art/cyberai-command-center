# ADR-0004 : Sessions côté serveur, cookie HttpOnly
- Statut : accepté
## Décision
Jeton aléatoire (256 bits) en cookie `HttpOnly`, `SameSite=Strict`, `Secure` par défaut ; seul son SHA-256 est stocké. Mots de passe hachés avec Argon2id. Rôles `viewer < analyst < admin`. Contrôle de l'en-tête `Origin` sur les requêtes mutantes. Aucun compte par défaut : création via `python -m app.cli create-user`.
## Conséquences
Révocation immédiate possible (suppression de la ligne). Frontend et API doivent partager l'origine (proxy nginx `/api`), donc pas de CORS à ouvrir.
## Limites connues
Pas de MFA ni de rotation de session au Sprint 1. Limiteur de tentatives par (utilisateur, IP) : derrière un proxy, l'IP vue est celle du proxy.
