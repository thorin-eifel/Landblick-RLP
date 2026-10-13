import { FullscreenControl, Map as MlMap, Marker, NavigationControl, Popup, ScaleControl, addProtocol } from '../../vendor/maplibre-gl/maplibre-gl.js';
import { PMTiles, Protocol } from '../../vendor/pmtiles/pmtiles.js';
import { createFlow, registerArrow } from '../fluss.js';
import { MIL_COLOUR, iconStatus, registerIcons, registerMedieval, registerSigns } from '../icons.js';
import { registerInfra } from '../infra.js';
import { buildRainLegend } from '../legend.js';
import { createLight } from '../licht.js';
import { FAUNA_SOURCE, faunaPoints, registerFauna, registerMedievalPatterns } from '../medieval.js';
import { ping as pingSound, silence as silenceSound, sizzle as sizzleSound, zap as zapSound } from '../ping-sound.js';
import { RELIEF_ATTRIBUTION, demTile, glyphsUrl, setupRelief } from '../relief.js';
import { createRipples } from '../ripples.js';
import { SWEEP_GREEN, createSweep } from '../sweep.js';
import { KIND_MIN_ZOOM } from '../zellen.js';
import { loadTerrain } from '../terrain.js';
import { ansichtAusAdresse } from '../ansicht.js';
import { $, getJSON, h, link } from '../util.js';
import { createWind, fillWindLegend } from '../wind.js';
import { applyBasemap, wireElevation } from './basiskarte.js';
import { debugHook } from './debug.js';
import { applyLayerFilters } from './ebenen.js';
import { palette, sevColor } from './farben.js';
import { VIG_FADE_KM, VIG_ID, circle, vignette } from './geometrie.js';
import { aussenDaten, ladeVignette, legeBildAn } from './vignette.js';
import { pushMapData } from './messnetz.js';
import { windroseUpdate } from './mittelalter.js';
import { INFRA_LAYER_IDS } from './orte.js';
import { showPopup } from './popup.js';
import { initSearch } from './suche-karte.js';
import { applyWind, fillTempLegend, showFlowWind, trackLegendBottom } from './wetterkarte.js';
import { ABFLUSS_URL, CORE_URL, GEB_JAHR, GEB_URL, RING_URL, START_VIEW, SYMBOL_LAYERS, TILES_URL, light, map, gebOk, reduceMotion, reliefOk, ripples, setAbflussOk, setBasemapOk, setCoreOk, setFlow, setGebOk, setKlippenOk, setLight, setMap, setMapReady, setPopup, setReliefOk, setRingOk, setRipples, setSweep, setWind, setWindLow, state, sweep, wind, windLow } from './zustand.js';

// ------------------------------------------------------------------ Karte
// Rahmen der Karte: Umriss von Rheinland-Pfalz (web/geo/rlp.geojson: 6,11–8,51 E, 48,97–50,94 N) mit gleichem Rand ringsum, damit der Mittelpunkt
// des Rahmens der Mittelpunkt des Landes ist. MapLibre rückt beim Herauszoomen auf diese Mitte und kürzt den Zoom, bis der Rahmen den Bildschirm füllt.
const LAND_MAX_ZOOM = 6.5;   // Übersicht: darunter eine Zahl je Land, darüber je Kreis, ab KIND_MIN_ZOOM.events die Einzelmeldungen
const RLP_BBOX = [[6.112, 48.967], [8.508, 50.942]];
const RAND_LON = 1.2, RAND_LAT = 0.75;   // Grad Luft um den kleinsten Ausschnitt
const RLP_RAHMEN = [[RLP_BBOX[0][0] - RAND_LON, RLP_BBOX[0][1] - RAND_LAT], [RLP_BBOX[1][0] + RAND_LON, RLP_BBOX[1][1] + RAND_LAT]];   // erster Rahmen bis zur ersten Messung

