"""Unit tests for the concrete L1 relation extractors.

Sibling file ``test_relation_extractors_utils.py`` already covers the pure
helpers (_parse_raw_data, _stable_uuid, _actor_id, _relation_id,
_classify_nature_juridique, _DEPT_NAMES, BaseExtractor abstract contract) and
the SireneExtractor happy path. This file therefore focuses on the *other*
extractor classes, the EXTRACTORS registry, and the harder branches of each
``extract()`` method.

All I/O is mocked:

- DB extractors patch ``acquire_conn`` (same pattern as the sibling file).
- Adapter-backed extractors patch the adapter class at its source module.
- httpx-backed extractors patch ``httpx.AsyncClient`` inside the
  relation_extractors module namespace.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.application.services.relation_extractors as re_mod
from src.application.services.relation_extractors import (
    ADEMEExtractor,
    BaseExtractor,
    BodaccExtractor,
    BoampExtractor,
    DVFExtractor,
    EPCIExtractor,
    EXTRACTORS,
    FranceTravailExtractor,
    INSEELocalExtractor,
    IncubatorExtractor,
    NatureJuridiqueExtractor,
    OFGLExtractor,
    PolesExtractor,
    QualiopiExtractor,
    RnaExtractor,
    SireneAddressEnricher,
    SireneDirigeantsEnricher,
    SubventionsExtractor,
    TerritorialStructuresExtractor,
    UrssafEffectifsEnricher,
    _BODACC_SUBTYPE_MAP,
    _POLES_COMPETITIVITE,
)

MODULE = "src.application.services.relation_extractors"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def make_conn(fetch_results):
    """Build a mock connection whose ``fetch`` returns queued result lists.

    ``fetch_results`` may be a single list (returned for every fetch call) or
    a list-of-lists (each successive fetch returns the next list). Returns
    ``(ctx_factory, mock_conn)``.
    """
    mock_conn = MagicMock()
    if fetch_results and isinstance(fetch_results[0], list):
        mock_conn.fetch = AsyncMock(side_effect=fetch_results)
    else:
        mock_conn.fetch = AsyncMock(return_value=fetch_results)

    @asynccontextmanager
    async def _ctx():
        yield mock_conn

    return _ctx, mock_conn


def make_response(status_code=200, json_data=None, text=""):
    """Build a mock httpx Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data if json_data is not None else {})
    resp.text = text
    return resp


def make_http_client(get_side_effect=None, get_return=None):
    """Build a mock object that works as ``async with httpx.AsyncClient(...)``.

    ``get_side_effect``/``get_return`` configure the async ``get`` method.
    Returns a factory suitable for ``patch(..., new=factory)``.
    """
    client = MagicMock()
    if get_side_effect is not None:
        client.get = AsyncMock(side_effect=get_side_effect)
    else:
        client.get = AsyncMock(return_value=get_return)

    class _ClientFactory:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return client

        async def __aexit__(self, *exc):
            return False

    return _ClientFactory, client


# ===========================================================================
# BodaccExtractor
# ===========================================================================


class TestBodaccExtractor:
    @pytest.fixture
    def extractor(self):
        return BodaccExtractor()

    async def test_no_rows_returns_empty(self, extractor):
        ctx, _ = make_conn([])
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_signal_without_siren_skipped(self, extractor):
        rows = [
            {
                "raw_data": {"ville": "Paris"},  # no siren
                "metric_name": "creation",
                "metric_value": 1,
                "event_date": "2026-01-01",
                "collected_at": "2026-01-01T10:00:00",
            }
        ]
        ctx, _ = make_conn(rows)
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        # Only the territory actor, no enterprise, no relations
        assert {a["type"] for a in result["actors"]} == {"territory"}
        assert result["relations"] == []

    async def test_creation_event_high_confidence(self, extractor):
        rows = [
            {
                "raw_data": {
                    "siren": "123456789",
                    "commercant": "Boulangerie Test",
                    "famille": "creation",
                    "ville": "Paris",
                    "cp": "75001",
                    "tribunal": "Paris",
                    "id": "BOD-1",
                },
                "metric_name": "",
                "metric_value": 1,
                "event_date": "2026-01-01",
                "collected_at": "2026-01-01T10:00:00",
            }
        ]
        ctx, _ = make_conn(rows)
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")

        ent = [a for a in result["actors"] if a["type"] == "enterprise"][0]
        assert ent["name"] == "Boulangerie Test"
        assert ent["metadata"]["ville"] == "Paris"
        assert ent["metadata"]["code_postal"] == "75001"
        assert ent["metadata"]["tribunal"] == "Paris"
        rel = result["relations"][0]
        assert rel["subtype"] == "event_creation"
        assert rel["confidence"] == 0.90
        assert rel["source_ref"] == "bodacc:BOD-1"  # uses bodacc id
        # event history tracked
        assert ent["metadata"]["bodacc_events"][0]["type"] == "event_creation"

    async def test_procedure_collective_confidence(self, extractor):
        rows = [
            {
                "raw_data": {"siren": "111", "famille": "collective"},
                "metric_name": "",
                "metric_value": 1,
                "event_date": None,
                "collected_at": "2026-01-01T10:00:00",
            }
        ]
        ctx, _ = make_conn(rows)
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        rel = result["relations"][0]
        assert rel["subtype"] == "event_procedure_collective"
        assert rel["confidence"] == 0.95
        # No bodacc id -> source_ref built from siren+metric+dept
        assert rel["source_ref"] == "bodacc:111::75"

    async def test_metric_name_takes_priority_over_famille(self, extractor):
        rows = [
            {
                "raw_data": {"siren": "222", "famille": "creation"},
                "metric_name": "liquidation_judiciaire",
                "metric_value": 1,
                "event_date": "2026-02-02",
                "collected_at": "2026-01-01T10:00:00",
            }
        ]
        ctx, _ = make_conn(rows)
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        rel = result["relations"][0]
        assert rel["subtype"] == "event_liquidation"
        assert rel["confidence"] == 0.95

    async def test_unknown_famille_builds_default_subtype(self, extractor):
        rows = [
            {
                "raw_data": {"siren": "333", "familleavis": "mystery"},
                "metric_name": "",
                "metric_value": 1,
                "event_date": "2026-02-02",
                "collected_at": "2026-01-01T10:00:00",
            }
        ]
        ctx, _ = make_conn(rows)
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        rel = result["relations"][0]
        assert rel["subtype"] == "event_mystery"
        assert rel["confidence"] == 0.85  # neither high nor medium bucket

    async def test_default_enterprise_name_when_no_commercant(self, extractor):
        rows = [
            {
                "raw_data": {"siren": "444"},
                "metric_name": "radiation",
                "metric_value": 1,
                "event_date": "2026-01-01",
                "collected_at": "2026-01-01T10:00:00",
            }
        ]
        ctx, _ = make_conn(rows)
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        ent = [a for a in result["actors"] if a["type"] == "enterprise"][0]
        assert ent["name"] == "Entreprise 444"

    async def test_event_history_capped_at_10(self, extractor):
        # 12 signals for the same SIREN -> at most 10 kept in metadata
        rows = [
            {
                "raw_data": {"siren": "555", "famille": "creation"},
                "metric_name": "",
                "metric_value": 1,
                "event_date": f"2026-01-{i:02d}",
                "collected_at": "2026-01-01T10:00:00",
            }
            for i in range(1, 13)
        ]
        ctx, _ = make_conn(rows)
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        ent = [a for a in result["actors"] if a["type"] == "enterprise"][0]
        assert len(ent["metadata"]["bodacc_events"]) == 10

    def test_subtype_map_has_expected_keys(self):
        assert _BODACC_SUBTYPE_MAP["creation"] == "event_creation"
        assert _BODACC_SUBTYPE_MAP["liquidation_judiciaire"] == "event_liquidation"


