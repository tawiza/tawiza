"""Unit tests for L2 relation inferrers (statistical correlation analysis).

All inferrers operate on the persisted ``actors`` / ``relations`` tables via
``acquire_conn``. These tests mock the DB connection (and the BAN geocoding
adapter for ``ProximityInferrer``) so the inference *logic* is exercised
without any infrastructure.

Invariants checked across inferrers:
- relation_type == "inferred"
- source_type  == "model"
- confidence stays within the documented L2 bounds
"""

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.relation_inferrers import (
    INFERRERS,
    BaseInferrer,
    DirectorLinkInferrer,
    EmploymentWeightInferrer,
    EPCIBelongsInferrer,
    FinancialLinkInferrer,
    FormationLinkInferrer,
    GeographicClusterInferrer,
    IncubatorMatchInferrer,
    PoleMembershipInferrer,
    ProximityInferrer,
    SectorConcentrationInferrer,
    SocialLinkInferrer,
    SupplyChainInferrer,
    _actor_id,
    _estimate_headcount,
    _extract_enterprise_naf_section,
    _extract_person_from_listepersonnes,
    _haversine,
    _is_person_name,
    _naf_code_to_section,
    _normalize_name,
    _normalize_sector_label,
    _parse_meta,
    _relation_id,
    _stable_uuid,
    _TRANCHE_EFFECTIF,
)

MODULE = "src.application.services.relation_inferrers"


# ---------------------------------------------------------------------------
# Mock DB helper
# ---------------------------------------------------------------------------


def _mock_acquire_conn(*, fetch_results=None, fetchval_results=None):
    """Build an async context manager yielding a connection.

    ``fetch_results`` / ``fetchval_results`` may be:
    - a single value -> returned for every call
    - a list of values -> returned in order (side_effect)
    """
    mock_conn = MagicMock()

    if isinstance(fetch_results, list) and fetch_results and isinstance(
        fetch_results[0], (list, tuple)
    ):
        mock_conn.fetch = AsyncMock(side_effect=[list(r) for r in fetch_results])
    else:
        mock_conn.fetch = AsyncMock(return_value=fetch_results or [])

    if isinstance(fetchval_results, list):
        mock_conn.fetchval = AsyncMock(side_effect=fetchval_results)
    else:
        mock_conn.fetchval = AsyncMock(return_value=fetchval_results)

    @asynccontextmanager
    async def _ctx():
        yield mock_conn

    return _ctx


def _patch_db(**kwargs):
    return patch(f"{MODULE}.acquire_conn", _mock_acquire_conn(**kwargs))


# ===========================================================================
# Pure helpers
# ===========================================================================


class TestStableUuidHelpers:
    def test_stable_uuid_deterministic_and_v5(self):
        a = _stable_uuid("relation", "k")
        b = _stable_uuid("relation", "k")
        assert a == b
        assert isinstance(a, uuid.UUID)
        assert a.version == 5

    def test_actor_id_format(self):
        assert _actor_id("sector", "X") == _stable_uuid("actor", "sector:X")

    def test_relation_id_direction_and_subtype_matter(self):
        assert _relation_id("A", "B", "x") != _relation_id("B", "A", "x")
        assert _relation_id("A", "B", "x") != _relation_id("A", "B", "y")
        assert _relation_id("A", "B", "x") == _stable_uuid("relation", "A->B:x")


class TestEstimateHeadcount:
    def test_known_tranche(self):
        assert _estimate_headcount("52") == 10000
        assert _estimate_headcount("11") == 15
        assert _estimate_headcount("00") == 0

    def test_none_returns_micro_default(self):
        assert _estimate_headcount(None) == 5

    def test_empty_string_returns_default(self):
        assert _estimate_headcount("") == 5

    def test_unknown_code_returns_default(self):
        assert _estimate_headcount("ZZ") == 5

    def test_whitespace_is_stripped(self):
        assert _estimate_headcount("  21  ") == 75

    def test_non_string_coerced(self):
        assert _estimate_headcount(11) == _TRANCHE_EFFECTIF["11"]

    def test_all_table_entries_resolve(self):
        for code, expected in _TRANCHE_EFFECTIF.items():
            assert _estimate_headcount(code) == expected


class TestNormalizeName:
    def test_lowercase_strip_accents(self):
        assert _normalize_name("DÉ MÔNT") == "de mont"

    def test_collapse_spaces(self):
        assert _normalize_name("  Jean   Pierre  ") == "jean pierre"

    def test_too_short_returns_empty(self):
        assert _normalize_name("ab") == ""

    def test_three_chars_kept(self):
        assert _normalize_name("abc") == "abc"


class TestIsPersonName:
    def test_simple_person(self):
        assert _is_person_name("DUPONT, Jean") is True

    def test_compound_last_and_first(self):
        assert _is_person_name("BEN SAID, Marie-Claire") is True

    def test_corporate_keyword_rejected(self):
        assert _is_person_name("PHARMACIE, Centrale") is False
        assert _is_person_name("MARTIN SARL, Jean") is False

    def test_multiple_commas_rejected(self):
        assert _is_person_name("ENSEIGNE, RAISON, SOCIALE") is False

    def test_no_comma_rejected(self):
        assert _is_person_name("DUPONT Jean") is False

    def test_corporate_substring_not_falsely_matched(self):
        # "sa" inside "ABBASSA" must NOT trigger the corporate keyword filter
        assert _is_person_name("ABBASSA, Yacine") is True


class TestExtractPersonFromListepersonnes:
    def test_valid_json_with_siren(self):
        raw = (
            '{"personne": {"nom": "DUPONT", "prenom": "Jean,Paul",'
            ' "numeroImmatriculation": {"numeroIdentification": "123 456 789"}}}'
        )
        name, siren = _extract_person_from_listepersonnes(raw)
        assert name == "DUPONT Jean"
        assert siren == "123456789"

    def test_dict_input_accepted(self):
        data = {"personne": {"nom": "MARTIN", "prenom": "Luc"}}
        name, siren = _extract_person_from_listepersonnes(data)
        assert name == "MARTIN Luc"
        assert siren == ""

    def test_invalid_rcs_number_yields_empty_siren(self):
        data = {"nom": "X", "prenom": "Y", "numeroImmatriculation": {"numeroIdentification": "12"}}
        name, siren = _extract_person_from_listepersonnes(data)
        assert siren == ""

    def test_malformed_returns_empty_tuple(self):
        assert _extract_person_from_listepersonnes("not json") == ("", "")


class TestHaversine:
    def test_zero_distance(self):
        assert _haversine(48.8566, 2.3522, 48.8566, 2.3522) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_paris_lyon(self):
        # Paris -> Lyon is roughly 392 km
        dist = _haversine(48.8566, 2.3522, 45.7640, 4.8357)
        assert 380_000 < dist < 400_000

    def test_symmetric(self):
        d1 = _haversine(48.0, 2.0, 49.0, 3.0)
        d2 = _haversine(49.0, 3.0, 48.0, 2.0)
        assert d1 == pytest.approx(d2)


