# Configuration

Tawiza se configure entierement via des variables d'environnement. Copiez `.env.example` et adaptez.

## Variables essentielles

### Application

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `Tawiza` | Nom de l'application |
| `APP_ENV` | `development` | Environnement (`development`, `production`) |
| `DEBUG` | `true` | Mode debug |
| `LOG_LEVEL` | `INFO` | Niveau de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `API_HOST` | `0.0.0.0` | Adresse d'ecoute du backend |
| `API_PORT` | `8000` | Port du backend |
| `CORS_ORIGINS` | `http://localhost:3000` | Origines CORS autorisees (separes par virgule) |

### Base de donnees

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://tawiza:changeme@localhost:5433/tawiza` | URL de connexion PostgreSQL |
| `DATABASE_POOL_SIZE` | `10` | Taille du pool de connexions |
| `DATABASE_MAX_OVERFLOW` | `20` | Connexions supplementaires max |

### Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6380/0` | URL de connexion Redis |

### LLM (Ollama)

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL du serveur Ollama |
| `OLLAMA_TIMEOUT` | `120` | Timeout des requetes (secondes) |
| `OLLAMA_POOL_CONNECTIONS` | `20` | Connexions dans le pool |

### pgvector (Embeddings)

| Variable | Default | Description |
|----------|---------|-------------|
| `VECTORDB__ENABLED` | `true` | Activer la recherche vectorielle |
| `VECTORDB__EMBEDDING_MODEL` | `nomic-embed-text` | Modele d'embedding Ollama |
| `VECTORDB__EMBEDDING_DIM` | `768` | Dimension des vecteurs |
| `VECTORDB__CHUNK_SIZE` | `512` | Taille des chunks de texte |

### APIs gouvernementales

| Variable | Default | Description |
|----------|---------|-------------|
| `INSEE_CLIENT_ID` | — | Identifiant API INSEE |
| `INSEE_CLIENT_SECRET` | — | Secret API INSEE |
| `FRANCE_TRAVAIL_CLIENT_ID` | — | Identifiant API France Travail |
| `FRANCE_TRAVAIL_CLIENT_SECRET` | — | Secret API France Travail |

### Securite

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `CHANGE_ME` | Cle secrete de l'application |
| `SECURITY__JWT_ALGORITHM` | `HS256` | Algorithme JWT |
| `SECURITY__JWT_EXPIRATION_MINUTES` | `60` | Duree de vie des tokens |
| `RATE_LIMIT_PER_IP` | `100` | Requetes par minute par IP |

### Services optionnels

| Variable | Default | Description |
|----------|---------|-------------|
| `LABEL_STUDIO_URL` | — | URL de Label Studio (fine-tuning) |
| `LABEL_STUDIO_API_KEY` | — | Cle API Label Studio |
| `SENTRY_DSN` | — | DSN Sentry/GlitchTip (error tracking) |
| `LANGFUSE_SECRET_KEY` | — | Cle Langfuse (LLM observability) |

## Frontend

Variables du frontend (dans `frontend/.env.local`) :

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | URL du backend API |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000/ws` | URL WebSocket |

## Docker Compose

Le `docker-compose.yml` utilise les variables de `.env` automatiquement. Les ports par defaut sont volontairement non-standard pour eviter les conflits :

- PostgreSQL : **5433** (pas 5432)
- Redis : **6380** (pas 6379)
- Grafana : **3003** (pas 3000)

## Production

En production, assurez-vous de :

1. **Changer tous les mots de passe** (`DATABASE_URL`, `SECRET_KEY`, `REDIS_URL`)
2. **Desactiver le debug** (`DEBUG=false`, `APP_ENV=production`)
3. **Configurer CORS** avec vos domaines specifiques
4. **Utiliser HTTPS** via un reverse proxy (Caddy recommande)
5. **Configurer les rate limits** selon votre usage
