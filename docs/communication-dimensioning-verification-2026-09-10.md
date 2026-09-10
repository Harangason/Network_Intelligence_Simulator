# Automatische Kommunikationsdimensionierung – Umsetzung und Nachweis

Stand: 10.09.2026. Produktiver Build `8554560f2a42`. Projekt `network-project-20260910042736034-d11591d0` (NIS Projekt 1).

Die automatische Zyklusdimensionierung ist in den laufenden Simulator integriert. Wizard, Capacity, SQL-Übernahme, Simulation und Intelligence verwenden einen gemeinsamen Übertragungsvertrag. DBC und ARXML bleiben nachgelagerte Ausgaben des kanonischen Modells; sie sind keine notwendigen Eingabedateien.

## Verhalten im Entwicklungsablauf

1. Der Wizard erstellt zunächst Geräte, Nachrichten, Signale und physische Routen. Bei der Parametererzeugung prüft derselbe Dimensionierungsdienst den gesamten Busverkehr.
2. Für das Automotive-Entwicklungsprofil gelten zunächst mindestens 20 ms Sendeabstand, höchstens 50 ms für automatisch verlängerte schnelle Zyklen, 60 % nominale Zielauslastung und höchstens 90 % reservierte LIN-Slots. Diese Werte sind in Capacity und Intelligence unter **Kommunikation automatisch dimensionieren** editierbar. Bestehende langsamere Zyklen werden erhalten.
3. Je Bus werden aufsteigend Varianten wie 20, 25, 40 und 50 ms geprüft. Gesperrte/importierte/Nutzerzyklen, explizite Maximalperioden, Fristen, Datenalter, Timeout und Jitter begrenzen die Auswahl. Ein nicht gefundener Plan wird als offen ausgewiesen, nicht durch veränderte Grenzwerte passend gemacht.
4. Die Übernahme aktualisiert Nachricht, Signal-Kommunikationsparameter, alle betroffenen Routen und den LIN-Plan gemeinsam in einer SQL-Transaktion. Ein Versions-Token verhindert die Übernahme einer veralteten Vorschau. Nur erfolgreich validierte Routen werden erneut freigegeben. Nachgelagerte Ergebnisse werden neu berechnet.
5. Simulationssnapshots übernehmen die kanonischen Perioden und tatsächlichen physischen Busse. LIN-Pläne werden vor dem Einfrieren gegen den aktuellen Modellstand erneut berechnet; alte Slotbreiten werden nach Bitraten-/Modelländerungen nicht ungeprüft weiterverwendet.
6. Intelligence erhält Varianten, Ablehnungsgründe, Prüfannahmen und passende frühere Dimensionierungen. Historie liefert Kandidaten, die mit aktuellen Eingaben erneut geprüft werden. Das ist nachvollziehbare Wiederverwendung von Projekterfahrung, kein unkontrolliertes Übernehmen früherer Freigaben und kein behauptetes neues LLM-Training.

## Busmodelle

