// Nur in der Desktop-App wirksam: Solange der Aufbau läuft, gehört die Besucherin auf die Aufbauseite, die den Fortschritt führt.
// Auf dem statischen Webspace antwortet api/state nicht, dann passiert nichts.

export function zurAufbauseite(s) {
  if (!s || !s.job) return false;
  if (['idle', 'tiles', 'error'].includes(s.job.phase)) return true;
  // Erster Start: Die Karte wird schon gezeigt, während die Quellen noch abgerufen werden — zu sehen ist dort aber nichts,
  // solange der erste Export fehlt. `daten` sagt, ob es ihn gibt; `ready` ohne Daten gäbe sonst ein Hin und Her.
  return s.daten === false && s.job.phase !== 'ready';
}

if (typeof document !== 'undefined') {
  fetch('api/state', { cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : null))
    .then((s) => { if (zurAufbauseite(s)) location.replace('einrichtung.html'); })
    .catch(() => {});
}
