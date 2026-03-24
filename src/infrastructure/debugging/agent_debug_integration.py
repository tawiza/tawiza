#!/usr/bin/env python3
"""
Intégration du débogage dans le système multi-agents Tawiza-V2
Debugging hooks et instrumentation pour tous les agents
"""

import asyncio
import functools
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypeVar

from loguru import logger

# Configuration du logging
# Import des composants de débogage
from src.infrastructure.debugging.advanced_debugger import (
    AdvancedDebugger,
    create_advanced_debugger,
)

# Types génériques
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class AgentDebugIntegration:
    """Intégration du débogage pour les agents"""

    def __init__(self, debugger: AdvancedDebugger | None = None):
        self.debugger = debugger or create_advanced_debugger()
        self.is_enabled = True
        self.trace_points: dict[str, list[str]] = {}
        self.performance_metrics: dict[str, list[float]] = {}
        self.error_patterns: dict[str, int] = {}

    def enable_debugging(self):
        """Activer le debugging"""
        self.is_enabled = True
        logger.info("🐛 Debugging des agents activé")

    def disable_debugging(self):
        """Désactiver le debugging"""
        self.is_enabled = False
        logger.info("🐛 Debugging des agents désactivé")

    def debug_agent_method(self, agent_type: str, method_name: str):
        """Décorateur pour debugger les méthodes d'agents"""

        def decorator(func: F) -> F:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not self.is_enabled:
                    return await func(*args, **kwargs)

                agent_id = self._extract_agent_id(args, kwargs)
                start_time = time.time()

                try:
                    # Log l'entrée dans la méthode
                    self.debugger.log_agent_activity(
                        agent_id or "unknown",
                        agent_type,
                        f"method_start.{method_name}",
                        method=method_name,
                        args_count=len(args),
                        kwargs_count=len(kwargs),
                    )

                    # Démarrer le traçage
                    trace_id = f"{agent_id}_{method_name}_{int(start_time * 1000)}"
                    self.debugger.agent_tracer.start_trace(agent_id or "unknown", trace_id)

                    # Exécuter la méthode
                    result = await func(*args, **kwargs)

                    # Calculer le temps d'exécution
                    execution_time = time.time() - start_time

                    # Log la sortie de la méthode
                    self.debugger.log_agent_activity(
                        agent_id or "unknown",
                        agent_type,
                        f"method_complete.{method_name}",
                        execution_time=execution_time,
                        success=True,
                    )

                    # Terminer le traçage
                    self.debugger.agent_tracer.end_trace(
                        trace_id, True, {"execution_time": execution_time}
                    )

                    # Enregistrer la métrique de performance
                    self._record_performance_metric(f"{agent_type}.{method_name}", execution_time)

                    return result

                except Exception as e:
                    # Calculer le temps jusqu'à l'erreur
                    execution_time = time.time() - start_time

                    # Log l'erreur
                    self.debugger.log_error(
                        f"agent.{agent_type}.{method_name}",
                        e,
                        {
                            "agent_id": agent_id,
                            "execution_time": execution_time,
                            "args": str(args),
                            "kwargs": str(kwargs),
                        },
                    )

                    # Log l'activité de l'agent
                    self.debugger.log_agent_activity(
                        agent_id or "unknown",
                        agent_type,
                        f"method_error.{method_name}",
                        error=str(e),
                        execution_time=execution_time,
                        success=False,
                    )

                    # Terminer le traçage avec erreur
                    self.debugger.agent_tracer.end_trace(trace_id, False, {"error": str(e)})

                    # Analyser le pattern d'erreur
                    self._analyze_error_pattern(agent_type, method_name, str(e))

                    # Re-raise l'exception
                    raise

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                if not self.is_enabled:
                    return func(*args, **kwargs)

                agent_id = self._extract_agent_id(args, kwargs)
                start_time = time.time()

                try:
                    # Log l'entrée dans la méthode
                    self.debugger.log_agent_activity(
                        agent_id or "unknown",
                        agent_type,
                        f"method_start.{method_name}",
                        method=method_name,
                        args_count=len(args),
                        kwargs_count=len(kwargs),
                    )

                    # Exécuter la méthode
                    result = func(*args, **kwargs)

                    # Calculer le temps d'exécution
                    execution_time = time.time() - start_time

                    # Log la sortie de la méthode
                    self.debugger.log_agent_activity(
                        agent_id or "unknown",
                        agent_type,
                        f"method_complete.{method_name}",
                        execution_time=execution_time,
                        success=True,
                    )

                    # Enregistrer la métrique de performance
                    self._record_performance_metric(f"{agent_type}.{method_name}", execution_time)

                    return result

                except Exception as e:
                    # Calculer le temps jusqu'à l'erreur
                    execution_time = time.time() - start_time

                    # Log l'erreur
                    self.debugger.log_error(
                        f"agent.{agent_type}.{method_name}",
                        e,
                        {
                            "agent_id": agent_id,
                            "execution_time": execution_time,
                            "args": str(args),
                            "kwargs": str(kwargs),
                        },
                    )

                    # Log l'activité de l'agent
                    self.debugger.log_agent_activity(
                        agent_id or "unknown",
                        agent_type,
                        f"method_error.{method_name}",
                        error=str(e),
                        execution_time=execution_time,
                        success=False,
                    )

                    # Analyser le pattern d'erreur
                    self._analyze_error_pattern(agent_type, method_name, str(e))

                    # Re-raise l'exception
                    raise

            # Retourner le wrapper approprié
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper

        return decorator

    def debug_agent_task(self, agent_type: str):
        """Décorateur pour debugger le traitement des tâches"""

        def decorator(func: F) -> F:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not self.is_enabled:
                    return await func(*args, **kwargs)

                task_id = kwargs.get("task_id") or self._extract_task_id(args, kwargs)
                agent_id = self._extract_agent_id(args, kwargs)
                start_time = time.time()

                try:
                    # Log le début du traitement
                    self.debugger.log_agent_activity(
                        agent_id or "unknown",
                        agent_type,
                        "task_processing_start",
                        task_id=task_id,
                        timestamp=datetime.now().isoformat(),
                    )

                    # Traçage détaillé
                    trace_id = f"task_{task_id}_{int(start_time * 1000)}"
                    self.debugger.agent_tracer.start_trace(agent_id or "unknown", trace_id)

                    # Exécuter la tâche
                    result = await func(*args, **kwargs)

                    # Calculer le temps de traitement
                    processing_time = time.time() - start_time

                    # Log la fin du traitement
                    self.debugger.log_agent_activity(
                        agent_id or "unknown",
                        agent_type,
                        "task_processing_complete",
                        task_id=task_id,
                        processing_time=processing_time,
                        success=True,
                    )

                    # Terminer le traçage
                    self.debugger.agent_tracer.end_trace(
                        trace_id,
                        True,
                        {"processing_time": processing_time, "result_type": type(result).__name__},
                    )

                    # Enregistrer la métrique
                    self._record_performance_metric(
                        f"{agent_type}.task_processing", processing_time
                    )

                    return result

                except Exception as e:
                    # Calculer le temps jusqu'à l'erreur
                    processing_time = time.time() - start_time

                    # Log l'erreur
                    self.debugger.log_error(
                        f"agent.{agent_type}.task_processing",
                        e,
                        {
                            "task_id": task_id,
                            "agent_id": agent_id,
                            "processing_time": processing_time,
                        },
                    )

                    # Log l'échec du traitement
                    self.debugger.log_agent_activity(
                        agent_id or "unknown",
                        agent_type,
                        "task_processing_error",
                        task_id=task_id,
                        processing_time=processing_time,
                        error=str(e),
                        success=False,
                    )

                    # Terminer le traçage avec erreur
                    self.debugger.agent_tracer.end_trace(
                        trace_id, False, {"processing_time": processing_time, "error": str(e)}
                    )

                    raise

            return async_wrapper

        return decorator

    def monitor_agent_lifecycle(self, agent_type: str, agent_id: str):
        """Monitorer le cycle de vie complet d'un agent"""
        if not self.is_enabled:
            return

        # Log l'état de l'agent
        self.debugger.log_agent_activity(
            agent_id,
            agent_type,
            "lifecycle_monitoring",
            status="active",
            memory_usage=self.debugger._get_current_memory_usage(),
            cpu_usage=self.debugger._get_current_cpu_usage(),
        )

    def track_agent_performance(
        self, agent_type: str, agent_id: str, metric_name: str, value: float
    ):
        """Tracker une métrique de performance spécifique"""
        if not self.is_enabled:
            return

        metric_key = f"{agent_type}.{agent_id}.{metric_name}"

        if metric_key not in self.performance_metrics:
            self.performance_metrics[metric_key] = []

        self.performance_metrics[metric_key].append(value)

        # Log si la métrique est anormale
        if len(self.performance_metrics[metric_key]) > 5:
            recent_values = self.performance_metrics[metric_key][-5:]
            avg_value = sum(recent_values) / len(recent_values)

            # Détecter les anomalies (simple règle: > 2x la moyenne)
            if value > avg_value * 2:
                self.debugger.log_debug(
                    f"agent.{agent_type}.performance",
                    f"Métrique anormale détectée: {metric_name}",
                    level="WARNING",
                    agent_id=agent_id,
                    metric_name=metric_name,
                    value=value,
                    average=avg_value,
                    deviation=(value - avg_value) / avg_value * 100,
                )

    def detect_agent_anomalies(
        self, agent_type: str, agent_id: str, current_metrics: dict[str, Any]
    ) -> list[str]:
        """Détecter des anomalies dans le comportement de l'agent"""
        anomalies = []

        if not self.is_enabled:
            return anomalies

        # Vérifier l'utilisation mémoire
        memory_usage = current_metrics.get("memory_usage_mb", 0)
        if memory_usage > 1000:  # 1GB
            anomalies.append(f"Utilisation mémoire élevée: {memory_usage:.0f}MB")

        # Vérifier le temps de réponse
        response_time = current_metrics.get("response_time_ms", 0)
        if response_time > 5000:  # 5 secondes
            anomalies.append(f"Temps de réponse élevé: {response_time:.0f}ms")

        # Vérifier le taux d'erreur
        error_rate = current_metrics.get("error_rate", 0)
        if error_rate > 10:  # 10%
            anomalies.append(f"Taux d'erreur élevé: {error_rate:.1f}%")

        # Log les anomalies détectées
        if anomalies:
            self.debugger.log_debug(
                f"agent.{agent_type}.anomaly_detection",
                f"Anomalies détectées pour l'agent {agent_id}",
                level="WARNING",
                agent_id=agent_id,
                anomalies=anomalies,
                current_metrics=current_metrics,
            )

        return anomalies

    def _extract_agent_id(self, args: tuple, kwargs: dict) -> str | None:
        """Extraire l'ID de l'agent des arguments"""
        # Chercher dans les arguments positionnels
        for arg in args:
            if hasattr(arg, "agent_id"):
                return arg.agent_id
            if hasattr(arg, "id"):
                return arg.id

        # Chercher dans les arguments nommés
        if "agent_id" in kwargs:
            return kwargs["agent_id"]
        if "id" in kwargs:
            return kwargs["id"]

        # Chercher dans self si c'est une méthode
        if args and hasattr(args[0], "agent_id"):
            return args[0].agent_id
        if args and hasattr(args[0], "id"):
            return args[0].id

        return None

    def _extract_task_id(self, args: tuple, kwargs: dict) -> str | None:
        """Extraire l'ID de la tâche des arguments"""
        # Chercher dans les arguments nommés
        if "task_id" in kwargs:
            return kwargs["task_id"]
        if "task" in kwargs and hasattr(kwargs["task"], "task_id"):
            return kwargs["task"].task_id

        # Chercher dans les arguments positionnels
        for arg in args:
            if hasattr(arg, "task_id"):
                return arg.task_id
            if hasattr(arg, "id"):
                return arg.id

        return None

    def _record_performance_metric(self, metric_name: str, value: float):
        """Enregistrer une métrique de performance"""
        if metric_name not in self.performance_metrics:
            self.performance_metrics[metric_name] = []

        self.performance_metrics[metric_name].append(value)

        # Limiter l'historique
        if len(self.performance_metrics[metric_name]) > 1000:
            self.performance_metrics[metric_name] = self.performance_metrics[metric_name][-500:]

    def _analyze_error_pattern(self, agent_type: str, method_name: str, error_message: str):
        """Analyser le pattern d'erreur"""
        error_key = f"{agent_type}.{method_name}.{error_message[:100]}"  # Clé tronquée

        if error_key not in self.error_patterns:
            self.error_patterns[error_key] = 0

        self.error_patterns[error_key] += 1

        # Alerte si le même pattern d'erreur se répète
        if self.error_patterns[error_key] > 5:
            self.debugger.log_debug(
                f"agent.{agent_type}.error_pattern",
                "Pattern d'erreur récurrent détecté",
                level="ERROR",
                agent_type=agent_type,
                method_name=method_name,
                error_count=self.error_patterns[error_key],
                error_message=error_message,
            )

    def get_debug_summary(self, agent_type: str | None = None) -> dict[str, Any]:
        """Obtenir un résumé du debugging"""
        summary = {
            "is_enabled": self.is_enabled,
            "total_trace_points": len(self.trace_points),
            "performance_metrics_count": len(self.performance_metrics),
            "error_patterns_count": len(self.error_patterns),
            "agents_monitored": list(self.trace_points.keys())
            if agent_type is None
            else [agent_type],
        }

        if agent_type:
            # Statistiques spécifiques à l'agent
            agent_metrics = {
                k: v for k, v in self.performance_metrics.items() if k.startswith(f"{agent_type}.")
            }
            agent_errors = {
                k: v for k, v in self.error_patterns.items() if k.startswith(f"{agent_type}.")
            }

            summary.update(
                {
                    "performance_metrics": len(agent_metrics),
                    "error_patterns": len(agent_errors),
                    "avg_response_time": self._calculate_avg_response_time(agent_type),
                }
            )

        return summary

    def _calculate_avg_response_time(self, agent_type: str) -> float:
        """Calculer le temps de réponse moyen pour un type d'agent"""
        response_times = []

        for metric_name, values in self.performance_metrics.items():
            if metric_name.startswith(f"{agent_type}.") and "response" in metric_name:
                response_times.extend(values)

        return sum(response_times) / len(response_times) if response_times else 0.0


