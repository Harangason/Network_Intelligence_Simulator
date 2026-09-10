# Prüfung von Capacity & Timing – 10.09.2026

**Aktuelle Antwort zu den erneut zitierten 22,5 ms / 310,5 % / 405 %:** [Prüfung der acht Sender, Signalgrößen, aktuellen Last und Audi-Musterdateien](I:/PycharmProjects/My_first_Network_Simulator/docs/lin-reference-and-brake-bus-audit-2026-09-10.md). Diese Zahlen unten gehören zum historischen Snapshot, nicht zum heute gespeicherten 50-ms-Schedule.

**Einordnung nach Nutzerkorrektur:** Dieser Bericht prüft die gespeicherten Eingaben, einschließlich der vom Generator vorgegebenen 5-/10-ms-Zyklen. Er bestätigt nicht deren fachliche Richtigkeit. Inzwischen hat der Nutzer **mindestens 20 ms Sendeabstand** als Projektvorgabe bestätigt; außerdem sind Ereignis- und Anfrageverkehr gesondert zu modellieren. Die [ergänzte Bewertung und das Umsetzungskonzept](I:/PycharmProjects/My_first_Network_Simulator/docs/communication-timing-design-2026-09-10.md) berücksichtigen diese Vorgaben und die Protokollspezifikationen.

Die Überlastung ist unter den damals gespeicherten Bitraten und Zyklen rechnerisch real. Gleichzeitig gibt es Fehler in Rahmenlänge, Zählung physischer Übertragungen und Latenzberechnung. Die Nachrichtenansicht verwendet außerdem eine unvollständige Netzzuordnung.

Geprüftes Projekt: `network-project-20260910042736034-d11591d0`, „NIS Projekt 1“.
Geprüfter Capacity-Snapshot: `f68b49c3-af07-46d1-b856-f3b05e3b5d84`, Berechnungsmodell 2.2, 10.09.2026 um 14:17 Uhr MESZ.
Diese ursprüngliche Prüfung hat weder die Projektdaten noch die produktive Rechenlogik verändert. Die anschließend freigegebene Implementierung und die tatsächliche Projektkorrektur sind im [Verifikationsbericht zur automatischen Dimensionierung](I:/PycharmProjects/My_first_Network_Simulator/docs/communication-dimensioning-verification-2026-09-10.md) dokumentiert. Die folgenden Werte bleiben historische Auditwerte.

## Datenherkunft und Reproduktion

Die relevanten Quellversionen des gespeicherten Ergebnisses stimmen mit dem aktuellen Projekt überein: Engineering-Modell 30, Routing 74, Netzwerk-Editor 16, Parameter 105. Der Snapshot ist nicht als veraltet markiert. Er enthält 95 Netze, 386 freigegebene Routen, 461 physische Routensegmente, 311 Nachrichten und 725 Signale.

Eine erneute Berechnung mit unveränderten Parametern über den nicht speichernden Szenario-Endpunkt liefert dieselbe Übersicht und identische Last- und Latenzwerte für alle 95 Netze. Alle 461 Routensegmente sind über physische Pfade aufgelöst. Eine unabhängige CPU-Summierung der vorhandenen Lastbeiträge stimmt bis auf weniger als 0,000000000001 Prozentpunkte mit der CUDA-Aggregation überein. CUDA ist aktiv; die erkannten Fehler liegen in den fachlichen Rechenansätzen.

Die auffälligen Netze sind tatsächlich als **LIN mit 19.200 bit/s** gespeichert. Das `can-fd` in einigen technischen IDs ist ein Überbleibsel. Beispiel Bremsregelung: Die Versionshistorie eines beteiligten physischen Anschlusses zeigt am 10.09.2026 um **09:56:38 Uhr MESZ** den Wechsel von CAN-FD auf LIN durch den Anwendungspfad `network-editor-bus-change`. Die technische Netzreferenz blieb bestehen. Das belegt den Änderungspfad, aber nicht die Identität der bedienenden Person.

## 1. LIN-Rahmenlänge unterschätzt die Buslast

In [calculators.py](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/capacity/calculators.py:60) wird `34 + 10 × Nutzdatenbytes` berechnet. Dabei fehlt das Prüfsummenbyte einschließlich Start- und Stoppbit.

