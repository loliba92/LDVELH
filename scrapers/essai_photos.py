"""Essai de la comparaison de photos sur de vraies annonces eBay (aucun enregistrement, résultats dans le journal).

Question posée : la méthode (reconciliation_image.decider) reconnaît-elle les vraies photos de vendeurs ?
Vérité de départ : une annonce trouvée par l'ISBN, dont le titre concorde, est bien celle de l'édition (sauf erreur rare du vendeur).
Trois mesures, par annonce :
  A. photo contre la jaquette de SON édition : « confirmée » (assez de points communs), « non concluante » (trop peu), « illisible » ;
  B. photo contre la jaquette d'un AUTRE livre : une confirmation ici est une fausse acceptation (doit rester à zéro) ;
  C. photo contre toutes les éditions du même livre (le cas de la réconciliation) : attribuée à la bonne édition, à une autre (grave), ou laissée sans décision.
Le journal d'un dépôt public est public : on n'y écrit que des décomptes et des liens d'annonces, jamais de titre ni de vendeur."""
import collections
import random

import reconciliation_image as ri

PAR_EDITION = 3          # annonces au plus par édition : l'échantillon couvre plus d'éditions
TRANCHES = ((0, 3), (4, 11), (12, 24), (25, 10**6))      # points communs : [0-3], [4-11], [12-24], [25 et plus]


def _tranche(n):
    return next(f"{a}-{b}" if b < 10**6 else f"{a}+" for a, b in TRANCHES if a <= n <= b)


def mesurer(par_isbn, dossier_covers, livre_de, editions_du_livre, http, graine=7):
    """par_isbn : {isbn: [annonces trouvées par l'ISBN, titre concordant]}. Renvoie (statistiques, exemples)."""
    rnd = random.Random(graine)
    toutes = sorted(i for i in livre_de if ri.jaquette_locale(dossier_covers, i))
    s = collections.Counter()
    tranches = collections.Counter()
    exemples = {"non_concluante": [], "fausse_acceptation": [], "mauvaise_edition": []}
    for isbn, items in sorted(par_isbn.items()):
        jaq = ri.jaquette_locale(dossier_covers, isbn)
        if jaq is None:
            s["éditions sans jaquette (ignorées)"] += 1
            continue
        for it in items[:PAR_EDITION]:
            lien = it.get("itemWebUrl") or it.get("itemId") or "?"
            octets = ri.empreinte_annonce(it, http)
            if octets is None:
                s["A illisible"] += 1
                continue
            s["annonces essayées"] += 1
            retenu, scores = ri.decider(octets, {isbn: jaq})
            points = scores.get(isbn, 0)
            tranches[_tranche(points)] += 1
            if retenu == isbn:
                s["A confirmée"] += 1
            else:
                s["A non concluante"] += 1
                if len(exemples["non_concluante"]) < 25:
                    exemples["non_concluante"].append((isbn, points, lien))
            # B : jaquette d'un autre livre, tirée au hasard
            autres = [i for i in toutes if livre_de[i] != livre_de[isbn]]
            if autres:
                autre = rnd.choice(autres)
                r2, sc2 = ri.decider(octets, {autre: ri.jaquette_locale(dossier_covers, autre)})
                s["B essais"] += 1
                if r2 == autre:
                    s["B fausse acceptation"] += 1
                    if len(exemples["fausse_acceptation"]) < 10:
                        exemples["fausse_acceptation"].append((isbn, sc2.get(autre, 0), lien))
            # C : toutes les éditions du même livre
            freres = [i for i in editions_du_livre.get(livre_de[isbn], []) if ri.jaquette_locale(dossier_covers, i)]
            if len(freres) >= 2:
                r3, _ = ri.decider(octets, {i: ri.jaquette_locale(dossier_covers, i) for i in freres})
                s["C essais (livre à plusieurs éditions)"] += 1
                if r3 == isbn:
                    s["C bonne édition"] += 1
                elif r3 is None:
                    s["C sans décision"] += 1
                else:
                    s["C MAUVAISE édition"] += 1
                    if len(exemples["mauvaise_edition"]) < 10:
                        exemples["mauvaise_edition"].append((isbn, r3, lien))
    return s, tranches, exemples


def afficher(s, tranches, exemples):
    def pct(a, b):
        return f"{100 * a / b:.0f} %" if b else "n/a"
    n = s["annonces essayées"]
    print(f"Annonces essayées : {n} (photos illisibles : {s['A illisible']}, éditions sans jaquette : {s['éditions sans jaquette (ignorées)']})")
    print(f"A. Photo contre la jaquette de son édition : confirmée {s['A confirmée']} ({pct(s['A confirmée'], n)}), non concluante {s['A non concluante']} ({pct(s['A non concluante'], n)})")
    print("   Points communs (SIFT) : " + ", ".join(f"{k} : {tranches[k]}" for k in ("0-3", "4-11", "12-24", "25+")) + f"  (seuil de décision : {ri.SEUIL_INLIERS})")
    print(f"B. Photo contre un autre livre : fausses acceptations {s['B fausse acceptation']} sur {s['B essais']} ({pct(s['B fausse acceptation'], s['B essais'])}) — doit rester à 0")
    c = s["C essais (livre à plusieurs éditions)"]
    print(f"C. Livre à plusieurs éditions ({c} essais) : bonne édition {s['C bonne édition']} ({pct(s['C bonne édition'], c)}), sans décision {s['C sans décision']} ({pct(s['C sans décision'], c)}), "
          f"MAUVAISE édition {s['C MAUVAISE édition']} ({pct(s['C MAUVAISE édition'], c)}) — doit rester à 0")
    for cle, titre in (("fausse_acceptation", "Fausses acceptations (B)"), ("mauvaise_edition", "Mauvaises éditions (C)"), ("non_concluante", "Annonces non concluantes (A), à ouvrir pour juger la photo")):
        if exemples[cle]:
            print(f"{titre} :")
            for isbn, x, lien in exemples[cle]:
                print(f"  {isbn} {x} {lien}")


def essayer(a, token, catalogue, chercher, concorde, dossier_covers, http=None):
    """Interroge eBay par l'ISBN pour un échantillon d'éditions, garde les annonces au titre concordant, puis mesure."""
    import requests
    http = http or requests
    rnd = random.Random(7)
    cat = catalogue()
    echantillon = rnd.sample(cat, min(a.essai_photos, len(cat)))
    livre_de = {c[0]: c[3] for c in cat}
    editions_du_livre = collections.defaultdict(list)
    for c in cat:
        editions_du_livre[c[3]].append(c[0])
    par_isbn = {}
    for isbn, titre, nb_ed, livre, annees in echantillon:
        items = [it for it in chercher(isbn, titre, token) if concorde(it.get("title", ""), titre)]
        if items:
            par_isbn[isbn] = items
    print(f"Échantillon : {len(echantillon)} éditions tirées au hasard, {len(par_isbn)} avec des annonces trouvées par l'ISBN.")
    s, tranches, exemples = mesurer(par_isbn, dossier_covers, livre_de, editions_du_livre, http)
    afficher(s, tranches, exemples)
