/*
 * Eigene Darstellung: Farben und Symbole des Benutzers auf ein Farb-Schema oder einen Symbolsatz legen.
 *
 * Zweck:    Aus einem Ausgangs-Skin (skins.js) und einer Liste von Überschreibungen entsteht ein Skin 'eigen' (Palette oder Zeichensatz).
 *           Reine Datenfunktionen, kein DOM, kein Speicher; in Node testbar (tests/js/anpassen.test.mjs).
 * Eingaben: nur Farben im Format #rrggbb und Schalter; alles andere wird verworfen (kein Stil-Ausdruck, kein Text vom Benutzer im Stil).
 * Grenzen:  Palette: eine Ansicht (hell oder dunkel) je Überschreibung; Zeichensätze kennen nur hell.
 */
import { ARTS } from './zeichensaetze.js';
import { skinById } from './skins.js';

const HEX = /^#[0-9a-f]{6}$/i;
export const gueltigeFarbe = (c) => typeof c === 'string' && HEX.test(c);

/** Hex um Faktor k abdunkeln (k < 1) oder aufhellen (k > 1). */
export function tone(hex, k) {
  const n = parseInt(hex.slice(1), 16);
  const f = (v) => Math.max(0, Math.min(255, Math.round(v * k)));
  return `#${[(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => f(v).toString(16).padStart(2, '0')).join('')}`;
}

/** Felder des Formulars je Methode: Schlüssel, Beschriftung. */
export const FARBFELDER = {
  tint: [['bg', 'Rand und Hintergrund'], ['earth', 'Boden'], ['water', 'Wasser'], ['forest', 'Wald'], ['green', 'Wiese und Park'], ['farm', 'Acker'],
    ['roadMajor', 'Hauptstraßen'], ['roadMinor', 'Nebenstraßen'], ['bld', 'Gebäude'], ['ink', 'Schrift']],
  art: [['paper', 'Papier'], ['ink', 'Tinte'], ['water', 'Wasser'], ['forest', 'Wald']],
};

/** Aktuelle Farben eines Skins für die Felder des Formulars (Vorbelegung). */
export function farbenVon(methode, base) {
  if (methode === 'art') {
    const a = ARTS[base];
    return a ? { paper: a.med.paper, ink: a.med.ink, water: a.med.water, forest: a.land.forest[0] } : {};
  }
  const p = base;   // Palette einer Ansicht
  return { bg: p.bg, earth: p.earth, water: p.water, forest: p.forest, green: p.green, farm: p.farm, roadMajor: p.roads.major[0], roadMinor: p.roads.minor[0], bld: p.bld[0], ink: p.ink };
}

const sauber = (ov) => Object.fromEntries(Object.entries(ov ?? {}).filter(([, v]) => gueltigeFarbe(v)));

/** Palette einer Ansicht mit Überschreibungen; Konturen leiten sich aus der Füllung ab. */
export function eigenePalette(base, ov) {
  const o = sauber(ov), p = structuredClone(base);
  for (const k of ['bg', 'earth', 'forest', 'green', 'farm', 'ink']) if (o[k]) p[k] = o[k];
  if (o.water) { p.water = o.water; p.edge = tone(o.water, 0.8); p.waterInk = tone(o.water, 0.4); }
  if (o.bld) p.bld = [o.bld, p.bld[1]];
  if (o.roadMajor) { p.roads.hw = [o.roadMajor, tone(o.roadMajor, 0.65)]; p.roads.major = [tone(o.roadMajor, 1.08), tone(o.roadMajor, 0.7)]; }
  if (o.roadMinor) for (const k of ['mid', 'minor', 'other']) p.roads[k] = [o.roadMinor, tone(o.roadMinor, 0.75)];
  return p;
}

/** Zeichensatz mit Überschreibungen: Papier, Tinte, Wasser, Wald und die Schalter Zierde und Fabelwesen. */
export function eigenerZeichensatz(baseId, ov, flags = {}) {
  const a = structuredClone(ARTS[baseId] ?? ARTS['alte-karte']), o = sauber(ov);
  if (o.paper) {
    Object.assign(a.med, { bg: tone(o.paper, 0.96), paper: o.paper });
    Object.assign(a.zeichen, { paper: o.paper, wash: `${o.paper}d9` });
    a.pig.paper = o.paper; a.colors.bg = o.paper; a.colors.white = o.paper; a.iconStyle.light = o.paper;
  }
  if (o.ink) {
    Object.assign(a.med, { ink: o.ink, road: tone(o.ink, 1.6) });
    a.zeichen.ink = o.ink; a.pig.ink = o.ink; a.iconStyle.dark = o.ink; a.cliff.ink = o.ink; a.flow.arrow = o.ink;
    Object.assign(a.colors, { fg: o.ink, ink: o.ink, black: o.ink, line: tone(o.ink, 1.6) });
  }
  if (o.water) { a.med.water = o.water; a.med.edge = tone(o.water, 0.65); a.zeichen.water = tone(o.water, 0.65); a.pig.water = o.water; }
  if (o.forest) a.land.forest = [o.forest, a.land.forest[1]];
  if (typeof flags.decor === 'boolean') a.decor = flags.decor;
  if (typeof flags.fauna === 'boolean') a.fauna = flags.fauna;
  a.name = 'Eigene Zeichnung';
  return a;
}

/**
 * Skin 'eigen' aus Schema, Symbolsatz und Überschreibungen.
 * eigen = { farben: { light: {}, dark: {} }, art: {}, patterns: bool|null, decor: bool|null, fauna: bool|null }
 * Liefert { skin, art } (art nur bei Symbolsatz; muss unter ARTS.eigen eingetragen werden) oder null, wenn nichts anzupassen ist.
 */
export function baueEigenenSkin(schema, symbole, eigen) {
  if (symbole && symbole !== 'landblick') {
    const art = eigenerZeichensatz(skinById(symbole).art, eigen.art, eigen);
    return { skin: { name: 'Eigene Zeichnung', hinweis: `Angepasst nach „${skinById(symbole).name}“`, tint: null, art: 'eigen', dunkel: false }, art };
  }
  const base = skinById(schema).tint ?? skinById('mountain-view').tint;
  const skin = { name: 'Eigenes Schema', hinweis: `Angepasst nach „${skinById(schema).name}“`,
    tint: { light: eigenePalette(base.light, eigen.farben?.light), dark: eigenePalette(base.dark, eigen.farben?.dark), patterns: typeof eigen.patterns === 'boolean' ? eigen.patterns : base.patterns !== false } };
  return { skin, art: null };
}
