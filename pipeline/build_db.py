"""Construit la base SQLite en étoile : data/warehouse/ldvelh.sqlite.

La base est reconstruite entièrement à chaque exécution à partir des fichiers
(la vérité reste dans les CSV) :
  - data/processed/editions.csv                 -> DimLivre, DimVersion
  - data/raw/collection-ldvelh/*.csv (dernier)  -> FaitPrix (prix historiques)
  - data/manual/observations.csv                -> FaitPrix (vos ventes, relevés à la main)

    python pipeline/build_db.py
"""
import argparse
import csv
import re
import sqlite3
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions

ROOT = editions.ROOT
DB = ROOT / "data" / "warehouse" / "ldvelh.sqlite"
SCHEMA = Path(__file__).resolve().parent / "schema.sql"
MANUAL = ROOT / "data" / "manual" / "observations.csv"
OCCASION = ROOT / "data" / "raw" / "occasion"
RAW = ROOT / "data" / "raw" / "collection-ldvelh"

ETATS = [  # code, libellé, rang, description
    ("inconnu", "Non précisé", 0, "État non indiqué par la source"),
    ("convenable", "Convenable", 1, "Usé mais complet et lisible"),
    ("bon", "Bon état", 2, "Quelques marques d'usage"),
    ("tres_bon", "Très bon état", 3, "Presque comme neuf"),
    ("neuf", "Neuf", 4, "Jamais lu, sous blister ou non"),
]
SOURCES = [  # code, nom, famille, accès, fiabilité
    ("collection_ldvelh", "Relevé d'archives (historique)", "historique", "fichier", 0.3),
    ("ebay_api", "eBay (interface officielle)", "marketplace", "api", 0.8),
    ("vente_perso", "Mes ventes", "perso", "saisie", 1.0),
    ("achat_perso", "Mes achats", "perso", "saisie", 0.9),
    ("releve_manuel", "Relevé manuel (Vinted, Leboncoin, comparateurs)", "marketplace", "saisie", 0.6),
    ("communaute", "Contribution d'un visiteur", "communaute", "saisie", 0.5),
]
TYPES = [  # code, libellé, poids, prix réel ?
    ("vente_reelle", "Vente réelle", 1.0, 1),
    ("vente_probable", "Vente probable (annonce disparue)", 0.6, 0),
    ("prix_demande", "Prix demandé (annonce active)", 0.3, 0),
    ("rachat", "Prix de rachat par un professionnel", 0.4, 1),
    ("historique", "Prix historique", 0.2, 0),
]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
ETAT_RAW = {"prix_convenable": "convenable", "prix_bon_etat": "bon", "prix_tres_bon_etat": "tres_bon"}


def slug(texte):
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def to_float(x):
    try:
        return float(str(x).replace(",", ".").strip())
    except ValueError:
        return None


def date_row(d):
    return (int(d.strftime("%Y%m%d")), d.isoformat(), d.year, (d.month - 1) // 3 + 1, d.month,
            MOIS[d.month - 1], d.strftime("%Y-%m"), d.isocalendar()[1], d.isoweekday(),
            JOURS[d.weekday()])


def ensure_date(cx, d):
    cx.execute("INSERT OR IGNORE INTO DimDate VALUES (?,?,?,?,?,?,?,?,?,?)", date_row(d))
    return int(d.strftime("%Y%m%d"))


def load_dimensions(cx):
    d, fin = date(2024, 1, 1), date(2035, 12, 31)
    while d <= fin:
        cx.execute("INSERT INTO DimDate VALUES (?,?,?,?,?,?,?,?,?,?)", date_row(d))
        d += timedelta(days=1)
    cx.executemany("INSERT INTO DimEtat(code,libelle,rang,description) VALUES (?,?,?,?)", ETATS)
    cx.executemany("INSERT INTO DimSource(code,nom,famille,acces,fiabilite) VALUES (?,?,?,?,?)", SOURCES)
    cx.executemany("INSERT INTO DimTypePrix(code,libelle,poids_modele,est_prix_reel) VALUES (?,?,?,?)", TYPES)


def load_series(cx, rows):
    """Une ligne par série ; « Non classée » sert aux livres sans série."""
    series = {}
    for r in rows:
        nom = (r.get("serie") or "").strip() or "Non classée"
        series.setdefault(slug(nom), nom)
    keys = {}
    for code, nom in sorted(series.items()):
        membres = [r for r in rows if (slug((r.get("serie") or "").strip() or "Non classée")) == code]
        annees = [int(r["annee"]) for r in membres if (r.get("annee") or "").isdigit()]
        editeurs = [r["editeur"] for r in membres if r.get("editeur")]
        principal = max(set(editeurs), key=editeurs.count) if editeurs else None
        cur = cx.execute("INSERT INTO DimSerie(code,nom,nb_versions,annee_min,annee_max,editeur_principal) "
                         "VALUES (?,?,?,?,?,?)", (code, nom, len(membres),
                                                  min(annees) if annees else None,
                                                  max(annees) if annees else None, principal))
        keys[code] = cur.lastrowid
    return keys


