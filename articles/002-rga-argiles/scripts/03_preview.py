#!/usr/bin/env python3
"""
03_preview.py — Génère preview.html depuis article.md (source de vérité)

Convertit le Markdown Tawiza en HTML stylé. Gère :
 - placeholders graphiques `[GRAPHIQUE N — ...]` → <figure class="chart">
 - "En bref"               → <div class="en-bref">
 - "Ce qu'on ne sait pas"  → <div class="limites">
 - "Méthodologie"          → <div class="methodo">
 - "Sources"               → <div class="sources">
 - "Deux liens utiles"     → <div class="action-box">
 - ASCII art + signature   → <div class="tawiza-footer">

Le preview est un artefact BUILDÉ, pas un fichier maintenu à la main.
Toute modification éditoriale passe par article.md ; ce script régénère.
"""
from __future__ import annotations

import re
import sys
import time
from datetime import datetime
from pathlib import Path

import markdown

BASE = Path(__file__).resolve().parent.parent
ARTICLE_MD = BASE / "article.md"
OUTPUT_HTML = BASE / "preview.html"
CHARTS_DIR = BASE / "charts"

# ────────────────────────────────────────────────────────────────────────────
# Template CSS — aligné avec l'identité Tawiza (palette terre/cream, serif
# El Messiri pour les titres, Inter pour le corps, JetBrains Mono pour l'ASCII).
# ────────────────────────────────────────────────────────────────────────────

