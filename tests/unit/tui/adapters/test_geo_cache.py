"""Tests for GeoCache adapter."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.cli.v3.tui.adapters.geo_cache import GeoCache, GeoCacheConfig


class TestGeoCacheConfig:
    """Test GeoCache configuration."""

    def test_default_cache_dir(self):
        """Default cache directory is ~/.cache/tawiza/geo."""
        config = GeoCacheConfig()
        assert config.cache_dir == Path.home() / ".cache" / "tawiza" / "geo"

    def test_custom_cache_dir(self):
        """Custom cache directory can be specified."""
        config = GeoCacheConfig(cache_dir=Path("/tmp/geo"))
        assert config.cache_dir == Path("/tmp/geo")

    def test_default_files(self):
        """Default files include departements and regions."""
        config = GeoCacheConfig()
        assert "departements.geojson" in config.files
        assert "regions.geojson" in config.files


class TestGeoCache:
    """Test GeoCache adapter."""

    def test_cache_exists_when_files_present(self, tmp_path):
        """Cache exists returns True when all files present."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        (tmp_path / "departements.geojson").write_text("{}")
        (tmp_path / "regions.geojson").write_text("{}")

        cache = GeoCache(config)
        assert cache.cache_exists() is True

    def test_cache_exists_when_files_missing(self, tmp_path):
        """Cache exists returns False when files missing."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)
        assert cache.cache_exists() is False

    def test_get_departements_path(self, tmp_path):
        """Get departements path returns correct path."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)
        assert cache.get_path("departements") == tmp_path / "departements.geojson"

    def test_get_regions_path(self, tmp_path):
        """Get regions path returns correct path."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)
        assert cache.get_path("regions") == tmp_path / "regions.geojson"

    def test_get_arbitrary_name_path(self, tmp_path):
        """Get path works with arbitrary names."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)
        assert cache.get_path("custom") == tmp_path / "custom.geojson"

    @pytest.mark.asyncio
    async def test_ensure_cache_creates_directory(self, tmp_path):
        """Ensure cache creates directory if not exists."""
        cache_dir = tmp_path / "new_cache"
        config = GeoCacheConfig(cache_dir=cache_dir)
        cache = GeoCache(config)

        with patch.object(cache, "_download_file") as mock_download:
            mock_download.return_value = True
            await cache.ensure_cache()

        assert cache_dir.exists()

    @pytest.mark.asyncio
    async def test_ensure_cache_when_files_exist(self, tmp_path):
        """Ensure cache returns empty dict when files already exist."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        (tmp_path / "departements.geojson").write_text("{}")
        (tmp_path / "regions.geojson").write_text("{}")

        cache = GeoCache(config)
        result = await cache.ensure_cache()

        assert result == {}

    @pytest.mark.asyncio
    async def test_ensure_cache_returns_success_status(self, tmp_path):
        """Ensure cache returns dict with download status."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)

        with patch.object(cache, "_download_file") as mock_download:
            mock_download.return_value = True
            result = await cache.ensure_cache()

        assert result == {
            "departements.geojson": True,
            "regions.geojson": True,
        }

    @pytest.mark.asyncio
    async def test_ensure_cache_partial_failure(self, tmp_path):
        """Ensure cache reports partial failures correctly."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)

        async def mock_download(url, filepath):
            if "departements" in str(filepath):
                return True
            return False

        with patch.object(cache, "_download_file", side_effect=mock_download):
            result = await cache.ensure_cache()

        assert result["departements.geojson"] is True
        assert result["regions.geojson"] is False

    @pytest.mark.asyncio
    async def test_ensure_cache_handles_exceptions(self, tmp_path):
        """Ensure cache handles exceptions gracefully."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)

        async def mock_download(url, filepath):
            if "departements" in str(filepath):
                raise httpx.TimeoutException("Connection timeout")
            return True

        with patch.object(cache, "_download_file", side_effect=mock_download):
            result = await cache.ensure_cache()

        assert result["departements.geojson"] is False
        assert result["regions.geojson"] is True

    @pytest.mark.asyncio
    async def test_download_file_success(self, tmp_path):
        """Download file successfully downloads and validates content."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)
        filepath = tmp_path / "test.geojson"

        valid_json = json.dumps({"type": "FeatureCollection", "features": []})
        mock_response = MagicMock()
        mock_response.content = valid_json.encode()
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await cache._download_file("http://example.com/test.json", filepath)

        assert result is True
        assert filepath.exists()
        assert json.loads(filepath.read_text()) == json.loads(valid_json)

    @pytest.mark.asyncio
    async def test_download_file_invalid_json(self, tmp_path):
        """Download file fails on invalid JSON."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)
        filepath = tmp_path / "test.geojson"

        mock_response = MagicMock()
        mock_response.content = b"not valid json"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await cache._download_file("http://example.com/test.json", filepath)

        assert result is False
        assert not filepath.exists()

    @pytest.mark.asyncio
    async def test_download_file_size_limit(self, tmp_path):
        """Download file fails when size exceeds limit."""
        config = GeoCacheConfig(cache_dir=tmp_path, max_file_size=100)
        cache = GeoCache(config)
        filepath = tmp_path / "test.geojson"

        large_json = json.dumps({"data": "x" * 200})
        mock_response = MagicMock()
        mock_response.content = large_json.encode()
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await cache._download_file("http://example.com/test.json", filepath)

        assert result is False
        assert not filepath.exists()

    @pytest.mark.asyncio
    async def test_download_file_http_error(self, tmp_path):
        """Download file handles HTTP errors."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)
        filepath = tmp_path / "test.geojson"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock())
        )

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await cache._download_file("http://example.com/test.json", filepath)

        assert result is False
        assert not filepath.exists()

    @pytest.mark.asyncio
    async def test_download_file_timeout(self, tmp_path):
        """Download file handles timeout errors."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)
        filepath = tmp_path / "test.geojson"

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await cache._download_file("http://example.com/test.json", filepath)

        assert result is False
        assert not filepath.exists()

    @pytest.mark.asyncio
    async def test_download_file_cleanup_on_failure(self, tmp_path):
        """Download file cleans up partial file on failure."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        cache = GeoCache(config)
        filepath = tmp_path / "test.geojson"

        # Create a partial file
        filepath.write_text("partial")

        mock_response = MagicMock()
        mock_response.content = b"not valid json"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await cache._download_file("http://example.com/test.json", filepath)

        assert result is False
        # File should be cleaned up
        assert not filepath.exists()

    def test_clear_cache_removes_files(self, tmp_path):
        """Clear cache removes all configured files."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        (tmp_path / "departements.geojson").write_text("{}")
        (tmp_path / "regions.geojson").write_text("{}")
        # Create a file not in config
        (tmp_path / "other.geojson").write_text("{}")

        cache = GeoCache(config)
        cache.clear_cache()

        assert not (tmp_path / "departements.geojson").exists()
        assert not (tmp_path / "regions.geojson").exists()
        # Other file should still exist
        assert (tmp_path / "other.geojson").exists()

    def test_clear_cache_no_directory(self, tmp_path):
        """Clear cache handles non-existent directory gracefully."""
        cache_dir = tmp_path / "nonexistent"
        config = GeoCacheConfig(cache_dir=cache_dir)
        cache = GeoCache(config)

        # Should not raise
        cache.clear_cache()

    def test_clear_cache_handles_deletion_errors(self, tmp_path):
        """Clear cache handles file deletion errors."""
        config = GeoCacheConfig(cache_dir=tmp_path)
        (tmp_path / "departements.geojson").write_text("{}")
        (tmp_path / "regions.geojson").write_text("{}")

        cache = GeoCache(config)

        # Mock unlink to raise OSError on first file only
        original_unlink = Path.unlink
        call_count = [0]

        def mock_unlink(self, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise OSError("Permission denied")
            return original_unlink(self, *args, **kwargs)

        with patch.object(Path, "unlink", mock_unlink):
            cache.clear_cache()

        # First file should still exist due to error
        assert (tmp_path / "departements.geojson").exists()
        # Second file should be deleted
        assert not (tmp_path / "regions.geojson").exists()
