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
        self.assertEqual(p.lire_fiche(FICHE.format(dispo="InStock", etat="NewCondition")), {"prix": 13.5, "disponibilite": "en_stock", "prix_occasion": None})

    def test_epuise_ou_occasion_est_indisponible(self):
        vide = {"prix": None, "disponibilite": "indisponible", "prix_occasion": None}
        self.assertEqual(p.lire_fiche(FICHE.format(dispo="OutOfStock", etat="NewCondition")), vide)
        self.assertEqual(p.lire_fiche("<html>rien</html>"), vide)

    def test_exemplaire_d_occasion(self):
        r = p.lire_fiche(FICHE.format(dispo="InStock", etat="UsedCondition"))
        self.assertEqual(r, {"prix": None, "disponibilite": "indisponible", "prix_occasion": 13.5, "etat_occasion": None})        # pas du neuf : prix neuf vide
        ligne = p.ligne_occasion({"isbn13": "1", "date": "2026-10-15", "prix_occasion": 3.5})
        self.assertEqual((ligne["etat"], ligne["nb_annonces"], ligne["prix_median"]), ("tres_bon", 1, "3.50"))
        self.assertIsNone(p.ligne_occasion({"isbn13": "1", "date": "2026-10-15", "prix_occasion": None}))

    def test_etat_de_l_exemplaire_lu_sur_la_fiche(self):
        # Fiche réelle (leslibraires.fr) : « Un peu abîmé » ne doit jamais devenir « très bon état »
        abime = FICHE.format(dispo="InStock", etat="UsedCondition") + "<p>État de l'exemplaire</p><span>Occasion - Etat Correct - Un peu abîmé - 0, 0</span>"
        self.assertEqual(p.lire_fiche(abime)["etat_occasion"], "convenable")
        tb = FICHE.format(dispo="InStock", etat="UsedCondition") + "<p>État de l&#39;exemplaire</p><span>Occasion - Etat Très bon - 1997</span>"
        self.assertEqual(p.lire_fiche(tb)["etat_occasion"], "tres_bon")
        bon = FICHE.format(dispo="InStock", etat="UsedCondition") + "<p>État de l'exemplaire</p><span>Occasion - Bon état</span>"
        self.assertEqual(p.lire_fiche(bon)["etat_occasion"], "bon")
        ligne = p.ligne_occasion({"isbn13": "1", "date": "2026-10-28", "prix_occasion": 4.98, "etat_occasion": "convenable"})
        self.assertEqual(ligne["etat"], "convenable")
        self.assertEqual(p.ligne_occasion({"isbn13": "1", "date": "2026-10-28", "prix_occasion": 4.98, "etat_occasion": None})["etat"], "tres_bon")

    def test_fiche_absente(self):
        self.assertEqual(p.source_leslibraires("9782075123150", Faux(Rep(404)), attentes=())["disponibilite"], "indisponible")

    def test_erreur_passagere_puis_succes(self):
        h = Faux(Rep(429), Rep(503), Rep(200, FICHE.format(dispo="InStock", etat="NewCondition")))
        self.assertEqual(p.source_leslibraires("x", h, attentes=(0, 0))["prix"], 13.5)
        self.assertEqual(h.n, 3)

    def test_fonction_prix_neuf_par_isbn(self):
        h = Faux(Rep(200, FICHE.format(dispo="InStock", etat="NewCondition")))
        r = p.prix_neuf("978-2-07-514864-1", h)
        self.assertEqual((r["isbn13"], r["prix"], r["disponibilite"], r["source"]), ("9782075148641", 13.5, "en_stock", "leslibraires.fr"))

    def test_aucune_source_ne_repond(self):
        self.assertIsNone(p.prix_neuf("9782075148641", Faux(Rep(503), Rep(503)), attentes=(0,)))

    def test_lot_hebdomadaire_toutes_les_editions(self):
        lignes = [{"isbn13": "2"}, {"isbn13": "1"}, {"isbn13": ""}, {"isbn13": "2"}]
        self.assertEqual(p.a_interroger(lignes), ["1", "2"])

    def test_erreur_persistante_levee(self):
        with self.assertRaises(Exception):
            p.source_leslibraires("x", Faux(Rep(503), Rep(503)), attentes=(0,))


