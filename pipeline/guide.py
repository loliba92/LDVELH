"""Guide de référence en PDF : jaquettes et cotes de tous les livres, éditeur par éditeur, à partir de web/data/versions.json et web/covers/.

Usage : python pipeline/guide.py [--sortie guide.pdf] [--style nuit|parchemin] [--couverture clair|bandeau] [--editeurs "Scriptarium,Hachette"] [--series "Loup Solitaire"]
                                 [--mention-sorciers]
Plan : éditeur, puis version (V1 avant V2, ordre naturel), puis série par ordre alphabétique, livres par numéro. Un éditeur et une version commencent toujours une nouvelle page ;
les séries d'une version s'enchaînent sans saut de page. Aucune requête réseau. Le PDF n'est pas gardé dans le dépôt : il se génère à la demande.
Polices : Cormorant Garamond et Source Sans 3 (licence SIL OFL, web/fonts/), converties au vol en TrueType ; sans fontTools, polices de base du PDF.
"""
import argparse
import io
import json
import re
import statistics
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.platypus.tableofcontents import TableOfContents

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guide_analyse as ga

# ---- RÉGLAGES à changer ici (valeur unique) : choix du propriétaire en attente ----
STYLE_PAR_DEFAUT = "parchemin"          # direction de style : "nuit" (sombre et or) ou "parchemin" (fond crème, pour l'impression)
SOUS_TITRE_PAR_DEFAUT = "clair"      # sous-titre de la couverture « huile » : "clair" ou "bandeau" (sans effet sur la couverture V1)
COUVERTURE_PAR_DEFAUT = "v1"         # illustration de couverture : "v1" (héros et dragon) ou "huile" (ancienne couverture)
COUVERTURE_STYLE = "b"              # mise en page de la couverture V1 : "a" (revue de collection), "b" (affiche d'aventure) ou "c" (ouvrage de référence sobre)
# -------------------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
WEB = RACINE / "web"
COUVERTURE = Path(__file__).resolve().parent / "guide" / "couverture.jpg"          # illustration « huile »
COUVERTURE_V1 = Path(__file__).resolve().parent / "guide" / "couverture-v1.jpg"          # illustration « V1 » (992 × 1586) : héros, dragon, château
EMBLEME = WEB / "icons" / "icon-512.png"          # le sceau du site : le personnage encapuchonné
SITE = "lacoteduheros.fr"
LIEN_SITE = "https://lacoteduheros.fr"
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
LARGEUR_JAQUETTE_PX = 230           # jaquette « small » réduite : nette à 28 mm (environ 210 points par pouce)
COLONNES = 5
LARGEUR_JAQUETTE = 24 * mm          # largeur de la jaquette dans la grille (5 colonnes)
MARGE_X, HAUT, BAS = 14 * mm, 21 * mm, 19 * mm
L_PAGE, H_PAGE = A4
L_CADRE = L_PAGE - 2 * MARGE_X

# Deux directions de style. « nuit » reprend la palette du site. « parchemin » : fond blanc, brun encre et or (couleurs nouvelles, pour l'impression papier).
STYLES = {
    "nuit": {"fond": "#0c0a08", "texte": "#f2e9d8", "sourdine": "#b8ad99", "or": "#d9b45f", "titre": "#d9b45f", "filet": "#d2a64a", "pastille": "#2a2412", "grille": "#2c261e",
             "ombre": (0, 0, 0), "ombre_alpha": 0.5, "filigrane": 0.065, "embleme": (217, 180, 95)},
    "parchemin": {"fond": "#ffffff", "texte": "#2a2118", "sourdine": "#6d5d47", "or": "#8c6a1c", "titre": "#7a5a14", "filet": "#b08a37", "pastille": "#e6d6b0", "grille": "#d9c9a3",
                  "ombre": (0.35, 0.25, 0.1), "ombre_alpha": 0.35, "filigrane": 0.10, "embleme": (140, 106, 28)},
}


def date_longue(iso):
    d = date.fromisoformat(str(iso)[:10])
    return f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"


# Repères en mots, sans chiffre. Les seuils sont ceux du site (web/app.js : niveauCote, SEUILS_COTE, et le bloc « Offre d'occasion ») ; ils ne sont jamais affichés.
SEUILS_PRIX = (10, 20, 40, 70)
MOTS_PRIX = ("pas cher", "abordable", "moyen", "cher", "très cher")
LIBELLE_OFFRE, LIBELLE_PRIX = "En vente", "Prix d'occasion"          # titres des deux repères sur chaque fiche


NBSP = "\u00a0"
FOURCHETTES = ((f"moins de {SEUILS_PRIX[0]}{NBSP}€",) + tuple(f"{a} à {b}{NBSP}€" for a, b in zip(SEUILS_PRIX, SEUILS_PRIX[1:])) + (f"{SEUILS_PRIX[-1]}{NBSP}€ et plus",))          # échelle en euros, tirée des seuils


def niveau_prix(v):
    """1 à 5 selon la cote, comme le site pour les visiteurs ; None sans cote."""
    return None if v is None else 1 + sum(1 for x in SEUILS_PRIX if v >= x)


def mot_offre(n, neuf=False):
    """« Rareté en vente » : abondance des annonces en ligne à l'instant T. Les trois premiers niveaux suivent le bloc « Offre d'occasion » du site (aucune, une seule, quelques-unes) ;
    le site réunit « beaucoup » en un seul niveau : ici il est coupé en courant et abondant (seuil propre au guide, jamais affiché)."""
    if n == 0:
        return "disponible neuf" if neuf else "introuvable"
    return "rare" if n == 1 else "peu d'annonces" if n <= 3 else "courant" if n < 10 else "abondant"


MOIS_COURTS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def sortie_prevue(v, jour):
    """« 11 févr. 2027 » si le livre n'est pas encore sorti au jour donné (AAAA-MM-JJ), sinon None."""
    p = str(v.get("parution") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p) or p <= jour:
        return None
    a, m, j = p.split("-")
    return f"{int(j)} {MOIS_COURTS[int(m) - 1]} {a}"


def _numero(v):
    n = str(v.get("numero") or "")
    return int(n) if n.isdigit() else 10 ** 6


def _rang_version(v):
    """Tri naturel : V1, V2, … V10."""
    m = re.search(r"\d+", str(v))
    return (int(m.group()) if m else 10 ** 6, str(v))


# Éditeurs retenus tels que la base les donne ; toute autre valeur (auteur, texte copié d'une page, série) va dans « Autres éditeurs ».
EDITEURS_CONNUS = ("Gallimard", "Gallimard Jeunesse", "Alkonost", "Scriptarium", "Hachette", "Elder Craft", "Sarbacane", "Bragelonne")
AUTRES = "Autres éditeurs"


def editeur_de(v):
    e = (v.get("editeur") or "").strip()
    return e if e in EDITEURS_CONNUS else AUTRES


def grouper(versions, series=None, editeurs=None):
    """[(éditeur, [(version, [(série, [livres par numéro])])])] : éditeurs du plus fourni au moins fourni (« Autres éditeurs » en dernier),
    versions en ordre naturel, séries par ordre alphabétique. On ne mélange jamais deux versions. `series` et `editeurs` : filtres d'essai."""
    arbre = {}
    for v in versions:
        s = (v.get("serie") or "").strip() or "Hors série"
        e = editeur_de(v)
        if (series and s not in series) or (editeurs and e not in editeurs):
            continue
        arbre.setdefault(e, {}).setdefault(v.get("version") or "?", {}).setdefault(s, []).append(v)
    ordre = sorted(arbre, key=lambda e: (e == AUTRES, -sum(len(l) for par in arbre[e].values() for l in par.values()), e.casefold()))
    return [(e, [(ver, [(s, sorted(l, key=lambda v: (_numero(v), v.get("titre") or ""))) for s, l in sorted(arbre[e][ver].items(), key=lambda x: x[0].casefold())])
                 for ver in sorted(arbre[e], key=_rang_version)]) for e in ordre]


def polices(dossier):
    """Enregistre les polices ; renvoie (titre, titre gras, texte, texte gras)."""
    try:
        from fontTools.ttLib import TTFont as FT
        from fontTools.varLib import instancer
    except ImportError:
        return "Times-Roman", "Times-Bold", "Helvetica", "Helvetica-Bold"
    sortie = {}
    for fichier, nom, graisses in (("cormorant-garamond.woff2", "Cormorant", (500, 700)), ("source-sans-3.woff2", "SourceSans", (400, 700))):
        for g in graisses:
            f = Path(dossier) / f"{nom}-{g}.ttf"
            if not f.exists():
                police = instancer.instantiateVariableFont(FT(WEB / "fonts" / fichier), {"wght": g})
                police.flavor = None
                police.save(f)
            pdfmetrics.registerFont(TTFont(f"{nom}-{g}", str(f)))
            sortie[(nom, g)] = f"{nom}-{g}"
    pdfmetrics.registerFontFamily(sortie[("SourceSans", 400)], normal=sortie[("SourceSans", 400)], bold=sortie[("SourceSans", 700)], italic=sortie[("SourceSans", 400)], boldItalic=sortie[("SourceSans", 700)])
    return sortie[("Cormorant", 500)], sortie[("Cormorant", 700)], sortie[("SourceSans", 400)], sortie[("SourceSans", 700)]


def jaquette_jpeg(chemin):
    """Octets JPEG de la jaquette réduite, ou None si le fichier manque ou n'est pas lisible."""
    try:
        with Image.open(chemin) as im:
            im = im.convert("RGB")
            h = round(im.height * LARGEUR_JAQUETTE_PX / im.width)
            tampon = io.BytesIO()
            im.resize((LARGEUR_JAQUETTE_PX, h), Image.LANCZOS).save(tampon, "JPEG", quality=58, optimize=True, progressive=True)
            return tampon.getvalue()
    except (OSError, ValueError, TypeError):
        return None


_CACHE = {}


def embleme(rgb, alpha=1.0, px=512):
    """Le sceau du site recolorié : le doré devient `rgb`, le noir devient transparent, l'ensemble prend l'opacité `alpha` (filigrane à faible opacité, signature)."""
    cle = (rgb, alpha, px)
    if cle not in _CACHE:
        with Image.open(EMBLEME) as im:
            lum = ImageOps.autocontrast(im.convert("RGBA").resize((px, px), Image.LANCZOS).convert("L"), cutoff=1)
            masque = lum.point(lambda v: int(min(255, v * 1.15) * alpha))
            fond = Image.new("RGBA", (px, px), rgb + (0,))
            fond.putalpha(masque)
        tampon = io.BytesIO()
        fond.save(tampon, "PNG", optimize=True)
        _CACHE[cle] = tampon.getvalue()
    return ImageReader(io.BytesIO(_CACHE[cle]))


