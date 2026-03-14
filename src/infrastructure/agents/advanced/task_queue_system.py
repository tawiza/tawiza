#!/usr/bin/env python3
"""
Task Queue System pour Multi-Agent Optimization
Système de queue partagée avec load balancing et worker pool
"""

import asyncio
import heapq
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class TaskPriority(Enum):
    """Priorités des tâches"""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class TaskStatus(Enum):
    """Statuts des tâches"""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Tâche à exécuter"""

    task_id: str
    task_type: str
    agent_type: str  # data_analyst, ml_engineer, browser_automation, code_generator
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: float = 300.0
    retry_count: int = 0
    max_retries: int = 3
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    result: Any = None
    error: str | None = None

    def __lt__(self, other):
        """Comparaison pour la priority queue (priorité plus haute = valeur plus petite)"""
        return self.priority.value > other.priority.value


@dataclass
class WorkerStats:
    """Statistiques d'un worker"""

    worker_id: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time: float = 0.0
    current_load: int = 0
    max_load: int = 5
    is_busy: bool = False
    last_task_time: float | None = None


class SharedTaskQueue:
    """Queue de tâches partagée avec priorité"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._queue: list[Task] = []
        self._task_map: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def put(self, task: Task):
        """Ajouter une tâche à la queue"""
        async with self._lock:
            if len(self._queue) >= self.max_size:
                raise ValueError(f"Queue pleine (max: {self.max_size})")

            heapq.heappush(self._queue, task)
            self._task_map[task.task_id] = task
            task.status = TaskStatus.QUEUED
            logger.info(
                f"📥 Tâche ajoutée à la queue: {task.task_id} (priorité: {task.priority.name})"
            )

    async def get(self) -> Task | None:
        """Récupérer la tâche de plus haute priorité"""
        async with self._lock:
            if not self._queue:
                return None

            task = heapq.heappop(self._queue)
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            return task

    async def get_task(self, task_id: str) -> Task | None:
        """Récupérer une tâche spécifique"""
        return self._task_map.get(task_id)

    async def size(self) -> int:
        """Taille de la queue"""
        return len(self._queue)

    async def is_empty(self) -> bool:
        """Vérifier si la queue est vide"""
        return len(self._queue) == 0


class LoadBalancer:
    """Load balancer pour distribuer les tâches entre workers"""

    def __init__(self):
        self.workers: dict[str, WorkerStats] = {}
        self.agent_to_workers: dict[str, list[str]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def register_worker(self, worker_id: str, agent_type: str, max_load: int = 5):
        """Enregistrer un worker"""
        async with self._lock:
            self.workers[worker_id] = WorkerStats(worker_id=worker_id, max_load=max_load)
            self.agent_to_workers[agent_type].append(worker_id)
            logger.info(
                f"👷 Worker enregistré: {worker_id} (type: {agent_type}, max_load: {max_load})"
            )

    async def get_best_worker(self, agent_type: str) -> str | None:
        """Obtenir le meilleur worker pour un type d'agent"""
        async with self._lock:
            workers = self.agent_to_workers.get(agent_type, [])

            if not workers:
                return None

            # Trouver le worker avec la charge la plus faible
            best_worker = None
            min_load = float("inf")

            for worker_id in workers:
                worker = self.workers[worker_id]
                if worker.current_load < worker.max_load and worker.current_load < min_load:
                    best_worker = worker_id
                    min_load = worker.current_load

            return best_worker

    async def update_worker_load(self, worker_id: str, delta: int):
        """Mettre à jour la charge d'un worker"""
        async with self._lock:
            if worker_id in self.workers:
                self.workers[worker_id].current_load += delta
                self.workers[worker_id].is_busy = self.workers[worker_id].current_load > 0

    async def record_task_completion(self, worker_id: str, success: bool, execution_time: float):
        """Enregistrer la complétion d'une tâche"""
        async with self._lock:
            if worker_id in self.workers:
                worker = self.workers[worker_id]
                if success:
                    worker.tasks_completed += 1
                else:
                    worker.tasks_failed += 1
                worker.total_execution_time += execution_time
                worker.last_task_time = time.time()

    async def get_stats(self) -> dict[str, dict]:
        """Obtenir les statistiques de tous les workers"""
        async with self._lock:
            return {
                worker_id: {
                    "tasks_completed": worker.tasks_completed,
                    "tasks_failed": worker.tasks_failed,
                    "avg_execution_time": worker.total_execution_time
                    / max(worker.tasks_completed, 1),
                    "current_load": worker.current_load,
                    "max_load": worker.max_load,
                    "utilization": worker.current_load / worker.max_load * 100,
                    "is_busy": worker.is_busy,
                }
                for worker_id, worker in self.workers.items()
            }


