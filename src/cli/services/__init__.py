"""
Tawiza-V2 CLI Services Layer

Ce module contient la couche de services qui sépare la logique métier
de l'interface utilisateur. Cela permet:
- Des tests unitaires sans UI
- La réutilisation de la logique dans différents contextes
- Une meilleure maintenabilité

Services disponibles:
- ConfigService: Gestion de la configuration système
- ValidationService: Validation des entrées utilisateur
- CacheService: Cache async avec TTL
- BackendService: Opérations backend unifiées avec circuit breaker
"""

from .backend_service import BackendService, ServiceResult, get_backend_service
from .cache_service import CacheEntry, CacheService
from .config_service import ConfigService, ConfigValidationError, SystemConfig
from .validation_service import InputValidator, PathValidator, ValidationService

__all__ = [
    # Configuration
    "ConfigService",
    "SystemConfig",
    "ConfigValidationError",
    # Validation
    "ValidationService",
    "PathValidator",
    "InputValidator",
    # Cache
    "CacheService",
    "CacheEntry",
    # Backend
    "BackendService",
    "ServiceResult",
    "get_backend_service",
]
