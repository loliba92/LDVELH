"""Pages publiques « une page par livre » (web/livre/<isbn13>.html), page « Tous les livres », plan du site et robots.txt.

Source unique : web/data/versions.json (la même liste que la fiche du guide). Rien ne s'écrit à la main : à chaque génération,
une page est créée pour chaque édition, mise à jour si l'édition change, et supprimée si l'édition disparaît.
Appelé par pipeline/construire_pages.py (lui-même lancé après chaque export des données).

Les prix exacts restent réservés aux comptes connectés : la page ne montre que le niveau de prix (€ à €€€€€), comme le guide pour un visiteur.
Aucune date du jour dans les pages : une page ne change que si l'édition change (pas de bruit dans les envois).
"""
import html
import json
import re
import unicodedata
from pathlib import Path

SITE = "https://lacoteduheros.fr"
SEUILS = [10, 20, 40, 70]                    # mêmes seuils que SEUILS_COTE dans web/app.js
ETATS = [("convenable", "C", "Convenable"), ("bon", "BE", "Bon état"), ("tres_bon", "TBE", "Très bon état")]
LEGENDE = [("€", "moins de 10 €"), ("€€", "10 à 20 €"), ("€€€", "20 à 40 €"), ("€€€€", "40 à 70 €"), ("€€€€€", "plus de 70 €")]
ACCUEIL_TITRE = "La Cote du Héros"


def e(texte):
    return html.escape("" if texte is None else str(texte), quote=True)


def niveau(v):
    return 0 if v is None else 1 + sum(1 for s in SEUILS if v >= s)


def slug(texte):
    s = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "livre"


def numero(b):
    n = b.get("numero")
    return f" n° {n}" if n and not re.fullmatch(r"0+", str(n)) else ""


def cle_tri(b):
    m = re.match(r"\d+", str(b.get("numero") or ""))
    return (b.get("serie") or "", int(m.group()) if m else 0, b.get("titre") or "", b.get("version_n") or 0)


def sous_dossier(fragment):
    """Les fragments communs (en-tête, barre du bas…) sont écrits pour la racine : on les adapte à un dossier d'un niveau."""
    def r(m):
        v = m.group(2)
        if v.startswith(("http://", "https://", "mailto:", "#", "/", "data:", "../")):
            return m.group(0)
        v = v[2:] if v.startswith("./") else v
        return f'{m.group(1)}="../{v}"'
    return re.sub(r'\b(href|src)="([^"]*)"', r, fragment)


