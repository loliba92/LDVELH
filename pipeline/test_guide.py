"""Tests du guide de référence en PDF (données de test petites, aucun réseau).   python pipeline/test_guide.py"""
import socket
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guide as g


def livre(titre, serie, numero, version, couverture=None, prix=(5.0, 8.0, 12.5), niveau="rare"):
    return {"titre": titre, "serie": serie, "numero": numero, "version": version, "version_n": int(version[1:]), "couverture": couverture,
            "rarete": {"niveau": niveau}, "prix": {"convenable": prix[0], "bon": prix[1], "tres_bon": prix[2]}}


class TestGuide(unittest.TestCase):
    def setUp(self):
        self.web = Path(tempfile.mkdtemp())
        (self.web / "covers").mkdir()
        Image.new("RGB", (320, 523), (120, 40, 50)).save(self.web / "covers" / "a.webp", "WEBP")
        self.versions = [livre("Zèbre", "Série B", "2", "V1", "covers/a.webp"), livre("Alpha", "Série A", "10", "V1", "covers/a.webp"),
                         livre("Beta", "Série A", "2", "V2", "covers/absente.webp", prix=(None, None, None)), livre("Beta", "Série A", "2", "V1")]

    def test_series_alphabetiques_livres_par_numero_puis_version(self):
        r = g.grouper(self.versions)
        self.assertEqual([s for s, _ in r], ["Série A", "Série B"])
        self.assertEqual([(v["numero"], v["version"]) for v in r[0][1]], [("2", "V1"), ("2", "V2"), ("10", "V1")])

    def test_filtre_de_series(self):
        self.assertEqual([s for s, _ in g.grouper(self.versions, {"Série B"})], ["Série B"])

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


if __name__ == "__main__":
    unittest.main()
