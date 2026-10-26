/* Porte de la page admin : le niveau (Sorcier ou Zagor) vient du relais (voir relais/), après la connexion Google du site.
   Plus de mot de passe. Une page peut exiger un niveau plus élevé avec data-niveau="superadmin" sur <main>.
   Protection légère côté navigateur : la vraie vérification est faite par le relais à chaque envoi. */
(function () {
  var porte = document.getElementById('porte');
  var main = document.getElementById('main');
  if (!porte || !main) return;
  var zone = document.getElementById('porte-google');
  var exige = main.dataset.niveau || 'superadmin';

  function montrer() { porte.hidden = true; main.hidden = false; document.dispatchEvent(new Event('cdh-porte-ouverte')); }
  var bouton = '<button type="button" class="bouton" data-compte="connecter">Se connecter avec Google</button>';
  function evaluer() {
    var C = window.Cloud, niveau = window.Compte ? window.Compte.role() : '';
    var connecte = C && C.lie() && C.actif();
    var ok = niveau === 'superadmin' || (exige === 'heros' && niveau === 'heros');   // « heros » : toute personne connectée
    if (connecte && ok) return montrer();
    porte.hidden = false; main.hidden = true; zone.hidden = false;
    if (!connecte) zone.innerHTML = '<p class="sous">Connectez-vous avec votre compte Google pour ' + (exige === 'heros' ? 'voir cette page.' : 'accéder à cet espace.') + '</p>' + bouton;
    else if (!niveau) {
      var echec = window.Compte && window.Compte.echecRole ? window.Compte.echecRole() : '';
      if (!echec) zone.innerHTML = '<p class="sous" role="status">Vérification de votre niveau…</p>';
      else if (/bloqu/.test(echec)) zone.innerHTML = '<p class="sous" role="status">Ce compte est bloqué. Écrivez-nous depuis la <a href="contact.html">page Contact</a>.</p>';
      else if (/expir|jeton/.test(echec)) zone.innerHTML = '<p class="sous" role="status">Votre connexion a expiré. Reconnectez-vous pour continuer.</p>' + '<button type="button" class="bouton" data-compte="connecter">Reconnecter</button>';
      else zone.innerHTML = '<p class="sous" role="status">Impossible de vérifier votre niveau pour le moment. Vérifiez votre connexion, puis réessayez.</p><button type="button" class="bouton" data-compte="role">Réessayer</button>';
    }
    else zone.innerHTML = '<p class="sous" role="status">Ce compte n\'a pas les droits nécessaires pour cette page. Demandez-les à la personne qui gère le site.</p>';
  }
  function demarrer() {
    if (!window.Identite) { zone.hidden = false; zone.innerHTML = '<p class="sous">L\'espace sorcier est momentanément indisponible.</p>'; return; }
    window.Identite.config().then(function (c) {
      if (!c || !c.relais_url) { zone.hidden = false; zone.innerHTML = '<p class="sous">L\'espace sorcier est momentanément indisponible.</p>'; return; }
      document.addEventListener('cdh-compte', evaluer);
      evaluer();
    });
  }
  demarrer();
})();
