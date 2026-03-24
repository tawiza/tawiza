"""
Territorial Alpha Factors Calculator - Phase 2 Algorithm Tawiza-V2

Calculates normalized alpha factors for territorial health assessment.
Inspired by quantitative finance alpha factors adapted to territorial intelligence.
"""

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from loguru import logger

from src.infrastructure.datasources.adapters.insee_local import INSEELocalAdapter


@dataclass
class PopulationData:
    """Population data for normalization."""

    code_dept: str
    nom: str
    population: int
    last_updated: datetime


@dataclass
class TerritorialFactors:
    """Calculated territorial alpha factors."""

    code_dept: str
    nom: str
    calculated_at: datetime

    # Alpha factors (normalized per 10k habitants)
    factor_tension_emploi: float  # offres_FT / nb_entreprises_actives_SIRENE
    factor_dynamisme_immo: float  # (prix_m2_DVF * transactions_DVF) / population
    factor_sante_entreprises: float  # creations_SIRENE / (liquidations_BODACC + 1)
    factor_construction: float  # logements_autorises_Sitadel / population * 10000
    factor_declin_ratio: float  # liquidations_BODACC / (creations_SIRENE + 1)

    # Composite score (0-100)
    score_composite: float
    rang_national: int | None = None

    # Source data for transparency
    population: int = 0
    nb_entreprises_actives: int = 0
    offres_emploi: int = 0
    creations: int = 0
    liquidations: int = 0
    prix_m2_moyen: float = 0.0
    transactions_immo: int = 0
    logements_autorises: int = 0


