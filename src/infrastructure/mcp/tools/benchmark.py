"""MCP Tools for Agent Benchmarking.

Benchmark system for Tawiza territorial intelligence agents.
Inspired by CRAB (Cross-platform Agent Benchmark) from CAMEL AI.

Tests quality, accuracy, and performance of analysis tools.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger
from mcp.server.fastmcp import Context, FastMCP


@dataclass
class BenchmarkResult:
    """Result of a single benchmark test."""

    test_name: str
    tool_name: str
    success: bool
    execution_time: float  # seconds
    quality_score: float  # 0-100
    data_count: int
    errors: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "test_name": self.test_name,
            "tool_name": self.tool_name,
            "success": self.success,
            "execution_time": self.execution_time,
            "quality_score": self.quality_score,
            "data_count": self.data_count,
            "errors": self.errors,
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results."""

    suite_name: str
    started_at: datetime
    completed_at: datetime | None = None
    results: list[BenchmarkResult] = field(default_factory=list)

    def add_result(self, result: BenchmarkResult):
        self.results.append(result)

    def get_summary(self) -> dict:
        if not self.results:
            return {"error": "No results"}

        total_tests = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        total_time = sum(r.execution_time for r in self.results)
        avg_quality = sum(r.quality_score for r in self.results) / total_tests

        return {
            "suite_name": self.suite_name,
            "total_tests": total_tests,
            "passed": passed,
            "failed": total_tests - passed,
            "pass_rate": round(passed / total_tests * 100, 1),
            "total_time_seconds": round(total_time, 2),
            "avg_quality_score": round(avg_quality, 1),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# Predefined benchmark tests
BENCHMARK_TESTS = {
    "sirene_basic": {
        "name": "Recherche SIRENE basique",
        "description": "Test de recherche simple dans la base SIRENE",
        "tool": "sirene_search",
        "params": {"query": "startup tech Lille", "limite": 10},
        "expected_min_results": 5,
        "timeout": 30,
    },
    "sirene_advanced": {
        "name": "Recherche SIRENE avancée",
        "description": "Test de recherche avec filtres complexes",
        "tool": "sirene_search",
        "params": {"query": "intelligence artificielle Paris", "limite": 50},
        "expected_min_results": 20,
        "timeout": 60,
    },
    "geocoding": {
        "name": "Géocodage BAN",
        "description": "Test de géocodage d'adresses",
        "tool": "geocode_address",
        "params": {"address": "1 rue de la République, Lille"},
        "expected_min_results": 1,
        "timeout": 15,
    },
    "news_search": {
        "name": "Recherche actualités",
        "description": "Test de recherche d'actualités économiques",
        "tool": "news_search",
        "params": {"query": "startup levée de fonds", "limit": 10},
        "expected_min_results": 3,
        "timeout": 30,
    },
    "bodacc_search": {
        "name": "Recherche BODACC",
        "description": "Test de recherche dans les annonces légales",
        "tool": "bodacc_search",
        "params": {"query": "création entreprise Lille"},
        "expected_min_results": 1,
        "timeout": 30,
    },
    "market_analysis": {
        "name": "Analyse de marché complète",
        "description": "Test de l'analyse multi-sources",
        "tool": "tawiza_analyze_market",
        "params": {"query": "conseil IT Lyon", "limit": 20},
        "expected_min_results": 10,
        "timeout": 120,
    },
    "comparison": {
        "name": "Comparaison territoires",
        "description": "Test de comparaison multi-territoires",
        "tool": "tawiza_compare_markets",
        "params": {"query": "tech", "territories": ["Lille", "Lyon"]},
        "expected_min_results": 2,
        "timeout": 180,
    },
    "prospect": {
        "name": "Prospection",
        "description": "Test du pipeline de prospection",
        "tool": "tawiza_prospect",
        "params": {"query": "startup SaaS Bordeaux", "limit": 10},
        "expected_min_results": 5,
        "timeout": 120,
    },
}


def register_benchmark_tools(mcp: FastMCP) -> None:
    """Register benchmark tools on the MCP server."""

    @mcp.tool()
    async def tawiza_benchmark_run(
        tests: list[str] | None = None,
        quick_mode: bool = True,
        ctx: Context = None,
    ) -> str:
        """Execute une suite de tests de benchmark sur les outils Tawiza.

        Mesure la performance, la qualité et la fiabilité des différents
        outils d'intelligence territoriale.

        Args:
            tests: Liste des tests à exécuter. Si vide, exécute tous les tests.
                   Tests disponibles: sirene_basic, sirene_advanced, geocoding,
                   news_search, bodacc_search, market_analysis, comparison, prospect
            quick_mode: Si True, exécute seulement les tests rapides (< 60s)

        Returns:
            Rapport de benchmark avec scores et métriques
        """

        def notify(msg: str, progress: int = None):
            if ctx:
                try:
                    ctx.info(msg)
                    if progress is not None:
                        ctx.report_progress(progress, 100, msg)
                except Exception as e:
                    logger.debug(f"Failed to send notification: {e}")
                    pass

        notify("[Benchmark] Démarrage...", 0)

        suite = BenchmarkSuite(
            suite_name="Tawiza Benchmark",
            started_at=datetime.now(),
        )

        # Select tests to run
        if tests:
            selected_tests = {k: v for k, v in BENCHMARK_TESTS.items() if k in tests}
        else:
            selected_tests = BENCHMARK_TESTS

        # Filter by quick mode
        if quick_mode:
            selected_tests = {k: v for k, v in selected_tests.items() if v["timeout"] <= 60}

        if not selected_tests:
            return json.dumps(
                {
                    "success": False,
                    "error": "Aucun test sélectionné",
                },
                ensure_ascii=False,
            )

        notify(f"[Benchmark] {len(selected_tests)} tests sélectionnés", 5)

        # Import tools for testing
        try:
            from src.infrastructure.agents.camel.tools.territorial_tools import (
                bodacc_search,
                geocode_address,
                news_search,
                sirene_search,
            )
        except ImportError as e:
            logger.error(f"Import error: {e}")
            return json.dumps(
                {
                    "success": False,
                    "error": f"Erreur import: {e}",
                },
                ensure_ascii=False,
            )

        # Map tool names to functions
        tool_functions = {
            "sirene_search": sirene_search,
            "geocode_address": geocode_address,
            "news_search": news_search,
            "bodacc_search": bodacc_search,
        }

        # Run tests
        test_items = list(selected_tests.items())
        for i, (_test_id, test_config) in enumerate(test_items):
            progress = 10 + int((i / len(test_items)) * 80)
            notify(f"[Benchmark] Test: {test_config['name']}", progress)

            result = BenchmarkResult(
                test_name=test_config["name"],
                tool_name=test_config["tool"],
                success=False,
                execution_time=0,
                quality_score=0,
                data_count=0,
            )

            # Get the tool function
            tool_func = tool_functions.get(test_config["tool"])

            if not tool_func:
                result.errors.append(f"Tool non disponible: {test_config['tool']}")
                suite.add_result(result)
                continue

            # Execute test
            start_time = time.time()
            try:
                # Run with timeout
                test_result = await asyncio.wait_for(
                    asyncio.to_thread(tool_func, **test_config["params"]),
                    timeout=test_config["timeout"],
                )

                execution_time = time.time() - start_time
                result.execution_time = round(execution_time, 2)

                # Analyze result
                if isinstance(test_result, dict):
                    if test_result.get("success", False):
                        result.success = True

                        # Count data items
                        data_keys = ["enterprises", "results", "data", "items", "entries"]
                        for key in data_keys:
                            if key in test_result and isinstance(test_result[key], list):
                                result.data_count = len(test_result[key])
                                break

                        # Calculate quality score
                        expected_min = test_config["expected_min_results"]
                        if result.data_count >= expected_min:
                            result.quality_score = 100
                        elif result.data_count > 0:
                            result.quality_score = (result.data_count / expected_min) * 100
                        else:
                            result.quality_score = 50  # Success but no data

                        result.metadata = {
                            "expected_min": expected_min,
                            "actual_count": result.data_count,
                        }
                    else:
                        result.errors.append(test_result.get("error", "Échec sans message"))
                else:
                    result.errors.append("Résultat inattendu")

            except TimeoutError:
                result.execution_time = test_config["timeout"]
                result.errors.append(f"Timeout après {test_config['timeout']}s")
            except Exception as e:
                result.execution_time = time.time() - start_time
                result.errors.append(str(e))

            suite.add_result(result)

        suite.completed_at = datetime.now()
        notify("[Benchmark] Terminé", 100)

        # Generate report
        summary = suite.get_summary()

        report_md = f"""# Rapport de Benchmark Tawiza

**Date**: {summary["started_at"]}
**Durée totale**: {summary["total_time_seconds"]}s

## Résumé

| Métrique | Valeur |
|----------|--------|
| Tests exécutés | {summary["total_tests"]} |
| Réussis | {summary["passed"]} |
| Échoués | {summary["failed"]} |
| Taux de réussite | {summary["pass_rate"]}% |
| Score qualité moyen | {summary["avg_quality_score"]}/100 |

## Détail des Tests

| Test | Outil | Succès | Temps | Score | Données |
|------|-------|--------|-------|-------|---------|
"""
        for r in suite.results:
            status = "✅" if r.success else "❌"
            report_md += f"| {r.test_name} | {r.tool_name} | {status} | {r.execution_time}s | {r.quality_score:.0f} | {r.data_count} |\n"

        if any(r.errors for r in suite.results):
            report_md += "\n## Erreurs\n\n"
            for r in suite.results:
                if r.errors:
                    report_md += f"### {r.test_name}\n"
                    for err in r.errors:
                        report_md += f"- {err}\n"

        report_md += f"""
---
*Benchmark Tawiza - {len(suite.results)} tests*
"""

        return json.dumps(
            {
                "success": True,
                "summary": summary,
                "results": [r.to_dict() for r in suite.results],
                "report_md": report_md,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    @mcp.tool()
    async def tawiza_benchmark_list(ctx: Context = None) -> str:
        """Liste les tests de benchmark disponibles.

        Returns:
            Liste des tests avec descriptions et configurations
        """
        tests_list = []
        for test_id, config in BENCHMARK_TESTS.items():
            tests_list.append(
                {
                    "id": test_id,
                    "name": config["name"],
                    "description": config["description"],
                    "tool": config["tool"],
                    "timeout_seconds": config["timeout"],
                    "expected_min_results": config["expected_min_results"],
                }
            )

        quick_tests = [t for t in tests_list if t["timeout_seconds"] <= 60]
        full_tests = [t for t in tests_list if t["timeout_seconds"] > 60]

        return json.dumps(
            {
                "success": True,
                "total_tests": len(tests_list),
                "quick_tests": quick_tests,
                "full_tests": full_tests,
                "usage": "tawiza_benchmark_run(tests=['sirene_basic', 'geocoding'], quick_mode=True)",
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def tawiza_benchmark_tool(
        tool_name: str,
        iterations: int = 3,
        ctx: Context = None,
    ) -> str:
        """Benchmark un outil spécifique avec plusieurs itérations.

        Mesure la performance moyenne et la stabilité d'un outil.

        Args:
            tool_name: Nom de l'outil à tester (sirene_search, geocode_address, etc.)
            iterations: Nombre d'itérations (1-10)

        Returns:
            Métriques de performance: temps moyen, min, max, écart-type
        """
        if ctx:
            ctx.info(f"[Benchmark] Testing {tool_name} x{iterations}")

        iterations = max(1, min(10, iterations))

        # Import tools
        try:
            from src.infrastructure.agents.camel.tools.territorial_tools import (
                bodacc_search,
                geocode_address,
                news_search,
                sirene_search,
            )
        except ImportError as e:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Import error: {e}",
                },
                ensure_ascii=False,
            )

        # Tool configs
        tool_configs = {
            "sirene_search": {
                "func": sirene_search,
                "params": {"query": "tech Lille", "limite": 20},
            },
            "geocode_address": {
                "func": geocode_address,
                "params": {"address": "1 rue de la République, Lille"},
            },
            "news_search": {
                "func": news_search,
                "params": {"query": "startup tech", "limit": 10},
            },
            "bodacc_search": {
                "func": bodacc_search,
                "params": {"query": "création Lille"},
            },
        }

        if tool_name not in tool_configs:
            return json.dumps(
                {
                    "success": False,
                    "error": f"Outil inconnu: {tool_name}. Disponibles: {list(tool_configs.keys())}",
                },
                ensure_ascii=False,
            )

        config = tool_configs[tool_name]
        times = []
        successes = 0
        data_counts = []

        for i in range(iterations):
            if ctx:
                ctx.info(f"[Benchmark] Iteration {i + 1}/{iterations}")

            start = time.time()
            try:
                result = await asyncio.to_thread(config["func"], **config["params"])
                elapsed = time.time() - start
                times.append(elapsed)

                if isinstance(result, dict) and result.get("success"):
                    successes += 1
                    # Try to get data count
                    for key in ["enterprises", "results", "data"]:
                        if key in result and isinstance(result[key], list):
                            data_counts.append(len(result[key]))
                            break

            except Exception as e:
                times.append(time.time() - start)
                logger.error(f"Iteration {i + 1} failed: {e}")

            await asyncio.sleep(0.5)  # Small delay between iterations

        # Calculate stats
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            std_dev = (sum((t - avg_time) ** 2 for t in times) / len(times)) ** 0.5
        else:
            avg_time = min_time = max_time = std_dev = 0

        avg_data = sum(data_counts) / len(data_counts) if data_counts else 0

        return json.dumps(
            {
                "success": True,
                "tool": tool_name,
                "iterations": iterations,
                "success_rate": round(successes / iterations * 100, 1),
                "timing": {
                    "avg_seconds": round(avg_time, 3),
                    "min_seconds": round(min_time, 3),
                    "max_seconds": round(max_time, 3),
                    "std_dev": round(std_dev, 3),
                },
                "data": {
                    "avg_items": round(avg_data, 1),
                },
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.tool()
    async def tawiza_benchmark_compare(
        tools: list[str],
        ctx: Context = None,
    ) -> str:
        """Compare les performances de plusieurs outils.

        Args:
            tools: Liste des outils à comparer

        Returns:
            Tableau comparatif des performances
        """
        if ctx:
            ctx.info(f"[Benchmark] Comparing {len(tools)} tools")

        results = []
        for tool_name in tools:
            result = await tawiza_benchmark_tool(
                tool_name=tool_name,
                iterations=2,
                ctx=ctx,
            )
            data = json.loads(result)
            if data.get("success"):
                results.append(
                    {
                        "tool": tool_name,
                        "success_rate": data["success_rate"],
                        "avg_time": data["timing"]["avg_seconds"],
                        "avg_data": data["data"]["avg_items"],
                    }
                )
            else:
                results.append(
                    {
                        "tool": tool_name,
                        "error": data.get("error", "Failed"),
                    }
                )

        # Sort by avg time
        results.sort(key=lambda x: x.get("avg_time", 999))

        report_md = """# Comparaison Performance Outils

| Outil | Taux Succès | Temps Moyen | Données Moy. |
|-------|-------------|-------------|--------------|
"""
        for r in results:
            if "error" in r:
                report_md += f"| {r['tool']} | ❌ | - | {r['error']} |\n"
            else:
                report_md += (
                    f"| {r['tool']} | {r['success_rate']}% | {r['avg_time']}s | {r['avg_data']} |\n"
                )

        return json.dumps(
            {
                "success": True,
                "comparison": results,
                "report_md": report_md,
            },
            ensure_ascii=False,
            indent=2,
        )
