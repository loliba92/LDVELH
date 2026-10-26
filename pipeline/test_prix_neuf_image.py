import io, random, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prix_neuf
from PIL import Image

ISBN = "9782070000099"


def jaquette(graine):
    rnd = random.Random(graine)
    im = Image.new("RGB", (120, 180))
    px = im.load()
    for x in range(120):
        for y in range(180):
            px[x, y] = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
    return im


def octets(im):
    buf = io.BytesIO(); im.save(buf, "PNG"); return buf.getvalue()


class Rep:
    def __init__(self, texte=None, contenu=None, code=200):
        self.text, self.content, self.status_code = texte or "", contenu or b"", code

    def raise_for_status(self):
        pass


PAGE = ('<meta property="og:image" content="https://img.example/{}.png">'
        '<link itemprop="availability" href="https://schema.org/InStock"><link itemprop="itemCondition" href="https://schema.org/NewCondition">'
        '<meta itemprop="price" content="13.50">')


class Faux:
    def __init__(self, page_image):
        self.page_image = page_image

    def get(self, url, headers=None, timeout=None, allow_redirects=None):
        if "/livre/" in url:
            return Rep(texte=PAGE.format("x"), code=200)
        return Rep(contenu=octets(self.page_image))


class TestFicheCoherente(unittest.TestCase):
    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp())
        self.jaquette_notre = jaquette(5)
        self.jaquette_notre.save(self.dossier / f"{ISBN}.webp", "WEBP")
        self._ancien = prix_neuf.COUVERTURES
        prix_neuf.COUVERTURES = self.dossier

    def tearDown(self):
        prix_neuf.COUVERTURES = self._ancien

    def test_meme_jaquette_prix_gardé(self):
        r = prix_neuf.source_leslibraires(ISBN, Faux(self.jaquette_notre), attentes=())
        self.assertEqual(r["prix"], 13.5)

    def test_autre_livre_sur_la_fiche_prix_retiré(self):
        r = prix_neuf.source_leslibraires(ISBN, Faux(jaquette(77)), attentes=())
        self.assertEqual(r["disponibilite"], "indisponible")
        self.assertIsNone(r["prix"])


if __name__ == "__main__":
    unittest.main()
