"""Pages « Méthode et analyse » du guide PDF : un état du marché à la date du guide, SANS chiffre, calculé à chaque génération.

Sources : web/data/versions.json (éditeur, série, cote) et data/processed/butin.json (nombre d'annonces par édition et par plateforme : décomptes seulement).
Aucune annonce individuelle, aucun lien, aucune évolution dans le temps. Les seuils qui servent à classer restent ici : le PDF n'affiche que des mots.
Une édition n'est jamais présentée seule : tout est dit pour un éditeur et une série.
"""
import json
import math
import statistics
import zlib
from pathlib import Path

from reportlab.graphics.shapes import Circle, Drawing, Group, Line, Polygon, Rect, String
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm

RACINE = Path(__file__).resolve().parent.parent
SOURCES = (("vin", "Vinted"), ("lbc", "Leboncoin"), ("ebay", "eBay"), ("lib", "les librairies"), ("rev", "les revendeurs"))
MIN_EDITIONS = 4              # une série compte dans le nuage et les classements à partir de ce nombre d'éditions
PART_PLATEFORME = ((0.5, "domine l'offre", "dominent l'offre"), (0.2, "tient une place importante", "tiennent une place importante"), (0.08, "apporte un complément", "apportent un complément"), (0.0, "reste discrète", "restent discrètes"))
COULEURS_NUIT = {"texte": HexColor("#f2e9d8"), "sourdine": HexColor("#b8ad99"), "or": HexColor("#d9b45f"), "filet": HexColor("#6f6a60"), "fond": HexColor("#0c0a08"), "grille": HexColor("#2c261e")}
EDITEURS_TENDANCE = ("Gallimard", "Gallimard Jeunesse", "Alkonost", "Scriptarium", "Hachette", "Elder Craft", "Sarbacane", "Bragelonne")


def charger(racine=RACINE):
    try:
        offre = json.loads((Path(racine) / "data/processed/butin.json").read_text(encoding="utf-8")).get("offre", {})
    except (OSError, ValueError):
        offre = {}
    return {"offre": offre}


def nb_annonces(o):
    return sum((o or {}).get(k, 0) or 0 for k, _ in SOURCES)


def cote(v):
    p = v.get("prix") or {}
    return p.get("tres_bon") or p.get("bon") or 0


def profils(versions, offre, editeur_de):
    """[{editeur, serie, editions, offre (annonces par édition, en moyenne), sans (part sans annonce), cote (médiane), sources {clé: total}}] pour les séries d'au moins MIN_EDITIONS éditions."""
    groupes = {}
    for v in versions:
        if v.get("isbn13") and cote(v) > 0:
            groupes.setdefault((editeur_de(v), (v.get("serie") or "").strip() or "Hors série"), []).append(v)
    sortie = []
    for (e, s), liste in groupes.items():
        if len(liste) < MIN_EDITIONS:
            continue
        o = [offre.get(v["isbn13"]) or {} for v in liste]
        sortie.append({"editeur": e, "serie": s, "editions": len(liste), "offre": sum(nb_annonces(x) for x in o) / len(liste), "sans": sum(1 for x in o if nb_annonces(x) == 0) / len(liste),
                       "cote": statistics.median(cote(v) for v in liste), "sources": {k: sum(x.get(k, 0) or 0 for x in o) for k, _ in SOURCES}})
    return sortie


def rang_relatif(valeur, valeurs):
    """Part des valeurs strictement plus petites (0 à 1)."""
    return sum(1 for x in valeurs if x < valeur) / max(1, len(valeurs) - 1) if len(valeurs) > 1 else 0.5


def niveau_activite(r):
    """Mot pour le rang relatif d'une série parmi les autres, d'après l'offre en ligne."""
    return "très active" if r >= 0.8 else "active" if r >= 0.5 else "calme" if r >= 0.2 else "atone"


def niveau_prix(r):
    return "haut" if r >= 0.67 else "moyen" if r >= 0.33 else "bas"


