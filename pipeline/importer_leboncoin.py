"""Importe un relevé Leboncoin envoyé par le bot personnel (« boîte aux lettres » : une issue GitHub).

Le bot (hors de ce dépôt, sur l'ordinateur du propriétaire) ouvre chaque soir une issue intitulée « Relevé Leboncoin AAAA-MM-JJ » dont le texte contient
un bloc ```csv``` : une ligne par annonce reconnue avec certitude (édition unique, état indiqué, pas de lot).

    isbn13,etat,prix,titre,lien,statut,age_jours,date

Ce script contrôle chaque ligne, puis écrit, dans data/raw/occasion/ :
  - annonces-leboncoin-AAAA-MM-JJ.csv  : annonces actives avec titre et lien (même format que annonces-*.csv d'eBay) -> onglet Butin ;
  - vendus-leboncoin-AAAA-MM-JJ.csv    : annonces vendues, gardées pour contrôle (jamais dans le Butin) ;
  - leboncoin-AAAA-MM-JJ.csv           : agrégat des actives (nb, min, médiane, max par livre et état) -> cote, comme eBay ;
  - leboncoin-vendus-AAAA-MM-JJ.csv    : agrégat des vendues -> cote, comme « vente probable ».
Rien n'est lu comme une instruction : seules des valeurs contrôlées sont écrites. Rejouer le même relevé donne le même résultat.

Usage : CORPS="$texte" python pipeline/importer_leboncoin.py [--aujourdhui AAAA-MM-JJ]
"""
import argparse
import csv
import io
import json
import os
import re
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions

DOSSIER = editions.ROOT / "data" / "raw" / "occasion"
LOTS = editions.ROOT / "data" / "manual" / "lots_annonces.json"
ETATS = ("convenable", "bon", "tres_bon")
STATUTS = ("actif", "vendu")
MAX_LIGNES = 300
PRIX_MIN, PRIX_MAX = 0.5, 3000.0
FENETRE_AVANT, FENETRE_APRES = 3, 1          # jours : une ligne trop ancienne ou datée du futur est refusée
LIEN = re.compile(r"^https://www\.leboncoin\.fr/[A-Za-z0-9_\-/.]+$")
LIEN_VINTED = re.compile(r"^https://www\.vinted\.fr/items/\d+(?:-[A-Za-z0-9_\-]*)?$")
SOURCES = ("leboncoin", "vinted")               # le bot envoie les deux dans le même relevé ; chaque source a ses propres fichiers


def source_du_lien(lien):
    """« leboncoin » ou « vinted » d'après le lien (seuls ces deux sites, en https) ; None sinon."""
    if LIEN.match(lien or ""):
        return "leboncoin"
    if LIEN_VINTED.match(lien or ""):
        return "vinted"
    return None


def nom_fichier(genre, source, jour):
    """annonces-/vendus-<source>-JOUR.csv (annonces) ; <source>-JOUR.csv et <source>-vendus-JOUR.csv (agrégats pour la cote)."""
    return {"annonces": f"annonces-{source}-{jour}.csv", "vendus": f"vendus-{source}-{jour}.csv",
            "agregat": f"{source}-{jour}.csv", "agregat_vendus": f"{source}-vendus-{jour}.csv"}[genre]
COLONNES_ANNONCES = ["isbn13", "etat", "prix", "titre", "lien", "age_jours", "trouvee_par"]
COLONNES_AGREGAT = ["isbn13", "date", "etat", "nb_annonces", "prix_min", "prix_median", "prix_max"]


def extraire_csv(corps):
    """Le bloc ```csv ... ``` du texte de l'issue (à défaut, le texte entier)."""
    m = re.search(r"```(?:csv)?\s*\n(.*?)```", corps or "", re.S)
    return (m.group(1) if m else corps or "").strip()


def nettoyer_titre(texte):
    t = re.sub(r"[\x00-\x1f\x7f<>]", " ", str(texte or ""))
    return re.sub(r"\s+", " ", t).strip()[:200]


