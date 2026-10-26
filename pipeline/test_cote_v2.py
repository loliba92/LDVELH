import sys, unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cote_v2

def ligne(prix, lien="https://www.ebay.fr/itm/1"):
    return {"isbn13": "9782070000001", "etat": "bon", "prix": str(prix), "lien": lien}

class TestCoteV2(unittest.TestCase):
    def test_annonce_qui_reste_ne_pese_pas_deux_fois(self):
        jours = {date(2026, 10, d): [ligne(60)] for d in (21, 22, 23)}
        obs = cote_v2.evenements(jours, "9782070000001", "bon")
        self.assertEqual([(o.type, o.prix) for o in obs], [("prix_demande", 60.0)])

    def test_disparition_compte_comme_vente_probable(self):
        jours = {date(2026, 10, 21): [ligne(60)], date(2026, 10, 22): [ligne(60)], date(2026, 10, 23): []}
        obs = cote_v2.evenements(jours, "9782070000001", "bon")
        self.assertIn(("vente_probable", date(2026, 10, 23), 60.0), [(o.type, o.date, o.prix) for o in obs])

    def test_changement_de_prix_est_une_observation(self):
        jours = {date(2026, 10, 21): [ligne(60)], date(2026, 10, 22): [ligne(50)]}
        obs = cote_v2.evenements(jours, "9782070000001", "bon")
        self.assertEqual([o.prix for o in obs if o.type == "prix_demande"], [60.0, 50.0])

if __name__ == "__main__":
    unittest.main()
