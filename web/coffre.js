/* Coffre : la clé d'envoi est chiffrée par le mot de passe de la page admin (AES-GCM, clé dérivée par PBKDF2 SHA-256).
   Le texte chiffré est publié dans data/coffre.json ; sans le mot de passe il est illisible. Le déchiffrement se fait
   dans le navigateur : ni le mot de passe ni la clé ne sont envoyés quelque part.
   Ce fichier sert à la fois à la porte (acces.js) et à la page de préparation (coffre.html). */
(function () {
  var ITER = 600000;
  var enc = new TextEncoder(), dec = new TextDecoder();
  function b64(u) { var s = ''; for (var i = 0; i < u.length; i++) s += String.fromCharCode(u[i]); return btoa(s); }
  function unb64(s) { var b = atob(s), u = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }
  function cle(mdp, sel, iter) {
    return crypto.subtle.importKey('raw', enc.encode(mdp), 'PBKDF2', false, ['deriveKey']).then(function (base) {
      return crypto.subtle.deriveKey({ name: 'PBKDF2', salt: sel, iterations: iter, hash: 'SHA-256' }, base, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
    });
  }
  function chiffrer(mdp, texte) {
    var sel = crypto.getRandomValues(new Uint8Array(16)), iv = crypto.getRandomValues(new Uint8Array(12));
    return cle(mdp, sel, ITER).then(function (k) {
      return crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv }, k, enc.encode(texte));
    }).then(function (ct) { return { v: 1, iter: ITER, sel: b64(sel), iv: b64(iv), ct: b64(new Uint8Array(ct)) }; });
  }
  // Rend le texte clair, ou null si le mot de passe est faux (l'authentification AES-GCM échoue).
  function dechiffrer(mdp, blob) {
    return cle(mdp, unb64(blob.sel), blob.iter).then(function (k) {
      return crypto.subtle.decrypt({ name: 'AES-GCM', iv: unb64(blob.iv) }, k, unb64(blob.ct));
    }).then(function (clair) { return dec.decode(clair); }, function () { return null; });
  }
  window.Coffre = { chiffrer: chiffrer, dechiffrer: dechiffrer };

  /* ---- Page de préparation (coffre.html) ---- */
  var form = document.getElementById('cf-form');
  if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  var ALPHA = 'abcdefghjkmnpqrstuvwxyz23456789';
  function proposer() {
    var r = crypto.getRandomValues(new Uint8Array(20)), groupes = [];
    for (var g = 0; g < 4; g++) { var s = ''; for (var i = 0; i < 5; i++) s += ALPHA[r[g * 5 + i] % ALPHA.length]; groupes.push(s); }
    return groupes.join('-');
  }
  $('cf-proposer').addEventListener('click', function () {
    $('cf-mdp').type = 'text'; $('cf-mdp').value = proposer();
    $('cf-etat').textContent = 'Mot de passe proposé : copiez-le tout de suite dans votre gestionnaire de mots de passe, il n\'est enregistré nulle part.';
  });
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var mdp = $('cf-mdp').value.trim(), jeton = $('cf-jeton').value.trim(), etat = $('cf-etat'), sortie = $('cf-sortie');
    sortie.hidden = true; $('cf-copier').hidden = true;
    if (mdp.length < 14) { etat.textContent = 'Mot de passe trop court : 14 caractères au minimum (le texte chiffré est public, seul un mot de passe long résiste aux essais automatiques). Utilisez « Proposer un mot de passe solide ».'; return; }
    if (!jeton) { etat.textContent = 'Collez d\'abord la clé d\'envoi.'; return; }
    etat.textContent = 'Chiffrement en cours…';
    chiffrer(mdp, jeton).then(function (blob) {
      return dechiffrer(mdp, blob).then(function (verif) {
        if (verif !== jeton) throw new Error('verif');
        sortie.value = JSON.stringify(blob); sortie.hidden = false; $('cf-copier').hidden = false;
        $('cf-jeton').value = '';
        etat.textContent = 'Terminé. Le texte ci-dessous est vérifié : il se déchiffre bien avec ce mot de passe. Transmettez-le pour qu\'il soit publié ; il est inutilisable sans le mot de passe.';
      });
    }).catch(function () { etat.textContent = 'Le chiffrement a échoué sur ce navigateur. Essayez avec un navigateur récent.'; });
  });
  $('cf-copier').addEventListener('click', function () {
    var s = $('cf-sortie'); s.select();
    (navigator.clipboard ? navigator.clipboard.writeText(s.value) : Promise.reject()).then(function () { $('cf-etat').textContent = 'Copié.'; }, function () { document.execCommand('copy'); $('cf-etat').textContent = 'Copié.'; });
  });
})();
