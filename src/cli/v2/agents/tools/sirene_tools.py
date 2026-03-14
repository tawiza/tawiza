"""Sirene tools for enterprise search and enrichment.

Uses the public API recherche-entreprises.api.gouv.fr which aggregates:
- Sirene (INSEE) - Base entreprises
- RNA - Associations
- RNE - Entreprises artisanales
- And more...

No API key required, rate limit: 7 requests/second.
"""

from typing import Any

import httpx
from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry

# API Base URL - No auth needed
API_BASE = "https://recherche-entreprises.api.gouv.fr"


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

# Department codes (most common ones)
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
    # Aliases
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

    # Normalize to NFD (decomposed form), then remove combining marks
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").lower().strip()


def _normalize_region(region: str) -> str | None:
    """Convert region name to INSEE code."""
    region_normalized = _normalize_text(region)

    # Direct code
    if region_normalized in REGION_CODES.values():
        return region_normalized

    # Name lookup (exact or contains)
    for name, code in REGION_CODES.items():
        if name in region_normalized or region_normalized in name:
            return code

    # Partial match (any word in the hyphenated name)
    for name, code in REGION_CODES.items():
        if any(word in region_normalized for word in name.split("-")):
            return code

    return None


def _normalize_department(dept: str) -> str | None:
    """Convert department name or code to INSEE code."""
    dept_normalized = _normalize_text(dept)

    # Direct code (01-95, 2A, 2B)
    if dept_normalized.isdigit() and 1 <= int(dept_normalized) <= 95:
        return dept_normalized.zfill(2)
    if dept_normalized in ("2a", "2b"):
        return dept_normalized.upper()

    # Exact name lookup first
    if dept_normalized in DEPARTMENT_CODES:
        return DEPARTMENT_CODES[dept_normalized]

    # Partial match: prefer exact word match (e.g., "rhone" should match "rhone" not "bouches-du-rhone")
    # Split hyphenated names and check for exact word
    for name, code in DEPARTMENT_CODES.items():
        name_parts = name.split("-")
        if dept_normalized in name_parts:
            return code

    # Last resort: substring match
    for name, code in DEPARTMENT_CODES.items():
        if dept_normalized in name:
            return code

    return None


def _parse_entreprise(data: dict) -> dict:
    """Parse raw API response into clean enterprise dict."""
    siege = data.get("siege", {})

    return {
        "siren": data.get("siren"),
        "siret": siege.get("siret"),
        "nom": data.get("nom_complet"),
        "nom_raison_sociale": data.get("nom_raison_sociale"),
        "nature_juridique": data.get("nature_juridique"),
        "activite_principale": data.get("activite_principale"),
        "libelle_activite": siege.get("libelle_activite_principale"),
        "section_activite": data.get("section_activite_principale"),
        "effectif": data.get("tranche_effectif_salarie"),
        "date_creation": data.get("date_creation"),
        "etat_administratif": data.get("etat_administratif"),
        "adresse": {
            "rue": siege.get("adresse"),
            "code_postal": siege.get("code_postal"),
            "commune": siege.get("libelle_commune"),
            "departement": siege.get("departement"),
            "region": siege.get("region"),
        },
        "geo": {
            "lat": float(siege.get("latitude")) if siege.get("latitude") else None,
            "lon": float(siege.get("longitude")) if siege.get("longitude") else None,
        }
        if siege.get("latitude")
        else None,
        "dirigeants": data.get("dirigeants", []),
        "finances": {
            "ca": data.get("finances", {}).get("ca"),
            "resultat": data.get("finances", {}).get("resultat_net"),
        }
        if data.get("finances")
        else None,
        "est_association": data.get("complements", {}).get("est_association", False),
        "est_ess": data.get("complements", {}).get("est_ess", False),
    }


