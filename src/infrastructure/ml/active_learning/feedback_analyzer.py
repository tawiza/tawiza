"""
Feedback analyzer for detecting patterns and conflicts.
"""

from typing import Any

from loguru import logger


class FeedbackAnalyzer:
    """Analyzes feedback to detect patterns and conflicts."""

    def detect_conflicts(
        self,
        feedbacks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Detect conflicting feedback for the same input.

        Args:
            feedbacks: List of feedback items

        Returns:
            List of conflicts detected
        """
        # Group by input
        input_groups: dict[str, list[dict[str, Any]]] = {}

        for feedback in feedbacks:
            input_text = feedback.get("input", "")
            if input_text not in input_groups:
                input_groups[input_text] = []
            input_groups[input_text].append(feedback)

        # Find conflicts
        conflicts = []

        for input_text, group in input_groups.items():
            if len(group) < 2:
                continue

            # Check for different labels
            labels = {fb.get("correct_label") for fb in group if fb.get("correct_label")}

            if len(labels) > 1:
                conflicts.append(
                    {
                        "input": input_text,
                        "count": len(group),
                        "labels": list(labels),
                        "feedbacks": group,
                    }
                )

        logger.info(f"Detected {len(conflicts)} conflicting feedback groups")

        return conflicts

    def analyze_error_patterns(
        self,
        feedbacks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze error patterns in feedback.

        Args:
            feedbacks: List of feedback items

        Returns:
            Analysis results
        """
        # Count error types
        error_types: dict[str, int] = {}

        for feedback in feedbacks:
            feedback_type = feedback.get("feedback_type", "unknown")
            error_types[feedback_type] = error_types.get(feedback_type, 0) + 1

        # Find common words in error comments
        error_comments = [
            fb.get("comments", "") for fb in feedbacks if fb.get("feedback_type") == "correction"
        ]

        common_words = self._extract_common_words(error_comments)

        analysis = {
            "total_feedbacks": len(feedbacks),
            "error_types": error_types,
            "common_error_themes": common_words[:10],
        }

        logger.info(f"Analyzed {len(feedbacks)} feedbacks")

        return analysis

    def _extract_common_words(
        self,
        texts: list[str],
        min_length: int = 4,
    ) -> list[tuple[str, int]]:
        """
        Extract common words from texts.

        Args:
            texts: List of text strings
            min_length: Minimum word length

        Returns:
            List of (word, count) tuples
        """
        word_counts: dict[str, int] = {}

        for text in texts:
            words = text.lower().split()
            for word in words:
                # Simple filtering
                word = word.strip(".,!?;:")
                if len(word) >= min_length:
                    word_counts[word] = word_counts.get(word, 0) + 1

        # Sort by count
        sorted_words = sorted(
            word_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return sorted_words
