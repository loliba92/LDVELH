# Design : « La Cote du Héros » (`web/`)

Spécification établie avec les compétences `aesthetic-literacy` et `aesthetic-application`.

**Esthétique appliquée : Dark Academia, en mode « citation nostalgique »**, avec un seul emprunt à Storybook Gothic : le sceau (médaillon) qui porte la cote.
- *Pourquoi* : un guide de cote est un objet de bibliophile (catalogue, fichier de bibliothèque) ; le public est nostalgique des lectures des années 80 et 90. L'ambiance habille, elle ne gêne pas la lecture des prix.
- *Conflit résolu* (palette) : Dark Academia l'emporte (sépia, bordeaux, laiton). Storybook Gothic ne fournit que la forme du sceau, pas ses tons bijou ni sa typographie gothique.

## 1. Jetons

| Rôle | Clair | Sombre |
|---|---|---|
| Fond (parchemin / cuir) | `#f0e8d6` | `#16110c` |
| Carte | `#fbf7ec` | `#211a13` |
| Texte | `#231a12` | `#efe4cf` |
| Texte discret | `#5f5040` | `#b9a98f` |
| Ligne | `#d9ccb2` | `#3b3125` |
| Bordure de champ | `#8f7d5e` | `#8d7b5e` |
| Accent (bordeaux / rose ancien) | `#7a1f2b` | `#e09aa5` |
| Laiton (texte) | `#7a5a12` | `#d2a64a` |
| Barres du graphique | `#a07a2c` | `#b08a37` |
| Bandeau et pied de page (noyer) | `#2a1c13` | `#0f0b08` |
| Or sur noyer | `#d9b45f` | `#d9b45f` |

