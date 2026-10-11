"""Ajoute une observation de prix réel (vente, achat, trouvaille) à data/manual/observations.csv.

    python pipeline/add_prix.py 9782070583805 12.5 --etat bon --type vente
    python pipeline/add_prix.py 9782070583805 8 --etat tres_bon --type achat --date 2026-10-03 --url https://...

Types : vente (vous avez vendu à ce prix), achat (vous avez acheté), releve (prix vu sur une annonce),
        rachat (offre d'un professionnel). Une vente réelle compte plus qu'une annonce dans l'estimation.
Ensuite : python pipeline/build_db.py && python pipeline/export_site.py
"""
import argparse
import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions

MANUEL = editions.ROOT / "data" / "manual" / "observations.csv"
CHAMPS = ["isbn", "date", "source", "type_prix", "etat", "prix", "frais_port", "lot", "url", "nb"]
TYPES = {  # option -> (source, type_prix)
    "vente": ("vente_perso", "vente_reelle"),
    "achat": ("achat_perso", "vente_reelle"),
    "releve": ("releve_manuel", "prix_demande"),
    "rachat": ("releve_manuel", "rachat"),
}
ETATS = ("convenable", "bon", "tres_bon")


def ligne(isbn, prix, etat, type_, jour, port=None, url=None, lot=0):
    isbn13 = editions.normalize_isbn(isbn)[0]
    if etat not in ETATS:
        raise ValueError(f"état inconnu : {etat} (choix : {', '.join(ETATS)})")
    if type_ not in TYPES:
        raise ValueError(f"type inconnu : {type_} (choix : {', '.join(TYPES)})")
    if prix <= 0:
        raise ValueError("le prix doit être positif")
    source, type_prix = TYPES[type_]
    return {"isbn": isbn13, "date": jour.isoformat(), "source": source, "type_prix": type_prix, "etat": etat,
            "prix": f"{prix:.2f}", "frais_port": "" if port is None else f"{port:.2f}", "lot": int(lot),
            "url": url or "", "nb": 1}


def ajouter(chemin, row):
    chemin = Path(chemin)
    existe = chemin.exists() and chemin.stat().st_size > 0
    if existe:
        with open(chemin, newline="", encoding="utf-8") as f:
            entete = next(csv.reader(f), None) or []
        champs = entete if set(entete) >= set(row) - {"nb"} else CHAMPS
    else:
        champs = CHAMPS
    with open(chemin, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=champs, extrasaction="ignore")
        if not existe:
            w.writeheader()
        w.writerow(row)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("isbn")
    p.add_argument("prix", type=float, help="en euros, hors port")
    p.add_argument("--etat", required=True, choices=ETATS)
    p.add_argument("--type", dest="type_", default="vente", choices=list(TYPES))
    p.add_argument("--date", type=date.fromisoformat, default=date.today())
    p.add_argument("--port", type=float)
    p.add_argument("--url")
    p.add_argument("--lot", action="store_true", help="prix d'un lot : non utilisé dans l'estimation")
    p.add_argument("--fichier", default=str(MANUEL))
    a = p.parse_args()
    try:
        row = ligne(a.isbn, a.prix, a.etat, a.type_, a.date, a.port, a.url, a.lot)
    except ValueError as e:
        sys.exit(f"Erreur : {e}")
    ajouter(a.fichier, row)
    print(f"Ajouté : {row['isbn']} · {a.etat} · {row['prix']} € · {a.type_} · {row['date']}")


if __name__ == "__main__":
    main()
