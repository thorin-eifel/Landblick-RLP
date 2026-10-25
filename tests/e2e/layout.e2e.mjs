// Layouttest der Lageseite im echten Browser.
//
// Zweck:    Fängt die Fehlerklasse "schwebende Felder liegen übereinander oder rutschen aus dem Bild" ab
//           (Menükarte, Detailfeld, Zeichenerklärung, Höhenpanel, Werkzeugleiste), in mehreren Breiten,
//           mit Details offen und zu, und im Vollbild. Prüft außerdem, dass die Kartenmitte frei bleibt.
// Aufruf:   node --test tests/e2e/layout.e2e.mjs
// Umgebung: Braucht Playwright und Chromium. Ohne beides werden die Tests übersprungen, nicht rot.
//           PLAYWRIGHT_MODULE  Pfad zum Playwright-Modul (Standard: `playwright`, sonst globales npm-Verzeichnis)
//           CHROMIUM_PATH      Pfad zur Chromium-Datei (Standard: /opt/pw-browsers/chromium, sonst Playwright-eigenes)
// Hinweis:  Kein Kartenarchiv nötig; geprüft wird nur Geometrie, nicht der Karteninhalt.
//           Nicht Teil von `node --test tests/js/*.test.mjs`, weil es einen Browser braucht.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const PORT = 18000 + Math.floor(Math.random() * 1000);
const BASE = `http://127.0.0.1:${PORT}/`;

// Felder, die über der Karte schweben. Name -> Selektor.
const FELDER = {
  menue: '.lage > .card:first-child .card-h',
  details: '#side',
  zeichenerklaerung: '#map-legend',
  hoehenpanel: '#relief-legend',
  leiste: '.map-dock',
};
const BREITEN = [[390, 800], [900, 800], [1300, 800], [1700, 1000], [2000, 1200]];

function ladePlaywright() {
  const kandidaten = [process.env.PLAYWRIGHT_MODULE, 'playwright',
    '/home/claude/.npm-global/lib/node_modules/playwright'].filter(Boolean);
  const req = createRequire(import.meta.url);
  for (const k of kandidaten) { try { return req(k); } catch { /* nächster */ } }
  return null;
}

const pw = ladePlaywright();
const chromium = [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'].find((p) => p && existsSync(p));
const skip = !pw ? 'Playwright nicht installiert' : false;

let server; let browser;

before(async () => {
  if (skip) return;
  server = spawn('python3', ['tools/serve-local.py', '--port', String(PORT), '--bind', '127.0.0.1'], { cwd: ROOT, stdio: 'ignore' });
  for (let i = 0; i < 50; i++) {
    try { if ((await fetch(BASE)).ok) break; } catch { /* noch nicht da */ }
    await new Promise((r) => setTimeout(r, 200));
  }
  browser = await pw.chromium.launch({
    ...(chromium ? { executablePath: chromium } : {}),
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
});
after(async () => { await browser?.close(); server?.kill(); });

// Rechtecke der sichtbaren Felder in Seitenkoordinaten (schmal gestapelt scrollt die Seite); beide Legenden werden eingeblendet, damit sie mitgeprüft werden.
async function messen(page) {
  return page.evaluate((felder) => {
    for (const id of ['#map-legend', '#relief-legend']) { const e = document.querySelector(id); if (e) e.hidden = false; }
    const aus = { _fenster: [innerWidth, innerHeight] };
    for (const [name, sel] of Object.entries(felder)) {
      const e = document.querySelector(sel); if (!e) continue;
      const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
      if (cs.display === 'none' || cs.visibility === 'hidden' || r.width < 2 || r.height < 2) continue;
      aus[name] = [r.left + scrollX, r.top + scrollY, r.right + scrollX, r.bottom + scrollY];
    }
    return aus;
  }, FELDER);
}

const schnitt = (a, b) => Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) * Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));