# ===========================================================================
# NatureJuridiqueExtractor
# ===========================================================================


class TestNatureJuridiqueExtractor:
    @pytest.fixture
    def extractor(self):
        return NatureJuridiqueExtractor()

    async def test_no_rows_returns_empty(self, extractor):
        ctx, _ = make_conn([])
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_reclassifies_association(self, extractor):
        rows = [
            {
                "external_id": "SIREN:111",
                "name": "Asso Test",
                "metadata": {"nature_juridique": "9210"},
            }
        ]
        ctx, _ = make_conn(rows)
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        actor = result["actors"][0]
        assert actor["type"] == "association"
        assert actor["metadata"]["original_type"] == "enterprise"
        assert actor["metadata"]["nature_juridique_label"] == "Association loi 1901"
        rel = result["relations"][0]
        assert rel["subtype"] == "operates_in"
        assert rel["target_actor_external_id"] == "DEPT:75"

    async def test_subtype_per_actor_type(self, extractor):
        rows = [
            {"external_id": "SIREN:1", "name": "A", "metadata": {"nature_juridique": "8510"}},
            {"external_id": "SIREN:2", "name": "B", "metadata": {"nature_juridique": "6411"}},
            {"external_id": "SIREN:3", "name": "C", "metadata": {"nature_juridique": "7210"}},
        ]
        ctx, _ = make_conn(rows)
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        subtypes = {r["source_actor_external_id"]: r["subtype"] for r in result["relations"]}
        assert subtypes["SIREN:1"] == "trains_in"  # formation
        assert subtypes["SIREN:2"] == "finances_in"  # financial
        assert subtypes["SIREN:3"] == "administers_in"  # institution

    async def test_unclassifiable_nj_skipped(self, extractor):
        rows = [
            {"external_id": "SIREN:9", "name": "X", "metadata": {"nature_juridique": "0000"}}
        ]
        ctx, _ = make_conn(rows)
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_non_dict_metadata_defaults_to_empty(self, extractor):
        rows = [
            {"external_id": "SIREN:7", "name": "Y", "metadata": "not-a-dict"}
        ]
        ctx, _ = make_conn(rows)
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        # meta becomes {} -> nj_code "" -> classification None -> skipped
        assert result == {"actors": [], "relations": []}


# ===========================================================================
# BoampExtractor (adapter-backed)
# ===========================================================================


class TestBoampExtractor:
    @pytest.fixture
    def extractor(self):
        return BoampExtractor()

    def _patch_adapter(self, records=None, raise_exc=False):
        adapter = MagicMock()
        if raise_exc:
            adapter.search = AsyncMock(side_effect=RuntimeError("api down"))
        else:
            adapter.search = AsyncMock(return_value=records or [])
        adapter._client = MagicMock()
        adapter._client.aclose = AsyncMock()
        return patch(
            "src.infrastructure.datasources.adapters.boamp.BoampAdapter",
            return_value=adapter,
        )

    async def test_api_exception_returns_empty(self, extractor):
        with self._patch_adapter(raise_exc=True):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_no_records_returns_empty(self, extractor):
        with self._patch_adapter(records=[]):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_awarded_contract_single_titulaire(self, extractor):
        records = [
            {
                "nom_acheteur": "Mairie de Paris",
                "titulaire": "Acme BTP",
                "id": "B-1",
                "objet": "Travaux",
                "cpv_code": "45000000",
                "date_publication": "2026-01-01",
            }
        ]
        with self._patch_adapter(records=records):
            result = await extractor.extract("75")
        types = {a["type"] for a in result["actors"]}
        assert "institution" in types and "enterprise" in types
        rel = result["relations"][0]
        assert rel["subtype"] == "awarded_contract"
        assert rel["source_actor_external_id"] == "BOAMP_BUYER:Mairie de Paris"
        assert rel["target_actor_external_id"] == "BOAMP_WINNER:Acme BTP"
        assert rel["source_ref"] == "boamp:B-1"

    async def test_multiple_titulaires_deduplicated(self, extractor):
        records = [
            {
                "nom_acheteur": "CD75",
                "titulaire": ["Win A", "Win A", "Win B", "", "  "],
                "id": "B-2",
            }
        ]
        with self._patch_adapter(records=records):
            result = await extractor.extract("75")
        winners = [a for a in result["actors"] if a["external_id"].startswith("BOAMP_WINNER")]
        names = sorted(w["name"] for w in winners)
        assert names == ["Win A", "Win B"]
        assert len(result["relations"]) == 2

    async def test_record_without_acheteur_skipped(self, extractor):
        records = [{"nom_acheteur": "", "titulaire": "X"}]
        with self._patch_adapter(records=records):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_record_with_no_valid_titulaire_skipped(self, extractor):
        records = [{"nom_acheteur": "Buyer", "titulaire": None}]
        with self._patch_adapter(records=records):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_source_ref_fallback_without_id(self, extractor):
        records = [{"nom_acheteur": "Buyer", "titulaire": "Winner"}]
        with self._patch_adapter(records=records):
            result = await extractor.extract("75")
        rel = result["relations"][0]
        assert rel["source_ref"].startswith("boamp:BOAMP_BUYER:Buyer->BOAMP_WINNER:Winner")


# ===========================================================================
# RnaExtractor (adapter-backed)
# ===========================================================================


class TestRnaExtractor:
    @pytest.fixture
    def extractor(self):
        return RnaExtractor()

    def _patch_adapter(self, records=None, raise_exc=False):
        adapter = MagicMock()
        if raise_exc:
            adapter.search_by_department = AsyncMock(side_effect=RuntimeError("boom"))
        else:
            adapter.search_by_department = AsyncMock(return_value=records or [])
        adapter.close = AsyncMock()
        return patch(
            "src.infrastructure.datasources.adapters.rna.RnaAdapter",
            return_value=adapter,
        )

    async def test_api_exception_returns_empty(self, extractor):
        with self._patch_adapter(raise_exc=True):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_no_records_returns_empty(self, extractor):
        with self._patch_adapter(records=[]):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_record_without_siren_skipped(self, extractor):
        with self._patch_adapter(records=[{"titre": "No SIREN"}]):
            result = await extractor.extract("75")
        assert {a["type"] for a in result["actors"]} == {"territory"}
        assert result["relations"] == []

    async def test_association_with_naf_creates_sector(self, extractor):
        records = [
            {
                "siren": "123",
                "titre": "Asso Verte",
                "activite_principale": "94.99Z",
                "nature_juridique": "9210",
                "nature_juridique_label": "Association loi 1901",
                "commune": "Paris",
                "code_postal": "75001",
                "date_creation": "2020-01-01",
            }
        ]
        with self._patch_adapter(records=records):
            result = await extractor.extract("75")
        types = {a["type"] for a in result["actors"]}
        assert {"territory", "association", "sector"} <= types
        assoc = [a for a in result["actors"] if a["type"] == "association"][0]
        assert assoc["metadata"]["commune"] == "Paris"
        assert assoc["metadata"]["activite_principale"] == "94.99Z"
        subtypes = {r["subtype"] for r in result["relations"]}
        assert {"operates_in", "belongs_to_sector"} <= subtypes

    async def test_association_without_naf_no_sector(self, extractor):
        records = [{"siren": "456", "titre": "Asso Sans NAF"}]
        with self._patch_adapter(records=records):
            result = await extractor.extract("75")
        types = {a["type"] for a in result["actors"]}
        assert "sector" not in types
        subtypes = {r["subtype"] for r in result["relations"]}
        assert subtypes == {"operates_in"}

    async def test_title_fallback_chain(self, extractor):
        records = [{"siren": "789", "nom_raison_sociale": "Raison Sociale"}]
        with self._patch_adapter(records=records):
            result = await extractor.extract("75")
        assoc = [a for a in result["actors"] if a["type"] == "association"][0]
        assert assoc["name"] == "Raison Sociale"


