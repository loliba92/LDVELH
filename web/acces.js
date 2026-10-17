/* Porte d'accès de la page « Vérifier les prix » : un seul mot de passe.
   Il ouvre la page et déchiffre la clé d'envoi publiée (data/coffre.json, voir coffre.js), qui est alors enregistrée
   sur cet appareil. Le mot de passe n'est écrit nulle part ; une saisie fausse ne déchiffre rien.
   Tant que data/coffre.json n'existe pas, l'ancienne comparaison d'empreinte reste en place.
   Protection légère : la page est statique, son contenu reste dans le code envoyé au navigateur. Elle écarte
   le passage par curiosité, pas une lecture déterminée du code source. */
(function () {
  var HASH = '84542babc81672662f9b777a4bde6f7b72518fdb1e8bb704437a4fa4e6d34b4e';
  var CLE = 'cdh-acces', CLE_JETON = 'cdh-jeton', CLE_REV = 'cdh-coffre-rev', CLE_NOM = 'cdh-admin-nom';
  var porte = document.getElementById('porte');
  var main = document.getElementById('main');
  if (!porte || !main) return;

  function ouvrir() { porte.hidden = true; main.hidden = false; }
  // Nom d'admin : demandé avec le mot de passe, joint ensuite à chaque mise à jour pour savoir qui l'a faite
  var nomDemande = document.getElementById('porte-nom');
  var codeChamp = document.getElementById('porte-code');
  function nettoyer(n) { return String(n || '').replace(/[|;\s\u0000-\u001f]+/g, ' ').trim().slice(0, 30); }
  var nomConnu = function () { return nettoyer(lire(CLE_NOM)); };
  var seulNom = false;
  nomDemande.value = nomConnu();
  // Appareil déjà ouvert avant l'ajout du nom : on ne redemande pas le mot de passe, seulement le nom
  function ouvrirOuDemanderNom() {
    if (nomConnu()) return ouvrir();
    seulNom = true; codeChamp.hidden = true;
    var e = document.getElementById('porte-erreur'); e.textContent = 'Indiquez votre nom d\'admin : il sera joint à vos mises à jour.'; e.hidden = false;
    nomDemande.focus();
  }
  function lire(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function ecrire(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* stockage indisponible */ } }

  function sha256(texte) {
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(texte)).then(function (b) {
      return Array.from(new Uint8Array(b)).map(function (o) { return o.toString(16).padStart(2, '0'); }).join('');
    });
  }

  var coffre = null;
  fetch('data/coffre.json', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (c) {
    coffre = c && c.ct ? c : null;
    var rev = coffre ? coffre.ct.slice(0, 16) : null;
    if (coffre) {
      if (lire(CLE) === 'coffre' && lire(CLE_REV) === rev) ouvrirOuDemanderNom();
      else if (lire(CLE) === 'coffre') { var e = document.getElementById('porte-erreur'); e.textContent = 'L\'accès a été renouvelé : saisissez à nouveau le mot de passe.'; e.hidden = false; }
    } else if (lire(CLE) === HASH) ouvrirOuDemanderNom();
  });

  document.getElementById('porte-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var erreur = document.getElementById('porte-erreur');
    var saisi = document.getElementById('porte-code').value.trim();
    var refus = function () { erreur.textContent = 'Code incorrect.'; erreur.hidden = false; };
    var nom = nettoyer(nomDemande.value);
    if (nom.length < 2) { erreur.textContent = 'Indiquez votre nom d\'admin (2 lettres au moins).'; erreur.hidden = false; nomDemande.focus(); return; }
    if (seulNom) { ecrire(CLE_NOM, nom); ouvrir(); document.dispatchEvent(new Event('cdh-jeton')); return; }
    if (coffre) {
      window.Coffre.dechiffrer(saisi, coffre).then(function (jeton) {
        if (jeton === null) return refus();
        ecrire(CLE, 'coffre'); ecrire(CLE_REV, coffre.ct.slice(0, 16)); ecrire(CLE_JETON, jeton); ecrire(CLE_NOM, nom);
        ouvrir();
        document.dispatchEvent(new Event('cdh-jeton'));
      });
    } else {
      sha256(document.getElementById('porte-code').value).then(function (h) {
        if (h === HASH) { ecrire(CLE, HASH); ecrire(CLE_NOM, nom); ouvrir(); document.dispatchEvent(new Event('cdh-jeton')); } else refus();
      });
    }
  });
})();
