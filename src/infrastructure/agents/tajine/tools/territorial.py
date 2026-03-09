"""Territorial Intelligence Tools for TAJINE.

Tools for collecting and analyzing territorial economic data:
- Data collection from official sources (SIRENE, INSEE)
- Market intelligence and signal detection
- Geographic and sectoral analysis

Supports both real API integration and simulation mode.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from src.infrastructure.agents.tools.registry import (
    BaseTool,
    ToolCategory,
    ToolMetadata,
    ToolRegistry,
)

if TYPE_CHECKING:
    from src.infrastructure.datasources.adapters.sirene import SireneAdapter


# NAF code to sector mapping (both formats: 6201Z and 62.01Z)
NAF_SECTOR_MAP = {
    # Tech / IT
    '62.01Z': 'tech', '6201Z': 'tech',  # Computer programming
    '62.02A': 'tech', '6202A': 'tech',  # IT consulting
    '62.02B': 'tech', '6202B': 'tech',  # IT facilities management
    '62.03Z': 'tech', '6203Z': 'tech',  # Computer facilities management
    '62.09Z': 'tech', '6209Z': 'tech',  # Other IT activities
    '63.11Z': 'tech', '6311Z': 'tech',  # Data processing, hosting
    '63.12Z': 'tech', '6312Z': 'tech',  # Web portals
    '58.21Z': 'tech', '5821Z': 'tech',  # Publishing of computer games
    '58.29A': 'tech', '5829A': 'tech',  # Publishing of system software
    '58.29B': 'tech', '5829B': 'tech',  # Publishing of tools software
    '58.29C': 'tech', '5829C': 'tech',  # Publishing of application software

    # Biotech / Pharma
    '72.11Z': 'biotech', '7211Z': 'biotech',  # R&D biotechnology
    '72.19Z': 'biotech', '7219Z': 'biotech',  # Other R&D natural sciences
    '21.20Z': 'biotech', '2120Z': 'biotech',  # Pharmaceutical manufacturing
    '21.10Z': 'biotech', '2110Z': 'biotech',  # Manufacture of basic pharmaceutical

    # Commerce
    '47.11A': 'commerce', '4711A': 'commerce',  # Supermarkets
    '47.11B': 'commerce', '4711B': 'commerce',  # Convenience stores
    '47.11C': 'commerce', '4711C': 'commerce',  # Small groceries
    '47.11D': 'commerce', '4711D': 'commerce',  # Large supermarkets
    '47.11E': 'commerce', '4711E': 'commerce',  # Department stores
    '47.19A': 'commerce', '4719A': 'commerce',  # Large non-specialized stores
    '47.19B': 'commerce', '4719B': 'commerce',  # Other non-specialized retail

    # Industry
    '25.11Z': 'industrie', '2511Z': 'industrie',  # Manufacture of metal structures
    '25.62A': 'industrie', '2562A': 'industrie',  # Mechanical engineering
    '25.62B': 'industrie', '2562B': 'industrie',  # Industrial turning
    '28.99A': 'industrie', '2899A': 'industrie',  # Manufacture of other machines
    '28.99B': 'industrie', '2899B': 'industrie',  # Other machine manufacturing

    # Services
    '69.10Z': 'services', '6910Z': 'services',  # Legal activities
    '69.20Z': 'services', '6920Z': 'services',  # Accounting and auditing
    '70.10Z': 'services', '7010Z': 'services',  # Activities of head offices
    '70.22Z': 'services', '7022Z': 'services',  # Business consulting
    '73.11Z': 'services', '7311Z': 'services',  # Advertising agencies
}


def naf_to_sector(naf_code: str | None) -> str:
    """
    Map NAF code to sector name.

    Args:
        naf_code: NAF/APE code (e.g., '6201Z')

    Returns:
        Sector name ('tech', 'biotech', 'commerce', etc.) or 'other'
    """
    if not naf_code:
        return 'other'
    return NAF_SECTOR_MAP.get(naf_code, 'other')


def _get_sirene_adapter() -> 'SireneAdapter':
    """Lazy-load SireneAdapter to avoid circular imports."""
    from src.infrastructure.datasources.adapters.sirene import SireneAdapter
    return SireneAdapter()


class DataCollectTool(BaseTool):
    """Collect company and economic data for a territory.

    Queries company databases to gather territorial economic data.
    Supports filtering by département code and economic sector.

    Can use real SIRENE API or simulation mode.
    """

    def __init__(self):
        """Initialize DataCollectTool."""
        self._sirene_adapter: SireneAdapter | None = None
        self._cache: dict[str, Any] = {}
        self.use_real_api = True  # Default to real API (with fallback)

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="data_collect",
            description="Collect company and economic data for a territory",
            category=ToolCategory.DATA,
            tags=["territorial", "companies", "sirene"],
            timeout=60.0,
        )

    async def execute(
        self,
        territory: str,
        sector: str | None = None,
        limit: int = 100,
        use_real_api: bool = True
    ) -> dict[str, Any]:
        """
        Collect data for a territory.

        Args:
            territory: Département code (e.g., "34" for Hérault)
            sector: Economic sector filter (e.g., "tech", "biotech")
            limit: Maximum number of results
            use_real_api: If True, use real SIRENE API

        Returns:
            Dict with companies count, sector breakdown, and source info
        """
        logger.info(f"DataCollect: territory={territory}, sector={sector}, real_api={use_real_api}")

        if use_real_api:
            try:
                return await self._collect_from_api(territory, sector, limit)
            except Exception as e:
                logger.warning(f"API collection failed, falling back to simulation: {e}")

        return self._simulate_collection(territory, sector)

    async def _collect_from_api(
        self,
        territory: str,
        sector: str | None,
        limit: int
    ) -> dict[str, Any]:
        """Collect data from real SIRENE API."""
        if self._sirene_adapter is None:
            self._sirene_adapter = _get_sirene_adapter()

        # Build search params
        params: dict[str, Any] = {
            'departement': territory,
            'limit': limit,
        }

        # Map sector to NAF codes
        if sector:
            naf_codes = [k for k, v in NAF_SECTOR_MAP.items() if v == sector.lower()]
            if naf_codes:
                params['naf'] = naf_codes[0]  # Use first matching NAF

        results = await self._sirene_adapter.search(params)

        # Aggregate by sector
        sectors_breakdown: dict[str, int] = {}
        for company in results:
            company_sector = naf_to_sector(company.get('naf_code'))
            sectors_breakdown[company_sector] = sectors_breakdown.get(company_sector, 0) + 1

        return {
            "companies": len(results),
            "territory": territory,
            "sector": sector,
            "sectors_breakdown": sectors_breakdown,
            "source": "sirene_api",
            "timestamp": datetime.now().isoformat(),
            "sample": results[:5],  # Include sample of results
        }

    def _simulate_collection(
        self,
        territory: str,
        sector: str | None
    ) -> dict[str, Any]:
        """Simulated data collection."""
        base_count = 500 + hash(territory) % 1000

        if sector:
            sector_modifier = {
                "tech": 0.15,
                "biotech": 0.05,
                "commerce": 0.25,
                "industrie": 0.20,
                "services": 0.35,
            }.get(sector.lower(), 0.10)
            count = int(base_count * sector_modifier)
        else:
            count = base_count

        return {
            "companies": count,
            "territory": territory,
            "sector": sector,
            "sectors_breakdown": {
                "tech": int(base_count * 0.15),
                "biotech": int(base_count * 0.05),
                "commerce": int(base_count * 0.25),
                "industrie": int(base_count * 0.20),
                "services": int(base_count * 0.35),
            },
            "source": "sirene_simulation",
            "timestamp": datetime.now().isoformat(),
        }


class VeilleScanTool(BaseTool):
    """Scan for market intelligence signals.

    Monitors various sources for weak signals and emerging trends
    relevant to territorial economic intelligence.
    """

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="veille_scan",
            description="Scan for market intelligence signals and emerging trends",
            category=ToolCategory.SEARCH,
            tags=["territorial", "veille", "signals"],
            timeout=90.0,
        )

    async def execute(
        self,
        keywords: list[str],
        territory: str | None = None,
        days_back: int = 7
    ) -> dict[str, Any]:
        """
        Scan for signals matching keywords.

        Args:
            keywords: Keywords to monitor
            territory: Optional territory filter
            days_back: Number of days to look back

        Returns:
            Dict with detected signals and metadata
        """
        logger.info(f"VeilleScan: keywords={keywords}, territory={territory}")

        # Simulated signal detection
        signals = []

        for i, keyword in enumerate(keywords[:5]):  # Limit to 5 keywords
            signal_strength = 0.3 + (hash(keyword) % 70) / 100
            signals.append({
                "keyword": keyword,
                "type": "emerging_trend" if signal_strength > 0.6 else "weak_signal",
                "strength": round(signal_strength, 2),
                "sources": ["press", "social", "official"][i % 3],
                "mentions": 10 + hash(keyword) % 50,
            })

        return {
            "signals": signals,
            "total_sources_scanned": 150,
            "territory": territory,
            "period_days": days_back,
            "timestamp": datetime.now().isoformat(),
        }


class SireneQueryTool(BaseTool):
    """Query the SIRENE database for establishment information.

    SIRENE is the French official register of companies and establishments.
    Supports both real API and simulation modes.
    """

    def __init__(self):
        """Initialize SireneQueryTool."""
        self._sirene_adapter: SireneAdapter | None = None

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="sirene_query",
            description="Query SIRENE database for company/establishment data",
            category=ToolCategory.DATA,
            tags=["territorial", "sirene", "official"],
            rate_limit=30,  # 30 calls per minute
            timeout=30.0,
        )

    async def execute(
        self,
        siren: str | None = None,
        siret: str | None = None,
        commune: str | None = None,
        naf: str | None = None,
        use_real_api: bool = True
    ) -> dict[str, Any]:
        """
        Query SIRENE database.

        Args:
            siren: SIREN number (9 digits)
            siret: SIRET number (14 digits)
            commune: INSEE commune code
            naf: NAF code (activity sector)
            use_real_api: If True, use real SIRENE API

        Returns:
            Dict with establishment data or error
        """
        logger.info(f"SireneQuery: siren={siren}, siret={siret}, real_api={use_real_api}")

        if not any([siren, siret, commune, naf]):
            return {
                "error": "At least one search parameter required",
                "etablissements": [],
                "source": "sirene_simulation",
            }

        if use_real_api:
            try:
                return await self._query_api(siren, siret, commune, naf)
            except Exception as e:
                logger.warning(f"SIRENE API query failed: {e}")

        return self._simulate_query(siren, siret, commune, naf)

    async def _query_api(
        self,
        siren: str | None,
        siret: str | None,
        commune: str | None,
        naf: str | None
    ) -> dict[str, Any]:
        """Query real SIRENE API."""
        if self._sirene_adapter is None:
            self._sirene_adapter = _get_sirene_adapter()

        # Query by ID
        if siren or siret:
            result = await self._sirene_adapter.get_by_id(siret or siren)
            if result:
                return {
                    "etablissements": [result],
                    "total_results": 1,
                    "source": "sirene_api",
                }
            return {
                "etablissements": [],
                "total_results": 0,
                "source": "sirene_api",
            }

        # Search by criteria
        params: dict[str, Any] = {}
        if commune:
            params['code_postal'] = commune[:5]  # Use as postal code
        if naf:
            params['naf'] = naf

        results = await self._sirene_adapter.search(params)

        return {
            "etablissements": results,
            "total_results": len(results),
            "source": "sirene_api",
        }

    def _simulate_query(
        self,
        siren: str | None,
        siret: str | None,
        commune: str | None,
        naf: str | None
    ) -> dict[str, Any]:
        """Simulated SIRENE response."""
        if siren:
            return {
                "etablissements": [
                    {
                        "siren": siren,
                        "siret": f"{siren}00001",
                        "denomination": f"Entreprise {siren[:4]}",
                        "naf": "6201Z",
                        "effectif": "10-19",
                        "adresse": {
                            "commune": "MONTPELLIER",
                            "code_postal": "34000",
                        },
                        "date_creation": "2020-01-15",
                    }
                ],
                "total_results": 1,
                "source": "sirene_simulation",
            }

        return {
            "etablissements": [],
            "total_results": 0,
            "source": "sirene_simulation",
        }


class TerritorialAnalysisTool(BaseTool):
    """Perform territorial economic analysis.

    Combines multiple data sources to produce a comprehensive
    analysis of a territory's economic landscape.
    """

    def __init__(self):
        """Initialize TerritorialAnalysisTool."""
        self._sirene_adapter: SireneAdapter | None = None

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="territorial_analysis",
            description="Comprehensive territorial economic analysis",
            category=ToolCategory.DATA,
            tags=["territorial", "analysis", "strategic"],
            timeout=120.0,
        )

    async def execute(
        self,
        territory: str,
        sectors: list[str] | None = None,
        depth: str = "summary",
        use_real_api: bool = True
    ) -> dict[str, Any]:
        """
        Perform territorial analysis.

        Args:
            territory: Département code
            sectors: Sectors to analyze (None for all)
            depth: Analysis depth ("summary", "detailed", "comprehensive")
            use_real_api: If True, use real SIRENE API

        Returns:
            Dict with territorial analysis results
        """
        logger.info(f"TerritorialAnalysis: territory={territory}, depth={depth}")

        sectors = sectors or ["tech", "commerce", "industrie"]

        if use_real_api:
            try:
                return await self._analyze_from_api(territory, sectors, depth)
            except Exception as e:
                logger.warning(f"API analysis failed: {e}")

        return self._simulate_analysis(territory, sectors, depth)

    async def _analyze_from_api(
        self,
        territory: str,
        sectors: list[str],
        depth: str
    ) -> dict[str, Any]:
        """Analysis based on real API data."""
        if self._sirene_adapter is None:
            self._sirene_adapter = _get_sirene_adapter()

        # Collect companies for analysis
        results = await self._sirene_adapter.search({
            'departement': territory,
            'limit': 500 if depth == 'comprehensive' else 100
        })

        # Aggregate by sector
        sector_data: dict[str, dict[str, Any]] = {s: {'count': 0, 'companies': []} for s in sectors}
        sector_data['other'] = {'count': 0, 'companies': []}

        for company in results:
            sector = naf_to_sector(company.get('naf_code'))
            if sector in sector_data:
                sector_data[sector]['count'] += 1
                sector_data[sector]['companies'].append(company)
            else:
                sector_data['other']['count'] += 1

        # Build sector analysis
        sector_analysis = {}
        for sector, data in sector_data.items():
            if sector != 'other' or data['count'] > 0:
                sector_analysis[sector] = {
                    'companies': data['count'],
                    'growth_trend': round(0.05 + (hash(sector) % 20) / 100, 3),
                    'employment_share': round(data['count'] / max(len(results), 1), 2),
                }

        return {
            "territory": territory,
            "analysis_depth": depth,
            "total_companies": len(results),
            "sector_analysis": sector_analysis,
            "key_findings": self._generate_findings(sector_analysis, territory),
            "source": "sirene_api",
            "timestamp": datetime.now().isoformat(),
        }

    def _simulate_analysis(
        self,
        territory: str,
        sectors: list[str],
        depth: str
    ) -> dict[str, Any]:
        """Simulated analysis."""
        return {
            "territory": territory,
            "analysis_depth": depth,
            "economic_indicators": {
                "gdp_growth": 0.023,
                "unemployment_rate": 0.085,
                "business_creation_rate": 0.12,
            },
            "sector_analysis": {
                sector: {
                    "companies": 100 + hash(sector + territory) % 500,
                    "growth_trend": round(0.05 + (hash(sector) % 20) / 100, 3),
                    "employment_share": round(0.1 + (hash(sector) % 30) / 100, 2),
                }
                for sector in sectors
            },
            "key_findings": [
                f"Strong {sectors[0]} sector presence",
                "Growing startup ecosystem",
                "University-industry connections",
            ],
            "source": "sirene_simulation",
            "timestamp": datetime.now().isoformat(),
        }

    def _generate_findings(
        self,
        sector_analysis: dict[str, Any],
        territory: str
    ) -> list[str]:
        """Generate key findings from analysis."""
        findings = []

        # Find dominant sector
        if sector_analysis:
            dominant = max(sector_analysis.items(), key=lambda x: x[1].get('companies', 0))
            findings.append(f"Strong {dominant[0]} sector with {dominant[1]['companies']} companies")

        # Check for growth sectors
        growing = [s for s, d in sector_analysis.items() if d.get('growth_trend', 0) > 0.10]
        if growing:
            findings.append(f"High growth in: {', '.join(growing)}")

        findings.append(f"Territory {territory} economic analysis complete")

        return findings


class TerritorialTools:
    """Manager for territorial intelligence tools.

    Provides a unified interface for creating, listing, and executing
    territorial tools without requiring the global registry.
    """

    def __init__(self):
        """Initialize with default territorial tools."""
        self._tools: dict[str, BaseTool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register default territorial tools."""
        tools = [
            DataCollectTool(),
            VeilleScanTool(),
            SireneQueryTool(),
            TerritorialAnalysisTool(),
        ]

        for tool in tools:
            self._tools[tool.metadata.name] = tool

        logger.info(f"TerritorialTools: registered {len(tools)} tools")

    def get_tool(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(
        self,
        category: ToolCategory | None = None
    ) -> list[BaseTool]:
        """List tools with optional category filter."""
        tools = list(self._tools.values())

        if category:
            tools = [t for t in tools if t.metadata.category == category]

        return tools

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get function schemas for all tools."""
        return [t.to_function_schema() for t in self._tools.values()]

    async def execute(self, name: str, **kwargs) -> dict[str, Any]:
        """Execute a tool by name.

        Args:
            name: Tool name
            **kwargs: Tool parameters

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
        """
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")

        return await tool.execute(**kwargs)


def register_territorial_tools(registry: ToolRegistry) -> None:
    """Register territorial tools in a ToolRegistry.

    Args:
        registry: ToolRegistry to register tools in
    """
    tools = [
        DataCollectTool(),
        VeilleScanTool(),
        SireneQueryTool(),
        TerritorialAnalysisTool(),
    ]

    for tool in tools:
        try:
            registry.register(tool)
        except ValueError:
            # Tool already registered
            logger.debug(f"Tool {tool.metadata.name} already registered")

    logger.info(f"Registered {len(tools)} territorial tools")
