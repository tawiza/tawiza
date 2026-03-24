"""Camel AI Tools wrappers for territorial intelligence.

Wraps existing Tawiza tools (Sirene, Geo, Subventions) as Camel FunctionTools.

Uses a thread pool executor to run async code from sync context,
avoiding event loop conflicts with uvloop (used by FastAPI/Uvicorn).

IMPORTANT: Coroutines must be created INSIDE the worker thread, not passed in.
This is because httpx/anyio maintain thread-local state that breaks if the
coroutine is created in one thread but executed in another.
"""

import asyncio
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor

from camel.toolkits import FunctionTool
from loguru import logger

# Thread pool for running async code in sync functions
# Using a dedicated thread avoids uvloop/nest_asyncio conflicts
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="territorial_tools")


def _run_async_factory(async_func: Callable[..., Coroutine], *args, **kwargs):
    """Run an async function in a separate thread with its own event loop.

    CRITICAL: Takes an async FUNCTION (not coroutine) and creates the coroutine
    inside the worker thread. This prevents httpx/anyio thread-local state issues.

    Args:
        async_func: An async function (not a coroutine object)
        *args: Positional arguments to pass to async_func
        **kwargs: Keyword arguments to pass to async_func

    Returns:
        The result of the async function
    """

    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Create the coroutine INSIDE this thread
            coro = async_func(*args, **kwargs)
            return loop.run_until_complete(coro)
        except Exception as e:
            logger.error(f"Async execution failed in thread: {type(e).__name__}: {e}")
            raise
        finally:
            loop.close()

    future = _executor.submit(run_in_thread)
    return future.result(timeout=60)  # 60s timeout


# ============================================================================
# SIRENE API DIRECT ACCESS (sync httpx to avoid event loop conflicts)
# ============================================================================

# API Base URL - No auth needed
SIRENE_API_BASE = "https://recherche-entreprises.api.gouv.fr"

# Region codes for filtering
REGION_CODES = {
    "hauts-de-france": "32",
    "ile-de-france": "11",
    "auvergne-rhone-alpes": "84",
    "nouvelle-aquitaine": "75",
    "occitanie": "76",
    "bretagne": "53",
    "normandie": "28",
    "pays-de-la-loire": "52",
    "grand-est": "44",
    "bourgogne-franche-comte": "27",
    "centre-val-de-loire": "24",
    "provence-alpes-cote-d-azur": "93",
    "corse": "94",
}

# Tranche effectif codes (INSEE nomenclature)
# See: https://www.sirene.fr/static-resources/htm/v_effectif.htm
EFFECTIF_TRANCHES = {
    "0": "00",  # 0 salarié
    "1": "01",  # 1-2 salariés
    "3": "02",  # 3-5 salariés
    "6": "03",  # 6-9 salariés
    "10": "11",  # 10-19 salariés
    "20": "12",  # 20-49 salariés
    "50": "21",  # 50-99 salariés
    "100": "22",  # 100-199 salariés
    "200": "31",  # 200-249 salariés
    "250": "32",  # 250-499 salariés
    "500": "41",  # 500-999 salariés
    "1000": "42",  # 1000-1999 salariés
    "2000": "51",  # 2000-4999 salariés
    "5000": "52",  # 5000-9999 salariés
    "10000": "53",  # 10000+ salariés
}

# Sorted thresholds for effectif mapping
_EFFECTIF_THRESHOLDS = [0, 1, 3, 6, 10, 20, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000]

