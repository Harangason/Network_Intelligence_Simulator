# Umsetzung Transport, Timing und Golden Trace

Die im Audit nachgewiesenen Transport- und Bewertungsfehler sind im Workspace korrigiert. Dieser Nachweis betrifft den lokalen Code und eine Offline-Wiederholung des gespeicherten Originalprojekts. Deployment und die Reparatur der fehlenden Modellrouten werden gesondert geprüft.

- Der Konfigurationsadapter übernimmt maximale Latenz, Jitter, Timeout und Freshness samt kanonischer Routing-ID. Anforderungen aus Nachricht, Signal und Route werden bei der Snapshot-Erstellung berücksichtigt. Die API für freigegebene Konfigurationen erhält Topologie und Netzwerkparameter.
- `physical_route_segments` verfolgt die freigegebenen Topologiekanten. Gateway-Strecken nutzen jeweils ihre tatsächlichen Endpunkte, Hardwareports, Technologie und Bitrate. Das zweite Segment wird erst nach Empfang des ersten freigegeben. Ein Ausfall des Eingangs erzeugt keine erfundene Übertragung auf dem Ausgang.
- Die Kapazitätsberechnung verwendet dieselben Segmente. Sie summiert die Übertragungszeiten des Weges und berechnet Ethernet-Last über die tatsächlich beanspruchten TX-/RX-Ports. Ein nicht bestätigter physischer Pfad wird als Fehler ausgewiesen.
- Die Laufzeitanalyse bewertet End-to-End-Empfang einschließlich erster, letzter und vollständig fehlender Zustellung. Paketverlust und verletzte Anforderungen ergeben FAIL. Fehlende Anforderungen oder unzureichende Beobachtung ergeben NOT_EVALUATED.
- Golden wird als eigener fehlerfreier Lauf mit demselben Seed und Startzeitpunkt erzeugt. Payload, Signalwerte, Zeitstempel und Metadaten stammen aus diesem Lauf. Ein optionales explizites Exportlimit wird ausgewiesen; standardmäßig ist der Golden Trace vollständig.
- Ethernet-Sessions werden auch am ausgehenden Gateway-Segment erzeugt. Datenbestätigungen werden nach dem tatsächlichen Empfang eingeplant. CSV unterstützt dabei gemischte Bus-, Session- und IP-Ereignisse.
- Der Simulator berücksichtigt die konfigurierte Jitteramplitude in Millisekunden. Ein explizites routenspezifisches Jitterverhältnis bleibt möglich.
- Beim manuellen Speichern im Netzwerkeditor werden physische Hardwarekanäle und Netzwerke innerhalb derselben Anfrage angelegt beziehungsweise zugeordnet. Logische Interface-Referenzen bleiben getrennt erhalten. Reserveports ohne Kante werden nicht entfernt. Der Folgeschritt erzeugt Routen mit kanonischen Hardwareport-IDs.
- Neu erzeugte Routing-Vorschläge erhalten ohne explizite Anforderung Timeout und Freshness von mindestens drei Nachrichtenzyklen beziehungsweise 500 ms. Die Herkunft ist im Vorschlag dokumentiert. Bestehende Anforderungen bleiben unverändert; ein Timeout-/Freshness-Budget unter Zyklus plus zulässigem Jitter erzeugt einen konkreten Routing-/Preflight-Befund.

## Prüfungen

**Finaler eingefrorener Stand nach den zusätzlichen Scope-Korrekturen: 802 Backendtests bestanden, keine Fehler, 137,36 s.** Maßgebliche Nachweise sind `verification/2026-09-09-backend-final-frozen.xml` und `.txt`. Der Lauf enthält die Korrekturen für explizite Signalteilmengen innerhalb einer Route sowie für die notwendigen Netze eines ausgewählten Simulationsumfangs.

Der vorherige vollständige Backend-Lauf auf der isolierten PostgreSQL-Datenbank an Port 15439 war ebenfalls erfolgreich: **796 Tests bestanden, keine Fehler, 215,77 s**. Nachweise: `verification/2026-09-09-transport-full-pytest-release.xml` und `.txt`. Der korrigierte kombinierte Wizard-Ablauf einschließlich Simulation und Bewertung ist enthalten. Der danach ergänzte Begründungsvertrag für explizite Teilumfänge wurde mit Scope-, Coverage-, Workflow- und Simulationsgateway-Tests zusätzlich geprüft: **49 bestanden, 4,68 s**, Nachweise `verification/2026-09-09-postfreeze-scope-pytest.xml` und `.txt`.

