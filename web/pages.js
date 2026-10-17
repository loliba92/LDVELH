/* Pages annexes (projet, confidentialité, mentions légales) : hors ligne et pastille de la collection. */
(function () {
  // nombre d'exemplaires de la collection, sur l'entrée « Ma collection » de la barre du bas
  try {
    var coll = JSON.parse(localStorage.getItem('cote-collection-v1') || '{}') || {};
    var n = Object.keys(coll).reduce(function (a, k) { return a + (coll[k].qte || 1); }, 0);
    var lien = document.querySelector('#barre-bas a[href="collection.html"]');
    if (lien && n) {
      var pastille = document.createElement('b');
      pastille.className = 'nb-coll';
      pastille.textContent = String(n);
      pastille.setAttribute('aria-label', n + (n > 1 ? ' exemplaires' : ' exemplaire'));
      lien.appendChild(pastille);
    }
  } catch (e) { /* sans conséquence */ }
  // Adresse de contact : assemblée ici plutôt qu'écrite dans la page, pour gêner les robots qui collectent les adresses
  document.querySelectorAll('a.mail[data-u]').forEach(function (a) {
    var adresse = a.dataset.u + '@' + a.dataset.d;
    a.href = 'mailto:' + adresse;
    if (!a.classList.contains('bouton')) a.textContent = adresse;
    a.setAttribute('aria-label', a.classList.contains('bouton') ? 'Écrire à ' + adresse : 'Écrire à ' + adresse + ' (ouvre votre messagerie)');
  });
  if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol)) {
    window.addEventListener('load', function () { navigator.serviceWorker.register('sw.js').catch(function () {}); });
  }
})();