def visuel_ouverture(style, indice, largeur_px=900):
    """Détail recadré de l'illustration de couverture, teinté : page d'ouverture d'un éditeur."""
    cadres = ((0.72, 0.55, 0.56), (0.30, 0.74, 0.58), (0.28, 0.28, 0.58), (0.84, 0.36, 0.40))
    cx, cy, lf = cadres[indice % len(cadres)]
    with Image.open(COUVERTURE) as src:
        w, h = src.size
        cw = int(w * lf)
        ch = int(cw * H_PAGE / L_PAGE)
        x0 = min(max(0, int(w * cx - cw / 2)), w - cw)
        y0 = min(max(0, int(h * cy - ch / 2)), h - ch)
        im = src.convert("RGB").crop((x0, y0, x0 + cw, y0 + ch)).resize((largeur_px, round(largeur_px * H_PAGE / L_PAGE)), Image.LANCZOS)
    if style == "nuit":
        im = ImageEnhance.Brightness(im).enhance(0.62)
        voile = Image.new("RGB", im.size, (12, 10, 8))
        degrade = Image.linear_gradient("L").resize(im.size).point(lambda v: int(v * 0.85))          # plus sombre vers le bas
        im = Image.composite(voile, im, degrade)
    else:
        sepia = ImageOps.colorize(ImageOps.grayscale(im), (58, 42, 20), (243, 233, 210))
        im = Image.blend(im, sepia, 0.65)
        crème = Image.new("RGB", im.size, (243, 233, 210))
        im = Image.blend(im, crème, 0.35)
    tampon = io.BytesIO()
    im.save(tampon, "JPEG", quality=62, optimize=True, progressive=True)
    return ImageReader(io.BytesIO(tampon.getvalue()))


def _voile(img, px_mm, hauteur_mm, couleur, alpha, en_haut=False):
    """Voile dégradé : transparent côté image, `alpha` au bord de la page."""
    from PIL import Image as _I
    degrade = _I.linear_gradient("L")          # noir en haut, blanc en bas
    if en_haut:
        degrade = degrade.transpose(_I.FLIP_TOP_BOTTOM)
    masque = degrade.resize((img.width, round(hauteur_mm * px_mm))).point(lambda a: int((a / 255) ** 1.25 * 255 * alpha))
    img.paste(_I.new("RGB", masque.size, couleur), (0, 0 if en_haut else img.height - masque.height), masque)


def couverture_v1(largeur_px=1240, art_mm=210, bas_coupe_px=210, voiles=(), global_=None, decalage_mm=0):
    """Toile de la couverture V1 (A4 entière) : l'illustration est agrandie (rééchantillonnage Lanczos, accentuation légère), son bas (roche) est recoupé,
    et la toile est prolongée vers le haut par un fond flou tiré de l'illustration elle-même. `voiles` : [(hauteur en mm, couleur, opacité, en haut ?)] ;
    `global_` : (couleur, opacité) sur toute la page ; `decalage_mm` : décalage vertical de l'illustration (positif vers le bas)."""
    from PIL import ImageFilter
    px_mm = largeur_px / 210
    haut_px = round(297 * px_mm)
    with Image.open(COUVERTURE_V1) as src:
        art = src.convert("RGB").crop((0, 0, src.width, src.height - bas_coupe_px))
    f = art_mm * px_mm / art.width
    art = art.resize((round(art.width * f), round(art.height * f)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.2, percent=35, threshold=2))
    fond = art.resize((largeur_px, haut_px), Image.LANCZOS).filter(ImageFilter.GaussianBlur(55))
    fond = ImageEnhance.Brightness(fond).enhance(0.7)
    x, y = (largeur_px - art.width) // 2, haut_px - art.height + round(decalage_mm * px_mm)
    masque = Image.new("L", art.size, 255)
    bord = 38
    pixels = masque.load()
    for i in range(bord):          # fondu seulement sur le bord haut
        v = int(255 * i / bord)
        for k in range(art.width):
            pixels[k, i] = min(pixels[k, i], v)
    fond.paste(art, (x, y), masque)
    if global_:
        fond.paste(Image.new("RGB", fond.size, global_[0]), (0, 0), Image.new("L", fond.size, int(255 * global_[1])))
    for hauteur, couleur, alpha, en_haut in voiles:
        _voile(fond, px_mm, hauteur, couleur, alpha, en_haut)
    tampon = io.BytesIO()
    fond.save(tampon, "JPEG", quality=84, optimize=True, progressive=True)
    return ImageReader(io.BytesIO(tampon.getvalue()))


def fenetre_couverture(largeur_px=1500, ratio=515 / 400, haut_px=150):
    """Recadrage paysage de l'illustration (soleil, épée, dragon, torse du héros) pour la couverture en fenêtre."""
    with Image.open(COUVERTURE_V1) as src:
        h = round(src.width / ratio)
        coupe = src.convert("RGB").crop((0, haut_px, src.width, haut_px + h))
    coupe = coupe.resize((largeur_px, round(largeur_px / ratio)), Image.LANCZOS)
    tampon = io.BytesIO()
    coupe.save(tampon, "JPEG", quality=86, optimize=True)
    return ImageReader(io.BytesIO(tampon.getvalue()))


def lettres(c, x, y, texte, police, taille, espace=0.8, centre=False):
    """Petites capitales espacées : texte en capitales, légèrement aéré."""
    t = c.beginText()
    t.setFont(police, taille)
    t.setCharSpace(espace)
    texte = texte.upper()
    if centre:
        x -= (pdfmetrics.stringWidth(texte, police, taille) + espace * len(texte)) / 2
    t.setTextOrigin(x, y)
    t.textOut(texte)
    t.setCharSpace(0)
    c.drawText(t)


class Marqueur(Flowable):
    """Flowable invisible : note à quel éditeur et à quelle version appartient le contenu qui suit (pour l'en-tête, les onglets et la page d'ouverture)."""
    def __init__(self, etat, **valeurs):
        super().__init__()
        self.etat, self.valeurs = etat, valeurs

    def wrap(self, *_):
        return 0, 0.01

    def draw(self):
        self.etat.update({k: v for k, v in self.valeurs.items() if k != "niveau0"})
        if self.valeurs.get("version"):
            self.etat.setdefault("vus", []).append((self.valeurs["editeur"], self.valeurs["version"]))


class Ornement(Flowable):
    """Filet doré fin avec un petit losange au centre."""
    def __init__(self, largeur, couleur):
        super().__init__()
        self.largeur, self.couleur = largeur, couleur

    def wrap(self, *_):
        return self.largeur, 5 * mm

    def draw(self):
        c, m = self.canv, self.largeur / 2
        c.setStrokeColor(self.couleur)
        c.setFillColor(self.couleur)
        c.setLineWidth(0.5)
        c.line(0, 2.5 * mm, m - 4 * mm, 2.5 * mm)
        c.line(m + 4 * mm, 2.5 * mm, self.largeur, 2.5 * mm)
        c.saveState()
        c.translate(m, 2.5 * mm)
        c.rotate(45)
        c.rect(-1 * mm, -1 * mm, 2 * mm, 2 * mm, fill=1, stroke=0)
        c.restoreState()


class BandeauEditeur(Flowable):
    """Changement d'éditeur dans le flux : un bandeau pleine largeur (petit éditeur, sans page d'ouverture)."""
    def __init__(self, editeur, nb, st, polices):
        super().__init__()
        self.editeur, self.nb, self.st, self.pol = editeur, nb, st, polices

    def wrap(self, *_):
        return L_CADRE, 22 * mm

    def draw(self):
        c, st, (f_titre, f_titre_gras, f_texte, f_gras) = self.canv, self.st, self.pol
        c.setFillColor(HexColor(st["pastille"]))
        c.setStrokeColor(HexColor(st["filet"]))
        c.setLineWidth(0.5)
        c.rect(0, 2 * mm, L_CADRE, 18 * mm, fill=1, stroke=1)
        c.setFillColor(HexColor(st["sourdine"]))
        lettres(c, 5 * mm, 15 * mm, "Éditeur", f_gras, 7, 1.6)
        c.setFillColor(HexColor(st["titre"]))
        c.setFont(f_titre_gras, 26)
        c.drawString(5 * mm, 6.2 * mm, self.editeur)
        c.setFillColor(HexColor(st["sourdine"]))
        c.setFont(f_texte, 8)
        c.drawRightString(L_CADRE - 5 * mm, 7 * mm, f"{self.nb} édition{'s' if self.nb > 1 else ''}")


class TitreVersion(Flowable):
    """Changement de version dans le flux : l'éditeur en petites capitales, la version en grand, un filet."""
    def __init__(self, editeur, version, st, polices):
        super().__init__()
        self.editeur, self.version, self.st, self.pol = editeur, version, st, polices

    def getPlainText(self):
        return f"{self.editeur} · {self.version}"

    def wrap(self, *_):
        return L_CADRE, 17 * mm

    def draw(self):
        c, st, (f_titre, f_titre_gras, f_texte, f_gras) = self.canv, self.st, self.pol
        c.setFillColor(HexColor(st["sourdine"]))
        lettres(c, 0, 12.6 * mm, self.editeur, f_gras, 7.5, 1.4)
        c.setFillColor(HexColor(st["titre"]))
        c.setFont(f_titre_gras, 28)
        c.drawString(0, 3.6 * mm, self.version)
        c.setStrokeColor(HexColor(st["filet"]))
        c.setLineWidth(0.5)
        c.line(pdfmetrics.stringWidth(self.version, f_titre_gras, 28) + 5 * mm, 5.5 * mm, L_CADRE, 5.5 * mm)


class TeteSerie(Flowable):
    """En-tête d'une série : petites capitales dorées, filet fin, nombre d'éditions."""
    def __init__(self, nom, nb, st, polices):
        super().__init__()
        self.nom, self.nb, self.st, self.pol = nom, nb, st, polices

    def getPlainText(self):
        return self.nom

    def wrap(self, *_):
        return L_CADRE, 11 * mm

    def draw(self):
        c, st, (f_titre, f_titre_gras, f_texte, f_gras) = self.canv, self.st, self.pol
        c.setFillColor(HexColor(st["titre"]))
        c.setFont(f_titre_gras, 17)
        c.drawString(0, 4 * mm, self.nom)
        n = f"{self.nb} édition{'s' if self.nb > 1 else ''}"
        c.setFillColor(HexColor(st["sourdine"]))
        c.setFont(f_texte, 7.5)
        c.drawRightString(L_CADRE, 4.4 * mm, n)
        c.setStrokeColor(HexColor(st["filet"]))
        c.setLineWidth(0.4)
        c.line(0, 1.6 * mm, L_CADRE, 1.6 * mm)


CRAN, PAS_CRAN = 3 * mm, 3.4 * mm
LARGEUR_JAUGE = 4 * PAS_CRAN + CRAN


def jauge(c, x, y, niveau, st):
    """Jauge à cinq crans, bord haut en y : plus elle est pleine, plus c'est cher."""
    for k in range(5):
        c.setFillColor(HexColor(st["or"]) if niveau and k < niveau else HexColor(st["grille"]))
        c.setStrokeColor(HexColor(st["filet"]))
        c.setLineWidth(0.3)
        c.rect(x + k * PAS_CRAN, y - 2.4 * mm, CRAN, 2.4 * mm, fill=1, stroke=1)


