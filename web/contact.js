/* Formulaire de contact : le message part sans quitter la page (service FormSubmit) ; sans JavaScript, le formulaire envoie normalement
   et revient sur cette page avec ?envoye=1. L'adresse de l'éditeur n'apparaît nulle part sur le site. */
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
  if (/[?&]envoye=1/.test(location.search)) dire('Merci, votre message est bien parti. ✓');
  if (!window.fetch) return;
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var bouton = form.querySelector('button[type="submit"]');
    var donnees = {};
    new FormData(form).forEach(function (v, k) { donnees[k] = v; });
    if (donnees._honey) return;                                        // champ piège : un robot l'a rempli
    bouton.disabled = true;
    bouton.textContent = 'Envoi…';
    dire('Envoi en cours…');
    fetch(form.action.replace('formsubmit.co/', 'formsubmit.co/ajax/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(donnees)
    }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (rep) { if (rep && String(rep.success) === 'false') throw new Error(rep.message || 'refus'); form.reset(); dire('Merci, votre message est bien parti. Je vous répondrai à l\'adresse indiquée. ✓'); })
      .catch(function () { dire('Envoi impossible pour le moment : vérifiez votre connexion et réessayez dans quelques instants.', true); })
      .then(function () { bouton.disabled = false; bouton.textContent = 'Envoyer'; });
  });
})();
