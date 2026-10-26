/* Relais entre le site (La Cote du Héros) et GitHub, hébergé dans Google Apps Script.
   Le site envoie la connexion Google de la personne ; le relais la vérifie, regarde son niveau dans data/admins.json, puis lance lui-même
   les lots GitHub. La clé GitHub reste ici, dans les propriétés du script : aucun administrateur ne la voit.
   Réglages (Paramètres du projet > Propriétés du script) : CLIENT_ID, GITHUB_TOKEN, DEPOT (par exemple loliba92/LDVELH).
   Mise en place pas à pas : relais/LISEZMOI.md. Les règles sont dans logique.gs. */

function prop(nom) { return PropertiesService.getScriptProperties().getProperty(nom) || ''; }
function reponse(objet) { return ContentService.createTextOutput(JSON.stringify(objet)).setMimeType(ContentService.MimeType.JSON); }

function empreinteDe(adresse) {
  var octets = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, adresse, Utilities.Charset.UTF_8);
  return 'sha256:' + octets.map(function (b) { return ('0' + (b < 0 ? b + 256 : b).toString(16)).slice(-2); }).join('');
}

function github(chemin, options) {
  options = options || {};
  var r = UrlFetchApp.fetch('https://api.github.com/repos/' + prop('DEPOT') + chemin, {
    method: options.method || 'get', muteHttpExceptions: true, contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + prop('GITHUB_TOKEN'), Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' },
    payload: options.payload ? JSON.stringify(options.payload) : undefined
  });
  return { code: r.getResponseCode(), texte: r.getContentText() };
}

function lireAdmins() {
  var cache = CacheService.getScriptCache(), connu = cache.get('admins');
  if (connu) return JSON.parse(connu);
  var r = github('/contents/data/admins.json?ref=main');
  if (r.code !== 200) throw new Error('liste des admins illisible (' + r.code + ')');
  var d = JSON.parse(r.texte);
  var fichier = { contenu: JSON.parse(Utilities.newBlob(Utilities.base64Decode(d.content.replace(/\n/g, ''))).getDataAsString('UTF-8')), sha: d.sha };
  cache.put('admins', JSON.stringify(fichier), 30);
  return fichier;
}
function ecrireAdmins(contenu, sha, message) {
  var r = github('/contents/data/admins.json', { method: 'put', payload: {
    message: message, branch: 'main', sha: sha,
    content: Utilities.base64Encode(JSON.stringify(contenu, null, 2) + '\n', Utilities.Charset.UTF_8) } });
  CacheService.getScriptCache().remove('admins');
  if (r.code !== 200 && r.code !== 201) throw new Error('écriture refusée (' + r.code + ')');
}

function verifierConnexion(jeton) {
  var champ = /^ya29\./.test(jeton) ? 'access_token' : 'id_token';        // le site envoie un jeton d'accès (ya29.…)
  var r = UrlFetchApp.fetch('https://oauth2.googleapis.com/tokeninfo?' + champ + '=' + encodeURIComponent(jeton), { muteHttpExceptions: true });
  var infos = {}; try { infos = JSON.parse(r.getContentText()); } catch (e) { /* réponse illisible : refus plus bas */ }
  var admins = lireAdmins();
  return { identite: decider(infos, admins.contenu, prop('CLIENT_ID'), empreinteDe, Math.floor(Date.now() / 1000)), admins: admins };
}

var URL_JETON_GOOGLE = 'https://oauth2.googleapis.com/token';

/* Session de longue durée : ouvrir (code Google -> session), renouveler (session -> nouveau jeton d'accès), fermer (révocation).
   Le jeton de renouvellement reste dans les propriétés du script ; le navigateur n'a que l'identifiant de session. */
