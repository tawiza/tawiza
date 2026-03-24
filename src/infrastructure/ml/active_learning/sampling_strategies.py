"""Sampling strategy implementations for active learning."""

import time

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_distances, euclidean_distances

from src.application.ports.active_learning_ports import ISamplingStrategy
from src.domain.repositories.ml_repositories import IFeedbackRepository, IMLModelRepository
from src.domain.value_objects.sampling import (
    SampleScore,
    SamplingConfig,
    SamplingResult,
    SamplingStrategyType,
)


class UncertaintySamplingStrategy(ISamplingStrategy):
    """Select samples where model has lowest confidence.

    Identifies predictions where the model is least certain,
    indicating areas where the model needs more training data.
    """

    def __init__(
        self,
        feedback_repository: IFeedbackRepository,
        model_repository: IMLModelRepository,
    ) -> None:
        """Initialize uncertainty sampling strategy.

        Args:
            feedback_repository: Repository for feedback data
            model_repository: Repository for model data
        """
        self._feedback_repo = feedback_repository
        self._model_repo = model_repository

    async def select_samples(
        self,
        model_name: str,
        model_version: str,
        config: SamplingConfig,
        feedback_filters: dict | None = None,
    ) -> SamplingResult:
        """Select samples with lowest confidence.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            config: Sampling configuration
            feedback_filters: Optional filters for feedback data

        Returns:
            Sampling result with selected samples

        Raises:
            ValueError: If model not found
        """
        start_time = time.time()

        # Get model
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Get feedback for this model (unlabeled predictions)
        # In practice, we'd query predictions without feedback
        # For now, we use feedback with prediction metadata
        feedbacks = await self._feedback_repo.get_by_model_id(model.id, skip=0, limit=1000)

        # Extract confidence scores from metadata
        candidates: list[SampleScore] = []
        for fb in feedbacks:
            # Get confidence from output_data or metadata
            confidence = fb.output_data.get("confidence") or fb.metadata.get("confidence")
            if confidence is not None:
                # Calculate uncertainty score (lower confidence = higher uncertainty)
                uncertainty_score = 1.0 - confidence
                candidates.append(
                    SampleScore(
                        sample_id=str(fb.prediction_id or fb.id),
                        score=uncertainty_score,
                        confidence=confidence,
                        metadata={
                            "feedback_id": str(fb.id),
                            "model_id": str(fb.model_id),
                        },
                    )
                )

        # Sort by uncertainty (highest first) and select top N
        candidates.sort(key=lambda x: x.score, reverse=True)
        selected = candidates[: config.sample_count]

        # Apply threshold if configured
        if config.threshold is not None:
            selected = [s for s in selected if s.score >= config.threshold]

        execution_time = (time.time() - start_time) * 1000

        return SamplingResult(
            strategy_type=SamplingStrategyType.UNCERTAINTY,
            selected_samples=selected,
            total_candidates=len(candidates),
            config=config,
            execution_time_ms=execution_time,
            metadata={
                "model_name": model_name,
                "model_version": model_version,
                "average_confidence": np.mean([s.confidence for s in selected])
                if selected
                else 0.0,
            },
        )

    def get_strategy_name(self) -> str:
        """Get strategy name."""
        return "UncertaintySampling"


