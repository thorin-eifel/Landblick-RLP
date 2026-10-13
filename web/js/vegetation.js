// Vegetationsmuster: naturnahe Draufsicht statt Piktogramm, angelehnt an Luftbild und Satellitenaufnahme.
// Jede Klasse ist eine nahtlos kachelbare Textur (64 x 64 Pixel, pixelRatio 2 = 32 px auf dem Schirm) mit eigener
// Grundfarbe, Körnung, Formen und Schattenwurf. Das Licht kommt von links oben, Schatten fallen nach rechts unten.
// Die Zeichnung ist deterministisch (festes Saatkorn je Klasse), damit sich Kacheln nicht von Start zu Start ändern.
// Bilder heißen lp-<klasse>-<light|dark>; stil.js legt sie als fill-pattern über die Flächenfarbe.

export const LP = 64;
const TAU = Math.PI * 2;

// Palette je Klasse: g Grund, a dunkel, b mittel, c hell, s Schatten, x/y Akzente (Blüte, Dach, Schilf, Boden)
export const PALETTE = {
  light: {
    forest: { g: '#3a5e35', a: '#27432a', b: '#44703b', c: '#76a05c', s: 'rgba(8,22,10,0.5)', x: '#b5c27a' },
    meadow: { g: '#a9c262', a: '#6f9a3a', b: '#8db04c', c: '#cde28a', x: '#f7f3d0', y: '#f2d64a' },
    grass: { g: '#8fc062', a: '#4f8a38', b: '#74ad4e', c: '#b4dc86' },
    scrub: { g: '#8a9a58', a: '#4f5e2c', b: '#6c8038', c: '#a8b864', s: 'rgba(30,35,10,0.45)', x: '#7b6446' },
    heath: { g: '#8c7a55', a: '#6a4f66', b: '#9a6a92', c: '#cfa0c8', x: '#6e7a3a' },
    farmland: { g: '#d8c68a', a: '#bfa968', b: '#e6d6a0', c: '#b7bd72' },
    orchard: { g: '#a6c46a', a: '#4b7a2e', b: '#68994a', c: '#9ac870', s: 'rgba(15,35,10,0.42)' },
    vineyard: { g: '#cdbf86', a: '#4f7226', b: '#7fa03c', c: '#dccfa4', s: 'rgba(70,45,10,0.5)' },
    allotment: { g: '#cdd698', a: '#7a9a40', b: '#a88f5c', c: '#e2e8b6', x: '#b8553a', y: '#8a7a64' },
    wetland: { g: '#7fb0a0', a: '#2f7a78', b: '#4f9aa0', c: '#b0dcd6', x: '#8a9a50' },
    rock: { g: '#a89d90', a: '#6f665a', b: '#8f8578', c: '#d2cabc', s: 'rgba(40,35,30,0.4)' },
    sand: { g: '#e8d9a0', a: '#c5ae6c', b: '#d8c585', c: '#f8f0cc' },
    cemetery: { g: '#a2c08e', a: '#4c6e47', b: '#6c8e62', c: '#dcdcd2', s: 'rgba(25,40,25,0.45)' },
  },
  dark: {
    forest: { g: '#1d3a28', a: '#12281c', b: '#2a5238', c: '#4a7c5a', s: 'rgba(0,8,4,0.55)', x: '#6a8a5a' },
    meadow: { g: '#46703c', a: '#2f5a30', b: '#548048', c: '#7ea868', x: '#d8d8b0', y: '#d8c060' },
    grass: { g: '#3f7040', a: '#2c5a30', b: '#4c8450', c: '#6ca868' },
    scrub: { g: '#4a5a34', a: '#2f3b22', b: '#586a3a', c: '#78905a', s: 'rgba(0,6,0,0.5)', x: '#5e4a34' },
    heath: { g: '#4e4438', a: '#4a3448', b: '#6a4a68', c: '#9a6e94', x: '#4e5a2c' },
    farmland: { g: '#6a6038', a: '#524a2a', b: '#7a6e42', c: '#5e6a34' },
    orchard: { g: '#456a35', a: '#2e5028', b: '#3f6a3a', c: '#628f56', s: 'rgba(0,8,0,0.5)' },
    vineyard: { g: '#5c5a32', a: '#38501f', b: '#587030', c: '#6e6c44', s: 'rgba(10,6,0,0.55)' },
    allotment: { g: '#4f6a3f', a: '#3a5a2a', b: '#6a5a3a', c: '#6e8e54', x: '#a8503a', y: '#7a6e5a' },
    wetland: { g: '#2f5f58', a: '#1f4f50', b: '#38726e', c: '#5e9e98', x: '#6a7a3a' },
    rock: { g: '#6a645c', a: '#47423c', b: '#58534b', c: '#8c867a', s: 'rgba(0,0,0,0.45)' },
    sand: { g: '#6f6747', a: '#574f33', b: '#7e7550', c: '#968c64' },
    cemetery: { g: '#3d5f45', a: '#2a4630', b: '#4a6e50', c: '#8c928a', s: 'rgba(0,8,0,0.5)' },
  },
};

