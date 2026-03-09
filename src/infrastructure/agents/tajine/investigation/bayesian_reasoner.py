"""
Bayesian Reasoner - Calcul de probabilité de risque.

Approche bayésienne:
- Prior: Taux de défaillance du secteur
- Likelihood Ratios: Multiplicateurs par signal observé
- Posterior: Probabilité ajustée après observation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any

from .signal_extractor import SECTOR_PRIORS, Signal, SignalCategory, SignalImpact


class RiskLevel(StrEnum):
    """Niveau de risque calculé."""

    LOW = "FAIBLE"
    MODERATE = "MODÉRÉ"
    ELEVATED = "MODÉRÉ-ÉLEVÉ"
    HIGH = "ÉLEVÉ"
    CRITICAL = "CRITIQUE"


@dataclass
class FactorContribution:
    """Contribution d'un facteur au risque final."""

    signal_name: str
    likelihood_ratio: float
    contribution: float  # Impact sur le posterior (en points)
    direction: str  # "+" ou "-"


@dataclass
class RiskAssessment:
    """Résultat de l'évaluation bayésienne."""

    prior: float
    posterior: float
    risk_level: RiskLevel
    confidence: float  # Confiance dans l'évaluation (0-1)
    data_coverage: float  # Couverture des données (0-1)
    key_factors: list[FactorContribution] = field(default_factory=list)
    main_concerns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "prior": round(self.prior, 4),
            "posterior": round(self.posterior, 4),
            "risk_level": self.risk_level.value,
            "confidence": round(self.confidence, 2),
            "data_coverage": round(self.data_coverage, 2),
            "key_factors": [
                {
                    "signal": f.signal_name,
                    "lr": f.likelihood_ratio,
                    "contribution": f"{f.direction}{abs(f.contribution):.2f}",
                }
                for f in self.key_factors
            ],
            "main_concerns": self.main_concerns,
        }


