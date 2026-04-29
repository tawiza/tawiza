"""
01_merge.py — Croisement RGA × DICRIM × TIM × DVF par département
Article 002 : Risque argile, le silence communal

Produit :
    data/processed/departements_rga.csv    (par département, agrégé)
    data/processed/tim_timeline.csv         (DICRIM publiés/an × CatNat/an)
    data/processed/tim_matrix.json          (matrice TIM × DICRIM communes RGA)
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
OUT = BASE / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

# ── 1. DICRIM × RGA depuis GASPAR ──────────────────────────────────────────

# Les fichiers GASPAR sont téléchargés par scripts/00_download.py dans
# data/raw/gaspar/. Fallback historique : /tmp (ancien emplacement).
GASPAR_DIR = RAW / "gaspar"
if not (GASPAR_DIR / "risq_gaspar.csv").exists():
    GASPAR_DIR = Path("/tmp")

# Communes exposées au RGA (= "Tassements différentiels" dans GASPAR)
communes_rga = {}  # code_commune -> nom
with open(GASPAR_DIR / "risq_gaspar.csv") as f:
    reader = csv.reader(f, delimiter=";", quotechar='"')
    next(reader)
    for row in reader:
        if len(row) >= 3 and "tassement" in row[2].lower():
            communes_rga[row[0]] = row[1]

# Communes avec DICRIM
dicrim_communes = set()
with open(GASPAR_DIR / "dicrim_gaspar.csv") as f:
    reader = csv.reader(f, delimiter=";", quotechar='"')
    next(reader)
    for row in reader:
        if row:
            dicrim_communes.add(row[0])

# Agréger par département
dept_rga_total = Counter()
dept_rga_dicrim = Counter()
for code in communes_rga:
    dept = code[:2] if not code.startswith("97") else code[:3]
    dept_rga_total[dept] += 1
    if code in dicrim_communes:
        dept_rga_dicrim[dept] += 1

# ── 2. DVF prix médians ────────────────────────────────────────────────────

dvf = {}
with open(RAW / "dvf_prix_departement.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        dvf[row["code_departement"]] = {
            "prix_median": float(row["prix_median_maison"]),
            "nb_transactions": int(row["nb_transactions_maison"]),
        }

# ── 3. Fonds prévention (11 départements) ──────────────────────────────────

fonds_depts = set()
with open(RAW / "fonds_prevention_argile.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        fonds_depts.add(row["code_dept"])

# ── 4. CatNat sécheresse par département ───────────────────────────────────

catnat = {}
with open(RAW / "catnat_secheresse.json") as f:
    catnat_data = json.load(f)
par_dept = catnat_data.get("par_departement", {})
for code_dept, dept_info in par_dept.items():
    catnat[code_dept] = dept_info.get("arretes_secheresse", 0)

# ── 5. Merge ───────────────────────────────────────────────────────────────

all_depts = sorted(set(dept_rga_total.keys()) | set(dvf.keys()))

rows = []
for dept in all_depts:
    rga_total = dept_rga_total.get(dept, 0)
    rga_dicrim = dept_rga_dicrim.get(dept, 0)
    pct_dicrim = round(rga_dicrim / rga_total * 100, 1) if rga_total > 0 else None
    pct_sans = round(100 - pct_dicrim, 1) if pct_dicrim is not None else None
    prix = dvf.get(dept, {}).get("prix_median")
    transactions = dvf.get(dept, {}).get("nb_transactions")
    nb_catnat = catnat.get(dept, 0)
    dans_fonds = "oui" if dept in fonds_depts else "non"

    rows.append({
        "code_dept": dept,
        "communes_rga": rga_total,
        "communes_rga_dicrim": rga_dicrim,
        "communes_rga_sans_dicrim": rga_total - rga_dicrim,
        "pct_dicrim": pct_dicrim,
        "pct_sans_dicrim": pct_sans,
        "prix_median_maison": prix,
        "nb_transactions": transactions,
        "nb_catnat_secheresse": nb_catnat,
        "dans_fonds_prevention": dans_fonds,
    })

# Sauvegarder
outfile = OUT / "departements_rga.csv"
fieldnames = list(rows[0].keys())
with open(outfile, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

# Stats
rga_depts = [r for r in rows if r["communes_rga"] > 0]
print(f"Départements avec communes RGA: {len(rga_depts)}")
print(f"Total communes RGA: {sum(r['communes_rga'] for r in rows)}")
print(f"Total avec DICRIM: {sum(r['communes_rga_dicrim'] for r in rows)}")
print(f"Total sans DICRIM: {sum(r['communes_rga_sans_dicrim'] for r in rows)}")
print(f"Fichier: {outfile}")

# ── 6. TIM × DICRIM : matrice et timeline (effet ciseaux) ─────────────────
#
# TIM = Transmission de l'Information aux Maires. Le préfet envoie au maire
# le Dossier Départemental des Risques Majeurs (DDRM), et GASPAR enregistre
# la date de transmission. C'est l'acte formel qui déclenche l'obligation
# de rédiger un DICRIM. On peut donc mesurer :
#   (a) combien de communes RGA ont été prévenues,
#   (b) combien n'ont jamais donné suite,
#   (c) depuis combien d'années leur transmission attend sans DICRIM,
#   (d) quel délai médian sépare TIM et DICRIM chez celles qui réagissent.
# On construit en parallèle une timeline annuelle pour le graphique ciseaux :
# DICRIM publiés par an dans les communes RGA vs arrêtés CatNat par an.


def _parse_year(date_str: str) -> int | None:
    """Année d'une date 'YYYY-MM-DD ...' ; None pour 1900 (null Excel) ou invalide."""
    if not date_str or len(date_str) < 4:
        return None
    try:
        year = int(date_str[:4])
    except ValueError:
        return None
    return None if year == 1900 else year


