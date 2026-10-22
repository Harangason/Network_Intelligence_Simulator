# NIS-Produktivlieferung und Fahrzeugprüfung – 17.10.2026

**Code produktiv verifiziert; der vollständige Fahrzeuglauf wartet auf Fachangaben.**
Projekt `20261016122109077-dc3a1aeb`. Kein kanonisches Modell erzeugt, keine manuelle Modellkorrektur und keine Fahrzeug-Simulation behauptet.

## Ausgeliefert

Genau das ausdrücklich freigegebene archivierte Image `networkis:candidate-07cb57d47f91` wurde mit frischem Archiv-/Nutzungsnachweis entfernt. Das wiederherstellbare Archiv bleibt erhalten; Produktion/Rückfallimages wurden nicht bereinigt.

Vollständiger PASS: `b53e295b15bd`, Image `sha256:eaab97030ad994dc8a00e8fc6f38ada67c38e915e316deda63d231902843537b`, Source `be82385a9aab125ae8a296d1f1df1698551e44241bf3d1c1984dc7837ecff897`, Git-Basis `70f0c160bc4f08bd23437f6b3c175523d1e5859c`. Das exakt geprüfte Image wurde über `scripts/release-and-deploy.py --receipt` produktiv übernommen. Eigene unabhängige Prüfung von Image/Source/Ready/vier Modulhashes und unabhängige Peer-Prüfung aller16 eingefrorenen Dateien bestanden.

28 Storageprüfungen, Typecheck,673 Frontendtests,22082 Backendtests plus56 Untertests (2 übersprungen,1 bekannte Feldnamenwarnung),119 Browserfälle und kleine/große HTTP-Abnahme bestanden. Großer HTTP-Lauf:766/766 Routen,0 failed/missing;594 Transportnachrichten/1169 Signale,59 interne Statusnachrichten/235 Signale ausdrücklich ausgeschlossen. Diese Fixture-Ergebnisse sind kein Nachweis einer Simulation dieses Originalfahrzeugs oder realer Hardware-/Safetyqualifikation.

## Tatsächlicher Fahrzeugweg

Unveränderte Originaldatei19088 Zeichen, SHA256 `86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7`, normaler Upload, echter lokaler Qwen über14Abschnitte. Frühere570Zeichen Nutzerergänzung und wörtliche HMI-Antwort bleiben erhalten. Eine von mir zusätzlich geschaffene Beschriftung wurde als Gerätegruppe erkannt; erster Vorschlag nicht übernommen, Befunde unverändert gesichert. Nur diese Metadatenzeile wurde entfernt und die Quelle normal erneut ausgewertet.

Aktuelle Abnahme:80/80 Befunde unverändert regulär im Wizard übernommen;168 vollständige Originalanforderungen,38 Originalfunktionen,5 belegte Controller und73 erforderliche Quellenunits. Kommunikation ist FUNCTION/OTHER. NIS übernimmt selbst22 eindeutig belegte Controlleraufgaben, darunter alle4ADC-Aufgaben Fusion/Perception/Planning/VehicleControl am ADC. Sechs Sensor- und drei Aktortypen haben ausschließlich die direkt menschlich bestätigte Mindestzahl1; ausdrücklich kein vollständiger Umfang. Drei NIS-Angebote zur Abdeckung allgemeiner Übersichten wurden anhand der bereits benannten Geräte bestätigt, ohne anonyme Zusatzcontroller zu erzeugen.

Die ursprüngliche starre Erwartung identischer FUNCTION-Zitatgruppierung war ein Review-Methodikfehler. Unabhängige Prüfung und7 negative Gegenproben bestätigen unveränderte Subjektidentität und vollständige kontextgebundene wörtliche Zeilenabdeckung. Alte FAILED-Datei bleibt unverändert; kein echter Quellen-/Rollen-/Mengenverlust wird dadurch entschuldigt.

## Konkrete Startsperre

NIS blockiert `Auftrag starten`, solange folgende Angaben offen sind:

- Physische HMI-Geräte/Stückzahlen und Integration der Bedienelemente. Die bisherige Menschenantwort beschreibt Funktionen, keine physische Stückliste.
- Ausführende Controller für16 übergeordnete Funktionsbefunde.
-12 Anschlüsse: Powertrain/Chassis/Body, Radar/Kamera/Lidar/Ultraschall/IMU/Raddrehzahl sowie Brems-/Lenk-/Antriebsaktorik.
- Radar-/Ultraschall-Messdaten sowie Stellbefehle und Kodierungen der drei Aktortypen.

Einzige passende Zusatzdatei ist eine Rechtslenker-/Sitz-/Türvariante ohne fehlende I/O-/Signal-/Gerätedefinition; sie wurde nicht als bestätigte Auslegung übernommen. Menschenfrage nach physischem HMI und vorhandener bestätigter I/O-/Referenzspezifikation ist offen.

GET-Nachweis: alle8 kanonischen Ressourcentypen0Objekte, alle9WorkflowstufenEMPTY,0Simulationsjobs. Es existiert deshalb noch kein APPLIED-Modellvorschlag, an dem die168REQ sowie alle Geräte/Funktionen und die Objekt-/Stellbefehlskette bis zum Aktor überprüft werden könnten. Native-/Handoff-PASS ist ausdrücklich kein Modell-/Simulations-PASS.

## Fortsetzen

Tab3 mit dem tatsächlichen Testprojekt bleibt erhalten. Nur reale NIS-Rückfragen mit belegten Quellen-/Menschenangaben beantworten; keine erfundenen Defaults oder direkten Modell-/Routen-/DB-Schreibungen. Danach vollständigen APPLIED-Vorschlag einschließlich source_versions/canonical_ids/Evidence prüfen, alle38 Funktionen und168 OriginalREQ nachweisen und den normalen Workflow bis zum gespeicherten Simulationsjob mit beobachteten Daten fortsetzen. Qwen-Slot nach beendeter Native2 explizit an den koordinierten Peer freigegeben; vor weiterer Inferenz abstimmen.

## Nachweise

- [Aktuelle native Übernahme](native-verification.json)
- [Startsperre](workflow-blocker.json)
- [Quellengestützte Funktionsübernahme](function-source-adoption.json)
- [Alle Cluster und offenen technischen Felder](cluster-source-readback.json)
- [Produktionsidentität](../followup-production-identity-verification.json)
- [Lieferlog](../followup-communication-actions/delivery.log)
- [Gespeicherter GET-Stand](../product-checkpoints/post-be82385-source-review/manifest.json)

[Projekt lokal](http://127.0.0.1:13500/studio/engineering?assistant=project&project=20261016122109077-dc3a1aeb) · [VPN/LAN](http://192.168.178.10:13500/studio/engineering?assistant=project&project=20261016122109077-dc3a1aeb)
