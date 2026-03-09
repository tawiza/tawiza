"""Tests for TAJINE reasoning module."""

import pytest

from src.infrastructure.agents.tajine.reasoning.chain_of_thought import (
    ChainOfThought,
    ThoughtStep,
    ThoughtType,
)
from src.infrastructure.agents.tajine.reasoning.tree_of_thoughts import (
    SearchStrategy,
    ThoughtNode,
    TreeOfThoughts,
)


class TestThoughtStep:
    """Tests for ThoughtStep dataclass."""

    def test_thought_step_creation(self):
        """Test creating a thought step."""
        step = ThoughtStep(
            step_id=1,
            thought_type=ThoughtType.OBSERVATION,
            thought="Je remarque une croissance",
            observation="Les données montrent +15%",
            reasoning="Cette tendance indique...",
            confidence=0.8,
        )
        assert step.step_id == 1
        assert step.thought_type == ThoughtType.OBSERVATION
        assert step.confidence == 0.8

    def test_thought_step_to_dict(self):
        """Test serialization."""
        step = ThoughtStep(
            step_id=1,
            thought_type=ThoughtType.INFERENCE,
            thought="Test thought",
            observation="Test observation",
            reasoning="Test reasoning",
            confidence=0.75,
            evidence=["evidence1", "evidence2"],
        )
        data = step.to_dict()
        assert data["step_id"] == 1
        assert data["thought_type"] == "inference"
        assert data["confidence"] == 0.75
        assert len(data["evidence"]) == 2

    def test_thought_step_to_markdown(self):
        """Test markdown formatting."""
        step = ThoughtStep(
            step_id=1,
            thought_type=ThoughtType.CONCLUSION,
            thought="Final conclusion",
            observation="All data points",
            reasoning="Based on analysis",
            confidence=0.9,
        )
        markdown = step.to_markdown()
        assert "Étape 1" in markdown
        assert "Conclusion" in markdown
        assert "Final conclusion" in markdown