def glyphe_zone(c, x, y, cote, zone, st):
    """Mini nuage : un carré à quatre cases (nombre d'annonces de gauche à droite, prix de bas en haut) dont la case de la zone est en or."""
    moitie = cote / 2
    for q in range(4):
        cx_, cy_ = x + (moitie if q in (1, 3) else 0), y + (moitie if q in (2, 3) else 0)
        c.setFillColor(HexColor(st["or"]) if q == zone else HexColor(st["grille"]))
        c.setStrokeColor(HexColor(st["filet"]))
        c.setLineWidth(0.3)
        c.rect(cx_, cy_, moitie, moitie, fill=1, stroke=1)


class Fiche(Flowable):
    """Un livre : jaquette avec ombre douce, titre, numéro, version, rareté, offre en vente, repères de prix par état (jauge à cinq crans ou mot). Aucun chiffre de cote."""
    def __init__(self, v, st, polices, web, offre=None, reperes="jauge", zone=None, jour=None):
        super().__init__()
        self.v, self.st, self.pol, self.web, self.reperes, self.zone = v, st, polices, web, reperes, zone          # zone : 0 à 3 (voir guide_analyse.quadrant), None sans repère
        self.largeur = L_CADRE / COLONNES
        self.iw = LARGEUR_JAQUETTE
        jpeg = jaquette_jpeg(web / v["couverture"]) if v.get("couverture") else None
        self.image = None
        self.ih = self.iw * 7 / 5
        if jpeg:
            with Image.open(io.BytesIO(jpeg)) as im:
                self.ih = self.iw * im.height / im.width
            self.image = ImageReader(io.BytesIO(jpeg))
        f_texte, f_gras = polices[2], polices[3]
        self.titre = Paragraph(v.get("titre") or "", ParagraphStyle("t", fontName=f_gras, fontSize=8, leading=9.4, textColor=HexColor(st["texte"]), alignment=TA_CENTER))
        self.th = max(self.titre.wrap(self.largeur - 3 * mm, 100 * mm)[1], 2 * 9.4)          # deux lignes réservées : les repères restent alignés d'un livre à l'autre
        num = f"n°\u00a0{v['numero']} · " if v.get("numero") and str(v["numero"]).strip("0") else ""
        self.meta = f"{num}{v.get('version') or ''}"
        self.offre = mot_offre(ga.nb_annonces((offre or {}).get(v.get("isbn13") or "")), v.get("en_vente") == 1)
        self.lib_offre, self.mot_prix = LIBELLE_OFFRE, "prix inconnu"
        self.niveau = niveau_prix(ga.cote(v)) if ga.cote(v) > 0 else None          # repère de prix : même état de référence que le site (très bon état, à défaut bon état) ; sans cote, pas de repère
        sortie = sortie_prevue(v, jour or date.today().isoformat())
        if sortie:          # livre annoncé, pas encore sorti : ni annonces ni prix
            self.lib_offre, self.offre, self.niveau, self.mot_prix = "Pas encore sorti", f"sortie : {sortie}", None, "pas encore de prix"

    def libelles(self):
        """Tous les textes dessinés dans la cellule (pour les tests : aucun montant, aucun état, aucun nombre décimal)."""
        return [self.v.get("titre") or "", self.meta, self.lib_offre, self.offre, LIBELLE_PRIX, MOTS_PRIX[self.niveau - 1] if self.niveau else self.mot_prix] + ([f"Zone {ga.NUM_ZONE[self.zone]}"] if self.zone is not None else [])

    def wrap(self, *_):
        self.h = self.ih + 3 * mm + self.th + 3.8 * mm + 7 * mm + 3.6 * mm + 8.4 * mm + 5.2 * mm + 2.5 * mm
        return self.largeur, self.h

    def draw(self):
        c, st, v = self.canv, self.st, self.v
        f_texte, f_gras = self.pol[2], self.pol[3]
        x0, y = (self.largeur - self.iw) / 2, self.h - self.ih
        r, g, b = st["ombre"]
        c.saveState()
        for dec, a in ((2.2, 0.10), (1.5, 0.14), (0.8, 0.2)):          # ombre douce sous la jaquette
            c.setFillColor(Color(r, g, b, alpha=a * st["ombre_alpha"] * 2))
            c.rect(x0 + dec * mm / 1.6, y - dec * mm / 1.6, self.iw, self.ih, fill=1, stroke=0)
        c.restoreState()
        if self.image:
            c.drawImage(self.image, x0, y, self.iw, self.ih)
        else:          # cadre de secours : le titre sur fond doré sombre
            c.setFillColor(HexColor(st["pastille"]))
            c.setStrokeColor(HexColor(st["filet"]))
            c.setLineWidth(0.6)
            c.rect(x0, y, self.iw, self.ih, fill=1, stroke=1)
            p = Paragraph(v.get("titre") or "", ParagraphStyle("s", fontName=self.pol[1], fontSize=9.5, leading=11.5, alignment=TA_CENTER, textColor=HexColor(st["titre"])))
            _, ph = p.wrap(self.iw - 6 * mm, self.ih)
            p.drawOn(c, x0 + 3 * mm, y + (self.ih - ph) / 2)
        y -= 3 * mm
        self.titre.drawOn(c, 1.5 * mm, y - self.th)
        y -= self.th + 3.4 * mm
        c.setFillColor(HexColor(st["sourdine"]))
        c.setFont(f_texte, 7)
        c.drawCentredString(self.largeur / 2, y, self.meta)
        y -= 3.4 * mm
        c.setFillColor(HexColor(st["sourdine"]))
        lettres(c, self.largeur / 2, y, self.lib_offre, f_texte, 5.4, 0.5, centre=True)
        y -= 3 * mm
        c.setFillColor(HexColor(st["titre"]))
        c.setFont(f_gras, 7.4)
        c.drawCentredString(self.largeur / 2, y, self.offre)
        y -= 3.4 * mm
        c.setFillColor(HexColor(st["sourdine"]))
        lettres(c, self.largeur / 2, y, LIBELLE_PRIX, f_texte, 5.4, 0.5, centre=True)
        y -= 1.4 * mm
        jauge(c, (self.largeur - LARGEUR_JAUGE) / 2, y, self.niveau, st)
        self.reperes_y = {"titre": self.h - self.ih - 3 * mm - self.th / 2, "offre": y + 4.4 * mm, "prix": y - 1.2 * mm, "zone": y - 10 * mm}          # positions des repères (légende annotée)
        c.setFillColor(HexColor(st["texte"]))
        c.setFont(f_gras, 7.2)
        c.drawCentredString(self.largeur / 2, y - 6.4 * mm, MOTS_PRIX[self.niveau - 1] if self.niveau else self.mot_prix)
        if self.zone is not None:          # où se situe le livre sur le nuage de points : petit carré à quatre cases, la sienne en or, et son numéro
            n = ga.NUM_ZONE[self.zone]
            tw = pdfmetrics.stringWidth(f"Zone {n}", f_gras, 6.6)
            gx0, gy0 = (self.largeur - (4 * mm + 1.6 * mm + tw)) / 2, y - 6.4 * mm - 5.8 * mm
            glyphe_zone(c, gx0, gy0, 4 * mm, self.zone, st)
            c.setFillColor(HexColor(st["titre"]))
            c.setFont(f_gras, 6.6)
            c.drawString(gx0 + 5.6 * mm, gy0 + 1.2 * mm, f"Zone {n}")
            self.reperes_y["zone"] = gy0 + 2 * mm


INTRO_TAILLE = 15.0          # corps de l'introduction (points) : à réduire si le texte dépasse deux pages
INTRODUCTION = Path(__file__).resolve().parent / "guide" / "introduction.md"


def _inline(t):
    t = re.sub(r" ([:;!?»])", "\u00a0\\1", t.replace("« ", "«\u00a0"))          # espaces insécables avant « : ; ! ? » » et après « « »
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t.replace("&", "&amp;").replace("<", "&lt;"))


def introduction(texte, variables, styles, st, pol):
    """Introduction lue dans pipeline/guide/introduction.md : « # titre », « *exergue* », « ## intertitre », « - puce », paragraphes ; {variables} remplies ; capitale d'ouverture."""
    f_titre, f_titre_gras, f_texte, f_gras = pol
    for k, v in variables.items():
        texte = texte.replace("{" + k + "}", str(v))
    sortie, premier = [], True
    for bloc in re.split(r"\n\s*\n", texte.strip()):
        lignes = [l for l in bloc.strip().split("\n") if l.strip()]
        if not lignes:
            continue
        t = " ".join(l.strip() for l in lignes)
        if t.startswith("# "):
            sortie += [Paragraph(_inline(t[2:]), styles["h1i"]), Ornement(40 * mm, HexColor(st["filet"])), Spacer(1, 6 * mm)]
        elif t.startswith("## "):
            sortie.append(Paragraph(_inline(t[3:]), styles["h2"]))
        elif t.startswith("*") and t.endswith("*") and not t.startswith("**"):
            sortie += [Paragraph(_inline(t.strip("*")), styles["exergue"]), Spacer(1, 6 * mm)]
        elif lignes[0].lstrip().startswith("- "):
            for l in lignes:
                sortie.append(Paragraph(_inline(l.strip()[2:]), styles["puce"], bulletText="•"))
            sortie.append(Spacer(1, 2 * mm))
        elif premier:
            premier = False
            sortie.append(Paragraph(f'<font name="{f_titre_gras}" size="40" color="{st["titre"]}">{_inline(t[0])}</font>{_inline(t[1:])}', styles["corps_initiale"]))
        else:
            sortie.append(Paragraph(_inline(t), styles["corps_intro"]))
    return sortie


OFFRE_SENS = (("abondant", "Beaucoup d'annonces : facile à trouver."), ("courant", "Plusieurs annonces : on le trouve sans difficulté."),
              ("peu d'annonces", "Quelques annonces seulement : il faut surveiller."), ("rare", "Une seule annonce en ce moment."),
              ("introuvable", "Aucune annonce aujourd'hui."), ("disponible neuf", "Encore vendu neuf."), ("pas encore sorti", "Annoncé : la fiche donne sa date de sortie prévue."))
PRIX_SENS = ("Se trouve à petit prix.", "Un prix doux, à la portée de tous.", "Un prix courant pour un livre de collection.", "Un exemplaire recherché.", "Un livre très recherché, parmi les plus chers.")


class FicheAnnotee(Flowable):
    """Une vraie fiche, avec une flèche et une phrase pour chaque repère."""
    def __init__(self, fiche, st, polices):
        super().__init__()
        self.fiche, self.st, self.pol = fiche, st, polices

    def wrap(self, *_):
        self.fiche.wrap()
        return L_CADRE, self.fiche.h

    def draw(self):
        c, st, f = self.canv, self.st, self.fiche
        f.canv = c
        f.draw()
        c.setStrokeColor(HexColor(st["filet"]))
        c.setFillColor(HexColor(st["texte"]))
        c.setLineWidth(0.4)
        for cle, texte in (("titre", "Titre, numéro de l'éditeur (pas celui du tome) et version."), ("offre", "En vente : combien d'annonces en ligne aujourd'hui."), ("prix", "Prix d'occasion : de 1 cran (pas cher) à 5 crans (très cher)."), ("zone", "Zone : où se situe le livre sur le nuage de points (zones 1 à 4).")):
            y = f.reperes_y[cle]
            c.line(f.largeur - 4 * mm, y, 56 * mm, y)
            c.setFont(self.pol[2], 9.5)
            c.drawString(58 * mm, y - 1.2 * mm, texte)