class PopulationManager:
    """Manages INSEE population data for normalization."""

    def __init__(self, db_path: str = "data/territorial_history.db"):
        self.db_path = db_path
        self.insee_adapter = INSEELocalAdapter()
        self._population_cache: dict[str, PopulationData] = {}

    async def get_population(self, code_dept: str) -> PopulationData | None:
        """Get population for a department, fetch from INSEE if not cached."""
        if code_dept in self._population_cache:
            return self._population_cache[code_dept]

        logger.info(f"Fetching population data for department {code_dept}")

        try:
            pop_data = await self.insee_adapter.get_population(code_dept)
            if pop_data:
                population_obj = PopulationData(
                    code_dept=code_dept,
                    nom=pop_data.get("nom", f"Département {code_dept}"),
                    population=pop_data.get("population", 0),
                    last_updated=datetime.now(),
                )
                self._population_cache[code_dept] = population_obj

                # Store in database
                await self._store_population(population_obj)

                return population_obj

        except Exception as e:
            logger.error(f"Failed to fetch population for {code_dept}: {e}")

        return None

    async def _store_population(self, pop_data: PopulationData):
        """Store population data in CSV and database."""
        # Store in CSV
        csv_path = "data/population_insee.csv"
        try:
            # Check if file exists and load existing data
            try:
                df = pd.read_csv(csv_path)
            except FileNotFoundError:
                df = pd.DataFrame(columns=["code_dept", "nom", "population", "last_updated"])

            # Update or append row
            existing = df[df["code_dept"] == pop_data.code_dept]
            if not existing.empty:
                df.loc[
                    df["code_dept"] == pop_data.code_dept, ["nom", "population", "last_updated"]
                ] = [pop_data.nom, pop_data.population, pop_data.last_updated.isoformat()]
            else:
                new_row = pd.DataFrame(
                    [
                        {
                            "code_dept": pop_data.code_dept,
                            "nom": pop_data.nom,
                            "population": pop_data.population,
                            "last_updated": pop_data.last_updated.isoformat(),
                        }
                    ]
                )
                df = pd.concat([df, new_row], ignore_index=True)

            df.to_csv(csv_path, index=False)
            logger.info(f"Population data saved to {csv_path}")

        except Exception as e:
            logger.error(f"Failed to save population CSV: {e}")

    async def load_all_populations(self) -> dict[str, PopulationData]:
        """Load population data for all departments."""
        # French metropolitan departments
        departments = [
            "01",
            "02",
            "03",
            "04",
            "05",
            "06",
            "07",
            "08",
            "09",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
            "17",
            "18",
            "19",
            "21",
            "22",
            "23",
            "24",
            "25",
            "26",
            "27",
            "28",
            "29",
            "30",
            "31",
            "32",
            "33",
            "34",
            "35",
            "36",
            "37",
            "38",
            "39",
            "40",
            "41",
            "42",
            "43",
            "44",
            "45",
            "46",
            "47",
            "48",
            "49",
            "50",
            "51",
            "52",
            "53",
            "54",
            "55",
            "56",
            "57",
            "58",
            "59",
            "60",
            "61",
            "62",
            "63",
            "64",
            "65",
            "66",
            "67",
            "68",
            "69",
            "70",
            "71",
            "72",
            "73",
            "74",
            "75",
            "76",
            "77",
            "78",
            "79",
            "80",
            "81",
            "82",
            "83",
            "84",
            "85",
            "86",
            "87",
            "88",
            "89",
            "90",
            "91",
            "92",
            "93",
            "94",
            "95",
        ]

        populations = {}
        # Limit to departments that have data in territorial_metrics_history
        existing_depts = await self._get_existing_departments()

        for dept in existing_depts:
            pop_data = await self.get_population(dept)
            if pop_data:
                populations[dept] = pop_data

        logger.info(f"Loaded population data for {len(populations)} departments")
        return populations

    async def _get_existing_departments(self) -> list[str]:
        """Get list of departments that have data in territorial_metrics_history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT territory_code FROM territorial_metrics_history")
            results = cursor.fetchall()
            conn.close()
            return [row[0] for row in results]
        except Exception as e:
            logger.error(f"Failed to get existing departments: {e}")
            return []


class TerritorialFactorsCalculator:
    """Calculates territorial alpha factors with population normalization."""

    def __init__(self, db_path: str = "data/territorial_history.db"):
        self.db_path = db_path
        self.pop_manager = PopulationManager(db_path)

    async def calculate_factors(self, code_dept: str | None = None) -> list[TerritorialFactors]:
        """Calculate alpha factors for department(s)."""
        logger.info("Starting territorial factors calculation")

        # Load population data
        populations = await self.pop_manager.load_all_populations()

        if not populations:
            logger.error("No population data available")
            return []

        # Get latest metrics from territorial_history
        metrics_data = await self._get_latest_metrics(code_dept)

        if not metrics_data:
            logger.error("No territorial metrics data available")
            return []

        factors_list = []

        for dept_code, metrics in metrics_data.items():
            if dept_code not in populations:
                logger.warning(f"No population data for {dept_code}, skipping")
                continue

            pop_data = populations[dept_code]
            factors = await self._calculate_dept_factors(metrics, pop_data)
            if factors:
                factors_list.append(factors)

        # Calculate composite scores and rankings
        if factors_list:
            factors_list = self._calculate_composite_scores(factors_list)

        logger.info(f"Calculated factors for {len(factors_list)} departments")
        return factors_list

    async def _get_latest_metrics(self, code_dept: str | None = None) -> dict[str, dict]:
        """Get latest metrics for each department."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get the most recent metrics for each department
            query = """
            SELECT
                territory_code,
                territory_name,
                MAX(collected_at) as latest_date,
                creations,
                closures as liquidations,
                job_offers,
                real_estate_tx as transactions_immo,
                avg_price_sqm as prix_m2_moyen
            FROM territorial_metrics_history
            """

            if code_dept:
                query += " WHERE territory_code = ?"
                cursor.execute(query + " GROUP BY territory_code", (code_dept,))
            else:
                query += " GROUP BY territory_code"
                cursor.execute(query)

            results = cursor.fetchall()
            conn.close()

            metrics = {}
            for row in results:
                metrics[row[0]] = {
                    "territory_name": row[1],
                    "latest_date": row[2],
                    "creations": row[3] or 0,
                    "liquidations": row[4] or 0,
                    "job_offers": row[5] or 0,
                    "transactions_immo": row[6] or 0,
                    "prix_m2_moyen": row[7] or 0.0,
                }

            return metrics

        except Exception as e:
            logger.error(f"Failed to get metrics data: {e}")
            return {}

    async def _calculate_dept_factors(
        self, metrics: dict, pop_data: PopulationData
    ) -> TerritorialFactors | None:
        """Calculate factors for a single department."""
        try:
            population = max(pop_data.population, 1)  # Avoid division by zero

            # Get additional data that we don't have yet - use defaults for now
            nb_entreprises_actives = max(metrics["creations"] * 10, 1)  # Rough estimate
            logements_autorises = 0  # TODO: Get from Sitadel when available

            # Calculate alpha factors
            factor_tension_emploi = (metrics["job_offers"] / nb_entreprises_actives) * 10000

            factor_dynamisme_immo = 0.0
            if metrics["prix_m2_moyen"] > 0 and metrics["transactions_immo"] > 0:
                factor_dynamisme_immo = (
                    (metrics["prix_m2_moyen"] * metrics["transactions_immo"]) / population
                ) * 10000

            factor_sante_entreprises = (
                metrics["creations"] / max(metrics["liquidations"] + 1, 1)
            ) * 1000  # Scale to reasonable range

            factor_construction = (logements_autorises / population) * 10000

            factor_declin_ratio = (
                metrics["liquidations"] / max(metrics["creations"] + 1, 1)
            ) * 1000  # Scale to reasonable range

            return TerritorialFactors(
                code_dept=pop_data.code_dept,
                nom=pop_data.nom,
                calculated_at=datetime.now(),
                factor_tension_emploi=factor_tension_emploi,
                factor_dynamisme_immo=factor_dynamisme_immo,
                factor_sante_entreprises=factor_sante_entreprises,
                factor_construction=factor_construction,
                factor_declin_ratio=factor_declin_ratio,
                score_composite=0.0,  # Calculated later
                population=population,
                nb_entreprises_actives=nb_entreprises_actives,
                offres_emploi=metrics["job_offers"],
                creations=metrics["creations"],
                liquidations=metrics["liquidations"],
                prix_m2_moyen=metrics["prix_m2_moyen"],
                transactions_immo=metrics["transactions_immo"],
                logements_autorises=logements_autorises,
            )

        except Exception as e:
            logger.error(f"Failed to calculate factors for {pop_data.code_dept}: {e}")
            return None

    def _calculate_composite_scores(
        self, factors_list: list[TerritorialFactors]
    ) -> list[TerritorialFactors]:
        """Calculate composite scores and national rankings."""
        if not factors_list:
            return factors_list

        # Define weights for each factor (can be made configurable later)
        weights = {
            "tension_emploi": 0.2,
            "dynamisme_immo": 0.25,
            "sante_entreprises": 0.3,
            "construction": 0.15,
            "declin_ratio": -0.1,  # Negative weight (higher declin = worse score)
        }

        # Calculate raw scores
        for factors in factors_list:
            raw_score = (
                factors.factor_tension_emploi * weights["tension_emploi"]
                + factors.factor_dynamisme_immo * weights["dynamisme_immo"]
                + factors.factor_sante_entreprises * weights["sante_entreprises"]
                + factors.factor_construction * weights["construction"]
                + factors.factor_declin_ratio * weights["declin_ratio"]
            )

            # Normalize to 0-100 scale (simple linear normalization for now)
            factors.score_composite = max(0, min(100, 50 + raw_score / 10))

        # Sort by composite score and assign rankings
        factors_list.sort(key=lambda f: f.score_composite, reverse=True)
        for i, factors in enumerate(factors_list):
            factors.rang_national = i + 1

        return factors_list


