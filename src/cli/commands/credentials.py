"""CLI commands for managing credentials."""

from getpass import getpass
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from src.infrastructure.auth import get_credential_manager

console = Console()
app = typer.Typer(help="Manage credentials for browser automation")


@app.command()
def add(
    site_name: str = typer.Argument(..., help="Unique name for the site"),
    url: str = typer.Option(..., "--url", "-u", help="Base URL of the site"),
    username: str | None = typer.Option(None, "--username", help="Username/email"),
    password: str | None = typer.Option(
        None, "--password", help="Password (will prompt if not provided)"
    ),
    auth_type: str = typer.Option(
        "form", "--type", "-t", help="Authentication type: form, oauth, api_key"
    ),
):
    """
    Add a new credential for a website.

    Examples:
        # Add GitHub credentials (will prompt for password)
        tawiza credentials add github --url https://github.com --username myuser

        # Add API key
        tawiza credentials add openai --url https://api.openai.com --type api_key
    """
    console.print(f"\n[bold cyan]Adding credential for:[/bold cyan] {site_name}")

    # Prompt for username if not provided
    if auth_type == "form" and not username:
        username = Prompt.ask("Enter username/email")

    # Prompt for password if not provided (and needed)
    if auth_type == "form" and not password:
        password = getpass("Enter password (hidden): ")

    # Handle API key
    api_key = None
    if auth_type == "api_key":
        api_key = getpass("Enter API key (hidden): ")

    # Handle OAuth token
    oauth_token = None
    if auth_type == "oauth":
        oauth_token = getpass("Enter OAuth token (hidden): ")

    # Get tags
    tags_input = Prompt.ask("Enter tags (comma-separated, optional)", default="")
    tags = [t.strip() for t in tags_input.split(",") if t.strip()]

    # Add notes
    notes = Prompt.ask("Enter notes (optional)", default="")

    # Add credential
    manager = get_credential_manager()

    try:
        credential = manager.add_credential(
            site_name=site_name,
            url=url,
            username=username,
            password=password,
            auth_type=auth_type,
            api_key=api_key,
            oauth_token=oauth_token,
            tags=tags,
            notes=notes or None,
        )

        console.print("\n[green]✅ Credential added successfully![/green]")
        console.print(f"Site: {credential.site_name}")
        console.print(f"URL: {credential.url}")
        console.print(f"Type: {credential.auth_type}")

    except Exception as e:
        console.print(f"\n[red]❌ Error adding credential: {e}[/red]")
        raise typer.Exit(1)


@app.command("list")
def list_credentials(
    tag: str | None = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    show_passwords: bool = typer.Option(
        False, "--show-passwords", help="Show passwords (dangerous!)"
    ),
):
    """
    List all stored credentials.

    Examples:
        # List all credentials
        tawiza credentials list

        # List only dev-related credentials
        tawiza credentials list --tag dev
    """
    try:
        manager = get_credential_manager()
    except Exception as e:
        console.print(f"[yellow]⚠️ Credential manager initialization warning: {e}[/yellow]")
        console.print("[dim]Using file-based credential storage as fallback.[/dim]\n")
        try:
            from src.infrastructure.auth.credential_manager import CredentialManager

            manager = CredentialManager(use_keyring=False)
        except Exception as e2:
            console.print(f"[red]❌ Failed to initialize credential manager: {e2}[/red]")
            raise typer.Exit(1)

    site_names = manager.list_credentials(tag=tag)

    if not site_names:
        console.print("[yellow]No credentials found[/yellow]")
        return

    table = Table(title=f"Stored Credentials{f' (tag: {tag})' if tag else ''}", show_header=True)
    table.add_column("Site Name", style="cyan", width=20)
    table.add_column("URL", style="magenta", width=40)
    table.add_column("Username", style="green", width=25)
    table.add_column("Type", style="yellow", width=10)
    table.add_column("Tags", style="blue", width=15)

    for site_name in sorted(site_names):
        cred = manager.get_credential(site_name)
        if cred:
            username_display = cred.username or "(API key)" if cred.api_key else "(OAuth)"
            if show_passwords and cred.password:
                username_display += f" / {cred.password}"

            table.add_row(
                cred.site_name,
                cred.url,
                username_display,
                cred.auth_type,
                ", ".join(cred.tags) if cred.tags else "",
            )

    console.print("\n")
    console.print(table)
    console.print(f"\n[dim]Total: {len(site_names)} credentials[/dim]\n")


