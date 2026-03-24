"""Hypothesis Generator - DSPy-based hypothesis generation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class OllamaLLMClient:
    """Simple synchronous Ollama client for hypothesis generation."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen3:8b"):
        self.base_url = base_url
        self.model = model

    def generate(self, system: str, prompt: str) -> str:
        """Generate text using Ollama API."""
        import json
        import urllib.request

        payload = json.dumps(
            {
                "model": self.model,
                "system": system,
                "prompt": prompt + "\n/no_think",
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 512,
                },
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "")
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return ""


def create_hypothesis_generator(
    ollama_url: str = "http://localhost:11434",
    model: str = "qwen3:8b",
) -> HypothesisGenerator:
    """Factory function to create HypothesisGenerator with Ollama backend."""
    client = OllamaLLMClient(base_url=ollama_url, model=model)
    return HypothesisGenerator(llm_client=client)


@dataclass
class Hypothesis:
    """A hypothesis to investigate."""

    statement: str
    confidence: float = 0.5
    sources_to_check: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    priority: int = 1  # 1=high, 2=medium, 3=low


class HypothesisGenerator:
    """
    Generate hypotheses from analysis context using LLM.

    Uses structured prompting to generate actionable hypotheses
    that guide the DataHunter's search.
    """

    SYSTEM_PROMPT = """Tu es un analyste territorial expert.
Génère des hypothèses de recherche à partir du contexte donné.
Chaque hypothèse doit être:
- Vérifiable avec des données publiques
- Pertinente pour l'intelligence territoriale
- Actionnable (suggère des sources à consulter)

Format: Une hypothèse par ligne."""

    def __init__(self, llm_client=None):
        """Initialize with optional LLM client."""
        self.llm_client = llm_client  # Injected or created later

    def generate(
        self,
        context: str,
        territory: str,
        max_hypotheses: int = 5,
        kg_gaps: dict | None = None,
    ) -> list[Hypothesis]:
        """
        Generate hypotheses from context.

        Args:
            context: Analysis context/query
            territory: Territory code (e.g., "31" for Haute-Garonne)
            max_hypotheses: Maximum hypotheses to generate
            kg_gaps: Known gaps in knowledge graph to address

        Returns:
            List of Hypothesis objects
        """
        # Build prompt
        prompt_parts = [
            f"Contexte: {context}",
            f"Territoire: {territory}",
        ]

        if kg_gaps:
            if kg_gaps.get("missing_fields"):
                prompt_parts.append(f"Données manquantes: {', '.join(kg_gaps['missing_fields'])}")
            if kg_gaps.get("stale_entities"):
                prompt_parts.append(
                    f"Entités obsolètes: {len(kg_gaps['stale_entities'])} à rafraîchir"
                )

        prompt_parts.append(f"\nGénère {max_hypotheses} hypothèses de recherche:")

        user_prompt = "\n".join(prompt_parts)

        # Call LLM
        raw_hypotheses = self._call_llm(user_prompt)

        # Parse into Hypothesis objects
        hypotheses = []
        for i, statement in enumerate(raw_hypotheses[:max_hypotheses]):
            h = Hypothesis(
                statement=statement.strip(),
                confidence=0.7 - (i * 0.1),  # Decreasing confidence
                sources_to_check=self._suggest_sources(statement),
                search_queries=self._generate_search_queries(statement, territory),
                priority=min(i + 1, 3),
            )
            hypotheses.append(h)

        return hypotheses

    def _call_llm(self, prompt: str) -> list[str]:
        """
        Call LLM to generate hypotheses.

        Override or mock this for testing.
        """
        if self.llm_client is None:
            # Fallback: return empty or use heuristics
            logger.warning("No LLM client configured, returning empty hypotheses")
            return []

        try:
            response = self.llm_client.generate(
                system=self.SYSTEM_PROMPT,
                prompt=prompt,
            )
            return response.strip().split("\n")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return []

    def _suggest_sources(self, statement: str) -> list[str]:
        """Suggest sources based on hypothesis content."""
        sources = []
        statement_lower = statement.lower()

        # Keyword-based source mapping
        if any(k in statement_lower for k in ["entreprise", "siren", "création"]):
            sources.append("sirene")
        if any(k in statement_lower for k in ["faillite", "liquidation", "procédure"]):
            sources.append("bodacc")
        if any(k in statement_lower for k in ["marché public", "appel d'offres"]):
            sources.append("boamp")
        if any(k in statement_lower for k in ["immobilier", "construction"]):
            sources.append("dvf")

        if any(k in statement_lower for k in ["emploi", "ch\u00f4mage", "recrutement"]):
            sources.append("france_travail")
        if any(k in statement_lower for k in ["population", "d\u00e9mograph", "m\u00e9nage"]):
            sources.append("insee_local")
        if any(k in statement_lower for k in ["pib", "inflation", "croissance", "macro"]):
            sources.append("dbnomics")
        if any(k in statement_lower for k in ["subvention", "aide", "financement"]):
            sources.append("subventions")
        if any(k in statement_lower for k in ["adresse", "g\u00e9o", "localisation"]):
            sources.append("ban")

        # Default if no match
        if not sources:
            sources = ["sirene", "bodacc"]

        return sources

    def _generate_search_queries(self, statement: str, territory: str) -> list[str]:
        """Generate search queries from hypothesis statement."""
        queries = []
        # Base query from statement
        queries.append(f"{statement} {territory}")
        # Add territory-specific variant
        queries.append(f"département {territory} {statement[:50]}")
        return queries
