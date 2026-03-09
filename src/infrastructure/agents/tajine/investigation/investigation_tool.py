"""
Investigation Tool - Outil TAJINE pour investigation d'entreprise.

Usage: investigate_enterprise(siren="123456789", context="Demande France 2030")
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .bayesian_reasoner import BayesianReasoner
from .report_generator import InvestigationReport, ReportGenerator
from .signal_extractor import SignalExtractor


class InvestigateEnterpriseTool:
    """
    Outil d'investigation entreprise pour TAJINE.

    Agrège toutes les sources publiques, calcule un score bayésien
    et génère un rapport d'investigation complet.
    """

    name = "investigate_enterprise"
    description = """
    Investigate a company for subsidy or partnership eligibility.

    Aggregates public data from SIRENE, BODACC, BOAMP to:
    - Extract financial and operational signals
    - Compute Bayesian risk assessment
    - Generate investigation report with questions

    Args:
        siren: SIREN number (9 digits)
        context: Investigation context (e.g., "Demande aide France 2030")
        denomination: Company name (optional)

    Returns:
        InvestigationReport with risk assessment and recommendations
    """

    def __init__(self) -> None:
        """Initialize the investigation tool."""
        self._extractor = SignalExtractor()
        self._reasoner = BayesianReasoner()
        self._generator = ReportGenerator()

    async def execute(
        self,
        siren: str,
        context: str = "",
        denomination: str = "Entreprise",
    ) -> InvestigationReport:
        """
        Execute investigation on a company.

        Args:
            siren: SIREN number (9 digits)
            context: Investigation context
            denomination: Company name

        Returns:
            Complete InvestigationReport
        """
        logger.info(f"Starting investigation for SIREN {siren}")

        # Validate SIREN format
        siren_clean = siren.replace(" ", "").strip()
        if not siren_clean.isdigit() or len(siren_clean) != 9:
            logger.warning(f"Invalid SIREN format: {siren}")
            # Try to proceed anyway

        # 1. Extract signals from all sources (parallel)
        signals = await self._extractor.extract_all(siren_clean)
        logger.info(f"Extracted {len(signals)} signals")

        # 2. Compute Bayesian risk assessment
        assessment = self._reasoner.compute(signals)
        logger.info(
            f"Risk assessment: {assessment.risk_level.value} "
            f"(posterior={assessment.posterior:.2%})"
        )

        # 3. Generate investigation report
        report = self._generator.generate(
            siren=siren_clean,
            signals=signals,
            assessment=assessment,
            context=context,
            denomination=denomination,
        )

        logger.info(f"Investigation complete for {siren_clean}")
        return report

    async def __call__(
        self,
        siren: str,
        context: str = "",
        denomination: str = "Entreprise",
    ) -> InvestigationReport:
        """Allow calling the tool directly."""
        return await self.execute(siren, context, denomination)

    def get_schema(self) -> dict[str, Any]:
        """Get JSON schema for tool parameters."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "siren": {
                        "type": "string",
                        "description": "SIREN number (9 digits)",
                        "pattern": "^[0-9]{9}$",
                    },
                    "context": {
                        "type": "string",
                        "description": "Investigation context (e.g., 'Demande France 2030')",
                        "default": "",
                    },
                    "denomination": {
                        "type": "string",
                        "description": "Company name",
                        "default": "Entreprise",
                    },
                },
                "required": ["siren"],
            },
        }


# Convenience function for direct use
async def investigate_enterprise(
    siren: str,
    context: str = "",
    denomination: str = "Entreprise",
) -> InvestigationReport:
    """
    Convenience function to investigate an enterprise.

    Example:
        >>> report = await investigate_enterprise("123456789", "Demande France 2030")
        >>> print(report.to_markdown())
    """
    tool = InvestigateEnterpriseTool()
    return await tool.execute(siren, context, denomination)