def _load_earliest_dates(path: Path, date_col: str) -> dict[str, str]:
    """Pour chaque commune, garde la première date connue (hors 1900/null)."""
    earliest: dict[str, str] = {}
    with open(path) as f:
        reader = csv.DictReader(f, delimiter=";", quotechar='"')
        for row in reader:
            cod = (row.get("cod_commune") or "").strip()
            dt = (row.get(date_col) or "").strip()
            if not cod or _parse_year(dt) is None:
                continue
            if cod not in earliest or dt < earliest[cod]:
                earliest[cod] = dt
    return earliest


tim_dates = _load_earliest_dates(GASPAR_DIR / "tim_gaspar.csv", "dat_transmission_tim")
dicrim_dates = _load_earliest_dates(GASPAR_DIR / "dicrim_gaspar.csv", "dat_publi_dicrim")

# Pour la matrice, on utilise dicrim_communes (toutes les communes avec DICRIM
# enregistré, quelle que soit la date) afin d'être cohérent avec les totaux
# de la section 1 — 4 323 communes RGA avec DICRIM. Les dates ne servent
# qu'au délai médian et à la timeline annuelle.
rga_codes = set(communes_rga.keys())
tim_rga = rga_codes & tim_dates.keys()
dicrim_rga = rga_codes & dicrim_communes

tim_avec_dicrim = tim_rga & dicrim_rga
tim_sans_dicrim = tim_rga - dicrim_rga
sans_tim_avec_dicrim = dicrim_rga - tim_rga
sans_tim_sans_dicrim = rga_codes - tim_rga - dicrim_rga

# Ancienneté des TIM non suivies d'un DICRIM (calculé au 31-12-2025)
buckets_tim_sans_dicrim = {
    "p1_avant_2010": 0,   # ≥ 15 ans d'inaction
    "p2_2010_2014": 0,    # 11-15 ans
    "p3_2015_2019": 0,    # 6-10 ans
    "p4_2020_2022": 0,    # 3-5 ans
    "p5_2023_2025": 0,    # < 3 ans (potentiellement trop récent pour juger)
}
for cod in tim_sans_dicrim:
    y = _parse_year(tim_dates[cod])
    if y is None:
        continue
    if y < 2010:
        buckets_tim_sans_dicrim["p1_avant_2010"] += 1
    elif y <= 2014:
        buckets_tim_sans_dicrim["p2_2010_2014"] += 1
    elif y <= 2019:
        buckets_tim_sans_dicrim["p3_2015_2019"] += 1
    elif y <= 2022:
        buckets_tim_sans_dicrim["p4_2020_2022"] += 1
    else:
        buckets_tim_sans_dicrim["p5_2023_2025"] += 1

