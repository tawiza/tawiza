"""Unit tests for utility helpers in relation_extractors.

Targets the pure-logic utilities (no DB) and the SireneExtractor with
mocked acquire_conn. The 20+ Extractor classes follow the same pattern,
so SireneExtractor is the canonical example here.
"""

import json
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.application.services.relation_extractors import (
    BaseExtractor,
    SireneExtractor,
    _actor_id,
    _classify_nature_juridique,
    _DEPT_NAMES,
    _parse_raw_data,
    _relation_id,
    _stable_uuid,
)


class TestParseRawData:
    """_parse_raw_data: dict pass-through, JSON string parsing, fallback to {}."""

    def test_dict_returned_as_is(self):
        data = {"key": "value"}
        assert _parse_raw_data(data) is data

    def test_json_string_parsed_to_dict(self):
        result = _parse_raw_data('{"naf": "62.01Z", "label": "Programming"}')
        assert result == {"naf": "62.01Z", "label": "Programming"}

    def test_invalid_json_returns_empty(self):
        assert _parse_raw_data("not a json") == {}

    def test_json_array_returns_empty(self):
        # JSON array is not a dict -> fallback
        assert _parse_raw_data("[1, 2, 3]") == {}

    def test_none_returns_empty(self):
        assert _parse_raw_data(None) == {}

    def test_int_returns_empty(self):
        assert _parse_raw_data(42) == {}

    def test_empty_string_returns_empty(self):
        assert _parse_raw_data("") == {}

    def test_nested_dict_preserved(self):
        nested = {"outer": {"inner": [1, 2, 3]}}
        assert _parse_raw_data(json.dumps(nested)) == nested


class TestStableUuid:
    """_stable_uuid: deterministic uuid5 from prefix + key."""

    def test_returns_uuid_instance(self):
        result = _stable_uuid("actor", "test")
        assert isinstance(result, uuid.UUID)

    def test_same_inputs_same_uuid(self):
        a = _stable_uuid("actor", "siren-12345")
        b = _stable_uuid("actor", "siren-12345")
        assert a == b

    def test_different_prefix_different_uuid(self):
        a = _stable_uuid("actor", "key")
        b = _stable_uuid("relation", "key")
        assert a != b

    def test_different_key_different_uuid(self):
        a = _stable_uuid("actor", "key1")
        b = _stable_uuid("actor", "key2")
        assert a != b

    def test_uuid_version_is_5(self):
        result = _stable_uuid("a", "b")
        assert result.version == 5


class TestActorId:
    """_actor_id: convenience wrapper for actor UUIDs."""

    def test_format_is_actor_type_external_id(self):
        # Should be equivalent to _stable_uuid("actor", f"{type}:{ext_id}")
        expected = _stable_uuid("actor", "enterprise:SIREN:12345")
        assert _actor_id("enterprise", "SIREN:12345") == expected

    def test_deterministic(self):
        a = _actor_id("territory", "DEPT:75")
        b = _actor_id("territory", "DEPT:75")
        assert a == b

    def test_different_actor_types_distinct(self):
        a = _actor_id("enterprise", "X")
        b = _actor_id("association", "X")
        assert a != b


class TestRelationId:
    """_relation_id: deterministic UUID for relations."""

    def test_format_includes_arrow_and_subtype(self):
        expected = _stable_uuid("relation", "A->B:owns")
        assert _relation_id("A", "B", "owns") == expected

    def test_direction_matters(self):
        a = _relation_id("A", "B", "owns")
        b = _relation_id("B", "A", "owns")
        assert a != b

    def test_subtype_matters(self):
        a = _relation_id("A", "B", "owns")
        b = _relation_id("A", "B", "operates")
        assert a != b


