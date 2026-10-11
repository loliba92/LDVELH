"""Exporte la base en étoile vers les fichiers lus par le site (web/data/).

Pour chaque version, le prix par état est la MOYENNE des observations (hors lots) de cet état.

    python pipeline/build_db.py && python pipeline/export_site.py
"""
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions

DB = editions.ROOT / "data" / "warehouse" / "ldvelh.sqlite"
SORTIE = editions.ROOT / "web" / "data"

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
SELECT f.version_key, e.code, ROUND(AVG(f.prix), 2), COUNT(*)
FROM FaitPrix f JOIN DimEtat e ON e.etat_key = f.etat_key
WHERE f.est_lot = 0
GROUP BY f.version_key, e.code
"""


def main():
    if not DB.exists():
        sys.exit(f"Base absente : lancez d'abord  python pipeline/build_db.py  ({DB})")
    cx = sqlite3.connect(DB)
    cx.row_factory = sqlite3.Row
    prix = {}
    for cle, etat, moyenne, nb in cx.execute(PRIX):
        prix.setdefault(cle, {})[etat] = {"prix": moyenne, "nb": nb}

    versions = []
    for r in cx.execute(REQUETE):
        p = prix.get(r["version_key"], {})
        versions.append({
            "id": r["id"], "isbn13": r["isbn13"], "titre": r["titre_version"], "livre_id": r["livre_id"],
            "livre": r["livre"], "serie": r["serie"], "numero": r["numero_serie"],
            "version": r["libelle_version"], "version_n": r["numero_version"],
            "derniere": bool(r["est_derniere_version"]),
            "en_vente": r["en_vente"], "annee": r["annee"], "annee_bnf": r["annee_bnf"],
            "editeur": r["editeur"], "collection": r["collection_editeur"], "pages": r["pages"],
            "auteurs": r["auteurs"], "traducteur": r["traducteur"], "illustrateur": r["illustrateur"],
            "notice": r["notice_bnf"], "couverture": r["couverture"], "statut": r["statut"],
            "prix": {e: p.get(e, {}).get("prix") for e in ("convenable", "bon", "tres_bon")},
            "nb_obs": {e: p.get(e, {}).get("nb", 0) for e in ("convenable", "bon", "tres_bon")},
        })
    meta = {
        "genere_le": date.today().isoformat(),
        "nb_versions": len(versions),
        "nb_livres": len({v["livre_id"] for v in versions}),
        "nb_series": len({v["serie"] for v in versions}),
        "sources_prix": [r[0] for r in cx.execute(
            "SELECT DISTINCT s.nom FROM FaitPrix f JOIN DimSource s ON s.source_key = f.source_key")],
        "types_prix": [r[0] for r in cx.execute(
            "SELECT DISTINCT t.libelle FROM FaitPrix f JOIN DimTypePrix t ON t.type_key = f.type_key")],
    }
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "versions.json").write_text(json.dumps(versions, ensure_ascii=False, separators=(",", ":")),
                                          encoding="utf-8")
    (SORTIE / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    sans_prix = sum(1 for v in versions if all(x is None for x in v["prix"].values()))
    taille = (SORTIE / "versions.json").stat().st_size // 1024
    print(f"{len(versions)} versions, {meta['nb_livres']} livres, {meta['nb_series']} séries exportés "
          f"({taille} Ko) ; {sans_prix} version(s) sans prix")


if __name__ == "__main__":
    main()
