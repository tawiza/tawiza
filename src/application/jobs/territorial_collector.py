"""
Territorial Collector Job - Collecte quotidienne des métriques territoriales.

Parcourt tous les départements français et stocke les métriques.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from loguru import logger

from src.infrastructure.persistence.territorial_history import (
    HistoricalMetrics,
    get_history_store,
)


# Liste des 101 départements français (métropole + DOM)
DEPARTEMENTS = {
    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes", "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes",
    "09": "Ariège", "10": "Aube", "11": "Aude", "12": "Aveyron",
    "13": "Bouches-du-Rhône", "14": "Calvados", "15": "Cantal", "16": "Charente",
    "17": "Charente-Maritime", "18": "Cher", "19": "Corrèze", "21": "Côte-d'Or",
    "22": "Côtes-d'Armor", "23": "Creuse", "24": "Dordogne", "25": "Doubs",
    "26": "Drôme", "27": "Eure", "28": "Eure-et-Loir", "29": "Finistère",
    "2A": "Corse-du-Sud", "2B": "Haute-Corse",
    "30": "Gard", "31": "Haute-Garonne", "32": "Gers", "33": "Gironde",
    "34": "Hérault", "35": "Ille-et-Vilaine", "36": "Indre", "37": "Indre-et-Loire",
    "38": "Isère", "39": "Jura", "40": "Landes", "41": "Loir-et-Cher",
    "42": "Loire", "43": "Haute-Loire", "44": "Loire-Atlantique", "45": "Loiret",
    "46": "Lot", "47": "Lot-et-Garonne", "48": "Lozère", "49": "Maine-et-Loire",
    "50": "Manche", "51": "Marne", "52": "Haute-Marne", "53": "Mayenne",
    "54": "Meurthe-et-Moselle", "55": "Meuse", "56": "Morbihan", "57": "Moselle",
    "58": "Nièvre", "59": "Nord", "60": "Oise", "61": "Orne",
    "62": "Pas-de-Calais", "63": "Puy-de-Dôme", "64": "Pyrénées-Atlantiques",
    "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales", "67": "Bas-Rhin",
    "68": "Haut-Rhin", "69": "Rhône", "70": "Haute-Saône", "71": "Saône-et-Loire",
    "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie", "75": "Paris",
    "76": "Seine-Maritime", "77": "Seine-et-Marne", "78": "Yvelines",
    "79": "Deux-Sèvres", "80": "Somme", "81": "Tarn", "82": "Tarn-et-Garonne",
    "83": "Var", "84": "Vaucluse", "85": "Vendée", "86": "Vienne",
    "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne", "90": "Territoire de Belfort",
    "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne", "95": "Val-d'Oise",
    # DOM
    "971": "Guadeloupe", "972": "Martinique", "973": "Guyane",
    "974": "La Réunion", "976": "Mayotte",
}


async def collect_all_departments(
    batch_size: int = 10,
    delay_between_batches: float = 2.0,
) -> dict[str, Any]:
    """
    Collecte les métriques de tous les départements.
    
    Args:
        batch_size: Nombre de départements à traiter en parallèle
        delay_between_batches: Délai entre les batches (rate limiting)
    
    Returns:
        Résumé de la collecte
    """
    from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter
    from src.infrastructure.datasources.adapters.sirene import SireneAdapter
    from src.infrastructure.agents.tajine.territorial.metrics_collector import TerritorialMetricsCollector
    
    # Initialiser les adaptateurs
    try:
        from src.infrastructure.datasources.adapters.france_travail import FranceTravailAdapter
        ft_adapter = FranceTravailAdapter()
        if not ft_adapter.has_credentials:
            ft_adapter = None
    except Exception:
        ft_adapter = None
    
    try:
        from src.infrastructure.datasources.adapters.insee_local import INSEELocalAdapter
        insee_adapter = INSEELocalAdapter()
        if not insee_adapter._client_id:
            insee_adapter = None
    except Exception:
        insee_adapter = None
    
    try:
        from src.infrastructure.datasources.adapters.dvf import DVFAdapter
        dvf_adapter = DVFAdapter()
    except Exception:
        dvf_adapter = None
    
    collector = TerritorialMetricsCollector(
        sirene_adapter=SireneAdapter(),
        bodacc_adapter=BodaccAdapter(),
        france_travail_adapter=ft_adapter,
        insee_adapter=insee_adapter,
        dvf_adapter=dvf_adapter,
    )
    
    store = get_history_store()
    now = datetime.utcnow()
    
    results = {
        "started_at": now.isoformat(),
        "success": 0,
        "failed": 0,
        "errors": [],
    }
    
    # Déterminer les sources utilisées
    sources_used = ["BODACC", "SIRENE"]
    if ft_adapter:
        sources_used.append("France Travail")
    if insee_adapter:
        sources_used.append("INSEE")
    if dvf_adapter:
        sources_used.append("DVF")
    
    logger.info(f"Starting territorial collection for {len(DEPARTEMENTS)} departments")
    logger.info(f"Sources: {', '.join(sources_used)}")
    
    # Traiter par batches
    dept_list = list(DEPARTEMENTS.items())
    
    for i in range(0, len(dept_list), batch_size):
        batch = dept_list[i:i + batch_size]
        
        # Collecter en parallèle
        tasks = []
        for code, name in batch:
            tasks.append(_collect_one(collector, store, code, name, now, sources_used))
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for (code, name), result in zip(batch, batch_results):
            if isinstance(result, Exception):
                results["failed"] += 1
                results["errors"].append({"code": code, "error": str(result)})
                logger.error(f"Failed to collect {code} ({name}): {result}")
            elif result:
                results["success"] += 1
            else:
                results["failed"] += 1
        
        # Rate limiting
        if i + batch_size < len(dept_list):
            await asyncio.sleep(delay_between_batches)
        
        # Log progress
        progress = min(i + batch_size, len(dept_list))
        logger.info(f"Progress: {progress}/{len(dept_list)} departments")
    
    results["finished_at"] = datetime.utcnow().isoformat()
    results["duration_seconds"] = (
        datetime.fromisoformat(results["finished_at"]) - 
        datetime.fromisoformat(results["started_at"])
    ).total_seconds()
    
    logger.info(
        f"Collection complete: {results['success']} success, "
        f"{results['failed']} failed in {results['duration_seconds']:.1f}s"
    )
    
    return results


async def _collect_one(
    collector,
    store,
    code: str,
    name: str,
    collected_at: datetime,
    sources_used: list[str],
) -> bool:
    """Collecte et sauvegarde les métriques d'un département."""
    try:
        metrics = await collector.collect_metrics(code, name, period_months=1)
        
        historical = HistoricalMetrics(
            territory_code=code,
            territory_name=name,
            collected_at=collected_at,
            creations=metrics.creations_count,
            closures=metrics.closures_count,
            procedures=metrics.collective_procedures_count,
            modifications=metrics.modifications_count,
            job_offers=metrics.job_offers_count,
            unemployment_rate=metrics.unemployment_rate,
            real_estate_tx=metrics.real_estate_transactions,
            avg_price_sqm=metrics.avg_price_sqm,
            population=metrics.population,
            vitality_index=metrics.vitality_index,
            net_creation=metrics.net_creation,
            sources_used=sources_used,
        )
        
        return store.save_metrics(historical)
        
    except Exception as e:
        logger.error(f"Error collecting {code}: {e}")
        raise


