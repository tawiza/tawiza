"""Data preparation service for fine-tuning."""

import json
from pathlib import Path
from typing import Any

from loguru import logger


class DataPreparationService:
    """Service pour préparer les données d'annotation pour le fine-tuning."""

    def prepare_training_data(
        self,
        annotations: list[dict[str, Any]],
        task_type: str = "classification",
        output_file: Path | None = None,
    ) -> list[dict[str, str]]:
        """
        Convertit les annotations Label Studio au format d'entraînement.

        Args:
            annotations: Liste des annotations depuis Label Studio
            task_type: Type de tâche (classification, ner, etc.)
            output_file: Fichier de sortie optionnel (JSONL)

        Returns:
            Liste de dictionnaires au format instruction/input/output
        """
        training_data = []

        for annotation in annotations:
            if not annotation.get("annotations"):
                logger.warning(f"Skipping annotation {annotation.get('id')} - no annotations")
                continue

            # Extraire le texte d'entrée
            text = annotation.get("data", {}).get("text", "")
            if not text:
                logger.warning(f"Skipping annotation {annotation.get('id')} - no text")
                continue

            # Extraire le label depuis les résultats d'annotation
            ann_results = annotation["annotations"][0].get("result", [])
            if not ann_results:
                logger.warning(f"Skipping annotation {annotation.get('id')} - no results")
                continue

            # Convertir selon le type de tâche
            if task_type == "classification":
                training_item = self._prepare_classification(text, ann_results)
            elif task_type == "ner":
                training_item = self._prepare_ner(text, ann_results)
            else:
                logger.warning(f"Unknown task type: {task_type}")
                continue

            if training_item:
                training_data.append(training_item)

        logger.info(f"Prepared {len(training_data)} training examples")

        # Sauvegarder si fichier de sortie spécifié
        if output_file:
            self._save_jsonl(training_data, output_file)

        return training_data

    def _prepare_classification(
        self, text: str, results: list[dict[str, Any]]
    ) -> dict[str, str] | None:
        """Prépare un exemple de classification."""
        try:
            # Extraire le label (choices)
            choices = results[0].get("value", {}).get("choices", [])
            if not choices:
                return None

            label = choices[0]

            return {
                "instruction": "Classify the following text into one of these categories: positive, negative, or neutral.",
                "input": text,
                "output": label,
            }
        except (IndexError, KeyError) as e:
            logger.warning(f"Error preparing classification example: {e}")
            return None

    def _prepare_ner(self, text: str, results: list[dict[str, Any]]) -> dict[str, str] | None:
        """Prépare un exemple de NER (Named Entity Recognition)."""
        try:
            entities = []
            for result in results:
                if result.get("type") == "labels":
                    entity_text = result["value"].get("text", "")
                    entity_label = result["value"].get("labels", [""])[0]
                    if entity_text and entity_label:
                        entities.append(f"{entity_text} [{entity_label}]")

            if not entities:
                return None

            return {
                "instruction": "Extract named entities from the following text.",
                "input": text,
                "output": ", ".join(entities),
            }
        except (IndexError, KeyError) as e:
            logger.warning(f"Error preparing NER example: {e}")
            return None

    def _save_jsonl(self, data: list[dict[str, str]], output_file: Path) -> None:
        """Sauvegarde les données au format JSONL."""
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(data)} training examples to {output_file}")

    def convert_to_ollama_format(
        self, training_data: list[dict[str, str]], base_model: str = "qwen3-coder:30b"
    ) -> str:
        """
        Convertit les données en format Modelfile pour Ollama.

        Args:
            training_data: Données d'entraînement préparées
            base_model: Modèle de base à utiliser

        Returns:
            Contenu du Modelfile
        """
        # Créer les exemples de conversation
        examples = []
        for item in training_data:
            example = f"""USER: {item["instruction"]}

{item["input"]}

ASSISTANT: {item["output"]}"""
            examples.append(example)

        # Construire le Modelfile
        modelfile = f"""FROM {base_model}

# Fine-tuned model with custom examples
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40

# System prompt
SYSTEM \"\"\"You are a helpful AI assistant that has been fine-tuned on specific examples.
Always provide accurate and concise responses based on the training data.
\"\"\"

# Training examples (few-shot learning)
"""

        # Ajouter quelques exemples (few-shot) dans le Modelfile
        # Ollama ne supporte pas le fine-tuning réel, on utilise few-shot learning
        for i, example in enumerate(examples[:10]):  # Limiter à 10 exemples
            modelfile += f"\n# Example {i + 1}\n"
            modelfile += (
                f'MESSAGE user "{example.split("USER:")[1].split("ASSISTANT:")[0].strip()}"\n'
            )
            modelfile += f'MESSAGE assistant "{example.split("ASSISTANT:")[1].strip()}"\n'

        return modelfile

    def validate_training_data(self, training_data: list[dict[str, str]]) -> dict[str, Any]:
        """
        Valide les données d'entraînement.

        Returns:
            Dictionnaire avec statistiques et erreurs
        """
        stats = {
            "total_examples": len(training_data),
            "valid_examples": 0,
            "invalid_examples": 0,
            "errors": [],
        }

        for i, item in enumerate(training_data):
            if not all(k in item for k in ["instruction", "input", "output"]):
                stats["invalid_examples"] += 1
                stats["errors"].append(f"Example {i}: Missing required fields")
                continue

            if not item["instruction"].strip() or not item["input"].strip():
                stats["invalid_examples"] += 1
                stats["errors"].append(f"Example {i}: Empty instruction or input")
                continue

            stats["valid_examples"] += 1

        logger.info(
            f"Validation: {stats['valid_examples']}/{stats['total_examples']} valid examples"
        )

        return stats
