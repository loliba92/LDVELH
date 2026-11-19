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
STYLE_PAR_DEFAUT = "nuit"            # direction de style : "nuit" (sombre et or) ou "parchemin" (fond crème, pour l'impression)
SOUS_TITRE_PAR_DEFAUT = "clair"      # sous-titre de la couverture « huile » : "clair" ou "bandeau" (sans effet sur la couverture V1)
COUVERTURE_PAR_DEFAUT = "v1"         # illustration de couverture : "v1" (héros et dragon) ou "huile" (ancienne couverture)
# -------------------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
WEB = RACINE / "web"
COUVERTURE = Path(__file__).resolve().parent / "guide" / "couverture.jpg"          # illustration « huile »
COUVERTURE_V1 = Path(__file__).resolve().parent / "guide" / "couverture-v1.jpg"          # illustration « V1 » (992 × 1586) : héros, dragon, château
EMBLEME = WEB / "icons" / "icon-512.png"          # le sceau du site : le personnage encapuchonné
SITE = "lacoteduheros.fr"
LIEN_SITE = "https://lacoteduheros.fr"
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
LARGEUR_JAQUETTE_PX = 230           # jaquette « small » réduite : nette à 36 mm (environ 160 points par pouce)
COLONNES = 4
MARGE_X, HAUT, BAS = 14 * mm, 21 * mm, 19 * mm
L_PAGE, H_PAGE = A4
L_CADRE = L_PAGE - 2 * MARGE_X

# Deux directions de style. « nuit » reprend la palette du site. « parchemin » : crème du papier de la couverture et brun encre (couleurs nouvelles, pour l'impression papier).
STYLES = {
    "nuit": {"fond": "#0c0a08", "texte": "#f2e9d8", "sourdine": "#b8ad99", "or": "#d9b45f", "titre": "#d9b45f", "filet": "#d2a64a", "pastille": "#2a2412", "grille": "#2c261e",
             "ombre": (0, 0, 0), "ombre_alpha": 0.5, "filigrane": 0.065, "embleme": (217, 180, 95)},
    "parchemin": {"fond": "#f3e9d2", "texte": "#2a2118", "sourdine": "#6d5d47", "or": "#8c6a1c", "titre": "#7a5a14", "filet": "#b08a37", "pastille": "#e6d6b0", "grille": "#d9c9a3",
                  "ombre": (0.35, 0.25, 0.1), "ombre_alpha": 0.35, "filigrane": 0.10, "embleme": (140, 106, 28)},
}


def date_longue(iso):
    d = date.fromisoformat(str(iso)[:10])
    return f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"


# Repères en mots, sans chiffre. Les seuils sont ceux du site (web/app.js : niveauCote, SEUILS_COTE, et le bloc « Offre d'occasion ») ; ils ne sont jamais affichés.
SEUILS_PRIX = (10, 20, 40, 70)
MOTS_PRIX = ("pas cher", "abordable", "moyen", "cher", "très cher")


def niveau_prix(v):
    """1 à 5 selon la cote, comme le site pour les visiteurs ; None sans cote."""
    return None if v is None else 1 + sum(1 for x in SEUILS_PRIX if v >= x)


def mot_offre(n, neuf=False):
    """« Rareté en vente » : abondance des annonces en ligne à l'instant T. Les trois premiers niveaux suivent le bloc « Offre d'occasion » du site (aucune, une seule, quelques-unes) ;
    le site réunit « beaucoup » en un seul niveau : ici il est coupé en courant et abondant (seuil propre au guide, jamais affiché)."""
    if n == 0:
        return "disponible neuf" if neuf else "introuvable"
    return "rare" if n == 1 else "peu d'annonces" if n <= 3 else "courant" if n < 10 else "abondant"


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


