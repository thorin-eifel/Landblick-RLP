// Geländerelief: Schummerung, Höhenfärbung, Höhenlinien mit Beschriftung, Höhenanzeige unter dem Zeiger.
// Datenbasis: Terrarium-Höhenkacheln bis Zoom 14 (mit build_dem_hires.py bis 16, dann steht hires.maxzoom in meta.json). In Rheinland-Pfalz aus dem DGM1 des Landes (LVermGeoRP, dl-de/by-2-0),
// sonst Mapzen Terrain Tiles (SRTM/EU-DEM); gebaut mit tools/build_dem_rlp.py nach web/tiles/dem/ und vom eigenen Server
// ausgeliefert. Den Vermerk liefert tiles/dem/meta.json. Kein Abruf bei Dritten.
// Höhenlinien rechnet das gebündelte maplibre-contour (BSD-3) im Browser in einem Web Worker.
// Fehlt die Kachelablage oder das Plugin, bleibt die Karte ohne Relief benutzbar (setupRelief liefert false).
import { addProtocol } from '../vendor/maplibre-gl/maplibre-gl.js';

const DEM_MAXZOOM_BASE = 14;   // Zoom, bis zu dem tiles/dem sicher vollständig ist (build_dem_rlp.py)
let DEM_MAXZOOM = DEM_MAXZOOM_BASE; // höher, wenn meta.json hires.maxzoom meldet (build_dem_hires.py)
const ELEV_SRC = 'dem';
const CONTOUR_SRC = 'contours';
export const RELIEF_LAYERS = ['relief-color', 'relief-hill', 'relief-contour', 'relief-contour-label'];
// Vermerk; setupRelief ersetzt ihn durch den Text aus tiles/dem/meta.json (Jahre der Befliegung).
export let RELIEF_ATTRIBUTION = 'Höhen: © GeoBasis-DE / LVermGeoRP, dl-de/by-2-0 [Daten bearbeitet]; außerhalb Rheinland-Pfalz EU-DEM (Copernicus, EU) und SRTM (NASA) über Mapzen Terrain Tiles';

// Höhenstufen in Metern über NN; Werte unter 100 m und über 700 m laufen in die Randfarbe aus.
export const RAMP = {
  light: [[100, '#b4d19c'], [200, '#d3e0a6'], [300, '#ece0a2'], [400, '#e2c98e'], [500, '#d1ac7b'], [600, '#bd9070'], [700, '#a9806f']],
  dark: [[100, '#25493a'], [200, '#3b5638'], [300, '#5a5a36'], [400, '#6e5a38'], [500, '#7d5a3e'], [600, '#8a5f4c'], [700, '#95695f']],
};
// Karte „um 1450“: Ocker statt Höhenstufen, braune Schummerung, Höhenlinien in Tinte (über den Relief-Schalter weiter nutzbar)
const MED_RAMP = [[100, '#e6d6a4'], [300, '#dcc790'], [500, '#cfb27c'], [700, '#bf9a68']];
const MED_STYLE = { opacity: 0.45, shadow: '#3f2a12', high: '#f3e4b8', accent: '#5e4220', hill: 0.72, contour: 'rgba(110,70,34,0.5)', contourMajor: 'rgba(84,52,24,0.8)', label: '#4a2f16', halo: 'rgba(238,224,182,0.9)' };
const STYLE = {
  light: { opacity: 0.62, shadow: '#1f2533', high: '#ffffff', accent: '#2f3646', hill: 0.7, contour: 'rgba(122,84,48,0.55)', contourMajor: 'rgba(104,68,36,0.8)', label: '#5b3d21', halo: 'rgba(255,255,255,0.85)' },
  dark: { opacity: 0.5, shadow: '#000000', high: '#7a8496', accent: '#000000', hill: 0.5, contour: 'rgba(226,196,150,0.5)', contourMajor: 'rgba(240,212,168,0.85)', label: '#f0dcbc', halo: 'rgba(18,18,18,0.9)' },
};

/** Stärke der Schummerung je Kartenstil (eine Quelle für Aufbau und Umschalten). */
export const hillStrength = (dark, med) => (med ? MED_STYLE : dark ? STYLE.dark : STYLE.light).hill;

let dem = null; // DemSource des Plugins

const abs = (rel) => new URL(rel, location.href).href;

