# Health & Probes

Tawiza expose deux endpoints destinés à la supervision et à l'orchestration.

## Endpoints

### `GET /health`

Endpoint de healthcheck principal, utilisé par Docker et les orchestrateurs.

| Propriété | Valeur |
|-----------|--------|
| Méthode | `GET` |
| Chemin | `/health` |
| Rate limit | 60 req/min |
| Code HTTP | `200 OK` |

**Corps de réponse :**

```json
{"status": "healthy"}
```

### `GET /metrics`

Endpoint Prometheus exposant les métriques internes (registry par défaut).

| Propriété | Valeur |
|-----------|--------|
| Méthode | `GET` |
| Chemin | `/metrics` |
| Rate limit | Aucun |
| Format | Prometheus text format (`text/plain; version=0.0.4`) |

> **Sécurité** : cet endpoint n'est pas authentifié. En production, bloquez-le au niveau du reverse proxy ou du pare-feu pour qu'il ne soit pas accessible depuis l'internet public.

---

## Configuration Docker

Le `Dockerfile` racine inclut déjà une instruction `HEALTHCHECK` prête à l'emploi :

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

Aucune configuration supplémentaire n'est nécessaire pour Docker ou Docker Compose.

---

## Configuration Kubernetes

### livenessProbe

Redémarre le conteneur si l'application est bloquée.

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 3
```

### readinessProbe

Retire le pod du load balancer tant que l'application n'est pas prête.

```yaml
readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 15
  timeoutSeconds: 5
  failureThreshold: 3
```

> Les valeurs ci-dessus sont alignées sur les paramètres du `HEALTHCHECK` Docker.

---

## Configuration reverse proxy

### Nginx

```nginx
upstream tawiza {
    server 127.0.0.1:8000;
}

server {
    location / {
        proxy_pass http://tawiza;
    }
}
```

Nginx surveille le backend via les connexions TCP. Les healthchecks HTTP actifs (polling du backend avec retrait automatique en cas d'échec) nécessitent le module `ngx_http_upstream_hc_module`, disponible uniquement dans **Nginx Plus**.

### Traefik

```yaml
# docker-compose.yml (labels)
services:
  tawiza:
    labels:
      - "traefik.enable=true"
      - "traefik.http.services.tawiza.loadbalancer.server.port=8000"
      - "traefik.http.services.tawiza.loadbalancer.healthcheck.path=/health"
      - "traefik.http.services.tawiza.loadbalancer.healthcheck.interval=30s"
      - "traefik.http.services.tawiza.loadbalancer.healthcheck.timeout=10s"
```

### Caddy

```caddyfile
tawiza.example.com {
    reverse_proxy localhost:8000 {
        health_uri      /health
        health_interval 30s
        health_timeout  10s
        health_status   200
    }
}
```

---

## Métriques Prometheus

Si vous utilisez Prometheus, ajoutez un job de scraping pointant vers `/metrics` :

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'tawiza'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: /metrics
    scrape_interval: 30s
```

> Assurez-vous que `/metrics` est accessible depuis votre instance Prometheus mais pas depuis l'internet public (voir note de sécurité ci-dessus).
