# Modèle de pricing

But : pour un livre (ISBN) et un état, donner une fourchette de prix de revente crédible, une confiance, et une aide à la décision d'achat.

## 1. Les observations et leur poids

| Type | Poids | Remarque |
|---|---|---|
| Vente réelle (vous, eBay) | 1,0 | Référence. |
| Vente probable déduite | 0,6 | Annonce disparue. |
| Prix demandé (annonce active) | 0,3 | Multiplié par une décote fixe demandé→vendu (`decote_annonces`, 0,85 au 23 octobre 2026, réglable dans `data/manual/ratios_etats.json`). Hypothèse, faute de ventes réelles : voir §7. |
| Historique collection-ldvelh | 0,2 | Base de départ, vieillit (voir plus bas). |

Le poids diminue avec l'ancienneté : demi-vie de 90 jours pour les relevés récents, 12 mois pour l'historique.

## 2. Nettoyage avant calcul

- Exclure les **lots** (« lot de », « x livres », séries complètes) ou les traiter à part.
- Exclure les annonces **incomplètes ou autres éditions** (mauvais ISBN).
- Normaliser l'**état** (convenable / bon / très bon) à partir des mots de l'annonce et de l'échelle de la plateforme.
- Retirer les **valeurs aberrantes** (écart à la médiane supérieur à 3 écarts absolus médians).
- Séparer le **prix du livre** et les **frais de port** : on compare toujours le prix hors port.

## 3. Estimation du prix

Pour chaque couple (ISBN, état) :

1. **Médiane pondérée** des observations nettoyées, avec poids de type et d'ancienneté.
2. **Fourchette** : 25e et 75e centiles pondérés (bas / haut).
3. **Confiance** selon le nombre d'observations efficaces (somme des poids) :
   - moins de 2 : faible → on utilise le repli ci-dessous ;
   - 2 à 5 : moyenne ;
   - plus de 5 : élevée.
4. **Repli quand les données manquent**, dans cet ordre :
   a. même ISBN, autre état, converti par le rapport moyen entre états (observé sur l'historique : environ 1 / 1,3 / 1,9 pour convenable / bon / très bon) ;
   b. même série, même tranche de rareté (part de collectionneurs) ;
   c. prix historique ajusté par l'indice de marché (point 5).
5. **Indice de marché** : rapport médian entre prix récents et prix historiques sur les livres bien observés. Il corrige l'ancienneté de l'historique (inflation, effet de mode).

### Lissage quotidien : le prix du jour dépend de celui de la veille

L'estimation ci-dessus est recalculée chaque jour : c'est la **cible du jour**. Le prix publié n'est pas cette cible, mais une fonction de la veille :

```
prix du jour = prix de la veille + gain × (cible du jour − prix de la veille)
```

Le **gain** (part de l'écart rattrapée en un jour) dépend du nombre d'annonces **distinctes** qui fondent le prix, c'est-à-dire le plus grand nombre vu le même jour (un exemplaire revu chaque jour compte pour une seule annonce, pas pour sept) :

| Annonces | 0 (déduit, archive) | 1 | 2 | 3 ou plus |
|---|---|---|---|---|
| Gain | 0,10 | 0,10 | 0,20 | 0,30 |

Un prix du neuf (prix éditeur) prend le gain maximal ; un prix d'archive ou déduit des autres états, le gain minimal. Un prix **validé** par le propriétaire n'est jamais lissé : il remplace la cible, et c'est lui qui sert de « prix de la veille » ensuite. Les gains se règlent dans `data/manual/ratios_etats.json` (clé `gains_lissage`). Effet : une annonce isolée, ou retirée, ne fait plus sauter un prix ; un prix appuyé sur plusieurs annonces rejoint sa cible en quelques jours (cible 42 € contre 5 € la veille, trois annonces : 16 € le premier jour, environ 39 € au bout de sept). Sans prix de la veille, la cible est prise telle quelle. Règle en vigueur depuis le 23 octobre 2026, en remplacement du plafond de 10 % par jour.

## 4. Indice de liquidité (0 à 100)

Combinaison pondérée, à calibrer :
- ventes sur 90 jours (35 %) ;
- rapport ventes / annonces actives (25 %) ;
- écart prix demandé / prix vendu, plus il est faible mieux c'est (20 %) ;
- part de collectionneurs qui possèdent le livre, comme demande potentielle (20 %).

Lecture : 70 et plus = rapide, 40 à 69 = moyen, moins de 40 = lent.

## 5. Aide à la décision d'achat (chasse aux livres)

```
net = prix_revente_médian × (1 − frais_plateforme) − frais_envoi − prix_achat
marge = net / prix_achat
```

Recommandation :
- **Acheter** si net ≥ seuil minimal (par exemple 5 €) ET marge ≥ 50 % ET liquidité ≥ 40 ;
- **À voir** si l'un des critères est juste en dessous ;
- **Laisser** sinon.

Pour un livre à faible liquidité, on utilise le bas de fourchette plutôt que la médiane (prudence). Frais par défaut à régler dans l'interface (Vinted : 0 % vendeur ; eBay : environ 13 % ; Leboncoin : 0 % hors envoi).

## 6. Vérification du modèle

- **Test à l'aveugle** : on cache 20 % des ventes réelles, on les prédit, on mesure l'erreur médiane en pourcentage. Objectif de départ : moins de 25 %.
- **Couverture de la fourchette** : environ 50 % des ventes réelles doivent tomber entre bas et haut.
- **Journal de prédictions** : chaque estimation publiée est enregistrée avec sa date, pour comparer ensuite avec le prix vraiment obtenu.
- Le modèle est volontairement simple (médianes pondérées). On ne passe à de l'apprentissage automatique que s'il y a assez de ventes réelles pour le justifier.

## 7. Limites assumées

- Les prix demandés surestiment les prix vendus (vendeurs qui affichent haut, annonces invendues qui restent en ligne). La décote de 0,85 (−15 %) est une **hypothèse** d'ordre de grandeur, pas une mesure : l'effet net sur les cotes est environ moitié moindre (le modèle mélange déjà les annonces avec les archives). À mesurer : une annonce qui disparaît d'un relevé quotidien à l'autre (cumul des annonces, `web/data/annonces.json`) est une vente probable ; son prix comparé à celui des annonces restantes donnera la vraie décote. À revoir quand ces ventes probables seront assez nombreuses. Ce n'est pas la marge de négociation, qui reste à la charge de l'acheteur, en plus de la cote.
- Sans accès aux ventes de Vinted et Leboncoin, ces plateformes (probablement les plus actives) ne sont représentées que par la saisie assistée.
- La rareté réelle dépend aussi de l'édition précise ; tant que l'ISBN manque, le rapprochement reste approximatif.


## Mise en œuvre

Le modèle est codé dans `pipeline/estimation.py` et appliqué par `pipeline/export_site.py`. Détails, sources et démarches : [PRIX-ACTUELS.md](PRIX-ACTUELS.md).
