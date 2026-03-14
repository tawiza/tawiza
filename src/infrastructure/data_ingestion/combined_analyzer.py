"""Combined Analyzer - Analyse combinée DVF + BODACC.

C'est ici qu'on trouve ce qu'un analyste ne voit pas:
- Corrélations décalées entre transactions immo et procédures
- Patterns précurseurs de crises
- Anomalies multi-sources
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
    CorrelationEngine,
    CorrelationResult,
    get_correlation_engine,
)
from src.infrastructure.data_ingestion.bodacc_ingester import BODACCIngester
from src.infrastructure.data_ingestion.dvf_ingester import DVFIngester
from src.infrastructure.persistence.models.territorial_timeseries import IndicatorType


@dataclass
class CombinedInsight:
    """Un insight découvert par l'analyse combinée."""

    type: str  # predictive, anomaly, pattern
    severity: float  # 0-1
    message: str
    sources: list[str]
    territory: str
    lag_months: int | None = None
    confidence: float = 0.0
    actionable: bool = True

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "severity": round(self.severity, 2),
            "message": self.message,
            "sources": self.sources,
            "territory": self.territory,
            "lag_months": self.lag_months,
            "confidence": round(self.confidence, 2),
            "actionable": self.actionable,
        }


class CombinedAnalyzer:
    """Analyse combinée multi-sources.

    Croise DVF + BODACC pour trouver les corrélations cachées.
    """

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path("/tmp/combined_analysis")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._dvf_series: dict[str, tuple[np.ndarray, list[datetime]]] = {}
        self._bodacc_series: dict[str, tuple[np.ndarray, list[datetime]]] = {}
        self._all_series: dict[tuple[IndicatorType, str], tuple[np.ndarray, list[datetime]]] = {}

    async def load_data(
        self,
        department: str,
        years: list[int] | None = None,
    ) -> dict[str, Any]:
        """Charge les données DVF et BODACC.

        Args:
            department: Code département
            years: Années à charger

        Returns:
            Stats de chargement
        """
        years = years or [2020, 2021, 2022, 2023, 2024]
        start_date = datetime(min(years), 1, 1)
        end_date = datetime(max(years), 12, 31)

        stats = {
            "department": department,
            "years": years,
            "dvf": {},
            "bodacc": {},
        }

        # 1. Charger DVF
        logger.info(f"Loading DVF for {department}...")
        dvf_monthly = await self._load_dvf(department, years)
        stats["dvf"]["periods"] = len(dvf_monthly)
        stats["dvf"]["total_tx"] = sum(d["transactions"] for d in dvf_monthly.values())

        # 2. Charger BODACC
        logger.info(f"Loading BODACC for {department}...")
        bodacc_monthly = await self._load_bodacc(department, start_date, end_date)
        stats["bodacc"]["periods"] = len(bodacc_monthly)
        stats["bodacc"]["total_procedures"] = sum(d["procedures"] for d in bodacc_monthly.values())

        # 3. Construire les séries temporelles alignées
        self._build_aligned_series(department, dvf_monthly, bodacc_monthly)

        stats["timeseries_count"] = len(self._all_series)

        return stats

    async def _load_dvf(
        self,
        department: str,
        years: list[int],
    ) -> dict[str, dict[str, Any]]:
        """Charge et agrège les données DVF par mois."""
        monthly: dict[str, dict[str, Any]] = {}

        async with DVFIngester(self.data_dir / "dvf") as ingester:
            for year in years:
                file_path = await ingester.download_department(year, department)
                if not file_path:
                    continue

                async for batch in ingester.parse_csv(file_path, batch_size=5000):
                    for tx in batch:
                        period = tx.date_mutation.strftime("%Y-%m")

                        if period not in monthly:
                            monthly[period] = {
                                "transactions": 0,
                                "volume": 0,
                                "apt_m2_sum": 0,
                                "apt_surface": 0,
                                "house_m2_sum": 0,
                                "house_surface": 0,
                            }

                        monthly[period]["transactions"] += 1
                        monthly[period]["volume"] += tx.valeur_fonciere

                        if tx.surface_reelle_bati and tx.surface_reelle_bati > 0:
                            if "Appartement" in (tx.type_local or ""):
                                monthly[period]["apt_m2_sum"] += tx.valeur_fonciere
                                monthly[period]["apt_surface"] += tx.surface_reelle_bati
                            elif "Maison" in (tx.type_local or ""):
                                monthly[period]["house_m2_sum"] += tx.valeur_fonciere
                                monthly[period]["house_surface"] += tx.surface_reelle_bati

        return monthly

    async def _load_bodacc(
        self,
        department: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, dict[str, int]]:
        """Charge et agrège les données BODACC par mois."""
        async with BODACCIngester() as ingester:
            # Limit to 5000 for performance
            announcements = await ingester.fetch_by_department(
                department, start_date, end_date, limit=5000
            )

            monthly: dict[str, dict[str, int]] = {}

            for ann in announcements:
                period = ann.date_parution.strftime("%Y-%m")

                if period not in monthly:
                    monthly[period] = {
                        "total": 0,
                        "procedures": 0,
                        "liquidations": 0,
                    }

                monthly[period]["total"] += 1
                monthly[period]["procedures"] += 1  # All BODACC B are procedures

                # Check type for liquidation
                type_annonce = (ann.type_annonce or "").lower()
                if "liquidation" in type_annonce or "lj" in type_annonce:
                    monthly[period]["liquidations"] += 1

            return monthly

    def _build_aligned_series(
        self,
        department: str,
        dvf_monthly: dict[str, dict],
        bodacc_monthly: dict[str, dict],
    ) -> None:
        """Construit des séries temporelles alignées."""
        # Trouver les périodes communes
        all_periods = sorted(set(dvf_monthly.keys()) | set(bodacc_monthly.keys()))

        if not all_periods:
            return

        # Convertir en dates
        dates = [datetime.strptime(p, "%Y-%m") for p in all_periods]

        # DVF Transactions
        values = np.array(
            [dvf_monthly.get(p, {}).get("transactions", 0) for p in all_periods], dtype=float
        )
        self._all_series[(IndicatorType.DVF_TRANSACTIONS, department)] = (values, dates)

        # DVF Volume
        values = np.array(
            [dvf_monthly.get(p, {}).get("volume", 0) for p in all_periods], dtype=float
        )
        self._all_series[(IndicatorType.DVF_VOLUME, department)] = (values, dates)

        # Prix m² Appartement
        apt_prices = []
        for p in all_periods:
            d = dvf_monthly.get(p, {})
            if d.get("apt_surface", 0) > 0:
                apt_prices.append(d["apt_m2_sum"] / d["apt_surface"])
            else:
                apt_prices.append(0)
        self._all_series[(IndicatorType.DVF_PRICE_M2_APT, department)] = (
            np.array(apt_prices),
            dates,
        )

        # BODACC Procédures
        values = np.array(
            [bodacc_monthly.get(p, {}).get("procedures", 0) for p in all_periods], dtype=float
        )
        self._all_series[(IndicatorType.BODACC_PROCEDURES, department)] = (values, dates)

        # BODACC Liquidations
        values = np.array(
            [bodacc_monthly.get(p, {}).get("liquidations", 0) for p in all_periods], dtype=float
        )
        self._all_series[(IndicatorType.BODACC_LIQUIDATIONS, department)] = (values, dates)

    def analyze(self) -> dict[str, Any]:
        """Analyse complète pour trouver les corrélations cachées."""
        engine = get_correlation_engine()

        # 1. Corrélations
        correlations = engine.find_all_correlations(self._all_series)

        # 2. Anomalies
        anomalies = []
        for (indicator, territory), (values, dates) in self._all_series.items():
            anoms = engine.detect_anomalies(values, indicator, territory, dates)
            anomalies.extend(anoms)

            breaks = engine.detect_trend_break(values, indicator, territory, dates)
            anomalies.extend(breaks)

        # 3. Insights combinés
        insights = self._generate_combined_insights(correlations, anomalies)

        return {
            "correlations": [c.to_dict() for c in correlations],
            "anomalies": [a.to_dict() for a in anomalies],
            "insights": [i.to_dict() for i in insights],
            "series_count": len(self._all_series),
        }

    def _generate_combined_insights(
        self,
        correlations: list[CorrelationResult],
        anomalies: list[AnomalyResult],
    ) -> list[CombinedInsight]:
        """Génère des insights exploitables."""
        insights = []

        # Insight 1: DVF → BODACC correlations (immobilier prédit procédures)
        for corr in correlations:
            if corr.source_indicator in [
                IndicatorType.DVF_TRANSACTIONS,
                IndicatorType.DVF_VOLUME,
            ] and corr.target_indicator in [
                IndicatorType.BODACC_PROCEDURES,
                IndicatorType.BODACC_LIQUIDATIONS,
            ]:
                if corr.lag_months >= 6 and abs(corr.correlation) > 0.4:
                    direction = "baisse" if corr.correlation > 0 else "hausse"
                    insights.append(
                        CombinedInsight(
                            type="predictive",
                            severity=abs(corr.correlation),
                            message=(
                                f"SIGNAL PRÉDICTIF: Une {direction} des transactions immobilières "
                                f"prédit les procédures collectives avec {corr.lag_months} mois d'avance "
                                f"(r={corr.correlation:.2f}, p={corr.p_value:.3f})"
                            ),
                            sources=["DVF", "BODACC"],
                            territory=corr.territory_code or "national",
                            lag_months=corr.lag_months,
                            confidence=corr.confidence,
                        )
                    )

        # Insight 2: Anomalies DVF récentes
        recent_dvf_anomalies = [
            a
            for a in anomalies
            if a.indicator in [IndicatorType.DVF_TRANSACTIONS, IndicatorType.DVF_VOLUME]
            and a.severity > 0.5
        ]

        if recent_dvf_anomalies:
            latest = max(recent_dvf_anomalies, key=lambda a: a.period)
            insights.append(
                CombinedInsight(
                    type="anomaly",
                    severity=latest.severity,
                    message=(
                        f"ANOMALIE DÉTECTÉE: {latest.anomaly_type} sur {latest.indicator.value} "
                        f"({latest.deviation_sigma:.1f}σ) - Surveiller les procédures dans 6-18 mois"
                    ),
                    sources=["DVF"],
                    territory=latest.territory_code,
                    confidence=0.7,
                )
            )

        # Insight 3: Hausse procédures
        proc_anomalies = [
            a
            for a in anomalies
            if a.indicator in [IndicatorType.BODACC_PROCEDURES, IndicatorType.BODACC_LIQUIDATIONS]
            and a.anomaly_type == "spike"
        ]

        if proc_anomalies:
            total_spike = sum(a.severity for a in proc_anomalies)
            insights.append(
                CombinedInsight(
                    type="alert",
                    severity=min(1.0, total_spike),
                    message=(
                        f"ALERTE: {len(proc_anomalies)} pics de procédures collectives détectés - "
                        f"Vérifier l'état du marché immobilier 6-12 mois avant"
                    ),
                    sources=["BODACC"],
                    territory=proc_anomalies[0].territory_code,
                    confidence=0.8,
                )
            )

        # Trier par sévérité
        insights.sort(key=lambda x: x.severity, reverse=True)

        return insights