class TestChainOfThought:
    """Tests for ChainOfThought engine."""

    @pytest.fixture
    def cot(self):
        """Create ChainOfThought instance."""
        return ChainOfThought(max_steps=5)

    def test_add_step(self, cot):
        """Test manually adding a step."""
        step = cot.add_step(
            thought_type=ThoughtType.OBSERVATION,
            thought="Observation initiale",
            observation="Données brutes",
            reasoning="Première analyse",
            confidence=0.7,
        )
        assert step.step_id == 1
        assert len(cot.steps) == 1

    def test_multiple_steps(self, cot):
        """Test adding multiple steps."""
        cot.add_step(
            thought_type=ThoughtType.OBSERVATION,
            thought="Step 1",
            observation="Obs 1",
            reasoning="Reason 1",
            confidence=0.6,
        )
        cot.add_step(
            thought_type=ThoughtType.ANALYSIS,
            thought="Step 2",
            observation="Obs 2",
            reasoning="Reason 2",
            confidence=0.7,
        )
        cot.add_step(
            thought_type=ThoughtType.CONCLUSION,
            thought="Step 3",
            observation="Obs 3",
            reasoning="Reason 3",
            confidence=0.85,
        )
        assert len(cot.steps) == 3
        assert cot.steps[0].step_id == 1
        assert cot.steps[2].step_id == 3

    def test_reset(self, cot):
        """Test resetting the chain."""
        cot.add_step(
            thought_type=ThoughtType.OBSERVATION,
            thought="Test",
            observation="Test",
            reasoning="Test",
            confidence=0.5,
        )
        assert len(cot.steps) == 1

        cot.reset()
        assert len(cot.steps) == 0

    def test_confidence_clamping(self, cot):
        """Test that confidence is clamped to [0, 1]."""
        step1 = cot.add_step(
            thought_type=ThoughtType.OBSERVATION,
            thought="Test",
            observation="Test",
            reasoning="Test",
            confidence=1.5,  # Too high
        )
        assert step1.confidence == 1.0

        cot.reset()
        step2 = cot.add_step(
            thought_type=ThoughtType.OBSERVATION,
            thought="Test",
            observation="Test",
            reasoning="Test",
            confidence=-0.5,  # Too low
        )
        assert step2.confidence == 0.0

    @pytest.mark.asyncio
    async def test_think_without_llm(self, cot):
        """Test thinking without LLM (fallback)."""
        step = await cot.think(
            context="Test context",
            question="What is happening?",
        )
        assert step is not None
        assert step.thought_type == ThoughtType.OBSERVATION

    @pytest.mark.asyncio
    async def test_reason_through(self, cot):
        """Test reasoning through a problem."""
        steps = await cot.reason_through(
            problem="Analyser la croissance économique de Paris",
            max_steps=3,
        )
        assert len(steps) >= 1

    @pytest.mark.asyncio
    async def test_get_conclusion(self, cot):
        """Test getting conclusion."""
        cot.add_step(
            thought_type=ThoughtType.OBSERVATION,
            thought="Initial observation",
            observation="Data shows growth",
            reasoning="Positive trend",
            confidence=0.7,
        )
        cot.add_step(
            thought_type=ThoughtType.CONCLUSION,
            thought="Final conclusion",
            observation="All indicators positive",
            reasoning="Growth confirmed",
            confidence=0.85,
            evidence=["Point 1", "Point 2"],
        )

        conclusion = await cot.get_conclusion("Test question")
        assert "answer" in conclusion
        assert "confidence" in conclusion
        assert conclusion["confidence"] > 0

    def test_get_chain_summary(self, cot):
        """Test getting chain summary."""
        cot.add_step(
            thought_type=ThoughtType.OBSERVATION,
            thought="Step 1",
            observation="Obs",
            reasoning="Reason",
            confidence=0.7,
        )
        summary = cot.get_chain_summary()
        assert "Chaîne de Raisonnement" in summary
        assert "Étapes" in summary

    def test_to_dict(self, cot):
        """Test converting chain to dict."""
        cot.add_step(
            thought_type=ThoughtType.CONCLUSION,
            thought="Conclusion",
            observation="Final",
            reasoning="Done",
            confidence=0.9,
        )
        data = cot.to_dict()
        assert data["step_count"] == 1
        assert data["has_conclusion"]


class TestThoughtNode:
    """Tests for ThoughtNode dataclass."""

    def test_node_creation(self):
        """Test creating a thought node."""
        node = ThoughtNode(
            id="node_1",
            thought="Analyze data",
            score=0.8,
            depth=0,
        )
        assert node.id == "node_1"
        assert node.score == 0.8
        assert len(node.children) == 0

    def test_node_to_dict(self):
        """Test node serialization."""
        node = ThoughtNode(
            id="node_1",
            thought="Test thought",
            score=0.75,
            depth=2,
            is_solution=True,
        )
        data = node.to_dict()
        assert data["id"] == "node_1"
        assert data["score"] == 0.75
        assert data["is_solution"]


