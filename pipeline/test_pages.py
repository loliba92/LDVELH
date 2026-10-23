"""Les pages générées par pipeline/construire_pages.py doivent concorder avec celles enregistrées dans web/.
Le relevé des prix régénère ces pages à chaque passage : une modification faite directement dans une page générée, sans le générateur,
serait effacée au passage suivant (constaté le 23 octobre 2026 sur revue-prix.html).    python -m unittest pipeline.test_pages"""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import construire_pages as cp

DATES = re.compile(r"(mise à jour de cette page : |Dernière mise à jour : )[^<]*")
A_PART = {"evolutions.html"}          # contenu qui dépend des données du jour


class TestPagesGenerees(unittest.TestCase):
    def test_les_pages_enregistrees_concordent_avec_le_generateur(self):
        racine = Path(tempfile.mkdtemp())
        copie = racine / "web"
        copie.mkdir()
        for f in cp.WEB.glob("*.html"):
            shutil.copy(f, copie / f.name)
        shutil.copytree(cp.WEB / "data", copie / "data")
        origine = cp.WEB
        try:
            cp.WEB = copie
            cp.main()
        finally:
            cp.WEB = origine
        ecarts = []
        for f in sorted(origine.glob("*.html")):
            if f.name in A_PART or not (copie / f.name).exists():
                continue
            avant = DATES.sub(r"\1", f.read_text(encoding="utf-8"))
            apres = DATES.sub(r"\1", (copie / f.name).read_text(encoding="utf-8"))
            if avant != apres:
                ecarts.append(f.name)
        self.assertEqual(ecarts, [], "pages différentes de ce que génère pipeline/construire_pages.py : corriger le générateur, puis relancer python pipeline/construire_pages.py")


if __name__ == "__main__":
    unittest.main()
