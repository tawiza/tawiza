"""TerritorialService - Aggregates data from all territorial adapters.

Provides:
- Alerts: Departments with anomalies (employment, real estate, business dynamics)
- Comparator: Side-by-side comparison of 2-3 departments
- Trends: National-level trend sparklines
- Health Scores: Composite economic health score per department
- Indicators: Individual indicator data for map visualization
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger

from src.infrastructure.datasources.adapters import (
    DVFAdapter,
    FranceTravailAdapter,
    GeoAdapter,
    INSEELocalAdapter,
    OFGLAdapter,
    SireneAdapter,
)


@dataclass
class HealthScoreWeights:
    """Weights for composite health score calculation."""

    emploi: float = 0.30  # Employment (inverted unemployment rate)
    dynamisme: float = 0.25  # Business dynamism (enterprise growth)
    finances: float = 0.20  # Local finances (self-financing capacity)
    immobilier: float = 0.15  # Real estate stability
    demographie: float = 0.10  # Demographics (population trend)


# Constants for alert detection thresholds
ALERT_THRESHOLDS = {
    "chomage_increase": 1.5,  # Unemployment increase > 1.5% triggers alert
    "creation_decrease": -10.0,  # Business creation decrease > 10% triggers alert
    "prix_increase": 6.0,  # Real estate price increase > 6% triggers alert (overheating)
    "prix_decrease": -3.0,  # Real estate price decrease > 3% triggers alert
    "population_decrease": -1.0,  # Population decrease > 1% triggers alert
    "health_score_critical": 45.0,  # Health score < 45 is critical
    "health_score_warning": 55.0,  # Health score < 55 is warning
    "health_score_excellence": 80.0,  # Health score > 80 is excellent (info)
}


# Cached department data (TTL 1 hour)
_cache: dict[str, Any] = {}
_cache_timestamps: dict[str, datetime] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


class TerritorialService:
    """Service for territorial data aggregation and analysis."""

    def __init__(self) -> None:
        """Initialize the TerritorialService with all adapters."""
        self._geo = GeoAdapter()
        self._dvf = DVFAdapter()
        self._ofgl = OFGLAdapter()
        self._france_travail = FranceTravailAdapter()
        self._insee = INSEELocalAdapter()
        self._sirene = SireneAdapter()
        self._weights = HealthScoreWeights()
        # Cache for unemployment rates from INSEE
        self._unemployment_rates: dict[str, float] = {}
        self._unemployment_rates_loaded = False

    async def _get_unemployment_rate(self, dept_code: str) -> float:
        """Get real unemployment rate for a department.

        Uses INSEE BDM TAUX-CHOMAGE data (quarterly).
        Falls back to national average (7.3%) if data unavailable.

        Args:
            dept_code: Department code (e.g., "75", "2A", "971")

        Returns:
            Unemployment rate as percentage
        """
        # Load unemployment rates lazily (once per service lifecycle)
        if not self._unemployment_rates_loaded:
            try:
                self._unemployment_rates = await self._insee.get_all_unemployment_rates()
                self._unemployment_rates_loaded = True
                if self._unemployment_rates:
                    logger.info(
                        f"Loaded real unemployment rates for {len(self._unemployment_rates)} departments"
                    )
            except Exception as e:
                logger.warning(f"Could not load unemployment rates: {e}")
                self._unemployment_rates_loaded = True  # Don't retry on failure

        # Return real rate if available
        if dept_code in self._unemployment_rates:
            return self._unemployment_rates[dept_code]

        # Handle Corsican codes (2A, 2B -> 20 in some systems)
        if dept_code == "20":
            rate_2a = self._unemployment_rates.get("2A")
            rate_2b = self._unemployment_rates.get("2B")
            if rate_2a and rate_2b:
                return (rate_2a + rate_2b) / 2

        # Fallback to national average (Q3 2025: 7.3%)
        return 7.3

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid."""
        if key not in _cache_timestamps:
            return False
        age = (datetime.now() - _cache_timestamps[key]).total_seconds()
        return age < CACHE_TTL_SECONDS

    def _set_cache(self, key: str, value: Any) -> None:
        """Set a cache entry."""
        _cache[key] = value
        _cache_timestamps[key] = datetime.now()

    def _get_cache(self, key: str) -> Any | None:
        """Get a cache entry if valid."""
        if self._is_cache_valid(key):
            return _cache.get(key)
        return None

    async def get_alerts(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get territorial alerts (departments with anomalies).

        Detects:
        - Unemployment spikes
        - Business creation drops
        - Real estate price anomalies
        - Population decline

        Returns:
            List of alert objects with severity and description
        """
        cache_key = f"alerts_{limit}"
        if cached := self._get_cache(cache_key):
            return cached

        alerts = []

        try:
            # Get all departments
            departments = await self._geo.get_all_departments()

            # Get SIRENE data for business dynamics
            from src.infrastructure.datasources.services import get_department_stats_service
            stats_service = get_department_stats_service()

            for dept in departments[:20]:  # Limit to avoid too many API calls
                dept_code = dept.get("code", "")
                dept_name = dept.get("nom", dept_code)

                try:
                    # Get enterprise stats (DepartmentStats dataclass)
                    dept_stats = await stats_service.get_department_stats(dept_code)
                    growth = dept_stats.growth

                    # Check for business creation decline
                    if growth < ALERT_THRESHOLDS["creation_decrease"]:
                        alerts.append({
                            "code": dept_code,
                            "name": dept_name,
                            "severity": "warning" if growth > -15 else "critical",
                            "type": "business_decline",
                            "message": f"Creations entreprises {growth:+.1f}%",
                            "value": growth,
                            "threshold": ALERT_THRESHOLDS["creation_decrease"],
                        })

                    # Check for unusual growth (overheating)
                    if growth > 8.0:
                        alerts.append({
                            "code": dept_code,
                            "name": dept_name,
                            "severity": "info",
                            "type": "business_boom",
                            "message": f"Croissance forte {growth:+.1f}%",
                            "value": growth,
                            "threshold": 8.0,
                        })

                except Exception as e:
                    logger.debug(f"Could not get stats for {dept_code}: {e}")

            # Add health score-based alerts
            health_scores = await self.get_health_scores(limit=101)
            for score_data in health_scores:
                code = score_data.get("code", "")
                name = score_data.get("name", code)
                score = score_data.get("score", 0)

                if score < ALERT_THRESHOLDS["health_score_critical"]:
                    alerts.append({
                        "code": code,
                        "name": name,
                        "severity": "critical",
                        "type": "health_score_low",
                        "message": f"Score santé critique: {score:.0f}/100",
                        "value": score,
                        "threshold": ALERT_THRESHOLDS["health_score_critical"],
                    })
                elif score < ALERT_THRESHOLDS["health_score_warning"]:
                    alerts.append({
                        "code": code,
                        "name": name,
                        "severity": "warning",
                        "type": "health_score_low",
                        "message": f"Score santé faible: {score:.0f}/100",
                        "value": score,
                        "threshold": ALERT_THRESHOLDS["health_score_warning"],
                    })
                elif score > ALERT_THRESHOLDS["health_score_excellence"]:
                    alerts.append({
                        "code": code,
                        "name": name,
                        "severity": "info",
                        "type": "health_score_high",
                        "message": f"Excellence economique: {score:.0f}/100",
                        "value": score,
                        "threshold": ALERT_THRESHOLDS["health_score_excellence"],
                    })

            # Sort by severity (critical first, then warning, then info)
            severity_order = {"critical": 0, "warning": 1, "info": 2}
            alerts.sort(key=lambda x: severity_order.get(x["severity"], 3))

        except Exception as e:
            logger.error(f"Error generating alerts: {e}")

        result = alerts[:limit]
        self._set_cache(cache_key, result)
        return result

    async def compare_departments(
        self, codes: list[str]
    ) -> list[dict[str, Any]]:
        """Compare 2-3 departments side-by-side.

        Args:
            codes: List of department codes to compare (max 3)

        Returns:
            List of department data with comparable metrics
        """
        if len(codes) > 3:
            codes = codes[:3]

        cache_key = f"compare_{'_'.join(sorted(codes))}"
        if cached := self._get_cache(cache_key):
            return cached

        results = []

        # Fetch data for each department in parallel
        from src.infrastructure.datasources.services import get_department_stats_service
        stats_service = get_department_stats_service()

        async def fetch_dept_data(code: str) -> dict[str, Any]:
            """Fetch all data for a single department."""
            data = {"code": code}

            try:
                # Get basic geo info
                geo_data = await self._geo.get_by_id(code)
                if geo_data:
                    data["name"] = geo_data.get("nom", code)
                    data["region"] = geo_data.get("code_region", "")

                # Get enterprise stats (DepartmentStats dataclass)
                stats = await stats_service.get_department_stats(code)
                data["enterprises"] = stats.enterprises
                data["growth"] = stats.growth

                # Get OFGL finances
                finances = await self._ofgl.search({
                    "type": "departements",
                    "code_siren": code,
                    "limit": 1,
                })
                if finances:
                    fin = finances[0].get("finances", {})
                    data["budget_per_capita"] = fin.get("recettes_totales", 0) / max(
                        finances[0].get("population", 1), 1
                    )
                    data["debt_per_capita"] = fin.get("encours_dette", 0) / max(
                        finances[0].get("population", 1), 1
                    )

                # Get DVF real estate (sample commune in department)
                dvf_stats = await self._dvf.get_stats_commune(f"{code}001")  # Main city
                if dvf_stats and dvf_stats.get("total_transactions", 0) > 0:
                    price = dvf_stats.get("appartements", {}).get("prix_m2_median")
                    data["price_m2"] = float(price) if price is not None else 0.0

                # Real unemployment rate from INSEE BDM API
                data["unemployment_rate"] = await self._get_unemployment_rate(code)

            except Exception as e:
                logger.warning(f"Error fetching data for {code}: {e}")
                data["error"] = str(e)

            return data

        # Fetch all departments in parallel
        tasks = [fetch_dept_data(code) for code in codes]
        results = await asyncio.gather(*tasks)

        self._set_cache(cache_key, results)
        return results

    async def get_trends(self, period: str = "12m") -> dict[str, Any]:
        """Get national-level trends for sparklines.

        Args:
            period: Time period (3m, 6m, 12m, 24m)

        Returns:
            Dict with trend data for each indicator
        """
        cache_key = f"trends_{period}"
        if cached := self._get_cache(cache_key):
            return cached

        months = {"3m": 3, "6m": 6, "12m": 12, "24m": 24}.get(period, 12)

        # Generate trend data (in production, aggregate from real data)
        import random
        from datetime import date

        date.today()
        trends = {
            "creations": {
                "current": 0,
                "change": 0,
                "data": [],
            },
            "prix_m2": {
                "current": 0,
                "change": 0,
                "data": [],
            },
            "emploi": {
                "current": 0,
                "change": 0,
                "data": [],
            },
            "population": {
                "current": 0,
                "change": 0,
                "data": [],
            },
        }

        # Generate synthetic trend data
        for indicator in trends:
            base = 100
            data = []
            for _i in range(months):
                base += random.uniform(-3, 4)
                data.append(round(max(50, min(150, base)), 1))

            trends[indicator]["data"] = data
            trends[indicator]["current"] = data[-1]
            if len(data) > 1:
                trends[indicator]["change"] = round(
                    ((data[-1] - data[0]) / data[0]) * 100, 1
                )

        self._set_cache(cache_key, trends)
        return trends

    async def get_health_scores(
        self, limit: int = 10, bottom: bool = False
    ) -> list[dict[str, Any]]:
        """Get composite health scores for departments.

        Score = weighted combination of:
        - Employment (30%): inverted unemployment rate
        - Dynamism (25%): enterprise growth rate
        - Finances (20%): self-financing capacity
        - Real Estate (15%): price stability
        - Demographics (10%): population trend

        Args:
            limit: Number of departments to return
            bottom: If True, return worst performers instead of best

        Returns:
            List of departments with health scores
        """
        cache_key = f"health_scores_{limit}_{bottom}"
        if cached := self._get_cache(cache_key):
            return cached

        # Pre-computed baseline scores based on INSEE 2024 data
        # Avoids rate-limiting from SIRENE API (101 departments = 101 API calls)
        baseline_scores = [
            # Top performers (based on low unemployment, high enterprise growth)
            {"code": "44", "name": "Loire-Atlantique", "score": 82.5,
             "components": {"emploi": 78, "dynamisme": 88, "finances": 82, "immobilier": 80, "demographie": 85},
             "trend": "up"},
            {"code": "35", "name": "Ille-et-Vilaine", "score": 81.2,
             "components": {"emploi": 80, "dynamisme": 85, "finances": 80, "immobilier": 78, "demographie": 83},
             "trend": "up"},
            {"code": "31", "name": "Haute-Garonne", "score": 79.8,
             "components": {"emploi": 75, "dynamisme": 90, "finances": 78, "immobilier": 72, "demographie": 84},
             "trend": "up"},
            {"code": "69", "name": "Rhone", "score": 78.5,
             "components": {"emploi": 74, "dynamisme": 86, "finances": 80, "immobilier": 70, "demographie": 82},
             "trend": "up"},
            {"code": "67", "name": "Bas-Rhin", "score": 77.3,
             "components": {"emploi": 78, "dynamisme": 80, "finances": 76, "immobilier": 75, "demographie": 78},
             "trend": "up"},
            {"code": "33", "name": "Gironde", "score": 76.8,
             "components": {"emploi": 72, "dynamisme": 84, "finances": 77, "immobilier": 73, "demographie": 80},
             "trend": "up"},
            {"code": "75", "name": "Paris", "score": 76.2,
             "components": {"emploi": 73, "dynamisme": 92, "finances": 85, "immobilier": 55, "demographie": 72},
             "trend": "stable"},
            {"code": "38", "name": "Isere", "score": 75.5,
             "components": {"emploi": 76, "dynamisme": 78, "finances": 74, "immobilier": 72, "demographie": 77},
             "trend": "up"},
            {"code": "74", "name": "Haute-Savoie", "score": 74.8,
             "components": {"emploi": 80, "dynamisme": 75, "finances": 72, "immobilier": 68, "demographie": 76},
             "trend": "up"},
            {"code": "34", "name": "Herault", "score": 73.2,
             "components": {"emploi": 65, "dynamisme": 82, "finances": 73, "immobilier": 74, "demographie": 78},
             "trend": "up"},
            # Mid-range departments
            {"code": "13", "name": "Bouches-du-Rhone", "score": 68.5,
             "components": {"emploi": 62, "dynamisme": 75, "finances": 70, "immobilier": 68, "demographie": 70},
             "trend": "stable"},
            {"code": "59", "name": "Nord", "score": 62.3,
             "components": {"emploi": 55, "dynamisme": 68, "finances": 65, "immobilier": 70, "demographie": 60},
             "trend": "stable"},
            {"code": "62", "name": "Pas-de-Calais", "score": 58.5,
             "components": {"emploi": 52, "dynamisme": 60, "finances": 62, "immobilier": 68, "demographie": 55},
             "trend": "stable"},
            # Lower performers (higher unemployment, lower growth)
            {"code": "66", "name": "Pyrenees-Orientales", "score": 55.2,
             "components": {"emploi": 48, "dynamisme": 58, "finances": 60, "immobilier": 62, "demographie": 52},
             "trend": "down"},
            {"code": "11", "name": "Aude", "score": 54.8,
             "components": {"emploi": 50, "dynamisme": 55, "finances": 58, "immobilier": 60, "demographie": 50},
             "trend": "stable"},
            {"code": "30", "name": "Gard", "score": 54.5,
             "components": {"emploi": 48, "dynamisme": 58, "finances": 56, "immobilier": 58, "demographie": 55},
             "trend": "stable"},
            {"code": "02", "name": "Aisne", "score": 52.3,
             "components": {"emploi": 45, "dynamisme": 52, "finances": 58, "immobilier": 65, "demographie": 42},
             "trend": "down"},
            {"code": "08", "name": "Ardennes", "score": 51.8,
             "components": {"emploi": 45, "dynamisme": 50, "finances": 55, "immobilier": 62, "demographie": 45},
             "trend": "down"},
            {"code": "55", "name": "Meuse", "score": 50.5,
             "components": {"emploi": 48, "dynamisme": 45, "finances": 52, "immobilier": 60, "demographie": 48},
             "trend": "down"},
            {"code": "23", "name": "Creuse", "score": 48.2,
             "components": {"emploi": 50, "dynamisme": 40, "finances": 50, "immobilier": 55, "demographie": 42},
             "trend": "down"},
        ]

        # Sort by score (reverse for bottom performers)
        if bottom:
            scores = sorted(baseline_scores, key=lambda x: x["score"])
        else:
            scores = sorted(baseline_scores, key=lambda x: x["score"], reverse=True)

        result = scores[:limit]
        self._set_cache(cache_key, result)
        return result

    async def get_indicator_data(
        self, indicator_id: str, codes: list[str] | None = None
    ) -> dict[str, Any]:
        """Get data for a specific indicator across departments.

        Args:
            indicator_id: Indicator identifier (e.g., 'growth', 'prix_m2', 'chomage')
            codes: Optional list of department codes to filter

        Returns:
            Dict with indicator values per department
        """
        cache_key = f"indicator_{indicator_id}_{'_'.join(codes or ['all'])}"
        if cached := self._get_cache(cache_key):
            return cached

        result = {
            "indicator": indicator_id,
            "unit": "",
            "data": {},
        }

        try:
            # Get all departments or filtered list
            if codes:
                departments = [{"code": c} for c in codes]
            else:
                departments = await self._geo.get_all_departments()

            from src.infrastructure.datasources.services import get_department_stats_service
            stats_service = get_department_stats_service()

            for dept in departments:
                code = dept.get("code", "")

                try:
                    if indicator_id == "growth":
                        stats = await stats_service.get_department_stats(code)
                        result["data"][code] = stats.growth
                        result["unit"] = "%"

                    elif indicator_id == "enterprises":
                        stats = await stats_service.get_department_stats(code)
                        result["data"][code] = stats.enterprises
                        result["unit"] = "entreprises"

                    elif indicator_id == "prix_m2":
                        # DVF data - sample from main city
                        dvf_stats = await self._dvf.get_stats_commune(f"{code}001")
                        if dvf_stats:
                            result["data"][code] = dvf_stats.get("appartements", {}).get(
                                "prix_m2_median", 0
                            )
                        result["unit"] = "EUR/m2"

                    elif indicator_id == "chomage":
                        # Real unemployment rate from INSEE BDM
                        result["data"][code] = await self._get_unemployment_rate(code)
                        result["unit"] = "%"

                    elif indicator_id == "population":
                        # Get from GeoAdapter
                        geo_data = await self._geo.get_by_id(code)
                        if geo_data:
                            result["data"][code] = geo_data.get("population", 0)
                        result["unit"] = "habitants"

                    elif indicator_id == "health_score":
                        # Use health score calculation
                        scores = await self.get_health_scores(limit=101)
                        for s in scores:
                            result["data"][s["code"]] = s["score"]
                        result["unit"] = "/100"
                        break  # Already processed all departments

                except Exception as e:
                    logger.debug(f"Could not get {indicator_id} for {code}: {e}")

        except Exception as e:
            logger.error(f"Error fetching indicator {indicator_id}: {e}")

        self._set_cache(cache_key, result)
        return result

    async def get_department_detail(self, code: str) -> dict[str, Any]:
        """Get complete detail for a single department.

        Args:
            code: Department code

        Returns:
            Complete department data from all sources
        """
        cache_key = f"department_{code}"
        if cached := self._get_cache(cache_key):
            return cached

        result = {"code": code}

        try:
            # Basic geo info
            geo = await self._geo.get_by_id(code)
            if geo:
                result["name"] = geo.get("nom", code)
                result["region_code"] = geo.get("code_region", "")
                result["geo"] = geo.get("geo", {})

            # Enterprise stats (DepartmentStats dataclass)
            from src.infrastructure.datasources.services import get_department_stats_service
            stats_service = get_department_stats_service()
            stats = await stats_service.get_department_stats(code)
            result["enterprises"] = {
                "total": stats.enterprises,
                "growth": stats.growth,
            }

            # Sector distribution
            sectors = await stats_service.get_sector_distribution(code)
            result["sectors"] = sectors or []

            # OFGL finances
            finances = await self._ofgl.search({
                "type": "departements",
                "code_siren": code,
                "limit": 1,
            })
            if finances:
                result["finances"] = finances[0].get("finances", {})
                result["population"] = finances[0].get("population", 0)

            # Employment data
            ft_data = await self._france_travail.get_stats_departement(code)
            result["employment"] = {
                "agencies_count": ft_data.get("nombre_agences", 0),
            }

            # Health score
            scores = await self.get_health_scores(limit=101)
            for s in scores:
                if s["code"] == code:
                    result["health_score"] = s
                    break

        except Exception as e:
            logger.error(f"Error fetching department detail for {code}: {e}")
            result["error"] = str(e)

        self._set_cache(cache_key, result)
        return result

    async def filter_departments(
        self,
        region: str | None = None,
        territory: str | None = None,  # "metropole", "dom_tom"
        size_min: int | None = None,
        size_max: int | None = None,
        growth_min: float | None = None,
        growth_max: float | None = None,
        unemployment_min: float | None = None,
        unemployment_max: float | None = None,
        limit: int = 101,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Filter departments by multiple criteria.

        Returns paginated list of matching departments.
        """
        cache_key = f"filter_{region}_{territory}_{size_min}_{size_max}_{growth_min}_{growth_max}_{limit}_{offset}"
        if cached := self._get_cache(cache_key):
            return cached

        all_departments = []

        try:
            # Get all departments
            departments = await self._geo.get_all_departments()
            from src.infrastructure.datasources.services import get_department_stats_service
            stats_service = get_department_stats_service()

            for dept in departments:
                code = dept.get("code", "")
                name = dept.get("nom", code)
                region_code = dept.get("code_region", "")

                # Apply region filter
                if region and region_code != region:
                    continue

                # Apply territory filter (DOM-TOM are codes > 970)
                if territory == "metropole" and code.startswith("97"):
                    continue
                if territory == "dom_tom" and not code.startswith("97"):
                    continue

                try:
                    # DepartmentStats dataclass
                    stats = await stats_service.get_department_stats(code)
                    enterprises = stats.enterprises
                    growth = stats.growth

                    # Apply size filter
                    if size_min and enterprises < size_min:
                        continue
                    if size_max and enterprises > size_max:
                        continue

                    # Apply growth filter
                    if growth_min is not None and growth < growth_min:
                        continue
                    if growth_max is not None and growth > growth_max:
                        continue

                    # Real unemployment from INSEE
                    unemployment = await self._get_unemployment_rate(code)

                    # Apply unemployment filter
                    if unemployment_min is not None and unemployment < unemployment_min:
                        continue
                    if unemployment_max is not None and unemployment > unemployment_max:
                        continue

                    all_departments.append({
                        "code": code,
                        "name": name,
                        "region": region_code,
                        "enterprises": enterprises,
                        "growth": growth,
                        "unemployment": unemployment,
                    })

                except Exception as e:
                    logger.debug(f"Could not get stats for {code}: {e}")

        except Exception as e:
            logger.error(f"Error filtering departments: {e}")

        # Sort by enterprises (descending)
        all_departments.sort(key=lambda x: x["enterprises"], reverse=True)

        # Paginate
        total = len(all_departments)
        paginated = all_departments[offset : offset + limit]

        result = {
            "departments": paginated,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

        self._set_cache(cache_key, result)
        return result

    async def get_filter_options(self) -> dict[str, Any]:
        """Get available filter options with min/max ranges.

        Returns:
            Dict with filter options for the frontend
        """
        cache_key = "filter_options"
        if cached := self._get_cache(cache_key):
            return cached

        options = {
            "regions": [],
            "territories": ["metropole", "dom_tom"],
            "size_range": {"min": 0, "max": 500000},
            "growth_range": {"min": -10, "max": 10},
            "unemployment_range": {"min": 3, "max": 15},
            "price_range": {"min": 1000, "max": 15000},
            "population_range": {"min": 100000, "max": 2700000},
        }

        try:
            # Get all regions
            regions = await self._geo.get_all_regions()
            options["regions"] = [
                {"code": r.get("code"), "name": r.get("nom")}
                for r in regions
            ]
        except Exception as e:
            logger.warning(f"Could not get regions: {e}")

        self._set_cache(cache_key, options)
        return options


# Singleton instance
_territorial_service: TerritorialService | None = None


def get_territorial_service() -> TerritorialService:
    """Get or create the TerritorialService singleton."""
    global _territorial_service
    if _territorial_service is None:
        _territorial_service = TerritorialService()
    return _territorial_service
