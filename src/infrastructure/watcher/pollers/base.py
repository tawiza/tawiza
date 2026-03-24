"""Base poller class for data sources."""

from abc import ABC, abstractmethod

from ...dashboard import Alert


class BasePoller(ABC):
    """Abstract base class for data source pollers.

    Each poller is responsible for:
    1. Querying its data source for new items
    2. Filtering results based on keywords
    3. Converting results to Alert objects
    """

    # Source identifier (override in subclasses)
    source: str = "unknown"

    # Default polling interval in seconds (override in subclasses)
    default_interval: int = 6 * 3600  # 6 hours

    def __init__(self):
        """Initialize the poller."""
        pass

    @abstractmethod
    async def poll(self, keywords: list[str]) -> list[Alert]:
        """Poll the source for new items matching keywords.

        Args:
            keywords: List of keywords to search for

        Returns:
            List of Alert objects for new items found
        """
        pass

    def matches_keywords(self, text: str, keywords: list[str]) -> bool:
        """Check if text contains any of the keywords.

        Args:
            text: Text to search in (will be lowercased)
            keywords: Keywords to look for

        Returns:
            True if any keyword is found in text
        """
        if not text or not keywords:
            return False

        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def filter_by_keywords(
        self, items: list[dict], keywords: list[str], text_fields: list[str]
    ) -> list[dict]:
        """Filter items that match any keyword in specified fields.

        Args:
            items: List of items to filter
            keywords: Keywords to match
            text_fields: Field names to search in each item

        Returns:
            Filtered list of items
        """
        if not keywords:
            return items

        filtered = []
        for item in items:
            for field in text_fields:
                text = item.get(field, "")
                if text and self.matches_keywords(str(text), keywords):
                    filtered.append(item)
                    break

        return filtered

    async def safe_poll(self, keywords: list[str]) -> tuple[list[Alert], str | None]:
        """Poll with error handling.

        Returns:
            Tuple of (alerts, error_message)
        """
        try:
            alerts = await self.poll(keywords)
            return alerts, None
        except Exception as e:
            self.logger.error(f"Error polling {self.source}: {e}")
            return [], str(e)
