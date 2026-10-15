import { decor } from '../medieval.js';
import { enableSound } from '../ping-sound.js';
import { setReliefVisible } from '../relief.js';
import { $, initTheme, tickAges } from '../util.js';
import { applyBaseToggles, applyLegend, applyLight, recolor } from './basiskarte.js';
import { pushAir, refreshAir } from './flugverkehr.js';
import { refresh, render } from './laden.js';
import { SACRAL_LAYERS } from '../infra.js';
import { windrose } from './mittelalter.js';
import { AUTO, BUNDLED, applyFont, cleanFontName, localNames, queryLocalFamilies, setLocalNames } from './schrift.js';
import { SKINS, skinById } from './skins.js';
import { applyArt } from './zeichensatz.js';
import { artOf } from './zeichensaetze.js';
import { applyNatureVisibility } from './natur.js';
import { applyInfra, applyInfraVisibility, applyRoutesVisibility, applyStopsVisibility } from './orte.js';
import { applyBlitzVisibility, applyFlow, applyLegends, applyRadarVisibility, applyWind } from './wetterkarte.js';
import { AIR_POLL_MS, GROUPS, map, mapReady, reliefOk, state } from './zustand.js';

export function applyLayerFilters() {
  if (!mapReady) return;
  const types = Object.entries(GROUPS).filter(([g]) => state.layers[g]).flatMap(([, t]) => t);
  const typeFilter = ['in', ['get', 'type'], ['literal', types]];
  const isPoint = ['==', ['geometry-type'], 'Point'];
  const isLine = ['any', ['==', ['geometry-type'], 'LineString'], ['==', ['geometry-type'], 'MultiLineString']];
  const isArea = ['any', ['==', ['geometry-type'], 'Polygon'], ['==', ['geometry-type'], 'MultiPolygon']];
  const works = ['any', ['==', ['get', 'source_id'], 'lbm_baustellen'], ['==', ['get', 'icon'], 'baustelle']], notWorks = ['!', works];
  const base = {
    'ev-fill': isArea, 'ev-outline': isArea, 'ev-line': isLine, 'ev-line-halo': isLine, 'ev-point': isPoint,
    'ev-sym-pt': ['all', isPoint, notWorks], 'ev-sym-ln': ['all', isLine, notWorks],
    'ev-sym-pt-w': ['all', isPoint, works], 'ev-sym-ln-w': ['all', isLine, works], 'ev-dot-w': ['all', isPoint, works],
  };
  for (const [id, f] of Object.entries(base)) map.setFilter(id, ['all', f, typeFilter]);
  const on = (v) => (v ? 'visible' : 'none');
  map.setLayoutProperty('st-sym', 'visibility', on(state.layers.gew && state.iconsOk));
  map.setLayoutProperty('st-circle', 'visibility', on(state.layers.gew && !state.iconsOk));
  map.setLayoutProperty('air-dim', 'visibility', on(state.layers.air));
  map.setLayoutProperty('air-sym', 'visibility', on(state.layers.air && state.iconsOk));
  map.setLayoutProperty('air-circle', 'visibility', on(state.layers.air && !state.iconsOk));
  const envKinds = [state.layers.airq && 'air', state.layers.rad && 'radiation', state.layers.wxst && 'weather'].filter(Boolean);
  const envOn = envKinds.length > 0;
  const envKind = ['in', ['get', 'kind'], ['literal', envKinds]];
  for (const id of ['env-sym', 'env-circle']) map.setFilter(id, envKind);
  map.setLayoutProperty('wxst-label', 'visibility', on(state.layers.wxst && state.iconsOk));
  map.setLayoutProperty('env-sym', 'visibility', on(envOn && state.iconsOk));
  map.setLayoutProperty('env-circle', 'visibility', on(envOn && !state.iconsOk));
  map.setLayoutProperty('tank-sym', 'visibility', on(state.layers.tank && state.iconsOk));
  map.setLayoutProperty('tank-label', 'visibility', on(state.layers.tank && state.iconsOk));
  applyInfraVisibility();
  applyRoutesVisibility();
  map.setLayoutProperty('tank-circle', 'visibility', on(state.layers.tank && !state.iconsOk));
  applyBaseToggles();
  applyFlow();
  applyRadarVisibility();
  applyWind();
  applyBlitzVisibility();
  applyStopsVisibility();
  applyNatureVisibility();
  if (reliefOk) { setReliefVisible(map, state.layers.relief, state.layers.contours); applyLight(); applyLegend(); }
}

