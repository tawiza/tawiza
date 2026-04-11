"""
02_charts.py — 8 graphiques + œil Tawiza animé pour l'article RGA
Article 002 : Risque argile, le silence communal
"""
import sys
from pathlib import Path

# Add repo root to path for src.analysis imports (open-source tawiza_style)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

import json

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analysis.tawiza_style import COLORS, apply_style, fmt_fr, save_chart

apply_style()

BASE = Path("/root/tawiza/articles/002-rga-argiles")
DATA = BASE / "data" / "processed" / "departements_rga.csv"
GEO = BASE / "data" / "raw" / "departements.geojson"
CHARTS = BASE / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA)
gdf = gpd.read_file(GEO)
DEPT_NAMES = dict(zip(gdf["code"], gdf["nom"]))

# Position standardisée pour les sources : toujours y=0.02, centré, taille lisible
SOURCE_Y = 0.02
SOURCE_STYLE = {"ha": "center", "fontsize": 9.5, "color": COLORS["text_muted"], "style": "italic"}
BOTTOM_MARGIN = 0.10


def add_source(fig, text):
    fig.text(0.5, SOURCE_Y, text, **SOURCE_STYLE)


# ════════════════════════════════════════════════════════════════════════════
# CHART 1 — La carte du silence
# ════════════════════════════════════════════════════════════════════════════

def chart_01_carte_silence():
    merged = gdf.merge(df, left_on="code", right_on="code_dept", how="left")
    merged["pct_sans_dicrim"] = merged["pct_sans_dicrim"].fillna(0)

    fig, ax = plt.subplots(1, 1, figsize=(10, 11))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    fig.subplots_adjust(bottom=BOTTOM_MARGIN)

    merged[merged["communes_rga"] == 0].plot(
        ax=ax, color=COLORS["separator"], edgecolor="white", linewidth=0.5
    )
    rga = merged[merged["communes_rga"] > 0].copy()
    rga.plot(
        ax=ax, column="pct_sans_dicrim", cmap="YlOrRd", vmin=0, vmax=100,
        edgecolor="white", linewidth=0.5, legend=True,
        legend_kwds={
            "label": "% communes RGA sans DICRIM",
            "orientation": "horizontal", "shrink": 0.6, "pad": 0.02,
        },
    )

    ax.set_xlim(-5.5, 10)
    ax.set_ylim(41, 51.5)
    ax.set_axis_off()
    ax.set_title("La carte du silence", fontsize=20, fontweight="bold",
                 color=COLORS["text"], pad=15)
    # Sous-titre explicatif
    ax.text(0.5, 0.06,
            "Plus la couleur est foncée, plus le pourcentage de communes\n"
            "qui n'ont pas informé leurs habitants est élevé. Gris = pas de risque argile.",
            transform=ax.transAxes, ha="center", fontsize=10,
            color=COLORS["text_secondary"])

    add_source(fig, "Source : base GASPAR, ministère de la Transition écologique (déc. 2025). Tawiza")
    save_chart(fig, "01_carte_silence", output_dir=str(CHARTS))
    plt.close()
    print("✓ 01_carte_silence")


# ════════════════════════════════════════════════════════════════════════════
# CHART 2 — Top 15 départements
# ════════════════════════════════════════════════════════════════════════════

