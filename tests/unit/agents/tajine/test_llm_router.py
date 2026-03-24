"""Tests for HybridLLMRouter mode-to-tier mapping.

Task 1.1: Fix LLM Router Mode Complet -> POWERFUL tier
Mode Complet should route to POWERFUL tier (32b+ models) instead of using the same model as Rapide.
"""

import pytest

from src.infrastructure.agents.tajine.llm_router import HybridLLMRouter, ModelTier


class TestLLMRouterModeTier:
    """Tests for the get_tier_for_mode method."""

    def test_mode_rapide_returns_local_tier(self):
        """Mode rapide (fast) should use LOCAL tier for quick responses."""
        router = HybridLLMRouter()
        tier = router.get_tier_for_mode("rapide")
        assert tier == ModelTier.LOCAL

    def test_mode_complet_returns_powerful_tier(self):
        """Mode complet should use POWERFUL tier (32b+ models) for comprehensive analysis."""
        router = HybridLLMRouter()
        tier = router.get_tier_for_mode("complet")
        assert tier == ModelTier.POWERFUL

    def test_mode_expert_returns_maximum_tier(self):
        """Mode expert should use MAXIMUM tier for highest capability."""
        router = HybridLLMRouter()
        tier = router.get_tier_for_mode("expert")
        assert tier == ModelTier.MAXIMUM

    def test_unknown_mode_returns_standard_tier(self):
        """Unknown modes should default to STANDARD tier."""
        router = HybridLLMRouter()
        tier = router.get_tier_for_mode("unknown")
        assert tier == ModelTier.STANDARD

    def test_mode_is_case_insensitive(self):
        """Mode selection should be case-insensitive."""
        router = HybridLLMRouter()
        assert router.get_tier_for_mode("RAPIDE") == ModelTier.LOCAL
        assert router.get_tier_for_mode("Complet") == ModelTier.POWERFUL
        assert router.get_tier_for_mode("EXPERT") == ModelTier.MAXIMUM

    def test_mode_standard_returns_standard_tier(self):
        """Mode standard should use STANDARD tier for balanced responses."""
        router = HybridLLMRouter()
        tier = router.get_tier_for_mode("standard")
        assert tier == ModelTier.STANDARD
