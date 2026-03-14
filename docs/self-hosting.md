# Guide de Self-Hosting

Déployer Tawiza sur votre propre serveur.

## Prérequis serveur

- **OS** : Ubuntu 22.04+ / Debian 12+ recommandé
- **RAM** : 4 GB minimum (8 GB+ avec LLM local)
- **CPU** : 2 cores minimum
- **Disque** : 20 GB minimum
- **GPU** : Optionnel (AMD ROCm ou NVIDIA CUDA pour LLM local)

## Déploiement avec Docker Compose

### 1. Préparation

```bash
# Installer Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Cloner Tawiza
git clone https://github.com/tawiza/tawiza.git
cd tawiza

# Configurer
cp .env.example .env
```

### 2. Configuration production

Éditez `.env` :

```bash
APP_ENV=production
DEBUG=false

# IMPORTANT : générez des vrais secrets
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
DATABASE_URL=postgresql+asyncpg://tawiza:VOTRE_MOT_DE_PASSE@db:5432/tawiza

# Vos domaines
CORS_ORIGINS=https://votre-domaine.fr
```

### 3. Lancement

```bash
docker compose -f docker-compose.yml up -d

# Vérifier
docker compose ps
docker compose logs -f --tail=50
```

### 4. Reverse proxy

Nous recommandons **Caddy** pour sa simplicité (HTTPS automatique) :

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

# Modèle léger (CPU)
ollama pull qwen2.5:7b

# Modèle performant (GPU recommandé)
ollama pull qwen2.5:32b

# Embeddings
ollama pull nomic-embed-text
```

### GPU AMD (ROCm)

```bash
# Vérifier la détection GPU
rocm-smi

# Ollama détecte automatiquement ROCm
ollama run qwen2.5:7b "test"
```

### GPU NVIDIA (CUDA)

```bash
# Installer NVIDIA Container Toolkit
# Ollama détecte automatiquement CUDA
ollama run qwen2.5:7b "test"
```

## Mise à jour

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
# Base de données
docker compose exec db pg_dump -U tawiza tawiza > backup_$(date +%Y%m%d).sql

# Restauration
cat backup_20260309.sql | docker compose exec -T db psql -U tawiza tawiza
```

## Monitoring

Tawiza expose des métriques Prometheus sur `/metrics` :

```bash
# Vérifier les métriques
curl http://localhost:8000/metrics
```

Intégrez avec votre stack de monitoring (Grafana, Datadog, etc.).

## Sécurité en production

- [ ] Mots de passe par défaut changés
- [ ] HTTPS configuré (Caddy/nginx + certificat)
- [ ] Firewall activé (UFW recommandé)
- [ ] Rate limiting configuré
- [ ] CORS restreint à vos domaines
- [ ] Sauvegardes automatisées
- [ ] Mises à jour régulières
