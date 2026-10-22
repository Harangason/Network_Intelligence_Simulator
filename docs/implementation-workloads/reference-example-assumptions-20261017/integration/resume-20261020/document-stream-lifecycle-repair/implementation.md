# Dokumentaufrufe nach verlassener Auswertung

Die genaue produktive Dokumentroute und der aktuelle gemeinsame Streamhelfer
starteten einen Hintergrundarbeiter, ohne dessen Lebensdauer an den geöffneten
HTTP-Stream zu binden. Die erhaltene Reproduktion schließt die Antwort und zeigt,
dass der freigegebene Arbeiter danach dennoch den nächsten Abschnitt beginnt.
Die Wizard-Dokument-/Referenzaufrufe besaßen außerdem keinen an Quelle, Projekt
und Dialog gebundenen Abbruch. Die konkrete Quelle jedes früheren produktiven
Modellaufrufs ist aus Slot-Metadaten allein nicht feststellbar.

Die Reparatur verwendet die vorhandene RunCancellation-Registry. Geschlossene
nicht-dauerhafte Dokumentstreams unterbrechen das gebundene asynchrone Await;
der Arbeiter startet keinen weiteren Abschnitt. Die Browseraufrufe besitzen
einen AbortController und ignorieren verspätete Ergebnisse anderer Quellen.
Referenzabbruch wird mit dem bestehenden Generationstoken als CANCELED gespeichert,
ohne einen Teilentwurf zu übernehmen oder einen Nachfolger zu überschreiben.
Die absichtlich dauerhafte Wizardausführung bleibt unverändert.

Provider, Modelle, Zeit-/Kontext-/Ausgabebudgets, Quellfakten, Schemas,
Planungssemantik und Freigabegates wurden durch diese Reparatur nicht verändert.
Der AST-Vergleich steht in source-change-scope-proof.json. Der vorherige Fix der
Vier-Fact-Hardwarestufen bleibt erhalten.

## Bisherige tatsächliche Nachweise

- Zwei erhaltene Vorher-Reproduktionen, einschließlich genauer Produktionsroute.
- 20 gezielte isolierte Backendfälle bestanden, darunter Abbruch, normale
  Fertigstellung, persistenter Referenzabbruch, Nachfolgertoken und Wizardabbruch.
- 15 Frontend-Streamfälle bestanden; Typecheck erfolgreich. Ein zunächst
  fehlschlagender Fehlertransportfall ist einschließlich Vorher-Beleg erhalten.
- 14 tatsächliche lokale qwen3.8:27b-Compiler-/Grammatikfälle bestanden; dies ist
  kein vollständiger Dokument-, Modell-, Simulations- oder Release-PASS.
- Breitere Dokument-/Referenzregression läuft unter der bereits gestarteten
  Session51372. Keine zweite identische Prüfung starten.

## Operative Bereinigung des alten Produktivstands

Alle drei registrierten Projekte wurden normal exportiert, und ein vollständiger
lesender Custom-Dump wurde mit pg_restore --list geprüft. Der bereits gelöschte
Default wurde nicht neu angelegt. Anschließend wurde ausschließlich der bestehende
NetworkIS-Appcontainer neu gestartet. Alle drei Exporte sind bis auf den
Exportzeitstempel unverändert, die laufende Imageidentität3792 unverändert und
Gesundheit/Readiness bestätigt. Die alten Dokumentarbeiter und ihre Verbindung
zum Inferenzserver waren danach beendet. Dies ist keine Auslieferung der Reparatur.

Das explizit freigegebene, vollständig archivierte alte Image53fc/eaf wurde mit
docker image rm --no-prune entfernt; der genaue Nachweis liegt unter
archive-review-53fc717a9d44. Andere Images wurden nicht entfernt.

## Noch erforderlicher Abschluss

Nach Ende der laufenden Regression den einen normalen Kandidaten auf eingefrorener
Quelle vorbereiten. Tatsächlichen HTTP-Abbruch mit lokalem Qwen im isolierten Stack
prüfen. Beide unveränderten Originale mit ihrer expliziten alten Intake-Herkunft
über die normalen Wege bis zum vollständigen gespeicherten Modell und zur
ALL-Scope-Simulation prüfen. Keine manuellen Modellkorrekturen. Danach vollständiges
Release-Gate, exakt geprüftes Image produktiv übernehmen und Identität, Gesundheit
und betroffene Funktion bestätigen. Alle15 Outcomes und15 Validations des
gemeinsamen Elternauftrags bleiben vollständig erhalten.