class TableauNiveaux(Flowable):
    """Une ligne par niveau : jauge (prix) ou rien (en vente), mot en gras, phrase courte."""
    def __init__(self, lignes, st, polices, jauges=False):
        super().__init__()
        self.lignes, self.st, self.pol, self.jauges = lignes, st, polices, jauges

    def wrap(self, *_):
        return L_CADRE, len(self.lignes) * 6.7 * mm + 2 * mm

    def draw(self):
        c, st = self.canv, self.st
        y = len(self.lignes) * 6.7 * mm
        for k, (mot, phrase, *fourchette) in enumerate(self.lignes, 1):
            if self.jauges:
                jauge(c, 0, y - 1.2 * mm, k, st)
            c.setFillColor(HexColor(st["titre"]))
            c.setFont(self.pol[3], 10)
            c.drawString(24 * mm if self.jauges else 0, y - 4 * mm, mot)
            c.setFillColor(HexColor(st["texte"]))
            if fourchette:
                c.setFont(self.pol[3], 10)
                c.drawString(52 * mm, y - 4 * mm, fourchette[0])
            c.setFont(self.pol[2], 10)
            c.drawString(86 * mm if fourchette else 56 * mm, y - 4 * mm, phrase)
            y -= 6.7 * mm


def legende(styles, st=None, polices=None, exemple=None):
    """Page de légende : une fiche annotée, puis chaque mot des repères avec sa phrase ; l'échelle des prix donne la fourchette en euros de chaque niveau."""
    P = lambda t, k="corps": Paragraph(t, styles[k])  # noqa: E731
    haut = []
    if exemple is not None:
        exemple.offre, exemple.niveau, exemple.zone = "courant", 3, 3
        haut = [P("Lire une fiche", "h2"), FicheAnnotee(exemple, st, polices), Spacer(1, 3 * mm)]
    return haut + [P("En vente", "h2"), P("L'abondance des annonces en ligne au moment du guide."), TableauNiveaux(OFFRE_SENS, st, polices) if st else Spacer(1, 1),
                   P("Prix d'occasion", "h2"), P("Le niveau de prix d'un exemplaire, d'après les cotes et les annonces : plus la jauge est pleine, plus il est cher. Sans cote, la fiche dit « prix inconnu »."),
                   TableauNiveaux(tuple(zip(MOTS_PRIX, PRIX_SENS, FOURCHETTES)), st, polices, jauges=True) if st else Spacer(1, 1)]


