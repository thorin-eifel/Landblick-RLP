import test from 'node:test';
import assert from 'node:assert/strict';

globalThis.window ??= globalThis;
globalThis.devicePixelRatio ??= 1;
const { PALETTE, LAND_CLASSES, prng, LP } = await import('../../web/js/vegetation.js');
const { LAND, LAND_KINDS } = await import('../../web/js/lage/stil.js');

test('jede Vegetationsklasse hat Muster, Palette und Flächenfarbe in hell und dunkel', () => {
  for (const cls of Object.keys(LAND_KINDS)) {
    assert.ok(LAND_CLASSES.includes(cls), `Muster fehlt: ${cls}`);
    for (const lv of ['light', 'dark']) {
      assert.ok(PALETTE[lv][cls], `Palette fehlt: ${cls}/${lv}`);
      assert.ok(LAND[lv][cls], `Flächenfarbe fehlt: ${cls}/${lv}`);
    }
  }
  assert.deepEqual(Object.keys(PALETTE.light).sort(), Object.keys(PALETTE.dark).sort());
});

test('Zufallsfolge ist je Saatkorn stabil', () => {
  const a = prng(42), b = prng(42), c = prng(43);
  const sa = Array.from({ length: 5 }, a), sb = Array.from({ length: 5 }, b), sc = Array.from({ length: 5 }, c);
  assert.deepEqual(sa, sb);
  assert.notDeepEqual(sa, sc);
  assert.ok(sa.every((v) => v >= 0 && v < 1));
});

test('Musterkachel hat Größe 64', () => assert.equal(LP, 64));
