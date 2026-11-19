"""Tests des corrections d'annonces.   python pipeline/test_corrections_annonces.py"""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corrections_annonces as ca
import cote_v2
from datetime import date

LIEN = "https://www.vinted.fr/items/1-livre"


def corr(statut, isbn=None):
    return {LIEN: {"statut": statut, "le": "2026-11-07", **({"isbn13": isbn} if isbn else {})}}


class TestCorrectionsAnnonces(unittest.TestCase):
    def test_reaffectation_change_l_edition(self):
        l = ca.corriger([{"lien": LIEN, "isbn13": "9782070000001"}, {"lien": "autre", "isbn13": "9782070000002"}], corr("reaffectee", "9782070000009"))
        self.assertEqual([x["isbn13"] for x in l], ["9782070000009", "9782070000002"])

    def test_exclusion_retire_l_annonce(self):
        self.assertEqual(ca.corriger([{"lien": LIEN, "isbn13": "9782070000001"}], corr("exclue")), [])

    def test_confirmation_garde_l_edition_choisie(self):
        l = ca.corriger([{"lien": LIEN, "isbn13": "9782070000001"}], corr("confirmee", "9782070000001"))
        self.assertEqual(l[0]["isbn13"], "9782070000001")

    def test_vendue_reste_affichee_avec_son_edition(self):
        l = ca.corriger([{"lien": LIEN, "isbn13": "9782070000001"}], corr("vendue", "9782070000001"))
        self.assertEqual(l, [{"lien": LIEN, "isbn13": "9782070000001"}])
        self.assertEqual(ca.promues(corr("vendue", "9782070000001")), {LIEN})

    def test_sans_correction_rien_ne_change(self):
        lignes = [{"lien": LIEN, "isbn13": "9782070000001"}]
        self.assertEqual(ca.corriger(lignes, {}), lignes)

    def test_fichier_illisible_ou_entree_invalide(self):
        d = Path(tempfile.mkdtemp())
        self.assertEqual(ca.lire(d / "absent.json"), {})
        (d / "x.json").write_text(json.dumps({"annonces": {LIEN: {"statut": "reaffectee", "le": "2026-11-07"}, "pas-un-lien": {"statut": "exclue", "le": "2026-11-07"}}}), encoding="utf-8")
        self.assertEqual(ca.lire(d / "x.json"), {})                    # réaffectation sans édition, lien invalide : ignorés

    def test_enregistrer_la_plus_recente_l_emporte(self):
        d = Path(tempfile.mkdtemp()) / "x.json"
        ca.enregistrer(corr("exclue"), d)
        ca.enregistrer(corr("reaffectee", "9782070000009"), d)
        self.assertEqual(ca.lire(d)[LIEN]["statut"], "reaffectee")

    def test_la_cote_ebay_suit_la_correction(self):
        d = Path(tempfile.mkdtemp())
        for j in (27, 28):
            with open(d / f"annonces-2026-10-{j}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["isbn13", "etat", "prix", "titre", "lien", "port"])
                w.writerow(["9782070000001", "bon", "20.00", "t", LIEN, "0.00"])
        jours = cote_v2.charger_jours(d, corr("reaffectee", "9782070000009"))
        self.assertEqual({r["isbn13"] for rows in jours.values() for r in rows}, {"9782070000009"})
        self.assertEqual(sum(len(r) for r in cote_v2.charger_jours(d, corr("exclue")).values()), 0)


LOT = "https://www.leboncoin.fr/ad/livres/3312541516"
A, B, C, D, V4 = "9782070509263", "9782070509256", "9782070665839", "9782070332939", "9782070665822"


class TestLotParLivre(unittest.TestCase):
    def annonces(self):
        return {A: {"bon": [[42.0, "Lot de 4 livres", LOT, "leboncoin", "2026-11-19", None]]}}

    def lots(self):
        return {LOT: {"isbns": [A, B, C, D], "poids": {A: 10, B: 10, C: 10, D: 10}, "confirmation": ""}}

    def corr(self, **entrees):
        return {k: {"statut": st, "le": "2026-11-19", **({"isbn13": i} if i else {})} for k, (st, i) in entrees.items()}

    def etaler(self, corrections):
        import importer_leboncoin as imp
        a = self.annonces()
        imp.etaler_lots(a, self.lots(), corrections)
        return {i: [x[0] for x in par.get("bon", []) if x[2] == LOT] for i, par in a.items()}

    def test_sans_correction_quatre_cartes_au_meme_prix(self):
        r = self.etaler({})
        self.assertEqual({i: v for i, v in r.items() if v}, {A: [10.5], B: [10.5], C: [10.5], D: [10.5]})

    def test_la_cle_par_livre_est_acceptee_et_la_cle_simple_aussi(self):
        v = {"statut": "reaffectee", "isbn13": V4, "le": "2026-11-19"}
        self.assertIsNotNone(ca._propre(ca.cle_livre(LOT, B), v))
        self.assertIsNotNone(ca._propre(LOT, v))
        self.assertIsNone(ca._propre(LOT + "|123", v))

    def test_reaffectee_sur_un_livre_ne_touche_pas_les_autres(self):
        r = self.etaler(self.corr(**{ca.cle_livre(LOT, A): ("reaffectee", V4)}))
        self.assertEqual({i: v for i, v in r.items() if v}, {V4: [10.5], B: [10.5], C: [10.5], D: [10.5]})      # même part, nouvelle édition

    def test_exclue_sur_un_livre_ne_touche_pas_les_autres(self):
        r = self.etaler(self.corr(**{ca.cle_livre(LOT, C): ("exclue", None)}))
        self.assertEqual({i: v for i, v in r.items() if v}, {A: [10.5], B: [10.5], D: [10.5]})                 # parts inchangées

    def test_correction_de_l_annonce_entiere_reste_valide(self):
        r = self.etaler(self.corr(**{LOT: ("reaffectee", V4)}))                                                 # ancienne clé : l'étalement n'y touche pas
        self.assertEqual({i: v for i, v in r.items() if v}, {A: [10.5], B: [10.5], C: [10.5], D: [10.5]})

    def test_enregistrer_et_relire_une_cle_par_livre(self):
        d = Path(tempfile.mkdtemp()) / "c.json"
        ok, refus = ca.enregistrer({ca.cle_livre(LOT, A): {"statut": "reaffectee", "isbn13": V4, "le": "2026-11-19"}, LOT: {"statut": "exclue", "le": "2026-11-19"}}, d)
        self.assertEqual((ok, refus), (2, 0))
        self.assertEqual(set(ca.lire(d)), {ca.cle_livre(LOT, A), LOT})

    def test_la_ligne_du_lot_corriger_prix_garde_l_isbn_d_origine(self):
        import corriger_prix as cp
        e = cp.lire(f"annonce ; {LOT} ; reaffectee ; {V4} ; V4 ; {A}")[0]
        self.assertEqual(e["lien"], ca.cle_livre(LOT, A))
        self.assertEqual(cp.lire(f"annonce ; {LOT} ; exclue ; ; ")[0]["lien"], LOT)


if __name__ == "__main__":
    unittest.main()
