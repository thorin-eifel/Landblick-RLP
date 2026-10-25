import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ENERGIE_SWITCH, energieAn, energieFeatures, energieKinds, energieText } from '../../web/js/energie.js';
import { infraFeatures, infraText } from '../../web/js/infra.js';

test('energieKinds folgt den Schaltern und schweigt auf der Karte um 1450', () => {
  assert.deepEqual(energieKinds({ enLine: true, enSub: true }), ['substation', 'line']);
  assert.deepEqual(energieKinds({ enLine: true }, true), []);
  assert.equal(energieAn({}), false);
  assert.equal(energieAn({ enSolar: true }), true);
  assert.equal(Object.keys(ENERGIE_SWITCH).length, 5);
});

test('energieFeatures trennt Zeichen, Flächen und Linien', () => {
  const ring = [[6.4, 49.8], [6.5, 49.8], [6.5, 49.9], [6.4, 49.8]];
  const f = energieFeatures([
    { id: 'a', kind: 'solar', lat: 49.84, lon: 6.45, ring, state: 'netz', kw: 2500, ha: 3.2, src: 'rok' },
    { id: 'b', kind: 'substation', lat: 49.8, lon: 6.4, kv: 380, name: 'Umspannwerk X' },
    { id: 'c', kind: 'line', kv: 220, lines: [[[6.1, 49.8], [6.9, 49.8]]] },
    { id: 'd', kind: 'plant', lat: 'x', lon: 6 },
  ]);
  assert.equal(f.points.features.length, 2);
  assert.equal(f.areas.features.length, 1);
  assert.equal(f.lines.features.length, 1);
  assert.equal(f.lines.features[0].properties.kv, 220);
});

test('energieText nennt Art, Sachwerte und Stand', () => {
  assert.equal(energieText({ kind: 'line', kv: 380 }), 'Hochspannungsleitung · 380 kV');
  assert.equal(energieText({ kind: 'plant', source: 'gas', kw: 120000, name: 'Gaskraftwerk X' }), 'Kraftwerk (Gas) · Gaskraftwerk X · 120 MW');
  assert.match(energieText({ kind: 'solar', state: 'genehmigt', ha: 3.2, kw: 2500, place: 'Irrel' }), /Solarpark · 2,5 MW · 3,2 ha · genehmigt, nicht gebaut · Irrel/);
});

test('Windräder tragen Stand und Maße in Karte und Popup', () => {
  const f = infraFeatures([{ id: 'rok/wind/1', kind: 'wind', lat: 49.8, lon: 6.4, state: 'beantragt', kw: 6000, hub: 160, top: 240, place: 'Irrel' }]);
  assert.equal(f.features[0].properties.plan, 1);
  assert.equal(infraText(f.features[0].properties), 'Windrad · 6 MW · beantragt · Nabe 160 m · Gesamthöhe 240 m · Irrel');
  assert.equal(infraFeatures([{ id: 'n', kind: 'wind', lat: 49.8, lon: 6.4 }]).features[0].properties.plan, 0);
});
