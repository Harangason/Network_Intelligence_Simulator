# LIN-Bremsregelungsbus, Signaldefinition und Musteraufzeichnungen

Stand: 10.09.2026. Gemeinsame Prüfung der vier Nutzernachrichten. Projekt: `network-project-20260910042736034-d11591d0`.

**Ergebnis: Auf Bremsregelung LIN 01 liegen acht Sensor-Datensender und das Steuergerät Bremsregelung, also neun physische Teilnehmer. Alle acht Nachrichten haben zwei Nutzdatenbytes. Die Nutzdaten sind nicht zu groß für LIN. Die zitierten 310,5 %/405 % stammen aus einer früheren, inzwischen ersetzten Bewertung.**

Geprüft wurden der aktuelle SQL-Projektexport und Capacity-Snapshot `3541bf91-0b7b-4610-98af-27a0f8d5a20f` vom 10.09.2026, 14:18:44 UTC (16:18:44 MESZ). Beim Abruf war `is_outdated=false`. Diese Untersuchung verändert weder Projektparameter noch die Musterdateien. Die bereits produktive automatische Dimensionierung ist im [Umsetzungsnachweis](I:/PycharmProjects/My_first_Network_Simulator/docs/communication-dimensioning-verification-2026-09-10.md) beschrieben.

## 1. Tatsächliche Sender und Nutzdaten

| Datensender | Signal | Bits | Nutzdaten pro Nachricht | Aktueller Abstand |
| --- | --- | ---: | ---: | ---: |
| BrakePedalPosition | Bremspedalstellung | 10 | 2 Byte | 50 ms |
| FrontLeftBrakePressure | Bremsdruck vorne links | 12 | 2 Byte | 50 ms |
| FrontRightBrakePressure | Bremsdruck vorne rechts | 12 | 2 Byte | 50 ms |
| RearLeftBrakePressure | Bremsdruck hinten links | 12 | 2 Byte | 50 ms |
| RearRightBrakePressure | Bremsdruck hinten rechts | 12 | 2 Byte | 50 ms |
| FrontLeftBrakeTemperature | Bremstemperatur vorne links | 12 | 2 Byte | 50 ms |
| FrontRightBrakeTemperature | Bremstemperatur vorne rechts | 12 | 2 Byte | 50 ms |
| RearLeftBrakeTemperature | Bremstemperatur hinten links | 12 | 2 Byte | 50 ms |

