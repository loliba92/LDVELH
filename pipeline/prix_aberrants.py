"""Annonces à prix aberrant : 3 fois le prix du très bon état de leur édition, ou plus. Elles restent affichées mais sont écartées de la cote."""
import json
from pathlib import Path

SEUIL = 3          # décision du propriétaire : à partir de 3 fois le très bon état, le prix est jugé fou ou trompeur
REVUE = Path(__file__).resolve().parent.parent / "web" / "data" / "revue.json"


def charger_tbe(chemin=None):
    """{isbn13: prix publié du très bon état}, lu dans le dernier fichier de revue des prix ; vide si le fichier manque."""
    try:
        lignes = json.loads(Path(chemin or REVUE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {l["isbn"]: float(l["publie"]) for l in lignes if l.get("etat") == "tres_bon" and l.get("isbn") and l.get("publie")}


def est_aberrant(prix, prix_tbe):
    """Vrai si le prix atteint SEUIL fois le prix du très bon état. Sans prix de référence, aucune annonce n'est écartée."""
    return bool(prix_tbe) and prix >= SEUIL * prix_tbe