CSS = """
:root {
    --bg: #fafaf9; --text: #1c1917; --text-secondary: #78716c;
    --text-muted: #a8a29e; --accent: #b45309; --separator: #e7e5e4;
    --surface: #ffffff; --positif: #2D6A4F; --alerte: #C1554D;
    --attention: #D4A843; --neutre: #5B7BA5; --social: #8B5E83;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
    font-family: 'Inter', sans-serif; background: var(--bg);
    color: var(--text); line-height: 1.75; font-size: 17px;
}
.progress { position: fixed; top: 0; left: 0; height: 3px;
            background: var(--accent); z-index: 100; transition: width 0.1s; }
nav { padding: 1rem 2rem; border-bottom: 1px solid var(--separator);
      background: var(--surface); position: sticky; top: 0; z-index: 50; }
nav a { color: var(--accent); text-decoration: none;
        font-weight: 600; font-size: 1.1rem; }
article { max-width: 720px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }
h1 { font-family: 'El Messiri', serif; font-size: 2.2rem; line-height: 1.2;
     color: var(--text); margin: 2rem 0 0.5rem; font-weight: 700; }
.dateline { color: var(--text-muted); font-size: 0.9rem; margin-bottom: 2rem; }
h2 { font-family: 'El Messiri', serif; font-size: 1.5rem; color: var(--text);
     margin: 3rem 0 1rem; padding-top: 1.5rem;
     border-top: 1px solid var(--separator); font-weight: 600; }
h2:first-of-type { border-top: none; }
h3 { font-size: 1.1rem; margin: 1.5rem 0 0.5rem; color: var(--text); font-weight: 600; }
p { margin-bottom: 1.2rem; }
strong { color: var(--text); font-weight: 600; }
em { font-style: italic; }
a { color: var(--accent); }
.en-bref { background: var(--surface); border-left: 4px solid var(--accent);
           padding: 1.2rem 1.5rem; margin: 1.5rem 0 2.5rem;
           border-radius: 0 8px 8px 0;
           box-shadow: 0 1px 3px rgba(0,0,0,0.05);
           font-size: 0.95rem; line-height: 1.7; }
.chart { margin: 2rem -1.5rem; text-align: center; }
.chart img { width: 100%; max-width: 800px; border-radius: 4px; }
.chart figcaption { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem; }
ul, ol { margin: 0.8rem 0 1.2rem 1.5rem; }
li { margin-bottom: 0.5rem; }
.limites { background: #f5f0eb; padding: 1.5rem 2rem;
           border-radius: 8px; margin: 1.5rem 0; }
.limites p { font-size: 0.95rem; }
.limites strong { color: var(--alerte); }
.action-box { background: var(--surface); border: 2px solid var(--accent);
              border-radius: 8px; padding: 1.5rem 2rem; margin: 2rem 0; }
.action-box a { color: var(--accent); font-weight: 600; }
.action-box p:last-child { margin-bottom: 0; }
.methodo { font-size: 0.9rem; color: var(--text-secondary); }
.methodo h3 { color: var(--text); margin-top: 1.5rem; }
.methodo table { width: 100%; border-collapse: collapse; margin: 1rem 0;
                 font-size: 0.85rem; }
.methodo th, .methodo td { padding: 0.5rem;
                           border-bottom: 1px solid var(--separator);
                           text-align: left; }
.methodo th { font-weight: 600; }
.methodo pre { background: #292524; color: #e7e5e4; padding: 1rem;
               border-radius: 6px; overflow-x: auto;
               font-family: 'JetBrains Mono', monospace;
               font-size: 0.8rem; margin: 1rem 0; }
.sources { font-size: 0.85rem; color: var(--text-secondary); }
.sources a { color: var(--neutre); }
.sources ul { list-style: none; margin-left: 0; }
.sources li { margin-bottom: 0.4rem; padding-left: 1rem;
              border-left: 2px solid var(--separator); }
article table { border-collapse: collapse; width: 100%; margin: 1.5rem 0;
                font-size: 0.9rem; background: var(--surface);
                border-radius: 6px; overflow: hidden;
                box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
article table th, article table td { padding: 0.6rem 0.8rem;
                                     border-bottom: 1px solid var(--separator);
                                     text-align: left; vertical-align: top; }
article table th { font-weight: 600; background: rgba(180, 83, 9, 0.06);
                   color: var(--text); }
article table tr:last-child td { border-bottom: none; }
.methodo table { box-shadow: none; background: transparent; }
.methodo table th { background: transparent; }
blockquote { border-left: 4px solid var(--attention);
             padding: 0.5rem 1.5rem; margin: 1.5rem 0;
             color: var(--text-secondary); font-style: italic; }
article > hr { border: none; border-top: 1px solid var(--separator);
               margin: 2rem 0; }
.tawiza-footer { margin: 4rem 0 2rem; text-align: center;
                 padding-top: 3rem;
                 border-top: 1px solid var(--separator); }
.tawiza-footer img { width: 280px; max-width: 70%; height: auto;
                     image-rendering: pixelated;
                     image-rendering: crisp-edges;
                     display: inline-block; margin: 0 auto 1rem; }
.tawiza-footer p { max-width: 520px; margin: 1rem auto;
                   font-size: 0.9rem; color: var(--text-muted);
                   line-height: 1.6; }
.tawiza-footer p:first-of-type { font-family: 'El Messiri', serif;
                                 font-size: 1.1rem; color: var(--accent);
                                 letter-spacing: 0.05em; margin-top: 0.5rem; }
.tawiza-footer p:last-child { font-size: 0.85rem; font-style: italic; }
@media (prefers-reduced-motion: reduce) {
    .tawiza-footer img { animation: none !important; }
}
footer { text-align: center; padding: 2rem; color: var(--text-muted);
         font-size: 0.85rem; border-top: 1px solid var(--separator); }
@media (max-width: 600px) {
    h1 { font-size: 1.6rem; }
    h2 { font-size: 1.25rem; }
    article { padding: 1rem 1rem 3rem; }
    .chart { margin: 1.5rem -1rem; }
    article table { font-size: 0.8rem; }
    article table th, article table td { padding: 0.4rem 0.5rem; }
}
"""

# ────────────────────────────────────────────────────────────────────────────
# Template HTML — placeholders @@XXX@@ pour éviter les collisions avec le CSS
# ────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@@TITLE@@</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=El+Messiri:wght@500;600;700&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
    <style>@@CSS@@
    </style>
