import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_site import aligner, annonces_cumulees, extraire_butin, calculer_offre, premieres_vues, fabriquer_minis


def e(prix):
    return {"prix": prix, "source": "archives"}


def a(prix):
    return {"prix": prix, "source": "actuel"}


class TestAligner(unittest.TestCase):
    def test_tbe_sous_le_be_est_remonte(self):
        p = {"convenable": e(10), "bon": e(15), "tres_bon": e(12)}
        self.assertEqual(aligner(p), 1)
        self.assertEqual(p["tres_bon"]["prix"], 18)                    # bon état + 20 %
        self.assertTrue(p["tres_bon"]["ajuste"])

    def test_tbe_sous_le_c_et_le_be(self):
        p = {"convenable": e(39.26), "bon": e(45.15), "tres_bon": e(29.38)}
        aligner(p)
        self.assertEqual((p["convenable"]["prix"], p["bon"]["prix"], p["tres_bon"]["prix"]), (39.26, 45.15, 54.18))

    def test_be_sous_le_c_est_remonte(self):
        p = {"convenable": e(20), "bon": e(18), "tres_bon": e(25)}
        aligner(p)
        self.assertEqual((p["bon"]["prix"], p["tres_bon"]["prix"]), (24, 25))        # convenable + 20 %, le très bon état reste au-dessus

    def test_prix_egaux_et_ordre_normal_inchanges(self):
        for p in ({"convenable": e(10), "bon": e(10), "tres_bon": e(10)}, {"convenable": e(5), "bon": e(8), "tres_bon": e(12)}):
            self.assertEqual(aligner(p), 0)
            self.assertFalse(any("ajuste" in v for v in p.values()))

    def test_archive_gonflee_ne_tire_pas_un_prix_actuel(self):
        """BE d'archive à 50, TBE actuel à 7,5 : c'est le BE d'archive qu'on ramène, pas le TBE actuel qu'on remonte."""
        p = {"convenable": e(5), "bon": e(50), "tres_bon": a(7.5)}
        self.assertEqual(aligner(p), 1)
        self.assertEqual((p["bon"]["prix"], p["tres_bon"]["prix"]), (6.25, 7.5))      # l'archive est ramenée à TBE ÷ 1,2
        self.assertTrue(p["bon"]["ajuste"])
        self.assertNotIn("ajuste", p["tres_bon"])

    def test_cascade_vers_le_convenable(self):
        p = {"convenable": e(40), "bon": e(50), "tres_bon": a(7.5)}
        aligner(p)
        self.assertEqual((p["convenable"]["prix"], p["bon"]["prix"], p["tres_bon"]["prix"]), (5.21, 6.25, 7.5))

    def test_etat_inferieur_actuel_remonte_l_etat_superieur(self):
        p = {"bon": a(30), "tres_bon": e(20)}
        aligner(p)
        self.assertEqual(p["tres_bon"]["prix"], 36)

    def test_etat_manquant_ignore(self):
        p = {"convenable": e(10), "tres_bon": e(8)}
        self.assertEqual(aligner(p), 1)
        self.assertEqual(p["tres_bon"]["prix"], 12)
        self.assertEqual(aligner({"bon": e(9)}), 0)

    def test_ecart_reglable(self):
        p = {"bon": e(15), "tres_bon": e(12)}
        aligner(p, 1.1)
        self.assertEqual(p["tres_bon"]["prix"], 16.5)