class TestTreeOfThoughts:
    """Tests for TreeOfThoughts engine."""

    @pytest.fixture
    def tot(self):
        """Create TreeOfThoughts instance."""
        return TreeOfThoughts(breadth=2, max_depth=2)

    def test_initialization(self, tot):
        """Test initialization."""
        assert tot.breadth == 2
        assert tot.max_depth == 2
        assert tot.strategy == SearchStrategy.BFS

    def test_different_strategies(self):
        """Test different search strategies."""
        bfs = TreeOfThoughts(strategy=SearchStrategy.BFS)
        assert bfs.strategy == SearchStrategy.BFS

        dfs = TreeOfThoughts(strategy=SearchStrategy.DFS)
        assert dfs.strategy == SearchStrategy.DFS

        best = TreeOfThoughts(strategy=SearchStrategy.BEST_FIRST)
        assert best.strategy == SearchStrategy.BEST_FIRST

    def test_create_node(self, tot):
        """Test node creation."""
        node = tot._create_node("Test thought", score=0.8)
        assert node.thought == "Test thought"
        assert node.score == 0.8
        assert node.id in tot.all_nodes

    def test_create_child_node(self, tot):
        """Test creating child node."""
        parent = tot._create_node("Parent")
        child = tot._create_node("Child", parent=parent, score=0.7)

        assert child.parent_id == parent.id
        assert child.depth == 1
        assert child in parent.children

    def test_get_path(self, tot):
        """Test getting path from root to node."""
        root = tot._create_node("Root")
        tot.root = root
        child = tot._create_node("Child", parent=root)
        grandchild = tot._create_node("Grandchild", parent=child)

        path = tot.get_path(grandchild)
        assert len(path) == 3
        assert path[0] == root
        assert path[2] == grandchild

    def test_reset(self, tot):
        """Test resetting the tree."""
        tot._create_node("Test")
        tot._create_node("Test2")
        assert len(tot.all_nodes) == 2

        tot.reset()
        assert len(tot.all_nodes) == 0
        assert tot.root is None

    @pytest.mark.asyncio
    async def test_explore_basic(self, tot):
        """Test basic exploration."""
        root = await tot.explore(
            problem="Analyze market trends",
            context="French market",
        )
        assert root is not None
        assert len(tot.all_nodes) >= 1

    @pytest.mark.asyncio
    async def test_evaluate_node(self, tot):
        """Test node evaluation."""
        tot.root = tot._create_node("Test root")
        score = await tot.evaluate(tot.root, "Test problem")
        assert 0.0 <= score <= 1.0

    def test_best_path(self, tot):
        """Test getting best path."""
        root = tot._create_node("Root", score=0.5)
        tot.root = root

        child1 = tot._create_node("Child 1", parent=root, score=0.6)
        child2 = tot._create_node("Child 2", parent=root, score=0.8)

        best = tot.best_path()
        assert len(best) >= 1
        # Best path should end at child2 (highest score)
        assert best[-1].score == 0.8

    def test_get_top_paths(self, tot):
        """Test getting top k paths."""
        root = tot._create_node("Root")
        tot.root = root

        tot._create_node("Low", parent=root, score=0.3)
        tot._create_node("Medium", parent=root, score=0.6)
        tot._create_node("High", parent=root, score=0.9)

        top = tot.get_top_paths(k=2)
        assert len(top) <= 2
        if top:
            assert top[0][-1].score >= top[-1][-1].score

    @pytest.mark.asyncio
    async def test_synthesize(self, tot):
        """Test synthesis without LLM."""
        root = tot._create_node("Root", score=0.7)
        tot.root = root
        tot._create_node("Solution", parent=root, score=0.85)

        synthesis = await tot.synthesize("Test problem")
        assert "solution" in synthesis
        assert "confidence" in synthesis

    def test_to_dict(self, tot):
        """Test tree serialization."""
        tot._create_node("Node 1", score=0.5)
        tot._create_node("Node 2", score=0.7)

        data = tot.to_dict()
        assert data["node_count"] == 2
        assert data["strategy"] == "bfs"

    def test_visualize_text(self, tot):
        """Test text visualization."""
        root = tot._create_node("Root")
        tot.root = root
        tot._create_node("Child 1", parent=root, score=0.6)
        tot._create_node("Child 2", parent=root, score=0.8)

        viz = tot.visualize_text()
        assert "Arbre de Pensées" in viz
        assert "Root" in viz


class TestSearchStrategy:
    """Tests for SearchStrategy enum."""

    def test_strategy_values(self):
        """Test strategy values."""
        assert SearchStrategy.BFS.value == "bfs"
        assert SearchStrategy.DFS.value == "dfs"
        assert SearchStrategy.BEST_FIRST.value == "best_first"
