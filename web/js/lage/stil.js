import { KLIPPEN_UMRISS } from './klippen-umriss.js';
import { RLP_UMRISS } from './rlp-umriss.js';
import { map } from './zustand.js';
import { BUILDING, buildingFill } from '../gebaeude-farben.js';

// Hauptstraßen (Autobahn, Bundes-/Landstraße, Anschlussstellen, auch Brücken und Tunnel) mit 1-px-Kontur in Schwarz:
// Autobahnen blau, alle anderen Hauptstraßen gelborange. Die Konturen des Stils sind Linien neben der Straße
// (line-gap-width), ihre Breite ist die Konturbreite.
export const MAIN_ROAD = /^roads_(highway|major|link|bridges_(highway|major|link)|tunnels_(highway|major|link))(_casing(_early|_late)?)?$/;
export const ROAD_FILL = '#f6a81c';
export const AUTOBAHN_FILL = '#1f5fbf';
// Breite der Fahrbahn (Füllung) in px; die Konturlinien sitzen mit line-gap-width genau daneben. Größer als im Stil, damit die Farbe
// schon bei kleinem Maßstab sichtbar ist und nicht nur die schwarze Kontur.
export const ROAD_W = ['interpolate', ['exponential', 1.6], ['zoom'], 6, 1.2, 9, 2.4, 12, 3.6, 15, 7, 18, 15];
export const LINK_W = ['interpolate', ['exponential', 1.6], ['zoom'], 11, 0, 12, 1.4, 15, 4, 18, 10];
// Zwei Klassen außerhalb der Autobahn: Bundes- und Nationalstraßen (B, N, RN; in OSM primary/trunk) kräftig orange und breiter,
// Land-, Kreis- und Departementsstraßen (L, K, D, CR; secondary/tertiary) hellgelb und schmaler. Die Klasse kommt aus kind_detail
// und dem Kürzel der Straßennummer (ref); beides steht in den Kacheln.
export const ROAD_FILL_MINOR = '#f8df85';
export const NATIONAL = ['any',
  ['in', ['coalesce', ['get', 'kind_detail'], ''], ['literal', ['primary', 'trunk', 'primary_link', 'trunk_link']]],
  ['in', ['slice', ['coalesce', ['get', 'ref'], ''], 0, 1], ['literal', ['B', 'N']]]];
// Zoom-Stützwerte einzeln mit dem Klassenfaktor multiplizieren (zoom darf nur oberster interpolate-Eingang sein)
export const scaled = (w, k) => w.map((x, i) => (i >= 4 && i % 2 === 0 && typeof x === 'number' && x > 0 ? ['*', k, x] : x));
export function mainRoad(l) {
  if (!MAIN_ROAD.test(l.id)) return l;
  const casing = l.id.includes('casing');
  const motorway = /^roads_(bridges_|tunnels_)?highway/.test(l.id);
  const base = l.id.includes('link') ? LINK_W : ROAD_W;
  const w = motorway ? base : scaled(base, ['case', NATIONAL, 1.2, 0.8]);
  const fill = motorway ? AUTOBAHN_FILL : ['case', NATIONAL, ROAD_FILL, ROAD_FILL_MINOR];
  const paint = { ...l.paint, 'line-color': casing ? '#000000' : fill };
  if (casing) {
    paint['line-gap-width'] = w;
    paint['line-width'] = 1;
    paint['line-opacity'] = ['interpolate', ['linear'], ['zoom'], 9.5, 0, 10.5, 1]; // weit herausgezoomt keine schwarze Kontur
  } else paint['line-width'] = w;
  return { ...l, paint };
}

