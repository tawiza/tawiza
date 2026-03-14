#!/usr/bin/env python3
"""
Advanced Debugger System for Tawiza-V2
Système de débogage complet pour l'architecture multi-agents
"""

import asyncio
import faulthandler
import gc
import json
import logging
import sys
import traceback
import tracemalloc
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psutil
from loguru import logger
from rich.console import Console

# Configuration du logging
console = Console()
root_logger = logging.getLogger()
agent_logger = logging.getLogger("agents")


@dataclass
class DebugInfo:
    """Information de débogage"""

    timestamp: str
    component: str
    level: str
    message: str
    context: dict[str, Any]
    stack_trace: str | None = None
    memory_usage: float | None = None
    cpu_usage: float | None = None
    gpu_usage: float | None = None


@dataclass
class PerformanceMetrics:
    """Métriques de performance"""

    timestamp: str
    component: str
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    gpu_utilization: float | None = None
    gpu_memory_mb: float | None = None
    response_time_ms: float | None = None
    throughput: float | None = None
    error_rate: float | None = None


@dataclass
class AgentDebugInfo:
    """Information de débogage spécifique aux agents"""

    agent_id: str
    agent_type: str
    status: str
    task_count: int
    error_count: int
    avg_response_time: float
    memory_usage_mb: float
    last_activity: str
    current_task: str | None = None
    stack_trace: str | None = None


