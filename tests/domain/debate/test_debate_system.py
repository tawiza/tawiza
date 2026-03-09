"""Tests for Multi-Agent Debate System.

Tests cover:
- Standard mode (3 agents)
- Extended mode (6 agents)
- Individual agent behavior
- Edge cases and error handling
"""

import pytest

from src.domain.debate import (
    AgentMessage,
    AgentRole,
    ChercheurAgent,
    CritiqueAgent,
    DebateMode,
    DebateResult,
    DebateSystem,
    FactCheckerAgent,
    SourceRankerAgent,
    SynthesisAgent,
    VerificateurAgent,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def good_data():
    """High-quality data with SIRET and official sources."""
    return {
        "results": [
            {
                "source": "sirene",
                "siret": "12345678901234",
                "name": "Test Corp",
                "date": "2024-01-01",
            },
            {
                "source": "bodacc",
                "siret": "12345678901234",
                "name": "Test Corp",
                "date": "2024-01-01",
            },
            {
                "source": "boamp",
                "siret": "12345678901234",
                "name": "Test Corp",
                "date": "2024-01-01",
            },
        ],
        "sources": ["sirene", "bodacc", "boamp"],
    }


@pytest.fixture
def poor_data():
    """Low-quality data without SIRET or dates."""
    return {
        "results": [
            {"source": "unknown", "name": "Bad Data"},
            {"source": "rss", "name": "Some News"},
        ],
        "sources": ["unknown", "rss"],
    }


@pytest.fixture
def empty_data():
    """Empty data."""
    return {"results": [], "sources": []}


@pytest.fixture
def mixed_data():
    """Mixed quality data."""
    return {
        "results": [
            {
                "source": "sirene",
                "siret": "12345678901234",
                "name": "Test Corp",
                "date": "2024-01-01",
            },
            {"source": "google_news", "name": "Test Corp News", "published_dt": "2024-01-01"},
            {"source": "rss", "name": "Random News"},
        ],
        "sources": ["sirene", "google_news", "rss"],
    }


# =============================================================================
# DebateSystem Tests - Standard Mode
# =============================================================================


@pytest.mark.asyncio
async def test_debate_with_good_data(good_data):
    """Test debate with high-quality data."""
    debate = DebateSystem()
    result = await debate.validate("Test Corp", good_data)

    assert result.final_confidence >= 40
    assert len(result.messages) == 3  # Standard mode: 3 agents
    assert result.is_valid


@pytest.mark.asyncio
async def test_debate_with_no_data(empty_data):
    """Test debate with empty data."""
    debate = DebateSystem()
    result = await debate.validate("empty query", empty_data)

    assert result.final_confidence == 0
    assert not result.is_valid


@pytest.mark.asyncio
async def test_debate_with_poor_data(poor_data):
    """Test debate with low-quality data."""
    debate = DebateSystem()
    result = await debate.validate("poor query", poor_data)

    # Should have lower confidence due to missing SIRET and unofficial sources
    assert result.final_confidence < 60
    assert len(result.issues) > 0  # Should identify issues


@pytest.mark.asyncio
async def test_debate_result_serialization(mixed_data):
    """Test DebateResult.to_dict()."""
    debate = DebateSystem()
    result = await debate.validate("test", mixed_data)
    data_dict = result.to_dict()

    assert "query" in data_dict
    assert "final_confidence" in data_dict
    assert "verdict" in data_dict
    assert "debate_rounds" in data_dict
    assert len(data_dict["debate_rounds"]) == 3


# =============================================================================
# DebateSystem Tests - Extended Mode
# =============================================================================


@pytest.mark.asyncio
async def test_extended_mode_agent_count(good_data):
    """Test extended mode uses 6 agents."""
    debate = DebateSystem(mode=DebateMode.EXTENDED)
    result = await debate.validate("Test Corp", good_data)

    assert len(result.messages) == 6  # Extended mode: 6 agents


@pytest.mark.asyncio
async def test_extended_mode_agent_order(mixed_data):
    """Test agents run in correct order in extended mode."""
    debate = DebateSystem(mode=DebateMode.EXTENDED)
    result = await debate.validate("test", mixed_data)

    agent_names = [msg.agent for msg in result.messages]

    # Expected order
    assert agent_names[0] == "Chercheur"
    assert agent_names[1] == "Source-Ranker"
    assert agent_names[2] == "Critique"
    assert agent_names[3] == "Fact-Checker"
    assert agent_names[4] == "Vérificateur"
    assert agent_names[5] == "Synthèse"


@pytest.mark.asyncio
async def test_mode_override_in_validate(good_data):
    """Test mode can be overridden in validate call."""
    debate = DebateSystem(mode=DebateMode.STANDARD)

    # Override to extended
    result = await debate.validate("test", good_data, mode=DebateMode.EXTENDED)
    assert len(result.messages) == 6


# =============================================================================
# Individual Agent Tests
# =============================================================================


@pytest.mark.asyncio
async def test_chercheur_agent_analysis():
    """Test ChercheurAgent correctly analyzes data."""
    agent = ChercheurAgent()

    data = {
        "results": [
            {"source": "sirene", "siret": "12345"},
            {"source": "bodacc", "siret": "12345"},
            {"source": "gdelt", "name": "news"},
        ],
        "sources": ["sirene", "bodacc", "gdelt"],
    }

    result = await agent.process(data, [])

    assert result.agent == "Chercheur"
    assert result.role == "researcher"
    assert result.confidence > 0
    assert len(result.evidence) > 0


@pytest.mark.asyncio
async def test_critique_agent_identifies_issues():
    """Test CritiqueAgent identifies data quality issues."""
    agent = CritiqueAgent()

    # Data without SIRET
    data = {
        "results": [
            {"source": "rss", "name": "news1"},
            {"source": "rss", "name": "news2"},
        ],
        "sources": ["rss"],
    }

    result = await agent.process(data, [])

    assert result.agent == "Critique"
    assert result.role == "critic"
    assert len(result.issues) > 0  # Should identify missing SIRET


@pytest.mark.asyncio
async def test_verificateur_agent_verdict():
    """Test VerificateurAgent provides correct verdict."""
    agent = VerificateurAgent()

    # Good data
    data = {
        "results": [
            {"source": "sirene", "siret": "12345678901234"},
            {"source": "bodacc", "siret": "12345678901234"},
        ],
        "sources": ["sirene", "bodacc"],
    }

    # Simulate previous agent context
    context = [
        AgentMessage(agent="Chercheur", role="researcher", content="Good data", confidence=80),
        AgentMessage(agent="Critique", role="critic", content="No issues", confidence=80),
    ]

    result = await agent.process(data, context)

    assert result.agent == "Vérificateur"
    assert result.role == "verifier"
    assert "CONFIANCE" in result.content.upper()


@pytest.mark.asyncio
async def test_fact_checker_agent_verification():
    """Test FactCheckerAgent verifies entities."""
    agent = FactCheckerAgent()

    data = {
        "results": [
            {"source": "sirene", "siret": "12345678901234", "name": "Verified Corp"},
            {"source": "rss", "name": "Unverified News"},
        ],
        "sources": ["sirene", "rss"],
    }

    result = await agent.process(data, [])

    assert result.agent == "Fact-Checker"
    assert result.role == "fact_checker"
    assert "verified_facts" in result.metadata
    assert "unverified_claims" in result.metadata


@pytest.mark.asyncio
async def test_source_ranker_agent_ranking():
    """Test SourceRankerAgent ranks sources correctly."""
    agent = SourceRankerAgent()

    data = {
        "results": [
            {"source": "sirene", "siret": "12345", "date": "2024-01-01"},
            {"source": "rss", "name": "news"},
            {"source": "bodacc", "siret": "12345"},
        ],
        "sources": ["sirene", "rss", "bodacc"],
    }

    result = await agent.process(data, [])

    assert result.agent == "Source-Ranker"
    assert result.role == "source_ranker"
    assert "ranked_sources" in result.metadata

    # Official sources should rank higher
    ranked = result.metadata["ranked_sources"]
    official_scores = [s for s in ranked if s["source"] in ["sirene", "bodacc"]]
    rss_scores = [s for s in ranked if s["source"] == "rss"]

    assert all(o["score"] > rss_scores[0]["score"] for o in official_scores)


@pytest.mark.asyncio
async def test_synthesis_agent_summary():
    """Test SynthesisAgent creates comprehensive summary."""
    agent = SynthesisAgent()

    data = {"results": [{"source": "test", "name": "test"}], "sources": ["test"]}

    context = [
        AgentMessage(
            agent="Chercheur",
            role="researcher",
            content="Found data",
            confidence=60,
            evidence=[{"source": "test", "count": 1}],
        ),
        AgentMessage(
            agent="Critique",
            role="critic",
            content="Some issues",
            confidence=50,
            issues=["Missing SIRET"],
        ),
    ]

    result = await agent.process(data, context)

    assert result.agent == "Synthèse"
    assert result.role == "synthesizer"
    assert "Synthèse" in result.content
    assert "agents_consulted" in result.metadata


# =============================================================================
# Edge Cases
# =============================================================================


@pytest.mark.asyncio
async def test_single_result():
    """Test with single result."""
    debate = DebateSystem()

    data = {
        "results": [{"source": "sirene", "siret": "12345678901234", "name": "Solo Corp"}],
        "sources": ["sirene"],
    }

    result = await debate.validate("solo", data)

    assert len(result.messages) == 3
    # Single source should have lower confidence
    assert result.final_confidence < 80


@pytest.mark.asyncio
async def test_duplicate_entities():
    """Test with duplicate SIRET across sources."""
    debate = DebateSystem(mode=DebateMode.EXTENDED)

    data = {
        "results": [
            {"source": "sirene", "siret": "12345678901234", "name": "ACME"},
            {"source": "bodacc", "siret": "12345678901234", "name": "ACME Corp"},
            {"source": "boamp", "siret": "12345678901234", "name": "ACME Corporation"},
        ],
        "sources": ["sirene", "bodacc", "boamp"],
    }

    result = await debate.validate("ACME", data)

    # Should recognize as same entity and boost confidence
    assert result.final_confidence >= 60


@pytest.mark.asyncio
async def test_is_high_confidence_property():
    """Test is_high_confidence property."""
    debate = DebateSystem()

    # Good data should yield high confidence
    good_data = {
        "results": [
            {"source": "sirene", "siret": "12345678901234", "name": "Test", "date": "2024-01-01"},
            {"source": "bodacc", "siret": "12345678901234", "name": "Test", "date": "2024-01-01"},
            {"source": "boamp", "siret": "12345678901234", "name": "Test", "date": "2024-01-01"},
        ],
        "sources": ["sirene", "bodacc", "boamp"],
    }

    result = await debate.validate("test", good_data)

    # High confidence threshold is 80
    if result.final_confidence >= 80:
        assert result.is_high_confidence
    else:
        assert not result.is_high_confidence


@pytest.mark.asyncio
async def test_quick_validate():
    """Test quick_validate convenience method."""
    debate = DebateSystem()

    data = {"results": [{"source": "test"}], "sources": ["test"]}

    confidence, verdict = await debate.quick_validate(data)

    assert isinstance(confidence, float)
    assert isinstance(verdict, str)


# =============================================================================
# AgentMessage Tests
# =============================================================================


def test_agent_message_to_dict():
    """Test AgentMessage.to_dict() serialization."""
    msg = AgentMessage(
        agent="Test",
        role="test",
        content="Test content",
        confidence=75.5,
        evidence=[{"key": "value"}],
        issues=["issue1"],
        metadata={"extra": "data"},
    )

    d = msg.to_dict()

    assert d["agent"] == "Test"
    assert d["role"] == "test"
    assert d["content"] == "Test content"
    assert d["confidence"] == 75.5
    assert d["evidence"] == [{"key": "value"}]
    assert d["issues"] == ["issue1"]
    assert d["metadata"] == {"extra": "data"}


def test_agent_role_enum():
    """Test AgentRole enum values."""
    assert AgentRole.RESEARCHER.value == "researcher"
    assert AgentRole.CRITIC.value == "critic"
    assert AgentRole.VERIFIER.value == "verifier"
    assert AgentRole.FACT_CHECKER.value == "fact_checker"
    assert AgentRole.SOURCE_RANKER.value == "source_ranker"
    assert AgentRole.SYNTHESIZER.value == "synthesizer"


def test_debate_mode_enum():
    """Test DebateMode enum values."""
    assert DebateMode.STANDARD.value == "standard"
    assert DebateMode.EXTENDED.value == "extended"
