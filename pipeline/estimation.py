"""Estimation du prix d'une édition, pour un état, à partir de ses observations.

Principe (voir docs/MODELE-PRICING.md) : prix lissé observation après observation (voir `lisser`). Les poids
ci-dessous servent à qualifier le résultat (source, nature, confiance). Chaque observation pèse selon
  - sa nature (une vente réelle compte plus qu'une annonce, qui compte plus qu'un ancien relevé) ;
  - sa fraîcheur (le poids est divisé par deux tous les 90 jours ; 365 jours pour l'ancien relevé) ;
  - le nombre d'annonces qu'elle résume (racine carrée, plafonnée à 9 annonces).
Un relevé de moins de 3 annonces n'est pas pris en compte : une annonce isolée peut être absurde.
Les prix demandés ne sont pas corrigés : faute de ventes réelles, on ne sait pas mesurer l'écart
entre prix demandé et prix payé. Le résultat l'indique (« annonces »).
"""
from collections import namedtuple
from datetime import date
from math import exp, log, sqrt

Obs = namedtuple("Obs", "prix type date nb")

POIDS_TYPE = {"vente_reelle": 1.0, "vente_probable": 0.6, "rachat": 0.4, "prix_demande": 0.3, "historique": 0.2}
ACTUELS = {"vente_reelle", "vente_probable", "rachat", "prix_demande"}
NATURE = {"vente_reelle": "ventes", "vente_probable": "ventes", "rachat": "rachats", "prix_demande": "annonces"}
DEMI_VIE = {"historique": 365}
DEMI_VIE_DEFAUT = 90
PLAFOND_ANNONCES = 9
MIN_ANNONCES = 3        # en dessous, un relevé d'annonces est trop mince pour fonder une cote (une annonce isolée peut être absurde)
# Lissage : le prix est mis à jour observation après observation (filtre de Kalman en logarithme).
# Chaque observation a une incertitude (écart-type du logarithme du prix) selon sa nature, divisée par le nombre
# d'annonces qu'elle résume ; le prix dérive avec le temps (BRUIT_SEMAINE), donc une donnée ancienne perd du poids
# toute seule ; une valeur très éloignée de l'estimation en cours est amortie (ECART_ALERTE).
SIGMA = {"vente_reelle": 0.15, "vente_probable": 0.22, "rachat": 0.30, "prix_demande": 0.35, "historique": 0.25}
BRUIT_SEMAINE = 0.02    # variance de dérive du log du prix par semaine
ECART_ALERTE = 3.0      # au-delà de 3 écarts-types, l'observation est jugée suspecte et son poids divisé par 4
SEUIL_ACTUEL = 0.7      # part du poids venant d'observations actuelles pour parler de cote « actuelle »


def poids(o, aujourdhui):
    age = max(0, (aujourdhui - o.date).days)
    demi_vie = DEMI_VIE.get(o.type, DEMI_VIE_DEFAUT)
    return POIDS_TYPE[o.type] * 0.5 ** (age / demi_vie) * sqrt(min(max(o.nb, 1), PLAFOND_ANNONCES))


def lisser(observations, aujourdhui, sigma_hist=None):
    """Prix lissé (filtre de Kalman en log) : renvoie (prix, incertitude). Les observations sont lues dans l'ordre
    des dates ; chaque nouvelle valeur corrige l'estimation d'une part (le « gain ») d'autant plus grande qu'elle
    est précise (nature, nombre d'annonces) et que l'estimation précédente est ancienne."""
    m = var = derniere = None
    for o in sorted(observations, key=lambda x: x.date):
        sigma = sigma_hist if (o.type == "historique" and sigma_hist) else SIGMA[o.type]
        r = sigma ** 2 / min(max(o.nb, 1), PLAFOND_ANNONCES)
        y = log(o.prix)
        if m is None:
            m, var = y, r
        else:
            var += BRUIT_SEMAINE * max(0, (o.date - derniere).days) / 7
            if abs(y - m) > ECART_ALERTE * sqrt(var + r):
                r *= 4
            gain = var / (var + r)
            m += gain * (y - m)
            var *= 1 - gain
        derniere = o.date
    var += BRUIT_SEMAINE * max(0, (aujourdhui - derniere).days) / 7
    return exp(m), sqrt(var)


def mediane_ponderee(points):
    """points : liste de (prix, poids). Renvoie la médiane pondérée (moyenne des deux valeurs centrales en cas d'égalité)."""
    pts = sorted(points)
    total = sum(w for _, w in pts)
    moitie, cumul = total / 2, 0.0
    for i, (prix, w) in enumerate(pts):
        cumul += w
        if cumul > moitie + 1e-12:
            return prix
        if abs(cumul - moitie) <= 1e-12 and i + 1 < len(pts):
            return (prix + pts[i + 1][0]) / 2
    return pts[-1][0]


def estimer(observations, aujourdhui=None, sigma_hist=None):
    """Renvoie un dict {prix, source, nature, nb, date, confiance} ou None s'il n'y a aucune observation.

    source : « archives » (aucune observation actuelle), « actuel » ou « mixte ».
    nature : « annonces », « ventes », « rachats » (observation actuelle dominante) ou « archives ».
    sigma_hist : incertitude de l'archive (écart-type du log du prix), apprise par le modèle ; défaut SIGMA["historique"].
    confiance : « ancienne » pour les archives ; « faible », « moyenne » ou « élevée » pour le reste.
    """
    aujourdhui = aujourdhui or date.today()
    obs = [o for o in observations if not (o.type == "prix_demande" and o.nb < MIN_ANNONCES)]
    if not obs:
        return None
    poids_obs = [(o, poids(o, aujourdhui)) for o in obs]
    prix, _incertitude = lisser(obs, aujourdhui, sigma_hist)
    actuelles = [(o, w) for o, w in poids_obs if o.type in ACTUELS]
    w_actuel = sum(w for _, w in actuelles)
    w_total = sum(w for _, w in poids_obs)
    if not actuelles:
        source, nature, confiance = "archives", "archives", "ancienne"
        nb, d = len(obs), max(o.date for o in obs)
    else:
        source = "actuel" if w_actuel / w_total >= SEUIL_ACTUEL else "mixte"
        dominante = max(actuelles, key=lambda x: x[1])[0]
        nature = NATURE[dominante.type]
        nb = sum(o.nb for o, _ in actuelles if NATURE[o.type] == nature)   # seulement la nature dominante
        d = max(o.date for o, _ in actuelles)
        confiance = "faible" if w_actuel < 0.5 else ("moyenne" if w_actuel < 0.85 else "élevée")
    return {"prix": round(prix, 2), "source": source, "nature": nature, "nb": nb,
            "date": d.isoformat(), "confiance": confiance}
