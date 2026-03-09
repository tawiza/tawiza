"""Dataset Builder - Builds and manages training datasets."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any

from loguru import logger


def utc_now() -> datetime:
    """Get current UTC time."""
    return datetime.now(UTC)


class DatasetFormat(StrEnum):
    """Supported dataset formats."""

    JSONL = "jsonl"
    ALPACA = "alpaca"
    SHAREGPT = "sharegpt"


@dataclass
class DatasetExample:
    """Single example in the dataset.

    Follows the instruction-input-output format used by
    most fine-tuning frameworks.
    """

    instruction: str
    input: str = ""
    output: str = ""
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "instruction": self.instruction,
            "input": self.input,
            "output": self.output,
            "source": self.source,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    def to_alpaca(self) -> dict[str, str]:
        """Convert to Alpaca format.

        Returns:
            Dict with instruction, input, output keys
        """
        return {
            "instruction": self.instruction,
            "input": self.input,
            "output": self.output,
        }

    def to_sharegpt(self) -> dict[str, Any]:
        """Convert to ShareGPT format.

        Returns:
            Dict with conversations array
        """
        conversations = []

        # Build human message from instruction + input
        human_content = self.instruction
        if self.input:
            human_content += f"\n\n{self.input}"

        conversations.append({
            "from": "human",
            "value": human_content,
        })

        conversations.append({
            "from": "gpt",
            "value": self.output,
        })

        return {"conversations": conversations}


@dataclass
class DatasetStats:
    """Statistics about a dataset."""

    total_examples: int
    sources: dict[str, int]
    avg_instruction_length: float = 0.0
    avg_output_length: float = 0.0
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0


class DatasetBuilder:
    """Builds and manages training datasets.

    Collects examples from various sources (tasks, feedback, etc.),
    supports multiple export formats, and provides filtering/deduplication.

    Example:
        builder = DatasetBuilder()
        builder.add(
            instruction="Summarize this text",
            input="Long article...",
            output="Brief summary",
            source="task"
        )
        builder.export("dataset.jsonl", format=DatasetFormat.JSONL)
    """

    def __init__(self):
        """Initialize empty dataset builder."""
        self._examples: list[DatasetExample] = []
        logger.info("DatasetBuilder initialized")

    @property
    def examples(self) -> list[DatasetExample]:
        """Get all examples."""
        return self._examples

    def add(
        self,
        instruction: str,
        output: str,
        source: str,
        input: str = "",
        feedback: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DatasetExample:
        """Add a new example to the dataset.

        Args:
            instruction: The instruction/question
            output: Expected output/answer
            source: Source identifier (e.g., "task", "feedback")
            input: Optional additional input context
            feedback: Optional feedback (positive/negative)
            metadata: Optional additional metadata

        Returns:
            The created DatasetExample
        """
        example_metadata = metadata or {}
        if feedback:
            example_metadata["feedback"] = feedback

        example = DatasetExample(
            instruction=instruction,
            input=input,
            output=output,
            source=source,
            metadata=example_metadata,
        )

        self._examples.append(example)
        logger.debug(f"Added example from source '{source}', total: {len(self._examples)}")

        return example

    def get_stats(self) -> DatasetStats:
        """Get statistics about the dataset.

        Returns:
            DatasetStats with counts and averages
        """
        if not self._examples:
            return DatasetStats(total_examples=0, sources={})

        # Count by source
        sources: dict[str, int] = {}
        total_instruction_len = 0
        total_output_len = 0
        positive_count = 0
        negative_count = 0

        for ex in self._examples:
            sources[ex.source] = sources.get(ex.source, 0) + 1
            total_instruction_len += len(ex.instruction)
            total_output_len += len(ex.output)

            feedback = ex.metadata.get("feedback")
            if feedback == "positive":
                positive_count += 1
            elif feedback == "negative":
                negative_count += 1

        n = len(self._examples)
        return DatasetStats(
            total_examples=n,
            sources=sources,
            avg_instruction_length=total_instruction_len / n,
            avg_output_length=total_output_len / n,
            positive_feedback_count=positive_count,
            negative_feedback_count=negative_count,
        )

    def filter(
        self,
        source: str | None = None,
        feedback: str | None = None,
    ) -> "DatasetBuilder":
        """Filter examples and return a new DatasetBuilder.

        Args:
            source: Filter by source
            feedback: Filter by feedback type

        Returns:
            New DatasetBuilder with filtered examples
        """
        filtered = DatasetBuilder()

        for ex in self._examples:
            if source and ex.source != source:
                continue
            if feedback and ex.metadata.get("feedback") != feedback:
                continue
            filtered._examples.append(ex)

        logger.debug(f"Filtered {len(self._examples)} -> {len(filtered._examples)} examples")
        return filtered

    def export(self, path: str, format: DatasetFormat = DatasetFormat.JSONL) -> int:
        """Export dataset to file.

        Args:
            path: Output file path
            format: Export format

        Returns:
            Number of examples exported
        """
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        if format == DatasetFormat.JSONL:
            with open(path, "w") as f:
                for ex in self._examples:
                    f.write(json.dumps(ex.to_dict()) + "\n")

        elif format == DatasetFormat.ALPACA:
            data = [ex.to_alpaca() for ex in self._examples]
            with open(path, "w") as f:
                json.dump(data, f, indent=2)

        elif format == DatasetFormat.SHAREGPT:
            data = [ex.to_sharegpt() for ex in self._examples]
            with open(path, "w") as f:
                json.dump(data, f, indent=2)

        logger.info(f"Exported {len(self._examples)} examples to {path} ({format.value})")
        return len(self._examples)

    def import_from(self, path: str, format: DatasetFormat = DatasetFormat.JSONL) -> int:
        """Import examples from file.

        Args:
            path: Input file path
            format: File format

        Returns:
            Number of examples imported
        """
        count = 0

        if format == DatasetFormat.JSONL:
            with open(path) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        self._examples.append(DatasetExample(
                            instruction=data.get("instruction", ""),
                            input=data.get("input", ""),
                            output=data.get("output", ""),
                            source=data.get("source", "import"),
                            metadata=data.get("metadata", {}),
                        ))
                        count += 1

        elif format == DatasetFormat.ALPACA:
            with open(path) as f:
                data = json.load(f)
                for item in data:
                    self._examples.append(DatasetExample(
                        instruction=item.get("instruction", ""),
                        input=item.get("input", ""),
                        output=item.get("output", ""),
                        source="alpaca_import",
                    ))
                    count += 1

        logger.info(f"Imported {count} examples from {path}")
        return count

    def clear(self) -> None:
        """Clear all examples."""
        self._examples.clear()
        logger.info("Dataset cleared")

    def merge(self, other: "DatasetBuilder") -> None:
        """Merge another dataset into this one.

        Args:
            other: Dataset to merge from
        """
        self._examples.extend(other._examples)
        logger.info(f"Merged {len(other._examples)} examples, total: {len(self._examples)}")

    def deduplicate(self) -> int:
        """Remove duplicate examples based on instruction+output.

        Returns:
            Number of duplicates removed
        """
        seen = set()
        unique = []

        for ex in self._examples:
            key = (ex.instruction, ex.output)
            if key not in seen:
                seen.add(key)
                unique.append(ex)

        removed = len(self._examples) - len(unique)
        self._examples = unique

        logger.info(f"Deduplicated: removed {removed} duplicates")
        return removed