/** Glyphen-URL für Beschriftungen; muss beim Erzeugen der Karte im Stil stehen. */
export const glyphsUrl = () => abs('fonts/') + '{fontstack}/{range}.pbf';

/** Quellen und Ebenen anlegen. Rückgabe: true, wenn das Relief nutzbar ist. */
export async function setupRelief(map) {
  const lib = globalThis.mlcontour;
  if (!lib?.DemSource) { console.warn('Relief: maplibre-contour nicht geladen'); return false; }
  try {
    const probe = await fetch(abs('tiles/dem/README.txt'), { method: 'HEAD' }).catch(() => null);
    if (!probe?.ok) throw new Error('Höhenkacheln fehlen (tools/build_dem.py ausführen)');
    const meta = await fetch(abs('tiles/dem/meta.json')).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (typeof meta?.attribution === 'string' && meta.attribution.length < 400) RELIEF_ATTRIBUTION = meta.attribution;
    const hz = meta?.hires?.maxzoom;
    if (Number.isInteger(hz) && hz > DEM_MAXZOOM_BASE && hz <= 17) DEM_MAXZOOM = hz;
    const tiles = abs('tiles/dem/') + '{z}/{x}/{y}.png';
    dem = new lib.DemSource({ url: tiles, encoding: 'terrarium', maxzoom: DEM_MAXZOOM, worker: true, cacheSize: 120, timeoutMs: 15000 });
    addProtocol(dem.sharedDemProtocolId, dem.sharedDemProtocolV4);
    addProtocol(dem.contourProtocolId, dem.contourProtocolV4);
    map.addSource(ELEV_SRC, { type: 'raster-dem', tiles: [tiles], tileSize: 256, encoding: 'terrarium', maxzoom: DEM_MAXZOOM });
    map.addSource(CONTOUR_SRC, {
      type: 'vector', maxzoom: 16,
      tiles: [dem.contourProtocolUrl({
        thresholds: { 7: [200, 1000], 10: [100, 500], 11: [50, 200], 12: [20, 100], 13: [10, 50], 14: [5, 25], 15: [5, 25], 16: [2.5, 10] },
        contourLayer: 'contours', elevationKey: 'ele', levelKey: 'level',
      })],
    });
    return true;
  } catch (err) {
    console.warn('Relief nicht verfügbar:', err?.message ?? err);
    dem = null;
    return false;
  }
}

/** Ebenen (neu) anlegen und passend einordnen: Färbung und Schummerung über Landnutzung, unter Wasser und Straßen. */
export function buildRelief(map, dark, shade, contours, med = false) {
  if (!dem) return;
  const s = med ? MED_STYLE : STYLE[dark ? 'dark' : 'light'];
  const vis = shade ? 'visible' : 'none';              // Höhenfärbung und Schummerung
  const visLines = contours ? 'visible' : 'none';       // Höhenlinien und ihre Beschriftung
  for (const id of RELIEF_LAYERS) if (map.getLayer(id)) map.removeLayer(id);
  const ramp = ['interpolate', ['linear'], ['elevation'], ...(med ? MED_RAMP : RAMP[dark ? 'dark' : 'light']).flat()];
  const anchor = 'radius-fill';
  // Wasser (Säume, Rand, Fläche): Schummerung, Hangneigung und Höhenlinien liegen darunter, damit in Seen und Flüssen nichts davon durchscheint
  const under = ['bm-water_stream_casing', 'bm-water_river_casing', 'bm-water_edge', 'bm-water'].find((id) => map.getLayer(id)) ?? anchor;
  const over = under;
  // Höhenfärbung unter den Flächenfarben (Wald, Wiese, Acker), Schummerung darüber: so bleibt das Grün sichtbar
  const colorUnder = map.getLayer('bm-land-forest') ? 'bm-land-forest' : under;
  map.addLayer({ id: 'relief-color', type: 'color-relief', source: ELEV_SRC, layout: { visibility: vis },
    paint: { 'color-relief-color': ramp, 'color-relief-opacity': s.opacity } }, colorUnder);
  const hillBefore = map.getLayer('bm-land-hang-ab15') ? 'bm-land-hang-ab15' : under;   // Hangneigung liegt über der Schummerung und ergänzt sie
  map.addLayer({ id: 'relief-hill', type: 'hillshade', source: ELEV_SRC, layout: { visibility: vis },
    paint: { 'hillshade-exaggeration': s.hill, 'hillshade-shadow-color': s.shadow, 'hillshade-highlight-color': s.high,
      'hillshade-accent-color': s.accent, 'hillshade-illumination-direction': 315 } }, hillBefore);
  const level = ['coalesce', ['get', 'level'], 0];
  map.addLayer({ id: 'relief-contour', type: 'line', source: CONTOUR_SRC, 'source-layer': 'contours', minzoom: 7, layout: { visibility: visLines, 'line-join': 'round' },
    paint: { 'line-color': ['case', ['>=', level, 1], s.contourMajor, s.contour],
      'line-width': ['interpolate', ['linear'], ['zoom'], 7, ['case', ['>=', level, 1], 0.5, 0.25], 13, ['case', ['>=', level, 1], 1.3, 0.7]] } }, over);
  map.addLayer({ id: 'relief-contour-label', type: 'symbol', source: CONTOUR_SRC, 'source-layer': 'contours', minzoom: 10,
    filter: ['>=', level, 1],
    layout: { visibility: visLines, 'symbol-placement': 'line', 'text-field': ['concat', ['to-string', ['get', 'ele']], ' m'], 'text-font': [med ? 'Grenze Gotisch Regular' : 'Noto Sans Regular'],
      'text-size': 10, 'text-max-angle': 30, 'symbol-spacing': 320 },
    paint: { 'text-color': s.label, 'text-halo-color': s.halo, 'text-halo-width': 1.4 } });
}