# Department codes (all 95 French departments + aliases)
DEPARTMENT_CODES = {
    "ain": "01",
    "aisne": "02",
    "allier": "03",
    "alpes-de-haute-provence": "04",
    "hautes-alpes": "05",
    "alpes-maritimes": "06",
    "ardeche": "07",
    "ardennes": "08",
    "ariege": "09",
    "aube": "10",
    "aude": "11",
    "aveyron": "12",
    "bouches-du-rhone": "13",
    "calvados": "14",
    "cantal": "15",
    "charente": "16",
    "charente-maritime": "17",
    "cher": "18",
    "correze": "19",
    "corse-du-sud": "2A",
    "haute-corse": "2B",
    "cote-d-or": "21",
    "cotes-d-armor": "22",
    "creuse": "23",
    "dordogne": "24",
    "doubs": "25",
    "drome": "26",
    "eure": "27",
    "eure-et-loir": "28",
    "finistere": "29",
    "gard": "30",
    "haute-garonne": "31",
    "gers": "32",
    "gironde": "33",
    "herault": "34",
    "ille-et-vilaine": "35",
    "indre": "36",
    "indre-et-loire": "37",
    "isere": "38",
    "jura": "39",
    "landes": "40",
    "loir-et-cher": "41",
    "loire": "42",
    "haute-loire": "43",
    "loire-atlantique": "44",
    "loiret": "45",
    "lot": "46",
    "lot-et-garonne": "47",
    "lozere": "48",
    "maine-et-loire": "49",
    "manche": "50",
    "marne": "51",
    "haute-marne": "52",
    "mayenne": "53",
    "meurthe-et-moselle": "54",
    "meuse": "55",
    "morbihan": "56",
    "moselle": "57",
    "nievre": "58",
    "nord": "59",
    "oise": "60",
    "orne": "61",
    "pas-de-calais": "62",
    "puy-de-dome": "63",
    "pyrenees-atlantiques": "64",
    "hautes-pyrenees": "65",
    "pyrenees-orientales": "66",
    "bas-rhin": "67",
    "haut-rhin": "68",
    "rhone": "69",
    "haute-saone": "70",
    "saone-et-loire": "71",
    "sarthe": "72",
    "savoie": "73",
    "haute-savoie": "74",
    "paris": "75",
    "seine-maritime": "76",
    "seine-et-marne": "77",
    "yvelines": "78",
    "deux-sevres": "79",
    "somme": "80",
    "tarn": "81",
    "tarn-et-garonne": "82",
    "var": "83",
    "vaucluse": "84",
    "vendee": "85",
    "vienne": "86",
    "haute-vienne": "87",
    "vosges": "88",
    "yonne": "89",
    "territoire-de-belfort": "90",
    "essonne": "91",
    "hauts-de-seine": "92",
    "seine-saint-denis": "93",
    "val-de-marne": "94",
    "val-d-oise": "95",
    # City aliases
    "lyon": "69",
    "marseille": "13",
    "lille": "59",
    "toulouse": "31",
    "bordeaux": "33",
    "nantes": "44",
    "strasbourg": "67",
    "nice": "06",
}


def _normalize_text(text: str) -> str:
    """Remove accents and normalize text for matching."""
    import unicodedata

    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").lower().strip()


def _normalize_effectif(effectif_min: str) -> str | None:
    """Convert user-friendly workforce number to INSEE tranche code.

    The SIRENE API expects tranche codes (e.g., "11" for 10-19 employees),
    not raw numbers (e.g., "10"). This function maps user inputs to valid codes.

    Args:
        effectif_min: User-provided minimum workforce (e.g., "10", "50", "100")

    Returns:
        INSEE tranche code or None if invalid
    """
    if not effectif_min:
        return None

    # Direct code match (user may already know the codes)
    if effectif_min in EFFECTIF_TRANCHES.values():
        return effectif_min

    try:
        val = int(str(effectif_min).strip())
        # Find the highest threshold <= val
        for threshold in reversed(_EFFECTIF_THRESHOLDS):
            if val >= threshold:
                return EFFECTIF_TRANCHES[str(threshold)]
    except (ValueError, TypeError):
        logger.warning(f"Invalid effectif_min value: {effectif_min}")

    return None


def _normalize_department(dept: str) -> str | None:
    """Convert department name or code to INSEE code."""
    dept_normalized = _normalize_text(dept)

    # Direct numeric code
    if dept_normalized.isdigit() and 1 <= int(dept_normalized) <= 95:
        return dept_normalized.zfill(2)

    # Corsica special codes
    if dept_normalized in ("2a", "2b"):
        return dept_normalized.upper()

    # Exact match in dictionary
    if dept_normalized in DEPARTMENT_CODES:
        return DEPARTMENT_CODES[dept_normalized]

    # Match by word parts (e.g., "rhone" matches "rhone" but not "bouches-du-rhone")
    for name, code in DEPARTMENT_CODES.items():
        name_parts = name.split("-")
        if dept_normalized in name_parts:
            return code

    # Substring match as last resort
    for name, code in DEPARTMENT_CODES.items():
        if dept_normalized in name:
            return code

    return None