// Gebäude in Bordeaux; Beschriftungen (Straßennamen, Hausnummern) mit der einzigen mitgelieferten Schrift, früher einsetzend als im Stil
export const SIZE_MIN_PX = 8 * 4 / 3;    // 8 pt kleinster Ortsname (Einzelhof, Weiler)
export const SIZE_MAX_PX = 12 * 4 / 3;   // 12 pt größter Ortsname (Großstadt)
export const LABEL_SKIP = /^(boundaries|pois$|roads_shields|roads_oneway|places_(country|region)|water_label_ocean|earth_label_islands)/;
export const INK = { light: '#111111', dark: '#f4f4f4' };
export const WATER_INK = { light: '#0b4f9c', dark: '#8cc4ff' };   // Gewässernamen immer blau
export const HALO = { light: 'rgba(255,255,255,0.95)', dark: 'rgba(16,16,16,0.95)' };
// Deckkraft der Gebäude nach Zoom: in der Übersicht 40 % (Relief und Straßen scheinen durch), im Nahbereich bis 75 % (Häuser stehen deutlich da)
export const BUILDING_OPACITY = ['interpolate', ['linear'], ['zoom'], 14, 0.4, 17, 0.75];
export const BUILDING_OPACITY_LEGEND = 0.75;   // Farbfeld der Zeichenerklärung
export const GREEN = { light: '#9fc98a', dark: '#2f6a43' };
// Flächenfarben nach OSM-Klasse (Farbe, Deckkraft); dezent, damit Relief, Straßen und Ereignisse führen
// Farben nach der Natur: Wald dunkles Blattgrün, Wiese frisches Gelbgrün, Weide/Rasen satteres Grün, Busch olivgrau,
// Heide Heidekraut-Violett, Acker Stoppelgelb, Obst helles Apfelgrün, Wein Strohgelb, Moor blaugrün, Fels Steingrau, Sand Hellgelb.
export const LAND = {
  light: { forest: ['#5f9f5b', 0.55], meadow: ['#c4dc8a', 0.5], grass: ['#a9d57c', 0.5], scrub: ['#94a862', 0.5], heath: ['#bb98ae', 0.5],
    farmland: ['#e9dcaa', 0.45], orchard: ['#bdd677', 0.5], vineyard: ['#cfc27c', 0.5], allotment: ['#d6e4a2', 0.5], wetland: ['#8fc4a8', 0.55],
    rock: ['#b6ab9c', 0.6], sand: ['#f0e3b2', 0.6], cemetery: ['#b5d0a4', 0.55] },
  dark: { forest: ['#245234', 0.6], meadow: ['#4a7240', 0.5], grass: ['#3f7040', 0.5], scrub: ['#505e36', 0.5], heath: ['#5e4a58', 0.5],
    farmland: ['#5f5733', 0.4], orchard: ['#4c6a35', 0.5], vineyard: ['#5d5a30', 0.5], allotment: ['#4f6a3f', 0.5], wetland: ['#2b5f58', 0.55],
    rock: ['#6d675f', 0.6], sand: ['#6f6747', 0.55], cemetery: ['#3d5f45', 0.55] },
};
// Tinte der Signaturen (Rgba), Bilder lp-<klasse>-<light|dark> aus icons.js registerLandPatterns()
export const PAT_MIN_ZOOM = 12;
export const PROTECTED = { light: '#2e7d3c', dark: '#7fd18a' };
export const CLIFF = { light: '#000000', dark: '#dedad2', med: '#3a2614' }; // dunkles Steingrau bzw. helles Grau, bewusst kein Braun: Höhenlinien sind braun
export const CLIFF_SCREE = { light: '#6f675b', dark: '#8d8578', med: '#7a5530' };   // Geröllband am Fuß der Wand
export const QUARRY = { light: ['#8a6d3b', '#4a3a1c'], dark: ['#d9b56b', '#f0dcae'] };
export const LAND_KINDS = {
  forest: ['forest', 'wood'],
  meadow: ['meadow'],
  grass: ['grass', 'grassland', 'park', 'garden', 'recreation_ground', 'golf_course', 'dog_park', 'village_green'],
  scrub: ['scrub'],
  heath: ['heath'],
  farmland: ['farmland'],
  orchard: ['orchard'],
  vineyard: ['vineyard'],
  allotment: ['allotments'],
  wetland: ['wetland'],
  rock: ['bare_rock'],
  sand: ['sand', 'beach'],
  cemetery: ['cemetery'],
};
export const PROTECTED_KINDS_NR = ['protected_area', 'nature_reserve'];
export const PROTECTED_KINDS_NP = ['national_park'];
export const PARK_NAT = { light: '#0f7a73', dark: '#5fd1c4' };
export const MILITARY = { light: '#b23b2a', dark: '#f08b78' };
// Grenzen: id, Filter, Mindestzoom. Alle Tilegrenzen sehen gleich aus (gepunktet, eine Farbe je Ansicht); nur die Landesgrenze von
// Rheinland-Pfalz hebt sich ab (rot, 2 px, grauer Verlauf 5 px nach außen), sie kommt aus web/geo/rlp.geojson.
export const BOUNDS = [
  ['local', ['in', 'kind_detail', 7, 8], 10],
  ['county', ['==', 'kind_detail', 6], 8],
  ['region', ['==', 'kind_detail', 4], 5],
  ['country', ['==', 'kind_detail', 2], 3],
];
export const BOUND_COLOR = { light: '#4b2e83', dark: '#c3a8ff' };
export const RLP_SOURCE = 'rlp-grenze';
export const RLP_RED = { light: '#d0021b', dark: '#ff4d5e' };
export const RLP_GLOW = { light: '#3d3d3d', dark: '#c8c8c8' };
// Verlauf: fünf Linien zu je 1 px Breite, Mitte bei 1,5 bis 5,5 px außerhalb der Linie (die rote Linie belegt ±1 px), Deckkraft nimmt ab.
// Das Vorzeichen ist an der Karte geprüft: bei Außenring gegen den Uhrzeigersinn liegt die Außenseite bei negativem line-offset.
export const RLP_GLOW_STEPS = [[-1.5, 0.5], [-2.5, 0.38], [-3.5, 0.27], [-4.5, 0.17], [-5.5, 0.08]];
/** Rote Landesgrenze mit Verlauf. Quelle web/geo/rlp.geojson, Außenring gegen den Uhrzeigersinn. */
export function rlpBorderLayers(dark) {
  const k = dark ? 'dark' : 'light', keep = { layout: { 'line-join': 'round', 'line-cap': 'butt' } };
  return [
    ...RLP_GLOW_STEPS.map(([off, op], i) => ({ id: `land-bound-region-glow${i}`, type: 'line', source: RLP_SOURCE, minzoom: 4, ...keep,
      paint: { 'line-color': RLP_GLOW[k], 'line-opacity': dark ? op * 0.6 : op, 'line-width': 1.2, 'line-offset': off } })),
    { id: 'land-bound-region-rlp', type: 'line', source: RLP_SOURCE, minzoom: 4, ...keep,
      paint: { 'line-color': RLP_RED[k], 'line-opacity': 1, 'line-width': 2 } },
  ];
}
// Übersichtskarte (Zoom 5 bis 9): in Rheinland-Pfalz alle Ortsnamen, die die Kacheln auf dieser Stufe führen, außerhalb nur Städte
// mit mehr als FREMD_MIN_EINWOHNER Einwohnern (Kachelfeld `population`). Ab Zoom 9 gilt überall dieselbe Beschriftung.
export const FREMD_MIN_EINWOHNER = 80000;
export function ortsnamenUebersicht(l) {
  if (l.id !== 'places_locality') return [l];
  const inRlp = ['within', RLP_UMRISS];
  const gross = ['>=', ['to-number', ['get', 'population'], 0], FREMD_MIN_EINWOHNER];
  return [{ ...l, minzoom: 9 }, { ...l, id: 'places_locality_ov', minzoom: 5, maxzoom: 9, filter: ['all', ['==', ['get', 'kind'], 'locality'], ['any', inRlp, gross]] }];
}
export const HOUSENO = { light: ['#6b0019', 'rgba(255,255,255,0.9)'], dark: ['#f0b3c4', 'rgba(20,20,20,0.9)'] };
export function labelsAndBuildings(dark) {
  const k = dark ? 'dark' : 'light';
  return (l) => {
    let out = l;
    if (l.layout?.['text-font']) {
      const layout = { ...out.layout, 'text-font': ['Noto Sans Regular'] };
      delete layout['icon-image']; // ohne Sprite kein Symbol, der Text bleibt
      out = { ...out, layout };
    }
    if (l.id === 'buildings') {
      out = { ...out, minzoom: 13, paint: { ...out.paint, 'fill-color': buildingFill(k), 'fill-outline-color': dark ? '#5a1830' : '#4d0013',
        'fill-opacity': BUILDING_OPACITY } };
    } else if (l.id === 'landuse_park') {
      // Wald, Wiese, Acker und Co. zeichnet landUseLayers() nach Klasse; hier bleibt, was der Stil sonst noch kennt
      out = { ...out, filter: ['in', 'kind', 'airfield', 'glacier'] };
    } else if (l.id === 'landuse_urban_green') {
      out = { ...out, paint: { ...out.paint, 'fill-color': LAND[k].meadow[0], 'fill-opacity': LAND[k].meadow[1] } };
    } else if (l.id === 'landcover') {
      // nur Wald, Wiese und Buschland grün; Acker, Siedlung und Kahlland behalten die Farbe des Stils
      out = { ...out, paint: { ...out.paint,
        'fill-color': ['match', ['get', 'kind'], ['forest', 'grassland', 'scrub'], GREEN[k], out.paint['fill-color']],
        'fill-opacity': ['interpolate', ['linear'], ['zoom'], 5, 0.5, 8, 0.3] } };
    } else if (l.id === 'address_label') {
      out = { ...out, minzoom: 16, layout: { ...out.layout, 'text-size': ['interpolate', ['linear'], ['zoom'], 16, 10, 19, 13], 'text-allow-overlap': false },
        paint: { ...out.paint, 'text-color': HOUSENO[k][0], 'text-halo-color': HOUSENO[k][1], 'text-halo-width': 1.5 } };
    } else if (l.id === 'roads_labels_minor' || l.id === 'roads_labels_major') {
      // Straßennamen: dunkle Schrift auf kräftigem hellem Saum (dunkel: umgekehrt), größer als im Stil
      out = { ...out, minzoom: l.id === 'roads_labels_minor' ? 13 : l.minzoom,
        layout: { ...out.layout, 'text-size': ['interpolate', ['linear'], ['zoom'], 11, 11, 15, 12.5, 18, 15] },
        paint: { ...out.paint, 'text-color': INK[k], 'text-halo-color': HALO[k], 'text-halo-width': 2.4, 'text-halo-blur': 0.3 } };
    } else if (l.id === 'water_waterway_label' || l.id === 'water_label_lakes') {
      out = { ...out, paint: { ...out.paint, 'text-color': WATER_INK[k], 'text-halo-color': HALO[k], 'text-halo-width': 2.2, 'text-halo-blur': 0.3 } };
    } else if (l.id === 'places_locality' || l.id === 'places_subplace') {
      // Ortsnamen: größer, gesperrt, in voller Textfarbe mit breitem Saum
      // Größe nach Siedlungsgröße: population_rank der Kacheln (1 Einzelhof … 9 Großstadt) → 8 pt bis 12 pt (10,67 bis 16 px),
      // unabhängig vom Zoom. Weiler = Rang 2, Dorf 3 bis 5, Stadt 6 bis 7, Trier = 9. Fehlt der Rang, gilt der kleinste Wert.
      const rank = ['max', 1, ['min', 9, ['to-number', ['get', 'population_rank'], 1]]];
      out = { ...out, minzoom: 9, ...(l.filter ? { filter: l.filter } : {}),
        layout: { ...out.layout, 'text-size': ['interpolate', ['linear'], rank, 1, SIZE_MIN_PX, 9, SIZE_MAX_PX],
          'text-letter-spacing': 0.06, 'text-transform': ['case', ['>=', rank, 6], 'uppercase', 'none'], 'text-max-width': 8 },
        paint: { ...out.paint, 'text-color': INK[k], 'text-halo-color': HALO[k], 'text-halo-width': 2.8, 'text-halo-blur': 0.3 } };
    }
    return out;
  };
}

