# Relais des administrateurs

Le relais est un petit programme hébergé chez Google (Apps Script). Il garde la clé GitHub : les administrateurs ne la voient jamais.

Parcours d'un envoi : la personne se connecte avec Google sur le site, le site envoie sa preuve au relais, le relais la vérifie auprès de
Google, lit son niveau dans `data/admins.json` (Héros, Admin, SuperAdmin), puis lance lui-même le lot GitHub en y inscrivant son nom.

| Niveau | Droits |
|---|---|
| Héros (tout compte Google) | consulter, construire sa collection, demander l'ajout d'un livre, noter les livres |
| Admin | corriger les prix, ajouter des livres, traiter les demandes d'ajout |
| SuperAdmin | tout cela, plus gérer l'équipe (ajouter, retirer, bloquer) |

Les règles sont dans `logique.gs` (testées par `node pipeline/test_relais.js`), l'accès réseau dans `Code.gs`.

## Mise en place (une fois, environ 10 minutes)

1. **Projet Apps Script.** Ouvrez script.google.com avec le compte propriétaire, créez un projet « Relais La Cote du Héros ».
   Remplacez le contenu de `Code.gs` par celui de ce dossier, puis ajoutez un fichier `logique` (type « Script ») avec le contenu de `logique.gs`.
2. **Clé GitHub dédiée.** Sur GitHub : Settings > Developer settings > Fine-grained tokens > Generate new token.
   Dépôt : `LDVELH` seulement. Droits : *Actions : Read and write*, *Contents : Read and write* et *Issues : Read and write* (pour les demandes d'ajout de livres). Durée : un an.
3. **Propriétés du script.** Dans le projet : Paramètres du projet > Propriétés du script, ajoutez :
   `CLIENT_ID` (l'identifiant client Google du site), `GITHUB_TOKEN` (la clé de l'étape 2), `DEPOT` (`loliba92/LDVELH`).
4. **Publication.** Déployer > Nouveau déploiement > Application Web. Exécuter en tant que : *moi*. Accès : *Tout le monde*.
   Autorisez l'accès demandé, puis copiez l'adresse de l'application web (`https://script.google.com/macros/s/…/exec`).
5. **Branchement.** Mettez cette adresse dans `web/data/admin-config.json`, champ `relais_url`.
6. **Premier essai.** Connectez-vous avec Google sur le site, validez un prix, envoyez : le lot doit se lancer, avec votre nom.
7. **Bascule définitive.** Quand tout fonctionne : dans `data/admins.json`, mettez `"relais": true` (le lot n'accepte plus que le nom
   transmis par le relais), puis **supprimez l'ancienne clé commune** et la page « Accès commun » : l'ancienne clé reste valable pour
   quiconque l'a déjà.

## Demandes d'ajout de livres

Tout compte connecté (Héros) peut demander l'ajout d'un livre : le relais en fait un signalement GitHub (étiquette `demande-ajout`) au nom de la personne
(prénom et quatre signes, jamais l'adresse), avec une limite de six demandes par personne toutes les six heures (aucune limite pour les Admins et SuperAdmins, qui peuvent aussi ajouter directement). Les admins les voient dans l'espace
administrateur, corrigent la ligne si besoin, puis acceptent (le lot « Ajouter des livres » est lancé, le signalement est fermé) ou refusent (fermé avec la raison).

## Notes des livres (1 à 5)

Tout compte connecté peut noter un livre (action `noter`, note 0 pour retirer la sienne) et retrouver ses notes (`mes_notes`). Une voix par compte et par livre
(le livre, toutes éditions confondues, identifié par son `livre_id`). Les votes sont rangés dans les propriétés du script (une propriété `n:<livre_id>` par livre,
au plus 400 votes chacune), sous une empreinte courte du compte : ni adresse ni nom. Les moyennes sont publiques : `<adresse du relais>?notes=1` répond
`{ ok, notes: { livre_id: [moyenne, nombre] } }` sans connexion, gardé dix minutes en mémoire. Un relais qui ne connaît pas encore les notes ne répond pas
`notes` : le site n'affiche alors aucune étoile. Tests : `node pipeline/test_relais.js` et `node pipeline/test_relais_notes.js`.

**Après une mise à jour de `Code.gs` ou `logique.gs`** : recopier les deux fichiers dans le projet Apps Script, puis *Déployer > Gérer les déploiements >
modifier (crayon) > Version : Nouvelle version > Déployer*. L'adresse de l'application web ne change pas.

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
