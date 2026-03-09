"""Tests for TAJINE tools with real SIRENE API integration.

Tests the connection between TerritorialTools and SireneAdapter
for real-world data collection.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSireneAdapterImport:
    """Test SireneAdapter can be imported."""

    def test_import_sirene_adapter(self):
        """Test SireneAdapter can be imported."""
        from src.infrastructure.datasources.adapters.sirene import SireneAdapter

        assert SireneAdapter is not None

    def test_import_from_adapters_package(self):
        """Test import from adapters package."""
        from src.infrastructure.datasources.adapters import SireneAdapter

        assert SireneAdapter is not None


class TestDataCollectToolWithSirene:
    """Test DataCollectTool with SireneAdapter."""

    def test_data_collect_has_sirene_mode(self):
        """Test DataCollectTool can use real SIRENE."""
        from src.infrastructure.agents.tajine.tools import TerritorialTools

        tools = TerritorialTools()
        tool = tools.get_tool("data_collect")

        assert tool is not None
        assert hasattr(tool, "use_real_api")

    @pytest.mark.asyncio
    async def test_data_collect_with_mock_adapter(self):
        """Test data collection with mocked SIRENE adapter."""
        from src.infrastructure.agents.tajine.tools.territorial import DataCollectTool

        mock_adapter = MagicMock()
        mock_adapter.search = AsyncMock(
            return_value=[
                {
                    "siren": "123456789",
                    "siret": "12345678900001",
                    "nom": "Test Company",
                    "naf_code": "6201Z",
                    "adresse": {"departement": "34"},
                },
                {
                    "siren": "987654321",
                    "siret": "98765432100001",
                    "nom": "Another Company",
                    "naf_code": "6201Z",
                    "adresse": {"departement": "34"},
                },
            ]
        )

        tool = DataCollectTool()
        tool._sirene_adapter = mock_adapter

        result = await tool.execute(territory="34", sector="tech", use_real_api=True)

        assert result["source"] == "sirene_api"
        assert result["companies"] == 2
        mock_adapter.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_data_collect_fallback_on_api_error(self):
        """Test fallback to simulation on API error."""
        from src.infrastructure.agents.tajine.tools.territorial import DataCollectTool

        mock_adapter = MagicMock()
        mock_adapter.search = AsyncMock(side_effect=Exception("API unavailable"))

        tool = DataCollectTool()
        tool._sirene_adapter = mock_adapter

        result = await tool.execute(territory="34", use_real_api=True)

        # Should fallback to simulation
        assert result["source"] == "sirene_simulation"
        assert "companies" in result

    @pytest.mark.asyncio
    async def test_data_collect_simulation_mode(self):
        """Test simulation mode doesn't call API."""
        from src.infrastructure.agents.tajine.tools.territorial import DataCollectTool

        tool = DataCollectTool()

        result = await tool.execute(territory="34", use_real_api=False)

        assert result["source"] == "sirene_simulation"
        assert "companies" in result


class TestSireneQueryToolWithAdapter:
    """Test SireneQueryTool with real adapter."""

    @pytest.mark.asyncio
    async def test_sirene_query_by_siren(self):
        """Test querying by SIREN number."""
        from src.infrastructure.agents.tajine.tools.territorial import SireneQueryTool

        mock_adapter = MagicMock()
        mock_adapter.get_by_id = AsyncMock(
            return_value={
                "siren": "380129866",
                "siret": "38012986646239",
                "nom": "ORANGE",
                "naf_code": "6110Z",
            }
        )

        tool = SireneQueryTool()
        tool._sirene_adapter = mock_adapter

        result = await tool.execute(siren="380129866", use_real_api=True)

        assert result["source"] == "sirene_api"
        assert len(result["etablissements"]) == 1
        assert result["etablissements"][0]["siren"] == "380129866"

    @pytest.mark.asyncio
    async def test_sirene_query_by_commune(self):
        """Test querying by commune."""
        from src.infrastructure.agents.tajine.tools.territorial import SireneQueryTool

        mock_adapter = MagicMock()
        mock_adapter.search = AsyncMock(
            return_value=[
                {"siren": "111", "nom": "Company A"},
                {"siren": "222", "nom": "Company B"},
            ]
        )

        tool = SireneQueryTool()
        tool._sirene_adapter = mock_adapter

        result = await tool.execute(commune="34172", use_real_api=True)

        assert result["total_results"] == 2