# ===========================================================================
# SubventionsExtractor (adapter-backed + _multi_search)
# ===========================================================================


class TestSubventionsExtractor:
    @pytest.fixture
    def extractor(self):
        return SubventionsExtractor()

    async def test_api_exception_returns_empty(self, extractor):
        adapter = MagicMock()
        adapter.search = AsyncMock(side_effect=RuntimeError("down"))
        adapter._client = MagicMock(aclose=AsyncMock())
        with patch(
            "src.infrastructure.datasources.adapters.subventions.SubventionsAdapter",
            return_value=adapter,
        ):
            # _multi_search swallows per-term exceptions, so to hit the
            # outer except we make _multi_search itself raise.
            with patch.object(extractor, "_multi_search", AsyncMock(side_effect=RuntimeError())):
                result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_no_datasets_returns_empty(self, extractor):
        adapter = MagicMock()
        adapter._client = MagicMock(aclose=AsyncMock())
        with patch(
            "src.infrastructure.datasources.adapters.subventions.SubventionsAdapter",
            return_value=adapter,
        ):
            with patch.object(extractor, "_multi_search", AsyncMock(return_value=[])):
                result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_funder_actor_and_relation(self, extractor):
        datasets = [
            {
                "organization": "Region IDF",
                "title": "Subventions sport",
                "id": "ds-1",
                "organization_id": "org-1",
            }
        ]
        adapter = MagicMock()
        adapter._client = MagicMock(aclose=AsyncMock())
        with patch(
            "src.infrastructure.datasources.adapters.subventions.SubventionsAdapter",
            return_value=adapter,
        ):
            with patch.object(extractor, "_multi_search", AsyncMock(return_value=datasets)):
                result = await extractor.extract("75")
        funder = [a for a in result["actors"] if a["external_id"].startswith("FUNDER:")][0]
        assert funder["name"] == "Region IDF"
        assert funder["metadata"]["role"] == "financeur_public"
        rel = result["relations"][0]
        assert rel["subtype"] == "funded_by"
        assert rel["source_ref"] == "subventions:ds-1"

    async def test_duplicate_orgs_deduplicated(self, extractor):
        datasets = [
            {"organization": "Ville X", "id": "1"},
            {"organization": "ville x", "id": "2"},  # same org, different case
            {"organization": "", "id": "3"},  # empty -> skipped
        ]
        adapter = MagicMock()
        adapter._client = MagicMock(aclose=AsyncMock())
        with patch(
            "src.infrastructure.datasources.adapters.subventions.SubventionsAdapter",
            return_value=adapter,
        ):
            with patch.object(extractor, "_multi_search", AsyncMock(return_value=datasets)):
                result = await extractor.extract("75")
        funders = [a for a in result["actors"] if a["external_id"].startswith("FUNDER:")]
        assert len(funders) == 1

    async def test_multi_search_merges_and_dedupes(self, extractor):
        adapter = MagicMock()
        # First term (prefecture "Paris") and second term ("Paris" dept name)
        adapter.search = AsyncMock(
            side_effect=[
                [{"id": "a"}, {"id": "b"}],
                [{"id": "b"}, {"id": "c"}, {"id": ""}],
            ]
        )
        out = await extractor._multi_search(adapter, "75")
        ids = [d.get("id") for d in out]
        # b deduped; empty-id dataset still appended
        assert ids.count("b") == 1
        assert "a" in ids and "c" in ids and "" in ids

    async def test_multi_search_handles_term_exception(self, extractor):
        adapter = MagicMock()
        adapter.search = AsyncMock(side_effect=[RuntimeError("x"), [{"id": "ok"}]])
        out = await extractor._multi_search(adapter, "75")
        assert [d["id"] for d in out] == ["ok"]

    async def test_multi_search_no_search_terms(self, extractor):
        adapter = MagicMock()
        adapter.search = AsyncMock(return_value=[])
        # Dept code with neither prefecture nor dept name -> no search terms
        out = await extractor._multi_search(adapter, "ZZ")
        assert out == []
        adapter.search.assert_not_called()


# ===========================================================================
# EPCIExtractor (httpx + DB)
# ===========================================================================


class TestEPCIExtractor:
    @pytest.fixture
    def extractor(self):
        return EPCIExtractor()

    async def test_http_error_on_first_call_returns_empty(self, extractor):
        import httpx

        factory, _ = make_http_client(get_side_effect=httpx.HTTPError("boom"))
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_non_200_status_returns_empty(self, extractor):
        factory, _ = make_http_client(get_return=make_response(status_code=500))
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_no_epcis_for_dept_returns_empty(self, extractor):
        # API returns EPCIs but none covers dept 75
        resp = make_response(json_data=[{"code": "200000", "codesDepartements": ["13"]}])
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_no_enterprises_returns_collectivities_only(self, extractor):
        epci_resp = make_response(
            json_data=[
                {"code": "200000", "nom": "Metropole", "population": 100000,
                 "codesDepartements": ["75"]}
            ]
        )
        factory, _ = make_http_client(get_return=epci_resp)
        ctx, _ = make_conn([])  # no enterprise rows
        with patch(f"{MODULE}.httpx.AsyncClient", factory), patch(
            f"{MODULE}.acquire_conn", ctx
        ):
            result = await extractor.extract("75")
        coll = [a for a in result["actors"] if a["type"] == "collectivity"]
        assert len(coll) == 1
        assert coll[0]["name"] == "Metropole"
        subtypes = {r["subtype"] for r in result["relations"]}
        assert subtypes == {"administers_territory"}

    async def test_epci_without_code_skipped(self, extractor):
        epci_resp = make_response(
            json_data=[
                {"nom": "NoCode", "codesDepartements": ["75"]},  # missing code
                {"code": "200001", "nom": "Valid", "codesDepartements": ["75"]},
            ]
        )
        factory, _ = make_http_client(get_return=epci_resp)
        ctx, _ = make_conn([])
        with patch(f"{MODULE}.httpx.AsyncClient", factory), patch(
            f"{MODULE}.acquire_conn", ctx
        ):
            result = await extractor.extract("75")
        coll = [a for a in result["actors"] if a["type"] == "collectivity"]
        assert len(coll) == 1
        assert coll[0]["name"] == "Valid"

    async def test_enterprise_matched_to_epci_by_postal_code(self, extractor):
        epci_list_resp = make_response(
            json_data=[
                {"code": "200000", "nom": "Metro", "population": 50000,
                 "codesDepartements": ["75"]}
            ]
        )
        communes_resp = make_response(
            json_data=[{"code": "75056", "codesPostaux": ["75001"]}]
        )
        # First get() = EPCI list, subsequent get() = communes per EPCI
        factory, _ = make_http_client(
            get_side_effect=[epci_list_resp, communes_resp]
        )
        enterprise_rows = [
            {"external_id": "SIREN:111", "name": "Ent", "metadata": {"code_postal": "75001"}}
        ]
        ctx, _ = make_conn(enterprise_rows)
        with patch(f"{MODULE}.httpx.AsyncClient", factory), patch(
            f"{MODULE}.acquire_conn", ctx
        ), patch("asyncio.sleep", AsyncMock()):
            result = await extractor.extract("75")
        belongs = [r for r in result["relations"] if r["subtype"] == "belongs_to_epci"]
        assert len(belongs) == 1
        assert belongs[0]["source_actor_external_id"] == "SIREN:111"
        assert belongs[0]["target_actor_external_id"] == "EPCI:200000"
        # EPCI metadata enriched with communes + postal codes
        epci_actor = [a for a in result["actors"] if a["external_id"] == "EPCI:200000"][0]
        assert epci_actor["metadata"]["communes"] == ["75056"]
        assert epci_actor["metadata"]["codes_postaux"] == ["75001"]

    async def test_no_commune_postal_codes_resolved(self, extractor):
        epci_list_resp = make_response(
            json_data=[
                {"code": "200000", "nom": "Metro", "population": 50000,
                 "codesDepartements": ["75"]}
            ]
        )
        communes_resp = make_response(json_data=[])  # no communes
        factory, _ = make_http_client(get_side_effect=[epci_list_resp, communes_resp])
        enterprise_rows = [
            {"external_id": "SIREN:111", "name": "Ent", "metadata": {"code_postal": "75001"}}
        ]
        ctx, _ = make_conn(enterprise_rows)
        with patch(f"{MODULE}.httpx.AsyncClient", factory), patch(
            f"{MODULE}.acquire_conn", ctx
        ), patch("asyncio.sleep", AsyncMock()):
            result = await extractor.extract("75")
        assert not [r for r in result["relations"] if r["subtype"] == "belongs_to_epci"]

    async def test_enterprise_postal_code_from_siege_subobject(self, extractor):
        epci_list_resp = make_response(
            json_data=[
                {"code": "200000", "nom": "Metro", "population": 50000,
                 "codesDepartements": ["75"]}
            ]
        )
        communes_resp = make_response(
            json_data=[{"code": "75056", "codesPostaux": ["75002"]}]
        )
        factory, _ = make_http_client(get_side_effect=[epci_list_resp, communes_resp])
        # code_postal nested in a JSON-string siege
        enterprise_rows = [
            {
                "external_id": "SIREN:222",
                "name": "Ent2",
                "metadata": {"siege": '{"code_postal": "75002"}'},
            }
        ]
        ctx, _ = make_conn(enterprise_rows)
        with patch(f"{MODULE}.httpx.AsyncClient", factory), patch(
            f"{MODULE}.acquire_conn", ctx
        ), patch("asyncio.sleep", AsyncMock()):
            result = await extractor.extract("75")
        belongs = [r for r in result["relations"] if r["subtype"] == "belongs_to_epci"]
        assert len(belongs) == 1


