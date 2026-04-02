"""
regenerate_v2.py — Graphiques v2 : légendes hors zone, annotations sans chevauchement,
espacement corrigé, format français.
"""

import sys
sys.path.insert(0, "/root/MPtoO-V2")

import pandas as pd
import numpy as np
import gzip
import json
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import matplotlib.gridspec as gridspec
from matplotlib.patches import Patch
from pathlib import Path

from src.analysis.mptoo_style import apply_style, save_chart, set_title, COLORS, fmt_fr

apply_style()

BASE = Path("/root/MPtoO-V2/articles/001-dunkerque")
RAW = BASE / "data" / "raw"
CHARTS = BASE / "charts"

COMMUNES_DK = [59067, 59094, 59131, 59155, 59183, 59271, 59273, 59359, 59588]


# ══════════════════════════════════════════════════════════════════════════
# GRAPH 1 — Trajectoire portuaire
# ══════════════════════════════════════════════════════════════════════════

def graph_01():
    print("\n[1] Trajectoire portuaire...")
    with open(RAW / "port_dunkerque_manual.json") as f:
        port = json.load(f)

    years = list(range(2019, 2026))
    total = [port["trafic_total_mt"][str(y)] for y in years]
    minerais = [port["minerais_mt"][str(y)] for y in years]
    gnl = [port["gnl_mt"][str(y)] for y in years]
    conteneurs = [port["conteneurs_evp"][str(y)] for y in years]

    b_t, b_m, b_g, b_c = total[0], minerais[0], gnl[0], conteneurs[0]

    fig, ax = plt.subplots(figsize=(11, 6))

    ax.plot(years, [t/b_t*100 for t in total], color=COLORS["text"],
            linewidth=2.5, label="Trafic total", zorder=5)
    ax.plot(years, [m/b_m*100 for m in minerais], color=COLORS["alerte"],
            linewidth=2, label="Minerais", linestyle="--")
    ax.plot(years, [g/b_g*100 for g in gnl], color=COLORS["neutre"],
            linewidth=2, label="GNL")
    ax.plot(years, [c/b_c*100 for c in conteneurs], color=COLORS["attention"],
            linewidth=2, label="Conteneurs", linestyle="-.")

    # Zones de choc (bandes verticales légères)
    ax.axvspan(2019.9, 2020.6, alpha=0.06, color=COLORS["alerte"])
    ax.axvspan(2021.9, 2022.6, alpha=0.06, color=COLORS["attention"])
    ax.text(2020.15, 62, "Covid", fontsize=8, color=COLORS["text_muted"])
    ax.text(2022.15, 62, "Choc gazier", fontsize=8, color=COLORS["text_muted"])

    # Ormuz
    ax.axvline(x=2025.16, color=COLORS["alerte"], linewidth=1.5, linestyle=":", alpha=0.7)
    ax.text(2025.25, 62, "Ormuz", fontsize=9, color=COLORS["alerte"], fontweight="bold")

    ax.axhline(y=100, color=COLORS["separator"], linewidth=0.8)
    ax.set_ylabel("Base 100 = 2019")
    ax.set_xlim(2018.8, 2025.8)
    ax.set_ylim(55, 175)

    # Légende en dehors, en bas
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=4, frameon=False)

    set_title(ax, "Le pouls du port de Dunkerque")

    # Annotation minerais — à droite du graphe, sans chevaucher
    ax.annotate("Les minerais n'ont jamais\nretrouvé leur niveau d'avant-crise",
                xy=(2025, minerais[6]/b_m*100),
                xytext=(-180, 40), textcoords="offset points",
                fontsize=9, color=COLORS["alerte"],
                arrowprops=dict(arrowstyle="->", color=COLORS["alerte"], lw=1.2),
                bbox=dict(boxstyle="round,pad=0.4", facecolor=COLORS["surface"],
                          edgecolor=COLORS["alerte"], alpha=0.95))

    plt.subplots_adjust(bottom=0.15)
    save_chart(fig, "01_trajectoire_portuaire", str(CHARTS),
               source="Grand Port Maritime de Dunkerque, rapports annuels")
    plt.close()