/** Kleinster Zoom: ganz Rheinland-Pfalz gerade im Bild. Dort liegt das Land genau in der Mitte (ein Schwenk springt zurück), egal woher man kam. */
function zentriereLand(m) {
  const stelle = () => {
    const cam = m.cameraForBounds(RLP_BBOX, { padding: 24 });
    if (!cam) return null;
    // Rahmen = Ausschnitt bei kleinstem Zoom um die Landesmitte plus Rand; sonst hebt ein zu enger Rahmen den Zoom an und das Land sitzt nicht mittig
    const { clientWidth: w, clientHeight: h } = m.getCanvas(), welt = 512 * 2 ** cam.zoom, rad = Math.PI / 180;
    const y = (lat) => (0.5 - Math.log(Math.tan(Math.PI / 4 + lat * rad / 2)) / (2 * Math.PI)) * welt;
    const lat = (py) => (2 * Math.atan(Math.exp((0.5 - py / welt) * 2 * Math.PI)) - Math.PI / 2) / rad;
    const dLon = (w / welt) * 180 + RAND_LON, yc = y(cam.center.lat);
    m.setMaxBounds([[cam.center.lng - dLon, lat(yc + h / 2) - RAND_LAT], [cam.center.lng + dLon, lat(yc - h / 2) + RAND_LAT]]);
    m.setMinZoom(cam.zoom);
    return cam;
    return null;
  };
  let cam = stelle();
  m.on('resize', () => { cam = stelle(); });
  m.on('moveend', () => {
    if (!cam || m.getZoom() > m.getMinZoom() + 0.02) return;
    const c = m.getCenter();
    if (Math.abs(c.lng - cam.center.lng) > 1e-4 || Math.abs(c.lat - cam.center.lat) > 1e-4) m.easeTo({ center: cam.center, duration: reduceMotion ? 0 : 300 });
  });
}