def chart_02_top_sans_dicrim():
    rga = df[df["communes_rga"] > 0].copy()
    rga = rga.sort_values("communes_rga_sans_dicrim", ascending=True).tail(15)

    fig, ax = plt.subplots(figsize=(12, 8))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    fig.subplots_adjust(bottom=BOTTOM_MARGIN, left=0.22)

    labels = [f"{row['code_dept']} {DEPT_NAMES.get(row['code_dept'], '')}"
              for _, row in rga.iterrows()]
    sans = rga["communes_rga_sans_dicrim"].values
    avec = rga["communes_rga_dicrim"].values

    y = range(len(labels))
    ax.barh(y, sans, color=COLORS["alerte"], label="Sans DICRIM", height=0.7)
    ax.barh(y, avec, left=sans, color=COLORS["positif"],
            label="Avec DICRIM", height=0.7, alpha=0.7)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Nombre de communes", fontsize=11)

    for i, (_, row) in enumerate(rga.iterrows()):
        total = row["communes_rga"]
        pct = row["pct_sans_dicrim"]
        ax.text(total + 5, i, f"{pct:.0f}%", va="center", fontsize=9,
                color=COLORS["alerte"], fontweight="bold")

    ax.legend(loc="lower right", frameon=False, fontsize=10)
    ax.set_title("Les 15 départements avec le plus de communes exposées\n"
                 "au risque argile qui n'ont pas informé leurs habitants",
                 fontsize=13, fontweight="bold", color=COLORS["text"], pad=15)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    add_source(fig, "Lecture : en Gironde, 497 communes sur 527 n'ont pas produit de DICRIM (94%). "
               "Source : GASPAR (déc. 2025). Tawiza")
    save_chart(fig, "02_top_sans_dicrim", output_dir=str(CHARTS))
    plt.close()
    print("✓ 02_top_sans_dicrim")


# ════════════════════════════════════════════════════════════════════════════
# CHART 3 — Scatter : prix médian DVF vs communes RGA sans DICRIM
# ════════════════════════════════════════════════════════════════════════════

def chart_03_patrimoine_expose():
    rga = df[(df["communes_rga"] > 20) & (df["prix_median_maison"].notna())].copy()

    fig, ax = plt.subplots(figsize=(11, 8))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    fig.subplots_adjust(bottom=0.14, right=0.72)

    sizes = rga["communes_rga"] * 0.8
    colors = [COLORS["alerte"] if p > 70 else COLORS["attention"] if p > 50
              else COLORS["positif"] for p in rga["pct_sans_dicrim"]]

    ax.scatter(rga["prix_median_maison"] / 1000, rga["pct_sans_dicrim"],
               s=sizes, c=colors, alpha=0.7, edgecolors="white", linewidth=0.5)

    for _, row in rga.iterrows():
        if row["pct_sans_dicrim"] > 93 or row["prix_median_maison"] > 500000:
            ax.annotate(DEPT_NAMES.get(row["code_dept"], row["code_dept"]),
                        (row["prix_median_maison"] / 1000, row["pct_sans_dicrim"]),
                        fontsize=8, color=COLORS["text"], fontweight="bold",
                        textcoords="offset points", xytext=(8, -12),
                        bbox={"boxstyle": "round,pad=0.2", "fc": COLORS["bg"],
                              "ec": "none", "alpha": 0.8})

    ax.set_xlabel("Prix médian des maisons (milliers d'euros)", fontsize=11)
    ax.set_ylabel("% communes exposées sans DICRIM", fontsize=11)
    ax.set_title("Patrimoine exposé, habitants non informés",
                 fontsize=14, fontweight="bold", color=COLORS["text"], pad=15)

    # Légende DEHORS du graphique, à droite
    legend_x = 1.04
    ax.text(legend_x, 0.95, "Comment lire", transform=ax.transAxes,
            fontsize=10, fontweight="bold", color=COLORS["text"])
    ax.text(legend_x, 0.88, "Chaque point = 1 département", transform=ax.transAxes,
            fontsize=9, color=COLORS["text_secondary"])
    ax.text(legend_x, 0.81, "Taille = nombre de communes\nexposées au risque argile",
            transform=ax.transAxes, fontsize=9, color=COLORS["text_secondary"])

    for clr, label, yp in [
        (COLORS["alerte"], "Plus de 70% sans DICRIM", 0.70),
        (COLORS["attention"], "50 à 70% sans DICRIM", 0.64),
        (COLORS["positif"], "Moins de 50% sans DICRIM", 0.58),
    ]:
        ax.plot(legend_x, yp, "o", markersize=10, color=clr, alpha=0.7,
                transform=ax.transAxes, clip_on=False)
        ax.text(legend_x + 0.04, yp, label, transform=ax.transAxes,
                fontsize=8.5, color=COLORS["text_secondary"], va="center")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    add_source(fig, "Sources : GASPAR (déc. 2025), DVF 2024 (data.gouv.fr). Tawiza")
    save_chart(fig, "03_patrimoine_expose", output_dir=str(CHARTS))
    plt.close()
    print("✓ 03_patrimoine_expose")


