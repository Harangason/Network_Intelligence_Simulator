# Prüfung: Kameraverarbeitung, autonome Führung und Sequenzanimation

Stand: 12.10.2026. Projekt: `network-project-20261009072206008-4bb505f1`.

Auftrag: die markierte Sequenz und die fachliche Kommunikation untersuchen und den Befund zeigen. Es wurden ausschließlich lokale Quellen und lesende API-Abfragen verwendet. Anwendungscode, Routingtabelle, Projektmodell und Produktion wurden nicht geändert. Kein Simulations-, Test- oder Release-Lauf wurde gestartet.

## Ergebnis

Die fehlende Kommunikation zur Fahrerassistenz ist sowohl im aktuellen Modell als auch im gespeicherten Lauf bestätigt. Die Ursache liegt vor der physischen Pfadsuche: Es fehlen fachliche Datenbedarfe, passende Funktionsausgänge und die zugehörigen Empfängerbeziehungen. Die vorhandene Ethernet-Anbindung allein erzeugt diese Beziehungen nicht.

Die Aussage „Kamera sendet nur an System“ braucht dagegen eine Präzisierung: `System` ist im Modell ein Gateway. Die Kamera-Routen führen über dieses Gateway bis zu HeadUpDisplay, Kombiinstrument und Infotainment. Das Sequenzdiagramm zeigt einzelne Transportabschnitte. Die anschließenden Gateway-Ausgänge sind vorhanden.

## Gespeicherte Belege

Die Erhebung umfasst 251 Hardwareknoten, 372 Hardwareinterfaces, 71 Funktionen, 335 logische Interfaces, 323 Nachrichten, 698 Signale und alle 523 Routing-Einträge. Die gezielten Ergebnisse und Identitäten stehen in [evidence.json](evidence.json).

| Knoten | Ausgehende Routen | Eingehende Routen |
|---|---|---|
| Kameraverarbeitung | 3 Anzeigeempfänger, 2 eigene Aktoren | 2 eigene Aktorrückmeldungen |
| Radarverarbeitung | 3 Anzeigeempfänger, 2 eigene Aktoren | FrontRadarDistance, 2 eigene Aktorrückmeldungen |
| Ultraschallverarbeitung | 3 Anzeigeempfänger, 2 eigene Aktoren | 2 eigene Aktorrückmeldungen |
| Fahrerassistenz | 3 Anzeigeempfänger, 2 eigene Aktoren | IntakeAirTemperature, 2 eigene Aktorrückmeldungen |

Die Nachricht `Kameraverarbeitung` (`dc8404dc-5711-4106-9b68-f64a44d2a208`) hat 3 Byte und enthält Mode, Quality, Status, AliveCounter und Health. Ihre expliziten Empfänger sind HeadUpDisplay, Infotainment und Kombiinstrument. Sie enthält keine Objektliste, Hindernisse, Freiraum- oder andere Wahrnehmungsdaten. Die zusätzlich vorhandene LIN-Befehlsnachricht richtet sich an die eigenen generischen Aktoren.

Im bestätigten Wizard-Graph besitzen die betroffenen Cluster keine `functional_routes`. Kamera hat dort keine Sensorzuordnung. Fahrerassistenz besitzt die Zuordnung `IntakeAirTemperature`. Diese Zuordnung ist fachlich für eine autonome Führung nicht erklärt. Die Automotive-Vorlage enthält zudem einen pauschalen Sensorbesitzer-Fallback auf Fahrerassistenz für nicht passende Namen (`engineering-specification.ts:944`); das ist ein konkreter zu prüfender Generierungsfehler. Die gespeicherte Zuordnung und dieser Codepfad sind belegt, die ursprüngliche Ausführung dieses Fallbacks wurde nicht erneut abgespielt.

## Historischer Lauf und Darstellung

