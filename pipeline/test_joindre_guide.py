"""Tests de l'étape qui joint le guide PDF à la publication (.github/scripts/joindre-guide.sh), avec un faux `gh` : artefact présent, absent, incomplet.   python pipeline/test_joindre_guide.py"""
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / ".github" / "scripts" / "joindre-guide.sh"
JETON = "0123456789abcdef0123456789abcdef"


class TestJoindreGuide(unittest.TestCase):
    def lancer(self, liste="123", telechargement="ok", contenu=("pdf", "date")):
        d = Path(tempfile.mkdtemp())
        bin_ = d / "bin"
        bin_.mkdir()
        gh = bin_ / "gh"
        gh.write_text(f"""#!/usr/bin/env bash
if [ "$1 $2" = "run list" ]; then echo "{liste}"; exit 0; fi
if [ "$1 $2" = "run download" ]; then
  [ "{telechargement}" = "ok" ] || exit 1
  while [ $# -gt 0 ]; do [ "$1" = "--dir" ] && dossier="$2"; shift; done
  {'echo "%PDF-1.4 essai" > "$dossier/guide-reference.pdf";' if 'pdf' in contenu else ''}
  {'echo "2026-11-19" > "$dossier/date.txt";' if 'date' in contenu else ''}
  exit 0
fi
exit 1
""")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        (d / "jeton.txt").write_text(JETON + "\n")
        sortie = d / "_site"
        sortie.mkdir()
        r = subprocess.run(["bash", str(SCRIPT), str(sortie), str(d / "jeton.txt")], env={**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}"}, capture_output=True, text=True)
        return r, sortie

    def test_guide_present_est_joint_avec_son_jeton_et_sa_date(self):
        r, sortie = self.lancer()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((sortie / f"guide-reference-{JETON}.pdf").exists())
        self.assertEqual(json.loads((sortie / "data" / "guide.json").read_text()), {"fichier": f"guide-reference-{JETON}.pdf", "date": "2026-11-19"})

    def test_aucune_generation_reussie_la_publication_continue_sans_guide(self):
        r, sortie = self.lancer(liste="")
        self.assertEqual(r.returncode, 0)
        self.assertFalse(any(sortie.rglob("*")))

    def test_artefact_expire_la_publication_continue_sans_guide(self):
        r, sortie = self.lancer(telechargement="echec")
        self.assertEqual(r.returncode, 0)
        self.assertFalse(any(sortie.rglob("*")))

    def test_artefact_incomplet_la_publication_continue_sans_guide(self):
        r, sortie = self.lancer(contenu=("pdf",))
        self.assertEqual(r.returncode, 0)
        self.assertFalse(any(sortie.rglob("*")))


if __name__ == "__main__":
    unittest.main()
