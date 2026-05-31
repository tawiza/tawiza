"""Unit tests for RelationService (issue #161, batch 5 -- big surface).

Target module: src/application/services/relation_service.py

The production code is the source of truth. These tests exercise the
orchestration logic in memory, with ALL I/O mocked via ``unittest.mock``:

- the shared asyncpg pool (``acquire_conn``) -- patched as an async context
  manager yielding a connection whose ``fetch/fetchval/fetchrow/execute`` are
  ``AsyncMock``s;
- the L1/L2/L3 registries (``EXTRACTORS`` / ``INFERRERS`` / ``PREDICTORS``)
  -- patched with fake extractor/inferrer/predictor classes;
- the Redis cache (``get_redis_cache``) -- patched so the cache helpers
  ``_cache_get`` / ``_cache_set`` / ``_cache_invalidate`` can be tested both
  on the happy path and when Redis raises;
- ``simulate_whatif`` and ``save_snapshot`` -- patched at the import sites.

Covered surface:
- module-level constants (CAPABILITY_MATRIX, _NODE_SIZE);
- cache helpers (_cache_get / _cache_set / _cache_invalidate), including the
  swallow-exception branches;
- RelationService.discover (default sources, custom sources + auto-append of
  nature_juridique, pre/post-persist split, L2 inferrers, L3 predictors,
  extractor/inferrer/predictor failures, snapshot failure swallowed);
- RelationService.get_graph (dept-scoped, cross-dept, actor_types filter,
  empty actor set, min_confidence filter, isolated-node pruning, cache hit);
- RelationService.get_coverage (percentages, weighted score, empty);
- RelationService.get_gaps (each of the 8 gap branches + honesty table);
- _upsert_actors (dedupe by external_id, json metadata, per-row error);
- _upsert_relations (ext_id -> uuid mapping, skip-missing-actor, error);
- _to_graphml (XML structure);
- export_graph (json / csv / graphml);
- whatif (delegates to simulate_whatif).
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services import relation_service as rs
from src.application.services.relation_service import (
    CAPABILITY_MATRIX,
    RelationService,
    _NODE_SIZE,
    _cache_get,
    _cache_invalidate,
    _cache_set,
)

MODULE = "src.application.services.relation_service"


# ---------------------------------------------------------------------------
# Mocking helpers
# ---------------------------------------------------------------------------
_UNSET = object()


def _make_conn(
    *,
    fetch=_UNSET,
    fetch_seq=_UNSET,
    fetchval=_UNSET,
    fetchval_seq=_UNSET,
    fetchrow=None,
):
    """Build a MagicMock connection with async DB methods.

    For a single ``conn.fetch(...)`` call use ``fetch=<list-of-rows>`` (the
    whole list is returned as one result). When the code under test issues
    *several* ``conn.fetch`` calls, use ``fetch_seq=[result1, result2, ...]``
    (consumed one per call via ``side_effect``). Same convention for
    ``fetchval`` / ``fetchval_seq``.
    """
    conn = MagicMock()

    if fetch_seq is not _UNSET:
        conn.fetch = AsyncMock(side_effect=fetch_seq)
    else:
        conn.fetch = AsyncMock(return_value=[] if fetch is _UNSET else fetch)

    if fetchval_seq is not _UNSET:
        conn.fetchval = AsyncMock(side_effect=fetchval_seq)
    else:
        conn.fetchval = AsyncMock(return_value=0 if fetchval is _UNSET else fetchval)

    conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.execute = AsyncMock(return_value=None)
    return conn


def _patch_acquire(conn):
    """Patch ``relation_service.acquire_conn`` to yield *conn*."""

    @asynccontextmanager
    async def _ctx():
        yield conn

    return patch(f"{MODULE}.acquire_conn", _ctx)


def _patch_acquire_factory(conns):
    """Patch ``acquire_conn`` so each ``async with`` yields the next conn.

    *conns* is a list consumed in call order -- useful for ``discover`` which
    opens several independent connections.
    """
    it = iter(conns)

    @asynccontextmanager
    async def _ctx():
        yield next(it)

    return patch(f"{MODULE}.acquire_conn", _ctx)


def _fake_cache(get_return=None, raise_on=None):
    """Return a MagicMock redis-cache whose get/set/delete are AsyncMocks."""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=get_return)
    cache.set = AsyncMock(return_value=None)
    cache.delete = AsyncMock(return_value=True)
    if raise_on:
        getattr(cache, raise_on).side_effect = RuntimeError("redis down")
    return cache


def _patch_cache(cache):
    return patch(f"{MODULE}.get_redis_cache", AsyncMock(return_value=cache))


def _patch_cache_raises():
    """Patch get_redis_cache itself to raise (connection failure)."""
    return patch(f"{MODULE}.get_redis_cache", AsyncMock(side_effect=RuntimeError("no redis")))


def _arow(**kw):
    """asyncpg rows behave like dict-with-attrs; a plain dict is enough here."""
    return dict(kw)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
class TestModuleConstants:
    def test_capability_matrix_is_list_of_dicts(self):
        assert isinstance(CAPABILITY_MATRIX, list)
        assert len(CAPABILITY_MATRIX) >= 10
        for entry in CAPABILITY_MATRIX:
            assert {"capability", "level", "missing", "source", "method"} <= set(entry)

    def test_capability_levels_within_bounds(self):
        for entry in CAPABILITY_MATRIX:
            assert 1 <= entry["level"] <= 7

    def test_node_size_known_types(self):
        assert _NODE_SIZE["territory"] == 25.0
        assert _NODE_SIZE["enterprise"] == 10.0

    def test_node_size_default_used_for_unknown(self):
        # get_graph uses _NODE_SIZE.get(type, 10.0)
        assert _NODE_SIZE.get("does_not_exist", 10.0) == 10.0


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
class TestCacheHelpers:
    @pytest.mark.asyncio
    async def test_cache_get_hit(self):
        cache = _fake_cache(get_return={"x": 1})
        with _patch_cache(cache):
            assert await _cache_get("k") == {"x": 1}
        cache.get.assert_awaited_once_with("k")

    @pytest.mark.asyncio
    async def test_cache_get_miss_returns_none(self):
        cache = _fake_cache(get_return=None)
        with _patch_cache(cache):
            assert await _cache_get("k") is None

    @pytest.mark.asyncio
    async def test_cache_get_swallows_exception(self):
        with _patch_cache_raises():
            assert await _cache_get("k") is None

    @pytest.mark.asyncio
    async def test_cache_set_calls_underlying(self):
        cache = _fake_cache()
        with _patch_cache(cache):
            await _cache_set("k", {"v": 2}, ttl=42)
        cache.set.assert_awaited_once_with("k", {"v": 2}, ttl=42)

    @pytest.mark.asyncio
    async def test_cache_set_swallows_exception(self):
        with _patch_cache_raises():
            # Must not raise
            await _cache_set("k", {"v": 2})

    @pytest.mark.asyncio
    async def test_cache_invalidate_deletes_all_suffixes(self):
        cache = _fake_cache()
        with _patch_cache(cache):
            await _cache_invalidate("75")
        deleted = {c.args[0] for c in cache.delete.await_args_list}
        assert "relations:75:graph" in deleted
        assert "relations:75:coverage" in deleted
        assert "relations:75:gaps" in deleted
        assert "relations:all:graph" in deleted

    @pytest.mark.asyncio
    async def test_cache_invalidate_swallows_exception(self):
        with _patch_cache_raises():
            await _cache_invalidate("75")


# ---------------------------------------------------------------------------
# Fakes for registries
# ---------------------------------------------------------------------------
def _make_extractor(actors=None, relations=None, raises=False):
    class _Fake:
        async def extract(self, department_code):
            if raises:
                raise RuntimeError("extractor boom")
            return {"actors": actors or [], "relations": relations or []}

    return _Fake


def _make_inferrer(actors=None, relations=None, raises=False):
    class _Fake:
        async def infer(self, department_code):
            if raises:
                raise RuntimeError("inferrer boom")
            return {"actors": actors or [], "relations": relations or []}

    return _Fake


def _make_predictor(actors=None, relations=None, raises=False):
    class _Fake:
        async def predict(self, department_code):
            if raises:
                raise RuntimeError("predictor boom")
            return {"actors": actors or [], "relations": relations or []}

    return _Fake


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------
class TestDiscover:
    @pytest.fixture
    def service(self):
        return RelationService()

    @pytest.mark.asyncio
    async def test_default_sources_appends_nature_juridique_implicitly(self, service):
        # With sources=None the default list already contains nature_juridique.
        captured = {}

        async def _fake_snapshot(dept, result):
            captured["snapshot"] = (dept, result)

        # No extractors/inferrers/predictors registered -> nothing persisted,
        # but the orchestration still completes and returns the summary.
        conn = _make_conn()
        with _patch_acquire(conn), patch.dict(
            f"{MODULE}.EXTRACTORS", {}, clear=True
        ), patch.dict(f"{MODULE}.INFERRERS", {}, clear=True), patch.dict(
            f"{MODULE}.PREDICTORS", {}, clear=True
        ), patch(
            "src.application.services.network_analytics_service.save_snapshot",
            new=AsyncMock(side_effect=_fake_snapshot),
        ), _patch_cache(_fake_cache()):
            result = await service.discover("75")

        assert result["department_code"] == "75"
        assert "nature_juridique" in result["sources_run"]
        assert result["actors_upserted"] == 0
        assert result["relations_upserted"] == 0
        assert result["inferrers_run"] == []
        assert result["predictors_run"] == []
        assert captured["snapshot"][0] == "75"

    @pytest.mark.asyncio
    async def test_custom_sources_auto_appends_nature_juridique(self, service):
        conn = _make_conn()
        with _patch_acquire(conn), patch.dict(
            f"{MODULE}.EXTRACTORS", {}, clear=True
        ), patch.dict(f"{MODULE}.INFERRERS", {}, clear=True), patch.dict(
            f"{MODULE}.PREDICTORS", {}, clear=True
        ), patch(
            "src.application.services.network_analytics_service.save_snapshot",
            new=AsyncMock(),
        ), _patch_cache(_fake_cache()):
            result = await service.discover("75", sources=["sirene"])

        assert result["sources_run"] == ["sirene", "nature_juridique"]

    @pytest.mark.asyncio
    async def test_custom_sources_keeps_explicit_nature_juridique(self, service):
        conn = _make_conn()
        with _patch_acquire(conn), patch.dict(
            f"{MODULE}.EXTRACTORS", {}, clear=True
        ), patch.dict(f"{MODULE}.INFERRERS", {}, clear=True), patch.dict(
            f"{MODULE}.PREDICTORS", {}, clear=True
        ), patch(
            "src.application.services.network_analytics_service.save_snapshot",
            new=AsyncMock(),
        ), _patch_cache(_fake_cache()):
            result = await service.discover("75", sources=["sirene", "nature_juridique"])

        # Not appended twice
        assert result["sources_run"].count("nature_juridique") == 1

    @pytest.mark.asyncio
    async def test_unknown_source_warned_and_skipped(self, service):
        conn = _make_conn()
        with _patch_acquire(conn), patch.dict(
            f"{MODULE}.EXTRACTORS", {}, clear=True
        ), patch.dict(f"{MODULE}.INFERRERS", {}, clear=True), patch.dict(
            f"{MODULE}.PREDICTORS", {}, clear=True
        ), patch(
            "src.application.services.network_analytics_service.save_snapshot",
            new=AsyncMock(),
        ), _patch_cache(_fake_cache()):
            result = await service.discover("75", sources=["totally_unknown_source"])

        assert result["actors_upserted"] == 0

    @pytest.mark.asyncio
    async def test_full_pipeline_persists_all_levels(self, service):
        actor = {
            "id": str(uuid.uuid4()),
            "type": "enterprise",
            "external_id": "SIREN:1",
            "name": "Acme",
            "department_code": "75",
            "metadata": {},
        }
        rel = {
            "id": str(uuid.uuid4()),
            "source_actor_external_id": "SIREN:1",
            "target_actor_external_id": "DEPT:75",
            "relation_type": "structural",
            "subtype": "headquarter_in",
            "confidence": 0.95,
        }
        # _upsert_relations does conn.fetch for ext->uuid mapping; provide BOTH
        # endpoints so the relation is not skipped as "actor not found".
        mapping_rows = [
            _arow(id=uuid.UUID(actor["id"]), external_id="SIREN:1"),
            _arow(id=uuid.uuid4(), external_id="DEPT:75"),
        ]

        # Pre-persist conn, post-persist conn, L2 conn, L3 conn.
        # Each _upsert_relations call does a fetch; _upsert_actors uses execute.
        c_pre = _make_conn(fetch=mapping_rows)
        c_post = _make_conn(fetch=mapping_rows)
        c_l2 = _make_conn(fetch=mapping_rows)
        c_l3 = _make_conn(fetch=mapping_rows)

        extractors = {
            "sirene": _make_extractor(actors=[actor], relations=[rel]),
            "nature_juridique": _make_extractor(actors=[actor], relations=[]),
        }
        inferrers = {"concentration": _make_inferrer(actors=[], relations=[rel])}
        predictors = {"cascade": _make_predictor(actors=[], relations=[rel])}

        with _patch_acquire_factory([c_pre, c_post, c_l2, c_l3]), patch.dict(
            f"{MODULE}.EXTRACTORS", extractors, clear=True
        ), patch.dict(f"{MODULE}.INFERRERS", inferrers, clear=True), patch.dict(
            f"{MODULE}.PREDICTORS", predictors, clear=True
        ), patch(
            "src.application.services.network_analytics_service.save_snapshot",
            new=AsyncMock(),
        ), _patch_cache(_fake_cache()):
            result = await service.discover("75", sources=["sirene", "nature_juridique"])

        assert result["inferrers_run"] == ["concentration"]
        assert result["predictors_run"] == ["cascade"]
        assert result["l1_relations"] == 1
        assert result["l2_relations"] == 1
        assert result["l3_relations"] == 1
        # L1 actors: 1 pre + 1 post = 2 ; L2 / L3 actors: 0
        assert result["actors_upserted"] == 2
        assert result["relations_upserted"] == 3

    @pytest.mark.asyncio
    async def test_post_persist_extractor_empty_skips_persist(self, service):
        # A post-persist extractor (nature_juridique) returning no actors and
        # no relations must not open a DB connection for persistence
        # (covers the `if post_actors or post_relations` false branch).
        conn = _make_conn()
        extractors = {
            "nature_juridique": _make_extractor(actors=[], relations=[]),
        }
        with _patch_acquire(conn), patch.dict(
            f"{MODULE}.EXTRACTORS", extractors, clear=True
        ), patch.dict(f"{MODULE}.INFERRERS", {}, clear=True), patch.dict(
            f"{MODULE}.PREDICTORS", {}, clear=True
        ), patch(
            "src.application.services.network_analytics_service.save_snapshot",
            new=AsyncMock(),
        ), _patch_cache(_fake_cache()):
            result = await service.discover("75", sources=["nature_juridique"])
        assert result["actors_upserted"] == 0
        # No persistence connection was opened (no execute calls)
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_extractor_exception_is_swallowed(self, service):
        conn = _make_conn()
        extractors = {
            "sirene": _make_extractor(raises=True),
            "nature_juridique": _make_extractor(raises=True),
        }
        with _patch_acquire(conn), patch.dict(
            f"{MODULE}.EXTRACTORS", extractors, clear=True
        ), patch.dict(f"{MODULE}.INFERRERS", {}, clear=True), patch.dict(
            f"{MODULE}.PREDICTORS", {}, clear=True
        ), patch(
            "src.application.services.network_analytics_service.save_snapshot",
            new=AsyncMock(),
        ), _patch_cache(_fake_cache()):
            result = await service.discover("75", sources=["sirene", "nature_juridique"])

        assert result["actors_upserted"] == 0

    @pytest.mark.asyncio
    async def test_inferrer_and_predictor_exceptions_swallowed(self, service):
        conn = _make_conn()
        inferrers = {"bad": _make_inferrer(raises=True)}
        predictors = {"bad": _make_predictor(raises=True)}
        with _patch_acquire(conn), patch.dict(
            f"{MODULE}.EXTRACTORS", {}, clear=True
        ), patch.dict(f"{MODULE}.INFERRERS", inferrers, clear=True), patch.dict(
            f"{MODULE}.PREDICTORS", predictors, clear=True
        ), patch(
            "src.application.services.network_analytics_service.save_snapshot",
            new=AsyncMock(),
        ), _patch_cache(_fake_cache()):
            result = await service.discover("75", sources=["sirene"])

        # Failed inferrer/predictor are not recorded in *_run lists
        assert result["inferrers_run"] == []
        assert result["predictors_run"] == []

    @pytest.mark.asyncio
    async def test_snapshot_failure_swallowed(self, service):
        conn = _make_conn()
        with _patch_acquire(conn), patch.dict(
            f"{MODULE}.EXTRACTORS", {}, clear=True
        ), patch.dict(f"{MODULE}.INFERRERS", {}, clear=True), patch.dict(
            f"{MODULE}.PREDICTORS", {}, clear=True
        ), patch(
            "src.application.services.network_analytics_service.save_snapshot",
            new=AsyncMock(side_effect=RuntimeError("snapshot boom")),
        ), _patch_cache(_fake_cache()):
            # Should still return normally
            result = await service.discover("75", sources=["sirene"])
        assert result["department_code"] == "75"

    @pytest.mark.asyncio
    async def test_cache_invalidated_after_discover(self, service):
        conn = _make_conn()
        cache = _fake_cache()
        with _patch_acquire(conn), patch.dict(
            f"{MODULE}.EXTRACTORS", {}, clear=True
        ), patch.dict(f"{MODULE}.INFERRERS", {}, clear=True), patch.dict(
            f"{MODULE}.PREDICTORS", {}, clear=True
        ), patch(
            "src.application.services.network_analytics_service.save_snapshot",
            new=AsyncMock(),
        ), _patch_cache(cache):
            await service.discover("75", sources=["sirene"])
        # _cache_invalidate issues at least one delete
        assert cache.delete.await_count >= 1


# ---------------------------------------------------------------------------
# get_graph
# ---------------------------------------------------------------------------
class TestGetGraph:
    @pytest.fixture
    def service(self):
        return RelationService()

    @pytest.mark.asyncio
    async def test_empty_actor_set_returns_empty_payload(self, service):
        conn = _make_conn(fetch=[])  # no actors
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_graph("75")
        assert result == {
            "nodes": [],
            "links": [],
            "total_actors": 0,
            "total_relations": 0,
        }

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self, service):
        cached = {"nodes": [], "links": [], "total_actors": 0, "total_relations": 0}
        cache = _fake_cache(get_return=cached)
        # acquire_conn must NOT be touched on a cache hit
        with patch(f"{MODULE}.acquire_conn", side_effect=AssertionError("DB hit!")), _patch_cache(
            cache
        ):
            result = await service.get_graph("75")
        assert result is cached

    @pytest.mark.asyncio
    async def test_dept_scoped_graph_builds_nodes_and_links(self, service):
        a1 = uuid.uuid4()
        a2 = uuid.uuid4()
        actor_rows = [
            _arow(id=a1, type="enterprise", external_id="SIREN:1", name="Acme",
                  department_code="75", metadata={"naf": "62"}),
            _arow(id=a2, type="territory", external_id="DEPT:75", name="Paris",
                  department_code="75", metadata={}),
        ]
        relation_rows = [
            _arow(id=uuid.uuid4(), source_actor_id=a1, target_actor_id=a2,
                  relation_type="structural", subtype="headquarter_in",
                  confidence=0.95, weight=1.0),
        ]
        # fetch order in get_graph: 1) actor_rows, 2) relation_rows
        conn = _make_conn(fetch_seq=[actor_rows, relation_rows], fetchval=1)
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_graph("75")

        assert result["total_actors"] == 2
        assert result["total_relations"] == 1
        assert result["total_relations_unfiltered"] == 1
        node_types = {n["type"] for n in result["nodes"]}
        assert node_types == {"enterprise", "territory"}
        # node size from _NODE_SIZE
        ent = next(n for n in result["nodes"] if n["type"] == "enterprise")
        assert ent["size"] == 10.0
        assert ent["metadata"] == {"naf": "62"}

    @pytest.mark.asyncio
    async def test_isolated_nodes_pruned(self, service):
        a1 = uuid.uuid4()
        a2 = uuid.uuid4()
        a3 = uuid.uuid4()  # isolated, no relations
        actor_rows = [
            _arow(id=a1, type="enterprise", external_id="E1", name="A",
                  department_code="75", metadata={}),
            _arow(id=a2, type="territory", external_id="DEPT:75", name="Paris",
                  department_code="75", metadata={}),
            _arow(id=a3, type="enterprise", external_id="E3", name="Orphan",
                  department_code="75", metadata={}),
        ]
        relation_rows = [
            _arow(id=uuid.uuid4(), source_actor_id=a1, target_actor_id=a2,
                  relation_type="structural", subtype="hq", confidence=0.9, weight=None),
        ]
        conn = _make_conn(fetch_seq=[actor_rows, relation_rows], fetchval=1)
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_graph("75")

        labels = {n["label"] for n in result["nodes"]}
        assert "Orphan" not in labels
        assert result["total_actors"] == 2
        # weight None coerced to 1.0
        assert result["links"][0]["weight"] == 1.0

    @pytest.mark.asyncio
    async def test_cross_department_view_uses_all_actors_query(self, service):
        a1 = uuid.uuid4()
        a2 = uuid.uuid4()
        actor_rows = [
            _arow(id=a1, type="enterprise", external_id="E1", name="A",
                  department_code="75", metadata={}),
            _arow(id=a2, type="enterprise", external_id="E2", name="B",
                  department_code="92", metadata=None),  # metadata not a dict -> {}
        ]
        relation_rows = [
            _arow(id=uuid.uuid4(), source_actor_id=a1, target_actor_id=a2,
                  relation_type="inferred", subtype="link", confidence=0.6, weight=2.0),
        ]
        conn = _make_conn(fetch_seq=[actor_rows, relation_rows], fetchval=1)
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_graph(None)

        assert result["total_actors"] == 2
        b = next(n for n in result["nodes"] if n["label"] == "B")
        assert b["metadata"] == {}

    @pytest.mark.asyncio
    async def test_actor_types_filter_skips_cache(self, service):
        a1 = uuid.uuid4()
        actor_rows = [
            _arow(id=a1, type="institution", external_id="I1", name="Inst",
                  department_code="75", metadata={}),
        ]
        # actor_types set -> cache_key is None -> no _cache_get call; one isolated
        # actor with no relations -> pruned -> empty nodes.
        conn = _make_conn(fetch_seq=[actor_rows, []], fetchval=0)
        cache = _fake_cache(get_return={"should": "not be used"})
        with _patch_acquire(conn), _patch_cache(cache):
            result = await service.get_graph("75", actor_types=["institution"])

        cache.get.assert_not_awaited()
        assert result["total_actors"] == 0

    @pytest.mark.asyncio
    async def test_cross_department_with_actor_types(self, service):
        a1 = uuid.uuid4()
        a2 = uuid.uuid4()
        actor_rows = [
            _arow(id=a1, type="financial", external_id="F1", name="Bank",
                  department_code="75", metadata={}),
            _arow(id=a2, type="financial", external_id="F2", name="Bank2",
                  department_code="92", metadata={}),
        ]
        relation_rows = [
            _arow(id=uuid.uuid4(), source_actor_id=a1, target_actor_id=a2,
                  relation_type="inferred", subtype="x", confidence=0.7, weight=1.0),
        ]
        conn = _make_conn(fetch_seq=[actor_rows, relation_rows], fetchval=1)
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_graph(None, actor_types=["financial"])
        assert result["total_actors"] == 2


# ---------------------------------------------------------------------------
# get_coverage
# ---------------------------------------------------------------------------
class TestGetCoverage:
    @pytest.fixture
    def service(self):
        return RelationService()

    @pytest.mark.asyncio
    async def test_cache_hit(self, service):
        cached = {"total_relations": 99}
        cache = _fake_cache(get_return=cached)
        with patch(f"{MODULE}.acquire_conn", side_effect=AssertionError("DB hit!")), _patch_cache(
            cache
        ):
            result = await service.get_coverage("75")
        assert result is cached

    @pytest.mark.asyncio
    async def test_empty_relations_zero_score(self, service):
        conn = _make_conn(fetch=[])
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_coverage("75")
        assert result["total_relations"] == 0
        assert result["coverage_score"] == 0.0
        assert result["structural_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_weighted_coverage_score_and_pct(self, service):
        rows = [
            _arow(rtype="structural", cnt=5),
            _arow(rtype="inferred", cnt=3),
            _arow(rtype="hypothetical", cnt=2),
        ]
        conn = _make_conn(fetch=rows)
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_coverage("75")

        assert result["total_relations"] == 10
        assert result["structural_count"] == 5
        assert result["inferred_count"] == 3
        assert result["hypothetical_count"] == 2
        assert result["structural_pct"] == 50.0
        assert result["inferred_pct"] == 30.0
        assert result["hypothetical_pct"] == 20.0
        # (5*1.0 + 3*0.6 + 2*0.2) / 10 = (5 + 1.8 + 0.4)/10 = 0.72
        assert result["coverage_score"] == 0.72

    @pytest.mark.asyncio
    async def test_missing_types_default_to_zero(self, service):
        rows = [_arow(rtype="structural", cnt=4)]
        conn = _make_conn(fetch=rows)
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_coverage("75")
        assert result["inferred_count"] == 0
        assert result["hypothetical_count"] == 0
        assert result["coverage_score"] == 1.0


# ---------------------------------------------------------------------------
# get_gaps
# ---------------------------------------------------------------------------
class TestGetGaps:
    @pytest.fixture
    def service(self):
        return RelationService()

    @pytest.mark.asyncio
    async def test_cache_hit(self, service):
        cached = {"total_gaps": 7}
        cache = _fake_cache(get_return=cached)
        with patch(f"{MODULE}.acquire_conn", side_effect=AssertionError("DB hit!")), _patch_cache(
            cache
        ):
            result = await service.get_gaps("75")
        assert result is cached

    @pytest.mark.asyncio
    async def test_no_enterprises_minimal_gaps(self, service):
        # total_enterprises = 0 -> most gaps gated off. The fetchval order
        # mirrors the code path. With zero enterprises only l3/l2 "missing"
        # gaps that don't require enterprises can appear.
        # fetchval call order in get_gaps:
        #  1 total_enterprises, 2 total_institutions, 3 no_institution,
        #  4 supply_chain_count, 5 no_directors, 6 l3_count, 7 no_sector,
        #  8 no_employment, 9 l2_count, 10 stale_count
        fetchvals = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        # _build_honesty_table does conn.fetch -> return empty
        conn = _make_conn(fetch=[], fetchval_seq=fetchvals)
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_gaps("75")

        gap_types = [g["gap_type"] for g in result["gaps"]]
        # Gap 4 (l3 missing_model) fires regardless of enterprise count
        assert "missing_model" in gap_types
        assert result["department_code"] == "75"
        assert result["capability_matrix"] is CAPABILITY_MATRIX
        assert result["algorithmic_honesty"] == []
        assert result["total_gaps"] == len(result["gaps"])

    @pytest.mark.asyncio
    async def test_all_gap_branches_when_data_missing(self, service):
        # 100 enterprises, institutions present, everything else missing/zero
        #  1 total_enterprises = 100
        #  2 total_institutions = 5
        #  3 no_institution = 100  -> Gap1 partial_coverage (+inst note)
        #  4 supply_chain_count = 0 -> Gap2 missing_source
        #  5 no_directors = 100 -> Gap3 missing_source
        #  6 l3_count = 0 -> Gap4 missing_model
        #  7 no_sector = 100 -> Gap5 low_coverage
        #  8 no_employment = 100 -> Gap6 low_coverage
        #  9 l2_count = 0 -> Gap7 missing_model
        # 10 stale_count = 10 -> Gap8 stale_data
        fetchvals = [100, 5, 100, 0, 100, 0, 100, 100, 0, 10]
        conn = _make_conn(fetch=[], fetchval_seq=fetchvals)
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_gaps("75")

        gap_types = [g["gap_type"] for g in result["gaps"]]
        assert "partial_coverage" in gap_types  # Gap1
        assert "missing_source" in gap_types  # Gap2/Gap3
        assert "missing_model" in gap_types  # Gap4/Gap7
        assert "low_coverage" in gap_types  # Gap5/Gap6
        assert "stale_data" in gap_types  # Gap8
        # Gap1 description includes the institution note
        gap1 = next(g for g in result["gaps"] if g["gap_type"] == "partial_coverage")
        assert "5 institutions" in gap1["description"]

    @pytest.mark.asyncio
    async def test_gap1_without_institution_note(self, service):
        # no_institution > 0 but total_institutions == 0 -> Gap1 fires with NO
        # institution note (covers the inner `if total_institutions` false branch).
        #  1 total_enterprises = 40
        #  2 total_institutions = 0
        #  3 no_institution = 40 -> Gap1, no note
        # rest zero -> only Gap4 (l3 missing) also fires
        fetchvals = [40, 0, 40, 0, 0, 0, 0, 0, 0, 0]
        conn = _make_conn(fetch=[], fetchval_seq=fetchvals)
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_gaps("75")
        gap1 = next(g for g in result["gaps"] if g["gap_type"] == "partial_coverage")
        assert "institutions detectees" not in gap1["description"]
        assert "40/40 entreprises" in gap1["description"]

    @pytest.mark.asyncio
    async def test_present_data_branches(self, service):
        # All "present" branches: supply chain, l3, l2 non-zero.
        #  1 total_enterprises = 50
        #  2 total_institutions = 0  -> no inst note
        #  3 no_institution = 0  -> Gap1 NOT fired
        #  4 supply_chain_count = 7 -> Gap2 partial_coverage (else branch)
        #  5 no_directors = 0  -> Gap3 not fired
        #  6 l3_count = 3 -> Gap4 model_limitation (else branch)
        #  7 no_sector = 0 -> Gap5 not fired
        #  8 no_employment = 0 -> Gap6 not fired
        #  9 l2_count = 4 -> Gap7 not fired (l2 present)
        # 10 stale_count = 0 -> Gap8 not fired
        fetchvals = [50, 0, 0, 7, 0, 3, 0, 0, 4, 0]
        conn = _make_conn(fetch=[], fetchval_seq=fetchvals)
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_gaps("75")

        gap_types = [g["gap_type"] for g in result["gaps"]]
        assert "model_limitation" in gap_types  # Gap4 else
        # Gap2 else branch -> partial_coverage
        assert "partial_coverage" in gap_types
        # No missing_source since directors present & supply chain present
        assert "missing_source" not in gap_types

    @pytest.mark.asyncio
    async def test_honesty_table_built_from_subtypes(self, service):
        # get_gaps -> _build_honesty_table issues a conn.fetch (the last fetch).
        # All fetchvals zero so no gaps depend on them beyond Gap4.
        honesty_rows = [
            _arow(subtype="headquarter_in", rtype="structural", cnt=10,
                  avg_confidence=0.95, min_confidence=0.9, max_confidence=1.0),
            _arow(subtype="totally_unknown_subtype", rtype="inferred", cnt=2,
                  avg_confidence=0.5, min_confidence=0.4, max_confidence=0.6),
        ]
        fetchvals = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        conn = _make_conn(fetch=honesty_rows, fetchval_seq=fetchvals)
        with _patch_acquire(conn), _patch_cache(_fake_cache(get_return=None)):
            result = await service.get_gaps("75")

        honesty = result["algorithmic_honesty"]
        assert len(honesty) == 2
        known = next(h for h in honesty if h["relation_subtype"] == "headquarter_in")
        assert known["method"] != "Non documente"
        assert known["count"] == 10
        assert known["avg_confidence"] == 0.95
        unknown = next(h for h in honesty if h["relation_subtype"] == "totally_unknown_subtype")
        assert unknown["method"] == "Non documente"
        assert unknown["data_source"] == "Inconnu"


# ---------------------------------------------------------------------------
# _upsert_actors
# ---------------------------------------------------------------------------
class TestUpsertActors:
    @pytest.fixture
    def service(self):
        return RelationService()

    @pytest.mark.asyncio
    async def test_empty_returns_zero(self, service):
        conn = _make_conn()
        assert await service._upsert_actors(conn, []) == 0
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dedupe_by_external_id_keeps_last(self, service):
        conn = _make_conn()
        actors = [
            {"id": str(uuid.uuid4()), "type": "enterprise", "external_id": "E1",
             "name": "First", "department_code": "75", "metadata": {}},
            {"id": str(uuid.uuid4()), "type": "enterprise", "external_id": "E1",
             "name": "Second", "department_code": "75", "metadata": {"x": 1}},
        ]
        count = await service._upsert_actors(conn, actors)
        # Deduplicated to a single external_id
        assert count == 1
        assert conn.execute.await_count == 1
        # The last actor (Second) is the one upserted
        args = conn.execute.await_args.args
        assert "Second" in args

    @pytest.mark.asyncio
    async def test_metadata_serialized_to_json(self, service):
        conn = _make_conn()
        actors = [
            {"id": str(uuid.uuid4()), "type": "enterprise", "external_id": "E1",
             "name": "A", "department_code": "75", "metadata": {"naf": "62"}},
        ]
        await service._upsert_actors(conn, actors)
        args = conn.execute.await_args.args
        # The metadata json string must be present among args
        assert any(isinstance(a, str) and '"naf"' in a for a in args)

    @pytest.mark.asyncio
    async def test_missing_metadata_defaults_to_empty_json(self, service):
        conn = _make_conn()
        actors = [
            {"id": str(uuid.uuid4()), "type": "enterprise", "external_id": "E1",
             "name": "A", "department_code": "75"},  # no metadata key
        ]
        count = await service._upsert_actors(conn, actors)
        assert count == 1
        args = conn.execute.await_args.args
        assert "{}" in args

    @pytest.mark.asyncio
    async def test_per_row_error_is_swallowed(self, service):
        conn = _make_conn()
        conn.execute = AsyncMock(side_effect=RuntimeError("db error"))
        actors = [
            {"id": str(uuid.uuid4()), "type": "enterprise", "external_id": "E1",
             "name": "A", "department_code": "75", "metadata": {}},
        ]
        # Should not raise; count stays 0
        count = await service._upsert_actors(conn, actors)
        assert count == 0


# ---------------------------------------------------------------------------
# _upsert_relations
# ---------------------------------------------------------------------------
class TestUpsertRelations:
    @pytest.fixture
    def service(self):
        return RelationService()

    @pytest.mark.asyncio
    async def test_empty_returns_zero(self, service):
        conn = _make_conn()
        assert await service._upsert_relations(conn, []) == 0

    @pytest.mark.asyncio
    async def test_resolves_ext_ids_and_upserts(self, service):
        src = uuid.uuid4()
        tgt = uuid.uuid4()
        mapping = [
            _arow(id=src, external_id="SIREN:1"),
            _arow(id=tgt, external_id="DEPT:75"),
        ]
        conn = _make_conn(fetch=mapping)
        rels = [
            {"id": str(uuid.uuid4()), "source_actor_external_id": "SIREN:1",
             "target_actor_external_id": "DEPT:75", "relation_type": "structural",
             "subtype": "headquarter_in", "confidence": 0.95, "weight": 1.0,
             "evidence": {"foo": "bar"}, "source_type": "sirene", "source_ref": "ref"},
        ]
        count = await service._upsert_relations(conn, rels)
        assert count == 1
        # Two executes: the relation insert + the relation_sources insert
        assert conn.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_skips_relation_with_missing_actor(self, service):
        # mapping only resolves the source, target unknown -> skipped
        src = uuid.uuid4()
        mapping = [_arow(id=src, external_id="SIREN:1")]
        conn = _make_conn(fetch=mapping)
        rels = [
            {"id": str(uuid.uuid4()), "source_actor_external_id": "SIREN:1",
             "target_actor_external_id": "DEPT:UNKNOWN", "relation_type": "structural",
             "subtype": "headquarter_in", "confidence": 0.95},
        ]
        count = await service._upsert_relations(conn, rels)
        assert count == 0
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_error_during_upsert_swallowed(self, service):
        src = uuid.uuid4()
        tgt = uuid.uuid4()
        mapping = [
            _arow(id=src, external_id="A"),
            _arow(id=tgt, external_id="B"),
        ]
        conn = _make_conn(fetch=mapping)
        conn.execute = AsyncMock(side_effect=RuntimeError("insert failed"))
        rels = [
            {"id": str(uuid.uuid4()), "source_actor_external_id": "A",
             "target_actor_external_id": "B", "relation_type": "inferred",
             "subtype": "x", "confidence": 0.6},
        ]
        count = await service._upsert_relations(conn, rels)
        assert count == 0

    @pytest.mark.asyncio
    async def test_defaults_weight_and_evidence(self, service):
        src = uuid.uuid4()
        tgt = uuid.uuid4()
        mapping = [
            _arow(id=src, external_id="A"),
            _arow(id=tgt, external_id="B"),
        ]
        conn = _make_conn(fetch=mapping)
        rels = [
            {"id": str(uuid.uuid4()), "source_actor_external_id": "A",
             "target_actor_external_id": "B", "relation_type": "inferred",
             "subtype": "x", "confidence": 0.6},  # no weight / evidence / source_*
        ]
        count = await service._upsert_relations(conn, rels)
        assert count == 1


# ---------------------------------------------------------------------------
# _to_graphml
# ---------------------------------------------------------------------------
class TestToGraphml:
    @pytest.fixture
    def service(self):
        return RelationService()

    def test_graphml_contains_nodes_and_edges(self, service):
        graph = {
            "nodes": [
                {"id": "n1", "label": "Acme", "type": "enterprise",
                 "external_id": "E1", "department_code": "75", "size": 10.0},
                {"id": "n2", "label": "Paris", "type": "territory",
                 "external_id": "DEPT:75", "department_code": None, "size": 25.0},
            ],
            "links": [
                {"source": "n1", "target": "n2", "relation_type": "structural",
                 "subtype": "hq", "confidence": 0.95, "weight": 1.0},
            ],
        }
        xml = service._to_graphml(graph)
        assert isinstance(xml, str)
        assert "<graphml" in xml
        assert "Acme" in xml
        assert "Paris" in xml
        assert 'source="n1"' in xml
        assert 'target="n2"' in xml

    def test_graphml_empty_graph(self, service):
        xml = service._to_graphml({"nodes": [], "links": []})
        assert "<graph" in xml

    def test_graphml_none_department_code_rendered_empty(self, service):
        graph = {
            "nodes": [
                {"id": "n1", "label": "X", "type": "enterprise",
                 "external_id": "E1", "department_code": None, "size": 10.0},
            ],
            "links": [],
        }
        xml = service._to_graphml(graph)
        assert "<node" in xml


# ---------------------------------------------------------------------------
# export_graph
# ---------------------------------------------------------------------------
class TestExportGraph:
    @pytest.fixture
    def service(self):
        return RelationService()

    @pytest.mark.asyncio
    async def test_json_export_merges_graph_and_coverage(self, service):
        graph = {"nodes": [], "links": [], "total_actors": 0, "total_relations": 0}
        coverage = {"total_relations": 0, "coverage_score": 0.0}
        with patch.object(service, "get_graph", new=AsyncMock(return_value=graph)), patch.object(
            service, "get_coverage", new=AsyncMock(return_value=coverage)
        ):
            result = await service.export_graph("75", fmt="json")
        assert result["format"] == "json"
        assert result["department_code"] == "75"
        assert result["coverage"] == coverage
        assert "nodes" in result

    @pytest.mark.asyncio
    async def test_csv_export_flattens_rows(self, service):
        graph = {
            "nodes": [
                {"id": "n1", "label": "Acme", "type": "enterprise",
                 "external_id": "E1", "department_code": "75"},
                {"id": "n2", "label": "Paris", "type": "territory",
                 "external_id": "DEPT:75", "department_code": "75"},
            ],
            "links": [
                {"source": "n1", "target": "n2", "relation_type": "structural",
                 "subtype": "hq", "confidence": 0.95, "weight": 1.0},
            ],
            "total_actors": 2,
            "total_relations": 1,
        }
        coverage = {"total_relations": 1}
        with patch.object(service, "get_graph", new=AsyncMock(return_value=graph)), patch.object(
            service, "get_coverage", new=AsyncMock(return_value=coverage)
        ):
            result = await service.export_graph("75", fmt="csv")
        assert result["format"] == "csv"
        assert len(result["actors"]) == 2
        assert len(result["relations"]) == 1
        rel = result["relations"][0]
        assert rel["source_label"] == "Acme"
        assert rel["target_label"] == "Paris"

    @pytest.mark.asyncio
    async def test_graphml_export(self, service):
        graph = {
            "nodes": [
                {"id": "n1", "label": "Acme", "type": "enterprise",
                 "external_id": "E1", "department_code": "75", "size": 10.0},
            ],
            "links": [],
            "total_actors": 1,
            "total_relations": 0,
        }
        with patch.object(service, "get_graph", new=AsyncMock(return_value=graph)), patch.object(
            service, "get_coverage", new=AsyncMock(return_value={})
        ):
            result = await service.export_graph("75", fmt="graphml")
        assert isinstance(result, str)
        assert "<graphml" in result


# ---------------------------------------------------------------------------
# whatif
# ---------------------------------------------------------------------------
class TestWhatif:
    @pytest.fixture
    def service(self):
        return RelationService()

    @pytest.mark.asyncio
    async def test_delegates_to_simulate_whatif(self, service):
        fake = AsyncMock(return_value={"total_impact_score": 1.0})
        with patch(f"{MODULE}.simulate_whatif", new=fake):
            result = await service.whatif("SIREN:1", "75", max_depth=2)
        assert result == {"total_impact_score": 1.0}
        fake.assert_awaited_once_with("SIREN:1", "75", 2)

    @pytest.mark.asyncio
    async def test_default_max_depth(self, service):
        fake = AsyncMock(return_value={})
        with patch(f"{MODULE}.simulate_whatif", new=fake):
            await service.whatif("SIREN:1", "75")
        fake.assert_awaited_once_with("SIREN:1", "75", 3)


# ---------------------------------------------------------------------------
# Sanity: the module imports the expected registries
# ---------------------------------------------------------------------------
class TestModuleWiring:
    def test_registries_are_dicts(self):
        assert isinstance(rs.EXTRACTORS, dict)
        assert isinstance(rs.INFERRERS, dict)
        assert isinstance(rs.PREDICTORS, dict)
