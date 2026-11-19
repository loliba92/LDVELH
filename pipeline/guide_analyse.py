"""Pages « Méthode et analyse » du guide PDF : nuage de points et chiffres de marché, calculés à chaque génération à partir des données du dépôt.

Sources : web/data/versions.json (cotes), data/processed/butin.json (nombre d'annonces par édition : décomptes seulement), web/data/tendances.json et
web/data/mouvements.json. Aucune annonce individuelle, aucun lien, aucun nom de site dans le PDF.
"""
import json
import math
import statistics
from pathlib import Path

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm

RACINE = Path(__file__).resolve().parent.parent
OR, SOURDINE, TEXTE, FILET = HexColor("#d9b45f"), HexColor("#b8ad99"), HexColor("#f2e9d8"), HexColor("#6f6a60")
EDITEURS_TENDANCE = ("Gallimard", "Gallimard Jeunesse", "Alkonost", "Scriptarium", "Hachette", "Elder Craft", "Sarbacane", "Bragelonne")
TRANCHES = ((0, 10, "moins de 10 €"), (10, 20, "10 à 20 €"), (20, 40, "20 à 40 €"), (40, 70, "40 à 70 €"), (70, 10 ** 9, "70 € et plus"))          # mêmes tranches que le site


def charger(racine=RACINE):
    lire = lambda c: json.loads((Path(racine) / c).read_text(encoding="utf-8"))  # noqa: E731
    try:
        offre = lire("data/processed/butin.json").get("offre", {})
    except (OSError, ValueError):
        offre = {}
    return {"offre": offre, "tendances": lire("web/data/tendances.json"), "mouvements": lire("web/data/mouvements.json")}


def nb_annonces(o):
    return sum((o or {}).get(k, 0) or 0 for k in ("ebay", "lbc", "vin", "lib", "rev"))


def cote(v):
    p = v.get("prix") or {}
    return p.get("tres_bon") or p.get("bon") or 0


def points(versions, offre):
    """[(nombre d'annonces, cote, titre)] : une édition avec ISBN et cote, un point."""
    return [(nb_annonces(offre.get(v["isbn13"])), cote(v), v.get("titre") or "") for v in versions if v.get("isbn13") and cote(v) > 0]


def quadrant(n, p, med_n, med_p):
    """0 peu d'annonces et bon marché, 1 beaucoup et bon marché, 2 peu et cher, 3 beaucoup et cher (au-dessus de la médiane = « beaucoup », « cher »)."""
    return (1 if n > med_n else 0) + (2 if p > med_p else 0)


COULEURS_NUIT = {"texte": TEXTE, "sourdine": SOURDINE, "or": OR, "filet": FILET, "fond": HexColor("#0c0a08"), "grille": HexColor("#2c261e")}


