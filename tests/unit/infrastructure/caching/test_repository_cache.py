"""Tests for repository cache wrappers and decorators."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.infrastructure.caching.repository_cache import (
    CachedDatasetRepository,
    CachedMLModelRepository,
    CachedRepositoryMixin,
    CacheKeyBuilder,
    cache_query,
    close_repository_cache,
    get_repository_cache,
    init_repository_cache,
    invalidate_cache,
)


class TestCacheKeyBuilder:
    """Test suite for CacheKeyBuilder."""

    def test_basic_key_building(self):
        """Test building simple cache keys."""
        key = CacheKeyBuilder("models").add("get_by_id").add("123").build()

        assert key == "models:get_by_id:123"

    def test_uuid_handling(self):
        """UUIDs should be converted to strings."""
        test_uuid = uuid4()
        key = CacheKeyBuilder("models").add("get_by_id").add(test_uuid).build()

        assert str(test_uuid) in key

    def test_none_handling(self):
        """None values should be represented as 'null'."""
        key = CacheKeyBuilder("models").add("get_by_status").add(None).build()

        assert "null" in key

    def test_dict_hashing(self):
        """Dict values should be hashed for consistent keys."""
        params = {"page": 1, "size": 10}
        key = CacheKeyBuilder("models").add("list").add(params).build()

        # Should produce consistent hash
        key2 = CacheKeyBuilder("models").add("list").add(params).build()
        assert key == key2

    def test_empty_prefix(self):
        """Empty prefix should work."""
        key = CacheKeyBuilder().add("method").add("arg").build()

        assert key == "method:arg"

    def test_from_method_basic(self):
        """Test from_method class method."""
        key = CacheKeyBuilder.from_method("models", "get_by_id", "model-123")

        assert key == "models:get_by_id:model-123"

    def test_from_method_with_kwargs(self):
        """Test from_method with keyword arguments."""
        key = CacheKeyBuilder.from_method(
            "models",
            "list",
            skip=0,
            limit=10,
        )

        assert "models:list" in key
        assert "skip=0" in key
        assert "limit=10" in key

    def test_chaining(self):
        """Test method chaining."""
        builder = CacheKeyBuilder("prefix")
        result = builder.add("a").add("b").add("c")

        assert result is builder  # Same object returned
        assert builder.build() == "prefix:a:b:c"


class TestCachedMLModelRepository:
    """Test suite for CachedMLModelRepository wrapper."""

    @pytest.fixture
    def mock_repo(self):
        """Create mock repository."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=MagicMock(id=uuid4()))
        repo.get_all = AsyncMock(return_value=[MagicMock(id=uuid4())])
        repo.save = AsyncMock(return_value=MagicMock(id=uuid4()))
        repo.delete = AsyncMock(return_value=True)
        repo.some_other_method = MagicMock(return_value="proxied")
        return repo

    @pytest.fixture
    def cached_repo(self, mock_repo):
        """Create cached repository wrapper."""
        return CachedMLModelRepository(mock_repo, cache_ttl=60, cache_prefix="test_models")

    def test_initialization(self, cached_repo, mock_repo):
        """Test repository initialization."""
        assert cached_repo._repo is mock_repo
        assert cached_repo._cache_ttl == 60
        assert cached_repo._cache_prefix == "test_models"

    @pytest.mark.asyncio
    async def test_get_by_id_cache_miss(self, cached_repo, mock_repo):
        """First call should hit the database."""
        model_id = uuid4()

        with patch.object(cached_repo, "_build_key", return_value="test_key"):
            with patch(
                "src.infrastructure.caching.repository_cache.get_repository_cache"
            ) as mock_cache:
                cache = MagicMock()
                cache.get_async = AsyncMock(return_value=None)  # Cache miss
                cache.put_async = AsyncMock()
                mock_cache.return_value = cache

                result = await cached_repo.get_by_id(model_id)

                # Should have called the underlying repo
                mock_repo.get_by_id.assert_called_once_with(model_id)
                # Should have cached the result
                cache.put_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_id_cache_hit(self, cached_repo, mock_repo):
        """Cached results should not hit the database."""
        model_id = uuid4()
        cached_model = MagicMock(id=model_id)

        with patch.object(cached_repo, "_build_key", return_value="test_key"):
            with patch(
                "src.infrastructure.caching.repository_cache.get_repository_cache"
            ) as mock_cache:
                cache = MagicMock()
                cache.get_async = AsyncMock(return_value=cached_model)  # Cache hit
                mock_cache.return_value = cache

                result = await cached_repo.get_by_id(model_id)

                # Should NOT have called the underlying repo
                mock_repo.get_by_id.assert_not_called()
                # Result should be the cached model
                assert result is cached_model

    @pytest.mark.asyncio
    async def test_save_invalidates_cache(self, cached_repo, mock_repo):
        """Save should invalidate the cache for that entity."""
        entity = MagicMock(id=uuid4())

        with patch(
            "src.infrastructure.caching.repository_cache.get_repository_cache"
        ) as mock_cache:
            cache = MagicMock()
            cache.delete_async = AsyncMock()
            mock_cache.return_value = cache

            await cached_repo.save(entity)

            # Should have called underlying save
            mock_repo.save.assert_called_once_with(entity)
            # Should have invalidated cache
            cache.delete_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_invalidates_cache(self, cached_repo, mock_repo):
        """Delete should invalidate the cache if successful."""
        entity_id = uuid4()

        with patch(
            "src.infrastructure.caching.repository_cache.get_repository_cache"
        ) as mock_cache:
            cache = MagicMock()
            cache.delete_async = AsyncMock()
            mock_cache.return_value = cache

            result = await cached_repo.delete(entity_id)

            assert result is True
            cache.delete_async.assert_called_once()

    def test_proxy_pattern(self, cached_repo, mock_repo):
        """Unknown methods should be proxied to wrapped repository."""
        result = cached_repo.some_other_method()

        assert result == "proxied"
        mock_repo.some_other_method.assert_called_once()


