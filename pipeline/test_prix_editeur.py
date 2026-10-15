import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prix_editeur as p

NOTICE = """<srw:searchRetrieveResponse xmlns:srw="http://www.loc.gov/zing/srw/"><srw:records><srw:record><srw:recordData>
<mxc:record xmlns:mxc="info:lc/xmlns/marcxchange-v2"><mxc:datafield tag="010" ind1=" " ind2=" ">
<mxc:subfield code="a">978-2-07-514864-1</mxc:subfield><mxc:subfield code="b">br.</mxc:subfield><mxc:subfield code="d">12 EUR</mxc:subfield>
</mxc:datafield></mxc:record></srw:recordData></srw:record></srw:records></srw:searchRetrieveResponse>"""


class TestPrixEditeur(unittest.TestCase):
    def test_lire_prix(self):
        self.assertEqual(p.lire_prix("12 EUR"), (12.0, "EUR"))
        self.assertEqual(p.lire_prix("14,95 EUR"), (14.95, "EUR"))
        self.assertEqual(p.lire_prix("29 F"), (29.0, "FRF"))
        self.assertEqual(p.lire_prix("gratuit"), (None, None))
        self.assertEqual(p.lire_prix(None), (None, None))
        self.assertEqual(p.lire_prix("1200 EUR"), (None, None))        # aberrant

    def test_prix_de_notice(self):
        self.assertEqual(p.prix_de_notice(NOTICE), "12 EUR")
        self.assertIsNone(p.prix_de_notice(NOTICE.replace('code="d"', 'code="z"')))
        self.assertIsNone(p.prix_de_notice("pas du xml"))


if __name__ == "__main__":
    unittest.main()
