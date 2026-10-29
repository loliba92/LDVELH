"""Exporte la base en étoile vers les fichiers lus par le site (web/data/).

Pour chaque version et chaque état, le prix est estimé par pipeline/estimation.py (médiane pondérée des
observations hors lots : natures, fraîcheur, nombre d'annonces). Sans relevé actuel, c'est le prix d'archive.

    python pipeline/build_db.py && python pipeline/export_site.py
"""
import argparse
import csv
import hashlib
import json
import sqlite3
import statistics
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
from estimation import Obs, estimer
from prix_neuf import FRAIS_LIBRAIRIE, prix_livre_vinted
import calibration
import cote_v2
import importer_leboncoin
import mouvements
import rarete
import veille_parutions
import tendances
import etats
import validations

DB = editions.ROOT / "data" / "warehouse" / "ldvelh.sqlite"
SORTIE = editions.ROOT / "web" / "data"
COVERS = editions.ROOT / "web" / "covers"

REQUETE = """
SELECT v.version_key, v.id, v.isbn13, v.titre_version, l.livre_id, l.titre AS livre, sr.nom AS serie,
       v.numero_serie, v.libelle_version, v.numero_version, v.est_derniere_version, v.en_vente,
       v.annee, v.annee_bnf, v.editeur, v.collection_editeur, v.pages, l.auteurs, v.traducteur,
       v.illustrateur, v.notice_bnf, v.couverture, v.statut
FROM DimVersion v
JOIN DimLivre l ON l.livre_key = v.livre_key
JOIN DimSerie sr ON sr.serie_key = v.serie_key
ORDER BY sr.nom, v.numero_serie, v.numero_version
"""
PRIX = """
SELECT f.version_key, e.code, t.code, d.date, f.prix, f.nb_annonces, s.code
FROM FaitPrix f
JOIN DimEtat e ON e.etat_key = f.etat_key
JOIN DimTypePrix t ON t.type_key = f.type_key
JOIN DimDate d ON d.date_key = f.date_key
JOIN DimSource s ON s.source_key = f.source_key
WHERE f.est_lot = 0
"""
ETATS = ("convenable", "bon", "tres_bon")
LISSAGE_DEPUIS = "2026-10-22"


def aligner(par_etat, ecart=etats.ECART_DEFAUT):
    """Cohérence : un état supérieur vaut toujours plus qu'un état inférieur (convenable < bon < très bon).
    Règle générale : si l'état supérieur est en dessous de l'état inférieur, il est relevé à `ecart` fois l'état inférieur
    (+20 % par défaut, réglable dans data/manual/ratios_etats.json), et marqué « ajusté ». Deux états égaux ne sont pas touchés.
    Exception : si l'état inférieur n'est qu'une archive alors que l'état supérieur vient d'un relevé actuel, c'est
    l'archive qu'on ramène (état supérieur ÷ `ecart`) à la donnée actuelle, sinon une archive gonflée tirerait vers le haut
    un prix actuel. Renvoie le nombre de prix modifiés."""
    ordre = [e for e in ETATS if par_etat.get(e)]
    fiables = {e for e in ordre if par_etat[e]["source"] != "archives"}      # valeur issue d'un relevé actuel
    for _ in range(3):
        change = False
        for bas, haut in zip(ordre, ordre[1:]):
            b, h = par_etat[bas], par_etat[haut]
            if h["prix"] < b["prix"] - 1e-9:
                if haut in fiables and bas not in fiables:
                    par_etat[bas] = {**b, "prix": round(h["prix"] / ecart, 2), "ajuste": True}
                    fiables.add(bas)
                else:
                    par_etat[haut] = {**h, "prix": round(b["prix"] * ecart, 2), "ajuste": True}
                    if bas in fiables:
                        fiables.add(haut)
                change = True
        if not change:
            break
    return sum(1 for e in ordre if par_etat[e].get("ajuste"))


JOURS_VINTED = 14          # même règle que Leboncoin : en ligne tant que le bot ne la signale pas vendue
JOURS_LEBONCOIN = 14       # une annonce Leboncoin reste en ligne tant qu'elle n'est pas signalée vendue : le bot ne revoit que les 50 plus récentes, une annonce plus ancienne n'y reparaît pas. Écartée après 14 jours sans être revue
JOURS_ANNONCES = 120      # une annonce qui n'est plus en ligne reste consultable ce nombre de jours après sa dernière observation


def extraire_butin(annonces, revue, seuil=0.5, economie_mini=3):
    """Le Butin seul : les annonces à 50 % du prix du site ou moins (3 € d'économie au moins), même édition, même état.
    Les sorciers ne reçoivent que ce sous-ensemble ; la liste complète des annonces est réservée au Zagor."""
    publie = {(r["isbn"], r["etat"]): r["publie"] for r in revue if r.get("publie")}
    butin = {}
    for isbn, par_etat in annonces.items():
        for etat, liste in par_etat.items():
            prix_site = publie.get((isbn, etat))
            if not prix_site:
                continue
            gardees = [a for a in liste if a[0] <= seuil * prix_site and prix_site - a[0] >= economie_mini and not str(a[1]).startswith("Lot de ")]
            if gardees:
                butin.setdefault(isbn, {})[etat] = gardees
    return butin


