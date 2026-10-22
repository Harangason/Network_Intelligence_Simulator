# NIS: eigener fachlicher Workflow und gemeinsamer Release

Der Simulator prüft fachliche Sensor–Verarbeiter–Funktionsausgabe–Empfänger–Aktor-Ketten im eigenen Vorschlags-, Prüf- und Freigabeablauf. Bestehende Modelle werden nicht vom Implementierungsagenten umgebaut oder stellvertretend neu simuliert.

## Umsetzung und fachliche Grenzen

Der Agent erhält gemeinsame Regeln und das registrierte, mit VALIDATE berechtigte Kommunikationsaudit. Dieses berücksichtigt auch ältere Verträge und meldet fehlende fachliche Nachweise als REVIEW. Neue PROCESSOR-Eingänge entstehen nur aus ausdrücklich deklarierten Funktionsausgaben und tatsächlichen Erzeuger-/Empfängerreferenzen. Status, Messung, Rückmeldung und Aktorbefehl bleiben getrennt. Der Modellgenerator verwendet eine neue Revision, damit alte Vorschläge nicht unbemerkt wiederverwendet werden.

Die gemeinsame Auslieferung enthält außerdem die vollständige Dokumentaufnahme und den nativen Qwen-Vorschlagspfad des Quellcode-Owners. Unveränderliche Quellenreferenzen koppeln Namen und Zitate. Kontextfenster decken die Originalquelle vollständig ab. Controllerdeklarationen, Aliasse, physische Anschlüsse und Anforderungen werden getrennt geprüft; Transportvarianten bleiben an die zentrale Registry gebunden. Bei mehreren Abschnitten entsteht der globale Prüfauftrag aus der vollständigen Faktenunion. Abschnittsweise fehlender Kontext, lokale R-IDs und widersprüchliche Annahmen werden nicht als globale Aussagen übernommen. Kategorien behalten offene Stückzahlen; unregistrierte technische Angaben bleiben Rückfragen ohne bestätigte Port-, Transport- oder Gerätezuordnung. Ein allgemeinerer Wortlaut für diese technischen Angaben ist als redaktioneller Folgepunkt beim Quellcode-Owner dokumentiert und verändert nicht die Auslieferung.

## Tatsächliche Prüfung

- Eigene fachliche Prüfungen: 140 isolierte Backendtests. Testdaten-/Inventarreparatur: separater gezielter Lauf mit 31 Tests. Globaler Dokumentpfad beim Quellcode-Owner: 154 gezielte Prüfungen.
- Echte lokale Qwen-Abnahme der Originaldatei: 19088 Unicode-Zeichen, 20406 UTF-8-Bytes einschließlich unverändertem CRLF, sieben vollständige Fenster, neun tatsächlich empfangene Antworten von qwen3.8:27b, PASS nach 2243.50s. Unabhängig geprüft: Originalhash, tatsächliche Requesttexte, Segmenthashes, Code/Probe-Fingerprints, alle fünf benannten Controller, unquantifizierte Sensor-/Aktorgruppen sowie konsistenter Gesamtauftrag und Rückfragen. Dies ist ein Vorschlag mit REVIEW_REQUIRED, keine Modellübernahme.
- Zwei Browser-Testvorbedingungen wurden korrigiert: normales Pflichtfeld Projektname ausfüllen; widersprüchliche separate CAN-Zeile aus dem ausdrücklich CAN-FD-only-Szenario entfernen. Assertions und Timeouts blieben erhalten. Beide echten isolierten UI-Fälle bestanden auf dem unveränderten Image; danach wurde das gesamte reguläre Gate wiederholt. Die GUI-Verification-Only-Änderung ist getrennt dokumentiert, der ursprüngliche Modellphasenbeleg wurde nicht als neue Inferenz ausgegeben.
- Abschließendes vollständiges Gate: Speicherprüfungen, Typecheck,643 Frontendtests, 21938 Backendtests mit 56 Untertests und 2 regulären Skips, 117 Browsertests sowie kleine und große HTTP-Abnahme erfolgreich. Der große reale Wizardfall 50/250/250 und alle Rückkehr-/Änderungsfälle sind im Browserumfang enthalten. HTTP-Szenarien enthalten die tatsächlich ausgewiesenen fachlichen WARNING-Stände; deren akzeptierter Umfang ist im Originalreport erhalten. Kein Tool-Checker-Kampagnen-PASS wird behauptet.

## Produktive Übernahme

Regulärer Einstieg: scripts/release-and-deploy.py. Vollständiger PASS-Beleg: backend/test-output/release-gates/delivery-3f9839f6b18a/da780e21f45c/receipt.json. Derselbe bestehende Kandidat wurde nach reiner GUI-Testdatenkorrektur vollständig neu geprüft und produktiv übernommen; kein zusätzlicher Imagebuild war nötig.

Laufendes geprüftes Image: sha256:e27aa35055b668d136f9f15adba308d1e4b22a1c5ad7d933f6118f9bc71b770b.
Anwendungsquellstand:19ebdcb753bb67b1de0b70a2df0ab88e3e6d787061bd0029e9e82645edde7857.
Git:70f0c160bc4f08bd23437f6b3c175523d1e5859c. Der zwischenzeitliche Commit wurde gegen alle 55 bereits eingefrorenen Anwendungs-/Testpfade und die genehmigte globale Reparatur abgeglichen; Nachweis commit-transition-audit.json.

Produktionsidentität, Build-Quelle, Datenbank-/Speichergesundheit und installierte Fachfunktionen wurden nach der Übernahme geprüft. Die fünf Branchenfälle (Automotive, Robotics, Aerospace, Building, Custom) laufen im Speicher des Produktionscontainers und verändern keine Produktmodelle. Die Dokumentguards, Berechtigungen und Registrierung des nativen Werkzeugs wurden ebenfalls dort geprüft. Der tatsächlich konfigurierte Qwen-Anbieter ist aus dem Container erreichbar; Modell-/Familien-/Parameterangaben wurden per tags/show gelesen. Diese letzte Anbieterprüfung ist ausdrücklich keine weitere Inferenz. Nachweise: production-functional.json, production-native-provider.json sowie native-full-source-acceptance.json und verification-input-transition.json.

Die gesicherten Abbrüche, negativen Originalantworten, vollständigen FAIL-Berichte und die gezielt freigegebene E125-Imagearchivierung bleiben nachvollziehbar. Produktion erhielt ausschließlich das exakt erfolgreich geprüfte Image.
