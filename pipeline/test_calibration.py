import random, sys, unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibration
from estimation import Obs

AUJ = date(2026, 10, 14)


def jeu(n, rapport, bruit, graine=1, etats=("convenable", "bon", "tres_bon")):
    """n éditions × 3 états : archive tirée au hasard, prix actuel = archive × rapport × bruit log-normal."""
    rnd = random.Random(graine)
    brut = {}
    for i in range(n):
        for e in etats:
            arch = rnd.uniform(5, 40)
            act = arch * rapport * (2.718281828 ** rnd.gauss(0, bruit))
            brut[f"{i}"] = brut.get(f"{i}", {})
            brut[f"{i}"][e] = [Obs(arch, "historique", date(2024, 12, 3), 1), Obs(act, "prix_demande", AUJ, 5)]
    return brut


class TestCalibration(unittest.TestCase):
    def test_apprend_le_rapport(self):
        m = calibration.apprendre(jeu(30, 1.5, 0.15), AUJ)
        self.assertTrue(m["actif"], m["raison"])
        self.assertAlmostEqual(m["rapport_global"], 1.5, delta=0.12)
        self.assertGreater(m["gain"], 0.15)

    def test_inactif_si_peu_de_donnees(self):
        m = calibration.apprendre(jeu(3, 1.5, 0.1), AUJ)      # 9 couples < 20
        self.assertFalse(m["actif"])
        self.assertIn("pas assez", m["raison"])

    def test_inactif_si_aucun_lien_avec_l_archive(self):
        rnd = random.Random(3)
        brut = {str(i): {"bon": [Obs(rnd.uniform(5, 40), "historique", date(2024, 12, 3), 1), Obs(rnd.uniform(5, 40), "prix_demande", AUJ, 5)]} for i in range(60)}
        m = calibration.apprendre(brut, AUJ)
        self.assertFalse(m["actif"], m)

    def test_releve_mince_ignore_pour_apprendre(self):
        brut = {"a": {"bon": [Obs(10, "historique", date(2024, 12, 3), 1), Obs(99, "prix_demande", AUJ, 1)]}}
        self.assertEqual(calibration.paires(brut), [])

    def test_valeur_extreme_ne_derange_pas(self):
        brut = jeu(30, 1.4, 0.1)
        brut["0"]["bon"] = [Obs(10, "historique", date(2024, 12, 3), 1), Obs(900, "prix_demande", AUJ, 5)]
        m = calibration.apprendre(brut, AUJ)
        self.assertAlmostEqual(m["rapport_global"], 1.4, delta=0.1)

    def test_rapport_hors_bornes_refuse(self):
        m = calibration.apprendre(jeu(30, 9.0, 0.05), AUJ)
        self.assertFalse(m["actif"])
        self.assertIn("bornes", m["raison"])

    def test_fraicheur_apprise(self):
        lignes = [{"etat": "bon", "nb_annonces": "3", "nb_toutes": "8", "prix_median": "10", "prix_median_toutes": "14"},
                  {"etat": "bon", "nb_annonces": "4", "nb_toutes": "9", "prix_median": "12", "prix_median_toutes": "16"},
                  {"etat": "bon", "nb_annonces": "5", "nb_toutes": "6", "prix_median": "12", "prix_median_toutes": "13"},   # < 3 anciennes : écartée
                  {"etat": "bon", "nb_annonces": "3", "prix_median": "10"}]                                              # ancien format : écartée
        f = calibration.fraicheur(lignes)
        self.assertEqual(f["bon"]["n"], 2)
        self.assertTrue(0.7 < f["bon"]["rapport"] < 0.8, f)

    def test_toutes_annonces_avec_decote_mesuree(self):
        # 12 éditions où la décote est mesurée (récentes = 0,95 × toutes), puis une édition sans 3 annonces récentes
        mesure = [{"etat": "bon", "nb_annonces": "3", "nb_toutes": "8", "prix_median": "9.5", "prix_median_toutes": "10", "isbn13": f"m{i}", "date": "2026-10-14"} for i in range(12)]
        fr = calibration.fraicheur(mesure)
        lignes = [{"etat": "bon", "nb_annonces": "1", "nb_toutes": "5", "prix_median": "20", "prix_median_toutes": "20", "isbn13": "x", "date": "2026-10-14"},
                  {"etat": "bon", "nb_annonces": "1", "nb_toutes": "2", "prix_median": "20", "prix_median_toutes": "20", "isbn13": "y", "date": "2026-10-14"},     # < 3 en tout
                  {"etat": "bon", "nb_annonces": "4", "nb_toutes": "6", "prix_median": "20", "prix_median_toutes": "20", "isbn13": "z", "date": "2026-10-14"}]     # déjà ≥ 3 récentes
        brut = {}
        n, util = calibration.ajouter_toutes_annonces(brut, lignes, {"x": "kx", "y": "ky", "z": "kz"}, fr)
        self.assertEqual(n, 1)
        self.assertEqual(list(brut), ["kx"])
        self.assertAlmostEqual(brut["kx"]["bon"][0].prix, 19.0, delta=0.1)
        self.assertEqual(brut["kx"]["bon"][0].nb, 5)

    def test_toutes_annonces_refusees_si_decote_mal_mesuree(self):
        fr = {"bon": {"rapport": 0.95, "n": 4}, "tres_bon": {"rapport": 0.5, "n": 40}}      # trop peu d'éditions / hors bornes
        lignes = [{"etat": e, "nb_annonces": "1", "nb_toutes": "5", "prix_median": "20", "prix_median_toutes": "20", "isbn13": "x", "date": "2026-10-14"} for e in ("bon", "tres_bon")]
        brut = {}
        n, util = calibration.ajouter_toutes_annonces(brut, lignes, {"x": "kx"}, fr)
        self.assertEqual((n, util), (0, {}))

    def test_sigma_archive_apprise(self):
        m = calibration.apprendre(jeu(30, 1.5, 0.5), AUJ)         # archive très imprécise : dispersion ≈ 0,5
        sig = calibration.sigma_archive(m)
        self.assertTrue(all(0.25 <= v <= 1.0 for v in sig.values()))
        self.assertGreater(max(sig.values()), 0.35)
        self.assertEqual(calibration.sigma_archive(calibration.apprendre(jeu(3, 1.5, 0.5), AUJ)), {})   # pas assez de données

    def test_remise_a_niveau(self):
        m = calibration.apprendre(jeu(30, 1.5, 0.1), AUJ)
        self.assertAlmostEqual(calibration.remettre_a_niveau(m, 10, "bon"), 15, delta=1.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
