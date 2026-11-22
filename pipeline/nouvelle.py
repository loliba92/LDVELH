"""Nouvelle du site, de l'idée à la publication : page, images, carte de la Communauté et flux RSS.

Usage : python pipeline/nouvelle.py --titre "…" --phrase "…" --texte "…" [--texte-facebook "…"] [--description "…"] [--fond dragon-rouge] [--date AAAA-MM-JJ] [--slug mon-article] [--apercu DOSSIER]
Chaque option se lit aussi dans la variable d'environnement NOUVELLE_<OPTION> (titre, phrase, texte, texte_facebook, description, fond, date, slug). Depuis le site : le Zagor remplit le formulaire de la page Communauté, le service technique lance .github/workflows/nouvelle.yml, qui passe les champs par ces variables d'environnement.

Écrit : web/<slug>.html, web/images/<slug>.webp, web/data/communaute/<slug>-partage.jpg et <slug>.jpg, une entrée en tête de web/data/communaute.json,
puis reconstruit web/nouvelles.xml (pipeline/flux_nouvelles.py). Avec --apercu, seules les trois images sont écrites, dans le dossier donné.
Texte de l'article : paragraphes séparés par une ligne vide ; « ## Titre » ; lignes « - puce » ou « 1. étape » ; **gras** ; [texte](adresse).
Aucune demande à un site distant.
"""
import argparse
import contextlib
import html
import io
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RACINE = Path(__file__).resolve().parent.parent
WEB = RACINE / "web"
COMMUNAUTE = WEB / "data" / "communaute.json"
MODELE = Path(__file__).resolve().parent / "modeles" / "nouvelle.html"
BASE = "https://lacoteduheros.fr/"
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
OR = (217, 180, 95)
CREME = (246, 236, 216)

# Illustrations de fond : (fichier, position du cadrage « x% y% »). Le texte est lu sur la gauche : l'illustration se voit à droite.
FONDS = {
    "dragon-rouge": ("web/images/accueil-1.webp", (55, 35), "Un sorcier face à un dragon rouge"),
    "sorcier-dragon": ("web/images/accueil-3.webp", (60, 40), "Un sorcier face à un dragon"),
    "dragon-noir": ("web/images/accueil-2.webp", (60, 30), "Un sorcier dans l'ombre d'un dragon noir"),
    "duel-neige": ("web/images/accueil-4.webp", (50, 45), "Un duel au coucher du soleil"),
    "duel-ruines": ("web/images/accueil-5.webp", (50, 45), "Un duel dans des ruines"),
    "golem": ("web/images/accueil-6.webp", (70, 50), "Un guerrier face à un golem de lave"),
    "glace": ("web/images/projet-glace.webp", (50, 40), "Un guerrier face à un géant des glaces"),
    "hydre": ("web/images/projet-hydre.webp", (50, 55), "Une hydre attaque un navire"),
    "heros-dragon": ("pipeline/guide/couverture-v1.jpg", (50, 22), "Un héros brandit son épée face à un dragon"),
}
FOND_PAR_DEFAUT = "dragon-rouge"

_polices = {}


def _police(nom, taille):
    """Cormorant Garamond gras (titre) ou Source Sans 3 moyen (phrase), tirés des polices du site."""
    dossier = Path(tempfile.gettempdir()) / "cdh-polices"
    dossier.mkdir(exist_ok=True)
    fichier, graisse = {"titre": ("cormorant-garamond.woff2", 700), "texte": ("source-sans-3.woff2", 500)}[nom]
    chemin = dossier / f"{nom}-{graisse}.ttf"
    if not chemin.exists():
        from fontTools.ttLib import TTFont
        from fontTools.varLib import instancer
        police = instancer.instantiateVariableFont(TTFont(WEB / "fonts" / fichier), {"wght": graisse})
        police.flavor = None
        police.save(chemin)
    cle = (nom, round(taille))
    if cle not in _polices:
        _polices[cle] = ImageFont.truetype(str(chemin), round(taille))
    return _polices[cle]


def _fond(chemin, position, taille):
    """L'illustration remplit tout le cadre (comme « cover »), cadrée selon `position` (pourcentages x, y)."""
    im = Image.open(RACINE / chemin).convert("RGB")
    L, H = taille
    echelle = max(L / im.width, H / im.height)
    im = im.resize((max(L, round(im.width * echelle)), max(H, round(im.height * echelle))), Image.LANCZOS)
    x = round((im.width - L) * position[0] / 100)
    y = round((im.height - H) * position[1] / 100)
    return im.crop((x, y, x + L, y + H))


