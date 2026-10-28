"""Tests de l'indice de marché (sans fichiers réels).
    python3 -m unittest pipeline.test_indice_marche"""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indice_marche as im

GROUPE = {"111": "V1 · Gallimard", "222": "V2 · Gallimard"}


class TestVariations(unittest.TestCase):
    def test_on_ne_compte_que_les_prix_presents_les_deux_jours(self):
        avant = {"111|bon": 10.0, "222|bon": 10.0}
        apres = {"111|bon": 11.0, "222|bon": None}
        v = im.variations(avant, apres, GROUPE)
        self.assertEqual(list(v), ["V1 · Gallimard"])
        self.assertAlmostEqual(v["V1 · Gallimard"][0], math.log(1.1))

    def test_un_isbn_sans_groupe_est_ignore(self):
        self.assertEqual(im.variations({"999|bon": 10.0}, {"999|bon": 12.0}, GROUPE), {})


class TestChainer(unittest.TestCase):
    def historique(self, jours):
        return [{"date": f"2026-10-{i + 1:02d}", "prix": p} for i, p in enumerate(jours)]

    def test_baisse_mediane_du_groupe(self):
        # 10 livres du même groupe, tous à -10 % le second jour : indice 100 puis 90
        j1 = {f"111|{i}": 10.0 for i in range(10)}
        j2 = {f"111|{i}": 9.0 for i in range(10)}
        courbe = im.chainer(self.historique([j1, j2]), {"111": "V1 · Gallimard"})
        self.assertEqual([s["indice"] for s in courbe["V1 · Gallimard"]], [90.0])

    def test_un_petit_groupe_bouge_aussi_mais_il_est_peu_fiable(self):
        j1 = {"111|bon": 10.0}
        j2 = {"111|bon": 5.0}
        courbe = im.chainer(self.historique([j1, j2]), {"111": "V1 · Gallimard"})
        self.assertEqual(courbe["V1 · Gallimard"][0]["indice"], 50.0)
        self.assertEqual(courbe["V1 · Gallimard"][0]["livres"], 1)
        self.assertEqual(im.confiance(1), "faible")

    def test_niveaux_de_confiance_selon_le_nombre_de_livres(self):
        self.assertEqual([im.confiance(n) for n in (9, 10, 49, 50, 576)], ["faible", "moyenne", "moyenne", "élevée", "élevée"])


if __name__ == "__main__":
    unittest.main()
