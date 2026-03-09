"""
DiscoveryLevel - Level 1 of CognitiveEngine

Detects weak signals and emerging patterns in data.
Inspired by Renaissance Technologies signal detection.

Integrates with ReflectionOutput for ReAct-style quality feedback.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from loguru import logger

from src.infrastructure.agents.tajine.cognitive.reflection import (
    ReflectionMixin,
    ReflectionOutput,
)

if TYPE_CHECKING:
    from src.infrastructure.agents.tajine.cognitive.llm_provider import LLMProvider


@dataclass
class Signal:
    """A detected weak signal."""
    type: str
    description: str
    strength: float  # 0-1
    source: str


@dataclass
class Pattern:
    """A detected pattern."""
    name: str
    description: str
    confidence: float


class BaseCognitiveLevel(ABC):
    """Base class for cognitive levels with optional LLM support."""

    def __init__(self, llm_provider: Optional['LLMProvider'] = None):
        """
        Initialize cognitive level.

        Args:
            llm_provider: Optional LLM provider for AI-powered processing
        """
        self._llm_provider = llm_provider

    @property
    @abstractmethod
    def level_number(self) -> int:
        """Return level number (1-5)."""
        pass

    @property
    @abstractmethod
    def level_name(self) -> str:
        """Return level name."""
        pass

    @abstractmethod
    async def process(
        self,
        results: list[dict[str, Any]],
        previous: dict[str, Any]
    ) -> dict[str, Any]:
        """Process results and return level output."""
        pass

    async def _process_with_llm(
        self,
        results: list[dict[str, Any]],
        previous: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Process using LLM if available.

        Returns None if LLM is unavailable or fails.
        """
        if self._llm_provider is None:
            return None

        try:
            return await self._llm_provider.process_level(
                self.level_name,
                results,
                previous
            )
        except Exception as e:
            logger.warning(f"LLM processing failed for {self.level_name}: {e}")
            return None


