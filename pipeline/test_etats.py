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
        self.assertEqual(etats.repartir(p, R), 2)           # le bon état, observé, ne change pas ; les deux autres sont déduits
        self.assertEqual((p["convenable"]["prix"], p["bon"]["prix"], p["tres_bon"]["prix"]), (20.0, 30.0, 50.0))
        self.assertNotIn("repartition", p["bon"])
        self.assertTrue(p["convenable"]["deduit"] and p["tres_bon"]["deduit"])        # états remplacés : déduits
        self.assertEqual(p["convenable"]["source"], "archives")                        # jamais comptés comme prix actuels

    def test_un_etat_observe_garde_son_prix(self):
        """Convenable observé à 8,55 : il reste à 8,55 (et non 40 % du plus haut prix observé) ; bon et très bon sont déduits."""
        p = {"convenable": est(8.55, "actuel"), "bon": est(6.98, "archives"), "tres_bon": est(29.79, "archives")}
        etats.repartir(p, R)
        self.assertEqual(p["convenable"]["prix"], 8.55)
        self.assertEqual((p["bon"]["prix"], p["tres_bon"]["prix"]), (12.83, 21.38))
        self.assertTrue(p["bon"]["deduit"] and p["tres_bon"]["deduit"])

    def test_plusieurs_etats_observes_ne_changent_pas(self):
        """Trois états observés : aucun n'est touché (la cohérence entre états relève de `aligner`)."""
        p = {e: {**est(10, "actuel"), "incertitude": 0.2} for e in etats.ETATS}
        self.assertEqual(etats.repartir(p, R), 0)
        self.assertEqual([p[e]["prix"] for e in etats.ETATS], [10, 10, 10])

    def test_etat_manquant_deduit_du_niveau_pondere(self):
        p = {"bon": {**est(30, "actuel"), "incertitude": 0.05}, "tres_bon": {**est(100, "actuel"), "incertitude": 0.9}}
        etats.repartir(p, R)
        self.assertEqual((p["bon"]["prix"], p["tres_bon"]["prix"]), (30, 100))      # observés : inchangés
        self.assertAlmostEqual(p["convenable"]["prix"], 20, delta=0.6)             # niveau ≈ BE ÷ 0,6 = 50 (le plus fiable pèse davantage)

    def test_tres_bon_etat_au_prix_du_neuf(self):
        """Édition en vente : TBE = prix éditeur (source « neuf », compte comme actuel) ; bon et convenable en sont déduits."""
        p = {"tres_bon": {**est(13.5, "neuf"), "incertitude": 0.05}, "bon": est(10.7, "archives"), "convenable": est(6.1, "archives")}
        etats.repartir(p, R)
        self.assertEqual((p["convenable"]["prix"], p["bon"]["prix"], p["tres_bon"]["prix"]), (5.4, 8.1, 13.5))
        self.assertTrue(p["bon"]["deduit"] and p["convenable"]["deduit"])

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


class TestPlafond(unittest.TestCase):
    def test_un_prix_ne_bouge_que_de_dix_pour_cent_par_jour(self):
        p = {"convenable": est(20), "bon": est(20), "tres_bon": est(20)}
        p["convenable"]["prix"], p["bon"]["prix"], p["tres_bon"]["prix"] = 30.0, 21.0, 10.0
        n = etats.plafonner(p, {"convenable": 20.0, "bon": 20.0, "tres_bon": 20.0}, 0.10)
        self.assertEqual((p["convenable"]["prix"], p["bon"]["prix"], p["tres_bon"]["prix"]), (22.0, 21.0, 18.0))
        self.assertEqual(n, 2)
        self.assertTrue(p["convenable"]["plafonne"] and "plafonne" not in p["bon"])

    def test_un_prix_valide_n_est_jamais_plafonne(self):
        p = {"bon": est(40, source="validé")}
        self.assertEqual(etats.plafonner(p, {"bon": 20.0}, 0.10), 0)
        self.assertEqual(p["bon"]["prix"], 40)

    def test_sans_prix_de_la_veille_rien_ne_change(self):
        p = {"bon": est(40)}
        self.assertEqual(etats.plafonner(p, {"bon": None}, 0.10), 0)


if __name__ == "__main__":
    unittest.main()
