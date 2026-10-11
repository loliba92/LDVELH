# Conformité légale (France et Europe)

Vérification faite dans le code le 11 octobre 2026 ; ce n'est pas un avis juridique.

## Ce que le site fait réellement
- Aucun cookie (`document.cookie` absent), aucun formulaire, aucune mesure d'audience, aucune publicité, aucun pixel.
- Aucune ressource externe : polices, images, jaquettes et données sont hébergées avec le site (recherche de tout domaine externe dans `web/` : seuls des liens sortants, GitHub, BnF).
- Deux clés de stockage local, jamais envoyées : `cote-collection-v1` et `cote-parcours-v1` (l'ancienne clé `cote-theme`, du temps du thème clair, n'est plus écrite). Un cache hors ligne (service worker) ne contient que les fichiers du site.
- Hébergement : GitHub Pages (GitHub, Inc.).

## Pages
`collection.html`, `le-projet.html`, `confidentialite.html`, `mentions-legales.html`, produites par `python pipeline/construire_pages.py`. Liens en pied de page de l'accueil et des trois pages (vérifié fichier par fichier) ; `web/v2/index.html` n'est qu'une redirection vers l'accueil. Sur téléphone, accès par la feuille « Plus » de la barre du bas.

## Ne s'applique pas, et pourquoi
Bandeau cookies et page cookies (aucun traceur) ; CGV et médiateur de la consommation (aucune vente) ; CGU (aucun compte ni contenu d'utilisateur) ; formulaires (il n'y en a pas) ; déclaration d'accessibilité (éditeur personnel, sans activité commerciale).

## À FAIRE PAR UN HUMAIN
1. Compléter `mentions-legales.html` (champs `[À COMPLÉTER]`) : nom et prénom de l'éditeur, ou pseudonyme si l'hébergeur détient les coordonnées ; titulaire des droits ; auteur et conditions d'utilisation de l'illustration de l'accueil ; adresse électronique de contact si vous en voulez une. La page est en `noindex` tant qu'elle est incomplète : retirer la balise `robots` de `pipeline/construire_pages.py` une fois terminée.
2. Vérifier l'adresse et le téléphone de l'hébergeur (GitHub, Inc.).
3. Ajouter un fichier de licence au dépôt si vous voulez préciser les droits sur le code.
4. Si vous ajoutez plus tard une mesure d'audience, des dons ou des comptes : mettre à jour la page Confidentialité, et prévoir un consentement si un traceur est utilisé.
5. Relecture par un juriste si le projet devient commercial.
