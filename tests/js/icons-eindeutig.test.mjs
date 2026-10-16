// Jedes Menüzeichen (Schalter in den Menüs, Reiter) kommt genau einmal vor; die Legende darf das Zeichen
// ihres Menüeintrags wiederholen, weil sie dasselbe erklärt. Die Dateien der Menüzeichen müssen im Repository liegen.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

const html = readFileSync(new URL('../../web/index.html', import.meta.url), 'utf8');
const css = readFileSync(new URL('../../web/css/icons.css', import.meta.url), 'utf8');
const zeilen = html.split('\n').filter((l) => !l.includes('legend-row') && /class="ico ico-[\w-]+/.test(l));

test('Menü- und Reiterzeichen sind eindeutig', () => {
  const nach = new Map();
  for (const l of zeilen) {
    const name = /class="ico (ico-[\w-]+)/.exec(l)[1];
    const wer = /data-layer="(\w+)"|id="([\w-]+)"/.exec(l);
    nach.set(name, [...(nach.get(name) ?? []), wer?.[1] ?? wer?.[2] ?? '?']);
  }
  const doppelt = [...nach].filter(([, v]) => v.length > 1).map(([k, v]) => `${k}: ${v.join(', ')}`);
  assert.deepEqual(doppelt, []);
  assert.ok(nach.size > 60, `nur ${nach.size} Zeichen gefunden`);
});

test('jede Menüzeichen-Klasse hat eine Datei im Repository', () => {
  for (const [, name] of css.matchAll(/\.ico-m-([\w-]+)\s*\{\s*--ico:\s*url\(\.\.\/icons\/menu\/([\w-]+)\.svg\)/g)) {
    assert.ok(existsSync(new URL(`../../web/icons/menu/${name}.svg`, import.meta.url)), `Datei fehlt: ${name}.svg`);
  }
  for (const l of zeilen) {
    const m = /ico-m-([\w-]+)/.exec(l);
    if (m) assert.match(css, new RegExp(`\\.ico-m-${m[1]}\\s*\\{`), `CSS fehlt: ico-m-${m[1]}`);
  }
});
