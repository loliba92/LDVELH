Relevés d'annonces (voir docs/ARCHITECTURE.md et docs/STRATEGIE-EXTRACTION.md).

- `ebay-AAAA-MM-JJ.csv`, `libraires-AAAA-MM-JJ.csv` : agrégats par livre et par état (nombre, minimum, médiane, maximum), lus par `pipeline/build_db.py`.
- `annonces-AAAA-MM-JJ.csv` : annonces eBay avec titre et lien, pour contrôler les prix et alimenter le Butin.
- `annonces-leboncoin-AAAA-MM-JJ.csv`, `vendus-leboncoin-AAAA-MM-JJ.csv`, `leboncoin-AAAA-MM-JJ.csv`, `leboncoin-vendus-AAAA-MM-JJ.csv` :
  relevés Leboncoin envoyés par le bot du propriétaire et contrôlés par `pipeline/importer_leboncoin.py`.
