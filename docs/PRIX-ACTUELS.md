# Prix actuels : comment ils entrent dans la cote

Les prix d'archives (ancien relevé de collection-ldvelh.fr) restent la base. Deux sources les complètent,
toutes deux légitimes : vos propres transactions, et les annonces d'eBay lues par son interface officielle.
Aucun site n'est « scrapé » (Vinted, Leboncoin, chasse-aux-livres : non).

## Ce que le site affiche

- Chaque cote porte une nature : **archives**, **annonces**, **ventes** ou **rachats**, avec le nombre de relevés,
  la date et un niveau de confiance (faible, moyenne, élevée).
- Une annonce est un prix demandé, pas un prix payé : elle est signalée comme telle et pèse peu.
- La bannière de l'accueil, la fiche d'une édition, le pied de page et l'estimation de la collection
  s'adaptent d'eux-mêmes dès qu'un prix actuel existe.

## Comment l'estimation choisit un prix

Médiane pondérée (`pipeline/estimation.py`, 14 tests). Le poids d'une observation dépend de :

| Critère | Règle |
|---|---|
| Nature | vente réelle 1,0 · vente probable 0,6 · rachat 0,4 · annonce 0,3 · archive 0,2 |
| Fraîcheur | poids divisé par 2 tous les 90 jours (365 jours pour l'archive) |
| Effectif | multiplié par la racine carrée du nombre d'annonces résumées (plafonné à 9) |

Avec une seule archive, le prix est exactement celui d'avant : l'export a été comparé sur les 430 éditions, sans écart.

## Option 1, immédiate : saisir vos propres prix

```
python pipeline/add_prix.py 9782070583805 12.5 --etat bon --type vente
python pipeline/add_prix.py 9782070583805 8 --etat tres_bon --type achat --date 2026-10-03
python pipeline/build_db.py && python pipeline/export_site.py
```

Types : `vente` (vous avez vendu), `achat` (vous avez acheté), `releve` (prix vu sur une annonce),
`rachat` (offre d'un professionnel). Les lots sont exclus du calcul. La saisie est écrite dans
`data/manual/observations.csv`.

## Option 2 : relevé hebdomadaire eBay

`scrapers/ebay_api.py` interroge la Browse API (place de marché France), par ISBN. Il écarte les lots,
les devises étrangères et les états non précisés, puis n'enregistre que des **agrégats** par état
(nombre, minimum, médiane, maximum) dans `data/raw/occasion/ebay-AAAA-MM-JJ.csv`. Ni titre, ni vendeur, ni lien.
Le workflow `.github/workflows/prix-ebay.yml` le lance chaque lundi, reconstruit la base et republie le site.

### Ce que seul le propriétaire peut faire

1. Créer un compte sur developer.ebay.com et demander les clés de **production** (pas seulement « sandbox »).
2. Déclarer la réponse à la notification de suppression de compte (obligatoire pour obtenir ces clés).
3. **Lire les conditions d'utilisation de l'API** : elles n'ont pas pu être consultées ici. Le choix de ne stocker
   que des agrégats limite le risque, mais ne remplace pas cette lecture.
4. Dans GitHub, Settings → Secrets and variables → Actions : ajouter `EBAY_CLIENT_ID` et `EBAY_CLIENT_SECRET`.
5. Lancer le workflow à la main avec une limite de 20 éditions, vérifier le résultat, puis laisser tourner.

### Points non vérifiés

- La recherche se fait par mot-clé (`q`) sur l'ISBN, car le filtre `gtin` d'eBay n'accepte que les codes UPC.
- La correspondance des codes d'état eBay (`conditionId`) avec nos trois états est une hypothèse raisonnable, à contrôler sur les premiers relevés.
- Si l'accès à la Browse API est refusé pour ce type d'usage, l'option 1 reste entièrement valable.

## Suites possibles

Classements « plus chers / moins chers », « prix qui évoluent vite » (il faut plusieurs relevés datés), partage d'une collection par lien.

## Premier relevé eBay (14 octobre 2026) et règle des 3 annonces
Essai sur 20 éditions : 19 ont au moins une annonce, 43 lignes (édition × état), 78 annonces au total. Constats :
- Les prix demandés sur eBay sont nettement plus élevés que les archives : rapport médian 1,95 sur la médiane des annonces, 1,4 sur le minimum (les archives sont une moyenne des prix les plus bas, pas une médiane : les deux mesures ne sont pas identiques).
- Des annonces isolées sont parfois aberrantes (104,69 € en bon état pour une édition archivée à 8,27 €).
- **Règle ajoutée** (`MIN_ANNONCES = 3` dans `pipeline/estimation.py`) : un relevé de moins de 3 annonces n'entre pas dans la cote. Sur ce premier relevé, 10 lignes sur 43 comptent ; les autres restent aux archives.
- À vérifier : la recherche par ISBN se fait par mot-clé, elle peut ramener d'autres éditions du même titre.

## Mise à jour lissée et auto-apprentissage (14 octobre 2026)
**Lissage** (`lisser` dans `pipeline/estimation.py`, filtre de Kalman en logarithme). Chaque nouveau relevé corrige le prix d'une part variable, au lieu de le remplacer :
- plus un relevé résume d'annonces, plus il pèse (incertitude divisée par leur nombre, plafonnée à 9) ;
- plus la nature est fiable (vente réelle > rachat > annonce > archive), plus il pèse ;
- plus l'estimation précédente est ancienne, moins elle pèse (dérive de 0,02 par semaine en variance du log) : l'archive s'efface d'elle-même ;
- une valeur à plus de 3 écarts-types de l'estimation est jugée suspecte et son poids est divisé par 4.
Exemple (premier relevé) : archive 6,98 €, médiane eBay 23,58 € sur 3 annonces → affiché 10,10 €. Un relevé de 5 annonces (12,90 € contre 7,30 €) donne 11,15 €.

**Auto-apprentissage** (`pipeline/calibration.py`). Les archives mesurent autre chose que les annonces actuelles (moyenne des prix les plus bas, relevée en 2024). Le modèle apprend le rapport actuel / archive par état, se contrôle par validation croisée et ne s'active que s'il bat les archives d'au moins 15 % sur au moins 20 éditions comparables. Actif, il remet à niveau les archives des éditions sans relevé (mention « estimation », confiance faible). Il est recalculé à chaque publication et son état est écrit dans `data/processed/calibration.json` et `web/data/meta.json`. Inactif au 14 octobre (10 éditions comparables sur 20).

**Contrôle du rattachement** : le workflow a une entrée « controle » (N éditions) qui n'enregistre rien et n'affiche que des comptages (annonces concordantes avec le titre, lots, états inconnus). La recherche se fait par ISBN, et aussi par titre pour les 120 éditions dont le titre n'existe qu'en une édition ; les annonces dont le titre ne correspond pas sont écartées.

## Fraîcheur des annonces
- L'interface d'eBay ne montre que les annonces **en ligne au moment du relevé** : aucune annonce vendue ni retirée, aucun historique. Un relevé est donc un instantané, daté du jour.
- Une annonce restée en ligne longtemps n'a pas trouvé preneur : son prix est probablement trop haut. Le programme écarte donc les annonces créées il y a plus de `MAX_AGE_JOURS` (90 jours), d'après `itemCreationDate`. 30 jours laisseraient trop peu d'annonces sur des livres rares, qui restent longtemps en vente. Les annonces sans date lisible sont conservées (le mode « contrôle » en donne le nombre).
- Les relevés successifs sont ensuite lissés (voir plus haut) : un relevé ancien perd son poids de lui-même.
- Piste, non faite : suivre les annonces qui **disparaissent** entre deux relevés (vendues ou retirées) donnerait un signal proche d'un prix de vente. Cela demande de conserver un identifiant d'annonce, ce que nous évitons tant que les conditions d'utilisation de l'API n'ont pas été lues.

## Suivi des évolutions (page « Évolutions des prix »)
À chaque exécution du workflow :
- `pipeline/mouvements.py` compare les prix publiés avec ceux de la publication précédente (instantanés conservés dans `data/processed/cotes-historique.json`, 60 derniers) ; à défaut d'instantané, la référence est la cote d'archives seule.
- Un « grand mouvement » = au moins 10 % **et** 0,50 €. Le résultat est écrit dans `web/data/mouvements.json`.
- Le **résumé de l'exécution GitHub** (onglet Actions, bas de la page de l'exécution) donne : nombre de prix comparés et modifiés, variation médiane, plus fortes hausses et baisses, état du modèle.
- La page publique `evolutions.html` (lien dans le pied de page) affiche les mêmes mouvements et se régénère avec `pipeline/construire_pages.py`.
Pistes : courbe d'évolution dans la fiche de chaque édition (les instantanés l'alimentent déjà), alerte quand beaucoup de prix bougent d'un coup.

