import test from 'node:test';
import assert from 'node:assert/strict';

const { roemisch } = await import('../../web/js/medieval.js');

test('Jahreszahlen in römischen Ziffern', () => {
  assert.equal(roemisch(2026), 'MMXXVI');
  assert.equal(roemisch(2027), 'MMXXVII');
  assert.equal(roemisch(2049), 'MMXLIX');
  assert.equal(roemisch(1999), 'MCMXCIX');
  assert.equal(roemisch(1450), 'MCDL');
  assert.equal(roemisch(3999), 'MMMCMXCIX');
});

test('außerhalb 1 bis 3999 bleibt die arabische Zahl stehen', () => {
  assert.equal(roemisch(0), '0');
  assert.equal(roemisch(4000), '4000');
});
