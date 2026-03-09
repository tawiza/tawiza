# Contribuer a Tawiza

Merci de votre interet pour Tawiza ! Ce guide vous aidera a demarrer.

## Premiere contribution ?

Regardez les issues avec le label [`good first issue`](https://github.com/hamidedefr/tawiza/labels/good%20first%20issue) —
elles sont specifiquement preparees pour les nouveaux contributeurs.

## Mise en place de l'environnement

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

# 4. Database
alembic upgrade head

# 5. Frontend
cd frontend
npm install
cp .env.local.example .env.local
cd ..

# 6. Lancer
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

### 2. Coder

- Suivez les conventions existantes du projet
- Ajoutez des tests pour tout nouveau code
- Verifiez que les tests existants passent

### 3. Commit

Nous utilisons [Conventional Commits](https://www.conventionalcommits.org/) :

```
feat: ajouter l'analyse des subventions regionales
fix: corriger le parsing des dates BODACC
docs: mettre a jour le guide d'installation
refactor: simplifier le pipeline de donnees SIRENE
test: ajouter les tests pour le DataHunter
```

### 4. Pull Request

- Remplissez le template de PR
- Liez l'issue concernee (`Fixes #123`)
- Assurez-vous que la CI passe

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

## Structure du projet

```
tawiza/
├── src/                    # Backend Python
│   ├── domain/             # Entites metier
│   ├── application/        # Use cases, services
│   ├── infrastructure/     # Agents, datasources, DB
│   │   ├── agents/tajine/  # Agent TAJINE (coeur)
│   │   └── datasources/    # Adaptateurs APIs
│   └── interfaces/api/     # FastAPI routes
├── frontend/               # Next.js 14
│   ├── app/dashboard/      # Pages du dashboard
│   ├── components/         # Composants React
│   └── hooks/              # Hooks SWR
├── tests/                  # Tests backend
├── docs/                   # Documentation
└── docker/                 # Configs Docker
```

## Ajouter une source de donnees

Tawiza est concu pour integrer facilement de nouvelles sources. Voir `docs/data-sources.md` pour le guide complet.

En resume :
1. Creer un adaptateur dans `src/infrastructure/datasources/adapters/`
2. Implementer l'interface `DataSourceAdapter`
3. Enregistrer dans le registry
4. Ajouter les tests
5. Documenter dans le catalogue

## Besoin d'aide ?

- Ouvrez une [Discussion GitHub](https://github.com/hamidedefr/tawiza/discussions)
- Consultez la [documentation](docs/)
- Regardez les issues existantes

## License

En contribuant a Tawiza, vous acceptez que vos contributions soient sous licence MIT.
