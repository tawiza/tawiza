"""Territorial Expert Router for TAJINE.

Implements Mixture-of-Experts (MoE) routing using MixLoRA
to adapt responses based on territorial/sectoral context.

Each expert specializes in a French territorial domain:
- immobilier: Real estate, DVF, property prices
- emploi: Employment, France Travail, job market
- entreprises: Companies, SIRENE, BODACC, business creation
- finances_locales: Local finances, OFGL, taxes, budgets
- demographie: Demographics, INSEE, population, migration
- infrastructure: Infrastructure, BAN, transport, equipment
"""

from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any, Protocol

from loguru import logger


class ExpertDomain(StrEnum):
    """Territorial expert domains."""

    IMMOBILIER = "immobilier"
    EMPLOI = "emploi"
    ENTREPRISES = "entreprises"
    FINANCES_LOCALES = "finances_locales"
    DEMOGRAPHIE = "demographie"
    INFRASTRUCTURE = "infrastructure"


# Domain definitions with keywords and descriptions
EXPERT_DEFINITIONS = {
    ExpertDomain.IMMOBILIER: {
        "description": "Expert transactions, DVF, prix m2, marché immobilier",
        "keywords": [
            "maison", "appartement", "prix", "m2", "dvf", "immobilier",
            "logement", "loyer", "achat", "vente", "transaction", "mutation",
            "terrain", "construction", "habitat", "propriétaire", "locataire",
            "foncier", "cadastre", "notaire",
        ],
        "sources": ["DVF", "INSEE", "Notaires"],
    },
    ExpertDomain.EMPLOI: {
        "description": "Expert France Travail, offres, chômage, marché du travail",
        "keywords": [
            "travail", "emploi", "chômage", "offre", "recrutement", "embauche",
            "salaire", "métier", "formation", "compétence", "pôle emploi",
            "france travail", "demandeur", "CDI", "CDD", "intérim", "stage",
            "apprentissage", "qualification", "DPAE",
        ],
        "sources": ["France Travail", "DARES", "URSSAF"],
    },
    ExpertDomain.ENTREPRISES: {
        "description": "Expert SIRENE, BODACC, créations, défaillances",
        "keywords": [
            "société", "entreprise", "création", "siret", "siren", "bodacc",
            "rcs", "kbis", "défaillance", "liquidation", "redressement",
            "établissement", "dirigeant", "effectif", "CA", "activité",
            "naf", "ape", "commerce", "industrie", "PME", "startup",
        ],
        "sources": ["SIRENE", "BODACC", "INPI"],
    },
    ExpertDomain.FINANCES_LOCALES: {
        "description": "Expert OFGL, budgets, fiscalité locale, finances publiques",
        "keywords": [
            "budget", "impôt", "taxe", "commune", "fiscalité", "recette",
            "dépense", "dette", "investissement", "fonctionnement", "dotation",
            "DGF", "CVAE", "CFE", "TFPB", "TFPNB", "DMTO", "intercommunalité",
            "EPCI", "trésorerie", "emprunt", "capacité",
        ],
        "sources": ["OFGL", "DGFiP", "Bercy"],
    },
    ExpertDomain.DEMOGRAPHIE: {
        "description": "Expert INSEE, population, migrations, structure démographique",
        "keywords": [
            "population", "habitant", "naissance", "décès", "migration",
            "âge", "pyramide", "ménage", "famille", "recensement", "densité",
            "vieillissement", "solde migratoire", "fécondité", "espérance",
            "ruralité", "urbain", "périurbain", "résidence",
        ],
        "sources": ["INSEE", "État civil", "Recensement"],
    },
    ExpertDomain.INFRASTRUCTURE: {
        "description": "Expert BAN, équipements, transport, services publics",
        "keywords": [
            "route", "école", "hôpital", "gare", "transport", "équipement",
            "service", "mairie", "bibliothèque", "sport", "culture",
            "accessibilité", "réseau", "fibre", "4G", "5G", "eau", "assainissement",
            "déchets", "énergie", "BAN", "adresse",
        ],
        "sources": ["BAN", "BPE", "OpenStreetMap"],
    },
}


@dataclass
class MixLoRAConfig:
    """Configuration for MixLoRA experts."""

    num_experts: int = 6
    top_k: int = 2  # Number of experts to activate per query
    lora_rank: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    router_type: str = "top_k"  # 'top_k', 'soft', 'hash'
    auxiliary_loss_weight: float = 0.01  # Load balancing loss
    base_model: str = "meta-llama/Llama-3.1-8B"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "num_experts": self.num_experts,
            "top_k": self.top_k,
            "lora_rank": self.lora_rank,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "router_type": self.router_type,
            "auxiliary_loss_weight": self.auxiliary_loss_weight,
            "base_model": self.base_model,
        }


