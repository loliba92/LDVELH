"""Construit les pages annexes du site (web/le-projet.html, confidentialite.html, mentions-legales.html).

    python pipeline/construire_pages.py

L'en-tête, la barre du bas, la feuille « Plus » et le pied de page sont communs aux trois pages (et recopiés
dans web/index.html, qui reste écrit à la main). Les textes juridiques décrivent ce que le site fait réellement :
voir docs/CONFORMITE.md pour la vérification faite dans le code.
"""
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
MAJ = "11 octobre 2026"
ISSUES = "https://github.com/loliba92/LDVELH/issues"


def ico(d):
    return (f'<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>')


PAGES = {
    "revue-prix.html": ("Revue des prix", "Revue des prix · La Cote du Héros",
                        "Outil de revue : archive, relevé eBay et prix publié, côte à côte, pour valider les cotes."),
    "evolutions.html": ("Évolutions", "Évolutions des prix · La Cote du Héros",
                        "Ce qui a bougé dans la cote : plus fortes hausses et baisses depuis la dernière mise à jour, et état du modèle d'auto-apprentissage."),
    "le-projet.html": ("Le projet", "Le projet · La Cote du Héros",
                       "Pourquoi ce guide existe, d'où viennent ses données, comment les prix sont estimés, et ce qu'il ne fait pas."),
    "confidentialite.html": ("Confidentialité", "Confidentialité · La Cote du Héros",
                             "Ce que La Cote du Héros fait de vos données : rien n'est envoyé, tout reste dans votre navigateur."),
    "coffre.html": ("Accès commun", "Accès commun · La Cote du Héros",
                    "Page d'administration : chiffrer la clé d'envoi avec le mot de passe de la page admin."),
    "mentions-legales.html": ("Mentions légales", "Mentions légales · La Cote du Héros",
                              "Éditeur, hébergeur et conditions d'utilisation de La Cote du Héros."),
}


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
      {lien("le-projet.html", "Le projet", "le-projet.html")}
      <a class="lien-prive" href="revue-prix.html" aria-label="Accès admin : vérifier les prix"{" aria-current=\"page\"" if courante == "revue-prix.html" else ""}><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg><span>Accès admin</span></a>
      <a class="menu-cafe" href="https://buymeacoffee.com/obertrand9s" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 9h11v6a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4Z"/><path d="M16 10.5h1.5a2 2 0 0 1 0 4H16"/><path d="M8.5 4.5c-.6.7-.6 1.3 0 2M12 4.5c-.6.7-.6 1.3 0 2"/></svg><span>Offrir un café</span></a>
    </nav>
  </div>
</header>'''


def barre(courante):
    plus_actif = ' aria-current="page"'
    return f'''<nav class="barre-bas" id="barre-bas" aria-label="Menu du bas">
  <a href="./">{ico('<path d="M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z"/>')}<span>Accueil</span></a>
  <a href="./#recherche">{ico('<path d="M4 20h16M6 20V9l3-1v12M11 20V5h3.5v15M16.5 20V10l2.5 1v9"/>')}<span>L'étagère</span></a>
  <a class="barre-centre" href="./?inventaire" aria-label="Inventaire guidé de ma collection">{ico('<path d="M12 5v14M5 12h14"/>')}<span>Inventaire</span></a>
  <a href="collection.html">{ico('<path d="M5 4.5h10a3 3 0 0 1 3 3V20H8a3 3 0 0 1-3-3zM8 4.5V17"/>')}<span>Ma collection</span></a>
  <button type="button" data-plus aria-haspopup="dialog" aria-expanded="false"{plus_actif}>{ico('<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.8v.2"/>')}<span>Infos</span></button>