// kleines, schnelles Zufallsrauschen mit festem Saatkorn (mulberry32)
export function prng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Jede Form wird neunmal gezeichnet (Kachel und acht Nachbarn), damit Ränder nahtlos anschließen.
const wrap = (x, f) => {
  for (const dx of [-LP, 0, LP]) for (const dy of [-LP, 0, LP]) { x.save(); x.translate(dx, dy); f(); x.restore(); }
};
const alpha = (x, a, f) => { const o = x.globalAlpha; x.globalAlpha = o * a; f(); x.globalAlpha = o; };
const radii = (n, jitter, r) => Array.from({ length: n }, () => 1 - jitter + r() * jitter * 2);

// weich geschwungene, unregelmäßige Fläche (Baumkrone, Busch, Wasserfleck)
function blob(x, cx, cy, r, rad, rot = 0) {
  const n = rad.length;
  const p = rad.map((k, i) => { const a = rot + (i * TAU) / n; return [cx + Math.cos(a) * r * k, cy + Math.sin(a) * r * k]; });
  const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  x.beginPath();
  const s = mid(p[n - 1], p[0]);
  x.moveTo(s[0], s[1]);
  for (let i = 0; i < n; i++) { const e = mid(p[i], p[(i + 1) % n]); x.quadraticCurveTo(p[i][0], p[i][1], e[0], e[1]); }
  x.closePath();
}
// Nadelbaum von oben: Stern mit abgestuften Zacken
function star(x, cx, cy, r, n = 9, inner = 0.5, rot = 0) {
  x.beginPath();
  for (let i = 0; i < n * 2; i++) {
    const a = rot + (i * Math.PI) / n, k = i % 2 ? inner : 1;
    x[i ? 'lineTo' : 'moveTo'](cx + Math.cos(a) * r * k, cy + Math.sin(a) * r * k);
  }
  x.closePath();
}
const dot = (x, cx, cy, r) => { x.beginPath(); x.arc(cx, cy, r, 0, TAU); x.fill(); };
const fill = (x, c) => { x.fillStyle = c; };

// Grund: Grundfarbe plus weiche Flecken in Dunkel und Hell, wie die Körnung einer Aufnahme
function ground(x, p, r, n = 26, rmin = 4, rmax = 10) {
  fill(x, p.g); x.fillRect(0, 0, LP, LP);
  for (let i = 0; i < n; i++) {
    const cx = r() * LP, cy = r() * LP, rr = rmin + r() * (rmax - rmin), rad = radii(7, 0.3, r), col = i % 2 ? p.a : p.c, al = 0.12 + r() * 0.12;
    wrap(x, () => alpha(x, al, () => { fill(x, col); blob(x, cx, cy, rr, rad, r() * TAU); x.fill(); }));
  }
}

