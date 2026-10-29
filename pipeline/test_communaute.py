import unittest

from communaute import appliquer, adresse_valide


class TestCommunaute(unittest.TestCase):
    def test_ajout_puis_tri(self):
        liste = appliquer([], "ajout ; Zeta ; https://z.example ; un site | ajout ; Alpha ; https://a.example ; une chaîne")
        self.assertEqual([x["nom"] for x in liste], ["Alpha", "Zeta"])

    def test_adresse_deja_presente_remplacee(self):
        liste = appliquer([], "ajout ; Alpha ; https://a.example ; ancien")
        liste = appliquer(liste, "ajout ; Alpha bis ; https://a.example ; nouveau")
        self.assertEqual(len(liste), 1)
        self.assertEqual(liste[0]["description"], "nouveau")

    def test_retrait(self):
        liste = appliquer([], "ajout ; Alpha ; https://a.example ; x | ajout ; Beta ; https://b.example ; y")
        liste = appliquer(liste, "retrait ; https://a.example")
        self.assertEqual([x["nom"] for x in liste], ["Beta"])

    def test_refus_http_et_adresse_vide(self):
        self.assertFalse(adresse_valide("http://a.example"))
        self.assertFalse(adresse_valide("https://"))
        with self.assertRaises(ValueError):
            appliquer([], "ajout ; Alpha ; http://a.example ; x")

    def test_refus_commande_inconnue_et_longueurs(self):
        with self.assertRaises(ValueError):
            appliquer([], "supprime ; https://a.example")
        with self.assertRaises(ValueError):
            appliquer([], "ajout ; " + "n" * 61 + " ; https://a.example ; x")
        with self.assertRaises(ValueError):
            appliquer([], "ajout ; Alpha ; https://a.example ; " + "d" * 301)


if __name__ == "__main__":
    unittest.main()
