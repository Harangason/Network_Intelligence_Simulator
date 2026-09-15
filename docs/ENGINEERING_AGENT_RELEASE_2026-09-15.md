# Engineering-Agent: ausgelieferter Stand vom 15.09.2026

Die freigegebenen sechs Arbeitspakete wurden umgesetzt und gemeinsam über das
Produktions-Release-Gate geprüft. NIS läuft mit Build `81dc57c2a8fd`.

## Ergebnis für den Nutzer

- Ein Projektentwurf lässt sich im Chat speichern, ergänzen, einem neuen Projekt
  zuweisen und über Review/Apply tatsächlich als Modell übernehmen, ohne den
  Wizard zu öffnen. Das Ursprungsprojekt wird dabei nicht verschoben.
- Fehlende Controller und unklare Anschlüsse werden als konkrete Entscheidungen
  behandelt. Geräte lassen sich ergänzen, zuordnen und korrigieren; unbekannte
  Angaben werden nicht mit Automotive-Hardware oder Ersatzprotokollen aufgefüllt.
- Chat und Wizard verwenden einen gemeinsamen, versionierten Entwurf. Native
  Wizardaufträge behalten ihren vollständigen Graph-, Anschluss- und HMI-Kontext.
- Reload, verlorene Speicherantworten, konkurrierende Revisionen und erneutes
  Fortsetzen erhalten den Auftrag. Veraltete Vorschläge dürfen nicht übernommen
  werden; Wiederholungen erzeugen keine zusätzlichen Modelle oder Jobs.
- Zusätzliche Fachaktionen sind über echte Werkzeuge erreichbar: Modellanlage,
  Zuordnung und Strukturtransfer, geprüfte Löschvorschläge, Dateieinfuhr,
  Projektpaketexport/-wiederherstellung und Fehlerszenarien. Der Katalog trennt
  Analyse, Vorschlag und tatsächliche Ausführung.

Die genaue Zuordnung und ihre Grenzen stehen in
[AGENT_UI_CAPABILITY_MATRIX.md](AGENT_UI_CAPABILITY_MATRIX.md).

## Gemeinsame Abnahme

| Prüfung | Ergebnis |
| --- | --- |
| Backend, ausschließlich isolierte SQL-Datenbank | 1645 bestanden, 3 übersprungen, eine bestehende Pydantic-Warnung |
| Frontend | 341 bestanden; TypeScript-Prüfung bestanden |
| Produktionsbuild | Bestanden, kein Entwicklungsimage |
| Browser-E2E | 17 bestanden; 0 übersprungen, 0 instabil |
| Kleiner HTTP-Neun-Stufen-Lauf | Conformance PASS; 8/8 Routen, 18/18 Signale |
| Großer HTTP-Neun-Stufen-Lauf | Conformance PASS; 838/838 Routen, 653/653 Nachrichten, 1404/1404 Signale |
| Nachprüfung des ausgelieferten Produkts | 18/18 Prüfungen bestanden |

Die Browserfälle enthalten Raspberry Pi mit drei Temperatursensoren und zwei
beziehungsweise fünf Ventilen, tatsächliche Chatmodellübernahme, neue Projekt-ID,
fehlenden Controller über Chat und Wizard, gemeinsame Draftänderung im selben
Wizardlauf, Konflikte, verlorene Antworten, Geräteentfernung sowie Reload und
echten Containerneustart. Der große bestätigte Auftrag mit 50 Controllern,
250 Sensoren und 250 Aktoren durchläuft echte Review-/Apply-Grenzen und einen
Neustart während der Simulation. Die unabhängigen HTTP-Läufe prüfen zusätzlich
gespeicherte Artefakte, Traceabdeckung und Wiederholung ohne doppelte Simulation.

Die beiden vollständigen Fixtures verwenden deterministische Fachwerkzeuge bei
nicht verfügbarem KI-Endpunkt. Ein zusätzlicher echter Qwen-Aufruf ist separat
bestanden (`backend/test-output/agent-live-model-tests.log`); dies ist kein
Nachweis beliebiger Spracheingaben in einem vollständigen LLM-Neun-Stufen-Lauf.

## Auslieferung und Bestand

- Gate: `3990c4575c55`, Status PASS.
- Image: `sha256:39aaa9eeb202082350bf4a342ecf40ddb3001aa91f92fc33324c143e4565a8d9`.
- Quelle: `81dc57c2a8fd7e3a699c654dfa5e512fa51ffad2b4b5e53970697607018bdb40`.
- Prüfmanifest: `ca9fef84d6e6dff7f4799812302ce2923780316af218b73f6495ecdf73012d91`.
- Gegenüber vorherigem PASS abgegrenzter Lieferumfang: 101 Dateien; fremde
  Landing-Animationen ausgeschlossen. Manifest unter
  `backend/test-output/release-source/agent-release-20260915-r1/agent-release-scope.json`.
- Konsistentes PostgreSQL-Backup: 254735206 Bytes, SHA-256
  `d5c035e9f22c7fd313188adb17e19aa4271e6366fa482d5dcf1df3e392d6d43f`.
- Vorher-/Nachher-Vergleich für `network-project-20260910042736034-d11591d0`:
  kanonische Daten, Workflowrevision, Snapshots und Jobs erhalten. Dieses Projekt
  war unmittelbar vor dem Update bereits ohne kanonische Modellobjekte;
  der Vergleich behauptet keine Wiederherstellung früher gelöschter Objekte.
- Volumes, Datenbankimage, KI-Einstellungen und GPU-Zuweisung erhalten.
  Ports 13500 und 15050 melden bereit und dieselbe geprüfte Quellidentität.
  Der lokale KI-Dienst ist aus dem neuen Container erreichbar (sechs Modelle).
- Die eigenen temporären Release-Testcontainer wurden entfernt. Backup und
  Prüfnachweise bleiben außerhalb der Wegwerfvolumes erhalten.

Alle Gate-, Browser-, HTTP-, Backup- und Bestandsnachweise liegen unter
`backend/test-output/agent-final-release-gates/3990c4575c55/`.
Maßgeblich sind `receipt.json` und `product-deployment-verification.json`.

## Bewusste Nachweisgrenzen

Das kompakte Geräteformular bietet eine Anschlusstechnologie pro Gerät;
Mehrportentscheidungen bleiben im vollständigen Wizard und den Fachwerkzeugen.
Freie Regelungsanforderungen bleiben als Quellen erhalten, werden aber nicht
allein durch ihre Eingabe zu geprüfter ausführbarer Steuerlogik. Unvollständige
Elektrik, Kodierung oder Timingnachweise dürfen weiterhin fachlich blockieren.
Das Fähigkeiteninventar beschreibt Fachaktionsgruppen, keine vollständige
Einzel-E2E-Abnahme jedes UI-Buttons. Kapazitäts- und Bewertungswarnungen werden
nicht für eine optisch grüne Abschlussanzeige unterdrückt.