</head>
<body>
    <div class="progress" id="progress"></div>
    <nav><a href="https://tawiza.fr">Tawiza</a> &nbsp;·&nbsp; Analyses</nav>
    <article>
        <h1>@@H1@@</h1>
        <p class="dateline">@@DATELINE@@</p>
@@BODY@@
    </article>
    <footer>
        Tawiza · Intelligence territoriale · Les donn&eacute;es publiques sont un bien commun<br>
        <a href="https://tawiza.fr" style="color:var(--accent)">tawiza.fr</a>
    </footer>
    <script>
        window.addEventListener('scroll', () => {
            const h = document.documentElement.scrollHeight - window.innerHeight;
            document.getElementById('progress').style.width = (window.scrollY / h * 100) + '%';
        });
    </script>
</body>
</html>
"""


# ────────────────────────────────────────────────────────────────────────────
# Rendu
# ────────────────────────────────────────────────────────────────────────────


def _render_chart(num: int, caption: str) -> str:
    """Remplace un placeholder `[GRAPHIQUE N — ...]` par <figure class="chart">."""
    candidates = sorted(CHARTS_DIR.glob(f"{num:02d}_*.png"))
    if not candidates:
        return (
            f'<p class="chart-missing"><em>[Graphique {num} manquant : '
            f"{caption}]</em></p>"
        )
    alt = caption.replace('"', "&quot;")
    return (
        f'<figure class="chart"><img src="charts/{candidates[0].name}" '
        f'alt="{alt}"></figure>'
    )


def _md_to_html(md_text: str) -> str:
    md = markdown.Markdown(
        extensions=["tables", "fenced_code"],
        output_format="html",
    )
    return md.convert(md_text)


def _strip_enclosing_p(html: str) -> str:
    stripped = html.strip()
    if (
        stripped.startswith("<p>")
        and stripped.endswith("</p>")
        and stripped.count("<p>") == 1
    ):
        return stripped[3:-4]
    return stripped


def _render_section(title: str, body_md: str) -> str:
    """Rend une section H2 avec wrapper stylé selon son titre."""
    body_html = _md_to_html(body_md)
    tl = title.lower()

    if "en bref" in tl:
        inner = _strip_enclosing_p(body_html)
        return f'<div class="en-bref"><strong>En bref.</strong> {inner}</div>'

    if "ce qu'on ne sait pas" in tl:
        return f'<h2>{title}</h2>\n<div class="limites">\n{body_html}\n</div>'

    if "méthodologie" in tl:
        return f'<h2>{title}</h2>\n<div class="methodo">\n{body_html}\n</div>'

    if tl == "sources":
        return f'<h2>{title}</h2>\n<div class="sources">\n{body_html}\n</div>'

    if "deux liens utiles" in tl or tl == "que faire":
        return f'<h2>{title}</h2>\n<div class="action-box">\n{body_html}\n</div>'

    return f"<h2>{title}</h2>\n{body_html}"


def _parse_sections(rest_md: str) -> list[tuple[str, str]]:
    """Découpe le markdown en sections H2, en ignorant les --- de séparation."""
    lines = rest_md.split("\n")
    sections: list[tuple[str, str]] = []
    current_title: str | None = None
    current_body: list[str] = []
    in_code = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            if current_title is not None:
                current_body.append(line)
            continue
        if not in_code and line.startswith("## "):
            if current_title is not None:
                sections.append((current_title, "\n".join(current_body).strip()))
            current_title = line[3:].strip()
            current_body = []
            continue
        if current_title is None:
            continue  # contenu pré-première-H2 (ignoré)
        current_body.append(line)

    if current_title is not None:
        sections.append((current_title, "\n".join(current_body).strip()))

    return sections


_FOOTER_MARKER = re.compile(r"\n---\s*\n\s*<!--\s*tawiza-footer\s*-->", re.IGNORECASE)


def _extract_footer(body_md: str) -> tuple[str, str | None]:
    """Détecte le marqueur explicite `<!-- tawiza-footer -->` et split."""
    match = _FOOTER_MARKER.search(body_md)
    if not match:
        return body_md, None
    idx = match.start()
    return body_md[:idx].rstrip(), body_md[match.end():].lstrip()


def _render_footer(footer_md: str) -> str:
    body_html = _md_to_html(footer_md)
    return f'<div class="tawiza-footer">\n{body_html}\n</div>'


def build_preview() -> None:
    md_text = ARTICLE_MD.read_text(encoding="utf-8")
    lines = md_text.split("\n")

    # 1. Titre H1
    h1 = ""
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("# "):
            h1 = line[2:].strip()
            i += 1
            break
        i += 1

    # 2. Dateline (*...*)
    dateline = ""
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("*") and line.endswith("*") and len(line) > 2:
            dateline = line.strip("*").strip()
            i += 1
            break
        if line.startswith("## "):
            break  # plus de dateline, on est déjà dans une section
        i += 1

    rest = "\n".join(lines[i:])

    # 3. Remplacer les placeholders graphiques AVANT la conversion markdown
    rest = re.sub(
        r"`\[GRAPHIQUE\s+(\d+)\s*[-—]\s*([^\]]+)\]`",
        lambda m: _render_chart(int(m.group(1)), m.group(2).strip()),
        rest,
    )

    # 4. Parser en sections H2
    sections = _parse_sections(rest)

    # 5. Extraire le pied d'article de la dernière section (Sources)
    footer_md: str | None = None
    if sections:
        last_title, last_body = sections[-1]
        cleaned_body, extracted_footer = _extract_footer(last_body)
        if extracted_footer:
            sections[-1] = (last_title, cleaned_body)
            footer_md = extracted_footer

    # 6. Rendu
    parts: list[str] = [_render_section(t, b) for t, b in sections]
    if footer_md:
        parts.append(_render_footer(footer_md))

    body_html = "\n\n".join(parts)

    # 7. Injection dans le template (via remplacement manuel, pas .format,
    # pour ne pas avoir à échapper les accolades CSS/JS)
    html = (
        HTML_TEMPLATE.replace("@@TITLE@@", f"{h1} | Tawiza")
        .replace("@@CSS@@", CSS)
        .replace("@@H1@@", h1)
        .replace("@@DATELINE@@", dateline)
        .replace("@@BODY@@", body_html)
    )

    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"✅ {OUTPUT_HTML}")
    print(f"   {len(sections)} sections rendues")
    if footer_md:
        print("   pied d'article (œil Tawiza) détecté et isolé")
    print(f"   {len(html):,} caractères HTML")


def _watched_mtime() -> float:
    """Mtime maximum sur les fichiers surveillés (article + charts)."""
    mtimes = [ARTICLE_MD.stat().st_mtime]
    for chart in CHARTS_DIR.glob("*.png"):
        mtimes.append(chart.stat().st_mtime)
    return max(mtimes)


def watch_mode() -> None:
    """Polling watcher : rebuild dès qu'article.md ou un chart change."""
    print(f"👁  watch : {ARTICLE_MD.relative_to(BASE)} + charts/")
    print(f"   sortie  : {OUTPUT_HTML.relative_to(BASE)}")
    print("   astuce  : pour prévisualiser, lance dans un autre shell :")
    print("             python3 -m http.server 8765")
    print("   arrêt   : Ctrl+C\n")
    last = 0.0
    try:
        while True:
            current = _watched_mtime()
            if current != last:
                if last > 0:
                    print(f"[{datetime.now():%H:%M:%S}] changement détecté → rebuild")
                build_preview()
                last = current
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n👋 watcher arrêté")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--watch", "-w"):
        watch_mode()
    else:
        build_preview()