- **Typographie** : titres en *Cormorant Garamond* (600 à 700, italique pour les mentions discrètes) ; texte et interface en *Source Sans 3*. Chiffres des prix en chiffres alignés (`lining-nums`). Polices auto-hébergées (`web/v2/fonts/`, licence OFL), sous-ensemble latin, 90 Ko au total.
- **Formes** : angles peu arrondis (6 px) ; filets doubles couleur laiton pour séparer les sections ; sceau circulaire à double anneau ; tampons rectangulaires légèrement inclinés pour les éditions (V1 à V5).
- **Texture** : grain de papier très léger (bruit SVG), uniquement derrière le fond ; jamais derrière du texte courant.
- **Mouvement** : 280 ms, courbe douce ; la jaquette se soulève de 5 px au survol (livre tiré de l'étagère). Désactivé si l'utilisateur demande moins de mouvement.
- **Espacement** : base de 8 px ; colonne de sélection de 290 px ; contenu jusqu'à 1180 px.

## 2. Repères culturels

À inclure : jaquettes des livres comme élément principal (lecture à distance d'étagère) ; filets doubles et sceau laiton ; tampons d'édition ; vocabulaire de bibliothèque (étagère, fiche, rayon) ; petites capitales espacées pour les libellés.
À éviter : fausse patine ou taches sur les surfaces de lecture ; noir pur façon film d'horreur ; polices gothiques ou pseudo-médiévales ; vocabulaire de jeu de rôle caricatural.

## 3. Notes par composant

- **Boutons / segments** : pilule à bordure fine ; état actif plein bordeaux ; zone tactile de 44 px.
- **Cartes** : fond parchemin clair, bordure fine, ombre douce ; la carte de cote est coiffée d'un double filet.
- **Champs** : bordure à 3:1 de contraste minimum, étiquette en petites capitales.
- **Navigation** : bandeau noir sobre, liens d'ancre.
- **En-tête** : titre grand format, chiffres clés, éventail de cinq jaquettes.
- **Titres** : Cormorant Garamond ; sections séparées par un filet double.
- **Séparateurs** : filet double laiton ou simple filet de ligne.
- **Liens** : accent bordeaux, soulignés.
- **Pastilles / tampons** : édition (V1 à V5) en rectangle incliné ; badge « V » or sur noyer.
- **Fenêtre de fiche** : liseré laiton en haut, jaquette à gauche, cotes en trois blocs, autres éditions en bandeau défilant.
- **Alertes** : l'avis « Cotes d'archives » en marge, filet laiton à gauche.
- **Icônes** : aucune icône décorative ; sceau et tampons dessinés en CSS.

## 4. Points d'attention

- **Contraste (WCAG AA)** : tous les couples de texte vérifiés passent (≥ 4,5). Les bordures de champ passent à 3,27 (clair) et 4,58 (sombre). Barres de graphique : corrigées pour atteindre 3:1 en clair (`#a07a2c`, 3,69).
- **Mouvement réduit** : les animations sont neutralisées ; aucune information ne dépend d'un mouvement.
- **Style** : fond noir unique (voir « Style unique : fond noir » plus bas) ; plus de thème clair.
- **Risque de lassitude** : Dark Academia est une esthétique très répandue depuis 2020. Ici elle reste au service d'un sujet de bibliophile, ce qui limite le risque.
- **Prix** : toujours sur des surfaces sobres ; le bandeau « Cotes d'archives » rappelle que les prix sont anciens.
- **Aucune dépendance externe** : polices, images et données sont servies par le site lui-même.

## 5. Audit avec PencilPlaybook

Le playbook `PencilPlaybook` (`.claude/skills/PencilPlaybook/`, MIT, source dans `SOURCE.txt`) est conçu pour l'outil Pencil.dev, non disponible ici. Sa section « Perceptual Design Defaults » a servi de liste de contrôle. Écarts corrigés :

| Règle | Avant | Après |
|---|---|---|
| Titre d'affichage (56 px et plus) : interlettrage de −0,03 em | +0,005 em | −0,03 em ; titres de section −0,015 em |
| Survol : écart de clarté d'au moins 8 % | liens du menu, éditions, segments et cartes sans retour visible | survols ajoutés ou renforcés |
| Boutons à 6 px (les pilules font « grand public ») | pilules à 999 px | 6 px (le sceau reste rond : c'est un sceau) |
| Zones tactiles de 44 px sur téléphone | quelques boutons à 32–40 px | 44 px partout |
| Contour de focus : décalage de 2 px, suit l'arrondi | arrondi forcé à 3 px | arrondi de l'élément |
| Mouvement : 200–300 ms, décélération | 280 ms, courbe maison | 250 ms, `cubic-bezier(0, 0, .2, 1)` |
| Longueur de ligne : 45 à 75 caractères | notes sans limite | 70 caractères maximum |

Valeurs déjà conformes : contrastes de texte (≥ 4,5), contrastes non textuels (≥ 3), corps de texte non blanc pur en mode sombre, interligne 1,55 pour le texte et 1,1 pour les titres, rayon des cartes de 6 px, aucun texte sous 10 px.

## 6. Ma collection

- **Stockage** : dans le navigateur de chacun (`localStorage`, clé `cote-collection-v1`). Rien n'est envoyé, aucun compte. Si le stockage est indisponible (navigation privée), un message le dit.
- **Ajout** : signet en haut à droite de chaque jaquette (« + » puis « ✓ »), ou case « Je possède ce livre » dans la fiche. L'état proposé est celui de la cote affichée ; il se règle ensuite, ainsi que le nombre d'exemplaires.
- **Estimation** : patrimoine = somme, par exemplaire, de la cote de l'état indiqué. Plancher (tout en convenable) et plafond (tout en TBE) encadrent le total. Les exemplaires sans cote pour l'état choisi sont signalés et exclus du total.
- **Lecture** : titres possédés sur titres existants par série (barre de progression), pièces les plus cotées, tableau modifiable de tous les exemplaires, filtre « Seulement ma collection ».
- **Export / import** : JSON (avec l'estimation) et CSV (séparateur point-virgule, lisible par Excel en français). Import d'une liste d'ISBN (10 ou 13 chiffres, avec ou sans tirets), éventuellement suivis de l'état et de la quantité, ou d'un fichier exporté.
- **Réserve** : l'estimation repose sur des cotes d'archives. Elle ne remplace ni une expertise ni un prix de vente réel, et le dit sur l'écran.

## 7. Inventaire guidé

Constituer une collection livre par livre est long ; le parcours procède du général au particulier, et s'enregistre à chaque geste :

1. **Bienvenue** : annonce des quatre étapes et choix de l'état habituel (convenable, bon état, TBE).
2. **Séries** : un écran de tuiles (couverture et nom), on touche celles dont on a au moins un livre.
3. **Éditions** : un seul tableau séries × V1 à V5 ; les éditions inexistantes pour une série sont grisées.
4. **Listes** : une par série et édition. « Tout cocher » pour une édition complète, puis on décoche les manquants ; ou saisie de numéros (« 252, 267-272 ») ; l'état se règle par liste et s'applique aux livres cochés.
5. **Bilan** : patrimoine estimé, plancher, plafond, et téléchargement du fichier JSON (ou CSV).

Principes : un seul choix par écran ; jamais de perte (fermer et reprendre à tout moment, les choix déjà faits sont repris) ; fenêtre en plein écran sur téléphone, zones tactiles de 44 px ; progression visible (barre et « liste 2 sur 5 »).

## Inventaire guidé : reprise et sauvegarde

- **Écran de départ** : « Reprendre là où j'en étais » (si un avancement est mémorisé) ou « Continuer avec ma collection » ; « Charger mon fichier » (JSON, CSV ou liste d'ISBN) ; « Repartir de zéro » (avec confirmation).
- **Fichier chargé** : les livres sont ajoutés à la collection, puis les séries, les éditions et les couvertures sont cochées d'après leur contenu. L'inventaire s'ouvre à l'étape « Séries », avec un message de bilan.
- **Enregistrement à chaque étape** : la collection est écrite à chaque clic (`cote-collection-v1`), l'avancement (étape, séries, éditions, liste en cours, état habituel) dans `cote-parcours-v1`. Le pied de l'inventaire affiche « Enregistré dans ce navigateur à HH:MM » et un lien « Télécharger ma sauvegarde » (JSON).

## Application installable (PWA)

Comme sur Scénario : manifeste (`web/manifest.webmanifest`), icônes (`web/icons/`, dont une version « maskable » pour Android) et bouton « Installer l'application » (visible seulement quand le navigateur le propose ; sur iPhone, une aide en pied de page). En plus, `web/sw.js` rend l'application utilisable sans réseau : pages, scripts, styles et données passent par le réseau d'abord (version à jour) avec copie locale en secours ; jaquettes, polices et icônes viennent de la copie locale. Les chemins sont relatifs, car le site vit sous `/LDVELH/`. Pour forcer le renouvellement des copies, changer `VERSION` dans `sw.js`.

## Haut de page de l'accueil : l'illustration

Fond toujours sombre : un fondu noir porte le bandeau, l'icône, le nom du site (titre précédé de l'icône) et les textes ; l'illustration (un mage face à un dragon, fournie par le propriétaire) apparaît à droite sur ordinateur, en bas sur téléphone. Trois illustrations (`web/images/accueil-1.webp`, `-2`, `-3`) sont tirées au hasard à chaque visite (petit script dans l'en-tête de `index.html`, cadrage propre à chacune dans `style.css`). Le contraste du texte a été mesuré (≥ 6,5 sur toutes les tailles, thèmes clair et sombre). Les originaux sont conservés dans `docs/images-accueil/`. L'ancienne photo Pexels et l'éventail de jaquettes ont été retirés ; `scrapers/image_accueil.py` reste disponible pour chercher d'autres images libres de droits.

## Icône du site : le mage doré

Emblème fourni par le propriétaire (mage encapuchonné, or sur noir), conservé dans `docs/icones-propositions/source-mage-or.png`. `python pipeline/icones.py` en tire toutes les déclinaisons : icônes de l'application (`web/icons/icon-192.png`, `icon-512.png`, `icon-maskable-512.png` pour Android), icône iPhone (`apple-touch-icon.png`), favicons (`web/favicon-16.png`, `favicon-32.png`, `favicon.ico`). Le noir de l'image est remplacé par le brun du site. Le même emblème sert de logo dans l'en-tête. Les anciennes propositions dessinées à la main ont été abandonnées.

## Barre de menu du bas (téléphones)

Sous 700 px de large, une barre fixe en bas remplace les liens de l'en-tête (qui n'est pas collant et masque ses liens sur téléphone) : La cote, L'étagère, **Inventaire** (bouton central, ouvre l'inventaire guidé), Ma collection (avec le nombre d'exemplaires) et À propos. Chaque entrée a une icône et un libellé ; l'entrée de la section en cours est dorée (`aria-current="location"`, suivie par un `IntersectionObserver`). La barre respecte la zone sûre des iPhone, laisse de la place en bas de page, et se masque pendant la saisie au clavier. Sur ordinateur, elle n'existe pas : le menu du haut reste inchangé.

## Organisation des pages

- **Accueil (`index.html`)** : le filtre à gauche ; à droite, la cote de la sélection puis, en dessous, l'étagère.
- **Ma collection (`collection.html`)** : page dédiée (estimation, répartition par série, pièces les plus cotées, exemplaires, import et export, inventaire guidé). Elle est générée par `pipeline/construire_pages.py`, et `app.js` s'adapte à la page (`data-page`). Le menu du haut et la barre du bas y mènent ; la pastille indique le nombre d'exemplaires.
- **Pages annexes** : Le projet, Confidentialité, Mentions légales (voir plus haut).

## Inventaire guidé : gestes rapides

- **Éditions** : sous chaque colonne V1 à V5, un bouton « Tout » (devient « Aucun ») coche cette édition pour toutes les séries choisies ; « Tout sélectionner » et « Tout désélectionner » valent pour l'ensemble du tableau.
- **Couvertures** : sous chaque jaquette, trois boutons C, BE, TBE (convenable, bon état, très bon état). Toucher l'état déjà choisi retire le livre. Toucher la couverture garde l'état par défaut de la liste.
- **Autres éditions** : au-dessus de la liste, des onglets V1 à V5 permettent d'ajouter une édition non cochée (utile après le chargement d'un fichier). Le petit chiffre indique les livres déjà cochés.

