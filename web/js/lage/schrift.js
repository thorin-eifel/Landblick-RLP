/*
 * Schriftwahl für die Kartenbeschriftung (Darstellung → Schrift).
 *
 * Zweck:    Alle Kartenbeschriftungen (Orte, Straßen, Höhenlinien, Datenebenen) in einer gewählten Schrift zeigen.
 *           "Standard" lässt jede Ebene bei der Schrift, die Darstellung und Zeichensatz vorgeben.
 * Quellen:  - mitgelieferte Schriften (web/fonts/woff2, SIL OFL 1.1, Lizenzen in web/fonts/README.txt), per MapLibre "font-faces"
 *             geladen; die Glyphen entstehen im Browser, es gibt keine Glyphen-PBF-Dateien dafür.
 *           - Schriften auf dem Gerät: Namen aus queryLocalFonts() (Chromium, nur nach Zustimmung) oder frei getippt.
 *             Der Browser zeichnet sie lokal; es wird nichts hochgeladen oder gespeichert.
 * Grenzen:  Eine Schrift für alle Beschriftungen (kein Fett/Kursiv je Ebene). Ohne Speicher: nach dem Neuladen gilt wieder Standard.
 */
import { map, state } from './zustand.js';

export const AUTO = 'auto';

/** Mitgelieferte Schriften: Name = Stack-Name in text-font, Datei unter web/fonts/woff2. */
export const BUNDLED = [
  { name: 'Noto Sans Regular', label: 'Noto Sans (sachlich)', file: null },   // Glyphen-PBF liegen bei
  { name: 'Lora', label: 'Lora (Serife, ruhig)', file: 'lora.woff2' },
  { name: 'Alegreya', label: 'Alegreya (Serife, lebendig)', file: 'alegreya.woff2' },
  { name: 'Cinzel', label: 'Cinzel (römische Versalien)', file: 'cinzel.woff2' },
  { name: 'IM Fell English', label: 'IM Fell English (alter Buchdruck)', file: 'im-fell-english.woff2' },
  { name: 'Almendra', label: 'Almendra (Kalligrafie)', file: 'almendra.woff2' },
  { name: 'Uncial Antiqua', label: 'Uncial Antiqua (Unziale)', file: 'uncial-antiqua.woff2' },
  { name: 'Pirata One', label: 'Pirata One (Fraktur)', file: 'pirata-one.woff2' },
  { name: 'Caveat', label: 'Caveat (Handschrift)', file: 'caveat.woff2' },
];

const orig = new Map();   // Layer-ID → ursprüngliche text-font-Liste
let local = [];           // Namen lokaler Schriften (queryLocalFonts oder getippt)
let applying = false;

export const localNames = () => local.slice();

/** Einen Schriftnamen für text-font bereinigen: Länge, keine Steuerzeichen, keine Kommas (sonst Stack-Trennung). */
export function cleanFontName(s) {
  const t = String(s ?? '').replace(/[\u0000-\u001f\u007f,"'{}<>\\/]/g, '').replace(/\s+/g, ' ').trim();
  return t.length >= 2 && t.length <= 80 ? t : '';
}

/** Lokale Namen übernehmen: bereinigt, ohne Doppelte (ohne Groß-/Kleinschreibung) und ohne die mitgelieferten. */
export function setLocalNames(names) {
  const seen = new Set(BUNDLED.map((b) => b.name.toLowerCase()));
  local = [];
  for (const n of names) {
    const c = cleanFontName(n);
    if (c && !seen.has(c.toLowerCase())) { seen.add(c.toLowerCase()); local.push(c); }
  }
  local.sort((a, b) => a.localeCompare(b, 'de'));
  return local;
}

/** Familien aus queryLocalFonts(): nur die Familiennamen, einmal je Familie. Wirft, wenn die API fehlt oder abgelehnt wird. */
export async function queryLocalFamilies(api = globalThis.queryLocalFonts) {
  if (typeof api !== 'function') throw new Error('nicht unterstützt');
  const list = await api.call(globalThis);
  return setLocalNames(list.map((f) => f.family));
}

/** MapLibre-"font-faces" für die mitgelieferten Schriften (URL absolut zur Seite). */
export function fontFaces(base = location.href) {
  const out = {};
  for (const b of BUNDLED) if (b.file) out[b.name] = [{ url: new URL(`fonts/woff2/${b.file}`, base).href }];
  return out;
}

export function registerFonts() {
  if (typeof map.setFontFaces === 'function') map.setFontFaces(fontFaces());
}

/** Gewählte Schrift auf alle Beschriftungs-Layer legen. AUTO stellt die ursprünglichen Schriften wieder her. */
export function applyFont(id = state.schrift) {
  if (!map || applying) return;
  applying = true;
  try {
    const want = id && id !== AUTO ? id : null;
    for (const l of map.getStyle().layers) {
      if (l.type !== 'symbol') continue;
      const cur = map.getLayoutProperty(l.id, 'text-font');
      if (!Array.isArray(cur) || cur[0] === 'literal') continue;   // Ausdrücke bleiben unangetastet
      if (!orig.has(l.id)) orig.set(l.id, cur);
      const next = want ? [want] : orig.get(l.id);
      if (next && JSON.stringify(cur) !== JSON.stringify(next)) map.setLayoutProperty(l.id, 'text-font', next);
    }
  } finally { applying = false; }
}

/** Beim Neuaufbau der Basiskarte entstehen die bm-Layer neu (mit Standardschrift): ihre gemerkten Ursprünge verwerfen. */
export function resetFontMemory() { for (const k of [...orig.keys()]) if (k.startsWith('bm-')) orig.delete(k); }

export function initFont() {
  // Der Stil lädt asynchron und würde früh gesetzte font-faces überschreiben: erst nach dem Laden anmelden
  if (map.isStyleLoaded()) registerFonts(); else map.once('load', registerFonts);
  map.on('styledata', () => { if (state.schrift && state.schrift !== AUTO) applyFont(); });   // später hinzugefügte Layer (Orte, Natur, Infrastruktur)
}
