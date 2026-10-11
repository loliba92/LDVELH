"""Télécharge les jaquettes de collection-ldvelh.fr dans web/covers/ (reprise possible).

Pour chaque édition de editions.csv qui a une adresse de jaquette, enregistre :
  web/covers/small/ISBN.webp    miniature de la liste (88 px de large)
  web/covers/medium/ISBN.webp   image de la fiche (300 px de large)
Les images sont recompressées pour garder un dépôt léger. Une seconde de pause entre deux
téléchargements. Les fichiers déjà présents ne sont pas retéléchargés.

Droits : les jaquettes appartiennent à leurs éditeurs ; source : collection-ldvelh.fr.

    python scrapers/telecharger_jaquettes.py
"""
import io
import sys
import time
from pathlib import Path

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import editions

DOSSIER = editions.ROOT / "web" / "covers"
TAILLES = {"small": (88, 80), "medium": (300, 82)}  # largeur en pixels, qualité webp
PAUSE = 1.0
HEADERS = {"User-Agent": "LDVELH-catalogue/0.1 (projet personnel de cote de livres-jeux)"}


def enregistrer(octets, isbn):
    image = Image.open(io.BytesIO(octets)).convert("RGB")
    for nom, (largeur, qualite) in TAILLES.items():
        hauteur = round(image.height * largeur / image.width)
        sortie = DOSSIER / nom / f"{isbn}.webp"
        sortie.parent.mkdir(parents=True, exist_ok=True)
        image.resize((largeur, hauteur), Image.LANCZOS).save(sortie, "WEBP", quality=qualite, method=6)


def main():
    lignes = [r for r in editions.load() if r.get("couverture") and r["isbn13"]]
    a_faire = [r for r in lignes if not all((DOSSIER / t / f"{r['isbn13']}.webp").exists() for t in TAILLES)]
    print(f"{len(lignes)} jaquettes connues, {len(a_faire)} à télécharger", flush=True)
    session = requests.Session()
    session.headers.update(HEADERS)
    ok, echecs = 0, []
    for i, r in enumerate(a_faire, start=1):
        time.sleep(PAUSE)
        url = r["couverture"].replace("/small/", "/medium/")  # on part de la taille moyenne
        try:
            rep = session.get(url, timeout=40)
            if rep.status_code != 200 or not rep.headers.get("content-type", "").startswith("image"):
                raise ValueError(f"HTTP {rep.status_code}")
            enregistrer(rep.content, r["isbn13"])
            ok += 1
        except Exception as e:
            echecs.append((r["isbn13"], r["titre"], str(e)[:60]))
        if i % 25 == 0:
            print(f"  {i}/{len(a_faire)} ...", flush=True)
    print(f"Téléchargées : {ok} ; échecs : {len(echecs)}", flush=True)
    for e in echecs[:20]:
        print("  ✗", e, flush=True)


if __name__ == "__main__":
    main()
