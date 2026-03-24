# Changelog

All notable changes to Tawiza will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-03-23

### Changed

- README reecrit avec l'etat reel du projet (chiffres corriges, sections mortes supprimees)
- Nettoyage typographique : em dashes, smart quotes, vocabulaire marketing
- 13 PRs Dependabot fermees (bumps majeurs a traiter manuellement)
- Ajout ROADMAP.md pour les features futures
- Description pyproject.toml simplifiee

### Removed

- Sections README mortes : browser automation, CAMEL workforce, investigation bayesienne, fine-tuning details
- Emojis et badges excessifs dans le README
- Vocabulaire marketing ("propulsee par l'IA", "cognitif", "proactive")

## [0.1.0-beta] - 2026-03-09

### Added

- 15+ sources de donnees gouvernementales francaises (SIRENE, BODACC, BOAMP, INSEE, France Travail, DVF, BAN, RNA, etc.)
- Agent TAJINE avec cycle cognitif PPDSL (5 niveaux: Discovery, Causal, Scenario, Strategy, Theoretical)
- Mode ReAct agentic pour analyses strategiques et prospectives
- Pipeline News Intelligence: RSS enhanced (65+ feeds), summarization LLM, sentiment analysis, spike detection
- Extraction de relations inter-entreprises et network analytics (graphe d'acteurs)
- Ecosystem scoring et investigation UI avec cascade graph
- Fine-tuning pipeline avec LLM-as-Judge et gestion de datasets
- Web crawling adaptatif avec stealth pool et circuit breakers
- Dashboard Next.js 14 avec 15+ pages (chat, cockpit territorial, analytics, investigation, signaux, etc.)
- Backend FastAPI avec endpoints OpenAI-compatible (integration LobeChat/Open-WebUI)
- Infrastructure PostgreSQL + pgvector + Redis
- Support Ollama local avec ROCm (AMD) et CUDA (NVIDIA)
- Fallback chain LLM: Ollama -> Groq -> OpenRouter
- Telemetrie anonyme opt-out (PostHog)
- Self-hosting complet via Docker Compose
- CLI avec TUI interactive (Textual)
- Export PDF/Markdown des analyses
- Systeme d'alertes territoriales
- Scheduled analyses avec cron
- Monitoring Prometheus + Grafana
