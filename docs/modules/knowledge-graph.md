# Knowledge Graph

Module de graphe de connaissances basé sur Neo4j pour la modélisation des relations entre entités économiques (entreprises, établissements, territoires, dirigeants).

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│            ExtendedKnowledgeGraph                        │
│                                                         │
│  ┌──────────────────┐     ┌──────────────────────────┐  │
│  │  In-Memory Cache │     │      Neo4j Client        │  │
│  │  (lecture rapide) │     │  (persistance + algos)   │  │
│  └────────┬─────────┘     └────────────┬─────────────┘  │
│           │                            │                │
│  ┌────────▼────────────────────────────▼────────────┐   │
│  │              SyncQueue + BatchWriter              │   │
│  │     (écriture asynchrone vers Neo4j)              │   │
│  └───────────────────────────────────────────────────┘   │
│                                                         │
│  ┌───────────────────────────────────────────────────┐   │
│  │              Algorithmes de graphe                 │   │
│  │  Centralité · Communautés · Similarité            │   │
│  └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

L'`ExtendedKnowledgeGraph` hérite d'un KG in-memory (pour les lectures rapides) et synchronise les écritures vers Neo4j de manière asynchrone via une file d'attente.

## Types de noeuds

| Noeud | Label | Clé | Propriétés |
|-------|-------|-----|------------|
| **Entreprise** | `:Company` | `siren` | name, legal_form, naf_code, creation_date, employee_count, capital |
| **Établissement** | `:Establishment` | `siret` | siren, address, postal_code, city, naf_code, is_headquarters |
| **Territoire** | `:Territory` | `code` | name, type (commune, département, région) |
| **Dirigeant** | `:Director` | `id` | name, role, mandate_start, mandate_end |
| **Secteur** | `:Sector` | `naf_code` | name, description |

## Types de relations

| Relation | De | Vers | Propriétés |
|----------|-----|------|------------|
| `HAS_ESTABLISHMENT` | Company | Establishment | — |
| `LOCATED_IN` | Establishment | Territory | — |
| `DIRECTED_BY` | Company | Director | role, since |
| `IN_SECTOR` | Company | Sector | — |
| `SUPPLIES` | Company | Company | contract_type, volume |
| `COMPETES_WITH` | Company | Company | market, overlap_score |
| `PARTNERS_WITH` | Company | Company | partnership_type |

## Algorithmes de graphe

Implémentés via Neo4j Graph Data Science (GDS) :

### Centralité (`algorithms/centrality.py`)

| Algorithme | Description | Usage |
|-----------|-------------|-------|
| **PageRank** | Importance relative des entreprises dans le réseau | Identifier les entreprises centrales d'un territoire |
| **Betweenness** | Intermédiarité — noeuds "ponts" entre communautés | Détecter les entreprises connectrices |

```python
# Exemple : Top 20 entreprises par PageRank en Haute-Garonne
scores = await centrality.pagerank(territory_code="31", top_k=20)
```

### Communautés (`algorithms/communities.py`)

| Algorithme | Description | Usage |
|-----------|-------------|-------|
| **Louvain** | Détection de communautés par modularité | Identifier les clusters d'entreprises liées |

```python
# Exemple : Clusters d'entreprises dans le département 31
communities = await detector.detect(territory_code="31", min_community_size=2)
```

### Similarité (`algorithms/similarity.py`)

| Algorithme | Description | Usage |
|-----------|-------------|-------|
| **Node Similarity** | Similarité basée sur les voisins communs | Trouver des entreprises similaires |

```python
# Exemple : Entreprises similaires à une entreprise donnée
similar = await finder.find_similar(siren="123456789", top_k=10)
```

## Synchronisation avec PostgreSQL

Le module `sync/` gère la synchronisation bidirectionnelle :

- `queue.py` : File d'attente des opérations à synchroniser (`SyncQueue`, `SyncItem`)
- `batch_writer.py` : Écriture par lots vers Neo4j (`BatchWriter`) avec configuration de taille de lot et intervalle
- `cypher_builder.py` : Génération de requêtes Cypher à partir des modèles

Le flux typique :
1. Les données sont écrites dans PostgreSQL (source de vérité)
2. Un `SyncItem` est ajouté à la `SyncQueue`
3. Le `BatchWriter` exécute les écritures vers Neo4j par lots

## Fichiers clés

```
src/infrastructure/knowledge_graph/
├── extended_kg.py              # KG étendu (in-memory + Neo4j)
├── neo4j_client.py             # Client Neo4j async
├── models/
│   └── nodes.py                # Modèles de noeuds (Company, Establishment, etc.)
├── algorithms/
│   ├── centrality.py           # PageRank, Betweenness
│   ├── communities.py          # Louvain
│   └── similarity.py           # Node Similarity
└── sync/
    ├── queue.py                # File d'attente de synchronisation
    ├── batch_writer.py         # Écriture par lots
    └── cypher_builder.py       # Générateur de requêtes Cypher

src/infrastructure/agents/tajine/
├── knowledge/
│   ├── bank.py                 # Banque de connaissances
│   ├── service.py              # Service de connaissances
│   └── territorial_kg.py       # KG territorial spécialisé
└── validation/
    └── knowledge_graph.py      # KG in-memory de base (classe parente)
```

## Configuration

| Variable | Description | Défaut |
|----------|-------------|--------|
| `NEO4J_URI` | URI de connexion Neo4j | `bolt://localhost:7687` |
| `NEO4J_USER` | Utilisateur Neo4j | `neo4j` |
| `NEO4J_PASSWORD` | Mot de passe Neo4j | — |
| `NEO4J_DATABASE` | Nom de la base | `neo4j` |

Neo4j est **optionnel**. Sans Neo4j, le KG fonctionne uniquement en mémoire (pas de persistence ni d'algorithmes GDS).

## État actuel

- Le KG in-memory fonctionne pour les validations et le stockage temporaire
- Le client Neo4j est implémenté avec connection pooling
- Les algorithmes de centralité et communautés sont implémentés
- Le batch writer synchronise les écritures de manière asynchrone
- Neo4j n'est pas déployé en production (fonctionnement in-memory uniquement)

## Limitations connues

- Neo4j n'est pas inclus dans le Docker Compose par défaut (nécessite une installation séparée)
- Les algorithmes GDS nécessitent le plugin Neo4j Graph Data Science (payant pour les grosses instances)
- La synchronisation PostgreSQL → Neo4j est unidirectionnelle
- Le KG in-memory ne persiste pas entre les redémarrages
- Pas de mécanisme de garbage collection pour les noeuds obsolètes