# ===========================================================================
# IncubatorExtractor (httpx)
# ===========================================================================


class TestIncubatorExtractor:
    @pytest.fixture
    def extractor(self):
        return IncubatorExtractor()

    def test_dept_code_mesr_format(self, extractor):
        assert extractor._dept_code_mesr("13") == "D013"
        assert extractor._dept_code_mesr("2A") == "D02A"
        assert extractor._dept_code_mesr("974") == "D974"

    async def test_no_structures_returns_empty(self, extractor):
        # Department query returns empty, region fallback also empty (no region)
        resp = make_response(json_data={"results": [], "total_count": 0})
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("999")  # no region mapping
        assert result == {"actors": [], "relations": []}

    async def test_structures_create_actors_and_relations(self, extractor):
        resp = make_response(
            json_data={
                "results": [
                    {
                        "identifiant": "INC1",
                        "libelle_court": "MonIncub",
                        "type_de_structure": "INCUB",
                        "libelle_type_de_structure": "Incubateur",
                        "geolocalisation": {"lat": 48.85, "lon": 2.35},
                        "adresse": "1 rue",
                        "localite": "Paris",
                        "code_postal": "75001",
                    }
                ],
                "total_count": 1,
            }
        )
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("13")
        actor = result["actors"][0]
        assert actor["type"] == "incubator"
        # short label appended when not already in name
        assert actor["name"] == "MonIncub (Incubateur)"
        assert actor["metadata"]["lat"] == 48.85
        rel = result["relations"][0]
        assert rel["subtype"] == "operates_in"
        assert rel["weight"] == 1.5

    async def test_structure_without_id_skipped(self, extractor):
        resp = make_response(
            json_data={"results": [{"libelle_court": "NoId"}], "total_count": 1}
        )
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("13")
        assert result == {"actors": [], "relations": []}

    async def test_region_fallback_filters_by_dept(self, extractor):
        # dept query empty, region query returns 2 records, one matching dept
        dept_empty = make_response(json_data={"results": [], "total_count": 0})
        region_resp = make_response(
            json_data={
                "results": [
                    {"identifiant": "A", "code_departement": "D013", "siret": "s"},
                    {"identifiant": "B", "code_departement": "D006", "siret": "s"},
                ],
                "total_count": 2,
            }
        )
        factory, _ = make_http_client(get_side_effect=[dept_empty, region_resp])
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("13")  # PACA region exists
        # Only the D013 structure should be kept
        ids = [a["external_id"] for a in result["actors"]]
        assert ids == ["INCUB:A"]

    async def test_fetch_by_department_non_200_breaks(self, extractor):
        client = MagicMock()
        client.get = AsyncMock(return_value=make_response(status_code=500))
        out = await extractor._fetch_by_department(client, "13")
        assert out == []


# ===========================================================================
# PolesExtractor (pure, hardcoded data)
# ===========================================================================


class TestPolesExtractor:
    @pytest.fixture
    def extractor(self):
        return PolesExtractor()

    async def test_no_poles_for_dept_returns_empty(self, extractor):
        result = await extractor.extract("999")
        assert result == {"actors": [], "relations": []}

    async def test_poles_for_dept_create_actors_and_sector_relations(self, extractor):
        # Dept 13 has several poles (Eurobiomed, etc.)
        result = await extractor.extract("13")
        assert len(result["actors"]) > 0
        assert all(a["type"] == "competitiveness_pole" for a in result["actors"])
        subtypes = {r["subtype"] for r in result["relations"]}
        assert "pole_in_territory" in subtypes
        assert "pole_covers_sector" in subtypes

    async def test_pole_external_id_normalized(self, extractor):
        result = await extractor.extract("87")  # Pole Europeen de la Ceramique
        ext_ids = [a["external_id"] for a in result["actors"]]
        assert any(e.startswith("POLE:") and " " not in e for e in ext_ids)

    def test_poles_data_nonempty(self):
        assert len(_POLES_COMPETITIVITE) > 50


# ===========================================================================
# TerritorialStructuresExtractor (httpx + DB)
# ===========================================================================


