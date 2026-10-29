"""Construit les pages annexes du site (web/le-projet.html, confidentialite.html, mentions-legales.html).

    python pipeline/construire_pages.py

L'en-tête, la barre du bas, la feuille « Plus » et le pied de page sont communs aux trois pages (et recopiés
dans web/index.html, qui reste écrit à la main). Les textes juridiques décrivent ce que le site fait réellement :
voir docs/CONFORMITE.md pour la vérification faite dans le code.
"""
import json
import re
from pathlib import Path

import pages_livres

WEB = Path(__file__).resolve().parent.parent / "web"
_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
_AUJ = __import__("datetime").date.today()
MAJ = f"{_AUJ.day} {_MOIS[_AUJ.month - 1]} {_AUJ.year}"      # date de la dernière construction des pages
MAJ_LEGAL = "22 octobre 2026"      # dernière révision des pages Confidentialité et Mentions légales
ISSUES = "https://github.com/loliba92/LDVELH/issues"


def _compte_actif():
    """Vrai quand la collection est liée au compte Google (web/data/admin-config.json : "collection": true) : les textes légaux changent alors."""
    try:
        return json.loads((WEB / "data" / "admin-config.json").read_text(encoding="utf-8")).get("collection") is True
    except (OSError, ValueError):
        return False


COMPTE = _compte_actif()


def ico(d):
    return (f'<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>')


PAGES = {
    "butin.html": ("Butin", "Butin · La Cote du Héros",
                   "Les bonnes affaires : annonces encore en ligne à moitié prix de la cote ou moins."),
    "ajouter.html": ("Ajouter des livres", "Ajouter des livres · La Cote du Héros",
                     "Ajout de livres au guide par scanner ou liste d'ISBN."),
    "revue-prix.html": ("Revue des prix", "Revue des prix · La Cote du Héros",
                        "Outil de revue : archive, relevé eBay et prix publié, côte à côte, pour valider les cotes."),
    "evolutions.html": ("Évolutions", "Évolutions des prix · La Cote du Héros",
                        "Ce qui a bougé dans la cote : plus fortes hausses et baisses depuis la dernière mise à jour, et état du modèle d'auto-apprentissage."),
    "le-projet.html": ("Le projet", "Le projet · La Cote du Héros",
                       "Un outil de collectionneur : tenir sa collection à jour, la suivre dans le temps et trouver les livres qui manquent. Les prix ne sont que des repères."),
    "confidentialite.html": ("Confidentialité", "Confidentialité · La Cote du Héros",
                             "Ce que La Cote du Héros garde de vous : rien sans compte ; avec un compte Google, votre collection est enregistrée dans votre propre Drive et vos notes dans le service du site."),
    "contact.html": ("Contact", "Contact · La Cote du Héros",
                     "Écrire à La Cote du Héros : une question, une erreur à signaler, un prix constaté, une idée ou un partenariat."),
    "communaute.html": ("Communauté", "Communauté · La Cote du Héros",
                        "Des passionnés de livres dont vous êtes le héros : chaînes, sites, blogs, collectionneurs et boutiques à suivre."),
    "equipe.html": ("Équipe", "Équipe · La Cote du Héros",
                    "Page réservée."),
    "mentions-legales.html": ("Mentions légales", "Mentions légales · La Cote du Héros",
                              "Éditeur, hébergeur et conditions d'utilisation de La Cote du Héros."),
}


# Textes qui changent quand la collection est liée au compte Google (voir COMPTE). Chaque paire doit trouver sa phrase : le test
# pipeline/test_textes_compte.py le vérifie, pour qu'une modification des textes ne fasse pas silencieusement manquer une variante.
VARIANTES = [
    ("La collection que vous composez est enregistrée dans votre navigateur, sur votre appareil. Rien n'est envoyé à un serveur.",
     "La collection que vous composez demande un compte Google : elle est enregistrée dans l'espace réservé de votre propre Google Drive, que seul ce site peut ouvrir, avec une copie sur votre appareil. Le guide n'a pas de serveur et ne la voit jamais."),
    ('Composez et suivez votre collection de livres dont vous êtes le héros. Tout reste dans votre navigateur.',
     'Composez et suivez votre collection de livres dont vous êtes le héros. Elle est sauvegardée dans votre Google Drive.'),
    ('Vos livres, leur état et leur évolution. Tout reste dans votre navigateur.',
     'Vos livres, leur état et leur évolution, sauvegardés dans votre Google Drive.'),
    ('Votre collection reste dans votre navigateur : voir',
     'Votre collection est dans votre Google Drive : voir'),
]


def variante(html):
    """Applique les textes du mode « collection liée au compte Google » quand il est actif."""
    if COMPTE:
        for ancien, nouveau in VARIANTES:
            html = html.replace(ancien, nouveau)
    return html


def entete(courante):
    lien = lambda href, txt, page=None: f'<a href="{href}"{" aria-current=\"page\"" if page == courante else ""}>{txt}</a>'
    return f'''<header class="bandeau">
  <div class="cadre bandeau-in">
    <a class="marque" href="./" aria-label="La Cote du Héros, accueil">
      <span class="marque-sceau" aria-hidden="true"></span>
      <span class="marque-nom">La Cote du Héros</span>
    </a>
    <nav class="menu" aria-label="Navigation">
      <a class="menu-maison" href="./"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z"/></svg><span>Accueil</span></a>
      <a href="./#recherche">L'étagère</a>
      <a href="collection.html">Ma collection</a>
      <a class="menu-butin" href="butin.html" hidden>Butin <span class="nb-coll nb-butin" aria-label=""></span></a>
      <a class="menu-cafe" href="https://buymeacoffee.com/obertrand9s" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 9h11v6a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4Z"/><path d="M16 10.5h1.5a2 2 0 0 1 0 4H16"/><path d="M8.5 4.5c-.6.7-.6 1.3 0 2M12 4.5c-.6.7-.6 1.3 0 2"/></svg><span>Offrir un café</span></a>
      <div class="compte" id="compte-haut"></div>
    </nav>
  </div>
</header>'''


def barre(courante):
    plus_actif = '' if courante == 'collection.html' else ' aria-current="page"'      # « Compte » est la page en cours sur les pages d'information, pas sur « Ma collection »
    return f'''<nav class="barre-bas" id="barre-bas" aria-label="Menu du bas">
  <a href="./">{ico('<path d="M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z"/>')}<span>Accueil</span><b class="nb-pep" id="nb-butin-bas"></b></a>
  <a href="./#recherche">{ico('<path d="M4 20h16M6 20V9l3-1v12M11 20V5h3.5v15M16.5 20V10l2.5 1v9"/>')}<span>L'étagère</span></a>
  <a class="barre-centre" href="collection.html">{ico('<path d="M5 4.5h10a3 3 0 0 1 3 3V20H8a3 3 0 0 1-3-3zM8 4.5V17"/>')}<span>Ma collection</span></a>
  <a class="barre-trouver" href="collection.html#trouver">{ico('<path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.9L12 16.9l-5.2 2.8 1-5.9-4.3-4.1 5.9-.8z"/>')}<span>À trouver</span><b class="nb-pep" id="nb-pep-bas"></b></a>
  <button type="button" data-plus aria-haspopup="dialog" aria-expanded="false"{plus_actif}>{ico('<circle cx="12" cy="8.5" r="3.6"/><path d="M5 20c.8-3.6 3.7-5.5 7-5.5s6.2 1.9 7 5.5"/>')}<span>Compte</span></button>
</nav>'''


def feuille(courante, racine_a_propos="./#apropos"):
    def e(href, titre, detail, page=None):
        cur = ' aria-current="page"' if page is not None and page == courante else ""
        return f'<li><a href="{href}"{cur}><b>{titre}</b><small>{detail}</small></a></li>'
    return f'''<dialog class="feuille" id="feuille-plus" aria-labelledby="feuille-plus-titre">
  <div class="feuille-poignee" aria-hidden="true"></div>
  <div class="feuille-tete"><h2 id="feuille-plus-titre">Mon compte</h2><button type="button" class="fermer feuille-fermer" aria-label="Fermer le menu">×</button></div>
  <div class="compte-feuille" id="compte-feuille"></div>
</dialog>'''


BANDEAU = '<aside aria-label="Avis sur le site"><p class="bandeau-chantier"><strong>Site en construction.</strong> Prix en cours de vérification.</p></aside>'

PIED_LIENS = '''<nav class="pied-liens" aria-label="Informations">
      <a href="le-projet.html">Le projet</a>
      <a href="livre/">Tous les livres</a>
      <a href="confidentialite.html">Confidentialité</a>
      <a href="mentions-legales.html">Mentions légales</a>
      <a href="contact.html">Contact</a>
    </nav>'''



def _revue_prix():
    """Page Prix et corrections : l'onglet Indice (Zagor seulement) vient après l'onglet Ajout."""
    lignes = []
    for l in REVUE.split("\n"):
        if l.startswith('<div class="rv-pane" id="pane-ajout"'):
            lignes.append(INDICE_PANNEAU)
        lignes.append(l)
        if 'data-pane="ajout"' in l and 'role="tab"' in l:
            lignes.append(INDICE_ONGLET)
    return "\n".join(lignes)


