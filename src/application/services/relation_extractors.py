"""Relation extractors (Level 1) -- SIRENE, BODACC, BOAMP, RNA, Subventions, EPCI, Incubators, Poles.

Each extractor queries the ``signals`` table (or external APIs) for a given
department and produces dicts of actors and relations ready for upsert by
RelationService.

Actors and relations use deterministic UUIDs (uuid5 with NAMESPACE_DNS) so
that repeated runs for the same department produce stable identifiers,
enabling clean UPSERT semantics.
"""

from __future__ import annotations

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx
from loguru import logger

from src.application.services._db_pool import acquire_conn


def _parse_raw_data(value: Any) -> dict[str, Any]:
    """Parse raw_data which asyncpg returns as a string for JSONB columns."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


# ---------------------------------------------------------------------------
# UUID helpers -- deterministic, stable across runs
# ---------------------------------------------------------------------------


def _stable_uuid(prefix: str, key: str) -> uuid.UUID:
    """Return a deterministic uuid5 from *prefix* + *key*."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"{prefix}:{key}")


def _actor_id(actor_type: str, external_id: str) -> uuid.UUID:
    return _stable_uuid("actor", f"{actor_type}:{external_id}")


def _relation_id(source_ext: str, target_ext: str, subtype: str) -> uuid.UUID:
    return _stable_uuid("relation", f"{source_ext}->{target_ext}:{subtype}")


# ---------------------------------------------------------------------------
# Department name lookup (simple mapping for labels)
# ---------------------------------------------------------------------------

_DEPT_NAMES: dict[str, str] = {
    "01": "Ain",
    "02": "Aisne",
    "03": "Allier",
    "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes",
    "06": "Alpes-Maritimes",
    "07": "Ardeche",
    "08": "Ardennes",
    "09": "Ariege",
    "10": "Aube",
    "11": "Aude",
    "12": "Aveyron",
    "13": "Bouches-du-Rhone",
    "14": "Calvados",
    "15": "Cantal",
    "16": "Charente",
    "17": "Charente-Maritime",
    "18": "Cher",
    "19": "Correze",
    "21": "Cote-d'Or",
    "22": "Cotes-d'Armor",
    "23": "Creuse",
    "24": "Dordogne",
    "25": "Doubs",
    "26": "Drome",
    "27": "Eure",
    "28": "Eure-et-Loir",
    "29": "Finistere",
    "2A": "Corse-du-Sud",
    "2B": "Haute-Corse",
    "30": "Gard",
    "31": "Haute-Garonne",
    "32": "Gers",
    "33": "Gironde",
    "34": "Herault",
    "35": "Ille-et-Vilaine",
    "36": "Indre",
    "37": "Indre-et-Loire",
    "38": "Isere",
    "39": "Jura",
    "40": "Landes",
    "41": "Loir-et-Cher",
    "42": "Loire",
    "43": "Haute-Loire",
    "44": "Loire-Atlantique",
    "45": "Loiret",
    "46": "Lot",
    "47": "Lot-et-Garonne",
    "48": "Lozere",
    "49": "Maine-et-Loire",
    "50": "Manche",
    "51": "Marne",
    "52": "Haute-Marne",
    "53": "Mayenne",
    "54": "Meurthe-et-Moselle",
    "55": "Meuse",
    "56": "Morbihan",
    "57": "Moselle",
    "58": "Nievre",
    "59": "Nord",
    "60": "Oise",
    "61": "Orne",
    "62": "Pas-de-Calais",
    "63": "Puy-de-Dome",
    "64": "Pyrenees-Atlantiques",
    "65": "Hautes-Pyrenees",
    "66": "Pyrenees-Orientales",
    "67": "Bas-Rhin",
    "68": "Haut-Rhin",
    "69": "Rhone",
    "70": "Haute-Saone",
    "71": "Saone-et-Loire",
    "72": "Sarthe",
    "73": "Savoie",
    "74": "Haute-Savoie",
    "75": "Paris",
    "76": "Seine-Maritime",
    "77": "Seine-et-Marne",
    "78": "Yvelines",
    "79": "Deux-Sevres",
    "80": "Somme",
    "81": "Tarn",
    "82": "Tarn-et-Garonne",
    "83": "Var",
    "84": "Vaucluse",
    "85": "Vendee",
    "86": "Vienne",
    "87": "Haute-Vienne",
    "88": "Vosges",
    "89": "Yonne",
    "90": "Territoire de Belfort",
    "91": "Essonne",
    "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne",
    "95": "Val-d'Oise",
    "971": "Guadeloupe",
    "972": "Martinique",
    "973": "Guyane",
    "974": "La Reunion",
    "976": "Mayotte",
}


# ---------------------------------------------------------------------------
# Nature Juridique → actor type mapping (INSEE codes)
# ---------------------------------------------------------------------------

_NJ_TYPE_MAP: list[tuple[str, str, str]] = [
    # (prefix, actor_type, category_label)
    # Associations
    ("9210", "association", "Association loi 1901"),
    ("9220", "association", "Association loi Alsace-Moselle"),
    ("9230", "association", "Association de droit local"),
    ("9240", "association", "Association declaree reconnue d'utilite publique"),
    ("9260", "association", "Association de droit local reconnue d'utilite publique"),
    ("92", "association", "Association"),
    ("93", "association", "Fondation"),
    ("94", "association", "Autre organisme prive fonde sur l'adhesion"),
    # Organismes de formation / enseignement
    ("7321", "formation", "Etablissement public d'enseignement"),
    ("7322", "formation", "Etablissement public de formation"),
    ("7323", "formation", "Lycee/college public"),
    ("8510", "formation", "Organisme de formation prive"),
    ("8520", "formation", "Enseignement secondaire prive"),
    ("8530", "formation", "Enseignement superieur prive"),
    ("8541", "formation", "CFA prive"),
    ("85", "formation", "Enseignement"),
    # Institutions financieres
    ("6411", "financial", "Banque centrale"),
    ("6419", "financial", "Autre intermediation monetaire"),
    ("6430", "financial", "Fonds de placement"),
    ("6491", "financial", "Credit-bail"),
    ("6492", "financial", "Autre distribution de credit"),
    ("6499", "financial", "Autre intermediation financiere"),
    ("6511", "financial", "Assurance vie"),
    ("6512", "financial", "Assurance non-vie"),
    ("6520", "financial", "Reassurance"),
    ("6530", "financial", "Caisse de retraite"),
    ("64", "financial", "Intermediation financiere"),
    ("65", "financial", "Assurance"),
    ("66", "financial", "Activites auxiliaires financieres"),
    # Etablissements publics → institution
    ("71", "institution", "Etablissement public administratif"),
    ("72", "institution", "Collectivite territoriale"),
    ("73", "institution", "Etablissement public hospitalier"),
    ("74", "institution", "Autre organisme public"),
]


def _classify_nature_juridique(nj_code: str | None) -> tuple[str, str] | None:
    """Return (actor_type, category_label) for a nature_juridique code, or None."""
    if not nj_code:
        return None
    nj = str(nj_code).strip()
    for prefix, actor_type, label in sorted(_NJ_TYPE_MAP, key=lambda x: -len(x[0])):
        if nj.startswith(prefix):
            return (actor_type, label)
    return None


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseExtractor(ABC):
    """Base class for L1 relation extractors."""

    source_name: str = ""

    @abstractmethod
    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        """Return ``{"actors": [...], "relations": [...]}``."""
        ...


# ---------------------------------------------------------------------------
# SIRENE extractor
# ---------------------------------------------------------------------------


