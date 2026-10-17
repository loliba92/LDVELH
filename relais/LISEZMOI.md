# Relais des administrateurs

Le relais est un petit programme hébergé chez Google (Apps Script). Il garde la clé GitHub : les administrateurs ne la voient jamais.

Parcours d'un envoi : la personne se connecte avec Google sur le site, le site envoie sa preuve au relais, le relais la vérifie auprès de
Google, lit son niveau dans `data/admins.json` (Héros, Admin, SuperAdmin), puis lance lui-même le lot GitHub en y inscrivant son nom.

| Niveau | Droits |
|---|---|
| Héros (tout compte Google) | consulter, construire sa collection |
| Admin | corriger les prix, ajouter des livres, voir le journal |
| SuperAdmin | tout cela, plus gérer l'équipe et lancer les relevés lourds |

Les règles sont dans `logique.gs` (testées par `node pipeline/test_relais.js`), l'accès réseau dans `Code.gs`.

## Mise en place (une fois, environ 10 minutes)

1. **Projet Apps Script.** Ouvrez script.google.com avec le compte propriétaire, créez un projet « Relais La Cote du Héros ».
   Remplacez le contenu de `Code.gs` par celui de ce dossier, puis ajoutez un fichier `logique` (type « Script ») avec le contenu de `logique.gs`.
2. **Clé GitHub dédiée.** Sur GitHub : Settings > Developer settings > Fine-grained tokens > Generate new token.
   Dépôt : `LDVELH` seulement. Droits : *Actions : Read and write* et *Contents : Read and write*. Durée : un an.
3. **Propriétés du script.** Dans le projet : Paramètres du projet > Propriétés du script, ajoutez :
   `CLIENT_ID` (l'identifiant client Google du site), `GITHUB_TOKEN` (la clé de l'étape 2), `DEPOT` (`loliba92/LDVELH`).
4. **Publication.** Déployer > Nouveau déploiement > Application Web. Exécuter en tant que : *moi*. Accès : *Tout le monde*.
   Autorisez l'accès demandé, puis copiez l'adresse de l'application web (`https://script.google.com/macros/s/…/exec`).
5. **Branchement.** Mettez cette adresse dans `web/data/admin-config.json`, champ `relais_url`.
6. **Premier essai.** Connectez-vous avec Google sur le site, validez un prix, envoyez : le lot doit se lancer, avec votre nom.
7. **Bascule définitive.** Quand tout fonctionne : dans `data/admins.json`, mettez `"relais": true` (le lot n'accepte plus que le nom
   transmis par le relais), puis **supprimez l'ancienne clé commune** et la page « Accès commun » : l'ancienne clé reste valable pour
   quiconque l'a déjà.

## Gérer l'équipe

- Depuis le site (SuperAdmin) : page « Équipe » (ajouter, retirer, bloquer).
- À la main : `data/admins.json`, rubrique `equipe` : `"sha256:EMPREINTE": {"nom": "Marie", "role": "admin"}`.
  L'empreinte est celle de l'adresse en minuscules : `printf '%s' "adresse@exemple.fr" | sha256sum`.

## Garde-fous

- Seuls les lots `corriger-prix.yml` et `ajout-isbn.yml` peuvent être lancés, avec leurs champs connus et une taille limitée.
- Le nom enregistré est posé par le relais, jamais par le site.
- On ne peut ni se retirer ni se bloquer soi-même, ni retirer le dernier SuperAdmin.
- La liste des admins est relue à chaque envoi (30 secondes de mémoire au plus) : un retrait est quasi immédiat.
- Une erreur interne ne renvoie jamais de détail à l'extérieur.
