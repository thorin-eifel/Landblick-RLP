import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

// Jedes Zeichen, das Oberfläche oder Karte anfordert, muss als Datei im Repository liegen. Bis Oktober 2026 kamen die meisten
// von uxwing und waren nicht versioniert: in den Installern fehlten sie, ohne dass ein Test es bemerkte.
const datei = (name) => new URL(`../../web/icons/${name}.svg`, import.meta.url);
const { CHIP_ICONS, NATURE_CHIP } = await import('../../web/js/icons.js');

test('Zeichen der Karte (Plaketten, Flugzeug, Landmarken) liegen in web/icons', () => {
  const namen = new Set([...CHIP_ICONS, 'flug', 'hubschrauber', 'tanken', ...Object.values(NATURE_CHIP).map(([g]) => g)]);
  for (const n of namen) assert.ok(existsSync(datei(n)), `fehlt: web/icons/${n}.svg`);
});

test('Zeichen aus iconFor (rules.js) liegen in web/icons', () => {
  const src = readFileSync(new URL('../../web/js/rules.js', import.meta.url), 'utf8');
  const block = src.slice(src.indexOf('export function iconFor'), src.indexOf('export function advance'));
  const namen = new Set([...block.matchAll(/'([a-z]+)'/g)].map((m) => m[1]).filter((n) => !['aircraft', 'congestion', 'flood', 'radiation', 'air', 'earthquake', 'fire', 'transit', 'traffic'].includes(n)));
  assert.ok(namen.size >= 8);
  for (const n of namen) assert.ok(existsSync(datei(n)), `fehlt: web/icons/${n}.svg`);
});

test('Klassen .ico-* in icons.css zeigen auf vorhandene Dateien', () => {
  const css = readFileSync(new URL('../../web/css/icons.css', import.meta.url), 'utf8');
  const namen = [...css.matchAll(/url\(\.\.\/icons\/([\w-]+)\.svg\)/g)].map((m) => m[1]);
  assert.ok(namen.length >= 20);
  for (const n of namen) assert.ok(existsSync(datei(n)), `fehlt: web/icons/${n}.svg`);
});
