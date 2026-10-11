// Aufbau der Desktop-App beim ersten Start: Fortschritt von Karte und Daten zeigen, danach zur Karte. Das Gebiet steht fest (region.yaml), es gibt nichts zu wählen.
// Spricht nur mit dem lokalen Dienst (api/state).
const $ = (id) => document.getElementById(id);
let hintergrund = null;

async function api(path) {
  const r = await fetch(path);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `Fehler ${r.status}`);
  return j;
}
const fehler = (t) => { $('fehler').textContent = t || ''; };

async function poll() {
  try {
    const s = await api('api/state');
    const j = s.job;
    $('bar').hidden = false; $('bar').setAttribute('aria-valuenow', j.pct); $('barfill').style.width = `${j.pct}%`;
    $('status').textContent = j.msg ? `${j.msg} (${j.pct} %)` : '';
    if (j.phase === 'error') return fehler(`Abbruch: ${j.error}. Beim nächsten Start geht es dort weiter, wo es stand.`);
    if (j.phase === 'ready') { location.href = './'; return; }
  } catch (err) { fehler(err.message); }
  setTimeout(poll, 2000);
}

poll();

// Mitgeliefert ist nur die Schrift "Noto Sans Regular" und kein Symbolsatz: Beschriftungen auf Regular zwingen, Symbole weglassen.
function nurRegular(l) {
  if (l.type !== 'symbol') return l;
  const { 'icon-image': _drop, ...layout } = l.layout ?? {};
  return { ...l, layout: { ...layout, 'text-font': ['Noto Sans Regular'] } };
}

// Hintergrund: Weltkarte Zoom 0 bis 5, liegt im Programm (basis/welt.pmtiles, rund 15 MB). Fehlt sie oder eine Bibliothek,
// bleibt die Seite ohne Karte und funktioniert trotzdem. Ohne Netz, ohne Drittanbieter.
(async () => {
  try {
    const [{ Map: MlMap, addProtocol }, { PMTiles, Protocol }, { layers, namedFlavor }] = await Promise.all([
      import('../vendor/maplibre-gl/maplibre-gl.js'), import('../vendor/pmtiles/pmtiles.js'), import('../vendor/protomaps-basemaps/basemaps.js')]);
    const url = new URL('basis/welt.pmtiles', location.href).href;
    const archive = new PMTiles(url);
    await archive.getHeader();
    const protocol = new Protocol();
    protocol.add(archive);
    addProtocol('pmtiles', protocol.tile);
    hintergrund = new MlMap({
      container: 'hintergrund', interactive: false, attributionControl: false, center: [7.3, 50.0], zoom: 5.4,
      style: { version: 8, glyphs: `${new URL('fonts/', location.href).href}{fontstack}/{range}.pbf`, sources: { basemap: { type: 'vector', url: `pmtiles://${url}` } },
        layers: layers('basemap', namedFlavor('grayscale'), { lang: 'de' }).filter((l) => !/^(pois$|roads_shields)/.test(l.id)).map(nurRegular) },
    });
  } catch (err) { console.warn('Hintergrundkarte nicht verfügbar:', err?.message ?? err); }
})();