</nav>'''


def feuille(courante, racine_a_propos="./#apropos"):
    def e(href, titre, detail, page=None):
        cur = ' aria-current="page"' if page is not None and page == courante else ""
        return f'<li><a href="{href}"{cur}><b>{titre}</b><small>{detail}</small></a></li>'
    return f'''<dialog class="feuille" id="feuille-plus" aria-labelledby="feuille-plus-titre">
  <div class="feuille-poignee" aria-hidden="true"></div>
  <div class="feuille-tete"><h2 id="feuille-plus-titre">Infos et mentions</h2><button type="button" class="fermer feuille-fermer" aria-label="Fermer le menu">×</button></div>
  <ul class="feuille-liste">
    {e("le-projet.html", "Le projet", "Pourquoi ce guide, d'où viennent les prix", "le-projet.html")}
    {e("confidentialite.html", "Confidentialité", "Vos données restent dans votre navigateur", "confidentialite.html")}
    {e("mentions-legales.html", "Mentions légales", "Éditeur, hébergeur, conditions d'utilisation", "mentions-legales.html")}
    {e(racine_a_propos, "À propos de la cote", "Ce qu'est la cote, les éditions V1 à V5")}
    {e("revue-prix.html", "Accès admin", "Réservé aux administrateurs : revue des prix, ajout de livres", "revue-prix.html")}
  </ul>
</dialog>'''


BANDEAU = '<p class="bandeau-chantier" role="note"><strong>Site en construction.</strong> Prix en cours de vérification.</p>'

PIED_LIENS = '''<nav class="pied-liens" aria-label="Informations">
      <a href="evolutions.html">Évolutions des prix</a>
      <a href="le-projet.html">Le projet</a>
      <a href="confidentialite.html">Confidentialité</a>
      <a href="mentions-legales.html">Mentions légales</a>
      <a href="https://buymeacoffee.com/obertrand9s" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 9h11v6a4 4 0 0 1-4 4H9a4 4 0 0 1-4-4Z"/><path d="M16 10.5h1.5a2 2 0 0 1 0 4H16"/><path d="M8.5 4.5c-.6.7-.6 1.3 0 2M12 4.5c-.6.7-.6 1.3 0 2"/></svg>Offrir un café</a>
      <a class="lien-prive" href="revue-prix.html"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>Accès admin</a>
    </nav>'''


def page(nom, corps):
    court, titre, desc = PAGES[nom]
    noindex = '\n<meta name="robots" content="noindex">' if nom in ("mentions-legales.html", "revue-prix.html", "coffre.html") else ""
    return f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titre}</title>
<meta name="description" content="{desc}">{noindex}
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

{PORTE if nom == "revue-prix.html" else ""}<main id="main" class="cadre page"{" hidden" if nom == "revue-prix.html" else ""}>
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
<script src="pages.js"></script>{SCRIPT_PAGE.get(nom, "")}
</body>
</html>
'''


SCRIPT_PAGE = {"revue-prix.html": '\n<script src="coffre.js"></script>\n<script src="acces.js"></script>\n<script src="revue.js"></script>',
               "coffre.html": '\n<script src="coffre.js"></script>'}
PORTE = '''<div class="porte" id="porte">
  <div class="porte-boite">
    <p class="porte-etiquette"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg> Accès admin</p>
    <form id="porte-form">
      <label class="sr-only" for="porte-code">Code d'accès</label>
      <input id="porte-code" type="password" placeholder="Code d'accès" autocomplete="off" autofocus>
      <button type="submit" class="bouton">Entrer</button>
    </form>
    <p class="porte-erreur" id="porte-erreur" role="alert" hidden>Code incorrect.</p>
  </div>
</div>
'''


