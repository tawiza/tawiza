#!/usr/bin/env python3
"""Scoring composite territorial — 6 alpha factors normalisés par population.

Dimensions :
  α1 : Santé des entreprises (créations vs liquidations, BODACC + SIRENE)
  α2 : Tension emploi (offres FT, CDI ratio, URSSAF AE)
  α3 : Dynamisme immobilier (prix DVF, volume transactions)
  α4 : Santé financière (OFGL dépenses/recettes, dette/hab)
  α5 : Déclin ratio (liquidations + radiations vs créations)
  α6 : Sentiment presse + Google Trends

Score composite = Σ(αi × wi) / Σ(wi), normalisé 0-100
"""

import asyncio
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path

import numpy as np
from loguru import logger

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# DB URL from environment
_RAW_DB_URL = os.getenv(
    "COLLECTOR_DATABASE_URL",
    "postgresql+asyncpg://localhost:5433/tawiza",
).replace("+asyncpg", "")

# Department names for save_scores
DEPT_NAMES: dict[str, str] = {
    '01':'Ain','02':'Aisne','03':'Allier','04':'Alpes-de-Haute-Provence','05':'Hautes-Alpes',
    '06':'Alpes-Maritimes','07':'Ardèche','08':'Ardennes','09':'Ariège','10':'Aube',
    '11':'Aude','12':'Aveyron','13':'Bouches-du-Rhône','14':'Calvados','15':'Cantal',
    '16':'Charente','17':'Charente-Maritime','18':'Cher','19':'Corrèze','2A':'Corse-du-Sud',
    '2B':'Haute-Corse','21':"Côte-d'Or",'22':"Côtes-d'Armor",'23':'Creuse','24':'Dordogne',
    '25':'Doubs','26':'Drôme','27':'Eure','28':'Eure-et-Loir','29':'Finistère',
    '30':'Gard','31':'Haute-Garonne','32':'Gers','33':'Gironde','34':'Hérault',
    '35':'Ille-et-Vilaine','36':'Indre','37':'Indre-et-Loire','38':'Isère','39':'Jura',
    '40':'Landes','41':'Loir-et-Cher','42':'Loire','43':'Haute-Loire','44':'Loire-Atlantique',
    '45':'Loiret','46':'Lot','47':'Lot-et-Garonne','48':'Lozère','49':'Maine-et-Loire',
    '50':'Manche','51':'Marne','52':'Haute-Marne','53':'Mayenne','54':'Meurthe-et-Moselle',
    '55':'Meuse','56':'Morbihan','57':'Moselle','58':'Nièvre','59':'Nord',
    '60':'Oise','61':'Orne','62':'Pas-de-Calais','63':'Puy-de-Dôme','64':'Pyrénées-Atlantiques',
    '65':'Hautes-Pyrénées','66':'Pyrénées-Orientales','67':'Bas-Rhin','68':'Haut-Rhin','69':'Rhône',
    '70':'Haute-Saône','71':'Saône-et-Loire','72':'Sarthe','73':'Savoie','74':'Haute-Savoie',
    '75':'Paris','76':'Seine-Maritime','77':'Seine-et-Marne','78':'Yvelines','79':'Deux-Sèvres',
    '80':'Somme','81':'Tarn','82':'Tarn-et-Garonne','83':'Var','84':'Vaucluse',
    '85':'Vendée','86':'Vienne','87':'Haute-Vienne','88':'Vosges','89':'Yonne',
    '90':'Territoire de Belfort','91':'Essonne','92':'Hauts-de-Seine','93':'Seine-Saint-Denis',
    '94':'Val-de-Marne','95':"Val-d'Oise",
    '971':'Guadeloupe','972':'Martinique','973':'Guyane','974':'La Réunion','976':'Mayotte',
}


