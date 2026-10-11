"""Crée data/processed/editions.csv à partir du dernier relevé de collection-ldvelh.fr."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions

RAW = editions.ROOT / "data" / "raw" / "collection-ldvelh"
latest = sorted(RAW.glob("books_data-*.csv"))[-1]

rows = []
with open(latest, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        isbn = (r.get("isbn") or "").strip()
        serie = (r.get("serie") or "").strip()
        numero = (r.get("numero") or "").strip()
        try:
            isbn13, isbn10 = editions.normalize_isbn(isbn)
            ident = isbn13
        except ValueError:
            isbn13 = isbn10 = ""
            ident = f"LOCAL-{serie}-{numero}".replace(" ", "_")
        rows.append({"id": ident, "isbn13": isbn13, "isbn10": isbn10, "titre": r["titre"],
                     "serie": serie, "numero": numero, "editeur": "",
                     "annee": (r.get("date") or "")[:4], "statut": "brut",
                     "source": "collection-ldvelh", "date_maj": editions.today()})

editions.save(rows)
sans_isbn = sum(1 for r in rows if not r["isbn13"])
print(f"{len(rows)} éditions écrites dans {editions.BASE} ({sans_isbn} sans ISBN valide)")