// Laubbaum von oben: Schatten rechts unten, Krone, Lichtfleck links oben, Blattkörnung
function broadleaf(x, p, c) {
  fill(x, p.s); blob(x, c.x + c.r * 0.35, c.y + c.r * 0.5, c.r * 1.02, c.rad, c.rot); x.fill();
  fill(x, p.b); blob(x, c.x, c.y, c.r, c.rad, c.rot); x.fill();
  fill(x, p.a); alpha(x, 0.55, () => { blob(x, c.x + c.r * 0.28, c.y + c.r * 0.3, c.r * 0.62, c.rad2, c.rot + 1); x.fill(); });
  fill(x, p.c); alpha(x, 0.85, () => { blob(x, c.x - c.r * 0.28, c.y - c.r * 0.3, c.r * 0.55, c.rad3, c.rot + 2); x.fill(); });
  for (const [dx, dy, k] of c.speck) { fill(x, k ? p.c : p.a); alpha(x, 0.7, () => dot(x, c.x + dx * c.r, c.y + dy * c.r, 0.55)); }
}
function conifer(x, p, c) {
  fill(x, p.s); star(x, c.x + c.r * 0.4, c.y + c.r * 0.55, c.r * 1.05, c.n, 0.52, c.rot); x.fill();
  fill(x, p.a); star(x, c.x, c.y, c.r, c.n, 0.52, c.rot); x.fill();
  fill(x, p.b); alpha(x, 0.8, () => { star(x, c.x - c.r * 0.12, c.y - c.r * 0.14, c.r * 0.62, c.n, 0.5, c.rot); x.fill(); });
  fill(x, p.c); alpha(x, 0.6, () => dot(x, c.x - c.r * 0.2, c.y - c.r * 0.22, c.r * 0.22));
}
function crownSpec(r, rr, conif = false) {
  return { x: r() * LP, y: r() * LP, r: rr, rad: radii(9, 0.22, r), rad2: radii(7, 0.25, r), rad3: radii(7, 0.25, r), rot: r() * TAU, n: 8 + Math.floor(r() * 3), conif,
    speck: Array.from({ length: 5 }, () => [(r() - 0.5) * 1.2, (r() - 0.5) * 1.2, r() > 0.5]) };
}
function crowns(x, p, list) {
  [...list].sort((a, b) => a.y - b.y).forEach((c) => wrap(x, () => (c.conif ? conifer(x, p, c) : broadleaf(x, p, c))));
}

