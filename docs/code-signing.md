# Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

Landblick - RLP signiert den Windows-Installer über SignPath. Das Zertifikat gehört der SignPath Foundation; als Herausgeber zeigt Windows deshalb „SignPath Foundation“, nicht den Namen des Projekts oder einer Person.

## Was signiert wird

Nur der Windows-Installer `Landblick - RLP_<Version>_x64-setup.exe`. Er entsteht ausschließlich im GitHub-Workflow [`windows-installer.yml`](../.github/workflows/windows-installer.yml) auf GitHub-gehosteten Runnern aus dem Quelltext dieses Repositorys. Von Hand gebaute Dateien werden nie signiert. Die Artefakt-Konfiguration liegt in [`.signpath/artifact-configuration.xml`](../.signpath/artifact-configuration.xml).

Mitgelieferte Programme Dritter werden nicht mit diesem Zertifikat signiert, insbesondere `pmtiles` ([go-pmtiles](https://github.com/protomaps/go-pmtiles), BSD-3-Clause).

## Rollen

| Rolle | Wer |
|---|---|
| Autoren (Committer) | [Thorsten Schleicher](https://github.com/thorin-eifel), siehe [Mitwirkende](https://github.com/thorin-eifel/Landblick-RLP/graphs/contributors) |
| Reviewer | [Thorsten Schleicher](https://github.com/thorin-eifel) |
| Approver (gibt jede Signatur frei) | [Thorsten Schleicher](https://github.com/thorin-eifel) |

Änderungen von Personen ohne Schreibrecht kommen nur über Pull Requests mit Review ins Repository. Für GitHub und SignPath ist bei allen Beteiligten die Zwei-Faktor-Anmeldung eingeschaltet. Jede Signatur wird in SignPath einzeln freigegeben.

## Datenschutz

Landblick überträgt keine Daten über die Person, die es benutzt. Das Programm ruft öffentliche Datenquellen ab (Warnungen, Wetter, Pegel, Verkehr, Luft, Strahlung und weitere); welche das sind, steht mit Betreiber, Lizenz und Abrufintervall in [`sources.yaml`](../sources.yaml) und in der App auf der Seite „Quellen und Lizenzen“. Diese Abrufe enthalten keine Nutzerdaten, nur einen User-Agent mit der Kontaktadresse, die bei der Einrichtung angegeben wird. Kartendienste weiterer Stellen (Menüs „LGB Daten“ und „Landesdaten“) werden erst nach einem Hinweis und auf ausdrücklichen Wunsch abgerufen. Es gibt kein Tracking, keine Telemetrie und keine Konten.

Die Datenschutzerklärung steht in [`web/datenschutz.html`](../web/datenschutz.html) und in der App unter „Datenschutz“.
