"""CLI commands for data sources management."""

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from src.cli.v2.ui.theme import footer, header

console = Console()
app = typer.Typer(help="Manage data sources")


def _get_manager():
    """Create DataSourceManager with all registered adapters."""
    from src.infrastructure.datasources.adapters import (
        BanAdapter,
        BoampAdapter,
        BodaccAdapter,
        GdeltAdapter,
        GoogleNewsAdapter,
        RssAdapter,
        SireneAdapter,
        SubventionsAdapter,
    )
    from src.infrastructure.datasources.adapters.commoncrawl import CommonCrawlAdapter
    from src.infrastructure.datasources.manager import DataSourceManager

    manager = DataSourceManager()
    # Legal/Business sources
    manager.register(BodaccAdapter())
    manager.register(BoampAdapter())
    manager.register(SireneAdapter())
    # Geographic sources
    manager.register(BanAdapter())
    # News sources
    manager.register(RssAdapter())
    manager.register(GdeltAdapter())
    manager.register(GoogleNewsAdapter())
    # Subventions sources
    manager.register(SubventionsAdapter())
    # Web archives
    manager.register(CommonCrawlAdapter())
    return manager


@app.command("status")
def status():
    """Show status of all data sources."""
    console.print(header("sources status", 55))
    console.print()

    async def _status():
        manager = _get_manager()
        return await manager.status()

    statuses = asyncio.run(_status())

    if not statuses:
        console.print("  [yellow]No adapters registered[/]")
        console.print()
        console.print(footer(55))
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Source", width=15)
    table.add_column("Status", width=10)
    table.add_column("Rate Limit", width=12)
    table.add_column("Cache TTL", width=12)

    for name, info in statuses.items():
        status_icon = "[green]✓[/]" if info.get("healthy") else "[red]✗[/]"
        config = info.get("config", {})
        table.add_row(
            name,
            status_icon,
            f"{config.get('rate_limit', '?')}/min",
            f"{config.get('cache_ttl', '?')}s",
        )

    console.print(table)
    console.print()
    console.print(footer(55))


@app.command("test")
def test_sources():
    """Test connectivity to all data sources."""
    console.print(header("sources test", 55))
    console.print()

    async def _test():
        manager = _get_manager()

        results = {}
        for name, adapter in manager.adapters.items():
            console.print(f"  Testing {name}...", end=" ")
            try:
                healthy = await adapter.health_check()
                if healthy:
                    console.print("[green]OK[/]")
                else:
                    console.print("[red]FAIL[/]")
                results[name] = healthy
            except Exception as e:
                console.print(f"[red]ERROR: {e}[/]")
                results[name] = False

        return results

    asyncio.run(_test())
    console.print()
    console.print(footer(55))


@app.command("sync")
def sync(
    source: str | None = typer.Argument(None, help="Source to sync (default: all)"),
    days: int = typer.Option(7, "--days", "-d", help="Sync last N days"),
):
    """Force synchronization of data sources."""
    from datetime import datetime, timedelta

    console.print(header("sources sync", 55))
    console.print()

    since = datetime.utcnow() - timedelta(days=days)
    console.print(f"  Syncing data since: {since.strftime('%Y-%m-%d')}")
    console.print()

    async def _sync():
        manager = _get_manager()

        if source:
            if source not in manager.adapters:
                console.print(f"  [red]Unknown source: {source}[/]")
                return []
            adapters = {source: manager.adapters[source]}
        else:
            adapters = manager.adapters

        statuses = []
        for name, adapter in adapters.items():
            console.print(f"  Syncing {name}...", end=" ")
            try:
                status = await adapter.sync(since)
                if status.status == "success":
                    console.print(f"[green]{status.records_synced} records[/]")
                else:
                    console.print(f"[yellow]{status.status}[/]")
                statuses.append(status)
            except Exception as e:
                console.print(f"[red]ERROR: {e}[/]")

        return statuses

    asyncio.run(_sync())
    console.print()
    console.print(footer(55))
