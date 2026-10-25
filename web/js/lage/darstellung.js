/*
 * Menü „Darstellung“: Farb-Schema, Symbole, Schrift und der Knopf „Anpassen“ mit dem Formular für eigene Farben und Symbole.
 *
 * Zweck:    Baut die Auswahl aus skins.js, schrift.js und anpassen.js auf und hält state.schema, state.symbole, state.eigen, state.skin.
 *           Der eigentliche Wechsel (Ebenen, Neuzeichnen) läuft im Rückruf `onChange` (ebenen.js).
 * Hinweis:  Ein Symbolsatz bringt eigene Farben mit; dann ist das Farb-Schema gesperrt. Nichts wird gespeichert (kein Storage).
 */
import { $ } from '../util.js';
import { FARBFELDER, baueEigenenSkin, farbenVon, gueltigeFarbe } from './anpassen.js';
import { AUTO, BUNDLED, applyFont, cleanFontName, localNames, queryLocalFamilies, setLocalNames } from './schrift.js';
import { SCHEMATA, SYMBOLSAETZE, effektiverSkin, setEigenerSkin, skinById } from './skins.js';
import { ARTS } from './zeichensaetze.js';
import { state } from './zustand.js';

const neuEigen = () => ({ farben: { light: {}, dark: {} }, art: {}, patterns: null, decor: null, fauna: null });
const dunkel = () => document.documentElement.dataset.ansicht === 'dunkel';

export function initDarstellung(onChange) {
  state.schema ??= 'landblick'; state.symbole ??= 'landblick'; state.eigenAn ??= false; state.eigen ??= neuEigen();
  const boxSchema = $('#fs-schema'), boxSymbole = $('#fs-symbole'), hint = $('#darstellung-hinweis'), custom = $('#anpassen-aktiv');
  if (!boxSchema || !boxSymbole) return;

  const radios = (box, name, list, current) => box.replaceChildren(...[...box.querySelectorAll('legend')], ...list.map((s) => {
    const lab = document.createElement('label'), r = document.createElement('input');
    r.type = 'radio'; r.name = name; r.value = s.id; r.checked = s.id === current;
    lab.append(r, ` ${s.name}`);
    return lab;
  }));
  const syncUi = () => {
    for (const r of boxSchema.querySelectorAll('input')) { r.checked = r.value === state.schema; r.disabled = state.symbole !== 'landblick'; }
    for (const r of boxSymbole.querySelectorAll('input')) r.checked = r.value === state.symbole;
    const sk = skinById(state.skin);
    hint.textContent = `${sk.hinweis}.${state.symbole !== 'landblick' ? ' Der Symbolsatz bringt seine eigenen Farben mit.' : ''} Die Ebenen bleiben in jeder Darstellung wählbar.`;
    custom.hidden = !state.eigenAn;
  };
  const apply = () => {
    if (state.eigenAn) {
      const b = baueEigenenSkin(state.schema, state.symbole, state.eigen);
      setEigenerSkin(b.skin);
      if (b.art) ARTS.eigen = b.art;
    }
    state.skin = effektiverSkin(state.schema, state.symbole, state.eigenAn);
    syncUi();
    onChange();
  };
  radios(boxSchema, 'schema', SCHEMATA, state.schema);
  radios(boxSymbole, 'symbole', SYMBOLSAETZE, state.symbole);
  boxSchema.addEventListener('change', (e) => { if (e.target.name !== 'schema') return; state.schema = e.target.value; state.eigenAn = false; state.eigen = neuEigen(); apply(); });
  boxSymbole.addEventListener('change', (e) => { if (e.target.name !== 'symbole') return; state.symbole = e.target.value; state.eigenAn = false; state.eigen = neuEigen(); apply(); });
  syncUi();
  initSchriftwahl();
  initAnpassen(apply, syncUi);
}

// Formular „Anpassen“: Farben (je nach Methode) und Symbolschalter; „Übernehmen“ baut den Skin 'eigen'
function initAnpassen(apply, syncUi) {
  const dlg = $('#dlg-anpassen'), form = $('#anpassen-form'), felder = $('#anpassen-felder'), schalter = $('#anpassen-schalter'), titel = $('#anpassen-titel');
  if (!dlg || !form) return;
  let methode = 'tint', base = {}, dark = false;
  const sBasis = () => {   // Ausgangsfarben: bei Zeichensatz dessen Werte, sonst Palette des Schemas (Landblick: Mountain View)
    if (state.symbole !== 'landblick') { methode = 'art'; return farbenVon('art', skinById(state.symbole).art); }
    methode = 'tint';
    const t = skinById(state.schema).tint ?? skinById('mountain-view').tint;
    return farbenVon('tint', t[dark ? 'dark' : 'light']);
  };
  const feldZeile = (key, label, wert) => {
    const row = document.createElement('label'), inp = document.createElement('input');
    inp.type = 'color'; inp.name = key; inp.value = gueltigeFarbe(wert) ? wert : '#808080';
    row.append(inp, ` ${label}`);
    return row;
  };
  const check = (key, label, an) => {
    const row = document.createElement('label'), inp = document.createElement('input');
    inp.type = 'checkbox'; inp.name = key; inp.checked = an;
    row.append(inp, ` ${label}`);
    return row;
  };
  const fuelle = () => {
    dark = dunkel();
    base = sBasis();
    const ov = methode === 'art' ? state.eigen.art : state.eigen.farben[dark ? 'dark' : 'light'];
    titel.textContent = methode === 'art'
      ? `Farben von „${skinById(state.symbole).name}“`
      : `Farben von „${skinById(state.schema).name === 'Landblick' ? 'Mountain View' : skinById(state.schema).name}“ (${dark ? 'dunkle' : 'helle'} Ansicht)`;
    felder.replaceChildren(...FARBFELDER[methode].map(([k, l]) => feldZeile(k, l, ov[k] ?? base[k])));
    const a = ARTS[skinById(state.symbole).art];
    schalter.replaceChildren(...(methode === 'art'
      ? [check('decor', 'Windrose und Titelschild', state.eigen.decor ?? a.decor), check('fauna', 'Fabelwesen', state.eigen.fauna ?? a.fauna)]
      : [check('patterns', 'Flächenmuster (Wald, Acker, Wiese)', state.eigen.patterns ?? (skinById(state.schema).tint?.patterns !== false && !!skinById(state.schema).tint))]));
  };
  const zu = () => (typeof dlg.close === 'function' ? dlg.close() : dlg.removeAttribute('open'));
  $('#anpassen-open').addEventListener('click', () => { fuelle(); if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', ''); });
  $('#anpassen-zu').addEventListener('click', () => zu());
  $('#anpassen-reset').addEventListener('click', () => { state.eigenAn = false; state.eigen = neuEigen(); apply(); fuelle(); });
  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const ov = {};
    for (const [k] of FARBFELDER[methode]) {
      const v = form.elements[k]?.value;
      if (gueltigeFarbe(v) && v.toLowerCase() !== String(base[k]).toLowerCase()) ov[k] = v;
    }
    if (methode === 'art') { state.eigen.art = ov; state.eigen.decor = form.elements.decor.checked; state.eigen.fauna = form.elements.fauna.checked; }
    else { state.eigen.farben[dark ? 'dark' : 'light'] = ov; state.eigen.patterns = form.elements.patterns.checked; }
    state.eigenAn = true;
    apply();
    zu();
  });
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
