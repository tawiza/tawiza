"""Chain-of-Thought reasoning for TAJINE agent.

Provides explicit step-by-step reasoning to make TAJINE's
analysis process transparent and verifiable.
"""

import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Protocol

from loguru import logger


class ThoughtType(StrEnum):
    """Types of thoughts in the chain."""

    OBSERVATION = "observation"  # What I see in the data
    HYPOTHESIS = "hypothesis"  # What I think might be true
    ANALYSIS = "analysis"  # Deeper examination
    INFERENCE = "inference"  # Logical conclusion
    QUESTION = "question"  # Need more information
    CONCLUSION = "conclusion"  # Final determination


@dataclass
class ThoughtStep:
    """A single step in the chain of thought."""

    step_id: int
    thought_type: ThoughtType
    thought: str  # "Je remarque que..."
    observation: str  # "Les donnees montrent..."
    reasoning: str  # "Donc, je conclus..."
    confidence: float  # 0.0 - 1.0
    evidence: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_id": self.step_id,
            "thought_type": self.thought_type.value,
            "thought": self.thought,
            "observation": self.observation,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_markdown(self) -> str:
        """Format as markdown for display."""
        icon = {
            ThoughtType.OBSERVATION: "👁️",
            ThoughtType.HYPOTHESIS: "💭",
            ThoughtType.ANALYSIS: "🔍",
            ThoughtType.INFERENCE: "💡",
            ThoughtType.QUESTION: "❓",
            ThoughtType.CONCLUSION: "✅",
        }.get(self.thought_type, "📝")

        lines = [
            f"### {icon} Étape {self.step_id}: {self.thought_type.value.title()}",
            f"**Pensée:** {self.thought}",
            f"**Observation:** {self.observation}",
            f"**Raisonnement:** {self.reasoning}",
            f"**Confiance:** {self.confidence:.0%}",
        ]

        if self.evidence:
            lines.append("**Preuves:**")
            for ev in self.evidence:
                lines.append(f"  - {ev}")

        return "\n".join(lines)


class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt."""
        ...


# Prompt templates for Chain-of-Thought
COT_SYSTEM_PROMPT = """Tu es un expert en analyse territoriale et économique française.
Tu dois raisonner étape par étape, en explicitant chaque pensée.

Pour chaque étape de raisonnement, tu dois fournir:
1. PENSÉE: Ce que tu remarques ou penses
2. OBSERVATION: Ce que les données montrent concrètement
3. RAISONNEMENT: La logique qui te mène à ta conclusion
4. CONFIANCE: Un score de 0.0 à 1.0 sur ta certitude

Utilise le format suivant pour chaque étape:
[ÉTAPE N]
TYPE: observation|hypothesis|analysis|inference|question|conclusion
PENSÉE: ...
OBSERVATION: ...
RAISONNEMENT: ...
CONFIANCE: 0.X
PREUVES: preuve1 | preuve2 | ...
[/ÉTAPE]
"""

COT_STEP_PROMPT = """Contexte: {context}

Question: {question}

Données disponibles:
{data}

Étapes précédentes:
{previous_steps}

Génère la prochaine étape de raisonnement."""

COT_FINAL_PROMPT = """Basé sur les étapes de raisonnement suivantes:
{reasoning_chain}

Question originale: {question}

