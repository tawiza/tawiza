#!/usr/bin/env python3
"""
Module de gestion d'erreurs pour Tawiza-V2 CLI

Fournit:
- Hiérarchie d'exceptions structurée
- Error handlers avec formatting Rich
- Retry decorators
- Logging intégré
"""
from __future__ import annotations

import functools
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, TypeVar

from loguru import logger
from rich import box
from rich.console import Console
from rich.table import Table

console = Console()

T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


# ==============================================================================
# ERROR CODES
# ==============================================================================

class ErrorCode(StrEnum):
    """Codes d'erreur standardisés"""
    # General (1000-1099)
    UNKNOWN = "E1000"
    INVALID_INPUT = "E1001"
    OPERATION_CANCELLED = "E1002"
    TIMEOUT = "E1003"

    # Configuration (1100-1199)
    CONFIG_LOAD_FAILED = "E1100"
    CONFIG_SAVE_FAILED = "E1101"
    CONFIG_VALIDATION_FAILED = "E1102"
    CONFIG_NOT_FOUND = "E1103"

    # System (1200-1299)
    SYSTEM_NOT_INITIALIZED = "E1200"
    SYSTEM_ALREADY_INITIALIZED = "E1201"
    SYSTEM_INIT_FAILED = "E1202"
    INSUFFICIENT_RESOURCES = "E1203"

    # GPU (1300-1399)
    GPU_NOT_AVAILABLE = "E1300"
    GPU_DRIVER_ERROR = "E1301"
    GPU_MEMORY_ERROR = "E1302"

    # Network (1400-1499)
    CONNECTION_FAILED = "E1400"
    SERVICE_UNAVAILABLE = "E1401"
    API_ERROR = "E1402"

    # Agents (1500-1599)
    AGENT_START_FAILED = "E1500"
    AGENT_STOP_FAILED = "E1501"
    AGENT_TASK_FAILED = "E1502"
    AGENT_NOT_FOUND = "E1503"

    # Models (1600-1699)
    MODEL_NOT_FOUND = "E1600"
    MODEL_LOAD_FAILED = "E1601"
    INFERENCE_FAILED = "E1602"

    # Files (1700-1799)
    FILE_NOT_FOUND = "E1700"
    FILE_READ_ERROR = "E1701"
    FILE_WRITE_ERROR = "E1702"
    PATH_TRAVERSAL = "E1703"
    INVALID_PATH = "E1704"


# ==============================================================================
# SEVERITY LEVELS
# ==============================================================================

class ErrorSeverity(StrEnum):
    """Niveaux de sévérité des erreurs"""
    LOW = "low"          # Avertissement, continue
    MEDIUM = "medium"    # Erreur, peut continuer
    HIGH = "high"        # Erreur critique, arrêt recommandé
    CRITICAL = "critical"  # Erreur fatale, arrêt nécessaire


# ==============================================================================
# ERROR INFO
# ==============================================================================