def construire(versions, sortie, date_cotes, series=None, web=WEB, genere_le=None, editeurs=None, donnees=None, sous_titre=SOUS_TITRE_PAR_DEFAUT, style=STYLE_PAR_DEFAUT, mention=False, visuel=COUVERTURE_PAR_DEFAUT, reperes="jauge", meta=None, introduction_md=None):
    """Écrit le PDF. Renvoie le nombre de livres."""
    st = STYLES[style]
    genere_le = genere_le or date.today().isoformat()
    groupes = grouper(versions, series, editeurs)
    pol = polices(tempfile.mkdtemp(prefix="guide-polices-"))
    f_titre, f_titre_gras, f_texte, f_gras = pol
    C = lambda k: HexColor(st[k])  # noqa: E731
    etat = {"editeur": None, "version": None, "versions": [], "index": 0, "nb": 0, "nv": 0, "debut": (None, None), "vus": []}
    styles = {
        "corps": ParagraphStyle("corps", fontName=f_texte, fontSize=10.5, leading=15.5, textColor=C("texte")),
        "h1": ParagraphStyle("h1", fontName=f_titre_gras, fontSize=30, leading=34, textColor=C("titre"), spaceAfter=7 * mm),
        "h1m": ParagraphStyle("h1m", fontName=f_titre_gras, fontSize=30, leading=34, textColor=C("titre"), spaceAfter=6 * mm),
        "h2": ParagraphStyle("h2", fontName=f_titre_gras, fontSize=17, leading=20, textColor=C("titre"), spaceBefore=5 * mm, spaceAfter=2 * mm, keepWithNext=1),
        "toc": ParagraphStyle("toc", fontName=f_texte, fontSize=10, leading=14, textColor=C("texte")),
        "h1i": ParagraphStyle("h1i", fontName=f_titre_gras, fontSize=34, leading=38, textColor=C("titre"), spaceAfter=3 * mm),
        "exergue": ParagraphStyle("exergue", fontName=f_titre, fontSize=19, leading=25, textColor=C("or"), alignment=TA_CENTER, leftIndent=14 * mm, rightIndent=14 * mm),
        "corps_intro": ParagraphStyle("corps_intro", fontName=f_texte, fontSize=INTRO_TAILLE, leading=INTRO_TAILLE * 1.62, textColor=C("texte"), spaceAfter=4 * mm, leftIndent=8 * mm, rightIndent=8 * mm),
        "puce_radar": ParagraphStyle("puce_radar", fontName=f_texte, fontSize=10.5, leading=15, textColor=C("texte"), leftIndent=5 * mm, bulletIndent=0, spaceAfter=1.4 * mm),
        "puce": ParagraphStyle("puce", fontName=f_texte, fontSize=INTRO_TAILLE, leading=INTRO_TAILLE * 1.62, textColor=C("texte"), leftIndent=15 * mm, rightIndent=8 * mm, bulletIndent=9 * mm, spaceAfter=2 * mm),
    }
    styles["corps_initiale"] = ParagraphStyle("corps_initiale", parent=styles["corps_intro"], autoLeading="max")

    def signature(c, y=10 * mm):
        c.drawImage(embleme(st["embleme"], 1.0, 128), MARGE_X, y - 1.6 * mm, 5.2 * mm, 5.2 * mm, mask="auto")
        c.setFillColor(C("sourdine"))
        c.setFont(f_texte, 7.6)
        c.drawString(MARGE_X + 7 * mm, y, f"La Cote du Héros · {SITE} · repères du {date_longue(date_cotes)}")
        c.linkURL(LIEN_SITE, (MARGE_X, y - 2 * mm, MARGE_X + 80 * mm, y + 4 * mm), relative=0)

    def fond(c, doc):
        c.setFillColor(C("fond"))
        c.rect(0, 0, L_PAGE, H_PAGE, fill=1, stroke=0)
        c.drawImage(embleme(st["embleme"], st["filigrane"], 512), L_PAGE * 0.5 - 62 * mm, H_PAGE * 0.40 - 62 * mm, 124 * mm, 124 * mm, mask="auto")          # filigrane très discret
        if style == "parchemin":
            c.setStrokeColor(C("grille"))
            c.setLineWidth(0.6)
            c.rect(6 * mm, 6 * mm, L_PAGE - 12 * mm, H_PAGE - 12 * mm, fill=0, stroke=1)

    def pied(c, doc, entete=True):
        c.setStrokeColor(C("filet"))
        c.setLineWidth(0.4)
        c.line(MARGE_X, 14.5 * mm, L_PAGE - MARGE_X, 14.5 * mm)
        signature(c)
        c.setFillColor(C("sourdine"))
        lettres(c, L_PAGE - MARGE_X - pdfmetrics.stringWidth(str(doc.page), f_gras, 8) - 9 * mm, 10 * mm, "page", f_texte, 6.5, 1)
        c.setFont(f_gras, 8)
        c.drawRightString(L_PAGE - MARGE_X, 10 * mm, str(doc.page))
        if mention:
            c.setFillColor(C("sourdine"))
            lettres(c, L_PAGE / 2, 17.5 * mm, "Document réservé aux sorciers de La Cote du Héros · ne pas diffuser", f_texte, 6.2, 0.5, centre=True)

    def debut_page(c, doc):
        etat["debut"] = (etat.get("editeur"), etat.get("version"))          # ce que la page continue ; les marqueurs de la page s'ajoutent à « vus »
        etat["vus"] = []
        fond(c, doc)

    def page_texte(c, doc):
        pied(c, doc)

    def page_catalogue(c, doc):
        pied(c, doc)
        eds = []
        for e, v in ([etat["debut"]] if etat["debut"][0] else []) + etat["vus"]:
            if not eds or eds[-1][0] != e:
                eds.append([e, []])
            if v and v not in eds[-1][1]:
                eds[-1][1].append(v)
        c.setFillColor(C("sourdine"))
        lettres(c, MARGE_X, H_PAGE - 12 * mm, " / ".join(f"{e} · {' · '.join(vs)}" for e, vs in eds), f_gras, 7.5, 1.2)
        c.setFont(f_texte, 7)
        c.drawRightString(L_PAGE - MARGE_X, H_PAGE - 12 * mm, "La Cote du Héros")
        c.setStrokeColor(C("filet"))
        c.setLineWidth(0.4)
        c.line(MARGE_X, H_PAGE - 14.5 * mm, L_PAGE - MARGE_X, H_PAGE - 14.5 * mm)
        actifs = eds[-1][1] if eds else []
        for k, ver in enumerate(etat["versions"]):          # onglets de version sur le bord de la page
            actif = ver in actifs
            ty = H_PAGE - 40 * mm - k * 24 * mm
            c.setFillColor(C("or") if actif else C("pastille"))
            c.setStrokeColor(C("filet"))
            c.setLineWidth(0.5)
            c.roundRect(L_PAGE - 6.5 * mm, ty, 9 * mm, 20 * mm, 2 * mm, fill=1, stroke=1)
            c.saveState()
            c.translate(L_PAGE - 2.6 * mm, ty + 10 * mm)
            c.rotate(90)
            c.setFillColor(C("fond") if actif else C("sourdine"))
            c.setFont(f_gras, 8.5)
            c.drawCentredString(0, -3 * mm, ver)
            c.restoreState()

    def page_ouverture(c, doc):
        c.drawImage(visuel_ouverture(style, etat["index"]), 0, 0, L_PAGE, H_PAGE)
        c.setStrokeColor(C("filet"))
        c.setLineWidth(0.7)
        c.rect(9 * mm, 9 * mm, L_PAGE - 18 * mm, H_PAGE - 18 * mm, fill=0, stroke=1)
        c.setLineWidth(0.3)
        c.rect(11 * mm, 11 * mm, L_PAGE - 22 * mm, H_PAGE - 22 * mm, fill=0, stroke=1)
        c.drawImage(embleme(st["embleme"], 1.0, 256), L_PAGE / 2 - 11 * mm, H_PAGE - 52 * mm, 22 * mm, 22 * mm, mask="auto")
        if style == "parchemin":          # bandeau crème sous le titre : lisible sur l'image
            c.saveState()
            c.setFillColor(C("fond"), alpha=0.82)
            c.rect(11 * mm, H_PAGE * 0.52 - 48 * mm, L_PAGE - 22 * mm, 64 * mm, fill=1, stroke=0)
            c.restoreState()
        c.setFillColor(C("or"))
        lettres(c, L_PAGE / 2, H_PAGE * 0.52, "Éditeur", f_gras, 11, 3, centre=True)
        c.setFillColor(C("titre") if style == "parchemin" else C("or"))
        taille = 54 if len(etat["editeur"]) < 14 else 40
        c.setFont(f_titre_gras, taille)
        c.drawCentredString(L_PAGE / 2, H_PAGE * 0.52 - 22 * mm, etat["editeur"])
        c.setStrokeColor(C("filet"))
        c.setLineWidth(0.6)
        c.line(L_PAGE / 2 - 30 * mm, H_PAGE * 0.52 - 30 * mm, L_PAGE / 2 + 30 * mm, H_PAGE * 0.52 - 30 * mm)
        c.setFillColor(C("texte"))
        c.setFont(f_texte, 11)
        c.drawCentredString(L_PAGE / 2, H_PAGE * 0.52 - 40 * mm, f"{etat['nb']} édition{'s' if etat['nb'] > 1 else ''} · {etat['nv']} version{'s' if etat['nv'] > 1 else ''}")
        if style == "parchemin":
            c.saveState()
            c.setFillColor(C("fond"), alpha=0.82)
            c.rect(11 * mm, 14 * mm, L_PAGE - 22 * mm, 12 * mm, fill=1, stroke=0)
            c.restoreState()
        c.setFillColor(C("texte") if style == "parchemin" else C("or"))
        lettres(c, L_PAGE / 2, 19 * mm, f"La Cote du Héros · {SITE}", f_gras, 8, 1.5, centre=True)

    def largeur_lettres(texte, police, taille, espace):
        return pdfmetrics.stringWidth(texte.upper(), police, taille) + espace * len(texte)

    def ombre_texte(c, x, y, texte, police, taille, espace, dy=1.5, alpha=0.5):
        c.setFillColor(HexColor("#000000"), alpha=alpha)
        lettres(c, x + dy * 0.6, y - dy, texte, police, taille, espace, centre=True)

    def losange(c, x, y, r=3.2):
        t = c.beginPath()
        t.moveTo(x, y + r); t.lineTo(x + r * 0.8, y); t.lineTo(x, y - r); t.lineTo(x - r * 0.8, y); t.close()
        c.drawPath(t, fill=1, stroke=0)

    def pied_lien(c, texte, x_droite, y, couleur, taille=9):
        c.setFillColor(HexColor(couleur))
        c.setFont(f_texte, taille)
        c.drawRightString(x_droite, y, texte)
        c.linkURL(LIEN_SITE, (x_droite - pdfmetrics.stringWidth(texte, f_texte, taille), y - 3, x_droite, y + taille), relative=0)

    def couverture_a(c):
        """Piste A : revue de collection. Illustration plein cadre, voiles sombres haut et bas, titre doré sur une ligne, accroches en bas à gauche."""
        c.drawImage(couverture_v1(art_mm=210, voiles=[(81, (20, 16, 31), 0.90, True), (128, (20, 16, 31), 0.95, False)]), 0, 0, L_PAGE, H_PAGE)
        titre, espace = "La Cote du Héros", 2.0
        taille = 46 * min(1.0, 515 / largeur_lettres(titre, f_titre_gras, 46, espace))
        ombre_texte(c, L_PAGE / 2, 770, titre, f_titre_gras, taille, espace)
        c.setFillColor(HexColor("#e8c766"))
        lettres(c, L_PAGE / 2, 770, titre, f_titre_gras, taille, espace, centre=True)
        c.setStrokeColor(HexColor("#e8c766"))
        c.setLineWidth(0.6)
        c.line(40, 756, L_PAGE - 40, 756)
        c.setFillColor(HexColor("#f4ecd8"))
        lettres(c, L_PAGE / 2, 738, "Le guide de référence des livres dont vous êtes le héros", f_texte, 11.5, 1.5, centre=True)
        accroches = ("Chaque livre, chaque édition, avec sa jaquette", "Rareté, niveau de prix et zone de 1 à 4", "Finir une série, retrouver les livres de son enfance", "Les quatre zones du marché, expliquées")
        for i, t in enumerate(accroches):
            y = 190 - 24 * i
            c.setFillColor(HexColor("#e8c766"))
            losange(c, 46, y + 4)
            c.setFillColor(HexColor("#f4ecd8"))
            c.setFont(f_gras, 12.5)
            c.drawString(58, y, t)
        c.setFillColor(HexColor("#f4ecd8"))
        c.setFont(f_titre, 16)
        c.drawString(40, 45, "Olivier Bertrand")
        pied_lien(c, f"{SITE} · Édition du {date_longue(genere_le)}", L_PAGE - 40, 45, "#bfb59a")

    def couverture_b(c):
        """Piste B : affiche d'aventure. Illustration plus serrée sous un voile violet, phrase d'affiche en haut, « HÉROS » très grand en bas, générique."""
        c.drawImage(couverture_v1(art_mm=226, global_=((26, 15, 46), 0.35), voiles=[(99, (11, 7, 20), 0.95, False)]), 0, 0, L_PAGE, H_PAGE)
        c.setFillColor(HexColor("#f4ecd8"))
        phrase = "Le guide de ceux qui collectionnent les livres dont vous êtes le héros."
        taille_phrase = min(17.0, 17.0 * 500 / pdfmetrics.stringWidth(phrase, f_titre, 17))          # tient dans la largeur de la page
        c.setFont(f_titre, taille_phrase)
        c.drawCentredString(L_PAGE / 2, 800, phrase)
        c.setFillColor(HexColor("#f4ecd8"))
        lettres(c, L_PAGE / 2, 262, "La Cote du", f_gras, 18, 9, centre=True)
        mot, taille = "HÉROS", 118.0
        taille *= min(1.0, 470 / pdfmetrics.stringWidth(mot, f_titre_gras, taille))
        x = (L_PAGE - pdfmetrics.stringWidth(mot, f_titre_gras, taille)) / 2
        y, haut = 160, 0.98 * taille          # le dégradé couvre aussi l'accent de « É »

        def texte(mode, dx=0, dy=0):
            t = c.beginText()
            t.setFont(f_titre_gras, taille)
            t.setTextRenderMode(mode)
            t.setTextOrigin(x + dx, y + dy)
            t.textOut(mot)
            c.drawText(t)
        for k, a in ((6, 0.15), (4, 0.2), (2.5, 0.3)):          # ombre portée
            c.saveState(); c.setFillColor(HexColor("#000000"), alpha=a); texte(0, 0, -k); c.restoreState()
        c.saveState()
        texte(7)          # le texte sert de découpe au dégradé or
        c.linearGradient(0, y + haut, 0, y, (HexColor("#f7e08a"), HexColor("#b98a2b")), (0, 1), extend=False)
        c.restoreState()
        c.saveState(); c.setStrokeColor(HexColor("#2a1a05")); c.setLineWidth(1.0); texte(1); c.restoreState()
        c.setFillColor(HexColor("#f4ecd8"))
        c.setFont(f_texte, 12)
        c.drawCentredString(L_PAGE / 2, 120, "La cote d'occasion de tous les livres dont vous êtes le héros")
        c.setFillColor(HexColor("#e8c766"))
        lettres(c, L_PAGE / 2, 95, "Éditions V1, V2… · Jaquettes · Rareté et prix · Zones 1 à 4", f_gras, 9.5, 1.0, centre=True)
        c.setFillColor(HexColor("#f4ecd8"))
        lettres(c, L_PAGE / 2, 50, "Un guide d'Olivier Bertrand", f_texte, 10, 3, centre=True)
        c.setFillColor(HexColor("#bfb59a"))
        c.setFont(f_texte, 8.5)
        c.drawCentredString(L_PAGE / 2, 36, f"{SITE} · {date_longue(genere_le)}")
        c.linkURL(LIEN_SITE, (L_PAGE / 2 - 60, 33, L_PAGE / 2 - 8, 45), relative=0)

    def couverture_c(c):
        """Piste C : ouvrage de référence. Fond ivoire, illustration en fenêtre, titre foncé, deux lignes d'accroche."""
        c.setFillColor(HexColor("#f3eee2"))
        c.rect(0, 0, L_PAGE, H_PAGE, fill=1, stroke=0)
        c.drawImage(fenetre_couverture(), 40, 380, 515, 400)
        c.setStrokeColor(HexColor("#a9842f"))
        c.setLineWidth(0.75)
        c.rect(46, 386, 503, 388, fill=0, stroke=1)
        titre = "La Cote du Héros"
        taille = 46 * min(1.0, 515 / pdfmetrics.stringWidth(titre, f_titre_gras, 46))
        c.setFillColor(HexColor("#1b1a17"))
        c.setFont(f_titre_gras, taille)
        c.drawCentredString(L_PAGE / 2, 320, titre)
        c.setStrokeColor(HexColor("#a9842f"))
        c.setLineWidth(0.6)
        c.line(L_PAGE / 2 - 20, 303, L_PAGE / 2 - 5, 303); c.line(L_PAGE / 2 + 5, 303, L_PAGE / 2 + 20, 303)
        c.setFillColor(HexColor("#a9842f"))
        losange(c, L_PAGE / 2, 303, 2.6)
        c.setFillColor(HexColor("#4a4336"))
        c.setFont(f_titre, 19)
        c.drawCentredString(L_PAGE / 2, 262, "Guide de référence des livres-jeux")
        c.setFillColor(HexColor("#7a705c"))
        lettres(c, L_PAGE / 2, 240, "Éditions, séries, raretés et niveaux de prix", f_texte, 10.5, 1.5, centre=True)
        c.setFillColor(HexColor("#4a4336"))
        c.setFont(f_texte, 11)
        c.drawCentredString(L_PAGE / 2, 205, "Tous les livres classés par éditeur, édition et série, avec leurs jaquettes")
        c.drawCentredString(L_PAGE / 2, 189, "Une page de méthode, quatre zones expliquées, la stratégie du collectionneur")
        c.setStrokeColor(HexColor("#a9842f"))
        c.setLineWidth(0.5)
        c.line(L_PAGE / 2 - 30, 112, L_PAGE / 2 + 30, 112)
        c.setFillColor(HexColor("#1b1a17"))
        lettres(c, L_PAGE / 2, 90, "Olivier Bertrand", f_gras, 12, 3, centre=True)
        pied_lien_centre = f"{SITE} · Édition du {date_longue(genere_le)}"
        pied_lien(c, pied_lien_centre, L_PAGE / 2 + pdfmetrics.stringWidth(pied_lien_centre, f_texte, 9) / 2, 60, "#7a705c")

    def couverture_v1_page(c, doc):
        {"a": couverture_a, "b": couverture_b, "c": couverture_c}[COUVERTURE_STYLE](c)

    def couverture(c, doc):
        if visuel == "v1":
            return couverture_v1_page(c, doc)
        c.drawImage(str(COUVERTURE), 0, 0, L_PAGE, H_PAGE)
        c.drawImage(embleme((217, 180, 95), 1.0, 256), L_PAGE / 2 - 10 * mm, 33 * mm, 20 * mm, 20 * mm, mask="auto")          # sceau du site sous l'illustration, sans la masquer
        if sous_titre == "bandeau":
            c.saveState()
            c.setFillColor(HexColor("#0c0a08"), alpha=0.72)
            c.rect(0, H_PAGE - 70 * mm, L_PAGE, 13 * mm, fill=1, stroke=0)
            c.restoreState()
        for decalage, couleur in ((0.6 * mm, HexColor("#0c0a08")), (0, HexColor("#d9b45f"))):          # ombre sombre sous le texte doré : lisible sur l'illustration
            c.setFillColor(couleur)
            c.setFont(f_titre_gras, 54)
            c.drawCentredString(L_PAGE / 2 + decalage, H_PAGE - 48 * mm - decalage, "La Cote du Héros")
            if sous_titre == "clair":
                for dx, dy in ((0.9 * mm, -0.9 * mm), (-0.9 * mm, -0.9 * mm), (0, -1.2 * mm)) if decalage else ((0, 0),):
                    c.setFont(f_gras, 22)
                    c.drawCentredString(L_PAGE / 2 + dx, H_PAGE - 63 * mm + dy, "Guide de référence")
            else:
                c.setFont(f_titre_gras, 26)
                c.drawCentredString(L_PAGE / 2 + decalage, H_PAGE - 63 * mm - decalage, "Guide de référence")
            c.setFont(f_gras, 11)
            c.drawCentredString(L_PAGE / 2 + decalage, 26 * mm - decalage, SITE)
            c.setFont(f_gras, 12)
            c.drawCentredString(L_PAGE / 2 + decalage, 19 * mm - decalage, f"Édition du {date_longue(genere_le)}")
        c.linkURL(LIEN_SITE, (L_PAGE / 2 - 25 * mm, 24 * mm, L_PAGE / 2 + 25 * mm, 30 * mm), relative=0)

    remplissage = {}

    class Doc(BaseDocTemplate):
        def handle_documentBegin(self):
            etat.update({"editeur": None, "version": None, "versions": [], "index": 0, "nb": 0, "nv": 0, "debut": (None, None), "vus": []})          # chaque passage de construction repart de zéro
            super().handle_documentBegin()

        def afterFlowable(self, f):
            if isinstance(f, TitreVersion):
                self.notify("TOCEntry", (1, f.getPlainText(), self.page))
            elif isinstance(f, TeteSerie):
                self.notify("TOCEntry", (2, f.getPlainText(), self.page))
            elif isinstance(f, Marqueur) and f.valeurs.get("niveau0"):
                self.notify("TOCEntry", (0, f.valeurs["niveau0"], self.page))
            elif isinstance(f, Paragraph) and f.style.name in ("h1m", "h1i"):
                self.notify("TOCEntry", (0, f.getPlainText(), self.page))

        def afterPage(self):
            if self.pageTemplate.id == "catalogue":          # taux de remplissage de la page (hauteur utilisée sur hauteur utile)
                fr = self.frame
                remplissage[self.page] = max(0.0, min(1.0, (fr._y1 + fr._height - fr._y) / fr._height))

    doc = Doc(str(sortie), pagesize=A4, leftMargin=MARGE_X, rightMargin=MARGE_X, topMargin=HAUT, bottomMargin=BAS,
              title="La Cote du Héros · Guide de référence", author="La Cote du Héros", subject="Cotes et jaquettes des livres dont vous êtes le héros, par éditeur et par édition",
              keywords="livres dont vous êtes le héros, livre-jeu, cote, jaquettes, lacoteduheros.fr", creator="La Cote du Héros")
    cadre = Frame(MARGE_X, BAS, L_CADRE, H_PAGE - HAUT - BAS, id="c", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate("couv", [Frame(0, 0, L_PAGE, H_PAGE, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=couverture, autoNextPageTemplate="texte"),
        PageTemplate("texte", [Frame(MARGE_X, BAS, L_CADRE, H_PAGE - 24 * mm - BAS, id="t")], onPage=debut_page, onPageEnd=page_texte),
        PageTemplate("ouverture", [Frame(0, 0, L_PAGE, H_PAGE, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=lambda c, d: None, onPageEnd=page_ouverture),
        PageTemplate("catalogue", [cadre], onPage=debut_page, onPageEnd=page_catalogue)])
    sommaire = TableOfContents()
    sommaire.levelStyles = [ParagraphStyle("t0", parent=styles["toc"], fontName=f_gras, spaceBefore=2.5 * mm, textColor=C("titre")), ParagraphStyle("t1", parent=styles["toc"], leftIndent=6 * mm, fontSize=9.5, leading=13),
                            ParagraphStyle("t2", parent=styles["toc"], leftIndent=12 * mm, fontSize=8.5, leading=11.5, textColor=C("sourdine"))]
    sommaire.dotsMinLevel = 0
    nb = sum(len(l) for _, vs in groupes for _, ss in vs for _, l in ss)
    donnees_offre = donnees if isinstance(donnees, dict) else ga.charger()
    offre_annonces = donnees_offre.get("offre", {})
    meta = meta or {}
    variables = {"nb_editions": meta.get("nb_versions") or nb, "nb_livres": meta.get("nb_livres") or len({v.get("livre_id") for v in versions}), "nb_series": meta.get("nb_series") or len({v.get("serie") for v in versions}), "date": date_longue(date_cotes)}
    texte_intro = introduction_md if introduction_md is not None else INTRODUCTION.read_text(encoding="utf-8")
    candidats = [v for v in versions if v.get("couverture") and (web / v["couverture"]).exists() and ga.cote(v)]
    exemple = Fiche(candidats[0] if candidats else versions[0], st, pol, web, {}, reperes) if versions else None
    donnees_zones = donnees if isinstance(donnees, dict) else (ga.charger() if donnees is None else None)
    pts_zones = ga.points_editions(versions, donnees_zones["offre"]) if donnees_zones else []
    med_o, med_c = (statistics.median(n for n, _ in pts_zones), statistics.median(p for _, p in pts_zones)) if pts_zones else (None, None)          # médianes de tout le guide : les deux pointillés du nuage

    def zone_de(v):
        c_ = ga.cote(v)
        if med_o is None or not v.get("isbn13") or c_ <= 0:
            return None
        return ga.quadrant(ga.nb_annonces(donnees_zones["offre"].get(v["isbn13"])), c_, med_o, med_c)
    histoire = [Spacer(1, 1), NextPageTemplate("texte"), PageBreak()] + introduction(texte_intro, variables, styles, st, pol) + [
        ] + (page_nuage(versions, donnees if donnees is not None else ga.charger(), styles, pol, st) if donnees is not False else []) + [PageBreak(), Paragraph("La feuille d'aventure", styles["h1m"]), Ornement(40 * mm, HexColor(st["filet"])), Spacer(1, 1 * mm)] + legende(styles, st, pol, exemple) + (page_strategie(styles, {"filet": HexColor(st["filet"])}) if donnees is not False else []) + [PageBreak(), Paragraph("Sommaire", styles["h1"]), sommaire]
    GRANDS = ("Gallimard", "Gallimard Jeunesse", "Alkonost")          # pages d'ouverture pleine page ; les autres éditeurs ont un bandeau dans le flux
    for k, (editeur, versions_ed) in enumerate(groupes):
        nom_versions = [ver for ver, _ in versions_ed]
        total = sum(len(l) for _, ss in versions_ed for _, l in ss)
        marque = Marqueur(etat, editeur=editeur, versions=nom_versions, index=k, nb=total, nv=len(nom_versions), niveau0=editeur)
        bandeau = []
        if editeur in GRANDS:
            histoire += [NextPageTemplate("ouverture"), PageBreak(), marque, NextPageTemplate("catalogue"), PageBreak()]
        else:
            if k == 0 or groupes[k - 1][0] in GRANDS:
                histoire += [NextPageTemplate("catalogue"), PageBreak()]
            bandeau = [marque, BandeauEditeur(editeur, total, st, pol)]
        for j, (version, series_v) in enumerate(versions_ed):
            entete = (bandeau if j == 0 else []) + [Marqueur(etat, editeur=editeur, version=version, versions=nom_versions), TitreVersion(editeur, version, st, pol)]
            for i, (nom, livres) in enumerate(series_v):
                cellules = [Fiche(v, st, pol, web, offre_annonces, reperes, zone_de(v), genere_le) for v in livres]
                while len(cellules) % COLONNES:
                    cellules.append("")
                rangs = []
                for r in range(0, len(cellules), COLONNES):
                    t = Table([cellules[r:r + COLONNES]], colWidths=[L_CADRE / COLONNES] * COLONNES, hAlign="LEFT")
                    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
                    rangs.append(t)
                tete = TeteSerie(nom, len(livres), st, pol)
                # une série qui tient sur une page n'est jamais coupée ; sinon, bandeaux avec au moins une rangée, et jamais une seule rangée isolée en haut de page
                bloc = (entete if i == 0 else []) + [tete] + rangs
                if sum(f.wrap(L_CADRE, H_PAGE)[1] for f in bloc) <= H_PAGE - HAUT - BAS:
                    histoire += [KeepTogether(bloc)]
                else:
                    histoire += [KeepTogether((entete if i == 0 else []) + [tete] + rangs[:1])] + rangs[1:-2] + [KeepTogether(rangs[-2:])]
    doc.multiBuild(histoire)
    construire.remplissage = (sum(remplissage.values()) / len(remplissage)) if remplissage else 0.0          # taux moyen de remplissage des pages du catalogue
    construire.pages_catalogue = len(remplissage)
    return nb


def fr(x, decimales=None):
    """Nombre à la française (virgule), entier sans zéros inutiles."""
    return f"{x:g}".replace(".", ",") if decimales is None else f"{x:.{decimales}f}".replace(".", ",")


class GlypheZone(Flowable):
    """Le mini nuage à quatre cases d'une zone, pour la page de méthode."""
    def __init__(self, zone, st):
        super().__init__()
        self.zone, self.st = zone, st

    def wrap(self, *_):
        return 7 * mm, 6 * mm

    def draw(self):
        glyphe_zone(self.canv, 0, 0.4 * mm, 5.2 * mm, self.zone, self.st)


def page_nuage(versions, donnees, styles, polices, st):
    """Une page de méthode : du nuage de points aux quatre zones, puis à la zone marquée sur chaque livre. Valeurs des médianes recalculées à chaque génération."""
    f_titre, f_titre_gras, f_texte, f_gras = polices
    cx = {"texte": HexColor(st["texte"]), "sourdine": HexColor(st["sourdine"]), "or": HexColor(st["or"]), "filet": HexColor(st["filet"]), "fond": HexColor(st["fond"]), "grille": HexColor(st["grille"])}
    P = lambda t, k="corps": Paragraph(t, styles[k])  # noqa: E731
    pts = ga.points_editions(versions, donnees["offre"])
    if not pts:
        return []
    e = ga.Echelles(pts, 100, 100)
    sens = {q: ZONES_TEXTE[q][0].split(" : ")[0] for q in ZONES_TEXTE}          # surnom de chaque zone ; le détail est sur les pages suivantes
    ordre = sorted(ga.NUM_ZONE, key=lambda q: ga.NUM_ZONE[q])          # zone 1 à 4
    parts = ga.parts_zones(versions, donnees["offre"], e.med_o, e.med_c)          # part de chaque zone parmi les livres du nuage
    zones = Table([[GlypheZone(q, st), P(f"<b>Zone {ga.NUM_ZONE[q]}</b> · {ga.ZONES[q]}"), P(f"{sens[q]} · {parts[q][1]}\u00a0%")] for q in ordre], colWidths=[9 * mm, 66 * mm, L_CADRE - 75 * mm], hAlign="LEFT")
    zones.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    return [PageBreak(), P("La méthode : le nuage et ses quatre zones", "h1m"), Ornement(40 * mm, cx["filet"]), Spacer(1, 3 * mm),
            P("Pour situer chaque livre, le guide s'appuie sur un nuage de points. Il se lit en trois temps."),
            Spacer(1, 1 * mm), ga.dessiner_radar(pts, (), L_CADRE, 60 * mm, f_texte, f_gras, cx), Spacer(1, 2 * mm),
            P(f"<b>1. Chaque livre est un point.</b> Sa place dépend de deux mesures : le nombre d'annonces en ligne, de gauche à droite (gradué en bas), et son prix d'occasion, de bas en haut (gradué sur le côté, en euros). Les repères ne sont pas réguliers : chacun double à peu près le précédent, pour garder les petits prix lisibles."),
            P(f"<b>2. Deux lignes pointillées coupent le nuage en quatre zones.</b> La verticale marque le milieu de l'offre : {fr(e.med_o)} annonces par livre (médiane de l'offre). L'horizontale marque le milieu des prix : {fr(e.med_c, 2)}\u00a0€ (médiane des prix). Un livre sur deux se trouve de chaque côté de chaque ligne : « beaucoup d'annonces » ou « cher » veut dire au-dessus de la médiane, pas hors de prix."),
            P("<b>3. Chaque livre du guide porte sa zone.</b> Sous son prix, un petit carré à quatre cases, dont la sienne est en or, et son numéro : « Zone 1 » à « Zone 4 ». D'un coup d'œil, on sait où le livre se situe sur le nuage."),
            Spacer(1, 1 * mm), zones,
            P(f"<b>Que veulent dire ces pourcentages ?</b> La part des livres du guide dans chaque zone : {sum(n for n, _ in parts.values())} livres placés sur le nuage, d'après {_annonces_en_chiffres(sum(ga.nb_annonces(o) for o in donnees['offre'].values()))} en ligne aujourd'hui. "
              "Les quatre parts font 100\u00a0% ; chaque zone pèse à peu près un quart, car les pointillés sont des médianes."),
            P("Par exemple, un livre marqué « Zone 1 » a peu d'annonces et un prix élevé : il se trouve en haut à gauche du nuage. Les pages suivantes racontent ce que chaque zone veut dire, avec des exemples. Ce nuage est une photographie à la date du guide : il décrit le marché du moment, pas une tendance."),
            P("<b>Le nuage ne sert pas à comparer deux livres</b>, qui n'ont pas forcément le même public ni le même tirage (deux éditions d'un même livre, elles, peuvent l'être). "
              "Il distingue <b>quatre marchés différents</b> : on n'aborde pas un marché rare comme un marché courant, et chaque zone appelle sa propre stratégie, expliquée plus loin.")] + page_zones(styles, st, cx, ga.exemples_zones(versions, donnees["offre"], e.med_o, e.med_c), parts)


def phrase_exemples(exemples):
    """« Quelques exemples d'aujourd'hui : … » d'après les livres choisis pour une zone."""
    morceaux = []
    for x in exemples:
        num = f" n°\u00a0{x['numero']}" if x.get("numero") and str(x["numero"]).strip("0") else ""
        n = x["annonces"]
        offre = "aucune annonce en ce moment" if n == 0 else f"{n} annonce{'s' if n > 1 else ''} en ligne"
        morceaux.append(f"« {x['titre']} » ({x['serie']}{num}, {x['version']}), {offre}, autour de {round(x['cote'])}\u00a0€")
    return ("Quelques exemples d'aujourd'hui : " + " ; ".join(morceaux) + ".") if morceaux else ""


def page_zones(styles, st, cx, exemples, parts=None):
    """Les quatre zones racontées : ce que le rapport entre le nombre d'annonces et le prix dit d'un livre, avec des exemples du guide. Aucun conseil d'achat ni de vente."""
    P = lambda t, k="corps": Paragraph(t, styles[k])  # noqa: E731
    h = [PageBreak(), P("Les quatre zones, une à une", "h1m"), Ornement(40 * mm, cx["filet"]), Spacer(1, 3 * mm),
         P("Un livre n'est jamais « cher » ou « bon marché » tout seul : cela dépend du nombre d'exemplaires qui sont à vendre. En croisant le nombre d'annonces et le prix, on obtient une petite histoire sur chaque livre. Sur un marché ordinaire, plus il y a d'offres, plus les prix se tassent ; chaque zone dit si c'est le cas, ou non, et pourquoi. Voici ce que raconte chacune, avec des exemples tirés du guide à la date de sa génération.")]
    for q in sorted(ZONES_TEXTE, key=lambda q: ga.NUM_ZONE[q]):
        titre, texte = ZONES_TEXTE[q]
        ligne = Table([[GlypheZone(q, st), [P(f"Zone {ga.NUM_ZONE[q]} · {titre}", "h2"), P(f"<i>{ga.ZONES[q]}</i>")] + ([P(f"<b>{parts[q][1]}\u00a0% des livres du guide</b> ({parts[q][0]}\u00a0livres)")] if parts and parts[q][0] else []) + [P(t) for t in texte + (phrase_exemples(exemples.get(q, [])),) if t]]],
                      colWidths=[11 * mm, L_CADRE - 11 * mm], hAlign="LEFT")
        ligne.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (0, 0), 4 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm)]))
        h.append(ligne)
    return h + [Spacer(1, 3 * mm),
                P("<b>D'où viennent ces données ?</b> La Cote du Héros relève les annonces d'occasion sur les différents sites, puis les range par titre, par édition et par éditeur, ce qui reste difficile quand une annonce est incomplète ou ambiguë. "
                  "Pour chaque livre, le site compte les annonces trouvées et calcule un prix médian : la moitié des annonces est moins chère, l'autre moitié plus chère."),
                P("Ces lectures sont des repères pour comprendre un marché, pas des promesses : une annonce est un prix demandé, pas un prix payé. Plus loin, « La stratégie du collectionneur » propose des façons de s'en servir.")]


