"""
UnifiedSynthesizer - Fusionne les 5 niveaux cognitifs en reponse structuree.

Ce module prend les outputs de tous les niveaux cognitifs et genere:
1. Une synthese executive (resume)
2. Des sections detaillees par niveau
3. Des recommandations prioritisees
4. Un score de confiance global
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider


@dataclass
class SynthesizedSection:
    """Une section de la synthese unifiee."""

    level: str
    title: str
    summary: str
    key_points: list[str]
    confidence: float
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "title": self.title,
            "summary": self.summary,
            "key_points": self.key_points,
            "confidence": round(self.confidence, 2),
            "data": self.data,
        }


@dataclass
class UnifiedSynthesis:
    """Resultat de la synthese unifiee des 5 niveaux."""

    executive_summary: str
    sections: list[SynthesizedSection]
    recommendations: list[dict[str, Any]]
    overall_confidence: float
    territory: str | None = None
    sector: str | None = None
    cognitive_signature: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "executive_summary": self.executive_summary,
            "sections": [s.to_dict() for s in self.sections],
            "recommendations": self.recommendations,
            "overall_confidence": round(self.overall_confidence, 2),
            "territory": self.territory,
            "sector": self.sector,
            "cognitive_signature": {k: round(v, 2) for k, v in self.cognitive_signature.items()},
        }

    def to_markdown(self) -> str:
        """Convertit la synthese en format Markdown structure."""
        lines: list[str] = []

        def _ensure_str(val) -> str:
            """Ensure value is a string, converting dicts/lists to readable format."""
            if val is None:
                return ""
            if isinstance(val, str):
                return val
            if isinstance(val, dict):
                # Convert dict to a readable summary
                return ", ".join(f"{k}: {v}" for k, v in val.items() if v)
            if isinstance(val, (list, tuple)):
                return ", ".join(_ensure_str(v) for v in val)
            return str(val)

        # En-tete avec contexte
        if self.territory or self.sector:
            context_parts = []
            if self.territory:
                context_parts.append(f"**Territoire:** {_ensure_str(self.territory)}")
            if self.sector:
                context_parts.append(f"**Secteur:** {_ensure_str(self.sector)}")
            lines.append(" | ".join(context_parts))
            lines.append("")

        # Resume executif
        lines.append("## Resume Executif")
        lines.append("")
        lines.append(_ensure_str(self.executive_summary))
        lines.append("")

        # Score de confiance global
        confidence_emoji = (
            "🟢"
            if self.overall_confidence >= 0.7
            else "🟡"
            if self.overall_confidence >= 0.5
            else "🔴"
        )
        lines.append(f"**Confiance globale:** {confidence_emoji} {self.overall_confidence:.0%}")
        lines.append("")

        # Sections par niveau
        for section in self.sections:
            level_emoji = {
                "discovery": "🔍",
                "causal": "🔗",
                "scenario": "📊",
                "strategy": "🎯",
                "theoretical": "📚",
            }.get(section.level, "📌")

            lines.append(f"### {level_emoji} {_ensure_str(section.title)}")
            lines.append("")
            lines.append(_ensure_str(section.summary))
            lines.append("")

            if section.key_points:
                for point in section.key_points:
                    lines.append(f"- {_ensure_str(point)}")
                lines.append("")

        # Recommandations
        if self.recommendations:
            lines.append("## Recommandations Prioritisees")
            lines.append("")
            for i, rec in enumerate(self.recommendations, 1):
                if isinstance(rec, dict):
                    priority_emoji = {
                        "critical": "🔴",
                        "high": "🟠",
                        "medium": "🟡",
                        "low": "🟢",
                    }.get(rec.get("priority", "medium"), "⚪")
                    desc = rec.get("description", "Recommandation")
                    lines.append(f"{i}. {priority_emoji} **{_ensure_str(desc)}**")
                    if rec.get("rationale"):
                        lines.append(f"   > {_ensure_str(rec['rationale'])}")
                else:
                    lines.append(f"{i}. {_ensure_str(rec)}")
                lines.append("")

        return "\n".join(lines)


# Mapping des niveaux vers titres francais
LEVEL_TITLES = {
    "discovery": "Decouverte et Signaux Faibles",
    "causal": "Analyse Causale",
    "scenario": "Scenarios Prospectifs",
    "strategy": "Recommandations Strategiques",
    "theoretical": "Validation Theorique",
}


class UnifiedSynthesizer:
    """
    Synthetiseur unifie pour les 5 niveaux cognitifs.

    Modes de fonctionnement:
    1. Rule-based: Extraction et agregation des donnees sans LLM
    2. LLM-powered: Utilise le LLM pour generer une synthese naturelle
    """

    def __init__(self, llm_provider: Optional["LLMProvider"] = None):
        """Initialize le synthetiseur."""
        self._llm_provider = llm_provider
        logger.debug(f"UnifiedSynthesizer initialized (LLM: {llm_provider is not None})")

    async def synthesize(
        self, cognitive_outputs: dict[str, dict[str, Any]], context: dict[str, Any] | None = None
    ) -> UnifiedSynthesis:
        """
        Synthetise les outputs de tous les niveaux cognitifs.

        Args:
            cognitive_outputs: Dict avec les outputs de chaque niveau
            context: Contexte optionnel (territoire, secteur, query)

        Returns:
            UnifiedSynthesis avec synthese structuree
        """
        context = context or {}

        # Essayer synthese LLM d'abord
        if self._llm_provider:
            try:
                return await self._synthesize_with_llm(cognitive_outputs, context)
            except Exception as e:
                logger.warning(f"LLM synthesis failed, falling back to rule-based: {e}")

        # Fallback rule-based
        return self._synthesize_rule_based(cognitive_outputs, context)

    async def _synthesize_with_llm(
        self, cognitive_outputs: dict[str, dict[str, Any]], context: dict[str, Any]
    ) -> UnifiedSynthesis:
        """Synthese utilisant le LLM pour une reponse naturelle."""
        # Preparer le contexte pour le LLM
        levels_summary = []
        for level_name in ["discovery", "causal", "scenario", "strategy", "theoretical"]:
            output = cognitive_outputs.get(level_name, {})
            summary = self._extract_level_summary(level_name, output)
            levels_summary.append(f"**{LEVEL_TITLES.get(level_name, level_name)}:**\n{summary}")

        prompt = f"""Synthetise les analyses suivantes en une reponse structuree et coherente.