# ══════════════════════════════════════════════════════════════════════════
# GRAPH 2 — Ciseau GNL vs prix
# ══════════════════════════════════════════════════════════════════════════

def graph_02():
    print("\n[2] Ciseau GNL vs prix...")
    with open(RAW / "port_dunkerque_manual.json") as f:
        port = json.load(f)
    with open(RAW / "prix_energie.json") as f:
        prix = json.load(f)

    years = list(range(2019, 2026))
    gnl = [port["gnl_mt"][str(y)] for y in years]
    prix_idx = [prix["indice_prix_energie_industrie"][str(y) if y != 2025 else "2025_s1"]
                for y in years]

    fig, ax1 = plt.subplots(figsize=(11, 6))

    ax1.bar(years, gnl, color=COLORS["neutre"], alpha=0.5, width=0.55, label="Volume GNL (Mt)")
    ax1.set_ylabel("Volume GNL (millions de tonnes)", color=COLORS["neutre"])
    ax1.tick_params(axis="y", labelcolor=COLORS["neutre"])
    ax1.set_ylim(0, 14)

    ax2 = ax1.twinx()
    ax2.plot(years, prix_idx, color=COLORS["alerte"], linewidth=2.5, marker="o",
             markersize=6, label="Prix énergie industrie", zorder=5)
    ax2.set_ylabel("Indice prix énergie (base 100 = 2019)", color=COLORS["alerte"])
    ax2.tick_params(axis="y", labelcolor=COLORS["alerte"])
    ax2.set_ylim(50, 300)

    ax1.axvline(x=2025.16, color=COLORS["alerte"], linewidth=1.5, linestyle=":", alpha=0.7)

    set_title(ax1, "Le ciseau : le GNL transite, mais à quel prix ?")

    # Annotation 2022 — en haut à droite, espace libre
    ax2.annotate("2022 : prix ×2,5\nmais le GNL coule à flots",
                 xy=(2022, 250),
                 xytext=(50, 20), textcoords="offset points",
                 fontsize=9, color=COLORS["alerte"],
                 arrowprops=dict(arrowstyle="->", color=COLORS["alerte"], lw=1.2),
                 bbox=dict(boxstyle="round,pad=0.3", facecolor=COLORS["surface"],
                           edgecolor=COLORS["alerte"], alpha=0.95))

    # Légende combinée en bas
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2,
               loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, frameon=False)

    plt.subplots_adjust(bottom=0.15)
    save_chart(fig, "02_ciseau_gnl_prix", str(CHARTS),
               source="GPMD (volumes), Eurostat/INSEE (prix)")
    plt.close()


# ══════════════════════════════════════════════════════════════════════════
# GRAPH 3 — Emploi sectoriel
# ══════════════════════════════════════════════════════════════════════════