Geprüfter Lauf: `33f124d0ad234c989dcbbd773e6393f9`, Snapshot `9992352a-af18-4a63-a50b-52d7e77ce4df`, erstellt am 09.10.2026. Der Snapshot ist `OUTDATED`, weil freigegebene Hardwarekanäle für die physische Topologie übernommen wurden. Er ist ein historischer Beleg. Die fehlende Kamera-Fahrerassistenz-Route wurde unabhängig davon im aktuellen Modell bestätigt.

Eine gespeicherte Transaktion `route-RT-2CDBCE3B-ea92cf44:0` enthält:

1. Kameraverarbeitung → System, Transportereignis bei 0,112016 ms.
2. System → HeadUpDisplay, Transportereignis bei 0,425376 ms.

Beide Ereignisse haben dieselbe Transaktions-ID und `segmentCount = 2`. Im vollständigen Sequenzmodell gibt es auch Kamera-Transaktionen zu Kombiinstrument und Infotainment. Für Fahrerassistenz fehlen entsprechende Kamera-, Radar- und Ultraschallereignisse.

Die erste Seite der 10.000 sichtbaren Ereignisse enthält bereits beide Abschnitte der Kamera-Anzeigerouten. Die späteren Abschnitte müssen vertikal gesucht werden; Anzeigeempfänger liegen außerdem weit rechts unter den 251 Teilnehmern. Es handelt sich daher nicht um einen abgebrochenen Kamera-Gateway-Transport.

`E2ESequenceDiagram` zeichnet in allen drei Detailstufen dieselben gespeicherten Hop-Endpunkte. „Funktional“ ändert hauptsächlich die Beschriftung, fasst eine Gateway-Transaktion aber noch nicht zu fachlichem Sender und Endempfänger zusammen. Der bestehende Wiedergabecursor filtert freigegebene Ereignisse; ein bewegtes Nachrichtensymbol ist nicht implementiert. Für ein Ende-zu-Ende-Verständnis fehlen eine Transaktionsfokussierung und eine wirkliche funktionale Projektion. Die derzeitigen Ereignisse belegen Transport; eine verarbeitete Anwendungseingabe darf daraus nicht automatisch behauptet werden.

## Vorhandener technischer Weg

Die lesende API `GET /api/engineering/routing/paths` findet den kürzesten Kandidaten:

```text
Kameraverarbeitung
  → ETH_Regelung_01 (Regelung_10-S01)
  → System / Gateway
  → ETH_Fahrerassistenz_01 (Fahrerassistenz_05-S01)
  → Fahrerassistenz
```

Dieser Kandidat ist nicht angewendet. Er zeigt die mögliche Erreichbarkeit im gespeicherten Modell; er beweist noch keine Kapazität, konkrete Payload-Eignung, Empfängerakzeptanz oder funktionale Frist. Eine neue physische Leitung ist für den gefundenen Kandidaten zunächst nicht erforderlich. Bei der späteren konkreten Kommunikation sind die tatsächlichen Ports, Gateway-Weiterleitung und Technologieprofile zu prüfen. Neue logische Kommunikationskanten können im Netzwerk sichtbar werden, ohne automatisch alle Gerätepositionen oder die Verkabelung zu verändern.

## Empfohlene Erweiterung

Die allgemeine Funktionskette soll unabhängig von der Industrie modelliert werden:

```text
Sensoren → Wahrnehmungsverarbeitung → autonome Führung
          → zuständige Regelungsfunktionen → lokale Aktoren
```

Im aktuellen Projekt übernimmt die vorhandene Funktion Fahrerassistenz die Rolle der autonomen Führung. Für andere Branchen wird die Rolle ausdrücklich zugeordnet; die Bezeichnung oder Geräteklasse allein darf sie nicht festlegen.

