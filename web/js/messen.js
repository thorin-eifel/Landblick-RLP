// Messen: Strecke, Umfang und Fläche aus Punkten auf der Karte. Reine Rechnung ohne Karte und DOM, Test: tests/js/messen.test.mjs.
// Rechnung auf der Kugel (Radius 6371,0088 km): Strecke nach Haversine, Fläche nach dem Kugelüberschuss-Verfahren (Summe über die Kanten).
// Abweichung gegenüber dem Ellipsoid (WGS84) liegt für Strecken und Flächen dieser Größe unter 0,5 %; für Grundstücksgrenzen ersetzt das keine Vermessung.
// Punkte sind [lon, lat] in Grad. Die Fläche gilt für das geschlossene Polygon (letzter Punkt zurück zum ersten).
const R = 6371008.8;
const rad = (d) => (d * Math.PI) / 180;

export function distance(a, b) {
  const p1 = rad(a[1]), p2 = rad(b[1]), dp = p2 - p1, dl = rad(b[0] - a[0]);
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Länge eines Linienzugs in Metern; `closed` hängt die Strecke vom letzten zum ersten Punkt an (Umfang). */
export function pathLength(pts, closed = false) {
  let sum = 0;
  for (let i = 1; i < pts.length; i++) sum += distance(pts[i - 1], pts[i]);
  if (closed && pts.length > 2) sum += distance(pts[pts.length - 1], pts[0]);
  return sum;
}

/** Fläche des Polygons in Quadratmetern (0 unter drei Punkten). */
export function polygonArea(pts) {
  if (pts.length < 3) return 0;
  let s = 0;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    s += rad(b[0] - a[0]) * (2 + Math.sin(rad(a[1])) + Math.sin(rad(b[1])));
  }
  return Math.abs((s * R * R) / 2);
}

const side = (a, b, c) => Math.sign((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]));
const cross = (a, b, c, d) => side(a, b, c) * side(a, b, d) < 0 && side(c, d, a) * side(c, d, b) < 0;

/** Schneiden sich zwei Kanten des geschlossenen Polygons? Dann ist die Fläche nicht eindeutig. */
export function selfIntersects(pts) {
  const n = pts.length;
  if (n < 4) return false;
  for (let i = 0; i < n; i++) {
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue;   // erste und letzte Kante teilen sich den Startpunkt
      if (cross(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n])) return true;
    }
  }
  return false;
}

const de = (v, digits) => v.toLocaleString('de-DE', { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function formatLength(m) {
  if (!Number.isFinite(m)) return '–';
  if (m < 1000) return `${de(Math.round(m), 0)} m`;
  return `${de(m / 1000, m < 10000 ? 2 : 1)} km`;
}

export function formatArea(m2) {
  if (!Number.isFinite(m2)) return '–';
  if (m2 < 10000) return `${de(Math.round(m2), 0)} m²`;
  if (m2 < 1e6) return `${de(m2 / 10000, m2 < 100000 ? 2 : 1)} ha (${de(Math.round(m2), 0)} m²)`;
  return `${de(m2 / 1e6, 2)} km² (${de(Math.round(m2 / 10000), 0)} ha)`;
}

/** Zusammenfassung für Anzeige und Zwischenablage. `closed`: Fläche gilt, sonst nur Strecke (mit Vorschau der Fläche ab drei Punkten). */
export function summary(pts, closed) {
  const n = pts.length;
  const out = { n, closed: !!closed && n >= 3, lines: [], warn: '' };
  if (n === 0) { out.lines.push('Karte anklicken, um Punkte zu setzen.'); return out; }
  if (out.closed) {
    out.lines.push(`Fläche: ${formatArea(polygonArea(pts))}`, `Umfang: ${formatLength(pathLength(pts, true))}`, `${n} Eckpunkte`);
    if (selfIntersects(pts)) out.warn = 'Die Kanten kreuzen sich; die Fläche ist dann nicht eindeutig.';
    return out;
  }
  out.lines.push(n === 1 ? 'Ersten Punkt gesetzt. Weitere Punkte anklicken.' : `Strecke: ${formatLength(pathLength(pts))}`);
  if (n >= 2) out.lines.push(`Letzter Abschnitt: ${formatLength(distance(pts[n - 2], pts[n - 1]))}`);
  if (n >= 3) out.lines.push(`Geschlossen: ${formatArea(polygonArea(pts))}, Umfang ${formatLength(pathLength(pts, true))}`);
  return out;
}

/** GeoJSON für die Karte: Linie, Füllung, Eckpunkte und Streckenbeschriftung. `cursor` ist der Gummibandpunkt (nur offen). */
export function messenFeatures(pts, closed, cursor = null) {
  const fc = (features) => ({ type: 'FeatureCollection', features });
  const ring = closed && pts.length >= 3 ? [...pts, pts[0]] : pts;
  const line = ring.length >= 2 ? [{ type: 'Feature', geometry: { type: 'LineString', coordinates: ring }, properties: {} }] : [];
  const rubber = !closed && cursor && pts.length ? [{ type: 'Feature', geometry: { type: 'LineString', coordinates: [pts[pts.length - 1], cursor] }, properties: {} }] : [];
  const fill = closed && pts.length >= 3 ? [{ type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} }] : [];
  const points = pts.map((p, i) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: p }, properties: { first: i === 0 ? 1 : 0, n: i + 1 } }));
  const labels = [];
  for (let i = 1; i < ring.length; i++) {
    const a = ring[i - 1], b = ring[i];
    labels.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] }, properties: { text: formatLength(distance(a, b)) } });
  }
  return { line: fc(line), rubber: fc(rubber), fill: fc(fill), points: fc(points), labels: fc(labels) };
}