@dataclass
class RoutingResult:
    """Result of expert routing."""

    activated_experts: list[ExpertDomain]
    expert_weights: dict[ExpertDomain, float]
    detected_keywords: list[str]
    confidence: float
    routing_reason: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "activated_experts": [e.value for e in self.activated_experts],
            "expert_weights": {k.value: v for k, v in self.expert_weights.items()},
            "detected_keywords": self.detected_keywords,
            "confidence": self.confidence,
            "routing_reason": self.routing_reason,
        }


@dataclass
class ExpertStats:
    """Statistics for expert usage."""

    domain: ExpertDomain
    activation_count: int = 0
    total_tokens_processed: int = 0
    avg_confidence: float = 0.0
    positive_feedback_rate: float = 0.0
    training_examples: int = 0
    last_trained: str | None = None


class MixLoRAModel(Protocol):
    """Protocol for MixLoRA model."""

    async def generate(
        self,
        prompt: str,
        active_experts: list[int],
        **kwargs: Any,
    ) -> str:
        """Generate response with specific experts active."""
        ...

    def get_expert_parameters(self, expert_idx: int) -> Any:
        """Get parameters for a specific expert."""
        ...


class TerritorialExpertRouter:
    """Routes queries to appropriate territorial experts.

    Uses keyword detection and optional embedding similarity
    to determine which domain experts should be activated.

    Integrates with MixLoRA for efficient expert switching.
    """

    def __init__(
        self,
        config: MixLoRAConfig | None = None,
        model: MixLoRAModel | None = None,
    ):
        """Initialize the router.

        Args:
            config: MixLoRA configuration
            model: Optional MixLoRA model instance
        """
        self.config = config or MixLoRAConfig()
        self.model = model

        # Map domains to expert indices
        self.domain_to_index = {
            domain: i for i, domain in enumerate(ExpertDomain)
        }
        self.index_to_domain = {
            i: domain for domain, i in self.domain_to_index.items()
        }

        # Expert statistics
        self.stats: dict[ExpertDomain, ExpertStats] = {
            domain: ExpertStats(domain=domain) for domain in ExpertDomain
        }

        # Training queues per domain
        self.training_queues: dict[ExpertDomain, list[dict[str, Any]]] = {
            domain: [] for domain in ExpertDomain
        }

        self._init_keyword_index()
        logger.info(
            f"TerritorialExpertRouter initialized with {len(ExpertDomain)} experts"
        )

    def _init_keyword_index(self) -> None:
        """Build inverted index from keywords to domains."""
        self.keyword_to_domains: dict[str, list[ExpertDomain]] = {}

        for domain, definition in EXPERT_DEFINITIONS.items():
            for keyword in definition["keywords"]:
                keyword_lower = keyword.lower()
                if keyword_lower not in self.keyword_to_domains:
                    self.keyword_to_domains[keyword_lower] = []
                self.keyword_to_domains[keyword_lower].append(domain)

    def detect_domains(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[list[ExpertDomain], dict[str, float], list[str]]:
        """Detect relevant domains from query and context.

        Args:
            query: User query
            context: Optional context (territory, sector, etc.)

        Returns:
            Tuple of (domains, scores, matched_keywords)
        """
        context = context or {}
        query_lower = query.lower()

        domain_scores: dict[ExpertDomain, float] = dict.fromkeys(ExpertDomain, 0.0)
        matched_keywords: list[str] = []

        # Score based on keyword matches
        for keyword, domains in self.keyword_to_domains.items():
            if keyword in query_lower:
                matched_keywords.append(keyword)
                for domain in domains:
                    # Longer keywords = stronger signal
                    weight = len(keyword) / 10.0
                    domain_scores[domain] += weight

        # Boost based on context
        if context.get("sector"):
            sector = context["sector"].lower()
            # NAF codes mapping
            if sector.startswith("68"):  # Immobilier
                domain_scores[ExpertDomain.IMMOBILIER] += 1.0
            elif sector.startswith("85"):  # Enseignement
                domain_scores[ExpertDomain.INFRASTRUCTURE] += 0.5
            elif sector.startswith(("46", "47")):  # Commerce
                domain_scores[ExpertDomain.ENTREPRISES] += 0.5

        if context.get("data_source"):
            source = context["data_source"].upper()
            for domain, definition in EXPERT_DEFINITIONS.items():
                if source in definition["sources"]:
                    domain_scores[domain] += 0.8

        # Normalize scores
        max_score = max(domain_scores.values()) if domain_scores else 1.0
        if max_score > 0:
            domain_scores = {
                d: s / max_score for d, s in domain_scores.items()
            }

        # Get top-k domains
        sorted_domains = sorted(
            domain_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        top_domains = [
            d for d, s in sorted_domains[: self.config.top_k]
            if s > 0.1  # Minimum threshold
        ]

        # Default to entreprises if no strong signal
        if not top_domains:
            top_domains = [ExpertDomain.ENTREPRISES]
            domain_scores[ExpertDomain.ENTREPRISES] = 0.5

        return top_domains, domain_scores, matched_keywords

    def route(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> RoutingResult:
        """Route query to appropriate experts.

        Args:
            query: User query
            context: Optional context

        Returns:
            RoutingResult with activated experts and weights
        """
        domains, scores, keywords = self.detect_domains(query, context)

        # Update statistics
        for domain in domains:
            self.stats[domain].activation_count += 1

        # Compute confidence based on score distribution
        if len(domains) == 1:
            confidence = scores[domains[0]]
        else:
            # Higher confidence if top scores are close (clear multi-domain query)
            # Lower if only one domain is strongly activated
            top_scores = [scores[d] for d in domains]
            confidence = sum(top_scores) / len(top_scores)

        # Build routing reason
        if keywords:
            reason = f"Mots-clés détectés: {', '.join(keywords[:5])}"
        else:
            reason = f"Routage par défaut vers {domains[0].value}"

        result = RoutingResult(
            activated_experts=domains,
            expert_weights={d: scores[d] for d in domains},
            detected_keywords=keywords,
            confidence=confidence,
            routing_reason=reason,
        )

        logger.debug(
            f"Routed to experts: {[d.value for d in domains]} "
            f"(confidence: {confidence:.2f})"
        )

        return result

    def get_expert_indices(self, domains: list[ExpertDomain]) -> list[int]:
        """Convert domains to expert indices.

        Args:
            domains: List of expert domains

        Returns:
            List of expert indices for MixLoRA
        """
        return [self.domain_to_index[d] for d in domains]

    async def generate_with_experts(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        **generate_kwargs: Any,
    ) -> tuple[str, RoutingResult]:
        """Generate response using appropriate experts.

        Args:
            query: User query
            context: Optional context
            **generate_kwargs: Additional generation parameters

        Returns:
            Tuple of (response, routing_result)
        """
        # Route to experts
        routing = self.route(query, context)
        expert_indices = self.get_expert_indices(routing.activated_experts)

        if not self.model:
            # No model available - return routing info only
            logger.warning("No MixLoRA model available for generation")
            return "", routing

        # Generate with activated experts
        try:
            response = await self.model.generate(
                query,
                active_experts=expert_indices,
                **generate_kwargs,
            )
            return response, routing
        except Exception as e:
            logger.error(f"Expert generation failed: {e}")
            return "", routing

    def add_training_example(
        self,
        domain: ExpertDomain,
        example: dict[str, Any],
    ) -> None:
        """Add training example for a specific domain.

        Args:
            domain: Target domain
            example: Training example (query, response, feedback)
        """
        self.training_queues[domain].append(example)
        self.stats[domain].training_examples += 1

        logger.debug(
            f"Added training example for {domain.value} "
            f"(queue size: {len(self.training_queues[domain])})"
        )

    def get_training_ready_domains(
        self,
        min_examples: int = 50,
    ) -> list[ExpertDomain]:
        """Get domains with enough examples for training.

        Args:
            min_examples: Minimum examples required

        Returns:
            List of domains ready for training
        """
        return [
            domain
            for domain, queue in self.training_queues.items()
            if len(queue) >= min_examples
        ]

    def get_training_data(
        self,
        domain: ExpertDomain,
    ) -> list[dict[str, Any]]:
        """Get training data for a domain.

        Args:
            domain: Target domain

        Returns:
            Training examples
        """
        return list(self.training_queues[domain])

    def clear_training_queue(self, domain: ExpertDomain) -> int:
        """Clear training queue after training.

        Args:
            domain: Domain to clear

        Returns:
            Number of cleared examples
        """
        count = len(self.training_queues[domain])
        self.training_queues[domain].clear()
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get router statistics.

        Returns:
            Statistics dictionary
        """
        total_activations = sum(s.activation_count for s in self.stats.values())

        return {
            "total_activations": total_activations,
            "experts": {
                domain.value: {
                    "activation_count": stats.activation_count,
                    "activation_rate": (
                        stats.activation_count / total_activations
                        if total_activations > 0
                        else 0.0
                    ),
                    "training_queue_size": len(self.training_queues[domain]),
                    "training_examples": stats.training_examples,
                }
                for domain, stats in self.stats.items()
            },
            "config": self.config.to_dict(),
        }

    def get_expert_info(self, domain: ExpertDomain) -> dict[str, Any]:
        """Get information about a specific expert.

        Args:
            domain: Expert domain

        Returns:
            Expert information
        """
        definition = EXPERT_DEFINITIONS[domain]
        stats = self.stats[domain]

        return {
            "domain": domain.value,
            "description": definition["description"],
            "keywords": definition["keywords"][:10],  # First 10
            "data_sources": definition["sources"],
            "activation_count": stats.activation_count,
            "training_examples": stats.training_examples,
            "queue_size": len(self.training_queues[domain]),
        }


    async def check_and_trigger_training(
        self,
        fine_tuner: Any = None,
        min_examples: int = 50,
    ) -> dict[str, Any]:
        """Check domains ready for training and trigger fine-tuning.

        This is the automatic retraining trigger mechanism.
        Called during PPDSL Learn phase.

        Args:
            fine_tuner: TAJINEFineTuner instance for training
            min_examples: Minimum examples required per domain

        Returns:
            Dictionary with training results per domain
        """
        results: dict[str, Any] = {
            "triggered": False,
            "domains_trained": [],
            "domains_pending": {},
            "errors": [],
        }

        ready_domains = self.get_training_ready_domains(min_examples)

        if not ready_domains:
            # Report pending domains
            for domain in ExpertDomain:
                queue_size = len(self.training_queues[domain])
                if queue_size > 0:
                    results["domains_pending"][domain.value] = {
                        "current": queue_size,
                        "required": min_examples,
                        "progress": queue_size / min_examples,
                    }
            return results

        results["triggered"] = True
        logger.info(f"Training triggered for {len(ready_domains)} domains: {[d.value for d in ready_domains]}")

        for domain in ready_domains:
            training_data = self.get_training_data(domain)

            try:
                if fine_tuner:
                    # Build domain-specific training examples
                    from src.infrastructure.agents.tajine.learning.data_collector import (
                        SuccessTrace,
                        TrainingData,
                    )

                    success_traces = [
                        SuccessTrace(
                            instruction=ex.get("query", ""),
                            input_context=f"Domain: {domain.value}",
                            output=ex.get("response", ""),
                            reasoning=ex.get("reasoning"),
                            cognitive_level=ex.get("cognitive_level", 3),
                            quality_score=ex.get("quality", 0.8),
                        )
                        for ex in training_data
                        if ex.get("query") and ex.get("response")
                    ]

                    domain_training_data = TrainingData(success_traces=success_traces)

                    # Trigger fine-tuning for this domain
                    train_result = await fine_tuner.finetune(domain_training_data)

                    if train_result.get("success"):
                        # Clear queue after successful training
                        cleared = self.clear_training_queue(domain)
                        self.stats[domain].last_trained = (
                            __import__("datetime").datetime.now().isoformat()
                        )
                        results["domains_trained"].append({
                            "domain": domain.value,
                            "examples_used": cleared,
                            "result": train_result,
                        })
                        logger.info(
                            f"Successfully trained {domain.value} with {cleared} examples"
                        )
                    else:
                        results["errors"].append({
                            "domain": domain.value,
                            "error": train_result.get("error", "Unknown error"),
                        })
                else:
                    # No fine-tuner - just log and keep data
                    logger.warning(
                        f"No fine-tuner provided, skipping training for {domain.value}"
                    )
                    results["errors"].append({
                        "domain": domain.value,
                        "error": "No fine-tuner available",
                    })

            except Exception as e:
                logger.error(f"Training failed for {domain.value}: {e}")
                results["errors"].append({
                    "domain": domain.value,
                    "error": str(e),
                })

        return results


# Singleton instance
_router_instance: TerritorialExpertRouter | None = None


def get_expert_router(
    config: MixLoRAConfig | None = None,
) -> TerritorialExpertRouter:
    """Get or create the expert router singleton.

    Args:
        config: Optional configuration (used only for first creation)

    Returns:
        TerritorialExpertRouter instance
    """
    global _router_instance
    if _router_instance is None:
        _router_instance = TerritorialExpertRouter(config)
    return _router_instance