export async function initMap() {
  const c = palette();
  const m = state.meta;
  setMap(new MlMap({
    container: 'map',
    style: { version: 8, sources: {}, glyphs: glyphsUrl(), layers: [{ id: 'bg', type: 'background', paint: { 'background-color': c.bg } }] },
    center: [m.center?.lon ?? START_VIEW.lon, m.center?.lat ?? START_VIEW.lat], zoom: 8.0, attributionControl: false, dragRotate: false, pitchWithRotate: false,
    locale: { 'FullscreenControl.Enter': 'Vollbild', 'FullscreenControl.Exit': 'Vollbild beenden', 'NavigationControl.ZoomIn': 'Vergrößern', 'NavigationControl.ZoomOut': 'Verkleinern' },
    maxBounds: RLP_RAHMEN,   // um Rheinland-Pfalz zentriert: ganz herausgezoomt sitzt das Land mittig, egal wo der Start liegt
  }));
  map.touchZoomRotate.disableRotation();
  zentriereLand(map);
  map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
  if (document.fullscreenEnabled || document.webkitFullscreenEnabled) map.addControl(new FullscreenControl({ container: document.querySelector('.map-wrap') }), 'top-right');      // Karte samt Cartouche, Windrose und Legende
  map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-right');
  setPopup(new Popup({ closeButton: true, maxWidth: '320px' }));

  await new Promise((res) => map.on('load', res));
  map.addSource('radius', { type: 'geojson', data: circle(m.center.lat, m.center.lon, m.radius_km) });
  // Verdunklung unter den Daten-Ebenen, nur bei eingeblendetem Luftverkehr: 80 % Schwarz bei 50 % Deckkraft = 0,4 wirksam
  map.addLayer({ id: 'air-dim', type: 'background', layout: { visibility: 'none' }, paint: { 'background-color': '#000000', 'background-opacity': 0.8 * 0.5 } });
  // Kein sichtbarer Kreis mehr; 'radius-fill' bleibt als unsichtbarer Anker, vor dem alle anderen Ebenen einsortiert werden
  map.addLayer({ id: 'radius-fill', type: 'fill', source: 'radius', layout: { visibility: 'none' }, paint: { 'fill-color': SWEEP_GREEN, 'fill-opacity': 0 } });
  const vig = await ladeVignette();   // Maske entlang der Landesgrenze; ohne sie bleibt der Kreis
  map.addSource('vignette', { type: 'geojson', data: vig ? aussenDaten(vig) : vignette(m.center.lat, m.center.lon, m.radius_km) });

  map.addSource('events', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  const isPoly = ['==', ['geometry-type'], 'Polygon'], isMulti = ['==', ['geometry-type'], 'MultiPolygon'];
  map.addLayer({ id: 'ev-fill', type: 'fill', source: 'events', filter: ['any', isPoly, isMulti],
    paint: { 'fill-color': sevColor(c), 'fill-opacity': 0.22 } });
  map.addLayer({ id: 'ev-outline', type: 'line', source: 'events', filter: ['any', isPoly, isMulti],
    paint: { 'line-color': sevColor(c), 'line-width': 2 } });
  map.addLayer({ id: 'ev-line-halo', type: 'line', source: 'events', layout: { 'line-cap': 'round' }, paint: { 'line-color': c.white, 'line-width': ['case', ['==', ['get', 'type'], 'congestion'], 10, ['==', ['get', 'severity'], 'info'], 6.5, 8], 'line-opacity': 0.8 } });
  map.addLayer({ id: 'ev-line', type: 'line', source: 'events', filter: ['any', ['==', ['geometry-type'], 'LineString'], ['==', ['geometry-type'], 'MultiLineString']],
    paint: { 'line-color': sevColor(c), 'line-width': ['case', ['==', ['get', 'type'], 'congestion'], 6, ['==', ['get', 'severity'], 'info'], 3, 4.5], 'line-opacity': 0.9 } });
  state.signsOk = registerSigns(map);
  registerArrow(map);
  state.iconsOk = await registerIcons(map, palette());
  try { registerMedieval(map); registerMedievalPatterns(map); registerFauna(map); registerInfra(map); map.addSource(FAUNA_SOURCE, { type: 'geojson', data: faunaPoints() }); } catch (err) { console.warn('Zeichen der historischen Karte fehlen:', err); }
  if (!state.iconsOk) $('.map-note')?.append(` · Symbole nicht geladen, Ersatzdarstellung (${iconStatus.errors[0] ?? 'Dateien fehlen'})`);
  // Rückfall ohne Icons (Dateien fehlen): die früheren Kreise
  map.addLayer({ id: 'ev-point', type: 'circle', source: 'events', filter: ['==', ['geometry-type'], 'Point'],
    layout: { visibility: state.iconsOk ? 'none' : 'visible' },
    paint: { 'circle-radius': 7, 'circle-color': sevColor(c), 'circle-stroke-color': c.white, 'circle-stroke-width': 1.5 } });
  // Symbole: Punkte am Ort, Linien in der Mitte. Wichtigeres wird zuerst gesetzt und nicht überdeckt.
  const iconImage = ['concat', 'ico-', ['get', 'icon'], '-', ['coalesce', ['get', 'lvl'], ['get', 'severity']]];
  const sym = (id, placement, works) => map.addLayer({
    id, type: 'symbol', source: 'events', minzoom: works ? 10 : 0,
    layout: { visibility: state.iconsOk ? 'visible' : 'none', 'symbol-placement': placement, 'icon-image': iconImage, 'icon-size': 1,
      // Plaketten stehen immer aufrecht; nur bewegte Objekte (Flugzeuge) drehen sich. Bei line-center würde MapLibre sonst dem Linienverlauf folgen.
      'icon-rotation-alignment': 'viewport', 'icon-rotate': 0, 'icon-keep-upright': false,
      // Stau, Sperrung, Warnung dürfen sich überlagern und werden nie ausgeblendet; Baustellen weichen einander aus
      'icon-allow-overlap': !works, 'icon-padding': 3, 'symbol-sort-key': ['-', 0, ['get', 'severity_rank']] },
  });
  sym('ev-sym-pt', 'point', false); sym('ev-sym-ln', 'line-center', false);
  // Örtliche Baustellen (Mobilitätsatlas, Autobahn-Baustellen) erst ab Zoom 10 als Symbol; davor kleine Punkte, sonst Teppich
  sym('ev-sym-pt-w', 'point', true); sym('ev-sym-ln-w', 'line-center', true);
  map.addLayer({ id: 'ev-dot-w', type: 'circle', source: 'events', maxzoom: 10,
    layout: { visibility: state.iconsOk ? 'visible' : 'none' },
    paint: { 'circle-radius': 3.5, 'circle-color': sevColor(c), 'circle-stroke-color': c.white, 'circle-stroke-width': 1 } });

  // Übersicht bei kleinen Zoomstufen (unter EVENTS_MIN_ZOOM): eine Zahl je Land, näher je Kreis, an der Lage der Fläche (start.json `einheiten`);
  // ohne dieses Feld (alter Export) je Rasterzelle. Von Einzelmeldungen wichtig nach unwichtig: Warnungen stehen schon hier als Punkte.
  map.addSource('dichte', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  const LAND = ['==', ['get', 'level'], 'land'], KREIS = ['==', ['get', 'level'], 'kreis'];
  const rad = (lo, hi) => ['interpolate', ['linear'], ['sqrt', ['get', 'n']], 1, lo, 60, hi];
  const circ = (id, filter, r, minzoom, maxzoom) => map.addLayer({ id, type: 'circle', source: 'dichte', minzoom, maxzoom, filter,
    layout: { 'circle-sort-key': ['*', -1, ['get', 'n']] },
    paint: { 'circle-radius': r, 'circle-color': sevColor(c, 'sev'), 'circle-opacity': 0.88, 'circle-stroke-color': c.white, 'circle-stroke-width': 1.5 } });
  const num = (id, filter, size, minzoom, maxzoom) => map.addLayer({ id, type: 'symbol', source: 'dichte', minzoom, maxzoom, filter,
    layout: { 'text-field': ['to-string', ['get', 'n']], 'text-font': ['Noto Sans Regular'], 'text-size': size, 'text-allow-overlap': true },
    paint: { 'text-color': ['match', ['get', 'sev'], 'warning', '#111', 'notice', '#111', c.white] } });   // dunkle Schrift auf Orange und Gelb (Kontrast), weiß auf Rot und Blau
  const name = (id, filter, size, off, minzoom, maxzoom) => map.addLayer({ id, type: 'symbol', source: 'dichte', minzoom, maxzoom, filter,
    layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': size, 'text-anchor': 'top', 'text-offset': off, 'text-optional': true,
      'symbol-sort-key': ['*', -1, ['get', 'n']], 'text-max-width': 8 },
    paint: { 'text-color': c.ink ?? '#222', 'text-halo-color': c.white, 'text-halo-width': 2, 'text-halo-blur': 0.3 } });
  circ('dichte-land', LAND, rad(16, 34), 0, LAND_MAX_ZOOM);  num('dichte-land-zahl', LAND, 14, 0, LAND_MAX_ZOOM);  name('dichte-land-name', LAND, 13, [0, 2.2], 0, LAND_MAX_ZOOM);
  circ('dichte-kreis', KREIS, rad(8, 22), LAND_MAX_ZOOM, KIND_MIN_ZOOM.events);  num('dichte-kreis-zahl', KREIS, 12, LAND_MAX_ZOOM, KIND_MIN_ZOOM.events);
  name('dichte-kreis-name', KREIS, 11, [0, 1.6], 7, KIND_MIN_ZOOM.events);

  // Luftverkehr: eigene Quelle, weil sie sich jede Sekunde bewegt
  map.addSource('air', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'air-circle', type: 'circle', source: 'air', layout: { visibility: 'none' },
    paint: { 'circle-radius': 5, 'circle-opacity': 0, 'circle-stroke-color': sevColor(c), 'circle-stroke-width': 2 } });
  map.addLayer({ id: 'air-sym', type: 'symbol', source: 'air', layout: { visibility: 'none', 'icon-image': ['concat', ['get', 'img'], ['get', 'severity']],
    // Hubschrauber (Seitenansicht) bleiben aufrecht, Flächenflugzeuge drehen sich mit dem Kurs
    'icon-rotate': ['case', ['in', ['get', 'klass'], ['literal', ['heli', 'milheli']]], 0, ['coalesce', ['to-number', ['get', 'track']], 0]], 'icon-rotation-alignment': 'map', 'icon-allow-overlap': true, 'icon-size': 1 } });

  map.addSource('stations', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'st-circle', type: 'circle', source: 'stations', layout: { visibility: state.iconsOk ? 'none' : 'visible' },
    paint: { 'circle-radius': 5, 'circle-color': c.white, 'circle-stroke-color': c.info, 'circle-stroke-width': 2.5 } });
  map.addLayer({ id: 'st-sym', type: 'symbol', source: 'stations', layout: { visibility: state.iconsOk ? 'visible' : 'none', 'icon-image': 'ico-pegel-info', 'icon-rotation-alignment': 'viewport',
    // Dichte steuern: große Läufe immer, kleinere Läufe erst bei näherem Zoom (Größe 0 = nicht gezeichnet, ohne Kollisionsfläche);
    // nichts übereinander; bei Gedränge gewinnt der größere Lauf, bei gleichem Rang der Pegel mit Warnstufe
    // (MapLibre erlaubt nur einen Zoom-Ausdruck: die Stufen stehen deshalb in den Stützstellen der einen Interpolation)
    'icon-size': ['interpolate', ['linear'], ['zoom'],
      7, ['case', ['<=', ['get', 'rank'], 1], 0.55, 0], 8.9, ['case', ['<=', ['get', 'rank'], 1], 0.7, 0],
      9, ['case', ['<=', ['get', 'rank'], 1], 0.7, ['<=', ['get', 'rank'], 3], 0.7, 0], 10.4, ['case', ['<=', ['get', 'rank'], 3], 0.85, 0],
      10.5, 0.85, 11, 0.9],
    'icon-allow-overlap': false, 'icon-padding': 3,
    'symbol-sort-key': ['-', ['get', 'rank'], ['case', ['to-boolean', ['get', 'state']], 5, 0]] } });

  // Messstationen Luft und Strahlung: eigene Quelle, Plakette in der Stufenfarbe je Messwert
  map.addSource('env', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'env-circle', type: 'circle', source: 'env', layout: { visibility: 'none' },
    paint: { 'circle-radius': 5, 'circle-color': c.white, 'circle-stroke-color': sevColor(c), 'circle-stroke-width': 2.5 } });
  map.addLayer({ id: 'env-sym', type: 'symbol', source: 'env', layout: { visibility: 'none',
    'icon-image': ['case', ['has', 'tclass'], ['concat', 'wx-', ['to-string', ['get', 'tclass']]], ['concat', 'ico-', ['get', 'icon'], '-', ['get', 'severity']]],
    'icon-rotation-alignment': 'viewport', 'icon-size': ['interpolate', ['linear'], ['zoom'], 7, 0.55, 11, 1],
    // Messstellen nicht übereinander legen; Warnungen und Auffälliges zuerst, damit sie bei Gedränge stehen bleiben
    'icon-allow-overlap': false, 'icon-padding': 2,
    'symbol-sort-key': ['match', ['get', 'severity'], 'critical', 0, 'warning', 1, 'notice', 2, 3] } });

  map.addLayer({ id: 'wxst-label', type: 'symbol', source: 'env', minzoom: 9, filter: ['==', ['get', 'kind'], 'weather'], layout: { visibility: 'none',
    'text-field': ['get', 'label'], 'text-font': ['Noto Sans Regular'], 'text-size': 11, 'text-offset': [0, 1.1], 'text-anchor': 'top', 'text-optional': true },
    paint: { 'text-color': '#1f3a5f', 'text-halo-color': '#fff', 'text-halo-width': 1.8 } });
  // Tankstellen (Tankerkönig): Zapfsäule am Standort, ab Zoom 11 der Preis für E10 daneben; Anklicken öffnet die Preiskarte
  map.addSource('tank', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'tank-circle', type: 'circle', source: 'tank', layout: { visibility: 'none' },
    paint: { 'circle-radius': 5, 'circle-color': c.white, 'circle-stroke-color': '#c2570c', 'circle-stroke-width': 2.5 } });
  map.addLayer({ id: 'tank-sym', type: 'symbol', source: 'tank', minzoom: 9.5, layout: { visibility: 'none', 'icon-image': 'stop-tanken',
    'icon-size': ['interpolate', ['linear'], ['zoom'], 9.5, 0.5, 13, 0.85], 'icon-allow-overlap': false, 'icon-padding': 2 } });
  map.addLayer({ id: 'tank-label', type: 'symbol', source: 'tank', minzoom: 12, layout: { visibility: 'none', 'text-field': ['get', 'label'], 'text-font': ['Noto Sans Regular'],
    'text-size': 11, 'text-offset': [0, 1.2], 'text-anchor': 'top', 'text-optional': true },
    paint: { 'text-color': '#8a3d06', 'text-halo-color': '#fff', 'text-halo-width': 1.8 } });

  for (const id of ['ev-fill', 'ev-outline', 'ev-line', 'ev-point', ...SYMBOL_LAYERS, 'air-circle', 'air-sym', 'st-circle', 'st-sym', 'env-circle', 'env-sym', 'tank-circle', 'tank-sym', ...INFRA_LAYER_IDS, 'routes-hit']) {
    map.on('mouseenter', id, () => (map.getCanvas().style.cursor = 'pointer'));
    map.on('mouseleave', id, () => (map.getCanvas().style.cursor = ''));
  }
  map.on('click', (e) => {
    const order = ['air-sym', 'air-circle', ...SYMBOL_LAYERS, ...INFRA_LAYER_IDS, 'routes-hit', 'ev-point', 'env-sym', 'env-circle', 'tank-sym', 'tank-circle', 'st-sym', 'st-circle', 'ev-line', 'ev-fill'];
    const hit = map.queryRenderedFeatures(e.point, { layers: order.filter((l) => map.getLayer(l)) })[0];
    if (!hit) {   // dünne Linien: Treffer in einem kleinen Kasten um den Zeiger; Senken vor Linien
      const kasten = [[e.point.x - 6, e.point.y - 6], [e.point.x + 6, e.point.y + 6]];
      const ab = map.queryRenderedFeatures(kasten, { layers: ['bm-senken-circle', 'bm-abfluss-gross', 'bm-abfluss-klein'].filter((l) => map.getLayer(l) && map.getLayoutProperty(l, 'visibility') !== 'none') })
        .sort((a, b) => (a.layer.id === 'bm-senken-circle' ? -1 : 0) - (b.layer.id === 'bm-senken-circle' ? -1 : 0))[0];
      if (ab) showPopup(ab.properties, ab.layer.id === 'bm-senken-circle' ? 'senke' : 'abfluss', e.lngLat);
      return;
    }
    showPopup(hit.properties, hit.layer.id === 'routes-hit' ? 'route' : hit.layer.id.startsWith('inf-') ? 'infra' : hit.layer.id.startsWith('tank-') ? 'tank' : hit.layer.id.startsWith('st-') ? 'station' : hit.layer.id.startsWith('env-') ? 'env' : 'event', e.lngLat);
  });

  map.fitBounds(RLP_BBOX, { padding: 24, animate: false });   // Start: ganz Rheinland-Pfalz, mittig (das Gebiet steht fest, es gibt keinen gewählten Mittelpunkt)
  const ansicht = ansichtAusAdresse(location.hash);   // Link auf eine Ansicht: #zoom/breite/länge
  if (ansicht) map.jumpTo({ center: [ansicht.lon, ansicht.lat], zoom: ansicht.zoom });
  await setupBasemap();
  setReliefOk(await setupRelief(map));
  if (reliefOk) setLight(createLight(map, { demTile, onError: (e) => console.warn('Licht:', e), reduce: reduceMotion, wind: () => { const c = map.getCenter(); const w = wind?.sample?.(c.lng, c.lat); return w ? { speed: w.speed, from: w.from } : null; } }));
  setMapReady(true);
  map.on('move', windroseUpdate);
  initSearch();
  if (location.hash === '#debug') debugHook(map); // nur für Prüfungen im Browser
  setRipples(createRipples(map, { center: state.meta.center, radiusKm: state.meta.radius_km, fadeKm: VIG_FADE_KM, vig: vig?.faktor, onSizzle: sizzleSound }));
  // Untere Schicht zuerst anlegen, damit die obere (reiner Modellwind) darüber liegt
  setWindLow(createWind(map, { center: state.meta.center, radiusKm: state.meta.radius_km, fadeKm: VIG_FADE_KM, vig: vig?.faktor, adjusted: true }));
  setWind(createWind(map, { center: state.meta.center, radiusKm: state.meta.radius_km, fadeKm: VIG_FADE_KM, vig: vig?.faktor }));
  loadTerrain('data/terrain.json').then((t) => { state.terrain = t; windLow.setTerrain(t); applyWind(); });
  ripples.setWind((lon, lat, out) => wind.sample(lon, lat, out));   // Dampf des Lasers driftet mit dem Modellwind
  setFlow(createFlow(map, { sampleWind: (lon, lat, out) => wind.sample(lon, lat, out), reduce: reduceMotion, onWind: showFlowWind }));   // Wellen auf Stillgewässern ziehen mit dem Modellwind
  const windBar = $('#wind-bar'); if (windBar) fillWindLegend(windBar);
  const windBarLow = $('#wind-bar-low'); if (windBarLow) fillWindLegend(windBarLow, undefined, true);
  fillTempLegend();
  trackLegendBottom();
  buildRainLegend($('#rain-strip'), $('#rain-labels'));
  setSweep(createSweep(map, { center: state.meta.center, radiusKm: state.meta.radius_km, mil: MIL_COLOUR, reducedMotion: reduceMotion, onPing: (e) => (e.zap ? zapSound(e) : pingSound(e)) }));
  const laserBtn = $('#laser');   // Radarstrahl als Laser: verdampft den Regen, der fällt später wieder herab
  if (laserBtn) {
    if (reduceMotion) laserBtn.hidden = true;   // ohne Bewegung kein Strahl
    else laserBtn.addEventListener('click', () => {
      const on = laserBtn.getAttribute('aria-pressed') !== 'true';
      laserBtn.setAttribute('aria-pressed', String(on));
      sweep.setLaser(on);
      if (!on) silenceSound();
      ripples.setLaser(on ? () => sweep.beam() : null);
    });
  }
  applyBasemap();
  // Vignette zuletzt und ohne Zielebene: liegt damit über Karte, Daten und Sweep
  map.addLayer({ id: VIG_ID, type: 'fill', source: 'vignette', paint: { 'fill-color': '#000000', 'fill-opacity': ['get', 'a'], 'fill-antialias': false } });
  if (vig) legeBildAn(map, vig);   // Verlauf entlang der Landesgrenze über der schwarzen Außenfläche
  wireElevation();
  $('#licht-hoehe')?.addEventListener('input', (e) => light?.setHeight(Number(e.target.value)));
  applyLayerFilters();
  pushMapData();
}