COFFRE = '''<h1>Accès commun <span class="badge-admin" title="Réservé aux administrateurs">Admin</span></h1>
<p class="chapeau">Un seul mot de passe pour toutes les personnes de confiance : il ouvre la page de revue des prix <strong>et</strong> enregistre sur leur appareil la clé qui permet d'envoyer les prix en un clic.</p>
<section class="rv-ajout" aria-labelledby="cf-titre">
  <h2 id="cf-titre">Préparer le coffre</h2>
  <ol>
    <li>Choisissez un mot de passe long, ou demandez-en un solide.</li>
    <li>Collez la clé d'envoi.</li>
    <li>Le site la chiffre avec ce mot de passe, <strong>dans votre navigateur</strong> : ni la clé ni le mot de passe ne sont envoyés ailleurs, et rien n'est enregistré sur cette page.</li>
    <li>Transmettez le texte obtenu pour qu'il soit publié. Il est inutilisable sans le mot de passe.</li>
  </ol>
  <form id="cf-form">
    <label for="cf-mdp"><strong>Mot de passe commun</strong> (14 caractères au minimum)</label>
    <input id="cf-mdp" class="cf-champ" type="password" autocomplete="new-password" spellcheck="false">
    <p><button type="button" class="bouton-lien" id="cf-proposer">Proposer un mot de passe solide</button></p>
    <label for="cf-jeton"><strong>Clé d'envoi</strong></label>
    <input id="cf-jeton" class="cf-champ" type="password" autocomplete="off" spellcheck="false">
    <div class="rv-ajout-actions"><button type="submit" class="bouton">Chiffrer</button></div>
  </form>
  <p class="rv-ajout-bilan" id="cf-etat" role="status"></p>
  <label class="sr-only" for="cf-sortie">Texte chiffré</label>
  <textarea id="cf-sortie" readonly hidden rows="6"></textarea>
  <div class="rv-ajout-actions"><button type="button" class="bouton" id="cf-copier" hidden>Copier le texte chiffré</button></div>
</section>
<section class="rv-ajout" aria-labelledby="cf-bon">
  <h2 id="cf-bon">À savoir</h2>
  <ul>
    <li>Le texte chiffré est public : seul un mot de passe long et aléatoire résiste aux essais automatiques. Évitez les mots courants et les suites de touches.</li>
    <li>Toute personne qui connaît le mot de passe peut envoyer des prix en votre nom.</li>
    <li>En cas de souci, générez une nouvelle clé, refaites cette page avec un nouveau mot de passe, puis communiquez-le : chaque appareil redemande alors le mot de passe.</li>
  </ul>
  <p><a href="revue-prix.html">Retour à la revue des prix</a></p>
</section>
'''


