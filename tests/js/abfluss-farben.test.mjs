// Tests für web/js/abfluss-farben.js (Ebene Starkregen und Abfluss: Klassen, Farben, Texte, Faustformel).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ABFLUSS_KLASSEN, KLASSE_FAKTOR, abflussFarbe, abflussPopup, abflussText, flaecheText, senkePopup, spitzenabfluss } from '../../web/js/abfluss-farben.js';

test('Klassen 0 bis 6 mit Farben für hell und dunkel', () => {
  assert.deepEqual(ABFLUSS_KLASSEN.map((c) => c.k), [0, 1, 2, 3, 4, 5, 6]);
  for (const c of ABFLUSS_KLASSEN) { assert.match(c.farbe.light, /^#[0-9a-f]{6}$/i); assert.match(c.farbe.dark, /^#[0-9a-f]{6}$/i); }
});

test('Ausdruck ordnet jede Klasse ihre Farbe zu, Standard ist die größte Klasse', () => {
  const e = abflussFarbe('light');
  assert.deepEqual(e.slice(0, 2), ['match', ['get', 'k']]);
  assert.equal(e[2], 0); assert.equal(e[3], ABFLUSS_KLASSEN[0].farbe.light);
  assert.equal(e.at(-1), ABFLUSS_KLASSEN.at(-1).farbe.light);
  assert.equal(e.length, 2 + 2 * 7 + 1);
});

test('Faktor und Klassenbeschriftung passen zusammen', () => {
  assert.equal(KLASSE_FAKTOR, 5);
  const py = readFileSync(new URL('../../tools/build_abfluss.py', import.meta.url), 'utf8');
  assert.match(py, /KLASSE_FAKTOR = 5\b/);
  assert.equal(ABFLUSS_KLASSEN[2].label, 'ab 25 ha');       // 1 · 5²
  assert.equal(ABFLUSS_KLASSEN[3].label, 'ab 1,25 km²');    // 1 · 5³ = 125 ha
  assert.equal(ABFLUSS_KLASSEN[6].label, 'ab 156 km²');     // 1 · 5⁶ = 15625 ha
});

test('Fläche und Abfluss lesbar', () => {
  assert.equal(flaecheText(12), '12 ha');
  assert.equal(flaecheText(340), '3,4 km²');
  assert.equal(abflussText(0.6), '600 l/s');
  assert.equal(abflussText(2.34), '2,3 m³/s');
});

test('Faustformel: 100 ha bei 50 mm/h und C 0,3 sind rund 4,2 m³/s', () => {
  assert.ok(Math.abs(spitzenabfluss(100) - 4.1667) < 0.01);
  assert.equal(spitzenabfluss(0), 0);
});

test('Popup: große Gebiete bekommen keine Faustformel, Senke nennt Durchlässe', () => {
  assert.match(abflussPopup({ ha: 12 }).zeilen[1], /Faustformel/);
  assert.match(abflussPopup({ ha: 5000 }).zeilen[1], /taugt die Faustformel nicht/);
  const s = senkePopup({ v: 1200, d: 85, ha: 14 });
  assert.match(s.zeilen[0], /1\.200 m³/); assert.match(s.zeilen[0], /0,9 m/); assert.match(s.zeilen[0], /1,4 ha/);
  assert.match(s.zeilen[1], /Durchlass/);
});