class MarginSamplingStrategy(ISamplingStrategy):
    """Select samples with smallest margin between top predictions.

    Identifies samples where the model is confused between multiple classes,
    indicated by small differences between top prediction scores.
    """

    def __init__(
        self,
        feedback_repository: IFeedbackRepository,
        model_repository: IMLModelRepository,
    ) -> None:
        """Initialize margin sampling strategy.

        Args:
            feedback_repository: Repository for feedback data
            model_repository: Repository for model data
        """
        self._feedback_repo = feedback_repository
        self._model_repo = model_repository

    async def select_samples(
        self,
        model_name: str,
        model_version: str,
        config: SamplingConfig,
        feedback_filters: dict | None = None,
    ) -> SamplingResult:
        """Select samples with smallest margin.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            config: Sampling configuration
            feedback_filters: Optional filters for feedback data

        Returns:
            Sampling result with selected samples

        Raises:
            ValueError: If model not found
        """
        start_time = time.time()

        # Get model
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Get feedback
        feedbacks = await self._feedback_repo.get_by_model_id(model.id, skip=0, limit=1000)

        # Calculate margins
        candidates: list[SampleScore] = []
        for fb in feedbacks:
            # Get prediction probabilities
            probabilities = fb.output_data.get("probabilities") or fb.metadata.get("probabilities")
            if probabilities and isinstance(probabilities, (list, np.ndarray)):
                probs = sorted(probabilities, reverse=True)
                if len(probs) >= 2:
                    # Margin = difference between top 2 predictions
                    margin = probs[0] - probs[1]
                    # Smaller margin = more informative (inverse for score)
                    margin_score = 1.0 - margin

                    candidates.append(
                        SampleScore(
                            sample_id=str(fb.prediction_id or fb.id),
                            score=margin_score,
                            confidence=probs[0],
                            margin=margin,
                            metadata={
                                "feedback_id": str(fb.id),
                                "top_2_probs": probs[:2],
                            },
                        )
                    )

        # Sort by margin score (smallest margin first)
        candidates.sort(key=lambda x: x.score, reverse=True)
        selected = candidates[: config.sample_count]

        # Apply threshold if configured
        if config.threshold is not None:
            selected = [s for s in selected if s.score >= config.threshold]

        execution_time = (time.time() - start_time) * 1000

        return SamplingResult(
            strategy_type=SamplingStrategyType.MARGIN,
            selected_samples=selected,
            total_candidates=len(candidates),
            config=config,
            execution_time_ms=execution_time,
            metadata={
                "model_name": model_name,
                "model_version": model_version,
                "average_margin": np.mean([s.margin for s in selected if s.margin])
                if selected
                else 0.0,
            },
        )

    def get_strategy_name(self) -> str:
        """Get strategy name."""
        return "MarginSampling"


class EntropySamplingStrategy(ISamplingStrategy):
    """Select samples with highest prediction entropy.

    Uses Shannon entropy to measure prediction uncertainty,
    identifying samples where the model is most confused.
    """

    def __init__(
        self,
        feedback_repository: IFeedbackRepository,
        model_repository: IMLModelRepository,
    ) -> None:
        """Initialize entropy sampling strategy.

        Args:
            feedback_repository: Repository for feedback data
            model_repository: Repository for model data
        """
        self._feedback_repo = feedback_repository
        self._model_repo = model_repository

    def _calculate_entropy(self, probabilities: list[float]) -> float:
        """Calculate Shannon entropy.

        Args:
            probabilities: Probability distribution

        Returns:
            Entropy value
        """
        probs = np.array(probabilities)
        # Add small epsilon to avoid log(0)
        probs = np.clip(probs, 1e-10, 1.0)
        entropy = -np.sum(probs * np.log2(probs))
        return float(entropy)

    async def select_samples(
        self,
        model_name: str,
        model_version: str,
        config: SamplingConfig,
        feedback_filters: dict | None = None,
    ) -> SamplingResult:
        """Select samples with highest entropy.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            config: Sampling configuration
            feedback_filters: Optional filters for feedback data

        Returns:
            Sampling result with selected samples

        Raises:
            ValueError: If model not found
        """
        start_time = time.time()

        # Get model
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Get feedback
        feedbacks = await self._feedback_repo.get_by_model_id(model.id, skip=0, limit=1000)

        # Calculate entropy
        candidates: list[SampleScore] = []
        for fb in feedbacks:
            probabilities = fb.output_data.get("probabilities") or fb.metadata.get("probabilities")
            if probabilities and isinstance(probabilities, (list, np.ndarray)):
                entropy = self._calculate_entropy(probabilities)
                confidence = max(probabilities) if probabilities else 0.0

                candidates.append(
                    SampleScore(
                        sample_id=str(fb.prediction_id or fb.id),
                        score=entropy,
                        confidence=confidence,
                        entropy=entropy,
                        metadata={
                            "feedback_id": str(fb.id),
                            "num_classes": len(probabilities),
                        },
                    )
                )

        # Sort by entropy (highest first)
        candidates.sort(key=lambda x: x.score, reverse=True)
        selected = candidates[: config.sample_count]

        # Apply threshold if configured
        if config.threshold is not None:
            selected = [s for s in selected if s.score >= config.threshold]

        execution_time = (time.time() - start_time) * 1000

        return SamplingResult(
            strategy_type=SamplingStrategyType.ENTROPY,
            selected_samples=selected,
            total_candidates=len(candidates),
            config=config,
            execution_time_ms=execution_time,
            metadata={
                "model_name": model_name,
                "model_version": model_version,
                "average_entropy": np.mean([s.entropy for s in selected if s.entropy])
                if selected
                else 0.0,
            },
        )

    def get_strategy_name(self) -> str:
        """Get strategy name."""
        return "EntropySampling"


