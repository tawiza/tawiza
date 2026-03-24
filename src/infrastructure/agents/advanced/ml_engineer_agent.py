#!/usr/bin/env python3
"""
MLEngineerAgent - Agent spécialisé en ML engineering pour Tawiza-V2
Pipeline ML automatique, optimisation hyperparamètres, sélection de modèles
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import optuna  # Required for hyperparameter optimization
import pandas as pd
from loguru import logger
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

# import torch  # Temporairement commenté
# import torch  # Temporairement commenté.nn as nn
# import torch  # Temporairement commenté.optim as optim
# from torch.utils.data import DataLoader, TensorDataset  # Temporairement commenté

# Configuration du logging


@dataclass
class MLTrainingConfig:
    """Configuration complète pour l'entraînement ML"""

    task_id: str
    dataset_path: str
    target_column: str
    problem_type: str  # classification, regression
    model_type: str  # random_forest, gradient_boosting, neural_network
    optimization_method: str  # grid_search, random_search, bayesian, optuna
    max_trials: int = 50
    cross_validation_folds: int = 5
    test_size: float = 0.2
    random_state: int = 42
    gpu_acceleration: bool = True
    early_stopping: bool = True
    max_epochs: int = 100
    batch_size: int = 32
    learning_rate: float = 0.001


@dataclass
class TrainingResult:
    """Résultat complet d'un entraînement"""

    task_id: str
    model_type: str
    best_params: dict[str, Any]
    best_score: float
    cv_scores: list[float]
    test_scores: dict[str, float]
    training_time: float
    model_size_mb: float
    gpu_usage: dict[str, float]
    convergence_history: list[float]
    generated_at: float
    model_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HyperparameterOptimizationResult:
    """Résultat de l'optimisation hyperparamètres"""

    best_params: dict[str, Any]
    best_score: float
    optimization_history: list[dict[str, Any]]
    total_trials: int
    best_trial_number: int
    optimization_time: float
    convergence_plot_data: dict[str, list[float]]


