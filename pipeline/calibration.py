"""Modèle d'auto-apprentissage de la cote : il apprend l'écart entre les archives et les prix actuels.

Les archives (ancien relevé) sont plus bas que le marché d'aujourd'hui, et pas dans la même proportion partout.
Chaque semaine, le relevé eBay apporte des prix actuels pour une partie des éditions. Le modèle :
  1. apprend, par état, le rapport médian actuel / archive (en logarithme, donc robuste aux valeurs extrêmes),
     sur les seules éditions où les deux existent et où le relevé compte au moins MIN_NB annonces ;
  2. se contrôle lui-même par validation croisée : pour chaque édition, il prédit le prix actuel avec un rapport
     appris SANS cette édition, puis compare son erreur à celle des archives seules ;
  3. ne s'active que s'il bat nettement les archives (GAIN_MIN) sur assez d'éditions (MIN_PAIRES).
Actif, il remet à niveau les archives des éditions sans relevé actuel (confiance « faible », mention explicite).
Inactif, il ne change rien. Il se recalcule à chaque publication, donc s'améliore avec chaque nouveau relevé.
"""
import json
import math
import statistics
from datetime import date

MIN_NB = 3            # annonces minimum pour qu'un relevé serve à apprendre
MIN_PAIRES = 20       # couples (édition, état) minimum pour oser apprendre
MIN_PAR_ETAT = 8      # en dessous, l'état emprunte le rapport de l'ensemble
GAIN_MIN = 0.15       # l'erreur doit baisser d'au moins 15 % par rapport aux archives seules
RATIO_BORNES = (0.4, 4.0)   # garde-fou : un rapport appris hors de ces bornes est refusé


def paires(brut):
    """brut : {cle: {etat: [Obs]}}. Renvoie [(cle, etat, archive, actuel)] pour les éditions ayant les deux."""
    sortie = []
    for cle, par_etat in brut.items():
        for etat, obs in par_etat.items():
            arch = [o for o in obs if o.type == "historique" and o.prix and o.prix > 0]
            act = [o for o in obs if o.type == "prix_demande" and o.nb >= MIN_NB and o.prix and o.prix > 0]
            if not arch or not act:
                continue
            derniere = max(o.date for o in act)
            recents = [o for o in act if o.date == derniere]
            actuel = statistics.median([o.prix for o in recents])
            archive = statistics.median([o.prix for o in arch])
            sortie.append((cle, etat, archive, actuel))
    return sortie


def _loc(logs):
    return statistics.median(logs) if logs else 0.0


def _ajuster(couples):
    """Rapport (log) par état, avec repli sur l'ensemble pour les états trop peu fournis."""
    tous = [math.log(a / b) for _, _, b, a in couples]
    glob = _loc(tous)
    par_etat = {}
    for etat in {c[1] for c in couples}:
        logs = [math.log(a / b) for _, e, b, a in couples if e == etat]
        loc = _loc(logs) if len(logs) >= MIN_PAR_ETAT else glob
        mad = statistics.median([abs(x - loc) for x in logs]) * 1.4826 if len(logs) > 1 else 0.0
        par_etat[etat] = {"log_rapport": loc, "ecart": mad, "n": len(logs)}
    return glob, par_etat


def _rapport(glob, par_etat, etat):
    return par_etat.get(etat, {}).get("log_rapport", glob)


def apprendre(brut, aujourdhui=None):
    """Apprend, se contrôle, et renvoie un dict décrivant le modèle (voir `actif`)."""
    aujourdhui = aujourdhui or date.today()
    couples = paires(brut)
    n = len(couples)
    base = {"actif": False, "n_paires": n, "calcule_le": aujourdhui.isoformat(), "par_etat": {},
            "erreur_modele": None, "erreur_archives": None, "gain": None, "raison": ""}
    if n < MIN_PAIRES:
        base["raison"] = f"pas assez d'éditions comparables ({n} sur {MIN_PAIRES} nécessaires)"
        return base
    glob, par_etat = _ajuster(couples)
    # validation croisée : on retire chaque couple, on réapprend, on prédit
    err_m, err_b = [], []
    for i, (cle, etat, arch, act) in enumerate(couples):
        reste = couples[:i] + couples[i + 1:]
        g, pe = _ajuster(reste)
        prevu = math.log(arch) + _rapport(g, pe, etat)
        err_m.append(abs(math.log(act) - prevu))
        err_b.append(abs(math.log(act) - math.log(arch)))
    mae_m, mae_b = statistics.mean(err_m), statistics.mean(err_b)
    gain = 1 - mae_m / mae_b if mae_b > 0 else 0.0
    base.update({"par_etat": {e: {"rapport": round(math.exp(v["log_rapport"]), 3), "ecart": round(v["ecart"], 3), "n": v["n"]}
                              for e, v in par_etat.items()},
                 "rapport_global": round(math.exp(glob), 3),
                 "erreur_modele": round(mae_m, 3), "erreur_archives": round(mae_b, 3), "gain": round(gain, 3)})
    bornes = all(RATIO_BORNES[0] <= math.exp(v["log_rapport"]) <= RATIO_BORNES[1] for v in par_etat.values())
    if not bornes:
        base["raison"] = "rapport appris hors des bornes de sécurité"
    elif gain < GAIN_MIN:
        base["raison"] = f"le modèle ne bat pas assez les archives (gain {gain:.0%}, {GAIN_MIN:.0%} exigés)"
    else:
        base["actif"] = True
        base["raison"] = f"validé : erreur {mae_m:.2f} contre {mae_b:.2f} pour les archives (gain {gain:.0%})"
    return base


def remettre_a_niveau(modele, archive, etat):
    """Prix d'archive remis à niveau avec le rapport appris pour l'état."""
    r = (modele["par_etat"].get(etat) or {}).get("rapport") or modele.get("rapport_global") or 1.0
    return round(archive * r, 2)


def ecrire(modele, chemin):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(modele, ensure_ascii=False, indent=2), encoding="utf-8")
