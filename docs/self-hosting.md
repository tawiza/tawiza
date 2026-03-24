# Guide de Self-Hosting

Deployer Tawiza sur votre propre serveur.

## Prerequis serveur

- **OS** : Ubuntu 22.04+ / Debian 12+ recommande
- **RAM** : 4 GB minimum (8 GB+ avec LLM local)
- **CPU** : 2 cores minimum
- **Disque** : 20 GB minimum
- **GPU** : Optionnel (AMD ROCm ou NVIDIA CUDA pour LLM local)

## Deploiement avec Docker Compose

### 1. Preparation

```bash
# Installer Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Cloner Tawiza
git clone https://github.com/hamidedefr/tawiza.git
cd tawiza

# Configurer
cp .env.example .env
```

### 2. Configuration production

Editez `.env` :

```bash
APP_ENV=production
DEBUG=false

# IMPORTANT : generez des vrais secrets
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
DATABASE_URL=postgresql+asyncpg://tawiza:VOTRE_MOT_DE_PASSE@db:5432/tawiza

# Vos domaines
CORS_ORIGINS=https://votre-domaine.fr
```

### 3. Lancement

```bash
docker compose -f docker-compose.yml up -d

# Verifier
docker compose ps
docker compose logs -f --tail=50
```

### 4. Reverse proxy

Nous recommandons **Caddy** pour sa simplicite (HTTPS automatique) :

```
# /etc/caddy/Caddyfile
votre-domaine.fr {
    reverse_proxy localhost:3000
}

api.votre-domaine.fr {
    reverse_proxy localhost:8000
}
```

Alternative nginx :

```nginx
server {
    listen 80;
    server_name votre-domaine.fr;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
    }
}

server {
    listen 80;
    server_name api.votre-domaine.fr;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## LLM local (optionnel)

### Avec Ollama

```bash
# Installer Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Modele leger (CPU)
ollama pull qwen2.5:7b

# Modele performant (GPU recommande)
ollama pull qwen2.5:32b

# Embeddings
ollama pull nomic-embed-text
```

### GPU AMD (ROCm)

```bash
# Verifier la detection GPU
rocm-smi

# Ollama detecte automatiquement ROCm
ollama run qwen2.5:7b "test"
```

### GPU NVIDIA (CUDA)

```bash
# Installer NVIDIA Container Toolkit
# Ollama detecte automatiquement CUDA
ollama run qwen2.5:7b "test"
```

## Mise a jour

```bash
cd tawiza
git pull origin main
docker compose down
docker compose build
docker compose up -d

# Migrations DB
docker compose exec backend alembic upgrade head
```

## Sauvegardes

```bash
# Base de donnees
docker compose exec db pg_dump -U tawiza tawiza > backup_$(date +%Y%m%d).sql

# Restauration
cat backup_20260309.sql | docker compose exec -T db psql -U tawiza tawiza
```

## Monitoring

Tawiza expose des metriques Prometheus sur `/metrics` :

```bash
# Verifier les metriques
curl http://localhost:8000/metrics
```

Integrez avec votre stack de monitoring (Grafana, Datadog, etc.).

## Securite en production

- [ ] Mots de passe par defaut changes
- [ ] HTTPS configure (Caddy/nginx + certificat)
- [ ] Firewall active (UFW recommande)
- [ ] Rate limiting configure
- [ ] CORS restreint a vos domaines
- [ ] Sauvegardes automatisees
- [ ] Mises a jour regulieres
