# Site

Site statique (HTML, CSS, JavaScript, sans outil de compilation). Il lit `data/versions.json` et `data/meta.json`, générés à partir de la base en étoile.

## Voir le site

```
python -m http.server 8000 --directory web
```

puis ouvrir http://localhost:8000 (le site ne s'ouvre pas en double-cliquant sur le fichier : le navigateur refuse de lire les données).

## Mettre à jour les données

```
python pipeline/build_db.py
python pipeline/export_site.py
```

## Ce que fait le site

- **Filtres** : recherche (titre, auteur, ISBN), série, éditeur, période d'édition, versions V1 à V5, encore en vente.
- **Moyenne du filtre** : pour chaque état (convenable, bon, très bon), moyenne, médiane, minimum, maximum et nombre de livres chiffrés. Un livre sans prix pour un état est ignoré dans la moyenne de cet état.
- **Regrouper par** série, version, année, décennie ou éditeur : une ligne par groupe avec sa moyenne ; un clic sur une ligne applique le groupe comme filtre.
- **Fiche d'un livre** : informations, prix par état, et toutes les versions du même livre côte à côte.
- Les filtres sont dans l'adresse de la page : on peut la copier pour partager une vue.
- Sur téléphone, les filtres sont repliés et un résumé indique ceux qui sont actifs.

## Limite actuelle

Les prix sont des prix historiques de collection-ldvelh.fr, sans date précise. Le pied de page le rappelle. Quand des ventes réelles seront chargées dans la base, la moyenne par version les inclura automatiquement (c'est la moyenne de toutes les observations hors lots).
