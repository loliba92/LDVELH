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

`isbn13` (clé), `isbn10`, `titre`, `oeuvre_id`, `titre_original`, `auteurs`, `traducteur`, `illustrateur`, `editeur`, `collection`, `numero_collection`, `annee`, `pages`, `format`, `prix_editeur`, `couverture_url`, `source_notice`, `statut` (brut / enrichi / vérifié), `date_maj`.

Règles :
- l'ISBN-13 sans tirets est la clé ; l'ISBN-10 est converti ;
- un livre sans ISBN reçoit un identifiant interne (`LOCAL-` + série + numéro) et le statut « à compléter » ;
- une valeur ajoutée à la main est marquée comme telle (`source_notice = manuel`).

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
