"""
Configuration avancée du cache pour les performances Tawiza-V2.
Implémente un système de cache multi-niveau avec LFU et LRU.
"""

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class CacheConfig:
    """Configuration du cache."""

    max_size: int = 1000
    ttl_seconds: int = 3600  # 1 heure par défaut
    cleanup_interval: int = 300  # 5 minutes
    lfu_threshold: int = 5  # Nombre d'accès minimum pour LFU


class LFUCache:
    """Cache LFU (Least Frequently Used) pour les données fréquemment accédées."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: dict[str, Any] = {}  # key -> value
        self.frequency: dict[str, int] = {}  # key -> access count
        self.access_time: dict[str, float] = {}  # key -> last access time
        self.lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        """Récupère une valeur du cache LFU."""
        with self.lock:
            if key in self.cache:
                self.frequency[key] += 1
                self.access_time[key] = time.time()
                logger.debug(f"LFU Cache HIT: {key}")
                return self.cache[key]
            logger.debug(f"LFU Cache MISS: {key}")
            return None

    def put(self, key: str, value: Any, ttl: int = 3600):
        """Ajoute une valeur au cache LFU."""
        with self.lock:
            if key in self.cache:
                self.cache[key] = value
                self.frequency[key] += 1
                self.access_time[key] = time.time()
                return

            # Nettoyer les entrées expirées
            self._cleanup_expired(ttl)

            # Si le cache est plein, éjecter la moins fréquemment utilisée
            if len(self.cache) >= self.max_size:
                self._evict_lfu()

            self.cache[key] = value
            self.frequency[key] = 1
            self.access_time[key] = time.time()
            logger.debug(f"LFU Cache PUT: {key}")

    def _cleanup_expired(self, ttl: int):
        """Nettoie les entrées expirées."""
        current_time = time.time()
        expired_keys = [
            key for key, access_time in self.access_time.items() if current_time - access_time > ttl
        ]
        for key in expired_keys:
            self._remove_key(key)

    def _evict_lfu(self):
        """Éjecte l'élément avec la fréquence la plus basse."""
        if not self.frequency:
            return

        # Trouver la clé avec la fréquence la plus basse
        min_freq = min(self.frequency.values())
        lfu_keys = [key for key, freq in self.frequency.items() if freq == min_freq]

        # Parmi les LFU, éjecter le plus ancien (LRU)
        oldest_key = min(lfu_keys, key=lambda k: self.access_time[k])
        self._remove_key(oldest_key)
        logger.debug(f"LFU Cache EVICT: {oldest_key} (freq={min_freq})")

    def _remove_key(self, key: str):
        """Supprime une clé du cache."""
        self.cache.pop(key, None)
        self.frequency.pop(key, None)
        self.access_time.pop(key, None)

    def clear(self):
        """Vide le cache."""
        with self.lock:
            self.cache.clear()
            self.frequency.clear()
            self.access_time.clear()
            logger.info("LFU Cache cleared")

    def stats(self) -> dict[str, Any]:
        """Retourne les statistiques du cache."""
        with self.lock:
            total_freq = sum(self.frequency.values())
            avg_freq = total_freq / len(self.frequency) if self.frequency else 0

            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "total_accesses": total_freq,
                "average_frequency": avg_freq,
                "keys": list(self.cache.keys()),
            }


class LRUCache:
    """Cache LRU (Least Recently Used) pour les données temporaires."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        """Récupère une valeur du cache LRU."""
        with self.lock:
            if key in self.cache:
                # Déplacer au début (plus récemment utilisé)
                self.cache.move_to_end(key, last=False)
                logger.debug(f"LRU Cache HIT: {key}")
                return self.cache[key]
            logger.debug(f"LRU Cache MISS: {key}")
            return None

    def put(self, key: str, value: Any):
        """Ajoute une valeur au cache LRU."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key, last=False)
            else:
                if len(self.cache) >= self.max_size:
                    # Éjecter le dernier élément (le moins récemment utilisé)
                    evicted = self.cache.popitem(last=True)
                    logger.debug(f"LRU Cache EVICT: {evicted[0]}")

                self.cache[key] = value
                self.cache.move_to_end(key, last=False)
                logger.debug(f"LRU Cache PUT: {key}")

    def clear(self):
        """Vide le cache."""
        with self.lock:
            self.cache.clear()
            logger.info("LRU Cache cleared")

    def stats(self) -> dict[str, Any]:
        """Retourne les statistiques du cache."""
        with self.lock:
            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "keys": list(self.cache.keys()),
            }


class MultiLevelCache:
    """Cache multi-niveau combinant LFU et LRU pour des performances optimales."""

    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self.lfu_cache = LFUCache(max_size=self.config.max_size // 2)
        self.lru_cache = LRUCache(max_size=self.config.max_size // 2)
        self.cleanup_thread = None
        self._start_cleanup_thread()

    def get(self, key: str) -> Any | None:
        """Récupère une valeur du cache multi-niveau."""
        # Essayer LFU d'abord (données fréquemment accédées)
        value = self.lfu_cache.get(key)
        if value is not None:
            return value

        # Ensayer LRU (données récentes)
        value = self.lru_cache.get(key)
        if value is not None:
            # Promouvoir vers LFU si fréquemment accédé
            self._promote_to_lfu(key, value)
            return value

        return None

    def put(self, key: str, value: Any, use_lfu: bool = False):
        """Ajoute une valeur au cache multi-niveau."""
        if use_lfu or self._should_use_lfu(key):
            self.lfu_cache.put(key, value, self.config.ttl_seconds)
        else:
            self.lru_cache.put(key, value)

    def _should_use_lfu(self, key: str) -> bool:
        """Détermine si une clé devrait utiliser LFU basé sur les patterns d'accès."""
        # Simple heuristique : les clés avec "model", "prediction", "embedding"
        # sont généralement fréquemment accédées
        lfu_keywords = ["model", "prediction", "embedding", "vector", "dataset"]
        return any(keyword in key.lower() for keyword in lfu_keywords)

    def _promote_to_lfu(self, key: str, value: Any):
        """Promouvoir une entrée de LRU vers LFU."""
        # Vérifier si elle devrait être promue (accès multiple)
        # Pour l'instant, on promouvoie toujours
        self.lfu_cache.put(key, value, self.config.ttl_seconds)

    def _start_cleanup_thread(self):
        """Démarre le thread de nettoyage périodique."""

        def cleanup_loop():
            while True:
                time.sleep(self.config.cleanup_interval)
                try:
                    self._cleanup()
                except Exception as e:
                    logger.error(f"Error during cache cleanup: {e}")

        self.cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        logger.info("Cache cleanup thread started")

    def _cleanup(self):
        """Nettoyage périodique du cache."""
        # Le LFU gère son propre nettoyage via TTL
        # Pour LRU, on peut implémenter un TTL si nécessaire
        logger.debug("Cache cleanup completed")

    def clear_all(self):
        """Vide tous les caches."""
        self.lfu_cache.clear()
        self.lru_cache.clear()
        logger.info("All caches cleared")

    def get_stats(self) -> dict[str, Any]:
        """Retourne les statistiques de tous les caches."""
        return {
            "lfu_cache": self.lfu_cache.stats(),
            "lru_cache": self.lru_cache.stats(),
            "total_size": (self.lfu_cache.stats()["size"] + self.lru_cache.stats()["size"]),
            "total_capacity": self.config.max_size,
        }


# Instance globale du cache multi-niveau
cache = MultiLevelCache()


def get_cache() -> MultiLevelCache:
    """Retourne l'instance globale du cache."""
    return cache