class TestTerritorialStructuresExtractor:
    @pytest.fixture
    def extractor(self):
        return TerritorialStructuresExtractor()

    async def test_cd_and_cr_always_created(self, extractor):
        # communes API returns empty -> still get CD + CR institutions
        resp = make_response(json_data=[])
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        insts = [a for a in result["actors"] if a["type"] == "institution"]
        roles = {a["metadata"]["role"] for a in insts}
        assert "conseil_departemental" in roles
        assert "conseil_regional" in roles
        # CD->CR belongs_to_region relation
        subtypes = {r["subtype"] for r in result["relations"]}
        assert "belongs_to_region" in subtypes

    async def test_communes_created_and_enterprise_matched(self, extractor):
        communes_resp = make_response(
            json_data=[
                {"nom": "Paris", "code": "75056", "population": 2000000,
                 "codesPostaux": ["75001", "75002"]},
                {"nom": "Tiny", "code": "75999", "population": 100,  # below min pop
                 "codesPostaux": ["75100"]},
            ]
        )
        factory, _ = make_http_client(get_return=communes_resp)
        enterprise_rows = [
            {"external_id": "SIREN:1", "metadata": {"code_postal": "75001"}},
            {"external_id": "SIREN:2", "metadata": {"cp": "75002"}},  # ville-based fallback
            {"external_id": "SIREN:3", "metadata": {"code_postal": "99999"}},  # no match
        ]
        ctx, _ = make_conn(enterprise_rows)
        with patch(f"{MODULE}.httpx.AsyncClient", factory), patch(
            f"{MODULE}.acquire_conn", ctx
        ):
            result = await extractor.extract("75")
        communes = [a for a in result["actors"]
                    if a["type"] == "territory" and a["external_id"].startswith("COMMUNE:")]
        # Tiny commune filtered out by min population
        assert len(communes) == 1
        located = [r for r in result["relations"] if r["subtype"] == "located_in_commune"]
        assert len(located) == 2  # SIREN:1 and SIREN:2 matched

    async def test_communes_api_failure_handled(self, extractor):
        factory, _ = make_http_client(get_side_effect=RuntimeError("net"))
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        # CD/CR still created even when commune fetch fails
        assert any(a["type"] == "institution" for a in result["actors"])

    async def test_region_unknown_skips_cr(self, extractor):
        # Dept "999" has no region code -> no conseil_regional actor
        resp = make_response(json_data=[])
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("999")
        roles = {a["metadata"].get("role") for a in result["actors"]
                 if a["type"] == "institution"}
        assert "conseil_regional" not in roles
        assert "conseil_departemental" in roles


# ===========================================================================
# SireneAddressEnricher (httpx + DB)
# ===========================================================================


class TestSireneAddressEnricher:
    @pytest.fixture
    def extractor(self):
        return SireneAddressEnricher()

    async def test_no_rows_returns_empty(self, extractor):
        # First fetch (enterprises) empty -> early return
        ctx, _ = make_conn([[], []])
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_enriches_and_creates_commune_relation(self, extractor):
        enterprise_rows = [
            {
                "id": "uuid-1",
                "external_id": "SIREN:111",
                "name": "Ent",
                "metadata": {},
            }
        ]
        commune_rows = [
            {"external_id": "COMMUNE:75056", "metadata": {"codes_postaux": ["75001"]}}
        ]
        ctx, _ = make_conn([enterprise_rows, commune_rows])
        api_resp = make_response(
            json_data={
                "results": [
                    {
                        "siege": {
                            "code_postal": "75001",
                            "libelle_commune": "Paris",
                            "latitude": "48.85",
                            "longitude": "2.35",
                        },
                        "date_creation": "2020-01-01",
                    }
                ]
            }
        )
        factory, _ = make_http_client(get_return=api_resp)
        with patch(f"{MODULE}.acquire_conn", ctx), patch(
            f"{MODULE}.httpx.AsyncClient", factory
        ), patch("asyncio.sleep", AsyncMock()):
            result = await extractor.extract("75")
        assert len(result["actors"]) == 1
        meta = result["actors"][0]["metadata"]
        assert meta["code_postal"] == "75001"
        assert meta["latitude"] == 48.85
        assert meta["date_creation"] == "2020-01-01"
        located = [r for r in result["relations"] if r["subtype"] == "located_in_commune"]
        assert len(located) == 1

    async def test_skips_when_api_returns_no_cp(self, extractor):
        enterprise_rows = [
            {"id": "uuid-1", "external_id": "SIREN:111", "name": "Ent", "metadata": {}}
        ]
        ctx, _ = make_conn([enterprise_rows, []])
        api_resp = make_response(json_data={"results": [{"siege": {}}]})  # no code_postal
        factory, _ = make_http_client(get_return=api_resp)
        with patch(f"{MODULE}.acquire_conn", ctx), patch(
            f"{MODULE}.httpx.AsyncClient", factory
        ), patch("asyncio.sleep", AsyncMock()):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_api_non_200_skipped(self, extractor):
        enterprise_rows = [
            {"id": "uuid-1", "external_id": "SIREN:111", "name": "Ent", "metadata": {}}
        ]
        ctx, _ = make_conn([enterprise_rows, []])
        factory, _ = make_http_client(get_return=make_response(status_code=404))
        with patch(f"{MODULE}.acquire_conn", ctx), patch(
            f"{MODULE}.httpx.AsyncClient", factory
        ), patch("asyncio.sleep", AsyncMock()):
            result = await extractor.extract("75")
        assert result["actors"] == []

    async def test_api_exception_skipped(self, extractor):
        enterprise_rows = [
            {"id": "uuid-1", "external_id": "SIREN:111", "name": "Ent", "metadata": {}}
        ]
        ctx, _ = make_conn([enterprise_rows, []])
        factory, _ = make_http_client(get_side_effect=RuntimeError("boom"))
        with patch(f"{MODULE}.acquire_conn", ctx), patch(
            f"{MODULE}.httpx.AsyncClient", factory
        ), patch("asyncio.sleep", AsyncMock()):
            result = await extractor.extract("75")
        assert result["actors"] == []


# ===========================================================================
# SireneDirigeantsEnricher (httpx + DB)
# ===========================================================================


class TestSireneDirigeantsEnricher:
    @pytest.fixture
    def extractor(self):
        return SireneDirigeantsEnricher()

    async def test_no_rows_returns_empty(self, extractor):
        ctx, _ = make_conn([])
        with patch(f"{MODULE}.acquire_conn", ctx):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_enriches_dirigeants_and_finances(self, extractor):
        rows = [
            {"id": "u1", "external_id": "SIREN:123456789", "name": "Ent", "metadata": {}}
        ]
        ctx, _ = make_conn(rows)
        api_resp = make_response(
            json_data={
                "results": [
                    {
                        "siren": "123456789",
                        "dirigeants": [
                            {
                                "type_dirigeant": "personne physique",
                                "nom": "Dupont",
                                "prenoms": "Jean",
                                "qualite": "President",
                                "annee_de_naissance": "1970",
                            },
                            {"type_dirigeant": "personne morale", "nom": "Holding"},
                        ],
                        "finances": {
                            "2022": {"ca": 1000, "resultat_net": 100},
                            "2023": {"ca": 2000, "resultat_net": 200},
                        },
                        "categorie_entreprise": "PME",
                        "tranche_effectif_salarie": "12",
                    }
                ]
            }
        )
        factory, _ = make_http_client(get_return=api_resp)
        with patch(f"{MODULE}.acquire_conn", ctx), patch(
            f"{MODULE}.httpx.AsyncClient", factory
        ), patch("asyncio.sleep", AsyncMock()):
            result = await extractor.extract("75")
        assert result["relations"] == []
        meta = result["actors"][0]["metadata"]
        # Only the personne physique is kept
        assert len(meta["dirigeants"]) == 1
        assert meta["dirigeants"][0]["nom"] == "Dupont"
        # Latest year finances picked
        assert meta["ca"] == 2000
        assert meta["annee_ca"] == "2023"
        assert meta["categorie_entreprise"] == "PME"
        assert meta["tranche_effectif"] == "12"

    async def test_siren_mismatch_skipped(self, extractor):
        rows = [
            {"id": "u1", "external_id": "SIREN:111111111", "name": "Ent", "metadata": {}}
        ]
        ctx, _ = make_conn(rows)
        api_resp = make_response(json_data={"results": [{"siren": "999999999"}]})
        factory, _ = make_http_client(get_return=api_resp)
        with patch(f"{MODULE}.acquire_conn", ctx), patch(
            f"{MODULE}.httpx.AsyncClient", factory
        ), patch("asyncio.sleep", AsyncMock()):
            result = await extractor.extract("75")
        assert result["actors"] == []

    async def test_empty_results_skipped(self, extractor):
        rows = [{"id": "u1", "external_id": "SIREN:111", "name": "E", "metadata": {}}]
        ctx, _ = make_conn(rows)
        api_resp = make_response(json_data={"results": []})
        factory, _ = make_http_client(get_return=api_resp)
        with patch(f"{MODULE}.acquire_conn", ctx), patch(
            f"{MODULE}.httpx.AsyncClient", factory
        ), patch("asyncio.sleep", AsyncMock()):
            result = await extractor.extract("75")
        assert result["actors"] == []


