"""Tests complets pour code_generator_agent.py

Tests couvrant:
- CodeGenerationRequest, GeneratedCode, CodeAnalysis dataclasses
- CodeGeneratorAgent
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.advanced.code_generator_agent import (
    CodeAnalysis,
    CodeGenerationRequest,
    CodeGeneratorAgent,
    GeneratedCode,
)


# ============================================================================
# Tests CodeGenerationRequest Dataclass
# ============================================================================
class TestCodeGenerationRequest:
    """Tests pour la dataclass CodeGenerationRequest."""

    def test_create_request_minimal(self):
        """Création d'une requête minimale."""
        request = CodeGenerationRequest(request_id="req-001", language="python")

        assert request.request_id == "req-001"
        assert request.language == "python"
        assert request.framework is None
        assert request.description == ""
        assert request.requirements is None
        assert request.existing_code is None

    def test_create_request_full(self):
        """Création d'une requête complète."""
        request = CodeGenerationRequest(
            request_id="req-002",
            language="python",
            framework="fastapi",
            description="Create a REST API endpoint",
            requirements=["async support", "validation"],
            existing_code="from fastapi import FastAPI",
            style_guide="PEP8",
            test_cases=["test_endpoint_returns_200"],
            performance_requirements={"max_latency_ms": 100},
            security_requirements=["input_validation", "rate_limiting"],
        )

        assert request.framework == "fastapi"
        assert len(request.requirements) == 2
        assert request.style_guide == "PEP8"
        assert len(request.security_requirements) == 2

    def test_supported_languages(self):
        """Test avec différents langages."""
        languages = ["python", "javascript", "typescript", "go", "rust"]

        for lang in languages:
            request = CodeGenerationRequest(request_id=f"req-{lang}", language=lang)
            assert request.language == lang


# ============================================================================
# Tests GeneratedCode Dataclass
# ============================================================================
class TestGeneratedCode:
    """Tests pour la dataclass GeneratedCode."""

    def test_create_generated_code(self):
        """Création de code généré."""
        code = GeneratedCode(
            request_id="req-001",
            language="python",
            code="def hello(): return 'Hello'",
            imports=["typing", "asyncio"],
            functions=[{"name": "hello", "params": [], "returns": "str"}],
            classes=[],
            tests=["def test_hello(): assert hello() == 'Hello'"],
            documentation="A simple hello function",
            dependencies=["pytest"],
            file_structure={"main.py": "def hello()..."},
            quality_score=0.95,
            performance_analysis={"complexity": "O(1)"},
            security_analysis={"vulnerabilities": []},
            timestamp="2024-01-01T00:00:00",
        )

        assert code.request_id == "req-001"
        assert "def hello" in code.code
        assert len(code.imports) == 2
        assert code.quality_score == 0.95

    def test_generated_code_with_classes(self):
        """Code généré avec classes."""
        code = GeneratedCode(
            request_id="req-002",
            language="python",
            code="class MyClass:\n    pass",
            imports=[],
            functions=[],
            classes=[
                {"name": "MyClass", "methods": ["__init__", "process"], "attributes": ["data"]}
            ],
            tests=[],
            documentation="",
            dependencies=[],
            file_structure={},
            quality_score=0.8,
            performance_analysis={},
            security_analysis={},
            timestamp="",
        )

        assert len(code.classes) == 1
        assert code.classes[0]["name"] == "MyClass"


# ============================================================================
# Tests CodeAnalysis Dataclass
# ============================================================================
class TestCodeAnalysis:
    """Tests pour la dataclass CodeAnalysis."""

    def test_create_analysis(self):
        """Création d'une analyse de code."""
        analysis = CodeAnalysis(
            complexity_score=0.7,
            maintainability_score=0.85,
            security_score=0.9,
            performance_score=0.8,
            test_coverage=0.75,
            code_quality=0.82,
            issues=[{"type": "warning", "message": "Consider adding docstring"}],
            recommendations=["Add type hints", "Improve error handling"],
        )

        assert analysis.complexity_score == 0.7
        assert analysis.maintainability_score == 0.85
        assert analysis.security_score == 0.9
        assert len(analysis.issues) == 1
        assert len(analysis.recommendations) == 2

    def test_perfect_analysis(self):
        """Analyse parfaite."""
        analysis = CodeAnalysis(
            complexity_score=1.0,
            maintainability_score=1.0,
            security_score=1.0,
            performance_score=1.0,
            test_coverage=1.0,
            code_quality=1.0,
            issues=[],
            recommendations=[],
        )

        assert analysis.code_quality == 1.0
        assert len(analysis.issues) == 0


# ============================================================================
# Tests CodeGeneratorAgent - Création
# ============================================================================
class TestCodeGeneratorAgentBasic:
    """Tests basiques pour CodeGeneratorAgent."""

    def test_create_agent(self):
        """Création de l'agent."""
        agent = CodeGeneratorAgent()

        assert agent.name == "CodeGeneratorAgent"
        assert agent.agent_type == "code_generator"
        assert isinstance(agent.capabilities, list)
        assert len(agent.capabilities) == 5
        assert agent.is_initialized is False

    def test_capabilities(self):
        """Vérification des capacités."""
        agent = CodeGeneratorAgent()

        expected_capabilities = [
            "code_generation",
            "code_analysis",
            "code_refactoring",
            "test_generation",
            "documentation_generation",
        ]

        for cap in expected_capabilities:
            assert cap in agent.capabilities

    def test_initial_state(self):
        """État initial de l'agent."""
        agent = CodeGeneratorAgent()

        assert agent.templates == {}
        assert agent.code_patterns == {}
        assert agent.best_practices == {}
        assert agent.security_rules == {}
        assert agent.performance_tips == {}
        assert agent.generation_history == []