def dessiner_nuage(pts, largeur=174 * mm, hauteur=118 * mm, police="Helvetica", police_gras="Helvetica-Bold", c=None):
    """Nuage de points : annonces en ligne (échelle logarithmique) et cote (logarithmique). Les formes suffisent à lire le graphique sans la couleur."""
    c = c or COULEURS_NUIT
    OR, SOURDINE, TEXTE, FILET = c["or"], c["sourdine"], c["texte"], c["filet"]
    d = Drawing(largeur, hauteur)
    gx, gy, dr, hb = 16 * mm, 12 * mm, 4 * mm, 4 * mm
    if not pts:
        return d
    med_n, med_p = statistics.median(n for n, _, _ in pts), statistics.median(p for _, p, _ in pts)
    nmax = max(10, max(n for n, _, _ in pts)) + 1
    lo, hi = math.log(max(1, min(p for _, p, _ in pts)) * 0.8), math.log(max(p for _, p, _ in pts) * 1.15)
    X = lambda n: gx + math.log(n + 1) / math.log(nmax + 1) * (largeur - gx - dr)  # noqa: E731
    Y = lambda p: gy + (math.log(p) - lo) / (hi - lo) * (hauteur - gy - hb)  # noqa: E731
    d.add(Rect(gx, gy, largeur - gx - dr, hauteur - gy - hb, strokeColor=FILET, fillColor=None, strokeWidth=0.6))
    for p in (5, 10, 20, 50, 100, 200):
        if math.exp(lo) < p < math.exp(hi):
            d.add(Line(gx, Y(p), largeur - dr, Y(p), strokeColor=c["grille"], strokeWidth=0.4))
            d.add(String(gx - 2 * mm, Y(p) - 1.2 * mm, f"{p} €", fontName=police, fontSize=7, fillColor=SOURDINE, textAnchor="end"))
    for n in (0, 1, 3, 10, 30, 100):
        if n < nmax:
            d.add(String(X(n), gy - 4.5 * mm, str(n), fontName=police, fontSize=7, fillColor=SOURDINE, textAnchor="middle"))
    for (x1, y1, x2, y2) in ((X(med_n), gy, X(med_n), hauteur - hb), (gx, Y(med_p), largeur - dr, Y(med_p))):
        d.add(Line(x1, y1, x2, y2, strokeColor=SOURDINE, strokeWidth=0.6, strokeDashArray=[3, 3]))
    formes = []
    for n, p, titre in pts:
        q, x, y = quadrant(n, p, med_n, med_p), X(n), Y(p)
        trait = dict(strokeColor=SOURDINE, strokeWidth=0.5, fillColor=None if q == 0 else SOURDINE if q == 3 else c["fond"])
        if q in (0, 3):
            forme = Circle(x, y, 1.5 * mm, **trait)
        elif q == 1:
            forme = Rect(x - 1.4 * mm, y - 1.4 * mm, 2.8 * mm, 2.8 * mm, **trait)
        else:
            forme = Polygon([x, y + 1.7 * mm, x - 1.6 * mm, y - 1.3 * mm, x + 1.6 * mm, y - 1.3 * mm], **trait)
        formes.append(forme)
    for f in formes:
        d.add(f)
    cart = {"hg": "Peu d'annonces, cher", "hd": "Beaucoup d'annonces, cher", "bg": "Peu d'annonces, bon marché", "bd": "Beaucoup d'annonces, bon marché"}
    d.add(String(gx + 2 * mm, hauteur - hb - 4 * mm, cart["hg"], fontName=police_gras, fontSize=7.5, fillColor=OR))
    d.add(String(largeur - dr - 2 * mm, hauteur - hb - 4 * mm, cart["hd"], fontName=police_gras, fontSize=7.5, fillColor=OR, textAnchor="end"))
    d.add(String(gx + 2 * mm, gy + 2 * mm, cart["bg"], fontName=police_gras, fontSize=7.5, fillColor=OR))
    d.add(String(largeur - dr - 2 * mm, gy + 2 * mm, cart["bd"], fontName=police_gras, fontSize=7.5, fillColor=OR, textAnchor="end"))
    d.add(String(X(med_n) + 1.5 * mm, gy + 8 * mm, f"médiane : {int(med_n)}", fontName=police, fontSize=7, fillColor=SOURDINE))
    d.add(String(gx + 1.5 * mm, Y(med_p) + 1.5 * mm, f"médiane : {med_p:.0f} €".replace(".", ","), fontName=police, fontSize=7, fillColor=SOURDINE))
    d.add(String((largeur + gx) / 2, 1 * mm, "nombre d'annonces en ligne (échelle logarithmique)", fontName=police, fontSize=7.5, fillColor=TEXTE, textAnchor="middle"))
    # étiquettes : les trois éditions les plus chères et les trois les plus recherchées
    ordre = sorted(pts, key=lambda t: -t[1])[:3] + sorted(pts, key=lambda t: -t[0])[:3]
    vus = set()
    for n, p, titre in ordre:
        if titre in vus:
            continue
        vus.add(titre)
        droite = X(n) > largeur * 0.65
        d.add(String(X(n) + (-2 if droite else 2) * mm, Y(p) + 1 * mm, titre[:26], fontName=police, fontSize=6.5, fillColor=TEXTE, textAnchor="end" if droite else "start"))
    return d


