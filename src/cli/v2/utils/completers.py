"""Dynamic autocompletion for Tawiza CLI v2."""

import json
from pathlib import Path


def complete_models(incomplete: str) -> list[tuple[str, str]]:
    """Complete model names from Ollama API."""
    models = []

    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            data = response.json()
            for m in data.get("models", []):
                name = m.get("name", "")
                size = m.get("size", 0)
                size_str = f"{size / 1e9:.1f}GB" if size else ""
                if incomplete.lower() in name.lower():
                    models.append((name, size_str))
    except Exception:
        # Fallback to common models
        common = [
            ("qwen3.5:27b", "Recommended"),
            ("qwen3:30b", "Large"),
            ("llama3:8b", "Fast"),
            ("mistral:latest", "Balanced"),
            ("codellama:13b", "Coding"),
        ]
        models = [(n, d) for n, d in common if incomplete.lower() in n.lower()]

    return models


def complete_agents(incomplete: str) -> list[tuple[str, str]]:
    """Complete agent names."""
    agents = [
        ("analyst", "Data analysis and insights"),
        ("coder", "Code generation and review"),
        ("browser", "Web automation and scraping"),
        ("ml", "Machine learning tasks"),
        ("writer", "Content creation"),
        ("researcher", "Information gathering"),
    ]

    # Also check for custom agents in config
    try:
        agents_dir = Path.home() / ".tawiza" / "agents"
        if agents_dir.exists():
            for agent_file in agents_dir.glob("*.json"):
                try:
                    agent_data = json.loads(agent_file.read_text())
                    name = agent_data.get("name", agent_file.stem)
                    desc = agent_data.get("description", "Custom agent")
                    agents.append((name, desc))
                except Exception:
                    pass
    except Exception:
        pass

    return [(n, d) for n, d in agents if incomplete.lower() in n.lower()]


def complete_datasets(incomplete: str) -> list[tuple[str, str]]:
    """Complete dataset names from storage."""
    datasets = []

    try:
        data_dir = Path.home() / ".tawiza" / "data"
        if data_dir.exists():
            for f in data_dir.iterdir():
                if f.is_file() and f.suffix in [".csv", ".json", ".jsonl", ".parquet"]:
                    size = f.stat().st_size
                    size_str = f"{size / 1024:.1f}KB" if size < 1024*1024 else f"{size / (1024*1024):.1f}MB"
                    if incomplete.lower() in f.name.lower():
                        datasets.append((f.name, size_str))
    except Exception:
        pass

    return datasets


def complete_jobs(incomplete: str) -> list[tuple[str, str]]:
    """Complete training job IDs."""
    jobs = []

    try:
        jobs_file = Path.home() / ".tawiza" / "jobs.json"
        if jobs_file.exists():
            data = json.loads(jobs_file.read_text())
            for job_id, job_info in data.items():
                status = job_info.get("status", "unknown")
                name = job_info.get("name", "")
                if incomplete.lower() in job_id.lower() or incomplete.lower() in name.lower():
                    jobs.append((job_id, f"{name} ({status})"))
    except Exception:
        pass

    return jobs


def complete_config_keys(incomplete: str) -> list[tuple[str, str]]:
    """Complete configuration keys."""
    from src.cli.v2.utils.config import DEFAULT_CONFIG

    return [
        (key, f"Default: {value}")
        for key, value in DEFAULT_CONFIG.items()
        if incomplete.lower() in key.lower()
    ]


def complete_gpu_pci(incomplete: str) -> list[tuple[str, str]]:
    """Complete GPU PCI addresses."""
    gpus = []

    try:
        import subprocess
        result = subprocess.run(
            ["lspci", "-nn"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "VGA" in line or "3D" in line:
                    pci_addr = line.split()[0]
                    name = line.split(":")[2].strip()[:40] if ":" in line else "GPU"
                    if incomplete in pci_addr:
                        gpus.append((pci_addr, name))
    except Exception:
        pass

    return gpus


def complete_files(incomplete: str, extensions: list[str] = None) -> list[tuple[str, str]]:
    """Complete file paths with optional extension filter."""
    files = []

    try:
        # Handle partial path
        if "/" in incomplete:
            base_path = Path(incomplete).parent
            prefix = Path(incomplete).name
        else:
            base_path = Path.cwd()
            prefix = incomplete

        if base_path.exists():
            for f in base_path.iterdir():
                name = f.name
                if prefix.lower() in name.lower():
                    if extensions is None or f.suffix.lower() in extensions:
                        desc = "dir" if f.is_dir() else f"{f.stat().st_size // 1024}KB"
                        full_path = str(f) if "/" in incomplete else name
                        files.append((full_path, desc))
    except Exception:
        pass

    return files[:20]  # Limit results


# Typer-compatible completion functions
def model_completion(incomplete: str) -> list[str]:
    """Typer callback for model completion."""
    return [name for name, _ in complete_models(incomplete)]


def agent_completion(incomplete: str) -> list[str]:
    """Typer callback for agent completion."""
    return [name for name, _ in complete_agents(incomplete)]


def dataset_completion(incomplete: str) -> list[str]:
    """Typer callback for dataset completion."""
    return [name for name, _ in complete_datasets(incomplete)]


def job_completion(incomplete: str) -> list[str]:
    """Typer callback for job completion."""
    return [job_id for job_id, _ in complete_jobs(incomplete)]


def config_key_completion(incomplete: str) -> list[str]:
    """Typer callback for config key completion."""
    return [key for key, _ in complete_config_keys(incomplete)]


def gpu_pci_completion(incomplete: str) -> list[str]:
    """Typer callback for GPU PCI address completion."""
    return [addr for addr, _ in complete_gpu_pci(incomplete)]


def data_file_completion(incomplete: str) -> list[str]:
    """Typer callback for data file completion."""
    return [f for f, _ in complete_files(incomplete, [".csv", ".json", ".jsonl", ".parquet"])]
