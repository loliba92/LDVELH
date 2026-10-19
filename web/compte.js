/* Compte : un seul point d'entrée pour se connecter avec Google, voir l'état de la sauvegarde et, selon son niveau, accéder à l'espace admin.
   Niveaux : visiteur (non connecté), Héros (connecté), Admin, SuperAdmin (le niveau vient du relais, voir relais/).
   Ce fichier ne touche ni à la collection ni aux prix : il s'appuie sur Cloud (connexion, sauvegarde), Relais (niveau) et AppCollection (app.js). */
window.Compte = (function () {
  var CLE_ROLE = 'cdh-role', SAUVE = 'cote-collection-avant-reprise';
  var configure = null, exigeCompte = false, role = '', echecRole = '', intention = null, reprisEnCours = false;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var lireSession = function (k) { try { return sessionStorage.getItem(k) || ''; } catch (e) { return ''; } };
  var ecrireSession = function (k, v) { try { if (v) sessionStorage.setItem(k, v); else sessionStorage.removeItem(k); } catch (e) { /* sans effet */ } };
  var NIVEAUX = { heros: 'Héros', admin: 'Admin', superadmin: 'SuperAdmin' };
  var estAdmin = function () { return role === 'admin' || role === 'superadmin'; };

  /* ---------- État affiché ---------- */
  function etat() {
    if (!window.Cloud || !window.Cloud.lie()) return { cle: 'deconnecte', ligne: 'Non connecté. Consulter les cotes reste libre.' };
    var s = window.Cloud.statut();
    if (!window.Cloud.actif() || s === 'a-reprendre') return { cle: 'reprendre', ligne: 'Votre connexion a expiré. Vos changements sont gardés sur cet appareil.' };
    if (s === 'connecte' && !reprisEnCours && window.Cloud.premiereFois()) return { cle: 'choix', ligne: 'Votre collection n\'est pas encore enregistrée dans votre compte : il reste un choix à faire.' };
    if (s === 'synchro' || s === 'connecte') return { cle: 'synchro', ligne: 'Enregistrement en cours…' };
    if (s === 'erreur') return { cle: 'erreur', ligne: 'La sauvegarde n\'a pas abouti. Vos changements sont gardés ici.' };
    return { cle: 'a-jour', ligne: 'Collection sauvegardée dans votre Google Drive.' };
  }
  var LIBELLE = { deconnecte: 'Se connecter', reprendre: 'Reconnecter', synchro: '', erreur: '', 'a-jour': '' };
  var SILHOUETTE = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8.5" r="3.6"/><path d="M5 20c.8-3.6 3.7-5.5 7-5.5s6.2 1.9 7 5.5"/></svg>';

  function badge() { return estAdmin() ? ' <span class="badge-admin">' + (role === 'superadmin' ? 'SuperAdmin' : 'Admin') + '</span>' : ''; }
  function bloc(e) {   // contenu commun au menu du haut et à la feuille mobile
    var nom = window.Cloud && window.Cloud.nom();
    if (e.cle === 'deconnecte') {
      return '<p class="compte-nom">Votre compte</p><p class="compte-ligne">' + esc(e.ligne) + '</p>' +
        '<button type="button" class="bouton" data-compte="connecter">Se connecter avec Google</button>';
    }
    var h = '<p class="compte-nom">' + esc(nom || 'Compte Google') + badge() + (role && !estAdmin() ? ' <span class="compte-niveau">Héros</span>' : '') + '</p><p class="compte-ligne" role="status">' + esc(e.ligne) + '</p>';
    if (e.cle === 'reprendre') h += '<button type="button" class="bouton" data-compte="connecter">Reconnecter</button>';
    else if (e.cle === 'erreur') h += '<button type="button" class="bouton bouton-clair" data-compte="sync">Réessayer</button>';
    else if (e.cle === 'choix') h += '<button type="button" class="bouton" data-compte="sync">Choisir maintenant</button>';
    h += '<ul class="compte-liste"><li><a href="collection.html">Ma collection</a></li>' +
      (e.cle === 'a-jour' ? '<li><button type="button" class="bouton-lien" data-compte="sync">Synchroniser maintenant</button></li>' : '') +
      (window.Relais && window.Relais.configure() ? '<li><button type="button" class="bouton-lien" data-compte="demande">Demander l\'ajout d\'un livre</button></li>' : '') +
      (window.Relais && window.Relais.configure() ? '<li><button type="button" class="bouton-lien" data-compte="avis">Qu\'en pensez-vous ?</button></li>' : '') +
      (estAdmin() ? '<li><a href="revue-prix.html">Espace administrateur</a></li>' : '') +
      (role === 'superadmin' && window.Compte.avecEquipe ? '<li><a href="equipe.html">Équipe</a></li>' : '') +
      (e.cle === 'a-jour' && exigeCompte ? '<li><button type="button" class="bouton-lien" data-compte="supprimer">Supprimer ma collection du Drive</button></li>' : '') +
      '<li><button type="button" class="bouton-lien" data-compte="deconnecter">Se déconnecter</button></li></ul>';
    return h;
  }

  function dessiner() {
    var e = etat();
    var haut = $('#compte-haut');
    if (haut) {
      var prenom = window.Cloud && window.Cloud.nom();
      var libelle = e.cle === 'deconnecte' || e.cle === 'reprendre' ? LIBELLE[e.cle] : (prenom || 'Compte');
      haut.innerHTML = '<button type="button" class="compte-bouton compte-' + e.cle + '" id="compte-btn" aria-haspopup="menu" aria-expanded="false" aria-controls="compte-menu">' +
        SILHOUETTE + '<span class="compte-libelle">' + esc(libelle) + '</span>' + (estAdmin() ? '<span class="badge-admin">' + (role === 'superadmin' ? 'SuperAdmin' : 'Admin') + '</span>' : '') + '<i class="compte-point" aria-hidden="true"></i></button>' +
        '<div class="compte-menu" id="compte-menu" role="group" aria-label="Mon compte" hidden>' + bloc(e) + '</div>';
    }
    var f = $('#compte-feuille');
    if (f) f.innerHTML = bloc(e);
    var tab = $('[data-plus]');
    if (tab) {                       // onglet du bas : « Compte » (« Reconnexion » si la connexion a expiré)
      var span = tab.querySelector('span');
      if (span) span.textContent = e.cle === 'reprendre' ? 'Reconnexion' : e.cle === 'erreur' ? 'Erreur' : e.cle === 'choix' ? 'À finir' : 'Compte';
      tab.classList.remove('compte-deconnecte', 'compte-reprendre', 'compte-synchro', 'compte-erreur', 'compte-a-jour', 'compte-choix');
      tab.classList.add('compte-' + e.cle);
    }
    var ban = $('#compte-bandeau');
    if (ban) ban.hidden = !(e.cle === 'reprendre' && enCours());
    document.dispatchEvent(new CustomEvent('cdh-compte', { detail: { etat: e.cle, role: role } }));
  }
  // Le bandeau « connexion expirée » n'apparaît que s'il y a des changements pas encore envoyés au Drive
  var enCours = function () { return !!window.AppCollection && window.Cloud.enAttente(window.AppCollection.lire()); };

  function bandeau() {
    if ($('#compte-bandeau')) return;
    var b = document.createElement('div');
    b.id = 'compte-bandeau'; b.className = 'compte-bandeau'; b.hidden = true; b.setAttribute('role', 'status');
    b.innerHTML = '<span>Votre connexion a expiré. Vos changements sont gardés sur cet appareil.</span> <button type="button" class="bouton" data-compte="connecter">Reconnecter</button>';
    var haut = $('.haut'); if (haut) haut.after(b); else document.body.prepend(b);
  }

  /* ---------- Niveau (Héros, Admin, SuperAdmin) ---------- */
  // Premier passage d'un compte : le relais le compte une fois et prévient l'éditeur (prénom et empreinte courte, jamais l'adresse)
  function signalerCompte() {                     // une fois par session : c'est le relais qui reconnaît un compte déjà compté
    if (lireSession('cdh-bienvenue')) return;
    window.Relais.appeler('bienvenue').then(function (r) {
      if (r && r.ok) ecrireSession('cdh-bienvenue', '1');
    }).catch(function () { /* nouvel essai à la prochaine page */ });
  }

  function chargerRole() {
    if (!window.Relais || !window.Relais.configure() || !window.Cloud || !window.Cloud.actif()) return Promise.resolve();
    return window.Relais.appeler('moi').then(function (r) {
      if (r && r.ok) { role = r.role; echecRole = ''; ecrireSession(CLE_ROLE, role); signalerCompte(); }
      else echecRole = (r && r.erreur) || 'inconnu';
    }).catch(function () { echecRole = 'relais'; }).then(dessiner);
  }

  /* ---------- Connexion et première reprise ---------- */
  // Message lu par les lecteurs d'écran (#annonce) et affiché quelques secondes à l'écran
  var minuteToast = null;
  function annoncer(t) {
    var a = $('#annonce'); if (a) { a.textContent = ''; setTimeout(function () { a.textContent = t; }, 30); }
    var z = $('#compte-toast');
    if (!z) { z = document.createElement('div'); z.id = 'compte-toast'; z.className = 'compte-toast'; z.setAttribute('aria-hidden', 'true'); document.body.appendChild(z); }
    z.textContent = t; z.hidden = false;
    clearTimeout(minuteToast); minuteToast = setTimeout(function () { z.hidden = true; }, 6000);
  }

  function connecter() {
    return window.Cloud.connecter().then(function () { dessiner(); return premiereReprise(); }).then(chargerRole).then(function () {
      var suite = intention; intention = null; if (suite) suite();
    }).catch(function (e) {
      annoncer(e && e.message === 'annule' ? 'Connexion annulée. Rien n\'a changé.' : 'La connexion n\'a pas abouti. Rien n\'a changé.');
      dessiner();
    });
  }

  function lire() { return window.AppCollection ? window.AppCollection.lire() : {}; }
  function adopter(c) { if (window.AppCollection) window.AppCollection.adopter(c); }
  function sync(strategie) { return window.Cloud.synchroniser(lire, adopter, strategie); }

  function premiereReprise() {
    if (!window.Cloud.premiereFois() || reprisEnCours) return sync();
    reprisEnCours = true;
    var nl = Object.keys(lire()).length;
    return window.Cloud.apercu().then(function (d) {
      var nd = d ? d.livres : 0;
      if (!nl && !nd) return null;
      try { localStorage.setItem(SAUVE, JSON.stringify(lire())); } catch (e) { /* copie de secours indisponible */ }
      if (!nl) return { strategie: 'fusionner', message: 'Votre collection (' + pluriel(nd) + ') a été chargée.' };
      if (!nd) return dialogueReprise('a', nl, 0);
      return dialogueReprise('b', nl, nd);
    }).then(function (choix) {
      if (!choix) return sync();
      return sync(choix.strategie).then(function () {
        try { localStorage.removeItem(SAUVE); } catch (e) { /* rien à retirer */ }
        annoncer(choix.message || 'Terminé : votre collection est sauvegardée.');
      });
    }).catch(function (e) {
      annoncer(e && e.message === 'reporte'
        ? 'Vous n\'avez pas encore choisi : votre collection n\'est pas encore enregistrée dans votre compte.'
        : 'La reprise n\'a pas abouti : vos livres sont toujours sur cet appareil.');
    }).then(function () { reprisEnCours = false; dessiner(); });
  }

  function dialogue(html, classe) {
    var d = document.createElement('dialog');
    d.className = 'dlg-compte ' + (classe || ''); d.innerHTML = html;
    document.body.appendChild(d);
    d.addEventListener('close', function () { d.remove(); });
    d.showModal();
    return d;
  }
  function pluriel(n) { return n + ' livre' + (n > 1 ? 's' : ''); }
  function dialogueReprise(cas, nl, nd) {
    var nom = window.Cloud.nom();
    return new Promise(function (ok) {
      var h = '<h2>Bienvenue' + (nom ? ', ' + esc(nom) : '') + '</h2>';
      if (cas === 'a') {
        h += '<p>Nous avons trouvé <strong>' + pluriel(nl) + '</strong> sur cet appareil. Voulez-vous les enregistrer dans votre compte ?</p>' +
          '<div class="dlg-actions"><button type="button" class="bouton" data-choix="fusionner" autofocus>Reprendre ma collection</button></div>';
      } else {
        h += '<p>Cet appareil contient <strong>' + pluriel(nl) + '</strong> et votre compte <strong>' + pluriel(nd) + '</strong>. Rien ne sera écrasé sans votre accord.</p>' +
          '<ul class="dlg-choix"><li><button type="button" class="bouton" data-choix="fusionner" autofocus>Fusionner les deux</button><small>On garde le plus récent pour chaque livre.</small></li>' +
          '<li><button type="button" class="bouton bouton-clair" data-choix="compte">Garder celle du compte</button><small>Les livres de cet appareil sont remplacés.</small></li>' +
          '<li><button type="button" class="bouton bouton-clair" data-choix="appareil">Garder celle de cet appareil</button><small>Les livres du compte sont remplacés.</small></li></ul>';
      }
      var d = dialogue(h, 'dlg-reprise'), fait = false;
      d.addEventListener('click', function (e) {
        var c = e.target.closest('[data-choix]'); if (!c) return;
        fait = true; var s = c.dataset.choix; d.close();
        ok({ strategie: s, message: s === 'compte' ? 'Votre collection du compte a remplacé celle de cet appareil.' : s === 'appareil' ? 'Votre collection de cet appareil est maintenant dans votre compte.' : 'Terminé : votre collection est sauvegardée.' });
      });
      d.addEventListener('close', function () { if (!fait) ok(null); });     // fermé sans choisir : rien n'est supprimé, la reprise reviendra
    }).then(function (c) { if (c === null) throw new Error('reporte'); return c; });
  }

  /* ---------- Garde : construire sa collection exige un compte ---------- */
  function actifGoogle() { return exigeCompte === true; }     // la collection exige un compte (drapeau « collection » de admin-config.json)
  function invitation() {
    if ($('.dlg-invitation')) return;
    var d = dialogue('<h2>Connectez-vous pour constituer votre collection</h2>' +
      '<p>Consulter les cotes reste libre. Pour garder vos livres, Google enregistre votre collection dans un espace réservé de votre Drive, que seul ce site peut ouvrir.</p>' +
      '<p class="sous">Nous ne voyons ni votre courriel ni vos autres fichiers. Votre collection est stockée chez vous, dans votre Google Drive, et vous pouvez la supprimer à tout moment.</p>' +
      '<div class="dlg-actions"><button type="button" class="bouton" data-compte="connecter" autofocus>Continuer avec Google</button><button type="button" class="bouton bouton-clair" data-fermer>Plus tard</button></div>', 'dlg-invitation');
    d.addEventListener('click', function (e) { if (e.target.closest('[data-compte="connecter"]') || e.target.closest('[data-fermer]')) d.close(); });
  }
  // Renvoie true si la personne peut modifier sa collection ; sinon ouvre l'invitation et garde l'intention, appliquée après la connexion.
  function exiger(suite) {
    if (!actifGoogle() || window.Cloud.lie()) return true;
    intention = typeof suite === 'function' ? suite : null;
    invitation();
    return false;
  }

  /* ---------- Demande d'ajout d'un livre (Héros) : le relais en fait un signalement que les admins traitent ---------- */
  function demanderLivre(texteInitial) {
    if ($('.dlg-demande')) return;
    if (!actifGoogle() || !window.Cloud.actif()) { intention = function () { demanderLivre(texteInitial); }; if (window.Cloud.lie()) { annoncer('Reconnectez-vous pour demander l\'ajout d\'un livre.'); } invitation(); return; }
    var d = dialogue('<h2>Demander l\'ajout d\'un livre</h2>' +
      '<p>Un livre manque au guide ? Indiquez son titre ou son ISBN. Un administrateur l\'examine, puis l\'ajoute avec sa jaquette.</p>' +
      '<form id="dem-form" class="eq-form"><label for="dem-texte">Titre ou ISBN</label>' +
      '<input id="dem-texte" type="text" maxlength="150" required autocomplete="off" placeholder="978-2380240283 ou un titre">' +
      '<label for="dem-note">Un mot (facultatif) : série, numéro, édition</label>' +
      '<input id="dem-note" type="text" maxlength="300" autocomplete="off" placeholder="Par exemple : édition collector">' +
      '<p class="sous">Votre prénom est joint à la demande, jamais votre adresse. La demande est publique.</p>' +
      '<p class="rv-ajout-bilan" id="dem-msg" role="status" hidden></p>' +
      '<div class="dlg-actions"><button type="submit" class="bouton" autofocus>Envoyer la demande</button><button type="button" class="bouton bouton-clair" data-fermer>Annuler</button></div></form>', 'dlg-demande');
    if (texteInitial) $('#dem-texte', d).value = texteInitial;
    d.addEventListener('click', function (e) { if (e.target.closest('[data-fermer]')) d.close(); });
    $('#dem-form', d).addEventListener('submit', function (ev) {
      ev.preventDefault();
      var msg = $('#dem-msg', d), bouton = d.querySelector('button[type=submit]');
      bouton.disabled = true; msg.hidden = false; msg.textContent = 'Envoi en cours…';
      window.Relais.appeler('demande', { texte: $('#dem-texte', d).value, note: $('#dem-note', d).value }).then(function (r) {
        if (r && r.ok) { d.close(); annoncer('Votre demande est envoyée. Merci !'); return; }
        var e = (r && r.erreur) || 'erreur inconnue';
        msg.textContent = /expir|jeton/.test(e) ? 'Votre connexion a expiré : reconnectez-vous puis réessayez.' : e.charAt(0).toUpperCase() + e.slice(1) + '.';
        bouton.disabled = false;
      }).catch(function () { msg.textContent = 'Le service ne répond pas : vérifiez votre connexion.'; bouton.disabled = false; });
    });
  }

  /* ---------- Qu'en pensez-vous ? Une note de 1 à 5 étoiles et un commentaire facultatif, envoyés par courriel à l'éditeur ---------- */
  function donnerAvis() {
    if ($('.dlg-avis')) return;
    if (!actifGoogle() || !window.Cloud.actif()) { intention = donnerAvis; if (window.Cloud.lie()) { annoncer('Reconnectez-vous pour donner votre avis.'); } invitation(); return; }
    var note = 0;
    var d = dialogue('<h2>Qu\'en pensez-vous ?</h2>' +
      '<p>Ce guide est fait pour les collectionneurs, et votre regard compte beaucoup pour moi. Je reçois chaque avis directement et je le lis moi-même. Dites-moi ce qui vous plaît, ce qui vous manque : c\'est ce qui fait avancer le projet.</p>' +
      '<form id="avis-form" class="eq-form"><span class="avis-label" id="avis-lib">Votre note pour le guide</span>' +
      '<div class="avis-etoiles" role="radiogroup" aria-labelledby="avis-lib">' +
      [1, 2, 3, 4, 5].map(function (n) { return '<button type="button" role="radio" aria-checked="false" data-avis-note="' + n + '" aria-label="' + n + ' sur 5">★</button>'; }).join('') + '</div>' +
      '<label for="avis-texte">Un petit mot (facultatif)</label>' +
      '<textarea id="avis-texte" rows="4" maxlength="1500" placeholder="Ce que vous aimez, ce qui manque, ce qui pourrait être plus simple… Dites-moi tout."></textarea>' +
      '<p class="sous">Votre avis est personnel : il n\'est lu que par moi et jamais publié, ni sur le site ni ailleurs. Je vois votre prénom, jamais votre adresse.</p>' +
      '<p class="rv-ajout-bilan" id="avis-msg" role="status" hidden></p>' +
      '<div class="dlg-actions"><button type="submit" class="bouton" autofocus>Envoyer mon avis</button><button type="button" class="bouton bouton-clair" data-fermer>Annuler</button></div></form>', 'dlg-avis');
    var etoiles = d.querySelectorAll('[data-avis-note]');
    var allumer = function (n) { note = n; etoiles.forEach(function (b) { var v = Number(b.dataset.avisNote); b.classList.toggle('allumee', v <= n); b.setAttribute('aria-checked', String(v === n)); }); };
    d.addEventListener('click', function (e) {
      if (e.target.closest('[data-fermer]')) d.close();
      var et = e.target.closest('[data-avis-note]'); if (et) { allumer(Number(et.dataset.avisNote)); var m = $('#avis-msg', d); m.hidden = true; }
    });
    $('#avis-form', d).addEventListener('submit', function (ev) {
      ev.preventDefault();
      var msg = $('#avis-msg', d), bouton = d.querySelector('button[type=submit]');
      msg.hidden = false;
      if (!note) { msg.textContent = 'Choisissez d\'abord une note de 1 à 5 étoiles.'; return; }
      bouton.disabled = true; msg.textContent = 'Envoi en cours…';
      var envoyer = function () { return window.Relais.appeler('avis', { note: note, texte: $('#avis-texte', d).value }); };
      // Une coupure réseau brève (Google redéploie, passage du Wi-Fi à la 4G) : un deuxième essai automatique avant d'abandonner
      envoyer().catch(function () { return new Promise(function (ok) { setTimeout(ok, 1500); }).then(envoyer); }).then(function (r) {
        if (r && r.ok) { d.close(); annoncer('Merci du fond du cœur ! J\'ai bien reçu votre avis et je le lirai avec attention.'); return; }
        var e = (r && r.erreur) || 'erreur inconnue';
        msg.textContent = /expir|jeton/.test(e) ? 'Votre connexion a expiré : reconnectez-vous puis réessayez.' : /action inconnue/.test(e) ? 'Cette fonction n\'est pas encore disponible. Réessayez bientôt.' : e.charAt(0).toUpperCase() + e.slice(1) + '.';
        bouton.disabled = false;
      }).catch(function () { msg.textContent = 'Le service ne répond pas pour le moment. Vérifiez votre connexion et réessayez dans une minute : votre texte est conservé.'; bouton.disabled = false; });
    });
  }

  /* ---------- Menu et clics ---------- */
  function fermerMenu(rendreFocus) {
    var m = $('#compte-menu'), b = $('#compte-btn');
    if (!m || m.hidden) return;
    m.hidden = true; if (b) { b.setAttribute('aria-expanded', 'false'); if (rendreFocus) b.focus(); }
  }
  document.addEventListener('click', function (e) {
    var act = e.target.closest('[data-compte]');
    if (act) {
      var a = act.dataset.compte;
      if (a === 'connecter') { fermerMenu(); connecter(); }
      else if (a === 'sync') { premiereReprise(); }
      else if (a === 'role') { echecRole = ''; dessiner(); chargerRole(); }
      else if (a === 'avis') { fermerMenu(); var feuilleA = $('#feuille-plus'); if (feuilleA && feuilleA.open) feuilleA.close(); donnerAvis(); }
      else if (a === 'demande') { fermerMenu(); var feuille = $('#feuille-plus'); if (feuille && feuille.open) feuille.close(); demanderLivre(); }
      else if (a === 'supprimer') {
        fermerMenu();
        if (window.confirm('Supprimer définitivement votre collection du Drive ? Elle sera aussi effacée de cet appareil. Exportez-la d\'abord si vous voulez en garder une copie.')) {
          window.Cloud.supprimerDrive().then(function () { adopter({}); annoncer('Votre collection a été supprimée du Drive et de cet appareil.'); dessiner(); })
            .catch(function () { annoncer('La suppression n\'a pas abouti. Réessayez après vous être reconnecté.'); dessiner(); });
        }
      }
      else if (a === 'deconnecter') {
        fermerMenu();
        if (window.confirm('Votre collection reste dans votre Drive. Sur cet appareil, vous ne pourrez plus la modifier tant que vous ne vous reconnectez pas. Se déconnecter ?')) { window.Cloud.deconnecter(); role = ''; ecrireSession(CLE_ROLE, ''); dessiner(); }
      }
      return;
    }
    var btn = e.target.closest('#compte-btn');
    if (btn) {
      var m = $('#compte-menu'), ouvert = m.hidden;
      if (btn.classList.contains('compte-deconnecte')) { connecter(); return; }
      m.hidden = !ouvert; btn.setAttribute('aria-expanded', String(ouvert));
      if (ouvert) { var premier = m.querySelector('a, button'); if (premier) premier.focus(); }
      return;
    }
    if (!e.target.closest('#compte-menu')) fermerMenu(false);
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') fermerMenu(true); });

  /* ---------- Démarrage ---------- */
  function demarrer() {
    if (!window.Cloud) return;
    window.Cloud.config().then(function (c) {
      configure = !!(c && c.client_id && (c.collection === true || c.relais_url));    // le bouton « Se connecter » n'apparaît que si une fonction l'utilise
      exigeCompte = !!(c && c.client_id && c.collection === true);
      if (!configure) { ['#compte-haut', '#compte-feuille'].forEach(function (s) { var n = $(s); if (n) n.hidden = true; }); return; }
      role = lireSession(CLE_ROLE);
      bandeau(); dessiner();
      if (window.Cloud.actif() && !role) chargerRole();      // connexion reprise sans nouvel onglet : le niveau est relu
      window.Cloud.surChangement(function () { dessiner(); if (window.Cloud.statut() === 'a-jour') chargerRole(); });
      document.addEventListener('cdh-collection', dessiner);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer); else demarrer();

  return { annoncer: annoncer, demanderLivre: demanderLivre, exiger: exiger, connecter: connecter, etat: etat, role: function () { return role; }, echecRole: function () { return echecRole; }, actif: actifGoogle, avecEquipe: true };
})();
