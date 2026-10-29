// Page Communauté : liste de liens, éditable par le Zagor seulement (lot communaute.yml, voir pipeline/communaute.py)
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const estZagor = () => !!window.Cloud && window.Cloud.actif() && !!window.Compte && window.Compte.role() === 'superadmin';
  const net = (t) => t.replace(/[;|]/g, ' ').replace(/\s+/g, ' ').trim();

  const liste = document.getElementById('comm-liste');
  if (!liste) return;
  const form = document.getElementById('comm-form'), vide = document.getElementById('comm-vide'), msg = document.getElementById('comm-msg');
  let donnees = [];
  const dire = (t) => { msg.textContent = t; msg.hidden = false; };
  const dessiner = () => {
    const z = estZagor();
    form.hidden = !z;
    vide.hidden = donnees.length > 0;
    liste.innerHTML = donnees.map((x) => `<article class="comm-lien">
      <h3><a href="${esc(x.adresse)}" target="_blank" rel="noopener noreferrer">${esc(x.nom)}<span class="sr-only"> (nouvel onglet)</span></a></h3>
      ${x.description ? `<p>${esc(x.description)}</p>` : ''}
      ${z ? `<button type="button" class="bouton bouton-clair" data-retrait="${esc(x.adresse)}">Retirer ${esc(x.nom)}</button>` : ''}
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
  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const nom = net($('#cf-nom').value), adresse = $('#cf-url').value.trim(), description = net($('#cf-desc').value);
    if (!/^https:\/\/\S+$/.test(adresse)) return dire("L'adresse doit commencer par https://");
    envoyer(`ajout ; ${nom} ; ${adresse} ; ${description}`);
  });
  liste.addEventListener('click', (e) => { const b = e.target.closest('[data-retrait]'); if (b) envoyer(`retrait ; ${b.dataset.retrait}`); });
  document.addEventListener('cdh-compte', dessiner);
  fetch('data/communaute.json', { cache: 'no-store' }).then((r) => (r.ok ? r.json() : [])).catch(() => []).then((d) => { donnees = Array.isArray(d) ? d : []; dessiner(); });
})();
