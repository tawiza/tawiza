"""
00_download.py — Télécharge les données brutes nécessaires à l'analyse
Article 002 : Risque argile, le silence communal

Sources :
- GASPAR (risq + dicrim) — Géorisques, ministère de la Transition écologique
- DVF — data.gouv.fr (prix médians par département, déjà agrégé)
- Fonds prévention argile — service-public.gouv.fr + Banque des Territoires
- RGA exposition régionale — CCR, Diagamter, arrêté 9 janvier 2026

Les fichiers DVF et fonds prévention sont déjà versionnés dans data/raw/ car
ils proviennent de sources stables ou de compilations manuelles. Ce script
se concentre sur GASPAR, qui est la base vivante publiée par Géorisques.

Produit :
    data/raw/gaspar/risq_gaspar.csv
    data/raw/gaspar/dicrim_gaspar.csv

Après exécution, lancer :
    python scripts/01_merge.py
"""

from __future__ import annotations

import sys
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
GASPAR_OUT = RAW / "gaspar"
GASPAR_OUT.mkdir(parents=True, exist_ok=True)

# URL stable publiée par Géorisques. Si le lien casse, consulter :
# https://www.georisques.gouv.fr/donnees/bases-de-donnees/gaspar
GASPAR_URL = "https://files.georisques.fr/gaspar/gaspar.zip"

# Fichiers à extraire depuis le zip GASPAR
# risq   : table des risques par commune (on filtre "tassement différentiel" = RGA)
# dicrim : dates de publication des DICRIM par commune
# tim    : dates de transmission du DDRM par le préfet à chaque maire
#          (utilisé pour la matrice TIM × DICRIM et l'effet ciseaux)
WANTED_FILES = {
    "risq_gaspar.csv",
    "dicrim_gaspar.csv",
    "tim_gaspar.csv",
}


def download_gaspar() -> None:
    """Télécharge le zip GASPAR et extrait les deux CSV utiles."""
    print(f"→ Téléchargement GASPAR : {GASPAR_URL}")
    req = Request(
        GASPAR_URL,
        headers={"User-Agent": "tawiza-article-002/1.0 (analyse reproductible)"},
    )
    with urlopen(req, timeout=120) as resp:
        data = resp.read()
    print(f"  reçu : {len(data) / 1e6:.1f} Mo")

    with zipfile.ZipFile(BytesIO(data)) as zf:
        members = zf.namelist()
        found: set[str] = set()
        for member in members:
            name = Path(member).name.lower()
            if name in WANTED_FILES:
                target = GASPAR_OUT / name
                with zf.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                print(f"  extrait : {target.relative_to(BASE)}")
                found.add(name)

        missing = WANTED_FILES - found
        if missing:
            print(
                f"⚠️  Fichiers attendus non trouvés dans le zip : {sorted(missing)}",
                file=sys.stderr,
            )
            print(
                "   Contenu du zip (10 premiers) : "
                f"{members[:10]}",
                file=sys.stderr,
            )
            sys.exit(1)


def main() -> None:
    download_gaspar()
    print()
    print("✅ Données brutes téléchargées.")
    print("   Étape suivante : python scripts/01_merge.py")


if __name__ == "__main__":
    main()
