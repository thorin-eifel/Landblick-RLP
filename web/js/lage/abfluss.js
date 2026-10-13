// Ebene "Starkregen und Abfluss": Kartenebenen aus tiles/abfluss.pmtiles (tools/build_abfluss.py). Geländeschätzung, kein Gefahrenkartenwerk.
//
// Zweck:   Linien für Abflussbahnen (Breite und Farbe nach Größe des Einzugsgebiets) und Punkte für Senken. Kleine Bahnen (Klasse 0 und 1)
//          sind gestrichelt: ein Rinnsal, das nur bei Starkregen läuft. Die Ebenen laufen mit der Basiskarte (id bm-abfluss-…, bm-senken-…)
//          und werden mit ihr bei jedem Wechsel von Hell und Dunkel neu gesetzt; die Schalter stehen in basiskarte.js (applyBaseToggles).
// Daten:   Quelle `abfluss` (PMTiles, Zoom 9 bis 14); fehlt die Datei, gibt es die Ebenen nicht (abflussOk bleibt aus).
import { ABFLUSS_KLASSEN, SENKE_FARBE, abflussFarbe } from '../abfluss-farben.js';

export const ABFLUSS_LAYER_IDS = ['bm-abfluss-klein', 'bm-abfluss-gross', 'bm-senken-circle'];

export function abflussLayers(dark) {
  const m = dark ? 'dark' : 'light';
  const breite = (basis) => ['interpolate', ['linear'], ['zoom'], 9, basis * 0.5, 12, basis, 14, basis * 1.8, 17, basis * 3.5];
  // Zoom muss außen stehen (MapLibre erlaubt nur eine Zoom-Interpolation je Ausdruck); die Klassenstufe wird je Zoomstufe innen gemischt.
  const breiteK = (a, b) => ['interpolate', ['linear'], ['zoom'],
    ...[[9, 0.5], [12, 1], [14, 1.8], [17, 3.5]].flatMap(([z, f]) => [z, ['interpolate', ['linear'], ['get', 'k'], 2, a * f, 6, b * f]])];
  const quelle = { source: 'abfluss', 'source-layer': 'abfluss' };
  return [
    { id: 'abfluss-klein', type: 'line', ...quelle, minzoom: 12, filter: ['<=', ['get', 'k'], 1],
      layout: { 'line-cap': 'round', 'line-join': 'round', visibility: 'none' },
      paint: { 'line-color': abflussFarbe(m), 'line-width': breite(1.1), 'line-opacity': 0.9, 'line-dasharray': [2.2, 1.6] } },
    { id: 'abfluss-gross', type: 'line', ...quelle, filter: ['>=', ['get', 'k'], 2],
      layout: { 'line-cap': 'round', 'line-join': 'round', visibility: 'none' },
      paint: { 'line-color': abflussFarbe(m), 'line-opacity': 0.9,
        'line-width': breiteK(1.5, 4.2) } },
    { id: 'senken-circle', type: 'circle', source: 'abfluss', 'source-layer': 'senken', minzoom: 11,
      layout: { visibility: 'none' },
      paint: { 'circle-color': SENKE_FARBE[m], 'circle-opacity': 0.45, 'circle-stroke-color': SENKE_FARBE[m], 'circle-stroke-width': 1.2,
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, ['interpolate', ['linear'], ['sqrt', ['get', 'v']], 14, 3, 140, 7, 450, 12],
          15, ['interpolate', ['linear'], ['sqrt', ['get', 'v']], 14, 5, 140, 14, 450, 26]] } },
  ];
}
export { ABFLUSS_KLASSEN };
