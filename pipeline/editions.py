"""Fonctions communes pour la base des éditions (data/processed/editions.csv)."""
import csv
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "processed" / "editions.csv"

COLUMNS = ["id", "isbn13", "isbn10", "livre", "titre", "version", "en_vente", "serie", "numero",
           "auteurs", "traducteur",
           "illustrateur", "editeur", "collection_editeur", "annee", "annee_bnf", "pages", "notice_bnf", "couverture",
           "statut", "source", "date_maj"]

BNF_URL = "https://catalogue.bnf.fr/api/SRU"
NS = {"srw": "http://www.loc.gov/zing/srw/", "dc": "http://purl.org/dc/elements/1.1/"}


# --- ISBN -------------------------------------------------------------------

def _digits(isbn):
    return re.sub(r"[^0-9Xx]", "", str(isbn)).upper()


def isbn10_to_13(isbn10):
    core = "978" + isbn10[:9]
    check = (10 - sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core)) % 10) % 10
    return core + str(check)


def isbn13_to_10(isbn13):
    if not isbn13.startswith("978"):
        return ""
    core = isbn13[3:12]
    total = sum(int(c) * (10 - i) for i, c in enumerate(core))
    check = (11 - total % 11) % 11
    return core + ("X" if check == 10 else str(check))


def normalize_isbn(raw):
    """Renvoie (isbn13, isbn10) ou lève ValueError si l'ISBN est invalide."""
    d = _digits(raw)
    if len(d) == 10:
        total = sum((10 if c == "X" else int(c)) * (10 - i) for i, c in enumerate(d))
        if total % 11 != 0:
            raise ValueError(f"ISBN-10 invalide (clé de contrôle) : {raw}")
        return isbn10_to_13(d), d
    if len(d) == 13 and d.isdigit():
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(d))
        if total % 10 != 0:
            raise ValueError(f"ISBN-13 invalide (clé de contrôle) : {raw}")
        return d, isbn13_to_10(d)
    raise ValueError(f"ISBN de longueur inattendue : {raw}")


# --- Éditeurs : une seule graphie par maison ----------------------------------

# Graphie retenue, par clé normalisée (sans accent, sans majuscule, tirets et points = espaces).
EDITEURS = {"gallimard jeunesse": "Gallimard Jeunesse", "gallimard": "Gallimard"}


def normaliser_editeur(nom):
    """« Gallimard jeunesse », « gallimard-jeunesse » et « Gallimard Jeunesse » donnent tous « Gallimard Jeunesse »."""
    propre = re.sub(r"\s+", " ", (nom or "").strip())
    if not propre:
        return ""
    cle = unicodedata.normalize("NFKD", propre).encode("ascii", "ignore").decode().lower()
    cle = re.sub(r"[\s\-_.]+", " ", cle).strip()
    return EDITEURS.get(cle, propre)


# --- Lecture / écriture de la base -------------------------------------------

def load(path=None):
    path = Path(path or BASE)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["editeur"] = normaliser_editeur(r.get("editeur"))
    return rows


def save(rows, path=None):
    path = Path(path or BASE)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r.get("serie", ""), r.get("numero", "").zfill(5), r["id"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: (normaliser_editeur(r.get(c)) if c == "editeur" else r.get(c, "")) for c in COLUMNS})


# --- Interrogation de la BnF -------------------------------------------------

def _name(raw):
    """« Morris, Dave (1940-....). Auteur du texte » -> (« Dave Morris », « Auteur du texte »)."""
    role = ""
    m = re.match(r"^(.*?)\.\s+([A-ZÉ][^.]*)$", raw)
    if m:
        raw, role = m.group(1), m.group(2)
    raw = re.sub(r"\s*\(.*?\)", "", raw).strip()
    if "," in raw:
        nom, prenom = [p.strip() for p in raw.split(",", 1)]
        raw = f"{prenom} {nom}".strip()
    return raw, role