def couverture_v1(largeur_px=1240, art_mm=198, bas_coupe_px=210):
    """Toile de la couverture V1 (A4 moins le bandeau du haut) : l'illustration est agrandie (rééchantillonnage Lanczos, accentuation légère), son bas (roche) est recoupé,
    et la toile est prolongée vers le haut et sur les côtés par un fond flou tiré de l'illustration elle-même : un vrai espace de titre dans le ciel violet."""
    from PIL import ImageFilter
    px_mm = largeur_px / 210
    haut_px = round(288 * px_mm)
    with Image.open(COUVERTURE_V1) as src:
        art = src.convert("RGB").crop((0, 0, src.width, src.height - bas_coupe_px))
    f = art_mm * px_mm / art.width
    art = art.resize((round(art.width * f), round(art.height * f)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.2, percent=35, threshold=2))
    fond = art.resize((largeur_px, haut_px), Image.LANCZOS).filter(ImageFilter.GaussianBlur(55))
    fond = ImageEnhance.Brightness(fond).enhance(0.7)
    x, y = (largeur_px - art.width) // 2, haut_px - art.height
    masque = Image.new("L", art.size, 255)
    bord = 38
    pixels = masque.load()
    for i in range(bord):
        v = int(255 * i / bord)
        for j in range(art.height):
            pixels[i, j] = min(pixels[i, j], v)
            pixels[art.width - 1 - i, j] = min(pixels[art.width - 1 - i, j], v)
        for k in range(art.width):
            pixels[k, i] = min(pixels[k, i], v)
    fond.paste(art, (x, y), masque)
    tampon = io.BytesIO()
    fond.save(tampon, "JPEG", quality=84, optimize=True, progressive=True)
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
    """Flowable invisible : note à quel éditeur et à quelle version appartient la page en cours (pour l'en-tête, les onglets et la page d'ouverture)."""
    def __init__(self, etat, **valeurs):
        super().__init__()
        self.etat, self.valeurs = etat, valeurs

    def wrap(self, *_):
        return 0, 0.01

    def draw(self):
        self.etat.update(self.valeurs)


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


class TitreVersion(Flowable):
    """Tête d'une version : l'éditeur en petites capitales, la version en grand, un ornement."""
    def __init__(self, editeur, version, st, polices):
        super().__init__()
        self.editeur, self.version, self.st, self.pol = editeur, version, st, polices

    def getPlainText(self):
        return f"{self.editeur} · {self.version}"

    def wrap(self, *_):
        return L_CADRE, 24 * mm

    def draw(self):
        c, st, (f_titre, f_titre_gras, f_texte, f_gras) = self.canv, self.st, self.pol
        c.setFillColor(HexColor(st["sourdine"]))
        lettres(c, 0, 19 * mm, self.editeur, f_gras, 8.5, 1.4)
        c.setFillColor(HexColor(st["titre"]))
        c.setFont(f_titre_gras, 38)
        c.drawString(0, 7.5 * mm, self.version)
        c.setStrokeColor(HexColor(st["filet"]))
        c.setLineWidth(0.5)
        c.line(pdfmetrics.stringWidth(self.version, f_titre_gras, 38) + 6 * mm, 11 * mm, L_CADRE, 11 * mm)


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