def premieres_vues(annonces, anciennes, maintenant, historiques=None):
    """Première apparition de chaque annonce (reconnue à son lien) : {lien: date ou date-heure UTC}.
    Une annonce déjà connue avec son heure la garde. Une annonce connue seulement par sa date prend l'heure retrouvée dans l'historique des relevés
    (`historiques`, voir pipeline/premieres_historiques.py) si elle est du même jour ou plus ancienne. Une annonce nouvelle reçoit l'heure du relevé.
    Au tout premier passage (`anciennes` est None : le fichier n'enregistrait pas encore cette information), les annonces sans heure retrouvée
    prennent leur date de dernière observation, sans heure. Seules les annonces actuelles sont gardées (une annonce disparue puis revenue repart de zéro)."""
    historiques = historiques or {}
    premieres = {}
    for par_etat in annonces.values():
        for liste in par_etat.values():
            for ligne in liste:
                lien, vue = ligne[2], ligne[4]
                if lien in premieres:
                    continue
                connue = anciennes.get(lien) if anciennes is not None else None
                h = historiques.get(lien)
                if connue and len(connue) > 10:
                    premieres[lien] = connue                                                       # heure déjà connue
                elif h and ligne[3] != "librairie" and (not connue or h[:10] <= connue[:10]):
                    premieres[lien] = h                                                            # heure retrouvée dans l'historique
                elif connue:
                    premieres[lien] = connue
                elif anciennes is None:
                    premieres[lien] = vue or maintenant[:10]
                elif ligne[3] == "librairie":
                    premieres[lien] = maintenant[:10]                 # une page de librairie n'est pas une annonce qui apparaît : pas d'heure
                else:
                    premieres[lien] = maintenant
    return premieres


def source_de_ligne(origine):
    """Source d'une annonce du relevé : Leboncoin, Vinted, librairie, sinon eBay (trouvée par l'ISBN ou par le titre)."""
    return origine if origine in ("leboncoin", "vinted", "librairie") else "ebay"


def mettre_a_jour_captures(captures, annonces, premieres, aujourdhui, jours_gardes=90, oubli_jours=14):
    """Nombre d'annonces captées chaque jour, par source (eBay, Leboncoin, Vinted, librairie) : {"jours": {date: {source: n}}, "vus": {empreinte du lien: dernier jour vu}}.
    Une annonce est comptée une seule fois, le jour où elle apparaît pour la première fois (jour de `premieres`). Les annonces déjà en ligne au premier passage sont
    rangées à leur date connue (au mieux : pour celles-ci, la date est celle de la dernière observation). `vus` oublie les liens absents depuis `oubli_jours` jours."""
    captures = captures or {"jours": {}, "vus": {}}
    jours, vus = captures.setdefault("jours", {}), captures.setdefault("vus", {})
    vues_ce_passage = set()
    for par_etat in annonces.values():
        for liste in par_etat.values():
            for ligne in liste:
                lien = ligne[2]
                h = hashlib.sha1(lien.encode("utf-8")).hexdigest()[:10]
                if h in vues_ce_passage:
                    continue
                vues_ce_passage.add(h)
                if h not in vus:
                    jour = (premieres.get(lien) or aujourdhui)[:10]
                    compte = jours.setdefault(jour, {})
                    source = source_de_ligne(ligne[3])
                    compte[source] = compte.get(source, 0) + 1
                vus[h] = aujourdhui
    limite_vus = (date.fromisoformat(aujourdhui) - timedelta(days=oubli_jours)).isoformat()
    captures["vus"] = {h: d for h, d in vus.items() if d >= limite_vus}
    limite_jours = (date.fromisoformat(aujourdhui) - timedelta(days=jours_gardes)).isoformat()
    captures["jours"] = {d: c for d, c in sorted(jours.items()) if d >= limite_jours}
    captures.setdefault("depuis", aujourdhui)          # début du comptage : les jours d'avant sont reconstitués au mieux
    return captures


def calculer_offre(annonces, ages_ebay, date_ebay, date_lbc):
    """Offre d'occasion par édition : nombre d'annonces en ligne au dernier relevé de chaque source (eBay, Leboncoin, exemplaires d'occasion en librairie)
    et âge médian des annonces eBay, en jours. Une annonce de lot n'est pas l'offre d'un livre seul : elle n'est pas comptée.
    Servi avec le Butin (niveaux 2 et 3) : seulement des décomptes, jamais de lien ni de titre."""
    offre = {}
    for isbn, par_etat in annonces.items():
        ebay = lbc = vin = lib = 0
        for liste in par_etat.values():
            for prix, titre, lien, origine, vue, suppose in liste:
                if str(titre).startswith("Lot de "):
                    continue
                if origine == "librairie":
                    lib += 1
                elif origine == "vinted":
                    vin += 1                         # même règle que Leboncoin : en ligne jusqu'à preuve du contraire
                elif origine == "leboncoin":
                    lbc += 1                         # en ligne jusqu'à preuve du contraire (voir JOURS_LEBONCOIN) : la liste a déjà retiré les vendues
                elif not (date_ebay and vue and vue < date_ebay):
                    ebay += 1
        if ebay or lbc or vin or lib:
            ages = [a for a in ages_ebay.get(isbn, []) if a is not None]
            offre[isbn] = {"ebay": ebay, "lbc": lbc, "vin": vin, "lib": lib, "age": int(statistics.median(ages)) if ages else None}
    return offre