# ════════════════════════════════════════════════════════════════════════════
# CHART 4 — La surprime invisible
# ════════════════════════════════════════════════════════════════════════════

def chart_04_surprime():
    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    fig.subplots_adjust(bottom=0.15)

    categories = [
        "Surprime CatNat\ncollectée par an",
        "Coût sinistres RGA\npar an (2018-2022)",
        "Fonds prévention\n(11 départements)",
    ]
    values = [720, 1500, 17]
    colors_bars = [COLORS["attention"], COLORS["alerte"], COLORS["positif"]]

    bars = ax.bar(categories, values, color=colors_bars, width=0.45, edgecolor="white")

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 30,
                f"{val} M€", ha="center", fontsize=15, fontweight="bold",
                color=COLORS["text"])

    ax.set_ylabel("Millions d'euros par an", fontsize=12)
    ax.tick_params(axis="x", labelsize=11)
    ax.set_title("On collecte plus, on répare plus, on prévient peu",
                 fontsize=15, fontweight="bold", color=COLORS["text"], pad=15)
    ax.set_ylim(0, 1800)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    add_source(fig, "Sources : France Assureurs, CCR, Service-public.fr. Tawiza")
    save_chart(fig, "04_surprime_invisible", output_dir=str(CHARTS))
    plt.close()
    print("✓ 04_surprime_invisible")


# ════════════════════════════════════════════════════════════════════════════
# CHART 5 — L'explosion des sinistres
# ════════════════════════════════════════════════════════════════════════════

