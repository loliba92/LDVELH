"""Ce qui a bougé entre deux publications de la cote : grands mouvements, état du modèle.

Chaque publication enregistre un instantané des prix (`data/processed/cotes-historique.json`, 60 derniers). La
comparaison avec l'instantané précédent donne les plus fortes hausses et baisses ; le résultat alimente
  - `web/data/mouvements.json` (page « Évolutions des prix » du site),
  - le résumé de l'exécution GitHub (`$GITHUB_STEP_SUMMARY`), lisible sans ouvrir de fichier.
Entièrement déterministe : mêmes prix, mêmes résultats.
"""
import json
import os
import statistics
from pathlib import Path

SEUIL_PCT = 0.10       # un mouvement compte à partir de 10 %…
SEUIL_EUR = 0.5        # …et de 0,50 €
TOP = 12
MAX_INSTANTANES = 60
ETATS_LIB = {"convenable": "C", "bon": "BE", "tres_bon": "TBE"}


def cle(id_, etat):
    return f"{id_}|{etat}"


def instantane(versions, jour):
    return {"date": jour.isoformat(),
            "prix": {cle(v["id"], e): p for v in versions for e, p in v["prix"].items() if p is not None}}


def charger(chemin):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def comparer(avant, apres, versions):
    """Compare deux instantanés {date, prix}. Renvoie le dict des mouvements (liste vide si `avant` est None)."""
    info = {v["id"]: v for v in versions}
    res = {"date": apres["date"], "precedent": avant["date"] if avant else None, "nb_comparees": 0, "nb_modifiees": 0,
           "mediane_variation": None, "nouvelles_cotes": 0, "hausses": [], "baisses": []}
    if not avant:
        return res
    mouv = []
    for k, nouveau in apres["prix"].items():
        ancien = avant["prix"].get(k)
        if ancien is None:
            res["nouvelles_cotes"] += 1
            continue
        res["nb_comparees"] += 1
        if abs(nouveau - ancien) > 1e-9:
            res["nb_modifiees"] += 1
        pct = (nouveau - ancien) / ancien if ancien else 0
        if abs(pct) >= SEUIL_PCT and abs(nouveau - ancien) >= SEUIL_EUR:
            id_, etat = k.rsplit("|", 1)
            v = info.get(id_)
            if not v:
                continue
            i = (v.get("prix_info") or {}).get(etat) or {}
            mouv.append({"id": id_, "isbn13": v.get("isbn13"), "titre": v["titre"], "serie": v["serie"],
                         "numero": v.get("numero"), "version": v["version"], "etat": etat,
                         "avant": round(ancien, 2), "apres": round(nouveau, 2), "pct": round(pct, 3),
                         "nature": i.get("nature"), "nb": i.get("nb"), "recalibre": bool(i.get("recalibre"))})
    variations = [(apres["prix"][k] - avant["prix"][k]) / avant["prix"][k] for k in apres["prix"]
                  if k in avant["prix"] and avant["prix"][k]]
    res["mediane_variation"] = round(statistics.median(variations), 3) if variations else None
    res["hausses"] = sorted((m for m in mouv if m["pct"] > 0), key=lambda m: -m["pct"])[:TOP]
    res["baisses"] = sorted((m for m in mouv if m["pct"] < 0), key=lambda m: m["pct"])[:TOP]
    res["nb_grands_mouvements"] = len(mouv)
    return res


def euros(v):
    return f"{v:.2f}".replace(".", ",") + " €"


def resume_md(mv, modele):
    """Résumé en Markdown pour la page de l'exécution GitHub."""
    l = ["## Évolution de la cote", ""]
    if not mv["precedent"]:
        l.append("Première publication : pas de comparaison possible.")
    else:
        med = mv["mediane_variation"]
        l += [f"Comparaison avec la publication du **{mv['precedent']}** :",
              f"- {mv['nb_comparees']} prix comparés, **{mv['nb_modifiees']} ont changé**"
              + (f", variation médiane {med:+.1%}" if med is not None else "") + ".",
              f"- {mv.get('nb_grands_mouvements', 0)} grands mouvements (au moins {SEUIL_PCT:.0%} et {SEUIL_EUR:.2f} €), "
              f"{mv['nouvelles_cotes']} nouvelles cotes.", ""]
        for titre, liste in (("Plus fortes hausses", mv["hausses"]), ("Plus fortes baisses", mv["baisses"])):
            if liste:
                l += [f"### {titre}", "", "| Livre | Éd. | État | Avant | Après | Variation |", "|---|---|---|---:|---:|---:|"]
                l += [f"| {m['titre']} | {m['version']} | {ETATS_LIB.get(m['etat'], m['etat'])} | {euros(m['avant'])} | "
                      f"{euros(m['apres'])} | {m['pct']:+.0%} |" for m in liste]
                l.append("")
    l += ["### Modèle d'auto-apprentissage", "",
          f"- {'**Actif**' if modele['actif'] else 'Inactif'} : {modele['raison']}.",
          f"- {modele['n_paires']} éditions comparables" + (f", gain mesuré {modele['gain']:.0%}" if modele.get("gain") is not None else "") + "."]
    return "\n".join(l) + "\n"


def mettre_a_jour(versions, jour, base, modele, chemin_hist, sortie_json):
    """Compare avec l'instantané précédent (ou `base` à défaut), enregistre le nouvel instantané et écrit les sorties."""
    hist = charger(chemin_hist) or ([base] if base else [])
    hist = [s for s in hist if s["date"] < jour.isoformat()]      # une réexécution le même jour remplace l'instantané
    precedent = hist[-1] if hist else None
    courant = instantane(versions, jour)
    mv = comparer(precedent, courant, versions)
    mv["modele"] = {k: modele.get(k) for k in ("actif", "n_paires", "gain", "raison", "rapport_global")}
    hist = (hist + [courant])[-MAX_INSTANTANES:]
    Path(chemin_hist).parent.mkdir(parents=True, exist_ok=True)
    Path(chemin_hist).write_text(json.dumps(hist, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    Path(sortie_json).write_text(json.dumps(mv, ensure_ascii=False, indent=1), encoding="utf-8")
    resume = os.environ.get("GITHUB_STEP_SUMMARY")
    if resume:
        with open(resume, "a", encoding="utf-8") as f:
            f.write(resume_md(mv, modele))
    return mv
