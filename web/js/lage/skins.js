// Darstellungen (Skins) der Basiskarte.
//
// Ein Skin ist ein Eintrag der Liste SKINS. Es gibt zwei Methoden, beide nebeneinander:
//   tint  Farbpalette: skinize() färbt die fertige Layerliste um (Boden, Wasser, Bewuchs, Straßen nach Klasse, Gebäude, Schrift);
//         Geometrie und Ebenen bleiben. Jede Palette gibt es für hell und dunkel.
//   art   Zeichensatz (zeichensaetze.js): tauscht Texturen, Symbole, Schrift und Zierde (mittelalter.js medievalize, medieval.js),
//         dazu die eigenen Farben des Satzes. Zeichensätze kennen nur hell (`dunkel: false`).
// Landblick ist die Grundzeichnung ohne beides. Ein Skin darf tint und art tragen; art hat dann Vorrang.
//
// Namen: Stilrichtungen, benannt nach dem Ort, an dem bekannte Kartenanbieter sitzen. Es sind eigene Zeichnungen in der Anmutung
// der jeweiligen Gattung, keine Nachbauten von Produkten, ohne Markennamen, Zeichen oder Schriften Dritter.
//
// Dieses Modul kennt weder Karte noch DOM und ist deshalb in Node testbar (tests/js/skins.test.mjs).

/** Bewuchsklassen aus stil.js (LAND) auf die fünf Farben der Palette abgebildet. */
export const LAND_GROUP = { forest: 'forest', meadow: 'green', grass: 'green', orchard: 'green', allotment: 'green', cemetery: 'green',
  scrub: 'scrub', heath: 'scrub', farmland: 'farm', vineyard: 'farm', wetland: 'wet', rock: 'rock', sand: 'rock' };

// Straßenklassen: Füllung und Kontur je [fill, casing]
const road = (hw, major, mid, minor, other, rail) => ({ hw, major, mid, minor, other, rail });