Die neun Teilnehmer sind sowohl über die physischen Anschlüsse als auch über die Kommunikationspfade nachweisbar. „Acht Sender“ meint die Herausgeber der Nutzdaten. Der LIN-Master sendet zusätzlich die Header; jeder reguläre Frame besteht aus Header und einer zugeordneten Antwort. Mehrere Empfänger vervielfachen einen Frame nicht. [NI: LIN-Aufbau und Ablauf](https://www.ni.com/de/shop/seamlessly-connect-to-third-party-devices-and-supervisory-system/introduction-to-the-local-interconnect-network-lin-bus.html).

RearRightBrakeTemperature liegt im aktuellen Modell auf **Bremsregelung LIN 02**. Stellglied, Schaltausgang und ihr gemeinsamer Befehl liegen auf **Bremsregelung LIN 03**. Diese drei Busse dürfen bei Senderzahl und Last nicht vermischt werden.

Die acht Messsignale beginnen jeweils an Bit 0 und passen vollständig in ihre 16-Bit-Nutzlast. Druck: 12 Bit unsigned, Faktor 0,1 bar, Bereich 0–250 bar. Temperatur: 12 Bit signed im aktuellen kanonischen Modell, Faktor 0,5 °C, Bereich −40–900 °C. Das bestätigt die Größenprüfung; eine spätere LIN/LDF-Kodierung muss auch die unsigned-Skalardefinition des LIN-Protokolls berücksichtigen. Eine negative physikalische Temperatur ist beispielsweise durch unsigned Rohwerte plus negativen Offset darstellbar; eine DBC-Signed-Kodierung darf nicht ungeprüft als identische LDF-Definition exportiert werden.

## 2. Woher die alten Zahlen kommen

Der historische Snapshot aus [capacity-audit-2026-09-10.md](I:/PycharmProjects/My_first_Network_Simulator/docs/capacity-audit-2026-09-10.md) enthält:

- vier Drucknachrichten alle 5 ms,
- eine Pedalnachricht alle 10 ms,
- drei Temperaturnachrichten alle 50 ms.

Der frühere Rechner vergaß das Prüfsummenbyte: `54 / 19200 = 2,8125 ms` pro 2-Byte-Frame. Daraus entstanden:

```text
270 % mittlerer angeforderter Bedarf
270 % × 1,15 = 310,5 % rechnerischer Peak
270 % × 1,50 = 405,0 % rechnerischer Burst
8 × 2,8125 ms = 22,5 ms für eine angenommene gemeinsame Freigabe
5 ms Periode + 5 ms Jitterbudget − 0,21 ms feste Verzögerung = 9,79 ms Budget
```

Das letzte Budget stammt aus dem alten `LIN_NON_PREEMPTIVE_BATCH_BOUND_V1`. Es beschreibt weder eine gemessene gleichzeitige Übertragung noch den aktuellen Master-Schedule. Die damalige Bezeichnung „gleichzeitige LIN-Frames“ war missverständlich. Die Peak-/Burstwerte waren Multiplikatoren, keine Messungen.

Mit vollständiger Prüfsumme hätte der nominale Bedarf bei denselben alten Zyklen sogar **320 %** betragen. Serialisierung vermeidet überlagerte reguläre Antworten, schafft aber keine zusätzliche Bandbreite: 3,2 Sekunden angeforderte Buszeit passen nicht in eine Sekunde.

Die technische ID `Fahrwerk_Fahrdynamik_03-IO-bremsregelung-can-fd-S01` blieb bei einem protokollseitigen Wechsel durch `network-editor-bus-change` erhalten. Der im früheren Audit belegte Änderungspfad vom 10.09.2026, 09:56:38 MESZ, erklärt die Endung. Maßgeblich sind heute physischer Anschluss, Bindung und **LIN mit 19.200 bit/s**, nicht `can-fd` im alten Schlüssel. Anzeigename: **Bremsregelung LIN 01**.

## 3. Heutige Rechnung und ihre Aussagegrenze

Ein vollständiger LIN-Frame hat nominal `34 + 10 × (Nutzbytes + 1)` Bit. Die Zeitreserve ist separat zu berücksichtigen. Die angegebenen 4–5 ms für **acht** Nutzbytes sind falsch: Bei 19,2 kbit/s sind es nominal **6,458 ms**, mit Faktor 1,4 **9,042 ms**. Zwei Nutzbytes brauchen nominal **3,333 ms**, maximal nach dieser Rahmenformel **4,667 ms**. [NI: LIN-Timing](https://www.ni.com/de/shop/seamlessly-connect-to-third-party-devices-and-supervisory-system/introduction-to-the-local-interconnect-network-lin-bus.html), [ebm-papst: Rahmenzeit und 40-%-Reserve](https://mag.ebmpapst.com/de/allgemein/die-formel-fuer-die-datentransferzeit_19778/).

| Aktuelle Größe | Wert | Bedeutung |
| --- | ---: | --- |
| Nominaler Busbedarf | **53,33 %** | `8 × 3,333 ms / 50 ms` |
| Nominale freie Kapazität | **46,67 %** | Differenz zu 100 % |
| Reservierte Slots | **80 %** | Acht 5-ms-Slots in 50 ms |
| Freie Schedule-Zeit | **10 ms je 50 ms** | Übrige Zeit nach Slotreservierung |
| Rechnerischer Peak | **61,33 %** | Nominaler Bedarf × 1,15 |
| Rechnerischer Burst | **80 %** | Nominaler Bedarf × 1,50 |

Die beiden 80-%-Werte sind hier zufällig gleich, haben aber verschiedene Bedeutungen. Der gespeicherte Gesamtstatus des Busses ist weiterhin `CRITICAL`, weil die bestehende Stressbewertung 80 % gegen das 60-%-Ziel bewertet. Das ist kein aktueller physischer `OVERLOAD`. Der Schedule ist unter seinen angegebenen Annahmen machbar.

```text
50-ms-Wiederholung: [0–5][5–10][10–15][15–20][20–25][25–30][30–35][35–40][40–50 frei]
                    je Slot eine andere der acht Nachrichten
```

Die gespeicherte Antwortgrenze von 4,667 ms bezieht sich auf die Rahmenübertragung unter der Annahme, dass die Wertbereitstellung dem Pollplan folgt. Sie ist **keine** allgemeine Grenze von einem beliebigen physikalischen Ereignis bis zur Reaktion der Bremsfunktion. Dafür zählen auch Abtastung, Wartezeit bis zum Poll, Applikationsverarbeitung und Aktuation. Ein 50-ms-Sendeplan beweist daher nicht, dass 50 ms für eine primäre Bremsregelung ausreichend sind.

## 4. Einordnung der zugesandten Quellen

- Die TUM-Arbeit heißt *Untersuchung der fahrdynamischen Potenziale eines elektromotorischen Traktionsantriebs*. Auf PDF-Seite 149 stehen 10 ms für Antriebs-/Drehzahlregler und 1 ms für die Bremsensoftware im beschriebenen Versuchsaufbau. Das sind dort Software-Rechenzyklen. Im geprüften Text fand sich keine Belegstelle für die zugesandte allgemeine LIN-Tabelle oder „CAN/FlexRay zwingend 1–5 ms“. [TUM-Originalarbeit](https://mediatum.ub.tum.de/doc/1237178/document.pdf).
- Der all-electronics-Artikel stammt laut Dokument aus **elektronik industrie 1/2–2006**, obwohl der URL-Pfad 2025 enthält. Er behandelt LIN-Anwendungen, Gateways und Konformitätstests, liefert aber keine der behaupteten universellen Bremszyklusvorgaben. [Artikel von Gavin C. Rogers, Vector](https://www.all-electronics.de/files/2025/10/15/ei06-02-072.pdf).
- Die LIN-Spezifikation beschreibt Master-Schedules, Slots, Ereignisrahmen und Kollisionsauflösung. Sie gibt keine pauschale sichere Bremszykluszeit vor. Auch ein ereignisgetriggerter LIN-Frame benötigt einen Master-Slot; gleichzeitige Antworten werden durch einen Auflösungsplan behandelt. [LIN 2.2A, Abschnitte 2.3.3 und 2.4](https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/16-bit/18786/3/LIN_Specification_Package_2.2A.pdf).
- Die frühere Aussage „LIN weit über 50 Teilnehmer“ ist ebenfalls keine allgemeine Standardfreigabe: LIN 2.2A Abschnitt 6.5.5 empfiehlt wegen der Netzimpedanz höchstens 16 Knoten. Ein editierbares Planungsmaximum ersetzt keinen elektrischen Nachweis. Die hier vorhandenen neun Teilnehmer sind unterhalb dieser Empfehlung.
- CAN kann konkurrierende Sendewünsche haben. Die Arbitration entscheidet über den Frame; bloßes Abwarten eines freien Busses garantiert noch keine Deadline. [Analog Devices AN-1123](https://www.analog.com/en/resources/app-notes/an-1123.html).
- Zustandswerte müssen nicht grundsätzlich nur bei Ereignissen gesendet werden. Periodisch, direkt und gemischt sind unterschiedliche konfigurierbare Modi. [AUTOSAR COM R24-11, ComTxMode](https://www.autosar.org/fileadmin/standards/R24-11/CP/AUTOSAR_CP_SWS_COM.pdf).
- Der verlinkte YouTube-Short konnte nicht inhaltlich geprüft werden. Der Werkstatt-Blog wurde geöffnet, aber nicht als Protokoll- oder Funktionsspezifikation übernommen.

Die Beispiele 10–20 ms beziehungsweise 50–100 ms können als zu prüfende Entwurfskandidaten dienen. „Niemals“, „zwingend“ und „absolut plausibel“ gehen über die vorgelegten Nachweise hinaus. Die bestätigte Projektregel von mindestens 20 ms bleibt eine Projektregel und wurde durch das bloße Zusenden dieser Texte nicht verändert.

## 5. Das konkrete 10-Bit-Prozentsignal

Die Definition gehört tatsächlich zu **BremsregelungStellgliedSollwert** auf **Bremsregelung LIN 03**:

| Bereich im 2-Byte-Befehl | Inhalt |
| --- | --- |
| Bit 0 | Schaltausgang-Sollwert OFF/ON |
| Bits 1–10 | Stellglied-Sollwert, unsigned, Faktor 0,1 %, Offset 0 |
| Bits 11–15 | Noch unbelegt |

Rohwerte 0–1000 bilden 0–100 % in Schritten von 0,1 % ab. Rohwerte 1001–1023 sind **23 weitere Kodierungen**. Sie sind nicht automatisch Fehler-, Initial- oder Reservewerte. Für dieses Sollwertsignal sind keine solchen Bedeutungen explizit gespeichert. Bit 1 ist hier sinnvoll, weil Bit 0 bereits belegt ist. Die Bitbelegung überschneidet sich nicht. Eine unabhängige Kodier-/Dekodierprüfung mit cantools bestand für alle 1001 Sollwerte kombiniert mit beiden Schaltzuständen, also **2002 Kombinationen**.

**Zusätzlicher Datenbefund:** Beim separaten `BremsregelungStellgliedStatus` stehen 10 Bit, Faktor 0,1 und Einheit `%` gleichzeitig neben `OK/WARNING/ERROR/NOT_AVAILABLE` und einer Auflösung von 1. Der Audit findet insgesamt **104 Prozent-Signale mit einer zusätzlichen Enum-Domäne**. Das ist eine Prüfliste, keine pauschale Lösch- oder Umkodierungsfreigabe: Messwert, Stellungsrückmeldung und Gerätezustand müssen fachlich unterschieden werden.

Ein konkreter Ursprung ist der Generatorpfad `generatedSignalSemanticType` / `stateDomain` in `frontend/src/lib/agent/engineering-specification.ts`: Er leitet unter anderem aus „Status“ einen Zustand ab, ergänzt eine feste Enum-Domäne und behält gleichzeitig Eingabe-Einheit und Skalierung. Der entsprechende Backend-Pfad liegt in `backend/engineering/workloads/handlers.py`. Beim Prozent-Sollwert ist dieser Konflikt nicht vorhanden. Für Zustände muss eine konsistente Kodierung definiert werden; freie Rohwerte dürfen nicht lediglich aufgrund einer mathematischen Lücke als Fehlercodes erfunden werden.

## 6. Was die Musterdateien tatsächlich belegen

Beide genannten Verzeichnisse wurden vollständig inventarisiert: **12 MF4-Dateien und 13 DBC-Dateien**. Acht MF4 stammen aus dem Tracepaket, vier weitere aus den DBC-Beispielen. Alle DBCs ließen sich streng parsen. In keiner der zwölf Aufzeichnungen wurden LIN-Frames gefunden. Das Tracepaket enthält getrennt Audi-OBD2, Lkw-J1939 und interne GPS-/IMU-Daten.

Die DBC-README bezeichnet die Dateien ausdrücklich als generische standardisierte OBD-PIDs und schließt proprietäre PIDs aus. Es handelt sich nicht um eine vollständige Audi-A4-Kommunikationsmatrix. Die reguläre DBC beschreibt vier CAN-Identifier-Varianten mit 891 Signaldefinitionen einschließlich Multiplexern. Keine der 13 DBCs liefert eine `GenMsgCycleTime`-Vorgabe.

Audi-Datei: `OBD2 (Audi A4)/LOG/31CB1F25/00000022/00000002.MF4`, ausgewertete Dauer **556,6752 s**:

| Daten | Anzahl / beobachteter Median |
| --- | --- |
| CAN-Frames insgesamt | **29.693** |
| Tester-Anfragen, ID 0x7DF | **18.176**, Abstand **20,00 ms** |
| Antworten, ID 0x7E8 | **11.517**, Abstand über alle PIDs **39,95 ms** |
| Antwort-PIDs 0x0B, 0x0C, 0x0D, 0x11, 0x1F | je Messgröße ungefähr **200 ms** |
| Kühlmitteltemperatur, PID 0x05 | ungefähr **1000,05 ms** |
| LIN-Frames | **0** |

Nicht für jede abgefragte PID ist eine Antwort im Mitschnitt vorhanden. Die unterschiedliche Anzahl belegt für sich allein keinen Paketverlust. Ein Median ist weder eine garantierte Maximalfrist noch ein Beweis für vollständig erfassten Fahrzeugverkehr. Alle 29.693 Audi-Frames ließen sich mit der regulären OBD-DBC dekodieren. Zwei unabhängige Leser stimmen für die Audi-Datei in Framezahl und ID-Häufigkeiten überein. Die ISO-TP-DBC-Variante darf nicht unverändert auf rohe CAN-Bytes angewendet werden, da sie einen anderen Transport-Layer-Zuschnitt beschreibt.

Damit sind die Dateien gut geeignet, um Decoder, Skalierung, Multiplexing, Anfrage-Antwort-Beziehungen und die Trennung von Frame-Rate und Messwert-Rate zu prüfen. Aus dem Diagnosekanal lassen sich **keine** internen Audi-Bremsregelungsfristen oder LIN-Schedules ableiten. Das entspricht auch der dokumentierten OBD-Anfrage-/Antwortarchitektur. [CSS Electronics: OBD2](https://www.csselectronics.com/pages/obd2-explained-simple-intro).

## 7. Konsequenz für die weitere Auslegung

1. **Kodierung:** Bitlänge und Framegrenze prüfen; Messwert und Zustand fachlich trennen; Fehler-/Reserve-/Initialwerte ausdrücklich definieren.
2. **Anforderungen:** Perioden, Ereignis-/Anfrageraten und End-to-End-Anforderungen pro Funktion festlegen. Keine universelle Bremsfreigabe aus 20 oder 50 ms ableiten.
3. **Busentscheidung:** Langsame Überwachung und schnelle Regelpfade getrennt dimensionieren. Passt eine bestätigte Frist nicht auf LIN, Aufteilung oder CAN/CAN-FD prüfen, statt die Frist still zu verlängern.
4. **Optimierung:** Packing nur innerhalb eines zulässigen gemeinsamen Publishers und kompatibler Anforderungen. Ein regulärer LIN-Frame kann nicht einfach die Antworten mehrerer selbständiger Sensoren zusammenpacken; dafür wäre ein vorgeschalteter Sammler beziehungsweise eine andere Architektur nötig.
5. **Bewertung:** Payloadprüfung, Schedule-Machbarkeit, nominale Last, Stressszenario und funktionale Eignung getrennt ausweisen. Die bestehende Warnung zum Stressziel darf nicht wie 405 % physische Belegung erscheinen.
6. **Referenzwissen:** Herkunft, Kanal, Diagnose-/Betriebsverkehr und Messdauer erhalten. Historische Beobachtungen liefern Kandidaten, keine stillen Grenzwerte. Die Audi-Datei darf nicht zum Trainingsbeleg für LIN-Bremszyklen werden.
7. **Export:** DBC/ARXML entstehen aus dem geprüften kanonischen Modell. Für den vollständigen LIN-Master-Schedule ist zusätzlich LDF relevant; passende unabhängige Decoder müssen die ausgegebenen Dateien und Grenzwerte prüfen.

Dieser Absatz beschreibt den ursprünglichen Auditstand. Die anschließend freigegebene Reparatur der Generatordomänen, die gemeinsame Prüfung der Übertragungsprofile und die getrennte Netzbewertung sind im [Umsetzungs- und Prüfbericht vom 10.09.2026](I:/PycharmProjects/My_first_Network_Simulator/docs/lin-analysis-implementation-2026-09-10.md) dokumentiert. Dort stehen der aktuelle räumlich aufgeteilte Bremsbus, die Live-Prüfergebnisse und die verbleibenden Grenzen der Anfragegenerierung und funktionalen Nachweise.

## Reproduktion

Leseskript: [audit_lin_reference_samples.py](I:/PycharmProjects/My_first_Network_Simulator/scripts/audit_lin_reference_samples.py). Maschinenlesbares Ergebnis: [lin-reference-audit.json](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/lin-reference-audit.json). Darin stehen SHA-256-Prüfsummen der Quellen, Leser-Versionen, aktuelle Sender-/Signalzuordnungen, unabhängige Lastrechnung sowie die 104 auffälligen Domänen. Rohpayloads und VINs werden nicht in den Auditbericht geschrieben.

```powershell
backend/.venv/Scripts/python.exe scripts/audit_lin_reference_samples.py --reader-path backend/runtime/lin-sample-reader --trace-root 'H:/OneDrive/Download/mf4-sample-data-v2.1' --dbc-root 'H:/OneDrive/Download/obd-dbc-files-v4.3' --capacity backend/runtime/lin-four-capacity.json --bundle backend/runtime/lin-four-bundle.json --output backend/runtime/lin-reference-audit.json
```

Verwendete Leser: `mdf_iter 2.1.1`, `asammdf 8.8.27`, `cantools 43.0.2`, isoliert im Runtime-Verzeichnis. Die CANedge-Dateien verwenden teilweise gepackte Felder; dafür wurde der herstellerspezifische MDF-Leser verwendet. Ergebnisse aus unmaskierten generischen Composite-Feldern wurden nicht als gültige CAN-Identifier übernommen.
