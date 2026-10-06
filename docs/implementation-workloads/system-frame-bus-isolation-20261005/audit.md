# Prüfung der Systemrahmen und Buszuordnung

Projekt: network-project-20261005103106027-d3a78a2c.

## Ergebnis der lesenden Produktprüfung

Die gespeicherte Topologie enthält 251 Geräte und 264 physische Verbindungssegmente.
Die Zahl der Verbindungssegmente ist nicht die Zahl der gemeinsamen Busnetze.
Alle 200 Sensoren/Aktoren besitzen eine explizite System-Owner-Zuordnung.
Die lokalen Netze mischen keine Unterteilnehmer unterschiedlicher System-Owner.

| Technologie | Netze | Lokale Netze | Controller-Backbones | Maximale Teilnehmer je Netz | Unterteilnehmer |
|---|---:|---:|---:|---:|---:|
| LIN | 52 | 52 | 0 | 6 | 121 |
| CAN-FD | 35 | 29 | 6 | 16 | 74 |
| Ethernet | 7 | 3 | 4 | 6 | 5 |

Unterteilnehmer gehören zum funktionalen Systemrahmen; sie sind weiterhin reale physische Teilnehmer ihres lokalen Netzes und zählen dort zur Grenze. Das Controller-Backbone zählt die daran angeschlossenen Controller/Gateways, nicht sämtliche Unterteilnehmer der lokalen Busse. Controller mit mehreren echten physischen Anschlüssen zählen auf jedem ihrer Netze einmal.

Im gespeicherten Auftrag und in den Projekteinstellungen sind aktuell LIN/CAN/CAN-FD/CAN-XL/FlexRay-Grenzen von 64 sowie Ethernet 256 eingestellt. Eine LIN-Grenze von sechs war das Beispiel des Nutzers, keine beauftragte Parameteränderung. Ein hartes Limit von sechs würde bei lokaler I/O-Generierung einen Controller plus höchstens fünf Endgeräte pro Segment erlauben. Neue Controllerkanäle sind Planungsbedarf, keine nachgewiesene Hardware.

## Projektübergreifende Gegenprüfung

Der gemeinsame Wizard-Generator ordnet bestätigte Systemcluster vor den Teilnehmergrenzen zu. Die Zuordnung ist kein Sonderfall dieses Projekts. Eine Gegenprüfung mit 20 Systemrahmen und insgesamt 200 Endgeräten je Fall bestand für 125 registrierte Technologieprofile in vier Industrie-Kontexten (500 Fälle). Jeder lokale Netzidentifier gehörte genau einem Owner. Die sechs konfigurierbaren physischen Bustypen einschließlich registrierter Aliasabbildungen bestanden zusätzlich die Grenze von sechs inklusive Controller (32 Fälle).

Diese Gegenprüfung prüft die Systemidentität/Zuordnungshelfer und konfigurierbare Grenzen. Sie ist kein E2E-Nachweis aller Technologiepfade, kein PHY-/Schedule-/Kapazitätsnachweis und keine industrielle Hardwarefreigabe. Andere Technologien behalten ihre native Modellierung; für sie wird hier keine universelle Teilnehmergrenze von sechs behauptet.

107 vorhandene Regressionstests zu Netzwerkdarstellung, räumlicher Architektur, Systemzuordnung, Generation-Regeln und automatischer Ressourcenplanung bestanden über scripts/run-isolated-tests.py in einer temporären SQL-Datenbank. Eine bestehende Pydantic-Namenswarnung bleibt unverändert. Die Kapazitätsplanung arbeitet je bereits bestehendem Netzidentifier und führt getrennte Netze nicht zusammen. Ein bereits gemischter expliziter Bus ist damit kein Beleg lokaler Systemtrennung und müsste als eigener Modellfall bewertet werden.

## Produktivstatus

Keine Anwendungs- oder Projektparameter geändert; der vorliegende Befund erforderte keine Reparatur. Kein neues Release nötig. NetworkIS läuft gesund mit dem zuletzt vollständig geprüften und ausgelieferten Image sha256:1ac99a2cc7e07158bba2f8d459ec21188840faf877927798480bfc7a55b6ca17. Die ursprüngliche Wizard-Sitzung wurde nicht verändert.

Evidence: system-frame-audit.json, generation-grouping-countercheck.json, regressions.xml, regressions.log und lesende API-Snapshots in diesem Verzeichnis.
