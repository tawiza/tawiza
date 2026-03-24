"""File operation tools for the unified agent."""

from pathlib import Path
from typing import Any

from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry


async def read_file(path: str) -> dict[str, Any]:
    """Read file content.

    Args:
        path: Path to the file to read

    Returns:
        Dict with success, content, and optional error
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return {"success": False, "error": f"File not found: {path}"}

        content = file_path.read_text()
        logger.debug(f"Read file: {path} ({len(content)} bytes)")

        return {"success": True, "content": content, "path": str(file_path)}
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        return {"success": False, "error": str(e)}


async def write_file(path: str, content: str) -> dict[str, Any]:
    """Write content to file.

    Args:
        path: Path to the file to write
        content: Content to write

    Returns:
        Dict with success and optional error
    """
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

        logger.debug(f"Wrote file: {path} ({len(content)} bytes)")

        return {"success": True, "path": str(file_path), "bytes_written": len(content)}
    except Exception as e:
        logger.error(f"Error writing file {path}: {e}")
        return {"success": False, "error": str(e)}


async def list_directory(path: str, pattern: str = "*") -> dict[str, Any]:
    """List directory contents.

    Args:
        path: Path to the directory to list
        pattern: Optional glob pattern (default: "*")

    Returns:
        Dict with success, files, directories, and optional error
    """
    try:
        dir_path = Path(path)
        if not dir_path.exists():
            return {"success": False, "error": f"Directory not found: {path}"}

        if not dir_path.is_dir():
            return {"success": False, "error": f"Not a directory: {path}"}

        files = []
        directories = []

        for item in dir_path.glob(pattern):
            if item.is_file():
                files.append(item.name)
            elif item.is_dir():
                directories.append(item.name)

        logger.debug(f"Listed directory: {path} ({len(files)} files, {len(directories)} dirs)")

        return {
            "success": True,
            "path": str(dir_path),
            "files": sorted(files),
            "directories": sorted(directories),
        }
    except Exception as e:
        logger.error(f"Error listing directory {path}: {e}")
        return {"success": False, "error": str(e)}


async def search_files(path: str, pattern: str, glob: str = "**/*") -> dict[str, Any]:
    """Search for pattern in files.

    Args:
        path: Path to the directory to search in
        pattern: Text pattern to search for
        glob: Glob pattern for file selection (default: "**/*")

    Returns:
        Dict with success, matches, and optional error
    """
    try:
        dir_path = Path(path)
        if not dir_path.exists():
            return {"success": False, "error": f"Directory not found: {path}"}

        matches = []

        for file_path in dir_path.glob(glob):
            if not file_path.is_file():
                continue

            try:
                content = file_path.read_text()
                if pattern in content:
                    # Find line numbers
                    lines = content.split("\n")
                    matching_lines = [
                        (i + 1, line) for i, line in enumerate(lines) if pattern in line
                    ]

                    matches.append(
                        {"file": str(file_path.relative_to(dir_path)), "lines": matching_lines}
                    )
            except (UnicodeDecodeError, PermissionError):
                # Skip binary files or files we can't read
                continue

        logger.debug(f"Searched files in {path}: {len(matches)} matches")

        return {"success": True, "path": str(dir_path), "pattern": pattern, "matches": matches}
    except Exception as e:
        logger.error(f"Error searching files in {path}: {e}")
        return {"success": False, "error": str(e)}


def register_file_tools(registry: ToolRegistry) -> None:
    """Register file tools with the registry.

    Args:
        registry: ToolRegistry instance to register tools with
    """
    # Manually add tools since registry.register is a decorator
    registry._tools["files.read"] = Tool(
        name="files.read",
        func=read_file,
        category=ToolCategory.FILES,
        description="Read content from a file",
    )

    registry._tools["files.write"] = Tool(
        name="files.write",
        func=write_file,
        category=ToolCategory.FILES,
        description="Write content to a file",
    )

    registry._tools["files.list"] = Tool(
        name="files.list",
        func=list_directory,
        category=ToolCategory.FILES,
        description="List contents of a directory",
    )

    registry._tools["files.search"] = Tool(
        name="files.search",
        func=search_files,
        category=ToolCategory.FILES,
        description="Search for pattern in files",
    )

    logger.debug("Registered 4 file tools")
