"""CLI commands for CAPTCHA solving configuration."""

import os
from getpass import getpass

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.infrastructure.captcha import get_captcha_solver

console = Console()
app = typer.Typer(help="Configure CAPTCHA solving")


@app.command()
def config(
    provider: str = typer.Option(
        "2captcha",
        "--provider",
        "-p",
        help="CAPTCHA solver provider: 2captcha, anti-captcha"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="API key (will prompt if not provided)"
    ),
    timeout: int = typer.Option(
        120,
        "--timeout",
        "-t",
        help="Max solving time in seconds"
    ),
):
    """
    Configure CAPTCHA solving service.

    Examples:
        # Configure 2Captcha (will prompt for API key)
        tawiza captcha config --provider 2captcha

        # Configure with API key inline
        tawiza captcha config --provider 2captcha --api-key YOUR_KEY
    """
    console.print(f"\n[bold cyan]Configuring CAPTCHA solver:[/bold cyan] {provider}")

    # Prompt for API key if not provided
    if not api_key:
        api_key = getpass(f"Enter {provider} API key (hidden): ")

    if not api_key:
        console.print("[red]❌ API key is required[/red]")
        raise typer.Exit(1)

    # Store in environment (for current session)
    # In production, this should be stored in a config file or keyring
    env_var_name = f"TAWIZA_CAPTCHA_{provider.upper().replace('-', '_')}_KEY"
    os.environ[env_var_name] = api_key
    os.environ["TAWIZA_CAPTCHA_PROVIDER"] = provider
    os.environ["TAWIZA_CAPTCHA_TIMEOUT"] = str(timeout)

    # Show configuration
    panel = Panel(
        f"""[bold]Provider:[/bold] {provider}
[bold]API Key:[/bold] ******{api_key[-4:]} (last 4 chars)
[bold]Timeout:[/bold] {timeout}s
[bold]Status:[/bold] ✅ Configured (for current session)

[yellow]Note:[/yellow] Add these to your .env file for persistence:
  {env_var_name}=YOUR_API_KEY
  TAWIZA_CAPTCHA_PROVIDER={provider}
  TAWIZA_CAPTCHA_TIMEOUT={timeout}""",
        title="[bold green]CAPTCHA Configuration[/bold green]",
        border_style="green",
    )

    console.print("\n")
    console.print(panel)
    console.print("\n")


@app.command()
def test(
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Override configured provider"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="Override configured API key"
    ),
):
    """
    Test CAPTCHA solver configuration.

    Examples:
        # Test configured solver
        tawiza captcha test

        # Test specific provider
        tawiza captcha test --provider 2captcha --api-key YOUR_KEY
    """
    import asyncio

    console.print("\n[bold cyan]Testing CAPTCHA solver...[/bold cyan]\n")

    # Get configuration
    if not provider:
        provider = os.environ.get("TAWIZA_CAPTCHA_PROVIDER", "2captcha")

    if not api_key:
        env_var_name = f"TAWIZA_CAPTCHA_{provider.upper().replace('-', '_')}_KEY"
        api_key = os.environ.get(env_var_name)

    if not api_key:
        console.print(
            "[red]❌ No API key configured. Run 'tawiza captcha config' first.[/red]"
        )
        raise typer.Exit(1)

    timeout = int(os.environ.get("TAWIZA_CAPTCHA_TIMEOUT", "120"))

    console.print(f"Provider: {provider}")
    console.print(f"Timeout: {timeout}s")
    console.print(f"API Key: ******{api_key[-4:]}\n")

    # Test with a demo reCAPTCHA
    console.print("[yellow]Testing with Google reCAPTCHA demo page...[/yellow]\n")

    async def run_test():
        solver = get_captcha_solver(provider=provider, api_key=api_key, timeout=timeout)

        try:
            console.print("Submitting reCAPTCHA v2 demo task...")

            result = await solver.solve_recaptcha_v2(
                site_key="6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-",
                page_url="https://www.google.com/recaptcha/api2/demo"
            )

            if result.success:
                console.print("\n[green]✅ Test PASSED![/green]")
                console.print(f"Solution received in {result.solve_time:.1f}s")
                console.print(f"Token (first 50 chars): {result.solution[:50]}...")
            else:
                console.print("\n[red]❌ Test FAILED[/red]")
                console.print(f"Error: {result.error}")
                raise typer.Exit(1)

        except Exception as e:
            console.print(f"\n[red]❌ Test ERROR: {e}[/red]")
            raise typer.Exit(1)
        finally:
            await solver.close()

    asyncio.run(run_test())