def _degrade(taille, couleur, arrets, axe):
    """Calque RGBA : dégradé de `couleur`, opacité interpolée entre les `arrets` [(position 0-1, opacité)] le long de l'axe « x » ou « y »."""
    L, H = taille
    n = L if axe == "x" else H
    pos = np.array([a[0] for a in arrets])
    alpha = np.interp(np.linspace(0, 1, n), pos, [a[1] for a in arrets])
    plan = np.tile(alpha[None, :], (H, 1)) if axe == "x" else np.tile(alpha[:, None], (1, L))
    calque = np.zeros((H, L, 4), dtype=np.uint8)
    calque[..., :3] = couleur
    calque[..., 3] = np.clip(plan * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(calque, "RGBA")


def _lignes(texte, police, largeur_max):
    """Retour à la ligne : respecte les sauts de ligne voulus, puis coupe aux espaces."""
    sortie = []
    for bloc in texte.split("\n"):
        courante = ""
        for mot in [m for m in re.split(r"[ \t]+", bloc) if m]:          # seules les espaces ordinaires coupent : une espace insécable garde « 3 mois » ensemble
            essai = f"{courante} {mot}".strip()
            if police.getlength(essai) <= largeur_max or not courante:
                courante = essai
            else:
                sortie.append(courante)
                courante = mot
        sortie.append(courante)
    return sortie


def affiche(titre, phrase, fond, taille=(1200, 630)):
    """Image de la nouvelle : illustration, dégradé noir, icône du site en haut, filet et cadre dorés, un titre en grand et une phrase."""
    chemin, position, _ = FONDS[fond]
    L, H = taille
    im = _fond(chemin, position, taille).convert("RGBA")
    noir, presque = (0, 0, 0), (4, 3, 2)
    for calque in (_degrade(taille, noir, [(0, 0), (0.52, 0), (1, 0.8)], "y"),
                   _degrade(taille, presque, [(0, 0.97), (0.38, 0.92), (0.62, 0.64), (1, 0.14)], "x"),
                   _degrade(taille, noir, [(0, 0.72), (0.30, 0), (1, 0)], "y")):
        im = Image.alpha_composite(im, calque)
    marge = L * 0.065
    # icône
    icone = Image.open(WEB / "icons" / "icon-512.png").convert("RGBA")
    cote = round(L * 0.084)
    icone = icone.resize((cote, cote), Image.LANCZOS)
    ombre = Image.new("RGBA", taille, (0, 0, 0, 0))
    ombre.paste((0, 0, 0, 200), (round(marge), round(L * 0.042)), icone.split()[3])
    im = Image.alpha_composite(im, ombre.filter(ImageFilter.GaussianBlur(L * 0.008)))
    im.alpha_composite(icone, (round(marge), round(L * 0.042)))
    # texte : le titre (et la phrase avec lui) rétrécit jusqu'à tenir dans l'image, sur trois lignes au plus
    dispo = H - (L * 0.042 + cote + L * 0.02) - L * 0.045
    taille_titre = L * 0.064
    while True:
        taille_phrase = min(L * 0.042, taille_titre * 0.7)
        pt, pp = _police("titre", taille_titre), _police("texte", taille_phrase)
        lignes_titre, lignes_phrase = _lignes(titre, pt, L * 0.66), _lignes(phrase, pp, L * 0.62)
        h_titre = len(lignes_titre) * taille_titre * 1.0
        h_filet = L * 0.0038
        h_phrase = len(lignes_phrase) * taille_phrase * 1.28
        espace_haut, espace_bas = L * 0.02, L * 0.018
        bloc = h_titre + espace_haut + h_filet + espace_bas + h_phrase
        if (len(lignes_titre) <= 3 and len(lignes_phrase) <= 5 and bloc <= dispo) or taille_titre <= L * 0.04:
            break
        taille_titre *= 0.94
    haut = max(H * 0.61 - bloc / 2, L * 0.042 + cote + L * 0.02)
    calque_texte = Image.new("RGBA", taille, (0, 0, 0, 0))
    ecrit = ImageDraw.Draw(calque_texte)
    y = haut
    decalage_titre = taille_titre * 0.16          # la ligne de base de Cormorant est sous le haut de la boîte de ligne
    for ligne in lignes_titre:
        ecrit.text((marge, y - decalage_titre), ligne, font=pt, fill=CREME + (255,))
        y += taille_titre * 1.0
    y += espace_haut
    ecrit.rounded_rectangle((marge, y, marge + L * 0.09, y + h_filet), radius=h_filet / 2, fill=OR + (255,))
    y += h_filet + espace_bas
    decalage_phrase = taille_phrase * 0.12
    for ligne in lignes_phrase:
        ecrit.text((marge, y - decalage_phrase), ligne, font=pp, fill=(239, 227, 203, 255))
        y += taille_phrase * 1.28
    ombre_texte = Image.new("RGBA", taille, (0, 0, 0, 0))
    ombre_texte.putalpha(calque_texte.split()[3].point(lambda v: int(v * 0.7)))
    ombre_texte = ombre_texte.filter(ImageFilter.GaussianBlur(L * 0.006))
    im = Image.alpha_composite(im, ombre_texte)
    im = Image.alpha_composite(im, calque_texte)
    # cadre doré
    cadre = Image.new("RGBA", taille, (0, 0, 0, 0))
    ImageDraw.Draw(cadre).rectangle((L * 0.015, L * 0.015, L - L * 0.015, H - L * 0.015), outline=OR + (153,), width=max(2, round(L * 0.0016)))
    return Image.alpha_composite(im, cadre).convert("RGB")


def images(titre, phrase, fond):
    """(grande image 1 200 × 630, vignette de la carte 640 × 360)."""
    return affiche(titre, phrase, fond, (1200, 630)), affiche(titre, phrase, fond, (1280, 720)).resize((640, 360), Image.LANCZOS)


def identifiant(titre):
    """Nom de fichier : lettres, chiffres et tirets, sans accents."""
    s = unicodedata.normalize("NFKD", titre.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60].strip("-")


def date_longue(jour):
    d = datetime.strptime(jour, "%Y-%m-%d")
    return f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"


def _en_ligne(texte):
    """Texte d'une ligne : échappé, avec **gras** et [texte](adresse) (adresse du site, https:// ou ancre)."""
    s = html.escape(texte, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)

    def lien(m):
        cible = html.unescape(m.group(2)).strip()
        if not re.match(r"^(https://|#|[a-z0-9\-_/]+\.html(#[\w\-]+)?$)", cible):
            return m.group(0)
        return f'<a href="{html.escape(cible)}">{m.group(1)}</a>'
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lien, s)


