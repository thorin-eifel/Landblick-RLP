import assert from 'node:assert/strict';
import { test } from 'node:test';
import { LAND_GROUP, SKINS, roadClass, scaleWidth, skinById, skinize, tintOf, wantsPatterns } from '../../web/js/lage/skins.js';

const KEYS = ['bg', 'earth', 'water', 'edge', 'waterInk', 'ink', 'halo', 'forest', 'green', 'scrub', 'farm', 'wet', 'rock', 'landOp', 'bld', 'roads'];

test('jeder Skin hat eindeutige Kennung und Namen', () => {
  assert.equal(new Set(SKINS.map((s) => s.id)).size, SKINS.length);
  assert.ok(SKINS.every((s) => s.name && s.hinweis));
  assert.equal(skinById('gibt-es-nicht').id, 'landblick');
});

test('Paletten sind vollständig, hell und dunkel', () => {
  for (const s of SKINS.filter((x) => x.tint)) for (const m of ['light', 'dark']) {
    const p = s.tint[m];
    for (const k of KEYS) assert.ok(p[k] !== undefined, `${s.id}/${m}: ${k}`);
    for (const c of ['hw', 'major', 'mid', 'minor', 'other']) assert.equal(p.roads[c].length, 2, `${s.id}/${m}: ${c}`);
    assert.ok(p.roads.rail);
  }
});

test('Landblick und Alte Karte haben keine Palette', () => {
  assert.equal(tintOf('landblick', false), null);
  assert.equal(tintOf('alte-karte', true), null);
  assert.ok(tintOf('amsterdam', true));
});

test('Straßenklassen der Stilebenen', () => {
  assert.deepEqual(roadClass('roads_bridges_highway_casing'), { cls: 'hw', casing: true });
  assert.deepEqual(roadClass('roads_major_casing_late'), { cls: 'major', casing: true });
  assert.deepEqual(roadClass('roads_tunnels_minor'), { cls: 'minor', casing: false });
  assert.deepEqual(roadClass('roads_minor_service'), { cls: 'minor', casing: false });
  assert.equal(roadClass('roads_labels_major'), null);
});

test('skinize färbt Boden, Wasser, Straße, Kontur, Bewuchs und Schrift um', () => {
  const p = tintOf('mountain-view', false);
  const styled = [
    { id: 'background', type: 'background', paint: { 'background-color': '#000' } },
    { id: 'water', type: 'fill', paint: { 'fill-color': '#000' } },
    { id: 'roads_major', type: 'line', paint: { 'line-color': '#000', 'line-width': 3 } },
    { id: 'roads_major_casing_late', type: 'line', paint: { 'line-color': '#000' } },
    { id: 'land-forest', type: 'fill', paint: { 'fill-color': '#000', 'fill-opacity': 0.1 } },
    { id: 'land-forest-pat', type: 'fill', paint: {} },
    { id: 'water_label_lakes', type: 'symbol', layout: { 'text-font': ['x'] }, paint: { 'text-color': '#000' } },
    { id: 'places_locality', type: 'symbol', layout: { 'text-font': ['x'] }, paint: {} },
  ];
  const out = skinize(styled, p, { patterns: false });
  const by = Object.fromEntries(out.map((l) => [l.id, l]));
  assert.equal(by.background.paint['background-color'], p.bg);
  assert.equal(by.water.paint['fill-color'], p.water);
  assert.equal(by.roads_major.paint['line-color'], p.roads.major[0]);
  assert.equal(by.roads_major.paint['line-width'], 3);
  assert.equal(by.roads_major_casing_late.paint['line-color'], p.roads.major[1]);
  assert.equal(by['land-forest'].paint['fill-color'], p.forest);
  assert.equal(by['land-forest'].paint['fill-opacity'], p.landOp);
  assert.equal(by['land-forest-pat'], undefined);
  assert.equal(by.water_label_lakes.paint['text-color'], p.waterInk);
  assert.equal(by.places_locality.paint['text-color'], p.ink);
  assert.equal(styled[0].paint['background-color'], '#000', 'Eingabe bleibt unverändert');
});

test('Signaturen nur dort, wo der Skin sie will', () => {
  assert.equal(wantsPatterns('landblick'), true);
  assert.equal(wantsPatterns('olathe'), true);
  assert.equal(wantsPatterns('cupertino'), false);
});

test('Bewuchsklassen sind abgebildet', () => {
  for (const g of Object.values(LAND_GROUP)) assert.ok(KEYS.includes(g));
});

test('Farbpalette mit feiner Linie (inkRoads): Straßen ohne Kontur, Nebenwege gestrichelt', () => {
  const p = { ...tintOf('mountain-view', false), inkRoads: 0.42, spacing: 0.12 };
  const w = ['interpolate', ['exponential', 1.6], ['zoom'], 6, 1.2, 15, 7];
  const out = skinize([
    { id: 'roads_minor_casing', type: 'line', paint: { 'line-width': 1 } },
    { id: 'roads_minor', type: 'line', paint: { 'line-width': w } },
    { id: 'roads_highway', type: 'line', paint: { 'line-width': w } },
    { id: 'places_locality', type: 'symbol', layout: { 'text-font': ['x'] }, paint: {} },
  ], p);
  const by = Object.fromEntries(out.map((l) => [l.id, l]));
  assert.equal(by.roads_minor_casing.paint['line-opacity'], 0);
  assert.deepEqual(by.roads_minor.paint['line-dasharray'], [6, 2]);
  assert.equal(by.roads_highway.paint['line-dasharray'], undefined);
  assert.ok(Math.abs(by.roads_highway.paint['line-width'][4] - 1.2 * p.inkRoads) < 1e-9);
  assert.equal(by.places_locality.layout['text-letter-spacing'], p.spacing);
});

test('scaleWidth: Zahl, Zoom-Ausdruck und sonstiger Ausdruck', () => {
  assert.equal(scaleWidth(2, 0.5), 1);
  assert.deepEqual(scaleWidth(['interpolate', ['linear'], ['zoom'], 5, 2, 10, 4], 0.5), ['interpolate', ['linear'], ['zoom'], 5, 1, 10, 2]);
  assert.deepEqual(scaleWidth(['get', 'w'], 0.5), ['*', 0.5, ['get', 'w']]);
});
