"""Tests for version value objects.

This module tests the semantic and auto-increment version value objects:
- SemanticVersion: MAJOR.MINOR.PATCH parsing, validation, comparison, bumping
- AutoIncrementVersion: sequential vN versioning, comparison, next/previous
"""

import pytest

from src.domain.value_objects.version import (
    AutoIncrementVersion,
    SemanticVersion,
)


class TestSemanticVersionCreation:
    """Tests for SemanticVersion construction and invariants."""

    def test_creation_with_valid_values(self):
        """SemanticVersion should be created with valid non-negative numbers."""
        version = SemanticVersion(major=1, minor=2, patch=3)

        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3

    def test_creation_with_zeros(self):
        """SemanticVersion should accept all zeros (0.0.0)."""
        version = SemanticVersion(major=0, minor=0, patch=0)

        assert version.major == 0
        assert version.minor == 0
        assert version.patch == 0

    def test_creation_rejects_negative_major(self):
        """SemanticVersion should reject negative major."""
        with pytest.raises(ValueError, match="must be non-negative"):
            SemanticVersion(major=-1, minor=0, patch=0)

    def test_creation_rejects_negative_minor(self):
        """SemanticVersion should reject negative minor."""
        with pytest.raises(ValueError, match="must be non-negative"):
            SemanticVersion(major=0, minor=-1, patch=0)

    def test_creation_rejects_negative_patch(self):
        """SemanticVersion should reject negative patch."""
        with pytest.raises(ValueError, match="must be non-negative"):
            SemanticVersion(major=0, minor=0, patch=-1)

    def test_is_frozen(self):
        """SemanticVersion should be immutable (frozen dataclass)."""
        version = SemanticVersion(major=1, minor=0, patch=0)

        with pytest.raises(AttributeError):
            version.major = 2


class TestSemanticVersionFromString:
    """Tests for SemanticVersion.from_string parsing."""

    def test_from_string_basic(self):
        """from_string should parse a plain semver string."""
        version = SemanticVersion.from_string("1.2.3")

        assert version == SemanticVersion(major=1, minor=2, patch=3)

    def test_from_string_with_v_prefix(self):
        """from_string should strip a leading 'v' prefix."""
        version = SemanticVersion.from_string("v2.5.7")

        assert version == SemanticVersion(major=2, minor=5, patch=7)

    def test_from_string_with_multiple_v_prefix(self):
        """from_string strips all leading 'v' chars (lstrip behavior)."""
        version = SemanticVersion.from_string("vv1.0.0")

        assert version == SemanticVersion(major=1, minor=0, patch=0)

    def test_from_string_zeros(self):
        """from_string should parse 0.0.0."""
        version = SemanticVersion.from_string("0.0.0")

        assert version == SemanticVersion(major=0, minor=0, patch=0)

    def test_from_string_large_numbers(self):
        """from_string should parse multi-digit version components."""
        version = SemanticVersion.from_string("10.20.30")

        assert version == SemanticVersion(major=10, minor=20, patch=30)

    def test_from_string_roundtrip(self):
        """from_string(str(version)) should yield the same version."""
        version = SemanticVersion(major=3, minor=4, patch=5)

        assert SemanticVersion.from_string(str(version)) == version

    @pytest.mark.parametrize(
        "invalid",
        [
            "1.2",
            "1",
            "1.2.3.4",
            "a.b.c",
            "1.2.x",
            "",
            "1.2.3-rc1",
            "1..3",
            " 1.2.3",
            "1.2.3 ",
        ],
    )
    def test_from_string_invalid_raises(self, invalid):
        """from_string should reject malformed version strings."""
        with pytest.raises(ValueError, match="Invalid semantic version"):
            SemanticVersion.from_string(invalid)


class TestSemanticVersionString:
    """Tests for SemanticVersion __str__."""

    def test_str_format(self):
        """__str__ should render MAJOR.MINOR.PATCH without a 'v' prefix."""
        version = SemanticVersion(major=1, minor=2, patch=3)

        assert str(version) == "1.2.3"

    def test_str_zeros(self):
        """__str__ should render zeros correctly."""
        assert str(SemanticVersion(major=0, minor=0, patch=0)) == "0.0.0"


class TestSemanticVersionEquality:
    """Tests for SemanticVersion equality and hashing."""

    def test_equal_versions(self):
        """Versions with identical components should be equal."""
        v1 = SemanticVersion(major=1, minor=2, patch=3)
        v2 = SemanticVersion(major=1, minor=2, patch=3)

        assert v1 == v2

    def test_unequal_versions(self):
        """Versions with different components should not be equal."""
        v1 = SemanticVersion(major=1, minor=2, patch=3)
        v2 = SemanticVersion(major=1, minor=2, patch=4)

        assert v1 != v2

    def test_hashable(self):
        """Frozen versions should be hashable and usable in sets/dicts."""
        v1 = SemanticVersion(major=1, minor=0, patch=0)
        v2 = SemanticVersion(major=1, minor=0, patch=0)

        assert hash(v1) == hash(v2)
        assert len({v1, v2}) == 1


