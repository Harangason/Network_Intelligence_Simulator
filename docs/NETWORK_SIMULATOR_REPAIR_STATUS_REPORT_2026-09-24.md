# Network Simulator – vollständiger Standbericht der Reparaturphase

Stand: 24.09.2026, 16:02 MESZ. Der gewünschte Endtermin 08:00 Uhr am selben Tag war bei dieser Bearbeitung bereits überschritten. Der Bericht beschreibt den tatsächlich geprüften Stand; er ist kein nachträglich umgedeuteter vollständiger Kampagnenlauf.

## Auftrag und Entscheidungsgrundlage

Der Nutzer beauftragte, Fehler des letzten Laufs zu beheben und den Testumfang begrenzt erneut auszuführen. Für den zuletzt genannten Lauf galt „nur Run 1“. Das Masterdokument ist eine Prüfquelle, keine eigenständige Chat-Anweisung. Bei Konzeptänderungen wurden Entscheidungen eingeholt: unvollständige Anschlüsse und Stellbefehle als prüfbare Vorschläge, neue EA-01-ECU aus Projektfakten als Review-Entwurf, Positionssensor/Servoantrieb 1↔1 und 2↔2 plus CANopen-Anfrage/Antwort als prüfbarer Entwurf, und S04-A-ThermalStatus ohne bestätigten externen Empfänger intern mit optionalem Export.

Kanonisches Projekt: `I:\PycharmProjects\My_first_Network_Simulator`. Die Produktdatenbank wurde in dieser Reparaturphase nicht für SQL-Tests verwendet. Browserprüfungen liefen auf eigenen Wegwerfprojekten und isolierten Entwicklungsstacks. Das bereits früher angelegte produktive S03-B-Projekt `nis-s03-b-review-20260924-4153cecb` wurde nicht verändert.

## Eingefrorener vollständiger Run 1

Der letzte vollständige 95-Fall-Lauf bleibt unverändert bei **10 PASS, 35 FAILED, 50 BLOCKED**. Davon waren 35 Wizard-Fälle fehlgeschlagen, 35 Wiederverwendungsfälle mangels vollständiger Quellmodelle blockiert und 15 EA-Unterfälle ohne geprüfte ausführbare Adapter/Fixtures blockiert. Die Einzelmatrix und Belege stehen in `NETWORK_SIMULATOR_SINGLE_RUN_REPORT_2026-09-24.md` und `.tool-checker/state/campaigns/nis-ea-20260924-single-run/run-1/`. Kein zweiter vollständiger Lauf wurde eröffnet.

## Umgesetzte Reparaturen

1. Der Wizard-Testadapter liest die aktuellen Geräte- und Befehlsfelder auch in eingeklappten Clustern. Die früheren acht Fragebogenstopps wurden damit technisch adressiert.
2. Fehlende Geräteanschlüsse und Stellbefehl-Kodierungen werden als begründete, ausdrücklich zu übernehmende Kandidaten angezeigt. Unbekannte fachliche Werte werden nicht als bestätigte Fakten ausgegeben.
3. Der S04-A-Wizard übernimmt 19,2 kbit/s LIN, 100 Mbit/s Ethernet, 500 ms für vier Temperatursensoren und 250 ms für drei Lüfterstatusmeldungen. Die zusätzlich vorgeschlagene 250-ms-Befehlsrate ist als Kandidat markiert; sie stammt nicht aus einer bestätigten Befehlsvorgabe.
4. Explizites CANopen bleibt in kanonischen Interfaces erhalten. Der physische CAN-Layer wird aus dem Technologieprofil für Ports, Routen und Preflight verwendet. So bleibt die CANopen-Anwendungsfähigkeit für Anfrage/Antwort sichtbar, ohne eine fremde physische Technologie einzuführen.
5. Controller- und Gatewaystatus ohne bestätigten Empfänger bleiben intern. Nur ausdrücklich deaktivierte interne Zustände ohne aktuelle Transportabsicht werden nachvollziehbar aus dem Bus-Transportscope genommen. Ein später entworfener Export bleibt bis zu einer bestätigten Route prüfpflichtig.
6. EA-01 erzeugt einen validierten ECU-Review-Entwurf aus vorhandenen Projektfakten. Er zeigt Positionssensor1↔Servoantrieb1, Positionssensor2↔Servoantrieb2 und eine 30.000-ms-CANopen-Anfrage/Antwort als Kandidaten. CANopen-Objektverzeichnis, Kodierung, Antwortzeit und Fehlerverhalten bleiben offen.
7. Die früheren Vertragsfehler und fünf veralteten Routenerwartungen in den Backendtests wurden korrigiert.

