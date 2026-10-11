(() => {
  'use strict';

  const ETATS = [
    { k: 'convenable', label: 'Convenable' },
    { k: 'bon', label: 'Bon état' },
    { k: 'tres_bon', label: 'TBE', long: 'Très bon état' },
  ];
  const PAR_PAGE = 100;
  // « TBE » avec info-bulle ; les autres états s'écrivent en toutes lettres
  const nomEtat = (e) => (e.long ? `<abbr title="${e.long}">${e.label}</abbr>` : e.label);
  const eur = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' });
  const $ = (s) => document.querySelector(s);
  const fmt = (v) => (v == null ? '—' : eur.format(v));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const norm = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

  const initiale = (b) => esc((b.serie || '?').trim().charAt(0).toUpperCase());
  const miniature = (b) => (b.couverture
    ? `<img class="jaq" src="${esc(b.couverture)}" alt="" width="44" height="62" loading="lazy" decoding="async" referrerpolicy="no-referrer" data-i="${initiale(b)}">`
    : `<span class="jaq jaq-vide" aria-hidden="true">${initiale(b)}</span>`);
  const grande = (b) => (b.couverture_grande
    ? `<img class="jaq-grande" src="${esc(b.couverture_grande)}" alt="Jaquette de ${esc(b.titre)}" width="150" height="212" decoding="async" referrerpolicy="no-referrer" data-i="${initiale(b)}">`
    : '');

  let DATA = [];
  let META = {};
  let VERSIONS = [];
  let limite = PAR_PAGE;

  const ETAT_VIDE = () => ({
    q: '', serie: '', ed: '', amin: '', amax: '', vente: false,
    versions: new Set(VERSIONS), g: 'liste', tri: 'serie', h: 'bon',
  });
  let S = {};

  /* ---------- Chargement ---------- */
  async function charger() {
    try {
      const [v, m] = await Promise.all([
        fetch('data/versions.json').then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
        fetch('data/meta.json').then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
      ]);
      DATA = v;
      META = m;
    } catch (e) {
      $('#resultats').innerHTML =
        '<p class="vide-global">Les données n\'ont pas pu être chargées. ' +
        'Ouvrez le site depuis un serveur (par exemple <code>python -m http.server</code> dans le dossier <code>web</code>).</p>';
      return;
    }
    DATA.forEach((b) => {
      b._txt = norm([b.titre, b.livre, b.auteurs, b.isbn13, b.serie, b.editeur].join(' '));
    });
    VERSIONS = [...new Set(DATA.map((b) => b.version))].sort();
    S = ETAT_VIDE();
    construireControles();
    lireAdresse();
    synchroniserControles();
    // Sur téléphone, les filtres sont repliés au départ ; un résumé indique ceux qui sont actifs
    basculerFiltres(!window.matchMedia('(max-width: 700px)').matches);
    afficher();
  }

  /* ---------- Contrôles ---------- */
  function compter(cle, defaut) {
    const m = new Map();
    DATA.forEach((b) => { const k = b[cle] ?? defaut; m.set(k, (m.get(k) || 0) + 1); });
    return m;
  }

  function construireControles() {
    const series = compter('serie');
    $('#f-serie').innerHTML = '<option value="">Toutes les séries</option>' +
      [...series].sort((a, b) => a[0].localeCompare(b[0], 'fr'))
        .map(([k, n]) => `<option value="${esc(k)}">${esc(k)} (${n})</option>`).join('');

    const eds = compter('editeur', 'Non renseigné');
    $('#f-ed').innerHTML = '<option value="">Tous les éditeurs</option>' +
      [...eds].sort((a, b) => b[1] - a[1])
        .map(([k, n]) => `<option value="${esc(k)}">${esc(k)} (${n})</option>`).join('');

    const annees = [...new Set(DATA.map((b) => b.annee).filter(Boolean))].sort((a, b) => a - b);
    const opt = (v) => `<option value="${v}">${v}</option>`;
    $('#f-amin').innerHTML = '<option value="">Début</option>' + annees.map(opt).join('');
    $('#f-amax').innerHTML = '<option value="">Fin</option>' + annees.map(opt).join('');

    const vers = compter('version');
    $('#f-versions').innerHTML = VERSIONS.map((v) =>
      `<label class="puce"><input type="checkbox" value="${esc(v)}"><span>${esc(v)} <small>&nbsp;(${vers.get(v)})</small></span></label>`).join('');

    $('#h-etats').innerHTML = ETATS.map((e) =>
      `<label class="puce"><input type="radio" name="h-etat" value="${e.k}"><span>${e.label}</span></label>`).join('');
    $('#h-etats').addEventListener('change', (e) => { S.h = e.target.value; ecrireAdresse(); afficherHisto(filtrer()); });
    let attente;
    window.addEventListener('resize', () => { clearTimeout(attente); attente = setTimeout(() => afficherHisto(filtrer()), 150); });
    $('#f-q').addEventListener('input', (e) => { S.q = e.target.value; changer(); });
    $('#f-serie').addEventListener('change', (e) => { S.serie = e.target.value; changer(); });
    $('#f-ed').addEventListener('change', (e) => { S.ed = e.target.value; changer(); });
    $('#f-amin').addEventListener('change', (e) => { S.amin = e.target.value; changer(); });
    $('#f-amax').addEventListener('change', (e) => { S.amax = e.target.value; changer(); });
    $('#f-vente').addEventListener('change', (e) => { S.vente = e.target.checked; changer(); });
    $('#f-groupe').addEventListener('change', (e) => { S.g = e.target.value; changer(); });
    $('#f-tri').addEventListener('change', (e) => { S.tri = e.target.value; changer(); });
    $('#f-versions').addEventListener('change', (e) => {
      if (e.target.checked) S.versions.add(e.target.value); else S.versions.delete(e.target.value);
      changer();
    });
    $('#bascule').addEventListener('click', () => basculerFiltres());
    $('#reinit').addEventListener('click', () => { S = ETAT_VIDE(); synchroniserControles(); changer(); });
    $('#fiche').addEventListener('click', (e) => { if (e.target === $('#fiche')) $('#fiche').close(); });
    window.addEventListener('hashchange', () => { lireAdresse(); synchroniserControles(); afficher(); });
  }

  function synchroniserControles() {
    $('#f-q').value = S.q;
    $('#f-serie').value = S.serie;
    $('#f-ed').value = S.ed;
    $('#f-amin').value = S.amin;
    $('#f-amax').value = S.amax;
    $('#f-vente').checked = S.vente;
    $('#f-groupe').value = S.g;
    $('#f-tri').value = S.tri;
    document.querySelectorAll('#h-etats input').forEach((i) => { i.checked = i.value === S.h; });
    document.querySelectorAll('#f-versions input').forEach((i) => { i.checked = S.versions.has(i.value); });
  }

  function nbFiltres() {
    return [S.q.trim(), S.serie, S.ed, S.amin || S.amax, S.vente,
      S.versions.size !== VERSIONS.length].filter(Boolean).length;
  }

  function resumeFiltres() {
    const t = [];
    if (S.q.trim()) t.push(`Recherche « ${S.q.trim()} »`);
    if (S.serie) t.push(`Série : ${S.serie}`);
    if (S.ed) t.push(`Éditeur : ${S.ed}`);
    if (S.amin || S.amax) t.push(S.amin && S.amax ? (S.amin === S.amax ? `Année ${S.amin}` : `Années ${S.amin} à ${S.amax}`) : (S.amin ? `Depuis ${S.amin}` : `Jusqu'en ${S.amax}`));
    if (S.versions.size !== VERSIONS.length) t.push(`Version${S.versions.size > 1 ? 's' : ''} : ${[...S.versions].sort().join(', ') || 'aucune'}`);
    if (S.vente) t.push('Encore en vente');
    return t.join(' · ');
  }

  function basculerFiltres(ouvert) {
    const bloc = $('#filtres');
    const voir = ouvert === undefined ? bloc.hidden : ouvert;
    bloc.hidden = !voir;
    bloc.parentElement.classList.toggle('replie', !voir);
    $('#bascule').textContent = voir ? 'Masquer' : 'Afficher';
    majResume();
    $('#bascule').setAttribute('aria-expanded', String(voir));
  }

  function majResume() {
    const r = resumeFiltres();
    $('#resume').textContent = r;
    $('#resume').hidden = !r || !$('#filtres').hidden;
  }

  function changer() { limite = PAR_PAGE; ecrireAdresse(); afficher(); }

  /* ---------- Adresse (filtres partageables) ---------- */
  function ecrireAdresse() {
    const p = new URLSearchParams();
    const d = ETAT_VIDE();
    if (S.q) p.set('q', S.q);
    if (S.serie) p.set('serie', S.serie);
    if (S.ed) p.set('ed', S.ed);
    if (S.amin) p.set('amin', S.amin);
    if (S.amax) p.set('amax', S.amax);
    if (S.vente) p.set('vente', '1');
    if (S.versions.size !== d.versions.size) p.set('v', [...S.versions].join(','));
    if (S.g !== 'liste') p.set('g', S.g);
    if (S.tri !== 'serie') p.set('tri', S.tri);
    if (S.h !== 'bon') p.set('h', S.h);
    const h = p.toString();
    history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
  }

  function lireAdresse() {
    const p = new URLSearchParams(location.hash.slice(1));
    S = ETAT_VIDE();
    S.q = p.get('q') || '';
    S.serie = p.get('serie') || '';
    S.ed = p.get('ed') || '';
    S.amin = p.get('amin') || '';
    S.amax = p.get('amax') || '';
    S.vente = p.get('vente') === '1';
    if (p.has('v')) S.versions = new Set(p.get('v').split(',').filter((v) => VERSIONS.includes(v)));
    if (['liste', 'serie', 'version', 'annee', 'decennie', 'editeur'].includes(p.get('g'))) S.g = p.get('g');
    if (p.get('tri')) S.tri = p.get('tri');
    if (ETATS.some((e) => e.k === p.get('h'))) S.h = p.get('h');
  }

  /* ---------- Calculs ---------- */
  function filtrer() {
    const q = norm(S.q.trim());
    const amin = S.amin ? +S.amin : null;
    const amax = S.amax ? +S.amax : null;
    return DATA.filter((b) =>
      (!q || b._txt.includes(q)) &&
      (!S.serie || b.serie === S.serie) &&
      S.versions.has(b.version) &&
      (!S.ed || (b.editeur || 'Non renseigné') === S.ed) &&
      (amin === null || (b.annee && b.annee >= amin)) &&
      (amax === null || (b.annee && b.annee <= amax)) &&
      (!S.vente || b.en_vente === 1));
  }

  function stat(liste, k) {
    const v = liste.map((b) => b.prix[k]).filter((x) => x != null).sort((a, b) => a - b);
    if (!v.length) return { n: 0 };
    const somme = v.reduce((a, b) => a + b, 0);
    const m = v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2;
    return { n: v.length, avg: somme / v.length, min: v[0], max: v[v.length - 1], med: m };
  }

  /* ---------- Affichage ---------- */
  function afficher() {
    const liste = filtrer();
    majResume();
    const nf = nbFiltres();
    $('#nb-filtres').textContent = nf ? `· ${nf} actif${nf > 1 ? 's' : ''}` : '';
    $('#compte').textContent = `· ${liste.length} livre${liste.length > 1 ? 's' : ''} sur ${DATA.length}`;
    afficherKpis(liste);
    afficherHisto(liste);
    $('#alerte').innerHTML = avertissement();
    $('#alerte').hidden = !avertissement();
    $('#bloc-tri').hidden = S.g !== 'liste';
    if (!liste.length) {
      $('#resultats').innerHTML = '<p class="vide-global">Aucun livre ne correspond à ces filtres.</p>';
    } else if (S.g === 'liste') {
      afficherListe(liste);
    } else {
      afficherGroupes(liste);
    }
    afficherPied();
  }

  function afficherKpis(liste) {
    $('#kpis').innerHTML = ETATS.map((e) => {
      const s = stat(liste, e.k);
      if (!s.n) {
        return `<div class="kpi"><h3>${nomEtat(e)}</h3><p class="gros">—</p><p class="vide">Aucun prix pour ce filtre</p></div>`;
      }
      return `<div class="kpi"><h3>${nomEtat(e)}</h3><p class="gros">${fmt(s.avg)}</p>` +
        `<p class="detail">Médiane ${fmt(s.med)}</p>` +
        `<p class="detail">De ${fmt(s.min)} à ${fmt(s.max)}</p>` +
        `<p class="detail">${s.n} livre${s.n > 1 ? 's' : ''} chiffré${s.n > 1 ? 's' : ''} sur ${liste.length}</p></div>`;
    }).join('');
  }

  function cellulesPrix(b) {
    return ETATS.map((e) =>
      `<td class="num prix-ligne" data-label="${e.label}"><span class="prix${b.prix[e.k] == null ? ' nul' : ''}">${fmt(b.prix[e.k])}</span></td>`).join('');
  }

  function trier(liste) {
    const num = (b) => parseInt(b.numero, 10) || 0;
    const cmp = {
      serie: (a, b) => a.serie.localeCompare(b.serie, 'fr') || num(a) - num(b) || a.version_n - b.version_n,
      titre: (a, b) => a.titre.localeCompare(b.titre, 'fr') || a.version_n - b.version_n,
      annee: (a, b) => (a.annee || 9999) - (b.annee || 9999) || a.titre.localeCompare(b.titre, 'fr'),
      'bon-desc': (a, b) => (b.prix.bon ?? -1) - (a.prix.bon ?? -1),
      'bon-asc': (a, b) => (a.prix.bon ?? 1e9) - (b.prix.bon ?? 1e9),
    }[S.tri] || (() => 0);
    return [...liste].sort(cmp);
  }

  function afficherListe(liste) {
    const tri = trier(liste);
    const vus = tri.slice(0, limite);
    const lignes = vus.map((b) => `
      <tr class="cliquable" data-id="${esc(b.id)}">
        <td class="principal titre-livre"><div class="livre">${miniature(b)}<div><button type="button" data-id="${esc(b.id)}">${esc(b.titre)}</button>
          <span class="sous">${esc(b.serie)}${b.numero && b.numero !== '000' ? ' n° ' + esc(b.numero) : ''}</span></div></div></td>
        <td data-label="Version"><span class="badge">${esc(b.version)}</span></td>
        <td data-label="Année">${b.annee ?? '—'}</td>
        <td data-label="Éditeur">${esc(b.editeur || '—')}</td>
        ${cellulesPrix(b)}
      </tr>`).join('');
    const reste = tri.length - vus.length;
    $('#resultats').innerHTML = `
      <table class="cartes liste">
        <thead><tr><th>Livre</th><th>Version</th><th>Année</th><th>Éditeur</th>
          ${ETATS.map((e) => `<th class="num">${nomEtat(e)}</th>`).join('')}</tr></thead>
        <tbody>${lignes}</tbody>
      </table>
      ${reste > 0 ? `<button type="button" class="plus" id="plus">Afficher les ${Math.min(reste, PAR_PAGE)} suivants (${reste} restants)</button>` : ''}`;
    const plus = $('#plus');
    if (plus) plus.addEventListener('click', () => { limite += PAR_PAGE; afficherListe(liste); });
    $('#resultats').querySelectorAll('tr.cliquable').forEach((tr) =>
      tr.addEventListener('click', () => ouvrirFiche(tr.dataset.id)));
  }

  function cleGroupe(b) {
    switch (S.g) {
      case 'serie': return b.serie;
      case 'version': return b.version;
      case 'annee': return b.annee ?? 'Année inconnue';
      case 'decennie': return b.annee ? `${Math.floor(b.annee / 10) * 10}` : 'Année inconnue';
      default: return b.editeur || 'Non renseigné';
    }
  }

  function afficherGroupes(liste) {
    const m = new Map();
    liste.forEach((b) => { const k = String(cleGroupe(b)); (m.get(k) || m.set(k, []).get(k)).push(b); });
    let groupes = [...m].map(([k, l]) => ({ k, l, bon: stat(l, 'bon') }));
    if (['version', 'annee', 'decennie'].includes(S.g)) {
      groupes.sort((a, b) => a.k.localeCompare(b.k, 'fr', { numeric: true }));
    } else {
      groupes.sort((a, b) => b.l.length - a.l.length || a.k.localeCompare(b.k, 'fr'));
    }
    const maxBon = Math.max(...groupes.map((g) => g.bon.avg || 0), 1);
    const libelle = { serie: 'Série', version: 'Version', annee: 'Année', decennie: 'Décennie', editeur: 'Éditeur' }[S.g];
    const lignes = groupes.map((g) => {
      const nom = S.g === 'decennie' && g.k !== 'Année inconnue' ? `Années ${g.k}` : g.k;
      const cellules = ETATS.map((e) => {
        const s = stat(g.l, e.k);
        const barre = e.k === 'bon' && s.n ? `<span class="barre" style="width:${Math.max(4, (s.avg / maxBon) * 100)}%"></span>` : '';
        return `<td class="num prix-ligne" data-label="${e.label}"><span class="prix${s.n ? '' : ' nul'}">${fmt(s.avg)}</span>${barre}</td>`;
      }).join('');
      return `<tr class="cliquable" data-groupe="${esc(g.k)}">
        <td class="principal titre-livre"><button type="button" data-groupe="${esc(g.k)}">${esc(nom)}</button></td>
        <td class="num" data-label="Livres">${g.l.length}</td>${cellules}</tr>`;
    }).join('');
    $('#resultats').innerHTML = `
      <table class="cartes groupes">
        <thead><tr><th>${libelle}</th><th class="num">Livres</th>
          ${ETATS.map((e) => `<th class="num">${nomEtat(e)} (moyenne)</th>`).join('')}</tr></thead>
        <tbody>${lignes}</tbody>
      </table>
      <p class="sous" style="margin:12px 0 0">Cliquez sur une ligne pour ne garder que ce groupe et voir ses livres.</p>`;
    $('#resultats').querySelectorAll('tr.cliquable').forEach((tr) =>
      tr.addEventListener('click', () => appliquerGroupe(tr.dataset.groupe)));
  }

  function appliquerGroupe(k) {
    if (S.g === 'serie') S.serie = k;
    else if (S.g === 'version') S.versions = new Set([k]);
    else if (S.g === 'annee' && k !== 'Année inconnue') { S.amin = k; S.amax = k; }
    else if (S.g === 'decennie' && k !== 'Année inconnue') { S.amin = k; S.amax = String(+k + 9); }
    else if (S.g === 'editeur') S.ed = k;
    S.g = 'liste';
    synchroniserControles();
    changer();
    window.scrollTo({ top: $('#titre-moyenne').getBoundingClientRect().top + window.scrollY - 12, behavior: 'smooth' });
  }


  /* ---------- Histogramme des fréquences ---------- */
  const LARGEURS = [0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200];
  const fmtN = (x) => (Number.isInteger(x) ? String(x) : x.toLocaleString('fr-FR'));

  function percentile(tri, q) { return tri[Math.floor(q * (tri.length - 1))]; }

  // Tranches « rondes » de 0 jusqu'au 95e centile ; une dernière tranche regroupe les prix plus élevés.
  function tranches(valeurs) {
    const tri = [...valeurs].sort((a, b) => a - b);
    const max = tri[tri.length - 1];
    let plafond = percentile(tri, 0.95);
    if (max <= plafond * 1.15) plafond = max;
    if (plafond <= 0) plafond = 1;
    const cible = Math.min(14, Math.max(6, Math.round(Math.sqrt(valeurs.length))));
    const largeur = LARGEURS.find((l) => l >= plafond / cible) || LARGEURS[LARGEURS.length - 1];
    const nb = Math.floor(plafond / largeur) + 1;
    const limite = nb * largeur;
    const comptes = new Array(nb).fill(0);
    let plus = 0;
    valeurs.forEach((v) => { if (v >= limite) plus += 1; else comptes[Math.floor(v / largeur)] += 1; });
    return { largeur, nb, limite, comptes, plus };
  }

  function pasAxe(maxi) {
    return [1, 2, 5, 10, 20, 25, 50, 100, 200, 500].find((p) => maxi / p <= 4) || 500;
  }

  function afficherHisto(liste) {
    const etat = ETATS.find((e) => e.k === S.h) || ETATS[1];
    const valeurs = liste.map((b) => b.prix[etat.k]).filter((x) => x != null);
    const zone = $('#histo');
    const nom = etat.long || etat.label;
    $('#titre-histo').textContent = `Répartition des prix · ${nom}`;
    $('#histo-chiffres').hidden = !valeurs.length;
    if (!valeurs.length) {
      zone.innerHTML = '<p class="vide-histo">Aucun prix pour cette sélection.</p>';
      $('#histo-legende').innerHTML = '';
      $('#histo-table').innerHTML = '';
      $('#histo-note').textContent = '';
      return;
    }
    const st = stat(liste, etat.k);
    const t = tranches(valeurs);
    const avecPlus = t.plus > 0;
    const nbBarres = t.nb + (avecPlus ? 1 : 0);
    const toutes = [...t.comptes, ...(avecPlus ? [t.plus] : [])];
    const W = Math.max(280, zone.clientWidth || 600);
    const H = W < 500 ? 210 : 250;
    const m = { g: 34, d: 8, h: 20, b: 30 };
    const pw = W - m.g - m.d;
    const ph = H - m.h - m.b;
    const bw = pw / nbBarres;
    const pas = pasAxe(Math.max(...toutes));
    const ymax = Math.ceil(Math.max(...toutes) / pas) * pas;
    const y = (n) => m.h + ph - (n / ymax) * ph;
    const xPrix = (v) => (v < t.limite ? m.g + (v / t.limite) * (t.nb * bw) : m.g + t.nb * bw + bw / 2);

    let svg = '';
    for (let g = 0; g <= ymax; g += pas) {
      svg += `<line class="${g === 0 ? 'h-axe' : 'h-grille'}" x1="${m.g}" x2="${W - m.d}" y1="${y(g)}" y2="${y(g)}"/>` +
             `<text class="h-txt" x="${m.g - 6}" y="${y(g) + 4}" text-anchor="end">${g}</text>`;
    }
    let nombres = '';
    toutes.forEach((n, i) => {
      const plus = avecPlus && i === t.nb;
      const debut = i * t.largeur;
      const lib = plus ? `à partir de ${fmtN(t.limite)} €` : `de ${fmtN(debut)} à ${fmtN(debut + t.largeur)} €`;
      const x = m.g + i * bw + 1.5;
      const h = (n / ymax) * ph;
      svg += `<rect class="${plus ? 'h-bar-plus' : 'h-bar'}" x="${x}" y="${y(n)}" width="${Math.max(1, bw - 3)}" height="${h}" rx="2">` +
             `<title>${lib} : ${n} livre${n > 1 ? 's' : ''}</title></rect>`;
      if (n > 0 && bw >= 17) nombres += `<text class="h-n" x="${x + (bw - 3) / 2}" y="${y(n) - 4}" text-anchor="middle">${n}</text>`;
    });
    // repères sur l'axe des prix : une étiquette tous les k intervalles pour éviter les chevauchements
    const pasEtiquette = Math.max(1, Math.ceil(36 / bw));
    for (let i = 0; i <= t.nb; i += pasEtiquette) {
      svg += `<text class="h-txt" x="${m.g + i * bw}" y="${H - 10}" text-anchor="${i === 0 ? 'start' : 'middle'}">${fmtN(i * t.largeur)}${i === 0 ? ' €' : ''}</text>`;
    }
    if (avecPlus) svg += `<text class="h-txt" x="${m.g + t.nb * bw + bw / 2}" y="${H - 10}" text-anchor="middle">+</text>`;
    svg += `<line class="h-med" x1="${xPrix(st.med)}" x2="${xPrix(st.med)}" y1="${m.h - 6}" y2="${m.h + ph}"/>`;
    svg += `<line class="h-moy" x1="${xPrix(st.avg)}" x2="${xPrix(st.avg)}" y1="${m.h - 6}" y2="${m.h + ph}"/>`;
    svg += nombres;

    zone.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" ` +
      `aria-label="Histogramme des prix en ${esc(nom.toLowerCase())} : ${valeurs.length} livres, médiane ${fmt(st.med)}, moyenne ${fmt(st.avg)}">${svg}</svg>`;

    $('#histo-note').textContent =
      `Chaque barre compte les livres dont le prix est dans la tranche (${fmtN(t.largeur)} € de large). ` +
      `${valeurs.length} livre${valeurs.length > 1 ? 's' : ''} chiffré${valeurs.length > 1 ? 's' : ''}` +
      `${avecPlus ? `, dont ${t.plus} à partir de ${fmtN(t.limite)} € regroupés dans la dernière barre` : ''}.`;
    $('#histo-legende').innerHTML =
      `<span class="leg"><i class="trait med"></i>Médiane ${fmt(st.med)}</span>` +
      `<span class="leg"><i class="trait"></i>Moyenne ${fmt(st.avg)}</span>` +
      (st.avg >= t.limite ? '<span class="leg sous">La moyenne dépasse la dernière tranche affichée.</span>' : '');
    const lignes = toutes.map((n, i) => {
      const plus = avecPlus && i === t.nb;
      const debut = i * t.largeur;
      return `<tr><td>${plus ? `À partir de ${fmtN(t.limite)} €` : `${fmtN(debut)} à ${fmtN(debut + t.largeur)} €`}</td>` +
             `<td class="num">${n}</td><td class="num">${Math.round((n / valeurs.length) * 100)} %</td></tr>`;
    }).join('');
    $('#histo-table').innerHTML =
      `<table><thead><tr><th>Tranche de prix</th><th class="num">Livres</th><th class="num">Part</th></tr></thead><tbody>${lignes}</tbody></table>`;
  }

  /* ---------- Fiche d'un livre ---------- */
  function ouvrirFiche(id) {
    const b = DATA.find((x) => x.id === id);
    if (!b) return;
    const autres = DATA.filter((x) => x.livre_id === b.livre_id).sort((x, y) => x.version_n - y.version_n);
    const ligne = (nom, val) => (val ? `<div><dt>${nom}</dt><dd>${val}</dd></div>` : '');
    const annee = b.annee ? (b.annee_bnf && b.annee_bnf !== b.annee ? `${b.annee} <span class="sous">(notice BnF : ${b.annee_bnf})</span>` : b.annee) : '';
    const numero = b.numero && b.numero !== '000' ? ` n° ${esc(b.numero)}` : '';
    const notice = b.notice ? `<a href="${esc(b.notice)}" target="_blank" rel="noopener">Notice BnF</a>` : '';
    $('#fiche-contenu').innerHTML = `
      <div class="fiche">
        <div class="fiche-tete">
          <h2 id="fiche-titre">${esc(b.titre)}</h2>
          <button type="button" class="fermer" id="fermer" aria-label="Fermer la fiche">×</button>
        </div>
        <p class="fiche-sous"><span class="badge">${esc(b.version)}</span> ${esc(b.serie)}${numero}${b.en_vente === 1 ? ' · encore en vente' : ''}</p>
        <div class="fiche-corps">
        ${grande(b)}
        <dl class="infos">
          ${ligne('Auteurs', esc(b.auteurs))}
          ${ligne('Traducteur', esc(b.traducteur))}
          ${ligne('Illustrateur', esc(b.illustrateur))}
          ${ligne('Éditeur', esc(b.editeur))}
          ${ligne('Collection', esc(b.collection))}
          ${ligne('Année d\'édition', annee)}
          ${ligne('Pages', b.pages)}
          ${ligne('ISBN', esc(b.isbn13))}
          ${ligne('Source', notice)}
        </dl>
        </div>
        <h3>Prix de cette version</h3>
        <div class="mini-prix">
          ${ETATS.map((e) => `<div><span class="petit">${nomEtat(e)}</span><span class="valeur">${fmt(b.prix[e.k])}</span></div>`).join('')}
        </div>
        ${autres.length > 1 ? `
        <h3>Les ${autres.length} versions de ce livre</h3>
        <table class="cartes versions">
          <thead><tr><th>Version</th><th>Année</th><th>Éditeur</th>${ETATS.map((e) => `<th class="num">${nomEtat(e)}</th>`).join('')}</tr></thead>
          <tbody>${autres.map((x) => `
            <tr class="cliquable${x.id === b.id ? ' courant' : ''}" data-autre="${esc(x.id)}">
              <td class="principal sans-etiquette"><span class="badge">${esc(x.version)}</span>${x.id === b.id ? ' <span class="sous" style="display:inline">(affichée)</span>' : ''}</td>
              <td data-label="Année">${x.annee ?? '—'}</td>
              <td class="large2" data-label="Éditeur">${esc(x.editeur || '—')}</td>
              ${cellulesPrix(x)}
            </tr>`).join('')}</tbody>
        </table>` : ''}
        <p class="sous" style="margin-top:16px">${avertissement()}</p>
      </div>`;
    const dlg = $('#fiche');
    $('#fermer').addEventListener('click', () => dlg.close());
    $('#fiche-contenu').querySelectorAll('tr[data-autre]').forEach((tr) =>
      tr.addEventListener('click', () => { if (tr.dataset.autre !== b.id) ouvrirFiche(tr.dataset.autre); }));
    if (!dlg.open) dlg.showModal();
    dlg.scrollTop = 0;
  }

  // Une jaquette qui ne charge pas est remplacée par une tuile (l'événement « error » ne remonte pas : phase de capture)
  document.addEventListener('error', (e) => {
    const img = e.target;
    if (!(img instanceof HTMLImageElement)) return;
    if (img.classList.contains('jaq') || img.classList.contains('jaq-grande')) {
      const t = document.createElement('span');
      t.className = img.classList.contains('jaq') ? 'jaq jaq-vide' : 'jaq-grande jaq-vide';
      t.setAttribute('aria-hidden', 'true');
      t.textContent = img.dataset.i || '?';
      img.replaceWith(t);
    }
  }, true);

  document.addEventListener('click', (e) => {
    const bouton = e.target.closest('button[data-id]');
    if (bouton) { e.stopPropagation(); ouvrirFiche(bouton.dataset.id); }
  });

  // Tant qu'aucune vente réelle n'est chargée, les prix sont des prix anciens : on le dit clairement.
  const prixAnciens = () => !(META.types_prix || []).some((t) => t.startsWith('Vente réelle'));
  // L'adresse du site source ne doit jamais être coupée en fin de ligne
  const SRC = '<span class="nowrap">collection-ldvelh.fr</span>';
  const avertissement = () => (prixAnciens()
    ? `Prix anciens, issus d'un relevé de ${SRC} qui n'est plus mis à jour : un ordre de grandeur, pas la cote d'aujourd'hui.`
    : '');

  function afficherPied() {
    $('#pied').innerHTML =
      `<p><strong>Comment lire ces prix.</strong> Chaque prix est la moyenne, pour l'état choisi, des livres du filtre. ` +
      `Un livre sans prix pour un état est ignoré dans cette moyenne. TBE : très bon état.</p>` +
      `<p>Source des prix : ${esc((META.sources_prix || []).join(', ')).replace('collection-ldvelh.fr', SRC)}.` +
      `${prixAnciens() ? ' Ces prix sont anciens et ne sont plus mis à jour.' : ''}</p>` +
      `<p>Jaquettes : © leurs éditeurs, reproduites ici à titre d'illustration ; source : ${SRC}.</p>` +
      `<p>${META.nb_versions} versions · ${META.nb_livres} livres · ${META.nb_series} séries · données générées le ` +
      `${new Date(META.genere_le).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}.</p>`;
  }

  charger();
})();
