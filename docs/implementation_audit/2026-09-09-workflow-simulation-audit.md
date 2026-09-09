# NIS: Workflow- und Simulationsprüfung vom 9. September 2026

Die aktuelle Kette läuft technisch durch, liefert aber noch keinen belastbaren Nachweis, dass das gesamte Projekt fachlich korrekt simuliert wurde. Im realen Lauf gehen vorhandene Timing-Anforderungen verloren; dadurch erhalten 20 Routen trotz überschrittener Jittergrenze ein `PASS`. Außerdem fehlen 351 von 520 Signalen im transportierten Ergebnis sowie ein belegtes Gateway-Zielsegment. Zwei isolierte Gegenproben zeigen zusätzliche Fehler bei vollständigem Nachrichtenausfall und der Golden-Trace-Erzeugung.

Untersucht: `network-project-20260909082213746-780a13ef`, SimulationSnapshot `8d0766df-0a7a-490a-95ea-13b2b27b2a17`, Job `2c3bd96c667e4d9b84f33d0d4aec5222`. Der eingefrorene Stand besitzt 260 Hardware-Knoten, 61 Funktionen, 326 Interfaces, 309 Nachrichten, 520 Signale und 217 Routen. Laufdauer: 1 s; Trace: 11.992 Events; 217 Runtime-Routen. Die Prüfung verwendete HTTP-GETs und lokale temporäre Testartefakte; Nutzerdaten und laufende Projektstände wurden nicht geändert.

## 1. P1 – Vorhandene Timing-Grenzen gehen vor der Laufzeitauswertung verloren

**Live nachgewiesen:** Alle 217 kanonischen Routen im eingefrorenen Snapshot besitzen `jitter_limit_ms=5`, `max_latency_ms=20`, `timeout_ms=500`. In den ausführbaren `communications` fehlen Jitter und Timeout; `deadline_ms` ist null. Alle 217 Runtime-Routen melden fehlende Jitter-/Latenzgrenzen und `PASS`, obwohl 20 den kanonischen Jittergrenzwert überschreiten.

Beispiel: `FrontLeftTireTemperature → Reifendruckkontrolle`, kanonische Route `08c24a56-8869-406e-b7c9-d5c3ea477702`: gemessener maximaler Jitter **9,243816 ms**, geforderter Grenzwert **5 ms**, ausgegebene Verletzungen **0**, Status **PASS**. `Infotainment → HeadUpDisplayStellglied` meldet ebenfalls PASS bei 9,076206 ms. Dies sind keine fehlenden Anforderungen des Nutzers, sondern verlorene Daten beim Übergang in die Simulation.

**Codeursache:**

- `backend/engineering/routing/config_builder.py:189–193`: exportiert `cycle_time_ms` als `cycle_ms`, liest jedoch `timing.deadline_ms` statt des normalisierten `timing.max_latency_ms`; `jitter_limit_ms` und `timeout_ms` werden nicht übernommen.
- `backend/app/runtime_analysis.py:41–46`: Anforderungen werden nur aus `communications`/`routes` gewonnen.
- `backend/app/runtime_analysis.py:197–217`: Fallbacks lesen flache Konfigurationsfelder; die vorhandenen Werte in `config.parameters` werden nicht aufgelöst.
- `backend/app/runtime_analysis.py:266`: Ohne erkannte Verletzung wird PASS vergeben, auch wenn keine Grenze angekommen ist.

**Lösung:** Ein gemeinsames, typisiertes Anforderungsobjekt mit kanonischer Route-ID, Einheit, Quelle und Gültigkeit durch Routing, Capacity, Snapshot, Runtime und Intelligence führen. Feldnamen einmalig normalisieren. Die Auswertung muss fehlende/ungeprüfte Anforderungen von erfüllten Anforderungen unterscheiden (`NOT_EVALUATED`/`INCOMPLETE` statt PASS). Ein optionales Default darf eine explizite Routenanforderung nicht überdecken.

**Abnahme:** Im gleichen eingefrorenen Projekt besitzen alle 217 Runtime-Routen exakt die bestätigten Grenzen; die 20 bekannten Überschreitungen werden erkannt. Ein Test setzt unterschiedliche Werte für Route, Nachricht, Signal und Projektdefault und überprüft die dokumentierte Priorität über den gesamten Übergang bis in das Ergebnis. `max_latency_ms`, Timeout, Jitter und Freshness werden jeweils durch einen tatsächlich verletzenden Lauf geprüft.