@app.command()
def show(
    site_name: str = typer.Argument(..., help="Site name to show"),
    show_password: bool = typer.Option(False, "--show-password", help="Show password (dangerous!)"),
):
    """
    Show details for a specific credential.

    Examples:
        tawiza credentials show github
        tawiza credentials show github --show-password
    """
    manager = get_credential_manager()
    cred = manager.get_credential(site_name)

    if not cred:
        console.print(f"[red]❌ Credential not found: {site_name}[/red]")
        raise typer.Exit(1)

    # Build info panel
    info_lines = [
        f"[bold]Site:[/bold] {cred.site_name}",
        f"[bold]URL:[/bold] {cred.url}",
        f"[bold]Type:[/bold] {cred.auth_type}",
    ]

    if cred.username:
        info_lines.append(f"[bold]Username:[/bold] {cred.username}")

    if cred.password:
        if show_password:
            info_lines.append(f"[bold]Password:[/bold] {cred.password}")
        else:
            info_lines.append("[bold]Password:[/bold] ****** (use --show-password to reveal)")

    if cred.api_key:
        if show_password:
            info_lines.append(f"[bold]API Key:[/bold] {cred.api_key}")
        else:
            info_lines.append("[bold]API Key:[/bold] ****** (use --show-password to reveal)")

    if cred.oauth_token:
        if show_password:
            info_lines.append(f"[bold]OAuth Token:[/bold] {cred.oauth_token}")
        else:
            info_lines.append("[bold]OAuth Token:[/bold] ****** (use --show-password to reveal)")

    if cred.tags:
        info_lines.append(f"[bold]Tags:[/bold] {', '.join(cred.tags)}")

    if cred.notes:
        info_lines.append(f"[bold]Notes:[/bold] {cred.notes}")

    panel = Panel(
        "\n".join(info_lines),
        title=f"[bold cyan]Credential: {site_name}[/bold cyan]",
        border_style="cyan",
    )

    console.print("\n")
    console.print(panel)
    console.print("\n")


@app.command()
def remove(
    site_name: str = typer.Argument(..., help="Site name to remove"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """
    Remove a credential.

    Examples:
        tawiza credentials remove github
        tawiza credentials remove github --yes
    """
    manager = get_credential_manager()

    if not yes:
        confirm = Confirm.ask(f"Are you sure you want to remove credential for '{site_name}'?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    if manager.remove_credential(site_name):
        console.print(f"[green]✅ Credential removed: {site_name}[/green]")
    else:
        console.print(f"[red]❌ Credential not found: {site_name}[/red]")
        raise typer.Exit(1)


@app.command()
def export(
    output: Path = typer.Option(
        "credentials_backup.json", "--output", "-o", help="Output file path"
    ),
    include_passwords: bool = typer.Option(
        False, "--include-passwords", help="Include passwords (DANGEROUS!)"
    ),
):
    """
    Export credentials to JSON file.

    Examples:
        # Export without passwords (safe)
        tawiza credentials export --output backup.json

        # Export with passwords (dangerous!)
        tawiza credentials export --output backup.json --include-passwords
    """
    if include_passwords:
        console.print("[bold red]⚠️ WARNING: Exporting passwords is a security risk![/bold red]")
        confirm = Confirm.ask("Are you sure you want to include passwords in the export?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    manager = get_credential_manager()

    try:
        manager.export_credentials(output, include_passwords=include_passwords)
        console.print(f"[green]✅ Credentials exported to: {output}[/green]")

        if not include_passwords:
            console.print("[yellow]Note: Passwords were redacted for security[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Error exporting credentials: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def import_creds(
    input_file: Path = typer.Argument(..., help="JSON file to import"),
    merge: bool = typer.Option(
        True, "--merge/--replace", help="Merge with existing or replace all"
    ),
):
    """
    Import credentials from JSON file.

    Examples:
        # Merge with existing
        tawiza credentials import backup.json

        # Replace all existing credentials
        tawiza credentials import backup.json --replace
    """
    if not input_file.exists():
        console.print(f"[red]❌ File not found: {input_file}[/red]")
        raise typer.Exit(1)

    if not merge:
        console.print("[bold red]⚠️ WARNING: This will replace all existing credentials![/bold red]")
        confirm = Confirm.ask("Are you sure?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    manager = get_credential_manager()

    try:
        manager.import_credentials(input_file, merge=merge)
        console.print(f"[green]✅ Credentials imported from: {input_file}[/green]")

    except Exception as e:
        console.print(f"[red]❌ Error importing credentials: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