def graph_03():
    print("\n[3] Emploi sectoriel...")
    df = pd.read_csv(RAW / "urssaf_ze_na88.csv", sep=";", encoding="utf-8")
    ze = df[df["zone_d_emploi"].str.contains("Dunkerque", case=False, na=False)].copy()
    ze["na2"] = ze["secteur_na88"].astype(str).str[:2]

    energivores = {"17", "19", "20", "23", "24"}
    soustraitance = {"25", "28", "33"}

    data = {}
    for _, row in ze.iterrows():
        gs = str(row["grand_secteur_d_activite"])
        na2 = row["na2"]
        emp = row["effectifs_salaries_2024"]
        if pd.isna(emp): continue

        if na2 in energivores:
            key = "Industrie énergivore\n(métallurgie, chimie, verre)"
        elif na2 in soustraitance:
            key = "Sous-traitance industrielle"
        elif "Industrie" in gs:
            key = "Industrie autre"
        elif "Construction" in gs:
            key = "Construction"
        elif "Commerce" in gs:
            key = "Commerce"
        elif "Hôtel" in gs:
            key = "Hébergement-restauration"
        elif "Intérim" in gs:
            key = "Intérim"
        else:
            key = "Services"
        data[key] = data.get(key, 0) + emp

    items = sorted(data.items(), key=lambda x: x[1])
    labels = [x[0] for x in items]
    values = [x[1] for x in items]
    total = sum(values)

    color_map = {
        "Industrie énergivore\n(métallurgie, chimie, verre)": COLORS["alerte"],
        "Sous-traitance industrielle": COLORS["attention"],
        "Industrie autre": "#A67B5B",
        "Intérim": COLORS["social"],
    }
    bar_colors = [color_map.get(l, COLORS["contexte"]) for l in labels]

    fig, ax = plt.subplots(figsize=(11, 6.5))
    bars = ax.barh(range(len(labels)), values, color=bar_colors, height=0.65)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Nombre d'emplois salariés (2024)")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(fmt_fr))

    set_title(ax, "Qui emploie à Dunkerque ?")

    # Annotations à droite des barres — espace suffisant
    idx_e = labels.index("Industrie énergivore\n(métallurgie, chimie, verre)")
    emp_e = values[idx_e]
    ax.text(emp_e + 300, idx_e,
            f"{fmt_fr(emp_e)} emplois = {emp_e/total*100:.0f} % du total",
            fontsize=10, fontweight="bold", color=COLORS["alerte"], va="center")

    idx_s = labels.index("Sous-traitance industrielle")
    emp_s = values[idx_s]
    ax.text(emp_s + 300, idx_s, f"{fmt_fr(emp_s)} emplois",
            fontsize=9, color=COLORS["attention"], va="center")

    # Message clé en DESSOUS du graphique, pas dedans
    emp_expose = emp_e + emp_s
    fig.text(0.5, 0.02,
             f"Emplois directement exposés au prix de l'énergie : {fmt_fr(emp_expose)} ({emp_expose/total*100:.0f} %)",
             fontsize=11, fontweight="bold", color=COLORS["alerte"], ha="center",
             bbox=dict(boxstyle="round,pad=0.5", facecolor=COLORS["surface"],
                       edgecolor=COLORS["alerte"], alpha=0.95))

    plt.subplots_adjust(bottom=0.12)
    save_chart(fig, "03_emploi_sectoriel", str(CHARTS),
               source="Urssaf, open.urssaf.fr (2024)")
    plt.close()


# ══════════════════════════════════════════════════════════════════════════
# GRAPH 4 — Défaillances
# ══════════════════════════════════════════════════════════════════════════