@dataclass
class ErrorInfo:
    """Informations structurées sur une erreur"""
    code: ErrorCode
    message: str
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    details: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    exception: Exception | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convertir en dictionnaire"""
        return {
            "code": self.code.value,
            "message": self.message,
            "severity": self.severity.value,
            "details": self.details,
            "suggestions": self.suggestions,
            "timestamp": self.timestamp.isoformat(),
        }


# ==============================================================================
# EXCEPTION HIERARCHY
# ==============================================================================

class TawizaError(Exception):
    """Exception de base pour Tawiza-V2"""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ):
        super().__init__(message)
        self.info = ErrorInfo(
            code=code,
            message=message,
            severity=severity,
            details=details or {},
            suggestions=suggestions or [],
            exception=self,
        )

    @property
    def code(self) -> ErrorCode:
        return self.info.code

    @property
    def severity(self) -> ErrorSeverity:
        return self.info.severity


# Configuration errors
class ConfigError(TawizaError):
    """Erreur de configuration"""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.CONFIG_VALIDATION_FAILED, **kwargs):
        super().__init__(message, code=code, **kwargs)


class ConfigNotFoundError(ConfigError):
    """Configuration introuvable"""
    def __init__(self, path: str):
        super().__init__(
            f"Configuration non trouvée: {path}",
            code=ErrorCode.CONFIG_NOT_FOUND,
            suggestions=["Exécutez 'tawiza system init' pour créer la configuration"]
        )


# System errors
class SystemError(TawizaError):
    """Erreur système"""
    pass


class SystemNotInitializedError(SystemError):
    """Système non initialisé"""
    def __init__(self):
        super().__init__(
            "Le système n'est pas initialisé",
            code=ErrorCode.SYSTEM_NOT_INITIALIZED,
            severity=ErrorSeverity.HIGH,
            suggestions=["Exécutez 'tawiza system init' d'abord"]
        )


class SystemAlreadyInitializedError(SystemError):
    """Système déjà initialisé"""
    def __init__(self):
        super().__init__(
            "Le système est déjà initialisé",
            code=ErrorCode.SYSTEM_ALREADY_INITIALIZED,
            suggestions=["Utilisez --force pour réinitialiser"]
        )


# GPU errors
class GPUError(TawizaError):
    """Erreur GPU"""
    pass


class GPUNotAvailableError(GPUError):
    """GPU non disponible"""
    def __init__(self, reason: str = ""):
        super().__init__(
            f"Aucun GPU détecté{': ' + reason if reason else ''}",
            code=ErrorCode.GPU_NOT_AVAILABLE,
            suggestions=[
                "Vérifiez que les drivers ROCm ou CUDA sont installés",
                "Utilisez 'rocm-smi' ou 'nvidia-smi' pour diagnostiquer"
            ]
        )


# Network errors
class NetworkError(TawizaError):
    """Erreur réseau"""
    pass


class ServiceUnavailableError(NetworkError):
    """Service non disponible"""
    def __init__(self, service: str, url: str):
        super().__init__(
            f"Service '{service}' non disponible à {url}",
            code=ErrorCode.SERVICE_UNAVAILABLE,
            details={"service": service, "url": url},
            suggestions=[
                f"Vérifiez que {service} est démarré",
                f"Testez la connectivité avec 'curl {url}'"
            ]
        )


class ConnectionError(NetworkError):
    """Erreur de connexion"""
    def __init__(self, url: str, reason: str = ""):
        super().__init__(
            f"Impossible de se connecter à {url}{': ' + reason if reason else ''}",
            code=ErrorCode.CONNECTION_FAILED,
            details={"url": url, "reason": reason}
        )


# Agent errors
class AgentError(TawizaError):
    """Erreur d'agent"""
    pass


class AgentNotFoundError(AgentError):
    """Agent non trouvé"""
    def __init__(self, agent_name: str):
        super().__init__(
            f"Agent '{agent_name}' non trouvé",
            code=ErrorCode.AGENT_NOT_FOUND,
            details={"agent": agent_name},
            suggestions=["Listez les agents disponibles avec 'tawiza agents list'"]
        )


# File errors
class FileError(TawizaError):
    """Erreur de fichier"""
    pass


class PathTraversalError(FileError):
    """Tentative de path traversal"""
    def __init__(self, path: str):
        super().__init__(
            "Path traversal détecté - accès non autorisé",
            code=ErrorCode.PATH_TRAVERSAL,
            severity=ErrorSeverity.HIGH,
            details={"attempted_path": path}
        )


class InvalidPathError(FileError):
    """Chemin invalide"""
    def __init__(self, path: str, reason: str = ""):
        super().__init__(
            f"Chemin invalide: {path}{': ' + reason if reason else ''}",
            code=ErrorCode.INVALID_PATH,
            details={"path": path, "reason": reason}
        )


# ==============================================================================
# ERROR HANDLER
# ==============================================================================