def quadrant(offre, cote_, med_offre, med_cote):
    """0 peu d'offre et bon marché, 1 beaucoup d'offre et bon marché, 2 peu d'offre et cher (en tension), 3 beaucoup d'offre et cher."""
    return (1 if offre > med_offre else 0) + (2 if cote_ > med_cote else 0)


def choix(cle, options):
    """Variante de phrase choisie de façon stable d'après `cle` : la même donnée donne la même phrase, deux séries voisines n'ont pas toujours la même tournure."""
    return options[zlib.crc32(str(cle).encode("utf-8")) % len(options)]


def liste_mots(noms):
    noms = list(noms)
    return noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + " et " + noms[-1]


def nom_serie(p):
    return f"{p['editeur']} · {p['serie']}"


def part_sources(profs):
    total = sum(sum(p["sources"].values()) for p in profs) or 1
    return {k: sum(p["sources"][k] for p in profs) / total for k, _ in SOURCES}


def synthese(profs, versions, offre):
    """Phrases de la synthèse globale du marché à la date du guide."""
    if not profs:
        return []
    avec = sum(1 for v in versions if v.get("isbn13") and nb_annonces(offre.get(v["isbn13"])) > 0) / max(1, sum(1 for v in versions if v.get("isbn13")))
    presence = "presque toutes" if avec >= 0.9 else "la grande majorité" if avec >= 0.7 else "environ la moitié" if avec >= 0.45 else "une minorité"
    offres = [p["offre"] for p in profs]
    actives = [p for p in profs if niveau_activite(rang_relatif(p["offre"], offres)) in ("très active", "active")]
    ph = [f"À la date du guide, le marché de l'occasion est {'très animé' if avec >= 0.85 else 'animé' if avec >= 0.6 else 'plutôt calme'} : {presence} des éditions suivies ont au moins une annonce en ligne."]
    if actives:
        ph.append(f"L'activité se concentre sur {liste_mots(nom_serie(p) for p in sorted(actives, key=lambda p: -p['offre'])[:3])}, où l'offre est la plus fournie.")
    calmes = [p for p in profs if niveau_activite(rang_relatif(p["offre"], offres)) == "atone"]
    if calmes:
        ph.append(f"À l'inverse, l'offre est atone pour {liste_mots(nom_serie(p) for p in sorted(calmes, key=lambda p: p['offre'])[:3])}.")
    return ph


def panorama_plateformes(profs):
    """[(plateforme, phrase)] : le poids de chacune dans l'offre et les séries où elle se montre le plus."""
    parts = part_sources(profs)
    sortie = []
    for k, nom in SOURCES:
        if k == "rev" and parts[k] == 0:
            continue
        pluriel = nom.startswith("les ")
        _, singulier, plur = next(m for m in PART_PLATEFORME if parts[k] >= m[0])
        phares = [p for p in sorted(profs, key=lambda p: -p["sources"][k] / p["editions"]) if p["sources"][k] > 0][:2]
        fin = f" {'Elles sont' if pluriel else 'Elle est'} surtout présente{'s' if pluriel else ''} pour {liste_mots(nom_serie(p) for p in phares)}." if phares and parts[k] >= 0.08 else ""
        sujet = nom[0].upper() + nom[1:] if not nom.startswith("e") else nom
        sortie.append((nom, f"{sujet} {plur if pluriel else singulier}.{fin}"))
    return sortie


