#!/usr/bin/env python3
"""Scheduler Tawiza V2  -  Planification automatique des collectes et détections.

Utilise APScheduler pour orchestrer :
- Collecte BODACC + France Travail : toutes les 6h
- Collecte SIRENE + INSEE + OFGL : quotidienne à 6h
- Collecte DVF : hebdomadaire (dimanche 3h)
- Collecte Presse : toutes les 4h
- Détection micro-signaux : toutes les 6h (après collecte)
"""

import asyncio
import sys
from pathlib import Path

from loguru import logger

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")


async def job_collect_frequent():
    """Collecte fréquente : BODACC + France Travail."""
    from src.scripts.collect_all_v2 import run_full_collect

    logger.info("⏰ [SCHEDULER] Collecte fréquente")
    await run_full_collect(sources=["bodacc", "france_travail", "presse_locale"], days_back=7)


async def job_collect_daily():
    """Collecte quotidienne : SIRENE + INSEE + OFGL."""
    from src.scripts.collect_all_v2 import run_full_collect

    logger.info("⏰ [SCHEDULER] Collecte quotidienne")
    await run_full_collect(sources=["sirene", "insee", "ofgl"], days_back=30)


async def job_collect_weekly():
    """Collecte hebdomadaire : DVF."""
    from src.scripts.collect_all_v2 import run_full_collect

    logger.info("⏰ [SCHEDULER] Collecte hebdo DVF")
    await run_full_collect(sources=["dvf"], days_back=90)


async def job_detect():
    """Détection micro-signaux + temporel + alertes."""
    from src.scripts.detect_microsignals_v2 import run_detection
    from src.scripts.detect_temporal import detect_temporal_signals

    logger.info("⏰ [SCHEDULER] Détection micro-signaux")
    await run_detection(days_back=180, save=True)

    logger.info("⏰ [SCHEDULER] Détection temporelle")
    await detect_temporal_signals()

    logger.info("⏰ [SCHEDULER] Vérification alertes")
    from src.scripts.alert_telegram import send_alert

    await send_alert()


def setup_scheduler():
    """Configure et lance le scheduler."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler(timezone="Europe/Paris")

    # Collecte fréquente : 6h, 12h, 18h, 0h
    scheduler.add_job(
        job_collect_frequent,
        CronTrigger(hour="0,6,12,18", minute=0),
        id="collect_frequent",
        name="BODACC + FT + Presse",
        replace_existing=True,
    )

    # Collecte quotidienne : 6h15
    scheduler.add_job(
        job_collect_daily,
        CronTrigger(hour=6, minute=15),
        id="collect_daily",
        name="SIRENE + INSEE + OFGL",
        replace_existing=True,
    )

    # Collecte hebdomadaire : dimanche 3h
    scheduler.add_job(
        job_collect_weekly,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="collect_weekly",
        name="DVF hebdo",
        replace_existing=True,
    )

    # Détection : 7h et 19h (après les collectes)
    scheduler.add_job(
        job_detect,
        CronTrigger(hour="7,19", minute=0),
        id="detect_microsignals",
        name="Détection micro-signaux",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("✅ Scheduler démarré  -  4 jobs planifiés")

    for job in scheduler.get_jobs():
        logger.info(f"  📅 {job.name}: next run {job.next_run_time}")

    return scheduler


async def main():
    logger.info("🚀 Démarrage scheduler Tawiza V2")
    scheduler = setup_scheduler()

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("🛑 Scheduler arrêté")


if __name__ == "__main__":
    asyncio.run(main())
