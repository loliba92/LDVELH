"""Tests de la rareté.   python pipeline/test_rarete.py"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rarete


class TestRarete(unittest.TestCase):
    def test_niveaux_par_version(self):
        versions = [{"isbn13": str(i), "version": "V1"} for i in range(20)] + [{"isbn13": "x", "version": "V2"}, {"isbn13": "inconnu", "version": "V1"}]
        pct = {str(i): float(i) for i in range(20)}
        pct["x"] = 0.0
        n = rarete.annoter(versions, pct)
        self.assertEqual(n, 20)                                        # V2 n'a qu'une édition : pas de niveau ; l'ISBN inconnu non plus
        niv = {v["isbn13"]: v.get("rarete", {}).get("niveau") for v in versions}
        self.assertEqual((niv["0"], niv["1"], niv["5"], niv["11"], niv["19"]), ("tres_rare", "tres_rare", "rare", "peu_courant", "courant"))
        self.assertIsNone(niv["x"])
        self.assertIsNone(niv["inconnu"])

    def test_les_tirages_gallimard_donnent_le_niveau(self):
        d = Path(tempfile.mkdtemp()) / "t.txt"
        lignes = ["# commentaire"] + [f"MA SERIE|1990|{i}|Livre {chr(65 + i)} Test|0|{i + 1}|0|0|0|0|0|0" for i in range(12)]
        d.write_text("\n".join(lignes), encoding="utf-8")
        tirages = rarete.charger_tirages(d)
        versions = [{"id": f"i{i}", "isbn13": f"i{i}", "version": "V1", "serie": "Ma série", "livre": f"Livre {chr(65 + i)} Test", "titre": f"Livre {chr(65 + i)} Test"} for i in range(12)]
        versions.append({"id": "autre", "isbn13": "x", "version": "V1", "serie": "Autre", "livre": "Sans tirage", "titre": "Sans tirage"})
        n = rarete.annoter(versions, {}, tirages)
        self.assertEqual(n, 12)
        r = {v["id"]: v.get("rarete") for v in versions}
        self.assertEqual((r["i0"]["tirages"], r["i0"]["niveau"]), (1, "tres_rare"))
        self.assertEqual(r["i11"]["niveau"], "courant")
        self.assertIsNone(r["autre"])

    def test_lecture_du_dernier_fichier(self):
        d = Path(tempfile.mkdtemp())
        (d / "books_data-2026-01-01.csv").write_text("isbn,collection_percentage\n111,5\n", encoding="utf-8")
        (d / "books_data-2026-02-01.csv").write_text("isbn,collection_percentage\n222,  26   \n333,\n", encoding="utf-8")
        self.assertEqual(rarete.charger(d), {"222": 26.0})
        self.assertEqual(rarete.charger(d / "absent"), {})


if __name__ == "__main__":
    unittest.main()
