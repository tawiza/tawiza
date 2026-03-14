"""
Sector Analyzer - Analyse sectorielle des données BODACC.

Fournit des statistiques par secteur NAF pour un territoire.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.infrastructure.agents.tajine.territorial.naf_classifier import (
    get_naf_classifier,
)


@dataclass
class SectorStats:
    """Statistiques d'un secteur."""

    code: str
    name: str
    short_name: str
    creations: int = 0
    closures: int = 0
    modifications: int = 0

    @property
    def net_creation(self) -> int:
        return self.creations - self.closures

    @property
    def dynamism_score(self) -> float:
        """Score de dynamisme (-100 à +100)."""
        total = self.creations + self.closures
        if total == 0:
            return 0.0
        return ((self.creations - self.closures) / total) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "short_name": self.short_name,
            "creations": self.creations,
            "closures": self.closures,
            "modifications": self.modifications,
            "net_creation": self.net_creation,
            "dynamism_score": round(self.dynamism_score, 1),
        }


@dataclass
class TerritorialSectorAnalysis:
    """Analyse sectorielle complète d'un territoire."""

    territory_code: str
    territory_name: str
    analyzed_at: datetime
    total_records: int
    classified_records: int
    sectors: dict[str, SectorStats] = field(default_factory=dict)

    @property
    def top_creators(self) -> list[SectorStats]:
        """Top 5 secteurs créateurs."""
        return sorted(
            [s for s in self.sectors.values() if s.creations > 0],
            key=lambda s: s.creations,
            reverse=True,
        )[:5]

    @property
    def top_destroyers(self) -> list[SectorStats]:
        """Top 5 secteurs avec le plus de fermetures."""
        return sorted(
            [s for s in self.sectors.values() if s.closures > 0],
            key=lambda s: s.closures,
            reverse=True,
        )[:5]

    @property
    def most_dynamic(self) -> list[SectorStats]:
        """Top 5 secteurs les plus dynamiques (score positif)."""
        return sorted(
            [s for s in self.sectors.values() if s.net_creation > 0],
            key=lambda s: s.net_creation,
            reverse=True,
        )[:5]

    @property
    def in_crisis(self) -> list[SectorStats]:
        """Secteurs en crise (plus de fermetures que créations)."""
        return [s for s in self.sectors.values() if s.net_creation < 0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "territory_code": self.territory_code,
            "territory_name": self.territory_name,
            "analyzed_at": self.analyzed_at.isoformat(),
            "total_records": self.total_records,
            "classified_records": self.classified_records,
            "classification_rate": round(
                self.classified_records / max(1, self.total_records) * 100, 1
            ),
            "sectors": {k: v.to_dict() for k, v in self.sectors.items()},
            "summary": {
                "top_creators": [s.to_dict() for s in self.top_creators],
                "top_destroyers": [s.to_dict() for s in self.top_destroyers],
                "most_dynamic": [s.to_dict() for s in self.most_dynamic],
                "in_crisis": [s.to_dict() for s in self.in_crisis],
            },
        }


class SectorAnalyzer:
    """Analyseur sectoriel pour les données BODACC."""

    def __init__(self):
        self.classifier = get_naf_classifier()

    async def analyze_territory(
        self,
        territory_code: str,
        territory_name: str,
        bodacc_adapter,
        limit: int = 500,
    ) -> TerritorialSectorAnalysis:
        """
        Analyse les données BODACC d'un territoire par secteur.

        Args:
            territory_code: Code du département
            territory_name: Nom du territoire
            bodacc_adapter: Adaptateur BODACC
            limit: Nombre max d'annonces à analyser
        """
        # Récupérer les données BODACC
        results = await bodacc_adapter.search(
            {
                "departement": territory_code,
                "limit": limit,
            }
        )

        # Initialiser les stats par secteur
        sector_stats: dict[str, SectorStats] = {}
        classified_count = 0

        for record in results:
            # Extraire et classifier l'activité
            activity = self._extract_activity(record)
            if not activity:
                continue

            code, confidence = self.classifier.classify(activity)
            if code == "?" or confidence < 0.3:
                continue

            classified_count += 1

            # Créer la section si nécessaire
            if code not in sector_stats:
                section = self.classifier.get_section(code)
                sector_stats[code] = SectorStats(
                    code=code,
                    name=section.name if section else "Inconnu",
                    short_name=section.short_name if section else "Autre",
                )

            # Incrémenter selon le type
            record_type = record.get("type", "").lower()
            if record_type == "creation":
                sector_stats[code].creations += 1
            elif record_type == "radiation":
                sector_stats[code].closures += 1
            elif record_type == "modification":
                sector_stats[code].modifications += 1

        return TerritorialSectorAnalysis(
            territory_code=territory_code,
            territory_name=territory_name,
            analyzed_at=datetime.utcnow(),
            total_records=len(results),
            classified_records=classified_count,
            sectors=sector_stats,
        )

    def _extract_activity(self, record: dict[str, Any]) -> str | None:
        """Extrait la description d'activité d'un enregistrement BODACC."""
        raw = record.get("raw", {})
        etab_str = raw.get("listeetablissements", "")

        if not etab_str:
            return None

        try:
            etab = json.loads(etab_str) if isinstance(etab_str, str) else etab_str
            if isinstance(etab, dict) and "etablissement" in etab:
                return etab["etablissement"].get("activite", "")
        except (json.JSONDecodeError, TypeError):
            pass

        return None


# Singleton
_analyzer: SectorAnalyzer | None = None


def get_sector_analyzer() -> SectorAnalyzer:
    """Retourne l'analyseur singleton."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SectorAnalyzer()
    return _analyzer
