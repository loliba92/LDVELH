/* Feuille « Plus » de la barre du bas : Le projet, À propos, Confidentialité, Mentions légales. */
(function () {
  var feuille = document.getElementById('plus');
  if (!feuille || !feuille.showModal) return;
  var boutons = document.querySelectorAll('[data-plus]');
  boutons.forEach(function (b) {
    b.addEventListener('click', function () { if (!feuille.open) feuille.showModal(); b.setAttribute('aria-expanded', 'true'); });
  });
  feuille.addEventListener('click', function (e) {
    if (e.target === feuille || e.target.closest('a') || e.target.closest('.feuille-fermer')) feuille.close();
  });
  feuille.addEventListener('close', function () {
    boutons.forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
  });
})();
