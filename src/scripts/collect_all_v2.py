#!/usr/bin/env python3
"""Collecteur unifié Tawiza V2 — Toutes sources vers table `signals`.

Sources :
  1. BODACC (liquidations, créations, modifications)
  2. France Travail (offres d'emploi)
  3. SIRENE (créations d'entreprises via data.gouv.fr)
  4. INSEE (chômage via BDM, population via geo.api)
  5. OFGL (finances locales)
  6. DVF (transactions immobilières via data.gouv.fr)
  7. Banque de France (défaillances)
  8. Presse locale (RSS)
  
Tout est inséré dans la table `signals` unifiée.
"""

import asyncio
import base64
import json
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Départements
ALL_DEPTS = [f"{i:02d}" for i in range(1, 96) if i != 20] + ["2A", "2B"] + ["971", "972", "973", "974", "976"]

@dataclass
class Signal:
    """Un signal brut à insérer en base."""
    source: str
    metric_name: str
    code_dept: str
    metric_value: float | None = None
    event_date: date | None = None
    code_commune: str | None = None
    signal_type: str | None = None
    confidence: float | None = None
    source_url: str | None = None
    raw_data: dict | None = None
    extracted_text: str | None = None
    entities: dict | None = None

@dataclass 
class CollectStats:
    """Statistiques de collecte."""
    source: str
    collected: int = 0
    errors: int = 0
    skipped: int = 0
    details: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# BODACC — Annonces légales (créations, liquidations, modifications)
# ═══════════════════════════════════════════════════════════════

async def collect_bodacc(client: httpx.AsyncClient, depts: list[str], days_back: int = 30) -> tuple[list[Signal], CollectStats]:
    """Collecte BODACC via API bodacc-datadila."""
    stats = CollectStats(source="bodacc")
    signals = []
    
    base_url = "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records"
    
    for dept in depts:
        try:
            for famille, signal_label in [
                ("Créations", "creation_entreprise"),
                ("Ventes et cessions", "vente_cession"),
                ("Procédures collectives", "procedure_collective"),
                ("Radiations", "radiation"),
                ("Immatriculations", "immatriculation"),
            ]:
                resp = await client.get(base_url, params={
                    "limit": 100,
                    "where": f"numerodepartement='{dept}' AND familleavis_lib='{famille}' AND dateparution >= date'{(datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')}'",
                    "order_by": "dateparution DESC",
                })
                
                if resp.status_code == 200:
                    data = resp.json()
                    records = data.get("results", [])
                    
                    for rec in records:
                        # Affiner le type pour les procédures collectives
                        contenu = str(rec.get("jugement", "") or "") + str(rec.get("acte", "") or "")
                        if signal_label == "procedure_collective":
                            if "liquidation" in contenu.lower():
                                metric = "liquidation_judiciaire"
                            elif "redressement" in contenu.lower():
                                metric = "redressement_judiciaire"
                            elif "sauvegarde" in contenu.lower():
                                metric = "sauvegarde"
                            else:
                                metric = "procedure_collective"
                        else:
                            metric = signal_label
                        
                        signals.append(Signal(
                            source="bodacc",
                            metric_name=metric,
                            code_dept=dept,
                            event_date=datetime.strptime(rec.get("dateparution", "")[:10], "%Y-%m-%d").date() if rec.get("dateparution") else None,
                            signal_type="event",
                            confidence=0.95,
                            source_url=f"https://www.bodacc.fr/annonce/{rec.get('id_annonce', '')}",
                            raw_data=rec,
                            extracted_text=contenu[:500],
                        ))
                        stats.collected += 1
                    
                await asyncio.sleep(0.2)
                
        except Exception as e:
            logger.error(f"BODACC {dept}: {e}")
            stats.errors += 1
    
    logger.info(f"📋 BODACC: {stats.collected} annonces, {stats.errors} erreurs")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# FRANCE TRAVAIL — Offres d'emploi
# ═══════════════════════════════════════════════════════════════

