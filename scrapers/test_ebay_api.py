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


class TestRechercheElargie(unittest.TestCase):
    def test_les_annonces_du_titre_seul_exigent_tous_les_mots(self):
        trouve_isbn = {"itemId": "1", **item(10, "5000")}
        par_titre_ok = {"itemId": "2", "_titre_seul": True, **item(11, "5000", "Le Sorcier de la montagne de feu - Défis Fantastiques")}
        par_titre_flou = {"itemId": "3", "_titre_seul": True, **item(5, "5000", "Sorcier de la nuit - jeu de cartes")}
        l = ebay_api.agreger([trouve_isbn, par_titre_ok, par_titre_flou], "9782070583805", date(2026, 10, 11), "Le Sorcier de la montagne de feu")
        self.assertEqual([(x["etat"], x["nb_annonces"]) for x in l], [("bon", 2)])      # l'annonce floue (autres mots) est écartée

    def test_requetes_complementaires(self):
        q = ebay_api.requetes_complementaires({"livre": "Le Sorcier Majdar", "serie": "Astre d'Or", "numero": "370", "auteurs": "Ian Page ; Joe Dever"})
        self.assertIn("Le Sorcier Majdar Ian Page", q)
        self.assertIn("Le Sorcier Majdar livre dont vous êtes le héros", q)
        self.assertIn("Le Sorcier Majdar Astre d'Or 370", q)
        self.assertEqual(ebay_api.requetes_complementaires({"livre": "Rêves"}), [])          # un titre d'un seul mot : trop de bruit

    def test_union_sans_doublon(self):
        class Http(Faux):
            def get(self, url, **kw):
                q = kw["params"]["q"]
                charge = [{"itemId": "1", **item(10, "5000")}] if q.isdigit() else [{"itemId": "1", **item(10, "5000")}, {"itemId": "2", **item(12, "5000")}]
                self.charge = {"itemSummaries": charge}
                return super().get(url, **kw)
        r = ebay_api.chercher_elargi("9782070583805", "Le Sorcier de la montagne de feu", "T", {"livre": "Le Sorcier de la montagne de feu", "auteurs": "Ian"}, http=Http({}))
        self.assertEqual(sorted(i["itemId"] for i in r), ["1", "2"])
        self.assertTrue(next(i for i in r if i["itemId"] == "2").get("_titre_seul"))


class TestEtatNonPrecise(unittest.TestCase):
    def test_etat_suppose_tres_bon_quand_non_precise(self):
        self.assertEqual(ebay_api.etat_de({"conditionId": "5000"}), ("bon", False))
        self.assertEqual(ebay_api.etat_de({"conditionId": "3000"}), ("tres_bon", True))     # d'occasion sans détail
        self.assertEqual(ebay_api.etat_de({}), ("tres_bon", True))                            # aucun état dans l'annonce
        self.assertEqual(ebay_api.etat_de({"conditionId": ""}), ("tres_bon", True))
        self.assertEqual(ebay_api.etat_de({"conditionId": "4000"}), ("tres_bon", False))

    def test_neuf_et_pieces_restent_ecartes(self):
        for code in ("1000", "1500", "7000"):
            self.assertEqual(ebay_api.etat_de({"conditionId": code}), (None, False))

    def test_agreger_compte_les_annonces_sans_etat_en_tres_bon_etat(self):
        sans_etat = {"title": "Le Sorcier de la montagne de feu", "price": {"value": "14", "currency": "EUR"}}
        l = ebay_api.agreger([sans_etat, item(10, "5000"), item(30, "1000")], "9782070583805", date(2026, 10, 14))
        self.assertEqual([(x["etat"], x["nb_annonces"], x["prix_median"]) for x in l], [("bon", 1, "10.00"), ("tres_bon", 1, "14.00")])    # le neuf (30 €) reste écarté


