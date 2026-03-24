# Contribuer a Tawiza

Merci de votre interet pour Tawiza ! Ce guide explique comment contribuer, les regles du projet, et le workflow de validation.

## Table des matieres

- [Premiere contribution ?](#premiere-contribution-)
- [Mise en place](#mise-en-place)
- [Workflow de contribution](#workflow-de-contribution)
- [Regles de la branche main](#regles-de-la-branche-main)
- [Standards de code](#standards-de-code)
- [Structure du projet](#structure-du-projet)
- [Ajouter une source de donnees](#ajouter-une-source-de-donnees)
- [Hooks pre-commit](#hooks-pre-commit)
- [Licence et droits](#licence-et-droits)

---

## Premiere contribution ?

Regardez les issues avec le label [`good first issue`](https://github.com/hamidedefr/tawiza/labels/good%20first%20issue) — elles sont specifiquement preparees pour les nouveaux contributeurs.

Exemples de contributions bienvenues :
- Ajouter une nouvelle source de donnees (API gouvernementale, open data)
- Ameliorer le dashboard (nouvelles visualisations, UX)
- Ajouter des tests pour un module existant
- Corriger un bug
- Ameliorer la documentation

---

## Mise en place

### Prerequisites

- Python 3.11+
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
cp .env.example .env  # Editez selon votre config

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

### Verification

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

### 1. Creer une branche

```bash
git checkout -b feat/ma-nouvelle-feature
# ou
git checkout -b fix/correction-du-bug
```

Conventions de nommage :
- `feat/` — nouvelle fonctionnalite
- `fix/` — correction de bug
- `docs/` — documentation
- `refactor/` — refactoring sans changement fonctionnel
- `test/` — ajout ou modification de tests
- `chore/` — maintenance, dependances, CI

### 2. Coder

- Suivez les conventions existantes du projet
- Ajoutez des tests pour tout nouveau code
- Verifiez que les tests existants passent
- Les hooks pre-commit valident automatiquement votre code

### 3. Commit

Nous utilisons [Conventional Commits](https://www.conventionalcommits.org/) :

```
feat: ajouter l'analyse des subventions regionales
fix: corriger le parsing des dates BODACC
docs: mettre a jour le guide d'installation
refactor: simplifier le pipeline de donnees SIRENE
test: ajouter les tests pour le DataHunter
chore: mettre a jour les dependances FastAPI
```

### 4. Pull Request

- Remplissez le template de PR
- Liez l'issue concernee (`Fixes #123`)
- Assurez-vous que la CI passe (obligatoire)
- Attendez la review d'un mainteneur

---

## Regles de la branche main

La branche `main` est protegee. Voici les regles en vigueur :

| Regle | Valeur | Description |
|-------|--------|-------------|
| **Review obligatoire** | 1 approbation minimum | Un mainteneur doit approuver avant merge |
| **CI obligatoire** | Tests doivent passer | Le workflow CI (lint + tests + build) doit etre vert |
| **Branch a jour** | Oui | Votre branche doit etre a jour avec `main` avant merge |
| **Reviews perimees** | Dismissees | Si vous modifiez la PR apres review, il faut une nouvelle approbation |
| **Conversations resolues** | Obligatoire | Tous les commentaires de review doivent etre resolus |
| **Historique lineaire** | Oui | Pas de merge commits — squash ou rebase uniquement |
| **Force push** | Interdit | Impossible de force-push sur `main` |
| **Suppression** | Interdite | Impossible de supprimer `main` |
| **CODEOWNERS** | Actif | Les mainteneurs listes dans `CODEOWNERS` sont automatiquement assignes |

### Ce que ca signifie concretement

**Pour les contributeurs :**
1. Vous ouvrez une PR depuis votre fork
2. La CI tourne automatiquement (lint, tests, build Docker)
3. Un mainteneur review votre code
4. Si des modifications sont demandees, vous les faites et poussez
5. Le mainteneur approuve → la PR est mergee (squash)
6. Votre branche est automatiquement supprimee

**Pour les mainteneurs :**
- Tout le monde passe par les memes regles (sauf bypass admin en urgence)
- Les PRs de Dependabot (securite) sont traitees en priorite
- Le `CODEOWNERS` assigne automatiquement les reviewers

### Types de merge autorises

| Type | Autorise | Usage |
|------|:--------:|-------|
| **Squash merge** | Oui | 1 PR = 1 commit propre dans `main` (recommande) |
| **Rebase merge** | Oui | Conserve les commits individuels |
| **Merge commit** | Non | Desactive pour garder un historique lineaire |

---

## Standards de code

### Python (Backend)

- **Formatter** : `ruff format` (compatible Black)
- **Linter** : `ruff check` avec les regles du `pyproject.toml`
- **Types** : Type hints encourages (pas obligatoires partout)
- **Tests** : pytest + pytest-asyncio pour le code async
- **Securite** : `bandit` pour le scan de vulnerabilites

### TypeScript (Frontend)

- **Linter** : ESLint avec config Next.js
- **Style** : Tailwind CSS + shadcn/ui
- **Composants** : Fonctionnels avec hooks
- **State** : SWR pour le data fetching

### Regles generales

- Pas de secrets dans le code (utiliser les variables d'environnement)
- Pas de `# type: ignore` sans commentaire explicatif
- Pas de `any` en TypeScript sauf cas justifie
- Les fonctions publiques ont une docstring
- Les messages d'erreur sont en anglais (i18n plus tard)

---

## Structure du projet

```
tawiza/
├── src/                    # Backend Python
│   ├── domain/             # Entites metier (zero dependance externe)
│   ├── application/        # Use cases, services, DTOs
│   ├── infrastructure/     # Adapters concrets
│   │   ├── agents/tajine/  # Agent TAJINE (coeur IA)
│   │   ├── agents/camel/   # Workforce multi-agents
│   │   ├── datasources/    # Adaptateurs 18+ APIs
│   │   ├── ml/             # Fine-tuning, active learning
│   │   ├── crawler/        # Crawler adaptatif
│   │   └── knowledge_graph/# Neo4j client
│   └── interfaces/api/     # FastAPI routes + WebSocket
├── frontend/               # Next.js 14
│   ├── app/dashboard/      # Pages du dashboard (15+)
│   ├── components/         # Composants React (shadcn/ui)
│   └── hooks/              # Hooks SWR + custom
├── tests/                  # Tests (unit, integration, e2e)
├── docs/                   # Documentation
├── alembic/                # Migrations base de donnees
└── docker/                 # Configs Docker supplementaires
```

---

## Ajouter une source de donnees

Tawiza est concu pour integrer facilement de nouvelles sources. Voir `docs/data-sources.md` pour le guide complet.

En resume :
1. Creer un adaptateur dans `src/infrastructure/datasources/adapters/`
2. Implementer l'interface `DataSourceAdapter`
3. Enregistrer dans le registry (`manager.py`)
4. Ajouter les tests dans `tests/unit/datasources/`
5. Documenter dans le catalogue (`docs/data-sources.md`)

---

## Hooks pre-commit

Le projet utilise [pre-commit](https://pre-commit.com/) pour valider automatiquement votre code avant chaque commit :

| Hook | Role |
|------|------|
| `trailing-whitespace` | Supprime les espaces en fin de ligne |
| `end-of-file-fixer` | Assure un saut de ligne en fin de fichier |
| `check-yaml` | Valide la syntaxe YAML |
| `check-json` | Valide la syntaxe JSON |
| `check-added-large-files` | Bloque les fichiers > 1 Mo |
| `check-merge-conflict` | Detecte les marqueurs de conflit oublies |
| `detect-private-key` | Empeche le commit de cles privees |
| `ruff` | Lint Python (fix automatique) |
| `ruff-format` | Formatage Python |
| `gitleaks` | Scanning de secrets dans le code |

```bash
# Installation (a faire une seule fois)
pip install pre-commit
pre-commit install

# Lancer manuellement sur tous les fichiers
pre-commit run --all-files
```

---

## Licence et droits

Tawiza est sous licence **MIT**. En contribuant :

- Vous acceptez que vos contributions soient publiees sous licence MIT
- Vous certifiez que vous avez le droit de soumettre ce code
- Vous conservez vos droits d'auteur sur vos contributions
- N'importe qui peut utiliser, modifier, et redistribuer le code (y compris commercialement)

Voir le fichier [LICENSE](LICENSE) pour le texte complet.

---

## Besoin d'aide ?

- [GitHub Discussions](https://github.com/hamidedefr/tawiza/discussions) — Questions, idees, retours
- [Issues](https://github.com/hamidedefr/tawiza/issues) — Bugs et feature requests
- [Documentation](docs/) — Guides techniques
