# Korrekturen zum 50-Szenarien-Prüfbericht

Stand: 16.09.2026. Korrekturen umgesetzt, Release-Gate PASS und geprüftes Image veröffentlicht.

## Änderungen

| Befund | Korrektur | Nachweis |
|---|---|---|
| Verlust konkreter Geräte und Anschlüsse | Abschnittsbezogene Inventarerkennung, explizite Stückzahlen und Gerätetypen, getrennte Kommunikationszuordnungen. Mehrdeutige Buslisten werden nicht willkürlich auf Geräte verteilt. | `test_industry50_corrections.py`, `test_industry_intake.py`, Entwurfsregressionen |
| Fehlende zusätzliche Rechner | Edge-, HPC- und Auswerte-Rechner werden zusätzlich zum Controllerumfang gezählt; Geräteidentitäten bleiben erhalten. | S07: 2, S11: 3, S20-A: 56 Controller/Compute-Knoten; korrigiertes gemeinsames Testfixture |
| Falscher Ablauf bei Signalprüfung | Prüfabsicht und ausgewähltes kanonisches Signal führen zum Lese-/Prüfwerkzeug, nicht zur Signalneuerzeugung. PHYSICAL_SCALAR wird auch im Encoding-Audit numerisch geprüft. | Echter MCP-/SQL-Test: MotorRPM 0–5000 rpm, Faktor 50, 4 Bit erzeugt 7-Bit-Bedarf und Fehlerbefund |
| Timeout bei Anbindungsfrage | Explizite Anbindungsabfrage liest Objekt, Hardware, Ports und Netze deterministisch; ein alter Goal wird nicht fortgesetzt. | Regression für den originalen S23-Prompt |
| Mehrteiliger Auftrag falsch zerlegt | Der Funktionsname endet vor dem Folgeauftrag; Simulation und Trace-Analyse bleiben als beauftragte Folgeschritte erhalten. | Originaler S30-Prompt und bestehende Goal-Folgeausführungstests |
| Fehlender Architekturmodus | Schnellwahl überträgt CREATE_ARCHITECTURE; weitere Schnellwahlen übertragen ebenfalls ihren Modus. Kontext enthält weiterhin die tatsächliche Auswahl und Projektbindung. | Envelope-/Modusregression und TypeScript-Prüfung |
| Unpassende Ventilauswahl | Ventilbefehle erscheinen nur bei tatsächlich als Ventil beschriebenen Aktoren. | Komponentenänderung und Frontend-Prüfung |
| Ungültige Antwortkarten | Echter HTTP-Verbindungslauf mit kanonischer Datenbank, MCP, gespeicherter Auswahl und COMPLETE wird gegen Backend- und Frontend-Schema geprüft. Aktuell kein Kartenfehler reproduziert; Validierungsfehler werden detailliert protokolliert. | `test_real_chat_connection_stream_keeps_every_response_valid` |
| MCP-Fehler und Metadaten | TOOL_NOT_FOUND, NOT_SUPPORTED und TOOL_TIMEOUT werden strukturiert zurückgegeben. Kein blinder Retry nach möglicherweise bereits abgeschlossener Mutation. Output-Schema, Version und Permission bleiben erhalten. | Echter MCP-Vertragstest; Transporttimeout ausdrücklich injiziert |
| Unpassende Finding-Antwort | Gespeicherter Befund wird mit derselben ID und Entscheidung dargestellt. Kanonisch normalisierte Hardware-Namen werden mit passendem Gerätetyp aufgelöst. | MCP/SQL-Lifecycle: Risikoakzeptanz und NEEDS_REVIEW nach Modelländerung |

## Testumfang und Grenzen

- SQL-Tests ausschließlich mit kurzlebigen, isolierten Postgres-Datenbanken; keine Produktdaten als Testziel.
- Abschließende Backend-Suite: **1.784 bestanden, 2 übersprungen**, einschließlich der ergänzenden Scalar-/Hardware-Namenskorrekturen.
- **388 Frontend-Tests und TypeScript-Prüfung bestanden** auch auf dem endgültigen Stand.
- **67 Browser-E2E-Tests bestanden**: einschließlich der 40 Inventarfälle, Neun-Schritte-Durchläufen mit Raspberry Pi/I²C und Modbus RTU, des bestätigten großen 50/250/250-Auftrags, Reload/Neustart und AMEND nach Modellfreigabe.
- [Auswertung der 40 Original-Anforderungen](industry50-corrected-intake.json): Parserumfang, offene Angaben und explizite Anschlüsse; keine behauptete vollständige Workflow-Ausführung.
- Der erste Gate-Durchlauf wird durch nachträgliche, aus echten Integrationsprüfungen abgeleitete Korrekturen ungültig und nicht veröffentlicht. Eine neue unveränderte Quelle muss das vollständige Gate bestehen.
- S28 war laut Ausgangsbericht ein unvollständiges Testfixture, kein nachgewiesener Produktfehler. Eine vollständige Queue-Growth-Kausalkette ist hier nicht zusätzlich als bestanden belegt.
- Offene Architekturentscheidungen der B-Fälle bleiben entsprechend Nutzeranweisung offen. Die Änderungen bedeuten keine vollständige Freigabe aller 50 Szenarien oder aller neun Schritte für jede denkbare Industrie.
- Der S29-Test beginnt mit einem explizit gespeicherten Befund. Er belegt Bewertung und Revisionswechsel, nicht die vorgelagerte automatische Topologieerkennung.

## Release

- Vollständige PASS-Receipt: [9bf5ec255659](../../backend/test-output/release-gates/9bf5ec255659/receipt.json).
- Alle sieben Gate-Prüfungen erfolgreich: TypeScript, Frontend-Tests, Backend-Tests, Produktionsbuild, Browser-E2E, kleiner und großer HTTP-Wizard.
- Build: `c16f447ee305`.
- Veröffentlichtes und erneut geprüftes Image: `sha256:366382afb7c34efeb2b2c689d7016ad752130368c195e264e3fff2cda1dfbde2`.
- Nach Deployment: `/api/ready` meldet `ready`, Datenbank und Speicher verfügbar; Frontend-Build und Container-Image stimmen mit der PASS-Receipt überein.
- Das PowerShell-Startskript scheiterte vor der Änderung an einer Ausgabeumleitung. Deployment erfolgte daraufhin erfolgreich direkt über `scripts/deploy-verified-release.py` mit der PASS-Receipt und den vorhandenen Container-/GPU-Einstellungen.
- Kurzlebige Testcontainer sind entfernt; Produktprojekte wurden nicht als Testdaten verwendet.
