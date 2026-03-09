# Politique de télémétrie

Tawiza collecte des données d'usage **anonymes** pour nous aider à comprendre comment la plateforme est utilisée et améliorer le projet. Cette page explique exactement ce qui est collecté, ce qui ne l'est pas, et comment désactiver la télémétrie.

## Pourquoi ?

On est une petite équipe et on n'a aucune visibilité sur comment les gens utilisent Tawiza. La télémétrie nous aide à :

- Savoir quelles fonctionnalités sont réellement utilisées (et lesquelles ne le sont pas)
- Identifier les sources de données les plus populaires
- Détecter les problèmes de performance (temps de réponse des agents)
- Prioriser les prochaines fonctionnalités

## Ce qu'on collecte

| Donnée | Exemple | Pourquoi |
|--------|---------|----------|
| Pages visitées | `/dashboard/analytics` | Savoir quelles pages sont utiles |
| Fonctionnalités utilisées | `feature:tajine_analysis` | Prioriser le développement |
| Sources de données appelées | `datasource:call {source: "sirene"}` | Savoir quelles APIs maintenir en priorité |
| Temps de réponse des agents | `agent:execution {duration_ms: 1200}` | Optimiser les performances |
| Version de Tawiza | `2.0.0` | Savoir quelles versions sont en production |
| OS et architecture | `Linux`, `x86_64` | Compatibilité |
| Démarrage de l'application | `app:startup` | Compter les installations actives |

## Ce qu'on ne collecte JAMAIS

- Adresses IP
- Emails, noms, ou toute information personnelle
- Contenu des requêtes utilisateur (les questions posées à TAJINE)
- Données d'entreprises ou territoriales analysées
- Tokens, clés API, ou identifiants
- Cookies ou données de session persistantes

## Où vont les données ?

Les données sont envoyées à [PostHog](https://posthog.com) hébergé dans l'**Union Européenne** (Francfort, Allemagne). PostHog est une plateforme d'analytics open source ([github.com/PostHog/posthog](https://github.com/PostHog/posthog)).

- **Hébergement** : EU (Francfort, `eu.i.posthog.com`)
- **Rétention** : 90 jours
- **Accès** : équipe Tawiza uniquement
- **Revente** : aucune — jamais

## Comment désactiver

Ajoutez dans votre fichier `.env` :

```bash
TELEMETRY_ENABLED=false
```

Et dans `frontend/.env.local` :

```bash
NEXT_PUBLIC_TELEMETRY_ENABLED=false
```

C'est tout. Aucune donnée ne sera envoyée. La clé PostHog présente dans le code est une clé **write-only** — elle ne peut qu'envoyer des événements anonymes, pas lire quoi que ce soit.

## Implémentation

Le code de télémétrie est entièrement open source et auditable :

- **Backend** : [`src/core/telemetry.py`](src/core/telemetry.py)
- **Frontend** : [`frontend/lib/telemetry.ts`](frontend/lib/telemetry.ts)

Principes d'implémentation :

- La télémétrie ne doit **jamais** casser l'application (tous les appels sont dans des `try/catch`)
- Aucun cookie, aucun `localStorage` (persistence en mémoire uniquement côté frontend)
- L'ID anonyme est un hash aléatoire sans lien avec l'utilisateur
- `autocapture` est désactivé (pas de tracking automatique des clics)
- L'enregistrement de session est désactivé
- La capture d'IP est désactivée côté PostHog

## Questions ?

Si vous avez des questions sur la télémétrie, ouvrez une [Discussion GitHub](https://github.com/hamidedefr/tawiza/discussions) ou une [Issue](https://github.com/hamidedefr/tawiza/issues).