`2026-09-09-transport-targeted-pytest.xml`: **202 Tests bestanden**. Darin sind CAN-FD→LIN- und CAN-FD→Ethernet-Strecken, unterschiedliche Bitraten, Signaltransport über Nachrichtenreferenzen, Eingangs-/Ausgangsausfall, hundertprozentiger Verlust, Anfangs-/End-Timeouts, fehlende Anforderungen, unabhängige Golden-Traces mit Signal-/Gateway-/Busfehlern, CSV, konfigurierte Jitteramplitude sowie UDP-/TCP-Sessions enthalten.

Der erste vollständige Backend-Lauf auf der isolierten PostgreSQL-Datenbank an Port 15439 ergab **758 bestanden, 3 Fehler**. Die Fehler betreffen noch parallel überarbeitete Port-/Topologie-Fixtures und die explizite Teilmodell-Abdeckung des Wizard-Tests; die Eigentümer wurden informiert. Dieser Lauf wird nicht als vollständig grüner Release-Nachweis bezeichnet.

Der zweite vollständige Lauf ergab **785 bestanden, 1 Fehler**. Die Port-/Topologieprobleme sind behoben. Der verbliebene Wizard-Test legte eine 500-ms-Nachricht mit einem ebenfalls 500-ms-Timeout und zu engem Jitterbudget auf einen gemeinsamen LIN-Bus; der Lauf wurde zu Recht als Anforderungsverletzung bewertet. Die Fachprüfung der Testanforderung und der abschließende Release-Lauf folgen im Gesamtbericht. Die gesonderte Gruppe für Routing, Transport und manuelles Speichern bestand anschließend mit **77 Tests**.

## Offline-Wiederholung des Originalprojekts

Die reproduzierbare Probe `verification/2026-09-09-transport-fixed-real260.py` benötigt keinen Datenbank- oder HTTP-Zugriff. Sie erzeugt das Ergebnis `2026-09-09-transport-fixed-real260.json`.

Die gemessenen Laufzeiten dieser Probe betragen 7,049 s für Simulation einschließlich Golden-Export, 1,866 s für die Runtime-Analyse und 0,509 s für Capacity. Das ist eine Einzelmessung auf dem vorhandenen Rechner für den gespeicherten einsekündigen Simulationsumfang.

| Messung | Ergebnis |
|---|---:|
| Hardwareknoten des gespeicherten Projekts | 260 |
| Bestehende freigegebene Routen | 217 |
| Tatsächliche Transportsegmente | 225 |
| Netzwerke in Runtime und Capacity | 83 |
| Trace-Ereignisse / Golden-Ereignisse | 12.800 / 12.800 |
| Beobachtete Signale aus den bestehenden Routen | 169 |
| Routen mit übernommener Jittergrenze | 217 |
| Routen PASS / FAIL | 193 / 24 |
| Gemeldete Jitterverletzungen | 44 |
| Trotz überschrittener Jittergrenze fälschlich PASS | 0 |

Das zuvor fehlende Zielnetz `Infotainment_08-S01` enthält nun 808 tatsächliche Ethernet-Ereignisse. Capacity verwendet Ethernet mit 100 Mbit/s und berechnet 0,5376 % mittlere Last des am stärksten beanspruchten Ports; die Simulation misst 0,536928 % bei ihrem tatsächlichen Beobachtungsfenster. Der Unterschied folgt dem Messfenster und wird nicht durch abweichende Technologie oder Bitrate verursacht.

Die alte Routenlücke bleibt in dieser gezielten Wiederholung erhalten: 169 beobachtete Signale entsprechen den vorhandenen Routen, nicht einer Abdeckung aller 520 Signale. Eine vollständige Projektreparatur muss die fehlenden Routen und Ports erstellen und anschließend neue Snapshots erzeugen. Die bisherigen, zu positiven Laufzeiturteile werden durch den Codefix nicht rückwirkend umgeschrieben.
