// Auskunft zu einem Punkt der Karte (Rechtsklick): Koordinaten, UTM, Gemeinde, Verbandsgemeinde, Kreis, Ort. Reine Funktionen, kein DOM.
//
// Zweck:  Aus geo/verwaltung.json (tools/build_verwaltung.py: Gemeindeflächen, Ortsteile) und geo/kreise.geojson (Kreise auch außerhalb
//         von Rheinland-Pfalz) den Namen unter dem Zeiger bestimmen. Alles läuft im Browser, es gibt keine Abfrage an Dritte.
// Daten:  verwaltung.json trägt Ringe als ganzzahlige Deltas in 1e-5 Grad (Feld `scale`). `entpacke` rechnet sie einmal in Kommazahlen
//         um und merkt sich je Gemeinde den Umgrenzungskasten, damit nur wenige Flächen genau geprüft werden.
// Grenzen: Punkt in Fläche ist auf wenige Meter genau (Vereinfachung beim Bau, --tol); direkt an einer Grenze kann die Nachbarin treffen.
//          Außerhalb von Rheinland-Pfalz gibt es keine Gemeinde, nur den Kreis aus kreise.geojson.
// Test:   tests/js/ortsinfo.test.mjs

/** Punkt (x, y) in Ring [x0, y0, x1, y1, ...]? Gerade-ungerade-Regel. */
export function imRing(ring, x, y) {
  let drin = false;
  for (let i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) {
    const xi = ring[i], yi = ring[i + 1], xj = ring[j], yj = ring[j + 1];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) drin = !drin;
  }
  return drin;
}

/** Ring aus Deltas ([x0, y0, dx1, dy1, ...] in 1/scale Grad) → absolute Grad-Werte [lon0, lat0, lon1, lat1, ...]. */
export function ringAusDeltas(d, scale) {
  const out = new Array(d.length);
  let x = 0, y = 0;
  for (let i = 0; i < d.length; i += 2) {
    x += d[i]; y += d[i + 1];
    out[i] = x / scale; out[i + 1] = y / scale;
  }
  return out;
}

function kasten(ringe) {
  let w = 1e9, s = 1e9, e = -1e9, n = -1e9;
  for (const r of ringe) for (let i = 0; i < r.length; i += 2) { w = Math.min(w, r[i]); e = Math.max(e, r[i]); s = Math.min(s, r[i + 1]); n = Math.max(n, r[i + 1]); }
  return [w, s, e, n];
}

/** verwaltung.json einmal entpacken: Ringe in Grad, Umgrenzungskasten je Gemeinde, Orte in Grad. */
export function entpacke(data) {
  const scale = data.scale || 100000;
  const gemeinden = data.gemeinden.map((g) => {
    const ringe = g.r.map((d) => ringAusDeltas(d, scale));
    return { code: g.c, name: g.n, vg: g.vg, kreis: g.k, ringe, bb: kasten(ringe) };
  });
  const orte = data.orte.map(([name, x, y, gi, ortsteil]) => ({ name, lon: x / scale, lat: y / scale, gemeinde: gi, ortsteil: !!ortsteil }));
  const nachGemeinde = new Map();
  for (const o of orte) { if (!nachGemeinde.has(o.gemeinde)) nachGemeinde.set(o.gemeinde, []); nachGemeinde.get(o.gemeinde).push(o); }
  return { gemeinden, orte, nachGemeinde, vg: data.vg, kreise: data.kreise, attribution: data.attribution, stand: data.stand };
}

/** Entfernung in Metern (flache Näherung, auf Ortsebene genau genug). */
export function entfernung(lon1, lat1, lon2, lat2) {
  const k = Math.PI / 180, dx = (lon2 - lon1) * k * Math.cos(((lat1 + lat2) / 2) * k), dy = (lat2 - lat1) * k;
  return Math.hypot(dx, dy) * 6371008.8;
}

/** MultiPolygon/Polygon-Geometrie (GeoJSON) enthält den Punkt? Löcher werden beachtet. */
export function imGeoJson(geom, lng, lat) {
  const polys = geom.type === 'Polygon' ? [geom.coordinates] : geom.type === 'MultiPolygon' ? geom.coordinates : [];
  for (const p of polys) {
    const flach = (r) => r.flatMap((c) => [c[0], c[1]]);
    if (imRing(flach(p[0]), lng, lat) && !p.slice(1).some((h) => imRing(flach(h), lng, lat))) return true;
  }
  return false;
}