class BayesianReasoner:
    """
    Raisonneur bayésien pour évaluation de risque.

    Formule: P(risque|signaux) = P(risque) × ∏ LR(signal_i) / Normalisation

    Contrairement à un score binaire, cette approche:
    - Est transparente (chaque LR est explicable)
    - Quantifie l'incertitude (confidence)
    - Identifie les facteurs clés de risque
    """

    # Seuils pour classification du risque
    RISK_THRESHOLDS = {
        RiskLevel.LOW: 0.10,
        RiskLevel.MODERATE: 0.25,
        RiskLevel.ELEVATED: 0.40,
        RiskLevel.HIGH: 0.60,
        RiskLevel.CRITICAL: 1.0,
    }

    def __init__(self) -> None:
        """Initialize the reasoner."""
        self._signals: list[Signal] = []

    def compute(
        self,
        signals: list[Signal],
        naf_code: str | None = None,
    ) -> RiskAssessment:
        """
        Compute risk assessment from signals.

        Args:
            signals: List of extracted signals
            naf_code: NAF code for sector-specific prior

        Returns:
            RiskAssessment with posterior probability and factors
        """
        self._signals = signals

        # Get prior from sector
        prior = self._get_prior(naf_code, signals)

        # Compute product of likelihood ratios
        lr_product = 1.0
        factors: list[FactorContribution] = []

        for signal in signals:
            lr = signal.likelihood_ratio

            # Skip neutral signals (LR = 1)
            if abs(lr - 1.0) < 0.01:
                continue

            lr_product *= lr

            # Calculate contribution (difference from neutral)
            contribution = (lr - 1.0) * prior
            direction = "+" if lr > 1 else "-"

            factors.append(
                FactorContribution(
                    signal_name=signal.name,
                    likelihood_ratio=lr,
                    contribution=abs(contribution),
                    direction=direction,
                )
            )

        # Compute posterior using Bayes' formula
        # P(R|S) = P(R) * LR / (P(R) * LR + (1-P(R)))
        numerator = prior * lr_product
        denominator = numerator + (1 - prior)
        posterior = numerator / denominator if denominator > 0 else prior

        # Clamp to [0, 1]
        posterior = max(0.0, min(1.0, posterior))

        # Determine risk level
        risk_level = self._classify_risk(posterior)

        # Calculate confidence based on signal coverage and consistency
        confidence = self._calculate_confidence(signals)

        # Calculate data coverage
        data_coverage = self._calculate_coverage(signals)

        # Extract main concerns
        main_concerns = self._extract_concerns(signals)

        # Sort factors by absolute contribution
        factors.sort(key=lambda f: f.contribution, reverse=True)

        return RiskAssessment(
            prior=prior,
            posterior=posterior,
            risk_level=risk_level,
            confidence=confidence,
            data_coverage=data_coverage,
            key_factors=factors[:5],  # Top 5 factors
            main_concerns=main_concerns[:3],  # Top 3 concerns
        )

    def _get_prior(self, naf_code: str | None, signals: list[Signal]) -> float:
        """Get prior probability from NAF code or signals."""
        if naf_code:
            section = naf_code[:2] if len(naf_code) >= 2 else naf_code
            return SECTOR_PRIORS.get(section, SECTOR_PRIORS["default"])

        # Try to extract NAF from signals
        for signal in signals:
            if signal.name in ("secteur_risque", "secteur_stable"):
                naf = str(signal.value)
                section = naf[:2] if len(naf) >= 2 else naf
                return SECTOR_PRIORS.get(section, SECTOR_PRIORS["default"])

        return SECTOR_PRIORS["default"]

    def _classify_risk(self, posterior: float) -> RiskLevel:
        """Classify risk level based on posterior probability."""
        for level, threshold in sorted(
            self.RISK_THRESHOLDS.items(), key=lambda x: x[1]
        ):
            if posterior <= threshold:
                return level
        return RiskLevel.CRITICAL

    def _calculate_confidence(self, signals: list[Signal]) -> float:
        """
        Calculate confidence in the assessment.

        Confidence is higher when:
        - More signals are available
        - Signals are consistent (all positive or all negative)
        - Critical sources (BODACC, SIRENE) responded
        """
        if not signals:
            return 0.1

        # Base confidence from signal count
        signal_count_score = min(1.0, len(signals) / 10)

        # Check critical source coverage
        sources = {s.source for s in signals}
        critical_sources = {"SIRENE", "BODACC"}
        source_coverage = len(sources & critical_sources) / len(critical_sources)

        # Check signal consistency
        negative_count = sum(
            1 for s in signals if s.impact in (SignalImpact.NEGATIVE, SignalImpact.CRITICAL)
        )
        positive_count = sum(1 for s in signals if s.impact == SignalImpact.POSITIVE)
        total_directional = negative_count + positive_count

        if total_directional > 0:
            consistency = abs(negative_count - positive_count) / total_directional
        else:
            consistency = 0.5

        # Weighted combination
        confidence = (
            0.3 * signal_count_score + 0.4 * source_coverage + 0.3 * consistency
        )

        return round(confidence, 2)

    def _calculate_coverage(self, signals: list[Signal]) -> float:
        """
        Calculate data coverage (% of available public data collected).

        Based on expected signal categories.
        """
        expected_categories = {
            SignalCategory.FINANCIAL,
            SignalCategory.LEGAL,
            SignalCategory.OPERATIONAL,
        }
        covered_categories = {s.category for s in signals}

        base_coverage = len(covered_categories & expected_categories) / len(
            expected_categories
        )

        # Bonus for having multiple signals per category
        category_counts = {}
        for s in signals:
            category_counts[s.category] = category_counts.get(s.category, 0) + 1

        depth_bonus = min(0.2, sum(min(c, 3) for c in category_counts.values()) / 15)

        return round(min(1.0, base_coverage + depth_bonus), 2)

    def _extract_concerns(self, signals: list[Signal]) -> list[str]:
        """Extract main concerns from negative signals."""
        concerns = []

        for signal in signals:
            if signal.impact in (SignalImpact.NEGATIVE, SignalImpact.CRITICAL):
                if signal.details:
                    concerns.append(signal.details)
                else:
                    concerns.append(signal.name.replace("_", " ").title())

        # Sort by likelihood ratio (most impactful first)
        concern_lr = {
            c: next(
                (s.likelihood_ratio for s in signals if s.details == c or s.name.replace("_", " ").title() == c),
                1.0,
            )
            for c in concerns
        }
        concerns.sort(key=lambda c: concern_lr.get(c, 1.0), reverse=True)

        return concerns
