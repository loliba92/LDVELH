/* Vérifier les prix : un livre par ligne, ses trois prix, l'ancien prix barré quand il a changé (outil du propriétaire). */
(() => {
  'use strict';

  const REVENDEURS = { amazon: 'Amazon', fnac: 'Fnac', abebooks: 'AbeBooks', recyclivre: 'Recyclivre' };          // offres d'occasion des revendeurs (relevé du bot)
  const enLigne = (o) => o === 'leboncoin' || o === 'vinted' || o === 'librairie' || Object.hasOwn(REVENDEURS, o);          // en ligne tant que non signalée vendue : pas de date de relevé eBay
  const $ = (s) => document.querySelector(s);
  const ETATS = [['convenable', 'Convenable'], ['bon', 'Bon état'], ['tres_bon', 'Très bon état']];
  const PAGE = 60;
  const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // Titre de recherche : sans parenthèses (« (Grand format) »…), absentes des annonces
  const requete = (t) => encodeURIComponent(t.replace(/\s*\([^)]*\)/g, '').replace(/\s+/g, ' ').trim()).replace(/%20/g, '+');
  const eur = (v) => (v == null ? '—' : v.toFixed(2).replace('.', ',') + ' €');
  const norm = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  let EDITIONS = [], VUE = [], vue = 'verif', limite = PAGE;

  // Validations faites sur cette page : gardées dans ce navigateur jusqu'à leur envoi (fichier à transmettre), puis reprises
  // dans les données du site (champ « valide »). Elles priment sur eBay et les archives.
  const CLE_LOC = 'cdh-validations-v1';
  let LOC = {};
  let HISTO = null;                                    // cotes publiées des 10 derniers jours, par livre et état
  try { LOC = JSON.parse(localStorage.getItem(CLE_LOC) || '{}') || {}; } catch (e) { LOC = {}; }
  // Une validation envoyée reste gardée jusqu'à ce que le site l'ait reprise (voir plus bas) ; pendant ce délai elle n'est plus « à transmettre ».
  // Si le site ne l'a pas reprise au bout de 20 minutes, elle est de nouveau proposée à l'envoi (l'envoi a pu échouer).
  const ATTENTE_SITE = 20 * 60000;
  const envoyee = (v) => !!v.envoye && Date.now() - v.envoye < ATTENTE_SITE;
  const sauver = () => { try { localStorage.setItem(CLE_LOC, JSON.stringify(LOC)); } catch (e) { /* navigateur sans stockage : la validation reste valable tant que la page est ouverte */ } };
  const cleDe = (ed, cle) => `${ed.isbn}|${cle}`;
  const aujourdhui = () => new Date().toISOString().slice(0, 10);
  // Nom de la personne connectée avec Google (affichage seulement) ; le nom enregistré est celui que le lot vérifie (pipeline/identite.py)
  // « aujourd'hui », « hier » ou la date : pour ne pas refaire une révision qui vient d'être faite
  function quand(iso) {
    if (!iso) return '';
    const ecart = Math.round((Date.parse(aujourdhui()) - Date.parse(iso)) / 86400000);
    return ecart <= 0 ? 'aujourd\'hui' : ecart === 1 ? 'hier' : 'le ' + new Date(iso + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', ...(ecart > 300 ? { year: 'numeric' } : {}) });
  }
  const jour = (iso) => (iso ? new Date(iso + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' }) : '');
  // Prix validé d'un état : validation de cette page (en attente d'envoi) ou déjà reprise dans les données du site
  function validation(ed, cle) {
    const loc = LOC[cleDe(ed, cle)], l = ed.etats[cle];
    if (loc) return { prix: loc.prix, le: loc.le, par: loc.par, decision: loc.decision, enAttente: true, calcule: l ? (l.valide ? l.calcule : l.publie) : null };
    if (l && l.valide) return { prix: l.publie, le: l.valide_le, par: l.valide_par, decision: l.decision, enAttente: false, calcule: l.calcule };
    return null;
  }

  // Prix recalculés quand des prix de l'édition viennent d'être saisis sur cette page (pas encore transmis) : le site fera le même
  // calcul à la prochaine mise à jour (pipeline/etats.py puis export_site.aligner), la page le montre tout de suite. Un prix saisi
  // ou issu d'annonces actuelles ne bouge pas ; les états sans annonce valent le « niveau » des autres (convenable 40 %, bon 60 %, très bon 100 %).
  const RAPPORT = { convenable: 0.4, bon: 0.6, tres_bon: 1 };
  function projection(ed) {
    if (!ETATS.some(([cle]) => LOC[cleDe(ed, cle)])) return {};
    const fixe = {}, poids = {};
    ETATS.forEach(([cle]) => {
      const v = validation(ed, cle), l = ed.etats[cle];
      if (v) { fixe[cle] = v.prix; poids[cle] = 1 / 0.03 ** 2; }
      else if (l && l.publie != null && (l.neuf || (l.source && l.source !== 'archives' && !l.deduit && !l.repartition))) { fixe[cle] = l.publie; poids[cle] = 1 / (l.neuf ? 0.05 : 0.35) ** 2; }
    });
    const cles = Object.keys(fixe);
    if (!cles.length) return {};
    const niveau = Math.exp(cles.reduce((t, c) => t + poids[c] * Math.log(fixe[c] / RAPPORT[c]), 0) / cles.reduce((t, c) => t + poids[c], 0));
    const prix = {}, libres = {};
    ETATS.forEach(([cle]) => { if (cle in fixe) prix[cle] = fixe[cle]; else { prix[cle] = Math.round(niveau * RAPPORT[cle] * 100) / 100; libres[cle] = true; } });
    for (let i = 0; i < 3; i += 1) {                                   // cohérence C ≤ BE ≤ TBE : on bouge d'abord un prix déduit
      ETATS.forEach(([bas], k) => {
        const haut = k < 2 ? ETATS[k + 1][0] : null;
        if (!haut || prix[haut] >= prix[bas]) return;
        if (libres[haut]) prix[haut] = Math.round(prix[bas] * 1.2 * 100) / 100;
        else if (libres[bas]) prix[bas] = Math.round(prix[haut] / 1.2 * 100) / 100;
      });
    }
    return Object.fromEntries(Object.keys(libres).map((c) => [c, prix[c]]));
  }

  const ratio = (l) => (l && l.archive && l.publie ? l.publie / l.archive : null);
  const modifie = (l) => l && l.publie != null && l.archive != null && Math.abs(l.publie - l.archive) > 0.01;
  // « À vérifier » : le prix a presque doublé (×1,8) ou presque divisé par deux (×0,55)
  const raison = (l, v) => {
    if (v || (l && l.valide)) return '';
    if (l && l.ajuste) return "remonté pour rester cohérent (très bon état au moins égal au bon état) : à confirmer";
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
    if (l.neuf) return 'prix du neuf (prix éditeur)';
    if (l.valide) return `validé le ${jour(l.valide_le)}`;
    if (l.deduit) return 'déduit des autres états';
    if (l.repartition) { const n = l.eb_nb_toutes || l.eb_nb; return `annonces eBay${n ? ' (' + n + ')' : ''}, réparti 40/60`; }
    if (l.source && l.source !== 'archives') {
      const n = l.eb_nb_toutes || l.eb_nb;
      if (!n && l.lib_prix) return `d'après un exemplaire en librairie : ${eur(l.lib_prix)}`;           // pas d'annonce eBay : le prix actuel vient d'une librairie
      return n ? `d'après ${n} annonce${n > 1 ? 's' : ''} eBay` : "d'après les annonces eBay";
    }
    return l.publie == null ? '' : 'ancienne cote';
  }

  // Date du dernier changement du prix : une correction de cette page, sinon le dernier changement des 10 jours publiés
  // Dernier changement du prix : { date (ISO), precis } ; precis = false quand aucun changement dans les 10 jours publiés
  function dernierChangement(ed, cle) {
    const v = validation(ed, cle);
    if (v && v.le) return { date: v.le, precis: true };
    const h = HISTO && HISTO.cotes[cleDe(ed, cle)];
    if (!h) return null;
    for (let i = h.length - 1; i > 0; i -= 1) if (h[i] != null && h[i] !== h[i - 1]) return { date: HISTO.dates[i], precis: true };
    return { date: HISTO.dates[0], precis: false };
  }
  function ajusteLe(ed, cle) {
    const c = dernierChangement(ed, cle);
    if (!c) return '';
    return c.precis ? `Prix ajusté le ${jour(c.date)}` : `Prix ajusté avant le ${jour(c.date)}`;
  }

  function cellule([cle, lib], ed) {
    const l = ed.etats[cle], v = validation(ed, cle);
    if (!l || l.publie == null) {
      if (!v) return `<div class="rv-prix vide"><span class="rv-lib">${lib}</span><strong>—</strong><span class="rv-note">pas de prix</span></div>`;
    }
    if (v) {
      const calc = v.calcule != null && Math.abs(v.calcule - v.prix) > 0.005 ? `<span class="rv-avant">le site calculait <s>${eur(v.calcule)}</s></span>` : '';
      const quand = v.enAttente ? `Validé ${v.decision === 'confirme' ? '(confirmé)' : '(corrigé)'} ${jour(v.le)}${v.par ? ', par ' + v.par : ''} : à transmettre` : `Validé ${v.decision === 'confirme' ? '(confirmé)' : '(corrigé)'} le ${jour(v.le)}${v.par ? ', par ' + v.par : ''}`;
      return `<div class="rv-prix valide"><span class="rv-lib">${lib}</span><strong>${eur(v.prix)}</strong>${calc}<span class="rv-note rv-quand">✓ ${esc(quand)}</span></div>`;
    }
    const proj = projection(ed)[cle];
    if (proj != null) {                                                 // recalculé d'après les prix que vous venez de saisir
      const site = l && l.publie != null && Math.abs(l.publie - proj) > 0.005 ? `<span class="rv-avant">le site affiche <s>${eur(l.publie)}</s></span>` : '';
      return `<div class="rv-prix"><span class="rv-lib">${lib}</span><strong>${eur(proj)}</strong>${site}<span class="rv-note">recalculé d'après vos prix saisis (à transmettre)</span></div>`;
    }
    const r = ratio(l), alerte = raison(l, null);
    const avant = modifie(l) ? `<span class="rv-avant">avant <s>${eur(l.archive)}</s> · <b>${pct(r)}</b></span>` : '';
    const notes = [origine(l), ajusteLe(ed, cle), l.lib_prix && (l.eb_nb_toutes || l.eb_nb || l.deduit || l.valide || l.neuf || l.repartition) ? `1 exemplaire en librairie : ${eur(l.lib_prix)}` : '', l.ajuste ? 'ajusté pour garder C ≤ BE ≤ TBE' : ''].filter(Boolean).join(' · ');
    return `<div class="rv-prix${modifie(l) ? (r > 1 ? ' hausse' : ' baisse') : ''}${alerte ? ' alerte' : ''}"><span class="rv-lib">${lib}</span>` +
      `<strong>${eur(l.publie)}</strong>${avant}${alerte ? `<span class="rv-raison">À vérifier : ${alerte}</span>` : ''}<span class="rv-note">${esc(notes)}</span></div>`;
  }

  // Dernière révision d'une édition : la validation la plus récente de l'un de ses états (y compris celles pas encore transmises)
  function derniereRevision(ed) {
    let best = null;
    ETATS.forEach(([cle]) => { const v = validation(ed, cle); if (v && v.le && (!best || v.le >= best.le)) best = v; });
    return best ? `<span class="rv-revision"${best.par ? ` title="Par ${esc(best.par)}"` : ''}>Révisée <strong>${esc(quand(best.le))}</strong></span>` : '<span class="rv-revision rien">Pas encore révisée</span>';
  }

  // Fiabilité du prix d'un livre : toutes les annonces du livre, tous états confondus (l'état ne fait pas le prix).
  // Solide : au moins 10 annonces et dispersion (écart-type / médiane) de 30 % au plus. À confirmer : 3 à 9 annonces, ou dispersion jusqu'à 60 %. Faible : le reste.
  function fiabilite(ed) {
    if (!ANN || !ANN.annonces) return null;
    const prix = [];
    if (ed.isbn) ETATS.forEach(([cle]) => (ANN.annonces[ed.isbn] && ANN.annonces[ed.isbn][cle] || []).forEach((x) => prix.push(x[0])));
    const n = prix.length;
    if (n < 2) return { n, niveau: 'insuffisant' };
    const tries = prix.slice().sort((a, b) => a - b), m = n >> 1;
    const med = n % 2 ? tries[m] : (tries[m - 1] + tries[m]) / 2;
    const moy = prix.reduce((t, x) => t + x, 0) / n;
    const ecart = Math.sqrt(prix.reduce((t, x) => t + (x - moy) ** 2, 0) / n);
    const disp = med > 0 ? ecart / med : null;
    const niveau = n >= 10 && disp !== null && disp <= 0.3 ? 'solide' : (n >= 3 && (disp === null || disp <= 0.6)) ? 'confirmer' : 'faible';
    const liste = [];
    ETATS.forEach(([cle, lib]) => (ANN.annonces[ed.isbn] && ANN.annonces[ed.isbn][cle] || []).forEach((x) => liste.push({ prix: x[0], titre: x[1], lien: x[2], origine: x[3], lib, cle })));
    return { n, med, disp, niveau, liste: liste.sort((a, b) => a.prix - b.prix) };
  }
  function fiabiliteHtml(ed) {
    const f = estNiveau3() ? fiabilite(ed) : null;
    if (!f) return '';
    // Le nombre d'annonces ouvre la liste de ces annonces (même fenêtre que « Voir les annonces »)
    const compte = f.n ? `<button type="button" class="bouton-lien rv-voir-fiab" data-fiab="${esc(ed.id)}">${f.n} annonce${f.n > 1 ? 's' : ''}</button>` : '0 annonce';
    if (f.niveau === 'insuffisant') return `<p class="rv-fiab"><span class="sous">Fiabilité : pas assez d'annonces (${compte})</span></p>`;
    const NIV = { solide: ['Solide', 'rc-v-dessous'], confirmer: ['À confirmer', 'rc-v-dans'], faible: ['Faible', 'rc-v-dessus'] }[f.niveau];
    const pourcent = f.disp == null ? '–' : Math.round(f.disp * 100) + ' %';
    return `<p class="rv-fiab"><span class="rc-pastille ${NIV[1]}">Fiabilité : ${NIV[0]}</span> <span class="sous">${compte}, dispersion ${pourcent}</span> <span class="rv-fiab-prop">Proposition : <strong>${eur(f.med)}</strong> (médiane)</span></p>`;
  }

  // Fenêtre « annonces comptées pour la fiabilité » : uniquement ces annonces, chacune avec son lien
  function ouvrirFiabilite(ed) {
    const f = fiabilite(ed);
    if (!f || !f.liste.length) return;
    let dlg = document.getElementById('fiab-dialog');
    if (!dlg) { dlg = document.createElement('dialog'); dlg.id = 'fiab-dialog'; dlg.className = 'fiab-dialog'; document.body.appendChild(dlg); }
    const ORIGINE = { ebay: 'eBay', leboncoin: 'Leboncoin', vinted: 'Vinted', librairie: 'Librairie', ...REVENDEURS };
    // Verdict comme sur la page Annonces : prix comparé au prix du site pour le même état
    const verdict = (prix, pub) => {
      if (pub == null) return null;
      if (prix <= 0.2 * pub) return ['Super pépite', 'rc-v-super'];
      if (prix <= 0.5 * pub) return ['Pépite', 'rc-v-pepite'];
      if (prix < 0.9 * pub) return ['Pas cher', 'rc-v-dessous'];
      if (prix <= 1.1 * pub) return ['Dans les prix', 'rc-v-dans'];
      if (prix <= 1.5 * pub) return ['Trop cher', 'rc-v-dessus'];
      return ['Très cher', 'rc-v-cher'];
    };
    const lignes = f.liste.map((x) => {
      const pub = ed.etats[x.cle] ? ed.etats[x.cle].publie : null;
      const v = verdict(x.prix, pub);
      const ecart = pub ? Math.round((x.prix / pub - 1) * 100) : null;
      const meta = `${x.lib}${x.frais ? ` · dont ${eur(x.frais)} de frais` : ''}${pub ? ` · site ${eur(pub)} · ${ecart > 0 ? '+' : ecart < 0 ? '−' : ''}${Math.abs(ecart)} %` : ''}`;
      return `<li class="fiab-ligne">
        <div class="fiab-haut"><a class="fiab-titre-ann" href="${esc(x.lien)}" target="_blank" rel="noopener noreferrer">${esc(x.titre)}<span class="sr-only"> (nouvel onglet)</span></a><b class="fiab-prix">${eur(x.prix)}</b></div>
        <div class="fiab-bas"><span class="fiab-origine">${esc(ORIGINE[x.origine] || 'eBay')}</span>${v ? `<span class="rc-pastille ${v[1]}">${v[0]}</span>` : ''}<span class="fiab-meta">${esc(meta)}</span></div>
      </li>`;
    }).join('');
    dlg.innerHTML = `<div class="fiab-cadre">
      <div class="fiab-tete"><div><p class="fiab-surtitre">Annonces comptées pour la fiabilité</p><p class="fiab-resume"><b>${f.n} annonce${f.n > 1 ? 's' : ''}</b> · ${esc(ed.titre)} ${esc(ed.version)} · médiane ${eur(f.med)}</p></div><button type="button" class="bouton-lien" data-fiab-fermer>Fermer</button></div>
      <ul class="fiab-liste">${lignes}</ul></div>`;
    dlg.querySelector('[data-fiab-fermer]').addEventListener('click', () => dlg.close());
    dlg.showModal();
  }
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-fiab]');
    if (!b) return;
    const ed = EDITIONS.find((x) => x.id === b.dataset.fiab);
    if (ed) ouvrirFiabilite(ed);
  });

  function carte(ed) {
    const jaq = JAQ[ed.id] ? `<img class="rv-jaq" src="${esc(JAQ[ed.id])}" alt="Jaquette de ${esc(ed.titre)}" width="56" height="80" loading="lazy" decoding="async">` : '';
    return `<article class="rv-edition"><header class="rv-tete">${jaq}<div class="rv-titre"><a href="./#q=${encodeURIComponent(ed.isbn || ed.id)}">${esc(ed.titre)}</a>` +
      `<span class="sous">${esc(ed.serie)}${ed.numero && !/^0+$/.test(ed.numero) ? ' n° ' + esc(ed.numero) : ''} · <span class="badge">${esc(ed.version)}</span>${RAR[ed.id] && /rare$/.test(RAR[ed.id].niveau) ? ` · <span class="rarete rarete-${RAR[ed.id].niveau}" title="Possédé par ${RAR[ed.id].pct} % des collections">${{ tres_rare: 'très rare', rare: 'rare', peu_courant: 'peu courant', courant: 'courant' }[RAR[ed.id].niveau]}</span>` : ''}</span>${derniereRevision(ed)}` +
      `<a class="rv-fiche" href="./#fiche=${encodeURIComponent(ed.id)}&corriger=1" target="_blank" rel="noopener">Corriger les prix dans la fiche</a>${voirAnnonces(ed) ? `<button type="button" class="bouton-lien rv-voir-ann" data-annonces="${esc(ed.id)}">Voir les annonces</button>` : (estNiveau3() && ANN ? '<span class="sous rv-pas-ann">Aucune annonce retenue au dernier relevé</span>' : '')}</div></header>` +
      `<div class="rv-trois">${ETATS.map((e) => cellule(e, ed)).join('')}</div>${fiabiliteHtml(ed)}` +
      `<span class="rv-liens"><span class="rv-liens-titre">Chercher en vente</span>${[
        ['eBay', `https://www.ebay.fr/sch/i.html?_nkw=${requete(ed.titre + ' ' + (ed.isbn || ''))}`],
        ['Leboncoin', `https://www.leboncoin.fr/recherche?text=${requete(ed.titre + ' ldvelh')}&sort=time`],
        ['Vinted', `https://www.vinted.fr/catalog?search_text=${requete(ed.titre + ' ldvelh')}`],
        ['Facebook', `https://www.facebook.com/marketplace/search/?query=${requete(ed.titre + ' ldvelh')}`]]
        .map(([nom, url]) => `<a class="rv-ebay" href="${url}" target="_blank" rel="noopener noreferrer" aria-label="Chercher ${esc(ed.titre)} sur ${nom} (nouvel onglet)">${nom} ↗</a>`).join('')}</span></div></article>`;
  }
  const lignes = (ed) => Object.values(ed.etats);
  const aVerifier = (ed) => ETATS.some(([cle]) => ed.etats[cle] && raison(ed.etats[cle], validation(ed, cle)));
  const aValide = (ed) => ETATS.some(([cle]) => validation(ed, cle));
  const aChange = (ed) => lignes(ed).some(modifie);
  // Dernier changement de l'édition (tous états) : sert à classer « Changés » du plus récent
  const dateEd = (ed) => Object.keys(ed.etats).map((cle) => { const c = dernierChangement(ed, cle); return c ? c.date : ''; }).sort().pop() || '';
  const force = (ed) => Math.max(0, ...lignes(ed).map((l) => { const r = ratio(l); return r ? Math.abs(Math.log(r)) : 0; }));

  function afficher() {
    const q = norm($('#rv-q').value).trim(), serie = $('#rv-serie').value, fiab = $('#rv-fiab').value;
    const niveauDe = (ed) => { const f = fiabilite(ed); return f ? f.niveau : null; };
    const base = EDITIONS.filter((ed) => (!q || norm(ed.titre + ' ' + ed.serie).includes(q)) && (!serie || ed.serie === serie) && (!fiab || niveauDe(ed) === fiab));
    $('#rv-n-verif').textContent = base.filter(aVerifier).length;
    $('#rv-n-change').textContent = base.filter(aChange).length;
    $('#rv-n-tous').textContent = base.length;
    $('#rv-n-valide').textContent = base.filter(aValide).length;
    VUE = vue === 'verif' ? base.filter(aVerifier).sort((a, b) => force(b) - force(a))
      : vue === 'change' ? base.filter(aChange).sort((a, b) => dateEd(b).localeCompare(dateEd(a)) || force(b) - force(a))
      : vue === 'valide' ? base.filter(aValide).sort((a, b) => a.serie.localeCompare(b.serie, 'fr') || (parseInt(a.numero, 10) || 0) - (parseInt(b.numero, 10) || 0))
      : base.slice().sort((a, b) => a.serie.localeCompare(b.serie, 'fr') || (parseInt(a.numero, 10) || 0) - (parseInt(b.numero, 10) || 0) || a.version.localeCompare(b.version));
    $('#rv-compte').textContent = `${VUE.length} livre${VUE.length > 1 ? 's' : ''}` + (vue === 'verif' ? ' dont un prix a beaucoup bougé, du plus fort changement au plus faible.' : vue === 'change' ? ' dont au moins un prix a changé.' : vue === 'valide' ? ' dont au moins un prix est validé.' : '.');
    const valeurs = Object.values(LOC), nbAttente = valeurs.filter((v) => !envoyee(v)).length, nbEnvoyees = valeurs.length - nbAttente;
    $('#rv-envoi').hidden = !nbAttente;
    $('#rv-envoi-attente').hidden = !nbAttente;                      // rien à transmettre : seules des validations déjà envoyées attendent la mise à jour du site
    $('#rv-envoyer').hidden = !nbAttente;
    $('#rv-n-attente').textContent = nbAttente;
    $('#rv-envoyer').textContent = 'Envoyer mes validations';
    const faites = $('#rv-envoi-faites');
    faites.hidden = !nbEnvoyees;
    faites.textContent = `${nbEnvoyees} validation${nbEnvoyees > 1 ? 's' : ''} déjà envoyée${nbEnvoyees > 1 ? 's' : ''} : le site se met à jour (environ 2 minutes). ${nbEnvoyees > 1 ? 'Elles disparaîtront' : 'Elle disparaîtra'} de cette liste dès qu'il ${nbEnvoyees > 1 ? 'les' : 'la'} aura reprise${nbEnvoyees > 1 ? 's' : ''}.`;
    $('#rv-liste').innerHTML = VUE.length ? VUE.slice(0, limite).map(carte).join('') : '<p>Aucun livre dans cette liste.</p>';
    $('#rv-plus').hidden = VUE.length <= limite;
    document.querySelectorAll('#rv-onglets button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.vue === vue)));
  }

  function csv() {
    const q = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
    const cols = ['Titre', 'Série', 'Numéro', 'Édition', 'État', 'Prix affiché', 'Ancien prix', 'Origine', 'À vérifier'];
    const lib = Object.fromEntries(ETATS);
    const lig = [];
    VUE.forEach((ed) => ETATS.forEach(([cle]) => { const l = ed.etats[cle], v = validation(ed, cle); if ((l && l.publie != null) || v) lig.push([ed.titre, ed.serie, ed.numero, ed.version, lib[cle], String(v ? v.prix : l.publie).replace('.', ','), !l || l.archive == null ? '' : String(l.archive).replace('.', ','), v ? `validé le ${jour(v.le)}` : origine(l), raison(l, v)].map(q).join(';')); }));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['﻿' + [cols.join(';')].concat(lig).join('\r\n')], { type: 'text/csv;charset=utf-8' }));
    a.download = 'verification-des-prix.csv'; document.body.appendChild(a); a.click(); a.remove();
  }

  // Fichier à transmettre : mêmes validations, dans le format lu par pipeline/validations.py
  async function envoyer() {
    const msg = $('#rv-envoi-msg'), dire = (t) => { msg.textContent = t; msg.hidden = false; };
    if (!jeton()) return dire('Votre connexion a expiré : reconnectez-vous avec le bouton du compte, en haut de la page. Vos validations sont gardées.');
    const par = {}, aEnvoyer = Object.entries(LOC).filter(([, v]) => !envoyee(v));
    if (!aEnvoyer.length) return dire('Rien à envoyer : vos validations sont déjà parties.');
    aEnvoyer.forEach(([cle, v]) => { const [isbn, etat] = cle.split('|'), k = `${isbn}|${v.decision}`; (par[k] = par[k] || {})[etat] = v.prix; });
    const lignes = Object.entries(par).map(([k, p]) => `${k.split('|')[0]} ; ${p.convenable ?? ''} ; ${p.bon ?? ''} ; ${p.tres_bon ?? ''}${k.endsWith('|confirme') ? ' ; confirme' : ''}`);
    $('#rv-envoyer').disabled = true; dire('Envoi en cours…');
    try {
      const r = await lancer('corriger-prix.yml', { corrections: lignes.join(' | ') });
      if (r.status === 204) { const t = Date.now(); aEnvoyer.forEach(([cle, v]) => { if (LOC[cle] === v) v.envoye = t; }); sauver(); afficher(); }      // envoyées : ne sont plus « à transmettre »
      dire(r.status === 204 ? `Envoyé (${lignes.length} livre${lignes.length > 1 ? 's' : ''}, ${aEnvoyer.length} prix). Le site sera à jour dans environ 2 minutes.`
        : r.status === 401 || r.status === 403 ? MSG_REFUS : `Échec de l'envoi : ${r.erreur || 'code ' + r.status}.`);
    } catch (err) { dire(err && err.name === 'AbortError' ? 'Le serveur ne répond pas (plus de 40 secondes). Vos validations sont gardées : réessayez dans quelques minutes.' : 'Envoi impossible : vérifiez votre connexion.'); }
    $('#rv-envoyer').disabled = false;
  }

  // Ajouter des livres : liste d'ISBN contrôlée ici (clé de contrôle, doublons, déjà dans la base), enregistrée ensuite par le lot « Ajouter des livres (ISBN) ».
  // Une ligne dont le premier élément n'est pas un nombre est un titre : le livre est ajouté sans ISBN (« Titre ; série ; numéro »).
  const ressembleIsbn = (brut) => /^\d+X?$/.test(String(brut).replace(/[\s-]/g, '').toUpperCase());
  const cleTitre = (x) => String(x || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\W+/g, ' ').trim();
  const isbn13De = (brut) => {
    const c = String(brut).replace(/[\s-]/g, '').toUpperCase();
    if (/^\d{13}$/.test(c)) return [...c].reduce((t, d, i) => t + d * (i % 2 ? 3 : 1), 0) % 10 === 0 ? c : null;
    if (/^\d{9}[\dX]$/.test(c)) {
      if ([...c].reduce((t, d, i) => t + (d === 'X' ? 10 : +d) * (10 - i), 0) % 11 !== 0) return null;
      const b = '978' + c.slice(0, 9), cle = (10 - [...b].reduce((t, d, i) => t + d * (i % 2 ? 3 : 1), 0) % 10) % 10;
      return b + cle;
    }
    return null;
  };
  const lireListe = (texte) => texte.replace(/[\u200b-\u200f\u202a-\u202e\u2060\ufeff]/g, '').replace(/\u00a0/g, ' ').split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith('#')).flatMap((l) => {
    if (/[;\t]/.test(l)) {
      const p = l.split(/[;\t]/).map((x) => x.trim()), [brut, serie = '', numero = '', titre = ''] = p;
      const isbns = p.slice(0, 3).filter((x) => x && ressembleIsbn(x) && x.replace(/\D/g, '').length >= 10);
      if (isbns.length >= 2) return p.filter((x) => x && ressembleIsbn(x)).map((x) => ({ brut: x, serie: '', numero: '', titre: '' }));   // « isbn ; isbn ; isbn » : une liste
      return [{ brut, serie, numero, titre }];
    }
    const mots = l.split(/[,\s]+/).filter(Boolean);
    if (!mots.some(ressembleIsbn)) return [{ brut: l, serie: '', numero: '', titre: '' }];     // aucun nombre sur la ligne : un titre
    return mots.map((brut) => ({ brut, serie: '', numero: '', titre: '' }));
  });
  let AJOUT = [];
  function verifierListe(catalogue) {
    const vus = new Set();
    AJOUT = lireListe($('#aj-texte').value).map((e) => {
      if (!ressembleIsbn(e.brut)) {                       // un titre : livre ajouté sans ISBN
        const cle = [cleTitre(e.brut), cleTitre(e.serie), String(e.numero).replace(/^0+/, '')].join('|');
        const connu = catalogue.titres.get(cleTitre(e.brut));
        if (connu && (!(e.serie && e.numero) || connu.serie === cleTitre(e.serie) && connu.numero === String(e.numero).replace(/^0+/, ''))) return { ...e, statut: 'deja', texte: `déjà dans la base : ${connu.label}` };
        if (vus.has(cle)) return { ...e, statut: 'doublon', texte: 'écrit deux fois dans la liste' };
        vus.add(cle);
        return { ...e, statut: 'nouveau', texte: ['sans ISBN', e.serie, e.numero && 'n° ' + e.numero].filter(Boolean).join(' · ') };
      }
      const isbn = isbn13De(e.brut);
      if (!isbn) return { ...e, statut: 'invalide', texte: 'ISBN invalide (vérifiez les chiffres)' };
      if (catalogue.isbn.has(isbn)) return { ...e, isbn, statut: 'deja', texte: `déjà dans la base : ${catalogue.isbn.get(isbn)}` };
      if (vus.has(isbn)) return { ...e, isbn, statut: 'doublon', texte: 'écrit deux fois dans la liste' };
      vus.add(isbn);
      return { ...e, isbn, statut: 'nouveau', texte: [e.serie, e.numero && 'n° ' + e.numero, e.titre].filter(Boolean).join(' · ') || 'la fiche sera complétée automatiquement' };
    });
    const nb = (st) => AJOUT.filter((a) => a.statut === st).length;
    const marque = { nouveau: '＋ À ajouter', deja: '= Déjà là', doublon: '= Doublon', invalide: '✗ Invalide' };
    $('#aj-liste').innerHTML = AJOUT.map((a) => `<li class="aj-${a.statut}"><strong>${esc(marque[a.statut])}</strong> <code>${esc(a.isbn || a.brut)}</code> <span>${esc(a.texte)}</span></li>`).join('');
    const n = nb('nouveau');
    $('#aj-bilan').textContent = AJOUT.length
      ? `${n} livre${n > 1 ? 's' : ''} à ajouter · ${nb('deja')} déjà dans la base · ${nb('doublon')} doublon${nb('doublon') > 1 ? 's' : ''} · ${nb('invalide')} invalide${nb('invalide') > 1 ? 's' : ''}`
      : 'Aucun ISBN dans la liste.';
    $('#aj-etapes').textContent = !n ? 'Rien à enregistrer.' : jeton() ? 'cliquez sur « Ajouter maintenant » : comptez environ 2 minutes, puis les livres apparaissent sur le site (les prix suivent au relevé).' : 'enregistrez votre jeton d\'accès dans « Envoi automatique » (plus haut) pour ajouter en un clic ; sinon copiez ou téléchargez la liste et transmettez-la moi.';
    ['#aj-copier', '#aj-telecharger'].forEach((s) => { $(s).disabled = !n; });
    $('#aj-lancer').hidden = !jeton() || !n;
    $('#aj-resultat').hidden = false;
    apercuBnf();
  }
  // Aperçu : pour chaque ISBN à ajouter sans titre, ce que la BnF connaît (titre, éditeur, année). Introuvable : la fiche sera cherchée chez
  // le libraire ; mieux vaut alors écrire « isbn ; série ; numéro ; titre ». Les réponses sont gardées pour ne pas interroger deux fois.
  const BNF = new Map();
  const isbn10De = (i13) => { const c = i13.slice(3, 12), k = (11 - [...c].reduce((t, d, i) => t + d * (10 - i), 0) % 11) % 11; return c + (k === 10 ? 'X' : k); };
  function notice(isbn) {                              // les notices anciennes sont indexées par l'ISBN-10, les récentes par l'ISBN-13 : on essaie les deux (comme le lot)
    if (BNF.has(isbn)) return BNF.get(isbn);
    const chercher = (num) => fetch(`https://catalogue.bnf.fr/api/SRU?version=1.2&operation=searchRetrieve&query=${encodeURIComponent(`bib.isbn adj "${num}"`)}&recordSchema=dublincore&maximumRecords=1`)
      .then((r) => r.text()).then((t) => {
        const x = new DOMParser().parseFromString(t, 'text/xml'), g = (n) => { const e = x.getElementsByTagNameNS('*', n)[0]; return e ? e.textContent.trim() : ''; };
        return g('title') ? { titre: g('title').split(' / ')[0], editeur: g('publisher'), annee: (g('date').match(/\d{4}/) || [''])[0] } : null;
      });
    const p = chercher(isbn10De(isbn)).then((n) => n || chercher(isbn)).catch(() => undefined);
    BNF.set(isbn, p);
    return p;
  }
  function apercuBnf() {
    document.querySelectorAll('#aj-liste li.aj-nouveau').forEach((li, i) => {
      const a = AJOUT.filter((x) => x.statut === 'nouveau')[i];
      if (!a || !a.isbn || a.titre) return;
      const zone = li.querySelector('span');
      const manque = [!a.serie && 'série', !a.numero && 'numéro'].filter(Boolean);
      const alerte = manque.length ? ` · ${manque.join(' et ')} à compléter ensuite` : '';
      zone.textContent = 'recherche de la fiche…';
      notice(a.isbn).then((n) => {
        if (n === undefined) zone.textContent = 'la BnF ne répond pas : la fiche sera complétée automatiquement' + alerte;
        else if (n) zone.textContent = `BnF : ${n.titre}${n.editeur ? ' · ' + n.editeur : ''}${n.annee ? ' · ' + n.annee : ''}${alerte}`;
        else { zone.textContent = 'inconnu de la BnF (livre récent ?) : écrivez « isbn ; série ; numéro ; titre » pour être sûr du résultat'; li.classList.add('aj-alerte'); }
      });
    });
  }
  const texteAjout = () => AJOUT.filter((a) => a.statut === 'nouveau').map((a) => (a.isbn ? [a.isbn, a.serie, a.numero, a.titre] : [a.brut, a.serie, a.numero]).join(' ; ').replace(/(\s;\s)+$/, '').replace(/\s;\s*$/, '')).join('\n');
  // Catalogue du site (ISBN et titres connus), chargé une fois : sert au formulaire d'ajout et au contrôle des demandes
  let CATALOGUE = null;
  function chargerCatalogue() {
    if (!CATALOGUE) CATALOGUE = fetch('data/versions.json').then((r) => r.json()).then((v) => {
      const label = (b) => `${b.titre} (${b.serie}${b.version ? ', ' + b.version : ''})`;
      return { isbn: new Map(v.filter((b) => b.isbn13).map((b) => [b.isbn13, label(b)])),
        titres: new Map(v.filter((b) => b.titre).map((b) => [cleTitre(b.titre), { label: label(b), serie: cleTitre(b.serie), numero: String(b.numero || '').replace(/^0+/, '') }])) };
    }).catch(() => ({ isbn: new Map(), titres: new Map() }));
    return CATALOGUE;
  }
  // Une ligne de demande est-elle bonne à ajouter ? ISBN valide (clé de contrôle), pas déjà dans la base, pas écrit deux fois
  function evaluerLigne(cat, ligne) {
    const elements = lireListe(ligne), vus = new Set();
    if (!elements.length) return { ok: false, texte: 'La ligne est vide.' };
    for (const e of elements) {
      if (!ressembleIsbn(e.brut)) {
        const connu = cat.titres.get(cleTitre(e.brut));
        if (connu && (!(e.serie && e.numero) || connu.serie === cleTitre(e.serie) && connu.numero === String(e.numero).replace(/^0+/, ''))) return { ok: false, texte: `Déjà dans la base : ${connu.label}.` };
        continue;
      }
      const isbn = isbn13De(e.brut);
      if (!isbn) return { ok: false, texte: `ISBN invalide : ${e.brut}. Vérifiez les chiffres (la clé de contrôle ne correspond pas).` };
      if (cat.isbn.has(isbn)) return { ok: false, texte: `Déjà dans la base : ${cat.isbn.get(isbn)}.` };
      if (vus.has(isbn)) return { ok: false, texte: `ISBN écrit deux fois : ${e.brut}.` };
      vus.add(isbn);
    }
    return { ok: true, texte: elements.length > 1 ? `${elements.length} livres à ajouter.` : 'Ligne correcte : le livre sera ajouté.' };
  }
  // Scan : après chaque livre lu, la liste est vérifiée puis envoyée toute seule (un seul envoi pour une rafale de scans).
  // Une liste contenant une ligne invalide n'est pas envoyée : elle reste affichée, pour correction.
  let minuterieScan = null;
  function envoiAutoScan() {
    chargerCatalogue().then((cat) => {
      verifierListe(cat);
      if (AJOUT.some((a) => a.statut === 'invalide')) return;
      if (!AJOUT.some((a) => a.statut === 'nouveau') || !jeton()) return;
      $('#aj-lancer').click();
    });
  }
  function initAjout() {
    if (!$('#aj-texte')) return;                       // pas d'onglet Ajouter sur cette page
    document.addEventListener('cdh-scan-ajout', () => { clearTimeout(minuterieScan); minuterieScan = setTimeout(envoiAutoScan, 1200); });
    $('#aj-verifier').addEventListener('click', () => { chargerCatalogue().then(verifierListe); });
    $('#aj-copier').addEventListener('click', () => {
      const t = texteAjout().replace(/\n/g, ' | '), ok = () => { $('#aj-copier').textContent = 'Liste copiée ✓'; setTimeout(() => { $('#aj-copier').textContent = 'Copier la liste à ajouter'; }, 2500); };
      if (navigator.clipboard) navigator.clipboard.writeText(t).then(ok).catch(() => { $('#aj-texte').value = t; $('#aj-texte').select(); });
      else { $('#aj-texte').value = t; $('#aj-texte').select(); }
    });
    $('#aj-telecharger').addEventListener('click', () => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([texteAjout() + '\n'], { type: 'text/plain;charset=utf-8' }));
      a.download = `isbn-a-ajouter-${aujourdhui()}.txt`; document.body.appendChild(a); a.click(); a.remove();
    });
  }

  // Les envois passent par le service technique (connexion Google du site, voir relais.js) : aucune clé GitHub sur l'appareil.
  // « jeton() » dit seulement si l'envoi en un clic est possible maintenant : relais en service et connexion encore valable.
  const jeton = () => (window.Relais && window.Relais.actif() ? 'relais' : null);
  const lancer = (lot, inputs) => window.Relais.envoyerLot(lot, (({ identite, ...reste }) => reste)(inputs));
  const MSG_REFUS = 'Ce compte n\'a pas accès à cette fonction, ou la connexion Google a expiré : reconnectez-vous avec le bouton du compte, en haut de la page.';
  function etatJeton() {
    $('#aj-lancer').hidden = !jeton() || !AJOUT.some((a) => a.statut === 'nouveau');
  }
  function initReglages() {
    if (!$('#aj-lancer')) return;                     // pas d'onglet Ajouter sur cette page
    $('#aj-lancer').addEventListener('click', async () => {
      const msg = $('#aj-msg'), dire = (t) => { msg.textContent = t; msg.hidden = false; };
      if (!jeton()) return dire('Votre connexion a expiré : reconnectez-vous avec le bouton du compte, en haut de la page.');
      $('#aj-lancer').disabled = true; dire('Envoi en cours…');
      try {
        const r = await lancer('ajout-isbn.yml', { liste: texteAjout().replace(/\n/g, ' | '), releve: 'oui' });
        if (r.status === 204) { $('#aj-texte').value = ''; AJOUT = []; }   // envoyé : la liste est vidée pour ne pas renvoyer ces livres au scan suivant
        dire(r.status === 204 ? 'Envoyé. Les livres seront sur le site dans environ 2 minutes, les prix après le relevé qui suit.'
          : r.status === 401 || r.status === 403 ? MSG_REFUS : `Échec de l'envoi : ${r.erreur || 'code ' + r.status}.`);
      } catch (e) { dire('Envoi impossible : vérifiez votre connexion.'); }
      $('#aj-lancer').disabled = false;
    });
    etatJeton();
  }
  initAjout();
  initReglages();

  /* ---------- Tendances : la cote monte-t-elle ou baisse-t-elle, et où ? (données : data/tendances.json) ---------- */
  function initTendances() {
    const pct = (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v * 100).toFixed(0).replace('.', ',') + ' %';
    const NOMS = { decennie: 'année d\'édition', version: 'version', serie: 'série', editeur: 'éditeur' };
    fetch('data/tendances.json', { cache: 'no-store' }).then((x) => (x.ok ? x.json() : null)).catch(() => null).then((T) => {
      if (!T) return;
      let dim = 'decennie', avec = false, ouvert = null;
      const NAT = { 'validé': 'prix validé', annonces: 'annonces', 'prix éditeur': 'prix éditeur' }, ABR = { convenable: 'C', bon: 'BE', tres_bon: 'TBE' };
      const detailGroupe = (l, cle) => {
        const eds = l.ids.map((i) => ({ i, ...T.detail[cle][i] })).sort((a, b) => a.var - b.var);
        return `<p class="sous">${l.n} édition${l.n > 1 ? 's' : ''}, de la plus forte baisse à la plus forte hausse. Chaque ligne montre l'ancienne cote et la cote publiée, par état.</p><ul class="tr-eds">` + eds.map((e) => {
          const s = e.var > 0.005 ? 'haut' : e.var < -0.005 ? 'bas' : 'stable', sources = [...new Set(e.lignes.map((x) => (x.nature === 'validé' ? (x.par ? 'prix validé par ' + x.par : NAT['validé']) : NAT[x.nature] || x.nature)))].join(', ');
          return `<li class="tr-ed"><div class="tr-ed-tete"><a href="./#q=${encodeURIComponent(e.isbn)}">${esc(e.titre)}</a><b class="tr-val tr-v-${s}">${pct(e.var)}</b></div>
            <small>${esc([e.serie, e.numero && e.numero !== '0' && e.numero !== '000' ? 'n° ' + parseInt(e.numero, 10) : '', e.version, e.annee, e.editeur].filter(Boolean).join(' · '))}</small>
            <small class="tr-etats">${e.lignes.map((x) => `${ABR[x.etat]} ${eur(x.archive)} → ${eur(x.publie)}`).join(' · ')}</small><small class="tr-src">Source : ${esc(sources)}</small></li>`;
        }).join('') + '</ul>';
      };
      const dessiner = () => {
        const cle = avec ? 'avec_editeur' : 'marche', g = T.global[cle], lignes = T.groupes[cle][dim] || [];
        $('#tr-resume').innerHTML = g.n
          ? `Par rapport à l'ancien relevé : <strong>${pct(g.mediane)}</strong> en médiane sur ${g.n} éditions comparées (${g.hausses} en hausse, ${g.baisses} en baisse, ${g.stables} stables).`
          : 'Pas encore assez de prix récents pour comparer avec l\'ancien relevé.';
        const max = Math.max(0.3, ...lignes.map((l) => Math.abs(l.mediane)));
        $('#tr-liste').innerHTML = lignes.map((l, k) => {
          const w = Math.min(50, Math.abs(l.mediane) / max * 50), s = l.mediane > 0.005 ? 'haut' : l.mediane < -0.005 ? 'bas' : 'stable';
          return `<li class="tr-item"><button type="button" class="tr-ligne${l.peu ? ' tr-peu' : ''}" data-k="${k}" aria-expanded="${ouvert === l.cle}" aria-controls="tr-d${k}"><span class="tr-nom">${esc(l.cle)}</span>
            <span class="tr-piste" aria-hidden="true"><i class="tr-barre tr-${s}" style="width:${w}%"></i></span>
            <b class="tr-val tr-v-${s}">${pct(l.mediane)}</b><small class="tr-n">${l.n} éd.${l.peu ? ' · peu de données' : ''}</small></button>
            <div class="tr-detail" id="tr-d${k}"${ouvert === l.cle ? '' : ' hidden'}>${ouvert === l.cle ? detailGroupe(l, cle) : ''}</div></li>`;
        }).join('') || '<li class="sous">Rien à comparer pour l\'instant.</li>';
        $('#tr-note').textContent = `Médiane de la variation entre l'ancien relevé et la cote publiée, par ${NOMS[dim]}. Seules comptent les cotes appuyées sur un prix récent (validé ou annonces) ; les autres n'ont pas bougé. Mis à jour le ${jour(T.date)}.`;
      };
      $('#tr-onglets').addEventListener('click', (e) => {
        const b = e.target.closest('[data-dim]'); if (!b) return;
        dim = b.dataset.dim; ouvert = null; document.querySelectorAll('#tr-onglets button').forEach((x) => x.setAttribute('aria-selected', String(x === b))); dessiner();
      });
      $('#tr-editeur').addEventListener('change', (e) => { avec = e.target.checked; ouvert = null; dessiner(); });
      $('#tr-liste').addEventListener('click', (e) => {
        const b = e.target.closest('.tr-ligne'); if (!b) return;
        const l = T.groupes[avec ? 'avec_editeur' : 'marche'][dim][+b.dataset.k];
        ouvert = ouvert === l.cle ? null : l.cle; dessiner();
        const nouveau = document.querySelector(`.tr-ligne[data-k="${b.dataset.k}"]`); if (ouvert && nouveau) nouveau.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      });
      // Courbe : indice des cotes publiées à chaque publication (100 à la première)
      const pts = T.temps || [];
      if (pts.length > 1) {
        const W = 300, H = 90, P = 14, vals = pts.map((p) => p.indice), lo = Math.min(...vals, 100) - 1, hi = Math.max(...vals, 100) + 1;
        const x = (i) => P + (i / (pts.length - 1)) * (W - 2 * P), y = (v) => H - P - ((v - lo) / (hi - lo)) * (H - 2 * P);
        const ligne = pts.map((p, i) => `${x(i).toFixed(1)},${y(p.indice).toFixed(1)}`).join(' ');
        const dernier = pts[pts.length - 1], d = (dernier.indice - 100) / 100;
        $('#tr-temps').innerHTML = `<svg viewBox="0 0 ${W} ${H}" class="tr-courbe" role="img" aria-label="Indice des cotes publiées : ${dernier.indice.toFixed(1).replace('.', ',')} au ${jour(dernier.date)}, base 100 au ${jour(pts[0].date)}">
          <line x1="${P}" x2="${W - P}" y1="${y(100).toFixed(1)}" y2="${y(100).toFixed(1)}" class="tr-base"/>
          <polyline points="${ligne}" class="tr-trait"/>
          ${pts.map((p, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(p.indice).toFixed(1)}" r="3.2" class="tr-point"><title>${jour(p.date)} : ${p.indice.toFixed(1).replace('.', ',')}</title></circle>`).join('')}
          <text x="${P}" y="${H - 1}" class="tr-axe">${jour(pts[0].date)}</text><text x="${W - P}" y="${H - 1}" text-anchor="end" class="tr-axe">${jour(dernier.date)}</text></svg>
          <p class="sous">Indice des cotes publiées (100 le ${jour(pts[0].date)}) : <strong>${dernier.indice.toFixed(1).replace('.', ',')}</strong>, soit ${pct(d)} sur ${pts.length} publications, pour ${dernier.n} cotes suivies depuis le début.</p>`;
      } else $('#tr-temps').innerHTML = '<p class="sous">La courbe apparaîtra à la prochaine publication des cotes.</p>';
      $('#rv-tendances').hidden = false;
      dessiner();
    });
  }
  initTendances();
  document.addEventListener('cdh-compte', () => { etatJeton(); });   // déconnexion : la porte se referme

  // Sections de la page : un seul panneau à la fois ; les onglets Tendances et Demandes n'apparaissent que si leur contenu est disponible
  // Annonces retenues par le dernier relevé, eBay et librairies (data/annonces.json) : onglet « Annonces » et lien « Voir les annonces » de chaque livre
  let ANN = null, annChargees = false;
  const INFO_ED = {};          // par édition : jaquette, éditeur, année (data/versions.json), pour l'onglet Annonces
  const chargerAnnonces = () => {
    if (annChargees) return annChargees;
    annChargees = window.Relais.lireAnnonces(true).catch(() => null)
      .then((a) => { ANN = a && a.annonces ? a : null; return ANN; });
    return annChargees;
  };
  const estNiveau3 = () => !!window.Compte && window.Compte.role() === 'superadmin';        // toutes les annonces : le niveau 3 seul (lues par le service technique)
  const estNiveau2 = () => !!window.Compte && ['admin', 'superadmin'].includes(window.Compte.role());        // Butin : niveaux 2 et 3
  // Butin : le service technique ne sert aux niveau 2 que les bonnes affaires (data/processed/butin.json), jamais la liste complète
  let BUT = null, butChargees = false;
  const chargerButin = () => {
    if (butChargees) return butChargees;
    butChargees = window.Relais.lireButin((cache) => { if (!BUT && cache && cache.annonces) { BUT = cache; dessinerPepites(); } }).catch(() => null)          // le Butin gardé s'affiche tout de suite
      .then((a) => { if (a && a.annonces) BUT = a; else if (!BUT) butChargees = null; return BUT; });
    return butChargees;
  };
  const aDesAnnonces = (ed) => estNiveau3() && !!(ANN && ed.isbn && ANN.annonces[ed.isbn]);
  const voirAnnonces = (ed) => estNiveau3() && !!(ANN && ed.isbn);          // le lien est toujours là : sans annonce retenue, la fenêtre dit d'où vient le prix
  function annoncesEdition(ed) {
    const par = ANN.annonces[ed.isbn] || {};
    const blocs = ETATS.map(([cle, lib]) => {
      const l = par[cle];
      if (!l || !l.length) return '';
      const disp = l.length > 1 && l[l.length - 1][0] > l[0][0] * 3 ? ' · prix très dispersés' : '';
      const dateRef = (origine) => (enLigne(origine) ? null : ANN.date_ebay);          // Leboncoin : en ligne tant que non signalée vendue (le bot ne revoit pas les anciennes)
      const partie = ([, , , origine, vue]) => !!(vue && dateRef(origine) && vue < dateRef(origine));          // annonce non revue au dernier relevé : retirée d'eBay ou vendue
      const nbPartie = l.filter(partie).length;
      return `<h4>${lib} · ${l.length} annonce${l.length > 1 ? 's' : ''}${nbPartie ? ` (dont ${nbPartie} non revue${nbPartie > 1 ? 's' : ''} au dernier relevé)` : ''}${disp}</h4><ul>${l.map((a) => { const [prix, titre, lien, origine, vue] = a; return `<li><span class="rv-ann-prix">${eur(prix)}</span> <a href="${esc(lien)}" target="_blank" rel="noopener noreferrer" aria-label="Ouvrir l'annonce${origine === 'librairie' ? ' de la librairie' : ' sur eBay'} (nouvel onglet) : ${esc(titre)}">${esc(titre)} ↗</a>${origine === 'titre' ? ' <span class="rv-ann-titre">trouvée par le titre</span>' : ''}${partie(a) ? ` <span class="rv-ann-titre">non revue au dernier relevé · vue le ${jour(vue)}</span>` : ''}</li>`; }).join('')}</ul>`;
    }).join('');
    const raisons = ETATS.map(([cle, lib]) => { const l = ed.etats[cle], o = l ? origine(l) : ''; return o ? `<li>${lib} : ${esc(o)}</li>` : ''; }).join('');
    return `<h3 class="rv-ann-livre">${esc(ed.titre)} <span class="sous">${esc(ed.serie)}${ed.numero && !/^0+$/.test(ed.numero) ? ' n° ' + esc(ed.numero) : ''} · ${esc(ed.version)}</span></h3>${blocs || `<p class="sous">Aucune annonce retenue pour cette édition.</p>${raisons ? `<p class="sous">D'où viennent ses prix :</p><ul>${raisons}</ul>` : ''}`}`;
  }
  // Fenêtre ouverte depuis un livre de l'onglet Prix
  function ouvrirAnnonces(ed) { ouvrirFenetreAnnonces(annoncesEdition(ed)); }
  function ouvrirFenetreAnnonces(corps) {
    let dlg = $('#an-dialog');
    if (!dlg) {
      dlg = document.createElement('dialog');
      dlg.id = 'an-dialog'; dlg.className = 'an-dialog'; dlg.setAttribute('aria-labelledby', 'an-dialog-titre');
      dlg.innerHTML = '<div class="an-cadre"><div class="an-tete"><p class="surtitre" id="an-dialog-titre">Annonces retenues (eBay, librairies, Leboncoin et Vinted)</p><button type="button" class="bouton bouton-clair" id="an-fermer">Fermer</button></div><div id="an-dialog-corps"></div><p class="sous">Relevé du <span id="an-dialog-date"></span>. Ouvrez une annonce pour vérifier que c\'est bien le bon livre, dans le bon état.</p></div>';
      document.body.appendChild(dlg);
      dlg.addEventListener('click', (e) => { if (e.target === dlg || e.target.id === 'an-fermer') dlg.close(); });
    }
    $('#an-dialog-corps').innerHTML = corps;
    $('#an-dialog-date').textContent = jour(ANN.date);
    dlg.showModal();
  }
  // Annonces d'un groupe de l'indice (une version × un éditeur, ou l'une de ses séries) : une fenêtre, les livres rangés par série
  const groupeDe = (ed) => `${ed.version} · ${EDITEUR[ed.id] || 'éditeur inconnu'}`;
  const pl = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`;
  const nbAnnonces = (ed) => ETATS.reduce((t, [cle]) => t + ((ANN.annonces[ed.isbn] || {})[cle] || []).length, 0);
  function ouvrirAnnoncesGroupe(groupe, serie) {
    chargerAnnonces().then(() => {
      if (!ANN) return;
      const eds = EDITIONS.filter((ed) => ed.isbn && groupeDe(ed) === groupe && (!serie || ed.serie === serie) && nbAnnonces(ed))
        .sort((a, b) => a.serie.localeCompare(b.serie, 'fr') || (parseInt(a.numero, 10) || 0) - (parseInt(b.numero, 10) || 0));
      const n = eds.reduce((t, ed) => t + nbAnnonces(ed), 0);
      ouvrirFenetreAnnonces(`<h3 class="rv-ann-groupe">${esc(serie ? `${serie} · ${groupe}` : groupe)} <span class="sous">${pl(n, 'annonce')} · ${pl(eds.length, 'livre')}</span></h3>${eds.map(annoncesEdition).join('') || '<p class="sous">Aucune annonce retenue pour ce groupe.</p>'}`);
    });
  }
  document.addEventListener('click', (e) => {
    const g = e.target.closest('[data-ind-annonces]');
    if (g) { ouvrirAnnoncesGroupe(g.dataset.indAnnonces, g.dataset.serie || ''); return; }
    const b = e.target.closest('[data-annonces]');
    if (!b) return;
    const ed = EDITIONS.find((x) => x.id === b.dataset.annonces);
    if (ed && voirAnnonces(ed)) ouvrirAnnonces(ed);
  });

  // Onglet « Annonces » : recherche d'un livre, puis ses annonces
  function initAnnonces() {
    const champ = $('#an-q'), liste = $('#an-liste'), etat = $('#an-etat');
    if (!champ) return;
    const dessiner = () => {
      const clair = (t) => norm(t).replace(/œ/g, 'oe').replace(/æ/g, 'ae').replace(/[^a-z0-9]+/g, ' ').trim();
      const mots = clair(champ.value).split(' ').filter(Boolean), q = mots.join(' ');
      if (!ANN) { etat.textContent = annChargees ? 'Pas encore d\'annonces enregistrées : elles apparaîtront après le prochain relevé des prix.' : 'Chargement…'; liste.innerHTML = ''; return; }
      const nbEd = Object.keys(ANN.annonces).length;
      // Sans recherche : les éditions dont une annonce a été vue le plus récemment
      const derniereVue = (ed) => Object.values(ANN.annonces[ed.isbn] || {}).reduce((m, l) => l.reduce((n, x) => (x[4] && x[4] > n ? x[4] : n), m), '');
      if (q.length < 2) {
        const recentes = EDITIONS.filter(aDesAnnonces).map((ed) => [ed, derniereVue(ed)]).sort((x, y) => (x[1] < y[1] ? 1 : x[1] > y[1] ? -1 : 0)).slice(0, 12).map((x) => x[0]);
        etat.textContent = `Relevé du ${jour(ANN.date)} : annonces retenues pour ${nbEd} éditions. Voici les ${recentes.length} dont les annonces ont été vues le plus récemment ; tapez au moins deux lettres pour chercher un livre.`;
        liste.innerHTML = recentes.map((ed) => `<article class="rv-edition">${annoncesEdition(ed)}</article>`).join('');
        return;
      }
      const trouves = EDITIONS.filter((ed) => aDesAnnonces(ed) && (() => { const t = clair(ed.titre + ' ' + ed.serie + ' ' + (ed.numero || '')); return mots.every((m) => t.includes(m)); })()).slice(0, 12);
      etat.textContent = trouves.length ? `${trouves.length} édition${trouves.length > 1 ? 's' : ''}${trouves.length === 12 ? ' (les 12 premières : précisez la recherche)' : ''}.` : 'Aucune édition avec des annonces retenues pour cette recherche.';
      liste.innerHTML = trouves.map((ed) => `<article class="rv-edition">${annoncesEdition(ed)}</article>`).join('');
    };
    champ.addEventListener('input', dessiner);
    document.addEventListener('cdh-pane', (e) => { if (e.detail === 'annonces' && estNiveau3()) chargerAnnonces().then(dessiner); });
    dessiner();
  }

  // Onglet « Butin » : annonces encore en ligne à 50 % du prix du site ou moins (même édition, même état), réservé au niveau 3 comme les annonces.
  // Point à vérifier : voir pointsAVerifier ; sans point, l'annonce est retenue sans réserve.
  // « À trouver » de la personne (liste gardée sur l'appareil et synchronisée avec son Drive) : les annonces de ces livres sont signalées
  const souhaits = () => { try { return JSON.parse(localStorage.getItem('cote-souhaits-v1') || '{}') || {}; } catch (e) { return {}; } };
  const SEUIL_ABERRANT = 3;          // une annonce à 3 fois le prix du très bon état ou plus : prix fou ou annonce trompeuse, affichée mais exclue de la cote (décision du propriétaire ; même seuil dans pipeline/prix_aberrants.py)
  const SEUIL_PEPITE = 0.5, ECONOMIE_MINI = 3, ECONOMIE_FORTE = 30, ABR_ETAT = { convenable: 'C', bon: 'BE', tres_bon: 'TBE' };
  // Corrections du propriétaire (édition confirmée, rattachée à une autre édition, ou annonce exclue) : {lien: {statut, isbn13, le, par, note}}
  const corrigees = () => (ANN && ANN.corrigees) || {};
  // Mention « Vendu » : l'annonce reste affichée (correction « vendue »)
  const vendueHtml = (a) => (corrigees()[a.lien] && corrigees()[a.lien].statut === 'vendue' ? '<span class="an-vendu">Vendu</span>' : '');
  let NB_CORR = 0;
  // Panneau « Corriger l'édition » d'une annonce : les jaquettes des éditions du livre à comparer avec la photo de l'annonce, puis un choix
  // En mode lite (liste Annonces), le panneau reste replié : le bouton « Corriger » de la ligne l'ouvre
  function panneauCorrection(a, lite) {
    const livre = (INFO_ED[a.ed.id] || {}).livre;
    const eds = Object.values(INFO_ED).filter((x) => livre && x.livre === livre && x.isbn).sort((x, y) => String(x.version).localeCompare(String(y.version), 'fr', { numeric: true }));
    if (!estNiveau3() || !a.lien || !eds.length) return '';
    const c = corrigees()[a.lien], nom = `corr-${NB_CORR += 1}`;
    const fait = c ? `<span class="corr-fait">${c.statut === 'exclue' ? 'Annonce exclue par vous' : c.statut === 'vendue' ? 'Annonce marquée vendue par vous' : c.statut === 'confirmee' ?'Édition confirmée par vous' : 'Édition corrigée par vous'}</span>` : '';
    const opt = (x) => `<label class="corr-opt"><input type="radio" name="${nom}" value="${esc(x.isbn)}"${x.isbn === a.ed.isbn ? ' checked' : ''}>${x.mini ? `<img src="${esc(x.mini)}" alt="" width="40" height="56" loading="lazy">` : ''}<span>${esc(x.version)}${x.annee ? ' · ' + esc(x.annee) : ''}${x.isbn === a.ed.isbn ? ' <small>(actuelle)</small>' : ''}</span></label>`;
    return `<details class="corr-ann${lite ? ' corr-lite' : ''}" data-lien="${esc(a.lien)}" data-isbn="${esc(a.ed.isbn)}"><summary>Corriger l'édition${!lite && fait ? ' · ' : ''}${lite ? '' : fait}</summary>${lite && fait ? `<p class="corr-fait-txt">${fait}</p>` : ''}
      <p class="sous">Ouvrez l'annonce, comparez sa photo aux jaquettes, puis choisissez l'édition. Votre choix remplace celui du relevé, aussi pour les relevés suivants.</p>
      <div class="corr-opts">${eds.map(opt).join('')}<label class="corr-opt corr-exclure"><input type="checkbox" class="corr-vendu-case"${c && c.statut === 'vendue' ? ' checked' : ''}><span>Annonce vendue : l'afficher avec la mention « Vendu »</span></label><label class="corr-opt corr-exclure"><input type="radio" name="${nom}" value="exclue"><span>Pas ce livre, ou un lot : exclure l'annonce</span></label></div>
      <label class="corr-note">Note <input type="text" maxlength="120" placeholder="facultatif"></label>
      <button type="button" class="bouton bouton-clair corr-go">Enregistrer</button><p class="corr-msg" role="status" hidden></p></details>`;
  }
  document.addEventListener('click', async (e) => {
    const go = e.target.closest && e.target.closest('.corr-go');
    if (!go) return;
    const bloc = go.closest('.corr-ann'), msg = bloc.querySelector('.corr-msg'), dire = (t) => { msg.textContent = t; msg.hidden = false; };
    const choix = bloc.querySelector('input[type=radio]:checked');
    if (!choix) return dire('Choisissez une édition, ou « exclure l\'annonce ».');
    const vendu = bloc.querySelector('.corr-vendu-case').checked;
    const statut = choix.value === 'exclue' ? 'exclue' : vendu ? 'vendue' : choix.value === bloc.dataset.isbn ? 'confirmee' : 'reaffectee';
    const note = (bloc.querySelector('.corr-note input').value || '').replace(/[;|\r\n]+/g, ' ').trim();
    if (!(window.Relais && window.Relais.actif())) return dire('Votre connexion a expiré : reconnectez-vous avec le bouton du compte, en haut de la page.');
    go.disabled = true; dire('Envoi en cours…');
    try {
      const r = await lancer('corriger-prix.yml', { corrections: `annonce ; ${bloc.dataset.lien} ; ${statut} ; ${statut === 'exclue' ? '' : choix.value} ; ${note}` });
      if (r.status === 204) dire('Envoyé. Le site sera à jour dans environ 2 minutes : rechargez la page ensuite.');
      else if (r.status === 401 || r.status === 403) dire('Ce compte n\'a pas accès à cette fonction, ou la connexion Google a expiré : reconnectez-vous.');
      else dire(`Échec de l'envoi : ${r.erreur || 'code ' + r.status}.`);
    } catch (err) { dire('Envoi impossible : vérifiez votre connexion.'); }
    go.disabled = false;
  });
  // Points à vérifier d'une annonce (liste vide si rien à vérifier). Leboncoin et Vinted : le bot a comparé la photo aux jaquettes et n'envoie que les annonces dont
  // l'édition est nette ; l'état est celui du vendeur. eBay trouvée par le titre : photo comparée à la jaquette au relevé, annonce gardée seulement si elle concorde.
  const pointsAVerifier = (origine, suppose) => {
    const points = [];
    if (origine === 'librairie' || origine === 'leboncoin' || origine === 'vinted') return points;
    if (suppose === 1) points.push("État supposé très bon");
    else if (suppose == null) points.push("État à confirmer");
    return points;
  };
  // Annonces reçues (Zagor) : toutes les annonces des derniers relevés, pour les statistiques du graphique
  let TOUTES_RC = null, redessinerCapt = () => {};
  const TRANCHES = [[0, 5, 'Moins de 5 €'], [5, 10, '5 à 10 €'], [10, 20, '10 à 20 €'], [20, 50, '20 à 50 €'], [50, Infinity, '50 € et plus']];
  const estPepite = (a) => a.v === 'super' || a.v === 'pepite';
  // Parts par verdict (seules les annonces dont le site a un prix comptent)
  function statsRecues(lignes) {
    const NOMS = { ebay: 'eBay', leboncoin: 'Leboncoin', vinted: 'Vinted', librairie: 'Librairies', ...REVENDEURS };
    const groupe = (liste, nom) => {
      const avec = liste.filter((a) => a.v);
      const part = (...vs) => (avec.length ? avec.filter((a) => vs.includes(a.v)).length / avec.length : null);
      return { nom, n: liste.length, base: avec.length, pep: liste.filter(estPepite).length, pepPart: part('super', 'pepite'), pas: part('dessous'), dans: part('dans'), cher: part('dessus', 'cher') };
    };
    const plateformes = Object.keys(NOMS).map((fam) => groupe(lignes.filter((a) => a.fam === fam), NOMS[fam])).filter((g) => g.base);
    const tranches = TRANCHES.map(([min, max, nom]) => groupe(lignes.filter((a) => a.prix >= min && a.prix < max), nom)).filter((g) => g.n);
    const pct = (x) => (x == null ? '–' : `${Math.round(x * 100)} %`);
    const haut = (cle) => plateformes.reduce((m, g) => (g[cle] > m[cle] ? g : m), plateformes[0]);
    const resume = plateformes.length ? `<p class="stats-resume">Plus de pépites : <b>${esc(haut('pepPart').nom)}</b> (${pct(haut('pepPart').pepPart)} des annonces). Plus souvent trop cher : <b>${esc(haut('cher').nom)}</b> (${pct(haut('cher').cher)}). Plus souvent pas cher : <b>${esc(haut('pas').nom)}</b> (${pct(haut('pas').pas)}).</p>` : '';
    const ligne = (g, colonnes) => `<tr><th scope="row">${esc(g.nom)}</th>${colonnes(g)}</tr>`;
    const tete = (cols) => `<thead><tr>${cols.map((c) => `<th scope="col">${c}</th>`).join('')}</tr></thead>`;
    const tabPlat = `<table class="captures-table"><caption class="sr-only">Parts par verdict, par plateforme</caption>${tete(['Plateforme', 'Annonces', 'Pépites', 'Pas cher', 'Dans les prix', 'Trop cher'])}<tbody>${plateformes.map((g) => ligne(g, (x) => `<td>${x.n}</td><td>${pct(x.pepPart)}</td><td>${pct(x.pas)}</td><td>${pct(x.dans)}</td><td>${pct(x.cher)}</td>`)).join('')}</tbody></table>`;
    const tabTr = `<table class="captures-table"><caption class="sr-only">Statistiques par tranche de prix</caption>${tete(['Tranche', 'Annonces', 'Pépites', 'Part de pépites'])}<tbody>${tranches.map((g) => ligne(g, (x) => `<td>${x.n}</td><td>${x.pep}</td><td>${pct(x.n ? x.pep / x.n : null)}</td>`)).join('')}</tbody></table>`;
    return `<div class="stats-rc">${resume}<h4 class="stats-titre">Par plateforme</h4><div class="captures-defile">${tabPlat}</div><h4 class="stats-titre">Par tranche de prix</h4><div class="captures-defile">${tabTr}</div></div>`;
  }
  const statsHtml = () => (TOUTES_RC && TOUTES_RC.length ? statsRecues(TOUTES_RC) + (TOUTES_RC.nbAberrantes ? `<p class="sous">${TOUTES_RC.nbAberrantes} annonces à 3 fois le prix du très bon état ou plus sont exclues de ces chiffres.</p>` : '') : '');
  let dessinerPepites = () => {};
  function pepites() {
    const lignes = [];
    if (!BUT) return lignes;
    EDITIONS.forEach((ed) => ETATS.forEach(([cle, lib]) => {
      const l = ed.etats[cle], pub = l && l.publie, liste = ed.isbn && BUT.annonces[ed.isbn] && BUT.annonces[ed.isbn][cle];
      if (!pub || !liste) return;
      liste.forEach(([prix, titre, lien, origine, vue, suppose]) => {
        if (origine === 'librairie' && cle === 'convenable') return;                                  // exemplaire abîmé en librairie (fiche : « Un peu abîmé ») : pas une pépite
        if (!enLigne(origine) && vue && BUT.date_ebay && vue < BUT.date_ebay) return;                 // non revue au dernier relevé : le Butin ne retient que ce qui a été revu
        if ((prix > SEUIL_PEPITE * pub || pub - prix < ECONOMIE_MINI) && pub - prix < ECONOMIE_FORTE) return;
        const raisons = pointsAVerifier(origine, suppose);
        lignes.push({ ed, cle, lib, prix, pub, titre, lien, origine, raisons, vue, premiere: (BUT.premieres && BUT.premieres[lien]) || vue });
      });
    }));
    return lignes.sort((x, y) => (y.pub - y.prix) - (x.pub - x.prix));
  }
  // Première apparition : une date-heure (UTC) pour les annonces apparues depuis que le site la retient, une date seule pour les plus anciennes
  const heureConnue = (p) => !!p.premiere && p.premiere.length > 10 && !Number.isNaN(Date.parse(p.premiere));
  const nouvelle = (p) => heureConnue(p) && Date.now() - Date.parse(p.premiere) < 24 * 3600 * 1000;
  // Date et heure concises (heure de Paris) : « Repérée 27 oct. · 14:30 » quand l'heure est connue, sinon « Vue le 27 oct. » (dernière observation)
  const reperee = (p) => {
    if (heureConnue(p)) return 'Repérée ' + new Date(p.premiere).toLocaleString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).replace(',', ' ·');
    const j = p.premiere || p.vue;
    return j && /^\d{4}-\d\d-\d\d$/.test(j) ? 'Vue le ' + new Date(j + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }) : '';
  };
  // Super pépite : au moins 30 € d'économie et au moins 70 % de réduction sur le prix du site
  const superPepite = (p) => p.pub - p.prix >= ECONOMIE_FORTE && p.prix <= (1 - 0.7) * p.pub;
  function cartePepite(p) {
    const eco = p.pub - p.prix, pct = Math.round((1 - p.prix / p.pub) * 100), solide = !p.raisons.length;
    const num = p.ed.numero && !/^0+$/.test(p.ed.numero) ? ' n° ' + esc(p.ed.numero) : '';
    const lieu = p.origine === 'librairie' ? ' de la librairie' : p.origine === 'leboncoin' ? ' sur Leboncoin' : p.origine === 'vinted' ? ' sur Vinted' : REVENDEURS[p.origine] ? ` chez ${REVENDEURS[p.origine]}` : ' sur eBay';
    const source = p.origine === 'librairie' ? 'Librairie' : p.origine === 'leboncoin' ? 'Leboncoin' : p.origine === 'vinted' ? 'Vinted' : REVENDEURS[p.origine] || 'eBay';          // libellé visible de la source
    const img = JAQ[p.ed.id] ? `<img src="${esc(JAQ[p.ed.id])}" alt="Jaquette de ${esc(p.ed.titre)}" width="88" height="124" loading="lazy" decoding="async">`
      : `<span class="jaq-vide pp-sans-jaq"><span>${esc(p.ed.titre)}</span></span>`;
    return `<article class="livre-carte pp-carte ${solide ? 'solide' : 'verifier'}"><a class="couv" href="./#fiche=${encodeURIComponent(p.ed.id)}" aria-label="Ouvrir la fiche du livre : ${esc(p.ed.titre)}">${img}` +
      (superPepite(p) ? `<span class="pp-super">Super pépite</span>` : '') +
      (p.trouver ? `<span class="pp-trouver">★ À trouver</span>` : '') +
      (nouvelle(p) ? `<span class="pp-nouveau">Nouveau</span>` : '') +
      `<span class="pp-voile"><strong class="pp-prix">${eur(p.prix)}</strong><span class="pp-pct">−${pct} %</span></span></a>` +
      `<span class="infos"><a class="titre" href="./#fiche=${encodeURIComponent(p.ed.id)}">${esc(p.ed.titre)}</a>` +
      `<span class="meta">${esc(p.ed.serie)}${num} · ${esc(p.ed.version)} · ${esc(p.lib)}</span>` +
      `<span class="meta pp-eco">au lieu de ${eur(p.pub)} · ${eur(eco)} d'économie</span>` +
      `<span class="meta pp-source">Source : ${source}</span>` + vendueHtml(p) +
      (reperee(p) ? `<span class="meta pp-reperee">${esc(reperee(p))}</span>` : '') +
      (solide ? '' : `<span class="meta pp-raison">${p.raisons.map(esc).join(' · ')}</span>`) + panneauCorrection(p) + `</span>` +
      `<a class="pp-ouvrir" href="${esc(p.lien)}" target="_blank" rel="noopener noreferrer" aria-label="Ouvrir l'annonce${lieu} (nouvel onglet) : ${esc(p.titre)}">Ouvrir l'annonce ↗</a>` +
      (estNiveau3() ? `<button type="button" class="bouton-lien pp-offrir" data-offrir="${esc(p.ed.id)}|${esc(p.cle)}|${esc(p.lien)}">Offrir</button>` : '') + `</article>`;
  }
  function initPepites() {
    const liste = $('#pp-liste'), etat = $('#pp-etat'), solides = $('#pp-solides'), tri = $('#pp-tri'), trouver = $('#pp-trouver');
    if (!liste) return;
    // Retour de la fiche : tri, filtres et position sont gardés au clic, puis remis à la réouverture de la page
    let etatARestaurer = null, defilementEnAttente = null;
    try { const o = JSON.parse(sessionStorage.getItem('cdh-butin-etat') || 'null'); if (o && Date.now() - o.t < 2 * 3600 * 1000) etatARestaurer = o; sessionStorage.removeItem('cdh-butin-etat'); } catch (e) { /* sans stockage : retour à la liste de départ */ }
    liste.addEventListener('click', (e) => {
      if (!e.target.closest('a.couv, a.titre')) return;
      try {
        sessionStorage.setItem('cdh-butin-etat', JSON.stringify({ t: Date.now(), y: window.scrollY, tri: tri.value, sol: solides.checked, tr: trouver.checked }));
        sessionStorage.setItem('cdh-retour-fiche', 'butin.html#pepites');
      } catch (er) { /* tant pis */ }
    });
    try { const m = localStorage.getItem('cdh-butin-tri'); if (m && [...tri.options].some((o) => o.value === m)) tri.value = m; } catch (e) { /* sans stockage : tri par défaut */ }
    const triUrl = new URLSearchParams(location.search).get('tri');
    if (triUrl && [...tri.options].some((o) => o.value === triUrl)) tri.value = triUrl;          // arrivée par « nouvelles annonces au Butin »
    // Les listes arrivent classées « sans point d'abord, puis économie » ; les autres choix reclassent toute la liste (à égalité : l'économie la plus grande d'abord)
    const ordonner = (l, cle) => {
      if (cle === 'solides') return l;
      const eco = (p) => p.pub - p.prix, pct = (p) => 1 - p.prix / p.pub;
      const f = { eco: (a, b) => eco(b) - eco(a), pct: (a, b) => pct(b) - pct(a), prix: (a, b) => a.prix - b.prix,
        date: (a, b) => (b.premiere || '').localeCompare(a.premiere || '') || pct(b) - pct(a), titre: (a, b) => a.ed.titre.localeCompare(b.ed.titre, 'fr') }[cle];
      return [...l].sort((a, b) => f(a, b) || eco(b) - eco(a));
    };
    tri.addEventListener('change', () => { try { localStorage.setItem('cdh-butin-tri', tri.value); } catch (e) { /* tant pis */ } dessinerPepites(); });
    // Annonces captées par jour : colonnes empilées + tableau
    const SOURCES_CAPT = [['ebay', 'eBay'], ['leboncoin', 'Leboncoin'], ['vinted', 'Vinted'], ['librairie', 'Librairies'], ...Object.entries(REVENDEURS)];
    const jourCourtCapt = (cle) => new Date(cle + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'numeric' });
    function svgCaptures(jours, depuis, largeur) {
      const H = 190, g = 8, b = 26, h = H - 20 - b, n = jours.length, pas = (largeur - 2 * g) / n;
      const max = Math.max(10, ...jours.map((j) => Math.max(...SOURCES_CAPT.map(([src]) => j.v[src] || 0))));
      const px = (k) => g + k * pas + pas / 2, y = (v) => 14 + h - (v / max) * h;
      const saut = n <= 8 ? 1 : largeur < 420 ? 4 : 2;
      let lignes = '', points = '', zones = '', etiquettes = '';
      SOURCES_CAPT.forEach(([src]) => {
        for (let k = 1; k < n; k += 1) {
          const estime = depuis && jours[k].cle < depuis;
          lignes += `<line x1="${px(k - 1)}" y1="${y(jours[k - 1].v[src] || 0)}" x2="${px(k)}" y2="${y(jours[k].v[src] || 0)}" class="cp-ligne cp-${src}${estime ? ' cp-estime' : ''}${jours[k].enCours ? ' cp-encours' : ''}"/>`;
        }
        jours.forEach((j, k) => { if (!(depuis && j.cle < depuis)) points += `<circle cx="${px(k)}" cy="${y(j.v[src] || 0)}" r="3" class="cp-pt cp-${src}${j.enCours ? ' cp-encours' : ''}"/>`; });
      });
      jours.forEach((j, k) => {
        const total = SOURCES_CAPT.reduce((t, [src]) => t + (j.v[src] || 0), 0);
        const detail = SOURCES_CAPT.map(([src, nom]) => `${nom} : ${j.v[src] || 0}`).join(', ');
        if ((n - 1 - k) % saut === 0) etiquettes += `<text x="${px(k)}" y="${H - 8}" class="cp-axe" text-anchor="middle">${jourCourtCapt(j.cle)}</text>`;
        zones += `<g class="cp-col" tabindex="0" data-i="${k}" role="img" aria-label="${esc(jourCourtCapt(j.cle))}${j.enCours ? ' (en cours)' : ''} : ${total} annonces (${esc(detail)})"><rect x="${g + k * pas}" y="0" width="${pas}" height="${H - b}" class="cp-zone"/><line x1="${px(k)}" x2="${px(k)}" y1="6" y2="${y(0)}" class="cp-guide"/></g>`;
      });
      const base = `<line x1="${g}" x2="${largeur - g}" y1="${y(0)}" y2="${y(0)}" class="cp-grille"/>`;
      return `<svg class="cp-svg" viewBox="0 0 ${largeur} ${H}" width="100%" role="group" aria-label="Annonces captées par jour et par plateforme, ${n} derniers jours">${base}${lignes}${points}${zones}${etiquettes}</svg>`;
    }
    // Total des annonces nouvelles par jour : une courbe, un point par jour, la valeur au-dessus quand la place le permet
    function svgTotal(jours, depuis, largeur) {
      // Échelle à gauche : le minimum et le maximum de la période, avec repères horizontaux
      const H = 130, gauche = 34, g = 8, b = 22, h = H - b - 16, n = jours.length, pas = (largeur - gauche - g) / n;
      const tot = jours.map((j) => SOURCES_CAPT.reduce((t, [src]) => t + (j.v[src] || 0), 0));
      const min = Math.min(...tot), max = Math.max(...tot, min + 1), saut = n <= 8 ? 1 : largeur < 420 ? 4 : 2;
      const px = (k) => gauche + k * pas + pas / 2, y = (v) => 16 + h - ((v - min) / (max - min)) * h;
      let svg = [min, max].map((v) => `<line x1="${gauche}" x2="${largeur - g}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" class="cp-grille"/><text x="${gauche - 5}" y="${(y(v) + 4).toFixed(1)}" class="cp-axe cp-echelle" text-anchor="end">${v}</text>`).join('');
      const pts = jours.map((j, k) => [px(k), y(tot[k])]), bas = 16 + h, haut = 16;
      const borne = (v) => Math.min(bas, Math.max(haut, v));
      const tangente = (k) => { const avant = pts[Math.max(k - 1, 0)], apres = pts[Math.min(k + 1, n - 1)]; return [(apres[0] - avant[0]) / 6, (apres[1] - avant[1]) / 6]; };
      for (let k = 1; k < n; k += 1) {
        const a = pts[k - 1], bb = pts[k], ta = tangente(k - 1), tb = tangente(k);
        const c1 = [a[0] + ta[0], borne(a[1] + ta[1])], c2 = [bb[0] - tb[0], borne(bb[1] - tb[1])];
        const estime = depuis && jours[k].cle < depuis;
        svg += `<path d="M${a[0].toFixed(1)},${a[1].toFixed(1)} C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${bb[0].toFixed(1)},${bb[1].toFixed(1)}" class="cp-total${estime ? ' cp-estime' : ''}${jours[k].enCours ? ' cp-encours' : ''}"/>`;
      }
      jours.forEach((j, k) => {
        const estime = depuis && j.cle < depuis;
        if (!estime) svg += `<circle cx="${px(k)}" cy="${y(tot[k])}" r="3" class="cp-total-pt${j.enCours ? ' cp-encours' : ''}"/>`;
        if (pas >= 20 && !estime) svg += `<text x="${px(k)}" y="${y(tot[k]) - 7}" class="cp-val" text-anchor="middle">${tot[k]}</text>`;
        if ((n - 1 - k) % saut === 0) svg += `<text x="${px(k)}" y="${H - 6}" class="cp-axe" text-anchor="middle">${jourCourtCapt(j.cle)}</text>`;
      });
      return `<svg class="cp-svg" viewBox="0 0 ${largeur} ${H}" width="100%" role="img" aria-label="Total des annonces nouvelles par jour, ${n} derniers jours, de ${min} à ${max}">${svg}</svg>`;
    }
    // Heure par heure (axe x = heure de Paris) : aujourd'hui, hier, et la moyenne des autres jours gardés
    const heureParis = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', hourCycle: 'h23', timeZone: 'Europe/Paris' });
    const jourParis = (t) => new Date(t).toLocaleDateString('sv-SE', { timeZone: 'Europe/Paris' });
    function courbesHoraires(heures, maintenant) {
      const par = {};
      Object.entries(heures || {}).forEach(([cle, n]) => {
        const t = Date.parse(cle + ':00:00Z'); if (Number.isNaN(t)) return;
        const j = jourParis(t), h = Number(heureParis.format(t));
        (par[j] = par[j] || Array(24).fill(null));
        par[j][h] = (par[j][h] ?? 0) + n;
      });
      const aujj = jourParis(maintenant), hier = jourParis(maintenant - 86400000);
      const aujourd = par[aujj] || Array(24).fill(null), veille = par[hier] || Array(24).fill(null);
      const autres = Object.keys(par).filter((j) => j !== aujj).map((j) => par[j]);
      const moyenne = Array.from({ length: 24 }, (_, h) => { const v = autres.map((x) => x[h]).filter((x) => x != null); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; });
      return { aujourd, veille, moyenne, heureCourante: Number(heureParis.format(maintenant)), nbAutres: autres.length };
    }
    function svgHoraire(c, largeur) {
      // Axe de 5 h à 23 h : la nuit, le bot ne tourne pas. Échelle à gauche, repères horizontaux.
      const debut = 5, n = 24 - debut, H = 150, gauche = 34, g = 8, b = 22, h = H - b - 16, pas = (largeur - gauche - g) / n;
      const px = (k) => gauche + k * pas + pas / 2;
      const tranche = (v) => v.slice(debut);
      const aujourd = tranche(c.aujourd), veille = tranche(c.veille), moyenne = tranche(c.moyenne), courante = c.heureCourante - debut;
      const toutes = [...aujourd, ...veille, ...moyenne].filter((v) => v != null);
      const max = Math.max(10, ...toutes), y = (v) => 16 + h - (v / max) * h;
      const ligne = (valeurs, cls) => {
        const pts = valeurs.map((v, k) => (v == null ? null : `${px(k).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean);
        return pts.length > 1 ? `<polyline points="${pts.join(' ')}" class="${cls}"/>` : '';
      };
      const echelle = [0, Math.round(max / 2), Math.round(max)];
      let svg = echelle.map((v) => `<line x1="${gauche}" x2="${largeur - g}" y1="${y(v)}" y2="${y(v)}" class="cp-grille"/><text x="${gauche - 5}" y="${y(v) + 4}" class="cp-axe cp-echelle" text-anchor="end">${v}</text>`).join('');
      svg += ligne(moyenne, 'cp-h cp-h-moy');
      svg += ligne(veille, 'cp-h cp-h-veille');
      svg += ligne(aujourd.map((v, k) => (k <= courante ? v : null)), 'cp-h cp-h-jour');
      aujourd.forEach((v, k) => { if (v != null && k <= courante) svg += `<circle cx="${px(k)}" cy="${y(v)}" r="3" class="cp-h-pt"/><text x="${px(k)}" y="${y(v) - 6}" class="cp-h-val" text-anchor="middle">${v}</text>`; });
      // Zones cliquables : chaque heure donne les chiffres sous le graphique
      for (let k = 0; k < n; k += 1) {
        const a = aujourd[k], v = veille[k], m = moyenne[k], ref = a ?? v ?? m;
        if (ref == null) continue;
        const txt = `${k + debut} h · aujourd'hui : ${a ?? '–'} · hier : ${v ?? '–'} · moyenne : ${m == null ? '–' : Math.round(m)}`;
        svg += `<circle cx="${px(k)}" cy="${y(ref)}" r="10" class="cp-h-hit" data-txt="${esc(txt)}" tabindex="0" role="button" aria-label="${esc(txt)}"/>`;
      }
      for (let k = debut; k < 24; k += 3) svg += `<text x="${px(k - debut)}" y="${H - 6}" class="cp-axe" text-anchor="middle">${k}h</text>`;
      return `<svg class="cp-svg" viewBox="0 0 ${largeur} ${H}" width="100%" role="img" aria-label="Annonces nouvelles heure par heure, de 5 h à 23 h : aujourd'hui, hier et la moyenne des jours précédents, échelle en nombre d'annonces">${svg}</svg>`;
    }
    const dessinerCaptures = () => {
      const zones = document.querySelectorAll('.captures-zone');
      const c = BUT && BUT.captures;
      if (!zones.length || !BUT) return;
      if (!estNiveau3()) { zones.forEach((z) => { z.innerHTML = ''; }); return; }
      if (!c || !c.jours) { zones.forEach((z) => { z.innerHTML = '<p class="sous">Annonces captées par jour : le premier comptage arrive au prochain relevé (dans l\'heure).</p>'; }); return; }
      const nbSrc = (v) => SOURCES_CAPT.reduce((t, [src]) => t + (v[src] || 0), 0);
      const cleJour = (k) => new Date(Date.now() - k * 86400000).toLocaleDateString('sv-SE', { timeZone: 'Europe/Paris' });
      // Du 25 octobre à hier (15 jours au plus) pour les moyennes ; le jour en cours s'ajoute au graphique et au tableau, sans entrer dans les moyennes
      const DEBUT_CAPT = '2026-10-25';
      const complets = [];
      for (let k = 15; k >= 1; k -= 1) { const cle = cleJour(k); if (cle >= DEBUT_CAPT) complets.push({ cle, v: c.jours[cle] || {} }); }
      const aujourdhui = c.jours[cleJour(0)] ? { cle: cleJour(0), v: c.jours[cleJour(0)], enCours: true } : null;          // sans comptage du jour : pas de point inventé
      const jours = aujourdhui ? complets.concat(aujourdhui) : complets, m = complets.length, moitie = Math.min(7, Math.floor(m / 2)), tendanceOk = m >= 6;
      const recents = complets.slice(m - moitie), avant = complets.slice(m - 2 * moitie, m - moitie);
      const somme = (liste, src) => liste.reduce((t, j) => t + (src ? (j.v[src] || 0) : nbSrc(j.v)), 0);
      const moy = (liste, src) => somme(liste, src) / liste.length;
      const fmt1 = (x) => (x >= 10 ? String(Math.round(x)) : x.toFixed(1).replace('.', ','));
      const evolution = (src) => { if (!tendanceOk) return null; const a = moy(recents, src), b = moy(avant, src); return b > 0 ? (a - b) / b : null; };
      const texteEvol = (p) => (p == null ? '–' : `${p > 0 ? '+' : p < 0 ? '−' : ''}${Math.abs(Math.round(p * 100))} %`);
      const verdictEvol = (p) => (p == null ? `disponible dans ${Math.max(6 - m, 1)} jour${6 - m > 1 ? 's' : ''}` : p >= 0.1 ? 'le marché accélère' : p <= -0.1 ? 'le marché ralentit' : 'le marché est stable');
      const pTotal = tendanceOk ? evolution(null) : null;
      // Source comptée seulement depuis un jour : la légende l'écrit, pour qu'un 0 ne paraisse pas une erreur
      const debutSource = (src) => {
        const premier = Object.keys(c.jours).filter((d) => (c.jours[d] || {})[src]).sort()[0];
        return premier && complets.length && premier > complets[0].cle ? ` <small class="cp-depuis">depuis le ${esc(jourCourtCapt(premier))}</small>` : '';
      };
      const estimes = c.depuis && jours.some((j) => j.cle < c.depuis);
      const depuis = c.depuis ? new Date(c.depuis + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' }) : '';
      const largeur = Math.max(300, Math.min(760, (document.documentElement.clientWidth || 360) - 56));
      const lignes = jours.slice().reverse().map((j, k) => {
        const quand = new Date(j.cle + 'T12:00:00').toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'numeric' }).replace('.', '') + (j.enCours ? ' (en cours)' : '');
        const total = nbSrc(j.v);
        return `<tr><th scope="row">${esc(quand)}</th>${SOURCES_CAPT.map(([src]) => `<td>${j.v[src] || '–'}</td>`).join('')}<td><b>${total || '–'}</b></td></tr>`;
      }).join('');
      const pied = `<tr><th scope="row">Total ${m} jours</th>${SOURCES_CAPT.map(([src]) => `<td>${somme(complets, src)}</td>`).join('')}<td><b>${somme(complets)}</b></td></tr>`
        + `<tr><th scope="row">Moyenne par jour</th>${SOURCES_CAPT.map(([src]) => `<td>${fmt1(moy(complets, src))}</td>`).join('')}<td><b>${fmt1(moy(complets))}</b></td></tr>`
        + `<tr><th scope="row">Évolution sur ${moitie} jours</th>${SOURCES_CAPT.map(([src]) => `<td>${texteEvol(evolution(src))}</td>`).join('')}<td><b>${texteEvol(pTotal)}</b></td></tr>`;
      const horaires = courbesHoraires(c.heures, Date.now());
      const html = `<section class="captures" aria-label="Annonces captées par jour">
        <h3 class="captures-titre">Annonces captées par jour</h3>
        <p class="cp-bilan"><b>${somme(complets)}</b> annonces en ${m} jours · <b>${fmt1(moy(complets))}</b> par jour en moyenne</p>
        <p class="cp-bilan cp-jour">${aujourdhui ? `Aujourd'hui, à cette heure : <b>${nbSrc(aujourdhui.v)}</b> annonce${nbSrc(aujourdhui.v) > 1 ? 's' : ''} <span class="sous">(jour en cours, non compté dans les moyennes)</span>` : `Aujourd'hui : <span class="sous">pas encore compté, le premier comptage arrive au prochain relevé.</span>`}</p>
        <ul class="cp-legende">${SOURCES_CAPT.map(([src, nom]) => `<li><span class="cp-pastille cp-${src}" aria-hidden="true"></span>${nom} <b>${somme(complets, src)}</b>${debutSource(src)}</li>`).join('')}</ul>
        <p class="cp-tendance">${pTotal == null ? `Tendance : ${verdictEvol(pTotal)}.` : `<b class="${pTotal >= 0.1 ? 'cp-hausse' : pTotal <= -0.1 ? 'cp-baisse' : ''}">${texteEvol(pTotal)}</b> : ${verdictEvol(pTotal)}.`}
          ${tendanceOk ? `<span class="sous">${moitie} derniers jours : ${fmt1(moy(recents))} par jour. ${moitie} jours d'avant : ${fmt1(moy(avant))} par jour.</span>` : ''}</p>
        <div class="cp-cadre">${svgCaptures(jours, c.depuis, largeur)}<div class="cp-bulle" hidden></div></div>
        <p class="sous">Annonces nouvelles, comptées le jour où elles apparaissent. ${aujourdhui ? " Le dernier point (pointillé, creux) est le jour en cours : il n'est pas fini." : ''}${estimes ? ` Comptage commencé le ${esc(depuis)} : les jours d'avant sont estimés (pointillés).` : ''}</p>${statsHtml()}
        <p class="sous cp-titre-total">Heure par heure (heure de Paris)</p>
        <p class="sous cp-legende-h"><span class="cp-h-l cp-h-jour"></span>aujourd'hui <span class="cp-h-l cp-h-veille"></span>hier <span class="cp-h-l cp-h-moy"></span>moyenne de ${horaires.nbAutres} jour${horaires.nbAutres > 1 ? 's' : ''} précédent${horaires.nbAutres > 1 ? 's' : ''}</p>
        <div class="cp-cadre">${svgHoraire(horaires, largeur)}</div>
        <p class="cp-info-h" aria-live="polite">Touchez un point pour voir les chiffres de l'heure.</p>
        <p class="sous cp-titre-total">Total des annonces par jour</p>
        <div class="cp-cadre">${svgTotal(jours, c.depuis, largeur)}</div>
        <details class="captures-acc"><summary>Tableau des chiffres</summary>
          <div class="captures-defile"><table class="captures-table"><caption class="sr-only">Nombre d'annonces nouvelles captées chaque jour, par plateforme</caption>
            <thead><tr><th scope="col">Jour</th>${SOURCES_CAPT.map(([, nom]) => `<th scope="col">${nom}</th>`).join('')}<th scope="col">Total</th></tr></thead><tbody>${lignes}</tbody><tfoot>${pied}</tfoot></table></div></details></section>`;
      zones.forEach((z) => {
        const ouvert = !!(z.querySelector('.captures-acc') || {}).open;
        z.innerHTML = html;
        const info = z.querySelector('.cp-info-h');
        z.querySelectorAll('.cp-h-hit').forEach((pt) => {
          const montre = () => { if (info) info.textContent = pt.dataset.txt; };
          pt.addEventListener('click', montre);
          pt.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); montre(); } });
        });
        if (ouvert) z.querySelector('.captures-acc').open = true;
        const cadre = z.querySelector('.cp-cadre'), bulle = z.querySelector('.cp-bulle');
        const montrer = (col) => {
          const k = Number(col.dataset.i), j = jours[k];
          bulle.innerHTML = `<b>${esc(j.enCours ? "Aujourd'hui (en cours)" : jourCourtCapt(j.cle))} · ${nbSrc(j.v)}</b>${SOURCES_CAPT.map(([src, nom]) => `<span><i class="cp-pastille cp-${src}"></i>${nom} ${j.v[src] || 0}</span>`).join('')}`;
          bulle.hidden = false;
          const r = col.getBoundingClientRect(), rc = cadre.getBoundingClientRect();
          bulle.style.left = `${Math.min(Math.max(r.left - rc.left + r.width / 2 - bulle.offsetWidth / 2, 0), rc.width - bulle.offsetWidth)}px`;
        };
        z.querySelectorAll('.cp-col').forEach((col) => {
          col.addEventListener('mouseenter', () => montrer(col));
          col.addEventListener('focus', () => montrer(col));
          col.addEventListener('click', () => montrer(col));
          col.addEventListener('mouseleave', () => { bulle.hidden = true; });
          col.addEventListener('blur', () => { bulle.hidden = true; });
        });
      });
    };
    redessinerCapt = dessinerCaptures;
    let largeurCapt = 0;
    window.addEventListener('resize', () => { const l = document.documentElement.clientWidth; if (Math.abs(l - largeurCapt) > 40) { largeurCapt = l; dessinerCaptures(); } });
    dessinerPepites = () => {
      dessinerCaptures();
      if (!BUT) { etat.textContent = butChargees ? "Pas encore d'annonces enregistrées : elles apparaîtront après le prochain relevé des prix." : 'Chargement…'; liste.innerHTML = ''; return; }
      if (etatARestaurer) {
        const o = etatARestaurer; etatARestaurer = null;
        if ([...tri.options].some((x) => x.value === o.tri)) tri.value = o.tri;
        solides.checked = !!o.sol; trouver.checked = !!o.tr; defilementEnAttente = o.y;
      }
      const sw = souhaits(), toutes = pepites().map((p) => Object.assign(p, { trouver: !!sw[p.ed.id] })).filter((p) => !trouver.checked || p.trouver), sures = toutes.filter((p) => !p.raisons.length), vues = ordonner(solides.checked ? sures : sures.concat(toutes.filter((p) => p.raisons.length)), tri.value);   // solides d'abord, puis à vérifier (chacun trié par économie)
      etat.textContent = `${toutes.length} bonne${toutes.length > 1 ? 's' : ''} affaire${toutes.length > 1 ? 's' : ''}, dont ${sures.length} sans point à vérifier. Dernier relevé eBay : ${jour(BUT.date_ebay || BUT.date)}.`;
      try { localStorage.setItem('cdh-butin-vu', String(Date.now())); } catch (e) { /* tant pis */ }          // les nouveautés comptées sur l'accueil repartent de zéro
      liste.innerHTML = vues.length ? '<div class="rayon pp-rayon">' + vues.map(cartePepite).join('') + '</div>' : '<p>Aucune bonne affaire pour ce filtre.</p>';
      const pane = document.getElementById('pane-pepites');
      if (defilementEnAttente != null && pane && !pane.hidden) { const y = defilementEnAttente; defilementEnAttente = null; requestAnimationFrame(() => window.scrollTo(0, y)); setTimeout(() => window.scrollTo(0, y), 400); }
    };
    // Pépite du jour : le Zagor choisit l'annonce offerte aux Héros (fichier public écrit par le service technique)
    liste.addEventListener('click', (e) => {
      const b = e.target.closest('[data-offrir]'); if (!b) return;
      // Le retour s'affiche sur la carte elle-même : la ligne d'état est en haut de la liste, hors de vue
      const dire = (texte) => { let r = b.parentElement.querySelector('.pp-retour'); if (!r) { r = document.createElement('p'); r.className = 'sous pp-retour'; r.setAttribute('role', 'status'); b.insertAdjacentElement('afterend', r); } r.textContent = texte; };
      const [id, cle, lien] = b.dataset.offrir.split('|'), p = pepites().find((x) => x.ed.id === id && x.cle === cle && x.lien === lien);
      if (!p) return dire('Annonce introuvable : rechargez la page.');
      if (!window.Relais) return dire("Échec : le service technique n'est pas chargé. Rechargez la page.");
      b.disabled = true; dire('Envoi de la pépite du jour…');
      const pct = Math.round((1 - p.prix / p.pub) * 100), ABR = { convenable: 'C', bon: 'BE', tres_bon: 'TBE' };
      window.Relais.appeler('pepite_offrir', { isbn13: p.ed.isbn, prix: p.prix, pub: p.pub, pct, etat: ABR[p.cle], origine: p.origine === 'leboncoin' ? 'leboncoin' : p.origine === 'vinted' ? 'vinted' : (p.origine === 'librairie' || REVENDEURS[p.origine]) ? 'librairie' : p.origine === 'titre' ? 'titre' : p.origine === 'isbn' ? 'isbn' : 'ebay', lien: p.lien, solide: !p.raisons.length })
        .then((r) => { dire(r && r.ok ? `✓ Offerte aux Héros aujourd'hui (visible d'ici quelques minutes).` : `Échec : ${(r && r.erreur) || 'réponse inattendue'}.`); })
        .catch(() => { dire('Échec : service injoignable. Vérifiez la connexion, puis réessayez.'); }).then(() => { b.disabled = false; });
    });
    solides.addEventListener('change', dessinerPepites);
    trouver.addEventListener('change', dessinerPepites);
    document.addEventListener('cdh-pane', (e) => { if (e.detail === 'pepites' && estNiveau2()) chargerButin().then(() => dessinerPepites()); });
    dessinerPepites();
  }

  let ouvrirOnglet = () => {};
  // Onglet « Annonces reçues » (niveau 3 seul, page Butin) : toutes les annonces des derniers relevés, la plus récemment vue en premier
  let dessinerRecues = () => {};
  function initRecues() {
    const rechercheRc = $('#rc-q');
    if (rechercheRc) rechercheRc.addEventListener('input', () => { limite = 60; dessinerRecues(); });
    const liste = $('#rc-liste'), etat = $('#rc-etat'), source = $('#rc-source'), enligne = $('#rc-enligne'), verdict = $('#rc-verdict'), trouverRc = $('#rc-trouver'), sansRc = $('#rc-sans'), triRc = $('#rc-tri');
    if (!liste) return;
    let limite = 60;
    const pepRc = $('#rc-pep'), bonRc = $('#rc-bon'), serieRc = $('#rc-serie'), editionRc = $('#rc-edition'), editeurRc = $('#rc-editeur'), etatfRc = $('#rc-etatf'), pminRc = $('#rc-pmin'), verifRc = $('#rc-verif'), aberrRc = $('#rc-aberr'), pmaxRc = $('#rc-pmax'), effacerRc = $('#rc-effacer'), nbPlus = $('#rc-nb-filtres');
    // Retour de la fiche : filtres, tri, longueur de liste et position sont gardés au clic, puis remis à la réouverture de la page
    const CTRL_RC = ['rc-q', 'rc-tri', 'rc-source', 'rc-verdict', 'rc-serie', 'rc-edition', 'rc-editeur', 'rc-etatf', 'rc-temp', 'rc-pmin', 'rc-pmax'], CASES_RC = ['rc-trouver', 'rc-pep', 'rc-bon', 'rc-sans', 'rc-verif', 'rc-enligne', 'rc-aberr'];
    let etatARestaurer = null, defilementEnAttente = null;
    try { const o = JSON.parse(sessionStorage.getItem('cdh-annonces-etat') || 'null'); if (o && Date.now() - o.t < 2 * 3600 * 1000) etatARestaurer = o; sessionStorage.removeItem('cdh-annonces-etat'); } catch (e) { /* sans stockage : retour à la liste de départ */ }
    const sauverEtatRc = () => {
      try {
        const o = { t: Date.now(), y: window.scrollY, lim: limite, per: periode, v: {}, c: {} };
        CTRL_RC.forEach((i) => { const e = document.getElementById(i); if (e) o.v[i] = e.value; });
        CASES_RC.forEach((i) => { const e = document.getElementById(i); if (e) o.c[i] = e.checked; });
        sessionStorage.setItem('cdh-annonces-etat', JSON.stringify(o)); sessionStorage.setItem('cdh-retour-fiche', 'butin.html#recues');
      } catch (e) { /* tant pis */ }
    };
    liste.addEventListener('click', (e) => { if (e.target.closest('a.an-jaq, a.an-titre, a.rc-fiche')) sauverEtatRc(); });
    const appliquerDefilement = () => {
      const pane = document.getElementById('pane-recues');
      if (defilementEnAttente == null || !pane || pane.hidden) return;
      const y = defilementEnAttente; defilementEnAttente = null;
      requestAnimationFrame(() => window.scrollTo(0, y)); setTimeout(() => window.scrollTo(0, y), 400);
    };
    const boutonsQuand = [...document.querySelectorAll('#rc-quand [data-quand]')], boutonsVue = [...document.querySelectorAll('#rc-vue [data-vue]')];
    let modeVue = 'grille', periode = 'tout';
    const accRc = $('#rc-acc'); if (accRc && window.matchMedia('(max-width: 600px)').matches) accRc.open = false;          // replié sur téléphone, ouvert sur ordinateur
    boutonsQuand.forEach((b) => b.addEventListener('click', () => { periode = b.dataset.quand; boutonsQuand.forEach((x) => x.setAttribute('aria-pressed', String(x === b))); limite = 60; dessinerRecues(); }));
    try { const m = localStorage.getItem('cdh-annonces-vue'); if (m === 'liste' || m === 'grille') modeVue = m; } catch (e) { /* sans stockage : jaquettes */ }
    boutonsVue.forEach((b) => { b.setAttribute('aria-pressed', String(b.dataset.vue === modeVue)); b.addEventListener('click', () => { modeVue = b.dataset.vue; boutonsVue.forEach((x) => x.setAttribute('aria-pressed', String(x === b))); try { localStorage.setItem('cdh-annonces-vue', modeVue); } catch (e) { /* tant pis */ } limite = 60; dessinerRecues(); }); });
    const famille = (o) => (o === 'leboncoin' ? 'leboncoin' : o === 'vinted' ? 'vinted' : o === 'librairie' ? 'librairie' : REVENDEURS[o] ? o : 'ebay');
    const NOM = { ebay: 'eBay', leboncoin: 'Leboncoin', vinted: 'Vinted', librairie: 'Librairie', ...REVENDEURS };
    // Position du prix de l'annonce par rapport au prix actuel du site (même état) : mêmes mots que le bot Leboncoin.
    // Pépite : la moitié du prix du site ou moins (règle du Butin) ; dans les prix : à 10 % près ; très cher : plus de 1,5 fois le prix du site.
    const VERDICTS = { super: ['🔥 Super pépite', 'rc-v-super'], pepite: ['Pépite', 'rc-v-pepite'], dessous: ['Pas cher', 'rc-v-dessous'], dans: ['Dans les prix', 'rc-v-dans'], dessus: ['Trop cher', 'rc-v-dessus'], cher: ['Très cher', 'rc-v-cher'] };
    const verdictDe = (prix, pub) => {
      if (pub == null) return null;
      if (prix <= 0.2 * pub && pub - prix >= ECONOMIE_MINI) return 'super';          // 20 % du prix du site ou moins
      if (prix <= SEUIL_PEPITE * pub && pub - prix >= ECONOMIE_MINI) return 'pepite';
      if (prix < 0.9 * pub) return 'dessous';
      if (prix <= 1.1 * pub) return 'dans';
      if (prix <= 1.5 * pub) return 'dessus';
      return 'cher';
    };
    const comparaison = (prix, pub, v, lot) => {
      if (pub == null) return '<span class="rc-vs">pas de prix sur le site</span>';
      const ecart = Math.round((prix / pub - 1) * 100);
      // Le moins cher / le plus cher du même livre et du même état, quand il y a plusieurs annonces (sinon le verdict habituel)
      const extremeBas = lot && prix === lot.min && v === 'dessous', extremeHaut = lot && prix === lot.max && (v === 'dessus' || v === 'cher');
      const libelle = extremeBas ? 'Le moins cher' : extremeHaut ? 'Le plus cher' : VERDICTS[v][0];
      return `<span class="rc-pastille ${VERDICTS[v][1]}">${libelle}</span><span class="rc-vs">site ${eur(pub)} · ${ecart > 0 ? '+' : ecart < 0 ? '−' : ''}${Math.abs(ecart)} %</span>`;
    };
    // Thermomètre : le rond est l'annonce, entre le moins cher et le plus cher du même livre et du même état ; le trait est le prix du site (même état).
    // L'échelle s'élargit au prix du site, pour que le trait reste dans la barre. Mêmes seuils que « Dans les prix » (10 % autour du prix du site).
    const thermometre = (a) => {
      if (!a.lot) return '';
      const site = a.pub != null;
      const bas = site ? Math.min(a.lot.min, a.pub) : a.lot.min, haut = site ? Math.max(a.lot.max, a.pub) : a.lot.max;
      const place = (x) => (haut > bas ? (x - bas) / (haut - bas) : 0);
      const rang = a.lot.max > a.lot.min ? (a.prix - a.lot.min) / (a.lot.max - a.lot.min) : 0;
      const extreme = rang <= 0.1 || rang >= 0.9;
      const cat = rang <= 0.1 ? 'Le moins cher' : rang >= 0.9 ? 'Le plus cher' : !site ? '' : a.prix < 0.9 * a.pub ? 'Sous le prix du site' : a.prix <= 1.1 * a.pub ? 'Au prix du site' : 'Au-dessus du prix du site';
      const txt = `${cat ? cat + ' : ' : ''}annonces de ${eur(a.lot.min)} à ${eur(a.lot.max)}, médiane ${eur(a.lot.med)}${site ? `. Le trait marque le prix du site, ${eur(a.pub)}` : ''}`;
      return `<span class="rc-therm" role="img" aria-label="${esc(txt)}" title="${esc(txt)}"><span class="rc-therm-piste">${site ? `<span class="rc-therm-rep" style="left:${(place(a.pub) * 100).toFixed(1)}%"></span>` : ''}<span class="rc-therm-pt" style="left:${(place(a.prix) * 100).toFixed(1)}%"></span></span>${extreme || !cat ? '' : `<span class="rc-therm-txt">${cat}</span>`}</span>`;
    };
    const exclueHtml = '<span class="an-exclu" title="Prix à 3 fois le très bon état ou plus : annonce affichée, mais écartée du calcul de la cote.">Exclue du pricing</span>';
    // Écart au prix du site : rouge au-dessus, vert en dessous
    const ecartHtml = (a) => {
      const e = Math.round((a.prix / a.pub - 1) * 100);
      return `<b class="an-ecart ${e > 0 ? 'an-ecart-plus' : e < 0 ? 'an-ecart-moins' : ''}">${e > 0 ? '+' : e < 0 ? '−' : ''}${Math.abs(e)}\u00a0%</b>`;
    };
    // Barre des prix : un trait par annonce du même livre et du même état, le point doré est celle-ci, le trait clair est le prix du site
    const barrePrix = (a) => {
      const p = a.tous || [a.prix], site = a.pub != null ? a.pub : null;
      const bas = Math.min(...p, site == null ? Infinity : site), haut = Math.max(...p, site == null ? -Infinity : site);
      const pos = (x) => (haut > bas ? ((x - bas) / (haut - bas)) * 100 : 50).toFixed(1);
      const txt = `${p.length} annonce${p.length > 1 ? 's' : ''} de ce livre dans le même état, de ${eur(Math.min(...p))} à ${eur(Math.max(...p))}. Cette annonce : ${eur(a.prix)}.${site != null ? ` Prix du site : ${eur(site)}.` : ''}`;
      return `<div class="an-barre" role="img" aria-label="${esc(txt)}" title="${esc(txt)}"><div class="an-barre-piste">${p.map((x) => `<i class="an-tick" style="left:${pos(x)}%"></i>`).join('')}${site != null ? `<i class="an-reperesite" style="left:${pos(site)}%"></i>` : ''}<i class="an-moi" style="left:${pos(a.prix)}%"></i></div><div class="an-barre-bornes"><span>${eur(bas)}</span><span>${eur(haut)}</span></div></div>`;
    };
    const jourCourt = (iso) => (iso ? new Date(iso + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }) : '');
    // Quand l'annonce est apparue : date et heure si l'heure est connue (« 29 oct. · 10:18 »), sinon le jour de la dernière observation
    // Ordres de tri : date et heure d'apparition (à défaut, dernier jour vu), série et numéro, prix, écart au prix du site, origine
    // Date de publication de l'annonce (donnée par le relevé : eBay, Leboncoin, Vinted) ; à défaut, le jour où le site l'a vue pour la première fois (donnée estimée)
    const jourParis = (d) => d.toLocaleDateString('sv-SE', { timeZone: 'Europe/Paris' });
    const ecartJours = (iso) => Math.round((Date.parse(jourParis(new Date()) + 'T12:00:00Z') - Date.parse(iso.slice(0, 10) + 'T12:00:00Z')) / 86400000);
    function fraicheurDe(a) {
      if (a.publiee) return { jours: Math.max(0, ecartJours(a.publiee)), estime: false };
      if (a.fam === 'vinted' && a.premiere) { const c = a.premiere; const j = c.length > 10 && !Number.isNaN(Date.parse(c)) ? jourParis(new Date(c)) : c.slice(0, 10); return { jours: Math.max(0, ecartJours(j)), estime: true }; }
      return { jours: null, estime: false };
    }
    const quandCle = (a) => (a.publiee || (a.premiere || a.vue || '').slice(0, 10)) + '|' + (a.premiere || '');
    const ageTexte = (a) => {
      if (a.ageJ == null) return 'date inconnue';
      const n = a.ageJ, base = a.ageEstime ? 'trouvée par le site' : 'publiée';
      if (n === 0) return `${base} aujourd'hui`;
      if (n === 1) return `${base} hier`;
      if (n < 60) return `${base} il y a ${n}\u00a0j`;
      return `${base} il y a ${Math.round(n / 30)}\u00a0mois`;
    };
    const ageClasse = (a) => (a.ageJ == null || a.ageEstime ? 'an-age-x' : a.ageJ <= 2 ? 'an-age-vert' : a.ageJ <= 14 ? 'an-age-neutre' : a.ageJ <= 30 ? 'an-age-moyen' : 'an-age-ancien');
    const ageHtml = (a) => `<span class="an-age ${ageClasse(a)}"${a.publiee ? ` title="Publiée le ${esc(new Date(a.publiee + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }))}"` : ''}>${esc(ageTexte(a))}</span>`;
    // Opportunités d'achat (Zagor, onglet Analyse) : annonces assez sous le prix du site pour être revendues avec une marge, frais déduits.
    // Marge nette = revente (part du prix du site) − frais de vente − prix d'achat livré. Revente sur Leboncoin : pas de frais de vente par défaut.
    const PARAMS_OPP_DEFAUT = { vente: 90, frais: 0 };
    let paramsOpp = { ...PARAMS_OPP_DEFAUT }, dernieresToutes = null, nbOppAffichees = 25, defilementOpp = null;
    try { const o = JSON.parse(localStorage.getItem('cdh-opp-params') || 'null'); if (o && o.vente > 0 && o.vente <= 150 && o.frais >= 0 && o.frais <= 50) paramsOpp = { vente: Number(o.vente), frais: Number(o.frais) }; } catch (e) { /* valeurs par défaut */ }
    try { const o = JSON.parse(sessionStorage.getItem('cdh-opp-etat') || 'null'); if (o && Date.now() - o.t < 2 * 3600 * 1000) { defilementOpp = o.y; nbOppAffichees = o.n || 25; } sessionStorage.removeItem('cdh-opp-etat'); } catch (e) { /* retour au début */ }
    // Fiabilité d'une opportunité : qualité de la donnée ET appui du marché. Une cote bien au-dessus de toutes les annonces, ou des annonces disparues (vendues ?) bien
    // moins chères, rendent la marge douteuse : ce n'est alors pas une affaire, c'est peut-être la cote qui est trop haute.
    const marcheOpp = (a, groupes) => {
      const memes = groupes.get(a.ed.isbn + '|' + a.cle) || [], mediane = (l) => { const t = l.slice().sort((x, y) => x - y), m = t.length >> 1; return t.length ? (t.length % 2 ? t[m] : (t[m - 1] + t[m]) / 2) : null; };
      const enLigne = memes.filter((x) => !x.partie && !x.aberrant), disparues = memes.filter((x) => x.partie && !x.aberrant);
      return { n: enLigne.length, bas: Math.min(...enLigne.map((x) => x.prix)), haut: Math.max(...enLigne.map((x) => x.prix)),
        proches: enLigne.filter((x) => x.lien !== a.lien && x.prix >= 0.7 * a.pub).length, disparues: disparues.map((x) => x.prix), medDisparues: mediane(disparues.map((x) => x.prix)) };
    };
    const fiabiliteOpp = (a, m) => {
      const cote = (a.ed.etats[a.cle] || {}).confiance;
      if (a.points.length) return { niveau: 'faible', raison: a.points.join(', ') };
      if (m.proches === 0) return { niveau: 'faible', raison: `Aucune autre annonce près du prix du site (${eur(a.pub)}) : la cote n'est pas confirmée par le marché.` };
      if (m.medDisparues != null && m.medDisparues < 0.6 * a.pub) return { niveau: 'faible', raison: `Les annonces disparues (vendues ?) étaient à ${eur(m.medDisparues)}, bien sous le prix du site.` };
      if (!['élevée', 'validée', 'moyenne'].includes(cote)) return { niveau: 'faible', raison: 'Cote peu fiable pour cette édition.' };
      return { niveau: ['élevée', 'validée'].includes(cote) && a.ageJ != null && !a.ageEstime && a.ageJ <= 30 ? 'haute' : 'moyenne', raison: '' };
    };
    const LIB_FIAB = { haute: 'Fiabilité haute', moyenne: 'Fiabilité moyenne', faible: 'À vérifier' };
    const POIDS_FIAB = { haute: 1, moyenne: 0.6, faible: 0.25 };
    function dessinerOpp(toutes) {
      const zone = document.getElementById('opp-zone');
      if (!zone || !estNiveau3()) return;
      if (toutes) dernieresToutes = toutes;
      if (!dernieresToutes) return;
      const vente = paramsOpp.vente / 100, frais = paramsOpp.frais;
      const groupes = new Map(); dernieresToutes.forEach((x) => { const k = x.ed.isbn + '|' + x.cle; if (!groupes.has(k)) groupes.set(k, []); groupes.get(k).push(x); });
      const liste = dernieresToutes.filter((a) => a.pub && !a.aberrant && !a.partie && a.fam !== 'librairie' && !/^Lot de /.test(a.titre || ''))
        .map((a) => { const marge = vente * a.pub - frais - a.prix, m = marcheOpp(a, groupes), f = fiabiliteOpp(a, m), fiab = f.niveau; return { a, marge, roi: marge / a.prix, fiab, raison: f.raison, m, score: marge * POIDS_FIAB[fiab] }; })
        .filter((o) => o.marge >= 5 && o.roi >= 0.25).sort((x, y) => y.score - x.score);
      const hautes = liste.filter((o) => o.fiab === 'haute').length;
      const cartes = liste.slice(0, nbOppAffichees).map((o) => {
        const a = o.a, fiche = `./#fiche=${encodeURIComponent(a.ed.id)}`, n = (a.tous || []).length;
        const num = a.ed.numero && !/^0+$/.test(a.ed.numero) ? ' n° ' + esc(a.ed.numero) : '';
        return `<article class="opp-carte opp-${o.fiab}">
          <div class="opp-tete"><a class="opp-titre" href="${fiche}">${esc(a.ed.titre)}</a>${vendueHtml(a)}<span class="opp-fiab opp-f-${o.fiab}" title="${o.fiab === 'faible' ? esc(o.raison) : o.fiab === 'moyenne' ? 'Cote correcte, mais date de publication inconnue ou ancienne' : 'Cote confirmée par le marché, état précisé, annonce publiée il y a 30 jours ou moins'}">${LIB_FIAB[o.fiab]}</span></div>
          <p class="opp-meta">${esc(a.ed.serie)}${num} · ${esc(a.ed.version)} · ${ABR_ETAT[a.cle]} · ${n} annonce${n > 1 ? 's' : ''} de ce livre dans cet état</p>
          <div class="opp-chiffres"><span>Achat <b>${eur(a.prix)}</b> <small>${esc(NOM[a.fam])}</small></span><span>Prix du site <b>${eur(a.pub)}</b></span><span class="opp-marge">Marge <b>+${eur(o.marge)}</b> <small>(+${Math.round(o.roi * 100)} %)</small></span></div>
          <p class="opp-marche">En ligne : ${o.m.n} annonce${o.m.n > 1 ? 's' : ''}${o.m.n > 1 ? ` de ${eur(o.m.bas)} à ${eur(o.m.haut)}` : ''}${o.m.disparues.length ? ` · disparues (vendues ?) : ${o.m.disparues.slice(0, 4).map((x) => eur(x)).join(', ')}` : ''}</p>
          ${o.raison ? `<p class="opp-raison">${esc(o.raison)}</p>` : ''}
          ${panneauCorrection(a)}
          <p class="opp-bas">${ageHtml(a)} · <a class="opp-lien" href="${esc(a.lien)}" target="_blank" rel="noopener noreferrer">Voir l'annonce ↗</a></p>
        </article>`;
      }).join('');
      zone.innerHTML = `<section class="opp" aria-label="Opportunités d'achat">
        <h3 class="captures-titre">Opportunités d'achat</h3>
        <p class="sous">Annonces assez sous le prix du site pour être revendues avec au moins 5 € de marge nette et 25 % de rendement. Triées par marge, la fiabilité compte : une marge énorme est souvent une erreur d'édition ou d'état.</p>
        <div class="opp-params"><label>Revente à <input type="number" id="opp-vente" min="10" max="150" step="1" value="${paramsOpp.vente}" inputmode="numeric"> % du prix du site</label><label>Frais de vente <input type="number" id="opp-frais" min="0" max="50" step="0.5" value="${paramsOpp.frais}" inputmode="decimal"> €</label></div>
        <p class="sous opp-bilan"><b>${liste.length}</b> opportunité${liste.length > 1 ? 's' : ''}, dont <b>${hautes}</b> de fiabilité haute${liste.length > nbOppAffichees ? ` · ${nbOppAffichees} affichées` : ''}. Prix demandés (pas des ventes) : la cote a ses marges d'erreur.</p>
        <div class="opp-liste">${cartes || '<p class="sous">Aucune opportunité avec ces hypothèses.</p>'}</div>
        ${liste.length > nbOppAffichees ? '<p><button type="button" class="bouton bouton-clair" id="opp-plus">Afficher plus</button></p>' : ''}
      </section>`;
      const pane = document.getElementById('pane-analyse');
      if (defilementOpp != null && pane && !pane.hidden) { const y = defilementOpp; defilementOpp = null; requestAnimationFrame(() => window.scrollTo(0, y)); setTimeout(() => window.scrollTo(0, y), 400); }
    }
    document.addEventListener('input', (e) => {
      if (e.target.id !== 'opp-vente' && e.target.id !== 'opp-frais') return;
      const v = Number(document.getElementById('opp-vente').value), f = Number(document.getElementById('opp-frais').value);
      if (!(v > 0 && v <= 150 && f >= 0 && f <= 50)) return;
      paramsOpp = { vente: v, frais: f };
      try { localStorage.setItem('cdh-opp-params', JSON.stringify(paramsOpp)); } catch (er) { /* tant pis */ }
      const actif = document.activeElement && document.activeElement.id; nbOppAffichees = 25; dessinerOpp();
      const el = actif && document.getElementById(actif); if (el) { el.focus(); try { el.setSelectionRange(el.value.length, el.value.length); } catch (er) { /* type nombre */ } }
    });
    document.addEventListener('click', (e) => {
      if (e.target.id === 'opp-plus') { nbOppAffichees += 25; dessinerOpp(); return; }
      if (e.target.closest('a.opp-titre')) {
        try { sessionStorage.setItem('cdh-opp-etat', JSON.stringify({ t: Date.now(), y: window.scrollY, n: nbOppAffichees })); sessionStorage.setItem('cdh-retour-fiche', 'butin.html#analyse'); } catch (er) { /* tant pis */ }
      }
    });
    const dansPeriode = (a) => {
      if (periode === 'tout') return true;
      if (a.ageJ == null) return false;
      return periode === 'auj' ? a.ageJ === 0 : a.ageJ <= 6;
    };
    const parRecent = (a, b) => quandCle(b).localeCompare(quandCle(a)) || a.prix - b.prix;
    const numeroDe = (a) => parseInt(a.ed.numero, 10) || 0;
    const distance = (a, b) => {          // distance de Levenshtein, pour les fautes de frappe
      let ligne = Array.from({ length: b.length + 1 }, (_, i) => i);
      for (let i = 1; i <= a.length; i += 1) {
        const suite = [i];
        for (let j = 1; j <= b.length; j += 1) suite[j] = Math.min(ligne[j] + 1, suite[j - 1] + 1, ligne[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        ligne = suite;
      }
      return ligne[b.length];
    };
    const comparerRc = (mode) => ({
      recent: parRecent,
      ancien: (a, b) => quandCle(a).localeCompare(quandCle(b)) || a.prix - b.prix,
      prixdesc: (a, b) => b.prix - a.prix || parRecent(a, b),
      eco: (a, b) => (b.pub ? b.pub - b.prix : -9999) - (a.pub ? a.pub - a.prix : -9999) || parRecent(a, b),
      editeur: (a, b) => ((INFO_ED[a.ed.id] || {}).editeur || '').localeCompare((INFO_ED[b.ed.id] || {}).editeur || '', 'fr') || parRecent(a, b),
      serie: (a, b) => (a.ed.serie || '').localeCompare(b.ed.serie || '', 'fr') || numeroDe(a) - numeroDe(b) || (a.ed.version || '').localeCompare(b.ed.version || '') || parRecent(a, b),
      prix: (a, b) => a.prix - b.prix || parRecent(a, b),
      ecart: (a, b) => (a.pub ? a.prix / a.pub : 99) - (b.pub ? b.prix / b.pub : 99) || parRecent(a, b),
      origine: (a, b) => a.fam.localeCompare(b.fam) || parRecent(a, b),
    }[mode] || parRecent);
    dessinerRecues = () => {
      if (!ANN) { etat.textContent = annChargees ? "Pas encore d'annonces enregistrées : elles apparaîtront après le prochain relevé des prix." : 'Chargement…'; liste.innerHTML = ''; return; }
      const parIsbn = new Map(); EDITIONS.forEach((ed) => { if (ed.isbn && !parIsbn.has(ed.isbn)) parIsbn.set(ed.isbn, ed); });
      const dateRef = (o) => (enLigne(o) ? null : ANN.date_ebay);
      const toutes = [], sw = souhaits();
      Object.keys(ANN.annonces).forEach((isbn) => {
        const ed = parIsbn.get(isbn); if (!ed) return;
        ETATS.forEach(([cle, lib]) => (ANN.annonces[isbn][cle] || []).forEach(([prix, titre, lien, origine, vue, suppose, nu]) => {
          const partie = !!(vue && dateRef(origine) && vue < dateRef(origine));
          const pub = ed.etats[cle] && ed.etats[cle].publie, butin = !!pub && prix <= SEUIL_PEPITE * pub && pub - prix >= ECONOMIE_MINI && !partie;
          toutes.push({ ed, trouver: !!sw[ed.id], lib, cle, prix, nuAff: nu != null ? nu : prix, pub, v: verdictDe(prix, pub), titre, lien, fam: famille(origine), vue, partie, butin, points: pointsAVerifier(origine, suppose), premiere: (ANN.premieres && ANN.premieres[lien]) || '', publiee: (ANN.publiees && ANN.publiees[lien]) || '' });
          // une librairie n'est pas une annonce de particulier : sa cote suit sa propre règle
          { const z = toutes[toutes.length - 1]; const tbe = ed.etats.tres_bon && ed.etats.tres_bon.publie; z.aberrant = z.fam !== 'librairie' && !!tbe && prix >= SEUIL_ABERRANT * tbe; const f = fraicheurDe(z); z.ageJ = f.jours; z.ageEstime = f.estime; z.nouveau = f.jours != null && !f.estime && f.jours <= 2; }
        }));
      });
      TOUTES_RC = toutes.filter((a) => !a.aberrant); TOUTES_RC.nbAberrantes = toutes.length - TOUTES_RC.length; redessinerCapt();
      // Position de chaque annonce parmi les annonces du même livre et du même état : le moins cher, la médiane, le plus cher
      const parLivre = new Map();
      toutes.forEach((a) => { const k = a.ed.isbn + '|' + a.cle; if (!parLivre.has(k)) parLivre.set(k, []); parLivre.get(k).push(a.prix); });
      toutes.forEach((a) => {
        const p = parLivre.get(a.ed.isbn + '|' + a.cle).slice().sort((x, y) => x - y);
        if (p.length < 2) return;
        const m = p.length >> 1, med = p.length % 2 ? p[m] : (p[m - 1] + p[m]) / 2;
        a.lot = { min: p[0], max: p[p.length - 1], med: med, n: p.length };
      });
      toutes.forEach((a) => { a.tous = parLivre.get(a.ed.isbn + '|' + a.cle).slice().sort((x, y) => x - y); });
      dessinerOpp(toutes);
      // Listes de filtres (série, édition, éditeur) : les valeurs présentes dans les annonces, remplies une fois
      const remplir = (el, valeurs, tous) => { if (!el || el.options.length > 1) return; el.innerHTML = `<option value="">${tous}</option>` + valeurs.map((v) => `<option>${esc(v)}</option>`).join(''); };
      const uniques = (f) => [...new Set(toutes.map(f).filter(Boolean))].sort((x, y) => String(x).localeCompare(String(y), 'fr', { numeric: true }));
      remplir(serieRc, uniques((a) => a.ed.serie), 'Toutes'); remplir(editionRc, uniques((a) => a.ed.version), 'Toutes'); remplir(editeurRc, uniques((a) => (INFO_ED[a.ed.id] || {}).editeur), 'Tous');
      if (etatARestaurer) {
        const o = etatARestaurer; etatARestaurer = null;
        CTRL_RC.forEach((i) => { const e = document.getElementById(i); if (e && o.v[i] != null) e.value = o.v[i]; });
        CASES_RC.forEach((i) => { const e = document.getElementById(i); if (e && o.c[i] != null) e.checked = o.c[i]; });
        periode = o.per || 'tout'; boutonsQuand.forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.quand === periode)));
        limite = o.lim || 60; defilementEnAttente = o.y;
      }
      // Recherche tolérante : chaque mot doit se trouver dans le titre, la série ou l'édition (sans accents ni majuscules),
      // ou à une lettre près pour les mots de 4 lettres et plus (« sorcir » trouve « sorcier »)
      const mots = norm(rechercheRc ? rechercheRc.value : '').split(/\s+/).filter(Boolean);
      const proche = (mot, texte) => texte.includes(mot) || (mot.length >= 4 && texte.split(/[^a-z0-9]+/).some((x) => distance(mot, x) <= 1 && Math.abs(x.length - mot.length) <= 1));
      const vues = toutes.filter((a) => (!mots.length || mots.every((m) => proche(m, norm(`${a.ed.titre} ${a.ed.serie} ${a.ed.version} ${a.titre}`)))) && (source.value === 'tout' || a.fam === source.value) && (verdict.value === 'tout' || a.v === verdict.value || (verdict.value === 'pepite' && a.v === 'super')) && (!trouverRc.checked || a.trouver) && (!sansRc || !sansRc.checked || !a.points.length) && (!verifRc || !verifRc.checked || a.points.length > 0) && dansPeriode(a) && !(enligne.checked && a.partie) && !(aberrRc && aberrRc.checked && a.aberrant)
        && (!pepRc || !pepRc.checked || a.v === 'pepite' || a.v === 'super') && (!bonRc || !bonRc.checked || ['dessous', 'pepite', 'super'].includes(a.v))
        && (!serieRc || !serieRc.value || a.ed.serie === serieRc.value) && (!editionRc || !editionRc.value || a.ed.version === editionRc.value)
        && (!editeurRc || !editeurRc.value || (INFO_ED[a.ed.id] || {}).editeur === editeurRc.value) && (!etatfRc || !etatfRc.value || a.cle === etatfRc.value)
        && (!pminRc || pminRc.value === '' || a.prix >= Number(pminRc.value)) && (!pmaxRc || pmaxRc.value === '' || a.prix <= Number(pmaxRc.value)))
        .sort(comparerRc(triRc ? triRc.value : 'recent'));
      const nbTr = $('#rc-nb-trouver'); if (nbTr) { const nt = toutes.filter((a) => a.trouver && !a.partie).length; nbTr.textContent = nt ? `(${nt})` : ''; }
      const dansPlus = [source.value !== 'tout', verdict.value !== 'tout', serieRc && serieRc.value, editionRc && editionRc.value, editeurRc && editeurRc.value, etatfRc && etatfRc.value, pminRc && pminRc.value !== '', pmaxRc && pmaxRc.value !== ''].filter(Boolean).length;
      const actifs = dansPlus + [aberrRc && aberrRc.checked, verifRc && verifRc.checked, periode !== 'tout', trouverRc.checked, pepRc && pepRc.checked, bonRc && bonRc.checked, sansRc && sansRc.checked].filter(Boolean).length;
      if (nbPlus) nbPlus.textContent = actifs ? `(${actifs} actif${actifs > 1 ? 's' : ''})` : '';
      if (effacerRc) effacerRc.hidden = !(dansPlus || (aberrRc && aberrRc.checked) || (verifRc && verifRc.checked) || periode !== 'tout' || trouverRc.checked || (pepRc && pepRc.checked) || (bonRc && bonRc.checked) || (sansRc && sansRc.checked));
      const nbAbs = toutes.filter((a) => a.aberrant).length;
      const lbl = $('#rc-aberr-nb'); if (lbl) lbl.textContent = nbAbs ? `(${nbAbs})` : '';
      etat.textContent = `${vues.length} annonce${vues.length > 1 ? 's' : ''} sur ${toutes.length}${nbAbs ? (aberrRc && aberrRc.checked ? ` (${nbAbs} masquées : prix à 3 fois le très bon état ou plus)` : `, dont ${nbAbs} exclue${nbAbs > 1 ? 's' : ''} de la cote (prix à 3 fois le très bon état ou plus)`) : ''}. Dernier relevé eBay : ${jour(ANN.date_ebay || ANN.date)}.`;
      const carteListe = (a) => {
        const corr = panneauCorrection(a, true);
        return `<article class="rc-ligne${a.butin ? ' rc-butin' : ''}">
        <a class="rc-titre" href="${esc(a.lien)}" target="_blank" rel="noopener noreferrer">${esc(a.ed.titre)}<span class="sr-only"> : ouvrir l'annonce (nouvel onglet)</span></a>
        <b class="rc-prix">${eur(a.nuAff)}</b>
        <span class="rc-ligne2">${a.nouveau ? '<span class="an-new an-new-ligne">Nouveau</span>' : ''}${a.aberrant ? exclueHtml : ''}${vendueHtml(a)}${ageHtml(a)}${a.trouver ?'<span class="pp-trouver rc-trouver">★ À trouver</span>' : ''}${comparaison(a.prix, a.pub, a.v, a.lot)}${thermometre(a)}<span class="rc-src">${NOM[a.fam]}</span><span class="rc-meta">${esc(a.ed.serie)} ${esc(a.ed.version)} · ${ABR_ETAT[a.cle]}${a.partie ? ' · plus vue' : ''}</span><span class="rc-actions">${corr ? '<button type="button" class="corr-bouton" aria-expanded="false">Corriger</button>' : ''}<a class="rc-fiche" href="./#fiche=${encodeURIComponent(a.ed.id)}" aria-label="Ouvrir la fiche du livre : ${esc(a.ed.titre)}">Fiche ↗</a></span></span>
        ${corr}
      </article>`;
      };
      const carteGrille = (a) => {
        const info = INFO_ED[a.ed.id] || {}, fiche = `./#fiche=${encodeURIComponent(a.ed.id)}`;
        const initiale = esc((a.ed.serie || a.ed.titre || '?').trim().charAt(0).toUpperCase());
        const image = info.mini ? `<img src="${esc(info.mini)}" alt="" width="320" height="523" loading="lazy" decoding="async">` : `<span class="an-jaq-vide" aria-hidden="true">${initiale}</span>`;
        return `<article class="an-carte${a.butin ? ' rc-butin' : ''}">
          <a class="an-jaq" href="${fiche}" aria-label="Ouvrir la fiche du livre : ${esc(a.ed.titre)}">${image}${vendueHtml(a) ? '<span class="an-pancarte">Vendu</span>' : ''}${a.trouver ? '<span class="an-trouver" title="À trouver">★</span>' : ''}</a>
          <div class="an-verdict">${a.nouveau ? '<span class="an-new">Nouveau</span>' : ''}${a.aberrant ? exclueHtml : ''}${a.pub == null ? '<span class="rc-vs">Pas de prix du site</span>' : `<span class="rc-pastille ${VERDICTS[a.v][1]}">${VERDICTS[a.v][0]}</span>`}</div>
          <div class="an-prixlien"><b class="rc-prix">${eur(a.nuAff)}</b><a class="an-lien" href="${esc(a.lien)}" target="_blank" rel="noopener noreferrer">Voir l'annonce ↗<span class="sr-only"> (nouvel onglet) : ${esc(a.ed.titre)}</span></a></div>
          <a class="an-titre" href="${fiche}">${esc(a.ed.titre)}</a>
          <span class="an-serie">${esc(a.ed.serie)}${a.ed.numero ? ' n° ' + esc(a.ed.numero) : ''}${a.ed.version ? ' · ' + esc(a.ed.version) : ''}</span>
          ${a.pub != null ? `<span class="an-site">site ${eur(a.pub)} · ${ecartHtml(a)}</span>` : ''}
          ${barrePrix(a)}
          <span class="an-meta">${ABR_ETAT[a.cle]} · ${NOM[a.fam]} · ${ageHtml(a)}${a.partie ? ' · plus vue' : ''}</span>
          ${panneauCorrection(a)}
        </article>`;
      };
      const page = vues.slice(0, limite);
      liste.innerHTML = (modeVue === 'grille' ? '<div class="an-grille">' + page.map(carteGrille).join('') + '</div>' : '<div class="rc-liste">' + page.map(carteListe).join('') + '</div>') + (vues.length > limite ? '<p><button type="button" class="bouton bouton-clair" id="rc-plus">Afficher plus</button></p>' : '');
      appliquerDefilement();
    };
    liste.addEventListener('click', (e) => {
      const corr = e.target.closest && e.target.closest('.corr-bouton');
      if (corr) { const d = corr.closest('article').querySelector(':scope > .corr-lite'); if (d) { d.open = !d.open; corr.setAttribute('aria-expanded', String(d.open)); } return; }
      if (e.target.id === 'rc-plus') { limite += 60; dessinerRecues(); }
    });
    source.addEventListener('change', () => { limite = 60; dessinerRecues(); });
    enligne.addEventListener('change', () => { limite = 60; dessinerRecues(); });
    verdict.addEventListener('change', () => { limite = 60; dessinerRecues(); });
    if (triRc) triRc.addEventListener('change', () => { limite = 60; dessinerRecues(); });
    trouverRc.addEventListener('change', () => { limite = 60; dessinerRecues(); });
    if (sansRc) sansRc.addEventListener('change', () => { limite = 60; dessinerRecues(); });
    [pepRc, bonRc, serieRc, editionRc, editeurRc, etatfRc, aberrRc].forEach((el) => { if (el) el.addEventListener('change', () => { limite = 60; dessinerRecues(); }); });
    [pminRc, pmaxRc].forEach((el) => { if (el) el.addEventListener('input', () => { limite = 60; dessinerRecues(); }); });
    const razFiltres = () => {
      [trouverRc, pepRc, bonRc, sansRc, verifRc].forEach((el) => { if (el) el.checked = false; });
      if (aberrRc) aberrRc.checked = false;
      source.value = 'tout'; verdict.value = 'tout';
      [serieRc, editionRc, editeurRc, etatfRc, pminRc, pmaxRc].forEach((el) => { if (el) el.value = ''; });
      if (rechercheRc) rechercheRc.value = '';
      periode = 'tout'; boutonsQuand.forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.quand === 'tout')));
      triRc.value = 'recent';
      limite = 60;
    };
    if (effacerRc) effacerRc.addEventListener('click', () => { razFiltres(); dessinerRecues(); });
    // Préréglages : chaque bouton remet tout à zéro puis règle les filtres d'un usage
    const PRESETS = {
      chasse: ['pépites sans réserve, les meilleures affaires d\'abord.', () => { pepRc.checked = true; sansRc.checked = true; triRc.value = 'ecart'; }],
      veille: ['annonces arrivées aujourd\'hui, les plus récentes d\'abord.', () => { periode = 'auj'; boutonsQuand.forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.quand === 'auj'))); triRc.value = 'recent'; }],
      comparaison: ['classées par prix croissant. Tapez un titre pour comparer les annonces d\'un même livre.', () => { triRc.value = 'prix'; }],
      verification: ['annonces dont l\'édition ou l\'état reste à confirmer, les meilleures affaires d\'abord.', () => { verifRc.checked = true; triRc.value = 'ecart'; }],
    };
    const txtPreset = $('#rc-preset-txt');
    document.querySelectorAll('#rc-presets [data-preset]').forEach((b) => b.addEventListener('click', () => {
      const p = PRESETS[b.dataset.preset]; if (!p) return;
      razFiltres(); p[1]();
      if (b.dataset.preset === 'comparaison') { modeVue = 'grille'; boutonsVue.forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.vue === 'grille'))); }
      if (txtPreset) { txtPreset.textContent = `${b.textContent} : ${p[0]}`; txtPreset.hidden = false; }
      dessinerRecues();
      if (b.dataset.preset === 'comparaison' && rechercheRc) rechercheRc.focus();
    }));
    // « Sans réserve » et « À vérifier » s'excluent
    if (sansRc && verifRc) { sansRc.addEventListener('change', () => { if (sansRc.checked) verifRc.checked = false; }); verifRc.addEventListener('change', () => { if (verifRc.checked) sansRc.checked = false; limite = 60; dessinerRecues(); }); }
    document.addEventListener('cdh-pane', (e) => { if (e.detail === 'recues' && estNiveau2()) chargerAnnonces().then(() => { dessinerRecues(); appliquerDefilement(); }); });
    dessinerRecues();
  }
  // Indice de marché : sur toutes les pages qui ont l'onglet Indice (pas seulement celles qui ont Annonces reçues)
  function initIndice() {
      // Indice de marché (Zagor seulement) : lu par le relais, affiché en tableau court
      let INDICE = null, indiceCharge = null;
      const chargerIndice = () => indiceCharge || (indiceCharge = window.Relais.appeler('indice_lire', {}).then((r) => { INDICE = r && r.ok ? r.indice : null; return INDICE; }).catch(() => null));
      // Indice de marché : une ligne par édition, les plus fortes baisses d'abord. Pas de liste de livres : elle n'apporte rien au groupe.
      const virgule = (x, n) => x.toFixed(n).replace('.', ',');
      const nb = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`;
      // « N annonces » : un lien vers leurs annonces pour le niveau 3 (les annonces ne sont lues que par lui), un simple texte sinon
      const lienAnnonces = (n, groupe, serie) => (n > 0 && estNiveau3() ? `<button type="button" class="ind-lien" data-ind-annonces="${esc(groupe)}" data-serie="${esc(serie || '')}">${nb(n, 'annonce')}</button>` : nb(n, 'annonce'));

      // Mini-courbe de l'indice (historique quotidien), sans bibliothèque : une ligne SVG
      const mini = (serie) => {
        if (!serie || serie.length < 2) return '';
        const v = serie.map((p) => p[1]), min = Math.min(...v), max = Math.max(...v), w = 80, h = 24;
        const y = (x) => (max === min ? h / 2 : h - 2 - ((x - min) / (max - min)) * (h - 4));
        const pts = v.map((x, i) => `${(i * w / (v.length - 1)).toFixed(1)},${y(x).toFixed(1)}`).join(' ');
        return `<svg class="ind-mini" viewBox="0 0 ${w} ${h}" aria-hidden="true" preserveAspectRatio="none"><polyline points="${pts}"/></svg>`;
      };
      const dessinerIndice = () => {
        const etat = document.getElementById('ind-etat'), liste = document.getElementById('ind-liste');
        if (!etat || !liste) return;
        if (!INDICE) { etat.textContent = 'Indice indisponible pour le moment.'; liste.innerHTML = ''; return; }
        const lignes = Object.entries(INDICE.groupes || {}).map(([cle, g]) => {
          const i = cle.indexOf(' · ');
          const ecart = Math.round((g.indice - 100) * 10) / 10;
          const sens = ecart < 0 ? 'baisse' : ecart > 0 ? 'hausse' : 'stable';
          return { cle, edition: cle.slice(0, i), editeur: cle.slice(i + 3), ecart, sens, g };
        }).sort((x, y) => x.ecart - y.ecart || y.g.livres - x.g.livres);
        const compte = (s) => lignes.filter((l) => l.sens === s).length;
        etat.textContent = `Au ${jour(INDICE.date)} : ${nb(compte('baisse'), 'édition')} en baisse, ${nb(compte('hausse'), 'édition')} en hausse, ${nb(compte('stable'), 'édition')} stable${compte('stable') > 1 ? 's' : ''}.`;
        const fleche = { baisse: '↓', hausse: '↑', stable: '→' };
      // Barre centrée sur 100 : à gauche une baisse, à droite une hausse. L'échelle est celle de la plus forte variation.
      const max = Math.max(1, ...lignes.map((l) => Math.abs(l.ecart)));
      const cartes = ['baisse', 'stable', 'hausse'].map((k) => `<div class="ind-carte ${k}"><b>${compte(k)}</b><span>${k === 'baisse' ? 'en baisse' : k === 'hausse' ? 'en hausse' : 'stables'}</span></div>`).join('');
      // Par éditeur d'abord (le plus de livres en premier), puis les éditions de l'éditeur (plus fortes baisses d'abord)
      const indiceEditeur = (nom) => { const x = (INDICE.editeurs || {})[nom]; if (!x) return ''; const ecart = Math.round((x.indice - 100) * 10) / 10; return `<b>${virgule(x.indice, 1)}</b> <span class="ind-var ${ecart < 0 ? 'baisse' : ecart > 0 ? 'hausse' : 'stable'}">${ecart === 0 ? 'stable' : (ecart < 0 ? '↓' : '↑') + ' ' + virgule(Math.abs(ecart), 1) + ' %'}</span> ${mini(x.historique)}`; };
      const parEditeur = {};
      lignes.forEach((l) => { (parEditeur[l.editeur] = parEditeur[l.editeur] || []).push(l); });
      const editeurs = Object.entries(parEditeur).map(([nom, ed]) => ({ nom, ed, livres: ed.reduce((t, l) => t + l.g.livres, 0) })).sort((x, y) => y.livres - x.livres);
      // Une ligne par édition qui bouge. Les éditions stables sont repliées en bas : elles ne disent rien de plus.
      // Cascade (waterfall) : chaque série fait monter ou descendre la variation du jour, de 0 au total
      // Détail par série, façon « roll-forward » : indice de départ (100), indice d'arrivée et variation, série par série, depuis le début de la mesure
      const cascadeHtml = (c, groupe) => {
        if (!c || !c.series || !c.series.length) return '<p class="ind-vide">Aucun détail disponible.</p>';
        const signe = (v) => (v < 0 ? 'baisse' : v > 0 ? 'hausse' : 'stable');
        const pct = (v) => `${v > 0 ? '+' : v < 0 ? '−' : ''}${virgule(Math.abs(v), 1)} %`;
        const ligneRf = (nom, meta, debut, fin, variation, classe) => `<li class="ind-rf-ligne ${classe || ''}"><span class="ind-rf-nom">${esc(nom)}${meta ? ` <span class="ind-meta">${meta}</span>` : ''}</span><span class="ind-rf-n">${virgule(debut, 1)}</span><span class="ind-rf-n">${virgule(fin, 1)}</span><b class="ind-var ${signe(variation)}">${pct(variation)}</b></li>`;
        const lignes = c.series.map((x) => ligneRf(x.serie, `${nb(x.livres, 'livre')} · ${x.autres ? nb(x.annonces || 0, 'annonce') : lienAnnonces(x.annonces || 0, groupe, x.serie)}`, x.debut, x.fin, x.variation_pct)).join('');
        return `<p class="ind-wf-total">Depuis le ${jour(c.depuis)}, sur ${nb(c.prix_observes, 'prix observé')}</p><ul class="ind-rf"><li class="ind-rf-ligne ind-rf-tete"><span class="ind-rf-nom">Série</span><span class="ind-rf-n">Début</span><span class="ind-rf-n">Fin</span><span class="ind-rf-n">Variation</span></li>${lignes}${ligneRf('Ensemble de l\'édition', '', c.debut, c.fin, c.variation_pct, 'ind-rf-total')}</ul>`;
      };
      const ligne = (l) => {
        const variation = l.sens === 'stable' ? 'stable' : `${virgule(Math.abs(l.ecart), 1)} %`;
        const detail = cascadeHtml((INDICE.cascade || {})[l.cle], l.cle);
        return `<article class="ind-ligne ${l.sens}"><div class="ind-haut"><span class="ind-titre">${esc(l.edition)}</span><span class="ind-chiffre"><b class="ind-val">${virgule(l.g.indice, 1)}</b><span class="ind-chip ${l.sens}">${fleche[l.sens]} ${variation}</span></span></div><div class="ind-bas">${mini(l.g.historique)}<span class="ind-meta">${nb(l.g.livres, 'livre')} · ${lienAnnonces(l.g.annonces, l.cle)}</span></div>${l.sens === 'stable' ? '' : `<details class="ind-detail"><summary>Détail par série</summary>${detail}</details>`}</article>`;
      };
      const bouge = lignes.filter((l) => l.sens !== 'stable');
      const stables = lignes.filter((l) => l.sens === 'stable');
      const parEditeurBouge = {};
      bouge.forEach((l) => { (parEditeurBouge[l.editeur] = parEditeurBouge[l.editeur] || []).push(l); });
      const editeursBouge = Object.entries(parEditeurBouge).map(([nom, ed]) => ({ nom, ed, livres: ed.reduce((t, l) => t + l.g.livres, 0) })).sort((x, y) => y.livres - x.livres);
      // Une maison (Gallimard) regroupe ses imprints (Gallimard, Gallimard Jeunesse) : l'indice de la maison d'abord, puis chaque imprint
      const FAM = (n) => (n === 'Gallimard Jeunesse' ? 'Gallimard' : n);
      const indiceFamille = (fam) => { const x = (INDICE.familles || {})[fam]; if (!x) return ''; const ecart = Math.round((x.indice - 100) * 10) / 10; return `<b>${virgule(x.indice, 1)}</b> <span class="ind-var ${ecart < 0 ? 'baisse' : ecart > 0 ? 'hausse' : 'stable'}">${ecart === 0 ? 'stable' : (ecart < 0 ? '↓' : '↑') + ' ' + virgule(Math.abs(ecart), 1) + ' %'}</span> ${mini(x.historique)}`; };
      const familles = {};
      editeursBouge.forEach((e) => { (familles[FAM(e.nom)] = familles[FAM(e.nom)] || []).push(e); });
      const blocsBouge = Object.entries(familles).map(([fam, imprints]) => {
        if (imprints.length === 1) {
          const e = imprints[0], ed = e.ed.slice().sort((x, y) => x.ecart - y.ecart || y.g.livres - x.g.livres);
          return `<section class="ind-editeur"><h3 class="ind-ed-titre">${esc(e.nom)}</h3><div class="ind-ed-indice">${indiceEditeur(e.nom)}</div><div class="ind-liste">${ed.map(ligne).join('')}</div></section>`;
        }
        // Une seule maison : toutes ses éditions dans une même liste. Le nom de l'imprint suit le numéro de version (V4 existe chez les deux).
        const tout = imprints.flatMap((e) => e.ed.map((l) => ({ ...l, edition: `${l.edition} · ${l.editeur === 'Gallimard Jeunesse' ? 'Jeunesse' : 'Gallimard'}` })));
        tout.sort((x, y) => x.ecart - y.ecart || y.g.livres - x.g.livres);
        return `<section class="ind-famille"><h2 class="ind-fam-titre">${esc(fam)}</h2><div class="ind-ed-indice">${indiceFamille(fam)}</div><div class="ind-liste">${tout.map(ligne).join('')}</div></section>`;
      }).join('');
      const parEditeurStable = {};
      stables.forEach((l) => { (parEditeurStable[l.editeur] = parEditeurStable[l.editeur] || []).push(l.edition); });
      const listeStables = Object.entries(parEditeurStable).map(([nom, eds]) => `<p class="ind-stables-ed"><b>${esc(nom)}</b> : ${eds.map(esc).join(', ')}</p>`).join('');
      const vide = bouge.length ? '' : '<p class="ind-vide">Aucune édition ne bouge pour l\'instant.</p>';
      liste.innerHTML = `<div class="ind-cartes">${cartes}</div>${vide}${blocsBouge}` +
        (stables.length ? `<details class="ind-stables"><summary>${nb(stables.length, 'édition')} stable${stables.length > 1 ? 's' : ''} (indice 100)</summary>${listeStables}</details>` : '');
    };
    document.addEventListener('cdh-pane', (e) => { if (e.detail === 'indice' && estNiveau3()) chargerIndice().then(dessinerIndice); });
  }

  function initNav() {
    const boutons = [...document.querySelectorAll('#rv-nav [data-pane]')];
    const montrer = (nom) => {
      boutons.forEach((b) => { b.setAttribute('aria-selected', String(b.dataset.pane === nom)); b.tabIndex = b.dataset.pane === nom ? 0 : -1; });
      document.querySelectorAll('.rv-pane').forEach((p) => { p.hidden = p.id !== 'pane-' + nom; });
      document.dispatchEvent(new CustomEvent('cdh-pane', { detail: nom }));
      try { sessionStorage.setItem('cdh-rv-pane', nom); } catch (e) { /* sans stockage : la page s'ouvre sur les prix */ }
    };
    ouvrirOnglet = (nom) => { const b = boutons.find((x) => x.dataset.pane === nom); if (b && !b.hidden) montrer(nom); };
    boutons.forEach((b) => {                              // motif des onglets : liés à leur panneau, flèches pour passer de l'un à l'autre
      b.id = 'onglet-rv-' + b.dataset.pane; b.setAttribute('aria-controls', 'pane-' + b.dataset.pane);
      const pan = document.getElementById('pane-' + b.dataset.pane);
      if (pan) pan.setAttribute('aria-labelledby', b.id);
      b.addEventListener('click', () => montrer(b.dataset.pane));
      b.addEventListener('keydown', (e) => {
        const visibles = boutons.filter((x) => !x.hidden), i = visibles.indexOf(b);
        const cible = { ArrowRight: visibles[(i + 1) % visibles.length], ArrowLeft: visibles[(i - 1 + visibles.length) % visibles.length], Home: visibles[0], End: visibles[visibles.length - 1] }[e.key];
        if (cible) { e.preventDefault(); cible.focus(); montrer(cible.dataset.pane); }
      });
    });
    [['tendances', '#rv-tendances']].forEach(([nom, sel]) => {
      const bloc = $(sel), onglet = boutons.find((b) => b.dataset.pane === nom);
      if (!bloc || !onglet) return;
      const maj = () => { onglet.hidden = bloc.hidden; if (bloc.hidden && onglet.getAttribute('aria-selected') === 'true') montrer('prix'); };
      new MutationObserver(maj).observe(bloc, { attributes: true, attributeFilter: ['hidden'] });
      maj();
    });
    let debut = (location.hash || '').slice(1);
    try { debut = debut || sessionStorage.getItem('cdh-rv-pane') || ''; } catch (e) { /* idem */ }
    if (boutons.some((b) => b.dataset.pane === debut) && !(boutons.find((b) => b.dataset.pane === debut) || {}).hidden) montrer(debut);
  }
  initAnnonces();
  initPepites();
  initRecues();
  initIndice();
  initNav();
  // Annonces : lien et onglet réservés au niveau 3 (le rôle arrive après la connexion)
  let pepitesOuvertes = false, recuesOuvertes = false, analyseOuverte = false;
  function majAnnonces() {
    const super_ = estNiveau3(), niveau2 = estNiveau2();
    const replier = (onglet) => { if (onglet && onglet.getAttribute('aria-selected') === 'true') { const prix = document.querySelector('#rv-nav [data-pane="prix"]') || document.querySelector('#rv-nav [data-pane="pepites"]'); if (prix) prix.click(); } };
    const onglet = document.querySelector('#rv-nav [data-pane="annonces"]');
    if (onglet) { onglet.hidden = !super_; if (!super_) replier(onglet); }
    const indice = document.querySelector('#rv-nav [data-pane="indice"]');
    if (indice) { indice.hidden = !super_; if (!super_) replier(indice); }
    const analyse = document.querySelector('#rv-nav [data-pane="analyse"]');
    if (analyse) { analyse.hidden = !super_; if (!super_) replier(analyse); }
    const recues = document.querySelector('#rv-nav [data-pane="recues"]');
    if (recues) { recues.hidden = !niveau2; if (!niveau2) { const pep = document.querySelector('#rv-nav [data-pane="pepites"]'); if (recues.getAttribute('aria-selected') === 'true' && pep) pep.click(); } }
    const pep = document.querySelector('#rv-nav [data-pane="pepites"]');
    if (pep) {
      pep.hidden = !niveau2;
      if (!niveau2 && pep.getAttribute('aria-selected') === 'true') { const prix = document.querySelector('#rv-nav [data-pane="prix"]'); if (prix) prix.click(); }
    }
    if (niveau2 && (location.hash || '') === '#recues' && !recuesOuvertes) { recuesOuvertes = true; ouvrirOnglet('recues'); }          // lien de l'accueil
    const ancre = location.hash || '';
    if (super_ && (ancre === '#analyse' || ancre === '#captures-recues') && !analyseOuverte) { analyseOuverte = true; ouvrirOnglet('analyse'); }          // ancien lien « annonces captées par jour »
    else if (niveau2 && ancre === '#captures-recues' && !recuesOuvertes) { recuesOuvertes = true; ouvrirOnglet('recues'); }
    if (niveau2 && (location.hash || '') === '#pepites' && !pepitesOuvertes) { pepitesOuvertes = true; ouvrirOnglet('pepites'); }   // lien direct du menu du compte : le rôle arrive après le chargement
    if (niveau2) chargerButin().then(() => dessinerPepites());
    if (niveau2) chargerAnnonces().then(() => { if (ANN && EDITIONS.length) afficher(); dessinerRecues(); });
    else if (EDITIONS.length) afficher();
  }
  document.addEventListener('cdh-compte', majAnnonces);
  majAnnonces();


  // La barre d'onglets reste visible sous l'en-tête collant : on lui donne la hauteur réelle de l'en-tête
  const calerOnglets = () => { const h = document.querySelector('.haut'); if (h) document.documentElement.style.setProperty('--haut-h', Math.max(0, Math.round(h.getBoundingClientRect().bottom)) + 'px'); };   // le bas de l'en-tête change quand le bandeau se replie au défilement
  calerOnglets(); addEventListener('resize', calerOnglets); addEventListener('load', calerOnglets); addEventListener('scroll', calerOnglets, { passive: true });

  const JAQ = {}, RAR = {}, EDITEUR = {};
  fetch('data/historique.json').then((r) => (r.ok ? r.json() : null)).catch(() => null).then((h) => { HISTO = h; const d = document.getElementById('rv-date'); if (d && h && h.dates.length) d.textContent = `Dernière publication des prix : ${jour(h.dates[h.dates.length - 1])}.`; if (EDITIONS.length) afficher(); });
  fetch('data/versions.json').then((r) => r.json()).then((v) => v.forEach((b) => { INFO_ED[b.id] = { livre: b.livre_id, isbn: b.isbn13 || '', version: b.version || '', mini: b.couverture || b.couverture_mini || '', editeur: (b.editeur || '').trim(), annee: b.annee || '', rarete: (b.rarete || {}).niveau || '' }; if (b.couverture) JAQ[b.id] = b.couverture; if (b.rarete) RAR[b.id] = b.rarete; EDITEUR[b.id] = (b.editeur || '').trim(); })).catch(() => {})
    .then(() => fetch('data/revue.json')).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then((d) => {
    const par = new Map();
    d.forEach((l) => { if (!par.has(l.id)) par.set(l.id, { id: l.id, isbn: l.isbn, titre: l.titre, serie: l.serie, numero: l.numero, version: l.version, etats: {} }); par.get(l.id).etats[l.etat] = l; });
    EDITIONS = [...par.values()];
    // Une validation déjà reprise dans les données du site n'a plus besoin d'être transmise
    EDITIONS.forEach((ed) => ETATS.forEach(([cle]) => { const l = ed.etats[cle], k = cleDe(ed, cle); if (l && l.valide && LOC[k] && LOC[k].prix === l.publie) delete LOC[k]; }));
    sauver();
    $('#rv-serie').innerHTML = '<option value="">Toutes les séries</option>' + [...new Set(EDITIONS.map((e) => e.serie))].sort((a, b) => a.localeCompare(b, 'fr')).map((s) => `<option>${esc(s)}</option>`).join('');
    document.querySelectorAll('#rv-onglets button').forEach((b) => b.addEventListener('click', () => { vue = b.dataset.vue; limite = PAGE; afficher(); }));
    ['#rv-q', '#rv-serie', '#rv-fiab'].forEach((s) => $(s).addEventListener('input', () => { limite = PAGE; afficher(); }));
    $('#rv-plus').addEventListener('click', () => { limite += PAGE; afficher(); });
    $('#rv-csv').addEventListener('click', csv);
    $('#rv-envoyer').addEventListener('click', envoyer);
    afficher();
    dessinerPepites();                                     // les annonces peuvent arriver avant les éditions : on redessine les pépites quand elles sont là
  }).catch(() => { $('#rv-liste').innerHTML = '<p class="erreur">Les données n\'ont pas pu être chargées.</p>'; });
})();