def panorama_editeurs(profs, editeurs):
    """[(éditeur, phrase)] : activité, niveau de prix et séries phares de chaque éditeur."""
    offres = [p["offre"] for p in profs]
    cotes = [p["cote"] for p in profs]
    cotes_mot = {"bas": ("basses", "bas"), "moyen": ("moyennes", "moyen"), "haut": ("hautes", "haut")}
    sortie = []
    for e in editeurs:
        ps = [p for p in profs if p["editeur"] == e]
        if not ps:
            continue
        act = niveau_activite(rang_relatif(statistics.mean(p["offre"] for p in ps), offres))
        px = niveau_prix(rang_relatif(statistics.median(p["cote"] for p in ps), cotes))
        phares = liste_mots(p["serie"] for p in sorted(ps, key=lambda p: -p["editions"] * (1 + p["offre"]))[:3])
        feminin, masculin = cotes_mot[px]
        sortie.append((e, choix(e, (f"{e} : un marché {act.replace('très active', 'très actif').replace('active', 'actif')}, des cotes plutôt {feminin}. Séries à suivre : {phares}.",
                                    f"Chez {e}, l'offre est {act} et le niveau des cotes {masculin}. Séries phares : {phares}."))))
    return sortie


def points_attention(profs):
    """(séries en tension, séries abondantes) : [(éditeur, série)] ; la tension : cote haute et offre faible ; l'abondance : offre forte et cote basse."""
    if not profs:
        return [], []
    mo, mc = statistics.median(p["offre"] for p in profs), statistics.median(p["cote"] for p in profs)
    tension = sorted((p for p in profs if quadrant(p["offre"], p["cote"], mo, mc) == 2), key=lambda p: (-p["cote"] / (1 + p["offre"])))[:5]
    abondantes = sorted((p for p in profs if quadrant(p["offre"], p["cote"], mo, mc) == 1), key=lambda p: -(p["offre"] / (1 + p["cote"])))[:5]
    return [(p["editeur"], p["serie"]) for p in tension], [(p["editeur"], p["serie"]) for p in abondantes]


def phrases_attention(profs):
    t, a = points_attention(profs)
    ph = []
    if t:
        ph.append(f"Séries en tension, où l'offre est rare pour des cotes élevées : {liste_mots(f'{e} · {s}' for e, s in t)}.")
    if a:
        ph.append(f"Séries abondantes, faciles à trouver à bas prix : {liste_mots(f'{e} · {s}' for e, s in a)}.")
    return ph


