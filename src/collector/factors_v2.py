"""
Territorial Alpha Factors Calculator - Phase 2 Algorithm Tawiza-V2 (Version Corrigée)

Calculates normalized alpha factors for territorial health assessment.
Inspired by quantitative finance alpha factors adapted to territorial intelligence.

Corrections apportées:
- Remplacement du scoring min-max par percentile ranking
- Gestion des valeurs manquantes (NaN au lieu de 0)
- Winsorization des outliers extrêmes
- Indicateur de confiance par source
- Meilleure intégration des données PostgreSQL
"""

import asyncio
import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from loguru import logger
import psycopg2


@dataclass
class SourceDataAvailability:
    """Disponibilité des données par source."""
    sirene_creations: bool = False
    bodacc_liquidations: bool = False
    france_travail_offers: bool = False
    dvf_transactions: bool = False
    sitadel_permits: bool = False
    insee_population: bool = False
    
    @property
    def confidence_score(self) -> float:
        """Score de confiance basé sur le nombre de sources disponibles."""
        available_sources = sum([
            self.sirene_creations,
            self.bodacc_liquidations, 
            self.france_travail_offers,
            self.dvf_transactions,
            self.sitadel_permits,
            self.insee_population
        ])
        return available_sources / 6.0


@dataclass
class TerritorialFactors:
    """Calculated territorial alpha factors with enhanced data quality tracking."""
    code_dept: str
    nom: str
    calculated_at: datetime
    
    # Alpha factors (normalized per 10k habitants) - can be NaN if no data
    factor_tension_emploi: float  # offres_FT / nb_entreprises_actives_SIRENE
    factor_dynamisme_immo: float  # (prix_m2_DVF * transactions_DVF) / population  
    factor_sante_entreprises: float  # creations_SIRENE / (liquidations_BODACC + 1)
    factor_construction: float  # logements_autorises_Sitadel / population * 10000
    factor_declin_ratio: float  # liquidations_BODACC / (creations_SIRENE + 1)
    
    # Composite score (0-100) using percentile ranking
    score_composite: float
    rang_national: Optional[int] = None
    
    # Data availability and confidence
    data_availability: SourceDataAvailability = None
    confidence_score: float = 0.0  # 0-1 based on data availability
    
    # Source data for transparency (raw counts, not normalized)
    population: int = 0
    nb_entreprises_actives: int = 0
    offres_emploi: int = 0
    creations: int = 0
    liquidations: int = 0
    prix_m2_moyen: float = 0.0
    transactions_immo: int = 0
    logements_autorises: int = 0


