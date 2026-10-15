/* Bandeau « Installer l'application », présent sur toutes les pages.
   Chrome, Edge, Android : capte l'invitation du navigateur et propose un bouton « Installer ».
   iPhone et iPad : pas d'installation par programme, on indique le geste « Partager, puis Sur l'écran d'accueil ».
   N'apparaît jamais si l'application est déjà installée ; une fermeture le masque 14 jours. */
(() => {
  'use strict';
  const CLE = 'cdh-installer-ferme-jusqu-au';
  const JOURS = 14, DELAI = 4000;
  const ICONE_PARTAGER = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px" aria-hidden="true"><path d="M12 3v12"/><path d="M8 7l4-4 4 4"/><rect x="5" y="9" width="14" height="12" rx="2"/></svg>';
  let invite = null, bandeau = null;

  const installee = () => (window.matchMedia && matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true;
  const ferme = () => { try { return Date.now() < Number(localStorage.getItem(CLE) || 0); } catch (e) { return false; } };
  const memoriser = () => { try { localStorage.setItem(CLE, String(Date.now() + JOURS * 864e5)); } catch (e) { /* sans stockage : le bandeau reviendra */ } };
  const ios = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (/macintosh/i.test(navigator.userAgent) && navigator.maxTouchPoints > 1);

  function cacher() {
    if (!bandeau) return;
    const el = bandeau; bandeau = null;
    el.classList.remove('visible');
    setTimeout(() => el.remove(), 350);
  }

  function montrer(sorte) {
    if (bandeau || installee() || ferme()) return;
    const el = document.createElement('div');
    el.className = 'bandeau-install';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-label', "Installer l'application La Cote du Héros");
    el.innerHTML = `<img class="bi-icone" src="icons/icon-192.png" alt="" width="40" height="40">
      <div class="bi-corps"><p class="bi-titre">Installer La Cote du Héros</p>
      <p class="bi-texte">${sorte === 'ios'
        ? `Ce bandeau n'a pas de bouton : appuyez sur l'icône Partager ${ICONE_PARTAGER} de votre navigateur, puis sur <strong>Sur l'écran d'accueil</strong>.`
        : "Retrouvez le guide d'un geste depuis votre écran d'accueil, même sans réseau."}</p></div>
      <div class="bi-actions">${sorte === 'ios' ? '' : '<button type="button" class="bi-installer">Installer</button>'}
      <button type="button" class="bi-fermer" aria-label="Fermer">&times;</button></div>`;
    const b = el.querySelector('.bi-installer');
    if (b) b.addEventListener('click', async () => {
      if (!invite) return;
      invite.prompt();
      await invite.userChoice.catch(() => null);
      invite = null; cacher();
    });
    el.querySelector('.bi-fermer').addEventListener('click', () => { memoriser(); cacher(); });
    document.body.appendChild(el);
    bandeau = el;
    requestAnimationFrame(() => requestAnimationFrame(() => { if (bandeau) bandeau.classList.add('visible'); }));
  }

  if (installee() || ferme()) return;
  if (ios()) { setTimeout(() => montrer('ios'), DELAI); return; }
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); invite = e; setTimeout(() => montrer('navigateur'), DELAI); });
  window.addEventListener('appinstalled', cacher);
})();