# Décorateurs de debugging prêts à l'emploi


def debug_data_analyst():
    """Décorateur pour debugger le DataAnalystAgent"""
    debug_integration = AgentDebugIntegration()
    return debug_integration.debug_agent_method("data_analyst", "analyze_dataset")


def debug_ml_engineer():
    """Décorateur pour debugger le MLEngineerAgent"""
    debug_integration = AgentDebugIntegration()
    return debug_integration.debug_agent_method("ml_engineer", "create_ml_pipeline")


def debug_browser_automation():
    """Décorateur pour debugger le BrowserAutomationAgent"""
    debug_integration = AgentDebugIntegration()
    return debug_integration.debug_agent_method("browser_automation", "execute_task")


def debug_code_generator():
    """Décorateur pour debugger le CodeGeneratorAgent"""
    debug_integration = AgentDebugIntegration()
    return debug_integration.debug_agent_method("code_generator", "generate_code")


def debug_gpu_optimizer():
    """Décorateur pour debugger le GPUOptimizer"""
    debug_integration = AgentDebugIntegration()
    return debug_integration.debug_agent_method("gpu_optimizer", "optimize_inference_performance")


# Fonctions utilitaires pour le debugging


def create_debug_wrapper(
    agent_instance: Any, debugger: AdvancedDebugger | None = None
) -> AgentDebugIntegration:
    """Créer un wrapper de debugging pour une instance d'agent"""
    debug_integration = AgentDebugIntegration(debugger)

    # Wrapper les méthodes principales
    if hasattr(agent_instance, "process_request"):
        original_method = agent_instance.process_request

        @debug_integration.debug_agent_method(agent_instance.agent_type, "process_request")
        async def wrapped_process_request(request):
            return await original_method(request)

        agent_instance.process_request = wrapped_process_request

    return debug_integration


