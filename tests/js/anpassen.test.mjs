import assert from 'node:assert/strict';
import { test } from 'node:test';
import { FARBFELDER, baueEigenenSkin, eigenePalette, eigenerZeichensatz, farbenVon, gueltigeFarbe, tone } from '../../web/js/lage/anpassen.js';
import { ARTS, ART_KEYS } from '../../web/js/lage/zeichensaetze.js';
import { SCHEMATA, SYMBOLSAETZE, effektiverSkin, setEigenerSkin, skinById, tintOf } from '../../web/js/lage/skins.js';

test('gueltigeFarbe: nur #rrggbb', () => {
  assert.ok(gueltigeFarbe('#a1B2c3'));
  for (const v of ['red', '#abc', 'url(x)', '#12345g', '', null, 5]) assert.equal(gueltigeFarbe(v), false, String(v));
});
test('tone dunkelt ab und klemmt', () => {
  assert.equal(tone('#808080', 0.5), '#404040');
  assert.equal(tone('#f0f0f0', 2), '#ffffff');
});
test('Schemata und Symbolsätze: Grundzeichnung dabei, Zeichensätze nur bei Symbolen', () => {
  assert.ok(SCHEMATA.some((s) => s.id === 'landblick') && SCHEMATA.every((s) => !s.art));
  assert.deepEqual(SYMBOLSAETZE.map((s) => s.id), ['landblick', 'alte-karte', 'oxford']);
});
test('effektiverSkin: Symbolsatz geht vor Schema, eigen nur wenn gesetzt', () => {
  assert.equal(effektiverSkin('cupertino', 'landblick'), 'cupertino');
  assert.equal(effektiverSkin('cupertino', 'oxford'), 'oxford');
  assert.equal(effektiverSkin('cupertino', 'landblick', true), 'cupertino');   // noch kein eigener Skin registriert
  setEigenerSkin({ name: 'x', tint: null });
  assert.equal(effektiverSkin('cupertino', 'landblick', true), 'eigen');
  setEigenerSkin(null);
});
test('eigenePalette überschreibt nur gültige Felder und leitet Konturen ab', () => {
  const base = tintOf('mountain-view', false);
  const p = eigenePalette(base, { water: '#336699', forest: 'rot', roadMajor: '#ff0000' });
  assert.equal(p.water, '#336699');
  assert.equal(p.forest, base.forest);
  assert.equal(p.roads.hw[0], '#ff0000');
  assert.notEqual(p.roads.hw[1], base.roads.hw[1]);
  assert.equal(base.water, tintOf('mountain-view', false).water, 'Ausgang bleibt unverändert');
});
test('eigenerZeichensatz bleibt vollständig und setzt Papier, Tinte, Schalter', () => {
  const a = eigenerZeichensatz('alte-karte', { paper: '#ffffff', ink: '#000000', evil: '#123456' }, { decor: false, fauna: true });
  for (const k of ART_KEYS) assert.ok(a[k] !== undefined, k);
  assert.equal(a.med.paper, '#ffffff'); assert.equal(a.zeichen.ink, '#000000');
  assert.equal(a.decor, false); assert.equal(a.fauna, true);
  assert.equal(ARTS['alte-karte'].med.paper, '#e8d6a6', 'Vorlage unverändert');
});
test('baueEigenenSkin: Palette ohne Symbolsatz, Zeichensatz mit', () => {
  const eigen = { farben: { light: { bg: '#101010' }, dark: {} }, art: { ink: '#222222' }, patterns: true, decor: null, fauna: null };
  const t = baueEigenenSkin('landblick', 'landblick', eigen);
  assert.equal(t.art, null); assert.equal(t.skin.tint.light.bg, '#101010'); assert.equal(t.skin.tint.patterns, true);
  const z = baueEigenenSkin('landblick', 'oxford', eigen);
  assert.equal(z.skin.art, 'eigen'); assert.equal(z.skin.dunkel, false); assert.equal(z.art.med.ink, '#222222');
});
test('farbenVon deckt alle Formularfelder', () => {
  const t = farbenVon('tint', tintOf('olathe', false));
  for (const [k] of FARBFELDER.tint) assert.ok(gueltigeFarbe(t[k]), k);
  const a = farbenVon('art', 'federzeichnung');
  for (const [k] of FARBFELDER.art) assert.ok(gueltigeFarbe(a[k]), k);
  assert.ok(skinById('gibt-es-nicht'));
});
