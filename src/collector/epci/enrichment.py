"""
EPCI Enrichment — add code_epci to existing signals in DB.

Batch-updates signals that have code_commune but no code_epci.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from .referentiel import get_referentiel

logger = logging.getLogger(__name__)


async def add_epci_column(engine: AsyncEngine) -> None:
    """Add code_epci column to signals table if not exists."""
    async with engine.begin() as conn:
        await conn.execute(
            text("""
            ALTER TABLE signals ADD COLUMN IF NOT EXISTS code_epci VARCHAR(20);
        """)
        )
        await conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_signals_code_epci ON signals(code_epci);
        """)
        )
    logger.info("code_epci column ensured on signals table")


async def enrich_signals_with_epci(engine: AsyncEngine, batch_size: int = 5000) -> int:
    """
    Batch-enrich signals: resolve code_commune → code_epci.
    Returns number of signals updated.
    """
    ref = await get_referentiel()
    total_updated = 0

    async with engine.begin() as conn:
        # Get signals with commune but no EPCI
        result = await conn.execute(
            text("""
            SELECT id, code_commune FROM signals
            WHERE code_commune IS NOT NULL
              AND (code_epci IS NULL OR code_epci = '')
            LIMIT :limit
        """),
            {"limit": batch_size},
        )
        rows = result.fetchall()

        if not rows:
            logger.info("No signals to enrich with EPCI")
            return 0

        updates = []
        for row in rows:
            sig_id, code_commune = row[0], row[1]
            epci = ref.commune_to_epci(code_commune)
            if epci:
                updates.append({"sid": sig_id, "epci": epci})

        if updates:
            # Batch update
            for u in updates:
                await conn.execute(text("UPDATE signals SET code_epci = :epci WHERE id = :sid"), u)
            total_updated = len(updates)

    logger.info(f"Enriched {total_updated}/{len(rows)} signals with EPCI codes")
    return total_updated


async def enrich_all_signals(engine: AsyncEngine) -> int:
    """Run enrichment in batches until all signals are processed."""
    total = 0
    while True:
        batch = await enrich_signals_with_epci(engine, batch_size=5000)
        total += batch
        if batch < 5000:
            break
    return total
