"""Unit tests for relation_predictors (issue #161, batch 4 coverage).

Target module: src/application/services/relation_predictors.py

The production code is the source of truth. These tests assert its *real*
behaviour, in memory, with DB access (``acquire_conn``) and the cascade ML
model (``predict_cascade_probability``) mocked via ``unittest.mock``.

L3 predictors are *hypothetical*: every emitted relation must carry
``relation_type == "hypothetical"``, ``source_type == "model"`` and a
confidence clamped into the L3 band ``[0.05, 0.39]``.

Coverage:
- pure helpers (_stable_uuid / _actor_id / _relation_id / _estimate_headcount)
- module constants (_TRANCHE_EFFECTIF / _INSTITUTIONS)
- the abstract base BasePredictor (cannot be instantiated; subclasses must
  implement ``predict``)
- the CONCRETE predictors CascadePredictor / TerritorialImpactPredictor /
  InstitutionalLinkPredictor (DB mocked)
- the PREDICTORS registry
- simulate_whatif (DB + cascade model mocked)
"""

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.relation_predictors import (
    PREDICTORS,
    BasePredictor,
    CascadePredictor,
    InstitutionalLinkPredictor,
    TerritorialImpactPredictor,
    _actor_id,
    _estimate_headcount,
    _INSTITUTIONS,
    _relation_id,
    _stable_uuid,
    _TRANCHE_EFFECTIF,
    simulate_whatif,
)

MODULE = "src.application.services.relation_predictors"


# ---------------------------------------------------------------------------
# Mocking helpers
# ---------------------------------------------------------------------------
def _patch_conn(fetch_side_effect=None, fetchval=0, fetchrow=None):
    """Patch ``acquire_conn`` with a connection whose methods are AsyncMocks.

    ``fetch_side_effect`` is a list of return values consumed in call order
    (one per ``conn.fetch(...)`` call), or a single list applied to every call.
    """
    mock_conn = MagicMock()

    if isinstance(fetch_side_effect, list) and fetch_side_effect and isinstance(
        fetch_side_effect[0], list
    ):
        mock_conn.fetch = AsyncMock(side_effect=fetch_side_effect)
    else:
        mock_conn.fetch = AsyncMock(return_value=fetch_side_effect or [])

    mock_conn.fetchval = AsyncMock(return_value=fetchval)
    mock_conn.fetchrow = AsyncMock(return_value=fetchrow)

    @asynccontextmanager
    async def _ctx():
        yield mock_conn

    return patch(f"{MODULE}.acquire_conn", _ctx)


# ===========================================================================
# Pure helpers
# ===========================================================================
class TestStableUuid:
    """_stable_uuid: deterministic uuid5 from prefix + key."""

    def test_returns_uuid(self):
        assert isinstance(_stable_uuid("relation", "k"), uuid.UUID)

    def test_deterministic(self):
        assert _stable_uuid("relation", "a->b:x") == _stable_uuid("relation", "a->b:x")

    def test_prefix_matters(self):
        assert _stable_uuid("actor", "k") != _stable_uuid("relation", "k")

    def test_key_matters(self):
        assert _stable_uuid("actor", "k1") != _stable_uuid("actor", "k2")

    def test_version_5(self):
        assert _stable_uuid("a", "b").version == 5


class TestActorId:
    """_actor_id: actor UUID == _stable_uuid('actor', '<type>:<ext>')."""

    def test_matches_stable_uuid(self):
        assert _actor_id("institution", "INST:CCI:75") == _stable_uuid(
            "actor", "institution:INST:CCI:75"
        )

    def test_deterministic(self):
        assert _actor_id("institution", "X") == _actor_id("institution", "X")

    def test_type_matters(self):
        assert _actor_id("institution", "X") != _actor_id("enterprise", "X")


class TestRelationId:
    """_relation_id: relation UUID == _stable_uuid('relation', 'A->B:subtype')."""

    def test_matches_stable_uuid(self):
        assert _relation_id("A", "B", "cascade_risk") == _stable_uuid(
            "relation", "A->B:cascade_risk"
        )

    def test_direction_matters(self):
        assert _relation_id("A", "B", "x") != _relation_id("B", "A", "x")

    def test_subtype_matters(self):
        assert _relation_id("A", "B", "x") != _relation_id("A", "B", "y")


