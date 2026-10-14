import sys, unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ebay_api


def item(prix, cond, titre="Le Sorcier de la montagne de feu", devise="EUR"):
    return {"title": titre, "conditionId": cond, "price": {"value": str(prix), "currency": devise}}


class Faux:
    def __init__(self, charge): self.charge = charge; self.appels = []
    def post(self, url, **kw): self.appels.append(("post", url)); return self._rep({"access_token": "T"})
    def get(self, url, **kw): self.appels.append(("get", kw)); return self._rep(self.charge)
    def _rep(self, data):
        class R:
            def raise_for_status(s): pass
            def json(s): return data
        return R()


class TestConcordance(unittest.TestCase):
    def test_concorde(self):
        self.assertTrue(ebay_api.concorde("LE SORCIER de la montagne de feu - Défis Fantastiques - Folio Junior", "Le Sorcier de la montagne de feu"))
        self.assertFalse(ebay_api.concorde("Harry Potter à l'école des sorciers", "Le Sorcier de la montagne de feu"))
        self.assertTrue(ebay_api.concorde("n'importe quoi", ""))      # rien à comparer : pas de filtre

    def test_agreger_ecarte_un_autre_livre(self):
        items = [item(10, "5000"), item(12, "5000", "Harry Potter à l'école des sorciers")]
        l = ebay_api.agreger(items, "9782070583805", date(2026, 10, 11), "Le Sorcier de la montagne de feu")
        self.assertEqual([(x["etat"], x["nb_annonces"]) for x in l], [("bon", 1)])


class Refus:
    def post(self, url, **kw):
        class R:
            status_code = 401
            text = '{"error":"invalid_client","error_description":"client authentication failed"}'
        return R()


class TestEbay(unittest.TestCase):
    def test_refus_des_cles_est_explique(self):
        with self.assertRaises(RuntimeError) as c:
            ebay_api.jeton("id", "secret", Refus())
        self.assertIn("invalid_client", str(c.exception))
        self.assertIn("PRD", str(c.exception))
        self.assertNotIn("secret", str(c.exception).replace("EBAY_CLIENT_SECRET", ""))

    def test_agregation_par_etat(self):
        items = [item(10, "5000"), item(12, "5000"), item(20, "5000"), item(30, "4000"), item(8, "6000")]
        lignes = ebay_api.agreger(items, "9782070583805", date(2026, 10, 11))
        par = {l["etat"]: l for l in lignes}
        self.assertEqual((par["bon"]["nb_annonces"], par["bon"]["prix_median"], par["bon"]["prix_min"], par["bon"]["prix_max"]),
                         (3, "12.00", "10.00", "20.00"))
        self.assertEqual(set(par), {"bon", "tres_bon", "convenable"})

    def test_ecarte_lots_devises_et_etats_inconnus(self):
        items = [item(50, "5000", "Lot de 10 livres dont vous êtes le héros"), item(9, "5000", devise="USD"),
                 item(9, "1000"), item(9, "3000"), item(15, "5000", "Collection complète"), item(11, "5000")]
        lignes = ebay_api.agreger(items, "9782070583805", date(2026, 10, 11))
        self.assertEqual([(l["etat"], l["nb_annonces"], l["prix_median"]) for l in lignes], [("bon", 1, "11.00")])

    def test_appels_http(self):
        faux = Faux({"itemSummaries": [item(10, "5000")]})
        t = ebay_api.jeton("id", "secret", faux)
        res = ebay_api.annonces("9782070583805", t, faux)
        self.assertEqual((t, len(res)), ("T", 1))
        self.assertEqual(faux.appels[1][1]["headers"]["X-EBAY-C-MARKETPLACE-ID"], "EBAY_FR")

    def test_aucune_annonce(self):
        self.assertEqual(ebay_api.agreger([], "9782070583805", date(2026, 10, 11)), [])


if __name__ == "__main__":
    unittest.main()
