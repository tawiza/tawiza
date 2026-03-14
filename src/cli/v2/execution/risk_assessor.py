"""Risk assessor - categorizes operations by risk level."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RiskLevel(Enum):
    """Risk levels for operations."""

    SAFE = "safe"  # Auto-execute, no approval needed
    MODERATE = "moderate"  # Notify user, continue unless stopped
    HIGH = "high"  # Require explicit approval


@dataclass
class RiskAssessment:
    """Result of risk assessment."""

    level: RiskLevel
    reason: str
    requires_approval: bool


class RiskAssessor:
    """Assesses risk level of tool operations."""

    # Tools categorized by risk level
    SAFE_TOOLS: set[str] = {
        "files.read",
        "files.list",
        "files.exists",
        "files.stat",
        "browser.navigate",
        "browser.screenshot",
        "browser.extract",
        "analyst.query",
        "analyst.describe",
        "api.get",  # GET requests only
        "search.web",
        "search.code",
        "time.now",
        "finish",
    }

    MODERATE_TOOLS: set[str] = {
        "files.write",
        "files.copy",
        "files.move",
        "browser.click",
        "browser.type",
        "browser.scroll",
        "api.request",
        "api.post",
        "analyst.transform",
        "coder.generate",
    }

    HIGH_TOOLS: set[str] = {
        "files.delete",
        "files.rmdir",
        "system.execute",
        "system.shell",
        "git.push",
        "git.commit",
        "api.delete",
        "browser.submit",
    }

    def assess(self, tool_name: str, params: dict[str, Any] = None) -> RiskLevel:
        """Assess the risk level of a tool operation.

        Args:
            tool_name: Name of the tool being called
            params: Parameters for the tool call

        Returns:
            RiskLevel indicating how risky the operation is
        """
        params = params or {}

        # Check for dangerous patterns FIRST (highest priority)
        if self._has_dangerous_patterns(params):
            return RiskLevel.HIGH

        # Then check explicit categorization
        if tool_name in self.SAFE_TOOLS:
            return RiskLevel.SAFE

        if tool_name in self.HIGH_TOOLS:
            return RiskLevel.HIGH

        if tool_name in self.MODERATE_TOOLS:
            return RiskLevel.MODERATE

        # Default to moderate for unknown tools
        return RiskLevel.MODERATE

    def _has_dangerous_patterns(self, params: dict[str, Any]) -> bool:
        """Check if params contain dangerous patterns."""
        dangerous_patterns = [
            "rm -rf",
            "sudo",
            "chmod 777",
            "> /dev/",
            "DROP TABLE",
            "DELETE FROM",
            "--force",
        ]

        params_str = str(params).lower()
        return any(pattern.lower() in params_str for pattern in dangerous_patterns)

    def get_assessment(self, tool_name: str, params: dict[str, Any] = None) -> RiskAssessment:
        """Get detailed risk assessment.

        Args:
            tool_name: Name of the tool being called
            params: Parameters for the tool call

        Returns:
            RiskAssessment with level, reason, and approval requirement
        """
        level = self.assess(tool_name, params)

        reasons = {
            RiskLevel.SAFE: "Read-only operation",
            RiskLevel.MODERATE: "May modify data or make external requests",
            RiskLevel.HIGH: "Potentially destructive or irreversible operation",
        }

        return RiskAssessment(
            level=level,
            reason=reasons[level],
            requires_approval=level == RiskLevel.HIGH,
        )