REVUE = '''<h1>Vérifier les prix <span class="badge-admin" title="Réservé aux administrateurs">Admin</span></h1>
<p class="sous admin-note">Page réservée aux administrateurs : tout ce qui s'y trouve sert à gérer les cotes et le catalogue.</p>
<p class="chapeau">Un livre par ligne, avec ses trois prix tels qu'ils sont affichés sur le site. Quand un prix a changé, l'ancien est barré. Les prix qui ont beaucoup bougé sont marqués « À vérifier ». Pour chaque prix, <strong>Confirmer</strong> le garde tel quel, <strong>Corriger</strong> en fixe un autre : votre prix prime ensuite sur eBay et sur les archives.</p>
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
<section class="rv-ajout" aria-labelledby="aj-titre">
  <h2 id="aj-titre">Ajouter des livres <span class="badge-admin" title="Réservé aux administrateurs">Admin</span></h2>
  <p>Collez un ou plusieurs ISBN, un par ligne (les tirets sont acceptés). Pour un livre qu'aucun catalogue ne connaît, ajoutez après l'ISBN la série, le numéro et le titre, séparés par un point-virgule :</p>
  <p><code class="aj-exemple">9791097577025 ; Fabled Lands ; 1 ; Le Royaume déchiré</code></p>
  <label class="sr-only" for="aj-texte">Liste d'ISBN</label>
  <textarea id="aj-texte" rows="6" spellcheck="false" autocomplete="off" placeholder="9791097577025&#10;2-07-033370-1&#10;9782070583805 ; Destins ; 731 ; Le Pirate des Sept Mers"></textarea>
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
<div class="rv-onglets" id="rv-onglets" role="group" aria-label="Quels livres voir ?">
  <button type="button" data-vue="verif" aria-pressed="true">À vérifier <span class="nb-onglet" id="rv-n-verif"></span></button>
  <button type="button" data-vue="change" aria-pressed="false">Tout ce qui a changé <span class="nb-onglet" id="rv-n-change"></span></button>
  <button type="button" data-vue="valide" aria-pressed="false">Validés par vous <span class="nb-onglet" id="rv-n-valide"></span></button>
  <button type="button" data-vue="tous" aria-pressed="false">Tous les livres <span class="nb-onglet" id="rv-n-tous"></span></button>
</div>
<div class="rv-envoi" id="rv-envoi" hidden>
  <p><strong><span id="rv-n-attente"></span> validation(s) à transmettre.</strong> Elles sont gardées dans ce navigateur. Avec le jeton enregistré plus haut, « Envoyer » les enregistre pour tous en un clic ; sans jeton, téléchargez le fichier et envoyez-le moi.</p>
  <button type="button" class="bouton" id="rv-envoyer">Télécharger mes validations</button>
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
<h2>Comment lire cette page</h2>
<ul>
  <li><strong>Le gros prix</strong> est celui affiché sur le site. <strong>Le prix barré</strong> est l'ancienne cote (ancien relevé de 2024). Le pourcentage montre le changement.</li>
  <li><strong>« À vérifier »</strong> : le prix a au moins doublé ou a été divisé par près de deux. Une raison est écrite en dessous.</li>
  <li>La ligne grise sous chaque prix dit d'où il vient : « d'après N annonces eBay » (prix actuel), « ancienne cote » (pas de relevé récent), « déduit des autres états » (état sans prix, estimé à partir des autres), « ajusté » (remonté ou ramené pour que convenable ≤ bon état ≤ très bon état).</li>
  <li><strong>Confirmer / Corriger</strong> : votre prix remplace celui du site, y compris aux prochains relevés. « Retirer » annule une validation pas encore transmise.</li>
  <li>Cliquez sur le titre d'un livre pour ouvrir sa fiche sur le site.</li>
</ul><details class="rv-appareil" id="rv-reglages">
  <summary>Cet appareil</summary>
  <p class="rv-ajout-bilan" id="rg-etat" role="status"></p>
  <div class="rv-ajout-actions"><button type="button" class="bouton-lien" id="rg-retirer">Retirer la clé de cet appareil</button></div>
  <p class="sous">Utiliser une autre clé :</p>
  <label class="sr-only" for="rg-jeton">Clé d'envoi</label>
  <input id="rg-jeton" type="password" autocomplete="off" spellcheck="false" placeholder="Collez la clé d'envoi ici">
  <div class="rv-ajout-actions"><button type="button" class="bouton" id="rg-enregistrer">Enregistrer la clé</button></div>
  <p class="sous"><a href="coffre.html">Préparer l'accès commun</a> (un seul mot de passe pour toutes les personnes de confiance).</p>
</details>
'''


