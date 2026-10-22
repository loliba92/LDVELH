"""Tests des corrections de fiches saisies sur le site.   python pipeline/test_corriger_fiche.py"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corriger_fiche as c
import editions


class TestFiches(unittest.TestCase):
    def base(self):
        d = Path(tempfile.mkdtemp())
        def r(i, t, v, s="", n=""):
            return dict(zip(editions.COLUMNS, [""] * len(editions.COLUMNS)), id=i, isbn13=i, livre=t, titre=t, version=v, serie=s, numero=n)
        editions.save([r("9782075237192", "Le Héros de Mynuit", "V1"), r("9782070593378", "Le Héros de Mynuit", "V2", "Loup Solitaire", "23"), r("9782070332885", "Autre livre", "V1")], d / "e.csv")
        (d / "p.json").write_text(json.dumps({"valides": {"9782075237192|bon": {"prix": 5}, "9782070332885|bon": {"prix": 7}}}), encoding="utf-8")
        return str(d / "e.csv"), d / "p.json"

    def test_la_suppression_est_reservee_au_superadmin(self):
        base, prix = self.base()
        for role in ("admin", ""):
            bilan = c.appliquer("9782075237192 ; supprimer", base, prix, jaquettes=False, role=role)
            self.assertEqual(bilan[0][0], "refuse")
            self.assertIn("SuperAdmin", bilan[0][2])
            self.assertIn("9782075237192", {r["id"] for r in editions.load(base)})
        bilan = c.appliquer("9782075237192 ; supprimer", base, prix, jaquettes=False, role="superadmin")
        self.assertEqual(bilan[0][0], "ok")
        self.assertNotIn("9782075237192", {r["id"] for r in editions.load(base)})

    def test_serie_et_titre_valent_pour_toutes_les_editions_du_livre(self):
        base, prix = self.base()
        bilan = c.appliquer("9782075237192 ; serie ; Loup Solitaire | 9782075237192 ; titre ; Le Héros de Minuit", base, prix)
        self.assertEqual([s for s, _, _ in bilan], ["ok", "ok"])
        rows = {r["id"]: r for r in editions.load(base)}
        self.assertEqual((rows["9782070593378"]["serie"], rows["9782070593378"]["titre"], rows["9782070593378"]["livre"]), ("Loup Solitaire", "Le Héros de Minuit", "Le Héros de Minuit"))
        self.assertEqual(rows["9782070332885"]["titre"], "Autre livre")

    def test_numero_d_une_seule_edition_et_refus(self):
        base, prix = self.base()
        bilan = c.appliquer("9782075237192 ; numero ; 7 | 9782075237192 ; numero ; abc | 000 ; titre ; X | 9782075237192 ; couleur ; rouge | 9782075237192 ; titre ;", base, prix)
        self.assertEqual([s for s, _, _ in bilan], ["ok", "refuse", "refuse", "refuse", "refuse"])
        rows = {r["id"]: r for r in editions.load(base)}
        self.assertEqual((rows["9782075237192"]["numero"], rows["9782070593378"]["numero"]), ("7", "23"))

    def test_suppression_retire_la_fiche_et_ses_prix(self):
        base, prix = self.base()
        self.assertEqual(c.appliquer("9782075237192 ; supprimer", base, prix, jaquettes=False)[0][0], "ok")
        self.assertEqual({r["id"] for r in editions.load(base)}, {"9782070593378", "9782070332885"})
        self.assertEqual(list(json.loads(prix.read_text(encoding="utf-8"))["valides"]), ["9782070332885|bon"])

    def test_les_caracteres_invisibles_sont_retires(self):
        base, prix = self.base()
        c.appliquer("9782075237192 ; titre ; ‎Le  Héros‏ de Minuit", base, prix)
        self.assertEqual(next(r for r in editions.load(base) if r["id"] == "9782075237192")["titre"], "Le Héros de Minuit")


if __name__ == "__main__":
    unittest.main()
