"""Essai en deux étapes sur de vraies annonces eBay (aucun enregistrement, comptages seulement dans le journal).

Méthode testée, pour des éditions « archive seule » :
  1. titre : on ne garde que les annonces dont le titre concorde avec le livre ;
  2. description : on lit la description de chaque annonce retenue (un appel par annonce), et on y cherche une indication
     de version (V1, V2, V3, ou l'année de parution d'une édition) ;
  3. image : la photo de l'annonce est comparée aux jaquettes des éditions du même livre (reconciliation_image.decider).
Le journal ne contient que des décomptes, jamais de titre, de vendeur ou de description."""
import collections
import random
import re
from pathlib import Path
from urllib.parse import quote

import requests

import reconciliation_image as ri

PAR_EDITION = 3                                   # annonces au plus par édition, pour limiter les appels
URL_ARTICLE = "https://api.ebay.com/buy/browse/v1/item/{id}"
CIBLES = Path(__file__).resolve().parent.parent / "data" / "manual" / "essais_archives.txt"   # éditions « archive seule »


def description(item_id, token, http=requests):
    """Description d'une annonce (texte brut), ou chaîne vide si eBay ne la donne pas."""
    try:
        r = http.get(URL_ARTICLE.format(id=quote(item_id, safe="")),
                     headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": "EBAY_FR"}, timeout=30)
        if getattr(r, "status_code", 200) != 200:
            return ""
        d = r.json()
        return " ".join(str(d.get(k) or "") for k in ("shortDescription", "description"))
    except (requests.RequestException, ValueError):
        return ""


def version_titre(titre):
    """Version écrite dans le titre d'une annonce (« V2 », « v 3 »…), en majuscules sans espace, ou None."""
    m = re.search(r"\bV\s?([1-9])\b", titre or "", flags=re.I)
    return f"V{m.group(1)}" if m else None


def version_indiquee(texte, editions):
    """Version dite par la description : « V2 », ou l'année d'une édition connue. None si rien ou plusieurs versions."""
    trouvees = set()
    for m in re.finditer(r"\bV\s?([1-9])\b", texte, flags=re.I):
        trouvees.add(f"V{m.group(1)}")
    annees = {str(e.get("annee")) for e in editions if e.get("annee")}
    for an in re.findall(r"\b(19[5-9]\d|20[0-3]\d)\b", texte):
        if an in annees:
            trouvees.add(an)
    versions = {e["version"]: e["isbn13"] for e in editions if e.get("version")}
    trouvees = {t for t in trouvees if t in versions or t in annees}
    if len(trouvees) != 1:
        return None
    t = next(iter(trouvees))
    if t in versions:
        return next(e["isbn13"] for e in editions if e.get("version") == t)
    return next(e["isbn13"] for e in editions if str(e.get("annee")) == t)


def essayer(a, token, catalogue, chercher_elargi, concorde, dossier_covers, editions_rows, http=None):
    """Compte, sur N éditions « archive seule », combien d'annonces passent chaque étape."""
    http = http or requests
    cat = catalogue()
    if CIBLES.exists():
        voulus = set(CIBLES.read_text(encoding="utf-8").split())
        cat = [c for c in cat if c[0] in voulus]
    rows = editions_rows()
    if not ri.disponible():
        print("Comparaison des photos indisponible sur ce relevé (bibliothèques absentes) : étape 3 non mesurée.")
    rnd = random.Random(7)
    echantillon = rnd.sample(cat, min(a.essai_version, len(cat)))
    par_livre = collections.defaultdict(list)
    for c in cat:
        par_livre[c[3]].append(c[0])
    compte = collections.Counter()
    for isbn, titre, nb_ed, livre, annees in echantillon:
        ed = next((r for r in rows if r.get("isbn13") == isbn), {})
        compte["editions"] += 1
        items = [it for it in chercher_elargi(isbn, titre, token, ed=ed) if concorde(it.get("title", ""), titre)]
        compte["annonces_titre_concordant"] += len(items)
        if not items:
            continue
        meme_livre = [r for r in rows if r.get("livre") == livre and r.get("isbn13")]
        jaquettes = {r["isbn13"]: ri.jaquette_locale(dossier_covers, r["isbn13"]) for r in meme_livre}
        jaquettes = {k: v for k, v in jaquettes.items() if v}
        ver_ed = (ed.get("version") or "").upper().replace(" ", "")
        lues = 0
        for it in items:
            if lues >= PAR_EDITION:
                break
            octets = ri.empreinte_annonce(it, http)
            v_img, _ = ri.decider(octets, jaquettes) if octets else (None, {})
            vt = version_titre(it.get("title", ""))
            if vt and ver_ed and vt != ver_ed:
                # Le titre dit une autre version : on n'écarte l'annonce que si la photo désigne clairement une autre édition.
                if v_img and v_img != isbn:
                    compte["rejetees_version_image"] += 1
                    continue
                compte["version_titre_gardee"] += 1
            if not lues:
                compte["editions_avec_annonce"] += 1
            lues += 1
            compte["annonces_lues"] += 1
            texte = description(it.get("itemId", ""), token, http)
            if texte.strip():
                compte["descriptions_non_vides"] += 1
            v_desc = version_indiquee(texte, meme_livre) if texte else None
            if v_desc:
                compte["version_par_description"] += 1
            if v_img:
                compte["version_par_image"] += 1
            if v_desc and v_img:
                compte["description_et_image_concordent" if v_desc == v_img else "description_et_image_contradictoires"] += 1
            if not v_desc and not v_img:
                compte["sans_version"] += 1
    print(f"Essai version sur {compte['editions']} éditions « archive seule » (comptages seulement)")
    for cle in ("editions_avec_annonce", "annonces_titre_concordant", "rejetees_version_image", "version_titre_gardee",
                "annonces_lues", "descriptions_non_vides", "version_par_description", "version_par_image",
                "description_et_image_concordent", "description_et_image_contradictoires", "sans_version"):
        print(f"- {cle} : {compte[cle]}")
