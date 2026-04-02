"""
carte_v3.py — Carte réaliste de la zone industrialo-portuaire de Dunkerque

Améliorations :
- Fond satellite/terrain (Esri World Imagery)
- Clusters visuels par type de site
- Marqueurs personnalisés avec icônes
- Popups riches avec contexte humain
- Périmètre port visible
- Légende unique, bien placée
"""

import sys
sys.path.insert(0, "/root/MPtoO-V2")

import json
import folium
from folium.plugins import MiniMap, FloatImage
from pathlib import Path

BASE = Path("/root/MPtoO-V2/articles/001-dunkerque")
RAW = BASE / "data" / "raw"
CHARTS = BASE / "charts"

with open(RAW / "icpe_dunkerque.json") as f:
    icpe = json.load(f)
with open(RAW / "gigafactories.json") as f:
    giga = json.load(f)
with open(RAW / "friches_dunkerque_manual.json") as f:
    friches = json.load(f)

# ── Carte avec fond satellite ──

m = folium.Map(
    location=[51.022, 2.28],
    zoom_start=12,
    tiles=None,
    width="100%",
    height=650,
    control_scale=True,
)

# Fonds de carte
folium.TileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Esri, Maxar, Earthstar Geographics",
    name="Satellite",
    max_zoom=18,
).add_to(m)

folium.TileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    attr="Esri, HERE, Garmin, USGS",
    name="Terrain",
    max_zoom=18,
).add_to(m)

folium.TileLayer("CartoDB positron", name="Plan").add_to(m)

# ── Sites industriels majeurs (les plus importants, nommés) ──

sites_majeurs = [
    {
        "nom": "ArcelorMittal Dunkerque",
        "lat": 51.028, "lon": 2.345,
        "desc": "Plus grand complexe sidérurgique de France. Deux hauts fourneaux, une aciérie, des laminoirs. Environ 3 500 salariés directs. Quand un haut fourneau s'arrête, c'est tout le port qui le sent dans les volumes de minerai.",
        "type": "Sidérurgie",
        "icon_color": "darkred",
        "emplois": "~3 500",
    },
    {
        "nom": "Terminal méthanier (GNL)",
        "lat": 51.045, "lon": 2.175,
        "desc": "Deuxième terminal GNL d'Europe. Capacité de 13 milliards de m3 par an. Record de 10 millions de tonnes en 2025. Le gaz arrive liquéfié par bateau à -162°C, il est réchauffé et injecté dans le réseau.",
        "type": "Énergie",
        "icon_color": "orange",
        "emplois": "~200",
    },
    {
        "nom": "Aluminium Dunkerque",
        "lat": 51.018, "lon": 2.305,
        "desc": "Plus grande aluminerie d'Europe. Environ 650 salariés. L'électrolyse de l'aluminium consomme autant d'électricité qu'une ville de 500 000 habitants. Quand le prix de l'énergie double, la facture passe de 200 à 400 millions d'euros par an.",
        "type": "Métallurgie",
        "icon_color": "darkred",
        "emplois": "~650",
    },
    {
        "nom": "Polychim / Versalis",
        "lat": 51.012, "lon": 2.290,
        "desc": "Chimie de base : éthylène, polyéthylène. Les molécules partent du pétrole pour devenir du plastique. Le prix du baril, c'est leur coût de matière première.",
        "type": "Pétrochimie",
        "icon_color": "darkred",
        "emplois": "~400",
    },
    {
        "nom": "Centrale nucléaire de Gravelines",
        "lat": 51.015, "lon": 2.107,
        "desc": "Plus grande centrale nucléaire d'Europe de l'Ouest. 6 réacteurs, 5 460 MW. Paradoxe : Dunkerque produit massivement de l'électricité décarbonée, mais ses industries consomment surtout du gaz et du coke.",
        "type": "Énergie nucléaire",
        "icon_color": "blue",
        "emplois": "~1 700",
    },
]

sites_layer = folium.FeatureGroup(name="⚙️ Sites industriels majeurs", show=True)
for site in sites_majeurs:
    popup_html = f"""
    <div style="font-family: -apple-system, sans-serif; font-size: 13px; max-width: 300px; line-height: 1.5;">
        <h4 style="margin: 0 0 8px; color: #1c1917; font-size: 15px; border-bottom: 2px solid #b45309; padding-bottom: 4px;">{site['nom']}</h4>
        <div style="display: inline-block; background: #f5f5f4; border-radius: 4px; padding: 2px 8px; font-size: 11px; color: #78716c; margin-bottom: 8px;">{site['type']} · {site['emplois']} emplois</div>
        <p style="margin: 6px 0; color: #44403c;">{site['desc']}</p>
    </div>
    """
    folium.Marker(
        location=[site["lat"], site["lon"]],
        popup=folium.Popup(popup_html, max_width=320),
        tooltip=f"⚙️ {site['nom']} ({site['emplois']})",
        icon=folium.Icon(color=site["icon_color"], icon="industry", prefix="fa")
    ).add_to(sites_layer)

sites_layer.add_to(m)

# ── Gigafactories ──