class DiscoveryLevel(BaseCognitiveLevel, ReflectionMixin):
    """
    Level 1: Discovery

    Detects weak signals and emerging patterns:
    - Growth/decline trends
    - Anomalies in data
    - Emerging sectors
    - Geographic concentrations

    Uses LLM when available for enhanced signal detection.
    Falls back to rule-based detection when LLM unavailable.

    Integrates ReflectionMixin for ReAct-style quality feedback.
    """

    @property
    def level_number(self) -> int:
        return 1

    @property
    def level_name(self) -> str:
        return "discovery"

    async def process(
        self,
        results: list[dict[str, Any]],
        previous: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Detect signals and patterns from raw results.

        Args:
            results: Raw execution results
            previous: Previous level outputs (empty for L1)

        Returns:
            Dict with signals, patterns, confidence, and reflection
        """
        logger.debug("DiscoveryLevel processing")

        # Try LLM-powered processing first
        llm_result = await self._process_with_llm(results, previous)
        if llm_result and llm_result.get('signals'):
            logger.info("DiscoveryLevel: Using LLM-powered analysis")
            # Add reflection for LLM result
            reflection = self._create_llm_reflection(llm_result)
            llm_result['reflection'] = reflection.to_dict()
            return llm_result

        # Fallback to rule-based processing
        logger.debug("DiscoveryLevel: Using rule-based analysis")

        signals = []
        patterns = []

        for r in results:
            result_data = r.get('result', {})
            if isinstance(result_data, dict):
                # Detect growth signals
                signals.extend(self._detect_growth_signals(result_data))
                # Detect anomalies
                signals.extend(self._detect_anomalies(result_data))
                # Detect patterns
                patterns.extend(self._detect_patterns(result_data))

        confidence = self._compute_confidence(signals, patterns)

        # Create reflection for quality tracking
        reflection = self._create_rule_based_reflection(signals, patterns, confidence)

        return {
            'signals': [s.__dict__ if hasattr(s, '__dict__') else s for s in signals],
            'patterns': [p.__dict__ if hasattr(p, '__dict__') else p for p in patterns],
            'confidence': confidence,
            'reflection': reflection.to_dict()
        }

    def _create_llm_reflection(self, llm_result: dict[str, Any]) -> ReflectionOutput:
        """Create reflection for LLM-powered analysis."""
        signals = llm_result.get('signals', [])
        patterns = llm_result.get('patterns', [])
        confidence = llm_result.get('confidence', 0.6)

        thinking = f"LLM analysis: {len(signals)} signals, {len(patterns)} patterns"

        gaps = []
        if len(signals) == 0:
            gaps.append("No signals from LLM")
        if len(patterns) == 0:
            gaps.append("No patterns from LLM")

        return ReflectionOutput(
            result=llm_result,
            thinking=thinking,
            confidence=confidence,
            gaps=gaps,
            suggestions=["Consider rule-based fallback if LLM fails"] if gaps else [],
        )

    def _create_rule_based_reflection(
        self,
        signals: list[Signal],
        patterns: list[Pattern],
        confidence: float
    ) -> ReflectionOutput:
        """Create reflection for rule-based analysis."""
        gaps = []
        suggestions = []

        # Assess signal quality
        if len(signals) == 0:
            gaps.append("No signals detected")
            suggestions.append("Expand data sources (SIRENE, BODACC)")
        elif len(signals) < 3:
            suggestions.append("Consider semantic search for more signals")

        # Assess pattern quality
        if len(patterns) == 0:
            gaps.append("No patterns identified")
            suggestions.append("Analyze sector distribution")
        elif len(patterns) < 2:
            suggestions.append("Look for geographic clustering")

        # Build thinking trace
        signal_types = {s.type for s in signals}
        pattern_names = {p.name for p in patterns}

        thinking_parts = []
        if signals:
            thinking_parts.append(f"Detected {len(signals)} signals ({', '.join(signal_types)})")
        if patterns:
            thinking_parts.append(f"Identified {len(patterns)} patterns ({', '.join(pattern_names)})")
        if gaps:
            thinking_parts.append(f"Gaps: {', '.join(gaps)}")

        thinking = ". ".join(thinking_parts) if thinking_parts else "Rule-based analysis completed"

        return ReflectionOutput(
            result={'signals': len(signals), 'patterns': len(patterns)},
            thinking=thinking,
            confidence=confidence,
            gaps=gaps,
            suggestions=suggestions,
        )

    def _detect_growth_signals(self, data: dict[str, Any]) -> list[Signal]:
        """Detect growth/decline signals from various data formats."""
        signals = []

        # 1. Handle DataHunter format with 'data' array from SIRENE/BODACC
        if hunt_data := data.get('data'):
            signals.extend(self._analyze_hunt_data(hunt_data))

        # 2. Handle direct company counts (legacy format)
        current = data.get('companies', data.get('count', data.get('data_count', 0)))
        previous = data.get('companies_last_year', data.get('count_last_year'))

        if previous and current and previous > 0:
            growth_rate = (current - previous) / previous
            if abs(growth_rate) > 0.1:  # >10% change
                signal_type = 'growth' if growth_rate > 0 else 'decline'
                signals.append(Signal(
                    type=signal_type,
                    description=f"{signal_type.capitalize()} detected: {growth_rate:.1%}",
                    strength=min(abs(growth_rate), 1.0),
                    source='year_over_year'
                ))

        # 3. Check for explicit growth indicator
        if growth := data.get('growth'):
            if isinstance(growth, (int, float)) and growth > 0.05:
                signals.append(Signal(
                    type='growth',
                    description=f"Growth indicator: {growth:.1%}",
                    strength=min(growth, 1.0),
                    source='growth_indicator'
                ))

        # 4. Detect signals from sources_used (DataHunter metadata)
        if sources := data.get('sources_used'):
            if len(sources) >= 3:
                signals.append(Signal(
                    type='data_richness',
                    description=f"Multi-source coverage: {', '.join(sources)}",
                    strength=min(len(sources) / 5, 1.0),
                    source='data_hunter'
                ))

        return signals

    def _analyze_hunt_data(self, hunt_data: list[dict]) -> list[Signal]:
        """Analyze DataHunter results to extract signals from SIRENE/BODACC data."""
        signals = []
        if not hunt_data:
            return signals

        # Group data by source for analysis
        by_source: dict[str, list] = {}
        for item in hunt_data:
            source = item.get('source', 'unknown')
            by_source.setdefault(source, []).append(item)

        # Analyze SIRENE data
        if sirene_data := by_source.get('sirene'):
            signals.extend(self._analyze_sirene_signals(sirene_data))

        # Analyze BODACC data (legal announcements)
        if bodacc_data := by_source.get('bodacc'):
            signals.extend(self._analyze_bodacc_signals(bodacc_data))

        # Analyze other sources
        for source, items in by_source.items():
            if source not in ('sirene', 'bodacc'):
                if len(items) > 5:
                    signals.append(Signal(
                        type='data_volume',
                        description=f"High data volume from {source}: {len(items)} items",
                        strength=min(len(items) / 20, 1.0),
                        source=source
                    ))

        return signals

    def _analyze_sirene_signals(self, sirene_data: list[dict]) -> list[Signal]:
        """Extract signals from SIRENE enterprise data."""
        from datetime import datetime
        signals = []

        # Analyze company creations by year
        creations_by_year: dict[int, int] = {}
        sectors: dict[str, int] = {}
        recent_creations = 0
        current_year = datetime.now().year

        for item in sirene_data:
            # Handle both flat format (from DataHunter) and nested 'content' format
            content = item.get('content', item) if isinstance(item, dict) else {}
            if not isinstance(content, dict):
                continue

            # Extract date_creation (format: YYYY-MM-DD or YYYY)
            date_creation = content.get('date_creation', content.get('dateCreation', ''))
            if date_creation:
                try:
                    year = int(str(date_creation)[:4])
                    creations_by_year[year] = creations_by_year.get(year, 0) + 1
                    if year >= current_year - 1:
                        recent_creations += 1
                except (ValueError, TypeError):
                    pass

            # Extract sector (NAF code)
            naf = content.get('activite_principale', content.get('activitePrincipale', ''))
            if naf:
                sector_code = str(naf)[:2]  # First 2 chars = sector
                sectors[sector_code] = sectors.get(sector_code, 0) + 1

        # Signal: Recent creations surge
        if recent_creations >= 3:
            signals.append(Signal(
                type='creation_surge',
                description=f"{recent_creations} entreprises créées récemment",
                strength=min(recent_creations / 10, 1.0),
                source='sirene_creations'
            ))

        # Signal: Year-over-year growth
        sorted_years = sorted(creations_by_year.keys())
        if len(sorted_years) >= 2:
            last_year = sorted_years[-1]
            prev_year = sorted_years[-2]
            if creations_by_year[prev_year] > 0:
                yoy_growth = (
                    creations_by_year[last_year] - creations_by_year[prev_year]
                ) / creations_by_year[prev_year]
                if yoy_growth > 0.1:
                    signals.append(Signal(
                        type='growth',
                        description=f"Croissance créations: +{yoy_growth:.0%} ({prev_year}→{last_year})",
                        strength=min(yoy_growth, 1.0),
                        source='sirene_yoy'
                    ))

        # Signal: Sector concentration
        if sectors:
            top_sector = max(sectors.items(), key=lambda x: x[1])
            if top_sector[1] >= 3:
                signals.append(Signal(
                    type='sector_concentration',
                    description=f"Concentration secteur NAF {top_sector[0]}: {top_sector[1]} entreprises",
                    strength=min(top_sector[1] / 10, 1.0),
                    source='sirene_sectors'
                ))

        return signals

    def _analyze_bodacc_signals(self, bodacc_data: list[dict]) -> list[Signal]:
        """Extract signals from BODACC legal announcements."""
        signals = []

        # Count by type (creation, dissolution, modification)
        by_type: dict[str, int] = {}
        for item in bodacc_data:
            # Handle both flat format (from DataHunter) and nested 'content' format
            content = item.get('content', item) if isinstance(item, dict) else {}
            pub_type = content.get('type_annonce', content.get('familleavis', 'unknown'))
            by_type[pub_type] = by_type.get(pub_type, 0) + 1

        # Signal: High dissolution count (economic stress)
        dissolutions = by_type.get('dissolution', 0) + by_type.get('Procédures collectives', 0)
        if dissolutions >= 3:
            signals.append(Signal(
                type='economic_stress',
                description=f"{dissolutions} procédures/dissolutions détectées",
                strength=min(dissolutions / 10, 0.9),
                source='bodacc_dissolutions'
            ))

        # Signal: High creation count (dynamism)
        creations = by_type.get('creation', 0) + by_type.get('Immatriculations', 0)
        if creations >= 5:
            signals.append(Signal(
                type='economic_dynamism',
                description=f"{creations} immatriculations BODACC",
                strength=min(creations / 15, 1.0),
                source='bodacc_creations'
            ))

        return signals

    def _detect_anomalies(self, data: dict[str, Any]) -> list[Signal]:
        """Detect statistical anomalies from various data formats."""
        signals = []

        # Check data_count from DataHunter
        data_count = data.get('data_count', 0)
        companies = data.get('companies', data_count)

        if companies and companies > 500:
            signals.append(Signal(
                type='concentration',
                description=f"High company concentration: {companies}",
                strength=min(companies / 1000, 1.0),
                source='company_count'
            ))

        # Check for high data_count (indicates active market)
        if data_count >= 10:
            signals.append(Signal(
                type='market_activity',
                description=f"Active market: {data_count} data points collected",
                strength=min(data_count / 30, 1.0),
                source='data_count'
            ))

        # Check for anomalies in SIRENE data
        if hunt_data := data.get('data'):
            signals.extend(self._detect_sirene_anomalies(hunt_data))

        return signals

    def _detect_sirene_anomalies(self, hunt_data: list[dict]) -> list[Signal]:
        """Detect anomalies in SIRENE/enterprise data."""
        signals = []

        # Analyze effectifs (workforce size)
        effectifs = []
        for item in hunt_data:
            content = item.get('content', {})
            if eff := content.get('tranche_effectif', content.get('trancheEffectifs')):
                effectifs.append(eff)

        if effectifs:
            # Count large companies (effectif >= 50)
            large_companies = sum(1 for e in effectifs if str(e).isdigit() and int(e) >= 21)
            if large_companies >= 2:
                signals.append(Signal(
                    type='large_employer_cluster',
                    description=f"{large_companies} grandes entreprises (50+ salariés)",
                    strength=min(large_companies / 5, 1.0),
                    source='sirene_effectifs'
                ))

        return signals

    def _detect_patterns(self, data: dict[str, Any]) -> list[Pattern]:
        """Detect recurring patterns from various data formats."""
        patterns = []

        # Check for university proximity pattern (legacy)
        if data.get('proximity_university'):
            patterns.append(Pattern(
                name='university_cluster',
                description='Cluster near university detected',
                confidence=0.7
            ))

        # Check for infrastructure patterns (legacy)
        if data.get('has_fiber') or data.get('has_tgv'):
            patterns.append(Pattern(
                name='infrastructure_hub',
                description='Good infrastructure connectivity',
                confidence=0.6
            ))

        # Detect patterns from DataHunter results
        if hunt_data := data.get('data'):
            patterns.extend(self._detect_hunt_patterns(hunt_data))

        # Detect multi-source pattern (data richness)
        sources = data.get('sources_used', [])
        if len(sources) >= 2:
            patterns.append(Pattern(
                name='multi_source_validation',
                description=f"Data from {len(sources)} sources: {', '.join(sources)}",
                confidence=min(0.5 + len(sources) * 0.1, 0.9)
            ))

        return patterns

    def _detect_hunt_patterns(self, hunt_data: list[dict]) -> list[Pattern]:
        """Detect patterns from DataHunter results."""
        patterns = []

        # Analyze NAF sector distribution
        sectors: dict[str, int] = {}
        cities: dict[str, int] = {}

        for item in hunt_data:
            content = item.get('content', {})
            if not isinstance(content, dict):
                continue

            # NAF sector
            naf = content.get('activite_principale', content.get('activitePrincipale', ''))
            if naf:
                sector = str(naf)[:2]
                sectors[sector] = sectors.get(sector, 0) + 1

            # City/commune
            city = content.get('commune', content.get('libelleCommuneEtablissement', ''))
            if city:
                cities[city] = cities.get(city, 0) + 1

        # Pattern: Sector specialization
        if sectors and len(sectors) <= 3 and sum(sectors.values()) >= 5:
            top_sector = max(sectors.items(), key=lambda x: x[1])
            patterns.append(Pattern(
                name='sector_specialization',
                description=f"Spécialisation sectorielle NAF {top_sector[0]}",
                confidence=min(top_sector[1] / sum(sectors.values()), 0.9)
            ))

        # Pattern: Geographic clustering
        if cities:
            top_city = max(cities.items(), key=lambda x: x[1])
            if top_city[1] >= 3:
                patterns.append(Pattern(
                    name='geographic_cluster',
                    description=f"Concentration géographique: {top_city[0]} ({top_city[1]} entreprises)",
                    confidence=min(top_city[1] / 10, 0.85)
                ))

        return patterns

    def _compute_confidence(
        self,
        signals: list[Signal],
        patterns: list[Pattern]
    ) -> float:
        """Compute confidence based on signals and patterns found."""
        if not signals and not patterns:
            return 0.3  # Low confidence with no findings

        # Average signal strength
        signal_conf = sum(s.strength for s in signals) / len(signals) if signals else 0
        # Average pattern confidence
        pattern_conf = sum(p.confidence for p in patterns) / len(patterns) if patterns else 0

        # Weighted combination
        return 0.6 * signal_conf + 0.4 * pattern_conf if (signals or patterns) else 0.3
