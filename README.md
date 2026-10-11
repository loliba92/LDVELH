# LDVELH : cote des livres dont vous êtes le héros

Site web pour estimer la valeur des livres-jeux d'occasion (Défis Fantastiques, Loup Solitaire, L'Œil Noir, etc.) et aider à la chasse aux livres.

## Principe

1. **Extraction** : des scripts collectent le catalogue (titres, éditions, ISBN) et les prix d'occasion sur plusieurs sites.
2. **Pipeline** : les données brutes sont nettoyées, rapprochées par ISBN, puis on calcule les fourchettes de prix par état et un indice de liquidité.
3. **Site web** : une interface statique lit les fichiers générés (catalogue, fiche d'un livre, scan d'ISBN, calculateur de marge).

## Arborescence

```
scrapers/            Phase 1 : extraction (un script par source)
  common/            Outils partagés (requêtes polies, journal, normalisation)
  collection_ldvelh.py   Catalogue historique collection-ldvelh.fr (site plus mis à jour)
data/
  raw/               Données brutes datées, jamais modifiées à la main
    collection-ldvelh/
    occasion/        Prix d'occasion relevés (une sous-source par site)
  processed/         Données nettoyées : editions.csv (dimension des versions)
  manual/            Vos ventes et relevés à la main (observations.csv)
  warehouse/         Base SQLite en étoile (générée, non versionnée)
pipeline/            Phase 2 : nettoyage, rapprochement par ISBN, indicateurs
web/                 Phase 3 : site web (lit data/processed)
docs/                Choix techniques, schéma des données, indice de liquidité
```

## Lancer l'extraction du catalogue

```
pip install -r requirements.txt
python scrapers/collection_ldvelh.py      # extraction des 5 versions (V1 à V5) du catalogue
python pipeline/import_catalogue.py       # importe les versions dans editions.csv et les relie par titre
python pipeline/enrich_bnf.py             # complète les fiches avec le catalogue de la BnF
python pipeline/add_book.py ISBN          # ajouter un livre
python pipeline/build_db.py               # (re)construire la base en étoile
```

Le fichier est écrit dans `data/raw/collection-ldvelh/books_data-AAAA-MM-JJ.csv`.

## Avancement

- [x] Catalogue historique extrait : 5 versions, 430 éditions, 226 livres distincts
- [ ] Sources de prix d'occasion
- [ ] Pipeline et indicateurs (fourchettes, liquidité)
- [ ] Site web

Documents : `docs/ARCHITECTURE.md` (vue d'ensemble), `docs/STRATEGIE-EXTRACTION.md` (sources et règles), `docs/MODELE-PRICING.md` (estimation des prix et liquidité), `docs/BASE-LIVRES.md` (définition de la base des livres), `docs/MODELE-ETOILE.md` (tables de dimensions et de faits), `docs/ANALYSE-CHASSE-AUX-LIVRES.md` (étude du concurrent).
