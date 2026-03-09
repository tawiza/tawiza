"""Tests complets pour ml_engineer_agent.py

Tests couvrant:
- MLTrainingConfig, TrainingResult, HyperparameterOptimizationResult dataclasses
- MLEngineerAgent
- Tests conditionnels pour ML
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.infrastructure.agents.advanced.ml_engineer_agent import (
    HyperparameterOptimizationResult,
    MLEngineerAgent,
    MLTrainingConfig,
    TrainingResult,
)


# ============================================================================
# Tests MLTrainingConfig Dataclass
# ============================================================================
class TestMLTrainingConfig:
    """Tests pour la dataclass MLTrainingConfig."""

    def test_create_config_minimal(self):
        """Configuration minimale."""
        config = MLTrainingConfig(
            task_id="task-001",
            dataset_path="/data/train.csv",
            target_column="label",
            problem_type="classification",
            model_type="random_forest",
            optimization_method="grid_search",
        )

        assert config.task_id == "task-001"
        assert config.target_column == "label"
        assert config.problem_type == "classification"
        assert config.max_trials == 50
        assert config.cross_validation_folds == 5
        assert config.test_size == 0.2

    def test_create_config_full(self):
        """Configuration complète."""
        config = MLTrainingConfig(
            task_id="task-002",
            dataset_path="/data/train.csv",
            target_column="target",
            problem_type="regression",
            model_type="gradient_boosting",
            optimization_method="bayesian",
            max_trials=100,
            cross_validation_folds=10,
            test_size=0.3,
            random_state=123,
            gpu_acceleration=False,
            early_stopping=False,
            max_epochs=50,
            batch_size=64,
            learning_rate=0.01,
        )

        assert config.max_trials == 100
        assert config.cross_validation_folds == 10
        assert config.test_size == 0.3
        assert config.gpu_acceleration is False
        assert config.learning_rate == 0.01

    def test_problem_types(self):
        """Types de problèmes valides."""
        for problem_type in ["classification", "regression"]:
            config = MLTrainingConfig(
                task_id="test",
                dataset_path="/data.csv",
                target_column="target",
                problem_type=problem_type,
                model_type="random_forest",
                optimization_method="grid_search",
            )
            assert config.problem_type == problem_type


# ============================================================================
# Tests TrainingResult Dataclass
# ============================================================================
class TestTrainingResult:
    """Tests pour la dataclass TrainingResult."""

    def test_create_result(self):
        """Création d'un résultat de training."""
        result = TrainingResult(
            task_id="task-001",
            model_type="random_forest",
            best_params={"n_estimators": 100, "max_depth": 10},
            best_score=0.95,
            cv_scores=[0.94, 0.95, 0.96, 0.94, 0.96],
            test_scores={"accuracy": 0.95, "f1": 0.94},
            training_time=120.5,
            model_size_mb=25.3,
            gpu_usage={"utilization": 75.0, "memory": 8000},
            convergence_history=[0.5, 0.7, 0.85, 0.92, 0.95],
            generated_at=time.time(),
            model_path="/models/model.pkl",
        )

        assert result.task_id == "task-001"
        assert result.best_score == 0.95
        assert len(result.cv_scores) == 5
        assert result.test_scores["accuracy"] == 0.95
        assert result.training_time == 120.5
        assert result.model_size_mb == 25.3

    def test_result_with_metadata(self):
        """Résultat avec métadonnées."""
        result = TrainingResult(
            task_id="task-002",
            model_type="neural_network",
            best_params={},
            best_score=0.90,
            cv_scores=[],
            test_scores={},
            training_time=500.0,
            model_size_mb=100.0,
            gpu_usage={},
            convergence_history=[],
            generated_at=time.time(),
            model_path="/models/nn.pt",
            metadata={"framework": "pytorch", "epochs_completed": 50, "early_stopped": True},
        )

        assert result.metadata["framework"] == "pytorch"
        assert result.metadata["early_stopped"] is True


# ============================================================================
# Tests HyperparameterOptimizationResult Dataclass
# ============================================================================
class TestHyperparameterOptimizationResult:
    """Tests pour HyperparameterOptimizationResult."""

    def test_create_optimization_result(self):
        """Création d'un résultat d'optimisation."""
        result = HyperparameterOptimizationResult(
            best_params={"n_estimators": 200, "max_depth": 15},
            best_score=0.97,
            optimization_history=[
                {"trial": 1, "score": 0.90},
                {"trial": 2, "score": 0.95},
                {"trial": 3, "score": 0.97},
            ],
            total_trials=50,
            best_trial_number=45,
            optimization_time=3600.0,
            convergence_plot_data={"trials": [1, 2, 3], "scores": [0.90, 0.95, 0.97]},
        )

        assert result.best_score == 0.97
        assert result.total_trials == 50
        assert result.best_trial_number == 45
        assert result.optimization_time == 3600.0


