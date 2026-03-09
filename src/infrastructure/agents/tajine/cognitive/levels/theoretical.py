"""
TheoreticalLevel - Level 5 of CognitiveEngine

Validates recommendations against theoretical frameworks and
produces concrete implementation plans with stakeholders, timelines, and KPIs.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.infrastructure.agents.tajine.cognitive.levels.discovery import BaseCognitiveLevel
from src.infrastructure.agents.tajine.knowledge.bank import THEORIES

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider


@dataclass
class Milestone:
    """A milestone in the implementation plan."""

    name: str
    month: int  # Month from start (1-indexed)
    description: str
    deliverables: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "month": self.month,
            "description": self.description,
            "deliverables": self.deliverables,
            "dependencies": self.dependencies
        }


@dataclass
class ImplementationPlan:
    """A complete implementation plan for a strategic recommendation."""

    recommendation_ref: str  # Reference to the recommendation
    title: str
    objective: str
    stakeholders: list[dict[str, str]]  # [{role, responsibility}]
    milestones: list[Milestone]
    resources: dict[str, Any]  # budget, team_size, tools
    success_metrics: list[dict[str, str]]  # [{metric, target, measurement}]
    risks: list[dict[str, str]]  # [{risk, probability, impact, mitigation}]
    total_duration_months: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_ref": self.recommendation_ref,
            "title": self.title,
            "objective": self.objective,
            "stakeholders": self.stakeholders,
            "milestones": [m.to_dict() for m in self.milestones],
            "resources": self.resources,
            "success_metrics": self.success_metrics,
            "risks": self.risks,
            "total_duration_months": self.total_duration_months
        }


# THEORIES dict is now loaded from knowledge/theories.json via knowledge/bank.py
# Contains 71 theories across 13 categories:
# - regional_growth, location, agglomeration, french_territorial, innovation,
# - resilience, industrial_transition, labor_markets, network_economics,
# - urban_economics, institutions, globalization, green_transition


class TheoreticalLevel(BaseCognitiveLevel):
    """
    Level 5: Theoretical Validation & Implementation Planning

    Two-part analysis:
    1. Validates strategy recommendations against economic/geographic theories
    2. Produces detailed implementation plans with:
       - Stakeholder mapping
       - Milestone-based timelines
       - Resource requirements
       - Success metrics (KPIs)
       - Risk management

    Theories applied:
    - Growth Pole Theory (Perroux)
    - Central Place Theory (Christaller)
    - New Economic Geography (Krugman)
    - Industrial District Theory (Marshall)
    """

    def __init__(self, llm_provider: Optional["LLMProvider"] = None):
        """Initialize TheoreticalLevel."""
        super().__init__(llm_provider)

    @property
    def level_number(self) -> int:
        return 5

    @property
    def level_name(self) -> str:
        return "theoretical"

    async def process(
        self,
        results: list[dict[str, Any]],
        previous: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate against theories and generate implementation plans.

        Args:
            results: Raw execution results
            previous: Previous level outputs (strategy recommendations)

        Returns:
            Dict with validation, implementation_plans, theories_applied, confidence
        """
        logger.debug("TheoreticalLevel processing")

        # Try LLM-powered processing first
        llm_result = await self._process_with_llm(results, previous)
        if llm_result and llm_result.get('implementation_plans'):
            logger.info("TheoreticalLevel: Using LLM-powered analysis")
            return llm_result

        # Try full theoretical analysis with implementation planning
        analysis_result = await self._process_with_analysis(previous)
        if analysis_result and analysis_result.get('implementation_plans'):
            logger.info("TheoreticalLevel: Using theoretical analysis")
            return analysis_result

        # Fallback to rule-based processing
        logger.debug("TheoreticalLevel: Using rule-based analysis")
        return self._process_rule_based(previous)

    async def _process_with_analysis(
        self,
        previous: dict[str, Any]
    ) -> dict[str, Any]:
        """Full theoretical validation and implementation planning."""
        discovery = previous.get('discovery', {})
        strategy = previous.get('strategy', {})
        scenario = previous.get('scenario', {})
        causal = previous.get('causal', {})

        signals = discovery.get('signals', [])
        recommendations = strategy.get('recommendations', [])
        actions = strategy.get('actions', [])

        if not recommendations:
            return {}

        try:
            # 1. Identify relevant theories
            theories_applied = self._identify_relevant_theories(signals)

            # 2. Validate recommendations against theories
            validation = self._validate_recommendations(recommendations, theories_applied)

            # 3. Generate implementation plans for top recommendations
            implementation_plans = self._generate_implementation_plans(
                recommendations=recommendations,
                actions=actions,
                validation=validation,
                causes=causal.get('causes', []),
                scenario=scenario
            )

            # 4. Compute overall confidence
            strategy_confidence = strategy.get('confidence', 0.5)
            theory_confidence = self._compute_theory_confidence(validation, theories_applied)
            confidence = (strategy_confidence + theory_confidence) / 2

            return {
                'validation': validation,
                'theories_applied': theories_applied,
                'implementation_plans': [p.to_dict() for p in implementation_plans],
                'summary': self._generate_executive_summary(
                    recommendations, validation, implementation_plans
                ),
                'confidence': round(confidence, 2),
                'method': 'theoretical_analysis'
            }

        except Exception as e:
            logger.warning(f"Theoretical analysis failed: {e}")
            return {}

    def _identify_relevant_theories(
        self,
        signals: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Identify which theories are relevant based on observed signals."""
        theories_applied = []

        for theory_key, theory in THEORIES.items():
            indicators = theory.get('indicators', [])
            matches = 0

            for signal in signals:
                signal_type = signal.get('type', '') if isinstance(signal, dict) else ''
                if signal_type in indicators:
                    matches += 1

            relevance = matches / len(indicators) if indicators else 0

            if relevance >= 0.3:  # At least 30% indicator match
                theories_applied.append({
                    'key': theory_key,
                    'theory': theory['name'],
                    'author': theory['author'],
                    'description': theory['description'],
                    'relevance': round(relevance, 2),
                    'matched_indicators': [
                        s.get('type', '') for s in signals
                        if isinstance(s, dict) and s.get('type', '') in indicators
                    ]
                })

        return sorted(theories_applied, key=lambda t: t['relevance'], reverse=True)

    def _validate_recommendations(
        self,
        recommendations: list[dict[str, Any]],
        theories_applied: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Validate recommendations against applicable theories."""
        validation = {
            'strongly_supported': [],
            'supported': [],
            'neutral': [],
            'inconsistent': []
        }

        for rec in recommendations:
            rec_type = rec.get('type', '')
            rec_desc = rec.get('description', '')

            for theory_info in theories_applied:
                theory_key = theory_info['key']
                theory = THEORIES[theory_key]
                alignment = theory['strategy_alignment'].get(rec_type, 0.5)

                # Adjust alignment by theory relevance
                adjusted_alignment = alignment * theory_info['relevance']

                result = {
                    'recommendation': rec_desc,
                    'recommendation_type': rec_type,
                    'theory': theory_info['theory'],
                    'alignment_score': round(adjusted_alignment, 2),
                    'explanation': self._get_alignment_explanation(
                        rec_type, theory_key, adjusted_alignment
                    )
                }

                if adjusted_alignment >= 0.7:
                    validation['strongly_supported'].append(result)
                elif adjusted_alignment >= 0.5:
                    validation['supported'].append(result)
                elif adjusted_alignment >= 0.3:
                    validation['neutral'].append(result)
                else:
                    validation['inconsistent'].append(result)

        return validation

    def _get_alignment_explanation(
        self,
        rec_type: str,
        theory_key: str,
        alignment: float
    ) -> str:
        """Generate explanation for theory-recommendation alignment."""
        explanations = {
            ('investment', 'growth_pole'): "Investment aligns with growth pole dynamics",
            ('investment', 'new_economic_geography'): "Agglomeration benefits support expansion",
            ('investment', 'industrial_district'): "Cluster effects enhance investment returns",
            ('diversification', 'new_economic_geography'): "Reduces concentration risk in agglomerations",
            ('monitoring', 'central_place'): "Hierarchical dynamics require ongoing observation",
            ('caution', 'growth_pole'): "Weak pole dynamics suggest limited growth potential",
            ('exit', 'growth_pole'): "Absence of pole characteristics indicates declining returns",
        }

        key = (rec_type, theory_key)
        if key in explanations:
            return explanations[key]

        if alignment >= 0.5:
            return f"Strategy type '{rec_type}' is generally aligned with theory"
        else:
            return f"Strategy type '{rec_type}' may not be optimal given theoretical framework"

    def _generate_implementation_plans(
        self,
        recommendations: list[dict[str, Any]],
        actions: list[dict[str, Any]],
        validation: dict[str, list],
        causes: list[dict[str, Any]],
        scenario: dict[str, Any]
    ) -> list[ImplementationPlan]:
        """Generate detailed implementation plans for recommendations."""
        plans = []

        # Process top 3 recommendations
        for i, rec in enumerate(recommendations[:3]):
            rec_type = rec.get('type', 'monitoring')
            rec_desc = rec.get('description', '')
            priority = rec.get('priority', 'medium')

            # Get related actions
            related_actions = [
                a for a in actions
                if isinstance(a, dict)
            ][:4]  # Up to 4 actions per recommendation

            # Generate plan based on recommendation type
            plan = self._create_plan_for_type(
                rec_type=rec_type,
                rec_desc=rec_desc,
                priority=priority,
                actions=related_actions,
                causes=causes,
                scenario=scenario,
                plan_index=i
            )

            if plan:
                plans.append(plan)

        return plans

    def _create_plan_for_type(
        self,
        rec_type: str,
        rec_desc: str,
        priority: str,
        actions: list[dict[str, Any]],
        causes: list[dict[str, Any]],
        scenario: dict[str, Any],
        plan_index: int
    ) -> ImplementationPlan | None:
        """Create implementation plan based on recommendation type."""
        # Duration based on priority
        duration_map = {
            'critical': 6,
            'high': 9,
            'medium': 12,
            'low': 18
        }
        duration = duration_map.get(priority, 12)

        # Base stakeholders
        stakeholders = [
            {"role": "Executive Sponsor", "responsibility": "Strategic oversight and resource allocation"},
            {"role": "Project Manager", "responsibility": "Day-to-day execution and coordination"},
        ]

        # Type-specific configuration
        if rec_type == "investment":
            title = f"Investment Initiative: {rec_desc[:50]}..."
            objective = "Execute strategic investment to capture growth opportunities"
            stakeholders.extend([
                {"role": "Finance Lead", "responsibility": "Financial modeling and due diligence"},
                {"role": "Business Development", "responsibility": "Partner/target identification"},
            ])
            milestones = [
                Milestone("Market Analysis Complete", 1, "Comprehensive market study",
                         ["Market report", "Competitor analysis", "Growth projections"]),
                Milestone("Target Identification", 3, "Identify acquisition/partnership targets",
                         ["Shortlist of targets", "Preliminary valuations"],
                         ["Market Analysis Complete"]),
                Milestone("Due Diligence", 5, "Complete due diligence on selected target",
                         ["DD report", "Risk assessment"],
                         ["Target Identification"]),
                Milestone("Deal Execution", duration, "Close transaction and integrate",
                         ["Signed agreement", "Integration plan"],
                         ["Due Diligence"]),
            ]
            resources = {"budget_range": "High", "team_size": 8, "tools": ["CRM", "Financial modeling"]}
            success_metrics = [
                {"metric": "ROI", "target": ">15% within 3 years", "measurement": "Financial returns"},
                {"metric": "Market Share", "target": "+5% in target segment", "measurement": "Market analysis"},
            ]

        elif rec_type == "diversification":
            title = f"Diversification Strategy: {rec_desc[:50]}..."
            objective = "Reduce concentration risk through strategic diversification"
            stakeholders.append(
                {"role": "Risk Manager", "responsibility": "Portfolio risk assessment"}
            )
            milestones = [
                Milestone("Opportunity Mapping", 2, "Map adjacent sectors",
                         ["Sector analysis", "Entry barriers assessment"]),
                Milestone("Pilot Selection", 4, "Select pilot diversification opportunity",
                         ["Business case", "Risk-reward analysis"],
                         ["Opportunity Mapping"]),
                Milestone("Pilot Execution", 8, "Execute pilot program",
                         ["Pilot results", "Lessons learned"],
                         ["Pilot Selection"]),
                Milestone("Scale Decision", duration, "Decide on scaling based on pilot",
                         ["Scale/no-scale recommendation", "Full rollout plan"],
                         ["Pilot Execution"]),
            ]
            resources = {"budget_range": "Medium", "team_size": 5, "tools": ["Analytics platform"]}
            success_metrics = [
                {"metric": "Portfolio Concentration", "target": "Reduce by 20%", "measurement": "HHI index"},
                {"metric": "Risk-Adjusted Returns", "target": "Improve Sharpe ratio", "measurement": "Financial metrics"},
            ]

        elif rec_type == "monitoring":
            title = f"Monitoring Program: {rec_desc[:50]}..."
            objective = "Establish systematic monitoring for informed decision-making"
            stakeholders.append(
                {"role": "Data Analyst", "responsibility": "Dashboard development and analysis"}
            )
            milestones = [
                Milestone("KPI Framework", 1, "Define key performance indicators",
                         ["KPI documentation", "Data sources identified"]),
                Milestone("Dashboard Live", 3, "Launch monitoring dashboard",
                         ["Working dashboard", "Alert system"],
                         ["KPI Framework"]),
                Milestone("First Review", 6, "Complete first quarterly review",
                         ["Review report", "Recommendations"],
                         ["Dashboard Live"]),
                Milestone("Process Institutionalized", duration, "Fully embedded monitoring process",
                         ["SOP documentation", "Training complete"],
                         ["First Review"]),
            ]
            resources = {"budget_range": "Low", "team_size": 3, "tools": ["BI platform", "Data warehouse"]}
            success_metrics = [
                {"metric": "Decision Latency", "target": "<1 week from signal to action", "measurement": "Process tracking"},
                {"metric": "Forecast Accuracy", "target": ">80%", "measurement": "Prediction vs actual"},
            ]

        elif rec_type == "caution":
            title = f"Risk Management: {rec_desc[:50]}..."
            objective = "Implement defensive measures to protect current position"
            stakeholders.append(
                {"role": "Risk Officer", "responsibility": "Risk framework and monitoring"}
            )
            milestones = [
                Milestone("Risk Assessment", 1, "Comprehensive risk review",
                         ["Risk register", "Exposure mapping"]),
                Milestone("Mitigation Deployed", 3, "Implement risk mitigations",
                         ["Hedging strategies active", "Contingency plans"],
                         ["Risk Assessment"]),
                Milestone("Stress Testing", 6, "Complete stress test scenarios",
                         ["Stress test results", "Action thresholds"],
                         ["Mitigation Deployed"]),
            ]
            resources = {"budget_range": "Low-Medium", "team_size": 4, "tools": ["Risk management system"]}
            success_metrics = [
                {"metric": "Maximum Drawdown", "target": "<15%", "measurement": "Portfolio performance"},
                {"metric": "Risk Coverage", "target": "100% of identified risks", "measurement": "Risk register"},
            ]

        elif rec_type == "exit":
            title = f"Exit Strategy: {rec_desc[:50]}..."
            objective = "Execute orderly exit to minimize losses and capture residual value"
            stakeholders.extend([
                {"role": "Legal Counsel", "responsibility": "Contract review and compliance"},
                {"role": "Communications Lead", "responsibility": "Stakeholder messaging"},
            ])
            milestones = [
                Milestone("Exit Assessment", 1, "Evaluate exit options and timing",
                         ["Options analysis", "Valuation range"]),
                Milestone("Exit Plan Approved", 2, "Board approval of exit strategy",
                         ["Board presentation", "Approved plan"],
                         ["Exit Assessment"]),
                Milestone("Transaction Complete", 6, "Complete exit transaction",
                         ["Signed agreement", "Funds received"],
                         ["Exit Plan Approved"]),
            ]
            resources = {"budget_range": "Medium", "team_size": 6, "tools": ["M&A platform"]}
            success_metrics = [
                {"metric": "Value Recovered", "target": ">80% of book value", "measurement": "Transaction value"},
                {"metric": "Timeline", "target": "Complete within 6 months", "measurement": "Project tracking"},
            ]

        else:
            return None

        # Add risks based on causal factors
        risks = self._generate_plan_risks(rec_type, causes, scenario)

        return ImplementationPlan(
            recommendation_ref=f"REC-{plan_index + 1}",
            title=title,
            objective=objective,
            stakeholders=stakeholders,
            milestones=milestones,
            resources=resources,
            success_metrics=success_metrics,
            risks=risks,
            total_duration_months=duration
        )

    def _generate_plan_risks(
        self,
        rec_type: str,
        causes: list[dict[str, Any]],
        scenario: dict[str, Any]
    ) -> list[dict[str, str]]:
        """Generate implementation risks based on causal factors."""
        risks = []

        # Scenario-based risks
        pessimistic = scenario.get('pessimistic', {})
        if pessimistic.get('growth_rate', 0) < 0:
            risks.append({
                "risk": "Market downturn",
                "probability": "Medium",
                "impact": "High",
                "mitigation": "Build in exit clauses and stage-gate reviews"
            })

        # Factor-based risks
        for cause in causes[:3]:
            if cause.get('confidence', 1) < 0.6:
                factor = cause.get('factor', 'Unknown')
                risks.append({
                    "risk": f"Uncertainty in {factor}",
                    "probability": "Medium",
                    "impact": "Medium",
                    "mitigation": f"Monitor {factor} closely, define trigger thresholds"
                })

        # Type-specific risks
        if rec_type == "investment":
            risks.append({
                "risk": "Integration challenges",
                "probability": "Medium",
                "impact": "High",
                "mitigation": "Dedicated integration team, detailed playbook"
            })
        elif rec_type == "exit":
            risks.append({
                "risk": "Value erosion during exit",
                "probability": "Medium",
                "impact": "High",
                "mitigation": "Maintain operational performance, confidential process"
            })

        return risks[:5]

    def _compute_theory_confidence(
        self,
        validation: dict[str, list],
        theories_applied: list[dict[str, Any]]
    ) -> float:
        """Compute confidence based on theoretical validation."""
        if not theories_applied:
            return 0.4

        # Count validation results
        strongly_supported = len(validation.get('strongly_supported', []))
        supported = len(validation.get('supported', []))
        inconsistent = len(validation.get('inconsistent', []))
        total = strongly_supported + supported + inconsistent + len(validation.get('neutral', []))

        if total == 0:
            return 0.5

        # Weighted score
        score = (strongly_supported * 1.0 + supported * 0.7 - inconsistent * 0.3) / total
        return max(0.3, min(0.9, score))

    def _generate_executive_summary(
        self,
        recommendations: list[dict[str, Any]],
        validation: dict[str, list],
        plans: list[ImplementationPlan]
    ) -> dict[str, Any]:
        """Generate executive summary of the analysis."""
        # Determine overall recommendation
        rec_types = [r.get('type', '') for r in recommendations]
        primary_strategy = rec_types[0] if rec_types else "monitoring"

        strategy_labels = {
            'investment': "Growth-Oriented",
            'diversification': "Risk-Balancing",
            'monitoring': "Watchful Waiting",
            'caution': "Defensive",
            'exit': "Strategic Exit"
        }

        return {
            'primary_strategy': strategy_labels.get(primary_strategy, "Adaptive"),
            'total_recommendations': len(recommendations),
            'strongly_supported_by_theory': len(validation.get('strongly_supported', [])),
            'implementation_plans_generated': len(plans),
            'total_duration_months': max((p.total_duration_months for p in plans), default=0),
            'key_stakeholders': list({
                s['role'] for p in plans for s in p.stakeholders
            })[:5]
        }

    def _process_rule_based(self, previous: dict[str, Any]) -> dict[str, Any]:
        """Fallback rule-based processing."""
        discovery = previous.get('discovery', {})
        strategy = previous.get('strategy', {})

        signals = discovery.get('signals', [])
        recommendations = strategy.get('recommendations', [])

        theories_applied = []
        validation = {
            'strongly_supported': [],
            'supported': [],
            'neutral': [],
            'inconsistent': []
        }

        # Simple theory matching
        for _theory_key, theory in THEORIES.items():
            relevance = self._check_theory_relevance_simple(signals, theory)
            if relevance > 0.3:
                theories_applied.append({
                    'theory': theory['name'],
                    'author': theory['author'],
                    'relevance': round(relevance, 2)
                })

                for rec in recommendations:
                    rec_type = rec.get('type', '')
                    alignment = theory['strategy_alignment'].get(rec_type, 0.5)

                    if alignment > 0.6:
                        validation['supported'].append({
                            'recommendation': rec.get('description', ''),
                            'theory': theory['name'],
                            'alignment_score': alignment
                        })

        confidence = 0.5 if theories_applied else 0.4

        return {
            'validation': validation,
            'theories_applied': theories_applied,
            'implementation_plans': [],
            'confidence': confidence,
            'method': 'rule_based'
        }

    def _check_theory_relevance_simple(
        self,
        signals: list[dict[str, Any]],
        theory: dict[str, Any]
    ) -> float:
        """Simple theory relevance check."""
        indicators = theory.get('indicators', [])
        matches = sum(
            1 for s in signals
            if isinstance(s, dict) and s.get('type', '') in indicators
        )
        return matches / len(indicators) if indicators else 0