LE_PROJET = f'''<p class="surtitre">À propos du guide</p>
<h1>Le projet</h1>
<p class="chapeau">La Cote du Héros est un guide indépendant, gratuit et sans publicité. Il aide à estimer la valeur des livres dont vous êtes le héros, pour suivre une collection et la compléter.</p>

<h2>À quoi sert ce site</h2>
<p>C'est une <strong>application pour tenir à jour et gérer sa collection</strong>, faite pour les collectionneurs et pas pour les traders (c'est dit avec le sourire, mais c'est sérieux). Ce n'est pas un instrument pour acheter et vendre au bon moment : aucune cote ne vous dit « achetez » ou « vendez ».</p>
<p>Elle sert d'abord à <strong>garder un œil sur votre collection</strong> : ce qu'elle contient, les titres et les éditions qu'il vous manque, et ce qu'elle vaut à peu près. Elle sert ensuite à <strong>progresser</strong> : voir ce qu'il reste à trouver pour finir une série, et ce que cela peut coûter, afin d'avancer à votre rythme sans mauvaise surprise sur le budget.</p>
<p>Les prix sont des repères financiers et économiques, pas des promesses. Une cote donne un ordre de grandeur ; ce qui compte, c'est le plaisir de compléter sa collection.</p>

<h2>Pourquoi ce guide</h2>
<p>Les livres-jeux ont paru en plusieurs éditions, chez plusieurs éditeurs, pendant près de quarante ans. Un même titre peut valoir quelques euros dans une édition et plusieurs dizaines dans une autre. Trouver le bon prix, c'est d'abord savoir de quelle édition on parle. Ce guide réunit toutes les éditions au même endroit, pour les comparer et pour estimer une collection entière.</p>

<h2>Ce que vous y trouvez</h2>
<ul>
  <li>Plus de 400 éditions, rattachées à plus de 200 livres et à 24 séries, avec leur jaquette et leur fiche (éditeur, année, pages, auteurs).</li>
  <li>Pour chaque édition, une cote par état : convenable, bon état, très bon état (TBE).</li>
  <li>Des moyennes, médianes et répartitions des prix pour toute sélection : une série, une époque, un éditeur.</li>
  <li>Un inventaire guidé, pour estimer le patrimoine d'une collection sans tout saisir à la main.</li>
</ul>

<h2>Comment les prix sont estimés</h2>
<p><strong>Une cote est une estimation, jamais un prix fixé.</strong> Elle donne un ordre de grandeur, pas la somme qu'on obtiendra.</p>
<ol>
  <li><strong>Aujourd'hui, ce sont des cotes d'archives.</strong> Les prix viennent d'un ancien relevé, qui n'est plus tenu à jour. Le guide le signale à l'accueil et sur chaque fiche d'édition.</li>
  <li><strong>Des prix actuels sont en préparation.</strong> Ils viendront de ventes et d'achats réellement constatés, puis d'annonces en ligne lues par les interfaces officielles des plateformes, sous réserve de leurs conditions d'utilisation. De ces annonces, on ne garde que des chiffres d'ensemble (nombre, minimum, médiane, maximum) : ni titre d'annonce, ni vendeur.</li>
  <li><strong>La méthode est une médiane pondérée.</strong> Une vente réelle compte plus qu'une annonce, qui compte plus qu'une archive. Un prix récent compte plus qu'un prix ancien : le poids d'une observation est divisé par deux tous les 90 jours. Une annonce reste un prix demandé, pas un prix payé : le guide ne la corrige pas et le signale.</li>
</ol>
<p>Dès qu'une cote repose sur des prix actuels, la fiche de l'édition indique leur nature, leur nombre, leur date et un niveau de confiance.</p>

<h2>D'où viennent les données</h2>
<ul>
  <li><strong>Catalogue et fiches</strong> : notices du catalogue général de la Bibliothèque nationale de France, complétées à partir de l'ancien relevé.</li>
  <li><strong>Jaquettes</strong> : © leurs éditeurs, reproduites à titre d'illustration.</li>
  <li><strong>Polices</strong> : Cormorant Garamond et Source Sans 3, sous licence SIL Open Font 1.1, hébergées avec le site.</li>
</ul>

<h2>Ce que le guide ne fait pas</h2>
<p>Il ne vend rien et ne contient ni publicité ni lien d'affiliation : les boutons Vinted, Leboncoin et eBay des fiches ouvrent de simples recherches sur ces sites, sans rien rapporter au guide. Il ne demande aucun compte et ne mesure pas votre visite. Il ne recopie pas les sites d'annonces ou de comparaison de prix qui interdisent la collecte automatique de leurs pages : cette interdiction est respectée.</p>

<h2>Votre collection reste chez vous</h2>
<p>La collection que vous composez est enregistrée dans votre navigateur, sur votre appareil. Rien n'est envoyé à un serveur. Les détails sont dans la page <a href="confidentialite.html">Confidentialité</a>.</p>

<h2>Signaler une erreur, proposer un prix</h2>
<p>Une édition manquante, une fiche erronée, un prix que vous avez constaté : écrivez-le dans un <a href="{ISSUES}" target="_blank" rel="noopener">signalement sur GitHub</a> (un compte GitHub est nécessaire).</p>

<h2>Soutenir le guide</h2>
<p>Le guide reste gratuit et sans publicité. S'il vous est utile, vous pouvez <a href="https://buymeacoffee.com/obertrand9s" target="_blank" rel="noopener noreferrer">offrir un café</a> : cela aide à couvrir les frais du site, notamment son adresse web. C'est libre et sans aucune obligation.</p>
'''

