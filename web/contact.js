/* Formulaire de contact : envoi classique vers le service FormSubmit, qui renvoie ensuite sur cette page avec ?envoye=1.
   Pas d'envoi en arrière-plan : si le service demande une validation, c'est sa propre page qui l'indique. */
(function () {
  var form = document.getElementById('contact-form');
  var sent = document.getElementById('form-sent');
  if (!form || !sent) return;
  if (new URLSearchParams(location.search).get('envoye') === '1') {
    sent.textContent = 'Merci, votre message est bien parti. ✓';
    sent.hidden = false;
    sent.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
  form.addEventListener('submit', function () {                       // évite un double envoi
    var btn = form.querySelector('button[type="submit"]');
    if (btn) { btn.disabled = true; btn.textContent = 'Envoi…'; }
  });
  window.addEventListener('pageshow', function (e) {                  // retour arrière : le bouton redevient utilisable
    var btn = form.querySelector('button[type="submit"]');
    if (e.persisted && btn) { btn.disabled = false; btn.textContent = 'Envoyer'; }
  });
})();
