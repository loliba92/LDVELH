# La Cote du Héros — instructions de travail

## Façon de répondre au propriétaire
- Vouvoiement, ton naturel et pédagogique, sans familiarité ni gros mots, pas de style « IA ». Réponses courtes et directes.

## Fusion des demandes de fusion
- Autorisation durable du propriétaire : je fusionne moi-même mes propres demandes de fusion (squash), sans attendre un « fusionne », une fois les vérifications passées. Je préviens ensuite le propriétaire, et je lui rappelle de recharger la page deux fois sur téléphone (cache).
- Cette autorisation ne couvre que mes propres demandes de fusion sur ce dépôt.

## Relais (Apps Script)
- Chaque fois que je demande au propriétaire de mettre à jour le relais (`relais/Code.gs`, `relais/logique.gs`), j'indique toujours la date et l'heure de la version à contrôler (la ligne « Version du … » en tête de fichier, heure de Paris).

## Interface
- Toute modification visuelle se vérifie à l'écran, sur ordinateur (≈ 1100 px) et sur téléphone (≈ 390 px) : aucun mot coupé, aucun débordement. Ajouts discrets, pas de boutons dans tous les sens.
- Tester chaque changement visuel dans **tous les états où il apparaît** : visiteur, Héros, sorcier, Zagor (connexion simulée dans le navigateur avec les vraies données du dépôt), données absentes (« … » plutôt qu'un bloc qui disparaît), texte long. Regarder la capture (pas seulement les mesures) et les éléments voisins : un bouton ajouté ne doit recouvrir ni le titre ni un autre bloc.
- Une classe CSS partagée (`scan-liste`, `retirer`…) peut s'appliquer ailleurs que prévu : vérifier aussi les éléments qui portent la même classe.
- Pas de fichiers annexes que personne ne maintiendra : les données vivent dans le système existant.
