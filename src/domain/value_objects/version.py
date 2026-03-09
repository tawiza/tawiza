"""Version value objects for semantic versioning."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SemanticVersion:
    """Semantic version following semver.org conventions.

    Format: MAJOR.MINOR.PATCH
    - MAJOR: Incompatible API changes
    - MINOR: Backwards-compatible functionality additions
    - PATCH: Backwards-compatible bug fixes
    """

    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        """Validate version numbers."""
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("Version numbers must be non-negative")

    @classmethod
    def from_string(cls, version_str: str) -> "SemanticVersion":
        """Parse semantic version from string.

        Args:
            version_str: Version string (e.g., "1.2.3", "v1.2.3")

        Returns:
            SemanticVersion instance

        Raises:
            ValueError: If version string is invalid
        """
        # Remove 'v' prefix if present
        version_str = version_str.lstrip("v")

        # Match semantic version pattern
        pattern = r"^(\d+)\.(\d+)\.(\d+)$"
        match = re.match(pattern, version_str)

        if not match:
            raise ValueError(
                f"Invalid semantic version: {version_str}. "
                "Expected format: MAJOR.MINOR.PATCH (e.g., 1.2.3)"
            )

        major, minor, patch = map(int, match.groups())
        return cls(major=major, minor=minor, patch=patch)

    def __str__(self) -> str:
        """Return version string."""
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: "SemanticVersion") -> bool:
        """Compare versions."""
        return (self.major, self.minor, self.patch) < (
            other.major,
            other.minor,
            other.patch,
        )

    def __le__(self, other: "SemanticVersion") -> bool:
        """Compare versions."""
        return (self.major, self.minor, self.patch) <= (
            other.major,
            other.minor,
            other.patch,
        )

    def __gt__(self, other: "SemanticVersion") -> bool:
        """Compare versions."""
        return (self.major, self.minor, self.patch) > (
            other.major,
            other.minor,
            other.patch,
        )

    def __ge__(self, other: "SemanticVersion") -> bool:
        """Compare versions."""
        return (self.major, self.minor, self.patch) >= (
            other.major,
            other.minor,
            other.patch,
        )

    def bump_major(self) -> "SemanticVersion":
        """Bump major version (resets minor and patch)."""
        return SemanticVersion(major=self.major + 1, minor=0, patch=0)

    def bump_minor(self) -> "SemanticVersion":
        """Bump minor version (resets patch)."""
        return SemanticVersion(major=self.major, minor=self.minor + 1, patch=0)

    def bump_patch(self) -> "SemanticVersion":
        """Bump patch version."""
        return SemanticVersion(major=self.major, minor=self.minor, patch=self.patch + 1)


@dataclass(frozen=True)
class AutoIncrementVersion:
    """Simple auto-incrementing version (v1, v2, v3, ...).

    This is simpler than semantic versioning and suitable for models
    where we just want sequential versioning without semantic meaning.
    """

    number: int

    def __post_init__(self) -> None:
        """Validate version number."""
        if self.number < 1:
            raise ValueError("Version number must be positive")

    @classmethod
    def from_string(cls, version_str: str) -> "AutoIncrementVersion":
        """Parse version from string.

        Args:
            version_str: Version string (e.g., "1", "v2", "42")

        Returns:
            AutoIncrementVersion instance

        Raises:
            ValueError: If version string is invalid
        """
        # Remove 'v' prefix if present
        version_str = version_str.lstrip("v")

        try:
            number = int(version_str)
            return cls(number=number)
        except ValueError:
            raise ValueError(
                f"Invalid auto-increment version: {version_str}. "
                "Expected format: N or vN (e.g., 1, v2)"
            )

    def __str__(self) -> str:
        """Return version string with 'v' prefix."""
        return f"v{self.number}"

    def __int__(self) -> int:
        """Return version number."""
        return self.number

    def __lt__(self, other: "AutoIncrementVersion") -> bool:
        """Compare versions."""
        return self.number < other.number

    def __le__(self, other: "AutoIncrementVersion") -> bool:
        """Compare versions."""
        return self.number <= other.number

    def __gt__(self, other: "AutoIncrementVersion") -> bool:
        """Compare versions."""
        return self.number > other.number

    def __ge__(self, other: "AutoIncrementVersion") -> bool:
        """Compare versions."""
        return self.number >= other.number

    def next(self) -> "AutoIncrementVersion":
        """Get next version."""
        return AutoIncrementVersion(number=self.number + 1)

    def previous(self) -> Optional["AutoIncrementVersion"]:
        """Get previous version (returns None if version is 1)."""
        if self.number <= 1:
            return None
        return AutoIncrementVersion(number=self.number - 1)
