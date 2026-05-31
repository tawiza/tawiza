"""Unit tests for the orchestrated multi-source report generator (issue #161, batch 4).

Covers ``src/application/reporting/orchestrated_report.py``:

- ReportConfig: dataclass construction (required + optional fields, defaults).
- OrchestratedReportGenerator: directory creation on init, and the three
  rendering methods (HTML, JSON, Markdown) exercised against in-memory
  ``OrchestratedResult`` / ``DebateResult`` fixtures.
- Section formatting: source breakdown, debate timeline, issues list,
  results preview, confidence colour/emoji thresholds, theme switching.
- Empty / degenerate cases: no sources, no debate messages, no issues,
  failed sources (error set), missing optional result fields.
- generate_orchestrated_report: the async convenience wrapper that emits all
  three formats at once.

The production code is the source of truth. The collaborators
(``OrchestratedResult``, ``QueryResult``, ``DebateResult``, ``AgentMessage``)
are plain dataclasses with no external I/O, so they are built directly rather
than mocked. The only side effect of the generator is writing files into the
configured output directory, which is redirected to a pytest ``tmp_path``.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.application.orchestration.data_orchestrator import (
    OrchestratedResult,
    QueryResult,
)
from src.application.reporting.orchestrated_report import (
    OrchestratedReportGenerator,
    ReportConfig,
    generate_orchestrated_report,
)
from src.domain.debate.agents import AgentMessage
from src.domain.debate.debate_system import DebateResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _query_result(
    source: str = "bodacc",
    results: list | None = None,
    duration_ms: float = 123.0,
    error: str | None = None,
) -> QueryResult:
    """Build a QueryResult with sensible defaults."""
    return QueryResult(
        source=source,
        query={"keywords": "test"},
        results=results if results is not None else [{"source": source, "title": "Item"}],
        duration_ms=duration_ms,
        error=error,
    )


def _orch_result(
    source_results: list[QueryResult] | None = None,
    total_results: int | None = None,
    total_duration_ms: float = 250.0,
    correlated_entities: list | None = None,
) -> OrchestratedResult:
    """Build an OrchestratedResult, deriving total_results when omitted."""
    if source_results is None:
        source_results = [_query_result()]
    if total_results is None:
        total_results = sum(len(sr.results) for sr in source_results)
    return OrchestratedResult(
        query="startup IA Lille",
        timestamp=datetime(2026, 5, 31, 12, 0, 0),
        source_results=source_results,
        correlated_entities=correlated_entities if correlated_entities is not None else [],
        total_results=total_results,
        total_duration_ms=total_duration_ms,
    )


def _agent_message(
    agent: str = "Chercheur",
    role: str = "researcher",
    content: str = "Analyse des données collectées.",
    confidence: float = 75.0,
    issues: list[str] | None = None,
) -> AgentMessage:
    """Build an AgentMessage with sensible defaults."""
    return AgentMessage(
        agent=agent,
        role=role,
        content=content,
        confidence=confidence,
        issues=issues if issues is not None else [],
    )


def _debate_result(
    messages: list[AgentMessage] | None = None,
    final_confidence: float = 85.0,
    verdict: str = "Données fiables",
    issues: list[str] | None = None,
) -> DebateResult:
    """Build a DebateResult with sensible defaults."""
    if messages is None:
        messages = [_agent_message()]
    return DebateResult(
        query="startup IA Lille",
        timestamp=datetime(2026, 5, 31, 12, 0, 0),
        messages=messages,
        final_confidence=final_confidence,
        verdict=verdict,
        issues=issues if issues is not None else [],
        duration_ms=42.0,
    )


def _make_generator(tmp_path, **config_overrides) -> OrchestratedReportGenerator:
    """Create a generator whose output_dir points to a tmp dir."""
    kwargs = {"output_dir": str(tmp_path / "out"), "query": "startup IA Lille"}
    kwargs.update(config_overrides)
    return OrchestratedReportGenerator(ReportConfig(**kwargs))


def _read(path: str) -> str:
    """Read a generated report file without leaking the handle."""
    return Path(path).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# ReportConfig
# ---------------------------------------------------------------------------
class TestReportConfig:
    """Construction and defaults of ReportConfig."""

    def test_required_fields(self):
        cfg = ReportConfig(output_dir="/tmp/x", query="q")
        assert cfg.output_dir == "/tmp/x"
        assert cfg.query == "q"

    def test_defaults(self):
        cfg = ReportConfig(output_dir="/tmp/x", query="q")
        assert cfg.include_raw_data is True
        assert cfg.include_timeline is True
        assert cfg.theme == "dark"

    def test_overriding_optional_fields(self):
        cfg = ReportConfig(
            output_dir="/tmp/x",
            query="q",
            include_raw_data=False,
            include_timeline=False,
            theme="light",
        )
        assert cfg.include_raw_data is False
        assert cfg.include_timeline is False
        assert cfg.theme == "light"


# ---------------------------------------------------------------------------
# OrchestratedReportGenerator — initialisation
# ---------------------------------------------------------------------------
class TestGeneratorInit:
    """The generator should create its output directory eagerly."""

    def test_init_creates_output_dir(self, tmp_path):
        target = tmp_path / "nested" / "reports"
        assert not target.exists()
        gen = OrchestratedReportGenerator(
            ReportConfig(output_dir=str(target), query="q")
        )
        assert target.exists()
        assert target.is_dir()
        assert gen.output_dir == target

    def test_init_is_idempotent_when_dir_exists(self, tmp_path):
        target = tmp_path / "reports"
        target.mkdir()
        # Should not raise (exist_ok=True).
        gen = OrchestratedReportGenerator(
            ReportConfig(output_dir=str(target), query="q")
        )
        assert gen.output_dir == target

    def test_init_keeps_config_reference(self, tmp_path):
        cfg = ReportConfig(output_dir=str(tmp_path / "o"), query="my query")
        gen = OrchestratedReportGenerator(cfg)
        assert gen.config is cfg


# ---------------------------------------------------------------------------
# generate_html_report
# ---------------------------------------------------------------------------
class TestHtmlReport:
    """HTML rendering, section content and theme handling."""

    def test_returns_path_and_writes_file(self, tmp_path):
        gen = _make_generator(tmp_path)
        path = gen.generate_html_report(_orch_result(), _debate_result())
        assert path.endswith("rapport_multi_source.html")
        assert (gen.output_dir / "rapport_multi_source.html").exists()

    def test_html_contains_query_and_verdict(self, tmp_path):
        gen = _make_generator(tmp_path, query="éolien Bretagne")
        html = _read(gen.generate_html_report(
                _orch_result(), _debate_result(verdict="Données fiables")
            ))
        assert "éolien Bretagne" in html
        assert "Données fiables" in html

    def test_html_renders_metrics(self, tmp_path):
        gen = _make_generator(tmp_path)
        orch = _orch_result(
            source_results=[
                _query_result(source="bodacc", results=[{"title": "a"}, {"title": "b"}]),
                _query_result(source="sirene", results=[]),
            ],
            total_results=2,
        )
        html = _read(gen.generate_html_report(orch, _debate_result()))
        # 1 of 2 sources had results -> "1/2"
        assert "1/2" in html
        # total_results metric
        assert ">2</div>" in html

    def test_html_source_rows_show_success_and_failure(self, tmp_path):
        gen = _make_generator(tmp_path)
        orch = _orch_result(
            source_results=[
                _query_result(source="bodacc", results=[{"title": "ok"}]),
                _query_result(source="gdelt", results=[], error="timeout exceeded"),
            ]
        )
        html = _read(gen.generate_html_report(orch, _debate_result()))
        assert "bodacc" in html
        assert "gdelt" in html
        assert "timeout exceeded" in html
        assert "✓" in html  # success marker
        assert "✗" in html  # failure marker

    def test_html_debate_timeline_rendered(self, tmp_path):
        gen = _make_generator(tmp_path)
        debate = _debate_result(
            messages=[
                _agent_message(agent="Chercheur", role="researcher", confidence=70),
                _agent_message(agent="Critique", role="critic", confidence=60),
                _agent_message(agent="Vérificateur", role="verifier", confidence=88),
            ]
        )
        html = _read(gen.generate_html_report(_orch_result(), debate))
        assert "Chercheur" in html
        assert "Critique" in html
        assert "Vérificateur" in html
        # Role icons present
        assert "🔍" in html and "🎯" in html and "✅" in html

    def test_html_issues_listed_when_present(self, tmp_path):
        gen = _make_generator(tmp_path)
        debate = _debate_result(issues=["Source non vérifiée", "Date manquante"])
        html = _read(gen.generate_html_report(_orch_result(), debate))
        assert "Source non vérifiée" in html
        assert "Date manquante" in html

    def test_html_no_issues_shows_success_message(self, tmp_path):
        gen = _make_generator(tmp_path)
        html = _read(gen.generate_html_report(_orch_result(), _debate_result(issues=[])))
        assert "Aucun problème majeur détecté" in html

    def test_html_results_preview_uses_fallback_title(self, tmp_path):
        gen = _make_generator(tmp_path)
        orch = _orch_result(
            source_results=[
                _query_result(
                    source="sirene",
                    results=[{"source": "sirene", "nom": "ACME SAS"}],
                )
            ]
        )
        html = _read(gen.generate_html_report(orch, _debate_result()))
        assert "ACME SAS" in html

    def test_html_results_preview_na_when_no_title_keys(self, tmp_path):
        gen = _make_generator(tmp_path)
        orch = _orch_result(
            source_results=[_query_result(results=[{"source": "x", "irrelevant": 1}])]
        )
        html = _read(gen.generate_html_report(orch, _debate_result()))
        assert "N/A" in html

    def test_html_dark_vs_light_theme_differ(self, tmp_path):
        dark = _make_generator(tmp_path / "d", theme="dark")
        light = _make_generator(tmp_path / "l", theme="light")
        dark_html = _read(dark.generate_html_report(_orch_result(), _debate_result()))
        light_html = _read(light.generate_html_report(_orch_result(), _debate_result()))
        assert "#1a1a2e" in dark_html  # dark bg
        assert "#1a1a2e" not in light_html
        assert "#f3f4f6" in light_html  # light bg

    @pytest.mark.parametrize(
        "confidence,color",
        [
            (90.0, "#10B981"),  # high -> green
            (70.0, "#F59E0B"),  # medium -> amber
            (30.0, "#EF4444"),  # low -> red
        ],
    )
    def test_html_confidence_colour_thresholds(self, tmp_path, confidence, color):
        gen = _make_generator(tmp_path / f"c{int(confidence)}")
        html = _read(gen.generate_html_report(
                _orch_result(), _debate_result(final_confidence=confidence)
            ))
        assert color in html

    def test_html_empty_everything(self, tmp_path):
        """No sources, no debate messages, no issues, zero results."""
        gen = _make_generator(tmp_path)
        orch = _orch_result(source_results=[], total_results=0)
        debate = _debate_result(messages=[], issues=[], final_confidence=0.0)
        html = _read(gen.generate_html_report(orch, debate))
        assert "0/0" in html  # 0 successful / 0 total
        assert "Aucun problème majeur détecté" in html
        assert "<!DOCTYPE html>" in html


# ---------------------------------------------------------------------------
# generate_json_export
# ---------------------------------------------------------------------------
class TestJsonExport:
    """JSON export structure and content."""

    def test_returns_path_and_writes_file(self, tmp_path):
        gen = _make_generator(tmp_path)
        path = gen.generate_json_export(_orch_result(), _debate_result())
        assert path.endswith("analyse_complete.json")
        assert (gen.output_dir / "analyse_complete.json").exists()

    def test_json_structure(self, tmp_path):
        gen = _make_generator(tmp_path, query="my query")
        orch = _orch_result(
            source_results=[
                _query_result(source="bodacc", results=[{"title": "a"}]),
                _query_result(source="gdelt", results=[], error="boom"),
            ],
            total_results=1,
            correlated_entities=[[{"a": 1}], [{"b": 2}]],
        )
        debate = _debate_result(
            messages=[_agent_message(issues=["i1"])],
            final_confidence=85.0,
            verdict="ok",
            issues=["i1"],
        )
        data = json.loads(
            _read(gen.generate_json_export(orch, debate))
        )
        assert data["meta"]["query"] == "my query"
        assert "generated_at" in data["meta"]
        assert data["confidence"]["score"] == 85.0
        assert data["confidence"]["verdict"] == "ok"
        assert data["confidence"]["is_valid"] is True
        assert data["confidence"]["is_high_confidence"] is True
        assert data["results"]["total"] == 1
        assert data["results"]["correlated_entities"] == 2

    def test_json_sources_include_counts_and_errors(self, tmp_path):
        gen = _make_generator(tmp_path)
        orch = _orch_result(
            source_results=[
                _query_result(source="bodacc", results=[{"x": 1}, {"x": 2}]),
                _query_result(source="gdelt", results=[], error="timeout"),
            ]
        )
        data = json.loads(
            _read(gen.generate_json_export(orch, _debate_result()))
        )
        sources = {s["name"]: s for s in data["sources"]}
        assert sources["bodacc"]["results_count"] == 2
        assert sources["bodacc"]["error"] is None
        assert sources["gdelt"]["results_count"] == 0
        assert sources["gdelt"]["error"] == "timeout"

    def test_json_debate_rounds(self, tmp_path):
        gen = _make_generator(tmp_path)
        debate = _debate_result(
            messages=[
                _agent_message(agent="Chercheur", role="researcher", confidence=70),
                _agent_message(agent="Critique", role="critic", confidence=60, issues=["q"]),
            ]
        )
        data = json.loads(
            _read(gen.generate_json_export(_orch_result(), debate))
        )
        rounds = data["debate"]["rounds"]
        assert len(rounds) == 2
        assert rounds[0]["agent"] == "Chercheur"
        assert rounds[0]["role"] == "researcher"
        assert rounds[1]["issues"] == ["q"]

    def test_json_by_source_only_includes_non_empty(self, tmp_path):
        gen = _make_generator(tmp_path)
        orch = _orch_result(
            source_results=[
                _query_result(source="bodacc", results=[{"title": "a"}]),
                _query_result(source="gdelt", results=[]),
            ]
        )
        data = json.loads(
            _read(gen.generate_json_export(orch, _debate_result()))
        )
        by_source = data["results"]["by_source"]
        assert "bodacc" in by_source
        assert "gdelt" not in by_source

    def test_json_low_confidence_flags(self, tmp_path):
        gen = _make_generator(tmp_path)
        debate = _debate_result(final_confidence=30.0)
        data = json.loads(
            _read(gen.generate_json_export(_orch_result(), debate))
        )
        assert data["confidence"]["is_valid"] is False
        assert data["confidence"]["is_high_confidence"] is False

    def test_json_empty_inputs_serialise(self, tmp_path):
        gen = _make_generator(tmp_path)
        orch = _orch_result(source_results=[], total_results=0)
        debate = _debate_result(messages=[], issues=[])
        data = json.loads(
            _read(gen.generate_json_export(orch, debate))
        )
        assert data["sources"] == []
        assert data["debate"]["rounds"] == []
        assert data["results"]["by_source"] == {}

    def test_json_is_valid_utf8_with_accents(self, tmp_path):
        gen = _make_generator(tmp_path)
        debate = _debate_result(verdict="Vérification réussie", issues=["Problème détecté"])
        raw = _read(gen.generate_json_export(_orch_result(), debate))
        # ensure_ascii=False -> accents kept literally, not escaped.
        assert "Vérification réussie" in raw
        assert "Problème détecté" in raw


# ---------------------------------------------------------------------------
# generate_markdown_report
# ---------------------------------------------------------------------------
class TestMarkdownReport:
    """Markdown rendering, section content and thresholds."""

    def test_returns_path_and_writes_file(self, tmp_path):
        gen = _make_generator(tmp_path)
        path = gen.generate_markdown_report(_orch_result(), _debate_result())
        assert path.endswith("rapport_multi_source.md")
        assert (gen.output_dir / "rapport_multi_source.md").exists()

    def test_markdown_header_and_verdict(self, tmp_path):
        gen = _make_generator(tmp_path, query="hydrogène vert")
        md = _read(gen.generate_markdown_report(
                _orch_result(), _debate_result(verdict="Confiance élevée")
            ))
        assert "# 📊 Rapport d'Analyse Multi-Source" in md
        assert "hydrogène vert" in md
        assert "Confiance élevée" in md

    def test_markdown_source_table(self, tmp_path):
        gen = _make_generator(tmp_path)
        orch = _orch_result(
            source_results=[
                _query_result(source="bodacc", results=[{"title": "a"}]),
                _query_result(source="gdelt", results=[], error="timeout error xyz"),
            ]
        )
        md = _read(gen.generate_markdown_report(orch, _debate_result()))
        assert "| Source | Résultats | Temps | Statut |" in md
        assert "bodacc" in md
        assert "✅" in md  # success
        assert "❌" in md  # failure
        assert "timeout error xyz" in md

    def test_markdown_debate_section(self, tmp_path):
        gen = _make_generator(tmp_path)
        debate = _debate_result(
            messages=[
                _agent_message(agent="Chercheur", role="researcher", confidence=72),
                _agent_message(agent="Vérificateur", role="verifier", confidence=90),
            ]
        )
        md = _read(gen.generate_markdown_report(_orch_result(), debate))
        assert "### 🔍 Chercheur (72%)" in md
        assert "### ✅ Vérificateur (90%)" in md

    def test_markdown_issues_present(self, tmp_path):
        gen = _make_generator(tmp_path)
        debate = _debate_result(issues=["Incohérence temporelle"])
        md = _read(gen.generate_markdown_report(_orch_result(), debate))
        assert "- ⚠️ Incohérence temporelle" in md

    def test_markdown_no_issues_success(self, tmp_path):
        gen = _make_generator(tmp_path)
        md = _read(gen.generate_markdown_report(_orch_result(), _debate_result(issues=[])))
        assert "Aucun problème majeur détecté" in md

    def test_markdown_results_preview_with_siret_and_date(self, tmp_path):
        gen = _make_generator(tmp_path)
        orch = _orch_result(
            source_results=[
                _query_result(
                    source="sirene",
                    results=[
                        {
                            "source": "sirene",
                            "name": "ACME SAS",
                            "siret": "12345678900011",
                            "date": "2026-01-01",
                        }
                    ],
                )
            ]
        )
        md = _read(gen.generate_markdown_report(orch, _debate_result()))
        assert "ACME SAS" in md
        assert "SIRET: 12345678900011" in md
        assert "2026-01-01" in md

    @pytest.mark.parametrize(
        "confidence,emoji",
        [
            (90.0, "🟢"),  # high
            (70.0, "🟡"),  # medium
            (20.0, "🔴"),  # low
        ],
    )
    def test_markdown_confidence_emoji_thresholds(self, tmp_path, confidence, emoji):
        gen = _make_generator(tmp_path / f"m{int(confidence)}")
        md = _read(gen.generate_markdown_report(
                _orch_result(), _debate_result(final_confidence=confidence)
            ))
        assert emoji in md

    def test_markdown_empty_inputs(self, tmp_path):
        gen = _make_generator(tmp_path)
        orch = _orch_result(source_results=[], total_results=0)
        debate = _debate_result(messages=[], issues=[], final_confidence=0.0)
        md = _read(gen.generate_markdown_report(orch, debate))
        assert "0/0" in md  # successful / total sources
        assert "Aucun problème majeur détecté" in md


# ---------------------------------------------------------------------------
# generate_orchestrated_report (async convenience wrapper)
# ---------------------------------------------------------------------------
class TestConvenienceWrapper:
    """The async helper emits all three formats into the output dir."""

    @pytest.mark.asyncio
    async def test_generates_all_three_formats(self, tmp_path):
        paths = await generate_orchestrated_report(
            query="startup IA Lille",
            output_dir=str(tmp_path / "out"),
            orch_result=_orch_result(),
            debate_result=_debate_result(),
        )
        assert set(paths.keys()) == {"md", "html", "json"}
        for fmt, path in paths.items():
            assert path  # non-empty path string
            with open(path, encoding="utf-8") as fh:
                assert fh.read()  # file exists and non-empty
        assert paths["md"].endswith(".md")
        assert paths["html"].endswith(".html")
        assert paths["json"].endswith(".json")

    @pytest.mark.asyncio
    async def test_theme_is_propagated(self, tmp_path):
        paths = await generate_orchestrated_report(
            query="q",
            output_dir=str(tmp_path / "out"),
            orch_result=_orch_result(),
            debate_result=_debate_result(),
            theme="light",
        )
        html = _read(paths["html"])
        assert "#f3f4f6" in html  # light theme background

    @pytest.mark.asyncio
    async def test_json_payload_is_consistent(self, tmp_path):
        paths = await generate_orchestrated_report(
            query="cohérence",
            output_dir=str(tmp_path / "out"),
            orch_result=_orch_result(),
            debate_result=_debate_result(verdict="OK", final_confidence=85.0),
        )
        data = json.loads(_read(paths["json"]))
        assert data["meta"]["query"] == "cohérence"
        assert data["confidence"]["verdict"] == "OK"
