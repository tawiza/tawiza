"""French department/city/territory mappings and extraction utilities."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from loguru import logger

# Department name -> code mapping (French departements)
DEPT_NAME_TO_CODE = {
    "ain": "01",
    "aisne": "02",
    "allier": "03",
    "alpes-de-haute-provence": "04",
    "hautes-alpes": "05",
    "alpes-maritimes": "06",
    "ardeche": "07",
    "ardèche": "07",
    "ardennes": "08",
    "ariege": "09",
    "ariège": "09",
    "aube": "10",
    "aude": "11",
    "aveyron": "12",
    "bouches-du-rhone": "13",
    "bouches-du-rhône": "13",
    "calvados": "14",
    "cantal": "15",
    "charente": "16",
    "charente-maritime": "17",
    "cher": "18",
    "correze": "19",
    "corrèze": "19",
    "corse-du-sud": "2A",
    "haute-corse": "2B",
    "cote-d'or": "21",
    "côte-d'or": "21",
    "cotes-d'armor": "22",
    "côtes-d'armor": "22",
    "creuse": "23",
    "dordogne": "24",
    "doubs": "25",
    "drome": "26",
    "drôme": "26",
    "eure": "27",
    "eure-et-loir": "28",
    "finistere": "29",
    "finistère": "29",
    "gard": "30",
    "haute-garonne": "31",
    "gers": "32",
    "gironde": "33",
    "herault": "34",
    "hérault": "34",
    "ille-et-vilaine": "35",
    "indre": "36",
    "indre-et-loire": "37",
    "isere": "38",
    "isère": "38",
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
    "lozère": "48",
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
    "nièvre": "58",
    "nord": "59",
    "oise": "60",
    "orne": "61",
    "pas-de-calais": "62",
    "puy-de-dome": "63",
    "puy-de-dôme": "63",
    "pyrenees-atlantiques": "64",
    "pyrénées-atlantiques": "64",
    "hautes-pyrenees": "65",
    "hautes-pyrénées": "65",
    "pyrenees-orientales": "66",
    "pyrénées-orientales": "66",
    "bas-rhin": "67",
    "haut-rhin": "68",
    "rhone": "69",
    "rhône": "69",
    "haute-saone": "70",
    "haute-saône": "70",
    "saone-et-loire": "71",
    "saône-et-loire": "71",
    "sarthe": "72",
    "savoie": "73",
    "haute-savoie": "74",
    "paris": "75",
    "seine-maritime": "76",
    "seine-et-marne": "77",
    "yvelines": "78",
    "deux-sevres": "79",
    "deux-sèvres": "79",
    "somme": "80",
    "tarn": "81",
    "tarn-et-garonne": "82",
    "var": "83",
    "vaucluse": "84",
    "vendee": "85",
    "vendée": "85",
    "vienne": "86",
    "haute-vienne": "87",
    "vosges": "88",
    "yonne": "89",
    "territoire-de-belfort": "90",
    "essonne": "91",
    "hauts-de-seine": "92",
    "seine-saint-denis": "93",
    "val-de-marne": "94",
    "val-d'oise": "95",
    "guadeloupe": "971",
    "martinique": "972",
    "guyane": "973",
    "reunion": "974",
    "réunion": "974",
    "mayotte": "976",
}

# Major cities -> department code mapping
CITY_TO_DEPT = {
    "paris": "75",
    "marseille": "13",
    "lyon": "69",
    "toulouse": "31",
    "nice": "06",
    "nantes": "44",
    "montpellier": "34",
    "strasbourg": "67",
    "bordeaux": "33",
    "lille": "59",
    "rennes": "35",
    "reims": "51",
    "saint-etienne": "42",
    "saint-étienne": "42",
    "toulon": "83",
    "grenoble": "38",
    "dijon": "21",
    "angers": "49",
    "nimes": "30",
    "nîmes": "30",
    "villeurbanne": "69",
    "clermont-ferrand": "63",
    "le havre": "76",
    "aix-en-provence": "13",
    "brest": "29",
    "limoges": "87",
    "tours": "37",
    "amiens": "80",
    "perpignan": "66",
    "metz": "57",
    "besancon": "25",
    "besançon": "25",
    "orleans": "45",
    "orléans": "45",
    "rouen": "76",
    "mulhouse": "68",
    "caen": "14",
    "nancy": "54",
    "argenteuil": "95",
    "saint-denis": "93",
    "montreuil": "93",
    "roubaix": "59",
    "tourcoing": "59",
    "dunkerque": "59",
    "avignon": "84",
    "poitiers": "86",
    "pau": "64",
    "calais": "62",
    "la rochelle": "17",
    "cannes": "06",
    "antibes": "06",
    "ajaccio": "2A",
    "bastia": "2B",
}

# Department code -> name mapping (for display)
DEPT_CODE_TO_NAME = {
    "01": "Ain",
    "02": "Aisne",
    "03": "Allier",
    "04": "Alpes-de-Haute-Provence",
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
    "2A": "Corse-du-Sud",
    "2B": "Haute-Corse",
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
    "90": "Territoire de Belfort",
    "91": "Essonne",
    "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne",
    "95": "Val-d'Oise",
    "971": "Guadeloupe",
    "972": "Martinique",
    "973": "Guyane",
    "974": "La Réunion",
    "976": "Mayotte",
}

# NAF sector mappings for conceptual terms
SECTOR_CONCEPTS = {
    "secteurs porteurs": ["tech", "santé", "énergie_renouvelable", "logistique"],
    "secteurs en croissance": ["tech", "santé", "services_entreprises"],
    "secteurs dynamiques": ["tech", "commerce_digital", "santé"],
    "nouvelles technologies": ["tech", "ia", "fintech"],
    "économie verte": ["énergie_renouvelable", "recyclage", "agriculture_bio"],
    "secteurs d'avenir": ["tech", "santé", "énergie_renouvelable", "ia"],
}

# NAF code mappings
SECTOR_TO_NAF = {
    "tech": ["62.01Z", "62.02A", "62.02B", "62.03Z", "62.09Z", "63.11Z"],
    "santé": ["86.10Z", "86.21Z", "86.22A", "86.22C", "86.90A", "21.20Z"],
    "commerce": ["47.11A", "47.11B", "47.11C", "47.19A", "47.19B"],
    "commerce_digital": ["47.91A", "47.91B", "63.12Z"],
    "industrie": ["25.11Z", "25.12Z", "28.11Z", "28.12Z", "29.10Z"],
    "agriculture": ["01.11Z", "01.12Z", "01.13Z", "01.19Z", "01.21Z"],
    "énergie_renouvelable": ["35.11Z", "35.14Z", "43.21A", "71.12B"],
    "services_entreprises": ["70.22Z", "69.20Z", "70.21Z", "73.11Z"],
    "ia": ["62.01Z", "63.11Z", "72.19Z"],
    "fintech": ["64.19Z", "64.99Z", "66.19A", "66.19B"],
    "logistique": ["49.41A", "49.41B", "52.10A", "52.10B"],
    "recyclage": ["38.11Z", "38.21Z", "38.31Z", "38.32Z"],
    "agriculture_bio": ["01.11Z", "01.13Z", "01.19Z", "01.50Z"],
}

# Capitalized city -> dept for LLM extraction validation
CITY_TO_DEPT_CAPITALIZED = {
    "Toulouse": "31",
    "Paris": "75",
    "Lyon": "69",
    "Marseille": "13",
    "Bordeaux": "33",
    "Lille": "59",
    "Nantes": "44",
    "Strasbourg": "67",
    "Nice": "06",
    "Montpellier": "34",
    "Rennes": "35",
    "Grenoble": "38",
    "Toulon": "83",
    "Saint-Étienne": "42",
    "Le Havre": "76",
    "Dijon": "21",
    "Angers": "49",
    "Villeurbanne": "69",
    "Clermont-Ferrand": "63",
    "Brest": "29",
    "Limoges": "87",
    "Tours": "37",
    "Amiens": "80",
    "Metz": "57",
    "Besançon": "25",
    "Orléans": "45",
    "Reims": "51",
    "Rouen": "76",
}


def _normalize(text: str) -> str:
    """Normalize text for matching (lowercase, remove accents)."""
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def extract_territory(query: str) -> tuple[str | None, str | None]:
    """Extract territory from query with multi-level fallback chain.

    Returns:
        Tuple of (department_code, department_name)
        Falls back to ("France", "France") if nothing found
    """
    query_lower = query.lower()
    query_normalized = _normalize(query)

    # 1. Try explicit department code (e.g., "69", "2A", "971")
    dept_match = re.search(r"\b(2[AB]|\d{2,3})\b", query)
    if dept_match:
        code = (
            dept_match.group(1).upper()
            if dept_match.group(1).upper() in ("2A", "2B")
            else dept_match.group(1)
        )
        if code in DEPT_CODE_TO_NAME:
            logger.debug(f"Territory extracted via code match: {code}")
            return code, DEPT_CODE_TO_NAME[code]

    # 2. Try department name match (with and without accents)
    for name, code in DEPT_NAME_TO_CODE.items():
        name_normalized = _normalize(name)
        if name in query_lower or name_normalized in query_normalized:
            dept_name = DEPT_CODE_TO_NAME.get(code, name.title())
            logger.debug(f"Territory extracted via name match: {code} ({dept_name})")
            return code, dept_name

    # 3. Try city name match
    for city, code in CITY_TO_DEPT.items():
        city_normalized = _normalize(city)
        if city in query_lower or city_normalized in query_normalized:
            dept_name = DEPT_CODE_TO_NAME.get(code, city.title())
            logger.debug(f"Territory extracted via city match: {city} -> {code} ({dept_name})")
            return code, dept_name

    # 4. Check for "France" or national scope
    if "france" in query_lower or "national" in query_lower:
        logger.debug("Territory extracted: France (national scope)")
        return "France", "France"

    # 5. Default fallback
    logger.debug("Territory extraction: no match found, defaulting to France")
    return "France", "France"


def detect_sectors(query: str) -> tuple[list[str], list[str]]:
    """Detect sectors and NAF codes from conceptual terms in query.

    Returns:
        Tuple of (detected_sectors, detected_naf_codes)
    """
    query_lower = query.lower()
    detected_sectors: list[str] = []
    detected_naf_codes: list[str] = []

    for concept, sectors in SECTOR_CONCEPTS.items():
        if concept in query_lower:
            detected_sectors.extend(sectors)
            for sector in sectors:
                detected_naf_codes.extend(SECTOR_TO_NAF.get(sector, []))
            break

    return detected_sectors, detected_naf_codes


def extract_intent_fallback(query: str) -> dict[str, Any]:
    """Keyword-based intent extraction fallback (no LLM needed).

    Returns a dict with intent, territory, territory_name, sector, raw_query.
    """
    intent_map = {
        "analyse": "analyze",
        "analyze": "analyze",
        "compare": "compare",
        "prospect": "prospect",
        "veille": "monitor",
        "monitor": "monitor",
        "cherche": "search",
        "search": "search",
        "recherche": "search",
        "trouve": "search",
        "find": "search",
        "correlation": "analyze",
        "corrélation": "analyze",
    }

    query_lower = query.lower()
    intent = "analyze"
    for keyword, intent_type in intent_map.items():
        if keyword in query_lower:
            intent = intent_type
            break

    territory_code, territory_name = extract_territory(query)
    detected_sectors, detected_naf_codes = detect_sectors(query)

    sector = None
    naf_codes: list[str] = []

    if detected_sectors:
        sector = "multi_sector"
        naf_codes = detected_naf_codes
    else:
        extended_sectors = {
            "tech": SECTOR_TO_NAF.get("tech", []),
            "santé": SECTOR_TO_NAF.get("santé", []),
            "commerce": SECTOR_TO_NAF.get("commerce", []),
            "industrie": SECTOR_TO_NAF.get("industrie", []),
            "agriculture": SECTOR_TO_NAF.get("agriculture", []),
            "énergie": SECTOR_TO_NAF.get("énergie_renouvelable", []),
            "logistique": SECTOR_TO_NAF.get("logistique", []),
            "fintech": SECTOR_TO_NAF.get("fintech", []),
            "ia": SECTOR_TO_NAF.get("ia", []),
            "services": SECTOR_TO_NAF.get("services_entreprises", []),
        }
        for s, codes in extended_sectors.items():
            if s in query_lower:
                sector = s
                naf_codes = codes
                break

    result: dict[str, Any] = {
        "intent": intent,
        "territory": territory_code,
        "territory_name": territory_name,
        "sector": sector,
        "raw_query": query,
    }

    if detected_sectors:
        result["detected_sectors"] = detected_sectors
    if naf_codes:
        result["naf_codes"] = list(set(naf_codes))

    return result
