"""Dynamic completion functions for CLI."""

from pathlib import Path

import httpx


def get_api_url(endpoint: str) -> str:
    """Get full API URL."""
    from src.cli.config.defaults import API_BASE_URL
    return f"{API_BASE_URL}{endpoint}"


def complete_model_names() -> list[str]:
    """
    Get list of available model names for completion.

    Returns:
        List of model names
    """
    try:
        response = httpx.get(
            get_api_url("/api/v1/models"),
            params={"page": 1, "page_size": 100},
            timeout=2.0
        )
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            return [model.get("name", "") for model in models if model.get("name")]
    except Exception:
        pass
    return []


def complete_model_ids() -> list[str]:
    """
    Get list of available model IDs for completion.

    Returns:
        List of model IDs
    """
    try:
        response = httpx.get(
            get_api_url("/api/v1/models"),
            params={"page": 1, "page_size": 100},
            timeout=2.0
        )
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            return [model.get("id", "") for model in models if model.get("id")]
    except Exception:
        pass
    return []


def complete_ollama_models() -> list[str]:
    """
    Get list of Ollama models for completion.

    Returns:
        List of Ollama model names
    """
    try:
        response = httpx.get(
            get_api_url("/api/v1/ollama/models"),
            timeout=2.0
        )
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            return [model.get("name", "") for model in models if model.get("name")]
    except Exception:
        pass
    return ["qwen3.5:27b", "qwen3-coder:30b", "llava:13b", "mistral:latest"]  # Defaults


def complete_job_ids() -> list[str]:
    """
    Get list of fine-tuning job IDs for completion.

    Returns:
        List of job IDs
    """
    try:
        response = httpx.get(
            get_api_url("/api/v1/fine-tuning/jobs"),
            params={"limit": 50},
            timeout=2.0
        )
        if response.status_code == 200:
            jobs = response.json()
            if isinstance(jobs, list):
                return [job.get("job_id", "") for job in jobs if job.get("job_id")]
    except Exception:
        pass
    return []


def complete_template_names() -> list[str]:
    """
    Get list of prompt template names for completion.

    Returns:
        List of template names
    """
    try:
        response = httpx.get(
            get_api_url("/api/v1/prompts/templates"),
            timeout=2.0
        )
        if response.status_code == 200:
            templates = response.json()
            if isinstance(templates, list):
                return [t.get("name", "") for t in templates if t.get("name")]
    except Exception:
        pass
    return []


def complete_project_ids() -> list[str]:
    """
    Get list of annotation project IDs for completion.

    Returns:
        List of project IDs
    """
    try:
        response = httpx.get(
            get_api_url("/api/v1/annotations/projects"),
            timeout=2.0
        )
        if response.status_code == 200:
            projects = response.json()
            if isinstance(projects, list):
                return [str(p.get("id", "")) for p in projects if p.get("id")]
    except Exception:
        pass
    return []


def complete_file_paths(incomplete: str = "", extensions: list[str] = None) -> list[str]:
    """
    Complete file paths with optional extension filtering.

    Args:
        incomplete: Partial path typed by user
        extensions: List of allowed extensions (e.g., [".json", ".csv"])

    Returns:
        List of matching file paths
    """
    try:
        if not incomplete:
            path = Path(".")
            pattern = "*"
        else:
            path = Path(incomplete).parent if "/" in incomplete or "\\" in incomplete else Path(".")
            pattern = Path(incomplete).name + "*" if incomplete else "*"

        matches = []
        for item in path.glob(pattern):
            if extensions:
                if item.is_file() and item.suffix in extensions:
                    matches.append(str(item))
                elif item.is_dir():
                    matches.append(str(item) + "/")
            else:
                matches.append(str(item) + ("/" if item.is_dir() else ""))

        return matches[:20]  # Limit to 20 suggestions
    except Exception:
        return []


# Completion mappings for different commands
COMPLETION_FUNCTIONS = {
    "model_names": complete_model_names,
    "model_ids": complete_model_ids,
    "ollama_models": complete_ollama_models,
    "job_ids": complete_job_ids,
    "template_names": complete_template_names,
    "project_ids": complete_project_ids,
}


def get_completions(completion_type: str) -> list[str]:
    """
    Get completions for a specific type.

    Args:
        completion_type: Type of completion (e.g., "model_names", "job_ids")

    Returns:
        List of completion strings
    """
    func = COMPLETION_FUNCTIONS.get(completion_type)
    if func:
        return func()
    return []
