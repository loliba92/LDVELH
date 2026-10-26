/* Ajouter des livres : sorciers et Zagors. La liste part au relais (action ajout_livres), qui vérifie le niveau et le quota.
   Le scanner ajoute chaque ISBN lu à la liste ; on peut aussi coller les ISBN à la main. */
(function () {
  var $ = function (s) { return document.querySelector(s); };
  var texte = $('#aj-texte'), compte = $('#aj-compte'), msg = $('#aj-msg'), envoyer = $('#aj-envoyer'), scan = $('#aj-scan');
  if (!texte) return;

  // Un ISBN-13 valide commence par 978 ou 979 et a une clé de contrôle juste (même règle que scan.js)
  function isbnValide(c) {
    var n = String(c || '').replace(/\D/g, '');
    if (n.length !== 13 || !/^97[89]/.test(n)) return null;
    var somme = 0;
    for (var i = 0; i < 12; i += 1) somme += Number(n[i]) * (i % 2 ? 3 : 1);
    return (10 - (somme % 10)) % 10 === Number(n[12]) ? n : null;
  }
  function lignes() { return texte.value.split('\n').map(function (x) { return x.trim(); }).filter(function (x) { return x; }); }
  function majCompte() { compte.textContent = lignes().length + ' ISBN'; }
  function dire(t) { msg.textContent = t; msg.hidden = false; }
  function ajouter(isbn) {
    if (lignes().indexOf(isbn) >= 0) return false;
    texte.value = (texte.value.trim() ? texte.value.trim() + '\n' : '') + isbn + '\n';
    majCompte();
    return true;
  }

  texte.addEventListener('input', majCompte);
  scan.addEventListener('click', function () {
    if (!window.Scan) return dire('Le lecteur de codes-barres n\'est pas disponible sur cet appareil.');
    window.Scan.scanner(function (lu) {
      var n = isbnValide(lu);
      if (!n) return dire('Code non reconnu : ' + lu);
      dire(ajouter(n) ? 'Ajouté : ' + n : 'Déjà dans la liste : ' + n);
    }, {});
  });

  envoyer.addEventListener('click', function () {
    var l = lignes();
    if (!l.length) return dire('La liste est vide.');
    if (!window.Relais || !window.Relais.actif()) return dire('Votre connexion a expiré : reconnectez-vous avec le bouton du compte, en haut de la page.');
    envoyer.disabled = true; dire('Envoi en cours…');
    window.Relais.appeler('ajout_livres', { liste: l.join(' | ') }).then(function (r) {
      if (r && r.ok) { texte.value = ''; majCompte(); dire('Envoyé : ' + r.nombre + ' ISBN. Les livres apparaissent sur le site dans environ deux minutes.'); }
      else dire((r && r.erreur) || 'Envoi refusé.');
    }).catch(function () { dire('Le service ne répond pas : vérifiez votre connexion.'); }).then(function () { envoyer.disabled = false; });
  });
  majCompte();
})();
