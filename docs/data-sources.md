# Catalogue des Sources de Donnees

Tawiza integre 15+ sources de donnees publiques francaises et internationales.

## Sources gouvernementales francaises

| Source | Description | API | Auth | Limites |
|--------|-------------|-----|------|---------|
| **SIRENE** | Repertoire des entreprises francaises | api.gouv.fr/entreprises | Non | 200 req/min |
| **BODACC** | Annonces legales (creations, modifications, radiations) | OpenDataSoft | Non | Illimite |
| **BOAMP** | Marches publics | OpenDataSoft | Non | Illimite |
| **INSEE Local** | Statistiques regionales et departementales | api.insee.fr | Oui (gratuit) | 30 req/min |
| **France Travail** | Offres d'emploi par territoire | api.francetravail.io | Oui (OAuth2) | 1000 req/j |
| **DVF** | Transactions immobilieres (Demandes de Valeurs Foncieres) | data.gouv.fr | Non | Illimite |
| **BAN** | Base Adresse Nationale (geocodage) | api-adresse.data.gouv.fr | Non | Raisonnable |
| **RNA** | Repertoire National des Associations | api.gouv.fr | Non | 200 req/min |
| **Subventions** | Aides et subventions territoriales | aides-territoires.beta.gouv.fr | Non | Raisonnable |

## Sources internationales

| Source | Description | API | Auth | Limites |
|--------|-------------|-----|------|---------|
| **GDELT** | Evenements mondiaux en temps reel | gdeltproject.org | Non | Raisonnable |
| **CommonCrawl** | Archive du web | commoncrawl.org | Non | Gros volumes |
| **DBNomics** | Donnees economiques mondiales | db.nomics.world | Non | Illimite |
| **PyTrends** | Tendances Google | Via scraping | Non | Rate limited |
| **Wikipedia** | Pageviews et contenu | wikimedia.org | Non | Raisonnable |

## Sources enrichies

| Source | Description | Methode |
|--------|-------------|---------|
| **RSS Enhanced** | Flux RSS avec extraction intelligente | Parsers custom |
| **Web Intelligence** | Crawling adaptatif de sources configurables | Crawl4AI |

## Configuration des APIs authentifiees

### INSEE

1. Creer un compte sur [api.insee.fr](https://api.insee.fr)
2. Generer des identifiants d'application
3. Configurer dans `.env` :

```bash
INSEE_CLIENT_ID=votre_client_id
INSEE_CLIENT_SECRET=votre_client_secret
```

### France Travail

1. S'inscrire sur [francetravail.io](https://francetravail.io/data/api)
2. Creer une application (OAuth2)
3. Configurer dans `.env` :

```bash
FRANCE_TRAVAIL_CLIENT_ID=votre_client_id
FRANCE_TRAVAIL_CLIENT_SECRET=votre_client_secret
```

## Ajouter une source de donnees

Tawiza utilise un systeme d'adaptateurs extensible :

```python
# src/infrastructure/datasources/adapters/ma_source.py

from src.infrastructure.datasources.base import DataSourceAdapter

class MaSourceAdapter(DataSourceAdapter):
    name = "ma_source"
    description = "Description de la source"

    async def fetch(self, query: str, **kwargs) -> dict:
        """Recuperer les donnees depuis la source."""
        # Votre implementation ici
        pass

    async def health_check(self) -> bool:
        """Verifier que la source est accessible."""
        pass
```

Voir [CONTRIBUTING.md](../CONTRIBUTING.md) pour le guide complet d'integration.