# ===========================================================================
# UrssafEffectifsEnricher (httpx + DB)
# ===========================================================================


class TestUrssafEffectifsEnricher:
    @pytest.fixture
    def extractor(self):
        return UrssafEffectifsEnricher()

    async def test_commune_query_failure_returns_empty(self, extractor):
        ctx, _ = make_conn([[], []])  # territory + sector rows both empty
        factory, _ = make_http_client(get_return=make_response(status_code=500))
        with patch(f"{MODULE}.acquire_conn", ctx), patch(
            f"{MODULE}.httpx.AsyncClient", factory
        ):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_commune_query_exception_returns_empty(self, extractor):
        ctx, _ = make_conn([[], []])
        factory, _ = make_http_client(get_side_effect=RuntimeError("net"))
        with patch(f"{MODULE}.acquire_conn", ctx), patch(
            f"{MODULE}.httpx.AsyncClient", factory
        ):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_enriches_communes_sectors_and_department(self, extractor):
        territory_rows = [
            {"id": "t1", "external_id": "COMMUNE:75056", "name": "Paris", "metadata": {}},
            {"id": "t2", "external_id": "DEPT:75", "name": "Paris dept", "metadata": {}},
        ]
        sector_rows = [
            {"id": "s1", "external_id": "NAF:43.33Z", "name": "Sect", "metadata": {}},
        ]
        ctx, _ = make_conn([territory_rows, sector_rows])

        commune_resp = make_response(
            json_data={
                "results": [
                    {"code_commune": "75056", "total_effectifs": 5000, "total_etabs": 300}
                ]
            }
        )
        sector_resp = make_response(
            json_data={
                "results": [
                    {"code_ape": "4333Z", "total_effectifs": 200, "total_etabs": 20}
                ]
            }
        )
        dept_resp = make_response(
            json_data={"results": [{"total_effectifs": 90000, "total_etabs": 8000}]}
        )
        factory, _ = make_http_client(
            get_side_effect=[commune_resp, sector_resp, dept_resp]
        )
        with patch(f"{MODULE}.acquire_conn", ctx), patch(
            f"{MODULE}.httpx.AsyncClient", factory
        ):
            result = await extractor.extract("75")
        by_ext = {a["external_id"]: a for a in result["actors"]}
        assert by_ext["COMMUNE:75056"]["metadata"]["effectifs_salaries"] == 5000
        assert by_ext["DEPT:75"]["metadata"]["effectifs_salaries"] == 90000
        # NAF normalized "4333Z" -> "43.33Z" matches existing sector actor
        assert "NAF:43.33Z" in by_ext
        assert by_ext["NAF:43.33Z"]["metadata"]["effectifs_75"] == 200
        assert result["relations"] == []


# ===========================================================================
# ADEMEExtractor (httpx)
# ===========================================================================


class TestADEMEExtractor:
    @pytest.fixture
    def extractor(self):
        return ADEMEExtractor()

    async def test_always_creates_ademe_actor(self, extractor):
        # Empty results on first page -> only ADEME national actor remains
        resp = make_response(json_data={"results": []})
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert len(result["actors"]) == 1
        assert result["actors"][0]["external_id"] == "INST:ADEME"
        assert result["relations"] == []

    async def test_aid_creates_beneficiary_and_relation(self, extractor):
        resp = make_response(
            json_data={
                "results": [
                    {
                        "idBeneficiaire": "12345678900011",
                        "nomBeneficiaire": "Beneficiaire SA",
                        "montant": 50000,
                        "objet": "Projet solaire",
                        "dateConvention": "2024-01-01",
                        "referenceDecision": "REF-1",
                    }
                ],
                "next": "",
            }
        )
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        ent = [a for a in result["actors"] if a["type"] == "enterprise"][0]
        assert ent["external_id"] == "SIREN:123456789"
        assert ent["metadata"]["ademe_total"] == 50000
        rel = result["relations"][0]
        assert rel["subtype"] == "funded_by_ademe"
        assert rel["source_actor_external_id"] == "SIREN:123456789"
        assert rel["target_actor_external_id"] == "INST:ADEME"

    async def test_short_siret_skipped(self, extractor):
        resp = make_response(
            json_data={"results": [{"idBeneficiaire": "123", "montant": 1}], "next": ""}
        )
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        # only ADEME actor, no beneficiary
        assert [a["external_id"] for a in result["actors"]] == ["INST:ADEME"]

    async def test_non_200_breaks_loop(self, extractor):
        factory, _ = make_http_client(get_return=make_response(status_code=503))
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert [a["external_id"] for a in result["actors"]] == ["INST:ADEME"]

    async def test_api_exception_breaks_loop(self, extractor):
        factory, _ = make_http_client(get_side_effect=RuntimeError("boom"))
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert [a["external_id"] for a in result["actors"]] == ["INST:ADEME"]

    async def test_accumulates_multiple_aids_same_beneficiary(self, extractor):
        resp = make_response(
            json_data={
                "results": [
                    {
                        "idBeneficiaire": "12345678900011",
                        "nomBeneficiaire": "B",
                        "montant": 1000,
                        "objet": "A",
                        "dateConvention": "2024-01-01",
                    },
                    {
                        "idBeneficiaire": "12345678900011",
                        "nomBeneficiaire": "B",
                        "montant": 2000,
                        "objet": "B",
                        "dateConvention": "2024-02-01",
                    },
                ],
                "next": "",
            }
        )
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        ent = [a for a in result["actors"] if a["type"] == "enterprise"][0]
        assert ent["metadata"]["ademe_total"] == 3000
        assert len(ent["metadata"]["ademe_aids"]) == 2


# ===========================================================================
# QualiopiExtractor (httpx)
# ===========================================================================


class TestQualiopiExtractor:
    @pytest.fixture
    def extractor(self):
        return QualiopiExtractor()

    async def test_always_creates_territory(self, extractor):
        resp = make_response(json_data={"results": []})
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert len(result["actors"]) == 1
        assert result["actors"][0]["type"] == "territory"

    async def test_org_creates_actor_with_certs_and_specialties(self, extractor):
        resp = make_response(
            json_data={
                "results": [
                    {
                        "denomination": "OF Test",
                        "siren": "123456789",
                        "certifications_actionsdeformation": "true",
                        "certifications_vae": True,
                        "informationsdeclarees_specialitesdeformation_libellespecialite1": "Info",
                        "informationsdeclarees_specialitesdeformation_libellespecialite2": "Lang",
                        "informationsdeclarees_nbstagiaires": 1000,
                        "informationsdeclarees_effectifformateurs": 10,
                        "adressephysiqueorganismeformation_ville": "Paris",
                    }
                ]
            }
        )
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        ent = [a for a in result["actors"] if a["external_id"] == "SIREN:123456789"][0]
        assert ent["metadata"]["qualiopi"] is True
        assert ent["metadata"]["qualiopi_certifications"]["actionsdeformation"] is True
        assert ent["metadata"]["qualiopi_certifications"]["vae"] is True
        assert ent["metadata"]["qualiopi_specialties"] == ["Info", "Lang"]
        assert ent["metadata"]["qualiopi_ville"] == "Paris"
        rel = result["relations"][0]
        assert rel["subtype"] == "trains_in_territory"
        assert rel["weight"] == min(1000 / 500.0, 5.0)

    async def test_short_siren_skipped(self, extractor):
        resp = make_response(
            json_data={"results": [{"denomination": "X", "siren": "12"}]}
        )
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert [a["type"] for a in result["actors"]] == ["territory"]

    async def test_non_200_breaks(self, extractor):
        factory, _ = make_http_client(get_return=make_response(status_code=500))
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert [a["type"] for a in result["actors"]] == ["territory"]

    async def test_api_exception_breaks(self, extractor):
        factory, _ = make_http_client(get_side_effect=RuntimeError("net"))
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert [a["type"] for a in result["actors"]] == ["territory"]