RECUES_ONGLET = '''  <button type="button" role="tab" data-pane="recues" aria-selected="false" hidden><svg class="rv-ico" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/></svg><span>Annonces reçues</span></button>'''
INDICE_ONGLET = '''  <button type="button" role="tab" data-pane="indice" aria-selected="false" hidden><svg class="rv-ico" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg><span>Indice</span></button>'''
INDICE_PANNEAU = '''<div class="rv-pane" id="pane-indice" role="tabpanel" hidden>
  <p class="chapeau">Indice de marché par édition, au dernier relevé (100 au premier jour mesuré). Suivi interne : il n'entre dans aucun prix.</p>
  <p class="sous" id="ind-etat" role="status" aria-live="polite"></p>
  <div id="ind-liste"></div>
</div>'''
RECUES_PANNEAU = '''<div class="rv-pane" id="pane-recues" role="tabpanel" hidden>
  <p class="chapeau">Toutes les annonces reçues (eBay, Leboncoin, Vinted, librairies), pas seulement les bonnes affaires. Chaque ligne indique l'origine et la date. Changez l'ordre avec « Trier par ».</p>
  <div class="captures-zone" id="captures-recues"></div>
  <div class="pp-barre">
    <p class="sous" id="rc-etat" role="status" aria-live="polite"></p>
    <div class="pp-outils">
      <label class="pp-tri"><span>Trier par</span><select id="rc-tri">
        <option value="recent">Date et heure (récentes d'abord)</option>
        <option value="serie">Série et numéro</option>
        <option value="prix">Prix croissant</option>
        <option value="ecart">Meilleures affaires d'abord</option>
        <option value="origine">Origine</option>
      </select></label>
      <label class="pp-tri"><span>Origine</span><select id="rc-source">
        <option value="tout">Toutes</option>
        <option value="ebay">eBay</option>
        <option value="leboncoin">Leboncoin</option>
        <option value="vinted">Vinted</option>
        <option value="librairie">Librairies</option>
      </select></label>
      <label class="pp-tri"><span>Prix</span><select id="rc-verdict">
        <option value="tout">Tous</option>
        <option value="super">Super pépites</option>
        <option value="pepite">Pépites</option>
        <option value="dessous">Pas cher</option>
        <option value="dans">Dans les prix</option>
        <option value="dessus">Trop cher</option>
        <option value="cher">Très chers</option>
      </select></label>
      <label class="case"><input type="checkbox" id="rc-trouver"><span>Mes « à trouver » seulement</span></label>
      <label class="case"><input type="checkbox" id="rc-enligne" checked><span>Revues au dernier relevé seulement</span></label>
    </div>
  </div>
  <div id="rc-liste"></div>
</div>'''


def _butin():
    """Page Butin : la page des prix avec le seul onglet Butin (même code, même données)."""
    lignes = []
    for l in REVUE.split("\n"):
        if re.search(r'data-pane="(prix|tendances|annonces|ajout)"', l):
            continue
        if l.startswith('<div class="rv-pane" id="pane-') and "hidden" not in l and 'id="pane-pepites"' not in l:
            l = l.replace('role="tabpanel">', 'role="tabpanel" hidden>', 1)
        if 'id="pane-pepites"' in l:
            l = l.replace(" hidden>", ">")
        if l.startswith("<h1>Prix et corrections"):
            l = "<h1>Butin</h1>"
        if 'data-pane="pepites"' in l:
            l = l.replace(' aria-selected="false" hidden>', ' aria-selected="true">') + "\n" + RECUES_ONGLET
        if l.startswith('<div class="rv-pane" id="pane-ajout"'):
            lignes.append(RECUES_PANNEAU)
        lignes.append(l)
    return "\n".join(lignes)



def page(nom, corps):
    court, titre, desc = PAGES[nom]
    corps = corps.replace("{ISSUES}", ISSUES)
    noindex = '\n<meta name="robots" content="noindex">' if nom in ("mentions-legales.html", "revue-prix.html", "equipe.html", "evolutions.html", "butin.html", "ajouter.html") else ""
    return f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titre}</title>
<meta name="description" content="{desc}">{noindex}
<meta property="og:type" content="website">
<meta property="og:site_name" content="La Cote du Héros">
<meta property="og:locale" content="fr_FR">
<meta property="og:title" content="{titre}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="https://lacoteduheros.fr/images/partage.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="La Cote du Héros : le guide de cote des livres dont vous êtes le héros, sur téléphone">
<meta name="twitter:card" content="summary_large_image">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#000000">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="preload" href="fonts/cormorant-garamond.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="fonts/source-sans-3.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="favicon-16.png">
<link rel="stylesheet" href="style.css">
</head>
<body class="annexe{' projet' if nom == 'le-projet.html' else ''}">
<a class="evitement" href="#main">Aller au contenu</a>

<div class="haut">
{BANDEAU}
{entete(nom)}
</div>

{PORTE if nom in GARDEES else ""}<main id="main" class="cadre page"{" hidden" if nom in GARDEES else ""}{f' data-niveau="{NIVEAU_PAGE[nom]}"' if nom in NIVEAU_PAGE else ""}>
{corps}
</main>

<footer class="pied">
  <div class="cadre pied-in">
    {PIED_LIENS}
    <p class="sous">La Cote du Héros · guide indépendant, sans publicité · mise à jour de cette page : {MAJ}.</p>
  </div>
</footer>

{barre(nom)}

{feuille(nom)}

<script src="plus.js"></script>
<script src="installer.js"></script>
<script src="identite.js"></script>
<script src="relais.js"></script>
<script src="cloud.js"></script>
<script src="scan.js"></script>
<script src="compte.js"></script>
<script src="pages.js"></script>{SCRIPT_PAGE.get(nom, "")}
</body>
</html>
'''


AJOUTER = '''<p class="surtitre">Contribuer</p>
<h1>Ajouter des livres</h1>
<p class="chapeau">Scannez les codes-barres un par un, ou collez une liste d'ISBN, un par ligne. Un envoi compte au plus 20 ISBN ; vous pouvez faire 3 envois par jour.</p>

<section class="carte" id="aj-carte" aria-labelledby="aj-titre">
  <h2 id="aj-titre">Liste à ajouter</h2>
  <label for="aj-texte">ISBN, un par ligne</label>
  <textarea id="aj-texte" rows="8" spellcheck="false" autocomplete="off" placeholder="9782070583805&#10;9791097577025"></textarea>
  <p class="sous" id="aj-compte" aria-live="polite">0 ISBN</p>
  <div class="rv-ajout-actions"><button type="button" class="bouton" id="aj-envoyer">Ajouter au guide</button></div>
  <p class="rv-ajout-bilan" id="aj-msg" role="status" hidden></p>
</section>
'''


GARDEES = ("revue-prix.html", "equipe.html", "evolutions.html", "ajouter.html", "butin.html")      # pages derrière la porte : Sorcier, Zagor, ou toute personne connectée (évolutions)
NIVEAU_PAGE = {"equipe.html": "superadmin", "revue-prix.html": "superadmin", "evolutions.html": "admin", "ajouter.html": "admin", "butin.html": "admin"}
def _version():          # même numéro que le service worker : les scripts changés ne restent pas en cache sur les pages gardées
    m = re.search(r"cdh-v(\d+)", (WEB / "sw.js").read_text(encoding="utf-8"))
    return m.group(1) if m else "0"


V = _version()
SCRIPT_PAGE = {"contact.html": '\n<script src="contact.js"></script>',
               "revue-prix.html": '\n<script src="acces.js?v=' + V + '"></script>\n<script src="revue.js?v=' + V + '"></script>',
               "equipe.html": '\n<script src="acces.js?v=' + V + '"></script>\n<script src="equipe.js?v=' + V + '"></script>',
               "evolutions.html": '\n<script src="acces.js"></script>',
               "ajouter.html": '\n<script src="acces.js"></script>\n<script src="ajouter.js"></script>',
               "butin.html": '\n<script src="acces.js?v=' + V + '"></script>\n<script src="revue.js?v=' + V + '"></script>'}
PORTE = '''<div class="porte" id="porte">
  <div class="porte-boite">
    <p class="porte-etiquette"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg> Espace réservé</p>
    <div class="porte-google" id="porte-google"></div>
  </div>
</div>
'''


PORTE_CONNECTE = PORTE.replace(" Espace réservé</p>", " Réservé aux personnes connectées</p>")




CONTACT = '''<p class="surtitre">Nous écrire</p>
<h1>Contact</h1>
<p class="chapeau">Une question, une erreur à signaler, un prix que vous avez constaté, une idée ou une proposition de collaboration : écrivez-moi avec le formulaire ci-dessous.</p>

<h2 id="formulaire">Envoyer un message</h2>
<form class="contact-form" id="contact-form" action="https://formsubmit.co/2d378aed4baf4cbd45b3c9db45512b9c" method="POST">
  <input type="hidden" name="_subject" value="Nouveau message via La Cote du Héros">
  <input type="hidden" name="_next" value="https://lacoteduheros.fr/contact.html?envoye=1">
  <input type="hidden" name="_template" value="table">
  <input type="hidden" name="_captcha" value="false">
  <input type="text" name="_honey" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">
  <div class="ct-champ"><label for="ct-nom">Votre nom (facultatif)</label><input id="ct-nom" type="text" name="nom" autocomplete="name" maxlength="80" placeholder="Comment vous appeler ?"></div>
  <div class="ct-champ"><label for="ct-email">Votre adresse électronique</label><input id="ct-email" type="email" name="email" autocomplete="email" required maxlength="120" placeholder="Pour pouvoir vous répondre"></div>
  <div class="ct-champ"><label for="ct-message">Votre message</label><textarea id="ct-message" name="message" required maxlength="4000" rows="6" placeholder="Une question, une erreur à signaler, un prix constaté, une idée…"></textarea></div>
  <button class="bouton" type="submit">Envoyer</button>
  <p class="form-sent" id="form-sent" role="status" aria-live="polite" tabindex="-1" hidden></p>
  <p class="sous">Vos coordonnées ne servent qu'à vous répondre. Le message passe par le service FormSubmit, qui le transmet à l'éditeur : voir <a href="confidentialite.html#contact">Confidentialité</a>.</p>
