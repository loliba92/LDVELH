"""Image d'ambiance de l'accueil, choisie sur Pexels (interface officielle, clé en variable d'environnement).

La photo est téléchargée une fois, redimensionnée et enregistrée dans le dépôt : le site ne dépend pas de Pexels
à l'affichage, et la clé n'est jamais envoyée au navigateur.

    PEXELS_API_KEY=... python scrapers/image_accueil.py --chercher "old library books warm light" --sortie /tmp/candidats
    PEXELS_API_KEY=... python scrapers/image_accueil.py --retenir 37302575

Clé : variable d'environnement PEXELS_API_KEY (jamais dans le dépôt). Le choix final reste un geste humain.
"""
import argparse
import io
import os
import sys
from pathlib import Path

import requests
from PIL import Image

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "web" / "images" / "accueil.webp"
LARGEUR = 1600
API = "https://api.pexels.com/v1"


def cle():
    k = os.environ.get("PEXELS_API_KEY")
    if not k:
        sys.exit("Clé absente : définissez la variable d'environnement PEXELS_API_KEY.")
    return {"Authorization": k}


def chercher(requete, sortie, nombre):
    r = requests.get(f"{API}/search", headers=cle(), params={"query": requete, "per_page": nombre, "orientation": "landscape"}, timeout=30)
    r.raise_for_status()
    Path(sortie).mkdir(parents=True, exist_ok=True)
    for ph in r.json().get("photos", []):
        img = requests.get(ph["src"]["medium"], timeout=60).content
        (Path(sortie) / f"{ph['id']}.jpg").write_bytes(img)
        print(f"{ph['id']} · {ph['width']}x{ph['height']} · {ph['photographer']} · {ph['url']}")


def retenir(photo_id):
    r = requests.get(f"{API}/photos/{photo_id}", headers=cle(), timeout=30)
    r.raise_for_status()
    ph = r.json()
    brut = requests.get(ph["src"]["large2x"], timeout=120).content
    im = Image.open(io.BytesIO(brut)).convert("RGB")
    im = im.resize((LARGEUR, round(im.height * LARGEUR / im.width)), Image.LANCZOS)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    im.save(SORTIE, "WEBP", quality=72, method=6)
    print(f"{SORTIE.relative_to(RACINE)} : {im.width}x{im.height}, {SORTIE.stat().st_size // 1024} Ko")
    print(f"Crédit à afficher : photo de {ph['photographer']}, {ph['photographer_url']} · {ph['url']}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--chercher", metavar="REQUETE")
    p.add_argument("--sortie", default="candidats")
    p.add_argument("--nombre", type=int, default=12)
    p.add_argument("--retenir", type=int, metavar="ID")
    a = p.parse_args()
    if a.chercher:
        chercher(a.chercher, a.sortie, a.nombre)
    elif a.retenir:
        retenir(a.retenir)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
