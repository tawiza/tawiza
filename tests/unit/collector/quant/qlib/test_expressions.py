"""Tests for the qlib alpha expressions library.

This module tests the predefined alpha expression helpers used for
territorial intelligence, including:
- get_required_metrics (metric extraction from a formula)
- validate_expression_metrics (availability validation)
- get_compatible_expressions (filtering by available metrics)
- describe_expression (metadata lookup for known/unknown names)
- get_expressions_by_category (category lookup)
- get_expression_set (predefined sets)
- create_custom_expression (registration + side effects)
"""

import copy

import pytest

from src.collector.quant.qlib import expressions
from src.collector.quant.qlib.expressions import (
    ALPHA_EXPRESSIONS,
    DEFAULT_EXPRESSION_SETS,
    EXPRESSION_CATEGORIES,
    EXPRESSION_METADATA,
    create_custom_expression,
    describe_expression,
    get_compatible_expressions,
    get_expression_set,
    get_expressions_by_category,
    get_required_metrics,
    validate_expression_metrics,
)


@pytest.fixture
def restore_module_state():
    """Snapshot and restore the mutable module-level registries.

    create_custom_expression mutates ALPHA_EXPRESSIONS, EXPRESSION_METADATA
    and EXPRESSION_CATEGORIES in place, so tests that register custom
    expressions must restore the original state to stay isolated.
    """
    saved_expressions = copy.deepcopy(expressions.ALPHA_EXPRESSIONS)
    saved_metadata = copy.deepcopy(expressions.EXPRESSION_METADATA)
    saved_categories = copy.deepcopy(expressions.EXPRESSION_CATEGORIES)
    try:
        yield
    finally:
        expressions.ALPHA_EXPRESSIONS.clear()
        expressions.ALPHA_EXPRESSIONS.update(saved_expressions)
        expressions.EXPRESSION_METADATA.clear()
        expressions.EXPRESSION_METADATA.update(saved_metadata)
        expressions.EXPRESSION_CATEGORIES.clear()
        expressions.EXPRESSION_CATEGORIES.update(saved_categories)


class TestGetRequiredMetrics:
    """Tests for get_required_metrics()."""

    def test_single_metric(self):
        """Should extract a single metric without the $ prefix."""
        assert get_required_metrics("Rank($creation_entreprise)") == [
            "creation_entreprise"
        ]

    def test_multiple_metrics_in_order(self):
        """Should extract all metrics, preserving order and duplicates."""
        formula = "$liquidation_judiciaire / ($creation_entreprise + 1)"
        assert get_required_metrics(formula) == [
            "liquidation_judiciaire",
            "creation_entreprise",
        ]

    def test_duplicate_metric_appears_twice(self):
        """Repeated metrics should each be captured (findall semantics)."""
        formula = "$creation_entreprise / Mean($creation_entreprise, 12)"
        assert get_required_metrics(formula) == [
            "creation_entreprise",
            "creation_entreprise",
        ]

    def test_no_metrics(self):
        """A formula without $ variables should yield an empty list."""
        assert get_required_metrics("Rank(42)") == []

    def test_matches_real_expression_in_library(self):
        """Extraction should work on a real library formula."""
        formula = ALPHA_EXPRESSIONS["convergence_negative"]
        assert get_required_metrics(formula) == [
            "liquidation_judiciaire",
            "fermeture_entreprise",
        ]


class TestValidateExpressionMetrics:
    """Tests for validate_expression_metrics()."""

    def test_sufficient_metrics_returns_true(self):
        """All required metrics available -> True."""
        # sante_entreprises needs liquidation_judiciaire + creation_entreprise
        assert (
            validate_expression_metrics(
                "sante_entreprises",
                ["liquidation_judiciaire", "creation_entreprise", "extra_metric"],
            )
            is True
        )

    def test_missing_metric_returns_false(self):
        """A missing required metric -> False."""
        assert (
            validate_expression_metrics(
                "sante_entreprises",
                ["liquidation_judiciaire"],  # missing creation_entreprise
            )
            is False
        )

    def test_empty_available_metrics_returns_false(self):
        """No available metrics for an expression that needs some -> False."""
        assert validate_expression_metrics("sante_entreprises", []) is False

    def test_unknown_expression_returns_false(self):
        """An unknown expression name -> False (not an exception)."""
        assert (
            validate_expression_metrics("not_a_real_expression", ["anything"])
            is False
        )

    def test_expression_without_metrics_is_always_valid(self):
        """LLM-merged formulas use no $ prefix, so they need zero metrics.

        get_required_metrics returns [] for them, so all() over an empty
        iterable is True even with no available metrics.
        """
        # employment_pressure_index formula = "offres_emploi / (creation_entreprise + 1)"
        # contains no $ variables, so required metrics is empty.
        assert get_required_metrics(ALPHA_EXPRESSIONS["employment_pressure_index"]) == []
        assert validate_expression_metrics("employment_pressure_index", []) is True


