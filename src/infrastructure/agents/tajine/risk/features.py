"""
Feature extraction for enterprise risk scoring.

Collects features from:
- BODACC API (privileges, procedures collectives)
- SIRENE API (effectifs, age, sector, changes)
- Derived calculations (ratios, sector/region risk)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import httpx
from loguru import logger


@dataclass
class BODACCSignals:
    """Signals extracted from BODACC."""

    nb_privileges_12m: int = 0
    nb_privileges_24m: int = 0
    montant_privileges: float = 0.0
    nb_jugements_12m: int = 0
    has_procedure_collective: bool = False
    has_plan_sauvegarde: bool = False
    has_redressement: bool = False
    has_liquidation: bool = False
    derniere_publication: datetime | None = None


@dataclass
class SIRENESignals:
    """Signals extracted from SIRENE."""

    siren: str = ""
    denomination: str = ""
    date_creation: datetime | None = None
    age_years: float = 0.0
    effectif_actuel: int = 0
    effectif_tranche: str = ""
    forme_juridique: str = ""
    code_naf: str = ""
    libelle_naf: str = ""
    departement: str = ""
    commune: str = ""
    is_active: bool = True
    nb_etablissements: int = 1


@dataclass
class EnterpriseFeatures:
    """Complete feature set for risk scoring."""

    siren: str
    denomination: str

    # BODACC features
    bodacc: BODACCSignals = field(default_factory=BODACCSignals)

    # SIRENE features
    sirene: SIRENESignals = field(default_factory=SIRENESignals)

    # Derived features
    ratio_age_privileges: float = 0.0
    secteur_risque_national: float = 0.0
    region_risque: float = 0.0

    # Metadata
    extracted_at: datetime = field(default_factory=datetime.now)
    data_quality: float = 1.0  # 0-1, reduced if data missing

    def to_model_input(self) -> dict[str, Any]:
        """Convert to dict for XGBoost prediction."""
        return {
            # BODACC features
            "nb_privileges_12m": self.bodacc.nb_privileges_12m,
            "nb_privileges_24m": self.bodacc.nb_privileges_24m,
            "montant_privileges": self.bodacc.montant_privileges,
            "nb_jugements_12m": self.bodacc.nb_jugements_12m,
            "has_procedure_collective": int(self.bodacc.has_procedure_collective),
            "has_plan_sauvegarde": int(self.bodacc.has_plan_sauvegarde),

            # SIRENE features
            "age_years": self.sirene.age_years,
            "effectif_actuel": self.sirene.effectif_actuel,
            "nb_etablissements": self.sirene.nb_etablissements,
            "is_active": int(self.sirene.is_active),

            # Categorical (will be one-hot encoded)
            "forme_juridique": self.sirene.forme_juridique,
            "code_naf_2": self.sirene.code_naf[:2] if self.sirene.code_naf else "00",
            "departement": self.sirene.departement,

            # Derived
            "ratio_age_privileges": self.ratio_age_privileges,
            "secteur_risque_national": self.secteur_risque_national,
            "region_risque": self.region_risque,
        }


# Sector risk rates (national averages from historical BODACC data)
# These are placeholder values - will be updated with real data
SECTOR_RISK_RATES = {
    "55": 0.08,  # Hébergement
    "56": 0.09,  # Restauration
    "41": 0.07,  # Construction bâtiments
    "43": 0.06,  # Travaux construction spécialisés
    "47": 0.05,  # Commerce détail
    "46": 0.04,  # Commerce gros
    "62": 0.02,  # Programmation informatique
    "70": 0.03,  # Conseil gestion
    "default": 0.04,
}

# Regional risk rates (département level)
REGION_RISK_RATES = {
    "93": 0.06,  # Seine-Saint-Denis
    "95": 0.05,  # Val d'Oise
    "13": 0.05,  # Bouches-du-Rhône
    "75": 0.04,  # Paris
    "69": 0.04,  # Rhône
    "default": 0.04,
}


class FeatureExtractor:
    """Extracts features from BODACC and SIRENE APIs."""

    SIRENE_API = "https://recherche-entreprises.api.gouv.fr/search"
    BODACC_API = "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records"

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def extract(self, siren: str) -> EnterpriseFeatures:
        """Extract all features for a SIREN."""
        logger.info(f"Extracting features for SIREN {siren}")

        # Validate SIREN format
        siren = siren.replace(" ", "").strip()
        if len(siren) != 9 or not siren.isdigit():
            raise ValueError(f"Invalid SIREN format: {siren}")

        # Fetch data in parallel
        import asyncio
        sirene_task = self.fetch_sirene(siren)
        bodacc_task = self.fetch_bodacc(siren)

        sirene_signals, bodacc_signals = await asyncio.gather(
            sirene_task, bodacc_task, return_exceptions=True
        )

        # Handle errors gracefully
        if isinstance(sirene_signals, Exception):
            logger.warning(f"SIRENE fetch failed: {sirene_signals}")
            sirene_signals = SIRENESignals(siren=siren)

        if isinstance(bodacc_signals, Exception):
            logger.warning(f"BODACC fetch failed: {bodacc_signals}")
            bodacc_signals = BODACCSignals()

        # Calculate derived features
        ratio_age_privileges = self._calc_ratio_age_privileges(
            bodacc_signals.nb_privileges_24m,
            sirene_signals.age_years
        )

        secteur_risque = SECTOR_RISK_RATES.get(
            sirene_signals.code_naf[:2] if sirene_signals.code_naf else "default",
            SECTOR_RISK_RATES["default"]
        )

        region_risque = REGION_RISK_RATES.get(
            sirene_signals.departement,
            REGION_RISK_RATES["default"]
        )

        # Assess data quality
        data_quality = self._assess_data_quality(sirene_signals, bodacc_signals)

        return EnterpriseFeatures(
            siren=siren,
            denomination=sirene_signals.denomination,
            bodacc=bodacc_signals,
            sirene=sirene_signals,
            ratio_age_privileges=ratio_age_privileges,
            secteur_risque_national=secteur_risque,
            region_risque=region_risque,
            data_quality=data_quality,
        )

    async def fetch_sirene(self, siren: str) -> SIRENESignals:
        """Fetch enterprise data from SIRENE API."""
        try:
            response = await self.client.get(
                self.SIRENE_API,
                params={"q": siren, "per_page": 1}
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("results"):
                logger.warning(f"No SIRENE results for {siren}")
                return SIRENESignals(siren=siren)

            result = data["results"][0]

            # Parse creation date
            date_creation = None
            age_years = 0.0
            if result.get("date_creation"):
                try:
                    date_creation = datetime.fromisoformat(
                        result["date_creation"].replace("Z", "+00:00")
                    )
                    age_years = (datetime.now() - date_creation.replace(tzinfo=None)).days / 365.25
                except (ValueError, TypeError):
                    pass

            # Parse effectif
            effectif = 0
            tranche = result.get("tranche_effectif_salarie", "")
            if tranche:
                # Map tranche codes to approximate values
                tranche_map = {
                    "00": 0, "01": 1, "02": 3, "03": 6,
                    "11": 15, "12": 30, "21": 75, "22": 150,
                    "31": 300, "32": 500, "41": 1500, "42": 3500,
                    "51": 7500, "52": 10000,
                }
                effectif = tranche_map.get(tranche, 0)

            # Get siege info
            siege = result.get("siege", {})

            return SIRENESignals(
                siren=siren,
                denomination=result.get("nom_complet", ""),
                date_creation=date_creation,
                age_years=age_years,
                effectif_actuel=effectif,
                effectif_tranche=tranche,
                forme_juridique=result.get("nature_juridique", ""),
                code_naf=result.get("activite_principale", ""),
                libelle_naf=result.get("libelle_activite_principale", ""),
                departement=siege.get("departement", ""),
                commune=siege.get("libelle_commune", ""),
                is_active=result.get("etat_administratif") == "A",
                nb_etablissements=result.get("nombre_etablissements", 1),
            )

        except httpx.HTTPError as e:
            logger.error(f"SIRENE API error: {e}")
            raise

    async def fetch_bodacc(self, siren: str) -> BODACCSignals:
        """Fetch BODACC announcements for a SIREN."""
        try:
            # Fetch last 24 months of announcements
            date_limit = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

            response = await self.client.get(
                self.BODACC_API,
                params={
                    "where": f'registre LIKE "{siren}%" AND dateparution >= "{date_limit}"',
                    "limit": 100,
                    "order_by": "dateparution DESC",
                }
            )
            response.raise_for_status()
            data = response.json()

            signals = BODACCSignals()
            results = data.get("results", [])

            if not results:
                return signals

            # Parse announcements
            date_12m_ago = datetime.now() - timedelta(days=365)

            for record in results:
                pub_date_str = record.get("dateparution", "")
                try:
                    pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                # Update derniere_publication
                if signals.derniere_publication is None:
                    signals.derniere_publication = pub_date

                famille = record.get("familleavis", "").lower()
                nature = record.get("nature", "").lower()

                # Count privileges
                if "privilège" in nature or "nantissement" in nature:
                    signals.nb_privileges_24m += 1
                    if pub_date >= date_12m_ago:
                        signals.nb_privileges_12m += 1

                # Check for procedures collectives
                if "procédure collective" in famille or "collective" in nature:
                    signals.has_procedure_collective = True

                    if "sauvegarde" in nature:
                        signals.has_plan_sauvegarde = True
                    elif "redressement" in nature:
                        signals.has_redressement = True
                    elif "liquidation" in nature:
                        signals.has_liquidation = True

                # Count jugements
                if "jugement" in nature and pub_date >= date_12m_ago:
                    signals.nb_jugements_12m += 1

            return signals

        except httpx.HTTPError as e:
            logger.error(f"BODACC API error: {e}")
            raise

    def _calc_ratio_age_privileges(
        self, nb_privileges: int, age_years: float
    ) -> float:
        """Calculate privilege/age ratio (higher = worse)."""
        if age_years <= 0:
            return nb_privileges * 2.0  # Young company with privileges = very bad
        return nb_privileges / age_years

    def _assess_data_quality(
        self, sirene: SIRENESignals, bodacc: BODACCSignals
    ) -> float:
        """Assess completeness of extracted data (0-1)."""
        quality = 1.0

        if not sirene.denomination:
            quality -= 0.2
        if sirene.age_years == 0:
            quality -= 0.1
        if not sirene.code_naf:
            quality -= 0.1
        if not sirene.departement:
            quality -= 0.1

        return max(0.0, quality)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
