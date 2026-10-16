import { Marker, Popup } from '../../vendor/maplibre-gl/maplibre-gl.js';
import { mountSearch, zoomFor } from '../suche.js';
import { $, getJSON } from '../util.js';
import { map } from './zustand.js';

// Suche: Index wird erst beim ersten Fokus geladen; Treffer bekommen eine Markierung mit Namen, Art und Ort (nur Text, keine Adressen)
export let searchMarker = null;
export function initSearch() {
  const input = $('#suche-q'), list = $('#suche-liste'), status = $('#suche-status');
  if (!input || !list || !status) return;
  const clear = () => { searchMarker?.remove(); searchMarker = null; };
  // Vollbild zeigt die ganze Lageseite (Menü mit Suchzeile und Detailfeld bleiben), die Suchzeile muss deshalb nicht umziehen
  mountSearch({
    input, list, status,
    getNear: () => { const c = map.getCenter(); return { lat: c.lat, lon: c.lng }; },
    loadParts: () => Promise.all(['data/suche_geo.json', 'data/suche.json'].map((p) => getJSON(p).catch(() => null))),
    onPick: (e) => {
      clear();
      if (!e) return;
      const el = document.createElement('div');                     // Träger ohne eigene Drehung (MapLibre setzt dessen transform)
      el.className = 'search-pin';
      el.append(document.createElement('span'));
      const box = document.createElement('div');
      box.className = 'pop search-pop';
      const b = document.createElement('h3'); b.textContent = e.name;
      const t = document.createElement('p'); t.className = 'k'; t.textContent = e.ort ? `${e.typ} · ${e.ort}` : e.typ;
      box.append(b, t);
      searchMarker = new Marker({ element: el, anchor: 'bottom' }).setLngLat([e.lon, e.lat])
        .setPopup(new Popup({ offset: [0, -34], closeButton: true, focusAfterOpen: false, maxWidth: '280px' }).setDOMContent(box)).addTo(map);
      map.flyTo({ center: [e.lon, e.lat], zoom: Math.min(zoomFor(e.typ), map.getMaxZoom()), essential: true });
      map.once('moveend', () => { if (searchMarker) searchMarker.togglePopup(); });
    },
  });
}
