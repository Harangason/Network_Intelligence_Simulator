# Netzwerkansicht Version 4 – Umsetzung und Prüfung

Stand: 10. September 2026. Projekt: `network-project-20260910042736034-d11591d0`.

Spätere Nutzerentscheidung vom selben Tag: Verbindungslinien im Netzwerkeditor
tragen keine Pfeilspitzen mehr. Die nachfolgende Beschreibung bidirektionaler
Pfeile dokumentiert den vorherigen Stand.

Die Ansicht verwendet jetzt einen gemeinsamen Strang je physischem Bus mit echten Anschlusszweigen. Das Gateway steht über den Domänen; die Rahmen einer ECU enthalten ihre zugeordneten Sensoren und Aktoren. Domänen und Systemrahmen sind unterschiedliche Gruppierungen. Busidentität, Anschlüsse und Protokoll stammen aus dem kanonischen Modell. Linienfarben kennzeichnen das Protokoll; Gerätefarben suggerieren keinen LIN-Anschluss mehr. Die Zweige tragen Pfeile in beide Richtungen. Die Sender-/Empfängerfestlegung der logischen Routen bleibt davon unabhängig.

Die Darstellung wird beim Erzeugen beziehungsweise Übernehmen der Topologie im Wizard serverseitig berechnet und zusammen mit der Topologie in PostgreSQL gespeichert. Die gespeicherte Szene enthält Positionen, Rahmen, Stränge, Zweige und eine Signatur des zugrunde liegenden Modells. Der Editor lädt sie über einen kleinen eigenen Endpunkt. Er zeigt während des Ladens einen Ladezustand und führt anschließend keine konkurrierende automatische Anordnung aus. Manuelles Verschieben wird atomar mit einer Versionsprüfung gespeichert; Fehler bleiben sichtbar und können erneut gespeichert werden.

Im Bestandsprojekt wurden 261 Geräte, 95 physische Busse und 51 Systemrahmen geprüft. Der Vergleich mit der Sicherung bestätigt identische Modellsemantik und unveränderte Workflow-Versionen. Bestehende getrennte Busse werden durch eine Änderung ihrer Anzeige nicht zusammengelegt. Die neuen Teilnehmergrenzen gelten für neue Planungen; ihre Änderung allein verdrahtet ein Bestandsprojekt nicht um.

**Teilnehmergrenzen unter Einstellungen**

| Bustyp | Vorgabe |
|---|---:|
| CAN | 64 |
| CAN-FD | 64 |
| CAN-XL | 64 |
| LIN | 64 |
| Ethernet | 256 |
| FlexRay | 64 |

Die Werte sind Planungsparameter und keine Behauptung über allgemeine Protokollgrenzen. Positive Werte zählen alle Teilnehmer einschließlich Gateway beziehungsweise Controller; 0 hebt diese Planungsobergrenze auf. Im Browser wurde LIN auf 128 gesetzt, gespeichert und nach erneutem Laden mit 128 bestätigt. Die feste Aufteilung nach sechs Controllern und die bisherigen versteckten Grenzen für lokale Geräte wurden ersetzt. Die Werte werden im Wizard-Auftrag festgehalten, sodass ein laufender Auftrag konsistent fortgesetzt wird. Die Aufzählung der verfügbaren Einstellungen beeinflusst nicht die Auswahl des tatsächlichen Protokolls.

Eine Teilnehmergrenze ist eine Obergrenze, kein Auffüllziel: Last, Latenz und Jitter können kleinere Segmente erforderlich machen. Der große Test zeigte, dass allein die mittlere LIN-Buslast nicht ausreicht. Die Planung prüft deshalb zusätzlich den konservativen Zeitbedarf gleichzeitig fälliger LIN-Nachrichten und teilt bei Bedarf physische Busse auf. Die geforderten Zeiten werden dabei nicht gelockert. Ein Test mit 100 langsam abgefragten LIN-Teilnehmern bestätigt, dass keine neue starre Grenze von 50 eingeführt wurde.

**Weitere beim Gesamttest korrigierte Ursachen**