class AdvancedDebugger:
    """Debugger avancé pour le système multi-agents"""

    def __init__(self, debug_level: str = "INFO", enable_profiling: bool = True):
        self.debug_level = debug_level
        self.enable_profiling = enable_profiling
        self.is_running = False
        self.debug_data: list[DebugInfo] = []
        self.performance_data: list[PerformanceMetrics] = []
        self.agent_debug_info: dict[str, AgentDebugInfo] = {}
        self.error_tracker: dict[str, int] = defaultdict(int)
        self.warning_tracker: dict[str, int] = defaultdict(int)
        self.memory_snapshots: deque = deque(maxlen=100)
        self.performance_monitor = PerformanceMonitor()
        self.memory_profiler = MemoryProfiler()
        self.agent_tracer = AgentTracer()
        self.system_monitor = SystemMonitor()

        # Configuration du logging avancé
        self._setup_advanced_logging()

        # Activer les outils de debugging système
        if enable_profiling:
            faulthandler.enable()
            tracemalloc.start()

        logger.info("🐛 Advanced Debugger initialisé")

    def _setup_advanced_logging(self):
        """Configuration du logging avancé"""
        # Handler pour fichier de log structuré
        log_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s | %(funcName)s:%(lineno)d"
        )

        # Créer le répertoire de logs
        Path("logs").mkdir(exist_ok=True)

        # Fichier de log principal
        file_handler = logging.FileHandler("logs/advanced_debug.log")
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(getattr(logging, self.debug_level))

        # Handler pour les erreurs critiques
        error_handler = logging.FileHandler("logs/critical_errors.log")
        error_handler.setFormatter(log_formatter)
        error_handler.setLevel(logging.ERROR)

        # Handler console avec couleurs
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        console_handler.setLevel(logging.INFO)

        # Configuration du logger root
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(console_handler)

        # Logger spécifique pour les agents
        agent_logger.setLevel(logging.DEBUG)

    async def start_debugging(self):
        """Démarrer le système de débogage"""
        if self.is_running:
            logger.warning("Le débogage est déjà en cours")
            return

        self.is_running = True
        logger.info("🚀 Démarrage du système de débogage avancé")

        # Démarrer les moniteurs
        await self.performance_monitor.start()
        await self.memory_profiler.start()
        await self.agent_tracer.start()
        await self.system_monitor.start()

        # Démarrer la collecte de données
        asyncio.create_task(self._data_collection_loop())
        asyncio.create_task(self._health_check_loop())

        logger.info("✅ Système de débogage démarré avec succès")

    async def stop_debugging(self):
        """Arrêter le système de débogage"""
        if not self.is_running:
            return

        self.is_running = False
        logger.info("🛑 Arrêt du système de débogage")

        # Arrêter les moniteurs
        await self.performance_monitor.stop()
        await self.memory_profiler.stop()
        await self.agent_tracer.stop()
        await self.system_monitor.stop()

        # Générer le rapport final
        await self.generate_final_report()

        logger.info("✅ Système de débogage arrêté")

    def log_debug(self, component: str, message: str, level: str = "INFO", **context):
        """Enregistrer une information de débogage"""
        debug_info = DebugInfo(
            timestamp=datetime.now().isoformat(),
            component=component,
            level=level,
            message=message,
            context=context,
            memory_usage=self._get_current_memory_usage(),
            cpu_usage=self._get_current_cpu_usage(),
            gpu_usage=self._get_current_gpu_usage(),
        )

        self.debug_data.append(debug_info)

        # Limiter la taille des données
        if len(self.debug_data) > 10000:
            self.debug_data = self.debug_data[-5000:]

        # Logger selon le niveau
        logger_func = getattr(logger, level.lower())
        logger_func(f"[{component}] {message}")

    def log_error(self, component: str, error: Exception, context: dict[str, Any] = None):
        """Enregistrer une erreur avec stack trace complète"""
        stack_trace = traceback.format_exc()

        debug_info = DebugInfo(
            timestamp=datetime.now().isoformat(),
            component=component,
            level="ERROR",
            message=str(error),
            context=context or {},
            stack_trace=stack_trace,
            memory_usage=self._get_current_memory_usage(),
            cpu_usage=self._get_current_cpu_usage(),
            gpu_usage=self._get_current_gpu_usage(),
        )

        self.debug_data.append(debug_info)
        self.error_tracker[component] += 1

        logger.error(f"❌ [{component}] {error}\n{stack_trace}")

    def log_agent_activity(self, agent_id: str, agent_type: str, activity: str, **kwargs):
        """Enregistrer l'activité d'un agent"""
        self.log_debug(
            f"agent.{agent_id}",
            f"Activity: {activity}",
            level="INFO",
            agent_type=agent_type,
            activity=activity,
            **kwargs,
        )

        # Mettre à jour les infos de débogage de l'agent
        if agent_id not in self.agent_debug_info:
            self.agent_debug_info[agent_id] = AgentDebugInfo(
                agent_id=agent_id,
                agent_type=agent_type,
                status="active",
                task_count=0,
                error_count=0,
                avg_response_time=0.0,
                memory_usage_mb=0.0,
                last_activity=datetime.now().isoformat(),
            )

        agent_info = self.agent_debug_info[agent_id]
        agent_info.last_activity = datetime.now().isoformat()

        if activity == "task_started":
            agent_info.task_count += 1
            agent_info.current_task = kwargs.get("task_id")
        elif activity == "task_completed":
            agent_info.current_task = None
        elif activity == "error":
            agent_info.error_count += 1
            agent_info.stack_trace = kwargs.get("stack_trace")

    async def _data_collection_loop(self):
        """Boucle de collecte de données de performance"""
        while self.is_running:
            try:
                # Collecter les métriques système
                metrics = await self._collect_system_metrics()
                self.performance_data.append(metrics)

                # Limiter la taille des données
                if len(self.performance_data) > 5000:
                    self.performance_data = self.performance_data[-2500:]

                # Prendre un snapshot mémoire
                if len(self.performance_data) % 10 == 0:  # Toutes les 10 itérations
                    snapshot = self.memory_profiler.take_snapshot()
                    if snapshot:
                        self.memory_snapshots.append(snapshot)

                await asyncio.sleep(1)  # Collecte chaque seconde

            except Exception as e:
                logger.error(f"Erreur dans la boucle de collecte: {e}")
                await asyncio.sleep(5)

    async def _health_check_loop(self):
        """Boucle de vérification de santé"""
        while self.is_running:
            try:
                # Vérifier la santé de chaque composant
                await self._check_agent_health()
                await self._check_system_health()
                await self._check_memory_health()

                await asyncio.sleep(30)  # Vérification toutes les 30 secondes

            except Exception as e:
                logger.error(f"Erreur dans la boucle de santé: {e}")
                await asyncio.sleep(10)

    async def _collect_system_metrics(self) -> PerformanceMetrics:
        """Collecter les métriques système"""
        # CPU et mémoire
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        # GPU (si disponible)
        gpu_utilization = None
        gpu_memory_mb = None

        try:
            import GPUtil

            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # Première GPU
                gpu_utilization = gpu.load * 100
                gpu_memory_mb = gpu.memoryUsed
        except Exception as e:
            logger.debug(f"GPU metrics unavailable: {e}")

        return PerformanceMetrics(
            timestamp=datetime.now().isoformat(),
            component="system",
            cpu_percent=cpu_percent,
            memory_mb=memory.used / 1024 / 1024,  # Convertir en MB
            memory_percent=memory.percent,
            gpu_utilization=gpu_utilization,
            gpu_memory_mb=gpu_memory_mb,
        )

    async def _check_agent_health(self):
        """Vérifier la santé des agents"""
        for agent_id, agent_info in self.agent_debug_info.items():
            # Vérifier si l'agent est actif
            last_activity = datetime.fromisoformat(agent_info.last_activity)
            time_since_activity = (datetime.now() - last_activity).total_seconds()

            if time_since_activity > 300:  # 5 minutes sans activité
                self.log_debug(
                    "health_check",
                    f"Agent {agent_id} semble inactif",
                    level="WARNING",
                    agent_id=agent_id,
                    time_since_activity=time_since_activity,
                )

            # Vérifier le taux d'erreur
            if agent_info.error_count > 10:
                self.log_debug(
                    "health_check",
                    f"Agent {agent_id} a un taux d'erreur élevé",
                    level="ERROR",
                    agent_id=agent_id,
                    error_count=agent_info.error_count,
                )

    async def _check_system_health(self):
        """Vérifier la santé du système"""
        if not self.performance_data:
            return

        latest_metrics = self.performance_data[-1]

        # Vérifier l'utilisation CPU
        if latest_metrics.cpu_percent > 90:
            self.log_debug(
                "health_check",
                "Utilisation CPU très élevée",
                level="WARNING",
                cpu_percent=latest_metrics.cpu_percent,
            )

        # Vérifier l'utilisation mémoire
        if latest_metrics.memory_percent > 85:
            self.log_debug(
                "health_check",
                "Utilisation mémoire très élevée",
                level="WARNING",
                memory_percent=latest_metrics.memory_percent,
            )

        # Vérifier la température GPU
        if latest_metrics.gpu_utilization and latest_metrics.gpu_utilization > 95:
            self.log_debug(
                "health_check",
                "Utilisation GPU très élevée",
                level="WARNING",
                gpu_utilization=latest_metrics.gpu_utilization,
            )

    async def _check_memory_health(self):
        """Vérifier la santé mémoire"""
        if not self.memory_snapshots:
            return

        latest_snapshot = self.memory_snapshots[-1]

        # Détecter les fuites mémoire
        if len(self.memory_snapshots) >= 2:
            prev_snapshot = self.memory_snapshots[-2]
            memory_growth = latest_snapshot.total_memory - prev_snapshot.total_memory

            if memory_growth > 100 * 1024 * 1024:  # 100MB de croissance
                self.log_debug(
                    "memory_health",
                    "Croissance mémoire significative détectée",
                    level="WARNING",
                    memory_growth_mb=memory_growth / 1024 / 1024,
                )

    def _get_current_memory_usage(self) -> float:
        """Obtenir l'utilisation mémoire actuelle"""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB

    def _get_current_cpu_usage(self) -> float:
        """Obtenir l'utilisation CPU actuelle"""
        return psutil.cpu_percent(interval=0.1)

    def _get_current_gpu_usage(self) -> float | None:
        """Obtenir l'utilisation GPU actuelle"""
        try:
            import GPUtil

            gpus = GPUtil.getGPUs()
            if gpus:
                return gpus[0].load * 100
        except Exception as e:
            logger.debug(f"Could not get GPU usage: {e}")
        return None

    async def generate_debug_report(self) -> dict[str, Any]:
        """Générer un rapport de débogage complet"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "system_info": await self._get_system_info(),
            "performance_summary": self._get_performance_summary(),
            "agent_status": self._get_agent_status_summary(),
            "error_analysis": self._get_error_analysis(),
            "memory_analysis": self._get_memory_analysis(),
            "recommendations": self._generate_recommendations(),
        }

        return report

    async def _get_system_info(self) -> dict[str, Any]:
        """Obtenir les informations système"""
        return {
            "python_version": sys.version,
            "platform": sys.platform,
            "cpu_count": psutil.cpu_count(),
            "total_memory_gb": psutil.virtual_memory().total / 1024 / 1024 / 1024,
            "disk_usage": psutil.disk_usage("/").percent,
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
        }

    def _get_performance_summary(self) -> dict[str, Any]:
        """Obtenir un résumé des performances"""
        if not self.performance_data:
            return {"error": "Aucune donnée de performance disponible"}

        recent_metrics = self.performance_data[-100:]  # 100 dernières mesures

        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]

        return {
            "period": f"{len(recent_metrics)} dernières mesures",
            "cpu": {
                "average": sum(cpu_values) / len(cpu_values),
                "max": max(cpu_values),
                "min": min(cpu_values),
            },
            "memory": {
                "average": sum(memory_values) / len(memory_values),
                "max": max(memory_values),
                "min": min(memory_values),
            },
            "gpu": self._get_gpu_summary(recent_metrics),
        }

    def _get_gpu_summary(self, metrics: list[PerformanceMetrics]) -> dict[str, Any]:
        """Obtenir un résumé GPU"""
        gpu_metrics = [m for m in metrics if m.gpu_utilization is not None]
        if not gpu_metrics:
            return {"status": "GPU non disponible"}

        gpu_util_values = [m.gpu_utilization for m in gpu_metrics]
        gpu_memory_values = [m.gpu_memory_mb for m in gpu_metrics if m.gpu_memory_mb is not None]

        return {
            "utilization": {
                "average": sum(gpu_util_values) / len(gpu_util_values),
                "max": max(gpu_util_values),
                "min": min(gpu_util_values),
            },
            "memory": {
                "average": sum(gpu_memory_values) / len(gpu_memory_values)
                if gpu_memory_values
                else 0,
                "max": max(gpu_memory_values) if gpu_memory_values else 0,
                "min": min(gpu_memory_values) if gpu_memory_values else 0,
            },
        }

    def _get_agent_status_summary(self) -> dict[str, Any]:
        """Obtenir un résumé du statut des agents"""
        if not self.agent_debug_info:
            return {"status": "Aucun agent actif"}

        total_agents = len(self.agent_debug_info)
        active_agents = sum(
            1 for agent in self.agent_debug_info.values() if agent.status == "active"
        )
        total_tasks = sum(agent.task_count for agent in self.agent_debug_info.values())
        total_errors = sum(agent.error_count for agent in self.agent_debug_info.values())

        return {
            "total_agents": total_agents,
            "active_agents": active_agents,
            "total_tasks": total_tasks,
            "total_errors": total_errors,
            "agents": [asdict(agent) for agent in self.agent_debug_info.values()],
        }

    def _get_error_analysis(self) -> dict[str, Any]:
        """Analyser les erreurs"""
        if not self.error_tracker:
            return {"status": "Aucune erreur enregistrée"}

        total_errors = sum(self.error_tracker.values())
        error_by_component = dict(self.error_tracker)

        # Analyser les erreurs récentes
        recent_errors = [d for d in self.debug_data if d.level == "ERROR"][-50:]

        return {
            "total_errors": total_errors,
            "errors_by_component": error_by_component,
            "recent_errors": [asdict(error) for error in recent_errors],
            "error_rate": total_errors / max(len(self.debug_data), 1) * 100,
        }

    def _get_memory_analysis(self) -> dict[str, Any]:
        """Analyser l'utilisation mémoire"""
        if not self.memory_snapshots:
            return {"status": "Aucune analyse mémoire disponible"}

        latest_snapshot = self.memory_snapshots[-1]

        # Détecter les fuites mémoire
        memory_leaks = []
        if len(self.memory_snapshots) >= 5:
            recent_snapshots = list(self.memory_snapshots)[-5:]
            for i in range(1, len(recent_snapshots)):
                growth = recent_snapshots[i].total_memory - recent_snapshots[i - 1].total_memory
                if growth > 50 * 1024 * 1024:  # 50MB
                    memory_leaks.append(
                        {
                            "timestamp": recent_snapshots[i].timestamp,
                            "growth_mb": growth / 1024 / 1024,
                        }
                    )

        return {
            "current_memory_mb": latest_snapshot.total_memory / 1024 / 1024,
            "object_count": len(latest_snapshot.objects),
            "memory_leaks": memory_leaks,
            "top_objects": latest_snapshot.top_objects[:10],
        }

    def _generate_recommendations(self) -> list[str]:
        """Générer des recommandations basées sur l'analyse"""
        recommendations = []

        # Analyser les performances
        if self.performance_data:
            latest = self.performance_data[-1]
            if latest.cpu_percent > 80:
                recommendations.append("CPU très utilisé - envisagez une répartition de charge")
            if latest.memory_percent > 85:
                recommendations.append("Mémoire presque pleine - surveillez les fuites mémoire")

        # Analyser les erreurs
        if self.error_tracker:
            total_errors = sum(self.error_tracker.values())
            if total_errors > 10:
                recommendations.append(
                    "Taux d'erreur élevé - analysez les logs pour identifier les problèmes"
                )

        # Analyser les agents
        if self.agent_debug_info:
            for agent_id, agent in self.agent_debug_info.items():
                if agent.error_count > 5:
                    recommendations.append(
                        f"Agent {agent_id} a des problèmes - redémarrez ou vérifiez la configuration"
                    )

        # Analyser la mémoire
        if self.memory_snapshots:
            latest = self.memory_snapshots[-1]
            if len(self.memory_snapshots) >= 5:
                recent_growth = []
                for i in range(1, min(5, len(self.memory_snapshots))):
                    growth = (
                        self.memory_snapshots[i].total_memory
                        - self.memory_snapshots[i - 1].total_memory
                    )
                    recent_growth.append(growth)

                avg_growth = sum(recent_growth) / len(recent_growth)
                if avg_growth > 10 * 1024 * 1024:  # 10MB average growth
                    recommendations.append(
                        "Croissance mémoire détectée - vérifiez les fuites mémoire"
                    )

        if not recommendations:
            recommendations.append("Système fonctionne normalement - aucune action requise")

        return recommendations

    async def generate_final_report(self):
        """Générer un rapport final complet"""
        report = await self.generate_debug_report()

        # Sauvegarder le rapport
        report_file = f"debug_reports/debug_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        Path(report_file).parent.mkdir(exist_ok=True)

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"📊 Rapport de débogage sauvegardé: {report_file}")

        # Afficher un résumé
        self._display_summary_report(report)

    def _display_summary_report(self, report: dict[str, Any]):
        """Afficher un résumé du rapport"""
        console.print("\n" + "=" * 60)
        console.print("[bold cyan]📊 Rapport de Débogage Final[/bold cyan]")
        console.print("=" * 60 + "\n")

        # Résumé des performances
        perf_summary = report.get("performance_summary", {})
        if "cpu" in perf_summary:
            console.print("[bold cyan]🖥️  Performance CPU:[/bold cyan]")
            console.print(f"  • Moyenne: {perf_summary['cpu']['average']:.1f}%")
            console.print(f"  • Max: {perf_summary['cpu']['max']:.1f}%")
            console.print(f"  • Min: {perf_summary['cpu']['min']:.1f}%")
            console.print()

        # Résumé des agents
        agent_summary = report.get("agent_status", {})
        if "total_agents" in agent_summary:
            console.print("[bold cyan]🤖 Agents:[/bold cyan]")
            console.print(f"  • Total: {agent_summary['total_agents']}")
            console.print(f"  • Actifs: {agent_summary['active_agents']}")
            console.print(f"  • Tâches: {agent_summary['total_tasks']}")
            console.print(f"  • Erreurs: {agent_summary['total_errors']}")
            console.print()

        # Recommandations
        recommendations = report.get("recommendations", [])
        if recommendations:
            console.print("[bold yellow]💡 Recommandations:[/bold yellow]")
            for i, rec in enumerate(recommendations, 1):
                console.print(f"  {i}. {rec}")
            console.print()

        console.print("=" * 60 + "\n")


