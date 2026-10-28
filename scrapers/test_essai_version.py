"""Tests de l'essai en deux étapes : détection de version dans une description (sans appel réseau)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import essai_version as ev

EDITIONS = [{"isbn13": "1", "version": "V1", "annee": 1993}, {"isbn13": "2", "version": "V2", "annee": 2002},
            {"isbn13": "3", "version": "V3", "annee": 2006}]


class TestVersionIndiquee(unittest.TestCase):
    def test_version_ecrite(self):
        self.assertEqual(ev.version_indiquee("Très bon état, V3 Gallimard Jeunesse", EDITIONS), "3")

    def test_annee_connue(self):
        self.assertEqual(ev.version_indiquee("Édition de 1993, bon état", EDITIONS), "1")

    def test_plusieurs_versions_donnent_rien(self):
        self.assertIsNone(ev.version_indiquee("V1 et V2 mélangées", EDITIONS))

    def test_version_du_titre(self):
        self.assertEqual(ev.version_titre("La Porte d'Ombre V2 Gallimard"), "V2")
        self.assertEqual(ev.version_titre("Loup Solitaire v 3"), "V3")
        self.assertIsNone(ev.version_titre("La Porte d'Ombre"))

    def test_texte_vide_ou_sans_version(self):
        self.assertIsNone(ev.version_indiquee("", EDITIONS))
        self.assertIsNone(ev.version_indiquee("Très bon état, envoi rapide", EDITIONS))


if __name__ == "__main__":
    unittest.main()
