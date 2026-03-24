"""Department Data Service for real API data.

Fetches real department statistics from:
- SIRENE API (company counts)
- INSEE data (growth rates when available)

Includes caching to respect rate limits (7 req/s).
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

import httpx
from loguru import logger

# API endpoint - no auth required
SIRENE_API = "https://recherche-entreprises.api.gouv.fr"

# All French department codes
DEPT_CODES = [f"{i:02d}" for i in range(1, 96) if i != 20] + ["2A", "2B"]

# Department names
DEPT_NAMES = {
    "01": "Ain",
    "02": "Aisne",
    "03": "Allier",
    "04": "Alpes-Hte-Prov",
    "05": "Hautes-Alpes",
    "06": "Alpes-Maritimes",
    "07": "Ardèche",
    "08": "Ardennes",
    "09": "Ariège",
    "10": "Aube",
    "11": "Aude",
    "12": "Aveyron",
    "13": "Bouches-du-Rhône",
    "14": "Calvados",
    "15": "Cantal",
    "16": "Charente",
    "17": "Charente-Maritime",
    "18": "Cher",
    "19": "Corrèze",
    "21": "Côte-d'Or",
    "22": "Côtes-d'Armor",
    "23": "Creuse",
    "24": "Dordogne",
    "25": "Doubs",
    "26": "Drôme",
    "27": "Eure",
    "28": "Eure-et-Loir",
    "29": "Finistère",
    "30": "Gard",
    "31": "Haute-Garonne",
    "32": "Gers",
    "33": "Gironde",
    "34": "Hérault",
    "35": "Ille-et-Vilaine",
    "36": "Indre",
    "37": "Indre-et-Loire",
    "38": "Isère",
    "39": "Jura",
    "40": "Landes",
    "41": "Loir-et-Cher",
    "42": "Loire",
    "43": "Haute-Loire",
    "44": "Loire-Atlantique",
    "45": "Loiret",
    "46": "Lot",
    "47": "Lot-et-Garonne",
    "48": "Lozère",
    "49": "Maine-et-Loire",
    "50": "Manche",
    "51": "Marne",
    "52": "Haute-Marne",
    "53": "Mayenne",
    "54": "Meurthe-et-Moselle",
    "55": "Meuse",
    "56": "Morbihan",
    "57": "Moselle",
    "58": "Nièvre",
    "59": "Nord",
    "60": "Oise",
    "61": "Orne",
    "62": "Pas-de-Calais",
    "63": "Puy-de-Dôme",
    "64": "Pyrénées-Atlantiques",
    "65": "Hautes-Pyrénées",
    "66": "Pyrénées-Orientales",
    "67": "Bas-Rhin",
    "68": "Haut-Rhin",
    "69": "Rhône",
    "70": "Haute-Saône",
    "71": "Saône-et-Loire",
    "72": "Sarthe",
    "73": "Savoie",
    "74": "Haute-Savoie",
    "75": "Paris",
    "76": "Seine-Maritime",
    "77": "Seine-et-Marne",
    "78": "Yvelines",
    "79": "Deux-Sèvres",
    "80": "Somme",
    "81": "Tarn",
    "82": "Tarn-et-Garonne",
    "83": "Var",
    "84": "Vaucluse",
    "85": "Vendée",
    "86": "Vienne",
    "87": "Haute-Vienne",
    "88": "Vosges",
    "89": "Yonne",
    "90": "Belfort",
    "91": "Essonne",
    "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne",
    "95": "Val-d'Oise",
    "2A": "Corse-du-Sud",
    "2B": "Haute-Corse",
}

# Top sectors by NAF code
TOP_SECTORS = {
    "62": "Tech",
    "86": "Santé",
    "64": "Finance",
    "47": "Commerce",
    "10": "Industrie",
    "56": "Restauration",
    "68": "Immobilier",
    "70": "Services",
}


class LoadingState(Enum):
    """State of data loading."""

    IDLE = "idle"
    LOADING = "loading"
    LOADED = "loaded"
    ERROR = "error"


@dataclass
class DepartmentStats:
    """Statistics for a single department."""

    code: str
    name: str
    companies_count: int
    growth_rate: float  # Estimated from recent creations
    top_sector: str
    confidence: float
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class LoadingProgress:
    """Progress of data loading."""

    total: int
    loaded: int
    current_dept: str
    state: LoadingState
    error: str | None = None


class DepartmentDataService:
    """Service for fetching real department data from APIs.

    Features:
    - Fetches company counts from SIRENE API
    - Estimates growth rates from recent company creations
    - Caches results to respect rate limits
    - Provides loading progress callbacks
    """

    def __init__(self, cache_ttl_hours: int = 24):
        self._cache: dict[str, DepartmentStats] = {}
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._loading_state = LoadingState.IDLE
        self._progress_callbacks: list[Callable[[LoadingProgress], None]] = []
        self._last_fetch: datetime | None = None

    @property
    def state(self) -> LoadingState:
        """Current loading state."""
        return self._loading_state

    @property
    def is_cached(self) -> bool:
        """Check if data is cached and valid."""
        if not self._cache or not self._last_fetch:
            return False
        return datetime.now() - self._last_fetch < self._cache_ttl

    def add_progress_callback(self, callback: Callable[[LoadingProgress], None]) -> None:
        """Add callback for loading progress updates."""
        self._progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: Callable[[LoadingProgress], None]) -> None:
        """Remove progress callback."""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    def _emit_progress(self, progress: LoadingProgress) -> None:
        """Emit progress to all callbacks."""
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    async def fetch_all_departments(
        self, force_refresh: bool = False
    ) -> dict[str, DepartmentStats]:
        """Fetch statistics for all French departments.

        Args:
            force_refresh: If True, bypass cache

        Returns:
            Dict mapping department codes to stats
        """
        # Return cache if valid
        if not force_refresh and self.is_cached:
            logger.info("Returning cached department data")
            return self._cache.copy()

        self._loading_state = LoadingState.LOADING
        total = len(DEPT_CODES)

        # Emit initial progress
        self._emit_progress(
            LoadingProgress(
                total=total, loaded=0, current_dept="Démarrage...", state=LoadingState.LOADING
            )
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for i, code in enumerate(DEPT_CODES):
                    # Emit progress only every 10 departments to avoid UI blocking
                    if i % 10 == 0:
                        self._emit_progress(
                            LoadingProgress(
                                total=total,
                                loaded=i,
                                current_dept=f"{code} - {DEPT_NAMES.get(code, code)}",
                                state=LoadingState.LOADING,
                            )
                        )
                        # Yield to event loop to allow UI updates
                        await asyncio.sleep(0)

                    try:
                        stats = await self._fetch_department(client, code)
                        self._cache[code] = stats

                        # Rate limit: max 7 req/s, so wait ~150ms between requests
                        await asyncio.sleep(0.15)

                    except Exception as e:
                        logger.warning(f"Failed to fetch dept {code}: {e}")
                        # Create placeholder with error
                        self._cache[code] = DepartmentStats(
                            code=code,
                            name=DEPT_NAMES.get(code, f"Dept {code}"),
                            companies_count=0,
                            growth_rate=0.0,
                            top_sector="N/A",
                            confidence=0.0,
                        )

            self._last_fetch = datetime.now()
            self._loading_state = LoadingState.LOADED

            self._emit_progress(
                LoadingProgress(
                    total=total, loaded=total, current_dept="", state=LoadingState.LOADED
                )
            )

            logger.info(f"Loaded {len(self._cache)} departments from API")
            return self._cache.copy()

        except Exception as e:
            self._loading_state = LoadingState.ERROR
            self._emit_progress(
                LoadingProgress(
                    total=total,
                    loaded=len(self._cache),
                    current_dept="",
                    state=LoadingState.ERROR,
                    error=str(e),
                )
            )
            logger.error(f"Department fetch failed: {e}")
            raise

    async def _fetch_department(self, client: httpx.AsyncClient, code: str) -> DepartmentStats:
        """Fetch data for a single department.

        Args:
            client: HTTP client
            code: Department code

        Returns:
            DepartmentStats for the department
        """
        # Get total company count
        params = {
            "departement": code,
            "per_page": 1,  # We only need the count
            "etat_administratif": "A",  # Only active companies
        }

        response = await client.get(f"{SIRENE_API}/search", params=params)
        response.raise_for_status()
        data = response.json()

        total_count = data.get("total_results", 0)

        # Get recent creations (last year) for growth estimation
        from datetime import date

        one_year_ago = (date.today() - timedelta(days=365)).isoformat()

        params_recent = {
            "departement": code,
            "per_page": 1,
            "date_creation_min": one_year_ago,
            "etat_administratif": "A",
        }

        response_recent = await client.get(f"{SIRENE_API}/search", params=params_recent)
        response_recent.raise_for_status()
        data_recent = response_recent.json()

        recent_count = data_recent.get("total_results", 0)

        # Estimate growth rate from new creations
        # Rough estimate: if 10% of companies are new, assume ~10% net growth
        if total_count > 0:
            growth_rate = (recent_count / total_count) - 0.05  # Subtract avg ~5% closures
        else:
            growth_rate = 0.0

        # Get top sector (sample a few companies)
        top_sector = await self._get_top_sector(client, code)

        return DepartmentStats(
            code=code,
            name=DEPT_NAMES.get(code, f"Dept {code}"),
            companies_count=total_count,
            growth_rate=min(max(growth_rate, -0.3), 0.4),  # Clamp to reasonable range
            top_sector=top_sector,
            confidence=0.85 if total_count > 100 else 0.6,
        )

    async def _get_top_sector(self, client: httpx.AsyncClient, code: str) -> str:
        """Get the dominant sector for a department.

        Args:
            client: HTTP client
            code: Department code

        Returns:
            Sector name
        """
        try:
            # Sample companies to find dominant sector
            params = {
                "departement": code,
                "per_page": 25,
                "etat_administratif": "A",
            }

            response = await client.get(f"{SIRENE_API}/search", params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])

            # Count sectors
            sector_counts: dict[str, int] = {}
            for company in results:
                naf = company.get("activite_principale", "")[:2]
                sector = TOP_SECTORS.get(naf, "Autre")
                sector_counts[sector] = sector_counts.get(sector, 0) + 1

            if sector_counts:
                return max(sector_counts, key=sector_counts.get)

        except Exception as e:
            logger.debug(f"Could not get top sector for {code}: {e}")

        return "Services"

    async def fetch_department(self, code: str) -> DepartmentStats | None:
        """Fetch data for a single department.

        Args:
            code: Department code

        Returns:
            DepartmentStats or None if not found
        """
        # Check cache first
        if code in self._cache:
            cached = self._cache[code]
            if datetime.now() - cached.last_updated < self._cache_ttl:
                return cached

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                stats = await self._fetch_department(client, code)
                self._cache[code] = stats
                return stats
        except Exception as e:
            logger.error(f"Failed to fetch department {code}: {e}")
            return self._cache.get(code)

    def get_cached_data(self) -> dict[str, DepartmentStats]:
        """Get all cached department data."""
        return self._cache.copy()

    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._last_fetch = None


# Singleton instance
_department_service: DepartmentDataService | None = None


def get_department_service() -> DepartmentDataService:
    """Get the singleton department data service."""
    global _department_service
    if _department_service is None:
        _department_service = DepartmentDataService()
    return _department_service
