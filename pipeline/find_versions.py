"""Propose des versions candidates (autres éditions) de chaque livre, d'après la BnF.

Rien n'est ajouté à la base : le résultat est écrit dans
data/processed/versions_candidates.csv, à relire. Pour valider une ligne :

    python pipeline/add_book.py ISBN --livre "Nom du livre" --version V2 --serie ... --numero ...

(pensez aussi à renseigner `livre` sur l'édition V1 de ce livre dans editions.csv).

    python pipeline/find_versions.py                 # tous les livres
    python pipeline/find_versions.py --serie "Défis Fantastiques"
"""
import argparse
import csv
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
from enrich_bnf import norm, similitude

SORTIE = editions.ROOT / "data" / "processed" / "versions_candidates.csv"
NS = {"srw": "http://www.loc.gov/zing/srw/", "dc": "http://purl.org/dc/elements/1.1/"}
ENTETE = ["id_v1", "titre_v1", "serie_v1", "numero_v1", "isbn13_candidat", "titre_bnf", "editeur",
          "annee", "collection", "livre_jeu_confirme", "notice_bnf", "ordre_chrono"]


def nom_famille(auteurs):
    premier = (auteurs or "").split(";")[0].strip()
    return premier.split()[-1] if premier else ""


def chercher(titre, famille):
    mots = re.sub(r"[\"'’]", " ", titre).strip()
    q = f'bib.title all "{mots}"' + (f' and bib.author all "{famille}"' if famille else "")
    r = requests.get(editions.BNF_URL, timeout=40, headers={"User-Agent": "LDVELH-catalogue/0.1"},
                     params={"version": "1.2", "operation": "searchRetrieve",
                             "recordSchema": "dublincore", "maximumRecords": "30", "query": q})
    r.raise_for_status()
    return ET.fromstring(r.content).iterfind(".//srw:record", NS)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--serie", help="se limiter à une série")
    a = p.parse_args()
    rows = editions.load()
    connus = {r["isbn13"] for r in rows if r["isbn13"]}
    cibles = [r for r in rows if r["isbn13"] and r["statut"] == "enrichi"
              and (not a.serie or r["serie"].lower() == a.serie.lower())]
    sortie, vus = [], set()
    print(f"{len(cibles)} livre(s) à examiner")
    for i, r in enumerate(cibles, start=1):
        time.sleep(1.0)
        try:
            notices = list(chercher(r["titre"], nom_famille(r["auteurs"])))
        except Exception as e:
            print(f"  ! {r['titre']} : {e}")
            continue
        cands = []
        for rec in notices:
            g = lambda t: [e.text.strip() for e in rec.iterfind(f".//dc:{t}", NS) if e.text]
            titre_bnf = (g("title") or [""])[0].split(" / ")[0]
            if similitude(r["titre"], titre_bnf) < 0.8:
                continue
            isbn = next((x[5:] for x in g("identifier") if x.startswith("ISBN ")), "")
            try:
                isbn13 = editions.normalize_isbn(isbn)[0]
            except ValueError:
                continue
            if isbn13 in connus or (r["id"], isbn13) in vus:
                continue  # c'est déjà un livre de la base (ou un doublon de notice)
            vus.add((r["id"], isbn13))
            col = next((d[len("Collection : "):] for d in g("description") if d.startswith("Collection : ")), "")
            cands.append([r["id"], r["titre"], r["serie"], r["numero"], isbn13, titre_bnf,
                          re.sub(r"\s*\(.*?\)", "", (g("publisher") or [""])[0]), (g("date") or [""])[0][:4],
                          col, "", next((x for x in g("identifier") if x.startswith("http")), "")])
        cands.sort(key=lambda c: c[7] or "9999")
        for n, c in enumerate(cands, start=1):
            sortie.append(c + [n])
        if i % 20 == 0:
            print(f"  {i}/{len(cibles)} ...", flush=True)
    with open(SORTIE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(ENTETE)
        w.writerows(sortie)
    livres = len({l[0] for l in sortie})
    print(f"{len(sortie)} édition(s) candidate(s) pour {livres} livre(s) -> {SORTIE}")


if __name__ == "__main__":
    main()
