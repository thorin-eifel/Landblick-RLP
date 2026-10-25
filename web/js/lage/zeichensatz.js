import { COLORS as FLOW_COLORS } from '../fluss.js';
import { PIG } from '../pigmente.js';
import { MED_RAMP, MED_STYLE } from '../relief.js';
import { MED as ZEICHEN, registerMedievalPatterns } from '../medieval.js';
import { registerInfra } from '../infra.js';
import { MED, MED_COLORS, MED_FONT, MED_ICON_STYLE, MED_LAND } from './mittelalter.js';
import { CLIFF, CLIFF_SCREE } from './stil.js';
import { artOf } from './zeichensaetze.js';

let aktiv = 'alte-karte';
export const aktiverZeichensatz = () => aktiv;

/**
 * Zeichensatz wechseln: Farben und Schrift in die Objekte schreiben, aus denen die Zeichnungen lesen, dann Muster, Symbole und Infrastrukturzeichen
 * neu zeichnen (gleiche Bildnamen, updateImage). Baut keine Karte um; danach muss recolor() laufen.
 */
export function applyArt(map, id) {
  const a = artOf(id);
  if (!a) return false;
  aktiv = id;
  Object.assign(MED, a.med);
  Object.assign(ZEICHEN, a.zeichen, { fauna: a.fauna });
  Object.assign(PIG, a.pig);
  Object.assign(MED_COLORS, a.colors);
  Object.assign(MED_ICON_STYLE, a.iconStyle);
  for (const k of Object.keys(MED_LAND)) delete MED_LAND[k];
  Object.assign(MED_LAND, a.land);
  MED_FONT.splice(0, MED_FONT.length, a.font);
  MED_RAMP.splice(0, MED_RAMP.length, ...a.ramp);
  Object.assign(MED_STYLE, a.relief, { font: a.font });
  Object.assign(FLOW_COLORS.med, a.flow);
  CLIFF.med = a.cliff.ink; CLIFF.medWall = a.cliff.wall; CLIFF_SCREE.med = a.cliff.scree;
  try { registerMedievalPatterns(map); registerInfra(map); } catch (err) { console.warn('Zeichensatz konnte nicht neu gezeichnet werden:', err); }
  const leg = document.querySelector('#map-legend [data-legend="medieval"]');   // Zeichenerklärung wird beim nächsten Einblenden neu gefüllt
  if (leg) { for (const r of leg.querySelectorAll('.med-leg-row')) r.remove(); delete leg.dataset.filled; }
  return true;
}
