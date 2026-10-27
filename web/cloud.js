/* Collection sauvegardée dans le compte Google de la personne.
   - La connexion Google est nécessaire pour construire sa collection ; consulter le site reste libre.
   - La collection est écrite dans l'espace caché « appDataFolder » du Drive de la personne : seul ce site peut le lire, il n'apparaît pas
     dans ses fichiers et rien ne passe par un serveur du guide (droit demandé : drive.appdata, classé non sensible par Google).
   - Plusieurs appareils : à chaque synchronisation on lit la copie du Drive, on fusionne avec la copie locale (la modification la plus récente
     l'emporte pour chaque livre ; un livre retiré est gardé en « supprimé » pour ne pas revenir), puis on réécrit.
   La fusion (fusionner, etatLocal) est du calcul pur, testé par pipeline/test_cloud_fusion.js. */
(function (racine) {
  var BASE = (typeof document !== 'undefined' && document.currentScript && document.currentScript.src) ? document.currentScript.src.replace(/[^\/]*$/, '') : '';   // les pages du dossier livre/ chargent les scripts de la racine
  var VERSION = 1, FICHIER = 'collection.json', OUBLI_JOURS = 90;

  /* ---------- Calcul pur ---------- */

  // Document à échanger : { v, items: { id: {...exemplaire, m} }, sup: { id: date de retrait } }, avec la date de dernière modification
  // de chaque livre. `meta` garde ces dates sur l'appareil : { m: {id: ts}, sup: {id: ts}, base: {id: json} }.
  function etatLocal(coll, meta, maintenant) {
    var m = Object.assign({}, meta.m), sup = Object.assign({}, meta.sup), base = Object.assign({}, meta.base);
    Object.keys(coll).forEach(function (id) {
      var j = JSON.stringify(coll[id]);
      if (base[id] !== j) { m[id] = maintenant; base[id] = j; delete sup[id]; }
    });
    Object.keys(base).forEach(function (id) {
      if (!(id in coll)) { sup[id] = maintenant; delete m[id]; delete base[id]; }
    });
    var items = {};
    Object.keys(coll).forEach(function (id) { items[id] = Object.assign({}, coll[id], { m: m[id] || 0 }); });
    return { meta: { m: m, sup: sup, base: base }, doc: { v: VERSION, items: items, sup: sup } };
  }

  // Fusion de deux documents : pour chaque livre, la date la plus récente décide (égalité : la copie locale).
  function fusionner(local, distant, maintenant) {
    distant = distant && distant.items ? distant : { items: {}, sup: {} };
    var ids = {};
    [local.items, local.sup, distant.items || {}, distant.sup || {}].forEach(function (o) { Object.keys(o).forEach(function (id) { ids[id] = 1; }); });
    var items = {}, sup = {}, limite = maintenant - OUBLI_JOURS * 86400000;
    Object.keys(ids).forEach(function (id) {
      var l = local.items[id] ? local.items[id].m : (local.sup[id] || 0);
      var d = (distant.items || {})[id] ? distant.items[id].m : ((distant.sup || {})[id] || 0);
      var localGagne = l >= d, source = localGagne ? local : distant;
      if (source.items && source.items[id]) items[id] = source.items[id];
      else { var t = localGagne ? local.sup[id] : distant.sup[id]; if (t && t > limite) sup[id] = t; }
    });
    return { v: VERSION, items: items, sup: sup };
  }

  // Document fusionné -> collection de l'appli (sans les dates) et nouvelle mémoire de l'appareil
  function versLocal(doc) {
    var coll = {}, m = {}, base = {};
    Object.keys(doc.items).forEach(function (id) {
      var e = Object.assign({}, doc.items[id]); m[id] = e.m || 0; delete e.m;
      coll[id] = e; base[id] = JSON.stringify(e);
    });
    return { coll: coll, meta: { m: m, sup: Object.assign({}, doc.sup), base: base } };
  }

  var meme = function (a, b) { return JSON.stringify(a) === JSON.stringify(b); };

  if (typeof module !== 'undefined' && module.exports) { module.exports = { etatLocal: etatLocal, fusionner: fusionner, versLocal: versLocal, meme: meme }; return; }

  /* ---------- Connexion Google et Drive (navigateur) ---------- */

  var CLE_LIEN = 'cdh-cloud-lie', CLE_META = 'cdh-cloud-meta';
  var CLE_JETON = 'cdh-cloud-jeton', CLE_SESSION = 'cdh-cloud-session', CLE_SANS_SESSION = 'cdh-cloud-sans-session';
  var derniereErreur = '', cfg = null, jeton = '', expire = 0, auClient = null, auDrive = null, minuterie = null, minuterieSession = null, enCours = false, aRejouer = false, statut = 'hors-ligne';
  var ecouteurs = [];
  var lireLoc = function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } };
  var ecrireLoc = function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* stockage indisponible */ } };
  var oterLoc = function (k) { try { localStorage.removeItem(k); } catch (e) { /* rien à retirer */ } };
  var lireMeta = function () { try { return JSON.parse(lireLoc(CLE_META) || '{}') || {}; } catch (e) { return {}; } };

  // La connexion survit au changement de page et à la fermeture de l'onglet : le laissez-passer de Google (une heure au plus) reste sur l'appareil
  // jusqu'à sa fin de validité, puis il est effacé. Il n'est jamais envoyé ailleurs qu'à Google.
  function garderJeton() { try { localStorage.setItem(CLE_JETON, JSON.stringify({ j: jeton, e: expire })); } catch (e) { /* stockage indisponible */ } }
  function oublierJeton() { try { localStorage.removeItem(CLE_JETON); sessionStorage.removeItem(CLE_JETON); } catch (e) { /* rien à oublier */ } }
  (function reprendreJeton() {
    try { var s = JSON.parse(localStorage.getItem(CLE_JETON) || 'null'); if (s && s.j && s.e > Date.now()) { jeton = s.j; expire = s.e; } else if (s) oublierJeton(); } catch (e) { /* rien à reprendre */ }
  })();

  function config() {
    if (!cfg) cfg = fetch(BASE + 'data/admin-config.json', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; });
    return cfg;
  }
  function dire(s, detail) { statut = s; ecouteurs.forEach(function (f) { f(s, detail); }); }
  function lie() { return !!lireLoc(CLE_LIEN); }
  function nom() { try { return (JSON.parse(lireLoc(CLE_LIEN) || 'null') || {}).nom || ''; } catch (e) { return ''; } }
  function actif() { return !!jeton && Date.now() < expire; }
  // Preuve de connexion transmise au relais (qui la vérifie auprès de Google) : valable environ une heure
  function preuve() { return actif() ? jeton : ''; }

  function chargerGoogle() {
    return new Promise(function (ok, ko) {
      if (window.google && window.google.accounts && window.google.accounts.oauth2) return ok();
      var s = document.createElement('script');
      s.src = 'https://accounts.google.com/gsi/client'; s.async = true; s.onload = ok; s.onerror = ko;
      document.head.appendChild(s);
    });
  }

  // Session de longue durée (30 jours) : le service technique garde le jeton de renouvellement ; le navigateur n'a qu'un identifiant de session révocable.
  // Activée par « session_relais » dans data/admin-config.json, une fois le service technique à jour et sa clé secrète en place.
  function appelRelais(action, params) {
    return config().then(function (c) {
      return fetch(c.relais_url, { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify(Object.assign({ action: action }, params)) }).then(function (r) { return r.json(); });
    });
  }
  function prendreJeton(r) {
    jeton = r.access_token; expire = Date.now() + (Number(r.expires_in) || 3600) * 1000 - 60000; garderJeton(); planifierRenouvellement();
  }
  function planifierRenouvellement() {
    clearTimeout(minuterieSession);
    if (!lireLoc(CLE_SESSION)) return;
    minuterieSession = setTimeout(function () { renouveler().catch(function () { /* la reprise se fera à la prochaine ouverture */ }); }, Math.max(5000, expire - Date.now() - 120000));
  }
  function renouveler() {
    var sid = lireLoc(CLE_SESSION);
    if (!sid) return Promise.reject(new Error('pas-de-session'));
    return appelRelais('session_renouveler', { session: sid }).then(function (r) {
      if (!r.ok) { if (/inconnue|expir/.test(r.erreur || '')) { oterLoc(CLE_SESSION); } throw new Error(r.erreur || 'refus'); }
      prendreJeton(r);
      return fetch('https://www.googleapis.com/oauth2/v3/userinfo', { headers: { Authorization: 'Bearer ' + jeton } })      // le prénom vient de Google (met aussi à jour une session ouverte avant ce correctif)
        .then(function (x) { return x.ok ? x.json() : {}; }).catch(function () { return {}; })
        .then(function (u) { if (u.given_name || u.name) ecrireLoc(CLE_LIEN, JSON.stringify({ nom: u.given_name || u.name })); dire('connecte'); });
    });
  }
  function connecterSession(c) {
    return new Promise(function (ok, ko) {
      var client = window.google.accounts.oauth2.initCodeClient({
        client_id: c.client_id,
        scope: 'openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/drive.appdata',
        ux_mode: 'popup',
        callback: function (rep) {
          if (rep.error || !rep.code) return ko(new Error(rep.error || 'refus'));
          appelRelais('session_ouvrir', { code: rep.code }).then(function (r) {
            if (!r.ok) throw new Error(r.erreur || 'refus');
            prendreJeton(r); ecrireLoc(CLE_SESSION, r.session);
            return fetch('https://www.googleapis.com/oauth2/v3/userinfo', { headers: { Authorization: 'Bearer ' + jeton } })
              .then(function (x) { return x.ok ? x.json() : {}; }).catch(function () { return {}; })
              .then(function (u) {
                ecrireLoc(CLE_LIEN, JSON.stringify({ nom: u.given_name || u.name || 'Compte Google' }));
                planifierRenouvellement(); dire('connecte'); ok();
              });
          }).catch(ko);
        },
        error_callback: function () { ko(new Error('annule')); }
      });
      client.requestCode();
    });
  }

  // À appeler depuis un clic (le navigateur n'ouvre la fenêtre Google que sur un geste de la personne)
  function connecter() {
    return Promise.all([config(), chargerGoogle()]).then(function (r) {
      if (!r[0].client_id) throw new Error('non-configure');
      if (r[0].session_relais && r[0].relais_url && !lireLoc(CLE_SANS_SESSION)) {
        return connecterSession(r[0]).catch(function (e) {
          // Le relais ne peut pas ouvrir la session (non configuré, renouvellement non accordé…) : la prochaine connexion sera celle d'une heure
          if (!e || e.message !== 'annule') ecrireLoc(CLE_SANS_SESSION, '1');
          throw e;
        });
      }
      return connecterJeton(r[0]);
    });
  }
  function connecterJeton(cfgSite) {
    return Promise.resolve([cfgSite]).then(function (r) {
      return new Promise(function (ok, ko) {
        var client = window.google.accounts.oauth2.initTokenClient({
          client_id: r[0].client_id,
          scope: 'openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/drive.appdata',
          callback: function (rep) {
            if (rep.error || !rep.access_token) return ko(new Error(rep.error || 'refus'));
            jeton = rep.access_token; expire = Date.now() + (Number(rep.expires_in) || 3600) * 1000 - 60000; garderJeton(); oterLoc(CLE_SESSION);
            fetch('https://www.googleapis.com/oauth2/v3/userinfo', { headers: { Authorization: 'Bearer ' + jeton } })
              .then(function (x) { return x.ok ? x.json() : {}; }).catch(function () { return {}; })
              .then(function (u) {
                ecrireLoc(CLE_LIEN, JSON.stringify({ nom: u.given_name || u.name || 'Compte Google' }));
                dire('connecte'); ok();
              });
          },
          error_callback: function () { ko(new Error('annule')); }
        });
        auClient = client;
        client.requestAccessToken({ prompt: lie() ? '' : 'select_account' });
      });
    });
  }

  function deconnecter() {
    var j = jeton, sid = lireLoc(CLE_SESSION); jeton = ''; expire = 0; oterLoc(CLE_LIEN); oublierJeton(); oterLoc(CLE_SESSION); clearTimeout(minuterieSession);
    if (sid) appelRelais('session_fermer', { session: sid }).catch(function () { /* hors ligne : la session expirera d'elle-même */ });
    try { if (j && window.google && window.google.accounts) window.google.accounts.oauth2.revoke(j, function () {}); } catch (e) { /* sans effet */ }
    dire('hors-ligne');
  }

  var entetes = function () { return { Authorization: 'Bearer ' + jeton }; };
  // Appel réseau qui ne reste jamais suspendu : sans réponse au bout de 25 s, il échoue (la synchronisation affiche alors une erreur au lieu de rester « en cours »)
  function reseau(url, options) {
    var ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var minute = setTimeout(function () { if (ctl) ctl.abort(); }, 25000);
    return fetch(url, Object.assign({}, options, ctl ? { signal: ctl.signal } : {})).then(function (r) { clearTimeout(minute); return r; }, function (e) { clearTimeout(minute); throw new Error(e && e.name === 'AbortError' ? 'delai' : 'reseau'); });
  }
  var API = 'https://www.googleapis.com/drive/v3/files', UP = 'https://www.googleapis.com/upload/drive/v3/files';
  function verifier(r) { if (r.status === 401 || r.status === 403) { jeton = ''; expire = 0; oublierJeton(); throw new Error('expire'); } if (!r.ok) throw new Error('drive-' + r.status); return r; }

  function lireDrive() {
    return reseau(API + '?spaces=appDataFolder&pageSize=1&fields=files(id)&q=' + encodeURIComponent("name='" + FICHIER + "'"), { headers: entetes() }).then(verifier).then(function (r) { return r.json(); }).then(function (l) {
      if (!l.files || !l.files.length) { auDrive = null; return null; }
      auDrive = l.files[0].id;
      return reseau(API + '/' + auDrive + '?alt=media', { headers: entetes() }).then(verifier).then(function (r) { return r.json(); }).catch(function (e) { if (e.message === 'expire' || e.message === 'delai' || e.message === 'reseau' || /^drive-/.test(e.message)) throw e; return null; });
    });
  }
  function ecrireDrive(doc) {
    var corps = JSON.stringify(doc);
    if (auDrive) return reseau(UP + '/' + auDrive + '?uploadType=media', { method: 'PATCH', headers: Object.assign({ 'Content-Type': 'application/json' }, entetes()), body: corps }).then(verifier);
    var borne = 'cdh' + Date.now();
    var multi = '--' + borne + '\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n' + JSON.stringify({ name: FICHIER, parents: ['appDataFolder'] }) +
      '\r\n--' + borne + '\r\nContent-Type: application/json\r\n\r\n' + corps + '\r\n--' + borne + '--';
    return reseau(UP + '?uploadType=multipart&fields=id', { method: 'POST', headers: Object.assign({ 'Content-Type': 'multipart/related; boundary=' + borne }, entetes()), body: multi })
      .then(verifier).then(function (r) { return r.json(); }).then(function (f) { auDrive = f.id; });
  }

  // Synchronise : `lireColl()` donne la collection de l'appli, `adopter(coll)` la remplace quand le Drive apporte des changements.
  function synchroniser(lireColl, adopter, strategie) {
    if (!lie()) return Promise.resolve();
    if (!actif()) { dire('a-reprendre'); return Promise.resolve(); }
    if (enCours) { aRejouer = true; return Promise.resolve(); }
    enCours = true; dire('synchro'); derniereErreur = '';
    var maintenant = Date.now(), local, instantane;
    try { instantane = JSON.stringify(lireColl()); local = etatLocal(lireColl(), lireMeta(), maintenant); }
    catch (e) { enCours = false; derniereErreur = 'lecture locale'; try { console.error('Synchronisation : lecture locale impossible', e); } catch (x) { /* console absente */ } dire('erreur'); return Promise.resolve(); }      // jamais « en cours » pour toujours
    return lireDrive().then(function (distant) {
      // Une modification faite pendant l'attente du réseau (import, ajout…) ne doit jamais être écrasée : on abandonne ce tour et on recommence avec la collection à jour
      if (JSON.stringify(lireColl()) !== instantane) { aRejouer = true; return null; }
      // Garde-fou : un appareil qui se retrouve soudain sans aucun livre alors qu'il en avait ne doit JAMAIS effacer le Drive (collection pas encore lue, stockage vidé…)
      if (!strategie && Object.keys(local.doc.items).length === 0 && Object.keys(lireMeta().base || {}).length > 0 && distant && distant.items && Object.keys(distant.items).length > 0) strategie = 'compte';
      // strategie : « fusionner » (défaut), « compte » (le Drive remplace l'appareil), « appareil » (l'appareil remplace le Drive)
      var fusion = strategie === 'compte' && distant && distant.items ? { v: VERSION, items: distant.items, sup: distant.sup || {} }
        : strategie === 'appareil' ? { v: VERSION, items: local.doc.items, sup: {} }
        : fusionner(local.doc, distant, maintenant);
      var res = versLocal(fusion);
      var change = !meme(res.coll, lireColl());
      ecrireLoc(CLE_META, JSON.stringify(res.meta));
      if (change) adopter(res.coll);
      return meme(fusion, distant) ? null : ecrireDrive(fusion);
    }).then(function () { dire('a-jour', Date.now()); }).catch(function (e) {
      derniereErreur = e && e.message ? e.message : 'inconnue';
      dire(e && e.message === 'expire' ? 'a-reprendre' : 'erreur');
    }).then(function () { enCours = false; if (aRejouer) { aRejouer = false; return synchroniser(lireColl, adopter); } });
  }
  // Supprime la copie du Drive et la mémoire de synchronisation de l'appareil (la collection locale est vidée par l'appelant)
  function supprimerDrive() {
    if (!actif()) return Promise.reject(new Error('expire'));
    return lireDrive().then(function () {
      if (!auDrive) return null;
      return fetch(API + '/' + auDrive, { method: 'DELETE', headers: entetes() }).then(verifier).then(function () { auDrive = null; });
    }).then(function () { oterLoc(CLE_META); });
  }
  // Première connexion : combien de livres le Drive contient-il déjà ? (null si la copie du Drive est absente)
  function apercu() {
    if (!actif()) return Promise.reject(new Error('expire'));
    return lireDrive().then(function (d) { return d && d.items ? { livres: Object.keys(d.items).filter(function (k) { return k.indexOf('souhait:') !== 0; }).length } : null; })
      .catch(function (e) { dire(e && e.message === 'expire' ? 'a-reprendre' : 'erreur'); throw e; });
  }
  // Y a-t-il des changements pas encore envoyés au Drive ? (collection différente de celle de la dernière synchronisation)
  function enAttente(coll) {
    var base = lireMeta().base || {}, ids = Object.keys(coll);
    if (ids.length !== Object.keys(base).length) return true;
    return ids.some(function (id) { return base[id] !== JSON.stringify(coll[id]); });
  }
  function premiereFois() { return !lireLoc(CLE_META); }
  // Après chaque modification : synchronisation groupée (2 s sans nouvelle modification)
  function planifier(lireColl, adopter) {
    if (!lie() || premiereFois()) return;     // tant que la reprise n'est pas faite, rien n'est envoyé sans le choix de la personne
    clearTimeout(minuterie);
    minuterie = setTimeout(function () { synchroniser(lireColl, adopter); }, 2000);
  }

  // Anciennes versions du fichier de collection gardées par Google Drive : pour retrouver une collection effacée ou abîmée par erreur
  function versionsDrive() {
    if (!actif()) return Promise.reject(new Error('expire'));
    return lireDrive().then(function () {
      if (!auDrive) return [];
      return reseau(API + '/' + auDrive + '/revisions?pageSize=200&fields=revisions(id,modifiedTime)', { headers: entetes() }).then(verifier).then(function (r) { return r.json(); })
        .then(function (j) { return (j.revisions || []).slice(-40).reverse(); });
    });
  }
  function lireVersion(id) {
    return reseau(API + '/' + auDrive + '/revisions/' + encodeURIComponent(id) + '?alt=media', { headers: entetes() }).then(verifier).then(function (r) { return r.json(); });
  }
  function collectionDe(doc) { return doc && doc.items ? versLocal(doc).coll : {}; }

  // Reprise silencieuse : à l'ouverture, ou quand on revient sur la page, si une session existe et que le jeton d'une heure est périmé
  function reprendreSession() { if (lireLoc(CLE_SESSION) && !actif()) renouveler().catch(function () { /* hors ligne : on réessaiera */ }); }
  if (typeof document !== 'undefined') {
    reprendreSession();
    document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') reprendreSession(); });
    planifierRenouvellement();
  }

  racine.Cloud = {
    config: config, lie: lie, nom: nom, actif: actif, preuve: preuve, connecter: connecter, deconnecter: deconnecter,
    synchroniser: synchroniser, planifier: planifier, apercu: apercu, premiereFois: premiereFois, enAttente: enAttente, supprimerDrive: supprimerDrive, statut: function () { return statut; },
    surChangement: function (f) { ecouteurs.push(f); }, derniereErreur: function () { return derniereErreur; }, versionsDrive: versionsDrive, lireVersion: lireVersion, collectionDe: collectionDe
  };
})(typeof window !== 'undefined' ? window : this);
