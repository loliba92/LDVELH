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

    def test_un_livre_dans_trois_etats_compte_pour_un_livre(self):
        j1 = {"111|convenable": 3.48, "111|bon": 5.23, "111|tres_bon": 9.01}
        j2 = {"111|convenable": 3.58, "111|bon": 5.38, "111|tres_bon": 9.26}
        courbe = im.chainer(self.historique([j1, j2]), {"111": "V1 · Gallimard"})
        self.assertEqual(courbe["V1 · Gallimard"][0]["livres"], 1)

    def test_un_petit_groupe_bouge_aussi_mais_il_est_peu_fiable(self):
        j1 = {"111|bon": 10.0}
        j2 = {"111|bon": 5.0}
        courbe = im.chainer(self.historique([j1, j2]), {"111": "V1 · Gallimard"})
        self.assertEqual(courbe["V1 · Gallimard"][0]["indice"], 50.0)
        self.assertEqual(courbe["V1 · Gallimard"][0]["livres"], 1)


class TestObserves(unittest.TestCase):
    def test_un_prix_sans_annonce_ne_pese_pas(self):
        historique = [{"date": "d1", "prix": {"111|bon": 10.0, "222|bon": 10.0}}, {"date": "d2", "prix": {"111|bon": 5.0, "222|bon": 20.0}}]
        gardes = im.garder_observes(historique, {"111|bon"})
        self.assertEqual(gardes[1]["prix"], {"111|bon": 5.0})
        courbe = im.chainer(gardes, {"111": "V1 · Gallimard", "222": "V1 · Gallimard"})
        self.assertEqual(courbe["V1 · Gallimard"][0]["indice"], 50.0)


class TestCascade(unittest.TestCase):
    def test_les_parts_par_serie_font_la_variation_du_groupe(self):
        avant = {"111|bon": 10.0, "111|tres_bon": 20.0, "222|bon": 10.0}
        apres = {"111|bon": 9.0, "111|tres_bon": 20.0, "222|bon": 11.0}
        groupe = {"111": "V1 · Gallimard", "222": "V1 · Gallimard"}
        serie = {"111": "Folio junior", "222": "Défis fantastiques"}
        c = im.cascade_du_dernier_jour([{"date": "d1", "prix": avant}, {"date": "d2", "prix": apres}], {"111|bon", "111|tres_bon", "222|bon"}, groupe, serie)
        g = c["V1 · Gallimard"]
        self.assertAlmostEqual(sum(p["contribution_pct"] for p in g["series"]), g["variation_pct"], places=1)
        self.assertEqual(g["prix_observes"], 3)


if __name__ == "__main__":
    unittest.main()
