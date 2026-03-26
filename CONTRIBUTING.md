[🇫🇷 Français](CONTRIBUTING.fr.md) | 🇬🇧 English

# Contributing to Tawiza

Thank you for your interest in Tawiza! This guide covers how to contribute, project rules, and the validation workflow.

## Table of Contents

- [First contribution?](#first-contribution)
- [Setup](#setup)
- [Contribution workflow](#contribution-workflow)
- [Branch protection rules](#branch-protection-rules)
- [Code standards](#code-standards)
- [Project structure](#project-structure)
- [Adding a data source](#adding-a-data-source)
- [Pre-commit hooks](#pre-commit-hooks)
- [License and rights](#license-and-rights)

---

## First contribution?

Look for issues labeled [`good first issue`](https://github.com/tawiza/tawiza/labels/good%20first%20issue) or [`contributor-friendly`](https://github.com/tawiza/tawiza/labels/contributor-friendly) — they are specifically prepared for new contributors.

Welcome contributions include:
- Adding a new data source (French government API, open data)
- Improving the dashboard (new visualizations, UX)
- Adding tests for an existing module
- Fixing a bug
- Improving documentation

---

## Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker & Docker Compose
- PostgreSQL 15+ (or via Docker)
- Redis 7+ (or via Docker)

### Installation

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/tawiza.git
cd tawiza

# 2. Services (PostgreSQL + Redis)
docker compose up -d db redis

# 3. Backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # Edit to match your config

# 4. Pre-commit hooks (mandatory)
pip install pre-commit
pre-commit install

# 5. Database
alembic upgrade head

# 6. Frontend
cd frontend
npm install
cp .env.local.example .env.local
cd ..

# 7. Run
# Terminal 1: Backend
uvicorn src.interfaces.api.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

### Verification

```bash
# Backend tests
pytest tests/ -v

# Lint
ruff check src/
ruff format --check src/

# Frontend lint
cd frontend && npm run lint
```

---

## Contribution workflow

### 1. Create a branch

```bash
git checkout -b feat/my-new-feature
# or
git checkout -b fix/bug-fix
```

Branch naming conventions:
- `feat/` — new feature
- `fix/` — bug fix
- `docs/` — documentation
- `refactor/` — refactoring without functional change
- `test/` — adding or modifying tests
- `chore/` — maintenance, dependencies, CI

### 2. Code

- Follow existing project conventions
- Add tests for all new code
- Verify existing tests still pass
- Pre-commit hooks will automatically validate your code

### 3. Commit

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add regional subsidy analysis
fix: correct BODACC date parsing
docs: update installation guide
refactor: simplify SIRENE data pipeline
test: add DataHunter tests
chore: update FastAPI dependencies
```

### 4. Pull Request

- Fill in the PR template
- Link the related issue (`Fixes #123`)
- Make sure CI passes (mandatory)
- Wait for a maintainer review

---

## Branch protection rules

The `main` branch is protected:

| Rule | Description |
|------|-------------|
| **CI required** | CI workflow (lint + tests + build) must be green |
| **Branch up to date** | Your branch must be up to date with `main` before merge |
| **Force push** | Forbidden on `main` |
| **Deletion** | Cannot delete `main` |
| **CODEOWNERS** | Listed maintainers are automatically assigned for review |

### Merge types

| Type | Allowed | Usage |
|------|:-------:|-------|
| **Squash merge** | Yes | 1 PR = 1 clean commit in `main` (recommended) |
| **Rebase merge** | No | Disabled |
| **Merge commit** | No | Disabled — keeps linear history |

---

## Code standards

### Python (Backend)

- **Formatter**: `ruff format` (Black-compatible)
- **Linter**: `ruff check` with rules from `pyproject.toml`
- **Types**: Type hints encouraged (not required everywhere)
- **Tests**: pytest + pytest-asyncio for async code
- **Security**: `bandit` for vulnerability scanning

### TypeScript (Frontend)

- **Linter**: ESLint with Next.js config
- **Style**: Tailwind CSS + shadcn/ui
- **Components**: Functional with hooks
- **State**: SWR for data fetching

### General rules

- No secrets in code (use environment variables)
- No `# type: ignore` without an explanatory comment
- No `any` in TypeScript unless justified
- Public functions have a docstring
- Error messages are in English

---

## Project structure

```
tawiza/
├── src/                    # Python backend
│   ├── domain/             # Business entities (zero external deps)
│   ├── application/        # Use cases, services, DTOs
│   ├── infrastructure/     # Concrete adapters
│   │   ├── agents/tajine/  # TAJINE agent (AI core)
│   │   ├── datasources/    # 19 API adapters
│   │   ├── ml/             # Fine-tuning, active learning
│   │   ├── crawler/        # Adaptive crawler
│   │   └── knowledge_graph/# Neo4j client
│   └── interfaces/api/     # FastAPI routes + WebSocket
├── frontend/               # Next.js 15
│   ├── app/dashboard/      # Dashboard pages (7)
│   ├── components/         # React components (shadcn/ui)
│   └── hooks/              # SWR + custom hooks
├── tests/                  # Tests (unit, integration, e2e)
├── docs/                   # Documentation
├── alembic/                # Database migrations
└── docker/                 # Extra Docker configs
```

---

## Adding a data source

Tawiza is designed to easily integrate new sources. See `docs/data-sources.md` for the full guide.

In short:
1. Create an adapter in `src/infrastructure/datasources/adapters/`
2. Implement the `DataSourceAdapter` interface
3. Register in the registry (`manager.py`)
4. Add tests in `tests/unit/datasources/`
5. Document in the catalog (`docs/data-sources.md`)

You can also use the **Data Source Request** issue template to propose a source without coding it yourself.

---

## Pre-commit hooks

The project uses [pre-commit](https://pre-commit.com/) to automatically validate your code before each commit:

| Hook | Purpose |
|------|---------|
| `trailing-whitespace` | Removes trailing spaces |
| `end-of-file-fixer` | Ensures newline at end of file |
| `check-yaml` | Validates YAML syntax |
| `check-json` | Validates JSON syntax |
| `check-added-large-files` | Blocks files > 1 MB |
| `check-merge-conflict` | Detects forgotten merge conflict markers |
| `detect-private-key` | Prevents committing private keys |
| `ruff` | Python lint (auto-fix) |
| `ruff-format` | Python formatting |
| `gitleaks` | Secret scanning in code |

```bash
# Installation (one time)
pip install pre-commit
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

---

## License and rights

Tawiza is licensed under **MIT**. By contributing:

- You agree that your contributions are published under the MIT license
- You certify that you have the right to submit this code
- You retain your copyright on your contributions
- Anyone can use, modify, and redistribute the code (including commercially)

See the [LICENSE](LICENSE) file for the full text.

---

## Need help?

- [GitHub Discussions](https://github.com/tawiza/tawiza/discussions) — Questions, ideas, feedback
- [Issues](https://github.com/tawiza/tawiza/issues) — Bugs and feature requests
- [Documentation](docs/) — Technical guides