class PostgreSQLDataCollector:
    """Collects data directly from PostgreSQL signals database."""
    
    def __init__(self):
        self.conn_params = {
            'host': 'localhost',
            'port': 5433,
            'database': os.getenv("SIGNALS_DB_NAME", "tawiza_signals"),
            'user': os.getenv("DATABASE_USER", "tawiza"),
            'password': os.getenv("DATABASE_PASSWORD", "")
        }
        
    async def collect_department_data(self) -> Dict[str, Dict]:
        """Collect aggregated data by department from PostgreSQL."""
        logger.info("Collecting data from PostgreSQL signals database")
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()
            
            # Aggregate signal data by department
            cursor.execute("""
            SELECT 
                code_dept,
                source,
                metric_name,
                COUNT(*) as signal_count,
                SUM(metric_value) as total_value,
                AVG(metric_value) as avg_value,
                MAX(collected_at) as last_collected
            FROM signals 
            WHERE code_dept IS NOT NULL 
            GROUP BY code_dept, source, metric_name
            ORDER BY code_dept, source, metric_name
            """)
            
            results = cursor.fetchall()
            conn.close()
            
            # Organize data by department
            dept_data = {}
            for row in results:
                code_dept, source, metric_name, count, total_val, avg_val, last_date = row
                
                if code_dept not in dept_data:
                    dept_data[code_dept] = {
                        'creations_sirene': 0,
                        'liquidations_bodacc': 0,
                        'offres_france_travail': 0,
                        'transactions_dvf': 0,
                        'prix_m2_dvf': 0.0,
                        'logements_sitadel': 0,
                        'data_availability': SourceDataAvailability()
                    }
                
                # Map signals to territorial metrics
                if source == 'sirene' and 'creation' in metric_name.lower():
                    dept_data[code_dept]['creations_sirene'] = count
                    dept_data[code_dept]['data_availability'].sirene_creations = True
                    
                elif source == 'bodacc' and 'liquidation' in metric_name.lower():
                    dept_data[code_dept]['liquidations_bodacc'] = count  
                    dept_data[code_dept]['data_availability'].bodacc_liquidations = True
                    
                elif source == 'france_travail' and 'offre' in metric_name.lower():
                    dept_data[code_dept]['offres_france_travail'] = count
                    dept_data[code_dept]['data_availability'].france_travail_offers = True
                    
                elif source == 'dvf':
                    if 'transaction' in metric_name.lower():
                        dept_data[code_dept]['transactions_dvf'] = count
                        dept_data[code_dept]['data_availability'].dvf_transactions = True
                    elif 'prix' in metric_name.lower():
                        dept_data[code_dept]['prix_m2_dvf'] = avg_val or 0.0
                        
                elif source == 'sitadel' and 'logement' in metric_name.lower():
                    dept_data[code_dept]['logements_sitadel'] = count
                    dept_data[code_dept]['data_availability'].sitadel_permits = True
                    
            logger.info(f"Collected data for {len(dept_data)} departments from PostgreSQL")
            return dept_data
            
        except Exception as e:
            logger.error(f"Failed to collect PostgreSQL data: {e}")
            return {}


class PopulationManager:
    """Manages population data with enhanced error handling."""
    
    def __init__(self, db_path: str = "data/territorial_history.db"):
        self.db_path = db_path
        self._population_cache: Dict[str, int] = {}
        
    async def get_population(self, code_dept: str) -> Optional[int]:
        """Get population for a department."""
        if code_dept in self._population_cache:
            return self._population_cache[code_dept]
            
        # Try to load from CSV first
        try:
            df = pd.read_csv("data/population_insee.csv")
            pop_data = df[df["code_dept"] == code_dept]
            if not pop_data.empty:
                population = int(pop_data.iloc[0]["population"])
                self._population_cache[code_dept] = population
                return population
        except:
            pass
            
        # Fallback: estimate based on department size (rough approximation)
        dept_populations = {
            "75": 2161000,  # Paris
            "13": 2043000,  # Bouches-du-Rhône  
            "59": 2604000,  # Nord
            "69": 1844000,  # Rhône
            "92": 1609000,  # Hauts-de-Seine
            "93": 1632000,  # Seine-Saint-Denis
            "94": 1387000,  # Val-de-Marne
        }
        
        if code_dept in dept_populations:
            population = dept_populations[code_dept]
            self._population_cache[code_dept] = population
            return population
            
        # Default estimation for other departments
        default_population = 600000  # Moyenne départements métropolitains
        self._population_cache[code_dept] = default_population
        return default_population


