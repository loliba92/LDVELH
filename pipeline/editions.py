"""Fonctions communes pour la base des éditions (data/processed/editions.csv)."""
import csv
import re
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "data" / "processed" / "editions.csv"

COLUMNS = ["id", "isbn13", "isbn10", "livre", "titre", "version", "en_vente", "serie", "numero",
           "auteurs", "traducteur",
           "illustrateur", "editeur", "collection_editeur", "annee", "annee_bnf", "pages", "notice_bnf",
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


# --- Lecture / écriture de la base -------------------------------------------

def load(path=None):
    path = Path(path or BASE)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(rows, path=None):
    path = Path(path or BASE)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r.get("serie", ""), r.get("numero", "").zfill(5), r["id"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


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


def lookup_bnf(isbn13, isbn10, pause=1.0):
    """Cherche l'édition dans le catalogue de la BnF. Renvoie un dict ou None."""
    time.sleep(pause)
    isbn = isbn10 or isbn13
    params = {"version": "1.2", "operation": "searchRetrieve", "recordSchema": "dublincore",
              "maximumRecords": "1", "query": f'bib.isbn all "{isbn}"'}
    r = requests.get(BNF_URL, params=params, timeout=30,
                     headers={"User-Agent": "LDVELH-catalogue/0.1 (projet de cote de livres-jeux)"})
    r.raise_for_status()
    root = ET.fromstring(r.content)
    rec = root.find(".//dc:title/..", NS)
    if rec is None:
        return None

    def texts(tag):
        return [e.text.strip() for e in rec.findall(f"dc:{tag}", NS) if e.text]

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
    collection = next((d[len("Collection : "):] for d in texts("description")
                       if d.startswith("Collection : ")), "")
    collection = re.sub(r"^Collection\s+", "", collection.split(" ; ")[0].strip())
    collection = collection[:1].upper() + collection[1:]
    fmt = " ".join(texts("format"))
    pages = (re.search(r"(\d+)\s*p\.", fmt) or [None, ""])[1]
    ark = next((i for i in texts("identifier") if i.startswith("http")), "")
    editeur = re.sub(r"\s*\(.*?\)", "", (texts("publisher") or [""])[0]).strip()
    return {"titre": titre, "auteurs": " ; ".join(auteurs), "traducteur": traducteur,
            "illustrateur": illustrateur, "editeur": editeur,
            "collection_editeur": collection, "annee": (texts("date") or [""])[0][:4],
            "pages": pages, "notice_bnf": ark}


def today():
    return date.today().isoformat()
