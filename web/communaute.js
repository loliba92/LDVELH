// Page Communauté : liste de liens, éditable par le Zagor seulement (lot communaute.yml, voir pipeline/communaute.py)
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const estZagor = () => !!window.Cloud && window.Cloud.actif() && !!window.Compte && window.Compte.role() === 'superadmin';
  const interne = (a) => { try { const u = new URL(a); return u.hostname === 'lacoteduheros.fr' || u.origin === location.origin ? u.pathname.replace(/^\//, '') + u.hash : ''; } catch (e) { return ''; } };   // page du site : même onglet
  const net = (t) => t.replace(/[;|]/g, ' ').replace(/\s+/g, ' ').trim();

  const liste = document.getElementById('comm-liste');
  if (!liste) return;
  const form = document.getElementById('comm-form'), vide = document.getElementById('comm-vide'), msg = document.getElementById('comm-msg');
  const ajout = document.getElementById('comm-ajout'), fenetre = document.getElementById('comm-dialog');
  const nouvelle = document.getElementById('comm-nouvelle');
  let donnees = [];
  let nombres = {}, mes = new Set();
  const connecte = () => !!window.Cloud && window.Cloud.actif();
  const dire = (t) => { msg.textContent = t; msg.hidden = false; };
  // « J'aime » : le nombre est public ; le bouton n'apparaît que pour une personne connectée
  const likeHtml = (adresse) => {
    const n = nombres[adresse] || 0, aime = mes.has(adresse);
    return connecte()
      ? `<p class="comm-like"><button type="button" class="bouton-lien" data-aime="${esc(adresse)}" aria-pressed="${aime}" aria-label="${aime ? 'Retirer mon cœur' : 'Mettre un cœur'} (${n})">${aime ? '♥' : '♡'} ${n}</button></p>`
      : `<p class="comm-like sous" aria-label="${n} cœur${n > 1 ? 's' : ''}">♡ ${n}</p>`;
  };
  const dessiner = () => {
    const z = estZagor();
    ajout.hidden = !z;
    if (nouvelle) nouvelle.hidden = !z;
    vide.hidden = donnees.length > 0;
    liste.innerHTML = donnees.map((x) => `<article class="comm-lien">
      ${x.image ? `<img src="${esc(x.image)}" alt="" width="640" height="360" loading="lazy" decoding="async">` : `<span class="comm-tuile" aria-hidden="true">${esc(x.nom.charAt(0).toUpperCase())}</span>`}
      <div class="comm-texte">
        <h3>${interne(x.adresse) ? `<a href="${esc(interne(x.adresse))}">${esc(x.nom)}</a>` : `<a href="${esc(x.adresse)}" target="_blank" rel="noopener noreferrer">${esc(x.nom)}<span class="sr-only"> (nouvel onglet)</span></a>`}</h3>
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
  // Nouvelle du site : le Zagor remplit le formulaire, le service technique lance le lot « nouvelle.yml » (pipeline/nouvelle.py : images, page, carte, flux RSS)
  const nouvDialog = document.getElementById('nouv-dialog'), nouvForm = document.getElementById('nouv-form'), nouvMsg = document.getElementById('nouv-msg');
  const identifiant = (t) => t.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60).replace(/-$/, '');
  const nouvDire = (t) => { nouvMsg.textContent = t; nouvMsg.hidden = false; };
  if (nouvelle && nouvDialog && nouvForm) {
    nouvelle.addEventListener('click', () => { nouvMsg.hidden = true; nouvDialog.showModal(); });
    document.getElementById('nouv-fermer').addEventListener('click', () => nouvDialog.close());
    nouvForm.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const v = (id) => document.getElementById(id).value.trim();
      const titre = v('nouv-titre'), phrase = v('nouv-phrase'), texte = v('nouv-texte'), date = v('nouv-date');
      if (!titre || !phrase || !texte) return nouvDire('Le titre, la phrase de l\'image et le texte de l\'article sont obligatoires.');
      if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) return nouvDire('La date doit être au format AAAA-MM-JJ.');
      const nom = identifiant(titre);
      if (!nom) return nouvDire('Le titre doit contenir au moins une lettre ou un chiffre.');
      if (donnees.some((x) => String(x.adresse || '').endsWith('/' + nom + '.html'))) return nouvDire('Une nouvelle avec ce titre existe déjà : changez le titre.');
      if (!window.confirm('Publier cette nouvelle maintenant ? Elle sera visible par tous sur le site.')) return;
      const entrees = { titre, phrase, texte, fond: v('nouv-fond') };
      if (v('nouv-facebook')) entrees.facebook = v('nouv-facebook');
      if (v('nouv-desc')) entrees.description = v('nouv-desc');
      if (date) entrees.date = date;
      try {
        const r = await window.Relais.envoyerLot('nouvelle.yml', entrees);
        if (r.status === 204) nouvDire('Envoyé. La nouvelle sera en ligne dans environ 3 minutes : rechargez la page ensuite.');
        else if (r.status === 401 || r.status === 403) nouvDire("Ce compte n'a pas accès à cette fonction, ou la connexion Google a expiré : reconnectez-vous.");
        else nouvDire(`Échec de l'envoi : ${r.erreur || 'code ' + r.status}.`);
      } catch (e) { nouvDire('Envoi impossible : vérifiez votre connexion.'); }
    });
  }
  fetch('data/communaute.json', { cache: 'no-store' }).then((r) => (r.ok ? r.json() : [])).catch(() => []).then((d) => { donnees = Array.isArray(d) ? d : []; dessiner(); });
})();