def valider(r, aujourdhui, connues):
    """Renvoie (ligne contrôlée, None) ou (None, raison)."""
    try:
        isbn = editions.normalize_isbn(r.get("isbn13", ""))[0]
    except ValueError:
        return None, "ISBN invalide"
    if isbn not in connues:
        return None, "édition inconnue"
    etat = (r.get("etat") or "").strip()
    if etat not in ETATS:
        return None, f"état inconnu ({etat or 'vide'})"
    statut = (r.get("statut") or "actif").strip()
    if statut not in STATUTS:
        return None, f"statut inconnu ({statut})"
    try:
        prix = round(float(str(r.get("prix", "")).replace(",", ".")), 2)
    except ValueError:
        return None, "prix illisible"
    if not PRIX_MIN <= prix <= PRIX_MAX:
        return None, f"prix hors limites ({prix})"
    titre = nettoyer_titre(r.get("titre"))
    if len(titre) < 3:
        return None, "titre vide"
    lien = (r.get("lien") or "").strip()
    source = source_du_lien(lien)
    if not source:
        return None, "lien non conforme"
    try:
        jour = date.fromisoformat((r.get("date") or "").strip())
    except ValueError:
        return None, "date illisible"
    if not aujourdhui - timedelta(days=FENETRE_AVANT) <= jour <= aujourdhui + timedelta(days=FENETRE_APRES):
        return None, "date hors fenêtre"
    try:
        age = max(0, min(3650, int(float(r.get("age_jours") or 0))))
    except ValueError:
        age = 0
    return {"isbn13": isbn, "etat": etat, "prix": f"{prix:.2f}", "titre": titre, "lien": lien, "age_jours": age,
            "trouvee_par": source, "statut": statut, "date": jour.isoformat()}, None


def _lire(chemin):
    if not chemin.exists():
        return {}
    with open(chemin, newline="", encoding="utf-8") as f:
        return {r["lien"]: r for r in csv.DictReader(f)}


def _ecrire(chemin, colonnes, lignes):
    if not lignes:
        chemin.unlink(missing_ok=True)
        return
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)


def charger_lots(chemin=None):
    """Annonces qui vendent plusieurs livres d'un coup : {lien: {"isbns": [...], "poids": {isbn: prix de référence}}}.
    Le fichier data/manual/lots_annonces.json est tenu à la main (le titre de l'annonce ne dit pas toujours que c'est un lot)."""
    chemin = Path(chemin or LOTS)
    if not chemin.exists():
        return {}
    brut = json.loads(chemin.read_text(encoding="utf-8"))
    return {x["lien"]: {"isbns": x["isbns"], "poids": x["poids"]} for x in brut if x.get("lien") and x.get("isbns") and x.get("poids")}


def repartir_lot(prix, lot):
    """Prix d'un lot réparti entre ses livres au prorata de leur prix de référence : [(isbn, part)]."""
    poids = [float(lot["poids"][i]) for i in lot["isbns"]]
    total = sum(poids)
    return [(i, prix * w / total) for i, w in zip(lot["isbns"], poids)]


def etaler_lots(annonces, lots):
    """Présentation des annonces de lot : chaque livre du lot reçoit une ligne « Lot de N livres », au prix de sa part.
    `annonces` : {isbn: {état: [[prix, titre, lien, origine, vue, supposé]]}} (modifié en place). Sans cela, l'annonce n'apparaîtrait
    que sous un seul des livres alors que sa part est comptée dans la cote de tous."""
    vues = [(isbn, etat, list(a)) for isbn, par in annonces.items() for etat, liste in par.items() for a in liste if a[2] in lots]
    for isbn, etat, a in vues:
        lot = lots[a[2]]
        prefixe = "Lot de %d livres · " % len(lot["isbns"])
        titre = prefixe + str(a[1]).removeprefix(prefixe)
        part_de = dict(repartir_lot(a[0], lot))
        for i in lot["isbns"]:
            liste = annonces.setdefault(i, {}).setdefault(etat, [])
            ligne = next((x for x in liste if x[2] == a[2]), None)
            if ligne is None:
                liste.append([round(part_de[i], 2), titre, a[2], a[3], a[4], a[5]])
            else:
                ligne[0], ligne[1] = round(part_de[i], 2), titre


def _agreger(lignes, jour, lots=None):
    """Une annonce de lot n'est pas le prix d'un livre : sa part de chaque livre remplace le prix entier."""
    lots = lots or {}
    groupes = {}
    for r in lignes:
        lot = lots.get(r["lien"])
        if lot:
            for isbn, part in repartir_lot(float(r["prix"]), lot):
                groupes.setdefault((isbn, r["etat"]), []).append(round(part, 2))
            continue
        groupes.setdefault((r["isbn13"], r["etat"]), []).append(float(r["prix"]))
    return [{"isbn13": i, "date": jour, "etat": e, "nb_annonces": len(p), "prix_min": f"{min(p):.2f}",
             "prix_median": f"{statistics.median(p):.2f}", "prix_max": f"{max(p):.2f}"}
            for (i, e), p in sorted(groupes.items())]