- **LIN:** vollständiger Rahmen einschließlich Checksumme, `34 + 10 × (Nutzbytes + 1)` Bits nominal. Wiederkehrende, nicht überlappende Master-Slots auf einer 5-ms-Zeitbasis. Reservierung strikt größer als 1,4-fache nominale Rahmendauer plus konfigurierter Master-Jitter. Messwertbereitstellung folgt dem Pollplan. Bei nachgelagerten LIN-Strecken wird die mögliche Wartezeit bis zum nächsten Slot einbezogen.
- **CAN/CAN-FD:** nicht unterbrechbare laufende Frames; unter wartenden Sendungen entscheidet die CAN-ID. Die konservative Antwortgrenze berücksichtigt niederpriore Blockierung, höherprioren Verkehr, Release-Jitter und einen großzügigen Rahmenlängenaufschlag. Der aktuelle Nachweis gilt für Standard-Identifier und streng nach ID priorisierte Senderqueues. Erweiterte Identifier erhalten keinen vereinfachten Nachweis über bloße numerische Sortierung.
- **Broadcast:** ein physischer Frame wird unabhängig von der Anzahl logischer Empfänger nur einmal in der Buslast gezählt. Alle Empfängerreferenzen und deren jeweils strengste Anforderungen bleiben erhalten. Die Trace-Auswertung trennt zusätzliche Empfangsbeobachtungen von zusätzlichen Sendungen.
- **Ethernet:** bestehende Auslastung pro Full-Duplex-Port bleibt berechenbar. Der neue CAN-/LIN-Dienst behauptet keinen zusätzlichen deterministischen Ethernet-/Switch-Nachweis. Die bestätigte Mindestabstandsregel kann für konsistente, generierte zyklische Nachrichten übernommen werden; diese Änderungen tragen `POLICY_ONLY_UNVERIFIED`, und die fehlende Ethernet-Antwortgrenze bleibt sichtbar. Eine über CAN und Ethernet weitergeleitete Nachricht erhält dennoch nur eine kanonische Periode.