def phrases_nuage(pts):
    """Phrases calculées sur les points."""
    if not pts:
        return []
    med_n, med_p = statistics.median(n for n, _, _ in pts), statistics.median(p for _, p, _ in pts)
    sans = sum(1 for n, _, _ in pts if n == 0)
    q = [0, 0, 0, 0]
    for n, p, _ in pts:
        q[quadrant(n, p, med_n, med_p)] += 1
    pl = lambda n, mot: f"{n} {mot}{'s' if n > 1 else ''}"  # noqa: E731
    return [f"Le graphique place {len(pts)} éditions. La médiane est de {pl(int(med_n), 'annonce')} en ligne et de {round(med_p)} €.",
            f"{pl(sans, 'édition')} ({round(100 * sans / len(pts))} %) {'sont' if sans > 1 else 'est'} sans annonce en ligne.",
            f"Par rapport aux médianes : {q[2]} éditions chères et peu annoncées (triangles), {q[3]} chères et très annoncées (disques pleins), "
            f"{q[0]} bon marché et peu annoncées (disques vides), {q[1]} bon marché et très annoncées (carrés)."]


def pct(x):
    return f"{x * 100:+.1f}".replace(".", ",").replace("-", "−") + " %"


def lignes_tendance(tendances, filtre=None, nom=None):
    """[(groupe, éditions comparées, variation médiane, hausses, baisses)] pour un type de groupe ('version', 'editeur', 'decennie', 'serie'), groupes trop petits écartés."""
    sortie = []
    for g in (tendances.get("groupes", {}).get("marche", {}).get(nom) or []):
        if g.get("peu") or (filtre and not filtre(g["cle"])):
            continue
        sortie.append((g["cle"], g["n"], g["mediane"], g["hausses"], g["baisses"]))
    return sortie


def repartition_tranches(versions):
    """[(libellé, nombre d'éditions)] selon la cote."""
    cotes = [cote(v) for v in versions if cote(v) > 0]
    return [(nom, sum(1 for c in cotes if a <= c < b)) for a, b, nom in TRANCHES]


def grands_mouvements(mouvements, nb=6):
    """[(titre, version, avant, après, variation)] : les plus fortes hausses puis les plus fortes baisses (cotes, pas d'annonces)."""
    hausses = sorted(mouvements.get("hausses") or [], key=lambda m: -m["pct"])[:nb]
    baisses = sorted(mouvements.get("baisses") or [], key=lambda m: m["pct"])[:nb]
    return [(m["titre"], m.get("version") or "", m["avant"], m["apres"], m["pct"]) for m in hausses], [(m["titre"], m.get("version") or "", m["avant"], m["apres"], m["pct"]) for m in baisses]


def indice_actuel(tendances):
    t = tendances.get("temps") or []
    return (t[0], t[-1]) if len(t) >= 2 else None


def barres(lignes, largeur, hauteur, police, police_gras, c, divergent=False, unite=""):
    """Diagramme en barres horizontales : [(libellé, valeur)]. `divergent` : axe au milieu, hausses à droite et baisses à gauche. Les valeurs sont écrites : la couleur n'est pas nécessaire."""
    d = Drawing(largeur, hauteur)
    if not lignes:
        return d
    pas = hauteur / len(lignes)
    gauche = 38 * mm
    zone = largeur - gauche - 22 * mm
    vmax = max(abs(v) for _, v in lignes) or 1
    zero = gauche + (zone / 2 if divergent else 0)
    for i, (nom, v) in enumerate(lignes):
        y = hauteur - (i + 1) * pas + pas * 0.2
        long = abs(v) / vmax * (zone / 2 if divergent else zone)
        x0 = zero if v >= 0 or not divergent else zero - long
        d.add(String(0, y + 0.6 * mm, nom, fontName=police, fontSize=8, fillColor=c["texte"]))
        d.add(Rect(x0, y, max(long, 0.4), pas * 0.55, strokeColor=c["or"], strokeWidth=0.5, fillColor=c["or"] if v >= 0 else None))
        texte = f"{v:+.1f} %".replace(".", ",").replace("-", "−") if unite == "pct" else str(v)
        d.add(String(x0 + long + 1.5 * mm if (v >= 0 or not divergent) else x0 - 1.5 * mm, y + 0.8 * mm, texte, fontName=police_gras, fontSize=8, fillColor=c["texte"], textAnchor="start" if (v >= 0 or not divergent) else "end"))
    if divergent:
        d.add(Line(zero, 0, zero, hauteur, strokeColor=c["sourdine"], strokeWidth=0.5))
    return d
