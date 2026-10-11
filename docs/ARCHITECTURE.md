# Architecture

## Phase 1 : extraction (`scrapers/`)

Un script par source, même sortie : des fichiers datés dans `data/raw/<source>/`.

| Source | Contenu | État |
|---|---|---|
| collection-ldvelh.fr | Catalogue, ISBN, prix par état (historiques), part de collectionneurs | fait |
| Ventes terminées (eBay, via l'interface officielle) | Prix réellement payés | à faire |
| Annonces (Vinted, Leboncoin, Rakuten, etc.) | Prix demandés, nombre d'annonces | à faire |
| Catalogue de référence (BnF, Babelio, etc.) | Éditions, couvertures, ISBN | à étudier |

Règles : respecter `robots.txt` et les conditions d'utilisation de chaque site, espacer les requêtes, préférer une interface officielle (API) quand elle existe, conserver la date de chaque relevé.

## Phase 2 : pipeline (`pipeline/`)

1. Normaliser (ISBN à 13 chiffres, titres, séries, états).
2. Rapprocher les sources par ISBN, à défaut par série et numéro.
3. Calculer par livre et par état : bas, médian, haut, nombre de ventes observées, indice de confiance.
4. Calculer l'indice de liquidité.
5. Charger la base en étoile (voir `docs/MODELE-ETOILE.md`), puis exporter les résultats pour le site.

### Schéma de `books.json` (proposition)

`isbn`, `titre`, `serie`, `numero`, `annee`, `editeur`, `couverture`, `note`, `part_collectionneurs`

### Schéma de `prices.json` (proposition)

`isbn`, `etat` (convenable / bon / tres_bon), `bas`, `median`, `haut`, `nb_observations`, `confiance`, `source`, `date_releve`

## Indice de liquidité (à définir ensemble)

Mesure la facilité de revente d'un livre. Ingrédients envisagés :
- nombre de ventes terminées sur 90 jours ;
- nombre d'annonces actives (offre) ;
- rapport ventes / annonces ;
- écart entre prix demandé et prix vendu ;
- part de collectionneurs qui le possèdent (rareté).

Sortie : une note de 0 à 100 et un libellé (rapide / moyen / lent).

## Phase 3 : site web (`web/`)

Site statique (pas de serveur) qui lit `data/processed`. Écrans prévus :
1. Catalogue filtrable par série, prix et liquidité.
2. Fiche d'un livre : fourchette par état, indice de liquidité, historique.
3. Scan d'ISBN (appareil photo du téléphone) pour la chasse aux livres.
4. Calculateur : prix d'achat demandé, frais de plateforme, envoi, marge nette.

Choix de technologie : à décider (HTML/JS simple ou framework).

## Mise à jour automatique

Une tâche planifiée (GitHub Actions) lancera les extractions, le pipeline, puis publiera le site. À mettre en place une fois les sources choisies.
