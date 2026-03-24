# tests/unit/ui/test_mascot_library.py
import pytest

from src.cli.ui.mascot_config import MascotStyle
from src.cli.ui.mascot_library import MascotLibrary, get_mascot_for_style


def test_kawaii_mascot():
    mascot = get_mascot_for_style(MascotStyle.KAWAII)
    assert "(=^" in mascot.happy
    assert "ω" in mascot.happy or "◡" in mascot.happy


def test_cyberpunk_mascot():
    mascot = get_mascot_for_style(MascotStyle.CYBERPUNK)
    assert "[" in mascot.happy  # Cyberpunk uses brackets


def test_all_emotions():
    mascot = get_mascot_for_style(MascotStyle.KAWAII)
    assert hasattr(mascot, "happy")
    assert hasattr(mascot, "sad")
    assert hasattr(mascot, "thinking")
    assert hasattr(mascot, "working")
    assert hasattr(mascot, "error")
    assert hasattr(mascot, "success")
