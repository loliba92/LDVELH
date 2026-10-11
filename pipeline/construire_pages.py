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
    "le-projet.html": ("Le projet", "Le projet · La Cote du Héros",
                       "Pourquoi ce guide existe, d'où viennent ses données, comment les prix sont estimés, et ce qu'il ne fait pas."),
    "confidentialite.html": ("Confidentialité", "Confidentialité · La Cote du Héros",
                             "Ce que La Cote du Héros fait de vos données : rien n'est envoyé, tout reste dans votre navigateur."),
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
      <a href="./#cote">La cote</a>
      <a href="collection.html">Ma collection</a>
      <a href="./#etagere">L'étagère</a>
      {lien("le-projet.html", "Le projet", "le-projet.html")}
      <button type="button" class="lampe" id="lampe" aria-pressed="false" title="Changer l'éclairage">
        <span class="lampe-ico" aria-hidden="true"></span><span class="lampe-txt">Éclairage</span>
      </button>
    </nav>
  </div>
</header>'''


def barre(courante):
    plus_actif = ' aria-current="page"'
    return f'''<nav class="barre-bas" id="barre-bas" aria-label="Menu du bas">
  <a href="./#cote">{ico('<path d="M5 20V11M12 20V5M19 20v-7"/>')}<span>La cote</span></a>
  <a href="./#etagere">{ico('<path d="M4 20h16M6 20V9l3-1v12M11 20V5h3.5v15M16.5 20V10l2.5 1v9"/>')}<span>L'étagère</span></a>
  <a class="barre-centre" href="./?inventaire" aria-label="Inventaire guidé de ma collection">{ico('<path d="M12 5v14M5 12h14"/>')}<span>Inventaire</span></a>
  <a href="collection.html">{ico('<path d="M5 4.5h10a3 3 0 0 1 3 3V20H8a3 3 0 0 1-3-3zM8 4.5V17"/>')}<span>Ma collection</span></a>
  <button type="button" data-plus aria-haspopup="dialog" aria-expanded="false"{plus_actif}>{ico('<circle cx="6" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="18" cy="12" r="1.2"/>')}<span>Plus</span></button>
</nav>'''


def feuille(courante, racine_a_propos="./#apropos"):
    def e(href, titre, detail, page=None):
        cur = ' aria-current="page"' if page is not None and page == courante else ""
        return f'<li><a href="{href}"{cur}><b>{titre}</b><small>{detail}</small></a></li>'
    return f'''<dialog class="feuille" id="plus" aria-labelledby="plus-titre">
  <div class="feuille-poignee" aria-hidden="true"></div>
  <div class="feuille-tete"><h2 id="plus-titre">Plus</h2><button type="button" class="fermer feuille-fermer" aria-label="Fermer le menu">×</button></div>
  <ul class="feuille-liste">
    {e("le-projet.html", "Le projet", "Pourquoi ce guide, d'où viennent les prix", "le-projet.html")}
    {e(racine_a_propos, "À propos de la cote", "Ce qu'est la cote, les éditions V1 à V5")}
    {e("confidentialite.html", "Confidentialité", "Vos données restent dans votre navigateur", "confidentialite.html")}
    {e("mentions-legales.html", "Mentions légales", "Éditeur, hébergeur, conditions d'utilisation", "mentions-legales.html")}
  </ul>
</dialog>'''


BANDEAU = '<p class="bandeau-chantier" role="note"><strong>Site en construction.</strong> Les prix sont en cours d\'ajustement et de vérification.</p>'

PIED_LIENS = '''<nav class="pied-liens" aria-label="Informations">
      <a href="le-projet.html">Le projet</a>
      <a href="confidentialite.html">Confidentialité</a>
      <a href="mentions-legales.html">Mentions légales</a>
    </nav>'''


def page(nom, corps):
    court, titre, desc = PAGES[nom]
    noindex = '\n<meta name="robots" content="noindex">' if nom == "mentions-legales.html" else ""
    return f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titre}</title>
<meta name="description" content="{desc}">{noindex}
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#2a1c13">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="preload" href="fonts/cormorant-garamond.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="fonts/source-sans-3.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="favicon-16.png">
<link rel="stylesheet" href="style.css">
<script>
  try {{ var t = localStorage.getItem('cote-theme'); if (t) document.documentElement.dataset.theme = t; }} catch (e) {{}}
</script>
</head>
<body class="annexe">
<a class="evitement" href="#main">Aller au contenu</a>

{BANDEAU}

{entete(nom)}

<main id="main" class="cadre page">
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
<script src="pages.js"></script>
</body>
</html>
'''


LE_PROJET = f'''<p class="surtitre">À propos du guide</p>
<h1>Le projet</h1>
<p class="chapeau">La Cote du Héros est un guide indépendant, gratuit et sans publicité. Il aide à estimer la valeur des livres dont vous êtes le héros, quand on les achète, les vend ou les range sur une étagère.</p>

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
<p>Il ne vend rien et ne contient ni publicité ni lien d'affiliation. Il ne demande aucun compte et ne mesure pas votre visite. Il ne recopie pas les sites d'annonces ou de comparaison de prix qui interdisent la collecte automatique de leurs pages : cette interdiction est respectée.</p>

<h2>Votre collection reste chez vous</h2>
<p>La collection que vous composez est enregistrée dans votre navigateur, sur votre appareil. Rien n'est envoyé à un serveur. Les détails sont dans la page <a href="confidentialite.html">Confidentialité</a>.</p>

<h2>Signaler une erreur, proposer un prix</h2>
<p>Une édition manquante, une fiche erronée, un prix que vous avez constaté : écrivez-le dans un <a href="{ISSUES}" target="_blank" rel="noopener">signalement sur GitHub</a> (un compte GitHub est nécessaire). Le code du guide est public sur le même dépôt.</p>
'''

