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

    def test_repartir_un_seul_etat_actuel(self):
        p = {"bon": est(30, "actuel"), "convenable": est(99, "archives"), "tres_bon": est(7, "archives")}
        self.assertEqual(etats.repartir(p, R), 3)
        # plafond : le très bon état ne dépasse pas le prix actuel observé (30), le bon état en vaut 60 %
        self.assertEqual((p["convenable"]["prix"], p["bon"]["prix"], p["tres_bon"]["prix"]), (12.0, 18.0, 30.0))
        self.assertTrue(p["bon"]["repartition"])
        self.assertTrue(p["convenable"]["deduit"] and p["tres_bon"]["deduit"])        # états remplacés : déduits
        self.assertEqual(p["convenable"]["source"], "archives")                        # jamais comptés comme prix actuels

    def test_repartir_plusieurs_etats_actuels_plats(self):
        """Trois états au même prix (annonces non différenciées) : le niveau est la moyenne pondérée, l'ordre 40/60 est rétabli."""
        p = {e: {**est(10, "actuel"), "incertitude": 0.2} for e in etats.ETATS}
        etats.repartir(p, R)
        c, b, t = (p[e]["prix"] for e in etats.ETATS)
        self.assertAlmostEqual(c / t, 0.4, places=2)
        self.assertAlmostEqual(b / t, 0.6, places=2)
        self.assertEqual(t, 10)                              # plafonné au prix actuel observé

    def test_le_plus_fiable_pese_davantage(self):
        p = {"bon": {**est(30, "actuel"), "incertitude": 0.05}, "tres_bon": {**est(100, "actuel"), "incertitude": 0.9}}
        etats.repartir(p, R)
        self.assertAlmostEqual(p["tres_bon"]["prix"], 50, delta=1.5)              # proche de BE/0,6 = 50

    def test_edition_sans_prix_actuel_inchangee(self):
        p = {"convenable": est(5), "bon": est(8), "tres_bon": est(12)}
        self.assertEqual(etats.repartir(p, R), 0)
        self.assertEqual((p["convenable"]["prix"], p["bon"]["prix"], p["tres_bon"]["prix"]), (5, 8, 12))

    def test_rien_a_deduire(self):
        self.assertEqual(etats.completer({}, R), 0)
        self.assertEqual(etats.completer({"convenable": est(1), "bon": est(2), "tres_bon": est(3)}, R), 0)

    def test_ecart_etat_superieur(self):
        import tempfile, json
        self.assertEqual(etats.charger_ecart("/n/existe/pas.json"), 1.2)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "r.json"
            f.write_text(json.dumps({"ecart_etat_superieur": 1.1}))
            self.assertEqual(etats.charger_ecart(f), 1.1)
            f.write_text(json.dumps({"ecart_etat_superieur": 5}))                  # hors limites : valeur par défaut
            self.assertEqual(etats.charger_ecart(f), 1.2)

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
