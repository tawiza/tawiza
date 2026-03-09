# Telemetrie — Tawiza

## Philosophie

Tawiza collecte des donnees de telemetrie **anonymes** et **opt-out** pour comprendre comment la plateforme est utilisee et ameliorer le produit. Aucune donnee personnelle n'est collectee.

## Ce qui est collecte

| Evenement | Donnees | Exemple |
|-----------|---------|---------|
| `app:startup` | Version Tawiza, version Python, OS, architecture, type de DB, provider LLM | `{"tawiza_version": "0.1.0", "os": "Linux", "db_type": "postgresql"}` |
| `feature:{name}` | Nom de la fonctionnalite utilisee | `feature:tajine_analysis` |
| `agent:execution` | Nom de l'agent, niveau cognitif, duree (ms) | `{"agent": "tajine", "level": "causal", "duration_ms": 4200}` |
| `datasource:call` | Source interrogee, succes/echec, duree (ms) | `{"source": "sirene", "success": true, "duration_ms": 320}` |

### Ce qui n'est PAS collecte

- Aucune adresse IP, email, nom, ou identifiant personnel
- Aucune requete utilisateur, contenu de chat, ou donnee d'analyse
- Aucune donnee d'entreprise ou territoriale
- Aucun token, cle API, ou credential

### Identification

Un identifiant anonyme (hash SHA-256 aleatoire, 16 caracteres) est genere au premier lancement et stocke dans `~/.tawiza/.telemetry_id`. Cet identifiant ne contient aucune information personnelle et sert uniquement a distinguer les installations pour les metriques d'usage.

## Desactiver la telemetrie

```bash
# Dans .env (backend)
TELEMETRY_ENABLED=false

# Dans .env.local (frontend)
NEXT_PUBLIC_TELEMETRY_ENABLED=false
```

C'est tout. Quand la telemetrie est desactivee :
- Aucun evenement n'est envoye
- Aucune connexion reseau n'est etablie vers le service de telemetrie
- Le code de telemetrie est court-circuite a la premiere ligne

## Infrastructure

- **Service** : [PostHog](https://posthog.com/) (heberge en EU — `eu.i.posthog.com`)
- **Cle API** : Write-only (ne permet pas de lire les donnees)
- **Retention** : 90 jours
- **RGPD** : Donnees anonymes, aucune donnee personnelle, serveurs EU

## Code source

Le code de telemetrie est entierement transparent :
- Backend : [`src/core/telemetry.py`](../src/core/telemetry.py)
- Frontend : [`frontend/lib/telemetry.ts`](../frontend/lib/telemetry.ts)

La telemetrie ne doit jamais casser l'application : toutes les erreurs sont silencieusement ignorees (`try/except: pass`).

## Pourquoi ?

En tant que projet open source, nous n'avons pas de metriques d'usage naturelles. La telemetrie anonyme nous aide a :

- Comprendre quelles fonctionnalites sont les plus utilisees
- Detecter les sources de donnees qui echouent souvent
- Prioriser les efforts de developpement
- Mesurer l'adoption de nouvelles versions

Si vous etes a l'aise avec ca, laissez-la activee — ca nous aide a ameliorer Tawiza pour tout le monde.
