"""Veille des parutions : repère les nouveaux livres de Gallimard Jeunesse (Défis fantastiques, Loup solitaire, Quête du Graal, Neige d'Automne)
et d'Alkonost, et les ajoute à la base.   python pipeline/veille_parutions.py   (lancé chaque jour par .github/workflows/veille-parutions.yml)

Source : les pages de collection de leslibraires.fr, qui listent les livres d'un éditeur (la recherche du site, elle, est interdite aux robots)
et chaque fiche /livre/<identifiant>, pour l'ISBN, la date de parution et la disponibilité. Une pause sépare deux requêtes.
Pour Gallimard Jeunesse, un livre n'est ajouté que si son titre porte le nom d'une des séries ; un livre d'un auteur connu mais sans nom de série
est seulement signalé. Pour Alkonost, tous les livres de ses collections de livres-jeux sont ajoutés.
Les livres annoncés (parution à venir) sont ajoutés aussi, avec leur date : data/processed/veille.json garde les fiches déjà vues et les dates de
parution à venir (l'accueil les présente dans « À paraître »).
"""
import html
import json
import re
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
import importer_isbn

BASE = "https://www.leslibraires.fr"
CHEMIN = editions.ROOT / "data" / "processed" / "veille.json"
AGENT = {"User-Agent": "LDVELH-catalogue/0.1 (projet de cote de livres-jeux)"}
GJ = ["/editeur/gallimard-jeunesse/collection/grand-format-li/",
      "/editeur/gallimard-jeunesse/collection/grand-format-litterature-un-livre-dont-vous-etes-le-heros/",
      "/editeur/gallimard-jeunesse/collection/livres-heros-gr/"]
ALKONOST = "/editeur/alkonost/"
SERIES_GJ = re.compile(r"d[ée]fis fantastiques|loup solitaire|qu[êe]te du graal|neige d.automne", re.I)
PAGES_MAX = 60


def cle(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower().replace("œ", "oe").replace("’", "'"))
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip()


def lire_cartes(h):
    """[{id, href, titre, auteur, stock}] d'une page de collection."""
    out = []
    for c in re.findall(r'<article class="card-product">(.*?)</article>', h, flags=re.S):
        m = re.search(r'href="(/livre/(\d+)-[^"]+)"[^>]*>([^<]+)</a>', c)
        if not m:
            continue
        a = re.search(r'itemprop="author">([^<]*)<', c)
        st = re.search(r'class="product-stock[^"]*"></span>\s*([^<]+)<', c)
        out.append({"id": m.group(2), "href": m.group(1), "titre": html.unescape(m.group(3)).strip(),
                    "auteur": html.unescape(a.group(1)).strip() if a else "", "stock": st.group(1).strip() if st else ""})
    return out


def collections_alkonost(h):
    """Adresses des collections de la page de l'éditeur."""
    return sorted({"/" + m.lstrip("/").split("leslibraires.fr/")[-1] for m in re.findall(r'href="((?://www\.leslibraires\.fr)?/editeur/alkonost/collection/[^"]+)"', h)})


def decouper_titre(t, series):
    """(série, numéro, titre) d'un titre de librairie : « Loup solitaire, 24, La Guerre des Runes », « Défis Fantastiques - Le Labyrinthe… »,
    « 4, Défis Fantastiques, 4 : La Cité des Voleurs ». La série est rendue avec l'écriture de la base."""
    t = re.sub(r"^\d+,\s*", "", t.strip())
    serie = numero = ""
    m = re.fullmatch(r"(.+?),\s*(\d{1,3})\s*(?:,|:)\s*(.+)", t)
    if m:
        serie, numero, t = m.group(1).strip(), m.group(2), m.group(3).strip()
    else:
        m = re.fullmatch(r"(.+?)\s+-\s+(.+)", t)
        if m and cle(m.group(1)) in {cle(s) for s in series}:
            serie, t = m.group(1).strip(), m.group(2).strip()
    t = re.sub(r",\s*((?:[ÉéEe]dition|Version) .+)$", r" (\1)", t)
    connue = next((s for s in series if cle(s) == cle(serie)), serie)
    return connue, numero, t


def fiche(h):
    """{isbn, date} d'une fiche de livre ('' si absent)."""
    m = re.search(r'itemprop="isbn"[^>]*>([^<]+)<', h) or re.search(r"(97[89][\d-]{10,14}\d)", h)
    isbn = re.sub(r"\D", "", m.group(1)) if m else ""
    d = re.search(r'itemprop="datePublished" datetime="([^"]+)"', h)
    return {"isbn": isbn if len(isbn) == 13 else "", "date": d.group(1)[:10] if d else ""}


def charger(chemin=CHEMIN):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"vus": {}, "a_paraitre": {}}


