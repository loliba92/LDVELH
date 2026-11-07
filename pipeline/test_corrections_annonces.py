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


if __name__ == "__main__":
    unittest.main()
