// Zeichensätze: die zweite Art von Darstellung (neben den Farbpaletten in skins.js). Ein Zeichensatz tauscht nicht nur Farben, sondern
// Flächenmuster (Bäume, Furchen, Schilf), Hügel-, Wellen- und Siedlungszeichen, Gebäudeschraffur, Schrift und Zierde. Die Zeichnungen entstehen
// im Browser auf Canvas (medieval.js, icons.js, infra.js) und lesen ihre Farben aus den Objekten, die zeichensatz.js beim Wechsel füllt.
// Dieses Modul ist reine Daten und in Node testbar. Standard ist die Alte Karte (die Werte stehen auch als Anfangswerte in den Modulen).

/** Pflichtfelder jedes Zeichensatzes; tests/js/zeichensaetze.test.mjs prüft sie. */
export const ART_KEYS = ['name', 'font', 'decor', 'fauna', 'med', 'zeichen', 'pig', 'colors', 'iconStyle', 'land', 'ramp', 'relief', 'flow', 'cliff'];

export const ARTS = {
  'alte-karte': {
    name: 'Alte Karte', font: 'Grenze Gotisch Regular', decor: true, fauna: true,
    // Karte (mittelalter.js MED): Grund, Papier, Tinte, Wege, Wasser, Rand, Saum, Gewässernamen
    med: { bg: '#d9c28c', paper: '#e8d6a6', ink: '#3a2614', road: '#7a5530', water: '#a6bcb0', edge: '#58726a', halo: 'rgba(238,224,182,0.92)', waterLabel: '#1f4f86' },
    // Zeichen (medieval.js MED)
    zeichen: { ink: '#3a2614', paper: '#efe0b0', stone: '#d9c68f', roof: '#a33a22', water: '#58726a', wash: 'rgba(239,224,176,0.82)',
      hillFill: 'rgba(239,224,176,0.7)', hillFillFine: 'rgba(239,224,176,0.8)', bldTint: 'rgba(122,85,48,0.28)' },
    pig: { ink: '#3a2614', paper: '#efe0b0', stone: '#d9c68f', roof: '#a33a22', water: '#8fb0ad' },
    colors: { bg: '#efe0b0', line: '#7a5530', fg: '#3a2614', muted: '#7a6850', critical: '#7a1020', warning: '#b03a22', notice: '#b7791f',
      yellow: '#d9a520', orange: '#c8661c', red: '#a33a22', black: '#2b1d10', info: '#3f6b72', accent: '#a33a22', white: '#efe0b0', ink: '#3a2614' },
    iconStyle: { light: '#efe0b0', dark: '#3a2614' },
    land: { forest: ['#8fa672', 0.55], meadow: ['#d6c88c', 0.15], scrub: ['#a9a66e', 0.35], farmland: ['#e3cf94', 0.2], wetland: ['#a9bdb0', 0.55], rock: ['#a89678', 0.55] },
    ramp: [[100, '#e6d6a4'], [300, '#dcc790'], [500, '#cfb27c'], [700, '#bf9a68']],
    relief: { opacity: 0.45, shadow: '#3f2a12', high: '#f3e4b8', accent: '#5e4220', hill: 0.72, contour: 'rgba(110,70,34,0.5)', contourMajor: 'rgba(84,52,24,0.8)', label: '#4a2f16', halo: 'rgba(238,224,182,0.9)' },
    flow: { dash: '#efe0b0', arrow: '#3a2614', wave: '#efe0b0' },
    cliff: { ink: '#3a2614', scree: '#7a5530', wall: '#b39d73' },
  },
  // Federzeichnung: schwarze Tusche auf hellem Papier, nüchterne Schrift, ohne Ungeheuer und Windrose; dieselben Zeichenformen, andere Hand
  federzeichnung: {
    name: 'Federzeichnung', font: 'Noto Sans Regular', decor: false, fauna: false,
    med: { bg: '#e6dfcb', paper: '#f3eee0', ink: '#1c1a17', road: '#3b3631', water: '#d3dcd9', edge: '#4d5d66', halo: 'rgba(243,238,224,0.92)', waterLabel: '#2f4a5a' },
    zeichen: { ink: '#1c1a17', paper: '#f3eee0', stone: '#ddd7c6', roof: '#2b2723', water: '#4d5d66', wash: 'rgba(243,238,224,0.85)',
      hillFill: 'rgba(243,238,224,0.8)', hillFillFine: 'rgba(243,238,224,0.85)', bldTint: 'rgba(60,55,48,0.2)' },
    pig: { ink: '#1c1a17', paper: '#f3eee0', stone: '#ddd7c6', roof: '#2b2723', water: '#8fa6ad' },
    colors: { bg: '#f3eee0', line: '#3b3631', fg: '#1c1a17', muted: '#6b655a', critical: '#8a1020', warning: '#b04a1c', notice: '#a8820f',
      yellow: '#d9a520', orange: '#c8661c', red: '#a33a22', black: '#1c1a17', info: '#3f5f6a', accent: '#8a1020', white: '#f3eee0', ink: '#1c1a17' },
    iconStyle: { light: '#f3eee0', dark: '#1c1a17' },
    land: { forest: ['#cfd8bf', 0.5], meadow: ['#e8e4cc', 0.12], scrub: ['#d8d9bb', 0.3], farmland: ['#efe7cc', 0.15], wetland: ['#cfdbd0', 0.5], rock: ['#d6cfbd', 0.5] },
    ramp: [[100, '#f1ebd8'], [300, '#ebe3cb'], [500, '#e3d9bd'], [700, '#d9cdae']],
    relief: { opacity: 0.35, shadow: '#2a2620', high: '#fbf8ee', accent: '#3a352c', hill: 0.6, contour: 'rgba(60,55,48,0.45)', contourMajor: 'rgba(40,36,30,0.75)', label: '#2a2620', halo: 'rgba(243,238,224,0.9)' },
    flow: { dash: '#f3eee0', arrow: '#1c1a17', wave: '#f3eee0' },
    cliff: { ink: '#1c1a17', scree: '#6b655a', wall: '#cfc8b4' },
  },
};
export const artOf = (id) => ARTS[id] ?? null;
