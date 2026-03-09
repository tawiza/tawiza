"""Unit tests for PromptManager.

Tests cover:
- Template registration and validation
- Variable extraction and validation
- Template rendering with variables
- Template persistence (save/load)
- Statistics tracking
- Error handling
- Singleton pattern
- Default templates creation
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pytest

from src.infrastructure.prompts.prompt_manager import (
    PromptFormat,
    PromptManager,
    PromptTemplate,
    get_prompt_manager,
)


# Test fixtures
@pytest.fixture
def temp_templates_dir(tmp_path):
    """Create temporary directory for templates."""
    templates_dir = tmp_path / "prompts"
    templates_dir.mkdir()
    return templates_dir


@pytest.fixture
def prompt_manager(temp_templates_dir):
    """Create a fresh PromptManager for testing."""
    return PromptManager(templates_dir=temp_templates_dir)


@pytest.fixture
def sample_template_data():
    """Sample template data for testing."""
    return {
        "name": "test_template",
        "format": PromptFormat.BROWSER,
        "template": "Navigate to {url} and {action}",
        "description": "Test template",
        "version": "1.0",
    }


# Unit Tests
class TestPromptTemplate:
    """Test PromptTemplate class."""

    def test_create_template(self):
        """Test template creation."""
        template = PromptTemplate(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
        )

        assert template.name == "test"
        assert template.format == PromptFormat.BROWSER
        assert template.template == "Go to {url}"
        assert len(template.variables) == 1
        assert "url" in template.variables
        assert template.usage_count == 0

    def test_variable_extraction(self):
        """Test automatic variable extraction."""
        template = PromptTemplate(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url} and {action} then {next_step}",
        )

        assert len(template.variables) == 3
        assert "url" in template.variables
        assert "action" in template.variables
        assert "next_step" in template.variables

    def test_variable_extraction_no_duplicates(self):
        """Test that duplicate variables are not extracted twice."""
        template = PromptTemplate(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url} and return to {url}",
        )

        assert len(template.variables) == 1
        assert "url" in template.variables

    def test_variable_validation_success(self):
        """Test variable validation with all variables provided."""
        template = PromptTemplate(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url} and {action}",
        )

        is_valid, missing = template.validate_variables(url="google.com", action="search")

        assert is_valid is True
        assert len(missing) == 0

    def test_variable_validation_missing(self):
        """Test variable validation with missing variables."""
        template = PromptTemplate(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url} and {action}",
        )

        is_valid, missing = template.validate_variables(url="google.com")

        assert is_valid is False
        assert "action" in missing

    def test_render_success(self):
        """Test successful template rendering."""
        template = PromptTemplate(
            name="test",
            format=PromptFormat.BROWSER,
            template="Navigate to {url} and {action}",
        )

        rendered = template.render(url="google.com", action="search for Python")

        assert rendered == "Navigate to google.com and search for Python"
        assert template.usage_count == 1

    def test_render_increments_usage_count(self):
        """Test that rendering increments usage count."""
        template = PromptTemplate(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
        )

        assert template.usage_count == 0
        template.render(url="google.com")
        assert template.usage_count == 1
        template.render(url="example.com")
        assert template.usage_count == 2

    def test_render_missing_variable_raises(self):
        """Test that rendering with missing variables raises ValueError."""
        template = PromptTemplate(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url} and {action}",
        )

        with pytest.raises(ValueError, match="Variables manquantes"):
            template.render(url="google.com")

    def test_render_extra_variables_ok(self):
        """Test that rendering with extra variables is ok."""
        template = PromptTemplate(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
        )

        # Should work fine with extra variables
        rendered = template.render(url="google.com", extra="ignored")
        assert rendered == "Go to google.com"

    def test_to_dict(self):
        """Test template conversion to dictionary."""
        template = PromptTemplate(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
            description="Test template",
            version="1.0",
            metadata={"category": "browser"},
        )

        data = template.to_dict()

        assert data["name"] == "test"
        assert data["format"] == "browser"
        assert data["template"] == "Go to {url}"
        assert data["description"] == "Test template"
        assert data["version"] == "1.0"
        assert data["metadata"]["category"] == "browser"
        assert "created_at" in data
        assert "updated_at" in data

    def test_from_dict(self):
        """Test template creation from dictionary."""
        data = {
            "name": "test",
            "format": "browser",
            "template": "Go to {url}",
            "variables": ["url"],
            "description": "Test",
            "version": "1.0",
            "metadata": {},
            "usage_count": 5,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-02T00:00:00",
        }

        template = PromptTemplate.from_dict(data)

        assert template.name == "test"
        assert template.format == PromptFormat.BROWSER
        assert template.template == "Go to {url}"
        assert template.usage_count == 5


class TestPromptManager:
    """Test PromptManager class."""

    def test_manager_initialization(self, prompt_manager):
        """Test manager initialization."""
        assert len(prompt_manager.templates) == 0
        assert prompt_manager.stats["total_renders"] == 0

    def test_register_template(self, prompt_manager):
        """Test template registration."""
        template = prompt_manager.register_template(
            name="test_template",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
            description="Test template",
        )

        assert template.name == "test_template"
        assert "test_template" in prompt_manager.templates
        assert len(prompt_manager.templates) == 1

    def test_register_duplicate_template_replaces(self, prompt_manager):
        """Test that registering duplicate template replaces the old one."""
        prompt_manager.register_template(
            name="test",
            format=PromptFormat.BROWSER,
            template="Old template {url}",
        )

        prompt_manager.register_template(
            name="test",
            format=PromptFormat.BROWSER,
            template="New template {url}",
        )

        assert len(prompt_manager.templates) == 1
        assert prompt_manager.templates["test"].template == "New template {url}"

    def test_get_template_exists(self, prompt_manager):
        """Test getting existing template."""
        prompt_manager.register_template(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
        )

        template = prompt_manager.get_template("test")

        assert template is not None
        assert template.name == "test"

    def test_get_template_not_exists(self, prompt_manager):
        """Test getting non-existent template returns None."""
        template = prompt_manager.get_template("nonexistent")

        assert template is None

    def test_render_template_success(self, prompt_manager):
        """Test rendering a template."""
        prompt_manager.register_template(
            name="test",
            format=PromptFormat.BROWSER,
            template="Navigate to {url} and {action}",
        )

        rendered = prompt_manager.render("test", url="google.com", action="search")

        assert rendered == "Navigate to google.com and search"
        assert prompt_manager.stats["total_renders"] == 1
        assert prompt_manager.stats["renders_by_template"]["test"] == 1
        assert prompt_manager.stats["renders_by_format"]["browser"] == 1

    def test_render_template_not_found_raises(self, prompt_manager):
        """Test rendering non-existent template raises ValueError."""
        with pytest.raises(ValueError, match="non trouvé"):
            prompt_manager.render("nonexistent", url="google.com")

    def test_render_increments_stats(self, prompt_manager):
        """Test that rendering increments statistics."""
        prompt_manager.register_template(
            name="test1",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
        )

        prompt_manager.register_template(
            name="test2",
            format=PromptFormat.ALPACA,
            template="### Instruction:\n{instruction}",
        )

        # Render test1 twice
        prompt_manager.render("test1", url="google.com")
        prompt_manager.render("test1", url="example.com")

        # Render test2 once
        prompt_manager.render("test2", instruction="Test")

        assert prompt_manager.stats["total_renders"] == 3
        assert prompt_manager.stats["renders_by_template"]["test1"] == 2
        assert prompt_manager.stats["renders_by_template"]["test2"] == 1
        assert prompt_manager.stats["renders_by_format"]["browser"] == 2
        assert prompt_manager.stats["renders_by_format"]["alpaca"] == 1

    def test_list_templates_all(self, prompt_manager):
        """Test listing all templates."""
        prompt_manager.register_template(
            name="test1",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
        )

        prompt_manager.register_template(
            name="test2",
            format=PromptFormat.ALPACA,
            template="### Instruction:\n{instruction}",
        )

        templates = prompt_manager.list_templates()

        assert len(templates) == 2
        names = [t.name for t in templates]
        assert "test1" in names
        assert "test2" in names

    def test_list_templates_filtered(self, prompt_manager):
        """Test listing templates with format filter."""
        prompt_manager.register_template(
            name="test1",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
        )

        prompt_manager.register_template(
            name="test2",
            format=PromptFormat.ALPACA,
            template="### Instruction:\n{instruction}",
        )

        prompt_manager.register_template(
            name="test3",
            format=PromptFormat.BROWSER,
            template="Navigate to {url}",
        )

        browser_templates = prompt_manager.list_templates(format_filter=PromptFormat.BROWSER)

        assert len(browser_templates) == 2
        for template in browser_templates:
            assert template.format == PromptFormat.BROWSER

    def test_save_templates(self, prompt_manager, temp_templates_dir):
        """Test saving templates to file."""
        prompt_manager.register_template(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
        )

        prompt_manager.save_templates()

        # Check file exists
        filepath = temp_templates_dir / "templates.json"
        assert filepath.exists()

        # Load and verify
        with open(filepath) as f:
            data = json.load(f)

        assert "templates" in data
        assert "stats" in data
        assert "saved_at" in data
        assert len(data["templates"]) == 1
        assert data["templates"][0]["name"] == "test"

    def test_load_templates(self, prompt_manager, temp_templates_dir):
        """Test loading templates from file."""
        # Create templates file
        templates_data = {
            "templates": [
                {
                    "name": "test",
                    "format": "browser",
                    "template": "Go to {url}",
                    "variables": ["url"],
                    "description": "Test",
                    "version": "1.0",
                    "metadata": {},
                    "usage_count": 5,
                    "created_at": "2025-01-01T00:00:00",
                    "updated_at": "2025-01-02T00:00:00",
                }
            ],
            "stats": {
                "total_renders": 10,
                "renders_by_template": {"test": 5},
                "renders_by_format": {"browser": 5},
            },
        }

        filepath = temp_templates_dir / "templates.json"
        with open(filepath, "w") as f:
            json.dump(templates_data, f)

        # Load templates
        prompt_manager.load_templates()

        assert len(prompt_manager.templates) == 1
        assert "test" in prompt_manager.templates
        assert prompt_manager.templates["test"].usage_count == 5
        assert prompt_manager.stats["total_renders"] == 10

    def test_load_templates_missing_file(self, prompt_manager, temp_templates_dir):
        """Test loading from missing file doesn't raise."""
        # Should not raise, just log warning
        prompt_manager.load_templates()
        assert len(prompt_manager.templates) == 0

    def test_get_stats(self, prompt_manager):
        """Test getting statistics."""
        prompt_manager.register_template(
            name="test1",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
        )

        prompt_manager.register_template(
            name="test2",
            format=PromptFormat.ALPACA,
            template="### Instruction:\n{instruction}",
        )

        prompt_manager.render("test1", url="google.com")

        stats = prompt_manager.get_stats()

        assert stats["total_templates"] == 2
        assert stats["total_renders"] == 1
        assert stats["templates_by_format"]["browser"] == 1
        assert stats["templates_by_format"]["alpaca"] == 1

    def test_create_default_templates(self, prompt_manager):
        """Test creating default templates."""
        prompt_manager.create_default_templates()

        assert len(prompt_manager.templates) == 17

        # Check specific templates
        assert "browser_navigation" in prompt_manager.templates
        assert "browser_task_detailed" in prompt_manager.templates
        assert "text_classification" in prompt_manager.templates
        assert "chat_simple" in prompt_manager.templates
        assert "named_entity_recognition" in prompt_manager.templates
        assert "text_summarization" in prompt_manager.templates
        assert "code_generation" in prompt_manager.templates

    def test_default_templates_have_correct_variables(self, prompt_manager):
        """Test that default templates have correct variables."""
        prompt_manager.create_default_templates()

        # Check browser_navigation
        browser_nav = prompt_manager.get_template("browser_navigation")
        assert "url" in browser_nav.variables
        assert "action" in browser_nav.variables

        # Check text_classification
        text_class = prompt_manager.get_template("text_classification")
        assert "text" in text_class.variables
        assert "categories" in text_class.variables

        # Check code_generation
        code_gen = prompt_manager.get_template("code_generation")
        assert "language" in code_gen.variables
        assert "task" in code_gen.variables
        assert "requirements" in code_gen.variables


