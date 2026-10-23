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
        self.assertEqual(v[("9782070585168", "bon")]["prix"], 36.74)      # fourchette complète : le bon état vide est calculé entre les deux

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

    def _valides(self, chemin, **prix):
        envoi = {f"9782070585168|{e}": {"prix": p, "decision": "confirme", "le": "2026-10-21"} for e, p in prix.items()}
        f = chemin.parent / "envoi.json"
        f.write_text(json.dumps({"valides": envoi}), encoding="utf-8")
        validations.importer(f, chemin)

    def test_une_fourchette_recalcule_un_bon_etat_deja_valide(self):
        base, chemin = self.base()
        self._valides(chemin, convenable=16.38, bon=24.58, tres_bon=40.96)
        bilan = c.appliquer("9782070585168 ; 2,5 ; ; 13", chemin, base)
        v = validations.lire(chemin)
        self.assertEqual([v[("9782070585168", e)]["prix"] for e in ("convenable", "bon", "tres_bon")], [2.5, 5.41, 13.0])
        self.assertEqual(v[("9782070585168", "bon")]["decision"], "corrige")
        self.assertIn("bon état recalculé", bilan[0][2])

    def test_un_seul_prix_recalcule_le_bon_etat_qui_le_depasse(self):
        base, chemin = self.base()
        self._valides(chemin, convenable=2, bon=24.58, tres_bon=40.96)
        c.appliquer("9782070585168 ; ; ; 13", chemin, base)
        v = validations.lire(chemin)
        self.assertEqual(v[("9782070585168", "tres_bon")]["prix"], 13.0)
        self.assertEqual(v[("9782070585168", "bon")]["prix"], 4.84)

    def test_un_bon_etat_coherent_n_est_pas_touche(self):
        base, chemin = self.base()
        self._valides(chemin, convenable=16.38, bon=24.58, tres_bon=40.96)
        c.appliquer("9782070585168 ; ; ; 50", chemin, base)                  # 24,58 reste entre 16,38 et 50
        v = validations.lire(chemin)
        self.assertEqual(v[("9782070585168", "bon")]["prix"], 24.58)
        self.assertEqual(v[("9782070585168", "bon")]["decision"], "confirme")

    def test_une_fourchette_met_toujours_a_jour_les_trois_prix(self):
        base, chemin = self.base()                                            # aucun bon état validé (il pouvait venir d'annonces)
        c.appliquer("9782070585168 ; 2,5 ; ; 13", chemin, base)
        v = validations.lire(chemin)
        self.assertEqual([v[("9782070585168", e)]["prix"] for e in ("convenable", "bon", "tres_bon")], [2.5, 5.41, 13.0])

    def test_un_seul_prix_sans_bon_etat_valide_ne_cree_pas_de_bon_etat(self):
        base, chemin = self.base()
        c.appliquer("9782070585168 ; ; ; 13", chemin, base)
        self.assertNotIn(("9782070585168", "bon"), validations.lire(chemin))

    def test_un_bon_etat_saisi_est_garde_tel_quel(self):
        base, chemin = self.base()
        self._valides(chemin, bon=24.58)
        c.appliquer("9782070585168 ; 2,5 ; 7 ; 13", chemin, base)
        self.assertEqual(validations.lire(chemin)[("9782070585168", "bon")]["prix"], 7.0)

    def test_prix_confirmes(self):
        base, chemin = self.base()
        c.appliquer("9782070585168 ; 25 ; 40 ; 60 ; confirme", chemin, base)
        v = validations.lire(chemin)
        self.assertEqual({k[1]: x["decision"] for k, x in v.items()}, {"convenable": "confirme", "bon": "confirme", "tres_bon": "confirme"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
