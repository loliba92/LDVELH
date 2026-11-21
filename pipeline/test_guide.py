"""Tests du guide de référence en PDF (données de test petites, aucun réseau).   python pipeline/test_guide.py"""
import re
import socket
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guide as g
import guide_analyse as ga


def livre(titre, serie, numero, version, couverture=None, prix=(5.0, 8.0, 12.5), niveau="rare", editeur="Gallimard"):
    return {"editeur": editeur, "titre": titre, "serie": serie, "numero": numero, "version": version, "version_n": int(version[1:]), "couverture": couverture,
            "rarete": {"niveau": niveau}, "prix": {"convenable": prix[0], "bon": prix[1], "tres_bon": prix[2]}}


class TestGuide(unittest.TestCase):
    def setUp(self):
        self.web = Path(tempfile.mkdtemp())
        (self.web / "covers").mkdir()
        Image.new("RGB", (320, 523), (120, 40, 50)).save(self.web / "covers" / "a.webp", "WEBP")
        self.versions = [livre("Zèbre", "Série B", "2", "V1", "covers/a.webp"), livre("Alpha", "Série A", "10", "V1", "covers/a.webp"),
                         livre("Beta", "Série A", "2", "V2", "covers/absente.webp", prix=(None, None, None)), livre("Beta", "Série A", "2", "V1")]

    def test_plan_editeur_version_serie(self):
        v = [livre("A", "Série B", "2", "V10"), livre("B", "Série B", "10", "V2"), livre("C", "Série A", "3", "V2"), livre("D", "Série A", "1", "V1"), livre("E", "Série A", "2", "V2"),
             livre("F", "X", "1", "V1", editeur="Alkonost"), livre("G", "Y", "1", "V1", editeur="<span>page copiée</span>"), livre("H", "Z", "1", "V1", editeur="Jean Nugent")]
        r = g.grouper(v)
        self.assertEqual([e for e, _ in r], ["Gallimard", "Alkonost", "Autres éditeurs"])          # le plus fourni d'abord, « Autres éditeurs » en dernier
        gal = dict(r)["Gallimard"]
        self.assertEqual([ver for ver, _ in gal], ["V1", "V2", "V10"])                              # ordre naturel, jamais V1 et V2 mélangés
        self.assertEqual([[(s, [x["titre"] for x in l]) for s, l in series] for _, series in gal][1], [("Série A", ["E", "C"]), ("Série B", ["B"])])   # séries alphabétiques, livres par numéro
        self.assertEqual(len(dict(r)["Autres éditeurs"][0][1][0][1]) + len(dict(r)["Autres éditeurs"][0][1]), 3)       # deux livres sans éditeur reconnu, deux séries

    def test_un_editeur_inconnu_ou_vide_va_dans_autres(self):
        self.assertEqual(g.editeur_de({"editeur": "Gallimard"}), "Gallimard")
        self.assertEqual(g.editeur_de({"editeur": ""}), "Autres éditeurs")
        self.assertEqual(g.editeur_de({}), "Autres éditeurs")
        self.assertEqual(g.editeur_de({"editeur": "R.L Stine"}), "Autres éditeurs")

    def test_filtres_d_essai(self):
        r = g.grouper(self.versions, {"Série B"})
        self.assertEqual([s for _, vs in r for _, ss in vs for s, _ in ss], ["Série B"])
        self.assertEqual([e for e, _ in g.grouper(self.versions, editeurs={"Alkonost"})], [])

    def test_formats(self):
        self.assertEqual(g.date_longue("2026-11-01"), "1er novembre 2026")

    def test_reperes_en_mots_memes_seuils_que_le_site(self):
        self.assertEqual([g.niveau_prix(v) for v in (None, 5, 10, 19.9, 20, 45, 70, 200)], [None, 1, 2, 2, 3, 4, 5, 5])
        self.assertEqual([g.MOTS_PRIX[n - 1] for n in (1, 2, 3, 4, 5)], ["pas cher", "abordable", "moyen", "cher", "très cher"])
        self.assertEqual([g.mot_offre(n) for n in (0, 1, 2, 3, 4, 9, 10, 50)], ["introuvable", "rare", "peu d'annonces", "peu d'annonces", "courant", "courant", "abondant", "abondant"])
        self.assertEqual(g.mot_offre(0, neuf=True), "disponible neuf")

    def test_aucun_montant_ni_decimal_dans_le_catalogue(self):
        import re
        for style in g.STYLES:
            for v in self.versions:
                v = dict(v, isbn13="9780000000001")
                f = g.Fiche(v, g.STYLES[style], ("Times-Roman", "Times-Bold", "Helvetica", "Helvetica-Bold"), self.web, {"9780000000001": {"vin": 7}})
                for texte in f.libelles():
                    self.assertNotIn("€", texte)
                    self.assertIsNone(re.search(r"\d+[,.]\d+", texte), texte)
        f = g.Fiche(self.versions[0], g.STYLES["nuit"], ("Times-Roman", "Times-Bold", "Helvetica", "Helvetica-Bold"), self.web, {})
        self.assertIn("En vente", f.libelles())
        self.assertIn("Prix d'occasion", f.libelles())
        self.assertFalse(any(x in " ".join(f.libelles()).split() for x in ("C", "BE", "TBE")))
        self.assertNotIn("Rare", " ".join(f.meta.split(" · ")[1:]))          # plus de rareté structurelle à côté du numéro et de la version

    def test_pdf_genere_sans_montant_ni_decimal(self):
        import re
        import shutil
        import subprocess
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext absent")
        sortie = self.web / "t.pdf"
        g.construire(self.versions, sortie, "2026-11-19", web=self.web, genere_le="2026-11-19", donnees={"offre": {}})
        texte = subprocess.run(["pdftotext", str(sortie), "-"], capture_output=True, text=True).stdout
        self.assertRegex(texte, r"moins de 10\s€")          # l'échelle des prix de la légende, seul endroit des fourchettes
        self.assertRegex(texte, r"70\s€ et plus")
        self.assertIsNone(re.search(r"\d+[,.]\d+", texte.split("Le radar du héros")[0].split("Sommaire")[0]))          # ni décimal dans l'introduction ni dans la légende
        for mot in ("convenable", "bon état", "très bon état"):
            self.assertNotIn(mot, texte.lower())          # aucune explication des états
        self.assertIn("Ces repères sont ceux du", texte)
        self.assertNotIn("sans publicité", texte.lower())

    def test_jaquette_absente_ou_illisible(self):
        self.assertIsNone(g.jaquette_jpeg(self.web / "covers" / "absente.webp"))
        (self.web / "covers" / "x.webp").write_bytes(b"pas une image")
        self.assertIsNone(g.jaquette_jpeg(self.web / "covers" / "x.webp"))
        self.assertTrue(g.jaquette_jpeg(self.web / "covers" / "a.webp").startswith(b"\xff\xd8"))

    def test_les_deux_styles_et_les_metadonnees(self):
        for style in ("nuit", "parchemin"):
            sortie = self.web / f"{style}.pdf"
            g.construire(self.versions, sortie, "2026-11-19", web=self.web, genere_le="2026-11-19", style=style, mention=(style == "nuit"))
            donnees = sortie.read_bytes()
            self.assertIn("La Cote du Héros".encode("latin-1", "replace")[:10], donnees)
            self.assertIn(b"/Author (La Cote du H", donnees)
            self.assertIn(b"lacoteduheros.fr", donnees)          # lien du site (annotation cliquable)

    def test_pas_de_sans_publicite(self):
        for f in ("guide.py", "guide_analyse.py"):
            self.assertNotIn("sans publicité", (Path(__file__).resolve().parent / f).read_text(encoding="utf-8").lower())

    def test_pdf_complet_sans_reseau(self):
        def interdit(*a, **k):
            raise AssertionError("requête réseau")
        reel, socket.socket.connect = socket.socket.connect, interdit
        try:
            sortie = self.web / "g.pdf"
            nb = g.construire(self.versions, sortie, "2026-11-19", web=self.web, genere_le="2026-11-19")
        finally:
            socket.socket.connect = reel
        self.assertEqual(nb, 4)
        donnees = sortie.read_bytes()
        self.assertTrue(donnees.startswith(b"%PDF"))
        self.assertGreaterEqual(donnees.count(b"/Type /Page\n") + donnees.count(b"/Type /Page "), 5)          # couverture, présentation, sommaire, deux séries

    def test_couverture_titre_et_date(self):
        import shutil
        import subprocess
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext absent")
        for variante in ("or", "creme"):
            g.TITRE_COUVERTURE = variante
            sortie = self.web / f"c-{variante}.pdf"
            g.construire(self.versions, sortie, "2026-11-19", web=self.web, genere_le="2026-11-19")
            texte = subprocess.run(["pdftotext", "-f", "1", "-l", "1", str(sortie), "-"], capture_output=True, text=True).stdout
            for attendu in ("LA COTE", "DU HÉROS", "GUIDE DE RÉFÉRENCE", "Édition du 19 novembre 2026"):
                self.assertIn(attendu, texte)
        g.TITRE_COUVERTURE = "or"