class TestEstimateHeadcount:
    """_estimate_headcount: INSEE tranche_effectif -> headcount estimate."""

    def test_none_defaults_to_5(self):
        assert _estimate_headcount(None) == 5

    def test_empty_string_defaults_to_5(self):
        assert _estimate_headcount("") == 5

    def test_unknown_code_defaults_to_5(self):
        assert _estimate_headcount("XX") == 5

    def test_known_codes(self):
        assert _estimate_headcount("00") == 0
        assert _estimate_headcount("11") == 15
        assert _estimate_headcount("52") == 10000

    def test_strips_whitespace(self):
        assert _estimate_headcount("  11  ") == 15

    def test_numeric_coerced_to_str(self):
        # str(11).strip() -> "11" which is a known key
        assert _estimate_headcount(11) == 15

    def test_every_tranche_resolves(self):
        for code, expected in _TRANCHE_EFFECTIF.items():
            assert _estimate_headcount(code) == expected


class TestModuleConstants:
    """_TRANCHE_EFFECTIF / _INSTITUTIONS sanity."""

    def test_tranche_values_monotonic_nonneg(self):
        values = list(_TRANCHE_EFFECTIF.values())
        assert all(v >= 0 for v in values)
        assert values == sorted(values)

    def test_institutions_have_required_keys(self):
        for inst in _INSTITUTIONS:
            assert "external_id" in inst
            assert "name" in inst
            assert "metadata" in inst
            assert inst["external_id"].startswith("INST:")

    def test_expected_institutions_present(self):
        ext_ids = {i["external_id"] for i in _INSTITUTIONS}
        assert {"INST:CCI", "INST:BPI", "INST:FT", "INST:URSSAF", "INST:TRIBUNAL"} <= ext_ids


# ===========================================================================
# Abstract base
# ===========================================================================
class TestBasePredictor:
    """BasePredictor is abstract: cannot be instantiated directly."""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BasePredictor()

    def test_subclass_missing_predict_cannot_instantiate(self):
        class Incomplete(BasePredictor):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_subclass_instantiates(self):
        class Concrete(BasePredictor):
            source_name = "x"

            async def predict(self, department_code):
                return {"actors": [], "relations": []}

        assert Concrete().source_name == "x"


# ===========================================================================
# Generic L3 invariants (shared assertions)
# ===========================================================================
def _assert_l3_invariants(relations):
    for rel in relations:
        assert rel["relation_type"] == "hypothetical"
        assert rel["source_type"] == "model"
        assert 0.05 <= rel["confidence"] <= 0.39