def chart_05_explosion():
    periodes = ["1995-2002", "2003-2010", "2011-2017", "2018-2022"]
    couts = [300, 400, 450, 1500]

    fig, ax = plt.subplots(figsize=(10, 6.5))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    fig.subplots_adjust(bottom=BOTTOM_MARGIN, top=0.85)

    colors_bars = [COLORS["neutre"], COLORS["neutre"], COLORS["attention"], COLORS["alerte"]]
    bars = ax.bar(periodes, couts, color=colors_bars, width=0.5, edgecolor="white")

    # Valeurs au-dessus des barres
    for bar, val in zip(bars, couts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 25,
                f"{val} M€/an", ha="center", fontsize=12, fontweight="bold",
                color=COLORS["text"])

    # Pas de flèche : texte annotation à côté de la barre, aligné proprement
    ax.text(3.38, 1200, "2022 : année record", fontsize=10, color=COLORS["alerte"],
            fontweight="bold", ha="left")
    ax.text(3.38, 1100, "7 946 arrêtés CatNat", fontsize=9, color=COLORS["alerte"],
            ha="left")
    ax.text(3.38, 1010, "sécheresse", fontsize=9, color=COLORS["alerte"],
            ha="left")

    ax.set_ylabel("Coût annuel moyen (M€)", fontsize=11)
    ax.set_title("Le coût des sinistres argile a quadruplé en 20 ans",
                 fontsize=14, fontweight="bold", color=COLORS["text"], pad=15)
    ax.set_ylim(0, 1750)
    ax.set_xlim(-0.5, 4.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    add_source(fig, "Source : CCR (rapports annuels), estimation par période. Tawiza")
    save_chart(fig, "05_explosion_sinistres", output_dir=str(CHARTS))
    plt.close()
    print("✓ 05_explosion_sinistres")


# ════════════════════════════════════════════════════════════════════════════
# CHART 6 — La spirale (retravaillée : numérotée, plus grande, plus claire)
# ════════════════════════════════════════════════════════════════════════════

def chart_06_spirale():
    fig, ax = plt.subplots(figsize=(10, 10))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    fig.subplots_adjust(bottom=0.08)

    labels = [
        "1. Sécheresse\net sol argileux",
        "2. Fissures sur\nla maison",
        "3. Valeur du bien\nen chute",
        "4. Propriétaire piégé\n(ne peut ni vendre\nni réparer)",
        "5. Recettes fiscales\nde la commune\nen baisse",
        "6. Moins de budget\npour la prévention",
    ]
    bg_colors = [
        COLORS["attention"], COLORS["alerte"], COLORS["alerte"],
        COLORS["structurel"], COLORS["neutre"], COLORS["social"],
    ]

    n = len(labels)
    R = 3.2       # rayon du cercle
    r_node = 1.3  # rayon de chaque noeud
    angles = [np.pi / 2 - i * 2 * np.pi / n for i in range(n)]

    # Positions des centres
    cx = [R * np.cos(a) for a in angles]
    cy = [R * np.sin(a) for a in angles]

    # Dessiner les noeuds
    for i in range(n):
        circle = plt.Circle((cx[i], cy[i]), r_node, color=bg_colors[i],
                             alpha=0.15, ec=bg_colors[i], lw=2.5)
        ax.add_patch(circle)
        ax.text(cx[i], cy[i], labels[i], ha="center", va="center",
                fontsize=11, fontweight="bold", color=COLORS["text"],
                linespacing=1.3)

    # Dessiner les flèches : du bord d'un noeud au bord du suivant
    for i in range(n):
        j = (i + 1) % n
        # Direction du centre i vers le centre j
        dx = cx[j] - cx[i]
        dy = cy[j] - cy[i]
        dist = np.sqrt(dx**2 + dy**2)
        ux, uy = dx / dist, dy / dist
        # Point de départ : bord du cercle i (+ petit espace)
        x1 = cx[i] + ux * (r_node + 0.12)
        y1 = cy[i] + uy * (r_node + 0.12)
        # Point d'arrivée : bord du cercle j (- petit espace)
        x2 = cx[j] - ux * (r_node + 0.12)
        y2 = cy[j] - uy * (r_node + 0.12)

        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                     arrowprops={"arrowstyle": "-|>", "color": COLORS["accent"],
                                 "lw": 2.5, "shrinkA": 0, "shrinkB": 0})

    ax.set_xlim(-5.5, 5.5)
    ax.set_ylim(-5.5, 5.5)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title("La spirale : quand le sol emporte tout",
                 fontsize=18, fontweight="bold", color=COLORS["text"], pad=20)
    ax.text(0.5, 0.06,
            "Chaque étape renforce la suivante. Le cycle se répète et s'aggrave.",
            transform=ax.transAxes, ha="center", fontsize=11,
            color=COLORS["text_secondary"])

    add_source(fig, "Source : analyse Tawiza")
    save_chart(fig, "06_spirale_cumulative", output_dir=str(CHARTS))
    plt.close()
    print("✓ 06_spirale_cumulative")


# ════════════════════════════════════════════════════════════════════════════
# CHART 7 — L'effet ciseaux : DICRIM ↓ vs CatNat ↑
# ════════════════════════════════════════════════════════════════════════════

