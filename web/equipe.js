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
    var etatTexte = '', hors = m.echu || m.avenir;
    if (m.role === 'admin') {
      var periode = m.debut && m.fin ? jour(m.debut) + ' → ' + jour(m.fin) : m.debut ? 'dès le ' + jour(m.debut) : m.fin ? 'jusqu\'au ' + jour(m.fin) : 'sans limite';
      etatTexte = m.echu ? 'Terminé le ' + jour(m.fin) + ' : redevenu Héros' : m.avenir ? 'Commence le ' + jour(m.debut) + ' (Héros d\'ici là)' : periode;
    } else etatTexte = 'protégé';
    var bouton = m.role === 'superadmin' ? '' : '<button type="button" class="eq-btn-gerer" data-gerer aria-expanded="false">Gérer</button>';
    var corps = m.role === 'superadmin' ? '' :
      '<div class="eq-corps" hidden>' +
      '<form class="eq-fin-form" data-e="' + esc(m.empreinte) + '"><label>Début <input type="date" name="debut" value="' + esc(m.debut || '') + '"></label><label>Fin <input type="date" name="fin" value="' + esc(m.fin || '') + '"></label>' +
      '<button type="submit" class="bouton bouton-clair">Enregistrer</button></form>' +
      '<div class="eq-actions"><button type="button" class="bouton bouton-clair" data-act="equipe_retirer" data-e="' + esc(m.empreinte) + '">Retirer</button>' +
      '<button type="button" class="bouton bouton-clair" data-act="equipe_bloquer" data-e="' + esc(m.empreinte) + '">Bloquer</button></div>' +
      '<span class="sous eq-empreinte">empreinte ' + esc(m.empreinte.slice(7, 15)) + '…</span></div>';
    return '<li class="eq-ligne"><div class="eq-haut"><span class="eq-avatar niveau-' + (hors ? 'heros' : m.role) + '">' + icone(hors ? 'heros' : m.role) + '</span>' +
      '<div class="eq-texte"><strong>' + esc(m.nom) + '</strong> <span class="compte-niveau niveau-' + m.role + '">' + NOMS[m.role] + '</span>' +
      '<span class="eq-fin' + (hors ? ' eq-fin-passee' : '') + '">' + esc(etatTexte) + '</span></div>' + bouton + '</div>' + corps + '</li>';
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
      etatC.textContent = r.total + ' compte' + (r.total > 1 ? 's' : '') + ' (équipe comprise), dont ' + r.aujourdhui + ' aujourd\'hui. Derniers arrivés' + (sans ? ' (les ' + sans + ' premiers sans prénom)' : '') + ' :';
      ul.innerHTML = r.liste.length ? r.liste.map(function (c) {
        return '<li class="eq-heros"><strong>' + esc(c.nom) + '</strong><span class="sous">' + esc(c.date ? new Date(c.date + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }) : '') + ' · n° ' + esc(c.rang) + '</span></li>';
      }).join('') : '<li class="sous">Aucun prénom enregistré pour l\'instant.</li>';
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
      setTimeout(charger, 2500);                              // laisse à GitHub le temps de servir la nouvelle liste
    }).catch(function () { dire('Le relais ne répond pas : vérifiez votre connexion.', true); });
  });

  function actions(ev) {
    var g = ev.target.closest('[data-gerer]');
    if (g) {
      var corps = g.closest('.eq-ligne').querySelector('.eq-corps'), ouvre = corps.hidden;
      corps.hidden = !ouvre; g.setAttribute('aria-expanded', ouvre ? 'true' : 'false'); g.textContent = ouvre ? 'Fermer' : 'Gérer';
      return;
    }
    var b = ev.target.closest('[data-act]');
    if (!b) return;
    var bloquer = b.dataset.act === 'equipe_bloquer';
    if (!window.confirm(bloquer ? 'Bloquer ce compte ? Il sera retiré de l\'équipe et ne pourra plus rien envoyer, même comme Héros.' : 'Retirer cette personne ? Elle redeviendra Héros.')) return;
    dire('Enregistrement…');
    window.Relais.appeler(b.dataset.act, { empreinte: b.dataset.e }).then(function (r) {
      if (!r || !r.ok) return dire(erreurLisible(r), true);
      dire(bloquer ? 'Compte bloqué.' : 'Personne retirée.');
      EQUIPE.equipe = EQUIPE.equipe.filter(function (x) { return x.empreinte !== b.dataset.e; });
      if (bloquer) EQUIPE.bloques.push(b.dataset.e);
      dessiner(EQUIPE);
    }).catch(function () { dire('Le relais ne répond pas : vérifiez votre connexion.', true); });
  }
  function nouvelleFin(ev) {
    var f = ev.target.closest('.eq-fin-form');
    if (!f) return;
    ev.preventDefault();
    var debut = f.elements.debut.value, fin = f.elements.fin.value;
    dire('Enregistrement…');
    window.Relais.appeler('equipe_periode', { empreinte: f.dataset.e, debut: debut, fin: fin }).then(function (r) {
      if (!r || !r.ok) return dire(erreurLisible(r), true);
      var m = EQUIPE.equipe.filter(function (x) { return x.empreinte === f.dataset.e; })[0];
      if (m) { m.debut = debut; m.fin = fin; m.echu = !!fin && fin < EQUIPE.aujourdhui; m.avenir = !!debut && debut > EQUIPE.aujourdhui; }
      dessiner(EQUIPE);                                      // affichage tout de suite, sans relire : GitHub peut renvoyer l'ancienne liste pendant quelques secondes
      dire('Dates enregistrées.');
    }).catch(function () { dire('Le relais ne répond pas : vérifiez votre connexion.', true); });
  }
  ['#eq-zagors', '#eq-sorciers'].forEach(function (s) { $(s).addEventListener('click', actions); $(s).addEventListener('submit', nouvelleFin); });

  // La porte ouvre la page une fois le niveau niveau 3 confirmé par le service technique
  document.addEventListener('cdh-porte-ouverte', charger);
  if (!document.getElementById('main').hidden) charger();
})();
