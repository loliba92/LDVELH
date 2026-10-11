"""Exporte la base en étoile vers les fichiers lus par le site (web/data/).

Pour chaque version et chaque état, le prix est estimé par pipeline/estimation.py (médiane pondérée des
observations hors lots : natures, fraîcheur, nombre d'annonces). Sans relevé actuel, c'est le prix d'archive.

    python pipeline/build_db.py && python pipeline/export_site.py
"""
import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
from estimation import Obs, estimer

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
    # Deux séries : les particuliers (et archives) d'un côté, les professionnels de l'autre
    prix, prix_pro = {}, {}
    for cle, par_etat in brut.items():
        for e, obs in par_etat.items():
            prix.setdefault(cle, {})[e] = estimer([o for o in obs if o.type != "prix_pro"], args.aujourdhui)
            pro = estimer([o for o in obs if o.type == "prix_pro"], args.aujourdhui)
            if pro:
                prix_pro.setdefault(cle, {})[e] = pro

    versions = []
    for r in cx.execute(REQUETE):
        p = prix.get(r["version_key"], {})
        pp = prix_pro.get(r["version_key"], {})
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
            "nb_obs": {e: sum(1 for o in brut.get(r["version_key"], {}).get(e, []) if o.type != "prix_pro") for e in ETATS},
            "prix_info": {e: {k: p[e][k] for k in ("source", "nature", "nb", "date", "confiance")}
                          for e in ETATS if p.get(e)},
            "prix_pro": {e: pp[e]["prix"] for e in ETATS if e in pp},
            "prix_pro_info": {e: {k: pp[e][k] for k in ("nb", "date", "confiance")} for e in ETATS if e in pp},
        })
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
    nb_actuels = sum(1 for v in versions for i in v["prix_info"].values() if i["source"] != "archives")
    meta["nb_prix_actuels"] = nb_actuels
    sortie.mkdir(parents=True, exist_ok=True)
    (sortie / "versions.json").write_text(json.dumps(versions, ensure_ascii=False, separators=(",", ":")),
                                          encoding="utf-8")
    (sortie / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    sans_image = sum(1 for v in versions if not v["couverture"])
    sans_prix = sum(1 for v in versions if all(x is None for x in v["prix"].values()))
    taille = (sortie / "versions.json").stat().st_size // 1024
    print(f"{len(versions)} versions, {meta['nb_livres']} livres, {meta['nb_series']} séries exportés "
          f"({taille} Ko) ; {sans_prix} version(s) sans prix ; {sans_image} sans jaquette")


if __name__ == "__main__":
    main()