def sauver(etat, chemin=CHEMIN):
    Path(chemin).write_text(json.dumps(etat, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def parcourir(url, get, pause):
    """Cartes de toutes les pages d'une collection."""
    out, page = [], 1
    while page <= PAGES_MAX:
        h = get(BASE + url, {"page": page} if page > 1 else None)
        if h is None:
            break
        cartes = lire_cartes(h)
        if not cartes:
            break
        out += cartes
        if f'href="?page={page + 1}"' not in h:
            break
        page += 1
        time.sleep(pause)
    return out


def http_get(url, params=None):
    r = requests.get(url, params=params, headers=AGENT, timeout=60)
    return r.text if r.status_code == 200 else None


def veiller(get=http_get, base=None, chemin=CHEMIN, aujourdhui=None, pause=1.2, importer=importer_isbn.importer):
    """Ajoute à la base les livres nouveaux. Renvoie {ajoutes: [...], signales: [...], a_paraitre: {...}}."""
    aujourdhui = (aujourdhui or date.today()).isoformat()
    etat = charger(chemin)
    rows = editions.load(base)
    connus = {r["isbn13"] for r in rows if r.get("isbn13")}
    series = sorted({r["serie"] for r in rows if r.get("serie")})
    cartes = []
    for url in GJ:
        for c in parcourir(url, get, pause):
            c["editeur"] = "gj"
            cartes.append(c)
        time.sleep(pause)
    page_alk = get(BASE + ALKONOST, None) or ""
    for url in collections_alkonost(page_alk):
        for c in parcourir(url, get, pause):
            c["editeur"] = "alkonost"
            cartes.append(c)
        time.sleep(pause)
    uniques = {c["id"]: c for c in cartes}
    signales, lignes, infos = [], [], {}
    for c in uniques.values():
        if c["editeur"] == "gj" and not SERIES_GJ.search(c["titre"]):
            # Titre sans nom de série : seulement les auteurs de la collection. Déjà dans la base (une réédition annoncée, par exemple) : on suit sa
            # date de parution ; sinon on le signale, sans l'ajouter.
            if not re.search("|".join(map(re.escape, ["Livingstone", "Jackson", "Dever", "Higgins", "Brennan"])), c["auteur"]):
                continue
            if c["id"] in etat["vus"] and etat["vus"][c["id"]] not in etat["a_paraitre"]:
                continue
            h = get(BASE + c["href"], None)
            time.sleep(pause)
            f = fiche(h or "")
            if f["isbn"] and f["isbn"] in connus:
                etat["vus"][c["id"]] = f["isbn"]
                if f["date"] > aujourdhui:
                    etat["a_paraitre"][f["isbn"]] = f["date"]
                else:
                    etat["a_paraitre"].pop(f["isbn"], None)
            elif c["id"] not in etat.setdefault("signales", []):
                signales.append(f"{c['titre']} ({c['auteur']}) : auteur connu, série non reconnue ({BASE}{c['href']})")
                etat["signales"].append(c["id"])
            continue
        if c["id"] in etat["vus"] and etat["vus"][c["id"]] in connus and etat["vus"][c["id"]] not in etat["a_paraitre"]:
            continue
        h = get(BASE + c["href"], None)
        time.sleep(pause)
        f = fiche(h or "")
        if not f["isbn"]:
            continue
        etat["vus"][c["id"]] = f["isbn"]
        if f["date"] > aujourdhui:
            etat["a_paraitre"][f["isbn"]] = f["date"]
        else:
            etat["a_paraitre"].pop(f["isbn"], None)
        if f["isbn"] in connus:
            continue
        serie, numero, titre = decouper_titre(c["titre"], series)
        infos[f["isbn"]] = {"carte": c, "fiche": f, "serie": serie, "numero": numero, "titre": titre}
        lignes.append(f"{f['isbn']} ; {serie} ; {numero} ; {titre}")
    ajoutes = []
    if lignes:
        bilan = importer("\n".join(lignes), base)
        rows = editions.load(base)
        par_id = {r["id"]: r for r in rows}
        for statut, isbn, texte in bilan:
            if statut != "ajoute" or isbn not in par_id:
                continue
            r, i = par_id[isbn], infos[isbn]
            if r["editeur"] == "Gallimard Jeunesse" and str(i["fiche"]["date"])[:4].isdigit() and int(i["fiche"]["date"][:4]) >= 2018:
                r["version"] = "V5"                                     # les rééditions de Gallimard Jeunesse depuis 2018 sont la version 5
            if i["fiche"]["date"] and not r["annee"]:
                r["annee"] = i["fiche"]["date"][:4]
            sib = next((x for x in rows if x["id"] != isbn and x["serie"] == r["serie"] and cle(x["titre"]) == cle(r["titre"]) and x.get("numero")), None)
            if sib:
                r["numero"], r["livre"] = sib["numero"], sib["livre"]
            ajoutes.append(f"{r['titre']} ({r['serie']}, {r['version']}, {r['annee']}) : {isbn}")
        editions.save(rows, base)
    sauver(etat, chemin)
    return {"ajoutes": ajoutes, "signales": signales, "a_paraitre": dict(etat["a_paraitre"])}


def main():
    r = veiller()
    print(f"{len(r['ajoutes'])} livre(s) ajouté(s) :")
    for a in r["ajoutes"]:
        print("  +", a)
    for s in r["signales"]:
        print("  ?", s)
    print(f"{len(r['a_paraitre'])} livre(s) à paraître.")


if __name__ == "__main__":
    main()
