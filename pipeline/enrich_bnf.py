"""Complète les fiches de editions.csv avec le catalogue de la BnF (reprise possible).

Pour chaque édition au statut « brut » ayant un ISBN :
  - interroge la BnF ;
  - compare le titre trouvé au titre attendu ; si trop différent, le livre est marqué
    « a_verifier » et RIEN n'est recopié (la BnF renvoie parfois un autre livre) ;
  - sinon complète uniquement les champs vides (auteurs, traducteur, illustrateur,
    éditeur, collection, pages, notice) et passe le statut à « enrichi ».
Un rapport des écarts est écrit dans data/processed/rapport_enrichissement.csv.

    python pipeline/enrich_bnf.py
    python pipeline/enrich_bnf.py --revalider   # recontrôle l'ISBN des fiches déjà enrichies
"""
import argparse
import csv
import difflib
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions

RAPPORT = editions.ROOT / "data" / "processed" / "rapport_enrichissement.csv"
SEUIL_TITRE = 0.55
CHAMPS = ["auteurs", "traducteur", "illustrateur", "editeur", "collection_editeur", "pages", "notice_bnf"]


def norm(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\b(le|la|les|l|un|une|de|du|des|d|et|a)\b", " ", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def similitude(a, b):
    a, b = norm(a), norm(b)
    if len(a) >= 8 and (a in b or b in a):  # ex. volume qui réunit deux récits
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def propre_collection(c):
    """« Collection Folio junior » -> « Folio junior »."""
    c = re.sub(r"^Collection\s+", "", c.strip())
    return c[:1].upper() + c[1:]


def isbn_incoherent(r, fiche):
    """Vrai si la notice annonce des ISBN et que celui de la fiche n'en fait pas partie."""
    return bool(r["isbn13"] and fiche.get("isbns") and r["isbn13"] not in fiche["isbns"])


def vide(r):
    for c in CHAMPS:
        r[c] = ""
    r["statut"] = "brut"
    r["source"] = "collection-ldvelh"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--revalider", action="store_true",
                    help="recontrôle les fiches enrichies dont l'année BnF s'écarte de plus de 2 ans")
    args = ap.parse_args()
    rows = editions.load()
    if args.revalider:
        a_faire = [r for r in rows if r["statut"] == "enrichi" and r["isbn13"] and r["annee"].isdigit()
                   and r["annee_bnf"].isdigit() and abs(int(r["annee"]) - int(r["annee_bnf"])) > 2]
    else:
        a_faire = [r for r in rows if (r["isbn13"] or r["statut"] == "brut") and (
            r["statut"] in ("brut", "a_verifier") or (r["statut"] == "enrichi" and not r.get("annee_bnf")))]
    print(f"{len(a_faire)} édition(s) à enrichir sur {len(rows)}")
    rapport, nb = [], {"enrichi": 0, "a_verifier": 0, "introuvable": 0, "erreur": 0}
    for i, r in enumerate(a_faire, start=1):
        try:
            fiche = editions.lookup_bnf(r["isbn13"], r["isbn10"], pause=1.0) if r["isbn13"] else None
        except Exception as e:
            nb["erreur"] += 1
            rapport.append([r["id"], r["titre"], "", "", "erreur", str(e)[:80]])
            continue
        confirmation = "isbn"
        if fiche is not None and isbn_incoherent(r, fiche):
            # La notice trouvée porte d'autres ISBN : c'est un autre livre ou une autre édition
            if args.revalider:
                vide(r)
            nb["a_verifier"] += 1
            rapport.append([r["id"], r["titre"], fiche["titre"], "", "isbn_different",
                            f"ISBN de la notice : {', '.join(fiche['isbns'])[:60]}"])
            fiche = None
            confirmation = "refuse"
        if fiche is None and confirmation != "refuse":  # secours : recherche par titre, avec confirmation
            try:
                fiche, confirmation = editions.lookup_bnf_titre(r["titre"], r["numero"], r["isbn13"], r.get("annee", ""))
            except Exception as e:
                fiche, confirmation = None, ""
        if fiche is None:
            if args.revalider:
                vide(r)  # ancienne fiche non confirmée par l'ISBN : on retire les données douteuses
            nb["introuvable"] += 1
            rapport.append([r["id"], r["titre"], "", "", "introuvable", ""])
            continue
        s = similitude(r["titre"], fiche["titre"])
        ecart_annee = ""
        if r.get("annee") and fiche.get("annee") and abs(int(r["annee"]) - int(fiche["annee"])) > 1:
            ecart_annee = f"année {r['annee']} vs BnF {fiche['annee']}"
        if s < SEUIL_TITRE:
            r["statut"] = "a_verifier"
            nb["a_verifier"] += 1
            rapport.append([r["id"], r["titre"], fiche["titre"], f"{s:.2f}", "a_verifier", ecart_annee])
        else:
            for c in CHAMPS:
                if not r.get(c) and fiche.get(c):
                    r[c] = propre_collection(fiche[c]) if c == "collection_editeur" else fiche[c]
            r["statut"] = "enrichi" if confirmation in ("isbn", "numero") else "a_verifier"
            if confirmation != "isbn":
                rapport.append([r["id"], r["titre"], fiche["titre"], f"{s:.2f}", r["statut"],
                                f"trouvé par le titre (confirmation : {confirmation})"])
            r["annee_bnf"] = fiche.get("annee", "")
            r["source"] = "collection-ldvelh+bnf"
            r["date_maj"] = editions.today()
            nb["enrichi" if r["statut"] == "enrichi" else "a_verifier"] += 1
            if ecart_annee:
                rapport.append([r["id"], r["titre"], fiche["titre"], f"{s:.2f}", "enrichi", ecart_annee])
        if i % 20 == 0:
            editions.save(rows)
            print(f"  {i}/{len(a_faire)} ...", flush=True)
    editions.save(rows)
    ancien = {}
    if RAPPORT.exists():
        with open(RAPPORT, newline="", encoding="utf-8") as f:
            ancien = {l[0]: l for l in list(csv.reader(f))[1:]}
    traites = {r["id"] for r in a_faire}
    ancien = {k: v for k, v in ancien.items() if k not in traites}
    ancien.update({l[0]: l for l in rapport})
    with open(RAPPORT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "titre_base", "titre_bnf", "similitude", "resultat", "remarque"])
        w.writerows(ancien.values())
    print("Résultat :", nb)
    print(f"Rapport : {RAPPORT}")


if __name__ == "__main__":
    main()
