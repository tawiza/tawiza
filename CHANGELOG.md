# Changelog

All notable changes to Tawiza will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-03-26

### Added

- Sandbox Docker pour scan de sécurité isolé (`Dockerfile.sandbox`, `sandbox-scan.sh`, `pr-scan.sh`)
- Workflow CI `pr-sandbox.yml` : scan automatique sur chaque Pull Request
- Workflow CI `security.yml` : CodeQL, Gitleaks, Bandit, Trojan Source, Dependency Review
- Pre-commit hooks : ruff, bandit, gitleaks, detect-private-key, check-symlinks

### Fixed

- 9 imports cassés dans le backend (alignement tests/code)
- Build frontend corrigé (ports alignés, configuration cohérente)
- Accents français manquants dans l'i18n et la documentation

### Changed

- ROADMAP.md restructuré avec liens vers les issues GitHub
- `.gitignore` étendu pour MLflow et artefacts d'outils

## [0.1.1] - 2026-03-23

### Changed

- README réécrit avec l'état réel du projet (chiffres corrigés, sections mortes supprimées)
- Nettoyage typographique : em dashes, smart quotes, vocabulaire marketing
- 13 PRs Dependabot fermées (bumps majeurs à traiter manuellement)
- Ajout ROADMAP.md pour les features futures
- Description pyproject.toml simplifiée

### Removed

- Sections README mortes : browser automation, CAMEL workforce, investigation bayésienne, fine-tuning details
- Emojis et badges excessifs dans le README
- Vocabulaire marketing ("propulsée par l'IA", "cognitif", "proactive")

## [0.1.0-beta] - 2026-03-09

### Added

- 15+ sources de données gouvernementales françaises (SIRENE, BODACC, BOAMP, INSEE, France Travail, DVF, BAN, RNA, etc.)
- Agent TAJINE avec cycle cognitif PPDSL (5 niveaux: Discovery, Causal, Scenario, Strategy, Theoretical)
- Mode ReAct agentic pour analyses stratégiques et prospectives
- Pipeline News Intelligence: RSS enhanced (65+ feeds), summarization LLM, sentiment analysis, spike detection
- Extraction de relations inter-entreprises et network analytics (graphe d'acteurs)
- Ecosystem scoring et investigation UI avec cascade graph
- Fine-tuning pipeline avec LLM-as-Judge et gestion de datasets
- Web crawling adaptatif avec stealth pool et circuit breakers
- Dashboard Next.js 14 avec 7 pages (chat IA, cockpit territorial, analytics, departements, sources, parametres)
- Backend FastAPI avec endpoints OpenAI-compatible (intégration LobeChat/Open-WebUI)
- Infrastructure PostgreSQL + pgvector + Redis
- Support Ollama local avec ROCm (AMD) et CUDA (NVIDIA)
- Fallback chain LLM: Ollama -> Groq -> OpenRouter
- Télémétrie anonyme opt-out (PostHog)
- Self-hosting complet via Docker Compose
- CLI avec TUI interactive (Textual)
- Export PDF/Markdown des analyses
- Système d'alertes territoriales
- Scheduled analyses avec cron
- Monitoring Prometheus + Grafana
