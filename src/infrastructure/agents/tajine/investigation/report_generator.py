"""
Report Generator - Génération de rapport d'investigation.

Structure du rapport:
- CE QU'ON SAIT (faits vérifiés)
- CE QUI EST SUSPECT (signaux à investiguer)
- CE QUI MANQUE (données non disponibles)
- QUESTIONS À POSER (au demandeur)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .bayesian_reasoner import RiskAssessment
from .signal_extractor import Signal, SignalCategory, SignalImpact


@dataclass
class KnownFact:
    """Un fait vérifié dans l'investigation."""

    category: str
    fact: str
    source: str
    impact: str
    details: str = ""


@dataclass
class SuspectSignal:
    """Un signal suspect à investiguer."""

    signal: str
    reason: str
    recommendation: str


@dataclass
class MissingData:
    """Donnée manquante dans l'investigation."""

    variable: str
    importance: str  # CRITIQUE, HAUTE, MOYENNE
    suggestion: str


@dataclass
class InvestigationReport:
    """Rapport complet d'investigation entreprise."""

    siren: str
    denomination: str
    investigation_date: datetime
    summary: RiskAssessment
    known_facts: list[KnownFact]
    suspect_signals: list[SuspectSignal]
    missing_data: list[MissingData]
    questions_for_applicant: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "siren": self.siren,
            "denomination": self.denomination,
            "investigation_date": self.investigation_date.isoformat(),
            "summary": self.summary.to_dict(),
            "known_facts": [
                {
                    "category": f.category,
                    "fact": f.fact,
                    "source": f.source,
                    "impact": f.impact,
                    "details": f.details,
                }
                for f in self.known_facts
            ],
            "suspect_signals": [
                {
                    "signal": s.signal,
                    "reason": s.reason,
                    "recommendation": s.recommendation,
                }
                for s in self.suspect_signals
            ],
            "missing_data": [
                {
                    "variable": m.variable,
                    "importance": m.importance,
                    "suggestion": m.suggestion,
                }
                for m in self.missing_data
            ],
            "questions_for_applicant": self.questions_for_applicant,
            "bayesian_details": self.summary.to_dict(),
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Rapport d'Investigation",
            "",
            f"**SIREN:** {self.siren}",
            f"**Dénomination:** {self.denomination}",
            f"**Date:** {self.investigation_date.strftime('%d/%m/%Y %H:%M')}",
            "",
            "---",
            "",
            "## 📊 Évaluation",
            "",
            "| Critère | Valeur |",
            "|---------|--------|",
            f"| **Niveau de risque** | {self.summary.risk_level.value} |",
            f"| **Probabilité** | {self.summary.posterior*100:.1f}% |",
            f"| **Confiance** | {self.summary.confidence*100:.0f}% |",
            f"| **Couverture données** | {self.summary.data_coverage*100:.0f}% |",
            "",
        ]

        if self.summary.main_concerns:
            lines.extend([
                "**Préoccupations principales:**",
            ])
            for concern in self.summary.main_concerns:
                lines.append(f"- {concern}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## ✅ Ce qu'on sait",
            "",
        ])

        for fact in self.known_facts:
            emoji = "🟢" if fact.impact == "POSITIF" else "🟡" if fact.impact == "NEUTRE" else "🔴"
            lines.append(f"- {emoji} **{fact.category}**: {fact.fact} ({fact.source})")
            if fact.details:
                lines.append(f"  - {fact.details}")

        lines.extend([
            "",
            "---",
            "",
            "## ⚠️ Points d'attention",
            "",
        ])

        if self.suspect_signals:
            for signal in self.suspect_signals:
                lines.extend([
                    f"### {signal.signal}",
                    "",
                    f"**Raison:** {signal.reason}",
                    "",
                    f"**Recommandation:** {signal.recommendation}",
                    "",
                ])
        else:
            lines.append("*Aucun signal suspect détecté.*")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## ❓ Données manquantes",
            "",
        ])

        if self.missing_data:
            lines.append("| Variable | Importance | Suggestion |")
            lines.append("|----------|------------|------------|")
            for m in self.missing_data:
                lines.append(f"| {m.variable} | {m.importance} | {m.suggestion} |")
            lines.append("")
        else:
            lines.append("*Toutes les données principales sont disponibles.*")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## 📝 Questions à poser au demandeur",
            "",
        ])

        for i, q in enumerate(self.questions_for_applicant, 1):
            lines.append(f"{i}. {q}")

        lines.extend([
            "",
            "---",
            "",
            "*Rapport généré automatiquement par TAJINE Investigation Engine*",
        ])

        return "\n".join(lines)


