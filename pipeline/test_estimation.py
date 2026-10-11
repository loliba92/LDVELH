"""Tests de l'estimateur de prix.   python -m unittest pipeline.test_estimation   (ou : python pipeline/test_estimation.py)"""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estimation import Obs, estimer, mediane_ponderee, poids

AUJ = date(2026, 10, 11)


class TestEstimation(unittest.TestCase):
    def test_aucune_observation(self):
        self.assertIsNone(estimer([], AUJ))

    def test_une_seule_archive_donne_exactement_son_prix(self):
        # garantit que le site n'a pas changé tant qu'il n'y a que l'ancien relevé
        r = estimer([Obs(12.34, "historique", AUJ, 1)], AUJ)
        self.assertEqual(r["prix"], 12.34)
        self.assertEqual((r["source"], r["nature"], r["confiance"]), ("archives", "archives", "ancienne"))

    def test_mediane_simple(self):
        self.assertEqual(mediane_ponderee([(10, 1), (20, 1), (30, 1)]), 20)

    def test_egalite_donne_la_moyenne_des_deux_centrales(self):
        self.assertEqual(mediane_ponderee([(10, 1), (20, 1)]), 15)

    def test_poids_fort_l_emporte(self):
        self.assertEqual(mediane_ponderee([(10, 0.2), (50, 0.8)]), 50)

    def test_annonces_actuelles_l_emportent_sur_l_archive(self):
        r = estimer([Obs(10, "historique", AUJ, 1), Obs(50, "prix_demande", AUJ, 5)], AUJ)
        self.assertEqual(r["prix"], 50)
        self.assertEqual((r["source"], r["nature"], r["nb"]), ("actuel", "annonces", 5))

    def test_une_seule_annonce_ne_suffit_pas_a_faire_oublier_l_archive_en_confiance(self):
        r = estimer([Obs(10, "historique", AUJ, 1), Obs(50, "prix_demande", AUJ, 1)], AUJ)
        self.assertEqual(r["source"], "mixte")          # annonce 0,3 contre archive 0,2 : 60 % < 70 %
        self.assertEqual(r["confiance"], "faible")

    def test_vente_reelle_pese_plus_qu_une_annonce(self):
        r = estimer([Obs(40, "prix_demande", AUJ, 1), Obs(20, "vente_reelle", AUJ, 1)], AUJ)
        self.assertEqual(r["prix"], 20)
        self.assertEqual(r["nature"], "ventes")

    def test_fraicheur_poids_divise_par_deux_tous_les_90_jours(self):
        frais = poids(Obs(10, "prix_demande", AUJ, 1), AUJ)
        vieux = poids(Obs(10, "prix_demande", AUJ - timedelta(days=90), 1), AUJ)
        self.assertAlmostEqual(vieux, frais / 2)

    def test_une_vieille_annonce_cede_a_une_recente(self):
        r = estimer([Obs(100, "prix_demande", AUJ - timedelta(days=360), 1), Obs(30, "prix_demande", AUJ, 1)], AUJ)
        self.assertEqual(r["prix"], 30)

    def test_nombre_d_annonces_plafonne(self):
        self.assertAlmostEqual(poids(Obs(1, "prix_demande", AUJ, 500), AUJ), poids(Obs(1, "prix_demande", AUJ, 9), AUJ))

    def test_confiance_croit_avec_le_nombre_d_annonces(self):
        faible = estimer([Obs(10, "prix_demande", AUJ, 1)], AUJ)["confiance"]
        moyenne = estimer([Obs(10, "prix_demande", AUJ, 4)], AUJ)["confiance"]
        elevee = estimer([Obs(10, "prix_demande", AUJ, 9)], AUJ)["confiance"]
        self.assertEqual((faible, moyenne, elevee), ("faible", "moyenne", "élevée"))

    def test_date_et_nombre_portent_sur_les_observations_actuelles(self):
        r = estimer([Obs(10, "historique", date(2026, 1, 1), 1),
                     Obs(20, "prix_demande", date(2026, 10, 1), 3), Obs(22, "prix_demande", date(2026, 10, 8), 2)], AUJ)
        self.assertEqual((r["date"], r["nb"]), ("2026-10-08", 5))

    def test_le_nombre_ne_melange_pas_ventes_et_annonces(self):
        r = estimer([Obs(25, "vente_reelle", date(2026, 10, 5), 1), Obs(30, "prix_demande", date(2026, 10, 10), 6)], AUJ)
        self.assertEqual((r["nature"], r["nb"]), ("ventes", 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
