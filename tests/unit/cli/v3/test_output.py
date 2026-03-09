"""Tests for CLI v3 output formatters."""

import json
from dataclasses import dataclass

import pytest

from src.cli.v3.output.base import OutputFormat, OutputOptions
from src.cli.v3.output.formatters import CSVFormatter, JSONFormatter, TableFormatter
from src.cli.v3.output.renderer import detect_format, render


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_dict(self):
        """Should format dict as JSON."""
        formatter = JSONFormatter()
        result = formatter.format({"key": "value", "number": 42})

        assert '"key": "value"' in result
        assert '"number": 42' in result

    def test_format_list(self):
        """Should format list as JSON array."""
        formatter = JSONFormatter()
        result = formatter.format([1, 2, 3])

        parsed = json.loads(result)
        assert parsed == [1, 2, 3]

    def test_format_dataclass(self):
        """Should format dataclass as JSON."""

        @dataclass
        class TestData:
            name: str
            value: int

        formatter = JSONFormatter()
        data = TestData(name="test", value=42)
        result = formatter.format(data)

        parsed = json.loads(result)
        assert parsed["name"] == "test"
        assert parsed["value"] == 42

    def test_custom_indent(self):
        """Should respect indent option."""
        formatter = JSONFormatter()
        options = OutputOptions(indent=4)
        result = formatter.format({"a": 1}, options)

        assert "    " in result  # 4-space indent

    def test_content_type(self):
        """Should return correct content type."""
        formatter = JSONFormatter()
        assert formatter.get_content_type() == "application/json"


class TestTableFormatter:
    """Tests for TableFormatter."""

    def test_format_dict(self):
        """Should format dict as key-value table."""
        formatter = TableFormatter()
        result = formatter.format({"name": "test", "value": 42})

        assert "Name" in result or "name" in result.lower()
        assert "test" in result

    def test_format_list_of_dicts(self):
        """Should format list of dicts as table."""
        formatter = TableFormatter()
        data = [
            {"name": "a", "value": 1},
            {"name": "b", "value": 2},
        ]
        result = formatter.format(data)

        assert "a" in result
        assert "b" in result

    def test_format_empty_list(self):
        """Should handle empty list."""
        formatter = TableFormatter()
        result = formatter.format([])
        assert result is not None

    def test_with_title(self):
        """Should include title when provided."""
        formatter = TableFormatter()
        options = OutputOptions(title="Test Title")
        result = formatter.format({"key": "value"}, options)

        assert "Test Title" in result


class TestCSVFormatter:
    """Tests for CSVFormatter."""

    def test_format_list_of_dicts(self):
        """Should format list as CSV."""
        formatter = CSVFormatter()
        data = [
            {"name": "a", "value": "1"},
            {"name": "b", "value": "2"},
        ]
        result = formatter.format(data)

        lines = result.strip().split("\n")
        assert len(lines) == 3  # Header + 2 rows
        assert "name" in lines[0]
        assert "a" in lines[1]

    def test_no_header_option(self):
        """Should skip header when requested."""
        formatter = CSVFormatter()
        options = OutputOptions(show_header=False)
        data = [{"name": "a"}]
        result = formatter.format(data, options)

        lines = result.strip().split("\n")
        assert len(lines) == 1
        assert "a" in lines[0]


class TestRenderer:
    """Tests for output renderer."""

    def test_render_json(self):
        """Should render JSON format."""
        result = render({"test": "data"}, OutputFormat.JSON)
        parsed = json.loads(result)
        assert parsed["test"] == "data"

    def test_render_table(self):
        """Should render table format."""
        result = render({"test": "data"}, OutputFormat.TABLE)
        assert "test" in result.lower()

    def test_render_csv(self):
        """Should render CSV format."""
        result = render([{"a": "1"}], OutputFormat.CSV)
        assert "a" in result
        assert "1" in result