# ===========================================================================
# CascadePredictor
# ===========================================================================
class TestCascadePredictor:
    @pytest.fixture
    def predictor(self):
        return CascadePredictor()

    def test_source_name(self, predictor):
        assert predictor.source_name == "cascade_predictor"

    def test_distress_subtypes_constant(self, predictor):
        assert "event_liquidation" in predictor.DISTRESS_SUBTYPES
        assert "event_redressement" in predictor.DISTRESS_SUBTYPES

    @pytest.mark.asyncio
    async def test_no_distressed_returns_empty(self, predictor):
        # First fetch (distressed) returns nothing -> early return.
        with _patch_conn(fetch_side_effect=[[]]):
            result = await predictor.predict("75")
        assert result == {"actors": [], "relations": []}

    @pytest.mark.asyncio
    async def test_zero_total_enterprises_returns_empty(self, predictor):
        distressed = [{"external_id": "E1", "name": "Acme", "metadata": {}, "distress_count": 1}]
        sector_links = [{"ent_ext": "E1", "sec_ext": "S1"}]
        with _patch_conn(fetch_side_effect=[distressed, sector_links], fetchval=0):
            result = await predictor.predict("75")
        assert result == {"actors": [], "relations": []}

    @pytest.mark.asyncio
    async def test_distressed_without_sector_skipped(self, predictor):
        distressed = [{"external_id": "E1", "name": "Acme", "metadata": {}, "distress_count": 1}]
        sector_links = []  # E1 has no sector
        with _patch_conn(fetch_side_effect=[distressed, sector_links], fetchval=10):
            result = await predictor.predict("75")
        assert result["relations"] == []

    @pytest.mark.asyncio
    async def test_sector_with_single_peer_skipped(self, predictor):
        # Sector has only the distressed enterprise itself (len(peers) < 2).
        distressed = [{"external_id": "E1", "name": "Acme", "metadata": {}, "distress_count": 1}]
        sector_links = [{"ent_ext": "E1", "sec_ext": "S1"}]
        with _patch_conn(fetch_side_effect=[distressed, sector_links], fetchval=10):
            result = await predictor.predict("75")
        assert result["relations"] == []

    @pytest.mark.asyncio
    async def test_creates_cascade_risk_to_healthy_peer(self, predictor):
        distressed = [{"external_id": "E1", "name": "Acme", "metadata": {}, "distress_count": 2}]
        sector_links = [
            {"ent_ext": "E1", "sec_ext": "S1"},
            {"ent_ext": "E2", "sec_ext": "S1"},  # healthy peer
        ]
        with _patch_conn(fetch_side_effect=[distressed, sector_links], fetchval=10):
            result = await predictor.predict("75")

        rels = result["relations"]
        assert len(rels) == 1
        rel = rels[0]
        assert rel["subtype"] == "cascade_risk"
        assert rel["source_actor_external_id"] == "E1"
        assert rel["target_actor_external_id"] == "E2"
        assert rel["evidence"]["method"] == "distress_propagation"
        assert rel["evidence"]["sector"] == "S1"
        _assert_l3_invariants(rels)

    @pytest.mark.asyncio
    async def test_distressed_peer_is_skipped(self, predictor):
        # Both E1 and E2 are distressed -> no cascade edge between them.
        distressed = [
            {"external_id": "E1", "name": "A", "metadata": {}, "distress_count": 1},
            {"external_id": "E2", "name": "B", "metadata": {}, "distress_count": 1},
        ]
        sector_links = [
            {"ent_ext": "E1", "sec_ext": "S1"},
            {"ent_ext": "E2", "sec_ext": "S1"},
        ]
        with _patch_conn(fetch_side_effect=[distressed, sector_links], fetchval=10):
            result = await predictor.predict("75")
        assert result["relations"] == []

    @pytest.mark.asyncio
    async def test_confidence_capped_at_039(self, predictor):
        # High distress + high concentration would overflow without the cap.
        distressed = [{"external_id": "E1", "name": "A", "metadata": {}, "distress_count": 10}]
        sector_links = [
            {"ent_ext": "E1", "sec_ext": "S1"},
            {"ent_ext": "E2", "sec_ext": "S1"},
            {"ent_ext": "E3", "sec_ext": "S1"},
        ]
        with _patch_conn(fetch_side_effect=[distressed, sector_links], fetchval=3):
            result = await predictor.predict("75")
        assert result["relations"]
        for rel in result["relations"]:
            assert rel["confidence"] == 0.39
        _assert_l3_invariants(result["relations"])

    @pytest.mark.asyncio
    async def test_actors_always_empty_list(self, predictor):
        # CascadePredictor never emits actors.
        distressed = [{"external_id": "E1", "name": "A", "metadata": {}, "distress_count": 1}]
        sector_links = [
            {"ent_ext": "E1", "sec_ext": "S1"},
            {"ent_ext": "E2", "sec_ext": "S1"},
        ]
        with _patch_conn(fetch_side_effect=[distressed, sector_links], fetchval=10):
            result = await predictor.predict("75")
        assert result["actors"] == []


