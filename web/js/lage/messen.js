// Messwerkzeug auf der Karte: Punkte anklicken ergibt eine Strecke; den ersten Punkt erneut anklicken (oder „Schließen“) ergibt eine Fläche mit Umfang.
// Bedienung ohne Maus: Knopf „Punkt in Kartenmitte“, Rücktaste (zurück), Eingabe (schließen), Esc (beenden). Rechnung: ../messen.js.
// Während das Werkzeug an ist, öffnen Klicks keine Popups (karte.js fragt messenAktiv()). Nichts wird gespeichert oder gesendet.
import { messenFeatures, summary } from '../messen.js';
import { map, state } from './zustand.js';

const COLOR = '#c026d3';
const SRC = ['line', 'rubber', 'fill', 'points', 'labels'];
let aktiv = false, closed = false, pts = [], cursor = null, panel = null, knopf = null;
export const messenAktiv = () => aktiv;

function ensureLayers() {
  if (map.getSource('mess-line')) return;
  for (const k of SRC) map.addSource(`mess-${k}`, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  const layout = { 'line-cap': 'round', 'line-join': 'round' };
  map.addLayer({ id: 'mess-fill', type: 'fill', source: 'mess-fill', paint: { 'fill-color': COLOR, 'fill-opacity': 0.2 } });
  map.addLayer({ id: 'mess-casing', type: 'line', source: 'mess-line', layout, paint: { 'line-color': '#fff', 'line-width': 6, 'line-opacity': 0.9 } });
  map.addLayer({ id: 'mess-line', type: 'line', source: 'mess-line', layout, paint: { 'line-color': COLOR, 'line-width': 3 } });
  map.addLayer({ id: 'mess-rubber', type: 'line', source: 'mess-rubber', layout, paint: { 'line-color': COLOR, 'line-width': 2, 'line-dasharray': [2, 2] } });
  map.addLayer({ id: 'mess-points', type: 'circle', source: 'mess-points', paint: { 'circle-radius': ['case', ['==', ['get', 'first'], 1], 7, 5], 'circle-color': ['case', ['==', ['get', 'first'], 1], '#fff', COLOR], 'circle-stroke-color': COLOR, 'circle-stroke-width': 2.5 } });
  map.addLayer({ id: 'mess-labels', type: 'symbol', source: 'mess-labels',
    layout: { 'text-field': ['get', 'text'], 'text-font': ['Noto Sans Regular'], 'text-size': 12, 'text-allow-overlap': true, 'text-offset': [0, -0.9] },
    paint: { 'text-color': '#4a044e', 'text-halo-color': '#fff', 'text-halo-width': 2 } });
}

const el = (tag, attrs = {}, ...kids) => { const e = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); e.append(...kids); return e; };

function draw() {
  const f = messenFeatures(pts, closed, cursor);
  for (const k of SRC) map.getSource(`mess-${k}`)?.setData(f[k]);
  const s = summary(pts, closed);
  panel.querySelector('.messen-werte').replaceChildren(...s.lines.map((t, i) => el('p', i === 0 && pts.length ? { class: 'messen-haupt' } : {}, t)));
  panel.querySelector('.messen-warn').textContent = s.warn;
  panel.querySelector('[data-m="zurueck"]').disabled = !pts.length;
  panel.querySelector('[data-m="neu"]').disabled = !pts.length;
  panel.querySelector('[data-m="schliessen"]').disabled = closed || pts.length < 3;
  panel.querySelector('[data-m="kopieren"]').disabled = !pts.length;
  panel.dataset.text = [...s.lines, s.warn].filter(Boolean).join('\n');
}

function add(lngLat) {
  if (closed) return;
  const p = [lngLat.lng, lngLat.lat];
  const first = pts[0] && map.project(pts[0]);
  const here = map.project(p);
  if (pts.length >= 3 && first && Math.hypot(first.x - here.x, first.y - here.y) < 14) closed = true;   // ersten Punkt getroffen: Fläche
  else pts.push(p);
  cursor = null;
  draw();
}