def _parse_entreprise(result: dict) -> dict:
    """Parse SIRENE API result into standardized format."""
    siege = result.get("siege", {})
    return {
        "siret": siege.get("siret", ""),
        "siren": result.get("siren", ""),
        "nom": result.get("nom_complet", ""),
        "nom_raison_sociale": result.get("nom_raison_sociale", ""),
        "activite_principale": siege.get("activite_principale", ""),
        "libelle_activite": siege.get("libelle_activite_principale", ""),
        "categorie_juridique": result.get("categorie_juridique", ""),
        "effectif": siege.get("tranche_effectif_salarie", ""),
        "date_creation": result.get("date_creation", ""),
        "adresse": siege.get("adresse", ""),
        "code_postal": siege.get("code_postal", ""),
        "commune": siege.get("commune", ""),
        "departement": siege.get("departement", ""),
        "region": siege.get("region", ""),
        "latitude": siege.get("latitude"),
        "longitude": siege.get("longitude"),
    }


def sirene_search(
    query: str,
    region: str | None = None,
    activite: str | None = None,
    effectif_min: str | None = None,
    limite: int = 20,
) -> dict:
    """Search French companies in the Sirene database.

    Uses synchronous HTTP to avoid event loop conflicts with uvloop.

    Args:
        query: Search terms (company name, activity, city, keywords)
        region: Filter by region name (e.g., "Hauts-de-France") or department (e.g., "Rhône")
        activite: Filter by NAF activity code (e.g., "62.01Z" for programming)
        effectif_min: Minimum workforce (e.g., "10", "50", "100")
        limite: Maximum number of results (default 20)

    Returns:
        Dictionary with:
        - enterprises: List of companies with SIRET, name, address, activity, workforce
        - total_count: Total number of matching companies
    """
    import httpx  # Import inside function to avoid module-level state issues

    try:
        params = {
            "q": query,
            "per_page": min(limite, 25),  # API max is 25
            "page": 1,
        }

        # Region/department filter
        if region:
            region_lower = _normalize_text(region)
            if region_lower in REGION_CODES:
                params["region"] = REGION_CODES[region_lower]
            else:
                dept_code = _normalize_department(region)
                if dept_code:
                    params["departement"] = dept_code
                    logger.debug(f"Using department filter: {region} -> {dept_code}")
                else:
                    logger.warning(f"Unknown region/department: {region}")

        # Activity filter
        if activite:
            first_code = activite.split(",")[0].strip().upper()
            if len(first_code) <= 2:
                params["section_activite_principale"] = first_code
            else:
                params["activite_principale"] = first_code

        # Employee filter - convert to INSEE tranche code
        if effectif_min:
            tranche_code = _normalize_effectif(effectif_min)
            if tranche_code:
                params["tranche_effectif_salarie"] = tranche_code
                logger.debug(f"Using effectif filter: {effectif_min} -> tranche {tranche_code}")
            else:
                logger.warning(f"Invalid effectif_min '{effectif_min}', skipping filter")

        # Use synchronous httpx client
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{SIRENE_API_BASE}/search", params=params)

            if response.status_code == 429:
                return {"success": False, "error": "Rate limit exceeded, try again later"}

            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            enterprises = [_parse_entreprise(r) for r in results]

            return {
                "success": True,
                "query": query,
                "total_count": data.get("total_results", 0),
                "page": data.get("page", 1),
                "per_page": data.get("per_page", 25),
                "enterprises": enterprises,
                "count": len(enterprises),
            }

    except httpx.HTTPStatusError as e:
        logger.error(f"Sirene API error: {e.response.status_code}")
        return {"success": False, "error": f"API error: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Sirene search failed: {type(e).__name__}: {e}")
        return {"success": False, "error": str(e)}


