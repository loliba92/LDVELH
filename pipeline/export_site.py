"""Exporte la base en étoile vers les fichiers lus par le site (web/data/).

Pour chaque version et chaque état, le prix est estimé par pipeline/estimation.py (médiane pondérée des
observations hors lots : natures, fraîcheur, nombre d'annonces). Sans relevé actuel, c'est le prix d'archive.

    python pipeline/build_db.py && python pipeline/export_site.py
"""
import argparse
import csv
import json
import sqlite3
import statistics
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
from estimation import Obs, estimer
import calibration
import mouvements

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
SELECT f.version_key, e.code, t.code, d.date, f.prix, f.nb_annonces
FROM FaitPrix f
JOIN DimEtat e ON e.etat_key = f.etat_key
JOIN DimTypePrix t ON t.type_key = f.type_key
JOIN DimDate d ON d.date_key = f.date_key
WHERE f.est_lot = 0
"""
ETATS = ("convenable", "bon", "tres_bon")


def aligner(par_etat):
    """Cohérence : un état supérieur ne vaut jamais moins qu'un état inférieur (convenable <= bon <= très bon).
    Règle générale : le prix de l'état supérieur est remonté au niveau de l'état inférieur, et marqué « ajusté ».
    Exception : si l'état inférieur n'est qu'une archive alors que l'état supérieur vient d'un relevé actuel, c'est
    l'archive qu'on ramène à la donnée actuelle (sinon une archive gonflée tirerait vers le haut un prix actuel).
    Renvoie le nombre de prix modifiés."""
    ordre = [e for e in ETATS if par_etat.get(e)]
    fiables = {e for e in ordre if par_etat[e]["source"] != "archives"}      # valeur issue d'un relevé actuel
    for _ in range(3):
        change = False
        for bas, haut in zip(ordre, ordre[1:]):
            b, h = par_etat[bas], par_etat[haut]
            if h["prix"] < b["prix"] - 1e-9:
                if haut in fiables and bas not in fiables:
                    par_etat[bas] = {**b, "prix": h["prix"], "ajuste": True}
                    fiables.add(bas)
                else:
                    par_etat[haut] = {**h, "prix": b["prix"], "ajuste": True}
                    if bas in fiables:
                        fiables.add(haut)
                change = True
        if not change:
            break
    return sum(1 for e in ordre if par_etat[e].get("ajuste"))


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
    for cle, etat, type_prix, jour, valeur, nb in cx.execute(PRIX):
        brut.setdefault(cle, {}).setdefault(etat, []).append(Obs(valeur, type_prix, date.fromisoformat(jour), nb))
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
        nb_toutes, decotes = calibration.ajouter_toutes_annonces(brut, releves, cle_isbn, fraicheur)
    # Auto-apprentissage : le modèle apprend l'écart entre archives et annonces actuelles, et s'en sert de deux façons :
    # 1. l'incertitude de l'archive (par état) règle la confiance que le lissage lui accorde ;
    # 2. s'il bat les archives (validation croisée), il remet à niveau celles des éditions sans relevé actuel.
    modele = calibration.apprendre(brut, args.aujourdhui)
    sig_arch = calibration.sigma_archive(modele)
    prix = {cle: {e: estimer(obs, args.aujourdhui, sig_arch.get(e)) for e, obs in par_etat.items()} for cle, par_etat in brut.items()}
    modele["fraicheur"] = fraicheur
    modele["sigma_archive"] = sig_arch
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
    nb_ajustes = sum(aligner(par_etat) for par_etat in prix.values())

    versions = []
    cle_de = {}
    for r in cx.execute(REQUETE):
        cle_de[r["id"]] = r["version_key"]
        p = prix.get(r["version_key"], {})
        isbn = r["isbn13"]
        petite = f"covers/small/{isbn}.webp" if isbn and (COVERS / "small" / f"{isbn}.webp").exists() else None
        grande = f"covers/medium/{isbn}.webp" if isbn and (COVERS / "medium" / f"{isbn}.webp").exists() else None
        versions.append({
            "id": r["id"], "isbn13": r["isbn13"], "titre": r["titre_version"], "livre_id": r["livre_id"],
            "livre": r["livre"], "serie": r["serie"], "numero": r["numero_serie"],
            "version": r["libelle_version"], "version_n": r["numero_version"],
            "derniere": bool(r["est_derniere_version"]),
            "en_vente": r["en_vente"], "annee": r["annee"], "annee_bnf": r["annee_bnf"],
            "editeur": r["editeur"], "collection": r["collection_editeur"], "pages": r["pages"],
            "auteurs": r["auteurs"], "traducteur": r["traducteur"], "illustrateur": r["illustrateur"],
            "notice": r["notice_bnf"], "couverture": petite, "couverture_grande": grande, "statut": r["statut"],
            "prix": {e: (p.get(e) or {}).get("prix") for e in ETATS},
            "nb_obs": {e: len(brut.get(r["version_key"], {}).get(e, [])) for e in ETATS},
            "prix_info": {e: {k: p[e][k] for k in ("source", "nature", "nb", "date", "confiance", "ajuste", "recalibre") if k in p[e]}
                          for e in ETATS if p.get(e)},
        })
    # Ce qui a bougé depuis la publication précédente (à défaut : cote d'archives seule)
    hist_chemin = DB.parent.parent / "processed" / "cotes-historique.json"
    if args.db == DB:
        archives_seules = {cle: {e: estimer([o for o in obs if o.type == "historique"], args.aujourdhui) for e, obs in par_etat.items()}
                           for cle, par_etat in brut.items()}
        for par_etat in archives_seules.values():
            aligner(par_etat)
        dates_arch = [o.date for par in brut.values() for obs in par.values() for o in obs if o.type == "historique"]
        base_versions = [{"id": v["id"], "prix": {e: (archives_seules.get(r_cle, {}).get(e) or {}).get("prix") for e in ETATS}}
                         for v, r_cle in ((v, cle_de[v["id"]]) for v in versions)]
        base = mouvements.instantane(base_versions, max(dates_arch) if dates_arch else args.aujourdhui)
        mv = mouvements.mettre_a_jour(versions, args.aujourdhui, base, modele, hist_chemin, sortie / "mouvements.json")
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
                     "confiance": info.get("confiance"), "ajuste": bool(info.get("ajuste")), "recalibre": bool(info.get("recalibre"))}
            if eb:
                ligne.update({"eb_date": eb["date"], "eb_nb": int(eb["nb_annonces"]), "eb_min": float(eb["prix_min"]),
                              "eb_med": float(eb["prix_median"]), "eb_max": float(eb["prix_max"])})
                if eb.get("nb_toutes"):
                    ligne.update({"eb_nb_toutes": int(eb["nb_toutes"]), "eb_med_toutes": float(eb["prix_median_toutes"])})
            revue.append(ligne)
    (sortie / "revue.json").write_text(json.dumps(revue, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    nb_actuels = sum(1 for v in versions for i in v["prix_info"].values() if i["source"] != "archives")
    meta["nb_prix_actuels"] = nb_actuels
    meta["calibration"] = {k: modele.get(k) for k in ("actif", "n_paires", "gain", "raison", "calcule_le", "rapport_global")}
    meta["calibration"]["nb_recalibres"] = nb_recalibres
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "versions.json").write_text(json.dumps(versions, ensure_ascii=False, separators=(",", ":")),
                                          encoding="utf-8")
    (sortie / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    sans_image = sum(1 for v in versions if not v["couverture"])
    sans_prix = sum(1 for v in versions if all(x is None for x in v["prix"].values()))
    taille = (sortie / "versions.json").stat().st_size // 1024
    print(f"{len(versions)} versions, {meta['nb_livres']} livres, {meta['nb_series']} séries exportés "
          f"({taille} Ko) ; {nb_ajustes} prix remonté(s) pour rester cohérents (C ≤ BE ≤ TBE) ; {sans_prix} version(s) sans prix ; {sans_image} sans jaquette ; modèle d'auto-apprentissage : {'ACTIF (' + str(nb_recalibres) + ' prix remis à niveau)' if modele['actif'] else 'inactif (' + modele['raison'] + ')'}")


if __name__ == "__main__":
    main()
