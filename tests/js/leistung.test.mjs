import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Messlauf, kurzfassung, perzentil } from '../../web/js/leistung.js';

test('Perzentil: nächster Rang, leer ergibt null', () => {
  assert.equal(perzentil([], 95), null);
  assert.equal(perzentil([10, 20, 30, 40], 50), 20);
  assert.equal(perzentil([1, 2, 3, 4, 5, 6, 7, 8, 9, 100], 95), 100);
  assert.equal(perzentil([5], 95), 5);
});

test('Messlauf: Nachladen zählt ab der letzten Eingabe, Kacheln je Quelle, langsamste zuerst', () => {
  const m = new Messlauf(0);
  m.eingabe(400);
  for (const f of [16, 17, 18, 40]) m.frame(f);
  m.kachelStart('basemap', '14/1/1', 100); m.kachelFertig('basemap', '14/1/1', 700);
  m.kachelStart('contours', '14/1/1', 100); m.kachelFertig('contours', '14/1/1', 1300);
  m.kachelStart('hang', '14/2/2', 200);                       // nie fertig: zählt als offen
  m.kachelFertig('basemap', 'nie/gestartet', 900);              // ohne Start: wird übergangen
  m.fehlerVon('basemap', 'Bad response code: 404');
  const e = m.ende(1500, { zoom: 14 });
  assert.equal(e.dauer_ms, 1500); assert.equal(e.nachladen_ms, 1100);
  assert.equal(e.frames, 4); assert.equal(e.frame_max_ms, 40); assert.equal(e.ueber_30ms, 1);
  assert.equal(e.offen, 1);
  assert.deepEqual(e.quellen.map((q) => q.id), ['contours', 'basemap']);
  assert.equal(e.quellen[1].fehler, 1); assert.equal(e.quellen[1].kacheln, 1);
  assert.equal(e.zoom, 14);
});

test('Kurzfassung: grün nur, wenn Nachladen unter 1 s und Frame p95 unter 30 ms', () => {
  const gut = new Messlauf(0); gut.frame(16); assert.equal(kurzfassung(gut.ende(800)).ok, true);
  const langsam = new Messlauf(0); langsam.frame(16); assert.equal(kurzfassung(langsam.ende(1200)).ok, false);
  const ruckelt = new Messlauf(0); for (let i = 0; i < 20; i++) ruckelt.frame(45); assert.equal(kurzfassung(ruckelt.ende(500)).ok, false);
});
