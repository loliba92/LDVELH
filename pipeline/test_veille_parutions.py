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


def ligne(**k):
    return dict(zip(editions.COLUMNS, [""] * len(editions.COLUMNS)), **k)


class TestScriptarium(unittest.TestCase):
    def test_classement_des_notices(self):
        rows = [ligne(id="1", serie="Défis et Sortilèges", titre="La Huitième Porte", editeur="Gallimard")]
        n = lambda **k: dict({"isbn": "9782490523351", "titre": "X", "collection": "", "numero": "", "annee": "2026"}, **k)
        self.assertEqual(v.classer_scriptarium(n(titre="Les Murmures", collection="Oeil Noir", numero="3"), rows), ("L'Œil noir (solos)", "3", "Les Murmures"))
        self.assertEqual(v.classer_scriptarium(n(titre="La huitième porte"), rows), ("Défis et Sortilèges", "", "La huitième porte"))   # sans collection : série du même titre
        self.assertIsNone(v.classer_scriptarium(n(collection="Oeil Noir bande dessinnée", numero="1"), rows))                           # bande dessinée
        self.assertIsNone(v.classer_scriptarium(n(titre="Le bal au pont"), rows))                                                        # roman : signalé seulement

    def test_ajout_et_versions(self):
        d = Path(tempfile.mkdtemp())
        base = d / "e.csv"
        editions.save([ligne(id="G1", isbn13="9782070567386", serie="Défis et Sortilèges", numero="672", titre="La Huitième Porte", livre="La Huitième Porte", version="V1", annee="1992", editeur="Gallimard")], base)
        notices = [{"isbn": "9782490523313", "titre": "La huitième porte", "collection": "Défis et Sortilèges édition deluxe", "numero": "3", "annee": "2025"},
                   {"isbn": "9782490523184", "titre": "La huitième porte", "collection": "", "numero": "", "annee": "2024"},
                   {"isbn": "9782954363141", "titre": "Le bal au pont", "collection": "", "numero": "", "annee": "2015"}]

        def faux_importer(texte, b=None, **kw):
            rows = editions.load(b)
            for l in texte.split("\n"):
                isbn, serie, numero, titre = [x.strip() for x in l.split(";")]
                rows.append(ligne(id=isbn, isbn13=isbn, serie=serie, numero=numero, titre=titre, livre=titre, version="V2", annee="2025" if isbn.endswith("3") else "2024", editeur="<junk>"))
            editions.save(rows, b)
            return [("ajoute", l.split(";")[0].strip(), "ok") for l in texte.split("\n")]
        r = v.veiller(lambda u, p=None: None, base=str(base), chemin=d / "veille.json", aujourdhui=date(2026, 10, 23), pause=0, importer=faux_importer, scriptarium=lambda: notices)
        rows = {x["id"]: x for x in editions.load(str(base))}
        self.assertEqual((len(r["ajoutes"]), len(r["signales"])), (2, 1))
        self.assertEqual([(rows[i]["version"], rows[i]["numero"], rows[i]["titre"], rows[i]["editeur"]) for i in ("9782490523184", "9782490523313")],
                         [("V2", "672", "La Huitième Porte", "Scriptarium"), ("V3", "672", "La Huitième Porte", "Scriptarium")])
        r2 = v.veiller(lambda u, p=None: None, base=str(base), chemin=d / "veille.json", aujourdhui=date(2026, 10, 24), pause=0, importer=faux_importer, scriptarium=lambda: notices)
        self.assertEqual((r2["ajoutes"], r2["signales"]), ([], []))                    # rien de nouveau, le roman n'est signalé qu'une fois


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