def corps_html(texte):
    """Corps de l'article en HTML à partir du texte simple décrit en tête de fichier."""
    sortie = []
    for bloc in re.split(r"\n\s*\n", texte.strip()):
        lignes = [x.strip() for x in bloc.strip().split("\n") if x.strip()]
        if not lignes:
            continue
        if lignes[0].startswith("## "):
            sortie.append(f"<h2>{_en_ligne(lignes[0][3:].strip())}</h2>")
            lignes = lignes[1:]
            if not lignes:
                continue
        if all(x.startswith("- ") for x in lignes):
            sortie.append("<ul>\n" + "\n".join(f"  <li>{_en_ligne(x[2:].strip())}</li>" for x in lignes) + "\n</ul>")
        elif all(re.match(r"^\d+\.\s", x) for x in lignes):
            sortie.append("<ol>\n" + "\n".join(f"  <li>{_en_ligne(re.sub(r'^\d+\.\s+', '', x))}</li>" for x in lignes) + "\n</ol>")
        else:
            sortie.append(f"<p>{_en_ligne(' '.join(lignes))}</p>")
    return "\n".join(sortie)


def page(modele, titre, description, slug, alt, jour, corps):
    """Page de la nouvelle à partir du modèle (pipeline/modeles/nouvelle.html)."""
    valeurs = {"TITRE": html.escape(titre), "DESCRIPTION": html.escape(description, quote=True), "SLUG": slug, "ALT": html.escape(alt, quote=True),
               "DATE_ISO": jour, "DATE_LONGUE": date_longue(jour), "CORPS": corps, "URL_PARTAGE": quote(f"{BASE}{slug}.html", safe="")}
    return re.sub(r"@@([A-Z_]+)@@", lambda m: valeurs[m.group(1)], modele)


def ajouter_entree(liste, entree):
    """Entrée en tête de la liste de la Communauté ; refuse une adresse déjà présente."""
    if any(x.get("adresse") == entree["adresse"] for x in liste):
        raise ValueError(f"Cette nouvelle existe déjà : {entree['adresse']}")
    return [entree] + list(liste)


def verifier(titre, phrase, texte, jour, fond, slug):
    erreurs = []
    if not titre.strip():
        erreurs.append("le titre est vide")
    if not phrase.strip():
        erreurs.append("la phrase de l'image est vide")
    if not texte.strip():
        erreurs.append("le texte de l'article est vide")
    if fond not in FONDS:
        erreurs.append(f"fond inconnu « {fond} » (choix : {', '.join(FONDS)})")
    try:
        datetime.strptime(jour, "%Y-%m-%d")
    except ValueError:
        erreurs.append(f"date invalide « {jour} » (format AAAA-MM-JJ)")
    if not slug:
        erreurs.append("le nom de fichier est vide")
    return erreurs