// Klippe in drei Lagen: weiches Geröllband auf der Abbruchseite (rechts der Linienrichtung), heller Saum für Lesbarkeit im Wald,
// dünne Wandlinie mit Schraffen (lange und kurze Striche im Wechsel, Bild cliff-tick, für die Klippenebene der Karte jetzt cliff-stroke).
// Mit `dgm` kommen die Wände in Rheinland-Pfalz aus dem Geländemodell (Quelle klippen, Ebenen wand, kante, schraffur, Attribut drop = Wandhöhe in m);
// die OpenStreetMap-Klippen der Basiskarte gelten dann nur noch außerhalb des Landes.
// Hangneigung aus dem DGM1: drei ineinander liegende Flächen (ab 15, 25, 35 Grad), je steiler desto dunkler. Liegt über Höhenfärbung, Schummerung und Vegetation (ergänzt die Schummerung), unter Wasser, Gebäuden, Straßen und Klippen; die Deckkraft addiert sich nach innen. Wandstriche und Oberkante der Klippen bleiben deckend. Nur mit Kacheln (hang).
export function hangLayers(dark, on, visible) {
  if (!on) return [];
  const col = dark ? { ab15: '#8a7a4a', ab25: '#9a6a3a', ab35: '#b04a3a' } : { ab15: '#e6d27a', ab25: '#d98a3a', ab35: '#b3342a' };
  return ['ab15', 'ab25', 'ab35'].map((c) => ({ id: `land-hang-${c}`, type: 'fill', source: 'hang', 'source-layer': c, minzoom: 14,
    layout: { visibility: visible ? 'visible' : 'none' },
    paint: { 'fill-color': col[c], 'fill-opacity': c === 'ab15' ? 0.16 : c === 'ab25' ? 0.2 : 0.24, 'fill-antialias': true } }));
}