function gererSession(q) {
  var props = PropertiesService.getScriptProperties(), maintenant = Math.floor(Date.now() / 1000), action = String(q.action);
  if (action === 'session_ouvrir') {
    var secret = prop('CLIENT_SECRET');
    if (!secret) return { ok: false, erreur: 'session non configurée' };
    var r = UrlFetchApp.fetch(URL_JETON_GOOGLE, { method: 'post', muteHttpExceptions: true, payload: { code: String(q.code || ''), client_id: prop('CLIENT_ID'), client_secret: secret, redirect_uri: 'postmessage', grant_type: 'authorization_code' } });
    var t = JSON.parse(r.getContentText() || '{}');
    if (r.getResponseCode() !== 200 || !t.access_token) return { ok: false, erreur: 'code refusé' };
    if (!t.refresh_token) return { ok: false, erreur: 'renouvellement non accordé' };
    var v = verifierConnexion(t.access_token);
    if (!v.identite.ok) return { ok: false, erreur: v.identite.raison };
    var id = Utilities.getUuid() + Utilities.getUuid();
    props.setProperty('sn:' + id, JSON.stringify(creerSession(v.identite.empreinte, t.refresh_token, maintenant)));
    return { ok: true, session: id, access_token: t.access_token, expires_in: t.expires_in, nom: v.identite.nom, role: v.identite.role };
  }
  var cle = 'sn:' + String(q.session || ''), brut = props.getProperty(cle);
  if (!brut) return { ok: false, erreur: 'session inconnue' };
  var session = JSON.parse(brut);
  if (action === 'session_fermer') {
    props.deleteProperty(cle);
    UrlFetchApp.fetch('https://oauth2.googleapis.com/revoke?token=' + encodeURIComponent(session.r), { method: 'post', muteHttpExceptions: true });
    return { ok: true };
  }
  if (action === 'session_renouveler') {
    if (sessionExpiree(session, maintenant)) { props.deleteProperty(cle); return { ok: false, erreur: 'session expirée' }; }
    var r2 = UrlFetchApp.fetch(URL_JETON_GOOGLE, { method: 'post', muteHttpExceptions: true, payload: { refresh_token: session.r, client_id: prop('CLIENT_ID'), client_secret: prop('CLIENT_SECRET'), grant_type: 'refresh_token' } });
    var t2 = JSON.parse(r2.getContentText() || '{}');
    if (r2.getResponseCode() !== 200 || !t2.access_token) { if (t2.error === 'invalid_grant') props.deleteProperty(cle); return { ok: false, erreur: 'renouvellement refusé' }; }
    props.setProperty(cle, JSON.stringify(prolongerSession(session, maintenant)));
    return { ok: true, access_token: t2.access_token, expires_in: t2.expires_in };
  }
  return { ok: false, erreur: 'action inconnue' };
}

