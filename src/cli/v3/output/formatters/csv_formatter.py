"""CSV output formatter."""

import csv
from dataclasses import asdict, is_dataclass
from io import StringIO
from typing import Any, Optional

from src.cli.v3.output.base import OutputFormatter, OutputOptions


class CSVFormatter(OutputFormatter):
    """Formats output as CSV."""

    def format(self, data: Any, options: OutputOptions | None = None) -> str:
        """Format data as CSV string.

        Args:
            data: Data to format (list of dicts)
            options: Formatting options

        Returns:
            CSV string
        """
        opts = options or OutputOptions()
        buffer = StringIO()

        # Convert single dict to list
        if isinstance(data, dict):
            # Check if it's a flat dict or nested
            if any(isinstance(v, (dict, list)) for v in data.values()):
                # Nested dict - flatten to key-value rows
                data = [{"key": k, "value": str(v)} for k, v in data.items()]
            else:
                data = [data]

        # Convert dataclasses
        if data and is_dataclass(data[0]) and not isinstance(data[0], type):
            data = [asdict(item) for item in data]

        if not data:
            return ""

        # Get fieldnames from first item
        fieldnames = list(data[0].keys()) if isinstance(data[0], dict) else ["value"]

        writer = csv.DictWriter(
            buffer,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        if opts.show_header:
            writer.writeheader()

        for row in data:
            if isinstance(row, dict):
                # Stringify complex values
                row = {k: str(v) if isinstance(v, (dict, list)) else v for k, v in row.items()}
                writer.writerow(row)
            else:
                writer.writerow({"value": row})

        return buffer.getvalue()

    def supports_streaming(self) -> bool:
        """CSV supports streaming."""
        return True

    def get_content_type(self) -> str:
        """Return CSV content type."""
        return "text/csv"
