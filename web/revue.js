/* Vérifier les prix : un livre par ligne, ses trois prix, l'ancien prix barré quand il a changé (outil du propriétaire). */
(() => {
  'use strict';
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
  try { LOC = JSON.parse(localStorage.getItem(CLE_LOC) || '{}') || {}; } catch (e) { LOC = {}; }
  const sauver = () => { try { localStorage.setItem(CLE_LOC, JSON.stringify(LOC)); } catch (e) { /* navigateur sans stockage : la validation reste valable tant que la page est ouverte */ } };
  const cleDe = (ed, cle) => `${ed.isbn}|${cle}`;
  const aujourdhui = () => new Date().toISOString().slice(0, 10);
  // Nom de la personne connectée avec Google (affichage seulement) ; le nom enregistré est celui que le lot vérifie (pipeline/identite.py)
  const nomAdmin = () => (window.Cloud ? window.Cloud.nom() : '');
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
  const prixAffiche = (ed, cle) => { const p = projection(ed)[cle], l = ed.etats[cle]; return p != null ? p : (l ? l.publie : null); };

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
      return n ? `d'après ${n} annonce${n > 1 ? 's' : ''} eBay` : "d'après les annonces eBay";
    }
    return l.publie == null ? '' : 'ancienne cote';
  }

  function boutons(ed, cle, v, l) {
    const id = `data-ed="${esc(ed.id)}" data-e="${cle}"`;
    return `<div class="rv-actions">` +
      `<button type="button" class="rv-b" data-act="corriger" ${id}>${l && l.publie != null || v ? 'Corriger' : 'Saisir un prix'}</button>` +
      (v && v.enAttente ? `<button type="button" class="rv-b rv-retirer" data-act="retirer" ${id}>Retirer</button>` : '') + `</div>` +
      `<form class="rv-form" data-ed="${esc(ed.id)}" data-e="${cle}" hidden><label>Prix en euros <input type="text" inputmode="decimal" pattern="[0-9]{1,4}([.,][0-9]{1,2})?" title="Un prix en euros, par exemple 24,50" required autocomplete="off" value="${String(v ? v.prix : (l && l.publie != null ? l.publie : '')).replace('.', ',')}"></label>` +
      `<button type="submit" class="rv-b rv-ok">Enregistrer</button><button type="button" class="rv-b" data-act="annuler">Annuler</button></form>`;
  }

  function cellule([cle, lib], ed) {
    const l = ed.etats[cle], v = validation(ed, cle);
    if (!l || l.publie == null) {
      if (!v) return `<div class="rv-prix vide"><span class="rv-lib">${lib}</span><strong>—</strong><span class="rv-note">pas de prix</span>${boutons(ed, cle, null, l)}</div>`;
    }
    if (v) {
      const calc = v.calcule != null && Math.abs(v.calcule - v.prix) > 0.005 ? `<span class="rv-avant">le site calculait <s>${eur(v.calcule)}</s></span>` : '';
      const quand = v.enAttente ? `Validé ${v.decision === 'confirme' ? '(confirmé)' : '(corrigé)'} ${jour(v.le)}${v.par ? ', par ' + v.par : ''} : à transmettre` : `Validé ${v.decision === 'confirme' ? '(confirmé)' : '(corrigé)'} le ${jour(v.le)}${v.par ? ', par ' + v.par : ''}`;
      return `<div class="rv-prix valide"><span class="rv-lib">${lib}</span><strong>${eur(v.prix)}</strong>${calc}<span class="rv-note rv-quand">✓ ${esc(quand)}</span>${boutons(ed, cle, v, l)}</div>`;
    }
    const proj = projection(ed)[cle];
    if (proj != null) {                                                 // recalculé d'après les prix que vous venez de saisir
      const site = l && l.publie != null && Math.abs(l.publie - proj) > 0.005 ? `<span class="rv-avant">le site affiche <s>${eur(l.publie)}</s></span>` : '';
      return `<div class="rv-prix"><span class="rv-lib">${lib}</span><strong>${eur(proj)}</strong>${site}<span class="rv-note">recalculé d'après vos prix saisis (à transmettre)</span>${boutons(ed, cle, null, l)}</div>`;
    }
    const r = ratio(l), alerte = raison(l, null);
    const avant = modifie(l) ? `<span class="rv-avant">avant <s>${eur(l.archive)}</s> · <b>${pct(r)}</b></span>` : '';
    const notes = [origine(l), l.lib_prix ? `1 exemplaire en librairie : ${eur(l.lib_prix)}` : '', l.ajuste ? 'ajusté pour garder C ≤ BE ≤ TBE' : ''].filter(Boolean).join(' · ');
    return `<div class="rv-prix${modifie(l) ? (r > 1 ? ' hausse' : ' baisse') : ''}${alerte ? ' alerte' : ''}"><span class="rv-lib">${lib}</span>` +
      `<strong>${eur(l.publie)}</strong>${avant}${alerte ? `<span class="rv-raison">À vérifier : ${alerte}</span>` : ''}<span class="rv-note">${esc(notes)}</span>${boutons(ed, cle, null, l)}</div>`;
  }

  // Dernière révision d'une édition : la validation la plus récente de l'un de ses états (y compris celles pas encore transmises)
  function derniereRevision(ed) {
    let best = null;
    ETATS.forEach(([cle]) => { const v = validation(ed, cle); if (v && v.le && (!best || v.le >= best.le)) best = v; });
    return best ? `<span class="rv-revision"${best.par ? ` title="Par ${esc(best.par)}"` : ''}>Révisée <strong>${esc(quand(best.le))}</strong></span>` : '<span class="rv-revision rien">Pas encore révisée</span>';
  }

  function carte(ed) {
    const jaq = JAQ[ed.id] ? `<img class="rv-jaq" src="${esc(JAQ[ed.id])}" alt="Jaquette de ${esc(ed.titre)}" width="56" height="80" loading="lazy" decoding="async">` : '';
    const attend = ETATS.some(([cle]) => { const l = ed.etats[cle]; return l && l.publie != null && !validation(ed, cle); });
    return `<article class="rv-edition"><header class="rv-tete">${jaq}<div class="rv-titre"><a href="./#q=${encodeURIComponent(ed.isbn || ed.id)}">${esc(ed.titre)}</a>` +
      `<span class="sous">${esc(ed.serie)}${ed.numero && !/^0+$/.test(ed.numero) ? ' n° ' + esc(ed.numero) : ''} · <span class="badge">${esc(ed.version)}</span>${RAR[ed.id] && /rare$/.test(RAR[ed.id].niveau) ? ` · <span class="rarete rarete-${RAR[ed.id].niveau}" title="Possédé par ${RAR[ed.id].pct} % des collections">${{ tres_rare: 'très rare', rare: 'rare', peu_courant: 'peu courant', courant: 'courant' }[RAR[ed.id].niveau]}</span>` : ''}</span>${derniereRevision(ed)}` +
      `<a class="rv-fiche" href="./#fiche=${encodeURIComponent(ed.id)}&corriger=1" target="_blank" rel="noopener">Corriger la fiche (titre, série…)</a>${aDesAnnonces(ed) ? `<button type="button" class="bouton-lien rv-voir-ann" data-annonces="${esc(ed.id)}">Voir les annonces</button>` : ''}</div></header>` +
      `<div class="rv-trois">${ETATS.map((e) => cellule(e, ed)).join('')}</div>` +
      `<div class="rv-bas">${attend ? `<button type="button" class="rv-b rv-ok rv-tout" data-act="tout-ok" data-ed="${esc(ed.id)}">Confirmer ces prix</button>` : '<span class="rv-tout-ok">✓ Prix validés</span>'}` +
      `<details class="rv-det"><summary>Saisir une fourchette</summary>` +
      `<form class="rv-fourchette" data-ed="${esc(ed.id)}"><span>De</span><input type="text" inputmode="decimal" name="mini" aria-label="Prix le plus bas observé, en euros" placeholder="€" autocomplete="off">` +
      `<span>à</span><input type="text" inputmode="decimal" name="maxi" aria-label="Prix le plus haut observé, en euros" placeholder="€" autocomplete="off"><button type="submit" class="rv-b rv-ok">Enregistrer</button>` +
      `<span class="rv-aide-fourchette">bas = convenable, haut = très bon état, bon état déduit</span></form></details>` +
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
  const force = (ed) => Math.max(0, ...lignes(ed).map((l) => { const r = ratio(l); return r ? Math.abs(Math.log(r)) : 0; }));

  function afficher() {
    const q = norm($('#rv-q').value).trim(), serie = $('#rv-serie').value;
    const base = EDITIONS.filter((ed) => (!q || norm(ed.titre + ' ' + ed.serie).includes(q)) && (!serie || ed.serie === serie));
    $('#rv-n-verif').textContent = base.filter(aVerifier).length;
    $('#rv-n-change').textContent = base.filter(aChange).length;
    $('#rv-n-tous').textContent = base.length;
    $('#rv-n-valide').textContent = base.filter(aValide).length;
    VUE = vue === 'verif' ? base.filter(aVerifier).sort((a, b) => force(b) - force(a))
      : vue === 'change' ? base.filter(aChange).sort((a, b) => force(b) - force(a))
      : vue === 'valide' ? base.filter(aValide).sort((a, b) => a.serie.localeCompare(b.serie, 'fr') || (parseInt(a.numero, 10) || 0) - (parseInt(b.numero, 10) || 0))
      : base.slice().sort((a, b) => a.serie.localeCompare(b.serie, 'fr') || (parseInt(a.numero, 10) || 0) - (parseInt(b.numero, 10) || 0) || a.version.localeCompare(b.version));
    $('#rv-compte').textContent = `${VUE.length} livre${VUE.length > 1 ? 's' : ''}` + (vue === 'verif' ? ' dont un prix a beaucoup bougé, du plus fort changement au plus faible.' : vue === 'change' ? ' dont au moins un prix a changé.' : vue === 'valide' ? ' dont au moins un prix est validé.' : '.');
    const nbAttente = Object.keys(LOC).length;
    $('#rv-envoi').hidden = !nbAttente;
    $('#rv-n-attente').textContent = nbAttente;
    $('#rv-envoyer').textContent = 'Envoyer mes validations';
    $('#rv-liste').innerHTML = VUE.length ? VUE.slice(0, limite).map(carte).join('') : '<p>Aucun livre dans cette liste.</p>';
    $('#rv-plus').hidden = VUE.length <= limite;
    document.querySelectorAll('#rv-onglets button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.vue === vue)));
  }

  function toutConfirmerListe() {
    const eds = VUE.filter((ed) => ETATS.some(([cle]) => { const l = ed.etats[cle]; return l && l.publie != null && !validation(ed, cle); }));
    const nb = eds.reduce((t, ed) => t + ETATS.filter(([cle]) => { const l = ed.etats[cle]; return l && l.publie != null && !validation(ed, cle); }).length, 0);
    if (!nb) { window.alert('Tous les prix de cette liste sont déjà validés.'); return; }
    if (!window.confirm(`Confirmer ${nb} prix de ${eds.length} livre${eds.length > 1 ? 's' : ''} tels qu'ils sont affichés, sans les regarder un par un ?`)) return;
    eds.forEach(confirmerEdition); sauver(); afficher();
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

  function enregistrer(edId, cle, prix, decision) {
    const ed = EDITIONS.find((x) => x.id === edId);
    if (!ed || !(prix > 0 && prix < 10000)) return;
    LOC[cleDe(ed, cle)] = { prix: Math.round(prix * 100) / 100, decision, le: aujourdhui(), ...(nomAdmin() ? { par: nomAdmin() } : {}) };
    sauver(); afficher();
  }

  // Confirmer d'un coup les prix affichés d'une édition (ceux qui ne sont pas déjà validés)
  function confirmerEdition(ed) {
    let n = 0;
    ETATS.forEach(([cle]) => {
      const l = ed.etats[cle], aff = prixAffiche(ed, cle);
      if (l && aff != null && !validation(ed, cle)) { LOC[cleDe(ed, cle)] = { prix: Math.round(aff * 100) / 100, decision: 'confirme', le: aujourdhui(), ...(nomAdmin() ? { par: nomAdmin() } : {}) }; n++; }
    });
    return n;
  }

  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-act]');
    if (!b) return;
    const edId = b.dataset.ed, cle = b.dataset.e, cell = b.closest('.rv-prix');
    if (b.dataset.act === 'tout-ok') {
      const ed = EDITIONS.find((x) => x.id === edId);
      if (ed && confirmerEdition(ed)) { sauver(); afficher(); }
      return;
    }
    if (b.dataset.act === 'ok') {
      const ed = EDITIONS.find((x) => x.id === edId), l = ed && ed.etats[cle];
      if (l && l.publie != null) enregistrer(edId, cle, l.publie, 'confirme');
    } else if (b.dataset.act === 'corriger') {
      const f = cell.querySelector('.rv-form'); f.hidden = false; cell.querySelector('.rv-actions').hidden = true; cell.classList.add('ouvert');
      const champ = f.querySelector('input'); champ.focus(); champ.select();
    } else if (b.dataset.act === 'annuler') {
      cell.querySelector('.rv-form').hidden = true; cell.querySelector('.rv-actions').hidden = false; cell.classList.remove('ouvert');
    } else if (b.dataset.act === 'retirer') {
      const ed = EDITIONS.find((x) => x.id === edId);
      if (ed) { delete LOC[cleDe(ed, cle)]; sauver(); afficher(); }
    }
  });
  document.addEventListener('submit', (e) => {
    const f = e.target.closest('.rv-form');
    if (!f) return;
    e.preventDefault();
    const prix = parseFloat(String(f.querySelector('input').value).replace(',', '.'));
    if (prix > 0 && prix < 10000) enregistrer(f.dataset.ed, f.dataset.e, prix, 'corrige');
  });

  document.addEventListener('submit', (e) => {
    const f = e.target.closest('.rv-fourchette');
    if (!f) return;
    e.preventDefault();
    const nb = (x) => parseFloat(String(x).replace(',', '.'));
    const mini = f.elements.mini.value.trim(), maxi = f.elements.maxi.value.trim();
    if (!mini && !maxi) return;
    if ([mini, maxi].some((x) => x && !(nb(x) > 0 && nb(x) < 10000)) || (mini && maxi && nb(mini) > nb(maxi))) { f.classList.add('erreur'); return; }
    if (mini && maxi) { enregistrer(f.dataset.ed, 'convenable', nb(mini), 'corrige'); enregistrer(f.dataset.ed, 'tres_bon', nb(maxi), 'corrige'); }
    else enregistrer(f.dataset.ed, 'tres_bon', nb(mini || maxi), 'corrige');          // un seul prix : très bon état
  });

  // Fichier à transmettre : mêmes validations, dans le format lu par pipeline/validations.py
  async function envoyer() {
    const msg = $('#rv-envoi-msg'), dire = (t) => { msg.textContent = t; msg.hidden = false; };
    if (!jeton()) return dire('Votre connexion a expiré : reconnectez-vous avec le bouton du compte, en haut de la page. Vos validations sont gardées.');
    const par = {};
    Object.entries(LOC).forEach(([cle, v]) => { const [isbn, etat] = cle.split('|'), k = `${isbn}|${v.decision}`; (par[k] = par[k] || {})[etat] = v.prix; });
    const lignes = Object.entries(par).map(([k, p]) => `${k.split('|')[0]} ; ${p.convenable ?? ''} ; ${p.bon ?? ''} ; ${p.tres_bon ?? ''}${k.endsWith('|confirme') ? ' ; confirme' : ''}`);
    $('#rv-envoyer').disabled = true; dire('Envoi en cours…');
    try {
      const r = await lancer('corriger-prix.yml', { corrections: lignes.join(' | ') });
      dire(r.status === 204 ? `Envoyé (${lignes.length} livre${lignes.length > 1 ? 's' : ''}). Le site sera à jour dans environ 2 minutes ; ces validations disparaîtront de la liste « à transmettre » dès qu'elles y seront.`
        : r.status === 401 || r.status === 403 ? MSG_REFUS : `Échec de l'envoi : ${r.erreur || 'code ' + r.status}.`);
    } catch (err) { dire('Envoi impossible : vérifiez votre connexion.'); }
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
  function initAjout() {
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

  // Les envois passent par le relais (connexion Google du site, voir relais.js) : aucune clé GitHub sur l'appareil.
  // « jeton() » dit seulement si l'envoi en un clic est possible maintenant : relais en service et connexion encore valable.
  const jeton = () => (window.Relais && window.Relais.actif() ? 'relais' : null);
  const lancer = (lot, inputs) => window.Relais.envoyerLot(lot, (({ identite, ...reste }) => reste)(inputs));
  const MSG_REFUS = 'Ce compte n\'a pas les droits d\'administrateur, ou la connexion Google a expiré : reconnectez-vous avec le bouton du compte, en haut de la page.';
  function etatJeton() {
    $('#aj-lancer').hidden = !jeton() || !AJOUT.some((a) => a.statut === 'nouveau');
  }
  function initReglages() {
    $('#aj-lancer').addEventListener('click', async () => {
      const msg = $('#aj-msg'), dire = (t) => { msg.textContent = t; msg.hidden = false; };
      if (!jeton()) return dire('Votre connexion a expiré : reconnectez-vous avec le bouton du compte, en haut de la page.');
      $('#aj-lancer').disabled = true; dire('Envoi en cours…');
      try {
        const r = await lancer('ajout-isbn.yml', { liste: texteAjout().replace(/\n/g, ' | '), releve: 'oui' });
        dire(r.status === 204 ? 'Envoyé. Les livres seront sur le site dans environ 2 minutes, les prix après le relevé qui suit.'
          : r.status === 401 || r.status === 403 ? MSG_REFUS : `Échec de l'envoi : ${r.erreur || 'code ' + r.status}.`);
      } catch (e) { dire('Envoi impossible : vérifiez votre connexion.'); }
      $('#aj-lancer').disabled = false;
    });
    etatJeton();
  }
  initAjout();
  initReglages();

  /* ---------- Demandes d'ajout faites par les personnes connectées (via le relais) ---------- */
  function initDemandes() {
    if (!window.Relais) return;
    window.Identite.config().then((c) => { if (c && c.relais_url) brancherDemandes(); });
  }
  function brancherDemandes() {
    const bloc = $('#rv-demandes'), liste = $('#dm-liste'), msg = $('#dm-msg');
    const dire = (t, erreur) => { msg.textContent = t; msg.hidden = false; msg.classList.toggle('erreur', !!erreur); };
    const lisible = (r) => { const e = (r && r.erreur) || 'erreur inconnue'; return /expir|jeton/.test(e) ? 'La connexion a expiré : reconnectez-vous avec le bouton du compte.' : e.charAt(0).toUpperCase() + e.slice(1) + '.'; };
    function charger() {
      if (!window.Relais.actif()) return;
      window.Relais.appeler('demandes_lire').then((r) => {
        if (!r || !r.ok) { bloc.hidden = false; dire(lisible(r), true); return; }
        bloc.hidden = false;
        $('#dm-nb').textContent = r.demandes.length || ''; $('#rv-nav-dm').textContent = r.demandes.length || '';
        if (!r.demandes.length) { liste.innerHTML = '<li class="sous">Aucune demande en attente.</li>'; return; }
        liste.innerHTML = r.demandes.map((d) => `<li class="dm-demande" data-n="${d.numero}">
          <p><strong>${esc(d.texte)}</strong> <span class="sous">demandé par ${esc(d.par || 'une personne connectée')}${d.date ? ', le ' + esc(jour(d.date)) : ''}</span></p>
          ${d.note ? `<p class="sous">${esc(d.note)}</p>` : ''}
          <label class="sr-only" for="dm-l-${d.numero}">Ligne à ajouter</label>
          <input id="dm-l-${d.numero}" type="text" value="${esc(d.texte)}" autocomplete="off">
          <p class="sous dm-controle" data-controle role="status"></p>
          <div class="dm-actions"><button type="button" class="bouton" data-dm="accepter">Accepter</button><button type="button" class="bouton bouton-clair" data-dm="refuser">Refuser</button></div></li>`).join('');
        liste.querySelectorAll('.dm-demande').forEach(controler);
      }).catch(() => {});
    }
    // Indicateur sous le champ : ligne correcte, ISBN invalide ou déjà dans la base
    function controler(li) {
      const zone = li.querySelector('[data-controle]');
      chargerCatalogue().then((cat) => {
        const c = evaluerLigne(cat, li.querySelector('input').value);
        zone.textContent = (c.ok ? '✓ ' : '✗ ') + c.texte; zone.classList.toggle('erreur', !c.ok);
      });
    }
    liste.addEventListener('input', (e) => { const li = e.target.closest('.dm-demande'); if (li) controler(li); });
    liste.addEventListener('click', (e) => {
      const b = e.target.closest('[data-dm]');
      if (!b) return;
      const li = b.closest('.dm-demande'), numero = Number(li.dataset.n), decision = b.dataset.dm;
      const donnees = { numero, decision };
      if (decision === 'accepter') {
        donnees.ligne = li.querySelector('input').value;
        chargerCatalogue().then((cat) => {
          const c = evaluerLigne(cat, donnees.ligne);
          if (!c.ok) { dire(c.texte + (/Déjà/.test(c.texte) ? ' Utilisez « Refuser » pour fermer la demande.' : ' Corrigez la ligne, puis acceptez de nouveau.'), true); return; }
          envoyerDecision(li, numero, decision, donnees);
        });
        return;
      }
      const raison = window.prompt('Raison du refus (facultatif, visible publiquement) :', ''); if (raison === null) return; donnees.raison = raison;
      envoyerDecision(li, numero, decision, donnees);
    });
    function envoyerDecision(li, numero, decision, donnees) {
      li.querySelectorAll('button').forEach((x) => { x.disabled = true; });
      dire('Enregistrement…');
      window.Relais.appeler('demande_traiter', donnees).then((r) => {
        if (r && r.ok) { dire(decision === 'accepter' ? 'Acceptée : le livre est en cours d\'ajout (environ 2 minutes).' : 'Demande refusée et fermée.'); charger(); } else { dire(lisible(r), true); li.querySelectorAll('button').forEach((x) => { x.disabled = false; }); }
      }).catch(() => { dire('Le service ne répond pas : vérifiez votre connexion.', true); li.querySelectorAll('button').forEach((x) => { x.disabled = false; }); });
    }
    document.addEventListener('cdh-porte-ouverte', charger);
    if (!$('#main').hidden) charger();
  }
  initDemandes();

  /* ---------- Tendances : la cote monte-t-elle ou baisse-t-elle, et où ? (données : data/tendances.json) ---------- */
  function initTendances() {
    const pct = (v) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v * 100).toFixed(0).replace('.', ',') + ' %';
    const NOMS = { decennie: 'année d\'édition', version: 'version', serie: 'série', editeur: 'éditeur' };
    fetch('data/tendances.json', { cache: 'no-store' }).then((x) => (x.ok ? x.json() : null)).catch(() => null).then((T) => {
      if (!T) return;
      let dim = 'decennie', avec = false, ouvert = null;
      const NAT = { 'validé': 'prix validé par un administrateur', annonces: 'annonces', 'prix éditeur': 'prix éditeur' }, ABR = { convenable: 'C', bon: 'BE', tres_bon: 'TBE' };
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
  // Annonces eBay retenues par le dernier relevé (data/annonces.json) : onglet « Annonces » et lien « Voir les annonces » de chaque livre
  let ANN = null, annChargees = false;
  const chargerAnnonces = () => {
    if (annChargees) return annChargees;
    annChargees = fetch('data/annonces.json', { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).catch(() => null)
      .then((a) => { ANN = a && a.annonces ? a : null; return ANN; });
    return annChargees;
  };
  const estSuper = () => !!window.Compte && window.Compte.role() === 'superadmin';        // les annonces ne sont montrées qu'au SuperAdmin
  const aDesAnnonces = (ed) => estSuper() && !!(ANN && ed.isbn && ANN.annonces[ed.isbn]);
  function annoncesEdition(ed) {
    const par = ANN.annonces[ed.isbn];
    const blocs = ETATS.map(([cle, lib]) => {
      const l = par[cle];
      if (!l || !l.length) return '';
      const disp = l.length > 1 && l[l.length - 1][0] > l[0][0] * 3 ? ' · prix très dispersés' : '';
      return `<h4>${lib} · ${l.length} annonce${l.length > 1 ? 's' : ''}${disp}</h4><ul>${l.map(([prix, titre, lien, origine]) => `<li><span class="rv-ann-prix">${eur(prix)}</span> <a href="${esc(lien)}" target="_blank" rel="noopener noreferrer" aria-label="Ouvrir l'annonce sur eBay (nouvel onglet) : ${esc(titre)}">${esc(titre)} ↗</a>${origine === 'titre' ? ' <span class="rv-ann-titre">trouvée par le titre</span>' : ''}</li>`).join('')}</ul>`;
    }).join('');
    return `<h3 class="rv-ann-livre">${esc(ed.titre)} <span class="sous">${esc(ed.serie)}${ed.numero && !/^0+$/.test(ed.numero) ? ' n° ' + esc(ed.numero) : ''} · ${esc(ed.version)}</span></h3>${blocs || '<p class="sous">Aucune annonce retenue pour cette édition.</p>'}`;
  }
  // Fenêtre ouverte depuis un livre de l'onglet Prix
  function ouvrirAnnonces(ed) {
    let dlg = $('#an-dialog');
    if (!dlg) {
      dlg = document.createElement('dialog');
      dlg.id = 'an-dialog'; dlg.className = 'an-dialog'; dlg.setAttribute('aria-labelledby', 'an-dialog-titre');
      dlg.innerHTML = '<div class="an-cadre"><div class="an-tete"><p class="surtitre" id="an-dialog-titre">Annonces eBay retenues</p><button type="button" class="bouton bouton-clair" id="an-fermer">Fermer</button></div><div id="an-dialog-corps"></div><p class="sous">Relevé du <span id="an-dialog-date"></span>. Ouvrez une annonce pour vérifier que c\'est bien le bon livre, dans le bon état.</p></div>';
      document.body.appendChild(dlg);
      dlg.addEventListener('click', (e) => { if (e.target === dlg || e.target.id === 'an-fermer') dlg.close(); });
    }
    $('#an-dialog-corps').innerHTML = annoncesEdition(ed);
    $('#an-dialog-date').textContent = jour(ANN.date);
    dlg.showModal();
  }
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-annonces]');
    if (!b) return;
    const ed = EDITIONS.find((x) => x.id === b.dataset.annonces);
    if (ed && aDesAnnonces(ed)) ouvrirAnnonces(ed);
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
      if (q.length < 2) { etat.textContent = `Relevé du ${jour(ANN.date)} : annonces retenues pour ${nbEd} éditions. Tapez au moins deux lettres.`; liste.innerHTML = ''; return; }
      const trouves = EDITIONS.filter((ed) => aDesAnnonces(ed) && (() => { const t = clair(ed.titre + ' ' + ed.serie + ' ' + (ed.numero || '')); return mots.every((m) => t.includes(m)); })()).slice(0, 12);
      etat.textContent = trouves.length ? `${trouves.length} édition${trouves.length > 1 ? 's' : ''}${trouves.length === 12 ? ' (les 12 premières : précisez la recherche)' : ''}.` : 'Aucune édition avec des annonces retenues pour cette recherche.';
      liste.innerHTML = trouves.map((ed) => `<article class="rv-edition">${annoncesEdition(ed)}</article>`).join('');
    };
    champ.addEventListener('input', dessiner);
    document.addEventListener('cdh-pane', (e) => { if (e.detail === 'annonces' && estSuper()) chargerAnnonces().then(dessiner); });
    dessiner();
  }

  function initNav() {
    const boutons = [...document.querySelectorAll('#rv-nav [data-pane]')];
    const montrer = (nom) => {
      boutons.forEach((b) => { b.setAttribute('aria-selected', String(b.dataset.pane === nom)); b.tabIndex = b.dataset.pane === nom ? 0 : -1; });
      document.querySelectorAll('.rv-pane').forEach((p) => { p.hidden = p.id !== 'pane-' + nom; });
      document.dispatchEvent(new CustomEvent('cdh-pane', { detail: nom }));
      try { sessionStorage.setItem('cdh-rv-pane', nom); } catch (e) { /* sans stockage : la page s'ouvre sur les prix */ }
    };
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
    [['tendances', '#rv-tendances'], ['demandes', '#rv-demandes']].forEach(([nom, sel]) => {
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
  initNav();
  // Annonces : lien et onglet réservés au SuperAdmin (le rôle arrive après la connexion)
  function majAnnonces() {
    const onglet = document.querySelector('#rv-nav [data-pane="annonces"]');
    const super_ = estSuper();
    if (onglet) {
      onglet.hidden = !super_;
      if (!super_ && onglet.getAttribute('aria-selected') === 'true') { const prix = document.querySelector('#rv-nav [data-pane="prix"]'); if (prix) prix.click(); }
    }
    if (super_) chargerAnnonces().then(() => { if (ANN && EDITIONS.length) afficher(); });
    else if (EDITIONS.length) afficher();
  }
  document.addEventListener('cdh-compte', majAnnonces);
  majAnnonces();

  // Dernières mises à jour automatiques du site (relevé des prix, ajouts, corrections, publication) : lues dans l'historique public des lots,
  // pour savoir d'un coup d'œil quand le dernier a tourné et s'il a réussi. Gardé cinq minutes dans le navigateur.
  const FAMILLES = [['prix-ebay.yml', 'Relevé des prix'], ['ajout-isbn.yml', 'Ajout de livres'], ['corriger-fiche.yml', 'Correction de fiches'], ['corriger-prix.yml', 'Correction de cotes'], ['pages.yml', 'Publication du site'], ['veille-parutions.yml', 'Veille des parutions']];
  const depuis = (d) => {
    const m = Math.max(0, Math.round((Date.now() - d.getTime()) / 60000));
    return m < 2 ? 'à l\'instant' : m < 60 ? `il y a ${m} min` : m < 36 * 60 ? `il y a ${Math.round(m / 60)} h` : `il y a ${Math.round(m / 1440)} jours`;
  };
  function initMaj() {
    const bloc = $('#rv-maj');
    if (!bloc) return;
    const CLE = 'cdh-rv-lots';
    const lire = () => { try { const c = JSON.parse(sessionStorage.getItem(CLE) || 'null'); if (c && Date.now() - c.t < 300000) return Promise.resolve(c.runs); } catch (e) { /* pas de cache */ }
      return fetch('https://api.github.com/repos/loliba92/LDVELH/actions/runs?per_page=100', { headers: { Accept: 'application/vnd.github+json' } }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then((d) => { const runs = d.workflow_runs.map((x) => ({ f: x.path.split('/').pop(), st: x.status, c: x.conclusion, t: x.status === 'completed' ? x.updated_at : x.run_started_at })); try { sessionStorage.setItem(CLE, JSON.stringify({ t: Date.now(), runs })); } catch (e) { /* idem */ } return runs; }); };
    lire().then((runs) => {
      const etat = (r) => (r.st !== 'completed' ? ['en cours…', 'en-cours'] : r.c === 'success' ? ['✓ réussi', 'ok'] : r.c === 'cancelled' ? ['annulé', 'annule'] : ['✗ échec', 'echec']);
      const lignes = FAMILLES.map(([f, nom]) => ({ nom, r: runs.find((x) => x.f === f) }));
      const quand = (r) => { const d = new Date(r.t); return `${depuis(d)} (${d.toLocaleString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })})`; };
      const releve = lignes[0];
      const recent = lignes.filter((l) => l.r).sort((a, b) => new Date(b.r.t) - new Date(a.r.t))[0];
      const vedette = releve.r || recent;
      if (!vedette) return;
      const [txt, cls] = etat(vedette.r || vedette);
      $('#rv-maj-resume').innerHTML = `<strong>${esc(releve.r ? 'Dernier relevé des prix' : recent.nom)}</strong> : ${esc(quand(releve.r || recent.r))} · <span class="rv-lot-${cls}">${esc(txt)}</span>`;
      $('#rv-maj-liste').innerHTML = lignes.map((l) => { if (!l.r) return `<li><strong>${esc(l.nom)}</strong> : pas d'exécution récente</li>`; const [t, c] = etat(l.r); return `<li><strong>${esc(l.nom)}</strong> : ${esc(quand(l.r))} · <span class="rv-lot-${c}">${esc(t)}</span></li>`; }).join('');
      const veille = lignes.find((l) => l.nom === 'Veille des parutions'), age = veille && veille.r ? (Date.now() - new Date(veille.r.t).getTime()) / 86400000 : null;
      if (veille && (age === null || age > 2)) {                    // GitHub peut sauter un passage programmé : on le voit ici plutôt que de le deviner
        const alerte = age === null ? 'pas encore d\'exécution' : `pas d'exécution depuis ${Math.floor(age)} jours`;
        $('#rv-maj-resume').innerHTML += ` <span class="rv-lot-echec">⚠ Veille des parutions : ${esc(alerte)}. Lancez-la à la main (Actions, « Veille des parutions »).</span>`;
        bloc.open = true;
      }
      bloc.hidden = false;
    }).catch(() => { /* historique indisponible (limite de l'interface publique) : rien n'est affiché */ });
  }
  initMaj();

  const JAQ = {}, RAR = {};
  fetch('data/versions.json').then((r) => r.json()).then((v) => v.forEach((b) => { if (b.couverture) JAQ[b.id] = b.couverture; if (b.rarete) RAR[b.id] = b.rarete; })).catch(() => {})
    .then(() => fetch('data/revue.json')).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then((d) => {
    const par = new Map();
    d.forEach((l) => { if (!par.has(l.id)) par.set(l.id, { id: l.id, isbn: l.isbn, titre: l.titre, serie: l.serie, numero: l.numero, version: l.version, etats: {} }); par.get(l.id).etats[l.etat] = l; });
    EDITIONS = [...par.values()];
    // Une validation déjà reprise dans les données du site n'a plus besoin d'être transmise
    EDITIONS.forEach((ed) => ETATS.forEach(([cle]) => { const l = ed.etats[cle], k = cleDe(ed, cle); if (l && l.valide && LOC[k] && LOC[k].prix === l.publie) delete LOC[k]; }));
    sauver();
    $('#rv-serie').innerHTML = '<option value="">Toutes les séries</option>' + [...new Set(EDITIONS.map((e) => e.serie))].sort((a, b) => a.localeCompare(b, 'fr')).map((s) => `<option>${esc(s)}</option>`).join('');
    document.querySelectorAll('#rv-onglets button').forEach((b) => b.addEventListener('click', () => { vue = b.dataset.vue; limite = PAGE; afficher(); }));
    ['#rv-q', '#rv-serie'].forEach((s) => $(s).addEventListener('input', () => { limite = PAGE; afficher(); }));
    $('#rv-plus').addEventListener('click', () => { limite += PAGE; afficher(); });
    $('#rv-csv').addEventListener('click', csv);
    $('#rv-tout-confirmer').addEventListener('click', toutConfirmerListe);
    $('#rv-envoyer').addEventListener('click', envoyer);
    afficher();
  }).catch(() => { $('#rv-liste').innerHTML = '<p class="erreur">Les données n\'ont pas pu être chargées.</p>'; });
})();