def jsonld(donnees):
    return json.dumps(donnees, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def liste_noms(texte):
    return [x.strip() for x in (texte or "").split(";") if x.strip()]


def couverture(web, b):
    for cle in ("couverture_grande", "couverture"):
        c = b.get(cle)
        if c and (web / c).exists():
            return c
    return None


def titre_complet(b):
    return f"{b['titre']} ({b.get('serie') or 'hors série'}{numero(b)}, {b['version']})"


def page_livre(b, freres, web, frag):
    isbn = b["isbn13"]
    url = f"{SITE}/livre/{isbn}.html"
    serie, titre = b.get("serie") or "", b["titre"]
    cov = couverture(web, b)
    niveaux = [(c, lib, niveau((b.get("prix") or {}).get(k))) for k, c, lib in ETATS]
    avec_prix = [n for n in niveaux if n[2]]
    editeur = " · ".join(x for x in (b.get("editeur"), b.get("collection")) if x)
    annee = b.get("annee") or b.get("annee_bnf")
    auteurs = liste_noms(b.get("auteurs"))

    chapeau = f"« {titre} » est l'édition {b['version']} du livre dont vous êtes le héros{f', {serie}{numero(b)}' if serie else ''}"
    chapeau += f", publiée chez {b['editeur']}" if b.get("editeur") else ""
    chapeau += f" en {annee}" if annee else ""
    chapeau += f", écrit par {' et '.join(auteurs)}" if auteurs else ""
    chapeau += "."
    if avec_prix:
        meilleur = max(avec_prix, key=lambda n: n[2])
        resume = f"Niveau de prix en {meilleur[1].lower()} : {'€' * meilleur[2]}."
    else:
        resume = "Pas encore de prix pour cette édition."
    description = f"{chapeau} {resume} ISBN {isbn}."
    titre_page = f"{titre_complet(b)} : cote et prix · {ACCUEIL_TITRE}"

    faits = [("Série", f"{serie}{numero(b)}" if serie else ""), ("Édition", b["version"]), ("Auteurs", " ; ".join(auteurs)),
             ("Illustrations", b.get("illustrateur")), ("Traduction", b.get("traducteur")), ("Éditeur", editeur),
             ("Année", annee), ("Pages", b.get("pages")), ("ISBN-13", isbn), ("ISBN-10", b.get("isbn10"))]
    faits_html = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in faits if v)

    if avec_prix:
        cases = "".join(
            f'<li><span class="petit">{e(c)}</span><span class="valeur repere" aria-label="{("niveau de prix " + str(n) + " sur 5") if n else "sans prix"}">{"€" * n if n else "—"}</span></li>'
            for c, _, n in niveaux)
        prix_html = (f'<h2>Niveau de prix</h2><ul class="livre-niveaux" aria-label="Niveau de prix selon l\'état">{cases}</ul>'
                     f'<p class="sous">C : convenable, BE : bon état, TBE : très bon état. '
                     + " · ".join(f"{e(s)} : {e(t)}" for s, t in LEGENDE) + '. Les prix exacts sont réservés aux comptes connectés. La Cote du Héros ne prend ni marge ni commission : le guide donne un repère, pas un prix de vente.</p>')
    else:
        prix_html = "<h2>Niveau de prix</h2><p>Cette édition n'a pas encore de prix : il manque des annonces récentes pour en établir un.</p>"

    autres = ""
    if freres:
        lignes = "".join(
            f'<li><a href="{e(f["isbn13"])}.html">{e(f["version"])}</a>'
            f'{" · " + e(f["editeur"]) if f.get("editeur") else ""}{" · " + e(f.get("annee") or f.get("annee_bnf")) if (f.get("annee") or f.get("annee_bnf")) else ""}</li>'
            for f in freres)
        autres = f"<h2>Autres éditions de ce livre</h2><ul>{lignes}</ul>"
    lien_serie = f'<p><a href="index.html#{slug(serie)}">Tous les livres de la série {e(serie)}</a></p>' if serie else ""

    donnees = {"@context": "https://schema.org", "@type": "Book", "name": titre, "url": url, "isbn": isbn, "inLanguage": "fr",
               "bookEdition": b["version"]}
    if auteurs:
        donnees["author"] = [{"@type": "Person", "name": a} for a in auteurs]
    if b.get("illustrateur"):
        donnees["illustrator"] = {"@type": "Person", "name": b["illustrateur"]}
    if b.get("traducteur"):
        donnees["translator"] = {"@type": "Person", "name": b["traducteur"]}
    if b.get("editeur"):
        donnees["publisher"] = {"@type": "Organization", "name": b["editeur"]}
    if annee:
        donnees["datePublished"] = str(annee)
    if serie:
        donnees["isPartOf"] = {"@type": "BookSeries", "name": serie}
    if cov:
        donnees["image"] = f"{SITE}/{cov}"
    fil = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": ACCUEIL_TITRE, "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": "Tous les livres", "item": SITE + "/livre/"},
        {"@type": "ListItem", "position": 3, "name": titre, "item": url}]}

    image_og = f"{SITE}/{cov}" if cov else f"{SITE}/images/partage.png"
    partage = "https://www.facebook.com/sharer/sharer.php?u=" + url
    img = (f'<img src="../{e(cov)}" alt="Couverture de {e(titre)}, {e(serie)}{e(numero(b))}, édition {e(b["version"])}" width="200" height="300" decoding="async">'
           if cov else "")
    maj = b.get("maj") or ""
    return f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titre_page)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="book">
<meta property="og:site_name" content="{ACCUEIL_TITRE}">
<meta property="og:locale" content="fr_FR">
<meta property="og:title" content="{e(titre_complet(b))}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{e(image_og)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#000000">
<link rel="manifest" href="../manifest.webmanifest">
<link rel="apple-touch-icon" href="../icons/apple-touch-icon.png">
<link rel="preload" href="../fonts/cormorant-garamond.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="../fonts/source-sans-3.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="../favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="32x32" href="../favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="../favicon-16.png">
<link rel="stylesheet" href="../style.css">
<script type="application/ld+json">{jsonld(donnees)}</script>
<script type="application/ld+json">{jsonld(fil)}</script>
</head>
<body class="annexe">
<a class="evitement" href="#main">Aller au contenu</a>

<div class="haut">
{frag["bandeau"]}
{frag["entete"]}
</div>

<main id="main" class="cadre page">
<p class="surtitre">{e(serie) if serie else "Livre dont vous êtes le héros"}{e(numero(b))} · édition {e(b["version"])}</p>
<h1>{e(titre)}</h1>
<div class="livre-tete">
  <div class="livre-couv">{img}</div>
  <p class="chapeau">{e(chapeau)}</p>
  <dl class="livre-faits">{faits_html}</dl>
</div>
<p class="actions"><a class="bouton" href="../index.html#fiche={e(b["id"])}">Ouvrir la fiche dans le guide</a> <a class="bouton bouton-clair" href="{e(partage)}" target="_blank" rel="noopener noreferrer">Partager sur Facebook</a></p>
{prix_html}
{autres}
{lien_serie}
</main>

<footer class="pied">
  <div class="cadre pied-in">
    {frag["pied"]}
    <p class="sous">La Cote du Héros · guide indépendant, sans publicité{f" · fiche mise à jour le {e(maj)}" if maj else ""}.</p>
  </div>
</footer>

{frag["barre"]}

{frag["feuille"]}

