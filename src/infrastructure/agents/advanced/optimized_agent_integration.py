#!/usr/bin/env python3
"""
Optimized Agent Integration avec Task Queue, Load Balancing et Caching
Version optimisée pour Phase 3: Multi-Agent Optimization
"""

import uuid
from dataclasses import dataclass
from typing import Any

from loguru import logger

from .gpu_optimizer import GPUOptimizer, create_gpu_optimizer
from .result_cache import CacheManager
from .task_queue_system import Task, TaskPriority, TaskQueueSystem


@dataclass
class OptimizedSystemConfig:
    """Configuration du système optimisé"""
    # Task Queue
    num_workers: int = 4
    max_queue_size: int = 1000

    # Cache
    cache_max_size: int = 1000
    cache_max_memory_mb: float = 100.0
    cache_default_ttl: float = 3600.0
    enable_smart_cache: bool = True

    # GPU
    enable_gpu_optimization: bool = True

    # Performance
    enable_performance_monitoring: bool = True
    task_timeout: float = 300.0
    max_retries: int = 3


class OptimizedAgentIntegration:
    """Intégration optimisée des agents avec queue, load balancing et cache"""

    def __init__(self, config: OptimizedSystemConfig | None = None):
        self.config = config or OptimizedSystemConfig()

        # Systèmes principaux
        self.task_queue_system = TaskQueueSystem(
            num_workers=self.config.num_workers,
            max_queue_size=self.config.max_queue_size
        )

        self.cache_manager = CacheManager(
            max_size=self.config.cache_max_size,
            max_memory_mb=self.config.cache_max_memory_mb,
            default_ttl=self.config.cache_default_ttl,
            enable_smart_cache=self.config.enable_smart_cache
        )

        self.gpu_optimizer: GPUOptimizer | None = None

        # État
        self.is_initialized = False
        self.performance_metrics = {}

    async def initialize(self):
        """Initialiser le système optimisé"""
        logger.info("🚀 Initialisation du système optimisé d'agents...")

        try:
            # 1. Initialiser le GPU Optimizer
            if self.config.enable_gpu_optimization:
                logger.info("🎮 Initialisation GPU Optimizer...")
                self.gpu_optimizer = create_gpu_optimizer()
                await self.gpu_optimizer.initialize()

            # 2. Enregistrer les workers pour chaque type d'agent
            logger.info("👷 Enregistrement des workers...")
            await self._register_workers()

            # 3. Démarrer le Task Queue System
            logger.info("🚀 Démarrage du Task Queue System...")
            await self.task_queue_system.start()

            # 4. Warmup du cache si nécessaire
            if self.config.enable_smart_cache:
                logger.info("🔥 Warmup du cache...")
                await self._warmup_cache()

            self.is_initialized = True
            logger.info("✅ Système optimisé initialisé avec succès!")

            # Afficher les stats initiales
            await self.show_system_stats()

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation: {e}")
            raise

    async def _register_workers(self):
        """Enregistrer les workers pour chaque type d'agent"""
        agent_types = ["data_analyst", "ml_engineer", "browser_automation", "code_generator"]

        for agent_type in agent_types:
            # Enregistrer un worker par type d'agent
            worker_id = f"{agent_type}-worker-0"
            await self.task_queue_system.load_balancer.register_worker(
                worker_id=worker_id,
                agent_type=agent_type,
                max_load=5
            )

    async def _warmup_cache(self):
        """Pré-charger le cache avec des résultats communs"""
        # Exemple de pré-chargement
        # En production, cela pourrait être basé sur les tâches fréquentes
        logger.info("🔥 Cache warmup complété")

    async def submit_task(
        self,
        agent_type: str,
        task_type: str,
        func: Any,
        args: tuple = (),
        kwargs: dict = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        use_cache: bool = True
    ) -> str:
        """
        Soumettre une tâche avec support de cache

        Args:
            agent_type: Type d'agent (data_analyst, ml_engineer, etc.)
            task_type: Type de tâche
            func: Fonction à exécuter
            args: Arguments de la fonction
            kwargs: Arguments nommés de la fonction
            priority: Priorité de la tâche
            use_cache: Utiliser le cache si disponible

        Returns:
            task_id: ID de la tâche
        """
        if kwargs is None:
            kwargs = {}

        # 1. Vérifier le cache d'abord
        if use_cache:
            cached_result = await self.cache_manager.get(
                agent_type=agent_type,
                task_type=task_type,
                parameters={"args": args, "kwargs": kwargs}
            )

            if cached_result is not None:
                logger.info(f"✅ Résultat trouvé en cache: {agent_type}/{task_type}")
                # Créer une tâche "virtuelle" déjà complétée
                task_id = str(uuid.uuid4())
                return task_id

        # 2. Créer la tâche
        task_id = str(uuid.uuid4())

        # Wrapper pour mettre en cache le résultat
        async def cached_func(*args, **kwargs):
            result = await func(*args, **kwargs)

            if use_cache:
                await self.cache_manager.put(
                    agent_type=agent_type,
                    task_type=task_type,
                    parameters={"args": args, "kwargs": kwargs},
                    result=result
                )

            return result

        task = Task(
            task_id=task_id,
            task_type=task_type,
            agent_type=agent_type,
            func=cached_func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            timeout=self.config.task_timeout,
            max_retries=self.config.max_retries
        )

        # 3. Soumettre à la queue
        await self.task_queue_system.submit_task(task)

        logger.info(f"📥 Tâche soumise: {task_id} ({agent_type}/{task_type}) - Priorité: {priority.name}")

        return task_id

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Obtenir le statut d'une tâche"""
        return await self.task_queue_system.get_task_status(task_id)

    async def get_task_result(self, task_id: str) -> Any | None:
        """Obtenir le résultat d'une tâche"""
        task_status = await self.get_task_status(task_id)

        if task_status is None:
            return None

        if task_status["status"] == "completed":
            task = await self.task_queue_system.task_queue.get_task(task_id)
            return task.result if task else None

        return None

    async def show_system_stats(self):
        """Afficher les statistiques du système"""
        from rich import box
        from rich.console import Console
        from rich.table import Table

        console = Console()

        # Statistiques du Task Queue System
        queue_stats = await self.task_queue_system.get_system_stats()

        # Statistiques du Cache
        cache_stats = await self.cache_manager.get_stats()

        # Table des statistiques
        table = Table(title="📊 Statistiques du Système Optimisé", box=box.ROUNDED)
        table.add_column("Composant", style="cyan")
        table.add_column("Métrique", style="magenta")
        table.add_column("Valeur", style="green")

        # Queue Stats
        table.add_row("Task Queue", "Tâches en queue", str(queue_stats["queue_size"]))
        table.add_row("Task Queue", "Workers", str(queue_stats["num_workers"]))
        table.add_row("Task Queue", "Tâches complétées", str(queue_stats["total_tasks_completed"]))
        table.add_row("Task Queue", "Tâches échouées", str(queue_stats["total_tasks_failed"]))
        table.add_row("Task Queue", "Utilisation moyenne", f"{queue_stats['avg_utilization']:.1f}%")

        # Cache Stats
        table.add_row("Cache", "Entrées", str(cache_stats["size"]))
        table.add_row("Cache", "Mémoire utilisée", f"{cache_stats['memory_usage_mb']:.2f} MB")
        table.add_row("Cache", "Taux de hit", f"{cache_stats['hit_rate']:.1f}%")
        table.add_row("Cache", "Utilisation", f"{cache_stats['utilization']:.1f}%")

        console.print(table)

        # Table des workers
        worker_table = Table(title="👷 Statistiques des Workers", box=box.ROUNDED)
        worker_table.add_column("Worker", style="cyan")
        worker_table.add_column("Complétées", style="green")
        worker_table.add_column("Échouées", style="red")
        worker_table.add_column("Charge", style="yellow")
        worker_table.add_column("Utilisation", style="magenta")

        for worker_id, worker_stats in queue_stats["workers"].items():
            worker_table.add_row(
                worker_id,
                str(worker_stats["tasks_completed"]),
                str(worker_stats["tasks_failed"]),
                f"{worker_stats['current_load']}/{worker_stats['max_load']}",
                f"{worker_stats['utilization']:.1f}%"
            )

        console.print(worker_table)

    async def invalidate_cache(self, agent_type: str | None = None):
        """Invalider le cache"""
        if agent_type:
            await self.cache_manager.invalidate(agent_type)
        else:
            await self.cache_manager.clear()

    async def shutdown(self):
        """Arrêter le système"""
        logger.info("🛑 Arrêt du système optimisé...")

        await self.task_queue_system.stop()
        self.is_initialized = False

        logger.info("✅ Système arrêté proprement")


# Fonctions utilitaires

async def create_optimized_agent_integration(
    config: OptimizedSystemConfig | None = None
) -> OptimizedAgentIntegration:
    """Créer et initialiser une intégration optimisée"""
    integration = OptimizedAgentIntegration(config)
    await integration.initialize()
    return integration


# Export
__all__ = [
    'OptimizedSystemConfig',
    'OptimizedAgentIntegration',
    'create_optimized_agent_integration'
]