CONFIDENTIALITE = f'''<p class="surtitre">Vos données</p>
<h1>Confidentialité</h1>
<p class="chapeau">En bref : <strong>La Cote du Héros ne collecte aucune donnée personnelle.</strong> Pas de compte, pas de formulaire, pas de cookie, pas de mesure d'audience, pas de publicité. Votre collection reste dans votre navigateur.</p>

<h2>Ce qui est enregistré sur votre appareil</h2>
<p>Pour fonctionner comme vous le demandez, le guide écrit trois réglages dans le stockage local de votre navigateur. Ces données ne quittent jamais votre appareil et l'éditeur n'y a pas accès.</p>
<div class="tableau-page">
<table>
  <thead><tr><th scope="col">Nom</th><th scope="col">Contenu</th><th scope="col">Pourquoi</th></tr></thead>
  <tbody>
    <tr><td data-label="Nom"><code>cote-theme</code></td><td data-label="Contenu">Votre choix d'éclairage (clair ou sombre)</td><td data-label="Pourquoi">Retrouver l'éclairage choisi</td></tr>
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
<p>Les polices, les images, les jaquettes et les données sont hébergées avec le site : le guide n'appelle aucun service extérieur pour s'afficher. Seuls les liens sur lesquels vous cliquez vous emmènent ailleurs (notice de la BnF, GitHub). Ces sites ont leurs propres règles de confidentialité.</p>

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
  <li><strong>Textes, calculs et code du guide</strong> : © [À COMPLÉTER : titulaire des droits]. Le code est consultable sur <a href="https://github.com/loliba92/LDVELH" target="_blank" rel="noopener">le dépôt public</a>.</li>
  <li><strong>Jaquettes</strong> : © leurs éditeurs, reproduites à titre d'illustration d'un guide gratuit et non commercial. Un ayant droit qui souhaiterait le retrait d'une image peut le demander par le contact ci-dessus.</li>
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


COLLECTION_SECTION = '    <section class="collection" id="collection" aria-labelledby="titre-collection">\n      <div class="cote-tete">\n        <h2 id="titre-collection">Ma collection</h2>\n        <p class="compte" id="coll-compte"></p>\n      </div>\n      <div id="coll-corps"></div>\n      <details class="importer" id="importer">\n        <summary>Importer une liste</summary>\n        <div class="importer-corps">\n          <p class="sous">Collez des ISBN (un par ligne ou séparés par des espaces), éventuellement suivis de l\'état (convenable, bon, TBE) et du nombre d\'exemplaires. Vous pouvez aussi charger un fichier exporté d\'ici (JSON ou CSV), ou un simple fichier texte.</p>\n          <label for="imp-texte">Liste d\'ISBN</label>\n          <textarea id="imp-texte" rows="5" placeholder="9782070583805 bon 1&#10;9782075100649 TBE 2"></textarea>\n          <div class="importer-actions">\n            <button type="button" class="bouton" id="imp-go">Ajouter à ma collection</button>\n            <label class="bouton bouton-clair" for="imp-fichier">Charger un fichier</label>\n            <input type="file" id="imp-fichier" accept=".json,.csv,.txt,text/plain,application/json" hidden>\n          </div>\n          <p class="statut" id="imp-statut" role="status" aria-live="polite"></p>\n        </div>\n      </details>\n      <p class="sous prive" id="coll-prive"></p>\n    </section>\n\n'


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
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#2a1c13">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="preload" href="fonts/cormorant-garamond.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="fonts/source-sans-3.woff2" as="font" type="font/woff2" crossorigin>
<link rel="icon" href="favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="favicon-16.png">
<link rel="stylesheet" href="style.css">
<script>
  try {{ var t = localStorage.getItem('cote-theme'); if (t) document.documentElement.dataset.theme = t; }} catch (e) {{}}
</script>
</head>
<body class="annexe page-collection" data-page="collection">
<a class="evitement" href="#main">Aller au contenu</a>

{BANDEAU}

{nav}

<main id="main" class="cadre contenu-collection">
{COLLECTION_SECTION.replace('<h2 id="titre-collection">Ma collection</h2>', '<h1 id="titre-collection">Ma collection</h1>')}</main>

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
<script src="app.js"></script>
</body>
</html>
'''


def main():
    index_html = (WEB / "index.html").read_text(encoding="utf-8")
    (WEB / "collection.html").write_text(page_collection(index_html), encoding="utf-8")
    print("écrit : collection.html")
    for nom, corps in (("le-projet.html", LE_PROJET), ("confidentialite.html", CONFIDENTIALITE), ("mentions-legales.html", MENTIONS)):
        (WEB / nom).write_text(page(nom, corps), encoding="utf-8")
        print("écrit :", nom)


if __name__ == "__main__":
    main()
