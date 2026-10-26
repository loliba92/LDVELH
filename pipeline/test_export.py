import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_site import aligner, annonces_cumulees, extraire_butin


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


if __name__ == "__main__":
    unittest.main()
