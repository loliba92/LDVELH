"""Tests de la jaquette envoyée depuis le site (aucun appel réseau : résolution de noms et téléchargement sont simulés).   python pipeline/test_jaquette.py"""
import io
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import editions
import jaquette as j
from PIL import Image


def publique(*_a, **_k):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def privee(*_a, **_k):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.20", 443))]


class Rep:
    def __init__(self, statut=200, type_="image/png", corps=b"", entetes=None):
        self.status_code, self.corps = statut, corps
        self.headers = {"Content-Type": type_, **(entetes or {})}
        self.ferme = False

    def iter_content(self, n):
        for i in range(0, len(self.corps), n):
            yield self.corps[i:i + n]

    def close(self):
        self.ferme = True


def png(l=700, h=1000, format_="PNG"):
    b = io.BytesIO()
    Image.new("RGB", (l, h), (120, 30, 40)).save(b, format_)
    return b.getvalue()


class TestAdresse(unittest.TestCase):
    def refuse(self, adresse, resoudre=publique):
        with self.assertRaises(j.Refus):
            j.adresse_permise(adresse, resoudre)

    def test_refus(self):
        for a in ["http://exemple.fr/a.png", "ftp://exemple.fr/a.png", "https://127.0.0.1/a.png", "https://[::1]/a.png", "https://10.0.0.5/a.png",
                  "https://localhost/a.png", "https://serveur.local/a.png", "https://monsite.internal/a.png", "https://intranet/a.png",
                  "https://exemple.fr:8443/a.png", "https://moi:mdp@exemple.fr/a.png", "https://exemple.fr/a b.png", "https://2130706433/a.png"]:
            self.refuse(a)

    def test_nom_qui_mene_a_une_adresse_privee(self):
        self.refuse("https://exemple.fr/a.png", resoudre=privee)

    def test_adresse_publique_acceptee(self):
        self.assertEqual(j.adresse_permise("https://exemple.fr/a.png", publique), "https://exemple.fr/a.png")


class TestTelechargement(unittest.TestCase):
    def test_valide(self):
        t, o = j.telecharger("https://exemple.fr/a.png", lambda u: Rep(corps=png()), publique)
        self.assertEqual(t, "image/png")
        self.assertTrue(o.startswith(b"\x89PNG"))

    def test_trop_gros_annonce_ou_reel(self):
        with self.assertRaises(j.Refus):
            j.telecharger("https://exemple.fr/a.png", lambda u: Rep(corps=b"x", entetes={"Content-Length": str(j.MAX_OCTETS + 1)}), publique)
        with self.assertRaises(j.Refus):
            j.telecharger("https://exemple.fr/a.png", lambda u: Rep(corps=b"x" * (j.MAX_OCTETS + 10)), publique)

    def test_mauvais_type(self):
        with self.assertRaises(j.Refus):
            j.telecharger("https://exemple.fr/a", lambda u: Rep(type_="text/html", corps=b"<html>"), publique)
        with self.assertRaises(j.Refus):
            j.telecharger("https://exemple.fr/a.gif", lambda u: Rep(type_="image/gif", corps=b"GIF89a"), publique)

    def test_redirection_vers_une_adresse_interne(self):
        def ouvrir(u):
            return Rep(302, entetes={"Location": "https://127.0.0.1/secret.png"})
        with self.assertRaises(j.Refus):
            j.telecharger("https://exemple.fr/a.png", ouvrir, publique)

    def test_redirection_vers_http(self):
        with self.assertRaises(j.Refus):
            j.telecharger("https://exemple.fr/a.png", lambda u: Rep(301, entetes={"Location": "http://exemple.fr/b.png"}), publique)

    def test_trop_de_redirections_et_une_seule_requete_par_etape(self):
        appels = []
        def ouvrir(u):
            appels.append(u)
            return Rep(302, entetes={"Location": "https://exemple.fr/suite"})
        with self.assertRaises(j.Refus):
            j.telecharger("https://exemple.fr/a.png", ouvrir, publique)
        self.assertEqual(len(appels), j.REDIRECTIONS + 1)

    def test_403_et_429_ne_sont_pas_retentes(self):
        for code in (403, 429):
            appels = []
            def ouvrir(u):
                appels.append(u)
                return Rep(code, entetes={"Retry-After": "120"})
            with self.assertRaises(j.Refus):
                j.telecharger("https://exemple.fr/a.png", ouvrir, publique)
            self.assertEqual(len(appels), 1)


class TestContenu(unittest.TestCase):
    def test_texte_deguise_en_image(self):
        with self.assertRaises(j.Refus):
            j.lire_image(b"<script>alert(1)</script>", "image/png")

    def test_type_annonce_different_du_contenu(self):
        with self.assertRaises(j.Refus):
            j.lire_image(png(format_="PNG"), "image/jpeg")

    def test_trop_petite(self):
        with self.assertRaises(j.Refus):
            j.lire_image(png(100, 150), "image/png")

    def test_formats_acceptes(self):
        for f, t in (("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")):
            self.assertEqual(j.lire_image(png(format_=f), t).mode, "RGB")


class TestEnregistrement(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp())
        ligne = lambda i: dict(zip(editions.COLUMNS, [""] * len(editions.COLUMNS)), id=i, isbn13=i, livre="Livre", titre="Livre", version="V1")  # noqa: E731
        editions.save([ligne("9782070332908")], d / "e.csv")
        self.base, self.covers, self.versions = str(d / "e.csv"), d / "covers", d / "jaquettes.json"

    def test_fiche_inconnue(self):
        with self.assertRaises(j.Refus):
            j.enregistrer("9780000000000", j.lire_image(png(), "image/png"), self.base, self.covers, self.versions)
        self.assertFalse(self.covers.exists())

    def test_trois_tailles_et_version(self):
        image = j.lire_image(png(700, 1000), "image/png")
        cle = j.enregistrer("9782070332908", image, self.base, self.covers, self.versions)
        self.assertEqual(cle, "9782070332908")
        largeurs = {}
        for t in ("medium", "small", "mini"):
            with Image.open(self.covers / t / f"{cle}.webp") as im:
                largeurs[t] = im.width
        self.assertEqual(largeurs, {"medium": 600, "small": 320, "mini": 160})
        self.assertEqual(json.loads(self.versions.read_text())[cle], 1)
        j.enregistrer("9782070332908", image, self.base, self.covers, self.versions)
        self.assertEqual(json.loads(self.versions.read_text())[cle], 2)       # chaque remplacement monte la version

    def test_jamais_d_agrandissement(self):
        cle = j.enregistrer("9782070332908", j.lire_image(png(400, 560), "image/png"), self.base, self.covers, self.versions)
        with Image.open(self.covers / "medium" / f"{cle}.webp") as im:
            self.assertEqual(im.width, 400)


if __name__ == "__main__":
    unittest.main()
