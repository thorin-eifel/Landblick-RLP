import assert from 'node:assert/strict';
import { test } from 'node:test';
import { distance, formatArea, formatLength, messenFeatures, pathLength, polygonArea, selfIntersects, summary } from '../../web/js/messen.js';

const near = (a, b, tol) => assert.ok(Math.abs(a - b) <= tol, `${a} nicht innerhalb ${tol} von ${b}`);

test('Strecke: ein Breitengrad sind rund 111,2 km, zwei Orte rund 5 km auseinander (grobe Prüfung)', () => {
  near(distance([6.45, 49], [6.45, 50]), 111195, 100);
  near(distance([6.4529, 49.8514], [6.4163, 49.8113]), 5100, 300);  
  assert.equal(distance([6, 49], [6, 49]), 0);
});

test('Fläche: Quadrat von 1 km Kantenlänge bei 49,85° N ist rund 1 km²', () => {
  const lat = 49.85, dLat = 1000 / 111195, dLon = 1000 / (111195 * Math.cos((lat * Math.PI) / 180));
  const sq = [[6.4, lat], [6.4 + dLon, lat], [6.4 + dLon, lat + dLat], [6.4, lat + dLat]];
  near(polygonArea(sq), 1e6, 6000);
  near(pathLength(sq, true), 4000, 20);
  assert.equal(polygonArea(sq.slice(0, 2)), 0);
  assert.equal(polygonArea([...sq].reverse()), polygonArea(sq));   // Umlaufsinn egal
});

test('Selbstüberschneidung: Schleife ja, Quadrat und Dreieck nein', () => {
  assert.equal(selfIntersects([[0, 0], [2, 2], [2, 0], [0, 2]]), true);   // Schmetterling
  assert.equal(selfIntersects([[0, 0], [2, 0], [2, 2], [0, 2]]), false);
  assert.equal(selfIntersects([[0, 0], [2, 0], [1, 1]]), false);
});

test('Formate: Meter, Kilometer, Quadratmeter, Hektar, Quadratkilometer', () => {
  assert.equal(formatLength(842.4), '842 m');
  assert.equal(formatLength(1234), '1,23 km');
  assert.equal(formatLength(23456), '23,5 km');
  assert.equal(formatArea(8432), '8.432 m²');
  assert.equal(formatArea(123456), '12,3 ha (123.456 m²)');
  assert.equal(formatArea(2_500_000), '2,50 km² (250 ha)');
  assert.equal(formatLength(NaN), '–');
});

test('summary: leer, offen mit Vorschau, geschlossen mit Warnung', () => {
  assert.match(summary([], false).lines[0], /anklicken/);
  const open = summary([[6.4, 49.8], [6.41, 49.8], [6.41, 49.81]], false);
  assert.match(open.lines[0], /^Strecke:/);
  assert.ok(open.lines.some((l) => l.startsWith('Geschlossen:')));
  const bow = summary([[0, 0], [0.01, 0.01], [0.01, 0], [0, 0.01]], true);
  assert.match(bow.lines[0], /^Fläche:/);
  assert.match(bow.warn, /kreuzen/);
  assert.equal(summary([[0, 0], [1, 1]], true).closed, false);   // zwei Punkte schließen nichts
});

test('messenFeatures: offene Linie, geschlossene Fläche, Gummiband', () => {
  const p = [[6.4, 49.8], [6.41, 49.8], [6.41, 49.81]];
  const o = messenFeatures(p, false, [6.42, 49.82]);
  assert.equal(o.line.features[0].geometry.coordinates.length, 3);
  assert.equal(o.fill.features.length, 0);
  assert.equal(o.rubber.features.length, 1);
  assert.equal(o.labels.features.length, 2);
  const c = messenFeatures(p, true, [6.42, 49.82]);
  assert.equal(c.fill.features.length, 1);
  assert.equal(c.rubber.features.length, 0);
  assert.equal(c.labels.features.length, 3);   // inkl. Schlusskante
  assert.equal(c.points.features[0].properties.first, 1);
});