# ============================================================================
# Tests CodeGeneratorAgent - Initialisation
# ============================================================================
class TestCodeGeneratorAgentInitialization:
    """Tests d'initialisation de l'agent."""

    @pytest.mark.asyncio
    async def test_initialize_mocked(self):
        """Initialisation avec mocks."""
        agent = CodeGeneratorAgent()

        agent._load_templates = AsyncMock()
        agent._load_code_patterns = AsyncMock()
        agent._load_best_practices = AsyncMock()
        agent._load_security_rules = AsyncMock()
        agent._load_performance_tips = AsyncMock()

        await agent.initialize()

        assert agent.is_initialized is True
        agent._load_templates.assert_called_once()
        agent._load_code_patterns.assert_called_once()
        agent._load_best_practices.assert_called_once()
        agent._load_security_rules.assert_called_once()
        agent._load_performance_tips.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """Échec de l'initialisation."""
        agent = CodeGeneratorAgent()

        agent._load_templates = AsyncMock(side_effect=Exception("Load failed"))

        with pytest.raises(Exception, match="Load failed"):
            await agent.initialize()

        assert agent.is_initialized is False


# ============================================================================
# Tests CodeGeneratorAgent - Templates
# ============================================================================
class TestCodeGeneratorAgentTemplates:
    """Tests des templates."""

    @pytest.mark.asyncio
    async def test_load_templates(self):
        """Chargement des templates."""
        agent = CodeGeneratorAgent()

        await agent._load_templates()

        assert "python" in agent.templates
        assert "class" in agent.templates["python"]
        assert "function" in agent.templates["python"]
        assert "test" in agent.templates["python"]


# ============================================================================
# Tests CodeGeneratorAgent - Historique
# ============================================================================
class TestCodeGeneratorAgentHistory:
    """Tests de l'historique de génération."""

    def test_empty_history(self):
        """Historique vide au départ."""
        agent = CodeGeneratorAgent()
        assert agent.generation_history == []

    def test_add_to_history(self):
        """Ajout à l'historique."""
        agent = CodeGeneratorAgent()

        code = GeneratedCode(
            request_id="req-001",
            language="python",
            code="pass",
            imports=[],
            functions=[],
            classes=[],
            tests=[],
            documentation="",
            dependencies=[],
            file_structure={},
            quality_score=0.5,
            performance_analysis={},
            security_analysis={},
            timestamp="",
        )

        agent.generation_history.append(code)
        assert len(agent.generation_history) == 1

    def test_history_limit(self):
        """Limite de l'historique."""
        agent = CodeGeneratorAgent()

        # Ajouter 100 entrées
        for i in range(100):
            code = GeneratedCode(
                request_id=f"req-{i:03d}",
                language="python",
                code="pass",
                imports=[],
                functions=[],
                classes=[],
                tests=[],
                documentation="",
                dependencies=[],
                file_structure={},
                quality_score=0.5,
                performance_analysis={},
                security_analysis={},
                timestamp="",
            )
            agent.generation_history.append(code)

        assert len(agent.generation_history) == 100


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestCodeGeneratorAgentEdgeCases:
    """Tests des cas limites."""

    def test_request_with_empty_description(self):
        """Requête avec description vide."""
        request = CodeGenerationRequest(request_id="req-empty", language="python", description="")
        assert request.description == ""

    def test_analysis_with_many_issues(self):
        """Analyse avec beaucoup d'issues."""
        issues = [{"type": "error", "message": f"Error {i}"} for i in range(50)]

        analysis = CodeAnalysis(
            complexity_score=0.3,
            maintainability_score=0.2,
            security_score=0.4,
            performance_score=0.5,
            test_coverage=0.1,
            code_quality=0.3,
            issues=issues,
            recommendations=[],
        )

        assert len(analysis.issues) == 50

    def test_generated_code_with_large_file_structure(self):
        """Code généré avec structure de fichiers large."""
        file_structure = {
            f"module_{i}/file_{j}.py": f"# Module {i} File {j}" for i in range(10) for j in range(5)
        }

        code = GeneratedCode(
            request_id="req-large",
            language="python",
            code="",
            imports=[],
            functions=[],
            classes=[],
            tests=[],
            documentation="",
            dependencies=[],
            file_structure=file_structure,
            quality_score=0.5,
            performance_analysis={},
            security_analysis={},
            timestamp="",
        )

        assert len(code.file_structure) == 50

    def test_multiple_agent_instances(self):
        """Plusieurs instances indépendantes."""
        agent1 = CodeGeneratorAgent()
        agent2 = CodeGeneratorAgent()

        agent1.templates["custom"] = {"template": "custom1"}
        agent2.templates["custom"] = {"template": "custom2"}

        assert agent1.templates["custom"]["template"] == "custom1"
        assert agent2.templates["custom"]["template"] == "custom2"