class TestRadar(unittest.TestCase):
    def setUp(self):
        noms = (("Gallimard", "Serie Alpha"), ("Gallimard", "Serie Beta"), ("Gallimard", "Serie Gamma"), ("Alkonost", "Serie Delta"), ("Hachette", "Serie Epsilon"))
        self.v, self.offre, k = [], {}, 0
        for i, (e, s) in enumerate(noms):
            for j in range(5):
                k += 1
                isbn = f"97800000{k:05d}"
                self.v.append({"isbn13": isbn, "titre": f"Livre {k}", "serie": s, "editeur": e, "version": f"V{j % 2 + 1}", "prix": {"bon": 6.0 + 9 * i, "tres_bon": 8.0 + 12 * i}})
                self.offre[isbn] = {"vin": (5 - i) * 3, "lbc": 1, "ebay": i % 2, "lib": 1 if i == 0 else 0}
        self.polices = ("Times-Roman", "Times-Bold", "Helvetica", "Helvetica-Bold")

    def section(self):
        styles = {k: g.ParagraphStyle(k) for k in ("corps", "h1", "h1m", "h2", "toc", "puce_radar")}
        return g.section_radar(self.v, {"offre": self.offre}, styles, "2026-11-19", self.polices, g.STYLES["nuit"])

    def textes(self, flowables):
        from reportlab.graphics.shapes import Drawing
        from reportlab.platypus import KeepTogether, Paragraph, Table
        sortie = []
        def parcourir(f):
            if isinstance(f, Paragraph):
                sortie.append(f.getPlainText())
            elif isinstance(f, Drawing):
                sortie.extend(getattr(x, "text", "") for x in f.contents)
            elif isinstance(f, KeepTogether):
                for x in f._content:
                    parcourir(x)
            elif isinstance(f, Table):
                for ligne in f._cellvalues:
                    for cellule in ligne:
                        for x in (cellule if isinstance(cellule, list) else [cellule]):
                            parcourir(x)
        for f in flowables:
            parcourir(f)
        return sortie

    def test_profils_une_serie_par_editeur_avec_assez_d_editions(self):
        profs = ga.profils(self.v, self.offre, g.editeur_de)
        self.assertEqual(len(profs), 5)
        self.assertEqual(ga.profils(self.v[:3], self.offre, g.editeur_de), [])          # trop peu d'éditions

    def test_zones_comme_le_radar_du_site(self):
        self.assertEqual([ga.quadrant(o, c, 5, 20) for o, c in ((1, 10), (9, 10), (1, 30), (9, 30))], [0, 1, 2, 3])
        self.assertEqual(sorted(ga.ZONES.values()), sorted(["Peu d'annonces, cher", "Beaucoup d'annonces, cher", "Peu d'annonces, bon marché", "Beaucoup d'annonces, bon marché"]))

    def test_le_chapitre_radar_ne_chiffre_que_les_medianes_et_les_graduations(self):
        textes = self.textes(self.section())
        self.assertGreater(len(textes), 20)
        graduation = lambda t: bool(re.fullmatch(r"\d+(\u00a0€)?", t))          # repères des axes : « 10 » annonces ou « 10 € »
        for t in textes:          # le reste du chapitre reste en mots
            sans_zone = re.sub(r"[Zz]one [1-4]", "zone", t)          # le numéro d'une zone n'est pas un chiffre de marché
            self.assertTrue("médiane" in t or graduation(t) or not any(ch.isdigit() for ch in sans_zone), t)
        self.assertEqual(len([t for t in textes if "médiane de l'offre" in t and "médiane des prix" in t]), 1)
        self.assertTrue(any(graduation(t) and t.endswith("€") for t in textes), "graduations de prix")
        self.assertTrue(any(graduation(t) and not t.endswith("€") for t in textes), "graduations d'annonces")

    def test_pas_de_ce_livre_et_un_radar_par_grand_editeur(self):
        textes = " ".join(self.textes(self.section()))
        self.assertNotIn("Ce livre", textes)
        self.assertIn("Gallimard", textes)
        profs = ga.profils(self.v, self.offre, g.editeur_de)
        self.assertEqual(ga.grands_editeurs(profs), ["Gallimard"])

    def test_chaque_serie_est_etiquetee_editeur_et_serie(self):
        profs = ga.profils(self.v, self.offre, g.editeur_de)
        pts = ga.points_editions(self.v, self.offre)
        d = ga.dessiner_radar(pts, [p for p in profs if p["editeur"] == "Gallimard"], 182 * g.mm, 90 * g.mm)
        etiquettes = [getattr(x, "text", "") for x in d.contents]
        self.assertTrue(any(t.startswith("Gallimard · Serie") for t in etiquettes))
        for mot in ("peu d'annonces", "beaucoup d'annonces", "cher", "pas cher"):
            self.assertIn(mot, etiquettes)

    def test_verdicts_et_series_a_surveiller_en_mots(self):
        profs = ga.profils(self.v, self.offre, g.editeur_de)
        pts = ga.points_editions(self.v, self.offre)
        for _, phrase in ga.verdicts_editeur([p for p in profs if p["editeur"] == "Gallimard"], pts):
            self.assertFalse(any(ch.isdigit() for ch in re.sub(r"[Zz]one [1-4]", "zone", phrase)), phrase)
        tendues, faciles = ga.series_a_surveiller(profs, pts)
        for e, s, mot in tendues + faciles:
            self.assertIn("à trouver", mot)
        self.assertTrue(ga.lecture_globale(pts))

    def test_les_plateformes_ne_sont_pas_nommees_dans_la_methode(self):
        source = (Path(__file__).resolve().parent / "guide.py").read_text(encoding="utf-8")
        methode = source[source.index("Les cotes sont des estimations"):source.index("Le radar de tout le guide")]
        for nom in ("Vinted", "Leboncoin", "eBay"):
            self.assertNotIn(nom, methode)

    def test_le_pdf_ne_contient_pas_de_sans_publicite(self):
        for f in ("guide.py", "guide_analyse.py"):
            self.assertNotIn("sans publicité", (Path(__file__).resolve().parent / f).read_text(encoding="utf-8").lower())

    def test_aucune_abreviation_d_etat_dans_le_pdf(self):
        import re
        import shutil
        import subprocess
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext absent")
        sortie = Path(tempfile.mkdtemp()) / "e.pdf"
        g.construire(self.v, sortie, "2026-11-19", web=Path(tempfile.mkdtemp()), genere_le="2026-11-19", donnees={"offre": self.offre})
        texte = subprocess.run(["pdftotext", str(sortie), "-"], capture_output=True, text=True).stdout
        self.assertIsNone(re.search(r"\b(C|BE|TBE)\b", texte), "abréviation d'état trouvée")
        for mot in ("convenable", "bon état", "très bon état"):
            self.assertNotIn(mot, texte.lower())

    def test_une_serie_courte_n_est_jamais_coupee_ni_une_rangee_isolee(self):
        v = [livre(f"L{k}", f"Série {c}", str(k), "V1") for c, n in (("A", 8), ("B", 10), ("C", 6), ("D", 9), ("E", 7), ("F", 28)) for k in range(1, n + 1)]
        evenements = []
        origine = g.Fiche.draw
        legende = {"en_cours": False}
        origine_annotee = g.FicheAnnotee.draw

        def annotee(self):          # la fiche d'exemple de la légende n'est pas une fiche du catalogue
            legende["en_cours"] = True
            origine_annotee(self)
            legende["en_cours"] = False
        g.FicheAnnotee.draw = annotee
        g.Fiche.draw = lambda self: (None if legende["en_cours"] else evenements.append((self.canv.getPageNumber(), self.v["serie"])), origine(self))[1]
        try:
            g.construire(v, Path(tempfile.mkdtemp()) / "m.pdf", "2026-11-19", web=Path(tempfile.mkdtemp()), genere_le="2026-11-19", donnees=False)
        finally:
            g.Fiche.draw = origine
            g.FicheAnnotee.draw = origine_annotee
        passes = [[]]
        for e in evenements:          # la construction se fait en plusieurs passes : seule la dernière compte
            if passes[-1] and e[0] < passes[-1][-1][0]:
                passes.append([])
            passes[-1].append(e)
        pages = {}
        for page, serie in passes[-1]:
            pages.setdefault(serie, []).append(page)
        for serie in "ABCDE":
            self.assertEqual(len(set(pages[f"Série {serie}"])), 1, f"Série {serie} coupée")
        self.assertGreater(len(set(pages["Série F"])), 1)          # une longue série passe sur plusieurs pages
        self.assertGreaterEqual(pages["Série F"].count(pages["Série F"][-1]), 6)          # la dernière page garde au moins deux rangées


    def test_une_page_de_methode_explique_le_nuage_et_les_zones_avant_le_sommaire(self):
        import re
        import shutil
        import subprocess
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext absent")
        sortie = Path(tempfile.mkdtemp()) / "n.pdf"
        g.construire(self.v, sortie, "2026-11-19", web=Path(tempfile.mkdtemp()), genere_le="2026-11-19", donnees={"offre": self.offre})
        texte = subprocess.run(["pdftotext", str(sortie), "-"], capture_output=True, text=True).stdout
        self.assertLess(texte.index("La méthode : le nuage et ses quatre zones"), texte.index("Sommaire"))
        plat = texte.replace("\n", " ")
        self.assertRegex(plat, r"\d+(,\d)? annonces par édition \(médiane de l'offre\)")
        self.assertRegex(plat, r"\d+(,\d{2})? € \(médiane des prix\)")
        for n in "1234":
            self.assertIn(f"Zone {n}", plat)
        self.assertIn("Chaque livre du guide porte sa zone", plat)

    def test_chaque_livre_porte_sa_zone_de_1_a_4_ou_aucune(self):
        pts = ga.points_editions(self.v, self.offre)
        med_o, med_c = 0, 0
        import statistics
        med_o, med_c = statistics.median(n for n, _ in pts), statistics.median(p for _, p in pts)
        zones = {ga.quadrant(ga.nb_annonces(self.offre.get(v["isbn13"])), ga.cote(v), med_o, med_c) for v in self.v if v.get("isbn13") and ga.cote(v) > 0}
        self.assertTrue(zones <= {0, 1, 2, 3} and len(zones) >= 2)
        f = g.Fiche(self.v[0], g.STYLES["parchemin"], ("Helvetica",) * 4, self.web if hasattr(self, "web") else Path("."), self.offre, "jauge", 3)
        self.assertIn("Zone 2", f.libelles())          # quadrant 3 : zone 2
        self.assertNotIn("Zone", " ".join(g.Fiche(self.v[0], g.STYLES["parchemin"], ("Helvetica",) * 4, Path("."), self.offre, "jauge").libelles()))


if __name__ == "__main__":
    unittest.main()
