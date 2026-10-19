/* Formulaire de contact : le message part sans quitter la page. Voie principale : le relais Google (courriel envoyé à l'éditeur, sans
   service tiers). Tant que le relais ne connaît pas encore le contact, ou s'il ne répond pas, repli sur le service FormSubmit, puis sur
   l'envoi classique du formulaire (retour sur cette page avec ?envoye=1). L'adresse de l'éditeur n'apparaît nulle part sur le site. */
(function () {
  var form = document.getElementById('contact-form');
  var etat = document.getElementById('form-sent');
  if (!form || !etat) return;
  var dire = function (texte, erreur) {
    etat.textContent = texte;
    etat.hidden = false;
    etat.classList.toggle('erreur', !!erreur);
    etat.scrollIntoView({ block: 'center', behavior: 'smooth' });
  };
  var MERCI = 'Merci, votre message est bien parti. Je vous répondrai à l\'adresse indiquée. ✓';
  if (/[?&]envoye=1/.test(location.search)) dire('Merci, votre message est bien parti. ✓');
  if (!window.fetch) return;

  var avecDelai = function (url, options, ms) {
    var ctl = window.AbortController ? new AbortController() : null;
    var delai = setTimeout(function () { if (ctl) ctl.abort(); }, ms);
    options.signal = ctl ? ctl.signal : undefined;
    return fetch(url, options).then(function (r) { clearTimeout(delai); return r; }, function (e) { clearTimeout(delai); throw e; });
  };

  // Relais Google : « refus » = le relais a répondu et dit pourquoi (à montrer) ; toute autre issue = on essaie le repli
  var parRelais = function (donnees) {
    return avecDelai('data/admin-config.json', { cache: 'no-store' }, 6000)
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (cfg) {
        if (!cfg.relais_url) throw new Error('relais absent');
        return avecDelai(cfg.relais_url, {
          method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' },
          body: JSON.stringify({ action: 'contact', nom: donnees.nom, email: donnees.email, message: donnees.message, piege: donnees._honey })
        }, 15000);
      })
      .then(function (r) { return r.json(); })
      .then(function (rep) {
        if (rep && rep.ok) return;
        var e = new Error(rep && rep.erreur || 'relais');
        e.refus = !!(rep && rep.erreur && !/action inconnue|erreur du relais|jeton|droits/.test(rep.erreur));
        throw e;
      });
  };

  var parFormSubmit = function (donnees) {
    return avecDelai(form.action.replace('formsubmit.co/', 'formsubmit.co/ajax/'), {
      method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(donnees)
    }, 12000)
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (rep) { if (rep && String(rep.success) === 'false') throw new Error(rep.message || 'refus'); });
  };

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var bouton = form.querySelector('button[type="submit"]');
    var donnees = {};
    new FormData(form).forEach(function (v, k) { donnees[k] = v; });
    if (donnees._honey) return;                                        // champ piège : un robot l'a rempli
    bouton.disabled = true;
    bouton.textContent = 'Envoi…';
    dire('Envoi en cours…');
    var fini = function () { bouton.disabled = false; bouton.textContent = 'Envoyer'; };
    parRelais(donnees)
      .catch(function (err) { if (err.refus) throw err; return parFormSubmit(donnees); })
      .then(function () { form.reset(); dire(MERCI); })
      .catch(function (err) {
        if (err && err.refus) return dire('Message non envoyé : ' + err.message + '.', true);
        dire('Envoi en cours…');
        form.submit();                                                 // dernier recours : envoi classique du formulaire
      })
      .then(fini);
  });
})();