class DiversitySamplingStrategy(ISamplingStrategy):
    """Select diverse samples using clustering.

    Uses embeddings and clustering to select samples that are
    diverse and representative of the input space.
    """

    def __init__(
        self,
        feedback_repository: IFeedbackRepository,
        model_repository: IMLModelRepository,
    ) -> None:
        """Initialize diversity sampling strategy.

        Args:
            feedback_repository: Repository for feedback data
            model_repository: Repository for model data
        """
        self._feedback_repo = feedback_repository
        self._model_repo = model_repository

    def _get_distance_matrix(self, embeddings: np.ndarray, metric: str = "cosine") -> np.ndarray:
        """Calculate pairwise distances.

        Args:
            embeddings: Embedding matrix
            metric: Distance metric ("cosine" or "euclidean")

        Returns:
            Distance matrix
        """
        if metric == "cosine":
            return cosine_distances(embeddings)
        else:
            return euclidean_distances(embeddings)

    async def select_samples(
        self,
        model_name: str,
        model_version: str,
        config: SamplingConfig,
        feedback_filters: dict | None = None,
    ) -> SamplingResult:
        """Select diverse samples using clustering.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            config: Sampling configuration
            feedback_filters: Optional filters for feedback data

        Returns:
            Sampling result with selected samples

        Raises:
            ValueError: If model not found or invalid config
        """
        start_time = time.time()

        # Get model
        model = await self._model_repo.get_by_name_and_version(model_name, model_version)
        if not model:
            raise ValueError(f"Model {model_name}:{model_version} not found")

        # Get feedback
        feedbacks = await self._feedback_repo.get_by_model_id(model.id, skip=0, limit=1000)

        # Extract embeddings
        embeddings_list = []
        feedback_map = {}
        for fb in feedbacks:
            embedding = fb.output_data.get("embedding") or fb.metadata.get("embedding")
            if embedding and isinstance(embedding, (list, np.ndarray)):
                embeddings_list.append(embedding)
                feedback_map[len(embeddings_list) - 1] = fb

        if not embeddings_list:
            # Fallback to random sampling if no embeddings
            return SamplingResult(
                strategy_type=SamplingStrategyType.DIVERSITY,
                selected_samples=[],
                total_candidates=0,
                config=config,
                execution_time_ms=(time.time() - start_time) * 1000,
                metadata={"error": "No embeddings found in feedback data"},
            )

        embeddings = np.array(embeddings_list)

        # Perform clustering
        n_clusters = min(config.sample_count, len(embeddings))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embeddings)

        # Select samples closest to cluster centers
        selected: list[SampleScore] = []
        metric = config.diversity_metric or "cosine"

        for cluster_id in range(n_clusters):
            cluster_mask = cluster_labels == cluster_id
            cluster_indices = np.where(cluster_mask)[0]

            if len(cluster_indices) == 0:
                continue

            cluster_embeddings = embeddings[cluster_indices]
            center = kmeans.cluster_centers_[cluster_id]

            # Find closest point to center
            distances = np.linalg.norm(cluster_embeddings - center, axis=1)
            closest_idx = cluster_indices[np.argmin(distances)]

            fb = feedback_map[closest_idx]
            confidence = fb.output_data.get("confidence") or fb.metadata.get("confidence", 0.5)

            # Diversity score based on cluster size and distance to center
            diversity_score = 1.0 / (1.0 + np.min(distances))

            selected.append(
                SampleScore(
                    sample_id=str(fb.prediction_id or fb.id),
                    score=diversity_score,
                    confidence=confidence,
                    metadata={
                        "feedback_id": str(fb.id),
                        "cluster_id": int(cluster_id),
                        "cluster_size": int(np.sum(cluster_mask)),
                        "distance_to_center": float(np.min(distances)),
                    },
                )
            )

        execution_time = (time.time() - start_time) * 1000

        return SamplingResult(
            strategy_type=SamplingStrategyType.DIVERSITY,
            selected_samples=selected,
            total_candidates=len(embeddings),
            config=config,
            execution_time_ms=execution_time,
            metadata={
                "model_name": model_name,
                "model_version": model_version,
                "n_clusters": n_clusters,
                "distance_metric": metric,
            },
        )

    def get_strategy_name(self) -> str:
        """Get strategy name."""
        return "DiversitySampling"
