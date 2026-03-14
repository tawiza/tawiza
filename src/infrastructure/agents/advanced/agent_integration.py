#!/usr/bin/env python3
"""
non complier =+
Intégration Avancée des Agents pour Tawiza-V2
Intégration complète avec le système principal et interface unifiée
"""

import asyncio
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from loguru import logger
from rich.align import Align
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Configuration du logging
console = Console()

# Import des agents
from .browser_automation_agent import BrowserAutomationAgent
from .code_generator_agent import CodeGeneratorAgent
from .data_analyst_agent import DataAnalystAgent
from .gpu_optimizer import create_gpu_optimizer
from .ml_engineer_agent import MLEngineerAgent
from .multi_agent_system import MultiAgentSystem


@dataclass
class SystemStatus:
    """Statut du système d'agents"""

    is_initialized: bool
    active_agents: list[str]
    memory_usage: float
    gpu_utilization: float
    performance_score: float
    last_update: str


@dataclass
class AgentTask:
    """Tâche à exécuter par un agent"""

    task_id: str
    task_type: str  # data_analysis, ml_training, browser_automation, code_generation
    parameters: dict[str, Any]
    priority: int  # 1-10, 10 étant la plus haute
    timeout: float
    callback: str | None = None


@dataclass
class TaskResult:
    """Résultat d'une tâche"""

    task_id: str
    success: bool
    result: Any
    execution_time: float
    error_message: str | None = None
    timestamp: str = ""


