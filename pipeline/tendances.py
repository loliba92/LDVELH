"""Tendances de la cote, pour la page d'administration : est-ce que ça monte ou que ça baisse, et où ?

Deux lectures, toutes deux calculées sur les cotes publiées :
  - « depuis l'ancien relevé » : pour chaque édition, la variation entre la cote d'archives et la cote publiée aujourd'hui
    (médiane de ses états), puis la médiane des éditions d'un même groupe (décennie, version, série, éditeur) ;
  - « dans le temps » : un indice des cotes publiées à chaque publication (base 100 à la première), avec les seules cotes présentes
    à toutes les dates.
Seules comptent les cotes qui reposent sur une observation récente : prix validés par le propriétaire et annonces
(à part, les prix de l'éditeur pour les nouveautés). Une cote d'archives inchangée ne dit rien de la tendance.
Écrit `web/data/tendances.json`. Entièrement déterministe.
"""
import math
import statistics
from collections import defaultdict

MARCHE = {"validé", "annonces"}
AVEC_EDITEUR = MARCHE | {"prix éditeur"}
PETIT = 3          # en dessous de 3 éditions, un groupe est signalé comme peu fiable
SEUIL = 0.005      # une variation inférieure à 0,5 % compte comme stable


def decennie(annee):
    if not annee:
        return "Année inconnue"
    return f"Avant 1990" if annee < 1990 else (f"{annee // 10 * 10}–{annee // 10 * 10 + 9}")


def variations(revue, natures):
    """{id_edition: variation médiane de ses états} pour les cotes observées récemment."""
    par = defaultdict(list)
    for ligne in revue:
        a, p = ligne.get("archive"), ligne.get("publie")
        if a and p and ligne.get("nature") in natures:
            par[ligne["id"]].append(p / a - 1)
    return {i: statistics.median(v) for i, v in par.items()}


def _resume(valeurs):
    return {"n": len(valeurs), "mediane": round(statistics.median(valeurs), 4),
            "hausses": sum(1 for x in valeurs if x > SEUIL), "baisses": sum(1 for x in valeurs if x < -SEUIL),
            "stables": sum(1 for x in valeurs if abs(x) <= SEUIL), "peu": len(valeurs) < PETIT}


def groupes(var, versions):
    info = {v["id"]: v for v in versions}
    dims = {"decennie": lambda v: decennie(v.get("annee")), "version": lambda v: v.get("version") or "?",
            "serie": lambda v: v.get("serie") or "?", "editeur": lambda v: v.get("editeur") or "Éditeur inconnu"}
    sortie = {}
    for nom, cle in dims.items():
        par = defaultdict(list)
        for i, x in var.items():
            if i in info:
                par[cle(info[i])].append(x)
        lignes = [{"cle": k, **_resume(v)} for k, v in par.items()]
        if nom == "decennie":
            lignes.sort(key=lambda r: 0 if r["cle"].startswith("Avant") else (9999 if r["cle"].startswith("Année") else int(r["cle"][:4])))
        elif nom == "version":
            lignes.sort(key=lambda r: r["cle"])
        else:
            lignes.sort(key=lambda r: (-r["n"], r["cle"]))
        sortie[nom] = lignes[:14]
    return sortie


def global_(var):
    if not var:
        return {"n": 0, "mediane": None, "hausses": 0, "baisses": 0, "stables": 0}
    r = _resume(list(var.values()))
    return {k: r[k] for k in ("n", "mediane", "hausses", "baisses", "stables")}


def temps(historique):
    """Indice (base 100 à la première date) des cotes présentes à toutes les dates."""
    if len(historique) < 2:
        return []
    communes = set.intersection(*(set(h["prix"]) for h in historique))
    communes = {k for k in communes if all(h["prix"][k] > 0 for h in historique)}
    if not communes:
        return []
    base = historique[0]["prix"]
    out = []
    for h in historique:
        logs = [math.log(h["prix"][k] / base[k]) for k in communes]
        out.append({"date": h["date"], "indice": round(100 * math.exp(statistics.mean(logs)), 2), "n": len(communes)})
    return out


def calculer(revue, versions, historique, date):
    marche, avec = variations(revue, MARCHE), variations(revue, AVEC_EDITEUR)
    return {"date": date, "reference": "ancien relevé",
            "global": {"marche": global_(marche), "avec_editeur": global_(avec)},
            "groupes": {"marche": groupes(marche, versions), "avec_editeur": groupes(avec, versions)},
            "temps": temps(sorted(historique, key=lambda h: h["date"]))}
