// Rechtsklick auf die Karte: kleines Fenster mit Höhe, Koordinaten, Ort, Gemeinde, Kreis (auf Touchgeräten: langes Drücken).
//
// Zweck:   Auskunft zum Punkt unter dem Zeiger. Höhe aus dem Geländemodell der Karte (relief.js), Namen aus geo/verwaltung.json
//          (tools/build_verwaltung.py) und geo/kreise.geojson; die Auswertung steht in js/ortsinfo.js.
// Datenschutz: Die Dateien werden beim ersten Aufruf vom eigenen Server geholt, die Abfrage läuft im Browser. Es gibt keine Anfrage an
//          Dritte, nichts wird gespeichert. "Koordinaten kopieren" schreibt nur auf Klick in die Zwischenablage.
// Grenzen: Gemarkung fehlt (kein offener Kleindatensatz; die Flurstückdaten des Landes sind über 1 GB). Außerhalb von Rheinland-Pfalz
//          gibt es nur Kreis und Koordinaten. Ohne verwaltung.json zeigt das Fenster Höhe, Koordinaten und, wo möglich, den Kreis.
// Tasten:  Escape schließt. Das Fenster ist ein Popup der Karte mit Schließen-Knopf und per Tab erreichbarem Kopierknopf.
import { Popup } from '../../vendor/maplibre-gl/maplibre-gl.js';
import { dezimalGrad, entpacke, finde, gradMinutenSekunden, utm } from '../ortsinfo.js';
import { elevationAt } from '../relief.js';
import { getJSON, h } from '../util.js';
import { map, popup as klickPopup, reliefOk } from './zustand.js';

const LANG_MS = 650, LANG_TOLERANZ_PX = 10;
let daten = null;      // Promise auf { v, kreise }
let fenster = null;

/** Beide Dateien einmal holen; fehlt eine, geht es mit der anderen weiter. */
function ladeDaten() {
  daten ??= Promise.all([
    getJSON('geo/verwaltung.json').then(entpacke).catch((e) => { console.warn('verwaltung.json:', e?.message ?? e); return null; }),
    getJSON('geo/kreise.geojson').catch((e) => { console.warn('kreise.geojson:', e?.message ?? e); return null; }),
  ]).then(([v, kreise]) => ({ v, kreise }));
  return daten;
}

const meter = (m) => (m >= 1000 ? `${(m / 1000).toFixed(1).replace('.', ',')} km` : `${Math.round(m / 10) * 10} m`);

function zeile(titel, wert) {
  return [h('dt', {}, titel), h('dd', {}, wert)];
}

export async function zeigeAuskunft(lngLat) {
  const { lng, lat } = lngLat;
  klickPopup?.remove();
  fenster?.remove();
  const hoehe = h('dd', { 'aria-live': 'polite' }, '…');
  const ortFeld = h('dd', {}, '…'), gemFeld = h('dd', {}, '…'), kreisFeld = h('dd', {}, '…');
  const u = utm(lat, lng);
  const dezimal = dezimalGrad(lat, lng);
  const kopierText = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
  const kopieren = h('button', { type: 'button', class: 'ev-link', onclick: async (e) => {
    try { await navigator.clipboard.writeText(kopierText); e.target.textContent = 'Kopiert'; } catch { e.target.textContent = 'Kopieren nicht möglich'; }
  } }, 'Koordinaten kopieren');
  const box = h('div', { class: 'pop ctx' },
    h('h3', {}, 'Punkt auf der Karte'),
    h('dl', { class: 'ctx-liste' },
      h('dt', {}, 'Höhe'), hoehe,
      h('dt', {}, 'Koordinaten'), h('dd', {}, dezimal, h('br'), h('span', { class: 'muted small' }, `${gradMinutenSekunden(lat, 'N', 'S')}, ${gradMinutenSekunden(lng, 'O', 'W')}`)),
      h('dt', {}, 'UTM'), h('dd', {}, `${u.text}`, h('span', { class: 'muted small' }, ' (ETRS89)')),
      h('dt', {}, 'Ort'), ortFeld,
      h('dt', {}, 'Gemeinde'), gemFeld,
      h('dt', {}, 'Kreis'), kreisFeld),
    h('p', { class: 'k' }, kopieren),
    h('p', { class: 'k', id: 'ctx-quelle' }, 'Höhe aus dem Geländemodell der Karte, ohne Gewähr.'));
  fenster = new Popup({ closeButton: true, maxWidth: '320px', className: 'ctx-pop' }).setLngLat([lng, lat]).setDOMContent(box).addTo(map);

  const [z, { v, kreise }] = await Promise.all([reliefOk ? elevationAt(lng, lat) : Promise.resolve(null), ladeDaten()]);
  hoehe.textContent = z === null ? 'nicht verfügbar' : `${z} m ü. NN`;
  const r = finde(v, kreise, lng, lat);
  ortFeld.textContent = r.ort ? `${r.ort}${r.ortAbstand > 500 ? ` (${meter(r.ortAbstand)} entfernt)` : ''}` : '–';
  gemFeld.textContent = r.gemeinde ? `${r.gemeinde}${r.vg ? `, Verbandsgemeinde ${r.vg}` : ''}` : v ? 'außerhalb von Rheinland-Pfalz' : 'nicht verfügbar';
  kreisFeld.textContent = r.kreis ?? '–';
  if (v?.attribution) box.querySelector('#ctx-quelle').textContent = `Höhe aus dem Geländemodell der Karte, ohne Gewähr. Verwaltung: ${v.attribution}`;
}

/** Einmal beim Start: Rechtsklick und langes Drücken. */
export function initKontext() {
  map.on('contextmenu', (e) => { e.preventDefault?.(); e.originalEvent?.preventDefault?.(); zeigeAuskunft(e.lngLat); });
  // Touch: ein Finger lang halten, ohne zu wischen oder zu zoomen
  let timer = null, start = null;
  const ab = () => { clearTimeout(timer); timer = null; };
  map.on('touchstart', (e) => {
    ab();
    if (e.originalEvent.touches.length !== 1) return;
    start = e.point;
    timer = setTimeout(() => { timer = null; zeigeAuskunft(e.lngLat); }, LANG_MS);
  });
  map.on('touchmove', (e) => { if (timer && start && Math.hypot(e.point.x - start.x, e.point.y - start.y) > LANG_TOLERANZ_PX) ab(); });
  for (const ev of ['touchend', 'touchcancel', 'zoomstart', 'dragstart']) map.on(ev, ab);
}