class ErrorHandler:
    """Gestionnaire d'erreurs centralisé"""

    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self._error_history: list[ErrorInfo] = []

    def handle(
        self,
        error: Exception | ErrorInfo,
        show_traceback: bool = False,
        exit_on_critical: bool = True
    ) -> None:
        """Gérer une erreur"""
        if isinstance(error, ErrorInfo):
            info = error
        elif isinstance(error, TawizaError):
            info = error.info
        else:
            info = ErrorInfo(
                code=ErrorCode.UNKNOWN,
                message=str(error),
                exception=error
            )

        # Log l'erreur
        self._log_error(info)

        # Ajouter à l'historique
        self._error_history.append(info)

        # Afficher
        self._display_error(info, show_traceback)

        # Exit si critique
        if exit_on_critical and info.severity == ErrorSeverity.CRITICAL:
            sys.exit(1)

    def _log_error(self, info: ErrorInfo) -> None:
        """Logger l'erreur"""
        log_level = {
            ErrorSeverity.LOW: logging.WARNING,
            ErrorSeverity.MEDIUM: logging.ERROR,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
        }.get(info.severity, logging.ERROR)

        logger.log(
            log_level,
            f"[{info.code.value}] {info.message}",
            extra={"error_info": info.to_dict()}
        )

    def _display_error(self, info: ErrorInfo, show_traceback: bool) -> None:
        """Afficher l'erreur de manière formatée"""
        # Couleur selon sévérité
        color = {
            ErrorSeverity.LOW: "yellow",
            ErrorSeverity.MEDIUM: "red",
            ErrorSeverity.HIGH: "bold red",
            ErrorSeverity.CRITICAL: "bold white on red",
        }.get(info.severity, "red")

        # Icône selon sévérité
        icon = {
            ErrorSeverity.LOW: "⚠️",
            ErrorSeverity.MEDIUM: "❌",
            ErrorSeverity.HIGH: "🚫",
            ErrorSeverity.CRITICAL: "💀",
        }.get(info.severity, "❌")

        # Message principal
        self.console.print(
            f"\n[{color}]{icon} [{info.code.value}] {info.message}[/{color}]"
        )

        # Détails si présents
        if info.details:
            details_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
            for key, value in info.details.items():
                details_table.add_row(f"[dim]{key}:[/dim]", str(value))
            self.console.print(details_table)

        # Suggestions
        if info.suggestions:
            self.console.print("\n[bold]💡 Suggestions:[/bold]")
            for suggestion in info.suggestions:
                self.console.print(f"   • {suggestion}")

        # Traceback si demandé
        if show_traceback and info.exception:
            self.console.print("\n[dim]Traceback:[/dim]")
            self.console.print_exception()

    def get_history(self) -> list[ErrorInfo]:
        """Obtenir l'historique des erreurs"""
        return self._error_history.copy()

    def clear_history(self) -> None:
        """Vider l'historique"""
        self._error_history.clear()


# ==============================================================================
# DECORATORS
# ==============================================================================

def handle_errors(
    *exception_types: type[Exception],
    default_code: ErrorCode = ErrorCode.UNKNOWN,
    reraise: bool = False,
    show_traceback: bool = False
) -> Callable[[F], F]:
    """Décorateur pour gérer automatiquement les erreurs"""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except TawizaError:
                if reraise:
                    raise
                handler = ErrorHandler()
                handler.handle(sys.exc_info()[1], show_traceback=show_traceback)
            except exception_types as e:
                if reraise:
                    raise
                error = TawizaError(str(e), code=default_code)
                error.info.exception = e
                handler = ErrorHandler()
                handler.handle(error.info, show_traceback=show_traceback)
            except Exception:
                if reraise:
                    raise
                handler = ErrorHandler()
                handler.handle(sys.exc_info()[1], show_traceback=show_traceback)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except TawizaError:
                if reraise:
                    raise
                handler = ErrorHandler()
                handler.handle(sys.exc_info()[1], show_traceback=show_traceback)
            except exception_types as e:
                if reraise:
                    raise
                error = TawizaError(str(e), code=default_code)
                error.info.exception = e
                handler = ErrorHandler()
                handler.handle(error.info, show_traceback=show_traceback)
            except Exception:
                if reraise:
                    raise
                handler = ErrorHandler()
                handler.handle(sys.exc_info()[1], show_traceback=show_traceback)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,)
) -> Callable[[F], F]:
    """Décorateur pour retry automatique avec backoff"""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import time
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait = delay * (backoff ** attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {wait:.1f}s: {e}"
                        )
                        time.sleep(wait)

            raise last_exception  # type: ignore

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            import asyncio
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        wait = delay * (backoff ** attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                            f"after {wait:.1f}s: {e}"
                        )
                        await asyncio.sleep(wait)

            raise last_exception  # type: ignore

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return wrapper  # type: ignore

    return decorator


# ==============================================================================
# GLOBAL HANDLER
# ==============================================================================

_error_handler: ErrorHandler | None = None


def get_error_handler() -> ErrorHandler:
    """Obtenir le gestionnaire d'erreurs global"""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler
