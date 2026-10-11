# Base des livres

La base est le socle de tout le projet : sans identification fiable de chaque édition, les prix ne sont pas comparables.

## 1. Trois niveaux distincts

| Niveau | Définition | Clé |
|---|---|---|
| **Œuvre** | Le texte original, indépendamment de ses éditions | `oeuvre_id` |
| **Édition** | Un livre précis : éditeur, collection, couverture, tirage | `isbn13` |
| **Observation de prix** | Un prix constaté pour une édition, un état, une date, une source | `observation_id` |

Exemple : l'œuvre *Down Among the Dead Men* (Dave Morris) a au moins deux éditions françaises : *Le repaire des morts vivants* (Défis Fantastiques n° 43, 1991) et *Le Pirate des Sept Mers* (Folio Junior, n° 731, 1994, ISBN 9782070583805). Leurs prix n'ont rien à voir ; seul l'ISBN les distingue sûrement. (Lien entre les deux à confirmer.)

## 2. Champs d'une édition (`data/processed/editions.csv`)

`id` (clé : ISBN-13, ou `LOCAL-série-numéro` sans ISBN), `isbn13`, `isbn10`, `titre`, `serie`, `numero`, `auteurs`, `traducteur`, `illustrateur`, `editeur`, `collection_editeur`, `annee`, `pages`, `notice_bnf`, `statut` (brut / enrichi / vérifié), `source`, `date_maj`.

Règles :
- l'ISBN-13 sans tirets est la clé ; l'ISBN-10 est calculé ;
- un livre sans ISBN reçoit un identifiant `LOCAL-` et le statut « brut » ;
- `serie` et `numero` désignent la série de livres-jeux (ex. Défis Fantastiques n° 43) ; `collection_editeur` est la collection de l'éditeur (ex. Folio Junior) ;
- la source de chaque fiche est conservée (`collection-ldvelh`, `bnf`, `manuel`).

## 2 bis. Ajouter un livre

```
python pipeline/add_book.py 9782070583805 --serie "Destins" --numero 731
python pipeline/add_book.py --file isbn.txt        # un ISBN par ligne
```

L'outil valide l'ISBN (clé de contrôle), refuse les doublons, complète la fiche par la BnF, puis indique ce qu'il reste à renseigner. Il avertit quand la série n'est pas précisée, car la BnF renvoie n'importe quel livre.

## 3. Sources pour construire la base

| Source | Apporte | Test du 2026-10-11 |
|---|---|---|
| collection-ldvelh.fr (déjà extrait) | Liste des livres-jeux, série, numéro, ISBN, prix historiques | 190 livres extraits |
| **Catalogue de la BnF** (interface SRU, ouverte) | Titre, auteur, traducteur, illustrateur, éditeur, année, lien de notice | Fonctionne ; requête par ISBN-10 avec tirets (`2-07-058380-5`), pas par ISBN-13 avec tirets |
| Open Library | Données internationales, couvertures | Aucune notice pour cet ISBN |
| Google Books | Pages, résumés, couvertures | Quota partagé épuisé ; demande une clé gratuite à créer |
| Wikidata | Liens œuvre/éditions, titres originaux | Limitation de débit lors du test, non évalué |
| Bases de fans internationales de livres-jeux | Numérotation d'origine (ex. Fighting Fantasy), titres originaux | À repérer et à vérifier un par un (conditions d'utilisation) |
| Saisie manuelle | Cas rares, éditions particulières, livres sans ISBN | Toujours possible |

Aucune source ne suffira seule. La BnF est la plus fiable pour les livres français.

## 4. Méthode de construction

1. **Amorçage** : importer les 190 livres déjà extraits (statut « brut »).
2. **Enrichissement automatique** par la BnF à partir de l'ISBN : traducteur, illustrateur, éditeur, année, lien de notice (statut « enrichi »).
3. **Complétion du catalogue** : lister les collections de livres-jeux manquantes sur le site historique (rééditions après 2003, collections récentes) via la BnF, par collection.
4. **Regroupement des éditions par œuvre** : proposition automatique (titre original, auteur), validation manuelle.
5. **Contrôle** : un livre devient « vérifié » après contrôle de l'ISBN, de la couverture et du numéro. Les livres rares sont contrôlés en priorité.
6. **Rapport de qualité** à chaque mise à jour : doublons d'ISBN, champs vides, titres sans ISBN, écarts entre sources.

## 5. À décider ensemble

- Périmètre : seulement les collections françaises, ou aussi les éditions étrangères et les rééditions récentes ?
- Où commencer le contrôle manuel : par les livres les plus chers ou par les plus courants ?

## 6. Les versions (V1 à V5)

**Origine.** La numérotation vient de collection-ldvelh.fr, qui range les livres en cinq « univers » (menu « Changer d'Univers », adresses `/version/V1` à `/version/V5`). Chaque version est une génération d'éditions françaises :

| Version | Livres | Exemple d'époque |
|---|---|---|
| V1 | 190 (+5 ajouts manuels) | Folio Junior, années 80-90 |
| V2 | 111 | 1996 à 2003 |
| V3 | 38 | 2007 |
| V4 | 50 | 2012 (« nouvelle édition ») |
| V5 | 36 | 2018, versions encore en vente |

Le script `scrapers/collection_ldvelh.py` parcourt les cinq versions (une session par version, une seconde entre deux requêtes) et ajoute les colonnes `version` et `rang_serie`.

**Relier les versions d'un même livre.** Le « rang dans la série » donné par le site n'est pas fiable d'une version à l'autre (chaque version réordonne sa série : le n° 4 n'est pas le même livre en V1 et en V3). `pipeline/import_catalogue.py` relie donc les versions par le **titre**, dans la même série, avec une comparaison tolérante aux majuscules et aux accents mais stricte sur les chiffres (« Livre des règles » ≠ « Livre des règles 2 »). Les rapprochements un peu moins sûrs sont listés dans `data/processed/rapport_liens_versions.csv`.

**Apport de la BnF.** Elle confirme les éditions (éditeur, année, ISBN, collection) et recoupe les ISBN du site, mais ne fournit ni numéro de version ni lien entre éditions. `pipeline/find_versions.py` reste utile pour repérer des éditions absentes du site (autres éditeurs, par exemple).

**Indicateur « en vente ».** Les livres de la V5 sont marqués en vente (indication du propriétaire du projet). Les autres versions sont à renseigner.
