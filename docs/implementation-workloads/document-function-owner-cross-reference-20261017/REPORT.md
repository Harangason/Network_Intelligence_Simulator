## Produktiver Abschluss dieses Teilauftrags – 17.10.2026

Der vollständige Release delivery-996d5008074f/952edd277e95 hat PASS. Storageprüfung,
Typecheck, 689 Frontendtests, 22.097 Backendtests (56 Subtests, 2 übersprungen),
Produktionsbuild, 119 Browserfälle sowie kleine und große HTTP-Gesamtprüfung
bestanden. Der große HTTP-Fall enthält einen tatsächlich abgeschlossenen
Simulationsjob im isolierten Release-Testprojekt; das ist keine Simulation der
Originaldatei „Fahrzeug komplett.txt“.

Image sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b
mit Quelle fd2d74b9c17b37aec51f92b377d037a54f9d9959808a06328097a9570fd3d7e9
wurde über release-and-deploy produktiv übernommen. Readiness, Imageidentität
und sämtliche 16 eingefrorenen Rohdateihashes sind geprüft. Gegen die laufenden
Produktmethoden bestätigt die unveränderte Fahrzeugquelle 23 belegte
Zuordnungen statt 22 und weiterhin 15 offene; beide Fahrdynamikbefunde bleiben
getrennte Quellenidentitäten mit demselben belegten CDC-Verantwortlichen.
Es wurden keine kanonischen Modelle oder Simulationen hierfür geschrieben.

production-verification.json, release-pass-receipt.json und completion-guard.json
belegen den Teilabschluss. Die erste Abschlussprüfung beanstandete falsch
verschachtelte delivery.checks; die unveränderten Nachweise wurden im korrekten
Schema eingetragen, die Wiederholungsprüfung bestand ohne Beanstandungen.

Die vollständigen Originaldatei-Läufe und die inzwischen ausdrücklich beauftragte
getrennte Referenzplanung für Beispielprojekte laufen unter
../reference-example-assumptions-20261017 weiter. Die HMI-Antwort und „neu 9.txt“
sind dafür gesicherte Nutzerergänzungen; fehlende Angaben sind jetzt als
prüfbare Referenzannahmen zu planen. Der nächste Schritt ist keine manuelle
Modellkorrektur. Dieser Teilabschluss stellt keinen Gesamt-PASS dar.

# Kapitelübergreifende Funktionszuordnung – 17.10.2026

Die bereits ausgelieferte Parser-Reparatur bleibt produktiv auf Image `eaab97030ad9`, Source `be82385a9aab`. Der vollständige Release dafür hat PASS. Die zusätzlich im echten Fahrzeugablauf gefundene Zuordnungslücke ist lokal repariert und gezielt geprüft; sie ist noch nicht produktiv.

NIS verbindet nun eine exakt gleiche, wörtlich belegte Funktion in verschiedenen Kapiteln desselben Quellsystems mit ihrem eindeutig deklarierten Controller. Die eigentliche Gerätefunktion muss unabhängig im Kontext dieses Controllers belegt sein. Mehrdeutige Besitzer, andere Profile, zusammengesetzte oder nur ähnliche Namen und fehlende Kontexte liefern weiterhin keine automatische Zuordnung. Backend und Frontend wenden dieselbe Quellgrenze an; die Herkunft bleibt `source_scoped_function`.

Am unveränderten Originalfahrzeug und seinen tatsächlich gespeicherten Qwen-Befunden sind 23 statt 22 Zuordnungen belegt. Alle 22 bisherigen Zuordnungen einschließlich der vier ADC-Aufgaben bleiben erhalten. Nur die zusätzliche globale Fahrdynamikregelung wird eindeutig dem CDC zugeordnet. Die beiden Quellenidentitäten bleiben erhalten. Das ist keine manuelle Modellkorrektur und keine Modell- oder Simulationsabnahme.

130 Frontendtests, 19 isolierte Backendtests und Typecheck bestanden. Die Backendtests melden eine bekannte Pydantic-Feldnamenwarnung. Die tatsächliche Quellgegenprobe und unabhängige Gegenproben aller fünf realen Robotik-Namenskollisionen bestanden ebenfalls. Vollständiger neuer Release, produktiver Funktionsnachweis und Originalsimulation sind offen.

Quellenstand ist eingefroren: `fd2d74b9c17b37aec51f92b377d037a54f9d9959808a06328097a9570fd3d7e9`, Git-Basis `70f0c160bc4f08bd23437f6b3c175523d1e5859c`. Verifikation `3ba046017f8b4c1566a9eaf30dedfeb3db508b2607640095447c2ec489add120`. Keine fremden Dateiänderungen gegenüber dem vorausgehenden Freeze festgestellt.

