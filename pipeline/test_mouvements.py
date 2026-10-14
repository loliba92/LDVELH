import sys, tempfile, unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mouvements


def versions(prix):
    return [{"id": f"i{n}", "isbn13": f"i{n}", "titre": f"Livre {n}", "serie": "S", "numero": "001", "version": "V1",
             "prix": {"convenable": None, "bon": p, "tres_bon": None}, "prix_info": {"bon": {"nature": "annonces", "nb": 3}}}
            for n, p in enumerate(prix)]


class TestMouvements(unittest.TestCase):
    def test_hausses_baisses_et_seuils(self):
        av = mouvements.instantane(versions([10, 10, 10, 10]), date(2026, 10, 11))
        ap_v = versions([20, 5, 10.2, 10.4])          # +100 %, -50 %, +2 % (ignoré), +4 % (ignoré)
        mv = mouvements.comparer(av, mouvements.instantane(ap_v, date(2026, 10, 14)), ap_v)
        self.assertEqual([m["titre"] for m in mv["hausses"]], ["Livre 0"])
        self.assertEqual([m["titre"] for m in mv["baisses"]], ["Livre 1"])
        self.assertEqual((mv["nb_comparees"], mv["nb_modifiees"], mv["nb_grands_mouvements"]), (4, 4, 2))

    def test_pas_de_comparaison_sans_precedent(self):
        v = versions([10])
        mv = mouvements.comparer(None, mouvements.instantane(v, date(2026, 10, 14)), v)
        self.assertIsNone(mv["precedent"])
        self.assertEqual(mv["hausses"], [])

    def test_nouvelle_cote(self):
        av = mouvements.instantane(versions([10]), date(2026, 10, 11))
        ap_v = versions([10, 12])
        mv = mouvements.comparer(av, mouvements.instantane(ap_v, date(2026, 10, 14)), ap_v)
        self.assertEqual(mv["nouvelles_cotes"], 1)

    def test_mise_a_jour_et_reexecution_le_meme_jour(self):
        with tempfile.TemporaryDirectory() as d:
            hist, sortie = Path(d) / "h.json", Path(d) / "m.json"
            base = mouvements.instantane(versions([10, 10]), date(2026, 10, 11))
            modele = {"actif": False, "n_paires": 3, "raison": "test", "gain": None}
            mv1 = mouvements.mettre_a_jour(versions([20, 10]), date(2026, 10, 14), base, modele, hist, sortie)
            self.assertEqual((mv1["precedent"], len(mv1["hausses"])), ("2026-10-11", 1))
            mv2 = mouvements.mettre_a_jour(versions([20, 10]), date(2026, 10, 14), base, modele, hist, sortie)
            self.assertEqual(mv2["precedent"], "2026-10-11")          # même résultat si on relance le même jour
            mv3 = mouvements.mettre_a_jour(versions([20, 5]), date(2026, 10, 21), base, modele, hist, sortie)
            self.assertEqual((mv3["precedent"], len(mv3["baisses"])), ("2026-10-14", 1))
            self.assertEqual(len(mouvements.charger(hist)), 3)

    def test_resume_markdown(self):
        av = mouvements.instantane(versions([10]), date(2026, 10, 11))
        ap_v = versions([20])
        mv = mouvements.comparer(av, mouvements.instantane(ap_v, date(2026, 10, 14)), ap_v)
        md = mouvements.resume_md(mv, {"actif": False, "n_paires": 3, "raison": "peu de données", "gain": None})
        self.assertIn("Plus fortes hausses", md)
        self.assertIn("+100%", md)
        self.assertIn("10,00 €", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
