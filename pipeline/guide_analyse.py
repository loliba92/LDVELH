"""Chapitre « Le radar du héros » du guide PDF : le radar du site (offre et prix) pour tout le guide, puis par éditeur et par série, SANS chiffre, calculé à chaque génération.

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


ZONES = {0: "Peu d'annonces, bon marché", 1: "Beaucoup d'annonces, bon marché", 2: "Peu d'annonces, cher", 3: "Beaucoup d'annonces, cher"}          # mots du radar du site
VERDICTS = {0: (("rares en vente, mais bon marché", "rare en vente, mais bon marché"), "peu de vendeurs et un prix bas : un petit marché"),
            1: (("faciles à trouver, et bon marché", "facile à trouver, et bon marché"), "beaucoup de vendeurs et un prix bas : on trouve sans peine"),
            2: (("difficiles à trouver et chères", "difficile à trouver et chère"), "peu de vendeurs et un prix élevé : il faut guetter"), 3: (("faciles à trouver, mais chères", "facile à trouver, mais chère"), "un marché actif, où l'on trouve facilement mais cher")}
GRANDS_RADARS = 3          # un radar par éditeur ayant au moins ce nombre de séries suivies


def liste_mots(noms):
    noms = list(noms)
    return noms[0] if len(noms) == 1 else ", ".join(noms[:-1]) + " et " + noms[-1]


def quadrant(offre, cote_, med_offre, med_cote):
    """0 peu d'offre et bon marché, 1 beaucoup d'offre et bon marché, 2 peu d'offre et cher, 3 beaucoup d'offre et cher (au-dessus de la médiane = « beaucoup », « cher »)."""
    return (1 if offre > med_offre else 0) + (2 if cote_ > med_cote else 0)


def choix(cle, options):
    """Variante de phrase choisie de façon stable d'après `cle`."""
    return options[zlib.crc32(str(cle).encode("utf-8")) % len(options)]


def points_editions(versions, offre):
    """[(annonces en ligne, cote)] : une édition avec ISBN et cote, un point."""
    return [(nb_annonces(offre.get(v["isbn13"])), cote(v)) for v in versions if v.get("isbn13") and cote(v) > 0]


class Echelles:
    """Échelles du radar : offre et prix en logarithmique, médianes (jamais affichées). Les zones se lisent toujours par rapport à tout le guide."""
    def __init__(self, pts, largeur, hauteur, gx=20 * mm, gy=12 * mm, dr=4 * mm, hb=4 * mm):
        self.largeur, self.hauteur, self.gx, self.gy, self.dr, self.hb = largeur, hauteur, gx, gy, dr, hb
        self.med_o = statistics.median(n for n, _ in pts)
        self.med_c = statistics.median(p for _, p in pts)
        self.omax = max(10, max(n for n, _ in pts)) + 1
        self.lo, self.hi = math.log(max(1, min(p for _, p in pts)) * 0.8), math.log(max(p for _, p in pts) * 1.15)

    def X(self, o):
        return self.gx + math.log(o + 1) / math.log(self.omax + 1) * (self.largeur - self.gx - self.dr)

    def Y(self, v):
        return self.gy + (math.log(v) - self.lo) / (self.hi - self.lo) * (self.hauteur - self.gy - self.hb)

    def zone(self, o, v):
        return quadrant(o, v, self.med_o, self.med_c)


def _recoupe(r, autres):
    return any(r[0] < b[2] and r[2] > b[0] and r[1] < b[3] and r[3] > b[1] for b in autres)


