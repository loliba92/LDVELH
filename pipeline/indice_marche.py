"""Indice de marché par version × éditeur, pour suivi interne seulement.

Il n'entre dans aucun prix publié : il sert à voir si un groupe de livres bouge, et de combien.

Principe :
  - chaque jour, on compare le prix de chaque livre et de chaque état à la veille (en logarithme) ;
  - la variation d'un groupe est la médiane de ces variations ;
  - l'indice se chaîne d'un jour à l'autre, base 100 au premier jour où le groupe est mesuré.
Tout groupe qui a au moins une variation fait bouger son indice, quel que soit son nombre de livres.
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


# Imprints rattachés à leur maison : même éditeur, numérotation de versions propre à chaque imprint
FAMILLE = {"Gallimard Jeunesse": "Gallimard"}


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


def livres_mesures(avant, apres, groupe_de):
    """Nombre de livres distincts (un même livre dans plusieurs états ne compte qu'une fois) mesurés par groupe."""
    isbns = {}
    for cle, p1 in apres.items():
        p0 = avant.get(cle)
        if not p0 or not p1 or p0 <= 0 or p1 <= 0:
            continue
        isbn = cle.split("|")[0]
        groupe = groupe_de.get(isbn)
        if groupe is not None:
            isbns.setdefault(groupe, set()).add(isbn)
    return {groupe: len(ensemble) for groupe, ensemble in isbns.items()}


def chainer(historique, groupe_de):
    """Indice par groupe et par jour. Renvoie {groupe: [{date, indice, livres}, ...]} ; indice None tant qu'il n'est pas mesuré."""
    niveau = {}
    sortie = {}
    for i in range(1, len(historique)):
        date = historique[i]["date"]
        avant, apres = historique[i - 1]["prix"], historique[i]["prix"]
        var = variations(avant, apres, groupe_de)
        nombre = livres_mesures(avant, apres, groupe_de)
        for groupe, valeurs in var.items():
            niveau.setdefault(groupe, 100.0)
            niveau[groupe] *= math.exp(statistics.median(valeurs))
            sortie.setdefault(groupe, []).append({"date": date, "indice": round(niveau[groupe], 2), "livres": nombre[groupe]})
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


def annonces_par_isbn(chemin_annonces):
    """{isbn13: nombre d'annonces actuelles (toutes sources, tous états)}."""
    try:
        donnees = json.loads(chemin_annonces.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {isbn: sum(len(liste) for liste in par_etat.values()) for isbn, par_etat in (donnees.get("annonces") or {}).items()}


def series_depuis(chemin=RACINE / "web" / "data" / "versions.json"):
    """{isbn13: série (même champ que l'étagère), ou « sans série »}, pour la décomposition par série."""
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {v["isbn13"]: (v.get("serie") or "sans série").strip() for v in donnees if v.get("isbn13")}


def variations_par_serie(avant, apres, observes, groupe_de, serie_de):
    """Variations logarithmiques des prix observés, rangées par groupe puis par série : [(isbn, variation), ...]."""
    par = {}
    for cle, p1 in apres.items():
        p0 = avant.get(cle)
        if cle not in observes or not p0 or not p1 or p0 <= 0 or p1 <= 0:
            continue
        isbn = cle.split("|")[0]
        groupe = groupe_de.get(isbn)
        if groupe is None:
            continue
        par.setdefault(groupe, {}).setdefault(serie_de.get(isbn, "sans série"), []).append((isbn, math.log(p1 / p0)))
    return par


MAX_SERIES = 5      # séries affichées dans le détail ; les autres sont regroupées dans un bloc « Autres séries »


def cascade_de_la_periode(historique, observes, groupe_de, serie_de, annonces_de=None):
    """Pour chaque groupe : la variation moyenne depuis le début de sa mesure (en %) et la part de chaque série.
    Chaque jour, la variation moyenne du groupe se découpe par série (somme des variations logarithmiques de la série / nombre de prix du groupe).
    Les parts de tous les jours s'additionnent ; elles sont ensuite ramenées à des % qui s'additionnent exactement à la variation du groupe.
    Pour chaque série : les livres distincts, leurs annonces actuelles et le nombre de prix observés."""
    annonces_de = annonces_de or {}
    cumul, propre, debut, isbns, cles = {}, {}, {}, {}, {}
    for i in range(1, len(historique)):
        avant, apres = historique[i - 1]["prix"], historique[i]["prix"]
        par = variations_par_serie(avant, apres, observes, groupe_de, serie_de)
        for groupe, series in par.items():
            n = sum(len(v) for v in series.values())
            debut.setdefault(groupe, historique[i - 1]["date"])
            for nom, v in series.items():
                cumul.setdefault(groupe, {}).setdefault(nom, 0.0)
                cumul[groupe][nom] += sum(x for _, x in v) / n
                propre.setdefault((groupe, nom), []).append((sum(x for _, x in v), len(v)))   # par jour : somme des variations et nombre de prix
                isbns.setdefault((groupe, nom), set()).update(isbn for isbn, _ in v)
    # prix distincts mesurés sur la période, par groupe
    for i in range(1, len(historique)):
        for cle, p1 in historique[i]["prix"].items():
            p0 = historique[i - 1]["prix"].get(cle)
            groupe = groupe_de.get(cle.split("|")[0])
            if groupe in cumul and cle in observes and p0 and p1 and p0 > 0 and p1 > 0:
                cles.setdefault(groupe, set()).add(cle)
    sortie = {}
    for groupe, series in cumul.items():
        total_log = sum(series.values())
        total_pct = (math.exp(total_log) - 1) * 100
        echelle = total_pct / total_log if abs(total_log) > 1e-9 else 100.0

        # indice propre d'une ou plusieurs séries : chaque jour, somme des variations / nombre de prix (jours alignés par rang)
        def indice_propre(noms):
            par_jour = {}
            for n in noms:
                for k, (somme, nombre) in enumerate(propre[(groupe, n)]):
                    d, t = par_jour.get(k, (0.0, 0))
                    par_jour[k] = (d + somme, t + nombre)
            return sum(d / t for d, t in par_jour.values() if t)

        parts = []
        for nom, valeur in series.items():
            parts.append({"serie": nom, "livres": len(isbns[(groupe, nom)]), "annonces": sum(annonces_de.get(i, 0) for i in isbns[(groupe, nom)]),
                          "contribution_pct": round(valeur * echelle, 2), "noms": [nom]})
        parts.sort(key=lambda x: -abs(x["contribution_pct"]))
        if len(parts) > MAX_SERIES + 1:
            reste = parts[MAX_SERIES:]
            parts = parts[:MAX_SERIES] + [{"serie": f"Autres séries ({len(reste)})", "autres": True,
                                           "livres": len({i for x in reste for i in isbns[(groupe, x['noms'][0])]}),
                                           "annonces": sum(x["annonces"] for x in reste),
                                           "contribution_pct": round(sum(x["contribution_pct"] for x in reste), 2),
                                           "noms": [n for x in reste for n in x["noms"]]}]
        for x in parts:
            log = indice_propre(x.pop("noms"))
            x["debut"], x["fin"], x["variation_pct"] = 100.0, round(100 * math.exp(log), 2), round((math.exp(log) - 1) * 100, 2)
        # les cinq premières par variation, le bloc « Autres » toujours en dernier
        parts.sort(key=lambda x: (x.get("autres", False), x["variation_pct"]))
        sortie[groupe] = {"depuis": debut[groupe], "date": historique[-1]["date"], "variation_pct": round(total_pct, 2),
                          "debut": 100.0, "fin": round(100 * math.exp(total_log), 2), "prix_observes": len(cles.get(groupe, ())), "series": parts}
    return sortie


def chainer_moyenne(historique, groupe_de):
    """Même chaîne que chainer, avec la moyenne des variations logarithmiques au lieu de la médiane (base 100)."""
    niveau, sortie = {}, {}
    for i in range(1, len(historique)):
        avant, apres = historique[i - 1]["prix"], historique[i]["prix"]
        var = variations(avant, apres, groupe_de)
        for groupe, valeurs in var.items():
            niveau.setdefault(groupe, 100.0)
            niveau[groupe] *= math.exp(statistics.fmean(valeurs))
            sortie.setdefault(groupe, []).append(round(niveau[groupe], 2))
    return {g: v[-1] for g, v in sortie.items()}


def garder_observes(historique, observes):
    """Ne garde, chaque jour, que les prix des livres observés (une annonce actuelle pour leur état).
    Les autres livres sont extrapolés plus tard, à partir du mouvement observé : ils ne pèsent pas dans l'indice."""
    return [{"date": h["date"], "prix": {k: v for k, v in h["prix"].items() if k in observes}} for h in historique]


def observes_depuis(chemin_annonces):
    """Clés « isbn|état » ayant au moins une annonce actuelle."""
    try:
        donnees = json.loads(chemin_annonces.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {f"{isbn}|{etat}" for isbn, par_etat in (donnees.get("annonces") or {}).items() for etat, liste in par_etat.items() if liste}


def main():
    historique = json.loads(HISTO.read_text(encoding="utf-8"))
    groupe_de = groupes()
    observes = observes_depuis(ANNONCES)
    historique_observes = garder_observes(historique, observes)
    historique = historique_observes
    courbes = chainer(historique, groupe_de)
    annonces = annonces_par_groupe(ANNONCES, groupe_de)
    resultat = {"date": historique[-1]["date"], "groupes": {}, "editeurs": {}}
    for groupe, serie in sorted(courbes.items()):
        dernier = serie[-1]
        resultat["groupes"][groupe] = {"indice": dernier["indice"], "livres": dernier["livres"],
                                       "annonces": annonces.get(groupe, 0), "historique": [[s["date"], s["indice"]] for s in serie]}
    # Indice par éditeur : même calcul, en regroupant toutes les éditions de l'éditeur
    editeur_de = {isbn: g.split(" · ", 1)[1] for isbn, g in groupe_de.items() if " · " in g}
    courbes_editeurs = chainer(historique, editeur_de)
    for editeur, serie in sorted(courbes_editeurs.items()):
        dernier = serie[-1]
        nb_annonces = sum(v["annonces"] for k, v in resultat["groupes"].items() if k.split(" · ", 1)[1] == editeur)
        resultat["editeurs"][editeur] = {"indice": dernier["indice"], "livres": dernier["livres"], "annonces": nb_annonces,
                                         "historique": [[s["date"], s["indice"]] for s in serie]}
    # Familles d'éditeurs : un imprint rattaché à sa maison (Gallimard Jeunesse → Gallimard), indice calculé sur l'ensemble
    famille_de = {isbn: FAMILLE.get(e, e) for isbn, e in editeur_de.items()}
    courbes_familles = chainer(historique, famille_de)
    for famille, serie in sorted(courbes_familles.items()):
        dernier = serie[-1]
        nb_annonces = sum(v["annonces"] for k, v in resultat["groupes"].items() if FAMILLE.get(k.split(" · ", 1)[1], k.split(" · ", 1)[1]) == famille)
        resultat.setdefault("familles", {})[famille] = {"indice": dernier["indice"], "livres": dernier["livres"], "annonces": nb_annonces,
                                                        "historique": [[s["date"], s["indice"]] for s in serie]}
    # Option B : la médiane reste l'indice ; la moyenne pondérée sert à la cascade et au contrôle d'écart
    moyennes = chainer_moyenne(historique_observes, groupe_de)
    for groupe, valeur in moyennes.items():
        if groupe in resultat["groupes"]:
            resultat["groupes"][groupe]["indice_moyenne"] = valeur
    resultat["cascade"] = cascade_de_la_periode(historique_observes, observes, groupe_de, series_depuis(), annonces_par_isbn(ANNONCES))
    SORTIE.write_text(json.dumps(resultat, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Indice de marché : {len(courbes)} groupes, au {resultat['date']} -> {SORTIE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
