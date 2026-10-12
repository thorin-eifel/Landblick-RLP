// Übersichtskarte: Ortsnamen in Rheinland-Pfalz alle, außerhalb nur Städte über 80.000 Einwohner.
import test from 'node:test';
import assert from 'node:assert/strict';

globalThis.window ??= globalThis;
globalThis.devicePixelRatio ??= 1;
const { ortsnamenUebersicht, FREMD_MIN_EINWOHNER } = await import('../../web/js/lage/stil.js');
const { RLP_UMRISS } = await import('../../web/js/lage/rlp-umriss.js');

const basis = { id: 'places_locality', type: 'symbol', source: 'basemap', 'source-layer': 'places', filter: ['==', ['get', 'kind'], 'locality'], layout: {}, paint: {} };

test('places_locality wird zu Detailebene ab Zoom 9 und Übersichtsebene Zoom 5 bis 9', () => {
  const [detail, ov] = ortsnamenUebersicht(basis);
  assert.equal(detail.id, 'places_locality');
  assert.equal(detail.minzoom, 9);
  assert.equal(detail.filter, basis.filter, 'ab Zoom 9 kein Unterschied, kein Irrel-Ausschluss');
  assert.equal(ov.id, 'places_locality_ov');
  assert.equal(ov.minzoom, 5);
  assert.equal(ov.maxzoom, 9);
  const any = ov.filter[2];
  assert.equal(any[0], 'any');
  assert.equal(any[1][0], 'within');
  assert.equal(any[1][1], RLP_UMRISS);
  assert.equal(any[2][2] !== undefined && any[2][2], FREMD_MIN_EINWOHNER);
});

test('andere Ebenen bleiben unverändert', () => {
  const x = { id: 'roads_labels_major' };
  assert.deepEqual(ortsnamenUebersicht(x), [x]);
});

test('Umriss: Trier, Mainz und Irrel liegen darin, Saarbrücken, Luxemburg und Köln nicht', () => {
  const inside = (lon, lat) => RLP_UMRISS.coordinates.some(([ring]) => {
    let c = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) c = !c;
    }
    return c;
  });
  for (const [n, lon, lat] of [['Trier', 6.64, 49.75], ['Mainz', 8.27, 50.0], ['Irrel', 6.45, 49.85], ['Koblenz', 7.59, 50.36]]) assert.ok(inside(lon, lat), n);
  for (const [n, lon, lat] of [['Saarbrücken', 7.0, 49.23], ['Luxemburg', 6.13, 49.61], ['Köln', 6.96, 50.94], ['Echternach', 6.42, 49.81]]) assert.ok(!inside(lon, lat), n);
});