# Classes auxiliaires pour le monitoring


class PerformanceMonitor:
    """Moniteur de performance spécialisé"""

    def __init__(self):
        self.is_running = False
        self.metrics_history = []

    async def start(self):
        """Démarrer le monitoring"""
        self.is_running = True
        logger.info("📊 Performance Monitor démarré")

    async def stop(self):
        """Arrêter le monitoring"""
        self.is_running = False
        logger.info("📊 Performance Monitor arrêté")

    def record_metric(self, metric: PerformanceMetrics):
        """Enregistrer une métrique"""
        self.metrics_history.append(metric)

        # Limiter l'historique
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-500:]


class MemoryProfiler:
    """Profileur mémoire avancé"""

    def __init__(self):
        self.is_running = False
        self.snapshots = []

    async def start(self):
        """Démarrer le profileur mémoire"""
        self.is_running = True
        logger.info("💾 Memory Profiler démarré")

    async def stop(self):
        """Arrêter le profileur mémoire"""
        self.is_running = False
        logger.info("💾 Memory Profiler arrêté")

    def take_snapshot(self) -> Optional["MemorySnapshot"]:
        """Prendre un snapshot mémoire"""
        if not self.is_running:
            return None

        # Obtenir les statistiques mémoire
        current_memory = self._get_current_memory()

        # Analyser les objets Python
        gc.collect()  # Forcer le garbage collection

        # Obtenir les objets les plus volumineux
        top_objects = self._get_top_objects(20)

        snapshot = MemorySnapshot(
            timestamp=datetime.now().isoformat(), total_memory=current_memory, objects=top_objects
        )

        self.snapshots.append(snapshot)
        return snapshot

    def _get_current_memory(self) -> int:
        """Obtenir la mémoire actuelle en octets"""
        process = psutil.Process()
        return process.memory_info().rss

    def _get_top_objects(self, count: int) -> list[dict[str, Any]]:
        """Obtenir les objets les plus volumineux"""
        try:
            import objgraph

            # Obtenir les types d'objets les plus communs
            obj_types = objgraph.get_most_common_types(limit=count)

            objects = []
            for obj_type, count in obj_types:
                objects.append(
                    {
                        "type": obj_type,
                        "count": count,
                        "size_bytes": self._estimate_object_size(obj_type, count),
                    }
                )

            return objects

        except ImportError:
            logger.warning("objgraph non installé - analyse mémoire limitée")
            return []

    def _estimate_object_size(self, obj_type: str, count: int) -> int:
        """Estimer la taille d'un type d'objet"""
        # Estimations basiques
        size_map = {
            "dict": 280,  # bytes par dict
            "list": 72,  # bytes par list
            "str": 50,  # bytes moyens par string
            "int": 28,  # bytes par int
            "function": 136,  # bytes par function
            "type": 904,  # bytes par type
        }

        return count * size_map.get(obj_type, 100)  # 100 bytes par défaut


