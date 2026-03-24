# Module Décisions

Module de gestion des décisions stratégiques et des parties prenantes (stakeholders) pour l'intelligence territoriale. Permet de structurer les décisions, d'identifier les acteurs impliqués et de modéliser leurs relations.

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  API Decisions                    │
│            /api/v1/decisions/                     │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────┐ │
│  │  Stakeholders │  │  Decisions   │  │ RACI   │ │
│  │  (acteurs)    │  │  (décisions) │  │ Matrix │ │
│  └──────┬───────┘  └──────┬───────┘  └────┬───┘ │
│         │                 │               │      │
│  ┌──────▼─────────────────▼───────────────▼────┐ │
│  │           PostgreSQL (models)                │ │
│  │  StakeholderDB · DecisionDB · RelationDB    │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

## Modèle de données

### Stakeholders (parties prenantes)

| Champ | Type | Description |
|-------|------|-------------|
| `name` | string | Nom de l'acteur |
| `role` | string | Fonction |
| `organization` | string | Organisation |
| `type` | enum | `institution`, `enterprise`, `association`, `person` |
| `domains` | list[str] | Domaines de compétence |
| `territory_dept` | string | Département de rattachement |
| `territory_scope` | enum | `commune`, `departement`, `region`, `national` |
| `influence_level` | int (1-5) | Niveau d'influence |
| `tags` | list[str] | Tags libres |

### Décisions

| Champ | Type | Description |
|-------|------|-------------|
| `title` | string | Titre de la décision |
| `description` | string | Description détaillée |
| `status` | enum | `draft`, `proposed`, `approved`, `rejected`, `implemented` |
| `priority` | enum | `low`, `medium`, `high`, `critical` |
| `territory_dept` | string | Département concerné |
| `stakeholders` | list | Acteurs impliqués avec rôle RACI |

### Matrice RACI

Chaque stakeholder lié à une décision a un rôle :

| Rôle | Code | Description |
|------|------|-------------|
| **Responsible** | `R` | Réalise l'action |
| **Accountable** | `A` | Approuve et rend des comptes |
| **Consulted** | `C` | Consulté pour avis |
| **Informed** | `I` | Informé du résultat |

### Relations entre stakeholders

| Type | Description |
|------|-------------|
| `hierarchy` | Lien hiérarchique |
| `collaboration` | Collaboration active |
| `funding` | Relation de financement |
| `regulation` | Relation de régulation |
| `competition` | Relation concurrentielle |
| `partnership` | Partenariat |

## API

### Stakeholders

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/v1/decisions/stakeholders` | Liste des acteurs (filtrable par territoire, type) |
| `POST` | `/api/v1/decisions/stakeholders` | Créer un acteur |
| `PUT` | `/api/v1/decisions/stakeholders/{id}` | Modifier un acteur |
| `DELETE` | `/api/v1/decisions/stakeholders/{id}` | Supprimer un acteur |

### Décisions

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/v1/decisions/` | Liste des décisions |
| `POST` | `/api/v1/decisions/` | Créer une décision |
| `PUT` | `/api/v1/decisions/{id}` | Modifier une décision |
| `DELETE` | `/api/v1/decisions/{id}` | Supprimer une décision |

### Relations

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/v1/decisions/stakeholders/{id}/relations` | Graphe de relations d'un acteur |
| `POST` | `/api/v1/decisions/stakeholders/relations` | Créer une relation |

## Fichiers clés

```
src/interfaces/api/v1/decisions/
└── routes.py                          # Endpoints REST complets

src/infrastructure/persistence/models/
└── decision_models.py                 # Modèles SQLAlchemy (DB, enums, relations)
```

## Configuration

Pas de configuration spécifique — le module utilise la base PostgreSQL principale (`DATABASE_URL`).

## État actuel

- Le CRUD complet stakeholders/décisions est opérationnel
- La matrice RACI fonctionne
- Le graphe de relations entre stakeholders est implémenté
- L'interface frontend (onglet Décisions) est en cours de développement
- En cours de validation avec des données réelles de parties prenantes territoriales

## Limitations connues

- Pas encore de calcul automatique de la matrice d'impact (saisie manuelle)
- Le graphe de relations n'a pas de visualisation D3/Force-Graph dans le frontend
- Pas d'intégration avec le Knowledge Graph Neo4j (données séparées dans PostgreSQL)
- L'auto-suggestion de stakeholders à partir des données SIRENE/RNA n'est pas implémentée
