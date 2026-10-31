/* Compte : un seul point d'entrée pour se connecter avec Google, voir l'état de la sauvegarde et, selon son niveau, accéder à l'espace des niveau 2.
   Niveaux : visiteur (non connecté), Héros (connecté), niveau 2, niveau 3 (le niveau vient du service technique, voir relais/).
   Ce fichier ne touche ni à la collection ni aux prix : il s'appuie sur Cloud (connexion, sauvegarde), Relais (niveau) et AppCollection (app.js). */
window.Compte = (function () {
  var CLE_ROLE = 'cdh-role', SAUVE = 'cote-collection-avant-reprise';
  var configure = null, configPrete = false, exigeCompte = false, role = '', finAcces = '', echecRole = '', intention = null, reprisEnCours = false;
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var esc = function (t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var lireSession = function (k) { try { return sessionStorage.getItem(k) || ''; } catch (e) { return ''; } };
  var ecrireSession = function (k, v) { try { if (v) sessionStorage.setItem(k, v); else sessionStorage.removeItem(k); } catch (e) { /* sans effet */ } };
  var NIVEAUX = { heros: 'Héros', admin: 'Sorcier', superadmin: 'Zagor' };
  var estAdmin = function () { return role === 'superadmin'; };   // les niveau 2 ne sont plus administrateurs

  /* ---------- État affiché ---------- */
  function etat() {
    if (!window.Cloud || !window.Cloud.lie()) return { cle: 'deconnecte', ligne: 'Non connecté. Les fiches et la recherche restent libres ; les prix estimés et le scan sont réservés aux comptes.' };
    var s = window.Cloud.statut();
    if (!window.Cloud.actif() && window.Cloud.reprise && window.Cloud.reprise()) return { cle: 'reprise', ligne: 'Connexion en cours…' };
    if (!window.Cloud.actif() || s === 'a-reprendre') return { cle: 'reprendre', ligne: 'Votre connexion a expiré. Vos changements sont gardés sur cet appareil.' };
    if (s === 'connecte' && !reprisEnCours && window.Cloud.premiereFois()) return { cle: 'choix', ligne: 'Votre collection n\'est pas encore enregistrée dans votre compte : il reste un choix à faire.' };
    if (s === 'synchro' || s === 'connecte') return { cle: 'synchro', ligne: 'Enregistrement en cours…' };
    if (s === 'erreur') { var det = window.Cloud.derniereErreur ? window.Cloud.derniereErreur() : ''; return { cle: 'erreur', ligne: 'La sauvegarde n\'a pas abouti' + (det ? ' (' + ({ delai: 'Google ne répond pas', reseau: 'réseau coupé', 'lecture locale': 'lecture de la collection de cet appareil' }[det] || det) + ')' : '') + '. Vos changements sont gardés ici.' }; }
    return { cle: 'a-jour', ligne: 'Collection sauvegardée dans votre Google Drive.' };
  }
  var LIBELLE = { deconnecte: 'Se connecter', reprendre: 'Reconnecter', synchro: '', erreur: '', 'a-jour': '' };
  var SILHOUETTE = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="8.5" r="3.6"/><path d="M5 20c.8-3.6 3.7-5.5 7-5.5s6.2 1.9 7 5.5"/></svg>';

  // Niveau de la personne : une petite icône et son libellé, dans le menu de son propre compte seulement
  var NIVEAU_AFFICHE = {
    heros: ['Héros', '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/>'],
    admin: ['Sorcier', '<path d="M5 19L15 9"/><path d="M16 3l1 2.5L19.5 7 17 8l-1 2.5L15 8l-2.5-1L15 5.5z"/>'],
    superadmin: ['Zagor', '<path d="M3 8l4 4 5-7 5 7 4-4-2 11H5z"/>']
  };
  function niveauBadge() {
    var n = NIVEAU_AFFICHE[role];
    if (!n) return '';
    return ' <span class="compte-niveau niveau-' + role + '"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + n[1] + '</svg>' + n[0] + '</span>';
  }
  function niveauIcone() {
    var n = NIVEAU_AFFICHE[role];
    return n ? '<svg class="niveau-icone" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="' + n[0] + '">' + n[1] + '</svg>' : '';
  }
  // Petites icônes du menu (même trait que la barre d'onglets de la page Vérifier les prix)
  var ICO = {
    collection: '<path d="M4 4h4v16H4zM10 4h4v16h-4z"/><path d="M16 5l4 1-3 14-4-1z"/>',
    sync: '<path d="M20 11a8 8 0 0 0-14-4M4 5v4h4"/><path d="M4 13a8 8 0 0 0 14 4M20 19v-4h-4"/>',
    demande: '<path d="M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M12 9v6M9 12h6"/>',
    espace: '<path d="M5 19L15 9"/><path d="M16 3l1 2.5L19.5 7 17 8l-1 2.5L15 8l-2.5-1L15 5.5z"/>',
    butin: '<path d="M6 3h12l4 6-10 12L2 9z"/><path d="M2 9h20"/>',
    equipe: '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M16 5a3 3 0 0 1 0 6M18 14c2 .6 3 2.5 3 5"/>',
    deconnecter: '<path d="M10 4H5v16h5"/><path d="M15 8l4 4-4 4M19 12H9"/>'
  };
  function ico(nom) { return '<svg class="ico-menu" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICO[nom] + '</svg>'; }

  // Niveau minimum pour voir la ligne : Héros (tout compte connecté), niveau 2, niveau 3 (qui voit aussi ce qui est réservé aux niveaux d'en dessous)

  function bloc(e) {   // contenu commun au menu du haut et à la feuille mobile
    var nom = window.Cloud && window.Cloud.nom();
    if (e.cle === 'deconnecte') {
      return '<p class="compte-nom">Votre compte</p><p class="compte-ligne">' + esc(e.ligne) + '</p>' +
        '<button type="button" class="bouton" data-compte="connecter">Se connecter avec Google</button>';
    }
    var h = '<p class="compte-nom">' + esc(nom || 'Compte Google') + niveauBadge() + '</p><p class="compte-ligne" role="status">' + esc(e.ligne) + '</p>';
    if (e.cle === 'reprendre') h += '<button type="button" class="bouton" data-compte="connecter">Reconnecter</button>';
    else if (e.cle === 'erreur') h += '<button type="button" class="bouton bouton-clair" data-compte="sync">Réessayer</button>';
    else if (e.cle === 'choix') h += '<button type="button" class="bouton" data-compte="sync">Choisir maintenant</button>';
    h += '<ul class="compte-liste">' +
      (role === 'admin' || role === 'superadmin' ? '<li><a href="butin.html">' + ico('butin') + 'Butins et Annonces</a></li>' : '') +
      (role === 'admin' || role === 'superadmin' ? '<li><a href="ajouter.html">' + ico('demande') + 'Ajouter des livres</a></li>' : '') +
      (role === 'admin' || role === 'superadmin' ? '<li><a href="evolutions.html">' + ico('butin') + 'Évolutions des prix</a></li>' : '') +
      (role === 'superadmin' ? '<li class="compte-section">Gestion</li><li><a href="revue-prix.html">' + ico('espace') + 'Prix et corrections</a></li>' : '') +
      (role === 'superadmin' && window.Compte.avecEquipe ? '<li><a href="equipe.html">' + ico('equipe') + 'Équipe</a></li>' : '') +
      (e.cle === 'a-jour' ? '<li><button type="button" class="bouton-lien" data-compte="sync">' + ico('sync') + 'Synchroniser maintenant</button></li>' : '') +
      '<li><button type="button" class="bouton-lien" data-compte="deconnecter">' + ico('deconnecter') + 'Se déconnecter</button></li></ul>';
    return h;
  }

  function dessiner() {
    var e = etat();
    var haut = $('#compte-haut');
    if (haut) {
      var prenom = window.Cloud && window.Cloud.nom();
      var libelle = e.cle === 'deconnecte' || e.cle === 'reprendre' ? LIBELLE[e.cle] : (prenom || 'Compte');
      haut.innerHTML = '<button type="button" class="compte-bouton compte-' + e.cle + '" id="compte-btn" aria-haspopup="menu" aria-expanded="false" aria-controls="compte-menu">' +
        SILHOUETTE + '<span class="compte-libelle">' + esc(libelle) + '</span>' + (e.cle === 'deconnecte' || e.cle === 'reprendre' ? '' : niveauIcone()) + '<i class="compte-point" aria-hidden="true"></i></button>' +
        '<div class="compte-menu" id="compte-menu" role="group" aria-label="Mon compte" hidden>' + bloc(e) + '</div>';
    }
    var f = $('#compte-feuille');
    if (f) f.innerHTML = bloc(e);
    var tab = $('[data-plus]');
    if (tab) {                       // onglet du bas : « Compte » (« Reconnexion » si la connexion a expiré)
      var span = tab.querySelector('span');
      if (span) span.textContent = e.cle === 'reprendre' ? 'Reconnexion' : e.cle === 'erreur' ? 'Erreur' : e.cle === 'choix' ? 'À finir' : 'Compte';
      tab.classList.remove('compte-deconnecte', 'compte-reprendre', 'compte-reprise', 'compte-synchro', 'compte-erreur', 'compte-a-jour', 'compte-choix');
      tab.classList.add('compte-' + e.cle);
    }
    var ban = $('#compte-bandeau');
    if (ban) ban.hidden = !(e.cle === 'reprendre' && enCours());
    bandeauFin();
    bienvenueSorcier();
    document.dispatchEvent(new CustomEvent('cdh-compte', { detail: { etat: e.cle, role: role } }));
  }
  // Le bandeau « connexion expirée » n'apparaît que s'il y a des changements pas encore envoyés au Drive
  var enCours = function () { return !!window.AppCollection && window.Cloud.enAttente(window.AppCollection.lire()); };

  // Accès à durée limitée : un bandeau prévient la personne concernée pendant les 14 derniers jours
  function bandeauFin() {
    var b = $('#compte-fin'), reste = null;
    if (role === 'admin' && finAcces) {
      var d = new Date(), auj = d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
      reste = Math.round((Date.parse(finAcces) - Date.parse(auj)) / 86400000);
    }
    var visible = reste !== null && reste >= 0 && reste <= 14;
    if (!visible) { if (b) b.hidden = true; return; }
    if (!b) {
      b = document.createElement('div'); b.id = 'compte-fin'; b.className = 'compte-bandeau'; b.setAttribute('role', 'status');
      var haut = $('.haut'); if (haut) haut.after(b); else document.body.prepend(b);
    }
    var quand = reste === 0 ? 'aujourd\'hui' : reste === 1 ? 'demain' : 'dans ' + reste + ' jours';
    b.innerHTML = '<span>Votre accès sorcier va bientôt se terminer : <strong>' + new Date(finAcces + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) + '</strong> (' + quand + '). Ensuite, vous redevenez Héros : votre collection est conservée.</span>';
    b.hidden = false;
  }

  // Fenêtre à l'arrivée sur le niveau sorcier, une fois par période : la date et ce que le sorcier a en plus
  var CLE_SORCIER_VU = 'cdh-sorcier-vu';
  function bienvenueSorcier() {
    var cle = role === 'admin' ? (finAcces || 'sans-fin') : '', vu = '';
    try { vu = localStorage.getItem(CLE_SORCIER_VU) || ''; } catch (e) { /* sans stockage : la fenêtre reviendra */ }
    if (role !== 'admin' || vu === cle || $('.dlg-sorcier')) return;
    var jusqua = finAcces ? 'jusqu\'au ' + new Date(finAcces + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) : 'sans date de fin';
    var d = dialogue('<img class="bienvenue-img" src="images/accueil-3.webp" alt="" width="460" height="120" decoding="async">' +
      '<h2>Vous êtes sorcier</h2>' +
      '<p>Vous êtes passé sorcier <strong>' + jusqua + '</strong>. Profitez-en bien.</p>' +
      '<p class="sous">Un sorcier, c\'est un héros avec en plus :</p>' +
      '<ul class="avantages">' +
      '<li><strong>Le Butin</strong> : les bonnes affaires, repérées pour vous.</li>' +
      '<li><strong>L\'ajout de livres en série</strong> : une liste d\'ISBN d\'un coup.</li>' +
      '</ul>' +
      '<div class="dlg-actions"><button type="button" class="bouton" data-fermer autofocus>Compris</button></div>', 'dlg-bienvenue dlg-sorcier');
    d.addEventListener('click', function (e) { if (e.target.closest('[data-fermer]')) d.close(); });
    d.addEventListener('close', function () { try { localStorage.setItem(CLE_SORCIER_VU, cle); } catch (e) { /* tant pis */ } });
  }

  function bandeau() {
    if ($('#compte-bandeau')) return;
    var b = document.createElement('div');
    b.id = 'compte-bandeau'; b.className = 'compte-bandeau'; b.hidden = true; b.setAttribute('role', 'status');
    b.innerHTML = '<span>Votre connexion a expiré. Vos changements sont gardés sur cet appareil.</span> <button type="button" class="bouton" data-compte="connecter">Reconnecter</button>';
    var haut = $('.haut'); if (haut) haut.after(b); else document.body.prepend(b);
  }

  /* ---------- Niveau (Héros, niveau 2, niveau 3) ---------- */
  // Premier passage d'un compte : le service technique le compte une fois et prévient l'éditeur (prénom et empreinte courte, jamais l'adresse)
  function signalerCompte() {                     // une fois par session : c'est le service technique qui reconnaît un compte déjà compté
    var qui = window.Cloud.nom() || '1';            // le signal est lié au compte connecté : changer de compte dans le même onglet le renvoie
    if (lireSession('cdh-bienvenue') === qui) return;
    window.Relais.appeler('bienvenue').then(function (r) {
      if (r && r.ok) ecrireSession('cdh-bienvenue', qui);
    }).catch(function () { /* nouvel essai à la prochaine page */ });
  }

  // Dernier niveau connu, gardé sur l'appareil : il s'affiche tout de suite à l'ouverture, pendant que la connexion se refait et que le service technique le revérifie.
  // Il ne donne aucun accès (les données restent servies seulement après vérification par le service technique).
  var CLE_ROLE_VU = 'cdh-role-vu', rolePromesse = null, derniereRole = 0;
  function roleVu() { try { var o = JSON.parse(localStorage.getItem(CLE_ROLE_VU) || 'null'); return o && o.r && Date.now() - o.t < 7 * 86400000 ? o : null; } catch (e) { return null; } }
  function garderRole() { try { localStorage.setItem(CLE_ROLE_VU, JSON.stringify({ r: role, fin: finAcces, t: Date.now() })); } catch (e) { /* stockage indisponible */ } }
  function oublierRole() { try { localStorage.removeItem(CLE_ROLE_VU); } catch (e) { /* rien à oublier */ } }
  function chargerRole() {
    if (!window.Relais || !window.Relais.configure() || !window.Cloud || !window.Cloud.actif()) return Promise.resolve();
    if (rolePromesse) return rolePromesse;                                   // une seule demande à la fois
    if (Date.now() - derniereRole < 60000 && role) return Promise.resolve();          // vérifié il y a moins d'une minute
    rolePromesse = window.Relais.appeler('moi').then(function (r) {
      if (r && r.ok) { role = r.role; finAcces = r.fin || ''; echecRole = ''; derniereRole = Date.now(); ecrireSession(CLE_ROLE, role); ecrireSession('cdh-fin', finAcces); garderRole(); if (role !== 'admin' && role !== 'superadmin' && window.Relais && window.Relais.oublierButin) window.Relais.oublierButin(); signalerCompte(); }
      else echecRole = (r && r.erreur) || 'inconnu';
    }).catch(function () { echecRole = 'relais'; }).then(function () { rolePromesse = null; dessiner(); });
    return rolePromesse;
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
    var d = dialogue('<h2>Devenez Héros, c\'est gratuit</h2>' +
      '<p>Les fiches et la recherche restent libres. Un compte Google vous ouvre tout le reste :</p>' +
      '<ul class="avantages">' +
      '<li><strong>Les prix estimés</strong> de chaque état (convenable, bon, très bon).</li>' +
      '<li><strong>Votre collection</strong> : ajoutez vos livres en un geste, ou en scannant leur code-barres.</li>' +
      '<li><strong>Sa valeur</strong>, calculée avec les prix du guide.</li>' +
      '<li><strong>Vos doubles à vendre</strong> et les livres que vous cherchez, bien séparés.</li>' +
      '<li><strong>Tout sauvegardé</strong> : vous retrouvez votre collection sur téléphone comme sur ordinateur.</li>' +
      '<li><strong>Un livre manque ?</strong> Demandez son ajout, et notez ceux que vous avez lus.</li>' +
      '</ul>' +
      '<p class="sous"><strong>Et mes données ?</strong> Google garde votre collection dans un espace réservé de votre Drive, que seul ce site peut ouvrir. Nous ne voyons ni votre courriel ni vos autres fichiers, et vous pouvez tout supprimer à tout moment.</p>' +
      '<div class="dlg-actions"><button type="button" class="bouton" data-compte="connecter" autofocus>Continuer avec Google</button><button type="button" class="bouton bouton-clair" data-fermer>Plus tard</button></div>', 'dlg-invitation');
    d.addEventListener('click', function (e) { if (e.target.closest('[data-compte="connecter"]') || e.target.closest('[data-fermer]')) d.close(); });
  }
  // Première visite sur l'accueil, sans compte : une fenêtre explique ce qu'est le site et ce qu'ouvre un compte gratuit (une seule fois par appareil)
  function bienvenue() {
    if ($('.dlg-bienvenue')) return;
    var d = dialogue('<img class="bienvenue-img" src="images/accueil-2.webp" alt="" width="460" height="120" decoding="async">' +
      '<h2>Bienvenue sur La Cote du Héros</h2>' +
      '<p>L\'outil des collectionneurs de livres dont vous êtes le héros : retrouvez vos livres, repérez vos doubles à vendre et ce que vous cherchez, et estimez la valeur de chaque édition.</p>' +
      '<p class="sous">Sans compte, vous consultez les fiches, les livres à paraître et un niveau de prix&nbsp;(€&nbsp;à&nbsp;€&#8288;€&#8288;€&#8288;€&#8288;€). <strong>Un compte Google, gratuit, ouvre tout le reste :</strong></p>' +
      '<ul class="avantages">' +
      '<li><strong>Le prix estimé</strong> de chaque livre, selon son état.</li>' +
      '<li><strong>Votre collection</strong>, en scannant les codes-barres avec votre téléphone.</li>' +
      '<li><strong>Vos doubles à vendre</strong> et les livres à trouver.</li>' +
      '<li><strong>Des liens directs</strong> vers LBC, Vinted et eBay.</li>' +
      '<li><strong>Un livre manque ?</strong> Demandez son ajout.</li>' +
      '<li><strong>La valeur de votre collection</strong>, suivie et analysée.</li>' +
      '</ul>' +
      '<p class="sous">La cote est un ordre de grandeur calculé sur des prix demandés : la marge de négociation reste à votre main. Votre collection est sauvegardée dans un espace réservé de votre Drive, sur téléphone comme sur ordinateur, et vous pouvez la supprimer à tout moment.</p>' +
      '<div class="dlg-actions"><button type="button" class="bouton" data-compte="connecter" autofocus>Créer mon compte gratuit</button><button type="button" class="bouton bouton-clair" data-fermer>Découvrir le site</button></div>', 'dlg-invitation dlg-bienvenue');
    d.addEventListener('click', function (e) { if (e.target.closest('[data-compte="connecter"]') || e.target.closest('[data-fermer]')) d.close(); });
  }
  // Appelée par app.js : n'ouvre la fenêtre que pour un visiteur sur l'accueil, sans fiche demandée, et jamais deux fois sur le même appareil
  function accueillir() {
    if (!exigeCompte || !window.Cloud || window.Cloud.lie() || !$('#hero-coll') || /fiche=/.test(location.hash) || $('dialog[open]')) return;
    try { if (localStorage.getItem('cdh-bienvenue')) return; localStorage.setItem('cdh-bienvenue', '1'); } catch (e) { return; }
    setTimeout(function () { if (!$('dialog[open]')) bienvenue(); }, 600);
  }
  // Renvoie true si la personne peut modifier sa collection ; sinon ouvre l'invitation et garde l'intention, appliquée après la connexion.
  function exiger(suite) {
    if (!actifGoogle() || window.Cloud.lie()) return true;
    intention = typeof suite === 'function' ? suite : null;
    invitation();
    return false;
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
        if (r && r.ok) { d.close(); try { localStorage.setItem('cdh-avis-donne', '1'); } catch (x) { /* sans stockage : le bandeau pourra revenir */ } var bv = document.getElementById('bandeau-avis'); if (bv) bv.remove(); annoncer('Merci du fond du cœur ! J\'ai bien reçu votre avis et je le lirai avec attention.'); return; }
        var e = (r && r.erreur) || 'erreur inconnue';
        msg.textContent = /expir|jeton/.test(e) ? 'Votre connexion a expiré : reconnectez-vous puis réessayez.' : /action inconnue/.test(e) ? 'Cette fonction n\'est pas encore disponible. Réessayez bientôt.' : e.charAt(0).toUpperCase() + e.slice(1) + '.';
        bouton.disabled = false;
      }).catch(function () { msg.textContent = 'Le service ne répond pas pour le moment. Vérifiez votre connexion et réessayez dans une minute : votre texte est conservé.'; bouton.disabled = false; });
    });
  }

  /* ---------- Retrouver une version précédente : Google Drive garde d'anciennes copies du fichier de collection ---------- */
  function retrouverVersions() {
    if (!window.Cloud.lie()) { annoncer('Connectez-vous d\'abord.'); return; }
    if (!window.Cloud.actif()) { annoncer('Votre connexion a expiré : reconnectez-vous, puis rouvrez cette fenêtre.'); connecter(); return; }
    if ($('.dlg-versions')) return;
    var d = dialogue('<h2>Retrouver une version précédente</h2>' +
      '<p>Google Drive garde d\'anciennes copies de votre collection. Choisissez celle qui contient vos livres : le nombre de livres est indiqué pour chacune.</p>' +
      '<ul class="eq-liste" id="ver-liste"><li class="sous">Recherche des versions…</li></ul>' +
      '<p class="rv-ajout-bilan" id="ver-msg" role="status" hidden></p>' +
      '<div class="dlg-actions"><button type="button" class="bouton bouton-clair" data-fermer>Fermer</button></div>', 'dlg-versions');
    var liste = $('#ver-liste', d), msg = $('#ver-msg', d), trouvees = [];
    d.addEventListener('click', function (e) {
      if (e.target.closest('[data-fermer]')) { d.close(); return; }
      var b = e.target.closest('[data-restaurer]');
      if (!b) return;
      var v = trouvees[Number(b.dataset.restaurer)];
      if (!v || !window.confirm('Remplacer la collection de cet appareil et de votre Drive par cette version (' + v.nb + ' livres) ?')) return;
      adopter(v.coll);
      msg.hidden = false; msg.textContent = 'Restauration en cours…';
      window.Cloud.synchroniser(lire, adopter, 'appareil').then(function () {
        msg.textContent = 'Terminé : votre collection a été restaurée (' + v.nb + ' livres).'; annoncer('Votre collection a été restaurée.');
      }).catch(function () { msg.textContent = 'La restauration n\'a pas abouti sur le Drive, mais la collection est revenue sur cet appareil. Réessayez avec « Synchroniser maintenant ».'; });
    });
    window.Cloud.versionsDrive().then(function (vs) {
      if (!vs.length) { liste.innerHTML = '<li class="sous">Google Drive n\'a pas gardé de version précédente.</li>'; return; }
      return Promise.all(vs.slice(0, 20).map(function (v) {
        return window.Cloud.lireVersion(v.id).then(function (doc) {
          var coll = window.Cloud.collectionDe(doc);
          return { date: v.modifiedTime, coll: coll, nb: Object.keys(coll).filter(function (k) { return k.indexOf('souhait:') !== 0; }).length };
        }).catch(function () { return null; });
      })).then(function (res) {
        trouvees = res.filter(Boolean);
        liste.innerHTML = trouvees.length ? trouvees.map(function (v, i) {
          return '<li class="eq-membre"><div><strong>' + esc(v.nb) + ' livre' + (v.nb > 1 ? 's' : '') + '</strong> <span class="sous">· ' + esc(new Date(v.date).toLocaleString('fr-FR', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })) + '</span></div>' +
            '<div class="eq-actions"><button type="button" class="bouton bouton-clair" data-restaurer="' + i + '">Restaurer</button></div></li>';
        }).join('') : '<li class="sous">Les versions précédentes n\'ont pas pu être lues.</li>';
      });
    }).catch(function () { liste.innerHTML = '<li class="sous">Impossible de lire les versions pour le moment. Vérifiez votre connexion et réessayez.</li>'; });
  }

  /* ---------- Bandeau « Donnez votre avis » : discret, pour les visiteurs connectés qui reviennent souvent ---------- */
  var aujourdhui = function () { return new Date().toISOString().slice(0, 10); };
  var plusTard = function (jours) { return new Date(Date.now() + jours * 86400000).toISOString().slice(0, 10); };
  var lireStock = function (cle) { try { return localStorage.getItem(cle); } catch (e) { return null; } };
  var ecrireStock = function (cle, v) { try { localStorage.setItem(cle, v); } catch (e) { /* sans stockage : pas de mémoire des visites */ } };
  (function noterVisite() {                                           // les jours où la personne est venue (dix derniers), jamais son identité
    var jours = []; try { jours = JSON.parse(lireStock('cdh-visites') || '[]') || []; } catch (e) { jours = []; }
    if (jours.indexOf(aujourdhui()) < 0) { jours.push(aujourdhui()); ecrireStock('cdh-visites', JSON.stringify(jours.slice(-10))); }
  })();
  function bandeauAvis() {
    var page = document.body && document.body.dataset.page;
    if (page !== 'accueil' && page !== 'collection') return;
    var deja = document.getElementById('bandeau-avis');
    var visites = []; try { visites = JSON.parse(lireStock('cdh-visites') || '[]') || []; } catch (e) { visites = []; }
    var voir = actifGoogle() && window.Cloud && window.Cloud.actif() && visites.length >= 3 && !lireStock('cdh-avis-donne') && !((lireStock('cdh-avis-ferme') || '') > aujourdhui());
    if (!voir) { if (deja) deja.remove(); return; }
    if (deja) return;
    var b = document.createElement('div');
    b.id = 'bandeau-avis'; b.className = 'bandeau-avis cadre';
    b.innerHTML = '<p>Le guide vous est utile ? <a href="#avis" data-compte="avis">Donnez votre avis</a></p><button type="button" data-avis-ferme aria-label="Fermer ce message">×</button>';
    var rang = document.getElementById('rang-accueil'), main = document.getElementById('main');
    if (rang) rang.parentNode.insertBefore(b, rang); else if (main) main.insertBefore(b, main.firstChild);
    b.addEventListener('click', function (e) {
      if (e.target.closest('[data-avis-ferme]')) { ecrireStock('cdh-avis-ferme', plusTard(60)); b.remove(); }
      else if (e.target.closest('[data-compte="avis"]')) ecrireStock('cdh-avis-ferme', plusTard(14));   // s'il annule, on ne le relance pas avant deux semaines
    });
  }
  document.addEventListener('cdh-compte', bandeauAvis);
  document.addEventListener('DOMContentLoaded', bandeauAvis);

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
      else if (a === 'versions') { retrouverVersions(); }
      else if (a === 'role') { echecRole = ''; dessiner(); chargerRole(); }
      else if (a === 'avis') { e.preventDefault(); document.querySelectorAll('details.menu-plus[open]').forEach(function (x) { x.open = false; }); fermerMenu(); var feuilleA = $('#feuille-plus'); if (feuilleA && feuilleA.open) feuilleA.close(); donnerAvis(); }
      else if (a === 'supprimer') {
        fermerMenu();
        if (window.confirm('Supprimer définitivement votre collection du Drive ? Elle sera aussi effacée de cet appareil. Exportez-la d\'abord si vous voulez en garder une copie.')) {
          window.Cloud.supprimerDrive().then(function () { adopter({}); annoncer('Votre collection a été supprimée du Drive et de cet appareil.'); dessiner(); })
            .catch(function () { annoncer('La suppression n\'a pas abouti. Réessayez après vous être reconnecté.'); dessiner(); });
        }
      }
      else if (a === 'deconnecter') {
        fermerMenu();
        if (window.confirm('Votre collection reste dans votre Drive. Sur cet appareil, vous ne pourrez plus la modifier tant que vous ne vous reconnectez pas. Se déconnecter ?')) { window.Cloud.deconnecter(); role = ''; finAcces = ''; ecrireSession(CLE_ROLE, ''); ecrireSession('cdh-fin', ''); dessiner(); }
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
      configPrete = true;
      if (!configure) { ['#compte-haut', '#compte-feuille'].forEach(function (s) { var n = $(s); if (n) n.hidden = true; }); return; }
      role = lireSession(CLE_ROLE); finAcces = lireSession('cdh-fin') || '';
      var vu = roleVu();
      if (!role && vu && window.Cloud.lie()) { role = vu.r; finAcces = vu.fin || ''; }          // dernier niveau connu, en attendant la vérification
      bandeau(); dessiner();
      if (window.Cloud.actif() && (!role || role === 'admin' || (role === 'superadmin' && !(vu && Date.now() - vu.t < 600000)))) chargerRole();   // un sorcier relit son niveau à chaque page : sa période peut avoir changé      // connexion reprise sans nouvel onglet : le niveau est relu
      window.Cloud.surChangement(function (st) { if (st === 'hors-ligne') { ecrireSession('cdh-bienvenue', ''); ecrireSession(CLE_ROLE, ''); ecrireSession('cdh-fin', ''); oublierRole(); if (window.Relais && window.Relais.oublierButin) window.Relais.oublierButin(); role = ''; finAcces = ''; } dessiner(); if (st === 'connecte' || window.Cloud.statut() === 'a-jour') chargerRole(); });          // le niveau est relu dès que la connexion est prête, en même temps que le Drive
      document.addEventListener('cdh-nom', dessiner);
      document.addEventListener('cdh-collection', dessiner);
      // Reprendre les changements faits sur un autre appareil : à l'ouverture de la page et quand on y revient (au plus une fois par 30 s)
      var derniere = 0;
      var rafraichir = function () {
        if (!window.AppCollection || !window.AppCollection.pret || !window.AppCollection.pret() || !window.Cloud.lie() || !window.Cloud.actif() || window.Cloud.premiereFois() || reprisEnCours) return;
        if (Date.now() - derniere < 30000) return;
        derniere = Date.now(); sync();
      };
      rafraichir();
      document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') rafraichir(); });
      window.addEventListener('focus', rafraichir);
      document.addEventListener('cdh-collection-prete', rafraichir);        // la collection de l'appareil est lue : seulement maintenant on peut la comparer au Drive
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer); else demarrer();

  return { accueillir: accueillir, annoncer: annoncer, exiger: exiger, inviter: function () { if (exigeCompte && window.Cloud && !window.Cloud.lie()) invitation(); }, pret: function () { return configPrete; }, connecter: connecter, etat: etat, role: function () { return role; }, echecRole: function () { return echecRole; }, actif: actifGoogle, avecEquipe: true };
})();
