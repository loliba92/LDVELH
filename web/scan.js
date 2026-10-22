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

  let dlg, video, msg, arret = null, mode = null, vus = new Set(), etatChoisi = 'bon';
  function fenetre() {
    if (dlg) return;
    dlg = document.createElement('dialog');
    dlg.className = 'scan-dialog'; dlg.setAttribute('aria-labelledby', 'scan-titre');
    dlg.innerHTML = '<div class="scan-cadre"><div class="scan-tete"><p class="surtitre" id="scan-titre">Scanner un code-barres</p><button type="button" class="bouton bouton-clair" id="scan-fermer">Fermer</button></div>' +
      '<div class="scan-video"><video playsinline muted></video><span class="scan-viseur" aria-hidden="true"></span></div>' +
      '<p class="sous" id="scan-msg" role="status" aria-live="polite"></p><p class="sous" id="scan-ancien">Livre ancien sans code-barres ? Fermez cette fenêtre et tapez son titre dans le champ.</p>' +
      '<div class="scan-serie" id="scan-serie" hidden><div class="scan-etat" id="scan-etat-zone"><span class="scan-etat-lib" id="scan-etat-lib">État des livres scannés</span><div class="ex-etats" role="group" aria-labelledby="scan-etat-lib">' +
      '<button type="button" data-etat="convenable" title="Convenable">C</button><button type="button" data-etat="bon" title="Bon état">BE</button><button type="button" data-etat="tres_bon" title="Très bon état">TBE</button></div></div>' +
      '<ul class="scan-liste" id="scan-liste" aria-label="Livres scannés"></ul></div></div>';
    document.body.appendChild(dlg);
    video = dlg.querySelector('video'); msg = dlg.querySelector('#scan-msg');
    dlg.addEventListener('click', (e) => {
      if (e.target === dlg || e.target.id === 'scan-fermer') { dlg.close(); return; }
      const et = e.target.closest('[data-etat]');
      if (et) { etatChoisi = et.dataset.etat; try { localStorage.setItem('cdh-scan-etat', etatChoisi); } catch (x) { /* sans stockage : BE par défaut */ } marquerEtat(); }
      const ann = e.target.closest('[data-annuler]');
      if (ann && mode && mode.annuler) { mode.annuler(ann.dataset.annuler); ann.closest('li').remove(); }      // l'ISBN reste « vu » : le livre encore sous la caméra n'est pas rajouté aussitôt
    });
    dlg.addEventListener('close', () => { if (arret) { arret(); arret = null; } });
  }

  const marquerEtat = () => dlg.querySelectorAll('[data-etat]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.etat === etatChoisi)));
  const echapper = (t) => String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function chargerZxing() {
    if (window.ZXing) return Promise.resolve();
    return new Promise((ok, ko) => {
      const s = document.createElement('script');
      s.src = 'vendor/zxing.min.js'; s.onload = ok; s.onerror = () => ko(new Error('lecteur'));
      document.head.appendChild(s);
    });
  }

  async function lire(quandTrouve) {
    const trouve = (code) => {
      const isbn = isbnValide(code);
      if (!isbn) return false;
      if (!mode) { dlg.close(); quandTrouve(isbn); return true; }
      if (vus.has(isbn)) return false;                                  // le même livre n'est pris qu'une fois par séance
      vus.add(isbn);
      const r = mode.traiter(isbn, etatChoisi);                          // { texte, ok, id } : une ligne dans la liste
      if (navigator.vibrate) navigator.vibrate(r.ok ? 60 : [40, 60, 40]);
      const li = document.createElement('li');
      li.className = r.ok ? 'ok' : 'ko';
      li.innerHTML = `<span>${echapper(r.texte)}</span>` + (r.id ? `<button type="button" class="bouton-lien" data-annuler="${echapper(r.id)}">Annuler</button>` : '') + (r.action || '');
      dlg.querySelector('#scan-liste').prepend(li);
      msg.textContent = r.texte;
      return false;                                                      // la caméra continue : livre suivant
    };
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

  // scanner(rappel) : un seul livre, puis la fenêtre se ferme.
  // scanner(null, { traiter(isbn, etat) -> { texte, ok, id }, annuler(id), etats: true|false, fin(n) }) : plusieurs livres de suite.
  function scanner(quandTrouve, serie) {
    fenetre();
    mode = serie || null; vus = new Set();
    const zone = dlg.querySelector('#scan-serie');
    zone.hidden = !mode; dlg.querySelector('#scan-liste').innerHTML = '';
    dlg.querySelector('#scan-etat-zone').hidden = !(mode && mode.etats);
    dlg.querySelector('#scan-fermer').textContent = mode ? 'Terminer' : 'Fermer';
    dlg.querySelector('#scan-titre').textContent = mode ? 'Scanner plusieurs livres' : 'Scanner un code-barres';
    try { etatChoisi = localStorage.getItem('cdh-scan-etat') || 'bon'; } catch (x) { etatChoisi = 'bon'; }
    marquerEtat();
    const consigne = mode ? 'Cadrez un code-barres, puis le suivant : chaque livre est ajouté au fur et à mesure.' : 'Cadrez le code-barres au dos du livre, bien éclairé. Il se lit tout seul.';
    dlg.querySelector('.scan-video').classList.remove('scan-erreur');
    msg.textContent = 'Démarrage de la caméra…';
    video.onplaying = () => { msg.textContent = consigne; };                // la consigne n'apparaît qu'une fois l'image là
    dlg.querySelector('#scan-ancien').hidden = false;
    dlg.addEventListener('close', () => { if (mode && mode.fin) mode.fin(dlg.querySelectorAll('#scan-liste li.ok').length); }, { once: true });
    dlg.showModal();
    lire(quandTrouve).catch((e) => {
      dlg.querySelector('.scan-video').classList.add('scan-erreur');
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

  window.Scan = { scanner, bouton };                    // utilisé aussi par la demande d'ajout d'un livre (compte.js)

  // Ajouter un titre à ma collection : plusieurs livres de suite, chacun ajouté dans l'état choisi (C, BE ou TBE) et annulable
  const champ = $('#ca-q');
  if (champ) {
    const bloc = document.createElement('div');
    bloc.className = 'ca-champ';
    champ.parentNode.insertBefore(bloc, champ);
    bloc.appendChild(champ);
    const b = bouton();
    b.addEventListener('click', () => {
      const demarrer = () => scanner(null, {
        etats: true,
        traiter(isbn, etat) {
          const livre = window.AjoutRapide.trouver(isbn);
          if (!livre) return { ok: false, texte: `ISBN ${isbn} : ce livre n'est pas encore dans le guide.`, action: ` <button type="button" class="bouton-lien" data-demander="${isbn}">Demander son ajout</button>` };
          const deja = window.AjoutRapide.etat(livre.id);
          if (deja) return { ok: false, texte: `${window.AjoutRapide.titre(livre)} est déjà dans votre collection.` };
          window.AjoutRapide.ajouter(livre.id, etat);
          return { ok: true, texte: `✓ ${window.AjoutRapide.titre(livre)} ajouté`, id: livre.id };
        },
        annuler: (id) => window.AjoutRapide.retirer(id),
        fin(n) {
          const ok = $('#ca-ok');
          if (ok && n) { ok.textContent = `✓ ${n} livre${n > 1 ? 's' : ''} scanné${n > 1 ? 's' : ''}.`; ok.hidden = false; }
        },
      });
      if (!window.AjoutRapide || window.AjoutRapide.garde(demarrer)) demarrer();      // sans compte : la fenêtre de connexion s'ouvre, puis on reprend ici
    });
    bloc.appendChild(b);
    document.addEventListener('click', (e) => {                           // ISBN inconnu : on propose la demande d'ajout
      const d = e.target.closest('[data-demander]');
      if (d && dlg) { const isbn = d.dataset.demander; dlg.close(); if (window.Compte) window.Compte.demanderLivre(isbn); }
    });
  }

  // Accueil : scanner un livre pour voir sa cote (rien n'est ajouté à la collection) ; la fiche du livre s'ouvre
  const hero = $('#hero-recherche'), hq = $('#h-q');
  if (hero && hq) {
    hero.classList.add('avec-scan');
    const b = bouton('scan-hero');
    const lancer = () => scanner((isbn) => {
      hq.value = isbn;
      hero.requestSubmit ? hero.requestSubmit() : hero.dispatchEvent(new Event('submit', { cancelable: true }));
      const livre = window.AjoutRapide && window.AjoutRapide.trouver(isbn);
      if (livre) window.AjoutRapide.ouvrir(livre.id);
    });
    // Le scan est réservé aux comptes : sans compte, la fenêtre de connexion s'ouvre puis le scan démarre
    b.addEventListener('click', () => { if (!window.Compte || window.Compte.exiger(lancer)) lancer(); });
    hq.parentNode.insertBefore(b, hq.nextSibling);
    const aide = document.createElement('p');
    aide.className = 'sous scan-aide'; aide.hidden = true;
    aide.textContent = 'Le scan est réservé aux comptes connectés.';
    hero.parentNode.insertBefore(aide, hero.nextSibling);
    const majScan = () => { const reserve = !!window.Compte && window.Compte.actif() && !(window.Cloud && window.Cloud.lie()); aide.hidden = !reserve; b.classList.toggle('scan-reserve', reserve); };
    document.addEventListener('cdh-compte', majScan); majScan();
  }

  // Espace administrateur, « Ajouter des livres » : l'ISBN lu est ajouté à la liste, une ligne par livre
  const texte = $('#aj-texte');
  if (texte) {
    const b = bouton('scan-liste');
    b.addEventListener('click', () => scanner(null, {
      etats: false,
      traiter(isbn) {
        texte.value = (texte.value.trim() ? texte.value.replace(/\s*$/, '\n') : '') + isbn + '\n';
        texte.dispatchEvent(new Event('input', { bubbles: true }));
        return { ok: true, texte: `✓ ${isbn} ajouté à la liste` };
      },
    }));
    const actions = document.querySelector('#aj-verifier') && document.querySelector('#aj-verifier').parentNode;     // à côté de « Vérifier la liste », même rangée, même hauteur
    if (actions) actions.appendChild(b); else texte.parentNode.insertBefore(b, texte.nextSibling);
  }
})();
