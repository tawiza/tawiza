# Guide de démarrage - Tawiza

## Prérequis

| Outil | Version minimum | Requis |
|-------|----------------|--------|
| Python | 3.11+ | Oui |
| Node.js | 20+ | Oui |
| Docker | 24+ | Recommandé |
| PostgreSQL | 15+ | Oui (ou via Docker) |
| Redis | 7+ | Oui (ou via Docker) |
| Ollama | 0.3+ | Optionnel (LLM local) |

## Installation rapide (Docker)

La méthode la plus simple pour démarrer :

```bash
# Cloner le repo
git clone https://github.com/hamidedefr/tawiza.git
cd tawiza

# Copier la configuration
cp .env.example .env

# Lancer les services
docker compose up -d

# Vérifier
docker compose ps
```

Services disponibles :
- **Backend API** : http://localhost:8000 (docs: http://localhost:8000/docs)
- **Frontend** : http://localhost:3000
- **PostgreSQL** : localhost:5433
- **Redis** : localhost:6380

## Installation manuelle

### 1. Services de base

```bash
# Option A : Docker pour les services
docker compose up -d db redis

# Option B : Services natifs (adapter les ports dans .env)
# PostgreSQL et Redis installés localement
```

### 2. Backend Python

```bash
# Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Installer les dépendances
pip install -e ".[dev]"

# Configurer
cp .env.example .env
# Éditez .env avec vos paramètres

# Migrations base de données
alembic upgrade head

# Lancer le backend
uvicorn src.interfaces.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Next.js

```bash
cd frontend

# Installer les dépendances
npm install

# Configurer
cp .env.local.example .env.local

# Lancer le frontend
npm run dev
```

### 4. LLM local (optionnel)

Pour les fonctionnalités d'IA :

```bash
# Installer Ollama (https://ollama.ai)
curl -fsSL https://ollama.ai/install.sh | sh

# Télécharger un modèle
ollama pull qwen2.5:7b          # Modèle principal (léger)
ollama pull nomic-embed-text     # Embeddings

# Configurer dans .env
OLLAMA_BASE_URL=http://localhost:11434
```

## Vérification

```bash
# Santé du backend
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs

# Frontend
open http://localhost:3000
```

## Configuration

Voir [configuration.md](configuration.md) pour la référence complète des variables d'environnement.

### Variables essentielles

```bash
# Base de données
DATABASE_URL=postgresql+asyncpg://tawiza:changeme@localhost:5433/tawiza

# Redis
REDIS_URL=redis://localhost:6380/0

# LLM (optionnel)
OLLAMA_BASE_URL=http://localhost:11434

# Sécurité (CHANGER en production !)
SECRET_KEY=votre-cle-secrete-unique
```

## Prochaines étapes

- [Architecture](architecture.md) — Comprendre la structure du projet
- [Sources de données](data-sources.md) — APIs disponibles
- [Configuration](configuration.md) — Toutes les options
- [API Reference](api-reference.md) — Endpoints disponibles
