# Site

Site statique (HTML, CSS, JavaScript, sans outil de compilation). Il lit `data/versions.json` et `data/meta.json`, générés à partir de la base en étoile.

## Voir le site

```
python -m http.server 8000 --directory web
```

puis ouvrir http://localhost:8000 (le site ne s'ouvre pas en double-cliquant sur le fichier : le navigateur refuse de lire les données).

## Proposition de refonte : `web/v2/`

Une nouvelle présentation, « La Cote du Héros », est proposée à côté du site actuel, qui reste inchangé : https://loliba92.github.io/LDVELH/v2/
Elle lit les mêmes données (`web/data/`) et les mêmes jaquettes (`web/covers/`). La spécification du design (jetons, repères, composants, points d'attention) est dans `docs/DESIGN.md`.

## En ligne

Le site est publié par GitHub Pages à chaque envoi sur `main` (fichier `.github/workflows/pages.yml`), à l'adresse https://loliba92.github.io/LDVELH/ .
Première fois seulement : dans le dépôt, **Settings → Pages → Build and deployment → Source : GitHub Actions**.

## Mettre à jour les données

```
python pipeline/build_db.py
python pipeline/export_site.py
```

## Ce que fait le site

- **Filtres** : recherche (titre, auteur, ISBN), série, éditeur, période d'édition, versions V1 à V5, encore en vente.
- **Moyenne du filtre** : pour chaque état (convenable, bon, très bon), moyenne, médiane, minimum, maximum et nombre de livres chiffrés. Un livre sans prix pour un état est ignoré dans la moyenne de cet état.
- **Répartition des prix** : histogramme des fréquences pour la sélection en cours, au choix pour l'état convenable, bon état ou TBE. Chaque barre compte les livres d'une tranche de prix ; la dernière regroupe les prix les plus élevés ; médiane et moyenne sont tracées ; le tableau « Voir les chiffres » donne les valeurs exactes.
- **Regrouper par** série, version, année, décennie ou éditeur : une ligne par groupe avec sa moyenne ; un clic sur une ligne applique le groupe comme filtre.
- **Fiche d'un livre** : informations, prix par état, et toutes les versions du même livre côte à côte.
- Les filtres sont dans l'adresse de la page : on peut la copier pour partager une vue.
- **Jaquettes** : miniature dans la liste, image plus grande dans la fiche. Elles sont stockées dans `web/covers/` (deux tailles recompressées) par `python scrapers/telecharger_jaquettes.py`. Une tuile remplace l'image si elle manque. Droits : les jaquettes appartiennent à leurs éditeurs, source collection-ldvelh.fr.
- Sur téléphone, les filtres sont repliés et un résumé indique ceux qui sont actifs.

## Limite actuelle

Les prix sont **anciens** : ils viennent du relevé de collection-ldvelh.fr, qui n'est plus mis à jour. Un bandeau le rappelle au-dessus des moyennes, et le pied de page aussi. Quand des ventes réelles seront chargées dans la base, la moyenne par version les inclura automatiquement (c'est la moyenne de toutes les observations hors lots).

Idées à venir (classements, prix qui évoluent vite) : voir `docs/EVOLUTIONS.md`.
