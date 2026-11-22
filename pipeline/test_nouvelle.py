import json
import re
import tempfile
import unittest
from pathlib import Path

import nouvelle


class TestNouvelle(unittest.TestCase):
    def test_identifiant_sans_accent_ni_signe(self):
        self.assertEqual(nouvelle.identifiant("Le lot d'achat et de vente !"), "le-lot-d-achat-et-de-vente")
        self.assertEqual(nouvelle.identifiant("Éditions Alkonost"), "editions-alkonost")

    def test_date_longue(self):
        self.assertEqual(nouvelle.date_longue("2026-12-01"), "1er décembre 2026")
        self.assertEqual(nouvelle.date_longue("2026-11-22"), "22 novembre 2026")

    def test_corps_paragraphes_titres_listes_gras_et_liens(self):
        h = nouvelle.corps_html("Un **gras** et un [guide](guide-reference.html).\n\n## Section\n\n- a\n- b\n\n1. un\n2. deux")
        self.assertIn("<p>Un <strong>gras</strong> et un <a href=\"guide-reference.html\">guide</a>.</p>", h)
        self.assertIn("<h2>Section</h2>", h)
        self.assertIn("<ul>\n  <li>a</li>\n  <li>b</li>\n</ul>", h)
        self.assertIn("<ol>\n  <li>un</li>\n  <li>deux</li>\n</ol>", h)

    def test_corps_echappe_le_html_et_refuse_les_liens_dangereux(self):
        h = nouvelle.corps_html("<script>x</script> [mal](javascript:alert(1))")
        self.assertNotIn("<script>", h)
        self.assertNotIn("href=\"javascript", h)

    def test_page_sans_jeton_restant(self):
        modele = nouvelle.MODELE.read_text(encoding="utf-8")
        p = nouvelle.page(modele, "Un titre", "Une \"description\"", "un-titre", "Texte alternatif", "2026-11-22", "<p>Corps</p>")
        self.assertNotIn("@@", p)
        self.assertIn("<h1>Un titre</h1>", p)
        self.assertIn("images/un-titre.webp", p)
        self.assertIn("data/communaute/un-titre-partage.jpg", p)
        self.assertIn("u=https%3A%2F%2Flacoteduheros.fr%2Fun-titre.html", p)
        self.assertIn("&quot;description&quot;", p)

    def test_entree_en_tete_et_pas_de_doublon(self):
        liste = [{"nom": "Ancienne", "adresse": "https://lacoteduheros.fr/a.html"}]
        neuve = {"nom": "Neuve", "adresse": "https://lacoteduheros.fr/b.html"}
        self.assertEqual([x["nom"] for x in nouvelle.ajouter_entree(liste, neuve)], ["Neuve", "Ancienne"])
        with self.assertRaises(ValueError):
            nouvelle.ajouter_entree(liste, {"nom": "Autre", "adresse": "https://lacoteduheros.fr/a.html"})

    def test_verification_des_champs(self):
        self.assertEqual(nouvelle.verifier("T", "P", "X", "2026-11-22", "golem", "t"), [])
        e = nouvelle.verifier("", "", "", "22/11/2026", "inconnu", "")
        self.assertEqual(len(e), 6)

    def test_affiche_aux_bonnes_tailles_pour_chaque_fond(self):
        for fond in nouvelle.FONDS:
            grande, vignette = nouvelle.images("Un titre assez long pour passer sur plusieurs lignes dans l'image", "Une phrase de présentation de la nouvelle.", fond)
            self.assertEqual((grande.size, vignette.size), ((1200, 630), (640, 360)), fond)

    def test_apercu_n_ecrit_que_les_images(self):
        with tempfile.TemporaryDirectory() as d:
            chemins = nouvelle.creer("Essai", "Phrase.", "Texte", "golem", "2026-11-22", apercu=d)
            self.assertEqual(sorted(Path(c).name for c in chemins), ["essai-carte.jpg", "essai-partage.jpg"])

    def test_formulaire_du_site_aligne_sur_le_programme(self):
        page_communaute = (nouvelle.WEB / "communaute.html").read_text(encoding="utf-8")
        fonds = re.findall(r'<option value="([a-z\-]+)">', page_communaute[page_communaute.index('id="nouv-fond"'):])
        self.assertEqual(fonds[:len(nouvelle.FONDS)], list(nouvelle.FONDS))

    def test_images_du_guide_du_mois_une_par_mois_et_sans_refaire(self):
        from datetime import date
        with tempfile.TemporaryDirectory() as d:
            premiers = nouvelle.images_guide_du_mois(date(2026, 11, 30), d)
            self.assertEqual(premiers, [])          # avant la première édition : rien
            ecrits = nouvelle.images_guide_du_mois(date(2027, 1, 1), d)
            self.assertEqual(sorted(Path(x).name for x in ecrits), ["guide-2026-12-partage.jpg", "guide-2026-12.jpg", "guide-2027-01-partage.jpg", "guide-2027-01.jpg"])
            self.assertEqual(nouvelle.images_guide_du_mois(date(2027, 1, 20), d), [])          # déjà faites

    def test_nouvelle_refusee_si_champ_vide(self):
        with self.assertRaises(ValueError):
            nouvelle.creer("", "Phrase.", "Texte")


if __name__ == "__main__":
    unittest.main()
