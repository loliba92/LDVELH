import unittest

from communaute import adresse_valide, appliquer, image_de_page


def sans_image(adresse):
    return ""


class TestCommunaute(unittest.TestCase):
    def test_ajout_puis_tri(self):
        liste = appliquer([], "ajout ; Zeta ; https://z.example ; un site | ajout ; Alpha ; https://a.example ; une chaîne", sans_image)
        self.assertEqual([x["nom"] for x in liste], ["Alpha", "Zeta"])

    def test_adresse_deja_presente_remplacee(self):
        liste = appliquer([], "ajout ; Alpha ; https://a.example ; ancien", sans_image)
        liste = appliquer(liste, "ajout ; Alpha bis ; https://a.example ; nouveau", sans_image)
        self.assertEqual(len(liste), 1)
        self.assertEqual(liste[0]["description"], "nouveau")

    def test_retrait(self):
        liste = appliquer([], "ajout ; Alpha ; https://a.example ; x | ajout ; Beta ; https://b.example ; y", sans_image)
        liste = appliquer(liste, "retrait ; https://a.example", sans_image)
        self.assertEqual([x["nom"] for x in liste], ["Beta"])

    def test_image_copiee_dans_l_entree(self):
        liste = appliquer([], "ajout ; Alpha ; https://a.example ; x", lambda a: "data/communaute/abc.jpg")
        self.assertEqual(liste[0]["image"], "data/communaute/abc.jpg")

    def test_refus_http_et_adresse_vide(self):
        self.assertFalse(adresse_valide("http://a.example"))
        self.assertFalse(adresse_valide("https://"))
        with self.assertRaises(ValueError):
            appliquer([], "ajout ; Alpha ; http://a.example ; x", sans_image)

    def test_refus_commande_inconnue_et_longueurs(self):
        with self.assertRaises(ValueError):
            appliquer([], "supprime ; https://a.example", sans_image)
        with self.assertRaises(ValueError):
            appliquer([], "ajout ; " + "n" * 61 + " ; https://a.example ; x", sans_image)
        with self.assertRaises(ValueError):
            appliquer([], "ajout ; Alpha ; https://a.example ; " + "d" * 301, sans_image)

    def test_image_og_relative_et_absente(self):
        page = '<head><meta property="og:image" content="/img/couv.jpg"><meta property="og:title" content="x"></head>'
        self.assertEqual(image_de_page(page, "https://site.example/accueil"), "https://site.example/img/couv.jpg")
        self.assertEqual(image_de_page('<meta name="twitter:image" content="https://cdn.example/a.png">', "https://s.example"), "https://cdn.example/a.png")
        self.assertIsNone(image_de_page("<p>rien</p>", "https://s.example"))


if __name__ == "__main__":
    unittest.main()
