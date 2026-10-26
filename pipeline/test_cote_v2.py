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

    def test_les_releves_sans_colonne_port_sont_ignores(self):
        import tempfile
        d = Path(tempfile.mkdtemp())
        (d / "annonces-2026-10-24.csv").write_text("isbn13,etat,prix,titre,lien\n9782070000001,bon,10.00,t,https://x/1\n", encoding="utf-8")
        (d / "annonces-2026-10-27.csv").write_text("isbn13,etat,prix,titre,lien,port\n9782070000001,bon,14.00,t,https://x/1,4.00\n", encoding="utf-8")
        jours = cote_v2.charger_jours(d)
        self.assertEqual(sorted(jours), [date(2026, 10, 27)])


if __name__ == "__main__":
    unittest.main()
