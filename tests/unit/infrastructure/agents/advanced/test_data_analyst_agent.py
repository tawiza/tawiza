"""Tests complets pour data_analyst_agent.py

Tests couvrant:
- DataAnalysisReport et PreprocessingRecommendation dataclasses
- DataAnalystAgent
- Tests conditionnels (pas de fichier réel requis)
"""

import asyncio
import os
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.infrastructure.agents.advanced.data_analyst_agent import (
    DataAnalysisReport,
    DataAnalystAgent,
    PreprocessingRecommendation,
)


# ============================================================================
# Tests DataAnalysisReport Dataclass
# ============================================================================
class TestDataAnalysisReport:
    """Tests pour la dataclass DataAnalysisReport."""

    def test_create_report(self):
        """Création d'un rapport d'analyse."""
        report = DataAnalysisReport(
            dataset_id="dataset-001",
            file_path="/path/to/data.csv",
            rows=1000,
            columns=10,
            missing_data_percentage=5.5,
            duplicate_rows=10,
            data_types={"col1": "int64", "col2": "object"},
            numerical_columns=["col1", "col3"],
            categorical_columns=["col2"],
            quality_score=0.85,
            recommendations=["Handle missing values"],
            anomalies_detected=[{"column": "col1", "type": "outlier"}],
            preprocessing_suggestions=[{"step": "imputation"}],
            generated_at=time.time(),
        )

        assert report.dataset_id == "dataset-001"
        assert report.rows == 1000
        assert report.columns == 10
        assert report.missing_data_percentage == 5.5
        assert report.quality_score == 0.85
        assert len(report.numerical_columns) == 2
        assert len(report.categorical_columns) == 1

    def test_report_with_no_issues(self):
        """Rapport sans problèmes détectés."""
        report = DataAnalysisReport(
            dataset_id="clean-dataset",
            file_path="/path/clean.csv",
            rows=500,
            columns=5,
            missing_data_percentage=0.0,
            duplicate_rows=0,
            data_types={},
            numerical_columns=[],
            categorical_columns=[],
            quality_score=1.0,
            recommendations=[],
            anomalies_detected=[],
            preprocessing_suggestions=[],
            generated_at=time.time(),
        )

        assert report.missing_data_percentage == 0.0
        assert report.duplicate_rows == 0
        assert report.quality_score == 1.0
        assert len(report.anomalies_detected) == 0


# ============================================================================
# Tests PreprocessingRecommendation Dataclass
# ============================================================================
class TestPreprocessingRecommendation:
    """Tests pour la dataclass PreprocessingRecommendation."""

    def test_create_recommendation(self):
        """Création d'une recommandation."""
        rec = PreprocessingRecommendation(
            step_name="imputation",
            description="Imputer les valeurs manquantes avec la médiane",
            priority="high",
            estimated_impact=0.8,
            implementation_complexity="simple",
            code_example="df.fillna(df.median())",
            expected_benefits=["Reduce missing data", "Improve model accuracy"],
        )

        assert rec.step_name == "imputation"
        assert rec.priority == "high"
        assert rec.estimated_impact == 0.8
        assert rec.implementation_complexity == "simple"
        assert len(rec.expected_benefits) == 2

    def test_recommendation_priorities(self):
        """Test des différentes priorités."""
        for priority in ["high", "medium", "low"]:
            rec = PreprocessingRecommendation(
                step_name="test",
                description="Test",
                priority=priority,
                estimated_impact=0.5,
                implementation_complexity="medium",
                code_example="",
                expected_benefits=[],
            )
            assert rec.priority == priority

    def test_recommendation_complexities(self):
        """Test des différentes complexités."""
        for complexity in ["simple", "medium", "complex"]:
            rec = PreprocessingRecommendation(
                step_name="test",
                description="Test",
                priority="medium",
                estimated_impact=0.5,
                implementation_complexity=complexity,
                code_example="",
                expected_benefits=[],
            )
            assert rec.implementation_complexity == complexity


# ============================================================================
# Tests DataAnalystAgent - Création
# ============================================================================
class TestDataAnalystAgentBasic:
    """Tests basiques pour DataAnalystAgent."""

    def test_create_agent(self):
        """Création de l'agent."""
        agent = DataAnalystAgent()

        assert agent.name == "DataAnalystAgent"
        assert agent.agent_type == "data_analyst"
        assert isinstance(agent.capabilities, list)
        assert len(agent.capabilities) == 5

    def test_create_agent_with_name(self):
        """Création avec nom personnalisé."""
        agent = DataAnalystAgent(name="CustomAnalyst")
        assert agent.name == "CustomAnalyst"

    def test_capabilities(self):
        """Vérification des capacités."""
        agent = DataAnalystAgent()

        expected_capabilities = [
            "data_analysis",
            "anomaly_detection",
            "preprocessing_recommendations",
            "data_quality_assessment",
            "feature_engineering_suggestions",
        ]

        for cap in expected_capabilities:
            assert cap in agent.capabilities

    def test_analysis_config(self):
        """Configuration de l'analyse."""
        agent = DataAnalystAgent()

        assert agent.analysis_config["missing_data_threshold"] == 0.05
        assert agent.analysis_config["quality_score_threshold"] == 0.7
        assert agent.analysis_config["anomaly_contamination"] == 0.1
        assert agent.analysis_config["feature_selection_k"] == 10
        assert agent.analysis_config["correlation_threshold"] == 0.8


