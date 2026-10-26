// Messmodus (rein, ohne DOM und Karte): sammelt Bildzeiten und Kachel-Ladezeiten einer Kartenbewegung und fasst sie zusammen.
// Eine Bewegung beginnt mit der ersten Eingabe nach Ruhe und endet, wenn die Karte wieder ruht (MapLibre-Ereignis 'idle').
// Maßzahl für das Ziel "alle Ebenen in unter 1 s": nachladen_ms = Zeit von der letzten Eingabe bis zur Ruhe.

export function perzentil(werte, p) {
  if (!werte.length) return null;
  const s = [...werte].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.max(0, Math.ceil((p / 100) * s.length) - 1))];
}

const r1 = (v) => (v == null ? null : Math.round(v * 10) / 10);

export class Messlauf {
  constructor(start) {
    this.start = start;
    this.letzteEingabe = start;
    this.frames = [];
    this.offen = new Map();     // "quelle|kachel" -> Startzeit
    this.quellen = new Map();   // quelle -> { kacheln, summe, max, fehler }
    this.fehler = [];
  }

  eingabe(t) { this.letzteEingabe = t; }

  frame(dt) { if (dt > 0 && dt < 60000) this.frames.push(dt); }

  kachelStart(quelle, kachel, t) {
    const k = `${quelle}|${kachel}`;
    if (!this.offen.has(k)) this.offen.set(k, t);
  }

  kachelFertig(quelle, kachel, t) {
    const k = `${quelle}|${kachel}`, t0 = this.offen.get(k);
    if (t0 == null) return;
    this.offen.delete(k);
    const q = this.quelle(quelle), d = t - t0;
    q.kacheln++; q.summe += d; q.max = Math.max(q.max, d);
  }

  fehlerVon(quelle, text) {
    this.quelle(quelle ?? '?').fehler++;
    if (this.fehler.length < 10) this.fehler.push(`${quelle ?? '?'}: ${String(text).slice(0, 160)}`);
  }

  quelle(id) {
    if (!this.quellen.has(id)) this.quellen.set(id, { kacheln: 0, summe: 0, max: 0, fehler: 0 });
    return this.quellen.get(id);
  }

  // Ergebnis als schlichtes Objekt fürs Protokoll; Quellen nach längster Kachel sortiert, die langsamsten zuerst
  ende(t, ansicht = {}) {
    const quellen = [...this.quellen.entries()]
      .map(([id, q]) => ({ id, kacheln: q.kacheln, max_ms: r1(q.max), mittel_ms: r1(q.kacheln ? q.summe / q.kacheln : 0), fehler: q.fehler }))
      .sort((a, b) => b.max_ms - a.max_ms);
    return {
      dauer_ms: r1(t - this.start),
      nachladen_ms: r1(t - this.letzteEingabe),
      frames: this.frames.length,
      frame_p50_ms: r1(perzentil(this.frames, 50)),
      frame_p95_ms: r1(perzentil(this.frames, 95)),
      frame_max_ms: r1(this.frames.length ? Math.max(...this.frames) : null),
      ueber_30ms: this.frames.filter((f) => f > 30).length,
      offen: this.offen.size,
      quellen,
      fehler: this.fehler,
      ...ansicht,
    };
  }
}

export const ZIEL_NACHLADEN_MS = 1000;
export const ZIEL_FRAME_MS = 30;

// Eine Zeile für die Anzeige: grün, wenn beide Ziele erreicht sind
export function kurzfassung(e) {
  const ok = e.nachladen_ms <= ZIEL_NACHLADEN_MS && (e.frame_p95_ms ?? 0) <= ZIEL_FRAME_MS;
  const langsam = e.quellen.slice(0, 3).map((q) => `${q.id} ${Math.round(q.max_ms)} ms`).join(', ');
  return { ok, text: `Nachladen ${Math.round(e.nachladen_ms)} ms · Frame p95 ${e.frame_p95_ms ?? '–'} ms, max ${e.frame_max_ms ?? '–'} ms${langsam ? ` · langsam: ${langsam}` : ''}` };
}
