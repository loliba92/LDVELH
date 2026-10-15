"""Prix du neuf et disponibilité des éditions encore en vente, lus sur la fiche de chaque livre du site leslibraires.fr.

Pourquoi ce site : le livre y a un prix unique en France (le prix éditeur, loi sur le prix unique du livre), la fiche donne la
disponibilité (en stock ou non) dans un balisage standard (schema.org), son robots.txt autorise la lecture des fiches
(`/livre/`), et il répond à un programme. Le site de l'éditeur, lui, rejette les programmes.
Une requête par ISBN, une seconde d'écart, un nom de programme explicite : une lecture légère, une fois par semaine.
Écrit `data/processed/prix_neuf.csv` (isbn13, prix, disponibilite, date, source). Une édition dont la fiche n'existe plus ou
n'est pas « en stock » est notée « indisponible » : l'export la considère hors vente.
Usage : python pipeline/prix_neuf.py [--limite N]
"""
import argparse
import csv
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions

SORTIE = Path(__file__).resolve().parent.parent / "data" / "processed" / "prix_neuf.csv"
URL = "https://www.leslibraires.fr/livre/{isbn}"
CHAMPS = ["isbn13", "prix", "disponibilite", "date", "source"]
PAUSE = 2.0
ESSAIS = (3, 8, 20)        # attentes (secondes) avant de réessayer après une erreur passagère (429, 5xx, réseau)
AGENT = "LDVELH-catalogue/0.1 (projet personnel de cote de livres-jeux ; lecture hebdomadaire d'une fiche par ISBN)"


def lire_fiche(html):
    """(prix, disponibilité) d'une fiche : prix en euros ou None ; disponibilité « en_stock » ou « indisponible »."""
    m = re.search(r'itemprop="price"\s+content="(\d+(?:\.\d{1,2})?)"', html)
    prix = float(m.group(1)) if m and 0 < float(m.group(1)) < 1000 else None
    dispo = re.search(r'itemprop="availability"\s+href="https?://schema\.org/(\w+)"', html)
    neuf = re.search(r'itemprop="itemCondition"\s+href="https?://schema\.org/NewCondition"', html)
    en_stock = bool(dispo and dispo.group(1) == "InStock" and neuf)
    return prix, ("en_stock" if en_stock else "indisponible")


def interroger(isbn, http=requests, attentes=ESSAIS):
    """(prix, disponibilité) ; 404 = fiche absente = indisponible ; erreur passagère : on réessaie, puis on lève l'erreur."""
    dernier = None
    for attente in (0,) + tuple(attentes):
        time.sleep(attente)
        try:
            r = http.get(URL.format(isbn=isbn), headers={"User-Agent": AGENT}, timeout=30, allow_redirects=True)
            if r.status_code == 404:
                return None, "indisponible"
            if r.status_code == 429 or r.status_code >= 500:
                dernier = requests.HTTPError(f"HTTP {r.status_code}")
                continue
            r.raise_for_status()
            return lire_fiche(r.text)
        except requests.RequestException as e:
            dernier = e
    raise dernier


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limite", type=int)
    a = ap.parse_args()
    isbns = sorted({r["isbn13"] for r in editions.load() if r.get("isbn13") and str(r.get("en_vente") or "").strip() not in ("", "0")})[: a.limite]
    lignes, erreurs = [], 0
    for n, isbn in enumerate(isbns, 1):
        try:
            prix, dispo = interroger(isbn)
        except requests.RequestException as e:
            erreurs += 1
            print(f"  {isbn} : erreur réseau ({e.__class__.__name__}), ignoré")
            continue
        lignes.append({"isbn13": isbn, "prix": "" if prix is None else prix, "disponibilite": dispo, "date": date.today().isoformat(), "source": "leslibraires.fr"})
        time.sleep(PAUSE)
    if erreurs > len(isbns) / 2:
        sys.exit("Trop d'erreurs réseau : le fichier précédent est conservé.")
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS)
        w.writeheader()
        w.writerows(lignes)
    dispo = sum(1 for l in lignes if l["disponibilite"] == "en_stock")
    print(f"{len(lignes)} éditions lues, {dispo} en stock, {len(lignes) - dispo} indisponibles : {SORTIE}")


if __name__ == "__main__":
    main()