def sirene_get(siret: str) -> dict:
    """Get detailed information about a company by SIRET.

    Uses synchronous HTTP to avoid event loop conflicts.

    Args:
        siret: The 14-digit SIRET number

    Returns:
        Dictionary with company details: name, address, activity, workforce,
        legal form, creation date, financial data if available
    """
    import httpx  # Import inside function to avoid module-level state issues

    try:
        # Clean SIRET (remove spaces)
        siret_clean = siret.replace(" ", "").replace(".", "")

        if len(siret_clean) != 14:
            return {
                "success": False,
                "error": f"Invalid SIRET: must be 14 digits, got {len(siret_clean)}",
            }

        # Use synchronous httpx client
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{SIRENE_API_BASE}/search", params={"q": siret_clean, "per_page": 1}
            )

            if response.status_code == 429:
                return {"success": False, "error": "Rate limit exceeded, try again later"}

            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                return {"success": False, "error": f"No company found with SIRET {siret}"}

            # Return first (and should be only) result
            enterprise = _parse_entreprise(results[0])
            return {
                "success": True,
                "siret": siret,
                "enterprise": enterprise,
            }

    except httpx.HTTPStatusError as e:
        logger.error(f"Sirene API error: {e.response.status_code}")
        return {"success": False, "error": f"API error: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Sirene get failed: {type(e).__name__}: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# GEO TOOLS
# ============================================================================


def geo_locate(address: str) -> dict:
    """Geocode an address to get coordinates.

    Args:
        address: Full address string (e.g., "Place du Général de Gaulle, Lille")

    Returns:
        Dictionary with:
        - lat: Latitude
        - lon: Longitude
        - label: Formatted address
        - city: City name
        - postcode: Postal code
    """

    async def _locate(addr):
        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        registry = ToolRegistry()
        register_all_tools(registry)
        return await registry.execute("geo.locate", {"address": addr})

    return _run_async_factory(_locate, address)


def geo_map(locations: list[dict], title: str = "Map", style: str = "default") -> dict:
    """Generate an interactive Folium map with markers.

    Args:
        locations: List of location dicts with 'nom', 'lat', 'lon', and optionally 'type'
        title: Map title
        style: Map style ('default', 'satellite', 'dark')

    Returns:
        Dictionary with:
        - success: Boolean
        - file_path: Path to generated HTML file
        - markers: Number of markers on map
        - center: Map center coordinates
    """

    async def _map(locs, t, s):
        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        registry = ToolRegistry()
        register_all_tools(registry)
        return await registry.execute(
            "geo.map",
            {
                "locations": locs,
                "title": t,
                "style": s,
            },
        )

    return _run_async_factory(_map, locations, title, style)


def geo_search_commune(name: str) -> dict:
    """Search for a French commune (city/town).

    Args:
        name: Commune name to search

    Returns:
        Dictionary with commune info: name, INSEE code, postal codes,
        department, region, population, coordinates
    """

    async def _search(n):
        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        registry = ToolRegistry()
        register_all_tools(registry)
        return await registry.execute("geo.search_commune", {"name": n})

    return _run_async_factory(_search, name)


# ============================================================================
# SUBVENTIONS TOOLS
# ============================================================================


def aides_search(
    text: str, territory: str | None = None, categories: list[str] | None = None, limit: int = 10
) -> dict:
    """Search public subsidies and grants catalog.

    Args:
        text: Search keywords (e.g., "innovation", "emploi", "transition écologique")
        territory: Filter by territory (region, department)
        categories: Filter by categories (e.g., ["innovation", "formation"])
        limit: Maximum number of results

    Returns:
        Dictionary with:
        - aides: List of subsidies with name, description, eligibility, amounts
        - count: Number of results
    """

    async def _search(txt, terr, cats, lim):
        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        registry = ToolRegistry()
        register_all_tools(registry)
        return await registry.execute(
            "aides.search",
            {
                "text": txt,
                "territory": terr,
                "categories": cats,
                "limit": lim,
            },
        )

    return _run_async_factory(_search, text, territory, categories, limit)


def subventions_by_theme(theme: str, limit: int = 20) -> dict:
    """Get subsidies by thematic area.

    Args:
        theme: Theme name (e.g., "innovation", "environnement", "emploi", "numerique")
        limit: Maximum number of results

    Returns:
        Dictionary with subsidies for the theme
    """

    async def _search(th, lim):
        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        registry = ToolRegistry()
        register_all_tools(registry)
        return await registry.execute(
            "subventions.by_theme",
            {
                "theme": th,
                "limit": lim,
            },
        )

    return _run_async_factory(_search, theme, limit)


# ============================================================================
# TOOL REGISTRATION
# ============================================================================


def get_territorial_tools() -> list[FunctionTool]:
    """Get all territorial intelligence tools as Camel FunctionTools.

    Returns:
        List of FunctionTool instances ready for use with Camel agents
    """
    tools = [
        # Sirene
        FunctionTool(sirene_search),
        FunctionTool(sirene_get),
        # Geo
        FunctionTool(geo_locate),
        FunctionTool(geo_map),
        FunctionTool(geo_search_commune),
        # Subventions
        FunctionTool(aides_search),
        FunctionTool(subventions_by_theme),
    ]

    logger.debug(f"Registered {len(tools)} territorial tools for Camel AI")
    return tools


# Convenience exports
SIRENE_TOOLS = [FunctionTool(sirene_search), FunctionTool(sirene_get)]
GEO_TOOLS = [FunctionTool(geo_locate), FunctionTool(geo_map), FunctionTool(geo_search_commune)]
SUBVENTIONS_TOOLS = [FunctionTool(aides_search), FunctionTool(subventions_by_theme)]