# ===========================================================================
# InstitutionalLinkPredictor (concrete, but absent from the registry)
# ===========================================================================
class TestInstitutionalLinkPredictor:
    @pytest.fixture
    def predictor(self):
        return InstitutionalLinkPredictor()

    def test_source_name(self, predictor):
        assert predictor.source_name == "institutional_link_predictor"

    @pytest.mark.asyncio
    async def test_no_enterprises_returns_empty(self, predictor):
        # enterprises fetch empty, distressed fetch empty.
        with _patch_conn(fetch_side_effect=[[], []]):
            result = await predictor.predict("75")
        assert result == {"actors": [], "relations": []}

    @pytest.mark.asyncio
    async def test_creates_institution_actors(self, predictor):
        enterprises = [{"external_id": "E1", "name": "Acme", "metadata": {"tranche_effectif": "11"}}]
        with _patch_conn(fetch_side_effect=[enterprises, []]):
            result = await predictor.predict("75")
        actor_types = {a["type"] for a in result["actors"]}
        assert actor_types == {"institution"}
        assert len(result["actors"]) == len(_INSTITUTIONS)
        # Institution external ids are namespaced by department.
        for a in result["actors"]:
            assert a["external_id"].endswith(":75")

    @pytest.mark.asyncio
    async def test_small_enterprise_gets_cci_urssaf(self, predictor):
        # headcount 15 (tranche "11"): >0 (URSSAF), >=10 (FT), <50 (no BPI).
        enterprises = [{"external_id": "E1", "name": "A", "metadata": {"tranche_effectif": "11"}}]
        with _patch_conn(fetch_side_effect=[enterprises, []]):
            result = await predictor.predict("75")
        institutions = {r["evidence"]["institution"] for r in result["relations"]}
        assert "CCI" in institutions
        assert "URSSAF" in institutions
        assert "France Travail" in institutions
        assert "BPI" not in institutions
        assert all(r["subtype"] == "likely_institution" for r in result["relations"])
        _assert_l3_invariants(result["relations"])

    @pytest.mark.asyncio
    async def test_large_enterprise_gets_bpi(self, predictor):
        # tranche "42" -> 3500 employees -> BPI link present.
        enterprises = [{"external_id": "E1", "name": "Big", "metadata": {"tranche_effectif": "42"}}]
        with _patch_conn(fetch_side_effect=[enterprises, []]):
            result = await predictor.predict("75")
        institutions = {r["evidence"]["institution"] for r in result["relations"]}
        assert "BPI" in institutions
        bpi_rel = next(r for r in result["relations"] if r["evidence"]["institution"] == "BPI")
        # confidence = min(0.10 + (3500/1000)*0.2, 0.35) == 0.35 cap.
        assert bpi_rel["confidence"] == 0.35

    @pytest.mark.asyncio
    async def test_distressed_enterprise_gets_tribunal(self, predictor):
        enterprises = [{"external_id": "E1", "name": "A", "metadata": {"tranche_effectif": "11"}}]
        distressed = [{"external_id": "E1"}]
        with _patch_conn(fetch_side_effect=[enterprises, distressed]):
            result = await predictor.predict("75")
        institutions = {r["evidence"]["institution"] for r in result["relations"]}
        assert "Tribunal de Commerce" in institutions
        tribunal_rel = next(
            r for r in result["relations"]
            if r["evidence"]["institution"] == "Tribunal de Commerce"
        )
        assert tribunal_rel["confidence"] == 0.35

    @pytest.mark.asyncio
    async def test_zero_headcount_no_urssaf(self, predictor):
        # tranche "00" -> headcount 0 -> no URSSAF/FT, only CCI.
        enterprises = [{"external_id": "E1", "name": "A", "metadata": {"tranche_effectif": "00"}}]
        with _patch_conn(fetch_side_effect=[enterprises, []]):
            result = await predictor.predict("75")
        institutions = {r["evidence"]["institution"] for r in result["relations"]}
        assert institutions == {"CCI"}

    @pytest.mark.asyncio
    async def test_non_dict_metadata_tolerated(self, predictor):
        # metadata is not a dict -> treated as {} -> headcount default 5.
        enterprises = [{"external_id": "E1", "name": "A", "metadata": None}]
        with _patch_conn(fetch_side_effect=[enterprises, []]):
            result = await predictor.predict("75")
        institutions = {r["evidence"]["institution"] for r in result["relations"]}
        # headcount 5 -> CCI + URSSAF (>0), no FT (<10), no BPI.
        assert institutions == {"CCI", "URSSAF"}


