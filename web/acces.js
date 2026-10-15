/* Porte d'accès de la page « Vérifier les prix » (même principe que le tableau de bord de Scénario).
   Le code saisi est comparé à une empreinte SHA-256 : le mot de passe n'est écrit nulle part dans le dépôt.
   Protection légère : la page est statique, son contenu reste dans le code envoyé au navigateur. Elle écarte
   le passage par curiosité, pas une lecture déterminée du code source. */
(function () {
  var HASH = '84542babc81672662f9b777a4bde6f7b72518fdb1e8bb704437a4fa4e6d34b4e';
  var CLE = 'cdh-acces';
  var porte = document.getElementById('porte');
  var main = document.getElementById('main');
  if (!porte || !main) return;

  function ouvrir() { porte.hidden = true; main.hidden = false; }

  try { if (localStorage.getItem(CLE) === HASH) ouvrir(); } catch (e) {}

  function sha256(texte) {
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(texte)).then(function (b) {
      return Array.from(new Uint8Array(b)).map(function (o) { return o.toString(16).padStart(2, '0'); }).join('');
    });
  }

  document.getElementById('porte-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var erreur = document.getElementById('porte-erreur');
    sha256(document.getElementById('porte-code').value).then(function (h) {
      if (h === HASH) {
        try { localStorage.setItem(CLE, HASH); } catch (e) {}
        ouvrir();
      } else {
        erreur.hidden = false;
      }
    });
  });
})();