class TerritorialFactorsRepository:
    """Manages storage and retrieval of territorial factors."""

    def __init__(self, db_path: str = "data/territorial_history.db"):
        self.db_path = db_path

    async def create_table(self):
        """Create the territorial_factors table."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS territorial_factors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code_dept TEXT NOT NULL,
                    nom TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,

                    -- Alpha factors
                    factor_tension_emploi REAL,
                    factor_dynamisme_immo REAL,
                    factor_sante_entreprises REAL,
                    factor_construction REAL,
                    factor_declin_ratio REAL,

                    -- Composite
                    score_composite REAL,
                    rang_national INTEGER,

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

            # Create index for efficient queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_territorial_factors_dept_date
                ON territorial_factors(code_dept, calculated_at)
            """)

            conn.commit()
            conn.close()
            logger.info("Created territorial_factors table")

        except Exception as e:
            logger.error(f"Failed to create territorial_factors table: {e}")

    async def store_factors(self, factors_list: list[TerritorialFactors]):
        """Store calculated factors in database."""
        if not factors_list:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for factors in factors_list:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO territorial_factors (
                        code_dept, nom, calculated_at,
                        factor_tension_emploi, factor_dynamisme_immo, factor_sante_entreprises,
                        factor_construction, factor_declin_ratio,
                        score_composite, rang_national,
                        population, nb_entreprises_actives, offres_emploi,
                        creations, liquidations, prix_m2_moyen,
                        transactions_immo, logements_autorises
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        factors.code_dept,
                        factors.nom,
                        factors.calculated_at.isoformat(),
                        factors.factor_tension_emploi,
                        factors.factor_dynamisme_immo,
                        factors.factor_sante_entreprises,
                        factors.factor_construction,
                        factors.factor_declin_ratio,
                        factors.score_composite,
                        factors.rang_national,
                        factors.population,
                        factors.nb_entreprises_actives,
                        factors.offres_emploi,
                        factors.creations,
                        factors.liquidations,
                        factors.prix_m2_moyen,
                        factors.transactions_immo,
                        factors.logements_autorises,
                    ),
                )

            conn.commit()
            conn.close()
            logger.info(f"Stored {len(factors_list)} territorial factors in database")

        except Exception as e:
            logger.error(f"Failed to store territorial factors: {e}")

    async def get_latest_factors(self, code_dept: str | None = None) -> list[TerritorialFactors]:
        """Get the latest factors for department(s)."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if code_dept:
                cursor.execute(
                    """
                    SELECT * FROM territorial_factors
                    WHERE code_dept = ?
                    ORDER BY calculated_at DESC LIMIT 1
                """,
                    (code_dept,),
                )
            else:
                cursor.execute("""
                    SELECT tf1.* FROM territorial_factors tf1
                    INNER JOIN (
                        SELECT code_dept, MAX(calculated_at) as max_date
                        FROM territorial_factors
                        GROUP BY code_dept
                    ) tf2 ON tf1.code_dept = tf2.code_dept AND tf1.calculated_at = tf2.max_date
                    ORDER BY score_composite DESC
                """)

            rows = cursor.fetchall()
            conn.close()

            factors_list = []
            for row in rows:
                factors = TerritorialFactors(
                    code_dept=row[1],
                    nom=row[2],
                    calculated_at=datetime.fromisoformat(row[3]),
                    factor_tension_emploi=row[4],
                    factor_dynamisme_immo=row[5],
                    factor_sante_entreprises=row[6],
                    factor_construction=row[7],
                    factor_declin_ratio=row[8],
                    score_composite=row[9],
                    rang_national=row[10],
                    population=row[11],
                    nb_entreprises_actives=row[12],
                    offres_emploi=row[13],
                    creations=row[14],
                    liquidations=row[15],
                    prix_m2_moyen=row[16],
                    transactions_immo=row[17],
                    logements_autorises=row[18],
                )
                factors_list.append(factors)

            return factors_list

        except Exception as e:
            logger.error(f"Failed to get latest factors: {e}")
            return []


async def main():
    """CLI entry point for calculating territorial factors."""
    import argparse

    parser = argparse.ArgumentParser(description="Calculate territorial alpha factors")
    parser.add_argument("--dept", help="Department code to process (default: all)")
    parser.add_argument("--show-ranking", action="store_true", help="Show national ranking")

    args = parser.parse_args()

    # Initialize components
    calculator = TerritorialFactorsCalculator()
    repository = TerritorialFactorsRepository()

    # Create table if needed
    await repository.create_table()

    # Calculate factors
    logger.info("Calculating territorial alpha factors...")
    factors_list = await calculator.calculate_factors(args.dept)

    if not factors_list:
        logger.error("No factors calculated")
        return

    # Store in database
    await repository.store_factors(factors_list)

    # Display results
    print("\n=== TERRITORIAL FACTORS PHASE 2 ===")
    print(f"Calculated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Departments analyzed: {len(factors_list)}")
    print()

    if args.show_ranking:
        print("NATIONAL RANKING (Dynamisme ↔ Déclin):")
        print("-" * 80)
        print(
            f"{'Rank':<4} {'Dept':<4} {'Name':<20} {'Score':<6} {'Tension':<8} {'Immo':<8} {'Santé':<8} {'Constr':<8} {'Déclin':<8}"
        )
        print("-" * 80)

        for f in factors_list:
            print(
                f"{f.rang_national:<4} "
                f"{f.code_dept:<4} "
                f"{f.nom[:18]:<20} "
                f"{f.score_composite:5.1f} "
                f"{f.factor_tension_emploi:7.1f} "
                f"{f.factor_dynamisme_immo:7.1f} "
                f"{f.factor_sante_entreprises:7.1f} "
                f"{f.factor_construction:7.1f} "
                f"{f.factor_declin_ratio:7.1f}"
            )
    else:
        for f in factors_list:
            print(f"Département {f.code_dept} - {f.nom}")
            print(f"  Population: {f.population:,} habitants")
            print(f"  Score composite: {f.score_composite:.1f}/100 (Rang: {f.rang_national})")
            print("  Facteurs:")
            print(f"    Tension emploi: {f.factor_tension_emploi:.1f}")
            print(f"    Dynamisme immo: {f.factor_dynamisme_immo:.1f}")
            print(f"    Santé entreprises: {f.factor_sante_entreprises:.1f}")
            print(f"    Construction: {f.factor_construction:.1f}")
            print(f"    Ratio déclin: {f.factor_declin_ratio:.1f}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
