"""Tests for the entity matcher.

This module tests entity matching across data sources, covering:
- MatchResult value object (fields, repr)
- EntityMatcher.match() with SIRET, SIREN and fuzzy name matching
- Near-identical names (case, accents, token order) -> high score
- Distinct names -> no match
- Threshold behaviour
- Edge cases: empty strings, None, missing keys, distinctive vs common tokens
- find_matches() and deduplicate() helpers

The production behaviour is the source of truth: assertions below were
validated against the real implementation in
src/domain/matching/entity_matcher.py.
"""

import pytest

from src.domain.matching.entity_matcher import EntityMatcher, MatchResult


@pytest.fixture
def matcher() -> EntityMatcher:
    """Default matcher instance."""
    return EntityMatcher()


class TestMatchResult:
    """Tests for the MatchResult value object."""

    def test_match_result_fields(self):
        """MatchResult should expose is_match, confidence and match_reasons."""
        result = MatchResult(
            is_match=True,
            confidence=95.0,
            match_reasons=["siret"],
            entity_a={"name": "A"},
            entity_b={"name": "B"},
        )

        assert result.is_match is True
        assert result.confidence == 95.0
        assert result.match_reasons == ["siret"]
        assert result.entity_a == {"name": "A"}
        assert result.entity_b == {"name": "B"}

    def test_match_result_defaults(self):
        """MatchResult should default collections to empty values."""
        result = MatchResult(is_match=False, confidence=0.0)

        assert result.match_reasons == []
        assert result.entity_a == {}
        assert result.entity_b == {}

    def test_match_result_repr_contains_reason(self):
        """repr() should surface the match reasons and rounded confidence."""
        result = MatchResult(
            is_match=True,
            confidence=88.456,
            match_reasons=["name(99%)"],
        )

        text = repr(result)

        assert "is_match=True" in text
        assert "88.5" in text  # confidence formatted with one decimal
        assert "name(99%)" in text


class TestNameMatching:
    """Tests for fuzzy name matching (near-identical names)."""

    def test_identical_names_match(self, matcher):
        """Identical names should yield a perfect score and a match."""
        result = matcher.match({"name": "ACME Corp"}, {"name": "ACME Corp"})

        assert result.is_match is True
        assert result.confidence == 100.0
        assert any("name" in reason for reason in result.match_reasons)

    def test_case_insensitive_names_match(self, matcher):
        """Names differing only by case should still score very high."""
        result = matcher.match({"name": "ACME Corp"}, {"name": "acme corp"})

        assert result.is_match is True
        assert result.confidence == 100.0

    def test_token_order_does_not_break_match(self, matcher):
        """Reordered tokens should still match thanks to token-based scoring."""
        result = matcher.match({"name": "Jean Dupont"}, {"name": "Dupont Jean"})

        assert result.is_match is True
        assert result.confidence == 100.0

    def test_accented_names_match_with_high_score(self, matcher):
        """Accents should not prevent a match for the same company name."""
        result = matcher.match(
            {"name": "Societe Generale"},
            {"name": "Société Générale"},
        )

        # Normalisation keeps accents, so the score is high but not perfect.
        assert result.is_match is True
        assert result.confidence >= matcher.match_threshold

    def test_suffix_variation_still_matches(self, matcher):
        """Legal suffixes are stripped, so SAS/SARL variants still match."""
        result = matcher.match(
            {"name": "Boulangerie Martin SAS"},
            {"name": "Boulangerie Martin SARL"},
        )

        assert result.is_match is True
        assert result.confidence >= matcher.match_threshold

    def test_distinct_names_do_not_match(self, matcher):
        """Clearly different names should not be considered a match."""
        result = matcher.match({"name": "Microsoft"}, {"name": "Carrefour"})

        assert result.is_match is False
        assert result.confidence < matcher.match_threshold
        assert result.match_reasons == []

    def test_distinctive_token_drives_match(self, matcher):
        """A shared distinctive token should produce a strong match."""
        result = matcher.match(
            {"name": "Neoen Energies"},
            {"name": "Neoen"},
        )

        assert result.is_match is True
        assert result.confidence >= matcher.match_threshold

    def test_common_token_alone_avoids_false_positive(self, matcher):
        """Sharing only a common/stripped token must not create a match."""
        # "FRANCE" is stripped as a common suffix, leaving "SOLAR" vs "WIND".
        result = matcher.match(
            {"name": "Solar France"},
            {"name": "Wind France"},
        )

        assert result.is_match is False
        assert result.confidence == 0.0