1. Fachlichen Abhängigkeitsgraph ergänzen: benötigte Ausgänge von Kamera/Radar/Ultraschall, konkrete empfangende Funktion, Steuerungsziele und Rückmeldungen. Kamerasensor-Zuordnung und Ansauglufttemperatur-Zuordnung gesondert klären. Unbekannte Zuordnungen offenlassen.
2. Passende Nachrichten bzw. DataObjects mit expliziten Feldern, Kodierung, Größe, Einheiten, Erzeugungszeit und Übertragungsart modellieren. Bestehende Statusnachrichten ersetzen keine Wahrnehmungsdaten. Werte und Datenmengen nicht erfinden.
3. Bestätigte Ausgänge als `communication_contract.scope = FUNCTION_OUTPUT` mit kanonischen `consumer_refs` und logischen Empfangsinterfaces ablegen. Sensor-Rohdaten und lokale Aktorbefehle behalten ihre Empfängergrenzen.
4. Der vorhandene Routing-Generator kann explizite Nachrichtenempfänger bereits in Routen umsetzen. Den Übergang vom fachlichen Abhängigkeitsgraph über Nachrichtengenerierung und Empfängerwahl bis zur Routing-Generierung vervollständigen. Eine reine zusätzliche Kamera-Statusroute wäre unzureichend.
5. Preflight soll erforderliche Funktionsbeziehungen gegen konkrete Payload, Eingänge und ausführbare Routen prüfen. Vollständige Abdeckung vorhandener Nachrichten sagt nichts über einen zuvor ausgelassenen fachlichen Datenbedarf aus.
6. Buslast, Gateway-Verarbeitung, E2E-Laufzeit, Datenalter und Empfängerreaktion für die neuen Daten bewerten. Generierte Fristen bleiben Annahmen, bis sie fachlich bestätigt sind. Historische Läufe bleiben unverändert; den geänderten Modellstand anschließend separat simulieren.

## Animation

Ein bewegtes Nachrichtensymbol folgt der ausgewählten echten Transaktion vom Sender über alle Gateway-Schritte bis zum Empfänger. Die Transportansicht zeigt die Hops; die funktionale Ansicht zeigt Quelle und tatsächliche empfangende Funktion. Der Nutzer kann Transaktion oder Signal wählen, abspielen, pausieren und schrittweise weiterschalten. Empfang, Ablehnung und unbekannte Annahme werden getrennt dargestellt.

Die Animation verwendet vorhandene Transaktions- und Ereignis-IDs sowie belegte Zeitpunkte. Für sichtbare Bewegung werden kurze Übertragungen als gekennzeichnete Zeitlupe dargestellt; Zeitmessungen bleiben unverändert. Fehlende Zeitpunkte oder Verarbeitungsschritte werden als offen angezeigt. Die bestehenden Wiedergabe- und Fensterkopplungsfunktionen liefern dafür die gemeinsame Zeitbasis. Eine Kamera-Fahrerassistenz-Animation wird erst angeboten, wenn diese Kommunikation tatsächlich im Modell vorhanden ist.

## Zuständige Quellen

- `backend/nis/agent/tools/wizard_generation.py:1285,1482,1498`: bestätigter Cluster-Graph, lokale Besitzbeziehungen, HMI-Routen und explizite Nachrichtenempfänger.
- `backend/nis/engineering/communication/wizard_communication.py:67,74,150`: Kommunikation aus bestätigten HMI-/Funktionsentscheidungen und Empfängergrenzen.
- `frontend/src/features/agent/lib/industry-templates/automotive-functions.ts`: bestehende illustrative Funktionsausgänge, ohne Wahrnehmungs-/Autonomie-Datenkette.
- `frontend/src/features/agent/lib/engineering-specification.ts:944`: pauschaler Sensorbesitzer-Fallback auf Fahrerassistenz.
- `backend/nis/simulation/e2e_assurance.py:186`: korreliertes Sequenzmodell mit Transport-/Empfangsereignissen.
- `frontend/src/features/simulation/ui/model-simulation-runner.tsx:752`: Wiedergabecursor filtert Sequenzereignisse.
- `frontend/src/features/simulation/ui/e2e-sequence-diagram.tsx:171`: Detailstufen verwenden dieselben Hop-Endpunkte.
- Projektverträge: Communication Design, Spatial Architecture, Generation Rule Manager, TechnologyProfile, Physical Realization, Validation/Preflight, E2E Timing und gemeinsames E2E Sequence Target.
