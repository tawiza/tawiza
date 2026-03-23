# Tawiza - Repo Public (Open Source)

## Architecture dual-repo

Ce repo (`tawiza/tawiza`) est la version **open source** du projet.
Le repo prive est `hamidedefr/MPtoO-v2`.

```
tawiza/tawiza     → Public, open source (MIT), visible par tous
hamidedefr/MPtoO-v2  → Prive, premium, confidentiel
```

### Regle fondamentale

**On ne peut pas reprendre ce qu'on a donne.** Un code publie en open source ne peut
plus devenir premium. Dans le doute, ca va dans MPtoO-V2 d'abord.

### Ce qui est PUBLIC (ce repo)

- Le site et la doc (README, CONTRIBUTING, SECURITY, architecture)
- Le dashboard Next.js (7 pages de base)
- Le backend FastAPI (endpoints publics)
- Les adaptateurs de sources de donnees (APIs gouvernementales publiques)
- Les tests de base
- Le schema des donnees (formats, pas les donnees elles-memes)
- Le docker-compose pour self-hosting

### Ce qui est PRIVE (MPtoO-V2)

- L'agent TAJINE complet (cycle PPDSL avance, calibrage, tuning)
- Les strategies Data Hunter avancees
- Le Territorial Analyzer complet (scoring 6 axes, simulateur Monte Carlo)
- Les scripts de collecte et transformation de donnees internes
- Le crawler adaptatif avec stealth pool
- Le browser agent (Playwright + CAPTCHA)
- Le fine-tuning pipeline (LoRA/DPO, LLM-as-Judge)
- Le Knowledge Graph avance (Neo4j, algorithmes de centralite)
- Les agents CAMEL workforce (12 agents)
- Le watcher/veille automatisee avance
- Les configs internes, secrets, backlog
- Les analyses et donnees exclusives
- Le monitoring avance (Langfuse, OpenTelemetry)

### Regles absolues

1. Ne JAMAIS copier du code de MPtoO-V2 vers ce repo sans verification
2. Ne JAMAIS referencer MPtoO-V2, hamidedefr, ou des chemins internes dans ce repo
3. Ne JAMAIS hardcoder des secrets, tokens, ou chemins de serveur
4. Ne JAMAIS publier des donnees brutes ou intermediaires
5. Quand on publie vers le public, TOUJOURS verifier le diff avant de push
6. Dans le doute, ca reste dans MPtoO-V2

## Conventions

### Code
- Python 3.12+, FastAPI, SQLAlchemy async
- Next.js 15, TypeScript, Tailwind CSS, shadcn/ui
- Pas d'emojis dans les commits sauf exception (securite, bug)
- Commits en francais, courts et directs
- Pas de vocabulaire marketing ("propulse par l'IA", "cognitif", "proactif")

### Documentation
- Pas d'em dashes, pas de smart quotes
- Ton sobre et factuel
- Chiffres reels, pas gonfles
- Le README decrit ce qui FONCTIONNE, pas la vision finale

## Mainteneur

@hamidedefr
