# Lokale Korrektur geprüft; Original- und Releaseabnahme offen

Die vollständige gezielte Regression besteht mit **449 unterschiedlichen Fällen**, ohne Fehler oder Skips. Alle bisherigen 429 Fälle sind enthalten; 20 neue Fälle prüfen die vollständige Kontextdarstellung. Die echte lokale Qwen-Gegenprobe liefert **13 von 13 Kontrollwerten exakt**. Daraus wird keine Originalmodell-, Simulations- oder Releaseabnahme abgeleitet.

## Änderung und Ursache

Der frühere vollständige Fahrzeugrequest37410 endete regulär am unveränderten Kontextgrößengate. Der bisherige private Codec komprimierte exakte Wiederholungen und Tabellen, aber kaum nahezu gleiche große Konfigurationsobjekte. Die exakte damals abgewiesene letzte Nachricht wurde nicht gespeichert; ein Autoren-Gegenbeispiel wird nicht als dieser Originalpayload ausgegeben.

Die bestehende private Darstellung unterstützt nun profitable Kopien mit ausdrücklichen Feldersetzungen. Als Basis dienen vollständig erhaltene Objekte. Bereits aus Differenzen rekonstruierte Konfigurationsobjekte werden nicht erneut zur Basis; damit stehen auch spät geänderte Werte direkt an jeder betroffenen Kopie. Die exakte JSON-Schreibweise geänderter Skalare wird zusätzlich als Zeichenkette mitgeführt, während der typisierte Wert unverändert bleibt. Widersprüchliche Angaben werden vom unabhängigen Prüfer abgelehnt. Vollständige Literal- und bisherige Tabellen-/Kopierdarstellungen bleiben Alternativen; die kleinste vollständige Darstellung gewinnt. Die Suchgrenze von acht Basiskandidaten begrenzt ausschließlich Optimierungsarbeit, keine Quelle oder Hardwaremenge.

Geändert wurden ausschließlich die beiden Kontexthelfer in local_reasoner.py. Alle anderen Modul-AST-Knoten einschließlich der gesamten normalen Reasonerklasse, Schemas, Identitätsvergabe, JSON-Patches und Eingangsgrößenprüfung sind exakt erhalten. Von 2.313 Anwendungsdateien unterscheiden sich nur die Kontexthelfer in dieser einen Datei. Modell, Maximum131072, Ausgabe8192 und Lesetimeout1200 bleiben unverändert. Fehlerdiagnostik erfasst Größen, Zählwerte und Hashes ohne Quelleninhalt.

## Tatsächliche Nachweise

| Prüfung | Ergebnis |
| --- | --- |
| Erste 16 Kontextfälle gegen eingefrorenen Vorzustand | 9 FAIL, 7 PASS; unveränderte App |
| Zusätzliche Literalabsicherung | 2 RED; danach 37 gezielte PASS |
| Zusätzliche flache Kopierbasis | 2 RED; danach alle 20 Kontextfälle PASS |
| Vollständiger aktueller Referenz-Regressionsumfang | 449 PASS, 0 Fehler/Skips; 1180,043 Sekunden |
| Echte Qwen-Gegenprobe auf diesem Stand | Genau ein Request; 13/13 exakt; normaler Stop und Exit0 |

Die früheren nativen Gegenproben2/3/4 bleiben fehlgeschlagene Nachweise. Sie belegten zunächst verlorenes Minuszeichen und danach veraltete Werte aus Kopierketten. Ihre vollständigen Rohantworten und die ursprünglichen FAIL-XMLs sind erhalten. Bestehende Fortsetzungstestfunktionen und Assertions sind AST-identisch; angepasst wurde ihr unabhängiger Decoder für das erweiterte private Format.

Für den **identischen tatsächlich gesendeten Autorenkontext** der erfolgreichen fünften Probe sinkt die Kontextdarstellung von266384auf97618UTF8-Bytes. Beide Darstellungen rekonstruieren unabhängig exakt dieselben Werte und Typen. Die sichere vollständige Eingangsobergrenze einschließlich identischem Systemtext und Reserven sinkt von279841auf111075; das Maximum bleibt131072. Das ist ein Kapazitätsnachweis an dieser Gegenprobe, kein gemessener Geschwindigkeitsnachweis für die vollständigen Originale.

Probe5 endete am02.11.2026 um20:37:54UTC regulär. Python73544/35620sind beendet; Guard2743endete mit Exit0 und SIGCONT20:38:09. Der tatsächliche Hauptworker war danach idle, Produktion3792healthy/ready und unverändert.287Ausgabetokens,29091Prompt-Evaluationstokens,286,169Sekunden Gesamtdauer. Wesentliche Belege: regression-terminal.json, native-context-delta-counter-5/terminal-proof.json, native-counter5-capacity-proof.json und source-scope-proof.json.

## Vorbereitung und offene Pflichtarbeit

Der eigene überholte a09Diagnosestack ist recoverbar archiviert und exakt stillgelegt: normale Projektexporte, frischer148741-Byte-Customdump mit geprüfter TOC, Runtime-/Logarchive samt Dateihashes und23geprüfte Imageblobs. Session56938endete regulär mit Exit0. Nur seine App, Datenbank, Netz- und Runtime-Ressourcen wurden entfernt. Image und originales PREPARED-Receipt bleiben erhalten; Produktion und Rollback sind geschützt. Es wurde kein Image gelöscht oder gepruned.

Der bestehende Source-only-Importoperator hat eine ausdrückliche Kindnachweisoption erhalten. Der normale API-Teil ist byteidentisch;14historisch eingefrorene Dateien werden gegen die echten unveränderlichen Vorstände geprüft. Eine neue Übertragung oder Imagevorbereitung ist damit noch nicht behauptet.

Es fehlen weiterhin: normaler Kandidat mit tatsächlichem Image-/Konfigurationsnachweis; normaler Source-only-Transfer in frische Zustände; beide unveränderten vollständigen Originale durch Referenzprüfung, hashgebundenes Review, Wizard und Apply zu gespeicherten vollständigen kanonischen Modellen; echte ALL-Simulationen mit PASS-Konformität, null fehlgeschlagenen Routen und vollständigen Trace-Seiten; vollständiges Releasegate am endgültigen Image; release-and-deploy.py mit passendem vollständigem PASS-Receipt und Prüfung der tatsächlichen Produktion. Auch die rohe35-Profil-Gatewayvorschau muss am aktuellen Kandidaten und nach Lieferung am Produkt frisch geprüft werden.

Alle15RequiredOutcomes und15ValidationRequirements bleiben unverändert. Produktion enthält die neue Korrektur noch nicht; der Tool-Checker-Kampagne wird kein PASS zugeschrieben. Die produktive Übernahme ist ausdrücklich autorisiert, bleibt aber von diesen tatsächlichen Pflichtnachweisen abhängig.
