"""Estimation du prix d'une édition, pour un état, à partir de ses observations.

Principe (voir docs/MODELE-PRICING.md) : prix lissé observation après observation (voir `lisser`). Les poids
ci-dessous servent à qualifier le résultat (source, nature, confiance). Chaque observation pèse selon
  - sa nature (une vente réelle compte plus qu'une annonce, qui compte plus qu'un ancien relevé) ;
  - sa fraîcheur (le poids est divisé par deux tous les 90 jours ; 365 jours pour l'ancien relevé) ;
  - le nombre d'annonces qu'elle résume (racine carrée, plafonnée à 9 annonces).
Un relevé mince (moins de 3 annonces) compte, mais peu : son incertitude est plus grande, et une valeur très éloignée de
l'estimation en cours est vite écartée (voir ECART_ALERTE_MINCE) : une annonce isolée peut être absurde.
Les prix demandés ne sont pas corrigés : faute de ventes réelles, on ne sait pas mesurer l'écart
entre prix demandé et prix payé. Le résultat l'indique (« annonces »).
"""
from collections import namedtuple
from datetime import date
from math import exp, log, sqrt
from statistics import median

Obs = namedtuple("Obs", "prix type date nb")

POIDS_TYPE = {"vente_reelle": 1.0, "vente_probable": 0.6, "rachat": 0.4, "prix_demande": 0.3, "historique": 0.2}
ACTUELS = {"vente_reelle", "vente_probable", "rachat", "prix_demande"}
NATURE = {"vente_reelle": "ventes", "vente_probable": "ventes", "rachat": "rachats", "prix_demande": "annonces"}
DEMI_VIE = {"historique": 365}
DEMI_VIE_DEFAUT = 90
PLAFOND_ANNONCES = 9
NB_SOLIDE = 6           # cumulées sur plusieurs jours, 6 annonces suffisent aussi à fonder une cote solide
NB_FIABLE = 3           # à partir de 3 annonces le même jour, un relevé est jugé solide ; en dessous il compte, avec plus de prudence
# Lissage : le prix est mis à jour observation après observation (filtre de Kalman en logarithme).
# Chaque observation a une incertitude (écart-type du logarithme du prix) selon sa nature, divisée par le nombre
# d'annonces qu'elle résume ; le prix dérive avec le temps (BRUIT_SEMAINE), donc une donnée ancienne perd du poids
# toute seule ; une valeur très éloignée de l'estimation en cours est amortie (ECART_ALERTE).
SIGMA = {"vente_reelle": 0.15, "vente_probable": 0.22, "rachat": 0.30, "prix_demande": 0.35, "historique": 0.25}
BRUIT_SEMAINE = 0.02    # variance de dérive du log du prix par semaine
ECART_ALERTE = 3.0      # au-delà de 3 écarts-types, l'observation est jugée suspecte et son poids divisé par 4
ECART_ALERTE_MINCE = 1.5  # pour un relevé de moins de NB_FIABLE annonces, on est plus strict : 1,5 écart-type
FACTEUR_MINCE = 2.0     # l'incertitude d'un relevé mince (moins de NB_FIABLE annonces) est multipliée par 2 : il déplace peu l'estimation
FACTEUR_ABERRANT = 2.5  # un relevé mince dont le prix s'écarte de plus de 2,5 fois de l'archive est écarté (annonce isolée absurde)
SEUIL_ACTUEL = 0.7      # part du poids venant d'observations actuelles pour parler de cote « actuelle »


def poids(o, aujourdhui):
    age = max(0, (aujourdhui - o.date).days)
    demi_vie = DEMI_VIE.get(o.type, DEMI_VIE_DEFAUT)
    return POIDS_TYPE[o.type] * 0.5 ** (age / demi_vie) * sqrt(min(max(o.nb, 1), PLAFOND_ANNONCES))


def lisser(observations, aujourdhui, sigma_hist=None, jours_minces=()):
    """Prix lissé (filtre de Kalman en log) : renvoie (prix, incertitude). Les observations sont lues dans l'ordre
    des dates ; chaque nouvelle valeur corrige l'estimation d'une part (le « gain ») d'autant plus grande qu'elle
    est précise (nature, nombre d'annonces) et que l'estimation précédente est ancienne."""
    m = var = derniere = None
    for o in sorted(observations, key=lambda x: x.date):
        sigma = sigma_hist if (o.type == "historique" and sigma_hist) else SIGMA[o.type]
        r = (sigma * (FACTEUR_MINCE if (o.type == "prix_demande" and o.date in jours_minces) else 1)) ** 2 / min(max(o.nb, 1), PLAFOND_ANNONCES)
        y = log(o.prix)
        if m is None:
            m, var = y, r
        else:
            var += BRUIT_SEMAINE * max(0, (o.date - derniere).days) / 7
            seuil = ECART_ALERTE_MINCE if (o.type == "prix_demande" and o.date in jours_minces) else ECART_ALERTE
            if abs(y - m) > seuil * sqrt(var + r):
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
    par_jour = {}                                              # annonces d'un même jour, toutes sources confondues (2 eBay + 1 librairie = 3)
    for o in observations:
        if o.type == "prix_demande":
            par_jour[o.date] = par_jour.get(o.date, 0) + o.nb
    jours_minces = {j for j, n in par_jour.items() if n < NB_FIABLE}
    archive = [o.prix for o in observations if o.type == "historique"]
    ref = median(archive) if archive else None
    def aberrante(o):                                         # relevé mince très éloigné de l'archive : on ne le croit pas
        return o.type == "prix_demande" and o.date in jours_minces and ref and abs(log(o.prix / ref)) > log(FACTEUR_ABERRANT)
    obs = [o for o in observations if not aberrante(o)]
    if not obs:
        return None
    poids_obs = [(o, poids(o, aujourdhui)) for o in obs]
    prix, incertitude = lisser(obs, aujourdhui, sigma_hist, jours_minces)
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
    res = {"prix": round(prix, 2), "source": source, "nature": nature, "nb": nb,
           "date": d.isoformat(), "confiance": confiance, "incertitude": round(incertitude, 3)}
    if source != "archives" and nature == "annonces" and nb < NB_SOLIDE and not any(par_jour.get(o.date, 0) >= NB_FIABLE for o, _ in actuelles):
        res["mince"] = True        # ni 3 annonces le même jour ni 6 au total : compte comme prix récent, mais ne sert pas à déduire les autres états
    return res
