import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ARTS, ART_KEYS, artOf } from '../../web/js/lage/zeichensaetze.js';
import { SKINS } from '../../web/js/lage/skins.js';

test('jeder Zeichensatz führt alle Pflichtfelder', () => {
  for (const [id, a] of Object.entries(ARTS)) for (const k of ART_KEYS) assert.ok(a[k] !== undefined, `${id}: ${k}`);
});

test('Zeichensätze führen dieselben Schlüssel wie die Alte Karte (der Wechsel überschreibt alles)', () => {
  const ref = ARTS['alte-karte'];
  for (const [id, a] of Object.entries(ARTS)) {
    for (const k of ['med', 'zeichen', 'pig', 'colors', 'iconStyle', 'land', 'relief', 'flow', 'cliff']) assert.deepEqual(Object.keys(a[k]).sort(), Object.keys(ref[k]).sort(), `${id}.${k}`);
    assert.equal(a.ramp.length, ref.ramp.length, `${id}.ramp`);
  }
});

test('jeder Skin mit art verweist auf einen vorhandenen Zeichensatz und kennt nur hell', () => {
  for (const s of SKINS.filter((x) => x.art)) { assert.ok(artOf(s.art), s.id); assert.equal(s.dunkel, false, s.id); }
  assert.equal(artOf('gibt-es-nicht'), null);
});

test('Farbpalette und Zeichensatz sind zwei getrennte Wege', () => {
  assert.ok(SKINS.some((s) => s.tint && !s.art), 'reiner Farbtausch');
  assert.ok(SKINS.some((s) => s.art && !s.tint), 'reiner Zeichensatz');
});
