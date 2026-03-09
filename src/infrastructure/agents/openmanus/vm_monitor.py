"""Système de surveillance pour VMs Sandbox.

Ce module fournit des capacités de monitoring en temps réel pour les machines
virtuelles sandbox, incluant les métriques de performance, la santé, et les alertes.
"""

import asyncio
import contextlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from loguru import logger
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Métriques Prometheus
VM_CREATION_COUNTER = Counter('vm_sandbox_creation_total', 'Total VM creations', ['provider', 'status'])
VM_DESTRUCTION_COUNTER = Counter('vm_sandbox_destruction_total', 'Total VM destructions', ['provider'])
VM_EXECUTION_DURATION = Histogram('vm_sandbox_execution_duration_seconds', 'VM execution duration', ['provider'])
VM_ACTIVE_GAUGE = Gauge('vm_sandbox_active_vms', 'Number of active VMs', ['provider'])
VM_CPU_USAGE = Gauge('vm_sandbox_cpu_usage_percent', 'VM CPU usage percentage', ['vm_id'])
VM_MEMORY_USAGE = Gauge('vm_sandbox_memory_usage_bytes', 'VM memory usage in bytes', ['vm_id'])
VM_DISK_USAGE = Gauge('vm_sandbox_disk_usage_bytes', 'VM disk usage in bytes', ['vm_id'])
VM_NETWORK_IO = Counter('vm_sandbox_network_io_bytes', 'VM network I/O in bytes', ['vm_id', 'direction'])


