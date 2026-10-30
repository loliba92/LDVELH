/* Ajouter des livres : niveaux 2 et 3. La liste part au relais (action ajout_livres), qui vérifie le niveau et le quota.
   Le scanner ajoute chaque ISBN lu à la liste ; on peut aussi coller les ISBN à la main.
   « Vérifier la liste » contrôle la liste avant l'envoi ; l'envoi refait le même contrôle. */
(function () {
  var $ = function (s) { return document.querySelector(s); };
  var texte = $('#aj-texte'), compte = $('#aj-compte'), msg = $('#aj-msg'), envoyer = $('#aj-envoyer'), verifier = $('#aj-verifier'), verif = $('#aj-verif');
  if (!texte) return;

  // Un ISBN-13 valide commence par 978 ou 979 et a une clé de contrôle juste (même règle que scan.js)
  function isbnValide(c) {
    var n = String(c || '').replace(/\D/g, '');
    if (n.length !== 13 || !/^97[89]/.test(n)) return null;
    var somme = 0;
    for (var i = 0; i < 12; i += 1) somme += Number(n[i]) * (i % 2 ? 3 : 1);
    return (10 - (somme % 10)) % 10 === Number(n[12]) ? n : null;
  }
  // Une ligne peut porter « ISBN ; série ; numéro ; titre » : seul l'ISBN compte ici
  function isbnDe(ligne) { return ligne.split(';')[0].trim(); }
  function lignes() { return texte.value.split('\n').map(function (x) { return x.trim(); }).filter(function (x) { return x; }); }
  function majCompte() { compte.textContent = lignes().length + ' ISBN'; }
  function dire(t) { msg.textContent = t; msg.hidden = false; }
  function echapper(t) { return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  // Livres déjà au guide : versions.json, chargé une seule fois. Sans lui, le contrôle ne signale que les erreurs de saisie.
  var connus = null;
  function connusDuGuide() {
    if (connus) return Promise.resolve(connus);
    return fetch('data/versions.json').then(function (r) { return r.json(); }).then(function (d) {
      connus = {};
      d.forEach(function (v) { if (v.isbn13) connus[v.isbn13] = v.titre || 'titre inconnu'; });
      return connus;
    }).catch(function () { return {}; });
  }
  function controler(l) {
    return connusDuGuide().then(function (deja) {
      var vus = {};
      return l.map(function (ligne) {
        var isbn = isbnValide(isbnDe(ligne));
        if (!isbn) return { ligne: ligne, statut: 'invalide' };
        if (vus[isbn]) return { ligne: ligne, isbn: isbn, statut: 'doublon' };
        vus[isbn] = true;
        if (deja[isbn]) return { ligne: ligne, isbn: isbn, statut: 'connu', titre: deja[isbn] };
        return { ligne: ligne, isbn: isbn, statut: 'nouveau' };
      });
    });
  }
  var LIBELLE = { invalide: 'Clé de contrôle fausse : ISBN invalide', doublon: 'Déjà dans la liste', nouveau: 'Nouveau' };
  function afficher(res) {
    verif.innerHTML = res.map(function (r) {
      var quoi = r.statut === 'connu' ? 'Déjà au guide : ' + r.titre : LIBELLE[r.statut];
      var classe = r.statut === 'nouveau' ? ' class="aj-nouveau"' : r.statut === 'invalide' ? ' class="aj-invalide"' : '';
      return '<li' + classe + '><strong>' + echapper(r.isbn || r.ligne) + '</strong><span>' + echapper(quoi) + '</span></li>';
    }).join('');
    verif.hidden = !res.length;
  }
  function bilan(res) {
    var nb = function (s) { return res.filter(function (r) { return r.statut === s; }).length; };
    return nb('nouveau') + ' nouveau(x), ' + nb('connu') + ' déjà au guide, ' + nb('doublon') + ' doublon(s), ' + nb('invalide') + ' invalide(s).';
  }

  texte.addEventListener('input', function () { majCompte(); verif.hidden = true; });
  verifier.addEventListener('click', function () {
    var l = lignes();
    if (!l.length) return dire('La liste est vide.');
    dire('Contrôle de la liste…');
    controler(l).then(function (res) {
      afficher(res);
      dire(bilan(res) + (res.some(function (r) { return r.statut === 'invalide' || r.statut === 'doublon'; }) ? ' Corrigez les lignes marquées avant d\'envoyer.' : ''));
    });
  });
  envoyer.addEventListener('click', function () {
    var l = lignes();
    if (!l.length) return dire('La liste est vide.');
    if (l.length > 20) return dire('Un envoi compte au plus 20 ISBN. Retirez-en ' + (l.length - 20) + ' avant d\'envoyer.');
    if (!window.Relais || !window.Relais.actif()) return dire('Votre connexion a expiré : reconnectez-vous avec le bouton du compte, en haut de la page.');
    envoyer.disabled = true; dire('Contrôle de la liste…');
    controler(l).then(function (res) {
      afficher(res);
      if (res.some(function (r) { return r.statut === 'invalide' || r.statut === 'doublon'; })) {
        envoyer.disabled = false;
        return dire('Corrigez les lignes marquées avant d\'envoyer.');
      }
      dire('Envoi en cours…');
      return window.Relais.appeler('ajout_livres', { liste: l.join(' | ') }).then(function (r) {
        if (r && r.ok) { texte.value = ''; majCompte(); verif.hidden = true; dire('Envoyé : ' + r.nombre + ' ISBN. Les livres apparaissent sur le site dans environ deux minutes.'); }
        else dire((r && r.erreur) || 'Envoi refusé.');
      }).catch(function () { dire('Le service ne répond pas : vérifiez votre connexion.'); }).then(function () { envoyer.disabled = false; });
    });
  });
  majCompte();
})();
