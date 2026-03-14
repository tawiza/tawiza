"""JSON output formatter."""

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Optional

from src.cli.v3.output.base import OutputFormatter, OutputOptions


class JSONFormatter(OutputFormatter):
    """Formats output as JSON."""

    def format(self, data: Any, options: OutputOptions | None = None) -> str:
        """Format data as JSON string.

        Args:
            data: Data to format
            options: Formatting options

        Returns:
            JSON string
        """
        opts = options or OutputOptions()

        # Convert dataclasses to dicts
        if is_dataclass(data) and not isinstance(data, type):
            data = asdict(data)

        return json.dumps(
            data,
            indent=opts.indent,
            sort_keys=opts.sort_keys,
            default=self._json_serializer,
            ensure_ascii=False,
        )

    def supports_streaming(self) -> bool:
        """JSON doesn't support streaming well."""
        return False

    def get_content_type(self) -> str:
        """Return JSON content type."""
        return "application/json"

    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom JSON serializer for special types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)