## Style unique : fond noir

Le site n'a plus de thème clair ni de bouton d'éclairage : un seul style, **fond noir** (`#000`), cartes en gris très sombre (`#0e0e0e`, `#181818`), texte crème, accent jaune doré foncé, bandeau « site en construction » en bordeaux. Plus aucun brun : le grain de papier a été supprimé, les icônes sont refaites sur fond noir (`python pipeline/icones.py`). `color-scheme: dark` rend aussi les champs, listes et barres de défilement du navigateur sombres.

## Format de sauvegarde et lien de transfert (règle de compatibilité)

Le fichier JSON exporté porte `application` et `version` (constante `FORMAT_FICHIER` dans `web/app.js`, actuellement 1).
Le lien de transfert (`collection.html#c=1z.…`) porte le même numéro de format ; la collection y est compressée
(`deflate-raw`, repli sans compression `1.…`) et reste après le « # » : elle n'est jamais envoyée à un serveur.

Règles à respecter à chaque modification, pour ne jamais rendre inutilisable le fichier d'un visiteur :
1. Le livre est identifié par son **ISBN** (stable) ; titre, série, prix du fichier ne servent qu'à l'affichage.
2. On peut **ajouter** des champs librement. Renommer ou retirer un champ impose de passer au format suivant
   **et** d'écrire dans `importer()` / `lireCode()` la conversion depuis l'ancien format. On ne supprime jamais un lecteur.