def encart(titre, texte, styles, cx):
    """Petit pavé d'avertissement : filet doré à gauche, fond doré très léger."""
    f = cx["filet"]
    cellule = [Paragraph(f"<b>{titre}</b>", styles["corps"]), Paragraph(texte, styles["corps"])]
    t = Table([[cellule]], colWidths=[L_CADRE], hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), Color(f.red, f.green, f.blue, alpha=0.12)), ("LINEBEFORE", (0, 0), (0, -1), 2.2, f),
                           ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm), ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm)]))
    return t


def page_strategie(styles, cx):
    """Un petit article : une stratégie par zone (qui collectionne, pourquoi, comment acquérir), puis les doubles."""
    P = lambda t, k="corps": Paragraph(t, styles[k])  # noqa: E731
    sections = (
        (2, ("<b>Qui ?</b> Le complétiste : celui qui veut toute une édition ou toute une série, et qui cherche le dernier numéro manquant.",
             "<b>Objectif.</b> Posséder ce que presque personne n'a, et boucher les trous de la collection.",
             "<b>Stratégie.</b> On guette, parfois des mois, et le jour où l'annonce arrive, il faut pouvoir payer le prix : savoir tôt ce qu'il vous manque en zone 1, c'est savoir combien de temps prévoir. "
             "Le bon coup est une annonce affichée en dessous du prix habituel du livre. Elle vient d'un vendeur pressé, ou qui ne connaît pas la valeur de ce qu'il vend. Cela arrive peu et ne dure pas : il faut être là le jour même, et le Butin et la Chasse, sur le site, sont faits pour cela. "
             "Avant d'acheter, vérifiez l'édition (V1, V2…), l'état et les frais de port : un prix bas qui cache un autre livre n'est pas une bonne affaire.")),
        (3, ("<b>Qui ?</b> L'acheteur pressé, et celui qui achète pour revendre ou échanger.",
             "<b>Objectif.</b> Trouver vite un livre très demandé, ou faire tourner sa collection.",
             "<b>Stratégie.</b> Laissez venir. Les annonces sont nombreuses, un prix demandé élevé n'est pas un prix payé : comparez, négociez.")),
        (0, ("<b>Qui ?</b> Le collectionneur de série, attiré par des titres moins connus ou des séries moins suivies.",
             "<b>Objectif.</b> Compléter sans se ruiner.",
             "<b>Stratégie.</b> Rien ne presse : peu d'annonces et pas cher, on prend au passage quand on en croise un. Le collectionneur de série y fait des économies.")),
        (1, ("<b>Qui ?</b> Le débutant, et celui qui retrouve les livres de son enfance.",
             "<b>Objectif.</b> Faire avancer la collection vite et pour presque rien.",
             "<b>Stratégie.</b> Commencez par là : l'offre est large, vous choisissez l'exemplaire et le vendeur, sans vous presser. Sélectionnez le très bon état. "
             "L'état est fondamental, et La Cote du Héros le précise pour chaque prix : sinon, on surpaie un livre qui ne vaut pas sa valeur. "
             "Mieux vaut parfois payer un peu plus cher pour un état impeccable.")),
    )
    h = [PageBreak(), P("La stratégie du collectionneur", "h1m"), Ornement(40 * mm, cx["filet"]), Spacer(1, 3 * mm),
         P("On ne collectionne pas tous de la même façon. Chaque zone est un marché à part, avec ses collectionneurs, son objectif et sa stratégie. "
           "Les zones ne disent pas quoi faire, elles disent où l'on se trouve : de quoi savoir par où commencer, et ce qu'il vaut mieux attendre. Premier réflexe, quelle que soit votre façon de collectionner : regarder la zone du livre avant de se décider.")]
    h += [Spacer(1, 2 * mm), encart("Attention aux V1 Gallimard", "Les livres dont vous êtes le héros en V1, chez Gallimard, sont extrêmement fragiles. Aujourd'hui, la colle ne tient plus, et ils demandent parfois une rénovation. "
                                    "On ne les recommande pas pour la lecture : les V5, elles, sont extraordinaires pour cela. Les V1 Gallimard sont plutôt destinées à la collection.", styles, cx)]
    for q, paragraphes in sorted(sections, key=lambda x: ga.NUM_ZONE[x[0]]):
        h.append(KeepTogether([P(f"Zone {ga.NUM_ZONE[q]} · {ZONES_TEXTE[q][0].split(' : ')[0]}", "h2")] + [P(t) for t in paragraphes]))
    h += [P("Si vous avez des doubles", "h2"), P("Un double en zone 1 se vend bien, puisqu'on le cherche. En zone 2, le marché est liquide : un livre cher y trouve preneur, surtout s'il est proposé un peu sous le prix des annonces voisines. Regardez-les avant de fixer le vôtre. En zones 3 et 4, il n'y a pas grand-chose à gagner à attendre : l'offre est large, ou la demande est faible. La liste « À vendre » du site est là pour ces doubles.")]
    return h


