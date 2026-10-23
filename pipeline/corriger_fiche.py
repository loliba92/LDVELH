"""Corrections de fiches saisies sur le site (formulaire « Corriger la fiche » de la fiche d'un livre, réservé aux administrateurs).

Une correction par ligne, ou plusieurs séparées par « | » (les champs d'un lancement GitHub tiennent sur une ligne) :
    identifiant ; titre ; Nouveau titre      renomme le livre : toutes ses éditions prennent ce titre
    identifiant ; serie ; Nouvelle série     change la série de toutes les éditions du livre (une série nouvelle est créée par ce geste)
    identifiant ; numero ; 12                change le numéro de cette édition
    identifiant ; supprimer                  retire cette édition de la base, avec sa jaquette et ses prix validés
L'identifiant est celui de la fiche (l'ISBN-13, ou « LOCAL-… » pour un livre sans ISBN).
Usage : python pipeline/corriger_fiche.py "9782075237246 ; serie ; Défis Fantastiques"
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
import validations

CHAMPS = ("titre", "serie", "numero", "supprimer")
LONGUEUR_MAX = 120


def _propre(t):
    return re.sub(r"\s+", " ", re.sub(r"[​-‏‪-‮⁠﻿]", "", str(t))).strip()


def lire(texte):
    """[{id, champ, valeur}] ; une entrée par ligne non vide."""
    out = []
    for ligne in re.split(r"[\r\n|]+", texte):
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#"):
            continue
        p = [_propre(x) for x in ligne.split(";", 2)] + ["", ""]
        out.append({"id": p[0], "champ": p[1].lower().replace("é", "e").replace("ç", "c"), "valeur": p[2]})
    return out


def _supprimer_jaquettes(row):
    for taille in ("small", "medium", "large"):
        f = editions.ROOT / "web" / "covers" / taille / f"{editions.cle_image(row['id'], row.get('isbn13', ''))}.webp"
        if f.exists():
            f.unlink()


def _retirer_prix(ident, chemin):
    if not Path(chemin).exists():
        return
    d = json.loads(Path(chemin).read_text(encoding="utf-8"))
    v = d.get("valides", {})
    for k in [k for k in v if k.split("|")[0] == ident]:
        del v[k]
    Path(chemin).write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def appliquer(texte, base=None, chemin_prix=validations.CHEMIN, jaquettes=True, role="superadmin"):
    """Applique les corrections. Renvoie [(statut, identifiant, texte)] ; statut : ok | refuse. La suppression d'une édition est réservée au Zagor."""
    rows = editions.load(base)
    bilan = []
    for e in lire(texte):
        r = next((x for x in rows if x["id"] == e["id"]), None)
        if r is None:
            bilan.append(("refuse", e["id"], "fiche absente de la base"))
            continue
        nom = f"{r['titre']} ({r['version']})"
        if e["champ"] not in CHAMPS:
            bilan.append(("refuse", e["id"], f"champ inconnu : {e['champ']}"))
        elif e["champ"] == "supprimer" and role != "superadmin":
            bilan.append(("refuse", e["id"], "la suppression d'une édition est réservée au Zagor"))
        elif e["champ"] == "supprimer":
            rows = [x for x in rows if x["id"] != r["id"]]
            if jaquettes:
                _supprimer_jaquettes(r)
            _retirer_prix(r["id"], chemin_prix)
            bilan.append(("ok", e["id"], f"{nom} : fiche supprimée"))
        elif not e["valeur"] or len(e["valeur"]) > LONGUEUR_MAX:
            bilan.append(("refuse", e["id"], "valeur vide ou trop longue"))
        elif e["champ"] == "numero":
            if not re.fullmatch(r"\d{1,4}", e["valeur"]):
                bilan.append(("refuse", e["id"], "le numéro doit être un nombre"))
                continue
            r["numero"] = e["valeur"]
            r["date_maj"] = editions.today()
            bilan.append(("ok", e["id"], f"{nom} : numéro {e['valeur']}"))
        else:
            cle = r.get("livre") or r["titre"]
            for x in rows:
                if (x.get("livre") or x["titre"]) == cle:
                    if e["champ"] == "titre":
                        x["titre"] = x["livre"] = e["valeur"]
                    else:
                        x["serie"] = e["valeur"]
                    x["date_maj"] = editions.today()
            bilan.append(("ok", e["id"], f"{nom} : {'titre' if e['champ'] == 'titre' else 'série'} « {e['valeur']} »"))
    if any(s == "ok" for s, _, _ in bilan):
        editions.save(rows, base)
    return bilan


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    bilan = appliquer(" | ".join(sys.argv[1:]), role=os.environ.get("ROLE_AUTEUR", ""))      # rôle vérifié par identite.py ; absent : pas de suppression
    for s, ident, t in bilan:
        print(f"{'+' if s == 'ok' else '✗'} {ident}  {t}")
    ok = sum(1 for s, _, _ in bilan if s == "ok")
    print(f"{ok} correction(s) appliquée(s) sur {len(bilan)} ligne(s).")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