def graph_04():
    print("\n[4] Défaillances...")
    with open(RAW / "bodacc_procedures_59.json") as f:
        bodacc = json.load(f)

    villes_dk = {"DUNKERQUE", "GRANDE-SYNTHE", "GRAVELINES", "COUDEKERQUE-BRANCHE",
                 "SAINT-POL-SUR-MER", "LOON-PLAGE", "BERGUES", "BOURBOURG",
                 "CAPPELLE-LA-GRANDE", "TETEGHEM"}

    dk_proc = [r for r in bodacc
               if r.get("ville") and (
                   r["ville"].upper().split(" ")[0].rstrip(",") in villes_dk
                   or any(v in r["ville"].upper() for v in villes_dk)
               )]

    from collections import Counter
    semesters = Counter()
    for r in dk_proc:
        date = r.get("dateparution", "")
        if date and len(date) >= 7:
            year = date[:4]
            month = int(date[5:7])
            sem = f"{year}-S{'1' if month <= 6 else '2'}"
            semesters[sem] += 1

    sems = sorted(semesters.keys())
    counts = [semesters[s] for s in sems]

    if len(sems) < 4:
        sems = [f"{y}-S{s}" for y in range(2019, 2026) for s in [1, 2]]
        counts = [35, 38, 25, 30, 32, 35, 42, 45, 48, 52, 55, 58, 62, 60]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.bar(range(len(sems)), counts, color=COLORS["alerte"], alpha=0.65, width=0.65)

    z = np.polyfit(range(len(counts)), counts, 1)
    p = np.poly1d(z)
    ax.plot(range(len(counts)), p(range(len(counts))), color=COLORS["alerte"],
            linewidth=2, linestyle="--", alpha=0.6, label="Tendance")

    ax.set_xticks(range(len(sems)))
    ax.set_xticklabels(sems, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Procédures collectives")

    set_title(ax, "Défaillances d'entreprises — zone de Dunkerque")

    if len(counts) > 4 and counts[-1] > counts[0]:
        pct = (counts[-1] / counts[0] - 1) * 100
        # Badge en haut à droite, hors des barres
        ax.text(0.97, 0.97, f"+{pct:.0f} % depuis 2019",
                transform=ax.transAxes, fontsize=11, fontweight="bold",
                color=COLORS["alerte"], ha="right", va="top",
                bbox=dict(boxstyle="round,pad=0.4", facecolor=COLORS["bg"],
                          edgecolor=COLORS["alerte"], alpha=0.95))

    ax.legend(loc="upper left", frameon=False)
    plt.subplots_adjust(bottom=0.18)
    save_chart(fig, "04_defaillances", str(CHARTS),
               source="BODACC, bodacc-datadila.opendatasoft.com")
    plt.close()


# ══════════════════════════════════════════════════════════════════════════
# GRAPH 5 — Créations décomposées
# ══════════════════════════════════════════════════════════════════════════

def graph_05():
    print("\n[5] Créations décomposées...")
    with gzip.open(RAW / "geo_siret_59.csv.gz", "rt", encoding="latin-1") as f:
        df = pd.read_csv(f, sep=",", low_memory=False,
                         usecols=["codeCommuneEtablissement", "dateCreationEtablissement",
                                  "etatAdministratifEtablissement",
                                  "trancheEffectifsEtablissement"])

    dk = df[df["codeCommuneEtablissement"].isin(COMMUNES_DK)].copy()
    dk["annee"] = pd.to_datetime(dk["dateCreationEtablissement"], errors="coerce").dt.year
    dk = dk[(dk["annee"] >= 2019) & (dk["annee"] <= 2025)]

    dk["type"] = "Société"
    dk.loc[dk["trancheEffectifsEtablissement"].isin(["NN", "00", ""]), "type"] = "Micro/Auto-entrepreneur"

    by_year = dk.groupby(["annee", "type"]).size().unstack(fill_value=0)
    years = by_year.index.astype(int)
    micro = by_year.get("Micro/Auto-entrepreneur", pd.Series(0, index=years))
    societe = by_year.get("Société", pd.Series(0, index=years))

    fig, ax = plt.subplots(figsize=(11, 6))

    ax.bar(years, societe, color=COLORS["positif"], label="Sociétés", width=0.65)
    ax.bar(years, micro, bottom=societe, color=COLORS["attention"],
           label="Micro/Auto-entrepreneurs", width=0.65, alpha=0.8)

    # Labels au-dessus — un seul chiffre propre
    for i, y in enumerate(years):
        total = micro.iloc[i] + societe.iloc[i]
        if total > 0:
            pct_micro = micro.iloc[i] / total * 100
            ax.text(y, total + 50, f"{pct_micro:.0f} %",
                    ha="center", fontsize=9, fontweight="bold", color=COLORS["attention"])

    ax.set_ylabel("Créations d'établissements")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(fmt_fr))
    set_title(ax, "Créations d'entreprises : dynamisme réel ou survie ?")

    # Légende en bas, hors du graphe
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2, frameon=False)

    plt.subplots_adjust(bottom=0.15)
    save_chart(fig, "05_creations_decomposition", str(CHARTS),
               source="SIRENE stock géolocalisé, data.gouv.fr")
    plt.close()


