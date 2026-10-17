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
  var r = UrlFetchApp.fetch('https://oauth2.googleapis.com/tokeninfo?id_token=' + encodeURIComponent(jeton), { muteHttpExceptions: true });
  var infos = {}; try { infos = JSON.parse(r.getContentText()); } catch (e) { /* réponse illisible : refus plus bas */ }
  var admins = lireAdmins();
  return { identite: decider(infos, admins.contenu, prop('CLIENT_ID'), empreinteDe, Math.floor(Date.now() / 1000)), admins: admins };
}

function doPost(e) {
  try {
    var q = JSON.parse(e.postData.contents || '{}');
    var v = verifierConnexion(String(q.jeton || ''));
    if (!v.identite.ok) return reponse({ ok: false, erreur: v.identite.raison });
    var moi = v.identite, action = String(q.action || '');
    if (!peut(moi.role, action)) return reponse({ ok: false, erreur: 'droits insuffisants', role: moi.role });

    if (action === 'moi') return reponse({ ok: true, role: moi.role, nom: moi.nom });

    if (action === 'envoyer') {
      var lot = validerEnvoi(String(q.lot || ''), q.entrees);
      if (!lot.ok) return reponse({ ok: false, erreur: lot.raison });
      lot.entrees.auteur = moi.nom;
      var r = github('/actions/workflows/' + encodeURIComponent(q.lot) + '/dispatches', { method: 'post', payload: { ref: 'main', inputs: lot.entrees } });
      return reponse(r.code === 204 ? { ok: true } : { ok: false, erreur: 'GitHub a refusé le lancement (' + r.code + ')' });
    }

    if (action === 'equipe_lire') {
      var eq = v.admins.contenu.equipe || {};
      return reponse({ ok: true, equipe: Object.keys(eq).map(function (k) { return { empreinte: k, nom: eq[k].nom, role: eq[k].role }; }), bloques: v.admins.contenu.bloques || [] });
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
    return reponse({ ok: false, erreur: 'erreur du relais' });
  }
}

function doGet() { return reponse({ ok: true, service: 'relais La Cote du Héros' }); }