class TestAnnoncesCumulees(unittest.TestCase):
    def fichiers(self, **jours):
        d = Path(tempfile.mkdtemp())
        for jour, lignes in jours.items():
            f = d / f"annonces-{jour.replace('_', '-')}.csv"
            f.write_text("isbn13,etat,prix,titre,lien,age_jours,trouvee_par\n" + "".join(f"{l}\n" for l in lignes), encoding="utf-8")
        return sorted(d.glob("annonces-*.csv"))

    def test_une_annonce_retiree_reste_avec_sa_derniere_date(self):
        f = self.fichiers(**{"2026_10_21": ["111,bon,10.00,Livre A,http://a,3,isbn", "111,bon,12.00,Livre B,http://b,3,isbn"],
                             "2026_10_22": ["111,bon,11.00,Livre A,http://a,4,isbn"]})
        r = annonces_cumulees(f)["111"]["bon"]
        self.assertEqual(sorted(r), [[11.0, "Livre A", "http://a", "isbn", "2026-10-22", None], [12.0, "Livre B", "http://b", "isbn", "2026-10-21", None]])

    def test_la_version_la_plus_recente_l_emporte_et_pas_de_doublon(self):
        f = self.fichiers(**{"2026_10_21": ["111,bon,10.00,Ancien titre,http://a,3,isbn"],
                             "2026_10_22": ["111,tres_bon,20.00,Nouveau titre,http://a,4,titre"]})
        r = annonces_cumulees(f)["111"]
        self.assertNotIn("bon", r)
        self.assertEqual(r["tres_bon"], [[20.0, "Nouveau titre", "http://a", "titre", "2026-10-22", None]])

    def test_l_etat_suppose_est_transporte(self):
        d = Path(tempfile.mkdtemp())
        f = d / "annonces-2026-10-22.csv"
        f.write_text("isbn13,etat,prix,titre,lien,age_jours,trouvee_par,etat_suppose\n"
                     "111,bon,10.00,Etat indique,http://a,3,isbn,0\n111,tres_bon,12.00,Etat suppose,http://b,3,isbn,1\n", encoding="utf-8")
        r = annonces_cumulees([f])["111"]
        self.assertEqual((r["bon"][0][5], r["tres_bon"][0][5]), (0, 1))

    def test_le_prix_du_relevé_a_port_est_deja_le_prix_livre(self):
        # Depuis le relevé à colonne « port », le prix est déjà le total : on ne rajoute pas les frais une seconde fois
        d = Path(tempfile.mkdtemp())
        f = d / "annonces-2026-10-22.csv"
        f.write_text("isbn13,etat,prix,titre,lien,age_jours,trouvee_par,etat_suppose,port\n"
                     "111,bon,13.58,Avec port,http://a,3,isbn,0,2.78\n", encoding="utf-8")
        self.assertEqual(annonces_cumulees([f])["111"]["bon"][0][0], 13.58)

    def test_une_tres_vieille_annonce_est_ecartee(self):
        f = self.fichiers(**{"2026_01_01": ["111,bon,10.00,Vieille,http://v,3,isbn"], "2026_10_22": ["222,bon,5.00,Recente,http://r,1,isbn"]})
        r = annonces_cumulees(f)
        self.assertNotIn("111", r)
        self.assertIn("222", r)
        self.assertEqual(annonces_cumulees([]), {})


class TestButin(unittest.TestCase):
    def test_le_butin_ne_garde_que_les_bonnes_affaires(self):
        ann = {"111": {"bon": [[10.0, "t", "u1", "isbn", "2026-10-25", None], [30.0, "t", "u2", "isbn", "2026-10-25", None], [28.0, "t", "u3", "isbn", "2026-10-25", None]],
                       "tres_bon": [[2.0, "t", "u4", "isbn", "2026-10-25", None]]},
               "222": {"bon": [[5.0, "t", "u5", "isbn", "2026-10-25", None]]}}
        revue = [{"isbn": "111", "etat": "bon", "publie": 40.0}, {"isbn": "111", "etat": "tres_bon", "publie": 4.0}, {"isbn": "222", "etat": "bon", "publie": None}]
        b = extraire_butin(ann, revue)
        self.assertEqual([x[2] for x in b["111"]["bon"]], ["u1"])      # 10 € ≤ 50 % de 40 € ; 28 € et 30 € ne sont pas des bonnes affaires
        self.assertNotIn("tres_bon", b["111"])                          # 2 € sur 4 € : moins de 3 € d'économie
        self.assertNotIn("222", b)                                      # pas de prix publié : pas de repère