// k: 'light', 'dark' oder 'med' (Alte Karte: Tinte, Pergament; dieselbe Zeichnung wie in Landblick)
export function cliffLayers(k, dark, ticks, dgm) {
  const osmFilter = dgm ? ['all', ['==', ['get', 'kind'], 'cliff'], ['!', ['within', KLIPPEN_UMRISS]]] : ['==', 'kind', 'cliff'];
  // Wandhöhe 5 m bis 30 m: Linie und Band wachsen mit der Höhe
  const byDrop = (lo, hi) => ['interpolate', ['linear'], ['get', 'drop'], 5, lo, 30, hi];
  const round = { 'line-cap': 'round', 'line-join': 'round' };
  const osm = { source: 'basemap', 'source-layer': 'earth' };
  // Gleiche Zeichnung für beide Quellen. Die OSM-Linie kennt weder Wandfläche noch Wandhöhe; sie wird deshalb wie eine 10-m-Wand gezeichnet:
  // Wandband rechts der Linie (dort liegt die Abbruchseite), Oberkante, Fallstriche. Breite, Strichlänge und -abstand wachsen mit dem Zoom
  // (Meter, nicht Pixel), wie bei den Kacheln aus dem Geländemodell. Einsatz bei Zoom 13, Striche ab 14.
  const wallColor = k === 'med' ? '#b39d73' : dark ? '#625c52' : '#c7bca4';
  const bandW = ['interpolate', ['linear'], ['zoom'], 13, 3, 14, 5, 15, 8, 16, 12, 17, 20, 18, 34];
  const bandOff = ['interpolate', ['linear'], ['zoom'], 13, 1.5, 14, 2.5, 15, 4, 16, 6, 17, 10, 18, 17];
  const out = [
    { id: 'land-cliff-band', type: 'line', ...osm, minzoom: 13, filter: osmFilter, layout: round,
      paint: { 'line-color': wallColor, 'line-opacity': ['interpolate', ['linear'], ['zoom'], 13, 0, 14, 0.35], 'line-blur': 0.5, 'line-offset': bandOff, 'line-width': bandW } },
    { id: 'land-cliff', type: 'line', ...osm, minzoom: 13, filter: osmFilter, layout: round,
      paint: { 'line-color': CLIFF[k], 'line-opacity': 1, 'line-width': ['interpolate', ['linear'], ['zoom'], 13, 0.92, 16, 1.6, 18, 2.28] } },
    ...(ticks ? [{ id: 'land-cliff-teeth', type: 'symbol', ...osm, minzoom: 14, filter: osmFilter,
      layout: { 'symbol-placement': 'line', 'symbol-spacing': ['interpolate', ['linear'], ['zoom'], 14, 2.5, 16, 3, 17, 4, 18, 8],
        'icon-image': 'cliff-stroke', 'icon-anchor': 'top', 'icon-offset': [0, 0],
        'icon-rotation-alignment': 'map', 'icon-allow-overlap': true, 'icon-ignore-placement': true,
        'icon-size': ['interpolate', ['linear'], ['zoom'], 14, 0.8, 15, 1.1, 16, 1.6, 17, 2.4, 18, 3.6] },
      paint: { 'icon-color': CLIFF[k], 'icon-opacity': 1 } }] : []),
  ];
  if (!dgm) return out;
  // Aus dem DGM1 (1 m) gezeichnete Felswand: helle Wandfläche (Polygon, 60 % Deckkraft), Striche in Fallrichtung (von oben nach
  // unten, kurz, schwarz) und obenauf die Oberkante. Die Kacheln (Zoom 13) führen Meter-genaue Geometrie; die Wandhöhe `drop`
  // bestimmt die Breite der Oberkante.
  const wall = (layer) => ({ source: 'klippen', 'source-layer': layer });
  return [
    ...out,
    { id: 'land-cliff-wand-dgm', type: 'fill', ...wall('wand'), minzoom: 13,
      paint: { 'fill-color': k === 'med' ? '#b39d73' : dark ? '#625c52' : '#c7bca4', 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 13, 0, 14, 0.2], 'fill-antialias': true } },
    { id: 'land-cliff-schraffur-dgm', type: 'line', ...wall('schraffur'), minzoom: 14, layout: round,
      paint: { 'line-color': CLIFF[k], 'line-opacity': 0.9, 'line-width': ['interpolate', ['linear'], ['zoom'], 14, 0.5, 17, 0.9, 19, 1.4] } },
    { id: 'land-cliff-dgm', type: 'line', ...wall('kante'), minzoom: 13, layout: round, filter: ['>=', ['get', 'drop'], 5],
      paint: { 'line-color': CLIFF[k], 'line-opacity': 1,
        'line-width': ['interpolate', ['linear'], ['zoom'], 13, byDrop(0.8, 1.4), 16, byDrop(1.4, 2.4), 18, byDrop(2, 3.4)] } },
  ];
}

