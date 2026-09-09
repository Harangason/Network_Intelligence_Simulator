# Namen und physische Busanzeige

Die sechs Browserkommentare sind auf der laufenden Anwendung umgesetzt. Release: **696c7195bbe5**.

| Vorher | Jetzt |
|---|---|
| Allradsteuerung_Steuerung | Allradsteuerung |
| RearLeftBrakeTemperature_1 | RearLeftBrakeTemperature |
| CAN_FD in der Technologiespalte | CAN-FD |
| FrontRightBrakeTemperatureSensorErfassungData | Front Right Brake Temperature |
| LIN Kanal 4 · Antriebsstrang_01-IO-abgasnachbehandlung-lin-S02 | Antrieb_06 |
| FrontRightBrakeTemperature_1 als vermeintlicher physischer Bus | Fahrwerk_11, aufgelöst aus der tatsächlichen Netzbindung |

CAN-FD bezeichnet die bereits im Modell hinterlegte Technologie. Der physische Bus hat einen eigenen Namen. Die Protokollzuordnung wurde nicht verändert.

Die Namenskorrektur ist im kanonischen Modell gespeichert: 54 Funktionen, 260 Kommunikationsschnittstellen und 309 Nachrichten wurden umbenannt. 339 physische Anschlussobjekte tragen den Namen ihres zugeordneten Busses; 159 vorhandene Netzdefinitionen erhalten kurze, eindeutige Namen. Die technischen Netz-IDs bleiben bestehen. Der Wizard erzeugt die kurzen Namen künftig direkt; zusätzliche tatsächlich benötigte Kanäle und Nachrichtenteile bleiben unterscheidbar.

Die Nachrichtentabelle löst den Bus über den physischen Anschluss und dessen Netzwerkreferenz auf. Explizite zusätzliche Sendebindungen werden ebenfalls berücksichtigt. Fehlende physische Bindungen werden als „Nicht zugeordnet“ angezeigt.

Vor der Migration wurden Projekt und bisheriger Containerquellstand gesichert. Ein Abgleich bestätigt unveränderte technische IDs, Endpunkte, Portbindungen, Protokolle, Payloads und Timingwerte. Alle 260 Hardwareknoten und 520 Signalobjekte sind vollständig unverändert. Es gibt weiterhin 317 Routen; wiederholte Namensmigration erzeugt keine Änderungen. Die zuvor offenen 47 Kommunikationsanforderungen bleiben fachlich offen.

Geprüft: 211 Frontendtests, TypeScript und Produktionsbuild, 12 gezielte Namens-/Porttests sowie der vollständige Live-Wizard bis Simulation und Auswertung. Der Referenzlauf umfasst alle sechs Nachrichten und 17 Signale, Ergebnis PASS. Alle sechs Browserbeispiele wurden auf Port 13500 geprüft, ohne JavaScript-Seitenfehler.

- [Browsernachweis](verification/2026-09-09-names-browser.json)
- [Technischer Vorher-/Nachher-Abgleich](verification/2026-09-09-names-integrity.json)
- [Vollständige Namensmigration](verification/2026-09-09-names-live.json)
- [Live-Wizard](verification/2026-09-09-names-wizard.json)

Sicherungen: `verification/2026-09-09-before-naming.nis-project.json` und `verification/2026-09-09-before-naming-source.tgz`.