Die online gegengeprüften Grundlagen sind [LIN 2.2A](https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/16-bit/18786/3/LIN_Specification_Package_2.2A.pdf), [AUTOSAR COM](https://www.autosar.org/fileadmin/standards/R25-11/CP/AUTOSAR_CP_SWS_COM.pdf) und die [korrigierte CAN-Schedulability-Analyse von Davis et al.](https://link.springer.com/article/10.1007/s11241-007-9012-7). Die implementierte CAN-Grenze ist bewusst konservativ; sie ersetzt keinen fahrzeugbezogenen Funktionsnachweis.

## Tatsächliche Projektkorrektur

295 Nachrichten wurden in zwei zusammenhängenden Übernahmen abgeglichen, einschließlich Herkunft und konsistenter Kopien. Es wurden 90 Perioden angepasst; weitere Änderungen ergänzen explizite Übertragungsverträge. Alle 303 beziehungsweise 67 betroffenen Routen wurden jeweils erfolgreich validiert und erneut freigegeben. Keine Nachrichten/Signale wurden gelöscht und keine Bitrate allein aus einer technischen Namensendung abgeleitet. Vorher wurde ein vollständiges Projektbundle gesichert.

| Physischer Bus | Tatsächliche Nachrichtenzyklen | Nominaler Busbedarf | Reservierte LIN-Slots |
| --- | ---: | ---: | ---: |
| Bremsregelung LIN 01 | 50 ms | 53,33 % | 80 % |
| Daempferregelung LIN 01 | 50 ms | 53,33 % | 80 % |
| Motorsteuerung LIN 05 | 20 ms | 50,00 % | 75 % |
| Elektromotorsteuerung LIN 03 | 20 ms | 50,00 % | 75 % |
| Batteriemanagement LIN 03 | 25 / 50 ms | 46,67 % | 70 % |
| Motorsteuerung LIN 06 | 40 ms | 41,67 % | 62,5 % |

Alle 90 CAN-/LIN-Netze besitzen einen Plan beziehungsweise eine Antwortgrenze unter den ausgewiesenen Modellannahmen. Kein berechneter physischer Sendestrom liegt mehr unter 20 ms. Ein weiterer Dimensionierungslauf findet **0 notwendige Nachrichtenänderungen** und erkennt **90 passende historische Buskonfigurationen**.

Die bisherigen sechs Überlastfälle sind beseitigt. Die geringste nominale Kapazitätsreserve beträgt nun 46,67 %. Vier Netze erreichen im rechnerischen Stressszenario den Status CRITICAL, zwei WARNING; es gibt keinen OVERLOAD. Der Stressfaktor 1,5 und der Peakfaktor 1,15 werden ausdrücklich angezeigt. Sie sind weder gemessene Spitzen noch gleichzeitig auf dem Bus sendende Teilnehmer. Die fünf Ethernet-Netze bleiben hinsichtlich deterministischer Antwortzeiten offen. Der Gesamtstatus ist deshalb weiterhin WARNING.

**50 ms ist hier ein zulässiges Ergebnis innerhalb des konfigurierten Entwicklungsprofils. Daraus folgt keine allgemeine Aussage, dass 50 ms für jede Bremsfunktion ausreichend oder sicher sind.** Eine strengere bestätigte Aktualitätsanforderung verhindert die betreffende Verlängerung.

## Verifikation

- 185 Backend-Regressionsfälle bestanden; drei bestehende Fälle benötigen eine separate SQL-Testumgebung und wurden im lokalen Sammellauf übersprungen.
- Separater SQL/API-Test gegen `nis_communication_sizing_tests` bestanden: Versionskonflikt, vollständiger Rollback bei injiziertem Fehler, Nachrichten-/Signal-/Routing-Konsistenz, erneute Freigabe sowie gespeicherte Historie und Slots.
- 75 Frontend-/Generator-Tests bestanden; TypeScript und Produktionsbuild bestanden.
- Zusätzlicher Broadcast-Test sichert, dass wiederholte physische Zusammenfassung keine Empfängerreferenzen verliert.
- Live-API: erneute Dimensionierung idempotent; Preflight mit **0 Fehlern**, `ready_for_simulation=true`; Intelligence auf aktuelle Eingaben neu berechnet.
- Aus dem real gespeicherten Snapshot: 386 logische Kommunikationspfade, 461 physische Segmente, 3.885 Trace-Ereignisse in 0,3 s. Auf allen 90 CAN-/LIN-Netzen keine überlappende Übertragung; alle 1.087 LIN-Ereignisse entsprechen ihren Slots. Alle 1.709 prüfbaren finalen Empfangsereignisse bleiben innerhalb der berechneten Antwortgrenzen. SQL-, Nachrichten- und Runtime-Perioden stimmen überein.
- Reguläre Simulationsjobs `406af0fb8bbe4f30a2de556a87871a72` und abschließend `27245679c2424eb085368d641189085e` abgeschlossen, ohne Ausführungsfehler; Ergebnisse anschließend in Intelligence neu bewertet. Die kurze Laufzeit ist ein Smoke-Test und keine vollständige Absicherung sämtlicher Last-/Fehlerszenarien.
- Browser: produktiver Build, tatsächliche 50-ms-Zyklen für Brems-/Dämpferregelung, richtige Busnamen, Stresskennzeichnung und erfolgreiche Neuberechnung mit 0 Änderungen sichtbar. Ändern einer Eingabe verwirft die bisherige Vorschau. Keine JavaScript-Fehler im geprüften Tab.

## Grenzen gegenüber dem gesamten Zielbild

Diese Änderung implementiert die automatische Zyklus- und Slotdimensionierung einschließlich gemeinsamer Persistenz und Bewertung. Sie ersetzt nicht alle weiteren Entwicklungswerkzeuge: Bitratenwahl, Packing und physische Segmentierung bleiben bei nicht erfüllbaren Zyklusvarianten ausdrücklich vorgeschlagene Folgemaßnahmen. Ereignis-/Anfrageverkehr ohne spezifizierte Raten und Auslöser wird nicht als beweisbar behandelt; bestehende Zustandsnachrichten werden nicht allein wegen ihres Namens zu Event-Frames umgedeutet. Die vollständige Ereignis-/Anfragesemantik sowie DBC-/ARXML-Export-Roundtrips aus dem weitergehenden Konzept sind nicht durch diesen Nachweis pauschal als fertig erklärt.

Die historischen 5-/10-ms-Auditzahlen im [ursprünglichen Bericht](I:/PycharmProjects/My_first_Network_Simulator/docs/capacity-audit-2026-09-10.md) beschreiben den früheren Zustand. Das [erweiterte Zielkonzept](I:/PycharmProjects/My_first_Network_Simulator/docs/communication-timing-design-2026-09-10.md) bleibt für die weitergehenden Sendemodi und Exporte erhalten.
