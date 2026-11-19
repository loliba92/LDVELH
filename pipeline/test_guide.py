"""Tests du guide de référence en PDF (données de test petites, aucun réseau).   python pipeline/test_guide.py"""
import socket
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guide as g
import guide_analyse as ga


def livre(titre, serie, numero, version, couverture=None, prix=(5.0, 8.0, 12.5), niveau="rare", editeur="Gallimard"):
    return {"editeur": editeur, "titre": titre, "serie": serie, "numero": numero, "version": version, "version_n": int(version[1:]), "couverture": couverture,
            "rarete": {"niveau": niveau}, "prix": {"convenable": prix[0], "bon": prix[1], "tres_bon": prix[2]}}


class TestGuide(unittest.TestCase):
    def setUp(self):
        self.web = Path(tempfile.mkdtemp())
        (self.web / "covers").mkdir()
        Image.new("RGB", (320, 523), (120, 40, 50)).save(self.web / "covers" / "a.webp", "WEBP")
        self.versions = [livre("Zèbre", "Série B", "2", "V1", "covers/a.webp"), livre("Alpha", "Série A", "10", "V1", "covers/a.webp"),
                         livre("Beta", "Série A", "2", "V2", "covers/absente.webp", prix=(None, None, None)), livre("Beta", "Série A", "2", "V1")]

    def test_plan_editeur_version_serie(self):
        v = [livre("A", "Série B", "2", "V10"), livre("B", "Série B", "10", "V2"), livre("C", "Série A", "3", "V2"), livre("D", "Série A", "1", "V1"), livre("E", "Série A", "2", "V2"),
             livre("F", "X", "1", "V1", editeur="Alkonost"), livre("G", "Y", "1", "V1", editeur="<span>page copiée</span>"), livre("H", "Z", "1", "V1", editeur="Jean Nugent")]
        r = g.grouper(v)
        self.assertEqual([e for e, _ in r], ["Gallimard", "Alkonost", "Autres éditeurs"])          # le plus fourni d'abord, « Autres éditeurs » en dernier
        gal = dict(r)["Gallimard"]
        self.assertEqual([ver for ver, _ in gal], ["V1", "V2", "V10"])                              # ordre naturel, jamais V1 et V2 mélangés
        self.assertEqual([[(s, [x["titre"] for x in l]) for s, l in series] for _, series in gal][1], [("Série A", ["E", "C"]), ("Série B", ["B"])])   # séries alphabétiques, livres par numéro
        self.assertEqual(len(dict(r)["Autres éditeurs"][0][1][0][1]) + len(dict(r)["Autres éditeurs"][0][1]), 3)       # deux livres sans éditeur reconnu, deux séries

    def test_un_editeur_inconnu_ou_vide_va_dans_autres(self):
        self.assertEqual(g.editeur_de({"editeur": "Gallimard"}), "Gallimard")
        self.assertEqual(g.editeur_de({"editeur": ""}), "Autres éditeurs")
        self.assertEqual(g.editeur_de({}), "Autres éditeurs")
        self.assertEqual(g.editeur_de({"editeur": "R.L Stine"}), "Autres éditeurs")

    def test_filtres_d_essai(self):
        r = g.grouper(self.versions, {"Série B"})
        self.assertEqual([s for _, vs in r for _, ss in vs for s, _ in ss], ["Série B"])
        self.assertEqual([e for e, _ in g.grouper(self.versions, editeurs={"Alkonost"})], [])

    def test_formats(self):
        self.assertEqual(g.date_longue("2026-11-01"), "1er novembre 2026")

    def test_reperes_en_mots_memes_seuils_que_le_site(self):
        self.assertEqual([g.niveau_prix(v) for v in (None, 5, 10, 19.9, 20, 45, 70, 200)], [None, 1, 2, 2, 3, 4, 5, 5])
        self.assertEqual([g.MOTS_PRIX[n - 1] for n in (1, 2, 3, 4, 5)], ["pas cher", "abordable", "moyen", "cher", "très cher"])
        self.assertEqual([g.mot_offre(n) for n in (0, 1, 2, 3, 4, 9, 10, 50)], ["introuvable", "rare", "peu d'annonces", "peu d'annonces", "courant", "courant", "abondant", "abondant"])
        self.assertEqual(g.mot_offre(0, neuf=True), "disponible neuf")

    def test_aucun_montant_ni_decimal_dans_le_catalogue(self):
        import re
        for style in g.STYLES:
            for v in self.versions:
                v = dict(v, isbn13="9780000000001")
                f = g.Fiche(v, g.STYLES[style], ("Times-Roman", "Times-Bold", "Helvetica", "Helvetica-Bold"), self.web, {"9780000000001": {"vin": 7}})
                for texte in f.libelles():
                    self.assertNotIn("€", texte)
                    self.assertIsNone(re.search(r"\d+[,.]\d+", texte), texte)
        f = g.Fiche(self.versions[0], g.STYLES["nuit"], ("Times-Roman", "Times-Bold", "Helvetica", "Helvetica-Bold"), self.web, {})
        self.assertIn("Rareté en vente", f.libelles())
        self.assertNotIn("Rare", " ".join(f.meta.split(" · ")[1:]))          # plus de rareté structurelle à côté du numéro et de la version

    def test_pdf_genere_sans_montant_ni_decimal(self):
        import re
        import shutil
        import subprocess
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext absent")
        sortie = self.web / "t.pdf"
        g.construire(self.versions, sortie, "2026-11-19", web=self.web, genere_le="2026-11-19", donnees={"offre": {}})
        texte = subprocess.run(["pdftotext", str(sortie), "-"], capture_output=True, text=True).stdout
        self.assertNotIn("€", texte)
        self.assertIsNone(re.search(r"\d+[,.]\d+", texte))
        for mot in ("convenable", "bon état", "très bon état"):
            self.assertNotIn(mot, texte.lower())          # aucune explication des états
        self.assertIn("Ces repères sont ceux du", texte)
        self.assertNotIn("sans publicité", texte.lower())

    def test_jaquette_absente_ou_illisible(self):
        self.assertIsNone(g.jaquette_jpeg(self.web / "covers" / "absente.webp"))
        (self.web / "covers" / "x.webp").write_bytes(b"pas une image")
        self.assertIsNone(g.jaquette_jpeg(self.web / "covers" / "x.webp"))
        self.assertTrue(g.jaquette_jpeg(self.web / "covers" / "a.webp").startswith(b"\xff\xd8"))

    def test_les_deux_styles_et_les_metadonnees(self):
        for style in ("nuit", "parchemin"):
            sortie = self.web / f"{style}.pdf"
            g.construire(self.versions, sortie, "2026-11-19", web=self.web, genere_le="2026-11-19", style=style, mention=(style == "nuit"))
            donnees = sortie.read_bytes()
            self.assertIn("La Cote du Héros".encode("latin-1", "replace")[:10], donnees)
            self.assertIn(b"/Author (La Cote du H", donnees)
            self.assertIn(b"lacoteduheros.fr", donnees)          # lien du site (annotation cliquable)

    def test_pas_de_sans_publicite(self):
        for f in ("guide.py", "guide_analyse.py"):
            self.assertNotIn("sans publicité", (Path(__file__).resolve().parent / f).read_text(encoding="utf-8").lower())

    def test_pdf_complet_sans_reseau(self):
        def interdit(*a, **k):
            raise AssertionError("requête réseau")
        reel, socket.socket.connect = socket.socket.connect, interdit
        try:
            sortie = self.web / "g.pdf"
            nb = g.construire(self.versions, sortie, "2026-11-19", web=self.web, genere_le="2026-11-19")
        finally:
            socket.socket.connect = reel
        self.assertEqual(nb, 4)
        donnees = sortie.read_bytes()
        self.assertTrue(donnees.startswith(b"%PDF"))
        self.assertGreaterEqual(donnees.count(b"/Type /Page\n") + donnees.count(b"/Type /Page "), 5)          # couverture, présentation, sommaire, deux séries


