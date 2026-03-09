#!/usr/bin/env python3
"""
Service de configuration pour Tawiza-V2 CLI

Gère la configuration système avec:
- Validation des configurations
- Persistance dans des fichiers JSON
- Application des configurations
- Rollback en cas d'erreur
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

# ==============================================================================
# CONSTANTES
# ==============================================================================

from src.cli.constants import PROJECT_ROOT

CONFIG_DIR = PROJECT_ROOT / "configs"
USER_CONFIG_FILE = CONFIG_DIR / "user_config.json"
SYSTEM_CONFIG_FILE = CONFIG_DIR / "system_config.json"
BACKUP_DIR = CONFIG_DIR / "backups"

DEFAULT_MAX_TASKS = 5
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_CACHE_TTL = 300  # 5 minutes


# ==============================================================================
# EXCEPTIONS
# ==============================================================================

class ConfigValidationError(Exception):
    """Erreur de validation de configuration"""

    def __init__(self, message: str, field: str | None = None, details: dict | None = None):
        self.message = message
        self.field = field
        self.details = details or {}
        super().__init__(message)


class ConfigPersistenceError(Exception):
    """Erreur de persistance de configuration"""
    pass


# ==============================================================================
# MODÈLES DE CONFIGURATION
# ==============================================================================

@dataclass
class GPUConfig:
    """Configuration GPU"""
    enabled: bool = True
    device_id: int = 0
    memory_limit: float | None = None  # Pourcentage (0-100)
    optimization_level: str = "auto"  # auto, conservative, aggressive

    def validate(self) -> list[str]:
        """Valider la configuration GPU"""
        errors = []

        if self.memory_limit is not None and not 0 <= self.memory_limit <= 100:
            errors.append("memory_limit doit être entre 0 et 100")

        if self.optimization_level not in ("auto", "conservative", "aggressive"):
            errors.append("optimization_level invalide")

        return errors


@dataclass
class MonitoringConfig:
    """Configuration du monitoring"""
    enabled: bool = True
    interval: float = 1.0  # secondes
    metrics: list[str] = field(default_factory=lambda: ["cpu", "memory", "gpu"])
    export_path: str | None = None

    def validate(self) -> list[str]:
        """Valider la configuration monitoring"""
        errors = []

        if self.interval < 0.1:
            errors.append("interval doit être >= 0.1 seconde")

        valid_metrics = {"cpu", "memory", "gpu", "disk", "network"}
        invalid_metrics = set(self.metrics) - valid_metrics
        if invalid_metrics:
            errors.append(f"Métriques invalides: {invalid_metrics}")

        return errors


@dataclass
class AgentConfig:
    """Configuration d'un agent"""
    name: str
    enabled: bool = True
    priority: int = 5  # 1-10
    timeout: int = 300  # secondes
    retry_count: int = 3
    auto_restart: bool = True

    def validate(self) -> list[str]:
        """Valider la configuration agent"""
        errors = []

        if not self.name:
            errors.append("Le nom de l'agent est requis")

        if not 1 <= self.priority <= 10:
            errors.append("priority doit être entre 1 et 10")

        if self.timeout < 0:
            errors.append("timeout doit être positif")

        if self.retry_count < 0:
            errors.append("retry_count doit être positif")

        return errors


