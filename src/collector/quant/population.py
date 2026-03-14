"""Population data and normalization utilities.

Provides department-level population data for territorial normalization.
Population data based on INSEE "populations légales" - 2024 estimates.
"""

from typing import Optional

from loguru import logger

# French department populations (2024 estimates)
# Source: INSEE populations légales
DEPARTMENT_POPULATIONS = {
    "01": 664246,  # Ain
    "02": 535899,  # Aisne
    "03": 338586,  # Allier
    "04": 164578,  # Alpes-de-Haute-Provence
    "05": 141760,  # Hautes-Alpes
    "06": 1097187,  # Alpes-Maritimes
    "07": 330167,  # Ardèche
    "08": 276050,  # Ardennes
    "09": 153989,  # Ariège
    "10": 310020,  # Aube
    "11": 379669,  # Aude
    "12": 279595,  # Aveyron
    "13": 2043110,  # Bouches-du-Rhône
    "14": 698719,  # Calvados
    "15": 143845,  # Cantal
    "16": 352705,  # Charente
    "17": 651857,  # Charente-Maritime
    "18": 302341,  # Cher
    "19": 240073,  # Corrèze
    "21": 534395,  # Côte-d'Or
    "22": 598814,  # Côtes-d'Armor
    "23": 116617,  # Creuse
    "24": 413606,  # Dordogne
    "25": 584412,  # Doubs
    "26": 515857,  # Drôme
    "27": 601843,  # Eure
    "28": 430416,  # Eure-et-Loir
    "29": 911735,  # Finistère
    "2A": 162849,  # Corse-du-Sud
    "2B": 181933,  # Haute-Corse
    "30": 774508,  # Gard
    "31": 1395442,  # Haute-Garonne
    "32": 191377,  # Gers
    "33": 1647446,  # Gironde
    "34": 1192989,  # Hérault
    "35": 1085907,  # Ille-et-Vilaine
    "36": 219316,  # Indre
    "37": 610079,  # Indre-et-Loire
    "38": 1298290,  # Isère
    "39": 259199,  # Jura
    "40": 413436,  # Landes
    "41": 333150,  # Loir-et-Cher
    "42": 765634,  # Loire
    "43": 227339,  # Haute-Loire
    "44": 1429272,  # Loire-Atlantique
    "45": 687560,  # Loiret
    "46": 174754,  # Lot
    "47": 335687,  # Lot-et-Garonne
    "48": 76360,  # Lozère
    "49": 818273,  # Maine-et-Loire
    "50": 495045,  # Manche
    "51": 571697,  # Marne
    "52": 172512,  # Haute-Marne
    "53": 307445,  # Mayenne
    "54": 732758,  # Meurthe-et-Moselle
    "55": 181557,  # Meuse
    "56": 761201,  # Morbihan
    "57": 1043522,  # Moselle
    "58": 205147,  # Nièvre
    "59": 2604361,  # Nord
    "60": 829545,  # Oise
    "61": 279636,  # Orne
    "62": 1465278,  # Pas-de-Calais
    "63": 660059,  # Puy-de-Dôme
    "64": 695668,  # Pyrénées-Atlantiques
    "65": 228530,  # Hautes-Pyrénées
    "66": 479979,  # Pyrénées-Orientales
    "67": 1151662,  # Bas-Rhin
    "68": 777616,  # Haut-Rhin
    "69": 1870981,  # Rhône + Lyon
    "70": 234818,  # Haute-Saône
    "71": 553595,  # Saône-et-Loire
    "72": 566506,  # Sarthe
    "73": 433739,  # Savoie
    "74": 829356,  # Haute-Savoie
    "75": 2161063,  # Paris
    "76": 1254378,  # Seine-Maritime
    "77": 1421197,  # Seine-et-Marne
    "78": 1431808,  # Yvelines
    "79": 374975,  # Deux-Sèvres
    "80": 571895,  # Somme
    "81": 387890,  # Tarn
    "82": 258349,  # Tarn-et-Garonne
    "83": 1076711,  # Var
    "84": 559479,  # Vaucluse
    "85": 695658,  # Vendée
    "86": 438253,  # Vienne
    "87": 374426,  # Haute-Vienne
    "88": 359701,  # Vosges
    "89": 337918,  # Yonne
    "90": 140120,  # Territoire de Belfort
    "91": 1296641,  # Essonne
    "92": 1609306,  # Hauts-de-Seine
    "93": 1644518,  # Seine-Saint-Denis
    "94": 1387926,  # Val-de-Marne
    "95": 1241834,  # Val-d'Oise
    # Overseas departments
    "971": 384239,  # Guadeloupe
    "972": 364508,  # Martinique
    "973": 295385,  # Guyane
    "974": 873617,  # La Réunion
    "976": 256518,  # Mayotte
}


def get_department_population(code_dept: str) -> int | None:
    """Get population for a given department code.

    Args:
        code_dept: Department code (e.g., '75', '13', '2A')

    Returns:
        Population count or None if department not found
    """
    population = DEPARTMENT_POPULATIONS.get(code_dept)
    if population is None:
        logger.warning(f"Population not found for department {code_dept}")
    return population


def normalize_per_10k(value: float, code_dept: str) -> float | None:
    """Normalize a value per 10,000 inhabitants.

    Args:
        value: Raw value to normalize
        code_dept: Department code

    Returns:
        Normalized value per 10K inhabitants or None if population unknown
    """
    population = get_department_population(code_dept)
    if population is None or population == 0:
        logger.warning(f"Cannot normalize for department {code_dept}: population unknown or zero")
        return None

    normalized = (value * 10_000) / population
    logger.debug(
        f"Normalized {value} for dept {code_dept} (pop={population:,}): {normalized:.3f} per 10K"
    )
    return normalized


def get_all_departments() -> list[str]:
    """Get list of all available department codes.

    Returns:
        List of department codes
    """
    return list(DEPARTMENT_POPULATIONS.keys())


def get_total_population() -> int:
    """Get total population across all departments.

    Returns:
        Total population count
    """
    return sum(DEPARTMENT_POPULATIONS.values())


if __name__ == "__main__":
    # Test the population functions
    print(f"Total departments: {len(get_all_departments())}")
    print(f"Total population: {get_total_population():,}")

    # Test some departments
    test_depts = ["75", "13", "59", "69", "2A"]
    for dept in test_depts:
        pop = get_department_population(dept)
        norm = normalize_per_10k(1000, dept)
        print(f"Dept {dept}: population={pop:,}, 1000 normalized={norm:.3f} per 10K")
