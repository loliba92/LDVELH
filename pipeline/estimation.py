"""Estimation du prix d'une édition, pour un état, à partir de ses observations.

Principe (voir docs/MODELE-PRICING.md) : médiane pondérée. Chaque observation pèse selon
  - sa nature (une vente réelle compte plus qu'une annonce, qui compte plus qu'un ancien relevé) ;
  - sa fraîcheur (le poids est divisé par deux tous les 90 jours ; 365 jours pour l'ancien relevé) ;
  - le nombre d'annonces qu'elle résume (racine carrée, plafonnée à 9 annonces).
Les prix des professionnels (boutiques, reconditionneurs) sont plus élevés que ceux des particuliers : ils forment une
série à part (type « prix_pro »), estimée séparément et jamais mêlée à la cote des particuliers.
Les prix demandés ne sont pas corrigés : faute de ventes réelles, on ne sait pas mesurer l'écart
entre prix demandé et prix payé. Le résultat l'indique (« annonces »).
"""
from collections import namedtuple
from datetime import date
from math import sqrt

Obs = namedtuple("Obs", "prix type date nb")

POIDS_TYPE = {"vente_reelle": 1.0, "vente_probable": 0.6, "rachat": 0.4, "prix_demande": 0.3, "prix_pro": 0.3, "historique": 0.2}
ACTUELS = {"vente_reelle", "vente_probable", "rachat", "prix_demande", "prix_pro"}
NATURE = {"vente_reelle": "ventes", "vente_probable": "ventes", "rachat": "rachats", "prix_demande": "annonces", "prix_pro": "professionnels"}
DEMI_VIE = {"historique": 365}
DEMI_VIE_DEFAUT = 90
PLAFOND_ANNONCES = 9
SEUIL_ACTUEL = 0.7      # part du poids venant d'observations actuelles pour parler de cote « actuelle »


def poids(o, aujourdhui):
    age = max(0, (aujourdhui - o.date).days)
    demi_vie = DEMI_VIE.get(o.type, DEMI_VIE_DEFAUT)
    return POIDS_TYPE[o.type] * 0.5 ** (age / demi_vie) * sqrt(min(max(o.nb, 1), PLAFOND_ANNONCES))


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


def estimer(observations, aujourdhui=None):
    """Renvoie un dict {prix, source, nature, nb, date, confiance} ou None s'il n'y a aucune observation.

    source : « archives » (aucune observation actuelle), « actuel » ou « mixte ».
    nature : « annonces », « ventes », « rachats » (observation actuelle dominante) ou « archives ».
    confiance : « ancienne » pour les archives ; « faible », « moyenne » ou « élevée » pour le reste.
    """
    aujourdhui = aujourdhui or date.today()
    obs = list(observations)
    if not obs:
        return None
    poids_obs = [(o, poids(o, aujourdhui)) for o in obs]
    prix = mediane_ponderee([(o.prix, w) for o, w in poids_obs])
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
