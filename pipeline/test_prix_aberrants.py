import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prix_aberrants as pa


class TestPrixAberrants(unittest.TestCase):
    def test_seuil_a_trois_fois(self):
        self.assertFalse(pa.est_aberrant(29.9, 10))
        self.assertTrue(pa.est_aberrant(30, 10))
        self.assertTrue(pa.est_aberrant(476, 15.8))

    def test_sans_reference(self):
        self.assertFalse(pa.est_aberrant(500, None))
        self.assertFalse(pa.est_aberrant(500, 0))

    def test_chargement_du_tbe(self):
        f = Path(tempfile.mkdtemp()) / "revue.json"
        f.write_text(json.dumps([{"isbn": "111", "etat": "tres_bon", "publie": 12.5}, {"isbn": "111", "etat": "bon", "publie": 8}, {"isbn": "", "etat": "tres_bon", "publie": 3}]), encoding="utf-8")
        self.assertEqual(pa.charger_tbe(f), {"111": 12.5})
        self.assertEqual(pa.charger_tbe(f.parent / "absent.json"), {})