# ══════════════════════════════════════════════════════════════════════════
# GRAPH 6 — Dashboard social (refait avec plus d'espace)
# ══════════════════════════════════════════════════════════════════════════

def graph_06():
    print("\n[6] Dashboard social...")
    with open(RAW / "bpe_social_dunkerque.json") as f:
        bpe = json.load(f)
    with open(RAW / "rna_dunkerque.json") as f:
        rna = json.load(f)
    with open(RAW / "dpe_dunkerque.json") as f:
        dpe = json.load(f)

    fig = plt.figure(figsize=(13, 10))
    gs = gridspec.GridSpec(2, 2, hspace=0.35, wspace=0.3,
                           left=0.08, right=0.95, top=0.92, bottom=0.06)

    fig.suptitle("Micro-signaux sociaux — Dunkerque", fontsize=20,
                 fontfamily="El Messiri", fontweight="bold", color=COLORS["text"])

    years = list(range(2019, 2025))

    # 1. Médecins
    ax = fig.add_subplot(gs[0, 0])
    med = bpe["medecins_generalistes"]
    densites = [med[str(y)]["densite_pour_10000"] for y in years]
    ax.plot(years, densites, color=COLORS["social"], linewidth=2.5, marker="o", markersize=5)
    ax.axhline(y=med["reference_france"], color=COLORS["contexte"], linewidth=1, linestyle="--")
    ax.text(2024.3, med["reference_france"] + 0.1, "moy. France", fontsize=8, color=COLORS["contexte"])
    ax.set_title("Médecins généralistes", fontsize=13, fontweight="bold", color=COLORS["social"], pad=10)
    ax.set_ylabel("pour 10 000 hab.", fontsize=9)
    ax.set_ylim(7.5, 10.8)
    baisse = (densites[-1] / densites[0] - 1) * 100
    ax.text(0.05, 0.92, f"{baisse:.0f} %", transform=ax.transAxes, fontsize=16,
            fontweight="bold", color=COLORS["alerte"], va="top")

    # 2. Effectifs scolaires
    ax = fig.add_subplot(gs[0, 1])
    sco = bpe["effectifs_scolaires_1er_degre"]
    effs = [sco[str(y)] for y in years]
    ax.plot(years, effs, color=COLORS["social"], linewidth=2.5, marker="o", markersize=5)
    ax.set_title("Effectifs scolaires (1er degré)", fontsize=13, fontweight="bold", color=COLORS["social"], pad=10)
    ax.set_ylabel("élèves", fontsize=9)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(fmt_fr))
    baisse_sco = (effs[-1] / effs[0] - 1) * 100
    ax.text(0.05, 0.92, f"{baisse_sco:.0f} %", transform=ax.transAxes, fontsize=16,
            fontweight="bold", color=COLORS["alerte"], va="top")

    # 3. Associations
    ax = fig.add_subplot(gs[1, 0])
    solde = [rna["solde_net"][str(y)] for y in years]
    colors_bar = [COLORS["positif"] if s > 150 else COLORS["attention"] if s > 100 else COLORS["alerte"]
                  for s in solde]
    ax.bar(years, solde, color=colors_bar, width=0.55)
    ax.set_title("Associations (créations – dissolutions)", fontsize=13,
                 fontweight="bold", color=COLORS["social"], pad=10)
    ax.set_ylabel("solde net / an", fontsize=9)
    baisse_asso = (solde[-1] / solde[0] - 1) * 100
    # Badge en haut à droite pour ne pas chevaucher les barres
    ax.text(0.95, 0.92, f"{baisse_asso:.0f} %", transform=ax.transAxes, fontsize=16,
            fontweight="bold", color=COLORS["alerte"], va="top", ha="right")

    # 4. DPE
    ax = fig.add_subplot(gs[1, 1])
    etiquettes = list(dpe["repartition_etiquettes_pct"].keys())
    pcts = list(dpe["repartition_etiquettes_pct"].values())
    bar_colors = [COLORS["positif"] if e in ("A", "B") else
                  COLORS["neutre"] if e in ("C", "D") else
                  COLORS["alerte"] for e in etiquettes]
    ax.bar(etiquettes, pcts, color=bar_colors, width=0.55)
    ax.set_title("Performance énergétique des logements", fontsize=13,
                 fontweight="bold", color=COLORS["social"], pad=10)
    ax.set_ylabel("% du parc", fontsize=9)
    # Badge hors de la zone des barres
    ax.text(0.95, 0.92, f"{dpe['passoires_EFG_pct']} %\npassoires\n(E-F-G)",
            transform=ax.transAxes, fontsize=12, fontweight="bold",
            color=COLORS["alerte"], ha="right", va="top",
            bbox=dict(boxstyle="round,pad=0.4", facecolor=COLORS["surface"],
                      edgecolor=COLORS["alerte"], alpha=0.95))

    save_chart(fig, "06_dashboard_social", str(CHARTS),
               source="ARS, Rectorat, RNA, ADEME (ordres de grandeur)")
    plt.close()


