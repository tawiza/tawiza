# API Reference

L'API Tawiza est documentee automatiquement via OpenAPI. Une fois le backend lance, accedez a :
- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

## Endpoints principaux

### Sante

```
GET /health
```

Verifie que l'API est operationnelle.

### Agent TAJINE

```
POST /api/v1/tajine/analyze
```

Lance une analyse complete via l'agent TAJINE.

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

Execute une tache en arriere-plan (async).

---

```
GET /api/v1/tajine/tasks/{task_id}
```

Recupere le statut et les resultats d'une tache.

---

```
GET /api/v1/tajine/tasks/{task_id}/stream
```

Stream les resultats en temps reel (Server-Sent Events).

### Analyse territoriale

```
POST /api/v1/tajine/territorial/analyze
```

Analyse un territoire sur 6 axes : infrastructure, capital humain, innovation, export, investissement, durabilite.

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

Historique BODACC par periode.

---

```
GET /api/v1/tajine/analytics/sankey?territory=31
```

Flux de relations inter-entreprises (format Sankey).

---

```
GET /api/v1/tajine/stats
```

Statistiques agregees depuis SIRENE/BODACC.

### WebSocket

```
WS /ws
```

Connexion temps reel pour le chat et les notifications.

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

- **Par IP** : 100 requetes/minute (configurable)
- **Burst** : 20 requetes instantanees
- **Global** : 1000 requetes/minute

Headers de response :
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1709913600
```

## Codes d'erreur

| Code | Description |
|------|-------------|
| 400 | Requete invalide |
| 401 | Non authentifie |
| 403 | Acces refuse |
| 404 | Ressource non trouvee |
| 429 | Rate limit depasse |
| 500 | Erreur interne |

Les erreurs retournent :
```json
{
  "detail": "Description de l'erreur",
  "request_id": "uuid"
}
```
