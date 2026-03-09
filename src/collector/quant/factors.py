"""Alpha factors calculation for territorial health assessment.

Calculates normalized alpha factors for each department using collector database.
Factors inspired by quantitative finance adapted to territorial intelligence.
"""

import os
from typing import Dict, Optional, Any
import asyncio
from collections import defaultdict
import numpy as np
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from .population import get_department_population, normalize_per_10k


class AlphaFactorsCalculator:
    """Calculator for territorial alpha factors."""
    
    def __init__(self, database_url: str):
        """Initialize with database connection.
        
        Args:
            database_url: PostgreSQL URL for collector database
        """
        self.database_url = database_url
        self._engine = create_async_engine(database_url, echo=False)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
    
    async def compute_all_factors(self) -> Dict[str, Dict[str, Optional[float]]]:
        """Compute all alpha factors for all departments.
        
        Returns:
            Dict mapping department code -> factor name -> value
        """
        logger.info("Computing alpha factors for all departments")
        
        # Get base data by department
        dept_data = await self._collect_department_data()
        
        # Calculate each factor
        factors = {}
        for dept in dept_data.keys():
            factors[dept] = {
                "factor_sante_entreprises": self._calculate_sante_entreprises(dept_data[dept]),
                "factor_tension_emploi": self._calculate_tension_emploi(dept_data[dept]),
                "factor_dynamisme_immo": self._calculate_dynamisme_immo(dept_data[dept]),
                "factor_construction": self._calculate_construction(dept_data[dept]),
                "factor_declin_ratio": self._calculate_declin_ratio(dept_data[dept]),
                "factor_presse_sentiment": self._calculate_presse_sentiment(dept_data[dept]),
            }
        
        logger.info(f"Computed factors for {len(factors)} departments")
        return factors
    
    async def _collect_department_data(self) -> Dict[str, Dict[str, Any]]:
        """Collect raw data by department from signals table.
        
        Returns:
            Dict mapping department code -> data metrics
        """
        logger.info("Collecting department data from signals table")
        
        async with self._session_factory() as session:
            # Query all signals grouped by department
            query = text("""
                SELECT 
                    code_dept,
                    source,
                    metric_name,
                    COUNT(*) as count,
                    AVG(metric_value) as avg_value,
                    SUM(metric_value) as sum_value,
                    MIN(metric_value) as min_value,
                    MAX(metric_value) as max_value
                FROM signals 
                WHERE code_dept IS NOT NULL 
                GROUP BY code_dept, source, metric_name
                ORDER BY code_dept
            """)
            
            result = await session.execute(query)
            rows = result.fetchall()
        
        # Organize data by department
        dept_data = defaultdict(lambda: defaultdict(dict))
        
        for row in rows:
            dept = row.code_dept
            source = row.source
            metric = row.metric_name
            
            dept_data[dept][f"{source}_{metric}"] = {
                "count": row.count,
                "avg": row.avg_value,
                "sum": row.sum_value,
                "min": row.min_value,
                "max": row.max_value
            }
        
        logger.info(f"Collected data for {len(dept_data)} departments")
        return dict(dept_data)
    
    def _calculate_sante_entreprises(self, dept_data: Dict[str, Any]) -> Optional[float]:
        """Calculate company health factor.
        
        Formula: creations_SIRENE / (liquidations_BODACC + 1)
        """
        creations = 0
        liquidations = 0
        
        # Count SIRENE creations
        for key, data in dept_data.items():
            if "sirene_" in key and ("creation" in key.lower() or "ouverture" in key.lower()):
                creations += data.get("count", 0)
        
        # Count BODACC liquidations  
        for key, data in dept_data.items():
            if "bodacc_" in key and ("liquidation" in key.lower() or "fermeture" in key.lower()):
                liquidations += data.get("count", 0)
        
        if creations == 0:
            return None
            
        factor = creations / (liquidations + 1)
        logger.debug(f"Sante entreprises: {creations} creations / ({liquidations} + 1) = {factor:.3f}")
        return factor
    
    def _calculate_tension_emploi(self, dept_data: Dict[str, Any]) -> Optional[float]:
        """Calculate employment tension factor.
        
        Formula: offres_FT / nb_entreprises_SIRENE
        """
        offres = 0
        entreprises = 0
        
        # Count France Travail job offers
        for key, data in dept_data.items():
            if "france_travail_" in key or "ft_" in key:
                offres += data.get("count", 0)
        
        # Count active companies from SIRENE
        for key, data in dept_data.items():
            if "sirene_" in key and ("actif" in key.lower() or "active" in key.lower()):
                entreprises += data.get("count", 0)
        
        if entreprises == 0:
            return None
            
        factor = offres / entreprises
        logger.debug(f"Tension emploi: {offres} offres / {entreprises} entreprises = {factor:.3f}")
        return factor
    
    def _calculate_dynamisme_immo(self, dept_data: Dict[str, Any]) -> Optional[float]:
        """Calculate real estate dynamism factor.
        
        Formula: (prix_m2_DVF * nb_transactions_DVF) / population * 10000
        """
        prix_total = 0
        nb_transactions = 0
        
        # Sum DVF transaction values and count
        for key, data in dept_data.items():
            if "dvf_" in key:
                if "prix" in key.lower() or "valeur" in key.lower():
                    prix_total += data.get("sum", 0)
                nb_transactions += data.get("count", 0)
        
        if nb_transactions == 0:
            return None
            
        # Calculate average price per m²
        prix_m2_moyen = prix_total / nb_transactions if nb_transactions > 0 else 0
        
        # Volume factor (price * transactions)
        volume = prix_m2_moyen * nb_transactions
        
        logger.debug(f"Dynamisme immo: prix_moyen={prix_m2_moyen:.0f}, transactions={nb_transactions}, volume={volume:.0f}")
        return volume  # Will be normalized by population later
    
    def _calculate_construction(self, dept_data: Dict[str, Any]) -> Optional[float]:
        """Calculate construction activity factor.
        
        Formula: logements_autorises_Sitadel / population * 10000
        """
        logements = 0
        
        # Count Sitadel permits
        for key, data in dept_data.items():
            if "sitadel_" in key and ("logement" in key.lower() or "autorisation" in key.lower()):
                logements += data.get("count", 0)
        
        if logements == 0:
            return None
            
        logger.debug(f"Construction: {logements} logements autorisés")
        return logements  # Will be normalized by population later
    
    def _calculate_declin_ratio(self, dept_data: Dict[str, Any]) -> Optional[float]:
        """Calculate decline ratio factor.
        
        Formula: liquidations_BODACC / (creations_SIRENE + 1)
        Inverse of sante_entreprises factor.
        """
        creations = 0
        liquidations = 0
        
        # Count SIRENE creations
        for key, data in dept_data.items():
            if "sirene_" in key and ("creation" in key.lower() or "ouverture" in key.lower()):
                creations += data.get("count", 0)
        
        # Count BODACC liquidations
        for key, data in dept_data.items():
            if "bodacc_" in key and ("liquidation" in key.lower() or "fermeture" in key.lower()):
                liquidations += data.get("count", 0)
        
        if liquidations == 0:
            return 0.0  # No decline if no liquidations
            
        factor = liquidations / (creations + 1)
        logger.debug(f"Decline ratio: {liquidations} liquidations / ({creations} + 1) = {factor:.3f}")
        return factor
    
    def _calculate_presse_sentiment(self, dept_data: Dict[str, Any]) -> Optional[float]:
        """Calculate press sentiment factor.
        
        Formula: (positif_presse - negatif_presse) / total_presse
        """
        positif = 0
        negatif = 0
        total = 0
        
        # Count press sentiment signals
        for key, data in dept_data.items():
            if "presse" in key.lower():
                count = data.get("count", 0)
                total += count
                
                if "positif" in key.lower() or "positive" in key.lower():
                    positif += count
                elif "negatif" in key.lower() or "negative" in key.lower():
                    negatif += count
        
        if total == 0:
            return None
            
        sentiment = (positif - negatif) / total
        logger.debug(f"Press sentiment: ({positif} - {negatif}) / {total} = {sentiment:.3f}")
        return sentiment


