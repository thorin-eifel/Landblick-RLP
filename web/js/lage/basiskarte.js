import { layers as basemapLayers, namedFlavor } from '../../vendor/protomaps-basemaps/basemaps.js';
import { registerIcons, registerMedieval, setIconStyle } from '../icons.js';
import { buildRelief, elevationAt, fillLegend, hillStrength } from '../relief.js';
import { $, SEV } from '../util.js';
import { fillWindLegend } from '../wind.js';
import { palette, sevColor } from './farben.js';
import { baseAnchor } from './geometrie.js';
import { MED, MED_COLORS, MED_ICON_STYLE, medFlavor, medievalize } from './mittelalter.js';
import { HER_LAYERS, NAT_LAYERS, applyNatureVisibility, paintNature, peakLayers } from './natur.js';
import { INFRA_LAYER_IDS, paintStops } from './orte.js';
import { placeLgb } from './lgb.js';
import { skinize, skinById, tintOf, wantsPatterns } from './skins.js';
import { BUILDING_OPACITY, LABEL_SKIP, LAND, cliffLayers, hangLayers, labelsAndBuildings, ortsnamenUebersicht, landUseLayers, mainRoad, roadsFromDetail, signLayers, waterEdges } from './stil.js';
import { applyFlow, applyLegends, fillTempLegend, placeRadar } from './wetterkarte.js';
import { BUILDING_KLASSEN } from '../gebaeude-farben.js';
import { basemapOk, coreOk, flow, gebOk, hangOk, light, klippenOk, map, mapReady, reliefOk, ringOk, state } from './zustand.js';

/** Farbfeld mit Text als Zeile der Zeichenerklärung (Farbe per CSSOM, die CSP verbietet Inline-Styles im Markup). */
function legendZeile(farbe, text, deckkraft = 1) {
  const z = document.createElement('div'), sw = document.createElement('span');
  z.className = 'legend-row';
  sw.className = 'geb-sw';
  sw.style.background = farbe;
  sw.style.opacity = String(deckkraft);
  sw.setAttribute('aria-hidden', 'true');
  z.append(sw, ` ${text}`);
  return z;
}

const VEG_LEGENDE = [['forest', 'Wald'], ['meadow', 'Wiese, Weide'], ['grass', 'Park, Rasen, Garten'], ['scrub', 'Busch'], ['heath', 'Heide'], ['farmland', 'Acker'],
  ['orchard', 'Obst'], ['vineyard', 'Wein'], ['wetland', 'Feuchtgebiet'], ['rock', 'Fels'], ['sand', 'Sand, Strand'], ['cemetery', 'Friedhof']];

/** Zeichenerklärung der Flächen: Gebäudefunktion, Bewuchs, Meldungsstufen. Farben folgen dem Farbschema (hell/dunkel). */
function fillFlaechenLegenden(dark) {
  const k = dark ? 'dark' : 'light';
  $('#legend-geb')?.replaceChildren(...BUILDING_KLASSEN.filter(([id]) => id !== 'sonst').map(([, titel, c]) => legendZeile(c[k], titel, BUILDING_OPACITY + 0.4)));
  $('#legend-veg')?.replaceChildren(...VEG_LEGENDE.map(([id, titel]) => legendZeile(LAND[k][id][0], titel, Math.min(1, LAND[k][id][1] + 0.3))));
  const pal = palette();
  $('#legend-warn')?.replaceChildren(...['critical', 'warning', 'notice', 'info'].map((id) => legendZeile(pal[id], SEV[id].label)));
}

