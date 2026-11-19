"""Guide de référence en PDF : jaquettes et cotes de tous les livres, série par série, à partir de web/data/versions.json et web/covers/.

Usage : python pipeline/guide.py [--sortie guide.pdf] [--editeurs "Scriptarium,Hachette"] [--series "Loup Solitaire"]
Plan : éditeur, puis version (V1 avant V2, ordre naturel), puis série par ordre alphabétique, livres par numéro. Une version commence toujours une nouvelle page.
Aucune requête réseau. Le PDF n'est pas gardé dans le dépôt : il se génère à la demande (voir la description de la demande de fusion).
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

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle

import guide_analyse as ga
from reportlab.platypus.tableofcontents import TableOfContents

sys.path.insert(0, str(Path(__file__).resolve().parent))
RACINE = Path(__file__).resolve().parent.parent
WEB = RACINE / "web"
COUVERTURE = Path(__file__).resolve().parent / "guide" / "couverture.jpg"
OR, FOND, FOND_DOUX, TEXTE, SOURDINE = HexColor("#d9b45f"), HexColor("#0c0a08"), HexColor("#2a2412"), HexColor("#f2e9d8"), HexColor("#b8ad99")
RARETE = {"tres_rare": "Très rare", "rare": "Rare", "peu_courant": "Peu courant", "courant": "Courant"}
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
LARGEUR_JAQUETTE_PX = 230           # jaquette « small » réduite : nette à 42 mm (environ 140 points par pouce)
COLONNES = 3


def date_longue(iso):
    d = date.fromisoformat(str(iso)[:10])
    return f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"


def euros(v):
    return "—" if v is None else f"{v:,.2f}".replace(",", " ").replace(".", ",") + " €"


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


class Secours(Flowable):
    """Cadre de remplacement d'une jaquette absente : le titre sur fond doré sombre."""
    def __init__(self, titre, largeur, hauteur, police):
        super().__init__()
        self.titre, self.largeur, self.hauteur, self.police = titre, largeur, hauteur, police

    def wrap(self, *_):
        return self.largeur, self.hauteur

    def draw(self):
        c = self.canv
        c.setFillColor(FOND_DOUX)
        c.setStrokeColor(OR)
        c.rect(0, 0, self.largeur, self.hauteur, fill=1, stroke=1)
        p = Paragraph(self.titre, ParagraphStyle("s", fontName=self.police, fontSize=10, leading=12, alignment=TA_CENTER, textColor=OR))
        w, h = p.wrap(self.largeur - 8 * mm, self.hauteur)
        p.drawOn(c, 4 * mm, (self.hauteur - h) / 2)


def fiche(v, styles, date_cotes, web=WEB, police_titre="Times-Bold"):
    """Cellule d'un livre : jaquette, titre, numéro et version, rareté, cotes C / BE / TBE."""
    from reportlab.platypus import Image as Img
    largeur = 42 * mm
    hauteur = largeur * 7 / 5
    jpeg = jaquette_jpeg(web / v["couverture"]) if v.get("couverture") else None
    if jpeg:
        with Image.open(io.BytesIO(jpeg)) as im:
            hauteur = largeur * im.height / im.width
        image = Img(io.BytesIO(jpeg), width=largeur, height=hauteur)
    else:
        image = Secours(v.get("titre") or "", largeur, hauteur, police_titre)
    num = f"n° {v['numero']} · " if v.get("numero") and str(v["numero"]).strip("0") else ""
    rare = RARETE.get((v.get("rarete") or {}).get("niveau"), "")
    p = v.get("prix") or {}
    cotes = f"C {euros(p.get('convenable'))} · BE {euros(p.get('bon'))} · TBE {euros(p.get('tres_bon'))}"
    return [image, Spacer(1, 2 * mm), Paragraph(v.get("titre") or "", styles["titre"]),
            Paragraph(f"{num}{v.get('version') or ''}{' · ' + rare if rare else ''}", styles["meta"]), Paragraph(cotes, styles["cotes"])]


def _tableau(lignes, f_texte, f_gras, largeurs):
    t = Table(lignes, colWidths=largeurs, hAlign="LEFT")
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), f_texte), ("FONTNAME", (0, 0), (-1, 0), f_gras), ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("TEXTCOLOR", (0, 0), (-1, -1), TEXTE),
                           ("TEXTCOLOR", (0, 0), (-1, 0), OR), ("LINEBELOW", (0, 0), (-1, 0), 0.5, SOURDINE), ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("TOPPADDING", (0, 0), (-1, -1), 2.5)]))
    return t


