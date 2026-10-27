"""Les pages « un livre » (web/livre/) doivent suivre exactement la liste des éditions (web/data/versions.json) :
une page par édition, aucune page en trop, contenu identique à ce que génère pipeline/pages_livres.py, aucun prix exact.
    python -m unittest pipeline.test_pages_livres"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import construire_pages as cp
import pages_livres as pl


class TestPagesLivres(unittest.TestCase):
    def test_une_page_par_edition_et_rien_en_trop(self):
        voulus = {f"{b['isbn13']}.html" for b in pl.editions_publiques(cp.WEB)} | {"index.html"}
        presents = {f.name for f in (cp.WEB / "livre").glob("*.html")}
        self.assertEqual(sorted(voulus - presents), [], "pages de livres manquantes : relancer python pipeline/construire_pages.py")
        self.assertEqual(sorted(presents - voulus), [], "pages de livres en trop : relancer python pipeline/construire_pages.py")

    def test_les_pages_enregistrees_concordent_avec_le_generateur(self):
        racine = Path(tempfile.mkdtemp())
        copie = racine / "web"
        copie.mkdir()
        for f in cp.WEB.glob("*.html"):
            shutil.copy(f, copie / f.name)
        shutil.copytree(cp.WEB / "data", copie / "data")
        shutil.copytree(cp.WEB / "covers", copie / "covers", ignore=lambda d, n: n if "small" in d else [])
        origine = cp.WEB
        try:
            cp.WEB = copie
            cp.main()
        finally:
            cp.WEB = origine
        ecarts = [f.name for f in sorted((origine / "livre").glob("*.html")) if (copie / "livre" / f.name).exists()
                  and f.read_text(encoding="utf-8") != (copie / "livre" / f.name).read_text(encoding="utf-8")]
        self.assertEqual(ecarts, [], "pages de livres différentes du générateur : relancer python pipeline/construire_pages.py")
        for nom in ("sitemap.xml", "robots.txt"):
            self.assertEqual((origine / nom).read_text(encoding="utf-8"), (copie / nom).read_text(encoding="utf-8"), nom)

    def test_le_plan_du_site_liste_chaque_livre(self):
        plan = (cp.WEB / "sitemap.xml").read_text(encoding="utf-8")
        for b in pl.editions_publiques(cp.WEB):
            self.assertIn(f"/livre/{b['isbn13']}.html</loc>", plan)

    def test_pas_de_prix_exact_dans_les_pages_publiques(self):
        prix = re.compile(r"\d+[,.]\d+\s?€")
        for f in (cp.WEB / "livre").glob("*.html"):
            self.assertIsNone(prix.search(f.read_text(encoding="utf-8")), f.name)

    def test_niveaux_de_prix_comme_dans_le_guide(self):
        self.assertEqual([pl.niveau(v) for v in (None, 9.99, 10, 25, 40, 69, 70, 500)], [0, 1, 2, 3, 4, 4, 5, 5])
        js = (cp.WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("const SEUILS_COTE = [10, 20, 40, 70];", js)

    def test_les_liens_internes_des_pages_livres_existent(self):
        page = (cp.WEB / "livre" / f"{pl.editions_publiques(cp.WEB)[0]['isbn13']}.html").read_text(encoding="utf-8")
        for lien in re.findall(r'(?:href|src)="([^"#:?]+)', page):
            if lien.startswith("../"):
                self.assertTrue((cp.WEB / lien[3:]).exists() or lien == "../", lien)


if __name__ == "__main__":
    unittest.main()