Datei- und Befunddetails stehen im `NETWORK_SIMULATOR_REPAIR_LEDGER_2026-09-24.md`.

## Gezielte Nachweise nach Reparatur

| Prüfung | Ergebnis | Grenze |
| --- | --- | --- |
| Isolierte Backendregression für Coverage, Wizardgenerierung und Kommunikation | **101/101 PASS** | Kein 95-Fall-Kampagnenlauf |
| Isolierte EA-/Hardware-Backendregression | **16/16 PASS** | Prüft Entwurf und Runtime, nicht vollständige EA-01-Abfrage |
| Frontend-Spezifikation und Vorschlagslogik | **76/76 PASS** | Gezielter Frontendumfang |
| S03-A, vollständiger isolierter Wizard mit Persistenz, Simulation und Trace | **PASS** | Ein Quellfall, nicht S03-B oder EA-01 |
| S03-B, frisches isoliertes Projekt | **PASS** | Separater Reparaturbeleg, eingefrorener Run-1-FAIL bleibt bestehen |
| S04-A, vollständiger isolierter Wizard mit Persistenz, Simulation und Trace | **PASS** | Interner Status, optionaler Export nicht abgenommen |
| S06-A, vollständiger isolierter Wizard mit Persistenz, Simulation und Trace | **PASS** | Review-Entscheidungen im Testskript, kein unbedingter Gerätefakt |
| S01-A, isolierte Kontrollprobe | **PASS** | War bereits im Run 1 PASS |
| EA-01 auf vollständigem isolierten S03-A-Fixture | **Review-Entwurf validiert** | Sechs Änderungen, elf Annahmen, keine Übernahme und keine Modellrevision |

Belegverzeichnisse unter `.tool-checker/runs/ea-campaign-20260924-repair/`: `s03-a-20260924135046`, `s03-b-20260924135550`, `s04-a-20260924134947`, `s06-a-20260924135142`, `s01-a-20260924135450` und `ea01-ui-probe-20260924140021`. Der letzte EA-01-Probe verwendet das neuere Kandidatenimage und den eigenen S03-A-Fixture `s03-a-20260924140021`. Das neueste Entwicklungsimage steht im PREPARED-Receipt `prepare-ea01-draft/6aa1954e78d9/receipt.json`; PREPARED ist ausdrücklich kein Release-Gate-PASS.

Ein paralleler S03-A/S04-A-Probe lieferte einmal einen Timeout im Testadapter vor der Eingabe. Der anschließende einzelne S03-A-Probe auf demselben Produktstand bestand. Der Timeout wird nicht als reproduzierbarer Produktfehler und nicht als zusätzlicher Kampagnen-PASS gewertet.

## Noch offen und Freigabestatus

- Die übrigen Wizard-Quellfälle wurden auf dem reparierten Stand nicht einzeln abgenommen. Die 35 Wiederverwendungsfälle S26–S60 benötigen vollständige Quellmodelle und eigene Browser/Core/Persistenznachweise.
- Die 15 EA-Unterfälle benötigen geprüfte ausführbare Adapter und fallbezogene Fixtures. EA-01 ist fachlich noch offen: Der Review-Entwurf enthält keine ausführbaren CANopen-Anfrage-/Antwortobjekte, Route, Kapazitätsrechnung, Antwortzeit- und Preflight-Abnahme. `READY_FOR_REVIEW` ist kein EA-01-PASS.
- S04-A-ThermalStatus bleibt gemäß Nutzerentscheidung intern. Der optionale Ethernet-Export ist noch kein bestätigter Modellbestandteil. Die vorgeschlagene 250-ms-Befehlsrate braucht fachliche Bestätigung.
- Der vollständige 95-Fall-Wiederholungslauf ist wegen dieser offenen Reparaturen gemäß Tool-Checker-Gate noch nicht gestartet. Die eingefrorenen 10/35/50 sind weiterhin das einzige vollständige Rundenergebnis. Es liegt weder ein Release-Gate-PASS noch eine Bereitstellung des reparierten Images auf die Produktinstanz vor.

## Schlussbewertung

Die Ursachen der konkret untersuchten Wizard-Blockaden sind im isolierten Stand behoben; S03-A/B, S04-A und S06-A bestehen gezielt. Die Gesamtsuite ist **nicht abgenommen**. Für eine belastbare Freigabe müssen die übrigen Quellfälle und EA-Unterfälle ausführbar und repariert sein, danach ist genau der autorisierte vollständige Wiederholungslauf auf einem festgehaltenen Image erforderlich. Ein erfolgreicher Entwicklungsstack oder sichtbare Wizardkarte ersetzt diesen Nachweis nicht.
