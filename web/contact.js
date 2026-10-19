/* Formulaire de contact : même fonctionnement que sur le site Scénario (envoi sans quitter la page, service FormSubmit). */
(function () {
  var form = document.getElementById('contact-form');
  var sent = document.getElementById('form-sent');
  if (!form || !sent) return;
  var montrer = function (texte, erreur) {
    sent.textContent = texte;
    sent.hidden = false;
    sent.classList.toggle('erreur', !!erreur);
    sent.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  // Repli sans JS : si on revient avec ?envoye=1, on affiche quand même le bandeau.
  if (new URLSearchParams(location.search).get('envoye') === '1') montrer('Merci, votre message est bien parti. ✓');

  if (!window.fetch) return;

  // Envoi AJAX : le message part sans quitter la page.
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var btn = form.querySelector('button[type="submit"]');
    var data = {};
    new FormData(form).forEach(function (value, key) { data[key] = value; });

    if (btn) { btn.disabled = true; btn.textContent = 'Envoi…'; }
    montrer('Envoi en cours…');

    fetch(form.action.replace('formsubmit.co/', 'formsubmit.co/ajax/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(data)
    })
      .then(function (r) { if (!r.ok) throw new Error('http'); return r.json(); })
      .then(function (rep) {
        if (rep && String(rep.success) === 'false') throw new Error(rep.message || 'refus');   // le service répond mais n'a pas envoyé (par exemple activation en attente)
        form.reset();
        montrer('Merci, votre message est bien parti. ✓');
      })
      .catch(function (err) {
        montrer('Envoi impossible pour le moment — réessayez dans quelques instants.' + (err && err.message && err.message !== 'http' ? ' (' + err.message + ')' : ''), true);
      })
      .then(function () { if (btn) { btn.disabled = false; btn.textContent = 'Envoyer'; } });
  });
})();
