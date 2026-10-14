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
from datetime import date, datetime
from pathlib import Path

import requests

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "pipeline"))

URL_TOKEN = "https://api.ebay.com/identity/v1/oauth2/token"
URL_RECHERCHE = "https://api.ebay.com/buy/browse/v1/item_summary/search"
PORTEE = "https://api.ebay.com/oauth/api_scope"
PAUSE = 0.5
# Fraîcheur : une annonce encore en ligne après longtemps n'a pas trouvé preneur, son prix est probablement trop haut.
# On n'en tient compte que si elle a été créée il y a moins de MAX_AGE_JOURS jours (90 : 30 jours laisseraient trop peu
# d'annonces sur des livres rares, qui restent en vente longtemps).
MAX_AGE_JOURS = 90
# Codes d'état d'eBay -> états du projet. Les codes absents (neuf, « d'occasion » sans précision) sont ignorés.
ETATS = {"2750": "tres_bon", "4000": "tres_bon", "5000": "bon", "6000": "convenable"}
LOT = re.compile(r"\b(lots?|collection|set|pack|x\s?\d+|\d+\s?x|\d+\s+livres|\d+\s+tomes)\b", re.I)
CHAMPS = ["isbn13", "date", "etat", "nb_annonces", "prix_min", "prix_median", "prix_max", "nb_toutes", "prix_median_toutes"]


MOTS_VIDES = {"les", "des", "dans", "avec", "pour", "livre", "dont", "vous", "etes", "heros", "poche", "folio", "junior", "gallimard", "jeunesse"}


