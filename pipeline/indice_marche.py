"""Indice de marché par version × éditeur, pour suivi interne seulement.

Il n'entre dans aucun prix publié : il sert à voir si un groupe de livres bouge, et de combien.

Principe :
  - chaque jour, on compare le prix de chaque livre et de chaque état à la veille (en logarithme) ;
  - la variation d'un groupe est la médiane de ces variations ;
  - l'indice se chaîne d'un jour à l'autre, base 100 au premier jour où le groupe est mesuré.
Tout groupe qui a au moins une variation fait bouger son indice. Sa fiabilité dépend du nombre de livres mesurés (voir confiance()) :
un groupe de quatre livres bouge, mais on le lit avec prudence.
Le nombre d'annonces actuelles par groupe est donné à côté, pour lire une baisse de prix avec l'offre.

    python pipeline/indice_marche.py
"""
import csv
import json
import math
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
HISTO = RACINE / "data" / "processed" / "cotes-historique.json"
EDITIONS = RACINE / "data" / "processed" / "editions.csv"
ANNONCES = RACINE / "data" / "processed" / "annonces.json"
SORTIE = RACINE / "data" / "processed" / "indice-marche.json"
MIN_LIVRES = 10          # en dessous : confiance faible
MOYENNE_LIVRES = 50      # à partir de là : confiance élevée, entre les deux : moyenne


def confiance(livres):
    """Niveau de confiance d'un indice, selon le nombre de livres mesurés."""
    if livres < MIN_LIVRES:
        return "faible"
    return "moyenne" if livres < MOYENNE_LIVRES else "élevée"


def groupes(chemin=EDITIONS):
    """{isbn13: « version · éditeur »}. Une valeur absente devient « sans version » ou « éditeur inconnu »."""
    par_isbn = {}
    with open(chemin, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            isbn = (r.get("isbn13") or "").strip()
            if isbn:
                version = (r.get("version") or "").strip() or "sans version"
                editeur = (r.get("editeur") or "").strip() or "éditeur inconnu"
                par_isbn[isbn] = f"{version} · {editeur}"
    return par_isbn


def variations(avant, apres, groupe_de):
    """Variations logarithmiques des prix présents les deux jours : {groupe: [variation, ...]}."""
    par_groupe = {}
    for cle, p1 in apres.items():
        p0 = avant.get(cle)
        if not p0 or not p1 or p0 <= 0 or p1 <= 0:
            continue
        groupe = groupe_de.get(cle.split("|")[0])
        if groupe is not None:
            par_groupe.setdefault(groupe, []).append(math.log(p1 / p0))
    return par_groupe


def chainer(historique, groupe_de):
    """Indice par groupe et par jour. Renvoie {groupe: [{date, indice, livres}, ...]} ; indice None tant qu'il n'est pas mesuré."""
    niveau = {}
    sortie = {}
    for i in range(1, len(historique)):
        date = historique[i]["date"]
        var = variations(historique[i - 1]["prix"], historique[i]["prix"], groupe_de)
        for groupe, valeurs in var.items():
            niveau.setdefault(groupe, 100.0)
            niveau[groupe] *= math.exp(statistics.median(valeurs))
            sortie.setdefault(groupe, []).append({"date": date, "indice": round(niveau[groupe], 2), "livres": len(valeurs)})
    return sortie


def annonces_par_groupe(chemin_annonces, groupe_de):
    """Nombre d'annonces actuelles (toutes sources, tous états) par groupe."""
    try:
        donnees = json.loads(chemin_annonces.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    compte = {}
    for isbn, par_etat in (donnees.get("annonces") or {}).items():
        groupe = groupe_de.get(isbn)
        if groupe is not None:
            compte[groupe] = compte.get(groupe, 0) + sum(len(liste) for liste in par_etat.values())
    return compte


def main():
    historique = json.loads(HISTO.read_text(encoding="utf-8"))
    groupe_de = groupes()
    courbes = chainer(historique, groupe_de)
    annonces = annonces_par_groupe(ANNONCES, groupe_de)
    resultat = {"date": historique[-1]["date"], "groupes": {}}
    for groupe, serie in sorted(courbes.items()):
        dernier = serie[-1]
        resultat["groupes"][groupe] = {"indice": dernier["indice"], "livres": dernier["livres"], "confiance": confiance(dernier["livres"]),
                                       "annonces": annonces.get(groupe, 0), "historique": [[s["date"], s["indice"]] for s in serie]}
    SORTIE.write_text(json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Indice de marché : {len(courbes)} groupes, au {resultat['date']} -> {SORTIE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