@dataclass
class SystemConfig:
    """Configuration système complète"""
    # Général
    log_level: str = DEFAULT_LOG_LEVEL
    max_concurrent_tasks: int = DEFAULT_MAX_TASKS
    cache_ttl: int = DEFAULT_CACHE_TTL

    # GPU
    gpu: GPUConfig = field(default_factory=GPUConfig)

    # Monitoring
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    # Agents activés
    enabled_agents: list[str] = field(default_factory=lambda: [
        "data_analyst",
        "ml_engineer",
        "code_generator"
    ])

    # Modèle LLM par défaut
    default_model: str = "qwen3.5:27b"

    # Métadonnées
    version: str = "3.0.0"
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self):
        """Initialisation post-création"""
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

        # Convertir les dicts en dataclasses si nécessaire
        if isinstance(self.gpu, dict):
            self.gpu = GPUConfig(**self.gpu)
        if isinstance(self.monitoring, dict):
            self.monitoring = MonitoringConfig(**self.monitoring)

    def validate(self) -> list[str]:
        """Valider la configuration complète"""
        errors = []

        # Validation log level
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_levels:
            errors.append(f"log_level invalide. Valeurs valides: {valid_levels}")

        # Validation max_concurrent_tasks
        if not 1 <= self.max_concurrent_tasks <= 100:
            errors.append("max_concurrent_tasks doit être entre 1 et 100")

        # Validation cache_ttl
        if self.cache_ttl < 0:
            errors.append("cache_ttl doit être positif")

        # Validation sous-configurations
        errors.extend(self.gpu.validate())
        errors.extend(self.monitoring.validate())

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Convertir en dictionnaire"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SystemConfig:
        """Créer depuis un dictionnaire"""
        return cls(**data)

    def merge_with(self, other: dict[str, Any]) -> SystemConfig:
        """Fusionner avec un autre dict de config"""
        current = self.to_dict()

        def deep_merge(base: dict, updates: dict) -> dict:
            result = base.copy()
            for key, value in updates.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        merged = deep_merge(current, other)
        merged['updated_at'] = datetime.now().isoformat()
        return SystemConfig.from_dict(merged)


# ==============================================================================
# SERVICE DE CONFIGURATION
# ==============================================================================

