# Engineering-Agent: Umsetzung und nachgewiesener Umfang

Stand: 2026-09-15. Umsetzung der Freigabe zum Audit
`engineering-agent-audit-2026-09-15.md`. Release-Gate `3990c4575c55` ist PASS;
das exakt geprüfte Produktionsimage wurde am 2026-09-15 ausgeliefert.
Abschluss und Nachweise: [ENGINEERING_AGENT_RELEASE_2026-09-15.md](ENGINEERING_AGENT_RELEASE_2026-09-15.md).

## Bereits umgesetzt

- REAL_PROJECT verwendet keine Hardware-Auffüllung aus Beispielkatalogen.
  Branche und Anschlusstechnologie werden nicht pauschal Automotive/CAN-FD.
- Persistierter Projektentwurf mit Herkunft, Revision, offenen Entscheidungen,
  AMEND/RESOLVE und idempotenten Operationsbelegen.
- Chat und verknüpfter Wizard bearbeiten denselben Entwurf; ein gemeinsamer
  Adapter erzeugt den Modellauftrag. Veränderte Entwurfsrevisionen sperren alte
  Vorschläge. Bereits angewendete Operationen bleiben wiederholbar.
- Chat kann einen Modellvorschlag erzeugen, menschlich prüfen/freigeben und
  tatsächlich übernehmen, ohne den Wizard zu öffnen. Ein Entwurf kann ein neues
  Projekt erhalten; das Ursprungsprojekt bleibt erhalten.
- Aktionsfähige Chatantworten werden vor Veröffentlichung serverseitig gespeichert.
  Ein schneller Reload hängt nicht mehr ausschließlich an der verzögerten
  History-Speicherung im Browser.
- Generische Modellanlage über `create_objects_via_proposal`, mit Schemaauskunft,
  Feldprüfung und bestehendem Review/Apply. Keine Governance-Felder aus Modelltext.
- Hierarchiezuordnung über `plan_structure_assignments`; gemeinsame fachliche
  Auflösung mit dem Structure Wizard, Validierung und menschlicher Review.
- Fähigkeitenkatalog unterscheidet Vorschlag, autorisierte Ausführung, gespeicherte
  Bewertung, Analyse und noch notwendige UI-Übernahme. Navigation gilt nie als
  Modelländerung. Diese Informationen erreichen auch den Reasoner.
- Funktionsgenerator verlangt vorhandene Hardware oder ausdrücklich benannte neue
  Hardware einschließlich Anschlusstechnologie und Statuszyklus.
- Laufender Wizard übernimmt eine neuere gemeinsame Draftrevision mit AMEND im
  selben Lauf; ein Reload erhält die Draftreferenz. Datenantworten im Chat senden
  die persistierte Nachrichten-ID bereits im Streamstart, damit Reload keine
  zweite Antwort mit derselben Aktion erzeugt.
- Strukturtransfer verwendet den gemeinsamen Review/Apply-Pfad. Persistierte
  Herkunft und Elternzuordnung verhindern erneute Anlage bereits übertragener
  Objekte, ohne fachlich fremde Objekte anhand ähnlicher Namen zusammenzuführen.
- Explizit entfernte Draftgeräte bleiben bei AMEND entfernt; fehlende Owner werden
  erneut ausgewiesen. Gemischte benannte Sensorarten und Gateway-Owner sind geprüft.
- Fehlervorschläge können als Szenario im Agenten geprüft und übernommen werden.
  Technische Prüfung vergibt keine Freigabe; erst menschliches Review und Apply
  aktivieren das gespeicherte Szenario. Dies startet noch keinen Simulationslauf.
- Engineering-Dateien verwenden denselben Parser und Feldadapter wie der UI-Import.
  Vorschau, Vorschlag, menschliches Review/Apply und wiederholbarer Import sind
  implementiert; Export liefert den tatsächlichen Projektinhalt bzw. Download.
- Draftversion 1 wird unter Beibehaltung von ID und Revision auf Version 2 gelesen;
  unbekannte zukünftige Versionen werden nicht überschrieben.