class TestReleveLeger(unittest.TestCase):
    """Relevé léger (--occasion) : seulement les éditions qui ont un exemplaire d'occasion, fusionné dans les fichiers existants."""
    A, B, C = "9782070585168", "9782070333707", "9782070544035"      # A : neuf en stock, B : occasion, C : occasion

    def ecrire_sortie(self, d):
        (d / "prix_neuf.csv").write_text("isbn13,prix,disponibilite,prix_occasion,date,source\n"
                                         f"{self.A},13.5,en_stock,,2026-10-01,leslibraires.fr\n"
                                         f"{self.B},,indisponible,20.0,2026-10-01,leslibraires.fr\n"
                                         f"{self.C},,indisponible,30.0,2026-10-01,leslibraires.fr\n", encoding="utf-8")

    def test_les_isbn_a_relire_sont_ceux_qui_ont_un_exemplaire_d_occasion(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            self.ecrire_sortie(Path(t))
            self.assertEqual(p.isbn_avec_occasion(Path(t) / "prix_neuf.csv"), sorted([self.B, self.C]))
            self.assertEqual(p.isbn_avec_occasion(Path(t) / "absent.csv"), [])

    def test_fusion_remplace_garde_et_ajoute(self):
        anciennes = [{"isbn13": "1", "x": "a"}, {"isbn13": "2", "x": "b"}]
        nouvelles = [{"isbn13": "2", "x": "B"}, {"isbn13": "3", "x": "c"}]
        self.assertEqual(p.fusionner(anciennes, nouvelles), [{"isbn13": "1", "x": "a"}, {"isbn13": "2", "x": "B"}, {"isbn13": "3", "x": "c"}])

    def test_le_releve_leger_ne_lit_que_ces_fiches_et_garde_le_reste(self):
        import tempfile
        lues = []
        def faux(isbn):
            lues.append(isbn)
            return {"isbn13": isbn, "prix": None, "disponibilite": "indisponible", "prix_occasion": 25.0 if isbn == self.B else None, "source": "leslibraires.fr", "date": "2026-10-24"}
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); self.ecrire_sortie(t)
            sauve = (p.SORTIE, p.OCCASION, p.prix_neuf, p.time.sleep, sys.argv)
            try:
                p.SORTIE, p.OCCASION, p.prix_neuf, p.time.sleep, sys.argv = t / "prix_neuf.csv", t / "occ", faux, (lambda s: None), ["prix_neuf.py", "--occasion"]
                p.main()
            finally:
                p.SORTIE, p.OCCASION, p.prix_neuf, p.time.sleep, sys.argv = sauve
            self.assertEqual(sorted(lues), sorted([self.B, self.C]))                    # A (neuf) n'est pas relue
            lignes = {r["isbn13"]: r for r in p.lire_csv(t / "prix_neuf.csv")}
            self.assertEqual((lignes[self.A]["date"], lignes[self.A]["prix"]), ("2026-10-01", "13.5"))         # intacte
            self.assertEqual((lignes[self.B]["date"], lignes[self.B]["prix_occasion"]), ("2026-10-24", "25.0"))  # relue
            self.assertEqual(lignes[self.C]["prix_occasion"], "")                                              # exemplaire vendu : plus d'occasion
            fichier = list((t / "occ").glob("libraires-*.csv"))
            self.assertEqual(len(fichier), 1)
            self.assertEqual([r["isbn13"] for r in p.lire_csv(fichier[0])], [self.B])


if __name__ == "__main__":
    unittest.main()
