#!/usr/bin/env python3
"""
Service de validation pour Tawiza-V2 CLI

Fournit des validateurs sécurisés pour:
- Chemins de fichiers (prévention path traversal)
- Entrées numériques (bounds checking, overflow protection)
- Chaînes de caractères (longueur, caractères autorisés)
- URLs et adresses
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from loguru import logger

# ==============================================================================
# CONSTANTES DE VALIDATION
# ==============================================================================

# Limites par défaut
DEFAULT_MIN_INT = 1
DEFAULT_MAX_INT = 10000
DEFAULT_MAX_STRING_LENGTH = 1000
DEFAULT_MAX_PATH_LENGTH = 4096

# Patterns autorisés
SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
SAFE_PATH_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-./\\:')

# Extensions de fichiers dangereuses
DANGEROUS_EXTENSIONS: set[str] = {
    '.exe', '.bat', '.cmd', '.com', '.msi', '.scr',
    '.vbs', '.vbe', '.js', '.jse', '.ws', '.wsf',
    '.sh', '.bash', '.zsh', '.ps1', '.psm1'
}

# Répertoires protégés
PROTECTED_PATHS: set[str] = {
    '/etc', '/bin', '/sbin', '/usr/bin', '/usr/sbin',
    '/root', '/var/log', '/var/run', '/boot',
    'C:\\Windows', 'C:\\Program Files'
}


# ==============================================================================
# EXCEPTIONS
# ==============================================================================

class ValidationError(Exception):
    """Exception de base pour les erreurs de validation"""

    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(message)


class PathValidationError(ValidationError):
    """Erreur de validation de chemin"""
    pass


class IntegerValidationError(ValidationError):
    """Erreur de validation d'entier"""
    pass


class StringValidationError(ValidationError):
    """Erreur de validation de chaîne"""
    pass


# ==============================================================================
# RÉSULTATS DE VALIDATION
# ==============================================================================

@dataclass
class ValidationResult:
    """Résultat d'une validation"""
    is_valid: bool
    value: Any = None
    error: str | None = None
    sanitized_value: Any = None

    @classmethod
    def success(cls, value: Any, sanitized: Any = None) -> ValidationResult:
        """Créer un résultat de succès"""
        return cls(is_valid=True, value=value, sanitized_value=sanitized or value)

    @classmethod
    def failure(cls, error: str) -> ValidationResult:
        """Créer un résultat d'échec"""
        return cls(is_valid=False, error=error)


# ==============================================================================
# VALIDATEURS DE CHEMINS
# ==============================================================================

