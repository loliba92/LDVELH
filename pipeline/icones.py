"""Fabrique les icônes du site (onglet, application, écran d'accueil) à partir de l'emblème doré.

    python pipeline/icones.py

Source : docs/icones-propositions/source-mage-or.png (or sur noir). Le noir est remplacé par le brun du site,
puis l'emblème est découpé en rond et décliné : icônes de l'application (192 et 512, plus une version
« maskable » pour Android), icône iPhone (180), favicons (16, 32, 48 et .ico).
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

RACINE = Path(__file__).resolve().parent.parent
SOURCE = RACINE / "docs" / "icones-propositions" / "source-mage-or.png"
SORTIE = RACINE / "web" / "icons"
CENTRE, RAYON = (620, 606), 541                      # anneau de l'emblème dans l'image source
BRUN = np.array([0x05, 0x05, 0x05], dtype=float)     # le noir de l'image devient un noir presque pur


def emblème():
    im = np.asarray(Image.open(SOURCE).convert("RGB"), dtype=float)
    lum = im.max(axis=2, keepdims=True) / 255
    teinte = im + BRUN * (1 - lum)                   # le brun ne vient qu'à la place du noir
    return Image.fromarray(np.clip(teinte, 0, 255).astype("uint8"))


def rond(img, taille, zoom=1.0):
    r = RAYON / zoom
    cx, cy = CENTRE
    carre = img.crop((round(cx - r), round(cy - r), round(cx + r), round(cy + r))).resize((taille, taille), Image.LANCZOS)
    masque = Image.new("L", (taille * 4, taille * 4), 0)
    ImageDraw.Draw(masque).ellipse((0, 0, taille * 4 - 1, taille * 4 - 1), fill=255)
    carre.putalpha(masque.resize((taille, taille), Image.LANCZOS))
    return carre


def sur_fond(img, taille, part):
    """Emblème rond centré sur un carré plein (icônes sans transparence)."""
    fond = Image.new("RGB", (taille, taille), tuple(int(v) for v in BRUN))
    e = rond(img, round(taille * part))
    fond.paste(e, ((taille - e.width) // 2, (taille - e.height) // 2), e)
    return fond


def main():
    img = emblème()
    SORTIE.mkdir(parents=True, exist_ok=True)
    rond(img, 512).save(SORTIE / "icon-512.png", optimize=True)
    rond(img, 192).save(SORTIE / "icon-192.png", optimize=True)
    sur_fond(img, 512, 0.74).save(SORTIE / "icon-maskable-512.png", optimize=True)   # zone de sécurité d'Android : 80 %
    sur_fond(img, 180, 0.94).save(SORTIE / "apple-touch-icon.png", optimize=True)
    # favicons : un léger zoom garde le capuchon et le regard lisibles en petit
    petits = [rond(img, t, zoom=1.12) for t in (16, 32, 48)]
    petits[1].save(SORTIE.parent / "favicon-32.png", optimize=True)
    petits[0].save(SORTIE.parent / "favicon-16.png", optimize=True)
    rond(img, 256, zoom=1.12).save(SORTIE.parent / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    for f in sorted(SORTIE.glob("*.png")) + sorted(SORTIE.parent.glob("favicon*")):
        print(f.relative_to(RACINE), f.stat().st_size // 1024, "Ko")


if __name__ == "__main__":
    main()
