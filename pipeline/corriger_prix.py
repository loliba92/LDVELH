"""Corrections de cotes saisies sur le site (formulaire « Corriger les cotes » de la fiche, réservé au propriétaire).

Une correction par ligne, ou plusieurs séparées par « | » (les champs d'un lancement GitHub tiennent sur une ligne) :
    ISBN ; convenable ; bon état ; très bon état [; confirme]
Le mot « confirme » en dernier champ marque ces prix comme confirmés (et non corrigés). Une case vide ne change pas cet état. Les prix acceptent la virgule. Exemple :
    9782070585168 ; 25 ; ; 60
Chaque prix saisi devient un prix validé (data/manual/prix_valides.json) : il prime sur eBay, les archives et la règle 40/60 ;
les états non saisis en sont déduits (voir pipeline/export_site.py).
Usage : python pipeline/corriger_prix.py "9782070585168 ; 25 ; ; 60"
"""
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
import validations

ORDRE = ("convenable", "bon", "tres_bon")


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


def appliquer(texte, chemin=validations.CHEMIN, base=None):
    """Enregistre les corrections. Renvoie [(statut, isbn, texte)] ; statut : ok | refuse."""
    connus = {r["isbn13"]: r for r in editions.load(base) if r.get("isbn13")}
    jour = editions.today()
    bilan, envoi = [], {}
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
        for etat, p in e["prix"].items():
            envoi[f"{isbn}|{etat}"] = {"prix": p, "decision": e["decision"], "le": jour}
        detail = " · ".join(f"{k.replace('tres_bon', 'très bon état').replace('bon', 'bon état') if k != 'convenable' else 'convenable'} {p:g} €" for k, p in e["prix"].items())
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
    bilan = appliquer(" | ".join(sys.argv[1:]))
    for s, isbn, t in bilan:
        print(f"{'+' if s == 'ok' else '✗'} {isbn}  {t}")
    ok = sum(1 for s, _, _ in bilan if s == "ok")
    print(f"{ok} correction(s) enregistrée(s) sur {len(bilan)} ligne(s).")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
