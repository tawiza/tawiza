# Télémétrie  -  Tawiza

## Philosophie

Tawiza collecte des données de télémétrie **anonymes** et **opt-out** pour comprendre comment la plateforme est utilisée et améliorer le produit. Aucune donnée personnelle n'est collectée.

## Ce qui est collecté

| Événement | Données | Exemple |
|-----------|---------|---------|
| `app:startup` | Version Tawiza, version Python, OS, architecture, type de DB, provider LLM | `{"tawiza_version": "0.1.0", "os": "Linux", "db_type": "postgresql"}` |
| `feature:{name}` | Nom de la fonctionnalité utilisée | `feature:tajine_analysis` |
| `agent:execution` | Nom de l'agent, niveau cognitif, durée (ms) | `{"agent": "tajine", "level": "causal", "duration_ms": 4200}` |
| `datasource:call` | Source interrogée, succès/échec, durée (ms) | `{"source": "sirene", "success": true, "duration_ms": 320}` |

### Ce qui n'est PAS collecté

- Aucune adresse IP, email, nom, ou identifiant personnel
- Aucune requête utilisateur, contenu de chat, ou donnée d'analyse
- Aucune donnée d'entreprise ou territoriale
- Aucun token, clé API, ou credential

### Identification

Un identifiant anonyme (hash SHA-256 aléatoire, 16 caractères) est généré au premier lancement et stocké dans `~/.tawiza/.telemetry_id`. Cet identifiant ne contient aucune information personnelle et sert uniquement à distinguer les installations pour les métriques d'usage.

## Désactiver la télémétrie

```bash
# Dans .env (backend)
TELEMETRY_ENABLED=false

# Dans .env.local (frontend)
NEXT_PUBLIC_TELEMETRY_ENABLED=false
```

C'est tout. Quand la télémétrie est désactivée :
- Aucun événement n'est envoyé
- Aucune connexion réseau n'est établie vers le service de télémétrie
- Le code de télémétrie est court-circuité à la première ligne

## Infrastructure

- **Service** : [PostHog](https://posthog.com/) (hébergé en EU  -  `eu.i.posthog.com`)
- **Clé API** : Write-only (ne permet pas de lire les données)
- **Rétention** : 90 jours
- **RGPD** : Données anonymes, aucune donnée personnelle, serveurs EU

## Code source

Le code de télémétrie est entièrement transparent :
- Backend : [`src/core/telemetry.py`](../src/core/telemetry.py)
- Frontend : [`frontend/lib/telemetry.ts`](../frontend/lib/telemetry.ts)

La télémétrie ne doit jamais casser l'application : toutes les erreurs sont silencieusement ignorées (`try/except: pass`).

## Pourquoi ?

En tant que projet open source, nous n'avons pas de métriques d'usage naturelles. La télémétrie anonyme nous aide à :

- Comprendre quelles fonctionnalités sont les plus utilisées
- Détecter les sources de données qui échouent souvent
- Prioriser les efforts de développement
- Mesurer l'adoption de nouvelles versions

Si vous êtes à l'aise avec ça, laissez-la activée  -  ça nous aide à améliorer Tawiza pour tout le monde.
