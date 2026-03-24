"""Authentication infrastructure for browser automation."""

from .credential_manager import (
    Credential,
    CredentialManager,
    get_credential_manager,
)

__all__ = [
    "CredentialManager",
    "Credential",
    "get_credential_manager",
]
