"""Déduction des états manquants : à partir d'un prix connu dans un état, on estime les autres états de la même édition.

Les trois états sont liés par des rapports relatifs au très bon état (règle du propriétaire : convenable 40 %,
bon 60 %, réglables dans data/manual/ratios_etats.json). Un état qui a déjà un prix n'est jamais modifié ici.
Le prix déduit est marqué « deduit » (confiance faible, jamais compté comme prix actuel).
Les rapports mesurés sur les données (archives, annonces) sont calculés à titre d'information : ils peuvent différer
du réglage du propriétaire, ce que la page de revue permet de constater.
"""
import json
import math
import statistics
from pathlib import Path

ETATS = ("convenable", "bon", "tres_bon")
DEFAUT = {"convenable": 0.40, "bon": 0.60, "tres_bon": 1.0}


def charger_ratios(chemin):
    try:
        brut = json.loads(Path(chemin).read_text(encoding="utf-8"))
        ratios = {e: float(brut[e]) for e in ETATS}
        if all(0 < ratios[e] <= 1.5 for e in ETATS) and ratios["convenable"] <= ratios["bon"] <= ratios["tres_bon"]:
            return ratios
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return dict(DEFAUT)


def completer(par_etat, ratios):
    """par_etat : {etat: estimation} d'une édition. Ajoute les états absents. Renvoie le nombre d'états ajoutés."""
    connus = {e: v for e, v in par_etat.items() if v and v.get("prix")}
    manquants = [e for e in ETATS if not par_etat.get(e)]
    if not connus or not manquants:
        return 0
    actuels = {e: v for e, v in connus.items() if v.get("source") != "archives"}
    refs = actuels or connus                                  # on se fie d'abord aux relevés actuels
    niveau = math.exp(statistics.mean(math.log(v["prix"] / ratios[e]) for e, v in refs.items()))   # prix en « très bon état »
    ref = max(refs.values(), key=lambda v: v.get("date", ""))
    for e in manquants:
        par_etat[e] = {"prix": round(niveau * ratios[e], 2), "source": "archives", "nature": "archives", "nb": 0,
                       "date": ref.get("date"), "confiance": "faible", "deduit": True}
    return len(manquants)


def rapports_mesures(triplets):
    """triplets : [(convenable, bon, tres_bon)] d'éditions où les trois états ont un prix. Médianes des rapports à titre indicatif."""
    if not triplets:
        return {}
    return {"n": len(triplets),
            "convenable": round(statistics.median(c / t for c, b, t in triplets), 3),
            "bon": round(statistics.median(b / t for c, b, t in triplets), 3)}
