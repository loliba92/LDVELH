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


if __name__ == "__main__":
    unittest.main(verbosity=2)