@app.command()
def balance(
    provider: str | None = typer.Option(
        None,
        "--provider",
        "-p",
        help="Override configured provider"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        "-k",
        help="Override configured API key"
    ),
):
    """
    Check account balance for CAPTCHA solving service.

    Examples:
        tawiza captcha balance
    """
    import asyncio

    import httpx

    # Get configuration
    if not provider:
        provider = os.environ.get("TAWIZA_CAPTCHA_PROVIDER", "2captcha")

    if not api_key:
        env_var_name = f"TAWIZA_CAPTCHA_{provider.upper().replace('-', '_')}_KEY"
        api_key = os.environ.get(env_var_name)

    if not api_key:
        console.print(
            "[red]❌ No API key configured. Run 'tawiza captcha config' first.[/red]"
        )
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]Checking balance for {provider}...[/bold cyan]\n")

    async def check_balance():
        async with httpx.AsyncClient() as client:
            if provider == "2captcha":
                response = await client.get(
                    "https://2captcha.com/res.php",
                    params={
                        "key": api_key,
                        "action": "getbalance",
                        "json": 1,
                    }
                )
                data = response.json()

                if data.get("status") == 1:
                    balance = float(data["request"])
                    console.print(f"[green]Balance: ${balance:.2f}[/green]")
                else:
                    console.print(f"[red]Error: {data.get('request')}[/red]")
                    raise typer.Exit(1)

            elif provider == "anti-captcha":
                response = await client.post(
                    "https://api.anti-captcha.com/getBalance",
                    json={"clientKey": api_key}
                )
                data = response.json()

                if data.get("errorId", 0) == 0:
                    balance = float(data["balance"])
                    console.print(f"[green]Balance: ${balance:.2f}[/green]")
                else:
                    console.print(f"[red]Error: {data.get('errorDescription')}[/red]")
                    raise typer.Exit(1)

            else:
                console.print(f"[red]Unknown provider: {provider}[/red]")
                raise typer.Exit(1)

    asyncio.run(check_balance())


@app.command()
def pricing():
    """
    Show pricing for CAPTCHA solving services.
    """
    console.print("\n[bold cyan]CAPTCHA Solving Pricing[/bold cyan]\n")

    table = Table(title="Popular CAPTCHA Solver Services", show_header=True)
    table.add_column("Service", style="cyan", width=20)
    table.add_column("reCAPTCHA v2", style="green", width=15)
    table.add_column("reCAPTCHA v3", style="green", width=15)
    table.add_column("hCaptcha", style="green", width=15)
    table.add_column("Image", style="green", width=15)

    table.add_row(
        "2Captcha",
        "$2.99 / 1000",
        "$2.99 / 1000",
        "$2.99 / 1000",
        "$0.50 / 1000"
    )
    table.add_row(
        "Anti-Captcha",
        "$2.00 / 1000",
        "$2.00 / 1000",
        "$2.00 / 1000",
        "$0.50 / 1000"
    )
    table.add_row(
        "CapSolver",
        "$0.80 / 1000",
        "$0.80 / 1000",
        "$0.80 / 1000",
        "$0.50 / 1000"
    )

    console.print(table)
    console.print("\n[yellow]Note:[/yellow] Prices are approximate and may vary.\n")


@app.command()
def status():
    """
    Show current CAPTCHA configuration status.
    """
    console.print("\n[bold cyan]CAPTCHA Configuration Status[/bold cyan]\n")

    provider = os.environ.get("TAWIZA_CAPTCHA_PROVIDER")
    timeout = os.environ.get("TAWIZA_CAPTCHA_TIMEOUT")

    if provider:
        env_var_name = f"TAWIZA_CAPTCHA_{provider.upper().replace('-', '_')}_KEY"
        api_key = os.environ.get(env_var_name)

        if api_key:
            status_text = f"""[bold]Provider:[/bold] {provider}
[bold]API Key:[/bold] ******{api_key[-4:]} (configured)
[bold]Timeout:[/bold] {timeout}s
[bold]Status:[/bold] ✅ Ready"""
        else:
            status_text = f"""[bold]Provider:[/bold] {provider}
[bold]API Key:[/bold] ❌ Not configured
[bold]Status:[/bold] ⚠️ Not ready (run 'tawiza captcha config')"""
    else:
        status_text = """[bold]Status:[/bold] ❌ Not configured

Run 'tawiza captcha config' to set up CAPTCHA solving."""

    panel = Panel(
        status_text,
        title="[bold]Configuration[/bold]",
        border_style="cyan",
    )

    console.print(panel)
    console.print("\n")


if __name__ == "__main__":
    app()
