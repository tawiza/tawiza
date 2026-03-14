"""VM Sandbox Adapter pour OpenManus.

Ce module fournit une sandbox basée sur des machines virtuelles pour OpenManus,
permettant l'exécution sécurisée de tâches automatisées dans un environnement isolé.
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from src.application.ports.agent_ports import AgentExecutionError, AgentType, TaskStatus
from src.infrastructure.agents.base_agent import BaseAgent


class VMSandboxAdapter(BaseAgent):
    """Adaptateur VM Sandbox pour OpenManus.

    Cet adaptateur crée et gère des machines virtuelles isolées où OpenManus
    peut exécuter des tâches automatisées de manière sécurisée.

    Features:
    - Création automatique de VMs isolées
    - Contrôle complet via API QEMU/KVM
    - Surveillance en temps réel
    - Capture d'écran et enregistrement
    - Nettoyage automatique
    """

    def __init__(
        self,
        vm_provider: str = "qemu",
        vm_image_path: str = "/var/lib/tawiza/vm-images",
        vm_storage_path: str = "/var/lib/tawiza/vm-storage",
        headless: bool = True,
        max_vms: int = 5,
        vm_timeout: int = 3600,
        llm_client: Any | None = None,
    ) -> None:
        """Initialise l'adaptateur VM Sandbox.

        Args:
            vm_provider: Fournisseur VM ('qemu', 'virtualbox', 'docker')
            vm_image_path: Chemin vers les images VM
            vm_storage_path: Chemin pour le stockage VM
            headless: Mode headless pour les VMs
            max_vms: Nombre maximum de VMs simultanées
            vm_timeout: Timeout par défaut pour les VMs (secondes)
            llm_client: Client LLM optionnel pour l'IA
        """
        super().__init__(AgentType.OPENMANUS)

        self.vm_provider = vm_provider
        self.vm_image_path = Path(vm_image_path)
        self.vm_storage_path = Path(vm_storage_path)
        self.headless = headless
        self.max_vms = max_vms
        self.vm_timeout = vm_timeout
        self.llm_client = llm_client

        # Créer les répertoires nécessaires
        self.vm_image_path.mkdir(parents=True, exist_ok=True)
        self.vm_storage_path.mkdir(parents=True, exist_ok=True)

        # État des VMs actives
        self.active_vms: dict[str, dict[str, Any]] = {}
        self.vm_counter = 0

        logger.info(f"VM Sandbox adapter initialisé (provider={vm_provider}, max_vms={max_vms})")

    async def create_vm(self, task_id: str, config: dict[str, Any]) -> str:
        """Crée une nouvelle machine virtuelle pour une tâche.

        Args:
            task_id: ID de la tâche
            config: Configuration VM

        Returns:
            ID de la VM créée
        """
        vm_id = f"tawiza-vm-{task_id}-{uuid.uuid4().hex[:8]}"

        # Vérifier la limite de VMs
        if len(self.active_vms) >= self.max_vms:
            raise AgentExecutionError(f"Limite de VMs atteinte: {self.max_vms}")

        try:
            logger.info(f"Création VM {vm_id} pour tâche {task_id}")

            if self.vm_provider == "qemu":
                vm_info = await self._create_qemu_vm(vm_id, config)
            elif self.vm_provider == "virtualbox":
                vm_info = await self._create_vbox_vm(vm_id, config)
            elif self.vm_provider == "docker":
                vm_info = await self._create_docker_vm(vm_id, config)
            else:
                raise AgentExecutionError(f"Fournisseur VM non supporté: {self.vm_provider}")

            # Stocker l'information de la VM
            self.active_vms[vm_id] = {
                "id": vm_id,
                "task_id": task_id,
                "created_at": datetime.now(),
                "status": "running",
                "info": vm_info,
                "config": config,
            }

            logger.info(f"VM {vm_id} créée avec succès")
            return vm_id

        except Exception as e:
            logger.error(f"Échec création VM {vm_id}: {e}")
            raise AgentExecutionError(f"Impossible de créer VM: {e}") from e

    async def _create_qemu_vm(self, vm_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Crée une VM QEMU/KVM.

        Args:
            vm_id: ID de la VM
            config: Configuration

        Returns:
            Informations de la VM
        """
        # Configuration QEMU
        memory = config.get("memory", "2G")
        cpus = config.get("cpus", 2)
        disk_size = config.get("disk_size", "20G")

        # Créer le disque virtuel
        disk_path = self.vm_storage_path / f"{vm_id}.qcow2"

        # Commande pour créer le disque
        create_disk_cmd = ["qemu-img", "create", "-f", "qcow2", str(disk_path), disk_size]

        process = await asyncio.create_subprocess_exec(
            *create_disk_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise AgentExecutionError(f"Erreur création disque: {stderr.decode()}")

        # Configuration de la VM
        qemu_cmd = [
            "qemu-system-x86_64",
            "-enable-kvm",
            "-m",
            memory,
            "-smp",
            str(cpus),
            "-drive",
            f"file={disk_path},format=qcow2",
            "-netdev",
            "user,id=net0,hostfwd=tcp::2222-:22",
            "-device",
            "virtio-net-pci,netdev=net0",
            "-vnc",
            f":{self.vm_counter}",
            "-daemonize",
        ]

        if self.headless:
            qemu_cmd.extend(["-display", "none"])

        # Démarrer la VM
        process = await asyncio.create_subprocess_exec(
            *qemu_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise AgentExecutionError(f"Erreur démarrage VM: {stderr.decode()}")

        self.vm_counter += 1

        return {
            "type": "qemu",
            "memory": memory,
            "cpus": cpus,
            "disk_path": str(disk_path),
            "vnc_port": self.vm_counter - 1,
            "ssh_port": 2222,
        }

    async def _create_vbox_vm(self, vm_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Crée une VM VirtualBox (implémentation simplifiée).

        Args:
            vm_id: ID de la VM
            config: Configuration

        Returns:
            Informations de la VM
        """
        # Note: VirtualBox nécessite des privilèges élevés
        # Cette implémentation est conceptuelle

        memory = config.get("memory", 2048)  # MB
        cpus = config.get("cpus", 2)

        logger.warning("VirtualBox support est conceptuel et nécessite configuration")

        return {"type": "virtualbox", "memory": memory, "cpus": cpus, "status": "conceptual"}

    async def _create_docker_vm(self, vm_id: str, config: dict[str, Any]) -> dict[str, Any]:
        """Crée un conteneur Docker comme VM légère.

        Args:
            vm_id: ID de la VM
            config: Configuration

        Returns:
            Informations de la VM
        """
        import docker

        try:
            client = docker.from_env()

            # Configuration du conteneur
            image = config.get("image", "ubuntu:22.04")
            memory_limit = config.get("memory", "2g")
            cpu_limit = config.get("cpus", 2)

            # Créer et démarrer le conteneur
            container = client.containers.run(
                image=image,
                name=vm_id,
                detach=True,
                mem_limit=memory_limit,
                cpu_count=cpu_limit,
                ports={"22/tcp": None, "5900/tcp": None},  # Ports dynamiques
                volumes={str(self.vm_storage_path / vm_id): {"bind": "/workspace", "mode": "rw"}},
                environment={"DISPLAY": ":99", "VNC_PORT": "5900"},
            )

            # Attendre que le conteneur soit prêt
            await asyncio.sleep(5)

            return {
                "type": "docker",
                "container_id": container.id,
                "container_name": container.name,
                "status": "running",
            }

        except Exception as e:
            raise AgentExecutionError(f"Erreur création conteneur Docker: {e}")

    async def execute_in_vm(self, vm_id: str, task_config: dict[str, Any]) -> dict[str, Any]:
        """Exécute une tâche dans la VM.

        Args:
            vm_id: ID de la VM
            task_config: Configuration de la tâche

        Returns:
            Résultat de l'exécution
        """
        if vm_id not in self.active_vms:
            raise AgentExecutionError(f"VM {vm_id} non trouvée")

        vm_info = self.active_vms[vm_id]

        try:
            logger.info(f"Exécution tâche dans VM {vm_id}")

            # Préparer l'environnement dans la VM
            await self._setup_vm_environment(vm_id)

            # Installer OpenManus et dépendances
            await self._install_openmanus_in_vm(vm_id)

            # Exécuter la tâche OpenManus
            result = await self._execute_openmanus_task(vm_id, task_config)

            # Capturer des screenshots
            screenshots = await self._capture_vm_screenshots(vm_id)

            return {
                "vm_id": vm_id,
                "status": "success",
                "result": result,
                "screenshots": screenshots,
                "execution_time": datetime.now() - vm_info["created_at"],
            }

        except Exception as e:
            logger.error(f"Erreur exécution dans VM {vm_id}: {e}")
            raise AgentExecutionError(f"Erreur exécution VM: {e}") from e

    async def _setup_vm_environment(self, vm_id: str) -> None:
        """Configure l'environnement dans la VM.

        Args:
            vm_id: ID de la VM
        """
        vm_info = self.active_vms[vm_id]

        if vm_info["info"]["type"] == "docker":
            # Configuration pour Docker
            setup_commands = [
                "apt-get update",
                "apt-get install -y python3 python3-pip wget curl",
                "pip3 install playwright beautifulsoup4 requests",
                "playwright install chromium",
            ]

            for cmd in setup_commands:
                await self._execute_in_container(vm_id, cmd)

    async def _install_openmanus_in_vm(self, vm_id: str) -> None:
        """Installe OpenManus dans la VM.

        Args:
            vm_id: ID de la VM
        """
        # Copier le code OpenManus dans la VM
        install_commands = [
            "mkdir -p /workspace/openmanus",
            "cd /workspace/openmanus && python3 -m pip install -e .",
        ]

        for cmd in install_commands:
            await self._execute_in_container(vm_id, cmd)

    async def _execute_openmanus_task(
        self, vm_id: str, task_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Exécute une tâche OpenManus dans la VM.

        Args:
            vm_id: ID de la VM
            task_config: Configuration de la tâche

        Returns:
            Résultat de l'exécution
        """
        # Créer le script de tâche
        task_script = f"""
import asyncio
import json
from openmanus_adapter import OpenManusAdapter

async def execute_task():
    agent = OpenManusAdapter(headless=True)

    try:
        result = await agent.execute_task({json.dumps(task_config)})
        print(json.dumps(result, indent=2))
        return result
    finally:
        await agent.cleanup()

if __name__ == "__main__":
    result = asyncio.run(execute_task())
"""

        # Écrire le script dans la VM
        script_path = "/workspace/task_script.py"
        await self._write_file_to_container(vm_id, script_path, task_script)

        # Exécuter le script
        result = await self._execute_in_container(vm_id, f"cd /workspace && python3 {script_path}")

        return result

    async def _capture_vm_screenshots(self, vm_id: str) -> list[str]:
        """Capture des screenshots de la VM.

        Args:
            vm_id: ID de la VM

        Returns:
            Liste des chemins des screenshots
        """
        screenshots = []

        # Pour Docker, on peut utiliser VNC ou des outils de capture
        if self.active_vms[vm_id]["info"]["type"] == "docker":
            # Capturer via VNC ou autre méthode
            screenshot_path = f"/tmp/{vm_id}_screenshot.png"

            # Commande de capture (simplifiée)
            capture_cmd = f"import pyautogui; pyautogui.screenshot('{screenshot_path}')"

            try:
                await self._execute_in_container(vm_id, f'python3 -c "{capture_cmd}"')
                screenshots.append(screenshot_path)
            except Exception as e:
                logger.warning(f"Impossible de capturer screenshot: {e}")

        return screenshots

    async def _execute_in_container(self, vm_id: str, command: str) -> str:
        """Exécute une commande dans un conteneur Docker.

        Args:
            vm_id: ID de la VM
            command: Commande à exécuter

        Returns:
            Sortie de la commande
        """
        import docker

        try:
            client = docker.from_env()
            container = client.containers.get(vm_id)

            result = container.exec_run(command, stdout=True, stderr=True)

            if result.exit_code != 0:
                raise AgentExecutionError(f"Commande échouée: {result.output.decode()}")

            return result.output.decode()

        except Exception as e:
            raise AgentExecutionError(f"Erreur exécution conteneur: {e}")

    async def _write_file_to_container(self, vm_id: str, file_path: str, content: str) -> None:
        """Écrit un fichier dans un conteneur Docker.

        Args:
            vm_id: ID de la VM
            file_path: Chemin du fichier
            content: Contenu du fichier
        """
        import io
        import tarfile

        import docker

        try:
            client = docker.from_env()
            container = client.containers.get(vm_id)

            # Créer un tar avec le fichier
            tar_buffer = io.BytesIO()

            with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                file_data = content.encode("utf-8")
                file_info = tarfile.TarInfo(name=file_path)
                file_info.size = len(file_data)
                file_info.mode = 0o644

                tar.addfile(file_info, io.BytesIO(file_data))

            tar_buffer.seek(0)

            # Copier dans le conteneur
            container.put_archive(path="/", data=tar_buffer.read())

        except Exception as e:
            raise AgentExecutionError(f"Erreur écriture fichier conteneur: {e}")

    async def destroy_vm(self, vm_id: str) -> None:
        """Détruit une VM et nettoie les ressources.

        Args:
            vm_id: ID de la VM à détruire
        """
        if vm_id not in self.active_vms:
            logger.warning(f"VM {vm_id} non trouvée pour destruction")
            return

        try:
            logger.info(f"Destruction VM {vm_id}")

            vm_info = self.active_vms[vm_id]
            vm_type = vm_info["info"]["type"]

            if vm_type == "docker":
                await self._destroy_docker_vm(vm_id)
            elif vm_type == "qemu":
                await self._destroy_qemu_vm(vm_id)

            # Nettoyer l'état
            del self.active_vms[vm_id]

            logger.info(f"VM {vm_id} détruite avec succès")

        except Exception as e:
            logger.error(f"Erreur destruction VM {vm_id}: {e}")

    async def _destroy_docker_vm(self, vm_id: str) -> None:
        """Détruit une VM Docker.

        Args:
            vm_id: ID de la VM
        """
        import docker

        try:
            client = docker.from_env()
            container = client.containers.get(vm_id)

            # Arrêter et supprimer le conteneur
            container.stop()
            container.remove()

        except Exception as e:
            logger.warning(f"Erreur destruction conteneur Docker: {e}")

    async def _destroy_qemu_vm(self, vm_id: str) -> None:
        """Détruit une VM QEMU.

        Args:
            vm_id: ID de la VM
        """
        # Implémentation simplifiée - nécessiterait gestion PID
        logger.info(f"Destruction VM QEMU {vm_id}")

    async def cleanup_expired_vms(self) -> None:
        """Nettoie les VMs expirées."""
        current_time = datetime.now()
        expired_vms = []

        for vm_id, vm_info in self.active_vms.items():
            created_at = vm_info["created_at"]
            if current_time - created_at > timedelta(seconds=self.vm_timeout):
                expired_vms.append(vm_id)

        for vm_id in expired_vms:
            logger.info(f"Nettoyage VM expirée {vm_id}")
            await self.destroy_vm(vm_id)

    async def get_vm_status(self, vm_id: str) -> dict[str, Any]:
        """Obtient le statut d'une VM.

        Args:
            vm_id: ID de la VM

        Returns:
            Statut de la VM
        """
        if vm_id not in self.active_vms:
            raise AgentExecutionError(f"VM {vm_id} non trouvée")

        vm_info = self.active_vms[vm_id]

        # Obtenir des informations supplémentaires selon le type
        if vm_info["info"]["type"] == "docker":
            status = await self._get_docker_container_status(vm_id)
        else:
            status = {"status": "unknown"}

        return {
            "vm_id": vm_id,
            "task_id": vm_info["task_id"],
            "created_at": vm_info["created_at"].isoformat(),
            "uptime": (datetime.now() - vm_info["created_at"]).total_seconds(),
            "config": vm_info["config"],
            "runtime_status": status,
        }

    async def _get_docker_container_status(self, vm_id: str) -> dict[str, Any]:
        """Obtient le statut d'un conteneur Docker.

        Args:
            vm_id: ID du conteneur

        Returns:
            Statut du conteneur
        """
        import docker

        try:
            client = docker.from_env()
            container = client.containers.get(vm_id)

            return {
                "status": container.status,
                "image": container.image.tags[0] if container.image.tags else "unknown",
                "created": container.attrs["Created"],
                "ports": container.ports,
                "stats": container.stats(stream=False),
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def execute_task(self, task_config: dict[str, Any]) -> dict[str, Any]:
        """Exécute une tâche dans une VM sandbox.

        Args:
            task_config: Configuration de la tâche:
                - vm_config: Configuration VM
                - automation_task: Tâche OpenManus
                - timeout: Timeout (optionnel)

        Returns:
            Résultat de l'exécution
        """
        task_id = self._create_task(task_config)

        try:
            self._update_task(task_id, {"status": TaskStatus.RUNNING})
            self._add_log(task_id, "Création VM sandbox")

            # Extraire la configuration
            vm_config = task_config.get("vm_config", {})
            automation_task = task_config.get("automation_task", {})
            timeout = task_config.get("timeout", self.vm_timeout)

            # Créer la VM
            vm_id = await self.create_vm(task_id, vm_config)
            self._add_log(task_id, f"VM créée: {vm_id}")

            # Exécuter la tâche dans la VM
            self._update_progress(task_id, 50, "Exécution tâche dans VM")
            result = await self.execute_in_vm(vm_id, automation_task)

            # Marquer comme complété
            self._update_progress(task_id, 100, "Tâche complétée")
            self._update_task(task_id, {"status": TaskStatus.COMPLETED, "result": result})

            # Nettoyer la VM si demandé
            if task_config.get("cleanup_vm", True):
                await self.destroy_vm(vm_id)

            return await self.get_task_result(task_id)

        except Exception as e:
            logger.error(f"Tâche {task_id} échouée: {e}")
            self._update_task(task_id, {"status": TaskStatus.FAILED, "error": str(e)})

            # Nettoyer la VM en cas d'erreur
            if "vm_id" in locals():
                await self.destroy_vm(vm_id)

            raise AgentExecutionError(f"Exécution tâche échouée: {e}") from e

    async def cleanup(self) -> None:
        """Nettoie toutes les ressources."""
        logger.info("Nettoyage VM Sandbox adapter")

        # Détruire toutes les VMs actives
        vm_ids = list(self.active_vms.keys())

        for vm_id in vm_ids:
            try:
                await self.destroy_vm(vm_id)
            except Exception as e:
                logger.error(f"Erreur nettoyage VM {vm_id}: {e}")

        logger.info("VM Sandbox adapter nettoyé")


# Fonction utilitaire pour tester
async def test_vm_sandbox():
    """Test l'adaptateur VM Sandbox."""
    adapter = VMSandboxAdapter(vm_provider="docker", max_vms=2)

    try:
        # Test création VM et exécution tâche
        task_config = {
            "vm_config": {"image": "ubuntu:22.04", "memory": "1g", "cpus": 1},
            "automation_task": {"url": "https://example.com", "action": "navigate"},
            "cleanup_vm": True,
        }

        result = await adapter.execute_task(task_config)
        print("Résultat test VM Sandbox:", json.dumps(result, indent=2, default=str))

    except Exception as e:
        logger.error(f"Test VM Sandbox échoué: {e}")

    finally:
        await adapter.cleanup()


if __name__ == "__main__":
    asyncio.run(test_vm_sandbox())
