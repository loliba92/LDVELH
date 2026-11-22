import unittest
import xml.etree.ElementTree as ET

from datetime import date

from flux_nouvelles import construire, date_rss, ajouter_editions, editions_mensuelles, nouvelles

LISTE = [
    {"nom": "Lien extérieur", "adresse": "https://autre.example/", "description": "sans date", "image": ""},
    {"nom": "Ancienne", "adresse": "https://lacoteduheros.fr/a.html", "description": "A & B", "image": "", "date": "2026-11-01"},
    {"nom": "Récente", "adresse": "https://lacoteduheros.fr/b.html", "description": "texte", "image": "data/communaute/sorcier.webp", "date": "2026-11-05"},
]


class TestFlux(unittest.TestCase):
    def test_seules_les_entrees_datees_les_plus_recentes_d_abord(self):
        self.assertEqual([x["nom"] for x in nouvelles(LISTE)], ["Récente", "Ancienne"])

    def test_flux_valide_avec_titre_texte_lien_date_image(self):
        racine = ET.fromstring(construire(LISTE))
        items = racine.findall("./channel/item")
        self.assertEqual(len(items), 2)
        premier = items[0]
        self.assertEqual(premier.findtext("title"), "Récente")
        self.assertEqual(premier.findtext("link"), "https://lacoteduheros.fr/b.html")
        self.assertEqual(premier.findtext("pubDate"), date_rss("2026-11-05"))
        self.assertEqual(premier.find("enclosure").get("url"), "https://lacoteduheros.fr/data/communaute/sorcier.webp")
        self.assertEqual(items[1].findtext("description"), "A & B")
        self.assertIsNone(items[1].find("enclosure"))

    def test_texte_flux_remplace_la_description_dans_le_flux_seulement(self):
        liste = [{"nom": "Longue", "adresse": "https://lacoteduheros.fr/c.html", "description": "courte", "texte_flux": "Texte long.\n\nSuite.", "image": "", "date": "2026-11-06"}]
        item = ET.fromstring(construire(liste)).find("./channel/item")
        self.assertEqual(item.findtext("description"), "Texte long.\n\nSuite.")
        self.assertEqual(liste[0]["description"], "courte")

    def test_image_flux_remplace_l_image_de_la_carte_dans_le_flux(self):
        liste = [{"nom": "Grande", "adresse": "https://lacoteduheros.fr/d.html", "description": "t", "image": "data/communaute/petite.jpg", "image_flux": "data/communaute/grande.jpg", "date": "2026-11-07"}]
        item = ET.fromstring(construire(liste)).find("./channel/item")
        self.assertEqual(item.find("enclosure").get("url"), "https://lacoteduheros.fr/data/communaute/grande.jpg")

    def test_date_a_l_heure_de_paris(self):
        self.assertEqual(date_rss("2026-11-05"), "Thu, 05 Nov 2026 08:00:00 +0100")
        self.assertEqual(date_rss("2026-07-14"), "Tue, 14 Jul 2026 08:00:00 +0200")

    def test_edition_mensuelle_le_premier_du_mois(self):
        self.assertEqual(editions_mensuelles(date(2026, 11, 30)), [])
        e = editions_mensuelles(date(2027, 1, 1))
        self.assertEqual([x["date"] for x in e], ["2026-12-01", "2027-01-01"])
        self.assertEqual(e[1]["nom"], "Guide de référence : édition de janvier 2027")
        self.assertEqual(len({x["adresse"] for x in e}), 2)
        ajoutee = ajouter_editions(LISTE, date(2027, 1, 15))
        self.assertEqual(nouvelles(ajoutee)[0]["date"], "2027-01-01")
        self.assertEqual(ajouter_editions(ajoutee, date(2027, 1, 20)), ajoutee)      # sans doublon
        ET.fromstring(construire(ajoutee))

    def test_flux_vide_reste_valide(self):
        ET.fromstring(construire([]))


if __name__ == "__main__":
    unittest.main()
