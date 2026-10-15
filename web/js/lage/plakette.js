/*
 * Zahlenplaketten der Übersicht (eine Zahl je Land und Kreis): Kreis und Ziffern in einem Bild, optisch exakt mittig.
 *
 * Zweck:    Text in MapLibre sitzt je nach Schrift zu hoch oder zu tief im Kreis (die Zeilenhöhe ist fest, Ziffern wie 9 und 3
 *           der Gotisch ragen unter die Grundlinie). Hier wird jede Plakette auf Canvas gezeichnet und nach der echten
 *           Tintenfläche der Ziffern zentriert (measureText: actualBoundingBox*), in jeder Schrift.
 * Ablauf:   Layer 'dichte-land' / 'dichte-kreis' (Symbole) fragen Bilder `plakette|<n>|<ebene>|<stufe>|<schrift>` an; die Auflösefunktion
 *           `setMissingStyleImageResolver` zeichnet sie bei Bedarf. Schriftwechsel stellt den Bildnamen um (aktualisiere).
 * Rein:     plaketteId, parsePlakette, plakettenRadius, zentriere, sevFarbe, textFarbe (tests/js/plakette.test.mjs).
 */
import { MED_FONT } from './mittelalter.js';
import { beiSchriftwechsel } from './schrift.js';
import { map, state } from './zustand.js';

const NOTO = 'Noto Sans Regular';
export const PLAKETTE = { land: { lo: 16, hi: 34, size: 14 }, kreis: { lo: 8, hi: 22, size: 12 } };   // Radius (px) bei n = 1 und n = 3600, Schriftgröße
const OPACITY = 0.88, STROKE = 1.5;

/** Radius in px: linear in sqrt(n) zwischen n = 1 (lo) und sqrt(n) = 60 (hi), außerhalb begrenzt (wie die frühere Kreisebene). */
export function plakettenRadius(n, lo, hi) {
  const t = Math.min(1, Math.max(0, (Math.sqrt(Math.max(1, n)) - 1) / 59));
  return lo + (hi - lo) * t;
}

const sauber = (s) => String(s).replace(/[|]/g, '');
export const plaketteId = (n, ebene, stufe, schrift) => `plakette|${Math.round(n)}|${ebene}|${stufe ?? ''}|${sauber(schrift)}`;
export function parsePlakette(id) {
  const [tag, n, ebene, stufe, ...rest] = String(id).split('|');
  if (tag !== 'plakette' || !PLAKETTE[ebene] || !Number.isFinite(Number(n))) return null;
  return { n: Number(n), ebene, stufe, schrift: rest.join('|') };
}

/** Füllfarbe je Stufe (gleiche Zuordnung wie sevColor in farben.js). */
export function sevFarbe(c, stufe) {
  return { critical: c.critical, warning: c.warning, notice: c.notice, yellow: c.yellow, orange: c.orange, red: c.red, black: c.black }[stufe] ?? c.info;
}
/** Dunkle Schrift auf Orange und Gelb (Kontrast), sonst weiß. */
export const textFarbe = (stufe) => (stufe === 'warning' || stufe === 'notice' ? '#111' : '#fff');

/**
 * Ursprung (x0, y0) für fillText mit textAlign 'left' und Grundlinie 'alphabetic', sodass die Tintenfläche um (cx, cy) liegt.
 * m: TextMetrics (actualBoundingBoxLeft/Right/Ascent/Descent).
 */
export function zentriere(m, cx, cy) {
  return { x: cx - (m.actualBoundingBoxRight - m.actualBoundingBoxLeft) / 2, y: cy - (m.actualBoundingBoxDescent - m.actualBoundingBoxAscent) / 2 };
}

// ------------------------------------------------------------------ Browser
let farben = null, schrift = NOTO;
export const plakettenSchrift = () => schrift;

/** Schrift, die die Karte gerade zeigt: Wahl im Menü, sonst Zeichensatz (Alte Karte) oder Noto Sans. */
export const gewaehlteSchrift = () => (state.schrift && state.schrift !== 'auto' ? state.schrift : state.layers.medieval ? MED_FONT[0] : NOTO);

// Für Canvas müssen die Schriften als Webschrift da sein (MapLibre bringt eigene Gesichter mit, die Canvas nicht sieht)
const CANVAS_FONTS = [['Noto Sans Regular', 'noto-sans.woff2'], ['Grenze Gotisch Regular', '../grenze-gotisch.woff'], ['Lora', 'lora.woff2'], ['Alegreya', 'alegreya.woff2'],
  ['Cinzel', 'cinzel.woff2'], ['IM Fell English', 'im-fell-english.woff2'], ['Almendra', 'almendra.woff2'], ['Uncial Antiqua', 'uncial-antiqua.woff2'],
  ['Pirata One', 'pirata-one.woff2'], ['Caveat', 'caveat.woff2']];