def chart_07_effet_ciseaux():
    tl = pd.read_csv(BASE / "data" / "processed" / "tim_timeline.csv")
    # Tronqué à 2023 : les années 2024-2025 sont en cours d'instruction côté
    # CatNat et sous-déclarées dans la base GASPAR de déc 2025.
    tl = tl[(tl["year"] >= 2000) & (tl["year"] <= 2023)].copy()

    fig, ax_l = plt.subplots(figsize=(11, 6.5))
    fig.patch.set_facecolor(COLORS["bg"])
    ax_l.set_facecolor(COLORS["bg"])
    fig.subplots_adjust(bottom=0.16, left=0.10, right=0.88, top=0.86)

    ax_r = ax_l.twinx()

    (line_d,) = ax_l.plot(
        tl["year"], tl["dicrim_rga_publies"],
        color=COLORS["structurel"], linewidth=3,
        marker="o", markersize=6,
        label="DICRIM publiés dans communes RGA",
    )
    (line_c,) = ax_r.plot(
        tl["year"], tl["catnat_secheresse_national"],
        color=COLORS["alerte"], linewidth=3,
        marker="s", markersize=6,
        label="Arrêtés CatNat sécheresse (national, toutes communes)",
    )

    ax_l.set_xlabel("Année", fontsize=11)
    ax_l.set_ylabel("DICRIM publiés par an",
                    color=COLORS["structurel"], fontsize=11, fontweight="bold")
    ax_r.set_ylabel("Arrêtés CatNat sécheresse par an",
                    color=COLORS["alerte"], fontsize=11, fontweight="bold")
    ax_l.tick_params(axis="y", colors=COLORS["structurel"])
    ax_r.tick_params(axis="y", colors=COLORS["alerte"])

    ax_l.set_ylim(0, 650)
    ax_r.set_ylim(0, 9000)

    ax_l.set_title(
        "L'effet ciseaux : quand le risque montait, l'information s'arrêtait",
        fontsize=14, fontweight="bold", color=COLORS["text"], pad=15,
    )

    # Annotation pic DICRIM 2013
    ax_l.annotate(
        "pic 2013 : 531 DICRIM publiés\ndans des communes argile",
        xy=(2013, 531), xytext=(2007, 610),
        fontsize=9, color=COLORS["structurel"], ha="center",
        arrowprops={"arrowstyle": "->", "color": COLORS["structurel"], "lw": 1.2},
    )
    # Annotation record CatNat 2022
    ax_r.annotate(
        "record 2022 : 7 946 arrêtés\nCatNat sécheresse",
        xy=(2022, 7946), xytext=(2018, 6900),
        fontsize=9, color=COLORS["alerte"], ha="center",
        arrowprops={"arrowstyle": "->", "color": COLORS["alerte"], "lw": 1.2},
    )
    # Annotation effondrement 2023
    ax_l.annotate(
        "82 en 2023",
        xy=(2023, 82), xytext=(2020.5, 240),
        fontsize=9, color=COLORS["structurel"], ha="center",
        arrowprops={"arrowstyle": "->", "color": COLORS["structurel"], "lw": 1.2},
    )

    ax_l.spines["top"].set_visible(False)
    ax_r.spines["top"].set_visible(False)

    # Pas de légende : les labels d'axes colorés (bleu = DICRIM, rouge = CatNat)
    # servent d'orientation au lecteur et libèrent l'espace haut-gauche pour
    # l'annotation du pic DICRIM 2013.
    _ = (line_d, line_c)  # référencées pour éviter le warning unused

    add_source(
        fig,
        "Sources : GASPAR (tables DICRIM + CatNat par département, déc. 2025). "
        "Tronqué à 2023 (années 2024-2025 en cours d'instruction). Tawiza",
    )
    save_chart(fig, "07_effet_ciseaux", output_dir=str(CHARTS))
    plt.close()
    print("✓ 07_effet_ciseaux")


# ════════════════════════════════════════════════════════════════════════════
# CHART 8 — Matrice TIM × DICRIM (visuelle, lecture rapide)
# ════════════════════════════════════════════════════════════════════════════

