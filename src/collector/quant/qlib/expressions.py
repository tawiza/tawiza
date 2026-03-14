"""
Predefined alpha expressions for territorial intelligence.

This module contains a library of pre-defined alpha factors specifically
designed for territorial analysis. These expressions combine raw metrics
into meaningful indicators of territorial dynamics.

Each expression is a string that can be evaluated by the ops module.
Variables prefixed with $ refer to metric columns in the data.
"""

from typing import Dict, List, Tuple

# Core alpha expressions for territorial intelligence
ALPHA_EXPRESSIONS: dict[str, str] = {
    # Business Health Indicators
    "sante_entreprises": "$liquidation_judiciaire / ($creation_entreprise + 1)",
    "pression_fermeture": "$fermeture_entreprise / ($creation_entreprise + 1)",
    "dynamisme_creation": "ROC($creation_entreprise, 6)",
    "stabilite_entreprises": "1 / (Volatility($liquidation_judiciaire, 12) + 0.1)",
    # Employment & Labor Market
    "tension_emploi": "$offres_emploi / ($creation_entreprise + 1) * 1000",
    "tension_emploi_ma3": "Mean($offres_emploi, 3) / (Mean($creation_entreprise, 3) + 1) * 1000",
    "momentum_emploi": "Momentum($offres_emploi, 3, 12)",
    "croissance_emploi": "ROC($offres_emploi, 6)",
    "stabilite_emploi": "1 / (Volatility($offres_emploi, 6) + 0.1)",
    # Real Estate & Housing
    "dynamisme_immo": "ROC($transactions_immobilieres, 6)",
    "acceleration_prix": "ROC($prix_m2_moyen, 3)",
    "pression_prix": "Rank($prix_m2_moyen)",
    "momentum_immo": "Momentum($transactions_immobilieres, 3, 12)",
    "bulle_immo_signal": "Slope($prix_m2_moyen, 12) / (Std($prix_m2_moyen, 12) + 1)",
    # Construction & Development
    "acceleration_construction": "Ref($logements_autorises, 1) / (Mean($logements_autorises, 6) + 1)",
    "dynamisme_construction": "ROC($logements_autorises, 6)",
    "cycle_construction": "Momentum($logements_autorises, 3, 12)",
    "boom_construction": "Max($logements_autorises, 12) / (Mean($logements_autorises, 12) + 1)",
    # Cross-Source Convergence
    "convergence_positive": "CSZScore($creation_entreprise) + CSZScore($offres_emploi) + CSZScore($transactions_immobilieres)",
    "convergence_negative": "CSZScore($liquidation_judiciaire) + CSZScore($fermeture_entreprise)",
    "signal_mixte": "CSZScore($creation_entreprise) - CSZScore($liquidation_judiciaire)",
    # Momentum & Trend Analysis
    "tendance_6m": "Slope($creation_entreprise, 6) - Slope($liquidation_judiciaire, 6)",
    "acceleration_economie": "Delta(Slope($creation_entreprise, 3), 3)",
    "retournement_cycle": "Corr($creation_entreprise, $liquidation_judiciaire, 6)",
    # Volatility & Risk Indicators
    "instabilite_economique": "Std($creation_entreprise, 6) + Std($liquidation_judiciaire, 6)",
    "risque_territorial": "Volatility($liquidation_judiciaire, 12) * Rank($liquidation_judiciaire)",
    "stress_immobilier": "Volatility($prix_m2_moyen, 6) * CSZScore($prix_m2_moyen)",
    # Comparative Indicators (Cross-sectional)
    "rang_creation": "Rank($creation_entreprise)",
    "rang_liquidation": "1 - Rank($liquidation_judiciaire)",  # Inverted (lower liquidation is better)
    "rang_emploi": "Rank($offres_emploi)",
    "rang_immobilier": "Rank($transactions_immobilieres)",
    "score_competitivite": "Rank($creation_entreprise) + Rank($offres_emploi) - Rank($liquidation_judiciaire)",
    # Sectoral Analysis (if sector data available)
    "commerce_sante": "$vente_fonds_commerce / ($fermeture_entreprise + 1)",
    "momentum_commerce": "ROC($vente_fonds_commerce, 3)",
    # Seasonal & Calendar Effects
    "croissance_desaisonnalisee": "ROC(Mean($creation_entreprise, 3), 12)",  # Year-over-year
    "effet_saisonnier": "$creation_entreprise / Mean($creation_entreprise, 12)",
    # Advanced Composite Indicators
    "indice_vitalite": "0.3 * CSZScore($creation_entreprise) + 0.3 * CSZScore($offres_emploi) + 0.2 * CSZScore($transactions_immobilieres) - 0.2 * CSZScore($liquidation_judiciaire)",
    "indice_risque": "0.4 * CSZScore($liquidation_judiciaire) + 0.3 * CSZScore($fermeture_entreprise) + 0.3 * Volatility($creation_entreprise, 6)",
    "potentiel_croissance": "Momentum($creation_entreprise, 3, 12) * (1 - Rank($liquidation_judiciaire)) * CSZScore($offres_emploi)",
}