class WorkerPool:
    """Pool de workers pour exécution parallèle"""

    def __init__(
        self, task_queue: SharedTaskQueue, load_balancer: LoadBalancer, num_workers: int = 4
    ):
        self.task_queue = task_queue
        self.load_balancer = load_balancer
        self.num_workers = num_workers
        self.workers: list[asyncio.Task] = []
        self.is_running = False

    async def start(self):
        """Démarrer le pool de workers"""
        if self.is_running:
            return

        self.is_running = True

        # Créer les workers
        for i in range(self.num_workers):
            worker = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self.workers.append(worker)

        logger.info(f"🚀 Worker pool démarré avec {self.num_workers} workers")

    async def stop(self):
        """Arrêter le pool de workers"""
        self.is_running = False

        # Annuler tous les workers
        for worker in self.workers:
            worker.cancel()

        # Attendre que tous les workers se terminent
        await asyncio.gather(*self.workers, return_exceptions=True)

        self.workers.clear()
        logger.info("🛑 Worker pool arrêté")

    async def _worker_loop(self, worker_id: str):
        """Boucle principale d'un worker"""
        logger.info(f"👷 Worker {worker_id} démarré")

        while self.is_running:
            try:
                # Récupérer une tâche de la queue
                task = await self.task_queue.get()

                if task is None:
                    # Pas de tâche disponible, attendre
                    await asyncio.sleep(0.1)
                    continue

                # Note: Suppression du check "best_worker" pour éviter l'infinite loop
                # Tous les workers peuvent traiter n'importe quelle tâche
                # Le load balancing se fait via la priorité de la queue

                # Mettre à jour la charge du worker
                await self.load_balancer.update_worker_load(worker_id, 1)

                # Exécuter la tâche
                start_time = time.time()
                success = False

                try:
                    logger.info(f"▶️ Worker {worker_id} exécute: {task.task_id}")

                    # Exécuter avec timeout
                    task.result = await asyncio.wait_for(
                        task.func(*task.args, **task.kwargs), timeout=task.timeout
                    )

                    task.status = TaskStatus.COMPLETED
                    success = True
                    logger.info(f"✅ Tâche complétée: {task.task_id}")

                except TimeoutError:
                    task.status = TaskStatus.FAILED
                    task.error = f"Timeout après {task.timeout}s"
                    logger.error(f"⏱️ Timeout: {task.task_id}")

                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    logger.error(f"❌ Erreur lors de l'exécution de {task.task_id}: {e}")

                    # Retry si possible
                    if task.retry_count < task.max_retries:
                        task.retry_count += 1
                        task.status = TaskStatus.PENDING
                        await self.task_queue.put(task)
                        logger.info(
                            f"🔄 Retry {task.retry_count}/{task.max_retries}: {task.task_id}"
                        )

                finally:
                    execution_time = time.time() - start_time
                    task.completed_at = time.time()

                    # Mettre à jour les statistiques
                    await self.load_balancer.record_task_completion(
                        worker_id, success, execution_time
                    )
                    await self.load_balancer.update_worker_load(worker_id, -1)

            except asyncio.CancelledError:
                logger.info(f"🛑 Worker {worker_id} annulé")
                break

            except Exception as e:
                logger.error(f"❌ Erreur dans le worker {worker_id}: {e}")
                await asyncio.sleep(1)

        logger.info(f"👷 Worker {worker_id} terminé")


class TaskQueueSystem:
    """Système complet de queue de tâches avec load balancing et worker pool"""

    def __init__(self, num_workers: int = 4, max_queue_size: int = 1000):
        self.task_queue = SharedTaskQueue(max_size=max_queue_size)
        self.load_balancer = LoadBalancer()
        self.worker_pool = WorkerPool(self.task_queue, self.load_balancer, num_workers)

    async def start(self):
        """Démarrer le système"""
        await self.worker_pool.start()
        logger.info("🚀 Task Queue System démarré")

    async def stop(self):
        """Arrêter le système"""
        await self.worker_pool.stop()
        logger.info("🛑 Task Queue System arrêté")

    async def submit_task(self, task: Task) -> str:
        """Soumettre une tâche"""
        await self.task_queue.put(task)
        return task.task_id

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Obtenir le statut d'une tâche"""
        task = await self.task_queue.get_task(task_id)

        if task is None:
            return None

        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "progress": self._calculate_progress(task),
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "retry_count": task.retry_count,
            "error": task.error,
        }

    async def get_system_stats(self) -> dict[str, Any]:
        """Obtenir les statistiques du système"""
        queue_size = await self.task_queue.size()
        worker_stats = await self.load_balancer.get_stats()

        return {
            "queue_size": queue_size,
            "num_workers": self.worker_pool.num_workers,
            "workers": worker_stats,
            "total_tasks_completed": sum(w["tasks_completed"] for w in worker_stats.values()),
            "total_tasks_failed": sum(w["tasks_failed"] for w in worker_stats.values()),
            "avg_utilization": sum(w["utilization"] for w in worker_stats.values())
            / max(len(worker_stats), 1),
        }

    def _calculate_progress(self, task: Task) -> float:
        """Calculer le progrès d'une tâche"""
        if task.status == TaskStatus.PENDING:
            return 0.0
        elif task.status == TaskStatus.QUEUED:
            return 10.0
        elif task.status == TaskStatus.RUNNING:
            if task.started_at:
                elapsed = time.time() - task.started_at
                return min(10.0 + (elapsed / task.timeout) * 80, 90.0)
            return 50.0
        elif task.status == TaskStatus.COMPLETED:
            return 100.0
        elif task.status in [TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return 0.0
        return 0.0


# Export
__all__ = [
    "Task",
    "TaskPriority",
    "TaskStatus",
    "SharedTaskQueue",
    "LoadBalancer",
    "WorkerPool",
    "TaskQueueSystem",
]
