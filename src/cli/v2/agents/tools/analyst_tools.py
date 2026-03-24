"""Data analyst tools for the unified agent."""

from typing import Any

from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry


def register_analyst_tools(registry: ToolRegistry) -> None:
    """Register data analysis tools."""

    async def analyst_analyze(data_path: str, analysis_type: str = "auto") -> dict[str, Any]:
        """Analyze a dataset."""
        try:
            from src.infrastructure.agents.advanced.data_analyst_agent import DataAnalystAgent

            agent = DataAnalystAgent()
            result = await agent.analyze_dataset(file_path=data_path)

            return {
                "success": True,
                "dataset_id": result.dataset_id,
                "rows": result.rows,
                "columns": result.columns,
                "quality_score": result.quality_score,
                "missing_data_percentage": result.missing_data_percentage,
                "duplicate_rows": result.duplicate_rows,
                "numerical_columns": result.numerical_columns,
                "categorical_columns": result.categorical_columns,
                "recommendations": result.recommendations[:5],  # Top 5 recommendations
                "anomalies_count": len(result.anomalies_detected),
            }
        except Exception as e:
            logger.error(f"Analyst analyze failed: {e}")
            return {"success": False, "error": str(e)}

    async def analyst_report(data_path: str) -> dict[str, Any]:
        """Generate a detailed analysis report."""
        try:
            from src.infrastructure.agents.advanced.data_analyst_agent import DataAnalystAgent

            agent = DataAnalystAgent()
            result = await agent.analyze_dataset(file_path=data_path)
            report = await agent.generate_data_report(result)

            return {
                "success": True,
                "report": report,
                "quality_score": result.quality_score,
            }
        except Exception as e:
            logger.error(f"Analyst report failed: {e}")
            return {"success": False, "error": str(e)}

    # Register tools
    registry._tools["analyst.analyze"] = Tool(
        name="analyst.analyze",
        func=analyst_analyze,
        category=ToolCategory.ANALYST,
        description="Analyze a dataset and get insights (CSV, Excel, JSON, Parquet)",
    )

    registry._tools["analyst.report"] = Tool(
        name="analyst.report",
        func=analyst_report,
        category=ToolCategory.ANALYST,
        description="Generate detailed analysis report in markdown",
    )

    logger.debug("Registered 2 analyst tools")
