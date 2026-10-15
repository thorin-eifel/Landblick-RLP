import assert from 'node:assert/strict';
import { test } from 'node:test';
globalThis.window ??= globalThis;
const { BUNDLED, cleanFontName, fontFaces, queryLocalFamilies, setLocalNames } = await import('../../web/js/lage/schrift.js');
import { existsSync } from 'node:fs';

test('jede mitgelieferte Schrift hat ihre Datei', () => {
  for (const b of BUNDLED) if (b.file) assert.ok(existsSync(new URL(`../../web/fonts/woff2/${b.file}`, import.meta.url)), b.file);
});
test('fontFaces: absolute URLs je Schrift, Noto Sans bleibt bei den PBF', () => {
  const f = fontFaces('http://x.test/app/');
  assert.equal(f.Cinzel[0].url, 'http://x.test/app/fonts/woff2/cinzel.woff2');
  assert.equal(f['Noto Sans Regular'], undefined);
});
test('cleanFontName entfernt Trenner und Steuerzeichen, begrenzt die Länge', () => {
  assert.equal(cleanFontName('  Fira,  Sans\n'), 'Fira Sans');
  assert.equal(cleanFontName('a'), '');
  assert.equal(cleanFontName('x'.repeat(81)), '');
});
test('setLocalNames: ohne Doppelte und ohne Mitgelieferte, sortiert', () => {
  assert.deepEqual(setLocalNames(['Zapfino', 'cinzel', 'Arial', 'arial', 'Lora']), ['Arial', 'Zapfino']);
});
test('queryLocalFamilies: Familien einmalig; ohne API ein Fehler', async () => {
  assert.deepEqual(await queryLocalFamilies(async () => [{ family: 'B' + 'b' }, { family: 'Bb' }, { family: 'Aa' }]), ['Aa', 'Bb']);
  await assert.rejects(queryLocalFamilies(undefined));
});
