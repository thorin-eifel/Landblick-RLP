// Gebäudefarben nach Funktion (Attribut `klasse` der Hausumringe): reine Daten und ein Ausdruck, ohne DOM, damit node --test sie prüft.
// Quelle der Klassen: tools/build_gebaeude_rlp.py (KLASSEN); der Test tests/js/gebaeude-farben.test.mjs hält beide Listen gleich.
export const BUILDING = { light: '#800020', dark: '#9c2a4b' };
// Gebäudefunktion der Hausumringe (Attribut `klasse`, tools/build_gebaeude_rlp.py). Wohnhäuser behalten das Weinrot, die übrigen Klassen
// weichen davon ab. Gebäude ohne Klasse (OSM außerhalb von Rheinland-Pfalz) und "sonst" bleiben weinrot.
export const BUILDING_KLASSEN = [
  ['wohnen', 'Wohngebäude', BUILDING],
  ['wirtschaft', 'Wirtschaft und Gewerbe (Schuppen, Scheunen, Hallen)', { light: '#a8741a', dark: '#c99a45' }],
  ['garage', 'Garagen und Parkhäuser', { light: '#6e6e6e', dark: '#a0a0a0' }],
  ['ueberdachung', 'Überdachungen', { light: '#9a9a9a', dark: '#767676' }],
  ['technik', 'Versorgung und Technik', { light: '#1f6f8b', dark: '#5eb0cc' }],
  ['oeffentlich', 'Öffentliche Zwecke (Verwaltung, Schule, Feuerwehr ...)', { light: '#5b3a8c', dark: '#a68ad6' }],
  ['religion', 'Kirchen, Kapellen, Friedhofsgebäude', { light: '#c2410c', dark: '#f08a4b' }],
  ['sonst', 'Sonstige', BUILDING],
];
/** Füllfarbe der Gebäude nach Klasse als MapLibre-Ausdruck (Standard: Weinrot, auch für Gebäude ohne Klasse). */
export function buildingFill(k) {
  const paare = BUILDING_KLASSEN.filter(([id, , c]) => id !== 'wohnen' && id !== 'sonst' && c[k]).flatMap(([id, , c]) => [id, c[k]]);
  return ['match', ['get', 'klasse'], ...paare, BUILDING[k]];
}