</form>

<h2>Pour signaler une erreur ou proposer un prix</h2>
<p>Dites-moi quel livre (le titre ou l'ISBN) et ce que vous avez constaté. Pour un prix, il m'aide de connaître l'<strong>état</strong> du livre (convenable, bon état, très bon état), le <strong>prix</strong> et la <strong>source</strong> (une vente, une annonce, une boutique) avec sa date.</p>

<h2>Vous voulez aider davantage</h2>
<ul>
  <li><a href="communaute.html">Communauté</a> : proposer une chaîne, un site ou une collection à faire connaître.</li>
</ul>
'''

TYPES_COMMUNAUTE = [
    ("chaine", "Chaînes vidéo"), ("podcast", "Podcasts"), ("site", "Sites et blogs"),
    ("collection", "Collectionneurs"), ("boutique", "Boutiques et éditeurs"),
]


def liste_communaute(donnees):
    """Sections HTML des liens de la communauté (données : web/data/communaute.json). Ne garde que les adresses https et échappe tout le texte."""
    import html as _h
    par_type = {k: [] for k, _ in TYPES_COMMUNAUTE}
    for l in donnees.get("liens", []):
        url = str(l.get("url", "")).strip()
        nom = str(l.get("nom", "")).strip()
        if not url.startswith("https://") or not nom or l.get("type") not in par_type:
            continue
        desc = str(l.get("description", "")).strip()
        par_type[l["type"]].append(
            f'<li class="comm-lien"><a href="{_h.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer"><strong>{_h.escape(nom)}</strong> <span aria-hidden="true">↗</span>'
            f'<span class="sr-only"> (nouvel onglet)</span></a>' + (f'<span class="sous">{_h.escape(desc)}</span>' if desc else "") + "</li>")
    sections = [f'<h2>{_h.escape(titre)}</h2>\n<ul class="comm-liste">\n' + "\n".join(par_type[k]) + "\n</ul>" for k, titre in TYPES_COMMUNAUTE if par_type[k]]
    return "\n\n".join(sections) if sections else '<p class="comm-vide">La liste se construit : les premières adresses arrivent bientôt. Vous en connaissez une qui mérite d\'y figurer ? <a href="contact.html">Écrivez-moi</a>.</p>'


def _donnees_communaute():
    try:
        return json.loads((WEB / "data" / "communaute.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def corps_communaute():
    return f'''<p class="surtitre">Passionnés</p>
<h1>Communauté</h1>
<p class="chapeau">Les livres dont vous êtes le héros vivent grâce à des passionnés : des chaînes, des sites, des collectionneurs, des boutiques. Voici ceux que nous aimons suivre.</p>

{liste_communaute(_donnees_communaute())}

<h2>Vous en faites partie ?</h2>
<p>Vous tenez une chaîne, un site, un podcast, une boutique, ou vous avez une collection que vous aimez partager ? <a href="contact.html">Écrivez-moi</a> avec l'adresse et deux lignes de présentation. La sélection se fait au cas par cas, et le guide reste gratuit et sans publicité.</p>
<p class="contact-mail"><a class="bouton" href="contact.html#formulaire">Proposer un lien</a></p>
'''


EQUIPE = '''<h1>Équipe</h1>
<p class="chapeau">Qui a accès à quoi, par personnage.</p>
<p class="sous" id="eq-etat" role="status">Chargement…</p>
<div class="eq-tuiles" id="eq-tuiles" hidden></div>
<section class="eq-bloc" aria-labelledby="eq-t-zagor">
  <h2 id="eq-t-zagor">Zagors</h2>
  <ul class="eq-liste" id="eq-zagors"></ul>
</section>
<section class="eq-bloc" aria-labelledby="eq-t-sorciers">
  <h2 id="eq-t-sorciers">Sorciers</h2>
  <ul class="eq-liste" id="eq-sorciers"></ul>
</section>
<section class="eq-bloc" aria-labelledby="eq-t-heros">
  <h2 id="eq-t-heros">Héros</h2>
  <p class="sous" id="eq-comptes-etat" role="status">Chargement…</p>
  <ul class="eq-comptes" id="eq-comptes"></ul>
</section>
<section class="eq-bloc" aria-labelledby="eq-t-ajout">
  <details class="eq-ajouter"><summary><h2 id="eq-t-ajout">Ajouter une personne</h2></summary>
  <form id="eq-ajout" class="eq-form">
    <label for="eq-adresse">Adresse Google</label>
    <input id="eq-adresse" type="email" autocomplete="off" required placeholder="prenom@gmail.com">
    <label for="eq-nom">Nom affiché</label>
    <input id="eq-nom" type="text" maxlength="30" autocomplete="off" required placeholder="Prénom">
    <label for="eq-niveau">Niveau</label>
    <select id="eq-niveau"><option value="admin">Sorcier</option><option value="superadmin">Zagor</option></select>
    <div id="eq-fin-champ" class="eq-dates">
      <label for="eq-debut">Début (facultatif)</label>
      <input id="eq-debut" type="date">
      <label for="eq-fin">Fin (facultative)</label>
      <input id="eq-fin" type="date">
      <p class="sous">Avant le début et après la fin, le sorcier est Héros. Vide : sans limite.</p>
    </div>
    <button type="submit" class="bouton">Ajouter</button>
  </form>
  <p class="sous">L'adresse n'est jamais gardée en clair, seulement son empreinte. Ajouter une adresse bloquée la débloque.</p>
  </details>
  <p class="rv-ajout-bilan" id="eq-msg" role="status" hidden></p>
</section>
<section class="eq-bloc" aria-labelledby="eq-t-bloques">
  <h2 id="eq-t-bloques">Comptes bloqués</h2>
  <p class="sous" id="eq-bloques"></p>
</section>
'''


REVUE = '''<h1>Prix et corrections</h1>
<div class="rv-identite" id="rv-identite" hidden></div>
<div class="rv-nav" id="rv-nav" role="tablist" aria-label="Sections de la page">
  <button type="button" role="tab" data-pane="prix" aria-selected="true"><svg class="rv-ico" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12V4h8l10 10-8 8L3 12z"/><circle cx="7.5" cy="8.5" r="1.2"/></svg><span>Prix</span></button>
  <button type="button" role="tab" data-pane="tendances" aria-selected="false" hidden><svg class="rv-ico" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/></svg><span>Tendances</span></button>
  <button type="button" role="tab" data-pane="annonces" aria-selected="false" hidden><svg class="rv-ico" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 6h13M8 12h13M8 18h13"/><path d="M3 6h.01M3 12h.01M3 18h.01"/></svg><span>Annonces</span></button>
  <button type="button" role="tab" data-pane="pepites" aria-selected="false" hidden><svg class="rv-ico" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3h12l4 6-10 12L2 9z"/><path d="M2 9h20"/></svg><span>Butin</span></button>
  <button type="button" role="tab" data-pane="ajout" aria-selected="false"><svg class="rv-ico" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg><span>Ajouter</span></button>
</div>
<div class="rv-pane" id="pane-prix" role="tabpanel">
<p class="chapeau">Un livre par ligne, avec ses trois prix. L'ancien prix est barré quand il a changé. Les prix qui ont beaucoup bougé sont marqués « À vérifier ». <strong>Confirmer</strong> garde un prix. <strong>Corriger</strong> en fixe un autre, qui prime sur eBay et sur les archives.</p>
<div class="rv-onglets" id="rv-onglets" role="group" aria-label="Quels livres voir ?">
  <button type="button" data-vue="verif" aria-pressed="true">À vérifier <span class="nb-onglet" id="rv-n-verif"></span></button>
  <button type="button" data-vue="change" aria-pressed="false">Changés <span class="nb-onglet" id="rv-n-change"></span></button>
  <button type="button" data-vue="valide" aria-pressed="false">Validés <span class="nb-onglet" id="rv-n-valide"></span></button>
  <button type="button" data-vue="tous" aria-pressed="false">Tous <span class="nb-onglet" id="rv-n-tous"></span></button>
</div>
<div class="rv-envoi" id="rv-envoi" hidden>
  <p id="rv-envoi-attente"><strong><span id="rv-n-attente"></span> validation(s) à transmettre.</strong> Elles sont gardées dans ce navigateur. « Envoyer » les enregistre pour tous en un clic, sous votre nom.</p>
  <button type="button" class="bouton" id="rv-envoyer">Envoyer mes validations</button>
  <p class="sous" id="rv-envoi-faites" role="status" hidden></p>
  <p class="rv-ajout-bilan" id="rv-envoi-msg" role="status" hidden></p>
</div>
<div class="rv-outils">
  <div class="champ"><label for="rv-q">Chercher un livre</label><input type="search" id="rv-q" autocomplete="off" placeholder="titre ou série"></div>
  <div class="champ"><label for="rv-serie">Série</label><select id="rv-serie"></select></div>
</div>
<p class="sous" id="rv-compte" role="status" aria-live="polite"></p>
<p><button type="button" class="bouton bouton-clair" id="rv-tout-confirmer">Tout confirmer dans cette liste</button></p>
<div id="rv-liste"><p>Chargement…</p></div>
<p><button type="button" class="bouton bouton-clair" id="rv-plus" hidden>Voir la suite</button>
<button type="button" class="bouton bouton-clair" id="rv-csv">Télécharger cette liste (tableur)</button></p>
<details class="rv-aide"><summary>Comment lire cette page</summary>
<ul>
  <li><strong>Le gros prix</strong> est celui affiché sur le site. <strong>Le prix barré</strong> est l'ancienne cote (ancien relevé de 2024). Le pourcentage montre le changement.</li>
  <li><strong>« À vérifier »</strong> : le prix a au moins doublé ou a été divisé par près de deux. Une raison est écrite en dessous.</li>
  <li>La ligne grise sous chaque prix donne son origine. « d'après N annonces eBay » : prix actuel. « ancienne cote » : pas de relevé récent. « déduit des autres états » : estimé à partir des autres états. « ajusté » : corrigé pour que convenable ≤ bon état ≤ très bon état.</li>
  <li><strong>Confirmer / Corriger</strong> : votre prix remplace celui du site, y compris aux prochains relevés. « Retirer » annule une validation pas encore transmise.</li>
  <li>Cliquez sur le titre d'un livre pour ouvrir sa fiche sur le site.</li>
</ul>
</details>
</div>
<div class="rv-pane" id="pane-tendances" role="tabpanel" hidden>
<section class="rv-ajout rv-tendances" id="rv-tendances" aria-labelledby="tr-titre" hidden>
  <h2 id="tr-titre">Tendances des prix</h2>
  <p class="sous" id="tr-resume"></p>
  <div class="tr-onglets" id="tr-onglets" role="tablist" aria-label="Regrouper par">
    <button type="button" role="tab" data-dim="decennie" aria-selected="true">Année d'édition</button>
    <button type="button" role="tab" data-dim="version" aria-selected="false">Version</button>
    <button type="button" role="tab" data-dim="serie" aria-selected="false">Série</button>
    <button type="button" role="tab" data-dim="editeur" aria-selected="false">Éditeur</button>
  </div>
  <ul class="tr-liste" id="tr-liste"></ul>
  <label class="tr-option"><input type="checkbox" id="tr-editeur"> Inclure les prix des éditeurs (nouveautés)</label>
  <p class="sous" id="tr-note"></p>
  <h3 class="tr-sous-titre">Évolution dans le temps</h3>
  <div id="tr-temps"></div>
</section>
</div>
<div class="rv-pane" id="pane-annonces" role="tabpanel" hidden>
  <p class="chapeau">Les annonces retenues pour calculer les cotes : eBay, librairies, Leboncoin, Vinted. Sans recherche, les plus récentes s'affichent. Ouvrez une annonce pour vérifier le livre et son état.</p>
  <div class="champ"><label for="an-q">Chercher un livre</label><input type="search" id="an-q" autocomplete="off" placeholder="Titre ou série"></div>
  <p class="sous" id="an-etat" role="status" aria-live="polite"></p>
  <div id="an-liste"></div>
</div>
<div class="rv-pane" id="pane-pepites" role="tabpanel" hidden>
  <p class="chapeau">Les bonnes affaires : <strong>50 % du prix du site ou moins</strong>, même édition, même état, 3 € d'économie au moins. Ouvrez l'annonce pour vérifier le livre, l'état et les frais de port.</p>
  <div class="pp-barre">
    <p class="sous" id="pp-etat" role="status" aria-live="polite"></p>
    <div class="pp-outils">
      <label class="pp-tri"><span>Trier par</span><select id="pp-tri">
        <option value="solides">Solides d'abord</option>
        <option value="eco">Plus grosse économie</option>
        <option value="pct">Plus forte réduction</option>
        <option value="prix">Prix de l'annonce, croissant</option>
        <option value="date">Nouvelles annonces d'abord</option>
        <option value="titre">Titre, de A à Z</option>
      </select></label>
      <label class="case"><input type="checkbox" id="pp-trouver"><span>Mes « à trouver » seulement</span></label>
      <label class="case"><input type="checkbox" id="pp-solides"><span>Seulement les solides</span></label>
    </div>
  </div>
  <div id="pp-liste"></div>
</div>
<div class="rv-pane" id="pane-ajout" role="tabpanel" hidden>
<section class="rv-ajout" aria-labelledby="aj-titre">
  <h2 id="aj-titre">Ajouter des livres</h2>
  <p>Collez un ou plusieurs ISBN, un par ligne (les tirets sont acceptés). Pour un livre qu'aucun catalogue ne connaît, ajoutez après l'ISBN la série, le numéro et le titre, séparés par un point-virgule :</p>
  <p><code class="aj-exemple">9791097577025 ; Fabled Lands ; 1 ; Le Royaume déchiré</code></p>
  <p>Pour un livre sans ISBN, écrivez son titre, puis éventuellement la série et le numéro :</p>
  <p><code class="aj-exemple">Cthulhu, le pacte d'Innsmouth ; L'Appel de Cthulhu ; 3</code></p>
  <label class="sr-only" for="aj-texte">Liste d'ISBN</label>
  <textarea id="aj-texte" rows="6" spellcheck="false" autocomplete="off" placeholder="9791097577025&#10;2-07-033370-1&#10;9782070583805 ; Destins ; 731 ; Le Pirate des Sept Mers&#10;Cthulhu, le pacte d'Innsmouth"></textarea>
  <div class="rv-ajout-actions"><button type="button" class="bouton" id="aj-verifier">Vérifier la liste</button></div>
  <div id="aj-resultat" hidden>
    <p id="aj-bilan" class="rv-ajout-bilan" role="status"></p>
    <ul id="aj-liste" class="aj-liste"></ul>
    <p class="rv-ajout-etapes"><strong>Pour les enregistrer</strong> : <span id="aj-etapes"></span></p>
    <p class="rv-ajout-bilan" id="aj-msg" role="status" hidden></p>
    <div class="rv-ajout-actions">
      <button type="button" class="bouton" id="aj-lancer" hidden>Ajouter maintenant</button>
      <button type="button" class="bouton" id="aj-copier">Copier la liste à ajouter</button>
      <button type="button" class="bouton-lien" id="aj-telecharger">Télécharger la liste</button>
    </div>
  </div>
</section>
</div>
'''


def stats_catalogue():
    """(éditions, livres, séries) d'après web/data/versions.json, pour que la page ne vieillisse pas."""
    try:
        v = json.loads((WEB / "data" / "versions.json").read_text(encoding="utf-8"))
        return len(v), len({b["livre_id"] for b in v}), len({b["serie"] for b in v})
    except (OSError, ValueError, KeyError):
        return None


def _nombres_catalogue():
    st = stats_catalogue()
    return f"{st[0]} éditions, rattachées à {st[1]} livres et à {st[2]} séries" if st else "Toutes les éditions que nous avons pu recenser"


LE_PROJET = f'''<p class="surtitre">À propos du guide</p>
<h1>Le projet</h1>
<p class="chapeau">La Cote du Héros est un guide indépendant, gratuit et sans publicité, fait pour les collectionneurs de livres dont vous êtes le héros : tenir sa collection à jour, la suivre dans le temps et trouver les livres qui lui manquent.</p>

<figure class="projet-large"><img src="images/accueil-4.webp" alt="" width="1122" height="1114" loading="lazy" decoding="async"></figure>

<h2>À quoi sert ce site</h2>
<p>C'est d'abord un outil pour <strong>tenir sa collection à jour et la suivre dans le temps</strong>. Vous indiquez les livres et les éditions que vous possédez, dans l'état où ils sont, et le guide garde la trace de ce que vous avez, de ce qu'il vous manque et de la façon dont votre collection grandit.</p>
<p>Il sert ensuite à <strong>trouver les livres</strong> : voir ce qu'il reste à chercher pour finir une série, retrouver la bonne édition, repérer les nouveautés et les livres annoncés. Il garde aussi une liste « À trouver » pour ceux que vous cherchez.</p>
<p>Les <strong>prix</strong> viennent après, comme de simples repères : ils aident à comprendre ce qu'un livre vaut à peu près. Ce ne sont ni des prix d'achat ni des prix de vente, et aucune cote ne vous dit « achetez » ou « vendez ». Le guide est fait pour les collectionneurs, pas pour les traders (c'est dit avec le sourire, mais c'est sérieux).</p>

<div class="projet-trio" aria-hidden="true">
  <img src="images/accueil-1.webp" alt="" width="992" height="1504" loading="lazy" decoding="async">
  <img src="images/accueil-3.webp" alt="" width="1214" height="1295" loading="lazy" decoding="async">
  <img src="images/accueil-5.webp" alt="" width="1215" height="1295" loading="lazy" decoding="async">
</div>
<p class="projet-legende">Des mondes à parcourir, des livres à retrouver.</p>

<h2>Pourquoi ce guide</h2>
<p>Les livres-jeux ont paru en plusieurs éditions, chez plusieurs éditeurs, pendant près de quarante ans. Savoir de quelle édition on parle est la première difficulté du collectionneur : un même titre existe sous plusieurs couvertures, et seul le numéro d'ISBN les distingue vraiment. Ce guide réunit toutes les éditions au même endroit, pour les reconnaître, les comparer et dire lesquelles vous avez.</p>

<h2>Ce que vous y trouvez</h2>
<ul>
  <li>{_nombres_catalogue()}, avec leur jaquette et leur fiche (éditeur, année, pages, auteurs).</li>
  <li>Une <strong>collection</strong> à tenir à jour, avec un inventaire guidé pour la constituer sans tout saisir à la main, et une liste « À trouver ». Les deux sont enregistrées dans votre Google Drive.</li>
  <li>Les <strong>nouveautés</strong> et les livres <strong>à paraître</strong>, repérés chaque jour.</li>
  <li>Pour chaque édition, un repère de prix par état : <strong>convenable, bon état, très bon état (TBE)</strong>.</li>
  <li>Une page <a href="evolutions.html">Évolutions des prix</a>, ce qui monte, ce qui baisse, et d'où viennent les changements.</li>
</ul>

<h2>Comment les prix sont estimés</h2>
<p><strong>Une cote est une estimation, jamais un prix fixé.</strong> Elle donne un ordre de grandeur, pas la somme qu'on obtiendra.</p>
<ul>
  <li><strong>L'ancien relevé.</strong> Point de départ du guide : des cotes d'archives, qui ne sont plus tenues à jour. Quand rien de plus récent n'existe, c'est lui qui s'affiche, et la fiche le dit.</li>
  <li><strong>Les annonces actuelles.</strong> Le guide relève régulièrement les annonces en ligne d'une plateforme, par son interface officielle et sous réserve de ses conditions d'utilisation. On n'en garde que des chiffres d'ensemble (nombre, minimum, médiane, maximum) : ni titre d'annonce, ni vendeur. Une annonce est un prix demandé, pas un prix payé : le guide ne la corrige pas et le signale.</li>
  <li><strong>Les prix des éditeurs.</strong> Pour les nouveautés encore en vente neuve, le prix de l'éditeur sert de repère pour le très bon état.</li>
  <li><strong>Les prix validés.</strong> Un prix peut être confirmé ou corrigé après vérification : ce prix prime alors sur tout le reste, et la fiche indique qu'il a été validé, et quand.</li>
</ul>
<p>Quand plusieurs sources existent, la cote est une <strong>médiane pondérée</strong> : une vente réelle compte plus qu'une annonce, qui compte plus qu'une archive, et un prix récent compte plus qu'un prix ancien (le poids est divisé par deux tous les 90 jours, tous les 365 jours pour l'ancien relevé). Un état sans prix est déduit des autres états de la même édition (le bon état vaut environ 60 % du très bon état, le convenable environ 40 %), et la fiche l'indique.</p>
<p>La fiche de chaque édition précise la nature du prix, le nombre d'observations, leur date et un niveau de confiance.</p>