- Auch native Wizardaufträge erhalten einen gemeinsamen versionierten Entwurf.
  Der WIZARD_V2-Adapter bewahrt den vollständigen bestätigten Quellauftrag samt
  Graph, Anschlüssen und HMI-Angaben. Ergänzungen lassen sich im selben Lauf
  ausdrücklich übernehmen. Einzelne strukturierte Fachfelder werden weiterhin
  über die bestehenden Wizard-/Fachbefehle geändert, nicht in ein vereinfachtes
  Geräteformular umgedeutet.
- Konflikte erhalten die Eingaben als Kopie. Ein verlorener Speicherresponse wird
  mit derselben Operations-ID wiederholt; ein echter Containerneustart erhält den
  gespeicherten Entwurf. Ausgeschlossene Geräte werden nicht positiv erkannt;
  mehrere Branchenalternativen bleiben eine offene Entscheidung.
- Vollständige Projektpakete können über einen menschlich geprüften Vorschlag in
  ein neues Projekt übernommen werden. Der bestehende Importdienst ordnet IDs und
  Beziehungen neu zu. Importierte Auftragskontexte bleiben Historie; keine aktive
  Ausführung oder noch nicht angewendete Freigabe wird aus Dateiinhalten aktiviert.
- Der reale MCP-Zugang erhält bei Draftänderungen die Unterscheidung zwischen
  ausgelassenen Feldern und ausdrücklich geleerten Werten. Löschvorschläge mit
  Auswirkungsanalyse sind planbar; tatsächliches Löschen bleibt Review/Apply.

## Tatsächliche Prüfbelege

SQL-Tests liefen ausschließlich mit `scripts/run-isolated-tests.py`.
Browserfälle liefen gegen einen getrennten Container mit zufälligem Port,
eigener Datenbank und eigenem Runtime-Volume.

| Umfang | Ergebnis / Beleg unter `backend/test-output` |
| --- | --- |
| Hardware, Domäne, MCP und Chatregressionen | 78 bestanden; `agent-explicit-hardware-tests-2.log` |
| Fähigkeitenvertrag und generische Modellanlage | 22 bestanden; `agent-capability-contract-tests.log` |
| Strukturzuordnung UI/Agent, veraltetes Review, Apply-Wiederholung | 1 bestanden; `agent-structure-parity-tests-2.log` |
| Fehlenden Controller über Chat und alternativ Wizard ergänzen, Reload, Geräteaufgaben und Owner speichern | 2 echte Browserfälle bestanden; `agent-missing-controller-browser-3/report.json` |
| Chatmodell Raspberry Pi / 3 Temperaturen / 2 Ventile sowie neues Projekt | Einzelne echte Browserfälle bestanden; `agent-draft-browser-c/report.json` enthält zusätzlich damalige Intake-Testfehler, kein Gesamt-PASS |
| Korrigierte Intake-Fälle | 2 bestanden; `agent-intake-browser-c2/report.json` |
| Gemeinsamer Entwurf über tatsächlichen Wizard-Review/Apply | 1 bestanden; `shared-draft-browser-c/report.json` |
| Tatsächlicher lokaler Qwen-Aufruf, 3 Sensoren / 5 Ventile | 1 bestanden; `agent-live-model-tests.log`; kein vollständiger LLM-Projektlauf |

Zusätzliche Prüfungen nach Kandidat C:

- Kandidat E: alle sieben neuen Browserfälle bestanden, einschließlich echter
  Chatmodellübernahme, Projektanlage, Reload und AMEND mit erneuter Modellübernahme
  im selben Wizardlauf (`agent-browser-e/report.json`).
- Gesamte Backend-Zwischenprüfung: 1611 bestanden, 2 übersprungen
  (`agent-upgrade-backend-sweep-2.log`). Da parallel am Arbeitsstand weitergearbeitet
  wurde, ersetzt diese Prüfung keinen unveränderlichen Releasebeleg.
- 43 gezielte SQL-Regressionsprüfungen bestanden: Draft, Gateway-Owner, Entfernung,
  Strukturtransfer und Fehlerszenarien (`agent-draft-transfer-fault-regressions.log`).
- Branchenerkennung: 19 Tests bestanden (`agent-negative-industry-tests.log`).
- Frontendtypprüfung nach den letzten Editoränderungen bestanden
  (`agent-draft-f-types.log`).