function doPost(e) {
  try {
    var q = JSON.parse(e.postData.contents || '{}');
    if (/^session_/.test(String(q.action || ''))) return reponse(gererSession(q));
    var v = verifierConnexion(String(q.jeton || ''));
    if (!v.identite.ok) return reponse({ ok: false, erreur: v.identite.raison });
    var moi = v.identite, action = String(q.action || '');
    if (!peut(moi.role, action)) return reponse({ ok: false, erreur: 'droits insuffisants', role: moi.role });

    if (action === 'moi') return reponse({ ok: true, role: moi.role, nom: moi.nom });

    if (action === 'ajout_livres') {
      var lignes = String(q.liste || '').split(/\n|\|/).map(function (x) { return x.trim(); }).filter(function (x) { return x; });
      var jour = new Date().toISOString().slice(0, 10), cleEnvois = 'aj:' + moi.empreinte + ':' + jour;
      var props = PropertiesService.getScriptProperties(), envois = Number(props.getProperty(cleEnvois)) || 0;
      var quota = quotaAjout(moi.role, lignes.length, envois);
      if (!quota.ok) return reponse({ ok: false, erreur: quota.raison });
      var lot = validerEnvoi('ajout-isbn.yml', { liste: lignes.join(' | '), releve: 'oui' });
      if (!lot.ok) return reponse({ ok: false, erreur: lot.raison });
      lot.entrees.auteur = moi.nom;
      var go = github('/actions/workflows/ajout-isbn.yml/dispatches', { method: 'post', payload: { ref: 'main', inputs: lot.entrees } });
      if (go.code !== 204) return reponse({ ok: false, erreur: 'GitHub a refusé le lancement (' + go.code + ')' });
      if (moi.role !== 'superadmin') props.setProperty(cleEnvois, String(envois + 1));
      return reponse({ ok: true, nombre: lignes.length });
    }

    if (action === 'butin_lire' || action === 'annonces_lire') {      // Butin seul pour les sorciers ; toutes les annonces pour le Zagor
      var ann = github('/contents/data/processed/' + (action === 'annonces_lire' ? 'annonces' : 'butin') + '.json?ref=main');
      if (ann.code !== 200) return reponse({ ok: false, erreur: 'annonces indisponibles (' + ann.code + ')' });
      var fic = JSON.parse(ann.texte);
      return reponse({ ok: true, annonces: JSON.parse(Utilities.newBlob(Utilities.base64Decode(fic.content.replace(/\n/g, ''))).getDataAsString('UTF-8')) });
    }

    if (action === 'envoyer') {
      var lot = validerEnvoi(String(q.lot || ''), q.entrees);
      if (!lot.ok) return reponse({ ok: false, erreur: lot.raison });
      lot.entrees.auteur = moi.nom;
      var r = github('/actions/workflows/' + encodeURIComponent(q.lot) + '/dispatches', { method: 'post', payload: { ref: 'main', inputs: lot.entrees } });
      return reponse(r.code === 204 ? { ok: true } : { ok: false, erreur: 'GitHub a refusé le lancement (' + r.code + ')' });
    }

    if (action === 'demande') {
      var d = validerDemande(q.texte, q.note);
      if (!d.ok) return reponse({ ok: false, erreur: d.raison });
      var cache = CacheService.getScriptCache(), cle = 'dem:' + moi.empreinte;
      if (!peutDemander(cache.get(cle), moi.role)) return reponse({ ok: false, erreur: 'trop de demandes pour le moment : réessayez plus tard' });
      var f = formaterDemande(d.texte, d.note, moi.nom);
      var cree = github('/issues', { method: 'post', payload: { title: f.titre, body: f.corps, labels: [ETIQUETTE_DEMANDE] } });
      if (cree.code !== 201) return reponse({ ok: false, erreur: 'la demande n\'a pas pu être enregistrée (' + cree.code + ')' });
      cache.put(cle, String((Number(cache.get(cle)) || 0) + 1), 21600);
      return reponse({ ok: true });
    }

    if (action === 'demandes_lire') {
      var l = github('/issues?state=open&labels=' + ETIQUETTE_DEMANDE + '&per_page=50&sort=created&direction=asc');
      if (l.code !== 200) return reponse({ ok: false, erreur: 'liste illisible (' + l.code + ')' });
      var dem = JSON.parse(l.texte).map(lireDemande).filter(function (x) { return x; });
      return reponse({ ok: true, demandes: dem });
    }

    if (action === 'demande_traiter') {
      var num = Number(q.numero);
      if (!(num > 0)) return reponse({ ok: false, erreur: 'numéro de demande invalide' });
      var iss = github('/issues/' + num);
      var dm = iss.code === 200 ? lireDemande(JSON.parse(iss.texte)) : null;
      if (!dm) return reponse({ ok: false, erreur: 'demande introuvable' });
      var decision = String(q.decision || '');
      if (decision === 'accepter') {
        var lot = validerEnvoi('ajout-isbn.yml', { liste: String(q.ligne || dm.texte), releve: 'oui' });
        if (!lot.ok) return reponse({ ok: false, erreur: lot.raison });
        lot.entrees.auteur = moi.nom;
        var go = github('/actions/workflows/ajout-isbn.yml/dispatches', { method: 'post', payload: { ref: 'main', inputs: lot.entrees } });
        if (go.code !== 204) return reponse({ ok: false, erreur: 'GitHub a refusé le lancement (' + go.code + ')' });
        github('/issues/' + num + '/comments', { method: 'post', payload: { body: 'Acceptée par ' + moi.nom + ' : le livre est en cours d\'ajout.' } });
        github('/issues/' + num, { method: 'patch', payload: { state: 'closed', state_reason: 'completed' } });
        return reponse({ ok: true });
      }
      if (decision === 'refuser') {
        var raison = nettoyerTexteDemande(q.raison, 200);
        github('/issues/' + num + '/comments', { method: 'post', payload: { body: 'Refusée par ' + moi.nom + (raison ? ' : ' + raison : '.') } });
        github('/issues/' + num, { method: 'patch', payload: { state: 'closed', state_reason: 'not_planned' } });
        return reponse({ ok: true });
      }
      return reponse({ ok: false, erreur: 'décision inconnue' });
    }

    if (action === 'bienvenue') {                  // premier passage d'un compte : compté une fois, l'éditeur est prévenu par courriel
      var verrouB = LockService.getScriptLock(), rang = 0;
      verrouB.waitLock(10000);
      try {
        var props = PropertiesService.getScriptProperties(), cleU = 'u:' + votant(moi.empreinte);
        if (!props.getProperty(cleU)) {
          rang = (Number(props.getProperty('u:total')) || 0) + 1;
          props.setProperty(cleU, '1'); props.setProperty('u:total', String(rang));
          props.setProperty('un:' + rang, ligneCompte(moi.nom, Utilities.formatDate(new Date(), 'Europe/Paris', 'yyyy-MM-dd')));      // prénom et date d'arrivée, pour la page Équipe
        }
      } finally { verrouB.releaseLock(); }
      if (rang) {
        var nc = formaterNouveauCompte(moi.nom, rang);
        try { envoyerCourriel(nc.sujet, nc.corps); } catch (errMail) { console.error(raisonCourriel(errMail)); }    // le compte est compté même si le courriel échoue
      }
      return reponse({ ok: true, nouveau: !!rang });
    }

    if (action === 'avis') {
      var av = validerAvis(q.note, q.texte);
      if (!av.ok) return reponse({ ok: false, erreur: av.raison });
      var cacheA = CacheService.getScriptCache(), cleAv = 'av:' + moi.empreinte.slice(7, 23);
      if (!avisAutorise(cacheA.get(cleAv))) return reponse({ ok: false, erreur: 'trop d\'avis pour le moment : réessayez plus tard' });
      var fa = formaterAvis(moi.nom, moi.role, av.note, av.texte);
      try { envoyerCourriel(fa.sujet, fa.corps); } catch (errMail2) { console.error(raisonCourriel(errMail2)); return reponse({ ok: false, erreur: raisonCourriel(errMail2) }); }
      cacheA.put(cleAv, String((Number(cacheA.get(cleAv)) || 0) + 1), 21600);
      return reponse({ ok: true });
    }

    if (action === 'noter') {
      var nt = validerNote(q.livre, q.note);
      if (!nt.ok) return reponse({ ok: false, erreur: nt.raison });
      var verrou = LockService.getScriptLock(), resultatNote;
      verrou.waitLock(10000);
      try {
        var ap = appliquerNote(lireVotes(nt.livre), votant(moi.empreinte), nt.note);
        if (!ap.ok) return reponse({ ok: false, erreur: ap.raison });
        if (Object.keys(ap.votes).length) PropertiesService.getScriptProperties().setProperty(cleNote(nt.livre), JSON.stringify(ap.votes));
        else PropertiesService.getScriptProperties().deleteProperty(cleNote(nt.livre));
        resultatNote = resumerNotes(ap.votes);
      } finally { verrou.releaseLock(); }
      CacheService.getScriptCache().remove('notes');
      return reponse({ ok: true, moyenne: resultatNote[0], nombre: resultatNote[1], note: nt.note });
    }

    if (action === 'mes_notes') {                  // les notes données par la personne connectée : { livre: note }
      var toutes = PropertiesService.getScriptProperties().getProperties(), qui = votant(moi.empreinte), miennes = {};
      Object.keys(toutes).forEach(function (k) {
        if (k.indexOf(PREFIXE_NOTE) !== 0) return;
        try { var vv = JSON.parse(toutes[k]); if (vv[qui]) miennes[k.slice(PREFIXE_NOTE.length)] = vv[qui]; } catch (e) { /* propriété abîmée : ignorée */ }
      });
      return reponse({ ok: true, notes: miennes });
    }

    if (action === 'equipe_lire') {
      var eq = v.admins.contenu.equipe || {};
      return reponse({ ok: true, equipe: Object.keys(eq).map(function (k) { return { empreinte: k, nom: eq[k].nom, role: eq[k].role }; }), bloques: v.admins.contenu.bloques || [] });
    }

    if (action === 'comptes_lire') {               // SuperAdmin : total, arrivées du jour et prénoms (comptes arrivés depuis l'ajout de cette liste)
      var tout = PropertiesService.getScriptProperties().getProperties(), vals = [];
      Object.keys(tout).forEach(function (k) { if (/^un:\d+$/.test(k)) vals.push({ rang: Number(k.slice(3)), valeur: tout[k] }); });
      var lc = listerComptes(vals, Utilities.formatDate(new Date(), 'Europe/Paris', 'yyyy-MM-dd'), 300);
      return reponse({ ok: true, total: Number(tout['u:total']) || 0, aujourdhui: lc.aujourdhui, connus: lc.connus, liste: lc.liste });
    }

    if (action === 'equipe_ajouter' || action === 'equipe_retirer' || action === 'equipe_bloquer') {
      var cible = q.adresse ? empreinteDe(minuscules(q.adresse)) : String(q.empreinte || '');
      var res = action === 'equipe_ajouter' ? ajouterMembre(v.admins.contenu, cible, q.nom, String(q.role || 'admin'), moi.empreinte)
        : action === 'equipe_retirer' ? retirerMembre(v.admins.contenu, cible, moi.empreinte)
        : bloquerCompte(v.admins.contenu, cible, moi.empreinte);
      if (!res.ok) return reponse({ ok: false, erreur: res.raison });
      ecrireAdmins(res.fichier, v.admins.sha, 'Équipe : ' + action.replace('equipe_', '') + ' par ' + moi.nom);
      return reponse({ ok: true });
    }
    return reponse({ ok: false, erreur: 'action inconnue' });
  } catch (err) {
    console.error(String(err && err.stack || err));                    // visible dans « Exécutions » d'Apps Script, jamais renvoyé au site
    return reponse({ ok: false, erreur: 'erreur du relais' });
  }
}