def section_analyse(versions, donnees, styles, date_cotes, polices):
    """« Méthode et analyse » : méthode en termes généraux, nuage de points, état du marché. Les chiffres et phrases d'analyse sont calculés sur les données."""
    f_texte, f_gras = polices
    P = lambda t, st="corps": Paragraph(t, styles[st])  # noqa: E731
    pts = ga.points(versions, donnees["offre"])
    h = [PageBreak(), P("Méthode et analyse", "h1m"),
         P("Les cotes sont des estimations tirées de plusieurs sources : archives, annonces en ligne et librairies. Une annonce est un prix demandé, pas un prix payé. "
           "La confiance d'une cote dépend du nombre d'observations. Une cote n'est pas un prix garanti."),
         P("Le nuage de points", "h2"),
         P("Chaque point est une édition. Plus il est à droite, plus il y a d'annonces en ligne ; plus il est haut, plus la cote est élevée. Les pointillés marquent les médianes de toutes les éditions. "
           "La forme du point dit dans quel coin il se trouve : disque vide, bon marché et peu d'annonces ; carré, bon marché et beaucoup d'annonces ; triangle, cher et peu d'annonces ; disque plein, cher et beaucoup d'annonces."),
         Spacer(1, 3 * mm), ga.dessiner_nuage(pts, police=f_texte, police_gras=f_gras), Spacer(1, 2 * mm)]
    h += [P(t) for t in ga.phrases_nuage(pts)]
    t = donnees["tendances"]
    h += [PageBreak(), P("État du marché", "h1m")]
    glob = (t.get("global") or {}).get("marche")
    depart_fin = ga.indice_actuel(t)
    if glob:
        h.append(P(f"Depuis l'{t.get('reference', 'ancien relevé')}, {glob['n']} cotes ont été comparées : variation médiane {ga.pct(glob['mediane'])}, "
                   f"{glob['hausses']} en hausse, {glob['baisses']} en baisse, {glob['stables']} stables."))
    if depart_fin:
        a, b = depart_fin
        h.append(P(f"L'indice des cotes est passé de {str(a['indice']).replace('.', ',')} le {date_longue(a['date'])} à {str(b['indice']).replace('.', ',')} le {date_longue(b['date'])}."))
    for titre, nom, filtre in (("Par version", "version", None), ("Par éditeur", "editeur", lambda c: c in ga.EDITEURS_TENDANCE)):
        lignes = ga.lignes_tendance(t, filtre, nom)
        if lignes:
            h += [P(titre, "h2"), _tableau([["", "Éditions", "Variation médiane", "Hausses", "Baisses"]] + [[c, str(n), ga.pct(m), str(hh), str(bb)] for c, n, m, hh, bb in lignes], f_texte, f_gras,
                                         [48 * mm, 24 * mm, 38 * mm, 22 * mm, 22 * mm])]
    tr = ga.repartition_tranches(versions)
    total = sum(n for _, n in tr) or 1
    h += [P("Répartition des éditions par cote", "h2"), _tableau([["Cote (très bon état, sinon bon état)", "Éditions", "Part"]] + [[nom, str(n), f"{round(100 * n / total)} %"] for nom, n in tr], f_texte, f_gras, [70 * mm, 24 * mm, 24 * mm])]
    hausses, baisses = ga.grands_mouvements(donnees["mouvements"])
    for titre, liste in (("Plus fortes hausses de cote du dernier relevé", hausses), ("Plus fortes baisses de cote du dernier relevé", baisses)):
        if liste:
            h += [P(titre, "h2"), _tableau([["Livre", "Version", "Avant", "Après", "Variation"]] + [[ti[:34], v, euros(a), euros(b), ga.pct(pc)] for ti, v, a, b, pc in liste], f_texte, f_gras,
                                          [66 * mm, 18 * mm, 24 * mm, 24 * mm, 24 * mm])]
    h += [P("Limites", "h2"), P("Une cote est un ordre de grandeur, à la date indiquée : l'état réel d'un exemplaire peut l'éloigner. Les chiffres de cette section sont recalculés à chaque génération du guide.")]
    return h


