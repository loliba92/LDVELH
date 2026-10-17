"""Tests des corrections de cotes saisies sur le site.   python pipeline/test_corriger_prix.py"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corriger_prix as c
import editions
import validations

RACINE = Path(__file__).resolve().parent.parent


class TestCorrections(unittest.TestCase):
    def base(self):
        d = Path(tempfile.mkdtemp())
        rows = [dict(zip(editions.COLUMNS, [""] * len(editions.COLUMNS)), id="9782070585168", isbn13="9782070585168", titre="La Malédiction de Naar", version="V1")]
        editions.save(rows, d / "e.csv")
        return str(d / "e.csv"), d / "v.json"

    def test_lecture(self):
        l = c.lire("9782070585168 ; 25 ; ; 60,5 | # note\n9782070333707;;12")
        self.assertEqual([(x["brut"], x["prix"]) for x in l], [("9782070585168", {"convenable": 25.0, "tres_bon": 60.5}), ("9782070333707", {"bon": 12.0})])

    def test_enregistrement_et_refus(self):
        base, chemin = self.base()
        bilan = c.appliquer("9782070585168 ; 25 ; ; 60 | 123 ; 5 | 9782070333707 ; 5 | 9782070585168 ; abc", chemin, base)
        self.assertEqual([s for s, _, _ in bilan], ["ok", "refuse", "refuse", "refuse"])
        v = validations.lire(chemin)
        self.assertEqual(v[("9782070585168", "convenable")]["prix"], 25.0)
        self.assertEqual(v[("9782070585168", "tres_bon")]["prix"], 60.0)
        self.assertNotIn(("9782070585168", "bon"), v)                     # case vide : l'état n'est pas touché

    def test_le_nom_d_admin_est_garde_et_nettoye(self):
        base, chemin = self.base()
        c.appliquer("9782070585168 ; 25", chemin, base, auteur="  Marc | \nDupont ; x  ")
        v = validations.lire(chemin)[("9782070585168", "convenable")]
        self.assertEqual(v["par"], "Marc Dupont x")
        c.appliquer("9782070585168 ; bon", chemin, base)                    # sans nom : aucune clé « par »
        c.appliquer("9782070585168 ; ; 40", chemin, base)
        self.assertNotIn("par", validations.lire(chemin)[("9782070585168", "bon")])
        d = {"bon": {"prix": 1}}
        validations.appliquer(d, "9782070585168", validations.lire(chemin))
        self.assertEqual(d["bon"]["prix"], 40.0)

    def test_la_derniere_correction_l_emporte(self):
        base, chemin = self.base()
        c.appliquer("9782070585168 ; 25", chemin, base)
        c.appliquer("9782070585168 ; 30", chemin, base)
        self.assertEqual(validations.lire(chemin)[("9782070585168", "convenable")]["prix"], 30.0)

    def test_prix_confirmes(self):
        base, chemin = self.base()
        c.appliquer("9782070585168 ; 25 ; 40 ; 60 ; confirme", chemin, base)
        v = validations.lire(chemin)
        self.assertEqual({k[1]: x["decision"] for k, x in v.items()}, {"convenable": "confirme", "bon": "confirme", "tres_bon": "confirme"})

    def test_meme_empreinte_pour_la_porte_et_la_fiche(self):
        h = lambda f: re.search(r"[0-9a-f]{64}", (RACINE / "web" / f).read_text(encoding="utf-8")).group(0)
        self.assertEqual(h("acces.js"), h("app.js"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