- Kandidat H: elf neue Browserfälle bestanden (`agent-browser-h/report.json`).
- Kandidat I: zwölf neue Browserfälle sowie der bestehende AMEND-Recovery-Fall
  gemeinsam bestanden, einschließlich nativer Wizard-/Draftübernahme im selben
  Lauf (`agent-browser-i/report.json`, 13 bestanden). Dieser Kandidat ist isoliert
  und nur PREPARED, kein Release-PASS.
- 42 gezielte Backendtests für den gemeinsamen nativen Wizard, Revisionen,
  bestehende Wizardkommandos und Inventarintegrität bestanden
  (`agent-structured-draft-tests-2.log`).
- 341 Frontendtests und TypeScript-Prüfung bestanden
  (`agent-structured-frontend-tests.log`, `agent-structured-draft-types.log`).
- 27 Tests für Kaltstart, vollständigen Toolkatalog, Import und Fehlerszenarien
  bestanden (`agent-cold-start-tests-2.log`). Ein zuvor fehlgeschlagener isolierter
  Kandidat G deckte einen Importreihenfolgefehler auf; die Kaltstartregression
  prüft jetzt den vollständigen tatsächlichen Katalog in einem frischen Prozess.

## Abschließende gemeinsame Prüfung und Auslieferung

- Unveränderlicher Kandidat R1: 1645 Backendtests bestanden, 3 übersprungen;
  341 Frontendtests bestanden, TypeScript und Produktionsbuild bestanden.
- Alle 17 Browser-E2E-Fälle bestanden, keine übersprungenen oder instabilen Fälle.
  Zusätzlich kleiner und großer HTTP-Neun-Stufen-Durchlauf bestanden.
- Großer HTTP-Lauf: 838/838 Routen, 653/653 Nachrichten und 1404/1404 Signale
  nachgewiesen; Conformance PASS. Fachliche Warnungen bleiben sichtbar.
- Lieferumfang gegen vorherigen PASS abgegrenzt; 101 geänderte Dateien,
  keine fremden Landing-Animationen. Quell- und Prüfmanifest unverändert.
- Datenbankbackup erstellt, exakt geprüftes Image ausgeliefert und 18
  Bestand-/Konfigurations-/Erreichbarkeitsprüfungen bestanden.
- Belege: `backend/test-output/agent-final-release-gates/3990c4575c55/`.

## Grenzen des nachgewiesenen Funktionsumfangs

- Draft v1/v2 und bestätigte WIZARD_V2-Aufträge sind abgedeckt; unbekannte Formate
  werden nicht interpretiert oder überschrieben.
- Das kompakte Draftformular hat eine Anschlusstechnologie pro Gerät. Mehrport-
  Entscheidungen bleiben im vollständigen Wizardkontext und den vorhandenen
  Anschluss-/Goal-Fachwerkzeugen. Das kompakte Formular ist kein vollständiger
  Ersatz für jeden spezialisierten Geräteeditor.
- Freie Anforderungen und Ergänzungen bleiben als Quellen im Auftrag und Vorschlag
  erhalten. Beliebige Regelungsprosa ist kein Nachweis ausführbarer Steuerlogik;
  Verhalten, Kodierung und Timing benötigen ihre jeweiligen Fachmodelle und Prüfungen.
- Der echte Qwen-Aufruf prüft Sprach-/Toolqualität an einer kleinen Anfrage. Er ist
  kein vollständiger Modell-zu-Neun-Stufen-Lauf mit unbeschränkter Spracheingabe.
- 1641 Backendtests bestanden auf unveränderlichem Kandidaten I, 3 übersprungen
  (`agent-frozen-i-backend-tests.log`). Die danach ergänzten Projektpaket-, MCP- und
  Löschfälle wurden gezielt geprüft: 51 Tests bestanden (`agent-ui-parity-tests.log`).
  Erst das abschließende gemeinsame Release-Gate belegt den gesamten Lieferstand.

Die Zwischenprüfungen oben dokumentieren die Entwicklung; der abschließende
Releasebeleg gilt für den gemeinsam geprüften Lieferstand. Einzelne grüne Tests
oder sichtbare Fortschrittskarten allein belegen keinen Neun-Stufen-Abschluss.