export function wire() {
  initTheme($('#theme'));
  document.addEventListener('ansicht', () => setTimeout(recolor, 0));
  for (const r of document.querySelectorAll('input[name="within"]')) r.addEventListener('change', () => { state.within = r.value; render(); });
  $('#pingsound')?.addEventListener('change', (e) => { // Nutzerklick: erst jetzt darf der Browser Ton erzeugen
    if (!enableSound(e.target.checked)) e.target.checked = false;
  });
  let medApplied = false, autoHeritage = false;
  const decorOn = () => !!state.layers.medieval && !!artOf(skinById(state.skin).art)?.decor;   // Titelschild und Windrose nur, wo der Zeichensatz sie führt
  const setLayer = (name, on) => { const cb = document.querySelector(`input[data-layer="${name}"]`); if (cb) cb.checked = on; state.layers[name] = on; };
  const syncMedieval = () => {
    if (state.layers.medieval === medApplied) return;
    medApplied = state.layers.medieval;
    // Burgen, Ruinen, Klöster und historische Gebäude gehören zur Karte: beim Einschalten mit einblenden, beim Ausschalten wieder zurück
    const HER = ['herCastle', 'herArch', 'herMonastery', 'herBuilding', 'herChurch', 'herChapel', 'herCross', 'herMill', 'herFord', 'herBorder', 'herGallows', 'herWell'];
    if (medApplied && !HER.some((n) => state.layers[n])) { for (const n of HER) setLayer(n, true); autoHeritage = true; }
    else if (!medApplied && autoHeritage) { for (const n of HER) setLayer(n, false); autoHeritage = false; }
    if (!medApplied) autoHeritage = false;
    windrose(decorOn()); decor(decorOn()); applyLegends();
    applyLayerFilters(); syncGroups(); recolor(); applyInfra();
  };
  const syncGroups = () => { // Themenschalter: an, wenn alle Ebenen des Themas an sind; „gemischt“, wenn nur einige
    for (const g of document.querySelectorAll('.layer-group')) {
      const t = g.querySelector('.group-toggle'), all = [...g.querySelectorAll('input[data-layer]')];
      const n = all.filter((c) => c.checked).length;
      t.checked = n === all.length; t.indeterminate = n > 0 && n < all.length;
    }
  };
  for (const cb of document.querySelectorAll('input[data-layer]')) cb.addEventListener('change', () => {
    state.layers[cb.dataset.layer] = cb.checked; applyLayerFilters(); render(); syncGroups(); syncMedieval();
    if (SACRAL_LAYERS.includes(cb.dataset.layer)) applyInfra();   // Kirchen, Mühlen … erst laden, wenn eine dieser Ebenen an ist
    if (cb.dataset.layer === 'licht') applyLight();
    if (cb.dataset.layer === 'air' && cb.checked) refreshAir();
  });
  for (const t of document.querySelectorAll('.group-toggle')) t.addEventListener('change', () => {
    const boxes = [...t.closest('.layer-group').querySelectorAll('input[data-layer]')];
    for (const cb of boxes) { cb.checked = t.checked; state.layers[cb.dataset.layer] = t.checked; }
    applyLayerFilters(); render(); syncGroups(); syncMedieval();
    if (boxes.some((cb) => SACRAL_LAYERS.includes(cb.dataset.layer))) applyInfra();
    if (boxes.some((cb) => cb.dataset.layer === 'licht')) applyLight();
    if (t.checked && boxes.some((cb) => cb.dataset.layer === 'air')) refreshAir();
  });
  // Darstellung: Radios und Hinweis aus der Liste der Skins (skins.js); Alte Karte schaltet zusätzlich die historischen Ebenen
  const skinBox = document.querySelector('#ctl-darstellung fieldset');
  const skinHint = document.querySelector('#ctl-darstellung .group-hint');
  if (skinBox) {
    skinBox.replaceChildren(...[...skinBox.querySelectorAll('legend')], ...SKINS.map((s) => {
      const lab = document.createElement('label'), r = document.createElement('input');
      r.type = 'radio'; r.name = 'skin'; r.value = s.id; r.checked = s.id === state.skin;
      lab.append(r, ` ${s.name}`);
      return lab;
    }));
  }
  const showHint = () => { if (skinHint) skinHint.textContent = `${skinById(state.skin).hinweis}. Die Ebenen bleiben in jeder Darstellung wählbar.`; };
  showHint();
  for (const r of document.querySelectorAll('input[name="skin"]')) r.addEventListener('change', () => {
    if (!r.checked) return;
    const sk = skinById(r.value);
    state.skin = sk.id; state.layers.medieval = !!sk.art; showHint();
    if (sk.art) applyArt(map, sk.art);   // Zeichensatz: Farben, Schrift, Muster und Symbole neu
    applyLayerFilters(); render(); syncGroups();
    if (state.layers.medieval !== medApplied) syncMedieval(); else { windrose(decorOn()); decor(decorOn()); recolor(); }
  });
  initSchriftwahl();
  syncGroups();
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  for (const t of tabs) t.addEventListener('click', () => {
    for (const o of tabs) { o.setAttribute('aria-selected', String(o === t)); $(`#${o.getAttribute('aria-controls')}`).hidden = o !== t; }
  });
  setInterval(tickAges, 30000);
  setInterval(refresh, 60000); // Dateien alle 60 s neu holen (kein Server-Push auf statischem Webspace)
  setInterval(refreshAir, AIR_POLL_MS); // Flüge: kleine Datei alle 15 s, nur bei eingeschalteter Ebene und sichtbarem Tab
  setInterval(() => { if (!document.hidden && state.layers.air) pushAir(); }, 1000); // weiterrücken und Stand-Anzeige
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshAir(); });
}