export const SKINS = [
  { id: 'landblick', name: 'Landblick', hinweis: 'Grundzeichnung von Landblick', tint: null },
  { id: 'alte-karte', name: 'Alte Karte', hinweis: 'Pergament, Tinte und Fabelwesen, um 1450 (Zeichensatz, nur hell)', tint: null, art: 'alte-karte', dunkel: false },
  { id: 'mountain-view', name: 'Mountain View', hinweis: 'Straßenkarte: ruhige Flächen, Straßen nach Klasse',
    tint: {
      light: { bg: '#e8e6e1', earth: '#f2efe9', water: '#a8d4e6', edge: '#8abbd1', waterInk: '#2f6f96', ink: '#3c4043', halo: 'rgba(255,255,255,0.92)',
        forest: '#bfe0b2', green: '#d3ebc7', scrub: '#cfe5c0', farm: '#f0ecdf', wet: '#c4e3d4', rock: '#dedbd4', landOp: 0.9, bld: ['#e4dfd6', 0.9],
        roads: road(['#fbc56b', '#dd9a2b'], ['#ffe49b', '#d8b25a'], ['#ffffff', '#c9c4b9'], ['#ffffff', '#d6d1c6'], ['#fafafa', '#d6d1c6'], '#b7b2a8') },
      dark: { bg: '#161b24', earth: '#222833', water: '#16263c', edge: '#2b4463', waterInk: '#8ab4f8', ink: '#e8eaed', halo: 'rgba(34,40,51,0.92)',
        forest: '#1f3a2e', green: '#254334', scrub: '#26402f', farm: '#2a2d2b', wet: '#1f3d3a', rock: '#33363a', landOp: 0.9, bld: ['#2d3440', 0.9],
        roads: road(['#a8782c', '#5d4217'], ['#8a6f3c', '#4d3d1f'], ['#4b5260', '#1a1e26'], ['#3e4553', '#1a1e26'], ['#363c48', '#1a1e26'], '#4a505c') },
      patterns: false } },
  { id: 'cupertino', name: 'Cupertino', hinweis: 'Straßenkarte: weich, kräftiges Grün und Wasser',
    tint: {
      light: { bg: '#ece8df', earth: '#f6f2ea', water: '#8cc3ec', edge: '#6fa9d6', waterInk: '#1c5f9c', ink: '#1d1d1f', halo: 'rgba(255,255,255,0.92)',
        forest: '#b5dc98', green: '#c9e8ab', scrub: '#c2e0a2', farm: '#efe8d4', wet: '#b6e0cf', rock: '#ddd8cc', landOp: 0.95, bld: ['#e2dccf', 0.95],
        roads: road(['#f6c85a', '#c99a2c'], ['#fbe08c', '#cdb164'], ['#ffffff', '#cfc8b8'], ['#ffffff', '#ddd6c6'], ['#ffffff', '#ddd6c6'], '#b9b2a2') },
      dark: { bg: '#10141a', earth: '#1c2128', water: '#12263f', edge: '#27507c', waterInk: '#79b4ff', ink: '#f5f5f7', halo: 'rgba(28,33,40,0.92)',
        forest: '#1b3a28', green: '#21442f', scrub: '#244531', farm: '#26292a', wet: '#1b3f3b', rock: '#30343a', landOp: 0.95, bld: ['#2a2f38', 0.95],
        roads: road(['#9a7424', '#503b10'], ['#85703a', '#40331a'], ['#454c58', '#161a20'], ['#3a404b', '#161a20'], ['#323843', '#161a20'], '#474d58') },
      patterns: false } },
  { id: 'amsterdam', name: 'Amsterdam', hinweis: 'Navigation: hoher Kontrast, Straßen im Vordergrund, dunkel als Nachtmodus',
    tint: {
      light: { bg: '#dcdcd6', earth: '#f1f1ec', water: '#7fb7e6', edge: '#4f8fc7', waterInk: '#134f86', ink: '#101418', halo: 'rgba(255,255,255,0.95)',
        forest: '#cfe5bd', green: '#dcedcc', scrub: '#d6e8c4', farm: '#ecebdf', wet: '#cde6dc', rock: '#dad8d0', landOp: 0.85, bld: ['#d4d2ca', 0.9],
        roads: road(['#ff9e3d', '#a85a0c'], ['#ffd166', '#9c7a1c'], ['#ffffff', '#8c8c86'], ['#ffffff', '#a9a9a2'], ['#f3f3ee', '#a9a9a2'], '#8d8d86') },
      dark: { bg: '#0d0f12', earth: '#16191d', water: '#0c2238', edge: '#1f5d94', waterInk: '#7cc0ff', ink: '#ffffff', halo: 'rgba(22,25,29,0.95)',
        forest: '#14301f', green: '#183823', scrub: '#19381f', farm: '#1d1f1c', wet: '#143733', rock: '#272a2e', landOp: 0.85, bld: ['#23272d', 0.9],
        roads: road(['#f2a03a', '#0b0c0e'], ['#ffd166', '#0b0c0e'], ['#6b7a90', '#0b0c0e'], ['#4c5666', '#0b0c0e'], ['#3b4452', '#0b0c0e'], '#5a6270') },
      patterns: false } },
  { id: 'olathe', name: 'Olathe', hinweis: 'Outdoor: Gelände und Bewuchs im Vordergrund, Wege betont',
    tint: {
      light: { bg: '#e3dcc8', earth: '#f1ecdc', water: '#9cc9e8', edge: '#5f9ac6', waterInk: '#1d5c93', ink: '#2b2418', halo: 'rgba(250,246,232,0.92)',
        forest: '#a9cf93', green: '#cfe3a8', scrub: '#c3d79a', farm: '#f3e9c2', wet: '#a9d6c2', rock: '#d3c8b2', landOp: 0.85, bld: ['#d8cdb4', 0.9],
        roads: road(['#e6a550', '#a6702a'], ['#f3d28a', '#b99a52'], ['#fffbf0', '#b9ad92'], ['#fffbf0', '#c8bd9f'], ['#a8794a', '#a8794a'], '#8a8272') },
      dark: { bg: '#15180f', earth: '#1f2318', water: '#122a3d', edge: '#2d6288', waterInk: '#86c0ee', ink: '#efe9d6', halo: 'rgba(31,35,24,0.92)',
        forest: '#2a4a24', green: '#35522a', scrub: '#3a4d2a', farm: '#3a3820', wet: '#24493f', rock: '#443f33', landOp: 0.85, bld: ['#3a3628', 0.9],
        roads: road(['#a8742a', '#4d3410'], ['#8f7a3e', '#40331a'], ['#5a553f', '#1a1a10'], ['#4a4634', '#1a1a10'], ['#8a6038', '#8a6038'], '#5e5a48') },
      patterns: true } },
  { id: 'ostfildern', name: 'Ostfildern', hinweis: 'Stadtplan: warmes Papier, gelbe Hauptstraßen, rosa Bebauung',
    tint: {
      light: { bg: '#efe8c4', earth: '#fbf6dc', water: '#b3dff5', edge: '#6aaed6', waterInk: '#17639c', ink: '#2a2a2a', halo: 'rgba(255,252,236,0.92)',
        forest: '#cfe8b0', green: '#dcefc0', scrub: '#d6eab8', farm: '#f6efc8', wet: '#c6e8d6', rock: '#e4dfcb', landOp: 0.95, bld: ['#f0c8c0', 1],
        roads: road(['#f0803c', '#8a3d12'], ['#ffe45e', '#9a8423'], ['#fff7b0', '#b5a54a'], ['#ffffff', '#c4b98a'], ['#fffdf0', '#c4b98a'], '#8a8468') },
      dark: { bg: '#1a1710', earth: '#24211a', water: '#14293a', edge: '#2f6a94', waterInk: '#86c0ee', ink: '#f3eed8', halo: 'rgba(36,33,26,0.92)',
        forest: '#2a4025', green: '#31492a', scrub: '#34462a', farm: '#38341f', wet: '#254a40', rock: '#403c30', landOp: 0.95, bld: ['#4a3430', 1],
        roads: road(['#b85a22', '#4a1d08'], ['#a08c20', '#3d3408'], ['#6a6430', '#221f0e'], ['#4e4a38', '#221f0e'], ['#423e30', '#221f0e'], '#5c5846') },
      patterns: false } },
  { id: 'oxford', name: 'Oxford', hinweis: 'Federzeichnung: schwarze Tusche auf hellem Papier, gezeichnete Bäume, Hügel und Häuser (Zeichensatz, nur hell)',
    tint: null, art: 'federzeichnung', dunkel: false },
];

