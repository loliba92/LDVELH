/* Notes des livres : une note de 1 à 5 par compte et par livre (le livre, toutes éditions confondues). La moyenne est visible de tous ;
   seuls les comptes connectés notent. Les notes vivent dans le relais (dossier relais/) : le site ne garde que la moyenne et la note de la personne. */
window.Notes = (function () {
  var MOY = {}, MIENNES = {}, chargees = false, miennesChargees = false, zone = null, livreOuvert = '';
  var CLE = 'cdh-notes', DUREE = 10 * 60 * 1000;
  var esc = function (t) { return String(t == null ? '' : t).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
  var virgule = function (x) { return String(x).replace('.', ','); };
  var actifRelais = function () { return !!window.Relais && window.Relais.configure(); };
  var connecte = function () { return !!window.Cloud && window.Cloud.actif() && !!window.Relais && window.Relais.actif(); };
  var signaler = function () { document.dispatchEvent(new CustomEvent('cdh-notes')); };

  function lireCache() { try { var c = JSON.parse(sessionStorage.getItem(CLE)); if (c && Date.now() - c.t < DUREE) return c.n; } catch (e) { /* mémoire d'onglet indisponible */ } return null; }
  function ecrireCache() { try { sessionStorage.setItem(CLE, JSON.stringify({ t: Date.now(), n: MOY })); } catch (e) { /* sans effet */ } }

  function charger() {
    var c = lireCache();
    if (c) { MOY = c; chargees = true; signaler(); }
    if (!window.Relais) return;
    window.Relais.lireNotes().then(function (r) {
      if (r && r.ok && r.notes && typeof r.notes === 'object') { MOY = r.notes; chargees = true; ecrireCache(); signaler(); }   // un relais pas encore mis à jour ne répond pas « notes » : rien ne s'affiche
    }).catch(function () { /* hors ligne : les étoiles n'apparaissent pas */ });
  }
  function chargerMiennes() {
    if (miennesChargees || !connecte()) return;
    miennesChargees = true;
    window.Relais.appeler('mes_notes').then(function (r) {
      if (r && r.ok) { MIENNES = r.notes || {}; signaler(); } else miennesChargees = false;
    }).catch(function () { miennesChargees = false; });
  }
  // La connexion change (connexion, expiration, déconnexion) : on relit ou on oublie les notes de la personne
  document.addEventListener('cdh-compte', function (e) {
    var etat = e.detail && e.detail.etat;
    if (etat === 'deconnecte') { MIENNES = {}; miennesChargees = false; signaler(); }
    else if (connecte()) chargerMiennes();
  });

  /* ---------- Affichage ---------- */
  function etoiles(moyenne) { return '<span class="etoiles" style="--p:' + Math.round(moyenne / 5 * 100) + '%" aria-hidden="true">★★★★★</span>'; }
  function resume(livre) {
    var m = MOY[livre];
    if (!m || !m[1]) return '<span class="note-vide">Pas encore noté</span>';
    return etoiles(m[0]) + ' <strong>' + virgule(m[0]) + '</strong><span class="note-sur"> sur 5</span> <span class="note-nb">· ' + m[1] + ' avis</span>';
  }
  // Petite note sur la carte d'un livre dans l'étagère (rien tant que personne n'a noté)
  function carte(livre) {
    var m = MOY[livre];
    return m && m[1] ? '<span class="note-carte" title="' + virgule(m[0]) + ' sur 5, ' + m[1] + ' avis"><span aria-hidden="true">★</span> ' + virgule(m[0]) + '<span class="sr-only"> sur 5, ' + m[1] + ' avis</span></span>' : '';
  }
  function saisie(livre) {
    if (!actifRelais()) return '';
    if (connecte()) {
      var mienne = MIENNES[livre] || 0;
      return '<div class="note-saisie"><span class="note-etiquette" id="note-et">Votre note</span><span class="note-boutons" role="radiogroup" aria-labelledby="note-et">' +
        [1, 2, 3, 4, 5].map(function (n) {
          return '<button type="button" role="radio" aria-checked="' + (mienne === n) + '" data-note="' + n + '" class="' + (n <= mienne ? 'allumee' : '') + '" aria-label="' + n + ' sur 5">★</button>';
        }).join('') + '</span>' + (mienne ? '<button type="button" class="bouton-lien" data-note-retirer>Retirer ma note</button>' : '') + '</div>';
    }
    if (window.Cloud && window.Cloud.lie()) return '<div class="note-saisie"><button type="button" class="bouton-lien" data-compte="connecter">Reconnectez-vous pour noter ce livre</button></div>';
    return '<div class="note-saisie"><button type="button" class="bouton-lien" data-compte="connecter">Se connecter avec Google pour noter ce livre</button></div>';
  }
  function dessiner() {
    if (!zone || !zone.isConnected) return;
    var msg = zone.querySelector('.note-msg'), texte = msg ? msg.textContent : '';
    zone.hidden = !actifRelais() || !chargees;
    zone.innerHTML = '<div class="note-resume">' + resume(livreOuvert) + '</div>' + saisie(livreOuvert) + '<p class="sous note-msg" role="status"' + (texte ? '' : ' hidden') + '>' + esc(texte) + '</p>';
  }
  document.addEventListener('cdh-notes', dessiner);

  function dire(texte, erreur) {
    var m = zone && zone.querySelector('.note-msg'); if (!m) return;
    m.textContent = texte; m.hidden = !texte; m.classList.toggle('erreur', !!erreur);
  }
  function lisible(r) {
    var e = (r && r.erreur) || 'erreur inconnue';
    return /expir|jeton/.test(e) ? 'Votre connexion a expiré : reconnectez-vous avec le bouton du compte, puis recommencez.' : e.charAt(0).toUpperCase() + e.slice(1) + '.';
  }
  function noter(note) {
    var livre = livreOuvert, ancienne = MIENNES[livre] || 0;
    if (note === ancienne) return;                                   // même note : rien à envoyer
    if (note) MIENNES[livre] = note; else delete MIENNES[livre];     // affichage immédiat, annulé si le relais refuse
    dessiner(); dire('Enregistrement…');
    window.Relais.appeler('noter', { livre: livre, note: note }).then(function (r) {
      if (r && r.ok) {
        if (r.nombre) MOY[livre] = [r.moyenne, r.nombre]; else delete MOY[livre];
        ecrireCache(); dessiner(); dire(note ? 'Merci, votre note est enregistrée.' : 'Votre note est retirée.'); signaler();
      } else { retour(livre, ancienne); dire(lisible(r), true); }
    }).catch(function () { retour(livre, ancienne); dire('Le service ne répond pas : vérifiez votre connexion.', true); });
  }
  function retour(livre, ancienne) { if (ancienne) MIENNES[livre] = ancienne; else delete MIENNES[livre]; dessiner(); }

  // Affiche le bloc de notes d'un livre dans la zone donnée (fiche ouverte)
  function rendre(z, livre) {
    zone = z; livreOuvert = livre;
    if (!z) return;
    z.onclick = function (e) {
      var b = e.target.closest('[data-note]'), r = e.target.closest('[data-note-retirer]');
      if (b) noter(Number(b.dataset.note)); else if (r) noter(0);
    };
    chargerMiennes(); dessiner();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', charger); else charger();
  return { rendre: rendre, carte: carte };
})();
