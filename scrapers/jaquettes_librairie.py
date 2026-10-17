"""Jaquettes des éditions qui n'en ont pas, d'après la fiche de leslibraires.fr (image de couverture affichée sur la fiche).

Pour chaque édition avec ISBN et sans fichier dans web/covers/, lit la fiche /livre/<isbn> (autorisée par le robots.txt du site),
télécharge l'image de couverture qu'elle affiche et l'enregistre dans les deux tailles du site (voir telecharger_jaquettes.py).
Une requête par seconde et demie ; une fiche absente ou sans couverture est simplement ignorée.

Droits : les jaquettes appartiennent à leurs éditeurs ; elles sont reproduites à titre d'illustration.

    python scrapers/jaquettes_librairie.py            # toutes les jaquettes manquantes
    python scrapers/jaquettes_librairie.py --limite 5 # essai
"""
import io
import re
import shutil
import sys
import time
from pathlib import Path

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
from prix_neuf import AGENT, URL
from telecharger_jaquettes import DOSSIER, TAILLES, enregistrer

PAUSE = 1.5
IMAGE = re.compile(r'(?:https?:)?//[\w.-]+\.b-cdn\.net/[\w\-/]+/s:\d+:\d+/[\w\-]+\.webp')


def adresse_couverture(html):
    """Adresse de l'image de couverture d'une fiche (la grande), ou None."""
    m = IMAGE.search(html)
    if not m:
        return None
    a = m.group(0)
    return "https:" + a if a.startswith("//") else a


def est_maquette(octets):
    """Vrai pour une image en relief du livre sur fond blanc (fond blanc ou noir uni tout autour) plutôt qu'une couverture à plat."""
    im = Image.open(io.BytesIO(octets)).convert("RGB")
    w, h = im.size
    bords = [im.getpixel(p) for p in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3), (w // 2, 2), (w // 2, h - 3), (2, h // 2), (w - 3, h // 2))]
    return all(min(c) > 235 for c in bords) or all(max(c) < 15 for c in bords)    # fond blanc ou fond noir uni tout autour


def a_faire(rows):
    return [r for r in rows if r.get("isbn13") and not all((DOSSIER / t / f"{editions.cle_image(r['id'], r['isbn13'])}.webp").exists() for t in TAILLES)]


def main():
    limite = int(sys.argv[sys.argv.index("--limite") + 1]) if "--limite" in sys.argv else None
    lignes = a_faire(editions.load())[:limite]
    print(f"{len(lignes)} jaquettes manquantes à chercher", flush=True)
    ok, sans, maquettes = 0, [], []
    s = requests.Session()
    s.headers.update({"User-Agent": AGENT})
    for r in lignes:
        time.sleep(PAUSE)
        try:
            f = s.get(URL.format(isbn=r["isbn13"]), timeout=30)
            adresse = adresse_couverture(f.text) if f.status_code == 200 else None
            if not adresse:
                sans.append((r["isbn13"], r["titre"]))
                continue
            img = s.get(adresse, timeout=40)
            if img.status_code != 200 or not img.headers.get("content-type", "").startswith("image"):
                sans.append((r["isbn13"], r["titre"]))
                continue
            if est_maquette(img.content):
                maquettes.append((r, img.content))
                continue
            enregistrer(img.content, r["isbn13"])
            ok += 1
        except (requests.RequestException, OSError) as e:
            sans.append((r["isbn13"], f"{r['titre']} ({str(e)[:40]})"))
    # Image en relief : on reprend la couverture à plat d'une autre édition du même livre (même illustration), si elle existe ; sinon on garde l'image en relief
    tout = editions.load()
    for r, contenu in maquettes:
        autre = next((x for x in tout if x["isbn13"] != r["isbn13"] and x.get("livre") == r.get("livre") and x.get("serie") == r.get("serie")
                      and all((DOSSIER / t / f"{x['isbn13']}.webp").exists() for t in TAILLES)), None)
        if autre:
            for t in TAILLES:
                shutil.copy(DOSSIER / t / f"{autre['isbn13']}.webp", DOSSIER / t / f"{r['isbn13']}.webp")
            ok += 1
            print(f"  = {r['titre']} ({r['version']}) : couverture d'une autre édition du même livre ({autre['version']})", flush=True)
        else:                                                   # faute de mieux (accepté le 17 octobre 2026) : l'image en relief, plutôt qu'une tuile vide
            enregistrer(contenu, r["isbn13"])
            ok += 1
            print(f"  ~ {r['titre']} ({r['version']}) : image en relief, faute de couverture à plat", flush=True)
    print(f"Jaquettes ajoutées : {ok} ; introuvables : {len(sans)}", flush=True)
    for x in sans[:60]:
        print("  ✗", x, flush=True)


if __name__ == "__main__":
    main()
