"""Prix validés par le propriétaire (boutons « Confirmer » / « Corriger » de la page « Vérifier les prix »).

Un prix validé prime sur tout le reste (archives, annonces eBay, règle 40/60, correctifs de cohérence) : il est affiché
tel quel jusqu'à ce que le propriétaire le change. Le fichier `data/manual/prix_valides.json` a la forme
  {"valides": {"<isbn13>|<etat>": {"prix": 27.5, "decision": "confirme" | "corrige", "le": "2026-10-14"}}}
La page produit un fichier de même forme (« Envoyer mes validations ») ; `importer` le fusionne dans le fichier du dépôt.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ETATS = ("convenable", "bon", "tres_bon")
DECISIONS = ("confirme", "corrige")
CHEMIN = Path(__file__).resolve().parent.parent / "data" / "manual" / "prix_valides.json"


def _propre(cle, v):
    """Renvoie l'entrée nettoyée, ou None si elle est invalide."""
    try:
        isbn, etat = str(cle).split("|")
        prix = round(float(v["prix"]), 2)
        jour = date.fromisoformat(str(v["le"]))
    except (ValueError, KeyError, TypeError):
        return None
    if not re.fullmatch(r"\d{13}", isbn) or etat not in ETATS or not 0 < prix < 10000 or v.get("decision") not in DECISIONS:
        return None
    return {"prix": prix, "decision": v["decision"], "le": jour.isoformat()}


def lire(chemin=CHEMIN):
    """{(isbn13, etat): {prix, decision, le}} ; fichier absent ou illisible : aucune validation."""
    try:
        brut = json.loads(Path(chemin).read_text(encoding="utf-8")).get("valides", {})
    except (OSError, ValueError, AttributeError):
        return {}
    out = {}
    for cle, v in brut.items():
        net = _propre(cle, v)
        if net:
            out[tuple(cle.split("|"))] = net
    return out


def importer(source, chemin=CHEMIN):
    """Fusionne un fichier de validations dans `chemin` (la plus récente l'emporte). Renvoie (ajoutées, refusées)."""
    envoi = json.loads(Path(source).read_text(encoding="utf-8")).get("valides", {})
    actuel = {"|".join(k): v for k, v in lire(chemin).items()}
    ajoutees = refusees = 0
    for cle, v in envoi.items():
        net = _propre(cle, v)
        if not net:
            refusees += 1
            continue
        if cle not in actuel or net["le"] >= actuel[cle]["le"]:
            actuel[cle] = net
            ajoutees += 1
    Path(chemin).parent.mkdir(parents=True, exist_ok=True)
    Path(chemin).write_text(json.dumps({"valides": dict(sorted(actuel.items()))}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return ajoutees, refusees


def appliquer(par_etat, isbn, valides):
    """Remplace dans `par_etat` ({etat: estimation}) les prix validés ; garde le prix calculé dans « calcule ». Renvoie le nombre."""
    n = 0
    for e in ETATS:
        v = valides.get((isbn, e))
        if v:
            avant = (par_etat.get(e) or {}).get("prix")
            par_etat[e] = {"prix": v["prix"], "source": "validé", "nature": "validé", "nb": 0, "date": v["le"],
                           "confiance": "validée", "valide": True, "decision": v["decision"], "calcule": avant}
            n += 1
    return n


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage : python pipeline/validations.py <fichier-de-validations.json>")
    a, r = importer(sys.argv[1])
    print(f"{a} validation(s) enregistrée(s), {r} refusée(s) ; fichier : {CHEMIN}")
