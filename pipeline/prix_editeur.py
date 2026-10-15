"""Prix éditeur à la parution, lu dans la notice de la BnF (zone 010, sous-zone d : « 12 EUR », « 29 F »…).

Source : interface ouverte du catalogue de la BnF (déjà utilisée pour les notices). C'est le prix de vente neuf fixé par l'éditeur
au moment de la parution, pas le prix d'aujourd'hui. Écrit `data/processed/prix_editeur.csv` (isbn13, prix, devise, texte, date).
Par défaut seules les éditions encore en vente neuve (V5) sont lues : pour les anciennes, la BnF n'a presque jamais de notice par ISBN-13 ni de prix.
Usage : python pipeline/prix_editeur.py [--tous] [--limite N]   (reprend où il s'était arrêté : les ISBN déjà lus sont gardés)
"""
import argparse
import csv
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions

SORTIE = Path(__file__).resolve().parent.parent / "data" / "processed" / "prix_editeur.csv"
URL = "https://catalogue.bnf.fr/api/SRU"
NS = {"srw": "http://www.loc.gov/zing/srw/", "m": "info:lc/xmlns/marcxchange-v2"}
CHAMPS = ["isbn13", "prix", "devise", "texte", "date"]
PAUSE = 0.4


def lire_prix(texte):
    """« 12 EUR » -> (12.0, 'EUR') ; « 29 F » -> (29.0, 'FRF') ; texte inexploitable -> (None, None)."""
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*(EUR|€|F\b|FRF|FF)", str(texte or ""), re.I)
    if not m:
        return None, None
    valeur = float(m.group(1).replace(",", "."))
    devise = "EUR" if m.group(2).upper() in ("EUR", "€") else "FRF"
    return (valeur, devise) if 0 < valeur < 1000 else (None, None)


def prix_de_notice(xml_texte):
    """Texte du premier prix (010 $d) trouvé dans une réponse SRU, ou None."""
    try:
        racine = ET.fromstring(xml_texte)
    except ET.ParseError:
        return None
    for champ in racine.iter("{info:lc/xmlns/marcxchange-v2}datafield"):
        if champ.get("tag") == "010":
            for sf in champ.findall("m:subfield", NS):
                if sf.get("code") == "d" and (sf.text or "").strip():
                    return sf.text.strip()
    return None


def interroger(isbn, http=requests):
    r = http.get(URL, params={"version": "1.2", "operation": "searchRetrieve", "query": f'bib.isbn adj "{isbn}"',
                              "recordSchema": "unimarcxchange", "maximumRecords": "5"},
                 headers={"User-Agent": "LDVELH-catalogue/0.1 (projet personnel de cote de livres-jeux)"}, timeout=30)
    r.raise_for_status()
    return prix_de_notice(r.text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limite", type=int)
    ap.add_argument("--tous", action="store_true", help="lire aussi les éditions qui ne sont plus en vente")
    a = ap.parse_args()
    deja = {}
    if SORTIE.exists():
        with open(SORTIE, newline="", encoding="utf-8") as f:
            deja = {r["isbn13"]: r for r in csv.DictReader(f)}
    isbns = sorted({r["isbn13"] for r in editions.load() if r.get("isbn13") and (a.tous or str(r.get("en_vente") or "").strip() not in ("", "0"))})
    a_lire = [i for i in isbns if i not in deja][: a.limite]
    print(f"{len(isbns)} ISBN, {len(deja)} déjà lus, {len(a_lire)} à lire")
    for n, isbn in enumerate(a_lire, 1):
        try:
            texte = interroger(isbn)
        except requests.RequestException as e:
            print(f"  {isbn} : erreur réseau ({e.__class__.__name__}), ignoré pour cette fois")
            continue
        prix, devise = lire_prix(texte)
        deja[isbn] = {"isbn13": isbn, "prix": "" if prix is None else prix, "devise": devise or "", "texte": texte or "", "date": date.today().isoformat()}
        if n % 50 == 0:
            print(f"  {n}/{len(a_lire)}")
        time.sleep(PAUSE)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS)
        w.writeheader()
        w.writerows(sorted(deja.values(), key=lambda r: r["isbn13"]))
    avec = sum(1 for r in deja.values() if r["prix"] != "")
    print(f"{avec} prix éditeur sur {len(deja)} ISBN lus : {SORTIE}")


if __name__ == "__main__":
    main()
