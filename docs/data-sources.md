# Catalogue des Sources de Données

Tawiza intègre 15+ sources de données publiques françaises et internationales.

## Sources gouvernementales françaises

| Source | Description | API | Auth | Limites |
|--------|-------------|-----|------|---------|
| **SIRENE** | Répertoire des entreprises françaises | api.gouv.fr/entreprises | Non | 200 req/min |
| **BODACC** | Annonces légales (créations, modifications, radiations) | OpenDataSoft | Non | Illimité |
| **BOAMP** | Marchés publics | OpenDataSoft | Non | Illimité |
| **INSEE Local** | Statistiques régionales et départementales | api.insee.fr | Oui (gratuit) | 30 req/min |
| **France Travail** | Offres d'emploi par territoire | api.francetravail.io | Oui (OAuth2) | 1000 req/j |
| **DVF** | Transactions immobilières (Demandes de Valeurs Foncières) | data.gouv.fr | Non | Illimité |
| **BAN** | Base Adresse Nationale (géocodage) | api-adresse.data.gouv.fr | Non | Raisonnable |
| **RNA** | Répertoire National des Associations | api.gouv.fr | Non | 200 req/min |
| **Subventions** | Aides et subventions territoriales | aides-territoires.beta.gouv.fr | Non | Raisonnable |

## Sources internationales

| Source | Description | API | Auth | Limites |
|--------|-------------|-----|------|---------|
| **GDELT** | Événements mondiaux en temps réel | gdeltproject.org | Non | Raisonnable |
| **CommonCrawl** | Archive du web | commoncrawl.org | Non | Gros volumes |
| **DBNomics** | Données économiques mondiales | db.nomics.world | Non | Illimité |
| **PyTrends** | Tendances Google | Via scraping | Non | Rate limited |
| **Wikipedia** | Pageviews et contenu | wikimedia.org | Non | Raisonnable |

## Sources enrichies

| Source | Description | Méthode |
|--------|-------------|---------|
| **RSS Enhanced** | Flux RSS avec extraction intelligente | Parsers custom |
| **Web Intelligence** | Crawling adaptatif de sources configurables | Crawl4AI |

## Configuration des APIs authentifiées

### INSEE

1. Créer un compte sur [api.insee.fr](https://api.insee.fr)
2. Générer des identifiants d'application
3. Configurer dans `.env` :

```bash
INSEE_CLIENT_ID=votre_client_id
INSEE_CLIENT_SECRET=votre_client_secret
```

### France Travail

1. S'inscrire sur [francetravail.io](https://francetravail.io/data/api)
2. Créer une application (OAuth2)
3. Configurer dans `.env` :

```bash
FRANCE_TRAVAIL_CLIENT_ID=votre_client_id
FRANCE_TRAVAIL_CLIENT_SECRET=votre_client_secret
```

## Ajouter une source de données

Tawiza utilise un système d'adaptateurs extensible :

```python
# src/infrastructure/datasources/adapters/ma_source.py

from src.infrastructure.datasources.base import DataSourceAdapter

class MaSourceAdapter(DataSourceAdapter):
    name = "ma_source"
    description = "Description de la source"

    async def fetch(self, query: str, **kwargs) -> dict:
        """Récupérer les données depuis la source."""
        # Votre implémentation ici
        pass

    async def health_check(self) -> bool:
        """Vérifier que la source est accessible."""
        pass
```

Voir [CONTRIBUTING.md](../CONTRIBUTING.md) pour le guide complet d'intégration.
