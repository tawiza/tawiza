"""RSS/Atom feed parser."""
from typing import Any

from .registry import BaseParser

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False


class FeedParser(BaseParser):
    """Parser for RSS and Atom feeds."""

    def can_parse(self, content_type: str, url: str) -> bool:
        """Check if content is a feed."""
        feed_types = ["rss", "atom", "xml"]
        return any(t in content_type.lower() for t in feed_types) or \
               any(url.lower().endswith(f".{t}") for t in ["rss", "atom", "xml"])

    async def parse(self, content: str, url: str) -> dict[str, Any]:
        """Parse feed and extract entries."""
        if not HAS_FEEDPARSER:
            return {"error": "feedparser not installed", "entries": []}

        feed = feedparser.parse(content)

        entries = []
        for entry in feed.entries[:50]:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", "")[:500],
                "published": entry.get("published", ""),
            })

        return {
            "title": feed.feed.get("title", ""),
            "description": feed.feed.get("description", ""),
            "entries": entries,
            "count": len(entries),
        }
