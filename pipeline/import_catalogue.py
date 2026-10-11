"""Importe les 5 versions (V1 à V5) du dernier relevé de collection-ldvelh.fr dans editions.csv.

- Les éditions déjà présentes (même ISBN) ne sont pas écrasées : seules les colonnes vides
  `version` et `livre` sont complétées.
- Les nouvelles éditions sont ajoutées au statut « brut » (à enrichir ensuite avec enrich_bnf.py).
- Les versions d'un même livre sont reliées par le TITRE, dans la même série : le « rang dans la
  série » du site change d'une version à l'autre et n'est pas fiable. Comparaison tolérante aux
  majuscules et accents, stricte sur les chiffres. La colonne `livre` reçoit le titre de la
  première version rencontrée.
- La version V5 est marquée « en vente » (indication du propriétaire du projet).

    python pipeline/import_catalogue.py
"""
import csv
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
from enrich_bnf import norm

RAW = editions.ROOT / "data" / "raw" / "collection-ldvelh"
RAPPORT = editions.ROOT / "data" / "processed" / "rapport_liens_versions.csv"
ORDRE = ["V1", "V2", "V3", "V4", "V5"]
SEUIL = 0.85
EN_VENTE = {"V5": "1"}


def similitude(a, b):
    na, nb = norm(a), norm(b)
    if re.findall(r"\d+", na) != re.findall(r"\d+", nb):
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def main():
    fichier = sorted(RAW.glob("books_data-*.csv"))[-1]
    with open(fichier, newline="", encoding="utf-8") as f:
        brut = list(csv.DictReader(f))
    if not brut or "version" not in brut[0]:
        sys.exit("Le relevé ne contient pas de colonne « version » : relancez scrapers/collection_ldvelh.py")

    base = editions.load()
    par_id = {r["id"]: r for r in base}
    livres = {}  # série -> [[nom du livre, titre]]
    rapport, ajoutes, completes = [], 0, 0
    brut.sort(key=lambda r: ORDRE.index(r["version"]))
    for r in brut:
        serie = (r.get("serie") or "").strip()
        numero = (r.get("numero") or "").strip()
        try:
            ident = editions.normalize_isbn(r.get("isbn") or "")[0]
            isbn13, isbn10 = editions.normalize_isbn(r["isbn"])
        except ValueError:
            ident, isbn13, isbn10 = f"LOCAL-{serie}-{numero}".replace(" ", "_"), "", ""

        # Lien avec le livre : même série, titre proche
        candidats = livres.setdefault(serie, [])
        scores = sorted(((similitude(r["titre"], c[1]), c) for c in candidats), key=lambda x: -x[0])
        if scores and scores[0][0] >= SEUIL:
            nom_livre = scores[0][1][0]
            if scores[0][0] < 0.95:
                rapport.append([r["version"], serie, r["titre"], nom_livre, f"{scores[0][0]:.2f}"])
        else:
            nom_livre = r["titre"]
            candidats.append([nom_livre, r["titre"]])

        if ident in par_id:
            ligne = par_id[ident]
            if not ligne.get("version"):
                ligne["version"] = r["version"]
            if not ligne.get("livre"):
                ligne["livre"] = nom_livre
            if not ligne.get("en_vente") and r["version"] in EN_VENTE:
                ligne["en_vente"] = EN_VENTE[r["version"]]
            completes += 1
            continue
        ligne = {"id": ident, "isbn13": isbn13, "isbn10": isbn10, "livre": nom_livre,
                 "titre": r["titre"], "version": r["version"], "en_vente": EN_VENTE.get(r["version"], ""),
                 "serie": serie, "numero": numero, "annee": (r.get("date") or "")[:4],
                 "statut": "brut", "source": "collection-ldvelh", "date_maj": editions.today()}
        base.append(ligne)
        par_id[ident] = ligne
        ajoutes += 1

    editions.save(base)
    with open(RAPPORT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["version", "serie", "titre_version", "livre_rattache", "similitude"])
        w.writerows(rapport)
    nb_livres = len({r["livre"] for r in base if r.get("livre")})
    print(f"{ajoutes} édition(s) ajoutée(s), {completes} déjà présente(s) complétée(s)")
    print(f"{len(base)} éditions au total, {nb_livres} livres distincts")
    print(f"{len(rapport)} rapprochement(s) moins sûr(s) listé(s) dans {RAPPORT}")


if __name__ == "__main__":
    main()