# Templates de questions par type de signal
QUESTION_TEMPLATES = {
    "privileges_inss_multiples": [
        "Pouvez-vous fournir un échéancier de remboursement des privilèges INSS déclarés?",
        "Quelle est la situation actuelle vis-à-vis de l'URSSAF?",
    ],
    "privilege_unique": [
        "Pouvez-vous expliquer le privilège déclaré et son état de régularisation?",
    ],
    "procedure_collective_passee": [
        "Comment l'entreprise s'est-elle restructurée depuis la procédure collective?",
        "Quelles mesures ont été prises pour éviter une nouvelle situation de difficulté?",
    ],
    "age_moins_2ans": [
        "Quel est le business plan pour les 3 prochaines années?",
        "Quels sont vos premiers clients et votre traction commerciale?",
    ],
    "transferts_siege_multiples": [
        "Quelle est la raison des transferts de siège social récents?",
    ],
    "secteur_risque": [
        "Comment vous différenciez-vous de la concurrence dans ce secteur?",
        "Quelles mesures de gestion des risques avez-vous mises en place?",
    ],
    "default": [
        "Pouvez-vous fournir une attestation de régularité fiscale datée de moins de 3 mois?",
        "Pouvez-vous fournir les bilans des 2 derniers exercices?",
    ],
}

# Données manquantes standards
STANDARD_MISSING_DATA = [
    MissingData(
        variable="Situation fiscale réelle",
        importance="CRITIQUE",
        suggestion="Demander attestation fiscale récente",
    ),
    MissingData(
        variable="Bilans comptables",
        importance="HAUTE",
        suggestion="Demander liasses fiscales 2 derniers exercices",
    ),
    MissingData(
        variable="Situation bancaire",
        importance="HAUTE",
        suggestion="Demander relevés bancaires 6 derniers mois",
    ),
]


