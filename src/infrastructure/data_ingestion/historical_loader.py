"""Historical Data Loader - Orchestre l'ingestion des données historiques.

Pipeline complet:
1. Télécharge les données (DVF, SIRENE, BODACC)
2. Agrège en séries temporelles
3. Calcule les corrélations
4. Détecte les anomalies
5. Stocke les résultats
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from src.application.services.correlation_engine import (
    AnomalyResult,
    CorrelationResult,
    get_correlation_engine,
)
from src.infrastructure.data_ingestion.dvf_ingester import DVFIngester
from src.infrastructure.persistence.models.territorial_timeseries import (
    IndicatorType,
)


@dataclass
class TerritoryStats:
    """Statistiques agrégées pour un territoire."""

    code: str
    name: str
    period: datetime

    # DVF
    dvf_transactions: int = 0
    dvf_volume: float = 0
    dvf_price_m2_apt: float = 0
    dvf_price_m2_house: float = 0

    # Surfaces pour moyenne pondérée
    _apt_surface_total: float = 0
    _apt_value_total: float = 0
    _house_surface_total: float = 0
    _house_value_total: float = 0

    def add_transaction(self, tx: dict) -> None:
        """Ajoute une transaction aux stats."""
        self.dvf_transactions += 1
        self.dvf_volume += tx.get("valeur_fonciere", 0)

        type_local = tx.get("type_local", "")
        surface = tx.get("surface_reelle_bati") or 0
        valeur = tx.get("valeur_fonciere", 0)

        if surface > 0:
            if "Appartement" in type_local:
                self._apt_surface_total += surface
                self._apt_value_total += valeur
            elif "Maison" in type_local:
                self._house_surface_total += surface
                self._house_value_total += valeur

    def finalize(self) -> None:
        """Calcule les moyennes finales."""
        if self._apt_surface_total > 0:
            self.dvf_price_m2_apt = self._apt_value_total / self._apt_surface_total
        if self._house_surface_total > 0:
            self.dvf_price_m2_house = self._house_value_total / self._house_surface_total


class HistoricalDataLoader:
    """Charge et analyse les données historiques.

    Crée des séries temporelles mensuelles par département.
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("/tmp/historical_data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._timeseries: dict[tuple[IndicatorType, str], tuple[np.ndarray, list[datetime]]] = {}
        self._stats_by_period: dict[
            tuple[str, str], TerritoryStats
        ] = {}  # (dept, YYYY-MM) -> stats

    async def load_dvf(
        self,
        departments: list[str],
        years: list[int] | None = None,
    ) -> dict[str, Any]:
        """Charge les données DVF pour les départements spécifiés.

        Args:
            departments: Codes départements (ex: ["69", "75", "13"])
            years: Années à charger (défaut: 2020-2024)

        Returns:
            Stats de chargement
        """
        years = years or [2020, 2021, 2022, 2023, 2024]

        stats = {
            "departments": departments,
            "years": years,
            "total_transactions": 0,
            "total_volume": 0,
            "by_department": {},
        }

        async with DVFIngester(self.data_dir / "dvf") as ingester:
            for dept in departments:
                dept_stats = {"transactions": 0, "volume": 0, "by_year": {}}

                for year in years:
                    logger.info(f"Loading DVF {year}/{dept}...")

                    file_path = await ingester.download_department(year, dept)
                    if not file_path:
                        logger.warning(f"No data for {year}/{dept}")
                        continue

                    year_tx = 0
                    year_vol = 0

                    async for batch in ingester.parse_csv(file_path, batch_size=5000):
                        for tx in batch:
                            # Clé période (YYYY-MM)
                            period_key = tx.date_mutation.strftime("%Y-%m")
                            stats_key = (dept, period_key)

                            if stats_key not in self._stats_by_period:
                                self._stats_by_period[stats_key] = TerritoryStats(
                                    code=dept,
                                    name=tx.nom_commune,
                                    period=tx.date_mutation.replace(day=1),
                                )

                            self._stats_by_period[stats_key].add_transaction(tx.to_dict())
                            year_tx += 1
                            year_vol += tx.valeur_fonciere

                    dept_stats["by_year"][year] = {"tx": year_tx, "vol": year_vol}
                    dept_stats["transactions"] += year_tx
                    dept_stats["volume"] += year_vol

                stats["by_department"][dept] = dept_stats
                stats["total_transactions"] += dept_stats["transactions"]
                stats["total_volume"] += dept_stats["volume"]

        # Finaliser les stats
        for s in self._stats_by_period.values():
            s.finalize()

        # Construire les séries temporelles
        self._build_timeseries()

        logger.info(
            f"Loaded {stats['total_transactions']:,} DVF transactions, "
            f"{stats['total_volume'] / 1e9:.2f}B€"
        )

        return stats

    def _build_timeseries(self) -> None:
        """Construit les séries temporelles à partir des stats agrégées."""
        # Grouper par département
        by_dept: dict[str, list[tuple[datetime, TerritoryStats]]] = {}

        for (dept, _), stats in self._stats_by_period.items():
            by_dept.setdefault(dept, []).append((stats.period, stats))

        # Construire les séries
        for dept, data in by_dept.items():
            # Trier par date
            data.sort(key=lambda x: x[0])

            dates = [d[0] for d in data]

            # DVF Transactions
            values = np.array([d[1].dvf_transactions for d in data], dtype=float)
            self._timeseries[(IndicatorType.DVF_TRANSACTIONS, dept)] = (values, dates)

            # DVF Volume
            values = np.array([d[1].dvf_volume for d in data], dtype=float)
            self._timeseries[(IndicatorType.DVF_VOLUME, dept)] = (values, dates)

            # Prix m² Appartement
            values = np.array([d[1].dvf_price_m2_apt for d in data], dtype=float)
            if np.any(values > 0):
                self._timeseries[(IndicatorType.DVF_PRICE_M2_APT, dept)] = (values, dates)

            # Prix m² Maison
            values = np.array([d[1].dvf_price_m2_house for d in data], dtype=float)
            if np.any(values > 0):
                self._timeseries[(IndicatorType.DVF_PRICE_M2_HOUSE, dept)] = (values, dates)

        logger.info(f"Built {len(self._timeseries)} time series")

    def analyze_correlations(self) -> list[CorrelationResult]:
        """Analyse les corrélations entre séries temporelles."""
        engine = get_correlation_engine()
        return engine.find_all_correlations(self._timeseries)

    def detect_anomalies(self) -> list[AnomalyResult]:
        """Détecte les anomalies dans toutes les séries."""
        engine = get_correlation_engine()
        anomalies = []

        for (indicator, territory), (values, dates) in self._timeseries.items():
            # Z-score anomalies
            anoms = engine.detect_anomalies(values, indicator, territory, dates)
            anomalies.extend(anoms)

            # Trend breaks
            breaks = engine.detect_trend_break(values, indicator, territory, dates)
            anomalies.extend(breaks)

        logger.info(f"Detected {len(anomalies)} anomalies")
        return anomalies

    def get_insights(self) -> list[dict[str, Any]]:
        """Génère les insights exploitables."""
        correlations = self.analyze_correlations()
        anomalies = self.detect_anomalies()

        engine = get_correlation_engine()
        return engine.generate_insights(correlations, anomalies)

    def get_summary(self) -> dict[str, Any]:
        """Résumé des données chargées."""
        return {
            "periods_loaded": len(self._stats_by_period),
            "timeseries_count": len(self._timeseries),
            "departments": list({k[1] for k in self._timeseries}),
            "indicators": list({k[0].value for k in self._timeseries}),
            "date_range": {
                "start": min(
                    (dates[0] for _, (_, dates) in self._timeseries.items() if dates), default=None
                ),
                "end": max(
                    (dates[-1] for _, (_, dates) in self._timeseries.items() if dates), default=None
                ),
            }
            if self._timeseries
            else None,
        }


async def run_full_analysis(departments: list[str]) -> dict[str, Any]:
    """Lance l'analyse complète sur les départements spécifiés.

    Args:
        departments: Liste des codes départements

    Returns:
        Résultats complets (stats, corrélations, anomalies, insights)
    """
    loader = HistoricalDataLoader()

    # 1. Charger les données DVF
    logger.info(f"Starting analysis for departments: {departments}")
    load_stats = await loader.load_dvf(departments)

    # 2. Analyser les corrélations
    correlations = loader.analyze_correlations()

    # 3. Détecter les anomalies
    anomalies = loader.detect_anomalies()

    # 4. Générer les insights
    insights = loader.get_insights()

    # 5. Résumé
    summary = loader.get_summary()

    return {
        "summary": summary,
        "load_stats": load_stats,
        "correlations": [c.to_dict() for c in correlations[:20]],  # Top 20
        "anomalies": [a.to_dict() for a in anomalies[:30]],  # Top 30
        "insights": insights[:10],  # Top 10
    }


if __name__ == "__main__":
    # Test sur Rhône, Paris, Bouches-du-Rhône
    results = asyncio.run(run_full_analysis(["69", "75", "13"]))

    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)

    print(f"\nSummary: {results['summary']}")
    print("\nTop Correlations:")
    for c in results["correlations"][:5]:
        print(f"  {c['source']} → {c['target']}: r={c['correlation']:.2f}, lag={c['lag_months']}m")

    print("\nTop Insights:")
    for i in results["insights"][:5]:
        print(f"  [{i['type']}] {i['message']}")