// Stil-Layer der Basiskarte unter den eigenen Ebenen; beim Wechsel Hell/Dunkel neu aufgebaut
export function applyBasemap() {
  if (!basemapOk) { applyRelief(); placeRadar(); return; }
  for (const l of map.getStyle().layers) if (l.id.startsWith('bm-')) map.removeLayer(l.id);
  const med = !!state.layers.medieval;
  document.documentElement.dataset.karte = med ? 'mittelalter' : '';
  document.documentElement.dataset.skin = skinById(state.skin).id;
  const flavor = !med && document.documentElement.dataset.ansicht === 'dunkel' ? 'dark' : 'grayscale';
  const before = baseAnchor();
  // Keine Grenzlinien (Länder, Kreise): die Karte zeigt Gelände, Gewässer, Straßen und den Radius
  // roads_shields entfällt: es braucht Sprite-Bilder, die wir nicht ausliefern; die Schilder zeichnen signLayers()
  const dark = flavor === 'dark';
  let styled = basemapLayers('basemap', med ? medFlavor() : namedFlavor(flavor), { lang: 'de' }).filter((x) => !LABEL_SKIP.test(x.id)).map(mainRoad).map(labelsAndBuildings(dark)).flatMap(ortsnamenUebersicht)
    .map((x) => {   // Gebäude: Hausumringe/OSM-Mischung (Zoom 14/15); sonst Kern. Hausnummern bleiben im Kern.
      if (gebOk && x.id === 'buildings') return { ...x, source: 'basemap-geb' };
      return coreOk && (x.id === 'buildings' || x.id === 'address_label') ? { ...x, source: 'basemap-core' } : x;
    });
  // eigene Flächen- und Geländeebenen gleich hinter dem Landnutzungs-Layer des Stils (unter Wasser, Straßen und Relief-Linien)
  const at = styled.findIndex((x) => x.id === 'landuse_park');
  // Reihenfolge von unten: Hangneigung, Vegetation (Landnutzung), Klippen (weiter unten im Code, über allem Gelände)
  styled.splice(at >= 0 ? at + 1 : 0, 0, ...hangLayers(dark, hangOk, state.layers.hang), ...landUseLayers(dark, !!map.getSource('rlp-grenze')));
  // Klippen weit oben: über Hangneigung, Relief, Höhenlinien, Vegetation, Gewässer und Straßen, unter den Beschriftungen
  const lab0 = styled.findIndex((x) => x.layout?.['text-font'] && !x.id.startsWith('land-'));
  styled.splice(lab0 < 0 ? styled.length : lab0, 0, ...cliffLayers(med ? 'med' : dark ? 'dark' : 'light', dark, map.hasImage('cliff-stroke'), klippenOk));
  waterEdges(styled, dark);
  styled.push(...peakLayers(dark, map.hasImage('peak-tri')));   // Gipfel oben auf den Beschriftungen des Stils
  const tint = tintOf(state.skin, dark);
  if (tint) styled = skinize(styled, tint, { patterns: wantsPatterns(state.skin) });
  if (med) styled = medievalize(styled);
  styled = roadsFromDetail(styled, { core: coreOk, ring: ringOk });   // Straßen und Namen ab Zoom 14 aus Kern und Ring (vollständiger als Zoom 13)
  if (ringOk && !gebOk) {   // gleiche Gebäudeebenen noch einmal aus dem Ring; Kern und Ring überlappen nicht, nichts wird doppelt gezeichnet
    const at2 = styled.map((x) => x.id).lastIndexOf('buildings-line');
    const extra = styled.filter((x) => x.id === 'buildings' || x.id === 'buildings-line').map((x) => ({ ...x, id: `${x.id}-ring`, source: 'basemap-ring' }));
    styled.splice((at2 >= 0 ? at2 : styled.findIndex((x) => x.id === 'buildings')) + 1, 0, ...extra);
  }
  if (flow) {   // Wasserbewegung (Ebene "flow")
    const fl = flow.layers({ dark, med });
    const wr = styled.findIndex((x) => x.id === 'water_river'), lab = styled.findIndex((x) => x.layout?.['text-font'] && !x.id.startsWith('land-'));
    styled.splice(wr >= 0 ? wr + 1 : lab < 0 ? styled.length : lab, 0, ...fl);   // gleich über die Gewässerlinien des Stils, unter Straßen und Beschriftung
  }
  for (const l of styled) map.addLayer({ ...l, id: `bm-${l.id}` }, before);
  if (state.signsOk) for (const l of signLayers(dark)) map.addLayer(l, before);
  for (const id of ['routes-hike-casing', 'routes-bike-casing', 'routes-hike', 'routes-bike', 'routes-hit', 'routes-label', ...INFRA_LAYER_IDS]) if (map.getLayer(id)) map.moveLayer(id, before);
  for (const id of [...NAT_LAYERS, ...HER_LAYERS]) if (map.getLayer(id)) map.moveLayer(id, before);   // Landmarken (Höhlen, Burgen …) über die neu gebauten Basislayer, sonst verdecken Flächen und Relief sie
  if (map.getLayer('air-dim')) map.moveLayer('air-dim', before);   // Verdunklung direkt über der Basiskarte, unter allen Datenebenen
  paintWater(flavor === 'dark', med);
  paintStops();
  paintNature();
  applyNatureVisibility();
  fillFlaechenLegenden(dark);
  applyLegends();
  applyBaseToggles();
  applyFlow();
  flow?.refresh();
  applyRelief();
  placeRadar();
  placeLgb();   // LGB-Ebenen bleiben über der neu gebauten Basis, unter Straßen und Beschriftung
}

