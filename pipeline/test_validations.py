import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validations

ISBN = "9782070335749"


def ecrire(d, contenu):
    f = Path(d) / "v.json"
    f.write_text(json.dumps(contenu), encoding="utf-8")
    return f


class TestValidations(unittest.TestCase):
    def test_un_prix_valide_prime_et_garde_le_prix_calcule(self):
        p = {"bon": {"prix": 14.27, "source": "archives"}, "tres_bon": {"prix": 14.27, "source": "archives", "ajuste": True}}
        v = {(ISBN, "tres_bon"): {"prix": 22.0, "decision": "corrige", "le": "2026-10-14"}}
        self.assertEqual(validations.appliquer(p, ISBN, v), 1)
        self.assertEqual((p["tres_bon"]["prix"], p["tres_bon"]["calcule"], p["tres_bon"]["valide"]), (22.0, 14.27, True))
        self.assertNotIn("ajuste", p["tres_bon"])                       # le correctif de cohérence ne s'applique plus
        self.assertEqual(p["bon"]["prix"], 14.27)                       # un autre état n'est pas touché

    def test_etat_sans_prix_peut_etre_saisi(self):
        p = {}
        validations.appliquer(p, ISBN, {(ISBN, "bon"): {"prix": 9.5, "decision": "corrige", "le": "2026-10-14"}})
        self.assertEqual((p["bon"]["prix"], p["bon"]["calcule"]), (9.5, None))

    def test_import_fusionne_et_refuse_les_entrees_invalides(self):
        with tempfile.TemporaryDirectory() as d:
            cible = Path(d) / "cible.json"
            f = ecrire(d, {"valides": {
                f"{ISBN}|bon": {"prix": 27.5, "decision": "confirme", "le": "2026-10-14"},
                f"{ISBN}|tres_bon": {"prix": -3, "decision": "corrige", "le": "2026-10-14"},          # prix négatif
                f"{ISBN}|excellent": {"prix": 30, "decision": "corrige", "le": "2026-10-14"},         # état inconnu
                "123|bon": {"prix": 30, "decision": "corrige", "le": "2026-10-14"},                   # ISBN invalide
                f"{ISBN}|convenable": {"prix": 20, "decision": "peut-etre", "le": "2026-10-14"}}})    # décision inconnue
            self.assertEqual(validations.importer(f, cible), (1, 4))
            self.assertEqual(validations.lire(cible), {(ISBN, "bon"): {"prix": 27.5, "decision": "confirme", "le": "2026-10-14"}})

    def test_la_validation_la_plus_recente_l_emporte(self):
        with tempfile.TemporaryDirectory() as d:
            cible = Path(d) / "cible.json"
            validations.importer(ecrire(d, {"valides": {f"{ISBN}|bon": {"prix": 27.5, "decision": "confirme", "le": "2026-10-14"}}}), cible)
            validations.importer(ecrire(d, {"valides": {f"{ISBN}|bon": {"prix": 30, "decision": "corrige", "le": "2026-10-20"}}}), cible)
            validations.importer(ecrire(d, {"valides": {f"{ISBN}|bon": {"prix": 1, "decision": "corrige", "le": "2026-10-01"}}}), cible)   # plus ancienne : ignorée
            self.assertEqual(validations.lire(cible)[(ISBN, "bon")]["prix"], 30.0)

    def test_fichier_absent_ou_illisible(self):
        self.assertEqual(validations.lire("/n/existe/pas.json"), {})
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.json"
            f.write_text("pas du json")
            self.assertEqual(validations.lire(f), {})


if __name__ == "__main__":
    unittest.main()