# Expression categories for easier navigation
EXPRESSION_CATEGORIES: dict[str, list[str]] = {
    "business_health": [
        "sante_entreprises",
        "pression_fermeture",
        "dynamisme_creation",
        "stabilite_entreprises",
        "commerce_sante",
        "momentum_commerce",
    ],
    "employment": [
        "tension_emploi",
        "tension_emploi_ma3",
        "momentum_emploi",
        "croissance_emploi",
        "stabilite_emploi",
    ],
    "real_estate": [
        "dynamisme_immo",
        "acceleration_prix",
        "pression_prix",
        "momentum_immo",
        "bulle_immo_signal",
        "stress_immobilier",
    ],
    "construction": [
        "acceleration_construction",
        "dynamisme_construction",
        "cycle_construction",
        "boom_construction",
    ],
    "convergence": ["convergence_positive", "convergence_negative", "signal_mixte"],
    "momentum": ["tendance_6m", "acceleration_economie", "retournement_cycle"],
    "risk": ["instabilite_economique", "risque_territorial", "indice_risque"],
    "ranking": [
        "rang_creation",
        "rang_liquidation",
        "rang_emploi",
        "rang_immobilier",
        "score_competitivite",
    ],
    "seasonal": ["croissance_desaisonnalisee", "effet_saisonnier"],
    "composite": ["indice_vitalite", "potentiel_croissance"],
}


# Expression metadata for documentation and validation
EXPRESSION_METADATA: dict[str, dict[str, str]] = {
    "sante_entreprises": {
        "description": "Business health ratio: liquidations relative to creations",
        "interpretation": "Lower is better. Values > 1.0 indicate more liquidations than creations",
        "unit": "ratio",
        "range": "0 to +inf",
        "good_threshold": "< 0.5",
        "alert_threshold": "> 1.0",
    },
    "tension_emploi_ma3": {
        "description": "Job market tension: 3-month average job offers per business creation",
        "interpretation": "Higher indicates better job market dynamics",
        "unit": "offers per 1000 businesses",
        "range": "0 to +inf",
        "good_threshold": "> 500",
        "alert_threshold": "< 100",
    },
    "dynamisme_immo": {
        "description": "Real estate momentum: 6-month rate of change in transactions",
        "interpretation": "Positive indicates growing market, negative indicates decline",
        "unit": "rate of change",
        "range": "-1 to +inf",
        "good_threshold": "> 0.1",
        "alert_threshold": "< -0.2",
    },
    "indice_vitalite": {
        "description": "Composite vitality index combining business, employment and real estate",
        "interpretation": "Standardized score. Positive indicates above-average vitality",
        "unit": "z-score",
        "range": "-3 to +3 (typically)",
        "good_threshold": "> 0.5",
        "alert_threshold": "< -1.0",
    },
    "convergence_positive": {
        "description": "Convergence of positive economic signals",
        "interpretation": "Higher values indicate multiple positive signals aligning",
        "unit": "z-score sum",
        "range": "-9 to +9 (typically)",
        "good_threshold": "> 1.0",
        "alert_threshold": "< -1.0",
    },
}


def get_expressions_by_category(category: str) -> list[tuple[str, str]]:
    """
    Get expressions for a specific category.

    Args:
        category: Category name

    Returns:
        List of (expression_name, expression_formula) tuples
    """
    if category not in EXPRESSION_CATEGORIES:
        raise ValueError(
            f"Unknown category: {category}. Available: {list(EXPRESSION_CATEGORIES.keys())}"
        )

    expressions = EXPRESSION_CATEGORIES[category]
    return [(expr, ALPHA_EXPRESSIONS[expr]) for expr in expressions]


def get_required_metrics(expression: str) -> list[str]:
    """
    Extract required metrics from an expression.

    Args:
        expression: Expression string

    Returns:
        List of required metric names (without $ prefix)
    """
    import re

    return re.findall(r"\$(\w+)", expression)


def validate_expression_metrics(expression_name: str, available_metrics: list[str]) -> bool:
    """
    Validate that all required metrics are available for an expression.

    Args:
        expression_name: Name of the expression
        available_metrics: List of available metric names

    Returns:
        True if all required metrics are available
    """
    if expression_name not in ALPHA_EXPRESSIONS:
        return False

    expression = ALPHA_EXPRESSIONS[expression_name]
    required = get_required_metrics(expression)

    return all(metric in available_metrics for metric in required)


def get_compatible_expressions(available_metrics: list[str]) -> list[str]:
    """
    Get all expressions that can be computed with available metrics.

    Args:
        available_metrics: List of available metric names

    Returns:
        List of compatible expression names
    """
    compatible = []
    for expr_name in ALPHA_EXPRESSIONS:
        if validate_expression_metrics(expr_name, available_metrics):
            compatible.append(expr_name)

    return compatible