export const DEFAULT_SKIN = 'landblick';
export const skinById = (id) => SKINS.find((s) => s.id === id) ?? SKINS[0];
/** Palette des Skins für die Ansicht oder null (Landblick, Alte Karte). */
export const tintOf = (id, dark) => { const t = skinById(id).tint; return t ? t[dark ? 'dark' : 'light'] : null; };
export const wantsPatterns = (id) => skinById(id).tint?.patterns !== false;

/** Klasse einer Straßenebene des Stils (roads_bridges_highway_casing_late → hw) oder null. */
export function roadClass(id) {
  const m = /^roads_(?:(?:bridges|tunnels)_)?(highway|link|major|medium|minor_service|minor|other|rail)(_casing(?:_early|_late)?)?$/.exec(id);
  if (!m) return null;
  const cls = { highway: 'hw', link: 'hw', major: 'major', medium: 'mid', minor_service: 'minor', minor: 'minor', other: 'other', rail: 'rail' }[m[1]];
  return { cls, casing: !!m[2] };
}

const setPaint = (l, p) => ({ ...l, paint: { ...l.paint, ...p } });

/** Linienbreite (Zahl oder Ausdruck) mit k multiplizieren; Zoom-Ausdrücke dürfen "zoom" nur als obersten Eingang führen, also die Stützwerte einzeln. */
export function scaleWidth(w, k) {
  if (typeof w === 'number') return w * k;
  if (Array.isArray(w) && w[0] === 'interpolate') return w.map((x, i) => (i >= 4 && i % 2 === 0 ? scaleWidth(x, k) : x));
  return ['*', k, w];
}

/**
 * Färbt die Layerliste (nach labelsAndBuildings, waterEdges, peakLayers) mit der Palette um.
 * `opts.patterns`: false entfernt die Flächensignaturen (land-*-pat).
 */
export function skinize(styled, p, opts = {}) {
  const out = [];
  for (const l of styled) {
    const id = l.id;
    if (/^land-[a-z]+-pat$/.test(id) && opts.patterns === false) continue;
    let x = l;
    if (id === 'background') x = { ...l, paint: { ...l.paint, 'background-color': p.bg } };
    else if (id === 'earth') x = setPaint(l, { 'fill-color': p.earth });
    else if (id === 'landcover') x = setPaint(l, { 'fill-color': p.green });
    else if (id === 'landuse_urban_green') x = setPaint(l, { 'fill-color': p.green });
    else if (id === 'water') x = setPaint(l, { 'fill-color': p.water });
    else if (id === 'water_edge' || /^water_(stream|river)_casing$/.test(id)) x = setPaint(l, { 'line-color': p.edge });
    else if (id === 'water_stream' || id === 'water_river') x = setPaint(l, { 'line-color': p.water });
    else if (id === 'buildings') x = setPaint(l, { 'fill-color': p.bld[0], 'fill-opacity': p.bld[1], 'fill-outline-color': p.roads.rail });
    else if (id.startsWith('land-') && l.type === 'fill' && LAND_GROUP[id.slice(5)]) {
      x = setPaint(l, { 'fill-color': p[LAND_GROUP[id.slice(5)]], 'fill-opacity': p.landOp });
    } else {
      const r = roadClass(id);
      if (r && l.type === 'line') {
        const c = p.roads[r.cls];
        x = setPaint(l, { 'line-color': r.cls === 'rail' ? c : c[r.casing ? 1 : 0] });
        if (p.inkRoads && r.cls !== 'rail') {   // Federzeichnung: keine Konturen, feine Linie, Nebenwege gestrichelt
          if (r.casing) x = setPaint(x, { 'line-opacity': 0 });
          else {
            x = setPaint(x, { 'line-width': scaleWidth(l.paint?.['line-width'] ?? 1, p.inkRoads) });
            if (r.cls === 'minor' || r.cls === 'other') x = setPaint(x, { 'line-dasharray': r.cls === 'other' ? [2, 2] : [6, 2] });
          }
        }
      }
    }
    if (x.layout?.['text-font']) {
      const water = /^water_/.test(x.id);
      x = setPaint(x, { 'text-color': water ? p.waterInk : p.ink, 'text-halo-color': p.halo });
      if (p.spacing && /^places_/.test(x.id)) x = { ...x, layout: { ...x.layout, 'text-letter-spacing': p.spacing } };
    }
    out.push(x);
  }
  return out;
}
