#!/usr/bin/env python3
"""
Service Backend unifié pour Tawiza-V2 CLI

Fournit une couche d'abstraction pour les opérations backend avec:
- Async-first design
- Caching intégré
- Pool de connexions
- Circuit breaker pattern
- Retry automatique avec backoff
- Métriques et logging
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, TypeVar

from loguru import logger

from .cache_service import CacheService, get_cache_service

T = TypeVar("T")

# ==============================================================================
# CONSTANTES
# ==============================================================================

MAX_WORKERS = 4
DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_BASE_DELAY = 0.5
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_RESET_TIMEOUT = 30.0

# Cache TTLs
CACHE_TTL_GPU_STATUS = 2.0  # secondes
CACHE_TTL_SYSTEM_STATUS = 1.0
CACHE_TTL_AGENT_STATUS = 5.0
CACHE_TTL_MODEL_LIST = 60.0
CACHE_TTL_CONFIG = 300.0  # 5 minutes


# ==============================================================================
# CIRCUIT BREAKER
# ==============================================================================


class CircuitState(StrEnum):
    """État du circuit breaker"""

    CLOSED = "closed"  # Fonctionnel
    OPEN = "open"  # En erreur, rejette les appels
    HALF_OPEN = "half_open"  # En test de récupération


@dataclass
class CircuitBreaker:
    """Circuit breaker pour la résilience des services"""

    name: str
    failure_threshold: int = CIRCUIT_BREAKER_THRESHOLD
    reset_timeout: float = CIRCUIT_BREAKER_RESET_TIMEOUT

    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = 0
    last_failure_time: float | None = None

    def record_success(self) -> None:
        """Enregistrer un succès"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Enregistrer un échec"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker '{self.name}' opened after {self.failure_count} failures"
            )

    def can_execute(self) -> bool:
        """Vérifier si on peut exécuter une opération"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Vérifier si le timeout est passé
            if (
                self.last_failure_time
                and (time.time() - self.last_failure_time) > self.reset_timeout
            ):
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}' entering half-open state")
                return True
            return False

        # HALF_OPEN: autoriser un essai
        return True

    def reset(self) -> None:
        """Réinitialiser le circuit breaker"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None


# ==============================================================================
# RESULT WRAPPER
# ==============================================================================


@dataclass
class ServiceResult[T]:
    """Résultat d'une opération de service"""

    success: bool
    data: T | None = None
    error: str | None = None
    cached: bool = False
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def ok(cls, data: T, cached: bool = False, latency_ms: float = 0.0) -> ServiceResult[T]:
        return cls(success=True, data=data, cached=cached, latency_ms=latency_ms)

    @classmethod
    def fail(cls, error: str, latency_ms: float = 0.0) -> ServiceResult[T]:
        return cls(success=False, error=error, latency_ms=latency_ms)


# ==============================================================================
# BACKEND SERVICE
# ==============================================================================


