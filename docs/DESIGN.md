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
- **Navigation** : bandeau noyer sobre, liens d'ancre ; bouton « Éclairage » pour le mode sombre.
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
- **Mode sombre** : fourni (cuir et lampe de bureau), suit le réglage du système, avec un bouton pour forcer l'éclairage.
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

## Image d'ambiance de l'accueil (Pexels)

Photo de bibliothèque ancienne en fond du haut de page, sous un voile de la couleur du fond : dense derrière le texte (contraste mesuré ≥ 4,5 en thème clair et sombre, ordinateur et téléphone), léger du côté des jaquettes. Elle est choisie avec `scrapers/image_accueil.py` (`--chercher` pour proposer des candidats, `--retenir ID` pour l'enregistrer en `web/images/accueil.webp`, 1600 px, environ 75 Ko). La clé Pexels vient de la variable d'environnement `PEXELS_API_KEY` et n'est jamais dans le dépôt ni envoyée au navigateur ; la photo est stockée localement, le site ne dépend pas de Pexels à l'affichage. Crédit en pied de page : Phát Trương, Pexels.

## Icône du site : le mage doré

Emblème fourni par le propriétaire (mage encapuchonné, or sur noir), conservé dans `docs/icones-propositions/source-mage-or.png`. `python pipeline/icones.py` en tire toutes les déclinaisons : icônes de l'application (`web/icons/icon-192.png`, `icon-512.png`, `icon-maskable-512.png` pour Android), icône iPhone (`apple-touch-icon.png`), favicons (`web/favicon-16.png`, `favicon-32.png`, `favicon.ico`). Le noir de l'image est remplacé par le brun du site. Le même emblème sert de logo dans l'en-tête. Les anciennes propositions dessinées à la main ont été abandonnées.
