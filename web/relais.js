/* Envois vers GitHub par le relais (dossier relais/) : le site transmet la connexion Google de la personne, le relais vérifie son niveau
   (Héros, Admin, SuperAdmin) dans data/admins.json puis lance lui-même le lot. La clé GitHub n'est jamais dans le navigateur.
   Actif quand web/data/admin-config.json contient « relais_url » ; sinon l'ancien envoi par clé continue de fonctionner. */
window.Relais = (function () {
  var URL_RELAIS = '';
  if (window.Identite) window.Identite.config().then(function (c) { URL_RELAIS = (c && c.relais_url) || ''; });

  function actif() { return !!URL_RELAIS && !!window.Identite && window.Identite.connecte(); }
  function configure() { return !!URL_RELAIS; }

  // Le corps part en « text/plain » : c'est ce qui évite la pré-vérification CORS, que les scripts Google n'acceptent pas.
  function appeler(action, params) {
    var corps = Object.assign({ action: action, jeton: window.Identite ? window.Identite.jeton() : '' }, params || {});
    return fetch(URL_RELAIS, { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify(corps) })
      .then(function (r) { return r.json(); });
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
  return { actif: actif, configure: configure, appeler: appeler, envoyerLot: envoyerLot };
})();
