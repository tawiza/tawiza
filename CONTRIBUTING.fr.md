🇫🇷 Français | [🇬🇧 English](CONTRIBUTING.md)

# Contribuer à Tawiza

Merci de votre intérêt pour Tawiza ! Ce guide explique comment contribuer, les règles du projet, et le workflow de validation.

## Table des matières

- [Première contribution ?](#première-contribution-)
- [Mise en place](#mise-en-place)
- [Workflow de contribution](#workflow-de-contribution)
- [Règles de la branche main](#règles-de-la-branche-main)
- [Standards de code](#standards-de-code)
- [Structure du projet](#structure-du-projet)
- [Ajouter une source de données](#ajouter-une-source-de-données)
- [Hooks pre-commit](#hooks-pre-commit)
- [Licence et droits](#licence-et-droits)

---

## Première contribution ?

Regardez les issues avec le label [`good first issue`](https://github.com/tawiza/tawiza/labels/good%20first%20issue)  -  elles sont spécifiquement préparées pour les nouveaux contributeurs.

Exemples de contributions bienvenues :
- Ajouter une nouvelle source de données (API gouvernementale, open data)
- Améliorer le dashboard (nouvelles visualisations, UX)
- Ajouter des tests pour un module existant
- Corriger un bug
- Améliorer la documentation

---

## Mise en place

### Prérequis

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose
- PostgreSQL 15+ (ou via Docker)
- Redis 7+ (ou via Docker)

### Installation

```bash
# 1. Fork et clone
git clone https://github.com/VOTRE_USERNAME/tawiza.git
cd tawiza

# 2. Services (PostgreSQL + Redis)
docker compose up -d db redis

# 3. Backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # Éditez selon votre config

# 4. Pre-commit hooks (obligatoire)
pip install pre-commit
pre-commit install

# 5. Database
alembic upgrade head

# 6. Frontend
cd frontend
npm install
cp .env.local.example .env.local
cd ..

# 7. Lancer
# Terminal 1 : Backend
uvicorn src.interfaces.api.main:app --reload --port 8000

# Terminal 2 : Frontend
cd frontend && npm run dev
```

### Vérification

```bash
# Tests backend
pytest tests/ -v

# Lint
ruff check src/
ruff format --check src/

# Tests frontend
cd frontend && npm run lint
```

---

## Workflow de contribution

### 1. Créer une branche

```bash
git checkout -b feat/ma-nouvelle-feature
# ou
git checkout -b fix/correction-du-bug
```

Conventions de nommage :
- `feat/`  -  nouvelle fonctionnalité
- `fix/`  -  correction de bug
- `docs/`  -  documentation
- `refactor/`  -  refactoring sans changement fonctionnel
- `test/`  -  ajout ou modification de tests
- `chore/`  -  maintenance, dépendances, CI

### 2. Coder

- Suivez les conventions existantes du projet
- Ajoutez des tests pour tout nouveau code
- Vérifiez que les tests existants passent
- Les hooks pre-commit valident automatiquement votre code

### 3. Commit

Nous utilisons [Conventional Commits](https://www.conventionalcommits.org/) :

```
feat: ajouter l'analyse des subventions régionales
fix: corriger le parsing des dates BODACC
docs: mettre à jour le guide d'installation
refactor: simplifier le pipeline de données SIRENE
test: ajouter les tests pour le DataHunter
chore: mettre à jour les dépendances FastAPI
```

### 4. Pull Request

- Remplissez le template de PR
- Liez l'issue concernée (`Fixes #123`)
- Assurez-vous que la CI passe (obligatoire)
- Attendez la review d'un mainteneur

---

## Règles de la branche main

La branche `main` est protégée :

| Règle | Description |
|-------|-------------|
| **CI obligatoire** | Le workflow CI (lint + tests + build) doit être vert |
| **Branch à jour** | Votre branche doit être à jour avec `main` avant merge |
| **Force push** | Interdit sur `main` |
| **Suppression** | Impossible de supprimer `main` |
| **CODEOWNERS** | Les mainteneurs listés dans `CODEOWNERS` sont automatiquement assignés |

### Concrètement

**Pour les contributeurs :**
1. Vous ouvrez une PR depuis votre fork
2. La CI tourne automatiquement (lint, tests, build Docker)
3. Un mainteneur review votre code
4. Si des modifications sont demandées, vous les faites et poussez
5. Le mainteneur approuve → la PR est mergée (squash)

### Types de merge autorisés

| Type | Autorisé | Usage |
|------|:--------:|-------|
| **Squash merge** | Oui | 1 PR = 1 commit propre dans `main` (recommandé) |
| **Rebase merge** | Non | Désactivé |
| **Merge commit** | Non | Désactivé — historique linéaire |

---

## Standards de code

### Python (Backend)

- **Formatter** : `ruff format` (compatible Black)
- **Linter** : `ruff check` avec les règles du `pyproject.toml`
- **Types** : Type hints encouragés (pas obligatoires partout)
- **Tests** : pytest + pytest-asyncio pour le code async
- **Sécurité** : `bandit` pour le scan de vulnérabilités

### TypeScript (Frontend)

- **Linter** : ESLint avec config Next.js
- **Style** : Tailwind CSS + shadcn/ui
- **Composants** : Fonctionnels avec hooks
- **State** : SWR pour le data fetching

### Règles générales

- Pas de secrets dans le code (utiliser les variables d'environnement)
- Pas de `# type: ignore` sans commentaire explicatif
- Pas de `any` en TypeScript sauf cas justifié
- Les fonctions publiques ont une docstring
- Les messages d'erreur sont en anglais (i18n plus tard)

---

## Structure du projet

```
tawiza/
├── src/                    # Backend Python
│   ├── domain/             # Entités métier (zéro dépendance externe)
│   ├── application/        # Use cases, services, DTOs
│   ├── infrastructure/     # Adapters concrets
│   │   ├── agents/tajine/  # Agent TAJINE (cœur IA)
│   │   ├── agents/camel/   # Workforce multi-agents
│   │   ├── datasources/    # Adaptateurs 19 APIs
│   │   ├── ml/             # Fine-tuning, active learning
│   │   ├── crawler/        # Crawler adaptatif
│   │   └── knowledge_graph/# Neo4j client
│   └── interfaces/api/     # FastAPI routes + WebSocket
├── frontend/               # Next.js 15
│   ├── app/dashboard/      # Pages du dashboard (7)
│   ├── components/         # Composants React (shadcn/ui)
│   └── hooks/              # Hooks SWR + custom
├── tests/                  # Tests (unit, integration, e2e)
├── docs/                   # Documentation
├── alembic/                # Migrations base de données
└── docker/                 # Configs Docker supplémentaires
```

---

## Ajouter une source de données

Tawiza est conçu pour intégrer facilement de nouvelles sources. Voir `docs/data-sources.md` pour le guide complet.

En résumé :
1. Créer un adaptateur dans `src/infrastructure/datasources/adapters/`
2. Implémenter l'interface `DataSourceAdapter`
3. Enregistrer dans le registry (`manager.py`)
4. Ajouter les tests dans `tests/unit/datasources/`
5. Documenter dans le catalogue (`docs/data-sources.md`)

---

## Hooks pre-commit

Le projet utilise [pre-commit](https://pre-commit.com/) pour valider automatiquement votre code avant chaque commit :

| Hook | Rôle |
|------|------|
| `trailing-whitespace` | Supprime les espaces en fin de ligne |
| `end-of-file-fixer` | Assure un saut de ligne en fin de fichier |
| `check-yaml` | Valide la syntaxe YAML |
| `check-json` | Valide la syntaxe JSON |
| `check-added-large-files` | Bloque les fichiers > 1 Mo |
| `check-merge-conflict` | Détecte les marqueurs de conflit oubliés |
| `detect-private-key` | Empêche le commit de clés privées |
| `ruff` | Lint Python (fix automatique) |
| `ruff-format` | Formatage Python |
| `gitleaks` | Scanning de secrets dans le code |

```bash
# Installation (à faire une seule fois)
pip install pre-commit
pre-commit install

# Lancer manuellement sur tous les fichiers
pre-commit run --all-files
```

---

## Licence et droits

Tawiza est sous licence **MIT**. En contribuant :

- Vous acceptez que vos contributions soient publiées sous licence MIT
- Vous certifiez que vous avez le droit de soumettre ce code
- Vous conservez vos droits d'auteur sur vos contributions
- N'importe qui peut utiliser, modifier, et redistribuer le code (y compris commercialement)

Voir le fichier [LICENSE](LICENSE) pour le texte complet.

---

## Besoin d'aide ?

- [GitHub Discussions](https://github.com/tawiza/tawiza/discussions)  -  Questions, idées, retours
- [Issues](https://github.com/tawiza/tawiza/issues)  -  Bugs et feature requests
- [Documentation](docs/)  -  Guides techniques
