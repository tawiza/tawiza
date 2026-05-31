"""Unit tests for the multi-agent debate validation system (issue #161, batch 4).

Target module: src/domain/debate/agents.py

The production code is the source of truth. These tests assert its *real*
behaviour, including its quirks:

- ``BaseAgent`` is abstract (``process`` is an ``@abstractmethod``) and is
  therefore never instantiated directly; only the concrete agents are tested.
- Every concrete agent exposes class-level ``name``/``role`` attributes and an
  async ``process(data, context)`` coroutine returning an :class:`AgentMessage`.
- All agents accept an optional ``llm`` provider. When provided, the LLM
  branch *appends* to (never replaces) the rule-based ``content``; an LLM that
  raises is swallowed (``_generate_with_llm`` returns ``None``) and the agent
  still produces a deterministic rule-based result.
- Confidence scores are clamped to ``[0, 100]`` and computed from the previous
  agents' messages (``context``) and the data quality heuristics.

Data is shaped as the pipeline expects: ``data["results"]`` is a list of dicts,
each with at least a ``"source"`` key, optionally ``"siret"``, ``"name"`` and a
date field (``published_dt`` / ``date`` / ``created_at``).
"""

from typing import Any

import pytest

from src.domain.debate.agents import (
    AgentMessage,
    AgentRole,
    BaseAgent,
    ChercheurAgent,
    CritiqueAgent,
    FactCheckerAgent,
    LLMProvider,
    SourceRankerAgent,
    SynthesisAgent,
    VerificateurAgent,
)