<h2>Ce que vous pouvez faire</h2>
<p>Consulter le guide est libre. Le compte Héros est un compte Google, gratuit : il ouvre tout le reste.</p>
<div class="tableau-page">
<table class="tableau-droits">
  <thead><tr><th scope="col">Fonction</th><th scope="col">Visiteur</th><th scope="col">Héros</th></tr></thead>
  <tbody>
    <tr><th scope="row" data-label="Fonction">Chercher un livre par titre, auteur ou ISBN</th><td data-label="Visiteur"><span aria-label="oui">✓</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Parcourir l'étagère, filtrer et trier (série, édition, année, éditeur, prix)</th><td data-label="Visiteur"><span aria-label="oui">✓</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Ouvrir les fiches : jaquette, détails, rareté d'après les tirages</th><td data-label="Visiteur"><span aria-label="oui">✓</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Voir les derniers ajouts et les livres à paraître</th><td data-label="Visiteur"><span aria-label="oui">✓</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Lire les notes moyennes des livres</th><td data-label="Visiteur"><span aria-label="oui">✓</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Voir les prix</th><td class="txt" data-label="Visiteur">Un niveau, de <span class="nowrap">€ à €€€€€</span></td><td class="txt" data-label="Héros">L'estimation, par état et par livre</td></tr>
    <tr><th scope="row" data-label="Fonction">Chercher l'édition en vente (Leboncoin, Vinted, eBay, Facebook)</th><td data-label="Visiteur"><span aria-label="non">—</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Constituer sa collection : état et nombre d'exemplaires</th><td data-label="Visiteur"><span aria-label="non">—</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Scanner le code-barres d'un livre pour l'ajouter</th><td data-label="Visiteur"><span aria-label="non">—</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Compléter sa collection pas à pas, série par série</th><td data-label="Visiteur"><span aria-label="non">—</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Importer ou exporter sa collection</th><td data-label="Visiteur"><span aria-label="non">—</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Suivre la valeur de sa collection et l'analyser</th><td data-label="Visiteur"><span aria-label="non">—</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Séparer ses doubles à vendre et les livres à trouver</th><td data-label="Visiteur"><span aria-label="non">—</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Retrouver sa collection sur tous ses appareils (Google Drive), et une ancienne version si besoin</th><td data-label="Visiteur"><span aria-label="non">—</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Ajouter un livre au guide</th><td data-label="Visiteur"><span aria-label="non">—</span></td><td data-label="Héros"><span aria-label="non">—</span></td></tr>
    <tr><th scope="row" data-label="Fonction">Noter les livres de 1 à 5</th><td data-label="Visiteur"><span aria-label="non">—</span></td><td data-label="Héros"><span aria-label="oui">✓</span></td></tr>
  </tbody>