def dessiner_nuage(profs, largeur=174 * mm, hauteur=118 * mm, police="Helvetica", police_gras="Helvetica-Bold", c=None):
    """Nuage de points : un point par série (éditeur entre parenthèses), offre en abscisse, niveau de prix en ordonnée. Ni graduation ni valeur : axes en mots ; les formes
    (et non la couleur) disent le coin où se trouve la série."""
    c = c or COULEURS_NUIT
    d = Drawing(largeur, hauteur)
    gx, gy, dr, hb = 8 * mm, 10 * mm, 4 * mm, 4 * mm
    if not profs:
        return d
    mo, mc = statistics.median(p["offre"] for p in profs), statistics.median(p["cote"] for p in profs)
    omax = max(p["offre"] for p in profs) + 1
    lo, hi = math.log(min(p["cote"] for p in profs) * 0.85), math.log(max(p["cote"] for p in profs) * 1.15)
    X = lambda o: gx + math.log(o + 1) / math.log(omax + 1) * (largeur - gx - dr)  # noqa: E731
    Y = lambda v: gy + (math.log(v) - lo) / (hi - lo) * (hauteur - gy - hb)  # noqa: E731
    d.add(Rect(gx, gy, largeur - gx - dr, hauteur - gy - hb, strokeColor=c["filet"], fillColor=None, strokeWidth=0.6))
    for (x1, y1, x2, y2) in ((X(mo), gy, X(mo), hauteur - hb), (gx, Y(mc), largeur - dr, Y(mc))):
        d.add(Line(x1, y1, x2, y2, strokeColor=c["sourdine"], strokeWidth=0.6, strokeDashArray=[3, 3]))
    for p in profs:
        q, x, y = quadrant(p["offre"], p["cote"], mo, mc), X(p["offre"]), Y(p["cote"])
        trait = dict(strokeColor=c["sourdine"], strokeWidth=0.6, fillColor=None if q == 0 else c["sourdine"] if q == 3 else c["fond"])
        if q in (0, 3):
            d.add(Circle(x, y, 1.9 * mm, **trait))
        elif q == 1:
            d.add(Rect(x - 1.8 * mm, y - 1.8 * mm, 3.6 * mm, 3.6 * mm, **trait))
        else:
            d.add(Polygon([x, y + 2.2 * mm, x - 2 * mm, y - 1.7 * mm, x + 2 * mm, y - 1.7 * mm], **trait))
    for p in sorted(profs, key=lambda p: -p["editions"])[:9]:          # les séries les plus fournies sont nommées
        x, y = X(p["offre"]), Y(p["cote"])
        droite = x > largeur * 0.6
        nom = f"{p['serie'][:24]} ({p['editeur'][:12]})"
        d.add(String(x + (-3 if droite else 3) * mm, y + 1 * mm, nom, fontName=police, fontSize=6.6, fillColor=c["texte"], textAnchor="end" if droite else "start"))
    for texte, x, y, ancre in (("En tension : offre faible, prix haut", gx + 2 * mm, hauteur - hb - 4 * mm, "start"), ("Offre forte, prix haut", largeur - dr - 2 * mm, hauteur - hb - 4 * mm, "end"),
                               ("Offre faible, prix bas", gx + 2 * mm, gy + 2 * mm, "start"), ("Abondant : offre forte, prix bas", largeur - dr - 2 * mm, gy + 2 * mm, "end")):
        d.add(String(x, y, texte, fontName=police_gras, fontSize=7.5, fillColor=c["or"], textAnchor=ancre))
    # axes en mots : flèches dessinées (le sous-ensemble de police du site n'a pas de flèche)
    ymid = 3.5 * mm
    d.add(String(gx, 1.2 * mm, "offre faible", fontName=police, fontSize=8, fillColor=c["texte"]))
    d.add(String(largeur - dr, 1.2 * mm, "offre forte", fontName=police, fontSize=8, fillColor=c["texte"], textAnchor="end"))
    d.add(Line(gx + 22 * mm, ymid, largeur - dr - 22 * mm, ymid, strokeColor=c["sourdine"], strokeWidth=0.6))
    d.add(Polygon([largeur - dr - 22 * mm, ymid + 1 * mm, largeur - dr - 19 * mm, ymid, largeur - dr - 22 * mm, ymid - 1 * mm], fillColor=c["sourdine"], strokeColor=c["sourdine"]))
    d.add(Line(3.2 * mm, gy + 18 * mm, 3.2 * mm, hauteur - hb - 14 * mm, strokeColor=c["sourdine"], strokeWidth=0.6))
    d.add(Polygon([2.2 * mm, hauteur - hb - 17 * mm, 3.2 * mm, hauteur - hb - 14 * mm, 4.2 * mm, hauteur - hb - 17 * mm], fillColor=c["sourdine"], strokeColor=c["sourdine"]))
    g = Group(String(0, 0, "prix bas", fontName=police, fontSize=8, fillColor=c["texte"]), String(0, 0, "", fontName=police, fontSize=8))
    g.rotate(90)
    g.translate(gy + 1 * mm, -2.2 * mm)
    d.add(g)
    g2 = Group(String(0, 0, "prix haut", fontName=police, fontSize=8, fillColor=c["texte"], textAnchor="end"))
    g2.rotate(90)
    g2.translate(hauteur - hb - 1 * mm, -2.2 * mm)
    d.add(g2)
    return d


def textes(versions, donnees, editeur_de, editeurs):
    """Tous les textes d'analyse calculés (pour les pages et pour les tests) : {rubrique: [phrases]}."""
    profs = profils(versions, donnees["offre"], editeur_de)
    return {"synthese": synthese(profs, versions, donnees["offre"]), "plateformes": [t for _, t in panorama_plateformes(profs)], "editeurs": [t for _, t in panorama_editeurs(profs, editeurs)],
            "attention": phrases_attention(profs)}, profs