# ===========================================================================
# OFGLExtractor (httpx, two-part)
# ===========================================================================


class TestOFGLExtractor:
    @pytest.fixture
    def extractor(self):
        return OFGLExtractor()

    def test_agregat_key_mapping(self, extractor):
        assert extractor._agregat_key("Recettes de fonctionnement") == "recettes_fonctionnement"
        assert extractor._agregat_key("Encours de dette") == "encours_dette"
        # Unknown -> normalized fallback
        assert extractor._agregat_key("Autre Chose") == "autre_chose"

    async def test_empty_results_only_dept_actor(self, extractor):
        # Every API call returns empty results
        resp = make_response(json_data={"results": []})
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert len(result["actors"]) == 1
        assert result["actors"][0]["external_id"] == "DEPT:75"

    async def test_commune_finances_create_institution(self, extractor):
        # 6 agregat calls (commune finances) + EPCI compositions call(s).
        # Return finance data only for the first agregat call.
        finance_resp = make_response(
            json_data={
                "results": [
                    {
                        "com_code": "75056",
                        "com_name": "Paris",
                        "siren": "217500016",
                        "insee": "75056",
                        "ptot": 2000000,
                        "montant": 8000000000,
                        "euros_par_habitant": 4000,
                        "exer": "2023",
                    }
                ]
            }
        )
        empty = make_response(json_data={"results": []})
        # 6 agregats: first has data, rest empty. Then EPCI comp: empty.
        side = [finance_resp] + [empty] * 4 + [empty] + [empty]
        factory, _ = make_http_client(get_side_effect=side)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        inst = [a for a in result["actors"] if a["external_id"] == "SIREN:217500016"]
        assert len(inst) == 1
        assert inst[0]["metadata"]["finances"]["recettes_fonctionnement"] == 8000000000
        rels = [r for r in result["relations"]
                if r["subtype"] == "institution_finances_territory"]
        assert len(rels) == 1

    async def test_epci_compositions_create_member_relation(self, extractor):
        empty = make_response(json_data={"results": []})
        epci_resp = make_response(
            json_data={
                "results": [
                    {
                        "insee": "75056",
                        "siren": "217500016",
                        "nom": "Paris",
                        "siren_epci": "200054781",
                        "nom_epci": "Metropole Grand Paris",
                        "pmun": 2000000,
                        "annee": "2023",
                    }
                ]
            }
        )
        # 6 commune-finance agregat calls (empty), then EPCI comp call(s)
        side = [empty] * 6 + [epci_resp, empty]
        factory, _ = make_http_client(get_side_effect=side)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        member_rels = [r for r in result["relations"] if r["subtype"] == "member_of_epci"]
        assert len(member_rels) == 1
        epci_actor = [a for a in result["actors"] if a["external_id"] == "SIREN:200054781"][0]
        assert epci_actor["metadata"]["nb_communes"] == 1
        assert epci_actor["metadata"]["population_totale"] == 2000000

    async def test_commune_finance_non_200_handled(self, extractor):
        # Non-200 on every call -> no crash, only dept actor
        resp = make_response(status_code=500, text="error\nbody")
        factory, _ = make_http_client(get_return=resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert [a["external_id"] for a in result["actors"]] == ["DEPT:75"]


# ===========================================================================
# DVFExtractor (httpx, helper methods)
# ===========================================================================


class TestDVFExtractor:
    @pytest.fixture
    def extractor(self):
        return DVFExtractor()

    async def test_no_communes_returns_dept_only(self, extractor):
        # _get_communes returns [] (geo API non-200)
        factory, _ = make_http_client(get_return=make_response(status_code=500))
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        assert [a["external_id"] for a in result["actors"]] == ["DEPT:75"]

    async def test_get_communes_success(self, extractor):
        client = MagicMock()
        client.get = AsyncMock(
            return_value=make_response(json_data=[{"code": "75056", "nom": "Paris"}])
        )
        out = await extractor._get_communes(client, "75")
        assert out == [{"code": "75056", "nom": "Paris"}]

    async def test_get_communes_exception(self, extractor):
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError("net"))
        out = await extractor._get_communes(client, "75")
        assert out == []

    async def test_get_commune_stats_computes_medians(self, extractor):
        client = MagicMock()
        client.get = AsyncMock(
            return_value=make_response(
                json_data={
                    "results": [
                        {"valeurfonc": "100000", "sbati": "50", "vefa": False},
                        {"valeurfonc": "200000", "sbati": "100", "vefa": True},
                        {"valeurfonc": "300000", "sbati": "0", "vefa": False},
                    ]
                }
            )
        )
        stats = await extractor._get_commune_stats(client, "75056")
        assert stats["nb_mutations"] == 3
        assert stats["prix_median"] == 200000.0
        assert stats["nb_vefa"] == 1
        assert stats["prix_m2_median"] == 2000.0

    async def test_get_commune_stats_no_results(self, extractor):
        client = MagicMock()
        client.get = AsyncMock(return_value=make_response(json_data={"results": []}))
        assert await extractor._get_commune_stats(client, "75056") is None

    async def test_get_commune_stats_no_valid_prices(self, extractor):
        client = MagicMock()
        client.get = AsyncMock(
            return_value=make_response(
                json_data={"results": [{"valeurfonc": "0", "sbati": "0"}]}
            )
        )
        assert await extractor._get_commune_stats(client, "75056") is None

    async def test_get_commune_stats_non_200(self, extractor):
        client = MagicMock()
        client.get = AsyncMock(return_value=make_response(status_code=500))
        assert await extractor._get_commune_stats(client, "75056") is None

    async def test_get_commune_stats_exception(self, extractor):
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError("boom"))
        assert await extractor._get_commune_stats(client, "75056") is None

    async def test_full_extract_with_commune_stats(self, extractor):
        communes_resp = make_response(
            json_data=[{"code": "75056", "nom": "Paris", "population": 2000000}]
        )
        stats_resp = make_response(
            json_data={
                "results": [
                    {"valeurfonc": "100000", "sbati": "50", "vefa": False},
                    {"valeurfonc": "200000", "sbati": "100", "vefa": True},
                ]
            }
        )
        factory, _ = make_http_client(get_side_effect=[communes_resp, stats_resp])
        with patch(f"{MODULE}.httpx.AsyncClient", factory):
            result = await extractor.extract("75")
        com_actors = [a for a in result["actors"] if a["external_id"] == "INSEE:75056"]
        assert len(com_actors) == 1
        assert "dvf" in com_actors[0]["metadata"]
        rels = [r for r in result["relations"] if r["subtype"] == "territory_immo_activity"]
        assert len(rels) == 1


# ===========================================================================
# FranceTravailExtractor (adapter-backed + static helpers)
# ===========================================================================