def register_sirene_tools(registry: ToolRegistry) -> None:
    """Register Sirene enterprise tools."""

    async def sirene_search(
        query: str,
        region: str | None = None,
        activite: str | None = None,
        effectif_min: str | None = None,
        limite: int = 20,
    ) -> dict[str, Any]:
        """Search enterprises in the French Sirene database.

        Args:
            query: Search terms (company name, activity, keywords)
            region: Region name or code (e.g., "Hauts-de-France" or "32")
            activite: NAF activity code filter (e.g., "62.01Z" for programming)
            effectif_min: Minimum employee range ("10", "50", "100", "250", "500")
            limite: Maximum results (default 20, max 25)

        Returns:
            Dict with enterprises list and metadata
        """
        try:
            params = {
                "q": query,
                "per_page": min(limite, 25),
                "page": 1,
            }

            # Region or department filter
            if region:
                region_code = _normalize_region(region)
                if region_code:
                    params["region"] = region_code
                else:
                    # Try as department (e.g., "Rhône" -> "69")
                    dept_code = _normalize_department(region)
                    if dept_code:
                        params["departement"] = dept_code
                        logger.debug(f"Using department filter: {region} -> {dept_code}")
                    else:
                        logger.warning(f"Unknown region/department: {region}")

            # Activity filter (NAF code)
            # API uses different params for section codes vs full NAF codes:
            # - section_activite_principale: for section codes like "J", "47", "G" (1-2 chars)
            # - activite_principale: for full NAF codes like "62.01Z" (with dot)
            # Note: API only accepts ONE code, not comma-separated lists
            if activite:
                # Handle comma-separated codes (LLM often sends multiple)
                # Take the first code only since API doesn't support multiple
                first_code = activite.split(",")[0].strip().upper()
                if len(first_code) <= 2 or (len(first_code) == 1 and first_code.isalpha()):
                    # Section code (e.g., "J", "G")
                    params["section_activite_principale"] = first_code
                else:
                    # Full NAF code (e.g., "62.01Z")
                    params["activite_principale"] = first_code

            # Employee range filter
            if effectif_min:
                params["tranche_effectif_salarie"] = effectif_min

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{API_BASE}/search", params=params)

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
            logger.error(f"Sirene search failed: {e}")
            return {"success": False, "error": str(e)}

    async def sirene_get(siret: str) -> dict[str, Any]:
        """Get detailed information about a specific enterprise by SIRET.

        Args:
            siret: The 14-digit SIRET number

        Returns:
            Dict with full enterprise details
        """
        try:
            # Clean SIRET (remove spaces)
            siret_clean = siret.replace(" ", "").replace(".", "")

            if len(siret_clean) != 14:
                return {
                    "success": False,
                    "error": f"Invalid SIRET: must be 14 digits, got {len(siret_clean)}",
                }

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Search by SIRET
                response = await client.get(
                    f"{API_BASE}/search", params={"q": siret_clean, "per_page": 1}
                )

                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if not results:
                    return {
                        "success": False,
                        "error": f"No enterprise found for SIRET {siret_clean}",
                    }

                enterprise = _parse_entreprise(results[0])

                return {
                    "success": True,
                    "enterprise": enterprise,
                }

        except Exception as e:
            logger.error(f"Sirene get failed: {e}")
            return {"success": False, "error": str(e)}

    async def sirene_by_location(
        commune: str,
        activite: str | None = None,
        rayon_km: int = 10,
        limite: int = 20,
    ) -> dict[str, Any]:
        """Search enterprises near a location (city name).

        Args:
            commune: City name (e.g., "Lille", "Nantes")
            activite: Optional NAF activity code filter
            rayon_km: Search radius in km (default 10)
            limite: Maximum results

        Returns:
            Dict with enterprises list
        """
        try:
            params = {
                "q": "",
                "commune": commune,
                "per_page": min(limite, 25),
            }

            if activite:
                first_code = activite.split(",")[0].strip().upper()
                if len(first_code) <= 2 or (len(first_code) == 1 and first_code.isalpha()):
                    params["section_activite_principale"] = first_code
                else:
                    params["activite_principale"] = first_code

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{API_BASE}/search", params=params)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                enterprises = [_parse_entreprise(r) for r in results]

                return {
                    "success": True,
                    "commune": commune,
                    "total_count": data.get("total_results", 0),
                    "enterprises": enterprises,
                    "count": len(enterprises),
                }

        except Exception as e:
            logger.error(f"Sirene by location failed: {e}")
            return {"success": False, "error": str(e)}

    async def sirene_naf_codes(query: str) -> dict[str, Any]:
        """Search for NAF activity codes by description.

        Args:
            query: Activity description (e.g., "programmation", "intelligence artificielle")

        Returns:
            Dict with matching NAF codes
        """
        # Common NAF codes for tech/innovation
        naf_database = {
            "62.01Z": "Programmation informatique",
            "62.02A": "Conseil en systèmes et logiciels",
            "62.02B": "Tierce maintenance informatique",
            "62.03Z": "Gestion d'installations informatiques",
            "62.09Z": "Autres activités informatiques",
            "63.11Z": "Traitement de données, hébergement",
            "63.12Z": "Portails Internet",
            "71.12B": "Ingénierie, études techniques",
            "71.20B": "Analyses, essais et inspections",
            "72.11Z": "Recherche en biotechnologie",
            "72.19Z": "R&D sciences physiques et naturelles",
            "72.20Z": "R&D sciences humaines et sociales",
            "73.11Z": "Activités des agences de publicité",
            "73.20Z": "Études de marché et sondages",
            "74.10Z": "Activités spécialisées de design",
            "74.90B": "Activités spécialisées scientifiques diverses",
            "85.42Z": "Enseignement supérieur",
        }

        query_lower = query.lower()
        matches = []

        for code, description in naf_database.items():
            if query_lower in description.lower():
                matches.append({"code": code, "description": description})

        # Also search for keywords
        keyword_mapping = {
            "ia": ["62.01Z", "62.02A", "72.19Z"],
            "intelligence artificielle": ["62.01Z", "62.02A", "72.19Z"],
            "startup": ["62.01Z", "62.02A", "72.19Z", "71.12B"],
            "tech": ["62.01Z", "62.02A", "63.11Z", "63.12Z"],
            "recherche": ["72.11Z", "72.19Z", "72.20Z"],
            "laboratoire": ["72.11Z", "72.19Z"],
            "innovation": ["62.01Z", "71.12B", "72.19Z"],
            "biotechnologie": ["72.11Z"],
            "énergie": ["71.12B", "72.19Z"],
            "hydrogène": ["71.12B", "72.19Z", "74.90B"],
        }

        for keyword, codes in keyword_mapping.items():
            if keyword in query_lower:
                for code in codes:
                    if (
                        code in naf_database
                        and {"code": code, "description": naf_database[code]} not in matches
                    ):
                        matches.append({"code": code, "description": naf_database[code]})

        return {
            "success": True,
            "query": query,
            "naf_codes": matches[:10],
            "count": len(matches),
        }

    # Register tools
    registry._tools["sirene.search"] = Tool(
        name="sirene.search",
        func=sirene_search,
        category=ToolCategory.DATA,
        description="Search French enterprises by name, activity, region. Returns company details, location, employees.",
    )

    registry._tools["sirene.get"] = Tool(
        name="sirene.get",
        func=sirene_get,
        category=ToolCategory.DATA,
        description="Get detailed enterprise information by SIRET number (14 digits).",
    )

    registry._tools["sirene.by_location"] = Tool(
        name="sirene.by_location",
        func=sirene_by_location,
        category=ToolCategory.DATA,
        description="Find enterprises near a city. Useful for local ecosystem mapping.",
    )

    registry._tools["sirene.naf_codes"] = Tool(
        name="sirene.naf_codes",
        func=sirene_naf_codes,
        category=ToolCategory.DATA,
        description="Find NAF activity codes by description (e.g., 'IA', 'startup', 'recherche').",
    )

    logger.debug("Registered 4 sirene tools")
