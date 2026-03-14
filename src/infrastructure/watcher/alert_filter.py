"""Intelligent alert filtering using LLM.

Filters alerts by relevance using an LLM to score business value.
"""

import asyncio
import json
from dataclasses import dataclass
from enum import StrEnum

from loguru import logger

from ..dashboard import Alert


class AlertPriority(StrEnum):
    """Priority levels for alerts."""

    CRITICAL = "critical"  # Score 80-100: Action immediate requise
    HIGH = "high"  # Score 60-79: Important, a traiter rapidement
    MEDIUM = "medium"  # Score 40-59: Interessant, a surveiller
    LOW = "low"  # Score 20-39: Information de fond
    NOISE = "noise"  # Score 0-19: Non pertinent


@dataclass
class ScoredAlert:
    """Alert with relevance score and analysis."""

    alert: Alert
    score: float  # 0-100
    priority: AlertPriority
    relevance_reason: str
    business_impact: str
    recommended_action: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            **self.alert.to_dict(),
            "score": self.score,
            "priority": self.priority.value,
            "relevance_reason": self.relevance_reason,
            "business_impact": self.business_impact,
            "recommended_action": self.recommended_action,
        }


FILTER_PROMPT = """Tu es un analyste de veille economique. Evalue la pertinence de cette alerte pour un utilisateur qui surveille le marche territorial francais.

**Contexte utilisateur:**
- Mots-cles surveilles: {keywords}
- Secteurs d'interet: intelligence territoriale, entreprises, marches publics

**Alerte a evaluer:**
- Source: {source}
- Type: {type}
- Titre: {title}
- Contenu: {content}

**Reponds UNIQUEMENT en JSON valide:**
{{
    "score": <0-100>,
    "relevance_reason": "<pourquoi pertinent ou non, 1 phrase>",
    "business_impact": "<impact business potentiel, 1 phrase>",
    "recommended_action": "<action recommandee ou null si non pertinent>"
}}

Criteres de scoring:
- 80-100 (CRITICAL): Opportunite commerciale directe, marche public pertinent, creation d'entreprise cible
- 60-79 (HIGH): Information strategique importante, concurrent, partenaire potentiel
- 40-59 (MEDIUM): Tendance de marche, signal faible interessant
- 20-39 (LOW): Information de contexte, peu actionnable
- 0-19 (NOISE): Non pertinent, hors sujet, spam
"""


