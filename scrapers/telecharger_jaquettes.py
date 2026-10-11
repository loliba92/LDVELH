"""Télécharge les jaquettes de collection-ldvelh.fr dans web/covers/ (reprise possible).

Pour chaque édition de editions.csv qui a une adresse de jaquette, enregistre :
  web/covers/small/ISBN.webp    jaquette des cartes et des listes (320 px de large, nette sur écran haute densité)
  web/covers/medium/ISBN.webp   image de la fiche (600 px de large)
Les images sont recompressées pour garder un dépôt léger. Une seconde de pause entre deux
téléchargements. Les fichiers déjà présents ne sont pas retéléchargés.

Droits : les jaquettes appartiennent à leurs éditeurs ; source : collection-ldvelh.fr.

    python scrapers/telecharger_jaquettes.py            # seulement les images manquantes
    python scrapers/telecharger_jaquettes.py --refaire  # tout retélécharger (après un changement de taille)

On part de la grande version de la source (700 px) et on ne grandit jamais une image : au-dessus de la taille
d'origine, la taille d'origine est conservée.
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
TAILLES = {"small": (320, 76), "medium": (600, 78)}  # largeur en pixels, qualité webp
PAUSE = 1.0
HEADERS = {"User-Agent": "LDVELH-catalogue/0.1 (projet personnel de cote de livres-jeux)"}


def enregistrer(octets, isbn):
    image = Image.open(io.BytesIO(octets)).convert("RGB")
    for nom, (largeur, qualite) in TAILLES.items():
        largeur = min(largeur, image.width)          # jamais d'agrandissement
        hauteur = round(image.height * largeur / image.width)
        sortie = DOSSIER / nom / f"{isbn}.webp"
        sortie.parent.mkdir(parents=True, exist_ok=True)
        image.resize((largeur, hauteur), Image.LANCZOS).save(sortie, "WEBP", quality=qualite, method=6)


def main():
    lignes = [r for r in editions.load() if r.get("couverture") and r["isbn13"]]
    refaire = "--refaire" in sys.argv
    a_faire = [r for r in lignes if refaire or not all((DOSSIER / t / f"{r['isbn13']}.webp").exists() for t in TAILLES)]
    print(f"{len(lignes)} jaquettes connues, {len(a_faire)} à télécharger", flush=True)
    session = requests.Session()
    session.headers.update(HEADERS)
    ok, echecs = 0, []
    for i, r in enumerate(a_faire, start=1):
        time.sleep(PAUSE)
        try:
            for taille in ("large", "medium", "small"):   # la plus grande version disponible
                rep = session.get(r["couverture"].replace("/small/", f"/{taille}/"), timeout=40)
                if rep.status_code == 200 and rep.headers.get("content-type", "").startswith("image"):
                    break
            else:
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