class TestGetCompatibleExpressions:
    """Tests for get_compatible_expressions()."""

    def test_filters_to_only_computable_expressions(self):
        """With a narrow metric set, only matching expressions are returned."""
        # Only provide creation_entreprise -> rang_creation should be computable,
        # but sante_entreprises (needs liquidation_judiciaire too) should not.
        compatible = get_compatible_expressions(["creation_entreprise"])

        assert "rang_creation" in compatible
        assert "sante_entreprises" not in compatible

    def test_empty_metrics_only_metricless_expressions(self):
        """With no metrics, only $-free expressions remain compatible."""
        compatible = get_compatible_expressions([])

        # LLM-merged factors have no $ variables -> compatible with zero metrics.
        assert "employment_pressure_index" in compatible
        # Anything needing a $ metric must be excluded.
        assert "rang_creation" not in compatible

    def test_all_metrics_returns_every_expression(self):
        """Providing every referenced metric should make all expressions compatible."""
        all_metrics = set()
        for formula in ALPHA_EXPRESSIONS.values():
            all_metrics.update(get_required_metrics(formula))

        compatible = get_compatible_expressions(list(all_metrics))

        assert set(compatible) == set(ALPHA_EXPRESSIONS.keys())

    def test_returns_list(self):
        """Return type should be a list."""
        assert isinstance(get_compatible_expressions(["creation_entreprise"]), list)


class TestDescribeExpression:
    """Tests for describe_expression()."""

    def test_known_expression_has_core_keys(self):
        """A known expression returns name, formula, required_metrics, categories."""
        result = describe_expression("sante_entreprises")

        assert result["name"] == "sante_entreprises"
        assert result["formula"] == ALPHA_EXPRESSIONS["sante_entreprises"]
        assert result["required_metrics"] == [
            "liquidation_judiciaire",
            "creation_entreprise",
        ]
        assert "categories" in result
        assert "business_health" in result["categories"]

    def test_known_expression_merges_metadata(self):
        """Metadata fields are merged in when present."""
        result = describe_expression("sante_entreprises")

        # From EXPRESSION_METADATA["sante_entreprises"]
        assert "description" in result
        assert result["unit"] == "ratio"
        assert result["good_threshold"] == "< 0.5"

    def test_known_expression_without_metadata(self):
        """An expression without metadata still returns the core dict."""
        # rang_creation has no EXPRESSION_METADATA entry.
        assert "rang_creation" not in EXPRESSION_METADATA
        result = describe_expression("rang_creation")

        assert result["name"] == "rang_creation"
        assert result["required_metrics"] == ["creation_entreprise"]
        assert "ranking" in result["categories"]
        # No metadata keys were injected.
        assert "unit" not in result

    def test_unknown_expression_raises_value_error(self):
        """An unknown expression name raises ValueError (handled, documented)."""
        with pytest.raises(ValueError, match="Unknown expression"):
            describe_expression("does_not_exist")


class TestGetExpressionsByCategory:
    """Tests for get_expressions_by_category()."""

    def test_valid_category_returns_name_formula_tuples(self):
        """A valid category returns (name, formula) tuples for each member."""
        result = get_expressions_by_category("convergence")

        names = [name for name, _ in result]
        assert names == EXPRESSION_CATEGORIES["convergence"]
        for name, formula in result:
            assert formula == ALPHA_EXPRESSIONS[name]

    def test_invalid_category_raises_value_error(self):
        """An unknown category raises ValueError."""
        with pytest.raises(ValueError, match="Unknown category"):
            get_expressions_by_category("nonexistent_category")