<script src="../plus.js"></script>
<script src="../installer.js"></script>
<script src="../identite.js"></script>
<script src="../relais.js"></script>
<script src="../cloud.js"></script>
<script src="../scan.js"></script>
<script src="../compte.js"></script>
<script src="../pages.js"></script>
</body>
</html>
'''


def page_index(livres, frag):
    par_serie = {}
    for b in livres:
        par_serie.setdefault(b.get("serie") or "Hors série", []).append(b)
    sections = []
    for serie in sorted(par_serie, key=lambda s: slug(s)):
        lignes = "".join(f'<li><a href="{e(b["isbn13"])}.html">{e(b["titre"])}</a> <span class="sous">{e(numero(b).strip())} · {e(b["version"])}</span></li>'
                         for b in sorted(par_serie[serie], key=cle_tri))
        sections.append(f'<h2 id="{slug(serie)}">{e(serie)} <span class="sous">({len(par_serie[serie])})</span></h2><ul class="livre-liste">{lignes}</ul>')
    description = f"Les {len(livres)} éditions de livres dont vous êtes le héros suivies par La Cote du Héros, classées par série : Défis Fantastiques, Loup Solitaire et bien d'autres."
    url = f"{SITE}/livre/"
    return f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tous les livres dont vous êtes le héros, par série · {ACCUEIL_TITRE}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{ACCUEIL_TITRE}">
<meta property="og:locale" content="fr_FR">
<meta property="og:title" content="Tous les livres dont vous êtes le héros, par série">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}/images/partage.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#000000">
<link rel="manifest" href="../manifest.webmanifest">
<link rel="apple-touch-icon" href="../icons/apple-touch-icon.png">
<link rel="preload" href="../fonts/cormorant-garamond.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="../fonts/source-sans-3.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="../favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="32x32" href="../favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="../favicon-16.png">
<link rel="stylesheet" href="../style.css">
</head>
<body class="annexe">
<a class="evitement" href="#main">Aller au contenu</a>

<div class="haut">
{frag["bandeau"]}
{frag["entete"]}
</div>

<main id="main" class="cadre page">
<p class="surtitre">Le guide</p>
<h1>Tous les livres</h1>
<p class="chapeau">{len(livres)} éditions de livres dont vous êtes le héros, classées par série. Chaque livre a sa page : fiche, niveau de prix et autres éditions.</p>
{"".join(sections)}
</main>

<footer class="pied">
  <div class="cadre pied-in">
    {frag["pied"]}
    <p class="sous">La Cote du Héros · guide indépendant, sans publicité.</p>
  </div>
</footer>

{frag["barre"]}

{frag["feuille"]}

<script src="../plus.js"></script>
<script src="../installer.js"></script>
<script src="../identite.js"></script>
<script src="../relais.js"></script>
<script src="../cloud.js"></script>
<script src="../scan.js"></script>
<script src="../compte.js"></script>
<script src="../pages.js"></script>
</body>
</html>
'''


PAGES_PUBLIQUES = ["", "le-projet.html", "communaute.html", "contact.html", "confidentialite.html"]


def plan_du_site(livres):
    lignes = [f"  <url><loc>{SITE}/{p}</loc></url>" for p in PAGES_PUBLIQUES]
    lignes.append(f"  <url><loc>{SITE}/livre/</loc></url>")
    for b in livres:
        maj = f"<lastmod>{b['maj']}</lastmod>" if re.fullmatch(r"\d{4}-\d\d-\d\d", b.get("maj") or "") else ""
        lignes.append(f"  <url><loc>{SITE}/livre/{b['isbn13']}.html</loc>{maj}</url>")
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(lignes) + "\n</urlset>\n"


ROBOTS = f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n"


def editions_publiques(web):
    donnees = json.loads((web / "data" / "versions.json").read_text(encoding="utf-8"))
    return sorted((b for b in donnees if b.get("isbn13") and b.get("titre")), key=cle_tri)


def ecrire(web, frag):
    """Écrit les pages, le plan du site et robots.txt ; supprime les pages de livres qui n'existent plus. Renvoie le nombre de pages écrites."""
    livres = editions_publiques(web)
    dossier = web / "livre"
    dossier.mkdir(exist_ok=True)
    frag = {**frag, **{k: sous_dossier(frag[k]) for k in ("bandeau", "entete", "pied", "barre", "feuille")}}
    variante = frag.get("variante", lambda h: h)
    par_livre = {}
    for b in livres:
        par_livre.setdefault(b.get("livre_id") or b["isbn13"], []).append(b)
    voulus = set()
    for b in livres:
        freres = [f for f in par_livre[b.get("livre_id") or b["isbn13"]] if f["isbn13"] != b["isbn13"]]
        (dossier / f"{b['isbn13']}.html").write_text(variante(page_livre(b, freres, web, frag)), encoding="utf-8")
        voulus.add(f"{b['isbn13']}.html")
    (dossier / "index.html").write_text(variante(page_index(livres, frag)), encoding="utf-8")
    voulus.add("index.html")
    for f in dossier.glob("*.html"):
        if f.name not in voulus:
            f.unlink()
    (web / "sitemap.xml").write_text(plan_du_site(livres), encoding="utf-8")
    (web / "robots.txt").write_text(ROBOTS, encoding="utf-8")
    return len(livres)