3. Un champ ou un livre inconnu est **ignoré et signalé** (« n non reconnus »), il ne fait pas échouer l'import.
4. Un fichier ou un lien d'un format **plus récent** que le site est refusé avec un message clair (« actualisez la page »).
5. Le lien reçu n'écrit rien tant que le visiteur n'a pas choisi (Ajouter / Remplacer / Ignorer) ; l'adresse est nettoyée.
À chaque évolution du format, vérifier à l'écran : ancien fichier v1 accepté, format futur refusé, liste simple, lien compressé ou non, lien abîmé.

## Accueil simplifié (octobre)
- **Première action = chercher** : champ « Titre, auteur ou ISBN » dans l'en-tête (formulaire de recherche, bouton « Chercher »), puis 4 raccourcis de séries (les plus fournies). Les deux envoient à `#recherche` avec le filtre appliqué.
- **Étagère d'abord** : onglet « Sur l'étagère » par défaut (les couvertures se reconnaissent), « Cote de la sélection » en second (`#onglet=cote`).
- **Un seul avertissement de cote** (`#avis-prix`), sous les onglets, valable pour les deux vues ; bandeau rouge réduit à une ligne : « Site en construction. Prix en cours de vérification. »
- Accroche courte ; les chiffres (éditions, livres, séries) tiennent sur une ligne discrète.