## 2. P1 – Erfolgreicher Workflowabschluss wird mit unvollständiger Simulationsabdeckung vermischt

**Live nachgewiesen:** 162 von 309 Nachrichten sind ausführbaren Communications zugeordnet. Der tatsächliche ModelTrace enthält **169 von 520 Signalen = 32,5 %**. **147 Nachrichten und 351 Signale** bleiben außerhalb des transportierten Ergebnisses. Beispiele sind `FahrwerkStatus`, `LichtStatus`, viele ECU-Statusmeldungen und generierte Aktorstatusmeldungen. Die Signal-Emulationsprüfung zählt dagegen 520 validierte/inferierte Signale.

Engineering-Modell, Netzwerk, Capacity, Simulation und Results stehen auf COMPLETE, Routing und Preflight auf APPROVED. Die spätere Intelligence-Seite zeigt die fehlenden 351 Signale und 32,5 % Signal Coverage tatsächlich an. Die Lücke ist dort also sichtbar; das Problem ist die fehlende gemeinsame Bedeutung der vorgelagerten Freigaben und der späteren Kennzahlen. Ein technisch abgeschlossener Teillauf und die Abnahme des gesamten Modells werden im Workflow nicht sauber unterschieden.

**Codeursache:**

- `backend/engineering/workflow/service.py:401–453`: Routing-Vollständigkeit prüft vorhandene aktive Routen auf Freigabe/Validität, aber nicht die Abdeckung der eingeschlossenen Nachrichten oder Signale.
- `backend/engineering/capacity/service.py:1010–1026`: Preflight prüft Elternreferenzen; `:1028` prüft vorhandene Routen. Ein Abgleich „Modellumfang → ausführbarer Transport → beobachteter Trace“ fehlt.
- `backend/simulator/model_based_simulation.py:539–555`: Signale werden anhand der konkreten Transportzuordnung ausgewählt; nicht geroutete Signale erzeugen daher keine Samples.
- `backend/engineering/workflow/service.py:1202–1209`: Bereits irgendeine Runtime-/Trace-/Hardware-/Warnungs-Evidenz genügt für `results_analysis=COMPLETE`. Diese Datei weicht im laufenden Image vom Workspace ab; sie belegt den aktuellen Workspace-Mechanismus. Die grünen Live-Status und die tatsächlichen Abdeckungszahlen sind unabhängig über APIs und Browser bestätigt.

**Lösung:** Vor dem Preflight einen verbindlichen Simulationsumfang festlegen. Jedes eingeschlossene Signal benötigt entweder einen ausführbaren Transportpfad oder eine explizit deklarierte lokale Auswertung. Nicht benötigte Empfangsdefinitionen, Hilfssignale und bewusst nicht modellierte Pfade dürfen mit begründetem Ausschluss existieren. Den Umfang nicht durch künstliches Routing sämtlicher Daten „reparieren“. Preflight und Results müssen Soll- und Ist-Abdeckung einschließlich fehlender Objekte nebeneinander ausweisen. „Lauf abgeschlossen“ und „fachliche Prüfung bestanden“ getrennt anzeigen.

**Abnahme:** Für dieses Projekt sind alle 520 Signale entweder begründet im bestätigten Umfang enthalten oder vor dem Start ausdrücklich ausgeschlossen. Für jedes eingeschlossene transportierte Signal gibt es Route, Nachricht und dekodiertes Sample. Ein bewusst entfernter Pfad macht den Preflight unvollständig. Agent und UI berichten dieselbe Abdeckung und denselben Prüfumfang.

## 3. P1 – Gateway-Zielnetz wird in der ausführbaren Simulation ausgelassen

**Live nachgewiesen:** Die zum Snapshot gehörende Capacity-Berechnung enthält **83 Netze**; die eingefrorene Simulation und die Runtime enthalten **82**. Das fehlende Netz ist genau `Infotainment_08-S01`, für das Capacity acht Routen und 13,32 % mittlere Last berechnet. Die acht Gateway-Routen verlaufen kanonisch von `Antriebsstrang_01-S01` über `System` zu diesem Zielnetz, unter anderem `Abgasnachbehandlung → Infotainment`.

