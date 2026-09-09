# Backbone und Netzwerk-Editor: Ursachen, Reparatur und Nachweis

Projekt: `network-project-20260909082213746-780a13ef`. Bereitgestellter Build: `6fb4050747db`.

## Ursache

Die Port-Migration hatte vorhandene, bereits an einen Backbone gebundene Hardwarekanäle für lokale I/O-Netze wiederverwendet. In der kanonischen Änderungshistorie ist beispielsweise der Motoranschluss ursprünglich an `Antriebsstrang_01` gebunden; die Migration änderte diese Bindung auf den lokalen Motor-Sensorbus. Die primäre Statusnachricht behielt die Referenz auf diesen umgebundenen Kanal.

Zwölf ECUs besaßen danach keinen übergeordneten Anschluss. Bei Getriebe- und Elektromotorsteuerung war ein separater Backbone bereits vorhanden, die primäre Nachrichtenbindung jedoch ebenfalls falsch. Insgesamt waren 14 Statusnachrichten betroffen.

Zusätzlich erzeugte der Netzwerk-Editor seine Verkabelung vorwiegend aus freigegebenen Nachrichtenrouten. Fehlende oder ungültige Routen konnten deshalb physische Anschlüsse verschwinden lassen. Ein Fallback verband Geräte sogar nach Namensähnlichkeit. Der Routengenerator wiederum konnte den ersten Anschluss mit passender Technologie wählen, obwohl dieser auf einem unabhängigen Sensorbus lag.

## Umgesetzt

- Bestehende Busbindungen werden bei der Port-Materialisierung nicht mehr für andere Netze wiederverwendet. Zusätzliche Netze erhalten eigene Kanäle.
- 14 primäre Nachrichtenbindungen korrigiert, zwölf fehlende ECU-Backbones und fünf zugehörige Gateway-Kanäle ergänzt. 356 physische Hardwarekanäle insgesamt. Lokale Sensor- und Aktoranschlüsse bleiben erhalten.
- Historische Backbone-Netze aus Version 1 verwendet; vorhandene eindeutige Backbone-Segmente weiterverwendet. Motorsteuerung gemäß Nutzeranforderung an `Antrieb_36` angeschlossen.
- `Abgasnachbehandlung → Motorsteuerung` angelegt und freigegeben: CAN-FD, gemeinsamer Bus `Antrieb_36`, 10-ms-Statusnachricht, kein Gateway-Übergang erforderlich. Empfängeranforderung dauerhaft in der Nachricht gespeichert; bestehende Anzeigeempfänger erhalten.
- Bestehende physische Leitungen bleiben bei der Neuerzeugung erhalten, auch wenn ihre Nachrichtenrouten ungültig werden. Explizite gemeinsame Busbindungen werden unabhängig von Nachrichtenrouten dargestellt. Keine Ersatzverkabelung anhand ähnlicher Gerätenamen.
- Deklarierte Nachrichtenanschlüsse bleiben sichtbar, auch ohne bestätigten Empfänger. 30 zuvor fehlende Anschlussreferenzen vervollständigt.
- Routing berücksichtigt kanonische Busmitgliedschaften. Fehlende physische Pfade, fehlende Empfängeranschlüsse und unabhängige Busse ohne expliziten Gateway-Pfad sind Fehler.
- Explizite Nachrichtenempfänger werden bei der graphbasierten Wizard-Routenerzeugung berücksichtigt.
- Die Startanzeige des Editors beschreibt vorhandene Modellreferenzen statt pauschal „Noch nicht synchronisiert“ zu behaupten.

## Verifikation

- 58 Tests für physische Kanäle, Routing und Wizard bestanden, einschließlich des großen MCP/Wizard-Integrationstests mit ausdrücklich definierten Testbussen und Befehlssignalen.
- TypeScript-Prüfung und Produktionsbuild erfolgreich.
- Alle 318 aktiven Routen erneut geprüft. Keine fehlenden Backbone-Anschlüsse bei ECUs mehr; keine Befunde der physischen Portkonsistenzprüfung.
- 228 vorhandene Leitungen vollständig erhalten; 27 weitere Verbindungen aus bereits deklarierten gemeinsamen Busmitgliedschaften dargestellt, insgesamt 255.
- Wiederholter Neuaufbau: weiterhin 255 Leitungen, keine Busbindungsänderungen und keine weiteren Anschlusskorrekturen.
- Browserprüfung: neue Motor-Empfängerroute sichtbar, Motor-Port `Antrieb_36` sichtbar und verbunden, keine JavaScript-Fehler.

Evidenz im Unterordner `verification`: `2026-09-09-before-backbone-repair.json` (Sicherung), `2026-09-09-backbone-repair.json`, `2026-09-09-exhaust-engine-route.json`, `2026-09-09-backbone-verification.json`, `2026-09-09-backbone-repeat.json`, `2026-09-09-backbone-live-check.json`, `2026-09-09-backbone-tests.txt`, `2026-09-09-backbone-browser.json` und die zugehörigen Browserbilder.

## Fachlich verbleibend

Die vollständige Validierung erkennt 100 Befehlsrouten ohne definierte Befehlssignale (`COMMAND_SIGNALS_MISSING`). Diese stehen auf CONFLICT, 218 Routen sind APPROVED. Das sind fehlende Befehlsspezifikationen, keine verlorenen Busanschlüsse. Die Verkabelung dieser Routen bleibt erhalten. Konkrete Schaltbefehle, Stellwerte und deren Kodierung wurden nicht erfunden.

Bestehende offene Empfängeranforderungen und Timingkonflikte außerhalb dieser Reparatur bleiben offen. Alte Capacity-, Simulations- und Analyseergebnisse werden durch die Modelländerungen veraltet; die Netzwerkreparatur ist kein Nachweis für eine vollständig spezifizierte Gesamtfahrzeugfunktion.
