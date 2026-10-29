"""Liste de la page Communauté : ajouts et retraits envoyés par le Zagor depuis le site (lot communaute.yml).

Usage : python pipeline/communaute.py "ajout ; nom ; https://adresse ; description | retrait ; https://adresse"
Écrit web/data/communaute.json, trié par nom. Une adresse déjà présente est remplacée.
Pour un ajout, l'image du site (balise og:image) est copiée dans web/data/communaute/ ; sans image, la carte affiche une tuile.
"""
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

RACINE = Path(__file__).resolve().parent.parent
FICHIER = RACINE / "web" / "data" / "communaute.json"
DOSSIER_IMAGES = RACINE / "web" / "data" / "communaute"
MAX_NOM = 60
MAX_DESCRIPTION = 300
MAX_PAGE = 1_000_000
MAX_IMAGE = 3_000_000
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
ENTETE = {"User-Agent": "La Cote du Heros (liste Communauté)"}


def lire(chemin=FICHIER):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def adresse_valide(adresse):
    p = urlparse(adresse)
    return p.scheme == "https" and bool(p.netloc) and " " not in adresse


def image_de_page(html, base):
    """Adresse absolue de la balise og:image (ou twitter:image) de la page, ou None."""
    for balise in re.findall(r"<meta\b[^>]*>", html, flags=re.I):
        if re.search(r'(property|name)\s*=\s*["\'](og:image|twitter:image)["\']', balise, flags=re.I):
            m = re.search(r'content\s*=\s*["\']([^"\']+)["\']', balise, flags=re.I)
            if m and m.group(1).strip():
                return urljoin(base, m.group(1).strip())
    return None


def image_de_contenu(html, base):
    """Sans balise de partage : première grande image en paysage de la page (largeur d'au moins 600 px), ou None."""
    for balise in re.findall(r"<img\b[^>]*>", html, flags=re.I):
        src = re.search(r'\ssrc\s*=\s*["\']([^"\']+)["\']', balise, flags=re.I)
        larg = re.search(r'\swidth\s*=\s*["\']?(\d+)', balise, flags=re.I)
        haut = re.search(r'\sheight\s*=\s*["\']?(\d+)', balise, flags=re.I)
        if not src or not larg or not haut:
            continue
        if int(larg.group(1)) >= 600 and int(larg.group(1)) >= int(haut.group(1)):
            return urljoin(base, src.group(1).strip())
    return None


def telecharger(adresse, limite):
    req = urllib.request.Request(adresse, headers=ENTETE)
    with urllib.request.urlopen(req, timeout=10) as r:
        type_ = r.headers.get_content_type()
        return type_, r.read(limite + 1)


def chercher_image(adresse):
    """Copie l'image du site dans web/data/communaute/ et renvoie son chemin (relatif à web/), ou '' si rien."""
    try:
        _, page = telecharger(adresse, MAX_PAGE)
        html = page[:MAX_PAGE].decode("utf-8", "replace")
        url = image_de_page(html, adresse) or image_de_contenu(html, adresse)
        if not url or not adresse_valide(url):
            return ""
        type_, contenu = telecharger(url, MAX_IMAGE)
        if type_ not in EXTENSIONS or len(contenu) > MAX_IMAGE:
            return ""
        nom = hashlib.sha1(adresse.encode("utf-8")).hexdigest()[:12] + "." + EXTENSIONS[type_]
        DOSSIER_IMAGES.mkdir(parents=True, exist_ok=True)
        (DOSSIER_IMAGES / nom).write_bytes(contenu)
        return f"data/communaute/{nom}"
    except Exception:  # noqa: BLE001 — un site injoignable ne doit pas bloquer l'ajout
        return ""


def retirer_image(entree):
    chemin = entree.get("image") or ""
    if chemin.startswith("data/communaute/"):
        (RACINE / "web" / chemin).unlink(missing_ok=True)


def appliquer(liste, commandes, image=lambda adresse: ""):
    """Applique les commandes (séparées par « | ») à la liste. Lève ValueError à la première commande invalide."""
    liste = list(liste)
    for brut in commandes.split("|"):
        brut = brut.strip()
        if not brut:
            continue
        morceaux = [m.strip() for m in brut.split(" ; ", 3)]
        action = morceaux[0]
        if action == "ajout" and len(morceaux) == 4:
            nom, adresse, description = morceaux[1], morceaux[2], morceaux[3]
            if not nom or len(nom) > MAX_NOM:
                raise ValueError(f"nom invalide : {nom!r}")
            if not adresse_valide(adresse):
                raise ValueError(f"adresse refusée (https attendu) : {adresse!r}")
            if len(description) > MAX_DESCRIPTION:
                raise ValueError("description trop longue")
            for x in liste:
                if x["adresse"] == adresse:
                    retirer_image(x)
            liste = [x for x in liste if x["adresse"] != adresse]
            liste.append({"nom": nom, "adresse": adresse, "description": description, "image": image(adresse)})
        elif action == "retrait" and len(morceaux) == 2:
            for x in liste:
                if x["adresse"] == morceaux[1]:
                    retirer_image(x)
            liste = [x for x in liste if x["adresse"] != morceaux[1]]
        else:
            raise ValueError(f"commande inconnue : {brut!r}")
    return sorted(liste, key=lambda x: x["nom"].casefold())


def main(argv):
    if len(argv) != 2:
        print("usage : python pipeline/communaute.py \"ajout ; nom ; https://… ; description\"", file=sys.stderr)
        return 2
    try:
        liste = appliquer(lire(), argv[1], chercher_image)
    except ValueError as e:
        print(f"refusé : {e}", file=sys.stderr)
        return 1
    FICHIER.write_text(json.dumps(liste, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(liste)} lien(s) dans la Communauté")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