def chart_08_matrice():
    """Visualisation 2×2 de la matrice TIM × DICRIM communes RGA.

    Lit data/processed/tim_matrix.json (produit par 01_merge.py).
    Met en évidence la case scoop : "Avec TIM, Sans DICRIM" en rouge alerte.
    Layout : grandes cases avec un seul label court par cellule pour éviter
    le débordement de texte.
    """
    with open(BASE / "data" / "processed" / "tim_matrix.json") as f:
        m = json.load(f)

    a = m["tim_avec_dicrim"]
    b = m["tim_sans_dicrim"]
    c = m["sans_tim_avec_dicrim"]
    d = m["sans_tim_sans_dicrim"]

    fig, ax = plt.subplots(figsize=(12, 8.5))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    fig.subplots_adjust(top=0.85, bottom=0.18, left=0.18, right=0.84)

    def _fmt(n):
        return f"{n:,}".replace(",", " ")

    # (valeur, x, y, couleur, alpha, couleur_texte, label_court)
    cells = [
        (a, 0, 1, COLORS["positif"],    0.70, "white",        "ont publié"),
        (b, 1, 1, COLORS["alerte"],     0.92, "white",        "n'ont rien publié"),
        (c, 0, 0, COLORS["neutre"],     0.55, "white",        "publié sans TIM"),
        (d, 1, 0, COLORS["text_muted"], 0.45, COLORS["text"], "aucune trace"),
    ]

    for val, x, y, color, alpha, txt_color, label in cells:
        rect = plt.Rectangle(
            (x, y), 1, 1, facecolor=color, alpha=alpha,
            edgecolor="white", linewidth=3,
        )
        ax.add_patch(rect)

        # Grand chiffre, légèrement au-dessus du milieu
        ax.text(x + 0.5, y + 0.58, _fmt(val),
                ha="center", va="center",
                fontsize=32, fontweight="bold", color=txt_color)

        # Label court single-line
        ax.text(x + 0.5, y + 0.28, label,
                ha="center", va="center",
                fontsize=11, color=txt_color, alpha=0.95)

    # Annotation scoop : flèche vers la case rouge
    ax.annotate(
        "scoop : 52,4% des\ncommunes prévenues\nrestent silencieuses",
        xy=(2.0, 1.5), xytext=(2.45, 1.5),
        fontsize=10, color=COLORS["alerte"], fontweight="bold",
        ha="left", va="center",
        arrowprops={"arrowstyle": "->", "color": COLORS["alerte"], "lw": 1.8},
    )

    # Headers de colonnes (DICRIM)
    ax.text(0.5, 2.20, "Avec DICRIM", ha="center", fontsize=13,
            fontweight="bold", color=COLORS["text"])
    ax.text(1.5, 2.20, "Sans DICRIM", ha="center", fontsize=13,
            fontweight="bold", color=COLORS["text"])
    ax.text(0.5, 2.07, "4 323 (35%)", ha="center", fontsize=10,
            color=COLORS["text_secondary"], style="italic")
    ax.text(1.5, 2.07, "8 031 (65%)", ha="center", fontsize=10,
            color=COLORS["text_secondary"], style="italic")

    # Headers de lignes (TIM)
    ax.text(-0.08, 1.55, "Avec TIM", ha="right", va="center", fontsize=13,
            fontweight="bold", color=COLORS["text"])
    ax.text(-0.08, 1.42, "7 440 (60%)", ha="right", va="center", fontsize=10,
            color=COLORS["text_secondary"], style="italic")
    ax.text(-0.08, 0.55, "Sans TIM", ha="right", va="center", fontsize=13,
            fontweight="bold", color=COLORS["text"])
    ax.text(-0.08, 0.42, "4 914 (40%)", ha="right", va="center", fontsize=10,
            color=COLORS["text_secondary"], style="italic")

    ax.set_xlim(-1.0, 3.3)
    ax.set_ylim(-0.3, 2.5)
    ax.set_aspect("equal")
    ax.set_axis_off()

    ax.set_title(
        "Matrice TIM × DICRIM : 12 354 communes RGA",
        fontsize=15, fontweight="bold", color=COLORS["text"], pad=18,
    )

    fig.text(
        0.5, 0.10,
        "TIM = Transmission de l'Information aux Maires (acte préfectoral).  "
        "DICRIM = Document d'Information Communal sur les Risques Majeurs.",
        ha="center", fontsize=9, color=COLORS["text_muted"], style="italic",
    )

    add_source(
        fig,
        "Source : GASPAR (tables risq + dicrim + tim, déc. 2025). Tawiza",
    )
    save_chart(fig, "08_matrice_tim_dicrim", output_dir=str(CHARTS))
    plt.close()
    print("✓ 08_matrice_tim_dicrim")


