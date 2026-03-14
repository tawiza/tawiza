#!/usr/bin/env python3
"""
Result Cache System pour Multi-Agent Optimization
Système de cache intelligent pour les résultats des agents
"""

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class CacheStrategy(Enum):
    """Stratégies de cache"""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    FIFO = "fifo"  # First In First Out


@dataclass
class CacheEntry:
    """Entrée de cache"""

    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    ttl: float | None = None  # Time to live en secondes
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """Vérifier si l'entrée est expirée"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def access(self):
        """Enregistrer un accès"""
        self.last_accessed = time.time()
        self.access_count += 1


class LRUCache:
    """Cache LRU (Least Recently Used)"""

    def __init__(self, max_size: int = 1000, max_memory_mb: float = 100.0):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.current_memory = 0
        self._lock = asyncio.Lock()
        self.hits = 0
        self.misses = 0

    async def get(self, key: str) -> Any | None:
        """Récupérer une valeur du cache"""
        async with self._lock:
            if key not in self.cache:
                self.misses += 1
                return None

            entry = self.cache[key]

            # Vérifier si l'entrée est expirée
            if entry.is_expired():
                await self._remove(key)
                self.misses += 1
                return None

            # Déplacer à la fin (plus récent)
            self.cache.move_to_end(key)
            entry.access()
            self.hits += 1

            return entry.value

    async def put(self, key: str, value: Any, ttl: float | None = None):
        """Ajouter une valeur au cache"""
        async with self._lock:
            # Calculer la taille
            value_size = len(json.dumps(value, default=str).encode("utf-8"))

            # Supprimer l'ancienne valeur si elle existe
            if key in self.cache:
                await self._remove(key)

            # Éviction si nécessaire
            while (
                len(self.cache) >= self.max_size
                or self.current_memory + value_size > self.max_memory_bytes
            ):
                if not self.cache:
                    break
                # Supprimer l'entrée la moins récente (début de l'OrderedDict)
                oldest_key = next(iter(self.cache))
                await self._remove(oldest_key)

            # Ajouter la nouvelle entrée
            entry = CacheEntry(key=key, value=value, ttl=ttl, size_bytes=value_size)

            self.cache[key] = entry
            self.current_memory += value_size

    async def _remove(self, key: str):
        """Supprimer une entrée du cache"""
        if key in self.cache:
            entry = self.cache.pop(key)
            self.current_memory -= entry.size_bytes

    async def clear(self):
        """Vider le cache"""
        async with self._lock:
            self.cache.clear()
            self.current_memory = 0
            self.hits = 0
            self.misses = 0

    async def get_stats(self) -> dict[str, Any]:
        """Obtenir les statistiques du cache"""
        async with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "memory_usage_mb": self.current_memory / (1024 * 1024),
                "max_memory_mb": self.max_memory_bytes / (1024 * 1024),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "utilization": len(self.cache) / self.max_size * 100,
            }


class AgentResultCache:
    """Cache spécialisé pour les résultats des agents"""

    def __init__(
        self, max_size: int = 1000, max_memory_mb: float = 100.0, default_ttl: float = 3600.0
    ):
        self.lru_cache = LRUCache(max_size, max_memory_mb)
        self.default_ttl = default_ttl
        self.cache_by_agent: dict[str, list[str]] = {}
        self._lock = asyncio.Lock()

    def _generate_cache_key(
        self, agent_type: str, task_type: str, parameters: dict[str, Any]
    ) -> str:
        """Générer une clé de cache unique"""
        # Créer une chaîne déterministe à partir des paramètres
        param_str = json.dumps(parameters, sort_keys=True, default=str)

        # Hash pour une clé courte
        key_input = f"{agent_type}:{task_type}:{param_str}"
        key_hash = hashlib.sha256(key_input.encode()).hexdigest()[:16]

        return f"{agent_type}:{task_type}:{key_hash}"

    async def get_result(
        self, agent_type: str, task_type: str, parameters: dict[str, Any]
    ) -> Any | None:
        """Récupérer un résultat en cache"""
        key = self._generate_cache_key(agent_type, task_type, parameters)
        result = await self.lru_cache.get(key)

        if result is not None:
            logger.info(f"✅ Cache hit: {agent_type}/{task_type}")
        else:
            logger.debug(f"❌ Cache miss: {agent_type}/{task_type}")

        return result

    async def cache_result(
        self,
        agent_type: str,
        task_type: str,
        parameters: dict[str, Any],
        result: Any,
        ttl: float | None = None,
    ):
        """Mettre en cache un résultat"""
        key = self._generate_cache_key(agent_type, task_type, parameters)
        cache_ttl = ttl if ttl is not None else self.default_ttl

        await self.lru_cache.put(key, result, ttl=cache_ttl)

        # Enregistrer l'association agent -> clé
        async with self._lock:
            if agent_type not in self.cache_by_agent:
                self.cache_by_agent[agent_type] = []
            self.cache_by_agent[agent_type].append(key)

        logger.info(f"💾 Résultat mis en cache: {agent_type}/{task_type} (TTL: {cache_ttl}s)")

    async def invalidate_agent_cache(self, agent_type: str):
        """Invalider tous les résultats en cache pour un agent"""
        async with self._lock:
            keys = self.cache_by_agent.get(agent_type, [])

            for key in keys:
                await self.lru_cache._remove(key)

            if agent_type in self.cache_by_agent:
                del self.cache_by_agent[agent_type]

        logger.info(f"🗑️ Cache invalidé pour: {agent_type}")

    async def get_stats(self) -> dict[str, Any]:
        """Obtenir les statistiques du cache"""
        cache_stats = await self.lru_cache.get_stats()

        async with self._lock:
            agent_counts = {agent: len(keys) for agent, keys in self.cache_by_agent.items()}

        return {**cache_stats, "agents": agent_counts, "total_agents": len(self.cache_by_agent)}

    async def clear(self):
        """Vider complètement le cache"""
        await self.lru_cache.clear()

        async with self._lock:
            self.cache_by_agent.clear()

        logger.info("🗑️ Cache complètement vidé")


class SmartCache:
    """Cache intelligent avec prédiction et pré-chargement"""

    def __init__(self, agent_cache: AgentResultCache):
        self.agent_cache = agent_cache
        self.access_patterns: dict[str, list[tuple[float, str]]] = {}
        self.prediction_threshold = 0.7
        self._lock = asyncio.Lock()

    async def record_access(self, agent_type: str, task_type: str):
        """Enregistrer un accès pour analyse"""
        async with self._lock:
            pattern_key = f"{agent_type}:{task_type}"

            if pattern_key not in self.access_patterns:
                self.access_patterns[pattern_key] = []

            self.access_patterns[pattern_key].append((time.time(), pattern_key))

            # Garder seulement les 100 derniers accès
            self.access_patterns[pattern_key] = self.access_patterns[pattern_key][-100:]

    async def predict_next_tasks(self, agent_type: str) -> list[str]:
        """Prédire les prochaines tâches probables"""
        async with self._lock:
            # Analyser les patterns d'accès récents
            relevant_patterns = [
                (timestamp, key)
                for key, accesses in self.access_patterns.items()
                if key.startswith(agent_type)
                for timestamp, _ in accesses
                if time.time() - timestamp < 3600  # Dernière heure
            ]

            if not relevant_patterns:
                return []

            # Trier par fréquence
            from collections import Counter

            task_counts = Counter(key for _, key in relevant_patterns)

            # Retourner les tâches les plus fréquentes
            return [task for task, _ in task_counts.most_common(5)]

    async def warmup_cache(self, predictions: list[tuple[str, str, dict[str, Any]]]):
        """Pré-charger le cache avec des résultats prédits"""
        logger.info(f"🔥 Warmup du cache avec {len(predictions)} prédictions")

        for agent_type, task_type, parameters in predictions:
            # Vérifier si déjà en cache
            cached = await self.agent_cache.get_result(agent_type, task_type, parameters)

            if cached is None:
                logger.info(f"⏩ Pré-chargement prédit: {agent_type}/{task_type}")
                # Ici on pourrait lancer la tâche en arrière-plan
                # pour pré-remplir le cache


class CacheManager:
    """Gestionnaire complet du système de cache"""

    def __init__(
        self,
        max_size: int = 1000,
        max_memory_mb: float = 100.0,
        default_ttl: float = 3600.0,
        enable_smart_cache: bool = True,
    ):
        self.agent_cache = AgentResultCache(max_size, max_memory_mb, default_ttl)
        self.smart_cache = SmartCache(self.agent_cache) if enable_smart_cache else None
        self.is_enabled = True

    async def get(self, agent_type: str, task_type: str, parameters: dict[str, Any]) -> Any | None:
        """Récupérer un résultat (avec enregistrement des patterns)"""
        if not self.is_enabled:
            return None

        result = await self.agent_cache.get_result(agent_type, task_type, parameters)

        if self.smart_cache:
            await self.smart_cache.record_access(agent_type, task_type)

        return result

    async def put(
        self,
        agent_type: str,
        task_type: str,
        parameters: dict[str, Any],
        result: Any,
        ttl: float | None = None,
    ):
        """Mettre en cache un résultat"""
        if not self.is_enabled:
            return

        await self.agent_cache.cache_result(agent_type, task_type, parameters, result, ttl)

    async def invalidate(self, agent_type: str):
        """Invalider le cache pour un agent"""
        await self.agent_cache.invalidate_agent_cache(agent_type)

    async def get_stats(self) -> dict[str, Any]:
        """Obtenir les statistiques complètes"""
        stats = await self.agent_cache.get_stats()

        if self.smart_cache:
            stats["smart_cache_patterns"] = len(self.smart_cache.access_patterns)

        stats["is_enabled"] = self.is_enabled

        return stats

    async def enable(self):
        """Activer le cache"""
        self.is_enabled = True
        logger.info("✅ Cache activé")

    async def disable(self):
        """Désactiver le cache"""
        self.is_enabled = False
        logger.info("❌ Cache désactivé")

    async def clear(self):
        """Vider le cache"""
        await self.agent_cache.clear()


# Export
__all__ = [
    "CacheStrategy",
    "CacheEntry",
    "LRUCache",
    "AgentResultCache",
    "SmartCache",
    "CacheManager",
]
