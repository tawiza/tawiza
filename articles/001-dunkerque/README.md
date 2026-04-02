# Analyse #4 : Dunkerque, vulnérabilité énergétique

Code reproductible de l'article publié sur [tawiza.fr/analyses/dunkerque-vulnerabilite-energetique.html](https://tawiza.fr/analyses/dunkerque-vulnerabilite-energetique.html).

## Reproduire l'analyse en 5 étapes

### 1. Installer les dépendances

```bash
pip install pandas matplotlib folium geopandas requests pyarrow
```

### 2. Télécharger les données

```bash
python articles/001-dunkerque/scripts/00_download.py
```

Les données sont téléchargées depuis des sources publiques (SIRENE, BODACC, Urssaf, Géorisques, etc.) dans `articles/001-dunkerque/data/raw/`.

### 3. Générer les graphiques

```bash
python articles/001-dunkerque/scripts/regenerate_v2.py
```

Produit 8 graphiques PNG + SVG dans `articles/001-dunkerque/charts/`.

### 4. Générer la carte interactive

```bash
python articles/001-dunkerque/scripts/carte_v3.py
```

Produit une carte Folium (HTML) avec fond satellite, ICPE, gigafactories et friches.

### 5. Adapter à un autre territoire

Modifier la variable `ZONE_EMPLOI_CODE` et la liste `COMMUNES_DK` dans chaque script. Par exemple pour Fos-sur-Mer, Le Havre, ou la vallée de la chimie.

## Structure

```
articles/001-dunkerque/
├── scripts/
│   ├── 00_download.py        # Téléchargement des données
│   ├── regenerate_v2.py      # Graphiques (8 PNG + SVG)
│   └── carte_v3.py           # Carte interactive (Folium)
├── data/raw/                  # Données brutes (généré par 00_download.py)
├── charts/                    # Graphiques (généré par regenerate_v2.py)
└── README.md
```

## Sources de données

| Source | Type | Accès |
|--------|------|-------|
| SIRENE stock géolocalisé | Établissements actifs | data.gouv.fr |
| BODACC procédures collectives | Défaillances | bodacc-datadila.opendatasoft.com |
| Urssaf effectifs salariés | Emploi par secteur × zone d'emploi | open.urssaf.fr |
| Géorisques ICPE | Installations classées | georisques.gouv.fr |
| Grand Port Maritime de Dunkerque | Trafic portuaire | Rapports annuels |
| ARS, Rectorat, ADEME | Données sociales (estimations) | Publications régionales |

## Limites

- Les données sociales (médecins, écoles, associations, DPE) sont des **ordres de grandeur estimés**, pas des données brutes.
- Les scénarios sont des **estimations qualitatives**, pas des prédictions économétriques.
- L'emploi énergivore a **remonté depuis 2021** et dépasse le niveau de 2019. L'article le mentionne.
- Le proxy sous-traitance (NAF 25, 28, 33) surestime probablement l'exposition réelle.

## Contribuer

Trois niveaux :

- **Témoin** : vous vivez ou travaillez à Dunkerque ? Dites-nous si ce portrait correspond à votre réalité.
- **Reproducteur** : changez `ZONE_EMPLOI_CODE`, relancez les scripts, publiez votre analyse.
- **Technique** : améliorez les scripts, ajoutez des sources, corrigez des bugs.

## Licence

Code : MIT. Article : CC BY-SA 4.0. Données : licences respectives de chaque source.