class AlertFilter:
    """LLM-based intelligent alert filter."""

    def __init__(self, ollama_model: str = "qwen3.5:27b"):
        """Initialize the filter.

        Args:
            ollama_model: Ollama model to use for scoring
        """
        self.model = ollama_model
        self._client = None

    async def _get_client(self):
        """Lazy load Ollama client."""
        if self._client is None:
            from ..llm import OllamaClient

            self._client = OllamaClient(model=self.model)
        return self._client

    def _score_to_priority(self, score: float) -> AlertPriority:
        """Convert score to priority level."""
        if score >= 80:
            return AlertPriority.CRITICAL
        elif score >= 60:
            return AlertPriority.HIGH
        elif score >= 40:
            return AlertPriority.MEDIUM
        elif score >= 20:
            return AlertPriority.LOW
        else:
            return AlertPriority.NOISE

    async def score_alert(
        self,
        alert: Alert,
        keywords: list[str],
    ) -> ScoredAlert:
        """Score a single alert for relevance.

        Args:
            alert: Alert to score
            keywords: User's watchlist keywords

        Returns:
            ScoredAlert with score and analysis
        """
        try:
            client = await self._get_client()

            prompt = FILTER_PROMPT.format(
                keywords=", ".join(keywords) if keywords else "aucun specifie",
                source=alert.source.value if hasattr(alert.source, "value") else alert.source,
                type=alert.type.value if hasattr(alert.type, "value") else alert.type,
                title=alert.title,
                content=alert.content[:500] if alert.content else "N/A",
            )

            response = await client.generate(prompt=prompt, max_tokens=300)

            # Parse JSON response
            try:
                # Extract JSON from response (handle markdown code blocks)
                json_str = response
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    json_str = response.split("```")[1].split("```")[0]

                result = json.loads(json_str.strip())

                score = float(result.get("score", 50))
                score = max(0, min(100, score))  # Clamp to 0-100

                return ScoredAlert(
                    alert=alert,
                    score=score,
                    priority=self._score_to_priority(score),
                    relevance_reason=result.get("relevance_reason", "Non analyse"),
                    business_impact=result.get("business_impact", "Impact inconnu"),
                    recommended_action=result.get("recommended_action"),
                )

            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response: {response[:100]}")
                # Fallback: use keyword matching for basic scoring
                return self._fallback_score(alert, keywords)

        except Exception as e:
            logger.error(f"Error scoring alert: {e}")
            return self._fallback_score(alert, keywords)

    def _fallback_score(self, alert: Alert, keywords: list[str]) -> ScoredAlert:
        """Fallback scoring using simple keyword matching."""
        score = 30  # Base score
        text = f"{alert.title} {alert.content or ''}".lower()

        # Boost score for keyword matches
        matches = sum(1 for kw in keywords if kw.lower() in text)
        score += matches * 15

        # Boost for certain alert types
        type_str = alert.type.value if hasattr(alert.type, "value") else str(alert.type)
        if type_str in ["creation", "marche", "attribution"]:
            score += 10

        score = min(100, score)

        return ScoredAlert(
            alert=alert,
            score=score,
            priority=self._score_to_priority(score),
            relevance_reason=f"Correspondance mots-cles: {matches}",
            business_impact="A evaluer manuellement",
            recommended_action=None,
        )

    async def filter_alerts(
        self,
        alerts: list[Alert],
        keywords: list[str],
        min_priority: AlertPriority = AlertPriority.LOW,
        batch_size: int = 5,
    ) -> list[ScoredAlert]:
        """Filter and score a batch of alerts.

        Args:
            alerts: Alerts to filter
            keywords: User's watchlist keywords
            min_priority: Minimum priority to include
            batch_size: Number of alerts to process concurrently

        Returns:
            List of ScoredAlerts above minimum priority, sorted by score
        """
        if not alerts:
            return []

        scored = []
        priority_order = [
            AlertPriority.NOISE,
            AlertPriority.LOW,
            AlertPriority.MEDIUM,
            AlertPriority.HIGH,
            AlertPriority.CRITICAL,
        ]
        min_idx = priority_order.index(min_priority)

        # Process in batches to avoid overwhelming Ollama
        for i in range(0, len(alerts), batch_size):
            batch = alerts[i : i + batch_size]
            tasks = [self.score_alert(alert, keywords) for alert in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, ScoredAlert):
                    # Filter by minimum priority
                    result_idx = priority_order.index(result.priority)
                    if result_idx >= min_idx:
                        scored.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Alert scoring failed: {result}")

        # Sort by score descending
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored

    async def get_priority_summary(self, scored_alerts: list[ScoredAlert]) -> dict:
        """Generate a summary of alerts by priority.

        Args:
            scored_alerts: List of scored alerts

        Returns:
            Summary dictionary with counts and highlights
        """
        summary = {
            "total": len(scored_alerts),
            "by_priority": {p.value: 0 for p in AlertPriority},
            "critical_alerts": [],
            "high_alerts": [],
            "avg_score": 0,
        }

        if not scored_alerts:
            return summary

        total_score = 0
        for sa in scored_alerts:
            summary["by_priority"][sa.priority.value] += 1
            total_score += sa.score

            if sa.priority == AlertPriority.CRITICAL:
                summary["critical_alerts"].append(
                    {
                        "title": sa.alert.title,
                        "score": sa.score,
                        "reason": sa.relevance_reason,
                        "action": sa.recommended_action,
                    }
                )
            elif sa.priority == AlertPriority.HIGH:
                summary["high_alerts"].append(
                    {
                        "title": sa.alert.title,
                        "score": sa.score,
                        "reason": sa.relevance_reason,
                    }
                )

        summary["avg_score"] = round(total_score / len(scored_alerts), 1)
        return summary


# Factory function
def create_alert_filter(model: str = "qwen3.5:27b") -> AlertFilter:
    """Create an AlertFilter instance.

    Args:
        model: Ollama model to use

    Returns:
        Configured AlertFilter
    """
    return AlertFilter(ollama_model=model)
