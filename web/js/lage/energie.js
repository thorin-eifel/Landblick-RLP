// Energie auf der Karte: Leitungen nach Spannung, Solarparks als Fläche, Kraftwerke, Umspannwerke und Transformatoren als Plaketten.
// Daten: state.energie (energie.json oder Zellenart 'energie'). Auf der Karte um 1450 ausgeblendet. Reine Teile: ../energie.js.
import { ENERGIE_COLOR, LINE_COLOR, PLAQUE_KINDS, energieFeatures, energieKinds } from '../energie.js';
import { map, mapReady, state } from './zustand.js';

const PX = 56;
const draw = {
  solar(x) {   // Sonne über Modulfläche
    x.fillStyle = '#fde047'; x.strokeStyle = '#fde047'; x.lineWidth = 3;   // gelbe Sonne auf blauem Grund, dazu weiße Module
    x.beginPath(); x.arc(28, 18, 6, 0, Math.PI * 2); x.fill();
    for (let a = 0; a < 8; a++) { const t = (a * Math.PI) / 4; x.beginPath(); x.moveTo(28 + Math.cos(t) * 9.5, 18 + Math.sin(t) * 9.5); x.lineTo(28 + Math.cos(t) * 13, 18 + Math.sin(t) * 13); x.stroke(); }
    x.fillStyle = '#fff'; x.beginPath(); x.moveTo(10, 50); x.lineTo(15, 33); x.lineTo(41, 33); x.lineTo(46, 50); x.closePath(); x.fill();
    x.strokeStyle = ENERGIE_COLOR.solar; x.lineWidth = 1.6;
    x.beginPath(); x.moveTo(28, 33); x.lineTo(28, 50); x.moveTo(12.5, 41.5); x.lineTo(43.5, 41.5); x.stroke();
  },
  plant(x) {   // Kühlturm
    x.fillStyle = '#fff'; x.beginPath(); x.moveTo(13, 48); x.bezierCurveTo(19, 36, 19, 26, 15, 14); x.lineTo(41, 14); x.bezierCurveTo(37, 26, 37, 36, 43, 48); x.closePath(); x.fill();
    x.strokeStyle = '#fff'; x.lineWidth = 3; x.beginPath(); x.moveTo(23, 10); x.bezierCurveTo(20, 6, 26, 4, 24, 1); x.moveTo(33, 10); x.bezierCurveTo(30, 6, 36, 4, 34, 1); x.stroke();
  },
  substation(x) {   // Schaltfeld: Mast mit zwei Ausleger und Blitz
    x.fillStyle = '#fff'; x.fillRect(8, 44, 40, 5); x.fillRect(12, 14, 5, 30); x.fillRect(39, 14, 5, 30); x.fillRect(12, 14, 32, 5);
    x.beginPath(); [[30, 21], [21, 34], [27, 34], [24, 44], [35, 30], [29, 30]].forEach(([a, b], i) => (i ? x.lineTo(a, b) : x.moveTo(a, b))); x.closePath(); x.fill();
  },
  transformer(x) {   // zwei verschränkte Spulenkreise
    x.strokeStyle = '#fff'; x.lineWidth = 4.4;
    x.beginPath(); x.arc(21, 28, 12, 0, Math.PI * 2); x.stroke(); x.beginPath(); x.arc(35, 28, 12, 0, Math.PI * 2); x.stroke();
  },
};
function plaque(kind) {
  const c = document.createElement('canvas'); c.width = PX; c.height = PX;
  const x = c.getContext('2d', { willReadFrequently: true }); x.lineCap = 'round'; x.lineJoin = 'round';
  x.beginPath(); x.arc(28, 28, 26, 0, Math.PI * 2); x.fillStyle = '#fff'; x.fill();
  x.beginPath(); x.arc(28, 28, 23, 0, Math.PI * 2); x.fillStyle = ENERGIE_COLOR[kind]; x.fill();
  draw[kind](x);
  return x.getImageData(0, 0, PX, PX);
}
export function registerEnergie(map_) {
  for (const k of PLAQUE_KINDS) { const id = `en-${k}`, img = plaque(k); if (map_.hasImage(id)) map_.updateImage(id, img); else map_.addImage(id, img, { pixelRatio: 2 }); }
}

