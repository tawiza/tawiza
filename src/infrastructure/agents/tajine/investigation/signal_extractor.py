"""
Signal Extractor - Collecte des signaux depuis sources publiques.

Collecte parallèle depuis:
- BODACC: Privilèges, procédures collectives
- SIRENE: Infos légales, effectifs, établissements
- INPI: Dirigeants, mandats
- Web: Avis, actualités
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any

from loguru import logger


class SignalCategory(StrEnum):
    """Catégories de signaux d'investigation."""

    FINANCIAL = "financial"
    LEGAL = "legal"
    OPERATIONAL = "operational"
    DIRECTOR = "director"
    WEAK_SIGNAL = "weak_signal"


class SignalImpact(StrEnum):
    """Impact d'un signal sur l'évaluation."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    CRITICAL = "critical"


@dataclass
class Signal:
    """Un signal d'investigation extrait d'une source."""

    category: SignalCategory
    name: str
    value: Any
    source: str
    impact: SignalImpact
    likelihood_ratio: float  # LR si présent
    details: str = ""
    extracted_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "category": self.category.value,
            "name": self.name,
            "value": self.value,
            "source": self.source,
            "impact": self.impact.value,
            "likelihood_ratio": self.likelihood_ratio,
            "details": self.details,
            "extracted_at": self.extracted_at.isoformat(),
        }


# Likelihood Ratios basés sur études statistiques de défaillance
# LR > 1 = augmente le risque, LR < 1 = diminue le risque
SIGNAL_LR_TABLE: dict[str, tuple[float, float]] = {
    # Signal: (LR si présent, LR si absent)
    "privileges_inss_multiples": (8.0, 0.9),
    "procedure_collective_passee": (12.0, 0.95),
    "dirigeant_multi_faillites": (6.0, 0.95),
    "effectif_baisse_30pct": (4.0, 0.8),
    "age_moins_2ans": (2.5, 0.7),
    "transferts_siege_multiples": (3.0, 0.9),
    "avis_google_negatifs": (2.0, 0.9),
    "actualites_negatives": (3.5, 0.85),
    "secteur_risque": (1.5, 0.9),  # Ajusté par secteur
    "capital_faible": (2.0, 0.95),
    "marches_publics_gagnes": (0.5, 1.0),  # Signal positif
    "certifications": (0.6, 1.0),  # Signal positif
}

# Priors par secteur NAF (taux de défaillance moyen)
SECTOR_PRIORS: dict[str, float] = {
    "55": 0.09,  # Hébergement
    "56": 0.09,  # Restauration
    "41": 0.08,  # Construction bâtiments
    "43": 0.08,  # Travaux spécialisés
    "47": 0.06,  # Commerce détail
    "46": 0.05,  # Commerce gros
    "62": 0.04,  # Programmation
    "70": 0.04,  # Conseil
    "86": 0.02,  # Santé
    "default": 0.05,  # Par défaut
}


class SignalExtractor:
    """Extracteur de signaux depuis sources publiques."""

    def __init__(self) -> None:
        """Initialize with lazy-loaded adapters."""
        self._bodacc = None
        self._sirene = None
        self._signals: list[Signal] = []

    async def _get_bodacc(self):
        """Lazy load BODACC adapter."""
        if self._bodacc is None:
            from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter

            self._bodacc = BodaccAdapter()
        return self._bodacc

    async def _get_sirene(self):
        """Lazy load SIRENE adapter."""
        if self._sirene is None:
            from src.infrastructure.datasources.adapters.sirene import SireneAdapter

            self._sirene = SireneAdapter()
        return self._sirene

    async def extract_all(self, siren: str) -> list[Signal]:
        """
        Extract all signals for a given SIREN.

        Args:
            siren: SIREN number (9 digits)

        Returns:
            List of extracted signals
        """
        self._signals = []

        # Parallel extraction from all sources
        tasks = [
            self._extract_sirene_signals(siren),
            self._extract_bodacc_signals(siren),
            self._extract_operational_signals(siren),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Signal extraction failed: {result}")
            elif isinstance(result, list):
                self._signals.extend(result)

        logger.info(f"Extracted {len(self._signals)} signals for SIREN {siren}")
        return self._signals

    async def _extract_sirene_signals(self, siren: str) -> list[Signal]:
        """Extract signals from SIRENE API."""
        signals: list[Signal] = []

        try:
            sirene = await self._get_sirene()
            # Use get_by_id for SIREN lookup (uses q= parameter correctly)
            company = await sirene.get_by_id(siren)
            results = [company] if company else []

            if not results:
                signals.append(
                    Signal(
                        category=SignalCategory.LEGAL,
                        name="entreprise_introuvable",
                        value=True,
                        source="SIRENE",
                        impact=SignalImpact.CRITICAL,
                        likelihood_ratio=10.0,
                        details="SIREN non trouvé dans la base SIRENE",
                    )
                )
                return signals

            company = results[0]

            # Date de création → âge
            date_creation = company.get("date_creation")
            if date_creation:
                from datetime import datetime

                try:
                    created = datetime.fromisoformat(date_creation)
                    age_years = (datetime.now() - created).days / 365

                    if age_years < 2:
                        signals.append(
                            Signal(
                                category=SignalCategory.OPERATIONAL,
                                name="age_moins_2ans",
                                value=round(age_years, 1),
                                source="SIRENE",
                                impact=SignalImpact.NEGATIVE,
                                likelihood_ratio=SIGNAL_LR_TABLE["age_moins_2ans"][0],
                                details=f"Entreprise créée il y a {age_years:.1f} ans",
                            )
                        )
                    else:
                        signals.append(
                            Signal(
                                category=SignalCategory.OPERATIONAL,
                                name="entreprise_etablie",
                                value=round(age_years, 1),
                                source="SIRENE",
                                impact=SignalImpact.POSITIVE,
                                likelihood_ratio=SIGNAL_LR_TABLE["age_moins_2ans"][1],
                                details=f"Entreprise établie depuis {age_years:.1f} ans",
                            )
                        )
                except (ValueError, TypeError):
                    pass

            # Effectifs
            effectif = company.get("tranche_effectif_salarie")
            if effectif:
                signals.append(
                    Signal(
                        category=SignalCategory.OPERATIONAL,
                        name="effectif_salarie",
                        value=effectif,
                        source="SIRENE",
                        impact=SignalImpact.NEUTRAL,
                        likelihood_ratio=1.0,
                        details=f"Tranche effectif: {effectif}",
                    )
                )

            # Secteur d'activité
            naf = company.get("activite_principale", "")
            if naf:
                naf_section = naf[:2] if len(naf) >= 2 else naf
                prior = SECTOR_PRIORS.get(naf_section, SECTOR_PRIORS["default"])

                if prior >= 0.08:
                    signals.append(
                        Signal(
                            category=SignalCategory.OPERATIONAL,
                            name="secteur_risque",
                            value=naf,
                            source="SIRENE",
                            impact=SignalImpact.NEGATIVE,
                            likelihood_ratio=prior / SECTOR_PRIORS["default"],
                            details=f"Secteur NAF {naf} - taux défaillance élevé ({prior * 100:.1f}%)",
                        )
                    )
                else:
                    signals.append(
                        Signal(
                            category=SignalCategory.OPERATIONAL,
                            name="secteur_stable",
                            value=naf,
                            source="SIRENE",
                            impact=SignalImpact.POSITIVE,
                            likelihood_ratio=prior / SECTOR_PRIORS["default"],
                            details=f"Secteur NAF {naf} - taux défaillance modéré ({prior * 100:.1f}%)",
                        )
                    )

            # Nombre d'établissements
            nb_etab = company.get("nombre_etablissements", 1)
            signals.append(
                Signal(
                    category=SignalCategory.OPERATIONAL,
                    name="nombre_etablissements",
                    value=nb_etab,
                    source="SIRENE",
                    impact=SignalImpact.NEUTRAL,
                    likelihood_ratio=1.0,
                    details=f"{nb_etab} établissement(s) actif(s)",
                )
            )

            # Siège social
            siege = company.get("siege", {})
            if siege:
                adresse = siege.get("adresse", "Non renseignée")
                signals.append(
                    Signal(
                        category=SignalCategory.LEGAL,
                        name="siege_social",
                        value=adresse,
                        source="SIRENE",
                        impact=SignalImpact.NEUTRAL,
                        likelihood_ratio=1.0,
                        details=f"Siège: {adresse}",
                    )
                )

        except Exception as e:
            logger.error(f"SIRENE extraction failed: {e}")
            signals.append(
                Signal(
                    category=SignalCategory.OPERATIONAL,
                    name="sirene_error",
                    value=str(e),
                    source="SIRENE",
                    impact=SignalImpact.NEUTRAL,
                    likelihood_ratio=1.0,
                    details="Impossible de récupérer les données SIRENE",
                )
            )

        return signals

    async def _extract_bodacc_signals(self, siren: str) -> list[Signal]:
        """Extract signals from BODACC (annonces légales)."""
        signals: list[Signal] = []

        try:
            bodacc = await self._get_bodacc()

            # Search for all announcements (adapter takes dict)
            announcements = await bodacc.search({"siren": siren, "limit": 50})

            if not announcements:
                signals.append(
                    Signal(
                        category=SignalCategory.FINANCIAL,
                        name="aucune_annonce_bodacc",
                        value=True,
                        source="BODACC",
                        impact=SignalImpact.NEUTRAL,
                        likelihood_ratio=1.0,
                        details="Aucune annonce légale trouvée",
                    )
                )
                return signals

            # Analyze announcements by type
            privileges = []
            procedures = []
            ventes = []
            modifications = []

            for ann in announcements:
                nature = ann.get("publicationavis", "").lower()
                famille = ann.get("familleavis", "").lower()

                if "privilège" in nature or "privilege" in famille:
                    privileges.append(ann)
                elif "procédure" in nature or "liquidation" in famille or "redressement" in famille:
                    procedures.append(ann)
                elif "vente" in nature or "cession" in famille:
                    ventes.append(ann)
                elif "modification" in nature:
                    modifications.append(ann)

            # Signal: Privilèges multiples
            if len(privileges) >= 2:
                signals.append(
                    Signal(
                        category=SignalCategory.FINANCIAL,
                        name="privileges_inss_multiples",
                        value=len(privileges),
                        source="BODACC",
                        impact=SignalImpact.CRITICAL,
                        likelihood_ratio=SIGNAL_LR_TABLE["privileges_inss_multiples"][0],
                        details=f"{len(privileges)} privilèges déclarés (INSS, Trésor)",
                    )
                )
            elif len(privileges) == 1:
                signals.append(
                    Signal(
                        category=SignalCategory.FINANCIAL,
                        name="privilege_unique",
                        value=1,
                        source="BODACC",
                        impact=SignalImpact.NEGATIVE,
                        likelihood_ratio=3.0,
                        details="1 privilège déclaré",
                    )
                )
            else:
                signals.append(
                    Signal(
                        category=SignalCategory.FINANCIAL,
                        name="aucun_privilege",
                        value=0,
                        source="BODACC",
                        impact=SignalImpact.POSITIVE,
                        likelihood_ratio=SIGNAL_LR_TABLE["privileges_inss_multiples"][1],
                        details="Aucun privilège déclaré",
                    )
                )

            # Signal: Procédures collectives
            if procedures:
                signals.append(
                    Signal(
                        category=SignalCategory.FINANCIAL,
                        name="procedure_collective_passee",
                        value=len(procedures),
                        source="BODACC",
                        impact=SignalImpact.CRITICAL,
                        likelihood_ratio=SIGNAL_LR_TABLE["procedure_collective_passee"][0],
                        details=f"{len(procedures)} procédure(s) collective(s) (RJ/LJ)",
                    )
                )
            else:
                signals.append(
                    Signal(
                        category=SignalCategory.FINANCIAL,
                        name="aucune_procedure",
                        value=0,
                        source="BODACC",
                        impact=SignalImpact.POSITIVE,
                        likelihood_ratio=SIGNAL_LR_TABLE["procedure_collective_passee"][1],
                        details="Aucune procédure collective",
                    )
                )

            # Signal: Transferts de siège multiples
            siege_changes = [m for m in modifications if "siège" in str(m).lower()]
            if len(siege_changes) >= 2:
                signals.append(
                    Signal(
                        category=SignalCategory.LEGAL,
                        name="transferts_siege_multiples",
                        value=len(siege_changes),
                        source="BODACC",
                        impact=SignalImpact.NEGATIVE,
                        likelihood_ratio=SIGNAL_LR_TABLE["transferts_siege_multiples"][0],
                        details=f"{len(siege_changes)} transferts de siège récents",
                    )
                )

        except Exception as e:
            logger.error(f"BODACC extraction failed: {e}")
            signals.append(
                Signal(
                    category=SignalCategory.FINANCIAL,
                    name="bodacc_error",
                    value=str(e),
                    source="BODACC",
                    impact=SignalImpact.NEUTRAL,
                    likelihood_ratio=1.0,
                    details="Impossible de récupérer les annonces BODACC",
                )
            )

        return signals

    async def _extract_operational_signals(self, siren: str) -> list[Signal]:
        """Extract operational signals (marchés publics, etc)."""
        signals: list[Signal] = []

        try:
            # Check BOAMP for public contracts (adapter takes dict)
            from src.infrastructure.datasources.adapters.boamp import BoampAdapter

            boamp = BoampAdapter()
            contracts = await boamp.search({"nom": siren, "limit": 10})

            if contracts:
                signals.append(
                    Signal(
                        category=SignalCategory.OPERATIONAL,
                        name="marches_publics_gagnes",
                        value=len(contracts),
                        source="BOAMP",
                        impact=SignalImpact.POSITIVE,
                        likelihood_ratio=SIGNAL_LR_TABLE["marches_publics_gagnes"][0],
                        details=f"{len(contracts)} marché(s) public(s) remporté(s)",
                    )
                )

        except Exception as e:
            logger.debug(f"BOAMP extraction failed (non-critical): {e}")

        return signals

    def get_prior(self, naf_code: str) -> float:
        """Get prior probability based on NAF sector."""
        if not naf_code:
            return SECTOR_PRIORS["default"]

        section = naf_code[:2] if len(naf_code) >= 2 else naf_code
        return SECTOR_PRIORS.get(section, SECTOR_PRIORS["default"])