// Gewässer blau, damit Mosel, Sauer und Seen auch auf der grauen Basiskarte und über dem Relief sofort lesbar sind
export function paintWater(dark, med) {
  const fill = med ? MED.water : tintOf(state.skin, dark)?.water ?? (dark ? '#1f4f7a' : '#8fc0e8'), line = fill;   // Linie in Flächenfarbe: Mittellinie und Fläche gehen nahtlos ineinander über
  if (map.getLayer('bm-water')) map.setPaintProperty('bm-water', 'fill-color', fill);
  for (const id of ['bm-water_stream', 'bm-water_river']) if (map.getLayer(id)) map.setPaintProperty(id, 'line-color', line);
}

export function applyRelief() {
  const dark = document.documentElement.dataset.ansicht === 'dunkel';
  if (reliefOk) buildRelief(map, dark, state.layers.relief, state.layers.contours, !!state.layers.medieval);
  applyLight(dark);
  fillLegend($('#relief-bar'), dark);
  applyLegend();
}

// Lichtquelle am Zeiger: nur mit Relief; die feste Schummerung wird gedämpft, damit sich beide nicht widersprechen
export function applyLight(dark = document.documentElement.dataset.ansicht === 'dunkel') {
  if (!light) return;
  const on = state.layers.licht && state.layers.relief;
  const med = !!state.layers.medieval;
  const before = map.getLayer('bm-water') ? 'bm-water' : 'radius-fill';
  // Wasserglitzern über Wasserfläche und Wasserlinien (Mosel, Bäche haben dieselbe Farbe), aber unter allem, was danach kommt
  const ids = map.getStyle().layers.map((l) => l.id);
  const last = Math.max(...['bm-water', 'bm-water_stream', 'bm-water_river'].map((i) => ids.indexOf(i)));
  const beforeWater = last >= 0 && ids[last + 1] ? ids[last + 1] : 'radius-fill';
  light.setEnabled(on);
  light.build(before, beforeWater, { dark, med, waterColor: med ? MED.water : tintOf(state.skin, dark)?.water ?? (dark ? '#1f4f7a' : '#8fc0e8') });
  if (map.getLayer('relief-hill')) map.setPaintProperty('relief-hill', 'hillshade-exaggeration', on ? 0.12 : hillStrength(dark, med));
  const box = $('#licht-opt'); if (box) box.hidden = !on;
}

export function applyLegend() {
  const box = $('#relief-legend');
  if (!box) return;
  const shade = state.layers.relief, lines = state.layers.contours;
  box.hidden = !(reliefOk && (shade || lines));
  for (const el of box.querySelectorAll('.relief-title, .relief-bar, .relief-scale')) el.hidden = !shade;   // Farbskala nur mit Höhenfärbung
}

// Höhe unter dem Zeiger (Maus) bzw. am Tippunkt (Touch), gedrosselt auf einen Abruf gleichzeitig
export function wireElevation() {
  const out = $('#relief-elev');
  if (!reliefOk || !out) return;
  let busy = false, last = null;
  const show = async (ll) => {
    last = ll;
    if (busy) return;
    busy = true;
    while (last) {
      const cur = last; last = null;
      const v = state.layers.relief || state.layers.contours ? await elevationAt(cur.lng, cur.lat) : null;
      out.textContent = v == null ? 'Höhe: –' : `Höhe: ${v} m ü. NN`;
    }
    busy = false;
  };
  map.on('mousemove', (e) => show(e.lngLat));
  map.on('click', (e) => show(e.lngLat));
}

