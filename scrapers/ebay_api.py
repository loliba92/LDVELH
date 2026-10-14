"""Relevé des annonces actuelles via l'interface officielle d'eBay (Browse API).

Pour chaque édition, on cherche l'ISBN, on écarte les lots, puis on ne conserve que des agrégats
(nombre d'annonces, minimum, médiane, maximum) par état, dans data/raw/occasion/ebay-AAAA-MM-JJ.csv.
Aucun titre, vendeur ni lien d'annonce n'est enregistré.

Identifiants : variables d'environnement EBAY_CLIENT_ID et EBAY_CLIENT_SECRET (clés de production).

    python scrapers/ebay_api.py --limite 20            # essai sur 20 éditions
    python scrapers/ebay_api.py                        # toutes les éditions ayant un ISBN
"""
import argparse
import base64
import csv
import os
import re
import statistics
import sys
import time
from datetime import date
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

URL_TOKEN = "https://api.ebay.com/identity/v1/oauth2/token"
URL_RECHERCHE = "https://api.ebay.com/buy/browse/v1/item_summary/search"
PORTEE = "https://api.ebay.com/oauth/api_scope"
PAUSE = 0.5
# Codes d'état d'eBay -> états du projet. Les codes absents (neuf, « d'occasion » sans précision) sont ignorés.
ETATS = {"2750": "tres_bon", "4000": "tres_bon", "5000": "bon", "6000": "convenable"}
LOT = re.compile(r"\b(lots?|collection|set|pack|x\s?\d+|\d+\s?x|\d+\s+livres|\d+\s+tomes)\b", re.I)
CHAMPS = ["isbn13", "date", "etat", "nb_annonces", "prix_min", "prix_median", "prix_max"]


def jeton(client_id, secret, http=requests):
    cle = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    r = http.post(URL_TOKEN, headers={"Authorization": f"Basic {cle}",
                                      "Content-Type": "application/x-www-form-urlencoded"},
                  data={"grant_type": "client_credentials", "scope": PORTEE}, timeout=30)
    if getattr(r, "status_code", 200) in (400, 401):
        # La réponse d'eBay décrit l'erreur (jamais les clés) : on la montre pour savoir quoi corriger.
        raise RuntimeError(f"eBay a refusé les clés (HTTP {r.status_code} : {str(getattr(r, 'text', ''))[:200]}). "
                           "Vérifiez : clés de PRODUCTION (App ID contenant PRD), jeu de clés activé "
                           "(déclaration de suppression de compte faite), App ID dans EBAY_CLIENT_ID et "
                           "Cert ID dans EBAY_CLIENT_SECRET, sans espace ni retour à la ligne.")
    r.raise_for_status()
    return r.json()["access_token"]


def annonces(isbn, token, http=requests):
    r = http.get(URL_RECHERCHE, params={"q": isbn, "limit": 50, "filter": "buyingOptions:{FIXED_PRICE}"},
                 headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"}, timeout=30)
    r.raise_for_status()
    return r.json().get("itemSummaries", [])


def agreger(items, isbn13, jour):
    """Regroupe les annonces par état et renvoie une ligne par état (lots et devises étrangères écartés)."""
    par_etat = {}
    for it in items:
        etat = ETATS.get(str(it.get("conditionId", "")))
        prix = it.get("price") or {}
        if etat is None or prix.get("currency") != "EUR" or LOT.search(it.get("title", "")):
            continue
        try:
            valeur = float(prix["value"])
        except (KeyError, ValueError):
            continue
        if valeur > 0:
            par_etat.setdefault(etat, []).append(valeur)
    return [{"isbn13": isbn13, "date": jour.isoformat(), "etat": etat, "nb_annonces": len(v),
             "prix_min": f"{min(v):.2f}", "prix_median": f"{statistics.median(v):.2f}", "prix_max": f"{max(v):.2f}"}
            for etat, v in sorted(par_etat.items())]


def isbns_catalogue():
    import editions
    return sorted({r["isbn13"] for r in editions.load() if r.get("isbn13")})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limite", type=int, help="nombre maximal d'éditions interrogées")
    p.add_argument("--sortie", default=str(RACINE / "data" / "raw" / "occasion"))
    a = p.parse_args()
    cid, secret = (os.environ.get("EBAY_CLIENT_ID") or "").strip(), (os.environ.get("EBAY_CLIENT_SECRET") or "").strip()
    if not cid or not secret:
        sys.exit("Identifiants absents : définissez EBAY_CLIENT_ID et EBAY_CLIENT_SECRET.")
    jour = date.today()
    try:
        token = jeton(cid, secret)
    except RuntimeError as e:
        sys.exit(str(e))
    isbns = isbns_catalogue()[: a.limite]
    lignes = []
    for i, isbn in enumerate(isbns, 1):
        lignes += agreger(annonces(isbn, token), isbn, jour)
        time.sleep(PAUSE)
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    fichier = sortie / f"ebay-{jour.isoformat()}.csv"
    with open(fichier, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS)
        w.writeheader()
        w.writerows(lignes)
    print(f"{len(isbns)} éditions interrogées, {len(lignes)} lignes écrites dans {fichier}")


if __name__ == "__main__":
    main()
