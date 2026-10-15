"""Prix du neuf et disponibilité d'un livre à partir de son ISBN : `prix_neuf(isbn)`.

    >>> prix_neuf("9782075148641")
    {'isbn13': '9782075148641', 'prix': 13.5, 'disponibilite': 'en_stock', 'source': 'leslibraires.fr', 'date': '2026-10-15'}

Sources essayées dans l'ordre (liste SOURCES) : la première qui répond donne le résultat. Aujourd'hui une seule répond à un
programme : leslibraires.fr (réseau de librairies indépendantes ; prix unique du livre en France, donc le prix éditeur ; fiche
`/livre/<isbn>` avec prix et disponibilité en balisage schema.org ; `robots.txt` favorable). Les autres grands vendeurs ont été
essayés le 15 octobre 2026 et refusent tous les programmes : Amazon (captcha), Cultura, Fnac, Furet du Nord, Momox, Rakuten
(HTTP 403 ou défi anti-robot), Decitre et Chapitre (erreur ou 429), le site de l'éditeur (« Request Rejected »). Pour ajouter une source,
écrire une fonction `(isbn, http) -> (prix, disponibilite)` et l'ajouter à SOURCES.

Une requête par ISBN, 2 secondes d'écart, nom de programme explicite, réessais après une erreur passagère.
Lot hebdomadaire (workflow `prix-ebay.yml`) : toutes les éditions récentes (parues depuis 2010) ou marquées « en vente » du catalogue,
donc aussi les nouvelles éditions dès qu'elles entrent au catalogue. Écrit `data/processed/prix_neuf.csv` (isbn13, prix,
disponibilite, date, source). « indisponible » = fiche absente ou livre pas en stock neuf : l'export le considère hors vente.
Usage : python pipeline/prix_neuf.py [--isbn ISBN] [--limite N]
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
ANNEE_MIN = 2010            # les éditions plus anciennes ne sont plus au catalogue des éditeurs (sauf marquage « en vente »)
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


def source_leslibraires(isbn, http=requests, attentes=ESSAIS):
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


SOURCES = [("leslibraires.fr", source_leslibraires)]


def prix_neuf(isbn, http=requests, attentes=ESSAIS):
    """{isbn13, prix, disponibilite, source, date} pour un ISBN, ou None si aucune source n'a pu répondre."""
    isbn = re.sub(r"[^0-9X]", "", str(isbn).upper())
    for nom, source in SOURCES:
        try:
            prix, dispo = source(isbn, http, attentes)
        except requests.RequestException:
            continue
        return {"isbn13": isbn, "prix": prix, "disponibilite": dispo, "source": nom, "date": date.today().isoformat()}
    return None


def a_interroger(lignes):
    """ISBN du lot : éditions parues depuis ANNEE_MIN ou marquées « en vente »."""
    def annee(r):
        try:
            return int(r.get("annee") or r.get("annee_bnf") or 0)
        except ValueError:
            return 0
    return sorted({r["isbn13"] for r in lignes if r.get("isbn13") and (annee(r) >= ANNEE_MIN or str(r.get("en_vente") or "").strip() not in ("", "0"))})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limite", type=int)
    ap.add_argument("--isbn", help="un seul ISBN : affiche le résultat, n'écrit rien")
    a = ap.parse_args()
    if a.isbn:
        print(prix_neuf(a.isbn) or "Aucune source n'a répondu.")
        return
    isbns = a_interroger(editions.load())[: a.limite]
    lignes, erreurs = [], 0
    for n, isbn in enumerate(isbns, 1):
        r = prix_neuf(isbn)
        if r is None:
            erreurs += 1
            print(f"  {isbn} : aucune source n'a répondu, ignoré")
            continue
        lignes.append({"isbn13": isbn, "prix": "" if r["prix"] is None else r["prix"], "disponibilite": r["disponibilite"], "date": r["date"], "source": r["source"]})
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