/* ---------- Courriels à l'éditeur ---------- */
// Destinataire : la propriété du script EMAIL_EDITEUR si elle existe, sinon le compte propriétaire du script
function envoyerCourriel(sujet, corps) {
  var dest = prop('EMAIL_EDITEUR') || Session.getEffectiveUser().getEmail();
  if (!dest) throw new Error('adresse du destinataire introuvable');
  MailApp.sendEmail({ to: dest, subject: sujet, body: corps, name: 'La Cote du Héros' });
}
function raisonCourriel(err) { return 'courriel impossible (' + String(err && err.message || err).replace(/[\r\n]+/g, ' ').slice(0, 140) + ')'; }

/* ---------- Notes des livres ---------- */
var PREFIXE_NOTE = 'n:';
function cleNote(livre) { return PREFIXE_NOTE + livre; }
function lireVotes(livre) {
  var t = prop(cleNote(livre));
  try { return t ? JSON.parse(t) : {}; } catch (e) { return {}; }
}
/* Moyennes publiques : { livre: [moyenne, nombre] }, gardées dix minutes en mémoire */
function notesPubliques() {
  var cache = CacheService.getScriptCache(), connu = cache.get('notes');
  if (connu) return JSON.parse(connu);
  var toutes = PropertiesService.getScriptProperties().getProperties(), resume = {};
  Object.keys(toutes).forEach(function (k) {
    if (k.indexOf(PREFIXE_NOTE) !== 0) return;
    try { resume[k.slice(PREFIXE_NOTE.length)] = resumerNotes(JSON.parse(toutes[k])); } catch (e) { /* propriété abîmée : ignorée */ }
  });
  cache.put('notes', JSON.stringify(resume), 600);
  return resume;
}

/* À lancer UNE FOIS à la main dans l'éditeur Apps Script (menu en haut : choisir « autoriser », puis Exécuter) :
   Google demande alors l'autorisation d'envoyer des courriels depuis votre compte, nécessaire aux nouveaux comptes et aux avis. */
function autoriser() {
  MailApp.getRemainingDailyQuota();
  Session.getEffectiveUser().getEmail();
}

/* Pour vérifier l'envoi : choisir « testerCourriel » dans l'éditeur, Exécuter. Le journal affiche l'adresse du destinataire, et un courriel de test part. */
function testerCourriel() {
  Logger.log('Destinataire : ' + (prop('EMAIL_EDITEUR') || Session.getEffectiveUser().getEmail()));
  envoyerCourriel('Test du relais La Cote du Héros', 'Si vous lisez ce message, l\'envoi de courriels fonctionne.');
  Logger.log('Courriel envoyé. Quota restant aujourd\'hui : ' + MailApp.getRemainingDailyQuota());
}

function doGet(e) {
  if (e && e.parameter && e.parameter.notes) return reponse({ ok: true, notes: notesPubliques() });      // lecture publique : pas de connexion
  return reponse({ ok: true, service: 'relais La Cote du Héros' });
}
