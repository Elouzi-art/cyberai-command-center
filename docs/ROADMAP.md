# Roadmap

Méthode : sprints de 2 semaines (3–4 en solo), **un chemin vertical par sprint**, contract-first (schémas JSON versionnés), agents derrière feature flags, ADR pour chaque choix, « hors périmètre » explicite par sprint. Invariants : [INVARIANTS.md](INVARIANTS.md).

## Phase 0 — Fondations (Sprint 0) ✅ ce dépôt
Repo, CI, schémas v1, squelette FastAPI + React TS strict, thème Cyberboard (tokens), `docker compose up`.

## Phase 1 — Observabilité (S1–S3) · MVP · R1 R2 R3 R8
- S1 ✅ : auth + RBAC minimal, `AIProvider` (1 local Ollama + 1 cloud), journal de requêtes (tokens, latence, erreurs)
- S2 ✅ : tokens/min/h/jour, quotas et reset **seulement si exposés**, WebSocket, agent factice
- S3 ✅ : dashboard Overview/Agents/Providers, état « N/A », `/health` `/metrics` `/usage`

## Phase 2 — Garde-fou (S4–S5) · R5 R9
S4 ✅ moteur de politique + file d'approbation + exécuteur factice + page Approvals. S5 : exécuteur séparé (processus, identifiants éphémères) — à planifier.
Moteur de politique (L0–L4), file d'approbation (hash des paramètres, expiration), exécuteur séparé (stub), audit log, page Approvals.

## Phase 3 — Malware (S6–S8) · R4 R6 R7
S6 ✅ upload sécurisé + quarantaine + conteneur sans réseau + analyse statique PE de base (hachages, entropie, sections, imports, règles) · S7 adapters pefile/ssdeep/TLSH/YARA/capa/FLOSS · S8 synthèse LLM étiquetée + VirusTotal (hash seul, L1).
Reporté : clustering HDBSCAN, classifieur EMBER.

## Phase 4 — Forensics (S9–S11) · R4 R6
S9 evtx (Hayabusa/Chainsaw) + timeline · S10 pcap (Zeek/tshark) · S11 Volatility 3 + corrélations + liste « à vérifier ».

## Phase 5 — Réseau et SOC (S12–S15) · R5 R6
S12 Network Detection **passif** · S13 détections + déduplication anti alert-fatigue · S14 SOC Agent · S15 Threat Intelligence (sources citées et datées).

## Phase 6 — v1 (S16–S18)
Threat model final, revue de sécurité, intégrations MCP/Wazuh/MISP/OpenCTI/Timesketch (versions et licences vérifiées), observabilité complète, première release publique.

## v2
Capture en direct, ML avancé, réponse active L3 avec rollback, sandbox de détonation (L2), multi-tenant, plugins.

## Pourquoi cet ordre
Observabilité d'abord (valeur centrale) → garde-fou avant tout agent actif → du plus isolé (fichier) au plus intégré (flux continus).
