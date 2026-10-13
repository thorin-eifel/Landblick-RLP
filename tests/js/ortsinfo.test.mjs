// Tests für web/js/ortsinfo.js (Auskunft zu einem Kartenpunkt).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { dezimalGrad, entfernung, entpacke, finde, gradMinutenSekunden, imGeoJson, imRing, ringAusDeltas, utm } from '../../web/js/ortsinfo.js';

const quadrat = (x0, y0, s) => [x0, y0, x0 + s, y0, x0 + s, y0 + s, x0, y0 + s];

test('Punkt im Ring, auch im Loch des GeoJSON', () => {
  assert.ok(imRing(quadrat(0, 0, 10), 5, 5));
  assert.ok(!imRing(quadrat(0, 0, 10), 11, 5));
  const geom = { type: 'Polygon', coordinates: [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]] };
  assert.ok(imGeoJson(geom, 1, 1));
  assert.ok(!imGeoJson(geom, 5, 5));
});

test('Deltas werden zu Grad', () => {
  assert.deepEqual(ringAusDeltas([645000, 4984000, 100, -50, -100, 0], 100000), [6.45, 49.84, 6.451, 49.8395, 6.45, 49.8395]);
});

test('UTM stimmt mit dem Wohnplatzverzeichnis überein (Irrel: 32317140 5524685)', () => {
  const u = utm(49.84666, 6.45642);
  assert.equal(u.zone, 32); assert.equal(u.band, 'U');
  assert.ok(Math.abs(u.east - 317140) < 15 && Math.abs(u.north - 5524685) < 15, u.text);
});

test('UTM am Zonenrand und Rechenfall Greenwich/Äquator', () => {
  const m = utm(0, 9);              // Mittelmeridian der Zone 32
  assert.equal(m.east, 500000); assert.equal(m.north, 0);
});

test('Koordinaten lesbar', () => {
  assert.equal(dezimalGrad(49.85, 6.45), '49,85000° N, 6,45000° O');
  assert.equal(gradMinutenSekunden(49.85, 'N', 'S'), '49° 51′ 00,0″ N');
  assert.ok(Math.abs(entfernung(6.45, 49.85, 6.46, 49.85) - 716) < 5);
});

const v = entpacke({
  scale: 100000, vg: [{ c: '1', n: 'Südeifel' }], kreise: { 20: 'Eifelkreis' },
  gemeinden: [
    { c: 'a', n: 'Irrel', vg: 0, k: '20', r: [[645000, 4984000, 1000, 0, 0, 1000, -1000, 0]] },
    { c: 'b', n: 'Freie Gemeinde', vg: -1, k: '20', r: [[646100, 4984000, 1000, 0, 0, 1000, -1000, 0]] },
  ],
  orte: [['Irrel', 645500, 4984500, 0, 1], ['Hof', 645100, 4984100, 0, 0], ['Dorf', 646600, 4984500, 1, 1]],
});

test('Gemeinde, Verbandsgemeinde, Kreis, Ort', () => {
  const r = finde(v, null, 6.4505, 49.8405);
  assert.deepEqual([r.gemeinde, r.vg, r.kreis, r.ort], ['Irrel', 'Südeifel', 'Eifelkreis', 'Irrel']);
  assert.ok(r.ortAbstand > 400 && r.ortAbstand < 800, String(r.ortAbstand));
});

test('Ort ist der nächste Ortsteil, Wohnplätze (Höfe) zählen nicht', () => {
  assert.equal(finde(v, null, 6.4501, 49.8401).ort, 'Irrel');      // Hof liegt näher, ist aber kein Ortsteil
});

test('verbandsfreie Gemeinde ohne Verbandsgemeinde', () => {
  const r = finde(v, null, 6.4615, 49.8405);
  assert.equal(r.gemeinde, 'Freie Gemeinde'); assert.equal(r.vg, null); assert.equal(r.ort, 'Dorf');
});

test('außerhalb: nur Kreis aus den Kreisflächen, sonst nichts', () => {
  const kreise = { features: [{ properties: { name: 'Kreis Merzig-Wadern' }, geometry: { type: 'Polygon', coordinates: [[[6.5, 49.4], [6.9, 49.4], [6.9, 49.6], [6.5, 49.6], [6.5, 49.4]]] } }] };
  assert.deepEqual(finde(v, kreise, 6.7, 49.5), { gemeinde: null, vg: null, kreis: 'Kreis Merzig-Wadern', ort: null, ortAbstand: null });
  assert.deepEqual(finde(null, null, 1, 1), { gemeinde: null, vg: null, kreis: null, ort: null, ortAbstand: null });
});

test('echte Datei (wenn gebaut): Irrel liegt in Irrel, Südeifel, Eifelkreis Bitburg-Prüm', { skip: !existsSync(new URL('../../web/geo/verwaltung.json', import.meta.url)) }, () => {
  const d = entpacke(JSON.parse(readFileSync(new URL('../../web/geo/verwaltung.json', import.meta.url))));
  const r = finde(d, null, 6.4564, 49.8467);
  assert.deepEqual([r.gemeinde, r.vg, r.kreis, r.ort], ['Irrel', 'Südeifel', 'Eifelkreis Bitburg-Prüm', 'Irrel']);
});