class TestPromptManagerSingleton:
    """Test global singleton pattern."""

    def test_get_prompt_manager_returns_singleton(self, temp_templates_dir):
        """Test that get_prompt_manager returns the same instance."""
        # Reset global instance
        import src.infrastructure.prompts.prompt_manager as pm_module

        pm_module._prompt_manager = None

        manager1 = get_prompt_manager(temp_templates_dir)
        manager2 = get_prompt_manager(temp_templates_dir)

        assert manager1 is manager2

        # Cleanup
        pm_module._prompt_manager = None

    def test_singleton_loads_and_creates_defaults(self, temp_templates_dir):
        """Test that singleton loads existing or creates defaults."""
        # Reset global instance
        import src.infrastructure.prompts.prompt_manager as pm_module

        pm_module._prompt_manager = None

        manager = get_prompt_manager(temp_templates_dir)

        # Should have default templates
        assert len(manager.templates) == 17

        # Cleanup
        pm_module._prompt_manager = None


class TestPromptManagerEdgeCases:
    """Test edge cases and error handling."""

    def test_template_with_no_variables(self, prompt_manager):
        """Test template with no variables works."""
        template = prompt_manager.register_template(
            name="static",
            format=PromptFormat.SIMPLE,
            template="This is a static prompt",
        )

        assert len(template.variables) == 0

        # Should render without any variables
        rendered = prompt_manager.render("static")
        assert rendered == "This is a static prompt"

    def test_template_with_special_characters(self, prompt_manager):
        """Test template with special characters in variables."""
        template = prompt_manager.register_template(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url} and search for {search_query}",
        )

        rendered = prompt_manager.render(
            "test", url="https://example.com?foo=bar&baz=qux", search_query="Python & ML"
        )

        assert "https://example.com?foo=bar&baz=qux" in rendered
        assert "Python & ML" in rendered

    def test_concurrent_renders_update_stats(self, prompt_manager):
        """Test that concurrent renders correctly update stats."""
        prompt_manager.register_template(
            name="test",
            format=PromptFormat.BROWSER,
            template="Go to {url}",
        )

        # Render multiple times
        for i in range(10):
            prompt_manager.render("test", url=f"url{i}.com")

        assert prompt_manager.stats["total_renders"] == 10
        assert prompt_manager.stats["renders_by_template"]["test"] == 10
