/* Porte de la page admin : le niveau (Admin ou SuperAdmin) vient du relais (voir relais/), après la connexion Google du site.
   Plus de mot de passe. Une page peut exiger un niveau plus élevé avec data-niveau="superadmin" sur <main>.
   Protection légère côté navigateur : la vraie vérification est faite par le relais à chaque envoi. */
(function () {
  var porte = document.getElementById('porte');
  var main = document.getElementById('main');
  if (!porte || !main) return;
  var zone = document.getElementById('porte-google');
  var exige = main.dataset.niveau || 'admin';

  function montrer() { porte.hidden = true; main.hidden = false; document.dispatchEvent(new Event('cdh-porte-ouverte')); }
  var bouton = '<button type="button" class="bouton" data-compte="connecter">Se connecter avec Google</button>';
  function evaluer() {
    var C = window.Cloud, niveau = window.Compte ? window.Compte.role() : '';
    var connecte = C && C.lie() && C.actif();
    var ok = niveau === 'superadmin' || (niveau === 'admin' && exige === 'admin');
    if (connecte && ok) return montrer();
    porte.hidden = false; main.hidden = true; zone.hidden = false;
    if (!connecte) zone.innerHTML = '<p class="sous">Connectez-vous avec votre compte Google pour accéder à cet espace.</p>' + bouton;
    else if (!niveau) zone.innerHTML = '<p class="sous" role="status">Vérification de votre niveau…</p>';
    else zone.innerHTML = '<p class="sous" role="status">Ce compte n\'a pas les droits nécessaires pour cette page. Demandez-les à la personne qui gère le site.</p>';
  }
  function demarrer() {
    if (!window.Identite) { zone.hidden = false; zone.innerHTML = '<p class="sous">L\'espace administrateur est momentanément indisponible.</p>'; return; }
    window.Identite.config().then(function (c) {
      if (!c || !c.relais_url) { zone.hidden = false; zone.innerHTML = '<p class="sous">L\'espace administrateur est momentanément indisponible.</p>'; return; }
      document.addEventListener('cdh-compte', evaluer);
      evaluer();
    });
  }
  demarrer();
})();
