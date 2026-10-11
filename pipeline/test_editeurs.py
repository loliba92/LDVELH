import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from editions import normaliser_editeur as n


class TestEditeurs(unittest.TestCase):
    def test_variantes_de_gallimard_jeunesse(self):
        for v in ("Gallimard jeunesse", "Gallimard-Jeunesse", "Gallimard Jeunesse", "gallimard-jeunesse", " GALLIMARD  JEUNESSE ", "Gallimard-jeunesse."):
            self.assertEqual(n(v), "Gallimard Jeunesse", v)

    def test_gallimard_seul_reste_distinct(self):
        self.assertEqual(n("gallimard"), "Gallimard")
        self.assertNotEqual(n("Gallimard"), n("Gallimard Jeunesse"))

    def test_autres_editeurs_inchanges(self):
        self.assertEqual(n("Hachette  Jeunesse"), "Hachette Jeunesse")   # seuls les espaces superflus sont nettoyés
        self.assertEqual(n(""), "")
        self.assertEqual(n(None), "")


if __name__ == "__main__":
    unittest.main()