@dataclass
class DepartmentFactors:
    code_dept: str
    population: float = 0
    
    # Raw metrics
    creations: int = 0
    liquidations: int = 0
    radiations: int = 0
    procedures_collectives: int = 0
    sirene_creations: float = 0
    
    offres_emploi: int = 0
    offres_cdi: int = 0
    ae_immatriculations: float = 0
    ae_radiations: float = 0
    ae_actifs: float = 0
    
    prix_m2: float = 0
    nb_transactions: float = 0
    
    depenses: float = 0
    recettes: float = 0
    dette: float = 0
    
    articles_positifs: int = 0
    articles_negatifs: int = 0
    google_trends_avg: float = 0
    
    # Computed factors (0-100)
    alpha1_sante_entreprises: float = 50
    alpha2_tension_emploi: float = 50
    alpha3_dynamisme_immo: float = 50
    alpha4_sante_financiere: float = 50
    alpha5_declin_ratio: float = 50
    alpha6_sentiment: float = 50
    score_composite: float = 50


async def load_all_metrics() -> dict[str, DepartmentFactors]:
    """Charge toutes les métriques par département."""
    import asyncpg
    conn = await asyncpg.connect(_RAW_DB_URL)
    
    try:
        rows = await conn.fetch("""
            SELECT code_dept, source, metric_name, 
                   SUM(metric_value) as total_val,
                   AVG(metric_value) as avg_val,
                   COUNT(*) as cnt
            FROM signals
            WHERE code_dept IS NOT NULL
            GROUP BY code_dept, source, metric_name
        """)
    finally:
        await conn.close()
    
    depts: dict[str, DepartmentFactors] = {}
    
    for r in rows:
        dept = r["code_dept"]
        if dept not in depts:
            depts[dept] = DepartmentFactors(code_dept=dept)
        d = depts[dept]
        
        src = r["source"]
        metric = r["metric_name"]
        total = float(r["total_val"]) if r["total_val"] else 0
        avg = float(r["avg_val"]) if r["avg_val"] else 0
        cnt = r["cnt"]
        
        # Population
        if src == "insee" and metric == "population":
            d.population = avg
        
        # Entreprises
        elif src == "bodacc":
            if "creation" in metric or "immatriculation" in metric:
                d.creations += cnt
            elif "liquidation" in metric:
                d.liquidations += cnt
            elif "radiation" in metric:
                d.radiations += cnt
            elif "procedure" in metric or "redressement" in metric or "sauvegarde" in metric:
                d.procedures_collectives += cnt
        
        elif src == "sirene" and metric == "creations_entreprises_count":
            d.sirene_creations = avg
        
        # Emploi
        elif src == "france_travail":
            d.offres_emploi += cnt
            if "cdi" in metric:
                d.offres_cdi += cnt
        
        elif src == "urssaf":
            if metric == "ae_immatriculations":
                d.ae_immatriculations = avg
            elif metric == "ae_radiations":
                d.ae_radiations = avg
            elif metric == "ae_economiquement_actifs":
                d.ae_actifs = avg
        
        # Immobilier
        elif src == "dvf":
            if metric == "prix_m2_median":
                d.prix_m2 = avg
            elif metric == "nb_transactions_immobilieres":
                d.nb_transactions = avg
        
        # Finances
        elif src == "ofgl":
            if "depenses" in metric:
                d.depenses = max(d.depenses, avg)
            elif "recettes" in metric:
                d.recettes = max(d.recettes, avg)
            elif "dette" in metric:
                d.dette = max(d.dette, avg)
        
        # Presse
        elif src == "presse_locale":
            if "positive" in metric:
                d.articles_positifs += cnt
            elif "negative" in metric:
                d.articles_negatifs += cnt
        
        # Google Trends
        elif src == "google_trends":
            d.google_trends_avg = avg
    
    return depts


def percentile_score(values: list[float], value: float, invert: bool = False) -> float:
    """Convertit une valeur en score 0-100 basé sur le percentile."""
    if not values or len(values) < 2:
        return 50.0
    arr = np.array(values)
    pct = float(np.sum(arr <= value) / len(arr) * 100)
    return 100 - pct if invert else pct


