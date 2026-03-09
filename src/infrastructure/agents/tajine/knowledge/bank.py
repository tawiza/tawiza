"""
TheoryBank - Centralized repository of economic/geographic theories.

Provides structured access to theories for:
- TheoreticalLevel validation
- Strategy alignment scoring
- Research recommendations
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class Theory:
    """A single economic/geographic theory."""

    key: str
    name: str
    author: str
    category: str
    description: str
    indicators: list[str]
    strategy_alignment: dict[str, float]

    def get_alignment(self, strategy_type: str) -> float:
        """Get alignment score for a strategy type."""
        return self.strategy_alignment.get(strategy_type, 0.5)

    def matches_indicators(self, signals: list[str]) -> float:
        """Calculate how well signals match this theory's indicators."""
        if not self.indicators:
            return 0.0
        matches = sum(1 for s in signals if s in self.indicators)
        return matches / len(self.indicators)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'key': self.key,
            'name': self.name,
            'author': self.author,
            'category': self.category,
            'description': self.description,
            'indicators': self.indicators,
            'strategy_alignment': self.strategy_alignment,
        }


class TheoryBank:
    """
    Central repository of economic/geographic theories.

    Loads theories from JSON and provides query methods for:
    - Finding relevant theories by category
    - Matching theories to observed signals
    - Validating strategies against theoretical frameworks
    """

    def __init__(self, theories_path: Path | None = None):
        """
        Initialize TheoryBank.

        Args:
            theories_path: Path to theories.json (default: same directory)
        """
        if theories_path is None:
            theories_path = Path(__file__).parent / "theories.json"

        self._theories: dict[str, Theory] = {}
        self._categories: dict[str, list[str]] = {}

        self._load_theories(theories_path)
        logger.info(f"TheoryBank loaded {len(self._theories)} theories")

    def _load_theories(self, path: Path) -> None:
        """Load theories from JSON file."""
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)

            for key, theory_data in data.items():
                theory = Theory(
                    key=key,
                    name=theory_data['name'],
                    author=theory_data['author'],
                    category=theory_data['category'],
                    description=theory_data['description'],
                    indicators=theory_data['indicators'],
                    strategy_alignment=theory_data['strategy_alignment'],
                )
                self._theories[key] = theory

                # Index by category
                cat = theory.category
                if cat not in self._categories:
                    self._categories[cat] = []
                self._categories[cat].append(key)

        except Exception as e:
            logger.error(f"Failed to load theories: {e}")
            raise

    def get(self, key: str) -> Theory | None:
        """Get a theory by key."""
        return self._theories.get(key)

    def get_all(self) -> dict[str, Theory]:
        """Get all theories."""
        return self._theories.copy()

    def get_by_category(self, category: str) -> list[Theory]:
        """Get all theories in a category."""
        keys = self._categories.get(category, [])
        return [self._theories[k] for k in keys]

    def get_categories(self) -> list[str]:
        """Get all category names."""
        return list(self._categories.keys())

    def find_relevant(
        self,
        signals: list[str],
        min_relevance: float = 0.3
    ) -> list[tuple[Theory, float]]:
        """
        Find theories relevant to observed signals.

        Args:
            signals: List of observed signal types
            min_relevance: Minimum relevance threshold

        Returns:
            List of (theory, relevance_score) tuples, sorted by relevance
        """
        results = []

        for theory in self._theories.values():
            relevance = theory.matches_indicators(signals)
            if relevance >= min_relevance:
                results.append((theory, relevance))

        return sorted(results, key=lambda x: x[1], reverse=True)

    def validate_strategy(
        self,
        strategy_type: str,
        signals: list[str],
        top_n: int = 5
    ) -> dict[str, Any]:
        """
        Validate a strategy type against relevant theories.

        Args:
            strategy_type: Strategy type (investment, monitoring, etc.)
            signals: Observed signals
            top_n: Number of top theories to consider

        Returns:
            Dict with alignment score, supporting/conflicting theories
        """
        relevant = self.find_relevant(signals)[:top_n]

        if not relevant:
            return {
                'alignment_score': 0.5,
                'supporting': [],
                'conflicting': [],
                'neutral': [],
            }

        supporting = []
        conflicting = []
        neutral = []
        total_alignment = 0.0

        for theory, relevance in relevant:
            alignment = theory.get_alignment(strategy_type)
            weighted = alignment * relevance
            total_alignment += weighted

            entry = {
                'theory': theory.name,
                'author': theory.author,
                'alignment': round(alignment, 2),
                'relevance': round(relevance, 2),
            }

            if alignment >= 0.7:
                supporting.append(entry)
            elif alignment <= 0.3:
                conflicting.append(entry)
            else:
                neutral.append(entry)

        avg_alignment = total_alignment / len(relevant) if relevant else 0.5

        return {
            'alignment_score': round(avg_alignment, 2),
            'supporting': supporting,
            'conflicting': conflicting,
            'neutral': neutral,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the theory bank."""
        return {
            'total_theories': len(self._theories),
            'categories': len(self._categories),
            'theories_by_category': {
                cat: len(keys) for cat, keys in self._categories.items()
            },
        }


# Global instance for convenience
_default_bank: TheoryBank | None = None


def get_theory_bank() -> TheoryBank:
    """Get the default TheoryBank instance."""
    global _default_bank
    if _default_bank is None:
        _default_bank = TheoryBank()
    return _default_bank


# Export THEORIES dict for backward compatibility
def get_theories_dict() -> dict[str, dict[str, Any]]:
    """Get theories as a plain dict (backward compatibility)."""
    bank = get_theory_bank()
    return {k: v.to_dict() for k, v in bank.get_all().items()}


# Lazy-loaded THEORIES for backward compatibility with existing imports
class _LazyTheories:
    """Lazy-loaded THEORIES dict for backward compatibility."""

    _data: dict[str, dict[str, Any]] | None = None

    def __getitem__(self, key: str) -> dict[str, Any]:
        if self._data is None:
            self._data = self._load()
        return self._data[key]

    def __iter__(self):
        if self._data is None:
            self._data = self._load()
        return iter(self._data)

    def __len__(self):
        if self._data is None:
            self._data = self._load()
        return len(self._data)

    def items(self):
        if self._data is None:
            self._data = self._load()
        return self._data.items()

    def keys(self):
        if self._data is None:
            self._data = self._load()
        return self._data.keys()

    def values(self):
        if self._data is None:
            self._data = self._load()
        return self._data.values()

    def get(self, key: str, default=None):
        if self._data is None:
            self._data = self._load()
        return self._data.get(key, default)

    def _load(self) -> dict[str, dict[str, Any]]:
        """Load theories from JSON file."""
        path = Path(__file__).parent / "theories.json"
        with open(path, encoding='utf-8') as f:
            return json.load(f)


THEORIES = _LazyTheories()
