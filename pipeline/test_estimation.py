"""Tests de l'estimateur de prix.   python -m unittest pipeline.test_estimation   (ou : python pipeline/test_estimation.py)"""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estimation import Obs, estimer, mediane_ponderee, poids

AUJ = date(2026, 10, 11)


class TestEstimation(unittest.TestCase):
    def test_la_decote_ne_touche_que_les_prix_demandes(self):
        annonces = [Obs(20.0, "prix_demande", AUJ, 4)]
        self.assertEqual(estimer(annonces, AUJ)["prix"], 20.0)                           # sans décote : inchangé
        self.assertEqual(estimer(annonces, AUJ, decote=0.85)["prix"], 17.0)              # 20 × 0,85
        archive = [Obs(12.34, "historique", AUJ, 1)]
        self.assertEqual(estimer(archive, AUJ, decote=0.85)["prix"], 12.34)              # une archive n'est pas un prix demandé

    def test_la_decote_tire_le_prix_vers_le_bas_sans_changer_la_nature(self):
        obs = [Obs(10.0, "historique", AUJ - timedelta(days=200), 1), Obs(20.0, "prix_demande", AUJ, 4)]
        sans, avec = estimer(obs, AUJ), estimer(obs, AUJ, decote=0.85)
        self.assertLess(avec["prix"], sans["prix"])
        self.assertGreater(avec["prix"], 0.85 * 10.0)
        self.assertEqual((avec["nature"], avec["source"]), (sans["nature"], sans["source"]))

    def test_nb_jour_compte_les_annonces_distinctes_pas_le_cumul(self):
        revu = [Obs(10.0, "prix_demande", AUJ - timedelta(days=k), 1) for k in range(5)]      # même exemplaire vu 5 jours de suite
        r = estimer(revu, AUJ)
        self.assertEqual((r["nb"], r["nb_jour"]), (5, 1))
        trois = [Obs(10.0, "prix_demande", AUJ, 3)]
        self.assertEqual(estimer(trois, AUJ)["nb_jour"], 3)
        self.assertNotIn("nb_jour", estimer([Obs(12.0, "historique", AUJ, 1)], AUJ))           # archive : aucune annonce

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
        r = estimer([Obs(10, "historique", AUJ, 1), Obs(20, "prix_demande", AUJ, 5)], AUJ)
        self.assertTrue(15 < r["prix"] < 20, r["prix"])        # lissé, mais plus près des annonces (n = 5)
        self.assertEqual((r["source"], r["nature"], r["nb"]), ("actuel", "annonces", 5))

    def test_trois_annonces_ne_suffisent_pas_a_faire_oublier_l_archive_en_confiance(self):
        r = estimer([Obs(10, "historique", AUJ - timedelta(days=300), 1), Obs(50, "prix_demande", AUJ, 3)], AUJ)
        self.assertEqual(r["source"], "actuel")         # une annonce récente pèse plus qu'une archive de dix mois
        self.assertEqual(r["confiance"], "moyenne")

    def test_une_annonce_isolee_tres_eloignee_de_l_archive_est_ignoree(self):
        r = estimer([Obs(10, "historique", AUJ, 1), Obs(104.69, "prix_demande", AUJ, 1), Obs(90, "prix_demande", AUJ - timedelta(days=7), 2)], AUJ)
        self.assertEqual((r["prix"], r["source"]), (10, "archives"))          # 1 annonce un jour, 2 une autre : relevés minces et dix fois l'archive, donc écartés

    def test_les_annonces_d_un_meme_jour_de_plusieurs_sources_se_comptent_ensemble(self):
        """2 annonces eBay + 1 exemplaire de librairie le même jour : 3 annonces, le relevé compte (et l'archive cède)."""
        r = estimer([Obs(40, "historique", AUJ, 1), Obs(20, "prix_demande", AUJ, 2), Obs(17, "prix_demande", AUJ, 1)], AUJ)
        self.assertEqual(r["source"], "actuel")
        self.assertEqual(r["nb"], 3)
        self.assertLess(r["prix"], 30)                                       # tiré vers les annonces (17-20 €), pas vers l'archive (40 €)
        seul = estimer([Obs(40, "historique", AUJ, 1), Obs(17, "prix_demande", AUJ, 1)], AUJ)           # une offre seule compte, mais peu
        self.assertTrue(30 < seul["prix"] < 40, seul["prix"])
        self.assertEqual(seul["confiance"], "faible")

    def test_sans_archive_un_releve_mince_donne_une_cote_faible(self):
        r = estimer([Obs(30, "prix_demande", AUJ, 2)], AUJ)
        self.assertEqual((r["prix"], r["nature"], r["confiance"]), (30.0, "annonces", "faible"))

    def test_une_annonce_un_peu_differente_de_l_archive_la_deplace_peu(self):
        r = estimer([Obs(10, "historique", AUJ, 1), Obs(14, "prix_demande", AUJ, 1)], AUJ)
        self.assertTrue(10 < r["prix"] < 12.5, r["prix"])

    def test_vente_reelle_pese_plus_qu_une_annonce(self):
        r = estimer([Obs(40, "prix_demande", AUJ, 3), Obs(20, "vente_reelle", AUJ, 1)], AUJ)
        self.assertTrue(20 <= r["prix"] < 30, r["prix"])        # plus près de la vente réelle que de l'annonce
        self.assertEqual(r["nature"], "ventes")

    def test_fraicheur_poids_divise_par_deux_tous_les_90_jours(self):
        frais = poids(Obs(10, "prix_demande", AUJ, 1), AUJ)
        vieux = poids(Obs(10, "prix_demande", AUJ - timedelta(days=90), 1), AUJ)
        self.assertAlmostEqual(vieux, frais / 2)

    def test_une_vieille_annonce_cede_a_une_recente(self):
        r = estimer([Obs(100, "prix_demande", AUJ - timedelta(days=360), 3), Obs(30, "prix_demande", AUJ, 3)], AUJ)
        self.assertAlmostEqual(r["prix"], 30, delta=3)

    def test_le_lissage_evolue_sans_sauter(self):
        """Des relevés hebdomadaires qui montent régulièrement donnent un prix qui monte régulièrement."""
        suite, prix = [Obs(20, "historique", date(2026, 9, 1), 1)], []
        for k, v in enumerate([22, 23, 25, 26]):
            suite.append(Obs(v, "prix_demande", date(2026, 9, 8) + timedelta(days=7 * k), 5))
            prix.append(estimer(suite, date(2026, 9, 8) + timedelta(days=7 * k))["prix"])
        self.assertEqual(prix, sorted(prix))
        self.assertTrue(all(b - a < 3 for a, b in zip(prix, prix[1:])), prix)

    def test_incertitude_de_l_archive_apprise(self):
        """Si l'archive est jugée peu fiable (sigma élevé), le relevé actuel l'emporte davantage."""
        obs = [Obs(100, "historique", AUJ, 1), Obs(10, "prix_demande", AUJ, 5)]
        confiante = estimer(obs, AUJ)["prix"]
        mefiante = estimer(obs, AUJ, 0.8)["prix"]
        self.assertLess(mefiante, confiante)
        self.assertLess(mefiante, 25)                        # proche du relevé, pas de l'archive

    def test_valeur_extreme_amortie(self):
        normal = estimer([Obs(20, "historique", AUJ - timedelta(days=7), 1), Obs(22, "prix_demande", AUJ, 5)], AUJ)["prix"]
        extreme = estimer([Obs(20, "historique", AUJ - timedelta(days=7), 1), Obs(200, "prix_demande", AUJ, 5)], AUJ)["prix"]
        self.assertLess(extreme, 200 * 0.6)                 # n'adopte pas aveuglément 200
        self.assertGreater(extreme, normal)

    def test_plus_d_annonces_plus_de_poids(self):
        peu = estimer([Obs(20, "historique", AUJ, 1), Obs(40, "prix_demande", AUJ, 3)], AUJ)["prix"]
        beaucoup = estimer([Obs(20, "historique", AUJ, 1), Obs(40, "prix_demande", AUJ, 9)], AUJ)["prix"]
        self.assertGreater(beaucoup, peu)

    def test_nombre_d_annonces_plafonne(self):
        self.assertAlmostEqual(poids(Obs(1, "prix_demande", AUJ, 500), AUJ), poids(Obs(1, "prix_demande", AUJ, 9), AUJ))

    def test_confiance_croit_avec_le_nombre_d_annonces(self):
        faible = estimer([Obs(10, "prix_demande", AUJ - timedelta(days=90), 3)], AUJ)["confiance"]
        moyenne = estimer([Obs(10, "prix_demande", AUJ, 4)], AUJ)["confiance"]
        elevee = estimer([Obs(10, "prix_demande", AUJ, 9)], AUJ)["confiance"]
        self.assertEqual((faible, moyenne, elevee), ("faible", "moyenne", "élevée"))

    def test_date_et_nombre_portent_sur_les_observations_actuelles(self):
        r = estimer([Obs(10, "historique", date(2026, 1, 1), 1),
                     Obs(20, "prix_demande", date(2026, 10, 1), 3), Obs(22, "prix_demande", date(2026, 10, 8), 4)], AUJ)
        self.assertEqual((r["date"], r["nb"]), ("2026-10-08", 7))

    def test_le_nombre_ne_melange_pas_ventes_et_annonces(self):
        r = estimer([Obs(25, "vente_reelle", date(2026, 10, 5), 1), Obs(30, "prix_demande", date(2026, 10, 10), 6)], AUJ)
        self.assertEqual((r["nature"], r["nb"]), ("ventes", 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