</table>
</div>
<p>Le compte ne sert qu'à cela. Le guide ne voit ni votre courriel ni vos autres fichiers, et vous pouvez tout supprimer à tout moment : voir la page <a href="confidentialite.html">Confidentialité</a>.</p>

<h2>D'où viennent les données</h2>
<ul>
  <li><strong>Catalogue et fiches :</strong> notices du catalogue général de la Bibliothèque nationale de France, complétées à partir de l'ancien relevé.</li>
  <li><strong>Prix :</strong> voir « Comment les prix sont estimés » ci-dessus.</li>
  <li><strong>Rareté :</strong> le nombre de tirages de chaque édition Gallimard, compilé par Thomtom d'après le site exlibris.to, et la part des collections qui possèdent le livre (collection-ldvelh.fr). C'est une information : elle n'entre pas dans la cote.</li>
  <li><strong>Jaquettes :</strong> © leurs éditeurs, reproduites à titre d'illustration.</li>
  <li><strong>Polices :</strong> Cormorant Garamond et Source Sans 3, sous licence SIL Open Font 1.1, hébergées avec le site.</li>
</ul>

<h2>Ce que le guide ne fait pas</h2>
<p>Il ne vend rien et ne contient ni publicité ni lien d'affiliation : les boutons Vinted, Leboncoin, eBay et Facebook des fiches (réservés aux Héros) ouvrent de simples recherches sur ces sites, sans rien rapporter au guide. Consulter les fiches ne demande aucun compte, et le guide ne mesure pas votre visite. Il ne recopie pas les sites d'annonces ou de comparaison de prix qui interdisent la collecte automatique de leurs pages : cette interdiction est respectée.</p>

<h2>Votre collection</h2>
<p>La collection que vous composez est enregistrée dans votre navigateur, sur votre appareil. Rien n'est envoyé à un serveur. Les détails sont dans la page <a href="confidentialite.html">Confidentialité</a>.</p>

<div class="projet-duo" aria-hidden="true">
  <img src="images/projet-glace.webp" alt="" width="1024" height="1100" loading="lazy" decoding="async">
  <img src="images/projet-hydre.webp" alt="" width="800" height="1100" loading="lazy" decoding="async">
</div>

<h2>Contribuer</h2>
<ul>
  <li><strong>Signaler une erreur, proposer un prix :</strong> une édition manquante, une fiche erronée, un prix que vous avez constaté. Écrivez-moi depuis la page <a href="contact.html">Contact</a>.</li>
  <li><strong>Ajouter un livre :</strong> la page « Ajouter des livres » est réservée à l'équipe du guide.</li>
  <li><strong>Faire connaître votre chaîne, votre site ou votre boutique :</strong> voir la page <a href="communaute.html">Communauté</a>.</li>
</ul>

<h2 id="contact">Le formulaire de contact</h2>
<p>Le formulaire de la page <a href="contact.html">Contact</a> envoie votre message au service <strong>FormSubmit</strong> (<a href="https://formsubmit.co" target="_blank" rel="noopener">formsubmit.co</a>), qui le transmet par courriel à l'éditeur. Il reçoit ce que vous écrivez : votre nom si vous le donnez, votre adresse électronique et le texte du message. Ces informations ne servent qu'à vous répondre : elles ne sont ni publiées ni utilisées pour autre chose, et l'éditeur ne les garde pas plus longtemps que nécessaire pour traiter votre demande. Vous pouvez demander leur effacement par ce même formulaire. Rien n'est envoyé tant que vous n'avez pas cliqué sur « Envoyer ».</p>

<h2>Soutenir le guide</h2>
<p>Le guide reste gratuit et sans publicité. S'il vous est utile, vous pouvez <a href="https://buymeacoffee.com/obertrand9s" target="_blank" rel="noopener noreferrer">offrir un café</a> : cela aide à couvrir les frais du site, notamment son adresse web. C'est libre et sans aucune obligation.</p>
'''

CONFIDENTIALITE = f'''<p class="surtitre">Vos données</p>
<h1>Confidentialité</h1>
<p class="chapeau">En bref : <strong>consulter La Cote du Héros ne demande aucun compte et ne dépose aucun cookie.</strong> Pas de mesure d'audience, pas de publicité. Pour constituer une collection, noter un livre ou demander un ajout, vous vous connectez avec Google : votre collection est alors enregistrée dans votre propre Google Drive, pas chez l'éditeur.</p>

