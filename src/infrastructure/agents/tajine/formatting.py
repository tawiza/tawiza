"""
ResponseFormatter - Formateur de reponses TAJINE.

Produit des reponses professionnelles avec structure visuelle coherente:
- SYNTHESE
- DONNEES CLES (tableau)
- ANALYSE (liste a puces)
- RECOMMANDATIONS (liste numerotee)
- Footer: Sources | Confiance | Mode

Contraintes:
- Pas d'emojis
- Markdown GFM uniquement
- Formules LaTeX pour calculs/probabilites
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DataPoint:
    """Un point de donnee pour le tableau."""

    label: str
    value: str
    variation: str = ""
    unit: str = ""


@dataclass
class AnalysisResult:
    """Resultat d'analyse TAJINE."""

    summary: str
    data: list[DataPoint] = field(default_factory=list)
    analysis: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.0
    mode: str = "RAPIDE"


class ResponseFormatter:
    """Formateur de reponses TAJINE."""

    TEMPLATE = """## SYNTHESE

{summary}

## DONNEES CLES

{data_table}

## ANALYSE

{analysis_points}

## RECOMMANDATIONS

{recommendations}

---
Sources: {sources} | Confiance: {confidence}% | Mode: {mode}"""

    TEMPLATE_MINIMAL = """## SYNTHESE

{summary}

## ANALYSE

{analysis_points}

---
Sources: {sources} | Confiance: {confidence}% | Mode: {mode}"""

    def format(self, result: AnalysisResult) -> str:
        """
        Formate le resultat d'analyse en Markdown professionnel.

        Args:
            result: Resultat d'analyse TAJINE

        Returns:
            Texte Markdown formate
        """
        # Use minimal template if no data or recommendations
        if not result.data and not result.recommendations:
            return self.TEMPLATE_MINIMAL.format(
                summary=result.summary,
                analysis_points=self._build_list(result.analysis),
                sources=", ".join(result.sources) if result.sources else "SIRENE",
                confidence=int(result.confidence * 100),
                mode=result.mode.upper(),
            )

        return self.TEMPLATE.format(
            summary=result.summary,
            data_table=self._build_table(result.data),
            analysis_points=self._build_list(result.analysis),
            recommendations=self._build_numbered_list(result.recommendations),
            sources=", ".join(result.sources) if result.sources else "SIRENE",
            confidence=int(result.confidence * 100),
            mode=result.mode.upper(),
        )

    def _build_table(self, data: list[DataPoint]) -> str:
        """Construit un tableau Markdown."""
        if not data:
            return "*Aucune donnee disponible*"

        # Build header
        lines = [
            "| Indicateur | Valeur | Variation |",
            "|------------|--------|-----------|",
        ]

        # Build rows
        for point in data:
            value = f"{point.value}{point.unit}" if point.unit else point.value
            variation = point.variation if point.variation else "-"
            lines.append(f"| {point.label} | {value} | {variation} |")

        return "\n".join(lines)

    def _build_list(self, items: list[str]) -> str:
        """Construit une liste a puces Markdown."""
        if not items:
            return "*Aucune analyse disponible*"
        return "\n".join(f"- {item}" for item in items)

    def _build_numbered_list(self, items: list[str]) -> str:
        """Construit une liste numerotee Markdown."""
        if not items:
            return "*Aucune recommandation*"
        return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1))


# Singleton instance for convenience
_formatter = ResponseFormatter()