/**
 * Was liegt unter (lng, lat)? { gemeinde, vg, kreis, ort, ortAbstand } mit null für Unbekanntes.
 * `v` kommt von entpacke() (oder null, wenn die Datei fehlt), `kreisFlaechen` ist kreise.geojson (oder null).
 */
export function finde(v, kreisFlaechen, lng, lat) {
  const out = { gemeinde: null, vg: null, kreis: null, ort: null, ortAbstand: null };
  if (v) {
    const gi = v.gemeinden.findIndex((g) => lng >= g.bb[0] && lng <= g.bb[2] && lat >= g.bb[1] && lat <= g.bb[3]
      && g.ringe.some((r) => imRing(r, lng, lat)));
    if (gi >= 0) {
      const g = v.gemeinden[gi];
      out.gemeinde = g.name;
      out.vg = g.vg >= 0 ? v.vg[g.vg].n : null;
      out.kreis = v.kreise[g.kreis] ?? null;
      let best = null;
      for (const o of v.nachGemeinde.get(gi) ?? []) {
        if (!o.ortsteil) continue;
        const d = entfernung(lng, lat, o.lon, o.lat);
        if (!best || d < best.d) best = { o, d };
      }
      if (best) { out.ort = best.o.name; out.ortAbstand = Math.round(best.d); }
    }
  }
  if (!out.kreis && kreisFlaechen) out.kreis = kreisFlaechen.features.find((f) => imGeoJson(f.geometry, lng, lat))?.properties?.name ?? null;
  return out;
}

const fmt = new Intl.NumberFormat('de-DE', { minimumFractionDigits: 5, maximumFractionDigits: 5 });
/** "49,85012° N, 6,45123° O" */
export function dezimalGrad(lat, lng) {
  return `${fmt.format(Math.abs(lat))}° ${lat >= 0 ? 'N' : 'S'}, ${fmt.format(Math.abs(lng))}° ${lng >= 0 ? 'O' : 'W'}`;
}

/** Grad Minuten Sekunden: 49° 51′ 00,4″ N */
export function gradMinutenSekunden(wert, pos, neg) {
  const a = Math.abs(wert), g = Math.floor(a), mf = (a - g) * 60, m = Math.floor(mf), s = (mf - m) * 60;
  return `${g}° ${String(m).padStart(2, '0')}′ ${s.toFixed(1).replace('.', ',').padStart(4, '0')}″ ${wert >= 0 ? pos : neg}`;
}

/** UTM nach ETRS89/GRS80 (Krüger-Reihe). Zone aus der Länge, Streifen als Buchstabe; "32U 317140 5524685". */
export function utm(lat, lng) {
  const a = 6378137, f = 1 / 298.257222101, k0 = 0.9996;
  const zone = Math.floor((lng + 180) / 6) + 1, lon0 = (zone * 6 - 183) * Math.PI / 180;
  const n = f / (2 - f), A = (a / (1 + n)) * (1 + n * n / 4 + n ** 4 / 64);
  const al = [n / 2 - 2 * n * n / 3 + 5 * n ** 3 / 16, 13 * n * n / 48 - 3 * n ** 3 / 5, 61 * n ** 3 / 240];
  const phi = lat * Math.PI / 180, lam = lng * Math.PI / 180 - lon0;
  const t = Math.sinh(Math.atanh(Math.sin(phi)) - (2 * Math.sqrt(n) / (1 + n)) * Math.atanh((2 * Math.sqrt(n) / (1 + n)) * Math.sin(phi)));
  const xi = Math.atan2(t, Math.cos(lam)), eta = Math.atanh(Math.sin(lam) / Math.sqrt(1 + t * t));
  let E = eta, N = xi;
  al.forEach((c, i) => { const j = i + 1; E += c * Math.cos(2 * j * xi) * Math.sinh(2 * j * eta); N += c * Math.sin(2 * j * xi) * Math.cosh(2 * j * eta); });
  const band = 'CDEFGHJKLMNPQRSTUVWX'[Math.max(0, Math.min(19, Math.floor((lat + 80) / 8)))];
  const east = Math.round(500000 + k0 * A * E), north = Math.round(k0 * A * N + (lat < 0 ? 10000000 : 0));
  return { zone, band, east, north, text: `${zone}${band} ${east} ${north}` };
}
