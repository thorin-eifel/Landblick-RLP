/*
 * Kartenausschnitt als Filter für das Detailfenster (Ereignisse, Gewässer, Luft und Strahlung).
 *
 * Zweck:    Das Detailfenster zeigt nur, was im sichtbaren Bereich der Karte liegt. Rein und in Node testbar
 *           (tests/js/ausschnitt.test.mjs); die Karte liefert nur die Grenzen.
 * Format:   Grenzen als { w, s, e, n } in Grad. Ohne Grenzen (Karte noch nicht bereit) bleibt alles sichtbar.
 */

/** Liegt der Punkt im Ausschnitt? Ohne Ausschnitt oder ohne Koordinaten: Punkt ohne Lage bleibt sichtbar, mit Ausschnitt ist er es nicht. */
export function imAusschnitt(b, lon, lat) {
  if (!b) return true;
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return false;
  return lon >= b.w && lon <= b.e && lat >= b.s && lat <= b.n;
}

/** Grenzen aus einem MapLibre-Bounds-Objekt (getWest, getSouth …) oder null. */
export function grenzenVon(bounds) {
  if (!bounds) return null;
  return { w: bounds.getWest(), s: bounds.getSouth(), e: bounds.getEast(), n: bounds.getNorth() };
}

/** Ereignisse (GeoJSON-Features mit properties.lon/lat) im Ausschnitt. */
export const ereignisseImAusschnitt = (feats, b) => feats.filter((f) => imAusschnitt(b, f.properties?.lon, f.properties?.lat));

/** Stationen (lon/lat am Objekt) im Ausschnitt. */
export const stationenImAusschnitt = (list, b) => list.filter((s) => imAusschnitt(b, s.lon, s.lat));
