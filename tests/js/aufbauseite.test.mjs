// Wann die Desktop-App von der Karte auf die Aufbauseite führt. Der Fall, der hier zählt: erster Start, die Quellen
// werden noch abgerufen — die Karte stand dann zwar offen, zeigte aber nur „Die Datendateien konnten nicht geladen werden“.
import test from 'node:test';
import assert from 'node:assert/strict';

const { zurAufbauseite } = await import('../../web/js/desktop-gate.js');

const zustand = (phase, daten) => ({ configured: true, daten, job: { phase, msg: '', pct: 0, error: '' } });

test('Aufbau läuft: Karte noch nicht gebaut, Fehler, oder noch nichts getan', () => {
  for (const phase of ['idle', 'tiles', 'error']) {
    assert.equal(zurAufbauseite(zustand(phase, false)), true, phase);
    assert.equal(zurAufbauseite(zustand(phase, true)), true, `${phase} auch mit Daten`);
  }
});

test('Erster Sammellauf ohne Export: Aufbauseite statt leerer Karte', () => {
  assert.equal(zurAufbauseite(zustand('collect', false)), true);
  assert.equal(zurAufbauseite(zustand('export', false)), true);
});

test('Im Betrieb bleibt die Karte stehen: der Takt holt alle fünf Minuten neu', () => {
  assert.equal(zurAufbauseite(zustand('collect', true)), false);
  assert.equal(zurAufbauseite(zustand('export', true)), false);
  assert.equal(zurAufbauseite(zustand('ready', true)), false);
});

test('ready ohne Daten führt nicht im Kreis', () => {
  // Die Aufbauseite schickt bei „ready“ zur Karte. Würde die Karte dann zurückschicken, liefen beide gegeneinander.
  assert.equal(zurAufbauseite(zustand('ready', false)), false);
});

test('Kein Dienst (statische Seite) oder unbekannte Antwort: nichts tun', () => {
  assert.equal(zurAufbauseite(null), false);
  assert.equal(zurAufbauseite({}), false);
  // Ältere Fassung des Dienstes kennt das Feld nicht: dann nicht umleiten, sonst landet man dauerhaft auf der Aufbauseite.
  assert.equal(zurAufbauseite({ job: { phase: 'collect' } }), false);
});
