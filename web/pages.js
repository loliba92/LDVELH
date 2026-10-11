/* Pages annexes (projet, confidentialité, mentions légales) : éclairage, hors ligne, pastille de la collection. */
(function () {
  var bouton = document.getElementById('lampe');
  if (bouton) {
    var sombre = function () {
      var t = document.documentElement.dataset.theme;
      return t ? t === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    };
    var maj = function () { bouton.setAttribute('aria-pressed', String(sombre())); };
    bouton.addEventListener('click', function () {
      var t = sombre() ? 'light' : 'dark';
      document.documentElement.dataset.theme = t;
      try { localStorage.setItem('cote-theme', t); } catch (e) { /* sans conséquence */ }
      maj();
    });
    maj();
  }
  // nombre d'exemplaires de la collection, sur l'entrée « Ma collection » de la barre du bas
  try {
    var coll = JSON.parse(localStorage.getItem('cote-collection-v1') || '{}') || {};
    var n = Object.keys(coll).reduce(function (a, k) { return a + (coll[k].qte || 1); }, 0);
    var lien = document.querySelector('#barre-bas a[href="./#collection"]');
    if (lien && n) {
      var pastille = document.createElement('b');
      pastille.className = 'nb-coll';
      pastille.textContent = String(n);
      pastille.setAttribute('aria-label', n + (n > 1 ? ' exemplaires' : ' exemplaire'));
      lien.appendChild(pastille);
    }
  } catch (e) { /* sans conséquence */ }
  if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol)) {
    window.addEventListener('load', function () { navigator.serviceWorker.register('sw.js').catch(function () {}); });
  }
})();
