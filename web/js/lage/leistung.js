// Messmodus der Lagekarte: Strg+Umschalt+M (Mac: Cmd+Umschalt+M) oder #messen in der Adresse.
// Misst je Kartenbewegung Bildzeiten und Kachel-Ladezeiten je Quelle, zeigt das Ergebnis unten links an und schreibt es
// in der Desktop-App nach <Datenordner>/logs/messung.jsonl (POST api/messung). Nichts davon verlässt den Rechner.
import { Messlauf, kurzfassung } from '../leistung.js';

const kachelId = (t) => { const c = t?.tileID?.canonical; return c ? `${c.z}/${c.x}/${c.y}${t.tileID.wrap ? `@${t.tileID.wrap}` : ''}` : null; };

export function initLeistung(map) {
  let an = false, lauf = null, raf = 0, letzterFrame = 0, anzeige = null;

  const schalter = () => {
    an = !an;
    if (!anzeige) {
      anzeige = document.createElement('div');
      anzeige.className = 'leistung-anzeige'; anzeige.setAttribute('role', 'status');
      map.getContainer().parentElement.append(anzeige);
    }
    anzeige.hidden = !an;
    anzeige.textContent = an ? 'Messmodus an: Karte bewegen, Ergebnis nach jeder Bewegung.' : '';
    if (!an) { cancelAnimationFrame(raf); raf = 0; lauf = null; }
  };

  const tick = (t) => {
    if (!lauf) { raf = 0; return; }
    if (letzterFrame) lauf.frame(t - letzterFrame);
    letzterFrame = t; raf = requestAnimationFrame(tick);
  };

  const beginne = () => {
    if (!an || lauf) return;
    lauf = new Messlauf(performance.now()); letzterFrame = 0;
    if (!raf) raf = requestAnimationFrame(tick);
  };

  for (const ev of ['movestart', 'zoomstart']) map.on(ev, beginne);
  map.on('move', () => { if (lauf) lauf.eingabe(performance.now()); });
  map.on('dataloading', (e) => {
    if (!an || e.dataType !== 'source' || !e.tile) return;
    beginne(); const id = kachelId(e.tile); if (id) lauf.kachelStart(e.sourceId, id, performance.now());
  });
  map.on('data', (e) => {
    if (!lauf || e.dataType !== 'source' || !e.tile) return;
    const id = kachelId(e.tile); if (id) lauf.kachelFertig(e.sourceId, id, performance.now());
  });
  map.on('error', (e) => { if (lauf) lauf.fehlerVon(e.sourceId, e.error?.message ?? e.error ?? 'Fehler'); });
  map.getCanvas().addEventListener('webglcontextlost', () => { if (lauf) lauf.fehlerVon('webgl', 'Kontext verloren'); });

  map.on('idle', () => {
    if (!lauf) return;
    const c = map.getCenter(), e = lauf.ende(performance.now(), { zoom: +map.getZoom().toFixed(2), mitte: [+c.lng.toFixed(3), +c.lat.toFixed(3)], zeit: new Date().toISOString() });
    lauf = null;
    const k = kurzfassung(e);
    anzeige.textContent = k.text; anzeige.dataset.ok = k.ok ? '1' : '0';
    fetch('api/messung', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Landblick': '1' }, body: JSON.stringify(e) }).catch(() => {});
  });

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'm') { e.preventDefault(); schalter(); }
  });
  if (location.hash === '#messen') schalter();
}
