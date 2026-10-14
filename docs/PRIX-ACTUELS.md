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