## Prix payé (collection)
- Champ **facultatif**, par exemplaire, dans le tableau « Vos exemplaires » et dans la fiche (`COLL[id].prix`, 0,01 à 2000 €, virgule ou point). Saisie invalide ou absurde : ignorée.
- Bloc « Investi » : la somme payée, rien d'autre. **Pas de « gain » ni de « perte »** : une cote est une estimation, pas un prix de vente, et le site ne promet pas de plus-value.
- Export JSON (`prix_paye`, format toujours 1 : champ ajouté), export CSV (colonne `prix_paye` en dernière position), import JSON et CSV (lecture par colonnes pour notre propre CSV), lien de transfert (`…b2@12.5`). Un ancien fichier sans prix reste accepté.
- Pour l'instant **rien n'est envoyé** : le prix reste dans le navigateur. L'envoi automatique à la cote (relais en ligne, anonyme, avec avis clair avant saisie) est la prochaine étape ; il exige un compte Cloudflare.

## Lot acheté (collection)
- Bouton « Ajouter un lot acheté » (collection vide et collection remplie) : fenêtre avec recherche (titre, auteur ou ISBN), livres du lot (état, exemplaires), **prix total payé** et **frais de port** facultatifs.
- Le prix à répartir = total − port, réparti sur les livres **au prorata de leur cote** (à défaut de cote, part moyenne). Chaque prix reste modifiable ; les autres se rééquilibrent. « Répartir de nouveau » annule les corrections.
- À l'ajout : chaque livre reçoit son prix par exemplaire et un repère `lot` (exporté en JSON). Un livre déjà possédé gagne un exemplaire, avec un prix moyen pondéré.
- **Ces prix sont une répartition, pas des prix réels livre par livre** : le site le dit, et les lots ne devront jamais alimenter la cote publique comme prix individuels (indicateur de tendance seulement).

## Fiche : jaquette en fond
Dans la fiche d'une édition, la jaquette sert de fond : floue (30 px), saturée, fondue vers le bas par un masque et assombrie par un voile (`.fiche-fond`, variable `--fond`). Contrôle de lisibilité fait sur les couvertures les plus claires (contraste du texte ≥ 4,5 ; mesuré à 5,6 au pire). Les lignes de la rubrique « Dans ma collection » (état, exemplaires, prix payé) sont en mise en page flexible avec un espace de 14 px entre l'intitulé et son champ.