CONFIDENTIALITE = f'''<p class="surtitre">Vos données</p>
<h1>Confidentialité</h1>
<p class="chapeau">En bref : <strong>La Cote du Héros ne collecte aucune donnée personnelle.</strong> Pas de compte, pas de formulaire, pas de cookie, pas de mesure d'audience, pas de publicité. Votre collection reste dans votre navigateur.</p>

<h2>Ce qui est enregistré sur votre appareil</h2>
<p>Pour fonctionner comme vous le demandez, le guide écrit deux enregistrements dans le stockage local de votre navigateur. Ces données ne quittent jamais votre appareil et l'éditeur n'y a pas accès.</p>
<div class="tableau-page">
<table>
  <thead><tr><th scope="col">Nom</th><th scope="col">Contenu</th><th scope="col">Pourquoi</th></tr></thead>
  <tbody>
    <tr><td data-label="Nom"><code>cote-collection-v1</code></td><td data-label="Contenu">Les livres de « Ma collection », leur état, leur quantité</td><td data-label="Pourquoi">Conserver votre collection d'une visite à l'autre</td></tr>
    <tr><td data-label="Nom"><code>cote-parcours-v1</code></td><td data-label="Contenu">L'avancement de l'inventaire guidé</td><td data-label="Pourquoi">Reprendre là où vous en étiez</td></tr>
  </tbody>
</table>
</div>
<p>Le guide garde aussi des copies de ses propres pages et images dans la mémoire de votre navigateur (cache), pour s'ouvrir sans réseau. Elles ne contiennent aucune donnée sur vous.</p>
<p><strong>Aucun cookie</strong> n'est déposé. Ces enregistrements sont nécessaires à des fonctions que vous demandez vous-même ; ils ne demandent donc pas de consentement et il n'y a pas de bandeau.</p>

<h2>Comment les effacer</h2>
<ul>
  <li>Votre collection : bouton « Tout effacer » dans la section Ma collection, ou « Repartir de zéro » dans l'inventaire guidé.</li>
  <li>Tout le reste : effacez les données du site dans les réglages de votre navigateur.</li>
</ul>

<h2>Fichiers de sauvegarde</h2>
<p>Le fichier que vous téléchargez (JSON ou CSV) est créé dans votre navigateur et enregistré chez vous. Quand vous chargez un fichier pour le retrouver, il est lu dans votre navigateur, sans être envoyé nulle part. Vous en restez seul responsable : il contient la liste de vos livres.</p>

<h2>Hébergement et journaux techniques</h2>
<p>Le site est hébergé par GitHub Pages (voir les <a href="mentions-legales.html">mentions légales</a>). Comme tout hébergeur, GitHub peut enregistrer des informations techniques lors d'une visite, comme l'adresse IP et le type de navigateur, pour assurer le service et sa sécurité. Ces journaux relèvent de l'hébergeur et non de l'éditeur, qui n'y a pas accès. GitHub est établi aux États-Unis ; son traitement des données est décrit dans sa <a href="https://docs.github.com/fr/site-policy/privacy-policies/github-general-privacy-statement" target="_blank" rel="noopener">déclaration de confidentialité</a>.</p>

<h2>Ressources et liens externes</h2>
<p>Les polices, les images, les jaquettes et les données sont hébergées avec le site : le guide n'appelle aucun service extérieur pour s'afficher. Seuls les liens sur lesquels vous cliquez vous emmènent ailleurs (notice de la BnF, recherches sur Vinted, Leboncoin ou eBay, GitHub). Ces sites ont leurs propres règles de confidentialité.</p>

<h2>Vos droits</h2>
<p>Comme le guide ne détient aucune donnée sur vous, il n'y a rien à consulter, corriger ou effacer chez l'éditeur. Pour toute question, ou si vous pensez qu'une donnée vous concernant est traitée à tort, écrivez par un <a href="{ISSUES}" target="_blank" rel="noopener">signalement sur GitHub</a>. Vous pouvez aussi saisir la CNIL (<a href="https://www.cnil.fr/fr/plaintes" target="_blank" rel="noopener">cnil.fr/fr/plaintes</a>).</p>

<h2>Si cela change</h2>
<p>Si le guide devait un jour mesurer sa fréquentation, proposer des dons ou ouvrir des comptes, cette page serait mise à jour avant, et un consentement serait demandé quand la loi l'exige. Dernière mise à jour : {MAJ}.</p>
'''