Fournis une conclusion finale avec:
1. Réponse synthétique
2. Niveau de confiance global
3. Points clés du raisonnement
"""


class ChainOfThought:
    """Chain-of-Thought reasoning engine.

    Generates explicit step-by-step reasoning that can be
    inspected and validated by users.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        max_steps: int = 10,
    ):
        """Initialize the Chain-of-Thought engine.

        Args:
            llm_provider: LLM for generating thoughts
            max_steps: Maximum reasoning steps
        """
        self.llm = llm_provider
        self.max_steps = max_steps
        self.steps: list[ThoughtStep] = []
        self._step_counter = 0

    def reset(self) -> None:
        """Reset the chain for a new reasoning session."""
        self.steps = []
        self._step_counter = 0

    def add_step(
        self,
        thought_type: ThoughtType,
        thought: str,
        observation: str,
        reasoning: str,
        confidence: float,
        evidence: list[str] | None = None,
    ) -> ThoughtStep:
        """Manually add a reasoning step.

        Args:
            thought_type: Type of thought
            thought: The thought itself
            observation: Data observation
            reasoning: Logical reasoning
            confidence: Confidence score (0-1)
            evidence: Supporting evidence

        Returns:
            The created ThoughtStep
        """
        self._step_counter += 1
        step = ThoughtStep(
            step_id=self._step_counter,
            thought_type=thought_type,
            thought=thought,
            observation=observation,
            reasoning=reasoning,
            confidence=max(0.0, min(1.0, confidence)),
            evidence=evidence or [],
        )
        self.steps.append(step)
        logger.debug(f"Added thought step {step.step_id}: {thought_type.value}")
        return step

    async def think(
        self,
        context: str,
        question: str,
        data: str = "",
    ) -> ThoughtStep:
        """Generate a single reasoning step using LLM.

        Args:
            context: Current context
            question: Question being answered
            data: Available data

        Returns:
            Generated ThoughtStep
        """
        if not self.llm:
            # Fallback: create observation step
            return self.add_step(
                thought_type=ThoughtType.OBSERVATION,
                thought=f"Analyse de: {question[:100]}",
                observation=f"Contexte disponible: {context[:200]}",
                reasoning="Analyse basée sur les données fournies",
                confidence=0.5,
            )

        # Format previous steps
        previous = "\n".join(
            f"Étape {s.step_id}: {s.thought}" for s in self.steps[-3:]
        )

        prompt = COT_STEP_PROMPT.format(
            context=context,
            question=question,
            data=data[:2000],  # Limit data size
            previous_steps=previous or "Aucune",
        )

        try:
            response = await self.llm.generate(
                f"{COT_SYSTEM_PROMPT}\n\n{prompt}",
                temperature=0.3,
                max_tokens=500,
            )
            return self._parse_step(response)
        except Exception as e:
            logger.warning(f"LLM thought generation failed: {e}")
            return self.add_step(
                thought_type=ThoughtType.OBSERVATION,
                thought=f"Analyse de: {question[:100]}",
                observation="Données disponibles analysées",
                reasoning="Raisonnement basé sur le contexte",
                confidence=0.4,
            )

    def _parse_step(self, response: str) -> ThoughtStep:
        """Parse LLM response into ThoughtStep.

        Args:
            response: Raw LLM response

        Returns:
            Parsed ThoughtStep
        """
        # Default values
        thought_type = ThoughtType.ANALYSIS
        thought = ""
        observation = ""
        reasoning = ""
        confidence = 0.5
        evidence: list[str] = []

        # Parse response
        lines = response.strip().split("\n")
        current_field = ""

        for line in lines:
            line = line.strip()
            if line.startswith("TYPE:"):
                type_str = line.replace("TYPE:", "").strip().lower()
                with contextlib.suppress(ValueError):
                    thought_type = ThoughtType(type_str)
            elif line.startswith("PENSÉE:") or line.startswith("PENSEE:"):
                thought = line.split(":", 1)[1].strip()
                current_field = "thought"
            elif line.startswith("OBSERVATION:"):
                observation = line.split(":", 1)[1].strip()
                current_field = "observation"
            elif line.startswith("RAISONNEMENT:"):
                reasoning = line.split(":", 1)[1].strip()
                current_field = "reasoning"
            elif line.startswith("CONFIANCE:"):
                try:
                    conf_str = line.replace("CONFIANCE:", "").strip()
                    confidence = float(conf_str)
                except ValueError:
                    pass
            elif line.startswith("PREUVES:"):
                evidence = [e.strip() for e in line.split(":", 1)[1].split("|")]
            elif line and current_field:
                # Continuation of previous field
                if current_field == "thought":
                    thought += " " + line
                elif current_field == "observation":
                    observation += " " + line
                elif current_field == "reasoning":
                    reasoning += " " + line

        return self.add_step(
            thought_type=thought_type,
            thought=thought or "Analyse en cours",
            observation=observation or "Examen des données",
            reasoning=reasoning or "Déduction logique",
            confidence=confidence,
            evidence=evidence,
        )

    async def reason_through(
        self,
        problem: str,
        context: str = "",
        data: str = "",
        max_steps: int | None = None,
    ) -> list[ThoughtStep]:
        """Reason through a problem step by step.

        Args:
            problem: Problem to solve
            context: Additional context
            data: Available data
            max_steps: Override max steps

        Returns:
            List of reasoning steps
        """
        self.reset()
        max_steps = max_steps or self.max_steps

        logger.info(f"Starting CoT reasoning for: {problem[:100]}...")

        for i in range(max_steps):
            step = await self.think(context, problem, data)

            # Stop if we reach a conclusion
            if step.thought_type == ThoughtType.CONCLUSION:
                logger.info(f"Reached conclusion at step {i + 1}")
                break

            # Stop if confidence is very high
            if step.confidence >= 0.95:
                # Add final conclusion
                self.add_step(
                    thought_type=ThoughtType.CONCLUSION,
                    thought="Conclusion basée sur l'analyse",
                    observation=step.observation,
                    reasoning=step.reasoning,
                    confidence=step.confidence,
                    evidence=step.evidence,
                )
                break

        logger.info(f"CoT reasoning completed with {len(self.steps)} steps")
        return self.steps

    async def get_conclusion(
        self,
        question: str,
    ) -> dict[str, Any]:
        """Get final conclusion from reasoning chain.

        Args:
            question: Original question

        Returns:
            Conclusion with summary and confidence
        """
        if not self.steps:
            return {
                "answer": "Pas de raisonnement disponible",
                "confidence": 0.0,
                "key_points": [],
            }

        if self.llm:
            # Use LLM to synthesize conclusion
            chain_text = "\n\n".join(s.to_markdown() for s in self.steps)
            prompt = COT_FINAL_PROMPT.format(
                reasoning_chain=chain_text,
                question=question,
            )

            try:
                response = await self.llm.generate(prompt, temperature=0.2)
                return self._parse_conclusion(response)
            except Exception as e:
                logger.warning(f"Conclusion generation failed: {e}")

        # Fallback: use last conclusion step
        conclusion_steps = [
            s for s in self.steps if s.thought_type == ThoughtType.CONCLUSION
        ]

        if conclusion_steps:
            last = conclusion_steps[-1]
            return {
                "answer": last.reasoning,
                "confidence": last.confidence,
                "key_points": last.evidence,
            }

        # No conclusion, summarize from all steps
        avg_confidence = sum(s.confidence for s in self.steps) / len(self.steps)
        return {
            "answer": self.steps[-1].reasoning if self.steps else "Analyse incomplète",
            "confidence": avg_confidence,
            "key_points": [s.thought for s in self.steps[-3:]],
        }

    def _parse_conclusion(self, response: str) -> dict[str, Any]:
        """Parse conclusion response.

        Args:
            response: LLM response

        Returns:
            Parsed conclusion
        """
        # Simple parsing - could be more sophisticated
        lines = response.strip().split("\n")
        answer = ""
        confidence = 0.7
        key_points: list[str] = []

        for line in lines:
            line = line.strip()
            if line.startswith("-") or line.startswith("•"):
                key_points.append(line.lstrip("-•").strip())
            elif "confiance" in line.lower():
                try:
                    # Extract number from line
                    import re
                    nums = re.findall(r"0\.\d+|\d+%", line)
                    if nums:
                        val = nums[0]
                        confidence = float(val.replace("%", "")) / 100 if "%" in val else float(val)
                except (ValueError, IndexError):
                    pass
            elif line and not answer:
                answer = line

        return {
            "answer": answer or response[:500],
            "confidence": min(1.0, max(0.0, confidence)),
            "key_points": key_points[:5],
        }

    def get_chain_summary(self) -> str:
        """Get a summary of the reasoning chain.

        Returns:
            Markdown-formatted summary
        """
        if not self.steps:
            return "Aucun raisonnement disponible."

        lines = [
            "## Chaîne de Raisonnement",
            f"**Étapes:** {len(self.steps)}",
            f"**Confiance moyenne:** {sum(s.confidence for s in self.steps) / len(self.steps):.0%}",
            "",
        ]

        for step in self.steps:
            lines.append(step.to_markdown())
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert chain to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "step_count": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
            "avg_confidence": (
                sum(s.confidence for s in self.steps) / len(self.steps)
                if self.steps
                else 0.0
            ),
            "has_conclusion": any(
                s.thought_type == ThoughtType.CONCLUSION for s in self.steps
            ),
        }


# Convenience functions for quick reasoning


async def quick_reason(
    problem: str,
    context: str = "",
    llm: LLMProvider | None = None,
    max_steps: int = 5,
) -> dict[str, Any]:
    """Quick reasoning helper.

    Args:
        problem: Problem to reason about
        context: Additional context
        llm: LLM provider
        max_steps: Maximum steps

    Returns:
        Conclusion dictionary
    """
    cot = ChainOfThought(llm, max_steps)
    await cot.reason_through(problem, context)
    return await cot.get_conclusion(problem)