export const SHADE_LAYERS = ['relief-color', 'relief-hill'];
export const CONTOUR_LAYERS = ['relief-contour', 'relief-contour-label'];

/** Schummerung/Höhenfärbung und Höhenlinien getrennt ein- oder ausblenden. */
export function setReliefVisible(map, shade, contours) {
  const set = (ids, on) => { for (const id of ids) if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'); };
  set(SHADE_LAYERS, shade);
  set(CONTOUR_LAYERS, contours);
}

/** Rohe Höhenkachel (Meter, zeilenweise) für das Lichtmodell; wirft, wenn es die Kachel nicht gibt. */
export const demTile = (z, x, y) => (dem ? dem.getDemTile(z, x, y) : Promise.reject(new Error('kein Relief')));

/** Höhe in Metern an einer Koordinate aus der Zoom-14-Kachel, bilinear gemittelt; null, wenn nicht ermittelbar. */
export async function elevationAt(lng, lat) {
  if (!dem) return null;
  const z = DEM_MAXZOOM_BASE, n = 2 ** z;
  const fx = ((lng + 180) / 360) * n;
  const sin = Math.sin((lat * Math.PI) / 180);
  const fy = (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * n;
  const tx = Math.floor(fx), ty = Math.floor(fy);
  try {
    const raw = await dem.getDemTile(z, tx, ty); // {width, height, data}: Höhen in m, zeilenweise (aus dem Worker kopiert)
    const w = raw.width, hgt = raw.height, el = raw.data;
    const at = (x, y) => el[y * w + x];
    const px = (fx - tx) * w - 0.5, py = (fy - ty) * hgt - 0.5;
    const x0 = Math.max(0, Math.min(w - 2, Math.floor(px))), y0 = Math.max(0, Math.min(hgt - 2, Math.floor(py)));
    const dx = Math.min(1, Math.max(0, px - x0)), dy = Math.min(1, Math.max(0, py - y0));
    const v = at(x0, y0) * (1 - dx) * (1 - dy) + at(x0 + 1, y0) * dx * (1 - dy) + at(x0, y0 + 1) * (1 - dx) * dy + at(x0 + 1, y0 + 1) * dx * dy;
    return Number.isFinite(v) ? Math.round(v) : null;
  } catch { return null; }
}

/** Legende: Farbverlauf und Werte, Farben über CSSOM gesetzt (die CSP verbietet Inline-Styles im Markup). */
export function fillLegend(bar, dark) {
  const stops = RAMP[dark ? 'dark' : 'light'];
  const lo = stops[0][0], hi = stops[stops.length - 1][0];
  bar.style.background = `linear-gradient(to right, ${stops.map(([m, c]) => `${c} ${(((m - lo) / (hi - lo)) * 100).toFixed(1)}%`).join(', ')})`;
}
