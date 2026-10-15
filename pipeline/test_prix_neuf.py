import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prix_neuf as p

FICHE = '''<meta itemprop="price" content="13.50"/><meta itemprop="priceCurrency" content="EUR"/>
<link itemprop="availability" href="https://schema.org/{dispo}"/><link itemprop="itemCondition" href="https://schema.org/{etat}"/>'''


class Rep:
    def __init__(self, code, texte=""): self.status_code, self.text = code, texte
    def raise_for_status(self): pass


class Faux:
    def __init__(self, *reponses): self.reponses, self.n = list(reponses), 0
    def get(self, *a, **k): self.n += 1; return self.reponses.pop(0)


class TestPrixNeuf(unittest.TestCase):
    def test_en_stock_neuf(self):
        self.assertEqual(p.lire_fiche(FICHE.format(dispo="InStock", etat="NewCondition")), (13.5, "en_stock"))

    def test_epuise_ou_occasion_est_indisponible(self):
        self.assertEqual(p.lire_fiche(FICHE.format(dispo="OutOfStock", etat="NewCondition"))[1], "indisponible")
        self.assertEqual(p.lire_fiche(FICHE.format(dispo="InStock", etat="UsedCondition"))[1], "indisponible")
        self.assertEqual(p.lire_fiche("<html>rien</html>"), (None, "indisponible"))

    def test_fiche_absente(self):
        self.assertEqual(p.interroger("9782075123150", Faux(Rep(404)), attentes=()), (None, "indisponible"))

    def test_erreur_passagere_puis_succes(self):
        h = Faux(Rep(429), Rep(503), Rep(200, FICHE.format(dispo="InStock", etat="NewCondition")))
        self.assertEqual(p.interroger("x", h, attentes=(0, 0)), (13.5, "en_stock"))
        self.assertEqual(h.n, 3)

    def test_erreur_persistante_levee(self):
        with self.assertRaises(Exception):
            p.interroger("x", Faux(Rep(503), Rep(503)), attentes=(0,))


if __name__ == "__main__":
    unittest.main()
