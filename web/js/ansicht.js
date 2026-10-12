// Kartenansicht aus der Adresse (ohne DOM, damit testbar).
/** Kartenansicht aus der Adresse: `#zoom/breite/länge`, z. B. `#15/49.861/6.448`; ungültig oder fremd (z. B. `#debug`) → null. */
export function ansichtAusAdresse(hash) {
  const m = /^#(\d{1,2}(?:\.\d+)?)\/(-?\d{1,2}(?:\.\d+)?)\/(-?\d{1,3}(?:\.\d+)?)$/.exec(String(hash ?? ''));
  if (!m) return null;
  const [zoom, lat, lon] = [Number(m[1]), Number(m[2]), Number(m[3])];
  return zoom >= 0 && zoom <= 22 && Math.abs(lat) <= 85 && Math.abs(lon) <= 180 ? { zoom, lat, lon } : null;
}