def compute_factors(depts: dict[str, DepartmentFactors]) -> dict[str, DepartmentFactors]:
    """Calcule les 6 alpha factors pour chaque département."""
    
    metrics_per_cap = defaultdict(list)
    
    for dept, d in depts.items():
        if d.population <= 0:
            continue
        
        pop = d.population / 10000  # Pour 10k habitants
        
        # α1: Santé entreprises
        crea_rate = (d.creations + d.sirene_creations * 0.01) / pop if pop else 0
        liq_rate = d.liquidations / pop if pop else 0
        metrics_per_cap["crea_rate"].append((dept, crea_rate))
        metrics_per_cap["liq_rate"].append((dept, liq_rate))
        
        # α2: Tension emploi
        offres_rate = d.offres_emploi / pop if pop else 0
        cdi_ratio = d.offres_cdi / max(d.offres_emploi, 1)
        ae_rate = d.ae_immatriculations / pop if pop else 0
        metrics_per_cap["offres_rate"].append((dept, offres_rate))
        metrics_per_cap["cdi_ratio"].append((dept, cdi_ratio))
        metrics_per_cap["ae_rate"].append((dept, ae_rate))
        
        # α3: Dynamisme immo
        if d.prix_m2 > 0:
            metrics_per_cap["prix_m2"].append((dept, d.prix_m2))
        if d.nb_transactions > 0:
            tx_rate = d.nb_transactions / pop if pop else 0
            metrics_per_cap["tx_rate"].append((dept, tx_rate))
        
        # α4: Santé financière
        if d.depenses > 0 and d.population > 0:
            depenses_hab = d.depenses / d.population
            metrics_per_cap["depenses_hab"].append((dept, depenses_hab))
        if d.recettes > 0 and d.depenses > 0:
            ratio_rec_dep = d.recettes / d.depenses
            metrics_per_cap["ratio_rec_dep"].append((dept, ratio_rec_dep))
        if d.dette > 0 and d.population > 0:
            dette_hab = d.dette / d.population
            metrics_per_cap["dette_hab"].append((dept, dette_hab))
        
        # α5: Déclin ratio (consistent: use max() everywhere)
        total_neg = d.liquidations + d.radiations + d.procedures_collectives
        total_pos = max(d.creations, 1)
        declin_ratio = total_neg / total_pos
        metrics_per_cap["declin_ratio"].append((dept, declin_ratio))
        
        # α6: Sentiment
        total_articles = d.articles_positifs + d.articles_negatifs
        sentiment = (d.articles_positifs - d.articles_negatifs) / max(total_articles, 1)
        metrics_per_cap["sentiment"].append((dept, sentiment))
        metrics_per_cap["gtrends"].append((dept, d.google_trends_avg))
    
    # Calculer les scores percentile
    for dept, d in depts.items():
        if d.population <= 0:
            continue
        
        pop = d.population / 10000
        
        # α1: Santé entreprises
        crea_vals = [v for _, v in metrics_per_cap["crea_rate"]]
        liq_vals = [v for _, v in metrics_per_cap["liq_rate"]]
        crea_score = percentile_score(crea_vals, (d.creations + d.sirene_creations * 0.01) / pop if pop else 0)
        liq_score = percentile_score(liq_vals, d.liquidations / pop if pop else 0, invert=True)
        d.alpha1_sante_entreprises = round(crea_score * 0.6 + liq_score * 0.4, 1)
        
        # α2: Tension emploi
        offres_vals = [v for _, v in metrics_per_cap["offres_rate"]]
        cdi_vals = [v for _, v in metrics_per_cap["cdi_ratio"]]
        ae_vals = [v for _, v in metrics_per_cap["ae_rate"]]
        
        offres_score = percentile_score(offres_vals, d.offres_emploi / pop if pop else 0)
        cdi_score = percentile_score(cdi_vals, d.offres_cdi / max(d.offres_emploi, 1))
        ae_score = percentile_score(ae_vals, d.ae_immatriculations / pop if pop else 0)
        
        d.alpha2_tension_emploi = round(offres_score * 0.4 + cdi_score * 0.3 + ae_score * 0.3, 1)
        
        # α3: Dynamisme immo
        if d.prix_m2 > 0 and d.nb_transactions > 0:
            prix_vals = [v for _, v in metrics_per_cap["prix_m2"]]
            tx_vals = [v for _, v in metrics_per_cap["tx_rate"]]
            prix_pct = percentile_score(prix_vals, d.prix_m2)
            # Pénaliser les extrêmes
            if prix_pct > 90:
                prix_score = 30
            elif prix_pct < 10:
                prix_score = 30
            else:
                prix_score = 50 + (50 - abs(prix_pct - 50)) * 0.6
            
            tx_score = percentile_score(tx_vals, d.nb_transactions / pop if pop else 0)
            d.alpha3_dynamisme_immo = round(tx_score * 0.6 + prix_score * 0.4, 1)
        
        # α4: Santé financière
        if d.depenses > 0:
            rec_dep_vals = [v for _, v in metrics_per_cap["ratio_rec_dep"]]
            dette_vals = [v for _, v in metrics_per_cap["dette_hab"]]
            
            rec_dep_score = percentile_score(rec_dep_vals, d.recettes / d.depenses if d.depenses else 1)
            dette_score = percentile_score(dette_vals, d.dette / d.population if d.population else 0, invert=True)
            
            d.alpha4_sante_financiere = round(rec_dep_score * 0.5 + dette_score * 0.5, 1)
        
        # α5: Déclin ratio (consistent with collection above)
        declin_vals = [v for _, v in metrics_per_cap["declin_ratio"]]
        total_neg = d.liquidations + d.radiations + d.procedures_collectives
        declin = total_neg / max(d.creations, 1)
        d.alpha5_declin_ratio = round(percentile_score(declin_vals, declin, invert=True), 1)
        
        # α6: Sentiment
        sent_vals = [v for _, v in metrics_per_cap["sentiment"]]
        gt_vals = [v for _, v in metrics_per_cap["gtrends"]]
        total_articles = d.articles_positifs + d.articles_negatifs
        sentiment = (d.articles_positifs - d.articles_negatifs) / max(total_articles, 1)
        sent_score = percentile_score(sent_vals, sentiment)
        gt_score = percentile_score(gt_vals, d.google_trends_avg, invert=True)
        
        d.alpha6_sentiment = round(sent_score * 0.5 + gt_score * 0.5, 1)
        
        # Score composite pondéré
        weights = {
            "alpha1": 0.25,
            "alpha2": 0.20,
            "alpha3": 0.15,
            "alpha4": 0.15,
            "alpha5": 0.15,
            "alpha6": 0.10,
        }
        
        d.score_composite = round(
            d.alpha1_sante_entreprises * weights["alpha1"] +
            d.alpha2_tension_emploi * weights["alpha2"] +
            d.alpha3_dynamisme_immo * weights["alpha3"] +
            d.alpha4_sante_financiere * weights["alpha4"] +
            d.alpha5_declin_ratio * weights["alpha5"] +
            d.alpha6_sentiment * weights["alpha6"],
            1
        )
    
    return depts


