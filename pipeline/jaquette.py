"""Jaquette d'un livre depuis l'adresse d'une image (lot jaquette.yml, envoyé par le Zagor depuis « Gestion de la fiche »).

Usage : python pipeline/jaquette.py IDENTIFIANT ADRESSE [--garder FICHIER]      télécharge une fois, vérifie, enregistre
        python pipeline/jaquette.py IDENTIFIANT --fichier FICHIER               rejoue l'enregistrement depuis l'image déjà téléchargée
Écrit web/covers/{small,medium,mini}/<clé>.webp (mêmes noms et tailles que les jaquettes existantes) et monte le numéro de version
de la jaquette dans web/data/jaquettes.json : l'export ajoute « ?v=N » à son adresse, ce qui renouvelle la copie gardée par les navigateurs.
Sobriété : une seule requête vers le site source (deux redirections au plus, chacune revérifiée) ; sur 403 ou 429, les en-têtes reçus
sont journalisés, sans nouvel essai.
"""
import io
import ipaddress
import json
import socket
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions

RACINE = Path(__file__).resolve().parent.parent
COVERS = RACINE / "web" / "covers"
VERSIONS = RACINE / "web" / "data" / "jaquettes.json"
TAILLES = {"medium": (600, 78), "small": (320, 76), "mini": (160, 65)}      # largeur en pixels, qualité webp
MAX_OCTETS = 3_000_000
MAX_PIXELS = 40_000_000
LARGEUR_MIN = 200
DELAI = (5, 15)                      # connexion, lecture (secondes)
REDIRECTIONS = 2
TYPES = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
ENTETE = {"User-Agent": "La Cote du Heros (jaquette demandee par le Zagor)", "Accept": "image/jpeg,image/png,image/webp"}


class Refus(Exception):
    """Une demande refusée : le message est affiché dans le journal du lot."""


def _interne(ip):
    a = ipaddress.ip_address(ip)
    return not a.is_global or a.is_multicast


def adresse_permise(adresse, resoudre=socket.getaddrinfo):
    """https seulement, sans identifiants ni port, ni IP littérale, ni nom interne ; le nom ne doit mener à aucune adresse privée."""
    p = urlparse(adresse)
    if p.scheme != "https" or not p.hostname or " " in adresse:
        raise Refus("adresse refusée : https uniquement")
    if p.username or p.password or p.port not in (None, 443):
        raise Refus("adresse refusée : ni identifiants ni port")
    hote = p.hostname.lower().rstrip(".")
    try:
        ipaddress.ip_address(hote)
        raise Refus("adresse refusée : une adresse IP n'est pas acceptée")
    except ValueError:
        pass
    if "." not in hote or hote == "localhost" or hote.endswith((".localhost", ".local", ".internal", ".lan", ".home", ".corp", ".intranet")):
        raise Refus("adresse refusée : nom interne")
    try:
        infos = resoudre(hote, 443, type=socket.SOCK_STREAM)
    except OSError:
        raise Refus("adresse refusée : nom introuvable")
    if not infos or any(_interne(i[4][0]) for i in infos):
        raise Refus("adresse refusée : mène à une adresse interne")
    return adresse


