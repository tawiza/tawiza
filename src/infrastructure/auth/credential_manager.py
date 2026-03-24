"""Secure credential management for browser automation.

Handles storage and retrieval of login credentials with encryption.
Supports multiple authentication methods (form login, OAuth, API keys).
"""

import json
import os
from pathlib import Path

import keyring
from cryptography.fernet import Fernet
from loguru import logger
from pydantic import BaseModel, Field


class Credential(BaseModel):
    """Credential model for a website."""

    site_name: str = Field(..., description="Unique identifier for the site")
    url: str = Field(..., description="Base URL of the site")
    username: str | None = Field(None, description="Username/email")
    password: str | None = Field(None, description="Password")
    auth_type: str = Field("form", description="Authentication type: form, oauth, api_key")

    # Additional fields for different auth types
    api_key: str | None = Field(None, description="API key for API authentication")
    oauth_token: str | None = Field(None, description="OAuth token")
    cookies: dict[str, str] | None = Field(None, description="Session cookies")

    # Metadata
    notes: str | None = Field(None, description="Additional notes")
    tags: list[str] = Field(default_factory=list, description="Tags for organization")


class CredentialManager:
    """
    Secure credential manager with encryption.

    Features:
    - Encrypted storage using cryptography.Fernet
    - Optional system keyring integration
    - Support for multiple auth types
    - Credential rotation
    - Audit logging
    """

    def __init__(
        self,
        storage_path: Path | None = None,
        use_keyring: bool = True,
        encryption_key: bytes | None = None,
    ):
        """
        Initialize credential manager.

        Args:
            storage_path: Path to credentials file (default: ~/.tawiza/credentials.enc)
            use_keyring: Use system keyring for master key (recommended)
            encryption_key: Custom encryption key (not recommended, use keyring)
        """
        self.storage_path = storage_path or Path.home() / ".tawiza" / "credentials.enc"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self.use_keyring = use_keyring
        self._cipher = self._initialize_cipher(encryption_key)
        self._credentials: dict[str, Credential] = {}
        self._load_credentials()

        logger.info(f"Credential manager initialized (storage: {self.storage_path})")

    def _initialize_cipher(self, custom_key: bytes | None = None) -> Fernet:
        """Initialize Fernet cipher with encryption key."""
        if custom_key:
            return Fernet(custom_key)

        if self.use_keyring:
            try:
                # Try to get key from system keyring
                key_str = keyring.get_password("tawiza", "credential_encryption_key")

                if not key_str:
                    # Generate new key and store in keyring
                    key = Fernet.generate_key()
                    keyring.set_password("tawiza", "credential_encryption_key", key.decode())
                    logger.info("Generated new encryption key and stored in system keyring")
                    return Fernet(key)

                return Fernet(key_str.encode())
            except Exception as e:
                # Fallback if keyring is not available (server environment)
                logger.warning(f"Keyring not available: {e}. Using file-based fallback.")
                return self._get_fallback_cipher()

        return self._get_fallback_cipher()

    def _get_fallback_cipher(self) -> Fernet:
        """Get cipher from environment variable or file-based key storage."""
        # Try environment variable first
        key_env = os.environ.get("TAWIZA_CREDENTIAL_KEY")
        if key_env:
            return Fernet(key_env.encode())

        # Try file-based key storage
        key_file = self.storage_path.parent / ".encryption_key"
        if key_file.exists():
            try:
                key = key_file.read_text().strip().encode()
                return Fernet(key)
            except Exception as e:
                logger.warning(f"Failed to read key file: {e}")

        # Generate new key and save to file
        key = Fernet.generate_key()
        try:
            key_file.write_text(key.decode())
            key_file.chmod(0o600)  # Read/write only for owner
            logger.info(f"Generated new encryption key and stored in {key_file}")
        except Exception as e:
            logger.warning(f"Could not save key to file: {e}. Key will be temporary.")

        return Fernet(key)

    def _load_credentials(self):
        """Load and decrypt credentials from storage."""
        if not self.storage_path.exists():
            logger.debug("No credentials file found, starting with empty storage")
            return

        try:
            encrypted_data = self.storage_path.read_bytes()
            decrypted_data = self._cipher.decrypt(encrypted_data)
            credentials_dict = json.loads(decrypted_data.decode())

            self._credentials = {
                name: Credential(**cred_data) for name, cred_data in credentials_dict.items()
            }

            logger.info(f"Loaded {len(self._credentials)} credentials from storage")
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            raise

    def _save_credentials(self):
        """Encrypt and save credentials to storage."""
        try:
            credentials_dict = {name: cred.model_dump() for name, cred in self._credentials.items()}

            json_data = json.dumps(credentials_dict, indent=2)
            encrypted_data = self._cipher.encrypt(json_data.encode())

            self.storage_path.write_bytes(encrypted_data)
            logger.info(f"Saved {len(self._credentials)} credentials to storage")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            raise

    def add_credential(
        self,
        site_name: str,
        url: str,
        username: str | None = None,
        password: str | None = None,
        auth_type: str = "form",
        **kwargs,
    ) -> Credential:
        """
        Add or update a credential.

        Args:
            site_name: Unique identifier for the site
            url: Base URL
            username: Username/email
            password: Password
            auth_type: Authentication type (form, oauth, api_key)
            **kwargs: Additional fields (api_key, oauth_token, cookies, notes, tags)

        Returns:
            Created/updated Credential
        """
        credential = Credential(
            site_name=site_name,
            url=url,
            username=username,
            password=password,
            auth_type=auth_type,
            **kwargs,
        )

        self._credentials[site_name] = credential
        self._save_credentials()

        logger.info(f"Added credential for {site_name} ({auth_type})")
        return credential

    def get_credential(self, site_name: str) -> Credential | None:
        """
        Get credential by site name.

        Args:
            site_name: Site identifier

        Returns:
            Credential if found, None otherwise
        """
        return self._credentials.get(site_name)

    def remove_credential(self, site_name: str) -> bool:
        """
        Remove a credential.

        Args:
            site_name: Site identifier

        Returns:
            True if removed, False if not found
        """
        if site_name in self._credentials:
            del self._credentials[site_name]
            self._save_credentials()
            logger.info(f"Removed credential for {site_name}")
            return True

        logger.warning(f"Credential not found: {site_name}")
        return False

    def list_credentials(self, tag: str | None = None) -> list[str]:
        """
        List all credential names.

        Args:
            tag: Optional tag filter

        Returns:
            List of site names
        """
        if tag:
            return [name for name, cred in self._credentials.items() if tag in cred.tags]

        return list(self._credentials.keys())

    def get_all_credentials(self) -> dict[str, Credential]:
        """Get all credentials (for admin/debugging)."""
        return self._credentials.copy()

    def export_credentials(self, output_path: Path, include_passwords: bool = False):
        """
        Export credentials to JSON file.

        Args:
            output_path: Path to output JSON file
            include_passwords: Whether to include passwords (security risk)
        """
        credentials_export = {}

        for name, cred in self._credentials.items():
            cred_dict = cred.model_dump()

            if not include_passwords:
                # Redact sensitive fields
                cred_dict["password"] = "***REDACTED***" if cred_dict["password"] else None
                cred_dict["api_key"] = "***REDACTED***" if cred_dict.get("api_key") else None
                cred_dict["oauth_token"] = (
                    "***REDACTED***" if cred_dict.get("oauth_token") else None
                )

            credentials_export[name] = cred_dict

        output_path.write_text(json.dumps(credentials_export, indent=2))
        logger.info(f"Exported {len(credentials_export)} credentials to {output_path}")

    def import_credentials(self, input_path: Path, merge: bool = True):
        """
        Import credentials from JSON file.

        Args:
            input_path: Path to JSON file
            merge: If True, merge with existing; if False, replace all
        """
        import_data = json.loads(input_path.read_text())

        if not merge:
            self._credentials.clear()

        for name, cred_data in import_data.items():
            self._credentials[name] = Credential(**cred_data)

        self._save_credentials()
        logger.info(f"Imported {len(import_data)} credentials from {input_path}")


