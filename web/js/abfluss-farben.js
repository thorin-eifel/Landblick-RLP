// Ebene "Starkregen und Abfluss": Größenklassen, Farben, Texte und eine Faustformel. Reine Daten und Funktionen, kein DOM (node --test).
//
// Zweck:   Die Kacheln (tools/build_abfluss.py) tragen je Abflussbahn die Klasse k (Einzugsgebiet ab 1 ha · 5^k) und das Einzugsgebiet `ha`;
//          Senken tragen Volumen v (m³), größte Tiefe d (cm) und Fläche ha (Zehntel Hektar). Hier stehen Farbe und Wortlaut dazu.
// Haltung: Das ist eine Geländerechnung. Durchlässe, Brücken, Gräben, Kanalisation, Boden und Bewuchs kennt sie nicht. Alle Texte sagen das.
// Test:    tests/js/abfluss-farben.test.mjs
export const KLASSE_FAKTOR = 5;

export const ABFLUSS_KLASSEN = [
  { k: 0, farbe: { light: '#4fb0c6', dark: '#7fd0e2' }, label: 'ab 1 ha' },
  { k: 1, farbe: { light: '#3b97c9', dark: '#6cb8ea' }, label: 'ab 5 ha' },
  { k: 2, farbe: { light: '#2c7fd0', dark: '#5ea4f0' }, label: 'ab 25 ha' },
  { k: 3, farbe: { light: '#2565d6', dark: '#5a8af2' }, label: 'ab 1,25 km²' },
  { k: 4, farbe: { light: '#2a4bd0', dark: '#6a7df0' }, label: 'ab 6 km²' },
  { k: 5, farbe: { light: '#3a33b8', dark: '#8070e8' }, label: 'ab 31 km²' },
  { k: 6, farbe: { light: '#4b2a99', dark: '#9a78e0' }, label: 'ab 156 km²' },
];
export const SENKE_FARBE = { light: '#d9730d', dark: '#f0a050' };

/** Zusammengesetzter Ausdruck für MapLibre: Farbe nach Klasse (k). */
export function abflussFarbe(modus) {
  return ['match', ['get', 'k'], ...ABFLUSS_KLASSEN.flatMap(({ k, farbe }) => [k, farbe[modus]]), ABFLUSS_KLASSEN.at(-1).farbe[modus]];
}

const zahl = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 1 });
const ganz = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 0 });

/** "12 ha" oder "3,4 km²" */
export function flaecheText(ha) {
  return ha >= 100 ? `${zahl.format(ha / 100)} km²` : `${ganz.format(ha)} ha`;
}

/**
 * Faustformel Q = C · i · A (Rationalverfahren): Spitzenabfluss in m³/s für ein Einzugsgebiet von `ha` Hektar bei `mmProStunde` Regen.
 * C = 0,3 steht für gemischtes Land (Wiese, Acker, Wald); Siedlung und gesättigter Boden liegen höher. Größenordnung, keine Vorhersage;
 * sinnvoll nur für kleine Gebiete (bis einige km²).
 */
export function spitzenabfluss(ha, mmProStunde = 50, c = 0.3) {
  return c * (mmProStunde / 1000 / 3600) * ha * 10000;
}

/** "0,6 m³/s" oder "600 l/s" */
export function abflussText(q) {
  return q < 1 ? `${ganz.format(q * 1000)} l/s` : `${zahl.format(q)} m³/s`;
}

export const HINWEIS = 'Rechnung aus dem Geländemodell (Raster rund 6 m): Wasser fließt bergab, Senken werden aufgefüllt. Durchlässe, Brücken, Gräben, Kanalisation, Boden und Bewuchs kennt sie nicht. Keine Gefahrenkarte: Wo amtliche Starkregen- oder Hochwassergefahrenkarten vorliegen, gelten diese.';

/** Zeilen für das Meldungsfenster einer Abflussbahn. */
export function abflussPopup(p) {
  const ha = Number(p.ha);
  const q = spitzenabfluss(ha);
  return {
    titel: 'Abflussbahn (Geländeschätzung)',
    zeilen: [
      `Einzugsgebiet oberhalb: rund ${flaecheText(ha)}`,
      ha <= 600 ? `Zur Einordnung: bei 50 mm Regen in einer Stunde grob ${abflussText(q)} (Faustformel, Abflussbeiwert 0,3)` : 'Für so große Gebiete taugt die Faustformel nicht; Pegel und amtliche Vorhersagen gehen vor.',
    ],
  };
}

/** Zeilen für das Meldungsfenster einer Senke. */
export function senkePopup(p) {
  const v = Number(p.v), d = Number(p.d), ha = Number(p.ha) / 10;
  return {
    titel: 'Senke im Gelände (Geländeschätzung)',
    zeilen: [
      `Fasst rund ${ganz.format(v)} m³ bis zum Überlaufen, größte Tiefe etwa ${zahl.format(d / 100)} m, Fläche ${zahl.format(ha)} ha`,
      'Oft sind es Teiche, Steinbrüche oder Straßendämme, hinter denen ein Durchlass das Wasser abführt. Das Modell kennt keine Durchlässe.',
    ],
  };
}
