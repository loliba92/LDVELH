# Stratégie d'extraction des prix

Relevé du 2026-10-11 (robots.txt et accès direct). À revérifier avant chaque nouvelle source.

## Constat par source

| Source | Ce que dit le site | Accès constaté | Décision |
|---|---|---|---|
| collection-ldvelh.fr | `Disallow:` vide, tout autorisé | 200 | Fait. Données figées (site plus à jour) : sert de base historique. |
| eBay.fr | Accès automatisé interdit sans autorisation | 403 sur la recherche web | Passer par l'interface officielle (API). Pas de scraping. |
| Vinted | Création de jeux de données interdite | 200 | Pas de collecte automatique. Saisie assistée (voir plus bas). |
| Leboncoin | Robots et méthodes automatiques interdits | 403 | Pas de collecte automatique pour la cote : saisie assistée. Seule exception, décidée par le propriétaire le 24 octobre 2026 : une alerte personnelle sur les nouvelles annonces (voir plus bas). |
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

## Exception : relevés Leboncoin du bot personnel (25 octobre 2026)

Le propriétaire utilise, pour son usage personnel, un bot d'alerte sur Leboncoin (outil open source `lbc-finder`, adapté dans le dépôt privé `lbc-cote`). Il a décidé que les annonces que ce bot reconnaît avec certitude **alimentent la cote et le Butin**, avec leur titre et leur lien, pour pouvoir les contrôler. Les limites, pour que la règle générale (« pas de collecte automatique pour la cote ») reste lisible :

- le bot vit **hors de ce dépôt**, sur l'ordinateur du propriétaire ; **aucun code de collecte n'est dans ce dépôt** ;
- il envoie chaque soir un relevé par une **boîte aux lettres** : une issue GitHub dont le titre commence par « Relevé Leboncoin », ouverte avec une clé qui n'a que le droit d'ouvrir des issues. Le lot `.github/workflows/releve-leboncoin.yml` ne réagit qu'aux issues du propriétaire du dépôt portant ce titre et ne les exécute jamais comme une instruction ;
- `pipeline/importer_leboncoin.py` contrôle chaque ligne (ISBN connu, état, prix plausible, lien Leboncoin, date récente), nettoie le titre, et écrit dans `data/raw/occasion/` : `annonces-leboncoin-*.csv` (actives, onglet Butin), `vendus-leboncoin-*.csv` (vendues, contrôle seulement), et deux agrégats `leboncoin-*.csv` et `leboncoin-vendus-*.csv` lus par `build_db.py` ;
- poids dans la cote : **prix demandé** (0,3) pour une annonce active, **vente probable** (0,6) pour une annonce vendue ; les règles de lissage et d'écart aberrant d'`estimation.py` s'appliquent comme pour eBay ;
- dans le Butin, une annonce Leboncoin est toujours « à vérifier » (édition et état à contrôler) ;
- **aucun proxy ni contournement** : si Leboncoin bloque le bot, il s'arrête et attend ; la source devient simplement indisponible ;
- sobriété du bot : aucune requête de 23 h à 7 h, 120 requêtes par jour au plus, ralentissement après chaque blocage ;
- **point d'attention** : les conditions de Leboncoin interdisent les méthodes automatiques et la réutilisation de ses contenus. Publier des titres et des liens d'annonces dans un dépôt public augmente l'exposition par rapport à de simples agrégats. La décision et le risque restent au propriétaire ; l'interrupteur est de désactiver l'envoi côté bot, ou d'enlever ce lot.