class PathValidator:
    """Validateur de chemins de fichiers sécurisé"""

    def __init__(
        self,
        allowed_directories: list[Path] | None = None,
        allow_absolute: bool = True,
        allow_relative: bool = True,
        max_length: int = DEFAULT_MAX_PATH_LENGTH,
        allowed_extensions: set[str] | None = None,
        blocked_extensions: set[str] | None = None
    ):
        self.allowed_directories = allowed_directories or self._default_allowed_dirs()
        self.allow_absolute = allow_absolute
        self.allow_relative = allow_relative
        self.max_length = max_length
        self.allowed_extensions = allowed_extensions
        self.blocked_extensions = blocked_extensions or DANGEROUS_EXTENSIONS

    @staticmethod
    def _default_allowed_dirs() -> list[Path]:
        """Répertoires autorisés par défaut"""
        from src.cli.constants import PROJECT_ROOT
        return [
            Path.cwd(),
            Path.home(),
            Path("/tmp"),
            PROJECT_ROOT,
            PROJECT_ROOT / "data",
            PROJECT_ROOT / "configs",
            PROJECT_ROOT / "output",
        ]

    def validate(self, path_str: str) -> ValidationResult:
        """Valider un chemin de fichier"""
        # Vérifications de base
        if not path_str:
            return ValidationResult.failure("Le chemin ne peut pas être vide")

        if len(path_str) > self.max_length:
            return ValidationResult.failure(f"Chemin trop long (max {self.max_length} caractères)")

        # Nettoyer le chemin
        try:
            path_str = path_str.strip()
            # Supprimer les caractères nuls et de contrôle
            path_str = ''.join(c for c in path_str if c.isprintable() or c in '/\\')
        except Exception as e:
            return ValidationResult.failure(f"Erreur de nettoyage du chemin: {e}")

        # Vérifier les caractères dangereux
        if '..' in path_str:
            # Vérifier si c'est un path traversal
            try:
                resolved = Path(path_str).resolve()
                if not self._is_within_allowed(resolved):
                    return ValidationResult.failure(
                        "Path traversal détecté: le chemin sort des répertoires autorisés"
                    )
            except Exception:
                return ValidationResult.failure("Chemin invalide avec séquence '..'")

        try:
            path = Path(path_str)

            # Vérifier absolu/relatif
            if path.is_absolute() and not self.allow_absolute:
                return ValidationResult.failure("Les chemins absolus ne sont pas autorisés")

            if not path.is_absolute() and not self.allow_relative:
                return ValidationResult.failure("Les chemins relatifs ne sont pas autorisés")

            # Résoudre le chemin
            resolved_path = path.resolve()

            # Vérifier l'extension
            ext = resolved_path.suffix.lower()
            if ext and self.blocked_extensions and ext in self.blocked_extensions:
                return ValidationResult.failure(f"Extension de fichier bloquée: {ext}")

            if self.allowed_extensions and ext not in self.allowed_extensions:
                return ValidationResult.failure(
                    f"Extension non autorisée. Extensions valides: {', '.join(self.allowed_extensions)}"
                )

            # Vérifier si dans les répertoires autorisés
            if not self._is_within_allowed(resolved_path):
                return ValidationResult.failure(
                    "Le chemin n'est pas dans un répertoire autorisé"
                )

            # Vérifier les chemins protégés
            if self._is_protected(resolved_path):
                return ValidationResult.failure(
                    "Accès interdit: répertoire système protégé"
                )

            return ValidationResult.success(str(path), str(resolved_path))

        except Exception as e:
            logger.warning(f"Erreur validation chemin '{path_str}': {e}")
            return ValidationResult.failure(f"Chemin invalide: {e}")

    def _is_within_allowed(self, path: Path) -> bool:
        """Vérifier si le chemin est dans un répertoire autorisé"""
        path_str = str(path.resolve())
        return any(
            path_str.startswith(str(allowed.resolve()))
            for allowed in self.allowed_directories
        )

    def _is_protected(self, path: Path) -> bool:
        """Vérifier si le chemin est protégé"""
        path_str = str(path)
        return any(
            path_str.startswith(protected)
            for protected in PROTECTED_PATHS
        )

    def validate_exists(self, path_str: str, must_be_file: bool = False, must_be_dir: bool = False) -> ValidationResult:
        """Valider qu'un chemin existe"""
        result = self.validate(path_str)
        if not result.is_valid:
            return result

        path = Path(result.sanitized_value)

        if not path.exists():
            return ValidationResult.failure(f"Le chemin n'existe pas: {path}")

        if must_be_file and not path.is_file():
            return ValidationResult.failure(f"'{path}' n'est pas un fichier")

        if must_be_dir and not path.is_dir():
            return ValidationResult.failure(f"'{path}' n'est pas un répertoire")

        return result


# ==============================================================================
# VALIDATEURS D'ENTRÉES
# ==============================================================================

