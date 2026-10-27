import io, json, random, sys, unittest
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).resolve().parent))
import reconciliation_image as ri
from PIL import Image, ImageEnhance

RACINE = Path(__file__).resolve().parent.parent
COVERS = RACINE / "web" / "covers"


def livres_a_plusieurs_editions():
    v = json.loads((RACINE / "web" / "data" / "versions.json").read_text(encoding="utf-8"))
    par = defaultdict(list)
    for b in v:
        if b.get("isbn13") and ri.jaquette_locale(COVERS, b["isbn13"]):
            par[b["livre_id"]].append(b["isbn13"])
    return {k: sorted(set(x)) for k, x in par.items() if len(set(x)) >= 2}


def photo_de(isbn, rnd):
    """Photo simulée d'une jaquette : recadrée, réduite, plus sombre, compressée."""
    im = Image.open(ri.jaquette_locale(COVERS, isbn)).convert("RGB")
    w, h = im.size
    im = im.crop((rnd.randint(0, w // 10), rnd.randint(0, h // 10), w - rnd.randint(0, w // 10), h - rnd.randint(0, h // 10)))
    im = im.resize((rnd.randint(150, 260), rnd.randint(220, 380)))
    im = ImageEnhance.Brightness(im).enhance(rnd.uniform(0.8, 1.2))
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=rnd.randint(55, 85))
    return buf.getvalue()


@unittest.skipUnless(ri.disponible(), "OpenCV absent")
class TestReconciliationImage(unittest.TestCase):
    def test_photo_de_la_jaquette_designe_la_bonne_edition(self):
        rnd = random.Random(3)
        livres = livres_a_plusieurs_editions()
        livre = sorted(livres)[0]
        isbns = livres[livre]
        cibles = {i: ri.jaquette_locale(COVERS, i) for i in isbns}
        cible = isbns[0]
        retenu, _ = ri.decider(photo_de(cible, rnd), cibles)
        self.assertEqual(retenu, cible)

    def test_image_sans_rapport_n_est_attribuee_a_aucune_edition(self):
        rnd = random.Random(4)
        bruit = Image.new("RGB", (240, 360))
        px = bruit.load()
        for x in range(240):
            for y in range(360):
                px[x, y] = (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
        buf = io.BytesIO(); bruit.save(buf, "PNG")
        livres = livres_a_plusieurs_editions()
        isbns = livres[sorted(livres)[0]]
        retenu, _ = ri.decider(buf.getvalue(), {i: ri.jaquette_locale(COVERS, i) for i in isbns})
        self.assertIsNone(retenu)

    def test_reconcilier_garde_la_bonne_edition(self):
        rnd = random.Random(5)
        livres = livres_a_plusieurs_editions()
        livre = sorted(livres)[0]
        isbns = livres[livre]
        cible = isbns[0]
        item = {"itemId": "42", "image": {"imageUrl": "x"}}

        class Faux:
            def get(self, url, timeout=None):
                class R:
                    status_code = 200
                    content = photo_de(cible, rnd)
                return R()
        par = {i: [dict(item)] for i in isbns}
        livre_de = {i: livre for i in isbns}
        out = ri.reconcilier(par, livre_de, COVERS, Faux())
        gardes = [i for i in out if out[i]]
        self.assertEqual(gardes, [cible])




@unittest.skipUnless(ri.disponible(), "OpenCV absent")
class TestTitreSeul(unittest.TestCase):
    def test_annonce_avec_la_bonne_photo_est_gardee(self):
        rnd = random.Random(8)
        livres = livres_a_plusieurs_editions()
        isbns = livres[sorted(livres)[0]]
        cible = isbns[0]
        item = {"itemId": "9", "_titre_seul": True, "image": {"imageUrl": "x"}}

        class Faux:
            def get(self, url, timeout=None):
                class R:
                    status_code = 200
                    content = photo_de(cible, rnd)
                return R()
        out = ri.verifier_photos({cible: [dict(item)]}, COVERS, Faux())
        self.assertEqual(len(out[cible]), 1)

    def test_annonce_avec_une_autre_photo_est_ecartee(self):
        rnd = random.Random(9)
        livres = livres_a_plusieurs_editions()
        isbns = livres[sorted(livres)[0]]
        cible, autre = isbns[0], isbns[-1]
        item = {"itemId": "9", "_titre_seul": True, "image": {"imageUrl": "x"}}

        class Faux:
            def get(self, url, timeout=None):
                class R:
                    status_code = 200
                    content = photo_de(autre, rnd)
                return R()
        out = ri.verifier_photos({cible: [dict(item)]}, COVERS, Faux())
        self.assertEqual(out[cible], [])

    def test_annonce_trouvee_par_l_isbn_est_gardee_meme_sans_photo_concluante(self):
        rnd = random.Random(9)
        livres = livres_a_plusieurs_editions()
        isbns = livres[sorted(livres)[0]]
        cible, autre = isbns[0], isbns[-1]
        item = {"itemId": "9", "image": {"imageUrl": "x"}}          # pas de « _titre_seul » : trouvée par l'ISBN

        class Faux:
            def get(self, url, timeout=None):
                class R:
                    status_code = 200
                    content = photo_de(autre, rnd)               # photo qui ne montre pas notre jaquette
                return R()
        out = ri.verifier_photos({cible: [dict(item)]}, COVERS, Faux())
        self.assertEqual(len(out[cible]), 1)


if __name__ == "__main__":
    unittest.main()
