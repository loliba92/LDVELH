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

    def test_isbn_separes_par_des_points_virgules_et_caracteres_invisibles(self):
        l = imp.lire_liste("\u200e9782075237246 ; 9782075237192 ; 9782075243919\n\u200e")
        self.assertEqual([x["brut"] for x in l], ["9782075237246", "9782075237192", "9782075243919"])
        self.assertTrue(all(not x["serie"] and not x["titre"] for x in l))

    def test_titre_de_librairie_decoupe_en_serie_numero_titre(self):
        class R:
            status_code = 200
            text = "<title>Livre-jeu, Défis fantastiques, 18, L'Œil d'Émeraude - Ian Livingstone - Leslibraires.fr</title>"
            def raise_for_status(self): pass
        class H:
            def get(self, *a, **k): return R()
        f = imp.fiche_librairie("9782075237246", H())
        self.assertEqual((f["serie"], f["numero"], f["titre"]), ("Défis fantastiques", "18", "L'Œil d'Émeraude"))

    def test_la_librairie_comble_la_notice_de_la_bnf(self):
        b = self.base([("9791040809630", "Reine des dragons", "2026")])
        rows = editions.load(b)
        rows[0]["editeur"] = "Sarbacane"
        editions.save(rows, b)
        bnf = lambda i13, i10: {"titre": "Reine de l'Ouest", "editeur": "Roman Sarbacane", "collection_editeur": "X'", "annee": "", "pages": "669"}
        lib = lambda i: {"titre": "Reine de l'Ouest, Le western", "annee": "2024", "pages": "672", "editeur": "Sarbacane", "collection": "Exprim'"}
        imp.importer("9791040805618", b, bnf, lib)
        r = {x["id"]: x for x in editions.load(b)}["9791040805618"]
        self.assertEqual((r["annee"], r["pages"], r["editeur"], r["collection_editeur"], r["titre"]), ("2024", "669", "Sarbacane", "Exprim'", "Reine de l'Ouest"))

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

    def test_une_ligne_sans_isbn_est_un_titre(self):
        """Signalé le 17 octobre 2026 : « Cthulhu le pacte d'innsmouth; » était rejeté comme ISBN invalide."""
        l = imp.lire_liste("Cthulhu le pacte d'innsmouth;\nCthulhu, le pacte d'Innsmouth\n9791097577025, 2-07-033370-1")
        self.assertEqual([x["brut"] for x in l], ["Cthulhu le pacte d'innsmouth", "Cthulhu, le pacte d'Innsmouth", "9791097577025", "2-07-033370-1"])
        self.assertTrue(imp.ressemble_isbn("2-07-033370-1") and imp.ressemble_isbn("123") and not imp.ressemble_isbn("Cthulhu"))

    def test_ajout_par_le_titre(self):
        b = self.base()
        bilan = imp.importer("Cthulhu, le pacte d'Innsmouth ; L'Appel de Cthulhu ; 3\nCthulhu le pacte d'innsmouth;", b, SANS_BNF, LIBRAIRIE)
        self.assertEqual([s for s, _, _ in bilan], ["ajoute", "deja"])      # la 2e ligne est le même titre, sans série
        rows = editions.load(b)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["id"], r["titre"], r["serie"], r["numero"], r["statut"], r["isbn13"]), ("LOCAL-L'Appel_de_Cthulhu-3", "Cthulhu, le pacte d'Innsmouth", "L'Appel de Cthulhu", "3", "brut", ""))

    def test_titre_sans_serie_ni_numero(self):
        b = self.base()
        bilan = imp.importer("Cthulhu le pacte d'innsmouth;", b, SANS_BNF, LIBRAIRIE)
        self.assertEqual(bilan[0][0], "ajoute")
        r = editions.load(b)[0]
        self.assertEqual((r["id"], r["titre"], r["version"]), ("LOCAL-Cthulhu_le_pacte_d'innsmouth", "Cthulhu le pacte d'innsmouth", "V1"))
        self.assertEqual(imp.importer("Cthulhu le pacte d'innsmouth", b, SANS_BNF, LIBRAIRIE)[0][0], "deja")

    def test_un_isbn_complete_ensuite_la_fiche_ajoutee_par_titre(self):
        b = self.base()
        imp.importer("Le Livre des Règles ; L'Œil Noir ; 2", b, SANS_BNF, LIBRAIRIE)
        bilan = imp.importer("2-07-033370-1 ; L'Œil Noir ; 2", b, SANS_BNF, lambda i: None)
        self.assertEqual(bilan[0][0], "complete")
        rows = editions.load(b)
        self.assertEqual((len(rows), rows[0]["id"], rows[0]["titre"]), (1, "9782070333707", "Le Livre des Règles"))

    def test_nom_de_jaquette_sans_isbn(self):
        self.assertEqual(editions.cle_image("LOCAL-L'Œil_Noir-002"), "local-l-oeil-noir-002")
        self.assertEqual(editions.cle_image("LOCAL-x", "9782070333707"), "9782070333707")


if __name__ == "__main__":
    unittest.main(verbosity=2)
