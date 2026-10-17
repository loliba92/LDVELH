import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tendances as t


def lig(id_, etat, archive, publie, nature="validé"):
    return {"id": id_, "etat": etat, "archive": archive, "publie": publie, "nature": nature}


VERSIONS = [{"id": "a", "annee": 1985, "version": "V1", "serie": "S1", "editeur": "E"},
            {"id": "b", "annee": 2015, "version": "V4", "serie": "S1", "editeur": "E"},
            {"id": "c", "annee": 2022, "version": "V5", "serie": "S2", "editeur": "F"}]


class TestTendances(unittest.TestCase):
    def test_mediane_des_etats_par_edition(self):
        v = t.variations([lig("a", "convenable", 10, 12), lig("a", "bon", 10, 15), lig("a", "tres_bon", 10, 11)], t.MARCHE)
        self.assertAlmostEqual(v["a"], 0.2)

    def test_archives_et_prix_editeur_exclus_du_marche(self):
        revue = [lig("a", "bon", 10, 20, "archives"), lig("b", "bon", 10, 5, "prix éditeur"), lig("c", "bon", 10, 8, "annonces")]
        self.assertEqual(set(t.variations(revue, t.MARCHE)), {"c"})
        self.assertEqual(set(t.variations(revue, t.AVEC_EDITEUR)), {"b", "c"})

    def test_groupes_par_decennie_et_version(self):
        var = {"a": 0.1, "b": -0.2, "c": -0.4}
        g = t.groupes(var, VERSIONS)
        self.assertEqual([r["cle"] for r in g["decennie"]], ["Avant 1990", "2010–2019", "2020–2029"])
        self.assertEqual({r["cle"]: r["mediane"] for r in g["version"]}, {"V1": 0.1, "V4": -0.2, "V5": -0.4})
        self.assertTrue(all(r["peu"] for r in g["version"]))

    def test_indice_dans_le_temps(self):
        h = [{"date": "2026-10-11", "prix": {"a|bon": 10.0, "b|bon": 20.0}},
             {"date": "2026-10-15", "prix": {"a|bon": 11.0, "b|bon": 20.0, "c|bon": 5.0}}]
        s = t.temps(h)
        self.assertEqual(s[0]["indice"], 100.0)
        self.assertAlmostEqual(s[1]["indice"], 100 * (1.1 ** 0.5), places=1)
        self.assertEqual(s[1]["n"], 2)

    def test_pas_assez_de_dates(self):
        self.assertEqual(t.temps([{"date": "2026-10-11", "prix": {"a|bon": 1.0}}]), [])


if __name__ == "__main__":
    unittest.main()