function pruefe(rects, wie, { mitteFrei }) {
  const [w, h] = rects._fenster; const namen = Object.keys(rects).filter((n) => n !== '_fenster');
  for (const n of namen) {
    const r = rects[n];
    assert.ok(r[0] >= -1 && r[2] <= w + 1, `${wie}: ${n} ragt seitlich aus dem Fenster (${r.map(Math.round)})`);
    assert.ok(r[1] >= -1, `${wie}: ${n} ragt oben aus der Seite (${r.map(Math.round)})`);
  }
  for (let i = 0; i < namen.length; i++) for (let j = i + 1; j < namen.length; j++) {
    const a = rects[namen[i]]; const b = rects[namen[j]];
    assert.ok(schnitt(a, b) < 4, `${wie}: ${namen[i]} und ${namen[j]} überlappen (${a.map(Math.round)} / ${b.map(Math.round)})`);
  }
  if (mitteFrei) {
    // mittlere 30 % mal 30 % der Seite
    const mitte = [w * 0.35, h * 0.35, w * 0.65, h * 0.65];
    for (const n of namen) assert.ok(schnitt(rects[n], mitte) < 4, `${wie}: ${n} liegt in der Kartenmitte (${rects[n].map(Math.round)})`);
  }
}

async function seite(breite, hoehe, touch = false) {
  const page = await browser.newPage({ viewport: { width: breite, height: hoehe }, ...(touch ? { hasTouch: true, isMobile: true } : {}) });
  const fehler = []; page.on('pageerror', (e) => fehler.push(String(e)));
  await page.goto(`${BASE}#11/49.85/6.45`);
  await page.waitForSelector('.map-dock', { timeout: 20000 });
  await page.waitForTimeout(1500);
  return { page, fehler };
}

async function detailsOeffnen(page) {
  if (await page.evaluate(() => document.querySelector('.lage').classList.contains('side-min'))) await page.click('#side-toggle');
  await page.waitForTimeout(500);
}

for (const [w, h] of BREITEN) {
  for (const offen of [false, true]) {
    test(`Lageseite ${w}x${h}, Details ${offen ? 'offen' : 'zu'}: nichts überlappt, nichts ragt heraus`, { skip }, async () => {
      const { page, fehler } = await seite(w, h);
      try {
        if (offen) await detailsOeffnen(page);
        const rects = await messen(page);
        assert.ok(rects.leiste, 'Werkzeugleiste fehlt');
        // Schmal gestapelt (bis 1000 px) liegt die Menükarte über der Karte, die Mitte ist dort nicht das Thema.
        pruefe(rects, `${w}px, Details ${offen ? 'offen' : 'zu'}`, { mitteFrei: w > 1000 });
        assert.deepEqual(fehler, []);
      } finally { await page.close(); }
    });
  }
}

// Touchgeräte bekommen 44-px-Ziele (pointer: coarse); die Leiste wird dadurch höher und darf trotzdem nichts berühren.
for (const [w, h] of [[390, 800], [820, 1100]]) {
  test(`Touchgerät ${w}x${h}: nichts überlappt`, { skip }, async () => {
    const { page, fehler } = await seite(w, h, true);
    try {
      for (const offen of [false, true]) {
        if (offen) await detailsOeffnen(page);
        pruefe(await messen(page), `Touch ${w}px, Details ${offen ? 'offen' : 'zu'}`, { mitteFrei: false });
      }
      assert.deepEqual(fehler, []);
    } finally { await page.close(); }
  });
}

for (const [w, h] of BREITEN.filter(([b]) => b > 1000)) {
  test(`Vollbild ${w}x${h}: Menü, Details und Legenden bleiben da und überlappen nicht`, { skip }, async () => {
    const { page, fehler } = await seite(w, h);
    try {
      await page.evaluate(() => document.querySelector('.lage').requestFullscreen());
      await page.waitForTimeout(800);
      const vollbild = await page.evaluate(() => document.fullscreenElement?.classList.contains('lage') === true);
      assert.ok(vollbild, 'Vollbild nicht aktiv');
      for (const offen of [false, true]) {
        if (offen) await detailsOeffnen(page);
        const rects = await messen(page);
        assert.ok(rects.menue, 'Menükarte fehlt im Vollbild');
        assert.ok(rects.details, 'Detailfeld fehlt im Vollbild');
        pruefe(rects, `Vollbild ${w}px, Details ${offen ? 'offen' : 'zu'}`, { mitteFrei: true });
      }
      assert.deepEqual(fehler, []);
    } finally { await page.close(); }
  });
}
