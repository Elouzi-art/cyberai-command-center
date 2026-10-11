# Garde-fou : politique et file d'approbation (R5, R9)

Toute action proposée par un agent ou un analyste passe par `app/actions.py`. Le niveau de risque est calculé par `policy/tools.yaml` (jamais par le LLM ni par la requête).

| Niveau | Politique | Validation |
|---|---|---|
| L0, L1 | lecture seule, enrichissement en liste blanche | automatique, journalisée |
| L2 | actif (scan, détonation) | file d'attente, rôle `analyst` |
| L3 | impact (blocage, isolation) | file d'attente, rôle `admin`, rollback obligatoire, TTL ≤ 60 min |
| L4 et outil inconnu | interdit | refusé, jamais en file, journalisé |

## Flux
```text
proposition → politique (niveau, rôle requis) → file (pending, hash des paramètres, expiration)
→ humain : voit la commande exacte + hash → approuve CE hash (ou dry-run, ou rejette)
→ prise en charge atomique (pending → approved) → exécuteur → executed | failed → audit + événement
```
Statuts : `pending`, `approved`, `rejected`, `expired`, `executed`, `failed`. Les paramètres sont **immuables** : pour changer une action, on la rejette et on en propose une nouvelle.

## Menaces traitées
| Attaque / erreur | Défense | Test |
|---|---|---|
| L'agent ou la requête choisit son niveau | niveau lu dans la politique ; champs inconnus refusés (422) | `test_request_cannot_choose_its_own_risk_level` |
| Outil inconnu ou L4 | refusé, audité ; l'exécuteur refuse aussi L4 | `test_forbidden_and_unknown_tools…`, `test_executor_refuses_l4…` |
| Politique affaiblie par erreur | le chargement échoue (plancher de validation par niveau, `default_level` = L4, rollback déclaré) | `test_policy_cannot_be_weakened` |
| Politique absente | l'application ne démarre pas (échec fermé) | `test_app_refuses_to_start_without_policy` |
| Analyste approuvant du L3 | refus 403 + audit | `test_analyst_cannot_approve_l3…` |
| Auto-approbation | refusée pour une demande humaine (sauf `ALLOW_SELF_APPROVAL=true`, à réserver au développement) | `test_no_self_approval…` |
| Approuver autre chose que ce qui est affiché | l'approbation porte le hash vu ; l'interface envoie le hash affiché | `test_approval_must_target_the_hash…` |
| Falsification des paramètres en base | hash recalculé avant exécution, action bloquée | `test_tampered_params…` |
| Double exécution / course entre deux décisions | `UPDATE … WHERE status='pending' AND expires_at > now` atomique | `test_claim_is_atomic…`, `test_double_approval…` |
| Exécution après expiration | expiration à la lecture et à la prise en charge | `test_expired_request_never_executes` |
| Politique modifiée après la proposition | approbation refusée, re-soumission exigée | `test_policy_change_after_proposal…` |
| Fuite de paramètres dans les journaux | l'audit et les événements ne contiennent que l'empreinte, jamais les valeurs | `test_params_never_leak…` |
| CSRF | contrôle de `Origin` sur toute route mutante | `test_foreign_origin_rejected_on_every_mutating_route` |
| XSS via paramètres ou justification | rendu texte par React, jamais de HTML | `Approvals.test.tsx` |

## Limites connues (Sprint 4)
- **L'exécuteur est factice** : aucun effet réel. Il est dans le même processus ; l'interface (requête immuable en entrée, résultat en sortie, aucun accès à la base) est prévue pour le déplacer dans un processus séparé avec identifiants éphémères avant tout outil réel (ADR-0006).
- Le niveau dépend **de l'outil seul**, pas encore des paramètres (une plage d'adresses de 1 hôte ou de /8 a le même niveau).
- Une action `approved` dont l'exécution est interrompue (arrêt du serveur) reste `approved` : elle n'est jamais rejouée automatiquement.
- L'expiration est évaluée à la lecture et à l'approbation, pas par une tâche de fond.
- Pas de notification (e-mail, chat) : l'approbateur voit la file dans le dashboard (badge dans la barre latérale).
- Les droits sont limités à 3 rôles ; pas de validation à deux personnes pour L3.
- Un utilisateur seul ne peut pas approuver ses propres demandes : créez un second compte (`python -m app.cli create-user`) ou, en développement uniquement, `ALLOW_SELF_APPROVAL=true`. Les actions proposées par l'agent de démonstration restent approuvables par la personne qui l'a déclenché.