async def save_scores(depts: dict[str, DepartmentFactors]):
    """Sauvegarde les scores dans territorial_snapshots (upsert)."""
    import asyncpg
    conn = await asyncpg.connect(_RAW_DB_URL)
    
    try:
        scored = 0
        today = datetime.now().date()
        for dept, d in depts.items():
            if d.population <= 0:
                continue
            
            extra = json.dumps({
                "alpha1_sante_entreprises": d.alpha1_sante_entreprises,
                "alpha2_tension_emploi": d.alpha2_tension_emploi,
                "alpha3_dynamisme_immo": d.alpha3_dynamisme_immo,
                "alpha4_sante_financiere": d.alpha4_sante_financiere,
                "alpha5_declin_ratio": d.alpha5_declin_ratio,
                "alpha6_sentiment": d.alpha6_sentiment,
                "score_composite": d.score_composite,
                "population": d.population,
                "creations": d.creations,
                "liquidations": d.liquidations,
                "offres_emploi": d.offres_emploi,
                "prix_m2": d.prix_m2,
            })
            
            await conn.execute("""
                INSERT INTO territorial_snapshots
                (territory_code, territory_name, snapshot_date, population,
                 attractiveness_score, capital_humain_score, environnement_eco_score,
                 innovation_score, qualite_vie_score, accessibilite_score,
                 extra_data, data_source)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::json, $12)
                ON CONFLICT (territory_code, snapshot_date, data_source)
                DO UPDATE SET
                    territory_name = EXCLUDED.territory_name,
                    population = EXCLUDED.population,
                    attractiveness_score = EXCLUDED.attractiveness_score,
                    capital_humain_score = EXCLUDED.capital_humain_score,
                    environnement_eco_score = EXCLUDED.environnement_eco_score,
                    innovation_score = EXCLUDED.innovation_score,
                    qualite_vie_score = EXCLUDED.qualite_vie_score,
                    accessibilite_score = EXCLUDED.accessibilite_score,
                    extra_data = EXCLUDED.extra_data
            """,
                dept,
                DEPT_NAMES.get(dept, dept),
                datetime.now(),
                int(d.population),
                d.score_composite,
                d.alpha2_tension_emploi,
                d.alpha1_sante_entreprises,
                d.alpha3_dynamisme_immo,
                d.alpha4_sante_financiere,
                d.alpha6_sentiment,
                extra,
                "scoring_composite_v2",
            )
            scored += 1
        
        return scored
    finally:
        await conn.close()


