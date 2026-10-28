"""Tests de la construction de la base : un relevé qui vise une édition supprimée ne doit pas faire échouer la construction.
    python -m unittest pipeline.test_build_db"""
import sqlite3
import subprocess
from unittest import mock
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_db

ENTETE = "isbn13,date,etat,nb_annonces,prix_min,prix_median,prix_max,nb_toutes,prix_median_toutes\n"
ISBN_SUPPRIME = "9782070666614"      # valide, mais absente de la base de test


class TestFraisDeLibrairie(unittest.TestCase):
    def test_le_prix_de_la_librairie_inclut_les_frais_de_port(self):
        d = Path(tempfile.mkdtemp())
        (d / "libraires-2026-10-27.csv").write_text(ENTETE + "9782070574940,2026-10-27,convenable,1,4.98,4.98,4.98,1,4.98\n", encoding="utf-8")
        with mock.patch.object(build_db, "insert_fait", return_value=1) as ins, mock.patch.object(build_db.editions, "normalize_isbn", return_value=("9782070574940",)):
            build_db.load_ebay(mock.Mock(), d, "libraires-*.csv", "libraires", ajout=build_db.FRAIS_LIBRAIRIE)
        self.assertEqual(ins.call_args[0][6], 9.48)


class TestReleveEditionSupprimee(unittest.TestCase):
    def base(self):
        cx = sqlite3.connect(":memory:")
        cx.executescript(build_db.SCHEMA.read_text(encoding="utf-8"))
        build_db.load_dimensions(cx)
        return cx

    def dossier(self, lignes):
        d = Path(tempfile.mkdtemp())
        (d / "ebay-2026-10-22.csv").write_text(ENTETE + "".join(f"{l}\n" for l in lignes), encoding="utf-8")
        return d

    def test_une_edition_supprimee_est_ecartee_sans_erreur(self):
        d = self.dossier([f"{ISBN_SUPPRIME},2026-10-22,bon,1,5.00,5.00,5.00,1,5.00", f"{ISBN_SUPPRIME},2026-10-22,tres_bon,1,8.00,8.00,8.00,1,8.00"])
        n, doublons, erreurs, nb_fichiers, ecartees = build_db.load_ebay(self.base(), d)
        self.assertEqual((n, erreurs), (0, []))                          # rien d'enregistré, aucune erreur
        self.assertEqual(ecartees, {"ebay-2026-10-22.csv": {ISBN_SUPPRIME: 2}})

    def test_une_vraie_erreur_reste_une_erreur(self):
        d = self.dossier([f"{ISBN_SUPPRIME},2026-10-22,bon,1,abc,abc,abc,1,abc", f"{ISBN_SUPPRIME},2026-10-22,bon,0,5.00,5.00,5.00,0,5.00"])
        _, _, erreurs, _, ecartees = build_db.load_ebay(self.base(), d)
        self.assertEqual(len(erreurs), 2)                                # prix illisible ; nombre d'annonces invalide
        self.assertEqual(ecartees, {})

    def test_la_construction_complete_reussit_avec_un_releve_sur_une_edition_supprimee(self):
        # lancement réel du script (comme le fait la publication automatique), sur les relevés du dépôt plus une ligne visant une édition absente
        d = Path(tempfile.mkdtemp())
        for f in Path(build_db.OCCASION).glob("*.csv"):
            (d / f.name).write_bytes(f.read_bytes())
        (d / "ebay-2026-10-30.csv").write_text(ENTETE + f"{ISBN_SUPPRIME},2026-10-30,bon,1,5.00,5.00,5.00,1,5.00\n", encoding="utf-8")
        db = Path(tempfile.mkdtemp()) / "t.sqlite"
        r = subprocess.run([sys.executable, str(Path(build_db.__file__)), "--db", str(db), "--occasion", str(d)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-600:])
        self.assertIn("1 ligne(s) écartée(s)", r.stdout)
        self.assertIn(ISBN_SUPPRIME, r.stdout)


if __name__ == "__main__":
    unittest.main()
