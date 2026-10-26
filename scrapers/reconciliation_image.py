"""Réconciliation par image : la photo d'une annonce désigne l'édition dont la jaquette lui ressemble.

Méthode reprise de la vérification photo du bot Leboncoin (dépôt privé lbc-cote, config/jaquette.py) :
- points caractéristiques SIFT de la photo et de chaque jaquette, appariés, puis homographie (RANSAC) ;
- une édition n'est retenue que si elle compte nettement plus de points concordants que la suivante ;
- pour départager deux éditions qui partagent la même illustration, la photo remise à plat est comparée à la jaquette
  (corrélation de la mise en page) ;
- une photo sans rapport avec les jaquettes, ou une mise en page très différente, n'est jamais attribuée.
En cas de doute, la fonction renvoie None et l'annonce garde l'attribution d'avant."""
import io

import numpy as np
import requests
from PIL import Image

try:
    import cv2

    DISPONIBLE = hasattr(cv2, "SIFT_create")
except Exception:  # noqa: BLE001 - OpenCV absent : la réconciliation reste inactive, sans erreur
    cv2 = None
    DISPONIBLE = False

SEUIL_INLIERS = 12          # points concordants minimaux pour décider
SEUIL_RATIO = 2.0           # la meilleure édition doit en compter au moins deux fois plus que la suivante
SEUIL_SANS_RAPPORT = 4      # au plus ce nombre de points avec toutes les éditions : la photo n'a aucun rapport
VETO_RESSEMBLANCE = 0.4     # mise en page très différente : refus même si les points concordent
SEUIL_RESSEMBLANCE = 0.6    # corrélation minimale pour départager deux éditions au même dessin
ECART_RESSEMBLANCE = 0.2    # avance minimale sur l'édition suivante pour ce départage
MAX_DIM = 900               # taille maximale de calcul (sans perte utile)
TAILLE_MAX = 4_000_000      # octets
DELAI = 20                  # secondes

_descripteurs = {}


def disponible():
    return DISPONIBLE


def _image(octets):
    """Image OpenCV (BGR) décodée avec Pillow (WebP, JPEG, PNG), réduite si elle est trop grande."""
    with Image.open(io.BytesIO(octets)) as im:
        rgb = np.array(im.convert("RGB"))
    img = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    h, w = img.shape[:2]
    if max(h, w) > MAX_DIM:
        echelle = MAX_DIM / max(h, w)
        img = cv2.resize(img, (int(w * echelle), int(h * echelle)))
    return img


def _caracteristiques(img):
    return cv2.SIFT_create(nfeatures=2000).detectAndCompute(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), None)


def _jaquette(chemin):
    """Points caractéristiques et image d'une jaquette locale (gardés en mémoire pendant le relevé)."""
    cle = str(chemin)
    if cle not in _descripteurs:
        with open(chemin, "rb") as f:
            img = _image(f.read())
        kp, d = _caracteristiques(img)
        _descripteurs[cle] = (kp, d, img)
    return _descripteurs[cle]


def _correspondance(kp1, d1, kp2, d2):
    """(points concordants, homographie photo -> jaquette ou None)."""
    if d1 is None or d2 is None or len(kp1) < 8 or len(kp2) < 8 or len(d2) < 2:
        return 0, None
    bons = [m for m, n in cv2.BFMatcher().knnMatch(d1, d2, k=2) if m.distance < 0.75 * n.distance]
    if len(bons) < 8:
        return len(bons) // 4, None
    p1 = np.float32([kp1[m.queryIdx].pt for m in bons])
    p2 = np.float32([kp2[m.trainIdx].pt for m in bons])
    homographie, masque = cv2.findHomography(p1, p2, cv2.RANSAC, 5.0)
    return (int(masque.sum()) if masque is not None else 0), homographie


def _ressemblance(photo, jaquette, homographie):
    """Corrélation (0 à 1) de la photo remise à plat avec la jaquette, ou None si la photo ne couvre pas assez la jaquette."""
    if homographie is None:
        return None
    h, w = jaquette.shape[:2]
    plate = cv2.warpPerspective(photo, homographie, (w, h))
    zone = cv2.warpPerspective(np.full(photo.shape[:2], 255, np.uint8), homographie, (w, h))
    zone = cv2.erode(zone, np.ones((9, 9), np.uint8))
    if (zone > 0).mean() < 0.5:
        return None
    gris = lambda im: cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 1.5)
    a, b = gris(plate)[zone > 0].astype(np.float32), gris(jaquette)[zone > 0].astype(np.float32)
    a -= a.mean()
    b -= b.mean()
    return round(float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6)), 3)