class Fiche(Flowable):
    """Un livre : jaquette avec ombre douce, titre, numéro, version, rareté, offre en vente, repères de prix par état (jauge à cinq crans ou mot). Aucun chiffre de cote."""
    def __init__(self, v, st, polices, web, offre=None, reperes="jauge"):
        super().__init__()
        self.v, self.st, self.pol, self.web, self.reperes = v, st, polices, web, reperes
        self.largeur = L_CADRE / COLONNES
        self.iw = 36 * mm
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
        prix = v.get("prix") or {}
        self.niveaux = [(lib, niveau_prix(prix.get(cle))) for lib, cle in (("C", "convenable"), ("BE", "bon"), ("TBE", "tres_bon"))]

    def libelles(self):
        """Tous les textes dessinés dans la cellule (pour les tests : aucun montant, aucun nombre décimal)."""
        bon = self.niveaux[1][1]
        return [self.v.get("titre") or "", self.meta, "Rareté en vente", self.offre, f"BE : {MOTS_PRIX[bon - 1] if bon else 'sans repère'}"]

    def wrap(self, *_):
        self.h = self.ih + 3 * mm + self.th + 3.8 * mm + 7 * mm + 9.2 * mm + 3.6 * mm + 2.5 * mm
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
        lettres(c, self.largeur / 2, y, "Rareté en vente", f_texte, 5.4, 0.5, centre=True)
        y -= 3 * mm
        c.setFillColor(HexColor(st["titre"]))
        c.setFont(f_gras, 7.4)
        c.drawCentredString(self.largeur / 2, y, self.offre)
        y -= 1.8 * mm
        pw, ph, gap = 13.6 * mm, 8 * mm, 1 * mm
        x = (self.largeur - 3 * pw - 2 * gap) / 2
        for lib, niveau in self.niveaux:          # pastilles arrondies comme les badges du site
            c.setFillColor(HexColor(st["pastille"]))
            c.setStrokeColor(HexColor(st["filet"]))
            c.setLineWidth(0.4)
            c.roundRect(x, y - ph, pw, ph, 2 * mm, fill=1, stroke=1)
            c.setFillColor(HexColor(st["sourdine"]))
            lettres(c, x + pw / 2, y - 2.9 * mm, lib, f_gras, 5.6, 0.6, centre=True)
            for k in range(5):          # jauge à cinq crans : plus elle est pleine, plus c'est cher
                c.setFillColor(HexColor(st["or"]) if niveau and k < niveau else HexColor(st["grille"]))
                c.setStrokeColor(HexColor(st["filet"]))
                c.setLineWidth(0.25)
                c.rect(x + 1.7 * mm + k * 2.05 * mm, y - 6.4 * mm, 1.7 * mm, 1.7 * mm, fill=1, stroke=1)
            x += pw + gap
        bon = self.niveaux[1][1]
        c.setFillColor(HexColor(st["texte"]))
        c.setFont(f_texte, 6.8)
        c.drawCentredString(self.largeur / 2, y - ph - 3 * mm, f"BE : {MOTS_PRIX[bon - 1] if bon else 'sans repère'}")


def legende(styles):
    """Page de légende : chaque mot des repères, sans seuil ni chiffre."""
    P = lambda t, k="corps": Paragraph(t, styles[k])  # noqa: E731
    return [P("Rareté en vente", "h2"), P("L'abondance des annonces en ligne au moment du guide : introuvable, rare, peu d'annonces, courant, abondant. Disponible neuf : le livre est encore vendu neuf."),
            P("Prix", "h2"), P("Une jauge de cinq crans : plus elle est pleine, plus l'exemplaire est cher. Le mot donne le niveau de prix : pas cher, abordable, moyen, cher, très cher."),
            ]