def serie_code(r):
    return slug((r.get("serie") or "").strip() or "Non classée")


def load_livres_versions(cx):
    rows = editions.load()
    series_keys = load_series(cx, rows)
    # Deux versions ne sont regroupées que si la colonne « livre » est renseignée et identique.
    # Deux titres identiques peuvent désigner des jeux différents : jamais de regroupement automatique.
    groupes = {}
    for r in rows:
        if (r.get("livre") or "").strip():
            nom = r["livre"].strip()
            cle = "livre-" + slug(r.get("serie") or "") + "-" + slug(nom)  # même nom dans deux séries : deux livres
        else:
            nom = r["titre"].strip()
            cle = f"{slug(nom)}-{r['id'].lower()}"
        groupes.setdefault(cle, []).append((nom, r))
    for livre_id, membres in groupes.items():
        nom = membres[0][0]
        auteurs = next((r["auteurs"] for _, r in membres if r.get("auteurs")), None)
        cur = cx.execute("INSERT INTO DimLivre(livre_id,titre,auteurs,nb_versions) VALUES (?,?,?,?)",
                         (livre_id, nom, auteurs, len(membres)))
        livre_key = cur.lastrowid
        # Numéro de version : celui indiqué (V3 -> 3), sinon l'ordre chronologique
        def annee(r):
            return int(r["annee"]) if (r.get("annee") or "").isdigit() else 9999
        ordre = sorted((r for _, r in membres), key=lambda r: (annee(r), r["id"]))
        numeros = {}
        for i, r in enumerate(ordre, start=1):
            m = re.search(r"\d+", r.get("version") or "")
            numeros[r["id"]] = int(m.group()) if m else i
        derniere = max(numeros.values())
        for _, r in membres:
            n = numeros[r["id"]]
            ev = r.get("en_vente")
            cx.execute(
                """INSERT INTO DimVersion(id,isbn13,isbn10,livre_key,serie_key,numero_version,libelle_version,
                   est_derniere_version,en_vente,titre_version,numero_serie,editeur,
                   collection_editeur,annee,annee_bnf,pages,traducteur,illustrateur,notice_bnf,couverture,statut)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["id"], r.get("isbn13") or None, r.get("isbn10") or None, livre_key,
                 series_keys[serie_code(r)], n,
                 (r.get("version") or f"V{n}").strip(), int(n == derniere),
                 int(ev) if ev in ("0", "1") else None, r["titre"],
                 r.get("numero") or None, r.get("editeur") or None, r.get("collection_editeur") or None,
                 int(r["annee"]) if (r.get("annee") or "").isdigit() else None,
                 int(r["annee_bnf"]) if (r.get("annee_bnf") or "").isdigit() else None,
                 int(r["pages"]) if (r.get("pages") or "").isdigit() else None,
                 r.get("traducteur") or None, r.get("illustrateur") or None,
                 r.get("notice_bnf") or None, r.get("couverture") or None, r.get("statut") or "brut"))


def insert_fait(cx, version_id, d, source, type_prix, etat, prix, port=None, lot=0, url=None, nb=1):
    v = cx.execute("SELECT version_key, livre_key, serie_key FROM DimVersion WHERE id=?", (version_id,)).fetchone()
    if v is None:
        raise ValueError(f"édition inconnue : {version_id}")
    keys = {}
    for table, col, code in (("DimEtat", "etat_key", etat), ("DimSource", "source_key", source),
                             ("DimTypePrix", "type_key", type_prix)):
        row = cx.execute(f"SELECT {col} FROM {table} WHERE code=?", (code,)).fetchone()
        if row is None:
            raise ValueError(f"{table[3:].lower()} inconnu : {code}")
        keys[col] = row[0]
    date_key = ensure_date(cx, d)
    cle = "|".join(map(str, (version_id, etat, d, source, type_prix, prix, url or "")))
    cur = cx.execute(
        """INSERT OR IGNORE INTO FaitPrix(version_key,livre_key,serie_key,etat_key,date_key,source_key,type_key,
           prix,frais_port,est_lot,nb_annonces,url,cle_naturelle,date_chargement) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (v[0], v[1], v[2], keys["etat_key"], date_key, keys["source_key"], keys["type_key"], prix, port,
         lot, nb, url, cle, datetime.now().isoformat(timespec="seconds")))
    return cur.rowcount


