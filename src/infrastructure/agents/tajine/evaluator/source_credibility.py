"""Source Credibility Scorer - Bayesian source reliability."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class SourceCredibilityScorer:
    """
    Bayesian source credibility scoring.

    Uses prior knowledge about sources combined with
    observed accuracy to compute posterior reliability scores.
    """

    # Prior credibility scores by source type
    PRIORS: dict[str, float] = field(
        default_factory=lambda: {
            # Official government sources
            "sirene": 0.95,
            "bodacc": 0.90,
            "boamp": 0.90,
            "dvf": 0.92,
            "ban": 0.93,
            # Institutional sources
            "insee": 0.88,
            "bdf": 0.85,  # Banque de France
            "infogreffe": 0.85,
            # Semi-official
            "pappers": 0.80,
            "societe.com": 0.75,
            # Media/Press
            "rss_presse": 0.70,
            "afp": 0.75,
            # Corporate
            "corporate": 0.60,
            # User-generated
            "blog": 0.30,
            "forum": 0.20,
            # Unknown
            "unknown": 0.10,
        }
    )

    # Store posteriors and observations
    posteriors: dict[str, float] = field(default_factory=dict)
    observations: dict[str, list[bool]] = field(default_factory=lambda: defaultdict(list))

    def __post_init__(self):
        """Initialize posteriors from priors."""
        self.posteriors = dict(self.PRIORS)

    def score(self, source: str) -> float:
        """
        Get credibility score for a source.

        Args:
            source: Source identifier

        Returns:
            Credibility score between 0 and 1
        """
        # Check posteriors first (learned)
        if source in self.posteriors:
            return self.posteriors[source]

        # Fall back to priors
        return self.PRIORS.get(source, self.PRIORS["unknown"])

    def update(self, source: str, was_correct: bool):
        """
        Update source credibility after observation.

        Uses simplified Beta-Bernoulli conjugate update:
        posterior_mean = (prior * n_prior + successes) / (n_prior + n_obs)

        Args:
            source: Source identifier
            was_correct: Whether the data from this source was correct
        """
        self.observations[source].append(was_correct)

        obs = self.observations[source]
        successes = sum(obs)
        n_obs = len(obs)

        # Prior strength (how many observations is the prior worth)
        n_prior = 5
        prior = self.PRIORS.get(source, 0.5)

        # Beta posterior mean
        posterior = (prior * n_prior + successes) / (n_prior + n_obs)

        # Clamp to [0.01, 0.99] to avoid extremes
        self.posteriors[source] = max(0.01, min(0.99, posterior))

    def get_observation_count(self, source: str) -> int:
        """Get number of observations for a source."""
        return len(self.observations.get(source, []))

    def get_success_rate(self, source: str) -> float:
        """Get empirical success rate for a source."""
        obs = self.observations.get(source, [])
        if not obs:
            return self.PRIORS.get(source, 0.5)
        return sum(obs) / len(obs)

    def reset(self, source: str | None = None):
        """Reset observations and posteriors."""
        if source:
            self.observations.pop(source, None)
            self.posteriors[source] = self.PRIORS.get(source, 0.5)
        else:
            self.observations.clear()
            self.posteriors = dict(self.PRIORS)
