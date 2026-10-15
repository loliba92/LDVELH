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
  const norm = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const etatDe = (k) => ETATS.find((e) => e.k === k) || ETATS[1];
  const racine = (b) => b || null;
  const numero = (b) => (b.numero && b.numero !== '000' ? ` n° ${b.numero}` : '');

  let DATA = [];
  let META = {};
  let VERSIONS = [];
  let limite = PAR_PAGE;
  let S = {};

  const defaut = () => ({
    q: '', serie: '', ed: '', amin: '', amax: '', pmin: '', pmax: '', vente: false, onglet: 'etagere', versions: new Set(VERSIONS),
    h: 'bon', vue: 'etagere', tri: 'serie', g: 'serie', mine: false,
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
    // Une fois sur six en haut de l'accueil, une fois sur deux sur « Ma collection » : le mur de jaquettes ; sinon l'illustration
    if (document.documentElement.dataset.accueil === '6') murJaquettes('.hero', matchMedia('(max-width: 900px)').matches ? 12 : 30);
    if (Math.random() < 0.5) murJaquettes('.banniere', matchMedia('(max-width: 700px)').matches ? 8 : 18);
    DATA.forEach((b) => { b._txt = norm([b.titre, b.livre, b.auteurs, b.isbn13, b.serie, b.editeur].join(' ')); });
    VERSIONS = [...new Set(DATA.map((b) => b.version))].sort();
    S = defaut();
    chargerColl();
    if (PAGE === 'collection') { initPageCollection(); return; }
    construireHero();
    construireControles();
    lireAdresse();
    synchroniser();
    basculerSelecteur(!window.matchMedia('(max-width: 1000px)').matches);
    afficher();
    if (new URLSearchParams(location.search).has('inventaire')) {   // lien « Inventaire » des pages annexes
      history.replaceState(null, '', location.pathname + location.hash);
      ouvrirParcours();
    }
  }

  /* ---------- En-tête : chiffres et éventail de jaquettes ---------- */
  function construireHero() {
    $('#chiffres-hero').textContent = `${META.nb_versions} éditions · ${META.nb_livres} livres · ${META.nb_series} séries`;
    const top = [...compter('serie').entries()].filter(([k]) => k).sort((x, y) => y[1] - x[1] || x[0].localeCompare(y[0], 'fr')).slice(0, 4);
    $('#hero-series').innerHTML = '<span>Séries :</span>' + top.map(([k, n]) =>
      `<button type="button" class="pastille" data-serie="${esc(k)}" title="${n} éditions">${esc(k)}</button>`).join('');
    const aller = () => $('#recherche').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    $('#hero-recherche').addEventListener('submit', (e) => {
      e.preventDefault();
      S.q = $('#h-q').value.trim(); S.onglet = 'etagere';
      synchroniser(); changer(); aller();
    });
    $('#hero-series').addEventListener('click', (e) => {
      const b = e.target.closest('[data-serie]');
      if (!b) return;
      S.serie = b.dataset.serie; S.onglet = 'etagere';
      synchroniser(); changer(); aller();
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
    $('#f-pmin').addEventListener('input', (e) => { S.pmin = e.target.value; changer(); });
    $('#f-pmax').addEventListener('input', (e) => { S.pmax = e.target.value; changer(); });
    $('#f-vente').addEventListener('change', (e) => { S.vente = e.target.checked; changer(); });
    $('#f-mine').addEventListener('change', (e) => { S.mine = e.target.checked; synchroniser(); changer(); });
    document.querySelectorAll('#f-coll input').forEach((r) => r.addEventListener('change', (e) => { if (e.target.checked) { S.mine = e.target.value === 'mine'; synchroniser(); changer(); } }));
    brancherParcours();
    $('#f-versions').addEventListener('change', (e) => {
      if (e.target.checked) S.versions.add(e.target.value); else S.versions.delete(e.target.value);
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
    window.addEventListener('hashchange', () => {
      const h = location.hash.slice(1);
      if (h && !h.includes('=')) return;      // simple ancre de section (#cote, #apropos…) : les filtres restent
      lireAdresse(); synchroniser(); afficher();
    });
    let attente;
    window.addEventListener('resize', () => { clearTimeout(attente); attente = setTimeout(afficher, 150); });
  }

  function synchroniser() {
    $('#f-q').value = S.q; if ($('#h-q')) $('#h-q').value = S.q; $('#f-serie').value = S.serie; $('#f-ed').value = S.ed;
    $('#f-amin').value = S.amin; $('#f-amax').value = S.amax; $('#f-pmin').value = S.pmin; $('#f-pmax').value = S.pmax;
    $('#prix-etat').textContent = `en ${etatDe(S.h).long.toLowerCase()}`;
    $('#f-vente').checked = S.vente; $('#f-mine').checked = S.mine;
    document.querySelectorAll('#f-coll input').forEach((r) => { r.checked = (r.value === 'mine') === S.mine; });
    $('#f-tri').value = S.tri; $('#f-groupe').value = S.g;
    document.querySelectorAll('#f-versions input').forEach((i) => { i.checked = S.versions.has(i.value); });
    document.querySelectorAll('#h-etats input').forEach((i) => { i.checked = i.value === S.h; });
    document.querySelectorAll('#f-vue input').forEach((i) => { i.checked = i.value === S.vue; });
  }

  function changer() { limite = PAR_PAGE; ecrireAdresse(); afficher(); }

  function nbFiltres() {
    return [S.q.trim(), S.serie, S.ed, S.amin || S.amax, S.pmin !== '' || S.pmax !== '', S.vente, S.mine, S.versions.size !== VERSIONS.length].filter(Boolean).length;
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
    if (S.versions.size !== d.versions.size) p.set('v', [...S.versions].join(','));
    if (S.h !== 'bon') p.set('h', S.h);
    if (S.vue !== 'etagere') p.set('vue', S.vue);
    if (S.tri !== 'serie') p.set('tri', S.tri);
    if (S.g !== 'serie') p.set('g', S.g);
    if (S.onglet !== 'etagere') p.set('onglet', S.onglet);
    const h = p.toString();
    history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
  }
  function lireAdresse() {
    const p = new URLSearchParams(location.hash.slice(1));
    S = defaut();
    S.q = p.get('q') || ''; S.serie = p.get('serie') || ''; S.ed = p.get('ed') || '';
    S.amin = p.get('amin') || ''; S.amax = p.get('amax') || ''; S.pmin = p.get('pmin') || ''; S.pmax = p.get('pmax') || ''; S.vente = p.get('vente') === '1'; S.mine = p.get('mine') === '1';
    if (p.has('v')) S.versions = new Set(p.get('v').split(',').filter((v) => VERSIONS.includes(v)));
    if (ETATS.some((e) => e.k === p.get('h'))) S.h = p.get('h');
    if (['etagere', 'liste', 'groupe'].includes(p.get('vue'))) S.vue = p.get('vue');
    if (['serie', 'titre', 'annee', 'cher', 'pascher'].includes(p.get('tri'))) S.tri = p.get('tri');
    if (['serie', 'version', 'annee', 'decennie', 'editeur'].includes(p.get('g'))) S.g = p.get('g');
    if (['cote', 'etagere'].includes(p.get('onglet'))) S.onglet = p.get('onglet');
  }

  /* ---------- Calculs ---------- */
  const libTranche = (mini, maxi) => (mini !== '' && maxi !== '' ? `${fmtN(+mini)} à ${fmtN(+maxi)} €` : (mini !== '' ? `à partir de ${fmtN(+mini)} €` : `moins de ${fmtN(+maxi)} €`));
  function filtrer(avecPrix = true) {
    const q = norm(S.q.trim());
    const k = etatDe(S.h).k;
    const pmin = avecPrix && S.pmin !== '' ? +S.pmin : null;
    const pmax = avecPrix && S.pmax !== '' ? +S.pmax : null;
    const amin = S.amin ? +S.amin : null;
    const amax = S.amax ? +S.amax : null;
    return DATA.filter((b) =>
      (!q || b._txt.includes(q)) && (!S.serie || b.serie === S.serie) && S.versions.has(b.version) &&
      (!S.ed || (b.editeur || 'Non renseigné') === S.ed) &&
      (amin === null || (b.annee && b.annee >= amin)) && (amax === null || (b.annee && b.annee <= amax)) &&
      (!S.vente || b.en_vente === 1) && (!S.mine || COLL[b.id]) &&
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
  function texteEstimation(bl) {
    if (prixAnciens()) return "Estimation d'après les cotes d'archives et l'état que vous indiquez. Elle ne remplace ni une expertise ni un prix de vente réel.";
    return `Estimation d'après les cotes de la sélection et l'état que vous indiquez : ${bl.actuels} exemplaire${bl.actuels > 1 ? 's' : ''} sur ${bl.exemplaires - bl.sansCote} ` +
      `${bl.actuels > 1 ? 'reposent' : 'repose'} sur des prix actuels, les autres sur des cotes d'archives. Elle ne remplace ni une expertise ni un prix de vente réel.`;
  }

  /* ---------- Affichage général ---------- */
  // Onglets « Cote de la sélection » / « Sur l'étagère » : un seul panneau à la fois, sans défilement
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
    appliquerOnglet();
    const liste = filtrer();
    const nf = nbFiltres();
    $('#nb-filtres').textContent = nf ? String(nf) : '';
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
      $('#resultats').innerHTML = '<p class="vide-global">Aucun livre ne répond à ces critères. Élargissez la sélection ou effacez un filtre.</p>';
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
      const poss = COLL[b.id];
      return `<article class="livre-carte${poss ? ' possede-oui' : ''}">
        <button type="button" class="ouvrir" data-id="${esc(b.id)}" aria-label="${esc(b.titre)}, édition ${esc(b.version)}${p != null ? ', ' + fmt(p) + ' en ' + e.long.toLowerCase() : ''}">
          <span class="couv">${b.couverture
            ? `<img src="${esc(racine(b.couverture))}" alt="" width="88" height="124" loading="lazy" decoding="async" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">`
            : tuile(b)}<span class="tampon-v">${esc(b.version)}</span></span>
          <span class="infos"><span class="titre">${esc(b.titre)}</span><span class="meta" style="display:block">${esc(b.serie)}${esc(numero(b))}${b.annee ? ' · ' + b.annee : ''}</span></span>
          <span class="prix${p == null ? ' nul' : ''}">${p == null ? 'Cote indisponible' : fmt(p)}${p == null ? '' : `<small>${e.k === 'tres_bon' ? 'TBE' : esc(e.court.toLowerCase())}</small>`}</span>
        </button>
        <div class="etats-carte" role="group" aria-label="Ajouter à ma collection : ${esc(b.titre)}, édition ${esc(b.version)}">${ETATS.map((x) =>
          `<button type="button" data-etat-possede="${esc(b.id)}" data-e="${x.k}" aria-pressed="${!!poss && poss.etat === x.k}" title="${poss && poss.etat === x.k ? 'Dans ma collection en ' + x.long.toLowerCase() + ' : retirer' : 'Ajouter en ' + x.long.toLowerCase()}" aria-label="${poss && poss.etat === x.k ? 'Retirer de ma collection' : 'Ajouter en ' + x.long.toLowerCase()} : ${esc(b.titre)}, édition ${esc(b.version)}">${ABREGE[x.k]}</button>`).join('')}</div>
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
  // Recherche de cette édition sur trois sites d'annonces (liens simples, ouverts dans un nouvel onglet)
  const requete = (t) => encodeURIComponent(t).replace(/%20/g, '+');
  function blocRecherche(b) {
    // Titre + « ldvelh » : ces sites exigent tous les mots, et les vendeurs écrivent « ldvelh » (livre dont vous êtes le héros),
    // presque jamais « V1 » ni « livre héros » (recherche vide constatée avec ces mots)
    const titre = b.titre.replace(/\s*\([^)]*\)/g, '').trim();                          // « (Grand format) » et autres parenthèses : absents des annonces
    const q = requete(`${titre} ldvelh`.replace(/\s+/g, ' '));
    const ebay = requete(`${titre} ${b.isbn13 || 'livre héros'}`);
    const liens = [
      ['Vinted', `https://www.vinted.fr/catalog?search_text=${q}`],
      ['Leboncoin', `https://www.leboncoin.fr/recherche?text=${q}&sort=time`],
      ['eBay', `https://www.ebay.fr/sch/i.html?_nkw=${ebay}`],
    ];
    return `<h3>Chercher cette édition en vente</h3>
        <p class="liens-vente">${liens.map(([nom, url]) => `<a class="bouton bouton-clair" href="${url}" target="_blank" rel="noopener noreferrer" aria-label="Chercher ${esc(b.titre)} sur ${nom} (nouvel onglet)">${nom}</a>`).join('')}</p>
        <p class="sous">Recherches sur des sites extérieurs, dans un nouvel onglet. Le guide n'y est affilié à aucun titre.</p>`;
  }

  /* ---------- Correction des cotes depuis la fiche (propriétaire) ---------- */
  // Visible seulement si la porte de la page privée a été ouverte sur cet appareil (même empreinte que acces.js).
  // L'envoi lance le lot « Corriger des cotes » sur GitHub avec un jeton enregistré dans la page privée (jamais dans le dépôt).
  const CLE_ACCES = 'cdh-acces', CLE_JETON = 'cdh-jeton';
  const EMPREINTE = '84542babc81672662f9b777a4bde6f7b72518fdb1e8bb704437a4fa4e6d34b4e';
  const lireLoc = (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const estProprietaire = () => lireLoc(CLE_ACCES) === EMPREINTE;
  const LIEN_CORRIGER = 'https://github.com/loliba92/LDVELH/actions/workflows/corriger-prix.yml';
  function blocCorriger(b) {
    if (!estProprietaire()) return '';
    if (!b.isbn13) return '<h3>Corriger les cotes</h3><p class="sous">Cette fiche n\'a pas d\'ISBN : la correction n\'est pas possible ici.</p>';
    const champ = ([k, nom]) => `<label>${nom}<input type="text" inputmode="decimal" name="${k}" autocomplete="off" placeholder="${b.prix[k] == null ? '—' : String(b.prix[k]).replace('.', ',')}"></label>`;
    return `<h3>Corriger les cotes</h3>
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
      const jeton = lireLoc(CLE_JETON);
      if (!jeton) {
        try { await navigator.clipboard.writeText(ligne); } catch (e) { /* copie impossible : la ligne reste affichée */ }
        msg.innerHTML = `Pas de jeton enregistré : la ligne <code>${esc(ligne)}</code> est copiée. Ouvrez <a href="${LIEN_CORRIGER}" target="_blank" rel="noopener">le lot « Corriger des cotes »</a>, « Run workflow », collez-la. Pour l'envoi en un clic, enregistrez votre jeton dans la page privée « Vérifier les prix ».`;
        msg.hidden = false;
        return;
      }
      f.querySelector('button').disabled = true; dire('Envoi en cours…');
      try {
        const r = await fetch('https://api.github.com/repos/loliba92/LDVELH/actions/workflows/corriger-prix.yml/dispatches', {
          method: 'POST',
          headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${jeton}`, 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json' },
          body: JSON.stringify({ ref: 'main', inputs: { corrections: ligne } }) });
        if (r.status === 204) dire('Envoyé. Le site sera à jour dans environ 2 minutes : rechargez la page ensuite.');
        else if (r.status === 401 || r.status === 403) dire('Le jeton est refusé ou expiré : enregistrez-en un nouveau dans la page privée.');
        else if (r.status === 404) dire('Le jeton n\'a pas accès à ce dépôt (ou le lot est introuvable) : vérifiez ses droits.');
        else dire(`Échec de l'envoi (code ${r.status}).`);
      } catch (e) { dire('Envoi impossible : vérifiez votre connexion.'); }
      f.querySelector('button').disabled = false;
    });
  }

  function ouvrirFiche(id) {
    const b = DATA.find((x) => x.id === id);
    if (!b) return;
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
        <p class="sous legende-prix">${legendePrix(b, sel.k)}</p>
        ${blocNeuf(b)}
        ${blocRecherche(b)}
        ${blocCorriger(b)}
        ${blocCollectionFiche(b)}
        ${autres.length > 1 ? `<h3>Les ${autres.length} éditions de ce livre</h3>
        <div class="autres">${autres.map((x) => `<button type="button" class="autre${x.id === b.id ? ' courante' : ''}" data-autre="${esc(x.id)}" aria-label="Édition ${esc(x.version)}${x.annee ? ', ' + x.annee : ''}">
          ${x.couverture ? `<img src="${esc(racine(x.couverture))}" alt="" width="88" height="124" loading="lazy" data-i="${esc((x.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(x)}
          <span class="v">${esc(x.version)}<small>${x.annee ?? ''}</small></span><span class="p">${fmt(x.prix[sel.k])}</span></button>`).join('')}</div>` : ''}
        ${prixAnciens() ? `<p class="sous" style="margin-top:16px">Cotes d'archives, issues d'un ancien relevé qui n'est plus mis à jour : un ordre de grandeur, pas la cote du jour.</p>` : ''}
      </div>`;
    const dlg = $('#fiche');
    brancherFicheCollection(b);
    brancherCorriger();
    $('#fermer').addEventListener('click', () => dlg.close());
    $('#fiche-contenu').querySelectorAll('[data-autre]').forEach((el) =>
      el.addEventListener('click', () => { if (el.dataset.autre !== b.id) ouvrirFiche(el.dataset.autre); }));
    if (!dlg.open) dlg.showModal();
    dlg.scrollTop = 0;
  }

  // Clic sur une carte ou un titre
  document.addEventListener('click', (e) => {
    const etatBtn = e.target.closest('button[data-etat-possede]');
    if (etatBtn) { basculerPossede(etatBtn.dataset.etatPossede, etatBtn.dataset.e); return; }
    const carte = e.target.closest('button[data-id]');
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
  let stockageOk = true;
  const chargerColl = () => {
    try { COLL = JSON.parse(localStorage.getItem(CLE) || '{}') || {}; } catch (e) { COLL = {}; stockageOk = false; }
    // Frais de port gardés à part par une version précédente : ils rejoignent le prix payé du livre (livraison comprise)
    Object.values(COLL).forEach((c) => { if (c && c.port > 0) { if (c.prix != null) c.prix = Math.round((c.prix + c.port / (c.qte || 1)) * 100) / 100; delete c.port; } else if (c) delete c.port; });
  };
  const sauverColl = () => {
    try { localStorage.setItem(CLE, JSON.stringify(COLL)); stockageOk = true; } catch (e) { stockageOk = false; }
  };
  const annonce = (t) => { $('#annonce').textContent = ''; setTimeout(() => { $('#annonce').textContent = t; }, 30); };
  const parId = () => new Map(DATA.map((b) => [b.id, b]));
  let INDEX = null;
  const livreDe = (id) => (INDEX || (INDEX = parId())).get(id);

  // C / BE / TBE sur une jaquette : ajoute le livre dans cet état ; retoucher l'état choisi le retire
  function basculerPossede(id, etat) {
    const b = livreDe(id);
    if (!b) return;
    if (COLL[id] && COLL[id].etat === etat) { delete COLL[id]; annonce(`${b.titre} retiré de votre collection.`); }
    else {
      COLL[id] = { etat, qte: (COLL[id] && COLL[id].qte) || 1 };
      annonce(`${b.titre} : en ${etatDe(etat).long.toLowerCase()} dans votre collection.`);
    }
    sauverColl();
    afficher();
  }
  const valeurLigne = (b, c) => (b.prix[c.etat] == null ? null : b.prix[c.etat] * c.qte);
  // Prix payé (facultatif, par exemplaire) : un nombre entre 0,01 et 2000 €, virgule ou point acceptés
  const lirePrix = (t) => { const n = parseFloat(String(t ?? '').replace(',', '.')); return Number.isFinite(n) && n > 0 && n <= 2000 ? Math.round(n * 100) / 100 : null; };
  const prixSaisi = (p) => (p == null ? '' : String(p).replace('.', ','));

  function bilan() {
    const lignes = Object.entries(COLL).map(([id, c]) => ({ b: livreDe(id), c })).filter((x) => x.b);
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

  function afficherCollection() {
    const bl = bilan();
    const n = bl.exemplaires;
    ['#nb-coll', '#nb-coll-bas'].forEach((sel) => {
      $(sel).textContent = n ? String(n) : '';
      $(sel).setAttribute('aria-label', n ? `${n} exemplaire${n > 1 ? 's' : ''}` : '');
    });
    if ($('#nb-coll-seg')) $('#nb-coll-seg').textContent = n ? `(${n})` : '';
    if ($('#hero-coll')) {              // accueil : résumé de la collection et lien vers la page collection
      $('#hc-etat').textContent = n ? `${bl.titres} titre${bl.titres > 1 ? 's' : ''} · ${n} exemplaire${n > 1 ? 's' : ''}` : "vide pour l'instant";
      const ch = $('#hc-chiffres');
      ch.hidden = !n;
      ch.innerHTML = n ? `Valeur estimée <strong>${fmtE(bl.total)}</strong>${bl.nbPayes ? ` · Investi <strong>${fmtE(bl.investi)}</strong>` : ''}` : '';
      $('#hero-parcours').textContent = n ? 'Compléter pas à pas' : 'Constituer pas à pas';
    }
    if (!$('#collection')) return;      // l'accueil n'affiche que les pastilles ; la section est sur la page collection
    $('#coll-compte').textContent = n ? `${bl.titres} titre${bl.titres > 1 ? 's' : ''} · ${n} exemplaire${n > 1 ? 's' : ''}` : 'vide pour l\'instant';
    $('#coll-prive').innerHTML = (stockageOk
      ? 'Votre collection reste dans ce navigateur, sur cet appareil : rien n\'est envoyé et aucun compte n\'est nécessaire. Exportez-la pour la sauvegarder, ou créez un lien de transfert pour la retrouver sur un autre appareil.'
      : '<strong>Le stockage local est indisponible</strong> (navigation privée ?) : votre collection sera perdue à la fermeture. Exportez-la pour la conserver.');
    const zone = $('#coll-corps');
    if (!n) {
      zone.innerHTML = `<div class="coll-vide"><p>Constituez ici votre collection pour en estimer la valeur.</p>
        <p>Le plus rapide : l'<strong>inventaire guidé</strong>. Vous indiquez vos séries, vos éditions, puis vous cochez vos couvertures. Vous pouvez aussi toucher <strong>C, BE ou TBE</strong> sur une jaquette de l'étagère, ou importer une liste d'ISBN ci-dessous.</p>
        <p><button type="button" class="bouton" data-parcours>Constituer ma collection pas à pas</button> <button type="button" class="bouton bouton-clair" data-lot>Ajouter un lot acheté</button></p></div>`;
      return;
    }
    // par série
    const parSerie = new Map();
    bl.lignes.forEach(({ b, c }) => {
      const e = parSerie.get(b.serie) || { titres: new Set(), ex: 0, val: 0 };
      e.titres.add(b.livre_id); e.ex += c.qte; e.val += valeurLigne(b, c) || 0;
      parSerie.set(b.serie, e);
    });
    const totalTitres = new Map();
    DATA.forEach((b) => { (totalTitres.get(b.serie) || totalTitres.set(b.serie, new Set()).get(b.serie)).add(b.livre_id); });
    const series = [...parSerie].sort((a, b) => b[1].val - a[1].val);
    const maxVal = Math.max(...series.map((x) => x[1].val), 1);
    const lignesSerie = series.map(([nom, e]) => {
      const tot = totalTitres.get(nom).size;
      return `<tr><td class="principal"><div class="l-livre"><b style="font:700 1.1rem var(--f-display)">${esc(nom)}</b></div></td>
        <td class="num" data-label="Titres"><span class="prix-c">${e.titres.size}</span> <span class="sous">sur ${tot}</span><span class="progres"><i style="width:${Math.round((e.titres.size / tot) * 100)}%"></i></span></td>
        <td class="num" data-label="Exemplaires"><span class="prix-c">${e.ex}</span></td>
        <td class="num" data-label="Valeur estimée"><span class="prix-c">${fmtE(e.val)}</span><span class="barre" style="width:${Math.max(4, (e.val / maxVal) * 100)}%"></span></td></tr>`;
    }).join('');
    // pièces les plus cotées
    const pieces = [...bl.lignes].filter((x) => x.b.prix[x.c.etat] != null).sort((a, b) => b.b.prix[b.c.etat] - a.b.prix[a.c.etat]).slice(0, 5);
    const htmlPieces = pieces.map(({ b, c }) => `<button type="button" class="piece" data-id="${esc(b.id)}" aria-label="${esc(b.titre)}, édition ${esc(b.version)}, ${fmt(b.prix[c.etat])}">
      ${b.couverture ? `<img src="${esc(racine(b.couverture))}" alt="" width="88" height="124" loading="lazy" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(b)}
      <b>${esc(b.titre)}</b><span>${esc(b.version)} · ${esc(etatDe(c.etat).court)}</span><span class="p">${fmt(b.prix[c.etat])}</span></button>`).join('');
    // exemplaires, modifiables
    const triees = [...bl.lignes].sort((x, y) => x.b.serie.localeCompare(y.b.serie, 'fr') || (parseInt(x.b.numero, 10) || 0) - (parseInt(y.b.numero, 10) || 0) || x.b.version_n - y.b.version_n);
    const vus = triees.slice(0, limiteColl);
    const lignesEx = vus.map(({ b, c }) => {
      const v = valeurLigne(b, c);
      return `<tr data-ligne="${esc(b.id)}"><td class="principal"><div class="l-livre">${b.couverture ? `<img src="${esc(racine(b.couverture))}" alt="" width="40" height="56" loading="lazy" data-i="${esc((b.serie || '?').trim().charAt(0).toUpperCase())}">` : tuile(b)}
        <div><button type="button" data-id="${esc(b.id)}">${esc(b.titre)}</button><span class="sous" style="display:block">${esc(b.serie)}${esc(numero(b))} · <span class="badge">${esc(b.version)}</span></span></div></div></td>
        <td data-label="État"><select data-etat="${esc(b.id)}" aria-label="État de ${esc(b.titre)}, édition ${esc(b.version)}">${ETATS.map((x) => `<option value="${x.k}"${x.k === c.etat ? ' selected' : ''}>${x.k === 'tres_bon' ? 'TBE' : x.court}</option>`).join('')}</select></td>
        <td data-label="Exemplaires"><input type="number" min="1" max="99" value="${c.qte}" data-qte="${esc(b.id)}" aria-label="Nombre d'exemplaires de ${esc(b.titre)}, édition ${esc(b.version)}"></td>
        <td data-label="Prix payé (par exemplaire)"><input type="text" inputmode="decimal" autocomplete="off" placeholder="facultatif" value="${prixSaisi(c.prix)}" data-prix="${esc(b.id)}" aria-label="Prix payé, par exemplaire, pour ${esc(b.titre)}, édition ${esc(b.version)} (facultatif)"></td>
        <td class="num" data-label="Valeur estimée"><span class="prix-c${v == null ? ' nul' : ''}">${v == null ? 'sans cote' : fmt(v)}</span></td>
        <td class="num"><button type="button" class="retirer" data-retirer="${esc(b.id)}" aria-label="Retirer ${esc(b.titre)}, édition ${esc(b.version)}">Retirer</button></td></tr>`;
    }).join('');
    const reste = triees.length - vus.length;
    zone.innerHTML = `
      <div class="coll-haut">
        <div class="sceau" role="img" aria-label="Patrimoine estimé : ${fmtE(bl.total)}"><span class="sceau-lib">Patrimoine estimé</span><span class="sceau-prix">${fmtE(bl.total)}</span><span class="sceau-etat">${bl.exemplaires} exemplaire${bl.exemplaires > 1 ? 's' : ''}</span></div>
        <div>
          <dl class="stats${bl.nbPayes ? ' stats-4' : ''}">
            <div><dt>Titres</dt><dd>${bl.titres}<small>${bl.lignes.length} édition${bl.lignes.length > 1 ? 's' : ''}</small></dd></div>
            <div><dt>Plancher</dt><dd>${fmtE(bl.bas)}<small>tout en convenable</small></dd></div>
            <div><dt>Plafond</dt><dd>${fmtE(bl.haut)}<small>tout en <abbr title="Très bon état">TBE</abbr></dd></div>
            ${bl.nbPayes ? `<div><dt>Investi</dt><dd>${fmtE(bl.investi)}<small>${bl.nbPayes} exemplaire${bl.nbPayes > 1 ? 's' : ''} renseigné${bl.nbPayes > 1 ? 's' : ''}</small></dd></div>` : ''}
          </dl>
          <p class="trois">${esc(texteEstimation(bl))}</p>
          ${bl.sansCote ? `<p class="sans-cote">${bl.sansCote} exemplaire${bl.sansCote > 1 ? 's' : ''} sans cote pour l'état choisi : non compté${bl.sansCote > 1 ? 's' : ''} dans le total.</p>` : ''}
          <div class="coll-actions">
            <button type="button" class="bouton" data-parcours>Compléter pas à pas</button>
            <button type="button" class="bouton bouton-clair" data-lot>Ajouter un lot acheté</button>
            <button type="button" class="bouton bouton-clair" id="exp-json">Exporter (JSON)</button>
            <button type="button" class="bouton bouton-clair" id="exp-csv">Exporter (CSV)</button>
            <button type="button" class="bouton bouton-danger" id="coll-vider">Tout effacer</button>
          </div>
        </div>
      </div>
      <h3 id="titre-coll-histo">Où se situe la valeur de vos exemplaires</h3>
      <p class="sous" id="coll-histo-note"></p>
      <div id="coll-histo" class="histo"></div>
      <div class="legende" id="coll-histo-legende"></div>
      <details class="chiffres" id="coll-histo-chiffres"><summary>Voir les chiffres</summary><div id="coll-histo-table"></div></details>
      <h3>Par série</h3>
      <table class="cartes groupes"><thead><tr><th>Série</th><th class="num">Titres possédés</th><th class="num">Exemplaires</th><th class="num">Valeur estimée</th></tr></thead><tbody>${lignesSerie}</tbody></table>
      ${pieces.length ? `<h3>Vos pièces les plus cotées</h3><div class="pieces">${htmlPieces}</div>` : ''}
      <h3>Vos exemplaires</h3>
      <table class="cartes coll-table"><thead><tr><th>Livre</th><th>État</th><th>Exemplaires</th><th>Prix payé</th><th class="num">Valeur estimée</th><th class="num">Retirer</th></tr></thead><tbody>${lignesEx}</tbody></table>
      ${reste > 0 ? `<button type="button" class="plus" id="coll-plus">Voir ${Math.min(reste, 30)} exemplaires de plus (${reste} restants)</button>` : ''}`;
    // répartition de la valeur : chaque exemplaire compte pour une unité, au prix de son état
    const valeursColl = [];
    bl.lignes.forEach(({ b, c }) => { if (b.prix[c.etat] != null) for (let i = 0; i < c.qte; i += 1) valeursColl.push(b.prix[c.etat]); });
    const okH = histogramme({ zone: $('#coll-histo'), legende: $('#coll-histo-legende'), note: $('#coll-histo-note'), table: $('#coll-histo-table'),
      valeurs: valeursColl, etat: 'l\'état de chaque exemplaire', nom: { s: 'exemplaire', p: 'exemplaires' }, choix: false, vide: 'Aucun exemplaire n\'a de cote.' });
    $('#coll-histo-chiffres').hidden = !okH;
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
      if (e.target.dataset.prix !== undefined) { const pp = lirePrix(e.target.value); if (pp == null) delete COLL[id].prix; else COLL[id].prix = pp; }
      if (e.target.dataset.etat) COLL[id].etat = e.target.value;
      if (e.target.dataset.qte) COLL[id].qte = Math.min(99, Math.max(1, parseInt(e.target.value, 10) || 1));
      sauverColl(); afficher();
    });
    $('#collection').addEventListener('click', (e) => {
      const t = e.target;
      if (t.dataset.retirer) { delete COLL[t.dataset.retirer]; sauverColl(); afficher(); annonce('Exemplaire retiré de votre collection.'); }
      else if (t.id === 'exp-json') exporter('json');
      else if (t.id === 'exp-csv') exporter('csv');
      else if (t.id === 'coll-plus') { limiteColl += 30; afficherCollection(); }
      else if (t.id === 'coll-vider') {
        if (window.confirm('Effacer toute votre collection de ce navigateur ? Pensez à l\'exporter avant : cette action est définitive.')) {
          COLL = {}; sauverColl(); afficher(); annonce('Collection effacée.');
        }
      }
    });
    $('#partage-go').addEventListener('click', creerLien);
    $('#partage-copier').addEventListener('click', async () => {
      const st = $('#partage-statut');
      try { await navigator.clipboard.writeText($('#partage-lien').value); st.textContent = 'Lien copié.'; st.classList.remove('erreur'); }
      catch (e) { $('#partage-lien').select(); st.textContent = 'Copie impossible ici : le lien est sélectionné, copiez-le à la main.'; }
    });
    brancherParcours();                 // l'inventaire guidé est ouvert depuis la page collection
    $('#imp-go').addEventListener('click', () => importerTexte($('#imp-texte').value));
    $('#imp-fichier').addEventListener('change', async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      try { importerTexte(await f.text()); } catch (err) { statut('Ce fichier n\'a pas pu être lu.', true); }
      e.target.value = '';
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
        exemplaires: bl.lignes.map(({ b, c }) => ({ isbn13: b.isbn13 || b.id, titre: b.titre, edition: b.version, serie: b.serie, numero: b.numero, etat: c.etat, quantite: c.qte, prix_unitaire_estime: b.prix[c.etat], prix_paye: c.prix ?? null, lot: c.lot ?? null })),
      }, null, 2), 'application/json');
    } else {
      const q = (t) => `"${String(t ?? '').replace(/"/g, '""')}"`;
      const lignes = [['isbn13', 'titre', 'edition', 'serie', 'numero', 'etat', 'quantite', 'prix_unitaire_estime', 'valeur_estimee', 'prix_paye'].join(';')]
        .concat(bl.lignes.map(({ b, c }) => [q(b.isbn13 || b.id), q(b.titre), b.version, q(b.serie), q(b.numero), c.etat, c.qte,
          b.prix[c.etat] == null ? '' : String(b.prix[c.etat]).replace('.', ','), valeurLigne(b, c) == null ? '' : valeurLigne(b, c).toFixed(2).replace('.', ','), prixSaisi(c.prix)].join(';')));
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
          else if (x && typeof x === 'object') entrees.push({ cle: x.isbn13 || x.isbn || x.id || '?', etat: etatDepuis(x.etat || ''), qte: parseInt(x.quantite ?? x.qte, 10) || 1, prix: lirePrix(x.prix_paye), lot: typeof x.lot === 'string' ? x.lot.slice(0, 20) : null });
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
          entrees.push({ cle: v[col('isbn13')], etat: etatDepuis(v[col('etat')] || ''), qte: parseInt(v[col('quantite')], 10) || 1, prix: col('prix_paye') >= 0 ? lirePrix(v[col('prix_paye')]) : null });
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
    if (remplacer) COLL = {};
    let ajoutes = 0, maj = 0; const inconnus = [];
    entrees.forEach((en) => {
      const isbn = en.inconnu ? null : versIsbn13(en.cle);
      const b = isbn ? DATA.find((x) => x.isbn13 === isbn) : DATA.find((x) => x.id === en.cle);
      if (!b) { inconnus.push(en.cle); return; }
      const avant = COLL[b.id];
      COLL[b.id] = { etat: en.etat || (avant && avant.etat) || S.h, qte: Math.min(99, Math.max(1, en.qte || (avant && avant.qte) || 1)) };
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
  const LETTRE = { convenable: 'c', bon: 'b', tres_bon: 't' };
  const DEPUIS_LETTRE = { c: 'convenable', b: 'bon', t: 'tres_bon' };
  const versB64 = (octets) => btoa(String.fromCharCode(...octets)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  const depuisB64 = (t) => Uint8Array.from(atob(t.replace(/-/g, '+').replace(/_/g, '/')), (c) => c.charCodeAt(0));
  async function fluxOctets(octets, Classe, mode) {
    const f = new Blob([octets]).stream().pipeThrough(new Classe(mode));
    return new Uint8Array(await new Response(f).arrayBuffer());
  }
  async function codeCollection() {
    const index = parId();
    const texte = Object.entries(COLL).filter(([id]) => index.has(id)).map(([id, c]) => {
      const b = index.get(id);
      return `${b.isbn13 || b.id}${LETTRE[c.etat] || 'b'}${c.qte > 1 ? c.qte : ''}${c.prix != null ? '@' + c.prix : ''}`;
    }).join(',');
    let octets = new TextEncoder().encode(texte), z = '';
    if (typeof CompressionStream === 'function') {
      try { octets = await fluxOctets(octets, CompressionStream, 'deflate-raw'); z = 'z'; } catch (e) { octets = new TextEncoder().encode(texte); }
    }
    return `${FORMAT_FICHIER}${z}.${versB64(octets)}`;
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
  async function creerLien() {
    const sortie = $('#partage-lien'), st = $('#partage-statut');
    if (!Object.keys(COLL).length) { st.textContent = 'Votre collection est vide : il n\'y a rien à transférer.'; st.classList.add('erreur'); return; }
    const url = `${location.origin}${location.pathname}#c=${await codeCollection()}`;
    sortie.value = url; sortie.hidden = false; $('#partage-copier').hidden = false; sortie.select();
    st.classList.remove('erreur'); st.textContent = `Lien prêt (${Object.keys(COLL).length} titres). Ouvrez-le sur l'autre appareil.`;
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
    const c = COLL[b.id];
    return `<div class="coll-fiche"><h3>Dans ma collection</h3><div class="coll-ligne">
      <label class="case"><input type="checkbox" id="c-poss"${c ? ' checked' : ''}><span>Je possède ce livre</span></label>
      <div class="champ-ligne"><label for="c-etat">État</label><select id="c-etat"${c ? '' : ' disabled'}>${ETATS.map((x) => `<option value="${x.k}"${(c ? c.etat : S.h) === x.k ? ' selected' : ''}>${x.k === 'tres_bon' ? 'TBE' : x.court}</option>`).join('')}</select></div>
      <div class="champ-ligne"><label for="c-qte">Exemplaires</label><input type="number" id="c-qte" min="1" max="99" value="${c ? c.qte : 1}"${c ? '' : ' disabled'}></div>
      <div class="champ-ligne"><label for="c-prix">Prix payé, par exemplaire (facultatif)</label><input type="text" id="c-prix" inputmode="decimal" autocomplete="off" placeholder="en €" value="${c ? prixSaisi(c.prix) : ''}"${c ? '' : ' disabled'}></div>
      <p class="valeur-ex" id="c-val"></p></div></div>`;
  }
  function brancherFicheCollection(b) {
    const maj = () => {
      const c = COLL[b.id];
      $('#c-etat').disabled = !c; $('#c-qte').disabled = !c; $('#c-prix').disabled = !c;
      const v = c ? valeurLigne(b, c) : null;
      $('#c-val').textContent = c ? (v == null ? 'Sans cote pour cet état' : `Valeur estimée : ${fmt(v)}`) : '';
    };
    $('#c-poss').addEventListener('change', (e) => {
      if (e.target.checked) { COLL[b.id] = { etat: $('#c-etat').value, qte: Math.min(99, Math.max(1, parseInt($('#c-qte').value, 10) || 1)) }; const pp = lirePrix($('#c-prix').value); if (pp != null) COLL[b.id].prix = pp; }
      else delete COLL[b.id];
      sauverColl(); maj(); afficher();
    });
    $('#c-etat').addEventListener('change', (e) => { if (COLL[b.id]) { COLL[b.id].etat = e.target.value; sauverColl(); maj(); afficher(); } });
    $('#c-prix').addEventListener('change', (e) => { if (COLL[b.id]) { const pp = lirePrix(e.target.value); if (pp == null) { delete COLL[b.id].prix; e.target.value = ''; } else { COLL[b.id].prix = pp; e.target.value = prixSaisi(pp); } sauverColl(); maj(); afficher(); } });
    $('#c-qte').addEventListener('change', (e) => { if (COLL[b.id]) { COLL[b.id].qte = Math.min(99, Math.max(1, parseInt(e.target.value, 10) || 1)); e.target.value = COLL[b.id].qte; sauverColl(); maj(); afficher(); } });
    maj();
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
    liste.innerHTML = trouves.slice(0, 8).map((b) => `<li><button type="button" data-lot-add="${esc(b.id)}"><strong>${esc(b.titre)}</strong><span>${esc(b.serie)}${esc(numero(b))} · <span class="badge">${esc(b.version)}</span>${b.annee ? ` · ${b.annee}` : ''}${COLL[b.id] ? ' · déjà dans votre collection' : ''}</span><em>Ajouter au lot</em></button></li>`).join('') +
      (trouves.length > 8 ? `<li class="sous">${trouves.length} résultats : précisez votre recherche.</li>` : '') + (!trouves.length ? '<li class="sous">Aucun livre trouvé.</li>' : '');
  }
  function rendreLot() {
    $('#lot-h').textContent = `Dans le lot (${LOT.lignes.reduce((t, l) => t + l.qte, 0)} exemplaire${LOT.lignes.reduce((t, l) => t + l.qte, 0) > 1 ? 's' : ''})`;
    $('#lot-lignes').innerHTML = !LOT.lignes.length ? '<p class="sous">Aucun livre pour l\'instant : cherchez-les ci-dessus.</p>' :
      `<table class="cartes coll-table"><thead><tr><th>Livre</th><th>État</th><th>Exemplaires</th><th>Prix par exemplaire</th><th class="num">Retirer</th></tr></thead><tbody>${LOT.lignes.map((l) => {
        const b = livreDe(l.id);
        return `<tr><td class="principal"><div><strong>${esc(b.titre)}</strong><span class="sous" style="display:block">${esc(b.serie)}${esc(numero(b))} · <span class="badge">${esc(b.version)}</span>${COLL[b.id] ? ' · déjà possédé : l\'exemplaire s\'ajoute' : ''}</span></div></td>
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


  /* ---------- Inventaire guidé : séries → éditions → listes → bilan ---------- */
  const P = { phase: 'intro', etat: 'bon', series: new Set(), cellules: new Set(), file: [], i: 0, message: '' };
  const CLE_P = 'cote-parcours-v1';
  let INFO = null, REPRISE = null, derniereSauvegarde = null;
  const heure = (d) => d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  function majIndicateur() {
    const el = $('#pa-save');
    if (el) el.textContent = derniereSauvegarde ? `✓ Enregistré dans ce navigateur à ${heure(derniereSauvegarde)}` : '';
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
      : (dejaN ? bouton('reprendre', `Continuer avec ma collection<small>${pl(dejaN, 'exemplaire')} déjà enregistré${dejaN > 1 ? 's' : ''} dans ce navigateur</small>`, 'bouton-choix') : '');
    $('#parcours-corps').innerHTML = `
      <section class="reprise" aria-labelledby="pe-reprise">
        <h3 id="pe-reprise">${reprendre ? 'Reprendre ou repartir ?' : 'Vous avez déjà un fichier ?'}</h3>
        <div class="reprise-choix">
          ${reprendre}
          <label class="bouton bouton-clair bouton-choix" for="pe-fichier">Charger mon fichier<small>sauvegarde JSON, CSV ou liste d'ISBN : tout est coché pour vous</small></label>
          <input type="file" id="pe-fichier" accept=".json,.csv,.txt,text/plain,application/json" hidden>
          ${dejaN ? bouton('zero', 'Repartir de zéro<small>efface la collection de ce navigateur</small>', 'bouton-clair bouton-choix') : ''}
        </div>
        <p class="statut" id="pe-statut" role="status" aria-live="polite"></p>
      </section>
      <p>Inutile de tout saisir à la main : on avance par grandes masses, de la série jusqu'à la couverture.</p>
      <ol class="etapes">
        <li><strong>Vos séries</strong> : vous touchez celles dont vous avez au moins un livre.</li>
        <li><strong>Vos éditions</strong> : un seul tableau, pour dire quelles éditions (V1 à V5) vous possédez dans chaque série.</li>
        <li><strong>Vos livres</strong> : pour chaque série et édition, vous cochez les couvertures. Une série complète se coche d'un geste.</li>
        <li><strong>Le bilan</strong> : le guide estime votre patrimoine et vous remet un fichier de sauvegarde (JSON).</li>
      </ol>
      <p><strong>Vos livres sont le plus souvent en…</strong> <span class="sous">(vous pourrez le changer à chaque liste)</span></p>
      <div class="choix-etat" role="radiogroup" aria-label="État habituel">
        ${ETATS.map((e) => `<label><input type="radio" name="pe-etat" value="${e.k}"${e.k === P.etat ? ' checked' : ''}><span>${e.k === 'tres_bon' ? 'Très bon état (TBE)' : e.court}<small>${esc(e.def.replace(' TBE signifie « très bon état ».', ''))}</small></span></label>`).join('')}
      </div>
      <p class="sous">Tout s'enregistre au fil de l'eau, dans ce navigateur uniquement. Vous pouvez fermer à tout moment et reprendre plus tard.</p>`;
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
    if (oui) COLL[b.id] = { etat: P.etat, qte: (COLL[b.id] && COLL[b.id].qte) || 1 };
    else delete COLL[b.id];
    majTuile(b);
  }
  // C / BE / TBE : choisit l'état d'un livre ; retoucher l'état déjà choisi retire le livre
  function etatRapide(b, etat) {
    if (COLL[b.id] && COLL[b.id].etat === etat) delete COLL[b.id];
    else COLL[b.id] = { etat, qte: (COLL[b.id] && COLL[b.id].qte) || 1 };
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
      <p><strong>Gardez votre fichier.</strong> Votre collection est enregistrée dans ce navigateur ; le fichier JSON en est la sauvegarde. Vous pourrez le recharger ici (« Importer une liste ») sur n'importe quel appareil.</p>
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
        if (window.confirm('Effacer toute votre collection de ce navigateur ? Pensez à la sauvegarder avant : cette action est définitive.')) {
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
      ? "<strong>Cotes d'archives.</strong> Les prix viennent d'un ancien relevé, qui n'est plus tenu à jour : lisez-les comme un repère de grandeur, pas comme la cote du jour."
      : `<strong>Prix actuels en cours d'ajout.</strong> ${nbActuels() > 1 ? `${nbActuels()} cotes reposent` : '1 cote repose'} sur des prix récents ; les autres restent des cotes d'archives, à lire comme un repère de grandeur.`;
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

  charger();
})();