- Große Wizard-Spezifikationen einschließlich der Einstellungen werden nicht mehr an der alten Grenze von 30.000 Zeichen abgeschnitten oder abgelehnt; das gemeinsame Auftragslimit beträgt 120.000 Zeichen.
- Ältere Funktions- und Kamera-Assistenten erzeugen für neue Controller ebenfalls den einheitlichen Betriebsstatus OFF, INIT, READY, ACTIVE, DEGRADED, ERROR. Die vorgeschlagenen Kommunikationsparameter bleiben ausdrücklich prüfbare Planungsannahmen.
- Vorhandene Positionen überstehen auch eine Topologie-Aktualisierung ohne gespeicherte Szene. Eine ECU unter einem Gateway behält ihren eigenen Systemrahmen.
- Der lokale HTTP-Proxy erlaubt für große atomare Übernahmen denselben begrenzten Zeitrahmen von 180 Sekunden wie der Agent-Test. Zuvor konnte er nach 30 Sekunden eine erfolgreich gespeicherte Übernahme als Verbindungsfehler melden. Der vorhandene Client liest bei unklarer Antwort den gespeicherten Zustand zurück und wiederholt den Schreibaufruf nicht blind.

**Prüfnachweise**

- 194 Backend-Tests bestanden: Szenen, physische Anschlüsse, Teilnehmergrenzen, industrielle Technologien, Agent-Dialog, Freigabe/Übernahme, Abbruch, Kapazitätsplanung, LIN-Timing und Workflow.
- 217 Frontend-Tests bestanden; Produktionsbuild einschließlich TypeScript-Prüfung erfolgreich.
- Browser: tatsächliches Laden der großen Busansicht, bidirektionale Zweige, unterscheidbare Protokolle, Speichern/Neuladen von LIN=128 sowie Verschieben/Neuladen eines Testknotens geprüft.
- Der neue Endpunkt lieferte die gespeicherten großen Szenen bei lokalen Stichproben in etwa 57–122 ms. Das ist die HTTP-Antwortzeit einschließlich Datenübertragung, keine zugesicherte Ladezeit der gesamten Seite.

Der ausführbare HTTP-Abnahmetest liegt in `scripts/verify-live-wizard.py`. Er läuft über denselben UI-Proxy wie die Anwendung, erzeugt ein isoliertes Projekt, prüft Freigaben und die Simulation und gleicht die aus SQL geladene Zeichnung mit sämtlichen physischen Anschlussreferenzen ab. Eine erfolgreiche Simulation erfordert dabei vollständige Abdeckung und null fehlgeschlagene Routen. Die abschließenden maschinenlesbaren Ergebnisse stehen in `docs/network-v4-large-wizard-acceptance.json`.

**Abschließender Durchlauf auf Build 678cceb0963b**

Projekt `astra-e2e-12fd6fa2789b`, Simulation `ed4d6606056f40fb8c682dd0ebf185e1`: PASS. Alle 386 Routen, 311 Nachrichten und 725 Signale wurden verarbeitet; keine Route scheiterte und keine erwarteten Netzwerke, Routen oder Signale fehlen. Die SQL-Szene enthält 261 Geräte, 82 Busse, 51 Systemrahmen und 343 geprüfte Anschlusszweige. Ihre Modellsignatur wurde ebenfalls bestätigt. Der Abruf der fertigen Szene dauerte im Abnahmelauf 62 ms. Eine größere Kapazitätsübernahme wurde nach 34,1 Sekunden mit HTTP 200 bestätigt. Die anschließende Wiederaufnahme erzeugte keinen zweiten Simulationslauf.

Engineering, Topologie, Kapazität, Simulation und Auswertung sind vollständig; Routing, Parameter und Validierung sind freigegeben. Die Intelligence meldet weiterhin offene Architekturhinweise. Diese Hinweise wurden nicht pauschal als erledigt markiert; ihre Codes und Anzahlen stehen in `docs/network-v4-verification.json`.

Maschinenlesbare Nachweise: [gesamter Wizard-Durchlauf](network-v4-large-wizard-acceptance.json) und [kompakte Prüfzusammenfassung](network-v4-verification.json).