Der echte produktive Wizard ist weiterhin bei 22 Zuordnungen und 16 offenen Feldern; einer dieser Fälle ist der hier behobene Produktfehler. Die übrigen 15 Zuordnungen sind mit der strikten exakten Quellenregel nicht bewiesen. Zusätzlich fehlen bestätigte physische HMI-Stückliste, qualifizierte Anschlüsse sowie Messdaten und Aktorkodierungen. Vorhandene physische Quellenanforderungen bleiben erhalten: Backbone mindestens 1 Gbit/s; Sensor-Punktverbindungen mindestens 2 Gbit/s; CAN 500 kbit/s oder CAN-FD ohne festgelegte Datenphase; GMSL/FPD-Link/GigE sind noch Alternativen. Keine dieser offenen Entscheidungen wird mit erfundenen Defaults geschlossen.

Die tatsächliche Projekt-ID bleibt `20261016122109077-dc3a1aeb`. Alle acht kanonischen Modellressourcen waren beim letzten gespeicherten GET-Checkpoint leer; es existierte kein Simulationsjob. Der normale NIS-Auftrag wurde nicht unter Umgehung der Startsperre ausgelöst.

- [Projekt lokal](http://127.0.0.1:13500/studio/engineering?assistant=project&project=20261016122109077-dc3a1aeb)
- [Projekt VPN/LAN](http://192.168.178.10:13500/studio/engineering?assistant=project&project=20261016122109077-dc3a1aeb)

Für den neuen Release sind aktuell 100 NIS-Images vorhanden, kein reiner ungenutzter FAIL-Kandidat ist automatisch freigegeben. Das vollständige Archiv für genau `networkis:candidate-48a0fca755d0` wurde mit 24 Bestandteilen geprüft; das Image hat FAIL und PREPARED, keinen PASS und keine Containerreferenz. Es wurde noch nicht entfernt. Produktion und Rückfallimages bleiben erhalten.

Archivnachweis: `archive-review-48a0fca755d0/archive-audit.json`; SHA256 `9700bb21e3a9cbb2fb60d11398be9a51af2f43c8a16d38366436224a296b9956`. Die gezielte Löschentscheidung wurde dem Menschen vorgelegt und ist noch offen. Ohne diese Entscheidung wurde weder ein weiterer Kandidat erzeugt noch ein neuer vollständiger Gate-Lauf gestartet.

Unabhängiger abschließender Fünf-Datei-Diff-/Test-/Freeze-Review: PASSED_READ_ONLY_PATCH_REVIEW, keine Befunde. Nachweis: `.tool-checker/runs/20261017_src_original_documents_simulation/robotics/source-owner-patch-independent-review.json`. Der erneute GET-Checkpoint `cross-section-repair-pending-20261017` bestätigt acht leere Modellressourcen; er stellt keine Modellabnahme dar.

## Fortsetzung nach menschlicher Freigabe

Die exakte Entfernung von candidate-48a0fca755d0 wurde erneut explizit freigegeben und nach frischem Archiv-/Tag-/Container-/Receipt-Audit mit --no-prune ausgeführt. Archiv und Produktion blieben erhalten. Der vorherige Speicherblocker ist aufgehoben. Der vollständige Release läuft unter delivery-996d5008074f/952edd277e95, Sitzung69251. Storage, Typecheck und689Frontendtests bestehen; Backendtests laufen. Quelle fd2d74 und alle16eingefrorenen Rohhashes sind unverändert. Ein neuer PASS und Produktivnachweis werden erst nach dem gesamten Lauf eingetragen.

Die weiteren wörtlichen Menschenantworten sind in user-continuation-answers.json gesichert. Der passende lokale Referenztext I:/PycharmProjects/neu 9.txt wurde mit SHA32c864c91ac85c2884ef0c3c9e62456e6ade59cc2a22cae384bdfe5a2e2eff60 gelesen und unverändert als Evidence kopiert. Ein flacher Vollanhang würde im aktuellen Parser unter anderem seine100Sensoren/100Aktoren/1Gateway als verpflichtende Inventarfakten klassifizieren; daher wurde er nicht blind in den laufenden Fahrzeugentwurf übernommen. Die Quelle ist Signal-/Kommunikationsreferenz, kein Ersatz des Originalumfangs. Weitere echte NIS-Referenzreview nach Auslieferung, ohne manuelle Modellkorrekturen.
