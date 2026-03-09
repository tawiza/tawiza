"""
TrustManager - Adaptive autonomy management for TAJINEAgent.

Tracks performance metrics and adjusts autonomy level based on:
- Success/failure rates
- User feedback
- Tool-specific performance
- Time-weighted historical data

Supports persistence to:
- JSON files (lightweight, human-readable)
- SQLite database (structured, queryable)
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class AutonomyLevel(Enum):
    """Autonomy levels for TAJINEAgent.

    Higher levels give the agent more independence in decision-making.
    """
    SUPERVISED = 0       # Human approval for all actions
    ASSISTED = 1         # Human approval for risky actions
    SEMI_AUTONOMOUS = 2  # Human approval for new patterns
    AUTONOMOUS = 3       # Notify on completion
    FULL_AUTONOMOUS = 4  # Full independence


class FailureType(Enum):
    """Classification of failure types for trust impact.

    External failures (not agent's fault) should not penalize trust.
    Internal failures (agent could have prevented) should penalize trust.
    """
    # External failures - NO trust penalty
    TIMEOUT = "timeout"                    # Network/API timeout
    API_UNAVAILABLE = "api_unavailable"    # API is down
    RATE_LIMITED = "rate_limited"          # Rate limit hit
    CAPTCHA = "captcha"                    # CAPTCHA encountered
    NETWORK_ERROR = "network_error"        # Connection issues
    SERVER_ERROR = "server_error"          # 5xx errors from APIs

    # Internal failures - PENALIZE trust
    BAD_LLM_RESPONSE = "bad_llm_response"  # LLM gave unusable output
    TOOL_MISUSE = "tool_misuse"            # Wrong tool or parameters
    PARSING_ERROR = "parsing_error"        # Failed to parse response
    LOGIC_ERROR = "logic_error"            # Agent made wrong decision
    VALIDATION_ERROR = "validation_error"  # Output validation failed


# Failures that should NOT penalize trust (external factors)
EXTERNAL_FAILURES = {
    FailureType.TIMEOUT,
    FailureType.API_UNAVAILABLE,
    FailureType.RATE_LIMITED,
    FailureType.CAPTCHA,
    FailureType.NETWORK_ERROR,
    FailureType.SERVER_ERROR,
}

# Failures that SHOULD penalize trust (agent could improve)
INTERNAL_FAILURES = {
    FailureType.BAD_LLM_RESPONSE,
    FailureType.TOOL_MISUSE,
    FailureType.PARSING_ERROR,
    FailureType.LOGIC_ERROR,
    FailureType.VALIDATION_ERROR,
}


def classify_failure(error: str | Exception) -> FailureType:
    """
    Automatically classify a failure based on error message patterns.

    Args:
        error: Error message string or Exception object

    Returns:
        FailureType classification
    """
    error_str = str(error).lower()

    # External: Timeouts
    if any(kw in error_str for kw in ["timeout", "timed out", "deadline exceeded"]):
        return FailureType.TIMEOUT

    # External: API/Network issues
    if any(kw in error_str for kw in [
        "connection refused", "connection reset", "connection error",
        "network unreachable", "dns", "socket", "ssl", "certificate"
    ]):
        return FailureType.NETWORK_ERROR

    # External: Server errors (5xx)
    if any(kw in error_str for kw in [
        "500", "502", "503", "504", "internal server error",
        "bad gateway", "service unavailable", "gateway timeout"
    ]):
        return FailureType.SERVER_ERROR

    # External: Rate limiting
    if any(kw in error_str for kw in [
        "rate limit", "too many requests", "429", "quota exceeded",
        "throttled", "slow down"
    ]):
        return FailureType.RATE_LIMITED

    # External: CAPTCHA (check before API unavailable)
    if any(kw in error_str for kw in ["captcha", "recaptcha", "challenge"]):
        return FailureType.CAPTCHA

    # External: API unavailable
    if any(kw in error_str for kw in [
        "api unavailable", "service down", "maintenance",
        "endpoint not found"
    ]):
        return FailureType.API_UNAVAILABLE

    # Also check for 404 specifically (but not general "not found" which could be data)
    if "404" in error_str and "not found" in error_str:
        return FailureType.API_UNAVAILABLE

    # Internal: Parsing errors (check before validation)
    if any(kw in error_str for kw in [
        "json", "parse", "decode", "syntax", "unexpected token",
        "invalid format", "malformed"
    ]):
        return FailureType.PARSING_ERROR

    # Internal: Validation errors
    if any(kw in error_str for kw in [
        "validation error", "required field", "type error",
        "pydantic", "schema error"
    ]):
        return FailureType.VALIDATION_ERROR

    # Internal: Tool misuse
    if any(kw in error_str for kw in [
        "tool", "function", "parameter", "argument", "missing required"
    ]):
        return FailureType.TOOL_MISUSE

    # Internal: Bad LLM response (catch-all for LLM issues)
    if any(kw in error_str for kw in [
        "llm", "model", "response", "generation", "completion",
        "empty response", "no response"
    ]):
        return FailureType.BAD_LLM_RESPONSE

    # Default: Assume internal logic error (conservative - penalizes trust)
    return FailureType.LOGIC_ERROR


@dataclass
class TrustRecord:
    """Record of a trust-affecting event."""
    timestamp: datetime
    event_type: str  # 'success', 'failure', 'feedback', 'tool_success', 'tool_failure'
    value: float
    details: str = ""
    tool: str | None = None


@dataclass
class ToolTrust:
    """Trust tracking for a specific tool."""
    name: str
    trust_score: float = 0.5
    success_count: int = 0
    failure_count: int = 0

    def record_outcome(self, success: bool) -> None:
        """Record a tool execution outcome."""
        if success:
            self.success_count += 1
            self.trust_score = min(1.0, self.trust_score + 0.03)
        else:
            self.failure_count += 1
            # 1:1 ratio for sustainable trust recovery
            self.trust_score = max(0.0, self.trust_score - 0.03)


class TrustManager:
    """
    Manages trust score and autonomy level.

    Trust score is computed from:
    - Success rate (40%)
    - User feedback (35%)
    - Historical performance (25%)

    Features:
    - Time-decay: Older records have less influence
    - Tool-specific tracking: Each tool has independent trust
    - State persistence: Export/import trust state
    """

    # Autonomy thresholds
    THRESHOLDS = {
        'full_autonomous': 0.9,
        'autonomous': 0.75,
        'semi_autonomous': 0.5,
        'assisted': 0.25,
    }

    # Score deltas - balanced for sustainable trust recovery
    # Old: failure=-0.03 was 1.5:1 ratio (hard to recover from failure streak)
    # New: 1:1 ratio allows realistic recovery with equal success/failure rates
    # Positive feedback has 2x impact to encourage user engagement
    DELTAS = {
        'success': 0.025,           # +0.025 per success
        'failure': -0.025,          # -0.025 per failure (1:1 ratio)
        'positive_feedback': 0.05,  # +0.05 - user feedback is highly valuable
        'negative_feedback': -0.03, # -0.03 - less punitive than auto-failure
    }

    def __init__(self, initial_score: float = 0.5):
        """
        Initialize TrustManager.

        Args:
            initial_score: Starting trust score (0.0 to 1.0)
        """
        self.trust_score = max(0.0, min(1.0, initial_score))
        self.autonomy_level = AutonomyLevel.ASSISTED
        self.records: list[TrustRecord] = []
        self.success_count = 0
        self.failure_count = 0
        self._tool_trust: dict[str, ToolTrust] = {}

        # Set initial autonomy level based on score
        self._update_autonomy_level()

        logger.info(f"TrustManager initialized with score {initial_score}")

    def get_trust_score(self) -> float:
        """Get current trust score (0.0 to 1.0)."""
        return self.trust_score

    def get_autonomy_level(self) -> AutonomyLevel:
        """Get current autonomy level."""
        return self.autonomy_level

    def record_success(self) -> None:
        """Record a successful task completion."""
        self.success_count += 1
        self._update_score(self.DELTAS['success'])
        self.records.append(TrustRecord(
            timestamp=datetime.now(),
            event_type='success',
            value=self.DELTAS['success']
        ))
        self._update_autonomy_level()
        logger.debug(f"Recorded success, trust: {self.trust_score:.2f}")

    def record_failure(self, failure_type: FailureType | None = None) -> None:
        """
        Record a task failure.

        Args:
            failure_type: Optional classification of the failure.
                          If None, assumes internal failure (penalizes trust).
        """
        # If failure type provided, use intelligent handling
        if failure_type is not None:
            self.record_failure_with_type(failure_type)
            return

        # Legacy behavior: assume internal failure
        self.failure_count += 1
        self._update_score(self.DELTAS['failure'])
        self.records.append(TrustRecord(
            timestamp=datetime.now(),
            event_type='failure',
            value=self.DELTAS['failure']
        ))
        self._update_autonomy_level()
        logger.debug(f"Recorded failure, trust: {self.trust_score:.2f}")

    def record_failure_with_type(
        self,
        failure_type: FailureType,
        error_message: str = ""
    ) -> None:
        """
        Record a failure with intelligent trust impact based on failure type.

        External failures (timeout, API down, captcha) do NOT penalize trust.
        Internal failures (bad LLM response, tool misuse) DO penalize trust.

        Args:
            failure_type: Classification of the failure
            error_message: Optional error message for logging
        """
        is_external = failure_type in EXTERNAL_FAILURES

        if is_external:
            # External failure - log but don't penalize
            logger.info(
                f"🔄 External failure ignored for trust: {failure_type.value} "
                f"({error_message[:50] if error_message else 'no details'})"
            )
            self.records.append(TrustRecord(
                timestamp=datetime.now(),
                event_type='external_failure',
                value=0.0,  # No trust impact
                details=f"{failure_type.value}: {error_message[:100]}"
            ))
            # Don't update failure_count or trust score
        else:
            # Internal failure - penalize trust
            self.failure_count += 1
            self._update_score(self.DELTAS['failure'])
            self.records.append(TrustRecord(
                timestamp=datetime.now(),
                event_type='failure',
                value=self.DELTAS['failure'],
                details=f"{failure_type.value}: {error_message[:100]}"
            ))
            self._update_autonomy_level()
            logger.debug(
                f"Recorded internal failure ({failure_type.value}), "
                f"trust: {self.trust_score:.2f}"
            )

    def record_feedback(self, feedback: str) -> None:
        """
        Record user feedback.

        Args:
            feedback: Feedback string ('positive', 'good', 'excellent',
                     'negative', 'bad', 'poor', or other for neutral)
        """
        feedback_lower = feedback.lower()

        if feedback_lower in ['positive', 'good', 'excellent']:
            delta = self.DELTAS['positive_feedback']
        elif feedback_lower in ['negative', 'bad', 'poor']:
            delta = self.DELTAS['negative_feedback']
        else:
            delta = 0.0

        self._update_score(delta)
        self.records.append(TrustRecord(
            timestamp=datetime.now(),
            event_type='feedback',
            value=delta,
            details=feedback
        ))
        self._update_autonomy_level()
        logger.debug(f"Recorded feedback '{feedback}', trust: {self.trust_score:.2f}")

    def record_tool_outcome(
        self,
        tool_name: str,
        success: bool,
        failure_type: FailureType | None = None,
        error_message: str = ""
    ) -> None:
        """
        Record outcome for a specific tool.

        Args:
            tool_name: Name of the tool
            success: Whether execution was successful
            failure_type: Optional failure classification (for failures)
            error_message: Optional error message (for auto-classification)
        """
        if tool_name not in self._tool_trust:
            self._tool_trust[tool_name] = ToolTrust(name=tool_name)

        if success:
            # Success - always record
            self._tool_trust[tool_name].record_outcome(True)
            delta = 0.01
            event_type = 'tool_success'

            self._update_score(delta)
            self.records.append(TrustRecord(
                timestamp=datetime.now(),
                event_type=event_type,
                value=delta,
                tool=tool_name
            ))
            logger.debug(f"Recorded tool success: {tool_name}")
        else:
            # Failure - classify and decide impact
            if failure_type is None and error_message:
                failure_type = classify_failure(error_message)
            elif failure_type is None:
                failure_type = FailureType.LOGIC_ERROR  # Default

            is_external = failure_type in EXTERNAL_FAILURES

            if is_external:
                # External failure - log but don't penalize tool trust
                logger.info(
                    f"🔄 Tool {tool_name} external failure ignored: "
                    f"{failure_type.value}"
                )
                self.records.append(TrustRecord(
                    timestamp=datetime.now(),
                    event_type='tool_external_failure',
                    value=0.0,
                    tool=tool_name,
                    details=f"{failure_type.value}: {error_message[:100]}"
                ))
                # Don't penalize tool trust for external failures
            else:
                # Internal failure - penalize
                self._tool_trust[tool_name].record_outcome(False)
                delta = -0.015
                self._update_score(delta)

                self.records.append(TrustRecord(
                    timestamp=datetime.now(),
                    event_type='tool_failure',
                    value=delta,
                    tool=tool_name,
                    details=f"{failure_type.value}: {error_message[:100]}"
                ))
                logger.debug(
                    f"Recorded tool failure: {tool_name} ({failure_type.value})"
                )

    def get_tool_trust(self, tool_name: str) -> float:
        """
        Get trust score for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool trust score (0.0 to 1.0), default 0.5 for unknown tools
        """
        if tool_name in self._tool_trust:
            return self._tool_trust[tool_name].trust_score
        return 0.5  # Default trust

    def get_success_rate(self) -> float:
        """
        Calculate overall success rate.

        Returns:
            Success rate as a float (0.0 to 1.0)
        """
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    def get_metrics(self) -> dict[str, Any]:
        """
        Get comprehensive metrics summary.

        Returns:
            Dict with trust score, autonomy level, counts, and rates
        """
        return {
            'trust_score': self.trust_score,
            'autonomy_level': self.autonomy_level.name,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': self.get_success_rate(),
            'total_records': len(self.records),
            'tool_count': len(self._tool_trust),
        }

    def get_effective_trust(self, decay_days: int = 7) -> float:
        """
        Calculate time-weighted effective trust score.

        More recent events have higher weight.

        Args:
            decay_days: Half-life for decay in days

        Returns:
            Effective trust score (0.0 to 1.0)
        """
        if not self.records:
            return self.trust_score

        now = datetime.now()
        weighted_sum = 0.0
        weight_total = 0.0

        for record in self.records:
            age = (now - record.timestamp).total_seconds() / 86400  # days
            weight = 0.5 ** (age / decay_days)  # Exponential decay
            weighted_sum += record.value * weight
            weight_total += weight

        if weight_total == 0:
            return self.trust_score

        # Apply decay adjustment to base score
        decay_adjustment = weighted_sum / weight_total if weight_total > 0 else 0
        effective = max(0.0, min(1.0, 0.5 + decay_adjustment * 10))

        return effective

    def _update_score(self, delta: float) -> None:
        """Update trust score with bounds checking."""
        self.trust_score = max(0.0, min(1.0, self.trust_score + delta))
        # Auto-save if enabled
        self._auto_save()

    def _update_autonomy_level(self) -> None:
        """Update autonomy level based on trust score."""
        if self.trust_score >= self.THRESHOLDS['full_autonomous']:
            self.autonomy_level = AutonomyLevel.FULL_AUTONOMOUS
        elif self.trust_score >= self.THRESHOLDS['autonomous']:
            self.autonomy_level = AutonomyLevel.AUTONOMOUS
        elif self.trust_score >= self.THRESHOLDS['semi_autonomous']:
            self.autonomy_level = AutonomyLevel.SEMI_AUTONOMOUS
        elif self.trust_score >= self.THRESHOLDS['assisted']:
            self.autonomy_level = AutonomyLevel.ASSISTED
        else:
            self.autonomy_level = AutonomyLevel.SUPERVISED

    def export_state(self) -> dict[str, Any]:
        """
        Export trust state for persistence.

        Returns:
            Dict containing all trust state
        """
        return {
            'trust_score': self.trust_score,
            'autonomy_level': self.autonomy_level.name,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'tool_trust': {
                name: {
                    'trust_score': tt.trust_score,
                    'success_count': tt.success_count,
                    'failure_count': tt.failure_count,
                }
                for name, tt in self._tool_trust.items()
            },
            'records': [
                {
                    'timestamp': r.timestamp.isoformat(),
                    'event_type': r.event_type,
                    'value': r.value,
                    'details': r.details,
                    'tool': r.tool,
                }
                for r in self.records[-100:]  # Keep last 100 records
            ]
        }

    def import_state(self, state: dict[str, Any]) -> None:
        """
        Import trust state from persistence.

        Args:
            state: Dict containing trust state
        """
        self.trust_score = state.get('trust_score', 0.5)
        self.success_count = state.get('success_count', 0)
        self.failure_count = state.get('failure_count', 0)

        # Restore autonomy level
        level_name = state.get('autonomy_level', 'ASSISTED')
        try:
            self.autonomy_level = AutonomyLevel[level_name]
        except KeyError:
            self.autonomy_level = AutonomyLevel.ASSISTED

        # Restore tool trust
        self._tool_trust = {}
        for name, data in state.get('tool_trust', {}).items():
            self._tool_trust[name] = ToolTrust(
                name=name,
                trust_score=data.get('trust_score', 0.5),
                success_count=data.get('success_count', 0),
                failure_count=data.get('failure_count', 0),
            )

        # Restore records
        self.records = []
        for r in state.get('records', []):
            try:
                self.records.append(TrustRecord(
                    timestamp=datetime.fromisoformat(r['timestamp']),
                    event_type=r['event_type'],
                    value=r['value'],
                    details=r.get('details', ''),
                    tool=r.get('tool'),
                ))
            except (KeyError, ValueError):
                continue  # Skip malformed records

        logger.info(f"Imported trust state: score={self.trust_score:.2f}, level={self.autonomy_level.name}")

    # =========================================================================
    # File Persistence (JSON)
    # =========================================================================

    def save_to_file(self, file_path: str | Path) -> bool:
        """
        Save trust state to JSON file.

        Args:
            file_path: Path to save file

        Returns:
            True if save successful
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            state = self.export_state()
            state['saved_at'] = datetime.now().isoformat()

            with open(path, 'w') as f:
                json.dump(state, f, indent=2)

            logger.info(f"💾 Trust state saved to {path}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to save trust state: {e}")
            return False

    @classmethod
    def load_from_file(cls, file_path: str | Path) -> Optional['TrustManager']:
        """
        Load TrustManager from JSON file.

        Args:
            file_path: Path to load from

        Returns:
            TrustManager instance or None if load fails
        """
        try:
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"Trust file not found: {path}")
                return None

            with open(path) as f:
                state = json.load(f)

            manager = cls(initial_score=state.get('trust_score', 0.5))
            manager.import_state(state)

            logger.info(f"📂 Loaded trust state from {path}")
            return manager

        except Exception as e:
            logger.error(f"❌ Failed to load trust state: {e}")
            return None

    # =========================================================================
    # Database Persistence (SQLite)
    # =========================================================================

    def save_to_db(self, db_path: str | Path, agent_id: str = "default") -> bool:
        """
        Save trust state to SQLite database.

        Args:
            db_path: Path to SQLite database
            agent_id: Unique identifier for this agent

        Returns:
            True if save successful
        """
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Create tables if not exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trust_state (
                    agent_id TEXT PRIMARY KEY,
                    trust_score REAL,
                    autonomy_level TEXT,
                    success_count INTEGER,
                    failure_count INTEGER,
                    updated_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trust_tools (
                    agent_id TEXT,
                    tool_name TEXT,
                    trust_score REAL,
                    success_count INTEGER,
                    failure_count INTEGER,
                    PRIMARY KEY (agent_id, tool_name)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trust_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TEXT,
                    event_type TEXT,
                    value REAL,
                    details TEXT,
                    tool TEXT
                )
            ''')

            # Save main state
            cursor.execute('''
                INSERT OR REPLACE INTO trust_state
                (agent_id, trust_score, autonomy_level, success_count, failure_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                agent_id,
                self.trust_score,
                self.autonomy_level.name,
                self.success_count,
                self.failure_count,
                datetime.now().isoformat()
            ))

            # Save tool trust
            cursor.execute('DELETE FROM trust_tools WHERE agent_id = ?', (agent_id,))
            for name, tt in self._tool_trust.items():
                cursor.execute('''
                    INSERT INTO trust_tools
                    (agent_id, tool_name, trust_score, success_count, failure_count)
                    VALUES (?, ?, ?, ?, ?)
                ''', (agent_id, name, tt.trust_score, tt.success_count, tt.failure_count))

            # Save recent records (last 100)
            cursor.execute('DELETE FROM trust_records WHERE agent_id = ?', (agent_id,))
            for record in self.records[-100:]:
                cursor.execute('''
                    INSERT INTO trust_records
                    (agent_id, timestamp, event_type, value, details, tool)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    agent_id,
                    record.timestamp.isoformat(),
                    record.event_type,
                    record.value,
                    record.details,
                    record.tool
                ))

            conn.commit()
            conn.close()

            logger.info(f"💾 Trust state saved to DB: {db_path} (agent={agent_id})")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to save trust to DB: {e}")
            return False

    @classmethod
    def load_from_db(
        cls,
        db_path: str | Path,
        agent_id: str = "default"
    ) -> Optional['TrustManager']:
        """
        Load TrustManager from SQLite database.

        Args:
            db_path: Path to SQLite database
            agent_id: Unique identifier for this agent

        Returns:
            TrustManager instance or None if load fails
        """
        try:
            path = Path(db_path)
            if not path.exists():
                logger.warning(f"Trust DB not found: {path}")
                return None

            conn = sqlite3.connect(str(path))
            cursor = conn.cursor()

            # Load main state
            cursor.execute('''
                SELECT trust_score, autonomy_level, success_count, failure_count
                FROM trust_state WHERE agent_id = ?
            ''', (agent_id,))
            row = cursor.fetchone()

            if not row:
                conn.close()
                logger.warning(f"No trust state found for agent: {agent_id}")
                return None

            manager = cls(initial_score=row[0])
            manager.success_count = row[2]
            manager.failure_count = row[3]

            try:
                manager.autonomy_level = AutonomyLevel[row[1]]
            except KeyError:
                manager.autonomy_level = AutonomyLevel.ASSISTED

            # Load tool trust
            cursor.execute('''
                SELECT tool_name, trust_score, success_count, failure_count
                FROM trust_tools WHERE agent_id = ?
            ''', (agent_id,))
            for tool_row in cursor.fetchall():
                manager._tool_trust[tool_row[0]] = ToolTrust(
                    name=tool_row[0],
                    trust_score=tool_row[1],
                    success_count=tool_row[2],
                    failure_count=tool_row[3]
                )

            # Load records
            cursor.execute('''
                SELECT timestamp, event_type, value, details, tool
                FROM trust_records WHERE agent_id = ?
                ORDER BY timestamp DESC LIMIT 100
            ''', (agent_id,))
            manager.records = []
            for rec_row in cursor.fetchall():
                try:
                    manager.records.append(TrustRecord(
                        timestamp=datetime.fromisoformat(rec_row[0]),
                        event_type=rec_row[1],
                        value=rec_row[2],
                        details=rec_row[3] or '',
                        tool=rec_row[4]
                    ))
                except (ValueError, TypeError):
                    continue

            conn.close()

            logger.info(f"📂 Loaded trust state from DB: {agent_id}")
            return manager

        except Exception as e:
            logger.error(f"❌ Failed to load trust from DB: {e}")
            return None

    # =========================================================================
    # Auto-persist wrapper
    # =========================================================================

    def enable_auto_persist(
        self,
        file_path: str | Path | None = None,
        db_path: str | Path | None = None,
        agent_id: str = "default"
    ) -> None:
        """
        Enable automatic persistence after each trust update.

        At least one of file_path or db_path must be provided.

        Args:
            file_path: JSON file path for persistence
            db_path: SQLite database path for persistence
            agent_id: Agent identifier for database persistence
        """
        self._auto_persist_file = Path(file_path) if file_path else None
        self._auto_persist_db = Path(db_path) if db_path else None
        self._auto_persist_agent_id = agent_id

        logger.info(f"Auto-persist enabled: file={file_path}, db={db_path}")

    def _auto_save(self) -> None:
        """Perform auto-save if enabled."""
        if hasattr(self, '_auto_persist_file') and self._auto_persist_file:
            self.save_to_file(self._auto_persist_file)
        if hasattr(self, '_auto_persist_db') and self._auto_persist_db:
            self.save_to_db(self._auto_persist_db, self._auto_persist_agent_id)
