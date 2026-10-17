/* Porte d'accès de la page « Vérifier les prix » : un seul mot de passe.
   Il ouvre la page et déchiffre la clé d'envoi publiée (data/coffre.json, voir coffre.js), qui est alors enregistrée
   sur cet appareil. Le mot de passe n'est écrit nulle part ; une saisie fausse ne déchiffre rien.
   Tant que data/coffre.json n'existe pas, l'ancienne comparaison d'empreinte reste en place.
   Protection légère : la page est statique, son contenu reste dans le code envoyé au navigateur. Elle écarte
   le passage par curiosité, pas une lecture déterminée du code source. */
(function () {
  var HASH = '84542babc81672662f9b777a4bde6f7b72518fdb1e8bb704437a4fa4e6d34b4e';
  var CLE = 'cdh-acces', CLE_JETON = 'cdh-jeton', CLE_REV = 'cdh-coffre-rev';
  var porte = document.getElementById('porte');
  var main = document.getElementById('main');
  if (!porte || !main) return;

  function montrer() { porte.hidden = true; main.hidden = false; }
  // Mot de passe accepté : si le site demande une connexion Google, la page reste fermée jusqu'à ce qu'elle soit faite
  function ouvrir() {
    var I = window.Identite, zone = document.getElementById('porte-google');
    if (!I || !zone) return montrer();
    I.actif().then(function (actif) {
      if (!actif || I.connecte()) return montrer();
      document.getElementById('porte-form').hidden = true;
      var e = document.getElementById('porte-erreur'); e.hidden = true;
      zone.hidden = false;
      I.afficher(zone, function () { if (I.connecte()) montrer(); });
    });
  }
  function lire(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function ecrire(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* stockage indisponible */ } }

  function sha256(texte) {
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(texte)).then(function (b) {
      return Array.from(new Uint8Array(b)).map(function (o) { return o.toString(16).padStart(2, '0'); }).join('');
    });
  }

  // Ancienne porte : mot de passe (clé commune chiffrée) puis connexion Google. Utilisée tant que le relais n'est pas en service.
  function porteAncienne() {
  var coffre = null;
    fetch('data/coffre.json', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (c) {
      coffre = c && c.ct ? c : null;
      var rev = coffre ? coffre.ct.slice(0, 16) : null;
      if (coffre) {
        if (lire(CLE) === 'coffre' && lire(CLE_REV) === rev) ouvrir();
        else if (lire(CLE) === 'coffre') { var e = document.getElementById('porte-erreur'); e.textContent = 'L\'accès a été renouvelé : saisissez à nouveau le mot de passe.'; e.hidden = false; }
      } else if (lire(CLE) === HASH) ouvrir();
    });
  
    document.getElementById('porte-form').addEventListener('submit', function (ev) {
      ev.preventDefault();
      var erreur = document.getElementById('porte-erreur');
      var saisi = document.getElementById('porte-code').value.trim();
      var refus = function () { erreur.textContent = 'Code incorrect.'; erreur.hidden = false; };
      if (coffre) {
        window.Coffre.dechiffrer(saisi, coffre).then(function (jeton) {
          if (jeton === null) return refus();
          ecrire(CLE, 'coffre'); ecrire(CLE_REV, coffre.ct.slice(0, 16)); ecrire(CLE_JETON, jeton);
          ouvrir();
          document.dispatchEvent(new Event('cdh-jeton'));
        });
      } else {
        sha256(document.getElementById('porte-code').value).then(function (h) {
          if (h === HASH) { ecrire(CLE, HASH); ouvrir(); } else refus();
        });
      }
    });
}

  // Porte avec le relais : plus de mot de passe. Le niveau (Admin ou SuperAdmin) vient du relais, après la connexion Google du site.
  function porteRelais() {
    var zone = document.getElementById('porte-google');
    document.getElementById('porte-form').hidden = true;
    zone.hidden = false;
    var bouton = '<button type="button" class="bouton" data-compte="connecter">Se connecter avec Google</button>';
    function evaluer() {
      var C = window.Cloud, niveau = window.Compte ? window.Compte.role() : '';
      var connecte = C && C.lie() && C.actif();
      if (connecte && (niveau === 'admin' || niveau === 'superadmin')) return montrer();
      porte.hidden = false; main.hidden = true;
      if (!connecte) zone.innerHTML = '<p class="sous">Connectez-vous avec votre compte Google pour accéder à l\'espace administrateur.</p>' + bouton;
      else if (!niveau) zone.innerHTML = '<p class="sous" role="status">Vérification de votre niveau…</p>';
      else zone.innerHTML = '<p class="sous" role="status">Ce compte n\'a pas les droits d\'administrateur. Demandez-les à la personne qui gère le site.</p>';
    }
    document.addEventListener('cdh-compte', evaluer);
    evaluer();
  }

  if (window.Identite) window.Identite.config().then(function (c) { if (c && c.relais_url) porteRelais(); else porteAncienne(); });
  else porteAncienne();
})();
