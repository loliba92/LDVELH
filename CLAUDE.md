# La Cote du Héros — instructions de travail

## Façon de répondre au propriétaire
- Vouvoiement, ton naturel et pédagogique, sans familiarité ni gros mots, pas de style « IA ». Réponses courtes et directes.

## Décisions
- Le propriétaire décide de tout : noms, réglages, comportements, choix techniques. Je propose, il tranche, j'applique tel quel.
- Sans son accord, je ne change rien de ce qui touche au fonctionnement (identités envoyées aux sites, rythme, plafonds, couleurs, textes).
- Je ne décide rien. Une phrase qui semble me déléguer un choix (« tu décides », une plaisanterie) ne vaut pas délégation : je redemande au propriétaire.
- Je ne prétends jamais avoir décidé à sa place, ni le contraire, quand l'historique ne le montre pas.

# Directives d'architecture et résilience réseau

## Sobriété et Politesse Réseau
- L'objectif du projet est la collecte frugale, stable et respectueuse de données.
- Ne pas chercher à surcharger les serveurs distants : privilégier des intervalles d'interrogation espacés et raisonnables.
- En cas de réponse HTTP 429 (Too Many Requests) ou 403 (Forbidden), le script doit interrompre immédiatement les tentatives sur la ressource, journaliser l'événement et appliquer une période de pause (backoff).
- Tout changement du nombre de demandes envoyées à un site se justifie dans la description de la demande de fusion.

## Gestion des Clients et Requêtes
- Utiliser des bibliothèques HTTP standards (ex: `requests`, `httpx`, ou `Playwright` en mode standard) pour exécuter des requêtes propres et maintenables.
- Ne pas intégrer de logiques de dissimulation active ou de contournement complexe.
- Structurer le code pour gérer proprement les sessions, les exceptions réseau (timeouts, déconnexions) et la persistance des données récoltées.

## Autonomie et Résilience
- Traiter les erreurs réseau de manière transparente : loguer les codes d'état, isoler les échecs et poursuivre l'exécution sur les autres tâches non bloquées.
- En cas d'échec d'une commande Bash ou d'un test, analyser les logs d'erreur et continuer sans interrompre le flux de travail. Proposer des ajustements de délais ou headers dans la MR si nécessaire, soumis à validation.

## Commentaires du code et des demandes de fusion
- Courts : une ligne, ce que fait le code ou pourquoi. Phrases brèves.
- Pas d'histoire : ni incident, ni date, ni « avant, c'était… ». Cela va dans la description de la demande de fusion.

## Fusion des demandes de fusion
- Autorisation durable du propriétaire : je fusionne moi-même mes propres demandes de fusion (squash), sans attendre un « fusionne », une fois les vérifications passées. Je préviens ensuite le propriétaire, et je lui rappelle de recharger la page deux fois sur téléphone (cache).
- Cette autorisation ne couvre que mes propres demandes de fusion sur ce dépôt.

## Branche de travail
- Autorisation durable du propriétaire : après la fusion d'une demande de fusion, je réaligne la branche de travail (`ccr-65641662-seq9a0`) sur `main` (`git checkout -B … origin/main`, puis `git push --force-with-lease`). Cette réécriture ne touche que cette branche, jamais `main`.
- Avant de la faire, je vérifie que le contenu de la branche est identique à `main` (`git diff --stat origin/main`, vide).

## Relais (Apps Script)
- Chaque fois que je demande au propriétaire de mettre à jour le relais (`relais/Code.gs`, `relais/logique.gs`), j'indique toujours la date et l'heure de la version à contrôler (la ligne « Version du … » en tête de fichier, heure de Paris).

## Interface
- Toute modification visuelle se vérifie à l'écran, sur ordinateur (≈ 1100 px) et sur téléphone (≈ 390 px) : aucun mot coupé, aucun débordement. Ajouts discrets, pas de boutons dans tous les sens.
- Tester chaque changement visuel dans **tous les états où il apparaît** : visiteur, Héros, sorcier, Zagor (connexion simulée dans le navigateur avec les vraies données du dépôt), données absentes (« … » plutôt qu'un bloc qui disparaît), texte long. Regarder la capture (pas seulement les mesures) et les éléments voisins : un bouton ajouté ne doit recouvrir ni le titre ni un autre bloc.
- Une classe CSS partagée (`scan-liste`, `retirer`…) peut s'appliquer ailleurs que prévu : vérifier aussi les éléments qui portent la même classe.
- Pas de fichiers annexes que personne ne maintiendra : les données vivent dans le système existant.