class ReportGenerator:
    """Générateur de rapports d'investigation."""

    def __init__(self) -> None:
        """Initialize the report generator."""
        pass

    def generate(
        self,
        siren: str,
        signals: list[Signal],
        assessment: RiskAssessment,
        context: str = "",
        denomination: str = "Entreprise",
    ) -> InvestigationReport:
        """
        Generate a complete investigation report.

        Args:
            siren: SIREN number
            signals: Extracted signals
            assessment: Bayesian risk assessment
            context: Investigation context (e.g., "Demande France 2030")
            denomination: Company name

        Returns:
            Complete InvestigationReport
        """
        # Extract company name from signals if available
        for signal in signals:
            if signal.name == "denomination":
                denomination = str(signal.value)
                break

        # Build known facts
        known_facts = self._build_known_facts(signals)

        # Build suspect signals
        suspect_signals = self._build_suspect_signals(signals)

        # Build missing data
        missing_data = self._build_missing_data(signals)

        # Generate questions
        questions = self._generate_questions(signals, context)

        return InvestigationReport(
            siren=siren,
            denomination=denomination,
            investigation_date=datetime.now(),
            summary=assessment,
            known_facts=known_facts,
            suspect_signals=suspect_signals,
            missing_data=missing_data,
            questions_for_applicant=questions,
        )

    def _build_known_facts(self, signals: list[Signal]) -> list[KnownFact]:
        """Build list of known facts from signals."""
        facts = []

        for signal in signals:
            # Skip error signals
            if signal.name.endswith("_error"):
                continue

            impact_map = {
                SignalImpact.POSITIVE: "POSITIF",
                SignalImpact.NEUTRAL: "NEUTRE",
                SignalImpact.NEGATIVE: "NÉGATIF",
                SignalImpact.CRITICAL: "CRITIQUE",
            }

            category_map = {
                SignalCategory.FINANCIAL: "Financier",
                SignalCategory.LEGAL: "Légal",
                SignalCategory.OPERATIONAL: "Opérationnel",
                SignalCategory.DIRECTOR: "Dirigeant",
                SignalCategory.WEAK_SIGNAL: "Signal faible",
            }

            facts.append(
                KnownFact(
                    category=category_map.get(signal.category, "Autre"),
                    fact=signal.name.replace("_", " ").title(),
                    source=signal.source,
                    impact=impact_map.get(signal.impact, "NEUTRE"),
                    details=signal.details,
                )
            )

        return facts

    def _build_suspect_signals(self, signals: list[Signal]) -> list[SuspectSignal]:
        """Build list of suspect signals requiring attention."""
        suspects = []

        suspect_configs = {
            "privileges_inss_multiples": {
                "reason": "Indicateur de difficultés de trésorerie",
                "recommendation": "Vérifier la situation actuelle avec l'URSSAF",
            },
            "privilege_unique": {
                "reason": "Possible difficulté ponctuelle de trésorerie",
                "recommendation": "Demander justification et plan de régularisation",
            },
            "procedure_collective_passee": {
                "reason": "Antécédent de difficultés financières majeures",
                "recommendation": "Vérifier les mesures de restructuration",
            },
            "transferts_siege_multiples": {
                "reason": "Peut indiquer fuite de créanciers ou restructuration",
                "recommendation": "Demander justification des transferts",
            },
            "age_moins_2ans": {
                "reason": "Entreprise récente, historique limité",
                "recommendation": "Examiner le business plan et la traction",
            },
            "dirigeant_multi_faillites": {
                "reason": "Antécédent de difficultés avec d'autres entreprises",
                "recommendation": "Vérifier séparation des activités",
            },
            "secteur_risque": {
                "reason": "Secteur avec taux de défaillance élevé",
                "recommendation": "Examiner les mesures de différenciation",
            },
        }

        for signal in signals:
            if signal.name in suspect_configs:
                config = suspect_configs[signal.name]
                suspects.append(
                    SuspectSignal(
                        signal=signal.details or signal.name.replace("_", " ").title(),
                        reason=config["reason"],
                        recommendation=config["recommendation"],
                    )
                )

        return suspects

    def _build_missing_data(self, signals: list[Signal]) -> list[MissingData]:
        """Build list of missing data based on signal coverage."""
        missing = []

        # Check which critical sources responded
        {s.source for s in signals}

        # Always add standard missing data (private sources)
        for std_missing in STANDARD_MISSING_DATA:
            missing.append(std_missing)

        # Add source-specific missing if errors occurred
        for signal in signals:
            if signal.name == "bodacc_error":
                missing.append(
                    MissingData(
                        variable="Annonces légales BODACC",
                        importance="HAUTE",
                        suggestion="Vérifier manuellement sur bodacc.fr",
                    )
                )
            elif signal.name == "sirene_error":
                missing.append(
                    MissingData(
                        variable="Données entreprise SIRENE",
                        importance="CRITIQUE",
                        suggestion="Vérifier le numéro SIREN",
                    )
                )

        return missing

    def _generate_questions(
        self, signals: list[Signal], context: str
    ) -> list[str]:
        """Generate questions to ask the applicant."""
        questions = set()

        # Add questions based on detected signals
        for signal in signals:
            if signal.name in QUESTION_TEMPLATES:
                for q in QUESTION_TEMPLATES[signal.name]:
                    questions.add(q)

        # Always add default questions
        for q in QUESTION_TEMPLATES["default"]:
            questions.add(q)

        # Context-specific questions
        if "france 2030" in context.lower():
            questions.add(
                "Comment ce projet s'inscrit-il dans les objectifs France 2030?"
            )
        if "innovation" in context.lower():
            questions.add(
                "Pouvez-vous détailler la dimension innovante de votre projet?"
            )
        if "subvention" in context.lower():
            questions.add(
                "Quel est le montant de la subvention demandée et son utilisation prévue?"
            )

        return list(questions)[:8]  # Limit to 8 questions
