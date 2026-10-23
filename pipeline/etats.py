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
ECART_DEFAUT = 1.20      # état supérieur au moins 20 % au-dessus de l'état inférieur quand les prix se contredisent
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


def charger_ecart(chemin):
    """Écart appliqué quand un état supérieur est en dessous d'un état inférieur (clé « ecart_etat_superieur »)."""
    try:
        v = float(json.loads(Path(chemin).read_text(encoding="utf-8"))["ecart_etat_superieur"])
        if 1.0 <= v <= 2.0:
            return v
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return ECART_DEFAUT


def repartir(par_etat, ratios):
    """Édition qui a au moins un prix issu d'un relevé actuel : chaque état OBSERVÉ garde son prix (annonces récentes), les
    états sans annonce récente sont déduits. Le niveau commun (en très bon état) est la moyenne géométrique, pondérée par
    la fiabilité de chacun, des états observés (prix ÷ rapport de l'état) ; un état déduit vaut ce niveau multiplié par son
    rapport (convenable 40 %, bon 60 %, très bon 100 %) et remplace l'éventuelle archive (« déduit », jamais compté comme prix
    actuel). Une édition sans aucun prix actuel n'est pas touchée. Renvoie le nombre d'états dont le prix a changé."""
    actuels = {e: v for e, v in par_etat.items() if v and v.get("prix") and v.get("source") != "archives" and not v.get("mince")}
    if not actuels:
        return 0
    poids = {e: 1 / max(v.get("incertitude") or 0.35, 0.05) ** 2 for e, v in actuels.items()}
    niveau = math.exp(sum(poids[e] * math.log(v["prix"] / ratios[e]) for e, v in actuels.items()) / sum(poids.values()))
    ref = max(actuels.values(), key=lambda v: v.get("date", ""))
    n = 0
    for e in ETATS:
        if e in actuels:
            continue                                                  # état observé : son prix ne bouge pas
        v = par_etat.get(e)
        avant = v.get("prix") if v else None
        nouveau = round(niveau * ratios[e], 2)
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
    actuels = {e: v for e, v in connus.items() if v.get("source") != "archives" and not v.get("mince")}
    refs = actuels or connus                                  # on se fie d'abord aux relevés actuels
    niveau = math.exp(statistics.mean(math.log(v["prix"] / ratios[e]) for e, v in refs.items()))   # prix en « très bon état »
    ref = max(refs.values(), key=lambda v: v.get("date", ""))
    for e in manquants:
        par_etat[e] = {"prix": round(niveau * ratios[e], 2), "source": "archives", "nature": "archives", "nb": 0,
                       "date": ref.get("date"), "confiance": "faible", "deduit": True}
    return len(manquants)


# Lissage quotidien : le prix du jour dépend de celui de la veille.
#     prix du jour = prix de la veille + gain × (cible du jour − prix de la veille)
# La « cible » est l'estimation recalculée chaque jour à partir des données (annonces, archives, rapports entre états). Le gain
# (part de l'écart rattrapée en un jour) dépend de la confiance : plus il y a d'annonces, plus le prix suit vite sa cible.
# Un prix validé par le propriétaire n'est jamais lissé : il remplace la cible, et c'est lui qui sert de prix de la veille ensuite.
GAINS_DEFAUT = {0: 0.10, 1: 0.10, 2: 0.20, 3: 0.30}      # selon le nombre d'annonces (3 = trois ou plus) ; 0 : prix déduit ou d'archive


def charger_gains(chemin):
    """Gains de lissage (clé « gains_lissage » de ratios_etats.json : {"0": …, "1": …, "2": …, "3": …}, chacun entre 0 et 1)."""
    try:
        brut = json.loads(Path(chemin).read_text(encoding="utf-8"))["gains_lissage"]
        gains = {n: float(brut[str(n)]) for n in GAINS_DEFAUT}
        if all(0 < g <= 1 for g in gains.values()):
            return gains
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return dict(GAINS_DEFAUT)


def gain_de(estimation, gains):
    """Gain applicable à un prix : un prix du neuf est fiable (gain maximal) ; sinon on compte les annonces qui le fondent."""
    if estimation.get("neuf"):
        return gains[3]
    return gains[max(0, min(3, int(estimation.get("nb") or 0)))]


def lisser(par_etat, precedents, gains=GAINS_DEFAUT):
    """par_etat : {etat: estimation du jour (la cible)} ; precedents : {etat: prix publié la veille}. Remplace chaque prix par le prix
    lissé et garde la cible dans « cible ». Sans prix de la veille, ou pour un prix validé, rien ne change. Renvoie le nombre de prix lissés."""
    n = 0
    for e in ETATS:
        v, avant = par_etat.get(e), precedents.get(e)
        if not v or not v.get("prix") or not avant or v.get("source") == "validé":
            continue
        nouveau = round(avant + gain_de(v, gains) * (v["prix"] - avant), 2)
        if abs(nouveau - v["prix"]) > 0.005:
            par_etat[e] = {**v, "prix": nouveau, "lisse": True, "cible": v["prix"]}
            n += 1
    return n


def rapports_mesures(triplets):
    """triplets : [(convenable, bon, tres_bon)] d'éditions où les trois états ont un prix. Médianes des rapports à titre indicatif."""
    if not triplets:
        return {}
    return {"n": len(triplets),
            "convenable": round(statistics.median(c / t for c, b, t in triplets), 3),
            "bon": round(statistics.median(b / t for c, b, t in triplets), 3)}