class TestFranceTravailExtractor:
    @pytest.fixture
    def extractor(self):
        return FranceTravailExtractor()

    def test_aggregate_by_rome(self, extractor):
        offres = [
            {
                "rome": {"code": "M1805", "libelle": "Dev"},
                "contrat": {"type": "CDI"},
                "intitule": "Dev Python",
            },
            {
                "rome": {"code": "M1805", "libelle": "Dev"},
                "contrat": {"type": "CDD"},
                "intitule": "Dev Java",
            },
            {"rome": None, "intitule": "skip"},  # no rome code -> skipped
        ]
        agg = extractor._aggregate_by_rome(offres)
        assert agg["M1805"]["count"] == 2
        assert agg["M1805"]["contrats"] == {"CDI": 1, "CDD": 1}
        assert "Dev Python" in agg["M1805"]["intitules"]

    async def test_no_credentials_returns_empty(self, extractor):
        adapter = MagicMock()
        adapter.has_credentials = False
        with patch(
            "src.infrastructure.datasources.adapters.france_travail.FranceTravailAdapter",
            return_value=adapter,
        ):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    async def test_offres_create_sector_actors(self, extractor):
        adapter = MagicMock()
        adapter.has_credentials = True
        adapter.search_offres = AsyncMock(
            return_value=[
                {
                    "rome": {"code": "M1805", "libelle": "Dev"},
                    "contrat": {"type": "CDI"},
                    "intitule": "Dev",
                }
            ]
        )
        adapter.search_la_bonne_boite = AsyncMock(return_value=[])
        with patch(
            "src.infrastructure.datasources.adapters.france_travail.FranceTravailAdapter",
            return_value=adapter,
        ):
            result = await extractor.extract("75")  # 75 has a centroid
        sector = [a for a in result["actors"] if a["external_id"] == "ROME:M1805"]
        assert len(sector) == 1
        rels = [r for r in result["relations"]
                if r["subtype"] == "sector_employment_tension"]
        assert len(rels) == 1

    async def test_lbb_creates_enterprise_recruits_relation(self, extractor):
        adapter = MagicMock()
        adapter.has_credentials = True
        adapter.search_offres = AsyncMock(
            return_value=[
                {
                    "rome": {"code": "M1805", "libelle": "Dev"},
                    "contrat": {"type": "CDI"},
                    "intitule": "Dev",
                }
            ]
        )
        adapter.search_la_bonne_boite = AsyncMock(
            return_value=[
                {
                    "siret": "12345678900011",
                    "nom": "TechCo",
                    "naf": "62.01Z",
                    "effectif": "50",
                    "score_embauche": 0.8,
                    "distance_km": 5,
                }
            ]
        )
        with patch(
            "src.infrastructure.datasources.adapters.france_travail.FranceTravailAdapter",
            return_value=adapter,
        ):
            result = await extractor.extract("75")
        ent = [a for a in result["actors"] if a["external_id"] == "SIRET:12345678900011"]
        assert len(ent) == 1
        rels = [r for r in result["relations"]
                if r["subtype"] == "enterprise_recruits_sector"]
        assert len(rels) == 1

    async def test_fetch_offres_filters_errors(self, extractor):
        adapter = MagicMock()
        adapter.search_offres = AsyncMock(
            return_value=[{"rome": {"code": "X"}}, {"error": "rate limit"}]
        )
        out = await extractor._fetch_offres(adapter, "75")
        assert out == [{"rome": {"code": "X"}}]

    async def test_fetch_offres_exception_returns_empty(self, extractor):
        adapter = MagicMock()
        adapter.search_offres = AsyncMock(side_effect=RuntimeError("boom"))
        assert await extractor._fetch_offres(adapter, "75") == []

    async def test_fetch_lbb_exception_returns_empty(self, extractor):
        adapter = MagicMock()
        adapter.search_la_bonne_boite = AsyncMock(side_effect=RuntimeError("boom"))
        assert await extractor._fetch_lbb(adapter, 1.0, 2.0, "M1805") == []


# ===========================================================================
# INSEELocalExtractor (httpx + adapter for unemployment)
# ===========================================================================


class TestINSEELocalExtractor:
    @pytest.fixture
    def extractor(self):
        return INSEELocalExtractor()

    async def test_communes_create_demographics(self, extractor):
        communes_resp = make_response(
            json_data=[
                {
                    "code": "75056",
                    "nom": "Paris",
                    "population": 2000000,
                    "surface": 10540,  # ha
                    "centre": {"coordinates": [2.35, 48.85]},
                }
            ]
        )
        factory, _ = make_http_client(get_return=communes_resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory), patch.object(
            extractor, "_fetch_unemployment", AsyncMock(return_value=7.5)
        ):
            result = await extractor.extract("75")
        com = [a for a in result["actors"] if a["external_id"] == "INSEE:75056"][0]
        assert com["metadata"]["population"] == 2000000
        assert com["metadata"]["surface_km2"] == 105.4
        dept = [a for a in result["actors"] if a["external_id"] == "DEPT:75"][0]
        assert dept["metadata"]["population_totale"] == 2000000
        assert dept["metadata"]["unemployment_rate"] == 7.5
        rels = [r for r in result["relations"] if r["subtype"] == "territory_demographics"]
        assert len(rels) == 1

    async def test_zero_population_commune_skipped(self, extractor):
        communes_resp = make_response(
            json_data=[{"code": "75999", "nom": "Empty", "population": 0, "surface": 100}]
        )
        factory, _ = make_http_client(get_return=communes_resp)
        with patch(f"{MODULE}.httpx.AsyncClient", factory), patch.object(
            extractor, "_fetch_unemployment", AsyncMock(return_value=None)
        ):
            result = await extractor.extract("75")
        assert not [a for a in result["actors"] if a["external_id"].startswith("INSEE:")]

    async def test_fetch_communes_non_200(self, extractor):
        client = MagicMock()
        client.get = AsyncMock(return_value=make_response(status_code=500))
        assert await extractor._fetch_communes(client, "75") == []

    async def test_fetch_communes_exception(self, extractor):
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError("net"))
        assert await extractor._fetch_communes(client, "75") == []

    async def test_fetch_unemployment_success(self, extractor):
        adapter = MagicMock()
        adapter.get_unemployment_rate = AsyncMock(return_value=8.1)
        with patch(
            "src.infrastructure.datasources.adapters.insee_local.INSEELocalAdapter",
            return_value=adapter,
        ):
            rate = await extractor._fetch_unemployment("75")
        assert rate == 8.1

    async def test_fetch_unemployment_exception_returns_none(self, extractor):
        with patch(
            "src.infrastructure.datasources.adapters.insee_local.INSEELocalAdapter",
            side_effect=RuntimeError("no creds"),
        ):
            assert await extractor._fetch_unemployment("75") is None


# ===========================================================================
# EXTRACTORS registry
# ===========================================================================


class TestExtractorsRegistry:
    def test_all_values_are_base_extractor_subclasses(self):
        for name, cls in EXTRACTORS.items():
            assert issubclass(cls, BaseExtractor), name

    def test_source_names_match_registry_keys(self):
        for name, cls in EXTRACTORS.items():
            assert cls.source_name == name

    def test_expected_extractors_present(self):
        expected = {
            "sirene", "bodacc", "nature_juridique", "boamp", "rna", "subventions",
            "epci", "incubator", "poles", "territorial", "sirene_enrich",
            "sirene_dirigeants", "urssaf", "ademe", "qualiopi", "ofgl", "dvf",
            "france_travail", "insee_local",
        }
        assert expected <= set(EXTRACTORS.keys())

    def test_registry_classes_instantiable(self):
        for cls in EXTRACTORS.values():
            instance = cls()
            assert isinstance(instance, BaseExtractor)

    def test_module_httpx_is_real_httpx(self):
        # Sanity check that the module exposes httpx for patching.
        import httpx as real_httpx

        assert re_mod.httpx is real_httpx
