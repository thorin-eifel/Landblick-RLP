// Laufzeitobjekte der Seite. Andere Module lesen sie über die gebundenen Importe; gesetzt wird nur über die Setzer unten.
export let map = null, popup = null, sweep = null, ripples = null, wind = null, windLow = null, flow = null;
export let mapReady = false, basemapOk = false, coreOk = false, ringOk = false, gebOk = false, reliefOk = false, klippenOk = false, hangOk = false;
export let light = null;   // Lichtquelle am Zeiger (js/licht.js)
export function setMap(v) { map = v; }
export function setPopup(v) { popup = v; }
export function setSweep(v) { sweep = v; }
export function setRipples(v) { ripples = v; }
export function setWind(v) { wind = v; }
export function setWindLow(v) { windLow = v; }
export function setFlow(v) { flow = v; }
export function setMapReady(v) { mapReady = v; }
export function setBasemapOk(v) { basemapOk = v; }
export function setCoreOk(v) { coreOk = v; }
export function setRingOk(v) { ringOk = v; }
export function setGebOk(v) { gebOk = v; }
export function setKlippenOk(v) { klippenOk = v; }
export function setHangOk(v) { hangOk = v; }
export function setReliefOk(v) { reliefOk = v; }
export function setLight(v) { light = v; }

// Startansicht und Bezugspunkt für Entfernungen: Irrel (Ortsmitte, Koordinate vom Betreiber angegeben).
export const START_VIEW = { lat: 49.84615562322509, lon: 6.456057281843173 };
// Radarbild blendet beim Hineinzoomen aus (Zoom 11 bis 13); die Regentropfen-Animation bleibt und läuft aus denselben Radardaten weiter
export const RADAR_OPACITY = ['interpolate', ['linear'], ['zoom'], 11, 0.6, 13, 0];
export const RING_URL = 'tiles/ring.pmtiles'; // Zoom 14 rund um den Kern bis zum 120-km-Rand: nur dafür da, dass Häuserumrisse im ganzen Gebiet stehen
export const CORE_URL = 'tiles/core.pmtiles'; // Kern um Irrel mit Zoom 15: Gebäude und Hausnummern (die große Datei reicht nur bis Zoom 13)
export const GEB_URL = 'tiles/gebaeude.pmtiles'; // Gebäudeumrisse: Hausumringe RLP im Land (dl-de/by-2-0), OSM außerhalb; ersetzt die Gebäude aus Kern und Ring (tools/build_gebaeude_rlp.py)
export const GEB_JAHR = 2026; // Jahr des Datenbezugs der Hausumringe (Vermerk)
export const TILES_URL = 'tiles/region.pmtiles'; // OSM-Ausschnitt (Protomaps-Build), liegt auf demselben Server

// Schalter im Ebenenmenü → Ereignisarten (Schema: app/models.py EventType). Ebenen ohne Ereignisart (Pegel, Radar, Blitze, Relief, Natur, Basiskarte) stehen nicht hier.
export const GROUPS = { traffic: ['traffic', 'congestion'], transit: ['transit'], warning: ['warning', 'weather'], flood: ['flood'], air: ['aircraft'],
  airq: ['air'], rad: ['radiation'], quake: ['earthquake'], fire: ['fire'] };
export const state = { gopen: new Map(), net: null, within: 'now', layers: { warning: false, flood: false, fire: false, quake: false, news: false, social: false, traffic: false, transit: false, stops: false, air: false, signs: false,
    radar: true, drops: true, wind: false, windlow: false, blitz: true, wehr: false, bruecke: false, rast: false, civic: false, cemetery: false, hike: false, bike: false, charge: false, wturb: false, emerg: false, gew: true, tank: false, wxst: true, airq: true, rad: true, nature: true, herCastle: false, herArch: false, herMonastery: false, herBuilding: false, herChurch: false, herChapel: false, herCross: false, herMill: false, herFord: false, herBorder: false, herGallows: false, herWell: false, relief: true,
    vegForest: true, vegMeadow: true, vegScrub: true, vegField: true, vegVine: true, vegWet: true, vegRock: true,
    bndCountry: true, bndRegion: true, bndCounty: true, bndLocal: false, protNature: true, protPark: true, protMil: true, flow: false, cliffs: true, hang: false, buildings: true, contours: true, licht: false, roadHw: true, roadMain: true, roadMid: true, roadMinor: true, roadPath: true, rail: true, roadNames: true, medieval: false }, meta: null, env: null, radar: null, wind: null, blitz: null, stops: null, landmarks: null, base: [], airRaw: [], airAt: 0, all: [], events: [], gew: null, wx: null, idx: null, fuel: null, infra: null, routen: null, themen: null, statuses: [], iconsOk: false, zellen: null, start: null, warnStubs: [], gebiet: { land: '', ars: '' } };
export const AIR_IMG = { civil: 'plane-', mil: 'mplane-', heli: 'heli-', milheli: 'mheli-' }; // Bildname je Klasse, dazu die Stufe
export const AIR_POLL_MS = 15000;  // aircraft.json: so oft schreibt die Live-Schleife
export const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
if (reduceMotion) { state.layers.drops = false; const cb = document.querySelector('input[data-layer="drops"]'); if (cb) cb.checked = false; } // Animation nur auf Wunsch
export const SYMBOL_LAYERS = ['ev-sym-pt', 'ev-sym-ln', 'ev-sym-pt-w', 'ev-sym-ln-w', 'ev-dot-w'];
