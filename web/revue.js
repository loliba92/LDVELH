/* Vérifier les prix : un livre par ligne, ses trois prix, l'ancien prix barré quand il a changé (outil du propriétaire). */
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const ETATS = [['convenable', 'Convenable'], ['bon', 'Bon état'], ['tres_bon', 'Très bon état']];
  const PAGE = 60;
  const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const eur = (v) => (v == null ? '—' : v.toFixed(2).replace('.', ',') + ' €');
  const norm = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  let EDITIONS = [], VUE = [], vue = 'verif', limite = PAGE;

  const ratio = (l) => (l && l.archive && l.publie ? l.publie / l.archive : null);
  const modifie = (l) => l && l.publie != null && l.archive != null && Math.abs(l.publie - l.archive) > 0.01;
  // « À vérifier » : le prix a presque doublé (×1,8) ou presque divisé par deux (×0,55)
  const raison = (l) => {
    const r = ratio(l);
    if (r == null || !modifie(l)) return '';
    if (r >= 2) return 'a plus que doublé';
    if (r >= 1.8) return 'a presque doublé';
    if (r <= 0.34) return 'a été divisé par trois ou plus';
    if (r <= 0.55) return 'a été presque divisé par deux';
    return '';
  };
  const pct = (r) => (r >= 1 ? '+' : '−') + Math.abs(Math.round((r - 1) * 100)) + ' %';

  function origine(l) {
    if (l.deduit) return 'déduit des autres états';
    if (l.repartition) { const n = l.eb_nb_toutes || l.eb_nb; return `annonces eBay${n ? ' (' + n + ')' : ''}, réparti 40/60`; }
    if (l.source && l.source !== 'archives') {
      const n = l.eb_nb_toutes || l.eb_nb;
      return n ? `d'après ${n} annonce${n > 1 ? 's' : ''} eBay` : "d'après les annonces eBay";
    }
    return l.publie == null ? '' : 'ancienne cote';
  }

  function cellule([cle, lib], ed) {
    const l = ed.etats[cle];
    if (!l || l.publie == null) return `<div class="rv-prix vide"><span class="rv-lib">${lib}</span><strong>—</strong><span class="rv-note">pas de prix</span></div>`;
    const r = ratio(l), alerte = raison(l);
    const avant = modifie(l) ? `<span class="rv-avant">avant <s>${eur(l.archive)}</s> · <b>${pct(r)}</b></span>` : '';
    const notes = [origine(l), l.ajuste ? 'ajusté pour garder C ≤ BE ≤ TBE' : ''].filter(Boolean).join(' · ');
    return `<div class="rv-prix${modifie(l) ? (r > 1 ? ' hausse' : ' baisse') : ''}${alerte ? ' alerte' : ''}"><span class="rv-lib">${lib}</span>` +
      `<strong>${eur(l.publie)}</strong>${avant}${alerte ? `<span class="rv-raison">À vérifier : ${alerte}</span>` : ''}<span class="rv-note">${esc(notes)}</span></div>`;
  }

  function carte(ed) {
    return `<article class="rv-edition"><header><a href="./#q=${encodeURIComponent(ed.isbn || ed.id)}">${esc(ed.titre)}</a>` +
      `<span class="sous">${esc(ed.serie)}${ed.numero && ed.numero !== '000' ? ' n° ' + esc(ed.numero) : ''} · <span class="badge">${esc(ed.version)}</span></span></header>` +
      `<div class="rv-trois">${ETATS.map((e) => cellule(e, ed)).join('')}</div></article>`;
  }

  const lignes = (ed) => Object.values(ed.etats);
  const aVerifier = (ed) => lignes(ed).some((l) => raison(l));
  const aChange = (ed) => lignes(ed).some(modifie);
  const force = (ed) => Math.max(0, ...lignes(ed).map((l) => { const r = ratio(l); return r ? Math.abs(Math.log(r)) : 0; }));

  function afficher() {
    const q = norm($('#rv-q').value).trim(), serie = $('#rv-serie').value;
    const base = EDITIONS.filter((ed) => (!q || norm(ed.titre + ' ' + ed.serie).includes(q)) && (!serie || ed.serie === serie));
    $('#rv-n-verif').textContent = base.filter(aVerifier).length;
    $('#rv-n-change').textContent = base.filter(aChange).length;
    $('#rv-n-tous').textContent = base.length;
    VUE = vue === 'verif' ? base.filter(aVerifier).sort((a, b) => force(b) - force(a))
      : vue === 'change' ? base.filter(aChange).sort((a, b) => force(b) - force(a))
      : base.slice().sort((a, b) => a.serie.localeCompare(b.serie, 'fr') || (parseInt(a.numero, 10) || 0) - (parseInt(b.numero, 10) || 0) || a.version.localeCompare(b.version));
    $('#rv-compte').textContent = `${VUE.length} livre${VUE.length > 1 ? 's' : ''}` + (vue === 'verif' ? ' dont un prix a beaucoup bougé, du plus fort changement au plus faible.' : vue === 'change' ? ' dont au moins un prix a changé.' : '.');
    $('#rv-liste').innerHTML = VUE.length ? VUE.slice(0, limite).map(carte).join('') : '<p>Aucun livre dans cette liste.</p>';
    $('#rv-plus').hidden = VUE.length <= limite;
    document.querySelectorAll('#rv-onglets button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.vue === vue)));
  }

  function csv() {
    const q = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const cols = ['Titre', 'Série', 'Numéro', 'Édition', 'État', 'Prix affiché', 'Ancien prix', 'Origine', 'À vérifier'];
    const lib = Object.fromEntries(ETATS);
    const lig = [];
    VUE.forEach((ed) => ETATS.forEach(([cle]) => { const l = ed.etats[cle]; if (l && l.publie != null) lig.push([ed.titre, ed.serie, ed.numero, ed.version, lib[cle], String(l.publie).replace('.', ','), l.archive == null ? '' : String(l.archive).replace('.', ','), origine(l), raison(l)].map(q).join(';')); }));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['﻿' + [cols.join(';')].concat(lig).join('\r\n')], { type: 'text/csv;charset=utf-8' }));
    a.download = 'verification-des-prix.csv'; document.body.appendChild(a); a.click(); a.remove();
  }

  fetch('data/revue.json').then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then((d) => {
    const par = new Map();
    d.forEach((l) => { if (!par.has(l.id)) par.set(l.id, { id: l.id, isbn: l.isbn, titre: l.titre, serie: l.serie, numero: l.numero, version: l.version, etats: {} }); par.get(l.id).etats[l.etat] = l; });
    EDITIONS = [...par.values()];
    $('#rv-serie').innerHTML = '<option value="">Toutes les séries</option>' + [...new Set(EDITIONS.map((e) => e.serie))].sort((a, b) => a.localeCompare(b, 'fr')).map((s) => `<option>${esc(s)}</option>`).join('');
    document.querySelectorAll('#rv-onglets button').forEach((b) => b.addEventListener('click', () => { vue = b.dataset.vue; limite = PAGE; afficher(); }));
    ['#rv-q', '#rv-serie'].forEach((s) => $(s).addEventListener('input', () => { limite = PAGE; afficher(); }));
    $('#rv-plus').addEventListener('click', () => { limite += PAGE; afficher(); });
    $('#rv-csv').addEventListener('click', csv);
    afficher();
  }).catch(() => { $('#rv-liste').innerHTML = '<p class="erreur">Les données n\'ont pas pu être chargées.</p>'; });
})();