def construire(versions, sortie, date_cotes, series=None, web=WEB, genere_le=None, editeurs=None, donnees=None, sous_titre=SOUS_TITRE_PAR_DEFAUT, style=STYLE_PAR_DEFAUT, mention=False, visuel=COUVERTURE_PAR_DEFAUT, reperes="jauge"):
    """Écrit le PDF. Renvoie le nombre de livres."""
    st = STYLES[style]
    genere_le = genere_le or date.today().isoformat()
    groupes = grouper(versions, series, editeurs)
    pol = polices(tempfile.mkdtemp(prefix="guide-polices-"))
    f_titre, f_titre_gras, f_texte, f_gras = pol
    C = lambda k: HexColor(st[k])  # noqa: E731
    etat = {"editeur": None, "version": None, "versions": [], "index": 0, "nb": 0}
    styles = {
        "corps": ParagraphStyle("corps", fontName=f_texte, fontSize=10.5, leading=15.5, textColor=C("texte")),
        "h1": ParagraphStyle("h1", fontName=f_titre_gras, fontSize=30, leading=34, textColor=C("titre"), spaceAfter=7 * mm),
        "h1m": ParagraphStyle("h1m", fontName=f_titre_gras, fontSize=30, leading=34, textColor=C("titre"), spaceAfter=6 * mm),
        "h2": ParagraphStyle("h2", fontName=f_titre_gras, fontSize=17, leading=20, textColor=C("titre"), spaceBefore=5 * mm, spaceAfter=2 * mm, keepWithNext=1),
        "toc": ParagraphStyle("toc", fontName=f_texte, fontSize=10, leading=14, textColor=C("texte")),
    }

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

    def page_texte(c, doc):
        pied(c, doc)

    def page_catalogue(c, doc):
        pied(c, doc)
        c.setFillColor(C("sourdine"))
        lettres(c, MARGE_X, H_PAGE - 12 * mm, f"{etat['editeur']} · {etat['version']}", f_gras, 7.5, 1.2)
        lettres(c, L_PAGE - MARGE_X, H_PAGE - 12 * mm - 0, "", f_texte, 7)
        c.setFillColor(C("sourdine"))
        c.setFont(f_texte, 7)
        c.drawRightString(L_PAGE - MARGE_X, H_PAGE - 12 * mm, "La Cote du Héros")
        c.setStrokeColor(C("filet"))
        c.setLineWidth(0.4)
        c.line(MARGE_X, H_PAGE - 14.5 * mm, L_PAGE - MARGE_X, H_PAGE - 14.5 * mm)
        for k, ver in enumerate(etat["versions"]):          # onglets de version sur le bord de la page
            actif = ver == etat["version"]
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

    def couverture_v1_page(c, doc):
        """Couverture inspirée des couvertures de poche des années 1980 : bandeau uni en haut, grand titre dans le ciel, encadré blanc et adresse du site en bas."""
        c.drawImage(couverture_v1(), 0, 0, L_PAGE, 288 * mm)
        c.setFillColor(HexColor("#d2a64a"))          # or du site
        c.rect(0, 288 * mm, L_PAGE, 9 * mm, fill=1, stroke=0)
        c.setFillColor(HexColor("#0c0a08"))
        lettres(c, L_PAGE / 2, 290.6 * mm, "La Cote du Héros", f_gras, 10, 3, centre=True)
        c.saveState()
        t = c.beginText()
        c.setFillColor(HexColor("#f2e9d8"))
        c.setStrokeColor(HexColor("#1a0d33"))
        c.setLineWidth(1.1)
        t.setTextRenderMode(2)          # remplissage crème et fin contour sombre
        t.setFont(f_titre_gras, 50)
        titre = "Guide de référence"
        t.setTextOrigin((L_PAGE - pdfmetrics.stringWidth(titre, f_titre_gras, 50)) / 2, 262 * mm)
        t.textOut(titre)
        c.drawText(t)
        c.restoreState()
        c.setFillColor(HexColor("#f2e9d8"))
        c.setFont(f_gras, 12)
        c.drawCentredString(L_PAGE / 2, 252 * mm, f"Édition du {date_longue(genere_le)}")
        c.setFillColor(HexColor("#ffffff"))          # encadré blanc : « Guide » et le sceau du site
        c.rect(10 * mm, 10 * mm, 50 * mm, 22 * mm, fill=1, stroke=0)
        c.setFillColor(HexColor("#0c0a08"))
        c.setFont(f_titre_gras, 24)
        c.drawString(14 * mm, 16.5 * mm, "Guide")
        c.drawImage(embleme((140, 106, 28), 1.0, 256), 41 * mm, 13 * mm, 15 * mm, 15 * mm, mask="auto")
        c.setFillColor(HexColor("#ffffff"))
        c.setFont(f_gras, 9)
        c.drawRightString(L_PAGE - 10 * mm, 12 * mm, SITE)
        c.linkURL(LIEN_SITE, (L_PAGE - 50 * mm, 9 * mm, L_PAGE - 10 * mm, 17 * mm), relative=0)

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

    class Doc(BaseDocTemplate):
        def afterFlowable(self, f):
            if isinstance(f, TitreVersion):
                self.notify("TOCEntry", (1, f.getPlainText(), self.page))
            elif isinstance(f, TeteSerie):
                self.notify("TOCEntry", (2, f.getPlainText(), self.page))
            elif isinstance(f, Marqueur) and f.valeurs.get("niveau0"):
                self.notify("TOCEntry", (0, f.valeurs["niveau0"], self.page))
            elif isinstance(f, Paragraph) and f.style.name == "h1m":
                self.notify("TOCEntry", (0, f.getPlainText(), self.page))

    doc = Doc(str(sortie), pagesize=A4, leftMargin=MARGE_X, rightMargin=MARGE_X, topMargin=HAUT, bottomMargin=BAS,
              title="La Cote du Héros · Guide de référence", author="La Cote du Héros", subject="Cotes et jaquettes des livres dont vous êtes le héros, par éditeur et par édition",
              keywords="livres dont vous êtes le héros, livre-jeu, cote, jaquettes, lacoteduheros.fr", creator="La Cote du Héros")
    cadre = Frame(MARGE_X, BAS, L_CADRE, H_PAGE - HAUT - BAS, id="c", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate("couv", [Frame(0, 0, L_PAGE, H_PAGE, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=couverture, autoNextPageTemplate="texte"),
        PageTemplate("texte", [Frame(MARGE_X, BAS, L_CADRE, H_PAGE - 24 * mm - BAS, id="t")], onPage=fond, onPageEnd=page_texte),
        PageTemplate("ouverture", [Frame(0, 0, L_PAGE, H_PAGE, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=lambda c, d: None, onPageEnd=page_ouverture),
        PageTemplate("catalogue", [cadre], onPage=fond, onPageEnd=page_catalogue)])
    sommaire = TableOfContents()
    sommaire.levelStyles = [ParagraphStyle("t0", parent=styles["toc"], fontName=f_gras, spaceBefore=2.5 * mm, textColor=C("titre")), ParagraphStyle("t1", parent=styles["toc"], leftIndent=6 * mm, fontSize=9.5, leading=13),
                            ParagraphStyle("t2", parent=styles["toc"], leftIndent=12 * mm, fontSize=8.5, leading=11.5, textColor=C("sourdine"))]
    sommaire.dotsMinLevel = 0
    nb = sum(len(l) for _, vs in groupes for _, ss in vs for _, l in ss)
    donnees_offre = donnees if isinstance(donnees, dict) else ga.charger()
    offre_annonces = donnees_offre.get("offre", {})
    histoire = [Spacer(1, 1), NextPageTemplate("texte"), PageBreak(),
                Paragraph("Présentation", styles["h1"]), Ornement(40 * mm, C("filet")), Spacer(1, 5 * mm),
                Paragraph(f"La Cote du Héros suit les prix d'occasion des livres dont vous êtes le héros. Ce guide reprend {nb} éditions, éditeur par éditeur, puis édition par édition : "
                          "jaquette, titre, numéro, version, puis deux repères en mots : la rareté en vente et le niveau de prix.", styles["corps"]), Spacer(1, 4 * mm),
                Paragraph("Chaque mot est expliqué dans la légende. Ces repères sont ceux du " + date_longue(date_cotes) + ".", styles["corps"]),
                Spacer(1, 4 * mm), Paragraph("Le site reste gratuit ; s'il vous est utile, vous pouvez « Offrir un café » depuis le site.", styles["corps"]),
                PageBreak(), Paragraph("Légende", styles["h1"]), Ornement(40 * mm, C("filet")), Spacer(1, 4 * mm)] + legende(styles) + [
                PageBreak(), Paragraph("Sommaire", styles["h1"]), sommaire]
    if donnees is not False:
        histoire += section_analyse(versions, donnees if donnees is not None else ga.charger(), styles, date_cotes, pol, st)
    for k, (editeur, versions_ed) in enumerate(groupes):
        nom_versions = [ver for ver, _ in versions_ed]
        total = sum(len(l) for _, ss in versions_ed for _, l in ss)
        histoire += [NextPageTemplate("ouverture"), PageBreak(), Marqueur(etat, editeur=editeur, versions=nom_versions, index=k, nb=total, nv=len(nom_versions), niveau0=editeur),
                     NextPageTemplate("catalogue"), PageBreak()]
        for j, (version, series_v) in enumerate(versions_ed):
            if j:
                histoire.append(PageBreak())
            histoire += [Marqueur(etat, editeur=editeur, version=version, versions=nom_versions), TitreVersion(editeur, version, st, pol)]
            for nom, livres in series_v:
                cellules = [Fiche(v, st, pol, web, offre_annonces, reperes) for v in livres]
                while len(cellules) % COLONNES:
                    cellules.append("")
                rangs = []
                for i in range(0, len(cellules), COLONNES):
                    t = Table([cellules[i:i + COLONNES]], colWidths=[L_CADRE / COLONNES] * COLONNES, hAlign="LEFT")
                    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
                    rangs.append(t)
                tete = TeteSerie(nom, len(livres), st, pol)
                histoire += [KeepTogether([tete] + rangs[:2])] + rangs[2:]          # l'en-tête n'est jamais seul : au moins deux rangées avec lui ; une rangée n'est jamais coupée
    doc.multiBuild(histoire)
    return nb


def section_analyse(versions, donnees, styles, date_cotes, polices, st):
    """« Méthode et analyse » : méthode en termes généraux, puis un état du marché à la date du guide, SANS chiffre (que des mots), calculé sur les données :
    synthèse, nuage de points des séries, panorama par plateforme et par éditeur, points d'attention."""
    f_titre, f_titre_gras, f_texte, f_gras = polices
    cx = {"texte": HexColor(st["texte"]), "sourdine": HexColor(st["sourdine"]), "or": HexColor(st["or"]), "filet": HexColor(st["filet"]), "fond": HexColor(st["fond"]), "grille": HexColor(st["grille"])}
    P = lambda t, k="corps": Paragraph(t, styles[k])  # noqa: E731
    textes, profs = ga.textes(versions, donnees, editeur_de, EDITEURS_CONNUS)
    h = [PageBreak(), P("Méthode et analyse", "h1m"), Ornement(40 * mm, cx["filet"]), Spacer(1, 4 * mm),
         P("Les cotes sont des estimations tirées de plusieurs sources : archives, annonces en ligne et librairies. Une annonce est un prix demandé, pas un prix payé. "
           "La confiance d'une cote dépend du nombre d'observations. Une cote n'est pas un prix garanti."),
         P("Le marché en bref", "h2")]
    h += [P(t) for t in textes["synthese"]]
    h += [PageBreak(), P("Le nuage de points", "h2"),
          P("Chaque point est une série, avec son éditeur entre parenthèses. Plus il est à droite, plus l'offre en ligne est fournie ; plus il est haut, plus les cotes sont élevées. "
            "Les pointillés marquent le milieu du marché. La forme du point dit dans quel coin il se trouve : disque vide, offre faible et prix bas ; carré, offre forte et prix bas ; "
            "triangle, offre faible et prix haut (série en tension) ; disque plein, offre forte et prix haut."),
          Spacer(1, 3 * mm), ga.dessiner_nuage(profs, largeur=L_CADRE, police=f_texte, police_gras=f_gras, c=cx)]
    h += [PageBreak(), P("Par plateforme", "h2")] + [P(t) for t in textes["plateformes"]]
    h += [P("Par éditeur", "h2")] + [P(t) for t in textes["editeurs"]]
    if textes["attention"]:
        h += [P("Points d'attention", "h2")] + [P(t) for t in textes["attention"]]
    h += [P("Limites", "h2"), P("Un état du marché est une photographie à la date du guide : il décrit l'offre du moment, pas une tendance. Les phrases de cette section sont recalculées à chaque génération du guide.")]
    return h


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--sortie", default="guide-reference.pdf")
    a.add_argument("--series", default="", help="noms de séries séparés par des virgules (essai)")
    a.add_argument("--editeurs", default="", help="noms d'éditeurs séparés par des virgules (essai)")
    a.add_argument("--style", default=STYLE_PAR_DEFAUT, choices=tuple(STYLES), help="direction de style : nuit (sombre et or) ou parchemin (fond crème, pour l'impression)")
    a.add_argument("--visuel-couverture", default=COUVERTURE_PAR_DEFAUT, choices=("v1", "huile"), help="illustration de couverture : v1 (héros et dragon, par défaut) ou huile (ancienne couverture)")
    a.add_argument("--couverture", default=SOUS_TITRE_PAR_DEFAUT, choices=("clair", "bandeau"), help="variante du sous-titre de la couverture « huile »")
    a.add_argument("--mention-sorciers", action="store_true", help="ajoute la mention « Document réservé aux sorciers… » en pied de page (option)")
    args = a.parse_args(argv)
    debut = time.time()
    versions = json.loads((WEB / "data" / "versions.json").read_text(encoding="utf-8"))
    meta = json.loads((WEB / "data" / "meta.json").read_text(encoding="utf-8"))
    series = {s.strip() for s in args.series.split(",") if s.strip()} or None
    editeurs = {s.strip() for s in args.editeurs.split(",") if s.strip()} or None
    nb = construire(versions, args.sortie, meta.get("genere_le") or date.today().isoformat(), series, editeurs=editeurs, sous_titre=args.couverture, style=args.style, mention=args.mention_sorciers, visuel=args.visuel_couverture)
    print(f"{nb} livres, {Path(args.sortie).stat().st_size // 1024} Ko, {time.time() - debut:.1f} s : {args.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
