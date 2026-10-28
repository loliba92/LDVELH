"""Retrouve la première apparition de chaque annonce dans l'historique git des relevés (data/raw/occasion/annonces-*.csv).

    python pipeline/premieres_historiques.py          # écrit data/manual/premieres_historiques.json

Pour une annonce (reconnue à son lien), la première apparition est l'heure (UTC, à la minute) du premier envoi de données qui la contient.
Le fichier sert d'amorce à `export_site.premieres_vues` : les annonces déjà en ligne avant que le site retienne l'heure reçoivent ainsi leur heure réelle
au lieu d'une simple date. À relancer seulement pour reprendre un historique plus ancien ; l'historique git doit être complet (git fetch --unshallow).
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "data" / "manual" / "premieres_historiques.json"
LIEN = re.compile(r"https?://[^,\s\"]+")


def minute_utc(iso):
    return datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def lire_historique(sortie_git):
    """Analyse la sortie de `git log --reverse --no-renames -p --format=@@%aI` : {lien: première heure}."""
    premieres, quand, fichier = {}, None, ""
    for ligne in sortie_git.splitlines():
        if ligne.startswith("@@") and re.match(r"@@\d{4}-", ligne):
            quand = minute_utc(ligne[2:])
        elif ligne.startswith("diff --git "):
            fichier = ligne.split(" b/", 1)[-1]
        elif ligne.startswith("+") and not ligne.startswith("+++") and quand and Path(fichier).name.startswith("annonces-"):
            m = LIEN.search(ligne)
            if m and m.group(0) not in premieres:
                premieres[m.group(0)] = quand
    return premieres


def main():
    sortie_git = subprocess.run(["git", "log", "--reverse", "--no-renames", "-p", "--format=@@%aI", "--", "data/raw/occasion"],
                                cwd=RACINE, capture_output=True, text=True, check=True).stdout
    premieres = lire_historique(sortie_git)
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps(dict(sorted(premieres.items())), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(premieres)} annonces datées dans {SORTIE.relative_to(RACINE)}")


if __name__ == "__main__":
    sys.exit(main())