class TerritorialFactorsCalculatorV2:
    """Enhanced territorial factors calculator with robust data handling."""
    
    def __init__(self, db_path: str = "data/territorial_history.db"):
        self.db_path = db_path
        self.pop_manager = PopulationManager(db_path)
        self.pg_collector = PostgreSQLDataCollector()
        
    async def calculate_factors(self, code_dept: Optional[str] = None) -> List[TerritorialFactors]:
        """Calculate enhanced alpha factors for department(s)."""
        logger.info("Starting enhanced territorial factors calculation")
        
        # Collect data from PostgreSQL
        pg_data = await self.pg_collector.collect_department_data()
        
        if not pg_data:
            logger.warning("No PostgreSQL data available, falling back to SQLite")
            return await self._calculate_from_sqlite(code_dept)
            
        factors_list = []
        
        # Get department names from SQLite 
        dept_names = await self._get_department_names()
        
        for dept_code, data in pg_data.items():
            if code_dept and dept_code != code_dept:
                continue
                
            factors = await self._calculate_dept_factors_v2(dept_code, data, dept_names.get(dept_code, f"Département {dept_code}"))
            if factors:
                factors_list.append(factors)
                
        # Calculate composite scores with percentile ranking
        if factors_list:
            factors_list = self._calculate_composite_scores_v2(factors_list)
            
        logger.info(f"Calculated enhanced factors for {len(factors_list)} departments")
        return factors_list
        
    async def _get_department_names(self) -> Dict[str, str]:
        """Get department names from SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT territory_code, territory_name FROM territorial_metrics_history")
            results = cursor.fetchall()
            conn.close()
            return {code: name for code, name in results}
        except:
            return {}
            
    async def _calculate_from_sqlite(self, code_dept: Optional[str] = None) -> List[TerritorialFactors]:
        """Fallback calculation from SQLite data."""
        logger.info("Calculating factors from SQLite data")
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = """
            SELECT 
                territory_code,
                territory_name,
                AVG(creations) as avg_creations,
                AVG(closures) as avg_liquidations,
                AVG(job_offers) as avg_job_offers,
                COUNT(*) as nb_records
            FROM territorial_metrics_history
            """
            
            if code_dept:
                query += " WHERE territory_code = ?"
                cursor.execute(query + " GROUP BY territory_code, territory_name", (code_dept,))
            else:
                query += " GROUP BY territory_code, territory_name"
                cursor.execute(query)
                
            results = cursor.fetchall()
            conn.close()
            
            factors_list = []
            for row in results:
                dept_code, nom, avg_creations, avg_liquidations, avg_job_offers, nb_records = row
                
                # Skip departments without business data
                if (avg_creations or 0) == 0 and (avg_liquidations or 0) == 0:
                    logger.warning(f"Skipping {dept_code} - {nom}: no business creation/liquidation data")
                    continue
                
                # Create data availability info
                data_avail = SourceDataAvailability()
                data_avail.sirene_creations = (avg_creations or 0) > 0
                data_avail.bodacc_liquidations = (avg_liquidations or 0) > 0
                data_avail.france_travail_offers = (avg_job_offers or 0) > 0
                
                # Get population
                population = await self.pop_manager.get_population(dept_code)
                data_avail.insee_population = population is not None
                
                factors = await self._calculate_dept_factors_legacy(
                    dept_code, nom, 
                    int(avg_creations or 0), 
                    int(avg_liquidations or 0), 
                    int(avg_job_offers or 0),
                    population,
                    data_avail
                )
                
                if factors:
                    factors_list.append(factors)
                    
            # Calculate composite scores
            if factors_list:
                factors_list = self._calculate_composite_scores_v2(factors_list)
                
            return factors_list
            
        except Exception as e:
            logger.error(f"Failed to calculate from SQLite: {e}")
            return []
            
    async def _calculate_dept_factors_v2(self, code_dept: str, data: Dict, nom: str) -> Optional[TerritorialFactors]:
        """Calculate factors for a department using PostgreSQL data."""
        try:
            # Get population
            population = await self.pop_manager.get_population(code_dept)
            if not population:
                population = 600000  # Default
                
            data_avail = data['data_availability']
            data_avail.insee_population = True  # We have population data
            
            # Extract metrics
            creations = data['creations_sirene']
            liquidations = data['liquidations_bodacc'] 
            job_offers = data['offres_france_travail']
            transactions = data['transactions_dvf']
            prix_m2 = data['prix_m2_dvf']
            logements = data['logements_sitadel']
            
            # Calculate factors with NaN for missing data
            factor_tension_emploi = np.nan
            if creations > 0 and job_offers > 0:
                factor_tension_emploi = (job_offers / creations) * 10000 / population * 100000
                
            factor_dynamisme_immo = np.nan  
            if transactions > 0 and prix_m2 > 0:
                factor_dynamisme_immo = (prix_m2 * transactions) / population * 10000
                
            factor_sante_entreprises = np.nan
            if creations > 0:
                factor_sante_entreprises = creations / max(liquidations + 1, 1) * 1000
                
            factor_construction = np.nan
            if logements > 0:
                factor_construction = (logements / population) * 10000
                
            factor_declin_ratio = np.nan
            if creations > 0 or liquidations > 0:
                factor_declin_ratio = liquidations / max(creations + 1, 1) * 1000
                
            return TerritorialFactors(
                code_dept=code_dept,
                nom=nom,
                calculated_at=datetime.now(),
                factor_tension_emploi=factor_tension_emploi,
                factor_dynamisme_immo=factor_dynamisme_immo,
                factor_sante_entreprises=factor_sante_entreprises,
                factor_construction=factor_construction,
                factor_declin_ratio=factor_declin_ratio,
                score_composite=0.0,
                data_availability=data_avail,
                confidence_score=data_avail.confidence_score,
                population=population,
                nb_entreprises_actives=creations * 10,  # Estimate
                offres_emploi=job_offers,
                creations=creations,
                liquidations=liquidations,
                prix_m2_moyen=prix_m2,
                transactions_immo=transactions,
                logements_autorises=logements
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate factors for {code_dept}: {e}")
            return None
            
    async def _calculate_dept_factors_legacy(self, code_dept: str, nom: str, creations: int, liquidations: int, job_offers: int, population: int, data_avail: SourceDataAvailability) -> Optional[TerritorialFactors]:
        """Calculate factors using legacy SQLite data."""
        try:
            # Calculate factors (only the ones we have data for)
            factor_tension_emploi = np.nan
            if creations > 0 and job_offers > 0:
                factor_tension_emploi = (job_offers / creations) * 1000
                
            factor_sante_entreprises = np.nan 
            if creations > 0:
                factor_sante_entreprises = creations / max(liquidations + 1, 1) * 1000
                
            factor_declin_ratio = np.nan
            if creations > 0 or liquidations > 0:
                factor_declin_ratio = liquidations / max(creations + 1, 1) * 1000
                
            # Missing data factors
            factor_dynamisme_immo = np.nan
            factor_construction = np.nan
            
            return TerritorialFactors(
                code_dept=code_dept,
                nom=nom,
                calculated_at=datetime.now(),
                factor_tension_emploi=factor_tension_emploi,
                factor_dynamisme_immo=factor_dynamisme_immo, 
                factor_sante_entreprises=factor_sante_entreprises,
                factor_construction=factor_construction,
                factor_declin_ratio=factor_declin_ratio,
                score_composite=0.0,
                data_availability=data_avail,
                confidence_score=data_avail.confidence_score,
                population=population,
                nb_entreprises_actives=creations * 10,
                offres_emploi=job_offers,
                creations=creations,
                liquidations=liquidations,
                prix_m2_moyen=0.0,
                transactions_immo=0,
                logements_autorises=0
            )
            
        except Exception as e:
            logger.error(f"Failed to calculate legacy factors for {code_dept}: {e}")
            return None
    
    def _winsorize_factor(self, values: List[float], percentile: float = 0.05) -> List[float]:
        """Winsorize extreme values to reduce outlier impact."""
        valid_values = [v for v in values if not np.isnan(v)]
        if len(valid_values) < 2:
            return values
            
        lower_bound = np.percentile(valid_values, percentile * 100)
        upper_bound = np.percentile(valid_values, (1 - percentile) * 100)
        
        winsorized = []
        for v in values:
            if np.isnan(v):
                winsorized.append(v)
            elif v < lower_bound:
                winsorized.append(lower_bound)
            elif v > upper_bound:
                winsorized.append(upper_bound)
            else:
                winsorized.append(v)
                
        return winsorized
        
    def _calculate_composite_scores_v2(self, factors_list: List[TerritorialFactors]) -> List[TerritorialFactors]:
        """Calculate composite scores using percentile ranking and winsorization."""
        if not factors_list:
            return factors_list
            
        logger.info("Calculating composite scores with percentile ranking")
        
        # Define weights for each factor
        weights = {
            "tension_emploi": 0.15,
            "dynamisme_immo": 0.20,
            "sante_entreprises": 0.35,  # Most important
            "construction": 0.10,
            "declin_ratio": -0.20  # Negative weight
        }
        
        # Extract factors and winsorize extreme values
        tension_values = [f.factor_tension_emploi for f in factors_list]
        dynamisme_values = [f.factor_dynamisme_immo for f in factors_list]
        sante_values = [f.factor_sante_entreprises for f in factors_list]
        construction_values = [f.factor_construction for f in factors_list]
        declin_values = [f.factor_declin_ratio for f in factors_list]
        
        # Winsorize outliers (clip extreme 5%)
        tension_values = self._winsorize_factor(tension_values)
        dynamisme_values = self._winsorize_factor(dynamisme_values)
        sante_values = self._winsorize_factor(sante_values) 
        construction_values = self._winsorize_factor(construction_values)
        declin_values = self._winsorize_factor(declin_values)
        
        # Calculate raw composite scores
        raw_scores = []
        for i, factors in enumerate(factors_list):
            score = 0.0
            weight_sum = 0.0
            
            # Only use factors where we have data
            if not np.isnan(tension_values[i]):
                score += tension_values[i] * weights["tension_emploi"]
                weight_sum += weights["tension_emploi"]
                
            if not np.isnan(dynamisme_values[i]):
                score += dynamisme_values[i] * weights["dynamisme_immo"] 
                weight_sum += weights["dynamisme_immo"]
                
            if not np.isnan(sante_values[i]):
                score += sante_values[i] * weights["sante_entreprises"]
                weight_sum += weights["sante_entreprises"]
                
            if not np.isnan(construction_values[i]):
                score += construction_values[i] * weights["construction"]
                weight_sum += weights["construction"]
                
            if not np.isnan(declin_values[i]):
                score += declin_values[i] * weights["declin_ratio"]
                weight_sum += abs(weights["declin_ratio"])  # Absolute value for weight sum
                
            # Normalize by available weights
            if weight_sum > 0:
                score = score / weight_sum * sum(abs(w) for w in weights.values())
            
            raw_scores.append((score, factors))
            
        # Sort by raw score for percentile ranking
        raw_scores.sort(key=lambda x: x[0])
        
        # Assign percentile-based scores (0-100)
        n = len(raw_scores)
        for i, (raw_score, factors) in enumerate(raw_scores):
            if n > 1:
                percentile = (i / (n - 1)) * 100
            else:
                percentile = 50.0
                
            # Adjust by confidence score (departments with more data get slight bonus)
            confidence_bonus = factors.confidence_score * 5  # Max 5 point bonus
            final_score = min(100.0, percentile + confidence_bonus)
            
            factors.score_composite = final_score
            
        # Sort by final score and assign rankings
        factors_list.sort(key=lambda f: f.score_composite, reverse=True)
        for i, factors in enumerate(factors_list):
            factors.rang_national = i + 1
            
        return factors_list


class TerritorialFactorsRepositoryV2:
    """Enhanced repository with data quality tracking."""
    
    def __init__(self, db_path: str = "data/territorial_history.db"):
        self.db_path = db_path
        
    async def create_table(self):
        """Create enhanced territorial_factors table."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS territorial_factors_v2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code_dept TEXT NOT NULL,
                    nom TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,
                    
                    -- Alpha factors (can be NULL for missing data)
                    factor_tension_emploi REAL,
                    factor_dynamisme_immo REAL,
                    factor_sante_entreprises REAL,
                    factor_construction REAL,
                    factor_declin_ratio REAL,
                    
                    -- Composite and ranking
                    score_composite REAL NOT NULL,
                    rang_national INTEGER,
                    confidence_score REAL NOT NULL,
                    
                    -- Data availability flags
                    has_sirene_data BOOLEAN DEFAULT FALSE,
                    has_bodacc_data BOOLEAN DEFAULT FALSE,
                    has_france_travail_data BOOLEAN DEFAULT FALSE,
                    has_dvf_data BOOLEAN DEFAULT FALSE,
                    has_sitadel_data BOOLEAN DEFAULT FALSE,
                    has_population_data BOOLEAN DEFAULT FALSE,
                    
                    -- Source data
                    population INTEGER,
                    nb_entreprises_actives INTEGER,
                    offres_emploi INTEGER,
                    creations INTEGER,
                    liquidations INTEGER,
                    prix_m2_moyen REAL,
                    transactions_immo INTEGER,
                    logements_autorises INTEGER,
                    
                    UNIQUE(code_dept, calculated_at)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_territorial_factors_v2_dept_date 
                ON territorial_factors_v2(code_dept, calculated_at)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_territorial_factors_v2_score 
                ON territorial_factors_v2(score_composite DESC)
            """)
            
            conn.commit()
            conn.close()
            logger.info("Created enhanced territorial_factors_v2 table")
            
        except Exception as e:
            logger.error(f"Failed to create enhanced table: {e}")
            
    async def store_factors(self, factors_list: List[TerritorialFactors]):
        """Store enhanced factors with data quality information."""
        if not factors_list:
            return
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for factors in factors_list:
                cursor.execute("""
                    INSERT OR REPLACE INTO territorial_factors_v2 (
                        code_dept, nom, calculated_at,
                        factor_tension_emploi, factor_dynamisme_immo, factor_sante_entreprises,
                        factor_construction, factor_declin_ratio,
                        score_composite, rang_national, confidence_score,
                        has_sirene_data, has_bodacc_data, has_france_travail_data,
                        has_dvf_data, has_sitadel_data, has_population_data,
                        population, nb_entreprises_actives, offres_emploi,
                        creations, liquidations, prix_m2_moyen,
                        transactions_immo, logements_autorises
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    factors.code_dept,
                    factors.nom,
                    factors.calculated_at.isoformat(),
                    factors.factor_tension_emploi if not np.isnan(factors.factor_tension_emploi) else None,
                    factors.factor_dynamisme_immo if not np.isnan(factors.factor_dynamisme_immo) else None,
                    factors.factor_sante_entreprises if not np.isnan(factors.factor_sante_entreprises) else None,
                    factors.factor_construction if not np.isnan(factors.factor_construction) else None,
                    factors.factor_declin_ratio if not np.isnan(factors.factor_declin_ratio) else None,
                    factors.score_composite,
                    factors.rang_national,
                    factors.confidence_score,
                    factors.data_availability.sirene_creations if factors.data_availability else False,
                    factors.data_availability.bodacc_liquidations if factors.data_availability else False,
                    factors.data_availability.france_travail_offers if factors.data_availability else False,
                    factors.data_availability.dvf_transactions if factors.data_availability else False,
                    factors.data_availability.sitadel_permits if factors.data_availability else False,
                    factors.data_availability.insee_population if factors.data_availability else False,
                    factors.population,
                    factors.nb_entreprises_actives,
                    factors.offres_emploi,
                    factors.creations,
                    factors.liquidations,
                    factors.prix_m2_moyen,
                    factors.transactions_immo,
                    factors.logements_autorises
                ))
                
            conn.commit()
            conn.close()
            logger.info(f"Stored {len(factors_list)} enhanced territorial factors")
            
        except Exception as e:
            logger.error(f"Failed to store enhanced factors: {e}")