class TestSemanticVersionComparison:
    """Tests for SemanticVersion ordering operators."""

    def test_less_than_by_patch(self):
        """Patch difference should drive ordering."""
        assert SemanticVersion(1, 0, 0) < SemanticVersion(1, 0, 1)

    def test_less_than_by_minor(self):
        """Minor difference should outrank patch in ordering."""
        assert SemanticVersion(1, 0, 9) < SemanticVersion(1, 1, 0)

    def test_less_than_by_major(self):
        """Major difference should outrank minor and patch."""
        assert SemanticVersion(1, 9, 9) < SemanticVersion(2, 0, 0)

    def test_greater_than(self):
        """__gt__ should reflect descending order."""
        assert SemanticVersion(2, 0, 0) > SemanticVersion(1, 9, 9)

    def test_less_equal_when_equal(self):
        """__le__ should be True for equal versions."""
        assert SemanticVersion(1, 2, 3) <= SemanticVersion(1, 2, 3)

    def test_less_equal_when_less(self):
        """__le__ should be True when strictly less."""
        assert SemanticVersion(1, 2, 2) <= SemanticVersion(1, 2, 3)

    def test_greater_equal_when_equal(self):
        """__ge__ should be True for equal versions."""
        assert SemanticVersion(1, 2, 3) >= SemanticVersion(1, 2, 3)

    def test_greater_equal_when_greater(self):
        """__ge__ should be True when strictly greater."""
        assert SemanticVersion(1, 2, 4) >= SemanticVersion(1, 2, 3)

    def test_sorting(self):
        """A list of versions should sort in semantic order."""
        versions = [
            SemanticVersion(2, 0, 0),
            SemanticVersion(1, 0, 0),
            SemanticVersion(1, 2, 0),
            SemanticVersion(1, 0, 5),
        ]

        ordered = sorted(versions)

        assert ordered == [
            SemanticVersion(1, 0, 0),
            SemanticVersion(1, 0, 5),
            SemanticVersion(1, 2, 0),
            SemanticVersion(2, 0, 0),
        ]


class TestSemanticVersionBumping:
    """Tests for SemanticVersion bump_* state transitions."""

    def test_bump_major_resets_minor_and_patch(self):
        """bump_major should increment major and reset minor/patch to 0."""
        version = SemanticVersion(major=1, minor=4, patch=7)

        bumped = version.bump_major()

        assert bumped == SemanticVersion(major=2, minor=0, patch=0)

    def test_bump_minor_resets_patch(self):
        """bump_minor should increment minor, keep major, reset patch."""
        version = SemanticVersion(major=1, minor=4, patch=7)

        bumped = version.bump_minor()

        assert bumped == SemanticVersion(major=1, minor=5, patch=0)

    def test_bump_patch_keeps_major_minor(self):
        """bump_patch should increment patch and keep major/minor."""
        version = SemanticVersion(major=1, minor=4, patch=7)

        bumped = version.bump_patch()

        assert bumped == SemanticVersion(major=1, minor=4, patch=8)

    def test_bump_does_not_mutate_original(self):
        """Bumping should return a new instance, not mutate the original."""
        version = SemanticVersion(major=1, minor=0, patch=0)

        version.bump_major()
        version.bump_minor()
        version.bump_patch()

        assert version == SemanticVersion(major=1, minor=0, patch=0)

    def test_bump_chain_is_increasing(self):
        """Each bump should yield a strictly greater version."""
        version = SemanticVersion(major=1, minor=2, patch=3)

        assert version.bump_patch() > version
        assert version.bump_minor() > version
        assert version.bump_major() > version


class TestAutoIncrementVersionCreation:
    """Tests for AutoIncrementVersion construction and invariants."""

    def test_creation_with_valid_number(self):
        """AutoIncrementVersion should accept a positive number."""
        version = AutoIncrementVersion(number=1)

        assert version.number == 1

    def test_creation_with_large_number(self):
        """AutoIncrementVersion should accept large numbers."""
        version = AutoIncrementVersion(number=999)

        assert version.number == 999

    def test_creation_rejects_zero(self):
        """AutoIncrementVersion should reject zero (must be positive)."""
        with pytest.raises(ValueError, match="must be positive"):
            AutoIncrementVersion(number=0)

    def test_creation_rejects_negative(self):
        """AutoIncrementVersion should reject negative numbers."""
        with pytest.raises(ValueError, match="must be positive"):
            AutoIncrementVersion(number=-5)

    def test_is_frozen(self):
        """AutoIncrementVersion should be immutable (frozen dataclass)."""
        version = AutoIncrementVersion(number=1)

        with pytest.raises(AttributeError):
            version.number = 2


