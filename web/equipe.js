/* Page « Équipe » (niveau 3) : ajouter, retirer ou bloquer des niveau 2, par le service technique (voir service technique/).
   Le relais vérifie à chaque demande que la personne est niveau 3 ; cette page n'est qu'une commande à distance. */
(function () {
  var $ = function (s) { return document.querySelector(s); };
  var esc = function (t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var NIVEAU = { admin: 'Accès', superadmin: 'Accès complet' };
  var etat = $('#eq-etat'), msg = $('#eq-msg');
  var dire = function (t, erreur) { msg.textContent = t; msg.hidden = false; msg.classList.toggle('erreur', !!erreur); };

  function erreurLisible(r) {
    var e = (r && r.erreur) || 'erreur inconnue';
    return e === 'droits insuffisants' ? 'Ce compte n\'a pas accès à cette page.' : /expir|jeton/.test(e) ? 'La connexion a expiré : reconnectez-vous avec le bouton du compte.' : e.charAt(0).toUpperCase() + e.slice(1) + '.';
  }

  function dessiner(r) {
    var liste = $('#eq-liste');
    liste.innerHTML = r.equipe.length ? r.equipe.map(function (m) {
      return '<li class="eq-membre"><div><strong>' + esc(m.nom) + '</strong> <span class="compte-niveau">' + esc(NIVEAU[m.role] || m.role) + '</span>' +
        '<span class="sous eq-empreinte">empreinte ' + esc(m.empreinte.slice(7, 15)) + '…</span></div>' +
        (m.role === 'superadmin' ? '<p class="sous">Protégé : ce compte ne peut être ni retiré ni bloqué.</p>' :
          '<div class="eq-actions"><button type="button" class="bouton bouton-clair" data-act="equipe_retirer" data-e="' + esc(m.empreinte) + '">Retirer</button>' +
          '<button type="button" class="bouton bouton-clair" data-act="equipe_bloquer" data-e="' + esc(m.empreinte) + '">Bloquer</button></div>') + '</li>';
    }).join('') : '<li class="sous">Aucun membre.</li>';
    var n = r.bloques.length;
    $('#eq-bloques').textContent = n ? n + ' compte' + (n > 1 ? 's' : '') + ' bloqué' + (n > 1 ? 's' : '') + '. Pour en débloquer un, ajoutez de nouveau son adresse à l\'équipe.' : 'Aucun compte bloqué.';
    etat.textContent = r.equipe.length + ' membre' + (r.equipe.length > 1 ? 's' : '') + ' dans l\'équipe.';
  }

  function comptes() {
    var etatC = $('#eq-comptes-etat'), ul = $('#eq-comptes');
    if (!etatC) return;
    window.Relais.appeler('comptes_lire').then(function (r) {
      if (!r || !r.ok) { etatC.textContent = /action inconnue/.test((r && r.erreur) || '') ? 'Mettez à jour le relais (relais/Code.gs) pour voir les comptes.' : erreurLisible(r); return; }
      var sans = Math.max(0, r.total - r.connus);
      etatC.textContent = r.total + ' compte' + (r.total > 1 ? 's' : '') + ', dont ' + r.aujourdhui + ' arrivé' + (r.aujourdhui > 1 ? 's' : '') + ' aujourd\'hui.' +
        (sans ? ' Les ' + sans + ' premiers comptes sont arrivés avant la liste : leurs prénoms ne sont pas gardés.' : '');
      ul.innerHTML = r.liste.length ? r.liste.map(function (c) {
        return '<li class="eq-membre"><div><strong>' + esc(c.nom) + '</strong> <span class="sous">· ' + esc(c.date ? new Date(c.date + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' }) : '') + ' · compte n° ' + esc(c.rang) + '</span></div></li>';
      }).join('') : '<li class="sous">Aucun prénom enregistré pour l\'instant : la liste se remplit à chaque nouveau compte.</li>';
    }).catch(function () { etatC.textContent = 'Le relais ne répond pas : vérifiez votre connexion.'; });
  }

  function charger() {
    comptes();
    etat.textContent = 'Chargement…';
    window.Relais.appeler('equipe_lire').then(function (r) {
      if (!r || !r.ok) { etat.textContent = erreurLisible(r); return; }
      dessiner(r);
    }).catch(function () { etat.textContent = 'Le relais ne répond pas : vérifiez votre connexion.'; });
  }

  $('#eq-ajout').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var adresse = $('#eq-adresse').value.trim(), nom = $('#eq-nom').value.trim(), role = $('#eq-niveau').value;
    dire('Enregistrement…');
    window.Relais.appeler('equipe_ajouter', { adresse: adresse, nom: nom, role: role }).then(function (r) {
      if (!r || !r.ok) return dire(erreurLisible(r), true);
      dire(nom + ' fait maintenant partie de l\'équipe (' + (NIVEAU[role] || role) + ').');
      $('#eq-adresse').value = ''; $('#eq-nom').value = '';
      charger();
    }).catch(function () { dire('Le relais ne répond pas : vérifiez votre connexion.', true); });
  });

  $('#eq-liste').addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-act]');
    if (!b) return;
    var bloquer = b.dataset.act === 'equipe_bloquer';
    if (!window.confirm(bloquer ? 'Bloquer ce compte ? Il sera retiré de l\'équipe et ne pourra plus rien envoyer, même s\'il redevient Héros.' : 'Retirer cette personne de l\'équipe ? Elle redeviendra Héros.')) return;
    dire('Enregistrement…');
    window.Relais.appeler(b.dataset.act, { empreinte: b.dataset.e }).then(function (r) {
      if (!r || !r.ok) return dire(erreurLisible(r), true);
      dire(bloquer ? 'Compte bloqué.' : 'Personne retirée de l\'équipe.');
      charger();
    }).catch(function () { dire('Le relais ne répond pas : vérifiez votre connexion.', true); });
  });

  // La porte ouvre la page une fois le niveau niveau 3 confirmé par le service technique
  document.addEventListener('cdh-porte-ouverte', charger);
  if (!document.getElementById('main').hidden) charger();
})();