// Basiskarte aus eigener PMTiles-Datei. Fehlt sie oder kann der Server keine Teilabrufe (HTTP Range),
// bleibt die Karte ohne Basis benutzbar und sagt das ehrlich im Kartenhinweis.
export async function setupBasemap() {
  // Die Kartenleiste ist aus der Seite genommen (Quellenangabe steht im Footer und unter Quellen und Lizenzen); ohne Element läuft es still weiter
  const note = $('.map-note') ?? document.createElement('span');
  try {
    const url = new URL(TILES_URL, location.href).href;
    const archive = new PMTiles(url);
    await archive.getHeader(); // wirft, wenn Datei fehlt oder der Server Range nicht unterstützt
    const protocol = new Protocol();
    protocol.add(archive);
    addProtocol('pmtiles', protocol.tile);
    map.addSource('basemap', { type: 'vector', url: `pmtiles://${url}` });
    map.addSource('rlp-grenze', { type: 'geojson', data: new URL('geo/rlp.geojson', location.href).href });   // Landesgrenze Rheinland-Pfalz (tools/build_landesgrenze.py)
    // Weinberge und Obstanlagen fehlen in den Kacheln: eigene Flächen aus data/anbau.json (OpenStreetMap, wöchentlich), Schalter "Obst und Wein"
    map.addSource('anbau', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
    (state.zellen ? Promise.resolve(null) : getJSON('data/anbau.json')).then((j) => { if (Array.isArray(j?.features)) map.getSource('anbau')?.setData(j); }).catch(() => {});
    setBasemapOk(true);
    try {   // Kern mit Gebäudedetail; fehlt er, bleibt die Karte wie sie ist (Gebäude dann nur grob aus Zoom 13, keine Hausnummern)
      const coreUrl = new URL(CORE_URL, location.href).href;
      const core = new PMTiles(coreUrl);
      await core.getHeader();
      protocol.add(core);
      map.addSource('basemap-core', { type: 'vector', url: `pmtiles://${coreUrl}` });   // kein tileSize: MapLibre 5 lässt bei Vektorquellen nur 512 zu (mit 256 lud der Kern gar nicht, und um Irrel fehlten die Gebäude)
      setCoreOk(true);
    } catch (err) { console.warn('Kernkarte (Zoom 15) nicht verfügbar:', err?.message ?? err); }
    try {   // Ring um den Kern (nur Zoom 14): Häuserumrisse im restlichen Radius, ohne Hausnummern
      const ringUrl = new URL(RING_URL, location.href).href;
      const ring = new PMTiles(ringUrl);
      await ring.getHeader();
      protocol.add(ring);
      map.addSource('basemap-ring', { type: 'vector', url: `pmtiles://${ringUrl}` });
      setRingOk(true);
    } catch (err) { console.warn('Ringkarte (Zoom 14) nicht verfügbar:', err?.message ?? err); }
    try {   // Gebäudeumrisse aus den Hausumringen (Land) und OSM (außerhalb): ersetzt Gebäude aus Kern und Ring; fehlt die Datei, bleibt es bei Kern und Ring
      const gebUrl = new URL(GEB_URL, location.href).href;
      const geb = new PMTiles(gebUrl);
      await geb.getHeader();
      protocol.add(geb);
      map.addSource('basemap-geb', { type: 'vector', url: `pmtiles://${gebUrl}` });   // Zoom 14 gilt ab Kartenzoom 14, Zoom 15 ab 15 (darüber hochgezoomt)
      setGebOk(true);
    } catch (err) { console.warn('Gebäudeebene (Hausumringe) nicht verfügbar:', err?.message ?? err); }
    try {   // Abflussbahnen und Senken aus dem Gelände (tools/build_abfluss.py); fehlt die Datei, bleiben die Schalter ohne Wirkung
      const abUrl = new URL(ABFLUSS_URL, location.href).href;
      const ab = new PMTiles(abUrl);
      await ab.getHeader();
      protocol.add(ab);
      map.addSource('abfluss', { type: 'vector', url: `pmtiles://${abUrl}` });
      setAbflussOk(true);
    } catch (err) { console.warn('Abflussebene nicht verfügbar:', err?.message ?? err); }
    try {   // Wände aus dem Geländemodell (tools/build_klippen_dgm.py): Vektorkacheln Zoom 13; fehlen sie, zeichnet die Karte nur die OSM-Klippen
      const kb = new URL('tiles/klippen/', location.href).href;
      const km = await fetch(kb + 'meta.json').then((r) => (r.ok ? r.json() : null)).catch(() => null);
      if (km) {
        map.addSource('klippen', { type: 'vector', tiles: [kb + '{z}/{x}/{y}.pbf'], minzoom: 13, maxzoom: 13 });
        setKlippenOk(true);
      }
    } catch (err) { console.warn('Klippen aus dem Gelaendemodell nicht verfuegbar:', err?.message ?? err); }
    note.replaceChildren('Karte: ', link('https://www.openstreetmap.org/copyright', '© OpenStreetMap-Mitwirkende (ODbL)'), ' · Protomaps');
    if (gebOk) note.append(' · Gebäude in Rheinland-Pfalz: ', link('https://lvermgeo.rlp.de', `© GeoBasis-DE / LVermGeoRP (${GEB_JAHR}), dl-de/by-2-0 [Daten bearbeitet]`));
    if (globalThis.mlcontour) note.append(' · ', RELIEF_ATTRIBUTION);
  } catch (err) {
    console.warn('Basiskarte nicht verfügbar:', err?.message ?? err);
    note.replaceChildren('Basiskarte nicht verfügbar');
  }
}