class TestAnalyse(unittest.TestCase):
    def setUp(self):
        noms = (("Gallimard", "Serie Alpha"), ("Gallimard", "Serie Beta"), ("Alkonost", "Serie Gamma"), ("Hachette", "Serie Delta"))
        self.v, self.offre, k = [], {}, 0
        for i, (e, s) in enumerate(noms):
            for j in range(5):
                k += 1
                isbn = f"97800000{k:05d}"
                self.v.append({"isbn13": isbn, "titre": f"Livre {k}", "serie": s, "editeur": e, "version": f"V{j % 2 + 1}", "prix": {"bon": 6.0 + 9 * i, "tres_bon": 8.0 + 12 * i}})
                self.offre[isbn] = {"vin": (4 - i) * 3, "lbc": 1, "ebay": i % 2, "lib": 1 if i == 0 else 0}

    def test_profils_une_serie_par_editeur_avec_assez_d_editions(self):
        profs = ga.profils(self.v, self.offre, g.editeur_de)
        self.assertEqual(sorted((p["editeur"], p["serie"]) for p in profs), sorted((e, s) for e, s in (("Gallimard", "Serie Alpha"), ("Gallimard", "Serie Beta"), ("Alkonost", "Serie Gamma"), ("Hachette", "Serie Delta"))))
        self.assertEqual(ga.profils(self.v[:3], self.offre, g.editeur_de), [])          # trop peu d'éditions

    def test_quadrants_et_mots(self):
        self.assertEqual([ga.quadrant(o, c, 5, 20) for o, c in ((1, 10), (9, 10), (1, 30), (9, 30))], [0, 1, 2, 3])
        self.assertEqual([ga.niveau_activite(r) for r in (0.9, 0.6, 0.3, 0.0)], ["très active", "active", "calme", "atone"])
        self.assertEqual([ga.niveau_prix(r) for r in (0.9, 0.5, 0.1)], ["haut", "moyen", "bas"])

    def test_aucun_chiffre_dans_les_pages_d_analyse(self):
        textes, _ = ga.textes(self.v, {"offre": self.offre}, g.editeur_de, g.EDITEURS_CONNUS)
        tous = [t for l in textes.values() for t in l]
        self.assertTrue(tous)
        for t in tous:
            self.assertFalse(any(ch.isdigit() for ch in t), t)
        # la section complète (paragraphes et titres) : aucun chiffre non plus
        from reportlab.platypus import Paragraph
        styles = {k: g.ParagraphStyle(k) for k in ("corps", "h1", "h1m", "h2", "toc")}
        section = g.section_analyse(self.v, {"offre": self.offre}, styles, "2026-11-19", ("Times-Roman", "Times-Bold", "Helvetica", "Helvetica-Bold"), g.STYLES["nuit"])
        for f in section:
            if isinstance(f, Paragraph):
                self.assertFalse(any(ch.isdigit() for ch in f.getPlainText()), f.getPlainText())

    def test_chaque_phrase_nomme_un_editeur_et_une_serie_jamais_une_edition_seule(self):
        textes, _ = ga.textes(self.v, {"offre": self.offre}, g.editeur_de, g.EDITEURS_CONNUS)
        for t in textes["synthese"] + textes["attention"]:
            self.assertNotRegex(t, r"\bV\d\b")
        self.assertTrue(any("Gallimard · Serie" in t for t in textes["synthese"] + textes["plateformes"]))

    def test_les_plateformes_sont_nommees_dans_l_analyse_seulement(self):
        textes, _ = ga.textes(self.v, {"offre": self.offre}, g.editeur_de, g.EDITEURS_CONNUS)
        self.assertTrue(any("Vinted" in t for t in textes["plateformes"]))
        source = (Path(__file__).resolve().parent / "guide.py").read_text(encoding="utf-8")
        methode = source[source.index("Les cotes sont des estimations"):source.index("Le marché en bref")]
        for nom in ("Vinted", "Leboncoin", "eBay"):
            self.assertNotIn(nom, methode)

    def test_le_nuage_ne_contient_aucun_nombre(self):
        profs = ga.profils(self.v, self.offre, g.editeur_de)
        d = ga.dessiner_nuage(profs)
        chaines = [getattr(x, "text", "") for x in d.contents]
        self.assertTrue(any(chaines))
        self.assertFalse(any(ch.isdigit() for c in chaines for ch in c))

    def test_phrases_stables_et_variees(self):
        self.assertEqual(ga.choix("Gallimard", ("a", "b")), ga.choix("Gallimard", ("a", "b")))
        self.assertIn("Gallimard", ga.panorama_editeurs(ga.profils(self.v, self.offre, g.editeur_de), ["Gallimard"])[0][1])

    def test_le_pdf_ne_contient_pas_de_sans_publicite(self):
        for f in ("guide.py", "guide_analyse.py"):
            self.assertNotIn("sans publicité", (Path(__file__).resolve().parent / f).read_text(encoding="utf-8").lower())


if __name__ == "__main__":
    unittest.main()