def _fiche_depuis_notice(rec):
    """Transforme une notice Dublin Core de la BnF en fiche (dict)."""
    def texts(tag):
        return [e.text.strip() for e in rec.findall(f".//dc:{tag}", NS) if e.text]

    titre = (texts("title") or [""])[0].split(" / ")[0].strip()
    auteurs, traducteur, illustrateur = [], "", ""
    for raw in texts("creator") + texts("contributor"):
        nom, role = _name(raw)
        if "Traducteur" in role:
            traducteur = nom
        elif "Illustrateur" in role:
            illustrateur = nom
        elif role.startswith("Auteur") or role == "":
            auteurs.append(nom)
    collection_brute = next((d[len("Collection : "):] for d in texts("description")
                             if d.startswith("Collection : ")), "")
    collection = re.sub(r"^Collection\s+", "", collection_brute.split(" ; ")[0].split(". ")[0].strip())
    collection = collection[:1].upper() + collection[1:]
    numero_col = (re.search(r";\s*(\d+)", collection_brute) or [None, ""])[1]
    fmt = " ".join(texts("format"))
    pages = (re.search(r"(\d+)\s*p\.", fmt) or [None, ""])[1]
    ark = next((i for i in texts("identifier") if i.startswith("http")), "")
    isbn = next((i[5:] for i in texts("identifier") if i.startswith("ISBN ")), "")
    isbns = []
    for i in texts("identifier"):
        if i.startswith("ISBN "):
            try:
                isbns.append(normalize_isbn(i[5:])[0])
            except ValueError:
                pass
    for d in texts("description"):  # « Code à barres commercial : EAN 9782070583805 »
        m = re.search(r"EAN\s*(\d{13})", d)
        if m and m.group(1) not in isbns:
            isbns.append(m.group(1))
    editeur = normaliser_editeur(re.sub(r"\s*\(.*?\)", "", (texts("publisher") or [""])[0]).strip())
    return {"titre": titre, "auteurs": " ; ".join(auteurs), "traducteur": traducteur,
            "illustrateur": illustrateur, "editeur": editeur,
            "collection_editeur": collection, "annee": (texts("date") or [""])[0][:4],
            "pages": pages, "notice_bnf": ark, "isbn": isbn, "isbns": isbns, "numero_collection": numero_col,
            "livre_jeu": "dont vous êtes le héros" in collection_brute.lower()}


def _sru(query, maximum, pause):
    time.sleep(pause)
    params = {"version": "1.2", "operation": "searchRetrieve", "recordSchema": "dublincore",
              "maximumRecords": str(maximum), "query": query}
    r = requests.get(BNF_URL, params=params, timeout=30,
                     headers={"User-Agent": "LDVELH-catalogue/0.1 (projet de cote de livres-jeux)"})
    r.raise_for_status()
    return ET.fromstring(r.content).findall(".//srw:record", NS)


def lookup_bnf(isbn13, isbn10, pause=1.0):
    """Cherche l'édition dans le catalogue de la BnF par ISBN. Renvoie un dict ou None."""
    # Les notices anciennes sont indexées par l'ISBN-10, les récentes par l'ISBN-13 : on essaie les deux.
    for isbn in (isbn10, isbn13):
        if not isbn:
            continue
        recs = _sru(f'bib.isbn all "{isbn}"', 1, pause)
        if recs:
            return _fiche_depuis_notice(recs[0])
    return None


def lookup_bnf_titre(titre, numero="", isbn13="", annee="", pause=1.0):
    """Recherche de secours par titre. Renvoie (fiche, confirmation) ou (None, '').

    confirmation : « isbn » (même ISBN), « numero » (même numéro de collection) ou
    « titre » (titre identique et collection « Un livre dont vous êtes le héros »,
    à faire confirmer à la main).
    """
    import difflib
    def n(t):
        t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
        t = re.sub(r"\b(le|la|les|l|un|une|de|du|des|d|et|a)\b", " ", t)
        return re.sub(r"[^a-z0-9]+", " ", t).strip()
    # Les lettres isolées issues des élisions (L', D') ne sont pas indexées : on les retire.
    mots = " ".join(m for m in re.sub(r"[\"'’]", " ", titre).split() if len(m) > 1)
    meilleur = (None, "", 0.0)
    for rec in _sru(f'bib.title all "{mots}"', 15, pause):
        f = _fiche_depuis_notice(rec)
        ratio = difflib.SequenceMatcher(None, n(titre), n(f["titre"])).ratio()
        if ratio < 0.9:
            continue
        # Une autre édition du même titre (V1 de 1986 vs V5 de 2022) n'est pas la bonne notice
        if annee.isdigit() and f["annee"].isdigit() and abs(int(annee) - int(f["annee"])) > 2:
            continue
        # Les chiffres doivent être identiques : « Livre des règles » ≠ « Livre des règles 2 »
        if re.findall(r"\d+", n(titre)) != re.findall(r"\d+", n(f["titre"])):
            continue
        if isbn13 and f["isbn"]:
            try:
                if normalize_isbn(f["isbn"])[0] == isbn13:
                    return f, "isbn"
            except ValueError:
                pass
        if numero and f["numero_collection"] and f["numero_collection"] == numero.lstrip("0"):
            conf = "numero"
        elif f["livre_jeu"] and f["editeur"].lower().startswith("gallimard"):
            conf = "titre"
        else:
            continue
        if ratio > meilleur[2]:
            meilleur = (f, conf, ratio)
    return (meilleur[0], meilleur[1]) if meilleur[0] else (None, "")


def today():
    return date.today().isoformat()