# ===========================================================================
# TerritorialImpactPredictor
# ===========================================================================
class TestTerritorialImpactPredictor:
    @pytest.fixture
    def predictor(self):
        return TerritorialImpactPredictor()

    def test_source_name(self, predictor):
        assert predictor.source_name == "territorial_impact_predictor"

    def test_impact_threshold(self, predictor):
        assert predictor.IMPACT_THRESHOLD == 0.15

    @pytest.mark.asyncio
    async def test_no_enterprises_returns_empty(self, predictor):
        with _patch_conn(fetch_side_effect=[[], [], []]):
            result = await predictor.predict("75")
        assert result == {"actors": [], "relations": []}

    @pytest.mark.asyncio
    async def test_sole_enterprise_high_impact(self, predictor):
        # One enterprise = 100% employment share, sole sector member.
        enterprises = [{"external_id": "E1", "name": "Solo", "metadata": {"tranche_effectif": "32"}}]
        sector_links = [{"ent_ext": "E1", "sec_ext": "S1", "sec_name": "Sector One"}]
        sector_distress = []
        with _patch_conn(fetch_side_effect=[enterprises, sector_links, sector_distress]):
            result = await predictor.predict("75")

        rels = result["relations"]
        assert len(rels) == 1
        rel = rels[0]
        assert rel["subtype"] == "territorial_impact"
        assert rel["source_actor_external_id"] == "E1"
        assert rel["target_actor_external_id"] == "DEPT:75"
        assert rel["evidence"]["sector_name"] == "Sector One"
        _assert_l3_invariants(rels)

    @pytest.mark.asyncio
    async def test_low_impact_below_threshold_skipped(self, predictor):
        # Many same-size peers in one sector dilute employment share & uniqueness.
        enterprises = [
            {"external_id": f"E{i}", "name": f"E{i}", "metadata": {"tranche_effectif": "11"}}
            for i in range(20)
        ]
        sector_links = [
            {"ent_ext": f"E{i}", "sec_ext": "S1", "sec_name": "S"} for i in range(20)
        ]
        with _patch_conn(fetch_side_effect=[enterprises, sector_links, []]):
            result = await predictor.predict("75")
        # Each: employment_share=0.05*0.5=0.025, uniqueness=(1/20)*0.3=0.015 -> 0.04 < 0.15
        assert result["relations"] == []

    @pytest.mark.asyncio
    async def test_confidence_capped(self, predictor):
        enterprises = [{"external_id": "E1", "name": "Solo", "metadata": {"tranche_effectif": "52"}}]
        sector_links = [{"ent_ext": "E1", "sec_ext": "S1", "sec_name": "S"}]
        sector_distress = [{"sec_ext": "S1", "distressed_count": 9}]
        with _patch_conn(fetch_side_effect=[enterprises, sector_links, sector_distress]):
            result = await predictor.predict("75")
        for rel in result["relations"]:
            assert rel["confidence"] <= 0.39
        _assert_l3_invariants(result["relations"])

    @pytest.mark.asyncio
    async def test_enterprise_without_sector_uniqueness_zero(self, predictor):
        # No sector link -> uniqueness 0; sole enterprise still high employment share.
        enterprises = [{"external_id": "E1", "name": "Solo", "metadata": {"tranche_effectif": "32"}}]
        with _patch_conn(fetch_side_effect=[enterprises, [], []]):
            result = await predictor.predict("75")
        # employment_share 1.0 * 0.5 = 0.5 >= 0.15 -> relation created.
        assert len(result["relations"]) == 1
        assert result["relations"][0]["evidence"]["sector"] == ""

    @pytest.mark.asyncio
    async def test_actors_always_empty(self, predictor):
        enterprises = [{"external_id": "E1", "name": "Solo", "metadata": {"tranche_effectif": "32"}}]
        sector_links = [{"ent_ext": "E1", "sec_ext": "S1", "sec_name": "S"}]
        with _patch_conn(fetch_side_effect=[enterprises, sector_links, []]):
            result = await predictor.predict("75")
        assert result["actors"] == []


# ===========================================================================
# Registry
# ===========================================================================
class TestRegistry:
    def test_contains_cascade_and_territorial(self):
        assert "cascade" in PREDICTORS
        assert "territorial_impact" in PREDICTORS

    def test_institutional_link_removed(self):
        # Comment in source: removed because it produced 7000+ relations/dept.
        assert "institutional_link" not in PREDICTORS

    def test_values_are_basepredictor_subclasses(self):
        for cls in PREDICTORS.values():
            assert issubclass(cls, BasePredictor)

    def test_classes_are_instantiable(self):
        for cls in PREDICTORS.values():
            instance = cls()
            assert isinstance(instance, BasePredictor)

    def test_cascade_maps_to_cascade_predictor(self):
        assert PREDICTORS["cascade"] is CascadePredictor

    def test_territorial_maps_to_territorial_impact_predictor(self):
        assert PREDICTORS["territorial_impact"] is TerritorialImpactPredictor


