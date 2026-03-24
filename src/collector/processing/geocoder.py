"""Geographic resolver using french-cities for commune/EPCI/department mapping.

Resolves:
- Commune name → INSEE code
- Postal code → Commune code
- Commune code → Department, EPCI
"""

from functools import lru_cache

from loguru import logger

_fc = None


def _get_fc():
    """Lazy-load french-cities."""
    global _fc
    if _fc is None:
        try:
            import french_cities

            _fc = french_cities
            logger.info("[geocoder] french-cities loaded")
        except ImportError:
            logger.warning("[geocoder] french-cities not installed")
    return _fc


@lru_cache(maxsize=2048)
def commune_to_dept(code_commune: str) -> str | None:
    """Get department code from commune INSEE code."""
    if not code_commune or len(code_commune) < 5:
        return None
    # Corsica: 2A, 2B
    if code_commune.startswith("2A") or code_commune.startswith("2B"):
        return code_commune[:2]
    # DOM: 97x
    if code_commune.startswith("97"):
        return code_commune[:3]
    return code_commune[:2]


@lru_cache(maxsize=2048)
def resolve_commune(name: str, code_dept: str | None = None) -> dict[str, str | None]:
    """
    Resolve a commune name to INSEE code, department, etc.

    Returns: {code_commune, code_dept, nom}
    """
    fc = _get_fc()
    if fc is None:
        return {"code_commune": None, "code_dept": code_dept, "nom": name}

    try:
        import pandas as pd

        # Use french-cities to find the commune
        df = pd.DataFrame({"city": [name], "dep": [code_dept or ""]})
        result = fc.find_city(df, "city", "dep")
        if not result.empty:
            row = result.iloc[0]
            code = row.get("city_found_code") or row.get("INSEE_COM")
            return {
                "code_commune": str(code) if code else None,
                "code_dept": commune_to_dept(str(code)) if code else code_dept,
                "nom": row.get("city_found") or name,
            }
    except Exception as e:
        logger.debug(f"[geocoder] Could not resolve '{name}': {e}")

    return {"code_commune": None, "code_dept": code_dept, "nom": name}


@lru_cache(maxsize=1024)
def postal_to_commune(postal_code: str) -> dict[str, str | None]:
    """Resolve postal code to commune."""
    fc = _get_fc()
    if fc is None:
        dept = postal_code[:2] if len(postal_code) >= 2 else None
        return {"code_commune": None, "code_dept": dept, "postal": postal_code}

    try:
        import pandas as pd

        df = pd.DataFrame({"postal": [postal_code]})
        result = fc.find_city(df, "postal")
        if not result.empty:
            row = result.iloc[0]
            code = row.get("city_found_code") or row.get("INSEE_COM")
            return {
                "code_commune": str(code) if code else None,
                "code_dept": commune_to_dept(str(code)) if code else postal_code[:2],
                "postal": postal_code,
            }
    except Exception as e:
        logger.debug(f"[geocoder] Could not resolve postal '{postal_code}': {e}")

    return {"code_commune": None, "code_dept": postal_code[:2], "postal": postal_code}
