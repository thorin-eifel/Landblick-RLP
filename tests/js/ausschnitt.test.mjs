import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ereignisseImAusschnitt, grenzenVon, imAusschnitt, stationenImAusschnitt } from '../../web/js/lage/ausschnitt.js';

const B = { w: 6.0, s: 49.5, e: 6.5, n: 50.0 };
test('imAusschnitt: innen, Rand, außen', () => {
  assert.ok(imAusschnitt(B, 6.2, 49.8));
  assert.ok(imAusschnitt(B, 6.0, 49.5) && imAusschnitt(B, 6.5, 50.0));
  assert.equal(imAusschnitt(B, 6.6, 49.8), false);
  assert.equal(imAusschnitt(B, 6.2, 50.1), false);
});
test('ohne Ausschnitt bleibt alles sichtbar, ohne Koordinaten nur dann', () => {
  assert.ok(imAusschnitt(null, 0, 0));
  assert.ok(imAusschnitt(null, undefined, undefined));
  assert.equal(imAusschnitt(B, undefined, 49.8), false);
});
test('Ereignisse und Stationen werden gefiltert', () => {
  const ev = [{ properties: { lon: 6.2, lat: 49.8 } }, { properties: { lon: 7.5, lat: 49.8 } }, { properties: {} }];
  assert.equal(ereignisseImAusschnitt(ev, B).length, 1);
  assert.equal(stationenImAusschnitt([{ lon: 6.1, lat: 49.6 }, { lon: 9, lat: 50 }], B).length, 1);
  assert.equal(ereignisseImAusschnitt(ev, null).length, 3);
});
test('grenzenVon liest MapLibre-Bounds', () => {
  const b = { getWest: () => 1, getSouth: () => 2, getEast: () => 3, getNorth: () => 4 };
  assert.deepEqual(grenzenVon(b), { w: 1, s: 2, e: 3, n: 4 });
  assert.equal(grenzenVon(null), null);
});
