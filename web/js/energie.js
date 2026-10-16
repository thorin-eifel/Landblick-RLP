// Energie: Kraftwerke, Solarparks, Umspannwerke, Transformatoren und Hochspannungsleitungen (110, 220, 380 kV).
// Daten: energie.json bzw. Zellenart 'energie' (OpenStreetMap, ODbL; Solarparks im Norden zusätzlich amtlich aus dem Raumordnungskataster SGD Nord, dl-de/by-2.0).
// Windräder stehen in infrastruktur.json und teilen sich Zeichen und Ebene mit der übrigen Infrastruktur (infra.js).
// Dieses Modul ist rein (keine Karte, kein DOM) und per Test prüfbar: tests/js/energie.test.mjs. Die Kartenanbindung steht in lage/energie.js.
export const ENERGIE_SWITCH = { enSolar: 'solar', enPlant: 'plant', enSub: 'substation', enTrafo: 'transformer', enLine: 'line' };
export const ENERGIE_WORD = { solar: 'Solarpark', plant: 'Kraftwerk', substation: 'Umspannwerk', transformer: 'Transformator', line: 'Hochspannungsleitung' };
export const ENERGIE_COLOR = { solar: '#a16207', plant: '#7c2d12', substation: '#5b21b6', transformer: '#9d174d' };
export const LINE_COLOR = { 110: '#b45309', 220: '#c2410c', 380: '#be123c' };
export const SOURCE_WORD = { gas: 'Gas', coal: 'Kohle', oil: 'Öl', hydro: 'Wasserkraft', nuclear: 'Kernkraft', biomass: 'Biomasse', waste: 'Müllverbrennung', geothermal: 'Erdwärme', battery: 'Batteriespeicher', other: '' };
export const STATE_WORD = { netz: 'am Netz', genehmigt: 'genehmigt, nicht gebaut', beantragt: 'beantragt' };
export const PLAQUE_KINDS = ['solar', 'plant', 'substation', 'transformer'];

/** Arten, deren Schalter an sind. Auf der Karte um 1450 gibt es keine davon. */
export function energieKinds(layers, medieval = false) {
  if (medieval) return [];
  return Object.entries(ENERGIE_SWITCH).filter(([sw]) => layers?.[sw]).map(([, kind]) => kind);
}
export const energieAn = (layers) => Object.keys(ENERGIE_SWITCH).some((sw) => layers?.[sw]);

const num = (v) => (Number.isFinite(v) ? v : null);

/** Eine Sammlung für Zeichen (Punkte), Flächen (Solarparks mit Umriss) und Linien (Leitungen). */
export function energieFeatures(items) {
  const pts = [], areas = [], lines = [];
  for (const i of items ?? []) {
    if (i.kind === 'line') {
      if (Array.isArray(i.lines) && i.lines.length) lines.push({ type: 'Feature', geometry: { type: 'MultiLineString', coordinates: i.lines }, properties: { kind: 'line', kv: i.kv ?? 110, id: i.id } });
      continue;
    }
    if (!Number.isFinite(i.lat) || !Number.isFinite(i.lon)) continue;
    const properties = { kind: i.kind, id: i.id, src: i.src ?? 'osm', name: i.name || '', kv: num(i.kv), kw: num(i.kw), ha: num(i.ha), source: i.source || '', state: i.state || '', place: i.place || '' };
    pts.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [i.lon, i.lat] }, properties });
    if (i.kind === 'solar' && Array.isArray(i.ring) && i.ring.length >= 4) areas.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [i.ring] }, properties });
  }
  const fc = (features) => ({ type: 'FeatureCollection', features });
  return { points: fc(pts), areas: fc(areas), lines: fc(lines) };
}

const power = (kw) => (kw >= 1000 ? `${(kw / 1000).toLocaleString('de-DE', { maximumFractionDigits: 1 })} MW` : `${kw} kW`);

/** Popup-Text: Art, Sachwerte, Stand des Verfahrens. Reiner Text. */
export function energieText(p) {
  if (p.kind === 'line') return `Hochspannungsleitung · ${p.kv} kV`;
  const bits = [p.kind === 'plant' && SOURCE_WORD[p.source] ? `Kraftwerk (${SOURCE_WORD[p.source]})` : ENERGIE_WORD[p.kind] ?? p.kind];
  if (p.name) bits.push(p.name);
  if (p.kv) bits.push(`${p.kv} kV`);
  if (p.kw) bits.push(power(p.kw));
  if (p.ha) bits.push(`${p.ha.toLocaleString('de-DE')} ha`);
  if (p.state && p.state !== 'netz') bits.push(STATE_WORD[p.state] ?? p.state);
  if (p.place) bits.push(p.place);
  return bits.join(' · ');
}

export const energieSourceText = (src) => (src === 'rok'
  ? 'Raumordnungskataster ROK25 Online SGD Nord Koblenz (dl-de/by-2.0)'
  : '© OpenStreetMap-Mitwirkende (ODbL)');