class ConfigService:
    """Service de gestion de configuration"""

    def __init__(self, config_dir: Path | None = None):
        self._config_dir = config_dir or CONFIG_DIR
        self._current_config: SystemConfig | None = None
        self._backup_dir = self._config_dir / "backups"

        # Créer les répertoires si nécessaire
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    @property
    def config(self) -> SystemConfig:
        """Obtenir la configuration actuelle"""
        if self._current_config is None:
            self._current_config = self.load_config()
        return self._current_config

    def load_config(self, config_file: Path | None = None) -> SystemConfig:
        """Charger la configuration depuis un fichier"""
        config_file = config_file or (self._config_dir / "system_config.json")

        if config_file.exists():
            try:
                with open(config_file) as f:
                    data = json.load(f)
                logger.info(f"Configuration chargée depuis {config_file}")
                return SystemConfig.from_dict(data)
            except Exception as e:
                logger.warning(f"Erreur chargement config: {e}. Utilisation config par défaut.")

        # Configuration par défaut
        return SystemConfig()

    def save_config(
        self,
        config: SystemConfig | None = None,
        config_file: Path | None = None,
        create_backup: bool = True
    ) -> None:
        """Sauvegarder la configuration"""
        config = config or self._current_config
        if config is None:
            raise ConfigPersistenceError("Aucune configuration à sauvegarder")

        config_file = config_file or (self._config_dir / "system_config.json")

        # Créer une backup si le fichier existe
        if create_backup and config_file.exists():
            self._create_backup(config_file)

        try:
            # Mettre à jour le timestamp
            config.updated_at = datetime.now().isoformat()

            with open(config_file, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)

            logger.info(f"Configuration sauvegardée dans {config_file}")

        except Exception as e:
            logger.error(f"Erreur sauvegarde config: {e}")
            raise ConfigPersistenceError(f"Impossible de sauvegarder: {e}")

    def _create_backup(self, config_file: Path) -> Path:
        """Créer une sauvegarde de la configuration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{config_file.stem}_{timestamp}{config_file.suffix}"
        backup_path = self._backup_dir / backup_name

        shutil.copy2(config_file, backup_path)
        logger.debug(f"Backup créée: {backup_path}")

        # Nettoyer les anciennes backups (garder les 10 dernières)
        backups = sorted(self._backup_dir.glob(f"{config_file.stem}_*"))
        for old_backup in backups[:-10]:
            old_backup.unlink()
            logger.debug(f"Ancienne backup supprimée: {old_backup}")

        return backup_path

    def validate_config(self, config: SystemConfig) -> list[str]:
        """Valider une configuration"""
        return config.validate()

    async def apply_config(self, config: SystemConfig) -> bool:
        """Appliquer une configuration au système"""
        # Valider d'abord
        errors = self.validate_config(config)
        if errors:
            raise ConfigValidationError(
                "Configuration invalide",
                details={"errors": errors}
            )

        try:
            # Sauvegarder l'ancienne config pour rollback potentiel
            old_config = self._current_config

            # Appliquer les changements
            logger.info("Application de la nouvelle configuration...")

            # Mettre à jour la configuration courante
            self._current_config = config

            # Appliquer les paramètres système
            await self._apply_system_settings(config)

            # Sauvegarder
            self.save_config(config)

            logger.info("Configuration appliquée avec succès")
            return True

        except Exception as e:
            logger.error(f"Erreur application config: {e}")
            # Rollback
            if old_config:
                self._current_config = old_config
            raise

    async def _apply_system_settings(self, config: SystemConfig) -> None:
        """Appliquer les paramètres système"""
        import logging as log_module

        # Appliquer le niveau de log
        level = getattr(log_module, config.log_level.upper(), log_module.INFO)
        log_module.getLogger().setLevel(level)
        logger.info(f"Niveau de log défini à {config.log_level}")

        # Note: D'autres paramètres seraient appliqués ici
        # (GPU, monitoring, agents, etc.)

    def get_quick_start_config(
        self,
        gpu: bool = True,
        monitoring: bool = True,
        autoscale: bool = True
    ) -> SystemConfig:
        """Créer une configuration quick start"""
        return SystemConfig(
            gpu=GPUConfig(enabled=gpu),
            monitoring=MonitoringConfig(enabled=monitoring),
            max_concurrent_tasks=10 if autoscale else 5,
            log_level="INFO"
        )

    def update_config(self, updates: dict[str, Any]) -> SystemConfig:
        """Mettre à jour la configuration avec des valeurs partielles"""
        current = self.config
        new_config = current.merge_with(updates)

        # Valider
        errors = self.validate_config(new_config)
        if errors:
            raise ConfigValidationError(
                "Mise à jour invalide",
                details={"errors": errors}
            )

        self._current_config = new_config
        return new_config

    def reset_to_defaults(self) -> SystemConfig:
        """Réinitialiser à la configuration par défaut"""
        self._current_config = SystemConfig()
        return self._current_config

    def list_backups(self) -> list[dict[str, Any]]:
        """Lister les backups disponibles"""
        backups = []
        for backup_file in sorted(self._backup_dir.glob("*.json"), reverse=True):
            stat = backup_file.stat()
            backups.append({
                "name": backup_file.name,
                "path": str(backup_file),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        return backups

    def restore_backup(self, backup_name: str) -> SystemConfig:
        """Restaurer une configuration depuis une backup"""
        backup_path = self._backup_dir / backup_name

        if not backup_path.exists():
            raise ConfigPersistenceError(f"Backup introuvable: {backup_name}")

        # Charger et valider la backup
        config = self.load_config(backup_path)
        errors = self.validate_config(config)

        if errors:
            raise ConfigValidationError(
                "Backup invalide",
                details={"errors": errors}
            )

        # Sauvegarder la config actuelle puis restaurer
        self.save_config()  # Backup la config actuelle
        self._current_config = config
        self.save_config(create_backup=False)

        logger.info(f"Configuration restaurée depuis {backup_name}")
        return config


# ==============================================================================
# INSTANCE SINGLETON
# ==============================================================================

_config_service: ConfigService | None = None


def get_config_service() -> ConfigService:
    """Obtenir l'instance du service de configuration"""
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service
