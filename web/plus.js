/* Feuille « Infos » de la barre du bas : Le projet, À propos, Confidentialité, Mentions légales. */
(function () {
  var feuille = document.getElementById('feuille-plus');
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

/* Menu déroulant « À propos » : se ferme au clic ailleurs, à la touche Échap ou au choix d'un lien */
(function () {
  var m = document.querySelector('.menu-plus');
  if (!m) return;
  document.addEventListener('click', function (e) { if (m.open && !m.contains(e.target)) m.open = false; });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && m.open) { m.open = false; var s = m.querySelector('summary'); if (s) s.focus(); } });
})();
