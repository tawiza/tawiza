"""Specialized Camel agents for territorial intelligence.

Coordination:
- OrchestratorAgent: Multi-agent workflow coordination

Core Workforce Agents (market analysis):
- DataAgent: Sirene data collection + web context
- GeoAgent: Mapping and geolocation
- WebAgent: Web enrichment
- AnalystAgent: Strategic analysis with SWOT

Specialized Agents:
- VeilleAgent: Market monitoring and alerts
- FinanceAgent: Financial data analysis
- SimulationAgent: Economic scenario simulation
- BusinessPlanAgent: Business plan generation
- ProspectionAgent: Lead scoring and outreach
- ComparisonAgent: Multi-territory comparison
"""

from .analyst_agent import create_analyst_agent, get_analyst_agent
from .business_plan_agent import create_business_plan_agent, get_business_plan_agent
from .comparison_agent import create_comparison_agent, get_comparison_agent
from .data_agent import create_data_agent, get_data_agent
from .finance_agent import create_finance_agent, get_finance_agent
from .geo_agent import create_geo_agent, get_geo_agent
from .orchestrator_agent import create_orchestrator_agent, get_orchestrator_agent
from .prospection_agent import create_prospection_agent, get_prospection_agent
from .simulation_agent import create_simulation_agent, get_simulation_agent
from .veille_agent import create_veille_agent, get_veille_agent
from .web_agent import create_web_agent, get_web_agent

__all__ = [
    # Coordination
    "create_orchestrator_agent",
    "get_orchestrator_agent",
    # Core Workforce
    "create_data_agent",
    "get_data_agent",
    "create_geo_agent",
    "get_geo_agent",
    "create_web_agent",
    "get_web_agent",
    "create_analyst_agent",
    "get_analyst_agent",
    # Specialized Agents
    "create_veille_agent",
    "get_veille_agent",
    "create_finance_agent",
    "get_finance_agent",
    "create_simulation_agent",
    "get_simulation_agent",
    "create_business_plan_agent",
    "get_business_plan_agent",
    "create_prospection_agent",
    "get_prospection_agent",
    "create_comparison_agent",
    "get_comparison_agent",
]