Im Simulationskonfigurationsmodell werden die Zielteilnehmer dagegen dem Quellnetz zugeordnet. Damit ist das Zielsegment kein tatsächlich belastetes Laufzeitnetz. Gateway-Metadaten und rechnerische Verzögerungen ersetzen dessen eigenständige Übertragung/Arbitration nicht. Capacity und Simulation beantworten hier unterschiedliche Netzfragen.

**Codeursache:** `backend/engineering/routing/config_builder.py:112–141` bildet Gruppen nach dem Quellnetz und weist allen Endpunkten desselben Routeneintrags dessen Netz und Technologie zu; `:186` trägt wiederum das Quellnetz als einziges Kommunikationsnetz ein. `backend/simulator/universal_trace.py:417–424` addiert Gateway-Verzögerungen zur Route; dadurch entsteht kein zusätzlicher physischer Zielsegmentverkehr.

**Lösung:** Eine kanonische Route in explizite physische Segmente mit Quellport, Zielport, Netzwerk, Technologie und Gateway-Verknüpfung übersetzen. Die Segmente müssen dieselbe Ende-zu-Ende-ID behalten und Ereignisse kausal weiterreichen. Capacity und Runtime sollen dieselbe Segmentdarstellung verwenden. Gateway-Konvertierung benötigt einen tatsächlichen Ausgangstransport einschließlich Zielnetzlast und Fehlerweitergabe.

**Abnahme:** Alle acht betreffenden Ende-zu-Ende-Routen erzeugen nachvollziehbare Ereignisse auf beiden Bussegmenten. `Infotainment_08-S01` erscheint in Runtime und Trace. Eine Zielbus-Überlast oder ein Zielbus-Ausfall beeinflusst Empfang, Latenz und Status am Infotainment, während die Quellbusübertragung getrennt sichtbar bleibt. Referenztests müssen unterschiedliche Technologien und Bitraten an Ein- und Ausgang verwenden.

## 4. P1 – Vollständiger Nachrichtenausfall erhält PASS

**Isoliert reproduziert; im Live-Normallauf nicht aufgetreten:** Zwei verworfene Frames bei 0 und 100 ms, kein einziger erfolgreicher Empfang, Zyklus 10 ms und Timeout 20 ms führen zu `drop_rate=1.0`, `timeouts=0`, Status **PASS**. Die Probe ruft nur die Laufzeitauswertung auf; sie verändert keine Datenbank.

**Codeursache:** `backend/app/runtime_analysis.py:191–194` berechnet Zeitintervalle ausschließlich zwischen erfolgreichen Frames. `:221` zählt Timeout nur aus diesen Intervallen. Bei keinem erfolgreichen Empfang ist die Liste leer; auch eine lange Funkstille nach dem letzten erfolgreichen Empfang fehlt. `:266` berücksichtigt weder Verlust- noch Korruptionsrate für den PASS/FAIL-Status.

**Lösung:** Empfangsüberwachung ab erwartetem Erstempfang bis zum Ende des Bewertungsfensters modellieren. Erwartete und empfangene Nachrichten sowie Deadline/Timeout/Freshness unabhängig voneinander führen. Prüfergebnis aus tatsächlicher Zustellung und bestätigten Qualitätsanforderungen ableiten. Fehlerkampagnen brauchen zusätzlich „erwarteter Fehler erfolgreich ausgelöst“, ohne den Transportausfall als gesund zu deklarieren.

**Abnahme:** 100 % Verlust, verspäteter Erstempfang, Ausfall am Laufende, einzelne Verluste und korrupte Frames werden separat geprüft. Die bestehende Probe muss Timeout/FAIL oder eine explizite fehlende Evidenz ergeben; niemals PASS. Ein Fehler mit erwarteter Detektion darf die Kampagne bestehen lassen, während die betroffene Kommunikationsroute weiterhin als gestört ausgewiesen wird.

## 5. P1 – Golden Trace enthält weiterhin fehlerhafte Nutzdaten

**Isoliert reproduziert:** Bei einem Signal-Offset von +20 °C zeigt das Golden-Sample `value=100,3 °C`; dessen `payload_hex="43 06 00 00 00 00 00 00"` dekodiert jedoch zu **120,3 °C**, genau dem Fault-Wert. Auch `actual_value`, `received_value` und `fault_state=SIGNAL_OFFSET` bleiben im Golden-Sample erhalten. Damit widersprechen sich dekodierter Wert und Rohdaten innerhalb desselben Baseline-Ereignisses.