class TestFraicheur(unittest.TestCase):
    JOUR = date(2026, 10, 14)

    def test_age(self):
        self.assertEqual(ebay_api.age_jours({"itemCreationDate": "2026-10-04T08:00:00.000Z"}, self.JOUR), 10)
        self.assertIsNone(ebay_api.age_jours({}, self.JOUR))
        self.assertIsNone(ebay_api.age_jours({"itemCreationDate": "n'importe quoi"}, self.JOUR))

    def test_les_annonces_trop_anciennes_sont_ecartees(self):
        recente = {**item(10, "5000"), "itemCreationDate": "2026-10-01T00:00:00.000Z"}
        ancienne = {**item(40, "5000"), "itemCreationDate": "2025-06-01T00:00:00.000Z"}
        sans_date = item(12, "5000")
        l = ebay_api.agreger([recente, ancienne, sans_date], "9782070583805", self.JOUR)
        self.assertEqual([(x["etat"], x["nb_annonces"], x["prix_max"]) for x in l], [("bon", 2, "12.00")])
        self.assertEqual((l[0]["nb_toutes"], l[0]["prix_median_toutes"]), (3, "12.00"))     # toutes les annonces, anciennes comprises

    def test_etat_sans_annonce_recente_pas_de_ligne(self):
        ancienne = {**item(40, "5000"), "itemCreationDate": "2025-06-01T00:00:00.000Z"}
        self.assertEqual(ebay_api.agreger([ancienne], "9782070583805", self.JOUR), [])


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
        # 11 € (état précisé) + 9 € (« d'occasion » sans détail, 3000, supposé TBE) ; neuf (1000), lot, collection et dollars écartés
        self.assertEqual([(l["etat"], l["nb_annonces"], l["prix_median"]) for l in lignes], [("bon", 1, "11.00"), ("tres_bon", 1, "9.00")])

    def test_appels_http(self):
        faux = Faux({"itemSummaries": [item(10, "5000")]})
        t = ebay_api.jeton("id", "secret", faux)
        res = ebay_api.annonces("9782070583805", t, faux)
        self.assertEqual((t, len(res)), ("T", 1))
        self.assertEqual(faux.appels[1][1]["headers"]["X-EBAY-C-MARKETPLACE-ID"], "EBAY_FR")

    def test_chercher_par_isbn_seul_sans_repli_par_le_titre(self):
        faux = Faux({"itemSummaries": [item(27, "5000")]})
        res = ebay_api.chercher("9782070335749", "La Forêt du Dragon", "T", faux)
        self.assertEqual(len(res), 1)
        self.assertEqual([c[1]["params"]["q"] for c in faux.appels], ["9782070335749"])

    def test_annee_de_parution(self):
        self.assertTrue(ebay_api.annee_compatible("La Forêt du Dragon Folio junior 1989", ("1989",)))
        self.assertFalse(ebay_api.annee_compatible("La Forêt du Dragon réédition 2005", ("1989",)))
        self.assertTrue(ebay_api.annee_compatible("La Forêt du Dragon", ("1989",)))        # pas d'année : on ne tranche pas
        self.assertTrue(ebay_api.annee_compatible("La Forêt du Dragon 2005", ()))          # année de l'édition inconnue
        lignes = ebay_api.agreger([item(10, "5000", "La Forêt du Dragon 1989"), item(40, "5000", "La Forêt du Dragon 2005")],
                                  "9782070335749", date(2026, 10, 14), "La Forêt du Dragon", ("1989",))
        self.assertEqual([(l["nb_annonces"], l["prix_median"]) for l in lignes], [(1, "10.00")])

    def test_annonce_trouvee_sous_deux_editions_du_meme_livre_est_ecartee(self):
        a, b = {**item(10, "5000"), "itemId": "A"}, {**item(12, "5000"), "itemId": "B"}
        res = ebay_api.ecarter_ambigues({"V1": [a, b], "V2": [b], "AUTRE": [a]},
                                        {"V1": "Livre X", "V2": "Livre X", "AUTRE": "Livre Y"})
        self.assertEqual([x["itemId"] for x in res["V1"]], ["A"])          # B est sous V1 et V2 : ambiguë
        self.assertEqual(res["V2"], [])
        self.assertEqual([x["itemId"] for x in res["AUTRE"]], ["A"])      # autre livre : pas de conflit

    def test_aucune_annonce(self):
        self.assertEqual(ebay_api.agreger([], "9782070583805", date(2026, 10, 11)), [])


if __name__ == "__main__":
    unittest.main()
