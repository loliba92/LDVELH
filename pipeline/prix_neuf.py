"""Prix du neuf, disponibilité et exemplaire d'occasion d'un livre à partir de son ISBN : `prix_neuf(isbn)`.

    >>> prix_neuf("9782075148641")
    {'isbn13': '9782075148641', 'prix': 13.5, 'disponibilite': 'en_stock', 'prix_occasion': None, 'source': 'leslibraires.fr', 'date': '2026-10-15'}

Sources essayées dans l'ordre (liste SOURCES) : la première qui répond donne le résultat. Aujourd'hui une seule répond à un
programme : leslibraires.fr (réseau de librairies indépendantes ; prix unique du livre en France, donc le prix éditeur ; fiche
`/livre/<isbn>` avec prix et disponibilité en balisage schema.org ; `robots.txt` favorable). Les autres grands vendeurs ont été
essayés le 15 octobre 2026 et refusent tous les programmes : Amazon (captcha), Cultura, Fnac, Furet du Nord, Momox, Rakuten
(HTTP 403 ou défi anti-robot), Decitre et Chapitre (erreur ou 429), le site de l'éditeur (« Request Rejected »). Pour ajouter une source,
écrire une fonction `(isbn, http, attentes) -> {"prix", "disponibilite", "prix_occasion"}` et l'ajouter à SOURCES.

La fiche montre soit le livre neuf (prix = prix du neuf), soit, pour un livre épuisé, l'exemplaire d'occasion qu'une librairie
propose (prix_occasion ; aucun état n'est indiqué). Ces exemplaires d'occasion entrent dans la cote avec les annonces eBay.

Une requête par ISBN, 2 secondes d'écart, nom de programme explicite, réessais après une erreur passagère.
Lot hebdomadaire (workflow `prix-ebay.yml`) : toutes les éditions du catalogue, donc aussi les nouvelles dès qu'elles y entrent.
Écrit `data/processed/prix_neuf.csv` (isbn13, prix, disponibilite, prix_occasion, date, source) et, pour l'occasion, un relevé daté
`data/raw/occasion/libraires-AAAA-MM-JJ.csv` au même format que celui d'eBay (une annonce, état non précisé : très bon état, règle du propriétaire).
« indisponible » = fiche absente ou livre pas en stock neuf : l'export le considère hors vente.
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
OCCASION = Path(__file__).resolve().parent.parent / "data" / "raw" / "occasion"
URL = "https://www.leslibraires.fr/livre/{isbn}"
CHAMPS = ["isbn13", "prix", "disponibilite", "prix_occasion", "date", "source"]
CHAMPS_OCCASION = ["isbn13", "date", "etat", "nb_annonces", "prix_min", "prix_median", "prix_max", "nb_toutes", "prix_median_toutes"]
ETAT_OCCASION = "tres_bon"   # aucun état n'est indiqué : très bon état (règle du propriétaire)
PAUSE = 2.0
ESSAIS = (3, 8, 20)        # attentes (secondes) avant de réessayer après une erreur passagère (429, 5xx, réseau)
AGENT = "LDVELH-catalogue/0.1 (projet personnel de cote de livres-jeux ; lecture hebdomadaire d'une fiche par ISBN)"


def lire_fiche(html):
    """{prix, disponibilite, prix_occasion} d'une fiche. Neuf en stock : prix = prix du neuf, disponibilite « en_stock » ;
    exemplaire d'occasion en stock : prix_occasion ; sinon « indisponible »."""
    m = re.search(r'itemprop="price"\s+content="(\d+(?:\.\d{1,2})?)"', html)
    prix = float(m.group(1)) if m and 0 < float(m.group(1)) < 1000 else None
    dispo = re.search(r'itemprop="availability"\s+href="https?://schema\.org/(\w+)"', html)
    etat = re.search(r'itemprop="itemCondition"\s+href="https?://schema\.org/(\w+)"', html)
    en_stock = bool(dispo and dispo.group(1) == "InStock" and etat)
    if en_stock and etat.group(1) == "NewCondition":
        return {"prix": prix, "disponibilite": "en_stock", "prix_occasion": None}
    if en_stock and etat.group(1) == "UsedCondition" and prix:
        return {"prix": None, "disponibilite": "indisponible", "prix_occasion": prix}
    return {"prix": None, "disponibilite": "indisponible", "prix_occasion": None}