def decider(octets, jaquettes):
    """jaquettes : {isbn: chemin de sa jaquette}. Renvoie (isbn retenu ou None, détail des scores)."""
    if not DISPONIBLE or not octets or not jaquettes:
        return None, {}
    try:
        photo = _image(octets)
    except (OSError, ValueError):
        return None, {}
    kp, d = _caracteristiques(photo)
    scores, ressemblances = {}, {}
    for isbn, chemin in jaquettes.items():
        try:
            kp2, d2, jaq = _jaquette(chemin)
        except (OSError, ValueError):
            continue
        scores[isbn], homographie = _correspondance(kp, d, kp2, d2)
        if scores[isbn] >= 8:
            ressemblances[isbn] = _ressemblance(photo, jaq, homographie)
    tri = sorted(scores.items(), key=lambda kv: -kv[1])
    if not tri:
        return None, scores
    meilleure, premier = tri[0]
    second = tri[1][1] if len(tri) > 1 else 0
    nette = premier >= SEUIL_INLIERS and premier >= SEUIL_RATIO * max(second, 1)
    if nette and ressemblances.get(meilleure) is not None and ressemblances[meilleure] < VETO_RESSEMBLANCE:
        nette = False
    if not nette and premier >= SEUIL_INLIERS:
        r = sorted(((i, c) for i, c in ressemblances.items() if c is not None), key=lambda x: -x[1])
        if r and r[0][0] == meilleure and r[0][1] >= SEUIL_RESSEMBLANCE and (len(r) < 2 or r[0][1] - r[1][1] >= ECART_RESSEMBLANCE):
            nette = True
    return (meilleure if nette else None), scores


def meme_jaquette(octets, chemin):
    """La photo (ou la jaquette affichée par une fiche) montre-t-elle la jaquette de notre édition ?"""
    if not DISPONIBLE or not octets or not chemin:
        return True              # sans moyen de comparer, on ne retire rien
    isbn, scores = decider(octets, {"x": chemin})
    return bool(scores) and scores.get("x", 0) >= SEUIL_INLIERS


def empreinte_annonce(item, http=requests):
    """Octets de la photo de l'annonce (URL donnée par eBay), ou None si elle n'est pas lisible."""
    url = ((item.get("image") or {}).get("imageUrl")) or ((item.get("thumbnailImages") or [{}])[0].get("imageUrl"))
    if not url:
        return None
    try:
        r = http.get(url, timeout=DELAI)
        if r.status_code != 200 or len(r.content) > TAILLE_MAX:
            return None
        return r.content
    except (requests.RequestException, IndexError):
        return None


def jaquette_locale(dossier_covers, isbn):
    """Chemin de la jaquette de notre édition (grande si elle existe, sinon petite), ou None."""
    for taille in ("medium", "small"):
        chemin = dossier_covers / taille / f"{isbn}.webp"
        if chemin.exists():
            return chemin
    return None


def reconcilier(par_isbn, livres, dossier_covers, http=requests):
    """par_isbn : {isbn: [annonces]} (sortie de retenues). livres : {isbn: livre}. Une annonce vue sous plusieurs éditions
    d'un même livre n'est gardée que sous l'édition que sa photo désigne, si le choix est sûr."""
    if not DISPONIBLE:
        return par_isbn
    par_livre = {}
    for isbn in par_isbn:
        par_livre.setdefault(livres.get(isbn), []).append(isbn)
    for livre, isbns in par_livre.items():
        if livre is None or len(isbns) < 2:
            continue
        jaquettes = {i: jaquette_locale(dossier_covers, i) for i in isbns}
        jaquettes = {i: c for i, c in jaquettes.items() if c}
        vues = {}
        for isbn in isbns:
            for it in par_isbn[isbn]:
                if it.get("itemId"):
                    vues.setdefault(it["itemId"], []).append(isbn)
        for item_id, ou in vues.items():
            ensemble = set(ou)
            if len(ensemble) < 2:
                continue
            item = next(it for isbn in ou for it in par_isbn[isbn] if it.get("itemId") == item_id)
            retenu, _ = decider(empreinte_annonce(item, http), {i: jaquettes[i] for i in ensemble if i in jaquettes})
            if retenu is None:
                continue
            for isbn in ensemble:
                if isbn != retenu:
                    par_isbn[isbn] = [it for it in par_isbn[isbn] if it.get("itemId") != item_id]
    return par_isbn


def verifier_titre_seul(par_isbn, dossier_covers, http=requests):
    """Une annonce trouvée seulement par le titre n'est gardée que si sa photo montre la jaquette de l'édition à laquelle
    elle est rattachée. Sans photo lisible, ou sans jaquette de notre côté, elle est écartée : on ne la vérifie pas."""
    if not DISPONIBLE:
        return par_isbn
    for isbn, items in par_isbn.items():
        jaquette = jaquette_locale(dossier_covers, isbn)
        gardees = []
        for it in items:
            if not it.get("_titre_seul"):
                gardees.append(it)
                continue
            if jaquette is None:
                continue
            octets = empreinte_annonce(it, http)
            if octets is None:
                continue
            retenu, _ = decider(octets, {isbn: jaquette})
            if retenu == isbn:
                gardees.append(it)
        par_isbn[isbn] = gardees
    return par_isbn
