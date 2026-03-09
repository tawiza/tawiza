#!/usr/bin/env python3
"""
DataAnalystAgent - Agent spécialisé dans l'analyse de données pour Tawiza-V2
Analyse intelligente, détection d'anomalies, recommandations de preprocessing
"""

import hashlib
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer

# import seaborn as sns  # Temporairement commenté

# Configuration du logging

@dataclass
class DataAnalysisReport:
    """Rapport complet d'analyse de données"""
    dataset_id: str
    file_path: str
    rows: int
    columns: int
    missing_data_percentage: float
    duplicate_rows: int
    data_types: dict[str, str]
    numerical_columns: list[str]
    categorical_columns: list[str]
    quality_score: float
    recommendations: list[str]
    anomalies_detected: list[dict[str, Any]]
    preprocessing_suggestions: list[dict[str, Any]]
    generated_at: float

@dataclass
class PreprocessingRecommendation:
    """Recommandation de preprocessing"""
    step_name: str
    description: str
    priority: str  # high, medium, low
    estimated_impact: float  # 0.0 to 1.0
    implementation_complexity: str  # simple, medium, complex
    code_example: str
    expected_benefits: list[str]

class DataAnalystAgent:
    """Agent spécialisé dans l'analyse et le preprocessing des données"""

    def __init__(self, name: str = "DataAnalystAgent"):
        self.name = name
        self.agent_type = "data_analyst"
        self.capabilities = [
            "data_analysis",
            "anomaly_detection",
            "preprocessing_recommendations",
            "data_quality_assessment",
            "feature_engineering_suggestions"
        ]

        # Configuration des analyses
        self.analysis_config = {
            "missing_data_threshold": 0.05,  # 5%
            "quality_score_threshold": 0.7,  # 70%
            "anomaly_contamination": 0.1,    # 10%
            "feature_selection_k": 10,       # Top 10 features
            "correlation_threshold": 0.8,    # 80% correlation
        }

        # Modèles d'analyse
        self.anomaly_detector = None
        self.quality_scorer = None

    async def analyze_dataset(self, file_path: str, dataset_id: str = None) -> DataAnalysisReport:
        """Analyser complètement un dataset"""
        logger.info(f"🔍 Analyse du dataset: {file_path}")

        if dataset_id is None:
            dataset_id = self._generate_dataset_id(file_path)

        try:
            # Charger les données
            df = await self._load_data(file_path)

            # Analyse de base
            basic_analysis = await self._perform_basic_analysis(df)

            # Détection d'anomalies
            anomalies = await self._detect_anomalies(df)

            # Évaluation de la qualité
            quality_score = await self._assess_data_quality(df)

            # Recommandations de preprocessing
            recommendations = await self._generate_preprocessing_recommendations(df, quality_score)

            # Créer le rapport complet
            report = DataAnalysisReport(
                dataset_id=dataset_id,
                file_path=file_path,
                rows=len(df),
                columns=len(df.columns),
                missing_data_percentage=basic_analysis["missing_percentage"],
                duplicate_rows=basic_analysis["duplicates"],
                data_types=basic_analysis["data_types"],
                numerical_columns=basic_analysis["numerical_cols"],
                categorical_columns=basic_analysis["categorical_cols"],
                quality_score=quality_score,
                recommendations=[rec.description for rec in recommendations],
                anomalies_detected=anomalies,
                preprocessing_suggestions=[asdict(rec) for rec in recommendations],
                generated_at=time.time()
            )

            logger.info(f"✅ Analyse complétée pour {dataset_id}")
            return report

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'analyse de {file_path}: {str(e)}")
            raise

    async def _load_data(self, file_path: str) -> pd.DataFrame:
        """Charger les données depuis différents formats"""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Fichier non trouvé: {file_path}")

        try:
            if file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
            elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            elif file_path.suffix.lower() == '.json':
                df = pd.read_json(file_path)
            elif file_path.suffix.lower() == '.jsonl':
                df = pd.read_json(file_path, lines=True)
            elif file_path.suffix.lower() == '.parquet':
                df = pd.read_parquet(file_path)
            else:
                raise ValueError(f"Format de fichier non supporté: {file_path.suffix}")

            logger.info(f"📊 Données chargées: {len(df)} lignes, {len(df.columns)} colonnes")
            return df

        except Exception as e:
            logger.error(f"❌ Erreur lors du chargement des données: {str(e)}")
            raise

    async def _perform_basic_analysis(self, df: pd.DataFrame) -> dict[str, Any]:
        """Effectuer l'analyse de base du dataset"""
        logger.info("🔍 Analyse de base en cours...")

        # Informations de base
        total_rows = len(df)
        total_columns = len(df.columns)

        # Données manquantes
        missing_data = df.isnull().sum()
        missing_percentage = (missing_data.sum() / (total_rows * total_columns)) * 100

        # Doublons
        duplicate_rows = df.duplicated().sum()

        # Types de données
        data_types = {col: str(df[col].dtype) for col in df.columns}

        # Colonnes numériques et catégorielles
        numerical_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

        # Statistiques de base pour les colonnes numériques
        numerical_stats = {}
        for col in numerical_cols:
            numerical_stats[col] = {
                "mean": float(df[col].mean()),
                "std": float(df[col].std()),
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "missing": int(df[col].isnull().sum())
            }

        analysis = {
            "rows": total_rows,
            "columns": total_columns,
            "missing_percentage": missing_percentage,
            "duplicates": duplicate_rows,
            "data_types": data_types,
            "numerical_cols": numerical_cols,
            "categorical_cols": categorical_cols,
            "numerical_stats": numerical_stats
        }

        logger.info(f"📊 Analyse de base complétée: {missing_percentage:.1f}% de données manquantes")
        return analysis

    async def _detect_anomalies(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """Détecter les anomalies dans le dataset"""
        logger.info("🔍 Détection d'anomalies en cours...")

        anomalies = []
        numerical_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        if not numerical_cols:
            logger.info("ℹ️ Aucune colonne numérique pour la détection d'anomalies")
            return anomalies

        try:
            # Préparer les données numériques
            numerical_data = df[numerical_cols].copy()

            # Imputer les valeurs manquantes pour l'anomaly detection
            imputer = SimpleImputer(strategy='mean')
            numerical_data_imputed = imputer.fit_transform(numerical_data)

            # Détection d'anomalies avec Isolation Forest
            iso_forest = IsolationForest(
                contamination=self.analysis_config["anomaly_contamination"],
                random_state=42
            )

            anomaly_labels = iso_forest.fit_predict(numerical_data_imputed)
            anomaly_scores = iso_forest.decision_function(numerical_data_imputed)

            # Identifier les anomalies (label -1)
            anomaly_indices = np.where(anomaly_labels == -1)[0]

            for idx in anomaly_indices[:10]:  # Limiter à 10 anomalies pour la clarté
                row_data = df.iloc[idx]
                anomaly_info = {
                    "row_index": int(idx),
                    "anomaly_score": float(anomaly_scores[idx]),
                    "affected_columns": [],
                    "description": "Donnée anormale détectée"
                }

                # Identifier les colonnes affectées
                for col in numerical_cols:
                    if pd.isna(row_data[col]) or abs(row_data[col] - numerical_data[col].mean()) > 3 * numerical_data[col].std():
                        anomaly_info["affected_columns"].append(col)

                anomalies.append(anomaly_info)

            logger.info(f"🔍 {len(anomalies)} anomalies détectées")
            return anomalies

        except Exception as e:
            logger.error(f"❌ Erreur lors de la détection d'anomalies: {str(e)}")
            return []

    async def _assess_data_quality(self, df: pd.DataFrame) -> float:
        """Évaluer la qualité des données"""
        logger.info("📊 Évaluation de la qualité des données...")

        quality_score = 1.0  # Score de base

        try:
            # Facteur 1: Complétude des données (absence de valeurs manquantes)
            missing_percentage = (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
            completeness_score = max(0, 1 - (missing_percentage / 100))

            # Facteur 2: Cohérence (absence de doublons)
            duplicate_percentage = (df.duplicated().sum() / len(df)) * 100
            consistency_score = max(0, 1 - (duplicate_percentage / 100))

            # Facteur 3: Validité des types de données
            validity_score = 1.0  # Pour l'instant, on considère que c'est valide

            # Facteur 4: Distribution des données (pas trop skewed)
            numerical_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            distribution_score = 1.0

            if numerical_cols:
                skew_scores = []
                for col in numerical_cols:
                    if df[col].std() > 0:  # Éviter la division par zéro
                        skewness = df[col].skew()
                        # Score basé sur le skewness (0 = parfait, >2 ou <-2 = problématique)
                        skew_score = max(0, 1 - abs(skewness) / 3)
                        skew_scores.append(skew_score)

                if skew_scores:
                    distribution_score = sum(skew_scores) / len(skew_scores)

            # Score final pondéré
            quality_score = (
                completeness_score * 0.4 +
                consistency_score * 0.3 +
                validity_score * 0.2 +
                distribution_score * 0.1
            )

            # Normaliser sur 100
            quality_score = min(quality_score * 100, 100)

            logger.info(f"📊 Score de qualité: {quality_score:.1f}/100")
            return quality_score

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'évaluation de la qualité: {str(e)}")
            return 50.0  # Score par défaut en cas d'erreur

    async def _generate_preprocessing_recommendations(self, df: pd.DataFrame, quality_score: float) -> list[PreprocessingRecommendation]:
        """Générer des recommandations de preprocessing intelligentes"""
        logger.info("🎯 Génération de recommandations de preprocessing...")

        recommendations = []

        try:
            # Analyse des données manquantes
            missing_data = df.isnull().sum()
            total_cells = len(df) * len(df.columns)
            missing_percentage = (missing_data.sum() / total_cells) * 100

            if missing_percentage > 5:
                recommendations.append(PreprocessingRecommendation(
                    step_name="Gestion des données manquantes",
                    description=f"{missing_percentage:.1f}% de données manquantes détectées. Imputation intelligente recommandée.",
                    priority="high",
                    estimated_impact=0.8,
                    implementation_complexity="medium",
                    code_example="""
# Imputation intelligente des données manquantes
from sklearn.impute import KNNImputer
imputer = KNNImputer(n_neighbors=5)
df_imputed = imputer.fit_transform(df[numerical_cols])
""",
                    expected_benefits=["Amélioration de la qualité des données", "Meilleures performances du modèle", "Réduction des biais"]
                ))

            # Analyse des doublons
            duplicate_percentage = (df.duplicated().sum() / len(df)) * 100
            if duplicate_percentage > 1:
                recommendations.append(PreprocessingRecommendation(
                    step_name="Suppression des doublons",
                    description=f"{duplicate_percentage:.1f}% de lignes dupliquées détectées.",
                    priority="medium",
                    estimated_impact=0.6,
                    implementation_complexity="simple",
                    code_example="""
# Suppression des doublons
df_cleaned = df.drop_duplicates()
""",
                    expected_benefits=["Données plus propres", "Réduction de la taille du dataset", "Élimination du biais"]
                ))

            # Analyse des colonnes numériques
            numerical_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if numerical_cols:
                # Normalisation si nécessaire
                recommendations.append(PreprocessingRecommendation(
                    step_name="Normalisation des données numériques",
                    description=f"Normalisation des {len(numerical_cols)} colonnes numériques pour optimisation GPU.",
                    priority="medium",
                    estimated_impact=0.7,
                    implementation_complexity="simple",
                    code_example="""
# Normalisation pour GPU acceleration
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
df_scaled = scaler.fit_transform(df[numerical_cols])
""",
                    expected_benefits=["Optimisation GPU", "Convergence plus rapide", "Stabilité numérique"]
                ))

            # Analyse des colonnes catégorielles
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
            if categorical_cols:
                recommendations.append(PreprocessingRecommendation(
                    step_name="Encodage des variables catégorielles",
                    description=f"Encodage intelligent des {len(categorical_cols)} colonnes catégorielles.",
                    priority="medium",
                    estimated_impact=0.6,
                    implementation_complexity="medium",
                    code_example="""
# Encodage intelligent
from sklearn.preprocessing import LabelEncoder
encoders = {}
for col in categorical_cols:
    if df[col].nunique() < 10:  # Peu de catégories
        encoders[col] = LabelEncoder()
        df[col] = encoders[col].fit_transform(df[col])
""",
                    expected_benefits=["Compatibilité avec les algorithmes", "Réduction de la dimension", "Meilleure performance"]
                ))

            # Sélection de features si beaucoup de colonnes
            if len(df.columns) > 20:
                recommendations.append(PreprocessingRecommendation(
                    step_name="Sélection de features",
                    description=f"Sélection des features les plus pertinentes parmi {len(df.columns)} colonnes.",
                    priority="medium",
                    estimated_impact=0.8,
                    implementation_complexity="medium",
                    code_example="""
# Sélection de features
from sklearn.feature_selection import SelectKBest, f_classif
selector = SelectKBest(f_classif, k=15)
X_selected = selector.fit_transform(X, y)
""",
                    expected_benefits=["Réduction de la complexité", "Amélioration de la vitesse", "Évitement du overfitting"]
                ))

            # Recommandations basées sur le score de qualité
            if quality_score < 70:
                recommendations.append(PreprocessingRecommendation(
                    step_name="Amélioration globale de la qualité",
                    description=f"Score de qualité de {quality_score:.1f}/100. Amélioration globale recommandée.",
                    priority="high",
                    estimated_impact=0.9,
                    implementation_complexity="complex",
                    code_example="""
# Pipeline complet d'amélioration
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import KNNImputer

pipeline = Pipeline([
    ('imputer', KNNImputer(n_neighbors=5)),
    ('scaler', StandardScaler()),
    ('feature_selection', SelectKBest(f_classif, k=20))
])
""",
                    expected_benefits=["Amélioration significative de la qualité", "Meilleures performances du modèle", "Réduction des erreurs"]
                ))

            logger.info(f"🎯 {len(recommendations)} recommandations générées")
            return recommendations

        except Exception as e:
            logger.error(f"❌ Erreur lors de la génération des recommandations: {str(e)}")
            return []

    def _generate_dataset_id(self, file_path: str) -> str:
        """Générer un ID unique pour un dataset"""
        file_path = str(file_path)
        timestamp = str(int(time.time() * 1000))
        content_hash = hashlib.md5(f"{file_path}{timestamp}".encode()).hexdigest()[:8]
        return f"dataset_{content_hash}_{timestamp}"

    async def generate_data_report(self, analysis_report: DataAnalysisReport) -> str:
        """Générer un rapport détaillé en format markdown"""
        report_lines = [
            f"# Rapport d'Analyse de Données - {analysis_report.dataset_id}",
            f"\n**Fichier:** {analysis_report.file_path}",
            f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(analysis_report.generated_at))}",
            "\n## Résumé",
            f"- **Dimensions:** {analysis_report.rows} lignes × {analysis_report.columns} colonnes",
            f"- **Données manquantes:** {analysis_report.missing_data_percentage:.1f}%",
            f"- **Doublons:** {analysis_report.duplicate_rows} lignes",
            f"- **Score de qualité:** {analysis_report.quality_score:.1f}/100",
            "\n## Colonnes Analysées",
        ]

        # Ajouter les colonnes numériques
        if analysis_report.numerical_columns:
            report_lines.append("\n### Colonnes Numériques")
            for col in analysis_report.numerical_columns:
                report_lines.append(f"- {col}")

        # Ajouter les colonnes catégorielles
        if analysis_report.categorical_columns:
            report_lines.append("\n### Colonnes Catégorielles")
            for col in analysis_report.categorical_columns:
                report_lines.append(f"- {col}")

        # Ajouter les recommandations
        if analysis_report.recommendations:
            report_lines.extend([
                "\n## Recommandations de Preprocessing",
                ""
            ])
            for i, rec in enumerate(analysis_report.recommendations, 1):
                report_lines.append(f"{i}. **{rec}**")

        # Ajouter les anomalies
        if analysis_report.anomalies_detected:
            report_lines.extend([
                "\n## Anomalies Détectées",
                ""
            ])
            for anomaly in analysis_report.anomalies_detected:
                report_lines.append(f"- Ligne {anomaly['row_index']}: {anomaly['description']}")

        return "\\n".join(report_lines)

    def get_capabilities(self) -> list[str]:
        """Obtenir les capacités de l'agent"""
        return [
            "Analyse complète de datasets",
            "Détection intelligente d'anomalies",
            "Évaluation de la qualité des données",
            "Génération de recommandations de preprocessing",
            "Création de rapports détaillés",
            "Support multiple formats de fichiers",
            "Optimisation pour GPU acceleration"
        ]