class TestClassifyNatureJuridique:
    """_classify_nature_juridique: NJ code → (actor_type, label)."""

    def test_none_returns_none(self):
        assert _classify_nature_juridique(None) is None

    def test_empty_string_returns_none(self):
        assert _classify_nature_juridique("") is None

    def test_unknown_prefix_returns_none(self):
        assert _classify_nature_juridique("0000") is None

    def test_association_loi_1901(self):
        result = _classify_nature_juridique("9210")
        assert result == ("association", "Association loi 1901")

    def test_association_alsace_moselle(self):
        result = _classify_nature_juridique("9220")
        assert result == ("association", "Association loi Alsace-Moselle")

    def test_generic_association_falls_back_to_92(self):
        # 9250 is not in the specific list, should match the general "92" prefix
        result = _classify_nature_juridique("9250")
        assert result == ("association", "Association")

    def test_fondation_via_93(self):
        result = _classify_nature_juridique("9300")
        assert result[0] == "association"
        assert "Fondation" in result[1]

    def test_formation_publique(self):
        result = _classify_nature_juridique("7321")
        assert result[0] == "formation"

    def test_formation_privee_falls_back_to_85(self):
        result = _classify_nature_juridique("8599")
        assert result[0] == "formation"

    def test_financial_banque_centrale(self):
        result = _classify_nature_juridique("6411")
        assert result == ("financial", "Banque centrale")

    def test_financial_assurance_fallback(self):
        result = _classify_nature_juridique("6599")  # 65 prefix general
        assert result[0] == "financial"

    def test_institution_collectivite_territoriale(self):
        result = _classify_nature_juridique("7210")
        assert result[0] == "institution"
        assert "Collectivite territoriale" in result[1]

    def test_institution_etablissement_hospitalier(self):
        result = _classify_nature_juridique("7300")
        assert result == ("institution", "Etablissement public hospitalier")

    def test_longest_prefix_wins(self):
        # "9210" should match the specific "9210" mapping, not the generic "92"
        specific = _classify_nature_juridique("9210")
        generic = _classify_nature_juridique("9299")
        assert specific[1] == "Association loi 1901"
        assert generic[1] == "Association"

    def test_strips_whitespace(self):
        # _classify_nature_juridique calls .strip()
        assert _classify_nature_juridique("  9210  ") == ("association", "Association loi 1901")

    def test_non_string_codes_handled(self):
        # Numeric codes should still work via str() coercion
        result = _classify_nature_juridique(9210)
        assert result == ("association", "Association loi 1901")


class TestDeptNamesMapping:
    """_DEPT_NAMES: department code → name lookup."""

    def test_paris_mapping(self):
        assert _DEPT_NAMES["75"] == "Paris"

    def test_corsica_split(self):
        assert _DEPT_NAMES["2A"] == "Corse-du-Sud"
        assert _DEPT_NAMES["2B"] == "Haute-Corse"

    def test_overseas_territories_present(self):
        assert _DEPT_NAMES["971"] == "Guadeloupe"
        assert _DEPT_NAMES["972"] == "Martinique"
        assert _DEPT_NAMES["973"] == "Guyane"
        assert _DEPT_NAMES["974"] == "La Reunion"
        assert _DEPT_NAMES["976"] == "Mayotte"

    def test_metropolitan_completeness(self):
        # Should have at least 96 metropolitan departments + Corsica split + DOM
        assert len(_DEPT_NAMES) >= 100

    def test_missing_code_not_in_dict(self):
        # 20 is split into 2A/2B, so plain "20" should not exist
        assert "20" not in _DEPT_NAMES


class TestBaseExtractor:
    """BaseExtractor: abstract base class, cannot be instantiated."""

    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            BaseExtractor()

    def test_subclass_must_implement_extract(self):
        class IncompleteExtractor(BaseExtractor):
            pass

        with pytest.raises(TypeError):
            IncompleteExtractor()

    def test_concrete_subclass_can_instantiate(self):
        class ConcreteExtractor(BaseExtractor):
            source_name = "test"

            async def extract(self, department_code):
                return {"actors": [], "relations": []}

        instance = ConcreteExtractor()
        assert instance.source_name == "test"


