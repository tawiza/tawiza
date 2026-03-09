"""DVF Local Cache - SQLite cache for DVF data from CSV files.

Downloads and caches DVF CSV files from data.gouv.fr for fast local queries.
Useful for large communes where Cerema API is slow.
"""

import asyncio
import csv
import gzip
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from loguru import logger


class DVFLocalCache:
    """Local SQLite cache for DVF transactions.
    
    Downloads CSV files from data.gouv.fr and stores in SQLite for fast queries.
    """
    
    CSV_BASE_URL = "https://files.data.gouv.fr/geo-dvf/latest/csv"
    AVAILABLE_YEARS = [2020, 2021, 2022, 2023, 2024]
    
    # Big departments that benefit from local cache
    RECOMMENDED_DEPARTMENTS = [
        "75",  # Paris
        "69",  # Rhône (Lyon)
        "13",  # Bouches-du-Rhône (Marseille)
        "33",  # Gironde (Bordeaux)
        "31",  # Haute-Garonne (Toulouse)
        "59",  # Nord (Lille)
        "44",  # Loire-Atlantique (Nantes)
        "34",  # Hérault (Montpellier)
        "06",  # Alpes-Maritimes (Nice)
        "67",  # Bas-Rhin (Strasbourg)
    ]
    
    def __init__(self, db_path: Path | str | None = None):
        """Initialize cache.
        
        Args:
            db_path: Path to SQLite database. Defaults to /data/dvf_cache.db
        """
        self.db_path = Path(db_path) if db_path else Path("/data/dvf_cache.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Create database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    date_mutation TEXT,
                    annee INTEGER,
                    nature_mutation TEXT,
                    valeur REAL,
                    type_local TEXT,
                    surface_reelle REAL,
                    surface_terrain REAL,
                    nombre_pieces INTEGER,
                    code_postal TEXT,
                    code_commune TEXT,
                    nom_commune TEXT,
                    code_departement TEXT,
                    longitude REAL,
                    latitude REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_code_commune ON transactions(code_commune)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_code_departement ON transactions(code_departement)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_annee ON transactions(annee)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type_local ON transactions(type_local)")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_meta (
                    department TEXT,
                    year INTEGER,
                    loaded_at TEXT,
                    transaction_count INTEGER,
                    PRIMARY KEY (department, year)
                )
            """)
            conn.commit()
    
    def is_cached(self, department: str, year: int | None = None) -> bool:
        """Check if department data is cached.
        
        Args:
            department: Department code
            year: Specific year or None for any
            
        Returns:
            True if data is cached
        """
        with sqlite3.connect(self.db_path) as conn:
            if year:
                cursor = conn.execute(
                    "SELECT 1 FROM cache_meta WHERE department = ? AND year = ?",
                    (department, year)
                )
            else:
                cursor = conn.execute(
                    "SELECT 1 FROM cache_meta WHERE department = ?",
                    (department,)
                )
            return cursor.fetchone() is not None
    
    def get_cached_departments(self) -> list[dict[str, Any]]:
        """Get list of cached departments with stats."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT department, 
                       GROUP_CONCAT(year) as years,
                       SUM(transaction_count) as total_transactions,
                       MAX(loaded_at) as last_update
                FROM cache_meta 
                GROUP BY department
                ORDER BY department
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    async def download_and_cache(
        self,
        department: str,
        years: list[int] | None = None,
        force: bool = False
    ) -> dict[str, Any]:
        """Download CSV and cache in SQLite.
        
        Args:
            department: Department code (e.g., "75", "69")
            years: Years to download (default: all available)
            force: Re-download even if cached
            
        Returns:
            Stats dict
        """
        years = years or self.AVAILABLE_YEARS
        stats = {"department": department, "years": [], "transactions": 0, "errors": []}
        
        async with httpx.AsyncClient(timeout=120) as client:
            for year in years:
                if not force and self.is_cached(department, year):
                    logger.info(f"DVF {department}/{year} already cached, skipping")
                    continue
                
                try:
                    count = await self._download_year(client, department, year)
                    stats["years"].append(year)
                    stats["transactions"] += count
                    logger.info(f"Cached DVF {department}/{year}: {count:,} transactions")
                except Exception as e:
                    logger.error(f"Failed to cache DVF {department}/{year}: {e}")
                    stats["errors"].append(f"{year}: {e}")
        
        return stats
    
    async def _download_year(
        self,
        client: httpx.AsyncClient,
        department: str,
        year: int
    ) -> int:
        """Download and parse one year's CSV."""
        url = f"{self.CSV_BASE_URL}/{year}/departements/{department}.csv.gz"
        
        response = await client.get(url)
        if response.status_code == 404:
            # Try communes folder
            url = f"{self.CSV_BASE_URL}/{year}/communes/{department}.csv.gz"
            response = await client.get(url)
        
        response.raise_for_status()
        
        # Decompress
        content = gzip.decompress(response.content)
        text = content.decode("utf-8", errors="ignore")
        
        # Parse CSV and insert
        reader = csv.DictReader(text.splitlines())
        count = 0
        batch = []
        
        with sqlite3.connect(self.db_path) as conn:
            for row in reader:
                tx = self._parse_csv_row(row)
                if tx:
                    batch.append(tx)
                    count += 1
                    
                    if len(batch) >= 1000:
                        self._insert_batch(conn, batch)
                        batch = []
            
            if batch:
                self._insert_batch(conn, batch)
            
            # Update meta
            conn.execute("""
                INSERT OR REPLACE INTO cache_meta (department, year, loaded_at, transaction_count)
                VALUES (?, ?, ?, ?)
            """, (department, year, datetime.now().isoformat(), count))
            conn.commit()
        
        return count
    
    def _parse_csv_row(self, row: dict) -> tuple | None:
        """Parse CSV row to tuple for insertion."""
        try:
            valeur = row.get("valeur_fonciere", "").replace(",", ".")
            if not valeur:
                return None
            valeur_float = float(valeur)
            if valeur_float <= 0:
                return None
            
            def parse_float(v: str) -> float | None:
                if not v:
                    return None
                try:
                    return float(v.replace(",", "."))
                except ValueError:
                    return None
            
            def parse_int(v: str) -> int | None:
                if not v:
                    return None
                try:
                    return int(float(v))
                except ValueError:
                    return None
            
            date_str = row.get("date_mutation", "")
            annee = int(date_str[:4]) if date_str else None
            
            return (
                row.get("id_mutation", ""),
                date_str,
                annee,
                row.get("nature_mutation", ""),
                valeur_float,
                row.get("type_local", ""),
                parse_float(row.get("surface_reelle_bati", "")),
                parse_float(row.get("surface_terrain", "")),
                parse_int(row.get("nombre_pieces_principales", "")),
                row.get("code_postal", "")[:5],
                row.get("code_commune", "")[:5],
                row.get("nom_commune", ""),
                row.get("code_departement", "")[:3],
                parse_float(row.get("longitude", "")),
                parse_float(row.get("latitude", "")),
            )
        except Exception:
            return None
    
    def _insert_batch(self, conn: sqlite3.Connection, batch: list[tuple]) -> None:
        """Insert batch of transactions."""
        conn.executemany("""
            INSERT OR IGNORE INTO transactions 
            (id, date_mutation, annee, nature_mutation, valeur, type_local,
             surface_reelle, surface_terrain, nombre_pieces, code_postal,
             code_commune, nom_commune, code_departement, longitude, latitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)
    
    def search(
        self,
        code_insee: str | None = None,
        code_departement: str | None = None,
        annee_min: int | None = None,
        annee_max: int | None = None,
        type_local: str | None = None,
        limit: int = 50
    ) -> list[dict[str, Any]]:
        """Search cached transactions.
        
        Args:
            code_insee: Commune INSEE code
            code_departement: Department code
            annee_min: Start year
            annee_max: End year
            type_local: Property type filter
            limit: Max results
            
        Returns:
            List of transactions
        """
        conditions = []
        params = []
        
        if code_insee:
            conditions.append("code_commune = ?")
            params.append(code_insee)
        elif code_departement:
            conditions.append("code_departement = ?")
            params.append(code_departement)
        
        if annee_min:
            conditions.append("annee >= ?")
            params.append(annee_min)
        if annee_max:
            conditions.append("annee <= ?")
            params.append(annee_max)
        if type_local:
            conditions.append("type_local LIKE ?")
            params.append(f"%{type_local}%")
        
        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"""
                SELECT * FROM transactions 
                WHERE {where}
                ORDER BY date_mutation DESC
                LIMIT ?
            """, params)
            
            return [self._row_to_dict(row) for row in cursor.fetchall()]
    
    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert SQLite row to standard format."""
        return {
            "source": "dvf_cache",
            "id": row["id"],
            "date_mutation": row["date_mutation"],
            "annee": row["annee"],
            "nature_mutation": row["nature_mutation"],
            "valeur": row["valeur"],
            "type_bien": row["type_local"],
            "surface_reelle": row["surface_reelle"],
            "surface_terrain": row["surface_terrain"],
            "nombre_pieces": row["nombre_pieces"],
            "code_postal": row["code_postal"],
            "code_insee": row["code_commune"],
            "nom_commune": row["nom_commune"],
            "code_departement": row["code_departement"],
            "geo": {
                "lat": row["latitude"],
                "lon": row["longitude"],
            } if row["latitude"] else None,
        }
    
    def get_stats(self, code_insee: str, annee: int | None = None) -> dict[str, Any]:
        """Get statistics for a commune."""
        conditions = ["code_commune = ?"]
        params: list[Any] = [code_insee]
        
        if annee:
            conditions.append("annee = ?")
            params.append(annee)
        
        where = " AND ".join(conditions)
        
        with sqlite3.connect(self.db_path) as conn:
            # Total count
            cursor = conn.execute(
                f"SELECT COUNT(*) FROM transactions WHERE {where}", params
            )
            total = cursor.fetchone()[0]
            
            if total == 0:
                return {"source": "dvf_cache", "code_insee": code_insee, "count": 0}
            
            # Stats by type
            cursor = conn.execute(f"""
                SELECT type_local,
                       COUNT(*) as count,
                       AVG(valeur) as avg_price,
                       AVG(CASE WHEN surface_reelle > 0 THEN valeur / surface_reelle END) as avg_price_m2
                FROM transactions 
                WHERE {where}
                GROUP BY type_local
            """, params)
            
            by_type = {}
            for row in cursor.fetchall():
                by_type[row[0] or "Autre"] = {
                    "count": row[1],
                    "avg_price": round(row[2], 2) if row[2] else None,
                    "avg_price_m2": round(row[3], 2) if row[3] else None,
                }
            
            return {
                "source": "dvf_cache",
                "code_insee": code_insee,
                "annee": annee,
                "total_transactions": total,
                "by_type": by_type,
            }


async def populate_cache(departments: list[str] | None = None):
    """Populate cache with recommended departments.
    
    Args:
        departments: Specific departments or None for recommended
    """
    cache = DVFLocalCache()
    departments = departments or DVFLocalCache.RECOMMENDED_DEPARTMENTS
    
    for dept in departments:
        logger.info(f"Caching department {dept}...")
        stats = await cache.download_and_cache(dept)
        logger.info(f"  → {stats['transactions']:,} transactions cached")


if __name__ == "__main__":
    # CLI to populate cache
    import sys
    
    if len(sys.argv) > 1:
        depts = sys.argv[1:]
    else:
        depts = DVFLocalCache.RECOMMENDED_DEPARTMENTS[:3]  # Top 3 by default
        print(f"Caching top departments: {depts}")
    
    asyncio.run(populate_cache(depts))