class InputValidator:
    """Validateur d'entrées génériques"""

    @staticmethod
    def validate_integer(
        value: str,
        min_value: int = DEFAULT_MIN_INT,
        max_value: int = DEFAULT_MAX_INT,
        field_name: str = "valeur"
    ) -> ValidationResult:
        """Valider un entier avec bounds checking"""
        if not value:
            return ValidationResult.failure(f"{field_name} ne peut pas être vide")

        # Nettoyer
        value = value.strip()

        # Vérifier le format
        if not value.lstrip('-').isdigit():
            return ValidationResult.failure(f"{field_name} doit être un nombre entier")

        try:
            # Conversion avec protection overflow
            num = int(value)

            if num < min_value:
                return ValidationResult.failure(
                    f"{field_name} doit être >= {min_value} (reçu: {num})"
                )

            if num > max_value:
                return ValidationResult.failure(
                    f"{field_name} doit être <= {max_value} (reçu: {num})"
                )

            return ValidationResult.success(num)

        except (ValueError, OverflowError) as e:
            return ValidationResult.failure(f"{field_name} invalide: {e}")

    @staticmethod
    def validate_float(
        value: str,
        min_value: float = 0.0,
        max_value: float = float('inf'),
        field_name: str = "valeur"
    ) -> ValidationResult:
        """Valider un nombre flottant"""
        if not value:
            return ValidationResult.failure(f"{field_name} ne peut pas être vide")

        value = value.strip()

        try:
            num = float(value)

            if num < min_value or num > max_value:
                return ValidationResult.failure(
                    f"{field_name} doit être entre {min_value} et {max_value}"
                )

            return ValidationResult.success(num)

        except (ValueError, OverflowError) as e:
            return ValidationResult.failure(f"{field_name} invalide: {e}")

    @staticmethod
    def validate_string(
        value: str,
        min_length: int = 0,
        max_length: int = DEFAULT_MAX_STRING_LENGTH,
        pattern: re.Pattern | None = None,
        allowed_chars: str | None = None,
        field_name: str = "valeur"
    ) -> ValidationResult:
        """Valider une chaîne de caractères"""
        if value is None:
            return ValidationResult.failure(f"{field_name} ne peut pas être null")

        # Nettoyer les caractères de contrôle
        cleaned = ''.join(c for c in value if c.isprintable() or c in '\n\t')

        if len(cleaned) < min_length:
            return ValidationResult.failure(
                f"{field_name} doit faire au moins {min_length} caractères"
            )

        if len(cleaned) > max_length:
            return ValidationResult.failure(
                f"{field_name} ne peut pas dépasser {max_length} caractères"
            )

        if allowed_chars:
            invalid_chars = set(cleaned) - set(allowed_chars)
            if invalid_chars:
                return ValidationResult.failure(
                    f"Caractères non autorisés dans {field_name}: {invalid_chars}"
                )

        if pattern and not pattern.match(cleaned):
            return ValidationResult.failure(
                f"{field_name} ne correspond pas au format attendu"
            )

        return ValidationResult.success(value, cleaned)

    @staticmethod
    def validate_choice(
        value: str,
        choices: list[str],
        case_sensitive: bool = False,
        field_name: str = "valeur"
    ) -> ValidationResult:
        """Valider qu'une valeur est dans une liste de choix"""
        if not value:
            return ValidationResult.failure(f"{field_name} ne peut pas être vide")

        value_check = value if case_sensitive else value.lower()
        choices_check = choices if case_sensitive else [c.lower() for c in choices]

        if value_check not in choices_check:
            return ValidationResult.failure(
                f"{field_name} invalide. Choix valides: {', '.join(choices)}"
            )

        # Retourner la valeur originale de la liste si correspondance insensible
        if not case_sensitive:
            for i, c in enumerate(choices_check):
                if c == value_check:
                    return ValidationResult.success(choices[i])

        return ValidationResult.success(value)

    @staticmethod
    def validate_url(value: str, require_https: bool = False) -> ValidationResult:
        """Valider une URL"""
        if not value:
            return ValidationResult.failure("URL ne peut pas être vide")

        try:
            parsed = urlparse(value)

            if not parsed.scheme:
                return ValidationResult.failure("URL doit avoir un schéma (http/https)")

            if require_https and parsed.scheme != 'https':
                return ValidationResult.failure("URL doit utiliser HTTPS")

            if parsed.scheme not in ('http', 'https'):
                return ValidationResult.failure("Schéma URL invalide")

            if not parsed.netloc:
                return ValidationResult.failure("URL doit avoir un domaine")

            return ValidationResult.success(value, parsed.geturl())

        except Exception as e:
            return ValidationResult.failure(f"URL invalide: {e}")

    @staticmethod
    def validate_email(value: str) -> ValidationResult:
        """Valider une adresse email"""
        if not value:
            return ValidationResult.failure("Email ne peut pas être vide")

        # Pattern email simple mais efficace
        email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )

        if not email_pattern.match(value):
            return ValidationResult.failure("Format email invalide")

        return ValidationResult.success(value.lower())