# Délai DICRIM après TIM (communes qui ont réagi, DICRIM postérieur à TIM).
# Restreint aux communes où tim_dates ET dicrim_dates sont valides (non 1900).
delays_days: list[int] = []
for cod in tim_avec_dicrim:
    if cod not in dicrim_dates:
        continue  # DICRIM enregistré mais sans date publiable, exclu du calcul
    try:
        t = datetime.fromisoformat(tim_dates[cod].split(" ")[0])
        d = datetime.fromisoformat(dicrim_dates[cod].split(" ")[0])
    except ValueError:
        continue
    if d > t:
        delays_days.append((d - t).days)

delays_days.sort()
median_delay_days = delays_days[len(delays_days) // 2] if delays_days else 0

# Timeline annuelle : DICRIM publiés dans communes RGA + arrêtés CatNat national.
# On utilise dicrim_dates (filtré 1900) car la timeline par an ne peut compter
# que les DICRIM avec date publiable. Le total diffère de la matrice (297 DICRIM
# sans date exploitable), ce qui est documenté dans la méthodologie.
dicrim_rga_by_year: Counter[int] = Counter()
for cod in dicrim_rga & dicrim_dates.keys():
    y = _parse_year(dicrim_dates[cod])
    if y is not None:
        dicrim_rga_by_year[y] += 1

catnat_nat_by_year: Counter[int] = Counter()
for dept_info in catnat_data.get("par_departement", {}).values():
    for year_str, count in dept_info.get("repartition_annuelle", {}).items():
        try:
            catnat_nat_by_year[int(year_str)] += int(count)
        except (ValueError, TypeError):
            continue

timeline_file = OUT / "tim_timeline.csv"
years_timeline = sorted(
    y for y in set(dicrim_rga_by_year) | set(catnat_nat_by_year)
    if 1995 <= y <= 2025
)
with open(timeline_file, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["year", "dicrim_rga_publies", "catnat_secheresse_national"])
    for y in years_timeline:
        w.writerow([y, dicrim_rga_by_year.get(y, 0), catnat_nat_by_year.get(y, 0)])

pct_tim_silencieuses = (
    round(len(tim_sans_dicrim) / len(tim_rga) * 100, 1) if tim_rga else 0.0
)
matrix = {
    "n_rga_total": len(rga_codes),
    "n_tim_rga": len(tim_rga),
    "n_dicrim_rga": len(dicrim_rga),
    "tim_avec_dicrim": len(tim_avec_dicrim),
    "tim_sans_dicrim": len(tim_sans_dicrim),
    "sans_tim_avec_dicrim": len(sans_tim_avec_dicrim),
    "sans_tim_sans_dicrim": len(sans_tim_sans_dicrim),
    "pct_tim_silencieuses": pct_tim_silencieuses,
    "buckets_tim_sans_dicrim": buckets_tim_sans_dicrim,
    "median_delay_days": median_delay_days,
    "median_delay_years": round(median_delay_days / 365.25, 1),
    "n_reactive_dicrim_after_tim": len(delays_days),
}
matrix_file = OUT / "tim_matrix.json"
with open(matrix_file, "w") as f:
    json.dump(matrix, f, ensure_ascii=False, indent=2, sort_keys=True)
    f.write("\n")

print()
print("── Matrice TIM × DICRIM (communes RGA) ──")
print(f"  TIM & DICRIM           : {matrix['tim_avec_dicrim']:>5d}")
print(
    f"  TIM sans DICRIM        : {matrix['tim_sans_dicrim']:>5d}  "
    f"({matrix['pct_tim_silencieuses']}% des TIM)"
)
print(f"    ≥15 ans d'inaction   : {buckets_tim_sans_dicrim['p1_avant_2010']:>5d}")
print(f"    11-15 ans d'inaction : {buckets_tim_sans_dicrim['p2_2010_2014']:>5d}")
print(f"    6-10 ans d'inaction  : {buckets_tim_sans_dicrim['p3_2015_2019']:>5d}")
print(f"    3-5 ans d'inaction   : {buckets_tim_sans_dicrim['p4_2020_2022']:>5d}")
print(f"    < 3 ans (récent)     : {buckets_tim_sans_dicrim['p5_2023_2025']:>5d}")
print(f"  Sans TIM avec DICRIM   : {matrix['sans_tim_avec_dicrim']:>5d}")
print(f"  Sans TIM sans DICRIM   : {matrix['sans_tim_sans_dicrim']:>5d}")
print(
    f"  Délai médian réactif   : {matrix['median_delay_years']} ans "
    f"({matrix['n_reactive_dicrim_after_tim']} communes)"
)
print(f"Fichier timeline : {timeline_file}")
print(f"Fichier matrice  : {matrix_file}")
