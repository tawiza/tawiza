# Guide de démarrage rapide avec Docker Compose

Ce guide vous permet de lancer Tawiza en local avec Docker Compose en quelques minutes.

---

## Prérequis

| Composant | Version minimale |
|-----------|-----------------|
| Docker | >= 24.0 |
| Docker Compose | >= 2.20 |
| RAM | 4 Go minimum (8 Go recommandé avec Ollama) |
| Disque | 5 Go minimum (20 Go recommandé avec modèles LLM) |

Vérifiez vos versions :

```bash
docker --version
docker compose version
```

---

## Démarrage rapide

### 1. Cloner le dépôt

```bash
git clone https://github.com/tawiza/tawiza.git
cd tawiza
```

### 2. Configurer les variables d'environnement

```bash
cp docker/.env.example .env
```

Éditez `.env` pour personnaliser les mots de passe :

```bash
# Obligatoire : changez les mots de passe par défaut
POSTGRES_PASSWORD=votre_mot_de_passe_securise

# Optionnel : clés API pour les LLM cloud
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
```

### 3. Lancer les services

```bash
# Tous les services (PostgreSQL, Redis, Prometheus, Grafana)
docker compose up -d

# Ou seulement les services essentiels
docker compose up -d postgres redis
```

---

## Vérification des services

### URLs des services

| Service | URL | Identifiants par défaut |
|---------|-----|------------------------|
| PostgreSQL | `localhost:5432` | `tawiza` / (voir `.env`) |
| Redis | `localhost:6379` | mot de passe dans `.env` |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3003 | `admin` / `admin` |

### Health checks

Vérifiez que tous les conteneurs sont sains :

```bash
# État de tous les conteneurs
docker compose ps

# Vérifier les health checks
docker inspect --format='{{.State.Health.Status}}' tawiza-postgres
docker inspect --format='{{.State.Health.Status}}' tawiza-redis
```

Résultat attendu : `healthy` pour chaque service.

### Tester la connexion à la base de données

```bash
docker exec tawiza-postgres pg_isready -U tawiza -h 127.0.0.1
```

---

## Configuration GPU pour Ollama

Tawiza peut utiliser Ollama pour exécuter des LLM en local avec accélération GPU.

### AMD (ROCm)

Le fichier `docker/docker-compose.ollama-gpu.yml` est préconfiguré pour les GPU AMD :

```bash
# Lancer Ollama avec support GPU AMD
docker compose -f docker/docker-compose.ollama-gpu.yml up -d

# Télécharger un modèle
docker exec tawiza-ollama ollama pull qwen2.5:7b
docker exec tawiza-ollama ollama pull nomic-embed-text

# Vérifier que le GPU est détecté
docker exec tawiza-ollama ollama list
curl http://localhost:11434/api/tags
```

**Prérequis AMD** :
- Driver AMD avec support ROCm installé sur l'hôte
- Périphériques `/dev/kfd` et `/dev/dri` accessibles
- L'utilisateur doit être dans les groupes `video` et `render`

### NVIDIA (CUDA)

Pour les GPU NVIDIA, créez un fichier `docker-compose.ollama-nvidia.yml` :

```yaml
services:
  ollama:
    image: ollama/ollama
    container_name: tawiza-ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - OLLAMA_GPU_LAYERS=-1
      - OLLAMA_PARALLEL=4
      - OLLAMA_KEEP_ALIVE=24h
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    restart: unless-stopped

volumes:
  ollama_data:
```

```bash
# Lancer avec GPU NVIDIA
docker compose -f docker-compose.ollama-nvidia.yml up -d
```

**Prérequis NVIDIA** :
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) installé
- Driver NVIDIA >= 525.60.13

### Combiner avec les services principaux

Pour lancer tous les services ensemble (base de données + Ollama GPU) :

```bash
# AMD
docker compose -f docker-compose.yml -f docker/docker-compose.ollama-gpu.yml up -d

# NVIDIA
docker compose -f docker-compose.yml -f docker-compose.ollama-nvidia.yml up -d
```

---

## Dépannage

### Conflit de ports

**Symptôme** : `Bind for 0.0.0.0:5432 failed: port is already allocated`

```bash
# Identifier le processus utilisant le port
sudo lsof -i :5432

# Solution 1 : arrêter le service local
sudo systemctl stop postgresql

# Solution 2 : changer le port dans docker-compose.yml
# Remplacer "5432:5432" par "5433:5432"
```

Ports utilisés par défaut : **5432** (PostgreSQL), **6379** (Redis), **9090** (Prometheus), **3003** (Grafana), **11434** (Ollama).

### GPU non détecté

**AMD — ROCm** :
```bash
# Vérifier que les périphériques existent
ls -la /dev/kfd /dev/dri/render*

# Vérifier les groupes
id | grep -E 'video|render'

# Tester ROCm dans le conteneur
docker exec tawiza-ollama rocm-smi
```

**NVIDIA — CUDA** :
```bash
# Vérifier le Container Toolkit
nvidia-ctk --version

# Tester l'accès GPU dans Docker
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### Connexion à la base de données refusée

```bash
# Vérifier que PostgreSQL est prêt
docker compose logs postgres

# Vérifier le health check
docker inspect --format='{{json .State.Health}}' tawiza-postgres | python3 -m json.tool

# Se connecter manuellement
docker exec -it tawiza-postgres psql -U tawiza -d tawiza
```

### Conteneurs qui redémarrent en boucle

```bash
# Voir les logs du conteneur problématique
docker compose logs --tail=50 <service>

# Vérifier les ressources disponibles
docker stats --no-stream
```

---

## Commandes courantes

### Logs

```bash
# Tous les logs
docker compose logs -f

# Logs d'un service spécifique
docker compose logs -f postgres

# Dernières 100 lignes
docker compose logs --tail=100 redis
```

### Redémarrage

```bash
# Redémarrer un service
docker compose restart postgres

# Redémarrer tous les services
docker compose restart

# Recréer les conteneurs (après modification du docker-compose.yml)
docker compose up -d --force-recreate
```

### Nettoyage

```bash
# Arrêter tous les services
docker compose down

# Arrêter et supprimer les volumes (⚠️ perte de données)
docker compose down -v

# Supprimer les images inutilisées
docker image prune -f

# Nettoyage complet Docker
docker system prune -af --volumes
```

### Sauvegarde et restauration

```bash
# Sauvegarder la base PostgreSQL
docker exec tawiza-postgres pg_dump -U tawiza tawiza > backup.sql

# Restaurer depuis une sauvegarde
cat backup.sql | docker exec -i tawiza-postgres psql -U tawiza tawiza
```

---

## Étapes suivantes

- [Configuration détaillée](configuration.md) — toutes les variables d'environnement
- [Architecture](architecture.md) — structure du projet
- [Self-Hosting](self-hosting.md) — guide de déploiement en production