class TestNafCodeToSection:
    def test_dotted_code(self):
        assert _naf_code_to_section("62.01Z") == "J"

    def test_undotted_code(self):
        assert _naf_code_to_section("4711C") == "G"

    def test_agriculture(self):
        assert _naf_code_to_section("01.11Z") == "A"

    def test_empty_returns_empty(self):
        assert _naf_code_to_section("") == ""

    def test_unknown_division_returns_empty(self):
        assert _naf_code_to_section("0411Z") == ""  # division "04" not mapped

    def test_letters_only_returns_empty(self):
        assert _naf_code_to_section("ABZ") == ""


class TestNormalizeSectorLabel:
    def test_lower_and_strip_accents(self):
        assert _normalize_sector_label("  Énergie  ") == "energie"


class TestParseMeta:
    def test_dict_passthrough(self):
        d = {"a": 1}
        assert _parse_meta(d) is d

    def test_json_string(self):
        assert _parse_meta('{"a": 1}') == {"a": 1}

    def test_bad_json(self):
        assert _parse_meta("nope") == {}

    def test_none(self):
        assert _parse_meta(None) == {}

    def test_int(self):
        assert _parse_meta(7) == {}


class TestExtractEnterpriseNafSection:
    def test_direct_naf_section(self):
        assert _extract_enterprise_naf_section({"naf_section": "j"}) == ("J", "naf_section")

    def test_from_naf_code(self):
        assert _extract_enterprise_naf_section({"naf": "62.01Z"}) == ("J", "naf_code")

    def test_from_activite_principale(self):
        assert _extract_enterprise_naf_section({"activite_principale": "4711C"}) == (
            "G",
            "naf_code",
        )

    def test_cpv_fallback_list(self):
        assert _extract_enterprise_naf_section({"cpv_code": ["45000000"]}) == ("F", "cpv_code")

    def test_cpv_fallback_string(self):
        assert _extract_enterprise_naf_section({"cpv_code": "85000000"}) == ("Q", "cpv_code")

    def test_cpv_json_string(self):
        assert _extract_enterprise_naf_section({"cpv_code": '["72000000"]'}) == ("J", "cpv_code")

    def test_nothing_found(self):
        assert _extract_enterprise_naf_section({}) == ("", "")

    def test_cpv_bad_json_string_falls_back_to_raw(self):
        # invalid JSON string -> treated as single raw code "45..." -> section F
        assert _extract_enterprise_naf_section({"cpv_code": "45-not-json"}) == ("F", "cpv_code")

    def test_unknown_cpv_prefix_returns_empty(self):
        assert _extract_enterprise_naf_section({"cpv_code": ["00000000"]}) == ("", "")

    def test_priority_naf_section_over_code(self):
        # naf_section field wins even if naf code present
        sec, src = _extract_enterprise_naf_section({"naf_section": "C", "naf": "62.01Z"})
        assert (sec, src) == ("C", "naf_section")


# ===========================================================================
# BaseInferrer / registry
# ===========================================================================


class TestBaseInferrer:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseInferrer()

    def test_incomplete_subclass_cannot_instantiate(self):
        class Incomplete(BaseInferrer):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    async def test_concrete_subclass_ok(self):
        class Concrete(BaseInferrer):
            source_name = "x"

            async def infer(self, department_code):
                return {"actors": [], "relations": []}

        out = await Concrete().infer("75")
        assert out == {"actors": [], "relations": []}


class TestRegistry:
    def test_registry_keys_match_source_names(self):
        for key, cls in INFERRERS.items():
            assert issubclass(cls, BaseInferrer)
            assert cls.source_name == key

    def test_expected_inferrers_registered(self):
        assert set(INFERRERS) == {
            "sector_concentration",
            "employment_weight",
            "geographic_cluster",
            "supply_chain",
            "director_link",
            "proximity",
            "pole_membership",
            "epci_belongs",
            "incubator_match",
        }

    def test_removed_speculative_inferrers_absent(self):
        # social_link / financial_link / formation_link were intentionally dropped
        assert "social_link" not in INFERRERS
        assert "financial_link" not in INFERRERS
        assert "formation_link" not in INFERRERS

    def test_all_registered_instantiable(self):
        for cls in INFERRERS.values():
            assert isinstance(cls(), BaseInferrer)


# ===========================================================================
# 1. SectorConcentrationInferrer
# ===========================================================================


class TestSectorConcentrationInferrer:
    @pytest.fixture
    def inferrer(self):
        return SectorConcentrationInferrer()

    async def test_no_rows_returns_empty(self, inferrer):
        with _patch_db(fetch_results=[], fetchval_results=0):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    async def test_total_zero_returns_empty(self, inferrer):
        rows = [{"sector_ext_id": "NAF:62", "sector_name": "Prog", "sector_metadata": {},
                 "enterprise_count": 10}]
        with _patch_db(fetch_results=rows, fetchval_results=0):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    async def test_below_threshold_skipped(self, inferrer):
        rows = [{"sector_ext_id": "NAF:62", "sector_name": "Prog", "sector_metadata": {},
                 "enterprise_count": 5}]  # 5/100 = 5% < 10%
        with _patch_db(fetch_results=rows, fetchval_results=100):
            out = await inferrer.infer("75")
        assert out["relations"] == []

    async def test_dominant_sector_creates_relation(self, inferrer):
        rows = [{"sector_ext_id": "NAF:62", "sector_name": "Prog", "sector_metadata": {},
                 "enterprise_count": 30}]  # 30%
        with _patch_db(fetch_results=rows, fetchval_results=100):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1
        rel = out["relations"][0]
        assert rel["subtype"] == "sector_dominance"
        assert rel["relation_type"] == "inferred"
        assert rel["source_type"] == "model"
        assert rel["target_actor_external_id"] == "DEPT:75"
        assert rel["source_actor_external_id"] == "NAF:62"
        # 0.45 + (0.30-0.10)*0.85 = 0.62
        assert rel["confidence"] == pytest.approx(0.62)
        assert rel["evidence"]["share_pct"] == 30.0

    async def test_confidence_capped_at_079(self, inferrer):
        rows = [{"sector_ext_id": "NAF:62", "sector_name": "Prog", "sector_metadata": {},
                 "enterprise_count": 90}]  # 90% -> would exceed cap
        with _patch_db(fetch_results=rows, fetchval_results=100):
            out = await inferrer.infer("75")
        assert out["relations"][0]["confidence"] == 0.79

    async def test_confidence_within_l2_bounds(self, inferrer):
        rows = [{"sector_ext_id": "NAF:62", "sector_name": "Prog", "sector_metadata": {},
                 "enterprise_count": c} for c in (12, 25, 50, 90)]
        with _patch_db(fetch_results=rows, fetchval_results=100):
            out = await inferrer.infer("75")
        for rel in out["relations"]:
            assert 0.40 <= rel["confidence"] <= 0.79


