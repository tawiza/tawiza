"""
tawiza_style.py — Style matplotlib pour les graphiques tawiza.fr

Palette et typographie alignées sur le design system de tawiza.fr.
Usage :
    from src.analysis.tawiza_style import apply_style, save_chart, COLORS
    apply_style()
    fig, ax = plt.subplots()
    ...
    save_chart(fig, "nom_du_graphique", output_dir="articles/001-dunkerque/charts")
"""

import locale
from pathlib import Path

import matplotlib as mpl
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

# Formateur de nombres français (espace comme séparateur de milliers)
try:
    locale.setlocale(locale.LC_ALL, "fr_FR.UTF-8")
except locale.Error:
    pass  # fallback si locale non dispo


def fmt_fr(x, pos=None):
    """Formatte un nombre au format français (espace milliers)."""
    if x == int(x):
        return f"{int(x):,}".replace(",", "\u202f")
    return f"{x:,.1f}".replace(",", "\u202f").replace(".", ",")

# ── Palette tawiza.fr ──────────────────────────────────────────────────────

COLORS = {
    # Base (from tawiza.fr CSS vars)
    "bg": "#fafaf9",
    "text": "#1c1917",
    "text_secondary": "#78716c",
    "text_muted": "#a8a29e",
    "accent": "#b45309",
    "separator": "#e7e5e4",
    "surface": "#ffffff",

    # Sémantiques article
    "positif": "#2D6A4F",       # vert forêt — territoire, positif
    "alerte": "#C1554D",        # rouille chaud — alerte, négatif
    "attention": "#D4A843",     # ambre — attention, intermédiaire
    "neutre": "#5B7BA5",        # bleu acier — données, neutre
    "social": "#8B5E83",        # mauve — signaux sociaux
    "contexte": "#C8C4BD",      # gris chaud — référence, contexte
    "structurel": "#7C6F64",    # brun — structurel

    # Scénarios simulation
    "scenario_court": "#2D6A4F",
    "scenario_prolonge": "#D4A843",
    "scenario_severe": "#C1554D",

    # Carte
    "icpe": "#C1554D",
    "gigafactory": "#2D6A4F",
    "friche": "#C8C4BD",
}

# ── Typographie ────────────────────────────────────────────────────────────

FONT_HEADING = "El Messiri"
FONT_BODY = "Inter"
FONT_FALLBACK_HEADING = "Georgia"
FONT_FALLBACK_BODY = "sans-serif"


def _font_available(name: str) -> bool:
    """Vérifie si une police est disponible dans matplotlib."""
    return any(f.name == name for f in fm.fontManager.ttflist)


def apply_style():
    """Applique le style tawiza.fr aux graphiques matplotlib."""

    heading = FONT_HEADING if _font_available(FONT_HEADING) else FONT_FALLBACK_HEADING
    body = FONT_BODY if _font_available(FONT_BODY) else FONT_FALLBACK_BODY

    mpl.rcParams.update({
        # Figure
        "figure.facecolor": COLORS["bg"],
        "figure.edgecolor": "none",
        "figure.dpi": 100,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.3,
        "savefig.facecolor": COLORS["bg"],
        "savefig.edgecolor": "none",

        # Axes
        "axes.facecolor": COLORS["bg"],
        "axes.edgecolor": COLORS["separator"],
        "axes.labelcolor": COLORS["text_secondary"],
        "axes.titlecolor": COLORS["text"],
        "axes.linewidth": 0.6,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize": 16,
        "axes.titleweight": "bold",
        "axes.titlepad": 16,
        "axes.labelsize": 11,
        "axes.labelpad": 8,

        # Grid
        "grid.color": COLORS["separator"],
        "grid.linewidth": 0.4,
        "grid.alpha": 0.7,

        # Ticks
        "xtick.color": COLORS["text_secondary"],
        "ytick.color": COLORS["text_secondary"],
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "xtick.major.size": 0,
        "ytick.major.size": 0,

        # Fonts
        "font.family": body,
        "font.size": 11,

        # Legend
        "legend.frameon": False,
        "legend.fontsize": 10,
        "legend.labelcolor": COLORS["text_secondary"],

        # Lines
        "lines.linewidth": 2.0,
        "lines.markersize": 6,

        # Patches (bars, etc.)
        "patch.edgecolor": "none",
    })


def save_chart(fig, name: str, output_dir: str = "charts", source: str = None):
    """
    Sauvegarde un graphique en PNG (200 dpi) et SVG.

    Args:
        fig: matplotlib Figure
        name: nom du fichier (sans extension)
        output_dir: dossier de sortie
        source: texte source à afficher en bas à droite
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if source:
        fig.text(
            0.98, 0.02, f"Source : {source}",
            fontsize=8, color=COLORS["text_muted"],
            ha="right", va="bottom",
            fontstyle="italic",
        )

    fig.savefig(out / f"{name}.png", dpi=200, bbox_inches="tight", facecolor=COLORS["bg"])
    fig.savefig(out / f"{name}.svg", bbox_inches="tight", facecolor=COLORS["bg"])
    print(f"  → {out / name}.png + .svg")


def set_title(ax, title: str, subtitle: str = None):
    """Titre en El Messiri (heading font) avec sous-titre optionnel."""
    heading = FONT_HEADING if _font_available(FONT_HEADING) else FONT_FALLBACK_HEADING
    ax.set_title(title, fontfamily=heading, fontsize=16, fontweight="bold",
                 color=COLORS["text"], pad=16 if not subtitle else 24)
    if subtitle:
        ax.text(0.0, 1.02, subtitle, transform=ax.transAxes,
                fontsize=11, color=COLORS["text_secondary"], style="italic")


def annotate_key_message(ax, x, y, text, color=None):
    """Ajoute un message clé annoté sur le graphique (flèche + texte)."""
    color = color or COLORS["accent"]
    ax.annotate(
        text, xy=(x, y),
        xytext=(20, 25), textcoords="offset points",
        fontsize=10, fontweight="bold", color=color,
        arrowprops={"arrowstyle": "->", "color": color, "lw": 1.5},
        bbox={"boxstyle": "round,pad=0.4", "facecolor": COLORS["surface"],
              "edgecolor": color, "alpha": 0.9},
    )


# Appliquer le style à l'import si utilisé comme module
apply_style()