class TestSiretMatching:
    """Tests for SIRET / SIREN based matching."""

    def test_exact_siret_match_is_perfect(self, matcher):
        """Identical SIRET should yield 100% confidence regardless of name."""
        result = matcher.match(
            {"siret": "12345678901234", "name": "ACME"},
            {"siret": "12345678901234", "name": "Totally Different Name"},
        )

        assert result.is_match is True
        assert result.confidence == matcher.SIRET_MATCH_CONFIDENCE
        assert "siret" in result.match_reasons

    def test_siret_normalization_ignores_spaces(self, matcher):
        """SIRET with spaces should normalise to the same digits and match."""
        result = matcher.match(
            {"siret": "123 456 789 01234"},
            {"siret": "12345678901234"},
        )

        assert result.is_match is True
        assert result.confidence == matcher.SIRET_MATCH_CONFIDENCE

    def test_same_siren_different_siret_below_threshold(self, matcher):
        """Same SIREN but different SIRET is a weak signal (below default match)."""
        result = matcher.match(
            {"siret": "12345678901234"},
            {"siret": "12345678955555"},
        )

        # SIREN match reason recorded, but weighted confidence stays below 60.
        assert "siren" in result.match_reasons
        assert result.is_match is False
        assert result.confidence == pytest.approx(
            matcher.SIREN_MATCH_CONFIDENCE * matcher.siret_weight
        )

    def test_siren_plus_name_combines_into_match(self, matcher):
        """SIREN match combined with a strong name match should match."""
        result = matcher.match(
            {"siret": "12345678901234", "name": "ACME Corp"},
            {"siret": "12345678955555", "name": "ACME Corporation"},
        )

        assert result.is_match is True
        assert result.confidence > matcher.match_threshold
        assert "siren" in result.match_reasons
        assert any("name" in reason for reason in result.match_reasons)

    def test_siret_mismatch_penalizes_name_match(self, matcher):
        """Different SIRETs make a perfect name match unreliable -> no match."""
        result = matcher.match(
            {"siret": "11111111111111", "name": "ACME Corp"},
            {"siret": "22222222222222", "name": "ACME Corp"},
        )

        # Name reason still recorded, but confidence is heavily penalised.
        assert any("name" in reason for reason in result.match_reasons)
        assert result.is_match is False
        assert result.confidence < matcher.match_threshold


class TestThreshold:
    """Tests for the configurable match threshold."""

    def test_lower_threshold_promotes_siren_to_match(self):
        """A lower threshold should let a SIREN-only signal become a match."""
        strict = EntityMatcher()
        lenient = EntityMatcher(match_threshold=50)

        a = {"siret": "12345678901234"}
        b = {"siret": "12345678955555"}

        # Same confidence, different verdict driven purely by the threshold.
        strict_result = strict.match(a, b)
        lenient_result = lenient.match(a, b)

        assert strict_result.confidence == pytest.approx(lenient_result.confidence)
        assert strict_result.is_match is False
        assert lenient_result.is_match is True

    def test_higher_threshold_blocks_borderline_name(self):
        """A high threshold should reject a name match that would otherwise pass."""
        lenient = EntityMatcher(match_threshold=70)
        strict = EntityMatcher(match_threshold=95)

        a = {"name": "Société Générale"}
        b = {"name": "Societe Generale"}

        assert lenient.match(a, b).is_match is True
        assert strict.match(a, b).is_match is False


