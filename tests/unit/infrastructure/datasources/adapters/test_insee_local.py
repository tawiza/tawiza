"""Unit tests for the INSEE Local adapter.

The adapter (``INSEELocalAdapter``) talks to two external services over an
``httpx.AsyncClient`` (``self._client``):

* the authenticated INSEE Donnees Locales / BDM API (OAuth2 + SDMX), and
* the public geo.api.gouv.fr fallback.

These tests exercise the LOGIC of the adapter (request building, JSON/XML/SDMX
parsing, error handling, internal model mapping, caching, empty cases) WITHOUT
any network access. We do this by replacing ``adapter._client`` with an
``AsyncMock`` and feeding it crafted ``httpx.Response``-like objects.

No production code is touched. Where a genuine production behaviour is asserted
(e.g. a 0-population fallback), it is encoded as a regression test.
"""

import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.infrastructure.datasources.adapters.insee_local import INSEELocalAdapter
from src.infrastructure.datasources.base import AdapterConfig, SyncStatus

# asyncio_mode = auto in pytest.ini, but be explicit for clarity.
pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _make_response(
    *,
    status_code: int = 200,
    json_data=None,
    text: str = "",
    raise_http_error: bool = False,
) -> MagicMock:
    """Build a fake httpx.Response.

    * ``json()`` returns ``json_data``.
    * ``text`` returns ``text``.
    * ``raise_for_status()`` either no-ops or raises ``httpx.HTTPStatusError``.
    """
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    resp.text = text

    if raise_http_error:
        request = httpx.Request("GET", "https://example.test")
        err = httpx.HTTPStatusError(
            "error", request=request, response=MagicMock(status_code=status_code)
        )
        resp.raise_for_status = MagicMock(side_effect=err)
    else:
        resp.raise_for_status = MagicMock(return_value=None)

    return resp


def _adapter(client_id="cid", client_secret="secret") -> INSEELocalAdapter:
    """Build an adapter with a mocked HTTP client and known credentials."""
    adapter = INSEELocalAdapter(client_id=client_id, client_secret=client_secret)
    adapter._client = AsyncMock()
    return adapter


def _prime_token(adapter: INSEELocalAdapter, token: str = "tok-123") -> None:
    """Pre-seed a valid cached OAuth2 token so token fetches are skipped."""
    adapter._access_token = token
    adapter._token_expires_at = datetime.now() + timedelta(hours=1)


# --------------------------------------------------------------------------- #
# __init__ / configuration
# --------------------------------------------------------------------------- #
class TestInit:
    async def test_default_config_values(self):
        adapter = INSEELocalAdapter(client_id="x", client_secret="y")
        assert adapter.config.name == "insee_local"
        assert adapter.config.base_url == INSEELocalAdapter.DONNEES_LOCALES_URL
        assert adapter.config.rate_limit == 30
        assert adapter.config.cache_ttl == 86400 * 7
        assert adapter.name == "insee_local"

    async def test_explicit_config_is_used(self):
        cfg = AdapterConfig(name="custom_insee", base_url="https://x.test", rate_limit=5)
        adapter = INSEELocalAdapter(config=cfg, client_id="x", client_secret="y")
        assert adapter.config.name == "custom_insee"
        assert adapter.config.rate_limit == 5

    async def test_credentials_from_arguments(self):
        adapter = INSEELocalAdapter(client_id="aaa", client_secret="bbb")
        assert adapter._client_id == "aaa"
        assert adapter._client_secret == "bbb"

    async def test_credentials_fall_back_to_env(self):
        with patch.dict(
            os.environ,
            {"INSEE_CLIENT_ID": "env-id", "INSEE_CLIENT_SECRET": "env-secret"},
            clear=False,
        ):
            adapter = INSEELocalAdapter()
        assert adapter._client_id == "env-id"
        assert adapter._client_secret == "env-secret"

    async def test_token_cache_starts_empty(self):
        adapter = INSEELocalAdapter(client_id="x", client_secret="y")
        assert adapter._access_token is None
        assert adapter._token_expires_at is None

    async def test_geo_levels_constant(self):
        assert INSEELocalAdapter.GEO_LEVELS["COM"] == "Commune"
        assert INSEELocalAdapter.GEO_LEVELS["DEP"] == "Département"
        assert "FE" in INSEELocalAdapter.GEO_LEVELS