def format_response(
    summary: str,
    data: list[dict[str, Any]] | None = None,
    analysis: list[str] | None = None,
    recommendations: list[str] | None = None,
    sources: list[str] | None = None,
    confidence: float = 0.7,
    mode: str = "RAPIDE",
) -> str:
    """
    Convenience function to format a TAJINE response.

    Args:
        summary: Resume en 2-3 phrases
        data: Liste de dictionnaires avec {label, value, variation?, unit?}
        analysis: Liste de points d'analyse
        recommendations: Liste de recommandations
        sources: Liste des sources utilisees
        confidence: Score de confiance (0-1)
        mode: Mode d'execution (RAPIDE ou COMPLET)

    Returns:
        Texte Markdown formate

    Example:
        >>> format_response(
        ...     summary="Le departement 69 montre une forte dynamique...",
        ...     data=[
        ...         {"label": "Creations", "value": "1,247", "variation": "+12.3%"},
        ...         {"label": "Radiations", "value": "892", "variation": "-5.1%"},
        ...     ],
        ...     analysis=[
        ...         "Le secteur tech represente 35% des creations",
        ...         "La croissance est concentree sur Lyon Metropole",
        ...     ],
        ...     recommendations=[
        ...         "Renforcer l'accompagnement des startups tech",
        ...         "Etendre les dispositifs aux zones rurales",
        ...     ],
        ...     sources=["SIRENE", "BODACC"],
        ...     confidence=0.85,
        ...     mode="COMPLET",
        ... )
    """
    data_points = []
    if data:
        for d in data:
            data_points.append(
                DataPoint(
                    label=d.get("label", ""),
                    value=str(d.get("value", "")),
                    variation=d.get("variation", ""),
                    unit=d.get("unit", ""),
                )
            )

    result = AnalysisResult(
        summary=summary,
        data=data_points,
        analysis=analysis or [],
        recommendations=recommendations or [],
        sources=sources or [],
        confidence=confidence,
        mode=mode,
    )

    return _formatter.format(result)


# Template for mathematical/statistical content
MATH_TEMPLATE = """## SYNTHESE

{summary}

## METHODOLOGIE

{methodology}

## RESULTATS

{data_table}

### Formules utilisees

{formulas}

## INTERPRETATION

{interpretation}

---
Sources: {sources} | Confiance: {confidence}% | Mode: {mode}"""


def format_statistical_response(
    summary: str,
    methodology: str,
    data: list[dict[str, Any]] | None = None,
    formulas: list[str] | None = None,
    interpretation: list[str] | None = None,
    sources: list[str] | None = None,
    confidence: float = 0.7,
    mode: str = "COMPLET",
) -> str:
    """
    Format a statistical/mathematical TAJINE response with LaTeX formulas.

    Args:
        summary: Resume en 2-3 phrases
        methodology: Description de la methodologie
        data: Resultats en tableau
        formulas: Formules LaTeX (sans les $)
        interpretation: Points d'interpretation
        sources: Sources utilisees
        confidence: Score de confiance
        mode: Mode d'execution

    Returns:
        Texte Markdown avec formules LaTeX

    Example:
        >>> format_statistical_response(
        ...     summary="L'analyse bayesienne montre...",
        ...     methodology="Inference bayesienne avec prior Beta(2,2)",
        ...     formulas=[
        ...         "P(H|E) = \\\\frac{P(E|H) \\\\cdot P(H)}{P(E)}",
        ...         "\\\\text{Posterior} = \\\\text{Beta}(a + x, b + n - x)",
        ...     ],
        ...     interpretation=["Le posterior indique...", "Le facteur Bayes..."],
        ... )
    """
    data_table = "*Aucune donnee*"
    if data:
        lines = ["| Metrique | Valeur | IC 95% |", "|----------|--------|--------|"]
        for d in data:
            ic = d.get("confidence_interval", "-")
            lines.append(f"| {d.get('label', '')} | {d.get('value', '')} | {ic} |")
        data_table = "\n".join(lines)

    formulas_md = "*Aucune formule*"
    if formulas:
        formulas_md = "\n".join(f"$${f}$$" for f in formulas)

    interp_md = "*Aucune interpretation*"
    if interpretation:
        interp_md = "\n".join(f"- {i}" for i in interpretation)

    return MATH_TEMPLATE.format(
        summary=summary,
        methodology=methodology,
        data_table=data_table,
        formulas=formulas_md,
        interpretation=interp_md,
        sources=", ".join(sources) if sources else "Analyse interne",
        confidence=int(confidence * 100),
        mode=mode.upper(),
    )
