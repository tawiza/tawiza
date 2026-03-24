#!/usr/bin/env python3
"""Fixed entry point for Tawiza CLI that properly handles imports."""

import sys
from pathlib import Path


def main():
    """Main entry point with proper path setup."""
    # Add the project root to Python path
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Import and run the app
    from src.cli.main import app

    app()


if __name__ == "__main__":
    main()