MENTIONS = f'''<p class="surtitre">Informations légales</p>
<h1>Mentions légales</h1>
<p class="encart-a-completer" role="note"><strong>Page à compléter.</strong> Les informations entre crochets doivent être renseignées par l'éditeur avant toute publicité de cette page.</p>

<h2>Éditeur du site</h2>
<p>La Cote du Héros est un site personnel, non commercial.</p>
<ul>
  <li><strong>Éditeur et directeur de la publication</strong> : [À COMPLÉTER : nom et prénom, ou pseudonyme si l'hébergeur détient vos coordonnées]</li>
  <li><strong>Contact</strong> : par <a href="{ISSUES}" target="_blank" rel="noopener">signalement sur GitHub</a> ; adresse électronique : [À COMPLÉTER]</li>
</ul>

<h2>Hébergeur</h2>
<ul>
  <li><strong>GitHub, Inc.</strong> (service GitHub Pages)</li>
  <li>Adresse : 88 Colin P. Kelly Jr. Street, San Francisco, CA 94107, États-Unis [À VÉRIFIER]</li>
  <li>Téléphone : [À COMPLÉTER ou à vérifier auprès de l'hébergeur]</li>
  <li>Site : <a href="https://pages.github.com" target="_blank" rel="noopener">pages.github.com</a></li>
</ul>

<h2>Propriété intellectuelle</h2>
<ul>
  <li><strong>Textes, calculs et code du guide</strong> : © [À COMPLÉTER : titulaire des droits].</li>
  <li><strong>Jaquettes</strong> : © leurs éditeurs, reproduites à titre d'illustration d'un guide non commercial. Un ayant droit qui souhaiterait le retrait d'une image peut le demander par le contact ci-dessus.</li>
  <li><strong>Données bibliographiques</strong> : catalogue général de la Bibliothèque nationale de France.</li>
  <li><strong>Illustration de l'accueil</strong> : [À COMPLÉTER : auteur ou source de l'illustration, et conditions d'utilisation]</li>
  <li><strong>Polices</strong> : Cormorant Garamond (© The Cormorant Project Authors) et Source Sans 3 (© Adobe), licence SIL Open Font 1.1.</li>
</ul>

<h2>Responsabilité</h2>
<p>Les cotes sont des estimations indicatives, établies à partir de données d'archives et d'observations partielles. Elles n'ont aucune valeur contractuelle, ne remplacent ni une expertise ni un prix de vente réel, et l'éditeur ne garantit ni leur exactitude ni leur actualité. Chaque cote indique sa nature et son ancienneté. Les liens vers des sites extérieurs n'engagent pas leurs éditeurs ni celui de ce guide.</p>

<h2>Données personnelles et cookies</h2>
<p>Le site ne collecte aucune donnée personnelle et ne dépose aucun cookie. Voir la page <a href="confidentialite.html">Confidentialité</a>.</p>

<h2>Droit applicable</h2>
<p>Le site est soumis au droit français. Il ne propose ni vente ni service payant : aucune médiation de la consommation n'est donc applicable.</p>

<p class="sous">Dernière mise à jour : {MAJ}.</p>
'''


