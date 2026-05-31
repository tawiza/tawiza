"""Tests for population data and normalization utilities.

This module tests the department-level population helpers used for
territorial normalization (issue #161, coverage):
- get_department_population: lookup of known/unknown department codes
- normalize_per_10k: per-10,000-inhabitants normalization
- get_all_departments: listing of available department codes
- get_total_population: aggregate population across all departments
"""

from src.collector.quant.population import (
    DEPARTMENT_POPULATIONS,
    get_all_departments,
    get_department_population,
    get_total_population,
    normalize_per_10k,
)


class TestGetDepartmentPopulation:
    """Tests for get_department_population."""

    def test_known_department_nord(self):
        """Should return the exact table value for Nord (59)."""
        assert get_department_population("59") == 2604361
        assert get_department_population("59") == DEPARTMENT_POPULATIONS["59"]

    def test_known_department_paris(self):
        """Should return the exact table value for Paris (75)."""
        assert get_department_population("75") == 2161063
        assert get_department_population("75") == DEPARTMENT_POPULATIONS["75"]

    def test_known_department_corse_du_sud(self):
        """Should return the exact table value for Corse-du-Sud (2A)."""
        assert get_department_population("2A") == 162849
        assert get_department_population("2A") == DEPARTMENT_POPULATIONS["2A"]

    def test_known_department_haute_corse(self):
        """Should return the exact table value for Haute-Corse (2B)."""
        assert get_department_population("2B") == 181933
        assert get_department_population("2B") == DEPARTMENT_POPULATIONS["2B"]

    def test_unknown_department_returns_none(self):
        """Should return None for a department code absent from the table."""
        assert get_department_population("999") is None

    def test_none_code_returns_none(self):
        """Should return None when the code is None (not in the table)."""
        assert get_department_population(None) is None

    def test_empty_string_returns_none(self):
        """Should return None for an empty department code."""
        assert get_department_population("") is None


class TestNormalizePer10k:
    """Tests for normalize_per_10k."""

    def test_normalization_matches_formula(self):
        """Should compute value * 10_000 / population for a known department."""
        population = DEPARTMENT_POPULATIONS["75"]
        expected = (1000 * 10_000) / population

        result = normalize_per_10k(1000, "75")

        assert result == expected

    def test_normalization_nord(self):
        """Should normalize correctly for Nord (59)."""
        expected = (2604.361 * 10_000) / DEPARTMENT_POPULATIONS["59"]

        assert normalize_per_10k(2604.361, "59") == expected

    def test_zero_value_returns_zero(self):
        """A value of 0 should normalize to 0.0 (not None)."""
        result = normalize_per_10k(0, "75")

        assert result == 0.0

    def test_unknown_department_returns_none(self):
        """Should return None when the department population is unknown."""
        assert normalize_per_10k(1000, "999") is None

    def test_none_department_returns_none(self):
        """Should return None when the department code is None."""
        assert normalize_per_10k(1000, None) is None


class TestGetAllDepartments:
    """Tests for get_all_departments."""

    def test_length_matches_table(self):
        """Should return one entry per department in the table."""
        departments = get_all_departments()

        assert len(departments) == len(DEPARTMENT_POPULATIONS)

    def test_returns_list(self):
        """Should return a list of department codes."""
        departments = get_all_departments()

        assert isinstance(departments, list)

    def test_contains_corsica_codes(self):
        """Should include the Corsican department codes 2A and 2B."""
        departments = get_all_departments()

        assert "2A" in departments
        assert "2B" in departments

    def test_contains_known_metropolitan_codes(self):
        """Should include common metropolitan department codes."""
        departments = get_all_departments()

        assert "59" in departments
        assert "75" in departments

    def test_keys_match_table(self):
        """Returned codes should match the table keys exactly."""
        assert set(get_all_departments()) == set(DEPARTMENT_POPULATIONS.keys())


class TestGetTotalPopulation:
    """Tests for get_total_population."""

    def test_total_equals_sum_of_table(self):
        """Total should equal the sum of all table values."""
        assert get_total_population() == sum(DEPARTMENT_POPULATIONS.values())

    def test_total_is_positive_int(self):
        """Total population should be a positive integer."""
        total = get_total_population()

        assert isinstance(total, int)
        assert total > 0