# ════════════════════════════════════════════════════════════════════════════
# ŒIL TAWIZA — pixel art repris du CLI tawiza-splash, transposé en SVG
# ════════════════════════════════════════════════════════════════════════════

def chart_eye_cli():
    """Génère charts/tawiza_eye_cli.svg : pixel art animé du CLI Tawiza.

    Le tawiza-splash (CLI) anime un œil qui s'ouvre via 3 frames pixel art :
    CLOSED → HALF → OPEN. On les transpose ici dans un SVG unique avec des
    animations SMIL <set> qui rejouent l'ouverture à chaque chargement de
    page (0.35s sur CLOSED, 0.35s sur HALF, puis OPEN figée).

    Palette extraite du tawiza-splash : 13 nuances de la sclère sombre au
    reflet blanc, en passant par l'iris doré-orangé signature Tawiza.

    Accessibilité : @media (prefers-reduced-motion: reduce) côté CSS doit
    cacher les frames CLOSED/HALF et ne montrer que OPEN.
    """
    palette = {
        "S": "#3a2a1a",  # sclère sombre
        "s": "#4a3828",  # sclère mi-sombre
        "L": "#1e120a",  # contour noir profond
        "W": "#e8e2d8",  # cornée (cream)
        "w": "#d0c8bc",  # cornée mi-ombre
        "B": "#2a1808",  # transition iris (presque noir)
        "D": "#705010",  # iris brun
        "I": "#a07820",  # iris orange
        "i": "#c8a030",  # iris jaune-orange
        "G": "#D4A843",  # iris doré (signature Tawiza)
        "g": "#e8c860",  # iris doré clair
        "P": "#060402",  # pupille noir absolu
        "R": "#f0ece8",  # reflet blanc
    }

    # Halves de chaque frame : chaque ligne fait 30 chars, mirrorée en 60.
    # Source : /opt/tawiza-cli/bin/tawiza-splash
    closed_half = [
        "............SSSSSSSSSSSSSSSSSS",
        "........SSSS..................",
        ".....SSSsLLLLLLLLLLLLLLLLLLLLL",
        "......SSsLLLLLLLLLLLLLLLLLLLLL",
        ".....SSSsLLLLLLLLLLLLLLLLLLLLL",
        "........SSSS..................",
        "............SSSSSSSSSSSSSSSSSS",
    ]
    half_half = [
        "............SSSSSSSSSSSSSSSSSS",
        ".......SSSSSssLLLLLLLLLLLLLLL.",
        ".....SSsLLwWWWWWWWWWWWWWWWWWW.",
        "..SSsLLwWWWWWWWWWBDIiGGGGGGGGG",
        "..SSsLLwWWWWWWWWWBDIiggRPPPPPP",
        "..SSsLLwWWWWWWWWWWBDIiGGGGGGGG",
        ".....SSsLLwWWWWWWWWWWWWWWWWWW.",
        ".......SSSSSssLLLLLLLLLLLLLLL.",
        "............SSSSSSSSSSSSSSSSSS",
    ]
    open_half = [
        "............SSSSSSSSSSSSSSSSSS",
        ".......SSSSSssLLLLLLLLLLLLLLL.",
        "....SSSSssLLLLLLLLLLLLLLLLLLLL",
        "...SSSsLLLwwwwwwwwwwwwwwwwwwww",
        "..SSSsLLwWWWWWWWWWWWWWWWWWWWWW",
        ".SSsLLwWWWWWWWWWWWBBBBBBBBBBBB",
        ".SSsLLwWWWWWWWWBDDIIIIIIIIIIII",
        "SSsLLwWWWWWWWBDIiiGGGGGGGGGGGG",
        "SSsLLwWWWWWWWBDIiiiggRPPPPPPPP",
        "SSsLLwWWWWWWWBDIiiigggPPPPPPPP",
        "SSsLLwWWWWWWWBDIiiGGGGGGGGGGGG",
        ".SSsLLwWWWWWWWWBDDIIIIIIIIIIII",
        ".SSsLLwWWWWWWWWWWWBBBBBBBBBBBB",
        "..SSSsLLwWWWWWWWWWWWWWWWWWWWWW",
        "...SSSsLLLwwwwwwwwwwwwwwwwwwww",
        "....SSSSssLLLLLLLLLLLLLLLLLLLL",
        ".......SSSSSssLLLLLLLLLLLLLLL.",
        "............SSSSSSSSSSSSSSSSSS",
    ]

    px = 8           # taille d'un pixel dans le viewBox
    max_rows = len(open_half)
    cols = len(open_half[0]) * 2  # mirroré
    width = cols * px
    height = max_rows * px

    def _frame_rects(half_lines: list[str]) -> str:
        """Génère les <rect> d'une frame, centrée verticalement dans la viewBox."""
        offset_y = (max_rows - len(half_lines)) // 2
        rects = []
        for ry, line in enumerate(half_lines):
            full = line + line[::-1]
            y = (ry + offset_y) * px
            for cx, ch in enumerate(full):
                color = palette.get(ch)
                if color is None:
                    continue
                rects.append(
                    f'    <rect x="{cx * px}" y="{y}" '
                    f'width="{px}" height="{px}" fill="{color}"/>'
                )
        return "\n".join(rects)

    closed_rects = _frame_rects(closed_half)
    half_rects = _frame_rects(half_half)
    open_rects = _frame_rects(open_half)

    # Animation en boucle infinie sur 3 secondes :
    #   0.0 - 0.4 : CLOSED
    #   0.4 - 0.7 : HALF (ouverture)
    #   0.7 - 2.5 : OPEN (longue pause, l'œil regarde)
    #   2.5 - 2.7 : HALF (fermeture)
    #   2.7 - 3.0 : CLOSED (puis on reboucle)
    # Implémentation : <animate> avec values + keyTimes en mode discrete,
    # repeatCount="indefinite". calcMode discrete = swap instantané (pas de fade).
    cycle_dur = "3s"
    key_times = "0;0.1333;0.2333;0.8333;0.9;1"
    closed_vals = "1;0;0;0;1;1"
    half_vals   = "0;1;0;1;0;0"
    open_vals   = "0;0;1;0;0;0"
    anim_attrs = (
        f'attributeName="opacity" calcMode="discrete" '
        f'dur="{cycle_dur}" repeatCount="indefinite" '
        f'keyTimes="{key_times}"'
    )

    svg = f"""<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {width} {height}"
     shape-rendering="crispEdges" role="img"
     aria-label="L'œil Tawiza qui s'ouvre et se ferme en boucle">
  <title>L'œil qui dort jamais - Tawiza</title>
  <desc>Pixel art repris du CLI Tawiza, animation 3 frames en boucle.</desc>

  <g class="frame-closed" opacity="1">
{closed_rects}
    <animate {anim_attrs} values="{closed_vals}"/>
  </g>

  <g class="frame-half" opacity="0">
{half_rects}
    <animate {anim_attrs} values="{half_vals}"/>
  </g>

  <g class="frame-open" opacity="0">
{open_rects}
    <animate {anim_attrs} values="{open_vals}"/>
  </g>
</svg>
"""

    out = CHARTS / "tawiza_eye_cli.svg"
    out.write_text(svg, encoding="utf-8")
    print(f"✓ tawiza_eye_cli ({cols}×{max_rows} pixels, 3 frames animées)")


if __name__ == "__main__":
    print("Génération des graphiques article RGA...\n")
    chart_01_carte_silence()
    chart_02_top_sans_dicrim()
    chart_03_patrimoine_expose()
    chart_04_surprime()
    chart_05_explosion()
    chart_06_spirale()
    chart_07_effet_ciseaux()
    chart_08_matrice()
    chart_eye_cli()
    print(f"\n✓ 8 graphiques + œil Tawiza générés dans {CHARTS}")
