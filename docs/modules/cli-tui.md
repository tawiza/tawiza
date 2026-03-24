# CLI & TUI

Interface en ligne de commande et interface textuelle pour Tawiza. Le projet maintient deux versions en cours de convergence.

## CLI v2 (Typer)

Interface en ligne de commande construite avec [Typer](https://typer.tiangolo.com/) et [Rich](https://github.com/Textualize/rich) pour un rendu terminal élégant.

### Commandes principales

```bash
tawiza ask "Analyse le secteur tech en Haute-Garonne"   # Analyse rapide
tawiza status                                             # État des services
tawiza sources                                            # Sources de données
tawiza version                                            # Version
tawiza --help                                             # Aide
```

### Namespace Pro

Commandes avancées sous `tawiza pro` :

```bash
tawiza pro agents    # Gestion des agents
tawiza pro models    # Modèles LLM disponibles
tawiza pro config    # Configuration avancée
```

### Architecture

```
src/cli/v2/
├── app.py              # Application Typer principale
├── entrypoint.py       # Point d'entrée
├── commands/
│   ├── simple/         # Commandes utilisateur (ask, status, etc.)
│   ├── pro/            # Commandes avancées
│   └── sources.py      # Gestion des sources de données
├── ui/
│   ├── components.py   # Composants Rich (MessageBox, etc.)
│   └── theme.py        # Thème visuel (header, footer, couleurs)
├── experience/         # ExperienceController (UX unifiée)
├── agents/             # Interaction avec les agents
├── execution/          # Exécution de tâches
├── completions/        # Auto-complétion shell
└── utils/
    ├── completers.py   # Compléteurs (agents, modèles)
    └── suggestions.py  # Suggestions contextuelles
```

### UX

- `ExperienceController` : Gère l'état de l'expérience utilisateur (mode interactif, historique)
- `MessageBox` : Composant Rich pour afficher les messages avec style
- Thème personnalisé avec header/footer colorés
- Auto-complétion pour les noms d'agents et de modèles

## TUI v3 (Textual)

Interface textuelle complète construite avec [Textual](https://textual.textualize.io/), offrant une expérience proche d'une application graphique dans le terminal.

### Écrans

| Écran | Fichier | Description |
|-------|---------|-------------|
| **Dashboard** | `dashboard.py` | Vue d'ensemble avec métriques et carte |
| **Chat** | `chat.py` | Chat interactif avec l'agent TAJINE |
| **Agent Live** | `agent_live.py` | Suivi en temps réel de l'exécution de l'agent |
| **TAJINE** | `tajine.py` | Configuration et contrôle de l'agent |
| **Config** | `config.py` | Paramètres de l'application |
| **Browser** | `browser.py` | Visualisation du navigateur de l'agent |
| **Logs** | `logs.py` | Journaux d'exécution |
| **Metrics** | `metrics.py` | Métriques de performance |
| **History** | `history.py` | Historique des analyses |
| **Files** | `files.py` | Gestionnaire de fichiers |

### Widgets personnalisés

| Widget | Description |
|--------|-------------|
| `france_map.py` | Carte de France interactive (départements) |
| `cognitive_charts.py` | Graphiques des niveaux cognitifs |
| `sparkline.py` | Mini-graphiques inline |
| `metric_gauge.py` | Jauges de métriques |
| `thinking_log.py` | Journal de raisonnement de l'agent |
| `action_timeline.py` | Timeline des actions de l'agent |
| `department_list.py` | Liste des départements avec scores |
| `service_status.py` | État des services (Ollama, DB, etc.) |
| `browser_preview.py` | Aperçu du navigateur de l'agent |
| `command_input.py` | Barre de commande avec auto-complétion |
| `global_sidebar.py` | Sidebar de navigation |
| `plotext_charts.py` | Graphiques Plotext dans le terminal |

### Architecture

```
src/cli/v3/tui/
├── app.py              # Application Textual principale
├── keybindings.py      # Raccourcis clavier
├── screens/            # 11 écrans (voir tableau)
├── widgets/            # 20+ widgets personnalisés
├── controllers/        # Logique métier des écrans
├── services/           # Services (API client, WebSocket)
├── adapters/           # Adaptateurs (Ollama, DB)
├── styles/             # CSS Textual
└── prototypes/         # Prototypes en cours
```

## Fichiers clés

```
src/cli/
├── main.py             # Point d'entrée global
├── entrypoint.py       # Routage CLI v1/v2/v3
├── v2/                 # CLI v2 (Typer + Rich)
│   └── app.py          # Application principale
├── v3/                 # TUI v3 (Textual)
│   └── tui/app.py      # Application principale
├── base/               # Classes de base partagées
├── commands/           # Commandes partagées (v1)
├── services/           # Services partagés
└── helpers/            # Utilitaires
```

## Configuration

Pas de variables d'environnement spécifiques au CLI. Le CLI utilise la configuration standard de Tawiza (`.env`).

## État actuel

- **CLI v2** : Commandes de base fonctionnelles (`ask`, `status`, `sources`). Auto-complétion opérationnelle.
- **TUI v3** : La plupart des écrans sont implémentés. Le Dashboard et le Chat sont les plus avancés. Certains widgets (carte de France, graphiques cognitifs) sont des prototypes.
- **Pas 100% fonctionnel** : Certains écrans ont des bugs d'affichage ou des fonctionnalités manquantes.
- Une fusion des versions v2 et v3 est prévue pour unifier l'expérience.

## Limitations connues

- Le TUI v3 nécessite un terminal moderne (256 couleurs, Unicode)  -  pas compatible avec tous les terminaux
- La carte de France (`france_map.py`) est une approximation ASCII, pas une vraie carte interactive
- Le WebSocket client dans le TUI peut se déconnecter sans reconnexion automatique
- Les graphiques Plotext sont limités en résolution dans le terminal
- Le CLI v2 et le TUI v3 partagent peu de code  -  duplication significative