## Contrôle du 14 octobre sur 30 éditions (sans enregistrement)
188 annonces trouvées : 151 concordent avec le titre attendu (80 %), 37 concernent un autre livre (écartées), 5 lots, 1 édition sans annonce. La date de création est toujours fournie. **63 % des annonces ont plus de 90 jours** (14 % moins de 30 jours, 22 % de 30 à 90 jours) : les livres restent longtemps en vente. Au final 45 annonces sur 188 sont retenues (récentes, concordantes, hors lots, état connu, en euros).
Conséquence : avec le minimum de 3 annonces récentes par édition et par état, peu d'éditions ont une cote actuelle. Plutôt que de choisir un seuil à la main, chaque relevé enregistre aussi les statistiques de toutes les annonces (`nb_toutes`, `prix_median_toutes`) ; `calibration.fraicheur()` en tire de combien les annonces anciennes surestiment les prix, par état (`fraicheur` dans `calibration.json`). Information seulement pour l'instant : à utiliser une fois le rapport mesuré sur assez d'éditions.

## Relevé complet du 14 octobre : ce que le modèle a appris et décidé
- **Couverture** : 236 éditions sur 425 ont des annonces ; 43 lignes (édition × état) ont 3 annonces récentes ; 126 en ont 3 en tout.
- **Décote des annonces anciennes** mesurée : les annonces récentes valent 98,7 % (bon état, 20 éditions) et 96,9 % (très bon, 12 éditions) de l'ensemble des annonces. Faible : le filtre des 90 jours écartait 48 % des annonces pour peu de gain. Le modèle étend donc la cote aux éditions qui ont au moins 3 annonces en tout (66 lignes ajoutées), en appliquant cette décote, **seulement** pour un état où elle est mesurée sur au moins 10 éditions et reste entre 0,80 et 1,05 (`calibration.ajouter_toutes_annonces`).
- **Incertitude de l'archive apprise** : l'écart entre archives et annonces actuelles est très grand (0,6 en bon état, 0,9 en convenable, 1,0 en très bon, en logarithme), bien au-dessus du 0,25 supposé au départ. Le lissage s'en sert (`calibration.sigma_archive`) : une archive très éloignée des annonces pèse peu.
- **Remise à niveau des archives sans relevé** : le modèle reste inactif (gain 6 % sous les 15 % exigés ; le rapport du très bon état sort des bornes). Aucune archive n'est modifiée sans relevé.
- **Alignement des états (C ≤ BE ≤ TBE)** : règle du propriétaire conservée (l'état supérieur est remonté au niveau de l'inférieur). **Exception** : si l'état inférieur n'est qu'une archive et l'état supérieur vient d'un relevé actuel, on ramène l'archive à la donnée actuelle, sinon une archive gonflée tirait vers le haut un prix actuel (ex. très bon état à 50 € alors que les annonces tournent à 7 €).
- **À valider** : page `revue-prix.html` (filtre « Écart important »). Cas typiques : archives très élevées (75 à 150 €) face à des annonces à 3 à 12 € ; états conflictuels dans une même édition (un état à 3 € force les états inférieurs à 3 €).