def dessiner_radar(pts_fond, series=(), largeur=182 * mm, hauteur=150 * mm, police="Helvetica", police_gras="Helvetica-Bold", c=None, editeur=None, max_etiquettes=14):
    """Radar du héros, comme celui du site mais sans « Ce livre » : un point par édition, quatre zones, médianes en pointillés ; ni graduation ni valeur.
    `series` : [{"editeur", "serie", "editions", "offre", "cote"}] dessinées en bulles étiquetées « Éditeur · Série » (taille selon le nombre d'éditions, sans légende chiffrée)."""
    c = c or COULEURS_NUIT
    d = Drawing(largeur, hauteur)
    if not pts_fond:
        return d
    E = Echelles(pts_fond, largeur, hauteur)
    gx, gy, dr, hb = E.gx, E.gy, E.dr, E.hb
    x_med, y_med = E.X(E.med_o), E.Y(E.med_c)
    for (x0, y0, x1, y1, teinte) in ((gx, y_med, x_med, hauteur - hb, 0.07), (x_med, y_med, largeur - dr, hauteur - hb, 0.0), (gx, gy, x_med, y_med, 0.0), (x_med, gy, largeur - dr, y_med, 0.07)):
        if teinte:
            d.add(Rect(x0, y0, x1 - x0, y1 - y0, strokeColor=None, fillColor=c["grille"], strokeWidth=0))
    d.add(Rect(gx, gy, largeur - gx - dr, hauteur - gy - hb, strokeColor=c["filet"], fillColor=None, strokeWidth=0.6))
    d.add(Line(x_med, gy, x_med, hauteur - hb, strokeColor=c["sourdine"], strokeWidth=0.6, strokeDashArray=[3, 3]))
    d.add(Line(gx, y_med, largeur - dr, y_med, strokeColor=c["sourdine"], strokeWidth=0.6, strokeDashArray=[3, 3]))
    for n, p in pts_fond:
        d.add(Circle(E.X(n), E.Y(p), 0.9 * mm if series else 1.1 * mm, strokeColor=None, fillColor=c["sourdine"], strokeWidth=0))
    pris = []
    for s in sorted(series, key=lambda s: -s["editions"]):
        x, y, r = E.X(s["offre"]), E.Y(s["cote"]), (1.8 + min(4.2, 0.55 * math.sqrt(s["editions"]))) * mm
        d.add(Circle(x, y, r, strokeColor=c["fond"], strokeWidth=0.8, fillColor=c["or"]))
        pris.append((s, x, y, r))
    etiquettes = []
    for s, x, y, r in pris[:max_etiquettes]:
        nom = f"{s['editeur']} · {s['serie']}" if s.get("etiquette_editeur", True) else s["serie"]
        w, h = len(nom) * 0.47 * 6.8, 6.8 * 1.15
        for dx, dy, ancre in ((r + 1.2 * mm, -h / 3, "start"), (-r - 1.2 * mm, -h / 3, "end"), (0, r + 1 * mm, "middle"), (0, -r - h - 0.5 * mm, "middle")):
            xt, yt = x + dx, y + dy
            x0 = xt if ancre == "start" else xt - w if ancre == "end" else xt - w / 2
            rect = (x0, yt, x0 + w, yt + h)
            if rect[0] >= gx and rect[2] <= largeur - dr and rect[1] >= gy and rect[3] <= hauteur - hb and not _recoupe(rect, etiquettes):
                etiquettes.append(rect)
                d.add(String(xt, yt, nom, fontName=police_gras, fontSize=6.8, fillColor=c["texte"], textAnchor=ancre))
                break
    for texte, x, y, ancre in ((ZONES[2], gx + 2 * mm, hauteur - hb - 4 * mm, "start"), (ZONES[3], largeur - dr - 2 * mm, hauteur - hb - 4 * mm, "end"),
                               (ZONES[0], gx + 2 * mm, gy + 2 * mm, "start"), (ZONES[1], largeur - dr - 2 * mm, gy + 2 * mm, "end")):
        d.add(String(x, y, texte, fontName=police_gras, fontSize=7.8, fillColor=c["or"], textAnchor=ancre))
    # axes en mots, avec de vraies flèches dessinées
    ym = 4.2 * mm
    d.add(String(gx, 1.4 * mm, "peu d'annonces", fontName=police, fontSize=8, fillColor=c["texte"]))
    d.add(String(largeur - dr, 1.4 * mm, "beaucoup d'annonces", fontName=police, fontSize=8, fillColor=c["texte"], textAnchor="end"))
    d.add(Line(gx + 30 * mm, ym, largeur - dr - 36 * mm, ym, strokeColor=c["sourdine"], strokeWidth=0.6))
    d.add(Polygon([largeur - dr - 36 * mm, ym + 1 * mm, largeur - dr - 33 * mm, ym, largeur - dr - 36 * mm, ym - 1 * mm], fillColor=c["sourdine"], strokeColor=c["sourdine"]))
    d.add(Polygon([gx + 30 * mm, ym + 1 * mm, gx + 27 * mm, ym, gx + 30 * mm, ym - 1 * mm], fillColor=c["sourdine"], strokeColor=c["sourdine"]))
    d.add(String(gx - 2 * mm, hauteur - hb - 4 * mm, "cher", fontName=police, fontSize=8, fillColor=c["texte"], textAnchor="end"))
    d.add(String(gx - 2 * mm, gy, "pas cher", fontName=police, fontSize=8, fillColor=c["texte"], textAnchor="end"))
    d.add(Line(gx - 8 * mm, gy + 8 * mm, gx - 8 * mm, hauteur - hb - 12 * mm, strokeColor=c["sourdine"], strokeWidth=0.6))
    d.add(Polygon([gx - 9 * mm, hauteur - hb - 12 * mm, gx - 8 * mm, hauteur - hb - 9 * mm, gx - 7 * mm, hauteur - hb - 12 * mm], fillColor=c["sourdine"], strokeColor=c["sourdine"]))
    d.add(Polygon([gx - 9 * mm, gy + 8 * mm, gx - 8 * mm, gy + 5 * mm, gx - 7 * mm, gy + 8 * mm], fillColor=c["sourdine"], strokeColor=c["sourdine"]))
    return d