class TestAnnoncesFdp(unittest.TestCase):
    def test_le_prix_affiche_ajoute_la_colonne_fdp(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "annonces-vinted-2026-10-27.csv"
            f.write_text("isbn13,etat,prix,titre,lien,age_jours,trouvee_par,fdp\n111,bon,10.00,A,https://www.vinted.fr/items/1-a,1,vinted,4.20\n"
                         "111,bon,12.00,B,https://www.leboncoin.fr/ad/livres/2,1,leboncoin,\n"
                         "111,bon,10.00,C,https://www.vinted.fr/items/3-c,1,vinted,\n", encoding="utf-8")        # Vinted reçue sans fdp : frais par défaut
            liste = annonces_cumulees([f])["111"]["bon"]
        self.assertEqual({a[2]: a[0] for a in liste}, {"https://www.vinted.fr/items/1-a": 14.2, "https://www.leboncoin.fr/ad/livres/2": 16.3,
                                                       "https://www.vinted.fr/items/3-c": 14.2})            # Leboncoin sans fdp : même prix livré que Vinted


class TestButinVinted(unittest.TestCase):
    def test_prix_livre_vinted(self):
        from prix_neuf import prix_livre_vinted
        self.assertEqual(prix_livre_vinted(10.0), 14.2)        # 10 + 0,70 + 5 % + 3 € de port
        self.assertEqual(prix_livre_vinted(2.6), 6.43)         # frais Vinted vus au paiement : 0,83 €

    def test_le_prix_livre_compte_dans_la_regle_du_butin(self):
        from prix_neuf import prix_livre_vinted
        revue = [{"isbn": "111", "etat": "bon", "publie": 40.0}]
        # 50 % de 40 € = 20 € : une annonce à 12 € (livrée 16,30 €) est retenue ; à 16 € (livrée 20,50 €) elle est écartée
        annonces = {"111": {"bon": [[prix_livre_vinted(12.0), "a", "https://www.vinted.fr/items/1-a", "vinted", "2026-10-27", None],
                                    [prix_livre_vinted(16.0), "b", "https://www.vinted.fr/items/2-b", "vinted", "2026-10-27", None]]}}
        butin = extraire_butin(annonces, revue)
        self.assertEqual([a[1] for a in butin["111"]["bon"]], ["a"])


class TestOffre(unittest.TestCase):
    def test_offre_compte_les_annonces_en_ligne_par_source(self):
        ann = {"111": {"bon": [[10, "a", "u1", "isbn", "2026-10-26", None], [12, "b", "u2", "titre", "2026-10-26", None],
                               [11, "c", "u3", "isbn", "2026-10-20", None],            # eBay non revue au dernier relevé : pas comptée
                               [9, "d", "u4", "leboncoin", "2026-10-27", None],
                               [8, "d2", "u8", "leboncoin", "2026-10-24", None],           # Leboncoin plus ancienne que le dernier relevé : le bot ne revoit que les plus récentes, elle reste en ligne
                               [14, "v", "u9", "vinted", "2026-10-22", None],              # Vinted : même règle que Leboncoin, en ligne jusqu'à preuve du contraire
                               [90, "Lot de 6 livres · e", "u5", "leboncoin", "2026-10-27", None]],      # un lot n'est pas l'offre d'un livre
                       "tres_bon": [[4, "f", "u6", "librairie", None, 1]]},
               "222": {"bon": [[5, "g", "u7", "isbn", "2026-10-19", None]]}}
        o = calculer_offre(ann, {"111": [10, 30, 50]}, "2026-10-26", "2026-10-27")
        self.assertEqual(o["111"], {"ebay": 2, "lbc": 2, "vin": 1, "lib": 1, "age": 30})
        self.assertNotIn("222", o)                                     # aucune annonce en ligne : pas de ligne (aucune offre)



class TestPremieresVues(unittest.TestCase):
    def ann(self, *liens):
        return {"978": {"bon": [[5.0, "t", l, o, "2026-10-27", 1] for l, o in liens]}}

    def test_premier_passage_prend_la_date_sans_heure(self):
        r = premieres_vues(self.ann(("https://a", "leboncoin")), None, "2026-10-27T15:30Z")
        self.assertEqual(r, {"https://a": "2026-10-27"})

    def test_annonce_connue_garde_sa_premiere_apparition(self):
        r = premieres_vues(self.ann(("https://a", "leboncoin")), {"https://a": "2026-10-20T08:00Z"}, "2026-10-27T15:30Z")
        self.assertEqual(r["https://a"], "2026-10-20T08:00Z")

    def test_annonce_nouvelle_recoit_date_et_heure(self):
        r = premieres_vues(self.ann(("https://a", "leboncoin"), ("https://b", "isbn")), {"https://a": "2026-10-27"}, "2026-10-27T15:30Z")
        self.assertEqual(r["https://a"], "2026-10-27")
        self.assertEqual(r["https://b"], "2026-10-27T15:30Z")

    def test_historique_donne_l_heure_aux_annonces_connues_par_leur_date(self):
        hist = {"https://a": "2026-10-27T13:30Z", "https://b": "2026-10-20T08:00Z", "https://c": "2026-10-29T09:00Z"}
        ann = self.ann(("https://a", "leboncoin"), ("https://b", "isbn"), ("https://c", "leboncoin"))
        r = premieres_vues(ann, {"https://a": "2026-10-27", "https://b": "2026-10-27", "https://c": "2026-10-27"}, "2026-10-28T10:00Z", hist)
        self.assertEqual(r["https://a"], "2026-10-27T13:30Z")                  # même jour : heure retrouvée
        self.assertEqual(r["https://b"], "2026-10-20T08:00Z")                  # plus ancienne : première apparition réelle
        self.assertEqual(r["https://c"], "2026-10-27")                         # historique postérieur à la date connue : incohérent, ignoré
        r2 = premieres_vues(self.ann(("https://a", "leboncoin")), None, "2026-10-28T10:00Z", hist)
        self.assertEqual(r2["https://a"], "2026-10-27T13:30Z")                 # premier passage : l'historique prime sur la simple date
        r3 = premieres_vues(self.ann(("https://a", "leboncoin")), {"https://a": "2026-10-27T15:00Z"}, "2026-10-28T10:00Z", hist)
        self.assertEqual(r3["https://a"], "2026-10-27T15:00Z")                 # une heure déjà connue n'est pas remplacée

    def test_librairie_sans_heure_et_annonce_disparue_oubliee(self):
        r = premieres_vues(self.ann(("https://l", "librairie")), {"https://vieux": "2026-10-01T10:00Z"}, "2026-10-27T15:30Z")
        self.assertEqual(r, {"https://l": "2026-10-27"})



class TestMinis(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.dossier = Path(tempfile.mkdtemp())
        (self.dossier / "small").mkdir()
        Image.new("RGB", (320, 480), (200, 30, 30)).save(self.dossier / "small" / "111.webp", "WEBP")
        self.Image = Image

    def test_miniature_creee_puis_laissee_telle_quelle(self):
        self.assertEqual(fabriquer_minis(self.dossier), 1)
        mini = self.dossier / "mini" / "111.webp"
        self.assertEqual(self.Image.open(mini).size, (160, 240))
        avant = mini.read_bytes()
        self.assertEqual(fabriquer_minis(self.dossier), 0)                     # jaquette inchangée : rien n'est réécrit
        self.assertEqual(mini.read_bytes(), avant)

    def test_miniature_refaite_si_la_jaquette_change_et_supprimee_si_elle_disparait(self):
        fabriquer_minis(self.dossier)
        self.Image.new("RGB", (320, 480), (30, 200, 30)).save(self.dossier / "small" / "111.webp", "WEBP")
        self.assertEqual(fabriquer_minis(self.dossier), 1)
        (self.dossier / "small" / "111.webp").unlink()
        fabriquer_minis(self.dossier)
        self.assertFalse((self.dossier / "mini" / "111.webp").exists())


if __name__ == "__main__":
    unittest.main()