class SireneExtractor(BaseExtractor):
    """Extract actors and relations from SIRENE signals.

    Handles two signal formats found in the ``signals`` table:

    1. **Aggregate** (sector-level): ``{"naf", "label", "total", "sample_size"}``
       -- creates *sector* actors and a territory->sector relation.

    2. **Individual** (enterprise-level): ``{"siren", "nom", "naf",
       "nature_juridique", "tranche_effectif"}``
       -- creates *enterprise* actors plus enterprise->territory and
       enterprise->sector relations.
    """

    source_name = "sirene"

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}  # keyed by external_id
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT raw_data, metric_name, metric_value, event_date, collected_at
                FROM signals
                WHERE source = 'sirene' AND code_dept = $1
                ORDER BY collected_at DESC
                """,
                department_code,
            )

        if not rows:
            logger.info("SireneExtractor: no signals for dept {}", department_code)
            return {"actors": [], "relations": []}

        # -- Ensure the territory actor exists --
        territory_ext_id = f"DEPT:{department_code}"
        territory_name = _DEPT_NAMES.get(department_code, f"Departement {department_code}")
        actors[territory_ext_id] = {
            "id": str(_actor_id("territory", territory_ext_id)),
            "type": "territory",
            "external_id": territory_ext_id,
            "name": territory_name,
            "department_code": department_code,
            "metadata": {"level": "department"},
        }

        for row in rows:
            rd = _parse_raw_data(row["raw_data"])
            naf_code = rd.get("naf", "")
            naf_label = rd.get("label", "")

            # ------- Individual enterprise signal -------
            siren = rd.get("siren")
            if siren:
                enterprise_name = rd.get("nom", f"Entreprise {siren}")
                ent_ext_id = f"SIREN:{siren}"

                # Actor: enterprise
                if ent_ext_id not in actors:
                    actors[ent_ext_id] = {
                        "id": str(_actor_id("enterprise", ent_ext_id)),
                        "type": "enterprise",
                        "external_id": ent_ext_id,
                        "name": enterprise_name,
                        "department_code": department_code,
                        "metadata": {},
                    }
                # Merge metadata (keep richest version)
                ent_meta = actors[ent_ext_id]["metadata"]
                if naf_code:
                    ent_meta["naf"] = naf_code
                    ent_meta["naf_label"] = naf_label
                if rd.get("nature_juridique"):
                    ent_meta["nature_juridique"] = rd["nature_juridique"]
                if rd.get("tranche_effectif"):
                    ent_meta["tranche_effectif"] = rd["tranche_effectif"]

                # Relation: enterprise -> territory (headquarter_in)
                rel_id_ht = _relation_id(ent_ext_id, territory_ext_id, "headquarter_in")
                relations.append(
                    {
                        "id": str(rel_id_ht),
                        "source_actor_external_id": ent_ext_id,
                        "target_actor_external_id": territory_ext_id,
                        "relation_type": "structural",
                        "subtype": "headquarter_in",
                        "confidence": 0.95,
                        "weight": 1.0,
                        "evidence": {
                            "source": "sirene",
                            "siren": siren,
                            "department": department_code,
                        },
                        "source_type": "sirene",
                        "source_ref": f"signal:sirene:{siren}:{department_code}",
                    }
                )

                # Relation: enterprise -> sector (belongs_to_sector)
                if naf_code:
                    sector_ext_id = f"NAF:{naf_code}"

                    # Actor: sector
                    if sector_ext_id not in actors:
                        actors[sector_ext_id] = {
                            "id": str(_actor_id("sector", sector_ext_id)),
                            "type": "sector",
                            "external_id": sector_ext_id,
                            "name": naf_label or f"Secteur {naf_code}",
                            "department_code": None,  # sectors are national
                            "metadata": {"naf": naf_code},
                        }

                    rel_id_sec = _relation_id(ent_ext_id, sector_ext_id, "belongs_to_sector")
                    relations.append(
                        {
                            "id": str(rel_id_sec),
                            "source_actor_external_id": ent_ext_id,
                            "target_actor_external_id": sector_ext_id,
                            "relation_type": "structural",
                            "subtype": "belongs_to_sector",
                            "confidence": 0.90,
                            "weight": 1.0,
                            "evidence": {
                                "source": "sirene",
                                "siren": siren,
                                "naf": naf_code,
                            },
                            "source_type": "sirene",
                            "source_ref": f"signal:sirene:{siren}:{naf_code}",
                        }
                    )

            # ------- Aggregate sector signal -------
            elif naf_code and not siren:
                sector_ext_id = f"NAF:{naf_code}"
                total_enterprises = rd.get("total", 0)

                # Actor: sector
                if sector_ext_id not in actors:
                    actors[sector_ext_id] = {
                        "id": str(_actor_id("sector", sector_ext_id)),
                        "type": "sector",
                        "external_id": sector_ext_id,
                        "name": naf_label or f"Secteur {naf_code}",
                        "department_code": None,
                        "metadata": {"naf": naf_code},
                    }
                # Enrich metadata with aggregate stats per department
                sec_meta = actors[sector_ext_id]["metadata"]
                dept_key = f"count_{department_code}"
                sec_meta[dept_key] = total_enterprises

                # Relation: sector -> territory (sector_present_in)
                rel_id_sp = _relation_id(sector_ext_id, territory_ext_id, "sector_present_in")
                # Weight proportional to enterprise count (normalize later if needed)
                weight = min(total_enterprises / 1000.0, 10.0) if total_enterprises else 1.0
                relations.append(
                    {
                        "id": str(rel_id_sp),
                        "source_actor_external_id": sector_ext_id,
                        "target_actor_external_id": territory_ext_id,
                        "relation_type": "structural",
                        "subtype": "sector_present_in",
                        "confidence": 0.92,
                        "weight": weight,
                        "evidence": {
                            "source": "sirene",
                            "naf": naf_code,
                            "total_enterprises": total_enterprises,
                            "department": department_code,
                        },
                        "source_type": "sirene",
                        "source_ref": f"signal:sirene:agg:{naf_code}:{department_code}",
                    }
                )

        logger.info(
            "SireneExtractor dept={}: {} actors, {} relations extracted",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# BODACC extractor
# ---------------------------------------------------------------------------

# Mapping from BODACC famille / metric_name to relation subtype
_BODACC_SUBTYPE_MAP: dict[str, str] = {
    # famille field
    "creation": "event_creation",
    "vente": "event_vente",
    "collective": "event_procedure_collective",
    # metric_name field (more granular)
    "immatriculation_rcs": "event_creation",
    "immatriculation": "event_creation",
    "creation_entreprise": "event_creation",
    "radiation": "event_radiation",
    "liquidation_judiciaire": "event_liquidation",
    "redressement_judiciaire": "event_redressement",
    "procedure_collective": "event_procedure_collective",
    "cloture_insuffisance_actif": "event_cloture_insuffisance",
    "plan_cession": "event_plan_cession",
    "plan_continuation": "event_plan_continuation",
}


class BodaccExtractor(BaseExtractor):
    """Extract actors and relations from BODACC signals.

    Handles two BODACC signal formats:

    1. **Simplified**: ``{"cp", "siren", "ville", "nature", "famille",
       "tribunal", "commercant"}``

    2. **Detailed** (from bodacc.fr API): includes ``id``, ``acte``,
       ``familleavis``, ``listepersonnes``, ``listeetablissements``,
       ``numerodepartement``, ``departement_nom_officiel``, etc.

    Both formats always contain a ``siren`` field.
    """

    source_name = "bodacc"

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT raw_data, metric_name, metric_value, event_date, collected_at
                FROM signals
                WHERE source = 'bodacc' AND code_dept = $1
                ORDER BY collected_at DESC
                """,
                department_code,
            )

        if not rows:
            logger.info("BodaccExtractor: no signals for dept {}", department_code)
            return {"actors": [], "relations": []}

        # -- Ensure territory actor --
        territory_ext_id = f"DEPT:{department_code}"
        territory_name = _DEPT_NAMES.get(department_code, f"Departement {department_code}")
        actors[territory_ext_id] = {
            "id": str(_actor_id("territory", territory_ext_id)),
            "type": "territory",
            "external_id": territory_ext_id,
            "name": territory_name,
            "department_code": department_code,
            "metadata": {"level": "department"},
        }

        for row in rows:
            rd = _parse_raw_data(row["raw_data"])
            siren = rd.get("siren")
            if not siren:
                continue  # skip signals without enterprise identifier

            # -- Enterprise name: try commercant, then listepersonnes, fallback --
            enterprise_name = rd.get("commercant", "").strip()
            if not enterprise_name:
                enterprise_name = f"Entreprise {siren}"

            ent_ext_id = f"SIREN:{siren}"

            # Actor: enterprise
            if ent_ext_id not in actors:
                actors[ent_ext_id] = {
                    "id": str(_actor_id("enterprise", ent_ext_id)),
                    "type": "enterprise",
                    "external_id": ent_ext_id,
                    "name": enterprise_name,
                    "department_code": department_code,
                    "metadata": {},
                }

            # Enrich metadata from BODACC
            ent_meta = actors[ent_ext_id]["metadata"]
            if rd.get("ville"):
                ent_meta["ville"] = rd["ville"]
            if rd.get("cp"):
                ent_meta["code_postal"] = rd["cp"]
            if rd.get("tribunal"):
                ent_meta["tribunal"] = rd["tribunal"]

            # -- Determine event subtype --
            # Prefer metric_name (more granular), fallback to famille / familleavis
            metric = row["metric_name"] or ""
            famille = rd.get("famille") or rd.get("familleavis") or ""
            subtype = (
                _BODACC_SUBTYPE_MAP.get(metric)
                or _BODACC_SUBTYPE_MAP.get(famille)
                or f"event_{famille or 'unknown'}"
            )

            # Confidence depends on event type -- procedures collectives are
            # very reliable data, creations/radiations slightly less so
            # (sometimes delayed publication)
            if "collective" in subtype or "liquidation" in subtype or "redressement" in subtype:
                confidence = 0.95
            elif "creation" in subtype or "radiation" in subtype:
                confidence = 0.90
            else:
                confidence = 0.85

            # -- Build a unique source_ref for deduplication --
            bodacc_id = rd.get("id", "")
            if bodacc_id:
                source_ref = f"bodacc:{bodacc_id}"
            else:
                source_ref = f"bodacc:{siren}:{metric}:{department_code}"

            # Relation: enterprise -> territory (event_*)
            rel_id = _relation_id(ent_ext_id, territory_ext_id, subtype)
            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": ent_ext_id,
                    "target_actor_external_id": territory_ext_id,
                    "relation_type": "structural",
                    "subtype": subtype,
                    "confidence": confidence,
                    "weight": 1.0,
                    "evidence": {
                        "source": "bodacc",
                        "siren": siren,
                        "metric_name": metric,
                        "famille": famille,
                        "nature": rd.get("nature", ""),
                        "date": str(row["event_date"]) if row["event_date"] else None,
                        "bodacc_id": bodacc_id,
                    },
                    "source_type": "bodacc",
                    "source_ref": source_ref,
                }
            )

            # -- Track event history in actor metadata --
            events = ent_meta.setdefault("bodacc_events", [])
            # Keep at most 10 events per actor (most recent)
            if len(events) < 10:
                events.append(
                    {
                        "type": subtype,
                        "date": str(row["event_date"]) if row["event_date"] else None,
                        "nature": rd.get("nature", ""),
                    }
                )

        logger.info(
            "BodaccExtractor dept={}: {} actors, {} relations extracted",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# Nature Juridique extractor (reclassifies SIRENE enterprises)
# ---------------------------------------------------------------------------


class NatureJuridiqueExtractor(BaseExtractor):
    """Reclassify SIRENE actors by nature_juridique code.

    Reads actors already persisted by SireneExtractor and creates
    properly-typed actors (association, formation, financial) based
    on their nature_juridique code. Also creates typed relations
    to the territory.

    Must run AFTER SireneExtractor in the L1 pipeline.
    """

    source_name = "nature_juridique"

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'enterprise'
                  AND metadata->>'nature_juridique' IS NOT NULL
                """,
                department_code,
            )

        if not rows:
            logger.info(
                "NatureJuridiqueExtractor: no enterprises with NJ for dept {}", department_code
            )
            return {"actors": [], "relations": []}

        territory_ext_id = f"DEPT:{department_code}"

        for row in rows:
            meta = row["metadata"] if isinstance(row["metadata"], dict) else {}
            nj_code = meta.get("nature_juridique", "")
            classification = _classify_nature_juridique(nj_code)
            if not classification:
                continue

            actor_type, category_label = classification
            ext_id = row["external_id"]

            actors[ext_id] = {
                "id": str(_actor_id(actor_type, ext_id)),
                "type": actor_type,
                "external_id": ext_id,
                "name": row["name"],
                "department_code": department_code,
                "metadata": {
                    **meta,
                    "nature_juridique_label": category_label,
                    "original_type": "enterprise",
                },
            }

            subtype_map = {
                "association": "operates_in",
                "formation": "trains_in",
                "financial": "finances_in",
                "institution": "administers_in",
            }
            subtype = subtype_map.get(actor_type, "operates_in")

            rel_id = _relation_id(ext_id, territory_ext_id, subtype)
            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": ext_id,
                    "target_actor_external_id": territory_ext_id,
                    "relation_type": "structural",
                    "subtype": subtype,
                    "confidence": 0.95,
                    "weight": 1.0,
                    "evidence": {
                        "source": "nature_juridique",
                        "nature_juridique": nj_code,
                        "category": category_label,
                        "department": department_code,
                    },
                    "source_type": "sirene",
                    "source_ref": f"nj:{ext_id}:{nj_code}",
                }
            )

        logger.info(
            "NatureJuridiqueExtractor dept={}: {} reclassified actors, {} relations",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# BOAMP extractor (public procurement - awarded contracts)
# ---------------------------------------------------------------------------


class BoampExtractor(BaseExtractor):
    """Extract actors and relations from BOAMP award notices.

    Queries the BOAMP OpenDataSoft API for *attribution* notices in a
    given department.  Each notice links a public buyer (institution) to
    a winning enterprise via an ``awarded_contract`` structural relation.

    Unlike SIRENE/BODACC extractors that read the local ``signals`` table,
    this extractor calls the BOAMP adapter directly (external API).
    """

    source_name = "boamp"

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        from src.infrastructure.datasources.adapters.boamp import BoampAdapter

        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        adapter = BoampAdapter()
        try:
            records = await adapter.search(
                {"departement": department_code, "type": "attribution", "limit": 100}
            )
        except Exception:
            logger.exception("BoampExtractor: BOAMP API call failed for dept {}", department_code)
            return {"actors": [], "relations": []}
        finally:
            # Close the underlying httpx client
            if hasattr(adapter, "_client"):
                await adapter._client.aclose()

        if not records:
            logger.info("BoampExtractor: no attribution notices for dept {}", department_code)
            return {"actors": [], "relations": []}

        seen_actors: set[str] = set()

        for rec in records:
            nom_acheteur = (rec.get("nom_acheteur") or "").strip()
            if not nom_acheteur:
                continue

            # titulaire can be a list (multiple winners) or a string
            raw_titulaire = rec.get("titulaire")
            if isinstance(raw_titulaire, list):
                # Deduplicate while preserving order
                titulaires = list(
                    dict.fromkeys(t.strip() for t in raw_titulaire if t and t.strip())
                )
            elif isinstance(raw_titulaire, str) and raw_titulaire.strip():
                titulaires = [raw_titulaire.strip()]
            else:
                continue

            if not titulaires:
                continue

            boamp_id = rec.get("id") or ""
            objet = rec.get("objet") or ""
            cpv_code = rec.get("cpv_code") or ""
            date_pub = rec.get("date_publication") or ""

            # -- Buyer actor (institution / public entity) --
            buyer_ext_id = f"BOAMP_BUYER:{nom_acheteur[:80]}"
            if buyer_ext_id not in seen_actors:
                seen_actors.add(buyer_ext_id)
                actors[buyer_ext_id] = {
                    "id": str(_actor_id("institution", buyer_ext_id)),
                    "type": "institution",
                    "external_id": buyer_ext_id,
                    "name": nom_acheteur,
                    "department_code": department_code,
                    "metadata": {
                        "source": "boamp",
                        "role": "acheteur_public",
                    },
                }

            for titulaire in titulaires:
                # -- Winner actor (enterprise / titulaire) --
                winner_ext_id = f"BOAMP_WINNER:{titulaire[:80]}"
                if winner_ext_id not in seen_actors:
                    seen_actors.add(winner_ext_id)
                    actors[winner_ext_id] = {
                        "id": str(_actor_id("enterprise", winner_ext_id)),
                        "type": "enterprise",
                        "external_id": winner_ext_id,
                        "name": titulaire,
                        "department_code": department_code,
                        "metadata": {},
                    }
                # Enrich winner metadata with latest contract info
                winner_meta = actors[winner_ext_id]["metadata"]
                if cpv_code:
                    winner_meta["cpv_code"] = cpv_code
                if objet:
                    winner_meta["objet"] = objet

                # -- Relation: buyer -> winner (awarded_contract) --
                rel_id = _relation_id(buyer_ext_id, winner_ext_id, "awarded_contract")
                source_ref = (
                    f"boamp:{boamp_id}" if boamp_id else f"boamp:{buyer_ext_id}->{winner_ext_id}"
                )

                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": buyer_ext_id,
                        "target_actor_external_id": winner_ext_id,
                        "relation_type": "structural",
                        "subtype": "awarded_contract",
                        "confidence": 0.95,
                        "weight": 1.0,
                        "evidence": {
                            "source": "boamp",
                            "boamp_id": boamp_id,
                            "objet": objet,
                            "cpv_code": cpv_code,
                            "date_publication": date_pub,
                            "department": department_code,
                        },
                        "source_type": "boamp",
                        "source_ref": source_ref,
                    }
                )

        logger.info(
            "BoampExtractor dept={}: {} actors, {} relations extracted",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# RNA extractor (associations loi 1901 via recherche-entreprises API)
# ---------------------------------------------------------------------------


class RnaExtractor(BaseExtractor):
    """Extract association actors and relations from RNA data.

    Queries the recherche-entreprises API (via RnaAdapter) for associations
    registered in a given department.  Each association creates:

    - An ``association`` actor
    - An ``operates_in`` structural relation toward the territory
    - A ``belongs_to_sector`` relation if the NAF code is present
    """

    source_name = "rna"

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        from src.infrastructure.datasources.adapters.rna import RnaAdapter

        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        adapter = RnaAdapter()
        try:
            records = await adapter.search_by_department(department_code, limit=100)
        except Exception:
            logger.exception("RnaExtractor: RNA API call failed for dept {}", department_code)
            return {"actors": [], "relations": []}
        finally:
            await adapter.close()

        if not records:
            logger.info("RnaExtractor: no associations for dept {}", department_code)
            return {"actors": [], "relations": []}

        # -- Ensure territory actor --
        territory_ext_id = f"DEPT:{department_code}"
        territory_name = _DEPT_NAMES.get(department_code, f"Departement {department_code}")
        actors[territory_ext_id] = {
            "id": str(_actor_id("territory", territory_ext_id)),
            "type": "territory",
            "external_id": territory_ext_id,
            "name": territory_name,
            "department_code": department_code,
            "metadata": {"level": "department"},
        }

        for rec in records:
            siren = rec.get("siren", "")
            if not siren:
                continue

            titre = (
                rec.get("titre", "") or rec.get("nom_raison_sociale", "") or f"Association {siren}"
            )
            naf_code = rec.get("activite_principale", "")
            nj_code = rec.get("nature_juridique", "")
            nj_label = rec.get("nature_juridique_label", "")

            # -- Association actor --
            assoc_ext_id = f"RNA:{siren}"
            if assoc_ext_id not in actors:
                actors[assoc_ext_id] = {
                    "id": str(_actor_id("association", assoc_ext_id)),
                    "type": "association",
                    "external_id": assoc_ext_id,
                    "name": titre,
                    "department_code": department_code,
                    "metadata": {},
                }

            # Enrich metadata
            meta = actors[assoc_ext_id]["metadata"]
            if naf_code:
                meta["activite_principale"] = naf_code
            if nj_code:
                meta["nature_juridique"] = nj_code
            if nj_label:
                meta["nature_juridique_label"] = nj_label
            if rec.get("commune"):
                meta["commune"] = rec["commune"]
            if rec.get("code_postal"):
                meta["code_postal"] = rec["code_postal"]
            if rec.get("date_creation"):
                meta["date_creation"] = rec["date_creation"]
            if rec.get("tranche_effectif"):
                meta["tranche_effectif"] = rec["tranche_effectif"]
            if rec.get("categorie_entreprise"):
                meta["categorie_entreprise"] = rec["categorie_entreprise"]

            # -- Relation: association -> territory (operates_in) --
            rel_id_oi = _relation_id(assoc_ext_id, territory_ext_id, "operates_in")
            relations.append(
                {
                    "id": str(rel_id_oi),
                    "source_actor_external_id": assoc_ext_id,
                    "target_actor_external_id": territory_ext_id,
                    "relation_type": "structural",
                    "subtype": "operates_in",
                    "confidence": 0.90,
                    "weight": 1.0,
                    "evidence": {
                        "source": "rna",
                        "siren": siren,
                        "nature_juridique": nj_code,
                        "nature_juridique_label": nj_label,
                        "department": department_code,
                    },
                    "source_type": "rna",
                    "source_ref": f"rna:{siren}:{department_code}",
                }
            )

            # -- Relation: association -> sector (belongs_to_sector) --
            if naf_code:
                sector_ext_id = f"NAF:{naf_code}"

                # Sector actor (if not already created)
                if sector_ext_id not in actors:
                    actors[sector_ext_id] = {
                        "id": str(_actor_id("sector", sector_ext_id)),
                        "type": "sector",
                        "external_id": sector_ext_id,
                        "name": f"Secteur {naf_code}",
                        "department_code": None,  # sectors are national
                        "metadata": {"naf": naf_code},
                    }

                rel_id_sec = _relation_id(assoc_ext_id, sector_ext_id, "belongs_to_sector")
                relations.append(
                    {
                        "id": str(rel_id_sec),
                        "source_actor_external_id": assoc_ext_id,
                        "target_actor_external_id": sector_ext_id,
                        "relation_type": "structural",
                        "subtype": "belongs_to_sector",
                        "confidence": 0.85,
                        "weight": 1.0,
                        "evidence": {
                            "source": "rna",
                            "siren": siren,
                            "naf": naf_code,
                        },
                        "source_type": "rna",
                        "source_ref": f"rna:{siren}:{naf_code}",
                    }
                )

        logger.info(
            "RnaExtractor dept={}: {} actors, {} relations extracted",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# Subventions extractor (data.gouv.fr public subsidies datasets)
# ---------------------------------------------------------------------------


class SubventionsExtractor(BaseExtractor):
    """Extract funder actors and funded_by relations from data.gouv.fr.

    Queries the SubventionsAdapter for subvention-related datasets in a
    given department.  Each dataset with an ``organization`` field creates:

    - A **funder** actor (type ``institution``, role ``financeur_public``)
    - A ``funded_by`` structural relation from funder toward the territory

    Organizations are deduplicated: if multiple datasets share the same
    organization name, only one funder actor is created.

    Uses a multi-query search strategy: searches by the departmental
    prefecture city name first (best results), then falls back to the
    department name.

    Pipeline placement: Phase 1a (no DB dependency).
    """

    source_name = "subventions"

    # Prefecture cities by department code (largest cities / prefectures)
    _DEPT_PREFECTURES: dict[str, str] = {
        "01": "Bourg-en-Bresse",
        "02": "Laon",
        "03": "Moulins",
        "04": "Digne-les-Bains",
        "05": "Gap",
        "06": "Nice",
        "07": "Privas",
        "08": "Charleville-Mezieres",
        "09": "Foix",
        "10": "Troyes",
        "11": "Carcassonne",
        "12": "Rodez",
        "13": "Marseille",
        "14": "Caen",
        "15": "Aurillac",
        "16": "Angouleme",
        "17": "La Rochelle",
        "18": "Bourges",
        "19": "Tulle",
        "21": "Dijon",
        "22": "Saint-Brieuc",
        "23": "Gueret",
        "24": "Perigueux",
        "25": "Besancon",
        "26": "Valence",
        "27": "Evreux",
        "28": "Chartres",
        "29": "Quimper",
        "2A": "Ajaccio",
        "2B": "Bastia",
        "30": "Nimes",
        "31": "Toulouse",
        "32": "Auch",
        "33": "Bordeaux",
        "34": "Montpellier",
        "35": "Rennes",
        "36": "Chateauroux",
        "37": "Tours",
        "38": "Grenoble",
        "39": "Lons-le-Saunier",
        "40": "Mont-de-Marsan",
        "41": "Blois",
        "42": "Saint-Etienne",
        "43": "Le Puy-en-Velay",
        "44": "Nantes",
        "45": "Orleans",
        "46": "Cahors",
        "47": "Agen",
        "48": "Mende",
        "49": "Angers",
        "50": "Saint-Lo",
        "51": "Chalons-en-Champagne",
        "52": "Chaumont",
        "53": "Laval",
        "54": "Nancy",
        "55": "Bar-le-Duc",
        "56": "Vannes",
        "57": "Metz",
        "58": "Nevers",
        "59": "Lille",
        "60": "Beauvais",
        "61": "Alencon",
        "62": "Arras",
        "63": "Clermont-Ferrand",
        "64": "Pau",
        "65": "Tarbes",
        "66": "Perpignan",
        "67": "Strasbourg",
        "68": "Colmar",
        "69": "Lyon",
        "70": "Vesoul",
        "71": "Macon",
        "72": "Le Mans",
        "73": "Chambery",
        "74": "Annecy",
        "75": "Paris",
        "76": "Rouen",
        "77": "Melun",
        "78": "Versailles",
        "79": "Niort",
        "80": "Amiens",
        "81": "Albi",
        "82": "Montauban",
        "83": "Toulon",
        "84": "Avignon",
        "85": "La Roche-sur-Yon",
        "86": "Poitiers",
        "87": "Limoges",
        "88": "Epinal",
        "89": "Auxerre",
        "90": "Belfort",
        "91": "Evry",
        "92": "Nanterre",
        "93": "Bobigny",
        "94": "Creteil",
        "95": "Cergy",
        "971": "Basse-Terre",
        "972": "Fort-de-France",
        "973": "Cayenne",
        "974": "Saint-Denis",
        "976": "Mamoudzou",
    }

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        from src.infrastructure.datasources.adapters.subventions import SubventionsAdapter

        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        adapter = SubventionsAdapter()
        try:
            datasets = await self._multi_search(adapter, department_code)
        except Exception:
            logger.exception(
                "SubventionsExtractor: data.gouv API call failed for dept {}", department_code
            )
            return {"actors": [], "relations": []}
        finally:
            if hasattr(adapter, "_client"):
                await adapter._client.aclose()

        if not datasets:
            logger.info("SubventionsExtractor: no datasets for dept {}", department_code)
            return {"actors": [], "relations": []}

        # -- Ensure territory actor --
        territory_ext_id = f"DEPT:{department_code}"
        territory_name = _DEPT_NAMES.get(department_code, f"Departement {department_code}")
        actors[territory_ext_id] = {
            "id": str(_actor_id("territory", territory_ext_id)),
            "type": "territory",
            "external_id": territory_ext_id,
            "name": territory_name,
            "department_code": department_code,
            "metadata": {"level": "department"},
        }

        # Track seen organizations for deduplication
        seen_orgs: set[str] = set()

        for ds in datasets:
            org_name = (ds.get("organization") or "").strip()
            if not org_name:
                continue

            dataset_title = ds.get("title") or ""
            dataset_id = ds.get("id") or ""
            org_id = ds.get("organization_id") or ""

            # Deduplicate: same org creates only 1 actor
            org_key = org_name.lower()
            if org_key in seen_orgs:
                continue
            seen_orgs.add(org_key)

            # -- Funder actor (institution / financeur public) --
            funder_ext_id = f"FUNDER:{org_name[:80]}"
            actors[funder_ext_id] = {
                "id": str(_actor_id("institution", funder_ext_id)),
                "type": "institution",
                "external_id": funder_ext_id,
                "name": org_name,
                "department_code": department_code,
                "metadata": {
                    "source": "subventions",
                    "role": "financeur_public",
                    "dataset_title": dataset_title[:200],
                    "organization_id": org_id,
                },
            }

            # -- Relation: funder -> territory (funded_by) --
            rel_id = _relation_id(funder_ext_id, territory_ext_id, "funded_by")
            source_ref = (
                f"subventions:{dataset_id}"
                if dataset_id
                else f"subventions:{funder_ext_id}->{territory_ext_id}"
            )

            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": funder_ext_id,
                    "target_actor_external_id": territory_ext_id,
                    "relation_type": "structural",
                    "subtype": "funded_by",
                    "confidence": 0.85,
                    "weight": 1.0,
                    "evidence": {
                        "source": "subventions",
                        "dataset_id": dataset_id,
                        "dataset_title": dataset_title,
                        "organization": org_name,
                        "organization_id": org_id,
                        "department": department_code,
                    },
                    "source_type": "subventions",
                    "source_ref": source_ref,
                }
            )

        logger.info(
            "SubventionsExtractor dept={}: {} actors, {} relations extracted",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}

    async def _multi_search(
        self,
        adapter: Any,
        department_code: str,
    ) -> list[dict[str, Any]]:
        """Search data.gouv.fr with multiple queries to maximize coverage.

        Strategy:
        1. Search by prefecture city name (best precision for local datasets)
        2. Search by department name (without accents/hyphens for better matching)
        3. Merge and deduplicate by dataset id
        """
        seen_ids: set[str] = set()
        all_datasets: list[dict[str, Any]] = []

        # Build search terms
        search_terms: list[str] = []

        # 1. Prefecture city (most effective for local subvention data)
        prefecture = self._DEPT_PREFECTURES.get(department_code)
        if prefecture:
            search_terms.append(prefecture)

        # 2. Department name simplified (remove hyphens/apostrophes)
        dept_name = _DEPT_NAMES.get(department_code, "")
        if dept_name:
            simplified = dept_name.replace("-", " ").replace("'", " ")
            search_terms.append(simplified)

        for term in search_terms:
            try:
                results = await adapter.search(
                    {
                        "keywords": term,
                        "limit": 30,
                    }
                )
                for ds in results:
                    ds_id = ds.get("id", "")
                    if ds_id and ds_id not in seen_ids:
                        seen_ids.add(ds_id)
                        all_datasets.append(ds)
                    elif not ds_id:
                        all_datasets.append(ds)
            except Exception:
                logger.warning(
                    "SubventionsExtractor: search '{}' failed for dept {}",
                    term,
                    department_code,
                )

        return all_datasets


# ---------------------------------------------------------------------------
# EPCI extractor (intercommunalites via geo.api.gouv.fr)
# ---------------------------------------------------------------------------
# DB migration (run before first use):
#   ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'epci';


class EPCIExtractor(BaseExtractor):
    """Extract EPCI (collectivites intercommunales) from geo.api.gouv.fr.

    Creates:
    - Actors of type ``collectivity`` for each EPCI in the department
    - ``administers_territory`` structural relations (EPCI -> territory)
    - ``belongs_to_epci`` structural relations (enterprise -> EPCI)
      via postal-code matching against each EPCI's communes

    API documentation: https://geo.api.gouv.fr/decoupage-administratif/epcis

    Pipeline placement: Phase 1a (external API, no local signal dependency),
    but the commune->enterprise matching in step 3 requires actors already
    persisted by SireneExtractor.  Running after SireneExtractor is recommended.
    """

    source_name = "epci"

    # Polite delay between API calls (seconds)
    _API_DELAY_S: float = 0.1
    # Max EPCIs for which we fetch commune lists (avoid hammering the API)
    _MAX_COMMUNE_LOOKUPS: int = 50

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        import asyncio

        import httpx

        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        # -----------------------------------------------------------------
        # 1. Fetch all EPCIs and filter by department
        #    The geo API has no server-side department filter for EPCIs,
        #    so we fetch the full list (~1200 records, ~120 KB) and filter
        #    client-side via the codesDepartements array.
        # -----------------------------------------------------------------
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    "https://geo.api.gouv.fr/epcis",
                    params={"fields": "nom,population,codesDepartements"},
                )
            except httpx.HTTPError:
                logger.warning(
                    "EPCIExtractor: HTTP error fetching EPCIs for dept {}",
                    department_code,
                )
                return {"actors": [], "relations": []}

        if resp.status_code != 200:
            logger.warning(
                "EPCIExtractor: geo API returned {} for dept {}",
                resp.status_code,
                department_code,
            )
            return {"actors": [], "relations": []}

        all_epcis: list[dict[str, Any]] = resp.json()
        # Filter to EPCIs that cover this department
        epcis = [e for e in all_epcis if department_code in (e.get("codesDepartements") or [])]
        if not epcis:
            logger.info("EPCIExtractor: no EPCIs for dept {}", department_code)
            return {"actors": [], "relations": []}

        logger.info("EPCIExtractor: found {} EPCIs for dept {}", len(epcis), department_code)

        # -- Ensure territory actor --
        territory_ext_id = f"DEPT:{department_code}"
        territory_name = _DEPT_NAMES.get(department_code, f"Departement {department_code}")
        actors[territory_ext_id] = {
            "id": str(_actor_id("territory", territory_ext_id)),
            "type": "territory",
            "external_id": territory_ext_id,
            "name": territory_name,
            "department_code": department_code,
            "metadata": {"level": "department"},
        }

        # -----------------------------------------------------------------
        # 2. Create collectivity actors + administers_territory relations
        # -----------------------------------------------------------------
        for epci in epcis:
            code = epci.get("code", "")
            if not code:
                continue
            name = epci.get("nom", f"EPCI {code}")
            population = epci.get("population") or 0

            ext_id = f"EPCI:{code}"
            actors[ext_id] = {
                "id": str(_actor_id("collectivity", ext_id)),
                "type": "collectivity",
                "external_id": ext_id,
                "name": name,
                "department_code": department_code,
                "metadata": {
                    "epci_code": code,
                    "population": population,
                    "departments": epci.get("codesDepartements", []),
                    "source": "geo.api.gouv.fr",
                },
            }

            # Relation: collectivity -> territory (administers_territory)
            # Weight proportional to population, capped at 10.0
            weight = min(max(1.0, population / 50_000), 10.0)
            relations.append(
                {
                    "id": str(_relation_id(ext_id, territory_ext_id, "administers_territory")),
                    "source_actor_external_id": ext_id,
                    "target_actor_external_id": territory_ext_id,
                    "relation_type": "structural",
                    "subtype": "administers_territory",
                    "confidence": 0.95,
                    "weight": weight,
                    "evidence": {
                        "source": "geo.api.gouv.fr",
                        "epci_code": code,
                        "population": population,
                        "department": department_code,
                    },
                    "source_type": "epci",
                    "source_ref": f"epci:{code}:{department_code}",
                }
            )

        # -----------------------------------------------------------------
        # 3. Match enterprises to EPCI via postal code <-> communes
        # -----------------------------------------------------------------
        async with acquire_conn() as conn:
            enterprise_rows = await conn.fetch(
                """SELECT external_id, name, metadata
                   FROM actors
                   WHERE department_code = $1 AND type = 'enterprise'""",
                department_code,
            )

        if not enterprise_rows:
            logger.info(
                "EPCIExtractor dept {}: no enterprises to match, skipping commune lookup",
                department_code,
            )
            return {
                "actors": list(actors.values()),
                "relations": relations,
            }

        # Build postal-code -> EPCI external_id mapping AND enrich EPCI
        # actor metadata with commune codes and postal codes (needed by
        # EPCIBelongsInferrer downstream).
        commune_to_epci: dict[str, str] = {}
        async with httpx.AsyncClient(timeout=30.0) as client:
            for epci in epcis[: self._MAX_COMMUNE_LOOKUPS]:
                code = epci.get("code", "")
                if not code:
                    continue
                try:
                    await asyncio.sleep(self._API_DELAY_S)
                    resp = await client.get(
                        f"https://geo.api.gouv.fr/epcis/{code}/communes",
                        params={"fields": "nom,code,codesPostaux"},
                    )
                    if resp.status_code == 200:
                        communes_data = resp.json()
                        epci_ext = f"EPCI:{code}"

                        # Collect commune codes and postal codes for
                        # EPCI metadata enrichment
                        epci_commune_codes: list[str] = []
                        epci_postal_codes: set[str] = set()

                        for commune in communes_data:
                            # Commune code (INSEE code, e.g. "13055")
                            commune_code = commune.get("code", "")
                            if commune_code:
                                epci_commune_codes.append(commune_code)

                            for cp in commune.get("codesPostaux", []):
                                epci_postal_codes.add(cp)
                                # First EPCI wins for a given postal code
                                # (a postal code rarely spans multiple EPCIs)
                                if cp not in commune_to_epci:
                                    commune_to_epci[cp] = epci_ext

                        # Enrich EPCI actor metadata with communes
                        # and postal codes for EPCIBelongsInferrer
                        if epci_ext in actors:
                            actors[epci_ext]["metadata"]["communes"] = epci_commune_codes
                            actors[epci_ext]["metadata"]["codes_postaux"] = sorted(
                                epci_postal_codes
                            )

                except httpx.HTTPError:
                    logger.debug(
                        "EPCIExtractor: failed to fetch communes for EPCI {}",
                        code,
                    )
                    continue

        if not commune_to_epci:
            logger.info(
                "EPCIExtractor dept {}: no commune postal codes resolved",
                department_code,
            )
            return {
                "actors": list(actors.values()),
                "relations": relations,
            }

        logger.info(
            "EPCIExtractor dept {}: {} postal codes mapped to EPCIs",
            department_code,
            len(commune_to_epci),
        )

        # Match enterprises to EPCI by postal code
        matched = 0
        for row in enterprise_rows:
            meta = _parse_raw_data(row["metadata"])

            # Try direct code_postal field first
            cp = meta.get("code_postal", "")

            # Fallback: look inside siege sub-object (SIRENE format)
            if not cp:
                siege = meta.get("siege", {})
                if isinstance(siege, str):
                    try:
                        siege = json.loads(siege)
                    except (json.JSONDecodeError, TypeError):
                        siege = {}
                if isinstance(siege, dict):
                    cp = siege.get("code_postal", "")

            if not cp or cp not in commune_to_epci:
                continue

            epci_ext = commune_to_epci[cp]
            ent_ext = row["external_id"]

            # Only create relation if the EPCI actor exists
            if epci_ext not in actors:
                continue

            relations.append(
                {
                    "id": str(_relation_id(ent_ext, epci_ext, "belongs_to_epci")),
                    "source_actor_external_id": ent_ext,
                    "target_actor_external_id": epci_ext,
                    "relation_type": "structural",
                    "subtype": "belongs_to_epci",
                    "confidence": 0.90,
                    "weight": 1.0,
                    "evidence": {
                        "source": "geo.api.gouv.fr",
                        "via": "postal_code_match",
                        "code_postal": cp,
                    },
                    "source_type": "epci",
                    "source_ref": f"epci:{epci_ext}:{ent_ext}",
                }
            )
            matched += 1

        logger.info(
            "EPCIExtractor dept {}: {} EPCI actors, {} relations "
            "({} administers_territory + {} belongs_to_epci)",
            department_code,
            len([a for a in actors.values() if a["type"] == "collectivity"]),
            len(relations),
            len(relations) - matched,
            matched,
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# Department -> Region mapping (for MESR API fallback filtering)
# ---------------------------------------------------------------------------

_DEPT_TO_REGION: dict[str, str] = {
    "13": "Provence-Alpes-Cote d'Azur",
    "06": "Provence-Alpes-Cote d'Azur",
    "83": "Provence-Alpes-Cote d'Azur",
    "84": "Provence-Alpes-Cote d'Azur",
    "04": "Provence-Alpes-Cote d'Azur",
    "05": "Provence-Alpes-Cote d'Azur",
    "75": "Ile-de-France",
    "92": "Ile-de-France",
    "93": "Ile-de-France",
    "94": "Ile-de-France",
    "77": "Ile-de-France",
    "78": "Ile-de-France",
    "91": "Ile-de-France",
    "95": "Ile-de-France",
    "59": "Hauts-de-France",
    "62": "Hauts-de-France",
    "60": "Hauts-de-France",
    "80": "Hauts-de-France",
    "02": "Hauts-de-France",
    "69": "Auvergne-Rhone-Alpes",
    "01": "Auvergne-Rhone-Alpes",
    "38": "Auvergne-Rhone-Alpes",
    "42": "Auvergne-Rhone-Alpes",
    "43": "Auvergne-Rhone-Alpes",
    "63": "Auvergne-Rhone-Alpes",
    "73": "Auvergne-Rhone-Alpes",
    "74": "Auvergne-Rhone-Alpes",
    "03": "Auvergne-Rhone-Alpes",
    "07": "Auvergne-Rhone-Alpes",
    "15": "Auvergne-Rhone-Alpes",
    "26": "Auvergne-Rhone-Alpes",
    "33": "Nouvelle-Aquitaine",
    "24": "Nouvelle-Aquitaine",
    "40": "Nouvelle-Aquitaine",
    "47": "Nouvelle-Aquitaine",
    "64": "Nouvelle-Aquitaine",
    "16": "Nouvelle-Aquitaine",
    "17": "Nouvelle-Aquitaine",
    "79": "Nouvelle-Aquitaine",
    "86": "Nouvelle-Aquitaine",
    "87": "Nouvelle-Aquitaine",
    "19": "Nouvelle-Aquitaine",
    "23": "Nouvelle-Aquitaine",
    "31": "Occitanie",
    "34": "Occitanie",
    "30": "Occitanie",
    "11": "Occitanie",
    "66": "Occitanie",
    "09": "Occitanie",
    "12": "Occitanie",
    "32": "Occitanie",
    "46": "Occitanie",
    "48": "Occitanie",
    "65": "Occitanie",
    "81": "Occitanie",
    "82": "Occitanie",
    "44": "Pays de la Loire",
    "49": "Pays de la Loire",
    "53": "Pays de la Loire",
    "72": "Pays de la Loire",
    "85": "Pays de la Loire",
    "35": "Bretagne",
    "22": "Bretagne",
    "29": "Bretagne",
    "56": "Bretagne",
    "67": "Grand Est",
    "68": "Grand Est",
    "57": "Grand Est",
    "54": "Grand Est",
    "55": "Grand Est",
    "88": "Grand Est",
    "10": "Grand Est",
    "51": "Grand Est",
    "52": "Grand Est",
    "08": "Grand Est",
    "76": "Normandie",
    "27": "Normandie",
    "14": "Normandie",
    "50": "Normandie",
    "61": "Normandie",
    "21": "Bourgogne-Franche-Comte",
    "58": "Bourgogne-Franche-Comte",
    "71": "Bourgogne-Franche-Comte",
    "89": "Bourgogne-Franche-Comte",
    "25": "Bourgogne-Franche-Comte",
    "39": "Bourgogne-Franche-Comte",
    "70": "Bourgogne-Franche-Comte",
    "90": "Bourgogne-Franche-Comte",
    "45": "Centre-Val de Loire",
    "18": "Centre-Val de Loire",
    "28": "Centre-Val de Loire",
    "36": "Centre-Val de Loire",
    "37": "Centre-Val de Loire",
    "41": "Centre-Val de Loire",
    "2A": "Corse",
    "2B": "Corse",
}


# ---------------------------------------------------------------------------
# Incubator extractor (MESR open data -- structures de transfert / valorisation)
# ---------------------------------------------------------------------------


class IncubatorExtractor(BaseExtractor):
    """Extract incubators, accelerators, and technology transfer structures
    from MESR (Ministere de l'Enseignement Superieur et de la Recherche) open data.

    Data source: ``fr-esr-structures-de-transfert-et-de-valorisation`` dataset
    on data.enseignementsup-recherche.gouv.fr (263 structures, open access).

    Creates:
    - Actors of type ``incubator`` for each structure in the department
    - ``operates_in`` structural relations (incubator -> territory)

    The extractor uses the MESR ``code_departement`` refine parameter as the
    primary filtering strategy (exact, single-request).  If that yields no
    results, it falls back to filtering by ``region`` (from ``_DEPT_TO_REGION``)
    and then filtering records locally by ``code_departement`` prefix.

    Pipeline placement: Phase 1a (external API, no local signal dependency).
    """

    source_name = "incubator"

    _MESR_BASE_URL = (
        "https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1"
        "/catalog/datasets/fr-esr-structures-de-transfert-et-de-valorisation/records"
    )

    @staticmethod
    def _dept_code_mesr(department_code: str) -> str:
        """Convert our department code to MESR ``code_departement`` format.

        Examples: ``"13"`` -> ``"D013"``, ``"2A"`` -> ``"D02A"``, ``"974"`` -> ``"D974"``
        """
        return f"D{department_code.zfill(3)}"

    async def _fetch_by_department(
        self,
        client: Any,
        department_code: str,
    ) -> list[dict[str, Any]]:
        """Primary strategy: refine by ``code_departement`` (exact, one request)."""
        mesr_code = self._dept_code_mesr(department_code)
        all_records: list[dict[str, Any]] = []
        offset = 0

        while True:
            resp = await client.get(
                self._MESR_BASE_URL,
                params={
                    "limit": 100,
                    "offset": offset,
                    "refine": f"code_departement:{mesr_code}",
                },
            )
            if resp.status_code != 200:
                logger.warning(
                    "IncubatorExtractor: MESR API returned {} (code_departement={})",
                    resp.status_code,
                    mesr_code,
                )
                break
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            all_records.extend(results)
            offset += 100
            if offset >= data.get("total_count", 0):
                break

        return all_records

    async def _fetch_by_region_fallback(
        self,
        client: Any,
        department_code: str,
    ) -> list[dict[str, Any]]:
        """Fallback: refine by region, then filter locally by ``code_departement``."""
        region = _DEPT_TO_REGION.get(department_code)
        if not region:
            return []

        mesr_dept = self._dept_code_mesr(department_code)
        all_records: list[dict[str, Any]] = []
        offset = 0

        while True:
            resp = await client.get(
                self._MESR_BASE_URL,
                params={
                    "limit": 100,
                    "offset": offset,
                    "refine": f"region:{region}",
                },
            )
            if resp.status_code != 200:
                logger.warning(
                    "IncubatorExtractor: MESR API returned {} (region={})",
                    resp.status_code,
                    region,
                )
                break
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            all_records.extend(results)
            offset += 100
            if offset >= data.get("total_count", 0):
                break

        # Filter to this department specifically
        return [rec for rec in all_records if rec.get("code_departement", "") == mesr_dept]

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        import httpx

        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Strategy 1: direct department code query
            records = await self._fetch_by_department(client, department_code)

            # Strategy 2: fallback to region + local filter
            if not records:
                records = await self._fetch_by_region_fallback(client, department_code)

        if not records:
            logger.info("IncubatorExtractor: no structures for dept {}", department_code)
            return {"actors": [], "relations": []}

        logger.info(
            "IncubatorExtractor: {} structures found for dept {}",
            len(records),
            department_code,
        )

        territory_ext_id = f"DEPT:{department_code}"

        # Short type labels for graph display
        _TYPE_SHORT: dict[str, str] = {
            "INCUB": "Incubateur",
            "CRT": "CRT",
            "CDT": "CDT",
            "SATT": "SATT",
            "PFT": "Plateforme Techno",
            "CARNOT": "Institut Carnot",
            "PEPITE": "PEPITE",
            "IRT": "IRT",
        }

        for rec in records:
            struct_id = rec.get("identifiant") or rec.get("siret") or ""
            if not struct_id:
                continue

            raw_name = (
                rec.get("libelle_court") or rec.get("libelle_long") or f"Structure {struct_id}"
            )
            struct_type = rec.get("type_de_structure", "INCUB")
            struct_type_label = rec.get("libelle_type_de_structure", struct_type)

            # Prefix name with short type label for visual distinction in graph
            short_label = _TYPE_SHORT.get(struct_type, struct_type)
            if short_label.upper() not in raw_name.upper():
                name = f"{raw_name} ({short_label})"
            else:
                name = raw_name

            ext_id = f"INCUB:{struct_id}"

            # Geolocation
            geoloc = rec.get("geolocalisation")
            lat = geoloc.get("lat") if isinstance(geoloc, dict) else None
            lon = geoloc.get("lon") if isinstance(geoloc, dict) else None

            actors[ext_id] = {
                "id": str(_actor_id("incubator", ext_id)),
                "type": "incubator",
                "external_id": ext_id,
                "name": name,
                "department_code": department_code,
                "metadata": {
                    "siret": rec.get("siret") or "",
                    "structure_type": struct_type,
                    "structure_type_label": struct_type_label,
                    "address": rec.get("adresse") or "",
                    "city": rec.get("localite") or rec.get("commune") or "",
                    "code_postal": rec.get("code_postal") or "",
                    "website": rec.get("site_internet") or "",
                    "lat": lat,
                    "lon": lon,
                    "source": "mesr.data.gouv.fr",
                },
            }

            # Relation: incubator -> territory (operates_in)
            relations.append(
                {
                    "id": str(_relation_id(ext_id, territory_ext_id, "operates_in")),
                    "source_actor_external_id": ext_id,
                    "target_actor_external_id": territory_ext_id,
                    "relation_type": "structural",
                    "subtype": "operates_in",
                    "confidence": 0.90,
                    "weight": 1.5,
                    "evidence": {
                        "source": "mesr.data.gouv.fr",
                        "structure_type": struct_type,
                        "structure_type_label": struct_type_label,
                        "department": department_code,
                    },
                    "source_type": "incubator",
                    "source_ref": f"mesr:{struct_id}:{department_code}",
                }
            )

        logger.info(
            "IncubatorExtractor dept {}: {} incubator actors, {} relations",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# Poles de competitivite Phase V -- hardcoded data (data.gouv.fr CSV is
# obsolete, last updated 2014).  Source: competitivite.gouv.fr + Wikipedia.
# ---------------------------------------------------------------------------

_POLES_COMPETITIVITE: list[dict[str, Any]] = [
    # Sante / Biotech
    {
        "name": "Eurobiomed",
        "departments": ["13", "34", "06"],
        "sectors": ["C", "M", "Q"],
        "theme": "sante_biotech",
    },
    {
        "name": "Lyonbiopole",
        "departments": ["69", "38"],
        "sectors": ["C", "M", "Q"],
        "theme": "sante_biotech",
    },
    {
        "name": "Medicen Paris Region",
        "departments": ["75", "92", "94"],
        "sectors": ["C", "M", "Q"],
        "theme": "sante_biotech",
    },
    {
        "name": "Atlanpole Biotherapies",
        "departments": ["44", "49"],
        "sectors": ["C", "M", "Q"],
        "theme": "sante_biotech",
    },
    # Numerique / IT
    {
        "name": "Systematic Paris-Region",
        "departments": ["75", "92", "91"],
        "sectors": ["J", "C", "M"],
        "theme": "numerique",
    },
    {
        "name": "Cap Digital",
        "departments": ["75", "92", "93"],
        "sectors": ["J", "R", "M"],
        "theme": "numerique",
    },
    {
        "name": "Images & Reseaux",
        "departments": ["35", "22", "29", "56"],
        "sectors": ["J", "C"],
        "theme": "numerique",
    },
    {
        "name": "Minalogic",
        "departments": ["38", "73", "74"],
        "sectors": ["C", "J", "M"],
        "theme": "numerique",
    },
    {
        "name": "SCS (Solutions Communicantes Securisees)",
        "departments": ["13", "06", "83"],
        "sectors": ["J", "C", "M"],
        "theme": "numerique",
    },
    # Aeronautique / Spatial / Defense
    {
        "name": "Aerospace Valley",
        "departments": ["31", "33", "64", "65"],
        "sectors": ["C", "M", "H"],
        "theme": "aeronautique",
    },
    {
        "name": "ASTech Paris Region",
        "departments": ["75", "78", "91", "92"],
        "sectors": ["C", "M", "H"],
        "theme": "aeronautique",
    },
    {
        "name": "SAFE Cluster",
        "departments": ["13", "06", "83", "84"],
        "sectors": ["C", "M", "N"],
        "theme": "securite_defense",
    },
    {
        "name": "Pegase",
        "departments": ["13", "83"],
        "sectors": ["C", "M", "H"],
        "theme": "aeronautique",
    },
    # Maritime
    {
        "name": "Pole Mer Mediterranee",
        "departments": ["13", "83", "06"],
        "sectors": ["C", "H", "A"],
        "theme": "maritime",
    },
    {
        "name": "Pole Mer Bretagne Atlantique",
        "departments": ["29", "56", "35", "44"],
        "sectors": ["C", "H", "A"],
        "theme": "maritime",
    },
    # Energie / Environnement
    {
        "name": "Tenerrdis",
        "departments": ["38", "73"],
        "sectors": ["D", "C", "M"],
        "theme": "energie",
    },
    {
        "name": "Derbi",
        "departments": ["34", "66", "11"],
        "sectors": ["D", "C", "M"],
        "theme": "energie",
    },
    {
        "name": "Capenergies",
        "departments": ["13", "83", "84", "06", "2A", "2B"],
        "sectors": ["D", "C", "M"],
        "theme": "energie",
    },
    {
        "name": "S2E2 (Sciences et Systemes de l'Energie Electrique)",
        "departments": ["37", "45", "28"],
        "sectors": ["D", "C", "M"],
        "theme": "energie",
    },
    {
        "name": "Axelera",
        "departments": ["69", "42", "01"],
        "sectors": ["C", "E", "M"],
        "theme": "chimie_environnement",
    },
    {
        "name": "IAR (Industries et Agro-Ressources)",
        "departments": ["51", "02", "60", "80"],
        "sectors": ["C", "A", "M"],
        "theme": "bioeconomie",
    },
    # Transport / Mobilite
    {
        "name": "i-Trans",
        "departments": ["59", "62", "80"],
        "sectors": ["C", "H", "M"],
        "theme": "transport",
    },
    {
        "name": "ID4CAR",
        "departments": ["44", "35", "49"],
        "sectors": ["C", "H", "M"],
        "theme": "automobile",
    },
    {
        "name": "Mov'eo",
        "departments": ["76", "78", "91", "92"],
        "sectors": ["C", "H", "M"],
        "theme": "automobile",
    },
    {
        "name": "Vehicule du Futur",
        "departments": ["67", "68", "90", "25"],
        "sectors": ["C", "H", "M"],
        "theme": "automobile",
    },
    # Materiaux / Mecanique
    {
        "name": "EMC2",
        "departments": ["44", "49", "53"],
        "sectors": ["C", "M"],
        "theme": "materiaux",
    },
    {
        "name": "Materalia",
        "departments": ["57", "54", "55"],
        "sectors": ["C", "M"],
        "theme": "materiaux",
    },
    {
        "name": "Plastipolis",
        "departments": ["01", "39", "69"],
        "sectors": ["C", "M"],
        "theme": "plastique",
    },
    {
        "name": "Pole Europeen de la Ceramique",
        "departments": ["87"],
        "sectors": ["C", "M"],
        "theme": "materiaux",
    },
    {
        "name": "Elastopole",
        "departments": ["45", "37", "28"],
        "sectors": ["C", "M"],
        "theme": "caoutchouc",
    },
    {
        "name": "Techtera",
        "departments": ["69", "42", "01"],
        "sectors": ["C", "M"],
        "theme": "textile",
    },
    # Agroalimentaire
    {
        "name": "Valorial",
        "departments": ["35", "22", "29", "56", "44"],
        "sectors": ["C", "A"],
        "theme": "agroalimentaire",
    },
    {
        "name": "Vitagora",
        "departments": ["21", "58", "71", "89"],
        "sectors": ["C", "A", "I"],
        "theme": "agroalimentaire",
    },
    {
        "name": "Agri Sud-Ouest Innovation",
        "departments": ["31", "32", "47"],
        "sectors": ["A", "C", "M"],
        "theme": "agroalimentaire",
    },
    {
        "name": "Qualimed",
        "departments": ["34", "30", "84"],
        "sectors": ["A", "C", "I"],
        "theme": "agroalimentaire",
    },
    # Cosmetique / Luxe
    {
        "name": "Cosmetic Valley",
        "departments": ["28", "45", "37", "41"],
        "sectors": ["C", "G", "M"],
        "theme": "cosmetique",
    },
    # Optique / Photonique
    {
        "name": "Route des Lasers / Alpha-RLH",
        "departments": ["33", "87"],
        "sectors": ["C", "M"],
        "theme": "photonique",
    },
    {
        "name": "Elopsys",
        "departments": ["87", "19", "23"],
        "sectors": ["C", "J", "M"],
        "theme": "electronique",
    },
    # Nucleaire
    {
        "name": "Nuclear Valley",
        "departments": ["42", "69", "63"],
        "sectors": ["C", "D", "M"],
        "theme": "nucleaire",
    },
    # Finance
    {
        "name": "Finance Innovation",
        "departments": ["75", "92"],
        "sectors": ["K", "J", "M"],
        "theme": "finance",
    },
    # Eau
    {
        "name": "Aqua-Valley (ex Pole Eau)",
        "departments": ["34", "30"],
        "sectors": ["E", "M", "C"],
        "theme": "eau",
    },
    # Construction / BTP
    {
        "name": "Fibres-Energivie",
        "departments": ["67", "68"],
        "sectors": ["F", "C", "M"],
        "theme": "construction",
    },
    # Logistique
    {
        "name": "Nov@log (Novalog)",
        "departments": ["76", "27", "14"],
        "sectors": ["H", "J", "M"],
        "theme": "logistique",
    },
    # Industrie du futur
    {
        "name": "ViaMeca",
        "departments": ["63", "42", "43"],
        "sectors": ["C", "M", "J"],
        "theme": "mecanique",
    },
    {
        "name": "Cimes (ex Arve Industries)",
        "departments": ["74"],
        "sectors": ["C", "M"],
        "theme": "decolletage",
    },
    # Parfum
    {
        "name": "PASS (Parfums, Aromes, Senteurs, Saveurs)",
        "departments": ["06", "83"],
        "sectors": ["C", "A", "M"],
        "theme": "parfum",
    },
    # Risques
    {
        "name": "Risques",
        "departments": ["30", "34", "13"],
        "sectors": ["M", "J", "O"],
        "theme": "gestion_risques",
    },
    # Design
    {"name": "Design", "departments": ["42"], "sectors": ["M", "C", "J"], "theme": "design"},
    # Fruits & Legumes
    {
        "name": "Terralia",
        "departments": ["84", "13", "04"],
        "sectors": ["A", "C"],
        "theme": "fruits_legumes",
    },
    # Bois
    {
        "name": "Xylofutur",
        "departments": ["33", "40", "64"],
        "sectors": ["A", "C", "M"],
        "theme": "bois",
    },
    # Cereales
    {
        "name": "Cereales Vallee",
        "departments": ["63", "03"],
        "sectors": ["A", "C"],
        "theme": "cereales",
    },
    # Microelectronique
    {
        "name": "Microelectronique (ex Minalogic spin)",
        "departments": ["38"],
        "sectors": ["C", "J"],
        "theme": "microelectronique",
    },
    # Bioeconomie
    {
        "name": "Bioeconomy for Change (BFC)",
        "departments": ["51", "02", "60"],
        "sectors": ["A", "C", "M"],
        "theme": "bioeconomie",
    },
]


# ---------------------------------------------------------------------------
# Poles de competitivite extractor (L1 -- hardcoded Phase V data)
# ---------------------------------------------------------------------------


class PolesExtractor(BaseExtractor):
    """Extract competitiveness poles (poles de competitivite Phase V).

    Uses hardcoded data (55 poles) since the data.gouv.fr CSV is obsolete.
    Creates:
    - Actors of type 'competitiveness_pole' for each pole present in the department
    - Relations 'pole_in_territory' (pole -> territory)
    - Relations 'pole_covers_sector' (pole -> sector) for each NAF section
    """

    source_name = "poles"

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        territory_ext = f"DEPT:{department_code}"

        # Filter poles that include this department
        dept_poles = [p for p in _POLES_COMPETITIVITE if department_code in p["departments"]]

        if not dept_poles:
            logger.info("PolesExtractor: no poles for dept {}", department_code)
            return {"actors": [], "relations": []}

        for pole in dept_poles:
            pole_name = pole["name"]
            ext_id = f"POLE:{pole_name.upper().replace(' ', '_')}"

            actors[ext_id] = {
                "id": str(_actor_id("competitiveness_pole", ext_id)),
                "type": "competitiveness_pole",
                "external_id": ext_id,
                "name": pole_name,
                "department_code": department_code,
                "metadata": {
                    "theme": pole["theme"],
                    "departments": pole["departments"],
                    "sectors": pole["sectors"],
                    "source": "competitivite.gouv.fr",
                },
            }

            # Relation: pole -> territory
            relations.append(
                {
                    "id": str(_relation_id(ext_id, territory_ext, "pole_in_territory")),
                    "source_actor_external_id": ext_id,
                    "target_actor_external_id": territory_ext,
                    "relation_type": "structural",
                    "subtype": "pole_in_territory",
                    "confidence": 0.95,
                    "weight": 2.0,
                    "metadata": {"source": "competitivite.gouv.fr"},
                }
            )

            # Relations: pole -> sector (for each NAF section)
            for sector_code in pole["sectors"]:
                sector_ext = f"NAF:{sector_code}"
                relations.append(
                    {
                        "id": str(_relation_id(ext_id, sector_ext, "pole_covers_sector")),
                        "source_actor_external_id": ext_id,
                        "target_actor_external_id": sector_ext,
                        "relation_type": "structural",
                        "subtype": "pole_covers_sector",
                        "confidence": 0.90,
                        "weight": 1.5,
                        "metadata": {"theme": pole["theme"]},
                    }
                )

        logger.info(
            "PolesExtractor dept {}: {} poles, {} relations",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# Territorial structures extractor (communes, CCI, CMA, CD, CR)
# ---------------------------------------------------------------------------


# Department -> Region code mapping (for geo.api.gouv.fr)
_DEPT_TO_REGION_CODE: dict[str, str] = {
    "01": "84",
    "02": "32",
    "03": "84",
    "04": "93",
    "05": "93",
    "06": "93",
    "07": "84",
    "08": "44",
    "09": "76",
    "10": "44",
    "11": "76",
    "12": "76",
    "13": "93",
    "14": "28",
    "15": "84",
    "16": "75",
    "17": "75",
    "18": "24",
    "19": "75",
    "21": "27",
    "22": "53",
    "23": "75",
    "24": "75",
    "25": "27",
    "26": "84",
    "27": "28",
    "28": "24",
    "29": "53",
    "2A": "94",
    "2B": "94",
    "30": "76",
    "31": "76",
    "32": "76",
    "33": "75",
    "34": "76",
    "35": "53",
    "36": "24",
    "37": "24",
    "38": "84",
    "39": "27",
    "40": "75",
    "41": "24",
    "42": "84",
    "43": "84",
    "44": "52",
    "45": "24",
    "46": "76",
    "47": "75",
    "48": "76",
    "49": "52",
    "50": "28",
    "51": "44",
    "52": "44",
    "53": "52",
    "54": "44",
    "55": "44",
    "56": "53",
    "57": "44",
    "58": "27",
    "59": "32",
    "60": "32",
    "61": "28",
    "62": "32",
    "63": "84",
    "64": "75",
    "65": "76",
    "66": "76",
    "67": "44",
    "68": "44",
    "69": "84",
    "70": "27",
    "71": "27",
    "72": "52",
    "73": "84",
    "74": "84",
    "75": "11",
    "76": "28",
    "77": "11",
    "78": "11",
    "79": "75",
    "80": "32",
    "81": "76",
    "82": "76",
    "83": "93",
    "84": "93",
    "85": "52",
    "86": "75",
    "87": "75",
    "88": "44",
    "89": "27",
    "90": "27",
    "91": "11",
    "92": "11",
    "93": "11",
    "94": "11",
    "95": "11",
}

# Region code -> name
_REGION_NAMES: dict[str, str] = {
    "11": "Ile-de-France",
    "24": "Centre-Val de Loire",
    "27": "Bourgogne-Franche-Comte",
    "28": "Normandie",
    "32": "Hauts-de-France",
    "44": "Grand Est",
    "52": "Pays de la Loire",
    "53": "Bretagne",
    "75": "Nouvelle-Aquitaine",
    "76": "Occitanie",
    "84": "Auvergne-Rhone-Alpes",
    "93": "Provence-Alpes-Cote d'Azur",
    "94": "Corse",
}


class TerritorialStructuresExtractor(BaseExtractor):
    """Extract key territorial structures: communes, conseil departemental,
    conseil regional, CCI, CMA.

    Creates a rich middle layer between enterprises and the department:
    - Top N communes by population (from geo.api.gouv.fr)
    - Conseil departemental (institution)
    - Conseil regional (institution)
    - Postal code → commune matching for enterprises

    Pipeline placement: Phase 1a (external API + DB read for matching).
    Should run AFTER SireneExtractor (needs enterprises in DB for matching).
    """

    source_name = "territorial"

    _MAX_COMMUNES: int = 30  # Top N communes by population
    _MIN_POPULATION: int = 5000  # Skip tiny communes

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        import httpx

        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        territory_ext_id = f"DEPT:{department_code}"
        territory_name = _DEPT_NAMES.get(department_code, f"Departement {department_code}")
        actors[territory_ext_id] = {
            "id": str(_actor_id("territory", territory_ext_id)),
            "type": "territory",
            "external_id": territory_ext_id,
            "name": territory_name,
            "department_code": department_code,
            "metadata": {"level": "department"},
        }

        # ---------------------------------------------------------------
        # 1. Conseil departemental
        # ---------------------------------------------------------------
        cd_ext = f"CD:{department_code}"
        cd_name = f"Conseil departemental {territory_name}"
        actors[cd_ext] = {
            "id": str(_actor_id("institution", cd_ext)),
            "type": "institution",
            "external_id": cd_ext,
            "name": cd_name,
            "department_code": department_code,
            "metadata": {
                "role": "conseil_departemental",
                "level": "department",
                "source": "static",
            },
        }
        relations.append(
            {
                "id": str(_relation_id(cd_ext, territory_ext_id, "administers_territory")),
                "source_actor_external_id": cd_ext,
                "target_actor_external_id": territory_ext_id,
                "relation_type": "structural",
                "subtype": "administers_territory",
                "confidence": 0.99,
                "weight": 5.0,
                "evidence": {"source": "static", "role": "conseil_departemental"},
                "source_type": "territorial",
                "source_ref": f"cd:{department_code}",
            }
        )

        # ---------------------------------------------------------------
        # 2. Conseil regional
        # ---------------------------------------------------------------
        region_code = _DEPT_TO_REGION_CODE.get(department_code)
        if region_code:
            region_name = _REGION_NAMES.get(region_code, f"Region {region_code}")
            cr_ext = f"CR:{region_code}"
            actors[cr_ext] = {
                "id": str(_actor_id("institution", cr_ext)),
                "type": "institution",
                "external_id": cr_ext,
                "name": f"Conseil regional {region_name}",
                "department_code": None,  # Regional, not department-specific
                "metadata": {
                    "role": "conseil_regional",
                    "level": "region",
                    "region_code": region_code,
                    "source": "static",
                },
            }
            # Region -> territory
            relations.append(
                {
                    "id": str(_relation_id(cr_ext, territory_ext_id, "administers_territory")),
                    "source_actor_external_id": cr_ext,
                    "target_actor_external_id": territory_ext_id,
                    "relation_type": "structural",
                    "subtype": "administers_territory",
                    "confidence": 0.99,
                    "weight": 4.0,
                    "evidence": {"source": "static", "role": "conseil_regional"},
                    "source_type": "territorial",
                    "source_ref": f"cr:{region_code}:{department_code}",
                }
            )
            # CD -> CR (hierarchical)
            relations.append(
                {
                    "id": str(_relation_id(cd_ext, cr_ext, "belongs_to_region")),
                    "source_actor_external_id": cd_ext,
                    "target_actor_external_id": cr_ext,
                    "relation_type": "structural",
                    "subtype": "belongs_to_region",
                    "confidence": 0.99,
                    "weight": 3.0,
                    "evidence": {"source": "static"},
                    "source_type": "territorial",
                    "source_ref": f"cd-cr:{department_code}:{region_code}",
                }
            )

        # ---------------------------------------------------------------
        # 3. Top communes from geo.api.gouv.fr
        # ---------------------------------------------------------------
        communes_data: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"https://geo.api.gouv.fr/departements/{department_code}/communes",
                    params={"fields": "nom,code,population,codesPostaux"},
                )
            if resp.status_code == 200:
                all_communes = resp.json()
                # Sort by population descending, filter by min pop
                communes_data = sorted(
                    [c for c in all_communes if (c.get("population") or 0) >= self._MIN_POPULATION],
                    key=lambda c: c.get("population", 0),
                    reverse=True,
                )[: self._MAX_COMMUNES]
        except Exception:
            logger.warning(
                "TerritorialStructuresExtractor: communes API failed for dept {}",
                department_code,
            )

        # Build postal code -> commune mapping for enterprise matching
        cp_to_commune: dict[str, str] = {}

        for commune in communes_data:
            code = commune.get("code", "")
            nom = commune.get("nom", "")
            population = commune.get("population", 0)
            if not code or not nom:
                continue

            commune_ext = f"COMMUNE:{code}"
            actors[commune_ext] = {
                "id": str(_actor_id("territory", commune_ext)),
                "type": "territory",
                "external_id": commune_ext,
                "name": nom,
                "department_code": department_code,
                "metadata": {
                    "level": "commune",
                    "insee_code": code,
                    "population": population,
                    "codes_postaux": commune.get("codesPostaux", []),
                    "source": "geo.api.gouv.fr",
                },
            }

            # Commune -> department territory
            weight = min(max(1.0, population / 20_000), 8.0)
            relations.append(
                {
                    "id": str(_relation_id(commune_ext, territory_ext_id, "commune_in_dept")),
                    "source_actor_external_id": commune_ext,
                    "target_actor_external_id": territory_ext_id,
                    "relation_type": "structural",
                    "subtype": "commune_in_dept",
                    "confidence": 0.99,
                    "weight": weight,
                    "evidence": {
                        "source": "geo.api.gouv.fr",
                        "population": population,
                    },
                    "source_type": "territorial",
                    "source_ref": f"commune:{code}:{department_code}",
                }
            )

            # Commune -> CD (administered by)
            relations.append(
                {
                    "id": str(_relation_id(commune_ext, cd_ext, "administered_by")),
                    "source_actor_external_id": commune_ext,
                    "target_actor_external_id": cd_ext,
                    "relation_type": "structural",
                    "subtype": "administered_by",
                    "confidence": 0.95,
                    "weight": 1.5,
                    "evidence": {"source": "static"},
                    "source_type": "territorial",
                    "source_ref": f"commune-cd:{code}:{department_code}",
                }
            )

            # Map postal codes for enterprise matching
            for cp in commune.get("codesPostaux", []):
                if cp not in cp_to_commune:
                    cp_to_commune[cp] = commune_ext

        # ---------------------------------------------------------------
        # 4. Match enterprises to communes via postal code
        # ---------------------------------------------------------------
        if cp_to_commune:
            async with acquire_conn() as conn:
                enterprise_rows = await conn.fetch(
                    """SELECT external_id, metadata
                       FROM actors
                       WHERE department_code = $1 AND type = 'enterprise'""",
                    department_code,
                )

            matched = 0
            for row in enterprise_rows:
                meta = _parse_raw_data(row["metadata"])
                cp = meta.get("code_postal", "")
                if not cp:
                    # Try ville-based postal code from BODACC
                    cp = meta.get("cp", "")
                if not cp or cp not in cp_to_commune:
                    continue

                commune_ext = cp_to_commune[cp]
                ent_ext = row["external_id"]
                relations.append(
                    {
                        "id": str(_relation_id(ent_ext, commune_ext, "located_in_commune")),
                        "source_actor_external_id": ent_ext,
                        "target_actor_external_id": commune_ext,
                        "relation_type": "structural",
                        "subtype": "located_in_commune",
                        "confidence": 0.85,
                        "weight": 1.0,
                        "evidence": {"source": "postal_code_match", "code_postal": cp},
                        "source_type": "territorial",
                        "source_ref": f"cp:{ent_ext}:{commune_ext}",
                    }
                )
                matched += 1

            logger.info(
                "TerritorialStructuresExtractor dept {}: matched {} enterprises to communes",
                department_code,
                matched,
            )

        logger.info(
            "TerritorialStructuresExtractor dept {}: {} actors, {} relations ({} communes)",
            department_code,
            len(actors),
            len(relations),
            len(communes_data),
        )
        return {"actors": list(actors.values()), "relations": relations}


# ---------------------------------------------------------------------------
# SIRENE Address Enricher (post-persist)
# ---------------------------------------------------------------------------


class SireneAddressEnricher(BaseExtractor):
    """Enrich enterprise actors with address data from the SIRENE API.

    Post-persist extractor that:
    1. Finds enterprise actors missing ``code_postal`` in metadata
    2. Calls recherche-entreprises.api.gouv.fr to get siege address
    3. Updates actor metadata with code_postal, commune, latitude, longitude
    4. Creates ``located_in_commune`` relations for newly geocoded enterprises

    Rate-limited to avoid overloading the free API (batch of 50, 200ms delay).
    """

    source_name = "sirene_enrich"

    _BATCH_SIZE = 50
    _DELAY_BETWEEN = 0.2  # seconds

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        import asyncio

        actors: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            # Find enterprises without code_postal
            rows = await conn.fetch(
                """
                SELECT id, external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'enterprise'
                  AND (metadata->>'code_postal' IS NULL
                       OR metadata->>'code_postal' = '')
                  AND external_id LIKE 'SIREN:%'
                ORDER BY name
                LIMIT 200
                """,
                department_code,
            )

            # Also get existing communes for matching
            commune_rows = await conn.fetch(
                """
                SELECT external_id, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'territory'
                  AND external_id LIKE 'COMMUNE:%'
                """,
                department_code,
            )

        if not rows:
            logger.info(
                "SireneAddressEnricher: all enterprises have addresses for dept {}", department_code
            )
            return {"actors": [], "relations": []}

        # Build commune lookup by postal code
        commune_by_cp: dict[str, str] = {}
        for crow in commune_rows:
            cmeta = crow["metadata"] if isinstance(crow["metadata"], dict) else {}
            for cp in cmeta.get("codes_postaux", []):
                commune_by_cp[str(cp)] = crow["external_id"]

        enriched = 0
        async with httpx.AsyncClient(timeout=15.0) as client:
            for row in rows[: self._BATCH_SIZE]:
                siren = row["external_id"].replace("SIREN:", "")
                try:
                    resp = await client.get(
                        "https://recherche-entreprises.api.gouv.fr/search",
                        params={"q": siren, "per_page": 1},
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    results = data.get("results", [])
                    if not results:
                        continue

                    siege = results[0].get("siege", {})
                    cp = siege.get("code_postal")
                    commune = siege.get("libelle_commune")
                    lat = siege.get("latitude")
                    lon = siege.get("longitude")
                    date_creation = results[0].get("date_creation")

                    if not cp:
                        continue

                    # Update actor metadata
                    old_meta = row["metadata"] if isinstance(row["metadata"], dict) else {}
                    new_meta = {
                        **old_meta,
                        "code_postal": cp,
                        "commune": commune,
                    }
                    if lat and lon:
                        new_meta["latitude"] = float(lat)
                        new_meta["longitude"] = float(lon)
                    if date_creation and "date_creation" not in old_meta:
                        new_meta["date_creation"] = date_creation

                    actors.append(
                        {
                            "id": str(row["id"]),
                            "type": "enterprise",
                            "external_id": row["external_id"],
                            "name": row["name"],
                            "department_code": department_code,
                            "metadata": new_meta,
                        }
                    )

                    # Create located_in_commune if matching commune exists
                    ent_ext = row["external_id"]
                    commune_ext = commune_by_cp.get(cp)
                    if commune_ext:
                        rel_id = _relation_id(ent_ext, commune_ext, "located_in_commune")
                        relations.append(
                            {
                                "id": str(rel_id),
                                "source_actor_external_id": ent_ext,
                                "target_actor_external_id": commune_ext,
                                "relation_type": "structural",
                                "subtype": "located_in_commune",
                                "confidence": 0.90,
                                "weight": 1.0,
                                "evidence": {
                                    "source": "sirene_api",
                                    "code_postal": cp,
                                    "commune": commune,
                                },
                                "source_type": "sirene",
                                "source_ref": f"sirene_enrich:{ent_ext}:{cp}",
                            }
                        )

                    enriched += 1
                    await asyncio.sleep(self._DELAY_BETWEEN)

                except Exception as e:
                    logger.debug("SireneAddressEnricher: failed for {}: {}", siren, e)
                    continue

        logger.info(
            "SireneAddressEnricher dept={}: enriched {}/{} enterprises, {} commune relations",
            department_code,
            enriched,
            len(rows),
            len(relations),
        )
        return {"actors": actors, "relations": relations}


class SireneDirigeantsEnricher(BaseExtractor):
    """Enrich enterprise actors with dirigeants and financial data from SIRENE API.

    Post-persist extractor that:
    1. Finds enterprise actors missing ``dirigeants`` in metadata
    2. Calls recherche-entreprises.api.gouv.fr with ``include=dirigeants,finances``
    3. Updates actor metadata with dirigeants list and latest CA/resultat_net

    Dirigeants data enables DirectorLinkInferrer V2 (shared directors detection).
    Financial data enables better employment/impact scoring.
    """

    source_name = "sirene_dirigeants"

    _BATCH_SIZE = 80
    _DELAY = 0.15  # seconds between API calls

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        import asyncio

        actors: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            rows = await conn.fetch(
                """
                SELECT id, external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'enterprise'
                  AND external_id LIKE 'SIREN:%'
                  AND (metadata->>'dirigeants' IS NULL)
                ORDER BY name
                LIMIT 500
                """,
                department_code,
            )

        if not rows:
            logger.info(
                "SireneDirigeantsEnricher: all enterprises already enriched for dept {}",
                department_code,
            )
            return {"actors": [], "relations": []}

        logger.info(
            "SireneDirigeantsEnricher: enriching {}/{} enterprises for dept {}",
            min(len(rows), self._BATCH_SIZE),
            len(rows),
            department_code,
        )

        enriched = 0
        async with httpx.AsyncClient(timeout=15.0) as client:
            for row in rows[: self._BATCH_SIZE]:
                siren = row["external_id"].replace("SIREN:", "")
                try:
                    resp = await client.get(
                        "https://recherche-entreprises.api.gouv.fr/search",
                        params={
                            "q": siren,
                            "per_page": 1,
                            "minimal": "true",
                            "include": "dirigeants,finances",
                        },
                    )
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    results = data.get("results", [])
                    if not results:
                        continue

                    r = results[0]
                    if r.get("siren") != siren:
                        continue

                    # Extract dirigeants (persons only, skip personnes morales)
                    dirigeants_raw = r.get("dirigeants", [])
                    dirigeants = []
                    for d in dirigeants_raw:
                        if d.get("type_dirigeant") == "personne physique":
                            dirigeants.append(
                                {
                                    "nom": d.get("nom", ""),
                                    "prenoms": d.get("prenoms", ""),
                                    "qualite": d.get("qualite", ""),
                                    "annee_naissance": d.get("annee_de_naissance", ""),
                                }
                            )

                    # Extract latest finances
                    finances = r.get("finances", {})
                    latest_year = max(finances.keys()) if finances else None
                    ca = None
                    resultat_net = None
                    if latest_year:
                        ca = finances[latest_year].get("ca")
                        resultat_net = finances[latest_year].get("resultat_net")

                    # Also grab categorie_entreprise and tranche_effectif
                    categorie = r.get("categorie_entreprise")
                    tranche = r.get("tranche_effectif_salarie")

                    old_meta = row["metadata"] if isinstance(row["metadata"], dict) else {}
                    new_meta = {**old_meta, "dirigeants": dirigeants}
                    if ca is not None:
                        new_meta["ca"] = ca
                        new_meta["annee_ca"] = latest_year
                    if resultat_net is not None:
                        new_meta["resultat_net"] = resultat_net
                    if categorie:
                        new_meta["categorie_entreprise"] = categorie
                    if tranche and "tranche_effectif" not in old_meta:
                        new_meta["tranche_effectif"] = tranche

                    actors.append(
                        {
                            "id": str(row["id"]),
                            "type": "enterprise",
                            "external_id": row["external_id"],
                            "name": row["name"],
                            "department_code": department_code,
                            "metadata": new_meta,
                        }
                    )
                    enriched += 1
                    await asyncio.sleep(self._DELAY)

                except Exception as e:
                    logger.debug("SireneDirigeantsEnricher: failed for {}: {}", siren, e)
                    continue

        logger.info(
            "SireneDirigeantsEnricher dept={}: enriched {}/{} enterprises "
            "({} with dirigeants, {} with finances)",
            department_code,
            enriched,
            len(rows),
            sum(1 for a in actors if a["metadata"].get("dirigeants")),
            sum(1 for a in actors if a["metadata"].get("ca") is not None),
        )
        return {"actors": actors, "relations": []}


class UrssafEffectifsEnricher(BaseExtractor):
    """Enrich territory and sector actors with real employment data from URSSAF.

    Post-persist extractor that queries open.urssaf.fr for actual employee
    counts by commune and by NAF code. Replaces the estimated tranche_effectif
    with real URSSAF aggregated data.

    Data source: open.urssaf.fr (free, no auth, OpenDataSoft API).
    Granularity: commune × code APE, annual (latest year).
    """

    source_name = "urssaf"

    _API_BASE = (
        "https://open.urssaf.fr/api/explore/v2.1/catalog/datasets/"
        "etablissements-et-effectifs-salaries-au-niveau-commune-x-ape-last/records"
    )
    _LATEST_YEAR = "2024"

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: list[dict[str, Any]] = []

        async with acquire_conn() as conn:
            # Get existing territory actors (communes + department)
            territory_rows = await conn.fetch(
                """
                SELECT id, external_id, name, metadata
                FROM actors
                WHERE department_code = $1
                  AND type = 'territory'
                """,
                department_code,
            )
            # Get existing sector actors
            sector_rows = await conn.fetch(
                """
                SELECT id, external_id, name, metadata
                FROM actors
                WHERE type = 'sector'
                  AND external_id LIKE 'NAF:%'
                """,
            )

        # Build lookups
        territory_by_code: dict[str, dict] = {}
        for r in territory_rows:
            ext = r["external_id"]
            if ext.startswith("COMMUNE:"):
                code = ext.replace("COMMUNE:", "")
                territory_by_code[code] = dict(r)
            elif ext.startswith("DEPT:"):
                territory_by_code[f"DEPT:{department_code}"] = dict(r)

        sector_by_naf: dict[str, dict] = {}
        for r in sector_rows:
            naf = r["external_id"].replace("NAF:", "")
            sector_by_naf[naf] = dict(r)

        eff_col = f"effectifs_salaries_{self._LATEST_YEAR}"
        etab_col = f"nombre_d_etablissements_{self._LATEST_YEAR}"

        # --- Query 1: aggregate by commune ---
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    self._API_BASE,
                    params={
                        "where": f"code_departement='{department_code}'",
                        "select": (
                            f"code_commune, intitule_commune, "
                            f"sum({eff_col}) as total_effectifs, "
                            f"sum({etab_col}) as total_etabs"
                        ),
                        "group_by": "code_commune, intitule_commune",
                        "order_by": "total_effectifs DESC",
                        "limit": "200",
                    },
                )
                if resp.status_code != 200:
                    logger.warning("URSSAF commune query failed: {}", resp.status_code)
                    return {"actors": [], "relations": []}

                commune_data = resp.json().get("results", [])
            except Exception as e:
                logger.error("URSSAF API error: {}", e)
                return {"actors": [], "relations": []}

            # --- Query 2: aggregate by NAF code ---
            try:
                resp2 = await client.get(
                    self._API_BASE,
                    params={
                        "where": f"code_departement='{department_code}'",
                        "select": (
                            f"code_ape, ape, "
                            f"sum({eff_col}) as total_effectifs, "
                            f"sum({etab_col}) as total_etabs"
                        ),
                        "group_by": "code_ape, ape",
                        "order_by": "total_effectifs DESC",
                        "limit": "500",
                    },
                )
                sector_data = resp2.json().get("results", []) if resp2.status_code == 200 else []
            except Exception:
                sector_data = []

            # --- Query 3: department total ---
            try:
                resp3 = await client.get(
                    self._API_BASE,
                    params={
                        "where": f"code_departement='{department_code}'",
                        "select": (
                            f"sum({eff_col}) as total_effectifs, sum({etab_col}) as total_etabs"
                        ),
                        "limit": "1",
                    },
                )
                dept_total = (
                    resp3.json().get("results", [{}])[0] if resp3.status_code == 200 else {}
                )
            except Exception:
                dept_total = {}

        # --- Enrich commune actors ---
        communes_enriched = 0
        for cd in commune_data:
            code = cd.get("code_commune")
            if not code or code not in territory_by_code:
                continue
            row = territory_by_code[code]
            old_meta = row["metadata"] if isinstance(row["metadata"], dict) else {}
            new_meta = {
                **old_meta,
                "effectifs_salaries": cd.get("total_effectifs", 0),
                "nb_etablissements": cd.get("total_etabs", 0),
                "source_effectifs": "urssaf",
                "annee_effectifs": self._LATEST_YEAR,
            }
            actors.append(
                {
                    "id": str(row["id"]),
                    "type": "territory",
                    "external_id": row["external_id"],
                    "name": row["name"],
                    "department_code": department_code,
                    "metadata": new_meta,
                }
            )
            communes_enriched += 1

        # --- Enrich department actor ---
        dept_key = f"DEPT:{department_code}"
        if dept_key in territory_by_code and dept_total:
            row = territory_by_code[dept_key]
            old_meta = row["metadata"] if isinstance(row["metadata"], dict) else {}
            new_meta = {
                **old_meta,
                "effectifs_salaries": dept_total.get("total_effectifs", 0),
                "nb_etablissements": dept_total.get("total_etabs", 0),
                "source_effectifs": "urssaf",
                "annee_effectifs": self._LATEST_YEAR,
            }
            actors.append(
                {
                    "id": str(row["id"]),
                    "type": "territory",
                    "external_id": row["external_id"],
                    "name": row["name"],
                    "department_code": department_code,
                    "metadata": new_meta,
                }
            )

        # --- Enrich sector actors ---
        sectors_enriched = 0
        for sd in sector_data:
            raw_code = sd.get("code_ape", "")
            if not raw_code:
                continue
            # Normalize: URSSAF uses "4333Z", our actors use "43.33Z"
            naf_code = (
                f"{raw_code[:2]}.{raw_code[2:]}"
                if len(raw_code) >= 4 and "." not in raw_code
                else raw_code
            )
            if naf_code not in sector_by_naf:
                continue
            row = sector_by_naf[naf_code]
            old_meta = row["metadata"] if isinstance(row["metadata"], dict) else {}
            dept_eff_key = f"effectifs_{department_code}"
            new_meta = {
                **old_meta,
                dept_eff_key: sd.get("total_effectifs", 0),
                f"etabs_{department_code}": sd.get("total_etabs", 0),
                "source_effectifs": "urssaf",
            }
            actors.append(
                {
                    "id": str(row["id"]),
                    "type": "sector",
                    "external_id": row["external_id"],
                    "name": row["name"],
                    "department_code": None,
                    "metadata": new_meta,
                }
            )
            sectors_enriched += 1

        logger.info(
            "UrssafEffectifsEnricher dept={}: {} communes enriched, {} sectors enriched, "
            "dept total = {} emplois / {} etablissements",
            department_code,
            communes_enriched,
            sectors_enriched,
            dept_total.get("total_effectifs", "?"),
            dept_total.get("total_etabs", "?"),
        )
        return {"actors": actors, "relations": []}


class ADEMEExtractor(BaseExtractor):
    """Extract ADEME financial aids for enterprises in a department.

    Uses the ADEME open data API (data.ademe.fr) to find individual
    grants with SIRET, amount, and purpose. Creates ``funded_by_ademe``
    relations between beneficiary enterprises/institutions and the ADEME.

    Data source: https://data.ademe.fr (free, no auth, DataFair API).
    """

    source_name = "ademe"

    _API_URL = (
        "https://data.ademe.fr/data-fair/api/v1/datasets/les-aides-financieres-de-l'ademe/lines"
    )
    _PAGE_SIZE = 200

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        # ADEME actor (national funder)
        ademe_ext = "INST:ADEME"
        actors[ademe_ext] = {
            "id": str(_actor_id("institution", ademe_ext)),
            "type": "institution",
            "external_id": ademe_ext,
            "name": "ADEME",
            "department_code": None,
            "metadata": {"full_name": "Agence de la transition écologique", "siren": "385290309"},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            after = None
            total_fetched = 0
            max_pages = 10  # cap at 2000 aids

            for _ in range(max_pages):
                params: dict[str, Any] = {
                    "size": self._PAGE_SIZE,
                    "format": "json",
                    "qs": f'_siret_infos._infos_commune.code_departement:"{department_code}"',
                    "select": "idBeneficiaire,nomBeneficiaire,montant,objet,dateConvention,nature,referenceDecision",
                }
                if after:
                    params["after"] = after

                try:
                    resp = await client.get(self._API_URL, params=params)
                    if resp.status_code != 200:
                        logger.warning("ADEME API returned {}", resp.status_code)
                        break
                    data = resp.json()
                except Exception as e:
                    logger.error("ADEME API error: {}", e)
                    break

                results = data.get("results", [])
                if not results:
                    break

                for rec in results:
                    siret = rec.get("idBeneficiaire", "")
                    name = rec.get("nomBeneficiaire", "")
                    montant = rec.get("montant", 0)
                    objet = rec.get("objet", "")
                    date_conv = rec.get("dateConvention", "")

                    if not siret or len(siret) < 9:
                        continue

                    # Use SIREN (first 9 digits of SIRET) for matching
                    siren = siret[:9]
                    ent_ext = f"SIREN:{siren}"

                    # Create/update beneficiary actor (minimal — may already exist)
                    if ent_ext not in actors:
                        actors[ent_ext] = {
                            "id": str(_actor_id("enterprise", ent_ext)),
                            "type": "enterprise",
                            "external_id": ent_ext,
                            "name": name,
                            "department_code": department_code,
                            "metadata": {},
                        }

                    # Accumulate ADEME aids in metadata
                    meta = actors[ent_ext]["metadata"]
                    aids = meta.get("ademe_aids", [])
                    aids.append(
                        {
                            "montant": montant,
                            "objet": objet[:200],
                            "date": date_conv,
                        }
                    )
                    meta["ademe_aids"] = aids
                    meta["ademe_total"] = meta.get("ademe_total", 0) + (montant or 0)

                    # Relation: enterprise -> ADEME (funded_by_ademe)
                    rel_id = _relation_id(
                        ent_ext, ademe_ext, f"funded_by_ademe:{siret}:{date_conv}"
                    )
                    relations.append(
                        {
                            "id": str(rel_id),
                            "source_actor_external_id": ent_ext,
                            "target_actor_external_id": ademe_ext,
                            "relation_type": "structural",
                            "subtype": "funded_by_ademe",
                            "confidence": 0.95,
                            "weight": min((montant or 0) / 100000.0, 5.0),
                            "evidence": {
                                "source": "ademe",
                                "siret": siret,
                                "montant": montant,
                                "objet": objet[:200],
                                "date_convention": date_conv,
                                "reference": rec.get("referenceDecision", ""),
                            },
                            "source_type": "ademe",
                            "source_ref": f"ademe:{siret}:{date_conv}",
                        }
                    )

                total_fetched += len(results)

                # Pagination: use the "next" URL's "after" param
                next_url = data.get("next", "")
                if not next_url or "after=" not in next_url:
                    break
                after = next_url.split("after=")[-1]

        logger.info(
            "ADEMEExtractor dept={}: {} aids fetched, {} actors, {} relations",
            department_code,
            total_fetched,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


class QualiopiExtractor(BaseExtractor):
    """Extract Qualiopi-certified training organisations for a department.

    Uses the DGEFP open data API (dgefp.opendatasoft.com) to find
    certified training organisms with SIREN, specialties, and trainee
    counts.  Creates ``formation`` actors and ``trains_in_territory``
    relations linking them to a territory actor.

    Data source: https://dgefp.opendatasoft.com (free, no auth, ODS API v2.1).
    """

    source_name = "qualiopi"

    _API_URL = (
        "https://dgefp.opendatasoft.com/api/explore/v2.1/catalog/datasets"
        "/liste-publique-des-of-v2/records"
    )
    _PAGE_SIZE = 100

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        # Territory actor (target for trains_in_territory)
        terr_ext = f"DEPT:{department_code}"
        actors[terr_ext] = {
            "id": str(_actor_id("territory", terr_ext)),
            "type": "territory",
            "external_id": terr_ext,
            "name": f"Département {department_code}",
            "department_code": department_code,
            "metadata": {},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            offset = 0
            total_fetched = 0
            max_records = 3500  # safety cap

            while total_fetched < max_records:
                params: dict[str, Any] = {
                    "where": f"dep_code='{department_code}'",
                    "limit": self._PAGE_SIZE,
                    "offset": offset,
                    "select": (
                        "denomination,siren,siretetablissementdeclarant,"
                        "adressephysiqueorganismeformation_ville,"
                        "certifications_actionsdeformation,"
                        "certifications_bilansdecompetences,"
                        "certifications_vae,"
                        "certifications_actionsdeformationparapprentissage,"
                        "informationsdeclarees_specialitesdeformation_libellespecialite1,"
                        "informationsdeclarees_specialitesdeformation_libellespecialite2,"
                        "informationsdeclarees_specialitesdeformation_libellespecialite3,"
                        "informationsdeclarees_nbstagiaires,"
                        "informationsdeclarees_effectifformateurs"
                    ),
                }

                try:
                    resp = await client.get(self._API_URL, params=params)
                    if resp.status_code != 200:
                        logger.warning("Qualiopi API returned {}", resp.status_code)
                        break
                    data = resp.json()
                except Exception as e:
                    logger.error("Qualiopi API error: {}", e)
                    break

                results = data.get("results", [])
                if not results:
                    break

                for rec in results:
                    siren = rec.get("siren", "")
                    name = rec.get("denomination", "")
                    if not siren or len(siren) < 9:
                        continue

                    siren = siren[:9]
                    ent_ext = f"SIREN:{siren}"

                    # Build specialties list
                    specialties = []
                    for i in range(1, 4):
                        sp = rec.get(
                            f"informationsdeclarees_specialitesdeformation_libellespecialite{i}"
                        )
                        if sp:
                            specialties.append(sp)

                    # Build certifications dict
                    certs = {}
                    for cert_key in (
                        "actionsdeformation",
                        "bilansdecompetences",
                        "vae",
                        "actionsdeformationparapprentissage",
                    ):
                        val = rec.get(f"certifications_{cert_key}")
                        if val is not None:
                            certs[cert_key] = val == "true" or val is True

                    nb_stagiaires = rec.get("informationsdeclarees_nbstagiaires") or 0
                    effectif_formateurs = rec.get("informationsdeclarees_effectifformateurs") or 0

                    # Create/update formation actor
                    if ent_ext not in actors:
                        actors[ent_ext] = {
                            "id": str(_actor_id("enterprise", ent_ext)),
                            "type": "enterprise",
                            "external_id": ent_ext,
                            "name": name,
                            "department_code": department_code,
                            "metadata": {},
                        }

                    meta = actors[ent_ext]["metadata"]
                    meta["qualiopi"] = True
                    meta["qualiopi_certifications"] = certs
                    if specialties:
                        meta["qualiopi_specialties"] = specialties
                    if nb_stagiaires:
                        meta["qualiopi_nb_stagiaires"] = nb_stagiaires
                    if effectif_formateurs:
                        meta["qualiopi_effectif_formateurs"] = effectif_formateurs
                    ville = rec.get("adressephysiqueorganismeformation_ville")
                    if ville:
                        meta["qualiopi_ville"] = ville

                    # Relation: formation org -> territory
                    rel_id = _relation_id(ent_ext, terr_ext, f"trains_in:{siren}")
                    relations.append(
                        {
                            "id": str(rel_id),
                            "source_actor_external_id": ent_ext,
                            "target_actor_external_id": terr_ext,
                            "relation_type": "structural",
                            "subtype": "trains_in_territory",
                            "confidence": 0.95,
                            "weight": min(nb_stagiaires / 500.0, 5.0) if nb_stagiaires else 1.0,
                            "evidence": {
                                "source": "qualiopi",
                                "siren": siren,
                                "denomination": name,
                                "certifications": certs,
                                "specialties": specialties,
                                "nb_stagiaires": nb_stagiaires,
                                "effectif_formateurs": effectif_formateurs,
                            },
                            "source_type": "qualiopi",
                            "source_ref": f"qualiopi:{siren}",
                        }
                    )

                total_fetched += len(results)
                offset += self._PAGE_SIZE

                # Stop if we got fewer results than requested (last page)
                if len(results) < self._PAGE_SIZE:
                    break

        logger.info(
            "QualiopiExtractor dept={}: {} orgs fetched, {} actors, {} relations",
            department_code,
            total_fetched,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}


class OFGLExtractor(BaseExtractor):
    """Extract local government finances and EPCI compositions for a department.

    Uses the OFGL open-data API (data.ofgl.fr, OpenDataSoft v2.1) to:
    1. Fetch commune finances (recettes, dépenses, dette, investissement)
       → creates ``institution_finances_territory`` relations.
    2. Fetch EPCI composition (which communes belong to which EPCI)
       → creates ``member_of_epci`` relations.

    No authentication required.
    """

    source_name = "ofgl"

    _BASE = "https://data.ofgl.fr/api/explore/v2.1/catalog/datasets"
    _DS_COMMUNES = "ofgl-base-communes-consolidee"
    _DS_EPCI_COMP = "detail_compositions_intercommunales_2012_2023"

    # Key budget aggregates we extract per commune.
    # NOTE: avoid agregats with apostrophes (e.g. "Dépenses d'équipement")
    # because ODSQL treats the apostrophe as a string delimiter.
    _KEY_AGREGATS = [
        "Recettes de fonctionnement",
        "Dépenses de fonctionnement",
        "Dépenses totales",
        "Encours de dette",
        "Impôts locaux",
        "Epargne brute",
    ]

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            # --- Part 1: commune finances ---
            await self._extract_commune_finances(client, department_code, actors, relations)

            # --- Part 2: EPCI compositions ---
            await self._extract_epci_compositions(client, department_code, actors, relations)

        logger.info(
            "OFGLExtractor dept={}: {} actors, {} relations",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}

    # ------------------------------------------------------------------

    async def _extract_commune_finances(
        self,
        client: httpx.AsyncClient,
        department_code: str,
        actors: dict[str, dict[str, Any]],
        relations: list[dict[str, Any]],
    ) -> None:
        """Fetch key budget aggregates for all communes in the department."""

        # Territory actor for the department itself
        dept_ext = f"DEPT:{department_code}"
        dept_name = _DEPT_NAMES.get(department_code, department_code)
        actors[dept_ext] = {
            "id": str(_actor_id("territory", dept_ext)),
            "type": "territory",
            "external_id": dept_ext,
            "name": dept_name,
            "department_code": department_code,
            "metadata": {},
        }

        # Fetch the main financial aggregates for all communes, latest year only.
        # We fetch "Recettes de fonctionnement" to discover communes, then fetch
        # the other aggregates in bulk.
        commune_data: dict[str, dict[str, Any]] = {}  # key: com_code

        for agregat in self._KEY_AGREGATS:
            # OFGL API enforces limit <= 100. Paginate to get all communes.
            all_results: list[dict] = []
            offset = 0
            page_size = 100

            for _page in range(20):  # max 2000 records per agregat
                params = {
                    "limit": page_size,
                    "offset": offset,
                    "where": f"dep_code='{department_code}' AND agregat='{agregat}'",
                    "select": "com_code,com_name,siren,insee,montant,ptot,euros_par_habitant,exer",
                    "order_by": "exer DESC",
                }
                try:
                    resp = await client.get(
                        f"{self._BASE}/{self._DS_COMMUNES}/records", params=params
                    )
                    if resp.status_code != 200:
                        err_msg = resp.text.replace("\n", " ")[:200]
                        logger.warning(
                            "OFGL communes API returned {} for agregat '{}': {}",
                            resp.status_code,
                            agregat,
                            err_msg,
                        )
                        break
                    data = resp.json()
                except Exception as e:
                    logger.error("OFGL communes API error for agregat '{}': {}", agregat, e)
                    break

                page_results = data.get("results", [])
                all_results.extend(page_results)
                if len(page_results) < page_size:
                    break
                offset += page_size

            # Keep only latest year per commune (results ordered by exer DESC)
            seen_communes: set[str] = set()
            for rec in all_results:
                com_code = rec.get("com_code", "")
                if not com_code or com_code in seen_communes:
                    continue
                seen_communes.add(com_code)

                if com_code not in commune_data:
                    commune_data[com_code] = {
                        "com_name": rec.get("com_name", ""),
                        "siren": rec.get("siren", ""),
                        "insee": rec.get("insee", ""),
                        "ptot": rec.get("ptot", 0),
                        "exer": rec.get("exer", ""),
                        "finances": {},
                    }

                agg_key = self._agregat_key(agregat)
                commune_data[com_code]["finances"][agg_key] = rec.get("montant", 0)
                commune_data[com_code]["finances"][f"{agg_key}_par_hab"] = rec.get(
                    "euros_par_habitant", 0
                )

        # Create actors and relations from collected data
        for com_code, cd in commune_data.items():
            siren = cd.get("siren", "")
            if not siren:
                continue

            # Institution actor (the collectivité, identified by SIREN)
            inst_ext = f"SIREN:{siren}"
            if inst_ext not in actors:
                actors[inst_ext] = {
                    "id": str(_actor_id("institution", inst_ext)),
                    "type": "institution",
                    "external_id": inst_ext,
                    "name": cd.get("com_name", com_code),
                    "department_code": department_code,
                    "metadata": {
                        "insee": cd.get("insee", ""),
                        "population": cd.get("ptot", 0),
                        "nature": "commune",
                    },
                }

            # Enrich metadata with finances
            actors[inst_ext]["metadata"]["finances"] = cd["finances"]
            actors[inst_ext]["metadata"]["budget_year"] = cd.get("exer", "")

            # Relation: institution → territory (institution_finances_territory)
            finances = cd["finances"]
            recettes = finances.get("recettes_fonctionnement", 0)
            depenses = finances.get("depenses_fonctionnement", 0)
            depenses_totales = finances.get("depenses_totales", 0)
            dette = finances.get("encours_dette", 0)
            epargne = finances.get("epargne_brute", 0)

            rel_id = _relation_id(inst_ext, dept_ext, f"institution_finances_territory:{com_code}")
            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": inst_ext,
                    "target_actor_external_id": dept_ext,
                    "relation_type": "structural",
                    "subtype": "institution_finances_territory",
                    "confidence": 0.95,
                    "weight": min((recettes or 0) / 10_000_000, 5.0),
                    "evidence": {
                        "source": "ofgl",
                        "com_code": com_code,
                        "recettes_fonctionnement": recettes,
                        "depenses_fonctionnement": depenses,
                        "depenses_totales": depenses_totales,
                        "encours_dette": dette,
                        "epargne_brute": epargne,
                        "population": cd.get("ptot", 0),
                        "annee": cd.get("exer", ""),
                    },
                    "source_type": "ofgl",
                    "source_ref": f"ofgl:communes:{com_code}:{cd.get('exer', '')}",
                }
            )

    async def _extract_epci_compositions(
        self,
        client: httpx.AsyncClient,
        department_code: str,
        actors: dict[str, dict[str, Any]],
        relations: list[dict[str, Any]],
    ) -> None:
        """Fetch EPCI compositions: which communes belong to which EPCI."""

        # Paginate EPCI compositions (limit max 100)
        all_epci_results: list[dict] = []
        offset = 0
        page_size = 100

        for _page in range(20):
            params = {
                "limit": page_size,
                "offset": offset,
                "where": f"startswith(insee, '{department_code}')",
                "select": "insee,siren,nom,siren_epci,nom_epci,pmun,annee",
                "order_by": "annee DESC",
            }
            try:
                resp = await client.get(f"{self._BASE}/{self._DS_EPCI_COMP}/records", params=params)
                if resp.status_code != 200:
                    err_msg = resp.text.replace("\n", " ")[:200]
                    logger.warning(
                        "OFGL EPCI compositions API returned {}: {}", resp.status_code, err_msg
                    )
                    break
                data = resp.json()
            except Exception as e:
                logger.error("OFGL EPCI compositions API error: {}", e)
                break

            page_results = data.get("results", [])
            all_epci_results.extend(page_results)
            if len(page_results) < page_size:
                break
            offset += page_size

        # Keep only latest year per commune
        seen: set[str] = set()
        epci_members: dict[str, list[dict]] = {}  # siren_epci → [commune_info]

        for rec in all_epci_results:
            insee = rec.get("insee", "")
            if not insee or insee in seen:
                continue
            seen.add(insee)

            siren_epci = str(rec.get("siren_epci", ""))
            nom_epci = rec.get("nom_epci", "")
            if not siren_epci:
                continue

            # Ensure EPCI actor exists
            epci_ext = f"SIREN:{siren_epci}"
            if epci_ext not in actors:
                actors[epci_ext] = {
                    "id": str(_actor_id("institution", epci_ext)),
                    "type": "institution",
                    "external_id": epci_ext,
                    "name": nom_epci,
                    "department_code": department_code,
                    "metadata": {"nature": "epci"},
                }

            # Track members for metadata enrichment
            if siren_epci not in epci_members:
                epci_members[siren_epci] = []
            epci_members[siren_epci].append(
                {
                    "insee": insee,
                    "nom": rec.get("nom", ""),
                    "population": rec.get("pmun", 0),
                }
            )

            # Commune actor (may already exist from finances step)
            siren_commune = str(rec.get("siren", ""))
            commune_ext = f"SIREN:{siren_commune}" if siren_commune else f"INSEE:{insee}"
            if commune_ext not in actors:
                actors[commune_ext] = {
                    "id": str(_actor_id("institution", commune_ext)),
                    "type": "institution",
                    "external_id": commune_ext,
                    "name": rec.get("nom", insee),
                    "department_code": department_code,
                    "metadata": {
                        "insee": insee,
                        "nature": "commune",
                        "population": rec.get("pmun", 0),
                    },
                }

            # Relation: commune → EPCI (member_of_epci)
            rel_id = _relation_id(commune_ext, epci_ext, f"member_of_epci:{insee}")
            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": commune_ext,
                    "target_actor_external_id": epci_ext,
                    "relation_type": "structural",
                    "subtype": "member_of_epci",
                    "confidence": 0.95,
                    "weight": min((rec.get("pmun", 0) or 0) / 100_000, 3.0),
                    "evidence": {
                        "source": "ofgl_compositions",
                        "insee_commune": insee,
                        "siren_epci": siren_epci,
                        "nom_epci": nom_epci,
                        "population": rec.get("pmun", 0),
                        "annee": rec.get("annee", ""),
                    },
                    "source_type": "ofgl",
                    "source_ref": f"ofgl:epci_comp:{insee}:{siren_epci}",
                }
            )

        # Enrich EPCI actors with member counts
        for siren_epci, members in epci_members.items():
            epci_ext = f"SIREN:{siren_epci}"
            if epci_ext in actors:
                actors[epci_ext]["metadata"]["nb_communes"] = len(members)
                actors[epci_ext]["metadata"]["population_totale"] = sum(
                    m.get("population", 0) for m in members
                )

    @staticmethod
    def _agregat_key(agregat: str) -> str:
        """Normalize an OFGL agregat label to a safe dict key."""
        mapping = {
            "Recettes de fonctionnement": "recettes_fonctionnement",
            "Dépenses de fonctionnement": "depenses_fonctionnement",
            "Dépenses totales": "depenses_totales",
            "Encours de dette": "encours_dette",
            "Impôts locaux": "impots_locaux",
            "Epargne brute": "epargne_brute",
        }
        return mapping.get(agregat, agregat.lower().replace(" ", "_").replace("'", ""))


class DVFExtractor(BaseExtractor):
    """Extract real-estate transaction statistics for a department.

    Uses the Cerema DVF API (apidf-preprod.cerema.fr) which provides
    free access to property transaction data (Demandes de Valeurs Foncières).
    Creates ``territory_immo_activity`` relations showing transaction volume
    and median prices per commune, enriching the territorial graph with
    economic dynamism indicators.

    No authentication required.
    """

    source_name = "dvf"

    _API_URL = "https://apidf-preprod.cerema.fr/dvf_opendata/mutations/"
    _GEO_API = "https://geo.api.gouv.fr/departements"

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        # Territory actor for the department
        dept_ext = f"DEPT:{department_code}"
        dept_name = _DEPT_NAMES.get(department_code, department_code)
        actors[dept_ext] = {
            "id": str(_actor_id("territory", dept_ext)),
            "type": "territory",
            "external_id": dept_ext,
            "name": dept_name,
            "department_code": department_code,
            "metadata": {},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get list of communes in this department
            communes = await self._get_communes(client, department_code)
            if not communes:
                logger.warning("DVFExtractor: no communes found for dept {}", department_code)
                return {"actors": list(actors.values()), "relations": relations}

            # Process top communes by population (cap at 30 to stay within rate limits)
            communes_sorted = sorted(
                communes, key=lambda c: c.get("population", 0) or 0, reverse=True
            )
            top_communes = communes_sorted[:30]

            for commune in top_communes:
                code_insee = commune.get("code", "")
                nom = commune.get("nom", "")
                if not code_insee:
                    continue

                stats = await self._get_commune_stats(client, code_insee)
                if not stats or stats.get("nb_mutations", 0) == 0:
                    continue

                # Create commune territory actor
                com_ext = f"INSEE:{code_insee}"
                if com_ext not in actors:
                    actors[com_ext] = {
                        "id": str(_actor_id("territory", com_ext)),
                        "type": "territory",
                        "external_id": com_ext,
                        "name": nom,
                        "department_code": department_code,
                        "metadata": {
                            "insee": code_insee,
                            "population": commune.get("population", 0),
                        },
                    }

                # Enrich with DVF stats
                actors[com_ext]["metadata"]["dvf"] = stats

                # Relation: commune → department (territory_immo_activity)
                rel_id = _relation_id(com_ext, dept_ext, f"territory_immo_activity:{code_insee}")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": com_ext,
                        "target_actor_external_id": dept_ext,
                        "relation_type": "structural",
                        "subtype": "territory_immo_activity",
                        "confidence": 0.85,
                        "weight": min(stats.get("nb_mutations", 0) / 500.0, 5.0),
                        "evidence": {
                            "source": "dvf",
                            "code_insee": code_insee,
                            "nb_mutations": stats.get("nb_mutations", 0),
                            "prix_median": stats.get("prix_median"),
                            "prix_m2_median": stats.get("prix_m2_median"),
                            "nb_vefa": stats.get("nb_vefa", 0),
                            "annee": stats.get("annee", ""),
                        },
                        "source_type": "dvf",
                        "source_ref": f"dvf:{code_insee}:{stats.get('annee', '')}",
                    }
                )

        logger.info(
            "DVFExtractor dept={}: {} actors, {} relations",
            department_code,
            len(actors),
            len(relations),
        )
        return {"actors": list(actors.values()), "relations": relations}

    async def _get_communes(
        self, client: httpx.AsyncClient, department_code: str
    ) -> list[dict[str, Any]]:
        """Get list of communes in a department from geo.api.gouv.fr."""
        try:
            resp = await client.get(
                f"{self._GEO_API}/{department_code}/communes",
                params={"fields": "code,nom,population"},
            )
            if resp.status_code != 200:
                return []
            return resp.json()
        except Exception as e:
            logger.error("Geo API error for dept {}: {}", department_code, e)
            return []

    async def _get_commune_stats(
        self, client: httpx.AsyncClient, code_insee: str
    ) -> dict[str, Any] | None:
        """Get DVF statistics for a single commune (latest year)."""
        try:
            resp = await client.get(
                self._API_URL,
                params={
                    "code_insee": code_insee,
                    "anneemut_min": "2023",
                    "anneemut_max": "2024",
                    "page_size": 500,
                },
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
        except Exception as e:
            logger.debug("DVF API error for {}: {}", code_insee, e)
            return None

        results = data.get("results", [])
        if not results:
            return None

        # Compute basic stats from raw mutations
        prices: list[float] = []
        prices_m2: list[float] = []
        nb_vefa = 0
        for mut in results:
            try:
                val = float(mut.get("valeurfonc") or 0)
                surface = float(mut.get("sbati") or 0)
            except (ValueError, TypeError):
                continue
            if val > 0:
                prices.append(val)
                if surface > 0:
                    prices_m2.append(val / surface)
            if mut.get("vefa"):
                nb_vefa += 1

        if not prices:
            return None

        prices.sort()
        median_idx = len(prices) // 2
        prix_median = prices[median_idx]

        prix_m2_median = None
        if prices_m2:
            prices_m2.sort()
            prix_m2_median = round(prices_m2[len(prices_m2) // 2], 2)

        return {
            "nb_mutations": len(results),
            "prix_median": round(prix_median, 2),
            "prix_m2_median": prix_m2_median,
            "prix_min": round(min(prices), 2),
            "prix_max": round(max(prices), 2),
            "nb_vefa": nb_vefa,
            "annee": "2023-2024",
        }


# ---------------------------------------------------------------------------
# France Travail -- employment data (offres d'emploi + La Bonne Boîte)
# ---------------------------------------------------------------------------


class FranceTravailExtractor(BaseExtractor):
    """Extract employment dynamics from France Travail APIs.

    Requires OAuth2 credentials (FRANCE_TRAVAIL_CLIENT_ID / SECRET).
    Creates two relation types:
    - ``sector_employment_tension``: aggregated job offer counts by ROME code
      per department, showing which sectors are actively recruiting.
    - ``enterprise_recruits_sector``: enterprises identified by La Bonne Boîte
      as likely to hire (hidden job market), linked to the territory via SIRET.
    """

    source_name = "france_travail"

    # GPS centroids for major communes per department (used for La Bonne Boîte)
    _DEPT_CENTROIDS: dict[str, tuple[float, float]] = {
        "01": (46.2044, 5.2257),  # Bourg-en-Bresse
        "13": (43.2965, 5.3698),  # Marseille
        "31": (43.6047, 1.4442),  # Toulouse
        "33": (44.8378, -0.5792),  # Bordeaux
        "34": (43.6108, 3.8767),  # Montpellier
        "59": (50.6292, 3.0573),  # Lille
        "69": (45.7640, 4.8357),  # Lyon
        "75": (48.8566, 2.3522),  # Paris
        "92": (48.8924, 2.2360),  # Hauts-de-Seine
        "93": (48.9100, 2.4800),  # Seine-Saint-Denis
        "94": (48.7800, 2.4600),  # Val-de-Marne
        "06": (43.7102, 7.2620),  # Nice
        "44": (47.2184, -1.5536),  # Nantes
        "67": (48.5734, 7.7521),  # Strasbourg
        "2A": (41.9193, 8.7386),  # Ajaccio
        "2B": (42.6970, 9.4503),  # Bastia
        "974": (-20.8789, 55.4481),  # La Réunion
    }

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        # Lazy import to avoid circular / top-level import issues
        from src.infrastructure.datasources.adapters.france_travail import (
            FranceTravailAdapter,
        )
        from src.infrastructure.datasources.base import AdapterConfig

        adapter = FranceTravailAdapter(
            AdapterConfig(
                name="france_travail",
                base_url="https://api.francetravail.io/partenaire",
            )
        )

        if not adapter.has_credentials:
            logger.warning("FranceTravailExtractor: OAuth2 credentials not configured, skipping")
            return {"actors": [], "relations": []}

        # Territory actor for the department
        dept_ext = f"DEPT:{department_code}"
        dept_name = _DEPT_NAMES.get(department_code, department_code)
        actors[dept_ext] = {
            "id": str(_actor_id("territory", dept_ext)),
            "type": "territory",
            "external_id": dept_ext,
            "name": dept_name,
            "department_code": department_code,
            "metadata": {},
        }

        # ------------------------------------------------------------------
        # Part 1 : Job offers aggregated by ROME code
        # ------------------------------------------------------------------
        offres = await self._fetch_offres(adapter, department_code)
        rome_agg = self._aggregate_by_rome(offres)

        for rome_code, info in rome_agg.items():
            # Create a "sector" actor per ROME code
            sector_ext = f"ROME:{rome_code}"
            if sector_ext not in actors:
                actors[sector_ext] = {
                    "id": str(_actor_id("sector", sector_ext)),
                    "type": "sector",
                    "external_id": sector_ext,
                    "name": info["libelle"],
                    "department_code": department_code,
                    "metadata": {
                        "rome_code": rome_code,
                        "nb_offres": info["count"],
                        "contrats": info["contrats"],
                    },
                }

            # Relation: sector → department (employment tension)
            rel_id = _relation_id(sector_ext, dept_ext, f"sector_employment_tension:{rome_code}")
            relations.append(
                {
                    "id": str(rel_id),
                    "source_actor_external_id": sector_ext,
                    "target_actor_external_id": dept_ext,
                    "relation_type": "structural",
                    "subtype": "sector_employment_tension",
                    "confidence": 0.90,
                    "weight": min(info["count"] / 20.0, 5.0),
                    "evidence": {
                        "source": "france_travail",
                        "rome_code": rome_code,
                        "rome_libelle": info["libelle"],
                        "nb_offres": info["count"],
                        "contrats": info["contrats"],
                        "sample_intitules": info["intitules"][:5],
                    },
                    "source_type": "france_travail",
                    "source_ref": f"ft:offres:{department_code}:{rome_code}",
                }
            )

        # ------------------------------------------------------------------
        # Part 2 : La Bonne Boîte -- enterprises likely to hire
        # ------------------------------------------------------------------
        top_rome = sorted(rome_agg.items(), key=lambda x: x[1]["count"], reverse=True)[:5]
        centroid = self._DEPT_CENTROIDS.get(department_code)

        if centroid and top_rome:
            lat, lon = centroid
            for rome_code, info in top_rome:
                companies = await self._fetch_lbb(adapter, lat, lon, rome_code)
                for comp in companies:
                    siret = comp.get("siret")
                    if not siret:
                        continue

                    ent_ext = f"SIRET:{siret}"
                    if ent_ext not in actors:
                        actors[ent_ext] = {
                            "id": str(_actor_id("enterprise", ent_ext)),
                            "type": "enterprise",
                            "external_id": ent_ext,
                            "name": comp.get("nom") or siret,
                            "department_code": department_code,
                            "metadata": {
                                "siret": siret,
                                "naf": comp.get("naf"),
                                "effectif": comp.get("effectif"),
                                "source": "la_bonne_boite",
                            },
                        }

                    # Relation: enterprise → sector (recruits in this ROME)
                    sector_ext = f"ROME:{rome_code}"
                    rel_id = _relation_id(
                        ent_ext,
                        sector_ext,
                        f"enterprise_recruits_sector:{siret}:{rome_code}",
                    )
                    relations.append(
                        {
                            "id": str(rel_id),
                            "source_actor_external_id": ent_ext,
                            "target_actor_external_id": sector_ext,
                            "relation_type": "structural",
                            "subtype": "enterprise_recruits_sector",
                            "confidence": min(0.5 + (comp.get("score_embauche") or 0) * 0.5, 1.0),
                            "weight": min((comp.get("score_embauche") or 0) * 3.0, 5.0),
                            "evidence": {
                                "source": "la_bonne_boite",
                                "siret": siret,
                                "rome_code": rome_code,
                                "score_embauche": comp.get("score_embauche"),
                                "effectif": comp.get("effectif"),
                                "distance_km": comp.get("distance_km"),
                            },
                            "source_type": "france_travail",
                            "source_ref": f"ft:lbb:{siret}:{rome_code}",
                        }
                    )

        logger.info(
            "FranceTravailExtractor dept={}: {} actors, {} relations "
            "(offres ROME: {}, LBB companies: {})",
            department_code,
            len(actors),
            len(relations),
            len(rome_agg),
            sum(
                1
                for a in actors.values()
                if a.get("metadata", {}).get("source") == "la_bonne_boite"
            ),
        )
        return {"actors": list(actors.values()), "relations": relations}

    async def _fetch_offres(self, adapter: Any, department_code: str) -> list[dict[str, Any]]:
        """Fetch job offers for a department (up to 149, API max per call)."""
        try:
            results = await adapter.search_offres(
                departement=department_code,
                limit=149,
            )
            # Filter out error dicts
            return [r for r in results if "error" not in r]
        except Exception as e:
            logger.error("FranceTravail offres error dept={}: {}", department_code, e)
            return []

    async def _fetch_lbb(
        self, adapter: Any, lat: float, lon: float, rome: str
    ) -> list[dict[str, Any]]:
        """Fetch La Bonne Boîte companies for a ROME code around coordinates."""
        try:
            return await adapter.search_la_bonne_boite(
                latitude=lat,
                longitude=lon,
                rome=rome,
                distance=30,
                limit=10,
            )
        except Exception as e:
            logger.debug("LBB error rome={}: {}", rome, e)
            return []

    @staticmethod
    def _aggregate_by_rome(offres: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Aggregate job offers by ROME code."""
        agg: dict[str, dict[str, Any]] = {}
        for o in offres:
            rome = o.get("rome", {})
            rome_code = rome.get("code") if isinstance(rome, dict) else None
            if not rome_code:
                continue
            if rome_code not in agg:
                agg[rome_code] = {
                    "libelle": rome.get("libelle") or rome_code,
                    "count": 0,
                    "contrats": {},
                    "intitules": [],
                }
            agg[rome_code]["count"] += 1
            # Track contract type distribution
            ct = o.get("contrat", {}).get("type") or "inconnu"
            agg[rome_code]["contrats"][ct] = agg[rome_code]["contrats"].get(ct, 0) + 1
            # Keep sample intitulés
            if len(agg[rome_code]["intitules"]) < 10:
                titre = o.get("intitule") or ""
                if titre and titre not in agg[rome_code]["intitules"]:
                    agg[rome_code]["intitules"].append(titre)
        return agg


# ---------------------------------------------------------------------------
# INSEE Local -- demographics, population, unemployment
# ---------------------------------------------------------------------------


class INSEELocalExtractor(BaseExtractor):
    """Extract demographic and socio-economic data from INSEE / geo.api.gouv.fr.

    Creates ``territory_demographics`` relations linking each commune to its
    department with population, density, and surface data.  When INSEE OAuth2
    credentials are available, also enriches the department actor with the
    official unemployment rate from the BDM quarterly survey.

    No authentication required for basic demographic data (geo.api.gouv.fr).
    INSEE OAuth2 needed only for unemployment rates.
    """

    source_name = "insee_local"

    _GEO_API = "https://geo.api.gouv.fr/departements"

    async def extract(self, department_code: str) -> dict[str, list[dict[str, Any]]]:
        actors: dict[str, dict[str, Any]] = {}
        relations: list[dict[str, Any]] = []

        # Department territory actor
        dept_ext = f"DEPT:{department_code}"
        dept_name = _DEPT_NAMES.get(department_code, department_code)
        actors[dept_ext] = {
            "id": str(_actor_id("territory", dept_ext)),
            "type": "territory",
            "external_id": dept_ext,
            "name": dept_name,
            "department_code": department_code,
            "metadata": {},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # ------------------------------------------------------------------
            # Part 1: Commune demographics from geo.api.gouv.fr (free, no auth)
            # ------------------------------------------------------------------
            communes = await self._fetch_communes(client, department_code)
            total_pop = 0
            total_surface_km2 = 0.0

            for c in communes:
                code_insee = c.get("code", "")
                nom = c.get("nom", "")
                population = c.get("population") or 0
                surface_ha = c.get("surface") or 0
                surface_km2 = surface_ha / 100.0
                density = population / max(1.0, surface_km2)
                centre = c.get("centre", {})
                coords = centre.get("coordinates", [0, 0]) if centre else [0, 0]

                total_pop += population
                total_surface_km2 += surface_km2

                if not code_insee or population == 0:
                    continue

                # Commune actor
                com_ext = f"INSEE:{code_insee}"
                if com_ext not in actors:
                    actors[com_ext] = {
                        "id": str(_actor_id("territory", com_ext)),
                        "type": "territory",
                        "external_id": com_ext,
                        "name": nom,
                        "department_code": department_code,
                        "metadata": {
                            "insee": code_insee,
                            "population": population,
                            "surface_km2": round(surface_km2, 1),
                            "density": round(density, 1),
                            "lat": coords[1] if len(coords) > 1 else None,
                            "lon": coords[0] if coords else None,
                        },
                    }

                # Relation: commune → department (demographics)
                rel_id = _relation_id(com_ext, dept_ext, f"territory_demographics:{code_insee}")
                relations.append(
                    {
                        "id": str(rel_id),
                        "source_actor_external_id": com_ext,
                        "target_actor_external_id": dept_ext,
                        "relation_type": "structural",
                        "subtype": "territory_demographics",
                        "confidence": 0.95,
                        "weight": min(population / 50000.0, 5.0),
                        "evidence": {
                            "source": "insee_local",
                            "code_insee": code_insee,
                            "population": population,
                            "surface_km2": round(surface_km2, 1),
                            "density": round(density, 1),
                        },
                        "source_type": "insee_local",
                        "source_ref": f"insee:{code_insee}:demographics",
                    }
                )

            # Enrich department metadata
            actors[dept_ext]["metadata"]["population_totale"] = total_pop
            actors[dept_ext]["metadata"]["surface_km2"] = round(total_surface_km2, 1)
            actors[dept_ext]["metadata"]["nb_communes"] = len(communes)
            actors[dept_ext]["metadata"]["density"] = round(
                total_pop / max(1.0, total_surface_km2), 1
            )

            # ------------------------------------------------------------------
            # Part 2: Unemployment rate from INSEE BDM (requires OAuth2)
            # ------------------------------------------------------------------
            unemployment = await self._fetch_unemployment(department_code)
            if unemployment is not None:
                actors[dept_ext]["metadata"]["unemployment_rate"] = unemployment

        logger.info(
            "INSEELocalExtractor dept={}: {} actors, {} relations, pop={:,}, communes={}",
            department_code,
            len(actors),
            len(relations),
            total_pop,
            len(communes),
        )
        return {"actors": list(actors.values()), "relations": relations}

    async def _fetch_communes(
        self, client: httpx.AsyncClient, department_code: str
    ) -> list[dict[str, Any]]:
        """Fetch commune list with population/surface from geo.api.gouv.fr."""
        try:
            resp = await client.get(
                f"{self._GEO_API}/{department_code}/communes",
                params={"fields": "nom,code,population,surface,centre"},
            )
            if resp.status_code != 200:
                return []
            return resp.json()
        except Exception as e:
            logger.error("Geo API communes error for dept {}: {}", department_code, e)
            return []

    async def _fetch_unemployment(self, department_code: str) -> float | None:
        """Fetch unemployment rate using the INSEE Local adapter (OAuth2)."""
        try:
            from src.infrastructure.datasources.adapters.insee_local import (
                INSEELocalAdapter,
            )

            adapter = INSEELocalAdapter()
            rate = await adapter.get_unemployment_rate(department_code)
            if rate is not None:
                logger.debug(
                    "INSEELocalExtractor: unemployment rate for dept {}: {}%",
                    department_code,
                    rate,
                )
            return rate
        except Exception as e:
            logger.debug("INSEELocalExtractor: unemployment fetch failed: {}", e)
            return None


# ---------------------------------------------------------------------------
# Registry -- maps source name to extractor class
# ---------------------------------------------------------------------------

EXTRACTORS: dict[str, type[BaseExtractor]] = {
    "sirene": SireneExtractor,
    "bodacc": BodaccExtractor,
    "nature_juridique": NatureJuridiqueExtractor,
    "boamp": BoampExtractor,
    "rna": RnaExtractor,
    "subventions": SubventionsExtractor,
    "epci": EPCIExtractor,
    "incubator": IncubatorExtractor,
    "poles": PolesExtractor,
    "territorial": TerritorialStructuresExtractor,
    "sirene_enrich": SireneAddressEnricher,
    "sirene_dirigeants": SireneDirigeantsEnricher,
    "urssaf": UrssafEffectifsEnricher,
    "ademe": ADEMEExtractor,
    "qualiopi": QualiopiExtractor,
    "ofgl": OFGLExtractor,
    "dvf": DVFExtractor,
    "france_travail": FranceTravailExtractor,
    "insee_local": INSEELocalExtractor,
}