# ==============================================================================
# SERVICE DE VALIDATION PRINCIPAL
# ==============================================================================

class ValidationService:
    """Service centralisé de validation"""

    def __init__(self):
        self._path_validator = PathValidator()
        self._input_validator = InputValidator()

    @property
    def path(self) -> PathValidator:
        """Accès au validateur de chemins"""
        return self._path_validator

    @property
    def input(self) -> InputValidator:
        """Accès au validateur d'entrées"""
        return self._input_validator

    def create_path_validator(self, **kwargs) -> PathValidator:
        """Créer un validateur de chemins personnalisé"""
        return PathValidator(**kwargs)

    # Méthodes utilitaires de haut niveau

    def validate_dataset_path(self, path: str) -> ValidationResult:
        """Valider un chemin de dataset"""
        validator = PathValidator(
            allowed_extensions={'.csv', '.json', '.jsonl', '.parquet', '.xlsx', '.tsv'},
            blocked_extensions=DANGEROUS_EXTENSIONS
        )
        return validator.validate_exists(path, must_be_file=True)

    def validate_output_path(self, path: str) -> ValidationResult:
        """Valider un chemin de sortie"""
        validator = PathValidator(
            allowed_extensions={'.json', '.html', '.pdf', '.md', '.txt', '.csv'}
        )
        result = validator.validate(path)

        if result.is_valid:
            # Vérifier que le répertoire parent existe
            parent = Path(result.sanitized_value).parent
            if not parent.exists():
                return ValidationResult.failure(
                    f"Répertoire parent n'existe pas: {parent}"
                )

        return result

    def validate_model_name(self, name: str) -> ValidationResult:
        """Valider un nom de modèle"""
        return self._input_validator.validate_string(
            name,
            min_length=1,
            max_length=100,
            pattern=re.compile(r'^[a-zA-Z0-9_\-:\.]+$'),
            field_name="nom du modèle"
        )

    def validate_max_tasks(self, value: str) -> ValidationResult:
        """Valider le nombre max de tâches concurrentes"""
        return self._input_validator.validate_integer(
            value,
            min_value=1,
            max_value=100,
            field_name="nombre de tâches"
        )

    def validate_epochs(self, value: str) -> ValidationResult:
        """Valider le nombre d'époques d'entraînement"""
        return self._input_validator.validate_integer(
            value,
            min_value=1,
            max_value=1000,
            field_name="nombre d'époques"
        )

    def validate_batch_size(self, value: str) -> ValidationResult:
        """Valider la taille du batch"""
        return self._input_validator.validate_integer(
            value,
            min_value=1,
            max_value=512,
            field_name="batch size"
        )

    def validate_learning_rate(self, value: str) -> ValidationResult:
        """Valider le learning rate"""
        result = self._input_validator.validate_float(
            value,
            min_value=1e-8,
            max_value=1.0,
            field_name="learning rate"
        )

        if result.is_valid and result.value > 0.1:
            # Warning pour valeur élevée
            logger.warning(f"Learning rate élevé: {result.value}")

        return result

    def validate_log_level(self, value: str) -> ValidationResult:
        """Valider le niveau de log"""
        return self._input_validator.validate_choice(
            value,
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            case_sensitive=False,
            field_name="niveau de log"
        )


# Instance singleton du service
_validation_service: ValidationService | None = None


def get_validation_service() -> ValidationService:
    """Obtenir l'instance du service de validation"""
    global _validation_service
    if _validation_service is None:
        _validation_service = ValidationService()
    return _validation_service
