import sys, unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ebay_api


def item(prix, cond, titre="Le Sorcier de la montagne de feu", devise="EUR"):
    return {"title": titre, "conditionId": cond, "price": {"value": str(prix), "currency": devise}}


def avec_port(prix, port):
    return dict(item(prix, "3000"), shippingOptions=[{"shippingCostType": "FIXED", "shippingCost": {"value": str(port), "currency": "EUR"}}])


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

    def test_une_annonce_du_titre_seul_doit_parler_d_un_livre_jeu(self):
        ed = {"serie": "Loup Solitaire", "auteurs": "Joe Dever"}
        livre = {"itemId": "1", "_titre_seul": True, **item(20, "5000", "LDVELH La Tour De Cristal Loup Solitaire n° 17")}
        auteur = {"itemId": "2", "_titre_seul": True, **item(8, "5000", "La Tour de Cristal, Dever, Joe")}
        inverse = {"itemId": "5", "_titre_seul": True, **item(9, "5000", "La Tour de Cristal, Dever, Joe")}
        carte = {"itemId": "3", "_titre_seul": True, **item(548, "5000", "Carte Pokémon La Tour de Cristal : Entei, promotion du 10e film")}
        dvd = {"itemId": "4", "_titre_seul": True, **item(817, "5000", "DVD Pokemon le film : Empereur de la Tour de Cristal")}
        l = ebay_api.agreger([livre, auteur, inverse, carte, dvd], "9782070512690", date(2026, 10, 21), "La Tour de Cristal", None, ed)
        self.assertEqual([(x["etat"], x["nb_annonces"], x["prix_max"]) for x in l], [("bon", 3, "20.00")])

    def test_les_prix_aberrants_sont_ecartes_quand_il_y_a_assez_d_annonces(self):
        items = [{"itemId": str(i), **item(p, "5000", "Le Sorcier de la montagne de feu - Défis Fantastiques")} for i, p in enumerate((18, 20, 22, 21, 250, 3))]
        l = ebay_api.agreger(items, "9782070583805", date(2026, 10, 21), "Le Sorcier de la montagne de feu")
        self.assertEqual([(x["nb_annonces"], x["prix_min"], x["prix_max"]) for x in l], [(4, "18.00", "22.00")])

    def test_le_fichier_des_annonces_dit_si_l_etat_est_precise_ou_suppose(self):
        titre = "Le Sorcier de la montagne de feu - Défis Fantastiques"
        items = [{"itemId": "1", "itemWebUrl": "http://a", **item(20, "5000", titre)},       # bon état indiqué
                 {"itemId": "2", "itemWebUrl": "http://b", **item(21, "3000", titre)},       # « d'occasion » sans précision : très bon état supposé
                 {"itemId": "3", "itemWebUrl": "http://c", **item(22, "", titre)}]           # aucun état : supposé aussi
        lignes = ebay_api.lignes_annonces(items, "9782070583805", date(2026, 10, 21), "Le Sorcier de la montagne de feu")
        self.assertEqual({l["lien"]: (l["etat"], l["etat_suppose"]) for l in lignes},
                         {"http://a": ("bon", 0), "http://b": ("tres_bon", 1), "http://c": ("tres_bon", 1)})
        self.assertIn("etat_suppose", ebay_api.CHAMPS_ANNONCES)

    def test_deux_annonces_ne_suffisent_pas_pour_juger(self):
        items = [{"itemId": str(i), **item(p, "5000", "Le Sorcier de la montagne de feu - Défis Fantastiques")} for i, p in enumerate((20, 200))]
        l = ebay_api.agreger(items, "9782070583805", date(2026, 10, 21), "Le Sorcier de la montagne de feu")
        self.assertEqual(l[0]["nb_annonces"], 2)

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