# Titre et récit de chaque zone (0 peu d'offre bon marché, 1 beaucoup d'offre bon marché, 2 peu d'offre cher, 3 beaucoup d'offre cher)
ZONES_TEXTE = {
    2: ("La rareté : les livres rares", ("Ce sont les livres rares. Peu d'exemplaires sont à vendre, et le prix est élevé : les deux vont ensemble. Un livre devient rare pour des raisons simples : il a été peu imprimé, son édition est épuisée depuis longtemps, ou ses propriétaires le gardent précieusement et ne le revendent presque jamais.",
                                          "Du côté des acheteurs, c'est l'inverse : les collectionneurs qui cherchent ce titre sont plus nombreux que les exemplaires disponibles. Quand une annonce apparaît, plusieurs personnes la guettent, et le vendeur peut demander un prix élevé. Le prix n'invente pas la rareté, il la constate : c'est ce que l'on appelle la rareté d'un livre.")),
    3: ("Cher et liquide : beaucoup d'annonces, mais cher", ("Beaucoup d'annonces et un prix élevé : c'est une zone chère, et c'est une zone liquide. Liquide, cela veut dire que le marché est actif : il y a du monde, des vendeurs comme des acheteurs, et les livres circulent.",
                                                              "D'ordinaire, quand les vendeurs sont nombreux, ils se font concurrence et les prix baissent. Si le prix reste haut malgré tout, deux explications sont possibles : la demande est très forte et absorbe l'offre, ou bien certains vendeurs demandent plus que ce que les acheteurs acceptent de payer. Rappelons qu'une annonce est un prix demandé, pas un prix payé.",
                                                              "Voilà la zone où certains achètent pour revendre plus cher. Comme le marché est liquide, un livre y trouve preneur : proposé un peu en dessous du prix des annonces voisines, il part en général plus vite. En revanche, le prix affiché y est le moins sûr : on compare avant de se fier à une annonce.")),
    0: ("Un marché calme : peu d'annonces, mais bon marché", ("Peu d'annonces et un prix bas. Ici, il ne faut pas confondre : peu d'exemplaires à vendre ne veut pas dire rare. La rareté suppose que l'on cherche le livre ; or personne ne se bat pour celui-ci. Peu de gens vendent, et peu de gens achètent.",
                                                              "Ces livres intéressent moins les collectionneurs : des titres moins connus, des séries moins suivies, des éditions que l'on ne cherche pas. Les prix restent bas parce que la demande est faible, pas parce que l'offre est abondante. Le marché y est tranquille, sans tension d'aucun côté.")),
    1: ("Le courant : beaucoup d'annonces, bon marché", ("Beaucoup d'annonces et un prix bas : ce sont les livres courants. Ils ont été beaucoup imprimés, beaucoup vendus, et beaucoup de gens s'en séparent aujourd'hui : l'offre est large et les vendeurs se font concurrence, ce qui tire les prix vers le bas.",
                                                         "L'acheteur est dans une position confortable : il choisit l'exemplaire (l'état, la jaquette) et le vendeur, sans se presser. Un livre courant n'est pas un livre sans intérêt : c'est souvent celui que l'on a lu enfant, simplement facile à retrouver.")),
}