# --------------------------------------------------------------------------- #
# _get_access_token
# --------------------------------------------------------------------------- #
class TestGetAccessToken:
    async def test_returns_cached_token_when_valid(self):
        adapter = _adapter()
        _prime_token(adapter, "cached-tok")
        token = await adapter._get_access_token()
        assert token == "cached-tok"
        adapter._client.post.assert_not_called()

    async def test_refreshes_when_token_near_expiry(self):
        adapter = _adapter()
        # Token expiring in 30s -> within the 1-minute refresh margin.
        adapter._access_token = "old"
        adapter._token_expires_at = datetime.now() + timedelta(seconds=30)
        adapter._client.post.return_value = _make_response(
            json_data={"access_token": "fresh", "expires_in": 3600}
        )
        token = await adapter._get_access_token()
        assert token == "fresh"
        adapter._client.post.assert_awaited_once()

    async def test_no_credentials_returns_none(self):
        adapter = _adapter(client_id=None, client_secret=None)
        token = await adapter._get_access_token()
        assert token is None
        adapter._client.post.assert_not_called()

    async def test_missing_secret_only_returns_none(self):
        adapter = _adapter(client_id="id", client_secret=None)
        assert await adapter._get_access_token() is None

    async def test_successful_token_fetch_sets_expiry(self):
        adapter = _adapter()
        adapter._client.post.return_value = _make_response(
            json_data={"access_token": "abc", "expires_in": 1200}
        )
        before = datetime.now()
        token = await adapter._get_access_token()
        assert token == "abc"
        assert adapter._access_token == "abc"
        assert adapter._token_expires_at is not None
        # Expiry should be roughly now + 1200s.
        delta = (adapter._token_expires_at - before).total_seconds()
        assert 1190 <= delta <= 1210

    async def test_token_request_payload(self):
        adapter = _adapter(client_id="my-id", client_secret="my-secret")
        adapter._client.post.return_value = _make_response(
            json_data={"access_token": "abc", "expires_in": 3600}
        )
        await adapter._get_access_token()
        _, kwargs = adapter._client.post.call_args
        assert adapter._client.post.call_args.args[0] == INSEELocalAdapter.TOKEN_URL
        assert kwargs["data"]["grant_type"] == "client_credentials"
        assert kwargs["data"]["client_id"] == "my-id"
        assert kwargs["data"]["client_secret"] == "my-secret"
        assert "x-www-form-urlencoded" in kwargs["headers"]["Content-Type"]

    async def test_default_expires_in_when_missing(self):
        adapter = _adapter()
        adapter._client.post.return_value = _make_response(json_data={"access_token": "abc"})
        before = datetime.now()
        await adapter._get_access_token()
        delta = (adapter._token_expires_at - before).total_seconds()
        # Defaults to 3600s.
        assert 3590 <= delta <= 3610

    async def test_http_error_returns_none(self):
        adapter = _adapter()
        adapter._client.post.side_effect = httpx.ConnectError("boom")
        token = await adapter._get_access_token()
        assert token is None

    async def test_http_status_error_returns_none(self):
        adapter = _adapter()
        adapter._client.post.return_value = _make_response(
            status_code=401, raise_http_error=True
        )
        token = await adapter._get_access_token()
        assert token is None


# --------------------------------------------------------------------------- #
# _api_request
# --------------------------------------------------------------------------- #
class TestApiRequest:
    async def test_no_token_returns_none(self):
        adapter = _adapter(client_id=None, client_secret=None)
        result = await adapter._api_request("/donnees/x")
        assert result is None
        adapter._client.get.assert_not_called()

    async def test_builds_url_and_auth_header(self):
        adapter = _adapter()
        _prime_token(adapter, "TOKVAL")
        adapter._client.get.return_value = _make_response(json_data={"ok": True})
        result = await adapter._api_request("/donnees/geo-75@DEP/jeuDeDonnees/X", params={"a": 1})
        assert result == {"ok": True}
        args, kwargs = adapter._client.get.call_args
        assert args[0] == f"{INSEELocalAdapter.DONNEES_LOCALES_URL}/donnees/geo-75@DEP/jeuDeDonnees/X"
        assert kwargs["headers"]["Authorization"] == "Bearer TOKVAL"
        assert kwargs["headers"]["Accept"] == "application/json"
        assert kwargs["params"] == {"a": 1}

    async def test_http_error_returns_none_and_logs(self):
        adapter = _adapter()
        _prime_token(adapter)
        adapter._client.get.return_value = _make_response(
            status_code=500, raise_http_error=True
        )
        result = await adapter._api_request("/donnees/x")
        assert result is None


