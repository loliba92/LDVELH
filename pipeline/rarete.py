"""Rareté d'une édition, d'après les collections saisies par les inscrits de collection-ldvelh.fr.

Ce site classe ses livres « les plus rares » par le nombre de collections qui les possèdent (le tirage réel n'est pas public).
Le relevé du catalogue (scrapers/collection_ldvelh.py) garde, pour chaque ISBN, le pourcentage de collections qui le contiennent
(colonne collection_percentage). Plus il est bas, plus le livre est rare.

Mesure faite le 19 octobre 2026 sur 425 éditions : pour les éditions d'origine (V1), le pourcentage explique une bonne part du prix
du très bon état (corrélation de rang -0,64 ; erreur médiane d'un prix estimé d'après la série seule : 37 %, avec la rareté : 21 %).
Pour les rééditions (V2 à V5) le lien est faible : la rareté est donc affichée comme une information, elle ne modifie aucune cote.

Niveaux, calculés version par version (un V1 se compare aux V1) : très rare (10 % des éditions les moins possédées), rare (jusqu'à 30 %),
peu courant (jusqu'à 60 %), courant.
"""
import csv
from pathlib import Path

NIVEAUX = (("tres_rare", 0.10), ("rare", 0.30), ("peu_courant", 0.60))      # part cumulée des éditions de la version, des moins possédées aux plus possédées


def charger(dossier):
    """{isbn13: pourcentage} d'après le dernier fichier books_data-*.csv du dossier (vide s'il n'y en a pas)."""
    fichiers = sorted(Path(dossier).glob("books_data-*.csv"))
    if not fichiers:
        return {}
    pct = {}
    with open(fichiers[-1], newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                pct[r["isbn"].strip()] = float(str(r["collection_percentage"]).strip())
            except (KeyError, ValueError):
                continue
    return pct


def niveau(valeur, triees):
    """Niveau d'un pourcentage parmi la liste triée croissante des pourcentages de sa version. Les égalités prennent le niveau le plus courant."""
    n = len(triees)
    rang_haut = sum(1 for x in triees if x <= valeur)          # nombre d'éditions au plus aussi rares
    part = rang_haut / n
    for nom, borne in NIVEAUX:
        if part <= borne:
            return nom
    return "courant"


def annoter(versions, pct):
    """Ajoute à chaque édition {"rarete": {"pct": 26, "niveau": "rare"}} quand son pourcentage est connu. Renvoie le nombre d'éditions annotées."""
    par_version = {}
    for v in versions:
        if v.get("isbn13") in pct:
            par_version.setdefault(v["version"], []).append(pct[v["isbn13"]])
    n = 0
    for v in versions:
        p = pct.get(v.get("isbn13"))
        if p is None:
            continue
        triees = sorted(par_version[v["version"]])
        if len(triees) < 10:                                  # trop peu d'éditions pour comparer : pas de niveau
            continue
        v["rarete"] = {"pct": round(p), "niveau": niveau(p, triees)}
        n += 1
    return n
