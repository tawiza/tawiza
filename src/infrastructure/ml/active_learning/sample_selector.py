"""
Active learning sample selector.

Implements various strategies for selecting samples for annotation:
- Uncertainty sampling
- Margin sampling
- Entropy sampling
- Diversity sampling
"""

from typing import Any, Literal

import numpy as np
from loguru import logger


class ActiveLearningSampleSelector:
    """Selects samples for active learning annotation."""

    def __init__(
        self,
        strategy: Literal["uncertainty", "margin", "entropy", "diversity"] = "uncertainty",
        batch_size: int = 10,
    ):
        """
        Initialize sample selector.

        Args:
            strategy: Sampling strategy to use
            batch_size: Number of samples to select
        """
        self.strategy = strategy
        self.batch_size = batch_size

    def select_samples(
        self,
        predictions: list[dict[str, Any]],
        num_samples: int,
    ) -> list[dict[str, Any]]:
        """
        Select samples based on the configured strategy.

        Args:
            predictions: List of predictions with metadata
            num_samples: Number of samples to select

        Returns:
            Selected samples for annotation
        """
        if self.strategy == "uncertainty":
            return self._uncertainty_sampling(predictions, num_samples)
        elif self.strategy == "margin":
            return self._margin_sampling(predictions, num_samples)
        elif self.strategy == "entropy":
            return self._entropy_sampling(predictions, num_samples)
        elif self.strategy == "diversity":
            return self._diversity_sampling(predictions, num_samples)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

    def _uncertainty_sampling(
        self,
        predictions: list[dict[str, Any]],
        num_samples: int,
    ) -> list[dict[str, Any]]:
        """
        Select samples with lowest confidence.

        Args:
            predictions: List of predictions
            num_samples: Number to select

        Returns:
            Samples with lowest confidence
        """
        # Sort by confidence (ascending)
        sorted_preds = sorted(
            predictions,
            key=lambda x: x.get("confidence", 1.0),
        )

        # Select top N least confident
        selected = sorted_preds[:num_samples]

        logger.info(
            f"Selected {len(selected)} samples using uncertainty sampling "
            f"(confidence range: {selected[0].get('confidence', 0):.2f} - {selected[-1].get('confidence', 0):.2f})"
        )

        return selected

    def _margin_sampling(
        self,
        predictions: list[dict[str, Any]],
        num_samples: int,
    ) -> list[dict[str, Any]]:
        """
        Select samples with smallest margin between top 2 classes.

        Args:
            predictions: List of predictions with probabilities
            num_samples: Number to select

        Returns:
            Samples with smallest margins
        """
        margins = []
        for pred in predictions:
            probs = pred.get("probabilities", [])
            if len(probs) >= 2:
                sorted_probs = sorted(probs, reverse=True)
                margin = sorted_probs[0] - sorted_probs[1]
                margins.append((pred, margin))

        # Sort by margin (ascending - smallest margin first)
        sorted_margins = sorted(margins, key=lambda x: x[1])

        selected = [item[0] for item in sorted_margins[:num_samples]]

        logger.info(f"Selected {len(selected)} samples using margin sampling")

        return selected

    def _entropy_sampling(
        self,
        predictions: list[dict[str, Any]],
        num_samples: int,
    ) -> list[dict[str, Any]]:
        """
        Select samples with highest entropy.

        Args:
            predictions: List of predictions with probabilities
            num_samples: Number to select

        Returns:
            Samples with highest entropy
        """
        entropies = []
        for pred in predictions:
            probs = pred.get("probabilities", [])
            if probs:
                # Calculate entropy: -sum(p * log(p))
                entropy = -sum(p * np.log(p + 1e-10) for p in probs if p > 0)
                entropies.append((pred, entropy))

        # Sort by entropy (descending - highest entropy first)
        sorted_entropies = sorted(entropies, key=lambda x: x[1], reverse=True)

        selected = [item[0] for item in sorted_entropies[:num_samples]]

        logger.info(f"Selected {len(selected)} samples using entropy sampling")

        return selected

    def _diversity_sampling(
        self,
        predictions: list[dict[str, Any]],
        num_samples: int,
    ) -> list[dict[str, Any]]:
        """
        Select diverse samples using clustering.

        Args:
            predictions: List of predictions with embeddings
            num_samples: Number to select

        Returns:
            Diverse samples
        """
        # Extract embeddings
        embeddings = []
        valid_preds = []

        for pred in predictions:
            if "embedding" in pred:
                embeddings.append(pred["embedding"])
                valid_preds.append(pred)

        if not embeddings:
            logger.warning("No embeddings found, falling back to random sampling")
            return predictions[:num_samples]

        # Convert to numpy array
        embeddings_array = np.array(embeddings)

        # Simple diversity sampling: select points far from each other
        selected_indices = []
        remaining_indices = list(range(len(embeddings)))

        # Start with random point
        selected_indices.append(remaining_indices.pop(0))

        while len(selected_indices) < num_samples and remaining_indices:
            # Find point farthest from already selected points
            max_min_distance = -1
            best_idx = None

            for idx in remaining_indices:
                # Calculate minimum distance to selected points
                distances = [
                    np.linalg.norm(embeddings_array[idx] - embeddings_array[sel_idx])
                    for sel_idx in selected_indices
                ]
                min_distance = min(distances)

                if min_distance > max_min_distance:
                    max_min_distance = min_distance
                    best_idx = idx

            if best_idx is not None:
                selected_indices.append(best_idx)
                remaining_indices.remove(best_idx)

        selected = [valid_preds[idx] for idx in selected_indices]

        logger.info(f"Selected {len(selected)} diverse samples")

        return selected