# Classe pour intégration avec le système multi-agents
class DataAnalystAgentIntegration:
    """Intégration de DataAnalystAgent avec le système multi-agents"""

    def __init__(self, multi_agent_system):
        self.multi_agent_system = multi_agent_system
        self.data_analyst = DataAnalystAgent()

    def register_with_system(self):
        """Enregistrer l'agent avec le système multi-agents"""
        self.data_analyst.capabilities = self.data_analyst.get_capabilities()
        self.multi_agent_system.coordinator.register_agent(self.data_analyst)
        logger.info(f"✅ {self.data_analyst.name} enregistré dans le système multi-agents")

    async def analyze_data_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Exécuter une tâche d'analyse de données"""
        try:
            file_path = task_data.get("file_path")
            dataset_id = task_data.get("dataset_id")

            if not file_path:
                return {"error": "Chemin du fichier requis", "success": False}

            # Exécuter l'analyse
            report = await self.data_analyst.analyze_dataset(file_path, dataset_id)

            return {
                "success": True,
                "report": asdict(report),
                "summary": f"Analyse complétée pour {report.dataset_id}",
                "key_findings": [
                    f"Score de qualité: {report.quality_score:.1f}/100",
                    f"{len(report.recommendations)} recommandations générées",
                    f"{len(report.anomalies_detected)} anomalies détectées"
                ]
            }

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'analyse: {str(e)}")
            return {"error": str(e), "success": False}

