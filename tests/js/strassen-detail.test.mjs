import assert from 'node:assert/strict';
import { test } from 'node:test';
globalThis.window ??= globalThis;
globalThis.devicePixelRatio ??= 1;
const { DETAIL_ZOOM, roadsFromDetail } = await import('../../web/js/lage/stil.js');

const roads = (id, extra = {}) => ({ id, type: 'line', source: 'basemap', 'source-layer': 'roads', ...extra });
const styled = [{ id: 'earth', type: 'fill', source: 'basemap', 'source-layer': 'earth' }, roads('roads_minor_casing'), roads('roads_minor'),
  roads('roads_labels_minor', { type: 'symbol', minzoom: 13 }), { id: 'buildings', type: 'fill', source: 'basemap', 'source-layer': 'buildings' }];

test('ohne Kern und Ring bleibt alles, wie es ist', () => {
  assert.deepEqual(roadsFromDetail(styled), styled);
});

test('jede Straßenebene bekommt Zwillinge hinter sich, das Original endet vor Zoom 14', () => {
  const out = roadsFromDetail(styled, { core: true, ring: true });
  assert.deepEqual(out.map((l) => l.id), ['earth', 'roads_minor_casing', 'roads_minor_casing_c', 'roads_minor_casing_r', 'roads_minor', 'roads_minor_c', 'roads_minor_r',
    'roads_labels_minor', 'roads_labels_minor_c', 'roads_labels_minor_r', 'buildings']);
  const by = Object.fromEntries(out.map((l) => [l.id, l]));
  assert.equal(by.roads_minor.maxzoom, DETAIL_ZOOM);
  assert.equal(by.roads_minor_c.source, 'basemap-core');
  assert.equal(by.roads_minor_r.source, 'basemap-ring');
  assert.equal(by.roads_minor_c.minzoom, DETAIL_ZOOM);
  assert.equal(by.roads_labels_minor_c.minzoom, 14, 'höherer Mindestzoom des Originals bleibt');
  assert.equal(by.earth.maxzoom, undefined);
});

test('nur Kern: kein Ringzwilling', () => {
  const ids = roadsFromDetail(styled, { core: true }).map((l) => l.id);
  assert.ok(ids.includes('roads_minor_c') && !ids.includes('roads_minor_r'));
});