def annonces_cumulees(fichiers, jours=JOURS_ANNONCES):
    """Annonces de tous les relevés quotidiens (annonces-AAAA-MM-JJ.csv), sans doublon.
    Une annonce est reconnue à son lien ; c'est sa version la plus récente qui compte (prix, état, titre).
    Chaque ligne : [prix, titre, lien, trouvée par, date de dernière observation, état supposé]. Depuis le relevé à colonne « port »,
    le prix eBay est le prix livré (frais de port compris). « état supposé » : 1 si l'annonce ne précise
    pas son état (on suppose le très bon état), 0 s'il est indiqué, None pour les relevés d'avant l'enregistrement de cette information.
    Une annonce non revue depuis plus de `jours` jours
    avant le dernier relevé est écartée. Renvoie {isbn13: {état: [lignes]}}."""
    fichiers = sorted(fichiers)
    if not fichiers:
        return {}
    vues = {}
    for f in fichiers:
        jour = f.stem[-10:]
        with open(f, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                supp = (r.get("etat_suppose") or "").strip()
                prix = float(r["prix"])
                brut_fdp = (r.get("fdp") or "").strip()
                if brut_fdp and not (r["trouvee_par"] == "leboncoin" and float(brut_fdp) == 0):
                    fdp = float(brut_fdp)          # Leboncoin / Vinted : frais ajoutés au prix par le bot (la médiane de la cote reste calculée sur le prix nu)
                elif r["trouvee_par"] in ("vinted", "leboncoin"):
                    fdp = prix_livre_vinted(prix) - prix      # lignes sans frais (avant la colonne fdp, ou Leboncoin à 0) : même prix livré que Vinted et eBay, mêmes frais par défaut que le bot
                else:
                    fdp = 0.0
                vues[(r["isbn13"], r["lien"])] = (r["etat"], round(prix + fdp, 2), r["titre"], r["trouvee_par"], jour, int(supp) if supp in ("0", "1") else None)
    limite = (date.fromisoformat(fichiers[-1].stem[-10:]) - timedelta(days=jours)).isoformat()
    sortie = {}
    for (isbn, lien), (etat, prix, titre, par, jour, supp) in vues.items():
        if jour >= limite:
            sortie.setdefault(isbn, {}).setdefault(etat, []).append([prix, titre, lien, par, jour, supp])
    return sortie


MINI_LARGEUR, MINI_QUALITE = 160, 65          # miniatures des petites vignettes (listes, rangées de 40 à 80 px d'affichage, nettes jusqu'à 2 fois la densité)


def fabriquer_minis(couvertures=None):
    """Miniatures (web/covers/mini/ISBN.webp, 160 px de large) tirées des jaquettes « small » : environ 5 Ko au lieu de 26 Ko.
    Une miniature est refaite seulement si sa jaquette source a changé (empreinte gardée dans web/covers/mini/sources.json) :
    pas de réécriture inutile, donc pas de bruit dans les envois. Sans Pillow, rien n'est fait. Renvoie le nombre de miniatures écrites."""
    try:
        from PIL import Image
    except ImportError:
        return 0
    couvertures = couvertures or COVERS
    src, dst = couvertures / "small", couvertures / "mini"
    if not src.exists():
        return 0
    dst.mkdir(exist_ok=True)
    registre = dst / "sources.json"
    try:
        connus = json.loads(registre.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        connus = {}
    ecrites, a_jour = 0, {}
    for f in sorted(src.glob("*.webp")):
        empreinte = hashlib.sha1(f.read_bytes()).hexdigest()
        cible = dst / f.name
        if connus.get(f.name) != empreinte or not cible.exists():
            with Image.open(f) as im:
                h = max(1, round(im.height * MINI_LARGEUR / im.width))
                im.convert("RGB").resize((MINI_LARGEUR, h), Image.LANCZOS).save(cible, "WEBP", quality=MINI_QUALITE, method=6)
            ecrites += 1
        a_jour[f.name] = empreinte
    for f in dst.glob("*.webp"):                      # miniature dont la jaquette a disparu
        if f.name not in a_jour:
            f.unlink()
    if a_jour != connus:
        registre.write_text(json.dumps(a_jour, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return ecrites


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--out", type=Path, default=SORTIE)
    ap.add_argument("--aujourdhui", type=date.fromisoformat, default=date.today(), help="date de référence (tests)")
    args = ap.parse_args()
    sortie = args.out
    if not args.db.exists():
        sys.exit(f"Base absente : lancez d'abord  python pipeline/build_db.py  ({args.db})")
    cx = sqlite3.connect(args.db)
    cx.row_factory = sqlite3.Row
    brut = {}
    for cle, etat, type_prix, jour, valeur, nb, source in cx.execute(PRIX):
        if args.db == DB and source == "ebay_api":
            continue                                                                  # eBay : remplacé par la cote v2 (pipeline/cote_v2.py)
        brut.setdefault(cle, {}).setdefault(etat, []).append(Obs(valeur, type_prix, date.fromisoformat(jour), nb))
    valides = validations.lire()                                                          # prix validés par le propriétaire
    ecart = etats.charger_ecart(DB.parent.parent / "manual" / "ratios_etats.json")                  # écart minimal entre deux états
    ratios = etats.charger_ratios(DB.parent.parent / "manual" / "ratios_etats.json")      # rapports entre états (propriétaire)
    # Relevés eBay déjà enregistrés : le modèle y mesure la décote des annonces anciennes, puis étend la cote aux
    # éditions qui n'ont pas 3 annonces récentes mais en ont 3 en tout (voir calibration.ajouter_toutes_annonces).
    releves = []
    for f in sorted((DB.parent.parent / "raw" / "occasion").glob("ebay-*.csv")):
        with open(f, newline="", encoding="utf-8") as fh:
            releves += list(csv.DictReader(fh))
    fraicheur = calibration.fraicheur(releves)
    nb_toutes, decotes = 0, {}
    if args.db == DB:
        cle_isbn = {r["isbn13"]: r["version_key"] for r in cx.execute(REQUETE) if r["isbn13"]}
        cote_v2.appliquer(brut, cle_isbn, DB.parent.parent / "raw" / "occasion")   # eBay : cote v2, une annonce = une observation
    # Auto-apprentissage : le modèle apprend l'écart entre archives et annonces actuelles, et s'en sert de deux façons :
    # 1. l'incertitude de l'archive (par état) règle la confiance que le lissage lui accorde ;
    # 2. s'il bat les archives (validation croisée), il remet à niveau celles des éditions sans relevé actuel.
    modele = calibration.apprendre(brut, args.aujourdhui)
    sig_arch = calibration.sigma_archive(modele)
    decote = etats.charger_decote(DB.parent.parent / "manual" / "ratios_etats.json")         # prix demandé -> prix visé (voir estimation.py)
    prix = {cle: {e: estimer(obs, args.aujourdhui, sig_arch.get(e), decote) for e, obs in par_etat.items()} for cle, par_etat in brut.items()}
    modele["fraicheur"] = fraicheur
    modele["sigma_archive"] = sig_arch
    trip = []
    for par in brut.values():
        a = {et: [o.prix for o in obs if o.type == "historique" and o.prix > 0] for et, obs in par.items()}
        if all(a.get(et) for et in ETATS):
            trip.append(tuple(statistics.median(a[et]) for et in ETATS))
    modele["rapports_etats_mesures_archives"] = etats.rapports_mesures(trip)
    modele["rapports_etats_retenus"] = ratios
    modele["toutes_annonces"] = {"lignes_ajoutees": nb_toutes, "decotes_utilisees": decotes}
    nb_recalibres = 0
    if modele["actif"]:
        for par_etat in prix.values():
            for e, est in par_etat.items():
                if est and est["source"] == "archives":
                    par_etat[e] = {**est, "prix": calibration.remettre_a_niveau(modele, est["prix"], e), "recalibre": True,
                                   "confiance": "faible"}
                    nb_recalibres += 1
    calibration.ecrire(modele, DB.parent.parent / "processed" / "calibration.json") if args.db == DB else None
    # Éditions encore en vente neuve : le relevé hebdomadaire des fiches de librairie (data/processed/prix_neuf.csv) donne le prix du
    # neuf et la disponibilité. Repli, dans l'ordre : prix relevé à la main sur le site de l'éditeur (data/manual/prix_editeur.csv),
    # puis prix à la parution de la notice BnF (data/processed/prix_editeur.csv), qui ne dit rien de la disponibilité.
    # data/manual/hors_vente.csv force une édition « plus en vente ». Une fiche marquée en_vente = 1 dans le catalogue le reste même si
    # le relevé de librairie ne la voit pas (livre vendu seulement chez l'éditeur ou sur Amazon).
    def lire_csv(chemin):
        if not chemin.exists():
            return {}
        with open(chemin, newline="", encoding="utf-8") as fh:
            return {r["isbn13"]: r for r in csv.DictReader(fh) if r.get("isbn13")}
    racine_donnees = DB.parent.parent
    auto = lire_csv(racine_donnees / "processed" / "prix_neuf.csv")
    manuel = {k: v for k, v in lire_csv(racine_donnees / "manual" / "prix_editeur.csv").items() if v.get("prix")}
    direct = {k for k, v in manuel.items() if v.get("vente_directe") == "1"}       # vendu seulement chez l'éditeur : la librairie ne le voit pas, ce n'est pas « hors vente »
    bnf = {k: v for k, v in lire_csv(racine_donnees / "processed" / "prix_editeur.csv").items() if v.get("prix")}
    hors_manuel = set(lire_csv(racine_donnees / "manual" / "hors_vente.csv"))      # décision du propriétaire : l'emporte toujours
    hors_vente = hors_manuel | {k for k, v in auto.items() if v.get("disponibilite") == "indisponible" and k not in direct}
    en_stock = {k for k, v in auto.items() if v.get("disponibilite") == "en_stock" and v.get("prix")}      # en vente neuve, constaté ce jour
    editeur = {}
    for isbn_e in set(bnf) | set(manuel) | set(auto):
        if isbn_e not in hors_vente and auto.get(isbn_e, {}).get("prix"):
            editeur[isbn_e] = {"prix": float(auto[isbn_e]["prix"]), "devise": "EUR", "source": "editeur", "date": auto[isbn_e].get("date")}
        elif isbn_e not in hors_vente and isbn_e in manuel:
            editeur[isbn_e] = {"prix": float(manuel[isbn_e]["prix"]), "devise": "EUR", "source": "editeur", "date": manuel[isbn_e].get("date")}
        elif isbn_e in bnf:
            editeur[isbn_e] = {"prix": float(bnf[isbn_e]["prix"]), "devise": bnf[isbn_e].get("devise") or "EUR", "source": "bnf"}
            continue
        else:
            continue
        if isbn_e in bnf and bnf[isbn_e].get("devise") == "EUR" and float(bnf[isbn_e]["prix"]) != editeur[isbn_e]["prix"]:
            editeur[isbn_e]["parution"] = float(bnf[isbn_e]["prix"])
    # Édition encore en vente neuve : un exemplaire en très bon état vaut le prix du neuf, donc le prix éditeur (décision du
    # propriétaire). Ce prix compte comme un prix actuel : les autres états en sont déduits (60 % / 40 %), un état d'archive
    # au-dessus est ramené sous lui par `aligner`.
    for r in cx.execute(REQUETE):
        e_ed = editeur.get(r["isbn13"]) if r["isbn13"] else None
        if e_ed and e_ed["source"] == "editeur":            # prix actuel relevé chez l'éditeur ; la notice BnF (prix à la parution) ne suffit pas
            prix.setdefault(r["version_key"], {})["tres_bon"] = {
                "prix": e_ed["prix"], "source": "neuf", "nature": "prix éditeur", "nb": 0, "date": e_ed.get("date") or args.aujourdhui.isoformat(),
                "confiance": "élevée", "incertitude": 0.05, "neuf": True}
    # Prix validés par le propriétaire : ils servent aussi de base pour déduire les états qu'il n'a pas chiffrés (60 % / 40 %)
    for r in cx.execute(REQUETE):
        for e in validations.ETATS:
            v = valides.get((r["isbn13"], e)) if r["isbn13"] else None
            if v:
                prix.setdefault(r["version_key"], {})[e] = {"prix": v["prix"], "source": "validé", "nature": "validé", "nb": 0, "date": v["le"],
                                                          "confiance": "validée", "incertitude": 0.03}
    # Déduction des états sans prix à partir des autres états de la même édition (rapports du propriétaire)
    nb_repartis = sum(etats.repartir(par_etat, ratios) for par_etat in prix.values())       # éditions avec un prix actuel
    nb_deduits = sum(etats.completer(par_etat, ratios) for par_etat in prix.values())       # éditions sans prix actuel, état manquant
    # Lissage quotidien : le prix du jour dépend de celui de la veille (voir etats.lisser). Appliqué à partir du 22 octobre 2026, après la
    # remise à zéro du relevé du 21 (annonces d'autres objets retirées), pour ne pas bloquer cette correction.
    nb_lisses = 0
    if args.aujourdhui.isoformat() >= LISSAGE_DEPUIS:
        veilles = [h for h in mouvements.charger(DB.parent.parent / "processed" / "cotes-historique.json") if h["date"] < args.aujourdhui.isoformat()]
        if veilles:
            veille = max(veilles, key=lambda h: h["date"])["prix"]
            gains = etats.charger_gains(DB.parent.parent / "manual" / "ratios_etats.json")
            isbn_de = {r["version_key"]: r["isbn13"] for r in cx.execute(REQUETE) if r["isbn13"]}
            for vk, par_etat in prix.items():
                isbn_v = isbn_de.get(vk)
                if isbn_v:
                    nb_lisses += etats.lisser(par_etat, {e: veille.get(f"{isbn_v}|{e}") for e in ETATS}, gains)
    nb_ajustes = sum(aligner(par_etat, ecart) for par_etat in prix.values())

    dates_maj = {x["id"]: x["date_maj"] for x in editions.load(None)}      # date d'ajout (ou de dernière mise à jour) de la fiche

    fabriquer_minis()
    versions = []
    cle_de = {}
    nb_valides = 0
    for r in cx.execute(REQUETE):
        cle_de[r["id"]] = r["version_key"]
        p = dict(prix.get(r["version_key"], {}))
        isbn = r["isbn13"]
        nb_valides += validations.appliquer(p, isbn, valides) if isbn else 0       # un prix validé prime sur tout le reste
        image = editions.cle_image(r["id"], isbn)                  # ISBN, ou identifiant simplifié pour une fiche sans ISBN
        petite = f"covers/small/{image}.webp" if (COVERS / "small" / f"{image}.webp").exists() else None
        grande = f"covers/medium/{image}.webp" if (COVERS / "medium" / f"{image}.webp").exists() else None
        mini = f"covers/mini/{image}.webp" if (COVERS / "mini" / f"{image}.webp").exists() else None
        versions.append({
            "id": r["id"], "isbn13": r["isbn13"], "titre": r["titre_version"], "livre_id": r["livre_id"],
            "livre": r["livre"], "serie": r["serie"], "numero": r["numero_serie"],
            "version": r["libelle_version"], "version_n": r["numero_version"],
            "derniere": bool(r["est_derniere_version"]),
            "en_vente": 1 if r["isbn13"] in en_stock else (None if (r["isbn13"] in hors_manuel or (r["isbn13"] in hors_vente and r["en_vente"] != 1)) else r["en_vente"]), "annee": r["annee"], "annee_bnf": r["annee_bnf"],
            "editeur": r["editeur"], "collection": r["collection_editeur"], "pages": r["pages"],
            "auteurs": r["auteurs"], "traducteur": r["traducteur"], "illustrateur": r["illustrateur"],
            "notice": r["notice_bnf"], "couverture": petite, "couverture_grande": grande, **({"couverture_mini": mini} if mini else {}), "statut": r["statut"],
            "maj": dates_maj.get(r["id"]),
            "prix": {e: (p.get(e) or {}).get("prix") for e in ETATS},
            **({"prix_editeur": editeur[isbn]} if isbn and isbn in editeur else {}),
            "nb_obs": {e: len(brut.get(r["version_key"], {}).get(e, [])) for e in ETATS},
            "prix_info": {e: {k: p[e][k] for k in ("source", "nature", "nb", "date", "confiance", "ajuste", "recalibre", "deduit", "repartition", "valide", "calcule", "decision", "par", "neuf") if k in p[e]}
                          for e in ETATS if p.get(e)},
        })
    # Ce qui a bougé depuis la publication précédente (à défaut : cote d'archives seule)
    hist_chemin = DB.parent.parent / "processed" / "cotes-historique.json"
    if args.db == DB:
        archives_seules = {cle: {e: estimer([o for o in obs if o.type == "historique"], args.aujourdhui) for e, obs in par_etat.items()}
                           for cle, par_etat in brut.items()}
        for par_etat in archives_seules.values():
            aligner(par_etat, ecart)
        dates_arch = [o.date for par in brut.values() for obs in par.values() for o in obs if o.type == "historique"]
        base_versions = [{"id": v["id"], "prix": {e: (archives_seules.get(r_cle, {}).get(e) or {}).get("prix") for e in ETATS}}
                         for v, r_cle in ((v, cle_de[v["id"]]) for v in versions)]
        base = mouvements.instantane(base_versions, max(dates_arch) if dates_arch else args.aujourdhui)
        mv = mouvements.mettre_a_jour(versions, args.aujourdhui, base, modele, hist_chemin, sortie / "mouvements.json")
        print(f"Prix validés par le propriétaire appliqués : {nb_valides}")
        print(f"États répartis 40/60 sur les éditions à prix actuel : {nb_repartis} prix modifiés ; états déduits pour les autres : {nb_deduits} ({ratios})")
        print(f"Annonces de toutes anciennetés ajoutées à la cote : {nb_toutes} lignes (décotes : {decotes}) ; incertitude de l'archive apprise : {sig_arch}")
        print(f"Mouvements depuis {mv['precedent']} : {mv['nb_modifiees']} prix modifiés sur {mv['nb_comparees']}, "
              f"{mv.get('nb_grands_mouvements', 0)} grands mouvements")
    meta = {
        "genere_le": args.aujourdhui.isoformat(),
        "nb_versions": len(versions),
        "nb_livres": len({v["livre_id"] for v in versions}),
        "nb_series": len({v["serie"] for v in versions}),
        "sources_prix": [r[0] for r in cx.execute(
            "SELECT DISTINCT s.nom FROM FaitPrix f JOIN DimSource s ON s.source_key = f.source_key")],
        "types_prix": [r[0] for r in cx.execute(
            "SELECT DISTINCT t.libelle FROM FaitPrix f JOIN DimTypePrix t ON t.type_key = f.type_key")],
    }
    # Page de revue des prix (outil du propriétaire) : archive, dernier relevé eBay et prix publié, côte à côte
    derniers = {}
    for r in releves:
        k = (r["isbn13"], r["etat"])
        if k not in derniers or r["date"] >= derniers[k]["date"]:
            derniers[k] = r
    # Exemplaires d'occasion proposés par les librairies (dernier relevé de chaque édition), pour la page de vérification
    libraires = {}
    for f in sorted((DB.parent.parent / "raw" / "occasion").glob("libraires-*.csv")):
        with open(f, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                libraires[(r["isbn13"], r["etat"])] = float(r["prix_median"])          # prix nu : la cote est nue, l'annonce est comparée livrée (+ 4,50 €)
    revue = []
    for v in versions:
        cle = cle_de[v["id"]]
        for e in ETATS:
            obs_e = brut.get(cle, {}).get(e, [])
            if v["prix"][e] is None and not obs_e:
                continue
            arch = [o.prix for o in obs_e if o.type == "historique" and o.prix > 0]
            eb = derniers.get((v["isbn13"], e))
            info = v["prix_info"].get(e, {})
            ligne = {"id": v["id"], "isbn": v["isbn13"], "titre": v["titre"], "serie": v["serie"], "numero": v["numero"],
                     "version": v["version"], "etat": e, "archive": round(statistics.median(arch), 2) if arch else None,
                     "publie": v["prix"][e], "source": info.get("source"), "nature": info.get("nature"),
                     "confiance": info.get("confiance"), "ajuste": bool(info.get("ajuste")), "recalibre": bool(info.get("recalibre")),
                     "deduit": bool(info.get("deduit")), "repartition": bool(info.get("repartition")), "neuf": bool(info.get("neuf"))}
            if (v["isbn13"], e) in libraires:
                ligne["lib_prix"] = libraires[(v["isbn13"], e)] + FRAIS_LIBRAIRIE          # prix livré, comparé à la cote nue
            if info.get("valide"):
                ligne.update({"valide": True, "valide_le": info.get("date"), "calcule": info.get("calcule"), "decision": info.get("decision"), "valide_par": info.get("par")})
            if eb:
                ligne.update({"eb_date": eb["date"], "eb_nb": int(eb["nb_annonces"]), "eb_min": float(eb["prix_min"]),
                              "eb_med": float(eb["prix_median"]), "eb_max": float(eb["prix_max"])})
                if eb.get("nb_toutes"):
                    ligne.update({"eb_nb_toutes": int(eb["nb_toutes"]), "eb_med_toutes": float(eb["prix_median_toutes"])})
            revue.append(ligne)
    # Annonces retenues par le dernier relevé eBay (titre, prix, lien) : l'onglet « Annonces » de l'espace administrateur les montre pour que chaque prix puisse
    # être contrôlé à la main (bon livre ? bon état ?). Absent tant qu'aucun relevé ne les a enregistrées.
    dossier_occasion = DB.parent.parent / "raw" / "occasion"
    fichiers_ann = sorted(f for f in dossier_occasion.glob("annonces-*.csv") if "leboncoin" not in f.name and "vinted" not in f.name)         # eBay
    annonces = annonces_cumulees(fichiers_ann)          # toutes les annonces vues, pas seulement celles du dernier relevé (voir annonces_cumulees)
    # Annonces Leboncoin envoyées par le bot du propriétaire (pipeline/importer_leboncoin.py) : même présentation, mais leur propre date de relevé,
    # pour qu'un relevé eBay plus récent ne les fasse pas passer pour « plus en ligne ».
    fichiers_lbc = sorted(dossier_occasion.glob("annonces-leboncoin-20*.csv"))
    lots = importer_leboncoin.charger_lots()
    liens_vendus = set()                                  # annonces Leboncoin signalées vendues par le bot : elles ne sont plus en ligne
    for f in dossier_occasion.glob("vendus-leboncoin-20*.csv"):
        with open(f, newline="", encoding="utf-8") as fh:
            liens_vendus.update(r["lien"] for r in csv.DictReader(fh))
    for isbn, par_etat in annonces_cumulees(fichiers_lbc, jours=JOURS_LEBONCOIN).items():
        for etat, liste in par_etat.items():
            liste = [a for a in liste if a[2] not in liens_vendus]
            if liste:
                annonces.setdefault(isbn, {}).setdefault(etat, []).extend(liste)
    # Annonces Vinted envoyées par le même bot : même présentation. Tout s'y commande : le prix affiché est le prix livré (protection acheteurs et port compris),
    # comparé à la cote nue ; le prix nu reste celui de l'annonce dans le fichier d'import.
    fichiers_vinted = sorted(dossier_occasion.glob("annonces-vinted-20*.csv"))
    liens_vendus_vinted = set()
    for f in dossier_occasion.glob("vendus-vinted-20*.csv"):
        with open(f, newline="", encoding="utf-8") as fh:
            liens_vendus_vinted.update(r["lien"] for r in csv.DictReader(fh))
    for isbn, par_etat in annonces_cumulees(fichiers_vinted, jours=JOURS_VINTED).items():
        for etat, liste in par_etat.items():
            liste = [a for a in liste if a[2] not in liens_vendus_vinted]          # le prix est déjà livré : la colonne fdp du relevé est ajoutée par annonces_cumulees
            if liste:
                annonces.setdefault(isbn, {}).setdefault(etat, []).extend(liste)
    importer_leboncoin.etaler_lots(annonces, lots)     # annonce de lot : une ligne « Lot de N livres », au prix de sa part, sous chacun de ses livres
    # Exemplaires relevés en librairie (leslibraires.fr) : présentés comme des annonces, avec le lien de la page du livre
    titres = {v["isbn13"]: v["titre"] for v in versions}
    for (isbn, etat), prix in libraires.items():
        if isbn in titres:
            annonces.setdefault(isbn, {}).setdefault(etat, []).append([round(prix + FRAIS_LIBRAIRIE, 2), f"{titres[isbn]} · librairie indépendante", f"https://www.leslibraires.fr/livre/{isbn}", "librairie", None, 1])      # une librairie n'indique pas l'état : supposé
    if annonces:
        for par_etat in annonces.values():
            for liste in par_etat.values():
                liste.sort()
        fichiers_lib = sorted((DB.parent.parent / "raw" / "occasion").glob("libraires-*.csv"))
        date_ann = max([f.stem[-10:] for f in fichiers_ann[-1:] + fichiers_lib[-1:] + fichiers_lbc[-1:] + fichiers_vinted[-1:]])
        # Annonces : réservées aux sorciers et aux Zagors. Elles ne sont pas publiées sur le site : le relais les lit dans data/processed/.
        chemin_ann = DB.parent.parent / "processed" / "annonces.json"
        try:
            anciennes = json.loads(chemin_ann.read_text(encoding="utf-8")).get("premieres")        # None : fichier d'avant cette information
        except (OSError, ValueError):
            anciennes = None
        try:
            historiques = json.loads((DB.parent.parent / "manual" / "premieres_historiques.json").read_text(encoding="utf-8"))      # heures retrouvées dans l'historique git
        except (OSError, ValueError):
            historiques = {}
        premieres = premieres_vues(annonces, anciennes, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), historiques)
        try:
            captures_avant = json.loads(chemin_ann.read_text(encoding="utf-8")).get("captures")
        except (OSError, ValueError):
            captures_avant = None
        captures = mettre_a_jour_captures(captures_avant, annonces, premieres, datetime.now(timezone.utc).date().isoformat())
        chemin_ann.write_text(json.dumps({"date": date_ann, "date_ebay": fichiers_ann[-1].stem[-10:] if fichiers_ann else None,
                                          "date_lbc": fichiers_lbc[-1].stem[-10:] if fichiers_lbc else None, "annonces": annonces, "premieres": premieres,
                                          "captures": captures},
                                         ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        ages_ebay = {}
        if fichiers_ann:
            with open(fichiers_ann[-1], newline="", encoding="utf-8") as fh:
                for r_ in csv.DictReader(fh):
                    try:
                        ages_ebay.setdefault(r_["isbn13"], []).append(int(float(r_["age_jours"])))
                    except (KeyError, ValueError):
                        pass
        # Butin : seulement les bonnes affaires, pour les niveaux 2 et 3 (le relais ne leur sert pas le fichier complet)
        (DB.parent.parent / "processed" / "butin.json").write_text(json.dumps({"date": date_ann, "date_ebay": fichiers_ann[-1].stem[-10:] if fichiers_ann else None,
                                                          "date_lbc": fichiers_lbc[-1].stem[-10:] if fichiers_lbc else None, "annonces": (butin := extraire_butin(annonces, revue)),
                                                          "premieres": {a_[2]: premieres[a_[2]] for par_ in butin.values() for l_ in par_.values() for a_ in l_ if a_[2] in premieres},
                                                          "captures": {"jours": dict(list(captures["jours"].items())[-30:]), "depuis": captures.get("depuis")},
                                                          "offre": calculer_offre(annonces, ages_ebay, fichiers_ann[-1].stem[-10:] if fichiers_ann else None, fichiers_lbc[-1].stem[-10:] if fichiers_lbc else None)},
                                                         ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (sortie / "revue.json").write_text(json.dumps(revue, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (sortie / "tendances.json").write_text(json.dumps(tendances.calculer(revue, versions, mouvements.charger(hist_chemin), args.aujourdhui.isoformat()),
                                                      ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    nb_actuels = sum(1 for v in versions for i in v["prix_info"].values() if i["source"] != "archives")
    meta["nb_prix_actuels"] = nb_actuels
    meta["calibration"] = {k: modele.get(k) for k in ("actif", "n_paires", "gain", "raison", "calcule_le", "rapport_global")}
    meta["calibration"]["nb_recalibres"] = nb_recalibres
    sortie.mkdir(parents=True, exist_ok=True)
    annonces = veille_parutions.charger().get("a_paraitre", {})                                           # parutions à venir (veille des parutions)
    for v_ in versions:
        if annonces.get(v_["isbn13"], "") > args.aujourdhui.isoformat():
            v_["parution"] = annonces[v_["isbn13"]]
    hist_pub = sorted(mouvements.charger(hist_chemin), key=lambda h: h["date"])[-10:]        # cotes publiées aux dernières dates : la tendance de la collection se calcule dans le navigateur
    cles = sorted({k for h in hist_pub for k in h["prix"]})
    (sortie / "historique.json").write_text(json.dumps({"dates": [h["date"] for h in hist_pub],
                                                         "cotes": {k: [h["prix"].get(k) for h in hist_pub] for k in cles}},
                                                        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    rarete.annoter(versions, rarete.charger(DB.parent.parent / "raw" / "collection-ldvelh"), rarete.charger_tirages())                # rareté (information), d'après les collections de collection-ldvelh.fr
    (sortie / "versions.json").write_text(json.dumps(versions, ensure_ascii=False, separators=(",", ":")),
                                          encoding="utf-8")
    (sortie / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    sans_image = sum(1 for v in versions if not v["couverture"])
    sans_prix = sum(1 for v in versions if all(x is None for x in v["prix"].values()))
    taille = (sortie / "versions.json").stat().st_size // 1024
    print(f"{len(versions)} versions, {meta['nb_livres']} livres, {meta['nb_series']} séries exportés "
          f"({taille} Ko) ; {nb_ajustes} prix remonté(s) pour rester cohérents (C ≤ BE ≤ TBE) ; {nb_lisses} prix lissé(s) sur la veille ; {sans_prix} version(s) sans prix ; {sans_image} sans jaquette ; modèle d'auto-apprentissage : {'ACTIF (' + str(nb_recalibres) + ' prix remis à niveau)' if modele['actif'] else 'inactif (' + modele['raison'] + ')'}")


if __name__ == "__main__":
    main()