def telecharger(adresse, ouvrir=None, resoudre=socket.getaddrinfo):
    """(type, octets). Une requête, 2 redirections au plus, chaque étape revérifiée. 403 et 429 : en-têtes journalisés, pas de nouvel essai."""
    if ouvrir is None:
        import requests
        ouvrir = lambda u: requests.get(u, headers=ENTETE, stream=True, timeout=DELAI, allow_redirects=False)  # noqa: E731
    url = adresse
    for _ in range(REDIRECTIONS + 1):
        adresse_permise(url, resoudre)
        rep = ouvrir(url)
        try:
            if rep.status_code in (301, 302, 303, 307, 308):
                lieu = rep.headers.get("Location", "")
                if not lieu:
                    raise Refus("redirection sans destination")
                url = urljoin(url, lieu)
                continue
            if rep.status_code in (403, 429):
                print(f"HTTP {rep.status_code} reçu, pas de nouvel essai. En-têtes : {json.dumps(dict(rep.headers), ensure_ascii=False)}", file=sys.stderr)
                raise Refus(f"le site source refuse la demande (HTTP {rep.status_code})")
            if rep.status_code != 200:
                raise Refus(f"le site source répond HTTP {rep.status_code}")
            type_ = (rep.headers.get("Content-Type", "").split(";")[0]).strip().lower()
            if type_ not in TYPES:
                raise Refus(f"type refusé : {type_ or 'inconnu'} (jpeg, png ou webp attendu)")
            try:
                if int(rep.headers.get("Content-Length", "0")) > MAX_OCTETS:
                    raise Refus("image trop lourde")
            except ValueError:
                pass
            morceaux, total = [], 0
            for m in rep.iter_content(65536):
                total += len(m)
                if total > MAX_OCTETS:
                    raise Refus("image trop lourde")
                morceaux.append(m)
            return type_, b"".join(morceaux)
        finally:
            rep.close()
    raise Refus("trop de redirections")


def lire_image(octets, type_):
    """Ouvre l'image, vérifie son contenu (format réel, dimensions) et renvoie une image RVB. Rien n'est exécuté : seul Pillow décode les pixels."""
    from PIL import Image, UnidentifiedImageError
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(octets)) as im:
            if im.format != TYPES.get(type_):
                raise Refus("le contenu n'est pas une image du type annoncé")
            im.verify()
        with Image.open(io.BytesIO(octets)) as im:
            if im.width < LARGEUR_MIN or im.height < LARGEUR_MIN:
                raise Refus(f"image trop petite (au moins {LARGEUR_MIN} px)")
            return im.convert("RGB")
    except Refus:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError, SyntaxError):
        raise Refus("le contenu n'est pas une image lisible")


def edition(ident, base=None):
    """La fiche demandée, qui doit exister dans les données."""
    ident = (ident or "").strip()
    for r in editions.load(base):
        if r["id"] == ident:
            return r
    raise Refus("fiche inconnue")


def enregistrer(ident, image, base=None, covers=COVERS, versions=VERSIONS):
    """Écrit les trois tailles et monte la version. Renvoie la clé de la jaquette."""
    row = edition(ident, base)
    cle = editions.cle_image(row["id"], row.get("isbn13", ""))
    from PIL import Image
    for nom, (largeur, qualite) in TAILLES.items():
        l = min(largeur, image.width)                       # jamais d'agrandissement
        h = round(image.height * l / image.width)
        sortie = Path(covers) / nom / f"{cle}.webp"
        sortie.parent.mkdir(parents=True, exist_ok=True)
        image.resize((l, h), Image.LANCZOS).save(sortie, "WEBP", quality=qualite, method=6)
    try:
        v = json.loads(Path(versions).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        v = {}
    v[cle] = int(v.get(cle, 0)) + 1
    Path(versions).parent.mkdir(parents=True, exist_ok=True)
    Path(versions).write_text(json.dumps(v, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    return cle


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    ident, reste = argv[0], argv[1:]
    try:
        edition(ident)                                    # la fiche est vérifiée avant tout téléchargement
        if "--fichier" in reste:
            octets = Path(reste[reste.index("--fichier") + 1]).read_bytes()
            type_ = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(_format(octets), "")
        else:
            type_, octets = telecharger(reste[0])
            if "--garder" in reste:
                Path(reste[reste.index("--garder") + 1]).write_bytes(octets)
        cle = enregistrer(ident, lire_image(octets, type_))
    except Refus as e:
        print(f"Refusé : {e}")
        return 1
    except Exception as e:  # noqa: BLE001 — réseau coupé, délai : échec propre, sans nouvel essai
        print(f"Échec : {type(e).__name__} : {str(e)[:120]}")
        return 1
    print(f"Jaquette enregistrée pour {cle}.")
    return 0


def _format(octets):
    from PIL import Image
    try:
        with Image.open(io.BytesIO(octets)) as im:
            return im.format
    except Exception:  # noqa: BLE001
        return ""


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
