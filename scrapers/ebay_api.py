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
# État non précisé (« d'occasion » sans détail, 3000, ou aucun état dans l'annonce) : on suppose le très bon état (règle du
# propriétaire, qui préfère tirer les prix vers le bas plutôt que de les gonfler).
# Les annonces « neuf » (1000, 1500…) et « pour pièces » (7000) restent écartées.
ETAT_SUPPOSE = "tres_bon"
CODES_NON_PRECISES = {"", "3000"}


def etat_de(item):
    """État du projet pour une annonce, ou None. Renvoie (état, supposé)."""
    code = str(item.get("conditionId") or "")
    if code in ETATS:
        return ETATS[code], False
    if code in CODES_NON_PRECISES:
        return ETAT_SUPPOSE, True
    return None, False
LOT = re.compile(r"\b(lots?|collection|set|pack|x\s?\d+|\d+\s?x|\d+\s+livres|\d+\s+tomes|au choix|a choisir|à choisir|votre choix|au choix parmi|plusieurs titres)\b", re.I)    # « au choix » : une annonce unique pour plusieurs livres, le prix ne dit rien d'un titre précis
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


class QuotaEbay(RuntimeError):
    """eBay répond 429 : la limite d'appels du jour est atteinte (environ 5 000 ; un relevé complet en fait environ 2 400)."""


