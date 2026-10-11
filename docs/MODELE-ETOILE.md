# Modèle en étoile

Base SQLite : `data/warehouse/ldvelh.sqlite`, reconstruite par `python pipeline/build_db.py` à partir des fichiers CSV (qui restent la source de vérité). Schéma : `pipeline/schema.sql`.

```
                 DimDate          DimEtat
                    \              /
   DimSource ---- FaitPrix ---- DimTypePrix
                    /      \
              DimVersion --- DimLivre
```

## La table de faits

**FaitPrix** : une ligne = un prix observé pour une version, dans un état, à une date, depuis une source.
Mesures : `prix` (hors port), `frais_port`, `est_lot`. Une clé naturelle unique empêche de charger deux fois la même observation.

## Les dimensions

| Dimension | Rôle | Exemples |
|---|---|---|
| **DimLivre** | Le livre au sens du texte, toutes éditions confondues | *Down Among the Dead Men* |
| **DimVersion** | Une édition précise : V1, V2… V5, autre éditeur | V1 = Défis Fantastiques n° 43 (1991) ; V2 = Folio Junior n° 731 (1994) ; V5 = réédition Alkonost (2024) |
| **DimEtat** | État du livre | Convenable, Bon, Très bon, Neuf, Non précisé |
| **DimDate** | Calendrier de l'observation | année, trimestre, mois, semaine, jour |
| **DimSource** | D'où vient le prix | historique, eBay (API), mes ventes, relevé manuel… avec un indice de fiabilité |
| **DimTypePrix** | Nature du prix | vente réelle, vente probable, prix demandé, rachat, historique, avec le poids utilisé par le modèle de prix |

L'éditeur (Gallimard, Alkonost…), la série (Défis Fantastiques, Loup Solitaire…) et la collection sont des colonnes de DimVersion. On pourra en faire des dimensions séparées plus tard si nécessaire.

## Les versions

- Une version appartient à un seul livre. Deux versions sont regroupées **uniquement** si la colonne `livre` de `editions.csv` est renseignée à l'identique. Aucun regroupement automatique par titre : deux titres identiques peuvent désigner des jeux différents (ex. « Le Livre des Règles » existe pour L'Œil Noir et pour Terres de Légende).
- Le numéro de version est celui indiqué dans la colonne `version` (V1, V5…). À défaut, il est calculé par ordre d'année d'édition.
- `est_derniere_version` vaut 1 pour la version la plus récente du livre ; `en_vente` (1/0) se renseigne à la main.

```
python pipeline/add_book.py 9782999999992 --livre "Down Among the Dead Men" --version V5 --en-vente 1 --serie "Défis Fantastiques" --numero 43
```

## Charger des prix

Les prix historiques de collection-ldvelh.fr sont chargés automatiquement (3 prix par livre : convenable, bon, très bon).

Vos ventes et relevés manuels s'ajoutent dans `data/manual/observations.csv` :

```
isbn,date,source,type_prix,etat,prix,frais_port,lot,url
9782070583805,2026-10-10,vente_perso,vente_reelle,bon,72.50,3.20,0,
```

Codes acceptés : sources `collection_ldvelh`, `ebay_api`, `vente_perso`, `achat_perso`, `releve_manuel`, `communaute` ; types `vente_reelle`, `vente_probable`, `prix_demande`, `rachat`, `historique` ; états `inconnu`, `convenable`, `bon`, `tres_bon`, `neuf`.

Le script contrôle chaque ligne (ISBN valide, codes connus, prix lisible), signale les erreurs avec leur numéro de ligne et ignore les doublons.

## Limites actuelles

- Les prix historiques sont datés du jour de leur extraction (2026-10-11), mais leur date réelle est inconnue (le site n'est plus mis à jour). Ils portent le type « historique » et un faible poids.
- Aucun livre n'a encore de `livre` renseigné : chaque version est donc un livre à part. Le regroupement se fait au fil de l'eau.
- Les 5 ouvrages « L'Œil Noir » ajoutés à la main n'ont pas de prix.