class AgentTracer:
    """Traceur d'agents pour le debugging"""

    def __init__(self):
        self.is_running = False
        self.traces = {}

    async def start(self):
        """Démarrer le traceur"""
        self.is_running = True
        logger.info("🔍 Agent Tracer démarré")

    async def stop(self):
        """Arrêter le traceur"""
        self.is_running = False
        logger.info("🔍 Agent Tracer arrêté")

    def start_trace(self, agent_id: str, task_id: str):
        """Commencer une trace"""
        if not self.is_running:
            return

        self.traces[task_id] = {"agent_id": agent_id, "start_time": datetime.now(), "steps": []}

    def add_trace_step(self, task_id: str, step: str, data: dict[str, Any] = None):
        """Ajouter une étape à la trace"""
        if task_id not in self.traces:
            return

        self.traces[task_id]["steps"].append(
            {"timestamp": datetime.now(), "step": step, "data": data or {}}
        )

    def end_trace(self, task_id: str, success: bool, result: Any = None):
        """Terminer une trace"""
        if task_id not in self.traces:
            return

        trace = self.traces[task_id]
        trace["end_time"] = datetime.now()
        trace["duration"] = (trace["end_time"] - trace["start_time"]).total_seconds()
        trace["success"] = success
        trace["result"] = result

        # Log la trace
        logger.info(f"Trace complétée pour tâche {task_id}: {trace['duration']:.2f}s")


class SystemMonitor:
    """Moniteur système global"""

    def __init__(self):
        self.is_running = False

    async def start(self):
        """Démarrer le moniteur système"""
        self.is_running = True
        logger.info("🖥️  System Monitor démarré")

    async def stop(self):
        """Arrêter le moniteur système"""
        self.is_running = False
        logger.info("🖥️  System Monitor arrêté")


@dataclass
class MemorySnapshot:
    """Snapshot mémoire"""

    timestamp: str
    total_memory: int
    objects: list[dict[str, Any]]


# Import du thème sunset centralisé


# Fonctions utilitaires
def create_advanced_debugger(
    debug_level: str = "INFO", enable_profiling: bool = True
) -> AdvancedDebugger:
    """Créer et initialiser le debugger avancé"""
    return AdvancedDebugger(debug_level, enable_profiling)


async def start_debugging_session() -> AdvancedDebugger:
    """Démarrer une session de débogage"""
    debugger = create_advanced_debugger()
    await debugger.start_debugging()
    return debugger


# Export
__all__ = [
    "AdvancedDebugger",
    "DebugInfo",
    "PerformanceMetrics",
    "AgentDebugInfo",
    "create_advanced_debugger",
    "start_debugging_session",
]