class TestSireneExtractor:
    """SireneExtractor.extract with mocked DB connection."""

    @pytest.fixture
    def extractor(self):
        return SireneExtractor()

    def _mock_acquire_conn(self, rows):
        """Build an async context manager that yields a connection with fetch() -> rows."""
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=rows)

        @asynccontextmanager
        async def _ctx():
            yield mock_conn

        return _ctx

    @pytest.mark.asyncio
    async def test_no_rows_returns_empty(self, extractor):
        with patch(
            "src.application.services.relation_extractors.acquire_conn",
            self._mock_acquire_conn([]),
        ):
            result = await extractor.extract("75")
        assert result == {"actors": [], "relations": []}

    @pytest.mark.asyncio
    async def test_aggregate_signal_creates_sector_actor(self, extractor):
        rows = [
            {
                "raw_data": {
                    "naf": "62.01Z",
                    "label": "Programmation",
                    "total": 100,
                    "sample_size": 100,
                },
                "metric_name": "sector_count",
                "metric_value": 100,
                "event_date": "2026-01-01",
                "collected_at": "2026-01-01T10:00:00",
            }
        ]
        with patch(
            "src.application.services.relation_extractors.acquire_conn",
            self._mock_acquire_conn(rows),
        ):
            result = await extractor.extract("75")
        actors_by_type = {a["type"] for a in result["actors"]}
        assert "territory" in actors_by_type
        # Sector actor should be created from the aggregate signal
        assert "sector" in actors_by_type

    @pytest.mark.asyncio
    async def test_individual_enterprise_signal(self, extractor):
        rows = [
            {
                "raw_data": {
                    "siren": "123456789",
                    "nom": "Acme SAS",
                    "naf": "62.01Z",
                    "label": "Programmation",
                    "nature_juridique": "5710",
                    "tranche_effectif": "10",
                },
                "metric_name": "enterprise",
                "metric_value": 1,
                "event_date": "2026-01-01",
                "collected_at": "2026-01-01T10:00:00",
            }
        ]
        with patch(
            "src.application.services.relation_extractors.acquire_conn",
            self._mock_acquire_conn(rows),
        ):
            result = await extractor.extract("75")

        # Should have at least one enterprise actor
        enterprise_actors = [a for a in result["actors"] if a["type"] == "enterprise"]
        assert len(enterprise_actors) == 1
        assert enterprise_actors[0]["name"] == "Acme SAS"
        assert enterprise_actors[0]["external_id"] == "SIREN:123456789"

        # Headquarter relation should be present
        hq_rels = [r for r in result["relations"] if r["subtype"] == "headquarter_in"]
        assert len(hq_rels) == 1
        assert hq_rels[0]["source_actor_external_id"] == "SIREN:123456789"
        assert hq_rels[0]["target_actor_external_id"] == "DEPT:75"
        assert hq_rels[0]["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_territory_actor_uses_dept_name(self, extractor):
        rows = [
            {
                "raw_data": {"siren": "111", "nom": "Foo"},
                "metric_name": "x",
                "metric_value": 1,
                "event_date": "2026-01-01",
                "collected_at": "2026-01-01T10:00:00",
            }
        ]
        with patch(
            "src.application.services.relation_extractors.acquire_conn",
            self._mock_acquire_conn(rows),
        ):
            result = await extractor.extract("75")

        territory = next(a for a in result["actors"] if a["type"] == "territory")
        assert territory["name"] == "Paris"
        assert territory["external_id"] == "DEPT:75"

    @pytest.mark.asyncio
    async def test_unknown_dept_uses_default_name(self, extractor):
        rows = [
            {
                "raw_data": {"siren": "111"},
                "metric_name": "x",
                "metric_value": 1,
                "event_date": "2026-01-01",
                "collected_at": "2026-01-01T10:00:00",
            }
        ]
        with patch(
            "src.application.services.relation_extractors.acquire_conn",
            self._mock_acquire_conn(rows),
        ):
            result = await extractor.extract("999")

        territory = next(a for a in result["actors"] if a["type"] == "territory")
        assert territory["name"] == "Departement 999"

    @pytest.mark.asyncio
    async def test_enterprise_metadata_merged_from_multiple_signals(self, extractor):
        # Two signals for same SIREN — naf in first, nature_juridique in second
        rows = [
            {
                "raw_data": {"siren": "111", "naf": "62.01Z", "label": "Prog"},
                "metric_name": "x",
                "metric_value": 1,
                "event_date": "2026-01-01",
                "collected_at": "2026-01-01T10:00:00",
            },
            {
                "raw_data": {"siren": "111", "nature_juridique": "5710"},
                "metric_name": "y",
                "metric_value": 1,
                "event_date": "2026-01-02",
                "collected_at": "2026-01-02T10:00:00",
            },
        ]
        with patch(
            "src.application.services.relation_extractors.acquire_conn",
            self._mock_acquire_conn(rows),
        ):
            result = await extractor.extract("75")

        ents = [a for a in result["actors"] if a["type"] == "enterprise"]
        assert len(ents) == 1
        meta = ents[0]["metadata"]
        # Both signals' metadata are merged into the same actor
        assert meta["naf"] == "62.01Z"
        assert meta["nature_juridique"] == "5710"

    @pytest.mark.asyncio
    async def test_source_name_constant(self, extractor):
        assert extractor.source_name == "sirene"

    @pytest.mark.asyncio
    async def test_raw_data_as_json_string_handled(self, extractor):
        # asyncpg returns JSONB as a string in some configurations
        rows = [
            {
                "raw_data": '{"siren": "111", "nom": "Bar"}',
                "metric_name": "x",
                "metric_value": 1,
                "event_date": "2026-01-01",
                "collected_at": "2026-01-01T10:00:00",
            }
        ]
        with patch(
            "src.application.services.relation_extractors.acquire_conn",
            self._mock_acquire_conn(rows),
        ):
            result = await extractor.extract("75")
        ents = [a for a in result["actors"] if a["type"] == "enterprise"]
        assert len(ents) == 1
        assert ents[0]["name"] == "Bar"