// Darstellung → Schrift: mitgelieferte OFL-Schriften, dazu Schriften dieses Geräts (Liste per Zustimmung oder frei getippt)
function initSchriftwahl() {
  const sel = $('#schrift-wahl'), btn = $('#schrift-lokal'), inp = $('#schrift-name'), dl = $('#schrift-liste'), note = $('#schrift-hinweis');
  if (!sel) return;
  const group = (label, names, labels = {}) => {
    const g = document.createElement('optgroup');
    g.label = label;
    for (const n of names) { const o = document.createElement('option'); o.value = n; o.textContent = labels[n] ?? n; g.append(o); }
    return g;
  };
  const fill = () => {
    const keep = state.schrift;
    sel.replaceChildren(Object.assign(document.createElement('option'), { value: AUTO, textContent: 'Standard der Darstellung' }),
      group('Mitgeliefert (frei)', BUNDLED.map((b) => b.name), Object.fromEntries(BUNDLED.map((b) => [b.name, b.label]))));
    if (localNames().length) sel.append(group('Auf diesem Gerät', localNames()));
    dl.replaceChildren(...localNames().map((n) => Object.assign(document.createElement('option'), { value: n })));
    sel.value = [...sel.options].some((o) => o.value === keep) ? keep : AUTO;
  };
  const choose = (name) => { state.schrift = name; sel.value = name; applyFont(name); };
  fill();
  sel.addEventListener('change', () => choose(sel.value));
  btn.addEventListener('click', async () => {
    try {
      const n = (await queryLocalFamilies()).length;
      fill();
      note.textContent = n ? `${n} Schriften dieses Geräts verfügbar (Liste „Auf diesem Gerät“).` : 'Keine Geräteschriften gemeldet.';
    } catch {
      note.textContent = 'Die Liste ist in diesem Browser nicht freigegeben. Tippen Sie den Namen einer installierten Schrift ins Feld.';
    }
  });
  inp.addEventListener('change', () => {
    const n = cleanFontName(inp.value);
    if (!n) return;
    setLocalNames([...localNames(), n]);
    fill();
    const hit = localNames().find((x) => x.toLowerCase() === n.toLowerCase()) ?? n;
    choose([...sel.options].some((o) => o.value === hit) ? hit : n);
    note.textContent = `Schrift „${hit}“ gewählt. Ist sie auf diesem Gerät nicht installiert, zeigt der Browser eine Ersatzschrift.`;
    inp.value = '';
  });
}
