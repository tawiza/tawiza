"""Tests for TAJINE datasource tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBodaccSearchTool:
    """Test BODACC search tool."""

    def test_metadata(self):
        """Should have correct metadata."""
        from src.infrastructure.agents.tajine.tools.datasource_tools import BodaccSearchTool

        tool = BodaccSearchTool()
        meta = tool.metadata

        assert meta.name == "bodacc_search"
        assert "BODACC" in meta.description or "legal" in meta.description.lower()

    @pytest.mark.asyncio
    async def test_search_by_department(self):
        """Should search legal events by department."""
        from src.infrastructure.agents.tajine.tools.datasource_tools import BodaccSearchTool

        tool = BodaccSearchTool()

        with patch.object(tool, "_adapter") as mock_adapter:
            mock_adapter.search = AsyncMock(
                return_value=[{"type": "creation", "siret": "123", "departement": "34"}]
            )

            result = await tool.execute(department="34")

            assert result["success"] is True
            assert "data" in result


class TestBoampSearchTool:
    """Test BOAMP search tool."""

    def test_metadata(self):
        """Should have correct metadata."""
        from src.infrastructure.agents.tajine.tools.datasource_tools import BoampSearchTool

        tool = BoampSearchTool()
        meta = tool.metadata

        assert meta.name == "boamp_search"

    @pytest.mark.asyncio
    async def test_search_procurement(self):
        """Should search public procurement."""
        from src.infrastructure.agents.tajine.tools.datasource_tools import BoampSearchTool

        tool = BoampSearchTool()

        with patch.object(tool, "_adapter") as mock_adapter:
            mock_adapter.search = AsyncMock(
                return_value=[{"id": "123", "title": "Test procurement"}]
            )

            result = await tool.execute(query="informatique", department="34")

            assert result["success"] is True


class TestGeocodeTool:
    """Test BAN geocode tool."""

    def test_metadata(self):
        """Should have correct metadata."""
        from src.infrastructure.agents.tajine.tools.datasource_tools import GeocodeTool

        tool = GeocodeTool()
        meta = tool.metadata

        assert meta.name == "geocode"

    @pytest.mark.asyncio
    async def test_geocode_address(self):
        """Should geocode an address."""
        from src.infrastructure.agents.tajine.tools.datasource_tools import GeocodeTool

        tool = GeocodeTool()

        with patch.object(tool, "_adapter") as mock_adapter:
            mock_adapter.geocode = AsyncMock(
                return_value={"lat": 43.6, "lon": 3.88, "label": "Montpellier"}
            )

            result = await tool.execute(address="Montpellier")

            assert result["success"] is True
            assert "data" in result

    @pytest.mark.asyncio
    async def test_reverse_geocode(self):
        """Should reverse geocode coordinates."""
        from src.infrastructure.agents.tajine.tools.datasource_tools import GeocodeTool

        tool = GeocodeTool()

        with patch.object(tool, "_adapter") as mock_adapter:
            mock_adapter.reverse = AsyncMock(
                return_value={"lat": 43.6, "lon": 3.88, "label": "Montpellier"}
            )

            result = await tool.execute(lat=43.6, lon=3.88)

            assert result["success"] is True
            assert "data" in result


class TestGetDatasourceTools:
    """Test get_datasource_tools function."""

    def test_returns_all_tools(self):
        """Should return list of all datasource tools."""
        from src.infrastructure.agents.tajine.tools.datasource_tools import get_datasource_tools

        tools = get_datasource_tools()

        assert len(tools) == 3
        tool_names = [t.metadata.name for t in tools]
        assert "bodacc_search" in tool_names
        assert "boamp_search" in tool_names
        assert "geocode" in tool_names