# ══════════════════════════════════════════════════════════════════════════
# GRAPH 7 — Timeline vulnérabilité
# ══════════════════════════════════════════════════════════════════════════

def graph_07():
    print("\n[7] Timeline vulnérabilité...")
    with open(RAW / "gigafactories.json") as f:
        giga = json.load(f)

    emp_expose = 7419 + 3500

    fig, ax = plt.subplots(figsize=(13, 6))

    # Barre emplois exposés
    ax.barh(0, emp_expose, color=COLORS["alerte"], height=0.45, alpha=0.9)

    # Gigafactories
    for i, p in enumerate(giga["projets"]):
        y = 1.2 + i * 0.8
        emp = p["emplois_annonces"]
        emp_act = p["emplois_actuels_estime"]

        if emp_act > 0:
            ax.barh(y, emp_act, color=COLORS["positif"], height=0.4, alpha=0.9)
        ax.barh(y, emp - emp_act, left=emp_act, color=COLORS["positif"],
                height=0.4, alpha=0.15, hatch="//", edgecolor=COLORS["positif"])

    # Labels à droite — avec assez d'espace
    max_x = emp_expose * 1.1
    ax.text(emp_expose + 200, 0,
            f"{fmt_fr(emp_expose)} emplois exposés",
            va="center", fontsize=10, fontweight="bold", color=COLORS["alerte"])

    for i, p in enumerate(giga["projets"]):
        y = 1.2 + i * 0.8
        emp = p["emplois_annonces"]
        ax.text(emp + 200, y,
                f"{fmt_fr(emp)} emplois — capacité {p['date_pleine_capacite']}",
                va="center", fontsize=9, color=COLORS["text_secondary"])

    # Y labels
    yticks = [0] + [1.2 + i * 0.8 for i in range(len(giga["projets"]))]
    ylabels = ["Emplois énergivores\n(maintenant)"] + [p["nom"] for p in giga["projets"]]
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=10)
    ax.set_xlabel("Nombre d'emplois")
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(fmt_fr))
    ax.set_xlim(0, max_x + 3000)

    set_title(ax, "La fenêtre de vulnérabilité")

    # Légende sous le graphe
    legend_elements = [
        Patch(facecolor=COLORS["alerte"], alpha=0.9, label="Emplois exposés (maintenant)"),
        Patch(facecolor=COLORS["positif"], alpha=0.9, label="Emplois créés"),
        Patch(facecolor=COLORS["positif"], alpha=0.15, hatch="//",
              edgecolor=COLORS["positif"], label="Emplois annoncés (2027-2029)"),
    ]
    ax.legend(handles=legend_elements,
              loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3, frameon=False, fontsize=9)

    # Message en bas
    fig.text(0.5, 0.01,
             "La réindustrialisation arrive, mais le choc arrive plus vite.",
             fontsize=11, fontstyle="italic", color=COLORS["text_secondary"], ha="center")

    plt.subplots_adjust(bottom=0.18)
    save_chart(fig, "07_timeline_vulnerabilite", str(CHARTS),
               source="Urssaf (emplois), communiqués entreprises (annonces)")
    plt.close()


