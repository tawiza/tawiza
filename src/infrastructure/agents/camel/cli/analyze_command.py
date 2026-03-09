"""CLI command for territorial market analysis using Camel AI.

Supports multiple depth levels:
- quick: Fast Sirene search + basic report
- standard: + Map + CSV export
- full: + Web enrichment + Graph + JSONL
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from src.cli.v2.ui.theme import footer, header

console = Console()

DepthLevel = Literal["quick", "standard", "full"]


def analyze_command(
    query: str = typer.Argument(..., help="Analysis query (e.g., 'marché conseil IT Lille')"),
    output: str = typer.Option("./outputs/analyses", "--output", "-o", help="Output directory"),
    model: str = typer.Option("qwen3.5:27b", "--model", "-m", help="Ollama model to use"),
    depth: str = typer.Option("standard", "--depth", "-d", help="Analysis depth: quick, standard, full"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max enterprises to analyze"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed progress"),
    use_agents: bool = typer.Option(False, "--use-agents", "-a", help="Use Camel AI multi-agent orchestration"),
    multi_source: bool = typer.Option(False, "--multi-source", "-M", help="Use parallel multi-source orchestration with validation"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Enter interactive mode after analysis"),
):
    """Analyze a territorial market using Camel AI multi-agent system.

    Depth levels:
    - quick: Fast search + basic report (10s)
    - standard: + Map + CSV export (30s)
    - full: + Web enrichment + Graph + JSONL annotation format (2-5min)

    Modes:
    - Default: Direct tool execution (faster, predictable)
    - --use-agents: Camel AI multi-agent orchestration (smarter, autonomous)
    - --multi-source: Parallel queries to 8 sources + multi-agent validation
    - --interactive: Continue with follow-up questions after analysis

    [bold]Examples:[/]
      tawiza analyze "conseil IT Lille"
      tawiza analyze "startups IA Hauts-de-France" --depth full
      tawiza analyze "startups IA Lille" --use-agents -v
      tawiza analyze "startup IA Lille" --multi-source  # Multi-source + validation
      tawiza analyze "conseil IT Lyon" -i  # Interactive follow-ups
    """
    # Create timestamped output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    query_slug = query[:30].replace(" ", "_").replace("/", "-")
    output_dir = f"{output}/{timestamp}_{query_slug}"

    if multi_source:
        result = asyncio.run(_orchestrated_analysis(
            query=query,
            output_dir=output_dir,
            limit=limit,
            verbose=verbose,
        ))
    elif use_agents:
        result = asyncio.run(_agent_analysis(
            query=query,
            output_dir=output_dir,
            model=model,
            verbose=verbose,
        ))
    else:
        result = asyncio.run(_run_analysis(
            query=query,
            output_dir=output_dir,
            model=model,
            depth=depth,
            limit=limit,
            verbose=verbose,
        ))

    # Enter interactive mode if requested
    if interactive and result and result.get("success"):
        asyncio.run(_interactive_mode(result, output_dir, model, verbose))


async def _run_analysis(
    query: str,
    output_dir: str,
    model: str,
    depth: str,
    limit: int,
    verbose: bool,
) -> dict:
    """Run the territorial analysis with specified depth."""
    from src.cli.v2.ui.components import MessageBox

    msg = MessageBox()

    # Header
    console.print(header("analyze", 55))
    console.print()
    console.print(f"  [bold]Query:[/] {query}")
    console.print(f"  [dim]Depth: {depth} | Limit: {limit} | Model: {model}[/]")
    console.print(footer(55))
    console.print()

    # Check Ollama availability
    try:
        from src.infrastructure.llm.ollama_client import OllamaClient
        ollama = OllamaClient(model=model)
        healthy = await ollama.health_check()
        if not healthy:
            console.print(msg.error(
                "Ollama not available",
                ["Start with: ollama serve", "Or: tawiza pro ollama-start"]
            ))
            return {"success": False}
    except Exception as e:
        console.print(msg.error("Failed to connect to Ollama", [str(e)]))
        return {"success": False}

    console.print("  [green]✓[/] Ollama connected")

    # Run analysis based on depth
    try:
        if depth == "quick":
            result = await _quick_analysis(query, output_dir, limit, verbose)
        elif depth == "standard":
            result = await _standard_analysis(query, output_dir, limit, verbose)
        else:  # full
            result = await _full_analysis(query, output_dir, limit, verbose)

        # Store query and depth for interactive mode
        result["query"] = query
        result["depth"] = depth

        # Display results
        if result.get("success"):
            _display_results(result, depth)
        else:
            console.print(msg.error("Analysis failed", [result.get("error", "Unknown error")]))

        return result

    except Exception as e:
        console.print()
        console.print(msg.error("Analysis failed", [str(e)]))
        if verbose:
            import traceback
            console.print(f"  [dim]{traceback.format_exc()}[/]")
        return {"success": False}


async def _quick_analysis(query: str, output_dir: str, limit: int, verbose: bool) -> dict:
    """Quick analysis: Sirene search + basic report."""
    from src.cli.v2.agents.tools import register_all_tools
    from src.cli.v2.agents.unified.tools import ToolRegistry

    registry = ToolRegistry()
    register_all_tools(registry)

    results = {"success": False, "enterprises": [], "outputs": {}}

    console.print("  [cyan]►[/] Searching enterprises...")

    search_result = await registry.execute('sirene.search', {
        'query': query,
        'limite': limit,
    })
    enterprises = search_result.get("enterprises", [])
    results["enterprises"] = enterprises
    results["enterprises_count"] = len(enterprises)

    if verbose:
        console.print(f"    [dim]Found {len(enterprises)} enterprises[/]")

    # Create output directory and save basic report
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save JSON
    import json
    json_file = output_path / "data.json"
    json_file.write_text(json.dumps({
        "query": query,
        "depth": "quick",
        "enterprises_count": len(enterprises),
        "enterprises": enterprises,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    results["outputs"]["json"] = str(json_file)

    results["report_dir"] = str(output_path)
    results["success"] = True
    return results


async def _standard_analysis(query: str, output_dir: str, limit: int, verbose: bool) -> dict:
    """Standard analysis: Sirene + Map + CSV + Report."""
    from src.cli.v2.agents.tools import register_all_tools
    from src.cli.v2.agents.unified.tools import ToolRegistry
    from src.infrastructure.agents.camel.services.output_pipeline import generate_all_outputs

    registry = ToolRegistry()
    register_all_tools(registry)

    results = {"success": False, "enterprises": [], "outputs": {}}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=not verbose,
    ) as progress:
        # Step 1: Search
        task = progress.add_task("  [1/3] Searching enterprises...", total=None)
        search_result = await registry.execute('sirene.search', {
            'query': query,
            'limite': limit,
        })
        enterprises = search_result.get("enterprises", [])
        results["enterprises"] = enterprises
        results["enterprises_count"] = len(enterprises)

        if verbose:
            console.print(f"    [dim]Found {len(enterprises)} enterprises[/]")

        # Step 2: Generate map
        progress.update(task, description="  [2/3] Generating map...")
        map_file = None

        locations = []
        for e in enterprises:
            geo = e.get("geo")
            if geo and geo.get("lat"):
                locations.append({
                    "nom": e["nom"],
                    "lat": geo["lat"],
                    "lon": geo["lon"],
                    "type": "entreprise",
                    "effectif": e.get("effectif"),
                    "commune": e.get("adresse", {}).get("commune"),
                })

        if locations:
            # Save map in the analysis output directory
            from pathlib import Path
            map_output_dir = Path(output_dir) / "maps"
            map_output_dir.mkdir(parents=True, exist_ok=True)
            map_output_path = str(map_output_dir / "carte.html")

            map_result = await registry.execute('geo.map', {
                'locations': locations,
                'title': f"Analyse: {query[:30]}",
                'output_path': map_output_path,
            })
            if map_result.get("success"):
                map_file = map_result.get("file_path")
                results["outputs"]["map"] = map_file

        # Step 3: Generate outputs
        progress.update(task, description="  [3/3] Generating outputs...")

        outputs = await generate_all_outputs(
            enterprises=enterprises,
            query=query,
            output_dir=output_dir,
            map_file=map_file,
            formats=['csv', 'md'],
        )
        results["outputs"].update(outputs)
        progress.update(task, description="  [green]✓[/] Analysis complete")

    results["report_dir"] = output_dir
    results["success"] = True
    return results


async def _full_analysis(query: str, output_dir: str, limit: int, verbose: bool) -> dict:
    """Full analysis: Standard + Web enrichment + Graph + JSONL."""
    from src.cli.v2.agents.tools import register_all_tools
    from src.cli.v2.agents.unified.tools import ToolRegistry
    from src.infrastructure.agents.camel.services.output_pipeline import generate_all_outputs
    from src.infrastructure.agents.camel.services.query_parser import QueryParser
    from src.infrastructure.agents.camel.services.skyvern_enrichment import SkyvernEnrichmentService

    registry = ToolRegistry()
    register_all_tools(registry)

    results = {"success": False, "enterprises": [], "enrichments": [], "outputs": {}}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
        refresh_per_second=4,
    ) as progress:
        # Step 0: Parse query with intelligent parser
        parser = QueryParser(use_llm_fallback=True)
        parsed = await parser.parse(query)

        if verbose:
            console.print(f"    [dim]Parsed: {len(parsed.keywords)} keywords, {len(parsed.naf_codes)} NAF codes, region={parsed.region}[/]")
            if parsed.used_llm:
                console.print("    [dim]Used LLM fallback[/]")

        # Step 1: Search enterprises with multiple strategies
        search_task = progress.add_task("  [1/5] Searching enterprises...", total=len(parsed.search_strategies) or 1)

        all_enterprises = []
        seen_sirets = set()

        # Execute each search strategy
        for i, strategy in enumerate(parsed.search_strategies):
            search_result = await registry.execute('sirene.search', {
                'query': strategy['query'],
                'region': parsed.region,
                'activite': strategy.get('naf'),
                'limite': max(5, limit // max(len(parsed.search_strategies), 1)),
            })

            for e in search_result.get("enterprises", []):
                siret = e.get("siret")
                if siret and siret not in seen_sirets:
                    seen_sirets.add(siret)
                    all_enterprises.append(e)

            progress.update(search_task, completed=i + 1)

        # If no strategies, try direct query as fallback
        if not parsed.search_strategies:
            search_result = await registry.execute('sirene.search', {
                'query': query,
                'limite': limit,
            })
            all_enterprises = search_result.get("enterprises", [])
            progress.update(search_task, completed=1)

        # Limit to requested amount
        enterprises = all_enterprises[:limit]
        results["enterprises"] = enterprises
        results["enterprises_count"] = len(enterprises)
        results["parsed_query"] = {
            "keywords": parsed.keywords,
            "naf_codes": parsed.naf_codes,
            "region": parsed.region,
            "strategies_count": len(parsed.search_strategies),
            "used_llm": parsed.used_llm,
        }

        if verbose:
            console.print(f"    [dim]Found {len(enterprises)} enterprises (from {len(parsed.search_strategies)} strategies)[/]")

        # Step 2: Web enrichment (do this BEFORE map so we can include URLs in popups)
        enrich_task = progress.add_task(
            f"  [2/5] Enriching {min(len(enterprises), 10)} enterprises...",
            total=min(len(enterprises), 10)
        )

        enrichment_service = SkyvernEnrichmentService(max_concurrent=2, use_playwright=False)
        enrichments = []

        # Limit enrichment to first 10 for speed
        enterprises_to_enrich = enterprises[:10]

        def progress_callback(current, total):
            progress.update(enrich_task, completed=current)

        try:
            enrichments = await enrichment_service.enrich_batch(
                enterprises_to_enrich,
                progress_callback=progress_callback
            )
            results["enrichments"] = [e.to_dict() for e in enrichments]

            # Count successful enrichments
            successful = sum(1 for e in enrichments if e.url_found)
            if verbose:
                console.print(f"    [dim]Enriched {successful}/{len(enrichments)} enterprises[/]")

        except Exception as e:
            if verbose:
                console.print(f"    [yellow]Enrichment partial: {e}[/]")
            progress.update(enrich_task, completed=len(enterprises_to_enrich))

        # Step 3: Generate map WITH enrichment data
        map_task = progress.add_task("  [3/5] Generating map...", total=1)
        map_file = None

        # Build enrichment lookup for quick access
        enrichment_by_siret = {e.siret: e for e in enrichments if e.siret}

        if verbose:
            console.print(f"    [dim]Building map with {len(enterprises)} enterprises, {len(enrichment_by_siret)} enriched[/]")

        # Build locations with enriched data for rich popups
        locations = []
        for e in enterprises:
            geo = e.get("geo")
            if geo and geo.get("lat"):
                siret = e.get("siret", "")
                enr = enrichment_by_siret.get(siret)

                loc = {
                    "nom": e["nom"],
                    "lat": geo["lat"],
                    "lon": geo["lon"],
                    "type": "entreprise",
                    "effectif": e.get("effectif"),
                    "commune": e.get("adresse", {}).get("commune"),
                }

                # Add enrichment data if available
                if enr:
                    loc["url"] = enr.url_found
                    loc["description"] = enr.description
                    loc["technologies"] = enr.technologies
                    loc["quality"] = enr.enrichment_quality

                locations.append(loc)

        if verbose:
            console.print(f"    [dim]Valid locations for map: {len(locations)}[/]")

        if locations:
            # Save map in the analysis output directory
            map_output_dir = Path(output_dir) / "maps"
            map_output_dir.mkdir(parents=True, exist_ok=True)
            map_output_path = str(map_output_dir / "carte.html")

            map_result = await registry.execute('geo.map', {
                'locations': locations,
                'title': f"Analyse: {query[:30]}",
                'output_path': map_output_path,
            })
            if map_result.get("success"):
                map_file = map_result.get("file_path")
                results["outputs"]["map"] = map_file
                if verbose:
                    console.print(f"    [dim]Map generated: {map_file}[/]")
            else:
                if verbose:
                    console.print(f"    [yellow]Map generation failed: {map_result.get('error', 'unknown')}[/]")
        else:
            if verbose:
                console.print("    [yellow]No valid locations for map[/]")

        progress.update(map_task, completed=1)

        # Step 4: Generate graph
        graph_task = progress.add_task("  [4/5] Building relation graph...", total=1)

        # Graph will be generated by output pipeline
        progress.update(graph_task, completed=1)

        # Step 5: Generate all outputs
        output_task = progress.add_task("  [5/5] Generating outputs...", total=1)

        outputs = await generate_all_outputs(
            enterprises=enterprises,
            query=query,
            output_dir=output_dir,
            enrichments=enrichments if enrichments else None,
            map_file=map_file,
            formats=['csv', 'jsonl', 'md', 'html'],
        )
        results["outputs"].update(outputs)
        progress.update(output_task, completed=1)

    results["report_dir"] = output_dir
    results["success"] = True
    return results


async def _orchestrated_analysis(
    query: str,
    output_dir: str,
    limit: int,
    verbose: bool,
) -> dict:
    """Multi-source orchestrated analysis with debate validation.

    Uses DataOrchestrator to query 8 sources in parallel:
    - Sirene (INSEE)
    - BAN (geocoding)
    - BODACC (legal announcements)
    - BOAMP (public contracts)
    - GDELT (news)
    - Google News RSS
    - Data.gouv Subventions

    Then validates with DebateSystem (3-agent validation):
    - Chercheur: Analyzes collected data
    - Critique: Questions and identifies issues
    - Vérificateur: Cross-validates and provides verdict
    """
    import json
    from pathlib import Path

    from src.application.orchestration.data_orchestrator import DataOrchestrator
    from src.application.reporting.orchestrated_report import generate_orchestrated_report
    from src.cli.v2.ui.components import MessageBox
    from src.domain.debate.debate_system import DebateSystem
    from src.infrastructure.llm import create_debate_system_with_llm

    msg = MessageBox()
    results = {"success": False, "enterprises": [], "outputs": {}}

    # Header
    console.print(header("analyze [multi-source]", 55))
    console.print()
    console.print(f"  [bold]Query:[/] {query}")
    console.print("  [dim]Mode: 8-Source Orchestration + LLM Debate (qwen3.5:27b)[/]")
    console.print(footer(55))
    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=not verbose,
        ) as progress:
            # Step 1: Multi-source search
            search_task = progress.add_task("  [1/3] Querying 8 sources in parallel...", total=None)

            orchestrator = DataOrchestrator()
            orch_result = await orchestrator.search(
                query=query,
                limit_per_source=limit,
            )

            if verbose:
                console.print(f"    [dim]Total results: {orch_result.total_results} in {orch_result.total_duration_ms:.0f}ms[/]")
                for sr in orch_result.source_results:
                    status = f"[green]{len(sr.results)}[/]" if sr.results else f"[red]{sr.error or '0'}[/]"
                    console.print(f"    [dim]  {sr.source}: {status}[/]")

            progress.update(search_task, description="  [green]✓[/] Sources queried")

            # Step 2: Debate validation with LLM
            debate_task = progress.add_task("  [2/3] Running LLM-powered validation...", total=None)

            # Try to use LLM-enhanced debate, fallback to rule-based if Ollama unavailable
            try:
                debate = create_debate_system_with_llm(text_model="qwen3.5:27b")
                if verbose:
                    console.print("    [dim]Using LLM-enhanced debate (qwen3.5:27b)[/]")
            except Exception as llm_err:
                if verbose:
                    console.print(f"    [dim]LLM unavailable, using rule-based: {llm_err}[/]")
                debate = DebateSystem()

            debate_result = await debate.validate(
                query=query,
                data={
                    "results": [item for sr in orch_result.source_results for item in sr.results],
                    "sources": [sr.source for sr in orch_result.source_results],
                },
            )

            if verbose:
                for msg_item in debate_result.messages:
                    icon = {"researcher": "🔍", "critic": "🎯", "verifier": "✅"}.get(msg_item.role, "•")
                    console.print(f"    [dim]{icon} {msg_item.agent}: {msg_item.confidence}%[/]")

            progress.update(debate_task, description="  [green]✓[/] Validation complete")

            # Step 3: Generate map with geocoding
            map_task = progress.add_task("  [3/4] Generating map...", total=None)

            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # Extract locations from results - with and without geo coordinates
            from src.cli.v2.agents.tools import register_all_tools
            from src.cli.v2.agents.unified.tools import ToolRegistry

            registry = ToolRegistry()
            register_all_tools(registry)

            locations = []
            addresses_to_geocode = []  # Addresses without coordinates
            all_results = [item for sr in orch_result.source_results for item in sr.results]

            for item in all_results:
                geo = item.get("geo")
                name = item.get("nom") or item.get("name") or item.get("title", "N/A")

                if geo and geo.get("lat"):
                    # Already has coordinates
                    locations.append({
                        "nom": name,
                        "lat": geo["lat"],
                        "lon": geo["lon"],
                        "type": "entreprise",
                        "effectif": item.get("effectif"),
                        "commune": item.get("adresse", {}).get("commune") if isinstance(item.get("adresse"), dict) else None,
                        "source": item.get("source", "unknown"),
                    })
                else:
                    # Try to extract address for geocoding
                    address = None
                    adresse = item.get("adresse")
                    if isinstance(adresse, dict):
                        # Build address string from components
                        parts = []
                        if adresse.get("numero"):
                            parts.append(adresse["numero"])
                        if adresse.get("voie"):
                            parts.append(adresse["voie"])
                        elif adresse.get("rue"):
                            parts.append(adresse["rue"])
                        if adresse.get("code_postal"):
                            parts.append(adresse["code_postal"])
                        if adresse.get("commune"):
                            parts.append(adresse["commune"])
                        if parts:
                            address = " ".join(parts)
                    elif isinstance(adresse, str) and len(adresse) > 5:
                        address = adresse
                    elif item.get("address"):
                        address = item.get("address")
                    elif item.get("location"):
                        address = item.get("location")

                    if address and name != "N/A":
                        addresses_to_geocode.append({
                            "address": address,
                            "name": name,
                            "item": item,
                        })

            # Geocode addresses without coordinates (max 30 to avoid slowdown)
            if addresses_to_geocode and verbose:
                console.print(f"    [dim]Geocoding {min(len(addresses_to_geocode), 30)} addresses...[/]")

            for addr_info in addresses_to_geocode[:30]:
                try:
                    geo_result = await registry.execute('geo.locate', {'address': addr_info["address"]})
                    if geo_result.get("success") and geo_result.get("lat"):
                        item = addr_info["item"]
                        locations.append({
                            "nom": addr_info["name"],
                            "lat": geo_result["lat"],
                            "lon": geo_result["lon"],
                            "type": "entreprise",
                            "effectif": item.get("effectif"),
                            "commune": geo_result.get("address_details", {}).get("commune"),
                            "source": item.get("source", "geocoded"),
                        })
                except Exception:
                    pass  # Skip failed geocoding

            map_file = None
            if locations:
                map_output_dir = output_path / "maps"
                map_output_dir.mkdir(parents=True, exist_ok=True)
                map_output_path = str(map_output_dir / "carte.html")

                map_result = await registry.execute('geo.map', {
                    'locations': locations,
                    'title': f"Analyse Multi-Source: {query[:30]}",
                    'output_path': map_output_path,
                })
                if map_result.get("success"):
                    map_file = map_result.get("file_path")
                    results["outputs"]["map"] = map_file
                    if verbose:
                        console.print(f"    [dim]Map: {len(locations)} locations[/]")
            elif verbose:
                console.print("    [dim]No locations to map (no addresses found)[/]")

            progress.update(map_task, description=f"  [green]✓[/] Map: {len(locations)} locations")

            # Step 4: Generate reports
            output_task = progress.add_task("  [4/4] Generating reports...", total=None)

            # Generate enhanced HTML report + JSON export + Markdown
            report_outputs = await generate_orchestrated_report(
                query=query,
                output_dir=output_dir,
                orch_result=orch_result,
                debate_result=debate_result,
                theme="dark",
            )
            results["outputs"].update(report_outputs)

            # Also save raw orchestration data
            orch_file = output_path / "orchestration.json"
            orch_file.write_text(
                json.dumps(orch_result.to_dict(), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            results["outputs"]["orchestration_raw"] = str(orch_file)

            # Extract enterprises from correlated entities
            enterprises = []
            for entity in orch_result.correlated_entities:
                if isinstance(entity, dict):
                    enterprises.append(entity)
                elif hasattr(entity, "items"):
                    enterprises.append(dict(entity.items()))

            results["enterprises"] = enterprises[:limit]
            results["enterprises_count"] = len(enterprises)

            progress.update(output_task, description="  [green]✓[/] Reports generated")

        # Display results
        console.print()
        console.print("  [green]✓[/] [bold]Multi-source analysis complete![/]")
        console.print()

        # Confidence display with color
        confidence = debate_result.final_confidence
        if confidence >= 80:
            conf_color = "green"
        elif confidence >= 60:
            conf_color = "yellow"
        else:
            conf_color = "red"

        console.print(f"  [bold]Confidence:[/] [{conf_color}]{confidence:.0f}%[/]")
        console.print(f"  [bold]Verdict:[/] {debate_result.verdict}")
        console.print()

        # Source stats table
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Source", width=15)
        table.add_column("Results", width=8)
        table.add_column("Duration", width=10)

        for sr in orch_result.source_results:
            count = f"[green]{len(sr.results)}[/]" if sr.results else "[red]0[/]"
            duration = f"{sr.duration_ms:.0f}ms"
            table.add_row(sr.source, count, duration)

        console.print(table)
        console.print()

        # Issues if any
        if debate_result.issues:
            console.print("  [yellow]Issues détectés:[/]")
            for issue in debate_result.issues[:3]:
                console.print(f"    ⚠️ {issue}")
            console.print()

        console.print(f"  [bold]Output directory:[/] {output_dir}")
        console.print()

        results["report_dir"] = output_dir
        results["confidence"] = confidence
        results["verdict"] = debate_result.verdict
        results["query"] = query
        results["depth"] = "multi-source"
        results["success"] = True

        return results

    except Exception as e:
        console.print()
        console.print(msg.error("Multi-source analysis failed", [str(e)]))
        if verbose:
            import traceback
            console.print(f"  [dim]{traceback.format_exc()}[/]")
        return {"success": False, "error": str(e)}


async def _agent_analysis(query: str, output_dir: str, model: str, verbose: bool) -> dict:
    """Run analysis using Camel AI multi-agent orchestration.

    This mode uses the TerritorialWorkforce which coordinates:
    - DataAgent: Collects enterprise data
    - GeoAgent: Creates maps
    - WebAgent: Enriches from websites
    - AnalystAgent: Generates reports
    """

    from src.cli.v2.ui.components import MessageBox
    from src.infrastructure.agents.camel.workforce.territorial_workforce import TerritorialWorkforce

    msg = MessageBox()

    # Header
    console.print(header("analyze [agents]", 55))
    console.print()
    console.print(f"  [bold]Query:[/] {query}")
    console.print(f"  [dim]Mode: Multi-Agent | Model: {model}[/]")
    console.print(footer(55))
    console.print()

    # Check Ollama
    try:
        from src.infrastructure.llm.ollama_client import OllamaClient
        ollama = OllamaClient(model=model)
        healthy = await ollama.health_check()
        if not healthy:
            console.print(msg.error("Ollama not available", ["Start with: ollama serve"]))
            return {"success": False}
    except Exception as e:
        console.print(msg.error("Failed to connect to Ollama", [str(e)]))
        return {"success": False}

    console.print("  [green]✓[/] Ollama connected")
    console.print()

    # Initialize workforce
    console.print("  [cyan]►[/] Initializing multi-agent workforce...")

    try:
        workforce = TerritorialWorkforce(
            model_id=model,
            enable_web_enrichment=True,
        )
        console.print("  [green]✓[/] Workforce ready (4 agents)")
    except Exception as e:
        console.print(msg.error("Failed to initialize workforce", [str(e)]))
        if verbose:
            import traceback
            console.print(f"  [dim]{traceback.format_exc()}[/]")
        return {"success": False}

    console.print()

    # Run analysis with live status
    console.print("  [bold cyan]🤖 Multi-Agent Analysis in progress...[/]")
    console.print()

    agents_status = {
        "DataAgent": "waiting",
        "GeoAgent": "waiting",
        "WebAgent": "waiting",
        "AnalystAgent": "waiting",
    }

    def render_agents():
        lines = []
        for agent, status in agents_status.items():
            if status == "running":
                icon = "[yellow]⚙[/]"
            elif status == "done":
                icon = "[green]✓[/]"
            elif status == "error":
                icon = "[red]✗[/]"
            else:
                icon = "[dim]○[/]"
            lines.append(f"     {icon} {agent}")
        return "\n".join(lines)

    try:
        # Show agents status
        console.print(render_agents())
        console.print()

        # Execute the workforce task
        result = await workforce.analyze_market(
            query=query,
            output_dir=output_dir,
        )

        console.print()
        console.print("  [green]✓[/] [bold]Multi-agent analysis complete![/]")
        console.print()

        # Display result
        if result.get("success"):
            console.print(f"  [bold]Output directory:[/] {output_dir}")
            if result.get("result"):
                console.print()
                console.print("  [bold]Agent Response:[/]")
                response_text = str(result.get("result", ""))[:500]
                console.print(f"  [dim]{response_text}...[/]")
        else:
            console.print(msg.error("Analysis failed", [result.get("error", "Unknown error")]))

        return result

    except Exception as e:
        console.print()
        console.print(msg.error("Multi-agent analysis failed", [str(e)]))
        if verbose:
            import traceback
            console.print(f"  [dim]{traceback.format_exc()}[/]")
        return {"success": False, "error": str(e)}


def _display_results(result: dict, depth: str):
    """Display analysis results."""
    console.print()
    console.print("  [green]✓[/] [bold]Analysis complete![/]")
    console.print()

    # Stats table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Label", style="dim", width=20)
    table.add_column("Value", style="bold")

    table.add_row("Enterprises", str(result.get("enterprises_count", 0)))
    table.add_row("Depth", depth)

    # Show enrichment stats for full mode
    if depth == "full" and result.get("enrichments"):
        enrichments = result["enrichments"]
        enriched = sum(1 for e in enrichments if e.get("url_found"))
        avg_quality = sum(e.get("enrichment_quality", 0) for e in enrichments) / max(len(enrichments), 1)
        table.add_row("Enriched", f"{enriched}/{len(enrichments)} ({avg_quality:.0%} quality)")

    console.print(table)
    console.print()

    # Output files
    outputs = result.get("outputs", {})
    if outputs:
        console.print("  [bold]Generated files:[/]")
        for fmt, path in outputs.items():
            icon = {
                "csv": "📊",
                "jsonl": "📝",
                "md": "📄",
                "map": "🗺️",
                "graph": "🔗",
            }.get(fmt, "📁")
            console.print(f"    {icon} {fmt}: {path}")
        console.print()

    # Top enterprises preview
    enterprises = result.get("enterprises", [])
    if enterprises:
        console.print("  [bold]Top entreprises:[/]")
        for i, e in enumerate(enterprises[:5], 1):
            commune = e.get("adresse", {}).get("commune", "?")
            effectif = e.get("effectif", "?")

            # Check if enriched
            enriched_marker = ""
            if depth == "full" and result.get("enrichments"):
                siret = e.get("siret", "")
                for enr in result["enrichments"]:
                    if enr.get("siret") == siret and enr.get("url_found"):
                        enriched_marker = " [cyan]●[/]"
                        break

            console.print(f"    {i}. {e['nom']} ({commune}, {effectif} sal.){enriched_marker}")

    if depth == "full":
        console.print()
        console.print("  [dim]● = enriched with web data[/]")

    console.print()


async def _interactive_mode(result: dict, output_dir: str, model: str, verbose: bool):
    """Interactive follow-up mode after analysis."""
    from rich.prompt import Prompt

    enterprises = result.get("enterprises", [])
    enrichments = result.get("enrichments", [])
    result.get("query", "")

    # Create enterprise lookup by name (case-insensitive)
    enterprise_by_name = {}
    for e in enterprises:
        name_lower = e.get("nom", "").lower()
        enterprise_by_name[name_lower] = e
        # Also add abbreviated names
        words = name_lower.split()
        if len(words) > 1:
            enterprise_by_name[words[0]] = e

    # Create enrichment lookup by siret
    enrichment_by_siret = {e.get("siret", ""): e for e in enrichments}

    console.print()
    console.print(Panel(
        "[bold cyan]Mode Interactif[/]\n\n"
        "Commandes disponibles:\n"
        "  [green]list[/]              - Liste des entreprises\n"
        "  [green]detail <n°|nom>[/]   - Détails d'une entreprise\n"
        "  [green]enrich <n°|nom>[/]   - Enrichir une entreprise\n"
        "  [green]filter <critère>[/]  - Filtrer (ex: effectif>50)\n"
        "  [green]export csv|json[/]   - Exporter les résultats\n"
        "  [green]ask <question>[/]    - Poser une question\n"
        "  [green]quit[/]              - Quitter",
        title="Analyse Interactive",
        border_style="cyan",
    ))

    while True:
        try:
            user_input = Prompt.ask("\n[cyan]>[/]", default="").strip()

            if not user_input:
                continue

            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ("quit", "exit", "q"):
                console.print("  [dim]Au revoir![/]")
                break

            elif cmd == "list":
                _interactive_list(enterprises, enrichment_by_siret)

            elif cmd == "detail":
                _interactive_detail(arg, enterprises, enterprise_by_name, enrichment_by_siret)

            elif cmd == "enrich":
                await _interactive_enrich(arg, enterprises, enterprise_by_name, enrichment_by_siret)

            elif cmd == "filter":
                _interactive_filter(arg, enterprises, enrichment_by_siret)

            elif cmd == "export":
                _interactive_export(arg, enterprises, enrichments, output_dir)

            elif cmd == "ask":
                await _interactive_ask(arg, enterprises, enrichments, model)

            elif cmd == "help":
                console.print("  [dim]Commandes: list, detail, enrich, filter, export, ask, quit[/]")

            else:
                console.print(f"  [yellow]Commande inconnue: {cmd}[/]")
                console.print("  [dim]Tapez 'help' pour l'aide[/]")

        except KeyboardInterrupt:
            console.print("\n  [dim]Au revoir![/]")
            break
        except Exception as e:
            console.print(f"  [red]Erreur: {e}[/]")


def _interactive_list(enterprises: list, enrichment_by_siret: dict):
    """List all enterprises."""
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", width=3)
    table.add_column("Nom", max_width=40)
    table.add_column("Ville")
    table.add_column("Eff.", width=5)
    table.add_column("Web", width=3)

    for i, e in enumerate(enterprises, 1):
        siret = e.get("siret", "")
        enriched = "●" if enrichment_by_siret.get(siret, {}).get("url_found") else ""
        table.add_row(
            str(i),
            e.get("nom", "")[:40],
            e.get("adresse", {}).get("commune", ""),
            str(e.get("effectif", "?")),
            f"[cyan]{enriched}[/]" if enriched else "",
        )

    console.print(table)


def _interactive_detail(arg: str, enterprises: list, enterprise_by_name: dict, enrichment_by_siret: dict):
    """Show detailed info for an enterprise."""
    enterprise = None

    # Try by number first
    if arg.isdigit():
        idx = int(arg) - 1
        if 0 <= idx < len(enterprises):
            enterprise = enterprises[idx]
    else:
        # Try by name
        enterprise = enterprise_by_name.get(arg.lower())

    if not enterprise:
        console.print(f"  [yellow]Entreprise non trouvée: {arg}[/]")
        return

    siret = enterprise.get("siret", "")
    enrichment = enrichment_by_siret.get(siret, {})

    console.print()
    console.print(f"  [bold]{enterprise.get('nom', '')}[/]")
    console.print(f"  SIRET: {siret}")

    addr = enterprise.get("adresse", {})
    console.print(f"  Adresse: {addr.get('rue', '')} {addr.get('code_postal', '')} {addr.get('commune', '')}")
    console.print(f"  Effectif: {enterprise.get('effectif', '?')} salariés")

    geo = enterprise.get("geo", {})
    if geo.get("lat"):
        console.print(f"  GPS: {geo['lat']}, {geo['lon']}")

    if enrichment.get("url_found"):
        console.print()
        console.print("  [cyan]Données enrichies:[/]")
        console.print(f"  Site web: {enrichment.get('url_found')}")
        if enrichment.get("description"):
            console.print(f"  Description: {enrichment['description'][:200]}...")
        if enrichment.get("contact"):
            console.print(f"  Contact: {enrichment['contact']}")
        if enrichment.get("social_media"):
            console.print(f"  Réseaux: {enrichment['social_media']}")
        if enrichment.get("technologies"):
            console.print(f"  Technologies: {', '.join(enrichment['technologies'])}")


async def _interactive_enrich(arg: str, enterprises: list, enterprise_by_name: dict, enrichment_by_siret: dict):
    """Enrich a specific enterprise."""
    from src.infrastructure.agents.camel.services.skyvern_enrichment import SkyvernEnrichmentService

    enterprise = None

    if arg.isdigit():
        idx = int(arg) - 1
        if 0 <= idx < len(enterprises):
            enterprise = enterprises[idx]
    else:
        enterprise = enterprise_by_name.get(arg.lower())

    if not enterprise:
        console.print(f"  [yellow]Entreprise non trouvée: {arg}[/]")
        return

    console.print(f"  [cyan]Enrichissement de {enterprise.get('nom')}...[/]")

    service = SkyvernEnrichmentService(max_concurrent=1, use_playwright=False)
    result = await service.enrich_company(enterprise)

    if result.url_found:
        console.print(f"  [green]✓[/] Site trouvé: {result.url_found}")
        console.print(f"  Qualité: {result.enrichment_quality:.0%}")
        if result.description:
            console.print(f"  Description: {result.description[:150]}...")
        if result.contact:
            console.print(f"  Contact: {result.contact}")

        # Update cache
        enrichment_by_siret[enterprise.get("siret", "")] = result.to_dict()
    else:
        console.print("  [yellow]Aucun site trouvé[/]")
        if result.errors:
            console.print(f"  [dim]{result.errors}[/]")


def _interactive_filter(arg: str, enterprises: list, enrichment_by_siret: dict):
    """Filter enterprises by criteria."""
    import re

    # Parse filter: effectif>50, commune=PARIS, enriched
    match = re.match(r'(\w+)\s*([><=]+)\s*(\w+)', arg)

    if arg.lower() == "enriched":
        filtered = [e for e in enterprises if enrichment_by_siret.get(e.get("siret", ""), {}).get("url_found")]
    elif match:
        field, op, value = match.groups()

        if field == "effectif":
            try:
                val = int(value)
                if op == ">":
                    filtered = [e for e in enterprises if _get_effectif(e) > val]
                elif op == "<":
                    filtered = [e for e in enterprises if _get_effectif(e) < val]
                elif op == "=":
                    filtered = [e for e in enterprises if _get_effectif(e) == val]
                else:
                    filtered = enterprises
            except ValueError:
                filtered = enterprises
        elif field == "commune":
            filtered = [e for e in enterprises if value.upper() in e.get("adresse", {}).get("commune", "").upper()]
        else:
            filtered = enterprises
    else:
        console.print("  [yellow]Filtre invalide. Ex: effectif>50, commune=PARIS, enriched[/]")
        return

    console.print(f"  [green]{len(filtered)} entreprises trouvées[/]")
    _interactive_list(filtered, enrichment_by_siret)


def _get_effectif(enterprise: dict) -> int:
    """Get effectif as int, handling 'NN' and other edge cases."""
    eff = enterprise.get("effectif", 0)
    if isinstance(eff, int):
        return eff
    if isinstance(eff, str) and eff.isdigit():
        return int(eff)
    return 0


def _interactive_export(arg: str, enterprises: list, enrichments: list, output_dir: str):
    """Export results to a specific format."""
    import json
    from pathlib import Path

    fmt = arg.lower() if arg else "json"
    output_path = Path(output_dir)

    if fmt == "json":
        out_file = output_path / "export_interactive.json"
        data = {"enterprises": enterprises, "enrichments": enrichments}
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        console.print(f"  [green]✓[/] Exporté: {out_file}")

    elif fmt == "csv":
        import csv
        out_file = output_path / "export_interactive.csv"
        with open(out_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["SIRET", "Nom", "Commune", "Effectif", "URL"])
            enrichment_map = {e.get("siret", ""): e for e in enrichments}
            for e in enterprises:
                siret = e.get("siret", "")
                enr = enrichment_map.get(siret, {})
                writer.writerow([
                    siret,
                    e.get("nom", ""),
                    e.get("adresse", {}).get("commune", ""),
                    e.get("effectif", ""),
                    enr.get("url_found", ""),
                ])
        console.print(f"  [green]✓[/] Exporté: {out_file}")
    else:
        console.print(f"  [yellow]Format non supporté: {fmt}. Utilisez json ou csv[/]")


async def _interactive_ask(question: str, enterprises: list, enrichments: list, model: str):
    """Ask a question about the analysis using LLM."""
    from src.infrastructure.llm.ollama_client import OllamaClient

    if not question:
        console.print("  [yellow]Usage: ask <votre question>[/]")
        return

    console.print("  [dim]Réflexion...[/]")

    # Build context
    enterprise_summary = "\n".join([
        f"- {e.get('nom')} ({e.get('adresse', {}).get('commune', '')}, {e.get('effectif', '?')} sal.)"
        for e in enterprises[:15]
    ])

    enrichment_summary = "\n".join([
        f"- {e.get('nom')}: {e.get('description', 'N/A')[:100]}"
        for e in enrichments if e.get("url_found")
    ][:10])

    prompt = f"""Tu es un expert en intelligence économique territoriale française.

Voici les entreprises analysées:
{enterprise_summary}

Données d'enrichissement web:
{enrichment_summary}

Question de l'utilisateur: {question}

Réponds de manière concise et factuelle en français."""

    try:
        ollama = OllamaClient(model=model)
        response = await ollama.complete(prompt)
        console.print()
        console.print(f"  {response}")
    except Exception as e:
        console.print(f"  [red]Erreur LLM: {e}[/]")
