"""Tests for file tools."""

from pathlib import Path

import pytest

from src.cli.v2.agents.tools.file_tools import register_file_tools
from src.cli.v2.agents.unified.tools import ToolRegistry


class TestFileTools:
    @pytest.fixture
    def registry(self):
        reg = ToolRegistry()
        register_file_tools(reg)
        return reg

    @pytest.mark.asyncio
    async def test_files_read(self, registry, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = await registry.execute("files.read", {"path": str(test_file)})
        assert result["content"] == "Hello, World!"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_files_read_not_found(self, registry, tmp_path):
        result = await registry.execute("files.read", {"path": str(tmp_path / "nonexistent.txt")})
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_files_write(self, registry, tmp_path):
        test_file = tmp_path / "output.txt"

        result = await registry.execute(
            "files.write", {"path": str(test_file), "content": "Test content"}
        )

        assert result["success"] is True
        assert test_file.read_text() == "Test content"

    @pytest.mark.asyncio
    async def test_files_list(self, registry, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        (tmp_path / "subdir").mkdir()

        result = await registry.execute("files.list", {"path": str(tmp_path)})
        assert result["success"] is True
        assert "a.txt" in result["files"]
        assert "b.txt" in result["files"]
        assert "subdir" in result["directories"]