function undo() { if (closed) closed = false; else pts.pop(); draw(); }
function reset() { pts = []; closed = false; cursor = null; draw(); }

function toggle(on) {
  aktiv = on;
  if (on) ensureLayers();
  knopf.setAttribute('aria-pressed', String(on));
  knopf.classList.toggle('an', on);
  panel.hidden = !on;
  map.getContainer().classList.toggle('messen-aktiv', on);
  if (on) { map.doubleClickZoom.disable(); document.getElementById('map-popup-close')?.click(); }
  else map.doubleClickZoom.enable();
  reset();
}

export function initMessen() {
  const btn = el('button', { type: 'button', class: 'messen-knopf', title: 'Entfernung und Fläche messen', 'aria-label': 'Messen: Entfernung und Fläche', 'aria-pressed': 'false' }, el('span', { class: 'ico ico-m-lineal', 'aria-hidden': 'true' }));
  knopf = btn;
  const group = el('div', { class: 'maplibregl-ctrl maplibregl-ctrl-group' }, btn);
  map.addControl({ onAdd: () => group, onRemove: () => group.remove() }, 'top-right');
  const b = (m, label, title) => el('button', { type: 'button', 'data-m': m, title }, label);
  panel = el('section', { class: 'messen-box', 'aria-label': 'Messen', hidden: '' },
    el('div', { class: 'messen-kopf' }, el('strong', {}, 'Messen'), b('ende', 'Beenden', 'Messen beenden (Esc)')),
    el('div', { class: 'messen-werte', role: 'status', 'aria-live': 'polite' }),
    el('p', { class: 'messen-warn small' }),
    el('p', { class: 'messen-hinweis small muted' }, 'Ersten Punkt erneut anklicken schließt die Fläche. Kugelrechnung, Abweichung unter 0,5 %; keine Vermessung.'),
    el('div', { class: 'messen-tasten' }, b('mitte', 'Punkt in Kartenmitte', 'Punkt in die Mitte des Kartenausschnitts setzen'), b('zurueck', 'Zurück', 'Letzten Punkt entfernen (Rücktaste)'),
      b('schliessen', 'Schließen', 'Fläche schließen (Eingabetaste)'), b('neu', 'Neu', 'Alle Punkte löschen'), b('kopieren', 'Kopieren', 'Werte in die Zwischenablage')));
  map.getContainer().parentElement.append(panel);
  btn.addEventListener('click', () => toggle(!aktiv));
  panel.addEventListener('click', (e) => {
    const m = e.target.closest('button')?.dataset.m;
    if (m === 'ende') toggle(false);
    else if (m === 'mitte') add(map.getCenter());
    else if (m === 'zurueck') undo();
    else if (m === 'neu') reset();
    else if (m === 'schliessen' && pts.length >= 3) { closed = true; draw(); }
    else if (m === 'kopieren') navigator.clipboard?.writeText(panel.dataset.text ?? '').then(() => { e.target.textContent = 'Kopiert'; setTimeout(() => { e.target.textContent = 'Kopieren'; }, 1500); }).catch(() => {});
  });
  map.on('click', (e) => { if (aktiv) add(e.lngLat); });
  map.on('mousemove', (e) => { if (aktiv && !closed && pts.length) { cursor = [e.lngLat.lng, e.lngLat.lat]; map.getSource('mess-rubber')?.setData(messenFeatures(pts, false, cursor).rubber); } });
  document.addEventListener('keydown', (e) => {
    if (!aktiv || e.target.closest?.('input, textarea, select')) return;
    if (e.key === 'Escape') toggle(false);
    else if (e.key === 'Backspace' || e.key === 'Delete') { e.preventDefault(); undo(); }
    else if (e.key === 'Enter' && e.target === document.body && pts.length >= 3 && !closed) { closed = true; draw(); }
  });
  draw();
}