<h2>Ce qui est enregistré sur votre appareil</h2>
<p>Pour fonctionner comme vous le demandez, le guide écrit quelques enregistrements dans le stockage de votre navigateur. Ils ne quittent votre appareil que pour rejoindre votre propre Google Drive si vous êtes connecté, et l'éditeur n'y a pas accès.</p>
<div class="tableau-page">
<table>
  <thead><tr><th scope="col">Nom</th><th scope="col">Contenu</th><th scope="col">Pourquoi</th></tr></thead>
  <tbody>
    <tr><td data-label="Nom"><code>cote-collection-v1</code></td><td data-label="Contenu">Les livres de « Ma collection », leur état, leur quantité</td><td data-label="Pourquoi">Conserver votre collection d'une visite à l'autre</td></tr>
    <tr><td data-label="Nom"><code>cote-souhaits-v1</code></td><td data-label="Contenu">Les livres de votre liste « À trouver »</td><td data-label="Pourquoi">Retenir ce que vous cherchez</td></tr>
    <tr><td data-label="Nom"><code>cote-parcours-v1</code></td><td data-label="Contenu">L'avancement de l'inventaire guidé</td><td data-label="Pourquoi">Reprendre là où vous en étiez</td></tr>
    <tr><td data-label="Nom"><code>cote-collection-avant-reprise</code></td><td data-label="Contenu">Une copie de sécurité de votre collection, faite avant de la fusionner avec celle de votre compte</td><td data-label="Pourquoi">Ne rien perdre à la première connexion</td></tr>
    <tr><td data-label="Nom"><code>cdh-cloud-lie</code></td><td data-label="Contenu">Votre prénom Google, pour l'afficher, et le fait que vous êtes connecté</td><td data-label="Pourquoi">Savoir que votre collection est liée à votre compte</td></tr>
    <tr><td data-label="Nom"><code>cdh-cloud-meta</code></td><td data-label="Contenu">La date de dernière modification de chaque livre</td><td data-label="Pourquoi">Fusionner proprement votre collection entre plusieurs appareils</td></tr>
    <tr><td data-label="Nom"><code>cdh-cloud-jeton</code></td><td data-label="Contenu">Le laissez-passer donné par Google, valable environ une heure</td><td data-label="Pourquoi">Ne pas vous redemander la connexion à chaque page ; effacé à la fin de sa validité ou à la déconnexion</td></tr>
    <tr><td data-label="Nom"><code>cdh-role</code> et <code>cdh-notes</code></td><td data-label="Contenu">Votre niveau d'accès et les moyennes des notes, gardés dans l'onglet</td><td data-label="Pourquoi">Afficher les bons menus et éviter de redemander les notes pendant dix minutes ; effacés à la fermeture de l'onglet</td></tr>
    <tr><td data-label="Nom"><code>cdh-avis-donne</code>, <code>cdh-avis-ferme</code>, <code>cdh-visites</code> et <code>cdh-bienvenue</code></td><td data-label="Contenu">Le fait que vous avez déjà répondu à « Qu'en pensez-vous ? » ou fermé le bandeau, les dates de vos visites, et le fait que l'accueil a été affiché</td><td data-label="Pourquoi">Ne proposer l'avis qu'aux visiteurs réguliers, une seule fois ; ces données restent sur votre appareil</td></tr>
    <tr><td data-label="Nom"><code>cdh-fiches-vues</code>, <code>cdh-invite-vue</code> et <code>cdh-invite-fiches</code></td><td data-label="Contenu">Les fiches consultées pendant la visite (effacées à la fermeture de l'onglet), et la date à laquelle l'invitation à se connecter a été montrée</td><td data-label="Pourquoi">Proposer la connexion une seule fois, après quelques fiches, et pas plus d'une fois par mois</td></tr>
    <tr><td data-label="Nom"><code>cdh-scan-etat</code>, <code>cdh-coll-pane</code>, <code>cdh-pane</code></td><td data-label="Contenu">Vos réglages d'affichage (état choisi pour le scan, onglet ouvert)</td><td data-label="Pourquoi">Retrouver la page comme vous l'avez laissée</td></tr>
    <tr><td data-label="Nom"><code>cdh-installer-ferme-jusqu-au</code></td><td data-label="Contenu">La date jusqu'à laquelle le bandeau d'installation reste masqué (quatorze jours)</td><td data-label="Pourquoi">Ne pas vous le montrer en boucle si vous l'avez fermé</td></tr>
  </tbody>
</table>
</div>
<p>Le guide garde aussi des copies de ses propres pages et images dans la mémoire de votre navigateur (cache), pour s'ouvrir sans réseau. Elles ne contiennent aucune donnée sur vous.</p>
<p><strong>Aucun cookie</strong> n'est déposé. Ces enregistrements sont nécessaires à des fonctions que vous demandez vous-même ; ils ne demandent donc pas de consentement et il n'y a pas de bandeau.</p>

<h2>Appareil photo et lecture des codes-barres</h2>
<p>Pour ajouter un livre en scannant son code-barres, le site vous demande l'autorisation d'utiliser l'appareil photo, à chaque usage selon votre navigateur. L'image est analysée dans votre navigateur par un composant libre (ZXing) hébergé avec le site : <strong>aucune image ni photo n'est enregistrée ni envoyée</strong>. Seul le numéro lu (l'ISBN) est utilisé, pour retrouver le livre. Vous pouvez refuser l'autorisation et saisir le numéro à la main.</p>

<h2>Si vous vous connectez avec Google</h2>
<p>Le site demande à Google trois choses : votre prénom, pour l'afficher, votre adresse électronique, pour vous reconnaître (elle n'est lue que par le service décrit plus bas), et l'accès à un <strong>espace réservé de votre Google Drive</strong> (le droit « données d'application », que Google classe comme non sensible). Cet espace n'apparaît pas dans vos fichiers, et seul ce site peut l'ouvrir. Votre collection et votre liste « À trouver » vont directement de votre navigateur à votre Drive, sans passer chez l'éditeur, qui ne voit pas vos autres fichiers. Le laissez-passer donné par Google reste sur cet appareil et s'efface au bout d'une heure ou à la déconnexion ; il n'est envoyé qu'à Google et, quand vous utilisez une fonction qui en a besoin, au service.</p>
<p>Google intervient à votre demande comme prestataire de stockage, selon <a href="https://policies.google.com/privacy" target="_blank" rel="noopener">sa propre politique de confidentialité</a>. Votre navigateur contacte Google quand vous cliquez sur « Se connecter », puis à chaque sauvegarde de votre collection dans votre Drive.</p>

<h2>Le service du site</h2>
<p>Certaines fonctions passent par un service technique géré par l'éditeur et hébergé chez Google. Il sert à afficher les moyennes des notes, à enregistrer vos notes, à gérer votre session de connexion et à permettre à l'éditeur de corriger les prix et les fiches.</p>
<ul>
  <li><strong>Sans connexion</strong> : à l'ouverture de la plupart des pages, le site interroge le service pour afficher les moyennes des notes. Google reçoit alors, comme tout serveur, l'adresse IP et le type de navigateur du visiteur. Aucune donnée sur vous n'est envoyée.</li>
  <li><strong>Connecté</strong> : votre laissez-passer est transmis au service, qui le vérifie auprès de Google et en tire une <strong>empreinte</strong>, un code calculé à partir de votre adresse qui ne permet pas de la retrouver. Il s'en sert pour vous reconnaître et pour savoir à quel niveau vous êtes. Le relais ne conserve ni votre adresse ni votre nom : seulement cette empreinte, avec ce que vous lui demandez d'enregistrer (une note, une demande).</li>
</ul>

<h2>Notes des livres</h2>
<p>Une fois connecté, vous pouvez noter un livre de 1 à 5. Votre note est enregistrée dans le service avec une <strong>empreinte courte de votre compte</strong> : un code qui ne contient ni votre adresse ni votre nom, mais qui permet de reconnaître que vous avez déjà voté, pour que chacun ne vote qu'une fois par livre. La moyenne et le nombre d'avis de chaque livre sont publics ; la note donnée par chaque personne ne l'est pas. Vous pouvez la modifier ou la retirer à tout moment depuis la fiche du livre.</p>