# ===========================================================================
# 2. EmploymentWeightInferrer
# ===========================================================================


class TestEmploymentWeightInferrer:
    @pytest.fixture
    def inferrer(self):
        return EmploymentWeightInferrer()

    async def test_no_rows_returns_empty(self, inferrer):
        with _patch_db(fetch_results=[]):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    async def test_zero_total_employment_returns_empty(self, inferrer):
        # All enterprises with tranche "00" -> headcount 0 -> total 0
        rows = [{"id": 1, "external_id": "SIREN:1", "name": "A",
                 "metadata": {"tranche_effectif": "00"}}]
        with _patch_db(fetch_results=rows):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    async def test_big_employer_creates_anchor(self, inferrer):
        rows = [
            {"id": 1, "external_id": "SIREN:1", "name": "Big",
             "metadata": {"tranche_effectif": "52"}},   # 10000
            {"id": 2, "external_id": "SIREN:2", "name": "Small",
             "metadata": {"tranche_effectif": "01"}},    # 1
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        anchors = [r for r in out["relations"] if r["subtype"] == "employment_anchor"]
        assert len(anchors) == 1  # only the big one passes 2% threshold
        rel = anchors[0]
        assert rel["source_actor_external_id"] == "SIREN:1"
        assert rel["target_actor_external_id"] == "DEPT:75"
        assert rel["confidence"] == 0.79  # near-100% share, capped
        assert rel["relation_type"] == "inferred"

    async def test_below_threshold_skipped(self, inferrer):
        # 50 enterprises of equal size -> each 2% exactly == threshold boundary
        rows = [{"id": i, "external_id": f"SIREN:{i}", "name": f"E{i}",
                 "metadata": {"tranche_effectif": "11"}} for i in range(100)]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        # each share = 1/100 = 1% < 2% -> none kept
        assert out["relations"] == []

    async def test_metadata_non_dict_treated_as_default(self, inferrer):
        rows = [{"id": 1, "external_id": "SIREN:1", "name": "A", "metadata": None}]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        # single enterprise, default headcount 5, share 100% -> anchor created
        assert len(out["relations"]) == 1
        assert out["relations"][0]["confidence"] == 0.79

    async def test_confidence_within_bounds(self, inferrer):
        rows = [
            {"id": 1, "external_id": "SIREN:1", "name": "A",
             "metadata": {"tranche_effectif": "31"}},   # 225
            {"id": 2, "external_id": "SIREN:2", "name": "B",
             "metadata": {"tranche_effectif": "21"}},    # 75
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        for rel in out["relations"]:
            assert 0.40 <= rel["confidence"] <= 0.79


# ===========================================================================
# 3. GeographicClusterInferrer
# ===========================================================================


class TestGeographicClusterInferrer:
    @pytest.fixture
    def inferrer(self):
        return GeographicClusterInferrer()

    async def test_no_rows_returns_empty(self, inferrer):
        with _patch_db(fetch_results=[]):
            assert await inferrer.infer("13") == {"actors": [], "relations": []}

    def _row(self, ext, cp, naf="47.11Z"):
        return {
            "ent_ext_id": ext,
            "ent_name": f"Ent {ext}",
            "ent_metadata": {"code_postal": cp},
            "sector_ext_id": f"NAF:{naf}",
            "sector_name": "Retail",
        }

    async def test_cluster_below_min_size_skipped(self, inferrer):
        rows = [self._row("SIREN:1", "13001"), self._row("SIREN:2", "13001")]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("13")
        assert out["actors"] == []
        assert out["relations"] == []

    async def test_cluster_formed_at_min_size(self, inferrer):
        rows = [self._row(f"SIREN:{i}", "13001") for i in range(3)]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("13")
        assert len(out["actors"]) == 1
        cluster = out["actors"][0]
        assert cluster["type"] == "sector"
        assert cluster["external_id"] == "CLUSTER:13:47:13001"
        assert cluster["metadata"]["member_count"] == 3
        assert len(out["relations"]) == 3
        for rel in out["relations"]:
            assert rel["subtype"] == "cluster_member"
            assert rel["target_actor_external_id"] == "CLUSTER:13:47:13001"
            # 0.40 + 3*0.05 = 0.55
            assert rel["confidence"] == pytest.approx(0.55)

    async def test_missing_cp_or_naf_skipped(self, inferrer):
        rows = [
            {"ent_ext_id": "SIREN:1", "ent_name": "A", "ent_metadata": {},
             "sector_ext_id": "NAF:47.11Z", "sector_name": "R"},  # no cp
            {"ent_ext_id": "SIREN:2", "ent_name": "B",
             "ent_metadata": {"code_postal": "13001"},
             "sector_ext_id": "FOO:bar", "sector_name": "R"},  # no NAF prefix
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("13")
        assert out["relations"] == []

    async def test_confidence_capped_at_075(self, inferrer):
        rows = [self._row(f"SIREN:{i}", "13001") for i in range(20)]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("13")
        for rel in out["relations"]:
            assert rel["confidence"] == 0.75
            assert 0.40 <= rel["confidence"] <= 0.79


# ===========================================================================
# 4. SocialLinkInferrer (not in registry, but logic still tested)
# ===========================================================================


class TestSocialLinkInferrer:
    @pytest.fixture
    def inferrer(self):
        return SocialLinkInferrer()

    async def test_no_data_returns_empty(self, inferrer):
        # both fetch calls empty
        with _patch_db(fetch_results=[[], []]):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    async def test_social_link_created_for_two_plus_enterprises(self, inferrer):
        assoc_rows = [{"id": 1, "external_id": "ASSOC:1", "name": "Asso",
                       "metadata": {"naf": "62.01Z"}}]
        sector_rows = [
            {"ent_ext_id": "SIREN:1", "ent_metadata": {"tranche_effectif": "01"},
             "sector_ext_id": "NAF:62.01Z", "sector_name": "Prog"},
            {"ent_ext_id": "SIREN:2", "ent_metadata": {"tranche_effectif": "01"},
             "sector_ext_id": "NAF:62.01Z", "sector_name": "Prog"},
        ]
        with _patch_db(fetch_results=[assoc_rows, sector_rows]):
            out = await inferrer.infer("75")
        links = [r for r in out["relations"] if r["subtype"] == "social_link"]
        assert len(links) == 1
        assert links[0]["source_actor_external_id"] == "ASSOC:1"
        assert links[0]["target_actor_external_id"] == "NAF:62.01Z"
        assert 0.40 <= links[0]["confidence"] <= 0.79

    async def test_social_proximity_for_large_employers(self, inferrer):
        assoc_rows = [{"id": 1, "external_id": "ASSOC:1", "name": "Asso",
                       "metadata": {"naf": "62.01Z"}}]
        sector_rows = [
            {"ent_ext_id": "SIREN:1", "ent_metadata": {"tranche_effectif": "32"},  # 375
             "sector_ext_id": "NAF:62.01Z", "sector_name": "Prog"},
            {"ent_ext_id": "SIREN:2", "ent_metadata": {"tranche_effectif": "22"},  # 150
             "sector_ext_id": "NAF:62.01Z", "sector_name": "Prog"},
        ]
        with _patch_db(fetch_results=[assoc_rows, sector_rows]):
            out = await inferrer.infer("75")
        prox = [r for r in out["relations"] if r["subtype"] == "social_proximity"]
        assert len(prox) == 2
        for rel in prox:
            assert rel["confidence"] <= 0.65

    async def test_assoc_without_naf_skipped(self, inferrer):
        assoc_rows = [{"id": 1, "external_id": "ASSOC:1", "name": "Asso", "metadata": {}}]
        sector_rows = [
            {"ent_ext_id": "SIREN:1", "ent_metadata": {"tranche_effectif": "01"},
             "sector_ext_id": "NAF:62.01Z", "sector_name": "Prog"},
            {"ent_ext_id": "SIREN:2", "ent_metadata": {"tranche_effectif": "01"},
             "sector_ext_id": "NAF:62.01Z", "sector_name": "Prog"},
        ]
        with _patch_db(fetch_results=[assoc_rows, sector_rows]):
            out = await inferrer.infer("75")
        assert out["relations"] == []


# ===========================================================================
# 5. FinancialLinkInferrer (not in registry)
# ===========================================================================


class TestFinancialLinkInferrer:
    @pytest.fixture
    def inferrer(self):
        return FinancialLinkInferrer()

    async def test_no_data_returns_empty(self, inferrer):
        with _patch_db(fetch_results=[[], []]):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    async def test_links_large_enterprises_only(self, inferrer):
        fin_rows = [{"id": 1, "external_id": "BANK:1", "name": "Bank", "metadata": {}}]
        ent_rows = [
            {"id": 1, "external_id": "SIREN:1", "name": "Big",
             "metadata": {"tranche_effectif": "21"}},   # 75 >= 15
            {"id": 2, "external_id": "SIREN:2", "name": "Tiny",
             "metadata": {"tranche_effectif": "01"}},    # 1 < 15
        ]
        with _patch_db(fetch_results=[fin_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1
        rel = out["relations"][0]
        assert rel["subtype"] == "likely_finances"
        assert rel["source_actor_external_id"] == "BANK:1"
        assert rel["target_actor_external_id"] == "SIREN:1"
        assert rel["confidence"] <= 0.70

    async def test_cap_50_relations_per_financial(self, inferrer):
        fin_rows = [{"id": 1, "external_id": "BANK:1", "name": "Bank", "metadata": {}}]
        ent_rows = [
            {"id": i, "external_id": f"SIREN:{i}", "name": f"E{i}",
             "metadata": {"tranche_effectif": "21"}}  # all big
            for i in range(80)
        ]
        with _patch_db(fetch_results=[fin_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 50


# ===========================================================================
# 6. FormationLinkInferrer (not in registry)
# ===========================================================================


class TestFormationLinkInferrer:
    @pytest.fixture
    def inferrer(self):
        return FormationLinkInferrer()

    async def test_no_formations_returns_empty(self, inferrer):
        with _patch_db(fetch_results=[[], [], []]):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    async def test_trains_sector_and_likely_trains(self, inferrer):
        formation_rows = [{"id": 1, "external_id": "FORM:1", "name": "IUT", "metadata": {}}]
        top_sectors = [
            {"sector_ext_id": "NAF:62.01Z", "sector_name": "Prog", "ent_count": 5},
        ]
        ent_rows = [
            {"id": 1, "external_id": "SIREN:1", "name": "Big",
             "metadata": {"tranche_effectif": "32"}},   # 375 >= 50
            {"id": 2, "external_id": "SIREN:2", "name": "Small",
             "metadata": {"tranche_effectif": "11"}},    # 15 < 50
        ]
        with _patch_db(fetch_results=[formation_rows, top_sectors, ent_rows]):
            out = await inferrer.infer("75")
        trains = [r for r in out["relations"] if r["subtype"] == "trains_sector"]
        likely = [r for r in out["relations"] if r["subtype"] == "likely_trains"]
        assert len(trains) == 1
        assert len(likely) == 1
        # trains_sector: 0.40 + 5*0.02 = 0.50
        assert trains[0]["confidence"] == pytest.approx(0.50)
        assert likely[0]["confidence"] <= 0.60
        assert likely[0]["target_actor_external_id"] == "SIREN:1"

    async def test_confidence_caps(self, inferrer):
        formation_rows = [{"id": 1, "external_id": "FORM:1", "name": "IUT", "metadata": {}}]
        top_sectors = [
            {"sector_ext_id": "NAF:62.01Z", "sector_name": "Prog", "ent_count": 100},
        ]
        ent_rows = [
            {"id": 1, "external_id": "SIREN:1", "name": "Huge",
             "metadata": {"tranche_effectif": "52"}},   # 10000
        ]
        with _patch_db(fetch_results=[formation_rows, top_sectors, ent_rows]):
            out = await inferrer.infer("75")
        trains = [r for r in out["relations"] if r["subtype"] == "trains_sector"][0]
        likely = [r for r in out["relations"] if r["subtype"] == "likely_trains"][0]
        assert trains["confidence"] == 0.65  # capped
        assert likely["confidence"] == 0.60  # capped


# ===========================================================================
# 7. SupplyChainInferrer
# ===========================================================================


class TestSupplyChainInferrer:
    @pytest.fixture
    def inferrer(self):
        return SupplyChainInferrer()

    async def test_no_contracts_returns_empty(self, inferrer):
        with _patch_db(fetch_results=[]):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    async def test_single_supplier_no_relation(self, inferrer):
        rows = [{"buyer_ext": "BUY:1", "buyer_name": "Mairie",
                 "supplier_ext": "SUP:1", "supplier_name": "A"}]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        assert out["relations"] == []

    async def test_co_supplier_one_shared_buyer(self, inferrer):
        rows = [
            {"buyer_ext": "BUY:1", "buyer_name": "Mairie",
             "supplier_ext": "SUP:1", "supplier_name": "A"},
            {"buyer_ext": "BUY:1", "buyer_name": "Mairie",
             "supplier_ext": "SUP:2", "supplier_name": "B"},
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1
        rel = out["relations"][0]
        assert rel["subtype"] == "co_supplier"
        assert rel["confidence"] == 0.70
        assert rel["evidence"]["shared_buyer_count"] == 1

    async def test_co_supplier_two_shared_buyers(self, inferrer):
        rows = [
            {"buyer_ext": "BUY:1", "buyer_name": "M1", "supplier_ext": "SUP:1",
             "supplier_name": "A"},
            {"buyer_ext": "BUY:1", "buyer_name": "M1", "supplier_ext": "SUP:2",
             "supplier_name": "B"},
            {"buyer_ext": "BUY:2", "buyer_name": "M2", "supplier_ext": "SUP:1",
             "supplier_name": "A"},
            {"buyer_ext": "BUY:2", "buyer_name": "M2", "supplier_ext": "SUP:2",
             "supplier_name": "B"},
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1
        assert out["relations"][0]["confidence"] == 0.80
        assert out["relations"][0]["evidence"]["shared_buyer_count"] == 2

    async def test_three_plus_shared_buyers_confidence_085(self, inferrer):
        rows = []
        for b in ("BUY:1", "BUY:2", "BUY:3"):
            rows.append({"buyer_ext": b, "buyer_name": b, "supplier_ext": "SUP:1",
                         "supplier_name": "A"})
            rows.append({"buyer_ext": b, "buyer_name": b, "supplier_ext": "SUP:2",
                         "supplier_name": "B"})
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        assert out["relations"][0]["confidence"] == 0.85

    async def test_max_suppliers_cap(self, inferrer):
        # one buyer with 25 suppliers -> capped at MAX_SUPPLIERS_PER_BUYER (20)
        rows = [
            {"buyer_ext": "BUY:1", "buyer_name": "M",
             "supplier_ext": f"SUP:{i}", "supplier_name": f"S{i}"}
            for i in range(25)
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        # combinations of 20 = 190 pairs
        assert len(out["relations"]) == 190


# ===========================================================================
# 8. DirectorLinkInferrer
# ===========================================================================


class TestDirectorLinkInferrer:
    @pytest.fixture
    def inferrer(self):
        return DirectorLinkInferrer()

    async def test_no_dirigeants_returns_empty(self, inferrer):
        with _patch_db(fetch_results=[]):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    async def test_shared_director_creates_relation(self, inferrer):
        dirigeant = {"nom": "DUPONT", "prenoms": "Jean", "annee_naissance": 1970,
                     "qualite": "Gerant"}
        rows = [
            {"external_id": "SIREN:1", "name": "Co A", "metadata": {"dirigeants": [dirigeant]}},
            {"external_id": "SIREN:2", "name": "Co B", "metadata": {"dirigeants": [dirigeant]}},
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1
        rel = out["relations"][0]
        assert rel["subtype"] == "shared_director"
        # 2 enterprises -> 0.85 base
        assert rel["confidence"] == 0.85
        assert rel["evidence"]["director_display"] == "dupont jean"

    async def test_metadata_as_json_string(self, inferrer):
        d = '{"dirigeants": [{"nom": "MARTIN", "prenoms": "Luc", "annee_naissance": 1980}]}'
        rows = [
            {"external_id": "SIREN:1", "name": "A", "metadata": d},
            {"external_id": "SIREN:2", "name": "B", "metadata": d},
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1

    async def test_bad_json_and_nonsense_metadata_handled(self, inferrer):
        d = {"dirigeants": [{"nom": "DUPONT", "prenoms": "Jean", "annee_naissance": 1970}]}
        rows = [
            {"external_id": "SIREN:1", "name": "Bad", "metadata": "{not json"},   # bad str
            {"external_id": "SIREN:2", "name": "Num", "metadata": 12345},          # non-dict
            {"external_id": "SIREN:3", "name": "OK1", "metadata": d},
            {"external_id": "SIREN:4", "name": "OK2", "metadata": d},
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        # bad/non-dict metadata -> empty dirigeants, only OK1<->OK2 paired
        assert len(out["relations"]) == 1

    async def test_director_normalizes_to_empty_skipped(self, inferrer):
        # nom normalizes to "" (too short after normalization) -> skipped
        rows = [
            {"external_id": "SIREN:1", "name": "A",
             "metadata": {"dirigeants": [{"nom": "ab", "prenoms": "cd"}]}},
            {"external_id": "SIREN:2", "name": "B",
             "metadata": {"dirigeants": [{"nom": "ab", "prenoms": "cd"}]}},
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        assert out["relations"] == []

    async def test_different_birth_year_not_matched(self, inferrer):
        rows = [
            {"external_id": "SIREN:1", "name": "A",
             "metadata": {"dirigeants": [{"nom": "X", "prenoms": "Y", "annee_naissance": 1970}]}},
            {"external_id": "SIREN:2", "name": "B",
             "metadata": {"dirigeants": [{"nom": "X", "prenoms": "Y", "annee_naissance": 1990}]}},
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        assert out["relations"] == []

    async def test_missing_nom_or_prenom_skipped(self, inferrer):
        rows = [
            {"external_id": "SIREN:1", "name": "A",
             "metadata": {"dirigeants": [{"nom": "", "prenoms": "Y"}]}},
            {"external_id": "SIREN:2", "name": "B",
             "metadata": {"dirigeants": [{"nom": "X", "prenoms": ""}]}},
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        assert out["relations"] == []

    async def test_confidence_scales_and_caps(self, inferrer):
        d = {"nom": "DUPONT", "prenoms": "Jean", "annee_naissance": 1970}
        rows = [
            {"external_id": f"SIREN:{i}", "name": f"Co {i}", "metadata": {"dirigeants": [d]}}
            for i in range(5)
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        # 5 enterprises -> 0.85 + 3*0.03 = 0.94, all pairs C(5,2)=10
        assert len(out["relations"]) == 10
        for rel in out["relations"]:
            assert rel["confidence"] == pytest.approx(0.94)

    async def test_too_many_enterprises_skipped(self, inferrer):
        d = {"nom": "DUPONT", "prenoms": "Jean", "annee_naissance": 1970}
        rows = [
            {"external_id": f"SIREN:{i}", "name": f"Co {i}", "metadata": {"dirigeants": [d]}}
            for i in range(12)  # > MAX_ENTERPRISES_PER_DIRECTOR (10)
        ]
        with _patch_db(fetch_results=rows):
            out = await inferrer.infer("75")
        assert out["relations"] == []


# ===========================================================================
# 9. ProximityInferrer (mocks BanAdapter HTTP client)
# ===========================================================================


class TestProximityInferrer:
    @pytest.fixture
    def inferrer(self):
        return ProximityInferrer()

    async def test_no_rows_returns_empty(self, inferrer):
        with _patch_db(fetch_results=[]):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    def _patch_ban(self, geocode_side_effect):
        mock_ban = MagicMock()
        mock_ban.geocode = AsyncMock(side_effect=geocode_side_effect)
        mock_cls = MagicMock(return_value=mock_ban)
        return patch(
            "src.infrastructure.datasources.adapters.ban.BanAdapter", mock_cls
        ), mock_ban

    async def test_close_actors_create_proximity(self, inferrer):
        rows = [
            {"id": 1, "external_id": "A:1", "name": "Alpha", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
            {"id": 2, "external_id": "A:2", "name": "Beta", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
        ]
        # Two points ~100m apart
        geocodes = [
            {"lat": 48.8566, "lon": 2.3522, "score": 0.9, "label": "Alpha"},
            {"lat": 48.8575, "lon": 2.3522, "score": 0.9, "label": "Beta"},
        ]
        ban_patch, _ = self._patch_ban(geocodes)
        with _patch_db(fetch_results=rows), ban_patch, patch(
            f"{MODULE}.asyncio.sleep", new=AsyncMock()
        ):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1
        rel = out["relations"][0]
        assert rel["subtype"] == "geographic_proximity"
        # ~100m < 200m -> high confidence 0.55
        assert rel["confidence"] == 0.55
        assert rel["weight"] > 0

    async def test_medium_distance_low_confidence(self, inferrer):
        rows = [
            {"id": 1, "external_id": "A:1", "name": "Alpha", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
            {"id": 2, "external_id": "A:2", "name": "Beta", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
        ]
        # ~330m apart (between 200 and 500m)
        geocodes = [
            {"lat": 48.8566, "lon": 2.3522, "score": 0.9, "label": "Alpha"},
            {"lat": 48.8596, "lon": 2.3522, "score": 0.9, "label": "Beta"},
        ]
        ban_patch, _ = self._patch_ban(geocodes)
        with _patch_db(fetch_results=rows), ban_patch, patch(
            f"{MODULE}.asyncio.sleep", new=AsyncMock()
        ):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1
        assert out["relations"][0]["confidence"] == 0.35

    async def test_far_apart_no_relation(self, inferrer):
        rows = [
            {"id": 1, "external_id": "A:1", "name": "Alpha", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
            {"id": 2, "external_id": "A:2", "name": "Beta", "actor_type": "enterprise",
             "metadata": {"ville": "Lyon", "code_postal": "69001"}},
        ]
        geocodes = [
            {"lat": 48.8566, "lon": 2.3522, "score": 0.9, "label": "Alpha"},
            {"lat": 45.7640, "lon": 4.8357, "score": 0.9, "label": "Beta"},
        ]
        ban_patch, _ = self._patch_ban(geocodes)
        with _patch_db(fetch_results=rows), ban_patch, patch(
            f"{MODULE}.asyncio.sleep", new=AsyncMock()
        ):
            out = await inferrer.infer("75")
        assert out["relations"] == []

    async def test_low_geocode_score_dropped(self, inferrer):
        rows = [
            {"id": 1, "external_id": "A:1", "name": "Alpha", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
            {"id": 2, "external_id": "A:2", "name": "Beta", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
        ]
        # both below score 0.4 -> dropped, fewer than 2 geocoded -> empty
        geocodes = [
            {"lat": 48.8566, "lon": 2.3522, "score": 0.2, "label": "Alpha"},
            {"lat": 48.8575, "lon": 2.3522, "score": 0.1, "label": "Beta"},
        ]
        ban_patch, _ = self._patch_ban(geocodes)
        with _patch_db(fetch_results=rows), ban_patch, patch(
            f"{MODULE}.asyncio.sleep", new=AsyncMock()
        ):
            out = await inferrer.infer("75")
        assert out["relations"] == []

    async def test_geocode_exception_handled(self, inferrer):
        rows = [
            {"id": 1, "external_id": "A:1", "name": "Alpha", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
            {"id": 2, "external_id": "A:2", "name": "Beta", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
        ]
        ban_patch, _ = self._patch_ban([RuntimeError("boom"), RuntimeError("boom")])
        with _patch_db(fetch_results=rows), ban_patch, patch(
            f"{MODULE}.asyncio.sleep", new=AsyncMock()
        ):
            out = await inferrer.infer("75")
        # exceptions swallowed, nothing geocoded -> empty
        assert out["relations"] == []

    async def test_bad_and_nondict_metadata_skipped(self, inferrer):
        rows = [
            {"id": 1, "external_id": "A:1", "name": "Bad", "actor_type": "enterprise",
             "metadata": "{not json"},   # bad json -> continue
            {"id": 2, "external_id": "A:2", "name": "Num", "actor_type": "enterprise",
             "metadata": 999},            # non-dict -> continue
            {"id": 3, "external_id": "A:3", "name": "OK", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
        ]
        geocodes = [{"lat": 48.8566, "lon": 2.3522, "score": 0.9, "label": "OK"}]
        ban_patch, mock_ban = self._patch_ban(geocodes)
        with _patch_db(fetch_results=rows), ban_patch, patch(
            f"{MODULE}.asyncio.sleep", new=AsyncMock()
        ):
            out = await inferrer.infer("75")
        assert out["relations"] == []
        # only the valid actor triggered a geocode call
        assert mock_ban.geocode.await_count == 1

    async def test_short_query_skipped(self, inferrer):
        # ville present but resulting query too short (<3 chars) -> skipped
        rows = [
            {"id": 1, "external_id": "A:1", "name": "X", "actor_type": "enterprise",
             "metadata": {"ville": "P"}},
            {"id": 2, "external_id": "A:2", "name": "Y", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
        ]
        geocodes = [{"lat": 48.8566, "lon": 2.3522, "score": 0.9, "label": "Y"}]
        ban_patch, mock_ban = self._patch_ban(geocodes)
        with _patch_db(fetch_results=rows), ban_patch, patch(
            f"{MODULE}.asyncio.sleep", new=AsyncMock()
        ):
            out = await inferrer.infer("75")
        assert out["relations"] == []
        assert mock_ban.geocode.await_count == 1

    async def test_max_geocode_calls_cap(self, inferrer):
        rows = [
            {"id": i, "external_id": f"A:{i}", "name": f"N{i}", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}}
            for i in range(60)  # > MAX_GEOCODE_CALLS (50)
        ]
        geocodes = [
            {"lat": 48.8566, "lon": 2.3522, "score": 0.2, "label": f"N{i}"}  # low score, dropped
            for i in range(60)
        ]
        ban_patch, mock_ban = self._patch_ban(geocodes)
        with _patch_db(fetch_results=rows), ban_patch, patch(
            f"{MODULE}.asyncio.sleep", new=AsyncMock()
        ):
            await inferrer.infer("75")
        assert mock_ban.geocode.await_count == 50

    async def test_actor_without_city_or_cp_skipped(self, inferrer):
        rows = [
            {"id": 1, "external_id": "A:1", "name": "Alpha", "actor_type": "enterprise",
             "metadata": {"adresse": "1 rue X"}},  # no ville/cp -> skipped
            {"id": 2, "external_id": "A:2", "name": "Beta", "actor_type": "enterprise",
             "metadata": {"ville": "Paris", "code_postal": "75001"}},
        ]
        geocodes = [{"lat": 48.8566, "lon": 2.3522, "score": 0.9, "label": "Beta"}]
        ban_patch, mock_ban = self._patch_ban(geocodes)
        with _patch_db(fetch_results=rows), ban_patch, patch(
            f"{MODULE}.asyncio.sleep", new=AsyncMock()
        ):
            out = await inferrer.infer("75")
        # only 1 geocode call (the second actor); <2 geocoded -> empty
        assert out["relations"] == []
        assert mock_ban.geocode.await_count == 1


# ===========================================================================
# 10. PoleMembershipInferrer
# ===========================================================================


class TestPoleMembershipInferrer:
    @pytest.fixture
    def inferrer(self):
        return PoleMembershipInferrer()

    async def test_no_poles_returns_empty(self, inferrer):
        with _patch_db(fetch_results=[[], []]):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    async def test_poles_without_naf_sections_skipped(self, inferrer):
        pole_rows = [{"external_id": "POLE:1", "name": "P",
                      "metadata": {"sectors": ["not-a-letter"]}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "E", "metadata": {"naf": "62.01Z"}}]
        with _patch_db(fetch_results=[pole_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert out["relations"] == []

    async def test_enterprise_matched_to_pole(self, inferrer):
        pole_rows = [{"external_id": "POLE:1", "name": "Tech Pole",
                      "metadata": {"sectors": ["J", "M"]}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "Soft",
                     "metadata": {"naf": "62.01Z"}}]  # section J
        with _patch_db(fetch_results=[pole_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1
        rel = out["relations"][0]
        assert rel["subtype"] == "pole_member_inferred"
        assert rel["confidence"] == 0.50  # naf_code source
        assert rel["target_actor_external_id"] == "POLE:1"

    async def test_cpv_source_lower_confidence(self, inferrer):
        pole_rows = [{"external_id": "POLE:1", "name": "P",
                      "metadata": {"sectors": ["F"]}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "Build",
                     "metadata": {"cpv_code": ["45000000"]}}]  # CPV->F
        with _patch_db(fetch_results=[pole_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert out["relations"][0]["confidence"] == 0.35

    async def test_sectors_as_comma_string(self, inferrer):
        pole_rows = [{"external_id": "POLE:1", "name": "P",
                      "metadata": {"sectors": "J, M"}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "Soft",
                     "metadata": {"naf": "62.01Z"}}]
        with _patch_db(fetch_results=[pole_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1

    async def test_non_matching_section_no_relation(self, inferrer):
        pole_rows = [{"external_id": "POLE:1", "name": "P", "metadata": {"sectors": ["A"]}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "Soft", "metadata": {"naf": "62.01Z"}}]
        with _patch_db(fetch_results=[pole_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert out["relations"] == []

    async def test_pole_bad_json_and_nondict_metadata_skipped(self, inferrer):
        pole_rows = [
            {"external_id": "POLE:1", "name": "Bad", "metadata": "{not json"},
            {"external_id": "POLE:2", "name": "Num", "metadata": 7},
        ]
        ent_rows = [{"external_id": "SIREN:1", "name": "E", "metadata": {"naf": "62.01Z"}}]
        with _patch_db(fetch_results=[pole_rows, ent_rows]):
            out = await inferrer.infer("75")
        # poles parse to empty meta -> no naf_sections -> skipped -> no poles left
        assert out["relations"] == []

    async def test_enterprise_bad_json_metadata_skipped(self, inferrer):
        pole_rows = [{"external_id": "POLE:1", "name": "P", "metadata": {"sectors": ["J"]}}]
        ent_rows = [
            {"external_id": "SIREN:1", "name": "Bad", "metadata": "{not json"},   # skipped
            {"external_id": "SIREN:2", "name": "Num", "metadata": 5},             # skipped
            {"external_id": "SIREN:3", "name": "OK", "metadata": {"naf": "62.01Z"}},
        ]
        with _patch_db(fetch_results=[pole_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1
        assert out["relations"][0]["source_actor_external_id"] == "SIREN:3"

    async def test_cap_per_pole(self, inferrer):
        pole_rows = [{"external_id": "POLE:1", "name": "P", "metadata": {"sectors": ["J"]}}]
        ent_rows = [
            {"external_id": f"SIREN:{i}", "name": f"E{i}", "metadata": {"naf": "62.01Z"}}
            for i in range(30)
        ]
        with _patch_db(fetch_results=[pole_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 15  # _MAX_PER_POLE


# ===========================================================================
# 11. EPCIBelongsInferrer
# ===========================================================================


class TestEPCIBelongsInferrer:
    @pytest.fixture
    def inferrer(self):
        return EPCIBelongsInferrer()

    async def test_no_epci_returns_empty(self, inferrer):
        with _patch_db(fetch_results=[[], []]):
            assert await inferrer.infer("13") == {"actors": [], "relations": []}

    async def test_commune_code_exact_match(self, inferrer):
        epci_rows = [{"external_id": "EPCI:1", "name": "Metropole",
                      "metadata": {"communes": ["13001", "13055"]}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "E",
                     "metadata": {"commune_code": "13055"}}]
        with _patch_db(fetch_results=[epci_rows, ent_rows]):
            out = await inferrer.infer("13")
        assert len(out["relations"]) == 1
        rel = out["relations"][0]
        assert rel["subtype"] == "belongs_to_epci_inferred"
        assert rel["confidence"] == 0.65
        assert rel["evidence"]["method"] == "commune_code_exact"

    async def test_postal_code_match_lower_confidence(self, inferrer):
        epci_rows = [{"external_id": "EPCI:1", "name": "Metropole",
                      "metadata": {"communes": ["13001"], "codes_postaux": ["13100"]}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "E",
                     "metadata": {"code_postal": "13100"}}]
        with _patch_db(fetch_results=[epci_rows, ent_rows]):
            out = await inferrer.infer("13")
        assert out["relations"][0]["confidence"] == 0.40
        assert out["relations"][0]["evidence"]["method"] == "postal_code_match"

    async def test_no_match_no_relation(self, inferrer):
        epci_rows = [{"external_id": "EPCI:1", "name": "M",
                      "metadata": {"communes": ["13001"]}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "E",
                     "metadata": {"commune_code": "99999"}}]
        with _patch_db(fetch_results=[epci_rows, ent_rows]):
            out = await inferrer.infer("13")
        assert out["relations"] == []

    async def test_epci_without_geo_metadata_skipped(self, inferrer):
        epci_rows = [{"external_id": "EPCI:1", "name": "M", "metadata": {}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "E",
                     "metadata": {"commune_code": "13055"}}]
        with _patch_db(fetch_results=[epci_rows, ent_rows]):
            out = await inferrer.infer("13")
        assert out["relations"] == []

    async def test_communes_as_json_string(self, inferrer):
        epci_rows = [{"external_id": "EPCI:1", "name": "M",
                      "metadata": {"communes": '["13055"]'}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "E",
                     "metadata": {"commune_code": "13055"}}]
        with _patch_db(fetch_results=[epci_rows, ent_rows]):
            out = await inferrer.infer("13")
        assert len(out["relations"]) == 1

    async def test_epci_bad_json_and_nondict_metadata_skipped(self, inferrer):
        epci_rows = [
            {"external_id": "EPCI:1", "name": "Bad", "metadata": "{not json"},
            {"external_id": "EPCI:2", "name": "Num", "metadata": 3},
        ]
        ent_rows = [{"external_id": "SIREN:1", "name": "E",
                     "metadata": {"commune_code": "13055"}}]
        with _patch_db(fetch_results=[epci_rows, ent_rows]):
            out = await inferrer.infer("13")
        assert out["relations"] == []

    async def test_epci_postal_codes_as_json_string(self, inferrer):
        epci_rows = [{"external_id": "EPCI:1", "name": "M",
                      "metadata": {"codes_postaux": '["13100"]'}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "E",
                     "metadata": {"code_postal": "13100"}}]
        with _patch_db(fetch_results=[epci_rows, ent_rows]):
            out = await inferrer.infer("13")
        assert len(out["relations"]) == 1
        assert out["relations"][0]["confidence"] == 0.40

    async def test_enterprise_bad_json_or_no_geo_skipped(self, inferrer):
        epci_rows = [{"external_id": "EPCI:1", "name": "M",
                      "metadata": {"communes": ["13055"]}}]
        ent_rows = [
            {"external_id": "SIREN:1", "name": "Bad", "metadata": "{not json"},  # skipped
            {"external_id": "SIREN:2", "name": "Num", "metadata": 9},            # skipped
            {"external_id": "SIREN:3", "name": "NoGeo", "metadata": {"naf": "x"}},  # no commune/cp
        ]
        with _patch_db(fetch_results=[epci_rows, ent_rows]):
            out = await inferrer.infer("13")
        assert out["relations"] == []

    async def test_enterprise_matches_only_first_epci(self, inferrer):
        # two EPCIs both containing the commune; enterprise should break after first
        epci_rows = [
            {"external_id": "EPCI:1", "name": "M1", "metadata": {"communes": ["13055"]}},
            {"external_id": "EPCI:2", "name": "M2", "metadata": {"communes": ["13055"]}},
        ]
        ent_rows = [{"external_id": "SIREN:1", "name": "E",
                     "metadata": {"commune_code": "13055"}}]
        with _patch_db(fetch_results=[epci_rows, ent_rows]):
            out = await inferrer.infer("13")
        assert len(out["relations"]) == 1


# ===========================================================================
# 12. IncubatorMatchInferrer
# ===========================================================================


class TestIncubatorMatchInferrer:
    @pytest.fixture
    def inferrer(self):
        return IncubatorMatchInferrer()

    async def test_no_incubators_returns_empty(self, inferrer):
        with _patch_db(fetch_results=[[], []]):
            assert await inferrer.infer("75") == {"actors": [], "relations": []}

    async def test_young_by_date_creation(self, inferrer):
        incub_rows = [{"external_id": "INC:1", "name": "Station F",
                       "metadata": {"themes": ["numérique"]}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "Startup",
                     "metadata": {"date_creation": "2022-01-01", "naf_section": "J",
                                  "tranche_effectif": "52"}}]
        with _patch_db(fetch_results=[incub_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1
        rel = out["relations"][0]
        assert rel["subtype"] == "incubated_by_inferred"
        # thematic match J in compatible_naf -> 0.55
        assert rel["confidence"] == 0.55
        assert rel["evidence"]["thematic_match"] is True

    async def test_young_by_small_headcount_no_thematic(self, inferrer):
        incub_rows = [{"external_id": "INC:1", "name": "Inc",
                       "metadata": {"themes": ["sante"]}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "Tiny",
                     "metadata": {"tranche_effectif": "01", "naf_section": "G"}}]
        with _patch_db(fetch_results=[incub_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1
        # no thematic match (G not in {Q,M}) -> 0.35
        assert out["relations"][0]["confidence"] == 0.35
        assert out["relations"][0]["evidence"]["thematic_match"] is False

    async def test_young_by_keyword(self, inferrer):
        incub_rows = [{"external_id": "INC:1", "name": "Inc", "metadata": {"themes": []}}]
        # big headcount and old creation, but name has "startup" keyword
        ent_rows = [{"external_id": "SIREN:1", "name": "Cool Startup",
                     "metadata": {"date_creation": "2010", "tranche_effectif": "52"}}]
        with _patch_db(fetch_results=[incub_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 1

    async def test_no_young_enterprises_returns_empty(self, inferrer):
        incub_rows = [{"external_id": "INC:1", "name": "Inc", "metadata": {"themes": []}}]
        # old + large + no keyword -> not young
        ent_rows = [{"external_id": "SIREN:1", "name": "OldCorp",
                     "metadata": {"date_creation": "1990", "tranche_effectif": "52"}}]
        with _patch_db(fetch_results=[incub_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert out["relations"] == []

    async def test_cap_per_incubator(self, inferrer):
        incub_rows = [{"external_id": "INC:1", "name": "Inc", "metadata": {"themes": []}}]
        ent_rows = [
            {"external_id": f"SIREN:{i}", "name": f"S{i}",
             "metadata": {"tranche_effectif": "01"}}
            for i in range(20)
        ]
        with _patch_db(fetch_results=[incub_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert len(out["relations"]) == 8  # _MAX_PER_INCUBATOR

    async def test_confidence_within_l2_bounds(self, inferrer):
        incub_rows = [{"external_id": "INC:1", "name": "Inc",
                       "metadata": {"themes": ["numerique"]}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "S",
                     "metadata": {"tranche_effectif": "01", "naf_section": "J"}}]
        with _patch_db(fetch_results=[incub_rows, ent_rows]):
            out = await inferrer.infer("75")
        for rel in out["relations"]:
            assert 0.35 <= rel["confidence"] <= 0.79

    async def test_themes_as_comma_string(self, inferrer):
        incub_rows = [{"external_id": "INC:1", "name": "Inc",
                       "metadata": {"themes": "numerique, sante"}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "S",
                     "metadata": {"tranche_effectif": "01", "naf_section": "J"}}]
        with _patch_db(fetch_results=[incub_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert out["relations"][0]["confidence"] == 0.55  # J matches numerique

    async def test_themes_nonlist_coerced_to_empty(self, inferrer):
        incub_rows = [{"external_id": "INC:1", "name": "Inc", "metadata": {"themes": 123}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "S",
                     "metadata": {"tranche_effectif": "01", "naf_section": "J"}}]
        with _patch_db(fetch_results=[incub_rows, ent_rows]):
            out = await inferrer.infer("75")
        # no themes -> base proximity confidence 0.35
        assert out["relations"][0]["confidence"] == 0.35

    async def test_naf_section_from_activite_principale_first_letter(self, inferrer):
        # naf_section missing, derived from first letter of activite_principale code
        incub_rows = [{"external_id": "INC:1", "name": "Inc",
                       "metadata": {"themes": ["numerique"]}}]
        ent_rows = [{"external_id": "SIREN:1", "name": "S",
                     "metadata": {"tranche_effectif": "01", "activite_principale": "J62.01"}}]
        with _patch_db(fetch_results=[incub_rows, ent_rows]):
            out = await inferrer.infer("75")
        assert out["relations"][0]["evidence"]["enterprise_naf_section"] == "J"
        assert out["relations"][0]["confidence"] == 0.55
