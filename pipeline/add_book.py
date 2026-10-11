"""Ajoute un ou plusieurs livres à la base à partir de leur ISBN.

Exemples :
    python pipeline/add_book.py 9782070583805
    python pipeline/add_book.py 2070583805 --serie "Destins" --numero 731
    python pipeline/add_book.py --file isbn.txt          (un ISBN par ligne)

Les tirets et espaces dans l'ISBN sont acceptés. La fiche est complétée
automatiquement par le catalogue de la BnF. Si le livre est introuvable,
il est tout de même ajouté (statut « brut ») avec ce que vous indiquez.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("isbn", nargs="*", help="un ou plusieurs ISBN (10 ou 13 chiffres)")
    p.add_argument("--file", help="fichier texte contenant un ISBN par ligne")
    p.add_argument("--serie", default="", help="série du livre-jeu (ex. Défis Fantastiques)")
    p.add_argument("--numero", default="", help="numéro dans la série")
    p.add_argument("--livre", default="", help="nom du livre commun à toutes ses versions (ex. Down Among the Dead Men)")
    p.add_argument("--version", default="", help="libellé de version (V1, V2... V5) ; sinon calculé par ordre d'année")
    p.add_argument("--en-vente", default="", choices=["", "0", "1"], help="1 si cette version est encore vendue neuve")
    p.add_argument("--titre", default="", help="titre, utile si la BnF ne trouve pas le livre")
    p.add_argument("--base", default=str(editions.BASE), help="fichier de la base (par défaut : la vraie)")
    a = p.parse_args()

    isbns = list(a.isbn)
    if a.file:
        isbns += [l.strip() for l in Path(a.file).read_text(encoding="utf-8").splitlines()
                  if l.strip() and not l.startswith("#")]
    if not isbns:
        p.error("indiquez au moins un ISBN")
    if len(isbns) > 1 and (a.serie or a.numero or a.titre or a.livre or a.version or a.en_vente):
        p.error("--serie, --numero, --titre, --livre, --version et --en-vente ne s'utilisent qu'avec un seul ISBN")

    rows = editions.load(a.base)
    known = {r["id"] for r in rows}
    ajoutes = 0
    for raw in isbns:
        try:
            isbn13, isbn10 = editions.normalize_isbn(raw)
        except ValueError as e:
            print(f"✗ {e}")
            continue
        if isbn13 in known:
            print(f"= {isbn13} est déjà dans la base, rien à faire")
            continue
        fiche = None
        try:
            fiche = editions.lookup_bnf(isbn13, isbn10)
        except Exception as e:  # réseau, BnF indisponible
            print(f"! BnF injoignable pour {isbn13} ({e}) : ajout sans enrichissement")
        row = {"id": isbn13, "isbn13": isbn13, "isbn10": isbn10, "serie": a.serie,
               "numero": a.numero, "titre": a.titre,
               "livre": a.livre, "version": a.version, "en_vente": a.en_vente, "source": "manuel",
               "statut": "brut", "date_maj": editions.today()}
        if fiche:
            row.update({k: v for k, v in fiche.items() if v and not (k == "titre" and a.titre)})
            row["statut"] = "enrichi"
            row["source"] = "bnf"
        rows.append(row)
        known.add(isbn13)
        ajoutes += 1
        manque = [n for n in ("titre", "serie", "numero") if not row.get(n)]
        print(f"+ {isbn13}  {row.get('titre') or '(titre inconnu)'}  [{row['statut']}]"
              + (f"  à compléter : {', '.join(manque)}" if manque else ""))
        if not row["serie"]:
            print("  ⚠ Série non indiquée : vérifiez que c'est bien un livre-jeu "
                  "(la BnF renvoie n'importe quel livre).")
    if ajoutes:
        editions.save(rows, a.base)
    print(f"{ajoutes} livre(s) ajouté(s), {len(rows)} dans la base.")


if __name__ == "__main__":
    main()
