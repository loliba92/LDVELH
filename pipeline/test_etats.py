import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import etats

R = etats.DEFAUT


def est(prix, source="archives", date="2026-10-14"):
    return {"prix": prix, "source": source, "nature": "x", "nb": 3, "date": date, "confiance": "moyenne"}


class TestEtats(unittest.TestCase):
    def test_depuis_le_tres_bon(self):
        p = {"tres_bon": est(50)}
        self.assertEqual(etats.completer(p, R), 2)
        self.assertEqual((p["convenable"]["prix"], p["bon"]["prix"]), (20.0, 30.0))
        self.assertTrue(p["bon"]["deduit"])
        self.assertEqual((p["bon"]["confiance"], p["bon"]["source"]), ("faible", "archives"))

    def test_depuis_le_bon(self):
        p = {"bon": est(30)}
        etats.completer(p, R)
        self.assertEqual((p["convenable"]["prix"], p["tres_bon"]["prix"]), (20.0, 50.0))

    def test_depuis_le_convenable(self):
        p = {"convenable": est(20)}
        etats.completer(p, R)
        self.assertEqual((p["bon"]["prix"], p["tres_bon"]["prix"]), (30.0, 50.0))

    def test_un_etat_connu_n_est_jamais_modifie(self):
        p = {"convenable": est(5), "tres_bon": est(50)}
        etats.completer(p, R)
        self.assertEqual(p["convenable"]["prix"], 5)
        self.assertNotIn("deduit", p["convenable"])
        self.assertEqual(p["bon"]["prix"], 15.0)         # moyenne géométrique des deux niveaux (12,5 et 50) × 0,6

    def test_le_releve_actuel_prime_sur_l_archive(self):
        p = {"bon": est(60, "archives"), "tres_bon": est(10, "actuel")}      # l'archive du BE est ignorée comme référence
        etats.completer(p, R)
        self.assertEqual(p["convenable"]["prix"], 4.0)

    def test_rien_a_deduire(self):
        self.assertEqual(etats.completer({}, R), 0)
        self.assertEqual(etats.completer({"convenable": est(1), "bon": est(2), "tres_bon": est(3)}, R), 0)

    def test_ratios_par_defaut_si_fichier_absent_ou_incoherent(self):
        self.assertEqual(etats.charger_ratios("/n/existe/pas.json"), etats.DEFAUT)
        import tempfile, json
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "r.json"
            f.write_text(json.dumps({"convenable": 0.9, "bon": 0.5, "tres_bon": 1}))    # ordre incohérent
            self.assertEqual(etats.charger_ratios(f), etats.DEFAUT)
            f.write_text(json.dumps({"convenable": 0.5, "bon": 0.7, "tres_bon": 1}))
            self.assertEqual(etats.charger_ratios(f)["bon"], 0.7)


if __name__ == "__main__":
    unittest.main()
