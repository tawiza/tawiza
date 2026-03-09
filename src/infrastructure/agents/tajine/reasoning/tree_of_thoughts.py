"""Tree-of-Thoughts reasoning for TAJINE agent.

Provides multi-path exploration for complex decisions
where multiple approaches need to be evaluated.
"""

import asyncio
import contextlib
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any, Protocol

from loguru import logger


class SearchStrategy(StrEnum):
    """Search strategies for tree exploration."""

    BFS = "bfs"  # Breadth-first: explore all branches at each level
    DFS = "dfs"  # Depth-first: go deep before exploring siblings
    BEST_FIRST = "best_first"  # Always expand best-scoring node


@dataclass
class ThoughtNode:
    """A node in the thought tree."""

    id: str
    thought: str  # The thought/approach at this node
    parent_id: str | None = None
    children: list["ThoughtNode"] = field(default_factory=list)
    score: float = 0.0  # Evaluation score for this path
    depth: int = 0
    is_solution: bool = False
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "thought": self.thought,
            "parent_id": self.parent_id,
            "score": self.score,
            "depth": self.depth,
            "is_solution": self.is_solution,
            "reasoning": self.reasoning,
            "children_count": len(self.children),
            "metadata": self.metadata,
        }

    def get_path_to_root(self) -> list[str]:
        """Get thoughts from this node to root."""
        return [self.thought]  # Parent traversal done by tree


class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt."""
        ...


# Prompt templates for Tree-of-Thoughts
TOT_EXPAND_PROMPT = """Tu es un expert en analyse territoriale française.
Tu dois proposer {n} approches différentes pour résoudre ce problème.

Problème: {problem}

Contexte: {context}

Chemin de raisonnement actuel:
{current_path}

Propose {n} approches DIFFÉRENTES et DISTINCTES pour continuer le raisonnement.
Chaque approche doit être une perspective unique sur le problème.

Format pour chaque approche:
[APPROCHE N]
PENSÉE: Description de l'approche
RAISONNEMENT: Pourquoi cette approche pourrait fonctionner
POTENTIEL: score de 0.0 à 1.0
[/APPROCHE]
"""

TOT_EVALUATE_PROMPT = """Évalue le chemin de raisonnement suivant pour résoudre le problème.

Problème: {problem}

Chemin de raisonnement:
{path}

Évalue ce chemin sur les critères suivants:
1. PERTINENCE: Le chemin adresse-t-il le problème? (0-1)
2. FAISABILITÉ: L'approche est-elle réalisable? (0-1)
3. COMPLÉTUDE: Le raisonnement est-il complet? (0-1)
4. QUALITÉ: La qualité du raisonnement (0-1)

Donne un SCORE GLOBAL de 0.0 à 1.0.
Indique si c'est une SOLUTION (oui/non).

Format:
PERTINENCE: 0.X
FAISABILITÉ: 0.X
COMPLÉTUDE: 0.X
QUALITÉ: 0.X
SCORE_GLOBAL: 0.X
EST_SOLUTION: oui|non
EXPLICATION: ...
"""

TOT_SYNTHESIZE_PROMPT = """Basé sur l'exploration de l'arbre de pensées suivant, synthétise la meilleure solution.

Problème: {problem}

Meilleurs chemins explorés:
{best_paths}

