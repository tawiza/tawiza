"""
Territorial Reports - Génération de rapports automatiques.

Rapports disponibles :
- Flash quotidien : Top 5 mouvements du jour
- Hebdo régional : Synthèse par région
- Mensuel national : Analyse complète France
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


@dataclass
class ReportSection:
    """Section d'un rapport."""

    title: str
    content: str
    data: dict[str, Any] | None = None


@dataclass
class TerritorialReport:
    """Rapport territorial généré."""

    report_type: str  # "daily", "weekly", "monthly"
    title: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    sections: list[ReportSection]
    summary: str

    def to_markdown(self) -> str:
        """Génère le rapport en Markdown."""
        lines = [
            f"# {self.title}",
            f"*Généré le {self.generated_at.strftime('%d/%m/%Y à %H:%M')}*",
            f"*Période : {self.period_start.strftime('%d/%m/%Y')} → {self.period_end.strftime('%d/%m/%Y')}*",
            "",
            "---",
            "",
            "## Résumé",
            self.summary,
            "",
        ]

        for section in self.sections:
            lines.extend(
                [
                    f"## {section.title}",
                    section.content,
                    "",
                ]
            )

        lines.extend(
            [
                "---",
                "*Rapport généré automatiquement par Tawiza-V2*",
            ]
        )

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_type": self.report_type,
            "title": self.title,
            "generated_at": self.generated_at.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "summary": self.summary,
            "sections": [
                {"title": s.title, "content": s.content, "data": s.data} for s in self.sections
            ],
        }


class TerritorialReportGenerator:
    """Générateur de rapports territoriaux."""

    def __init__(self):
        self._history_store = None
        self._signal_detector = None

    @property
    def history_store(self):
        if self._history_store is None:
            from src.infrastructure.persistence.territorial_history import get_history_store

            self._history_store = get_history_store()
        return self._history_store

    @property
    def signal_detector(self):
        if self._signal_detector is None:
            from src.infrastructure.agents.tajine.territorial.predictive_signals import (
                get_signal_detector,
            )

            self._signal_detector = get_signal_detector()
        return self._signal_detector

    async def generate_daily_flash(self) -> TerritorialReport:
        """
        Génère le flash quotidien.

        Contenu :
        - Top 5 territoires dynamiques
        - Top 5 territoires en difficulté
        - Alertes du jour
        """
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)

        # Récupérer les dernières données
        all_latest = self.history_store.get_all_latest()

        if not all_latest:
            return TerritorialReport(
                report_type="daily",
                title="📊 Flash Territorial - Aucune donnée",
                generated_at=now,
                period_start=yesterday,
                period_end=now,
                sections=[],
                summary="Aucune donnée disponible. Lancez une collecte.",
            )

        # Trier par vitalité
        sorted_by_vitality = sorted(all_latest, key=lambda m: m.vitality_index, reverse=True)

        # Top 5 dynamiques
        top_5 = sorted_by_vitality[:5]
        top_5_content = "\n".join(
            [
                f"**{i + 1}. {m.territory_name}** — Vitalité: **{m.vitality_index:.1f}** | "
                f"Créations: +{m.creations} | Fermetures: {m.closures}"
                for i, m in enumerate(top_5)
            ]
        )

        # Bottom 5 (en difficulté)
        bottom_5 = sorted_by_vitality[-5:][::-1]
        bottom_5_content = "\n".join(
            [
                f"**{i + 1}. {m.territory_name}** — Vitalité: **{m.vitality_index:.1f}** | "
                f"Solde: {m.creations - m.closures:+d}"
                for i, m in enumerate(bottom_5)
            ]
        )

        # Collecter les alertes
        alerts = []
        for m in all_latest:
            signals = await self.signal_detector.detect_signals(
                m.territory_code,
                m.territory_name,
                {
                    "creations_count": m.creations,
                    "closures_count": m.closures,
                    "modifications_count": m.modifications,
                    "unemployment_rate": m.unemployment_rate,
                    "vitality_index": m.vitality_index,
                },
            )
            for s in signals:
                if s.severity.value in ("alert", "critical"):
                    alerts.append(f"⚠️ **{m.territory_name}** : {s.title}")

        alerts_content = "\n".join(alerts[:10]) if alerts else "✅ Aucune alerte critique"

        # Résumé
        avg_vitality = sum(m.vitality_index for m in all_latest) / len(all_latest)
        total_creations = sum(m.creations for m in all_latest)
        total_closures = sum(m.closures for m in all_latest)

        summary = (
            f"**{len(all_latest)} territoires** analysés | "
            f"Vitalité moyenne: **{avg_vitality:.1f}** | "
            f"Créations: **{total_creations}** | Fermetures: **{total_closures}** | "
            f"Solde national: **{total_creations - total_closures:+d}**"
        )

        return TerritorialReport(
            report_type="daily",
            title=f"📊 Flash Territorial du {now.strftime('%d/%m/%Y')}",
            generated_at=now,
            period_start=yesterday,
            period_end=now,
            sections=[
                ReportSection(
                    "🏆 Top 5 Dynamiques",
                    top_5_content,
                    {"territories": [m.territory_code for m in top_5]},
                ),
                ReportSection(
                    "⚠️ 5 Territoires à surveiller",
                    bottom_5_content,
                    {"territories": [m.territory_code for m in bottom_5]},
                ),
                ReportSection("🚨 Alertes", alerts_content, {"count": len(alerts)}),
            ],
            summary=summary,
        )

    async def generate_weekly_summary(self) -> TerritorialReport:
        """Génère le résumé hebdomadaire."""
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)

        all_latest = self.history_store.get_all_latest()

        # Calculer les tendances sur 7 jours
        trends_data = []
        for m in all_latest:
            trends = self.history_store.get_trends(m.territory_code, periods=[7])
            trend_7d = trends.get("7d", {})
            trends_data.append(
                {
                    "code": m.territory_code,
                    "name": m.territory_name,
                    "vitality": m.vitality_index,
                    "change_7d": trend_7d.get("vitality_change", 0),
                }
            )

        # Top progressions
        progressions = sorted(trends_data, key=lambda x: x["change_7d"], reverse=True)[:5]
        prog_content = (
            "\n".join(
                [
                    f"**{t['name']}** : {t['vitality']:.1f} ({t['change_7d']:+.1f} pts)"
                    for t in progressions
                    if t["change_7d"] > 0
                ]
            )
            or "Pas de progression significative"
        )

        # Top régressions
        regressions = sorted(trends_data, key=lambda x: x["change_7d"])[:5]
        reg_content = (
            "\n".join(
                [
                    f"**{t['name']}** : {t['vitality']:.1f} ({t['change_7d']:+.1f} pts)"
                    for t in regressions
                    if t["change_7d"] < 0
                ]
            )
            or "Pas de régression significative"
        )

        summary = f"Analyse de {len(all_latest)} territoires sur 7 jours"

        return TerritorialReport(
            report_type="weekly",
            title=f"📈 Synthèse Hebdomadaire - Semaine du {week_ago.strftime('%d/%m')}",
            generated_at=now,
            period_start=week_ago,
            period_end=now,
            sections=[
                ReportSection("📈 Top Progressions", prog_content),
                ReportSection("📉 Régressions", reg_content),
            ],
            summary=summary,
        )


# Singleton
_generator: TerritorialReportGenerator | None = None


def get_report_generator() -> TerritorialReportGenerator:
    global _generator
    if _generator is None:
        _generator = TerritorialReportGenerator()
    return _generator