def enable_comprehensive_debugging(
    debugger: AdvancedDebugger | None = None,
) -> AgentDebugIntegration:
    """Activer le debugging complet pour tous les agents"""
    debug_integration = AgentDebugIntegration(debugger)
    debug_integration.enable_debugging()

    logger.info("🐛 Debugging complet activé pour tous les agents")
    return debug_integration


def get_debug_insights(agent_type: str, debug_integration: AgentDebugIntegration) -> dict[str, Any]:
    """Obtenir des insights de debugging pour un type d'agent"""
    insights = debug_integration.get_debug_summary(agent_type)

    # Ajouter des insights supplémentaires
    insights.update(
        {
            "debug_level": "comprehensive",
            "monitoring_active": True,
            "last_updated": datetime.now().isoformat(),
            "recommendations": generate_debug_recommendations(insights),
        }
    )

    return insights


def generate_debug_recommendations(debug_summary: dict[str, Any]) -> list[str]:
    """Générer des recommandations basées sur le résumé de debugging"""
    recommendations = []

    # Recommandations basées sur les métriques
    avg_response_time = debug_summary.get("avg_response_time", 0)
    if avg_response_time > 5.0:  # 5 secondes
        recommendations.append(
            "Temps de réponse élevé - optimisez les algorithmes ou augmentez les ressources"
        )

    error_patterns = debug_summary.get("error_patterns", 0)
    if error_patterns > 10:
        recommendations.append(
            "Nombre élevé de patterns d'erreur - analysez les logs pour identifier les problèmes récurrents"
        )

    performance_metrics = debug_summary.get("performance_metrics", 0)
    if performance_metrics > 100:
        recommendations.append(
            "Beaucoup de métriques de performance - envisagez une agrégation ou un résumé"
        )

    if not recommendations:
        recommendations.append("Aucun problème détecté - le debugging fonctionne correctement")

    return recommendations


# Export
__all__ = [
    "AgentDebugIntegration",
    "debug_data_analyst",
    "debug_ml_engineer",
    "debug_browser_automation",
    "debug_code_generator",
    "debug_gpu_optimizer",
    "create_debug_wrapper",
    "enable_comprehensive_debugging",
    "get_debug_insights",
    "generate_debug_recommendations",
]
