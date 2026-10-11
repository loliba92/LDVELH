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
  processed/         Données nettoyées et fusionnées
pipeline/            Phase 2 : nettoyage, rapprochement par ISBN, indicateurs
web/                 Phase 3 : site web (lit data/processed)
docs/                Choix techniques, schéma des données, indice de liquidité
```

## Lancer l'extraction du catalogue

```
pip install -r requirements.txt
python scrapers/collection_ldvelh.py
```

Le fichier est écrit dans `data/raw/collection-ldvelh/books_data-AAAA-MM-JJ.csv`.

## Avancement

- [x] Catalogue historique extrait (190 livres + 5 ajouts manuels)
- [ ] Sources de prix d'occasion
- [ ] Pipeline et indicateurs (fourchettes, liquidité)
- [ ] Site web

Voir `docs/ARCHITECTURE.md` pour le détail.
