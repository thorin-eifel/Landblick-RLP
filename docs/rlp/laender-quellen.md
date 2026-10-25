# Meldungen und Warndaten der Nachbarländer (NRW, Hessen, Baden-Württemberg, Bayern, Saarland)

Stand 12.10.2026. Vergleichsmaßstab ist der Mobilitätsatlas RLP (LBM): Baustellen, Sperrungen, Verkehrsmeldungen, dazu Pegel und Hochwasserwarnungen.

## Schon bundesweit abgedeckt
NINA (alle Länder, MoWaS/Katwarn/Polizei), DWD-Warnungen, Autobahn-API (alle Autobahnen), Presseportal. Offen waren Baustellen und Meldungen auf Bundes-, Landes- und Kreisstraßen sowie Pegel der Länder.

## Eingebaut (PR „Länder-Quellen“)
| Quelle | Collector | Lizenz | Inhalt |
|---|---|---|---|
| LHP-PublicAPI (hochwasserzentralen.de) | `lhp_hochwasser` | CC BY 4.0, Stand und Quelle sichtbar | Hochwasserklasse an rund 240 Pegeln im Gebiet (NW, HE, BW, BY, SL) und Warnflächen. Keine Wasserstände. |
| MobiData BW, Baustelleninformationen | `mobidata_bw_baustellen` | dl-de/by-2.0 | Bundes-, Landes-, Kreisstraßen, Verlauf als Linie, Sperrung/Baustelle |
| MobiData BW, Verkehrsmeldungen (LMS BW) | `mobidata_bw_meldungen` | dl-de/by-2.0 | Unfälle, Störungen, Hindernisse, Sperrungen; ohne Baustellen und Autobahnen (Dubletten) |

Stolpersteine: Die LHP-API liefert je nach `Accept` eine andere Struktur (`application/geo+json` für `features`). Die Struktur der Warnungen ist nach dem dokumentierten Beispiel gebaut, zum Bauzeitpunkt war keine Warnung aktiv. Pegel an Rhein, Main, Neckar, Mosel können doppelt vorkommen (PEGELONLINE und LHP, verschiedene Kennungen).

## Noch offen
| Land | Befund | Nächster Schritt |
|---|---|---|
| Bayern | Bayerninfo bietet Verkehrs- und Baustellenmeldungen (DATEX II, alle 3 Minuten) über die Mobilithek (Angebote 110000000002506000 und 110000000002507001). Lizenz auf der Bayerninfo-Seite nicht genannt. | Mobilithek-Konto durch den Betreiber, Angebotsseite lesen (Lizenz, Abruf ohne Zertifikat?) |
| Hessen | Hessen Mobil liefert Baustellen laut eigener Broschüre im Datex-Format an die Mobilithek; Verkehrsservice Hessen nutzt eine interne, nicht dokumentierte Schnittstelle (nicht anfassen). | Mobilithek: gibt es ein freies Hessen-Angebot? |
| NRW | Auf open.NRW steht ein Datensatz der VIZ.NRW (Landesverkehrszentrale), Zugang und Lizenz ließen sich aus der Sandbox nicht prüfen. Das Portal verkehr.nrw bietet Meldungen und Baustellen. | Datensatzseite lesen, Mobilithek-Angebot prüfen |
| alle | Wasserstände der Länderpegel (LANUV, HLNUG, LUBW, HND) | einzeln anfragen, LHP liefert nur Klassen |

Zugangsdaten für die Mobilithek gehören in die `.env`, nie in den Chat oder ins Repository.