## États déduits (règle du propriétaire)
Un état sans prix est déduit des autres états de la même édition (`pipeline/etats.py`) avec des rapports relatifs au très bon état : **convenable 40 %, bon état 60 %** (`data/manual/ratios_etats.json`, modifiable). Un état qui a déjà un prix n'est jamais modifié ; les relevés actuels priment sur les archives ; le prix déduit est marqué « déduit », de confiance faible, et n'est jamais compté comme prix actuel. Au 14 octobre : 6 états déduits (3 éditions n'avaient que le très bon état) ; 6 éditions restent sans aucun prix (elles n'ont aucune annonce ni archive).
Rapports **mesurés** à titre d'information (`calibration.json`) : archives (421 éditions avec les 3 états) convenable 62 %, bon 78 % ; annonces eBay : états presque au même prix (≈ 100 %). Le réglage du propriétaire est donc plus tranché que les deux sources ; faute de prix de vente réels, il n'est pas vérifiable pour l'instant.

## Annonces sans état précisé
Règle du propriétaire : quand l'état n'est pas précisé dans l'annonce (« d'occasion » sans détail, code 3000, ou aucun état), on suppose le **bon état** (`etat_de` dans `scrapers/ebay_api.py`). Les annonces « neuf » (1000, 1500…) et « pour pièces » (7000) restent écartées. Le mode contrôle compte les annonces à état supposé. Ces annonces étaient jusqu'ici écartées (le premier contrôle en signalait beaucoup).

## Répartition 40/60 sur les trois états (règle du propriétaire)
Pour une édition qui a au moins un prix issu d'un relevé actuel, les trois états sont tirés d'un même niveau (en très bon état) : moyenne géométrique des niveaux de chaque état actuel (prix ÷ rapport de l'état), pondérée par la fiabilité de chacun ; puis convenable = 40 %, bon état = 60 %, très bon état = 100 % du niveau (`etats.repartir`). Un état qui n'avait que son archive est remplacé (« déduit », jamais compté comme prix actuel). Une édition sans prix actuel n'est pas touchée (archives conservées). Conséquence : l'ordre C ≤ BE ≤ TBE est garanti sur ces éditions, l'alignement automatique ne sert presque plus, et un état dont les annonces ne sont pas différenciées (ex. trois états à 9 €) retrouve les rapports 40/60.
Limite : cette règle n'est pas confirmée par les données (archives : 62 % et 78 % ; annonces eBay : états presque au même prix). Réglage dans `data/manual/ratios_etats.json`.
