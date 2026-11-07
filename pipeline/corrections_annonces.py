"""Corrections d'annonces faites par le propriétaire (Analyse, Annonces, fiche : « Corriger l'édition »).

Une annonce est reconnue à son lien. Le fichier `data/manual/annonces_corrigees.json` a la forme
  {"annonces": {"<lien>": {"statut": "confirmee" | "reaffectee" | "exclue", "isbn13": "<édition retenue>", "le": "AAAA-MM-JJ", "par": "nom", "note": "..."}}}
- confirmee : l'édition (isbn13) est bonne, l'annonce n'est plus « à vérifier ». Pour une annonce d'édition incertaine, c'est l'édition choisie : l'annonce
  devient certaine et entre dans les annonces et la cote ;
- reaffectee : l'annonce va à une autre édition (isbn13) ; ses prix et sa place dans la cote suivent ;
- exclue : l'annonce n'est pas ce livre (autre livre, lot, hors sujet) ; elle sort des annonces et de la cote.
La correction s'applique aux relevés à chaque reconstruction (annonces, cote eBay, agrégats Leboncoin et Vinted) : elle tient pour les relevés
passés et futurs, et un nouveau relevé ne la défait pas. Elle se saisit par le lot « Corriger des cotes » (lignes « annonce ; lien ; édition ; note »).
"""
import json
import re
from datetime import date
from pathlib import Path

CHEMIN = Path(__file__).resolve().parent.parent / "data" / "manual" / "annonces_corrigees.json"
STATUTS = ("confirmee", "reaffectee", "exclue")


def _propre(lien, v):
    """Entrée nettoyée, ou None si elle est invalide."""
    if not isinstance(v, dict) or not re.fullmatch(r"https://[^\s;|]{5,300}", str(lien)):
        return None
    statut = v.get("statut")
    isbn = str(v.get("isbn13") or "")
    if statut not in STATUTS or (statut != "exclue" and not re.fullmatch(r"\d{13}", isbn)):
        return None
    try:
        jour = date.fromisoformat(str(v.get("le")))
    except (ValueError, TypeError):
        return None
    net = {"statut": statut, "le": jour.isoformat()}
    if statut != "exclue":
        net["isbn13"] = isbn
    par = re.sub(r"[\x00-\x1f|;\s]+", " ", str(v.get("par") or "")).strip()[:30]
    note = re.sub(r"[\x00-\x1f|;\s]+", " ", str(v.get("note") or "")).strip()[:120]
    if par:
        net["par"] = par
    if note:
        net["note"] = note
    return net


def lire(chemin=None):
    """{lien: correction} ; fichier absent ou illisible : aucune correction."""
    try:
        brut = json.loads(Path(chemin or CHEMIN).read_text(encoding="utf-8")).get("annonces", {})
    except (OSError, ValueError, AttributeError):
        return {}
    sortie = {}
    for lien, v in brut.items():
        net = _propre(lien, v)
        if net:
            sortie[lien] = net
    return sortie


def enregistrer(nouvelles, chemin=None):
    """Ajoute ou remplace des corrections ({lien: correction}) ; la plus récente l'emporte. Renvoie (acceptées, refusées)."""
    chemin = Path(chemin or CHEMIN)
    actuel = lire(chemin)
    ok = refus = 0
    for lien, v in nouvelles.items():
        net = _propre(lien, v)
        if net:
            actuel[lien] = net
            ok += 1
        else:
            refus += 1
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps({"annonces": dict(sorted(actuel.items()))}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return ok, refus


def corriger_ligne(ligne, corrections):
    """Ligne d'un relevé (dictionnaire avec « lien » et « isbn13 ») après correction : None si l'annonce est exclue, la même ligne sinon,
    avec l'édition changée si elle est réaffectée."""
    c = corrections.get(ligne.get("lien"))
    if not c:
        return ligne
    if c["statut"] == "exclue":
        return None
    if c["isbn13"] != ligne.get("isbn13"):
        return {**ligne, "isbn13": c["isbn13"]}
    return ligne


def promues(corrections):
    """Liens des annonces que le propriétaire a rattachées à une édition (confirmées ou réaffectées) : celles d'édition incertaine deviennent certaines."""
    return {lien for lien, c in corrections.items() if c["statut"] != "exclue"}


def corriger(lignes, corrections=None):
    """Liste des lignes d'un relevé après correction."""
    corrections = lire() if corrections is None else corrections
    if not corrections:
        return list(lignes)
    return [l for l in (corriger_ligne(x, corrections) for x in lignes) if l is not None]