def describe_expression(expression_name: str) -> dict[str, str]:
    """
    Get detailed description of an expression.

    Args:
        expression_name: Name of the expression

    Returns:
        Dictionary with expression metadata
    """
    if expression_name not in ALPHA_EXPRESSIONS:
        raise ValueError(f"Unknown expression: {expression_name}")

    result = {
        "name": expression_name,
        "formula": ALPHA_EXPRESSIONS[expression_name],
        "required_metrics": get_required_metrics(ALPHA_EXPRESSIONS[expression_name]),
    }

    # Add metadata if available
    if expression_name in EXPRESSION_METADATA:
        result.update(EXPRESSION_METADATA[expression_name])

    # Find categories containing this expression
    categories = [cat for cat, exprs in EXPRESSION_CATEGORIES.items() if expression_name in exprs]
    result["categories"] = categories

    return result


# Default expression sets for different use cases
DEFAULT_EXPRESSION_SETS: dict[str, list[str]] = {
    "basic": [
        "sante_entreprises",
        "tension_emploi_ma3",
        "dynamisme_immo",
        "acceleration_construction",
    ],
    "comprehensive": [
        "sante_entreprises",
        "tension_emploi_ma3",
        "dynamisme_immo",
        "acceleration_construction",
        "convergence_positive",
        "indice_vitalite",
        "momentum_emploi",
        "risque_territorial",
        "score_competitivite",
    ],
    "risk_focused": [
        "sante_entreprises",
        "pression_fermeture",
        "instabilite_economique",
        "risque_territorial",
        "indice_risque",
        "stress_immobilier",
    ],
    "momentum_focused": [
        "dynamisme_creation",
        "momentum_emploi",
        "dynamisme_immo",
        "cycle_construction",
        "tendance_6m",
        "acceleration_economie",
    ],
    "ranking_focused": [
        "rang_creation",
        "rang_liquidation",
        "rang_emploi",
        "rang_immobilier",
        "score_competitivite",
        "pression_prix",
    ],
}


def get_expression_set(set_name: str) -> list[tuple[str, str]]:
    """
    Get a predefined set of expressions.

    Args:
        set_name: Name of the expression set

    Returns:
        List of (expression_name, expression_formula) tuples
    """
    if set_name not in DEFAULT_EXPRESSION_SETS:
        raise ValueError(
            f"Unknown expression set: {set_name}. Available: {list(DEFAULT_EXPRESSION_SETS.keys())}"
        )

    expressions = DEFAULT_EXPRESSION_SETS[set_name]
    return [(expr, ALPHA_EXPRESSIONS[expr]) for expr in expressions]


# Helper function to create custom expressions
def create_custom_expression(
    name: str, formula: str, description: str = "", categories: list[str] = None
) -> None:
    """
    Create a custom alpha expression.

    Args:
        name: Expression name
        formula: Expression formula
        description: Description of the expression
        categories: Categories this expression belongs to
    """
    ALPHA_EXPRESSIONS[name] = formula

    if description:
        if name not in EXPRESSION_METADATA:
            EXPRESSION_METADATA[name] = {}
        EXPRESSION_METADATA[name]["description"] = description

    if categories:
        for category in categories:
            if category not in EXPRESSION_CATEGORIES:
                EXPRESSION_CATEGORIES[category] = []
            if name not in EXPRESSION_CATEGORIES[category]:
                EXPRESSION_CATEGORIES[category].append(name)


# === LLM-GENERATED FACTORS (qwen3.5:27b, 2026-02-13) ===
LLM_ALPHA_EXPRESSIONS = {
    "economic_vitality_index": {
        "formula": "(creation_entreprise - fermeture_entreprise) / (creation_entreprise + fermeture_entreprise + 1)",
        "hypothesis": "Net rate of business creation vs closures indicates economic dynamism",
    },
    "employment_pressure_index": {
        "formula": "offres_emploi / (creation_entreprise + 1)",
        "hypothesis": "Job offers relative to new businesses reflects employment tension",
    },
    "financial_distress_index": {
        "formula": "(liquidation_judiciaire + procedure_collective) / (creation_entreprise + 1)",
        "hypothesis": "Liquidations and collective procedures relative to new businesses indicates financial distress",
    },
    "housing_market_pressure": {
        "formula": "transactions_immobilieres / (logements_autorises + 1)",
        "hypothesis": "Real estate transactions vs authorized housing reflects market saturation",
    },
    "social_sentiment_index": {
        "formula": "(presse_fermeture + search_interest_RSA) / (offres_emploi + 1)",
        "hypothesis": "Media closures coverage + RSA interest relative to job offers indicates social distress sentiment",
    },
}

# Merge into main expressions
ALPHA_EXPRESSIONS.update({k: v["formula"] for k, v in LLM_ALPHA_EXPRESSIONS.items()})
