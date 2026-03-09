"""Tests for Settings configuration."""

from functools import lru_cache
from unittest.mock import patch

import pytest

from src.infrastructure.config.cache_config import CacheConfig, LFUCache
from src.infrastructure.config.settings import (
    DatabaseSettings,
    OllamaSettings,
    RedisSettings,
    SecuritySettings,
    Settings,
    get_settings,
)


class TestSettings:
    """Test Settings class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        # Clear environment variables that might override defaults
        with patch.dict("os.environ", {}, clear=True):
            settings = Settings()

            assert settings.app_name == "Tawiza"
            assert settings.app_env == "development"
            # debug depends on app_env being development
            assert settings.api_host == "0.0.0.0"
            assert settings.api_port == 8000

    def test_database_settings_defaults(self):
        """Test database settings defaults."""
        db_settings = DatabaseSettings()

        assert db_settings.pool_size == 10
        assert db_settings.max_overflow == 20
        assert db_settings.echo is False

    def test_redis_settings_defaults(self):
        """Test Redis settings defaults."""
        redis_settings = RedisSettings()

        assert redis_settings.max_connections == 50

    def test_ollama_settings_defaults(self):
        """Test Ollama settings defaults."""
        ollama_settings = OllamaSettings()

        assert ollama_settings.url == "http://localhost:11434"
        assert ollama_settings.timeout == 120
        assert ollama_settings.max_retries == 3
        assert ollama_settings.enable_cache is True

    def test_security_settings_validation(self):
        """Test security settings have minimum length."""
        security = SecuritySettings()

        assert len(security.secret_key) >= 32
        assert security.jwt_algorithm == "HS256"
        assert security.jwt_expiration_minutes == 60

    def test_is_production(self):
        """Test is_production property."""
        settings = Settings(app_env="production")
        assert settings.is_production is True

        settings = Settings(app_env="development")
        assert settings.is_production is False

    def test_is_development(self):
        """Test is_development property."""
        settings = Settings(app_env="development")
        assert settings.is_development is True

        settings = Settings(app_env="production")
        assert settings.is_development is False

    def test_nested_settings(self):
        """Test that nested settings are properly initialized."""
        settings = Settings()

        assert settings.database is not None
        assert settings.redis is not None
        assert settings.ollama is not None
        assert settings.security is not None
        assert settings.monitoring is not None


class TestGetSettings:
    """Test get_settings function."""

    def test_get_settings_returns_settings(self):
        """Test that get_settings returns a Settings instance."""
        # Clear cache first
        get_settings.cache_clear()

        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_is_cached(self):
        """Test that get_settings returns cached instance."""
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2


class TestCacheConfig:
    """Test CacheConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CacheConfig()

        assert config.max_size == 1000
        assert config.ttl_seconds == 3600
        assert config.cleanup_interval == 300
        assert config.lfu_threshold == 5

    def test_custom_values(self):
        """Test custom configuration values."""
        config = CacheConfig(max_size=500, ttl_seconds=1800, cleanup_interval=60, lfu_threshold=10)

        assert config.max_size == 500
        assert config.ttl_seconds == 1800
        assert config.cleanup_interval == 60
        assert config.lfu_threshold == 10


class TestLFUCache:
    """Test LFUCache class."""

    def test_put_and_get(self):
        """Test basic put and get operations."""
        cache = LFUCache(max_size=10)

        cache.put("key1", "value1")
        result = cache.get("key1")

        assert result == "value1"

    def test_get_missing_key(self):
        """Test get returns None for missing key."""
        cache = LFUCache(max_size=10)

        result = cache.get("nonexistent")

        assert result is None

    def test_frequency_tracking(self):
        """Test that access frequency is tracked."""
        cache = LFUCache(max_size=10)

        cache.put("key1", "value1")

        # Access multiple times
        cache.get("key1")
        cache.get("key1")
        cache.get("key1")

        # Frequency should be 4 (1 put + 3 gets)
        assert cache.frequency["key1"] == 4

    def test_eviction_when_full(self):
        """Test LFU eviction when cache is full."""
        cache = LFUCache(max_size=3)

        # Add 3 items
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        # Access key2 and key3 more frequently
        cache.get("key2")
        cache.get("key2")
        cache.get("key3")

        # Add 4th item - should evict key1 (least frequently used)
        cache.put("key4", "value4")

        # key1 should be evicted
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_update_existing_key(self):
        """Test updating an existing key."""
        cache = LFUCache(max_size=10)

        cache.put("key1", "value1")
        cache.put("key1", "value2")

        result = cache.get("key1")

        assert result == "value2"
        # Frequency should be 3 (2 puts + 1 get)
        assert cache.frequency["key1"] == 3

    def test_thread_safety(self):
        """Test that cache operations are thread-safe."""
        import threading

        cache = LFUCache(max_size=100)
        errors = []

        def writer():
            try:
                for i in range(100):
                    cache.put(f"key{i}", f"value{i}")
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    cache.get(f"key{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
