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
        self.assertEqual(p.source_leslibraires("9782075123150", Faux(Rep(404)), attentes=()), (None, "indisponible"))

    def test_erreur_passagere_puis_succes(self):
        h = Faux(Rep(429), Rep(503), Rep(200, FICHE.format(dispo="InStock", etat="NewCondition")))
        self.assertEqual(p.source_leslibraires("x", h, attentes=(0, 0)), (13.5, "en_stock"))
        self.assertEqual(h.n, 3)

    def test_fonction_prix_neuf_par_isbn(self):
        h = Faux(Rep(200, FICHE.format(dispo="InStock", etat="NewCondition")))
        r = p.prix_neuf("978-2-07-514864-1", h)
        self.assertEqual((r["isbn13"], r["prix"], r["disponibilite"], r["source"]), ("9782075148641", 13.5, "en_stock", "leslibraires.fr"))

    def test_aucune_source_ne_repond(self):
        self.assertIsNone(p.prix_neuf("9782075148641", Faux(Rep(503), Rep(503)), attentes=(0,)))

    def test_lot_hebdomadaire(self):
        lignes = [{"isbn13": "1", "annee": "1987", "en_vente": ""}, {"isbn13": "2", "annee": "2014", "en_vente": ""},
                  {"isbn13": "3", "annee": "1999", "en_vente": "1"}, {"isbn13": "4", "annee": "", "annee_bnf": "2021"}, {"isbn13": "", "annee": "2024"}]
        self.assertEqual(p.a_interroger(lignes), ["2", "3", "4"])

    def test_erreur_persistante_levee(self):
        with self.assertRaises(Exception):
            p.source_leslibraires("x", Faux(Rep(503), Rep(503)), attentes=(0,))


if __name__ == "__main__":
    unittest.main()
