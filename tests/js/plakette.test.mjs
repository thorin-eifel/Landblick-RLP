import test from 'node:test';
import assert from 'node:assert/strict';

// plakette.js importiert Karten-Module, die im Browser leben; für die reinen Funktionen genügt ein Stub von window
globalThis.window ??= { devicePixelRatio: 1 };
const { plakettenRadius, plaketteId, parsePlakette, zentriere, sevFarbe, textFarbe, PLAKETTE } = await import('../../web/js/lage/plakette.js');

test('Radius wächst mit n und bleibt begrenzt', () => {
  const { lo, hi } = PLAKETTE.kreis;
  assert.equal(plakettenRadius(1, lo, hi), lo);
  assert.equal(plakettenRadius(1e9, lo, hi), hi);
  assert.ok(plakettenRadius(93, lo, hi) > plakettenRadius(8, lo, hi));
  assert.equal(plakettenRadius(0, lo, hi), lo);
});

test('Bildname: Rundlauf, auch mit Leerzeichen in der Schrift', () => {
  const id = plaketteId(93, 'kreis', 'warning', 'Noto Sans Regular');
  assert.deepEqual(parsePlakette(id), { n: 93, ebene: 'kreis', stufe: 'warning', schrift: 'Noto Sans Regular' });
  assert.equal(parsePlakette('anderes|1|kreis||x'), null);
  assert.equal(parsePlakette('plakette|x|kreis||x'), null);
  assert.equal(parsePlakette('plakette|1|quark||x'), null);
});

test('zentriere legt die Tintenfläche auf den Mittelpunkt', () => {
  // Ziffern mit Unterlänge (Gotisch): Tinte reicht 3 px unter die Grundlinie
  const m = { actualBoundingBoxLeft: -1, actualBoundingBoxRight: 11, actualBoundingBoxAscent: 7, actualBoundingBoxDescent: -(-3) };
  const p = zentriere(m, 20, 20);
  const tinteOben = p.y - m.actualBoundingBoxAscent, tinteUnten = p.y + m.actualBoundingBoxDescent;
  assert.equal((tinteOben + tinteUnten) / 2, 20);
  const links = p.x - m.actualBoundingBoxLeft, rechts = p.x + m.actualBoundingBoxRight;
  assert.equal((links + rechts) / 2, 20);
});

test('Farben: Kontrast und unbekannte Stufe', () => {
  const c = { critical: 'r', warning: 'o', notice: 'y', info: 'b' };
  assert.equal(sevFarbe(c, 'warning'), 'o');
  assert.equal(sevFarbe(c, ''), 'b');
  assert.equal(textFarbe('warning'), '#111');
  assert.equal(textFarbe('critical'), '#fff');
});
