"""Lecture de l'historique git des relevés (pipeline/premieres_historiques.py).    python -m unittest pipeline.test_premieres_historiques"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from premieres_historiques import lire_historique

SORTIE = """@@2026-10-27T15:30:00+02:00
diff --git a/data/raw/occasion/annonces-2026-10-27.csv b/data/raw/occasion/annonces-2026-10-27.csv
--- a/data/raw/occasion/annonces-2026-10-27.csv
+++ b/data/raw/occasion/annonces-2026-10-27.csv
+9782,tres_bon,5.00,titre,https://www.leboncoin.fr/ad/livres/1,0,leboncoin
@@2026-10-27T16:00:00+00:00
diff --git a/data/raw/occasion/annonces-2026-10-27.csv b/data/raw/occasion/annonces-2026-10-27.csv
+9782,tres_bon,5.00,titre,https://www.leboncoin.fr/ad/livres/1,0,leboncoin
+9783,bon,7.00,"titre, avec virgule",https://www.ebay.fr/itm/2,3,isbn
diff --git a/data/raw/occasion/leboncoin-2026-10-27.csv b/data/raw/occasion/leboncoin-2026-10-27.csv
+9784,2026-10-27,bon,1,9.00,9.00,9.00
"""


class TestLireHistorique(unittest.TestCase):
    def test_premiere_heure_en_utc_a_la_minute(self):
        r = lire_historique(SORTIE)
        self.assertEqual(r["https://www.leboncoin.fr/ad/livres/1"], "2026-10-27T13:30Z")          # 15:30 à Paris (été) = 13:30 UTC ; la seconde apparition est ignorée
        self.assertEqual(r["https://www.ebay.fr/itm/2"], "2026-10-27T16:00Z")

    def test_seuls_les_fichiers_d_annonces_sont_lus(self):
        self.assertEqual(len(lire_historique(SORTIE)), 2)


if __name__ == "__main__":
    unittest.main()