COLLECTION_SECTION = '    <section class="collection" id="collection" aria-labelledby="titre-collection">\n      <div class="cote-tete">\n        <h2 id="titre-collection">Ma collection</h2>\n        <p class="compte" id="coll-compte"></p>\n      </div>\n      <div id="coll-corps"></div>\n      <details class="importer" id="importer">\n        <summary>Importer une liste</summary>\n        <div class="importer-corps">\n          <p class="sous">Collez des ISBN (un par ligne ou séparés par des espaces), éventuellement suivis de l\'état (convenable, bon, TBE) et du nombre d\'exemplaires. Vous pouvez aussi charger un fichier exporté d\'ici (JSON ou CSV), ou un simple fichier texte.</p>\n          <label for="imp-texte">Liste d\'ISBN</label>\n          <textarea id="imp-texte" rows="5" placeholder="9782070583805 bon 1&#10;9782075100649 TBE 2"></textarea>\n          <div class="importer-actions">\n            <button type="button" class="bouton" id="imp-go">Ajouter à ma collection</button>\n            <label class="bouton bouton-clair" for="imp-fichier">Charger un fichier</label>\n            <input type="file" id="imp-fichier" accept=".json,.csv,.txt,text/plain,application/json" hidden>\n          </div>\n          <p class="statut" id="imp-statut" role="status" aria-live="polite"></p>\n        </div>\n      </details>\n      <details class="importer" id="partager">\n        <summary>Transférer sur un autre appareil</summary>\n        <div class="importer-corps">\n          <p class="sous">Créez un lien qui contient votre collection, puis ouvrez-le sur l\'autre appareil. Rien n\'est stocké sur un serveur : la collection voyage dans l\'adresse elle-même. Ne partagez ce lien qu\'avec les personnes de votre choix.</p>\n          <div class="importer-actions">\n            <button type="button" class="bouton" id="partage-go">Créer mon lien</button>\n            <button type="button" class="bouton bouton-clair" id="partage-copier" hidden>Copier le lien</button>\n          </div>\n          <label for="partage-lien" class="sr-only">Lien de transfert</label>\n          <input type="text" id="partage-lien" readonly hidden>\n          <p class="statut" id="partage-statut" role="status" aria-live="polite"></p>\n        </div>\n      </details>\n      <p class="sous prive" id="coll-prive"></p>\n    </section>\n\n'


def barre_collection():
    """Barre du bas de la page collection : l'inventaire ouvre sa fenêtre sur place, « Ma collection » est la page en cours."""
    b = barre("collection.html")
    b = b.replace('<a class="barre-centre" href="./?inventaire" aria-label="Inventaire guidé de ma collection">',
                  '<button type="button" class="barre-centre" data-parcours aria-label="Inventaire guidé de ma collection">')
    b = b.replace('<span>Inventaire</span></a>', '<span>Inventaire</span></button>')
    b = b.replace('<a href="collection.html">', '<a href="collection.html" aria-current="page">')
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
<meta name="description" content="Composez votre collection de livres dont vous êtes le héros et estimez sa valeur. Tout reste dans votre navigateur.">
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

<header class="banniere" aria-labelledby="titre-page">
  <div class="cadre banniere-in">
    <p class="surtitre">Mon inventaire</p>
    <h1 id="titre-page">Ma collection</h1>
    <p class="chapeau">Vos livres, leur état et leur valeur estimée. Tout reste dans votre navigateur.</p>
  </div>
</header>

<main id="main" class="cadre contenu-collection">
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
        return "<h1>Évolutions des prix</h1>\n<p>Les premières évolutions apparaîtront après la prochaine mise à jour des prix.</p>"
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
    modele = (f'<p>Le modèle apprend l\'écart entre les cotes d\'archives et les prix actuels, et se contrôle lui-même : '
              f'il ne s\'active que s\'il prédit mieux que les archives seules. '
              f'<strong>État : {"actif" if mo["actif"] else "inactif"}</strong> ({h(mo["raison"])}).</p>')
    return f'''<h1>Évolutions des prix</h1>
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
<p class="sous">Mise à jour automatique chaque semaine. Les prix viennent d'annonces publiques et d'un ancien relevé, voir <a href="le-projet.html">Le projet</a>.</p>'''


def main():
    index_html = (WEB / "index.html").read_text(encoding="utf-8")
    (WEB / "collection.html").write_text(page_collection(index_html), encoding="utf-8")
    print("écrit : collection.html")
    for nom, corps in (("le-projet.html", LE_PROJET), ("confidentialite.html", CONFIDENTIALITE), ("mentions-legales.html", MENTIONS),
                       ("evolutions.html", corps_evolutions()), ("revue-prix.html", REVUE), ("coffre.html", COFFRE)):
        (WEB / nom).write_text(page(nom, corps), encoding="utf-8")
        print("écrit :", nom)


if __name__ == "__main__":
    main()
