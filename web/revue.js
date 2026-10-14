/* Revue des prix : archive, relevé eBay et prix publié, côte à côte (outil du propriétaire, page non référencée). */
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const ETAT = { convenable: 'C', bon: 'BE', tres_bon: 'TBE' };
  const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const eur = (v) => (v == null ? '—' : v.toFixed(2).replace('.', ',') + ' €');
  const norm = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  let LIGNES = [], VUE = [];

  const ratio = (l) => (l.archive && l.publie ? l.publie / l.archive : null);
  const ecartImportant = (l) => { const r = ratio(l); return r != null && (r >= 2 || r <= 0.5); };
  const filtres = {
    ecart: ecartImportant,
    ebay: (l) => l.source && l.source !== 'archives',
    sans: (l) => l.eb_nb == null,
    aligne: (l) => l.ajuste,
    recalibre: (l) => l.recalibre,
    deduit: (l) => l.deduit,
  };
  const tris = {
    ecart: (a, b) => Math.abs(Math.log(ratio(b) || 1)) - Math.abs(Math.log(ratio(a) || 1)),
    titre: (a, b) => a.titre.localeCompare(b.titre, 'fr') || a.version.localeCompare(b.version),
    serie: (a, b) => a.serie.localeCompare(b.serie, 'fr') || (parseInt(a.numero, 10) || 0) - (parseInt(b.numero, 10) || 0) || a.version.localeCompare(b.version),
    publie: (a, b) => (b.publie || 0) - (a.publie || 0),
    annonces: (a, b) => (b.eb_nb || 0) - (a.eb_nb || 0),
  };

  function ligneHtml(l) {
    const r = ratio(l);
    const eb = l.eb_nb == null ? '<span class="sous">pas de relevé</span>'
      : `<strong>${eur(l.eb_med)}</strong> · ${l.eb_nb} annonce${l.eb_nb > 1 ? 's' : ''}<span class="sous" style="display:block">${eur(l.eb_min)} à ${eur(l.eb_max)}` +
        (l.eb_nb_toutes ? ` · toutes : ${eur(l.eb_med_toutes)} (${l.eb_nb_toutes})` : '') + '</span>';
    const notes = [l.ajuste ? 'ajusté' : '', l.recalibre ? 'modèle' : '', l.deduit ? 'déduit des autres états' : ''].filter(Boolean).join(', ');
    return `<tr${ecartImportant(l) ? ' class="alerte"' : ''}><td class="principal"><a href="./#q=${encodeURIComponent(l.isbn || l.id)}">${esc(l.titre)}</a>` +
      `<span class="sous" style="display:block">${esc(l.serie)}${l.numero && l.numero !== '000' ? ' n° ' + esc(l.numero) : ''} · <span class="badge">${esc(l.version)}</span></span></td>` +
      `<td data-label="État">${ETAT[l.etat] || l.etat}</td><td class="num" data-label="Archive">${eur(l.archive)}</td>` +
      `<td data-label="eBay">${eb}</td><td class="num" data-label="Publié"><strong>${eur(l.publie)}</strong></td>` +
      `<td class="num" data-label="Écart">${r == null ? '—' : '×' + r.toFixed(2).replace('.', ',')}</td>` +
      `<td data-label="Source">${esc(l.source || '—')}${notes ? ` <span class="sous">(${notes})</span>` : ''}</td></tr>`;
  }

  function afficher() {
    const q = norm($('#r-q').value).trim(), serie = $('#r-serie').value, etat = $('#r-etat').value, f = $('#r-filtre').value, t = $('#r-tri').value;
    VUE = LIGNES.filter((l) => (!q || norm(l.titre + ' ' + l.serie).includes(q)) && (!serie || l.serie === serie) && (!etat || l.etat === etat) && (!f || filtres[f](l))).sort(tris[t]);
    $('#r-compte').textContent = `${VUE.length} ligne${VUE.length > 1 ? 's' : ''} (édition × état) sur ${LIGNES.length}.` + (VUE.length > 300 ? ' Les 300 premières sont affichées : affinez avec les filtres.' : '');
    $('#r-zone').innerHTML = VUE.length
      ? `<table class="cartes revue"><thead><tr><th>Livre</th><th>État</th><th class="num">Archive</th><th>eBay (récent)</th><th class="num">Publié</th><th class="num">Écart</th><th>Source</th></tr></thead><tbody>${VUE.slice(0, 300).map(ligneHtml).join('')}</tbody></table>`
      : '<p>Aucune ligne pour ces filtres.</p>';
  }

  function csv() {
    const cols = ['isbn', 'titre', 'serie', 'numero', 'version', 'etat', 'archive', 'eb_nb', 'eb_med', 'eb_min', 'eb_max', 'eb_nb_toutes', 'eb_med_toutes', 'publie', 'source', 'ajuste', 'recalibre'];
    const q = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const texte = '﻿' + [cols.join(';')].concat(VUE.map((l) => cols.map((c) => (typeof l[c] === 'number' ? String(l[c]).replace('.', ',') : q(l[c]))).join(';'))).join('\r\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([texte], { type: 'text/csv;charset=utf-8' }));
    a.download = 'revue-des-prix.csv'; document.body.appendChild(a); a.click(); a.remove();
  }

  fetch('data/revue.json').then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then((d) => {
    LIGNES = d;
    $('#r-serie').innerHTML = '<option value="">Toutes</option>' + [...new Set(d.map((l) => l.serie))].sort((a, b) => a.localeCompare(b, 'fr')).map((s) => `<option>${esc(s)}</option>`).join('');
    ['#r-q', '#r-serie', '#r-etat', '#r-filtre', '#r-tri'].forEach((s) => $(s).addEventListener('input', afficher));
    $('#r-csv').addEventListener('click', csv);
    afficher();
  }).catch(() => { $('#r-zone').innerHTML = '<p class="erreur">Les données de revue n\'ont pas pu être chargées.</p>'; });
})();
