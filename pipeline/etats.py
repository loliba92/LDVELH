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


DECOTE_ANNONCES_DEFAUT = 0.85     # prix demandé (annonce) -> prix visé : une annonce est un prix de vente affiché, au-dessus du prix qui se conclut


def charger_decote(chemin):
    """Décote des annonces (clé « decote_annonces » de ratios_etats.json, entre 0,5 et 1 ; 1 = aucune correction)."""
    try:
        v = float(json.loads(Path(chemin).read_text(encoding="utf-8"))["decote_annonces"])
        if 0.5 <= v <= 1.0:
            return v
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return DECOTE_ANNONCES_DEFAUT


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
    """Gain applicable à un prix. Un prix du neuf est fiable (gain maximal) ; un prix d'archive ou déduit des autres états n'est fondé
    sur aucune annonce (gain minimal) ; sinon on compte les annonces DISTINCTES : le plus grand nombre vu le même jour (« nb_jour »),
    et non le total additionné sur plusieurs jours, où un même exemplaire revu chaque jour compterait pour plusieurs."""
    if estimation.get("neuf"):
        return gains[3]
    if estimation.get("source") == "archives" or estimation.get("deduit"):
        return gains[0]
    n = estimation.get("nb_jour")
    n = estimation.get("nb") if n is None else n
    return gains[max(0, min(3, int(n or 0)))]


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


# Cohérence et marché, intégrées au calcul : les trois états d'une édition restent cohérents entre eux et ne dépassent pas les annonces en ligne.
BIAIS_BAISSE = 5          # relever un prix coûte 5 fois plus cher que le baisser : l'écart se comble surtout en baissant le prix trop haut
CONVENABLE_MAX = 0.85     # le convenable ne dépasse pas 85 % du bon état
TBE_MAX = 1.9             # le très bon état ne dépasse pas 1,9 fois le bon état
MARGE_MARCHE = 1.05       # une cote est « au-dessus du marché » au-delà de 5 % de l'annonce la plus chère
MIN_ANNONCES_MARCHE = 2   # en dessous de 2 annonces en ligne, on laisse le lissage faire le travail


def plafonner_au_marche(par_etat, annonces):
    """Cible d'un état (avant lissage) ramenée à la médiane de ses annonces en ligne quand elle les dépasse de plus de 5 % et que l'état a au moins
    2 annonces. annonces : {état: [prix des annonces en ligne]}. Un prix validé et le prix du neuf (règle du propriétaire) ne sont jamais touchés.
    Les annonces à 3 fois le très bon état ou plus sont écartées. Renvoie le nombre d'états ramenés."""
    n = 0
    tbe = (par_etat.get("tres_bon") or {}).get("prix")
    for e in ETATS:
        v = par_etat.get(e)
        if not v or not v.get("prix") or v.get("source") in ("validé", "neuf") or v.get("neuf"):
            continue
        prix = [p for p in annonces.get(e, []) if not (tbe and p >= 3 * tbe)]
        if len(prix) >= MIN_ANNONCES_MARCHE and v["prix"] > MARGE_MARCHE * max(prix):
            par_etat[e] = {**v, "prix": round(statistics.median(prix), 2), "source": "actuel", "nature": "annonces", "nb": len(prix),
                           "confiance": "faible", "plafonne_marche": True, "deduit": False}
            n += 1
    return n


def _poids_coherence(v):
    if v.get("source") == "validé":
        return 1000.0                                 # prix du propriétaire : jamais déplacé
    if v.get("source") == "neuf" or v.get("neuf"):
        return 10.0
    if v.get("source") == "archives" or v.get("deduit"):
        return 0.5
    return 1.0 + min(v.get("nb") or 0, 5)


def lisser_coherence(par_etat):
    """Ajustement minimal des trois états : déplacés le moins possible (en pourcentage), les mieux appuyés le moins, avec un biais à la baisse.
    Contraintes : convenable ≤ 85 % du bon état ; bon état ≤ très bon état ≤ 1,9 fois le bon état. Renvoie le nombre d'états déplacés (au moins 2 %)."""
    ks = [e for e in ETATS if par_etat.get(e) and par_etat[e].get("prix")]
    if len(ks) < 2:
        return 0
    u = {k: math.log(par_etat[k]["prix"]) for k in ks}
    w = {k: _poids_coherence(par_etat[k]) for k in ks}
    cons = [("convenable", "bon", math.log(1 / CONVENABLE_MAX), math.inf), ("bon", "tres_bon", 0.0, math.log(TBE_MAX)),
            ("convenable", "tres_bon", math.log(1 / CONVENABLE_MAX), math.inf)]
    cons = [c for c in cons if c[0] in ks and c[1] in ks]
    for _ in range(200):
        ok = True
        for bas, haut, mn, mx in cons:
            d = u[haut] - u[bas]
            cible = mn if d < mn - 1e-9 else mx if d > mx + 1e-9 else None
            if cible is None:
                continue
            ok = False
            g = cible - d
            wb = w[bas] * (BIAIS_BAISSE if g < 0 else 1)
            wh = w[haut] * (BIAIS_BAISSE if g > 0 else 1)
            u[haut] += g * wb / (wb + wh)
            u[bas] -= g * wh / (wb + wh)
        if ok:
            break
    n = 0
    for k in ks:
        nouveau = round(math.exp(u[k]), 2)
        avant = par_etat[k]["prix"]
        if abs(nouveau / avant - 1) >= 0.02:
            par_etat[k] = {**par_etat[k], "prix": nouveau, "coherence": True}
            n += 1
    return n


def rapports_mesures(triplets):
    """triplets : [(convenable, bon, tres_bon)] d'éditions où les trois états ont un prix. Médianes des rapports à titre indicatif."""
    if not triplets:
        return {}
    return {"n": len(triplets),
            "convenable": round(statistics.median(c / t for c, b, t in triplets), 3),
            "bon": round(statistics.median(b / t for c, b, t in triplets), 3)}