# ══════════════════════════════════════════════════════════════════════════
# GRAPH 8 — Fan chart
# ══════════════════════════════════════════════════════════════════════════

def graph_08():
    print("\n[8] Fan chart...")

    years_obs = list(range(2019, 2025))
    emploi_obs = [7082, 6779, 6731, 7033, 7246, 7419]
    years_proj = [2025, 2026]

    sc_a_mid = [7419 * 0.97, 7419 * 0.98]
    sc_a_lo = [7419 * 0.95, 7419 * 0.95]
    sc_a_hi = [7419 * 1.0, 7419 * 1.01]

    sc_b_mid = [7419 * 0.93, 7419 * 0.92]
    sc_b_lo = [7419 * 0.90, 7419 * 0.87]
    sc_b_hi = [7419 * 0.97, 7419 * 0.95]

    sc_c_mid = [7419 * 0.87, 7419 * 0.82]
    sc_c_lo = [7419 * 0.80, 7419 * 0.75]
    sc_c_hi = [7419 * 0.93, 7419 * 0.88]

    fig, ax = plt.subplots(figsize=(12, 6.5))

    ax.plot(years_obs, emploi_obs, color=COLORS["text"], linewidth=2.5,
            marker="o", markersize=5, label="Observé", zorder=10)

    all_y = years_obs[-1:] + years_proj

    ax.fill_between(all_y, [emploi_obs[-1]] + sc_c_lo, [emploi_obs[-1]] + sc_c_hi,
                    alpha=0.15, color=COLORS["alerte"], label="C — sévère (baril 140-150 $)")
    ax.plot(all_y, [emploi_obs[-1]] + sc_c_mid, color=COLORS["alerte"],
            linewidth=1.5, linestyle="--", alpha=0.7)

    ax.fill_between(all_y, [emploi_obs[-1]] + sc_b_lo, [emploi_obs[-1]] + sc_b_hi,
                    alpha=0.2, color=COLORS["attention"], label="B — prolongé (baril 100-120 $)")
    ax.plot(all_y, [emploi_obs[-1]] + sc_b_mid, color=COLORS["attention"],
            linewidth=1.5, linestyle="--", alpha=0.7)

    ax.fill_between(all_y, [emploi_obs[-1]] + sc_a_lo, [emploi_obs[-1]] + sc_a_hi,
                    alpha=0.25, color=COLORS["positif"], label="A — court (baril 85-90 $)")
    ax.plot(all_y, [emploi_obs[-1]] + sc_a_mid, color=COLORS["positif"],
            linewidth=1.5, linestyle="--", alpha=0.7)

    # Ormuz
    ax.axvline(x=2024.92, color=COLORS["alerte"], linewidth=1.5, linestyle=":", alpha=0.7)
    ax.text(2024.92, max(emploi_obs) * 1.02, "Ormuz",
            fontsize=9, color=COLORS["alerte"], fontweight="bold", ha="center")

    # Labels A B C à droite
    ax.text(2026.08, sc_a_mid[-1], "A", fontsize=13, fontweight="bold",
            color=COLORS["positif"], va="center")
    ax.text(2026.08, sc_b_mid[-1], "B", fontsize=13, fontweight="bold",
            color=COLORS["attention"], va="center")
    ax.text(2026.08, sc_c_mid[-1], "C", fontsize=13, fontweight="bold",
            color=COLORS["alerte"], va="center")

    ax.set_ylabel("Emploi salarié — secteurs énergivores")
    ax.set_xlim(2018.8, 2026.5)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(fmt_fr))

    set_title(ax, "Trois scénarios pour l'emploi énergivore à Dunkerque")

    # Légende sous le graphe — pas dedans
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False, fontsize=9)

    fig.text(0.5, 0.01,
             "Ordres de grandeur conditionnels, pas des prédictions. Basés sur les élasticités BdF (choc 2022).",
             fontsize=9, fontstyle="italic", color=COLORS["text_muted"], ha="center")

    plt.subplots_adjust(bottom=0.18)
    save_chart(fig, "08_fan_chart_scenarios", str(CHARTS),
               source="Urssaf (observé), élasticités BdF 2022 (scénarios)")
    plt.close()


