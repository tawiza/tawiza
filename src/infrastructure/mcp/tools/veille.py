"""MCP Tools for Intelligent Veille - Automated Market Monitoring.

Provides LLM-enhanced alert filtering and monitoring tools for Cherry Studio.
"""

import json
from typing import Literal

from loguru import logger
from mcp.server.fastmcp import Context, FastMCP


def register_veille_tools(mcp: FastMCP) -> None:
    """Register veille (monitoring) tools on the MCP server."""

    @mcp.tool()
    async def tawiza_veille_scan(
        keywords: list[str] | None = None,
        sources: list[str] | None = None,
        min_priority: Literal["noise", "low", "medium", "high", "critical"] = "medium",
        limit: int = 20,
        ctx: Context = None,
    ) -> str:
        """Scan les sources de veille avec filtrage intelligent LLM.

        Interroge BODACC, BOAMP, GDELT et filtre les alertes par pertinence
        en utilisant un LLM pour scorer chaque alerte.

        Args:
            keywords: Mots-cles a surveiller (utilise watchlist si non fourni)
            sources: Sources a scanner (bodacc, boamp, gdelt). Defaut: toutes
            min_priority: Priorite minimum (noise, low, medium, high, critical)
            limit: Nombre max d'alertes a retourner

        Returns:
            JSON avec alertes scorees, triees par pertinence
        """
        from src.infrastructure.dashboard import DashboardDB
        from src.infrastructure.watcher import (
            AlertPriority,
            BoampPoller,
            BodaccPoller,
            GdeltPoller,
            WatcherStorage,
            create_alert_filter,
        )

        def notify(msg: str, progress: int = None):
            if ctx:
                try:
                    ctx.info(msg)
                    if progress is not None:
                        ctx.report_progress(progress, 100, msg)
                except Exception as e:
                    logger.debug(f"Failed to send notification: {e}")
                    pass

        notify("Demarrage scan de veille intelligent...", 0)

        # Initialize components
        db = DashboardDB()
        storage = WatcherStorage(db)
        alert_filter = create_alert_filter()

        # Get keywords
        if not keywords:
            watchlist = await storage.async_get_watchlist(active_only=True)
            keywords = []
            for item in watchlist:
                keywords.extend(item.get("keywords", []))
            keywords = list(set(keywords))
            notify(f"Mots-cles watchlist: {len(keywords)}")

        if not keywords:
            keywords = ["startup", "innovation", "IA", "numerique"]
            notify("Utilisation mots-cles par defaut")

        # Determine sources to poll
        sources_to_poll = sources or ["bodacc", "boamp", "gdelt"]
        pollers = {
            "bodacc": BodaccPoller(),
            "boamp": BoampPoller(),
            "gdelt": GdeltPoller(),
        }

        notify(f"Sources: {', '.join(sources_to_poll)}", 10)

        # Poll each source
        all_alerts = []
        for i, src in enumerate(sources_to_poll):
            if src not in pollers:
                continue

            progress = 10 + (40 * (i + 1) / len(sources_to_poll))
            notify(f"[{src.upper()}] Interrogation...", int(progress))

            poller = pollers[src]
            alerts, error = await poller.safe_poll(keywords)

            if error:
                notify(f"[{src.upper()}] Erreur: {error}")
            else:
                all_alerts.extend(alerts)
                notify(f"[{src.upper()}] {len(alerts)} alertes trouvees")

        notify(f"Total: {len(all_alerts)} alertes brutes", 50)

        if not all_alerts:
            return json.dumps(
                {
                    "success": True,
                    "message": "Aucune nouvelle alerte trouvee",
                    "alerts": [],
                    "summary": {"total": 0},
                },
                ensure_ascii=False,
            )

        # Filter with LLM
        notify("[LLM] Filtrage intelligent des alertes...", 55)

        priority_map = {
            "noise": AlertPriority.NOISE,
            "low": AlertPriority.LOW,
            "medium": AlertPriority.MEDIUM,
            "high": AlertPriority.HIGH,
            "critical": AlertPriority.CRITICAL,
        }
        min_prio = priority_map.get(min_priority, AlertPriority.MEDIUM)

        scored_alerts = await alert_filter.filter_alerts(
            alerts=all_alerts[:50],  # Limit to avoid timeout
            keywords=keywords,
            min_priority=min_prio,
            batch_size=5,
        )

        notify(f"[LLM] {len(scored_alerts)} alertes pertinentes", 85)

        # Generate summary
        summary = await alert_filter.get_priority_summary(scored_alerts)

        notify(f"Scan termine: {summary['total']} alertes", 100)

        # Build response
        result = {
            "success": True,
            "alerts": [sa.to_dict() for sa in scored_alerts[:limit]],
            "summary": summary,
            "keywords_used": keywords,
            "sources_scanned": sources_to_poll,
        }

        return json.dumps(result, ensure_ascii=False, indent=2, default=str)

    @mcp.tool()
    async def tawiza_veille_digest(
        period: Literal["today", "week", "month"] = "today",
        ctx: Context = None,
    ) -> str:
        """Génère un digest des alertes récentes avec analyse LLM.

        Synthetise les alertes de la periode et produit un rapport
        avec tendances et recommandations.

        Args:
            period: Periode a analyser (today, week, month)

        Returns:
            Digest Markdown avec resume, tendances et alertes prioritaires
        """
        from datetime import datetime, timedelta

        from src.infrastructure.dashboard import DashboardDB
        from src.infrastructure.watcher import AlertPriority, create_alert_filter

        def notify(msg: str, progress: int = None):
            if ctx:
                try:
                    ctx.info(msg)
                    if progress is not None:
                        ctx.report_progress(progress, 100, msg)
                except Exception as e:
                    logger.debug(f"Failed to send notification: {e}")
                    pass

        notify("Generation du digest de veille...", 0)

        # Calculate date range
        now = datetime.now()
        if period == "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_label = "aujourd'hui"
        elif period == "week":
            start_date = now - timedelta(days=7)
            period_label = "7 derniers jours"
        else:
            start_date = now - timedelta(days=30)
            period_label = "30 derniers jours"

        notify(f"Periode: {period_label}", 10)

        # Get alerts from database
        db = DashboardDB()
        cursor = db.conn.execute(
            """
            SELECT id, source, type, title, content, url, detected_at, read
            FROM alerts
            WHERE detected_at >= ?
            ORDER BY detected_at DESC
            """,
            (start_date.isoformat(),),
        )
        rows = cursor.fetchall()
        alerts_data = [dict(row) for row in rows]

        notify(f"{len(alerts_data)} alertes trouvees", 20)

        if not alerts_data:
            digest = f"""# Digest de Veille - {period_label}

## Resume
Aucune nouvelle alerte detectee sur cette periode.

## Recommandations
- Verifier les mots-cles de la watchlist
- Elargir les criteres de surveillance
"""
            return json.dumps(
                {
                    "success": True,
                    "digest_md": digest,
                    "alerts_count": 0,
                    "period": period,
                },
                ensure_ascii=False,
            )

        # Convert to Alert objects and score
        from src.infrastructure.dashboard import Alert
        from src.infrastructure.watcher import WatcherStorage

        storage = WatcherStorage(db)
        watchlist = await storage.async_get_watchlist(active_only=True)
        keywords = []
        for item in watchlist:
            keywords.extend(item.get("keywords", []))
        keywords = list(set(keywords)) or ["startup", "innovation", "entreprise"]

        alerts = []
        for data in alerts_data:
            try:
                alerts.append(Alert.from_dict(data))
            except Exception as e:
                logger.debug(f"Failed to convert alert data: {e}")
                continue

        notify("[LLM] Analyse des alertes...", 30)

        alert_filter = create_alert_filter()
        scored_alerts = await alert_filter.filter_alerts(
            alerts=alerts[:30],  # Limit for speed
            keywords=keywords,
            min_priority=AlertPriority.LOW,
        )

        notify(f"{len(scored_alerts)} alertes analysees", 70)

        summary = await alert_filter.get_priority_summary(scored_alerts)

        # Generate digest Markdown
        notify("Generation du digest...", 80)

        digest = f"""# Digest de Veille - {period_label}

*Généré le {now.strftime("%d/%m/%Y à %H:%M")}*

## Resume Executif

| Metrique | Valeur |
|----------|--------|
| Alertes totales | **{len(alerts_data)}** |
| Alertes analysees | **{len(scored_alerts)}** |
| Score moyen | **{summary["avg_score"]:.0f}/100** |
| Critiques | **{summary["by_priority"].get("critical", 0)}** |
| Hautes | **{summary["by_priority"].get("high", 0)}** |

## Distribution par Priorite

| Priorite | Nombre |
|----------|--------|
| Critical | {summary["by_priority"].get("critical", 0)} |
| High | {summary["by_priority"].get("high", 0)} |
| Medium | {summary["by_priority"].get("medium", 0)} |
| Low | {summary["by_priority"].get("low", 0)} |

"""

        if summary["critical_alerts"]:
            digest += "## Alertes Critiques\n\n"
            for ca in summary["critical_alerts"][:5]:
                digest += f"- **{ca['title'][:60]}...** (Score: {ca['score']})\n"
                digest += f"  - {ca['reason']}\n"
                if ca.get("action"):
                    digest += f"  - Action: {ca['action']}\n"
                digest += "\n"

        if summary["high_alerts"]:
            digest += "## Alertes Importantes\n\n"
            for ha in summary["high_alerts"][:5]:
                digest += f"- **{ha['title'][:60]}...** (Score: {ha['score']})\n"
                digest += f"  - {ha['reason']}\n\n"

        # Source breakdown
        sources = {}
        for data in alerts_data:
            src = data.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1

        digest += "## Repartition par Source\n\n"
        digest += "| Source | Alertes |\n|--------|--------|\n"
        for src, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            digest += f"| {src.upper()} | {count} |\n"

        digest += f"""
## Recommandations

1. **Traiter en priorite** les {summary["by_priority"].get("critical", 0)} alertes critiques
2. **Examiner** les {summary["by_priority"].get("high", 0)} alertes importantes
3. **Surveiller** les tendances sur les {summary["by_priority"].get("medium", 0)} alertes moyennes

---
*Mots-cles surveilles: {", ".join(keywords[:10])}*
"""

        notify("Digest généré", 100)

        return json.dumps(
            {
                "success": True,
                "digest_md": digest,
                "alerts_count": len(alerts_data),
                "scored_count": len(scored_alerts),
                "summary": summary,
                "period": period,
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def tawiza_veille_configure(
        action: Literal["add", "remove", "list", "status"],
        keywords: list[str] | None = None,
        sources: list[str] | None = None,
        ctx: Context = None,
    ) -> str:
        """Configure la veille automatique.

        Gere les mots-cles surveilles et les sources actives.

        Args:
            action: Action a effectuer
                - add: Ajouter des mots-cles a surveiller
                - remove: Retirer des mots-cles
                - list: Lister la configuration actuelle
                - status: Statut du daemon de veille
            keywords: Mots-cles (pour add/remove)
            sources: Sources a configurer (bodacc, boamp, gdelt)

        Returns:
            Configuration actuelle ou confirmation de modification
        """
        from src.infrastructure.dashboard import DashboardDB
        from src.infrastructure.watcher import WatcherStorage

        db = DashboardDB()
        storage = WatcherStorage(db)

        if action == "list":
            watchlist = await storage.async_get_watchlist(active_only=True)
            all_keywords = set()
            all_sources = set()
            for item in watchlist:
                all_keywords.update(item.get("keywords", []))
                all_sources.update(item.get("sources", []))

            poll_status = db.get_poll_status()
            next_polls = storage.get_next_poll_times()

            return json.dumps(
                {
                    "success": True,
                    "watchlist": {
                        "keywords": sorted(all_keywords),
                        "sources": sorted(all_sources),
                        "items_count": len(watchlist),
                    },
                    "poll_status": {
                        src: {
                            "last_poll": poll_status.get(src, {}).get("last_poll"),
                            "next_poll": next_polls.get(src, "unknown"),
                            "polls_count": poll_status.get(src, {}).get("polls_count", 0),
                        }
                        for src in ["bodacc", "boamp", "gdelt"]
                    },
                },
                ensure_ascii=False,
                indent=2,
            )

        elif action == "add":
            if not keywords:
                return json.dumps(
                    {
                        "success": False,
                        "error": "keywords requis pour action 'add'",
                    },
                    ensure_ascii=False,
                )

            sources = sources or ["bodacc", "boamp", "gdelt"]
            item_id = await db.async_add_watchlist_item(keywords, sources)

            if ctx:
                ctx.info(f"[Veille] Ajoute: {', '.join(keywords)}")

            return json.dumps(
                {
                    "success": True,
                    "action": "add",
                    "id": item_id,
                    "keywords": keywords,
                    "sources": sources,
                    "message": f"Mots-cles ajoutes: {', '.join(keywords)}",
                },
                ensure_ascii=False,
            )

        elif action == "remove":
            if not keywords:
                return json.dumps(
                    {
                        "success": False,
                        "error": "keywords requis pour action 'remove'",
                    },
                    ensure_ascii=False,
                )

            count = db.remove_watchlist_keywords(keywords)

            if ctx:
                ctx.info(f"[Veille] Retire: {', '.join(keywords)}")

            return json.dumps(
                {
                    "success": True,
                    "action": "remove",
                    "removed_count": count,
                    "keywords": keywords,
                    "message": f"{count} entrees desactivees",
                },
                ensure_ascii=False,
            )

        elif action == "status":
            poll_status = db.get_poll_status()
            alerts_count = db.get_alerts_count()

            return json.dumps(
                {
                    "success": True,
                    "daemon_status": "configured",
                    "poll_status": poll_status,
                    "alerts": alerts_count,
                },
                ensure_ascii=False,
                indent=2,
            )

        else:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Action inconnue: {action}",
                },
                ensure_ascii=False,
            )

    @mcp.tool()
    async def tawiza_veille_alert_detail(
        alert_id: int,
        ctx: Context = None,
    ) -> str:
        """Récupère le détail complet d'une alerte avec analyse LLM.

        Analyse l'alerte en profondeur et génère des recommandations
        d'actions spécifiques.

        Args:
            alert_id: ID de l'alerte à analyser

        Returns:
            Detail complet avec analyse et recommandations
        """
        from src.infrastructure.dashboard import Alert, DashboardDB
        from src.infrastructure.watcher import WatcherStorage, create_alert_filter

        db = DashboardDB()

        # Get alert
        alert_dict = db.get_alert_detail(alert_id)
        if not alert_dict:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Alerte {alert_id} non trouvee",
                },
                ensure_ascii=False,
            )

        if ctx:
            ctx.info(f"[Veille] Analyse alerte {alert_id}...")

        # Get keywords for context
        storage = WatcherStorage(db)
        watchlist = await storage.async_get_watchlist(active_only=True)
        keywords = []
        for item in watchlist:
            keywords.extend(item.get("keywords", []))
        keywords = list(set(keywords)) or ["entreprise", "marche"]

        # Score with LLM
        alert = Alert.from_dict(alert_dict)
        alert_filter = create_alert_filter()
        scored = await alert_filter.score_alert(alert, keywords)

        if ctx:
            ctx.info(f"[Veille] Score: {scored.score}/100 ({scored.priority.value})")

        return json.dumps(
            {
                "success": True,
                "alert": scored.to_dict(),
                "analysis": {
                    "score": scored.score,
                    "priority": scored.priority.value,
                    "relevance": scored.relevance_reason,
                    "impact": scored.business_impact,
                    "recommended_action": scored.recommended_action,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
