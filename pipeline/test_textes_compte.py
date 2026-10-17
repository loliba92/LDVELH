"""Les variantes de textes du mode « collection liée au compte Google » trouvent toutes leur phrase.   python pipeline/test_textes_compte.py"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import construire_pages as cp


class TestVariantes(unittest.TestCase):
    def pages(self):
        index = (cp.WEB / "index.html").read_text(encoding="utf-8")
        brutes = [cp.page_collection(index)]
        brutes += [cp.page(n, c) for n, c in (("le-projet.html", cp.LE_PROJET), ("confidentialite.html", cp.CONFIDENTIALITE), ("mentions-legales.html", cp.MENTIONS))]
        return brutes

    def test_chaque_variante_trouve_sa_phrase(self):
        texte = "\n".join(self.pages())
        for ancien, _ in cp.VARIANTES:
            with self.subTest(ancien=ancien[:60]):
                self.assertIn(ancien, texte)

    def test_le_mode_compte_ne_laisse_plus_la_promesse_sans_compte(self):
        avant, cp.COMPTE = cp.COMPTE, True
        try:
            sortie = "\n".join(cp.variante(p) for p in self.pages())
        finally:
            cp.COMPTE = avant
        for faux in ("rien n'est envoyé, tout reste dans votre navigateur", "Votre collection reste dans votre navigateur", "Rien n'est envoyé à un serveur", "Pas de compte, pas de formulaire"):
            self.assertNotIn(faux, sortie)
        self.assertIn("espace réservé de votre Google Drive", sortie)

    def test_sans_le_mode_compte_rien_ne_change(self):
        avant, cp.COMPTE = cp.COMPTE, False
        try:
            for p in self.pages():
                self.assertEqual(cp.variante(p), p)
        finally:
            cp.COMPTE = avant


if __name__ == "__main__":
    unittest.main(verbosity=2)
