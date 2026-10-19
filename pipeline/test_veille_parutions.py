"""Tests de la veille des parutions.   python pipeline/test_veille_parutions.py"""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
import veille_parutions as v

CARTE = '<article class="card-product"><div><h3 class="card-product__title"><a href="/livre/{id}-x" class="stretched-link">{titre}</a></h3><span class="card-product__author" itemprop="author">{auteur}</span></div></article>'
FICHE = '<span itemprop="isbn">{isbn}</span><time itemprop="datePublished" datetime="{date}"></time>'


class TestVeille(unittest.TestCase):
    def test_titres_decoupes(self):
        s = ["Défis Fantastiques", "Loup Solitaire", "Quête du Graal"]
        self.assertEqual(v.decouper_titre("Loup solitaire, 24, La Guerre des Runes", s), ("Loup Solitaire", "24", "La Guerre des Runes"))
        self.assertEqual(v.decouper_titre("Défis Fantastiques - Le Labyrinthe de l'île Sanglante", s), ("Défis Fantastiques", "", "Le Labyrinthe de l'île Sanglante"))
        self.assertEqual(v.decouper_titre("4, Défis Fantastiques, 4 : La Cité des Voleurs", s), ("Défis Fantastiques", "4", "La Cité des Voleurs"))
        self.assertEqual(v.decouper_titre("Loup solitaire, 31, Le crépuscule de la nuit éternelle, Édition collector", s)[2], "Le crépuscule de la nuit éternelle (Édition collector)")
        self.assertEqual(v.decouper_titre("Titre - avec tiret", s), ("", "", "Titre - avec tiret"))

    def test_lecture_des_cartes(self):
        h = CARTE.format(id=1, titre="Loup solitaire, 24, La Guerre des Runes", auteur="Joe Dever") + CARTE.format(id=2, titre="Autre", auteur="X")
        self.assertEqual([c["id"] for c in v.lire_cartes(h)], ["1", "2"])
        self.assertEqual(v.fiche(FICHE.format(isbn="978-2-07-523712-3", date="2026-05-28T00:00")), {"isbn": "9782075237123", "date": "2026-05-28"})

    def test_ajout_des_nouveautes_et_des_annonces(self):
        d = Path(tempfile.mkdtemp())
        base = d / "e.csv"
        editions.save([dict(zip(editions.COLUMNS, [""] * len(editions.COLUMNS)), id="9782075000001", isbn13="9782075000001", titre="Connu", livre="Connu", serie="Loup Solitaire", version="V5", annee="2020")], base)
        pages = {
            v.BASE + v.GJ[0]: CARTE.format(id=1, titre="Loup solitaire, 24, La Guerre des Runes", auteur="Joe Dever") + CARTE.format(id=3, titre="Un roman", auteur="Quelqu'un"),
            v.BASE + v.GJ[1]: "", v.BASE + v.GJ[2]: "", v.BASE + v.ALKONOST: "",
            v.BASE + "/livre/1-x": FICHE.format(isbn="9782075237123", date="2027-02-11"),
        }
        def get(url, params=None):
            return pages.get(url)
        bilan_importe = []
        def faux_importer(texte, b=None, **kw):
            bilan_importe.append(texte)
            rows = editions.load(b)
            rows.append(dict(zip(editions.COLUMNS, [""] * len(editions.COLUMNS)), id="9782075237123", isbn13="9782075237123", titre="La Guerre des Runes", livre="La Guerre des Runes", serie="Loup Solitaire", version="V1", editeur="Gallimard Jeunesse"))
            editions.save(rows, b)
            return [("ajoute", "9782075237123", "ok")]
        r = v.veiller(get, base=str(base), chemin=d / "veille.json", aujourdhui=date(2026, 10, 19), pause=0, importer=faux_importer)
        self.assertEqual(bilan_importe, ["9782075237123 ; Loup Solitaire ; 24 ; La Guerre des Runes"])
        self.assertEqual(r["a_paraitre"], {"9782075237123": "2027-02-11"})
        ligne = next(x for x in editions.load(str(base)) if x["id"] == "9782075237123")
        self.assertEqual((ligne["version"], ligne["annee"]), ("V5", "2027"))          # Gallimard Jeunesse depuis 2018 : version 5
        self.assertEqual(json.loads((d / "veille.json").read_text(encoding="utf-8"))["vus"], {"1": "9782075237123"})
        # deuxième passage : rien de nouveau, l'annonce reste suivie
        bilan_importe.clear()
        r2 = v.veiller(get, base=str(base), chemin=d / "veille.json", aujourdhui=date(2026, 10, 20), pause=0, importer=faux_importer)
        self.assertEqual((bilan_importe, r2["ajoutes"]), ([], []))
        # le jour de la parution, l'annonce disparaît
        r3 = v.veiller(get, base=str(base), chemin=d / "veille.json", aujourdhui=date(2027, 2, 11), pause=0, importer=faux_importer)
        self.assertEqual(r3["a_paraitre"], {})


if __name__ == "__main__":
    unittest.main()
