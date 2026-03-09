"""
Territorial Metrics History - Stockage historique des métriques territoriales.

Utilise SQLite pour la persistance (migration PostgreSQL possible).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from loguru import logger


# Chemin par défaut de la base SQLite
def _find_project_root() -> Path:
    """Walk up from this file to find the project root (contains pyproject.toml)."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()

DEFAULT_DB_PATH = _find_project_root() / "data" / "territorial_history.db"


@dataclass
class HistoricalMetrics:
    """Métriques historiques d'un territoire."""
    territory_code: str
    territory_name: str
    collected_at: datetime
    
    # Métriques brutes
    creations: int
    closures: int
    procedures: int
    modifications: int
    job_offers: int
    unemployment_rate: float
    real_estate_tx: int
    avg_price_sqm: float
    population: int
    
    # Calculés
    vitality_index: float
    net_creation: int
    
    # Metadata
    sources_used: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["collected_at"] = self.collected_at.isoformat()
        return d
    
    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "HistoricalMetrics":
        return cls(
            territory_code=row["territory_code"],
            territory_name=row["territory_name"],
            collected_at=datetime.fromisoformat(row["collected_at"]),
            creations=row["creations"],
            closures=row["closures"],
            procedures=row["procedures"],
            modifications=row["modifications"],
            job_offers=row["job_offers"],
            unemployment_rate=row["unemployment_rate"],
            real_estate_tx=row["real_estate_tx"],
            avg_price_sqm=row["avg_price_sqm"],
            population=row["population"],
            vitality_index=row["vitality_index"],
            net_creation=row["net_creation"],
            sources_used=json.loads(row["sources_used"]),
        )


class TerritorialHistoryStore:
    """Store pour l'historique des métriques territoriales."""
    
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialise le schéma de la base."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS territorial_metrics_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    territory_code TEXT NOT NULL,
                    territory_name TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    
                    -- Métriques brutes
                    creations INTEGER DEFAULT 0,
                    closures INTEGER DEFAULT 0,
                    procedures INTEGER DEFAULT 0,
                    modifications INTEGER DEFAULT 0,
                    job_offers INTEGER DEFAULT 0,
                    unemployment_rate REAL DEFAULT 0.0,
                    real_estate_tx INTEGER DEFAULT 0,
                    avg_price_sqm REAL DEFAULT 0.0,
                    population INTEGER DEFAULT 0,
                    
                    -- Calculés
                    vitality_index REAL DEFAULT 50.0,
                    net_creation INTEGER DEFAULT 0,
                    
                    -- Metadata
                    sources_used TEXT DEFAULT '[]',
                    
                    -- Index
                    UNIQUE(territory_code, collected_at)
                )
            """)
            
            # Index pour les requêtes fréquentes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_territory_date 
                ON territorial_metrics_history(territory_code, collected_at DESC)
            """)
            
            conn.commit()
            logger.info(f"Territorial history database initialized: {self.db_path}")
    
    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager pour les connexions."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def save_metrics(self, metrics: HistoricalMetrics) -> bool:
        """Sauvegarde les métriques d'un territoire."""
        with self._get_connection() as conn:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO territorial_metrics_history (
                        territory_code, territory_name, collected_at,
                        creations, closures, procedures, modifications,
                        job_offers, unemployment_rate, real_estate_tx, avg_price_sqm,
                        population, vitality_index, net_creation, sources_used
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    metrics.territory_code,
                    metrics.territory_name,
                    metrics.collected_at.isoformat(),
                    metrics.creations,
                    metrics.closures,
                    metrics.procedures,
                    metrics.modifications,
                    metrics.job_offers,
                    metrics.unemployment_rate,
                    metrics.real_estate_tx,
                    metrics.avg_price_sqm,
                    metrics.population,
                    metrics.vitality_index,
                    metrics.net_creation,
                    json.dumps(metrics.sources_used),
                ))
                conn.commit()
                logger.debug(f"Saved metrics for {metrics.territory_code} at {metrics.collected_at}")
                return True
            except Exception as e:
                logger.error(f"Failed to save metrics: {e}")
                return False
    
    def get_history(
        self,
        territory_code: str,
        days: int = 30,
    ) -> list[HistoricalMetrics]:
        """Récupère l'historique d'un territoire."""
        since = datetime.utcnow() - timedelta(days=days)
        
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM territorial_metrics_history
                WHERE territory_code = ? AND collected_at >= ?
                ORDER BY collected_at ASC
            """, (territory_code, since.isoformat()))
            
            return [HistoricalMetrics.from_row(row) for row in cursor.fetchall()]
    
    def get_latest(self, territory_code: str) -> HistoricalMetrics | None:
        """Récupère la dernière entrée d'un territoire."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM territorial_metrics_history
                WHERE territory_code = ?
                ORDER BY collected_at DESC
                LIMIT 1
            """, (territory_code,))
            
            row = cursor.fetchone()
            return HistoricalMetrics.from_row(row) if row else None
    
    def get_all_latest(self) -> list[HistoricalMetrics]:
        """Récupère la dernière entrée de chaque territoire."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT t1.* FROM territorial_metrics_history t1
                INNER JOIN (
                    SELECT territory_code, MAX(collected_at) as max_date
                    FROM territorial_metrics_history
                    GROUP BY territory_code
                ) t2 ON t1.territory_code = t2.territory_code 
                    AND t1.collected_at = t2.max_date
                ORDER BY t1.vitality_index DESC
            """)
            
            return [HistoricalMetrics.from_row(row) for row in cursor.fetchall()]
    
    def get_trends(
        self,
        territory_code: str,
        periods: list[int] = [7, 30, 90],
    ) -> dict[str, dict[str, float]]:
        """
        Calcule les tendances sur différentes périodes.
        
        Returns:
            {
                "7d": {"vitality_change": -2.5, "vitality_pct": -3.8},
                "30d": {"vitality_change": +5.0, "vitality_pct": +8.2},
                ...
            }
        """
        latest = self.get_latest(territory_code)
        if not latest:
            return {}
        
        trends = {}
        now = datetime.utcnow()
        
        for days in periods:
            target_date = now - timedelta(days=days)
            
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT vitality_index, creations, closures, job_offers
                    FROM territorial_metrics_history
                    WHERE territory_code = ? AND collected_at <= ?
                    ORDER BY collected_at DESC
                    LIMIT 1
                """, (territory_code, target_date.isoformat()))
                
                row = cursor.fetchone()
                if row:
                    old_vitality = row["vitality_index"]
                    change = latest.vitality_index - old_vitality
                    pct = (change / old_vitality * 100) if old_vitality != 0 else 0
                    
                    trends[f"{days}d"] = {
                        "vitality_change": round(change, 2),
                        "vitality_pct": round(pct, 2),
                        "creations_change": latest.creations - row["creations"],
                        "closures_change": latest.closures - row["closures"],
                    }
        
        return trends
    
    def count_records(self) -> dict[str, int]:
        """Compte les enregistrements par territoire."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT territory_code, COUNT(*) as count
                FROM territorial_metrics_history
                GROUP BY territory_code
            """)
            return {row["territory_code"]: row["count"] for row in cursor.fetchall()}


# Singleton pour accès global
_store: TerritorialHistoryStore | None = None


def get_history_store() -> TerritorialHistoryStore:
    """Retourne le store singleton."""
    global _store
    if _store is None:
        _store = TerritorialHistoryStore()
    return _store