async def get_ft_token(client: httpx.AsyncClient) -> str | None:
    """OAuth2 token France Travail."""
    client_id = os.getenv("FRANCE_TRAVAIL_CLIENT_ID")
    client_secret = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.error("❌ Pas de credentials France Travail")
        return None
    
    try:
        resp = await client.post(
            "https://entreprise.francetravail.fr/connexion/oauth2/access_token",
            params={"realm": "/partenaire"},
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "api_offresdemploiv2 o2dsoffre",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
    except Exception as e:
        logger.error(f"❌ Token FT: {e}")
        return None


async def collect_france_travail(client: httpx.AsyncClient, depts: list[str], max_per_dept: int = 50) -> tuple[list[Signal], CollectStats]:
    """Collecte offres France Travail."""
    stats = CollectStats(source="france_travail")
    signals = []
    
    token = await get_ft_token(client)
    if not token:
        return signals, stats
    
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    for dept in depts:
        try:
            resp = await client.get(
                "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search",
                headers=headers,
                params={
                    "departement": dept,
                    "range": f"0-{min(max_per_dept, 149)}",
                    "sort": 1,  # par date
                },
            )
            
            if resp.status_code in (200, 206):
                data = resp.json()
                offres = data.get("resultats", [])
                
                for offre in offres:
                    # Extraire le salaire
                    salaire = offre.get("salaire", {})
                    salaire_val = None
                    if salaire.get("libelle"):
                        try:
                            # Tenter d'extraire un nombre
                            import re
                            nums = re.findall(r'[\d]+(?:[.,]\d+)?', salaire["libelle"].replace(" ", ""))
                            if nums:
                                salaire_val = float(nums[0].replace(",", "."))
                        except Exception:
                            pass
                    
                    type_contrat = offre.get("typeContrat", "")
                    
                    signals.append(Signal(
                        source="france_travail",
                        metric_name=f"offre_emploi_{type_contrat.lower()}" if type_contrat else "offre_emploi",
                        code_dept=dept,
                        metric_value=salaire_val,
                        event_date=datetime.fromisoformat(offre["dateCreation"][:10]).date() if offre.get("dateCreation") else None,
                        signal_type="event",
                        confidence=0.9,
                        source_url=offre.get("origineOffre", {}).get("urlOrigine"),
                        raw_data={
                            "id": offre.get("id"),
                            "intitule": offre.get("intitule"),
                            "typeContrat": type_contrat,
                            "qualitesProfessionnelles": [q.get("libelle") for q in offre.get("qualitesProfessionnelles", [])],
                            "secteurActivite": offre.get("secteurActivite"),
                            "experienceExige": offre.get("experienceExige"),
                        },
                        extracted_text=offre.get("intitule", ""),
                    ))
                    stats.collected += 1
                
            elif resp.status_code == 429:
                logger.warning(f"  FT {dept}: rate limited, pause...")
                await asyncio.sleep(5)
            else:
                logger.debug(f"  FT {dept}: HTTP {resp.status_code}")
                stats.errors += 1
            
            await asyncio.sleep(0.3)
            
        except Exception as e:
            logger.error(f"FT {dept}: {e}")
            stats.errors += 1
    
    logger.info(f"💼 France Travail: {stats.collected} offres, {stats.errors} erreurs")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# SIRENE — Créations d'entreprises (data.gouv.fr StockEtablissement)
# ═══════════════════════════════════════════════════════════════

async def collect_sirene(client: httpx.AsyncClient, depts: list[str], months_back: int = 3) -> tuple[list[Signal], CollectStats]:
    """Collecte créations via API SIRENE publique (recherche.entreprises.api.gouv.fr)."""
    stats = CollectStats(source="sirene")
    signals = []
    
    date_min = (datetime.now() - timedelta(days=months_back * 30)).strftime("%Y-%m-%d")
    
    for dept in depts:
        try:
            resp = await client.get(
                "https://recherche-entreprises.api.gouv.fr/search",
                params={
                    "departement": dept,
                    "date_creation_min": date_min,
                    "per_page": 25,
                    "page": 1,
                },
                timeout=15,
            )
            
            if resp.status_code == 200:
                data = resp.json()
                total = data.get("total_results", 0)
                results = data.get("results", [])
                
                # Signal agrégé : nombre de créations
                signals.append(Signal(
                    source="sirene",
                    metric_name="creations_entreprises_count",
                    code_dept=dept,
                    metric_value=float(total),
                    event_date=date.today(),
                    signal_type="metric",
                    confidence=0.95,
                    raw_data={"total": total, "date_min": date_min, "sample_size": len(results)},
                ))
                stats.collected += 1
                
                # Signaux individuels (échantillon)
                for ent in results[:10]:
                    naf = ent.get("activite_principale", "")
                    signals.append(Signal(
                        source="sirene",
                        metric_name=f"creation_entreprise_{naf}" if naf else "creation_entreprise",
                        code_dept=dept,
                        event_date=datetime.strptime(ent["date_creation"], "%Y-%m-%d").date() if ent.get("date_creation") else None,
                        signal_type="event",
                        confidence=0.9,
                        raw_data={
                            "siren": ent.get("siren"),
                            "nom": ent.get("nom_complet"),
                            "naf": naf,
                            "nature_juridique": ent.get("nature_juridique"),
                            "tranche_effectif": ent.get("tranche_effectif_salarie"),
                        },
                    ))
                    stats.collected += 1
            else:
                logger.debug(f"  SIRENE {dept}: HTTP {resp.status_code}")
                stats.errors += 1
            
            await asyncio.sleep(0.3)
            
        except Exception as e:
            logger.error(f"SIRENE {dept}: {e}")
            stats.errors += 1
    
    logger.info(f"🏢 SIRENE: {stats.collected} signaux, {stats.errors} erreurs")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# INSEE — Chômage + Population
# ═══════════════════════════════════════════════════════════════

async def get_insee_token(client: httpx.AsyncClient) -> str | None:
    """OAuth2 token INSEE."""
    client_key = os.getenv("INSEE_CLIENT_ID")
    client_secret = os.getenv("INSEE_CLIENT_SECRET")
    if not client_key or not client_secret:
        logger.warning("⚠️ Pas de credentials INSEE — utilisation geo.api uniquement")
        return None
    
    try:
        credentials = base64.b64encode(f"{client_key}:{client_secret}".encode()).decode()
        resp = await client.post(
            "https://api.insee.fr/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        logger.info("✅ Token INSEE obtenu")
        return token
    except Exception as e:
        logger.warning(f"⚠️ Token INSEE échoué: {e}")
        return None


async def collect_insee(client: httpx.AsyncClient, depts: list[str]) -> tuple[list[Signal], CollectStats]:
    """Collecte INSEE : population + chômage."""
    stats = CollectStats(source="insee")
    signals = []
    
    # 1. Population via geo.api.gouv.fr (gratuit, pas d'auth)
    # L'API département ne retourne pas toujours 'population', on utilise les communes
    logger.info("  👥 Population via geo.api.gouv.fr")
    for dept in depts:
        try:
            # Récupérer toutes les communes du département et sommer la population
            resp = await client.get(
                f"https://geo.api.gouv.fr/departements/{dept}/communes",
                params={"fields": "nom,code,population,codesPostaux"},
                timeout=15,
            )
            if resp.status_code == 200:
                communes = resp.json()
                total_pop = sum(c.get("population", 0) for c in communes if c.get("population"))
                nb_communes = len(communes)
                
                if total_pop > 0:
                    signals.append(Signal(
                        source="insee",
                        metric_name="population",
                        code_dept=dept,
                        metric_value=float(total_pop),
                        event_date=date.today(),
                        signal_type="metric",
                        confidence=0.99,
                        raw_data={"nb_communes": nb_communes, "total_population": total_pop},
                    ))
                    stats.collected += 1
                    
                    # Aussi : densité de communes (indicateur d'urbanisation)
                    signals.append(Signal(
                        source="insee",
                        metric_name="nb_communes",
                        code_dept=dept,
                        metric_value=float(nb_communes),
                        event_date=date.today(),
                        signal_type="metric",
                        confidence=0.99,
                    ))
                    stats.collected += 1
                    
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.debug(f"  Geo {dept}: {e}")
            stats.errors += 1
    
    # 2. Chômage via INSEE BDM (si token dispo)
    token = await get_insee_token(client)
    if token:
        logger.info("  📊 Chômage via INSEE BDM")
        # Série nationale du chômage localisé trimestriel
        # On utilise l'API SDMX pour récupérer les séries par département
        try:
            resp = await client.get(
                "https://api.insee.fr/series/BDM/V1/data/SERIES_BDM/001688370,001688371,001688375,001688382,001688400,001688402,001688404,001688413,001688428,001688436,001688438,001688444,001688462,001688463",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                # Parse SDMX-JSON
                try:
                    datasets = data.get("dataSets", [])
                    if datasets:
                        series_map = datasets[0].get("series", {})
                        # Map series index to dept codes
                        dept_codes = ["01", "02", "06", "13", "31", "33", "35", "44", "59", "67", "69", "75", "93", "94"]
                        for idx, (key, val) in enumerate(series_map.items()):
                            obs = val.get("observations", {})
                            if obs:
                                # Get last observation
                                last_key = max(obs.keys(), key=int)
                                last_val = obs[last_key]
                                if last_val and last_val[0] is not None:
                                    dept_code = dept_codes[idx] if idx < len(dept_codes) else f"?{idx}"
                                    signals.append(Signal(
                                        source="insee",
                                        metric_name="taux_chomage_trimestriel",
                                        code_dept=dept_code,
                                        metric_value=float(last_val[0]),
                                        event_date=date.today(),
                                        signal_type="metric",
                                        confidence=0.95,
                                        raw_data={"series_key": key, "period_index": last_key},
                                    ))
                                    stats.collected += 1
                except Exception as e:
                    logger.warning(f"  Parse BDM: {e}")
            else:
                logger.warning(f"  INSEE BDM HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"  INSEE BDM: {e}")
    
    logger.info(f"📈 INSEE: {stats.collected} signaux, {stats.errors} erreurs")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# OFGL — Finances des collectivités
# ═══════════════════════════════════════════════════════════════

async def collect_ofgl(client: httpx.AsyncClient, depts: list[str]) -> tuple[list[Signal], CollectStats]:
    """Collecte OFGL : finances locales."""
    stats = CollectStats(source="ofgl")
    signals = []
    
    # OFGL : dataset départements a des agrégats (Dépenses totales, Recettes totales, etc.)
    # Chaque ligne = 1 département × 1 agrégat. On récupère les agrégats clés.
    agregats_cles = [
        "Dépenses totales",
        "Recettes totales", 
        "Encours de dette au 31/12",
        "Capacité d'autofinancement brute",
        "Dépenses d'investissement hors remboursements",
    ]
    
    for year in [2023, 2022]:
        found_data = False
        for agregat in agregats_cles:
            try:
                # Paginer pour avoir tous les départements
                resp = await client.get(
                    "https://data.ofgl.fr/api/explore/v2.1/catalog/datasets/ofgl-base-departements-consolidee/records",
                    params={
                        "limit": 100,
                        "refine": f"exer:{year}",
                        "where": f"agregat='{agregat}'",
                        "select": "dep_code, dep_name, agregat, montant, euros_par_habitant, ptot",
                    },
                    timeout=30,
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    records = data.get("results", [])
                    
                    if records:
                        found_data = True
                        metric_name = agregat.lower().replace(" ", "_").replace("'", "").replace("/", "")
                        
                        for rec in records:
                            dept_code = rec.get("dep_code", "")
                            if not dept_code or dept_code not in depts:
                                continue
                            
                            montant = rec.get("montant")
                            eur_hab = rec.get("euros_par_habitant")
                            
                            if montant:
                                signals.append(Signal(
                                    source="ofgl",
                                    metric_name=f"finances_{metric_name}",
                                    code_dept=dept_code,
                                    metric_value=float(montant),
                                    event_date=date(year, 12, 31),
                                    signal_type="metric",
                                    confidence=0.95,
                                    raw_data={
                                        "agregat": agregat,
                                        "dep_name": rec.get("dep_name"),
                                        "euros_par_habitant": eur_hab,
                                        "population": rec.get("ptot"),
                                        "annee": year,
                                    },
                                ))
                                stats.collected += 1
                        
                        logger.info(f"  ✅ OFGL {agregat} {year}: {len(records)} depts")
                
            except Exception as e:
                logger.error(f"  OFGL {agregat}: {e}")
                stats.errors += 1
        
        if found_data:
            break  # Got data for this year
    
    logger.info(f"💰 OFGL: {stats.collected} signaux, {stats.errors} erreurs")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# DVF — Transactions immobilières (data.gouv.fr)
# ═══════════════════════════════════════════════════════════════

async def collect_dvf(client: httpx.AsyncClient, depts: list[str], year: int = 2024) -> tuple[list[Signal], CollectStats]:
    """Collecte DVF via CSV data.gouv.fr (fichiers géo-DVF)."""
    import csv
    import gzip
    import io
    
    stats = CollectStats(source="dvf")
    signals = []
    
    for dept in depts:
        try:
            # Télécharger le CSV gzippé pour le département
            url = f"https://files.data.gouv.fr/geo-dvf/latest/csv/{year}/departements/{dept}.csv.gz"
            resp = await client.get(url, timeout=30)
            
            if resp.status_code == 404 and year == 2024:
                # Fallback année précédente
                url = f"https://files.data.gouv.fr/geo-dvf/latest/csv/2023/departements/{dept}.csv.gz"
                resp = await client.get(url, timeout=30)
            
            if resp.status_code == 200:
                # Décompresser et parser le CSV
                raw = gzip.decompress(resp.content)
                text = raw.decode("utf-8")
                reader = csv.DictReader(io.StringIO(text))
                
                rows = []
                for row in reader:
                    rows.append(row)
                
                # Prendre un échantillon des dernières transactions + stats agrégées
                ventes = [r for r in rows if r.get("nature_mutation") == "Vente" and r.get("valeur_fonciere")]
                
                if ventes:
                    # Stats agrégées par département
                    prix_list = []
                    for v in ventes:
                        try:
                            val = float(v["valeur_fonciere"])
                            surf = float(v.get("surface_reelle_bati") or 0)
                            if val > 0 and surf > 10:
                                prix_list.append(val / surf)
                        except (ValueError, ZeroDivisionError):
                            pass
                    
                    if prix_list:
                        import statistics
                        signals.append(Signal(
                            source="dvf",
                            metric_name="prix_m2_median",
                            code_dept=dept,
                            metric_value=round(statistics.median(prix_list), 2),
                            event_date=date.today(),
                            signal_type="metric",
                            confidence=0.95,
                            raw_data={
                                "nb_transactions": len(ventes),
                                "nb_avec_prix_m2": len(prix_list),
                                "mean": round(statistics.mean(prix_list), 2),
                                "median": round(statistics.median(prix_list), 2),
                                "stdev": round(statistics.stdev(prix_list), 2) if len(prix_list) > 1 else 0,
                                "year": year,
                            },
                        ))
                        stats.collected += 1
                    
                    # Signal nombre de transactions
                    signals.append(Signal(
                        source="dvf",
                        metric_name="nb_transactions_immobilieres",
                        code_dept=dept,
                        metric_value=float(len(ventes)),
                        event_date=date.today(),
                        signal_type="metric",
                        confidence=0.95,
                        raw_data={"year": year, "total_rows": len(rows)},
                    ))
                    stats.collected += 1
                    
                    # Dernières transactions individuelles (échantillon)
                    for v in ventes[-20:]:
                        try:
                            val = float(v["valeur_fonciere"])
                            surf = float(v.get("surface_reelle_bati") or 0)
                            prix_m2 = val / surf if surf > 10 else None
                        except (ValueError, ZeroDivisionError):
                            val = None
                            prix_m2 = None
                        
                        signals.append(Signal(
                            source="dvf",
                            metric_name="transaction_immobiliere",
                            code_dept=dept,
                            code_commune=v.get("code_commune", "")[:5] or None,
                            metric_value=prix_m2,
                            event_date=datetime.strptime(v["date_mutation"], "%Y-%m-%d").date() if v.get("date_mutation") else None,
                            signal_type="event",
                            confidence=0.95,
                            raw_data={
                                "valeur_fonciere": val,
                                "surface": surf if surf else None,
                                "type_local": v.get("type_local"),
                                "commune": v.get("nom_commune"),
                            },
                        ))
                        stats.collected += 1
                    
                    logger.info(f"  ✅ DVF {dept}: {len(ventes)} ventes, prix médian {round(statistics.median(prix_list), 0) if prix_list else '?'}€/m²")
            else:
                logger.debug(f"  DVF {dept}: HTTP {resp.status_code}")
                stats.skipped += 1
            
            await asyncio.sleep(0.2)
            
        except Exception as e:
            logger.error(f"  DVF {dept}: {e}")
            stats.errors += 1
    
    logger.info(f"🏠 DVF: {stats.collected} signaux, {stats.errors} erreurs")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# BANQUE DE FRANCE — Défaillances d'entreprises
# ═══════════════════════════════════════════════════════════════

async def collect_banque_france(client: httpx.AsyncClient) -> tuple[list[Signal], CollectStats]:
    """Collecte statistiques défaillances Banque de France via webstat API SDMX."""
    stats = CollectStats(source="banque_france")
    signals = []
    
    # Webstat BdF — SDMX REST API
    # Défaillances d'entreprises : série ESANE
    urls_to_try = [
        "https://webstat.banque-france.fr/api/v1/data/FM/M.FR.EUR.FR2.BB.DEFAILLANCES_CUMUL12M.E",
        "https://api.webstat.banque-france.fr/webstat-fr/v1/data/FM/M.FR.EUR.FR2.BB.DEFAILLANCES_CUMUL12M.E",
        # Alternative: open data BdF
        "https://www.banque-france.fr/sites/default/files/media/2024/defaillances-entreprises.json",
    ]
    
    for url in urls_to_try:
        try:
            resp = await client.get(url, headers={"Accept": "application/json"}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                
                # Essayer de parser selon le format
                if isinstance(data, list):
                    for item in data[-12:]:  # Derniers 12 mois
                        signals.append(Signal(
                            source="banque_france",
                            metric_name="defaillances_mensuelles",
                            code_dept="FR",
                            metric_value=float(item.get("value", item.get("valeur", 0))),
                            event_date=date.today(),
                            signal_type="metric",
                            confidence=0.98,
                            raw_data=item,
                        ))
                        stats.collected += 1
                elif isinstance(data, dict):
                    datasets = data.get("dataSets", [])
                    if datasets:
                        series = datasets[0].get("series", {})
                        for key, val in series.items():
                            obs = val.get("observations", {})
                            if obs:
                                last_key = max(obs.keys(), key=int)
                                last_val = obs[last_key]
                                if last_val and last_val[0] is not None:
                                    signals.append(Signal(
                                        source="banque_france",
                                        metric_name="defaillances_mensuelles",
                                        code_dept="FR",
                                        metric_value=float(last_val[0]),
                                        event_date=date.today(),
                                        signal_type="metric",
                                        confidence=0.98,
                                        raw_data={"series_key": key, "url": url},
                                    ))
                                    stats.collected += 1
                
                if stats.collected > 0:
                    logger.info(f"  ✅ BdF: {stats.collected} données depuis {url}")
                    break
            else:
                logger.debug(f"  BdF {url}: HTTP {resp.status_code}")
        except Exception as e:
            logger.debug(f"  BdF {url}: {e}")
    
    if stats.collected == 0:
        logger.warning("  ⚠️ Banque de France: aucune donnée récupérée (API instable)")
    
    logger.info(f"🏦 Banque de France: {stats.collected} signaux")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# PRESSE LOCALE — Flux RSS
# ═══════════════════════════════════════════════════════════════

RSS_FEEDS = {
    "france_bleu": "https://www.francebleu.fr/rss/infos.xml",
    "20minutes": "https://www.20minutes.fr/feeds/rss-actu-home.xml",
    "la_depeche": "https://www.ladepeche.fr/rss.xml",
    "le_telegramme": "https://www.letelegramme.fr/rss.xml",
    "sud_ouest": "https://www.sudouest.fr/rss.xml",
    "le_parisien": "https://www.leparisien.fr/arc/outboundfeeds/rss/economie.xml",
    "bfm_eco": "https://www.bfmtv.com/rss/economie/",
    "capital": "https://www.capital.fr/feeds/rss",
    "challenges": "https://www.challenges.fr/rss.xml",
    "france_info_eco": "https://www.francetvinfo.fr/economie.rss",
    "la_tribune": "https://www.latribune.fr/rss/rubriques/economie.html",
    "le_monde_eco": "https://www.lemonde.fr/economie/rss_full.xml",
    "liberation_eco": "https://www.liberation.fr/arc/outboundfeeds/rss/economie/?outputType=xml",
    "la_voix_du_nord": "https://www.lavoixdunord.fr/rss",
    "dna": "https://www.dna.fr/rss",
    "le_progres": "https://www.leprogres.fr/rss",
    "nice_matin": "https://www.nicematin.com/rss",
    "midi_libre": "https://www.midilibre.fr/rss.xml",
    "ouest_france": "https://www.ouest-france.fr/rss.xml",
    "paris_normandie": "https://www.paris-normandie.fr/rss",
}


async def collect_presse(client: httpx.AsyncClient) -> tuple[list[Signal], CollectStats]:
    """Collecte presse locale via RSS."""
    stats = CollectStats(source="presse_locale")
    signals = []
    
    keywords_eco = [
        "entreprise", "emploi", "chômage", "licenciement", "embauche",
        "usine", "fermeture", "ouverture", "investissement", "start-up",
        "commerce", "immobilier", "construction", "logement", "économie",
        "défaillance", "liquidation", "redressement", "plan social",
    ]
    
    for feed_name, feed_url in RSS_FEEDS.items():
        try:
            resp = await client.get(feed_url, timeout=10, follow_redirects=True)
            if resp.status_code != 200:
                logger.debug(f"  RSS {feed_name}: HTTP {resp.status_code}")
                stats.skipped += 1
                continue
            
            root = ET.fromstring(resp.text)
            items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
            
            for item in items[:50]:
                title = item.findtext("title", "") or item.findtext("{http://www.w3.org/2005/Atom}title", "")
                desc = item.findtext("description", "") or item.findtext("{http://www.w3.org/2005/Atom}summary", "")
                link = item.findtext("link", "") or ""
                pub_date = item.findtext("pubDate", "") or item.findtext("{http://www.w3.org/2005/Atom}published", "")
                
                text = f"{title} {desc}".lower()
                
                # Filtrer sur les mots-clés économiques
                matching_kw = [kw for kw in keywords_eco if kw in text]
                if not matching_kw:
                    continue
                
                # Détecter le sentiment
                neg_words = ["fermeture", "licenciement", "liquidation", "défaillance", "plan social", "chômage", "déclin"]
                pos_words = ["embauche", "ouverture", "investissement", "start-up", "croissance", "création"]
                
                neg_count = sum(1 for w in neg_words if w in text)
                pos_count = sum(1 for w in pos_words if w in text)
                sentiment = "negative" if neg_count > pos_count else "positive" if pos_count > neg_count else "neutral"
                
                signals.append(Signal(
                    source="presse_locale",
                    metric_name=f"article_{sentiment}",
                    code_dept="FR",  # TODO: extraire le département du texte
                    event_date=date.today(),
                    signal_type="text",
                    confidence=0.6,
                    source_url=link,
                    raw_data={"feed": feed_name, "keywords": matching_kw, "sentiment": sentiment},
                    extracted_text=f"{title} — {desc[:300]}",
                ))
                stats.collected += 1
                
        except ET.ParseError:
            logger.debug(f"  RSS {feed_name}: XML parse error")
            stats.errors += 1
        except Exception as e:
            logger.debug(f"  RSS {feed_name}: {e}")
            stats.errors += 1
    
    logger.info(f"📰 Presse: {stats.collected} articles, {stats.errors} erreurs")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# URSSAF — Auto-entrepreneurs par département
# ═══════════════════════════════════════════════════════════════

async def collect_urssaf(client: httpx.AsyncClient, depts: list[str]) -> tuple[list[Signal], CollectStats]:
    """Collecte données auto-entrepreneurs URSSAF (open data)."""
    stats = CollectStats(source="urssaf")
    signals = []
    
    try:
        # Récupérer les derniers trimestres
        resp = await client.get(
            "https://open.urssaf.fr/api/explore/v2.1/catalog/datasets/auto-entrepreneurs-par-departement/records",
            params={
                "limit": 100,
                "order_by": "dernier_jour_du_trimestre DESC",
                "select": "code_departement, departement, annee, trimestre, immatriculations, radiations, chiffres_d_affaires, economiquement_actifs, administrativement_actifs",
            },
            timeout=30,
        )
        
        if resp.status_code == 200:
            data = resp.json()
            records = data.get("results", [])
            
            for rec in records:
                dept_code = str(rec.get("code_departement", "")).zfill(2)
                if dept_code not in depts:
                    continue
                
                immat = rec.get("immatriculations")
                rad = rec.get("radiations")
                ca = rec.get("chiffres_d_affaires")
                actifs = rec.get("economiquement_actifs")
                
                year = rec.get("annee", "")
                trim = rec.get("trimestre", "")
                period = f"{year}-T{trim}"
                
                if immat is not None:
                    signals.append(Signal(
                        source="urssaf", metric_name="ae_immatriculations",
                        code_dept=dept_code, metric_value=float(immat),
                        event_date=date(int(year), int(trim) * 3, 28) if year and trim else None,
                        signal_type="metric", confidence=0.95,
                        raw_data={"period": period, "departement": rec.get("departement")},
                    ))
                    stats.collected += 1
                
                if rad is not None:
                    signals.append(Signal(
                        source="urssaf", metric_name="ae_radiations",
                        code_dept=dept_code, metric_value=float(rad),
                        event_date=date(int(year), int(trim) * 3, 28) if year and trim else None,
                        signal_type="metric", confidence=0.95,
                    ))
                    stats.collected += 1
                
                if ca is not None:
                    signals.append(Signal(
                        source="urssaf", metric_name="ae_chiffre_affaires",
                        code_dept=dept_code, metric_value=float(ca),
                        event_date=date(int(year), int(trim) * 3, 28) if year and trim else None,
                        signal_type="metric", confidence=0.95,
                    ))
                    stats.collected += 1
                
                if actifs is not None:
                    signals.append(Signal(
                        source="urssaf", metric_name="ae_economiquement_actifs",
                        code_dept=dept_code, metric_value=float(actifs),
                        event_date=date(int(year), int(trim) * 3, 28) if year and trim else None,
                        signal_type="metric", confidence=0.95,
                    ))
                    stats.collected += 1
            
            logger.info(f"  ✅ URSSAF: {len(records)} records")
        else:
            logger.warning(f"  URSSAF HTTP {resp.status_code}")
            stats.errors += 1
            
    except Exception as e:
        logger.error(f"  URSSAF: {e}")
        stats.errors += 1
    
    # Aussi : effectifs salariés par département
    try:
        resp2 = await client.get(
            "https://open.urssaf.fr/api/explore/v2.1/catalog/datasets/effectifs-salaries-et-masse-salariale-du-secteur-prive-par-departement-x-na38/records",
            params={"limit": 100, "order_by": "dernier_jour_du_trimestre DESC"},
            timeout=30,
        )
        if resp2.status_code == 200:
            for rec in resp2.json().get("results", []):
                dept_code = str(rec.get("departement", "")).zfill(2)
                if dept_code not in depts:
                    continue
                effectif = rec.get("effectif")
                if effectif:
                    signals.append(Signal(
                        source="urssaf", metric_name="effectifs_salaries",
                        code_dept=dept_code, metric_value=float(effectif),
                        event_date=date.today(), signal_type="metric", confidence=0.95,
                        raw_data={"secteur": rec.get("grand_secteur_d_activite")},
                    ))
                    stats.collected += 1
    except Exception as e:
        logger.debug(f"  URSSAF effectifs: {e}")
    
    logger.info(f"📊 URSSAF: {stats.collected} signaux, {stats.errors} erreurs")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# GOOGLE TRENDS — Tendances de recherche
# ═══════════════════════════════════════════════════════════════

async def collect_google_trends(client: httpx.AsyncClient, depts: list[str]) -> tuple[list[Signal], CollectStats]:
    """Collecte Google Trends via pytrends (anciennes régions FR → départements)."""
    stats = CollectStats(source="google_trends")
    signals = []
    
    try:
        from pytrends.request import TrendReq
    except ImportError:
        logger.warning("  ⚠️ pytrends non installé")
        return signals, stats
    
    keywords = [
        "liquidation judiciaire",
        "pôle emploi",
        "création entreprise",
        "RSA",
        "immobilier achat",
    ]
    
    # Google Trends retourne les anciennes régions FR (pré-2016)
    OLD_REGIONS_TO_DEPTS = {
        "Alsace": ["67", "68"],
        "Aquitaine": ["24", "33", "40", "47", "64"],
        "Auvergne": ["03", "15", "43", "63"],
        "Basse-Normandie": ["14", "50", "61"],
        "Bourgogne": ["21", "58", "71", "89"],
        "Bretagne": ["22", "29", "35", "56"],
        "Centre-Val de Loire": ["18", "28", "36", "37", "41", "45"],
        "Champagne-Ardenne": ["08", "10", "51", "52"],
        "Corse": ["2A", "2B"],
        "Franche-Comté": ["25", "39", "70", "90"],
        "Haute-Normandie": ["27", "76"],
        "Languedoc-Roussillon": ["11", "30", "34", "48", "66"],
        "Limousin": ["19", "23", "87"],
        "Lorraine": ["54", "55", "57", "88"],
        "Midi-Pyrénées": ["09", "12", "31", "32", "46", "65", "81", "82"],
        "Nord-Pas-de-Calais": ["59", "62"],
        "Pays de la Loire": ["44", "49", "53", "72", "85"],
        "Picardie": ["02", "60", "80"],
        "Poitou-Charentes": ["16", "17", "79", "86"],
        "Provence-Alpes-Côte d'Azur": ["04", "05", "06", "13", "83", "84"],
        "Rhône-Alpes": ["01", "07", "26", "38", "42", "69", "73", "74"],
        "Île-de-France": ["75", "77", "78", "91", "92", "93", "94", "95"],
    }
    
    try:
        pytrends = TrendReq(hl='fr-FR', tz=60, timeout=(10, 25))
        
        for kw in keywords:
            try:
                pytrends.build_payload([kw], cat=0, timeframe='today 3-m', geo='FR')
                interest = pytrends.interest_by_region(resolution='REGION', inc_low_vol=True)
                
                if not interest.empty:
                    for region_name, row in interest.iterrows():
                        val = row.get(kw, 0)
                        if val == 0:
                            continue
                        
                        # Mapper la région aux départements
                        dept_list = OLD_REGIONS_TO_DEPTS.get(region_name, [])
                        for d in dept_list:
                            if d in depts:
                                signals.append(Signal(
                                    source="google_trends",
                                    metric_name=f"trend_{kw.replace(' ', '_')}",
                                    code_dept=d,
                                    metric_value=float(val),
                                    event_date=date.today(),
                                    signal_type="metric",
                                    confidence=0.6,
                                    raw_data={"keyword": kw, "region": region_name},
                                ))
                                stats.collected += 1
                
                await asyncio.sleep(3)  # Rate limiting Google
                
            except Exception as e:
                logger.debug(f"  Trends '{kw}': {e}")
                stats.errors += 1
                await asyncio.sleep(5)
        
    except Exception as e:
        logger.warning(f"  Google Trends global error: {e}")
        stats.errors += 1
    
    logger.info(f"📈 Google Trends: {stats.collected} signaux, {stats.errors} erreurs")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# STOCKAGE EN BASE
# ═══════════════════════════════════════════════════════════════

async def store_signals(signals: list[Signal]) -> int:
    """Insère les signaux en base via asyncpg batch insert."""
    if not signals:
        return 0
    
    import asyncpg
    
    db_url = os.getenv("DATABASE_URL", "postgresql://localhost:5433/tawiza")
    conn = await asyncpg.connect(db_url)
    
    try:
        # Batch insert
        records = [
            (
                s.source, s.source_url, datetime.now(), s.event_date,
                s.code_commune, None, s.code_dept, None, None,
                s.metric_name, s.metric_value, s.signal_type,
                s.confidence, json.dumps(s.raw_data) if s.raw_data else None,
                s.extracted_text, json.dumps(s.entities) if s.entities else None,
            )
            for s in signals
        ]
        
        # Séparer events (insert direct) et metrics (upsert)
        events = [r for r, s in zip(records, signals) if s.signal_type != "metric"]
        metrics = [r for r, s in zip(records, signals) if s.signal_type == "metric"]
        
        if events:
            await conn.executemany("""
                INSERT INTO signals (
                    source, source_url, collected_at, event_date,
                    code_commune, code_epci, code_dept, latitude, longitude,
                    metric_name, metric_value, signal_type,
                    confidence, raw_data, extracted_text, entities
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb, $15, $16::jsonb)
            """, events)
        
        if metrics:
            await conn.executemany("""
                INSERT INTO signals (
                    source, source_url, collected_at, event_date,
                    code_commune, code_epci, code_dept, latitude, longitude,
                    metric_name, metric_value, signal_type,
                    confidence, raw_data, extracted_text, entities
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb, $15, $16::jsonb)
                ON CONFLICT (source, code_dept, metric_name, event_date) 
                WHERE signal_type = 'metric'
                DO UPDATE SET metric_value = EXCLUDED.metric_value, collected_at = EXCLUDED.collected_at, raw_data = EXCLUDED.raw_data
            """, metrics)
        
        logger.info(f"💾 {len(records)} signaux insérés en base")
        return len(records)
    finally:
        await conn.close()


# ═══════════════════════════════════════════════════════════════
# SITADEL — Permis de construire (SDES DiDo API)
# ═══════════════════════════════════════════════════════════════

DIDO_BASE = "https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1"
LOGEMENTS_DEPT_RID = "d264957b-c6d2-4efa-bf5e-6a8da836550a"

async def collect_sitadel(client: httpx.AsyncClient, depts: list[str]) -> tuple[list[Signal], CollectStats]:
    """Collecte permis de construire Sitadel via SDES DiDo API."""
    import csv
    import io
    
    stats = CollectStats(source="sitadel")
    signals = []
    
    try:
        url = f"{DIDO_BASE}/datafiles/{LOGEMENTS_DEPT_RID}/csv?millesime=2026-02&withColumnName=true&withColumnDescription=false&withColumnUnit=false"
        resp = await client.get(url, timeout=60)
        resp.raise_for_status()
        
        reader = csv.DictReader(io.StringIO(resp.text), delimiter=";")
        cutoff_year = datetime.now().year - 2
        
        for row in reader:
            try:
                year = int(row.get("ANNEE", "").strip('"'))
                if year < cutoff_year:
                    continue
                month = int(row.get("MOIS", "").strip('"'))
                dept = row.get("DEPARTEMENT_CODE", "").strip('"')
                
                if dept not in depts:
                    continue
                
                ev_date = date(year, month, 1)
                
                for field, metric in [("LOG_AUT", "logements_autorises"), ("LOG_COM", "logements_commences")]:
                    val_str = row.get(field, "").strip().strip('"')
                    if val_str and val_str not in ("", "s", "nd"):
                        try:
                            val = int(float(val_str))
                            if val > 0:
                                signals.append(Signal(
                                    source="sitadel",
                                    source_url=f"https://data.statistiques.developpement-durable.gouv.fr/sitadel/{dept}/{year}-{month:02d}",
                                    metric_name=metric,
                                    metric_value=val,
                                    code_dept=dept,
                                    event_date=ev_date,
                                    signal_type="construction",
                                    raw_data={"type_logement": row.get("TYPE_LGT", "").strip('"')},
                                ))
                                stats.collected += 1
                        except (ValueError, TypeError):
                            pass
            except (ValueError, KeyError):
                continue
        
        logger.info(f"  Sitadel: {stats.collected} signaux collectés")
    except Exception as e:
        logger.error(f"  Sitadel error: {e}")
        stats.errors += 1
    
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# GDELT — Événements mondiaux géolocalisés en France
# ═══════════════════════════════════════════════════════════════

async def collect_gdelt(client: httpx.AsyncClient, depts: list[str]) -> tuple[list[Signal], CollectStats]:
    """Collecte événements GDELT géolocalisés en France via BigQuery API."""
    stats = CollectStats(source="gdelt")
    signals = []
    
    # GDELT DOC API - search for French economic events
    keywords = [
        "liquidation entreprise france",
        "creation entreprise france",
        "emploi france departement",
        "immobilier france prix",
        "industrie france fermeture",
    ]
    
    for kw in keywords:
        try:
            url = "https://api.gdeltproject.org/api/v2/doc/doc"
            params = {
                "query": kw,
                "mode": "artlist",
                "maxrecords": 50,
                "format": "json",
                "sourcelang": "french",
                "timespan": "30d",
            }
            resp = await client.get(url, params=params, timeout=30)
            if resp.status_code != 200:
                continue
            
            data = resp.json()
            articles = data.get("articles", [])
            
            for art in articles:
                title = art.get("title", "")
                url_art = art.get("url", "")
                date_str = art.get("seendate", "")
                
                if not title or not date_str:
                    continue
                
                try:
                    ev_date = datetime.strptime(date_str[:8], "%Y%m%d").date()
                except (ValueError, IndexError):
                    continue
                
                # Try to extract department from title/domain
                dept_found = None
                for d in depts[:20]:  # Check top departments
                    if d in title:
                        dept_found = d
                        break
                
                signals.append(Signal(
                    source="gdelt",
                    source_url=url_art,
                    metric_name=kw.replace(" ", "_"),
                    metric_value=art.get("socialimage", 0) or 0,
                    code_dept=dept_found,
                    event_date=ev_date,
                    signal_type="presse",
                    extracted_text=title[:500],
                    raw_data={"domain": art.get("domain", ""), "language": art.get("language", "")},
                ))
                stats.collected += 1
                
        except Exception as e:
            logger.warning(f"  GDELT '{kw}': {e}")
            stats.errors += 1
    
    logger.info(f"  GDELT: {stats.collected} signaux collectés")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# DGFiP — Fiscalité locale & Comptes départementaux
# ═══════════════════════════════════════════════════════════════

async def collect_dgfip(client: httpx.AsyncClient, depts: list[str]) -> tuple[list[Signal], CollectStats]:
    """Collecte DGFiP via data.economie.gouv.fr open data API.
    
    2 datasets:
    - fiscalite-locale-des-entreprises: taux TFB/CFE/TEOM par commune (agrégé par dept)
    - comptes-individuels-des-departements 2023-2024: budget, dette, CAF, investissement
    """
    stats = CollectStats(source="dgfip")
    signals: list[Signal] = []
    base = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
    today = date.today()
    
    # --- 1. Fiscalité locale: taux moyens par département ---
    logger.info("  DGFiP: Collecte fiscalité locale (taux par département)...")
    try:
        for dept in depts:
            dept_filter = dept.lstrip("0") if len(dept) <= 2 else dept
            url = (
                f"{base}/fiscalite-locale-des-entreprises/records"
                f"?where=dep='{dept_filter}' AND exercice='2024'"
                f"&select=avg(taux_global_tfb) as avg_tfb, avg(taux_global_cfe_hz) as avg_cfe, avg(taux_plein_teom) as avg_teom, count(*) as nb_communes"
                f"&group_by=dep"
                f"&limit=1"
            )
            try:
                resp = await client.get(url, timeout=15)
                if resp.status_code != 200:
                    # Try 2023 as fallback
                    url2 = url.replace("exercice='2024'", "exercice='2023'")
                    resp = await client.get(url2, timeout=15)
                    if resp.status_code != 200:
                        stats.skipped += 1
                        continue
                
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    stats.skipped += 1
                    continue
                
                r = results[0]
                avg_tfb = r.get("avg_tfb")
                avg_cfe = r.get("avg_cfe")
                avg_teom = r.get("avg_teom")
                nb_communes = r.get("nb_communes", 0)
                
                if avg_tfb is not None:
                    signals.append(Signal(
                        source="dgfip", metric_name="taux_moyen_tfb",
                        code_dept=dept, metric_value=round(avg_tfb, 2),
                        event_date=date(2024, 1, 1), signal_type="metric",
                        confidence=0.95,
                        source_url="https://data.economie.gouv.fr/explore/dataset/fiscalite-locale-des-entreprises",
                        extracted_text=f"Dept {dept}: Taux moyen TFB {avg_tfb:.2f}%, CFE {avg_cfe:.2f}%, TEOM {avg_teom:.2f}% ({nb_communes} communes)",
                        raw_data={"avg_tfb": avg_tfb, "avg_cfe": avg_cfe, "avg_teom": avg_teom, "nb_communes": nb_communes},
                    ))
                    stats.collected += 1
                
                if avg_cfe is not None:
                    signals.append(Signal(
                        source="dgfip", metric_name="taux_moyen_cfe",
                        code_dept=dept, metric_value=round(avg_cfe, 2),
                        event_date=date(2024, 1, 1), signal_type="metric",
                        confidence=0.95,
                        source_url="https://data.economie.gouv.fr/explore/dataset/fiscalite-locale-des-entreprises",
                        extracted_text=f"Dept {dept}: Taux moyen CFE (hors zone) {avg_cfe:.2f}%",
                        raw_data={"avg_cfe": avg_cfe, "dept": dept},
                    ))
                    stats.collected += 1
                
                if avg_teom is not None:
                    signals.append(Signal(
                        source="dgfip", metric_name="taux_moyen_teom",
                        code_dept=dept, metric_value=round(avg_teom, 2),
                        event_date=date(2024, 1, 1), signal_type="metric",
                        confidence=0.95,
                        source_url="https://data.economie.gouv.fr/explore/dataset/fiscalite-locale-des-entreprises",
                        extracted_text=f"Dept {dept}: Taux moyen TEOM {avg_teom:.2f}%",
                        raw_data={"avg_teom": avg_teom, "dept": dept},
                    ))
                    stats.collected += 1
                    
            except Exception as e:
                logger.debug(f"  DGFiP fiscalité dept {dept}: {e}")
                stats.errors += 1
                
    except Exception as e:
        logger.warning(f"  DGFiP fiscalité locale: {e}")
        stats.errors += 1
    
    logger.info(f"  DGFiP fiscalité: {stats.collected} signaux")
    
    # --- 2. Comptes départementaux 2023-2024 ---
    logger.info("  DGFiP: Collecte comptes départementaux...")
    dataset_id = "comptes-individuels-des-departements-et-des-collectivites-territoriales-uniques-fichier-global-2023-2024"
    
    # Key financial indicators from comptes:
    # tpf = total produits de fonctionnement (recettes)
    # tcf = total charges de fonctionnement (dépenses)
    # ebf = épargne brute de fonctionnement
    # caf = capacité d'autofinancement
    # dba = dette bancaire et assimilée
    # aid = aides versées (social)
    # fsh = frais de séjour et hébergement
    # tri = total recettes d'investissement
    
    FINANCIAL_METRICS = {
        "tpf": ("recettes_fonctionnement", "Total produits de fonctionnement"),
        "tcf": ("charges_fonctionnement", "Total charges de fonctionnement"),
        "ebf": ("epargne_brute", "Epargne brute de fonctionnement"),
        "caf": ("capacite_autofinancement", "Capacité d'autofinancement"),
        "dba": ("dette_bancaire", "Dette bancaire et assimilée"),
        "aid": ("aides_versees", "Aides versées (social)"),
        "dgf": ("dotation_globale", "Dotation globale de fonctionnement"),
        "tri": ("recettes_investissement", "Total recettes d'investissement"),
    }
    
    try:
        for dept in depts:
            dept_code = dept.zfill(3) if len(dept) <= 2 else dept
            url = (
                f"{base}/{dataset_id}/records"
                f"?where=dep='{dept_code}' AND exer='2023'"
                f"&select=dep,exer,lbudg,mpoid_bp,tpf,tcf,ebf,caf,dba,aid,dgf,tri"
                f"&limit=1"
            )
            try:
                resp = await client.get(url, timeout=15)
                if resp.status_code != 200:
                    stats.skipped += 1
                    continue
                
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    stats.skipped += 1
                    continue
                
                r = results[0]
                pop = r.get("mpoid_bp", 0)
                lbudg = r.get("lbudg", "")
                
                for field_name, (metric_name, label) in FINANCIAL_METRICS.items():
                    val = r.get(field_name)
                    if val is not None:
                        # Values are in thousands of euros
                        signals.append(Signal(
                            source="dgfip", metric_name=metric_name,
                            code_dept=dept, metric_value=round(val, 2),
                            event_date=date(2023, 12, 31), signal_type="metric",
                            confidence=0.95,
                            source_url=f"https://data.economie.gouv.fr/explore/dataset/{dataset_id}",
                            extracted_text=f"{lbudg} ({dept}): {label} = {val:,.0f} k€ (pop: {pop:,})",
                            raw_data={"value_keur": val, "population": pop, "exercice": 2023, "field": field_name},
                        ))
                        stats.collected += 1
                        
            except Exception as e:
                logger.debug(f"  DGFiP comptes dept {dept}: {e}")
                stats.errors += 1
                
    except Exception as e:
        logger.warning(f"  DGFiP comptes départementaux: {e}")
        stats.errors += 1
    
    logger.info(f"  DGFiP total: {stats.collected} signaux collectés")
    return signals, stats


# ═══════════════════════════════════════════════════════════════
# ORCHESTRATEUR
# ═══════════════════════════════════════════════════════════════

async def run_full_collect(
    depts: list[str] | None = None,
    sources: list[str] | None = None,
    days_back: int = 30,
):
    """Lance la collecte complète."""
    target_depts = depts or ALL_DEPTS
    target_sources = sources or ["bodacc", "france_travail", "sirene", "insee", "ofgl", "dvf", "urssaf", "banque_france", "presse_locale", "google_trends", "sitadel", "gdelt", "dgfip"]
    
    logger.info(f"🚀 COLLECTE Tawiza V2")
    logger.info(f"   Départements: {len(target_depts)}")
    logger.info(f"   Sources: {', '.join(target_sources)}")
    logger.info(f"   Lookback: {days_back} jours")
    
    all_signals: list[Signal] = []
    all_stats: list[CollectStats] = []
    
    async with httpx.AsyncClient(
        timeout=30,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        follow_redirects=True,
    ) as client:
        
        collectors = {
            "bodacc": lambda: collect_bodacc(client, target_depts, days_back),
            "france_travail": lambda: collect_france_travail(client, target_depts),
            "sirene": lambda: collect_sirene(client, target_depts),
            "insee": lambda: collect_insee(client, target_depts),
            "ofgl": lambda: collect_ofgl(client, target_depts),
            "dvf": lambda: collect_dvf(client, target_depts),
            "urssaf": lambda: collect_urssaf(client, target_depts),
            "banque_france": lambda: collect_banque_france(client),
            "presse_locale": lambda: collect_presse(client),
            "google_trends": lambda: collect_google_trends(client, target_depts),
            "sitadel": lambda: collect_sitadel(client, target_depts),
            "gdelt": lambda: collect_gdelt(client, target_depts),
            "dgfip": lambda: collect_dgfip(client, target_depts),
        }
        
        for src_name in target_sources:
            if src_name not in collectors:
                logger.warning(f"  ⚠️ Source inconnue: {src_name}")
                continue
            
            logger.info(f"\n{'='*60}")
            logger.info(f"📡 {src_name.upper()}")
            logger.info(f"{'='*60}")
            
            try:
                signals, stats = await collectors[src_name]()
                all_signals.extend(signals)
                all_stats.append(stats)
            except Exception as e:
                logger.error(f"❌ {src_name}: {e}")
                all_stats.append(CollectStats(source=src_name, errors=1))
    
    # Stockage
    if all_signals:
        stored = await store_signals(all_signals)
    else:
        stored = 0
    
    # Résumé
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 RÉSUMÉ COLLECTE Tawiza V2")
    logger.info(f"{'='*60}")
    
    total_collected = 0
    total_errors = 0
    for s in all_stats:
        logger.info(f"  {s.source:20s} | {s.collected:6d} collectés | {s.errors:3d} erreurs")
        total_collected += s.collected
        total_errors += s.errors
    
    logger.info(f"  {'─'*50}")
    logger.info(f"  {'TOTAL':20s} | {total_collected:6d} collectés | {total_errors:3d} erreurs")
    logger.info(f"  💾 {stored} signaux insérés en base")
    
    return all_signals, all_stats


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Collecteur unifié Tawiza V2")
    parser.add_argument("--depts", nargs="+", help="Départements à collecter (ex: 75 93 35)")
    parser.add_argument("--sources", nargs="+", help="Sources (bodacc france_travail sirene insee ofgl dvf banque_france presse_locale)")
    parser.add_argument("--days", type=int, default=30, help="Lookback en jours (défaut: 30)")
    parser.add_argument("--all", action="store_true", help="Tous les 101 départements")
    
    args = parser.parse_args()
    
    depts = None
    if args.depts:
        depts = args.depts
    elif not args.all:
        # Par défaut: 20 départements stratégiques
        depts = ["75", "93", "92", "94", "91", "78", "95", "77",  # IDF
                 "13", "69", "31", "33", "59", "44", "35", "67",  # Grandes métropoles
                 "06", "34", "17", "15"]  # Mix
    
    asyncio.run(run_full_collect(
        depts=depts,
        sources=args.sources,
        days_back=args.days,
    ))
