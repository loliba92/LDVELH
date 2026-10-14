import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_site import aligner


def e(prix):
    return {"prix": prix, "source": "archives"}


def a(prix):
    return {"prix": prix, "source": "actuel"}


class TestAligner(unittest.TestCase):
    def test_tbe_sous_le_be_est_remonte(self):
        p = {"convenable": e(10), "bon": e(15), "tres_bon": e(12)}
        self.assertEqual(aligner(p), 1)
        self.assertEqual(p["tres_bon"]["prix"], 15)
        self.assertTrue(p["tres_bon"]["ajuste"])

    def test_tbe_sous_le_c_et_le_be(self):
        p = {"convenable": e(39.26), "bon": e(45.15), "tres_bon": e(29.38)}
        aligner(p)
        self.assertEqual((p["convenable"]["prix"], p["bon"]["prix"], p["tres_bon"]["prix"]), (39.26, 45.15, 45.15))

    def test_be_sous_le_c_est_remonte(self):
        p = {"convenable": e(20), "bon": e(18), "tres_bon": e(25)}
        aligner(p)
        self.assertEqual((p["bon"]["prix"], p["tres_bon"]["prix"]), (20, 25))

    def test_prix_egaux_et_ordre_normal_inchanges(self):
        for p in ({"convenable": e(10), "bon": e(10), "tres_bon": e(10)}, {"convenable": e(5), "bon": e(8), "tres_bon": e(12)}):
            self.assertEqual(aligner(p), 0)
            self.assertFalse(any("ajuste" in v for v in p.values()))

    def test_archive_gonflee_ne_tire_pas_un_prix_actuel(self):
        """BE d'archive à 50, TBE actuel à 7,5 : c'est le BE d'archive qu'on ramène, pas le TBE actuel qu'on remonte."""
        p = {"convenable": e(5), "bon": e(50), "tres_bon": a(7.5)}
        self.assertEqual(aligner(p), 1)
        self.assertEqual((p["bon"]["prix"], p["tres_bon"]["prix"]), (7.5, 7.5))
        self.assertTrue(p["bon"]["ajuste"])
        self.assertNotIn("ajuste", p["tres_bon"])

    def test_cascade_vers_le_convenable(self):
        p = {"convenable": e(40), "bon": e(50), "tres_bon": a(7.5)}
        aligner(p)
        self.assertEqual((p["convenable"]["prix"], p["bon"]["prix"], p["tres_bon"]["prix"]), (7.5, 7.5, 7.5))

    def test_etat_inferieur_actuel_remonte_l_etat_superieur(self):
        p = {"bon": a(30), "tres_bon": e(20)}
        aligner(p)
        self.assertEqual(p["tres_bon"]["prix"], 30)

    def test_etat_manquant_ignore(self):
        p = {"convenable": e(10), "tres_bon": e(8)}
        self.assertEqual(aligner(p), 1)
        self.assertEqual(p["tres_bon"]["prix"], 10)
        self.assertEqual(aligner({"bon": e(9)}), 0)


if __name__ == "__main__":
    unittest.main()