class TestCachedDatasetRepository:
    """Test suite for CachedDatasetRepository wrapper."""

    @pytest.fixture
    def mock_repo(self):
        """Create mock dataset repository."""
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=MagicMock(id=uuid4()))
        repo.get_all = AsyncMock(return_value=[MagicMock()])
        repo.get_by_status = AsyncMock(return_value=[MagicMock()])
        repo.save = AsyncMock(return_value=MagicMock(id=uuid4()))
        repo.delete = AsyncMock(return_value=True)
        return repo

    @pytest.fixture
    def cached_repo(self, mock_repo):
        """Create cached dataset repository wrapper."""
        return CachedDatasetRepository(mock_repo, cache_ttl=120, cache_prefix="test_datasets")

    def test_initialization(self, cached_repo, mock_repo):
        """Test repository initialization."""
        assert cached_repo._repo is mock_repo
        assert cached_repo._cache_ttl == 120
        assert cached_repo._cache_prefix == "test_datasets"

    @pytest.mark.asyncio
    async def test_get_by_status_caching(self, cached_repo, mock_repo):
        """get_by_status should use caching."""
        from enum import Enum

        class Status(Enum):
            READY = "ready"

        with patch(
            "src.infrastructure.caching.repository_cache.get_repository_cache"
        ) as mock_cache:
            cache = MagicMock()
            cache.get_async = AsyncMock(return_value=None)  # Cache miss
            cache.put_async = AsyncMock()
            mock_cache.return_value = cache

            result = await cached_repo.get_by_status(Status.READY, skip=0, limit=10)

            mock_repo.get_by_status.assert_called_once()
            cache.put_async.assert_called_once()


class TestCacheQueryDecorator:
    """Test suite for @cache_query decorator."""

    @pytest.mark.asyncio
    async def test_cache_query_decorator(self):
        """Test the cache_query decorator."""

        class TestRepo:
            @cache_query(ttl=60, key_prefix="test")
            async def get_item(self, item_id: str):
                return {"id": item_id, "name": "test"}

        with patch(
            "src.infrastructure.caching.repository_cache.get_repository_cache"
        ) as mock_cache:
            cache = MagicMock()
            cache.get_async = AsyncMock(return_value=None)  # Cache miss
            cache.put_async = AsyncMock()
            mock_cache.return_value = cache

            repo = TestRepo()
            result = await repo.get_item("123")

            assert result["id"] == "123"
            cache.put_async.assert_called_once()


class TestRepositoryCacheLifecycle:
    """Test suite for repository cache lifecycle functions."""

    @pytest.mark.asyncio
    async def test_init_repository_cache(self):
        """Test initializing repository cache."""
        cache = await init_repository_cache(
            l1_capacity=100,
            l2_capacity=500,
            enable_redis=False,
        )

        assert cache is not None

    @pytest.mark.asyncio
    async def test_close_repository_cache(self):
        """Test closing repository cache."""
        # First init
        await init_repository_cache()

        # Then close
        await close_repository_cache()

        # Should not raise

    def test_get_repository_cache_creates_default(self):
        """get_repository_cache should create default cache if not initialized."""
        # Reset global cache
        import src.infrastructure.caching.repository_cache as rc

        rc._repository_cache = None

        cache = get_repository_cache()

        assert cache is not None
