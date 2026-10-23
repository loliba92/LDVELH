/* Envois vers GitHub par le relais (dossier relais/) : le site transmet la connexion Google de la personne, le relais vérifie son niveau
   (Héros, Admin, Zagor) dans data/admins.json puis lance lui-même le lot. La clé GitHub n'est jamais dans le navigateur.
   Actif quand web/data/admin-config.json contient « relais_url » ; sinon l'ancien envoi par clé continue de fonctionner. */
window.Relais = (function () {
  var URL_RELAIS = '';
  var pret = window.Identite ? window.Identite.config().then(function (c) { URL_RELAIS = (c && c.relais_url) || ''; }) : Promise.resolve();

  // Preuve de connexion : celle du compte Google du site (Cloud), à défaut celle de l'ancienne porte admin (Identite)
  function preuve() { return (window.Cloud && window.Cloud.preuve()) || (window.Identite ? window.Identite.jeton() : ''); }
  function actif() { return !!URL_RELAIS && !!preuve(); }
  function configure() { return !!URL_RELAIS; }

  // Le corps part en « text/plain » : c'est ce qui évite la pré-vérification CORS, que les scripts Google n'acceptent pas.
  function appeler(action, params) {
    var corps = Object.assign({ action: action, jeton: preuve() }, params || {});
    // Sans réponse au bout de 40 s, l'appel échoue : l'écran n'affiche plus « en cours » pour toujours (les validations restent gardées)
    var ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var minute = setTimeout(function () { if (ctl) ctl.abort(); }, 40000);
    return fetch(URL_RELAIS, { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify(corps), signal: ctl ? ctl.signal : undefined })
      .then(function (r) { clearTimeout(minute); return r.json(); }, function (e) { clearTimeout(minute); throw e; });
  }

  // Même forme de réponse que l'ancien envoi direct : { status } (204 = lancé)
  function envoyerLot(lot, entrees) {
    return appeler('envoyer', { lot: lot, entrees: entrees }).then(function (r) {
      if (r.ok) return { status: 204 };
      if (r.erreur === 'droits insuffisants') return { status: 403, erreur: r.erreur };
      if (/expirée|jeton/.test(r.erreur || '')) return { status: 401, erreur: r.erreur };
      return { status: 400, erreur: r.erreur };
    });
  }
  // Moyennes des notes : lecture publique, sans connexion. Renvoie { ok, notes: { livre: [moyenne, nombre] } } ou null si le relais n'est pas configuré.
  function lireNotes() {
    return pret.then(function () { return URL_RELAIS ? fetch(URL_RELAIS + '?notes=1').then(function (r) { return r.json(); }) : null; });
  }
  return { preuve: preuve, actif: actif, configure: configure, appeler: appeler, envoyerLot: envoyerLot, lireNotes: lireNotes, pret: pret };
})();