# ============================================================================
# Tests MLEngineerAgent - Création
# ============================================================================
class TestMLEngineerAgentBasic:
    """Tests basiques pour MLEngineerAgent."""

    def test_create_agent(self):
        """Création de l'agent."""
        agent = MLEngineerAgent()

        assert agent.name == "MLEngineerAgent"
        assert agent.agent_type == "ml_engineer"
        assert isinstance(agent.capabilities, list)
        assert len(agent.capabilities) == 6

    def test_create_agent_with_name(self):
        """Création avec nom personnalisé."""
        agent = MLEngineerAgent(name="CustomMLAgent")
        assert agent.name == "CustomMLAgent"

    def test_capabilities(self):
        """Vérification des capacités."""
        agent = MLEngineerAgent()

        expected_capabilities = [
            "ml_pipeline_automation",
            "hyperparameter_optimization",
            "model_selection",
            "performance_monitoring",
            "auto_ml_pipeline",
            "gpu_optimization",
        ]

        for cap in expected_capabilities:
            assert cap in agent.capabilities

    def test_ml_config(self):
        """Configuration ML."""
        agent = MLEngineerAgent()

        assert "supported_models" in agent.ml_config
        assert "optimization_methods" in agent.ml_config
        assert agent.ml_config["gpu_optimization"] is True
        assert agent.ml_config["early_stopping"] is True
        assert agent.ml_config["cross_validation"] is True

    def test_supported_models(self):
        """Modèles supportés."""
        agent = MLEngineerAgent()

        classification_models = agent.ml_config["supported_models"]["classification"]
        regression_models = agent.ml_config["supported_models"]["regression"]

        assert "random_forest" in classification_models
        assert "gradient_boosting" in classification_models
        assert "neural_network" in classification_models

        assert "random_forest" in regression_models
        assert "neural_network" in regression_models

    def test_optimization_methods(self):
        """Méthodes d'optimisation supportées."""
        agent = MLEngineerAgent()

        methods = agent.ml_config["optimization_methods"]
        expected = ["grid_search", "random_search", "bayesian", "optuna", "hyperband"]

        for method in expected:
            assert method in methods


# ============================================================================
# Tests MLEngineerAgent - Cache
# ============================================================================
class TestMLEngineerAgentCache:
    """Tests du système de cache."""

    def test_empty_cache(self):
        """Cache vide au départ."""
        agent = MLEngineerAgent()

        assert agent.model_cache == {}
        assert agent.optimization_cache == {}

    def test_cache_model(self):
        """Mise en cache d'un modèle."""
        agent = MLEngineerAgent()

        agent.model_cache["model_hash_001"] = {"model": "mock_model", "score": 0.95}

        assert "model_hash_001" in agent.model_cache
        assert agent.model_cache["model_hash_001"]["score"] == 0.95

    def test_cache_optimization(self):
        """Mise en cache d'une optimisation."""
        agent = MLEngineerAgent()

        agent.optimization_cache["opt_hash_001"] = {
            "best_params": {"n_estimators": 100},
            "best_score": 0.95,
        }

        assert "opt_hash_001" in agent.optimization_cache


# ============================================================================
# Tests MLEngineerAgent - Méthodes avec mocks
# ============================================================================
class TestMLEngineerAgentMethods:
    """Tests des méthodes avec mocks."""

    @pytest.mark.asyncio
    async def test_create_ml_pipeline_mocked(self):
        """Création de pipeline ML avec mocks."""
        agent = MLEngineerAgent()

        config = MLTrainingConfig(
            task_id="test-001",
            dataset_path="/fake/data.csv",
            target_column="target",
            problem_type="classification",
            model_type="random_forest",
            optimization_method="grid_search",
        )

        # Mock les méthodes internes
        agent._prepare_data = AsyncMock(
            return_value=(np.array([[1, 2], [3, 4], [5, 6]]), np.array([0, 1, 0]), MagicMock())
        )
        agent._optimize_hyperparameters = AsyncMock(
            return_value=({"n_estimators": 100}, MagicMock())
        )
        agent._train_final_model = AsyncMock(return_value=(MagicMock(), {"accuracy": 0.95}))
        agent._evaluate_model = AsyncMock(return_value={"accuracy": 0.95, "f1": 0.94})
        agent._save_model = AsyncMock(return_value="/models/model.pkl")

        result = await agent.create_ml_pipeline(config)

        assert result.task_id == "test-001"
        agent._prepare_data.assert_called_once()
        agent._optimize_hyperparameters.assert_called_once()


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestMLEngineerAgentEdgeCases:
    """Tests des cas limites."""

    def test_multiple_agent_instances(self):
        """Plusieurs instances indépendantes."""
        agent1 = MLEngineerAgent(name="Agent1")
        agent2 = MLEngineerAgent(name="Agent2")

        agent1.model_cache["key"] = "value1"
        agent2.model_cache["key"] = "value2"

        assert agent1.model_cache["key"] == "value1"
        assert agent2.model_cache["key"] == "value2"

    def test_config_neural_network(self):
        """Configuration pour réseau de neurones."""
        config = MLTrainingConfig(
            task_id="nn-task",
            dataset_path="/data.csv",
            target_column="target",
            problem_type="classification",
            model_type="neural_network",
            optimization_method="optuna",
            gpu_acceleration=True,
            max_epochs=200,
            batch_size=128,
            learning_rate=0.0001,
        )

        assert config.model_type == "neural_network"
        assert config.gpu_acceleration is True
        assert config.max_epochs == 200
        assert config.batch_size == 128

    def test_cv_scores_statistics(self):
        """Statistiques sur les scores CV."""
        result = TrainingResult(
            task_id="stat-test",
            model_type="random_forest",
            best_params={},
            best_score=0.95,
            cv_scores=[0.92, 0.94, 0.96, 0.95, 0.93],
            test_scores={},
            training_time=100.0,
            model_size_mb=10.0,
            gpu_usage={},
            convergence_history=[],
            generated_at=time.time(),
            model_path="",
        )

        cv_mean = np.mean(result.cv_scores)
        cv_std = np.std(result.cv_scores)

        assert 0.93 < cv_mean < 0.96
        assert cv_std < 0.05  # Faible variance

    def test_empty_convergence_history(self):
        """Historique de convergence vide."""
        result = TrainingResult(
            task_id="empty-hist",
            model_type="logistic_regression",
            best_params={},
            best_score=0.85,
            cv_scores=[],
            test_scores={},
            training_time=5.0,
            model_size_mb=0.1,
            gpu_usage={},
            convergence_history=[],
            generated_at=time.time(),
            model_path="",
        )

        assert result.convergence_history == []
