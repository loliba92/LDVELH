"""Cote v2 : une annonce = une observation, datée de ses événements, lissée dans le temps (path dépendant).

Événements, lus dans les relevés quotidiens data/raw/occasion/annonces-AAAA-MM-JJ.csv :
- apparition d'une annonce (premier jour où elle est vue) : une observation « prix demandé » ;
- changement de prix : une nouvelle observation « prix demandé » ;
- disparition (vue la veille, plus le lendemain) : une observation « vente probable » au dernier prix.
Une annonce qui reste en ligne ne pèse pas une deuxième fois, quel que soit le nombre de relevés.
Le prix du jour est le filtre de lissage de estimation.lisser, avec sa mémoire de la veille.
"""
import csv
from datetime import date, timedelta
from pathlib import Path

import estimation

DECOTE = 0.85   # décote des prix demandés (voir estimation.py)


def charger_jours(dossier):
    """{date: [lignes]} des relevés eBay quotidiens (annonces-AAAA-MM-JJ.csv)."""
    jours = {}
    for f in sorted(Path(dossier).glob("annonces-????-??-??.csv")):
        jour = date.fromisoformat(f.stem[-10:])
        with open(f, encoding="utf-8", newline="") as h:
            jours[jour] = list(csv.DictReader(h))
    return jours


def evenements(jours, isbn, etat):
    """Observations (Obs) d'une édition et d'un état, à partir des relevés. Une annonce est repérée par son lien."""
    dates = sorted(jours)
    if not dates:
        return []
    dernier = dates[-1]
    vues = {}                      # lien -> {date: prix}
    for d in dates:
        for r in jours[d]:
            if r.get("isbn13") == isbn and r.get("etat") == etat and r.get("lien"):
                vues.setdefault(r["lien"], {})[d] = float(r["prix"])
    obs = []
    for lien, par_jour in vues.items():
        jours_vus = sorted(par_jour)
        prec = None
        for d in jours_vus:
            if prec is None or par_jour[d] != prec:
                obs.append(estimation.Obs(par_jour[d], "prix_demande", d, 1))     # apparition ou changement de prix
            prec = par_jour[d]
        derniere_vue = jours_vus[-1]
        if derniere_vue < dernier:                                                # disparue : probablement vendue
            obs.append(estimation.Obs(par_jour[derniere_vue], "vente_probable", derniere_vue + timedelta(days=1), 1))
    return sorted(obs, key=lambda o: o.date)


def serie(jours, isbn, etat):
    """{date: (prix du jour, incertitude)} : le prix d'un jour ne tient compte que des événements connus ce jour-là."""
    obs = evenements(jours, isbn, etat)
    sortie = {}
    for d in sorted(jours):
        connus = [o for o in obs if o.date <= d]
        if connus:
            sortie[d] = estimation.lisser(connus, d, decote=DECOTE)
    return sortie
