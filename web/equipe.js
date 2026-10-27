/* Page « Équipe » (niveau 3) : les Zagors, les sorciers (avec une date de fin possible) et les héros, par le service technique (voir relais/).
   Le relais vérifie à chaque demande que la personne est niveau 3 ; cette page n'est qu'une commande à distance. */
(function () {
  var $ = function (s) { return document.querySelector(s); };
  var esc = function (t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var ICONES = {
    heros: '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/>',
    admin: '<path d="M5 19L15 9"/><path d="M16 3l1 2.5L19.5 7 17 8l-1 2.5L15 8l-2.5-1L15 5.5z"/>',
    superadmin: '<path d="M3 8l4 4 5-7 5 7 4-4-2 11H5z"/>'
  };
  var NOMS = { heros: 'Héros', admin: 'Sorcier', superadmin: 'Zagor' };
  var etat = $('#eq-etat'), msg = $('#eq-msg'), TOTAL = null, EQUIPE = null;
  var dire = function (t, erreur) { msg.textContent = t; msg.hidden = false; msg.classList.toggle('erreur', !!erreur); };
  var icone = function (r) { return '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONES[r] + '</svg>'; };
  var jour = function (d) { return new Date(d + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }); };

  function erreurLisible(r) {
    var e = (r && r.erreur) || 'erreur inconnue';
    return e === 'droits insuffisants' ? 'Ce compte n\'a pas accès à cette page.' : /expir|jeton/.test(e) ? 'La connexion a expiré : reconnectez-vous avec le bouton du compte.' : /action inconnue/.test(e) ? 'Mettez à jour le relais (relais/Code.gs et logique.gs) : cette action n\'existe pas encore.' : e.charAt(0).toUpperCase() + e.slice(1) + '.';
  }

  function tuiles() {
    if (!EQUIPE) return;
    var zagors = EQUIPE.equipe.filter(function (m) { return m.role === 'superadmin'; }).length;
    var sorciers = EQUIPE.equipe.filter(function (m) { return m.role === 'admin' && !m.echu && !m.avenir; }).length;
    var heros = TOTAL == null ? null : Math.max(0, TOTAL - zagors - sorciers);
    var t = $('#eq-tuiles');
    t.innerHTML = [['superadmin', zagors, 'Zagor' + (zagors > 1 ? 's' : '')], ['admin', sorciers, 'Sorcier' + (sorciers > 1 ? 's' : '')], ['heros', heros, 'Héros']].map(function (x) {
      return '<div class="eq-tuile niveau-' + x[0] + '">' + icone(x[0]) + '<strong>' + (x[1] == null ? '…' : x[1]) + '</strong><span>' + x[2] + '</span></div>';
    }).join('');
    t.hidden = false;
  }

  function carte(m) {
    var infos = [];
    if (m.depuis) infos.push('depuis le ' + jour(m.depuis));
    var fin = '';
    if (m.role === 'admin') {
      var periode = m.debut && m.fin ? 'Du ' + jour(m.debut) + ' au ' + jour(m.fin) : m.debut ? 'À partir du ' + jour(m.debut) : m.fin ? 'Jusqu\'au ' + jour(m.fin) : 'Sans date de début ni de fin';
      fin = m.echu ? '<span class="eq-fin eq-fin-passee">Terminé le ' + esc(jour(m.fin)) + ' : redevenu Héros</span>'
        : m.avenir ? '<span class="eq-fin eq-fin-passee">Commence le ' + esc(jour(m.debut)) + ' (Héros d\'ici là)</span>'
        : '<span class="eq-fin">' + esc(periode) + '</span>';
    }
    var actions = m.role === 'superadmin' ? '<p class="sous">Protégé : ni retiré ni bloqué.</p>' :
      '<form class="eq-fin-form" data-e="' + esc(m.empreinte) + '"><label>Début <input type="date" name="debut" value="' + esc(m.debut || '') + '"></label><label>Fin <input type="date" name="fin" value="' + esc(m.fin || '') + '"></label>' +
      '<button type="submit" class="bouton bouton-clair">Enregistrer</button></form>' +
      '<div class="eq-actions"><button type="button" class="bouton bouton-clair" data-act="equipe_retirer" data-e="' + esc(m.empreinte) + '">Retirer</button>' +
      '<button type="button" class="bouton bouton-clair" data-act="equipe_bloquer" data-e="' + esc(m.empreinte) + '">Bloquer</button></div>';
    return '<li class="eq-membre eq-carte"><div class="eq-profil"><span class="eq-avatar niveau-' + ((m.echu || m.avenir) ? 'heros' : m.role) + '">' + icone((m.echu || m.avenir) ? 'heros' : m.role) + '</span>' +
      '<div><strong>' + esc(m.nom) + '</strong> <span class="compte-niveau niveau-' + m.role + '">' + NOMS[m.role] + '</span>' +
      (fin ? '<div>' + fin + '</div>' : '') + (infos.length ? '<span class="sous">' + esc(infos.join(' · ')) + '</span>' : '') +
      '<span class="sous eq-empreinte">empreinte ' + esc(m.empreinte.slice(7, 15)) + '…</span></div></div>' + actions + '</li>';
  }

  function dessiner(r) {
    EQUIPE = r;
    var z = r.equipe.filter(function (m) { return m.role === 'superadmin'; }), s = r.equipe.filter(function (m) { return m.role === 'admin'; });
    s.sort(function (a, b) { return ((a.echu ? 1 : 0) + (a.avenir ? 1 : 0)) - ((b.echu ? 1 : 0) + (b.avenir ? 1 : 0)); });
    $('#eq-zagors').innerHTML = z.length ? z.map(carte).join('') : '<li class="sous">Aucun Zagor.</li>';
    $('#eq-sorciers').innerHTML = s.length ? s.map(carte).join('') : '<li class="sous">Aucun sorcier pour l\'instant.</li>';
    var n = r.bloques.length;
    $('#eq-bloques').textContent = n ? n + ' compte' + (n > 1 ? 's' : '') + ' bloqué' + (n > 1 ? 's' : '') + '. Pour en débloquer un, ajoutez de nouveau son adresse.' : 'Aucun compte bloqué.';
    etat.textContent = z.length + ' Zagor' + (z.length > 1 ? 's' : '') + ', ' + s.length + ' sorcier' + (s.length > 1 ? 's' : '') + '.';
    tuiles();
  }

  function comptes() {
    var etatC = $('#eq-comptes-etat'), ul = $('#eq-comptes');
    window.Relais.appeler('comptes_lire').then(function (r) {
      if (!r || !r.ok) { etatC.textContent = erreurLisible(r); return; }
      TOTAL = r.total; tuiles();
      var sans = Math.max(0, r.total - r.connus);
      etatC.textContent = r.total + ' compte' + (r.total > 1 ? 's' : '') + ' au total (héros, sorciers et Zagors), dont ' + r.aujourdhui + ' arrivé' + (r.aujourdhui > 1 ? 's' : '') + ' aujourd\'hui. Derniers arrivés :' +
        (sans ? ' (les ' + sans + ' premiers n\'ont pas de prénom gardé)' : '');
      ul.innerHTML = r.liste.length ? r.liste.map(function (c) {
        return '<li class="eq-membre"><div class="eq-profil"><span class="eq-avatar niveau-heros">' + icone('heros') + '</span><div><strong>' + esc(c.nom) + '</strong><span class="sous eq-date">' + esc(c.date ? new Date(c.date + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' }) : '') + ' · compte n° ' + esc(c.rang) + '</span></div></div></li>';
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

  function champFin() { $('#eq-fin-champ').hidden = $('#eq-niveau').value !== 'admin'; }
  $('#eq-niveau').addEventListener('change', champFin); champFin();

  $('#eq-ajout').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var adresse = $('#eq-adresse').value.trim(), nom = $('#eq-nom').value.trim(), role = $('#eq-niveau').value, fin = role === 'admin' ? $('#eq-fin').value : '', debut = role === 'admin' ? $('#eq-debut').value : '';
    dire('Enregistrement…');
    window.Relais.appeler('equipe_ajouter', { adresse: adresse, nom: nom, role: role, debut: debut, fin: fin }).then(function (r) {
      if (!r || !r.ok) return dire(erreurLisible(r), true);
      dire(nom + ' : ' + NOMS[role] + (debut ? ', à partir du ' + jour(debut) : '') + (fin ? ', jusqu\'au ' + jour(fin) : '') + '.');
      $('#eq-adresse').value = ''; $('#eq-nom').value = ''; $('#eq-fin').value = ''; $('#eq-debut').value = '';
      charger();
    }).catch(function () { dire('Le relais ne répond pas : vérifiez votre connexion.', true); });
  });

  function actions(ev) {
    var b = ev.target.closest('[data-act]');
    if (!b) return;
    var bloquer = b.dataset.act === 'equipe_bloquer';
    if (!window.confirm(bloquer ? 'Bloquer ce compte ? Il sera retiré de l\'équipe et ne pourra plus rien envoyer, même comme Héros.' : 'Retirer cette personne ? Elle redeviendra Héros.')) return;
    dire('Enregistrement…');
    window.Relais.appeler(b.dataset.act, { empreinte: b.dataset.e }).then(function (r) {
      if (!r || !r.ok) return dire(erreurLisible(r), true);
      dire(bloquer ? 'Compte bloqué.' : 'Personne retirée.');
      charger();
    }).catch(function () { dire('Le relais ne répond pas : vérifiez votre connexion.', true); });
  }
  function nouvelleFin(ev) {
    var f = ev.target.closest('.eq-fin-form');
    if (!f) return;
    ev.preventDefault();
    dire('Enregistrement…');
    window.Relais.appeler('equipe_periode', { empreinte: f.dataset.e, debut: f.elements.debut.value, fin: f.elements.fin.value }).then(function (r) {
      if (!r || !r.ok) return dire(erreurLisible(r), true);
      dire('Dates enregistrées.');
      charger();
    }).catch(function () { dire('Le relais ne répond pas : vérifiez votre connexion.', true); });
  }
  ['#eq-zagors', '#eq-sorciers'].forEach(function (s) { $(s).addEventListener('click', actions); $(s).addEventListener('submit', nouvelleFin); });

  // La porte ouvre la page une fois le niveau niveau 3 confirmé par le service technique
  document.addEventListener('cdh-porte-ouverte', charger);
  if (!document.getElementById('main').hidden) charger();
})();