# ---------------------------------------------------------------------------
# Test doubles / helpers
# ---------------------------------------------------------------------------
class FakeLLM:
    """Minimal in-memory LLM provider that records its calls."""

    def __init__(self, response: str = "RÉPONSE LLM SIMULÉE"):
        self.response = response
        self.calls: list[tuple[str, str | None]] = []

    async def generate(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self.response


class FailingLLM:
    """LLM provider whose ``generate`` always raises."""

    async def generate(self, prompt: str, system: str | None = None) -> str:
        raise RuntimeError("boom")


def make_results(*specs: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a list of result dicts, defaulting the source to 'unknown'."""
    out = []
    for spec in specs:
        item = dict(spec)
        item.setdefault("source", "unknown")
        out.append(item)
    return out


# A rich, official-source dataset: 3 sources, >=10 results, SIRET present.
RICH_RESULTS = make_results(
    {"source": "sirene", "siret": "12345678901234", "name": "Alpha", "date": "2024-01-01"},
    {"source": "sirene", "siret": "22345678901234", "name": "Beta", "date": "2024-01-02"},
    {"source": "sirene", "siret": "32345678901234", "name": "Gamma", "date": "2024-01-03"},
    {"source": "bodacc", "siret": "12345678901234", "name": "Alpha", "date": "2024-01-04"},
    {"source": "bodacc", "siret": "42345678901234", "name": "Delta", "date": "2024-01-05"},
    {"source": "bodacc", "siret": "52345678901234", "name": "Epsilon", "date": "2024-01-06"},
    {"source": "boamp", "siret": "62345678901234", "name": "Zeta", "date": "2024-01-07"},
    {"source": "boamp", "siret": "72345678901234", "name": "Eta", "date": "2024-01-08"},
    {"source": "boamp", "siret": "82345678901234", "name": "Theta", "date": "2024-01-09"},
    {"source": "boamp", "siret": "92345678901234", "name": "Iota", "date": "2024-01-10"},
)


@pytest.fixture
def rich_data() -> dict[str, Any]:
    return {"results": list(RICH_RESULTS), "sources": ["sirene", "bodacc", "boamp"]}


@pytest.fixture
def empty_data() -> dict[str, Any]:
    return {"results": [], "sources": []}


@pytest.fixture
def two_source_data() -> dict[str, Any]:
    """Two sources, fewer than 10 results -> moderate confidence path."""
    return {
        "results": make_results(
            {"source": "sirene", "siret": "11111111111111", "name": "A"},
            {"source": "gdelt", "name": "B"},
        ),
        "sources": ["sirene", "gdelt"],
    }


@pytest.fixture
def single_source_unofficial() -> dict[str, Any]:
    """One unofficial source, no SIRET, no dates -> low confidence + issues."""
    return {
        "results": make_results(
            {"source": "rss", "name": "NewsCo"},
            {"source": "rss", "name": "OtherCo"},
        ),
        "sources": ["rss"],
    }


# ---------------------------------------------------------------------------
# Module-level structure
# ---------------------------------------------------------------------------
class TestModuleStructure:
    def test_base_agent_is_abstract(self):
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore[abstract]

    def test_agent_role_values(self):
        assert AgentRole.RESEARCHER.value == "researcher"
        assert AgentRole.CRITIC.value == "critic"
        assert AgentRole.VERIFIER.value == "verifier"
        assert AgentRole.FACT_CHECKER.value == "fact_checker"
        assert AgentRole.SOURCE_RANKER.value == "source_ranker"
        assert AgentRole.SYNTHESIZER.value == "synthesizer"

    @pytest.mark.parametrize(
        "agent_cls, name, role",
        [
            (ChercheurAgent, "Chercheur", "researcher"),
            (CritiqueAgent, "Critique", "critic"),
            (VerificateurAgent, "Vérificateur", "verifier"),
            (FactCheckerAgent, "Fact-Checker", "fact_checker"),
            (SourceRankerAgent, "Source-Ranker", "source_ranker"),
            (SynthesisAgent, "Synthèse", "synthesizer"),
        ],
    )
    def test_concrete_agents_name_and_role(self, agent_cls, name, role):
        agent = agent_cls()
        assert agent.name == name
        assert agent.role == role
        assert isinstance(agent, BaseAgent)

    def test_fake_llm_satisfies_protocol(self):
        # The Protocol is runtime_checkable; the double must pass isinstance.
        assert isinstance(FakeLLM(), LLMProvider)


# ---------------------------------------------------------------------------
# AgentMessage dataclass
# ---------------------------------------------------------------------------
class TestAgentMessage:
    def test_defaults(self):
        msg = AgentMessage(agent="X", role="researcher", content="hello")
        assert msg.confidence == 0.0
        assert msg.evidence == []
        assert msg.issues == []
        assert msg.metadata == {}

    def test_mutable_defaults_are_independent(self):
        a = AgentMessage(agent="A", role="r", content="c")
        b = AgentMessage(agent="B", role="r", content="c")
        a.issues.append("only-a")
        assert b.issues == []

    def test_to_dict_roundtrip_keys(self):
        msg = AgentMessage(
            agent="Chercheur",
            role="researcher",
            content="texte",
            confidence=42.0,
            evidence=[{"source": "sirene", "count": 3}],
            issues=["lacune"],
            metadata={"k": "v"},
        )
        d = msg.to_dict()
        assert d == {
            "agent": "Chercheur",
            "role": "researcher",
            "content": "texte",
            "confidence": 42.0,
            "evidence": [{"source": "sirene", "count": 3}],
            "issues": ["lacune"],
            "metadata": {"k": "v"},
        }


# ---------------------------------------------------------------------------
# BaseAgent shared behaviour (through a concrete subclass)
# ---------------------------------------------------------------------------
class TestBaseAgentBehaviour:
    def test_has_llm_false_by_default(self):
        assert ChercheurAgent().has_llm is False

    def test_has_llm_true_when_provided(self):
        assert ChercheurAgent(llm=FakeLLM()).has_llm is True

    async def test_generate_with_llm_returns_none_without_llm(self):
        agent = ChercheurAgent()
        assert await agent._generate_with_llm("prompt") is None

    async def test_generate_with_llm_returns_text(self):
        agent = ChercheurAgent(llm=FakeLLM("ok"))
        assert await agent._generate_with_llm("prompt", "system") == "ok"

    async def test_generate_with_llm_swallows_exceptions(self):
        # A failing LLM must not propagate; it returns None instead.
        agent = ChercheurAgent(llm=FailingLLM())
        assert await agent._generate_with_llm("prompt") is None


# ---------------------------------------------------------------------------
# ChercheurAgent (researcher)
# ---------------------------------------------------------------------------
class TestChercheurAgent:
    async def test_empty_results_zero_confidence(self, empty_data):
        msg = await ChercheurAgent().process(empty_data, [])
        assert msg.confidence == 0
        assert msg.role == "researcher"
        assert msg.agent == "Chercheur"
        assert "Aucun résultat" in msg.content

    async def test_rich_data_high_confidence(self, rich_data):
        msg = await ChercheurAgent().process(rich_data, [])
        assert msg.confidence == 80
        # One evidence entry per distinct source.
        assert {e["source"] for e in msg.evidence} == {"sirene", "bodacc", "boamp"}

    async def test_evidence_counts_match_grouping(self, rich_data):
        msg = await ChercheurAgent().process(rich_data, [])
        counts = {e["source"]: e["count"] for e in msg.evidence}
        assert counts == {"sirene": 3, "bodacc": 3, "boamp": 4}

    async def test_two_sources_moderate_confidence(self, two_source_data):
        msg = await ChercheurAgent().process(two_source_data, [])
        assert msg.confidence == 60

    async def test_single_source_limited_confidence(self, single_source_unofficial):
        msg = await ChercheurAgent().process(single_source_unofficial, [])
        assert msg.confidence == 40

    async def test_llm_appends_to_content(self, rich_data):
        llm = FakeLLM("INSIGHT")
        msg = await ChercheurAgent(llm=llm).process(rich_data, [])
        assert "### Analyse LLM:" in msg.content
        assert "INSIGHT" in msg.content
        assert len(llm.calls) == 1
        # The system prompt is forwarded to the LLM.
        assert llm.calls[0][1] == ChercheurAgent.SYSTEM_PROMPT

    async def test_llm_not_called_when_no_results(self, empty_data):
        llm = FakeLLM()
        await ChercheurAgent(llm=llm).process(empty_data, [])
        assert llm.calls == []

    async def test_failing_llm_falls_back_to_rule_based(self, rich_data):
        msg = await ChercheurAgent(llm=FailingLLM()).process(rich_data, [])
        assert "### Analyse LLM:" not in msg.content
        assert msg.confidence == 80


# ---------------------------------------------------------------------------
# CritiqueAgent (critic)
# ---------------------------------------------------------------------------
class TestCritiqueAgent:
    async def test_no_results_returns_zero_and_issue(self, empty_data):
        msg = await CritiqueAgent().process(empty_data, [])
        assert msg.confidence == 0
        assert "Aucune donnée à analyser" in msg.issues

    async def test_flags_missing_siret(self, single_source_unofficial):
        msg = await CritiqueAgent().process(single_source_unofficial, [])
        assert any("sans SIRET" in i for i in msg.issues)

    async def test_flags_missing_dates(self, single_source_unofficial):
        msg = await CritiqueAgent().process(single_source_unofficial, [])
        assert any("sans date" in i for i in msg.issues)

    async def test_flags_no_official_source(self, single_source_unofficial):
        msg = await CritiqueAgent().process(single_source_unofficial, [])
        assert any("Aucune source officielle" in i for i in msg.issues)

    async def test_rich_official_data_has_no_quality_issues(self, rich_data):
        msg = await CritiqueAgent().process(rich_data, [])
        assert msg.issues == []
        assert "Aucun problème majeur" in msg.content

    async def test_clean_data_gets_confidence_boost(self, rich_data):
        # No issues -> adjusted_confidence = min(base + 10, 100); base default 50.
        msg = await CritiqueAgent().process(rich_data, [])
        assert msg.confidence == 60

    async def test_penalty_subtracts_ten_per_issue(self, single_source_unofficial):
        # 3 issues -> penalty 30, base default 50 -> 20.
        msg = await CritiqueAgent().process(single_source_unofficial, [])
        assert len(msg.issues) == 3
        assert msg.confidence == 20

    async def test_uses_last_context_confidence_as_base(self, rich_data):
        prior = AgentMessage(agent="Chercheur", role="researcher", content="x", confidence=90)
        msg = await CritiqueAgent().process(rich_data, [prior])
        # No issues -> min(90 + 10, 100) = 100.
        assert msg.confidence == 100

    async def test_notes_low_researcher_confidence(self, rich_data):
        prior = AgentMessage(agent="Chercheur", role="researcher", content="x", confidence=30)
        msg = await CritiqueAgent().process(rich_data, [prior])
        assert any("faible niveau de confiance" in i for i in msg.issues)

    async def test_confidence_never_negative(self):
        data = {
            "results": make_results(
                *[{"source": "rss", "name": f"n{i}"} for i in range(3)]
            )
        }
        prior = AgentMessage(agent="x", role="researcher", content="x", confidence=5)
        msg = await CritiqueAgent().process(data, [prior])
        assert msg.confidence == 0

    async def test_llm_appends_when_results_present(self, single_source_unofficial):
        llm = FakeLLM("CRITIQUE")
        msg = await CritiqueAgent(llm=llm).process(single_source_unofficial, [])
        assert "### Critique LLM:" in msg.content
        assert len(llm.calls) == 1


# ---------------------------------------------------------------------------
# VerificateurAgent (verifier)
# ---------------------------------------------------------------------------
class TestVerificateurAgent:
    async def test_high_confidence_verdict(self, rich_data):
        prior = AgentMessage(agent="Critique", role="critic", content="x", confidence=80)
        msg = await VerificateurAgent().process(rich_data, [prior])
        assert msg.confidence >= 80
        assert "HAUTE CONFIANCE" in msg.content

    async def test_multi_source_entity_boost(self, rich_data):
        # "Alpha" (12345678901234) appears in both sirene and bodacc -> +10.
        prior = AgentMessage(agent="Critique", role="critic", content="x", confidence=50)
        msg = await VerificateurAgent().process(rich_data, [prior])
        # base 50 + 10 (multi-source) - 0 issues = 60.
        assert msg.confidence == 60
        assert "Entités multi-sources" in msg.content

    async def test_issue_penalty_five_per_issue(self, rich_data):
        prior = AgentMessage(
            agent="Critique",
            role="critic",
            content="x",
            confidence=50,
            issues=["i1", "i2"],
        )
        msg = await VerificateurAgent().process(rich_data, [prior])
        # base 50 + 10 (multi-source) - 2*5 = 50.
        assert msg.confidence == 50
        # All upstream issues are carried forward.
        assert msg.issues == ["i1", "i2"]

    async def test_confidence_clamped_to_hundred(self, rich_data):
        prior = AgentMessage(agent="x", role="critic", content="x", confidence=100)
        msg = await VerificateurAgent().process(rich_data, [prior])
        assert msg.confidence <= 100

    async def test_low_confidence_verdict(self, empty_data):
        prior = AgentMessage(
            agent="x",
            role="critic",
            content="x",
            confidence=20,
            issues=["a", "b", "c"],
        )
        msg = await VerificateurAgent().process(empty_data, [prior])
        assert msg.confidence < 40
        assert "TRÈS FAIBLE" in msg.content

    async def test_default_base_confidence_without_context(self, rich_data):
        msg = await VerificateurAgent().process(rich_data, [])
        # base default 50 + 10 (multi-source Alpha) = 60.
        assert msg.confidence == 60

    async def test_llm_appends_to_content(self, rich_data):
        llm = FakeLLM("VERIF")
        prior = AgentMessage(agent="x", role="critic", content="x", confidence=70)
        msg = await VerificateurAgent(llm=llm).process(rich_data, [prior])
        assert "### Vérification LLM:" in msg.content
        assert len(llm.calls) == 1


# ---------------------------------------------------------------------------
# FactCheckerAgent (fact_checker)
# ---------------------------------------------------------------------------
class TestFactCheckerAgent:
    async def test_no_results_zero_confidence(self, empty_data):
        msg = await FactCheckerAgent().process(empty_data, [])
        assert msg.confidence == 0
        assert "Aucune entité" in msg.content

    async def test_all_official_full_confidence(self, rich_data):
        msg = await FactCheckerAgent().process(rich_data, [])
        # Every entity is keyed by SIRET and seen via an authoritative source.
        assert msg.confidence == 100
        assert msg.metadata["unverified_claims"] == []
        assert len(msg.metadata["verified_facts"]) > 0

    async def test_unofficial_only_zero_verified(self, single_source_unofficial):
        msg = await FactCheckerAgent().process(single_source_unofficial, [])
        assert msg.confidence == 0
        assert msg.metadata["verified_facts"] == []
        assert any("sans source officielle" in i for i in msg.issues)

    async def test_partial_verification_ratio(self):
        # 2 entities: one via sirene (verified), one via rss (unverified) -> 50%.
        data = {
            "results": make_results(
                {"source": "sirene", "siret": "11111111111111", "name": "A"},
                {"source": "rss", "name": "B"},
            )
        }
        msg = await FactCheckerAgent().process(data, [])
        assert msg.confidence == 50
        assert len(msg.metadata["verified_facts"]) == 1
        assert len(msg.metadata["unverified_claims"]) == 1

    async def test_verified_fact_records_source(self, rich_data):
        msg = await FactCheckerAgent().process(rich_data, [])
        alpha = next(
            f for f in msg.metadata["verified_facts"] if f["entity"] == "12345678901234"
        )
        # Alpha is corroborated by both sirene and bodacc.
        assert set(alpha["verified_by"]) == {"sirene", "bodacc"}

    async def test_llm_appends_to_content(self, rich_data):
        llm = FakeLLM("FACTS")
        msg = await FactCheckerAgent(llm=llm).process(rich_data, [])
        assert "### Fact-Check LLM:" in msg.content
        assert len(llm.calls) == 1


# ---------------------------------------------------------------------------
# SourceRankerAgent (source_ranker)
# ---------------------------------------------------------------------------
class TestSourceRankerAgent:
    async def test_no_results_zero_confidence(self, empty_data):
        msg = await SourceRankerAgent().process(empty_data, [])
        assert msg.confidence == 0
        assert "Aucune source" in msg.content

    async def test_official_sources_rank_high(self, rich_data):
        msg = await SourceRankerAgent().process(rich_data, [])
        ranked = msg.metadata["ranked_sources"]
        # Sorted by composite score descending.
        scores = [s["score"] for s in ranked]
        assert scores == sorted(scores, reverse=True)
        assert ranked[0]["source"] in {"sirene", "bodacc", "boamp"}
        assert msg.confidence >= 80

    async def test_completeness_bonus_caps_at_hundred(self, rich_data):
        msg = await SourceRankerAgent().process(rich_data, [])
        for src in msg.metadata["ranked_sources"]:
            assert src["score"] <= 100

    async def test_unknown_source_low_score(self):
        data = {"results": make_results({"name": "x"}, {"name": "y"})}  # source defaults unknown
        msg = await SourceRankerAgent().process(data, [])
        ranked = msg.metadata["ranked_sources"]
        assert ranked[0]["source"] == "unknown"
        assert ranked[0]["reliability"] == 30

    async def test_low_reliability_sources_flagged(self):
        data = {
            "results": make_results(
                {"source": "rss", "name": "a"},
                {"source": "unknown", "name": "b"},
            )
        }
        msg = await SourceRankerAgent().process(data, [])
        assert any("peu fiables" in i for i in msg.issues)

    async def test_confidence_is_top3_average(self):
        # sirene(95) only, no dates/siret -> top score 95 -> confidence 95.
        data = {"results": make_results({"source": "sirene", "name": "a"})}
        msg = await SourceRankerAgent().process(data, [])
        assert msg.confidence == 95

    async def test_llm_appends_to_content(self, rich_data):
        llm = FakeLLM("RANK")
        msg = await SourceRankerAgent(llm=llm).process(rich_data, [])
        assert "### Analyse LLM:" in msg.content
        assert len(llm.calls) == 1


# ---------------------------------------------------------------------------
# SynthesisAgent (synthesizer)
# ---------------------------------------------------------------------------
class TestSynthesisAgent:
    async def test_no_context_zero_confidence(self, rich_data):
        msg = await SynthesisAgent().process(rich_data, [])
        assert msg.confidence == 0
        assert msg.metadata["agents_consulted"] == 0

    async def test_averages_positive_confidences(self, rich_data):
        context = [
            AgentMessage(agent="A", role="researcher", content="x", confidence=80),
            AgentMessage(agent="B", role="critic", content="x", confidence=60),
        ]
        msg = await SynthesisAgent().process(rich_data, context)
        # avg = 70, no issues -> confidence 70.
        assert msg.confidence == 70

    async def test_zero_confidence_messages_excluded_from_average(self, rich_data):
        context = [
            AgentMessage(agent="A", role="researcher", content="x", confidence=0),
            AgentMessage(agent="B", role="critic", content="x", confidence=80),
        ]
        msg = await SynthesisAgent().process(rich_data, context)
        # Only the 80 counts (the 0 is skipped) -> 80.
        assert msg.confidence == 80

    async def test_issue_penalty_three_per_unique_issue(self, rich_data):
        context = [
            AgentMessage(
                agent="A",
                role="critic",
                content="x",
                confidence=90,
                issues=["i1", "i2"],
            )
        ]
        msg = await SynthesisAgent().process(rich_data, context)
        # avg 90 - 2 unique issues * 3 = 84.
        assert msg.confidence == 84

    async def test_duplicate_issues_deduplicated(self, rich_data):
        context = [
            AgentMessage(agent="A", role="critic", content="x", confidence=90, issues=["dup"]),
            AgentMessage(agent="B", role="verifier", content="x", confidence=90, issues=["dup"]),
        ]
        msg = await SynthesisAgent().process(rich_data, context)
        assert msg.issues == ["dup"]
        # avg 90 - 1 unique issue * 3 = 87.
        assert msg.confidence == 87
        assert msg.metadata["issues_count"] == 1

    async def test_metadata_counts(self, rich_data):
        context = [
            AgentMessage(agent="A", role="researcher", content="x", confidence=70),
        ]
        msg = await SynthesisAgent().process(rich_data, context)
        assert msg.metadata["total_results"] == len(RICH_RESULTS)
        assert msg.metadata["agents_consulted"] == 1

    async def test_confidence_never_negative(self, rich_data):
        context = [
            AgentMessage(
                agent="A",
                role="critic",
                content="x",
                confidence=5,
                issues=[f"i{n}" for n in range(10)],
            )
        ]
        msg = await SynthesisAgent().process(rich_data, context)
        assert msg.confidence == 0

    async def test_recommendation_reflects_confidence(self, rich_data):
        high = [AgentMessage(agent="A", role="r", content="x", confidence=90)]
        msg = await SynthesisAgent().process(rich_data, high)
        assert "Données fiables" in msg.content

    async def test_llm_appends_to_content(self, rich_data):
        llm = FakeLLM("SYNTH")
        context = [AgentMessage(agent="A", role="researcher", content="x", confidence=70)]
        msg = await SynthesisAgent(llm=llm).process(rich_data, context)
        assert "### Synthèse LLM:" in msg.content
        assert len(llm.calls) == 1

    async def test_llm_not_called_without_context(self, rich_data):
        llm = FakeLLM()
        await SynthesisAgent(llm=llm).process(rich_data, [])
        assert llm.calls == []


# ---------------------------------------------------------------------------
# End-to-end debate chain (agents fed each other's messages)
# ---------------------------------------------------------------------------
class TestDebateChain:
    async def test_full_pipeline_produces_messages(self, rich_data):
        context: list[AgentMessage] = []
        for agent in (
            ChercheurAgent(),
            SourceRankerAgent(),
            CritiqueAgent(),
            FactCheckerAgent(),
            VerificateurAgent(),
            SynthesisAgent(),
        ):
            msg = await agent.process(rich_data, context)
            assert isinstance(msg, AgentMessage)
            assert 0 <= msg.confidence <= 100
            context.append(msg)
        assert len(context) == 6
        # Each agent kept its declared role.
        assert [m.role for m in context] == [
            "researcher",
            "source_ranker",
            "critic",
            "fact_checker",
            "verifier",
            "synthesizer",
        ]

    async def test_pipeline_on_poor_data_stays_low(self, single_source_unofficial):
        context: list[AgentMessage] = []
        for agent in (
            ChercheurAgent(),
            SourceRankerAgent(),
            CritiqueAgent(),
            FactCheckerAgent(),
            VerificateurAgent(),
            SynthesisAgent(),
        ):
            context.append(await agent.process(single_source_unofficial, context))
        # Unofficial, no SIRET, no dates -> final synthesis confidence is modest.
        assert context[-1].confidence < 60
