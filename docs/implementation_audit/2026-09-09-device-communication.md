# Mindestkommunikation und Konfliktbehebung

## Regeln

Die vorhandene Klassendefinition bleibt maßgeblich: Status ab Klasse 2, Funktionen ab Klasse 3. Neue Projekte nutzen für den Betriebsstatus OFF=0, INIT=1, READY=2, ACTIVE=3, DEGRADED=4, ERROR=5. Der Generator hatte bisher beim Deduplizieren ein älteres Statussignal vor der gemeinsamen Vorlage bevorzugt; diese Reihenfolge ist korrigiert. Klasse-2-Geräte erhalten auch bei Generierung über den Backend-Agenten einen Status, wenn der Messwert ihn nicht bereits ergänzt.

Sensoren benötigen mindestens ein ausgehendes Signal. Aktoren benötigen eine ausgehende Rückmeldung. Die generischen Simulatorrollen Schaltausgang und Stellglied erhalten einen Sollwert sowie eine separate Ausführungsmeldung mit IDLE, ACCEPTED, EXECUTING, COMPLETED und FAILED. Annahme und Abschluss sind damit verschiedene Codes. Diese Vorlagen sind als `requires_hardware_adaptation` gekennzeichnet: Sie sind keine herstellerspezifischen oder realen Airbag-Befehlsdefinitionen und implementieren keine physische Aktordynamik.

Für unbekannte Aktoren werden keine Befehle erfunden. Bestätigte Definitionen können unter `Aktor-Befehle` in die Wizard-Spezifikation aufgenommen werden. Fehlende Definitionen werden bereits bei der Modellfreigabe ausgewiesen. Der Agent hat zusätzlich `validate_device_communication` zur Prüfung bestehender Projekte. Die Proposal-Prüfung verwendet dieselben Mindestregeln.

## Bestehendes Projekt

Projekt `network-project-20260909082213746-780a13ef`:

- 98 fehlende Sollwertsignale und 100 Ausführungsrückmeldungen ergänzt.
- 53 bisher unveränderte, automatisch generierte Legacy-Statusdefinitionen vereinheitlicht.
- Vorhandene Befehlssignale sowie bearbeitete Statusdefinitionen erhalten.
- Keine Bitbelegungsfehler in den ergänzten Nachrichten.
- Alle 318 Routen technisch valide: 218 bisherige Freigaben erhalten, 100 ehemalige Konflikte zur erneuten Freigabe bereit.
- Wiederholung des Migrationsplans: null weitere Änderungen und keine Mindestkommunikationsbefunde.

Nachgelagerte Berechnungen werden durch die Modelländerungen als veraltet markiert und müssen mit dem neuen Modellstand erneut durchgeführt werden.

## Bedienung und Prüfung

Konfliktmeldungen bieten direkte Links zur betroffenen Nachricht sowie bei fehlenden Befehlssignalen zum Signal-Wizard mit vorausgewählter Nachricht. Ein Browsertest mit simuliertem Konflikt prüft den vollständigen Navigationsweg ohne Modelländerung.

Nachweise: 12 Wizard-/MCP-Tests einschließlich isolierter Modellerstellung und Routing; 39 Routing-/Mindestkommunikationstests; 40 Frontend-Spezifikationstests; TypeScript und Produktionsbuild. Skripte `repair-device-communication.py`, `verify-device-communication.py` und `verify-conflict-wizard.mjs` dokumentieren Migration, Prüfung und Browserablauf. Detailnachweise befinden sich in `verification/2026-09-09-device-communication-*`.