def load_historique(cx):
    fichiers = sorted(RAW.glob("books_data-*.csv"))
    if not fichiers:
        return 0, 0, 0
    n = ignores = orphelins = 0
    with open(fichiers[-1], newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                ident = editions.normalize_isbn(r.get("isbn") or "")[0]
            except ValueError:
                continue
            d = date.fromisoformat(r["last_date"])
            for col, etat in ETAT_RAW.items():
                prix = to_float(r.get(col))
                if prix is None or prix <= 0:
                    ignores += 1
                    continue
                try:
                    n += insert_fait(cx, ident, d, "collection_ldvelh", "historique", etat, round(prix, 2))
                except ValueError:  # édition absente de editions.csv : on l'écarte et on le signale
                    orphelins += 1
    return n, ignores, orphelins


def load_manuel(cx, chemin):
    n, doublons, erreurs = 0, 0, []
    if not Path(chemin).exists():
        return 0, 0, erreurs
    with open(chemin, newline="", encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            try:
                ident = editions.normalize_isbn(r["isbn"])[0]
                prix = to_float(r["prix"])
                if prix is None:
                    raise ValueError(f"prix illisible : {r['prix']}")
                ajoute = insert_fait(cx, ident, date.fromisoformat(r["date"]), r["source"], r["type_prix"],
                                     r.get("etat") or "inconnu", prix, to_float(r.get("frais_port")),
                                     int(r.get("lot") or 0), r.get("url") or None, max(1, int(r.get("nb") or 1)))
                n += ajoute
                doublons += 1 - ajoute
            except (ValueError, KeyError) as e:
                erreurs.append(f"ligne {i} : {e}")
    return n, doublons, erreurs


def load_ebay(cx, dossier):
    """Relevés d'annonces eBay agrégés : data/raw/occasion/ebay-AAAA-MM-JJ.csv.

    Une ligne par livre et par état : isbn13, date, etat, nb_annonces, prix_min, prix_median, prix_max.
    Seule la médiane entre dans la base (nature « prix demandé », nombre d'annonces conservé).
    """
    n, doublons, erreurs, fichiers = 0, 0, [], sorted(Path(dossier).glob("ebay-*.csv"))
    for fichier in fichiers:
        with open(fichier, newline="", encoding="utf-8") as f:
            for i, r in enumerate(csv.DictReader(f), start=2):
                try:
                    ident = editions.normalize_isbn(r["isbn13"])[0]
                    prix, nb = to_float(r["prix_median"]), int(r["nb_annonces"])
                    if prix is None or prix <= 0 or nb < 1:
                        raise ValueError(f"valeurs invalides (prix {r['prix_median']}, annonces {r['nb_annonces']})")
                    ajoute = insert_fait(cx, ident, date.fromisoformat(r["date"]), "ebay_api", "prix_demande",
                                         r["etat"], round(prix, 2), nb=nb)
                    n += ajoute
                    doublons += 1 - ajoute
                except (ValueError, KeyError) as e:
                    erreurs.append(f"{fichier.name} ligne {i} : {e}")
    return n, doublons, erreurs, len(fichiers)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=str(DB))
    p.add_argument("--manual", default=str(MANUAL))
    p.add_argument("--occasion", default=str(OCCASION), help="dossier des relevés d'annonces agrégés (ebay-*.csv)")
    a = p.parse_args()

    db = Path(a.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    db.unlink(missing_ok=True)
    cx = sqlite3.connect(db)
    cx.executescript(SCHEMA.read_text(encoding="utf-8"))
    with cx:
        load_dimensions(cx)
        load_livres_versions(cx)
        n_hist, ignores, orphelins = load_historique(cx)
        n_man, doublons, erreurs = load_manuel(cx, a.manual)
        n_ebay, dbl_ebay, err_ebay, nb_fichiers = load_ebay(cx, a.occasion)
        doublons += dbl_ebay
        erreurs += err_ebay
    cx.execute("PRAGMA foreign_keys = ON")
    problemes = cx.execute("PRAGMA foreign_key_check").fetchall()

    def compte(t):
        return cx.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"Base écrite : {db}")
    print(f"  DimLivre {compte('DimLivre')} | DimSerie {compte('DimSerie')} | DimVersion {compte('DimVersion')} | DimEtat {compte('DimEtat')} | "
          f"DimSource {compte('DimSource')} | DimTypePrix {compte('DimTypePrix')} | DimDate {compte('DimDate')}")
    print(f"  FaitPrix {compte('FaitPrix')} (historique {n_hist}, saisies manuelles {n_man}, relevés eBay {n_ebay} dans {nb_fichiers} fichier(s); "
          f"{ignores} prix historiques vides ou à 0 ignorés, {doublons} doublon(s) de saisie ignoré(s), "
          f"{orphelins} prix sans édition connue écartés)")
    for e in erreurs:
        print(f"  ✗ {e}")
    print("  Contrôle des clés étrangères :", "OK" if not problemes else f"{len(problemes)} anomalie(s)")
    cx.close()
    return 1 if (problemes or erreurs) else 0


if __name__ == "__main__":
    sys.exit(main())