@dataclass
class VMMetrics:
    """Métriques d'une VM."""
    vm_id: str
    timestamp: datetime
    cpu_percent: float
    memory_used: int
    memory_total: int
    disk_used: int
    disk_total: int
    network_bytes_sent: int
    network_bytes_recv: int
    uptime_seconds: float
    status: str
    error_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convertit en dictionnaire."""
        return asdict(self)


@dataclass
class VMHealth:
    """État de santé d'une VM."""
    vm_id: str
    status: str  # healthy, warning, critical, unknown
    message: str
    last_check: datetime
    metrics: VMMetrics | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convertit en dictionnaire."""
        data = asdict(self)
        if self.metrics:
            data['metrics'] = self.metrics.to_dict()
        return data


class VMMonitor:
    """Moniteur pour VMs Sandbox."""

    def __init__(
        self,
        adapter: Any,
        check_interval: int = 30,
        metrics_retention_hours: int = 24,
        alerting_enabled: bool = True,
        prometheus_port: int | None = None
    ):
        """Initialise le moniteur.

        Args:
            adapter: Adaptateur VM Sandbox
            check_interval: Intervalle de vérification (secondes)
            metrics_retention_hours: Heures de rétention des métriques
            alerting_enabled: Activer les alertes
            prometheus_port: Port pour Prometheus (None = désactivé)
        """
        self.adapter = adapter
        self.check_interval = check_interval
        self.metrics_retention = timedelta(hours=metrics_retention_hours)
        self.alerting_enabled = alerting_enabled
        self.prometheus_port = prometheus_port

        # Stockage des métriques
        self.metrics_history: dict[str, list[VMMetrics]] = {}
        self.health_status: dict[str, VMHealth] = {}
        self.alert_handlers: list[Callable] = []

        # État du moniteur
        self.running = False
        self.monitor_task: asyncio.Task | None = None

        # Seuil d'alerte
        self.alert_thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_percent': 90.0,
            'uptime_hours': 24.0,
            'error_rate': 0.1  # 10% d'erreurs
        }

        logger.info(f"VM Monitor initialisé (interval={check_interval}s, prometheus={prometheus_port})")

    def add_alert_handler(self, handler: Callable) -> None:
        """Ajoute un gestionnaire d'alertes.

        Args:
            handler: Fonction à appeler pour les alertes
        """
        self.alert_handlers.append(handler)

    async def start(self) -> None:
        """Démarre le monitoring."""
        logger.info("Démarrage VM Monitor")

        self.running = True

        # Démarrer Prometheus si configuré
        if self.prometheus_port:
            start_http_server(self.prometheus_port)
            logger.info(f"Prometheus metrics server démarré sur port {self.prometheus_port}")

        # Démarrer la tâche de monitoring
        self.monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info("VM Monitor démarré")

    async def stop(self) -> None:
        """Arrête le monitoring."""
        logger.info("Arrêt VM Monitor")

        self.running = False

        if self.monitor_task:
            self.monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.monitor_task

        logger.info("VM Monitor arrêté")

    async def _monitor_loop(self) -> None:
        """Boucle principale de monitoring."""
        logger.info("Démarrage boucle monitoring")

        while self.running:
            try:
                # Obtenir la liste des VMs actives
                active_vms = list(self.adapter.active_vms.keys())

                # Mettre à jour les métriques Prometheus
                VM_ACTIVE_GAUGE.labels(provider=self.adapter.vm_provider).set(len(active_vms))

                # Monitorer chaque VM
                for vm_id in active_vms:
                    try:
                        await self._check_vm_health(vm_id)
                        await self._collect_vm_metrics(vm_id)
                    except Exception as e:
                        logger.error(f"Erreur monitoring VM {vm_id}: {e}")

                # Nettoyer les anciennes métriques
                self._cleanup_old_metrics()

                # Attendre le prochain cycle
                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans la boucle monitoring: {e}")
                await asyncio.sleep(self.check_interval)

        logger.info("Arrêt boucle monitoring")

    async def _check_vm_health(self, vm_id: str) -> VMHealth:
        """Vérifie la santé d'une VM.

        Args:
            vm_id: ID de la VM

        Returns:
            État de santé
        """
        try:
            # Obtenir le statut de la VM
            vm_status = await self.adapter.get_vm_status(vm_id)

            # Analyser l'état
            runtime_status = vm_status.get("runtime_status", {})
            container_status = runtime_status.get("status", "unknown")

            # Déterminer le statut de santé
            if container_status == "running":
                health_status = "healthy"
                message = "VM fonctionne normalement"
            elif container_status in ["paused", "restarting"]:
                health_status = "warning"
                message = f"VM en état {container_status}"
            elif container_status in ["exited", "dead"]:
                health_status = "critical"
                message = f"VM arrêtée ({container_status})"
            else:
                health_status = "unknown"
                message = f"Statut VM inconnu: {container_status}"

            # Créer l'objet santé
            health = VMHealth(
                vm_id=vm_id,
                status=health_status,
                message=message,
                last_check=datetime.now()
            )

            # Stocker l'état
            self.health_status[vm_id] = health

            # Vérifier les alertes
            if self.alerting_enabled:
                await self._check_alerts(vm_id, health)

            return health

        except Exception as e:
            logger.error(f"Erreur vérification santé VM {vm_id}: {e}")

            # Créer un état d'erreur
            health = VMHealth(
                vm_id=vm_id,
                status="critical",
                message=f"Erreur santé VM: {e}",
                last_check=datetime.now()
            )

            self.health_status[vm_id] = health
            return health

    async def _collect_vm_metrics(self, vm_id: str) -> VMMetrics:
        """Collecte les métriques d'une VM.

        Args:
            vm_id: ID de la VM

        Returns:
            Métriques de la VM
        """
        try:
            # Obtenir les statistiques du conteneur Docker
            if self.adapter.vm_provider == "docker":
                metrics = await self._collect_docker_metrics(vm_id)
            else:
                # Métriques génériques pour d'autres providers
                metrics = await self._collect_generic_metrics(vm_id)

            # Stocker dans l'historique
            if vm_id not in self.metrics_history:
                self.metrics_history[vm_id] = []

            self.metrics_history[vm_id].append(metrics)

            # Mettre à jour Prometheus
            self._update_prometheus_metrics(vm_id, metrics)

            return metrics

        except Exception as e:
            logger.error(f"Erreur collecte métriques VM {vm_id}: {e}")

            # Retourner des métriques d'erreur
            return VMMetrics(
                vm_id=vm_id,
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_used=0,
                memory_total=0,
                disk_used=0,
                disk_total=0,
                network_bytes_sent=0,
                network_bytes_recv=0,
                uptime_seconds=0.0,
                status="error",
                error_count=1
            )

    async def _collect_docker_metrics(self, vm_id: str) -> VMMetrics:
        """Collecte les métriques Docker.

        Args:
            vm_id: ID du conteneur

        Returns:
            Métriques Docker
        """
        import docker

        try:
            client = docker.from_env()
            container = client.containers.get(vm_id)

            # Obtenir les statistiques
            stats = container.stats(stream=False)

            # CPU
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]

            cpu_percent = 0.0
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * 100.0 * stats["cpu_stats"]["online_cpus"]

            # Mémoire
            memory_used = stats["memory_stats"]["usage"]
            memory_total = stats["memory_stats"]["limit"]

            # Disque (approximation)
            disk_used = memory_used  # Simplification
            disk_total = memory_total

            # Réseau
            network_stats = stats.get("networks", {})
            bytes_sent = sum(net["tx_bytes"] for net in network_stats.values())
            bytes_recv = sum(net["rx_bytes"] for net in network_stats.values())

            # Uptime
            created_at = datetime.fromisoformat(container.attrs["Created"].replace("Z", "+00:00"))
            uptime = (datetime.now(created_at.tzinfo) - created_at).total_seconds()

            return VMMetrics(
                vm_id=vm_id,
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_used=memory_used,
                memory_total=memory_total,
                disk_used=disk_used,
                disk_total=disk_total,
                network_bytes_sent=bytes_sent,
                network_bytes_recv=bytes_recv,
                uptime_seconds=uptime,
                status="running"
            )

        except Exception as e:
            logger.error(f"Erreur collecte métriques Docker {vm_id}: {e}")
            raise

    async def _collect_generic_metrics(self, vm_id: str) -> VMMetrics:
        """Collecte des métriques génériques.

        Args:
            vm_id: ID de la VM

        Returns:
            Métriques génériques
        """
        # Métriques par défaut si Docker n'est pas disponible
        vm_info = self.adapter.active_vms.get(vm_id, {})
        created_at = vm_info.get("created_at", datetime.now())
        uptime = (datetime.now() - created_at).total_seconds()

        return VMMetrics(
            vm_id=vm_id,
            timestamp=datetime.now(),
            cpu_percent=0.0,
            memory_used=0,
            memory_total=0,
            disk_used=0,
            disk_total=0,
            network_bytes_sent=0,
            network_bytes_recv=0,
            uptime_seconds=uptime,
            status="unknown"
        )

    def _update_prometheus_metrics(self, vm_id: str, metrics: VMMetrics) -> None:
        """Met à jour les métriques Prometheus.

        Args:
            vm_id: ID de la VM
            metrics: Métriques à mettre à jour
        """
        try:
            # CPU
            VM_CPU_USAGE.labels(vm_id=vm_id).set(metrics.cpu_percent)

            # Mémoire
            VM_MEMORY_USAGE.labels(vm_id=vm_id).set(metrics.memory_used)

            # Disque
            VM_DISK_USAGE.labels(vm_id=vm_id).set(metrics.disk_used)

            # Réseau
            VM_NETWORK_IO.labels(vm_id=vm_id, direction="sent").inc(metrics.network_bytes_sent)
            VM_NETWORK_IO.labels(vm_id=vm_id, direction="recv").inc(metrics.network_bytes_recv)

        except Exception as e:
            logger.warning(f"Erreur mise à jour métriques Prometheus {vm_id}: {e}")

    async def _check_alerts(self, vm_id: str, health: VMHealth) -> None:
        """Vérifie et déclenche les alertes.

        Args:
            vm_id: ID de la VM
            health: État de santé
        """
        try:
            # Obtenir les métriques récentes
            recent_metrics = self.metrics_history.get(vm_id, [])[-10:]  # 10 dernières

            if not recent_metrics:
                return

            # Calculer les moyennes
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory_percent = sum((m.memory_used / m.memory_total * 100) if m.memory_total > 0 else 0
                                   for m in recent_metrics) / len(recent_metrics)

            # Vérifier les seuils
            alerts = []

            if avg_cpu > self.alert_thresholds['cpu_percent']:
                alerts.append({
                    'type': 'high_cpu',
                    'severity': 'warning',
                    'message': f"CPU usage élevé: {avg_cpu:.1f}%"
                })

            if avg_memory_percent > self.alert_thresholds['memory_percent']:
                alerts.append({
                    'type': 'high_memory',
                    'severity': 'warning',
                    'message': f"Memory usage élevé: {avg_memory_percent:.1f}%"
                })

            if health.status == "critical":
                alerts.append({
                    'type': 'vm_down',
                    'severity': 'critical',
                    'message': f"VM en état critique: {health.message}"
                })

            # Déclencher les alertes
            for alert in alerts:
                await self._trigger_alert(vm_id, alert)

        except Exception as e:
            logger.error(f"Erreur vérification alertes VM {vm_id}: {e}")

    async def _trigger_alert(self, vm_id: str, alert: dict[str, Any]) -> None:
        """Déclenche une alerte.

        Args:
            vm_id: ID de la VM
            alert: Information d'alerte
        """
        try:
            alert_data = {
                'vm_id': vm_id,
                'timestamp': datetime.now().isoformat(),
                'type': alert['type'],
                'severity': alert['severity'],
                'message': alert['message']
            }

            logger.warning(f"Alerte VM {vm_id}: {alert['message']}")

            # Appeler les gestionnaires d'alerte
            for handler in self.alert_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(alert_data)
                    else:
                        handler(alert_data)
                except Exception as e:
                    logger.error(f"Erreur gestionnaire alerte: {e}")

        except Exception as e:
            logger.error(f"Erreur déclenchement alerte VM {vm_id}: {e}")

    def _cleanup_old_metrics(self) -> None:
        """Nettoie les anciennes métriques."""
        try:
            current_time = datetime.now()
            cutoff_time = current_time - self.metrics_retention

            for vm_id, metrics_list in self.metrics_history.items():
                # Filtrer les métriques récentes
                self.metrics_history[vm_id] = [
                    m for m in metrics_list
                    if m.timestamp > cutoff_time
                ]

        except Exception as e:
            logger.error(f"Erreur nettoyage anciennes métriques: {e}")

    def get_health_summary(self) -> dict[str, Any]:
        """Obtient un résumé de la santé de toutes les VMs.

        Returns:
            Résumé de santé
        """
        try:
            health_summary = {
                'total_vms': len(self.health_status),
                'healthy_vms': 0,
                'warning_vms': 0,
                'critical_vms': 0,
                'unknown_vms': 0,
                'vms': {}
            }

            for vm_id, health in self.health_status.items():
                health_summary['vms'][vm_id] = health.to_dict()

                if health.status == 'healthy':
                    health_summary['healthy_vms'] += 1
                elif health.status == 'warning':
                    health_summary['warning_vms'] += 1
                elif health.status == 'critical':
                    health_summary['critical_vms'] += 1
                else:
                    health_summary['unknown_vms'] += 1

            return health_summary

        except Exception as e:
            logger.error(f"Erreur obtention résumé santé: {e}")
            return {'error': str(e)}

    def get_metrics_summary(self, vm_id: str | None = None) -> dict[str, Any]:
        """Obtient un résumé des métriques.

        Args:
            vm_id: ID VM spécifique (None = toutes)

        Returns:
            Résumé des métriques
        """
        try:
            if vm_id:
                # Métriques pour une VM spécifique
                metrics_list = self.metrics_history.get(vm_id, [])

                if not metrics_list:
                    return {'vm_id': vm_id, 'error': 'Aucune métrique disponible'}

                # Calculer les statistiques
                cpu_values = [m.cpu_percent for m in metrics_list]
                memory_values = [(m.memory_used / m.memory_total * 100) if m.memory_total > 0 else 0
                               for m in metrics_list]

                return {
                    'vm_id': vm_id,
                    'metrics_count': len(metrics_list),
                    'time_range': {
                        'start': metrics_list[0].timestamp.isoformat(),
                        'end': metrics_list[-1].timestamp.isoformat()
                    },
                    'cpu_stats': {
                        'avg': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                        'min': min(cpu_values) if cpu_values else 0,
                        'max': max(cpu_values) if cpu_values else 0
                    },
                    'memory_stats': {
                        'avg': sum(memory_values) / len(memory_values) if memory_values else 0,
                        'min': min(memory_values) if memory_values else 0,
                        'max': max(memory_values) if memory_values else 0
                    }
                }

            else:
                # Résumé global
                all_metrics = []
                for vm_metrics in self.metrics_history.values():
                    all_metrics.extend(vm_metrics)

                return {
                    'total_metrics': len(all_metrics),
                    'monitored_vms': len(self.metrics_history),
                    'vms_with_metrics': list(self.metrics_history.keys())
                }

        except Exception as e:
            logger.error(f"Erreur obtention résumé métriques: {e}")
            return {'error': str(e)}


# Fonctions utilitaires d'alerte
async def log_alert_handler(alert_data: dict[str, Any]) -> None:
    """Gestionnaire d'alerte simple qui loggue.

    Args:
        alert_data: Données d'alerte
    """
    severity = alert_data['severity']
    message = alert_data['message']
    vm_id = alert_data['vm_id']

    if severity == 'critical':
        logger.critical(f"Alerte VM {vm_id}: {message}")
    elif severity == 'warning':
        logger.warning(f"Alerte VM {vm_id}: {message}")
    else:
        logger.info(f"Alerte VM {vm_id}: {message}")


async def webhook_alert_handler(webhook_url: str) -> Callable:
    """Crée un gestionnaire d'alerte webhook.

    Args:
        webhook_url: URL du webhook

    Returns:
        Fonction gestionnaire
    """
    async def handler(alert_data: dict[str, Any]) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=alert_data) as response:
                    if response.status >= 400:
                        logger.error(f"Erreur envoi webhook alerte: {response.status}")
        except Exception as e:
            logger.error(f"Erreur gestionnaire webhook alerte: {e}")

    return handler


# Exemple d'utilisation
if __name__ == "__main__":
    import asyncio

    async def test_monitor():
        """Test le moniteur VM."""
        # Créer un adaptateur factice
        from unittest.mock import Mock

        mock_adapter = Mock()
        mock_adapter.active_vms = {
            "test-vm-1": {"created_at": datetime.now(), "status": "running"}
        }
        mock_adapter.vm_provider = "docker"

        # Créer le moniteur
        monitor = VMMonitor(
            adapter=mock_adapter,
            check_interval=5,
            prometheus_port=None
        )

        # Ajouter un gestionnaire d'alerte
        monitor.add_alert_handler(log_alert_handler)

        # Démarrer le monitoring
        await monitor.start()

        # Attendre un peu
        await asyncio.sleep(15)

        # Obtenir les résumés
        health_summary = monitor.get_health_summary()
        metrics_summary = monitor.get_metrics_summary()

        print("Health Summary:", json.dumps(health_summary, indent=2))
        print("Metrics Summary:", json.dumps(metrics_summary, indent=2))

        # Arrêter
        await monitor.stop()

    asyncio.run(test_monitor())
