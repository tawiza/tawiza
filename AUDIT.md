# Audit reel du repo - 2026-03-23

> Fichier temporaire - NE PAS COMMIT

## Pages frontend qui EXISTENT (repertoires dans app/dashboard/)

19 repertoires, 12 dans la sidebar active (sidebar.tsx) :

### Dans la sidebar (12)
1. main (Vue d'ensemble)
2. ai-chat (Chat TAJINE)
3. tajine (Analyse Territoriale)
4. signals (Signaux)
5. news-intelligence (News)
6. investigation (Investigation)
7. decisions (Decisions)
8. analytics (Analytics)
9. web-intel (Web Intel)
10. departments (Departements)
11. fine-tuning (Fine-Tuning)
12. settings (Configuration)

### Repertoires existants mais PAS dans la sidebar (7)
- alertes
- compare
- crawl-intel
- data-sources (present dans routes.tsx mais pas sidebar.tsx)
- epci
- intelligence (present dans routes.tsx mais pas sidebar.tsx)
- predictions (present dans routes.tsx mais pas sidebar.tsx)

## Endpoints API qui EXISTENT
- Total : ~466 (35 @app + 431 @router)
- Principaux groupes :
  - /api/v1/tajine/* (~30 endpoints - analyse, conversations, analytics, departments)
  - /api/v1/orchestration/* (pipelines, services, health)
  - /api/v1/watcher/* (alertes, watchlist)
  - /api/v1/conversations/* (CRUD conversations, messages)
  - /api/v1/export/* (pdf, markdown, formats)
  - /api/v1/sources/* (statut des sources)
  - Plus: health, websocket, datasets, ollama, ML, etc.

## APIs externes avec du code reel (19 adaptateurs)
1. SIRENE - recherche-entreprises.api.gouv.fr (pas d'auth)
2. BODACC - bodacc-datainfogreffe (pas d'auth)
3. BOAMP - marches publics (pas d'auth)
4. DVF - api.cquest.org/dvf (pas d'auth)
5. INSEE Local - api.insee.fr (auth OAuth2)
6. France Travail - api.francetravail.io (auth OAuth2)
7. BAN - geocodage (pas d'auth)
8. RNA - via recherche-entreprises (pas d'auth)
9. Subventions - (pas d'auth)
10. OFGL - finances locales (pas d'auth)
11. MELODI - api.insee.fr/melodi (auth)
12. GDELT - api.gdeltproject.org (pas d'auth)
13. DBNomics - api.db.nomics.world (pas d'auth)
14. Google News - scraping (pas d'auth)
15. CommonCrawl - archive web (pas d'auth)
16. PyTrends - Google Trends (pas d'auth)
17. RSS Enhanced - flux RSS (pas d'auth)
18. Wikipedia Pageviews - (pas d'auth)
19. Geo - geo.api.gouv.fr (pas d'auth)
- Banque de France mentionnee dans collect_all_v2.py aussi

Statut : le code existe pour 19 sources. Non teste si elles fonctionnent toutes.

## Tests
- Fichiers de test : 200
- Fonctions de test : 3389
- Non teste si ils passent (pas de venv sur le host)

## Agent TAJINE
- Cycle PPDSL : code present pour les 5 niveaux
- Discovery : le plus avance
- Causal, Scenario, Strategy, Theoretical : code present, non garanti
- README dit deja "en cours de simplification et calibrage"

## Docker
- Services : postgres, redis, prometheus, grafana
- docker-compose.yml present et configure

## Alembic
- 10 migrations presentes
- alembic.ini configure

## Ce qui est GONFLE dans le README
- "22 pages" : 19 repertoires, 12 dans la sidebar
- "40+ endpoints" : ~466 routes, mais beaucoup sont internes
- "Stable" pour le dashboard : c'est "en cours" au mieux
- "18+ APIs integrees" : 19 adaptateurs codees, defensible mais "fonctionnel" non garanti
- Vocabulaire marketing : "propulsee par l'IA", "cognitif", "proactive", etc.

## PRs ouvertes (13)
- TOUTES des bumps Dependabot (npm + GitHub Actions)
- Aucune PR de code/feature en attente