# --------------------------------------------------------------------------- #
# search() dispatch
# --------------------------------------------------------------------------- #
class TestSearchDispatch:
    async def test_default_type_is_population(self):
        adapter = _adapter()
        adapter._get_population = AsyncMock(return_value=[{"type": "population"}])
        result = await adapter.search({})
        adapter._get_population.assert_awaited_once()
        assert result == [{"type": "population"}]

    async def test_dispatch_logement(self):
        adapter = _adapter()
        adapter._get_logement = AsyncMock(return_value=["L"])
        assert await adapter.search({"type": "logement"}) == ["L"]
        adapter._get_logement.assert_awaited_once()

    async def test_dispatch_revenus(self):
        adapter = _adapter()
        adapter._get_revenus = AsyncMock(return_value=["R"])
        assert await adapter.search({"type": "revenus"}) == ["R"]

    async def test_dispatch_emploi(self):
        adapter = _adapter()
        adapter._get_emploi = AsyncMock(return_value=["E"])
        assert await adapter.search({"type": "emploi"}) == ["E"]

    async def test_dispatch_indicateur(self):
        adapter = _adapter()
        adapter._get_indicateur = AsyncMock(return_value=["I"])
        assert await adapter.search({"type": "indicateur"}) == ["I"]

    async def test_unknown_type_falls_back_to_dossier_complet(self):
        adapter = _adapter()
        adapter._get_dossier_complet = AsyncMock(return_value=["D"])
        assert await adapter.search({"type": "whatever"}) == ["D"]
        adapter._get_dossier_complet.assert_awaited_once()


# --------------------------------------------------------------------------- #
# _get_indicateur
# --------------------------------------------------------------------------- #
class TestGetIndicateur:
    async def test_no_geo_code_returns_empty(self):
        adapter = _adapter()
        assert await adapter._get_indicateur({}) == []

    async def test_builds_endpoint_and_maps_response(self):
        adapter = _adapter()
        _prime_token(adapter)
        adapter._api_request = AsyncMock(return_value={"Cellule": []})
        result = await adapter._get_indicateur(
            {"niveau_geo": "DEP", "code_departement": "59", "indicateur": "POP_X"}
        )
        adapter._api_request.assert_awaited_once_with(
            "/donnees/geo-59@DEP/jeuDeDonnees/POP_X"
        )
        assert len(result) == 1
        entry = result[0]
        assert entry["source"] == "insee_local"
        assert entry["type"] == "indicateur"
        assert entry["indicateur"] == "POP_X"
        assert entry["niveau_geo"] == "DEP"
        assert entry["code_geo"] == "59"
        assert entry["data"] == {"Cellule": []}

    async def test_default_niveau_and_indicateur(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value={"data": 1})
        await adapter._get_indicateur({"code_insee": "59350"})
        adapter._api_request.assert_awaited_once_with(
            "/donnees/geo-59350@DEP/jeuDeDonnees/GEO2024POP_G"
        )

    async def test_code_priority_departement_over_insee(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value={"data": 1})
        await adapter._get_indicateur(
            {"code_departement": "59", "code_insee": "59350", "code_region": "32"}
        )
        # code_departement wins.
        assert "geo-59@" in adapter._api_request.call_args.args[0]

    async def test_region_used_when_only_region_present(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value={"data": 1})
        await adapter._get_indicateur({"code_region": "32"})
        assert "geo-32@" in adapter._api_request.call_args.args[0]

    async def test_falls_back_to_population_when_no_data(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value=None)
        adapter._get_population_fallback = AsyncMock(return_value=["FB"])
        result = await adapter._get_indicateur({"code_departement": "59"})
        assert result == ["FB"]
        adapter._get_population_fallback.assert_awaited_once()


# --------------------------------------------------------------------------- #
# _get_population (+ fallback)
# --------------------------------------------------------------------------- #
class TestGetPopulation:
    async def test_authenticated_population_with_indicators(self):
        adapter = _adapter()
        data = {"Cellule": [{"Mesure": "POP", "Valeur": "1234"}]}
        adapter._api_request = AsyncMock(return_value=data)
        result = await adapter._get_population({"code_departement": "75"})
        adapter._api_request.assert_awaited_once_with(
            "/donnees/geo-75@DEP/jeuDeDonnees/GEO2024POP_G"
        )
        assert len(result) == 1
        assert result[0]["authenticated"] is True
        assert result[0]["niveau_geo"] == "DEP"
        assert result[0]["code_geo"] == "75"
        assert result[0]["indicateurs"] == {"POP": 1234.0}

    async def test_falls_back_when_api_returns_none(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value=None)
        adapter._get_population_fallback = AsyncMock(return_value=["FB"])
        result = await adapter._get_population({"code_departement": "75"})
        assert result == ["FB"]

    async def test_no_dept_goes_straight_to_fallback(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value={"data": 1})
        adapter._get_population_fallback = AsyncMock(return_value=["FB"])
        result = await adapter._get_population({"code_insee": "75056"})
        # With no code_departement, the authenticated branch is skipped entirely.
        adapter._api_request.assert_not_awaited()
        assert result == ["FB"]


