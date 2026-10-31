// Version du 2026-10-31 16:58 (heure de Paris) : retrait du rattachement par prénom ; promotion d'un héros en sorcier depuis la liste des comptes (equipe_promouvoir, sans adresse).
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

/* Compte arrivé avant la version qui garde l'empreinte : rattaché à sa ligne seulement s'il n'y en a qu'une (prénom et signes). */
function rattacherEmpreinte(props, nom, empreinte) {
  if (!/#[0-9a-f]{4}$/.test(nettoyerNom(nom))) return;
  var tout = props.getProperties(), vals = [];
  Object.keys(tout).forEach(function (k) { if (/^un:\d+$/.test(k) && !tout['ue:' + k.slice(3)]) vals.push({ rang: Number(k.slice(3)), valeur: tout[k] }); });
  var rangs = rangsSansEmpreinte(vals, nom);
  if (rangs.length === 1) props.setProperty('ue:' + rangs[0], empreinte);
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
  if (r.code !== 200 && r.code !== 201) { CacheService.getScriptCache().remove('admins'); throw new Error('écriture refusée (' + r.code + ')'); }
  // La liste qui vient d'être écrite devient la version connue (30 s) : relire GitHub tout de suite pourrait renvoyer l'ancienne.
  try { CacheService.getScriptCache().put('admins', JSON.stringify({ contenu: contenu, sha: JSON.parse(r.texte).content.sha }), 30); }
  catch (e) { CacheService.getScriptCache().remove('admins'); }
}

function verifierConnexion(jeton) {
  var champ = /^ya29\./.test(jeton) ? 'access_token' : 'id_token';        // le site envoie un jeton d'accès (ya29.…)
  // La réponse de Google est gardée 5 minutes (sous une empreinte du jeton) : les appels qui se suivent (niveau, Butin, notes…) ne redemandent pas à Google.
  // L'expiration du jeton reste vérifiée à chaque appel par decider(), et la liste des admins est relue à chaque fois (30 s de cache).
  var cache = CacheService.getScriptCache(), cleGoogle = 'ti:' + empreinteDe(jeton).slice(7, 47), infos = null;
  try { var connu = cache.get(cleGoogle); if (connu) infos = JSON.parse(connu); } catch (e) { infos = null; }
  if (!infos) {
    var r = UrlFetchApp.fetch('https://oauth2.googleapis.com/tokeninfo?' + champ + '=' + encodeURIComponent(jeton), { muteHttpExceptions: true });
    try { infos = JSON.parse(r.getContentText()); } catch (e) { infos = {}; /* réponse illisible : refus plus bas */ }
    if (r.getResponseCode() === 200 && infos && infos.aud) { try { cache.put(cleGoogle, JSON.stringify(infos), 300); } catch (e) { /* trop gros ou cache indisponible */ } }
  }
  var admins = lireAdmins();
  return { identite: decider(infos, admins.contenu, prop('CLIENT_ID'), empreinteDe, Math.floor(Date.now() / 1000)), admins: admins };
}

/* À brancher sur un déclencheur « toutes les 5 minutes » (relais/LISEZMOI.md) : garde le service éveillé et la liste des admins en mémoire.
   L'effet sur la rapidité n'est pas garanti par Google : à constater à l'usage. */
function garderEveille() { try { lireAdmins(); } catch (e) { /* tant pis */ } }

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
    if (q.action === 'ping') return reponse({ ok: true });                  // réveille le service, sans aucune donnée
    if (/^session_/.test(String(q.action || ''))) return reponse(gererSession(q));
    var v = verifierConnexion(String(q.jeton || ''));
    if (!v.identite.ok) return reponse({ ok: false, erreur: v.identite.raison });
    var moi = v.identite, action = String(q.action || '');
    if (!peut(moi.role, action)) return reponse({ ok: false, erreur: 'droits insuffisants', role: moi.role });

    if (action === 'moi') return reponse({ ok: true, role: moi.role, nom: moi.nom, fin: moi.fin || '' });

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

    if (action === 'indice_lire') {      // indice de marché par version et éditeur : le Zagor seulement, suivi interne
      var ind = github('/contents/data/processed/indice-marche.json?ref=main');
      if (ind.code !== 200) return reponse({ ok: false, erreur: 'indice indisponible (' + ind.code + ')' });
      var fic = JSON.parse(ind.texte);
      return reponse({ ok: true, indice: JSON.parse(Utilities.newBlob(Utilities.base64Decode(fic.content.replace(/\n/g, ''))).getDataAsString('UTF-8')) });
    }

    if (action === 'butin_lire' || action === 'annonces_lire') {      // Butin seul pour les sorciers ; toutes les annonces pour le Zagor
      var ann = github('/contents/data/processed/' + (action === 'annonces_lire' ? 'annonces' : 'butin') + '.json?ref=main');
      if (ann.code !== 200) return reponse({ ok: false, erreur: 'annonces indisponibles (' + ann.code + ')' });
      var fic = JSON.parse(ann.texte);
      return reponse({ ok: true, annonces: JSON.parse(Utilities.newBlob(Utilities.base64Decode(fic.content.replace(/\n/g, ''))).getDataAsString('UTF-8')) });
    }

    if (action === 'pepite_offrir' || action === 'pepite_retirer' || action === 'pepite_vendre') {      // pépite du jour : fichier public lu par tous les Héros
      var chemin = '/contents/web/data/pepite-du-jour.json', contenuPep = {};
      if (action === 'pepite_offrir') {
        var vp = validerPepite(q);
        if (!vp.ok) return reponse({ ok: false, erreur: vp.raison });
        contenuPep = vp.pepite; contenuPep.date = Utilities.formatDate(new Date(), 'Europe/Paris', 'yyyy-MM-dd');
      }
      var actuel = github(chemin + '?ref=main'), shaPep = actuel.code === 200 ? JSON.parse(actuel.texte).sha : undefined;
      if (action === 'pepite_vendre') {                                     // on garde la pépite et on la marque vendue
        if (actuel.code !== 200) return reponse({ ok: false, erreur: 'pépite introuvable' });
        var fichierPep = JSON.parse(actuel.texte);
        contenuPep = JSON.parse(Utilities.newBlob(Utilities.base64Decode(fichierPep.content.replace(/\n/g, ''))).getDataAsString('UTF-8'));
        if (!contenuPep.isbn13) return reponse({ ok: false, erreur: 'aucune pépite à marquer' });
        contenuPep.vendue = true;
      }
      var libelle = action === 'pepite_offrir' ? contenuPep.isbn13 : action === 'pepite_vendre' ? 'vendue' : 'retirée';
      var ecrit = github(chemin, { method: 'put', payload: { message: 'Pépite du jour : ' + libelle + ' par ' + moi.nom, branch: 'main', sha: shaPep,
        content: Utilities.base64Encode(JSON.stringify(contenuPep, null, 2) + '\n', Utilities.Charset.UTF_8) } });
      if (ecrit.code !== 200 && ecrit.code !== 201) return reponse({ ok: false, erreur: 'écriture refusée (' + ecrit.code + ')' });
      return reponse({ ok: true });
    }

    if (action === 'envoyer') {
      if (String(q.lot || '') === 'communaute.yml' && moi.role !== 'superadmin') return reponse({ ok: false, erreur: 'réservé au Zagor' });
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
          props.setProperty('ue:' + rang, moi.empreinte);                                                                              // empreinte, gardée côté relais seulement (jamais envoyée au site)
        }
        rattacherEmpreinte(props, moi.nom, moi.empreinte);                                                                             // comptes arrivés avant cette version : rattachés à leur ligne
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

    if (action === 'aimer_lien') {                 // « j'aime » sur un lien de la Communauté : un par personne, on peut le retirer
      var li = validerLien(q.adresse);
      if (!li.ok) return reponse({ ok: false, erreur: li.raison });
      var verrouLien = LockService.getScriptLock(), resultatLien;
      verrouLien.waitLock(10000);
      try {
        var cleLien = cleLike(li.adresse), votesLien = lireLikes(cleLien), qui = votant(moi.empreinte);
        if (q.aime === false || q.aime === 'non') delete votesLien.votes[qui]; else votesLien.votes[qui] = 1;
        if (!votesLien.adresse) votesLien.adresse = li.adresse;
        if (Object.keys(votesLien.votes).length) PropertiesService.getScriptProperties().setProperty(cleLien, JSON.stringify(votesLien));
        else PropertiesService.getScriptProperties().deleteProperty(cleLien);
        resultatLien = { ok: true, nombre: Object.keys(votesLien.votes).length, aime: !!votesLien.votes[qui] };
      } finally { verrouLien.releaseLock(); }
      CacheService.getScriptCache().remove('likes');
      return reponse(resultatLien);
    }

    if (action === 'mes_likes') {                  // les liens aimés par la personne connectée : [adresse]
      var tousLikes = PropertiesService.getScriptProperties().getProperties(), moi2 = votant(moi.empreinte), aimes = [];
      Object.keys(tousLikes).forEach(function (k) {
        if (k.indexOf(PREFIXE_LIKE) !== 0) return;
        try { var vl = JSON.parse(tousLikes[k]); if (vl.votes && vl.votes[moi2]) aimes.push(vl.adresse); } catch (e) { /* propriété abîmée : ignorée */ }
      });
      return reponse({ ok: true, adresses: aimes });
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
      var eq = v.admins.contenu.equipe || {}, auj = jourDe(Math.floor(Date.now() / 1000));
      return reponse({ ok: true, aujourdhui: auj, equipe: Object.keys(eq).map(function (k) { return { empreinte: k, nom: eq[k].nom, role: eq[k].role, depuis: eq[k].depuis || '', debut: eq[k].debut || '', fin: eq[k].fin || '', echu: estEchu(eq[k], auj), avenir: estAVenir(eq[k], auj) }; }), bloques: v.admins.contenu.bloques || [] });
    }

    if (action === 'comptes_lire') {               // SuperAdmin : total, arrivées du jour et prénoms (comptes arrivés depuis l'ajout de cette liste)
      var tout = PropertiesService.getScriptProperties().getProperties(), vals = [];
      Object.keys(tout).forEach(function (k) { if (/^un:\d+$/.test(k)) vals.push({ rang: Number(k.slice(3)), valeur: tout[k] }); });
      var lc = listerComptes(vals, Utilities.formatDate(new Date(), 'Europe/Paris', 'yyyy-MM-dd'), 300);
      lc.liste.forEach(function (c) { c.promouvable = !!tout['ue:' + c.rang]; });       // le bouton « Passer sorcier » n'apparaît que pour ces comptes
      return reponse({ ok: true, total: Number(tout['u:total']) || 0, aujourdhui: lc.aujourdhui, connus: lc.connus, liste: lc.liste });
    }

    if (action === 'equipe_promouvoir') {          // SuperAdmin : un héros de la liste devient sorcier, sur une période (fin obligatoire)
      var propsP = PropertiesService.getScriptProperties(), rangP = Number(q.rang) || 0;
      var empP = propsP.getProperty('ue:' + rangP), ligneP = propsP.getProperty('un:' + rangP);
      if (!empP || !ligneP) return reponse({ ok: false, erreur: 'compte introuvable ou trop ancien pour être promu ici' });
      if (!String(q.fin || '').trim()) return reponse({ ok: false, erreur: 'indiquez la date de fin' });
      var resP = ajouterMembre(v.admins.contenu, empP, ligneP.split('|')[0], 'admin', moi.empreinte, q.fin, jourDe(Math.floor(Date.now() / 1000)), q.debut);
      if (!resP.ok) return reponse({ ok: false, erreur: resP.raison });
      ecrireAdmins(resP.fichier, v.admins.sha, 'Équipe : promotion en sorcier par ' + moi.nom);
      return reponse({ ok: true });
    }

    if (action === 'equipe_ajouter' || action === 'equipe_retirer' || action === 'equipe_bloquer' || action === 'equipe_periode') {
      var cible = q.adresse ? empreinteDe(minuscules(q.adresse)) : String(q.empreinte || ''), aujourd = jourDe(Math.floor(Date.now() / 1000));
      var res = action === 'equipe_ajouter' ? ajouterMembre(v.admins.contenu, cible, q.nom, String(q.role || 'admin'), moi.empreinte, q.fin, aujourd, q.debut)
        : action === 'equipe_retirer' ? retirerMembre(v.admins.contenu, cible, moi.empreinte)
        : action === 'equipe_periode' ? changerPeriode(v.admins.contenu, cible, q.debut, q.fin, aujourd)
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

var PREFIXE_LIKE = 'l:';
function cleLike(adresse) { return PREFIXE_LIKE + empreinteDe(adresse).slice(7, 23); }
function lireLikes(cle) {
  var t = prop(cle);
  try { return t ? JSON.parse(t) : { votes: {} }; } catch (e) { return { votes: {} }; }
}
/* Nombres de « j'aime » par lien : { adresse: nombre }, gardés dix minutes en mémoire */
function likesPublics() {
  var cache = CacheService.getScriptCache(), connu = cache.get('likes');
  if (connu) return JSON.parse(connu);
  var toutes = PropertiesService.getScriptProperties().getProperties(), resume = {};
  Object.keys(toutes).forEach(function (k) {
    if (k.indexOf(PREFIXE_LIKE) !== 0) return;
    try { var vl = JSON.parse(toutes[k]); resume[vl.adresse] = Object.keys(vl.votes || {}).length; } catch (e) { /* propriété abîmée : ignorée */ }
  });
  cache.put('likes', JSON.stringify(resume), 600);
  return resume;
}

function doGet(e) {
  if (e && e.parameter && e.parameter.likes) return reponse({ ok: true, likes: likesPublics() });       // lecture publique : pas de connexion
  if (e && e.parameter && e.parameter.notes) return reponse({ ok: true, notes: notesPubliques() });      // lecture publique : pas de connexion
  return reponse({ ok: true, service: 'relais La Cote du Héros' });
}
