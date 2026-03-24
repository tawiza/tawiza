"""JSON content parser."""

import json
from typing import Any

from .registry import BaseParser


class JSONParser(BaseParser):
    """Parser for JSON API responses."""

    def can_parse(self, content_type: str, url: str) -> bool:
        """Check if content is JSON."""
        return "application/json" in content_type.lower()

    async def parse(self, content: str, url: str) -> dict[str, Any]:
        """Parse JSON content."""
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return {"items": data, "count": len(data)}
            return data
        except json.JSONDecodeError as e:
            return {"error": str(e), "raw": content[:200]}