## Cinq illustrations d'accueil
Tirage au hasard à chaque visite parmi cinq images (`accueil-1` à `accueil-5`, choix dans l'en-tête de `index.html`). **Chaque image couvre tout l'en-tête, titre compris** (`cover`), avec un voile sombre à gauche pour la lecture du texte (contraste mesuré ≥ 10 sur chaque image, ordinateur et téléphone). Le cadrage propre à chaque image est réglé par `--pos`.
- 4 : duel elfe et orque dans la neige (`docs/images-accueil/4-elfe-et-orque.webp`, source de 561 × 557 px agrandie ×2 : un peu floue sur un très grand écran ; une source plus grande serait préférable).
- 5 : duel dans des ruines (`docs/images-accueil/5-elfe-et-orque-ruines.webp`, 1215 × 1295 px).

## Accueil : bloc « Ma collection » et frais de port d'un lot
- L'accueil affiche, sous la recherche, un bloc **Ma collection** : « vide pour l'instant » ou nombre de titres et d'exemplaires, valeur estimée et somme investie, avec le bouton « Voir ma collection » (vers `collection.html`) et « Constituer / Compléter pas à pas ».
- **Frais de port d'un lot** : ils sont comptés dans le prix payé. On saisit le prix total payé, livraison comprise ; il est réparti en entier sur les livres du lot (un lot de 20 € dont 5 € de port donne 20 € répartis et 20 € investis). Il n'y a pas de champ séparé pour le port. Une version intermédiaire gardait le port à part (champ `port`) : à la lecture, ce port est ajouté au prix du livre.

## Pages publiques des livres (référencement)

- Une page par édition (`web/livre/<isbn13>.html`), une page « Tous les livres » (`web/livre/index.html`), `web/sitemap.xml` et `web/robots.txt`.
- Source unique : `web/data/versions.json`, la même liste que la fiche du guide. Tout est généré par `pipeline/pages_livres.py`, appelé par `pipeline/construire_pages.py` (donc après chaque export des données). On ne modifie jamais ces fichiers à la main : un livre créé, modifié ou supprimé dans les données crée, met à jour ou supprime sa page.
- Les prix exacts restent réservés aux comptes connectés : la page ne montre que le niveau de prix (€ à €€€€€, mêmes seuils que `SEUILS_COTE` dans `web/app.js`). Aucune annonce, aucune pépite.
- Les chaînes qui publient le site (`.github/workflows/*.yml`) envoient `web/livre`, `web/sitemap.xml` et `web/robots.txt` avec le reste. Un nouvel atelier qui régénère les pages doit faire de même.
- Garde-fou : `pipeline/test_pages_livres.py` (une page par édition, aucune en trop, contenu conforme au générateur, aucun prix exact).
- Les 5 titres sans ISBN (L'Œil Noir, identifiants `LOCAL-…`) n'ont pas de page.

## Pépite du jour (offerte aux Héros) et partage

- Le Zagor choisit l'annonce : bouton « Offrir aux Héros aujourd'hui » sur chaque carte du Butin. Le service technique (action `pepite_offrir`, Zagor seul) écrit `web/data/pepite-du-jour.json` ; `pepite_retirer` le vide. Le fichier est public : l'annonce, son prix, son lien, la date.
- Objectif : attirer des visiteurs et faire connaître le site. La pépite du jour est donc publique : bloc « Pépite du jour » sous la présentation de l'accueil (prix, pourcentage sous la cote, lien de l'annonce, lien de la fiche), et encart sur la page publique du livre concerné. Les autres pépites restent réservées aux sorciers.
- Les Héros connectés la voient aussi en tête de « À trouver » ; le badge de l'étoile du menu affiche 1. Elle n'est valable que le jour où elle est offerte (jour de Paris) : dès le lendemain, elle disparaît de l'accueil, de « À trouver » et de la page du livre. Les sorciers voient déjà toutes les pépites ; le Zagor voit celle qu'il a offerte, avec « Retirer ».
- La carte de partage (« Créer la carte à partager », sous la pépite du jour) est réservée au Zagor. L'image montre la couverture, le prix de l'annonce et « −N % sous la cote », jamais la cote. La fenêtre propose aussi le texte du post (court, modifiable, à copier) : la pépite, puis le lien vers le bloc « Pépite du jour » de l'accueil (`/#pepite-jour`), qui renvoie vers l'annonce, et l'invitation à se connecter. Le trafic passe ainsi par le site. Le Zagor publie lui-même sur Facebook ; le site ne publie rien à sa place.
- Après toute modification de `relais/Code.gs` ou `relais/logique.gs`, le propriétaire redéploie le service technique à la main (première ligne : date et heure de version).

## Butin : première apparition des annonces

- `pipeline/export_site.py` mémorise la première apparition de chaque annonce (clé : son lien) dans `premieres`, dans `annonces.json` (toutes) et `butin.json` (celles du Butin). Une annonce déjà connue garde sa première apparition ; une annonce nouvelle reçoit la date et l'heure (UTC) de la génération. Au premier passage, les annonces déjà en ligne prennent leur date de dernière observation, sans heure : elles ne seront jamais « nouvelles ».
- Le Butin trie « Nouvelles annonces d'abord » sur cette date (à égalité : plus forte réduction), affiche l'étiquette « Nouveau » pendant 24 heures et « repérée il y a … ».
- Garde-fou : `pipeline/test_export.py` (`TestPremieresVues`).

## Nouveaux butins (sorciers et Zagor)

- Une annonce du Butin est « nouvelle » si sa première apparition (`premieres`, voir plus haut) est postérieure à la dernière ouverture de la page Butin sur cet appareil (clé `cdh-butin-vu`, 24 h au premier passage).
- Le nombre est dit sur l'accueil (bandeau « N nouvelles annonces au Butin », qui remplace le petit bouton « Butin » de la carte) et dans le menu du haut (entrée « Butin » avec pastille). Les deux mènent au Butin trié « Nouvelles annonces d'abord » (`butin.html?tri=date`). Ouvrir le Butin remet le compte à zéro.
- Les Héros et les visiteurs ne voient rien de cela.

## Reconnexion plus rapide

- Reconnexion automatique (jeton d'une heure périmé, session de 30 jours valable) : l'écran dit « Connexion en cours » (prénom et point doré qui pulse) au lieu de « Reconnecter ».
- Le niveau de la personne est relu dès que la connexion est prête, en même temps que le Drive (avant : après la fin de la synchronisation). Le prénom arrive en parallèle (événement `cdh-nom`).
- Dernier niveau connu gardé sur l'appareil (`cdh-role-vu`, 7 jours) : affiché tout de suite, puis revérifié (Zagor : si la vérification date de plus de 10 minutes ; sorcier : à chaque page). Il ne donne aucun accès : les données ne sont servies qu'après vérification par le service technique. Effacé à la déconnexion.
- Service technique (`relais/Code.gs`) : la réponse de Google à la vérification d'un jeton est gardée 5 minutes ; action `ping` ; fonction `garderEveille` pour un déclencheur toutes les 5 minutes (voir `relais/LISEZMOI.md`).

## Performance : miniatures et Butin instantané

- **Miniatures** : `pipeline/export_site.py` (`fabriquer_minis`) tire de chaque jaquette « small » une miniature de 160 px (`web/covers/mini/ISBN.webp`, environ 8 Ko au lieu de 26 Ko) et ajoute `couverture_mini` à chaque édition de `versions.json`. Elle n'est refaite que si la jaquette change (empreintes dans `web/covers/mini/sources.json`) : pas de bruit dans les envois. Les petites vignettes (40 à 80 px : listes, « À trouver », ajout, éventail) l'utilisent ; les cartes et la fiche gardent « small » et « medium ». Les chaînes qui publient `web/covers` envoient donc aussi `mini/`.
- **Butin instantané** (sorciers et Zagor) : `Relais.lireButin` donne tout de suite la dernière réponse gardée sur l'appareil (`cdh-butin-cache`, 12 h au plus), puis la réponse fraîche la remplace. Badges, bandeau et pépites s'affichent donc sans attendre le service technique. Le Butin gardé n'est lu que pour un niveau 2 ou 3 connu, et il est effacé à la déconnexion et si la personne n'a plus ce niveau.
