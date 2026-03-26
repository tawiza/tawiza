# Roadmap Tawiza

## Fait

- [x] Réduction du dashboard (19 pages → 7 pages essentielles)
- [x] Pipeline de sécurité CI (CodeQL, Gitleaks, Bandit, Trojan Source)
- [x] Dependabot + Dependency Review sur les PRs
- [x] Scan automatique de sécurité sur chaque PR (sandbox Docker)
- [x] Pre-commit hooks (ruff, bandit, gitleaks, detect-private-key)
- [x] Correction des imports cassés et alignement des tests (#54 partiel)
- [x] Correction des accents français dans l'i18n
- [x] Alignement des ports et fix du build frontend

## En cours

- [ ] Tests unitaires fonctionnels ([#54](https://github.com/tawiza/tawiza/issues/54))
- [ ] Tests end-to-end des adaptateurs de sources ([#52](https://github.com/tawiza/tawiza/issues/52))
- [ ] Stabilisation de l'agent TAJINE (niveaux Causal et Scénario)
- [ ] Stabilisation du crawler adaptatif

## Prévu — Court terme

- [ ] Guide Docker Compose quick-start ([#66](https://github.com/tawiza/tawiza/issues/66))
- [ ] Traduction du README en anglais ([#53](https://github.com/tawiza/tawiza/issues/53))
- [ ] Validation OpenAPI schema en CI ([#67](https://github.com/tawiza/tawiza/issues/67))
- [ ] Auto-détection Ollama + fallback modèles ([#68](https://github.com/tawiza/tawiza/issues/68))
- [ ] Accessibilité du dashboard ([#51](https://github.com/tawiza/tawiza/issues/51))
- [ ] Activation branch protection + CodeRabbit sur GitHub

## Prévu — Moyen terme

- [ ] Finalisation CLI / TUI (fusion v2/v3)
- [ ] Fine-tuning LoRA sur des cas d'usage territoriaux
- [ ] Investigation bayésienne complète
- [ ] Extension du Knowledge Graph (Neo4j)
- [ ] Internationalisation (i18n) du frontend
- [ ] Mode offline avec cache local des APIs

## À terme

- Fusion des modules redondants de collecte
- Simplification de l'architecture des agents
- Plugin system pour les sources de données communautaires
- Jupyter Notebook pour l'analyse exploratoire