# CLI entry point for testing the enhanced version
async def main_v2():
    """Enhanced CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Calculate enhanced territorial alpha factors (V2)")
    parser.add_argument("--dept", help="Department code to process (default: all)")
    parser.add_argument("--show-ranking", action="store_true", help="Show national ranking")
    parser.add_argument("--data-quality", action="store_true", help="Show data quality report")
    
    args = parser.parse_args()
    
    # Initialize enhanced components
    calculator = TerritorialFactorsCalculatorV2()
    repository = TerritorialFactorsRepositoryV2()
    
    # Create enhanced table
    await repository.create_table()
    
    # Calculate enhanced factors
    logger.info("Calculating enhanced territorial alpha factors...")
    factors_list = await calculator.calculate_factors(args.dept)
    
    if not factors_list:
        logger.error("No enhanced factors calculated")
        return
        
    # Store results
    await repository.store_factors(factors_list)
    
    # Display results
    print(f"\n=== ENHANCED TERRITORIAL FACTORS PHASE 2 ===")
    print(f"Calculated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Departments analyzed: {len(factors_list)}")
    
    if args.data_quality:
        print(f"\n📊 DATA QUALITY REPORT:")
        print("-" * 80)
        print(f"{'Dept':<4} {'Name':<20} {'Conf.':<5} {'SIRENE':<7} {'BODACC':<7} {'FT':<3} {'DVF':<3} {'Sitadel':<7}")
        print("-" * 80)
        
        for f in factors_list:
            print(
                f"{f.code_dept:<4} "
                f"{f.nom[:18]:<20} "
                f"{f.confidence_score:.2f} "
                f"{'✓' if f.data_availability and f.data_availability.sirene_creations else '✗':<7} "
                f"{'✓' if f.data_availability and f.data_availability.bodacc_liquidations else '✗':<7} "
                f"{'✓' if f.data_availability and f.data_availability.france_travail_offers else '✗':<3} "
                f"{'✓' if f.data_availability and f.data_availability.dvf_transactions else '✗':<3} "
                f"{'✓' if f.data_availability and f.data_availability.sitadel_permits else '✗':<7}"
            )
    
    if args.show_ranking:
        print(f"\n🏆 ENHANCED NATIONAL RANKING:")
        print("-" * 90)
        print(f"{'Rank':<4} {'Dept':<4} {'Name':<20} {'Score':<6} {'Conf.':<5} {'Santé':<8} {'Déclin':<8}")
        print("-" * 90)
        
        for f in factors_list[:20]:  # Top 20
            sante_str = f"{f.factor_sante_entreprises:.1f}" if not np.isnan(f.factor_sante_entreprises) else "N/A"
            declin_str = f"{f.factor_declin_ratio:.1f}" if not np.isnan(f.factor_declin_ratio) else "N/A"
            
            print(
                f"{f.rang_national:<4} "
                f"{f.code_dept:<4} "
                f"{f.nom[:18]:<20} "
                f"{f.score_composite:5.1f} "
                f"{f.confidence_score:.2f} "
                f"{sante_str:<8} "
                f"{declin_str:<8}"
            )
            
        # Enhanced statistics
        scores = [f.score_composite for f in factors_list]
        confidences = [f.confidence_score for f in factors_list]
        
        print(f"\n📊 ENHANCED STATISTICS:")
        print(f"   Score distribution: min={min(scores):.1f}, max={max(scores):.1f}, median={np.median(scores):.1f}")
        print(f"   Confidence distribution: min={min(confidences):.2f}, max={max(confidences):.2f}, avg={np.mean(confidences):.2f}")
        print(f"   Departments with full data (confidence=1.0): {len([c for c in confidences if c >= 1.0])}")
        print(f"   Departments with partial data (confidence<0.5): {len([c for c in confidences if c < 0.5])}")


if __name__ == "__main__":
    asyncio.run(main_v2())