"""Corrections de cotes saisies sur le site (formulaire « Corriger les cotes » de la fiche, réservé au propriétaire).

Une correction par ligne, ou plusieurs séparées par « | » (les champs d'un lancement GitHub tiennent sur une ligne) :
    ISBN ; convenable ; bon état ; très bon état [; confirme]
Le mot « confirme » en dernier champ marque ces prix comme confirmés (et non corrigés). Une case vide ne change pas l'état correspondant (sauf le bon état d'une fourchette : voir plus bas). Les prix acceptent la virgule. Exemple :
    9782070585168 ; 25 ; ; 60
Chaque prix saisi devient un prix validé (data/manual/prix_valides.json) : il prime sur eBay, les archives et la règle 40/60 ;
les états non saisis en sont déduits (voir pipeline/export_site.py).
Exception : une fourchette (convenable ET très bon état, bon état non saisi) met toujours à jour les trois prix : le bon état est calculé
entre les deux, avec les mêmes rapports que le site, et remplace un ancien bon état validé ou issu d'annonces. Avec un seul des deux prix,
un bon état déjà validé n'est recalculé que s'il sort de l'intervalle [convenable, très bon état] après la correction.
Usage : python pipeline/corriger_prix.py "9782070585168 ; 25 ; ; 60"
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
import etats
import validations

ORDRE = ("convenable", "bon", "tres_bon")
RATIOS = Path(__file__).resolve().parent.parent / "data" / "manual" / "ratios_etats.json"


def bon_recalcule(prix, valides, isbn, ratios):
    """Nouveau bon état à enregistrer quand un bon état déjà validé contredit la ligne, sinon None.
    prix : prix saisis dans la ligne ; valides : validations existantes ({(isbn, etat): {prix, ...}})."""
    ancien = valides.get((isbn, "bon"))
    fourchette = bool(prix.get("convenable") and prix.get("tres_bon"))
    if "bon" in prix or not (ancien or fourchette):
        return None
    connu = lambda etat: prix.get(etat) or (valides.get((isbn, etat)) or {}).get("prix")
    c, t = connu("convenable"), connu("tres_bon")
    if c is None and t is None:
        return None
    c = c if c is not None else t * ratios["convenable"] / ratios["tres_bon"]
    t = t if t is not None else c * ratios["tres_bon"] / ratios["convenable"]
    if c > t:
        return None                                                   # prix qui se contredisent : on ne devine pas
    if not fourchette and c <= ancien["prix"] <= t:
        return None                                                   # le bon état validé reste cohérent : on n'y touche pas
    niveau = ((c / ratios["convenable"]) * (t / ratios["tres_bon"])) ** 0.5
    return round(min(t, max(c, niveau * ratios["bon"])), 2)


def lire(texte):
    """[{brut, prix: {etat: float}}] ; une entrée par ligne non vide."""
    out = []
    for ligne in re.split(r"[\r\n|]+", texte):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        champs = [c.strip() for c in ligne.split(";")] + ["", "", "", "", ""]
        prix = {}
        for etat, brut in zip(ORDRE, champs[1:4]):
            if brut:
                try:
                    prix[etat] = float(brut.replace(",", ".").replace("€", "").replace(" ", ""))
                except ValueError:
                    prix[etat] = None
        out.append({"brut": champs[0], "prix": prix, "decision": "confirme" if champs[4].lower().startswith("confirm") else "corrige"})
    return out


def appliquer(texte, chemin=validations.CHEMIN, base=None, auteur=""):
    """Enregistre les corrections. Renvoie [(statut, isbn, texte)] ; statut : ok | refuse."""
    connus = {r["isbn13"]: r for r in editions.load(base) if r.get("isbn13")}
    jour = editions.today()
    bilan, envoi = [], {}
    par = validations.nom_propre(auteur)
    valides = validations.lire(chemin)
    ratios = etats.charger_ratios(RATIOS)
    for e in lire(texte):
        try:
            isbn = editions.normalize_isbn(e["brut"])[0]
        except ValueError:
            bilan.append(("refuse", e["brut"], "ISBN invalide"))
            continue
        if isbn not in connus:
            bilan.append(("refuse", isbn, "ISBN absent de la base"))
            continue
        if not e["prix"]:
            bilan.append(("refuse", isbn, "aucun prix indiqué"))
            continue
        mauvais = [k for k, v in e["prix"].items() if v is None or not 0 < v < 10000]
        if mauvais:
            bilan.append(("refuse", isbn, f"prix incorrect ({', '.join(mauvais)})"))
            continue
        recalcule = bon_recalcule(e["prix"], valides, isbn, ratios)
        if recalcule is not None:
            e["prix"]["bon"] = recalcule
        for etat, p in e["prix"].items():
            envoi[f"{isbn}|{etat}"] = {"prix": p, "decision": e["decision"], "le": jour, **({"par": par} if par else {})}
        noms = {"convenable": "convenable", "bon": "bon état", "tres_bon": "très bon état"}
        detail = " · ".join(f"{noms[k]} {p:g} €" for k, p in e["prix"].items())
        if recalcule is not None:
            detail += " (bon état recalculé)"
        bilan.append(("ok", isbn, f"{connus[isbn]['titre']} ({connus[isbn]['version']}) : {detail}"))
    if envoi:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"valides": envoi}, f)
        validations.importer(f.name, chemin)
        Path(f.name).unlink()
    return bilan


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    bilan = appliquer(" | ".join(sys.argv[1:]), auteur=os.environ.get("AUTEUR", ""))
    for s, isbn, t in bilan:
        print(f"{'+' if s == 'ok' else '✗'} {isbn}  {t}")
    ok = sum(1 for s, _, _ in bilan if s == "ok")
    print(f"{ok} correction(s) enregistrée(s) sur {len(bilan)} ligne(s).")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
