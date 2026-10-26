"""Réconciliation par image : une annonce eBay est rattachée à l'édition dont la jaquette lui ressemble le plus.

Empreinte perceptuelle (dHash, 64 bits) : une image réduite en niveaux de gris, 9 × 8 pixels, comparée à ses voisines.
Deux images qui se ressemblent (même jaquette, photo plus petite ou plus sombre) donnent presque les mêmes bits.
Une édition n'est retenue que si elle est nettement plus proche que les autres éditions du même livre ; sinon l'annonce
reste attribuée comme avant (règles de ecarter_ambigues)."""
import io

import requests
from PIL import Image

SEUIL = 12        # distance de Hamming au-delà de laquelle deux images ne sont pas la même jaquette (sur 64 bits)
MARGE = 6         # la meilleure édition doit être plus proche d'au moins cette distance que la deuxième
DELAI = 10        # secondes


def dhash(image):
    g = image.convert("L").resize((9, 8), Image.LANCZOS)
    px = g.load()
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | (1 if px[x, y] > px[x + 1, y] else 0)
    return bits


def distance(a, b):
    return bin(a ^ b).count("1")


def empreinte_fichier(chemin):
    try:
        with Image.open(chemin) as im:
            return dhash(im)
    except (OSError, ValueError):
        return None


def empreinte_annonce(item, http=requests):
    """Empreinte de la photo de l'annonce (URL donnée par eBay), ou None si elle n'est pas lisible."""
    url = ((item.get("image") or {}).get("imageUrl")) or ((item.get("thumbnailImages") or [{}])[0].get("imageUrl"))
    if not url:
        return None
    try:
        r = http.get(url, timeout=DELAI)
        if r.status_code != 200:
            return None
        with Image.open(io.BytesIO(r.content)) as im:
            return dhash(im)
    except (requests.RequestException, OSError, ValueError, IndexError):
        return None


def choisir_edition(empreinte, candidats):
    """candidats : {isbn: empreinte de sa jaquette}. Renvoie l'ISBN de l'édition retenue, ou None si le choix n'est pas sûr."""
    if empreinte is None:
        return None
    classees = sorted((distance(empreinte, e), isbn) for isbn, e in candidats.items() if e is not None)
    if not classees or classees[0][0] > SEUIL:
        return None
    if len(classees) > 1 and classees[1][0] - classees[0][0] < MARGE:
        return None
    return classees[0][1]


def reconcilier(par_isbn, livres, dossier_covers, http=requests):
    """par_isbn : {isbn: [annonces]} (sortie de retenues). livres : {isbn: livre}. Une annonce qui apparaît sous plusieurs
    éditions d'un même livre n'est gardée que sous l'édition dont la jaquette lui ressemble, si le choix est sûr."""
    par_livre = {}
    for isbn in par_isbn:
        par_livre.setdefault(livres.get(isbn), []).append(isbn)
    empreintes = {}

    def jaquette(isbn):
        if isbn not in empreintes:
            empreintes[isbn] = empreinte_fichier(dossier_covers / "small" / f"{isbn}.webp")
        return empreintes[isbn]

    for livre, isbns in par_livre.items():
        if livre is None or len(isbns) < 2:
            continue
        candidats = {i: jaquette(i) for i in isbns}
        # annonces présentes sous au moins deux éditions du même livre
        vues = {}
        for isbn in isbns:
            for it in par_isbn[isbn]:
                if it.get("itemId"):
                    vues.setdefault(it["itemId"], []).append(isbn)
        for item_id, ou in vues.items():
            if len(set(ou)) < 2:
                continue
            item = next(it for isbn in ou for it in par_isbn[isbn] if it.get("itemId") == item_id)
            retenue = choisir_edition(empreinte_annonce(item, http), {i: candidats[i] for i in set(ou)})
            if retenue is None:
                continue
            for isbn in set(ou):
                if isbn != retenue:
                    par_isbn[isbn] = [it for it in par_isbn[isbn] if it.get("itemId") != item_id]
    return par_isbn
