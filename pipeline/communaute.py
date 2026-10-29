"""Liste de la page Communauté : ajouts et retraits envoyés par le Zagor depuis le site (lot communaute.yml).

Usage : python pipeline/communaute.py "ajout ; nom ; https://adresse ; description | retrait ; https://adresse"
Écrit web/data/communaute.json, trié par nom. Une adresse déjà présente est remplacée.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

FICHIER = Path(__file__).resolve().parent.parent / "web" / "data" / "communaute.json"
MAX_NOM = 60
MAX_DESCRIPTION = 300


def lire(chemin=FICHIER):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def adresse_valide(adresse):
    p = urlparse(adresse)
    return p.scheme == "https" and bool(p.netloc) and " " not in adresse


def appliquer(liste, commandes):
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
            liste = [x for x in liste if x["adresse"] != adresse]
            liste.append({"nom": nom, "adresse": adresse, "description": description})
        elif action == "retrait" and len(morceaux) == 2:
            liste = [x for x in liste if x["adresse"] != morceaux[1]]
        else:
            raise ValueError(f"commande inconnue : {brut!r}")
    return sorted(liste, key=lambda x: x["nom"].casefold())


def main(argv):
    if len(argv) != 2:
        print("usage : python pipeline/communaute.py \"ajout ; nom ; https://… ; description\"", file=sys.stderr)
        return 2
    try:
        liste = appliquer(lire(), argv[1])
    except ValueError as e:
        print(f"refusé : {e}", file=sys.stderr)
        return 1
    FICHIER.write_text(json.dumps(liste, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(liste)} lien(s) dans la Communauté")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