class TestAmbiguites(unittest.TestCase):
    def test_une_annonce_trouvee_par_l_isbn_reste_a_son_edition(self):
        a = {"itemId": "1", **item(10, "5000")}
        par = {"A": [a], "B": [{**a, "_titre_seul": True}]}
        r = ebay_api.ecarter_ambigues(par, {"A": "livre", "B": "livre"})
        self.assertEqual((len(r["A"]), len(r["B"])), (1, 0))          # gardée sous A (ISBN), retirée sous B (titre)

    def test_deux_isbn_citent_la_meme_annonce(self):
        a = {"itemId": "1", **item(10, "5000")}
        r = ebay_api.ecarter_ambigues({"A": [a], "B": [a]}, {"A": "livre", "B": "livre"})
        self.assertEqual((len(r["A"]), len(r["B"])), (0, 0))

    def test_annonce_du_titre_seul_gardee_si_une_seule_edition(self):
        a = {"itemId": "9", "_titre_seul": True, **item(10, "5000")}
        r = ebay_api.ecarter_ambigues({"A": [a], "B": []}, {"A": "livre", "B": "livre"})
        self.assertEqual(len(r["A"]), 1)
        r2 = ebay_api.ecarter_ambigues({"A": [a], "B": [a]}, {"A": "livre", "B": "livre"})
        self.assertEqual((len(r2["A"]), len(r2["B"])), (0, 0))        # vue par deux éditions : ambiguë


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


class TestRequetesLdvelh(unittest.TestCase):
    def test_titre_plus_ldvelh_est_une_requete(self):
        ed = {"livre": "Les Terres de Légende", "serie": "Terres de Légende", "numero": "577", "auteurs": "Joe Dever"}
        self.assertIn("Les Terres de Légende ldvelh", ebay_api.requetes_complementaires(ed))

    def test_orthographe_sans_s_est_une_requete(self):
        ed = {"livre": "Les Terres de Légende"}
        self.assertIn("Les Terres de Légende livre dont vous êtes le héro", ebay_api.requetes_complementaires(ed))

    def test_titre_plus_isbn_est_une_requete(self):
        ed = {"livre": "Les Terres de Légende", "isbn13": "9782070335770"}
        self.assertIn("Les Terres de Légende 9782070335770", ebay_api.requetes_complementaires(ed))


class TestPortDansLesAnnonces(unittest.TestCase):
    def test_colonne_port_et_prix_total(self):
        from datetime import date as _d
        it = dict(avec_port(10, 4.5), itemWebUrl="https://www.ebay.fr/itm/1", itemId="1")
        lignes = ebay_api.lignes_annonces([it], "9782070000001", _d(2026, 10, 26))
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]["prix"], "14.50")
        self.assertEqual(lignes[0]["port"], "4.50")

    def test_port_inconnu_reste_vide(self):
        from datetime import date as _d
        it = dict(item(10, "3000"), itemWebUrl="https://www.ebay.fr/itm/2", itemId="2")
        lignes = ebay_api.lignes_annonces([it], "9782070000001", _d(2026, 10, 26))
        self.assertEqual(lignes[0]["port"], "")


class TestFraisPort(unittest.TestCase):
    def test_frais_lus_et_ajoutes_au_prix(self):
        self.assertEqual(ebay_api.frais_port(avec_port(10, 4.5)), 4.5)
        self.assertEqual(ebay_api.frais_port(item(10, "3000")), None)
        self.assertEqual(ebay_api.frais_port(dict(item(10, "3000"), shippingOptions=[{"shippingCost": {"value": "0.00", "currency": "EUR"}}])), 0.0)

    def test_le_moins_cher_des_modes_de_livraison(self):
        it = dict(item(10, "3000"), shippingOptions=[{"shippingCost": {"value": "6.90", "currency": "EUR"}}, {"shippingCost": {"value": "3.50", "currency": "EUR"}}])
        self.assertEqual(ebay_api.frais_port(it), 3.5)

    def test_retenues_donne_le_prix_port_inclus(self):
        jour = date(2026, 10, 26)
        sortie = ebay_api.retenues([avec_port(10, 4.5)], jour)
        self.assertEqual(len(sortie), 1)
        self.assertAlmostEqual(sortie[0][2], 14.5)


if __name__ == "__main__":
    unittest.main()