const DRAW = {
  // Mischwald: Laub- und Nadelbäume dicht, Kronen überlappen, dazwischen dunkler Grund
  forest(x, p, r) {
    ground(x, p, r, 30, 3, 8);
    const list = Array.from({ length: 16 }, (_, i) => crownSpec(r, 4.6 + r() * 3.4, i % 3 === 0));
    crowns(x, p, list);
  },
  // Wiese: gemischtes Gras, kleine Büschel und verstreute Blüten
  meadow(x, p, r) {
    ground(x, p, r, 34, 3, 9);
    for (let i = 0; i < 22; i++) {
      const cx = r() * LP, cy = r() * LP, col = i % 3 ? p.a : p.c, h = 3 + r() * 3;
      wrap(x, () => {
        x.strokeStyle = col; x.lineWidth = 0.9; x.lineCap = 'round'; alpha(x, 0.8, () => {
          x.beginPath();
          for (const k of [-1.6, 0, 1.6]) { x.moveTo(cx + k * 0.5, cy); x.quadraticCurveTo(cx + k, cy - h * 0.6, cx + k * 1.7, cy - h); }
          x.stroke();
        });
      });
    }
    for (let i = 0; i < 12; i++) { const cx = r() * LP, cy = r() * LP, col = i % 3 ? p.x : p.y; wrap(x, () => { fill(x, col); alpha(x, 0.9, () => dot(x, cx, cy, 0.75 + r() * 0.35)); }); }
  },
  // Rasen, Park: kurzes, dichtes Gras mit Mähstreifen
  grass(x, p, r) {
    ground(x, p, r, 18, 4, 11);
    fill(x, p.c); for (let i = 0; i < 4; i++) alpha(x, 0.14, () => x.fillRect(0, i * 16, LP, 8));
    for (let i = 0; i < 70; i++) {
      const cx = r() * LP, cy = r() * LP;
      wrap(x, () => { x.strokeStyle = i % 2 ? p.a : p.c; x.lineWidth = 0.7; alpha(x, 0.55, () => { x.beginPath(); x.moveTo(cx, cy); x.lineTo(cx + (r() - 0.5) * 1.6, cy - 1.8 - r() * 1.4); x.stroke(); }); });
    }
  },
  // Gebüsch: einzelne rundliche Büsche mit Schatten auf offenem Boden
  scrub(x, p, r) {
    ground(x, p, r, 22, 3, 8);
    for (let i = 0; i < 12; i++) { const cx = r() * LP, cy = r() * LP; wrap(x, () => { fill(x, p.x); alpha(x, 0.3, () => dot(x, cx, cy, 0.9 + r())); }); }
    const list = Array.from({ length: 11 }, () => crownSpec(r, 2.6 + r() * 2.4));
    [...list].sort((a, b) => a.y - b.y).forEach((c) => wrap(x, () => {
      fill(x, p.s); blob(x, c.x + c.r * 0.4, c.y + c.r * 0.5, c.r, c.rad, c.rot); x.fill();
      fill(x, p.b); blob(x, c.x, c.y, c.r, c.rad, c.rot); x.fill();
      fill(x, p.c); alpha(x, 0.8, () => { blob(x, c.x - c.r * 0.28, c.y - c.r * 0.3, c.r * 0.5, c.rad3, c.rot + 2); x.fill(); });
      fill(x, p.a); alpha(x, 0.5, () => dot(x, c.x + c.r * 0.3, c.y + c.r * 0.3, c.r * 0.3));
    }));
  },
  // Heide: Zwergsträucher in violetter Blüte zwischen Gras und Boden
  heath(x, p, r) {
    ground(x, p, r, 26, 3, 9);
    for (let i = 0; i < 9; i++) { const cx = r() * LP, cy = r() * LP, rr = 2 + r() * 1.5; wrap(x, () => { fill(x, p.x); alpha(x, 0.55, () => { blob(x, cx, cy, rr, radii(6, 0.3, r), r() * TAU); x.fill(); }); }); }
    for (let i = 0; i < 12; i++) {
      const cx = r() * LP, cy = r() * LP, rr = 3 + r() * 3;
      wrap(x, () => {
        fill(x, p.a); alpha(x, 0.55, () => dot(x, cx + 1, cy + 1.4, rr * 0.8));
        for (let k = 0; k < 16; k++) { const a = r() * TAU, d = Math.sqrt(r()) * rr; fill(x, [p.b, p.c, p.a][k % 3]); alpha(x, 0.9, () => dot(x, cx + Math.cos(a) * d, cy + Math.sin(a) * d, 0.7 + r() * 0.5)); }
      });
    }
  },
  // Acker: Feldstreifen mit Saat- bzw. Stoppelreihen; bewusst quer zu den Rebzeilen
  farmland(x, p, r) {
    fill(x, p.g); x.fillRect(0, 0, LP, LP);
    const tones = [p.b, p.g, p.a, p.c, p.b, p.g, p.c, p.a];
    tones.forEach((t, i) => { fill(x, t); alpha(x, 0.7, () => x.fillRect(0, i * 8, LP, 8)); });
    x.strokeStyle = p.a; x.lineWidth = 0.6;
    for (let i = 0; i < LP / 2; i++) { alpha(x, 0.22 + (i % 4 === 0 ? 0.12 : 0), () => { x.beginPath(); x.moveTo(0, i * 2 + 0.5); x.lineTo(LP, i * 2 + 0.5); x.stroke(); }); }
    for (let i = 0; i < 40; i++) { fill(x, i % 2 ? p.a : p.b); alpha(x, 0.3, () => dot(x, r() * LP, r() * LP, 0.6)); }
  },
  // Streuobst: Bäume im versetzten Raster, helles Gras dazwischen
  orchard(x, p, r) {
    ground(x, p, r, 18, 4, 10);
    const list = [];
    for (let row = 0; row < 4; row++) for (let col = 0; col < 4; col++) {
      const c = crownSpec(r, 4.3 + r() * 0.7); c.x = col * 16 + (row % 2 ? 8 : 0) + 4 + (r() - 0.5) * 1.5; c.y = row * 16 + 8 + (r() - 0.5) * 1.5; list.push(c);
    }
    crowns(x, p, list);
  },
  // Weinberg: dichte senkrechte Rebzeilen, daneben offener Boden mit Gasse
  vineyard(x, p, r) {
    fill(x, p.g); x.fillRect(0, 0, LP, LP);
    for (let i = 0; i < 40; i++) { fill(x, i % 2 ? p.a : p.c); alpha(x, 0.12, () => dot(x, r() * LP, r() * LP, 1 + r() * 1.5)); }
    for (let col = 0; col < 8; col++) {
      const px = col * 8 + 3;
      fill(x, p.c); alpha(x, 0.55, () => x.fillRect(px + 2, 0, 3.5, LP));            // helle Gasse zwischen den Zeilen
      fill(x, p.s); alpha(x, 0.9, () => x.fillRect(px + 1.3, 0, 1.4, LP));         // Schatten der Zeile
      for (let y = 0; y < LP; y += 2) {
        fill(x, y % 4 ? p.b : p.a); alpha(x, 0.95, () => { x.beginPath(); x.ellipse(px, y + 1, 1.6 + r() * 0.5, 1.4, 0, 0, TAU); x.fill(); });
      }
    }
  },
  // Kleingarten: Beete in Parzellen, Wege, einzelne Lauben
  allotment(x, p, r) {
    fill(x, p.y); x.fillRect(0, 0, LP, LP);
    const tones = [p.a, p.b, p.c, p.a];
    for (let i = 0; i < 4; i++) {
      const ox = (i % 2) * 32 + 2, oy = Math.floor(i / 2) * 32 + 2;
      fill(x, tones[i]); x.fillRect(ox, oy, 28, 28);
      x.strokeStyle = 'rgba(0,0,0,0.22)'; x.lineWidth = 0.8;
      for (let b = 3; b < 28; b += 4) { x.beginPath(); if (i % 2) { x.moveTo(ox + b, oy + 8); x.lineTo(ox + b, oy + 28); } else { x.moveTo(ox + 8, oy + b); x.lineTo(ox + 28, oy + b); } x.stroke(); }
      fill(x, p.s || 'rgba(0,0,0,0.3)'); x.fillRect(ox + 1.6, oy + 1.6, 7, 7);
      fill(x, i % 2 ? p.x : p.c); x.fillRect(ox, oy, 7, 7);                         // Laube mit Dach
      fill(x, 'rgba(0,0,0,0.25)'); x.fillRect(ox + 3.5, oy, 3.5, 7);                  // Dachfirst, Schattenseite
    }
  },
  // Moor, Sumpf: Wasserflecken, Riedgras und Torfboden
  wetland(x, p, r) {
    ground(x, p, r, 22, 4, 10);
    for (let i = 0; i < 4; i++) {
      const cx = r() * LP, cy = r() * LP, rr = 4 + r() * 4, rad = radii(8, 0.3, r);
      wrap(x, () => { fill(x, p.a); alpha(x, 0.85, () => { blob(x, cx, cy, rr, rad, 0); x.fill(); }); fill(x, p.c); alpha(x, 0.45, () => { blob(x, cx - rr * 0.2, cy - rr * 0.25, rr * 0.5, rad, 1); x.fill(); }); });
    }
    for (let i = 0; i < 26; i++) {
      const cx = r() * LP, cy = r() * LP, h = 3 + r() * 3;
      wrap(x, () => { x.strokeStyle = i % 3 ? p.x : p.b; x.lineWidth = 0.8; x.lineCap = 'round'; alpha(x, 0.9, () => { x.beginPath(); for (const k of [-1.4, 0, 1.4]) { x.moveTo(cx, cy); x.lineTo(cx + k, cy - h + Math.abs(k)); } x.stroke(); }); });
    }
  },
  // Fels: kantige Platten, helle Lichtseite, dunkle Schattenseite, Risse
  rock(x, p, r) {
    ground(x, p, r, 22, 3, 8);
    for (let i = 0; i < 11; i++) {
      const cx = r() * LP, cy = r() * LP, rr = 5 + r() * 5, cnt = 7 + Math.floor(r() * 3), pts = Array.from({ length: cnt }, (_, k) => { const ang = (k / cnt) * TAU + (r() - 0.5) * 0.35, d = rr * (0.8 + r() * 0.3); return [Math.cos(ang) * d, Math.sin(ang) * d]; });
      wrap(x, () => {
        const poly = (list, dx = 0, dy = 0) => { x.beginPath(); list.forEach(([a, b], k) => x[k ? 'lineTo' : 'moveTo'](cx + a + dx, cy + b + dy)); x.closePath(); };
        fill(x, p.s); poly(pts, 1.2, 1.6); x.fill();
        fill(x, p.b); poly(pts); x.fill();
        const half = pts.slice(Math.floor(pts.length / 2)).concat([[0, 0]]);          // untere rechte Hälfte im Schatten
        fill(x, p.a); alpha(x, 0.7, () => { poly(half); x.fill(); });
        const lit = pts.slice(0, Math.ceil(pts.length / 2)).concat([[0, 0]]);          // obere linke Hälfte im Licht
        fill(x, p.c); alpha(x, 0.7, () => { poly(lit); x.fill(); });
      });
    }
  },
  // Sand: feine Körner in drei Tönen, flache Rippel
  sand(x, p, r) {
    ground(x, p, r, 18, 5, 12);
    for (let i = 0; i < 120; i++) { fill(x, [p.a, p.b, p.c][i % 3]); alpha(x, 0.55, () => x.fillRect(r() * LP, r() * LP, 1, 1)); }
    x.strokeStyle = p.a; x.lineWidth = 0.7;
    for (let i = 0; i < 6; i++) { const cx = r() * LP, cy = r() * LP; wrap(x, () => alpha(x, 0.3, () => { x.beginPath(); x.arc(cx, cy, 6 + r() * 4, Math.PI * 1.1, Math.PI * 1.9); x.stroke(); })); }
  },
  // Friedhof: Rasen, Grabreihen mit Steinen und Schattenwurf, wenige Bäume
  cemetery(x, p, r) {
    ground(x, p, r, 14, 4, 10);
    for (let row = 0; row < 4; row++) for (let col = 0; col < 5; col++) {
      const gx = col * 12.8 + 3, gy = row * 16 + 9;
      fill(x, p.a); alpha(x, 0.35, () => x.fillRect(gx - 0.5, gy - 1, 5, 9));          // Grabhügel
      fill(x, p.s); x.fillRect(gx + 1.2, gy - 1.6, 2.4, 1.4);
      fill(x, p.c); x.fillRect(gx + 0.8, gy - 2.4, 2.4, 1.8);                          // Stein
    }
    crowns(x, p, [crownSpec(r, 5.5), crownSpec(r, 4.8)]);
  },
};

export const LAND_CLASSES = Object.keys(DRAW);

// Zeichnet ein Muster in einen Canvas der Größe LP x LP (auch für Tests und die Vorschau nutzbar)
export function drawLandPattern(ctx, cls, level) {
  const p = PALETTE[level]?.[cls];
  if (!p || !DRAW[cls]) throw new Error(`Unbekannte Vegetationsklasse: ${cls}/${level}`);
  const seed = [...cls].reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) >>> 0, 7919);
  ctx.save();
  ctx.clearRect(0, 0, LP, LP);
  ctx.lineJoin = 'round';
  DRAW[cls](ctx, p, prng(seed));
  ctx.restore();
}

export function registerLandPatterns(map) {
  for (const level of ['light', 'dark']) {
    for (const cls of LAND_CLASSES) {
      const c = document.createElement('canvas'); c.width = LP; c.height = LP;
      const x = c.getContext('2d', { willReadFrequently: true });
      drawLandPattern(x, cls, level);
      const id = `lp-${cls}-${level}`, data = x.getImageData(0, 0, LP, LP);
      if (map.hasImage(id)) map.updateImage(id, data); else map.addImage(id, data, { pixelRatio: 2 });
    }
  }
}