# Convenience function
def get_credential_manager() -> CredentialManager:
    """Get singleton instance of credential manager."""
    if not hasattr(get_credential_manager, "_instance"):
        get_credential_manager._instance = CredentialManager()

    return get_credential_manager._instance


if __name__ == "__main__":
    # Example usage - NEVER use real credentials in code!
    # All secrets should come from environment variables or secure storage
    import os

    manager = CredentialManager()

    # Add form-based authentication (credentials from env)
    github_user = os.environ.get("GITHUB_USER", "user@example.com")
    github_pass = os.environ.get("GITHUB_PASSWORD")
    if github_pass:
        manager.add_credential(
            site_name="github",
            url="https://github.com",
            username=github_user,
            password=github_pass,
            auth_type="form",
            tags=["dev", "code"],
        )

    # Add API key authentication (from env)
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        manager.add_credential(
            site_name="openai",
            url="https://api.openai.com",
            auth_type="api_key",
            api_key=openai_key,
            tags=["api", "llm"],
        )

    # Retrieve credential
    github_cred = manager.get_credential("github")
    if github_cred:
        print(f"GitHub credential: {github_cred.username}")

    # List all
    print(f"All credentials: {manager.list_credentials()}")

    # Export (without passwords for safety)
    manager.export_credentials(Path("credentials_backup.json"), include_passwords=False)
