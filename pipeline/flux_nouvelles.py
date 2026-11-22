"""Flux RSS des nouvelles du site (web/nouvelles.xml), à relier à une page Facebook (Make).

Usage : python pipeline/flux_nouvelles.py
Une nouvelle est une entrée de web/data/communaute.json qui porte un champ « date » (AAAA-MM-JJ) : titre, texte, lien et image de la carte.
Le flux est reconstruit en entier, les plus récentes en premier (20 au plus).
Le 1er de chaque mois, une carte « Guide de référence : édition du mois » s'ajoute à la liste Communauté, donc au flux (workflow guide-mensuel.yml).
"""
import json
import mimetypes
from datetime import date, datetime
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr
from zoneinfo import ZoneInfo

RACINE = Path(__file__).resolve().parent.parent
LISTE = RACINE / "web" / "data" / "communaute.json"
SORTIE = RACINE / "web" / "nouvelles.xml"
BASE = "https://lacoteduheros.fr/"
MAX_NOUVELLES = 20
PARIS = ZoneInfo("Europe/Paris")


MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
PREMIERE_EDITION = (2026, 12)


def editions_mensuelles(jour):
    """Une entrée par premier du mois, de PREMIERE_EDITION jusqu'au mois de `jour` (un objet date)."""
    sortie, (a, m) = [], PREMIERE_EDITION
    while (a, m) <= (jour.year, jour.month):
        sortie.append({
            "nom": f"Guide de référence : édition de {MOIS[m - 1]} {a}",
            "adresse": f"{BASE}sorcier.html#guide-{a}-{m:02d}",
            "description": f"Le guide PDF de {MOIS[m - 1]} {a} est prêt : les repères, les quatre zones et la stratégie du collectionneur, pour les Sorciers et les Héros en essai.",
            "image": "data/communaute/sorcier.jpg",
            "date": f"{a}-{m:02d}-01",
        })
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return sortie


def ajouter_editions(liste, jour):
    """Ajoute en tête de la liste les éditions mensuelles qui n'y sont pas encore ; renvoie la liste."""
    connues = {x.get("adresse") for x in liste}
    neuves = [x for x in editions_mensuelles(jour) if x["adresse"] not in connues]
    return sorted(neuves, key=lambda x: x["date"], reverse=True) + list(liste)


def nouvelles(liste):
    """Les entrées datées, la plus récente d'abord."""
    datees = [x for x in liste if x.get("date")]
    return sorted(datees, key=lambda x: (x["date"], x["nom"].casefold()), reverse=True)[:MAX_NOUVELLES]


def date_rss(jour):
    return format_datetime(datetime.strptime(jour, "%Y-%m-%d").replace(hour=8, tzinfo=PARIS))


def image_absolue(chemin):
    return chemin if chemin.startswith("https://") else BASE + chemin


def element(x, racine=RACINE):
    lien = x["adresse"]
    xml = [
        "    <item>",
        f"      <title>{escape(x['nom'])}</title>",
        f"      <link>{escape(lien)}</link>",
        f'      <guid isPermaLink="true">{escape(lien)}</guid>',
        f"      <pubDate>{date_rss(x['date'])}</pubDate>",
        f"      <description>{escape(x.get('description', ''))}</description>",
    ]
    chemin = x.get("image", "")
    if chemin:
        fichier = racine / "web" / chemin
        taille = fichier.stat().st_size if fichier.is_file() else 0
        type_ = mimetypes.guess_type(chemin)[0] or "image/jpeg"
        url = image_absolue(chemin)
        xml.append(f"      <enclosure url={quoteattr(url)} length=\"{taille}\" type={quoteattr(type_)}/>")
        xml.append(f"      <media:content url={quoteattr(url)} medium=\"image\" type={quoteattr(type_)}/>")
    xml.append("    </item>")
    return "\n".join(xml)


def construire(liste, racine=RACINE):
    elements = nouvelles(liste)
    derniere = date_rss(elements[0]["date"]) if elements else date_rss("2026-01-01")
    return "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">',
        "  <channel>",
        "    <title>La Cote du Héros · Nouvelles</title>",
        f"    <link>{BASE}communaute.html</link>",
        '    <description>Les nouvelles de La Cote du Héros, le guide de cote des livres dont vous êtes le héros.</description>',
        "    <language>fr-FR</language>",
        f"    <lastBuildDate>{derniere}</lastBuildDate>",
        f'    <atom:link href="{BASE}nouvelles.xml" rel="self" type="application/rss+xml"/>',
        *[element(x, racine) for x in elements],
        "  </channel>",
        "</rss>",
        "",
    ])


def main():
    liste = json.loads(LISTE.read_text(encoding="utf-8"))
    complete = ajouter_editions(liste, date.today())
    if complete != liste:
        LISTE.write_text(json.dumps(complete, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SORTIE.write_text(construire(complete), encoding="utf-8")
    print(f"{len(nouvelles(complete))} nouvelle(s) dans le flux")


if __name__ == "__main__":
    main()