def annonces(isbn, token, http=requests):
    """Annonces à prix fixe pour une requête (un ISBN, ou un titre suivi de l'ISBN)."""
    r = http.get(URL_RECHERCHE, params={"q": isbn, "limit": 50, "filter": "buyingOptions:{FIXED_PRICE}"},
                 headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"}, timeout=30)
    if getattr(r, "status_code", 200) == 429:
        raise QuotaEbay("Limite d'appels eBay atteinte pour aujourd'hui (erreur 429). Aucun enregistrement. "
                        "Ne lancez pas deux relevés complets le même jour ; réessayez demain.")
    r.raise_for_status()
    return r.json().get("itemSummaries", [])


def chercher(isbn, titre, token, http=requests, pause=0):
    """Annonces d'une édition : recherche par ISBN seul, comme un acheteur qui colle l'ISBN dans eBay (vérifié par le
    propriétaire sur « La Forêt du Dragon » : 3 annonces, les mêmes qu'avec le titre). Pas de recherche de repli par le
    titre : elle remplaçait ces 3 annonces (27 à 50 €) par 14 annonces à 6 € d'autres objets au titre voisin."""
    items = annonces(isbn, token, http)
    if pause:
        time.sleep(pause)
    return items


# Requêtes complémentaires (essai du 20 octobre 2026 sur 60 éditions) : l'ISBN seul ne trouve que 10 éditions à 3 annonces ; avec le titre
# et l'auteur, le titre et « livre dont vous êtes le héros », le titre et la série, 35. Les annonces trouvées SEULEMENT par le titre
# sont soumises à une concordance stricte (tous les mots du titre) et, comme toutes les autres, retirées si elles sont ambiguës entre
# plusieurs éditions d'un même livre (ecarter_ambigues).
def requetes_complementaires(ed):
    ed = ed or {}
    serie = (ed.get("serie") or "").strip()
    num = (ed.get("numero") or "").strip().lstrip("0")
    livre = ed.get("livre") or ed.get("titre") or ""
    auteur = (ed.get("auteurs") or "").split(";")[0].strip()
    isbn = (ed.get("isbn13") or "").strip()
    q = [" ".join(x for x in (livre, auteur) if x), f"{livre} livre dont vous êtes le héros", f"{livre} livre dont vous êtes le héro", f"{livre} ldvelh", " ".join(x for x in (livre, serie, num) if x)]
    if isbn:
        q.append(f"{livre} {isbn}")
    vues, sortie = set(), []
    for t in q:
        if t.strip() and len(mots(livre)) >= 2 and t not in vues:
            vues.add(t); sortie.append(t)
    return sortie


def chercher_elargi(isbn, titre, token, ed=None, http=requests, pause=0):
    """Annonces d'une édition : recherche par ISBN, puis par le titre (voir requetes_complementaires). Les annonces apportées
    seulement par le titre sont marquées « _titre_seul » : agreger leur applique une concordance stricte."""
    items = list(chercher(isbn, titre, token, http, pause))
    vus = {it.get("itemId") for it in items}
    for q in requetes_complementaires(ed):
        try:
            extra = annonces(q, token, http)
        except requests.RequestException:
            continue
        if pause:
            time.sleep(pause)
        for it in extra:
            if it.get("itemId") not in vus:
                vus.add(it.get("itemId"))
                items.append({**it, "_titre_seul": True})
    return items


ANNEE = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")


def annee_compatible(titre_annonce, annees):
    """Faux si le titre de l'annonce donne une année de parution qui n'est celle d'aucune année connue de l'édition
    (même titre, autre édition). Sans année dans le titre, ou sans année connue, on ne tranche pas."""
    vues = set(ANNEE.findall(str(titre_annonce or "")))
    return not vues or not annees or bool(vues & set(annees))


def ecarter_ambigues(par_isbn, livres):
    """par_isbn : {isbn: [annonces]} ; livres : {isbn: livre}. Une annonce ne doit être attribuée qu'à une édition :
    - trouvée par l'ISBN sous une seule édition d'un livre : elle lui est attribuée (son vendeur a cité cet ISBN), et ses copies
      trouvées par le titre sous les autres éditions du même livre sont retirées ;
    - trouvée par l'ISBN sous plusieurs éditions du livre (le vendeur cite plusieurs ISBN) : retirée de toutes ;
    - trouvée seulement par le titre (« _titre_seul ») : gardée seulement si une seule édition du livre la voit."""
    par_ann = {}
    for isbn, items in par_isbn.items():
        for it in items:
            if it.get("itemId"):
                e = par_ann.setdefault((livres.get(isbn), it["itemId"]), {"isbn": set(), "titre": set()})
                e["titre" if it.get("_titre_seul") else "isbn"].add(isbn)

    def garder(isbn, it):
        e = par_ann.get((livres.get(isbn), it.get("itemId")))
        if e is None:
            return True
        if len(e["isbn"]) >= 2:
            return False
        if len(e["isbn"]) == 1:
            return isbn in e["isbn"]
        return len(e["titre"]) < 2
    return {isbn: [it for it in items if garder(isbn, it)] for isbn, items in par_isbn.items()}


def _norm(texte):
    import unicodedata
    t = unicodedata.normalize("NFD", str(texte or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip()


GENERIQUES = ("ldvelh", "dont vous etes le heros", "dont vous etes", "livre jeu", "livres jeux", "gamebook")


def parle_de_la_collection(titre_annonce, ed):
    """Vrai si le titre d'une annonce trouvée par le seul titre montre qu'il s'agit d'un livre-jeu : mention générique (LDVELH,
    « dont vous êtes le héros »), nom de la série ou nom de l'auteur. Sans cela, un titre de deux mots comme « La Tour de Cristal »
    ramène des cartes Pokémon, des DVD et des bijoux, qui concordent « à 100 % » avec le titre. Sans fiche, on ne tranche pas."""
    if not ed:
        return True
    t = " " + _norm(titre_annonce) + " "
    if any(f" {g} " in t for g in GENERIQUES):
        return True
    serie = _norm(ed.get("serie"))
    if len(serie) >= 4 and f" {serie} " in t:
        return True
    for auteur in str(ed.get("auteurs") or "").split(";"):
        for nom in _norm(auteur).split(" "):                       # « Joe Dever » comme « Dever, Joe »
            if len(nom) >= 4 and f" {nom} " in t:
                return True
    return False


def titre_ambigu(titre, ed):
    """Vrai quand le titre du livre n'est que le nom (ou une partie du nom) de sa série : « Les Terres de Légende » dans la série
    « Les Terres de Légende ». Une annonce qui porte ce titre peut concerner n'importe quel tome de la série."""
    t, serie = _norm(titre), _norm((ed or {}).get("serie"))
    return len(t) >= 4 and f" {t} " in f" {serie} "


def frais_port(item):
    """Frais de port annoncés (en euros), le moins cher des modes de livraison proposés ; None si l'annonce n'en indique pas."""
    couts = []
    for option in item.get("shippingOptions") or []:
        cout = (option.get("shippingCost") or {})
        if cout.get("currency", "EUR") == "EUR" and cout.get("value") not in (None, ""):
            try:
                couts.append(float(cout["value"]))
            except ValueError:
                continue
    return min(couts) if couts else None


def retenues(items, jour, titre=None, annees=None, ed=None):
    """Annonces que le relevé garde pour une édition : [(annonce, état, prix, ancienne)]. « ancienne » : plus de MAX_AGE_JOURS jours
    (gardée pour les statistiques, pas pour la cote). Lots, devises étrangères, autres livres et autres années sont écartés."""
    sortie = []
    for it in items:
        if titre and not concorde(it.get("title", ""), titre, 1.0 if it.get("_titre_seul") else 0.6):
            continue
        if it.get("_titre_seul") and not parle_de_la_collection(it.get("title", ""), ed):
            continue
        if it.get("_titre_seul") and titre_ambigu(titre, ed):
            continue                       # titre = nom de la série : l'annonce peut parler de n'importe quel tome ; seul l'ISBN tranche
        if not annee_compatible(it.get("title", ""), annees):
            continue
        age = age_jours(it, jour)
        ancienne = age is not None and age > MAX_AGE_JOURS     # invendue depuis longtemps : prix probablement trop haut
        etat, _suppose = etat_de(it)
        prix = it.get("price") or {}
        if etat is None or prix.get("currency") != "EUR" or LOT.search(it.get("title", "")):
            continue
        try:
            valeur = float(prix["value"])
        except (KeyError, ValueError):
            continue
        if valeur > 0:
            # Prix total pour l'acheteur : le prix de l'annonce plus les frais de port (0 si l'annonce ne les indique pas)
            sortie.append((it, etat, valeur + (frais_port(it) or 0.0), ancienne))
    return sortie


FACTEUR_ABERRANT_ANNONCE = 3.0       # au-delà de 3 × la médiane (ou en dessous du tiers) : très probablement un autre objet, ou un prix absurde


def ecarter_aberrantes(liste):
    """liste : sortie de `retenues`. Pour un état qui compte au moins 3 annonces récentes, retire celles dont le prix est à plus de
    3 × la médiane ou à moins du tiers : ce sont presque toujours d'autres objets (carte, DVD…) ou des prix de collectionneur absurdes.
    Les annonces anciennes ne servent pas à la cote : elles sont rangées avec leur état mais jugées sur les récentes."""
    par = {}
    for x in liste:
        if not x[3]:
            par.setdefault(x[1], []).append(x[2])
    bornes = {}
    for etat, prix in par.items():
        if len(prix) >= 3:
            m = statistics.median(prix)
            bornes[etat] = (m / FACTEUR_ABERRANT_ANNONCE, m * FACTEUR_ABERRANT_ANNONCE)
    return [x for x in liste if x[1] not in bornes or bornes[x[1]][0] <= x[2] <= bornes[x[1]][1]]


def agreger(items, isbn13, jour, titre=None, annees=None, ed=None):
    """Regroupe les annonces par état et renvoie une ligne par état (lots, devises étrangères et annonces d'un autre livre écartés)."""
    par_etat = {}
    for _it, etat, valeur, ancienne in ecarter_aberrantes(retenues(items, jour, titre, annees, ed)):
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


CHAMPS_ANNONCES = ["isbn13", "etat", "prix", "titre", "lien", "age_jours", "trouvee_par", "etat_suppose", "port"]    # « prix » = prix total avec les frais de port ; « port » vide si l'annonce n'en indique pas


def lignes_annonces(items, isbn13, jour, titre=None, annees=None, ed=None):
    """Les annonces récentes retenues pour la cote, une ligne chacune : le propriétaire peut ainsi ouvrir chaque annonce et vérifier
    que c'est bien le bon livre (page « Vérifier les prix »)."""
    sortie = []
    for it, etat, valeur, ancienne in ecarter_aberrantes(retenues(items, jour, titre, annees, ed)):
        if ancienne:
            continue
        age = age_jours(it, jour)
        sortie.append({"isbn13": isbn13, "etat": etat, "prix": f"{valeur:.2f}", "titre": str(it.get("title", ""))[:120],
                       "lien": str(it.get("itemWebUrl", "")).split("?")[0], "age_jours": "" if age is None else age,
                       "trouvee_par": "titre" if it.get("_titre_seul") else "isbn",
                       "etat_suppose": 1 if etat_de(it)[1] else 0,          # 1 : l'annonce ne précise pas l'état, on suppose le très bon état
                       "port": "" if frais_port(it) is None else f"{frais_port(it):.2f}"})
    return sortie


CIBLES_ESSAIS = Path(__file__).resolve().parent.parent / "data" / "manual" / "essais_archives.txt"   # ISBN des éditions « archive seule » (mode --essais)


def catalogue():
    """[(isbn13, titre, nb d'éditions du livre, livre, années de parution)] : le titre sert à vérifier la concordance ;
    le nombre d'éditions, le livre et l'année servent à ne pas confondre les éditions d'un même titre."""
    import collections
    import editions
    lignes = [r for r in editions.load() if r.get("isbn13")]
    nb = collections.Counter(r["livre"] for r in lignes)
    return sorted({(r["isbn13"], r["titre"], nb[r["livre"]], r["livre"],
                    tuple(sorted({str(a) for a in (r.get("annee"), r.get("annee_bnf")) if a}))) for r in lignes})


def isbns_catalogue():
    return [c[0] for c in catalogue()]


def controler(a, token):
    """Contrôle sans enregistrement : ne montre que des comptages (jamais de titre ni de vendeur), pour juger
    la fiabilité du rattachement aux éditions. Le journal d'un dépôt public est public."""
    import collections
    cat = catalogue()[: a.controle]
    tot = collections.Counter()
    for isbn, titre, nb_ed, livre, annees in cat:
        items = chercher(isbn, titre, token, pause=PAUSE)
        c = collections.Counter(total=len(items))
        for it in items:
            conc = concorde(it.get("title", ""), titre)
            c["concordant" if conc else "autre_livre"] += 1
            if not annee_compatible(it.get("title", ""), annees):
                c["autre_annee"] += 1
            if LOT.search(it.get("title", "")):
                c["lot"] += 1
            etat_it, suppose = etat_de(it)
            if suppose:
                c["etat_suppose"] += 1
            elif etat_it is None:
                c["etat_inconnu"] += 1
            age = age_jours(it, date.today())
            c["age_inconnu" if age is None else ("age_30" if age <= 30 else ("age_90" if age <= MAX_AGE_JOURS else "age_plus"))] += 1
        retenues = sum(l["nb_annonces"] for l in agreger(items, isbn, date.today(), titre, annees))
        par_titre = None
        print(f"{isbn} | éditions du titre : {nb_ed} | annonces ISBN : {c['total']} (concordantes {c['concordant']}, "
              f"autre livre {c['autre_livre']}, autre année {c['autre_annee']}, lots {c['lot']}, état supposé TBE {c['etat_suppose']}, autre état écarté {c['etat_inconnu']}) | âge : ≤30 j {c['age_30']}, ≤{MAX_AGE_JOURS} j {c['age_90']}, plus ancien {c['age_plus']}, date absente {c['age_inconnu']} | retenues : {retenues}"
              + (f" | annonces par titre : {par_titre}" if par_titre is not None else ""))
        tot.update(c); tot["retenues"] += retenues; tot["isbn"] += 1; tot["isbn_sans_annonce"] += (c["total"] == 0)
        time.sleep(PAUSE)
    print(f"Âges : ≤30 jours {tot['age_30']}, ≤{MAX_AGE_JOURS} jours {tot['age_90']}, plus anciennes {tot['age_plus']} (écartées), date absente {tot['age_inconnu']}")
    print(f"Bilan : {tot['isbn']} éditions, {tot['total']} annonces, concordantes {tot['concordant']}, autre livre {tot['autre_livre']}, "
          f"lots {tot['lot']}, retenues {tot['retenues']}, éditions sans annonce {tot['isbn_sans_annonce']}")


def diagnostiquer(isbn, token):
    """Montre, pour un ISBN, les annonces que le relevé voit (recherche par ISBN, puis par le titre) et ce qu'il en fait : retenue
    ou écartée avec le motif, et la cote qui en résulte. Chaque annonce a son lien, pour que le propriétaire l'ouvre et vérifie.
    Rien n'est enregistré dans les données du site."""
    import editions
    ed = next((r for r in editions.load() if r.get("isbn13") == isbn), None)
    titre = ed["titre"] if ed else ""
    annees = tuple(sorted({str(a) for a in ((ed or {}).get("annee"), (ed or {}).get("annee_bnf")) if a}))
    print(f"Édition {isbn} : « {titre} », parution {', '.join(annees) or 'inconnue'}")
    items = chercher_elargi(isbn, titre, token, ed)
    gardees = []
    print(f"\n### {len(items)} annonces trouvées (par l'ISBN, puis par le titre)")
    for it in items:
        etat, _suppose = etat_de(it)
        titre_seul = bool(it.get("_titre_seul"))
        age = age_jours(it, date.today())
        motif = ("autre livre" if not concorde(it.get("title", ""), titre, 1.0 if titre_seul else 0.6) else
                 "pas un livre-jeu (ni série, ni auteur, ni LDVELH)" if titre_seul and not parle_de_la_collection(it.get("title", ""), ed) else
                 "autre année" if not annee_compatible(it.get("title", ""), annees) else
                 "lot" if LOT.search(it.get("title", "")) else
                 "état écarté (neuf, pièces…)" if etat is None else
                 "plus de 90 jours" if age is not None and age > MAX_AGE_JOURS else "RETENUE")
        if motif == "RETENUE":
            gardees.append(it)
        p = it.get("price") or {}
        print(f"- {p.get('value')} {p.get('currency')} | {it.get('title', '')} | état {it.get('condition', '?')} | "
              f"âge {age if age is not None else '?'} j | {'titre' if titre_seul else 'ISBN'} | {motif} | {it.get('itemWebUrl', '').split('?')[0]}")
    print("\n### Ce que le relevé en tire")
    for l in agreger(items, isbn, date.today(), titre, annees, ed):
        print(f"- {l['etat']} : {l['nb_annonces']} annonce(s), de {l['prix_min']} à {l['prix_max']} €, médiane {l['prix_median']} €")
    if not gardees:
        print("- aucune annonce retenue")


def requetes_candidates(isbn13, ed):
    """Requêtes testées par --essais pour une édition : {nom: texte}. L'ISBN seul est la méthode actuelle."""
    import editions
    try:
        _, isbn10 = editions.normalize_isbn(isbn13)
    except ValueError:
        isbn10 = ""
    h = isbn13
    trait = f"{h[:3]}-{h[3]}-{h[4:6]}-{h[6:12]}-{h[12]}" if len(h) == 13 else h
    serie = (ed.get("serie") or "").strip()
    num = (ed.get("numero") or "").strip().lstrip("0")
    livre = ed.get("livre") or ed.get("titre") or ""
    auteur = (ed.get("auteurs") or "").split(";")[0].strip()
    q = {"isbn13": isbn13}
    if isbn10:
        q["isbn10"] = isbn10
    q["isbn13_tirets"] = trait
    q["titre_serie"] = " ".join(x for x in (livre, serie, num) if x)
    q["titre_auteur"] = " ".join(x for x in (livre, auteur) if x)
    q["titre_livre_heros"] = f"{livre} livre dont vous êtes le héros"
    q["titre_ldvelh"] = f"{livre} ldvelh"
    q["ldvelh"] = "ldvelh"
    return q


def essayer(a, token):
    """Compare, sur N éditions, plusieurs façons de chercher sur eBay. Rien n'est enregistré, et le journal (public) ne montre
    que des comptages. Une annonce est « valable » si elle concorde avec le titre et l'année de l'édition, n'est pas un lot,
    est en euros, a un état connu et a moins de 90 jours : c'est exactement ce que le relevé retient."""
    import collections
    import editions
    jour = date.today()
    rows = {r["isbn13"]: r for r in editions.load() if r.get("isbn13")}
    cat = catalogue()
    if CIBLES_ESSAIS.exists():                                             # essais ciblés : seulement les éditions de la liste (archive seule)
        voulus = set(CIBLES_ESSAIS.read_text(encoding="utf-8").split())
        cat = [c for c in cat if c[0] in voulus]
    pas = max(1, len(cat) // a.essais)
    echantillon = cat[::pas][: a.essais]                                  # réparti sur tout le catalogue
    valables = collections.defaultdict(dict)                              # nom de requête -> {isbn: {itemId}}
    valables_stricts = collections.defaultdict(dict)                      # idem, concordance stricte pour les requêtes par titre
    renvoyees = collections.Counter(); concordantes = collections.Counter()
    for isbn, titre, nb_ed, livre, annees in echantillon:
        for nom, texte in requetes_candidates(isbn, rows.get(isbn, {})).items():
            if not texte.strip():
                continue
            try:
                items = annonces(texte, token)
            except requests.RequestException:
                continue
            time.sleep(PAUSE)
            ids, ids_stricts = set(), set()
            for it in items:
                renvoyees[nom] += 1
                if not concorde(it.get("title", ""), titre):
                    continue
                concordantes[nom] += 1
                if not annee_compatible(it.get("title", ""), annees):
                    continue
                strict = concorde(it.get("title", ""), titre, 1.0)
                etat, _ = etat_de(it)
                prix = it.get("price") or {}
                age = age_jours(it, jour)
                if etat is None or prix.get("currency") != "EUR" or LOT.search(it.get("title", "")):
                    continue
                if age is not None and age > MAX_AGE_JOURS:
                    continue
                ids.add(it.get("itemId"))
                if strict or nom.startswith("isbn"):
                    ids_stricts.add(it.get("itemId"))
            valables[nom][isbn] = ids
            valables_stricts[nom][isbn] = ids_stricts
    base = valables["isbn13"]
    noms = list(valables)
    print(f"Essai sur {len(echantillon)} éditions réparties sur le catalogue (comptages seulement)\n")
    print("| Requête | annonces renvoyées | concordantes avec le titre | annonces valables | éditions avec ≥ 1 | éditions avec ≥ 3 |")
    print("|---|---|---|---|---|---|")
    for nom in noms:
        v = valables[nom]
        print(f"| {nom} | {renvoyees[nom]} | {concordantes[nom]} ({100 * concordantes[nom] // max(renvoyees[nom], 1)} %) | {sum(len(x) for x in v.values())} | "
              f"{sum(1 for x in v.values() if x)} | {sum(1 for x in v.values() if len(x) >= 3)} |")
    print("\n**Gain par rapport à l'ISBN seul** (annonces valables nouvelles ; éditions qui atteignent 3 annonces)\n")
    print("| Ajout à l'ISBN | annonces en plus | éditions avec ≥ 3 (avant → après) |")
    print("|---|---|---|")
    avant3 = sum(1 for x in base.values() if len(x) >= 3)
    for nom in noms:
        if nom == "isbn13":
            continue
        plus = 0; apres3 = 0
        for isbn in base:
            u = base[isbn] | valables[nom].get(isbn, set())
            plus += len(u - base[isbn]); apres3 += len(u) >= 3
        print(f"| + {nom} | {plus} | {avant3} → {apres3} |")
    tout = {isbn: set().union(*(valables[n].get(isbn, set()) for n in noms)) for isbn in base}
    print(f"| + toutes les requêtes | {sum(len(tout[i] - base[i]) for i in base)} | {avant3} → {sum(1 for x in tout.values() if len(x) >= 3)} |")
    strict = {isbn: set().union(*(valables_stricts[n].get(isbn, set()) for n in noms)) for isbn in base}
    print(f"| + toutes, concordance stricte sur le titre (méthode retenue) | {sum(len(strict[i] - base[i]) for i in base)} | {avant3} → {sum(1 for x in strict.values() if len(x) >= 3)} |")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limite", type=int, help="nombre maximal d'éditions interrogées")
    p.add_argument("--controle", type=int, help="contrôle sans enregistrement sur N éditions (comptages seulement)")
    p.add_argument("--diagnostic", help="ISBN (un ou plusieurs, séparés par des espaces) : liste les annonces trouvées, avec leur lien (aucun enregistrement)")
    p.add_argument("--essais", type=int, help="compare plusieurs requêtes (ISBN-13, ISBN-10, titre…) sur N éditions, sans enregistrement")
    p.add_argument("--essai-version", dest="essai_version", type=int, help="essai en deux étapes (titre, description, image) sur N éditions « archive seule » (aucun enregistrement)")
    p.add_argument("--essai-photos", dest="essai_photos", type=int, help="essai de la comparaison de photos sur de vraies annonces, N éditions tirées au hasard (aucun enregistrement)")
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
    if a.diagnostic:
        for isbn in a.diagnostic.replace(",", " ").split():          # plusieurs ISBN possibles, séparés par des espaces
            diagnostiquer(isbn.strip(), token)
            print("\n" + "=" * 70 + "\n")
        return
    if a.controle:
        controler(a, token)
        return
    if a.essais:
        essayer(a, token)
        return
    if a.essai_version:
        import essai_version
        import editions
        essai_version.essayer(a, token, catalogue, chercher_elargi, concorde, RACINE / "web" / "covers", lambda: editions.load())
        return
    if a.essai_photos:
        import essai_photos
        essai_photos.essayer(a, token, catalogue, chercher, concorde, RACINE / "web" / "covers")
        return
    cat = catalogue()[: a.limite]
    isbns = [c[0] for c in cat]
    lignes, par_isbn = [], {}
    import editions
    fiches = {r["isbn13"]: r for r in editions.load() if r.get("isbn13")}
    for isbn, titre, nb_ed, livre, annees in cat:
        par_isbn[isbn] = chercher_elargi(isbn, titre, token, fiches.get(isbn), pause=PAUSE)
    import reconciliation_image                                  # réconciliation par image : une annonce vue sous plusieurs éditions va à celle dont la jaquette lui ressemble
    par_isbn = reconciliation_image.reconcilier(par_isbn, {c[0]: c[3] for c in cat}, RACINE / "web" / "covers")
    par_isbn = reconciliation_image.verifier_photos(par_isbn, RACINE / "web" / "covers")      # toute annonce retenue : la photo doit montrer l'édition à laquelle elle est rattachée
    par_isbn = ecarter_ambigues(par_isbn, {c[0]: c[3] for c in cat})
    annonces_gardees = []
    for isbn, titre, nb_ed, livre, annees in cat:
        lignes += agreger(par_isbn[isbn], isbn, jour, titre, annees, fiches.get(isbn))
        annonces_gardees += lignes_annonces(par_isbn[isbn], isbn, jour, titre, annees, fiches.get(isbn))
    sortie = Path(a.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    fichier = sortie / f"ebay-{jour.isoformat()}.csv"
    with open(fichier, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CHAMPS)
        w.writeheader()
        w.writerows(lignes)
    with open(sortie / f"annonces-{jour.isoformat()}.csv", "w", newline="", encoding="utf-8") as f:       # non lu par build_db : sert à vérifier
        w = csv.DictWriter(f, fieldnames=CHAMPS_ANNONCES)
        w.writeheader()
        w.writerows(annonces_gardees)
    print(f"{len(isbns)} éditions interrogées, {len(lignes)} lignes écrites dans {fichier}")


if __name__ == "__main__":
    try:
        main()
    except QuotaEbay as e:
        sys.exit(str(e))