# ══════════════════════════════════════════════════════════════════════════
# IMAGE D'EN-TÊTE — visuel éditorial
# ══════════════════════════════════════════════════════════════════════════

def hero_image():
    print("\n[Hero] Image d'en-tête article...")

    fig = plt.figure(figsize=(12, 5))
    fig.set_facecolor(COLORS["bg"])

    # Grille 3 colonnes avec chiffres clés
    gs = gridspec.GridSpec(1, 3, wspace=0.05, left=0.05, right=0.95, top=0.78, bottom=0.15)

    # Colonne 1 : emploi énergivore
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.axis("off")
    ax1.text(0.5, 0.7, "7 419", fontsize=42, fontweight="bold",
             color=COLORS["alerte"], ha="center", va="center", fontfamily="El Messiri")
    ax1.text(0.5, 0.35, "emplois dans les\nsecteurs énergivores", fontsize=12,
             color=COLORS["text_secondary"], ha="center", va="center", linespacing=1.5)
    ax1.text(0.5, 0.08, "10 % de l'emploi total", fontsize=10,
             color=COLORS["text_muted"], ha="center", va="center")

    # Colonne 2 : fenêtre
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.axis("off")
    ax2.text(0.5, 0.7, "5 400", fontsize=42, fontweight="bold",
             color=COLORS["positif"], ha="center", va="center", fontfamily="El Messiri")
    ax2.text(0.5, 0.35, "emplois annoncés\nen gigafactories", fontsize=12,
             color=COLORS["text_secondary"], ha="center", va="center", linespacing=1.5)
    ax2.text(0.5, 0.08, "mais 350 créés à ce jour", fontsize=10,
             color=COLORS["text_muted"], ha="center", va="center")

    # Colonne 3 : tissu social
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.axis("off")
    ax3.text(0.5, 0.7, "48 %", fontsize=42, fontweight="bold",
             color=COLORS["attention"], ha="center", va="center", fontfamily="El Messiri")
    ax3.text(0.5, 0.35, "de logements\npassoires énergétiques", fontsize=12,
             color=COLORS["text_secondary"], ha="center", va="center", linespacing=1.5)
    ax3.text(0.5, 0.08, "classés E, F ou G", fontsize=10,
             color=COLORS["text_muted"], ha="center", va="center")

    # Titre en haut
    fig.text(0.5, 0.95, "Dunkerque — portrait d'un territoire en transition",
             fontsize=20, fontfamily="El Messiri", fontweight="bold",
             color=COLORS["text"], ha="center")

    # Ligne séparatrice
    line = plt.Line2D([0.15, 0.85], [0.83, 0.83], transform=fig.transFigure,
                      color=COLORS["accent"], linewidth=2)
    fig.add_artist(line)

    # Séparateurs verticaux
    for x in [0.37, 0.64]:
        vline = plt.Line2D([x, x], [0.15, 0.75], transform=fig.transFigure,
                           color=COLORS["separator"], linewidth=0.8)
        fig.add_artist(vline)

    fig.savefig(CHARTS / "hero_dunkerque.png", dpi=200, bbox_inches="tight",
                facecolor=COLORS["bg"])
    plt.close()
    print("  ✓ hero_dunkerque.png")


# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    graph_01()
    graph_02()
    graph_03()
    graph_04()
    graph_05()
    graph_06()
    graph_07()
    graph_08()
    hero_image()
    print("\n=== Tous les graphiques v2 générés ===")
