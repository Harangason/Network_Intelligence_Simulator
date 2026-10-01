# Wizard-Korrektur: isolierte Prüfung vom 29.09.2026

## Umfang und Teststand

- Kanonisches Repository: `I:\PycharmProjects\My_first_Network_Simulator`.
- Isolierter Stack: `work/nis-wizard-correction-isolated/f19e524288a5/receipt.json`, Status `PREPARED`, Build `df80c791c23a`, Quellhash `df80c791c23abd547dfaea849b2b6232b66f6f6ef56f18696db03ccf6d220703`. Produktprojekt und Produktdatenbank wurden nicht als Testziel verwendet.
- Ein erster Startversuch scheiterte an `all predefined address pools have been fully subnetted`. Das leere, als Wegwerf-Testnetz markierte `nis-e2e-network-4f1165907713` wurde nach Prüfung auf fehlende Container entfernt. Danach startete der isolierte Stack.
- Höchstens sechs Wizard-Beispiele ausgeführt: genau sechs. Playwright-JSON-Berichte liegen unter `work/nis-wizard-correction-isolated/f19e524288a5/`.

## Änderungen

1. Eine ausdrücklich genannte einzelne ECU wird als konkreter generischer Controller erkannt. Es wird kein Raspberry Pi dafür eingesetzt.
2. Bestätigte Messgrößen, Anschlüsse und Aktorbefehle bleiben bei einer Textkorrektur intern erhalten; ihre JSON-Metadaten erscheinen nicht mehr im Feld „Projektbeschreibung“.
3. Der Automotive-Parameterkatalog bietet auch die registrierten lokalen Technologien I2C, SPI, UART, GPIO, PWM, ADC und DAC an. Die Profile behalten ihren tatsächlichen Implementierungs- und Nachweisstatus.
4. Fehlende Parameterdaten oder eine nicht mehr passende gespeicherte Branche/Technologie erscheinen als konkrete Fehlermeldung mit Auswahlmöglichkeit anstelle eines unbegrenzten „Katalog wird geladen“.

## Sechs Browserbeispiele

| Nr. | Beispiel | Ergebnis | Beleg |
| --- | --- | --- | --- |
| 1 | Gemeldeter Satz „ein sensor temperatur mess , eine ECU, ein Aktor Ventil schließen“; ECU/I2C gewählt, Beschreibung korrigiert, zu Schritt 4 zurück | **FEHLER**: Der ECU-Anschluss verschwindet nach der Textkorrektur. Ursprünglich wird die ECU korrekt als 1 konkreter Controller angezeigt. | `browser-inventory.json`; `browser-inventory/equipment-inventory-generi-a2645--to-the-project-description/{error-context.md,trace.zip,test-failed-1.png,video.webm}` |
| 2 | Drei generische Sensoren: Messgrößen und einzelne Anschlüsse wählen | **BESTANDEN** | `browser-inventory.json` |
| 3 | Vier Temperatursensoren, zwei Ventilaktoren, Raspberry Pi: Geräte, Anschlüsse und zwei verschiedene Stellbefehle prüfen | **BESTANDEN** | `browser-inventory.json` |
| 4 | Pauschale Sensorzahl zu konkreten Temperatursensoren berichtigen | **BESTANDEN** | `browser-inventory.json` |
| 5 | Gemischtes LIN/CAN-FD-Projekt: ungültige 2-Mbit/s-LIN-Rate zurückweisen und bestätigte Parameter erhalten | **BESTANDEN** | `browser-technology.json` |
| 6 | Kleiner Automotive-CAN-FD-Auftrag durch alle neun echten Workflow-Schritte, inklusive Review, Reload, App-Neustart, Simulation und Abschluss | **BESTANDEN**; Projekt `nis-e2e-small-b20ceb26-7e06-4b1b-80a1-ccd0401540b1`, Lauf `0a85f46a-447e-49da-9475-0c3c14133774`, drei Reviews, neun Schritte, Assessment `COMPLETE`, ein Simulationsjob | `browser-small.json`, Attachment `evidence` |

Zusätzliche gezielte Prüfungen: Frontend-Typprüfung bestanden; 80 Frontend-Spezifikationstests bestanden; 33 isolierte Backend-Technologieprofiltests bestanden. Der isolierte HTTP-Katalog enthält alle acht geprüften Automotive-IDs `ethernet`, `i2c`, `spi`, `uart`, `gpio`, `pwm`, `adc`, `dac` (26 Technologien insgesamt). `git diff --check` fand keine Formatfehler.

## Neuer Stopper aus Beispiel 1

Nach der Korrektur zu „ein sensor temperatur misst, eine ECU steuert ein Ventil“ wird im Wizard ein Controller mit dem Namen `steuert` statt `ECU` angezeigt. Die UI zeigt `steuert: Anschluss`; der Test findet deshalb `ECU: Anschluss` nicht mehr. Die Ursache liegt im Role-first-Parser `declaredHardwareNames`: Das Verb nach „eine ECU“ wird wie ein expliziter Gerätename behandelt. Die strukturierte Anschlusswahl bleibt an der ursprünglichen Identität `ECU` gespeichert und kann dem umbenannten Controller nicht zugeordnet werden. Das ist ein echter Identitäts- und Korrekturfehler, kein fehlender Testbeleg. Trace, Video, Screenshot und DOM-Kontext sind vorhanden.

## Offene Grenzen

- Beispiel 1 muss nach einer Parserkorrektur erneut auf dem dann neu gebauten isolierten Image bestehen. Nach der vereinbarten Grenze wurden keine weiteren Fallbeispiele gestartet.
- Die Auswahl von I2C als Netzwerktechnologie bestätigt noch nicht automatisch den physischen Anschluss jedes einzelnen Geräts. Im Wizard existieren Vorschläge und eine bewusste Sammelübernahme; die vom Nutzer bemängelte direkte Anzeige/Übernahme je Gerät ist damit noch nicht vollständig gelöst.
- Die neue Katalog-Fehleransicht wurde statisch geprüft, aber in diesen sechs Browserfällen nicht durch einen absichtlich inkonsistenten gespeicherten Wert ausgelöst. Der ursprüngliche Validierungsstopp zu fehlender I2C-Bitrate bleibt ein fachlich notwendiger Nachweisblocker und wurde hier nicht als erfolgreicher Durchlauf ausgegeben.
- Die vollständige Release-Gate-Prüfung wurde wegen des fehlgeschlagenen Browserfalls nicht als PASS ausgeführt. Es gibt keine Produktionsübernahme; die produktive Instanz enthält diese Änderungen noch nicht.

**Status:** Reparatur teilweise umgesetzt, sechs Beispiele aufgezeichnet, neuer Stopper dokumentiert. Gemäß Auftrag wird hier auf Rückmeldung gewartet.
