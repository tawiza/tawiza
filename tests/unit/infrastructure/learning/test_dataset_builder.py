"""Tests for Dataset Builder."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.infrastructure.learning.dataset_builder import (
    DatasetBuilder,
    DatasetExample,
    DatasetFormat,
    DatasetStats,
)


class TestDatasetExample:
    """Test DatasetExample dataclass."""

    def test_create_example(self):
        """Should create a valid example."""
        example = DatasetExample(
            instruction="What is 2+2?",
            input="",
            output="4",
            source="test",
        )
        assert example.instruction == "What is 2+2?"
        assert example.output == "4"

    def test_example_with_metadata(self):
        """Should support metadata."""
        example = DatasetExample(
            instruction="Summarize this",
            input="Long text...",
            output="Summary",
            source="task",
            metadata={"task_id": "123", "confidence": 0.95},
        )
        assert example.metadata["task_id"] == "123"

    def test_example_to_dict(self):
        """Should convert to dictionary."""
        example = DatasetExample(
            instruction="Test",
            input="input",
            output="output",
            source="test",
        )
        d = example.to_dict()
        assert "instruction" in d
        assert "input" in d
        assert "output" in d

    def test_example_to_alpaca_format(self):
        """Should convert to Alpaca format."""
        example = DatasetExample(
            instruction="Translate to French",
            input="Hello",
            output="Bonjour",
            source="test",
        )
        alpaca = example.to_alpaca()
        assert alpaca["instruction"] == "Translate to French"
        assert alpaca["input"] == "Hello"
        assert alpaca["output"] == "Bonjour"

    def test_example_to_sharegpt_format(self):
        """Should convert to ShareGPT format."""
        example = DatasetExample(
            instruction="What is AI?",
            input="",
            output="AI is artificial intelligence.",
            source="test",
        )
        sharegpt = example.to_sharegpt()
        assert "conversations" in sharegpt
        assert len(sharegpt["conversations"]) == 2
        assert sharegpt["conversations"][0]["from"] == "human"
        assert sharegpt["conversations"][1]["from"] == "gpt"


class TestDatasetFormat:
    """Test DatasetFormat enum."""

    def test_formats_exist(self):
        """Should have all expected formats."""
        assert DatasetFormat.JSONL.value == "jsonl"
        assert DatasetFormat.ALPACA.value == "alpaca"
        assert DatasetFormat.SHAREGPT.value == "sharegpt"


class TestDatasetBuilder:
    """Test DatasetBuilder class."""

    def test_init_creates_empty_dataset(self):
        """Should start with empty examples list."""
        builder = DatasetBuilder()
        assert len(builder.examples) == 0

    def test_add_example(self):
        """Should add example to dataset."""
        builder = DatasetBuilder()
        builder.add(instruction="Test instruction", output="Test output", source="unit_test")
        assert len(builder.examples) == 1
        assert builder.examples[0].instruction == "Test instruction"

    def test_add_with_input(self):
        """Should add example with input."""
        builder = DatasetBuilder()
        builder.add(instruction="Translate", input="Hello", output="Bonjour", source="test")
        assert builder.examples[0].input == "Hello"

    def test_add_with_feedback(self):
        """Should record feedback with example."""
        builder = DatasetBuilder()
        builder.add(instruction="Test", output="Output", source="test", feedback="positive")
        assert builder.examples[0].metadata.get("feedback") == "positive"

    def test_get_stats(self):
        """Should return dataset statistics."""
        builder = DatasetBuilder()
        builder.add(instruction="Test 1", output="Out 1", source="a")
        builder.add(instruction="Test 2", output="Out 2", source="b")
        builder.add(instruction="Test 3", output="Out 3", source="a")

        stats = builder.get_stats()

        assert stats.total_examples == 3
        assert stats.sources == {"a": 2, "b": 1}

    def test_filter_by_source(self):
        """Should filter examples by source."""
        builder = DatasetBuilder()
        builder.add(instruction="A", output="1", source="task")
        builder.add(instruction="B", output="2", source="feedback")
        builder.add(instruction="C", output="3", source="task")

        filtered = builder.filter(source="task")

        assert len(filtered.examples) == 2

    def test_filter_by_feedback(self):
        """Should filter examples by feedback."""
        builder = DatasetBuilder()
        builder.add(instruction="A", output="1", source="test", feedback="positive")
        builder.add(instruction="B", output="2", source="test", feedback="negative")
        builder.add(instruction="C", output="3", source="test", feedback="positive")

        filtered = builder.filter(feedback="positive")

        assert len(filtered.examples) == 2

    def test_export_jsonl(self, tmp_path):
        """Should export to JSONL format."""
        builder = DatasetBuilder()
        builder.add(instruction="Test", output="Output", source="test")

        output_file = tmp_path / "dataset.jsonl"
        builder.export(str(output_file), format=DatasetFormat.JSONL)

        assert output_file.exists()
        with open(output_file) as f:
            line = f.readline()
            data = json.loads(line)
            assert "instruction" in data

    def test_export_alpaca(self, tmp_path):
        """Should export to Alpaca JSON format."""
        builder = DatasetBuilder()
        builder.add(instruction="Test", input="Input", output="Output", source="test")

        output_file = tmp_path / "dataset.json"
        builder.export(str(output_file), format=DatasetFormat.ALPACA)

        assert output_file.exists()
        with open(output_file) as f:
            data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 1

    def test_export_sharegpt(self, tmp_path):
        """Should export to ShareGPT format."""
        builder = DatasetBuilder()
        builder.add(instruction="Test", output="Output", source="test")

        output_file = tmp_path / "dataset.json"
        builder.export(str(output_file), format=DatasetFormat.SHAREGPT)

        assert output_file.exists()
        with open(output_file) as f:
            data = json.load(f)
            assert "conversations" in data[0]

    def test_import_jsonl(self, tmp_path):
        """Should import from JSONL file."""
        # Create test file
        jsonl_file = tmp_path / "import.jsonl"
        with open(jsonl_file, "w") as f:
            f.write(json.dumps({"instruction": "Test", "input": "", "output": "Out"}) + "\n")
            f.write(json.dumps({"instruction": "Test2", "input": "", "output": "Out2"}) + "\n")

        builder = DatasetBuilder()
        builder.import_from(str(jsonl_file), format=DatasetFormat.JSONL)

        assert len(builder.examples) == 2

    def test_clear(self):
        """Should clear all examples."""
        builder = DatasetBuilder()
        builder.add(instruction="Test", output="Output", source="test")
        assert len(builder.examples) == 1

        builder.clear()
        assert len(builder.examples) == 0

    def test_merge(self):
        """Should merge two datasets."""
        builder1 = DatasetBuilder()
        builder1.add(instruction="A", output="1", source="a")

        builder2 = DatasetBuilder()
        builder2.add(instruction="B", output="2", source="b")

        builder1.merge(builder2)

        assert len(builder1.examples) == 2

    def test_deduplicate(self):
        """Should remove duplicate examples."""
        builder = DatasetBuilder()
        builder.add(instruction="Same", output="Same", source="test")
        builder.add(instruction="Same", output="Same", source="test")
        builder.add(instruction="Different", output="Other", source="test")

        builder.deduplicate()

        assert len(builder.examples) == 2


class TestDatasetStats:
    """Test DatasetStats dataclass."""

    def test_stats_fields(self):
        """Should have all expected fields."""
        stats = DatasetStats(
            total_examples=100,
            sources={"task": 50, "feedback": 50},
            avg_instruction_length=25.5,
            avg_output_length=100.2,
        )
        assert stats.total_examples == 100
        assert stats.sources["task"] == 50
