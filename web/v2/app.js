(() => {
  'use strict';

  const DONNEES = '../data/';
  const ETATS = [
    { k: 'convenable', court: 'Convenable', long: 'Convenable',
      def: 'Complet et lisible, mais marqué par l\'usage : plis, coins usés, dos passé.' },
    { k: 'bon', court: 'Bon état', long: 'Bon état',
      def: 'Complet, quelques marques du temps : coins légèrement frottés, pages un peu jaunies.' },
    { k: 'tres_bon', court: 'TBE', long: 'Très bon état',
      def: 'Presque comme à la parution : peu ou pas de traces de lecture. TBE signifie « très bon état ».' },
  ];
  const PAR_PAGE = 48;
  const eur = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' });
  const fmt = (v) => (v == null ? '—' : eur.format(v));
  const fmtN = (x) => (Number.isInteger(x) ? String(x) : x.toLocaleString('fr-FR'));
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const norm = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const SRC = '<span class="nowrap">collection-ldvelh.fr</span>';
  const etatDe = (k) => ETATS.find((e) => e.k === k) || ETATS[1];
  const racine = (b) => (b ? '../' + b : null);          // les images sont à la racine de web/
  const numero = (b) => (b.numero && b.numero !== '000' ? ` n° ${b.numero}` : '');

  let DATA = [];
  let META = {};
  let VERSIONS = [];
  let limite = PAR_PAGE;
  let S = {};

  const defaut = () => ({
    q: '', serie: '', ed: '', amin: '', amax: '', vente: false, versions: new Set(VERSIONS),
    h: 'bon', vue: 'etagere', tri: 'serie', g: 'serie',
  });

  /* ---------- Chargement ---------- */
  async function charger() {
    try {
      const [v, m] = await Promise.all([
        fetch(DONNEES + 'versions.json').then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
        fetch(DONNEES + 'meta.json').then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
      ]);
      DATA = v; META = m;
    } catch (e) {
      $('#resultats').innerHTML = '<p class="vide-global">Les données n\'ont pas pu être chargées. ' +
        'Ouvrez le guide depuis un serveur (par exemple <code>python -m http.server</code> dans le dossier <code>web</code>).</p>';
      return;
    }
    DATA.forEach((b) => { b._txt = norm([b.titre, b.livre, b.auteurs, b.isbn13, b.serie, b.editeur].join(' ')); });
    VERSIONS = [...new Set(DATA.map((b) => b.version))].sort();
    S = defaut();
    construireHero();
    construireControles();
    lireAdresse();
    synchroniser();
    basculerSelecteur(!window.matchMedia('(max-width: 1000px)').matches);
    afficher();
  }

  /* ---------- En-tête : chiffres et éventail de jaquettes ---------- */
  function construireHero() {
    $('#chiffres-hero').innerHTML =
      `<li><b>${META.nb_versions}</b><span>éditions</span></li>` +
      `<li><b>${META.nb_livres}</b><span>livres</span></li>` +
      `<li><b>${META.nb_series}</b><span>séries</span></li>` +
      `<li><b>${VERSIONS.length}</b><span>générations d'éditions</span></li>`;
    // Cinq jaquettes de séries différentes (la plus chère de chaque série, en V1)
    const parSerie = new Map();
    DATA.filter((b) => b.version === 'V1' && b.couverture_grande).forEach((b) => {
      const cur = parSerie.get(b.serie);
      if (!cur || (b.prix.tres_bon ?? 0) > (cur.prix.tres_bon ?? 0)) parSerie.set(b.serie, b);
    });
    const choix = [...parSerie.values()].sort((a, b) => (b.prix.tres_bon ?? 0) - (a.prix.tres_bon ?? 0)).slice(0, 5);
    const ordre = [choix[3], choix[1], choix[0], choix[2], choix[4]].filter(Boolean);
    $('#eventail').innerHTML = ordre.map((b) =>
      `<img src="${esc(racine(b.couverture_grande))}" alt="" width="150" height="210" decoding="async">`).join('');
  }

  /* ---------- Contrôles ---------- */
  const compter = (cle, vide) => {
    const m = new Map();
    DATA.forEach((b) => { const k = b[cle] ?? vide; m.set(k, (m.get(k) || 0) + 1); });
    return m;
  };
  const anneeMediane = (v) => {
    const a = DATA.filter((b) => b.version === v && b.annee).map((b) => b.annee).sort((x, y) => x - y);
    return a.length ? a[Math.floor(a.length / 2)] : null;
  };

  function construireControles() {
    $('#f-serie').innerHTML = '<option value="">Toutes les séries</option>' +
      [...compter('serie')].sort((a, b) => a[0].localeCompare(b[0], 'fr'))
        .map(([k, n]) => `<option value="${esc(k)}">${esc(k)} (${n})</option>`).join('');
    $('#f-ed').innerHTML = '<option value="">Tous les éditeurs</option>' +
      [...compter('editeur', 'Non renseigné')].sort((a, b) => b[1] - a[1])
        .map(([k, n]) => `<option value="${esc(k)}">${esc(k)} (${n})</option>`).join('');
    const annees = [...new Set(DATA.map((b) => b.annee).filter(Boolean))].sort((a, b) => a - b);
    const opt = (v) => `<option value="${v}">${v}</option>`;
    $('#f-amin').innerHTML = '<option value="">Début</option>' + annees.map(opt).join('');
    $('#f-amax').innerHTML = '<option value="">Fin</option>' + annees.map(opt).join('');

    const nb = compter('version');
    $('#f-versions').innerHTML = VERSIONS.map((v) => {
      const m = anneeMediane(v);
      return `<label class="edition"><input type="checkbox" value="${esc(v)}"><span class="tampon">${esc(v)}</span>` +
        `<span class="reste"><span>Édition ${esc(v)}</span><small>${m ? `vers ${m}` : ''}</small></span>` +
        `<span class="nb">${nb.get(v)} livres</span></label>`;
    }).join('');

    $('#h-etats').innerHTML = ETATS.map((e) =>
      `<label><input type="radio" name="h-etat" value="${e.k}"><span>${e.court}</span></label>`).join('');

    $('#f-q').addEventListener('input', (e) => { S.q = e.target.value; changer(); });
    $('#f-serie').addEventListener('change', (e) => { S.serie = e.target.value; changer(); });
    $('#f-ed').addEventListener('change', (e) => { S.ed = e.target.value; changer(); });
    $('#f-amin').addEventListener('change', (e) => { S.amin = e.target.value; changer(); });
    $('#f-amax').addEventListener('change', (e) => { S.amax = e.target.value; changer(); });
    $('#f-vente').addEventListener('change', (e) => { S.vente = e.target.checked; changer(); });
    $('#f-versions').addEventListener('change', (e) => {
      if (e.target.checked) S.versions.add(e.target.value); else S.versions.delete(e.target.value);
      changer();
    });
    $('#h-etats').addEventListener('change', (e) => { S.h = e.target.value; ecrireAdresse(); afficher(); });
    $('#f-vue').addEventListener('change', (e) => { S.vue = e.target.value; changer(); });
    $('#f-tri').addEventListener('change', (e) => { S.tri = e.target.value; changer(); });
    $('#f-groupe').addEventListener('change', (e) => { S.g = e.target.value; changer(); });
    $('#reinit').addEventListener('click', () => { const { h, vue, tri, g } = S; S = { ...defaut(), h, vue, tri, g }; synchroniser(); changer(); });
    $('#bascule').addEventListener('click', () => basculerSelecteur());
    $('#fiche').addEventListener('click', (e) => { if (e.target === $('#fiche')) $('#fiche').close(); });
    window.addEventListener('hashchange', () => { lireAdresse(); synchroniser(); afficher(); });
    let attente;
    window.addEventListener('resize', () => { clearTimeout(attente); attente = setTimeout(afficher, 150); });
    construireLampe();
  }

  function construireLampe() {
    const bouton = $('#lampe');
    const sombre = () => {
      const t = document.documentElement.dataset.theme;
      return t ? t === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
    };
    const maj = () => bouton.setAttribute('aria-pressed', String(sombre()));
    bouton.addEventListener('click', () => {
      const t = sombre() ? 'light' : 'dark';
      document.documentElement.dataset.theme = t;
      try { localStorage.setItem('cote-theme', t); } catch (e) { /* stockage indisponible : sans conséquence */ }
      maj();
    });
    maj();
  }

  function synchroniser() {
    $('#f-q').value = S.q; $('#f-serie').value = S.serie; $('#f-ed').value = S.ed;
    $('#f-amin').value = S.amin; $('#f-amax').value = S.amax; $('#f-vente').checked = S.vente;
    $('#f-tri').value = S.tri; $('#f-groupe').value = S.g;
    document.querySelectorAll('#f-versions input').forEach((i) => { i.checked = S.versions.has(i.value); });
    document.querySelectorAll('#h-etats input').forEach((i) => { i.checked = i.value === S.h; });
    document.querySelectorAll('#f-vue input').forEach((i) => { i.checked = i.value === S.vue; });
  }

  function changer() { limite = PAR_PAGE; ecrireAdresse(); afficher(); }

  function nbFiltres() {
    return [S.q.trim(), S.serie, S.ed, S.amin || S.amax, S.vente, S.versions.size !== VERSIONS.length].filter(Boolean).length;
  }
  function resumeFiltres() {
    const t = [];
    if (S.q.trim()) t.push(`« ${S.q.trim()} »`);
    if (S.serie) t.push(S.serie);
    if (S.ed) t.push(S.ed);
    if (S.amin || S.amax) t.push(S.amin && S.amax ? (S.amin === S.amax ? S.amin : `${S.amin}–${S.amax}`) : (S.amin ? `depuis ${S.amin}` : `jusqu'en ${S.amax}`));
    if (S.versions.size !== VERSIONS.length) t.push([...S.versions].sort().join(', ') || 'aucune édition');
    if (S.vente) t.push('encore en vente');
    return t.join(' · ');
  }
  function basculerSelecteur(ouvert) {
    const f = $('#formulaire');
    const voir = ouvert === undefined ? f.hidden : ouvert;
    f.hidden = !voir;
    $('#bascule').textContent = voir ? 'Masquer' : 'Afficher';
    $('#bascule').setAttribute('aria-expanded', String(voir));
    majResume();
  }
  function majResume() {
    const r = resumeFiltres();
    $('#resume').textContent = r;
    $('#resume').hidden = !r || !$('#formulaire').hidden;
  }

  /* ---------- Adresse partageable ---------- */
  function ecrireAdresse() {
    const p = new URLSearchParams();
    const d = defaut();
    if (S.q) p.set('q', S.q);
    if (S.serie) p.set('serie', S.serie);
    if (S.ed) p.set('ed', S.ed);
    if (S.amin) p.set('amin', S.amin);
    if (S.amax) p.set('amax', S.amax);
    if (S.vente) p.set('vente', '1');
    if (S.versions.size !== d.versions.size) p.set('v', [...S.versions].join(','));
    if (S.h !== 'bon') p.set('h', S.h);
    if (S.vue !== 'etagere') p.set('vue', S.vue);
    if (S.tri !== 'serie') p.set('tri', S.tri);
    if (S.g !== 'serie') p.set('g', S.g);
    const h = p.toString();
    history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
  }
  function lireAdresse() {
    const p = new URLSearchParams(location.hash.slice(1));
    S = defaut();
    S.q = p.get('q') || ''; S.serie = p.get('serie') || ''; S.ed = p.get('ed') || '';
    S.amin = p.get('amin') || ''; S.amax = p.get('amax') || ''; S.vente = p.get('vente') === '1';
    if (p.has('v')) S.versions = new Set(p.get('v').split(',').filter((v) => VERSIONS.includes(v)));
    if (ETATS.some((e) => e.k === p.get('h'))) S.h = p.get('h');
    if (['etagere', 'liste', 'groupe'].includes(p.get('vue'))) S.vue = p.get('vue');
    if (['serie', 'titre', 'annee', 'cher', 'pascher'].includes(p.get('tri'))) S.tri = p.get('tri');
    if (['serie', 'version', 'annee', 'decennie', 'editeur'].includes(p.get('g'))) S.g = p.get('g');
  }

  /* ---------- Calculs ---------- */
  function filtrer() {
    const q = norm(S.q.trim());
    const amin = S.amin ? +S.amin : null;
    const amax = S.amax ? +S.amax : null;
    return DATA.filter((b) =>
      (!q || b._txt.includes(q)) && (!S.serie || b.serie === S.serie) && S.versions.has(b.version) &&
      (!S.ed || (b.editeur || 'Non renseigné') === S.ed) &&
      (amin === null || (b.annee && b.annee >= amin)) && (amax === null || (b.annee && b.annee <= amax)) &&
      (!S.vente || b.en_vente === 1));
  }
  function stat(liste, k) {
    const v = liste.map((b) => b.prix[k]).filter((x) => x != null).sort((a, b) => a - b);
    if (!v.length) return { n: 0 };
    const somme = v.reduce((a, b) => a + b, 0);
    const m = v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2;
    return { n: v.length, avg: somme / v.length, min: v[0], max: v[v.length - 1], med: m };
  }
  const prixAnciens = () => !(META.types_prix || []).some((t) => t.startsWith('Vente réelle'));

  /* ---------- Affichage général ---------- */
  function afficher() {
    const liste = filtrer();
    const nf = nbFiltres();
    $('#nb-filtres').textContent = nf ? String(nf) : '';
    $('#nb-filtres').setAttribute('aria-label', nf ? `${nf} filtre${nf > 1 ? 's' : ''} actif${nf > 1 ? 's' : ''}` : '');
    majResume();
    $('#compte').textContent = `${liste.length} livre${liste.length > 1 ? 's' : ''} sur ${DATA.length}`;
    afficherCote(liste);
    afficherHisto(liste);
    $('#bloc-tri').hidden = S.vue === 'groupe';
    $('#bloc-groupe').hidden = S.vue !== 'groupe';
    if (!liste.length) {
      $('#resultats').innerHTML = '<p class="vide-global">Aucun livre ne répond à ces critères. Élargissez la sélection ou effacez un filtre.</p>';
    } else if (S.vue === 'etagere') {
      afficherEtagere(liste);
    } else if (S.vue === 'liste') {
      afficherListe(liste);
    } else {
      afficherGroupes(liste);
    }
    afficherPied();
  }

  /* ---------- Cote : sceau et chiffres ---------- */
  function afficherCote(liste) {
    const e = etatDe(S.h);
    const st = stat(liste, e.k);
    $('#sceau').setAttribute('aria-label', st.n ? `Prix moyen en ${e.long.toLowerCase()} : ${fmt(st.avg)}` : 'Aucun prix pour cette sélection');
    $('#sceau').innerHTML = st.n
      ? `<span class="sceau-lib">Prix moyen</span><span class="sceau-prix">${fmt(st.avg)}</span><span class="sceau-etat">${esc(e.long.toLowerCase())}</span>`
      : '<span class="sceau-lib">Prix moyen</span><span class="sceau-prix">—</span><span class="sceau-etat">aucun prix</span>';
    $('#etat-def').textContent = e.def;
    $('#stats').innerHTML = st.n
      ? `<div><dt>Médiane</dt><dd>${fmt(st.med)}</dd></div>` +
        `<div><dt>Fourchette</dt><dd>${fmt(st.min)}<small>à ${fmt(st.max)}</small></dd></div>` +
        `<div><dt>Exemplaires chiffrés</dt><dd>${st.n}<small>sur ${liste.length} livres</small></dd></div>`
      : '<div><dt>Médiane</dt><dd>—</dd></div><div><dt>Fourchette</dt><dd>—</dd></div><div><dt>Exemplaires chiffrés</dt><dd>0</dd></div>';
    $('#trois').innerHTML = 'Pour comparer : ' + ETATS.map((x) => {
      const s = stat(liste, x.k);
      return `<span class="nowrap">${x.k === 'tres_bon' ? '<abbr title="Très bon état">TBE</abbr>' : x.court} <b>${s.n ? fmt(s.avg) : '—'}</b></span>`;
    }).join(' · ');
  }

  /* ---------- Histogramme des fréquences ---------- */
  const LARGEURS = [0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200];
  function percentile(tri, q) { return tri[Math.floor(q * (tri.length - 1))]; }
  function tranches(valeurs) {
    const tri = [...valeurs].sort((a, b) => a - b);
    const max = tri[tri.length - 1];
    let plafond = percentile(tri, 0.95);
    if (max <= plafond * 1.15) plafond = max;
    if (plafond <= 0) plafond = 1;
    const cible = Math.min(14, Math.max(6, Math.round(Math.sqrt(valeurs.length))));
    const largeur = LARGEURS.find((l) => l >= plafond / cible) || LARGEURS[LARGEURS.length - 1];
    const nb = Math.floor(plafond / largeur) + 1;
    const limiteHaute = nb * largeur;
    const comptes = new Array(nb).fill(0);
    let plus = 0;
    valeurs.forEach((v) => { if (v >= limiteHaute) plus += 1; else comptes[Math.floor(v / largeur)] += 1; });
    return { largeur, nb, limite: limiteHaute, comptes, plus };
  }
  const pasAxe = (maxi) => [1, 2, 5, 10, 20, 25, 50, 100, 200, 500].find((p) => maxi / p <= 4) || 500;

  function afficherHisto(liste) {
    const e = etatDe(S.h);
    const valeurs = liste.map((b) => b.prix[e.k]).filter((x) => x != null);
    const zone = $('#histo');
    $('#titre-histo').textContent = `Où se situent les prix · ${e.long.toLowerCase()}`;
    $('#histo-chiffres').hidden = !valeurs.length;
    if (!valeurs.length) {
      zone.innerHTML = '<p class="vide-histo">Aucun prix pour cette sélection.</p>';
      $('#histo-legende').innerHTML = ''; $('#histo-table').innerHTML = ''; $('#histo-note').textContent = '';
      return;
    }
    const st = stat(liste, e.k);
    const t = tranches(valeurs);
    const avecPlus = t.plus > 0;
    const nbBarres = t.nb + (avecPlus ? 1 : 0);
    const toutes = [...t.comptes, ...(avecPlus ? [t.plus] : [])];
    const W = Math.max(280, zone.clientWidth || 600);
    const H = W < 500 ? 210 : 250;
    const m = { g: 34, d: 8, h: 20, b: 30 };
    const pw = W - m.g - m.d, ph = H - m.h - m.b, bw = pw / nbBarres;
    const pas = pasAxe(Math.max(...toutes));
    const ymax = Math.ceil(Math.max(...toutes) / pas) * pas;
    const y = (n) => m.h + ph - (n / ymax) * ph;
    const xPrix = (v) => (v < t.limite ? m.g + (v / t.limite) * (t.nb * bw) : m.g + t.nb * bw + bw / 2);

    let svg = '', nombres = '';
    for (let g = 0; g <= ymax; g += pas) {
      svg += `<line class="${g === 0 ? 'h-axe' : 'h-grille'}" x1="${m.g}" x2="${W - m.d}" y1="${y(g)}" y2="${y(g)}"/>` +
             `<text class="h-txt" x="${m.g - 6}" y="${y(g) + 4}" text-anchor="end">${g}</text>`;
    }
    toutes.forEach((n, i) => {
      const plus = avecPlus && i === t.nb;
      const debut = i * t.largeur;
      const lib = plus ? `à partir de ${fmtN(t.limite)} €` : `de ${fmtN(debut)} à ${fmtN(debut + t.largeur)} €`;
      const x = m.g + i * bw + 1.5;
      svg += `<rect class="${plus ? 'h-bar-plus' : 'h-bar'}" x="${x}" y="${y(n)}" width="${Math.max(1, bw - 3)}" height="${(n / ymax) * ph}" rx="2">` +
             `<title>${lib} : ${n} livre${n > 1 ? 's' : ''}</title></rect>`;
      if (n > 0 && bw >= 17) nombres += `<text class="h-n" x="${x + (bw - 3) / 2}" y="${y(n) - 4}" text-anchor="middle">${n}</text>`;
    });
    const pasEt = Math.max(1, Math.ceil(36 / bw));
    for (let i = 0; i <= t.nb; i += pasEt) {
      svg += `<text class="h-txt" x="${m.g + i * bw}" y="${H - 10}" text-anchor="${i === 0 ? 'start' : 'middle'}">${fmtN(i * t.largeur)}${i === 0 ? ' €' : ''}</text>`;
    }
    if (avecPlus) svg += `<text class="h-txt" x="${m.g + t.nb * bw + bw / 2}" y="${H - 10}" text-anchor="middle">+</text>`;
    svg += `<line class="h-med" x1="${xPrix(st.med)}" x2="${xPrix(st.med)}" y1="${m.h - 6}" y2="${m.h + ph}"/>`;
    svg += `<line class="h-moy" x1="${xPrix(st.avg)}" x2="${xPrix(st.avg)}" y1="${m.h - 6}" y2="${m.h + ph}"/>`;
    svg += nombres;
    zone.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" ` +
      `aria-label="Histogramme des prix en ${esc(e.long.toLowerCase())} : ${valeurs.length} livres, médiane ${fmt(st.med)}, moyenne ${fmt(st.avg)}">${svg}</svg>`;
    $('#histo-note').textContent =
      `Chaque barre compte les livres dont le prix tombe dans la tranche (${fmtN(t.largeur)} € de large). ` +
      `${valeurs.length} livre${valeurs.length > 1 ? 's' : ''} chiffré${valeurs.length > 1 ? 's' : ''}` +
      `${avecPlus ? `, dont ${t.plus} à partir de ${fmtN(t.limite)} € regroupés dans la dernière barre` : ''}.`;
    $('#histo-legende').innerHTML =
      `<span class="leg"><i class="trait med"></i>Médiane ${fmt(st.med)}</span><span class="leg"><i class="trait"></i>Moyenne ${fmt(st.avg)}</span>` +
      (st.avg >= t.limite ? '<span class="leg sous">La moyenne dépasse la dernière tranche affichée.</span>' : '');
    $('#histo-table').innerHTML = '<table><thead><tr><th>Tranche de prix</th><th class="num">Livres</th><th class="num">Part</th></tr></thead><tbody>' +
      toutes.map((n, i) => {
        const plus = avecPlus && i === t.nb;
        const d = i * t.largeur;
        return `<tr><td>${plus ? `À partir de ${fmtN(t.limite)} €` : `${fmtN(d)} à ${fmtN(d + t.largeur)} €`}</td><td class="num">${n}</td><td class="num">${Math.round((n / valeurs.length) * 100)} %</td></tr>`;
      }).join('') + '</tbody></table>';
  }

  /* ---------- Étagère (jaquettes) ---------- */
  const tuile = (b, cls = 'jaq-vide') => `<span class="${cls}" aria-hidden="true">${esc((b.serie || '?').trim().charAt(0).toUpperCase())}</span>`;

  function trier(liste) {
    const num = (b) => parseInt(b.numero, 10) || 0;
    const k = etatDe(S.h).k;
    const cmp = {
      serie: (a, b) => a.serie.localeCompare(b.serie, 'fr') || num(a) - num(b) || a.version_n - b.version_n,
      titre: (a, b) => a.titre.localeCompare(b.titre, 'fr') || a.version_n - b.version_n,
      annee: (a, b) => (a.annee || 9999) - (b.annee || 9999) || a.titre.localeCompare(b.titre, 'fr'),
      cher: (a, b) => (b.prix[k] ?? -1) - (a.prix[k] ?? -1),
      pascher: (a, b) => (a.prix[k] ?? 1e9) - (b.prix[k] ?? 1e9),
    }[S.tri] || (() => 0);
    return [...liste].sort(cmp);
  }

  function afficherEtagere(liste) {
    const e = etatDe(S.h);
    const tri = trier(liste);
    const vus = tri.slice(0, limite);
    const cartes = vus.map((b) => {
      const p = b.prix[e.k];
      return `<button type="button" class="livre-carte" data-id="${esc(b.id)}" aria-label="${esc(b.titre)}, édition ${esc(b.version)}${p != null ? ', ' + fmt(p) + ' en ' + e.long.toLowerCase() : ''}">
        <span class="couv">${b.couverture
          ? `<img src="${esc(racine(b.couverture))}" alt="" width="88" height="124" loading="lazy" decoding="async" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">`
          : tuile(b)}<span class="tampon-v">${esc(b.version)}</span></span>
        <span><span class="titre">${esc(b.titre)}</span><span class="meta" style="display:block">${esc(b.serie)}${esc(numero(b))}${b.annee ? ' · ' + b.annee : ''}</span></span>
        <span class="prix${p == null ? ' nul' : ''}">${p == null ? 'Cote indisponible' : fmt(p)}${p == null ? '' : `<small>${e.k === 'tres_bon' ? 'TBE' : esc(e.court.toLowerCase())}</small>`}</span>
      </button>`;
    }).join('');
    const reste = tri.length - vus.length;
    $('#resultats').innerHTML = `<div class="rayon">${cartes}</div>` +
      (reste > 0 ? `<button type="button" class="plus" id="plus">Voir ${Math.min(reste, PAR_PAGE)} livres de plus (${reste} restants)</button>` : '');
    const plus = $('#plus');
    if (plus) plus.addEventListener('click', () => { limite += PAR_PAGE; afficherEtagere(liste); });
  }

  /* ---------- Liste ---------- */
  function cellulesPrix(b) {
    return ETATS.map((e) => `<td class="num" data-label="${e.court}"><span class="prix-c${b.prix[e.k] == null ? ' nul' : ''}">${fmt(b.prix[e.k])}</span></td>`).join('');
  }
  function afficherListe(liste) {
    const tri = trier(liste);
    const vus = tri.slice(0, limite);
    const lignes = vus.map((b) => `
      <tr class="cliquable" data-id="${esc(b.id)}">
        <td class="principal"><div class="l-livre">${b.couverture ? `<img src="${esc(racine(b.couverture))}" alt="" width="40" height="56" loading="lazy" decoding="async" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(b)}
          <div><button type="button" data-id="${esc(b.id)}">${esc(b.titre)}</button><span class="sous" style="display:block">${esc(b.serie)}${esc(numero(b))}</span></div></div></td>
        <td data-label="Édition"><span class="badge">${esc(b.version)}</span></td>
        <td data-label="Année">${b.annee ?? '—'}</td>
        <td data-label="Éditeur">${esc(b.editeur || '—')}</td>
        ${cellulesPrix(b)}
      </tr>`).join('');
    const reste = tri.length - vus.length;
    $('#resultats').innerHTML = `<table class="cartes liste"><thead><tr><th>Livre</th><th>Édition</th><th>Année</th><th>Éditeur</th>
      ${ETATS.map((e) => `<th class="num">${e.k === 'tres_bon' ? '<abbr title="Très bon état">TBE</abbr>' : e.court}</th>`).join('')}</tr></thead><tbody>${lignes}</tbody></table>` +
      (reste > 0 ? `<button type="button" class="plus" id="plus">Voir ${Math.min(reste, PAR_PAGE)} livres de plus (${reste} restants)</button>` : '');
    const plus = $('#plus');
    if (plus) plus.addEventListener('click', () => { limite += PAR_PAGE; afficherListe(liste); });
    $('#resultats').querySelectorAll('tr.cliquable').forEach((tr) => tr.addEventListener('click', () => ouvrirFiche(tr.dataset.id)));
  }

  /* ---------- Groupes ---------- */
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
    const groupes = [...m].map(([k, l]) => ({ k, l, bon: stat(l, S.h) }));
    if (['version', 'annee', 'decennie'].includes(S.g)) groupes.sort((a, b) => a.k.localeCompare(b.k, 'fr', { numeric: true }));
    else groupes.sort((a, b) => b.l.length - a.l.length || a.k.localeCompare(b.k, 'fr'));
    const maxi = Math.max(...groupes.map((g) => g.bon.avg || 0), 1);
    const nomCol = { serie: 'Série', version: 'Édition', annee: 'Année', decennie: 'Décennie', editeur: 'Éditeur' }[S.g];
    const lignes = groupes.map((g) => {
      const nom = S.g === 'decennie' && g.k !== 'Année inconnue' ? `Années ${g.k}` : (S.g === 'version' ? `Édition ${g.k}` : g.k);
      const cel = ETATS.map((e) => {
        const s = stat(g.l, e.k);
        const barre = e.k === S.h && s.n ? `<span class="barre" style="width:${Math.max(4, (s.avg / maxi) * 100)}%"></span>` : '';
        return `<td class="num" data-label="${e.court}"><span class="prix-c${s.n ? '' : ' nul'}">${fmt(s.avg)}</span>${barre}</td>`;
      }).join('');
      return `<tr class="cliquable" data-groupe="${esc(g.k)}"><td class="principal"><div class="l-livre"><button type="button" data-groupe="${esc(g.k)}">${esc(nom)}</button></div></td>
        <td class="num" data-label="Livres">${g.l.length}</td>${cel}</tr>`;
    }).join('');
    $('#resultats').innerHTML = `<table class="cartes groupes"><thead><tr><th>${nomCol}</th><th class="num">Livres</th>
      ${ETATS.map((e) => `<th class="num">${e.k === 'tres_bon' ? '<abbr title="Très bon état">TBE</abbr>' : e.court}</th>`).join('')}</tr></thead><tbody>${lignes}</tbody></table>
      <p class="sous" style="margin:14px 0 0">Prix moyens par groupe. Touchez une ligne pour ne garder que ce groupe et voir ses livres sur l'étagère.</p>`;
    $('#resultats').querySelectorAll('tr.cliquable').forEach((tr) => tr.addEventListener('click', () => appliquerGroupe(tr.dataset.groupe)));
  }
  function appliquerGroupe(k) {
    if (S.g === 'serie') S.serie = k;
    else if (S.g === 'version') S.versions = new Set([k]);
    else if (S.g === 'annee' && k !== 'Année inconnue') { S.amin = k; S.amax = k; }
    else if (S.g === 'decennie' && k !== 'Année inconnue') { S.amin = k; S.amax = String(+k + 9); }
    else if (S.g === 'editeur') S.ed = k;
    S.vue = 'etagere';
    synchroniser();
    changer();
    $('#cote').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  /* ---------- Fiche d'un livre ---------- */
  function ouvrirFiche(id) {
    const b = DATA.find((x) => x.id === id);
    if (!b) return;
    const sel = etatDe(S.h);
    const autres = DATA.filter((x) => x.livre_id === b.livre_id).sort((x, y) => x.version_n - y.version_n);
    const ligne = (nom, val) => (val ? `<div><dt>${nom}</dt><dd>${val}</dd></div>` : '');
    const annee = b.annee ? (b.annee_bnf && b.annee_bnf !== b.annee ? `${b.annee} <span class="sous">(notice BnF : ${b.annee_bnf})</span>` : b.annee) : '';
    const notice = b.notice ? `<a href="${esc(b.notice)}" target="_blank" rel="noopener">Notice de la BnF</a>` : '';
    $('#fiche-contenu').innerHTML = `
      <div class="fiche">
        <div class="fiche-haut">
          <div class="fiche-couv">${b.couverture_grande
            ? `<img src="${esc(racine(b.couverture_grande))}" alt="Jaquette de ${esc(b.titre)}" width="300" height="420" decoding="async" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">`
            : tuile(b)}</div>
          <div>
            <div class="fiche-tete"><h2 id="fiche-titre">${esc(b.titre)}</h2>
              <button type="button" class="fermer" id="fermer" aria-label="Fermer la fiche">×</button></div>
            <p class="fiche-sous"><span class="badge">${esc(b.version)}</span><span>${esc(b.serie)}${esc(numero(b))}</span>${b.en_vente === 1 ? '<span>· encore en vente neuve</span>' : ''}</p>
            <dl class="infos">
              ${ligne('Auteurs', esc(b.auteurs))}${ligne('Traducteur', esc(b.traducteur))}${ligne('Illustrateur', esc(b.illustrateur))}
              ${ligne('Éditeur', esc(b.editeur))}${ligne('Collection', esc(b.collection))}${ligne('Année d\'édition', annee)}
              ${ligne('Pages', b.pages)}${ligne('ISBN', esc(b.isbn13))}${ligne('Source', notice)}
            </dl>
          </div>
        </div>
        <h3>Cotes de cette édition</h3>
        <div class="cotes">${ETATS.map((e) => `<div class="${e.k === sel.k ? 'choisi' : ''}"><span class="petit">${e.k === 'tres_bon' ? '<abbr title="Très bon état">TBE</abbr>' : e.court}</span><span class="valeur">${fmt(b.prix[e.k])}</span></div>`).join('')}</div>
        ${autres.length > 1 ? `<h3>Les ${autres.length} éditions de ce livre</h3>
        <div class="autres">${autres.map((x) => `<button type="button" class="autre${x.id === b.id ? ' courante' : ''}" data-autre="${esc(x.id)}" aria-label="Édition ${esc(x.version)}${x.annee ? ', ' + x.annee : ''}">
          ${x.couverture ? `<img src="${esc(racine(x.couverture))}" alt="" width="88" height="124" loading="lazy" data-i="${esc((x.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(x)}
          <span class="v">${esc(x.version)}<small>${x.annee ?? ''}</small></span><span class="p">${fmt(x.prix[sel.k])}</span></button>`).join('')}</div>` : ''}
        ${prixAnciens() ? `<p class="sous" style="margin-top:16px">Cotes d'archives, issues d'un relevé de ${SRC} qui n'est plus mis à jour : un ordre de grandeur, pas la cote du jour.</p>` : ''}
      </div>`;
    const dlg = $('#fiche');
    $('#fermer').addEventListener('click', () => dlg.close());
    $('#fiche-contenu').querySelectorAll('[data-autre]').forEach((el) =>
      el.addEventListener('click', () => { if (el.dataset.autre !== b.id) ouvrirFiche(el.dataset.autre); }));
    if (!dlg.open) dlg.showModal();
    dlg.scrollTop = 0;
  }

  // Clic sur une carte ou un titre
  document.addEventListener('click', (e) => {
    const carte = e.target.closest('.livre-carte[data-id], button[data-id]');
    if (carte) ouvrirFiche(carte.dataset.id);
  });

  // Une jaquette qui ne charge pas est remplacée par une tuile (l'événement « error » ne remonte pas : phase de capture)
  document.addEventListener('error', (e) => {
    const img = e.target;
    if (!(img instanceof HTMLImageElement) || !img.dataset.i) return;
    const t = document.createElement('span');
    t.className = 'jaq-vide';
    t.setAttribute('aria-hidden', 'true');
    t.textContent = img.dataset.i;
    img.replaceWith(t);
  }, true);

  /* ---------- Pied de page ---------- */
  function afficherPied() {
    const minus = (t) => t.charAt(0).toLowerCase() + t.slice(1);
    $('#etats-def').innerHTML = ETATS.map((e) =>
      `<strong>${e.k === 'tres_bon' ? '<abbr title="Très bon état">TBE</abbr>' : e.court}</strong> : ${esc(minus(e.def.replace(' TBE signifie « très bon état ».', '')))}`).join('<br>');
    $('#pied-sources').innerHTML = prixAnciens()
      ? `Prix : ancien relevé du site ${SRC}, qui n'est plus mis à jour. Ils indiquent un ordre de grandeur, pas la cote du jour.`
      : `Prix : relevé du site ${SRC} et ventes constatées.`;
    $('#pied-meta').textContent = `${META.nb_versions} éditions · ${META.nb_livres} livres · ${META.nb_series} séries · données du ` +
      new Date(META.genere_le).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) + '.';
  }

  charger();
})();
