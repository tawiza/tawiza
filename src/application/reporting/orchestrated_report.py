"""Enhanced report generator for multi-source orchestrated analysis.

Generates rich HTML reports with:
- Executive summary with confidence score
- Source-by-source breakdown
- Multi-agent validation timeline
- Issues and recommendations
- Interactive visualizations
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.application.orchestration.data_orchestrator import OrchestratedResult
from src.domain.debate.debate_system import DebateResult


@dataclass
class ReportConfig:
    """Configuration for report generation."""

    output_dir: str
    query: str
    include_raw_data: bool = True
    include_timeline: bool = True
    theme: str = "dark"  # dark or light


class OrchestratedReportGenerator:
    """Generate comprehensive reports for multi-source analysis."""

    def __init__(self, config: ReportConfig):
        """Initialize report generator.

        Args:
            config: Report configuration
        """
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_html_report(
        self,
        orch_result: OrchestratedResult,
        debate_result: DebateResult,
    ) -> str:
        """Generate comprehensive HTML report.

        Args:
            orch_result: Results from DataOrchestrator
            debate_result: Results from DebateSystem

        Returns:
            Path to generated HTML file
        """
        report_path = self.output_dir / "rapport_multi_source.html"

        # Calculate metrics
        total_results = orch_result.total_results
        successful_sources = sum(
            1 for sr in orch_result.source_results if sr.results
        )
        total_sources = len(orch_result.source_results)
        confidence = debate_result.final_confidence

        # Confidence color
        if confidence >= 80:
            conf_color = "#10B981"  # green
            conf_bg = "#D1FAE5"
        elif confidence >= 60:
            conf_color = "#F59E0B"  # amber
            conf_bg = "#FEF3C7"
        else:
            conf_color = "#EF4444"  # red
            conf_bg = "#FEE2E2"

        # Build source rows
        source_rows = ""
        for sr in orch_result.source_results:
            status = "✓" if sr.results else "✗"
            status_color = "#10B981" if sr.results else "#EF4444"
            count = len(sr.results) if sr.results else 0
            error = sr.error[:50] if sr.error else ""

            source_rows += f"""
            <tr>
                <td><span style="color: {status_color}; font-weight: bold;">{status}</span> {sr.source}</td>
                <td>{count}</td>
                <td>{sr.duration_ms:.0f}ms</td>
                <td class="error-cell">{error}</td>
            </tr>
            """

        # Build debate timeline
        debate_timeline = ""
        for _i, msg in enumerate(debate_result.messages, 1):
            icon = {"researcher": "🔍", "critic": "🎯", "verifier": "✅"}.get(msg.role, "•")
            agent_color = {"researcher": "#3B82F6", "critic": "#F59E0B", "verifier": "#10B981"}.get(msg.role, "#6B7280")

            debate_timeline += f"""
            <div class="timeline-item">
                <div class="timeline-marker" style="background: {agent_color};">
                    <span>{icon}</span>
                </div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <strong>{msg.agent}</strong>
                        <span class="confidence-badge" style="background: {agent_color}20; color: {agent_color};">
                            {msg.confidence:.0f}%
                        </span>
                    </div>
                    <p>{msg.content}</p>
                </div>
            </div>
            """

        # Build issues list
        issues_html = ""
        if debate_result.issues:
            for issue in debate_result.issues:
                issues_html += f'<li class="issue-item">⚠️ {issue}</li>'
        else:
            issues_html = '<li class="success-item">✓ Aucun problème majeur détecté</li>'

        # Build results preview
        results_preview = ""
        all_results = [
            item for sr in orch_result.source_results for item in sr.results
        ][:10]

        for item in all_results:
            source = item.get("source", "unknown")
            title = item.get("title") or item.get("name") or item.get("nom") or "N/A"
            date = item.get("published_dt") or item.get("date") or ""

            results_preview += f"""
            <div class="result-card">
                <div class="result-source">{source}</div>
                <div class="result-title">{title[:60]}{'...' if len(str(title)) > 60 else ''}</div>
                <div class="result-date">{date}</div>
            </div>
            """

        # Theme styles
        if self.config.theme == "dark":
            bg_color = "#1a1a2e"
            card_bg = "#16213e"
            text_color = "#e8e8e8"
            text_muted = "#9ca3af"
            border_color = "#374151"
        else:
            bg_color = "#f3f4f6"
            card_bg = "#ffffff"
            text_color = "#1f2937"
            text_muted = "#6b7280"
            border_color = "#e5e7eb"

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rapport Multi-Source - {self.config.query}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif;
            background: {bg_color};
            color: {text_color};
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}

        /* Header */
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 3rem 2rem;
            border-radius: 1rem;
            margin-bottom: 2rem;
            color: white;
        }}

        .header h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}

        .header .meta {{
            opacity: 0.9;
            font-size: 0.9rem;
        }}

        /* Cards */
        .card {{
            background: {card_bg};
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid {border_color};
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid {border_color};
        }}

        .card-title {{
            font-size: 1.1rem;
            font-weight: 600;
        }}

        /* Confidence Score */
        .confidence-section {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .metric-card {{
            background: {card_bg};
            border-radius: 1rem;
            padding: 1.5rem;
            text-align: center;
            border: 1px solid {border_color};
        }}

        .metric-value {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}

        .metric-label {{
            color: {text_muted};
            font-size: 0.9rem;
        }}

        .confidence-ring {{
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: conic-gradient({conf_color} 0% {confidence}%, {border_color} {confidence}% 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1rem;
        }}

        .confidence-inner {{
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: {card_bg};
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.8rem;
            font-weight: 700;
            color: {conf_color};
        }}

        /* Table */
        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th, td {{
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid {border_color};
        }}

        th {{
            font-weight: 600;
            color: {text_muted};
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .error-cell {{
            color: {text_muted};
            font-size: 0.8rem;
        }}

        /* Timeline */
        .timeline {{
            position: relative;
            padding-left: 2rem;
        }}

        .timeline::before {{
            content: '';
            position: absolute;
            left: 0.75rem;
            top: 0;
            bottom: 0;
            width: 2px;
            background: {border_color};
        }}

        .timeline-item {{
            position: relative;
            padding-bottom: 1.5rem;
        }}

        .timeline-marker {{
            position: absolute;
            left: -2rem;
            width: 1.5rem;
            height: 1.5rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
        }}

        .timeline-header {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }}

        .confidence-badge {{
            padding: 0.2rem 0.5rem;
            border-radius: 1rem;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .timeline-content p {{
            color: {text_muted};
            font-size: 0.9rem;
        }}

        /* Issues */
        .issues-list {{
            list-style: none;
        }}

        .issue-item {{
            padding: 0.75rem 1rem;
            background: #FEF3C7;
            color: #92400E;
            border-radius: 0.5rem;
            margin-bottom: 0.5rem;
        }}

        .success-item {{
            padding: 0.75rem 1rem;
            background: #D1FAE5;
            color: #065F46;
            border-radius: 0.5rem;
        }}

        /* Results Preview */
        .results-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 1rem;
        }}

        .result-card {{
            background: {bg_color};
            padding: 1rem;
            border-radius: 0.5rem;
            border: 1px solid {border_color};
        }}

        .result-source {{
            font-size: 0.75rem;
            color: #667eea;
            font-weight: 600;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }}

        .result-title {{
            font-weight: 500;
            margin-bottom: 0.25rem;
        }}

        .result-date {{
            color: {text_muted};
            font-size: 0.8rem;
        }}

        /* Verdict */
        .verdict {{
            background: {conf_bg};
            color: {conf_color};
            padding: 1rem 1.5rem;
            border-radius: 0.75rem;
            font-weight: 600;
            text-align: center;
            margin-top: 1rem;
        }}

        /* Print styles */
        @media print {{
            body {{
                background: white;
                color: black;
            }}
            .header {{
                background: #667eea;
                -webkit-print-color-adjust: exact;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Rapport d'Analyse Multi-Source</h1>
            <div class="meta">
                Requête: <strong>{self.config.query}</strong> |
                Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} |
                Durée totale: {orch_result.total_duration_ms:.0f}ms
            </div>
        </div>

        <div class="confidence-section">
            <div class="metric-card">
                <div class="confidence-ring">
                    <div class="confidence-inner">{confidence:.0f}%</div>
                </div>
                <div class="metric-label">Score de Confiance</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{total_results}</div>
                <div class="metric-label">Résultats Totaux</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{successful_sources}/{total_sources}</div>
                <div class="metric-label">Sources Actives</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{orch_result.total_duration_ms:.0f}ms</div>
                <div class="metric-label">Temps de Réponse</div>
            </div>
        </div>

        <div class="verdict">{debate_result.verdict}</div>

        <div class="card" style="margin-top: 2rem;">
            <div class="card-header">
                <span class="card-title">📡 Sources de Données</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>Résultats</th>
                        <th>Temps</th>
                        <th>Statut</th>
                    </tr>
                </thead>
                <tbody>
                    {source_rows}
                </tbody>
            </table>
        </div>

        <div class="card">
            <div class="card-header">
                <span class="card-title">🔬 Validation Multi-Agent</span>
            </div>
            <div class="timeline">
                {debate_timeline}
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <span class="card-title">⚠️ Points d'Attention</span>
            </div>
            <ul class="issues-list">
                {issues_html}
            </ul>
        </div>

        <div class="card">
            <div class="card-header">
                <span class="card-title">📋 Aperçu des Résultats</span>
            </div>
            <div class="results-grid">
                {results_preview}
            </div>
        </div>

        <div style="text-align: center; color: {text_muted}; margin-top: 2rem; font-size: 0.85rem;">
            Rapport généré par Tawiza - Intelligence Territoriale<br>
            Multi-Source Orchestration + Multi-Agent Validation
        </div>
    </div>
</body>
</html>
"""
        report_path.write_text(html, encoding="utf-8")
        logger.info(f"Generated HTML report: {report_path}")
        return str(report_path)

    def generate_json_export(
        self,
        orch_result: OrchestratedResult,
        debate_result: DebateResult,
    ) -> str:
        """Export complete analysis data as JSON.

        Args:
            orch_result: Results from DataOrchestrator
            debate_result: Results from DebateSystem

        Returns:
            Path to generated JSON file
        """
        export_path = self.output_dir / "analyse_complete.json"

        data = {
            "meta": {
                "query": self.config.query,
                "generated_at": datetime.now().isoformat(),
                "total_duration_ms": orch_result.total_duration_ms,
            },
            "confidence": {
                "score": debate_result.final_confidence,
                "verdict": debate_result.verdict,
                "is_valid": debate_result.is_valid,
                "is_high_confidence": debate_result.is_high_confidence,
            },
            "sources": [
                {
                    "name": sr.source,
                    "results_count": len(sr.results) if sr.results else 0,
                    "duration_ms": sr.duration_ms,
                    "error": sr.error,
                }
                for sr in orch_result.source_results
            ],
            "debate": {
                "rounds": [
                    {
                        "agent": msg.agent,
                        "role": msg.role,
                        "confidence": msg.confidence,
                        "content": msg.content,
                        "issues": msg.issues,
                    }
                    for msg in debate_result.messages
                ],
                "final_issues": debate_result.issues,
            },
            "results": {
                "total": orch_result.total_results,
                "correlated_entities": len(orch_result.correlated_entities),
                "by_source": {
                    sr.source: sr.results
                    for sr in orch_result.source_results
                    if sr.results
                },
            },
        }

        export_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"Generated JSON export: {export_path}")
        return str(export_path)


    def generate_markdown_report(
        self,
        orch_result: OrchestratedResult,
        debate_result: DebateResult,
    ) -> str:
        """Generate clean Markdown report.

        Args:
            orch_result: Results from DataOrchestrator
            debate_result: Results from DebateSystem

        Returns:
            Path to generated Markdown file
        """
        report_path = self.output_dir / "rapport_multi_source.md"

        # Calculate metrics
        total_results = orch_result.total_results
        successful_sources = sum(1 for sr in orch_result.source_results if sr.results)
        total_sources = len(orch_result.source_results)
        confidence = debate_result.final_confidence

        # Confidence emoji
        if confidence >= 80:
            conf_emoji = "🟢"
        elif confidence >= 60:
            conf_emoji = "🟡"
        else:
            conf_emoji = "🔴"

        # Build source table
        source_table = "| Source | Résultats | Temps | Statut |\n"
        source_table += "|--------|-----------|-------|--------|\n"
        for sr in orch_result.source_results:
            status = "✅" if sr.results else "❌"
            count = len(sr.results) if sr.results else 0
            error = sr.error[:30] if sr.error else "-"
            source_table += f"| {sr.source} | {count} | {sr.duration_ms:.0f}ms | {status} {error} |\n"

        # Build debate section
        debate_section = ""
        for msg in debate_result.messages:
            icon = {"researcher": "🔍", "critic": "🎯", "verifier": "✅"}.get(msg.role, "•")
            debate_section += f"\n### {icon} {msg.agent} ({msg.confidence:.0f}%)\n\n"
            debate_section += f"{msg.content}\n"

        # Build issues
        issues_section = ""
        if debate_result.issues:
            for issue in debate_result.issues:
                issues_section += f"- ⚠️ {issue}\n"
        else:
            issues_section = "- ✅ Aucun problème majeur détecté\n"

        # Build results preview
        results_preview = ""
        all_results = [item for sr in orch_result.source_results for item in sr.results][:15]
        for item in all_results:
            source = item.get("source", "unknown")
            title = item.get("title") or item.get("name") or item.get("nom") or "N/A"
            siret = item.get("siret", "")
            date = item.get("published_dt") or item.get("date") or ""
            results_preview += f"- **[{source}]** {title[:60]}"
            if siret:
                results_preview += f" (SIRET: {siret})"
            if date:
                results_preview += f" - {date}"
            results_preview += "\n"

        md = f"""# 📊 Rapport d'Analyse Multi-Source

**Requête:** {self.config.query}
**Date:** {datetime.now().strftime('%d/%m/%Y à %H:%M')}
**Durée totale:** {orch_result.total_duration_ms:.0f}ms

---

## 📈 Résumé

| Métrique | Valeur |
|----------|--------|
| Score de confiance | {conf_emoji} **{confidence:.0f}%** |
| Résultats totaux | {total_results} |
| Sources actives | {successful_sources}/{total_sources} |

### Verdict

> {debate_result.verdict}

---

## 📡 Sources de Données

{source_table}

---

## 🔬 Validation Multi-Agent (LLM)

{debate_section}

---

## ⚠️ Points d'Attention

{issues_section}

---

## 📋 Aperçu des Résultats

{results_preview}

---

*Rapport généré par Tawiza - Intelligence Territoriale*
*Multi-Source Orchestration + LLM Debate Validation*
"""
        report_path.write_text(md, encoding="utf-8")
        logger.info(f"Generated Markdown report: {report_path}")
        return str(report_path)


async def generate_orchestrated_report(
    query: str,
    output_dir: str,
    orch_result: OrchestratedResult,
    debate_result: DebateResult,
    theme: str = "dark",
) -> dict[str, str]:
    """Convenience function to generate all report formats.

    Args:
        query: Original search query
        output_dir: Output directory
        orch_result: Orchestration results
        debate_result: Debate validation results
        theme: Report theme (dark/light)

    Returns:
        Dictionary mapping format to file path
    """
    config = ReportConfig(
        output_dir=output_dir,
        query=query,
        theme=theme,
    )
    generator = OrchestratedReportGenerator(config)

    return {
        "md": generator.generate_markdown_report(orch_result, debate_result),
        "html": generator.generate_html_report(orch_result, debate_result),
        "json": generator.generate_json_export(orch_result, debate_result),
    }
