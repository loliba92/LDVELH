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


def repartir(par_etat, ratios):
    """Édition qui a au moins un prix issu d'un relevé actuel : les trois états sont tirés d'un même niveau (en très bon
    état), calculé à partir de tous les états actuels (moyenne géométrique pondérée par la fiabilité de chacun), puis
    multiplié par les rapports (convenable 40 %, bon 60 %). Un état qui n'avait que son archive est remplacé (« déduit »).
    Une édition sans aucun prix actuel n'est pas touchée. Renvoie le nombre d'états dont le prix a changé."""
    actuels = {e: v for e, v in par_etat.items() if v and v.get("prix") and v.get("source") != "archives"}
    if not actuels:
        return 0
    poids = {e: 1 / max(v.get("incertitude") or 0.35, 0.05) ** 2 for e, v in actuels.items()}
    niveau = math.exp(sum(poids[e] * math.log(v["prix"] / ratios[e]) for e, v in actuels.items()) / sum(poids.values()))
    # Plafond : l'édition n'est jamais cotée plus haut que le prix actuel le plus élevé réellement observé. Sans lui, un
    # état observé (bon, convenable) dont les annonces sont presque aussi chères que le très bon état tirerait celui-ci
    # trop haut (bon ÷ 0,6) : le très bon état ressortait au-dessus de ce qu'on voit sur eBay.
    niveau = min(niveau, max(v["prix"] for v in actuels.values()))
    ref = max(actuels.values(), key=lambda v: v.get("date", ""))
    n = 0
    for e in ETATS:
        nouveau = round(niveau * ratios[e], 2)
        v = par_etat.get(e)
        avant = v.get("prix") if v else None
        if v and e in actuels:
            par_etat[e] = {**v, "prix": nouveau, "repartition": True}
        else:
            par_etat[e] = {"prix": nouveau, "source": "archives", "nature": "archives", "nb": 0, "date": ref.get("date"),
                           "confiance": "faible", "deduit": True}
        n += avant is None or abs(avant - nouveau) > 0.005
    return n


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