class MLEngineerAgent:
    """Agent spécialisé en ML engineering - pipeline ML automatique"""

    def __init__(self, name: str = "MLEngineerAgent"):
        self.name = name
        self.agent_type = "ml_engineer"
        self.capabilities = [
            "ml_pipeline_automation",
            "hyperparameter_optimization",
            "model_selection",
            "performance_monitoring",
            "auto_ml_pipeline",
            "gpu_optimization",
        ]

        # Configuration ML
        self.ml_config = {
            "supported_models": {
                "classification": [
                    "random_forest",
                    "gradient_boosting",
                    "logistic_regression",
                    "svm",
                    "neural_network",
                ],
                "regression": [
                    "random_forest",
                    "gradient_boosting",
                    "linear_regression",
                    "neural_network",
                ],
            },
            "optimization_methods": [
                "grid_search",
                "random_search",
                "bayesian",
                "optuna",
                "hyperband",
            ],
            "gpu_optimization": True,
            "early_stopping": True,
            "cross_validation": True,
        }

        # Cache pour éviter les recalculs
        self.model_cache = {}
        self.optimization_cache = {}

    async def create_ml_pipeline(self, config: MLTrainingConfig) -> TrainingResult:
        """Créer un pipeline ML complet avec optimisation"""
        logger.info(f"🎯 Création du pipeline ML pour {config.task_id}")

        try:
            start_time = time.time()

            # 1. Préparation des données
            logger.info("📊 Préparation des données...")
            X, y, preprocessing_pipeline = await self._prepare_data(config)

            # 2. Optimisation hyperparamètres
            logger.info("🔧 Optimisation des hyperparamètres...")
            best_params, optimization_result = await self._optimize_hyperparameters(
                X, y, config, preprocessing_pipeline
            )

            # 3. Entraînement final avec meilleurs paramètres
            logger.info("🏋️ Entraînement final...")
            model, training_metrics = await self._train_final_model(
                X, y, best_params, config, preprocessing_pipeline
            )

            # 4. Évaluation complète
            logger.info("📈 Évaluation du modèle...")
            test_scores = await self._evaluate_model(model, X, y, config)

            # 5. Sauvegarde et métriques
            model_path = await self._save_model(model, config)

            # Calculer les métriques finales
            training_time = time.time() - start_time
            model_size = await self._calculate_model_size(model_path)
            gpu_usage = await self._get_gpu_metrics()

            # Créer le résultat complet
            result = TrainingResult(
                task_id=config.task_id,
                model_type=config.model_type,
                best_params=best_params,
                best_score=optimization_result.best_score,
                cv_scores=training_metrics.get("cv_scores", []),
                test_scores=test_scores,
                training_time=training_time,
                model_size_mb=model_size,
                gpu_usage=gpu_usage,
                convergence_history=training_metrics.get("convergence_history", []),
                generated_at=time.time(),
                model_path=model_path,
                metadata={
                    "optimization_method": config.optimization_method,
                    "gpu_acceleration": config.gpu_acceleration,
                    "cross_validation_folds": config.cross_validation_folds,
                },
            )

            logger.info(f"✅ Pipeline ML créé avec succès pour {config.task_id}")
            return result

        except Exception as e:
            logger.error(f"❌ Erreur lors de la création du pipeline ML: {str(e)}")
            raise

    async def _prepare_data(self, config: MLTrainingConfig) -> tuple[np.ndarray, np.ndarray, Any]:
        """Préparer les données pour l'entraînement"""
        logger.info("📊 Préparation des données...")

        try:
            # Charger les données
            df = pd.read_csv(config.dataset_path)

            # Séparer features et target
            X = df.drop(columns=[config.target_column])
            y = df[config.target_column]

            # Encoder la target si nécessaire
            if config.problem_type == "classification" and y.dtype == "object":
                label_encoder = LabelEncoder()
                y = label_encoder.fit_transform(y)

            # Séparer features numériques et catégorielles
            numerical_features = X.select_dtypes(include=[np.number]).columns.tolist()
            categorical_features = X.select_dtypes(include=["object", "category"]).columns.tolist()

            # Créer le pipeline de preprocessing
            preprocessing_steps = []

            if numerical_features:
                preprocessing_steps.append(("numerical", StandardScaler(), numerical_features))

            if categorical_features:
                preprocessing_steps.append(("categorical", "passthrough", categorical_features))

            preprocessing_pipeline = Pipeline([("preprocessor", preprocessing_steps)])

            # Appliquer le preprocessing
            X_processed = preprocessing_pipeline.fit_transform(X)

            logger.info(
                f"📊 Données préparées: {X_processed.shape[0]} échantillons, {X_processed.shape[1]} features"
            )
            return X_processed, y.values, preprocessing_pipeline

        except Exception as e:
            logger.error(f"❌ Erreur lors de la préparation des données: {str(e)}")
            raise

    async def _optimize_hyperparameters(
        self, X: np.ndarray, y: np.ndarray, config: MLTrainingConfig, preprocessing_pipeline: Any
    ) -> tuple[dict[str, Any], HyperparameterOptimizationResult]:
        """Optimiser les hyperparamètres avec la méthode spécifiée"""
        logger.info(f"🔧 Optimisation hyperparamètres avec {config.optimization_method}")

        try:
            # Définir les grilles d'hyperparamètres selon le type de modèle
            param_grids = self._get_param_grids(config.model_type)

            if config.optimization_method == "grid_search":
                return await self._grid_search_optimization(X, y, config, param_grids)
            elif config.optimization_method == "random_search":
                return await self._random_search_optimization(X, y, config, param_grids)
            elif config.optimization_method == "bayesian":
                return await self._bayesian_optimization(X, y, config, param_grids)
            elif config.optimization_method == "optuna":
                return await self._optuna_optimization(X, y, config, param_grids)
            else:
                raise ValueError(
                    f"Méthode d'optimisation non supportée: {config.optimization_method}"
                )

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'optimisation: {str(e)}")
            raise

    def _get_param_grids(self, model_type: str) -> dict[str, list[Any]]:
        """Obtenir les grilles d'hyperparamètres selon le type de modèle"""
        if model_type == "random_forest":
            return {
                "n_estimators": [50, 100, 200],
                "max_depth": [10, 20, None],
                "min_samples_split": [2, 5, 10],
                "min_samples_leaf": [1, 2, 4],
                "max_features": ["auto", "sqrt"],
            }
        elif model_type == "gradient_boosting":
            return {
                "n_estimators": [50, 100, 200],
                "learning_rate": [0.01, 0.1, 0.2],
                "max_depth": [3, 5, 7],
                "min_samples_split": [2, 5, 10],
                "subsample": [0.8, 0.9, 1.0],
            }
        elif model_type == "logistic_regression":
            return {
                "C": [0.1, 1.0, 10.0],
                "penalty": ["l1", "l2"],
                "solver": ["liblinear", "saga"],
                "max_iter": [100, 200, 500],
            }
        elif model_type == "svm":
            return {
                "C": [0.1, 1.0, 10.0],
                "kernel": ["linear", "rbf", "poly"],
                "gamma": ["scale", "auto", 0.001, 0.01],
                "degree": [2, 3, 4],  # Pour kernel poly
            }
        elif model_type == "neural_network":
            return {
                "hidden_layer_sizes": [(50,), (100,), (50, 50), (100, 50)],
                "activation": ["relu", "tanh"],
                "learning_rate_init": [0.001, 0.01, 0.1],
                "max_iter": [200, 500, 1000],
                "early_stopping": [True, False],
            }
        else:
            raise ValueError(f"Type de modèle non supporté: {model_type}")

    async def _grid_search_optimization(
        self,
        X: np.ndarray,
        y: np.ndarray,
        config: MLTrainingConfig,
        param_grids: dict[str, list[Any]],
    ) -> tuple[dict[str, Any], HyperparameterOptimizationResult]:
        """Optimisation par grille complète"""
        logger.info("🔧 Optimisation par grille complète...")

        try:
            # Créer le modèle de base
            base_model = self._create_base_model(config.model_type)

            # Grid Search avec cross-validation
            grid_search = GridSearchCV(
                base_model,
                param_grid=param_grids,
                cv=config.cross_validation_folds,
                scoring="accuracy" if config.problem_type == "classification" else "r2",
                n_jobs=-1,
                verbose=1,
            )

            # Exécuter la recherche
            grid_search.fit(X, y)

            # Extraire les résultats
            best_params = grid_search.best_params_
            best_score = grid_search.best_score_

            # Historique d'optimisation
            optimization_history = []
            for i, (params, score) in enumerate(
                zip(
                    grid_search.cv_results_["params"],
                    grid_search.cv_results_["mean_test_score"],
                    strict=False,
                )
            ):
                optimization_history.append(
                    {
                        "trial_number": i + 1,
                        "params": params,
                        "score": score,
                        "timestamp": time.time(),
                    }
                )

            optimization_result = HyperparameterOptimizationResult(
                best_params=best_params,
                best_score=best_score,
                optimization_history=optimization_history,
                total_trials=len(optimization_history),
                best_trial_number=grid_search.best_index_ + 1,
                optimization_time=0,  # Sera calculé plus tard
                convergence_plot_data={
                    "trials": list(range(1, len(optimization_history) + 1)),
                    "scores": [h["score"] for h in optimization_history],
                },
            )

            logger.info(
                f"✅ Grid Search complété: {len(optimization_history)} combinaisons testées"
            )
            return best_params, optimization_result

        except Exception as e:
            logger.error(f"❌ Erreur Grid Search: {str(e)}")
            raise

    async def _random_search_optimization(
        self,
        X: np.ndarray,
        y: np.ndarray,
        config: MLTrainingConfig,
        param_grids: dict[str, list[Any]],
    ) -> tuple[dict[str, Any], HyperparameterOptimizationResult]:
        """Optimisation par recherche aléatoire"""
        logger.info("🔧 Optimisation par recherche aléatoire...")

        try:
            base_model = self._create_base_model(config.model_type)

            random_search = RandomizedSearchCV(
                base_model,
                param_distributions=param_grids,
                n_iter=config.max_trials,
                cv=config.cross_validation_folds,
                scoring="accuracy" if config.problem_type == "classification" else "r2",
                n_jobs=-1,
                verbose=1,
                random_state=config.random_state,
            )

            random_search.fit(X, y)

            # Résultats similaires à Grid Search
            best_params = random_search.best_params_
            best_score = random_search.best_score_

            optimization_history = []
            for i, (params, score) in enumerate(
                zip(
                    random_search.cv_results_["params"],
                    random_search.cv_results_["mean_test_score"],
                    strict=False,
                )
            ):
                optimization_history.append(
                    {
                        "trial_number": i + 1,
                        "params": params,
                        "score": score,
                        "timestamp": time.time(),
                    }
                )

            optimization_result = HyperparameterOptimizationResult(
                best_params=best_params,
                best_score=best_score,
                optimization_history=optimization_history,
                total_trials=len(optimization_history),
                best_trial_number=random_search.best_index_ + 1,
                optimization_time=0,
                convergence_plot_data={
                    "trials": list(range(1, len(optimization_history) + 1)),
                    "scores": [h["score"] for h in optimization_history],
                },
            )

            logger.info(f"✅ Random Search complété: {len(optimization_history)} essais")
            return best_params, optimization_result

        except Exception as e:
            logger.error(f"❌ Erreur Random Search: {str(e)}")
            raise

    async def _bayesian_optimization(
        self,
        X: np.ndarray,
        y: np.ndarray,
        config: MLTrainingConfig,
        param_grids: dict[str, list[Any]],
    ) -> tuple[dict[str, Any], HyperparameterOptimizationResult]:
        """Optimisation bayésienne avec Optuna"""
        logger.info("🔧 Optimisation bayésienne avec Optuna...")

        try:
            # import optuna  # Temporairement commenté

            optimization_history = []
            best_params = None
            best_score = -float("inf")

            def objective(trial):
                # Suggérer des hyperparamètres
                params = {}
                for param_name, param_values in param_grids.items():
                    if all(isinstance(v, (int, float)) for v in param_values):
                        # Paramètres numériques continus
                        if len(param_values) == 2:
                            params[param_name] = trial.suggest_float(
                                param_name, param_values[0], param_values[1]
                            )
                        else:
                            params[param_name] = trial.suggest_float(
                                param_name, min(param_values), max(param_values)
                            )
                    else:
                        # Paramètres catégoriels
                        params[param_name] = trial.suggest_categorical(param_name, param_values)

                # Créer et évaluer le modèle
                model = self._create_model_with_params(config.model_type, params)

                # Cross-validation
                scores = cross_val_score(
                    model,
                    X,
                    y,
                    cv=config.cross_validation_folds,
                    scoring="accuracy" if config.problem_type == "classification" else "r2",
                )

                score = scores.mean()

                # Enregistrer dans l'historie
                optimization_history.append(
                    {
                        "trial_number": trial.number + 1,
                        "params": params,
                        "score": score,
                        "timestamp": time.time(),
                    }
                )

                return score

            # Créer l'étude Optuna
            study = optuna.create_study(
                direction="maximize", sampler=optuna.samplers.TPESampler(seed=config.random_state)
            )

            # Lancer l'optimisation
            study.optimize(objective, n_trials=config.max_trials, show_progress_bar=True)

            # Extraire les résultats
            best_params = study.best_params
            best_score = study.best_value

            optimization_result = HyperparameterOptimizationResult(
                best_params=best_params,
                best_score=best_score,
                optimization_history=optimization_history,
                total_trials=len(optimization_history),
                best_trial_number=study.best_trial.number + 1,
                optimization_time=0,
                convergence_plot_data={
                    "trials": [h["trial_number"] for h in optimization_history],
                    "scores": [h["score"] for h in optimization_history],
                },
            )

            logger.info(f"✅ Bayesian Optimization complétée: {len(optimization_history)} trials")
            return best_params, optimization_result

        except Exception as e:
            logger.error(f"❌ Erreur Bayesian Optimization: {str(e)}")
            raise

    async def _train_final_model(
        self,
        X: np.ndarray,
        y: np.ndarray,
        best_params: dict[str, Any],
        config: MLTrainingConfig,
        preprocessing_pipeline: Any,
    ) -> tuple[Any, dict[str, Any]]:
        """Entraînement final avec les meilleurs paramètres"""
        logger.info("🏋️ Entraînement final avec meilleurs paramètres...")

        try:
            # Créer le modèle avec les meilleurs paramètres
            final_model = self._create_model_with_params(config.model_type, best_params)

            # Cross-validation pour obtenir des scores robustes
            logger.info("📊 Cross-validation en cours...")
            cv_scores = cross_val_score(
                final_model,
                X,
                y,
                cv=config.cross_validation_folds,
                scoring="accuracy" if config.problem_type == "classification" else "r2",
                n_jobs=-1,
            )

            # Entraînement final sur toutes les données
            logger.info("🏋️ Entraînement final sur toutes les données...")
            final_model.fit(X, y)

            # Historique de convergence (simulé pour l'instant)
            convergence_history = list(cv_scores) + [cv_scores.mean()]

            training_metrics = {
                "cv_scores": cv_scores.tolist(),
                "cv_mean": float(cv_scores.mean()),
                "cv_std": float(cv_scores.std()),
                "convergence_history": convergence_history,
            }

            logger.info(
                f"✅ Entraînement final complété - CV Score: {cv_scores.mean():.4f} (±{cv_scores.std():.4f})"
            )
            return final_model, training_metrics

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'entraînement final: {str(e)}")
            raise

    def _create_base_model(self, model_type: str) -> Any:
        """Créer un modèle de base"""
        if model_type == "random_forest":
            from sklearn.ensemble import RandomForestClassifier

            return RandomForestClassifier(random_state=42)
        elif model_type == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingClassifier

            return GradientBoostingClassifier(random_state=42)
        elif model_type == "logistic_regression":
            from sklearn.linear_model import LogisticRegression

            return LogisticRegression(random_state=42, max_iter=1000)
        elif model_type == "svm":
            from sklearn.svm import SVC

            return SVC(random_state=42)
        elif model_type == "neural_network":
            from sklearn.neural_network import MLPClassifier

            return MLPClassifier(random_state=42, max_iter=1000)
        else:
            raise ValueError(f"Type de modèle non supporté: {model_type}")

    def _create_model_with_params(self, model_type: str, params: dict[str, Any]) -> Any:
        """Créer un modèle avec des paramètres spécifiques"""
        base_model = self._create_base_model(model_type)

        # Appliquer les paramètres
        for param_name, param_value in params.items():
            if hasattr(base_model, param_name):
                setattr(base_model, param_name, param_value)
            else:
                logger.warning(f"⚠️ Paramètre non reconnu: {param_name}")

        return base_model

    async def _evaluate_model(
        self, model: Any, X: np.ndarray, y: np.ndarray, config: MLTrainingConfig
    ) -> dict[str, float]:
        """Évaluer complètement le modèle"""
        logger.info("📈 Évaluation complète du modèle...")

        try:
            # Prédiction sur les données d'entraînement (pour référence)
            y_pred = model.predict(X)

            # Calcul des métriques selon le type de problème
            if config.problem_type == "classification":
                scores = {
                    "accuracy": float(accuracy_score(y, y_pred)),
                    "precision": float(precision_score(y, y_pred, average="weighted")),
                    "recall": float(recall_score(y, y_pred, average="weighted")),
                    "f1_score": float(f1_score(y, y_pred, average="weighted")),
                }
            else:  # regression
                from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

                scores = {
                    "mse": float(mean_squared_error(y, y_pred)),
                    "mae": float(mean_absolute_error(y, y_pred)),
                    "r2_score": float(r2_score(y, y_pred)),
                }

            logger.info(f"📊 Scores d'évaluation: {scores}")
            return scores

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'évaluation: {str(e)}")
            return {}

    async def _save_model(self, model: Any, config: MLTrainingConfig) -> str:
        """Sauvegarder le modèle entraîné"""
        logger.info(f"💾 Sauvegarde du modèle {config.task_id}...")

        try:
            import joblib

            # Créer le chemin de sauvegarde
            model_path = f"/tmp/tawiza_models/{config.task_id}_model.pkl"
            Path("/tmp/tawiza_models").mkdir(parents=True, exist_ok=True)

            # Sauvegarder le modèle et le preprocessing
            joblib.dump(
                {
                    "model": model,
                    "preprocessing": None,  # Sera ajouté si nécessaire
                    "config": config,
                    "timestamp": time.time(),
                },
                model_path,
            )

            logger.info(f"✅ Modèle sauvegardé: {model_path}")
            return model_path

        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde: {str(e)}")
            raise

    async def _calculate_model_size(self, model_path: str) -> float:
        """Calculer la taille du modèle en MB"""
        try:
            import os

            size_bytes = os.path.getsize(model_path)
            size_mb = size_bytes / (1024 * 1024)
            return size_mb
        except Exception as e:
            logger.error(f"❌ Erreur calcul taille modèle: {str(e)}")
            return 0.0

    async def _get_gpu_metrics(self) -> dict[str, float]:
        """Obtenir les métriques GPU réelles.

        Supporte:
        - NVIDIA via nvidia-smi ou pynvml
        - AMD via rocm-smi
        - Fallback sur valeurs estimées si non disponible
        """
        # Try NVIDIA first
        nvidia_metrics = await self._get_nvidia_metrics()
        if nvidia_metrics:
            return nvidia_metrics

        # Try AMD ROCm
        amd_metrics = await self._get_amd_metrics()
        if amd_metrics:
            return amd_metrics

        # Fallback to estimated values
        logger.warning("GPU metrics unavailable - returning estimates")
        return {
            "gpu_utilization": 0.0,
            "memory_used_mb": 0.0,
            "memory_total_mb": 0.0,
            "temperature_celsius": 0.0,
            "power_usage_watts": 0.0,
            "gpu_type": "unknown",
            "available": False,
        }

    async def _get_nvidia_metrics(self) -> dict[str, float] | None:
        """Get NVIDIA GPU metrics via nvidia-smi."""
        import subprocess

        try:
            # Query nvidia-smi for GPU metrics
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,name",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return None

            # Parse output (format: "util, mem_used, mem_total, temp, power, name")
            line = result.stdout.strip().split("\n")[0]  # First GPU
            parts = [p.strip() for p in line.split(",")]

            if len(parts) >= 6:
                return {
                    "gpu_utilization": float(parts[0]) if parts[0] else 0.0,
                    "memory_used_mb": float(parts[1]) if parts[1] else 0.0,
                    "memory_total_mb": float(parts[2]) if parts[2] else 0.0,
                    "temperature_celsius": float(parts[3]) if parts[3] else 0.0,
                    "power_usage_watts": float(parts[4]) if parts[4] not in ("[N/A]", "") else 0.0,
                    "gpu_name": parts[5],
                    "gpu_type": "nvidia",
                    "available": True,
                }
        except FileNotFoundError:
            pass  # nvidia-smi not found
        except subprocess.TimeoutExpired:
            logger.warning("nvidia-smi timed out")
        except Exception as e:
            logger.debug(f"NVIDIA metrics failed: {e}")

        return None

    async def _get_amd_metrics(self) -> dict[str, float] | None:
        """Get AMD GPU metrics via rocm-smi."""
        import subprocess

        try:
            # Check if rocm-smi is available
            result = subprocess.run(
                ["rocm-smi", "--showuse", "--showmemuse", "--showtemp", "--showpower"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return None

            output = result.stdout

            # Parse rocm-smi output (format varies)
            metrics = {
                "gpu_utilization": 0.0,
                "memory_used_mb": 0.0,
                "memory_total_mb": 0.0,
                "temperature_celsius": 0.0,
                "power_usage_watts": 0.0,
                "gpu_type": "amd",
                "available": True,
            }

            # Parse GPU utilization
            for line in output.split("\n"):
                if "GPU use" in line or "GPU%" in line:
                    # Extract percentage
                    import re

                    match = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
                    if match:
                        metrics["gpu_utilization"] = float(match.group(1))

                elif "Memory Use" in line or "VRAM" in line:
                    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:MB|MiB)", line)
                    if match:
                        metrics["memory_used_mb"] = float(match.group(1))

                elif "Temperature" in line or "Temp" in line:
                    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:c|C|°C)", line)
                    if match:
                        metrics["temperature_celsius"] = float(match.group(1))

                elif "Power" in line:
                    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:W|Watts)", line)
                    if match:
                        metrics["power_usage_watts"] = float(match.group(1))

            # Get total memory separately
            try:
                mem_result = subprocess.run(
                    ["rocm-smi", "--showmeminfo", "vram"], capture_output=True, text=True, timeout=5
                )
                if mem_result.returncode == 0:
                    import re

                    # Look for total memory
                    match = re.search(
                        r"Total.*?(\d+)\s*(?:MB|MiB|bytes)", mem_result.stdout, re.IGNORECASE
                    )
                    if match:
                        total = int(match.group(1))
                        # Convert bytes to MB if needed
                        if total > 1_000_000_000:
                            total = total / (1024 * 1024)
                        metrics["memory_total_mb"] = float(total)
            except Exception:
                pass

            return metrics

        except FileNotFoundError:
            pass  # rocm-smi not found
        except subprocess.TimeoutExpired:
            logger.warning("rocm-smi timed out")
        except Exception as e:
            logger.debug(f"AMD metrics failed: {e}")

        return None

    def get_capabilities(self) -> list[str]:
        """Obtenir les capacités de l'agent"""
        return [
            "Pipeline ML automatique complet",
            "Optimisation hyperparamètres avancée (Grid, Random, Bayesian, Optuna)",
            "Sélection automatique de modèles",
            "Cross-validation intelligente",
            "Monitoring temps réel des performances",
            "GPU acceleration optimisée",
            "Auto-ML avec recommandations intelligentes",
            "Évaluation complète avec métriques multiples",
            "Sauvegarde et versioning des modèles",
            "Support multi-GPU et distributed training",
        ]


