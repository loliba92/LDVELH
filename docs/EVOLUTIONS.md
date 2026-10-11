# Évolutions prévues

## Classements : les plus chers, les moins chers

Faisable avec les données actuelles : le site sait déjà trier par prix en bon état. À ajouter :
- une vue « Classements » : les 20 livres les plus chers et les 20 moins chers, par état, avec filtre par série ou version ;
- les mêmes classements pour les séries et les versions (moyenne la plus haute et la plus basse).

Attention : tant que les prix sont ceux de l'ancien relevé de collection-ldvelh.fr, ces classements reflètent d'anciennes cotes.

## Les prix qui évoluent vite

Nécessite **plusieurs relevés de prix actuels, espacés dans le temps**. Le modèle en étoile le permet déjà (dimension date, une ligne par prix observé), mais aujourd'hui chaque livre n'a qu'un seul prix, ancien et de date inconnue : calculer une évolution n'aurait aucun sens.

Quand deux ou trois relevés espacés de plusieurs semaines existeront :
- **variation** du prix médian sur 30 et 90 jours, en pourcentage ;
- **volatilité** : écart relatif entre les observations d'un même livre ;
- **confiance** : nombre d'observations derrière chaque chiffre, pour ne pas classer « en forte hausse » un livre vu deux fois.

Page « Mouvements » : les plus fortes hausses et baisses, avec le nombre d'observations.

## Prix actuels

Voir `docs/STRATEGIE-EXTRACTION.md` : interface officielle d'eBay, vos ventes et achats, relevés manuels. C'est la condition pour que les classements et les mouvements aient un sens.
