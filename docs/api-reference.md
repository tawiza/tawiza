# API Reference

L'API Tawiza est documentée automatiquement via OpenAPI. Une fois le backend lancé, accédez à :
- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

## Endpoints principaux

### Santé

```
GET /health
```

Vérifie que l'API est opérationnelle.

### Agent TAJINE

```
POST /api/v1/tajine/analyze
```

Lance une analyse complète via l'agent TAJINE.

**Body :**
```json
{
  "query": "Quel est le potentiel innovation en Haute-Garonne ?",
  "territory_code": "31",
  "sector": "tech",
  "cognitive_level": "causal"
}
```

**Response :**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "cognitive_level": "causal",
  "confidence": 0.92,
  "insights": ["..."],
  "charts": {
    "radar": [...],
    "sankey": {...}
  }
}
```

---

```
POST /api/v1/tajine/execute
```

Exécute une tâche en arrière-plan (async).

---

```
GET /api/v1/tajine/tasks/{task_id}
```

Récupère le statut et les résultats d'une tâche.

---

```
GET /api/v1/tajine/tasks/{task_id}/stream
```

Stream les résultats en temps réel (Server-Sent Events).

### Analyse territoriale

```
POST /api/v1/tajine/territorial/analyze
```

Analyse un territoire sur 6 axes : infrastructure, capital humain, innovation, export, investissement, durabilité.

---

```
POST /api/v1/tajine/territorial/simulate
```

Simulation What-If avec Monte Carlo.

**Body :**
```json
{
  "territory_code": "31",
  "scenario": {
    "tax_change": 0.15,
    "infrastructure_investment": 1000000
  },
  "iterations": 1000
}
```

### Analytics

```
GET /api/v1/tajine/analytics/timeseries?period=6m&territory=31
```

Historique BODACC par période.

---

```
GET /api/v1/tajine/analytics/sankey?territory=31
```

Flux de relations inter-entreprises (format Sankey).

---

```
GET /api/v1/tajine/stats
```

Statistiques agrégées depuis SIRENE/BODACC.

### WebSocket

```
WS /ws
```

Connexion temps réel pour le chat et les notifications.

**Messages entrants :**
```json
{
  "type": "chat",
  "content": "Analyse les entreprises tech de Toulouse",
  "context": {"territory": "31"}
}
```

**Messages sortants :**
```json
{
  "type": "response",
  "content": "...",
  "charts": {...},
  "cognitive_level": "discovery",
  "progress": 0.75
}
```

## Authentification

L'API utilise des JWT tokens :

```bash
# Obtenir un token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "..."}'

# Utiliser le token
curl http://localhost:8000/api/v1/tajine/stats \
  -H "Authorization: Bearer <token>"
```

## Rate Limiting

- **Par IP** : 100 requêtes/minute (configurable)
- **Burst** : 20 requêtes instantanées
- **Global** : 1000 requêtes/minute

Headers de réponse :
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1709913600
```

## Codes d'erreur

| Code | Description |
|------|-------------|
| 400 | Requête invalide |
| 401 | Non authentifié |
| 403 | Accès refusé |
| 404 | Ressource non trouvée |
| 429 | Rate limit dépassé |
| 500 | Erreur interne |

Les erreurs retournent :
```json
{
  "detail": "Description de l'erreur",
  "request_id": "uuid"
}
```
