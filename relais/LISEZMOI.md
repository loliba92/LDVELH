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

## Nouveaux comptes et avis

- `bienvenue` (tout compte connecté) : la première fois qu'un compte appelle le relais, il est compté (propriétés du script `u:<empreinte courte>` et `u:total`) et un courriel
  « Nouveau compte : Marie #a3f2 (42e compte) » est envoyé au compte propriétaire du script. Le site ne l'appelle qu'une fois par navigateur.
- `comptes_lire` (SuperAdmin) : total des comptes (`u:total`), arrivées du jour et liste des prénoms avec leur date (propriétés `un:<rang>`, écrites par `bienvenue` depuis l'ajout de cette liste ; les comptes arrivés avant n'ont que leur rang). Affichés par la page Équipe. À redéployer après mise à jour de `Code.gs` et `logique.gs`.
- `avis` (tout compte connecté) : la note de 1 à 5 étoiles (obligatoire) et le commentaire (facultatif, 1500 caractères au plus) de « Qu'en pensez-vous ? » sont envoyés par courriel au compte propriétaire, avec le prénom du
  compte, jamais l'adresse. Limite : trois avis par personne et par six heures.
- Ces deux actions envoient des courriels. Il faut d'abord autoriser l'envoi : dans l'éditeur Apps Script, choisir la fonction `autoriser` dans la liste en haut, cliquer sur Exécuter, accepter les autorisations demandées par Google, puis redéployer (Déployer > Gérer les déploiements > crayon > Nouvelle version > Déployer).

## Gérer l'équipe

- Depuis le site (SuperAdmin) : page « Équipe » (ajouter, retirer, bloquer).
- À la main : `data/admins.json`, rubrique `equipe` : `"sha256:EMPREINTE": {"nom": "Marie", "role": "admin"}`.
  L'empreinte est celle de l'adresse en minuscules : `printf '%s' "adresse@exemple.fr" | sha256sum`.

## Garde-fous

- Seuls les lots `corriger-prix.yml`, `corriger-fiche.yml` et `ajout-isbn.yml` peuvent être lancés, avec leurs champs connus et une taille limitée.
- Le nom enregistré est posé par le relais, jamais par le site.
- On ne peut ni se retirer ni se bloquer soi-même, ni retirer le dernier SuperAdmin.
- La liste des admins est relue à chaque envoi (30 secondes de mémoire au plus) : un retrait est quasi immédiat.
- Une erreur interne ne renvoie jamais de détail à l'extérieur.

## Session de longue durée (30 jours)

Le relais garde le jeton de renouvellement de Google ; le navigateur n'a qu'un identifiant de session, révocable.

Mise en place :
1. Console Google Cloud : le client OAuth « Application Web » du site doit avoir les origines JavaScript autorisées du site (déjà le cas). Aucune adresse de redirection à ajouter : la connexion utilise la fenêtre Google (« postmessage »).
2. Propriétés du script : ajouter `CLIENT_SECRET` (le secret du client OAuth). Ne jamais l'écrire dans le dépôt.
3. Copier `Code.gs` et `logique.gs`, puis Déployer > Gérer les déploiements > Nouvelle version.
4. Dans `web/data/admin-config.json`, mettre `"session_relais": true`.
5. Se connecter une fois. Si Google n'accorde pas de jeton de renouvellement (compte déjà autorisé), retirer l'accès de l'application dans le compte Google (myaccount.google.com/permissions) puis se reconnecter.

Actions du relais : `session_ouvrir` (code Google), `session_renouveler`, `session_fermer` (révoque chez Google). Tests : `node pipeline/test_relais.js`.

## Rapidité de la reconnexion

- Le service vérifie un jeton auprès de Google : cette vérification est gardée 5 minutes, les appels qui se suivent (niveau, Butin, notes) sont donc plus rapides. L'expiration du jeton et la liste des admins restent contrôlées à chaque appel.
- Action `ping` : réveille le service sans aucune donnée.
- Déclencheur facultatif : dans Apps Script, icône « Déclencheurs » (horloge) > Ajouter un déclencheur > fonction `garderEveille`, source « Selon l'heure », « Minuteur », « Toutes les 5 minutes ». Il garde la liste des admins en mémoire. Google ne garantit pas qu'il évite le temps de réveil du service : à constater à l'usage, et à retirer s'il ne change rien.