def construire(versions, sortie, date_cotes, series=None, web=WEB, genere_le=None, editeurs=None, donnees=None, sous_titre="clair"):
    """Écrit le PDF. Renvoie le nombre de livres."""
    genere_le = genere_le or date.today().isoformat()
    groupes = grouper(versions, series, editeurs)
    dossier = tempfile.mkdtemp(prefix="guide-polices-")
    f_titre, f_titre_gras, f_texte, f_gras = polices(dossier)
    styles = {
        "titre": ParagraphStyle("titre", fontName=f_gras, fontSize=8.6, leading=10.4, textColor=TEXTE, alignment=TA_CENTER),
        "meta": ParagraphStyle("meta", fontName=f_texte, fontSize=7.6, leading=9.4, textColor=SOURDINE, alignment=TA_CENTER),
        "cotes": ParagraphStyle("cotes", fontName=f_gras, fontSize=7.6, leading=9.4, textColor=OR, alignment=TA_CENTER),
        "version": ParagraphStyle("version", fontName=f_titre_gras, fontSize=26, leading=30, textColor=OR, spaceAfter=4 * mm),
        "serie": ParagraphStyle("serie", fontName=f_titre_gras, fontSize=17, leading=20, textColor=OR, spaceBefore=4 * mm, spaceAfter=3 * mm, keepWithNext=1),
        "corps": ParagraphStyle("corps", fontName=f_texte, fontSize=11, leading=16, textColor=TEXTE),
        "h1": ParagraphStyle("h1", fontName=f_titre_gras, fontSize=30, leading=34, textColor=OR, spaceAfter=8 * mm),
        "h1m": ParagraphStyle("h1m", fontName=f_titre_gras, fontSize=30, leading=34, textColor=OR, spaceAfter=6 * mm),
        "h2": ParagraphStyle("h2", fontName=f_titre_gras, fontSize=17, leading=20, textColor=OR, spaceBefore=5 * mm, spaceAfter=2 * mm, keepWithNext=1),
        "toc": ParagraphStyle("toc", fontName=f_texte, fontSize=10.5, leading=15, textColor=TEXTE),
    }
    pied = f"La Cote du Héros · Guide de référence · généré le {date_longue(genere_le)}"

    def fond(c, doc):
        c.setFillColor(FOND)
        c.rect(0, 0, *A4, fill=1, stroke=0)
        c.setFont(f_texte, 8)
        c.setFillColor(SOURDINE)
        c.drawString(18 * mm, 10 * mm, pied)
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"page {doc.page}")

    def couverture(c, doc):
        c.drawImage(str(COUVERTURE), 0, 0, A4[0], A4[1])
        if sous_titre == "bandeau":          # variante : sous-titre doré sur un bandeau sombre
            c.saveState()
            c.setFillColor(HexColor("#0c0a08"), alpha=0.72)
            c.rect(0, A4[1] - 70 * mm, A4[0], 13 * mm, fill=1, stroke=0)
            c.restoreState()
        for decalage, couleur in ((0.6 * mm, FOND), (0, OR)):          # ombre sombre sous le texte doré : lisible sur l'illustration
            c.setFillColor(couleur)
            c.setFont(f_titre_gras, 54)
            c.drawCentredString(A4[0] / 2 + decalage, A4[1] - 48 * mm - decalage, "La Cote du Héros")
            if sous_titre == "clair":          # variante : sous-titre plus grand, en gras, ombre renforcée
                for dx, dy in ((0.9 * mm, -0.9 * mm), (-0.9 * mm, -0.9 * mm), (0, -1.2 * mm)) if couleur == FOND else ((0, 0),):
                    c.setFillColor(couleur)
                    c.setFont(f_gras, 22)
                    c.drawCentredString(A4[0] / 2 + dx, A4[1] - 63 * mm + dy, "Guide de référence")
            else:
                c.setFont(f_titre_gras, 26)
                c.drawCentredString(A4[0] / 2 + decalage, A4[1] - 63 * mm - decalage, "Guide de référence")
            c.setFillColor(couleur)
            c.setFont(f_gras, 12)
            c.drawCentredString(A4[0] / 2 + decalage, 18 * mm - decalage, f"Édition du {date_longue(genere_le)}")

    class Doc(BaseDocTemplate):
        def afterFlowable(self, f):
            if isinstance(f, Paragraph) and f.style.name == "version":
                if getattr(f, "editeur", None):
                    self.notify("TOCEntry", (0, f.editeur, self.page))
                self.notify("TOCEntry", (1, f.getPlainText(), self.page))
            elif isinstance(f, Paragraph) and f.style.name == "h1m":
                self.notify("TOCEntry", (0, f.getPlainText(), self.page))
            elif isinstance(f, Paragraph) and f.style.name == "serie":
                self.notify("TOCEntry", (2, f.getPlainText(), self.page))

    doc = Doc(str(sortie), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
              title="La Cote du Héros : guide de référence", author="La Cote du Héros")
    cadre = Frame(18 * mm, 18 * mm, A4[0] - 36 * mm, A4[1] - 34 * mm, id="c")
    doc.addPageTemplates([PageTemplate("couv", [Frame(0, 0, 1, 1)], onPage=couverture, autoNextPageTemplate="page"), PageTemplate("page", [cadre], onPage=fond)])
    sommaire = TableOfContents()
    sommaire.levelStyles = [ParagraphStyle("t0", parent=styles["toc"], fontName=f_gras, spaceBefore=2.5 * mm), ParagraphStyle("t1", parent=styles["toc"], leftIndent=6 * mm, fontSize=9.5, leading=13),
                            ParagraphStyle("t2", parent=styles["toc"], leftIndent=12 * mm, fontSize=8.5, leading=11.5, textColor=SOURDINE)]
    sommaire.dotsMinLevel = 0
    nb = sum(len(l) for _, vs in groupes for _, ss in vs for _, l in ss)
    histoire = [Spacer(1, 1), PageBreak(),
                Paragraph("Présentation", styles["h1"]),
                Paragraph(f"La Cote du Héros suit les prix d'occasion des livres dont vous êtes le héros. Ce guide reprend {nb} éditions, série par série : "
                          "jaquette, titre, numéro, version, rareté et cotes.", styles["corps"]), Spacer(1, 4 * mm),
                Paragraph("C = convenable, BE = bon état, TBE = très bon état. Les cotes sont des estimations, à la date du " + date_longue(date_cotes) + ".", styles["corps"]),
                Spacer(1, 4 * mm), Paragraph("Le site reste gratuit ; s'il vous est utile, vous pouvez « Offrir un café » depuis le site.", styles["corps"]),
                PageBreak(), Paragraph("Sommaire", styles["h1"]), sommaire]
    if donnees is not False:
        histoire += section_analyse(versions, donnees if donnees is not None else ga.charger(), styles, date_cotes, (f_texte, f_gras))
    for editeur, versions_ed in groupes:
        for k, (version, series_v) in enumerate(versions_ed):
            titre = Paragraph(f"{editeur} · {version}", styles["version"])
            titre.editeur = editeur if k == 0 else None
            histoire += [PageBreak(), titre]
            for nom, livres in series_v:
                histoire.append(Paragraph(nom, styles["serie"]))
                cellules = [fiche(v, styles, date_cotes, web, f_titre_gras) for v in livres]
                while len(cellules) % COLONNES:
                    cellules.append("")
                lignes = [cellules[i:i + COLONNES] for i in range(0, len(cellules), COLONNES)]
                t = Table(lignes, colWidths=[(A4[0] - 36 * mm) / COLONNES] * COLONNES, hAlign="CENTER")
                t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm)]))
                histoire.append(t)
    doc.multiBuild(histoire)
    return nb


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("--sortie", default="guide-reference.pdf")
    a.add_argument("--series", default="", help="noms de séries séparés par des virgules (essai)")
    a.add_argument("--editeurs", default="", help="noms d'éditeurs séparés par des virgules (essai)")
    a.add_argument("--couverture", default="clair", choices=("clair", "bandeau"), help="variante du sous-titre de couverture")
    args = a.parse_args(argv)
    debut = time.time()
    versions = json.loads((WEB / "data" / "versions.json").read_text(encoding="utf-8"))
    meta = json.loads((WEB / "data" / "meta.json").read_text(encoding="utf-8"))
    series = {s.strip() for s in args.series.split(",") if s.strip()} or None
    editeurs = {s.strip() for s in args.editeurs.split(",") if s.strip()} or None
    nb = construire(versions, args.sortie, meta.get("genere_le") or date.today().isoformat(), series, editeurs=editeurs, sous_titre=args.couverture)
    print(f"{nb} livres, {Path(args.sortie).stat().st_size // 1024} Ko, {time.time() - debut:.1f} s : {args.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
