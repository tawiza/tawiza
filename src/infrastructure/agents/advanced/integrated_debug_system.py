#!/usr/bin/env python3
"""
Système de Débogage Intégré pour Tawiza-V2
Intégration complète du debugging dans l'architecture multi-agents
"""

import asyncio
from datetime import datetime
from typing import Any

from loguru import logger

from src.infrastructure.agents.advanced.agent_integration import AdvancedAgentIntegration

# Import des composants
from src.infrastructure.debugging.advanced_debugger import (
    AdvancedDebugger,
    create_advanced_debugger,
)
from src.infrastructure.debugging.agent_debug_integration import (
    AgentDebugIntegration,
    enable_comprehensive_debugging,
)

# Configuration du logging

class IntegratedDebugSystem:
    """Système de débogage intégré pour Tawiza-V2"""

    def __init__(self, agent_integration: AdvancedAgentIntegration):
        self.agent_integration = agent_integration
        self.debugger: AdvancedDebugger | None = None
        self.agent_debug_integration: AgentDebugIntegration | None = None
        self.is_debugging_active = False
        self.debug_config = {
            "enable_profiling": True,
            "debug_level": "INFO",
            "max_log_entries": 10000,
            "performance_sampling_interval": 1.0,
            "health_check_interval": 30.0,
            "memory_snapshot_interval": 60.0,
            "enable_real_time_monitoring": True,
            "auto_error_detection": True,
            "anomaly_thresholds": {
                "cpu_usage": 85.0,
                "memory_usage": 85.0,
                "gpu_usage": 95.0,
                "response_time_ms": 5000.0,
                "error_rate": 10.0
            }
        }

    async def initialize_debugging(self):
        """Initialiser le système de débogage intégré"""
        logger.info("🐛 Initialisation du système de débogage intégré...")

        try:
            # Créer et configurer le debugger
            self.debugger = create_advanced_debugger(
                debug_level=self.debug_config["debug_level"],
                enable_profiling=self.debug_config["enable_profiling"]
            )

            # Démarrer le debugging
            await self.debugger.start_debugging()

            # Créer l'intégration de debugging pour les agents
            self.agent_debug_integration = enable_comprehensive_debugging(self.debugger)

            # Intégrer le debugging dans le système multi-agents
            await self._integrate_with_multi_agent_system()

            # Configurer le monitoring automatique
            await self._setup_automatic_monitoring()

            self.is_debugging_active = True
            logger.info("✅ Système de débogage intégré initialisé avec succès")

            # Afficher le statut initial
            await self.show_debug_status()

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation du debugging: {e}")
            raise

    async def _integrate_with_multi_agent_system(self):
        """Intégrer le debugging avec le système multi-agents"""
        logger.info("🔗 Intégration du debugging avec le système multi-agents...")

        # Wrapper les agents existants avec debugging
        if hasattr(self.agent_integration, 'data_analyst'):
            self._wrap_agent_with_debugging(self.agent_integration.data_analyst, "data_analyst")

        if hasattr(self.agent_integration, 'ml_engineer'):
            self._wrap_agent_with_debugging(self.agent_integration.ml_engineer, "ml_engineer")

        if hasattr(self.agent_integration, 'browser_automation'):
            self._wrap_agent_with_debugging(self.agent_integration.browser_automation, "browser_automation")

        if hasattr(self.agent_integration, 'code_generator'):
            self._wrap_agent_with_debugging(self.agent_integration.code_generator, "code_generator")

        if hasattr(self.agent_integration, 'gpu_optimizer'):
            self._wrap_agent_with_debugging(self.agent_integration.gpu_optimizer, "gpu_optimizer")

        logger.info("✅ Intégration multi-agents complétée")

    def _wrap_agent_with_debugging(self, agent_instance: Any, agent_type: str):
        """Wrapper une instance d'agent avec debugging"""
        if not agent_instance:
            return

        # Obtenir les méthodes principales de l'agent
        methods_to_wrap = [
            "process_request", "execute_task", "analyze_dataset",
            "create_ml_pipeline", "optimize_inference_performance",
            "generate_code", "execute_task"
        ]

        for method_name in methods_to_wrap:
            if hasattr(agent_instance, method_name):
                original_method = getattr(agent_instance, method_name)

                # Créer un wrapper avec debugging
                async def debug_wrapper(*args, **kwargs):
                    if not self.debugger:
                        return await original_method(*args, **kwargs)

                    agent_id = getattr(agent_instance, 'agent_id', f"{agent_type}_instance")
                    start_time = datetime.now()

                    try:
                        # Log le début de l'exécution
                        self.debugger.log_agent_activity(
                            agent_id,
                            agent_type,
                            f"method_start.{method_name}",
                            method=method_name,
                            args_count=len(args),
                            kwargs_count=len(kwargs),
                            timestamp=start_time.isoformat()
                        )

                        # Exécuter la méthode originale
                        result = await original_method(*args, **kwargs)

                        # Calculer le temps d'exécution
                        execution_time = (datetime.now() - start_time).total_seconds()

                        # Log la fin de l'exécution
                        self.debugger.log_agent_activity(
                            agent_id,
                            agent_type,
                            f"method_complete.{method_name}",
                            execution_time=execution_time,
                            success=True,
                            timestamp=datetime.now().isoformat()
                        )

                        return result

                    except Exception as e:
                        # Calculer le temps jusqu'à l'erreur
                        execution_time = (datetime.now() - start_time).total_seconds()

                        # Log l'erreur
                        self.debugger.log_error(
                            f"agent.{agent_type}.{method_name}",
                            e,
                            {
                                "agent_id": agent_id,
                                "execution_time": execution_time,
                                "method": method_name
                            }
                        )

                        # Log l'échec
                        self.debugger.log_agent_activity(
                            agent_id,
                            agent_type,
                            f"method_error.{method_name}",
                            error=str(e),
                            execution_time=execution_time,
                            success=False,
                            timestamp=datetime.now().isoformat()
                        )

                        raise

                # Remplacer la méthode par le wrapper
                setattr(agent_instance, method_name, debug_wrapper)

                logger.debug(f"✅ Méthode {method_name} de {agent_type} wrappée avec debugging")

    async def _setup_automatic_monitoring(self):
        """Configurer le monitoring automatique"""
        logger.info("📊 Configuration du monitoring automatique...")

        # Configurer les seuils d'anomalie
        if self.agent_debug_integration:
            # Ajouter des hooks pour le monitoring en temps réel
            self._setup_real_time_monitoring()

            # Configurer la détection automatique d'erreurs
            self._setup_error_detection()

            # Configurer le monitoring de performance
            self._setup_performance_monitoring()

        logger.info("✅ Monitoring automatique configuré")

    def _setup_real_time_monitoring(self):
        """Configurer le monitoring en temps réel"""
        # Créer une tâche de monitoring en arrière-plan
        if self.debugger and self.debug_config["enable_real_time_monitoring"]:
            asyncio.create_task(self._real_time_monitoring_loop())

    async def _real_time_monitoring_loop(self):
        """Boucle de monitoring en temps réel"""
        logger.info("🔄 Démarrage du monitoring en temps réel")

        while self.is_debugging_active:
            try:
                # Collecter les métriques système
                await self._collect_system_metrics()

                # Vérifier la santé des agents
                await self._check_agents_health()

                # Détecter les anomalies
                await self._detect_anomalies()

                # Attendre avant la prochaine itération
                await asyncio.sleep(self.debug_config["performance_sampling_interval"])

            except Exception as e:
                logger.error(f"❌ Erreur dans la boucle de monitoring: {e}")
                await asyncio.sleep(5)  # Attendre plus longtemps en cas d'erreur

    async def _collect_system_metrics(self):
        """Collecter les métriques système"""
        if not self.debugger:
            return

        # Les métriques sont déjà collectées par le debugger
        # Cette méthode peut être étendue pour des métriques supplémentaires
        pass

    async def _check_agents_health(self):
        """Vérifier la santé des agents"""
        if not self.debugger or not self.agent_integration:
            return

        # Vérifier chaque agent
        agents_to_check = [
            ("data_analyst", self.agent_integration.data_analyst),
            ("ml_engineer", self.agent_integration.ml_engineer),
            ("browser_automation", self.agent_integration.browser_automation),
            ("code_generator", self.agent_integration.code_generator),
            ("gpu_optimizer", self.agent_integration.gpu_optimizer)
        ]

        for agent_type, agent in agents_to_check:
            if agent and hasattr(agent, 'is_initialized') and not agent.is_initialized:
                self.debugger.log_debug(
                    f"health_check.{agent_type}",
                    f"Agent {agent_type} non initialisé",
                    level="WARNING",
                    agent_type=agent_type
                )

    async def _detect_anomalies(self):
        """Détecter les anomalies dans le système"""
        if not self.debugger or not self.debug_config["auto_error_detection"]:
            return

        # Obtenir les dernières métriques
        if self.debugger.performance_data:
            latest_metrics = self.debugger.performance_data[-1]

            # Vérifier les seuils d'anomalie
            thresholds = self.debug_config["anomaly_thresholds"]

            # CPU usage
            if latest_metrics.cpu_percent > thresholds["cpu_usage"]:
                self.debugger.log_debug(
                    "anomaly_detection",
                    "Utilisation CPU anormalement élevée détectée",
                    level="WARNING",
                    cpu_percent=latest_metrics.cpu_percent,
                    threshold=thresholds["cpu_usage"]
                )

            # Memory usage
            if latest_metrics.memory_percent > thresholds["memory_usage"]:
                self.debugger.log_debug(
                    "anomaly_detection",
                    "Utilisation mémoire anormalement élevée détectée",
                    level="WARNING",
                    memory_percent=latest_metrics.memory_percent,
                    threshold=thresholds["memory_usage"]
                )

            # GPU usage (si disponible)
            if latest_metrics.gpu_utilization and latest_metrics.gpu_utilization > thresholds["gpu_usage"]:
                self.debugger.log_debug(
                    "anomaly_detection",
                    "Utilisation GPU anormalement élevée détectée",
                    level="WARNING",
                    gpu_utilization=latest_metrics.gpu_utilization,
                    threshold=thresholds["gpu_usage"]
                )

    def _setup_error_detection(self):
        """Configurer la détection automatique d'erreurs"""
        # La détection est déjà intégrée dans le système de logging
        # Cette méthode peut être étendue pour des règles de détection supplémentaires
        pass

    def _setup_performance_monitoring(self):
        """Configurer le monitoring de performance"""
        # Le monitoring de performance est déjà actif via le debugger
        # Cette méthode peut être étendue pour des métriques personnalisées
        pass

    async def show_debug_status(self):
        """Afficher le statut du debugging"""
        if not self.debugger:
            logger.warning("⚠️  Debugger non disponible")
            return

        # Générer et afficher un rapport rapide
        try:
            report = await self.debugger.generate_debug_report()

            logger.info("📊 Statut du Système de Débogage:")
            logger.info(f"  • Timestamp: {report.get('timestamp', 'N/A')}")

            # Performance summary
            perf_summary = report.get("performance_summary", {})
            if "cpu" in perf_summary:
                logger.info(f"  • CPU Moyenne: {perf_summary['cpu']['average']:.1f}%")
                logger.info(f"  • Memory Moyenne: {perf_summary['memory']['average']:.1f}%")

            # Agent status
            agent_summary = report.get("agent_status", {})
            if "total_agents" in agent_summary:
                logger.info(f"  • Agents Total: {agent_summary['total_agents']}")
                logger.info(f"  • Agents Actifs: {agent_summary['active_agents']}")
                logger.info(f"  • Tâches: {agent_summary['total_tasks']}")
                logger.info(f"  • Erreurs: {agent_summary['total_errors']}")

            # Recommandations
            recommendations = report.get("recommendations", [])
            if recommendations:
                logger.info("  • Recommandations:")
                for i, rec in enumerate(recommendations[:3], 1):
                    logger.info(f"    {i}. {rec}")

        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération du rapport de statut: {e}")

    async def get_debug_insights(self) -> dict[str, Any]:
        """Obtenir des insights de debugging"""
        if not self.debugger or not self.agent_debug_integration:
            return {"error": "Système de debugging non initialisé"}

        try:
            # Générer le rapport complet
            report = await self.debugger.generate_debug_report()

            # Ajouter des insights spécifiques aux agents
            agent_insights = {}
            if self.agent_debug_integration:
                for agent_type in ["data_analyst", "ml_engineer", "browser_automation", "code_generator", "gpu_optimizer"]:
                    agent_insights[agent_type] = self.agent_debug_integration.get_debug_summary(agent_type)

            return {
                "system_report": report,
                "agent_insights": agent_insights,
                "debugging_active": self.is_debugging_active,
                "config": self.debug_config,
                "uptime": self._calculate_uptime()
            }

        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération des insights: {e}")
            return {"error": str(e)}

    def _calculate_uptime(self) -> float:
        """Calculer le temps de fonctionnement du debugging"""
        # Cette méthode peut être étendue pour un calcul réel
        return 0.0  # Placeholder

    async def generate_comprehensive_debug_report(self) -> dict[str, Any]:
        """Générer un rapport de débogage complet"""
        if not self.debugger:
            return {"error": "Debugger non disponible"}

        try:
            # Générer le rapport de base
            base_report = await self.debugger.generate_debug_report()

            # Ajouter des informations spécifiques au système d'agents
            enhanced_report = {
                **base_report,
                "agent_system_info": await self._get_agent_system_info(),
                "debugging_config": self.debug_config,
                "integration_status": {
                    "multi_agent_system": self._check_multi_agent_system_status(),
                    "gpu_optimization": self._check_gpu_optimization_status(),
                    "task_queue": self._check_task_queue_status()
                },
                "performance_analysis": await self._analyze_performance(),
                "reliability_metrics": self._calculate_reliability_metrics()
            }

            return enhanced_report

        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération du rapport complet: {e}")
            return {"error": str(e)}

    async def _get_agent_system_info(self) -> dict[str, Any]:
        """Obtenir des informations spécifiques au système d'agents"""
        info = {
            "active_agents": 0,
            "queued_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "average_response_time": 0.0,
            "gpu_performance": {}
        }

        if self.agent_integration:
            # Compter les agents actifs
            agents = [
                self.agent_integration.data_analyst,
                self.agent_integration.ml_engineer,
                self.agent_integration.browser_automation,
                self.agent_integration.code_generator,
                self.agent_integration.gpu_optimizer
            ]

            info["active_agents"] = sum(1 for agent in agents if agent and getattr(agent, 'is_initialized', False))
            info["queued_tasks"] = self.agent_integration.task_queue.qsize()
            info["completed_tasks"] = len([t for t in self.agent_integration.task_history if t.get("status") == "completed"])
            info["failed_tasks"] = len([t for t in self.agent_integration.task_history if t.get("status") == "failed"])

            # Performance GPU
            if self.agent_integration.performance_metrics:
                info["gpu_performance"] = self.agent_integration.performance_metrics

        return info

    def _check_multi_agent_system_status(self) -> dict[str, Any]:
        """Vérifier le statut du système multi-agents"""
        if not self.agent_integration or not self.agent_integration.multi_agent_system:
            return {"status": "non_disponible"}

        return {
            "status": "actif",
            "coordinator": self.agent_integration.multi_agent_system.coordinator is not None,
            "registry": self.agent_integration.multi_agent_system.registry is not None,
            "memory": self.agent_integration.multi_agent_system.memory is not None
        }

    def _check_gpu_optimization_status(self) -> dict[str, Any]:
        """Vérifier le statut de l'optimisation GPU"""
        if not self.agent_integration or not self.agent_integration.gpu_optimizer:
            return {"status": "non_disponible"}

        return {
            "status": "actif",
            "is_initialized": self.agent_integration.gpu_optimizer.is_initialized,
            "models_optimized": len(self.agent_integration.gpu_optimizer.optimization_history)
        }

    def _check_task_queue_status(self) -> dict[str, Any]:
        """Vérifier le statut de la file de tâches"""
        if not self.agent_integration:
            return {"status": "non_disponible"}

        return {
            "status": "actif",
            "queue_size": self.agent_integration.task_queue.qsize(),
            "active_tasks": len(self.agent_integration.active_tasks),
            "history_size": len(self.agent_integration.task_history)
        }

    async def _analyze_performance(self) -> dict[str, Any]:
        """Analyser les performances du système"""
        if not self.debugger or not self.debugger.performance_data:
            return {"status": "aucune_donnee"}

        recent_metrics = self.debugger.performance_data[-100:]  # 100 dernières mesures

        if not recent_metrics:
            return {"status": "pas_assez_de_donnees"}

        # Analyser les tendances
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]

        return {
            "cpu_analysis": {
                "average": sum(cpu_values) / len(cpu_values),
                "trend": self._calculate_trend(cpu_values),
                "peak_usage": max(cpu_values)
            },
            "memory_analysis": {
                "average": sum(memory_values) / len(memory_values),
                "trend": self._calculate_trend(memory_values),
                "peak_usage": max(memory_values)
            },
            "efficiency_score": self._calculate_efficiency_score(cpu_values, memory_values)
        }

    def _calculate_trend(self, values: list[float]) -> str:
        """Calculer la tendance d'une série de valeurs"""
        if len(values) < 2:
            return "stable"

        # Simple analyse de tendance
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        if avg_second > avg_first * 1.1:  # 10% d'augmentation
            return "croissante"
        elif avg_second < avg_first * 0.9:  # 10% de diminution
            return "décroissante"
        else:
            return "stable"

    def _calculate_efficiency_score(self, cpu_values: list[float], memory_values: list[float]) -> float:
        """Calculer un score d'efficacité basé sur l'utilisation des ressources"""
        if not cpu_values or not memory_values:
            return 0.0

        # Score basé sur l'utilisation optimale (60-80%)
        def calculate_resource_score(values: list[float]) -> float:
            avg_usage = sum(values) / len(values)

            if avg_usage < 30:  # Sous-utilisation
                return 50.0
            elif avg_usage < 60:  # Utilisation faible mais acceptable
                return 70.0
            elif avg_usage < 85:  # Utilisation optimale
                return 90.0
            elif avg_usage < 95:  # Utilisation élevée
                return 70.0
            else:  # Sur-utilisation
                return 30.0

        cpu_score = calculate_resource_score(cpu_values)
        memory_score = calculate_resource_score(memory_values)

        return (cpu_score + memory_score) / 2

    def _calculate_reliability_metrics(self) -> dict[str, Any]:
        """Calculer les métriques de fiabilité"""
        if not self.debugger or not self.debugger.debug_data:
            return {"status": "aucune_donnee"}

        total_entries = len(self.debugger.debug_data)
        error_entries = len([d for d in self.debugger.debug_data if d.level == "ERROR"])
        warning_entries = len([d for d in self.debugger.debug_data if d.level == "WARNING"])

        return {
            "total_operations": total_entries,
            "error_count": error_entries,
            "warning_count": warning_entries,
            "error_rate": (error_entries / total_entries * 100) if total_entries > 0 else 0,
            "warning_rate": (warning_entries / total_entries * 100) if total_entries > 0 else 0,
            "reliability_score": max(0, 100 - (error_entries / total_entries * 100)) if total_entries > 0 else 100
        }

    async def stop_debugging(self):
        """Arrêter le système de débogage"""
        if not self.is_debugging_active:
            return

        logger.info("🛑 Arrêt du système de débogage intégré...")

        try:
            # Arrêter le debugging
            if self.debugger:
                await self.debugger.stop_debugging()

            # Désactiver l'intégration
            if self.agent_debug_integration:
                self.agent_debug_integration.disable_debugging()

            self.is_debugging_active = False
            logger.info("✅ Système de débogage intégré arrêté")

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'arrêt du debugging: {e}")

    def get_debug_config(self) -> dict[str, Any]:
        """Obtenir la configuration de debugging"""
        return self.debug_config.copy()

    def update_debug_config(self, new_config: dict[str, Any]):
        """Mettre à jour la configuration de debugging"""
        self.debug_config.update(new_config)
        logger.info("📝 Configuration de debugging mise à jour")

    def is_debugging_enabled(self) -> bool:
        """Vérifier si le debugging est activé"""
        return self.is_debugging_active

# Fonctions utilitaires

async def create_integrated_debug_system(agent_integration: AdvancedAgentIntegration) -> IntegratedDebugSystem:
    """Créer et initialiser le système de débogage intégré"""
    debug_system = IntegratedDebugSystem(agent_integration)
    await debug_system.initialize_debugging()
    return debug_system

def get_debug_system_status(debug_system: IntegratedDebugSystem) -> dict[str, Any]:
    """Obtenir le statut du système de débogage"""
    return {
        "is_active": debug_system.is_debugging_enabled(),
        "config": debug_system.get_debug_config(),
        "uptime": debug_system._calculate_uptime(),
        "last_updated": datetime.now().isoformat()
    }

async def generate_debug_report(debug_system: IntegratedDebugSystem) -> dict[str, Any]:
    """Générer un rapport de débogage complet"""
    return await debug_system.generate_comprehensive_debug_report()

# Export
__all__ = [
    'IntegratedDebugSystem',
    'create_integrated_debug_system',
    'get_debug_system_status',
    'generate_debug_report'
]