export function registiereCanvasSchriften() {
  if (typeof FontFace === 'undefined' || !document.fonts) return;
  for (const [name, file] of CANVAS_FONTS) {
    const url = new URL(`fonts/woff2/${file}`, location.href).href;
    const face = new FontFace(name, `url(${url})`);
    face.load().then(() => { document.fonts.add(face); aktualisiere(); }).catch(() => {});
  }
}

/** Plakette zeichnen: ImageData + pixelRatio. */
export function zeichnePlakette(spec, c, dpr = window.devicePixelRatio || 1) {
  const g = PLAKETTE[spec.ebene], r = plakettenRadius(spec.n, g.lo, g.hi), px = Math.ceil((r + STROKE) * 2);
  const cv = document.createElement('canvas');
  cv.width = Math.ceil(px * dpr); cv.height = Math.ceil(px * dpr);
  const ctx = cv.getContext('2d');
  ctx.scale(dpr, dpr);
  const cx = px / 2, cy = px / 2;
  ctx.globalAlpha = OPACITY;
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.fillStyle = sevFarbe(c, spec.stufe); ctx.fill();
  ctx.globalAlpha = 1;
  ctx.lineWidth = STROKE; ctx.strokeStyle = c.white; ctx.stroke();
  ctx.font = `${g.size}px "${spec.schrift}", "${NOTO}", sans-serif`;
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.fillStyle = textFarbe(spec.stufe);
  const t = String(spec.n), o = zentriere(ctx.measureText(t), cx, cy);
  ctx.fillText(t, o.x, o.y);
  return { data: ctx.getImageData(0, 0, cv.width, cv.height), pixelRatio: dpr };
}

/** Ebene für eine der beiden Stufen anlegen; Bilder entstehen bei Bedarf. */
export function plakettenEbene(id, ebene, filter, minzoom, maxzoom, c) {
  farben = c;
  map.addLayer({ id, type: 'symbol', source: 'dichte', minzoom, maxzoom, filter,
    layout: { 'icon-image': iconExpr(ebene), 'icon-allow-overlap': true, 'icon-ignore-placement': true, 'symbol-sort-key': ['*', -1, ['get', 'n']] } });
}
const iconExpr = (ebene) => ['concat', 'plakette|', ['to-string', ['get', 'n']], `|${ebene}|`, ['coalesce', ['get', 'sev'], ''], `|${sauber(schrift)}`];

export function initPlaketten(c) {
  farben = c;
  schrift = gewaehlteSchrift();
  map.setMissingStyleImageResolver(async (id) => {
    const e = { id };
    const spec = parsePlakette(e.id);
    if (!spec || !farben) return;
    const img = zeichnePlakette(spec, farben);
    if (!map.hasImage(e.id)) map.addImage(e.id, img.data, { pixelRatio: img.pixelRatio });
    document.fonts?.load(`12px "${spec.schrift}"`).then(() => { if (map.hasImage(e.id)) { const n = zeichnePlakette(spec, farben); map.updateImage(e.id, n.data); } }).catch(() => {});
  });
  registiereCanvasSchriften();
  beiSchriftwechsel(aktualisiere);
}

/** Schrift hat sich geändert (Menü, Zeichensatz): Bildnamen umstellen, alte Bilder verwerfen. */
export function aktualisiere() {
  if (!map || !farben) return;
  const neu = gewaehlteSchrift();
  if (neu !== schrift) {
    schrift = neu;
    for (const id of map.listImages().filter((i) => i.startsWith('plakette|') && !i.endsWith(`|${sauber(neu)}`))) map.removeImage(id);
  } else {   // gleiche Schrift, aber das Gesicht ist jetzt geladen: Bilder neu zeichnen
    for (const id of map.listImages().filter((i) => i.startsWith('plakette|'))) { const s = parsePlakette(id); if (s) map.updateImage(id, zeichnePlakette(s, farben).data); }
  }
  for (const id of ['dichte-land', 'dichte-kreis']) if (map.getLayer(id)) map.setLayoutProperty(id, 'icon-image', iconExpr(id === 'dichte-land' ? 'land' : 'kreis'));
}
