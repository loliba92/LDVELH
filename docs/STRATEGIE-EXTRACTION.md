# Stratégie d'extraction des prix

Relevé du 2026-10-11 (robots.txt et accès direct). À revérifier avant chaque nouvelle source.

## Constat par source

| Source | Ce que dit le site | Accès constaté | Décision |
|---|---|---|---|
| collection-ldvelh.fr | `Disallow:` vide, tout autorisé | 200 | Fait. Données figées (site plus à jour) : sert de base historique. |
| eBay.fr | Accès automatisé interdit sans autorisation | 403 sur la recherche web | Passer par l'interface officielle (API). Pas de scraping. |
| Vinted | Création de jeux de données interdite | 200 | Pas de collecte automatique. Saisie assistée (voir plus bas). |
| Leboncoin | Robots et méthodes automatiques interdits | 403 | Pas de collecte automatique. Saisie assistée. |
| AbeBooks | Recherche interdite aux robots | non testé | Écarté, sauf accord. |
| Momox / Rakuten | Partiellement ouvert | non testé | À étudier : prix de rachat (plancher) et prix de vente reconditionné. |

Principe : on ne contourne jamais un blocage (403, anti-robot). Un blocage signifie que la source est écartée ou passe par une voie officielle.

## Sources retenues, par ordre de priorité

1. **API officielle eBay (compte développeur gratuit).**
   - *Browse API* : annonces actives, prix demandés, nombre d'offres (mesure de l'offre).
   - *Ventes réelles* : l'API dédiée (Marketplace Insights) est à accès restreint ; il faut en faire la demande. En attendant, on déduit les ventes probables des annonces qui disparaissent entre deux relevés (annonce à prix fixe fermée avant son terme = vendue probable). C'est une estimation, marquée comme telle.
2. **Vos propres ventes et achats** : la meilleure donnée, la plus fiable. Un fichier CSV simple (ISBN, état, prix, date, plateforme, frais).
3. **Saisie assistée pour Vinted et Leboncoin** : vous relevez à la main les prix lors de vos recherches (formulaire sur le site ou import CSV). Aucun robot. Le volume est plus faible, mais légitime.
4. **Catalogues ouverts** (BnF, Open Library, Google Books) : uniquement pour compléter ISBN, éditions, couvertures. Pas de prix.
5. **Contributions des utilisateurs** (plus tard) : « j'ai vendu ce livre tant, en tel état », avec modération.

## Règles techniques de tout script d'extraction

- Un script par source, sortie datée dans `data/raw/<source>/`, jamais modifiée ensuite.
- Colonnes minimales d'une observation : `source`, `type` (vendu / demandé / rachat / historique), `isbn` (ou titre brut), `prix`, `frais_port`, `etat_brut`, `etat_normalise`, `lot` (oui/non), `date_observation`, `url`.
- Respect de `robots.txt`, délai entre requêtes, identification claire, reprise après erreur, journal.
- Les données personnelles des vendeurs ne sont jamais conservées.
- Un relevé par semaine suffit pour ce marché : le marché bouge lentement.