export const ENERGIE_LAYER_IDS = ['en-area-fill', 'en-area-line', 'en-line-casing', 'en-line', 'en-line-hit', 'en-sym'];
let key = '';

export function applyEnergie() {
  if (!mapReady || !state.energie) return;
  const k = `${state.energie.fetched_at}|${(state.energie.items ?? []).length}`;
  const f = energieFeatures(state.energie.items);
  if (map.getSource('energie-pts')) {
    if (k !== key) { map.getSource('energie-pts').setData(f.points); map.getSource('energie-areas').setData(f.areas); map.getSource('energie-lines').setData(f.lines); }
  } else {
    map.addSource('energie-pts', { type: 'geojson', data: f.points });
    map.addSource('energie-areas', { type: 'geojson', data: f.areas });
    map.addSource('energie-lines', { type: 'geojson', data: f.lines });
    const kv = (a, b, c) => ['match', ['get', 'kv'], 380, a, 220, b, c];
    const lineColor = ['match', ['get', 'kv'], 380, LINE_COLOR[380], 220, LINE_COLOR[220], LINE_COLOR[110]];
    const layout = { 'line-cap': 'round', 'line-join': 'round' };
    map.addLayer({ id: 'en-area-fill', type: 'fill', source: 'energie-areas', paint: { 'fill-color': ENERGIE_COLOR.solar, 'fill-opacity': ['match', ['get', 'state'], 'netz', 0.4, 0.18] } }, 'radius-fill');
    map.addLayer({ id: 'en-area-line', type: 'line', source: 'energie-areas', layout, paint: { 'line-color': ENERGIE_COLOR.solar, 'line-width': 1.2} }, 'radius-fill');
    map.addLayer({ id: 'en-line-casing', type: 'line', source: 'energie-lines', layout, paint: { 'line-color': '#ffffff', 'line-opacity': 0.85, 'line-width': ['interpolate', ['linear'], ['zoom'], 8, kv(3.6, 3.2, 2.8), 14, kv(6, 5.2, 4.4)] } }, 'radius-fill');
    map.addLayer({ id: 'en-line', type: 'line', source: 'energie-lines', layout, paint: { 'line-color': lineColor, 'line-width': ['interpolate', ['linear'], ['zoom'], 8, kv(1.8, 1.5, 1.1), 14, kv(3.4, 2.8, 2.2)] } }, 'radius-fill');
    map.addLayer({ id: 'en-line-hit', type: 'line', source: 'energie-lines', layout, paint: { 'line-color': '#000000', 'line-opacity': 0.01, 'line-width': 14 } }, 'radius-fill');
    map.addLayer({ id: 'en-sym', type: 'symbol', source: 'energie-pts', minzoom: 9.5,
      layout: { 'icon-image': ['concat', 'en-', ['get', 'kind']], 'icon-size': ['interpolate', ['linear'], ['zoom'], 9.5, 0.5, 14, 0.8], 'icon-allow-overlap': false, 'icon-padding': 2,
        'symbol-sort-key': ['match', ['get', 'kind'], 'plant', 0, 'substation', 1, 'transformer', 2, 3],
        'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': 11, 'text-offset': [0, 1.2], 'text-anchor': 'top', 'text-max-width': 9, 'text-optional': true },
      paint: { 'text-color': '#1c1c1c', 'text-halo-color': '#fff', 'text-halo-width': 1.8, 'text-opacity': ['step', ['zoom'], 0, 12, 1] } }, 'radius-fill');
  }
  key = k;
  applyEnergieVisibility();
}

export function applyEnergieVisibility() {
  if (!mapReady || !map.getLayer('en-sym')) return;
  const kinds = energieKinds(state.layers, !!state.layers.medieval), vis = (on) => (on ? 'visible' : 'none');
  const has = (kind) => kinds.includes(kind);
  for (const id of ['en-area-fill', 'en-area-line']) map.setLayoutProperty(id, 'visibility', vis(has('solar')));
  for (const id of ['en-line-casing', 'en-line', 'en-line-hit']) map.setLayoutProperty(id, 'visibility', vis(has('line')));
  const pointKinds = kinds.filter((x) => x !== 'line');
  map.setLayoutProperty('en-sym', 'visibility', vis(pointKinds.length > 0));
  map.setFilter('en-sym', ['in', ['get', 'kind'], ['literal', pointKinds]]);
}