# ===========================================================================
# simulate_whatif
# ===========================================================================
class TestSimulateWhatif:
    @pytest.mark.asyncio
    async def test_actor_not_found_returns_error(self):
        with _patch_conn(fetch_side_effect=[], fetchrow=None):
            result = await simulate_whatif("MISSING", "75")
        assert "error" in result
        assert "MISSING" in result["error"]

    @pytest.mark.asyncio
    async def test_isolated_actor_no_cascade(self):
        actor = {"id": 1, "external_id": "E1", "name": "Solo", "metadata": {"tranche_effectif": "22"}}
        # No relations at all -> no cascade paths.
        with _patch_conn(fetch_side_effect=[], fetchrow=actor):
            result = await simulate_whatif("E1", "75", max_depth=3)
        assert result["source_actor"]["external_id"] == "E1"
        assert result["source_actor"]["estimated_headcount"] == 150
        assert result["affected_actors"] == 0
        assert result["cascade_paths"] == []
        assert result["total_impact_score"] == 0.0
        assert result["employment_at_risk"] == 150
        assert result["cascade_depth"] == 3

    @pytest.mark.asyncio
    async def test_cascade_propagates_to_enterprise_neighbor(self):
        actor = {"id": 1, "external_id": "E1", "name": "Source", "metadata": {"tranche_effectif": "32"}}
        relations = [
            {
                "source_actor_id": 1,
                "target_actor_id": 2,
                "relation_type": "structural",
                "subtype": "belongs_to_sector",
                "confidence": 0.9,
                "weight": 1.5,
                "src_ext": "E1",
                "src_name": "Source",
                "src_meta": {"tranche_effectif": "32", "naf": "6201Z"},
                "src_type": "enterprise",
                "tgt_ext": "E2",
                "tgt_name": "Target",
                "tgt_meta": {"tranche_effectif": "21", "naf": "6201Z"},
                "tgt_type": "enterprise",
            }
        ]
        with _patch_conn(fetch_side_effect=[relations], fetchrow=actor):
            with patch(f"{MODULE}.predict_cascade_probability", return_value=0.5):
                result = await simulate_whatif("E1", "75", max_depth=2)

        assert result["affected_actors"] == 1
        path = result["cascade_paths"][0]
        assert path["actor_external_id"] == "E2"
        assert path["actor_type"] == "enterprise"
        assert path["depth"] == 1
        assert path["cascade_probability"] == 0.5
        assert path["via_relation"] == "belongs_to_sector"
        assert result["total_impact_score"] > 0

    @pytest.mark.asyncio
    async def test_non_enterprise_non_sector_neighbor_skipped(self):
        actor = {"id": 1, "external_id": "E1", "name": "Source", "metadata": {"tranche_effectif": "32"}}
        relations = [
            {
                "source_actor_id": 1,
                "target_actor_id": 2,
                "relation_type": "structural",
                "subtype": "headquarter_in",
                "confidence": 0.95,
                "weight": 1.0,
                "src_ext": "E1",
                "src_name": "Source",
                "src_meta": {"tranche_effectif": "32"},
                "src_type": "enterprise",
                "tgt_ext": "DEPT:75",
                "tgt_name": "Paris",
                "tgt_meta": {},
                "tgt_type": "territory",  # not enterprise/sector -> skipped
            }
        ]
        with _patch_conn(fetch_side_effect=[relations], fetchrow=actor):
            with patch(f"{MODULE}.predict_cascade_probability", return_value=0.5):
                result = await simulate_whatif("E1", "75")
        assert result["affected_actors"] == 0

    @pytest.mark.asyncio
    async def test_low_cascade_probability_pruned(self):
        actor = {"id": 1, "external_id": "E1", "name": "Source", "metadata": {"tranche_effectif": "32"}}
        relations = [
            {
                "source_actor_id": 1,
                "target_actor_id": 2,
                "relation_type": "structural",
                "subtype": "belongs_to_sector",
                "confidence": 0.9,
                "weight": 1.0,
                "src_ext": "E1",
                "src_name": "Source",
                "src_meta": {"tranche_effectif": "32"},
                "src_type": "enterprise",
                "tgt_ext": "E2",
                "tgt_name": "Target",
                "tgt_meta": {"tranche_effectif": "21"},
                "tgt_type": "enterprise",
            }
        ]
        with _patch_conn(fetch_side_effect=[relations], fetchrow=actor):
            with patch(f"{MODULE}.predict_cascade_probability", return_value=0.001):
                result = await simulate_whatif("E1", "75")
        # cascade_prob < 0.01 -> neighbor pruned.
        assert result["affected_actors"] == 0

    @pytest.mark.asyncio
    async def test_cascade_paths_limited_to_50(self):
        actor = {"id": 0, "external_id": "E0", "name": "Source", "metadata": {"tranche_effectif": "52"}}
        # 60 direct enterprise neighbors of E0.
        relations = []
        for i in range(1, 61):
            relations.append(
                {
                    "source_actor_id": 0,
                    "target_actor_id": i,
                    "relation_type": "structural",
                    "subtype": "belongs_to_sector",
                    "confidence": 0.9,
                    "weight": 1.0,
                    "src_ext": "E0",
                    "src_name": "Source",
                    "src_meta": {"tranche_effectif": "52"},
                    "src_type": "enterprise",
                    "tgt_ext": f"E{i}",
                    "tgt_name": f"Target {i}",
                    "tgt_meta": {"tranche_effectif": "21"},
                    "tgt_type": "enterprise",
                }
            )
        with _patch_conn(fetch_side_effect=[relations], fetchrow=actor):
            with patch(f"{MODULE}.predict_cascade_probability", return_value=0.5):
                result = await simulate_whatif("E0", "75", max_depth=1)
        assert result["affected_actors"] == 60  # all visited
        assert len(result["cascade_paths"]) == 50  # but output truncated to 50

    @pytest.mark.asyncio
    async def test_paths_sorted_by_impact_desc(self):
        actor = {"id": 0, "external_id": "E0", "name": "Source", "metadata": {"tranche_effectif": "52"}}
        relations = [
            {
                "source_actor_id": 0,
                "target_actor_id": 1,
                "relation_type": "structural",
                "subtype": "belongs_to_sector",
                "confidence": 0.9,
                "weight": 1.0,
                "src_ext": "E0",
                "src_name": "Source",
                "src_meta": {"tranche_effectif": "52"},
                "src_type": "enterprise",
                "tgt_ext": "Small",
                "tgt_name": "Small",
                "tgt_meta": {"tranche_effectif": "11"},  # 15
                "tgt_type": "enterprise",
            },
            {
                "source_actor_id": 0,
                "target_actor_id": 2,
                "relation_type": "structural",
                "subtype": "belongs_to_sector",
                "confidence": 0.9,
                "weight": 1.0,
                "src_ext": "E0",
                "src_name": "Source",
                "src_meta": {"tranche_effectif": "52"},
                "src_type": "enterprise",
                "tgt_ext": "Big",
                "tgt_name": "Big",
                "tgt_meta": {"tranche_effectif": "42"},  # 3500
                "tgt_type": "enterprise",
            },
        ]
        with _patch_conn(fetch_side_effect=[relations], fetchrow=actor):
            with patch(f"{MODULE}.predict_cascade_probability", return_value=0.5):
                result = await simulate_whatif("E0", "75", max_depth=1)
        scores = [p["impact_score"] for p in result["cascade_paths"]]
        assert scores == sorted(scores, reverse=True)
        # Bigger headcount target should rank first.
        assert result["cascade_paths"][0]["actor_external_id"] == "Big"

    @pytest.mark.asyncio
    async def test_non_dict_actor_metadata_tolerated(self):
        actor = {"id": 1, "external_id": "E1", "name": "Solo", "metadata": None}
        with _patch_conn(fetch_side_effect=[], fetchrow=actor):
            result = await simulate_whatif("E1", "75")
        # metadata None -> {} -> default headcount 5.
        assert result["source_actor"]["estimated_headcount"] == 5