def source_leslibraires(isbn, http=requests, attentes=ESSAIS):
    """Dictionnaire de lire_fiche ; 404 = fiche absente = indisponible ; erreur passagère : on réessaie, puis on lève l'erreur."""
    dernier = None
    for attente in (0,) + tuple(attentes):
        time.sleep(attente)
        try:
            r = http.get(URL.format(isbn=isbn), headers={"User-Agent": AGENT}, timeout=30, allow_redirects=True)
            if r.status_code == 404:
                return {"prix": None, "disponibilite": "indisponible", "prix_occasion": None}
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
    """{isbn13, prix, disponibilite, prix_occasion, source, date} pour un ISBN, ou None si aucune source n'a pu répondre."""
    isbn = re.sub(r"[^0-9X]", "", str(isbn).upper())
    for nom, source in SOURCES:
        try:
            r = source(isbn, http, attentes)
        except requests.RequestException:
            continue
        return {"isbn13": isbn, **r, "source": nom, "date": date.today().isoformat()}
    return None


def a_interroger(lignes):
    """ISBN du lot : toutes les éditions du catalogue (le neuf pour les éditions récentes, l'occasion pour toutes)."""
    return sorted({r["isbn13"] for r in lignes if r.get("isbn13")})


def ligne_occasion(r):
    """Ligne au format du relevé eBay pour l'exemplaire d'occasion d'une fiche, ou None."""
    po = r.get("prix_occasion")
    if not po:
        return None
    p = f"{po:.2f}"
    return {"isbn13": r["isbn13"], "date": r["date"], "etat": ETAT_OCCASION, "nb_annonces": 1, "prix_min": p, "prix_median": p,
            "prix_max": p, "nb_toutes": 1, "prix_median_toutes": p}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limite", type=int)
    ap.add_argument("--isbn", help="un seul ISBN : affiche le résultat, n'écrit rien")
    a = ap.parse_args()
    if a.isbn:
        print(prix_neuf(a.isbn) or "Aucune source n'a répondu.")
        return
    isbns = a_interroger(editions.load())[: a.limite]
    lignes, occasion, erreurs = [], [], 0
    for n, isbn in enumerate(isbns, 1):
        r = prix_neuf(isbn)
        if r is None:
            erreurs += 1
            print(f"  {isbn} : aucune source n'a répondu, ignoré")
            continue
        lignes.append({"isbn13": isbn, "prix": "" if r["prix"] is None else r["prix"], "disponibilite": r["disponibilite"],
                       "prix_occasion": "" if r["prix_occasion"] is None else r["prix_occasion"], "date": r["date"], "source": r["source"]})
        if ligne_occasion(r):
            occasion.append(ligne_occasion(r))
        time.sleep(PAUSE)
    if erreurs > len(isbns) / 2:
        sys.exit("Trop d'erreurs réseau : le fichier précédent est conservé.")
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS)
        w.writeheader()
        w.writerows(lignes)
    OCCASION.mkdir(parents=True, exist_ok=True)
    with open(OCCASION / f"libraires-{date.today().isoformat()}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS_OCCASION)
        w.writeheader()
        w.writerows(occasion)
    dispo = sum(1 for l in lignes if l["disponibilite"] == "en_stock")
    print(f"{len(lignes)} éditions lues, {dispo} en stock neuf, {len(occasion)} avec un exemplaire d'occasion : {SORTIE}")


if __name__ == "__main__":
    main()
