"""Ajoute plusieurs livres à la base à partir d'une liste d'ISBN : python pipeline/importer_isbn.py liste.txt   (ou : --texte "…")

Une ligne par livre. On peut ajouter après l'ISBN, séparés par un point-virgule, la série, le numéro et le titre (tous facultatifs) :
    9791097577025 ; Fabled Lands ; 1 ; Le Royaume déchiré
    2-07-033370-1
Une ligne sans point-virgule peut aussi contenir plusieurs ISBN séparés par des espaces ou des virgules. Les tirets sont acceptés.

La fiche vient de la BnF ; à défaut (livre récent), de la fiche de leslibraires.fr (titre, année, pages, éditeur, collection).
Un ISBN déjà dans la base est ignoré. Le numéro de version (V1, V2…) suit les éditions déjà connues du même livre, par année.
Le prix du neuf et la disponibilité sont relevés ensuite par le lot hebdomadaire (pipeline/prix_neuf.py).
"""
import argparse
import html
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
from prix_neuf import AGENT, URL


def lire_liste(texte):
    """[{brut, serie, numero, titre}] : une entrée par ISBN trouvé ; les lignes vides et les # sont ignorées."""
    out = []
    for ligne in texte.splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        if ";" in ligne or "\t" in ligne:
            p = [x.strip() for x in re.split(r"[;\t]", ligne)] + ["", "", ""]
            out.append({"brut": p[0], "serie": p[1], "numero": p[2], "titre": p[3]})
        else:
            out += [{"brut": t, "serie": "", "numero": "", "titre": ""} for t in re.split(r"[,\s]+", ligne) if t]
    return out


def fiche_librairie(isbn, http=requests):
    """Fiche de leslibraires.fr : {titre, annee, pages, editeur, collection} ; None si la fiche n'existe pas."""
    r = http.get(URL.format(isbn=isbn), headers={"User-Agent": AGENT}, timeout=30, allow_redirects=True)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    h = r.text

    def g(motif):
        m = re.search(motif, h, re.S)
        return html.unescape(m.group(1)).strip() if m else ""
    titre = g(r"<title>(.*?)</title>").replace(" - Leslibraires.fr", "")
    if not titre or titre == "Leslibraires.fr":
        return None
    titre = re.sub(r"^Livre-jeu,\s*", "", titre)
    titre = re.sub(r"\s+-\s+[^-]+$", "", titre)          # « Titre - Auteur » : on garde le titre
    return {"titre": titre, "annee": g(r'itemprop="datePublished" datetime="(\d{4})'), "pages": g(r'itemprop="numberOfPages">(\d+)'),
            "editeur": g(r'<th scope="row">Éditeur</th>.*?<a[^>]*>(.*?)</a>'),
            "collection": g(r'<th scope="row">Collection</th>\s*<td>\s*<a[^>]*>(.*?)</a>').title()}


def _cle(t):
    return re.sub(r"\W+", " ", (t or "").casefold()).strip()


def numero_version(rows, livre, annee):
    """1 + nombre d'éditions déjà connues de ce livre publiées au plus tard la même année (toutes, si l'année est inconnue)."""
    memes = [r for r in rows if _cle(r.get("livre") or r.get("titre")) == _cle(livre)]
    if not annee:
        return len(memes) + 1
    return 1 + sum(1 for r in memes if not str(r.get("annee") or "").isdigit() or int(r["annee"]) <= int(annee))


def importer(texte, base=None, bnf=editions.lookup_bnf, librairie=fiche_librairie):
    """Ajoute à la base ce qui est nouveau. Renvoie [(statut, isbn, texte)] ; statut : ajoute | deja | invalide."""
    rows = editions.load(base)
    connus = {r["id"] for r in rows}
    bilan = []
    for e in lire_liste(texte):
        try:
            isbn13, isbn10 = editions.normalize_isbn(e["brut"])
        except ValueError:
            bilan.append(("invalide", e["brut"], "ISBN invalide"))
            continue
        if isbn13 in connus:
            bilan.append(("deja", isbn13, "déjà dans la base"))
            continue
        fiche = None
        try:
            fiche = bnf(isbn13, isbn10)
        except Exception:                                     # BnF injoignable : on essaie la librairie
            pass
        source = "bnf"
        if not fiche:
            try:
                fiche, source = librairie(isbn13), "leslibraires"
            except requests.RequestException:
                fiche = None
        fiche = fiche or {}
        titre = e["titre"] or fiche.get("titre") or ""
        annee = str(fiche.get("annee") or "")
        row = {c: "" for c in editions.COLUMNS}
        row.update({k: v for k, v in fiche.items() if k in row and v})
        n = numero_version(rows, titre, annee) if titre else 1
        row.update({"id": isbn13, "isbn13": isbn13, "isbn10": isbn10, "serie": e["serie"] or row["serie"], "numero": e["numero"] or row["numero"],
                    "titre": titre, "livre": titre, "version": f"V{n}", "annee": annee,
                    "collection_editeur": row["collection_editeur"] or fiche.get("collection", ""),
                    "statut": "enrichi" if fiche else "brut", "source": source if fiche else "manuel", "date_maj": editions.today()})
        rows.append(row)
        connus.add(isbn13)
        manque = [n_ for n_ in ("titre", "serie", "numero") if not row[n_]]
        bilan.append(("ajoute", isbn13, f"{titre or '(titre inconnu)'} · {row['version']}" + (f" · à compléter : {', '.join(manque)}" if manque else "")))
    if any(s == "ajoute" for s, _, _ in bilan):
        editions.save(rows, base)
    return bilan


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fichier", nargs="?", help="fichier texte : une ligne par livre")
    ap.add_argument("--texte", help="la liste directement, lignes séparées par \\n")
    ap.add_argument("--base", default=str(editions.BASE))
    a = ap.parse_args()
    texte = a.texte.replace("\\n", "\n") if a.texte else Path(a.fichier).read_text(encoding="utf-8") if a.fichier else ""
    if not texte.strip():
        ap.error("indiquez un fichier ou --texte")
    bilan = importer(texte, a.base)
    icone = {"ajoute": "+", "deja": "=", "invalide": "✗"}
    for s, isbn, t in bilan:
        print(f"{icone[s]} {isbn}  {t}")
    n = sum(1 for s, _, _ in bilan if s == "ajoute")
    print(f"{n} livre(s) ajouté(s) sur {len(bilan)} ISBN lus.")


if __name__ == "__main__":
    main()