Fournis:
1. SOLUTION: La meilleure réponse au problème
2. CONFIANCE: Score de confiance global (0-1)
3. JUSTIFICATION: Pourquoi cette solution
4. ALTERNATIVES: Autres approches viables
"""


class TreeOfThoughts:
    """Tree-of-Thoughts reasoning engine.

    Explores multiple reasoning paths in parallel,
    evaluating and pruning to find optimal solutions.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        breadth: int = 3,  # Number of branches at each node
        max_depth: int = 4,  # Maximum tree depth
        strategy: SearchStrategy = SearchStrategy.BFS,
        pruning_threshold: float = 0.3,  # Prune paths below this score
    ):
        """Initialize Tree-of-Thoughts engine.

        Args:
            llm_provider: LLM for generating and evaluating thoughts
            breadth: Number of branches per node
            max_depth: Maximum depth to explore
            strategy: Search strategy (BFS, DFS, best-first)
            pruning_threshold: Minimum score to continue exploring
        """
        self.llm = llm_provider
        self.breadth = breadth
        self.max_depth = max_depth
        self.strategy = strategy
        self.pruning_threshold = pruning_threshold

        self.root: ThoughtNode | None = None
        self.all_nodes: dict[str, ThoughtNode] = {}
        self._node_counter = 0
        self.solutions: list[ThoughtNode] = []

    def _generate_id(self) -> str:
        """Generate unique node ID."""
        self._node_counter += 1
        return f"node_{self._node_counter}"

    def reset(self) -> None:
        """Reset tree for new exploration."""
        self.root = None
        self.all_nodes = {}
        self._node_counter = 0
        self.solutions = []

    def _create_node(
        self,
        thought: str,
        parent: ThoughtNode | None = None,
        score: float = 0.0,
    ) -> ThoughtNode:
        """Create a new thought node.

        Args:
            thought: The thought content
            parent: Parent node (None for root)
            score: Initial score

        Returns:
            New ThoughtNode
        """
        node = ThoughtNode(
            id=self._generate_id(),
            thought=thought,
            parent_id=parent.id if parent else None,
            score=score,
            depth=parent.depth + 1 if parent else 0,
        )
        self.all_nodes[node.id] = node

        if parent:
            parent.children.append(node)

        return node

    def get_path(self, node: ThoughtNode) -> list[ThoughtNode]:
        """Get path from root to node.

        Args:
            node: Target node

        Returns:
            List of nodes from root to target
        """
        path = []
        current: ThoughtNode | None = node

        while current:
            path.append(current)
            current = self.all_nodes.get(current.parent_id) if current.parent_id else None

        return list(reversed(path))

    def get_path_text(self, node: ThoughtNode) -> str:
        """Get readable text of path to node.

        Args:
            node: Target node

        Returns:
            Formatted path string
        """
        path = self.get_path(node)
        return "\n".join(
            f"Étape {i + 1} (score: {n.score:.2f}): {n.thought}"
            for i, n in enumerate(path)
        )

    async def expand(
        self,
        node: ThoughtNode,
        problem: str,
        context: str = "",
    ) -> list[ThoughtNode]:
        """Expand a node by generating child thoughts.

        Args:
            node: Node to expand
            problem: Problem being solved
            context: Additional context

        Returns:
            List of new child nodes
        """
        if node.depth >= self.max_depth:
            logger.debug(f"Node {node.id} at max depth, not expanding")
            return []

        current_path = self.get_path_text(node)

        if not self.llm:
            # Fallback: generate generic approaches
            approaches = [
                f"Approche analytique: examiner les données de {problem[:50]}",
                "Approche comparative: comparer avec des cas similaires",
                "Approche causale: identifier les facteurs clés",
            ]
            children = []
            for i, approach in enumerate(approaches[: self.breadth]):
                child = self._create_node(
                    thought=approach,
                    parent=node,
                    score=0.5 - i * 0.1,  # Decreasing scores
                )
                children.append(child)
            return children

        # Use LLM to generate expansions
        prompt = TOT_EXPAND_PROMPT.format(
            n=self.breadth,
            problem=problem,
            context=context[:1000],
            current_path=current_path,
        )

        try:
            response = await self.llm.generate(prompt, temperature=0.7)
            children = self._parse_expansions(response, node)
            logger.debug(f"Expanded node {node.id} with {len(children)} children")
            return children
        except Exception as e:
            logger.warning(f"Expansion failed for node {node.id}: {e}")
            return []

    def _parse_expansions(
        self,
        response: str,
        parent: ThoughtNode,
    ) -> list[ThoughtNode]:
        """Parse LLM expansion response.

        Args:
            response: Raw LLM response
            parent: Parent node

        Returns:
            List of child nodes
        """
        children = []
        current_thought = ""
        current_reasoning = ""
        current_score = 0.5

        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("[APPROCHE"):
                if current_thought:
                    child = self._create_node(
                        thought=current_thought,
                        parent=parent,
                        score=current_score,
                    )
                    child.reasoning = current_reasoning
                    children.append(child)
                current_thought = ""
                current_reasoning = ""
                current_score = 0.5
            elif line.startswith("PENSÉE:") or line.startswith("PENSEE:"):
                current_thought = line.split(":", 1)[1].strip()
            elif line.startswith("RAISONNEMENT:"):
                current_reasoning = line.split(":", 1)[1].strip()
            elif line.startswith("POTENTIEL:"):
                with contextlib.suppress(ValueError):
                    current_score = float(line.split(":", 1)[1].strip())

        # Add last approach if exists
        if current_thought:
            child = self._create_node(
                thought=current_thought,
                parent=parent,
                score=current_score,
            )
            child.reasoning = current_reasoning
            children.append(child)

        return children[: self.breadth]

    async def evaluate(
        self,
        node: ThoughtNode,
        problem: str,
    ) -> float:
        """Evaluate a node's path.

        Args:
            node: Node to evaluate
            problem: Problem being solved

        Returns:
            Evaluation score (0-1)
        """
        path_text = self.get_path_text(node)

        if not self.llm:
            # Fallback: use simple heuristics
            # Score based on depth and existing score
            base_score = node.score
            depth_penalty = node.depth * 0.05
            return max(0.0, min(1.0, base_score - depth_penalty + 0.2))

        prompt = TOT_EVALUATE_PROMPT.format(
            problem=problem,
            path=path_text,
        )

        try:
            response = await self.llm.generate(prompt, temperature=0.2)
            score, is_solution, explanation = self._parse_evaluation(response)
            node.score = score
            node.is_solution = is_solution
            node.metadata["evaluation"] = explanation
            return score
        except Exception as e:
            logger.warning(f"Evaluation failed for node {node.id}: {e}")
            return node.score

    def _parse_evaluation(
        self,
        response: str,
    ) -> tuple[float, bool, str]:
        """Parse evaluation response.

        Args:
            response: Raw LLM response

        Returns:
            Tuple of (score, is_solution, explanation)
        """
        score = 0.5
        is_solution = False
        explanation = ""

        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("SCORE_GLOBAL:"):
                with contextlib.suppress(ValueError):
                    score = float(line.split(":", 1)[1].strip())
            elif line.startswith("EST_SOLUTION:"):
                val = line.split(":", 1)[1].strip().lower()
                is_solution = val in ("oui", "yes", "true", "1")
            elif line.startswith("EXPLICATION:"):
                explanation = line.split(":", 1)[1].strip()

        return (max(0.0, min(1.0, score)), is_solution, explanation)

    async def explore(
        self,
        problem: str,
        context: str = "",
        initial_thought: str = "",
    ) -> ThoughtNode:
        """Explore the thought tree.

        Args:
            problem: Problem to solve
            context: Additional context
            initial_thought: Starting thought (or auto-generate)

        Returns:
            Root node of explored tree
        """
        self.reset()

        # Create root
        root_thought = initial_thought or f"Analyser: {problem[:100]}"
        self.root = self._create_node(root_thought)
        self.root.score = await self.evaluate(self.root, problem)

        logger.info(f"Starting ToT exploration with strategy: {self.strategy}")

        if self.strategy == SearchStrategy.BFS:
            await self._explore_bfs(problem, context)
        elif self.strategy == SearchStrategy.DFS:
            await self._explore_dfs(self.root, problem, context)
        else:  # BEST_FIRST
            await self._explore_best_first(problem, context)

        logger.info(
            f"ToT exploration complete: {len(self.all_nodes)} nodes, "
            f"{len(self.solutions)} solutions"
        )

        return self.root

    async def _explore_bfs(
        self,
        problem: str,
        context: str,
    ) -> None:
        """Breadth-first exploration.

        Args:
            problem: Problem being solved
            context: Additional context
        """
        if not self.root:
            return

        frontier = [self.root]

        while frontier:
            # Process all nodes at current level
            next_frontier = []

            # Expand in parallel
            expansion_tasks = [
                self.expand(node, problem, context)
                for node in frontier
                if node.score >= self.pruning_threshold
            ]

            if not expansion_tasks:
                break

            results = await asyncio.gather(*expansion_tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list):
                    # Evaluate new children
                    for child in result:
                        child.score = await self.evaluate(child, problem)

                        if child.is_solution:
                            self.solutions.append(child)
                        elif child.score >= self.pruning_threshold:
                            next_frontier.append(child)

            frontier = next_frontier

            # Safety: limit total nodes
            if len(self.all_nodes) > 100:
                logger.warning("ToT node limit reached, stopping")
                break

    async def _explore_dfs(
        self,
        node: ThoughtNode,
        problem: str,
        context: str,
    ) -> None:
        """Depth-first exploration.

        Args:
            node: Current node
            problem: Problem being solved
            context: Additional context
        """
        if node.is_solution:
            self.solutions.append(node)
            return

        if node.score < self.pruning_threshold:
            return

        if len(self.all_nodes) > 100:
            return

        # Expand and recurse
        children = await self.expand(node, problem, context)

        for child in children:
            child.score = await self.evaluate(child, problem)
            await self._explore_dfs(child, problem, context)

    async def _explore_best_first(
        self,
        problem: str,
        context: str,
    ) -> None:
        """Best-first exploration.

        Args:
            problem: Problem being solved
            context: Additional context
        """
        if not self.root:
            return

        # Priority queue (sorted by score descending)
        frontier = [self.root]

        while frontier and len(self.all_nodes) < 100:
            # Get best node
            frontier.sort(key=lambda n: n.score, reverse=True)
            node = frontier.pop(0)

            if node.is_solution:
                self.solutions.append(node)
                continue

            if node.score < self.pruning_threshold:
                continue

            # Expand best node
            children = await self.expand(node, problem, context)

            for child in children:
                child.score = await self.evaluate(child, problem)
                if child.is_solution:
                    self.solutions.append(child)
                else:
                    frontier.append(child)

    def best_path(self) -> list[ThoughtNode]:
        """Get the best reasoning path found.

        Returns:
            List of nodes in best path
        """
        if self.solutions:
            # Return path to best solution
            best = max(self.solutions, key=lambda n: n.score)
            return self.get_path(best)

        if not self.all_nodes:
            return []

        # No solutions, return path to best-scoring node
        best = max(self.all_nodes.values(), key=lambda n: n.score)
        return self.get_path(best)

    def get_top_paths(self, k: int = 3) -> list[list[ThoughtNode]]:
        """Get top k reasoning paths.

        Args:
            k: Number of paths to return

        Returns:
            List of paths (each path is list of nodes)
        """
        # Get all leaf nodes
        leaves = [
            n for n in self.all_nodes.values()
            if not n.children
        ]

        # Sort by score
        leaves.sort(key=lambda n: n.score, reverse=True)

        return [self.get_path(leaf) for leaf in leaves[:k]]

    async def synthesize(self, problem: str) -> dict[str, Any]:
        """Synthesize final answer from exploration.

        Args:
            problem: Original problem

        Returns:
            Synthesized solution
        """
        top_paths = self.get_top_paths(3)

        if not top_paths:
            return {
                "solution": "Pas de solution trouvée",
                "confidence": 0.0,
                "justification": "",
                "alternatives": [],
            }

        if not self.llm:
            # Fallback: return best path
            best = top_paths[0]
            return {
                "solution": best[-1].thought if best else "Analyse incomplète",
                "confidence": best[-1].score if best else 0.0,
                "justification": " -> ".join(n.thought for n in best),
                "alternatives": [
                    p[-1].thought for p in top_paths[1:] if p
                ],
            }

        # Use LLM to synthesize
        paths_text = "\n\n".join(
            f"Chemin {i + 1} (score: {p[-1].score:.2f}):\n{self.get_path_text(p[-1])}"
            for i, p in enumerate(top_paths)
        )

        prompt = TOT_SYNTHESIZE_PROMPT.format(
            problem=problem,
            best_paths=paths_text,
        )

        try:
            response = await self.llm.generate(prompt, temperature=0.3)
            return self._parse_synthesis(response)
        except Exception as e:
            logger.warning(f"Synthesis failed: {e}")
            best = top_paths[0]
            return {
                "solution": best[-1].thought if best else "",
                "confidence": best[-1].score if best else 0.0,
                "justification": "Basé sur l'exploration de l'arbre",
                "alternatives": [],
            }

    def _parse_synthesis(self, response: str) -> dict[str, Any]:
        """Parse synthesis response.

        Args:
            response: Raw LLM response

        Returns:
            Parsed synthesis
        """
        solution = ""
        confidence = 0.7
        justification = ""
        alternatives: list[str] = []

        current_field = ""

        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("SOLUTION:"):
                solution = line.split(":", 1)[1].strip()
                current_field = "solution"
            elif line.startswith("CONFIANCE:"):
                with contextlib.suppress(ValueError):
                    confidence = float(line.split(":", 1)[1].strip())
            elif line.startswith("JUSTIFICATION:"):
                justification = line.split(":", 1)[1].strip()
                current_field = "justification"
            elif line.startswith("ALTERNATIVES:"):
                current_field = "alternatives"
            elif line.startswith("-") and current_field == "alternatives":
                alternatives.append(line.lstrip("-").strip())
            elif line and current_field == "solution":
                solution += " " + line
            elif line and current_field == "justification":
                justification += " " + line

        return {
            "solution": solution or response[:500],
            "confidence": max(0.0, min(1.0, confidence)),
            "justification": justification,
            "alternatives": alternatives[:3],
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert tree to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "strategy": self.strategy.value,
            "node_count": len(self.all_nodes),
            "solution_count": len(self.solutions),
            "max_depth_reached": max((n.depth for n in self.all_nodes.values()), default=0),
            "best_score": max((n.score for n in self.all_nodes.values()), default=0.0),
            "nodes": {k: v.to_dict() for k, v in self.all_nodes.items()},
        }

    def visualize_text(self) -> str:
        """Get text visualization of tree.

        Returns:
            ASCII tree representation
        """
        if not self.root:
            return "Arbre vide"

        lines = ["## Arbre de Pensées\n"]
        self._visualize_node(self.root, lines, "", True)
        return "\n".join(lines)

    def _visualize_node(
        self,
        node: ThoughtNode,
        lines: list[str],
        prefix: str,
        is_last: bool,
    ) -> None:
        """Recursively visualize node.

        Args:
            node: Node to visualize
            lines: Output lines
            prefix: Current line prefix
            is_last: Is this the last child
        """
        connector = "└── " if is_last else "├── "
        solution_mark = " ✅" if node.is_solution else ""
        score_color = "🟢" if node.score >= 0.7 else "🟡" if node.score >= 0.4 else "🔴"

        lines.append(
            f"{prefix}{connector}{score_color} [{node.score:.2f}] "
            f"{node.thought[:60]}{'...' if len(node.thought) > 60 else ''}{solution_mark}"
        )

        child_prefix = prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(node.children):
            self._visualize_node(
                child,
                lines,
                child_prefix,
                i == len(node.children) - 1,
            )


# Convenience function


async def explore_solutions(
    problem: str,
    context: str = "",
    llm: LLMProvider | None = None,
    breadth: int = 3,
    depth: int = 3,
) -> dict[str, Any]:
    """Quick tree exploration helper.

    Args:
        problem: Problem to solve
        context: Additional context
        llm: LLM provider
        breadth: Branch factor
        depth: Max depth

    Returns:
        Synthesized solution
    """
    tot = TreeOfThoughts(llm, breadth=breadth, max_depth=depth)
    await tot.explore(problem, context)
    return await tot.synthesize(problem)
