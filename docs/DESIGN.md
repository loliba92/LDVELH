# Design : proposition « La Cote du Héros » (`web/v2/`)

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