class TestGetExpressionSet:
    """Tests for get_expression_set()."""

    def test_valid_set_returns_name_formula_tuples(self):
        """A valid set returns (name, formula) tuples matching the registry."""
        result = get_expression_set("basic")

        names = [name for name, _ in result]
        assert names == DEFAULT_EXPRESSION_SETS["basic"]
        for name, formula in result:
            assert formula == ALPHA_EXPRESSIONS[name]

    def test_invalid_set_raises_value_error(self):
        """An unknown set name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown expression set"):
            get_expression_set("not_a_set")

    def test_all_default_sets_are_resolvable(self):
        """Every predefined set should reference only known expressions."""
        for set_name in DEFAULT_EXPRESSION_SETS:
            result = get_expression_set(set_name)
            assert len(result) == len(DEFAULT_EXPRESSION_SETS[set_name])


class TestCreateCustomExpression:
    """Tests for create_custom_expression()."""

    def test_registers_formula(self, restore_module_state):
        """A custom expression is added to ALPHA_EXPRESSIONS."""
        create_custom_expression(
            "my_custom",
            "$creation_entreprise / ($offres_emploi + 1)",
        )

        assert "my_custom" in ALPHA_EXPRESSIONS
        assert (
            ALPHA_EXPRESSIONS["my_custom"]
            == "$creation_entreprise / ($offres_emploi + 1)"
        )

    def test_registered_expression_is_describable(self, restore_module_state):
        """After registration, the expression resolves through the API."""
        create_custom_expression(
            "my_custom",
            "$creation_entreprise / ($offres_emploi + 1)",
            description="A custom ratio",
            categories=["custom_cat"],
        )

        described = describe_expression("my_custom")
        assert described["name"] == "my_custom"
        assert described["required_metrics"] == [
            "creation_entreprise",
            "offres_emploi",
        ]
        assert described["description"] == "A custom ratio"
        assert "custom_cat" in described["categories"]

    def test_description_stored_in_metadata(self, restore_module_state):
        """A provided description is written to EXPRESSION_METADATA."""
        create_custom_expression(
            "metric_with_desc",
            "$creation_entreprise",
            description="Some description",
        )

        assert EXPRESSION_METADATA["metric_with_desc"]["description"] == (
            "Some description"
        )

    def test_new_category_created_and_populated(self, restore_module_state):
        """A new category is created and the expression appended to it."""
        create_custom_expression(
            "categorized_metric",
            "$offres_emploi",
            categories=["brand_new_category"],
        )

        assert "brand_new_category" in EXPRESSION_CATEGORIES
        assert "categorized_metric" in EXPRESSION_CATEGORIES["brand_new_category"]

    def test_validate_after_registration(self, restore_module_state):
        """A registered expression validates against its required metrics."""
        create_custom_expression(
            "validated_metric",
            "$creation_entreprise + $offres_emploi",
        )

        assert (
            validate_expression_metrics(
                "validated_metric",
                ["creation_entreprise", "offres_emploi"],
            )
            is True
        )
        assert (
            validate_expression_metrics("validated_metric", ["creation_entreprise"])
            is False
        )

    def test_no_description_no_metadata_entry(self, restore_module_state):
        """Without a description, no metadata entry is created."""
        create_custom_expression("bare_metric", "$creation_entreprise")

        assert "bare_metric" not in EXPRESSION_METADATA

    def test_no_duplicate_in_category_on_reregister(self, restore_module_state):
        """Re-registering with the same category does not duplicate the name."""
        create_custom_expression(
            "dedup_metric", "$creation_entreprise", categories=["dedup_cat"]
        )
        create_custom_expression(
            "dedup_metric", "$offres_emploi", categories=["dedup_cat"]
        )

        assert EXPRESSION_CATEGORIES["dedup_cat"].count("dedup_metric") == 1
        # Formula should reflect the latest registration.
        assert ALPHA_EXPRESSIONS["dedup_metric"] == "$offres_emploi"

    def test_returns_none(self, restore_module_state):
        """create_custom_expression returns None (side-effect only)."""
        assert (
            create_custom_expression("ret_metric", "$creation_entreprise") is None
        )
