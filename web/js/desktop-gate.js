// Nur in der Desktop-App wirksam: Gibt es api/state und ist der Aufbau nicht fertig (Karte wird geladen, Fehler), geht es zur Aufbauseite.
// Auf dem statischen Webspace antwortet api/state nicht, dann passiert nichts.
fetch('api/state', { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).then((s) => {
  if (s && ['idle', 'tiles', 'error'].includes(s.job.phase)) location.replace('einrichtung.html');
}).catch(() => {});