async def run_scoring():
    """Pipeline complet de scoring."""
    logger.info("SCORING COMPOSITE TERRITORIAL V2")
    
    depts = await load_all_metrics()
    logger.info(f"  {len(depts)} departements charges")
    
    with_pop = sum(1 for d in depts.values() if d.population > 0)
    logger.info(f"  {with_pop} avec population")
    
    depts = compute_factors(depts)
    
    scored = await save_scores(depts)
    logger.info(f"  {scored} scores sauvegardes")
    
    ranked = sorted(
        [(d.code_dept, d.score_composite, d) for d in depts.values() if d.population > 0],
        key=lambda x: x[1], reverse=True,
    )
    
    logger.info(f"\n{'='*70}")
    logger.info(f"CLASSEMENT TERRITORIAL - {len(ranked)} departements")
    logger.info(f"{'='*70}")
    logger.info(f"{'Dept':>5} {'Score':>6} {'a1 Entr':>8} {'a2 Empl':>8} {'a3 Immo':>8} {'a4 Fin':>8} {'a5 Decl':>8} {'a6 Sent':>8}")
    logger.info(f"{'─'*70}")
    
    for i, (dept, score, d) in enumerate(ranked[:20], 1):
        logger.info(
            f"{dept:>5} {score:>6.1f} {d.alpha1_sante_entreprises:>8.1f} "
            f"{d.alpha2_tension_emploi:>8.1f} {d.alpha3_dynamisme_immo:>8.1f} "
            f"{d.alpha4_sante_financiere:>8.1f} {d.alpha5_declin_ratio:>8.1f} "
            f"{d.alpha6_sentiment:>8.1f}"
        )
    
    logger.info(f"\n  {'─'*70}")
    logger.info(f"  ... BOTTOM 10:")
    for dept, score, d in ranked[-10:]:
        logger.info(
            f"{dept:>5} {score:>6.1f} {d.alpha1_sante_entreprises:>8.1f} "
            f"{d.alpha2_tension_emploi:>8.1f} {d.alpha3_dynamisme_immo:>8.1f} "
            f"{d.alpha4_sante_financiere:>8.1f} {d.alpha5_declin_ratio:>8.1f} "
            f"{d.alpha6_sentiment:>8.1f}"
        )
    
    return ranked


async def get_department_scores() -> list[dict]:
    """Pour l'API : retourne les scores de tous les departements."""
    depts = await load_all_metrics()
    depts = compute_factors(depts)
    
    return [
        {
            "code_dept": d.code_dept,
            "score_composite": d.score_composite,
            "alpha1_sante_entreprises": d.alpha1_sante_entreprises,
            "alpha2_tension_emploi": d.alpha2_tension_emploi,
            "alpha3_dynamisme_immo": d.alpha3_dynamisme_immo,
            "alpha4_sante_financiere": d.alpha4_sante_financiere,
            "alpha5_declin_ratio": d.alpha5_declin_ratio,
            "alpha6_sentiment": d.alpha6_sentiment,
            "population": d.population,
        }
        for d in depts.values()
        if d.population > 0
    ]


if __name__ == "__main__":
    asyncio.run(run_scoring())