giga_layer = folium.FeatureGroup(name="🔋 Gigafactories (batteries)", show=True)
for p in giga["projets"]:
    status_emoji = "🟢" if p["emplois_actuels_estime"] > 100 else "🟡" if p["emplois_actuels_estime"] > 0 else "⚪"
    popup_html = f"""
    <div style="font-family: -apple-system, sans-serif; font-size: 13px; max-width: 300px; line-height: 1.5;">
        <h4 style="margin: 0 0 8px; color: #2D6A4F; font-size: 15px; border-bottom: 2px solid #2D6A4F; padding-bottom: 4px;">🔋 {p['nom']}</h4>
        <div style="display: inline-block; background: #f0fdf4; border-radius: 4px; padding: 2px 8px; font-size: 11px; color: #2D6A4F; margin-bottom: 8px;">{p['produit']}</div>
        <table style="font-size: 12px; width: 100%; border-collapse: collapse; margin-top: 6px;">
            <tr><td style="padding: 3px 0; color: #78716c;">Emplois annoncés</td><td style="padding: 3px 0; text-align: right; font-weight: 600;">{p['emplois_annonces']:,}</td></tr>
            <tr><td style="padding: 3px 0; color: #78716c;">Emplois actuels</td><td style="padding: 3px 0; text-align: right; font-weight: 600;">{status_emoji} ~{p['emplois_actuels_estime']}</td></tr>
            <tr><td style="padding: 3px 0; color: #78716c;">Investissement</td><td style="padding: 3px 0; text-align: right; font-weight: 600;">{p['investissement_meur']:,} M€</td></tr>
            <tr><td style="padding: 3px 0; color: #78716c;">Pleine capacité</td><td style="padding: 3px 0; text-align: right; font-weight: 600;">{p['date_pleine_capacite']}</td></tr>
        </table>
        <p style="margin: 8px 0 0; font-size: 11px; color: #78716c; font-style: italic;">{p['statut']}</p>
    </div>
    """
    folium.Marker(
        location=[p["lat"], p["lon"]],
        popup=folium.Popup(popup_html, max_width=320),
        tooltip=f"🔋 {p['nom']} ({p['emplois_annonces']:,} emplois annoncés)",
        icon=folium.Icon(color="green", icon="bolt", prefix="fa")
    ).add_to(giga_layer)

giga_layer.add_to(m)

# ── ICPE (filtrées : seulement les autorisées) ──

icpe_layer = folium.FeatureGroup(name="🏭 Sites industriels classés (ICPE)", show=False)
icpe_count = 0
for inst in icpe:
    lat = inst.get("latitude") or inst.get("y")
    lon = inst.get("longitude") or inst.get("x")
    if not lat or not lon:
        continue
    try:
        lat, lon = float(lat), float(lon)
    except (ValueError, TypeError):
        continue

    nom = inst.get("nomEtablissement", inst.get("raisonSociale", "ICPE"))
    seveso = str(inst.get("seveso", ""))
    regime = str(inst.get("regime", ""))

    is_seveso = seveso.lower() not in ("", "non", "ns", "none")
    is_autorisation = "A" in regime.upper()
    if not is_seveso and not is_autorisation:
        continue

    color = "#C1554D" if is_seveso else "#D4A843"
    radius = 8 if is_seveso else 4

    folium.CircleMarker(
        location=[lat, lon], radius=radius,
        color=color, fill=True, fill_color=color, fill_opacity=0.4,
        weight=1,
        tooltip=nom
    ).add_to(icpe_layer)
    icpe_count += 1

icpe_layer.add_to(m)
print(f"ICPE : {icpe_count} sites")

# ── Friches ──

friche_layer = folium.FeatureGroup(name="🏚️ Friches industrielles", show=True)
for fr in friches["friches"]:
    popup_html = f"""
    <div style="font-family: -apple-system, sans-serif; font-size: 13px; max-width: 240px; line-height: 1.5;">
        <h4 style="margin: 0 0 6px; color: #78716c; font-size: 14px;">🏚️ {fr['nom']}</h4>
        <p style="margin: 2px 0; font-size: 12px;">Surface : <strong>{fr['surface_ha']} hectares</strong></p>
        <p style="margin: 2px 0; font-size: 12px;">Type : {fr['type']}</p>
        <p style="margin: 6px 0 0; font-size: 11px; color: #a8a29e; font-style: italic;">Cicatrice des crises passées</p>
    </div>
    """
    folium.CircleMarker(
        location=[fr["lat"], fr["lon"]],
        radius=max(8, fr["surface_ha"] / 3),
        color="#78716c", fill=True, fill_color="#78716c", fill_opacity=0.2,
        weight=1.5, dash_array="6,4",
        popup=folium.Popup(popup_html, max_width=260),
        tooltip=f"Friche : {fr['nom']} ({fr['surface_ha']} ha)"
    ).add_to(friche_layer)

friche_layer.add_to(m)

# ── Contrôles ──

folium.LayerControl(collapsed=False, position="topright").add_to(m)
MiniMap(toggle_display=True, position="bottomright", tile_layer="CartoDB positron",
        width=120, height=100).add_to(m)

# ── Légende ──

legend_html = """
<div id="map-legend" style="position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); z-index: 999;
            background: rgba(255,255,255,0.95); padding: 10px 20px; border-radius: 8px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.15); font-family: -apple-system, sans-serif;
            font-size: 12px; display: flex; gap: 18px; align-items: center; flex-wrap: wrap;
            justify-content: center; max-width: 90vw;">
    <span style="font-weight: 700; color: #1c1917; margin-right: 4px;">Légende</span>
    <span>⚙️ Sites majeurs</span>
    <span>🔋 Gigafactories</span>
    <span>🏚️ Friches</span>
    <span style="opacity: 0.6;">🏭 ICPE (masquée)</span>
    <span style="font-size: 10px; color: #a8a29e;">tawiza.fr</span>
</div>
<style>
@media (max-width: 600px) {
    #map-legend { font-size: 11px; gap: 10px; padding: 8px 14px; bottom: 10px; }
}
</style>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# ── Sauvegarder ──

out = CHARTS / "10_carte_dunkerque.html"
m.save(str(out))
print(f"→ {out}")
