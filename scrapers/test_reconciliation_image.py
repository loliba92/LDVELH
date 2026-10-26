import random, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import reconciliation_image as ri
from PIL import Image, ImageEnhance


def jaquette(graine):
    rnd = random.Random(graine)
    im = Image.new("RGB", (120, 180))
    px = im.load()
    for x in range(120):
        for y in range(180):
            px[x, y] = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
    return im


class Faux:
    def __init__(self, image):
        self.image = image

    def get(self, url, timeout=None):
        import io
        class R:
            status_code = 200
            content = b""
        r = R()
        buf = io.BytesIO(); self.image.save(buf, "PNG"); r.content = buf.getvalue()
        return r


class TestReconciliationImage(unittest.TestCase):
    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp())
        (self.dossier / "small").mkdir()
        self.couv = {}
        for isbn, graine in [("9782070000001", 1), ("9782070000002", 2), ("9782070000003", 3)]:
            jaquette(graine).save(self.dossier / "small" / f"{isbn}.webp", "WEBP")
            self.couv[isbn] = jaquette(graine)

    def test_meme_jaquette_retrouvee_meme_si_photo_plus_sombre(self):
        photo = ImageEnhance.Brightness(self.couv["9782070000002"].resize((60, 90))).enhance(0.8)
        e = ri.empreinte_annonce({"image": {"imageUrl": "x"}}, Faux(photo))
        self.assertEqual(ri.choisir_edition(e, {i: ri.empreinte_fichier(self.dossier / "small" / f"{i}.webp") for i in self.couv}), "9782070000002")

    def test_image_qui_ne_ressemble_a_aucune_edition(self):
        autre = jaquette(99)
        e = ri.empreinte_annonce({"image": {"imageUrl": "x"}}, Faux(autre))
        self.assertIsNone(ri.choisir_edition(e, {i: ri.empreinte_fichier(self.dossier / "small" / f"{i}.webp") for i in self.couv}))

    def test_deux_jaquettes_identiques_donnent_un_choix_incertain(self):
        d = Path(tempfile.mkdtemp())
        (d / "small").mkdir()
        for isbn in ("9782070000010", "9782070000011"):
            jaquette(7).save(d / "small" / f"{isbn}.webp", "WEBP")
        e = ri.empreinte_fichier(d / "small" / "9782070000010.webp")
        self.assertIsNone(ri.choisir_edition(e, {i: ri.empreinte_fichier(d / "small" / f"{i}.webp") for i in ("9782070000010", "9782070000011")}))

    def test_reconcilier_garde_la_bonne_edition(self):
        cible = "9782070000002"
        photo = self.couv[cible].resize((60, 90))
        item = {"itemId": "1", "image": {"imageUrl": "x"}}
        par = {"9782070000001": [dict(item)], cible: [dict(item)], "9782070000003": []}
        livres = {i: "livre-A" for i in par}
        out = ri.reconcilier(par, livres, self.dossier, Faux(photo))
        gardes = [i for i in out if out[i]]
        self.assertEqual(gardes, [cible])


if __name__ == "__main__":
    unittest.main()
