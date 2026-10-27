import io, random, sys, unittest
from contextlib import redirect_stdout
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import reconciliation_image as ri
import essai_photos
from test_reconciliation_image import livres_a_plusieurs_editions, photo_de, COVERS


@unittest.skipUnless(ri.disponible(), "OpenCV absent")
class TestEssaiPhotos(unittest.TestCase):
    def test_mesure_sur_des_photos_simulees(self):
        rnd = random.Random(3)
        livres = livres_a_plusieurs_editions()
        noms = sorted(livres)[:3]
        livre_de = {i: n for n in noms for i in livres[n]}
        editions_du_livre = {n: list(livres[n]) for n in noms}
        photos = {}

        class Faux:
            def get(self, url, timeout=None):
                class R:
                    status_code = 200
                    content = photos[url]
                return R()
        par_isbn = {}
        for isbn in list(livre_de)[:6]:
            url = f"u-{isbn}"
            photos[url] = photo_de(isbn, rnd)
            par_isbn[isbn] = [{"itemId": isbn, "itemWebUrl": "https://exemple/" + isbn, "image": {"imageUrl": url}}]
        s, tranches, exemples = essai_photos.mesurer(par_isbn, COVERS, livre_de, editions_du_livre, Faux())
        self.assertEqual(s["annonces essayées"], 6)
        self.assertGreaterEqual(s["A confirmée"], 4)                     # les photos simulées gardent assez de points
        self.assertEqual(s["B fausse acceptation"], 0)                   # une photo ne confirme jamais la jaquette d'un autre livre
        self.assertEqual(s["C MAUVAISE édition"], 0)
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            essai_photos.afficher(s, tranches, exemples)
        self.assertIn("A. Photo contre la jaquette de son édition", sortie.getvalue())
        self.assertIn("doit rester à 0", sortie.getvalue())


if __name__ == "__main__":
    unittest.main()
