"""
Docker commands for container management.

Provides CLI interface for Docker operations integrated with Tawiza.
"""

import json
import subprocess

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.cli.ui.theme import SUNSET_THEME

app = typer.Typer(
    name="docker", help="Docker container management", add_completion=False, rich_markup_mode="rich"
)

console = Console()


def _run_docker_cmd(cmd: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    """Run a docker command."""
    full_cmd = ["docker"] + cmd
    return subprocess.run(full_cmd, capture_output=capture, text=True, timeout=60)


def _docker_available() -> bool:
    """Check if Docker is available."""
    try:
        result = _run_docker_cmd(["version", "--format", "{{.Server.Version}}"])
        return result.returncode == 0
    except Exception:
        return False


# ===== Container Commands =====


@app.command("ps")
def list_containers(
    all: bool = typer.Option(False, "--all", "-a", help="Show all containers"),
    filter_name: str | None = typer.Option(None, "--filter", "-f", help="Filter by name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    List Docker containers

    Examples:
        # List running containers
        tawiza docker ps

        # List all containers
        tawiza docker ps --all

        # Filter by name
        tawiza docker ps --filter tawiza
    """
    if not _docker_available():
        console.print("[red]Docker not available or not running[/red]")
        return

    cmd = ["ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"]
    if all:
        cmd.insert(1, "-a")

    result = _run_docker_cmd(cmd)

    if result.returncode != 0:
        console.print(f"[red]Error: {result.stderr}[/red]")
        return

    containers = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split("\t")
            if len(parts) >= 4:
                container = {
                    "id": parts[0][:12],
                    "name": parts[1],
                    "image": parts[2],
                    "status": parts[3],
                    "ports": parts[4] if len(parts) > 4 else "",
                }
                if filter_name is None or filter_name.lower() in container["name"].lower():
                    containers.append(container)

    if json_output:
        console.print(json.dumps(containers, indent=2))
        return

    if not containers:
        console.print("[yellow]No containers found[/yellow]")
        return

    table = Table(
        title="Docker Containers", border_style=SUNSET_THEME.accent_color, show_header=True
    )
    table.add_column("ID", style="cyan", width=12)
    table.add_column("Name", style="green")
    table.add_column("Image")
    table.add_column("Status")
    table.add_column("Ports", style="dim")

    for c in containers:
        status_style = "green" if "Up" in c["status"] else "yellow"
        table.add_row(
            c["id"],
            c["name"],
            c["image"][:30],
            f"[{status_style}]{c['status'][:20]}[/{status_style}]",
            c["ports"][:30] if c["ports"] else "-",
        )

    console.print()
    console.print(table)


@app.command("run")
def run_container(
    image: str = typer.Argument(..., help="Image to run"),
    name: str | None = typer.Option(None, "--name", "-n", help="Container name"),
    detach: bool = typer.Option(True, "--detach/--no-detach", "-d", help="Run in background"),
    port: str | None = typer.Option(None, "--port", "-p", help="Port mapping (e.g., 8080:80)"),
    env: list[str] | None = typer.Option(None, "--env", "-e", help="Environment variables"),
    volume: str | None = typer.Option(None, "--volume", "-v", help="Volume mount"),
    gpu: bool = typer.Option(False, "--gpu", help="Enable GPU access (ROCm)"),
):
    """
    Run a Docker container

    Examples:
        # Run nginx
        tawiza docker run nginx --name web --port 8080:80

        # Run with GPU
        tawiza docker run ollama/ollama --gpu --name ollama

        # Run with environment
        tawiza docker run postgres --env POSTGRES_PASSWORD=secret
    """
    if not _docker_available():
        console.print("[red]Docker not available or not running[/red]")
        return

    cmd = ["run"]

    if detach:
        cmd.append("-d")

    if name:
        cmd.extend(["--name", name])

    if port:
        cmd.extend(["-p", port])

    if volume:
        cmd.extend(["-v", volume])

    if env:
        for e in env:
            cmd.extend(["-e", e])

    if gpu:
        # AMD ROCm GPU support
        cmd.extend(
            [
                "--device=/dev/kfd",
                "--device=/dev/dri",
                "--group-add=video",
                "--security-opt=seccomp=unconfined",
            ]
        )

    cmd.append(image)

    console.print(f"[dim]Running: docker {' '.join(cmd)}[/dim]")

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
    ) as progress:
        progress.add_task("Starting container...", total=None)
        result = _run_docker_cmd(cmd)

    if result.returncode == 0:
        container_id = result.stdout.strip()[:12]
        console.print(f"[green]✓[/green] Container started: {container_id}")
        if name:
            console.print(f"[dim]Name: {name}[/dim]")
    else:
        console.print(f"[red]Error: {result.stderr}[/red]")


@app.command("stop")
def stop_container(
    container: str = typer.Argument(..., help="Container ID or name"),
    force: bool = typer.Option(False, "--force", "-f", help="Force stop"),
):
    """
    Stop a running container

    Examples:
        tawiza docker stop web
        tawiza docker stop abc123 --force
    """
    if not _docker_available():
        console.print("[red]Docker not available or not running[/red]")
        return

    cmd = ["stop"]
    if force:
        cmd = ["kill"]
    cmd.append(container)

    result = _run_docker_cmd(cmd)

    if result.returncode == 0:
        console.print(f"[green]✓[/green] Container stopped: {container}")
    else:
        console.print(f"[red]Error: {result.stderr}[/red]")


@app.command("rm")
def remove_container(
    container: str = typer.Argument(..., help="Container ID or name"),
    force: bool = typer.Option(False, "--force", "-f", help="Force remove"),
):
    """
    Remove a container

    Examples:
        tawiza docker rm web
        tawiza docker rm abc123 --force
    """
    if not _docker_available():
        console.print("[red]Docker not available or not running[/red]")
        return

    cmd = ["rm"]
    if force:
        cmd.append("-f")
    cmd.append(container)

    result = _run_docker_cmd(cmd)

    if result.returncode == 0:
        console.print(f"[green]✓[/green] Container removed: {container}")
    else:
        console.print(f"[red]Error: {result.stderr}[/red]")


@app.command("logs")
def container_logs(
    container: str = typer.Argument(..., help="Container ID or name"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: int = typer.Option(50, "--tail", "-n", help="Number of lines to show"),
):
    """
    View container logs

    Examples:
        tawiza docker logs web
        tawiza docker logs web --follow
        tawiza docker logs web --tail 100
    """
    if not _docker_available():
        console.print("[red]Docker not available or not running[/red]")
        return

    cmd = ["logs", "--tail", str(tail)]
    if follow:
        cmd.append("-f")
    cmd.append(container)

    if follow:
        # Stream logs
        console.print(f"[dim]Following logs for {container} (Ctrl+C to stop)[/dim]\n")
        try:
            subprocess.run(["docker"] + cmd, timeout=None)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped following logs[/yellow]")
    else:
        result = _run_docker_cmd(cmd)
        if result.returncode == 0:
            console.print(result.stdout)
        else:
            console.print(f"[red]Error: {result.stderr}[/red]")


@app.command("exec")
def exec_container(
    container: str = typer.Argument(..., help="Container ID or name"),
    command: str = typer.Argument("bash", help="Command to execute"),
):
    """
    Execute command in container

    Examples:
        tawiza docker exec web bash
        tawiza docker exec web "ls -la"
    """
    if not _docker_available():
        console.print("[red]Docker not available or not running[/red]")
        return

    console.print(f"[dim]Executing in {container}: {command}[/dim]\n")

    # Interactive exec
    try:
        subprocess.run(["docker", "exec", "-it", container] + command.split(), timeout=None)
    except KeyboardInterrupt:
        console.print("\n[yellow]Execution interrupted[/yellow]")


# ===== Image Commands =====


@app.command("images")
def list_images(json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON")):
    """
    List Docker images

    Examples:
        tawiza docker images
    """
    if not _docker_available():
        console.print("[red]Docker not available or not running[/red]")
        return

    result = _run_docker_cmd(
        ["images", "--format", "{{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedSince}}"]
    )

    if result.returncode != 0:
        console.print(f"[red]Error: {result.stderr}[/red]")
        return

    images = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split("\t")
            if len(parts) >= 4:
                images.append(
                    {
                        "repository": parts[0],
                        "tag": parts[1],
                        "id": parts[2][:12],
                        "size": parts[3],
                        "created": parts[4] if len(parts) > 4 else "",
                    }
                )

    if json_output:
        console.print(json.dumps(images, indent=2))
        return

    table = Table(title="Docker Images", border_style=SUNSET_THEME.accent_color, show_header=True)
    table.add_column("Repository", style="cyan")
    table.add_column("Tag", style="green")
    table.add_column("ID", style="dim")
    table.add_column("Size", justify="right")
    table.add_column("Created")

    for img in images:
        table.add_row(img["repository"][:30], img["tag"], img["id"], img["size"], img["created"])

    console.print()
    console.print(table)


@app.command("pull")
def pull_image(image: str = typer.Argument(..., help="Image to pull")):
    """
    Pull a Docker image

    Examples:
        tawiza docker pull nginx
        tawiza docker pull ollama/ollama:latest
    """
    if not _docker_available():
        console.print("[red]Docker not available or not running[/red]")
        return

    console.print(f"[dim]Pulling image: {image}[/dim]\n")

    try:
        subprocess.run(["docker", "pull", image], timeout=600)
        console.print(f"\n[green]✓[/green] Image pulled: {image}")
    except subprocess.TimeoutExpired:
        console.print("[red]Timeout pulling image[/red]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Pull cancelled[/yellow]")


# ===== Stats and Info =====


@app.command("stats")
def container_stats(
    container: str | None = typer.Argument(
        None, help="Container ID or name (all if not specified)"
    ),
    no_stream: bool = typer.Option(False, "--no-stream", help="Disable streaming stats"),
):
    """
    Show container resource usage

    Examples:
        tawiza docker stats
        tawiza docker stats web --no-stream
    """
    if not _docker_available():
        console.print("[red]Docker not available or not running[/red]")
        return

    cmd = ["stats"]
    if no_stream:
        cmd.append("--no-stream")
    if container:
        cmd.append(container)

    console.print("[dim]Container statistics (Ctrl+C to stop)[/dim]\n")

    try:
        subprocess.run(["docker"] + cmd, timeout=None)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stats stopped[/yellow]")


@app.command("info")
def docker_info():
    """
    Show Docker system information

    Examples:
        tawiza docker info
    """
    if not _docker_available():
        console.print("[red]Docker not available or not running[/red]")
        return

    result = _run_docker_cmd(["info", "--format", "{{json .}}"])

    if result.returncode != 0:
        console.print(f"[red]Error: {result.stderr}[/red]")
        return

    try:
        info = json.loads(result.stdout)

        console.print()
        console.print(
            Panel("[bold cyan]Docker Info[/bold cyan]", border_style=SUNSET_THEME.accent_color)
        )

        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        table.add_row("Docker Version", info.get("ServerVersion", "N/A"))
        table.add_row("Containers", str(info.get("Containers", 0)))
        table.add_row("  Running", str(info.get("ContainersRunning", 0)))
        table.add_row("  Stopped", str(info.get("ContainersStopped", 0)))
        table.add_row("Images", str(info.get("Images", 0)))
        table.add_row("Driver", info.get("Driver", "N/A"))
        table.add_row("OS", info.get("OperatingSystem", "N/A"))
        table.add_row("CPUs", str(info.get("NCPU", "N/A")))
        table.add_row("Memory", f"{info.get('MemTotal', 0) / (1024**3):.1f} GB")

        # GPU info
        runtimes = info.get("Runtimes", {})
        if "rocm" in runtimes or "amd" in str(runtimes).lower():
            table.add_row("GPU Runtime", "[green]ROCm Available[/green]")
        elif "nvidia" in runtimes:
            table.add_row("GPU Runtime", "[green]NVIDIA Available[/green]")
        else:
            table.add_row("GPU Runtime", "[dim]Not configured[/dim]")

        console.print(table)

    except json.JSONDecodeError:
        console.print(result.stdout)


# ===== Cleanup =====


@app.command("prune")
def docker_prune(
    all: bool = typer.Option(False, "--all", "-a", help="Remove all unused resources"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """
    Remove unused Docker resources

    Examples:
        tawiza docker prune
        tawiza docker prune --all --force
    """
    if not _docker_available():
        console.print("[red]Docker not available or not running[/red]")
        return

    if not force:
        from rich.prompt import Confirm

        if not Confirm.ask("Remove unused Docker resources?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    cmds = [["container", "prune", "-f"]]
    if all:
        cmds.extend(
            [["image", "prune", "-a", "-f"], ["volume", "prune", "-f"], ["network", "prune", "-f"]]
        )

    for cmd in cmds:
        console.print(f"[dim]Running: docker {' '.join(cmd)}[/dim]")
        result = _run_docker_cmd(cmd)
        if result.stdout:
            console.print(result.stdout)

    console.print("[green]✓[/green] Cleanup completed")


if __name__ == "__main__":
    app()