async def collect_selected_departments(
    codes: list[str],
) -> dict[str, Any]:
    """Collecte uniquement les départements spécifiés."""
    from src.infrastructure.datasources.adapters.bodacc import BodaccAdapter
    from src.infrastructure.datasources.adapters.sirene import SireneAdapter
    from src.infrastructure.agents.tajine.territorial.metrics_collector import TerritorialMetricsCollector
    
    collector = TerritorialMetricsCollector(
        sirene_adapter=SireneAdapter(),
        bodacc_adapter=BodaccAdapter(),
    )
    
    store = get_history_store()
    now = datetime.utcnow()
    
    results = {"success": 0, "failed": 0}
    
    for code in codes:
        name = DEPARTEMENTS.get(code, f"Département {code}")
        try:
            metrics = await collector.collect_metrics(code, name, period_months=1)
            
            historical = HistoricalMetrics(
                territory_code=code,
                territory_name=name,
                collected_at=now,
                creations=metrics.creations_count,
                closures=metrics.closures_count,
                procedures=metrics.collective_procedures_count,
                modifications=metrics.modifications_count,
                job_offers=metrics.job_offers_count,
                unemployment_rate=metrics.unemployment_rate,
                real_estate_tx=metrics.real_estate_transactions,
                avg_price_sqm=metrics.avg_price_sqm,
                population=metrics.population,
                vitality_index=metrics.vitality_index,
                net_creation=metrics.net_creation,
                sources_used=["BODACC", "SIRENE"],
            )
            
            if store.save_metrics(historical):
                results["success"] += 1
            else:
                results["failed"] += 1
                
        except Exception as e:
            logger.error(f"Failed to collect {code}: {e}")
            results["failed"] += 1
    
    return results


# CLI pour test manuel
if __name__ == "__main__":
    import sys
    
    async def main():
        if len(sys.argv) > 1 and sys.argv[1] == "--all":
            print("Collecting ALL departments...")
            results = await collect_all_departments(batch_size=5)
        else:
            # Par défaut, collecter quelques départements de test
            print("Collecting test departments (75, 69, 13, 33, 59)...")
            results = await collect_selected_departments(["75", "69", "13", "33", "59"])
        
        print(f"\nResults: {results}")
    
    asyncio.run(main())
