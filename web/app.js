(() => {
  'use strict';

  const DONNEES = 'data/';
  const ETATS = [
    { k: 'convenable', court: 'Convenable', long: 'Convenable',
      def: 'Complet et lisible, mais marqué par l\'usage : plis, coins usés, dos passé.' },
    { k: 'bon', court: 'Bon état', long: 'Bon état',
      def: 'Complet, quelques marques du temps : coins légèrement frottés, pages un peu jaunies.' },
    { k: 'tres_bon', court: 'TBE', long: 'Très bon état',
      def: 'Presque comme à la parution : peu ou pas de traces de lecture. TBE signifie « très bon état ».' },
  ];
  const PAR_PAGE = 48;
  // Prix : toujours un chiffre après la virgule ; patrimoine et totaux : aucun (fmtE)
  const eur = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const eurEntier = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
  const fmt = (v) => (v == null ? '—' : eur.format(v));
  const fmtE = (v) => (v == null ? '—' : eurEntier.format(v));
  const fmtN = (x) => (Number.isInteger(x) ? String(x) : x.toLocaleString('fr-FR'));
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const norm = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/œ/g, 'oe').replace(/æ/g, 'ae').replace(/['’]/g, ' ');
  const gv = (c) => (c && c.vendre ? { vendre: true } : {});            // le drapeau « à vendre » survit à tout changement d'état ou d'import
  const etatDe = (k) => ETATS.find((e) => e.k === k) || ETATS[1];
  const racine = (b) => b || null;
  // Rareté : d'après le nombre de tirages Gallimard, sinon les collections saisies sur collection-ldvelh.fr (voir pipeline/rarete.py) ; une information, elle ne modifie aucune cote
  const RARETE = { tres_rare: 'Très rare', rare: 'Rare', peu_courant: 'Peu courant', courant: 'Courant' };
  const pastilleRarete = (b) => (b.rarete && (b.rarete.niveau === 'rare' || b.rarete.niveau === 'tres_rare') ? `<span class="rarete rarete-${b.rarete.niveau}" title="${b.rarete.tirages ? 'Imprimé ' + b.rarete.tirages + ' fois par Gallimard' : 'Possédé par ' + b.rarete.pct + ' % des collections saisies sur collection-ldvelh.fr'}">${RARETE[b.rarete.niveau]}</span>` : '');
  const numero = (b) => (b.numero && !/^0+$/.test(b.numero) ? ` n° ${b.numero}` : '');

  let DATA = [];
  let HIST = null;
  let META = {};
  let VERSIONS = [];
  let limite = PAR_PAGE;
  let S = {};

  const defaut = () => ({
    q: '', serie: '', ed: '', amin: '', amax: '', pmin: '', pmax: '', vente: false, onglet: 'etagere', versions: new Set(VERSIONS),
    h: 'bon', vue: 'etagere', tri: 'serie', g: 'serie', mine: false, cherche: false, avendre: false,
  });

  /* ---------- Chargement ---------- */
  const PAGE = document.body.dataset.page || 'accueil';   // « accueil » ou « collection »

  // Mur de jaquettes : des couvertures du catalogue tirées au hasard à chaque visite (un seul exemplaire par livre), derrière le voile du haut de page
  function murJaquettes(selecteur, n) {
    const zone = $(selecteur);
    if (!zone) return;
    const vues = new Set(), choix = [];
    DATA.filter((b) => b.couverture).sort(() => Math.random() - 0.5).forEach((b) => { if (choix.length < n && !vues.has(b.livre_id)) { vues.add(b.livre_id); choix.push(b); } });
    if (!choix.length) return;
    const mur = document.createElement('div');
    mur.className = 'mur'; mur.setAttribute('aria-hidden', 'true');
    mur.innerHTML = choix.map((b) => `<img src="${esc(racine(b.couverture))}" alt="" width="160" height="240" decoding="async">`).join('');
    zone.classList.add('avec-mur');
    zone.prepend(mur);
  }

  async function charger() {
    try {
      const [v, m, h] = await Promise.all([
        fetch(DONNEES + 'versions.json').then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
        fetch(DONNEES + 'meta.json').then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
        fetch(DONNEES + 'historique.json').then((r) => (r.ok ? r.json() : null)).catch(() => null),      // facultatif : sans lui, pas de flèche
      ]);
      DATA = v; META = m; HIST = h;
    } catch (e) {
      $('#resultats').innerHTML = '<p class="vide-global">Les données n\'ont pas pu être chargées. ' +
        'Ouvrez le guide depuis un serveur (par exemple <code>python -m http.server</code> dans le dossier <code>web</code>).</p>';
      return;
    }
    // Une fois sur six en haut de l'accueil, une fois sur deux sur « Ma collection » : le mur de jaquettes ; sinon l'illustration
    if (document.documentElement.dataset.accueil === '6') murJaquettes('.hero', matchMedia('(max-width: 900px)').matches ? 12 : 30);
    if (Math.random() < 0.5) murJaquettes('.banniere', matchMedia('(max-width: 700px)').matches ? 8 : 18);
    DATA.forEach((b) => { b._txt = norm([b.titre, b.livre, b.auteurs, b.isbn13, b.serie, b.editeur].join(' ')); });
    VERSIONS = [...new Set(DATA.map((b) => b.version))].sort();
    S = defaut();
    chargerColl(); chargerSouh(); COLL_PRET = true; document.dispatchEvent(new Event('cdh-collection-prete'));
    appPrete = true;
    if (PAGE === 'collection') { initPageCollection(); return; }
    construireHero();
    construireControles();
    lireAdresse();
    if (window.Compte && window.Compte.pret()) window.Compte.accueillir();
    synchroniser();
    ouvrirDepuisAdresse();
    basculerSelecteur(!window.matchMedia('(max-width: 1000px)').matches);
    afficher();
    if (new URLSearchParams(location.search).has('inventaire')) {   // lien « Inventaire » des pages annexes
      history.replaceState(null, '', location.pathname + location.hash);
      ouvrirParcours();
    }
  }

  // Du plus récent au plus ancien ; à date égale, le livre ajouté en dernier à la base passe devant (une correction de fiche le même jour ne le déclasse pas).
  // Les petites jaquettes de l'accueil et le tri « Derniers ajouts » (bouton « Voir tous ») utilisent ce même ordre : un livre vu parmi les derniers ajouts est le premier de la liste.
  let RANG = null;                                                    // rang de chaque édition dans la base, calculé une fois les données chargées
  const parRecence = (a, b) => {
    if (!RANG) RANG = new Map(DATA.map((x, i) => [x.id, i]));
    return (b.maj || '').localeCompare(a.maj || '') || (RANG.get(b.id) - RANG.get(a.id));
  };

  /* ---------- En-tête : chiffres et éventail de jaquettes ---------- */
  function construireHero() {
    $('#chiffres-hero').textContent = `${META.nb_versions} éditions · ${META.nb_livres} livres · ${META.nb_series} séries`;
    const aller = () => $('#recherche').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    // Livres annoncés (parution à venir) : de quoi donner envie de les précommander chez un libraire
    const aVenir = DATA.filter((b) => b.parution).sort((x, y) => x.parution.localeCompare(y.parution) || x.titre.localeCompare(y.titre, 'fr')).slice(0, 6);
    if (aVenir.length && $('#ap-liste')) {
      const jourCourt = (iso) => new Date(iso + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
      $('#ap-titre').textContent = `À paraître (${aVenir.length})`;
      $('#ap-liste').innerHTML = aVenir.map((b) => `<li><button type="button" class="bouton-lien" data-id="${esc(b.id)}">${esc(b.titre)}</button><span class="sous"> · ${esc(b.serie)} · ${esc(jourCourt(b.parution))}</span></li>`).join('');
      $('#ap-liste').addEventListener('click', (e) => { const x = e.target.closest('[data-id]'); if (x) ouvrirFiche(x.dataset.id); });
      $('#hero-aparaitre').hidden = false;
    }
    // Derniers livres ajoutés à la base : petites couvertures cliquables, et accès au tri « Derniers ajouts »
    const dates = DATA.map((b) => b.maj).filter(Boolean).sort();
    if (dates.length && dates[0] !== dates[dates.length - 1]) {
      const vus = new Set();
      const recents = DATA.filter((b) => b.maj && !b.parution).sort(parRecence).filter((b) => (vus.has(b.livre_id) ? false : vus.add(b.livre_id))).slice(0, 8);      // une couverture par livre
      if (recents.length) {
        $('#hero-ajouts-liste').innerHTML = recents.map((b) => `<button type="button" class="ajout-mini" data-id="${esc(b.id)}" title="${esc(b.titre)} · ${esc(b.serie)}" aria-label="${esc(b.titre)}, ${esc(b.serie)}">${b.couverture ? `<img src="${esc(b.couverture)}" alt="" loading="lazy" width="80" height="120">` : `<span class="ajout-vide" aria-hidden="true">${esc((b.serie && b.serie !== 'Non classée' ? b.serie : b.titre || '?').trim().charAt(0).toUpperCase())}</span>`}</button>`).join('');
        $('#hero-ajouts-liste').addEventListener('click', (e) => { const x = e.target.closest('[data-id]'); if (x) ouvrirFiche(x.dataset.id); });
        $('#hero-ajouts-tous').addEventListener('click', () => { S.tri = 'recent'; S.onglet = 'etagere'; synchroniser(); changer(); aller(); });
        $('#hero-ajouts').hidden = false;
      }
    }
    // La croix du champ (ou l'effacement du texte) retire aussitôt le filtre : l'étagère n'attend pas un nouveau clic sur « Chercher »
    $('#h-q').addEventListener('input', (e) => { if (!e.target.value && S.q) { S.q = ''; synchroniser(); changer(); } });
    $('#hero-recherche').addEventListener('submit', (e) => {
      e.preventDefault();
      S.q = $('#h-q').value.trim(); S.onglet = 'etagere';
      synchroniser(); changer();
      const r = $('#resultats');                                         // on descend jusqu'aux titres trouvés, pas seulement jusqu'au bloc des filtres
      (r || $('#recherche')).scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    });
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

  // Quand on choisit une série (pastille, groupe) qui n'est pas de l'éditeur déjà choisi, l'éditeur est retiré
  function accorderEditeur() {
    if (S.ed && S.serie && !DATA.some((b) => b.serie === S.serie && (b.editeur || 'Non renseigné') === S.ed)) S.ed = '';
  }

  // Les séries proposées sont celles de l'éditeur choisi (toutes si aucun éditeur) ; la série choisie reste si elle en fait partie
  function remplirSeries() {
    const m = new Map();
    DATA.forEach((b) => { if (!S.ed || (b.editeur || 'Non renseigné') === S.ed) m.set(b.serie, (m.get(b.serie) || 0) + 1); });
    if (S.serie && !m.has(S.serie)) S.serie = '';
    $('#f-serie').innerHTML = '<option value="">Toutes les séries</option>' +
      [...m].sort((a, b) => a[0].localeCompare(b[0], 'fr')).map(([k, n]) => `<option value="${esc(k)}">${esc(k)} (${n})</option>`).join('');
    $('#f-serie').value = S.serie;
  }

  function construireControles() {
    remplirSeries();
    $('#f-ed').innerHTML = '<option value="">Tous les éditeurs</option>' +
      [...compter('editeur', 'Non renseigné')].sort((a, b) => b[1] - a[1])
        .map(([k, n]) => `<option value="${esc(k)}">${esc(k)} (${n})</option>`).join('');
    const annees = [...new Set(DATA.map((b) => b.annee).filter(Boolean))].sort((a, b) => a - b);
    const opt = (v) => `<option value="${v}">${v}</option>`;
    $('#f-amin').innerHTML = '<option value="">Début</option>' + annees.map(opt).join('');
    $('#f-amax').innerHTML = '<option value="">Fin</option>' + annees.map(opt).join('');

    const nb = compter('version');
    $('#f-versions').innerHTML = '<option value="">Toutes les éditions</option>' +
      VERSIONS.map((v) => `<option value="${esc(v)}">Édition ${esc(v)} (${nb.get(v)})</option>`).join('') +
      '<option value="multi" hidden disabled>Plusieurs éditions</option>';

    $('#h-etats').innerHTML = ETATS.map((e) =>
      `<label><input type="radio" name="h-etat" value="${e.k}"><span>${e.court}</span></label>`).join('');

    $('#f-q').addEventListener('input', (e) => { S.q = e.target.value; changer(); });
    $('#f-serie').addEventListener('change', (e) => { S.serie = e.target.value; changer(); });
    $('#f-ed').addEventListener('change', (e) => { S.ed = e.target.value; remplirSeries(); changer(); });
    $('#f-amin').addEventListener('change', (e) => { S.amin = e.target.value; changer(); });
    $('#f-amax').addEventListener('change', (e) => { S.amax = e.target.value; changer(); });
    $('#f-pmin').addEventListener('input', (e) => { S.pmin = e.target.value; changer(); });
    $('#f-pmax').addEventListener('input', (e) => { S.pmax = e.target.value; changer(); });
    $('#f-vente').addEventListener('change', (e) => { S.vente = e.target.checked; changer(); });
    $('#f-mine').addEventListener('change', (e) => { S.mine = e.target.checked; if (S.mine) { S.cherche = false; S.avendre = false; } synchroniser(); changer(); });
    document.querySelectorAll('#f-coll input').forEach((r) => r.addEventListener('change', (e) => { if (e.target.checked) { S.mine = e.target.value === 'mine'; S.cherche = e.target.value === 'cherche'; S.avendre = e.target.value === 'vendre'; synchroniser(); changer(); } }));
    brancherParcours();
    $('#f-versions').addEventListener('change', (e) => {
      S.versions = new Set(e.target.value ? [e.target.value] : VERSIONS);
      changer();
    });
    $('#h-etats').addEventListener('change', (e) => { S.h = e.target.value; $('#prix-etat').textContent = `en ${etatDe(S.h).long.toLowerCase()}`; ecrireAdresse(); afficher(); });
    $('#f-vue').addEventListener('change', (e) => { S.vue = e.target.value; changer(); });
    $('#f-tri').addEventListener('change', (e) => { S.tri = e.target.value; changer(); });
    $('#f-groupe').addEventListener('change', (e) => { S.g = e.target.value; changer(); });
    brancherHisto();
    brancherOnglets();
    $('#reinit').addEventListener('click', () => { const { h, vue, tri, g, onglet } = S; S = { ...defaut(), h, vue, tri, g, onglet }; synchroniser(); changer(); });
    $('#bascule').addEventListener('click', () => basculerSelecteur());
    $('#fiche').addEventListener('click', (e) => { if (e.target === $('#fiche')) $('#fiche').close(); });
    $('#fiche').addEventListener('close', () => { inviterApresFiches(); const id = RETOUR_FICHE; RETOUR_FICHE = ''; if (!id) return; setTimeout(() => { const el = document.querySelector(`[data-id="${id.replace(/"/g, '')}"]`); if (el) el.focus({ preventScroll: true }); }, 0); });
    window.addEventListener('hashchange', () => {
      const h = location.hash.slice(1);
      if (h && !h.includes('=')) return;      // simple ancre de section (#cote, #apropos…) : les filtres restent
      lireAdresse(); synchroniser(); afficher();
    });
    let attente;
    window.addEventListener('resize', () => { clearTimeout(attente); attente = setTimeout(afficher, 150); });
  }

  function synchroniser() {
    $('#f-q').value = S.q; if ($('#h-q')) $('#h-q').value = S.q; $('#f-ed').value = S.ed; remplirSeries();
    $('#f-amin').value = S.amin; $('#f-amax').value = S.amax; $('#f-pmin').value = S.pmin; $('#f-pmax').value = S.pmax;
    $('#prix-etat').textContent = `en ${etatDe(S.h).long.toLowerCase()}`;
    $('#f-vente').checked = S.vente; $('#f-mine').checked = S.mine;
    document.querySelectorAll('#f-coll input').forEach((r) => { r.checked = r.value === (S.avendre ? 'vendre' : S.cherche ? 'cherche' : S.mine ? 'mine' : 'tous'); });
    $('#f-tri').value = S.tri; $('#f-groupe').value = S.g;
    $('#f-versions').value = S.versions.size === VERSIONS.length ? '' : S.versions.size === 1 ? [...S.versions][0] : 'multi';
    document.querySelectorAll('#h-etats input').forEach((i) => { i.checked = i.value === S.h; });
    document.querySelectorAll('#f-vue input').forEach((i) => { i.checked = i.value === S.vue; });
  }

  function changer() { limite = PAR_PAGE; ecrireAdresse(); afficher(); }
  // Les notes des livres arrivent après le premier affichage (et changent quand quelqu'un note) : l'étagère se redessine
  let minuteNotes = null;
  document.addEventListener('cdh-notes', () => { clearTimeout(minuteNotes); minuteNotes = setTimeout(() => { if (PAGE !== 'collection') afficher(); }, 200); });

  function nbFiltres() {
    return [S.q.trim(), S.serie, S.ed, S.amin || S.amax, S.pmin !== '' || S.pmax !== '', S.vente, S.mine, S.cherche, S.avendre, S.versions.size !== VERSIONS.length].filter(Boolean).length;
  }
  function resumeFiltres() {
    const t = [];
    if (S.q.trim()) t.push(`« ${S.q.trim()} »`);
    if (S.serie) t.push(S.serie);
    if (S.ed) t.push(S.ed);
    if (S.amin || S.amax) t.push(S.amin && S.amax ? (S.amin === S.amax ? S.amin : `${S.amin}–${S.amax}`) : (S.amin ? `depuis ${S.amin}` : `jusqu'en ${S.amax}`));
    if (S.pmin !== '' || S.pmax !== '') t.push(libTranche(S.pmin, S.pmax));
    if (S.versions.size !== VERSIONS.length) t.push([...S.versions].sort().join(', ') || 'aucune édition');
    if (S.vente) t.push('encore en vente');
    if (S.mine) t.push('ma collection');
    if (S.cherche) t.push('à trouver');
    if (S.avendre) t.push('à vendre');
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
    if (S.pmin !== '') p.set('pmin', S.pmin);
    if (S.pmax !== '') p.set('pmax', S.pmax);
    if (S.vente) p.set('vente', '1');
    if (S.mine) p.set('mine', '1');
    if (S.cherche) p.set('cherche', '1');
    if (S.avendre) p.set('avendre', '1');
    if (S.versions.size !== d.versions.size) p.set('v', [...S.versions].join(','));
    if (S.h !== 'bon') p.set('h', S.h);
    if (S.vue !== 'etagere') p.set('vue', S.vue);
    if (S.tri !== 'serie') p.set('tri', S.tri);
    if (S.g !== 'serie') p.set('g', S.g);
    if (S.onglet !== 'etagere') p.set('onglet', S.onglet);
    const h = p.toString();
    history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
  }
  let FICHE_URL = '', CORR_URL = false;     // « #fiche=<id>&corriger=1 » : ouvre la fiche (et son bloc « Corriger la fiche » pour un administrateur)
  function lireAdresse() {
    const p = new URLSearchParams(location.hash.slice(1));
    FICHE_URL = p.get('fiche') || ''; CORR_URL = p.get('corriger') === '1';
    S = defaut();
    S.q = p.get('q') || ''; S.serie = p.get('serie') || ''; S.ed = p.get('ed') || '';
    S.amin = p.get('amin') || ''; S.amax = p.get('amax') || ''; S.pmin = p.get('pmin') || ''; S.pmax = p.get('pmax') || ''; S.vente = p.get('vente') === '1'; S.mine = p.get('mine') === '1'; S.cherche = p.get('cherche') === '1'; S.avendre = p.get('avendre') === '1';
    if (p.has('v')) S.versions = new Set(p.get('v').split(',').filter((v) => VERSIONS.includes(v)));
    if (ETATS.some((e) => e.k === p.get('h'))) S.h = p.get('h');
    if (['etagere', 'liste', 'groupe'].includes(p.get('vue'))) S.vue = p.get('vue');
    if (['serie', 'recent', 'titre', 'annee', 'cher', 'pascher'].includes(p.get('tri'))) S.tri = p.get('tri');
    if (['serie', 'version', 'annee', 'decennie', 'editeur'].includes(p.get('g'))) S.g = p.get('g');
    if (['cote', 'etagere'].includes(p.get('onglet'))) S.onglet = p.get('onglet');
  }

  /* ---------- Calculs ---------- */
  const libTranche = (mini, maxi) => (mini !== '' && maxi !== '' ? `${fmtN(+mini)} à ${fmtN(+maxi)} €` : (mini !== '' ? `à partir de ${fmtN(+mini)} €` : `moins de ${fmtN(+maxi)} €`));
  function filtrer(avecPrix = true) {
    const q = norm(S.q.trim());
    const k = etatDe(S.h).k;
    const pmin = avecPrix && S.pmin !== '' && !cotesMasquees() ? +S.pmin : null;
    const pmax = avecPrix && S.pmax !== '' && !cotesMasquees() ? +S.pmax : null;
    const amin = S.amin ? +S.amin : null;
    const amax = S.amax ? +S.amax : null;
    return DATA.filter((b) =>
      (!q || b._txt.includes(q)) && (!S.serie || b.serie === S.serie) && S.versions.has(b.version) &&
      (!S.ed || (b.editeur || 'Non renseigné') === S.ed) &&
      (amin === null || (b.annee && b.annee >= amin)) && (amax === null || (b.annee && b.annee <= amax)) &&
      (!S.vente || b.en_vente === 1) && (!S.mine || COLL[b.id]) && (!S.cherche || (SOUH[b.id] && !COLL[b.id])) && (!S.avendre || (COLL[b.id] && COLL[b.id].vendre)) &&
      ((pmin === null && pmax === null) || (b.prix[k] != null && (pmin === null || b.prix[k] >= pmin) && (pmax === null || b.prix[k] < pmax))));
  }
  function stat(liste, k) {
    const v = liste.map((b) => b.prix[k]).filter((x) => x != null).sort((a, b) => a - b);
    if (!v.length) return { n: 0 };
    const somme = v.reduce((a, b) => a + b, 0);
    const m = v.length % 2 ? v[(v.length - 1) / 2] : (v[v.length / 2 - 1] + v[v.length / 2]) / 2;
    return { n: v.length, avg: somme / v.length, min: v[0], max: v[v.length - 1], med: m };
  }
  /* Nature des prix : « archives » (ancien relevé) ou prix actuels (annonces, ventes) pour une partie des éditions */
  const nbActuels = () => META.nb_prix_actuels || 0;
  const prixAnciens = () => nbActuels() === 0;
  const infoPrix = (b, k) => (b.prix_info && b.prix_info[k]) || null;
  const estActuel = (i) => !!i && i.source !== 'archives';
  const NATURES = { annonces: 'annonce', ventes: 'vente', rachats: 'rachat' };
  const dateCourte = (iso) => new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
  function legendePrix(b, k) {
    const i = infoPrix(b, k);
    if (b.prix[k] == null) return '';
    const aligne = i && i.ajuste ? ' Alignée sur l\'état inférieur : un état supérieur ne vaut jamais moins qu\'un état inférieur.' : '';
    if (i && i.neuf) return `Édition encore en vente neuve : un exemplaire en très bon état est coté au prix du neuf, le prix éditeur. Les autres états en sont déduits (bon état ≈ 60 %, convenable ≈ 40 %).`;
    if (i && i.valide) return `Prix validé par le guide le ${dateCourte(i.date)}${i.decision === 'corrige' ? ' (corrigé à la main)' : ' (confirmé)'} : il prime sur les annonces et les archives.`;
    if (i && i.repartition) return `Prix réparti entre les trois états d'après les annonces actuelles de cette édition (convenable ≈ 40 %, bon état ≈ 60 % du très bon état), ${i.nb} annonce${i.nb > 1 ? 's' : ''} relevée${i.nb > 1 ? 's' : ''} au ${dateCourte(i.date)} · confiance ${i.confiance}. Prix demandés, souvent supérieurs aux prix réellement payés.${aligne}`;
    if (i && i.deduit) return `Prix estimé d'après les autres états de cette édition (convenable ≈ 40 %, bon état ≈ 60 % du très bon état) : une estimation, pas un relevé.${aligne}`;
    if (i && i.recalibre) return `Cote d'archives remise à niveau : le modèle a appris l'écart entre les archives et les annonces actuelles. C'est une estimation, pas un relevé.${aligne}`;
    if (!estActuel(i)) return `Cote d'archives (ancien relevé) : un ordre de grandeur.${aligne}`;
    const mot = NATURES[i.nature] || 'observation';
    const base = `${i.nb} ${mot}${i.nb > 1 ? 's' : ''} relevée${i.nb > 1 ? 's' : ''} au ${dateCourte(i.date)}`;
    const reserve = i.nature === 'annonces' ? ' Prix demandés, souvent supérieurs aux prix réellement payés.' : '';
    return `${base} · confiance ${i.confiance}.${reserve}${aligne}`;
  }
  // Prix éditeur des éditions encore en vente (fiche du livre chez Gallimard Jeunesse) ou, à défaut, prix à la parution (notice BnF)
  function blocNeuf(b) {
    const e = b.prix_editeur;
    if (!e) return '';
    if (e.source === 'editeur') return `<p class="sous prix-neuf">Prix du neuf : <strong>${fmt(e.prix)}</strong> (prix éditeur en librairie, relevé au ${dateCourte(e.date)})${e.parution ? `. À la parution : ${fmt(e.parution)} (notice de la BnF)` : ''}.</p>`;
    return `<p class="sous prix-neuf">Prix éditeur à la parution : <strong>${e.devise === 'EUR' ? fmt(e.prix) : String(e.prix).replace('.', ',') + ' F'}</strong> (notice de la BnF).</p>`;
  }
  function texteEstimation() {          // texte fixe : il ne dépend ni de la collection ni de l'état des relevés
    return "Estimation indicative d'après les cotes du guide.";
  }

  /* ---------- Affichage général ---------- */
  // Onglets « Cote de la sélection » / « Sur l'étagère » : un seul panneau à la fois, sans défilement
  // Après la cinquième fiche consultée (une fois par visite, au plus une fois par mois), à la fermeture de la fiche : une invitation fermable à se connecter
  function inviterApresFiches() {
    if (!sansCompte() || !window.Compte) return;
    try {
      const vus = JSON.parse(sessionStorage.getItem('cdh-fiches-vues') || '[]');
      if (vus.length < 5 || sessionStorage.getItem('cdh-invite-vue')) return;
      if (Date.now() - (+localStorage.getItem('cdh-invite-fiches') || 0) < 30 * 86400000) return;
      sessionStorage.setItem('cdh-invite-vue', '1'); localStorage.setItem('cdh-invite-fiches', String(Date.now()));
      setTimeout(() => window.Compte.inviter(), 400);
    } catch (e) { /* stockage indisponible : pas d'invitation */ }
  }
  function appliquerOnglet() {
    ['cote', 'etagere'].forEach((n) => {
      const on = S.onglet === n;
      $('#' + n).hidden = !on;
      $('#onglet-' + n).setAttribute('aria-selected', String(on));
      $('#onglet-' + n).tabIndex = on ? 0 : -1;
    });
  }
  function choisirOnglet(n, focus) {
    if (S.onglet === n) return;
    S.onglet = n; ecrireAdresse(); afficher();
    if (focus) $('#onglet-' + n).focus();
  }
  function brancherOnglets() {
    const ordre = ['etagere', 'cote'];
    ordre.forEach((n) => $('#onglet-' + n).addEventListener('click', () => choisirOnglet(n)));
    $('.onglets-vue').addEventListener('keydown', (e) => {
      const i = ordre.indexOf(S.onglet);
      const cible = { ArrowRight: ordre[(i + 1) % 2], ArrowLeft: ordre[(i + 1) % 2], Home: ordre[0], End: ordre[1] }[e.key];
      if (cible) { e.preventDefault(); choisirOnglet(cible, true); }
    });
  }

  function afficher() {
    if (PAGE === 'collection') { afficherCollection(); return; }
    appliquerMasqueCotes();
    if ($('#legende-niveaux')) { $('#legende-niveaux').hidden = !cotesMasquees() || S.vue === 'groupe'; $('#legende-niveaux').innerHTML = `<span class="niveaux">${LEGENDE_NIVEAUX}</span>Les prix estimés sont réservés aux comptes connectés.`; }
    appliquerOnglet();
    const liste = filtrer();
    const nf = nbFiltres();
    $('#nb-filtres').textContent = nf ? String(nf) : '';
    $('#reinit').hidden = !nf;
    if ($('#aide-cartes')) $('#aide-cartes').hidden = S.vue !== 'etagere' || (!cotesMasquees() && Object.keys(COLL).length > 0);      // l'aide disparaît dès le premier livre ajouté
    $('#nb-filtres').setAttribute('aria-label', nf ? `${nf} filtre${nf > 1 ? 's' : ''} actif${nf > 1 ? 's' : ''}` : '');
    majResume();
    $('#compte').textContent = `${liste.length} livre${liste.length > 1 ? 's' : ''} sur ${DATA.length}`;
    $('#nb-onglet').textContent = String(liste.length);
    afficherCote(liste);
    afficherHisto();
    afficherCollection();
    $('#bloc-tri').hidden = S.vue === 'groupe';
    $('#bloc-groupe').hidden = S.vue !== 'groupe';
    if (!liste.length) {
      $('#resultats').innerHTML = '<p class="vide-global">Aucun livre ne répond à ces critères. Élargissez la sélection ou effacez un filtre.' + (window.Relais && window.Relais.configure() ? ' Un livre manque au guide ? <button type="button" class="bouton-lien" data-demande>Demandez son ajout</button>.' : '') + '</p>';
    } else if (S.vue === 'etagere') {
      afficherEtagere(liste);
    } else if (S.vue === 'liste') {
      afficherListe(liste);
    } else {
      afficherGroupes(liste);
    }
    if (S.mine && !liste.length && !Object.keys(COLL).length) {
      $('#resultats').innerHTML = '<p class="vide-global">Votre collection est vide. Touchez C, BE ou TBE sous une jaquette pour y ajouter un livre.</p>';
    }
    if (S.cherche && !liste.length) {
      $('#resultats').innerHTML = '<p class="vide-global">Aucun livre à trouver. Sur une fiche, appuyez sur « À trouver » pour l\'ajouter ici.</p>';
    }
    if (S.avendre && !liste.length) {
      $('#resultats').innerHTML = '<p class="vide-global">Aucun livre à vendre. Dans « Ma collection », touchez « À vendre » sous un exemplaire pour le placer ici.</p>';
    }
    afficherPied();
  }

  /* ---------- Cote : sceau et chiffres ---------- */
  function appliquerMasqueCotes() {
    const m = cotesMasquees();
    document.body.classList.toggle('cotes-masquees', m);
    if (!m) return;
    if (S.onglet === 'cote') S.onglet = 'etagere';
    S.mine = false; S.cherche = false; S.avendre = false;               // filtres de collection : réservés aux comptes
  }
  function afficherCote(liste) {
    if (cotesMasquees()) { ['#sceau', '#stats', '#trois'].forEach((q) => { const n = $(q); if (n) n.innerHTML = ''; }); return; }
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

  /* Histogramme générique : zone, légende, note et tableau sont des éléments ; `valeurs` les prix à répartir.
     Avec `choix`, chaque tranche est un bouton qui renvoie sa borne (mini, maxi) : maxi = null pour « à partir de ». */
  function histogramme({ zone, legende, note, table, valeurs, etat, nom, choix, sel, vide }) {
    zone.classList.toggle('interactif', !!choix);
    const au = (n) => `${n} ${n > 1 ? nom.p : nom.s}`;
    if (!valeurs.length) {
      zone.innerHTML = `<p class="vide-histo">${vide}</p>`;
      legende.innerHTML = ''; table.innerHTML = ''; note.textContent = '';
      return false;
    }
    const tri = [...valeurs].sort((a, b) => a - b);
    const n = tri.length;
    const moy = tri.reduce((a, b) => a + b, 0) / n;
    const med = n % 2 ? tri[(n - 1) / 2] : (tri[n / 2 - 1] + tri[n / 2]) / 2;
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
    const y = (c) => m.h + ph - (c / ymax) * ph;
    const xPrix = (v) => (v < t.limite ? m.g + (v / t.limite) * (t.nb * bw) : m.g + t.nb * bw + bw / 2);
    const borne = (i) => (avecPlus && i === t.nb ? { mini: t.limite, maxi: null } : { mini: i * t.largeur, maxi: (i + 1) * t.largeur });
    const choisie = (b) => !!sel && sel.mini !== '' && +sel.mini === b.mini && ((b.maxi === null && sel.maxi === '') || (b.maxi !== null && sel.maxi !== '' && +sel.maxi === b.maxi));

    let svg = '', nombres = '', zones = '';
    for (let g = 0; g <= ymax; g += pas) {
      svg += `<line class="${g === 0 ? 'h-axe' : 'h-grille'}" x1="${m.g}" x2="${W - m.d}" y1="${y(g)}" y2="${y(g)}"/>` +
             `<text class="h-txt" x="${m.g - 6}" y="${y(g) + 4}" text-anchor="end">${g}</text>`;
    }
    toutes.forEach((c, i) => {
      const b = borne(i), plus = b.maxi === null;
      const lib = plus ? `à partir de ${fmtN(b.mini)} €` : `de ${fmtN(b.mini)} à ${fmtN(b.maxi)} €`;
      const x = m.g + i * bw + 1.5;
      const on = choisie(b);
      svg += `<rect class="${plus ? 'h-bar-plus' : 'h-bar'}${on ? ' h-choisie' : ''}" x="${x}" y="${y(c)}" width="${Math.max(1, bw - 3)}" height="${(c / ymax) * ph}" rx="2">` +
             `<title>${lib} : ${au(c)}</title></rect>`;
      if (c > 0 && bw >= 17) nombres += `<text class="h-n" x="${x + (bw - 3) / 2}" y="${y(c) - 4}" text-anchor="middle">${c}</text>`;
      if (choix) {
        zones += `<rect class="h-clic" tabindex="0" role="button" aria-pressed="${on}" data-mini="${b.mini}" data-maxi="${b.maxi === null ? '' : b.maxi}" ` +
                 `aria-label="${on ? 'Retirer le filtre' : 'Ne garder que'} ${lib} : ${au(c)}" x="${m.g + i * bw}" y="${m.h}" width="${bw}" height="${ph}"/>`;
      }
    });
    const pasEt = Math.max(1, Math.ceil(36 / bw));
    for (let i = 0; i <= t.nb; i += pasEt) {
      svg += `<text class="h-txt" x="${m.g + i * bw}" y="${H - 10}" text-anchor="${i === 0 ? 'start' : 'middle'}">${fmtN(i * t.largeur)}${i === 0 ? ' €' : ''}</text>`;
    }
    if (avecPlus) svg += `<text class="h-txt" x="${m.g + t.nb * bw + bw / 2}" y="${H - 10}" text-anchor="middle">+</text>`;
    svg += `<line class="h-med" x1="${xPrix(med)}" x2="${xPrix(med)}" y1="${m.h - 6}" y2="${m.h + ph}"/>`;
    svg += `<line class="h-moy" x1="${xPrix(moy)}" x2="${xPrix(moy)}" y1="${m.h - 6}" y2="${m.h + ph}"/>`;
    svg += nombres + zones;
    zone.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="${choix ? 'group' : 'img'}" ` +
      `aria-label="Histogramme des prix en ${esc(etat)} : ${au(n)}, médiane ${fmt(med)}, moyenne ${fmt(moy)}">${svg}</svg>`;
    note.textContent =
      `Chaque barre compte les ${nom.p} dont le prix tombe dans la tranche (${fmtN(t.largeur)} € de large). ` +
      `${au(n)} chiffré${n > 1 ? 's' : ''}` +
      `${avecPlus ? `, dont ${t.plus} à partir de ${fmtN(t.limite)} € regroupés dans la dernière barre` : ''}.` +
      (choix ? ' Touchez une barre pour ne garder que les livres de cette tranche.' : '');
    legende.innerHTML =
      `<span class="leg"><i class="trait med"></i>Médiane ${fmt(med)}</span><span class="leg"><i class="trait"></i>Moyenne ${fmt(moy)}</span>` +
      (moy >= t.limite ? '<span class="leg sous">La moyenne dépasse la dernière tranche affichée.</span>' : '') +
      (choix && sel && (sel.mini !== '' || sel.maxi !== '')
        ? `<span class="leg filtre-actif">Tranche gardée : <b>${libTranche(sel.mini, sel.maxi)}</b> <button type="button" class="bouton-lien" data-effacer-prix>Retirer</button></span>` : '');
    table.innerHTML = `<table><thead><tr><th>Tranche de prix</th><th class="num">${nom.p.charAt(0).toUpperCase() + nom.p.slice(1)}</th><th class="num">Part</th></tr></thead><tbody>` +
      toutes.map((c, i) => {
        const b = borne(i);
        return `<tr><td>${b.maxi === null ? `À partir de ${fmtN(b.mini)} €` : `${fmtN(b.mini)} à ${fmtN(b.maxi)} €`}</td><td class="num">${c}</td><td class="num">${Math.round((c / n) * 100)} %</td></tr>`;
      }).join('') + '</tbody></table>';
    return true;
  }

  function afficherHisto() {
    if (cotesMasquees()) { ['#histo', '#histo-legende', '#histo-table'].forEach((q) => { const n = $(q); if (n) n.innerHTML = ''; }); return; }
    const e = etatDe(S.h);
    const valeurs = filtrer(false).map((b) => b.prix[e.k]).filter((x) => x != null);   // sans la tranche : toutes les barres restent
    $('#titre-histo').textContent = `Où se situent les prix · ${e.long.toLowerCase()}`;
    const ok = histogramme({ zone: $('#histo'), legende: $('#histo-legende'), note: $('#histo-note'), table: $('#histo-table'),
      valeurs, etat: e.long.toLowerCase(), nom: { s: 'livre', p: 'livres' }, choix: true, sel: { mini: S.pmin, maxi: S.pmax }, vide: 'Aucun prix pour cette sélection.' });
    $('#histo-chiffres').hidden = !ok;
  }
  function brancherHisto() {
    const zone = $('#histo');
    const choisir = (el) => {
      const mini = el.dataset.mini, maxi = el.dataset.maxi;
      const dejà = S.pmin === mini && S.pmax === maxi;
      S.pmin = dejà ? '' : mini; S.pmax = dejà ? '' : maxi;
      synchroniser(); changer();
      annonce(dejà ? 'Filtre de prix retiré.' : `Tranche gardée : ${libTranche(S.pmin, S.pmax)}.`);
    };
    zone.addEventListener('click', (e) => { const el = e.target.closest('.h-clic'); if (el) choisir(el); });
    zone.addEventListener('keydown', (e) => { if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('h-clic')) { e.preventDefault(); choisir(e.target); } });
    $('#histo-legende').addEventListener('click', (e) => {
      if (e.target.closest('[data-effacer-prix]')) { S.pmin = ''; S.pmax = ''; synchroniser(); changer(); annonce('Filtre de prix retiré.'); }
    });
  }

  /* ---------- Étagère (jaquettes) ---------- */
  const tuile = (b, cls = 'jaq-vide') => `<span class="${cls}" aria-hidden="true">${esc((b.serie || '?').trim().charAt(0).toUpperCase())}</span>`;

  function trier(liste) {
    const num = (b) => parseInt(b.numero, 10) || 0;
    const k = etatDe(S.h).k;
    const parSerie = (a, b) => a.serie.localeCompare(b.serie, 'fr') || num(a) - num(b) || a.version_n - b.version_n;
    // Un visiteur ne voit que le niveau (€ à €€€€€) : il est trié sur ce niveau, puis par série, sans révéler l'ordre exact des prix
    const valeur = (b) => (b.prix[k] == null ? null : cotesMasquees() ? niveauCote(b.prix[k], k) : b.prix[k]);
    const cmp = {
      serie: parSerie,
      titre: (a, b) => a.titre.localeCompare(b.titre, 'fr') || a.version_n - b.version_n,
      recent: (a, b) => parRecence(a, b) || a.serie.localeCompare(b.serie, 'fr') || num(a) - num(b) || a.version_n - b.version_n,
      annee: (a, b) => (a.annee || 9999) - (b.annee || 9999) || a.titre.localeCompare(b.titre, 'fr'),
      cher: (a, b) => (valeur(b) ?? -1) - (valeur(a) ?? -1) || parSerie(a, b),
      pascher: (a, b) => (valeur(a) ?? 1e9) - (valeur(b) ?? 1e9) || parSerie(a, b),
    }[S.tri] || (() => 0);
    return [...liste].sort(cmp);
  }

  function afficherEtagere(liste) {
    const e = etatDe(S.h);
    const tri = trier(liste);
    const vus = tri.slice(0, limite);
    const cartes = vus.map((b) => {
      const p = b.prix[e.k];
      const masq = cotesMasquees(), poss = masq ? null : COLL[b.id], souh = masq ? null : SOUH[b.id];
      return `<article class="livre-carte${poss ? ' possede-oui' : ''}${poss && poss.vendre ? ' vendre-oui' : ''}${!poss && souh ? ' trouver-oui' : ''}">
        <button type="button" class="ouvrir" data-id="${esc(b.id)}" aria-label="${esc(b.titre)}, édition ${esc(b.version)}${p != null ? ', ' + (cotesMasquees() ? 'niveau de prix ' + niveauCote(p, e.k) + ' sur 5' : fmt(p)) + ' en ' + e.long.toLowerCase() : ''}${poss ? ', dans ma collection en ' + etatDe(poss.etat).long.toLowerCase() : ''}">
          <span class="couv">${b.couverture
            ? `<img src="${esc(racine(b.couverture))}" alt="" width="88" height="124" loading="lazy" decoding="async" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">`
            : tuile(b)}</span>
          <span class="infos"><span class="titre">${esc(b.titre)}</span><span class="meta" style="display:block">${esc(b.serie)}${esc(numero(b))}<span class="ed"><b class="bv">${esc(b.version)}</b>${b.annee ? esc(String(b.annee)) : ''}</span></span></span>
        </button>
        ${window.Notes ? window.Notes.pastille(b.livre_id) : ''}
        <div class="etats-carte" role="group" aria-label="Ajouter à ma collection : ${esc(b.titre)}, édition ${esc(b.version)}">${ETATS.map((x) =>
          `<button type="button" data-etat-possede="${esc(b.id)}" data-e="${x.k}" aria-pressed="${!!poss && poss.etat === x.k}" title="${poss && poss.etat === x.k ? 'Dans ma collection en ' + x.long.toLowerCase() + ' : retirer' : 'Ajouter en ' + x.long.toLowerCase()}" aria-label="${poss && poss.etat === x.k ? 'Retirer de ma collection' : 'Ajouter en ' + x.long.toLowerCase()} : ${esc(b.titre)}, édition ${esc(b.version)}">${ABREGE[x.k]}</button>`).join('')}</div>${poss ? `<button type="button" class="souhait-carte" data-vendre-carte="${esc(b.id)}" aria-pressed="${!!poss.vendre}" title="${poss.vendre ? 'Dans ma liste à vendre : retirer' : 'Mettre à vendre'}" aria-label="${poss.vendre ? 'Retirer de ma liste à vendre' : 'Mettre à vendre'} : ${esc(b.titre)}, édition ${esc(b.version)}"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" aria-hidden="true"><circle cx="10" cy="12" r="7"/><path d="M10 12h12M19 9l3 3-3 3"/></svg><span class="souhait-txt">À vendre</span></button>` : `<button type="button" class="souhait-carte" data-souhait-carte="${esc(b.id)}" aria-pressed="${!poss && !!souh}"${poss ? ' disabled' : ''} title="${poss ? 'Déjà dans ma collection' : souh ? 'Dans ma liste à trouver : retirer' : 'Ajouter à ma liste à trouver'}" aria-label="${poss ? 'Déjà dans ma collection' : souh ? 'Retirer de ma liste à trouver' : 'Ajouter à ma liste à trouver'} : ${esc(b.titre)}, édition ${esc(b.version)}"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" aria-hidden="true"><circle cx="14" cy="12" r="7"/><path d="M2 12h9M8 9l3 3-3 3"/></svg><span class="souhait-txt">À trouver</span></button>`}
        <span class="prix${p == null ? ' nul' : ''}">${p == null ? 'Cote indisponible' : coteTxt(p, e.k, true)}${p == null ? '' : `<small>${e.k === 'tres_bon' ? 'TBE' : esc(e.court.toLowerCase())}</small>`}</span>
      </article>`;
    }).join('');
    const reste = tri.length - vus.length;
    $('#resultats').innerHTML = `<div class="rayon">${cartes}</div>` +
      (reste > 0 ? `<button type="button" class="plus" id="plus">Voir ${Math.min(reste, PAR_PAGE)} livres de plus (${reste} restants)</button>` : '');
    const plus = $('#plus');
    if (plus) plus.addEventListener('click', () => { limite += PAR_PAGE; afficherEtagere(liste); });
  }

  /* ---------- Liste ---------- */
  function cellulesPrix(b) {
    return ETATS.map((e) => `<td class="num" data-label="${e.court}"><span class="prix-c${b.prix[e.k] == null ? ' nul' : ''}">${coteTxt(b.prix[e.k], e.k, true)}</span></td>`).join('');
  }
  function afficherListe(liste) {
    const tri = trier(liste);
    const vus = tri.slice(0, limite);
    const avecNotes = !!window.Notes && window.Notes.disponible();      // colonne Note seulement quand les notes sont en service
    const lignes = vus.map((b) => `
      <tr class="cliquable" data-id="${esc(b.id)}">
        <td class="principal"><div class="l-livre">${b.couverture ? `<img src="${esc(racine(b.couverture))}" alt="" width="40" height="56" loading="lazy" decoding="async" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(b)}
          <div class="l-titre"><button type="button" data-id="${esc(b.id)}">${esc(b.titre)}</button><span class="sous" style="display:block">${esc(b.serie)}${esc(numero(b))}</span></div>${avecNotes ? window.Notes.etiquette(b.livre_id) : ''}</div></td>
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
      const cel = cotesMasquees() ? '' : ETATS.map((e) => {
        const s = stat(g.l, e.k);
        const barre = e.k === S.h && s.n ? `<span class="barre" style="width:${Math.max(4, (s.avg / maxi) * 100)}%"></span>` : '';
        return `<td class="num" data-label="${e.court}"><span class="prix-c${s.n ? '' : ' nul'}">${fmt(s.avg)}</span>${barre}</td>`;
      }).join('');
      return `<tr class="cliquable" data-groupe="${esc(g.k)}"><td class="principal"><div class="l-livre"><button type="button" data-groupe="${esc(g.k)}">${esc(nom)}</button></div></td>
        <td class="num" data-label="Livres">${g.l.length}</td>${cel}</tr>`;
    }).join('');
    $('#resultats').innerHTML = `<table class="cartes groupes"><thead><tr><th>${nomCol}</th><th class="num">Livres</th>
      ${cotesMasquees() ? '' : ETATS.map((e) => `<th class="num">${e.k === 'tres_bon' ? '<abbr title="Très bon état">TBE</abbr>' : e.court}</th>`).join('')}</tr></thead><tbody>${lignes}</tbody></table>
      <p class="sous" style="margin:14px 0 0">${cotesMasquees() ? 'Nombre de livres par groupe.' : 'Prix moyens par groupe.'} Touchez une ligne pour ne garder que ce groupe et voir ses livres sur l'étagère.</p>`;
    $('#resultats').querySelectorAll('tr.cliquable').forEach((tr) => tr.addEventListener('click', () => appliquerGroupe(tr.dataset.groupe)));
  }
  function appliquerGroupe(k) {
    if (S.g === 'serie') { S.serie = k; accorderEditeur(); }
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
  // Recherche de cette édition sur trois sites d'annonces (liens simples, ouverts dans un nouvel onglet)
  const requete = (t) => encodeURIComponent(t).replace(/%20/g, '+');
  function liensRecherche(b) {
    // Titre + « ldvelh » : ces sites exigent tous les mots, et les vendeurs écrivent « ldvelh » (livre dont vous êtes le héros),
    // presque jamais « V1 » ni « livre héros » (recherche vide constatée avec ces mots)
    const titre = b.titre.replace(/\s*\([^)]*\)/g, '').trim();                          // « (Grand format) » et autres parenthèses : absents des annonces
    const q = requete(`${titre} ldvelh`.replace(/\s+/g, ' '));
    const ebay = requete(`${titre} ${b.isbn13 || 'livre héros'}`);
    const liens = [
      ['Vinted', `https://www.vinted.fr/catalog?search_text=${q}`],
      ['Leboncoin', `https://www.leboncoin.fr/recherche?text=${q}&sort=time`],
      ['eBay', `https://www.ebay.fr/sch/i.html?_nkw=${ebay}`],
      ['Facebook', `https://www.facebook.com/marketplace/search/?query=${q}`],
    ];
    if (b.en_vente === 1 && b.isbn13) liens.push(['Amazon', `https://www.amazon.fr/s?k=${encodeURIComponent(b.isbn13)}`]);
    return liens;
  }
  const htmlLiens = (b) => liensRecherche(b).map(([nom, url]) => `<a class="bouton bouton-clair" href="${url}" target="_blank" rel="noopener noreferrer" aria-label="Chercher ${esc(b.titre)} sur ${nom} (nouvel onglet)">${nom}</a>`).join('');
  // Un bouton réservé aux comptes ouvre la fenêtre qui explique l'intérêt de se connecter (et non la connexion directe)
  document.addEventListener('click', (e) => { if (e.target.closest('[data-invite]') && window.Compte) window.Compte.inviter(); });
  function blocRecherche(b) {
    if (cotesMasquees()) {          // sans compte : seul Amazon reste libre ; les autres sites sont visibles, grisés, et mènent à la connexion
      const boutons = liensRecherche(b).map(([nom, url]) => nom === 'Amazon'
        ? `<a class="bouton bouton-clair" href="${url}" target="_blank" rel="noopener noreferrer" aria-label="Chercher ${esc(b.titre)} sur ${nom} (nouvel onglet)">${nom}</a>`
        : `<button type="button" class="bouton bouton-clair lien-reserve" data-invite aria-label="${nom} : réservé aux comptes connectés, se connecter">${nom}</button>`).join('');
      return `<h3>Chercher cette édition en vente</h3>
        <p class="liens-vente">${boutons}</p>
        <p class="sous">Vinted, Leboncoin, eBay et Facebook sont réservés aux comptes connectés : touchez-en un pour vous connecter avec Google.</p>`;
    }
    return `<h3>Chercher cette édition en vente</h3>
        <p class="liens-vente">${htmlLiens(b)}</p>
        <p class="sous">Recherches sur des sites extérieurs, dans un nouvel onglet. Le guide n'y est affilié à aucun titre.</p>`;
  }

  /* ---------- Annonces retenues (SuperAdmin) ---------- */
  // Les annonces eBay du dernier relevé (data/annonces.json) derrière la cote, par état : pour vérifier d'où vient un prix. Réservé au SuperAdmin.
  const estSuper = () => !!window.Compte && window.Compte.role() === 'superadmin';
  let ANN = null, annChargees = null;
  const chargerAnnonces = () => annChargees || (annChargees = fetch('data/annonces.json', { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).catch(() => null)
    .then((a) => { ANN = a && a.annonces ? a : null; return ANN; }));
  function blocAnnonces(b) {
    return `<details class="annonces-fiche" id="annonces-fiche" data-id="${esc(b.id)}"><summary>Annonces retenues <span class="badge-admin" title="Réservé au SuperAdmin">SuperAdmin</span></summary>
      <div class="annonces-corps" id="annonces-corps"><p class="sous">Chargement…</p></div></details>`;
  }
  function remplirAnnonces(b) {
    const zone = $('#annonces-corps');
    if (!zone) return;
    chargerAnnonces().then(() => {
      if (ficheOuverte !== b.id || !$('#annonces-corps')) return;
      const par = ANN && b.isbn13 ? ANN.annonces[b.isbn13] : null;
      const nb = par ? ETATS.reduce((n, e) => n + ((par[e.k] || []).length), 0) : 0;
      const resume = $('#annonces-fiche summary');
      if (resume && nb) resume.firstChild.textContent = `Annonces retenues (${nb}) `;
      if (!nb) { zone.innerHTML = `<p class="sous">${ANN ? 'Aucune annonce retenue pour cette édition.' : 'Pas encore de relevé d\'annonces.'}</p>`; return; }
      zone.innerHTML = ETATS.map((e) => {
        const l = par[e.k];
        if (!l || !l.length) return '';
        const disp = l.length > 1 && l[l.length - 1][0] > l[0][0] * 3 ? ' · prix très dispersés' : '';
        const partie = ([, , , , vue]) => !!(vue && ANN.date_ebay && vue < ANN.date_ebay);          // annonce non revue au dernier relevé : retirée d'eBay ou vendue
        const nbPartie = l.filter(partie).length;
        return `<h4>${esc(e.long)} · ${l.length} annonce${l.length > 1 ? 's' : ''}${nbPartie ? ` (dont ${nbPartie} plus en ligne)` : ''}${disp}</h4><ul>${l.map((a) => {
          const [prix, titre, lien, origine, vue] = a;
          return `<li><span class="ann-prix">${fmt(prix)}</span><a href="${esc(lien)}" target="_blank" rel="noopener noreferrer" aria-label="Ouvrir l'annonce sur eBay (nouvel onglet) : ${esc(titre)}">${esc(titre)} ↗</a>${origine === 'titre' ? '<span class="ann-titre">trouvée par le titre</span>' : ''}${partie(a) ? `<span class="ann-titre">plus en ligne · vue le ${dateCourte(vue)}</span>` : ''}</li>`; }).join('')}</ul>`;
      }).join('') + `<p class="sous">Dernier relevé du ${dateCourte(ANN.date_ebay || ANN.date)}. Prix demandés, pas des prix payés. Ouvrez une annonce pour vérifier le livre et son état.</p>`;
    });
  }

  /* ---------- Correction des cotes depuis la fiche (propriétaire) ---------- */
  // Visible seulement pour un compte Admin ou SuperAdmin connecté (niveau donné par le relais, voir relais/ et compte.js).
  // L'envoi lance le lot « Corriger des cotes » par le relais : aucune clé n'est dans le navigateur.
  const estProprietaire = () => !!window.Cloud && window.Cloud.actif() && !!window.Compte && ['admin', 'superadmin'].includes(window.Compte.role());   // niveau donné par le relais
  // Dernière révision d'une fiche : validation la plus récente de l'un de ses états (aujourd'hui, hier ou la date)
  function derniereRevision(b) {
    const infos = ['convenable', 'bon', 'tres_bon'].map((k) => infoPrix(b, k)).filter((i) => i && i.valide && i.date).sort((x, y) => (x.date < y.date ? 1 : -1));
    if (!infos.length) return '<p class="sous corriger-revision">Pas encore révisée.</p>';
    const i = infos[0], aujourdhui = new Date().toISOString().slice(0, 10), ecart = Math.round((Date.parse(aujourdhui) - Date.parse(i.date)) / 86400000);
    const quand = ecart <= 0 ? 'aujourd\'hui' : ecart === 1 ? 'hier' : 'le ' + dateCourte(i.date);
    return `<p class="sous corriger-revision">Dernière révision : <strong>${esc(quand)}</strong>${i.par ? ', par ' + esc(i.par) : ''}.</p>`;
  }
  // Corriger la fiche (titre, série, numéro, suppression) : réservé aux administrateurs, envoyé par le relais
  function blocFiche(b) {
    const series = [...new Set(DATA.map((x) => x.serie).filter(Boolean))].sort((x, y) => x.localeCompare(y, 'fr'));
    return `<details class="corriger-fiche"><summary>Corriger la fiche <span class="badge-admin" title="Réservé aux administrateurs">Admin</span></summary>
      <form class="corriger" id="corriger-fiche" data-id="${esc(b.id)}">
        <p class="sous">Le titre et la série s'appliquent à toutes les éditions de ce livre ; le numéro, à cette édition seulement. Pour une nouvelle série, écrivez simplement son nom.</p>
        <div class="corriger-champs corriger-fiche-champs">
          <label>Titre<input type="text" name="titre" maxlength="120" autocomplete="off" value="${esc(b.titre)}"></label>
          <label>Série<input type="text" name="serie" maxlength="120" autocomplete="off" list="liste-series" value="${esc(b.serie)}"></label>
          <label>Numéro<input type="text" name="numero" inputmode="numeric" maxlength="4" autocomplete="off" value="${esc(b.numero && b.numero !== '000' ? b.numero : '')}"></label>
        </div>
        <datalist id="liste-series">${series.map((x) => `<option value="${esc(x)}">`).join('')}</datalist>
        <div class="corriger-actions"><button type="submit" class="bouton">Enregistrer la fiche</button></div>
        ${window.Compte && window.Compte.role() === 'superadmin' ? `<label class="case corriger-suppr"><input type="checkbox" name="suppr"><span>Supprimer cette édition de la base (jaquette et prix compris) <span class="badge-admin" title="Réservé au SuperAdmin">SuperAdmin</span></span></label>
        <div class="corriger-actions"><button type="button" class="bouton bouton-clair" id="corriger-suppr" hidden>Supprimer définitivement cette édition</button></div>` : ''}
        <p class="corriger-msg" id="corriger-fiche-msg" role="status" hidden></p>
      </form></details>`;
  }
  function brancherFiche() {
    const f = $('#corriger-fiche');
    if (!f) return;
    const msg = $('#corriger-fiche-msg'), dire = (t) => { msg.textContent = t; msg.hidden = false; };
    const b = DATA.find((x) => x.id === f.dataset.id);
    const numAffiche = b.numero && b.numero !== '000' ? b.numero : '';
    if (f.elements.suppr) f.elements.suppr.addEventListener('change', () => { $('#corriger-suppr').hidden = !f.elements.suppr.checked; });
    const envoyer = async (corrections) => {
      if (!(window.Relais && window.Relais.actif())) return dire('Votre connexion a expiré : reconnectez-vous avec le bouton du compte, en haut de la page.');
      f.querySelectorAll('button').forEach((x) => { x.disabled = true; }); dire('Envoi en cours…');
      try {
        const r = await window.Relais.envoyerLot('corriger-fiche.yml', { corrections: corrections.join(' | ') });
        if (r.status === 204) dire('Envoyé. Le site sera à jour dans environ 2 minutes : rechargez la page ensuite.');
        else if (r.status === 401 || r.status === 403) dire("Ce compte n'a pas les droits d'administrateur, ou la connexion Google a expiré : reconnectez-vous.");
        else dire(`Échec de l'envoi : ${r.erreur || 'code ' + r.status}.`);
      } catch (e) { dire('Envoi impossible : vérifiez votre connexion.'); }
      f.querySelectorAll('button').forEach((x) => { x.disabled = false; });
    };
    const net = (t) => t.replace(/[;|]/g, ' ').replace(/\s+/g, ' ').trim();
    f.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const l = [], t = net(f.elements.titre.value), se = net(f.elements.serie.value), n = f.elements.numero.value.trim();
      if (t && t !== b.titre) l.push(`${b.id} ; titre ; ${t}`);
      if (se && se !== b.serie) l.push(`${b.id} ; serie ; ${se}`);
      if (n && n !== numAffiche) { if (!/^\d{1,4}$/.test(n)) return dire('Le numéro doit être un nombre.'); l.push(`${b.id} ; numero ; ${n}`); }
      if (!l.length) return dire("Rien n'a changé.");
      envoyer(l);
    });
    if ($('#corriger-suppr')) $('#corriger-suppr').addEventListener('click', () => { if (window.confirm(`Supprimer « ${b.titre} » (${b.version}) de la base ? Cette action est définitive.`)) envoyer([`${b.id} ; supprimer`]); });
  }
  function blocCorriger(b) {
    if (!estProprietaire()) return '';
    if (!b.isbn13) return '<h3>Corriger les cotes <span class="badge-admin" title="Réservé aux administrateurs">Admin</span></h3><p class="sous">Cette fiche n\'a pas d\'ISBN : la correction des cotes n\'est pas possible ici.</p>';
    const champ = ([k, nom]) => `<label>${nom}<input type="text" inputmode="decimal" name="${k}" autocomplete="off" placeholder="${b.prix[k] == null ? '—' : String(b.prix[k]).replace('.', ',')}"></label>`;
    return `<h3>Corriger les cotes <span class="badge-admin" title="Réservé aux administrateurs">Admin</span></h3>
        ${derniereRevision(b)}
        <form class="corriger" id="corriger" data-isbn="${esc(b.isbn13)}">
          <p class="sous">Le plus simple : la <strong>fourchette observée</strong>. Le prix le plus bas est compté en convenable, le plus haut en très bon état, et le bon état en est déduit. Un seul prix est compté en très bon état.</p>
          <div class="corriger-fourchette"><label>De<input type="text" inputmode="decimal" name="mini" autocomplete="off" placeholder="€"></label>
            <label>à<input type="text" inputmode="decimal" name="maxi" autocomplete="off" placeholder="€"></label></div>
          <details class="corriger-detail"><summary>Ou fixer chaque état</summary>
          <p class="sous">Les états laissés vides en sont déduits ; votre prix prime ensuite sur tout le reste.</p>
          <div class="corriger-champs">${[['convenable', 'Convenable'], ['bon', 'Bon état'], ['tres_bon', 'Très bon état']].map(champ).join('')}</div></details>
          <div class="corriger-actions"><button type="submit" class="bouton">Enregistrer ces prix</button></div>
          <p class="corriger-msg" id="corriger-msg" role="status" hidden></p>
        </form>`;
  }
  function brancherCorriger() {
    brancherFiche();
    const f = $('#corriger');
    if (!f) return;
    f.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const msg = $('#corriger-msg'), dire = (t) => { msg.textContent = t; msg.hidden = false; };
      const nb = (x) => parseFloat(String(x).replace(',', '.'));
      const v = ['convenable', 'bon', 'tres_bon'].map((k) => f.elements[k].value.trim());
      const mini = f.elements.mini.value.trim(), maxi = f.elements.maxi.value.trim();
      if (mini || maxi) {                                   // fourchette : le bas en convenable, le haut en très bon état, un seul prix en très bon état
        if ([mini, maxi].some((x) => x && !(nb(x) > 0))) return dire('Un des prix de la fourchette n\'est pas un nombre : corrigez-le.');
        if (mini && maxi && nb(mini) > nb(maxi)) return dire('Le prix le plus bas doit venir en premier.');
        if (mini && maxi) { v[0] = mini; v[2] = maxi; } else v[2] = mini || maxi;
      }
      if (v.some((x) => x && !(nb(x) > 0))) return dire('Un des prix n\'est pas un nombre : corrigez-le.');
      if (!v.some(Boolean)) return dire('Indiquez au moins un prix.');
      const ligne = `${f.dataset.isbn} ; ${v.join(' ; ')}`;
      if (!(window.Relais && window.Relais.actif())) return dire('Votre connexion a expiré : reconnectez-vous avec le bouton du compte, en haut de la page.');
      f.querySelector('button').disabled = true; dire('Envoi en cours…');
      try {
        const r = await window.Relais.envoyerLot('corriger-prix.yml', { corrections: ligne });
        if (r.status === 204) dire('Envoyé. Le site sera à jour dans environ 2 minutes : rechargez la page ensuite.');
        else if (r.status === 401 || r.status === 403) dire('Ce compte n\'a pas les droits d\'administrateur, ou la connexion Google a expiré : reconnectez-vous.');
        else dire(`Échec de l'envoi : ${r.erreur || 'code ' + r.status}.`);
      } catch (e) { dire('Envoi impossible : vérifiez votre connexion.'); }
      f.querySelector('button').disabled = false;
    });
  }

  function ouvrirDepuisAdresse() {
    const id = FICHE_URL;
    if (!id || !DATA.some((b) => b.id === id)) return;
    ouvrirFiche(id);
    if (!CORR_URL) return;
    const ouvrir = () => { const d = $('.corriger-fiche'); if (d) d.open = true; return !!d; };
    if (ouvrir()) return;
    const retenter = () => { if (!estProprietaire()) return; document.removeEventListener('cdh-compte', retenter); ouvrirFiche(id); ouvrir(); };   // le niveau d'administrateur arrive après le chargement
    document.addEventListener('cdh-compte', retenter);
  }
  let ficheOuverte = null, RETOUR_FICHE = '';      // RETOUR_FICHE : la jaquette d'où l'on est venu, pour y remettre le focus à la fermeture
  function ouvrirFiche(id) {
    const b = DATA.find((x) => x.id === id);
    if (!b) return;
    ficheOuverte = id;
    if (sansCompte()) {                       // fiches distinctes consultées pendant la visite : sert à proposer la connexion (voir inviterApresFiches)
      try { const vus = new Set(JSON.parse(sessionStorage.getItem('cdh-fiches-vues') || '[]')); vus.add(b.livre_id); sessionStorage.setItem('cdh-fiches-vues', JSON.stringify([...vus])); } catch (e) { /* stockage indisponible */ }
    }
    const sel = etatDe(S.h);
    const autres = DATA.filter((x) => x.livre_id === b.livre_id).sort((x, y) => x.version_n - y.version_n);
    const ligne = (nom, val) => (val ? `<div><dt>${nom}</dt><dd>${val}</dd></div>` : '');
    const annee = b.annee ? (b.annee_bnf && b.annee_bnf !== b.annee ? `${b.annee} <span class="sous">(notice BnF : ${b.annee_bnf})</span>` : b.annee) : '';
    const notice = b.notice ? `<a href="${esc(b.notice)}" target="_blank" rel="noopener">Notice de la BnF</a>` : '';
    const fond = b.couverture_grande || b.couverture;
    const zoneFiche = $('#fiche-contenu');
    zoneFiche.classList.toggle('a-fond', !!fond);
    if (fond) zoneFiche.style.setProperty('--fond', `url("${racine(fond)}")`); else zoneFiche.style.removeProperty('--fond');
    $('#fiche-contenu').innerHTML = `
      ${fond ? '<div class="fiche-fond" aria-hidden="true"></div>' : ''}
      <div class="fiche">
        <div class="fiche-haut">
          <div class="fiche-couv">${b.couverture_grande
            ? `<img src="${esc(racine(b.couverture_grande))}" alt="Jaquette de ${esc(b.titre)}" width="300" height="420" decoding="async" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">`
            : tuile(b)}</div>
          <div>
            <div class="fiche-tete"><h2 id="fiche-titre">${esc(b.titre)}</h2>
              <button type="button" class="fermer" id="fermer" aria-label="Fermer la fiche">×</button></div>
            <p class="fiche-sous"><span class="badge">${esc(b.version)}</span><span>${esc(b.serie)}${esc(numero(b))}</span>${pastilleRarete(b)}${b.parution ? `<span class="rarete" title="Livre annoncé, pas encore en librairie">Paraît le ${new Date(b.parution + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}</span>` : ''}${b.en_vente === 1 ? '<span>· encore en vente neuve</span>' : ''}</p>
            ${b.parution && b.isbn13 ? `<p class="fiche-precommande"><span>Précommander :</span>${[['Libraires', `https://www.leslibraires.fr/livre/${b.isbn13}`], ['Fnac', `https://www.fnac.com/SearchResult/ResultList.aspx?Search=${b.isbn13}`], ['Amazon', `https://www.amazon.fr/s?k=${b.isbn13}`]].map(([nom, url]) => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="${nom} (nouvel onglet)">${nom} ↗</a>`).join('')}</p>` : ''}
            ${estProprietaire() ? blocFiche(b) : ''}
            <div class="note-livre" id="note-livre" hidden></div>
            ${cotesMasquees() ? `<h3 class="fiche-cotes-titre">Niveau de prix</h3>
        <div class="cotes">${ETATS.map((e) => `<div class="${e.k === sel.k ? 'choisi' : ''}"><span class="petit">${e.k === 'tres_bon' ? '<abbr title="Très bon état">TBE</abbr>' : e.court}</span><span class="valeur repere" aria-label="${b.prix[e.k] == null ? 'sans cote' : 'niveau de prix ' + niveauCote(b.prix[e.k], e.k) + ' sur 5'}">${repere(b.prix[e.k], e.k)}</span></div>`).join('')}</div>
        <p class="sous legende-prix"><span class="niveaux">${LEGENDE_NIVEAUX}</span>Les prix estimés sont réservés aux comptes connectés.</p>` : `<h3 class="fiche-cotes-titre">Cotes de cette édition</h3>
        <div class="cotes">${ETATS.map((e) => `<div class="${e.k === sel.k ? 'choisi' : ''}"><span class="petit">${e.k === 'tres_bon' ? '<abbr title="Très bon état">TBE</abbr>' : e.court}</span><span class="valeur">${fmt(b.prix[e.k])}</span></div>`).join('')}</div>
        <p class="sous legende-prix">${legendePrix(b, sel.k)}</p>`}

          </div>
        </div>
        ${blocCollectionFiche(b)}
        <h3>Détails du livre</h3>
        <dl class="infos">
              ${ligne('Auteurs', esc(b.auteurs))}${ligne('Traducteur', esc(b.traducteur))}${ligne('Illustrateur', esc(b.illustrateur))}
              ${ligne('Éditeur', esc(b.editeur))}${ligne('Collection', esc(b.collection))}${ligne('Année d\'édition', annee)}
              ${ligne('Pages', b.pages)}${ligne('Rareté', b.rarete ? `${RARETE[b.rarete.niveau]} <span class="sous">(${b.rarete.tirages ? 'imprimé ' + b.rarete.tirages + ' fois par Gallimard' : ''}${b.rarete.tirages && b.rarete.pct != null ? ' ; ' : ''}${b.rarete.pct != null ? 'dans ' + b.rarete.pct + ' % des collections saisies sur collection-ldvelh.fr' : ''} ; une information, qui n'entre pas dans la cote)</span>` : '')}${ligne('ISBN', esc(b.isbn13))}${ligne('Source', notice)}
            </dl>

        ${blocNeuf(b)}
        ${estSuper() ? blocAnnonces(b) : ''}
        ${blocRecherche(b)}
        ${blocCorriger(b)}
        ${autres.length > 1 ? `<h3>Les ${autres.length} éditions de ce livre</h3>
        <div class="autres">${autres.map((x) => `<button type="button" class="autre${x.id === b.id ? ' courante' : ''}" data-autre="${esc(x.id)}" aria-label="Édition ${esc(x.version)}${x.annee ? ', ' + x.annee : ''}">
          ${x.couverture ? `<img src="${esc(racine(x.couverture))}" alt="" width="88" height="124" loading="lazy" data-i="${esc((x.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(x)}
          <span class="v">${esc(x.version)}<small>${x.annee ?? ''}</small></span><span class="p">${coteTxt(x.prix[sel.k], sel.k, true)}</span></button>`).join('')}</div>` : ''}
        ${prixAnciens() ? `<p class="sous" style="margin-top:16px">Cotes d'archives, issues d'un ancien relevé qui n'est plus mis à jour : un ordre de grandeur, pas la cote du jour.</p>` : ''}
      </div>`;
    const dlg = $('#fiche');
    if (window.Notes) window.Notes.rendre($('#note-livre'), b.livre_id);
    brancherFicheCollection(b);
    brancherCorriger();
    if (estSuper()) remplirAnnonces(b);
    $('#fermer').addEventListener('click', () => dlg.close());
    $('#fiche-contenu').querySelectorAll('[data-autre]').forEach((el) =>
      el.addEventListener('click', () => { if (el.dataset.autre !== b.id) ouvrirFiche(el.dataset.autre); }));
    if (!dlg.open) { RETOUR_FICHE = (document.activeElement && document.activeElement.dataset && document.activeElement.dataset.id) || ''; dlg.showModal(); }
    dlg.scrollTop = 0;
  }

  // Clic sur une carte ou un titre
  document.addEventListener('click', (e) => {
    const etatBtn = e.target.closest('button[data-etat-possede]');
    if (etatBtn) {
      const id = etatBtn.dataset.etatPossede, depuisAjout = !!etatBtn.closest('#ca-res');
      basculerPossede(id, etatBtn.dataset.e);
      if (depuisAjout && COLL[id]) retourAjoutColl(id);          // le livre est ajouté : retour au champ pour le suivant, sans remonter à la main
      return;
    }
    const vendreBtn = e.target.closest('button[data-vendre-carte]');
    if (vendreBtn) { basculerVendre(vendreBtn.dataset.vendreCarte); return; }
    const souhaitBtn = e.target.closest('button[data-souhait-carte]');
    if (souhaitBtn) { basculerSouhait(souhaitBtn.dataset.souhaitCarte); return; }
    const carte = e.target.closest('button[data-id]') || (e.target.closest('.livre-carte .prix') && e.target.closest('.livre-carte').querySelector('button.ouvrir'));
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


  /* ---------- Ma collection : stockage local, estimation, import / export ---------- */
  const CLE = 'cote-collection-v1';
  /* Format du fichier de sauvegarde (JSON) et du lien de transfert.
     Règles pour ne jamais casser le fichier d'un visiteur :
     1. le livre est identifié par son ISBN (stable), le reste n'est que de l'affichage ;
     2. on peut AJOUTER des champs librement ; renommer ou retirer un champ impose de passer au format suivant
        ET d'écrire ici la conversion de l'ancien format, que l'on ne supprime jamais ;
     3. un champ ou un livre inconnu est ignoré et signalé, il ne fait jamais échouer l'import. */
  const FORMAT_FICHIER = 1;
  let COLL = {};
  let COLL_PRET = false;                       // vrai quand la collection de l'appareil est lue : jusque-là, COLL est vide et ne doit jamais être synchronisée
  let stockageOk = true;
  const chargerColl = () => {
    try { COLL = JSON.parse(localStorage.getItem(CLE) || '{}') || {}; } catch (e) { COLL = {}; stockageOk = false; }
    // Frais de port gardés à part par une version précédente : ils rejoignent le prix payé du livre (livraison comprise)
    Object.values(COLL).forEach((c) => { if (c && c.port > 0) { if (c.prix != null) c.prix = Math.round((c.prix + c.port / (c.qte || 1)) * 100) / 100; delete c.port; } else if (c) delete c.port; });
  };
  // « À trouver » : livres recherchés, rangés dans le même fichier synchronisé sous la clé « souhait:<id> ».
  // Un livre entré dans la collection quitte la liste tout seul.
  const CLE_S = 'cote-souhaits-v1', PRE = 'souhait:';
  let SOUH = {};
  const chargerSouh = () => { try { SOUH = JSON.parse(localStorage.getItem(CLE_S) || '{}') || {}; } catch (e) { SOUH = {}; } };
  const purgerSouh = () => { Object.keys(SOUH).forEach((id) => { if (COLL[id]) delete SOUH[id]; }); };
  const sauverLocal = () => {
    purgerSouh();
    try { localStorage.setItem(CLE, JSON.stringify(COLL)); localStorage.setItem(CLE_S, JSON.stringify(SOUH)); stockageOk = true; } catch (e) { stockageOk = false; }
  };
  const toutSynchro = () => {
    purgerSouh();
    const t = Object.assign({}, COLL);
    Object.keys(SOUH).forEach((id) => { t[PRE + id] = SOUH[id]; });
    return t;
  };
  // Chaque modification est gardée sur l'appareil, puis envoyée au Drive de la personne connectée (groupée, voir cloud.js)
  const adopterCloud = (c) => {
    COLL = {}; SOUH = {};
    Object.keys(c || {}).forEach((k) => { if (k.indexOf(PRE) === 0) SOUH[k.slice(PRE.length)] = c[k]; else COLL[k] = c[k]; });
    sauverLocal(); afficher();
  };
  const sauverColl = () => {
    sauverLocal();
    if (window.Cloud) window.Cloud.planifier(toutSynchro, adopterCloud);
    document.dispatchEvent(new Event('cdh-collection'));
  };
  window.AppCollection = { lire: toutSynchro, adopter: adopterCloud, nb: () => Object.keys(COLL).length, pret: () => COLL_PRET };
  // Construire sa collection exige un compte Google (consulter reste libre). `suite` est rejouée après la connexion.
  const garde = (suite) => !window.Compte || window.Compte.exiger(suite);
  const dansCompte = () => !!window.Compte && window.Compte.actif() && !!window.Cloud && window.Cloud.lie();
  const sansCompte = () => !!window.Compte && window.Compte.actif() && !window.Cloud.lie();
  // Cotes chiffrées réservées aux comptes : un visiteur voit un niveau de 1 à 5 euros (€ à €€€€€), jamais le chiffre. Tant que la configuration du compte
  // n'est pas lue, on masque aussi (pas d'affichage furtif des chiffres).
  const cotesMasquees = () => !!window.Compte && !dansCompte() && (!window.Compte.pret() || window.Compte.actif());
  // Cinq niveaux à seuils fixes (en euros) : moins de 10, 10 à 20, 20 à 40, 40 à 70, 70 et plus. Les mêmes seuils pour les trois états.
  const SEUILS_COTE = [10, 20, 40, 70];
  const niveauCote = (v, k) => (v == null ? 0 : 1 + SEUILS_COTE.filter((x) => v >= x).length);
  const LEGENDE_NIVEAUX = [['€', '&lt; 10 €'], ['€€', '10–20 €'], ['€€€', '20–40 €'], ['€€€€', '40–70 €'], ['€€€€€', '&gt; 70 €']]
    .map(([n, t]) => `<span class="nowrap"><strong>${n}</strong> ${t}</span>`).join('');
  const repere = (v, k) => (v == null ? '—' : '€'.repeat(niveauCote(v, k)));
  const coteTxt = (v, k, court) => (cotesMasquees() ? repere(v, k, court) : fmt(v));
  // Le compte change (connexion, expiration, déconnexion) : la collection et la fiche ouverte se redessinent
  let etaitSansCompte = null, etaitSuper = null, appPrete = false;
  document.addEventListener('cdh-compte', () => {
    if (!appPrete) return;
    const sans = sansCompte();
    afficher();
    if (etaitSansCompte !== null && etaitSansCompte !== sans && ficheOuverte && $('#fiche') && $('#fiche').open) ouvrirFiche(ficheOuverte);
    etaitSansCompte = sans;
    const super_ = estSuper();           // le rôle arrive après l'ouverture de la fiche : le bloc des annonces apparaît (ou disparaît) sans la rouvrir
    if (etaitSuper !== null && etaitSuper !== super_ && ficheOuverte && $('#fiche') && $('#fiche').open) ouvrirFiche(ficheOuverte);
    etaitSuper = super_;
    if (window.Compte) window.Compte.accueillir();
  });
  const annonce = (t) => { $('#annonce').textContent = ''; setTimeout(() => { $('#annonce').textContent = t; }, 30); };
  const parId = () => new Map(DATA.map((b) => [b.id, b]));
  let INDEX = null;
  const livreDe = (id) => (INDEX || (INDEX = parId())).get(id);

  // C / BE / TBE sur une jaquette : ajoute le livre dans cet état ; retoucher l'état choisi le retire
  function basculerPossede(id, etat) {
    const b = livreDe(id);
    if (!b) return;
    if (!garde(() => basculerPossede(id, etat))) return;
    if (COLL[id] && COLL[id].etat === etat) { delete COLL[id]; annonce(`${b.titre} retiré de votre collection.`); }
    else {
      COLL[id] = { etat, qte: (COLL[id] && COLL[id].qte) || 1, ...gv(COLL[id]) };
      annonce(`${b.titre} : en ${etatDe(etat).long.toLowerCase()} dans votre collection.`);
    }
    sauverColl();
    afficher();
  }
  // T sur une jaquette : le livre entre dans la liste « À trouver » ; retoucher T l'en retire
  // Depuis une jaquette de l'étagère : un livre de la collection part dans la liste « à vendre » (ou en revient)
  function basculerVendre(id) {
    const b = livreDe(id);
    if (!b || !COLL[id] || !garde(() => basculerVendre(id))) return;
    if (COLL[id].vendre) { delete COLL[id].vendre; annonce(`${b.titre} retiré de votre liste à vendre.`); }
    else { COLL[id].vendre = true; annonce(`${b.titre} ajouté à votre liste à vendre.`); }
    sauverColl();
    afficher();
  }
  function basculerSouhait(id) {
    const b = livreDe(id);
    if (!b || !garde(() => basculerSouhait(id))) return;
    if (SOUH[id]) { delete SOUH[id]; annonce(`${b.titre} retiré de votre liste à trouver.`); }
    else { SOUH[id] = {}; annonce(`${b.titre} ajouté à votre liste à trouver.`); }
    sauverColl();
    afficher();
  }
  const valeurLigne = (b, c) => (b.prix[c.etat] == null ? null : b.prix[c.etat] * c.qte);
  // Prix payé (facultatif, par exemplaire) : un nombre entre 0,01 et 2000 €, virgule ou point acceptés
  const lirePrix = (t) => { const n = parseFloat(String(t ?? '').replace(',', '.')); return Number.isFinite(n) && n > 0 && n <= 2000 ? Math.round(n * 100) / 100 : null; };
  const prixSaisi = (p) => (p == null ? '' : String(p).replace('.', ','));

  function bilan(garder = () => true) {
    const lignes = Object.entries(COLL).map(([id, c]) => ({ b: livreDe(id), c })).filter((x) => x.b).filter((x) => garder(x));
    let total = 0, bas = 0, haut = 0, exemplaires = 0, sansCote = 0, actuels = 0, investi = 0, nbPayes = 0;
    lignes.forEach(({ b, c }) => {
      exemplaires += c.qte;
      const v = valeurLigne(b, c);
      if (c.prix != null) { investi += c.prix * c.qte; nbPayes += c.qte; }
      if (v == null) sansCote += c.qte; else { total += v; if (estActuel(infoPrix(b, c.etat))) actuels += c.qte; }
      bas += (b.prix.convenable ?? 0) * c.qte;
      haut += (b.prix.tres_bon ?? 0) * c.qte;
    });
    return { lignes, total, bas, haut, exemplaires, sansCote, actuels, investi, nbPayes, titres: new Set(lignes.map((x) => x.b.livre_id)).size };
  }

  // Analyses du portefeuille (accueil) : où est la valeur, par série, éditions d'origine, fiabilité des cotes, répartition par état
  function analysesPortefeuille(bl, page = false, avant = '') {
    const L = bl.lignes.map(({ b, c }) => ({ b, c, v: valeurLigne(b, c) })).filter((x) => x.v != null).sort((x, y) => y.v - x.v);
    if (!L.length || !bl.total) return '';
    const somme = (liste) => liste.reduce((t, x) => t + x.v, 0);
    const pc = (v) => `${Math.round((100 * v) / bl.total)} %`;
    const top = L.slice(0, 5), parSerie = new Map();
    L.forEach((x) => parSerie.set(x.b.serie, (parSerie.get(x.b.serie) || 0) + x.v));
    const series = [...parSerie.entries()].sort((x, y) => y[1] - x[1]).slice(0, 4);
    const origine = somme(L.filter((x) => x.b.version_n === 1)), recent = somme(L.filter((x) => estActuel(infoPrix(x.b, x.c.etat))));
    const exNeufs = bl.lignes.filter((x) => x.b.en_vente === 1).reduce((t, x) => t + x.c.qte, 0);
    const etats = { convenable: 0, bon: 0, tres_bon: 0 };
    bl.lignes.forEach(({ c }) => { if (etats[c.etat] !== undefined) etats[c.etat] += c.qte; });
    const unitaires = L.flatMap((x) => Array(x.c.qte).fill(x.v / x.c.qte)).sort((x, y) => x - y);
    const mediane = unitaires.length % 2 ? unitaires[(unitaires.length - 1) / 2] : (unitaires[unitaires.length / 2 - 1] + unitaires[unitaires.length / 2]) / 2;
    const barre = (v) => `<span class="hc-barre"><i style="width:${Math.max(3, Math.round((100 * v) / bl.total))}%"></i></span>`;
    const entete = page ? `<details class="hc-analyses" id="titre-analyses"><summary>Comprendre mon portefeuille${filtresActifs() ? ' <span class="sous">· selon vos filtres</span>' : ''}</summary><div class="hc-grille hc-grille-page">`
      : `<details class="hc-analyses"><summary>${avant ? 'Comprendre ma collection' : 'Comprendre mon portefeuille'}</summary><div class="hc-grille">${avant}`;
    return `${entete}
      <div><h3>Où se trouve la valeur</h3>
        <p>Vos 5 exemplaires les plus chers pèsent <strong>${pc(somme(top))}</strong> de la valeur.</p>
        ${(() => { const [p1, ...reste] = L.slice(0, 7); const img = (x, l, h) => (x.b.couverture ? `<img src="${esc(racine(x.b.couverture))}" alt="" width="${l}" height="${h}" loading="lazy" decoding="async">` : `<span class="hc-sans-img" style="width:${l}px;height:${h}px"></span>`);
          return `<div class="hc-premier">${img(p1, 56, 84)}<span><small>Le plus précieux</small>${esc(p1.b.titre)} <span class="sous">${esc(p1.b.version)}</span><br><strong>${fmtE(p1.v)}</strong>${p1.c.qte > 1 ? ` <span class="sous">(${p1.c.qte} exemplaires)</span>` : ''}</span></div>
          <ul class="hc-vignettes" aria-label="Les exemplaires suivants, du plus cher au moins cher">${reste.map((x) => `<li title="${esc(x.b.titre)} (${esc(x.b.version)}) : ${fmtE(x.v)}">${img(x, 44, 66)}<strong>${fmtE(x.v)}</strong></li>`).join('')}</ul>`; })()}
      </div>
      <div><h3>Par série</h3><ul class="hc-series">${series.map(([nom, v]) => `<li><span>${esc(nom)}</span><strong>${pc(v)}</strong>${barre(v)}</li>`).join('')}</ul></div>
      <div><h3>Éditions d'origine</h3><p><strong>${pc(origine)}</strong> de la valeur est en première édition (V1). Le reste est en rééditions.</p>
        ${exNeufs ? `<p>${exNeufs} exemplaire${exNeufs > 1 ? 's' : ''} encore vendu${exNeufs > 1 ? 's' : ''} neuf${exNeufs > 1 ? 's' : ''} : leur cote est le prix du neuf.</p>` : ''}</div>
      <div><h3>Fiabilité des cotes</h3><p><strong>${pc(recent)}</strong> de la valeur repose sur des prix récents ; le reste, sur d'anciennes archives (un ordre de grandeur).</p>
        ${bl.sansCote ? `<p>${bl.sansCote} exemplaire${bl.sansCote > 1 ? 's' : ''} sans cote, non compté${bl.sansCote > 1 ? 's' : ''}.</p>` : ''}</div>
      <div><h3>Selon l'état</h3><p>${etats.convenable} en convenable · ${etats.bon} en bon état · ${etats.tres_bon} en très bon état.</p>
        <p>Valeur médiane d'un exemplaire : <strong>${fmtE(mediane)}</strong>. Selon l'état réel, la collection vaut de <strong>${fmtE(bl.bas)}</strong> (tout en convenable) à <strong>${fmtE(bl.haut)}</strong> (tout en très bon état).</p></div>
    </div></details>`;
  }

  // Accueil, vue collectionneur : séries commencées (titres possédés / titres du catalogue), sans aucun montant
  function seriesCollection(bl) {
    const poss = new Map(), tot = new Map();
    bl.lignes.forEach(({ b }) => { (poss.get(b.serie) || poss.set(b.serie, new Set()).get(b.serie)).add(b.livre_id); });
    DATA.forEach((b) => { (tot.get(b.serie) || tot.set(b.serie, new Set()).get(b.serie)).add(b.livre_id); });
    return [...poss].map(([nom, set]) => ({ nom, possedes: set.size, total: tot.get(nom).size })).sort((x, y) => y.possedes - x.possedes || x.nom.localeCompare(y.nom, 'fr'));
  }

  // Éventail de quelques couvertures de la collection (tirées au hasard), anneau des titres par série, série la plus proche d'être complète
  const COULEURS_ANNEAU = ['#d9b45f', '#7f9fc4', '#8fb08a', '#c98a6b', '#8a8478'];
  function apercuVisuel(bl) {
    const series = seriesCollection(bl);
    if (!series.length) return '';
    const vus = new Set(), tops = [];
    bl.lignes.filter((x) => x.b.couverture).sort(() => Math.random() - 0.5).forEach((x) => { if (tops.length < 4 && !vus.has(x.b.livre_id)) { vus.add(x.b.livre_id); tops.push(x); } });
    const nbTitres = series.reduce((t, x) => t + x.possedes, 0);
    const parts = series.slice(0, 3).map((x) => [x.nom, x.possedes]).concat(series.length > 3 ? [['Autres séries', series.slice(3).reduce((t, x) => t + x.possedes, 0)]] : []);
    const r = 32, C = 2 * Math.PI * r;
    let decal = 0;
    const arcs = parts.map(([nom, n], i) => {
      const long = (n / nbTitres) * C, a = `<circle cx="42" cy="42" r="${r}" fill="none" stroke="${COULEURS_ANNEAU[i]}" stroke-width="14" stroke-dasharray="${Math.max(0, long - 1.5)} ${C}" stroke-dashoffset="${-decal}" transform="rotate(-90 42 42)"><title>${esc(nom)} : ${n} titre${n > 1 ? 's' : ''}</title></circle>`;
      decal += long; return a;
    }).join('');
    const legende = parts.map(([nom, n], i) => `<li><i style="background:${COULEURS_ANNEAU[i]}"></i><span>${esc(nom)}</span><b>${n}</b></li>`).join('');
    // la série commencée la plus proche d'être complète (au moins 6 titres au catalogue)
    const encours = series.filter((x) => x.total >= 6 && x.possedes < x.total).sort((x, y) => y.possedes / y.total - x.possedes / x.total || y.total - x.total)[0];
    return `<div class="hc-visuel">
      <div class="hc-eventail" aria-hidden="true">${tops.map((x, i) => `<img style="--i:${i}" src="${esc(racine(x.b.couverture))}" alt="" width="64" height="96" loading="lazy" decoding="async">`).join('')}</div>
      <div class="hc-anneau"><svg viewBox="0 0 84 84" width="84" height="84" role="img" aria-label="Titres possédés par série"><text x="42" y="40" text-anchor="middle" class="hc-anneau-n">${nbTitres}</text><text x="42" y="54" text-anchor="middle" class="hc-anneau-u">titres</text>${arcs}</svg>
        <ul class="hc-legende" aria-label="Titres possédés par série">${legende}</ul></div>
      ${encours ? `<div class="hc-progres"><span>${esc(encours.nom)} <b>${encours.possedes}</b>/${encours.total}</span><span class="hc-barre"><i style="width:${Math.max(3, Math.round((100 * encours.possedes) / encours.total))}%"></i></span>
        <button type="button" class="bouton-lien" data-parcours>${encours.total - encours.possedes === 1 ? 'Il en manque 1' : `Il en manque ${encours.total - encours.possedes}`} →</button></div>` : ''}
    </div>`;
  }

  // Détail repliable de l'accueil : où en est la collection, sans aucun montant
  function contenuCollecteur(bl) {
    const series = seriesCollection(bl);
    if (!series.length) return '';
    const etats = { convenable: 0, bon: 0, tres_bon: 0 };
    let origine = 0, rees = 0, plusAncien = null;
    bl.lignes.forEach(({ b, c }) => {
      if (etats[c.etat] !== undefined) etats[c.etat] += c.qte;
      if (b.version_n === 1) origine += 1; else rees += 1;
      if (b.annee && (!plusAncien || b.annee < plusAncien.b.annee)) plusAncien = { b };
    });
    const completes = series.filter((x) => x.possedes === x.total).length;
    return `
      <div><h3>Vos séries</h3><ul class="hc-series">${series.slice(0, 5).map((x) => `<li><span>${esc(x.nom)}</span><strong>${x.possedes}/${x.total}</strong><span class="hc-barre"><i style="width:${Math.max(3, Math.round((100 * x.possedes) / x.total))}%"></i></span></li>`).join('')}</ul>
        <p class="sous">${series.length} série${series.length > 1 ? 's' : ''} commencée${series.length > 1 ? 's' : ''}${completes ? `, dont ${completes} complète${completes > 1 ? 's' : ''}` : ''}.</p></div>
      <div><h3>Vos éditions</h3><p><strong>${origine}</strong> en première édition (V1), <strong>${rees}</strong> en réédition.</p>
        ${plusAncien ? `<p>Le plus ancien : <strong>${esc(plusAncien.b.titre)}</strong> (${plusAncien.b.annee}).</p>` : ''}</div>
      <div><h3>État de vos exemplaires</h3><p>${etats.convenable} en convenable · ${etats.bon} en bon état · ${etats.tres_bon} en très bon état.</p></div>`;
  }

  // Ligne discrète de chiffres clés, toujours visible (le détail est dans « Comprendre mon portefeuille »)
  function infosRapides(bl, avecSerie = true) {
    const L = bl.lignes.map(({ b, c }) => ({ b, c, v: valeurLigne(b, c) })).filter((x) => x.v != null).sort((x, y) => y.v - x.v);
    if (!L.length || !bl.total) return '';
    const pc = (v) => `${Math.round((100 * v) / bl.total)} %`;
    const somme = (liste) => liste.reduce((t, x) => t + x.v, 0);
    const parSerie = new Map();
    L.forEach((x) => parSerie.set(x.b.serie, (parSerie.get(x.b.serie) || 0) + x.v));
    const [serie, vSerie] = [...parSerie.entries()].sort((x, y) => y[1] - x[1])[0];
    const p1 = L[0], recent = somme(L.filter((x) => estActuel(infoPrix(x.b, x.c.etat))));
    const puce = (html, titre) => `<li title="${esc(titre)}">${html}</li>`;
    return `<ul class="hc-rapide" aria-label="Chiffres clés de la collection">` +
      puce(`${p1.b.couverture ? `<img src="${esc(racine(p1.b.couverture))}" alt="" width="20" height="30" loading="lazy" decoding="async">` : ''}<span>Le plus précieux <b>${esc(p1.b.titre)}</b> ${fmtE(p1.v)}</span>`, 'Exemplaire le plus cher de la sélection') +
      (avecSerie ? puce(`<span>${esc(serie)} <b>${pc(vSerie)}</b></span>`, 'Série qui pèse le plus dans la valeur') : '') +
      puce(`<span>Premières éditions <b>${pc(somme(L.filter((x) => x.b.version_n === 1)))}</b></span>`, 'Part de la valeur en première édition (V1)') +
      puce(`<span>Cotes récentes <b>${pc(recent)}</b></span>`, 'Part de la valeur fondée sur des prix récents (le reste vient d\'archives)') + '</ul>';
  }


  /* ---------- Filtres de la liste « Vos exemplaires » (page collection) ---------- */
  const FC0 = { q: '', serie: '', editeur: '', version: '', etat: '', cote: '', pmin: '', pmax: '', tri: 'serie' };
  let FC = { ...FC0 };
  const triSerie = (x, y) => x.b.serie.localeCompare(y.b.serie, 'fr') || (parseInt(x.b.numero, 10) || 0) - (parseInt(y.b.numero, 10) || 0) || x.b.version_n - y.b.version_n;
  const valeurTri = (x) => valeurLigne(x.b, x.c) ?? -1;
  const TRIS = {
    serie: ['Série et numéro', triSerie],
    valeur: ['Valeur décroissante', (x, y) => valeurTri(y) - valeurTri(x) || triSerie(x, y)],
    valeur_asc: ['Valeur croissante', (x, y) => valeurTri(x) - valeurTri(y) || triSerie(x, y)],
    titre: ['Titre (A à Z)', (x, y) => x.b.titre.localeCompare(y.b.titre, 'fr') || triSerie(x, y)],
    annee: ['Année croissante', (x, y) => (x.b.annee || 9999) - (y.b.annee || 9999) || triSerie(x, y)],
  };
  const filtresActifs = () => Object.keys(FC0).some((k) => k !== 'tri' && FC[k] !== FC0[k]);

  // Un exemplaire est retenu s'il passe tous les filtres ; « avecTranche » : y compris la tranche de prix cliquée sur l'histogramme
  // (l'histogramme lui-même ignore la tranche, pour que toutes ses barres restent visibles)
  function retenue({ b, c }, avecTranche = true) {
    const q = norm(FC.q).trim();
    if (q && !b._txt.includes(q)) return false;
    if ((FC.serie && b.serie !== FC.serie) || (FC.editeur && b.editeur !== FC.editeur) || (FC.version && b.version !== FC.version) || (FC.etat && c.etat !== FC.etat)) return false;
    if (FC.cote && (FC.cote === 'avec') !== (valeurLigne(b, c) != null)) return false;
    if (avecTranche && (FC.pmin !== '' || FC.pmax !== '')) {
      const p = b.prix[c.etat];
      if (p == null || (FC.pmin !== '' && p < +FC.pmin) || (FC.pmax !== '' && p >= +FC.pmax)) return false;
    }
    return true;
  }

  function listeExemplaires(bl) {
    const triees = bl.lignes.filter((x) => retenue(x)).sort((TRIS[FC.tri] || TRIS.serie)[1]);
    const vus = triees.slice(0, limiteColl);
    const html = vus.map(({ b, c }) => {
      const v = valeurLigne(b, c);
      const nom = `${esc(b.titre)}, édition ${esc(b.version)}`;
      return `<li class="ex" data-ligne="${esc(b.id)}">
        <div class="ex-livre"><button type="button" class="retirer" data-retirer="${esc(b.id)}" title="Retirer de ma collection" aria-label="Retirer ${nom} de ma collection">×</button>${b.couverture ? `<img src="${esc(racine(b.couverture))}" alt="" width="48" height="68" loading="lazy" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(b)}
          <div class="ex-titre"><button type="button" data-id="${esc(b.id)}">${esc(b.titre)}</button><span class="sous">${esc(b.serie)}${esc(numero(b))} <span class="nowrap"><span class="badge">${esc(b.version)}</span></span></span></div>
          <div class="ex-droite"><span class="ex-valeur${v == null ? ' nul' : ''}" title="Valeur estimée">${v == null ? 'sans cote' : fmt(v)}</span></div></div>
        <div class="ex-regl">
          <div class="ex-etats" role="group" aria-label="État : ${nom}">${ETATS.map((x) => `<button type="button" data-ex-etat="${esc(b.id)}" data-e="${x.k}" aria-pressed="${x.k === c.etat}" title="${x.long}" aria-label="${x.long} : ${nom}">${ABREGE[x.k]}</button>`).join('')}</div>
          <div class="ex-qte" role="group" aria-label="Exemplaires : ${nom}"><button type="button" data-ex-qte="${esc(b.id)}" data-delta="-1" aria-label="Un exemplaire de moins : ${nom}"${c.qte <= 1 ? ' disabled' : ''}>−</button><output aria-live="polite">${c.qte}</output><button type="button" data-ex-qte="${esc(b.id)}" data-delta="1" aria-label="Un exemplaire de plus : ${nom}"${c.qte >= 99 ? ' disabled' : ''}>+</button></div>
          <button type="button" class="ex-vendre${c.vendre ? ' actif' : ''}" data-ex-vendre="${esc(b.id)}" aria-pressed="${!!c.vendre}" title="${c.vendre ? 'Dans la liste à vendre : retirer' : 'Mettre dans la liste à vendre'}" aria-label="${c.vendre ? 'Retirer de la liste à vendre' : 'Mettre à vendre'} : ${nom}"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="10" cy="12" r="7"/><path d="M10 12h12M19 9l3 3-3 3"/></svg><span>À vendre</span></button>
        </div></li>`;
    }).join('');
    return { html, reste: triees.length - vus.length, nb: triees.length, ex: triees.reduce((t, x) => t + x.c.qte, 0), valeur: triees.reduce((t, x) => t + (valeurLigne(x.b, x.c) || 0), 0) };
  }
  const texteFiltre = (lst, bl) => (!lst.nb ? (filtresActifs() ? 'Aucun exemplaire ne correspond à ces filtres.' : 'Tous vos livres sont dans la liste à vendre, plus bas.')
    : `${lst.ex} livre${lst.ex > 1 ? 's' : ''}${filtresActifs() ? ` sur ${bl.exemplaires}` : ''} · ${filtresActifs() ? 'valeur de cette sélection' : 'valeur'} : ${fmtE(lst.valeur)}`);
  const boutonPlus = (reste) => (reste > 0 ? `<button type="button" class="plus" id="coll-plus">Voir ${Math.min(reste, 30)} exemplaires de plus (${reste} restants)</button>` : '');

  // Séries de la collection proposées : celles de l'éditeur choisi (toutes si aucun)
  function optsSerieColl(bl) {
    const m = new Map();
    bl.lignes.forEach(({ b, c }) => { if (!FC.editeur || b.editeur === FC.editeur) m.set(b.serie, (m.get(b.serie) || 0) + c.qte); });
    return '<option value="">Toutes les séries</option>' + [...m].sort((x, y) => x[0].localeCompare(y[0], 'fr'))
      .map(([k, n]) => `<option value="${esc(k)}"${k === FC.serie ? ' selected' : ''}>${esc(k)} (${n})</option>`).join('');
  }

  const nbFiltresPlus = () => [FC.editeur, FC.serie, FC.version, FC.etat, FC.cote, FC.pmin !== '' || FC.pmax !== ''].filter(Boolean).length;
  const titreFiltresColl = () => { const n = nbFiltresPlus(); return `Filtres et tri${n ? ` (${n})` : ''}`; };
  function barreFiltres(bl) {
    if (bl.lignes.length < 2) return '';
    const compte = (cle) => { const m = new Map(); bl.lignes.forEach(({ b, c }) => { const k = cle(b, c); if (k) m.set(k, (m.get(k) || 0) + c.qte); }); return [...m].sort((x, y) => String(x[0]).localeCompare(String(y[0]), 'fr', { numeric: true })); };
    const opts = (liste, val, tous) => `<option value="">${tous}</option>` + liste.map(([k, n]) => `<option value="${esc(k)}"${k === val ? ' selected' : ''}>${esc(k)} (${n})</option>`).join('');
    const nbEtat = (k) => bl.lignes.filter((x) => x.c.etat === k).reduce((t, x) => t + x.c.qte, 0);
    const champ = (id, nom, html) => `<label for="${id}">${nom}${html}</label>`;
    const ouvert = window.matchMedia('(min-width: 900px)').matches || nbFiltresPlus() > 0;     // replié sur téléphone tant qu'aucun filtre n'est choisi
    return `<div class="coll-filtres" role="group" aria-label="Filtrer et trier vos exemplaires">
      ${champ('cf-q', 'Filtrer mes exemplaires', `<input type="search" id="cf-q" value="${esc(FC.q)}" placeholder="Titre, auteur ou ISBN" autocomplete="off">`)}
      <details class="cf-plus" id="cf-plus"${ouvert ? ' open' : ''}><summary id="cf-resume">${titreFiltresColl()}</summary><div class="cf-plus-grille">
      ${champ('cf-editeur', 'Éditeur', `<select id="cf-editeur">${opts(compte((b) => b.editeur), FC.editeur, 'Tous les éditeurs')}</select>`)}
      ${champ('cf-serie', 'Série (collection)', `<select id="cf-serie">${optsSerieColl(bl)}</select>`)}
      ${champ('cf-version', 'Édition', `<select id="cf-version">${opts(compte((b) => b.version), FC.version, 'Toutes')}</select>`)}
      ${champ('cf-etat', 'État', `<select id="cf-etat"><option value="">Tous les états</option>${ETATS.map((x) => `<option value="${x.k}"${x.k === FC.etat ? ' selected' : ''}>${esc(x.nom || x.court)} (${nbEtat(x.k)})</option>`).join('')}</select>`)}
      ${champ('cf-cote', 'Cote', `<select id="cf-cote"><option value="">Toutes</option><option value="avec"${FC.cote === 'avec' ? ' selected' : ''}>Avec cote</option><option value="sans"${FC.cote === 'sans' ? ' selected' : ''}>Sans cote</option></select>`)}
      ${champ('cf-tri', 'Trier par', `<select id="cf-tri">${Object.entries(TRIS).map(([k, [nom]]) => `<option value="${k}"${k === FC.tri ? ' selected' : ''}>${nom}</option>`).join('')}</select>`)}
      </div></details>
      <button type="button" class="bouton bouton-clair" id="cf-raz"${filtresActifs() ? '' : ' hidden'}>Réinitialiser</button></div>`;
  }

  // Répartition de la valeur : chaque exemplaire compte pour une unité, au prix de son état ; une barre cliquée filtre la liste
  function afficherHistoColl(bl) {
    const valeursColl = [];
    bl.lignes.forEach(({ b, c }) => { if (b.prix[c.etat] != null) for (let i = 0; i < c.qte; i += 1) valeursColl.push(b.prix[c.etat]); });
    const okH = histogramme({ zone: $('#coll-histo'), legende: $('#coll-histo-legende'), note: $('#coll-histo-note'), table: $('#coll-histo-table'),
      valeurs: valeursColl, etat: 'l\'état de chaque exemplaire', nom: { s: 'exemplaire', p: 'exemplaires' }, choix: true, sel: { mini: '', maxi: '' }, vide: 'Aucun exemplaire n\'a de cote pour l\'instant.' });
    $('#coll-histo-chiffres').hidden = !okH;
  }

  function majListe() {
    const bl = bilan(), lst = listeExemplaires(bl);
    $('#coll-lignes').innerHTML = lst.html;
    $('#coll-filtre-compte').textContent = texteFiltre(lst, bl);
    $('#coll-plus-zone').innerHTML = boutonPlus(lst.reste);
    if ($('#cf-raz')) $('#cf-raz').hidden = !filtresActifs();
    if ($('#cf-resume')) $('#cf-resume').textContent = titreFiltresColl();
  }

  function brancherFiltresColl() {
    const lie = (id, cle, evt) => { const el = $(id); if (el) el.addEventListener(evt, () => { FC[cle] = el.value; limiteColl = 30; majListe(); }); };
    lie('#cf-q', 'q', 'input');
    [['#cf-serie', 'serie'], ['#cf-editeur', 'editeur'], ['#cf-version', 'version'], ['#cf-etat', 'etat'], ['#cf-cote', 'cote'], ['#cf-tri', 'tri']].forEach(([id, cle]) => lie(id, cle, 'change'));
    const hz = $('#coll-histo');
    if (hz) {
      const choisir = (el) => {
        const deja = FC.pmin === el.dataset.mini && FC.pmax === el.dataset.maxi;
        FC = { ...FC0, pmin: el.dataset.mini, pmax: el.dataset.maxi }; limiteColl = 30; CTAB = 'livres'; afficherCollection(); ouvrirOnglet('livres', { aller: true });
        const h = $('#titre-exemplaires'); if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); }
      };
      hz.addEventListener('click', (e) => { const el = e.target.closest('.h-clic'); if (el) choisir(el); });
      hz.addEventListener('keydown', (e) => { if ((e.key === 'Enter' || e.key === ' ') && e.target.classList.contains('h-clic')) { e.preventDefault(); choisir(e.target); } });
    }
    const ed = $('#cf-editeur');
    if (ed) ed.addEventListener('change', () => {          // la série choisie reste si elle appartient à cet éditeur, sinon elle est retirée
      const bl = bilan();
      if (FC.serie && !bl.lignes.some(({ b }) => (!FC.editeur || b.editeur === FC.editeur) && b.serie === FC.serie)) FC.serie = '';
      $('#cf-serie').innerHTML = optsSerieColl(bl); majListe();
    });
    const raz = $('#cf-raz');
    if (raz) raz.addEventListener('click', () => { FC = { ...FC0 }; limiteColl = 30; afficherCollection(); });
  }

  // Livres recherchés : la liste ne garde que ceux qui ne sont pas (encore) dans la collection
  const lienATrouver = () => {
    const nb = Object.keys(SOUH).filter((id) => !COLL[id] && livreDe(id)).length;
    return nb ? `<p class="sous lien-a-trouver"><a href="#titre-a-trouver">À trouver : ${nb} livre${nb > 1 ? 's' : ''} ↓</a></p>` : '';
  };
  function htmlATrouver() {
    const lignes = Object.keys(SOUH).filter((id) => !COLL[id]).map(livreDe).filter(Boolean);
    if (!lignes.length) return '';
    return `<h3 id="titre-a-trouver">À trouver <span class="sous">(${lignes.length})</span></h3>
      <ul class="a-trouver">${lignes.map((b) => `<li data-souhait="${esc(b.id)}">
        <div class="l-livre">${b.couverture ? `<img src="${esc(racine(b.couverture))}" alt="" width="40" height="56" loading="lazy" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(b)}
          <div><button type="button" data-id="${esc(b.id)}">${esc(b.titre)}</button><span class="sous sur-ligne">${esc(b.serie)}${esc(numero(b))} <span class="nowrap"><span class="badge">${esc(b.version)}</span></span></span></div></div>
        <button type="button" class="retirer" data-souhait-retirer="${esc(b.id)}" aria-label="Retirer ${esc(b.titre)}, édition ${esc(b.version)}, de la liste à trouver">Retirer</button></li>`).join('')}</ul>`;
  }

  // Exemplaires de la collection marqués « à vendre » : isolés dans leur propre liste, hors de « Vos exemplaires »
  function htmlAVendre(bl) {
    const lignes = bl.lignes.filter((x) => x.c.vendre);
    if (!lignes.length) return '';
    return `<h3 id="titre-a-vendre">À vendre <span class="sous">(${lignes.length})</span></h3>
      <p class="sous">Livres à sortir de votre collection, comptés dans le total jusqu'à la vente.</p>
      <ul class="a-trouver a-vendre">${lignes.map(({ b, c }) => `<li data-vendre="${esc(b.id)}">
        <div class="l-livre">${b.couverture ? `<img src="${esc(racine(b.couverture))}" alt="" width="40" height="56" loading="lazy" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(b)}
          <div><button type="button" data-id="${esc(b.id)}">${esc(b.titre)}</button><span class="sous sur-ligne">${esc(b.serie)}${esc(numero(b))} <span class="nowrap"><span class="badge">${esc(b.version)}</span></span> <span class="nb">· ${ABREGE[c.etat]}${c.qte > 1 ? ' · ' + c.qte + ' ex.' : ''}${valeurLigne(b, c) != null ? ' · ' + fmt(valeurLigne(b, c)) : ''}</span></span></div></div>
        <span class="vendre-actions"><button type="button" class="retirer" data-vendre-garder="${esc(b.id)}" title="Remettre dans ma collection" aria-label="Garder ${esc(b.titre)}, édition ${esc(b.version)}, dans ma collection">Je le garde</button>
        <button type="button" class="retirer" data-vendu="${esc(b.id)}" aria-label="Vendu : retirer ${esc(b.titre)}, édition ${esc(b.version)}, de ma collection">Vendu</button></span></li>`).join('')}</ul>`;
  }

  // Page « Ma collection » : recherche d'un livre de la base pour l'ajouter d'un geste (titre, série, auteur ou ISBN)
  let AJ_Q = '', AJ_N = 30;                                  // résultats montrés dans « Ajouter un titre » : 30, puis 30 de plus à chaque demande
  function rendreAjoutColl() {
    const liste = $('#ca-res');
    if (!liste) return;
    const q = norm(AJ_Q).trim();
    const statut = $('#ca-statut');
    if (q.length < 2) { liste.innerHTML = ''; if (statut) statut.textContent = ''; return; }
    const isbn = versIsbn13(AJ_Q);
    const mots = q.split(/\s+/);
    const trouves = DATA.filter((b) => (isbn ? b.isbn13 === isbn : mots.every((m) => b._txt.includes(m))))
      .sort((x, y) => x.serie.localeCompare(y.serie, 'fr') || (parseInt(x.numero, 10) || 0) - (parseInt(y.numero, 10) || 0) || x.version_n - y.version_n);
    liste.innerHTML = trouves.slice(0, AJ_N).map((b) => {
      const poss = COLL[b.id];
      return `<li class="ca-ligne"><span class="ca-couv">${b.couverture ? `<img src="${esc(racine(b.couverture))}" alt="" width="44" height="62" loading="lazy" decoding="async">` : ''}</span>
        <span class="ca-texte"><strong>${esc(b.titre)}</strong><span class="sous">${esc(b.serie)}${esc(numero(b))} <span class="nowrap"><span class="badge">${esc(b.version)}</span></span>${b.annee ? ` · ${b.annee}` : ''}</span></span>
        <span class="ca-etats" role="group" aria-label="Ajouter à ma collection : ${esc(b.titre)}, édition ${esc(b.version)}">${ETATS.map((x) =>
          `<button type="button" data-etat-possede="${esc(b.id)}" data-e="${x.k}" aria-pressed="${!!poss && poss.etat === x.k}" title="${poss && poss.etat === x.k ? 'Dans ma collection en ' + x.long.toLowerCase() + ' : retirer' : 'Ajouter en ' + x.long.toLowerCase()}" aria-label="${poss && poss.etat === x.k ? 'Retirer de ma collection' : 'Ajouter en ' + x.long.toLowerCase()} : ${esc(b.titre)}, édition ${esc(b.version)}">${ABREGE[x.k]}</button>`).join('')}</span></li>`;
    }).join('') + (trouves.length > AJ_N ? `<li class="sous">${AJ_N} livres sur ${trouves.length}. <button type="button" class="bouton-lien" data-aj-plus>Afficher les ${Math.min(30, trouves.length - AJ_N)} suivants</button></li>` : '') +
      (!trouves.length ? '<li class="sous">Aucun livre trouvé. <button type="button" class="lien" data-demande-coll>Demander son ajout au guide</button></li>' : '');
    if (statut) statut.textContent = trouves.length ? `${trouves.length} livre${trouves.length > 1 ? 's' : ''} trouvé${trouves.length > 1 ? 's' : ''}.` : 'Aucun livre trouvé.';
  }
  // « Retiré. Annuler » : quelques secondes pour revenir sur un retrait fait par erreur
  let minuteurAnnuler = null;
  function annulerRetrait(b, id, ancien, libelle) {
    let z = $('#annuler-retrait');
    if (!z) { z = document.createElement('div'); z.id = 'annuler-retrait'; z.className = 'annuler-retrait'; z.setAttribute('role', 'status'); document.body.appendChild(z); }
    z.innerHTML = `<span>${esc(b ? b.titre : 'Livre')} ${libelle || 'retiré'}.</span><button type="button" class="bouton-lien">Annuler</button>`;
    z.hidden = false;
    clearTimeout(minuteurAnnuler);
    minuteurAnnuler = setTimeout(() => { z.hidden = true; }, 10000);
    z.querySelector('button').onclick = () => { COLL[id] = ancien; sauverColl(); afficher(); z.hidden = true; clearTimeout(minuteurAnnuler); };
  }
  // Ajout en série par scan (scan.js) : un livre est reconnu par son ISBN, ajouté dans l'état choisi, et peut être annulé
  window.AjoutRapide = {
    garde: (suite) => garde(suite),
    trouver: (isbn) => DATA.find((b) => b.isbn13 === isbn) || null,
    etat: (id) => (COLL[id] ? COLL[id].etat : null),
    ajouter(id, etat) {
      const b = livreDe(id);
      if (!b) return;
      COLL[id] = { etat, qte: (COLL[id] && COLL[id].qte) || 1, ...gv(COLL[id]) };
      sauverColl(); afficher();
      annonce(`${b.titre} : en ${etatDe(etat).long.toLowerCase()} dans votre collection.`);
    },
    retirer(id) { delete COLL[id]; sauverColl(); afficher(); },
    titre: (b) => `${b.titre} (${b.version})`,
    ouvrir: (id) => ouvrirFiche(id),
  };
  function retourAjoutColl(id) {
    const b = livreDe(id), champ = $('#ca-q'), ok = $('#ca-ok');
    if (!champ) return;
    if (ok) { ok.textContent = `✓ ${b.titre} (${b.version}) ajouté en ${etatDe(COLL[id].etat).long.toLowerCase()}.`; ok.hidden = false; }
    AJ_Q = ''; champ.value = ''; rendreAjoutColl();
    $('.ajout-coll').scrollIntoView({ behavior: 'auto', block: 'start' });
    champ.focus({ preventScroll: true });
  }
  document.addEventListener('input', (e) => { if (e.target.id === 'ca-q') { AJ_Q = e.target.value; AJ_N = 30; const ok = $('#ca-ok'); if (ok) ok.hidden = true; rendreAjoutColl(); } });
  document.addEventListener('click', (e) => { if (e.target.closest('[data-aj-plus]')) { AJ_N += 30; rendreAjoutColl(); } });
  document.addEventListener('click', (e) => { if (e.target.closest('[data-demande-coll]') && window.Compte) window.Compte.demanderLivre(AJ_Q); });

  // Tendance de la valeur de la collection : mêmes livres, mêmes états, cotes publiées à la première et à la dernière date de l'historique
  function flecheValeur(bl) {
    if (!HIST || !HIST.dates || HIST.dates.length < 2) return '';
    const { tot } = serieValeur(bl), debut = tot[0], fin = tot[tot.length - 1];
    if (!(debut > 0)) return '';
    const v = fin / debut - 1;
    if (Math.abs(v) < 0.005) return '';                                  // trop faible pour dire quoi que ce soit : pas de flèche
    const dir = v > 0 ? 'hausse' : 'baisse', pct = (Math.round(Math.abs(v) * 1000) / 10).toString().replace('.', ',');
    const depuis = new Date(HIST.dates[0] + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' });
    const txt = `Valeur de la collection en ${dir} de ${pct} % depuis le ${depuis}`;
    return ` <span class="fleche fleche-${dir}" role="img" aria-label="${txt}" title="${txt}">${v > 0 ? '▲' : '▼'}</span>`;
  }
  // Médiane de la valeur d'un exemplaire (chaque exemplaire compte pour une unité, au prix de son état)
  function medianeEx(bl) {
    const u = bl.lignes.flatMap(({ b, c }) => { const v = valeurLigne(b, c); return v == null ? [] : Array(c.qte).fill(v / c.qte); }).sort((x, y) => x - y);
    if (!u.length) return 0;
    return u.length % 2 ? u[(u.length - 1) / 2] : (u[u.length / 2 - 1] + u[u.length / 2]) / 2;
  }
  // Répartition de la valeur par segment : un seul sélecteur, des barres ; une barre cliquée filtre « Mes livres » quand ce segment sert de filtre
  const SEGMENTS = [
    ['serie', 'Série', (b) => b.serie || 'Sans série', 'serie'],
    ['editeur', 'Éditeur', (b) => b.editeur || 'Éditeur inconnu', 'editeur'],
    ['version', 'Édition (V1 à V5)', (b) => b.version, 'version'],
    ['decennie', 'Décennie', (b) => (b.annee ? `${Math.floor(b.annee / 10) * 10}–${Math.floor(b.annee / 10) * 10 + 9}` : 'Année inconnue'), null],
    ['etat', 'État', (b, c) => etatDe(c.etat).long, 'etat'],
    ['rarete', 'Rareté', (b) => (b.rarete ? RARETE[b.rarete.niveau] : 'Sans information'), null]];
  function barresSegment(bl) {
    const [, , clef, filtre] = SEGMENTS.find((x) => x[0] === CSEG) || SEGMENTS[0];
    const m = new Map();
    bl.lignes.forEach(({ b, c }) => {
      const k = clef(b, c), e = m.get(k) || { nom: k, val: 0, ex: 0, v: filtre === 'etat' ? c.etat : k };
      e.val += valeurLigne(b, c) || 0; e.ex += c.qte; m.set(k, e);
    });
    let L = [...m.values()].sort((x, y) => y.val - x.val);
    if (L.length > 8) { const reste = L.slice(7); L = L.slice(0, 7).concat([{ nom: 'Autres', val: reste.reduce((t, x) => t + x.val, 0), ex: reste.reduce((t, x) => t + x.ex, 0), v: null, autres: true }]); }
    const max = Math.max(...L.map((x) => x.val), 1), tot = bl.total || 1;
    return L.map((x) => {
      const pct = Math.round((100 * x.val) / tot), txt = `<span class="seg-nom">${esc(x.nom)}</span><span class="seg-fond"><i style="width:${Math.max(3, Math.round((100 * x.val) / max))}%"></i></span><span class="seg-val">${fmtE(x.val)} · ${pct} %<small> · ${x.ex} ex.</small></span>`;
      return filtre && !x.autres
        ? `<li><button type="button" class="seg-ligne seg-clic" data-seg="${filtre}" data-val="${esc(x.v)}" aria-label="${esc(x.nom)} : ${fmtE(x.val)}, ${pct} % de la valeur, ${x.ex} exemplaire${x.ex > 1 ? 's' : ''}. Afficher ces livres.">${txt}</button></li>`
        : `<li><div class="seg-ligne" role="group" aria-label="${esc(x.nom)} : ${fmtE(x.val)}, ${pct} % de la valeur, ${x.ex} exemplaire${x.ex > 1 ? 's' : ''}">${txt}</div></li>`;
    }).join('');
  }
  function pieceHtml({ b, c }) {
    return `<button type="button" class="piece" data-id="${esc(b.id)}" aria-label="${esc(b.titre)}, édition ${esc(b.version)}, ${fmt(b.prix[c.etat])}">
      ${b.couverture ? `<img src="${esc(racine(b.couverture))}" alt="" width="88" height="124" loading="lazy" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(b)}
      <b>${esc(b.titre)}</b><span>${esc(b.version)} · ${esc(etatDe(c.etat).court)}</span><span class="p">${fmt(b.prix[c.etat])}</span>${pastilleRarete(b)}</button>`;
  }
  // Historique : valeur de la collection à chaque date de relevé, pour les livres dont la cote est connue à toutes les dates (mêmes livres, mêmes états)
  // Les cinq livres dont la valeur (cote × exemplaires) a le plus monté ou le plus baissé depuis le premier relevé
  function listeMouv(titre, liste, dir) {
    const signe = dir === 'hausse' ? '+' : '−', fl = dir === 'hausse' ? '▲' : '▼';
    return `<section class="hc-liste"><h4>${titre}</h4>` + (liste.length ? `<ol>${liste.map(({ b, c, d, f, delta, pct }) => `<li><button type="button" class="hc-livre" data-id="${esc(b.id)}" aria-label="Ouvrir la fiche : ${esc(b.titre)}, édition ${esc(b.version)}"><span class="hc-titre">${esc(b.titre)}</span><span class="hc-sous">${esc(b.serie)} · ${esc(b.version)} · ${ABREGE[c.etat]}${c.qte > 1 ? ' · ' + c.qte + ' ex.' : ''}</span></button>` +
      `<span class="hc-var fleche-${dir}"><b>${fl} ${signe}${fmt(Math.abs(delta))}</b><small>${fmt(d)} → ${fmt(f)} · ${signe}${(Math.round(Math.abs(pct) * 1000) / 10).toString().replace('.', ',')} %</small></span></li>`).join('')}</ol>` : '<p class="sous">Aucun livre dans ce cas.</p>') + '</section>';
  }
  // Valeur de la collection à chaque date de relevé : même calcul pour la courbe, les listes et la flèche de tendance
  function serieValeur(bl) {
    const n = HIST.dates.length, tot = new Array(n).fill(0), mouv = [];
    let suivis = 0;
    bl.lignes.forEach(({ b, c }) => {
      const cur = b.prix[c.etat];
      if (cur == null || cur <= 0) return;                                  // sans cote : hors du total, comme dans l'estimation
      const a = HIST.cotes[`${b.id}|${c.etat}`] || [];
      const sr = []; let der = null;
      for (let i = 0; i < n; i += 1) { if (a[i] != null && a[i] > 0) der = a[i]; sr.push(der); }       // une date sans cote reprend la dernière connue
      const premier = sr.find((x) => x != null) ?? cur;
      for (let i = 0; i < n; i += 1) if (sr[i] == null) sr[i] = premier;      // avant sa première cote, un livre garde cette première cote
      sr[n - 1] = cur;                                                      // le dernier point est la cote du jour : le graphique rejoint toujours le total de l'estimation
      suivis += c.qte;
      sr.forEach((x, k) => { tot[k] += x * c.qte; });
      mouv.push({ b, c, d: sr[0], f: sr[n - 1], delta: (sr[n - 1] - sr[0]) * c.qte, pct: sr[n - 1] / sr[0] - 1 });
    });
    return { n, tot, mouv, suivis };
  }
  function historiquePane(bl) {
    if (!HIST || !HIST.dates || HIST.dates.length < 2) return '<p class="vide-global">L\'historique se construit avec les relevés de prix : revenez dans quelques jours.</p>';
    const { n, tot, mouv, suivis } = serieValeur(bl);
    if (!suivis) return '<p class="vide-global">Aucun de vos livres n\'a encore de cote : l\'historique apparaîtra avec les prochains relevés.</p>';
    const jour = (d, long) => new Date(d + 'T12:00:00').toLocaleDateString('fr-FR', long ? { day: 'numeric', month: 'long' } : { day: 'numeric', month: 'numeric' });
    const mini = Math.min(...tot), maxi = Math.max(...tot), marge = Math.max((maxi - mini) * 0.2, maxi * 0.02);
    const bas = mini - marge, haut = maxi + marge, W = 640, H = 240, gx = 78, gd = 22, gh = 16, gb = 34;
    const X = (i) => gx + (i * (W - gx - gd)) / (n - 1), Y = (v) => gh + ((haut - v) / (haut - bas)) * (H - gh - gb);
    const pts = tot.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ');
    const graduations = [bas + marge, (mini + maxi) / 2, maxi].map((v) => `<g><line x1="${gx}" x2="${W - gd}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" class="hc-grille"/><text x="${gx - 6}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end">${Math.round(v)} €</text></g>`).join('');
    const pas = Math.max(1, Math.ceil(n / 6));
    const dates = HIST.dates.map((d, i) => ((i % pas === 0 && n - 1 - i >= Math.max(2, pas)) || i === n - 1) ? `<text x="${X(i).toFixed(1)}" y="${H - 12}" text-anchor="${i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'}">${jour(d)}</text>` : '').join('');
    const points = tot.map((v, i) => `<circle cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="3.5"/>`).join('');
    const v0 = tot[0], v1 = tot[n - 1], ev = v0 > 0 ? v1 / v0 - 1 : 0;
    const pct = (Math.round(Math.abs(ev) * 1000) / 10).toString().replace('.', ',');
    const phrase = Math.abs(ev) < 0.005 ? `Valeur stable depuis le ${jour(HIST.dates[0], true)} : ${fmtE(v1)}.` : `De ${fmtE(v0)} le ${jour(HIST.dates[0], true)} à ${fmtE(v1)} le ${jour(HIST.dates[n - 1], true)} (${ev > 0 ? 'hausse' : 'baisse'} de ${pct} %).`;
    const lignes = HIST.dates.map((d, i) => `<tr><td>${jour(d, true)}</td><td class="num">${fmtE(tot[i])}</td><td class="num">${i ? `${tot[i] - tot[i - 1] >= 0 ? '+' : '−'}${fmtE(Math.abs(tot[i] - tot[i - 1]))}` : '—'}</td></tr>`).join('');
    const total = bl.exemplaires, dir = Math.abs(ev) < 0.005 ? '' : ev > 0 ? 'hausse' : 'baisse';
    const cle = (lib, val, cls = '') => `<li class="${cls}"><span class="cle-lib">${lib}</span><b>${val}</b></li>`;
    return `<h3 id="titre-historique">Valeur de ma collection dans le temps</h3>
      <p class="hc-phrase" role="status">${phrase}</p>
      <div class="hc-grille">
        <figure class="hc-fig"><svg viewBox="0 0 ${W} ${H}" class="hc-svg" role="img" aria-label="Courbe de la valeur de la collection du ${jour(HIST.dates[0], true)} au ${jour(HIST.dates[n - 1], true)}. ${phrase}">${graduations}<polyline points="${pts}" class="hc-ligne"/>${points}${dates}</svg></figure>
        <ul class="coll-cles hc-cles" aria-label="Repères">${cle('Au ' + jour(HIST.dates[0], true), fmtE(v0))}${cle('Au ' + jour(HIST.dates[n - 1], true), fmtE(v1))}${cle('Évolution', dir ? `<span class="fleche-${dir}">${ev > 0 ? '▲ +' : '▼ −'}${pct} %</span>` : '0 %')}</ul>
      </div>
      <p class="sous hc-note">Mêmes livres, mêmes états à chaque date : seule la cote change.${suivis < total ? ` ${total - suivis} exemplaire${total - suivis > 1 ? 's' : ''} sans cote ne ${total - suivis > 1 ? 'sont' : 'est'} pas compté${total - suivis > 1 ? 's' : ''}.` : ''} Un livre qui n'avait pas encore de cote garde sa première cote connue.</p>
      <div class="hc-mouv">${listeMouv('Ont le plus progressé', mouv.filter((x) => x.delta > 0.004).sort((x, y) => y.delta - x.delta).slice(0, 5), 'hausse')}${listeMouv('Ont le plus reculé', mouv.filter((x) => x.delta < -0.004).sort((x, y) => x.delta - y.delta).slice(0, 5), 'baisse')}</div>`;
  }
  function analysePane(bl) {
    const cotes = bl.lignes.filter((x) => x.b.prix[x.c.etat] != null);
    const chers = [...cotes].sort((x, y) => y.b.prix[y.c.etat] - x.b.prix[x.c.etat]).slice(0, 5);
    const rang = { tres_rare: 0, rare: 1 };
    const rares = bl.lignes.filter((x) => x.b.rarete && rang[x.b.rarete.niveau] !== undefined && x.b.prix[x.c.etat] != null)
      .sort((x, y) => rang[x.b.rarete.niveau] - rang[y.b.rarete.niveau] || y.b.prix[y.c.etat] - x.b.prix[x.c.etat]).slice(0, 5);
    const sansInfo = bl.lignes.filter((x) => !x.b.rarete).length;
    const recent = bl.lignes.reduce((t, x) => t + (estActuel(infoPrix(x.b, x.c.etat)) ? (valeurLigne(x.b, x.c) || 0) : 0), 0);
    return `<h3>Répartition de la valeur</h3>
      <div class="seg-choix"><label for="coll-segment">Répartir par</label><select id="coll-segment">${SEGMENTS.map(([k, nom]) => `<option value="${k}"${k === CSEG ? ' selected' : ''}>${nom}</option>`).join('')}</select></div>
      <ul class="seg-liste" id="coll-seg">${barresSegment(bl)}</ul>
      <h3 id="titre-coll-histo">Où se situe la valeur de vos exemplaires</h3>
      <p class="sous" id="coll-histo-note"></p>
      <div id="coll-histo" class="histo"></div>
      <div class="legende" id="coll-histo-legende"></div>
      <details class="chiffres" id="coll-histo-chiffres"><summary>Voir les chiffres</summary><div id="coll-histo-table"></div></details>
      <div class="coll-pieces">
        <div><h3>Les plus chères</h3>${chers.length ? `<div class="pieces">${chers.map(pieceHtml).join('')}</div>` : '<p class="sous">Aucune cote disponible pour l\'instant.</p>'}</div>
        <div><h3>Les plus rares</h3>${rares.length ? `<div class="pieces">${rares.map(pieceHtml).join('')}</div>` : '<p class="sous">Aucune de vos pièces n\'est rare ou très rare.</p>'}
          ${sansInfo ? `<p class="sous">${sansInfo} édition${sansInfo > 1 ? 's' : ''} sans information de rareté : ${sansInfo > 1 ? 'elles ne sont' : 'elle n\'est'} pas classée${sansInfo > 1 ? 's' : ''}.</p>` : ''}</div>
      </div>
      <p class="sous">${bl.total ? `${Math.round((100 * recent) / bl.total)} % de la valeur repose sur des prix récents ; le reste, sur d'anciennes archives (un ordre de grandeur).` : ''}</p>`;
  }

  /* ---------- Onglets de « Ma collection » : Mes livres, Analyse, À vendre, À trouver ---------- */
  // Pictogrammes de la barre d'onglets de la collection (décoratifs : le libellé reste lu)
  const pict = (d) => `<svg class="onglet-ico" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const ICONES_ONGLET = {
    livres: pict('<path d="M5 4h10a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3V4z"/><path d="M8 17h10"/>'),
    analyse: pict('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'),
    historique: pict('<path d="M3 17l5-6 4 3 8-9"/><path d="M15 5h5v5"/>'),
    vendre: pict('<circle cx="10" cy="12" r="7"/><path d="M10 12h12M19 9l3 3-3 3"/>'),
    trouver: pict('<circle cx="14" cy="12" r="7"/><path d="M2 12h9M8 9l3 3-3 3"/>'),
    gerer: pict('<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>'),
  };
  const ONGLETS_COLL = ['livres', 'analyse', 'historique', 'vendre', 'trouver', 'gerer'];
  const ALIAS_ONGLET = { livres: 'livres', analyse: 'analyse', historique: 'historique', gerer: 'gerer', vendre: 'vendre', trouver: 'trouver', 'titre-exemplaires': 'livres', 'titre-a-vendre': 'vendre', 'titre-a-trouver': 'trouver', 'titre-analyses': 'analyse', 'coll-analyse': 'analyse' };
  let CTAB = 'livres', CSEG = 'serie';
  (function lireOngletInitial() {
    const h = location.hash.replace('#', '');
    if (ALIAS_ONGLET[h]) { CTAB = ALIAS_ONGLET[h]; return; }
    try { const m = sessionStorage.getItem('cdh-coll-pane'); if (ONGLETS_COLL.includes(m)) CTAB = m; } catch (e) { /* sans stockage : « Mes livres » */ }
  })();
  function ouvrirOnglet(nom, { aller = false } = {}) {
    if (!ONGLETS_COLL.includes(nom) || !$('#onglet-coll-' + nom)) return;          // un onglet réservé aux administrateurs n'existe pas pour les autres
    CTAB = nom;
    try { sessionStorage.setItem('cdh-coll-pane', nom); } catch (e) { /* sans effet */ }
    if ($('#collection') && /^(#(livres|analyse|vendre|trouver|titre-[a-z-]+|coll-analyse)?)?$/.test(location.hash)) history.replaceState(null, '', '#' + nom);
    ONGLETS_COLL.forEach((k) => {
      const b = $('#onglet-coll-' + k), pan = $('#pane-coll-' + k);
      if (b) { b.setAttribute('aria-selected', String(k === nom)); b.tabIndex = k === nom ? 0 : -1; }
      if (pan) pan.hidden = k !== nom;
    });
    if (aller) { const t = $('#coll-nav'); if (t) t.scrollIntoView({ behavior: 'auto', block: 'start' }); }
  }
  document.addEventListener('click', (e) => { const b = e.target.closest('[data-onglet]'); if (b && $('#collection')) ouvrirOnglet(b.dataset.onglet, { aller: true }); });
  document.addEventListener('keydown', (e) => {
    const t = e.target.closest && e.target.closest('#coll-nav [role="tab"]');
    if (!t) return;
    const dispo = ONGLETS_COLL.filter((k) => $('#onglet-coll-' + k)), i = dispo.indexOf(t.dataset.onglet);
    const j = e.key === 'ArrowRight' ? (i + 1) % dispo.length : e.key === 'ArrowLeft' ? (i + dispo.length - 1) % dispo.length : e.key === 'Home' ? 0 : e.key === 'End' ? dispo.length - 1 : -1;
    if (j < 0) return;
    e.preventDefault(); ouvrirOnglet(dispo[j]); $('#onglet-coll-' + dispo[j]).focus();
  });
  window.addEventListener('hashchange', () => { const h = location.hash.replace('#', ''); if (ALIAS_ONGLET[h] && $('#collection')) { ouvrirOnglet(ALIAS_ONGLET[h], { aller: true }); } });
  document.addEventListener('change', (e) => { if (e.target.id === 'coll-segment') { CSEG = e.target.value; $('#coll-seg').innerHTML = barresSegment(bilan()); } });
  // Une barre de répartition ouvre « Mes livres » filtré sur ce segment
  document.addEventListener('click', (e) => {
    const l = e.target.closest('.seg-clic'); if (!l) return;
    FC = { ...FC0, [l.dataset.seg]: l.dataset.val }; limiteColl = 30; CTAB = 'livres'; afficherCollection(); ouvrirOnglet('livres', { aller: true });
    const h = $('#titre-exemplaires'); if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); }
  });

  // « Gérer ma collection » : importer, exporter, effacer. Toujours affiché, même quand la collection est vide (c'est là qu'on la retrouve).
  const blocGerer = () => `<div class="coll-gerer"><h3>Gérer ma collection</h3>
        <div class="gerer-grille">
          <button type="button" class="gerer-tuile" data-parcours><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2"/></svg><span><b>Compléter pas à pas</b><small>Indiquer les séries que vous possédez</small></span></button>
          <button type="button" class="gerer-tuile" id="imp-ouvrir"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 19h16"/></svg><span><b>Importer un fichier</b><small>JSON, CSV ou liste d'ISBN</small></span></button>
          <button type="button" class="gerer-tuile" data-importer-liste aria-expanded="false" aria-controls="importer"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 4h14v16H5z"/><path d="M8 9h8M8 13h8M8 17h5"/></svg><span><b>Importer une liste</b><small>Coller des ISBN</small></span></button>
          <button type="button" class="gerer-tuile" data-exporter aria-expanded="false" aria-controls="exporter-choix"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21V9M7 14l5-5 5 5"/><path d="M4 5h16"/></svg><span><b>Exporter ma collection</b><small>Fichier JSON ou tableur</small></span></button>
        </div>
        ${window.Cloud && window.Cloud.lie() ? '<p class="coll-versions"><button type="button" class="bouton-lien" data-compte="versions">Retrouver une version précédente de ma collection (Google Drive)</button></p>' : ''}
        <div class="exporter-choix" id="exporter-choix" hidden><button type="button" class="bouton bouton-clair" id="exp-json">Fichier JSON</button><button type="button" class="bouton bouton-clair" id="exp-csv">Fichier CSV (tableur)</button></div>
        <div class="gerer-danger" role="group" aria-label="Danger zone"><span class="danger-texte"><b class="danger-titre">Danger zone</b>Effacer toute la collection, y compris dans votre compte. Définitif : pensez à l'exporter avant.</span><button type="button" class="bouton bouton-danger" id="coll-vider">Tout effacer</button></div>
      </div>`;
  function afficherCollection() {
    rendreAjoutColl();
    const bl = bilan();
    const n = bl.exemplaires, nPastille = cotesMasquees() ? 0 : n;          // sans compte, la copie gardée sur l'appareil n'est pas affichée
    ['#nb-coll', '#nb-coll-bas'].forEach((sel) => {
      $(sel).textContent = nPastille ? String(nPastille) : '';
      $(sel).setAttribute('aria-label', nPastille ? `${nPastille} exemplaire${nPastille > 1 ? 's' : ''}` : '');
    });
    if ($('#nb-coll-seg')) $('#nb-coll-seg').textContent = nPastille ? `(${nPastille})` : '';
    if ($('#seg-cherche')) {
      const nbS = Object.keys(SOUH).filter((id) => !COLL[id] && livreDe(id)).length;
      $('#seg-cherche').hidden = !nbS && !S.cherche;
      $('#nb-cherche-seg').textContent = nbS ? `(${nbS})` : '';
    }
    if ($('#seg-vendre')) {
      const nbV = Object.keys(COLL).filter((id) => COLL[id].vendre && livreDe(id)).length;
      $('#seg-vendre').hidden = !nbV && !S.avendre && !Object.keys(COLL).length;      // visible dès qu'on possède un livre : on peut y arriver sans rien y avoir mis
      $('#nb-vendre-seg').textContent = nbV ? `(${nbV})` : '';
    }
    if ($('#hero-coll')) {              // accueil : la carte « Ma collection » a trois états (visiteur, connecté sans livre, avec collection)
      const visiteurAccueil = sansCompte();
      const cha = $('#hero-chapeau');
      if (cha) cha.textContent = visiteurAccueil ? 'Retrouvez la cote de chaque édition des livres-jeux.' : n ? 'Votre collection est une aventure. Complétez-la.' : 'Votre collection est une aventure. Commencez-la.';
      let corps;
      if (visiteurAccueil) {
        corps = `<p class="gros">Gardez la trace de vos livres</p>
          <p class="texte">Avec un compte Google, gratuit :</p>
          <ul class="avantages"><li>Prix estimés</li><li>Scan des codes-barres</li><li>Valeur de la collection</li><li>Doubles à vendre</li><li>Livres à trouver</li><li>Sur tous vos appareils</li></ul>
          <p class="actions"><button type="button" class="bouton" data-compte="connecter">Se connecter avec Google</button></p>`;
      } else if (!n) {
        corps = `<p class="gros">Elle est encore vide</p>
          <p class="texte">Indiquez les séries que vous possédez : le guide calcule la valeur pour vous.</p>
          <p class="actions"><button type="button" class="bouton" data-parcours id="hero-parcours">Constituer pas à pas</button></p>`;
      } else {
        const couvs = Object.keys(COLL).map((id) => livreDe(id)).filter((b) => b && b.couverture).sort((x, y) => (valeurLigne(y, COLL[y.id]) || 0) - (valeurLigne(x, COLL[x.id]) || 0)).slice(0, 4);
        const eventail = couvs.length ? `<div class="eventail" aria-hidden="true">${couvs.map((b, i) => `<img src="${esc(b.couverture)}" alt="" style="--i:${i}" width="50" height="75">`).join('')}</div>` : '';
        const pct = Math.max(2, Math.round(100 * bl.lignes.length / (META.nb_versions || 1)));
        corps = `<div class="coll-resume">${eventail}<div><p class="valeur"><span>Valeur estimée</span><b>${bl.total > 0 ? fmtE(bl.total) + flecheValeur(bl) : 'prix à venir'}</b></p>
          <p class="texte petit">${n} livre${n > 1 ? 's' : ''} · ${bl.titres} titre${bl.titres > 1 ? 's' : ''}</p></div></div>
          <div class="coll-prog"><div class="prog-barre" role="img" aria-label="${bl.lignes.length} éditions sur ${META.nb_versions}"><i style="width:${pct}%"></i></div><span>${bl.lignes.length} édition${bl.lignes.length > 1 ? 's' : ''} sur ${META.nb_versions}</span></div>
          <p class="actions"><a class="bouton" href="collection.html" id="hc-voir">Voir ma collection</a><button type="button" class="bouton bouton-clair" data-parcours id="hero-parcours">Compléter pas à pas</button></p>`;
      }
      $('#hc-corps').innerHTML = corps;
    }
    if (!$('#collection')) return;      // l'accueil n'affiche que les pastilles ; la section est sur la page collection
    const visiteur = sansCompte();       // compte demandé et pas connecté : écran d'invitation à la place de l'outil
    if ($('.ajout-coll')) $('.ajout-coll').hidden = visiteur;           // sans compte, la carte d'invitation ci-dessous dit tout : pas de second appel à se connecter
    ['#importer', '#coll-prive', '#coll-compte'].forEach((s) => { if ($(s)) $(s).hidden = visiteur; });
    $('#coll-compte').textContent = n ? `${n} livre${n > 1 ? 's' : ''} · ${bl.titres} titre${bl.titres > 1 ? 's' : ''}` : 'vide pour l\'instant';
    const comptePrevu = !!window.Compte && window.Compte.actif();
    $('#coll-prive').innerHTML = (stockageOk
      ? (comptePrevu
        ? 'Votre collection est sauvegardée dans l\'espace réservé de votre Google Drive, que seul ce site peut ouvrir ; une copie reste sur cet appareil. Exportez-la quand vous voulez : le fichier vous appartient.'
        : 'Votre collection reste dans ce navigateur, sur cet appareil : rien n\'est envoyé et aucun compte n\'est nécessaire. Exportez-la pour la sauvegarder, ou créez un lien de transfert pour la retrouver sur un autre appareil.')
      : '<strong>Le stockage local est indisponible</strong> (navigation privée ?) : votre collection sera perdue à la fermeture. Exportez-la pour la conserver.');
    const zone = $('#coll-corps');
    if (visiteur) {
      zone.innerHTML = `<div class="coll-invite">
        ${n ? `<p class="coll-reprise" role="status">Vous avez déjà <strong>${bl.titres} livre${bl.titres > 1 ? 's' : ''}</strong> sur cet appareil. Ils seront repris dans votre compte à la connexion.</p>` : ''}
        <h3>Gardez votre collection, où que vous soyez</h3>
        <ul class="coll-avantages">
          <li><b>Sauvegardée</b><span>Vos exemplaires sont enregistrés dans votre Google Drive, pas chez nous.</span></li>
          <li><b>Scannée</b><span>Scannez le code-barres des livres pour les ajouter à votre collection.</span></li>
          <li><b>Estimée</b><span>Sa valeur suit les cotes, livre par livre.</span></li>
          <li><b>Partout</b><span>Retrouvée sur tous vos appareils, sans rien recopier.</span></li>
        </ul>
        <p><button type="button" class="bouton" data-compte="connecter">Continuer avec Google</button></p>
        <p class="sous">Nous ne voyons ni votre courriel ni vos autres fichiers. Votre collection est stockée chez vous, dans votre Google Drive, et vous pouvez la supprimer à tout moment.</p>
        <p class="sous"><a href="./#recherche">Continuer sans compte : consulter l'étagère</a></p></div>`;
      return;
    }
    if (!n) {
      const imp00 = $('#importer');                       // le panneau d'import est remis à l'abri avant de redessiner
      if (imp00 && zone.contains(imp00)) $('#collection').insertBefore(imp00, $('#coll-prive'));
      zone.innerHTML = `<div class="coll-vide"><p>Constituez ici votre collection pour la suivre dans le temps.</p>
        <p>Le plus rapide : l'<strong>inventaire guidé</strong>. Vous indiquez vos séries, vos éditions, puis vous cochez vos couvertures. Vous pouvez aussi toucher <strong>C, BE ou TBE</strong> sur une jaquette de l'étagère, ou importer une liste d'ISBN ci-dessous.</p>
        <p><button type="button" class="bouton" data-parcours>Constituer ma collection pas à pas</button></p></div>${htmlATrouver()}${blocGerer()}`;
      const imp2 = $('#importer'), dang2 = $('.gerer-danger');
      if (imp2 && dang2) dang2.before(imp2);
      return;
    }
    const lst = listeExemplaires(bl);
    const plusChere = bl.lignes.map(({ b, c }) => ({ b, v: b.prix[c.etat] })).filter((x) => x.v != null).sort((x, y) => y.v - x.v)[0];
    const aVendre = bl.lignes.filter((x) => x.c.vendre), exV = aVendre.reduce((t, x) => t + x.c.qte, 0), valVendre = aVendre.reduce((t, x) => t + (valeurLigne(x.b, x.c) || 0), 0);
    const nbTrouver = Object.keys(SOUH).filter((id) => !COLL[id] && livreDe(id)).length;
    const cases = [
      ['Valeur estimée', bl.total > 0 ? fmtE(bl.total) + flecheValeur(bl) : 'à venir', aVendre.length ? `dont ${fmtE(valVendre)} à vendre` : '', 'cle-valeur'],
      ['Livres', String(bl.exemplaires), exV ? `dont ${exV} à vendre` : '', ''],
      ['Plus chère', fmtE(plusChere ? plusChere.v : 0), plusChere ? plusChere.b.titre : '', ''],
      ['Médiane', fmtE(medianeEx(bl)), 'd\'un exemplaire', ''],
      ['Plancher', fmtE(bl.bas), 'tout en convenable', ''],
      ['Plafond', fmtE(bl.haut), 'tout en très bon état', '']];
    if (CTAB === 'historique' && !estProprietaire()) CTAB = 'livres';           // l'historique est réservé aux administrateurs
    const onglets = [['livres', 'Mes livres', bl.exemplaires], ['analyse', 'Analyse', null], ...(estProprietaire() ? [['historique', 'Historique', null]] : []), ['vendre', 'À vendre', exV], ['trouver', 'À trouver', nbTrouver], ['gerer', 'Gérer', null]];
    const vide = (t) => `<p class="coll-vide-onglet">${t}</p>`;
    const imp0 = $('#importer');                         // le panneau d'import vit dans « Gérer ma collection » : on le remet à l'abri avant de redessiner
    if (imp0 && zone.contains(imp0)) $('#collection').insertBefore(imp0, $('#coll-prive'));
    zone.innerHTML = `
      <ul class="coll-cles" id="coll-cles" aria-label="Chiffres clés de la collection">${cases.map(([l, v, d, c]) => `<li class="${c}"><span class="cle-lib">${l}</span><b>${v}</b>${d ? `<small>${d}</small>` : ''}</li>`).join('')}</ul>
      <p class="trois">${esc(texteEstimation(bl))}</p>
      ${bl.sansCote ? `<p class="sans-cote">${bl.sansCote} exemplaire${bl.sansCote > 1 ? 's' : ''} sans cote pour l'état choisi : non compté${bl.sansCote > 1 ? 's' : ''} dans le total.</p>` : ''}
      <div class="coll-nav" id="coll-nav" role="tablist" aria-label="Sections de ma collection">${onglets.map(([k, nom, nb]) =>
        `<button type="button" role="tab" id="onglet-coll-${k}" aria-controls="pane-coll-${k}" aria-selected="${k === CTAB}" tabindex="${k === CTAB ? 0 : -1}" data-onglet="${k}">${ICONES_ONGLET[k] || ''}<span class="onglet-nom">${nom}</span>${nb == null ? '' : ` <span class="coll-nb" aria-label="${nb} livre${nb > 1 ? 's' : ''}">(${nb})</span>`}</button>`).join('')}</div>
      <div class="coll-pane" id="pane-coll-livres" role="tabpanel" aria-labelledby="onglet-coll-livres"${CTAB === 'livres' ? '' : ' hidden'}>
        <h3 id="titre-exemplaires" class="sr-only">Mes livres</h3>
        ${barreFiltres(bl)}
        <p class="coll-filtre-compte" id="coll-filtre-compte" role="status" aria-live="polite">${texteFiltre(lst, bl)}</p>
        <ul class="ex-liste" id="coll-lignes">${lst.html}</ul>
        <div id="coll-plus-zone">${boutonPlus(lst.reste)}</div>
      </div>
      <div class="coll-pane" id="pane-coll-analyse" role="tabpanel" aria-labelledby="onglet-coll-analyse"${CTAB === 'analyse' ? '' : ' hidden'}>${analysePane(bl)}</div>
      ${estProprietaire() ? `<div class="coll-pane" id="pane-coll-historique" role="tabpanel" aria-labelledby="onglet-coll-historique"${CTAB === 'historique' ? '' : ' hidden'}>${historiquePane(bl)}</div>` : ''}
      <div class="coll-pane" id="pane-coll-vendre" role="tabpanel" aria-labelledby="onglet-coll-vendre"${CTAB === 'vendre' ? '' : ' hidden'}>${htmlAVendre(bl) || vide('Aucun livre à vendre pour l\'instant. Dans « Mes livres », touchez « À vendre » sous un exemplaire pour le placer ici.')}</div>
      <div class="coll-pane" id="pane-coll-trouver" role="tabpanel" aria-labelledby="onglet-coll-trouver"${CTAB === 'trouver' ? '' : ' hidden'}>${htmlATrouver() || vide('Aucun livre à trouver pour l\'instant. Sur l\'étagère, touchez « À trouver » sous une jaquette pour l\'ajouter ici.')}</div>
      <div class="coll-pane" id="pane-coll-gerer" role="tabpanel" aria-labelledby="onglet-coll-gerer"${CTAB === 'gerer' ? '' : ' hidden'}>${blocGerer()}</div>`;
    const imp1 = $('#importer'), dang = $('.gerer-danger');
    if (imp1 && dang) dang.before(imp1);
    afficherHistoColl(bl);
    brancherFiltresColl();
  }
  let limiteColl = 30;

  function initPageCollection() {
    brancherCollection();
    $('#fiche').addEventListener('click', (e) => { if (e.target === $('#fiche')) $('#fiche').close(); });
    let attente;
    window.addEventListener('resize', () => { clearTimeout(attente); attente = setTimeout(afficher, 150); });
    afficher();
    recevoirLien();
    if (new URLSearchParams(location.search).has('inventaire')) {
      history.replaceState(null, '', location.pathname + location.hash);
      ouvrirParcours();
    }
  }

  function brancherCollection() {
    // actions de la carte (déléguées : la carte est redessinée à chaque changement)
    $('#collection').addEventListener('change', (e) => {
      const id = e.target.dataset.etat || e.target.dataset.qte || e.target.dataset.prix;
      if (!id || !COLL[id]) return;
      if (!garde()) { afficher(); return; }
      if (e.target.dataset.prix !== undefined) { const pp = lirePrix(e.target.value); if (pp == null) delete COLL[id].prix; else COLL[id].prix = pp; }
      if (e.target.dataset.etat) COLL[id].etat = e.target.value;
      if (e.target.dataset.qte) COLL[id].qte = Math.min(99, Math.max(1, parseInt(e.target.value, 10) || 1));
      sauverColl(); afficher();
    });
    $('#collection').addEventListener('click', (e) => {
      const t = e.target;
      const bEtat = t.closest('[data-ex-etat]'), bQte = t.closest('[data-ex-qte]');
      if (bEtat || bQte) {                                  // état (C, BE, TBE) et nombre d'exemplaires d'une ligne de la liste
        const id = (bEtat || bQte).dataset.exEtat || (bEtat || bQte).dataset.exQte;
        if (!COLL[id] || !garde()) return;
        if (bEtat) COLL[id].etat = bEtat.dataset.e;
        else COLL[id].qte = Math.min(99, Math.max(1, COLL[id].qte + (+bQte.dataset.delta)));
        sauverColl(); afficher();
        return;
      }
      const tImp = t.closest('[data-importer-liste]'), tExp = t.closest('[data-exporter]');
      if (tImp || tExp) {                                 // « Gérer ma collection » : les deux tuiles qui déplient un bloc
        const cible = tImp ? $('#importer') : $('#exporter-choix'), ouvert = tImp ? !cible.open : cible.hidden;
        if (tImp) { cible.open = ouvert; if (ouvert) cible.scrollIntoView({ behavior: 'smooth', block: 'center' }); } else cible.hidden = !ouvert;
        (tImp || tExp).setAttribute('aria-expanded', String(ouvert));
        return;
      }
      const bVendre = t.closest('[data-ex-vendre]');
      if (bVendre || t.dataset.vendreGarder || t.dataset.vendu) {   // liste « à vendre » : marquer, garder, ou retirer une fois vendu
        const id = bVendre ? bVendre.dataset.exVendre : (t.dataset.vendreGarder || t.dataset.vendu);
        if (!COLL[id] || !garde()) return;
        if (t.dataset.vendu) {
          const ancien = COLL[id], b = livreDe(id);
          delete COLL[id]; sauverColl(); afficher(); annonce('Livre vendu : retiré de votre collection.');
          annulerRetrait(b, id, ancien, 'vendu, retiré de votre collection');
        } else {
          const mettre = bVendre ? !COLL[id].vendre : false;
          if (mettre) COLL[id].vendre = true; else delete COLL[id].vendre;
          sauverColl(); afficher(); annonce(mettre ? 'Livre ajouté à votre liste à vendre.' : 'Livre retiré de votre liste à vendre.');
        }
        return;
      }
      if ((t.dataset.retirer || t.id === 'coll-vider') && !garde()) return;
      if (t.dataset.souhaitRetirer) { if (!garde()) return; delete SOUH[t.dataset.souhaitRetirer]; sauverColl(); afficher(); annonce('Livre retiré de votre liste à trouver.'); }
      else if (t.dataset.retirer) {
        const id = t.dataset.retirer, ancien = COLL[id], b = livreDe(id);
        delete COLL[id]; sauverColl(); afficher(); annonce('Exemplaire retiré de votre collection.');
        annulerRetrait(b, id, ancien);
      }
      else if (t.closest('#imp-ouvrir')) { if (garde()) { $('#importer').open = true; $('#importer').hidden = false; $('#imp-fichier').click(); } }
      else if (t.closest('#exp-json')) exporter('json');
      else if (t.closest('#exp-csv')) exporter('csv');
      else if (t.id === 'coll-plus') { limiteColl += 30; afficherCollection(); }
      else if (t.id === 'coll-vider') {
        if (window.confirm(dansCompte() ? 'Effacer toute votre collection, y compris dans votre compte Google ? Pensez à l\'exporter avant : cette action est définitive.' : 'Effacer toute votre collection de ce navigateur ? Pensez à l\'exporter avant : cette action est définitive.')) {
          COLL = {}; sauverColl(); afficher(); annonce('Collection effacée.');
        }
      }
    });
    brancherParcours();                 // l'inventaire guidé est ouvert depuis la page collection
    $('#imp-go').addEventListener('click', () => importerTexte($('#imp-texte').value));
    $('#imp-fichier').addEventListener('change', async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      $('#importer').open = true;
      try { importerTexte(await f.text()); } catch (err) { statut('Ce fichier n\'a pas pu être lu.', true); }
      e.target.value = '';
      $('#imp-statut').scrollIntoView({ block: 'center' });
    });
  }

  function telecharger(nom, contenu, type) {
    const url = URL.createObjectURL(new Blob([contenu], { type }));
    const a = document.createElement('a');
    a.href = url; a.download = nom; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function exporter(format) {
    const bl = bilan();
    const jour = new Date().toISOString().slice(0, 10);
    if (format === 'json') {
      telecharger(`ma-collection-${jour}.json`, JSON.stringify({
        application: 'La Cote du Héros', version: 1, exporte_le: jour,
        avertissement: prixAnciens()
          ? 'Estimation fondée sur des cotes d\'archives (ancien relevé) : un ordre de grandeur, pas un prix de vente.'
          : 'Estimation mêlant prix actuels (annonces, ventes) et cotes d\'archives : un ordre de grandeur, pas un prix de vente.',
        estimation: { total: Math.round(bl.total * 100) / 100, exemplaires: bl.exemplaires, titres: bl.titres },
        exemplaires: bl.lignes.map(({ b, c }) => ({ isbn13: b.isbn13 || b.id, titre: b.titre, edition: b.version, serie: b.serie, numero: b.numero, etat: c.etat, quantite: c.qte, a_vendre: !!c.vendre, prix_unitaire_estime: b.prix[c.etat], prix_paye: c.prix ?? null, lot: c.lot ?? null })),
      }, null, 2), 'application/json');
    } else {
      const q = (t) => `"${String(t ?? '').replace(/"/g, '""')}"`;
      const lignes = [['isbn13', 'titre', 'edition', 'serie', 'numero', 'etat', 'quantite', 'prix_unitaire_estime', 'valeur_estimee', 'prix_paye', 'a_vendre'].join(';')]
        .concat(bl.lignes.map(({ b, c }) => [q(b.isbn13 || b.id), q(b.titre), b.version, q(b.serie), q(b.numero), c.etat, c.qte,
          b.prix[c.etat] == null ? '' : String(b.prix[c.etat]).replace('.', ','), valeurLigne(b, c) == null ? '' : valeurLigne(b, c).toFixed(2).replace('.', ','), prixSaisi(c.prix), c.vendre ? 'oui' : ''].join(';')));
      telecharger(`ma-collection-${jour}.csv`, '﻿' + lignes.join('\r\n'), 'text/csv;charset=utf-8');
    }
    annonce('Export prêt : le fichier a été téléchargé.');
  }

  // ISBN : conversion et validation
  const chiffres = (t) => String(t).replace(/[^0-9Xx]/g, '').toUpperCase();
  function versIsbn13(t) {
    const d = chiffres(t);
    if (d.length === 13 && /^\d{13}$/.test(d)) return d;
    if (d.length === 10 && /^\d{9}[\dX]$/.test(d)) {
      const c = '978' + d.slice(0, 9);
      const k = (10 - (c.split('').reduce((s2, x, i) => s2 + (+x) * (i % 2 ? 3 : 1), 0) % 10)) % 10;
      return c + k;
    }
    return null;
  }
  const etatDepuis = (t) => {
    const n = norm(t).replace(/[^a-z]/g, '');
    if (['convenable', 'conv', 'correct', 'moyen', 'ec'].includes(n)) return 'convenable';
    if (['bon', 'bonetat', 'be'].includes(n)) return 'bon';
    if (['tbe', 'tresbon', 'tresbonetat', 'neuf', 'excellent'].includes(n)) return 'tres_bon';
    return null;
  };
  function statut(t, erreur) { const el = $('#imp-statut'); el.textContent = t; el.classList.toggle('erreur', !!erreur); }

  function importer(texte) {
    const entrees = []; // { isbn13, etat, qte }
    const brut = String(texte || '').trim();
    if (!brut) return { erreur: 'Rien à importer : la liste est vide.' };
    try {
      if (brut.startsWith('{') || brut.startsWith('[')) {
        const j = JSON.parse(brut);
        const v = Array.isArray(j) ? 0 : Number(j.version ?? 1);
        if (v > FORMAT_FICHIER) return { erreur: `Ce fichier a été créé avec une version plus récente du site (format ${v}). Actualisez la page, puis recommencez.` };
        // formats 0 (simple liste) et 1 : même lecture. Un futur format 2 ajoutera ici sa conversion vers cette forme.
        const liste = Array.isArray(j) ? j : (Array.isArray(j.exemplaires) ? j.exemplaires : []);
        liste.forEach((x) => {
          if (typeof x === 'string') entrees.push({ cle: x });
          else if (x && typeof x === 'object') entrees.push({ cle: x.isbn13 || x.isbn || x.id || '?', etat: etatDepuis(x.etat || ''), qte: parseInt(x.quantite ?? x.qte, 10) || 1, prix: lirePrix(x.prix_paye), vendre: x.a_vendre === true, lot: typeof x.lot === 'string' ? x.lot.slice(0, 20) : null });
        });
        if (!entrees.length) return { erreur: 'Ce fichier ne contient aucun livre exploitable.' };
      }
    } catch (e) { return { erreur: 'Le JSON est illisible.' }; }
    if (!entrees.length) {
      // CSV issu de l'export du site : lecture par colonnes (les titres peuvent contenir « ; »)
      const coupe = (l) => { const o = []; let t = '', g = false; for (let i = 0; i < l.length; i++) { const ch = l[i]; if (g) { if (ch === '"' && l[i + 1] === '"') { t += '"'; i++; } else if (ch === '"') g = false; else t += ch; } else if (ch === '"') g = true; else if (ch === ';') { o.push(t); t = ''; } else t += ch; } o.push(t); return o; };
      const brutes = brut.replace(/^\uFEFF/, '').split(/\r?\n/).filter((l) => l.trim());
      const tete = coupe(brutes[0] || '').map((x) => x.trim().toLowerCase());
      if (tete.includes('isbn13') && tete.includes('quantite')) {
        const col = (n) => tete.indexOf(n);
        brutes.slice(1).forEach((l) => {
          const v = coupe(l);
          entrees.push({ cle: v[col('isbn13')], etat: etatDepuis(v[col('etat')] || ''), qte: parseInt(v[col('quantite')], 10) || 1, prix: col('prix_paye') >= 0 ? lirePrix(v[col('prix_paye')]) : null, vendre: col('a_vendre') >= 0 && /^(oui|1|true)$/i.test((v[col('a_vendre')] || '').trim()) });
        });
      }
    }
    if (!entrees.length) {
      brut.split(/\r?\n/).forEach((ligne, i) => {
        if (!ligne.trim() || (i === 0 && /isbn/i.test(ligne) && /;|,|\t/.test(ligne))) return;
        let cle = null, etat = null, qte = null;
        ligne.split(/[;,\t]+|\s+/).map((x) => x.replace(/^"|"$/g, '')).filter(Boolean).forEach((tok) => {
          if (!cle && versIsbn13(tok)) { cle = tok; return; }
          const e2 = etatDepuis(tok);
          if (e2 && !etat) { etat = e2; return; }
          if (/^x?\d{1,2}$/i.test(tok) && qte == null) qte = parseInt(tok.replace(/x/i, ''), 10);
        });
        if (cle) entrees.push({ cle, etat, qte });
        else if (ligne.trim()) entrees.push({ cle: ligne.trim().slice(0, 40), inconnu: true });
      });
    }
    return appliquerEntrees(entrees, false);
  }
  function appliquerEntrees(entrees, remplacer) {
    if (!garde(() => appliquerEntrees(entrees, remplacer))) return;
    if (remplacer) COLL = {};
    let ajoutes = 0, maj = 0; const inconnus = [];
    entrees.forEach((en) => {
      const isbn = en.inconnu ? null : versIsbn13(en.cle);
      const b = isbn ? DATA.find((x) => x.isbn13 === isbn) : DATA.find((x) => x.id === en.cle);
      if (!b) { inconnus.push(en.cle); return; }
      const avant = COLL[b.id];
      COLL[b.id] = { etat: en.etat || (avant && avant.etat) || S.h, qte: Math.min(99, Math.max(1, en.qte || (avant && avant.qte) || 1)), ...(en.vendre ? { vendre: true } : gv(avant)) };
      const pp = en.prix != null ? en.prix : (avant && avant.prix != null ? avant.prix : null);
      if (pp != null) COLL[b.id].prix = pp;
      const lotId = en.lot || (avant && avant.lot);
      if (lotId) COLL[b.id].lot = lotId;
      if (avant) maj += 1; else ajoutes += 1;
    });
    sauverColl(); afficher();
    return { ajoutes, maj, inconnus };
  }

  /* ---------- Lien de transfert : la collection est dans l'adresse, après le « # » (jamais envoyée à un serveur) ---------- */
  const DEPUIS_LETTRE = { c: 'convenable', b: 'bon', t: 'tres_bon' };
  const versB64 = (octets) => btoa(String.fromCharCode(...octets)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const depuisB64 = (t) => Uint8Array.from(atob(t.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));
  async function fluxOctets(octets, Classe, mode) {
    const f = new Blob([octets]).stream().pipeThrough(new Classe(mode));
    return new Uint8Array(await new Response(f).arrayBuffer());
  }
  async function lireCode(code) {
    const m = /^(\d+)(z?)\.([A-Za-z0-9_-]*)$/.exec(code || '');
    if (!m) return { erreur: 'Ce lien de transfert est incomplet ou abîmé.' };
    if (+m[1] > FORMAT_FICHIER) return { erreur: 'Ce lien a été créé avec une version plus récente du site. Actualisez la page, puis rouvrez-le.' };
    try {
      let octets = depuisB64(m[3]);
      if (m[2]) octets = await fluxOctets(octets, DecompressionStream, 'deflate-raw');
      const entrees = [];
      new TextDecoder().decode(octets).split(',').filter(Boolean).forEach((part) => {
        const x = /^(.+?)([cbt])(\d{0,2})(?:@(\d+(?:\.\d{1,2})?))?$/.exec(part);
        if (x) entrees.push({ cle: x[1], etat: DEPUIS_LETTRE[x[2]], qte: parseInt(x[3], 10) || 1, prix: lirePrix(x[4]) });
      });
      return { entrees };
    } catch (e) { return { erreur: 'Ce lien de transfert est incomplet ou abîmé.' }; }
  }
  async function recevoirLien() {
    const code = new URLSearchParams(location.hash.slice(1)).get('c');
    if (code == null) return;
    history.replaceState(null, '', location.pathname + location.search);   // l'adresse ne garde pas la collection
    const r = await lireCode(code);
    const bloc = document.createElement('div');
    bloc.className = 'lien-recu'; bloc.setAttribute('role', 'region'); bloc.setAttribute('aria-label', 'Collection reçue par lien');
    $('#collection').before(bloc);
    if (r.erreur || !r.entrees.length) { bloc.innerHTML = `<p class="erreur">${esc(r.erreur || 'Ce lien ne contient aucun livre.')}</p><button type="button" class="bouton bouton-clair" data-lien="ignorer">Fermer</button>`; }
    else {
      const n = r.entrees.reduce((t, e2) => t + (e2.qte || 1), 0);
      const vide = !Object.keys(COLL).length;
      bloc.innerHTML = `<p><strong>Une collection vous a été transmise :</strong> ${r.entrees.length} titre${r.entrees.length > 1 ? 's' : ''}, ${n} exemplaire${n > 1 ? 's' : ''}. Rien n'est enregistré tant que vous n'avez pas choisi.</p>
        <div class="coll-actions"><button type="button" class="bouton" data-lien="ajouter">${vide ? 'Charger cette collection' : 'Ajouter à ma collection'}</button>
        ${vide ? '' : '<button type="button" class="bouton bouton-clair" data-lien="remplacer">Remplacer ma collection</button>'}
        <button type="button" class="bouton bouton-clair" data-lien="ignorer">Ignorer</button></div>`;
    }
    bloc.addEventListener('click', (e) => {
      const a = e.target.dataset.lien;
      if (!a) return;
      if (a === 'remplacer' && !window.confirm('Remplacer toute votre collection actuelle par celle de ce lien ? Pensez à l\'exporter avant.')) return;
      if (a !== 'ignorer' && r.entrees) {
        const res = appliquerEntrees(r.entrees, a === 'remplacer');
        annonce(resumeImport(res));
      }
      bloc.remove();
    });
  }
  function resumeImport(r) {
    const morceaux = [`${r.ajoutes} ajouté${r.ajoutes > 1 ? 's' : ''}`];
    if (r.maj) morceaux.push(`${r.maj} mis à jour`);
    if (r.inconnus.length) morceaux.push(`${r.inconnus.length} non reconnu${r.inconnus.length > 1 ? 's' : ''} (${r.inconnus.slice(0, 4).join(', ')}${r.inconnus.length > 4 ? '…' : ''})`);
    return morceaux.join(' · ') + '.';
  }
  function importerTexte(texte) {
    const r = importer(texte);
    if (r.erreur) { statut(r.erreur, true); return; }
    statut(resumeImport(r), !r.ajoutes && !r.maj);
    if (r.ajoutes || r.maj) $('#imp-texte').value = '';
  }

  // Fiche : bloc « dans ma collection »
  function blocCollectionFiche(b) {
    if (sansCompte()) {
      return `<div class="coll-fiche"><h3>Dans ma collection</h3><p class="sous">Les fiches restent consultables sans compte. Pour garder vos livres, connectez-vous : Google les enregistre dans un espace réservé de votre Drive.</p>
        <button type="button" class="bouton" data-compte="connecter">Se connecter pour ajouter à ma collection</button></div>`;
    }
    const c = COLL[b.id], v = c ? valeurLigne(b, c) : null;
    const etats = ETATS.map((x) => `<button type="button" data-fe="${x.k}" aria-pressed="${!!c && c.etat === x.k}" title="${x.long}" aria-label="${x.long}${c && c.etat === x.k ? ' : retirer de ma collection' : ''}">${ABREGE[x.k]}</button>`).join('');
    const action = c
      ? `<button type="button" class="fiche-marque vendre${c.vendre ? ' actif' : ''}" data-fe-vendre aria-pressed="${!!c.vendre}">À vendre</button>`
      : `<button type="button" class="fiche-marque trouver${SOUH[b.id] ? ' actif' : ''}" data-fe-trouver aria-pressed="${!!SOUH[b.id]}">À trouver</button>`;
    return `<div class="coll-fiche"><h3>Dans ma collection</h3>
      <p class="sous">${c ? 'Touchez l\'état de votre exemplaire. Toucher le même état le retire.' : 'Choisissez l\'état de votre exemplaire pour l\'ajouter.'}</p>
      <div class="coll-ligne"><div class="ex-etats" role="group" aria-label="État de mon exemplaire">${etats}</div>
        ${c ? `<label class="fiche-qte">Exemplaires <input type="number" id="c-qte" min="1" max="99" value="${c.qte}"></label>` : ''}${action}</div>
      ${c ? `<p class="valeur-ex">${v == null ? 'Sans cote pour cet état' : `Valeur estimée : ${fmt(v)}`}</p>` : ''}</div>`;
  }
  function brancherFicheCollection(b) {
    const zone = $('.coll-fiche');
    if (!zone || !zone.querySelector('[data-fe]')) return;           // visiteur sans compte : le bloc ne contient que l'invitation
    let enCours = false;
    const rafraichir = () => {                                       // la zone reste en place : seul son contenu est remplacé
      if (enCours) return;                                           // le retrait d'un champ actif déclenche un « change » : on l'ignore
      enCours = true;
      const t = document.createElement('div'); t.innerHTML = blocCollectionFiche(b);
      zone.replaceChildren(...t.firstElementChild.childNodes); afficher();
      enCours = false;
    };
    zone.addEventListener('click', (e) => {
      const et = e.target.closest('[data-fe]');
      if (et) { basculerPossede(b.id, et.dataset.fe); rafraichir(); return; }
      if (e.target.closest('[data-fe-vendre]')) { basculerVendre(b.id); rafraichir(); return; }
      if (e.target.closest('[data-fe-trouver]')) { basculerSouhait(b.id); rafraichir(); }
    });
    zone.addEventListener('change', (e) => {
      if (e.target.id !== 'c-qte' || !COLL[b.id] || enCours) return;
      COLL[b.id].qte = Math.min(99, Math.max(1, parseInt(e.target.value, 10) || 1)); sauverColl(); rafraichir();
    });
  }


  /* ---------- Lot acheté : plusieurs livres pour un seul prix, réparti d'après les cotes ---------- */
  const LOT = { lignes: [], total: '' };
  // Répartit le total payé (livraison comprise) sur les lignes non corrigées à la main, au prorata de la cote de chaque ligne.
  // Ce ne sont pas des prix réels livre par livre : c'est une répartition, et le site le dit.
  function repartirLot() {
    const base = lirePrix(LOT.total) || 0;
    const fixes = LOT.lignes.filter((l) => l.manuel && l.prix != null);
    const libres = LOT.lignes.filter((l) => !(l.manuel && l.prix != null));
    if (!(base > 0)) { libres.forEach((l) => { l.prix = null; }); return; }
    if (!libres.length) return;
    const poids = libres.map((l) => { const b = livreDe(l.id), c = b && b.prix[l.etat]; return { l, w: c ? c * l.qte : null }; });
    const connus = poids.filter((x) => x.w != null);
    const moyenne = connus.length ? connus.reduce((t, x) => t + x.w, 0) / connus.length : 1;
    poids.forEach((x) => { if (x.w == null) x.w = moyenne; });
    const somme = poids.reduce((t, x) => t + x.w, 0);
    const cible = Math.max(base - fixes.reduce((t, l) => t + l.prix * l.qte, 0), 0);
    let attribue = 0;
    poids.forEach((x, i) => {
      const ligne = i === poids.length - 1 ? Math.max(cible - attribue, 0) : Math.round((cible * x.w / somme) * 100) / 100;
      attribue += ligne;
      x.l.prix = Math.max(0.01, Math.round((ligne / x.l.qte) * 100) / 100);
    });
  }
  const sommeLot = () => LOT.lignes.reduce((t, l) => t + (l.prix || 0) * l.qte, 0);

  function ouvrirLot() {
    if (!garde(ouvrirLot)) return;
    let dlg = $('#lot');
    if (!dlg) {
      dlg = document.createElement('dialog');
      dlg.id = 'lot'; dlg.className = 'lot'; dlg.setAttribute('aria-labelledby', 'lot-titre');
      dlg.innerHTML = `<div class="lot-cadre">
        <div class="parcours-tete"><h2 id="lot-titre">Ajouter un lot acheté</h2><button type="button" class="bouton bouton-clair" id="lot-fermer">Fermer</button></div>
        <p class="sous">Vous avez acheté plusieurs livres pour un seul prix, par exemple sur un site de vente en ligne ? Choisissez-les, indiquez le prix total : le site répartit ce prix d'après les cotes. Vous pouvez corriger chaque prix.</p>
        <div class="champ"><label for="lot-q">Chercher un livre (titre, auteur ou ISBN)</label><input type="search" id="lot-q" autocomplete="off" placeholder="Par exemple : sorcier, Dever, 978…"></div>
        <ul class="lot-res" id="lot-res" aria-live="polite"></ul>
        <h3 id="lot-h">Dans le lot</h3>
        <div id="lot-lignes"></div>
        <div class="lot-prix">
          <div class="champ"><label for="lot-total">Prix total payé, livraison comprise (€)</label><input type="text" id="lot-total" inputmode="decimal" autocomplete="off" placeholder="par exemple 45"></div>
        </div>
        <p class="statut" id="lot-verif" role="status" aria-live="polite"></p>
        <p class="sous">Les prix du lot sont une répartition d'après les cotes, pas des prix réels livre par livre : le site n'en fait pas des prix de référence.</p>
        <div class="importer-actions">
          <button type="button" class="bouton" id="lot-valider">Ajouter à ma collection</button>
          <button type="button" class="bouton bouton-clair" id="lot-repartir">Répartir de nouveau</button>
        </div></div>`;
      document.body.appendChild(dlg);
      brancherLot(dlg);
    }
    dlg.showModal();
    rendreLot();
    $('#lot-q').focus();
  }
  function rechercheLot(v) {
    const q = norm(v).trim(), liste = $('#lot-res');
    if (q.length < 2) { liste.innerHTML = ''; return; }
    const isbn = versIsbn13(v);
    const mots = q.split(/\s+/);
    const trouves = DATA.filter((b) => (isbn ? b.isbn13 === isbn : mots.every((m) => b._txt.includes(m))))
      .sort((x, y) => x.serie.localeCompare(y.serie, 'fr') || (parseInt(x.numero, 10) || 0) - (parseInt(y.numero, 10) || 0) || x.version_n - y.version_n);
    liste.innerHTML = trouves.slice(0, 8).map((b) => `<li><button type="button" data-lot-add="${esc(b.id)}"><strong>${esc(b.titre)}</strong><span>${esc(b.serie)}${esc(numero(b))} <span class="nowrap"><span class="badge">${esc(b.version)}</span></span>${b.annee ? ` · ${b.annee}` : ''}${COLL[b.id] ? ' · déjà dans votre collection' : ''}</span><em>Ajouter au lot</em></button></li>`).join('') +
      (trouves.length > 8 ? `<li class="sous">${trouves.length} résultats : précisez votre recherche.</li>` : '') + (!trouves.length ? '<li class="sous">Aucun livre trouvé.</li>' : '');
  }
  function rendreLot() {
    $('#lot-h').textContent = `Dans le lot (${LOT.lignes.reduce((t, l) => t + l.qte, 0)} exemplaire${LOT.lignes.reduce((t, l) => t + l.qte, 0) > 1 ? 's' : ''})`;
    $('#lot-lignes').innerHTML = !LOT.lignes.length ? '<p class="sous">Aucun livre pour l\'instant : cherchez-les ci-dessus.</p>' :
      `<table class="cartes coll-table"><thead><tr><th>Livre</th><th>État</th><th>Exemplaires</th><th>Prix par exemplaire</th><th class="num">Retirer</th></tr></thead><tbody>${LOT.lignes.map((l) => {
        const b = livreDe(l.id);
        return `<tr><td class="principal"><div><strong>${esc(b.titre)}</strong><span class="sous" style="display:block">${esc(b.serie)}${esc(numero(b))} <span class="nowrap"><span class="badge">${esc(b.version)}</span></span>${COLL[b.id] ? ' · déjà possédé : l\'exemplaire s\'ajoute' : ''}</span></div></td>
          <td data-label="État"><select data-lot-etat="${esc(l.id)}" aria-label="État de ${esc(b.titre)}, édition ${esc(b.version)}">${ETATS.map((x) => `<option value="${x.k}"${x.k === l.etat ? ' selected' : ''}>${x.k === 'tres_bon' ? 'TBE' : x.court}</option>`).join('')}</select></td>
          <td data-label="Exemplaires"><input type="number" min="1" max="99" value="${l.qte}" data-lot-qte="${esc(l.id)}" aria-label="Nombre d'exemplaires de ${esc(b.titre)}, édition ${esc(b.version)}"></td>
          <td data-label="Prix par exemplaire"><input type="text" inputmode="decimal" autocomplete="off" value="${prixSaisi(l.prix)}" placeholder="après le prix total" data-lot-prix="${esc(l.id)}" aria-label="Prix par exemplaire de ${esc(b.titre)}, édition ${esc(b.version)}">${l.manuel ? '<small class="sous">corrigé à la main</small>' : ''}</td>
          <td class="num"><button type="button" class="retirer" data-lot-retirer="${esc(l.id)}" aria-label="Retirer ${esc(b.titre)} du lot">Retirer</button></td></tr>`;
      }).join('')}</tbody></table>`;
    const base = lirePrix(LOT.total) || 0;
    const v = $('#lot-verif');
    if (!LOT.lignes.length) v.textContent = '';
    else if (!(base > 0)) v.textContent = 'Indiquez le prix total payé : le site répartira ce prix sur les livres.';
    else {
      const ecart = Math.abs(sommeLot() - base);
      v.textContent = ecart <= 0.05 * Math.max(1, LOT.lignes.reduce((t, l) => t + l.qte, 0))
        ? `Total réparti : ${fmt(sommeLot())} pour ${fmt(base)} à répartir.`
        : `Attention : les prix saisis font ${fmt(sommeLot())}, pour ${fmt(base)} à répartir. Corrigez, ou répartissez de nouveau.`;
    }
    v.classList.remove('erreur');
  }
  function brancherLot(dlg) {
    $('#lot-fermer').addEventListener('click', () => dlg.close());
    $('#lot-q').addEventListener('input', (e) => rechercheLot(e.target.value));
    const relire = () => { LOT.total = $('#lot-total').value; repartirLot(); rendreLot(); };
    $('#lot-total').addEventListener('change', relire);
    dlg.addEventListener('click', (e) => {
      const t = e.target.closest('button');
      if (!t) return;
      if (t.dataset.lotAdd) {
        const l = LOT.lignes.find((x) => x.id === t.dataset.lotAdd);
        if (l) l.qte = Math.min(99, l.qte + 1); else LOT.lignes.push({ id: t.dataset.lotAdd, etat: S.h, qte: 1, prix: null, manuel: false });
        $('#lot-q').value = ''; $('#lot-res').innerHTML = ''; repartirLot(); rendreLot(); $('#lot-q').focus();
        annonce('Livre ajouté au lot.');
      } else if (t.dataset.lotRetirer) {
        LOT.lignes = LOT.lignes.filter((x) => x.id !== t.dataset.lotRetirer); repartirLot(); rendreLot();
      } else if (t.id === 'lot-repartir') {
        LOT.lignes.forEach((l) => { l.manuel = false; }); relire();
      } else if (t.id === 'lot-valider') validerLot(dlg);
    });
    dlg.addEventListener('change', (e) => {
      const d = e.target.dataset;
      const l = LOT.lignes.find((x) => x.id === (d.lotEtat || d.lotQte || d.lotPrix));
      if (!l) return;
      if (d.lotEtat) { l.etat = e.target.value; repartirLot(); }
      if (d.lotQte) { l.qte = Math.min(99, Math.max(1, parseInt(e.target.value, 10) || 1)); repartirLot(); }
      if (d.lotPrix !== undefined) { const pp = lirePrix(e.target.value); if (pp == null) { l.manuel = false; } else { l.prix = pp; l.manuel = true; } repartirLot(); }
      rendreLot();
    });
  }
  function validerLot(dlg) {
    LOT.total = $('#lot-total').value; repartirLot();
    const v = $('#lot-verif');
    const echec = (m) => { rendreLot(); v.textContent = m; v.classList.add('erreur'); };
    if (!LOT.lignes.length) return echec('Ajoutez au moins un livre au lot.');
    if (!(lirePrix(LOT.total) > 0)) return echec('Indiquez le prix total payé.');
    if (LOT.lignes.some((l) => l.prix == null)) return echec('Un prix manque : vérifiez le prix total.');
    const idLot = 'L' + Date.now().toString(36);
    let n = 0;
    LOT.lignes.forEach((l) => {
      const avant = COLL[l.id], qn = Math.min(99, (avant ? avant.qte : 0) + l.qte);
      const pm = avant && avant.prix != null ? Math.round(((avant.prix * avant.qte + l.prix * l.qte) / (avant.qte + l.qte)) * 100) / 100 : l.prix;
      COLL[l.id] = { etat: l.etat, qte: qn, prix: pm, lot: idLot };
      n += l.qte;
    });
    const total = sommeLot();
    LOT.lignes = []; LOT.total = ''; $('#lot-total').value = '';
    sauverColl(); dlg.close(); afficher();
    annonce(`${n} exemplaire${n > 1 ? 's' : ''} ajouté${n > 1 ? 's' : ''} à votre collection, pour ${fmt(total)} au total.`);
  }
  document.addEventListener('click', (e) => { if (e.target.closest('[data-lot]')) ouvrirLot(); });
  document.addEventListener('click', (e) => { if (e.target.closest('[data-demande]') && window.Compte) window.Compte.demanderLivre(S.q); });


  /* ---------- Inventaire guidé : séries → éditions → listes → bilan ---------- */
  const P = { phase: 'intro', etat: 'bon', series: new Set(), cellules: new Set(), file: [], i: 0, message: '' };
  const CLE_P = 'cote-parcours-v1';
  let INFO = null, REPRISE = null, derniereSauvegarde = null;
  const heure = (d) => d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  function majIndicateur() {
    const el = $('#pa-save');
    if (el) el.textContent = derniereSauvegarde ? `✓ Enregistré sur cet appareil à ${heure(derniereSauvegarde)}` : '';
  }
  /* Mémorise l'avancement (étape, séries, éditions, liste en cours) ; la collection l'est déjà à chaque clic */
  function memoriser() {
    try {
      localStorage.setItem(CLE_P, JSON.stringify({ phase: P.phase, etat: P.etat, i: P.i, series: [...P.series], cellules: [...P.cellules] }));
      derniereSauvegarde = new Date();
    } catch (e) { /* stockage indisponible : l'indicateur reste vide */ }
    majIndicateur();
  }
  function lireParcours() {
    try {
      const j = JSON.parse(localStorage.getItem(CLE_P) || 'null');
      if (!j || !['series', 'editions', 'liste'].includes(j.phase)) return null;
      const series = (j.series || []).filter((n) => INFO.has(n));
      const cellules = (j.cellules || []).filter((c) => { const [n, v] = c.split('|'); return INFO.has(n) && INFO.get(n).edit.has(v); });
      return { phase: j.phase, etat: ETATS.some((e) => e.k === j.etat) ? j.etat : 'bon', i: j.i | 0, series, cellules };
    } catch (e) { return null; }
  }
  function depuisCollection() {
    Object.keys(COLL).forEach((id) => { const b = livreDe(id); if (b) { P.series.add(b.serie); P.cellules.add(cleCell(b.serie, b.version)); } });
  }
  const cleCell = (serie, v) => `${serie}|${v}`;
  function infoSeries() {
    const m = new Map();
    DATA.forEach((b) => {
      const e = m.get(b.serie) || { nom: b.serie, livres: new Set(), edit: new Map(), nb: 0 };
      e.livres.add(b.livre_id); e.nb += 1;
      (e.edit.get(b.version) || e.edit.set(b.version, []).get(b.version)).push(b);
      m.set(b.serie, e);
    });
    return m;
  }
  const numDe = (b) => parseInt(b.numero, 10) || 0;
  const livresDe = (serie, v) => (INFO.get(serie).edit.get(v) || []).slice()
    .sort((a, b) => numDe(a) - numDe(b) || a.titre.localeCompare(b.titre, 'fr'));
  const pl = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`;

  function ouvrirParcours() {
    if (!garde(ouvrirParcours)) return;
    INFO = INFO || infoSeries();
    P.phase = 'intro'; P.series = new Set(); P.cellules = new Set(); P.file = []; P.i = 0; P.message = '';
    REPRISE = lireParcours();
    if (REPRISE) { P.etat = REPRISE.etat; REPRISE.series.forEach((n) => P.series.add(n)); REPRISE.cellules.forEach((c) => P.cellules.add(c)); }
    depuisCollection();
    if (!$('#parcours').open) $('#parcours').showModal();
    rendre();
  }

  function tete(etape, titre, pct) {
    $('#parcours-etape').textContent = etape;
    $('#parcours-titre').textContent = titre;
    const barre = $('#parcours-barre');
    barre.setAttribute('aria-valuenow', String(Math.round(pct)));
    barre.firstElementChild.style.width = `${pct}%`;
  }
  function pied(gauche, droite, info) {
    const sauve = ['series', 'editions', 'liste'].includes(P.phase)
      ? `<div class="pa-sauve"><span id="pa-save" role="status"></span><button type="button" class="bouton-lien" data-pa="sauve">Télécharger ma sauvegarde</button></div>` : '';
    $('#parcours-pied').innerHTML = `<div class="gauche">${gauche}</div><div class="droite">${info ? `<span class="info">${info}</span>` : ''}${droite}</div>${sauve}`;
    majIndicateur();
  }
  const bouton = (act, txt, cls = '', dis = false) => `<button type="button" class="bouton ${cls}" data-pa="${act}"${dis ? ' disabled' : ''}>${txt}</button>`;

  function rendre() {
    const corps = $('#parcours-corps');
    ({ intro: etapeIntro, series: etapeSeries, editions: etapeEditions, liste: etapeListe, fin: etapeFin })[P.phase]();
    if (P.phase !== 'intro') memoriser();
    corps.scrollTop = 0;
    $('#parcours-titre').focus({ preventScroll: true });
  }

  function etapeIntro() {
    const dejaN = Object.values(COLL).reduce((a, c) => a + c.qte, 0);
    tete('Inventaire guidé', 'Faisons l\'inventaire de votre collection', 0);
    const etapes = { series: 'les séries', editions: 'les éditions', liste: 'les listes de livres' };
    const reprendre = REPRISE
      ? bouton('reprendre', `Reprendre là où j'en étais<small>${etapes[REPRISE.phase]} · ${dejaN ? pl(dejaN, 'exemplaire') : 'aucun livre coché'}</small>`, 'bouton-choix')
      : (dejaN ? bouton('reprendre', `Continuer avec ma collection<small>${pl(dejaN, 'exemplaire')} déjà enregistré${dejaN > 1 ? 's' : ''} sur cet appareil</small>`, 'bouton-choix') : '');
    $('#parcours-corps').innerHTML = `
      <section class="reprise" aria-labelledby="pe-reprise">
        <h3 id="pe-reprise">${reprendre ? 'Reprendre ou repartir ?' : 'Vous avez déjà un fichier ?'}</h3>
        <div class="reprise-choix">
          ${reprendre}
          <label class="bouton bouton-clair bouton-choix" for="pe-fichier">Charger mon fichier<small>sauvegarde JSON, CSV ou liste d'ISBN : tout est coché pour vous</small></label>
          <input type="file" id="pe-fichier" accept=".json,.csv,.txt,text/plain,application/json" hidden>
          ${dejaN ? bouton('zero', `Repartir de zéro<small>efface la collection${dansCompte() ? ' (aussi dans votre compte)' : ' de ce navigateur'}</small>`, 'bouton-clair bouton-choix') : ''}
        </div>
        <p class="statut" id="pe-statut" role="status" aria-live="polite"></p>
      </section>
      <p>Inutile de tout saisir à la main : vous touchez vos <strong>séries</strong>, puis vos <strong>éditions</strong>, puis vous cochez vos <strong>couvertures</strong>. Le <strong>bilan</strong> estime votre patrimoine à la fin.</p>
      <p><strong>Vos livres sont le plus souvent en…</strong> <span class="sous">(vous pourrez le changer à chaque liste)</span></p>
      <div class="choix-etat" role="radiogroup" aria-label="État habituel">
        ${ETATS.map((e) => `<label><input type="radio" name="pe-etat" value="${e.k}"${e.k === P.etat ? ' checked' : ''}><span>${e.k === 'tres_bon' ? 'Très bon état (TBE)' : e.court}<small>${esc(e.def.replace(' TBE signifie « très bon état ».', ''))}</small></span></label>`).join('')}
      </div>
      <p class="sous">Tout s'enregistre au fil de l'eau, ${dansCompte() ? 'sur cet appareil et dans votre compte' : 'dans ce navigateur uniquement'}. Vous pouvez fermer à tout moment et reprendre plus tard.</p>`;
    pied(bouton('fermer', 'Plus tard', 'bouton-clair'), bouton('commencer', 'Commencer →'));
  }

  function etapeSeries() {
    tete('Étape 1 sur 3 · Séries', 'Quelles séries avez-vous ?', 20);
    const liste = [...INFO.values()].sort((a, b) => b.nb - a.nb || a.nom.localeCompare(b.nom, 'fr'));
    $('#parcours-corps').innerHTML = `${P.message ? `<p class="statut" role="status">${esc(P.message)}</p>` : ''}<p>Touchez chaque série dont vous possédez <strong>au moins un livre</strong>. Vous choisirez ensuite, à l'étape suivante, les éditions (V1 à V5) que vous possédez dans chaque série.</p>
      <div class="boutons-liste">${bouton('series-tout', 'Tout sélectionner')}${bouton('series-rien', 'Tout désélectionner', 'bouton-clair')}</div>
      <div class="tuiles" id="pa-series">${liste.map((e) => {
        const modele = [...e.edit.values()].flat().filter((b) => b.couverture).sort((x, y) => x.version_n - y.version_n || numDe(x) - numDe(y))[0];
        const on = P.series.has(e.nom);
        return `<button type="button" class="tuile-serie" data-serie="${esc(e.nom)}" aria-pressed="${on}">
          ${modele ? `<img src="${esc(racine(modele.couverture))}" alt="" width="44" height="62" loading="lazy" data-i="${esc(e.nom.charAt(0).toUpperCase())}">` : `<span class="jaq-vide" aria-hidden="true">${esc(e.nom.charAt(0).toUpperCase())}</span>`}
          <span><b>${esc(e.nom)}</b><small>${pl(e.livres.size, 'titre')} · ${[...e.edit.keys()].sort().join(', ')}</small></span></button>`;
      }).join('')}</div>`;
    majPiedSeries();
  }
  function majPiedSeries() {
    const n = P.series.size;
    pied(bouton('prec', '← Retour', 'bouton-clair'), n ? bouton('suiv', 'Continuer →') : bouton('fin', 'Passer au bilan', 'bouton-clair'),
      n ? pl(n, 'série') + ' choisie' + (n > 1 ? 's' : '') : 'Aucune série choisie');
  }

  function etapeEditions() {
    tete('Étape 2 sur 3 · Éditions', 'Dans quelles éditions ?', 40);
    const noms = [...INFO.values()].filter((e) => P.series.has(e.nom)).sort((a, b) => b.nb - a.nb || a.nom.localeCompare(b.nom, 'fr'));
    const legende = VERSIONS.map((v) => `<b>${v}</b> vers ${anneeMediane(v)}`).join(' · ');
    $('#parcours-corps').innerHTML = `<p>Pour chaque série, touchez les éditions que vous avez. <strong>V1</strong> désigne les poches d'origine ; les suivantes, les rééditions.</p>
      <p class="sous">${legende}</p>
      <div class="boutons-liste">${bouton('cells-tout', 'Tout sélectionner')}${bouton('cells-rien', 'Tout désélectionner', 'bouton-clair')}</div>
      <p class="sous">Vous avez toutes les séries d'une édition ? Touchez « Tout » sous son nom, dans l'en-tête de la colonne.</p>
      <table class="matrice"><thead><tr><th>Série</th>${VERSIONS.map((v) => `<th scope="col">${v}<small>vers ${anneeMediane(v)}</small><button type="button" class="col-tout" data-col="${v}"></button></th>`).join('')}</tr></thead>
      <tbody>${noms.map((e) => `<tr><td>${esc(e.nom)}</td>${VERSIONS.map((v) => {
        const n = (e.edit.get(v) || []).length;
        if (!n) return '<td><button type="button" class="cellule" disabled aria-label="Pas d\'édition ' + v + ' pour cette série">—</button></td>';
        return `<td><button type="button" class="cellule" data-cell="${esc(cleCell(e.nom, v))}" aria-pressed="${P.cellules.has(cleCell(e.nom, v))}" aria-label="${esc(e.nom)}, édition ${v}, ${pl(n, 'livre')}">${v}<small>${n}</small></button></td>`;
      }).join('')}</tr>`).join('')}</tbody></table>`;
    majMatrice();
    majPiedEditions();
  }
  // cellules d'une colonne (une série ne propose pas toutes les éditions)
  const cellulesDe = (v) => [...INFO.values()].filter((e) => P.series.has(e.nom) && e.edit.has(v)).map((e) => cleCell(e.nom, v));
  function majMatrice() {
    document.querySelectorAll('#parcours-corps .cellule[data-cell]').forEach((el) => el.setAttribute('aria-pressed', String(P.cellules.has(el.dataset.cell))));
    document.querySelectorAll('#parcours-corps .col-tout').forEach((el) => {
      const cs = cellulesDe(el.dataset.col);
      const tout = cs.length > 0 && cs.every((c) => P.cellules.has(c));
      el.disabled = !cs.length;
      el.textContent = tout ? 'Aucun' : 'Tout';
      el.setAttribute('aria-label', `${tout ? 'Tout décocher' : 'Tout cocher'} : édition ${el.dataset.col} de toutes les séries`);
    });
  }
  function toutesCellules(oui) {
    VERSIONS.forEach((v) => cellulesDe(v).forEach((c) => { if (oui) P.cellules.add(c); else P.cellules.delete(c); }));
  }
  function cellulesValides() {
    return [...P.cellules].filter((c) => P.series.has(c.split('|')[0]));
  }
  function majPiedEditions() {
    const n = cellulesValides().length;
    pied(bouton('prec', '← Séries', 'bouton-clair'), n ? bouton('suiv', 'Continuer →') : bouton('fin', 'Passer au bilan', 'bouton-clair'),
      n ? pl(n, 'liste') + ' à parcourir' : 'Aucune édition choisie');
  }

  function construireFile() {
    const ordre = [...INFO.values()].filter((e) => P.series.has(e.nom)).sort((a, b) => b.nb - a.nb || a.nom.localeCompare(b.nom, 'fr')).map((e) => e.nom);
    P.file = [];
    ordre.forEach((nom) => VERSIONS.forEach((v) => { if (P.cellules.has(cleCell(nom, v)) && INFO.get(nom).edit.has(v)) P.file.push({ serie: nom, v }); }));
  }

  function etapeListe() {
    const { serie, v } = P.file[P.i];
    const liste = livresDe(serie, v);
    tete(`Étape 3 sur 3 · Liste ${P.i + 1} sur ${P.file.length}`, `${serie} · édition ${v}`, 40 + (P.i / P.file.length) * 55);
    const avecNum = liste.some((b) => numDe(b) > 0);
    const editions = [...INFO.get(serie).edit.keys()].sort();
    const onglets = editions.length > 1 ? `<div class="onglets-ed" role="group" aria-label="Éditions de ${esc(serie)}">${editions.map((x) =>
      `<button type="button" data-ongl="${x}" aria-pressed="${x === v}" class="${P.cellules.has(cleCell(serie, x)) ? 'choisie' : ''}">${x}<small>${INFO.get(serie).edit.get(x).filter((l) => COLL[l.id]).length || ''}</small></button>`).join('')}</div>
      <p class="sous">Une autre édition de cette série ? Touchez-la : elle s'ajoute à votre inventaire. Le petit chiffre indique les livres déjà cochés.</p>` : '';
    $('#parcours-corps').innerHTML = `${onglets}
      <p class="liste-aide">Touchez les couvertures que vous avez. Vous avez <strong>toute l'édition</strong> ? « Tout cocher ». Il en manque quelques-uns ? « Tout cocher », puis touchez ceux qui manquent.</p>
      <div class="liste-outils">
        <div class="champ"><label for="pl-etat">État des livres cochés</label>
          <select id="pl-etat">${ETATS.map((e) => `<option value="${e.k}"${e.k === P.etat ? ' selected' : ''}>${e.k === 'tres_bon' ? 'TBE' : e.court}</option>`).join('')}</select></div>
        ${avecNum ? `<div class="champ champ-num"><label for="pl-num">Numéros (ex. 252, 267-272)</label>
          <div class="num-ligne"><input type="text" id="pl-num" inputmode="numeric" autocomplete="off" placeholder="252, 267-272"><button type="button" class="bouton bouton-clair" data-pa="num" aria-label="Cocher ces numéros">Cocher</button></div></div>` : ''}
        <div class="boutons-liste">${bouton('tout', 'Tout cocher')}${bouton('rien', 'Tout décocher', 'bouton-clair')}</div>
      </div>
      <p class="retour" id="pl-retour" role="status" aria-live="polite"></p>
      <p class="compteur" id="pl-compteur"></p>
      <div class="tuiles-livres" id="pa-livres">${liste.map((b) => `<div class="bloc-livre"><button type="button" class="tuile-livre" data-livre="${esc(b.id)}" aria-pressed="${!!COLL[b.id]}">
        ${b.couverture ? `<img src="${esc(racine(b.couverture))}" alt="" width="88" height="124" loading="lazy" decoding="async" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(b)}
        <span class="coche" aria-hidden="true"></span>
        <span class="t">${esc(b.titre)}</span><span class="n">${numDe(b) ? `n° ${esc(b.numero)} · ` : ''}${b.annee ?? ''}</span></button>
        <div class="etats-rapides" role="group" aria-label="État de ${esc(b.titre)}">${ETATS.map((e) =>
          `<button type="button" data-etat-livre="${esc(b.id)}" data-e="${e.k}" aria-pressed="${!!COLL[b.id] && COLL[b.id].etat === e.k}" title="${e.long}" aria-label="${e.long} : ${esc(b.titre)}">${ABREGE[e.k]}</button>`).join('')}</div></div>`).join('')}</div>`;
    majCompteur(liste);
    const dernier = P.i === P.file.length - 1;
    pied(bouton('prec', '← Précédent', 'bouton-clair'), bouton('suiv', dernier ? 'Terminer →' : 'Liste suivante →'), '');
  }
  function majCompteur(liste) {
    const n = liste.filter((b) => COLL[b.id]).length;
    $('#pl-compteur').innerHTML = `${n} <span class="sur">coché${n > 1 ? 's' : ''} sur ${liste.length}</span>`;
  }
  const ABREGE = { convenable: 'C', bon: 'BE', tres_bon: 'TBE' };
  // met à jour une couverture et ses trois boutons d'état d'après la collection
  function majTuile(b) {
    const t = document.querySelector(`.tuile-livre[data-livre="${CSS.escape(b.id)}"]`);
    if (t) t.setAttribute('aria-pressed', String(!!COLL[b.id]));
    document.querySelectorAll(`[data-etat-livre="${CSS.escape(b.id)}"]`).forEach((el) => el.setAttribute('aria-pressed', String(!!COLL[b.id] && COLL[b.id].etat === el.dataset.e)));
  }
  function cocher(b, oui) {
    if (oui) COLL[b.id] = { etat: P.etat, qte: (COLL[b.id] && COLL[b.id].qte) || 1, ...gv(COLL[b.id]) };
    else delete COLL[b.id];
    majTuile(b);
  }
  // C / BE / TBE : choisit l'état d'un livre ; retoucher l'état déjà choisi retire le livre
  function etatRapide(b, etat) {
    if (COLL[b.id] && COLL[b.id].etat === etat) delete COLL[b.id];
    else COLL[b.id] = { etat, qte: (COLL[b.id] && COLL[b.id].qte) || 1, ...gv(COLL[b.id]) };
    majTuile(b);
  }
  function parseNumeros(txt) {
    const set = new Set();
    String(txt).split(/[,;\s]+/).filter(Boolean).forEach((tok) => {
      const m = tok.match(/^(\d+)\s*[-–àa]\s*(\d+)$/i);
      if (m) { let a = +m[1], z = +m[2]; if (a > z) [a, z] = [z, a]; for (let k = a; k <= z && k - a < 2000; k += 1) set.add(k); }
      else if (/^\d+$/.test(tok)) set.add(+tok);
    });
    return set;
  }

  function etapeFin() {
    const bl = bilan();
    tete('Terminé', bl.exemplaires ? 'Votre inventaire est prêt' : 'Aucun livre coché', 100);
    if (!bl.exemplaires) {
      $('#parcours-corps').innerHTML = '<p>Vous n\'avez coché aucun livre. Revenez en arrière pour choisir des séries et des éditions, ou fermez et ajoutez vos livres un par un avec C, BE ou TBE sous les jaquettes.</p>';
      pied(bouton('debut', '← Recommencer', 'bouton-clair'), bouton('fermer', 'Fermer'));
      return;
    }
    $('#parcours-corps').innerHTML = `
      <div class="bilan">
        <div class="sceau" role="img" aria-label="Patrimoine estimé : ${fmtE(bl.total)}"><span class="sceau-lib">Patrimoine estimé</span><span class="sceau-prix">${fmtE(bl.total)}</span><span class="sceau-etat">${pl(bl.exemplaires, 'exemplaire')}</span></div>
        <div>
          <dl class="stats">
            <div><dt>Titres</dt><dd>${bl.titres}<small>${pl(bl.lignes.length, 'édition')}</small></dd></div>
            <div><dt>Plancher</dt><dd>${fmtE(bl.bas)}<small>tout en convenable</small></dd></div>
            <div><dt>Plafond</dt><dd>${fmtE(bl.haut)}<small>tout en <abbr title="Très bon état">TBE</abbr></small></dd></div>
          </dl>
          <p class="trois">${esc(texteEstimation(bl))}</p>
          ${bl.sansCote ? `<p class="sans-cote">${pl(bl.sansCote, 'exemplaire')} sans cote pour l'état choisi : non compté${bl.sansCote > 1 ? 's' : ''} dans le total.</p>` : ''}
        </div>
      </div>
      <p><strong>Gardez votre fichier.</strong> Votre collection est enregistrée ${dansCompte() ? 'dans votre compte et sur cet appareil' : 'dans ce navigateur'} ; le fichier JSON en est une copie que vous gardez chez vous. Vous pourrez le recharger ici (« Importer une liste ») sur n'importe quel appareil.</p>
      <div class="coll-actions">
        <button type="button" class="bouton" id="pa-json">Télécharger mon fichier (JSON)</button>
        <button type="button" class="bouton bouton-clair" id="pa-csv">Télécharger en CSV</button>
      </div>`;
    pied(bouton('prec', '← Modifier mes listes', 'bouton-clair'), bouton('voir', 'Voir ma collection'));
  }

  function brancherParcours() {
    const dlg = $('#parcours');
    document.addEventListener('click', (e) => { if (e.target.closest('[data-parcours]')) ouvrirParcours(); });
    $('#parcours-fermer').addEventListener('click', () => dlg.close());
    dlg.addEventListener('close', () => { afficher(); });
    dlg.addEventListener('change', (e) => {
      if (e.target.name === 'pe-etat') { P.etat = e.target.value; memoriser(); }
      if (e.target.id === 'pe-fichier') {
        const f = e.target.files[0];
        if (!f) return;
        f.text().then((texte) => {
          const r = importer(texte), st = $('#pe-statut');
          e.target.value = '';
          if (r.erreur || (!r.ajoutes && !r.maj)) { st.textContent = r.erreur || 'Aucun livre de ce fichier n\'a été reconnu.'; st.classList.add('erreur'); return; }
          depuisCollection();
          P.message = `${resumeImport(r)} Vos séries et éditions sont déjà cochées : vérifiez, complétez, puis continuez.`;
          P.phase = 'series'; rendre();
        }).catch(() => { const st = $('#pe-statut'); st.textContent = 'Ce fichier n\'a pas pu être lu.'; st.classList.add('erreur'); });
        return;
      }
      if (e.target.id === 'pl-etat') {
        P.etat = e.target.value;
        const { serie, v } = P.file[P.i];
        livresDe(serie, v).forEach((b) => { if (COLL[b.id]) COLL[b.id].etat = P.etat; majTuile(b); });
        sauverColl();
        const r = $('#pl-retour'); if (r) r.textContent = `État « ${etatDe(P.etat).long.toLowerCase()} » appliqué aux livres cochés de cette liste.`;
      }
    });
    dlg.addEventListener('click', (e) => {
      const t = e.target.closest('button');
      if (!t) return;
      if (t.dataset.serie) {                                   // tuile de série
        const on = t.getAttribute('aria-pressed') !== 'true';
        t.setAttribute('aria-pressed', String(on));
        if (on) P.series.add(t.dataset.serie); else P.series.delete(t.dataset.serie);
        majPiedSeries(); memoriser(); return;
      }
      if (t.dataset.cell) {                                    // cellule série × édition
        const on = t.getAttribute('aria-pressed') !== 'true';
        t.setAttribute('aria-pressed', String(on));
        if (on) P.cellules.add(t.dataset.cell); else P.cellules.delete(t.dataset.cell);
        majPiedEditions(); memoriser(); return;
      }
      if (t.dataset.col) {                                     // « Tout » d'une colonne d'édition
        const cs = cellulesDe(t.dataset.col);
        const tout = cs.length > 0 && cs.every((c) => P.cellules.has(c));
        cs.forEach((c) => { if (tout) P.cellules.delete(c); else P.cellules.add(c); });
        majMatrice(); majPiedEditions(); memoriser(); return;
      }
      if (t.dataset.ongl) {                                    // autre édition de la série, depuis la liste
        const { serie } = P.file[P.i];
        P.cellules.add(cleCell(serie, t.dataset.ongl));
        construireFile();
        const k = P.file.findIndex((x) => x.serie === serie && x.v === t.dataset.ongl);
        P.i = Math.max(0, k); rendre(); return;
      }
      if (t.dataset.etatLivre) {                               // C / BE / TBE
        const b = livreDe(t.dataset.etatLivre);
        etatRapide(b, t.dataset.e);
        sauverColl(); memoriser();
        const { serie, v } = P.file[P.i]; majCompteur(livresDe(serie, v)); return;
      }
      if (t.dataset.livre) {                                   // couverture
        const b = livreDe(t.dataset.livre);
        cocher(b, t.getAttribute('aria-pressed') !== 'true');
        sauverColl();
        memoriser(); const { serie, v } = P.file[P.i]; majCompteur(livresDe(serie, v)); return;
      }
      if (t.id === 'pa-json') { exporter('json'); return; }
      if (t.id === 'pa-csv') { exporter('csv'); return; }
      const act = t.dataset.pa;
      if (!act) return;
      const liste = P.phase === 'liste' ? livresDe(P.file[P.i].serie, P.file[P.i].v) : [];
      if (act === 'tout' || act === 'rien') {
        liste.forEach((b) => cocher(b, act === 'tout'));
        if (act === 'tout') liste.forEach((b) => { COLL[b.id].etat = P.etat; });
        sauverColl(); memoriser(); majCompteur(liste);
        $('#pl-retour').textContent = act === 'tout' ? 'Toute l\'édition est cochée : touchez les livres qui vous manquent pour les décocher.' : 'Tout est décoché.';
        return;
      }
      if (act === 'num') {
        const voulus = parseNumeros($('#pl-num').value);
        if (!voulus.size) { $('#pl-retour').textContent = 'Indiquez des numéros, par exemple « 252, 267-272 ».'; return; }
        let n = 0; const trouves = new Set();
        liste.forEach((b) => { if (voulus.has(numDe(b))) { cocher(b, true); n += 1; trouves.add(numDe(b)); } });
        sauverColl(); majCompteur(liste);
        const manquants = [...voulus].filter((k) => !trouves.has(k));
        $('#pl-retour').textContent = `${pl(n, 'livre')} coché${n > 1 ? 's' : ''}` + (manquants.length ? ` · numéros absents de cette liste : ${manquants.slice(0, 6).join(', ')}${manquants.length > 6 ? '…' : ''}` : '') + '.';
        return;
      }
      if (act === 'cells-tout' || act === 'cells-rien') {
        toutesCellules(act === 'cells-tout');
        majMatrice(); majPiedEditions(); memoriser(); return;
      }
      if (act === 'series-tout' || act === 'series-rien') {
        const tout = act === 'series-tout';
        document.querySelectorAll('#pa-series .tuile-serie').forEach((el) => {
          el.setAttribute('aria-pressed', String(tout));
          if (tout) P.series.add(el.dataset.serie); else P.series.delete(el.dataset.serie);
        });
        majPiedSeries(); memoriser(); return;
      }
      if (act === 'fermer') { dlg.close(); return; }
      if (act === 'commencer') { P.phase = 'series'; rendre(); return; }
      if (act === 'sauve') { exporter('json'); return; }
      if (act === 'reprendre') {
        P.message = '';
        if (REPRISE && REPRISE.phase !== 'series') {
          P.phase = REPRISE.phase;
          if (REPRISE.phase === 'liste') {
            construireFile();
            if (P.file.length) P.i = Math.min(Math.max(REPRISE.i, 0), P.file.length - 1); else P.phase = 'editions';
          }
        } else P.phase = 'series';
        rendre(); return;
      }
      if (act === 'zero') {
        if (window.confirm(dansCompte() ? 'Effacer toute votre collection, y compris dans votre compte Google ? Pensez à la sauvegarder avant : cette action est définitive.' : 'Effacer toute votre collection de ce navigateur ? Pensez à la sauvegarder avant : cette action est définitive.')) {
          COLL = {}; sauverColl(); try { localStorage.removeItem(CLE_P); } catch (err) { /* sans effet */ }
          afficher(); ouvrirParcours();
        }
        return;
      }
      if (act === 'debut') { P.phase = 'series'; rendre(); return; }
      if (act === 'fin') { P.phase = 'fin'; rendre(); return; }
      if (act === 'voir') {
        if (PAGE === 'collection') { dlg.close(); $('#collection').scrollIntoView({ behavior: 'smooth', block: 'start' }); } else location.href = 'collection.html';
        return;
      }
      if (act === 'suiv') {
        if (P.phase === 'series') P.phase = 'editions';
        else if (P.phase === 'editions') { construireFile(); P.i = 0; P.phase = P.file.length ? 'liste' : 'fin'; }
        else if (P.phase === 'liste') { if (P.i < P.file.length - 1) P.i += 1; else P.phase = 'fin'; }
        rendre(); return;
      }
      if (act === 'prec') {
        if (P.phase === 'series') P.phase = 'intro';
        else if (P.phase === 'editions') P.phase = 'series';
        else if (P.phase === 'liste') { if (P.i > 0) P.i -= 1; else P.phase = 'editions'; }
        else if (P.phase === 'fin') { if (P.file.length) { P.i = P.file.length - 1; P.phase = 'liste'; } else P.phase = 'editions'; }
        rendre();
      }
    });
  }

  /* ---------- Pied de page ---------- */
  function afficherPied() {
    const minus = (t) => t.charAt(0).toLowerCase() + t.slice(1);
    $('#etats-def').innerHTML = ETATS.map((e) =>
      `<strong>${e.k === 'tres_bon' ? '<abbr title="Très bon état">TBE</abbr>' : e.court}</strong> : ${esc(minus(e.def.replace(' TBE signifie « très bon état ».', '')))}`).join('<br>');
    $('#pied-sources').innerHTML = prixAnciens()
      ? `Prix : ancien relevé, qui n'est plus mis à jour. Ils indiquent un ordre de grandeur, pas la cote du jour.`
      : `Prix : cotes d'archives (ancien relevé), complétées pour ${nbActuels()} cote${nbActuels() > 1 ? 's' : ''} par des prix actuels (annonces et ventes constatées). Une annonce est un prix demandé, pas un prix payé.`;
    const avis = $('#avis-prix');
    if (avis) avis.innerHTML = prixAnciens()
      ? "<strong>Cotes d'archives.</strong> Les prix viennent d'un ancien relevé, qui n'est plus tenu à jour : lisez-les comme un repère de grandeur, pas comme la cote du jour. Pour ajouter un livre à votre collection, cliquez sur son état&nbsp;: <strong>C</strong>, <strong>BE</strong> ou <strong>TBE</strong>."
      : `<strong>Prix actuels en cours d'ajout.</strong> ${nbActuels() > 1 ? `${nbActuels()} cotes reposent` : '1 cote repose'} sur des prix récents ; les autres restent des cotes d'archives, à lire comme un repère de grandeur. Pour ajouter un livre à votre collection, cliquez sur son état&nbsp;: <strong>C</strong>, <strong>BE</strong> ou <strong>TBE</strong>.`;
    $('#pied-meta').textContent = `${META.nb_versions} éditions · ${META.nb_livres} livres · ${META.nb_series} séries · données du ` +
      new Date(META.genere_le).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) + '.';
  }

  /* ---------- Maison et logo : retour tout en haut de l'accueil, sans toucher aux filtres ---------- */
  document.addEventListener('click', (e) => {
    const maison = e.target.closest('a[href="#haut"]');
    if (!maison) return;
    e.preventDefault();
    window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  });

  /* ---------- Barre du bas (téléphones) : section en cours et clavier ---------- */
  (function barreBas() {
    const liens = [...document.querySelectorAll('#barre-bas a[data-sec]')];
    const idsDe = (l) => l.dataset.sec.split(' ');
    const sections = [...new Set(liens.flatMap(idsDe))].map((id) => document.getElementById(id)).filter(Boolean);
    if ('IntersectionObserver' in window && sections.length) {
      const io = new IntersectionObserver((entrees) => {
        entrees.forEach((e) => {
          if (!e.isIntersecting) return;
          liens.forEach((l) => { if (idsDe(l).includes(e.target.id)) l.setAttribute('aria-current', 'location'); else l.removeAttribute('aria-current'); });
        });
      }, { rootMargin: '-35% 0px -60% 0px' });
      sections.forEach((s) => io.observe(s));
    }
    // le clavier virtuel pousse les barres fixes au-dessus des champs : on masque la barre pendant la saisie
    const champ = (el) => el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) && !['checkbox', 'radio', 'button', 'file'].includes(el.type);
    document.addEventListener('focusin', (e) => { if (champ(e.target)) document.body.classList.add('clavier'); });
    document.addEventListener('focusout', () => document.body.classList.remove('clavier'));
  })();

  /* ---------- Application installable (PWA) ---------- */
  if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol)) {
    window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => { /* hors ligne indisponible, sans conséquence */ }));
  }

  // Arrivée sur « #recherche » depuis une autre page : la page se met en place après le premier défilement (jaquettes, polices),
  // qui s'arrêtait alors trop haut. On recale la section, sans animation, jusqu'à ce que la page soit stable.
  if (PAGE !== 'collection' && location.hash === '#recherche') {
    const caler = () => {
      const el = $('#recherche'), html = document.documentElement;
      if (!el) return;
      html.style.scrollBehavior = 'auto';
      el.scrollIntoView({ block: 'start' });
      html.style.scrollBehavior = '';
    };
    requestAnimationFrame(caler);
    window.addEventListener('load', caler, { once: true });
    [400, 1200].forEach((ms) => setTimeout(caler, ms));
  }

  charger();
})();
