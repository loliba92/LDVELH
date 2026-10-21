/* Lecture du code-barres d'un livre avec l'appareil photo : l'ISBN est lu dans le téléphone, aucune image n'est envoyée ni gardée.
   Le lecteur du navigateur (BarcodeDetector, Chrome sur Android) est utilisé quand il existe ; sinon la bibliothèque ZXing, hébergée
   sur le site (vendor/zxing.min.js, licence Apache 2.0), est chargée au premier scan seulement. */
(function () {
  'use strict';
  if (!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)) return;
  const $ = (s) => document.querySelector(s);

  // ISBN-13 valide : 13 chiffres, préfixe 978 ou 979, clé de contrôle exacte
  function isbnValide(c) {
    const n = String(c || '').replace(/\D/g, '');
    if (n.length !== 13 || !/^97[89]/.test(n)) return null;
    let somme = 0;
    for (let i = 0; i < 12; i += 1) somme += Number(n[i]) * (i % 2 ? 3 : 1);
    return (10 - (somme % 10)) % 10 === Number(n[12]) ? n : null;
  }

  let dlg, video, msg, arret = null;
  function fenetre() {
    if (dlg) return;
    dlg = document.createElement('dialog');
    dlg.className = 'scan-dialog'; dlg.setAttribute('aria-labelledby', 'scan-titre');
    dlg.innerHTML = '<div class="scan-cadre"><div class="scan-tete"><p class="surtitre" id="scan-titre">Scanner un code-barres</p><button type="button" class="bouton bouton-clair" id="scan-fermer">Fermer</button></div>' +
      '<div class="scan-video"><video playsinline muted></video><span class="scan-viseur" aria-hidden="true"></span></div>' +
      '<p class="sous" id="scan-msg" role="status" aria-live="polite"></p></div>';
    document.body.appendChild(dlg);
    video = dlg.querySelector('video'); msg = dlg.querySelector('#scan-msg');
    dlg.addEventListener('click', (e) => { if (e.target === dlg || e.target.id === 'scan-fermer') dlg.close(); });
    dlg.addEventListener('close', () => { if (arret) { arret(); arret = null; } });
  }

  function chargerZxing() {
    if (window.ZXing) return Promise.resolve();
    return new Promise((ok, ko) => {
      const s = document.createElement('script');
      s.src = 'vendor/zxing.min.js'; s.onload = ok; s.onerror = () => ko(new Error('lecteur'));
      document.head.appendChild(s);
    });
  }

  async function lire(quandTrouve) {
    const trouve = (code) => { const isbn = isbnValide(code); if (!isbn) return false; dlg.close(); quandTrouve(isbn); return true; };
    if ('BarcodeDetector' in window) {
      const flux = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      video.srcObject = flux; await video.play();
      const det = new window.BarcodeDetector({ formats: ['ean_13'] });
      let actif = true;
      const tour = async () => {
        if (!actif) return;
        try { const r = await det.detect(video); if (r.some((x) => trouve(x.rawValue))) return; } catch (e) { /* image pas prête : on réessaie */ }
        setTimeout(tour, 250);
      };
      arret = () => { actif = false; flux.getTracks().forEach((t) => t.stop()); video.srcObject = null; };
      tour();
      return;
    }
    await chargerZxing();
    const hints = new Map([[window.ZXing.DecodeHintType.POSSIBLE_FORMATS, [window.ZXing.BarcodeFormat.EAN_13]]]);
    const lecteur = new window.ZXing.BrowserMultiFormatReader(hints, 300);
    arret = () => lecteur.reset();
    await lecteur.decodeFromVideoDevice(null, video, (res) => { if (res) trouve(res.getText()); });
  }

  function scanner(quandTrouve) {
    fenetre();
    msg.textContent = 'Cadrez le code-barres au dos du livre, bien éclairé. Il se lit tout seul.';
    dlg.showModal();
    lire(quandTrouve).catch((e) => {
      msg.textContent = e && (e.name === 'NotAllowedError' || e.name === 'SecurityError')
        ? 'La caméra n\'est pas autorisée. Autorisez-la dans votre navigateur, ou saisissez l\'ISBN à la main.'
        : e && e.name === 'NotFoundError' ? 'Aucune caméra trouvée. Saisissez l\'ISBN à la main.'
        : 'Le lecteur n\'a pas pu démarrer. Saisissez l\'ISBN à la main.';
    });
  }

  function bouton(classe) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'bouton bouton-clair scan-bouton ' + (classe || '');
    b.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2M7 9v6M10.5 9v6M14 9v6M17 9v6"/></svg><span>Scanner</span>';
    b.setAttribute('aria-label', 'Scanner le code-barres d\'un livre avec l\'appareil photo');
    return b;
  }

  // Ajouter un titre à ma collection : l'ISBN lu est mis dans le champ de recherche, le livre apparaît avec C / BE / TBE
  const champ = $('#ca-q');
  if (champ) {
    const bloc = document.createElement('div');
    bloc.className = 'ca-champ';
    champ.parentNode.insertBefore(bloc, champ);
    bloc.appendChild(champ);
    const b = bouton();
    b.addEventListener('click', () => scanner((isbn) => {
      champ.value = isbn;
      champ.dispatchEvent(new Event('input', { bubbles: true }));
      const st = $('#ca-statut'); if (st) st.textContent = `ISBN ${isbn} lu.`;
      champ.focus({ preventScroll: true });
    }));
    bloc.appendChild(b);
  }

  // Espace administrateur, « Ajouter des livres » : l'ISBN lu est ajouté à la liste, une ligne par livre
  const texte = $('#aj-texte');
  if (texte) {
    const b = bouton('scan-liste');
    b.addEventListener('click', () => scanner((isbn) => {
      texte.value = (texte.value.trim() ? texte.value.replace(/\s*$/, '\n') : '') + isbn + '\n';
      texte.dispatchEvent(new Event('input', { bubbles: true }));
    }));
    texte.parentNode.insertBefore(b, texte.nextSibling);
  }
})();