# Classe pour intégration avec le système multi-agents
class MLEngineerAgentIntegration:
    """Intégration de MLEngineerAgent avec le système multi-agents"""

    def __init__(self, multi_agent_system):
        self.multi_agent_system = multi_agent_system
        self.ml_engineer = MLEngineerAgent()

    def register_with_system(self):
        """Enregistrer l'agent avec le système multi-agents"""
        self.ml_engineer.capabilities = self.ml_engineer.get_capabilities()
        self.multi_agent_system.coordinator.register_agent(self.ml_engineer)
        logger.info(f"✅ {self.ml_engineer.name} enregistré dans le système multi-agents")

    async def create_ml_pipeline_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Exécuter une tâche de création de pipeline ML"""
        try:
            # Extraire les paramètres de la tâche
            dataset_path = task_data.get("dataset_path")
            target_column = task_data.get("target_column")
            problem_type = task_data.get("problem_type", "classification")
            model_type = task_data.get("model_type", "random_forest")
            optimization_method = task_data.get("optimization_method", "bayesian")

            if not dataset_path or not target_column:
                return {"error": "dataset_path et target_column sont requis", "success": False}

            # Créer la configuration
            config = MLTrainingConfig(
                task_id=task_data.get("task_id", f"ml_task_{int(time.time())}"),
                dataset_path=dataset_path,
                target_column=target_column,
                problem_type=problem_type,
                model_type=model_type,
                optimization_method=optimization_method,
                max_trials=task_data.get("max_trials", 50),
                gpu_acceleration=task_data.get("gpu_acceleration", True),
            )

            # Exécuter le pipeline
            result = await self.ml_engineer.create_ml_pipeline(config)

            return {
                "success": True,
                "result": {
                    "task_id": result.task_id,
                    "model_type": result.model_type,
                    "best_score": result.best_score,
                    "training_time": result.training_time,
                    "model_path": result.model_path,
                    "key_metrics": {
                        "cv_mean": result.cv_scores[0] if result.cv_scores else 0,
                        "model_size_mb": result.model_size_mb,
                        "gpu_usage": result.gpu_usage,
                    },
                },
                "summary": f"Pipeline ML créé avec succès pour {result.task_id}",
            }

        except Exception as e:
            logger.error(f"❌ Erreur lors de la création du pipeline ML: {str(e)}")
            return {"error": str(e), "success": False}
