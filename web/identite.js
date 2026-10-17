/* Identité des administrateurs : connexion avec Google.
   Le bouton remet à la page un jeton signé par Google (valable environ une heure). Il est joint aux envois (champ « identite ») :
   c'est le lot GitHub qui le vérifie et qui décide si l'adresse est autorisée (data/admins.json, voir pipeline/identite.py).
   Le nom lu ici dans le jeton ne sert qu'à l'affichage. Tant que web/data/admin-config.json n'a pas de « client_id »,
   rien n'est demandé. */
window.Identite = (function () {
  var CLE = 'cdh-google';
  var chargement = null;

  function config() {
    if (!chargement) chargement = fetch('data/admin-config.json', { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; });
    return chargement;
  }
  function decoder(jwt) {
    try { return JSON.parse(decodeURIComponent(escape(atob(jwt.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))))); } catch (e) { return null; }
  }
  function lire() {
    try { var v = JSON.parse(localStorage.getItem(CLE) || 'null'); return v && v.exp * 1000 > Date.now() + 60000 ? v : null; } catch (e) { return null; }
  }
  function jeton() { var v = lire(); return v ? v.jwt : ''; }
  function nom() { var v = lire(); return v ? v.nom : ''; }
  function actif() { return config().then(function (c) { return !!c.client_id; }); }
  function sortir() { try { localStorage.removeItem(CLE); } catch (e) { /* rien à retirer */ } }

  function recu(reponse) {
    var p = decoder(reponse.credential);
    if (!p) return;
    var nomAffiche = p.given_name || p.name || String(p.email || '').split('@')[0];
    try { localStorage.setItem(CLE, JSON.stringify({ jwt: reponse.credential, nom: nomAffiche, exp: p.exp })); } catch (e) { /* stockage indisponible */ }
  }

  function chargerGoogle() {
    return new Promise(function (ok, ko) {
      if (window.google && window.google.accounts) return ok();
      var s = document.createElement('script');
      s.src = 'https://accounts.google.com/gsi/client'; s.async = true;
      s.onload = ok; s.onerror = ko;
      document.head.appendChild(s);
    });
  }

  // Remplit `zone` : le nom de la personne connectée, ou le bouton Google. `aChange` est rappelé après chaque connexion ou déconnexion.
  function afficher(zone, aChange) {
    actif().then(function (oui) {
      if (!oui) { zone.hidden = true; return; }
      zone.hidden = false;
      var v = lire();
      zone.textContent = '';
      var p = document.createElement('p'); p.className = 'sous';
      if (v) {
        p.innerHTML = 'Connecté avec Google : <strong></strong>. ';
        p.querySelector('strong').textContent = v.nom;
        var b = document.createElement('button'); b.type = 'button'; b.className = 'bouton-lien'; b.textContent = 'Changer de compte';
        b.addEventListener('click', function () { sortir(); afficher(zone, aChange); if (aChange) aChange(); });
        p.appendChild(b); zone.appendChild(p);
        return;
      }
      p.textContent = 'Pour envoyer des mises à jour, connectez-vous avec votre compte Google : votre nom sera enregistré avec elles.';
      var bouton = document.createElement('div');
      zone.appendChild(p); zone.appendChild(bouton);
      Promise.all([config(), chargerGoogle()]).then(function (r) {
        window.google.accounts.id.initialize({ client_id: r[0].client_id, callback: function (rep) { recu(rep); afficher(zone, aChange); if (aChange) aChange(); }, auto_select: true });
        window.google.accounts.id.renderButton(bouton, { theme: 'filled_black', size: 'large', text: 'signin_with', locale: 'fr' });
      }).catch(function () { p.textContent = 'La connexion Google n\'a pas pu se charger : vérifiez votre connexion puis rechargez la page.'; });
    });
  }

  // Avant un envoi : jeton valable, ou null (avec la phrase à montrer) si une connexion est demandée et absente
  function pourEnvoi() {
    return actif().then(function (oui) {
      if (!oui) return { ok: true, jeton: '' };
      var j = jeton();
      return j ? { ok: true, jeton: j } : { ok: false, jeton: '', message: 'Connectez-vous d\'abord avec Google (en haut de la page « Vérifier les prix ») : la connexion dure environ une heure.' };
    });
  }
  return { afficher: afficher, pourEnvoi: pourEnvoi, nom: nom, jeton: jeton, actif: actif };
})();
