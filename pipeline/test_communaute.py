"""Liste de la page Communauté : adresses https seulement, texte échappé, état vide.   python pipeline/test_communaute.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import construire_pages as cp


class TestCommunaute(unittest.TestCase):
    def test_etat_vide(self):
        self.assertIn("La liste se construit", cp.liste_communaute({"liens": []}))
        self.assertIn("La liste se construit", cp.liste_communaute({}))

    def test_sections_et_liens(self):
        h = cp.liste_communaute({"liens": [
            {"nom": "Ma chaîne", "url": "https://exemple.fr/chaine", "type": "chaine", "description": "Des parties commentées"},
            {"nom": "Blog", "url": "https://exemple.fr/blog", "type": "site"}]})
        self.assertIn("<h2>Chaînes vidéo</h2>", h)
        self.assertIn("<h2>Sites et blogs</h2>", h)
        self.assertNotIn("Podcasts", h)
        self.assertIn('rel="noopener noreferrer"', h)
        self.assertIn('target="_blank"', h)
        self.assertIn("Des parties commentées", h)

    def test_refus_et_echappement(self):
        h = cp.liste_communaute({"liens": [
            {"nom": "Piégé", "url": "javascript:alert(1)", "type": "site"},
            {"nom": "Sans https", "url": "http://exemple.fr", "type": "site"},
            {"nom": "Type inconnu", "url": "https://exemple.fr", "type": "autre"},
            {"nom": "", "url": "https://exemple.fr", "type": "site"},
            {"nom": "<script>x</script>", "url": 'https://exemple.fr/"onmouseover="x', "type": "site", "description": "<b>gras</b>"}]})
        self.assertNotIn("javascript:", h)
        self.assertNotIn("Sans https", h)
        self.assertNotIn("Type inconnu", h)
        self.assertNotIn("<script>", h)
        self.assertNotIn("<b>gras</b>", h)
        self.assertNotIn('"onmouseover="x', h)
        self.assertIn("&lt;script&gt;", h)


if __name__ == "__main__":
    unittest.main(verbosity=2)