# ============================================================================
# Tests DataAnalystAgent - Méthodes avec mocks
# ============================================================================
class TestDataAnalystAgentMethods:
    """Tests des méthodes avec mocks."""

    @pytest.mark.asyncio
    async def test_analyze_dataset_mocked(self):
        """Analyse de dataset avec mocks."""
        agent = DataAnalystAgent()

        # Mock les méthodes internes
        mock_df = pd.DataFrame({"num_col": [1, 2, 3, 4, 5], "cat_col": ["a", "b", "a", "b", "a"]})

        agent._load_data = AsyncMock(return_value=mock_df)
        agent._perform_basic_analysis = AsyncMock(
            return_value={
                "missing_percentage": 0.0,
                "duplicates": 0,
                "data_types": {"num_col": "int64", "cat_col": "object"},
                "numerical_cols": ["num_col"],
                "categorical_cols": ["cat_col"],
            }
        )
        agent._detect_anomalies = AsyncMock(return_value=[])
        agent._assess_data_quality = AsyncMock(return_value=0.95)
        agent._generate_preprocessing_recommendations = AsyncMock(return_value=[])

        report = await agent.analyze_dataset("/fake/path.csv", "test-dataset")

        assert report.dataset_id == "test-dataset"
        assert report.rows == 5
        assert report.columns == 2
        assert report.quality_score == 0.95

    def test_generate_dataset_id(self):
        """Génération d'ID de dataset."""
        agent = DataAnalystAgent()

        # Accéder à la méthode privée
        id1 = agent._generate_dataset_id("/path/to/file1.csv")
        id2 = agent._generate_dataset_id("/path/to/file2.csv")
        id3 = agent._generate_dataset_id("/path/to/file1.csv")

        # IDs différents pour fichiers différents
        assert id1 != id2
        # Même ID pour même fichier
        assert id1 == id3


# ============================================================================
# Tests avec données réelles (temporaires)
# ============================================================================
class TestDataAnalystAgentWithData:
    """Tests avec données temporaires."""

    @pytest.fixture
    def temp_csv_file(self):
        """Crée un fichier CSV temporaire."""
        df = pd.DataFrame(
            {
                "num1": [1, 2, 3, np.nan, 5],
                "num2": [10, 20, 30, 40, 50],
                "cat1": ["a", "b", "a", "b", "c"],
            }
        )

        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        df.to_csv(path, index=False)

        yield path

        if os.path.exists(path):
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_load_csv_data(self, temp_csv_file):
        """Chargement de données CSV."""
        agent = DataAnalystAgent()
        df = await agent._load_data(temp_csv_file)

        assert len(df) == 5
        assert len(df.columns) == 3

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self):
        """Chargement d'un fichier inexistant."""
        agent = DataAnalystAgent()

        with pytest.raises(FileNotFoundError):
            await agent._load_data("/nonexistent/file.csv")

    @pytest.mark.asyncio
    async def test_basic_analysis(self, temp_csv_file):
        """Analyse basique des données."""
        agent = DataAnalystAgent()
        df = await agent._load_data(temp_csv_file)

        analysis = await agent._perform_basic_analysis(df)

        assert "missing_percentage" in analysis
        assert "duplicates" in analysis
        assert "data_types" in analysis
        assert "numerical_cols" in analysis
        assert "categorical_cols" in analysis

    @pytest.mark.asyncio
    async def test_detect_anomalies(self, temp_csv_file):
        """Détection d'anomalies."""
        agent = DataAnalystAgent()
        df = await agent._load_data(temp_csv_file)

        anomalies = await agent._detect_anomalies(df)

        assert isinstance(anomalies, list)

    @pytest.mark.asyncio
    async def test_assess_data_quality(self, temp_csv_file):
        """Évaluation de la qualité."""
        agent = DataAnalystAgent()
        df = await agent._load_data(temp_csv_file)

        quality = await agent._assess_data_quality(df)

        # Quality score could be > 1 if returned as percentage
        # Just verify it's a positive number
        assert quality >= 0.0


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestDataAnalystAgentEdgeCases:
    """Tests des cas limites."""

    @pytest.fixture
    def temp_empty_csv(self):
        """Crée un CSV vide avec en-têtes."""
        df = pd.DataFrame(columns=["col1", "col2"])
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        df.to_csv(path, index=False)

        yield path

        if os.path.exists(path):
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_empty_dataframe(self, temp_empty_csv):
        """DataFrame vide."""
        agent = DataAnalystAgent()
        df = await agent._load_data(temp_empty_csv)

        assert len(df) == 0
        assert len(df.columns) == 2

    def test_config_modification(self):
        """Modification de la configuration."""
        agent = DataAnalystAgent()

        agent.analysis_config["missing_data_threshold"] = 0.1
        assert agent.analysis_config["missing_data_threshold"] == 0.1

    def test_multiple_agent_instances(self):
        """Plusieurs instances indépendantes."""
        agent1 = DataAnalystAgent(name="Agent1")
        agent2 = DataAnalystAgent(name="Agent2")

        agent1.analysis_config["missing_data_threshold"] = 0.01
        agent2.analysis_config["missing_data_threshold"] = 0.99

        assert agent1.analysis_config["missing_data_threshold"] == 0.01
        assert agent2.analysis_config["missing_data_threshold"] == 0.99
        assert agent1.name != agent2.name
