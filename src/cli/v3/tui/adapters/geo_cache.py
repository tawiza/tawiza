"""GeoCache adapter for managing GeoJSON data."""

import asyncio
import contextlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from loguru import logger

FRANCE_GEOJSON_BASE = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master"

DEFAULT_FILES = {
    "departements.geojson": f"{FRANCE_GEOJSON_BASE}/departements.geojson",
    "regions.geojson": f"{FRANCE_GEOJSON_BASE}/regions.geojson",
}


@dataclass
class GeoCacheConfig:
    """Configuration for GeoCache."""

    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "tawiza" / "geo")
    files: dict[str, str] = field(default_factory=lambda: DEFAULT_FILES.copy())
    timeout: float = 30.0
    max_file_size: int = 10 * 1024 * 1024  # 10 MB


class GeoCache:
    """Adapter for managing GeoJSON cache."""

    def __init__(self, config: GeoCacheConfig | None = None):
        self.config = config or GeoCacheConfig()

    def cache_exists(self) -> bool:
        """Check if all cache files exist."""
        if not self.config.cache_dir.exists():
            return False
        return all(
            (self.config.cache_dir / filename).exists()
            for filename in self.config.files
        )

    def get_path(self, name: str) -> Path:
        """Get path to a cached file."""
        filename = f"{name}.geojson"
        return self.config.cache_dir / filename

    async def ensure_cache(self) -> dict[str, bool]:
        """Ensure all GeoJSON files are cached.

        Returns:
            Dict mapping filename to download success (True) or failure (False).
            Files that already exist are not included in the result.
        """
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)

        downloads = {}
        tasks = []
        filenames = []

        for filename, url in self.config.files.items():
            filepath = self.config.cache_dir / filename
            if not filepath.exists():
                tasks.append(self._download_file(url, filepath))
                filenames.append(filename)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for filename, result in zip(filenames, results, strict=False):
                if isinstance(result, Exception):
                    downloads[filename] = False
                    logger.error(f"Failed to download {filename}: {result}")
                else:
                    downloads[filename] = result

        return downloads

    async def _download_file(self, url: str, filepath: Path) -> bool:
        """Download a file from URL to filepath.

        Validates file size and JSON content before saving.
        Cleans up partial files on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Validate file size
                content = response.content
                if len(content) > self.config.max_file_size:
                    raise ValueError(
                        f"File size {len(content)} exceeds max {self.config.max_file_size}"
                    )

                # Validate JSON content
                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON content: {e}")

                # Write to file
                filepath.write_bytes(content)
                logger.info(f"Downloaded {filepath.name} ({len(content) / 1024:.1f} KB)")
                return True

        except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
            logger.error(f"Failed to download {url}: {e}")
            # Cleanup partial file if it exists
            if filepath.exists():
                with contextlib.suppress(OSError):
                    filepath.unlink()
            return False

    def clear_cache(self) -> None:
        """Clear all cached files.

        Only removes files specified in config.files.
        Handles deletion errors gracefully.
        """
        if not self.config.cache_dir.exists():
            return

        errors = []
        for filename in self.config.files:
            filepath = self.config.cache_dir / filename
            if filepath.exists():
                try:
                    filepath.unlink()
                except OSError as e:
                    errors.append(f"{filename}: {e}")
                    logger.error(f"Failed to delete {filepath}: {e}")

        if not errors:
            logger.info("GeoCache cleared")
        else:
            logger.warning(f"GeoCache partially cleared, {len(errors)} errors occurred")