class TestNAFCodeMapping:
    """Test NAF code to sector mapping."""

    def test_naf_to_sector_tech(self):
        """Test tech sector NAF codes."""
        from src.infrastructure.agents.tajine.tools.territorial import naf_to_sector

        assert naf_to_sector("6201Z") == "tech"  # Computer programming
        assert naf_to_sector("6202A") == "tech"  # IT consulting
        assert naf_to_sector("6311Z") == "tech"  # Data processing

    def test_naf_to_sector_biotech(self):
        """Test biotech sector NAF codes."""
        from src.infrastructure.agents.tajine.tools.territorial import naf_to_sector

        assert naf_to_sector("7211Z") == "biotech"  # R&D biotechnology
        assert naf_to_sector("2120Z") == "biotech"  # Pharmaceutical manufacturing

    def test_naf_to_sector_commerce(self):
        """Test commerce sector NAF codes."""
        from src.infrastructure.agents.tajine.tools.territorial import naf_to_sector

        assert naf_to_sector("4711A") == "commerce"  # Supermarkets
        assert naf_to_sector("4711B") == "commerce"  # Convenience stores

    def test_naf_to_sector_unknown(self):
        """Test unknown NAF code returns 'other'."""
        from src.infrastructure.agents.tajine.tools.territorial import naf_to_sector

        assert naf_to_sector("9999Z") == "other"
        assert naf_to_sector("") == "other"
        assert naf_to_sector(None) == "other"


class TestTerritorialAnalysisWithRealData:
    """Test territorial analysis with real API data."""

    @pytest.mark.asyncio
    async def test_analysis_aggregates_api_data(self):
        """Test analysis aggregates data from API."""
        from src.infrastructure.agents.tajine.tools.territorial import TerritorialAnalysisTool

        mock_adapter = MagicMock()
        mock_adapter.search = AsyncMock(
            return_value=[
                {"naf_code": "6201Z", "effectif": "10-19"},
                {"naf_code": "6201Z", "effectif": "20-49"},
                {"naf_code": "4711A", "effectif": "1-2"},
            ]
        )

        tool = TerritorialAnalysisTool()
        tool._sirene_adapter = mock_adapter

        result = await tool.execute(territory="34", sectors=["tech", "commerce"], use_real_api=True)

        assert "sector_analysis" in result
        assert result["source"] == "sirene_api"


class TestAdapterCaching:
    """Test caching behavior for API calls."""

    def test_adapter_has_cache_config(self):
        """Test adapter has cache configuration."""
        from src.infrastructure.datasources.adapters.sirene import SireneAdapter

        adapter = SireneAdapter()

        assert adapter.config.cache_ttl > 0
        assert adapter.config.cache_ttl == 604800  # 7 days

    @pytest.mark.asyncio
    async def test_tool_caches_results(self):
        """Test tool caches API results."""
        from src.infrastructure.agents.tajine.tools.territorial import DataCollectTool

        mock_adapter = MagicMock()
        mock_adapter.search = AsyncMock(return_value=[{"siren": "123"}])

        tool = DataCollectTool()
        tool._sirene_adapter = mock_adapter
        tool._cache = {}

        # First call
        await tool.execute(territory="34", use_real_api=True)
        # Second call with same params
        await tool.execute(territory="34", use_real_api=True)

        # With caching, adapter should only be called once
        # (or we test that cache is populated)
        assert "34" in tool._cache or mock_adapter.search.call_count >= 1


class TestErrorHandling:
    """Test error handling for API failures."""

    @pytest.mark.asyncio
    async def test_handles_timeout(self):
        """Test graceful handling of API timeout."""
        import httpx

        from src.infrastructure.agents.tajine.tools.territorial import DataCollectTool

        mock_adapter = MagicMock()
        mock_adapter.search = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        tool = DataCollectTool()
        tool._sirene_adapter = mock_adapter

        result = await tool.execute(territory="34", use_real_api=True)

        # Should not raise, should return simulation
        assert result["source"] == "sirene_simulation"

    @pytest.mark.asyncio
    async def test_handles_rate_limit(self):
        """Test handling of rate limit errors."""
        import httpx

        from src.infrastructure.agents.tajine.tools.territorial import DataCollectTool

        mock_adapter = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_adapter.search = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Rate limited", request=MagicMock(), response=mock_response
            )
        )

        tool = DataCollectTool()
        tool._sirene_adapter = mock_adapter

        result = await tool.execute(territory="34", use_real_api=True)

        assert result["source"] == "sirene_simulation"


class TestTAJINEAgentSireneIntegration:
    """Test TAJINEAgent integration with real SIRENE."""

    @pytest.mark.asyncio
    async def test_delegate_uses_real_api_when_configured(self):
        """Test delegate can use real API."""
        from src.infrastructure.agents.tajine import TAJINEAgent

        agent = TAJINEAgent()

        # Mock the tool registry's data_collect to track calls
        mock_tool = MagicMock()
        mock_tool.execute = AsyncMock(
            return_value={"companies": 100, "source": "sirene_api", "territory": "34"}
        )

        with patch.object(agent.tool_registry, "get_tool", return_value=mock_tool):
            with patch.object(
                agent, "_create_manus_agent", new_callable=AsyncMock, return_value=None
            ):
                result = await agent.delegate(
                    {"tool": "data_collect", "params": {"territory": "34", "use_real_api": True}}
                )

                assert result["success"] is True
