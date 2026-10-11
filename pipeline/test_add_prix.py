import csv, tempfile, unittest
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import add_prix


class TestAddPrix(unittest.TestCase):
    def test_ajout_et_entete(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "o.csv"
            add_prix.ajouter(f, add_prix.ligne("9782070583805", 12.5, "bon", "vente", date(2026, 10, 3)))
            add_prix.ajouter(f, add_prix.ligne("2070583805", 9, "tres_bon", "releve", date(2026, 10, 4)))
            rows = list(csv.DictReader(open(f, encoding="utf-8")))
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]["source"], rows[0]["type_prix"], rows[0]["prix"]), ("vente_perso", "vente_reelle", "12.50"))
        self.assertEqual(rows[1]["isbn"], "9782070583805")

    def test_prix_professionnel(self):
        r = add_prix.ligne("9782070583805", 75, "bon", "pro", date(2026, 10, 11))
        self.assertEqual((r["source"], r["type_prix"]), ("releve_manuel", "prix_pro"))

    def test_refus(self):
        for args in (("9782070583805", 5, "mauvais", "vente"), ("9782070583805", -1, "bon", "vente"),
                     ("9782070583805", 5, "bon", "inconnu")):
            with self.assertRaises(ValueError):
                add_prix.ligne(*args, date(2026, 10, 3))


if __name__ == "__main__":
    unittest.main()
