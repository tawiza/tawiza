"""Directory management service implementation.

This service handles creation and verification of application directories.

Follows Single Responsibility Principle: Only handles directory operations.
"""

from pathlib import Path

from loguru import logger

from src.core.constants import DIRS_TO_CREATE


class DirectoryManagerService:
    """Concrete implementation of directory management.

    This service manages application directory structure without
    affecting other parts of the system.
    """

    def __init__(self, base_path: Path = None):
        """Initialize directory manager.

        Args:
            base_path: Base path for all directories (defaults to current dir)
        """
        self.base_path = base_path or Path.cwd()

    def create_required_directories(self, directories: list[str] = None) -> None:
        """Create all required directories.

        Args:
            directories: List of directory paths to create
                        (defaults to DIRS_TO_CREATE constant)

        Raises:
            OSError: If directory creation fails
        """
        dirs_to_create = directories or DIRS_TO_CREATE

        for directory in dirs_to_create:
            dir_path = self.base_path / directory

            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Directory created/verified: {dir_path}")

            except OSError as e:
                logger.error(f"Failed to create directory {dir_path}: {e}")
                raise

    def verify_directory_structure(self, directories: list[str] = None) -> bool:
        """Verify all required directories exist.

        Args:
            directories: List of directories to verify
                        (defaults to DIRS_TO_CREATE constant)

        Returns:
            True if all directories exist
        """
        dirs_to_verify = directories or DIRS_TO_CREATE

        all_exist = True
        for directory in dirs_to_verify:
            dir_path = self.base_path / directory

            if not dir_path.exists():
                logger.warning(f"Directory missing: {dir_path}")
                all_exist = False
            elif not dir_path.is_dir():
                logger.error(f"Path exists but is not a directory: {dir_path}")
                all_exist = False

        return all_exist

    def get_directory_status(self, directories: list[str] = None) -> dict[str, bool]:
        """Get existence status of all directories.

        Args:
            directories: List of directories to check
                        (defaults to DIRS_TO_CREATE constant)

        Returns:
            Dictionary mapping directory names to existence status
        """
        dirs_to_check = directories or DIRS_TO_CREATE

        status = {}
        for directory in dirs_to_check:
            dir_path = self.base_path / directory
            status[directory] = dir_path.exists() and dir_path.is_dir()

        return status

    def ensure_directory_exists(self, directory: str) -> Path:
        """Ensure a single directory exists, create if needed.

        Args:
            directory: Directory path

        Returns:
            Path object for the directory

        Raises:
            OSError: If creation fails
        """
        dir_path = self.base_path / directory

        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            return dir_path

        except OSError as e:
            logger.error(f"Failed to ensure directory {dir_path}: {e}")
            raise

    def clean_directory(self, directory: str, confirm: bool = False) -> None:
        """Clean (delete contents of) a directory.

        Args:
            directory: Directory to clean
            confirm: Must be True to actually delete

        Raises:
            ValueError: If confirm is False
            OSError: If deletion fails
        """
        if not confirm:
            raise ValueError("Must pass confirm=True to delete directory contents")

        dir_path = self.base_path / directory

        if not dir_path.exists():
            logger.warning(f"Directory does not exist: {dir_path}")
            return

        try:
            import shutil

            shutil.rmtree(dir_path)
            dir_path.mkdir(parents=True)
            logger.info(f"Directory cleaned: {dir_path}")

        except OSError as e:
            logger.error(f"Failed to clean directory {dir_path}: {e}")
            raise