export async function recolor() {
  if (!mapReady) return;
  const c = palette();
  const medOn = !!state.layers.medieval;
  if (state.iconsOk) {   // Umriss der Flugzeuge hängt vom Hintergrund ab; historische Karte: eigene Farben, Pergamentsaum und gezeichnete Zeichen
    setIconStyle(medOn ? MED_ICON_STYLE : null);
    try { await registerIcons(map, medOn ? MED_COLORS : c); } finally { setIconStyle(null); }
    if (medOn) registerMedieval(map, MED_COLORS);
  }
  map.setPaintProperty('bg', 'background-color', c.bg);
  applyBasemap();
  for (const id of ['ev-fill', 'ev-outline', 'ev-line', 'ev-point', 'ev-dot-w']) {
    map.setPaintProperty(id, id === 'ev-fill' ? 'fill-color' : id.startsWith('ev-point') || id === 'ev-dot-w' ? 'circle-color' : 'line-color', sevColor(c));
  }
  map.setPaintProperty('st-circle', 'circle-stroke-color', c.info);
  map.setPaintProperty('air-circle', 'circle-stroke-color', sevColor(c));
  map.setPaintProperty('env-circle', 'circle-stroke-color', sevColor(c));
  fillTempLegend();
  const wb = $('#wind-bar'); if (wb) fillWindLegend(wb);
  const wbl = $('#wind-bar-low'); if (wbl) fillWindLegend(wbl, undefined, true);   // Windpalette folgt der Ansicht
}

// Schalter für Teile der Basiskarte: Landnutzung, Klippen und Steinbrüche, Gebäude, Straßenschilder (Layer heißen bm-*)
// Straßenarten der Protomaps-Grundkarte (Ebenen roads_*, auch Brücken und Tunnel, mit Rand): je Art ein Schalter
export const ROAD_KEYS = [
  ['roadNames', /^bm-roads_(labels_|shields|oneway)/],
  ['rail', /^bm-roads_(?:(?:bridges|tunnels)_)?rail/],
  ['roadHw', /^bm-roads_(?:(?:bridges|tunnels)_)?(?:highway|link)(?:_|$)/],
  ['roadMain', /^bm-roads_(?:(?:bridges|tunnels)_)?major(?:_|$)/],
  ['roadMid', /^bm-roads_(?:(?:bridges|tunnels)_)?medium(?:_|$)/],
  ['roadMinor', /^bm-roads_(?:(?:bridges|tunnels)_)?minor(?:_|$)/],
  ['roadPath', /^bm-roads_(?:(?:bridges|tunnels)_)?other(?:_|$)/],
];
export const roadKey = (id) => (id.startsWith('bm-roads_') ? ROAD_KEYS.find(([, rx]) => rx.test(id))?.[0] ?? null : null);

// Flächenklasse → Schalter (Bewuchs); Friedhofsgrün läuft mit den Wiesen
export const LAND_KEY = { forest: 'vegForest', meadow: 'vegMeadow', grass: 'vegMeadow', cemetery: 'vegMeadow', scrub: 'vegScrub', heath: 'vegScrub', farmland: 'vegField', allotment: 'vegField',
  orchard: 'vegVine', vineyard: 'vegVine', wetland: 'vegWet', rock: 'vegRock', sand: 'vegRock' };
export const BOUND_KEY = { country: 'bndCountry', region: 'bndRegion', county: 'bndCounty', local: 'bndLocal' };
export function applyBaseToggles() {
  if (!mapReady || !basemapOk) return;
  const on = (v) => (v ? 'visible' : 'none');
  for (const l of map.getStyle().layers) {
    let key = null;
    if (l.id.startsWith('bm-flow-')) key = 'flow';
    else if (l.id.startsWith('bm-land-hang-')) key = 'hang';
    else if (/^bm-land-(cliff|quarry)/.test(l.id)) key = 'cliffs';
    else if (/^bm-land-protected-nr-/.test(l.id)) key = 'protNature';
    else if (/^bm-land-protected-np-/.test(l.id)) key = 'protPark';
    else if (/^bm-land-military-/.test(l.id)) key = 'protMil';
    else if (/^bm-land-bound-/.test(l.id)) key = BOUND_KEY[l.id.slice('bm-land-bound-'.length).replace(/-(rlp|glow\d)$/, '')];
    else if (l.id.startsWith('bm-land-')) key = LAND_KEY[l.id.slice('bm-land-'.length).replace(/-pat$/, '')];
    else if (/^bm-buildings(-line)?(-ring)?$/.test(l.id)) key = 'buildings';
    else if (l.id.startsWith('bm-sign-')) key = 'signs';
    else key = roadKey(l.id);
    if (key) map.setLayoutProperty(l.id, 'visibility', on(state.layers[key]));
  }
}