Contexte:
- Territoire: {context.get("territory", "Non specifie")}
- Secteur: {context.get("sector", "Non specifie")}
- Question originale: {context.get("query", "Analyse territoriale")}

Analyses par niveau:
{chr(10).join(levels_summary)}

Genere un objet JSON strict avec la structure suivante:
{{
    "executive_summary": "Resume global (3-4 phrases)",
    "sections": [
        {{
            "level": "discovery|causal|scenario|strategy|theoretical",
            "title": "Titre de la section",
            "summary": "Resume de ce niveau",
            "key_points": ["point 1", "point 2"]
        }}
    ],
    "recommendations": [
        {{
            "description": "Action recommandee",
            "priority": "critical|high|medium|low",
            "rationale": "Pourquoi cette action"
        }}
    ]
}}

Reponds UNIQUEMENT avec le JSON valide."""

        # Appeler le LLM
        response = await self._llm_provider.generate(prompt=prompt, task_type="synthesis")

        # Parser la reponse LLM et construire UnifiedSynthesis
        return self._parse_llm_response(response, cognitive_outputs, context)

    def _synthesize_rule_based(
        self, cognitive_outputs: dict[str, dict[str, Any]], context: dict[str, Any]
    ) -> UnifiedSynthesis:
        """Synthese rule-based sans LLM."""
        sections = []
        all_recommendations = []
        confidences = {}

        # Traiter chaque niveau
        for level_name in ["discovery", "causal", "scenario", "strategy", "theoretical"]:
            output = cognitive_outputs.get(level_name, {})
            section = self._build_section(level_name, output)
            sections.append(section)
            confidences[level_name] = section.confidence

            # Collecter les recommandations du niveau strategy
            if level_name == "strategy":
                recs = output.get("recommendations", [])
                all_recommendations.extend(recs if isinstance(recs, list) else [])

        # Generer resume executif
        executive_summary = self._generate_executive_summary(sections, context)

        # Calculer confiance globale (moyenne ponderee)
        weights = {"discovery": 1, "causal": 2, "scenario": 3, "strategy": 4, "theoretical": 5}
        total_weight = sum(weights.values())
        overall_confidence = (
            sum(confidences.get(level, 0.5) * weight for level, weight in weights.items())
            / total_weight
        )

        # Trier recommandations par priorite
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_recs = sorted(
            all_recommendations, key=lambda r: priority_order.get(r.get("priority", "medium"), 2)
        )

        return UnifiedSynthesis(
            executive_summary=executive_summary,
            sections=sections,
            recommendations=sorted_recs[:5],  # Top 5
            overall_confidence=overall_confidence,
            territory=context.get("territory"),
            sector=context.get("sector"),
            cognitive_signature=confidences,
        )

    def _build_section(self, level_name: str, output: dict[str, Any]) -> SynthesizedSection:
        """Construit une section a partir d'un output de niveau."""
        title = LEVEL_TITLES.get(level_name, level_name.title())
        confidence = output.get("confidence", 0.5)
        key_points = []

        # Extraire les points cles selon le niveau
        if level_name == "discovery":
            signals = output.get("signals", [])
            trends = output.get("trends", [])
            for signal in signals[:3]:
                if isinstance(signal, dict):
                    key_points.append(signal.get("description", str(signal)))
                else:
                    key_points.append(str(signal))
            for trend in trends[:2]:
                if isinstance(trend, dict):
                    key_points.append(
                        f"Tendance: {trend.get('type', '')} ({trend.get('direction', '')})"
                    )
                else:
                    key_points.append(str(trend))

        elif level_name == "causal":
            causes = output.get("causes", [])
            for cause in causes[:4]:
                if isinstance(cause, dict):
                    factor = cause.get("factor", "")
                    direction = cause.get("direction", "")
                    key_points.append(f"{factor} ({direction})")
                else:
                    key_points.append(str(cause))

        elif level_name == "scenario":
            optimistic = output.get("optimistic", {})
            median = output.get("median", {})
            pessimistic = output.get("pessimistic", {})

            if median:
                growth = median.get("growth_rate", 0)
                key_points.append(f"Scenario median: croissance de {growth:.1%}")
            if optimistic:
                growth = optimistic.get("growth_rate", 0)
                key_points.append(f"Scenario optimiste: croissance de {growth:.1%}")
            if pessimistic:
                growth = pessimistic.get("growth_rate", 0)
                key_points.append(f"Scenario pessimiste: croissance de {growth:.1%}")

        elif level_name == "strategy":
            recommendations = output.get("recommendations", [])
            for rec in recommendations[:3]:
                if isinstance(rec, dict):
                    key_points.append(
                        f"{rec.get('type', '').title()}: {rec.get('description', '')}"
                    )
                else:
                    key_points.append(str(rec))
            actions = output.get("actions", [])
            if actions:
                key_points.append(f"{len(actions)} actions prioritaires identifiees")

        elif level_name == "theoretical":
            validated = output.get("validated", False)
            alignment = output.get("framework_alignment", 0)
            limitations = output.get("limitations", [])

            if validated:
                key_points.append(f"Analyse validee theoriquement (alignement: {alignment:.0%})")
            if limitations:
                key_points.append(f"Limitations identifiees: {len(limitations)}")

        # Generer le resume de la section
        summary = self._extract_level_summary(level_name, output)

        return SynthesizedSection(
            level=level_name,
            title=title,
            summary=summary,
            key_points=key_points,
            confidence=confidence,
            data=output,
        )

    def _extract_level_summary(self, level_name: str, output: dict[str, Any]) -> str:
        """Extrait un resume du niveau."""
        # Chercher un champ summary existant
        if "summary" in output:
            return output["summary"]

        # Generer un resume selon le niveau
        if level_name == "discovery":
            signals = len(output.get("signals", []))
            trends = len(output.get("trends", []))
            return f"{signals} signaux faibles detectes, {trends} tendances identifiees."

        elif level_name == "causal":
            causes = output.get("causes", [])
            if causes:
                top_cause = causes[0] if causes else {}
                factor = top_cause.get("factor", "facteur principal")
                return f"Facteur principal: {factor}. {len(causes)} relations causales analysees."
            return "Analyse causale en cours."

        elif level_name == "scenario":
            median = output.get("median", {})
            method = output.get("method", "projection")
            growth = median.get("growth_rate", 0)
            return f"Methode {method}: croissance prevue de {growth:.1%} (scenario median)."

        elif level_name == "strategy":
            recs = output.get("recommendations", [])
            if recs:
                top_rec = recs[0] if recs else {}
                rec_type = top_rec.get("type", "action")
                return f"Recommandation principale: {rec_type}. {len(recs)} strategies proposees."
            return "Strategies en cours d'elaboration."

        elif level_name == "theoretical":
            validated = output.get("validated", False)
            alignment = output.get("framework_alignment", 0)
            if validated:
                return f"Analyse validee avec {alignment:.0%} d'alignement theorique."
            return "Validation theorique en attente."

        return "Analyse en cours."

    def _generate_executive_summary(
        self, sections: list[SynthesizedSection], context: dict[str, Any]
    ) -> str:
        """Genere un resume executif a partir des sections."""
        territory = context.get("territory", "le territoire analyse")
        sector = context.get("sector", "le secteur etudie")

        # Extraire les elements cles
        discovery = next((s for s in sections if s.level == "discovery"), None)
        strategy = next((s for s in sections if s.level == "strategy"), None)
        scenario = next((s for s in sections if s.level == "scenario"), None)

        parts = [f"L'analyse de {sector} sur {territory} revele plusieurs elements significatifs."]

        if discovery and discovery.key_points:
            parts.append(f"Decouverte: {discovery.key_points[0]}" if discovery.key_points else "")

        if scenario and scenario.key_points:
            parts.append(f"Perspectives: {scenario.key_points[0]}" if scenario.key_points else "")

        if strategy and strategy.key_points:
            parts.append(
                f"Strategie recommandee: {strategy.key_points[0]}" if strategy.key_points else ""
            )

        return " ".join(filter(None, parts))

    def _parse_llm_response(
        self, response: str, cognitive_outputs: dict[str, dict[str, Any]], context: dict[str, Any]
    ) -> UnifiedSynthesis:
        """Parse la reponse LLM pour construire UnifiedSynthesis."""
        import json

        try:
            # Nettoyer le markdown code block si present
            cleaned_response = response.strip()
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            data = json.loads(cleaned_response)

            # Convertir les sections JSON en objets SynthesizedSection
            sections = []
            for sec in data.get("sections", []):
                level = sec.get("level", "unknown")
                # Recuperer les donnees brutes originales pour ce niveau
                original_data = cognitive_outputs.get(level, {})

                sections.append(
                    SynthesizedSection(
                        level=level,
                        title=sec.get("title", LEVEL_TITLES.get(level, level)),
                        summary=sec.get("summary", ""),
                        key_points=sec.get("key_points", []),
                        confidence=original_data.get(
                            "confidence", 0.8
                        ),  # Confiance par defaut si non dispo
                        data=original_data,
                    )
                )

            # Convertir les recommandations
            recommendations = data.get("recommendations", [])

            return UnifiedSynthesis(
                executive_summary=data.get("executive_summary", ""),
                sections=sections,
                recommendations=recommendations,
                overall_confidence=0.9,  # Confiance elevee car synthese LLM
                territory=context.get("territory"),
                sector=context.get("sector"),
                cognitive_signature={
                    k: v.get("confidence", 0.5) for k, v in cognitive_outputs.items()
                },
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON synthesis: {e}. Falling back to rule-based.")
            logger.debug(f"Raw response: {response}")

            # Fallback en utilisant la reponse brute comme resume si possible
            rule_based = self._synthesize_rule_based(cognitive_outputs, context)
            if len(response) < 2000:  # Si la reponse n'est pas trop longue, l'utiliser comme resume
                return UnifiedSynthesis(
                    executive_summary=response,
                    sections=rule_based.sections,
                    recommendations=rule_based.recommendations,
                    overall_confidence=rule_based.overall_confidence,
                    territory=context.get("territory"),
                    sector=context.get("sector"),
                    cognitive_signature=rule_based.cognitive_signature,
                )
            return rule_based
