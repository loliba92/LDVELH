# Site : La Cote du Héros

Site statique (HTML, CSS, JavaScript, sans outil de compilation), publié par GitHub Pages à chaque envoi sur `main` (voir `.github/workflows/pages.yml`) : https://loliba92.github.io/LDVELH/
Il lit `data/versions.json` et `data/meta.json` (générés depuis la base en étoile), les jaquettes de `covers/` et les polices de `fonts/`. Aucune requête vers un site extérieur.

## Voir le site en local

```
python -m http.server 8000 --directory web
```

puis http://localhost:8000 (un double-clic sur le fichier ne marche pas : le navigateur refuse de lire les données).

## Mettre à jour les données

```
python pipeline/build_db.py
python pipeline/export_site.py
```

## Ce que fait le site

- **Sélection** : recherche (titre, auteur, ISBN), série, éditeur, années, éditions V1 à V5, « encore en vente », « seulement ma collection ». Les filtres sont dans l'adresse : on peut la partager.
- **Cote de la sélection** : prix moyen en sceau pour l'état choisi (convenable, bon état, TBE), médiane, fourchette, et répartition des prix en histogramme (avec tableau des chiffres).
- **Étagère** : jaquettes, liste, ou regroupement (série, édition, année, décennie, éditeur) ; fiche d'un livre avec ses autres éditions.
- **Ma collection** : signet sur chaque jaquette, état et nombre d'exemplaires, estimation du patrimoine (plancher et plafond), détail par série, export JSON ou CSV, import d'une liste d'ISBN. Tout est stocké dans le navigateur, rien n'est envoyé.
- **Inventaire guidé** : pour constituer sa collection sans tout saisir. Séries (un écran), éditions (un tableau séries × V1 à V5), puis pour chaque série et édition les couvertures à cocher (« Tout cocher », saisie de numéros comme « 252, 267-272 »), et enfin le bilan avec le fichier JSON à télécharger. Tout s'enregistre au fil de l'eau ; on peut quitter et reprendre.

## Limites actuelles

Les prix sont **anciens** : ils viennent d'un ancien relevé qui n'est plus mis à jour. Un bandeau le rappelle, ainsi que le pied de page et l'estimation du patrimoine.

## Anciennes versions

L'ancienne présentation du site se retrouve dans l'historique Git, au commit `1ed53485386db5295bbab6b63a26cafd769bebc3`. L'adresse provisoire `/v2/` redirige vers la racine.

Design et spécification : `docs/DESIGN.md`. Idées à venir : `docs/EVOLUTIONS.md`.