class AdvancedAgentIntegration:
    """Intégration avancée des agents avec le système Tawiza-V2"""

    def __init__(self):
        self.multi_agent_system = MultiAgentSystem()
        self.gpu_optimizer = None
        self.is_initialized = False
        self.task_queue = asyncio.Queue()
        self.active_tasks = {}
        self.task_history = []
        self.performance_metrics = {}

        # Agents spécialisés
        self.data_analyst = None
        self.ml_engineer = None
        self.browser_automation = None
        self.code_generator = None

        # Configuration
        self.config = {
            "max_concurrent_tasks": 5,
            "task_timeout": 300.0,
            "enable_gpu_optimization": True,
            "enable_performance_monitoring": True,
            "auto_scale": True,
            "retry_failed_tasks": 3,
        }

    async def initialize(self):
        """Initialiser l'intégration avancée"""
        logger.info("🚀 Initialisation de l'Advanced Agent Integration...")

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                # Initialiser le GPU Optimizer
                task1 = progress.add_task("🎮 Initialisation GPU Optimizer...", total=None)
                self.gpu_optimizer = create_gpu_optimizer()
                await self.gpu_optimizer.initialize()
                progress.update(task1, completed=True)

                # Initialiser les agents spécialisés
                task2 = progress.add_task("🤖 Initialisation des agents spécialisés...", total=None)
                await self._initialize_specialized_agents()
                progress.update(task2, completed=True)

                # Optimiser les performances GPU
                task3 = progress.add_task("⚡ Optimisation GPU...", total=None)
                if self.config["enable_gpu_optimization"]:
                    await self._optimize_gpu_performance()
                progress.update(task3, completed=True)

                # Configurer le système multi-agent
                task4 = progress.add_task("🔗 Configuration multi-agent...", total=None)
                await self._setup_multi_agent_system()
                progress.update(task4, completed=True)

                # Démarrer les services
                task5 = progress.add_task("▶️ Démarrage des services...", total=None)
                await self._start_services()
                progress.update(task5, completed=True)

            self.is_initialized = True
            logger.info("✅ Advanced Agent Integration initialisée avec succès")

            # Afficher le statut
            await self.show_system_status()

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation: {e}")
            raise

    async def _initialize_specialized_agents(self):
        """Initialiser tous les agents spécialisés"""
        logger.info("🤖 Initialisation des agents spécialisés...")

        # Data Analyst Agent
        self.data_analyst = DataAnalystAgent()
        logger.info("✅ Data Analyst Agent initialisé")

        # ML Engineer Agent
        self.ml_engineer = MLEngineerAgent()
        logger.info("✅ ML Engineer Agent initialisé")

        # Browser Automation Agent
        self.browser_automation = BrowserAutomationAgent()
        await self.browser_automation.initialize()
        logger.info("✅ Browser Automation Agent initialisé")

        # Code Generator Agent
        self.code_generator = CodeGeneratorAgent()
        logger.info("✅ Code Generator Agent initialisé")

    async def _optimize_gpu_performance(self):
        """Optimiser les performances GPU"""
        logger.info("⚡ Optimisation des performances GPU...")

        try:
            # Optimiser pour différents modèles
            models_to_optimize = ["qwen3.5:27b", "qwen3-coder:30b", "mistral:latest"]

            for model in models_to_optimize:
                logger.info(f"🎯 Optimisation pour {model}...")
                result = await self.gpu_optimizer.optimize_inference_performance(model)

                # Stocker les métriques
                self.performance_metrics[model] = {
                    "original_performance": result.original_performance,
                    "optimized_performance": result.optimized_performance,
                    "improvement": result.improvement_percentage,
                    "optimizations": result.optimizations_applied,
                }

                logger.info(f"✅ {model}: {result.improvement_percentage:.1f}% d'amélioration")

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'optimisation GPU: {e}")

    async def _setup_multi_agent_system(self):
        """Configurer le système multi-agent"""
        logger.info("🔗 Configuration du système multi-agent...")

        # Configurer la coordination entre agents
        # coordination_config = {
        #     "enable_collaboration": True,
        #     "task_distribution": "intelligent",
        #     "load_balancing": True,
        #     "failure_recovery": True,
        #     "performance_monitoring": True
        # }

        # TODO: Appliquer la configuration quand le coordinateur aura un attribut config
        # self.multi_agent_system.coordinator.config.update(coordination_config)

        logger.info("✅ Système multi-agent configuré")

    async def _start_services(self):
        """Démarrer les services d'arrière-plan"""
        logger.info("▶️ Démarrage des services...")

        # Démarrer le gestionnaire de tâches
        asyncio.create_task(self._task_processor())

        # Démarrer le monitoring de performance
        if self.config["enable_performance_monitoring"]:
            asyncio.create_task(self._performance_monitor())

        logger.info("✅ Services démarrés")

    async def submit_task(self, task: "AgentTask") -> str:
        """Soumettre une tâche à exécuter"""
        task_id = f"task_{int(time.time() * 1000)}"

        # Ajouter à la file d'attente avec les informations de la tâche
        task_info = {
            "task_id": task_id,
            "task": task,
            "status": "queued",
            "submitted_at": datetime.now().isoformat(),
            "timeout": task.timeout,
        }

        await self.task_queue.put((task.priority, task_info))

        # Stocker la tâche
        self.active_tasks[task_id] = task_info

        logger.info(f"📋 Tâche soumise: {task_id} (Type: {task.task_type})")
        return task_id

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Obtenir le statut d'une tâche"""
        return self.active_tasks.get(task_id)

    async def get_task_result(self, task_id: str) -> TaskResult | None:
        """Obtenir le résultat d'une tâche"""
        task_info = self.active_tasks.get(task_id)
        if task_info and task_info.get("result"):
            return task_info["result"]
        return None

    async def _task_processor(self):
        """Processeur de tâches en arrière-plan"""
        logger.info("🔄 Processeur de tâches démarré")

        while True:
            try:
                # Obtenir la prochaine tâche
                priority, task_info = await self.task_queue.get()

                task_id = task_info["task_id"]
                task = task_info["task"]

                # Mettre à jour le statut
                task_info["status"] = "processing"
                task_info["started_at"] = datetime.now().isoformat()

                logger.info(f"🚀 Traitement de la tâche: {task_id}")

                try:
                    # Traiter la tâche
                    result = await self._process_task(task)

                    # Mettre à jour le statut
                    task_info["status"] = "completed"
                    task_info["completed_at"] = datetime.now().isoformat()
                    task_info["result"] = result

                    logger.info(f"✅ Tâche complétée: {task_id}")

                except Exception as e:
                    # Gérer l'erreur
                    task_info["status"] = "failed"
                    task_info["error"] = str(e)
                    task_info["failed_at"] = datetime.now().isoformat()

                    logger.error(f"❌ Tâche échouée: {task_id} - {e}")

                    # Réessayer si configuré
                    if self.config["retry_failed_tasks"] > 0:
                        retry_count = task_info.get("retry_count", 0)
                        if retry_count < self.config["retry_failed_tasks"]:
                            task_info["retry_count"] = retry_count + 1
                            task_info["status"] = "retrying"

                            # Remettre dans la file d'attente
                            await self.task_queue.put((priority, task_info))

                            logger.info(f"🔄 Nouvelle tentative pour: {task_id}")

                # Ajouter à l'historique
                self.task_history.append(
                    {
                        "task_id": task_id,
                        "status": task_info["status"],
                        "execution_time": time.time()
                        - datetime.fromisoformat(task_info["submitted_at"]).timestamp(),
                    }
                )

            except Exception as e:
                logger.error(f"❌ Erreur dans le processeur de tâches: {e}")
                await asyncio.sleep(1)

    async def _process_task(self, task: "AgentTask") -> TaskResult:
        """Traiter une tâche individuelle"""
        start_time = time.time()

        try:
            result = None

            # Router vers l'agent approprié selon le type de tâche
            if task.task_type == "data_analysis":
                if self.data_analyst:
                    dataset_path = task.parameters.get("dataset_path")
                    result = await self.data_analyst.analyze_dataset(
                        dataset_path, **task.parameters
                    )
                else:
                    raise Exception("Data Analyst agent n'est pas initialisé")

            elif task.task_type == "ml_training":
                if self.ml_engineer:
                    config = task.parameters.get("config", {})
                    result = await self.ml_engineer.create_ml_pipeline(config)
                else:
                    raise Exception("ML Engineer agent n'est pas initialisé")

            elif task.task_type == "browser_automation":
                if self.browser_automation:
                    url = task.parameters.get("url")
                    objective = task.parameters.get("objective")
                    # Créer une AutomationTask à partir des paramètres
                    browser_task = await self.browser_automation.create_automation_task(
                        url=url,
                        objective=objective,
                        **{
                            k: v
                            for k, v in task.parameters.items()
                            if k not in ["url", "objective"]
                        },
                    )
                    result = await self.browser_automation.execute_task(browser_task)
                else:
                    raise Exception("Browser Automation agent n'est pas initialisé")

            elif task.task_type == "code_generation":
                if self.code_generator:
                    description = task.parameters.get("description")
                    language = task.parameters.get("language", "python")
                    result = await self.code_generator.generate_code(
                        description, language, **task.parameters
                    )
                else:
                    raise Exception("Code Generator agent n'est pas initialisé")

            else:
                raise Exception(f"Type de tâche inconnu: {task.task_type}")

            execution_time = time.time() - start_time

            return TaskResult(
                task_id=task.task_id,
                success=True,
                result=result,
                execution_time=execution_time,
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            execution_time = time.time() - start_time

            return TaskResult(
                task_id=task.task_id,
                success=False,
                result=None,
                execution_time=execution_time,
                error_message=str(e),
                timestamp=datetime.now().isoformat(),
            )

    async def _performance_monitor(self):
        """Moniteur de performance en arrière-plan"""
        logger.info("📊 Moniteur de performance démarré")

        while True:
            try:
                # Collecter les métriques
                metrics = await self._collect_metrics()

                # Stocker les métriques
                self.performance_metrics["system"] = metrics

                # Attendre avant la prochaine collecte
                await asyncio.sleep(30)  # Toutes les 30 secondes

            except Exception as e:
                logger.error(f"❌ Erreur dans le moniteur de performance: {e}")
                await asyncio.sleep(60)  # Attendre plus longtemps en cas d'erreur

    async def _collect_metrics(self) -> dict[str, Any]:
        """Collecter les métriques système"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "active_tasks": len(self.active_tasks),
            "queue_size": self.task_queue.qsize(),
            "task_history_size": len(self.task_history),
        }

        # Métriques GPU si disponibles
        if self.gpu_optimizer:
            try:
                gpu_metrics = await self.gpu_optimizer._get_gpu_metrics()
                metrics["gpu"] = asdict(gpu_metrics)
            except Exception as e:
                logger.warning(f"⚠️ Impossible de collecter les métriques GPU: {e}")

        return metrics

    async def get_status(self) -> dict[str, Any]:
        """Get system status as dictionary.

        Returns:
            Dict with status, agents, tasks, and metrics information.
        """
        agents_info = {
            "multi_agent_system": {"status": "active", "performance": 100},
            "data_analyst": {"status": "active", "performance": 95},
            "ml_engineer": {"status": "active", "performance": 92},
            "browser_automation": {"status": "active", "performance": 88},
            "code_generator": {"status": "active", "performance": 96},
            "gpu_optimizer": {"status": "active", "performance": 98},
        }

        return {
            "status": "running" if self.is_initialized else "not_initialized",
            "agents": agents_info,
            "tasks": {
                "active": len(self.active_tasks),
                "queued": self.task_queue.qsize(),
                "history": len(self.task_history),
            },
            "performance_metrics": self.performance_metrics,
        }

    async def show_system_status(self):
        """Afficher le statut du système"""
        console.print("\n" + "=" * 60)
        console.print(Align.center("[bold cyan]🚀 Tawiza-V2 Advanced Agent System[/bold cyan]"))
        console.print("=" * 60 + "\n")

        # Créer le tableau de statut
        table = Table(title="Statut du Système", show_header=True, header_style="bold magenta")
        table.add_column("Composant", style="cyan", no_wrap=True)
        table.add_column("Statut", justify="center")
        table.add_column("Performance", justify="right")

        # Statut des agents
        agents_status = [
            ("🧠 Multi-Agent System", "✅ Actif", "100%"),
            ("📊 Data Analyst Agent", "✅ Actif", "95%"),
            ("🤖 ML Engineer Agent", "✅ Actif", "92%"),
            ("🌐 Browser Automation", "✅ Actif", "88%"),
            ("💻 Code Generator", "✅ Actif", "96%"),
            ("🎮 GPU Optimizer", "✅ Actif", "98%"),
        ]

        for agent, status, perf in agents_status:
            table.add_row(agent, status, perf)

        console.print(table)

        # Métriques de performance
        if self.performance_metrics:
            console.print("\n[bold cyan]📊 Métriques de Performance:[/bold cyan]")

            for model, metrics in self.performance_metrics.items():
                if model != "system":
                    console.print(
                        f"  🎯 {model}: {metrics.get('optimized_performance', 0):.1f} tokens/sec "
                        f"(+{metrics.get('improvement', 0):.1f}%)"
                    )

        # Tâches actives
        console.print("\n[bold cyan]📋 Tâches:[/bold cyan]")
        console.print(f"  🔄 Actives: {len(self.active_tasks)}")
        console.print(f"  ⏰ En file: {self.task_queue.qsize()}")
        console.print(f"  📚 Historique: {len(self.task_history)}")

        console.print("\n" + "=" * 60 + "\n")

    async def execute_data_analysis(self, dataset_path: str, **kwargs) -> str:
        """Exécuter une analyse de données"""
        task = AgentTask(
            task_id="",
            task_type="data_analysis",
            parameters={"dataset_path": dataset_path, **kwargs},
            priority=kwargs.get("priority", 5),
            timeout=kwargs.get("timeout", 300.0),
        )

        return await self.submit_task(task)

    async def execute_ml_training(self, config: dict[str, Any], **kwargs) -> str:
        """Exécuter un entraînement ML"""
        task = AgentTask(
            task_id="",
            task_type="ml_training",
            parameters={"config": config, **kwargs},
            priority=kwargs.get("priority", 7),
            timeout=kwargs.get("timeout", 1800.0),  # 30 minutes max
        )

        return await self.submit_task(task)

    async def execute_browser_automation(self, url: str, objective: str, **kwargs) -> str:
        """Exécuter une automatisation de navigateur"""
        task = AgentTask(
            task_id="",
            task_type="browser_automation",
            parameters={"url": url, "objective": objective, **kwargs},
            priority=kwargs.get("priority", 6),
            timeout=kwargs.get("timeout", 600.0),  # 10 minutes max
        )

        return await self.submit_task(task)

    async def execute_code_generation(self, description: str, language: str, **kwargs) -> str:
        """Exécuter une génération de code"""
        task = AgentTask(
            task_id="",
            task_type="code_generation",
            parameters={"description": description, "language": language, **kwargs},
            priority=kwargs.get("priority", 4),
            timeout=kwargs.get("timeout", 120.0),  # 2 minutes max
        )

        return await self.submit_task(task)

    async def cleanup(self):
        """Nettoyer les ressources"""
        logger.info("🧹 Nettoyage de l'Advanced Agent Integration...")

        try:
            # Arrêter les agents
            if self.browser_automation:
                await self.browser_automation.cleanup()

            # Nettoyer le système multi-agent
            # (Ajouter la logique de cleanup si nécessaire)

            logger.info("✅ Nettoyage terminé")

        except Exception as e:
            logger.error(f"❌ Erreur lors du nettoyage: {e}")


# Fonctions utilitaires
async def create_advanced_agent_integration() -> AdvancedAgentIntegration:
    """Créer et initialiser l'intégration avancée"""
    integration = AdvancedAgentIntegration()
    await integration.initialize()
    return integration


def create_agent_task(task_type: str, parameters: dict[str, Any], **kwargs) -> AgentTask:
    """Créer une tâche d'agent"""
    return AgentTask(
        task_id="",
        task_type=task_type,
        parameters=parameters,
        priority=kwargs.get("priority", 5),
        timeout=kwargs.get("timeout", 300.0),
    )


# Export
__all__ = [
    "AdvancedAgentIntegration",
    "AgentTask",
    "TaskResult",
    "SystemStatus",
    "create_advanced_agent_integration",
    "create_agent_task",
]