def creer(titre, phrase, texte, fond=FOND_PAR_DEFAUT, jour=None, slug="", description="", texte_facebook="", apercu=None):
    """Écrit tous les fichiers de la nouvelle ; renvoie la liste des chemins écrits (relatifs à la racine du dépôt)."""
    jour = jour or date.today().isoformat()
    slug = identifiant(slug or titre)
    erreurs = verifier(titre, phrase, texte, jour, fond, slug)
    if erreurs:
        raise ValueError("Nouvelle refusée : " + " ; ".join(erreurs))
    grande, vignette = images(titre, phrase, fond)
    if apercu:
        dossier = Path(apercu)
        dossier.mkdir(parents=True, exist_ok=True)
        grande.save(dossier / f"{slug}-partage.jpg", quality=88, optimize=True)
        vignette.save(dossier / f"{slug}-carte.jpg", quality=88, optimize=True)
        return [str(dossier / f"{slug}-partage.jpg"), str(dossier / f"{slug}-carte.jpg")]
    if (WEB / f"{slug}.html").exists():
        raise ValueError(f"Cette page existe déjà : web/{slug}.html")
    description = (description or phrase).strip()
    alt = f"{titre} : {FONDS[fond][2].lower()}"
    liste = json.loads(COMMUNAUTE.read_text(encoding="utf-8"))
    entree = {"nom": titre.strip(), "adresse": f"{BASE}{slug}.html", "description": description, "texte_flux": (texte_facebook or f"{titre.strip()}\n\n{description}").strip(),
              "image": f"data/communaute/{slug}.jpg", "image_flux": f"data/communaute/{slug}-partage.jpg", "date": jour}
    liste = ajouter_entree(liste, entree)
    modele = MODELE.read_text(encoding="utf-8")
    fichiers = {
        f"web/{slug}.html": page(modele, titre.strip(), description, slug, alt, jour, corps_html(texte)),
    }
    for chemin, contenu in fichiers.items():
        (RACINE / chemin).write_text(contenu, encoding="utf-8")
    grande.save(WEB / "images" / f"{slug}.webp", quality=85, method=6)
    grande.save(WEB / "data" / "communaute" / f"{slug}-partage.jpg", quality=88, optimize=True)
    vignette.save(WEB / "data" / "communaute" / f"{slug}.jpg", quality=88, optimize=True)
    COMMUNAUTE.write_text(json.dumps(liste, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import flux_nouvelles
    with contextlib.redirect_stdout(io.StringIO()):          # la sortie du programme ne doit contenir que les chemins écrits
        flux_nouvelles.main()
    return [f"web/{slug}.html", f"web/images/{slug}.webp", f"web/data/communaute/{slug}-partage.jpg", f"web/data/communaute/{slug}.jpg",
            "web/data/communaute.json", "web/nouvelles.xml"]


def images_guide_du_mois(jour=None, dossier=None):
    """Images (grande et vignette) de la carte mensuelle du guide, avec le mois écrit : une par mois depuis la première édition, celles qui manquent seulement.
    Renvoie les chemins écrits."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import flux_nouvelles as fn
    jour = jour or date.today()
    dossier = Path(dossier) if dossier else WEB / "data" / "communaute"
    dossier.mkdir(parents=True, exist_ok=True)
    ecrits, (a, m) = [], fn.PREMIERE_EDITION
    while (a, m) <= (jour.year, jour.month):
        grande_f, petite_f = dossier / f"guide-{a}-{m:02d}-partage.jpg", dossier / f"guide-{a}-{m:02d}.jpg"
        if not (grande_f.exists() and petite_f.exists()):
            grande, petite = images(f"Le guide de référence\n{fn.de_mois(m)} {a}", "L'édition du mois est prête : créez votre compte gratuit, puis ouvrez le menu pour la télécharger.", "heros-dragon")
            grande.save(grande_f, quality=88, optimize=True)
            petite.save(petite_f, quality=88, optimize=True)
            ecrits += [str(grande_f), str(petite_f)]
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return ecrits


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    for nom in ("titre", "phrase", "texte", "texte_facebook", "description", "fond", "date", "slug", "apercu"):
        a.add_argument("--" + nom.replace("_", "-"), default=os.environ.get("NOUVELLE_" + nom.upper(), ""))
    a.add_argument("--guide-du-mois", action="store_true", help="crée les images de la carte mensuelle du guide qui manquent")
    a.add_argument("--jusqu-a", default="", help="avec --guide-du-mois : jour limite AAAA-MM-JJ (par défaut aujourd'hui)")
    o = a.parse_args(argv)
    if o.guide_du_mois:
        jour = datetime.strptime(o.jusqu_a, "%Y-%m-%d").date() if o.jusqu_a else None
        print("\n".join(x.replace(str(RACINE) + "/", "") for x in images_guide_du_mois(jour)))
        return 0
    try:
        chemins = creer(o.titre, o.phrase, o.texte, o.fond or FOND_PAR_DEFAUT, o.date or None, o.slug, o.description, o.texte_facebook, o.apercu or None)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    print("\n".join(chemins))
    return 0


if __name__ == "__main__":
    sys.exit(main())