<h2>Première connexion et avis</h2>
<p>La première fois qu'un compte se connecte, le service l'enregistre sous une empreinte courte (jamais l'adresse) pour compter les comptes, et prévient l'éditeur par courriel avec votre <strong>prénom</strong> seulement. Ce prénom et la date de votre arrivée sont aussi gardés dans une liste privée, que seul l'éditeur peut consulter, jamais votre adresse. Si vous répondez à « Qu'en pensez-vous ? » (note de 1 à 5 étoiles et commentaire facultatif), votre réponse est envoyée par courriel à l'éditeur, avec votre prénom et sans votre adresse. L'avis est personnel : il n'est lu que par l'éditeur, il n'est jamais publié et n'est utilisé que pour améliorer le guide.</p>

<h2>Ajouter un livre</h2>
<p>Des livres sont ajoutés au guide, un par un avec le scanner ou par une liste d'ISBN. Le nom de la personne qui ajoute apparaît dans l'historique public des modifications, comme pour les corrections.</p>

<h2>Soutenir le guide</h2>
<p>Le lien « Offrir un café » ouvre la page du guide sur Buy Me a Coffee, un service extérieur. Le don se fait chez ce service, selon ses propres règles. Il peut communiquer à l'éditeur les informations de votre don (par exemple le nom et le message que vous laissez). Le guide lui-même ne reçoit rien et n'enregistre rien à ce sujet.</p>

<h2>Comment les effacer</h2>
<ul>
  <li>Votre collection : bouton « Tout effacer » dans la section Ma collection, ou « Repartir de zéro » dans l'inventaire guidé.</li>
  <li>Vos notes : « Retirer ma note » dans la fiche du livre noté.</li>
  <li>Les anciennes versions de votre collection gardées par Google Drive (historique du fichier) : elles disparaissent avec « Supprimer ma collection du Drive » ou avec le retrait de l'accès.</li>
  <li>Votre collection dans le Drive : « Supprimer ma collection du Drive » dans le menu du compte, ou retirez l'accès à ce site depuis <a href="https://myaccount.google.com/permissions" target="_blank" rel="noopener">myaccount.google.com</a>.</li>
  <li>Une demande d'ajout publiée : écrivez à l'éditeur par la page <a href="contact.html">Contact</a> pour la faire retirer.</li>
  <li>Tout le reste : effacez les données du site dans les réglages de votre navigateur.</li>
</ul>

<h2>Fichiers de sauvegarde</h2>
<p>Le fichier que vous téléchargez (JSON ou CSV) est créé dans votre navigateur et enregistré chez vous. Quand vous chargez un fichier pour le retrouver, il est lu dans votre navigateur, sans être envoyé nulle part. Vous en restez seul responsable : il contient la liste de vos livres.</p>

<h2>Hébergement et journaux techniques</h2>
<p>Le site est hébergé par la société indiquée dans les <a href="mentions-legales.html">mentions légales</a> ; la connexion, la sauvegarde dans votre Drive et le service passent par Google. Comme tout hébergeur, l'hébergeur du site et Google peuvent enregistrer des informations techniques lors d'une visite, comme l'adresse IP et le type de navigateur, pour assurer le service et sa sécurité. Ces journaux relèvent de ces sociétés et non de l'éditeur, qui n'y a pas accès. Elles sont établies aux États-Unis ; leur traitement des données est décrit dans leurs déclarations de confidentialité, dont celle de Google : <a href="https://policies.google.com/privacy" target="_blank" rel="noopener">politique de confidentialité de Google</a>.</p>

<h2>Ressources et liens externes</h2>
<p>Les polices, les images, les jaquettes et les données sont hébergées avec le site. Pour s'afficher, le guide n'appelle qu'un service extérieur : le service, chez Google, pour les moyennes des notes (voir plus haut). Seuls les liens sur lesquels vous cliquez vous emmènent ailleurs : notice de la BnF, recherches sur Vinted, Leboncoin, eBay, Facebook, Amazon et la Fnac, fiches de leslibraires.fr, Buy Me a Coffee. Ces sites ont leurs propres règles de confidentialité. Les liens vers les sites de vente sont de simples recherches : le guide n'en tire aucun revenu.</p>

<h2>Vos droits</h2>
<p>Votre collection est dans votre Drive : vous pouvez la consulter, la corriger ou l'effacer vous-même. Vos notes se retirent depuis la fiche du livre. Pour exercer vos droits d'accès, de rectification, d'effacement ou d'opposition sur ce que le guide détient (une note, une demande d'ajout, une inscription à l'équipe), ou pour toute question, écrivez à l'éditeur par la page <a href="contact.html">Contact</a>. Vous pouvez aussi saisir la CNIL (<a href="https://www.cnil.fr/fr/plaintes" target="_blank" rel="noopener">cnil.fr/fr/plaintes</a>).</p>

<h2>Si cela change</h2>
<p>Si le guide devait un jour mesurer sa fréquentation ou ajouter un service qui touche à vos données, cette page serait mise à jour avant, et un consentement serait demandé quand la loi l'exige. Dernière mise à jour : {MAJ_LEGAL}.</p>
'''

MENTIONS = f'''<p class="surtitre">Informations légales</p>
<h1>Mentions légales</h1>

<h2>Éditeur du site</h2>
<p>La Cote du Héros est un site personnel, non commercial.</p>
<ul>
  <li><strong>Éditeur et directeur de la publication</strong> : un particulier, qui agit à titre non professionnel et reste anonyme à l'égard du public. Conformément à l'article 6 de la loi du 21 juin 2004 (LCEN), son identité a été communiquée à l'hébergeur, qui peut la transmettre à l'autorité judiciaire</li>
  <li><strong>Contact</strong> : par le <a href="contact.html#formulaire">formulaire de la page Contact</a>.</li>
</ul>

<h2>Hébergeur</h2>
<ul>
  <li><strong>GitHub, Inc.</strong> (service GitHub Pages), qui héberge le site</li>
  <li>Adresse : 88 Colin P. Kelly Jr. Street, San Francisco, CA 94107, États-Unis</li>
  <li>Site : <a href="https://pages.github.com" target="_blank" rel="noopener">pages.github.com</a></li>
</ul>

<h2>Services de connexion et de sauvegarde</h2>
<p>La connexion avec Google, l'enregistrement de votre collection dans votre Google Drive et le service du site (notes, ajouts de livres, outils de l'équipe, hébergé chez Google) sont assurés par <strong>Google LLC</strong>, 1600 Amphitheatre Parkway, Mountain View, CA 94043, États-Unis (<a href="https://about.google" target="_blank" rel="noopener">about.google</a>). La page <a href="confidentialite.html">Confidentialité</a> détaille ce qui leur est transmis.</p>
<p>Les messages envoyés par le formulaire de la page Contact sont acheminés par le service <strong>FormSubmit</strong> (<a href="https://formsubmit.co" target="_blank" rel="noopener">formsubmit.co</a>), qui les transmet à l'éditeur par courriel.</p>

<h2>Propriété intellectuelle</h2>
<ul>
  <li><strong>Textes, calculs et code du guide</strong> : © La Cote du Héros, tous droits réservés.</li>
  <li><strong>Jaquettes</strong> : © leurs éditeurs, reproduites à titre d'illustration d'un guide non commercial. Un ayant droit qui souhaiterait le retrait d'une image peut le demander par le contact ci-dessus.</li>
  <li><strong>Données bibliographiques</strong> : catalogue général de la Bibliothèque nationale de France.</li>
  <li><strong>Illustrations de l'accueil</strong> : images générées par intelligence artificielle pour le guide, choisies par l'éditeur.</li>
  <li><strong>Polices</strong> : Cormorant Garamond (© The Cormorant Project Authors) et Source Sans 3 (© Adobe), licence SIL Open Font 1.1.</li>
</ul>

<h2>Responsabilité</h2>
<p>Les cotes sont des estimations indicatives, établies à partir de données d'archives et d'observations partielles. Elles n'ont aucune valeur contractuelle, ne remplacent ni une expertise ni un prix de vente réel, et l'éditeur ne garantit ni leur exactitude ni leur actualité. Chaque cote indique sa nature et son ancienneté. Les liens vers des sites extérieurs n'engagent pas leurs éditeurs ni celui de ce guide.</p>

<h2>Données personnelles et cookies</h2>
<p>Le site ne dépose aucun cookie, ne mesure pas sa fréquentation et ne contient aucune publicité. Consulter les cotes ne demande aucune donnée personnelle. Si vous vous connectez avec Google, votre collection est enregistrée dans votre propre Google Drive ; vos notes et vos demandes d'ajout sont enregistrées avec une empreinte de votre compte (jamais votre adresse), par un relais hébergé chez Google. L'éditeur est responsable de ces notes et de ces demandes : pour exercer vos droits, voir la page <a href="confidentialite.html">Confidentialité</a>.</p>

<h2>Droit applicable</h2>
<p>Le site est soumis au droit français. Il ne propose ni vente ni service payant : aucune médiation de la consommation n'est donc applicable. Le lien « Offrir un café » mène à un service extérieur (Buy Me a Coffee) où l'on peut faire un don libre : un don n'est ni une vente ni la contrepartie d'un service.</p>

