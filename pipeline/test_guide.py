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
        self.assertEqual(g.euros(9.4), "9,40 €")
        self.assertEqual(g.euros(None), "—")
        self.assertEqual(g.date_longue("2026-11-01"), "1er novembre 2026")

    def test_jaquette_absente_ou_illisible(self):
        self.assertIsNone(g.jaquette_jpeg(self.web / "covers" / "absente.webp"))
        (self.web / "covers" / "x.webp").write_bytes(b"pas une image")
        self.assertIsNone(g.jaquette_jpeg(self.web / "covers" / "x.webp"))
        self.assertTrue(g.jaquette_jpeg(self.web / "covers" / "a.webp").startswith(b"\xff\xd8"))

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
        self.v = [{"isbn13": str(i), "titre": f"L{i}", "prix": {"bon": 5.0 * i, "tres_bon": 6.0 * i}} for i in range(1, 9)] + [{"titre": "sans isbn", "prix": {"bon": 3}}]
        self.offre = {"1": {"ebay": 1, "vin": 2}, "2": {"lbc": 4}, "8": {"lib": 9, "rev": 1}}

    def test_points_une_edition_avec_isbn_et_cote(self):
        pts = ga.points(self.v, self.offre)
        self.assertEqual(len(pts), 8)
        self.assertEqual(pts[0], (3, 6.0, "L1"))
        self.assertEqual(pts[2][0], 0)

    def test_quadrants_par_rapport_aux_medianes(self):
        self.assertEqual([ga.quadrant(n, p, 5, 20) for n, p in ((1, 10), (9, 10), (1, 30), (9, 30))], [0, 1, 2, 3])

    def test_phrases_calculees(self):
        t = " ".join(ga.phrases_nuage(ga.points(self.v, self.offre)))
        self.assertIn("8 éditions", t)
        self.assertIn("5 éditions (62 %) sont sans annonce en ligne", t)

    def test_tranches_et_tendances(self):
        self.assertEqual(sum(n for _, n in ga.repartition_tranches(self.v)), 9)
        tend = {"groupes": {"marche": {"version": [{"cle": "V1", "n": 10, "mediane": -0.1, "hausses": 2, "baisses": 7, "peu": False}, {"cle": "V9", "n": 1, "mediane": 0.5, "hausses": 1, "baisses": 0, "peu": True}]}}}
        self.assertEqual(ga.lignes_tendance(tend, nom="version"), [("V1", 10, -0.1, 2, 7)])
        self.assertEqual(ga.pct(-0.1234), "−12,3 %")

    def test_le_dessin_et_le_pdf_ne_contiennent_pas_d_annonce_ni_de_nom_de_site(self):
        d = ga.dessiner_nuage(ga.points(self.v, self.offre))
        self.assertGreater(len(d.contents), 10)
        source = (Path(__file__).resolve().parent / "guide.py").read_text(encoding="utf-8") + (Path(__file__).resolve().parent / "guide_analyse.py").read_text(encoding="utf-8")
        for mot in ("sans publicité", "ebay.", "leboncoin", "vinted", "http"):
            self.assertNotIn(mot, source.lower().replace('"ebay", "lbc"', ""))


if __name__ == "__main__":
    unittest.main()
