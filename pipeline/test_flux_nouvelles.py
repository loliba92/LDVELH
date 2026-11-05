import unittest
import xml.etree.ElementTree as ET

from flux_nouvelles import construire, date_rss, nouvelles

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

    def test_date_a_l_heure_de_paris(self):
        self.assertEqual(date_rss("2026-11-05"), "Thu, 05 Nov 2026 08:00:00 +0100")
        self.assertEqual(date_rss("2026-07-14"), "Tue, 14 Jul 2026 08:00:00 +0200")

    def test_flux_vide_reste_valide(self):
        ET.fromstring(construire([]))


if __name__ == "__main__":
    unittest.main()
