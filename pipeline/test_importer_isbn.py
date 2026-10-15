"""Tests de l'import d'ISBN en lot.   python pipeline/test_importer_isbn.py"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
import importer_isbn as imp

SANS_BNF = lambda isbn13, isbn10: None
LIBRAIRIE = lambda isbn13: {"titre": "Le Royaume déchiré", "annee": "2018", "pages": "188", "editeur": "Alkonost", "collection": "Livre-Jeu"}


class TestImport(unittest.TestCase):
    def base(self, lignes=()):
        d = tempfile.mkdtemp()
        p = Path(d) / "editions.csv"
        editions.save([dict(zip(editions.COLUMNS, [""] * len(editions.COLUMNS)), id=i, isbn13=i, livre=t, titre=t, annee=a) for i, t, a in lignes], p)
        return str(p)

    def test_lecture_de_la_liste(self):
        t = "# commentaire\n9791097577025 ; Fabled Lands ; 1 ; Le Royaume déchiré\n\n2-07-033370-1, 978-2-07-058380-5  9782070583812\n"
        l = imp.lire_liste(t)
        self.assertEqual([x["brut"] for x in l], ["9791097577025", "2-07-033370-1", "978-2-07-058380-5", "9782070583812"])
        self.assertEqual((l[0]["serie"], l[0]["numero"], l[0]["titre"]), ("Fabled Lands", "1", "Le Royaume déchiré"))

    def test_ajout_deja_et_invalide(self):
        b = self.base([("9791097577025", "Le Royaume déchiré", "2018")])
        bilan = imp.importer("9791097577025\n9791097577049 ; Fabled Lands ; 1\n123\n", b, SANS_BNF, LIBRAIRIE)
        self.assertEqual([s for s, _, _ in bilan], ["deja", "ajoute", "invalide"])
        rows = {r["id"]: r for r in editions.load(b)}
        nouveau = rows["9791097577049"]
        self.assertEqual((nouveau["serie"], nouveau["numero"], nouveau["editeur"], nouveau["pages"], nouveau["source"]), ("Fabled Lands", "1", "Alkonost", "188", "leslibraires"))

    def test_version_suivant_les_editions_connues(self):
        b = self.base([("9791097577025", "Le Royaume déchiré", "2018"), ("9791097577117", "Le Royaume déchiré", "2020")])
        imp.importer("9791097577308", b, SANS_BNF, lambda i: {"titre": "Le Royaume déchiré", "annee": "2022"})
        self.assertEqual({r["id"]: r["version"] for r in editions.load(b)}["9791097577308"], "V3")

    def test_livre_introuvable_ajoute_en_brut(self):
        b = self.base()
        bilan = imp.importer("9791097577025 ; Fabled Lands ; 1 ; Titre à moi", b, SANS_BNF, lambda i: None)
        self.assertEqual(bilan[0][0], "ajoute")
        r = editions.load(b)[0]
        self.assertEqual((r["statut"], r["titre"], r["version"]), ("brut", "Titre à moi", "V1"))

    def test_deux_fois_le_meme_isbn_dans_la_liste(self):
        b = self.base()
        bilan = imp.importer("9791097577025\n979-10-97577-02-5", b, SANS_BNF, LIBRAIRIE)
        self.assertEqual([s for s, _, _ in bilan], ["ajoute", "deja"])

    def test_un_isbn_complete_la_fiche_sans_isbn(self):
        b = self.base([("LOCAL-Oeil-002", "Le Livre des Règles", "")])
        rows = editions.load(b)
        rows[0].update({"serie": "L'Œil Noir", "numero": "002", "version": "V1"})
        editions.save(rows, b)
        bilan = imp.importer("2-07-033370-1 ; L'Œil Noir ; 2", b, SANS_BNF, lambda i: None)
        self.assertEqual(bilan[0][0], "complete")
        r = editions.load(b)
        self.assertEqual((len(r), r[0]["id"], r[0]["isbn13"], r[0]["titre"], r[0]["version"]), (1, "9782070333707", "9782070333707", "Le Livre des Règles", "V1"))

    def test_nom_de_jaquette_sans_isbn(self):
        self.assertEqual(editions.cle_image("LOCAL-L'Œil_Noir-002"), "local-l-oeil-noir-002")
        self.assertEqual(editions.cle_image("LOCAL-x", "9782070333707"), "9782070333707")


if __name__ == "__main__":
    unittest.main(verbosity=2)