class TestEdgeCases:
    """Tests for empty / None / missing inputs."""

    def test_both_empty_names(self, matcher):
        """Two empty names should not match."""
        result = matcher.match({"name": ""}, {"name": ""})

        assert result.is_match is False
        assert result.confidence == 0.0
        assert result.match_reasons == []

    def test_none_names(self, matcher):
        """None names should be handled gracefully and not match."""
        result = matcher.match({"name": None}, {"name": None})

        assert result.is_match is False
        assert result.confidence == 0.0

    def test_missing_keys(self, matcher):
        """Entities with no usable fields should not match."""
        result = matcher.match({}, {})

        assert result.is_match is False
        assert result.confidence == 0.0
        assert result.match_reasons == []

    def test_one_empty_one_present_name(self, matcher):
        """An empty name on one side should yield no name match."""
        result = matcher.match({"name": ""}, {"name": "ACME Corp"})

        assert result.is_match is False
        assert result.confidence == 0.0

    def test_empty_siret_does_not_match(self, matcher):
        """Empty SIRET strings should not be treated as matching."""
        result = matcher.match({"siret": ""}, {"siret": ""})

        assert result.is_match is False
        assert result.confidence == 0.0


class TestFindMatches:
    """Tests for find_matches()."""

    def test_find_matches_returns_only_above_threshold(self, matcher):
        """find_matches should keep only candidates at/above the threshold."""
        target = {"siret": "12345678901234", "name": "ACME"}
        candidates = [
            {"siret": "12345678901234", "name": "Acme Corp"},  # exact SIRET
            {"name": "Totally Other"},  # no match
            {"siret": "12345678901234", "name": "ACME"},  # exact SIRET dup
        ]

        results = matcher.find_matches(target, candidates)

        assert len(results) == 2
        assert all(r.confidence >= matcher.match_threshold for r in results)

    def test_find_matches_sorted_descending(self, matcher):
        """Results should be sorted by confidence, highest first."""
        target = {"name": "Neoen"}
        candidates = [
            {"name": "Neoen Energies"},  # strong but partial
            {"name": "Neoen"},  # perfect
            {"name": "Carrefour"},  # no match
        ]

        results = matcher.find_matches(target, candidates)

        confidences = [r.confidence for r in results]
        assert confidences == sorted(confidences, reverse=True)

    def test_find_matches_min_confidence_override(self, matcher):
        """An explicit min_confidence should override the instance threshold."""
        target = {"name": "ACME"}
        candidates = [
            {"name": "ACME"},  # 100
            {"name": "ACMA"},  # close but below 99
        ]

        results = matcher.find_matches(target, candidates, min_confidence=99)

        assert len(results) == 1
        assert results[0].confidence >= 99

    def test_find_matches_empty_candidates(self, matcher):
        """No candidates should produce an empty result list."""
        assert matcher.find_matches({"name": "ACME"}, []) == []


class TestDeduplicate:
    """Tests for deduplicate()."""

    def test_deduplicate_groups_matching_entities(self, matcher):
        """Entities sharing a SIRET should be grouped together."""
        entities = [
            {"siret": "11111111111111", "name": "ACME Corp"},
            {"siret": "11111111111111", "name": "Acme Corporation"},
            {"siret": "99999999999999", "name": "Carrefour"},
        ]

        groups = matcher.deduplicate(entities)

        assert len(groups) == 2
        sizes = sorted(len(g) for g in groups)
        assert sizes == [1, 2]

    def test_deduplicate_empty_list(self, matcher):
        """Deduplicating an empty list should return an empty list."""
        assert matcher.deduplicate([]) == []

    def test_deduplicate_all_distinct(self, matcher):
        """Distinct entities should each land in their own group."""
        entities = [
            {"siret": "11111111111111", "name": "Microsoft"},
            {"siret": "22222222222222", "name": "Carrefour"},
            {"siret": "33333333333333", "name": "Renault"},
        ]

        groups = matcher.deduplicate(entities)

        assert len(groups) == 3
        assert all(len(g) == 1 for g in groups)

    def test_deduplicate_single_entity(self, matcher):
        """A single entity should form one group of one."""
        groups = matcher.deduplicate([{"name": "ACME"}])

        assert len(groups) == 1
        assert groups[0] == [{"name": "ACME"}]
