// Page Communauté : liste de liens, éditable par le Zagor seulement (lot communaute.yml, voir pipeline/communaute.py)
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const estZagor = () => !!window.Cloud && window.Cloud.actif() && !!window.Compte && window.Compte.role() === 'superadmin';
  const net = (t) => t.replace(/[;|]/g, ' ').replace(/\s+/g, ' ').trim();

  const liste = document.getElementById('comm-liste');
  if (!liste) return;
  const form = document.getElementById('comm-form'), vide = document.getElementById('comm-vide'), msg = document.getElementById('comm-msg');
  const ajout = document.getElementById('comm-ajout'), fenetre = document.getElementById('comm-dialog');
  let donnees = [];
  let nombres = {}, mes = new Set();
  const connecte = () => !!window.Cloud && window.Cloud.actif();
  const dire = (t) => { msg.textContent = t; msg.hidden = false; };
  // « J'aime » : le nombre est public ; le bouton n'apparaît que pour une personne connectée
  const likeHtml = (adresse) => {
    const n = nombres[adresse] || 0, aime = mes.has(adresse);
    return connecte()
      ? `<p class="comm-like"><button type="button" class="bouton-lien" data-aime="${esc(adresse)}" aria-pressed="${aime}">${aime ? 'Vous aimez' : "J'aime"} · ${n}</button></p>`
      : `<p class="comm-like sous">${n ? `${n} personne${n > 1 ? 's' : ''} aime${n > 1 ? 'nt' : ''} ce lien` : 'Personne n\'a encore aimé ce lien'}</p>`;
  };
  const dessiner = () => {
    const z = estZagor();
    ajout.hidden = !z;
    vide.hidden = donnees.length > 0;
    liste.innerHTML = donnees.map((x) => `<article class="comm-lien">
      ${x.image ? `<img src="${esc(x.image)}" alt="" width="640" height="360" loading="lazy" decoding="async">` : `<span class="comm-tuile" aria-hidden="true">${esc(x.nom.charAt(0).toUpperCase())}</span>`}
      <div class="comm-texte">
        <h3><a href="${esc(x.adresse)}" target="_blank" rel="noopener noreferrer">${esc(x.nom)}<span class="sr-only"> (nouvel onglet)</span></a></h3>
        ${x.description ? `<p>${esc(x.description)}</p>` : ''}
        ${likeHtml(x.adresse)}
        ${z ? `<button type="button" class="bouton-lien" data-retrait="${esc(x.adresse)}">Retirer ${esc(x.nom)}</button>` : ''}
      </div>
    </article>`).join('');
  };
  async function envoyer(commande) {
    try {
      const r = await window.Relais.envoyerLot('communaute.yml', { commandes: commande });
      if (r.status === 204) dire('Envoyé. La liste sera à jour dans environ 2 minutes : rechargez la page ensuite.');
      else if (r.status === 401 || r.status === 403) dire("Ce compte n'a pas accès à cette fonction, ou la connexion Google a expiré : reconnectez-vous.");
      else dire(`Échec de l'envoi : ${r.erreur || 'code ' + r.status}.`);
    } catch (e) { dire('Envoi impossible : vérifiez votre connexion.'); }
  }
  ajout.addEventListener('click', () => { msg.hidden = true; fenetre.showModal(); });
  document.getElementById('comm-fermer').addEventListener('click', () => fenetre.close());
  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const nom = net($('#cf-nom').value), adresse = $('#cf-url').value.trim(), description = net($('#cf-desc').value);
    if (!/^https:\/\/\S+$/.test(adresse)) return dire("L'adresse doit commencer par https://");
    envoyer(`ajout ; ${nom} ; ${adresse} ; ${description}`);
  });
  liste.addEventListener('click', (e) => { const b = e.target.closest('[data-retrait]'); if (b) envoyer(`retrait ; ${b.dataset.retrait}`); });
  liste.addEventListener('click', (e) => {
    const b = e.target.closest('[data-aime]');
    if (!b) return;
    const adresse = b.dataset.aime, aime = !mes.has(adresse);
    b.disabled = true;
    window.Relais.aimerLien(adresse, aime).then((r) => {
      if (!r || !r.ok) throw new Error((r && r.erreur) || 'refus');
      if (r.aime) mes.add(adresse); else mes.delete(adresse);
      nombres[adresse] = r.nombre;
      dessiner();
    }).catch((err) => { b.disabled = false; dire(`Votre « j'aime » n'a pas été enregistré : ${err.message || 'erreur'}.`); });
  });
  document.addEventListener('cdh-compte', () => {
    if (!connecte()) { mes = new Set(); dessiner(); return; }
    window.Relais.mesLikes().then((r) => { mes = new Set((r && r.ok && r.adresses) || []); dessiner(); }).catch(() => dessiner());
  });
  window.Relais.lireLikes().then((r) => { nombres = (r && r.ok && r.likes) || {}; dessiner(); }).catch(() => {});
  fetch('data/communaute.json', { cache: 'no-store' }).then((r) => (r.ok ? r.json() : [])).catch(() => []).then((d) => { donnees = Array.isArray(d) ? d : []; dessiner(); });
})();