async def compute_normalized_factors(database_url: str) -> Dict[str, Dict[str, Optional[float]]]:
    """Compute all normalized alpha factors.
    
    Args:
        database_url: PostgreSQL connection URL
        
    Returns:
        Dict mapping department -> factor_name -> normalized_value
    """
    calculator = AlphaFactorsCalculator(database_url)
    
    # Get raw factors
    raw_factors = await calculator.compute_all_factors()
    
    # Normalize factors that need population adjustment
    normalized_factors = {}
    
    for dept, factors in raw_factors.items():
        normalized_factors[dept] = {}
        
        for factor_name, value in factors.items():
            if value is None:
                normalized_factors[dept][factor_name] = None
                continue
                
            # These factors need population normalization
            if factor_name in ["factor_dynamisme_immo", "factor_construction"]:
                normalized_value = normalize_per_10k(value, dept)
                normalized_factors[dept][factor_name] = normalized_value
            else:
                # Already normalized ratios
                normalized_factors[dept][factor_name] = value
    
    return normalized_factors


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        database_url = sys.argv[1]
    else:
        database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost:5433/tawiza_signals")
    
    # Test the factors calculation
    factors = asyncio.run(compute_normalized_factors(database_url))
    
    print(f"Computed factors for {len(factors)} departments")
    
    # Show top 5 departments by number of factors available
    dept_scores = [(dept, sum(1 for v in data.values() if v is not None)) 
                   for dept, data in factors.items()]
    dept_scores.sort(key=lambda x: x[1], reverse=True)
    
    print("\nTop departments by data availability:")
    for dept, score in dept_scores[:5]:
        print(f"  {dept}: {score}/6 factors available")
        for factor, value in factors[dept].items():
            if value is not None:
                print(f"    {factor}: {value:.3f}")
        print()