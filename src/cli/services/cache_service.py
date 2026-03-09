#!/usr/bin/env python3
"""
Service de cache pour Tawiza-V2 CLI

Fournit un cache thread-safe avec:
- TTL configurable par entrée
- Invalidation automatique
- Statistiques d'utilisation
- Support async
"""
from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, TypeVar

from loguru import logger

T = TypeVar('T')


# ==============================================================================
# CONSTANTES
# ==============================================================================

DEFAULT_TTL = 300  # 5 minutes
DEFAULT_MAX_SIZE = 1000
CLEANUP_INTERVAL = 60  # 1 minute


# ==============================================================================
# MODÈLES
# ==============================================================================

@dataclass
class CacheEntry[T]:
    """Entrée de cache avec métadonnées"""
    key: str
    value: T
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(seconds=DEFAULT_TTL))
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)

    def is_expired(self) -> bool:
        """Vérifier si l'entrée est expirée"""
        return datetime.now() >= self.expires_at

    def touch(self) -> None:
        """Mettre à jour les métadonnées d'accès"""
        self.access_count += 1
        self.last_accessed = datetime.now()

    def ttl_remaining(self) -> float:
        """Temps restant avant expiration (secondes)"""
        remaining = (self.expires_at - datetime.now()).total_seconds()
        return max(0, remaining)


@dataclass
class CacheStats:
    """Statistiques du cache"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        """Taux de succès du cache"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convertir en dictionnaire"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "size": self.size,
            "hit_rate": f"{self.hit_rate:.2%}"
        }


# ==============================================================================
# SERVICE DE CACHE
# ==============================================================================

class CacheService:
    """Service de cache thread-safe avec support async"""

    def __init__(
        self,
        default_ttl: int = DEFAULT_TTL,
        max_size: int = DEFAULT_MAX_SIZE,
        cleanup_interval: int = CLEANUP_INTERVAL
    ):
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._cleanup_interval = cleanup_interval
        self._stats = CacheStats()
        self._cleanup_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Démarrer le service de nettoyage automatique"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.debug("Cache cleanup task started")

    async def stop(self) -> None:
        """Arrêter le service"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None
            logger.debug("Cache cleanup task stopped")

    async def _cleanup_loop(self) -> None:
        """Boucle de nettoyage automatique"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")

    async def _cleanup_expired(self) -> int:
        """Nettoyer les entrées expirées"""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]
                self._stats.expirations += 1

            self._stats.size = len(self._cache)

            if expired_keys:
                logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")

            return len(expired_keys)

    async def get(self, key: str) -> Any | None:
        """Récupérer une valeur du cache"""
        async with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._stats.expirations += 1
                self._stats.misses += 1
                self._stats.size = len(self._cache)
                return None

            entry.touch()
            self._stats.hits += 1
            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None
    ) -> None:
        """Stocker une valeur dans le cache"""
        async with self._lock:
            # Vérifier la taille max
            if len(self._cache) >= self._max_size and key not in self._cache:
                await self._evict_lru()

            ttl_seconds = ttl if ttl is not None else self._default_ttl
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

            self._cache[key] = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at
            )
            self._stats.size = len(self._cache)

    async def _evict_lru(self) -> None:
        """Évincer l'entrée la moins récemment utilisée"""
        if not self._cache:
            return

        # Trouver l'entrée LRU
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_accessed
        )

        del self._cache[lru_key]
        self._stats.evictions += 1
        logger.debug(f"Evicted LRU cache entry: {lru_key}")

    async def delete(self, key: str) -> bool:
        """Supprimer une entrée du cache"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.size = len(self._cache)
                return True
            return False

    async def clear(self) -> None:
        """Vider tout le cache"""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats.size = 0
            logger.info(f"Cache cleared ({count} entries)")

    async def has(self, key: str) -> bool:
        """Vérifier si une clé existe et n'est pas expirée"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._cache[key]
                self._stats.expirations += 1
                return False
            return True

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int | None = None
    ) -> Any:
        """Récupérer du cache ou créer avec factory"""
        value = await self.get(key)
        if value is not None:
            return value

        # Créer la valeur
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        await self.set(key, value, ttl)
        return value

    def get_stats(self) -> CacheStats:
        """Obtenir les statistiques du cache"""
        return self._stats

    async def get_info(self, key: str) -> dict[str, Any] | None:
        """Obtenir les informations d'une entrée"""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None or entry.is_expired():
                return None

            return {
                "key": entry.key,
                "created_at": entry.created_at.isoformat(),
                "expires_at": entry.expires_at.isoformat(),
                "ttl_remaining": entry.ttl_remaining(),
                "access_count": entry.access_count,
                "last_accessed": entry.last_accessed.isoformat()
            }

    async def keys(self) -> list:
        """Obtenir toutes les clés non expirées"""
        async with self._lock:
            return [
                key for key, entry in self._cache.items()
                if not entry.is_expired()
            ]


# ==============================================================================
# DÉCORATEUR DE CACHE
# ==============================================================================

def cached(
    ttl: int = DEFAULT_TTL,
    key_prefix: str = "",
    cache_service: CacheService | None = None
):
    """Décorateur pour mettre en cache les résultats d'une fonction"""

    def decorator(func: Callable):
        _cache = cache_service or CacheService()

        async def async_wrapper(*args, **kwargs):
            # Générer la clé de cache
            cache_key = f"{key_prefix}:{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"

            # Vérifier le cache
            cached_value = await _cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Exécuter la fonction
            result = await func(*args, **kwargs)

            # Mettre en cache
            await _cache.set(cache_key, result, ttl)

            return result

        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ==============================================================================
# INSTANCE SINGLETON
# ==============================================================================

_cache_service: CacheService | None = None


async def get_cache_service() -> CacheService:
    """Obtenir l'instance du service de cache"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.start()
    return _cache_service
