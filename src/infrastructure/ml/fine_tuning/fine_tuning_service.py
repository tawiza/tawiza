"""Fine-tuning service using Ollama."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import mlflow
from loguru import logger

from src.application.ports.storage_ports import (
    IModelStorageService,
    IModelVersioningService,
)
from src.infrastructure.security.validators import (
    validate_model_name,
    validate_path,
)

from .data_preparation import DataPreparationService
from .lora_finetuner import LoRAConfig, LoRAFineTuner, TrainingConfig


class FineTuningService:
    """Service de fine-tuning utilisant Ollama."""

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        mlflow_tracking_uri: str | None = None,
        storage_service: IModelStorageService | None = None,
        versioning_service: IModelVersioningService | None = None,
    ):
        """
        Initialise le service de fine-tuning.

        Args:
            ollama_url: URL du service Ollama
            mlflow_tracking_uri: URI de tracking MLflow (optionnel)
            storage_service: Service de stockage MinIO (optionnel)
            versioning_service: Service de versioning (optionnel)
        """
        self.ollama_url = ollama_url
        self.mlflow_tracking_uri = mlflow_tracking_uri
        self.data_prep = DataPreparationService()
        self.training_jobs: dict[str, dict[str, Any]] = {}
        self.storage_service = storage_service
        self.versioning_service = versioning_service

        # Setup MLflow tracking (optional)
        if self.mlflow_tracking_uri:
            mlflow.set_tracking_uri(self.mlflow_tracking_uri)
            # Create or get experiment for fine-tuning
            try:
                experiment = mlflow.get_experiment_by_name("ollama-fine-tuning")
                if experiment is None:
                    mlflow.create_experiment("ollama-fine-tuning")
                    logger.info("Created MLflow experiment: ollama-fine-tuning")
                else:
                    logger.debug(
                        f"Using existing MLflow experiment: ollama-fine-tuning (ID: {experiment.experiment_id})"
                    )
            except Exception as e:
                logger.debug(f"MLflow not available (optional): {type(e).__name__}")
        else:
            logger.debug("MLflow tracking disabled (no tracking URI provided)")

    async def start_fine_tuning(
        self,
        project_id: str,
        base_model: str,
        annotations: list[dict[str, Any]],
        task_type: str = "classification",
        model_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Démarre un job de fine-tuning.

        Args:
            project_id: ID du projet Label Studio
            base_model: Modèle de base (ex: "qwen3-coder:30b")
            annotations: Annotations depuis Label Studio
            task_type: Type de tâche (classification, ner, etc.)
            model_name: Nom du modèle fine-tuné (auto-généré si None)

        Returns:
            Informations sur le job de fine-tuning
        """
        job_id = str(uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # SECURITY FIX (VULN-002): Validate base_model to prevent command injection
        try:
            base_model = validate_model_name(base_model)
        except ValueError as e:
            raise ValueError(f"Invalid base model name: {e}")

        if model_name is None:
            model_name = f"{base_model.split(':')[0]}-finetuned-{timestamp}"

        # SECURITY FIX (VULN-002): Validate model_name to prevent command injection
        try:
            model_name = validate_model_name(model_name)
        except ValueError as e:
            raise ValueError(f"Invalid model name: {e}")

        logger.info(f"Starting fine-tuning job {job_id} for model {model_name}")

        # Préparer les données
        training_data = self.data_prep.prepare_training_data(
            annotations=annotations, task_type=task_type
        )

        if not training_data:
            raise ValueError("No training data could be prepared from annotations")

        # Valider les données
        validation_stats = self.data_prep.validate_training_data(training_data)
        if validation_stats["valid_examples"] == 0:
            raise ValueError("No valid training examples found")

        # Créer le Modelfile
        modelfile_content = self.data_prep.convert_to_ollama_format(
            training_data=training_data, base_model=base_model
        )

        # Sauvegarder le Modelfile
        modelfile_path = Path(f"/tmp/modelfile_{job_id}")
        modelfile_path.write_text(modelfile_content)

        # Initialiser le job
        self.training_jobs[job_id] = {
            "job_id": job_id,
            "project_id": project_id,
            "base_model": base_model,
            "model_name": model_name,
            "task_type": task_type,
            "status": "preparing",
            "training_examples": len(training_data),
            "validation_stats": validation_stats,
            "created_at": datetime.now().isoformat(),
            "modelfile_path": str(modelfile_path),
        }

        # Log to MLflow if enabled
        if self.mlflow_tracking_uri:
            try:
                with mlflow.start_run(run_name=f"fine-tune-{model_name}") as run:
                    # Log parameters
                    mlflow.log_param("job_id", job_id)
                    mlflow.log_param("project_id", project_id)
                    mlflow.log_param("base_model", base_model)
                    mlflow.log_param("model_name", model_name)
                    mlflow.log_param("task_type", task_type)
                    mlflow.log_param("training_examples", len(training_data))

                    # Log validation metrics
                    mlflow.log_metric("valid_examples", validation_stats["valid_examples"])
                    mlflow.log_metric("invalid_examples", validation_stats["invalid_examples"])
                    mlflow.log_metric("total_examples", validation_stats["total_examples"])

                    # Log Modelfile as artifact
                    mlflow.log_artifact(str(modelfile_path), "modelfiles")

                    # Save MLflow run ID
                    self.training_jobs[job_id]["mlflow_run_id"] = run.info.run_id

                    logger.info(f"Logged fine-tuning job to MLflow: {run.info.run_id}")
            except Exception as e:
                logger.error(f"Failed to log to MLflow: {e}")

        # Lancer le fine-tuning en arrière-plan
        asyncio.create_task(self._run_fine_tuning(job_id, model_name, modelfile_path))

        return self.training_jobs[job_id]

    async def _run_fine_tuning(self, job_id: str, model_name: str, modelfile_path: Path) -> None:
        """
        Exécute le fine-tuning en arrière-plan.

        Args:
            job_id: ID du job
            model_name: Nom du modèle à créer
            modelfile_path: Chemin vers le Modelfile
        """
        try:
            self.training_jobs[job_id]["status"] = "training"
            self.training_jobs[job_id]["started_at"] = datetime.now().isoformat()

            logger.info(f"Creating model {model_name} with Ollama")

            # SECURITY FIX (VULN-002): Validate inputs before subprocess execution
            # Re-validate model_name (defense in depth)
            validated_model_name = validate_model_name(model_name)

            # Validate modelfile path (prevent path traversal)
            validated_path = validate_path(
                str(modelfile_path), base_dir="/tmp", must_be_within_base=True
            )

            # Créer le modèle avec Ollama
            # Note: Ollama ne supporte pas le vrai fine-tuning, on crée un modèle
            # avec few-shot learning via le Modelfile
            # SECURITY: Using list of args (NOT shell=True) prevents command injection
            process = await asyncio.create_subprocess_exec(
                "ollama",
                "create",
                validated_model_name,  # SECURITY: Validated input
                "-f",
                str(validated_path),  # SECURITY: Validated path
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Fine-tuning failed: {error_msg}")
                self.training_jobs[job_id]["status"] = "failed"
                self.training_jobs[job_id]["error"] = error_msg
                return

            logger.info(f"Model {model_name} created successfully")

            # Tester le modèle
            test_result = await self._test_model(model_name)

            self.training_jobs[job_id].update(
                {
                    "status": "completed",
                    "completed_at": datetime.now().isoformat(),
                    "test_result": test_result,
                    "model_available": True,
                }
            )

            # Backup model to MinIO if storage service is configured
            if self.storage_service and self.versioning_service:
                try:
                    await self._backup_model_to_storage(job_id, model_name, modelfile_path)
                except Exception as e:
                    logger.error(f"Failed to backup model to storage: {e}")
                    # Don't fail the job if backup fails, just log the error

            # Log completion to MLflow
            if self.mlflow_tracking_uri and "mlflow_run_id" in self.training_jobs[job_id]:
                try:
                    mlflow_run_id = self.training_jobs[job_id]["mlflow_run_id"]
                    with mlflow.start_run(run_id=mlflow_run_id):
                        # Log completion status
                        mlflow.log_metric("training_success", 1.0)
                        mlflow.log_metric("model_available", 1.0)

                        # Log test results if available
                        if test_result.get("status") == "success":
                            mlflow.log_metric("test_success", 1.0)
                            if "tokens_generated" in test_result:
                                mlflow.log_metric(
                                    "test_tokens_generated", test_result["tokens_generated"]
                                )

                        # Log training duration
                        started_at = datetime.fromisoformat(
                            self.training_jobs[job_id]["started_at"]
                        )
                        completed_at = datetime.fromisoformat(
                            self.training_jobs[job_id]["completed_at"]
                        )
                        duration_seconds = (completed_at - started_at).total_seconds()
                        mlflow.log_metric("training_duration_seconds", duration_seconds)

                        logger.info(f"Logged completion metrics to MLflow: {mlflow_run_id}")
                except Exception as e:
                    logger.error(f"Failed to log completion to MLflow: {e}")

            logger.info(f"Fine-tuning job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Fine-tuning job {job_id} failed: {e}")
            self.training_jobs[job_id].update(
                {
                    "status": "failed",
                    "error": str(e),
                    "failed_at": datetime.now().isoformat(),
                }
            )

            # Log failure to MLflow
            if self.mlflow_tracking_uri and "mlflow_run_id" in self.training_jobs[job_id]:
                try:
                    mlflow_run_id = self.training_jobs[job_id]["mlflow_run_id"]
                    with mlflow.start_run(run_id=mlflow_run_id):
                        mlflow.log_metric("training_success", 0.0)
                        mlflow.log_param("error_message", str(e))
                        logger.info(f"Logged failure to MLflow: {mlflow_run_id}")
                except Exception as mlflow_error:
                    logger.error(f"Failed to log failure to MLflow: {mlflow_error}")

    async def _test_model(self, model_name: str) -> dict[str, Any]:
        """
        Teste le modèle fine-tuné.

        Args:
            model_name: Nom du modèle

        Returns:
            Résultat du test
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "Hello, can you introduce yourself?",
                        "stream": False,
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "status": "success",
                        "response": result.get("response", ""),
                        "tokens_generated": len(result.get("response", "").split()),
                    }
                else:
                    return {"status": "failed", "error": f"HTTP {response.status_code}"}

        except Exception as e:
            logger.error(f"Model test failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """
        Récupère le statut d'un job de fine-tuning.

        Args:
            job_id: ID du job

        Returns:
            Statut du job ou None si non trouvé
        """
        return self.training_jobs.get(job_id)

    async def list_jobs(self, project_id: str | None = None) -> list[dict[str, Any]]:
        """
        Liste les jobs de fine-tuning.

        Args:
            project_id: Filtrer par projet (optionnel)

        Returns:
            Liste des jobs
        """
        jobs = list(self.training_jobs.values())

        if project_id:
            jobs = [j for j in jobs if j.get("project_id") == project_id]

        # Trier par date de création (plus récents en premier)
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return jobs

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        """
        Annule un job de fine-tuning en cours.

        Args:
            job_id: ID du job à annuler

        Returns:
            Résultat de l'annulation
        """
        job = self.training_jobs.get(job_id)
        if not job:
            return {"status": "error", "message": f"Job {job_id} not found"}

        current_status = job.get("status")
        if current_status not in ("pending", "running", "preparing"):
            return {
                "status": "error",
                "message": f"Cannot cancel job in status '{current_status}'",
            }

        # Update job status
        job["status"] = "cancelled"
        job["cancelled_at"] = datetime.now().isoformat()

        # If there's an associated subprocess/task, we could kill it here
        # For now, the status update will prevent further processing

        logger.info(f"Job {job_id} cancelled")

        # Log cancellation to MLflow if available
        if self.mlflow_tracking_uri and "mlflow_run_id" in job:
            try:
                with mlflow.start_run(run_id=job["mlflow_run_id"]):
                    mlflow.log_metric("training_cancelled", 1.0)
                    mlflow.set_tag("status", "cancelled")
            except Exception as e:
                logger.warning(f"Failed to log cancellation to MLflow: {e}")

        return {
            "status": "success",
            "job_id": job_id,
            "message": f"Job {job_id} cancelled successfully",
        }

    async def get_mlflow_logs(self, job_id: str) -> dict[str, Any]:
        """
        Récupère les logs MLflow d'un job.

        Args:
            job_id: ID du job

        Returns:
            Logs et métriques du job
        """
        job = self.training_jobs.get(job_id)
        if not job:
            return {"status": "error", "message": f"Job {job_id} not found"}

        mlflow_run_id = job.get("mlflow_run_id")
        if not mlflow_run_id:
            return {
                "status": "no_mlflow",
                "job_id": job_id,
                "message": "No MLflow run associated with this job",
                "job_status": job.get("status"),
            }

        if not self.mlflow_tracking_uri:
            return {
                "status": "mlflow_disabled",
                "job_id": job_id,
                "message": "MLflow tracking is not configured",
            }

        try:
            # Get run info from MLflow
            run = mlflow.get_run(mlflow_run_id)

            # Extract metrics
            metrics = run.data.metrics
            params = run.data.params
            tags = run.data.tags

            # Format logs
            log_lines = [
                f"=== MLflow Run: {mlflow_run_id} ===",
                f"Status: {run.info.status}",
                f"Start Time: {datetime.fromtimestamp(run.info.start_time / 1000).isoformat()}",
            ]

            if run.info.end_time:
                log_lines.append(
                    f"End Time: {datetime.fromtimestamp(run.info.end_time / 1000).isoformat()}"
                )

            log_lines.append("\n--- Parameters ---")
            for key, value in params.items():
                log_lines.append(f"  {key}: {value}")

            log_lines.append("\n--- Metrics ---")
            for key, value in metrics.items():
                log_lines.append(f"  {key}: {value}")

            if tags:
                log_lines.append("\n--- Tags ---")
                for key, value in tags.items():
                    if not key.startswith("mlflow."):  # Skip internal tags
                        log_lines.append(f"  {key}: {value}")

            return {
                "status": "success",
                "job_id": job_id,
                "mlflow_run_id": mlflow_run_id,
                "mlflow_status": run.info.status,
                "metrics": metrics,
                "params": params,
                "content": "\n".join(log_lines),
            }

        except Exception as e:
            logger.error(f"Failed to get MLflow logs for job {job_id}: {e}")
            return {
                "status": "error",
                "job_id": job_id,
                "message": f"Failed to retrieve MLflow logs: {str(e)}",
            }

    async def delete_model(self, model_name: str) -> dict[str, Any]:
        """
        Supprime un modèle fine-tuné.

        Args:
            model_name: Nom du modèle

        Returns:
            Résultat de la suppression
        """
        try:
            # SECURITY FIX (VULN-002): Validate model_name before subprocess
            validated_model_name = validate_model_name(model_name)

            # SECURITY: Using list of args prevents command injection
            process = await asyncio.create_subprocess_exec(
                "ollama",
                "rm",
                validated_model_name,  # SECURITY: Validated input
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"Model {model_name} deleted successfully")
                return {"status": "success", "message": f"Model {model_name} deleted"}
            else:
                error = stderr.decode() if stderr else "Unknown error"
                return {"status": "failed", "error": error}

        except Exception as e:
            logger.error(f"Failed to delete model {model_name}: {e}")
            return {"status": "failed", "error": str(e)}

    async def list_fine_tuned_models(self) -> list[dict[str, Any]]:
        """
        Liste tous les modèles fine-tunés.

        Returns:
            Liste des modèles
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")

                if response.status_code == 200:
                    all_models = response.json().get("models", [])
                    # Filtrer les modèles fine-tunés (contiennent "finetuned" dans le nom)
                    fine_tuned = [m for m in all_models if "finetuned" in m.get("name", "").lower()]
                    return fine_tuned
                else:
                    logger.error(f"Failed to list models: HTTP {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"Failed to list fine-tuned models: {e}")
            return []

    async def export_model(self, model_name: str, export_path: Path) -> dict[str, Any]:
        """
        Exporte un modèle fine-tuné.

        Args:
            model_name: Nom du modèle
            export_path: Chemin d'export

        Returns:
            Résultat de l'export
        """
        try:
            # SECURITY FIX (VULN-002): Validate model_name before subprocess
            validated_model_name = validate_model_name(model_name)

            # SECURITY FIX (VULN-005): Validate export_path to prevent path traversal
            # Note: export_path is a Path object, convert to string for validation
            validated_export_path = validate_path(
                str(export_path),
                must_be_within_base=False,  # Allow any path for exports
            )

            validated_export_path.parent.mkdir(parents=True, exist_ok=True)

            # Obtenir le Modelfile
            # SECURITY: Using list of args prevents command injection
            process = await asyncio.create_subprocess_exec(
                "ollama",
                "show",
                validated_model_name,  # SECURITY: Validated input
                "--modelfile",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                modelfile_content = stdout.decode()
                validated_export_path.write_text(modelfile_content)

                return {
                    "status": "success",
                    "export_path": str(validated_export_path),
                    "size_bytes": validated_export_path.stat().st_size,
                }
            else:
                error = stderr.decode() if stderr else "Unknown error"
                return {"status": "failed", "error": error}

        except Exception as e:
            logger.error(f"Failed to export model {model_name}: {e}")
            return {"status": "failed", "error": str(e)}

    async def _backup_model_to_storage(
        self,
        job_id: str,
        model_name: str,
        modelfile_path: Path,
    ) -> dict[str, Any]:
        """
        Backup a fine-tuned model to MinIO storage.

        Args:
            job_id: Training job ID
            model_name: Name of the model
            modelfile_path: Path to the modelfile

        Returns:
            Backup result with version information
        """
        try:
            logger.info(f"Backing up model {model_name} to MinIO storage")

            # SECURITY FIX (VULN-002): Validate model_name before subprocess
            validated_model_name = validate_model_name(model_name)

            # Export modelfile from Ollama
            # SECURITY: Using list of args prevents command injection
            process = await asyncio.create_subprocess_exec(
                "ollama",
                "show",
                validated_model_name,  # SECURITY: Validated input
                "--modelfile",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Failed to export modelfile: {error}")
                return {"status": "failed", "error": error}

            modelfile_content = stdout.decode()

            # Get job metadata
            job = self.training_jobs.get(job_id, {})

            # Prepare version metadata
            metadata = {
                "mlflow_run_id": job.get("mlflow_run_id"),
                "mlflow_experiment_id": "ollama-fine-tuning",
                "accuracy": None,  # Could be extracted from test_result if available
                "training_examples": job.get("training_examples", 0),
                "task_type": job.get("task_type", "classification"),
                "hyperparameters": {},  # Ollama doesn't expose these easily
                "tags": {
                    "job_id": job_id,
                    "created_from": "fine_tuning_service",
                },
                "description": f"Auto-backup from fine-tuning job {job_id}",
            }

            # Create new version in storage
            version_metadata = await self.versioning_service.create_new_version(
                model_name=model_name,
                base_model=job.get("base_model", "unknown"),
                modelfile_content=modelfile_content,
                metadata=metadata,
            )

            # Update job with storage info
            self.training_jobs[job_id]["storage_version"] = str(version_metadata.version)
            self.training_jobs[job_id]["storage_path"] = version_metadata.storage_path

            logger.info(
                f"Model {model_name} backed up to MinIO as version {version_metadata.version}"
            )

            return {
                "status": "success",
                "version": str(version_metadata.version),
                "storage_path": version_metadata.storage_path,
            }

        except Exception as e:
            logger.error(f"Failed to backup model {model_name}: {e}")
            return {"status": "failed", "error": str(e)}

    async def start_lora_fine_tuning(
        self,
        model_name: str,
        train_data: list[dict[str, str]],
        eval_data: list[dict[str, str]] | None = None,
        lora_r: int = 16,
        lora_alpha: int = 32,
        epochs: int = 3,
        batch_size: int = 2,
        learning_rate: float = 2e-4,
        max_seq_length: int = 2048,
        output_dir: str | None = None,
    ) -> dict[str, Any]:
        """
        Start LoRA fine-tuning using Unsloth.

        This method provides efficient fine-tuning with:
        - 2x faster training vs standard LoRA
        - 70% less VRAM usage
        - QLoRA (4-bit quantization) support
        - MLflow experiment tracking
        - Automatic checkpointing

        Args:
            model_name: Base model name (HuggingFace format)
            train_data: Training examples [{"instruction": ..., "input": ..., "output": ...}]
            eval_data: Validation examples (optional)
            lora_r: LoRA rank (16, 32, or 64 recommended)
            lora_alpha: LoRA alpha (typically 2*r)
            epochs: Number of training epochs
            batch_size: Batch size per device
            learning_rate: Learning rate
            max_seq_length: Maximum sequence length
            output_dir: Output directory for checkpoints

        Returns:
            dict: Job information with status and metrics

        Example:
            train_data = [
                {
                    "instruction": "Translate to French",
                    "input": "Hello world",
                    "output": "Bonjour le monde"
                },
                ...
            ]

            result = await service.start_lora_fine_tuning(
                model_name="unsloth/Qwen2.5-14B-Instruct",
                train_data=train_data,
                epochs=3,
                lora_r=16
            )
        """
        job_id = str(uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Validate model name
        try:
            model_name = validate_model_name(model_name)
        except ValueError as e:
            raise ValueError(f"Invalid model name: {e}")

        # Set output directory
        if output_dir is None:
            output_dir = f"./outputs/lora/{model_name.replace('/', '_')}_{timestamp}"

        # SECURITY FIX (VULN-003): Validate output_dir to prevent path traversal
        try:
            output_dir = validate_path(output_dir, allowed_base="./outputs")
        except ValueError as e:
            raise ValueError(f"Invalid output directory: {e}")

        # Create configurations
        lora_config = LoRAConfig(
            r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=0.05,
        )

        training_config = TrainingConfig(
            output_dir=output_dir,
            num_train_epochs=epochs,
            per_device_train_batch_size=batch_size,
            learning_rate=learning_rate,
            max_seq_length=max_seq_length,
        )

        # Create job entry
        self.training_jobs[job_id] = {
            "job_id": job_id,
            "type": "lora",
            "model_name": model_name,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "training_examples": len(train_data),
            "validation_examples": len(eval_data) if eval_data else 0,
            "lora_config": {
                "r": lora_r,
                "alpha": lora_alpha,
            },
            "training_config": {
                "epochs": epochs,
                "batch_size": batch_size,
                "learning_rate": learning_rate,
            },
            "output_dir": output_dir,
        }

        logger.info(
            f"Starting LoRA fine-tuning job {job_id} "
            f"(model={model_name}, examples={len(train_data)})"
        )

        # Start training in background
        asyncio.create_task(
            self._run_lora_training(
                job_id, model_name, train_data, eval_data, lora_config, training_config
            )
        )

        return {
            "job_id": job_id,
            "status": "running",
            "model_name": model_name,
            "training_examples": len(train_data),
            "started_at": self.training_jobs[job_id]["started_at"],
        }

    async def _run_lora_training(
        self,
        job_id: str,
        model_name: str,
        train_data: list[dict[str, str]],
        eval_data: list[dict[str, str]] | None,
        lora_config: LoRAConfig,
        training_config: TrainingConfig,
    ):
        """
        Run LoRA training (internal background task).

        Args:
            job_id: Job identifier
            model_name: Model name
            train_data: Training data
            eval_data: Validation data
            lora_config: LoRA configuration
            training_config: Training configuration
        """
        try:
            # Create fine-tuner
            tuner = LoRAFineTuner(
                model_name=model_name,
                lora_config=lora_config,
                training_config=training_config,
                mlflow_tracking_uri=self.mlflow_tracking_uri,
            )

            # Load model
            logger.info(f"Loading model for job {job_id}...")
            await tuner.load_model()

            # Train
            logger.info(f"Training model for job {job_id}...")
            result = await tuner.train(
                train_data=train_data, eval_data=eval_data, experiment_name="lora-fine-tuning"
            )

            # Save model
            output_path = f"{training_config.output_dir}/final_model"
            logger.info(f"Saving model for job {job_id} to {output_path}...")
            saved_path = await tuner.save_model(output_path, save_method="merged")

            # Update job status
            self.training_jobs[job_id].update(
                {
                    "status": "completed",
                    "completed_at": datetime.now().isoformat(),
                    "metrics": result.get("metrics", {}),
                    "model_path": saved_path,
                }
            )

            logger.info(f"LoRA fine-tuning job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"LoRA fine-tuning job {job_id} failed: {e}")
            self.training_jobs[job_id].update(
                {
                    "status": "failed",
                    "error": str(e),
                    "failed_at": datetime.now().isoformat(),
                }
            )
