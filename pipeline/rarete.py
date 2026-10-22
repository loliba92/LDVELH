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
import difflib
import re
import unicodedata
from pathlib import Path

TIRAGES = Path(__file__).resolve().parent.parent / "data" / "manual" / "tirages_gallimard.txt"

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


def _n(texte):
    t = unicodedata.normalize("NFD", str(texte or "").lower().replace("œ", "oe"))
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in t if not unicodedata.combining(c)))


def charger_tirages(chemin=TIRAGES):
    """Nombre de tirages (impressions et réimpressions) de chaque livre par édition Gallimard, compilé par Thomtom d'après exlibris.to
    (data/manual/tirages_gallimard.txt). Renvoie {série normalisée : [(titre normalisé, {colonne : tirages})]} ; vide si le fichier manque.
    Colonnes : V0 V1 V2 V3 V4 V4GF (grand format) V5 V5C (collector)."""
    sortie = {}
    try:
        lignes = Path(chemin).read_text(encoding="utf-8").splitlines()
    except OSError:
        return sortie
    cols = ("V0", "V1", "V2", "V3", "V4", "V4GF", "V5", "V5C")
    for l in lignes:
        if not l.strip() or l.startswith("#"):
            continue
        morceaux = l.split("|")
        try:
            valeurs = [int(x) for x in morceaux[4:12]]
        except ValueError:
            continue
        if len(morceaux) < 12:
            continue
        sortie.setdefault(_n(morceaux[0]), []).append((_n(morceaux[3]), dict(zip(cols, valeurs))))
    return sortie


def tirages_de(v, tirages):
    """Tirages de l'édition `v` (une entrée de versions.json), ou None : même série, titre très proche (0,85), colonne de la bonne version."""
    candidats = tirages.get(_n(v.get("serie")))
    if not candidats:
        return None
    titre = _n(re.sub(r"\([^)]*\)", "", v.get("livre") or v.get("titre") or ""))
    score, valeurs = max(((difflib.SequenceMatcher(None, titre, t).ratio(), d) for t, d in candidats), key=lambda z: z[0])
    if score < 0.85:
        return None
    version, brut = v.get("version"), _n(v.get("titre"))
    if version == "V4":
        col = "V4GF" if "grandformat" in brut else "V4"
    elif version == "V5":
        col = "V5C" if "collector" in brut else "V5"
    else:
        col = version
    n = valeurs.get(col)
    return n if n else None                                  # 0 : cette édition n'a pas été tirée par Gallimard


def niveau(valeur, triees):
    """Niveau d'un pourcentage parmi la liste triée croissante des pourcentages de sa version. Les égalités prennent le niveau le plus courant."""
    n = len(triees)
    rang_haut = sum(1 for x in triees if x <= valeur)          # nombre d'éditions au plus aussi rares
    part = rang_haut / n
    for nom, borne in NIVEAUX:
        if part <= borne:
            return nom
    return "courant"


def annoter(versions, pct, tirages=None):
    """Ajoute à chaque édition {"rarete": {"niveau": "rare", "tirages": 3, "pct": 26}} : le niveau vient du nombre de tirages Gallimard quand il est
    connu (moins une édition a été tirée, plus elle est rare), sinon du pourcentage de collections de collection-ldvelh.fr. Le niveau se calcule
    version par version (un V1 se compare aux V1). Renvoie le nombre d'éditions annotées."""
    tirages = tirages or {}
    nb_tirages = {id(v): tirages_de(v, tirages) for v in versions} if tirages else {}
    par_t, par_p = {}, {}
    for v in versions:
        if nb_tirages.get(id(v)) is not None:
            par_t.setdefault(v["version"], []).append(nb_tirages[id(v)])
        if v.get("isbn13") in pct:
            par_p.setdefault(v["version"], []).append(pct[v["isbn13"]])
    n = 0
    for v in versions:
        t, p = nb_tirages.get(id(v)), pct.get(v.get("isbn13"))
        if t is not None and len(par_t[v["version"]]) >= 10:
            r = {"niveau": niveau(t, sorted(par_t[v["version"]])), "tirages": t}
        elif p is not None and len(par_p.get(v["version"], [])) >= 10:      # trop peu d'éditions pour comparer : pas de niveau
            r = {"niveau": niveau(p, sorted(par_p[v["version"]]))}
        else:
            continue
        if p is not None:
            r["pct"] = round(p)
        v["rarete"] = r
        n += 1
    return n