// Flächen nach Klasse (Wald, Wiese, Buschland, Acker, Feuchtgebiet, Fels), Klippenlinien und Steinbrüche aus der Basiskarte.
// Die Kacheln führen Klippen als earth/cliff (Linien) und Steinbrüche als benannte Punkte in pois/quarry.
export function landUseLayers(dark, rlp = false) {
  const k = dark ? 'dark' : 'light';
  const fills = Object.entries(LAND_KINDS).flatMap(([cls, kinds]) => {
    // Weinberg und Obstanlage kommen aus der eigenen GeoJSON-Quelle (die Kacheln führen sie nicht)
    const own = cls === 'vineyard' || cls === 'orchard';
    const src = own ? { source: 'anbau' } : { source: 'basemap', 'source-layer': 'landuse' };
    const flt = own ? ['==', ['get', 'kind'], cls] : ['in', 'kind', ...kinds];
    const fill = {
      id: `land-${cls}`, type: 'fill', ...src, filter: flt,
      paint: { 'fill-color': LAND[k][cls][0], 'fill-opacity': LAND[k][cls][1], 'fill-antialias': true },
    };
    // Signatur (Baumkronen, Furchen, Rebzeilen …) ab Zoom 12 darüber; fehlt das Bild, bleibt die Farbe allein
    const img = `lp-${cls}-${k}`;
    if (!map.hasImage(img)) return [fill];
    return [fill, { id: `land-${cls}-pat`, type: 'fill', ...src, minzoom: PAT_MIN_ZOOM - 1, filter: fill.filter,
      paint: { 'fill-pattern': img, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], PAT_MIN_ZOOM - 1, 0, PAT_MIN_ZOOM + 1, 0.9], 'fill-antialias': false } }];
  });
  return [
    ...fills,
    // Schutzgebiete: Flächenton kaum sichtbar, gestrichelte Kante; Naturschutzgebiete grün, Nationalparks blaugrün
    ...[['nr', PROTECTED_KINDS_NR, PROTECTED[k]], ['np', PROTECTED_KINDS_NP, PARK_NAT[k]]].flatMap(([id, kinds, col]) => [
      { id: `land-protected-${id}-fill`, type: 'fill', source: 'basemap', 'source-layer': 'landuse', filter: ['in', 'kind', ...kinds],
        paint: { 'fill-color': col, 'fill-opacity': 0.07 } },
      { id: `land-protected-${id}-line`, type: 'line', source: 'basemap', 'source-layer': 'landuse', minzoom: 9, filter: ['in', 'kind', ...kinds],
        layout: { 'line-join': 'round' },
        paint: { 'line-color': col, 'line-opacity': 0.75, 'line-dasharray': [4, 3],
          'line-width': ['interpolate', ['linear'], ['zoom'], 9, 0.8, 14, 1.8], 'line-offset': ['interpolate', ['linear'], ['zoom'], 9, 0.4, 14, 1] } },
    ]),
    // Militärgelände und Sperrgebiete: rötlicher Ton, Strichpunkt-Kante
    { id: 'land-military-fill', type: 'fill', source: 'basemap', 'source-layer': 'landuse', filter: ['in', 'kind', 'military', 'naval_base'],
      paint: { 'fill-color': MILITARY[k], 'fill-opacity': 0.12 } },
    { id: 'land-military-line', type: 'line', source: 'basemap', 'source-layer': 'landuse', minzoom: 9, filter: ['in', 'kind', 'military', 'naval_base'],
      layout: { 'line-join': 'round' },
      paint: { 'line-color': MILITARY[k], 'line-opacity': 0.85, 'line-dasharray': [6, 2, 1, 2],
        'line-width': ['interpolate', ['linear'], ['zoom'], 9, 0.8, 14, 1.8], 'line-offset': ['interpolate', ['linear'], ['zoom'], 9, 0.4, 14, 1] } },
    // Verwaltungsgrenzen aus den Kacheln (kind_detail = admin_level: 2 Staat, 4 Land, 6 Kreis, 7 und 8 Gemeinde)
    ...BOUNDS.map(([id, filter, minzoom]) => ({ id: `land-bound-${id}`, type: 'line', source: 'basemap', 'source-layer': 'boundaries', minzoom, filter,
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': BOUND_COLOR[k], 'line-opacity': 0.9, 'line-width': ['interpolate', ['linear'], ['zoom'], 3, 1.2, 14, 2], 'line-dasharray': [0.01, 2.2] } })),
    ...(rlp ? rlpBorderLayers(dark) : []),
    { id: 'land-quarry-dot', type: 'circle', source: 'basemap', 'source-layer': 'pois', minzoom: 11, filter: ['==', 'kind', 'quarry'],
      paint: { 'circle-radius': 4.5, 'circle-color': QUARRY[k][0], 'circle-stroke-color': dark ? '#161616' : '#ffffff', 'circle-stroke-width': 1.5 } },
    { id: 'land-quarry-label', type: 'symbol', source: 'basemap', 'source-layer': 'pois', minzoom: 12, filter: ['==', 'kind', 'quarry'],
      layout: { 'text-field': ['concat', 'Steinbruch ', ['coalesce', ['get', 'name'], '']], 'text-font': ['Noto Sans Regular'], 'text-size': 11,
        'text-offset': [0, 0.9], 'text-anchor': 'top', 'text-max-width': 9 },
      paint: { 'text-color': QUARRY[k][1], 'text-halo-color': HALO[k], 'text-halo-width': 2, 'text-halo-blur': 0.3 } },
  ];
}

// Dunkelblaue Kontrastlinie um Gewässer, im Maßstab wie die Straßenkanten: Seen und Flussflächen bekommen eine Randlinie,
// Flüsse und Bäche (als Linien) einen dunkleren, etwas breiteren Saum unter der Wasserlinie.
// Linienbreite um `add` px verbreitern. Zoom-Ausdrücke dürfen nur oberste interpolate/step sein, also die Stützwerte einzeln anheben
// (Nullstellen bleiben null, damit der Saum dort einsetzt, wo die Linie selbst beginnt).
export function widen(w, add) {
  if (typeof w === 'number') return w + add;
  if (Array.isArray(w) && w[0] === 'interpolate') return w.map((x, i) => (i >= 4 && i % 2 === 0 && typeof x === 'number' && x > 0 ? x + add : x));
  return w;
}
export const WATER_EDGE = { light: '#1a4a85', dark: '#7db7f0' };
export function waterEdges(styled, dark) {
  const k = dark ? 'dark' : 'light', color = WATER_EDGE[k];
  const at = (id) => styled.findIndex((x) => x.id === id);
  // Flüsse und Bäche sind in OSM teils Fläche (breite Abschnitte), teils nur Mittellinie (schmale, ungemappte Abschnitte wie die Prüm).
  // Linie samt dunklem Saum liegt deshalb UNTER der Wasserfläche: wo eine Fläche ist, verdeckt sie die Linie (kein Strich mitten im Fluss),
  // wo keine ist, bleibt die Linie mit Saum sichtbar und der Fluss reißt nicht ab.
  const casings = [], tops = [];
  for (const id of ['water_stream', 'water_river']) {
    const i = at(id);
    if (i < 0) continue;
    const base = styled[i];
    styled.splice(i, 1);
    // Breite im Maßstab der Wirklichkeit (Fluss etwa 12 m, Bach etwa 3 m; Pixel verdoppeln sich je Zoomstufe), damit die Linie dort, wo nur
    // die Mittellinie gemappt ist, so breit aussieht wie die Wasserfläche daneben. Farbe wie die Fläche (paintWater), Saum wie ihr Rand.
    const width = id === 'water_river'
      ? ['interpolate', ['exponential', 2], ['zoom'], 8, 1.2, 12, 1.8, 14, 3.4, 16, 8, 19, 62]
      : ['interpolate', ['exponential', 2], ['zoom'], 8, 0.6, 12, 1, 14, 1.6, 16, 3, 19, 22];
    const round = { ...base.layout, 'line-cap': 'round', 'line-join': 'round' };
    casings.push({ ...base, id: `${id}_casing`, layout: round, minzoom: Math.max(base.minzoom ?? 0, 8),
      paint: { 'line-color': color, 'line-opacity': 0.9, 'line-width': widen(width, 2.2) } });
    tops.push({ ...base, layout: round, paint: { ...base.paint, 'line-width': width, 'line-opacity': 1 } });
  }
  // Reihenfolge von unten: dunkle Säume der Linien, dunkler Rand der Flächen (doppelt breit, unter der Fläche nur die Außenhälfte sichtbar),
  // Wasserfläche, zuletzt die hellen Mittellinien in Flächenfarbe. So verdeckt die helle Linie den Querstrich, wo eine gemappte Fläche endet
  // und die bloße Mittellinie weiterläuft: Fläche und Linie lesen sich als ein Fluss.
  const edge = { id: 'water_edge', type: 'line', source: 'basemap', 'source-layer': 'water', minzoom: 8, filter: ['==', ['geometry-type'], 'Polygon'],
    layout: { 'line-join': 'round' },
    paint: { 'line-color': color, 'line-opacity': 0.9, 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1, 12, 2.2, 16, 4.4] } };
  const w = at('water');
  if (w >= 0) styled.splice(w, 1, ...casings, edge, styled[w], ...tops);
  else styled.push(...casings, ...tops);
}

// Straßenschilder auf der Karte (Ausgangsbild: icons.js registerSigns): A blau, B gelb, L und K weiß. Text ist die Straßennummer
// aus OSM (ref, z. B. "A 60", "B 257", "L 4"); Mehrfachbezeichnungen mit Semikolon oder mehr als 8 Zeichen bleiben weg.
export function signLayers(dark) {
  const first = ['slice', ['get', 'ref'], 0, 1];
  const mk = (id, kinds, prefixes, image, text, minzoom) => ({
    id, type: 'symbol', source: 'basemap', 'source-layer': 'roads', minzoom,
    filter: ['all', ['in', ['get', 'kind'], ['literal', kinds]], ['has', 'ref'], ['in', first, ['literal', prefixes]],
      ['<=', ['length', ['get', 'ref']], 8], ['!', ['has', 'is_link']]],
    layout: { 'symbol-placement': 'line', 'symbol-spacing': 340, 'text-field': ['get', 'ref'], 'text-font': ['Noto Sans Regular'], 'text-size': 11,
      'icon-image': image, 'icon-text-fit': 'both', 'icon-text-fit-padding': [2, 5, 2, 5], 'icon-rotation-alignment': 'viewport',
      'text-rotation-alignment': 'viewport', 'text-keep-upright': false, 'text-padding': 8, 'icon-padding': 8 },
    paint: { 'text-color': text },
  });
  void dark;
  return [
    mk('bm-sign-autobahn', ['highway'], ['A'], 'sign-autobahn', '#ffffff', 8),
    mk('bm-sign-bundes', ['major_road'], ['B', 'N'], 'sign-bundes', '#111111', 10),
    mk('bm-sign-land', ['major_road'], ['L', 'K', 'D', 'C'], 'sign-land', '#111111', 12),
  ];
}

// Straßen ab Zoom 14 aus den feineren Archiven. region.pmtiles endet bei Zoom 13: dort fehlen kleine Straßen, Wege und fast alle
// Straßennamen (Kachelfeld `name` nur an Haupt- und Landstraßen). core.pmtiles (Zoom 14 und 15) und ring.pmtiles (Zoom 14, außerhalb der
// Kerne) führen dieselbe Schicht `roads` vollständig. Jede Straßenebene der Basiskarte (Linien und Namen) bekommt je Archiv einen Zwilling
// direkt hinter sich (gleiche Stapelfolge), das Original endet vor Zoom 14. Die Kachelfelder sind dieselben, Filter und Zeichnung gelten unverändert.
export const DETAIL_ZOOM = 14;
export function roadsFromDetail(styled, { core = false, ring = false } = {}) {
  if (!core && !ring) return styled;
  const out = [];
  for (const l of styled) {
    if (l.source !== 'basemap' || l['source-layer'] !== 'roads' || l.type === 'fill') { out.push(l); continue; }
    out.push({ ...l, maxzoom: Math.min(l.maxzoom ?? DETAIL_ZOOM, DETAIL_ZOOM) });
    for (const [on, suffix, source] of [[core, 'c', 'basemap-core'], [ring, 'r', 'basemap-ring']]) {
      if (!on || (l.maxzoom != null && l.maxzoom <= DETAIL_ZOOM)) continue;
      out.push({ ...l, id: `${l.id}_${suffix}`, source, minzoom: Math.max(l.minzoom ?? 0, DETAIL_ZOOM) });
    }
  }
  return out;
}
