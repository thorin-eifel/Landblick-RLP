// Grenzen des sichtbaren Kartenbereichs für das Detailfenster (Logik: ausschnitt.js). Ohne Karte null: dann bleibt alles sichtbar.
import { grenzenVon } from './ausschnitt.js';
import { map, mapReady } from './zustand.js';

export const ausschnitt = () => (mapReady && map ? grenzenVon(map.getBounds()) : null);
