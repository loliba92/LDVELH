import csv, tempfile, unittest
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importer_leboncoin as imp

ISBN_A, ISBN_B = "9782070333707", "9782070506736"
CONNUES = {ISBN_A, ISBN_B}
JOUR = date(2026, 10, 24)
ENTETE = "isbn13,etat,prix,titre,lien,statut,age_jours,date\n"


def ligne(isbn=ISBN_A, etat="bon", prix="12.50", titre="LDVELH Le Sorcier Majdar", lien="https://www.leboncoin.fr/ad/livres/1", statut="actif", age="3", jour="2026-10-24"):
    return f'{isbn},{etat},{prix},"{titre}",{lien},{statut},{age},{jour}\n'


def corps(*lignes):
    return "Relevé du soir\n\n```csv\n" + ENTETE + "".join(lignes) + "```\n"


def lire(d, nom):
    with open(Path(d) / nom, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestImporter(unittest.TestCase):
    def test_import_ecrit_les_quatre_fichiers(self):
        with tempfile.TemporaryDirectory() as d:
            b = imp.importer(corps(ligne(prix="10"), ligne(prix="14", lien="https://www.leboncoin.fr/ad/livres/2"),
                                   ligne(prix="9", lien="https://www.leboncoin.fr/ad/livres/3", statut="vendu")), JOUR, d, CONNUES)
            self.assertEqual((b["acceptees"], b["refusees"], b["jours"]), (3, 0, ["2026-10-24"]))
            act = lire(d, "annonces-leboncoin-2026-10-24.csv")
            self.assertEqual(len(act), 2)
            self.assertEqual({r["trouvee_par"] for r in act}, {"leboncoin"})
            self.assertEqual(list(act[0].keys()), imp.COLONNES_ANNONCES)         # même format que annonces-*.csv d'eBay
            self.assertEqual(len(lire(d, "vendus-leboncoin-2026-10-24.csv")), 1)
            ag = lire(d, "leboncoin-2026-10-24.csv")[0]
            self.assertEqual((ag["nb_annonces"], ag["prix_min"], ag["prix_median"], ag["prix_max"]), ("2", "10.00", "12.00", "14.00"))
            self.assertEqual(lire(d, "leboncoin-vendus-2026-10-24.csv")[0]["prix_median"], "9.00")

    def test_refus(self):
        cas = {"édition inconnue": ligne(isbn="9782070999996"), "ISBN invalide": ligne(isbn="123"), "état inconnu": ligne(etat="neuf"),
               "prix hors limites": ligne(prix="0.1"), "lien non conforme": ligne(lien="https://exemple.fr/x"),
               "date hors fenêtre": ligne(jour="2026-09-01"), "statut inconnu": ligne(statut="supprimer"), "prix illisible": ligne(prix="abc")}
        for raison, l in cas.items():
            with tempfile.TemporaryDirectory() as d:
                b = imp.importer(corps(l), JOUR, d, CONNUES)
                self.assertEqual(b["acceptees"], 0, raison)
                self.assertTrue(any(k.startswith(raison.split(" (")[0]) for k in b["raisons"]), (raison, b["raisons"]))
                self.assertEqual(list(Path(d).iterdir()), [], raison)            # rien d'écrit

    def test_titre_nettoye(self):
        with tempfile.TemporaryDirectory() as d:
            imp.importer(corps(ligne(titre="<script>alert(1)</script> LDVELH  Majdar")), JOUR, d, CONNUES)
            t = lire(d, "annonces-leboncoin-2026-10-24.csv")[0]["titre"]
            self.assertNotIn("<", t); self.assertNotIn(">", t); self.assertIn("LDVELH Majdar", t)

    def test_rejouer_donne_le_meme_resultat(self):
        with tempfile.TemporaryDirectory() as d:
            c = corps(ligne(prix="10"), ligne(prix="14", lien="https://www.leboncoin.fr/ad/livres/2"))
            imp.importer(c, JOUR, d, CONNUES); premier = (Path(d) / "leboncoin-2026-10-24.csv").read_text(encoding="utf-8")
            imp.importer(c, JOUR, d, CONNUES)
            self.assertEqual((Path(d) / "leboncoin-2026-10-24.csv").read_text(encoding="utf-8"), premier)
            self.assertEqual(len(lire(d, "annonces-leboncoin-2026-10-24.csv")), 2)

    def test_vendue_quitte_les_actives_et_ne_revient_pas(self):
        with tempfile.TemporaryDirectory() as d:
            imp.importer(corps(ligne(prix="10")), JOUR, d, CONNUES)
            imp.importer(corps(ligne(prix="10", statut="vendu")), JOUR, d, CONNUES)
            self.assertFalse((Path(d) / "annonces-leboncoin-2026-10-24.csv").exists())
            self.assertFalse((Path(d) / "leboncoin-2026-10-24.csv").exists())
            self.assertEqual(len(lire(d, "vendus-leboncoin-2026-10-24.csv")), 1)
            imp.importer(corps(ligne(prix="10")), JOUR, d, CONNUES)             # un relevé en retard la redonne « active » : elle reste vendue
            self.assertFalse((Path(d) / "annonces-leboncoin-2026-10-24.csv").exists())

    def test_trop_de_lignes_et_texte_libre(self):
        with tempfile.TemporaryDirectory() as d:
            b = imp.importer(corps(*[ligne(lien=f"https://www.leboncoin.fr/ad/livres/{i}") for i in range(imp.MAX_LIGNES + 1)]), JOUR, d, CONNUES)
            self.assertEqual(b["acceptees"], 0)
            self.assertEqual(imp.importer("bonjour, rien à voir", JOUR, d, CONNUES)["acceptees"], 0)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_bloc_sans_balise(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(imp.importer(ENTETE + ligne(), JOUR, d, CONNUES)["acceptees"], 1)

    def test_un_lot_repartit_son_prix_entre_ses_livres(self):
        lien = "https://www.leboncoin.fr/ad/livres/77"
        lot = {"isbns": [ISBN_A, ISBN_B], "poids": {ISBN_A: 10.0, ISBN_B: 30.0}}
        self.assertEqual([(i, round(p, 2)) for i, p in imp.repartir_lot(40.0, lot)], [(ISBN_A, 10.0), (ISBN_B, 30.0)])
        with tempfile.TemporaryDirectory() as d:
            imp.importer(corps(ligne(prix="40", lien=lien), ligne(isbn=ISBN_B, prix="28", lien="https://www.leboncoin.fr/ad/livres/78")), JOUR, d, CONNUES)
            avant = {r["isbn13"]: r["prix_median"] for r in lire(d, "leboncoin-2026-10-24.csv")}
            self.assertEqual(avant[ISBN_A], "40.00")                      # sans registre : le prix entier
            imp.reagreger(d, {lien: lot})
            apres = {r["isbn13"]: r for r in lire(d, "leboncoin-2026-10-24.csv")}
            self.assertEqual(apres[ISBN_A]["prix_median"], "10.00")       # sa part du lot
            self.assertEqual(apres[ISBN_B]["nb_annonces"], "2")           # sa part du lot + son annonce seule
            self.assertEqual(apres[ISBN_B]["prix_min"], "28.00")
            self.assertEqual(apres[ISBN_B]["prix_max"], "30.00")
            imp.reagreger(d, {lien: lot})                                  # rejouer donne le même résultat
            self.assertEqual({r["isbn13"]: r for r in lire(d, "leboncoin-2026-10-24.csv")}, apres)

    def test_les_lots_enregistres_sont_valides(self):
        for lien, lot in imp.charger_lots().items():
            self.assertTrue(lien.startswith("https://www.leboncoin.fr/"))
            self.assertTrue(set(lot["isbns"]) <= set(lot["poids"]) and all(float(v) > 0 for v in lot["poids"].values()))


if __name__ == "__main__":
    unittest.main()
