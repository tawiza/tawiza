"""Tests for FranceMapPNG widget."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli.v3.tui.widgets.france_map_png import (
    GROWTH_COLORS,
    DepartmentData,
    FranceMapPNG,
    MapConfig,
)


class TestMapConfig:
    """Test MapConfig dataclass."""

    def test_default_values(self):
        """MapConfig has sensible default values."""
        config = MapConfig()
        assert config.width == 800
        assert config.height == 600
        assert config.dpi == 100
        assert config.background_color == "#FFFFFF"
        assert config.edge_color == "#000000"
        assert config.edge_width == 0.5
        assert config.colormap_colors == list(GROWTH_COLORS.values())
        assert config.vmin == -0.3
        assert config.vmax == 0.4

    def test_custom_values(self):
        """MapConfig accepts custom values."""
        config = MapConfig(
            width=1024,
            height=768,
            dpi=150,
            background_color="#F0F0F0",
            edge_color="#333333",
            edge_width=1.0,
            colormap_colors=["#FF0000", "#00FF00", "#0000FF"],
            vmin=-50.0,
            vmax=50.0,
        )
        assert config.width == 1024
        assert config.height == 768
        assert config.dpi == 150
        assert config.background_color == "#F0F0F0"
        assert config.edge_color == "#333333"
        assert config.edge_width == 1.0
        assert config.colormap_colors == ["#FF0000", "#00FF00", "#0000FF"]
        assert config.vmin == -50.0
        assert config.vmax == 50.0


class TestDepartmentData:
    """Test DepartmentData dataclass."""

    def test_strong_growth_color(self):
        """Department with >20% growth has strong_growth color."""
        dept = DepartmentData(
            code="75",
            name="Paris",
            growth_rate=0.25,
            companies_count=1000,
            confidence=0.9,
            top_sector="Tech",
        )
        assert dept.color == GROWTH_COLORS["strong_growth"]

    def test_moderate_growth_color(self):
        """Department with 5-20% growth has moderate_growth color."""
        dept = DepartmentData(
            code="69",
            name="Rhône",
            growth_rate=0.10,
            companies_count=500,
            confidence=0.8,
            top_sector="Industry",
        )
        assert dept.color == GROWTH_COLORS["moderate_growth"]

    def test_stable_color_positive(self):
        """Department with 0-5% growth has stable color."""
        dept = DepartmentData(
            code="13",
            name="Bouches-du-Rhône",
            growth_rate=0.03,
            companies_count=300,
            confidence=0.7,
            top_sector="Tourism",
        )
        assert dept.color == GROWTH_COLORS["stable"]

    def test_stable_color_negative(self):
        """Department with -5-0% growth has stable color."""
        dept = DepartmentData(
            code="59",
            name="Nord",
            growth_rate=-0.02,
            companies_count=200,
            confidence=0.6,
            top_sector="Retail",
        )
        assert dept.color == GROWTH_COLORS["stable"]

    def test_moderate_decline_color(self):
        """Department with -20 to -5% growth has moderate_decline color."""
        dept = DepartmentData(
            code="08",
            name="Ardennes",
            growth_rate=-0.10,
            companies_count=150,
            confidence=0.5,
            top_sector="Agriculture",
        )
        assert dept.color == GROWTH_COLORS["moderate_decline"]

    def test_strong_decline_color(self):
        """Department with <-20% growth has strong_decline color."""
        dept = DepartmentData(
            code="23",
            name="Creuse",
            growth_rate=-0.25,
            companies_count=50,
            confidence=0.4,
            top_sector="Services",
        )
        assert dept.color == GROWTH_COLORS["strong_decline"]

    def test_boundary_strong_growth(self):
        """Department with exactly 20% growth has moderate_growth color."""
        dept = DepartmentData(
            code="75",
            name="Paris",
            growth_rate=0.20,
            companies_count=1000,
            confidence=0.9,
            top_sector="Tech",
        )
        assert dept.color == GROWTH_COLORS["moderate_growth"]

    def test_boundary_moderate_growth(self):
        """Department with exactly 5% growth has moderate_growth color."""
        dept = DepartmentData(
            code="75",
            name="Paris",
            growth_rate=0.05,
            companies_count=1000,
            confidence=0.9,
            top_sector="Tech",
        )
        assert dept.color == GROWTH_COLORS["moderate_growth"]

    def test_boundary_moderate_decline(self):
        """Department with exactly -5% growth has stable color."""
        dept = DepartmentData(
            code="75",
            name="Paris",
            growth_rate=-0.05,
            companies_count=1000,
            confidence=0.9,
            top_sector="Tech",
        )
        assert dept.color == GROWTH_COLORS["stable"]

    def test_boundary_strong_decline(self):
        """Department with exactly -20% growth has moderate_decline color."""
        dept = DepartmentData(
            code="75",
            name="Paris",
            growth_rate=-0.20,
            companies_count=1000,
            confidence=0.9,
            top_sector="Tech",
        )
        assert dept.color == GROWTH_COLORS["moderate_decline"]


class TestFranceMapPNG:
    """Test FranceMapPNG widget."""

    def test_initialization_default(self):
        """FranceMapPNG initializes with default values."""
        widget = FranceMapPNG()
        assert (
            widget.geojson_path == Path.home() / ".cache" / "tawiza" / "geo" / "departements.geojson"
        )
        assert isinstance(widget.config, MapConfig)
        assert widget._department_data == {}

    def test_initialization_custom_path(self, tmp_path):
        """FranceMapPNG accepts custom geojson path."""
        custom_path = tmp_path / "custom.geojson"
        widget = FranceMapPNG(geojson_path=custom_path)
        assert widget.geojson_path == custom_path

    def test_initialization_custom_config(self):
        """FranceMapPNG accepts custom MapConfig."""
        config = MapConfig(width=1024, height=768)
        widget = FranceMapPNG(config=config)
        assert widget.config.width == 1024
        assert widget.config.height == 768

    def test_update_department(self):
        """update_department stores department data."""
        widget = FranceMapPNG()
        dept_data = DepartmentData(
            code="75",
            name="Paris",
            growth_rate=0.15,
            companies_count=1000,
            confidence=0.9,
            top_sector="Tech",
        )

        widget.update_department(dept_data)

        assert "75" in widget._department_data
        assert widget._department_data["75"] == dept_data

    def test_update_department_overwrites(self):
        """update_department overwrites existing data."""
        widget = FranceMapPNG()
        dept_data1 = DepartmentData(
            code="75",
            name="Paris",
            growth_rate=0.15,
            companies_count=1000,
            confidence=0.9,
            top_sector="Tech",
        )
        dept_data2 = DepartmentData(
            code="75",
            name="Paris",
            growth_rate=0.20,
            companies_count=1200,
            confidence=0.95,
            top_sector="Finance",
        )

        widget.update_department(dept_data1)
        widget.update_department(dept_data2)

        assert widget._department_data["75"] == dept_data2

    def test_update_all_data(self):
        """update_all_data updates multiple departments at once."""
        widget = FranceMapPNG()
        data = {
            "75": DepartmentData("75", "Paris", 0.15, 1000, 0.9, "Tech"),
            "69": DepartmentData("69", "Rhône", 0.10, 500, 0.8, "Industry"),
            "13": DepartmentData("13", "Bouches-du-Rhône", 0.05, 300, 0.7, "Tourism"),
        }

        widget.update_all_data(data)

        assert len(widget._department_data) == 3
        assert widget._department_data["75"].name == "Paris"
        assert widget._department_data["69"].name == "Rhône"
        assert widget._department_data["13"].name == "Bouches-du-Rhône"

    def test_clear_data(self):
        """clear_data removes all department data."""
        widget = FranceMapPNG()
        widget._department_data = {
            "75": DepartmentData("75", "Paris", 0.15, 1000, 0.9, "Tech"),
            "69": DepartmentData("69", "Rhône", 0.10, 500, 0.8, "Industry"),
        }

        widget.clear_data()

        assert widget._department_data == {}

    def test_get_department_data(self):
        """get_department_data returns department data or None."""
        widget = FranceMapPNG()
        dept_data = DepartmentData("75", "Paris", 0.15, 1000, 0.9, "Tech")
        widget.update_department(dept_data)

        assert widget.get_department_data("75") == dept_data
        assert widget.get_department_data("99") is None