**Codeursache:** `backend/simulator/communication_simulator.py:278–291` kopiert die bereits durch Fehler beeinflussten Events, ersetzt einige Status-/Wertefelder, kodiert aber die Nutzdaten nicht neu. Da auch Zeitpunkte übernommen werden, erzeugt diese Konstruktion generell keinen unabhängigen fehlerfreien Transportlauf. Der Payload-Widerspruch ist durch einen konkreten Lauf belegt; weitere zeitliche/kausale Auswirkungen müssen bei der Korrektur geprüft werden.

**Lösung:** Golden-Lauf aus derselben eingefrorenen Konfiguration, demselben Seed und denselben externen Eingaben mit deaktivierten injizierten Fehlern berechnen. Fehlerlauf und Golden-Lauf über stabile fachliche Event-IDs korrelieren. Die Golden-Rohdaten müssen zu ihren dekodierten Werten passen. Diese Baseline auch für Zeit-, Verlust- und Gateway-Fehler verwenden; bloßes Entfernen von Fehlermarkierungen genügt nicht.

**Abnahme:** Jedes Golden-Signal stimmt mit dem aus seinen Rohdaten dekodierten Wert überein; keine Fault-Zustände oder Fault-Empfangswerte bleiben zurück. Referenzvergleich gegen einen unabhängig erzeugten Normal-Lauf mit gleichem Seed. Eigene Prüfungen für Offset, Skalierung, Verlust, Verzögerung, Duplikation und Gateway-Drop.

## Prüfnachweise und Grenzen

- [Reproduzierbares Prüfskript](verification/2026-09-09-workflow-sim-audit.py): sammelt nur GET-basierte Live-Evidenz und erzeugt lokale Gegenproben unter `.tmp/workflow-sim-golden-audit-20260909`.
- [Maschinenlesbare Evidenz](verification/2026-09-09-workflow-sim-audit.json): alle 20 falschen Jitter-PASS-Routen, vollständige Listen fehlender Nachrichten/Signale, fehlendes Zielsegment, Ausfallprobe und Golden-Payload-Widerspruch.
- [Gezielte bestehende Tests](verification/2026-09-09-workflow-sim-pytest.xml): 133 bestanden; zwei Tests benötigen trotz ihrer Mock-Konfiguration eine echte Addressing-Datenbank und scheiterten am für diese Prüfung bewusst unerreichbaren Port 1. Das sind hier Umgebungs-/Testisolationsfehler und kein Beleg für einen Live-Produktfehler. Der parallele Gesamtbericht führt eine separate vollständige Suite gegen eine isolierte Testdatenbank.
- Die drei für Timing, Ausfall und Golden relevanten Dateien `routing/config_builder.py`, `app/runtime_analysis.py` und `simulator/communication_simulator.py` wurden im übergreifenden Audit zwischen Workspace und laufendem Container verglichen: nach Zeilenenden-Normalisierung identisch. [Quellcodeparität](verification/2026-09-09-source-parity.json).
- Der Live-Lauf wurde gelesen, nicht neu gestartet. Er enthält Normalbetrieb und belegt keine erfolgreiche vollständige Fehlerkampagne oder längeren Fahrzyklus. Native PCAP-/Restbus-Exportvarianten wurden in dieser Teilprüfung nicht zusätzlich ausgeführt.

## Empfohlene Reihenfolge

1. Timing-Anforderungen unverlierbar durchreichen und den Runtime-Status bei fehlender Zustellung/fehlender Prüfung korrigieren. Bis dahin bestehende PASS-Raten nicht als fachliche Abnahme verwenden.
2. Gateway-Transport und gemeinsamen Simulationsumfang vervollständigen; anschließend den bestehenden Projektstand mit expliziter Abdeckung erneut berechnen und simulieren.
3. Unabhängige Golden-Baseline herstellen und Fehlerkampagnen über Sensor → Nachricht → Bus → Gateway → Empfänger → Auswertung prüfen.
4. Workflow, Results und Intelligence auf dieselben Bedeutungen für Laufabschluss, Abdeckung, Anforderungserfüllung und erwartete Fehlerreaktion umstellen. Der Agent muss genau diese gemeinsamen Verträge verwenden.