async def run_combined_analysis(department: str) -> dict[str, Any]:
    """Lance l'analyse combinée complète."""
    analyzer = CombinedAnalyzer()

    # Charger les données
    load_stats = await analyzer.load_data(department, years=[2020, 2021, 2022, 2023, 2024])

    # Analyser
    results = analyzer.analyze()

    return {
        "load_stats": load_stats,
        **results,
    }


if __name__ == "__main__":
    results = asyncio.run(run_combined_analysis("69"))

    print("\n" + "=" * 60)
    print("ANALYSE COMBINÉE DVF + BODACC - RHÔNE (69)")
    print("=" * 60)

    print("\nDonnées chargées:")
    print(f"  DVF: {results['load_stats']['dvf']['total_tx']:,} transactions")
    print(f"  BODACC: {results['load_stats']['bodacc']['total_procedures']:,} procédures")

    print(f"\nCorrélations trouvées: {len(results['correlations'])}")
    for c in results["correlations"][:5]:
        print(f"  {c['source']} → {c['target']}: r={c['correlation']:.2f}, lag={c['lag_months']}m")

    print(f"\nAnomalies: {len(results['anomalies'])}")

    print("\n🎯 INSIGHTS:")
    for i in results["insights"][:5]:
        print(f"\n  [{i['type'].upper()}] (sévérité: {i['severity']:.0%})")
        print(f"  {i['message']}")
