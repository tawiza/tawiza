#!/usr/bin/env python3
"""
Script de collecte territoriale - à exécuter quotidiennement via cron.

Usage:
    python scripts/collect_territorial.py           # 5 départements test
    python scripts/collect_territorial.py --all     # Tous les départements
    python scripts/collect_territorial.py --top20   # Top 20 départements
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le chemin du projet
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.application.jobs.territorial_collector import (
    collect_all_departments,
    collect_selected_departments,
)

# Top 20 départements par population/importance
TOP_20_DEPTS = [
    "75",
    "13",
    "69",
    "59",
    "33",  # Paris, BdR, Rhône, Nord, Gironde
    "92",
    "93",
    "94",
    "77",
    "78",  # Île-de-France
    "31",
    "44",
    "34",
    "06",
    "67",  # Toulouse, Nantes, Montpellier, Nice, Strasbourg
    "38",
    "76",
    "35",
    "62",
    "83",  # Isère, Seine-Maritime, Ille-et-Vilaine, PdC, Var
]


async def main():
    if "--all" in sys.argv:
        print("🚀 Collecting ALL 101 departments...")
        results = await collect_all_departments(batch_size=10, delay_between_batches=3.0)
    elif "--top20" in sys.argv:
        print("📊 Collecting TOP 20 departments...")
        results = await collect_selected_departments(TOP_20_DEPTS)
    else:
        print("🧪 Test mode: collecting 5 departments...")
        results = await collect_selected_departments(["75", "69", "13", "33", "59"])

    print(f"\n✅ Results: {results['success']} success, {results['failed']} failed")

    if results.get("errors"):
        print(f"⚠️ Errors: {results['errors'][:5]}")


if __name__ == "__main__":
    asyncio.run(main())