def reagreger(dossier=None, lots=None):
    """Recalcule les agrégats (leboncoin-*.csv, leboncoin-vendus-*.csv, et de même pour Vinted) à partir des annonces de chaque jour, en tenant compte des lots.
    Appelé à chaque construction de la base : un lot ajouté au fichier agit sur tous les jours déjà importés."""
    dossier = Path(dossier or DOSSIER)
    lots = charger_lots() if lots is None else lots
    for source in SOURCES:
        for fic in sorted(dossier.glob(f"annonces-{source}-20*.csv")):
            jour = fic.stem[-10:]
            _ecrire(dossier / nom_fichier("agregat", source, jour), COLONNES_AGREGAT, _agreger(_lire(fic).values(), jour, lots))
        for fic in sorted(dossier.glob(f"vendus-{source}-20*.csv")):
            jour = fic.stem[-10:]
            _ecrire(dossier / nom_fichier("agregat_vendus", source, jour), COLONNES_AGREGAT, _agreger(_lire(fic).values(), jour, lots))


def importer(corps, aujourdhui=None, dossier=None, connues=None):
    """Importe le relevé. Renvoie un compte rendu {'acceptees', 'refusees', 'jours', 'raisons'}."""
    aujourdhui = aujourdhui or date.today()
    dossier = Path(dossier or DOSSIER)
    if connues is None:
        with open(editions.BASE, newline="", encoding="utf-8") as f:
            connues = {r["isbn13"] for r in csv.DictReader(f)}
    lignes = list(csv.DictReader(io.StringIO(extraire_csv(corps))))
    bilan = {"acceptees": 0, "refusees": 0, "jours": [], "raisons": {}}
    if len(lignes) > MAX_LIGNES:
        bilan["refusees"] = len(lignes)
        bilan["raisons"]["trop de lignes"] = len(lignes)
        return bilan
    par_jour = {}
    for r in lignes:
        ok, raison = valider(r, aujourdhui, connues)
        if ok is None:
            bilan["refusees"] += 1
            bilan["raisons"][raison] = bilan["raisons"].get(raison, 0) + 1
        else:
            bilan["acceptees"] += 1
            par_jour.setdefault((ok["trouvee_par"], ok["date"]), []).append(ok)
    for (source, jour), nouvelles in sorted(par_jour.items()):
        actives = _lire(dossier / nom_fichier("annonces", source, jour))
        vendues = _lire(dossier / nom_fichier("vendus", source, jour))
        for r in nouvelles:                              # la ligne la plus récente d'une annonce l'emporte ; vendue, elle quitte les actives
            if r["statut"] == "vendu":
                actives.pop(r["lien"], None)
                vendues[r["lien"]] = r
            elif r["lien"] not in vendues:
                actives[r["lien"]] = r
        dossier.mkdir(parents=True, exist_ok=True)
        _ecrire(dossier / nom_fichier("annonces", source, jour), COLONNES_ANNONCES, list(actives.values()))
        _ecrire(dossier / nom_fichier("vendus", source, jour), COLONNES_ANNONCES, list(vendues.values()))
        lots = charger_lots()
        _ecrire(dossier / nom_fichier("agregat", source, jour), COLONNES_AGREGAT, _agreger(actives.values(), jour, lots))
        _ecrire(dossier / nom_fichier("agregat_vendus", source, jour), COLONNES_AGREGAT, _agreger(vendues.values(), jour, lots))
        if jour not in bilan["jours"]:
            bilan["jours"].append(jour)
    return bilan


def compte_rendu(b):
    if not b["acceptees"] and not b["refusees"]:
        return "Aucune ligne reconnue dans ce relevé."
    texte = f"**{b['acceptees']}** annonce(s) importée(s), **{b['refusees']}** refusée(s)."
    if b["raisons"]:
        texte += " Raisons : " + ", ".join(f"{k} ({v})" for k, v in sorted(b["raisons"].items(), key=lambda kv: -kv[1])) + "."
    if b["jours"]:
        texte += " Jours : " + ", ".join(b["jours"]) + "."
    return texte


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aujourdhui", type=date.fromisoformat, default=date.today())
    a = p.parse_args()
    bilan = importer(os.environ.get("CORPS", ""), a.aujourdhui)
    print(compte_rendu(bilan))
    return 0 if bilan["acceptees"] or not bilan["refusees"] else 1


if __name__ == "__main__":
    sys.exit(main())