class BackendService:
    """Service backend unifié avec async et caching"""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self._cache: CacheService | None = None
        self._circuits: dict[str, CircuitBreaker] = {}
        self._started = False

    async def start(self) -> None:
        """Démarrer le service backend"""
        if self._started:
            return

        self._cache = await get_cache_service()
        self._started = True
        logger.info("BackendService started")

    async def stop(self) -> None:
        """Arrêter le service backend"""
        if not self._started:
            return

        self._executor.shutdown(wait=False)
        if self._cache:
            await self._cache.stop()

        self._started = False
        logger.info("BackendService stopped")

    def _get_circuit(self, name: str) -> CircuitBreaker:
        """Obtenir ou créer un circuit breaker"""
        if name not in self._circuits:
            self._circuits[name] = CircuitBreaker(name=name)
        return self._circuits[name]

    async def _execute_with_circuit(
        self, circuit_name: str, operation: Callable, *args, **kwargs
    ) -> Any:
        """Exécuter une opération avec circuit breaker"""
        circuit = self._get_circuit(circuit_name)

        if not circuit.can_execute():
            raise CircuitOpenError(f"Circuit '{circuit_name}' is open")

        try:
            result = await operation(*args, **kwargs)
            circuit.record_success()
            return result
        except Exception:
            circuit.record_failure()
            raise

    async def _run_in_executor(self, func: Callable, *args) -> Any:
        """Exécuter une fonction bloquante dans un executor"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    async def _with_retry(
        self,
        operation: Callable,
        max_retries: int = MAX_RETRIES,
        base_delay: float = RETRY_BASE_DELAY,
    ) -> Any:
        """Exécuter avec retry et exponential backoff"""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return await operation()
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    delay = base_delay * (2**attempt)
                    logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s: {e}")
                    await asyncio.sleep(delay)

        raise last_error

    # ==========================================================================
    # SYSTEM OPERATIONS
    # ==========================================================================

    async def get_system_status(self) -> ServiceResult[dict[str, Any]]:
        """Obtenir le statut système avec caching"""
        start = time.time()
        cache_key = "system_status"

        # Vérifier le cache
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return ServiceResult.ok(
                    cached, cached=True, latency_ms=(time.time() - start) * 1000
                )

        try:
            status = await self._execute_with_circuit("system", self._fetch_system_status)

            # Mettre en cache
            if self._cache:
                await self._cache.set(cache_key, status, ttl=int(CACHE_TTL_SYSTEM_STATUS))

            return ServiceResult.ok(status, latency_ms=(time.time() - start) * 1000)
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return ServiceResult.fail(str(e), latency_ms=(time.time() - start) * 1000)

    async def _fetch_system_status(self) -> dict[str, Any]:
        """Récupérer le statut système (opération bloquante)"""
        import psutil

        def _get_status():
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "percent": psutil.virtual_memory().percent,
                },
                "disk": {
                    "total": psutil.disk_usage("/").total,
                    "free": psutil.disk_usage("/").free,
                    "percent": psutil.disk_usage("/").percent,
                },
                "uptime": time.time() - psutil.boot_time(),
            }

        return await self._run_in_executor(_get_status)

    # ==========================================================================
    # GPU OPERATIONS
    # ==========================================================================

    async def get_gpu_status(self) -> ServiceResult[dict[str, Any]]:
        """Obtenir le statut GPU avec caching"""
        start = time.time()
        cache_key = "gpu_status"

        # Vérifier le cache
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return ServiceResult.ok(
                    cached, cached=True, latency_ms=(time.time() - start) * 1000
                )

        try:
            status = await self._execute_with_circuit("gpu", self._fetch_gpu_status)

            if self._cache:
                await self._cache.set(cache_key, status, ttl=int(CACHE_TTL_GPU_STATUS))

            return ServiceResult.ok(status, latency_ms=(time.time() - start) * 1000)
        except CircuitOpenError:
            return ServiceResult.fail(
                "GPU service temporarily unavailable", latency_ms=(time.time() - start) * 1000
            )
        except Exception as e:
            logger.error(f"Failed to get GPU status: {e}")
            return ServiceResult.fail(str(e), latency_ms=(time.time() - start) * 1000)

    async def _fetch_gpu_status(self) -> dict[str, Any]:
        """Récupérer le statut GPU"""

        def _get_gpu():
            import subprocess

            # Essayer ROCm d'abord
            try:
                result = subprocess.run(
                    ["rocm-smi", "--showuse"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and "GPU" in result.stdout:
                    # Parse text output (rocm-smi doesn't always have --json)
                    return {"type": "amd", "available": True, "raw_output": result.stdout[:500]}
                elif (
                    "not found" in result.stderr.lower()
                    or "not initialized" in result.stderr.lower()
                ):
                    pass  # Driver not loaded, try NVIDIA

            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                pass

            # Essayer NVIDIA
            try:
                result = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=name,memory.used,memory.total,utilization.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    lines = result.stdout.strip().split("\n")
                    gpus = []
                    for line in lines:
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 4:
                            try:
                                gpus.append(
                                    {
                                        "name": parts[0],
                                        "memory_used": int(parts[1]),
                                        "memory_total": int(parts[2]),
                                        "utilization": int(parts[3]),
                                    }
                                )
                            except (ValueError, IndexError):
                                continue
                    if gpus:
                        return {"type": "nvidia", "available": True, "gpus": gpus}

            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                pass

            return {
                "type": "none",
                "available": False,
                "message": "Aucun GPU détecté (ROCm/CUDA non disponible)",
            }

        return await self._run_in_executor(_get_gpu)

    # ==========================================================================
    # AGENT OPERATIONS
    # ==========================================================================

    async def get_agents_status(self) -> ServiceResult[list[dict[str, Any]]]:
        """Obtenir le statut des agents"""
        start = time.time()
        cache_key = "agents_status"

        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return ServiceResult.ok(
                    cached, cached=True, latency_ms=(time.time() - start) * 1000
                )

        try:
            agents = await self._fetch_agents_status()

            if self._cache:
                await self._cache.set(cache_key, agents, ttl=int(CACHE_TTL_AGENT_STATUS))

            return ServiceResult.ok(agents, latency_ms=(time.time() - start) * 1000)
        except Exception as e:
            logger.error(f"Failed to get agents status: {e}")
            return ServiceResult.fail(str(e), latency_ms=(time.time() - start) * 1000)

    async def _fetch_agents_status(self) -> list[dict[str, Any]]:
        """Récupérer le statut des agents"""
        # Cette méthode serait connectée au vrai système d'agents
        # Pour l'instant, retourne des données simulées
        return [
            {"name": "data_analyst", "status": "running", "tasks_completed": 15},
            {"name": "ml_engineer", "status": "running", "tasks_completed": 8},
            {"name": "code_generator", "status": "idle", "tasks_completed": 0},
            {"name": "browser_automation", "status": "stopped", "tasks_completed": 0},
            {"name": "gpu_optimizer", "status": "running", "tasks_completed": 3},
        ]

    # ==========================================================================
    # MODEL OPERATIONS
    # ==========================================================================

    async def get_available_models(self) -> ServiceResult[list[dict[str, Any]]]:
        """Obtenir la liste des modèles disponibles"""
        start = time.time()
        cache_key = "available_models"

        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return ServiceResult.ok(
                    cached, cached=True, latency_ms=(time.time() - start) * 1000
                )

        try:
            models = await self._with_retry(self._fetch_models)

            if self._cache:
                await self._cache.set(cache_key, models, ttl=int(CACHE_TTL_MODEL_LIST))

            return ServiceResult.ok(models, latency_ms=(time.time() - start) * 1000)
        except Exception as e:
            logger.error(f"Failed to get models: {e}")
            return ServiceResult.fail(str(e), latency_ms=(time.time() - start) * 1000)

    async def _fetch_models(self) -> list[dict[str, Any]]:
        """Récupérer les modèles depuis Ollama"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get("http://localhost:11434/api/tags")
                response.raise_for_status()
                data = response.json()
                return data.get("models", [])
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return []

    # ==========================================================================
    # BATCH OPERATIONS
    # ==========================================================================

    async def get_all_status(self) -> dict[str, ServiceResult]:
        """Obtenir tous les statuts en parallèle"""
        results = await asyncio.gather(
            self.get_system_status(),
            self.get_gpu_status(),
            self.get_agents_status(),
            return_exceptions=True,
        )

        return {
            "system": results[0]
            if not isinstance(results[0], Exception)
            else ServiceResult.fail(str(results[0])),
            "gpu": results[1]
            if not isinstance(results[1], Exception)
            else ServiceResult.fail(str(results[1])),
            "agents": results[2]
            if not isinstance(results[2], Exception)
            else ServiceResult.fail(str(results[2])),
        }

    # ==========================================================================
    # METRICS
    # ==========================================================================

    def get_circuit_status(self) -> dict[str, dict[str, Any]]:
        """Obtenir le statut de tous les circuit breakers"""
        return {
            name: {
                "state": circuit.state.value,
                "failure_count": circuit.failure_count,
                "last_failure": circuit.last_failure_time,
            }
            for name, circuit in self._circuits.items()
        }

    async def get_cache_stats(self) -> dict[str, Any]:
        """Obtenir les statistiques du cache"""
        if self._cache:
            stats = self._cache.get_stats()
            return stats.to_dict()
        return {}


# ==============================================================================
# EXCEPTIONS
# ==============================================================================


class CircuitOpenError(Exception):
    """Circuit breaker is open"""

    pass


class BackendServiceError(Exception):
    """Erreur générale du service backend"""

    pass


# ==============================================================================
# SINGLETON
# ==============================================================================

_backend_service: BackendService | None = None


async def get_backend_service() -> BackendService:
    """Obtenir l'instance du service backend"""
    global _backend_service
    if _backend_service is None:
        _backend_service = BackendService()
        await _backend_service.start()
    return _backend_service