Die nominale Rahmenlänge lautet **34 + 10 × (Nutzdatenbytes + 1)**. Bei zwei Nutzdatenbytes sind das 64 statt 54 Bit beziehungsweise 3,333 statt 2,8125 ms bei 19.200 bit/s. Diese Rechnung enthält noch keine zusätzlichen Antwort-, Byte- oder Rahmenabstände. Quelle: [Microchip AN1099, Seite 5, LIN-Rahmenzeiten](https://ww1.microchip.com/downloads/en/Appnotes/01099A.pdf).

Unabhängige Gegenrechnung bei den damaligen, noch nicht gegen die 20-ms-Projektvorgabe geprüften Zyklen. Die erste Spalte verwendet jetzt die tatsächlichen Busanzeigenamen; historische IDs werden nicht als Bustechnik dargestellt:

| Busanzeigename, Typ LIN | Damals angezeigte mittlere Last | Nur Prüfsummenbyte korrigiert, alte Zyklen |
| --- | ---: | ---: |
| Bremsregelung LIN 01 | 270,00 % | **320,00 %** |
| Daempferregelung LIN 01 | 225,00 % | **266,67 %** |
| Motorsteuerung LIN 06 | 154,69 % | **183,33 %** |
| Elektromotorsteuerung LIN 03 | 126,56 % | **150,00 %** |
| Batteriemanagement LIN 03 | 73,13 % | **86,67 %** |
| Motorsteuerung LIN 05 | 70,31 % | **83,33 %** |

Die Übertragungen dieser sechs Zweige sind jeweils eindeutig; der nachstehende Fehler der Mehrfachzählung beeinflusst diese Gegenrechnung nicht. Werte über 100 % bedeuten, dass die geforderten Übertragungen mehr Buszeit benötigen, als verfügbar ist.

Für Bremsregelung waren acht Nachrichten mit jeweils zwei Nutzdatenbytes gespeichert: vier alle 5 ms, eine alle 10 ms und drei alle 50 ms. Die fünf schnellen Vorgaben widersprechen der inzwischen bestätigten Projektregel. Aus den alten Eingaben ergibt sich:

`3,333333 ms × (4/5 ms + 1/10 ms + 3/50 ms) × 100 = 320 %`.

Mit mindestens 20 ms Abstand, unter Beibehaltung der langsameren 50-ms-Nachrichten, beträgt dieser nominale Bedarf **103,33 %**. Das ist weiterhin zu viel für diesen einen LIN-Bus; zusätzliche Sendeplatzreserven sind darin noch nicht enthalten.

Die fehlerhafte Formel steht auch in der [Vorauslegung des Projekt-Wizards](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/lib/agent/engineering-specification.ts:320). Der Simulator verwendet denselben Backend-Rahmenschätzer. Eine Korrektur muss diese Pfade gemeinsam erfassen.

## 2. Mehrere Empfänger führen zu mehrfach berechneter Buslast

Die [Aggregation](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/capacity/service.py:467) summiert Routensegmente. Auf einem gemeinsam genutzten Bus muss hingegen jede tatsächliche Nachrichtensendung einmal gezählt werden, auch wenn mehrere Geräte sie empfangen.

Im aktuellen Ergebnis wurden **54 Gruppen** mit identischer Nachricht, physischem Senderanschluss, Bus, Protokoll, Bitrate, Nutzdatenlänge und Zyklus gefunden: 46 auf LIN und acht auf CAN-FD. Diese werden pro Empfängerroute mehrfach angerechnet.

Beispiel: „Radarverarbeitung LIN IO Befehl“ geht über denselben LIN-Anschluss alle 100 ms an Schaltausgang und Stellglied. Beide Routen referenzieren dieselbe kanonische Nachricht. Die Berechnung addiert zweimal 3,3333 %. Mit vollständigem LIN-Rahmen wären hier einmal 3,8542 % nominal anzurechnen. Weitere acht gleichartige Gruppen auf Ethernet wurden nicht als bestätigte Doppelzählungen gewertet, weil dort Unicast-, Multicast- und Portbelegung gesondert zu unterscheiden sind.

Dieser Fehler überschätzt manche Netze, während das fehlende Prüfsummenbyte alle LIN-Rahmen unterschätzt. Eine pauschale prozentuale Korrektur des Gesamtergebnisses wäre deshalb falsch.

## 3. „Worst E2E 4,831 ms“ ist kein belastbarer Worst-Case-Wert

Die [Wartezeitberechnung](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/capacity/service.py:327) verwendet nur den Lastbeitrag der einzelnen Route. Die gesamte Buslast wird erst später aggregiert. Zusätzlich begrenzt der [Warteschlangenschätzer](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/capacity/calculators.py:89) die Auslastung rechnerisch auf 99 %.

Konkret entsteht der Spitzenwert aus „RearRightBrakePressure → Bremsregelung“: 2,8125 ms Sendezeit, 1,808036 ms geschätzte Wartezeit, zweimal 0,1 ms Verarbeitung und 0,01 ms Ausbreitung. Die Wartezeit nutzt die eigene Routenlast von 56,25 %, obwohl der gesamte Bus bereits nach der bisherigen Rechnung 270 % benötigt. Trotzdem erhält die Route `latency_status: PASS`.

Bei dauerhaft mehr angeforderter als verfügbarer Buszeit ist kein endlicher Verzögerungsgrenzwert für alle geforderten Sendungen belegbar. Auch unterhalb dieser Grenze ist eine mittlere Warteschlangenschätzung kein nachgewiesener Worst Case. Erforderlich sind die gesamte Busbelegung und ein zum Bus passendes Scheduling-Modell; nicht erfüllbare Zeitpläne müssen ausdrücklich als solche ausgewiesen werden.

## 4. Die Nachrichtenansicht löst das physische Netz nicht korrekt auf

Die [Message-Metriken](I:/PycharmProjects/My_first_Network_Simulator/backend/engineering/capacity/service.py:720) lesen die Konfiguration der logischen Kommunikationsschnittstelle. Der physische Anschluss der Nachricht und dessen Netzreferenz werden hier nicht berücksichtigt.

**311 von 311 Nachrichtenzeilen** enthalten deshalb einen allgemeinen Protokollnamen als Netzkennung, obwohl ein konkreter physischer Bus hinterlegt ist. Die Protokolle selbst stimmen nach Normalisierung der Schreibweise überein. Netzspezifische Parameter können auf diesem Pfad dennoch fehlen. Die Netz- und Routenübersicht verwendet dagegen die aufgelösten physischen Segmente; dieser Fehler erklärt also nicht die hohe Last der Übersicht.

## 5. Anzeige mischt unterschiedliche Bewertungsgrundlagen

Die Zahlen des Screenshots lassen sich mit der bestehenden, fehlerhaften Rahmenformel nachvollziehen:

- Mittlere Last Bremsregelung: 270 %.
- Peak: `270 × 1,15 = 310,50 %`.
- Reserve gegenüber mittlerer Last: `100 − 270 = −170 %`.
- Burst: `270 × 1,50 = 405 %`; diese Last bestimmt hier den Status.

Das sichtbare Eingabefeld „Burst-Faktor 1,25“ gehört zum Szenario. Die gespeicherte aktuelle Berechnung verwendet **1,50**. [Der Button „Aktuell berechnen“ übergibt diesen Szenariowert nicht](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/capacity-workbench.tsx:85). Die Oberfläche muss aktive Parameter und Szenarioannahmen eindeutig ausweisen und die Bezugsgröße der Reserve nennen.

Die „27 Hinweise“ entsprechen **19 Backend-Befunden plus acht zusätzlichen Netz-Hinweisen** der Oberfläche. Sie stehen nicht für 27 unabhängige Fehlerursachen. Die Ergänzung erfolgt in [capacity-workbench.tsx](I:/PycharmProjects/My_first_Network_Simulator/frontend/src/components/capacity-workbench.tsx:304).

## Erforderliche Korrekturen

1. LIN-Rahmenlänge in Berechnung, Wizard und Simulation konsistent korrigieren; nominale Dauer und reservierte Zeit eines Sendeplatzes unterscheiden.
2. Physische Sendungen aus Nachricht, Senderanschluss und Bus ableiten. Empfängerreferenzen getrennt führen; Ethernet nach tatsächlichem Übertragungsmodus behandeln.
3. Latenzen anhand des gesamten Busverkehrs und Scheduling-Verfahrens bewerten. Überlastete Zeitpläne dürfen keinen scheinbar gültigen Worst-Case-Wert liefern.
4. Nachrichten-, Routen- und Netzansicht über dieselbe physische Zuordnung und dieselben wirksamen Parameter rechnen lassen.
5. In der Oberfläche Busanzeigenamen, aktive Berechnungsparameter, mittlere Last, Peak, Burst und Reserve nachvollziehbar kennzeichnen; Hinweise nach Ursache gruppieren.
6. Berechnungsversion erhöhen, bestehende Ergebnisse als veraltet markieren und neu berechnen. Regressionen müssen unter anderem Prüfsummenbyte, mehrere Empfänger, unterschiedliche Nachrichtenzyklen, Busparameteränderung und Überlast abdecken.

Eine fachliche Anpassung von Bustypen oder Zykluszeiten ist davon getrennt zu entscheiden. Insbesondere dürfen Zyklen nicht allein für einen grünen Status verlängert werden.

## Prüfartefakte

- [Gesicherter Eingabestand](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/capacity-audit-before.json)
- [Unabhängige Gegenrechnung](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/capacity-independent-audit.json)
- [Zusammengefasste Reproduktionsprüfung](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/capacity-audit-verification.json)
- [Historie des geprüften physischen Anschlusses](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/capacity-audit-port-history.json)
- [Ausführbares Prüfsystem](I:/PycharmProjects/My_first_Network_Simulator/backend/runtime/capacity-audit-verify.py)