def _fr(x, decimales=None):
    """Nombre à la française : virgule décimale, sans zéros inutiles pour un entier."""
    if decimales is None:
        return f"{x:g}".replace(".", ",")
    return f"{x:.{decimales}f}".replace(".", ",")


def lecture_globale(pts):
    """Lecture vivante du radar de tout le guide, d'après la répartition des éditions entre les quatre zones (mots seulement)."""
    if not pts:
        return []
    E = Echelles(pts, 100, 100)
    parts = [0, 0, 0, 0]
    for n, p in pts:
        parts[E.zone(n, p)] += 1
    total = sum(parts)
    sans = sum(1 for n, _ in pts if n == 0) / total
    ordre = sorted(range(4), key=lambda z: -parts[z])

    def poids(z):
        r = parts[z] / total
        return "la plus grosse part" if z == ordre[0] else "une part importante" if r >= 0.22 else "une part modeste" if r >= 0.1 else "peu d'éditions"
    ph = ["Chaque point est une édition. Elle se place selon ce qu'on en trouve en ce moment, de gauche à droite, et selon son prix, de bas en haut ; les pointillés marquent le milieu du marché : la ligne verticale, à " + _fr(E.med_o) + " annonces par édition (médiane de l'offre) ; la ligne horizontale, à " + _fr(E.med_c, 2) + "\u00a0€ (médiane des prix). À droite de la verticale, on trouve beaucoup d'annonces ; au-dessus de l'horizontale, c'est cher.",
          f"La plus grosse part des éditions se range en zone « {ZONES[ordre[0]].lower()} » : {VERDICTS[ordre[0]][1]}.",
          f"La zone « {ZONES[ordre[-1]].lower()} » est la plus clairsemée : {VERDICTS[ordre[-1]][1]}."]
    ph.append("Certaines éditions n'ont aucune annonce en ce moment : elles s'alignent tout à gauche du radar." if sans >= 0.05 else "Presque toutes les éditions ont au moins une annonce en ce moment.")
    return ph


def grands_editeurs(profs, minimum=GRANDS_RADARS):
    """Éditeurs qui ont assez de séries suivies pour un radar à eux, du plus fourni au moins fourni."""
    par = {}
    for p in profs:
        par.setdefault(p["editeur"], []).append(p)
    return [e for e, l in sorted(par.items(), key=lambda x: -len(x[1])) if len(l) >= minimum and e != "Autres éditeurs"]


def verdicts_editeur(profs_editeur, pts_fond):
    """[(zone, phrase)] : pour chaque zone peuplée, les séries concernées et un verdict en mots."""
    if not pts_fond:
        return []
    E = Echelles(pts_fond, 100, 100)
    par = {z: [] for z in range(4)}
    for p in profs_editeur:
        par[E.zone(p["offre"], p["cote"])].append(p)
    sortie = []
    for z in (2, 3, 1, 0):
        liste = sorted(par[z], key=lambda p: -p["editions"])[:6]
        if liste:
            noms = liste_mots(p["serie"] for p in liste)
            v = VERDICTS[z][0][1 if len(liste) == 1 else 0]
            sortie.append((z, choix(f"{z}{noms}", (f"{ZONES[z]} : {noms}, {v}.", f"{noms} : {v}. Zone « {ZONES[z].lower()} »."))))
    return sortie


def series_a_surveiller(profs, pts_fond, nb=6):
    """([(éditeur, série, mot)] en zone tendue, [(éditeur, série, mot)] faciles) : les séries à surveiller, avec un mot (jamais un chiffre)."""
    if not pts_fond or not profs:
        return [], []
    E = Echelles(pts_fond, 100, 100)
    tendues, faciles = [], []
    for p in profs:
        z = E.zone(p["offre"], p["cote"])
        eloigne = (E.med_o - p["offre"]) / max(1e-9, E.med_o) + (math.log(p["cote"]) - math.log(E.med_c))
        if z == 2:
            tendues.append((eloigne, p))
        elif z == 1:
            faciles.append(((p["offre"] - E.med_o) / max(1e-9, E.med_o) + (math.log(E.med_c) - math.log(p["cote"])), p))
    t = sorted(tendues, key=lambda x: -x[0])[:nb]
    f = sorted(faciles, key=lambda x: -x[0])[:nb]
    mot_t = lambda v: "très difficile à trouver" if v >= 1.2 else "difficile à trouver"  # noqa: E731
    mot_f = lambda v: "très facile à trouver" if v >= 1.5 else "facile à trouver"  # noqa: E731
    return [(p["editeur"], p["serie"], mot_t(v)) for v, p in t], [(p["editeur"], p["serie"], mot_f(v)) for v, p in f]