class TestGetPopulationFallback:
    async def test_department_aggregates_population(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            json_data=[
                {"population": 100},
                {"population": 250},
                {},  # missing population -> 0
            ]
        )
        result = await adapter._get_population_fallback({"code_departement": "59"})
        assert len(result) == 1
        entry = result[0]
        assert entry["niveau_geo"] == "DEP"
        assert entry["population_totale"] == 350
        assert entry["nombre_communes"] == 3
        assert entry["authenticated"] is False
        # Correct geo API URL + fields param.
        args, kwargs = adapter._client.get.call_args
        assert args[0] == "https://geo.api.gouv.fr/departements/59/communes"
        assert kwargs["params"] == {"fields": "population"}

    async def test_department_http_error_returns_empty(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            status_code=503, raise_http_error=True
        )
        result = await adapter._get_population_fallback({"code_departement": "59"})
        assert result == []

    async def test_commune_population(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            json_data={
                "code": "59350",
                "nom": "Lille",
                "population": 234475,
                "densité": 6634,
            }
        )
        result = await adapter._get_population_fallback({"code_insee": "59350"})
        assert len(result) == 1
        entry = result[0]
        assert entry["code_insee"] == "59350"
        assert entry["nom"] == "Lille"
        assert entry["population"] == 234475
        assert entry["densite"] == 6634
        assert entry["authenticated"] is False
        args, kwargs = adapter._client.get.call_args
        assert args[0] == "https://geo.api.gouv.fr/communes/59350"

    async def test_commune_http_error_returns_empty(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            status_code=404, raise_http_error=True
        )
        result = await adapter._get_population_fallback({"code_insee": "00000"})
        assert result == []

    async def test_no_codes_returns_empty(self):
        adapter = _adapter()
        result = await adapter._get_population_fallback({})
        assert result == []
        adapter._client.get.assert_not_called()

    async def test_department_takes_priority_over_commune(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(json_data=[{"population": 10}])
        result = await adapter._get_population_fallback(
            {"code_departement": "59", "code_insee": "59350"}
        )
        # Department branch handles it and returns -> commune branch never reached.
        assert result[0]["niveau_geo"] == "DEP"
        assert adapter._client.get.call_count == 1


# --------------------------------------------------------------------------- #
# _extract_population_indicators / _extract_housing_indicators
# --------------------------------------------------------------------------- #
class TestExtractIndicators:
    async def test_population_indicators_parsed(self):
        adapter = _adapter()
        data = {
            "Cellule": [
                {"Mesure": "POP_TOTAL", "Valeur": "1000"},
                {"Mesure": "POP_HOMMES", "Valeur": "480.5"},
            ]
        }
        out = adapter._extract_population_indicators(data)
        assert out == {"POP_TOTAL": 1000.0, "POP_HOMMES": 480.5}

    async def test_population_no_cellule_returns_empty(self):
        adapter = _adapter()
        assert adapter._extract_population_indicators({"other": 1}) == {}

    async def test_population_skips_cells_without_measure_or_value(self):
        adapter = _adapter()
        data = {
            "Cellule": [
                {"Mesure": "X"},  # no value
                {"Valeur": "10"},  # no measure
                {"Mesure": "Y", "Valeur": "5"},
            ]
        }
        out = adapter._extract_population_indicators(data)
        assert out == {"Y": 5.0}

    async def test_housing_indicators_with_modalite_key(self):
        adapter = _adapter()
        data = {
            "Cellule": [
                {"Mesure": "LOG", "Valeur": "100", "Modalite": "PRINCIPALE"},
                {"Mesure": "LOG", "Valeur": "20"},  # no modalite -> plain measure key
            ]
        }
        out = adapter._extract_housing_indicators(data)
        assert out["LOG_PRINCIPALE"] == 100.0
        assert out["LOG"] == 20.0

    async def test_housing_no_cellule_returns_empty(self):
        adapter = _adapter()
        assert adapter._extract_housing_indicators({}) == {}


# --------------------------------------------------------------------------- #
# _get_logement
# --------------------------------------------------------------------------- #
class TestGetLogement:
    async def test_no_geo_code_returns_empty(self):
        adapter = _adapter()
        assert await adapter._get_logement({}) == []

    async def test_authenticated_logement(self):
        adapter = _adapter()
        data = {"Cellule": [{"Mesure": "LOG", "Valeur": "50", "Modalite": "VAC"}]}
        adapter._api_request = AsyncMock(return_value=data)
        result = await adapter._get_logement({"code_departement": "59"})
        adapter._api_request.assert_awaited_once_with(
            "/donnees/geo-59@DEP/jeuDeDonnees/GEO2024LOG_G"
        )
        assert result[0]["authenticated"] is True
        assert result[0]["niveau_geo"] == "DEP"
        assert result[0]["indicateurs"] == {"LOG_VAC": 50.0}

    async def test_commune_niveau_geo_is_com(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value={"Cellule": []})
        await adapter._get_logement({"code_insee": "59350"})
        assert "geo-59350@COM" in adapter._api_request.call_args.args[0]

    async def test_fallback_when_no_data(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value=None)
        result = await adapter._get_logement({"code_departement": "59"})
        assert result[0]["authenticated"] is False
        assert "indicators_available" in result[0]
        assert "residences_principales" in result[0]["indicators_available"]
        assert result[0]["url"].startswith("https://statistiques-locales.insee.fr")


# --------------------------------------------------------------------------- #
# _get_revenus
# --------------------------------------------------------------------------- #
class TestGetRevenus:
    async def test_no_geo_code_returns_empty(self):
        adapter = _adapter()
        assert await adapter._get_revenus({}) == []

    async def test_authenticated_revenus(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value={"some": "data"})
        result = await adapter._get_revenus({"code_departement": "75"})
        adapter._api_request.assert_awaited_once_with(
            "/donnees/geo-75@DEP/jeuDeDonnees/GEO2024REV_G"
        )
        assert result[0]["authenticated"] is True
        assert result[0]["data"] == {"some": "data"}

    async def test_fallback_when_no_data(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value=None)
        result = await adapter._get_revenus({"code_insee": "75056"})
        assert result[0]["authenticated"] is False
        assert result[0]["url"] == "https://statistiques-locales.insee.fr"
        assert "geo-75056@COM" not in str(result[0])  # commune niveau used internally


# --------------------------------------------------------------------------- #
# _get_emploi
# --------------------------------------------------------------------------- #
class TestGetEmploi:
    async def test_no_geo_code_returns_empty(self):
        adapter = _adapter()
        assert await adapter._get_emploi({}) == []

    async def test_authenticated_emploi(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value={"emp": 1})
        result = await adapter._get_emploi({"code_departement": "59"})
        adapter._api_request.assert_awaited_once_with(
            "/donnees/geo-59@DEP/jeuDeDonnees/GEO2024EMP_G"
        )
        assert result[0]["authenticated"] is True
        assert result[0]["type"] == "emploi"

    async def test_fallback_when_no_data(self):
        adapter = _adapter()
        adapter._api_request = AsyncMock(return_value=None)
        result = await adapter._get_emploi({"code_insee": "59350"})
        assert result[0]["authenticated"] is False
        assert result[0]["url"] == "https://statistiques-locales.insee.fr"


# --------------------------------------------------------------------------- #
# _get_dossier_complet
# --------------------------------------------------------------------------- #
class TestGetDossierComplet:
    async def test_builds_dossier_url(self):
        adapter = _adapter()
        result = await adapter._get_dossier_complet({"code_insee": "59350"})
        assert len(result) == 1
        entry = result[0]
        assert entry["type"] == "dossier_complet"
        assert entry["code_insee"] == "59350"
        assert "geo=COM-59350" in entry["url"]
        assert "population" in entry["sections"]

    async def test_handles_missing_code_insee(self):
        adapter = _adapter()
        result = await adapter._get_dossier_complet({})
        assert result[0]["code_insee"] is None


# --------------------------------------------------------------------------- #
# get_by_id
# --------------------------------------------------------------------------- #
class TestGetById:
    async def test_returns_first_population_result(self):
        adapter = _adapter()
        adapter._get_population = AsyncMock(return_value=[{"code_insee": "59350"}])
        result = await adapter.get_by_id("59350")
        assert result == {"code_insee": "59350"}
        adapter._get_population.assert_awaited_once_with({"code_insee": "59350"})

    async def test_returns_none_when_no_results(self):
        adapter = _adapter()
        adapter._get_population = AsyncMock(return_value=[])
        assert await adapter.get_by_id("00000") is None


# --------------------------------------------------------------------------- #
# get_population (high-level helper using geo API)
# --------------------------------------------------------------------------- #
class TestGetPopulationHelper:
    async def test_department_two_digit_code(self):
        adapter = _adapter()
        dept_resp = _make_response(
            json_data={"nom": "Nord", "code": "59", "codeRegion": "32"}
        )
        communes_resp = _make_response(
            json_data=[
                {"nom": "A", "population": 1000, "surface": 10000},  # 100 km2
                {"nom": "B", "population": 500, "surface": 10000},  # 100 km2
            ]
        )
        adapter._client.get.side_effect = [dept_resp, communes_resp]
        result = await adapter.get_population("59")
        assert result["code"] == "59"
        assert result["nom"] == "Nord"
        assert result["population"] == 1500
        assert result["nb_communes"] == 2
        # surface 20000 ha / 100 = 200 km2; densite = 1500/200 = 7.5
        assert result["surface_km2"] == 200
        assert result["densite"] == 7.5

    async def test_department_zero_surface_avoids_division_error(self):
        adapter = _adapter()
        dept_resp = _make_response(json_data={"nom": "X", "code": "00"})
        communes_resp = _make_response(json_data=[{"population": 100, "surface": 0}])
        adapter._client.get.side_effect = [dept_resp, communes_resp]
        result = await adapter.get_population("00")
        # max(1, surface) guard -> densite = pop / 1
        assert result["densite"] == 100

    async def test_commune_five_digit_code(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            json_data={
                "nom": "Lille",
                "population": 234000,
                "surface": 3483,  # ha
                "departement": {"code": "59", "nom": "Nord"},
            }
        )
        result = await adapter.get_population("59350")
        assert result["code"] == "59350"
        assert result["nom"] == "Lille"
        assert result["population"] == 234000
        assert result["surface_km2"] == 34.83
        assert result["departement"] == {"code": "59", "nom": "Nord"}
        # only ONE call for a commune
        assert adapter._client.get.call_count == 1

    async def test_commune_default_surface_one_when_missing(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            json_data={"nom": "Tiny", "population": 5}
        )
        result = await adapter.get_population("12345")
        # surface defaults to 1 ha -> 0.01 km2 -> max(1, 0.01) = 1 -> densite = 5
        assert result["surface_km2"] == 0.01
        assert result["densite"] == 5

    async def test_http_error_returns_none(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            status_code=500, raise_http_error=True
        )
        assert await adapter.get_population("59") is None


# --------------------------------------------------------------------------- #
# get_commune_profile
# --------------------------------------------------------------------------- #
class TestGetCommuneProfile:
    async def test_maps_geo_response(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            json_data={
                "nom": "Lille",
                "code": "59350",
                "population": 234000,
                "departement": {"code": "59"},
                "region": {"code": "32"},
                "codesPostaux": ["59000", "59800"],
                "centre": {"coordinates": [3.0573, 50.6292]},
            }
        )
        result = await adapter.get_commune_profile("59350")
        assert result["source"] == "insee_local"
        assert result["code_insee"] == "59350"
        assert result["nom"] == "Lille"
        assert result["codes_postaux"] == ["59000", "59800"]
        # GeoJSON coords are [lon, lat] -> we map lat then lon.
        assert result["geo"]["lat"] == 50.6292
        assert result["geo"]["lon"] == 3.0573

    async def test_missing_centre_defaults_to_zero(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(json_data={"nom": "X"})
        result = await adapter.get_commune_profile("12345")
        assert result["geo"]["lat"] == 0
        assert result["geo"]["lon"] == 0
        assert result["codes_postaux"] == []

    async def test_http_error_returns_error_dict(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            status_code=500, raise_http_error=True
        )
        result = await adapter.get_commune_profile("59350")
        assert result["code_insee"] == "59350"
        assert "error" in result


# --------------------------------------------------------------------------- #
# get_department_stats
# --------------------------------------------------------------------------- #
class TestGetDepartmentStats:
    async def test_full_authenticated_flow(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            json_data={"nom": "Nord", "code": "59", "codeRegion": "32"}
        )
        adapter._get_population = AsyncMock(
            return_value=[{"authenticated": True, "indicateurs": {"POP": 1000.0}}]
        )
        adapter._get_emploi = AsyncMock(
            return_value=[{"authenticated": True, "data": {"emp": 42}}]
        )
        result = await adapter.get_department_stats("59")
        assert result["code"] == "59"
        assert result["nom"] == "Nord"
        assert result["code_region"] == "32"
        assert result["authenticated"] is True
        assert result["population_data"] == {"POP": 1000.0}
        assert result["emploi_data"] == {"emp": 42}

    async def test_unauthenticated_population_uses_total(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            json_data={"nom": "Nord", "codeRegion": "32"}
        )
        adapter._get_population = AsyncMock(
            return_value=[{"authenticated": False, "population_totale": 2600000}]
        )
        adapter._get_emploi = AsyncMock(return_value=[{"authenticated": False}])
        result = await adapter.get_department_stats("59")
        assert result["authenticated"] is False
        assert result["population_totale"] == 2600000
        assert "emploi_data" not in result

    async def test_geo_http_error_still_returns_partial(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(
            status_code=500, raise_http_error=True
        )
        adapter._get_population = AsyncMock(return_value=[])
        adapter._get_emploi = AsyncMock(return_value=[])
        result = await adapter.get_department_stats("59")
        # geo failed -> no 'nom', but base fields stay.
        assert result["code"] == "59"
        assert result["source"] == "insee_local"
        assert "nom" not in result

    async def test_empty_population_and_emploi(self):
        adapter = _adapter()
        adapter._client.get.return_value = _make_response(json_data={"nom": "Nord"})
        adapter._get_population = AsyncMock(return_value=[])
        adapter._get_emploi = AsyncMock(return_value=[])
        result = await adapter.get_department_stats("59")
        assert "authenticated" not in result
        assert "population_data" not in result


# --------------------------------------------------------------------------- #
# Unemployment rates (BDM + SDMX) + cache
# --------------------------------------------------------------------------- #
class TestUnemploymentRates:
    async def test_get_rate_from_bulk_cache(self):
        adapter = _adapter()
        adapter.get_all_unemployment_rates = AsyncMock(return_value={"59": 8.4, "75": 6.1})
        assert await adapter.get_unemployment_rate("59") == 8.4

    async def test_get_rate_missing_department_returns_none(self):
        adapter = _adapter()
        adapter.get_all_unemployment_rates = AsyncMock(return_value={"75": 6.1})
        assert await adapter.get_unemployment_rate("59") is None

    async def test_get_rate_empty_rates_returns_none(self):
        adapter = _adapter()
        adapter.get_all_unemployment_rates = AsyncMock(return_value={})
        assert await adapter.get_unemployment_rate("59") is None

    async def test_all_rates_returns_cached_value(self):
        adapter = _adapter()
        adapter._set_cache("unemployment_rates_all", {"75": 6.1})
        result = await adapter.get_all_unemployment_rates()
        assert result == {"75": 6.1}
        # Cache hit -> no token fetch, no HTTP.
        adapter._client.get.assert_not_called()

    async def test_all_rates_no_token_returns_empty(self):
        adapter = _adapter(client_id=None, client_secret=None)
        result = await adapter.get_all_unemployment_rates()
        assert result == {}
        adapter._client.get.assert_not_called()

    async def test_all_rates_parses_sdmx_and_caches(self):
        adapter = _adapter()
        _prime_token(adapter)
        xml = (
            '<Series REF_AREA="D75"><Obs OBS_VALUE="6.1"/></Series>'
            '<Series REF_AREA="D59"><Obs OBS_VALUE="8.4"/></Series>'
        )
        adapter._client.get.return_value = _make_response(text=xml)
        result = await adapter.get_all_unemployment_rates()
        assert result == {"75": 6.1, "59": 8.4}
        # Subsequent call served from cache (no extra HTTP).
        adapter._client.get.reset_mock()
        cached = await adapter.get_all_unemployment_rates()
        assert cached == {"75": 6.1, "59": 8.4}
        adapter._client.get.assert_not_called()

    async def test_all_rates_request_params_and_headers(self):
        adapter = _adapter()
        _prime_token(adapter, "TK")
        adapter._client.get.return_value = _make_response(
            text='<Series REF_AREA="D2A"><Obs OBS_VALUE="9.0"/></Series>'
        )
        await adapter.get_all_unemployment_rates()
        args, kwargs = adapter._client.get.call_args
        assert args[0] == "https://api.insee.fr/series/BDM/V1/data/TAUX-CHOMAGE"
        assert kwargs["params"] == {"lastNObservations": "1"}
        assert kwargs["headers"]["Authorization"] == "Bearer TK"
        assert kwargs["headers"]["Accept"] == "application/xml"

    async def test_all_rates_empty_parse_returns_empty_not_cached(self):
        adapter = _adapter()
        _prime_token(adapter)
        adapter._client.get.return_value = _make_response(text="<root>no series</root>")
        result = await adapter.get_all_unemployment_rates()
        assert result == {}
        # Empty results are NOT cached -> internal cache stays absent.
        assert adapter._get_cache("unemployment_rates_all") is None

    async def test_all_rates_http_error_returns_empty(self):
        adapter = _adapter()
        _prime_token(adapter)
        adapter._client.get.return_value = _make_response(
            status_code=500, raise_http_error=True
        )
        result = await adapter.get_all_unemployment_rates()
        assert result == {}


# --------------------------------------------------------------------------- #
# _parse_unemployment_sdmx
# --------------------------------------------------------------------------- #
class TestParseUnemploymentSdmx:
    async def test_basic_parse(self):
        adapter = _adapter()
        xml = '<Series REF_AREA="D75"><Obs OBS_VALUE="6.1"/></Series>'
        assert adapter._parse_unemployment_sdmx(xml) == {"75": 6.1}

    async def test_corsica_codes(self):
        adapter = _adapter()
        xml = (
            '<Series REF_AREA="D2A"><Obs OBS_VALUE="7.5"/></Series>'
            '<Series REF_AREA="D2B"><Obs OBS_VALUE="8.1"/></Series>'
        )
        out = adapter._parse_unemployment_sdmx(xml)
        assert out["2A"] == 7.5
        assert out["2B"] == 8.1

    async def test_overseas_three_digit_code(self):
        adapter = _adapter()
        xml = '<Series REF_AREA="D971"><Obs OBS_VALUE="18.9"/></Series>'
        out = adapter._parse_unemployment_sdmx(xml)
        assert out["971"] == 18.9

    async def test_strips_d_prefix(self):
        adapter = _adapter()
        xml = '<Series REF_AREA="D01"><Obs OBS_VALUE="5.0"/></Series>'
        assert "01" in adapter._parse_unemployment_sdmx(xml)

    async def test_empty_xml_returns_empty(self):
        adapter = _adapter()
        assert adapter._parse_unemployment_sdmx("") == {}

    async def test_no_matching_series_returns_empty(self):
        adapter = _adapter()
        xml = '<Series REF_AREA="X99"><Obs OBS_VALUE="1.0"/></Series>'
        # REF_AREA must start with D[0-9A-B] -> X is ignored.
        assert adapter._parse_unemployment_sdmx(xml) == {}

    async def test_multiline_series_with_dotall(self):
        adapter = _adapter()
        xml = (
            '<Series REF_AREA="D33">\n'
            "  <some-other-tag/>\n"
            '  <Obs OBS_VALUE="7.2"/>\n'
            "</Series>"
        )
        assert adapter._parse_unemployment_sdmx(xml) == {"33": 7.2}

    async def test_malformed_value_is_skipped(self):
        adapter = _adapter()
        # "1.2.3" matches the [0-9.]+ capture group but float() raises ValueError,
        # so the department is skipped rather than crashing the whole parse.
        xml = (
            '<Series REF_AREA="D11"><Obs OBS_VALUE="1.2.3"/></Series>'
            '<Series REF_AREA="D12"><Obs OBS_VALUE="5.5"/></Series>'
        )
        out = adapter._parse_unemployment_sdmx(xml)
        assert "11" not in out
        assert out["12"] == 5.5


# --------------------------------------------------------------------------- #
# Cache helpers (_set_cache / _get_cache)
# --------------------------------------------------------------------------- #
class TestCacheHelpers:
    async def test_get_cache_before_any_set_returns_none(self):
        adapter = _adapter()
        assert adapter._get_cache("nope") is None

    async def test_set_then_get(self):
        adapter = _adapter()
        adapter._set_cache("k", {"a": 1})
        assert adapter._get_cache("k") == {"a": 1}

    async def test_get_missing_key_after_set_returns_none(self):
        adapter = _adapter()
        adapter._set_cache("k", 1)
        assert adapter._get_cache("other") is None

    async def test_expired_cache_returns_none(self):
        adapter = _adapter()
        adapter._set_cache("k", "v")
        # Force the timestamp to be older than the 6h TTL.
        adapter._local_cache_timestamps["k"] = datetime.now() - timedelta(hours=7)
        assert adapter._get_cache("k") is None

    async def test_fresh_cache_within_ttl_returns_value(self):
        adapter = _adapter()
        adapter._set_cache("k", "v")
        adapter._local_cache_timestamps["k"] = datetime.now() - timedelta(hours=5)
        assert adapter._get_cache("k") == "v"


# --------------------------------------------------------------------------- #
# health_check
# --------------------------------------------------------------------------- #
class TestHealthCheck:
    async def test_oauth_success_returns_true(self):
        adapter = _adapter()
        _prime_token(adapter, "tok")
        assert await adapter.health_check() is True
        # geo fallback not needed.
        adapter._client.get.assert_not_called()

    async def test_falls_back_to_geo_api_200(self):
        adapter = _adapter(client_id=None, client_secret=None)
        adapter._client.get.return_value = _make_response(status_code=200)
        assert await adapter.health_check() is True
        args, kwargs = adapter._client.get.call_args
        assert args[0] == "https://geo.api.gouv.fr/communes"
        assert kwargs["params"] == {"nom": "Paris", "limit": 1}

    async def test_geo_api_non_200_returns_false(self):
        adapter = _adapter(client_id=None, client_secret=None)
        adapter._client.get.return_value = _make_response(status_code=503)
        assert await adapter.health_check() is False

    async def test_geo_api_exception_returns_false(self):
        adapter = _adapter(client_id=None, client_secret=None)
        adapter._client.get.side_effect = httpx.ConnectError("down")
        assert await adapter.health_check() is False


# --------------------------------------------------------------------------- #
# sync
# --------------------------------------------------------------------------- #
class TestSync:
    async def test_sync_returns_not_supported(self):
        adapter = _adapter()
        status = await adapter.sync()
        assert isinstance(status, SyncStatus)
        assert status.adapter_name == "insee_local"
        assert status.status == "not_supported"
        assert status.records_synced == 0
        assert status.last_sync is None
        assert "annually" in status.error

    async def test_sync_ignores_since_argument(self):
        adapter = _adapter()
        status = await adapter.sync(since=datetime(2020, 1, 1))
        assert status.status == "not_supported"