<p class="sous">Dernière mise à jour : {MAJ_LEGAL}.</p>
'''


COLLECTION_SECTION = '    <section class="collection" id="collection" aria-labelledby="titre-collection">\n      <div class="cote-tete">\n        <h2 id="titre-collection">Ma collection</h2>\n        <p class="compte" id="coll-compte"></p>\n      </div>\n      <div id="coll-corps"></div>\n      <details class="importer" id="importer">\n        <summary>Importer une liste</summary>\n        <div class="importer-corps">\n          <p class="sous">Collez des ISBN (un par ligne ou séparés par des espaces), éventuellement suivis de l\'état (convenable, bon, TBE) et du nombre d\'exemplaires. Vous pouvez aussi charger un fichier exporté d\'ici (JSON ou CSV), ou un simple fichier texte.</p>\n          <label for="imp-texte">Liste d\'ISBN</label>\n          <textarea id="imp-texte" rows="5" placeholder="9782070583805 bon 1&#10;9782075100649 TBE 2"></textarea>\n          <div class="importer-actions">\n            <button type="button" class="bouton" id="imp-go">Ajouter à ma collection</button>\n            <label class="bouton bouton-clair" for="imp-fichier">Charger un fichier</label>\n            <input type="file" id="imp-fichier" accept=".json,.csv,.txt,text/plain,application/json" hidden>\n          </div>\n          <p class="statut" id="imp-statut" role="status" aria-live="polite"></p>\n        </div>\n      </details>\n      <p class="sous prive" id="coll-prive"></p>\n    </section>\n\n'


def barre_collection():
    """Barre du bas de la page collection : « Ma collection » est la page en cours."""
    b = barre("collection.html")
    b = b.replace('<a class="barre-centre" href="collection.html">', '<a class="barre-centre" href="collection.html" aria-current="page">')
    return b.replace('<span>Ma collection</span></a>', '<span>Ma collection</span><b class="nb-coll" id="nb-coll-bas"></b></a>')


def page_collection(index_html):
    """Page « Ma collection » : la section, l'inventaire guidé et la fiche viennent de l'accueil (une seule source)."""
    import re
    dlg = lambda ident: re.search(r'<dialog[^>]*id="%s".*?</dialog>' % ident, index_html, re.S).group(0)
    nav = entete("collection.html").replace('<a href="collection.html">Ma collection</a>', '<a href="collection.html" aria-current="page">Ma collection <span class="nb-coll" id="nb-coll"></span></a>')
    bar = barre_collection()
    return f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ma collection · La Cote du Héros</title>
<meta name="description" content="Composez et suivez votre collection de livres dont vous êtes le héros. Tout reste dans votre navigateur.">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#000000">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="preload" href="fonts/cormorant-garamond.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="fonts/source-sans-3.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="favicon-16.png">
<link rel="stylesheet" href="style.css">
</head>
<body class="annexe page-collection" data-page="collection">
<a class="evitement" href="#main">Aller au contenu</a>

<div class="haut">
{BANDEAU}
{nav}
</div>

<div class="banniere" role="region" aria-labelledby="titre-page">
  <div class="cadre banniere-in">
    <p class="surtitre">Vos livres</p>
    <h1 id="titre-page">Ma collection</h1>
    <p class="chapeau">Vos livres, leur état et leur évolution. Tout reste dans votre navigateur.</p>
  </div>
</div>

<main id="main" class="cadre contenu-collection">
    <section class="ajout-coll" aria-labelledby="titre-ajout">
      <h2 id="titre-ajout">Ajouter un titre à ma collection</h2>
      <p class="ca-invite" id="ca-invite" hidden>Pour enregistrer vos livres, <button type="button" class="bouton-lien" data-compte="connecter">connectez-vous avec Google</button></p>
      <label class="sr-only" for="ca-q">Titre à ajouter à ma collection</label>
      <input type="search" id="ca-q" placeholder="Titre ou ISBN du livre" autocomplete="off" enterkeyhint="search">
      <p class="sous">Choisissez le livre, puis son état : C, BE ou TBE. Retouchez pour le retirer.</p>
      <p class="sr-only" id="ca-statut" role="status" aria-live="polite"></p>
      <p class="ca-ok" id="ca-ok" role="status" hidden></p>
      <ul class="ca-res" id="ca-res"></ul>
    </section>
{COLLECTION_SECTION.replace('<h2 id="titre-collection">Ma collection</h2>', '<h2 id="titre-collection">Estimation</h2>')}</main>

<footer class="pied">
  <div class="cadre pied-in">
    {PIED_LIENS}
    <p class="sous">La Cote du Héros · guide indépendant, sans publicité. Votre collection reste dans votre navigateur : voir <a href="confidentialite.html">Confidentialité</a>.</p>
  </div>
</footer>

{bar}

{feuille("collection.html")}

<div class="sr-only" id="annonce" role="status" aria-live="polite"></div>

{dlg("parcours")}

{dlg("fiche")}

<script src="plus.js"></script>
<script src="installer.js"></script>
<script src="identite.js"></script>
<script src="relais.js"></script>
<script src="cloud.js"></script>
<script src="compte.js"></script>
<script src="notes.js"></script>
<script src="scan.js"></script>
<script src="app.js"></script>
</body>
</html>
'''


def corps_evolutions():
    """Corps de la page « Évolutions des prix », construit à partir de web/data/mouvements.json."""
    import json
    from html import escape as h
    try:
        mv = json.loads((WEB / "data" / "mouvements.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "<p class=\"surtitre\">Suivi des cotes</p>\n<h1>Évolutions des prix</h1>\n<p>Les premières évolutions apparaîtront après la prochaine mise à jour des prix.</p>"
    mois = ("janvier février mars avril mai juin juillet août septembre octobre novembre décembre").split()
    def jour(iso):
        a, m_, j = iso.split("-")
        return f"{int(j)} {mois[int(m_) - 1]} {a}"
    euros = lambda v: f"{v:.2f}".replace(".", ",") + "\u00a0€"
    etat = {"convenable": "C", "bon": "BE", "tres_bon": "TBE"}
    def tableau(liste, vide):
        if not liste:
            return f"<p>{vide}</p>"
        lignes = "".join(
            f'<tr><td class="principal"><a href="./#q={h(str(m["isbn13"] or m["id"]))}">{h(m["titre"])}</a>'
            f'<span class="sous" style="display:block">{h(m["serie"])} · <span class="badge">{h(m["version"])}</span></span></td>'
            f'<td data-label="État">{etat.get(m["etat"], m["etat"])}</td>'
            f'<td class="num" data-label="Avant">{euros(m["avant"])}</td><td class="num" data-label="Après">{euros(m["apres"])}</td>'
            f'<td class="num" data-label="Variation"><strong>{("+" if m["pct"] > 0 else "−")}{abs(m["pct"]):.0%}</strong></td></tr>'
            for m in liste)
        return ('<table class="cartes mouv"><thead><tr><th>Livre</th><th>État</th><th class="num">Avant</th>'
                '<th class="num">Après</th><th class="num">Variation</th></tr></thead><tbody>' + lignes + "</tbody></table>")
    if mv["precedent"]:
        med = mv["mediane_variation"]
        bref = (f'<p>Comparaison de la mise à jour du <strong>{jour(mv["date"])}</strong> avec celle du {jour(mv["precedent"])}.</p>'
                f'<dl class="stats"><div><dt>Prix comparés</dt><dd>{mv["nb_comparees"]}</dd></div>'
                f'<div><dt>Prix modifiés</dt><dd>{mv["nb_modifiees"]}</dd></div>'
                f'<div><dt>Grands mouvements</dt><dd>{mv.get("nb_grands_mouvements", 0)}<small>au moins 10 % et 0,50 €</small></dd></div></dl>'
                + (f'<p class="sous">Variation médiane de l\'ensemble : {("+" if med >= 0 else "−")}{abs(med):.1%}'.replace(".", ",") + ".</p>" if med is not None else ""))
    else:
        bref = "<p>Première mise à jour : la comparaison commencera à la suivante.</p>"
    mo = mv["modele"]
    modele = (f'<p>Le modèle apprend l\'écart entre les cotes d\'archives et les prix actuels. Il se contrôle lui-même : '
              f'il ne s\'active que s\'il prédit mieux que les archives seules. '
              f'<strong>État : {"actif" if mo["actif"] else "inactif"}</strong> ({h(mo["raison"])}).</p>')
    return f'''<p class="surtitre">Suivi des cotes</p>
<h1>Évolutions des prix</h1>
<p class="chapeau">Ce que la cote a changé à la dernière mise à jour. Ces prix sont des prix demandés, pas des prix de vente.</p>
<h2>En bref</h2>
{bref}
<h2>Plus fortes hausses</h2>
{tableau(mv["hausses"], "Aucune hausse importante depuis la mise à jour précédente.")}
<h2>Plus fortes baisses</h2>
{tableau(mv["baisses"], "Aucune baisse importante depuis la mise à jour précédente.")}
<h2>Le modèle d'auto-apprentissage</h2>
{modele}
<h2>Comment lire cette page</h2>
<ul>
  <li>Un prix n'est mis à jour qu'avec au moins 3 annonces récentes (moins de 90 jours) pour l'édition et l'état concernés : une annonce isolée peut être absurde.</li>
  <li>La cote ne saute pas : chaque nouveau relevé corrige le prix précédent d'une part qui dépend du nombre d'annonces et de l'ancienneté.</li>
  <li>Un grand mouvement sur une seule semaine peut être du bruit ; c'est la répétition d'une semaine à l'autre qui compte.</li>
</ul>
<p class="sous">Mise à jour automatique tous les deux jours. Les prix viennent d'annonces publiques et d'un ancien relevé, voir <a href="le-projet.html">Le projet</a>.</p>'''


def main():
    index_html = (WEB / "index.html").read_text(encoding="utf-8")
    (WEB / "collection.html").write_text(variante(page_collection(index_html)), encoding="utf-8")
    print("écrit : collection.html")
    for nom, corps in (("le-projet.html", LE_PROJET), ("confidentialite.html", CONFIDENTIALITE), ("mentions-legales.html", MENTIONS),
                       ("evolutions.html", corps_evolutions()), ("revue-prix.html", _revue_prix()), ("ajouter.html", AJOUTER), ("butin.html", _butin()), ("equipe.html", EQUIPE), ("contact.html", CONTACT), ("communaute.html", corps_communaute())):
        (WEB / nom).write_text(variante(page(nom, corps)), encoding="utf-8")
        print("écrit :", nom)
    n = pages_livres.ecrire(WEB, {"bandeau": BANDEAU, "entete": entete("livre"), "pied": PIED_LIENS, "barre": barre("livre"),
                                  "feuille": feuille("livre"), "variante": variante})
    print("écrit :", n, "pages de livres, livre/index.html, sitemap.xml et robots.txt")


if __name__ == "__main__":
    main()