class TestAutoIncrementVersionFromString:
    """Tests for AutoIncrementVersion.from_string parsing."""

    def test_from_string_plain_number(self):
        """from_string should parse a bare integer string."""
        version = AutoIncrementVersion.from_string("3")

        assert version == AutoIncrementVersion(number=3)

    def test_from_string_with_v_prefix(self):
        """from_string should strip a leading 'v' prefix."""
        version = AutoIncrementVersion.from_string("v42")

        assert version == AutoIncrementVersion(number=42)

    def test_from_string_roundtrip(self):
        """from_string(str(version)) should yield the same version."""
        version = AutoIncrementVersion(number=7)

        assert AutoIncrementVersion.from_string(str(version)) == version

    @pytest.mark.parametrize(
        "invalid",
        [
            "abc",
            "",
            "v",
            "1.2",
            "1a",
            "v1.0",
        ],
    )
    def test_from_string_invalid_raises(self, invalid):
        """from_string should reject non-integer strings."""
        with pytest.raises(ValueError, match="Invalid auto-increment version"):
            AutoIncrementVersion.from_string(invalid)

    def test_from_string_zero_raises(self):
        """from_string('0') parses to 0; the invariant ValueError is caught and
        re-raised as an 'Invalid auto-increment version' error."""
        with pytest.raises(ValueError, match="Invalid auto-increment version"):
            AutoIncrementVersion.from_string("0")

    def test_from_string_negative_raises(self):
        """from_string('-1') parses to -1; the invariant ValueError is caught and
        re-raised as an 'Invalid auto-increment version' error."""
        with pytest.raises(ValueError, match="Invalid auto-increment version"):
            AutoIncrementVersion.from_string("-1")


class TestAutoIncrementVersionConversions:
    """Tests for AutoIncrementVersion __str__ and __int__."""

    def test_str_has_v_prefix(self):
        """__str__ should render with a 'v' prefix."""
        assert str(AutoIncrementVersion(number=5)) == "v5"

    def test_int_conversion(self):
        """__int__ should return the underlying number."""
        assert int(AutoIncrementVersion(number=8)) == 8


class TestAutoIncrementVersionEquality:
    """Tests for AutoIncrementVersion equality and hashing."""

    def test_equal_versions(self):
        """Versions with the same number should be equal."""
        assert AutoIncrementVersion(number=4) == AutoIncrementVersion(number=4)

    def test_unequal_versions(self):
        """Versions with different numbers should not be equal."""
        assert AutoIncrementVersion(number=4) != AutoIncrementVersion(number=5)

    def test_hashable(self):
        """Frozen versions should be hashable and deduplicate in a set."""
        v1 = AutoIncrementVersion(number=2)
        v2 = AutoIncrementVersion(number=2)

        assert hash(v1) == hash(v2)
        assert len({v1, v2}) == 1


class TestAutoIncrementVersionComparison:
    """Tests for AutoIncrementVersion ordering operators."""

    def test_less_than(self):
        """__lt__ should compare by number."""
        assert AutoIncrementVersion(number=1) < AutoIncrementVersion(number=2)

    def test_greater_than(self):
        """__gt__ should compare by number."""
        assert AutoIncrementVersion(number=3) > AutoIncrementVersion(number=2)

    def test_less_equal_when_equal(self):
        """__le__ should be True for equal numbers."""
        assert AutoIncrementVersion(number=2) <= AutoIncrementVersion(number=2)

    def test_less_equal_when_less(self):
        """__le__ should be True when strictly less."""
        assert AutoIncrementVersion(number=1) <= AutoIncrementVersion(number=2)

    def test_greater_equal_when_equal(self):
        """__ge__ should be True for equal numbers."""
        assert AutoIncrementVersion(number=2) >= AutoIncrementVersion(number=2)

    def test_greater_equal_when_greater(self):
        """__ge__ should be True when strictly greater."""
        assert AutoIncrementVersion(number=3) >= AutoIncrementVersion(number=2)

    def test_sorting(self):
        """A list of versions should sort by number ascending."""
        versions = [
            AutoIncrementVersion(number=3),
            AutoIncrementVersion(number=1),
            AutoIncrementVersion(number=2),
        ]

        ordered = sorted(versions)

        assert ordered == [
            AutoIncrementVersion(number=1),
            AutoIncrementVersion(number=2),
            AutoIncrementVersion(number=3),
        ]


class TestAutoIncrementVersionTransitions:
    """Tests for AutoIncrementVersion next/previous transitions."""

    def test_next_increments(self):
        """next() should return the version with number + 1."""
        version = AutoIncrementVersion(number=4)

        assert version.next() == AutoIncrementVersion(number=5)

    def test_next_does_not_mutate(self):
        """next() should not mutate the original version."""
        version = AutoIncrementVersion(number=4)

        version.next()

        assert version == AutoIncrementVersion(number=4)

    def test_previous_decrements(self):
        """previous() should return the version with number - 1."""
        version = AutoIncrementVersion(number=4)

        assert version.previous() == AutoIncrementVersion(number=3)

    def test_previous_at_one_returns_none(self):
        """previous() should return None at the boundary (version 1)."""
        version = AutoIncrementVersion(number=1)

        assert version.previous() is None

    def test_next_then_previous_roundtrip(self):
        """previous() of next() should return the original version."""
        version = AutoIncrementVersion(number=10)

        assert version.next().previous() == version

    def test_next_is_greater(self):
        """next() should be strictly greater than the original."""
        version = AutoIncrementVersion(number=5)

        assert version.next() > version