def mots(texte):
    import unicodedata
    t = unicodedata.normalize("NFD", str(texte or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return {m for m in re.findall(r"[a-z0-9]+", t) if len(m) >= 3 and m not in MOTS_VIDES}


def concorde(titre_annonce, titre_attendu, seuil=0.6):
    """Vrai si l'annonce parle du bon livre : au moins `seuil` des mots du titre attendu figurent dans son titre."""
    attendus = mots(titre_attendu)
    if not attendus:
        return True                      # rien à comparer : on ne filtre pas
    return len(attendus & mots(titre_annonce)) / len(attendus) >= seuil


def age_jours(item, jour):
    """Âge de l'annonce en jours d'après `itemCreationDate`, ou None si la date est absente ou illisible."""
    brut = item.get("itemCreationDate")
    if not brut:
        return None
    try:
        return (jour - datetime.fromisoformat(str(brut).replace("Z", "+00:00")).date()).days
    except ValueError:
        return None


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


def agreger(items, isbn13, jour, titre=None):
    """Regroupe les annonces par état et renvoie une ligne par état (lots, devises étrangères et annonces d'un autre livre écartés)."""
    par_etat = {}
    for it in items:
        if titre and not concorde(it.get("title", ""), titre):
            continue
        age = age_jours(it, jour)
        ancienne = age is not None and age > MAX_AGE_JOURS     # invendue depuis longtemps : prix probablement trop haut
        etat = ETATS.get(str(it.get("conditionId", "")))
        prix = it.get("price") or {}
        if etat is None or prix.get("currency") != "EUR" or LOT.search(it.get("title", "")):
            continue
        try:
            valeur = float(prix["value"])
        except (KeyError, ValueError):
            continue
        if valeur > 0:
            par_etat.setdefault(etat, {"frais": [], "toutes": []})
            par_etat[etat]["toutes"].append(valeur)
            if not ancienne:
                par_etat[etat]["frais"].append(valeur)
    # La cote n'utilise que les annonces récentes. Les statistiques de toutes les annonces sont gardées à côté :
    # le modèle d'auto-apprentissage en tire de combien les annonces anciennes surestiment les prix.
    return [{"isbn13": isbn13, "date": jour.isoformat(), "etat": etat, "nb_annonces": len(v["frais"]),
             "prix_min": f"{min(v['frais']):.2f}", "prix_median": f"{statistics.median(v['frais']):.2f}", "prix_max": f"{max(v['frais']):.2f}",
             "nb_toutes": len(v["toutes"]), "prix_median_toutes": f"{statistics.median(v['toutes']):.2f}"}
            for etat, v in sorted(par_etat.items()) if v["frais"]]


def catalogue():
    """[(isbn13, titre, nb d'éditions du livre)] : le titre sert à vérifier la concordance et, pour un livre
    qui n'a qu'une édition, à chercher aussi par titre (un titre ne distingue pas les éditions entre elles)."""
    import collections
    import editions
    lignes = [r for r in editions.load() if r.get("isbn13")]
    nb = collections.Counter(r["livre"] for r in lignes)
    return sorted({(r["isbn13"], r["titre"], nb[r["livre"]]) for r in lignes})


def isbns_catalogue():
    return [c[0] for c in catalogue()]


def controler(a, token):
    """Contrôle sans enregistrement : ne montre que des comptages (jamais de titre ni de vendeur), pour juger
    la fiabilité du rattachement aux éditions. Le journal d'un dépôt public est public."""
    import collections
    cat = catalogue()[: a.controle]
    tot = collections.Counter()
    for isbn, titre, nb_ed in cat:
        items = annonces(isbn, token)
        c = collections.Counter(total=len(items))
        for it in items:
            conc = concorde(it.get("title", ""), titre)
            c["concordant" if conc else "autre_livre"] += 1
            if LOT.search(it.get("title", "")):
                c["lot"] += 1
            if str(it.get("conditionId", "")) not in ETATS:
                c["etat_inconnu"] += 1
            age = age_jours(it, date.today())
            c["age_inconnu" if age is None else ("age_30" if age <= 30 else ("age_90" if age <= MAX_AGE_JOURS else "age_plus"))] += 1
        retenues = sum(l["nb_annonces"] for l in agreger(items, isbn, date.today(), titre))
        par_titre = len(annonces(titre, token)) if nb_ed == 1 else None
        print(f"{isbn} | éditions du titre : {nb_ed} | annonces ISBN : {c['total']} (concordantes {c['concordant']}, "
              f"autre livre {c['autre_livre']}, lots {c['lot']}, état inconnu {c['etat_inconnu']}) | âge : ≤30 j {c['age_30']}, ≤{MAX_AGE_JOURS} j {c['age_90']}, plus ancien {c['age_plus']}, date absente {c['age_inconnu']} | retenues : {retenues}"
              + (f" | annonces par titre : {par_titre}" if par_titre is not None else ""))
        tot.update(c); tot["retenues"] += retenues; tot["isbn"] += 1; tot["isbn_sans_annonce"] += (c["total"] == 0)
        time.sleep(PAUSE)
    print(f"Âges : ≤30 jours {tot['age_30']}, ≤{MAX_AGE_JOURS} jours {tot['age_90']}, plus anciennes {tot['age_plus']} (écartées), date absente {tot['age_inconnu']}")
    print(f"Bilan : {tot['isbn']} éditions, {tot['total']} annonces, concordantes {tot['concordant']}, autre livre {tot['autre_livre']}, "
          f"lots {tot['lot']}, retenues {tot['retenues']}, éditions sans annonce {tot['isbn_sans_annonce']}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limite", type=int, help="nombre maximal d'éditions interrogées")
    p.add_argument("--controle", type=int, help="contrôle sans enregistrement sur N éditions (comptages seulement)")
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
    if a.controle:
        controler(a, token)
        return
    cat = catalogue()[: a.limite]
    isbns = [c[0] for c in cat]
    lignes = []
    for isbn, titre, nb_ed in cat:
        trouvees = agreger(annonces(isbn, token), isbn, jour, titre)
        time.sleep(PAUSE)
        if sum(l["nb_annonces"] for l in trouvees) < 3 and nb_ed == 1:
            # titre à édition unique : la recherche par titre est sans ambiguïté et ramène plus d'annonces
            trouvees = agreger(annonces(titre, token), isbn, jour, titre)
            time.sleep(PAUSE)
        lignes += trouvees
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