MILLIERS = {1: "mille", 2: "deux mille", 3: "trois mille", 4: "quatre mille", 5: "cinq mille", 6: "six mille", 7: "sept mille", 8: "huit mille", 9: "neuf mille", 10: "dix mille"}


def _annonces_en_chiffres(n):
    """« plus de 5 000 annonces » (millier inférieur) ; « de nombreuses annonces » sous mille."""
    return f"plus de {n // 1000 * 1000:,} annonces".replace(",", "\u00a0") if n >= 1000 else "de nombreuses annonces"


def _annonces_en_mots(n):
    """« plus de cinq mille annonces » (millier inférieur, en toutes lettres) ; « de nombreuses annonces » sans chiffre exploitable."""
    mots = MILLIERS.get(n // 1000)
    return f"plus de {mots} annonces" if mots else "de nombreuses annonces"


def section_radar(versions, donnees, styles, date_cotes, polices, st):
    """Chapitre « Le radar du héros » : le radar du site pour tout le guide, un radar par grand éditeur (une bulle par série), puis les séries à surveiller.
    Axes et zones en mots ; les deux médianes (pointillés) sont écrites une fois, dans la lecture du radar ; phrases calculées à chaque génération."""
    f_titre, f_titre_gras, f_texte, f_gras = polices
    cx = {"texte": HexColor(st["texte"]), "sourdine": HexColor(st["sourdine"]), "or": HexColor(st["or"]), "filet": HexColor(st["filet"]), "fond": HexColor(st["fond"]), "grille": HexColor(st["grille"])}
    P = lambda t, k="corps": Paragraph(t, styles[k])  # noqa: E731
    profs = ga.profils(versions, donnees["offre"], editeur_de)
    pts = ga.points_editions(versions, donnees["offre"])
    h = [P("Le radar du héros", "h1m"), Ornement(40 * mm, cx["filet"]), Spacer(1, 3 * mm),
         P("Les cotes sont des estimations tirées de plusieurs sources : archives, annonces en ligne et librairies. Une annonce est un prix demandé, pas un prix payé. "
           "La confiance d'une cote dépend du nombre d'observations. Une cote n'est pas un prix garanti."),
         P("Le radar de tout le guide", "h2"),
         P("Ce nuage de points repose sur une collecte délicate. Derrière lui, il y a " + _annonces_en_mots(sum(ga.nb_annonces(o) for o in donnees["offre"].values())) + " en circulation aujourd'hui sur les différents sites : une estimation de ce que le marché propose, pas un décompte exact. "
           "La Cote du Héros les relève, puis les range par titre, par édition et par éditeur, ce qui reste difficile quand une annonce est incomplète ou ambiguë. "
           "Pour chaque livre, le site compte les annonces trouvées et calcule un prix médian : la moitié des annonces est moins chère, l'autre moitié plus chère."),
         ga.dessiner_radar(pts, (), L_CADRE, 128 * mm, f_texte, f_gras, cx), Spacer(1, 2 * mm)]
    h += [P(t) for t in ga.lecture_globale(pts)]
    h += [P("Que faire de ce radar ?", "h2"),
          P("Sur La Cote du Héros, chaque livre est placé sur ce même graphique. Il sert à vous poser la bonne question : dois-je acheter, attendre ou passer mon chemin ?"),
          P(f"<b>Vous débutez, sans aucun livre ?</b> Commencez par la zone {ga.NUM_ZONE[1]}, « beaucoup d'annonces, bon marché », en bas à droite : les vendeurs sont nombreux et les prix bas. "
            "Vous constituez votre collection sans courir après les livres, ni risquer de payer trop cher.")]
    editeurs = ga.grands_editeurs(profs)
    for i, e in enumerate(editeurs):
        ps = [p for p in profs if p["editeur"] == e]
        bloc = [P(e, "h2")]
        if i == 0:
            bloc.append(P("Chaque bulle est une série, placée au centre de ses livres ; plus elle est grosse, plus l'éditeur y compte de livres."))
        bloc += [ga.dessiner_radar(pts, ps, L_CADRE, 84 * mm, f_texte, f_gras, cx)] + [P(t) for _, t in ga.verdicts_editeur(ps, pts)]
        h.append(KeepTogether(bloc))
    tendues, faciles = ga.series_a_surveiller(profs, pts)
    if tendues or faciles:
        puce = lambda l: [Paragraph(f"<b>{e} · {s_}</b>, {m}", styles["puce_radar"], bulletText="•") for e, s_, m in l]  # noqa: E731
        colonnes = Table([[[P("En zone tendue", "h2")] + puce(tendues), [P("Faciles à trouver", "h2")] + puce(faciles)]], colWidths=[L_CADRE / 2, L_CADRE / 2], hAlign="LEFT")
        colonnes.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm)]))
        h += [P("Les séries à surveiller", "h2"), P("Celles où l'offre se raréfie alors que les prix montent, et celles où l'on peut encore se servir sans attendre."), Spacer(1, 1 * mm), colonnes]
    h += [P("Un radar est une photographie à la date du guide : il décrit l'offre du moment, pas une tendance. Ses phrases sont recalculées à chaque génération.")]
    return h


def main(argv=None):
    global COUVERTURE_STYLE
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--sortie", default="guide-reference.pdf")
    a.add_argument("--series", default="", help="noms de séries séparés par des virgules (essai)")
    a.add_argument("--editeurs", default="", help="noms d'éditeurs séparés par des virgules (essai)")
    a.add_argument("--style", default=STYLE_PAR_DEFAUT, choices=tuple(STYLES), help="direction de style : nuit (sombre et or) ou parchemin (fond crème, pour l'impression)")
    a.add_argument("--style-couverture", default=COUVERTURE_STYLE, choices=("a", "b", "c"), help="mise en page de la couverture : a (revue de collection), b (affiche d'aventure, par défaut) ou c (ouvrage de référence sobre)")
    a.add_argument("--visuel-couverture", default=COUVERTURE_PAR_DEFAUT, choices=("v1", "huile"), help="illustration de couverture : v1 (héros et dragon, par défaut) ou huile (ancienne couverture)")
    a.add_argument("--couverture", default=SOUS_TITRE_PAR_DEFAUT, choices=("clair", "bandeau"), help="variante du sous-titre de la couverture « huile »")
    a.add_argument("--mention-sorciers", action="store_true", help="ajoute la mention « Document réservé aux sorciers… » en pied de page (option)")
    args = a.parse_args(argv)
    debut = time.time()
    versions = json.loads((WEB / "data" / "versions.json").read_text(encoding="utf-8"))
    meta = json.loads((WEB / "data" / "meta.json").read_text(encoding="utf-8"))
    series = {s.strip() for s in args.series.split(",") if s.strip()} or None
    editeurs = {s.strip() for s in args.editeurs.split(",") if s.strip()} or None
    COUVERTURE_STYLE = args.style_couverture
    nb = construire(versions, args.sortie, meta.get("genere_le") or date.today().isoformat(), series, editeurs=editeurs, sous_titre=args.couverture, style=args.style, mention=args.mention_sorciers, visuel=args.visuel_couverture, meta=meta)
    print(f"{nb} livres, {Path(args.sortie).stat().st_size // 1024} Ko, {time.time() - debut:.1f} s, {construire.pages_catalogue} pages de catalogue remplies à {construire.remplissage * 100:.0f} % en moyenne : {args.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
