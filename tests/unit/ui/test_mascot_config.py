# tests/unit/ui/test_mascot_config.py
import pytest

from src.cli.ui.mascot_config import MascotConfig, MascotStyle


def test_default_mascot_config():
    config = MascotConfig()
    assert config.style == MascotStyle.KAWAII
    assert config.name == "Neko"
    assert config.color == "magenta"


def test_load_custom_config(tmp_path):
    config_file = tmp_path / "mascot.yaml"
    config_file.write_text("""
style: cyberpunk
name: CyberCat
color: cyan
animations: true
""")
    config = MascotConfig.load(config_file)
    assert config.style == MascotStyle.CYBERPUNK
    assert config.name == "CyberCat"
