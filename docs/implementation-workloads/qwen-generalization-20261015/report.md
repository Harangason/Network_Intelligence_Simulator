# Qwen mit sieben weiteren Projektdateien geprüft

**Ergebnis: Das allgemeine Funktionieren ist nicht nachgewiesen. Vier Dokumente werden abgelehnt, drei liefern nur teilweise brauchbare Vorschläge. Kein Fall erfüllt alle vorab festgelegten fachlichen Kriterien.** Qwen erkennt unterschiedliche Branchen und Inhalte, aber die Überführung in getrennte, quellengebundene Geräte, Funktionen und Rückfragen ist noch unzuverlässig.

| Originaldatei | Ergebnis | Entscheidender Befund |
| --- | --- | --- |
| Intelligentes HLK-Regelsystem.txt | Abgelehnt | Controller, Sensorik und Aktoren teilen eine Architekturzeile; beide Antworten scheitern an der Mehrfachreferenz. Allgemeine Controllerart wird als Instanz behandelt. |
| Chemieanlagen-Modul.txt | Teilweise brauchbar | Prozesskontext und Funktionen passen; Sensorik, Aktoren und SPS/DCS verschwinden als getrennte Rollen in einer CATEGORY/OTHER. |
| Kollaborativer Roboterarm.txt | Abgelehnt | Qwen erkennt verschiedene Hardwarekategorien, kann sie wegen der gemeinsamen Quellenzeile aber nicht getrennt übergeben. Auch die Korrektur scheitert. |
| Infusionspumpe.txt | Abgelehnt | Gemeinsame Hardwarezeile scheitert zweimal. Allgemeiner Embedded Controller wird zunächst mit Stückzahl 1 angesetzt. |
| 5G-RAN-Komponente.txt | Teilweise brauchbar | Telekommunikationskontext erkannt; Baseband-Processing wird zusammen mit Hardware und Schnittstellen als Hardwarekategorie eingeordnet. |
| Satelliten-Avionik.txt | Abgelehnt | Gemeinsame Hardwareliste scheitert zweimal; „UART-ähnlich“ erscheint in der Vorschlagsprosa als UART ohne Einschränkung. |
| Mobiler Service‑Roboter mit Greifarm und 360°‑Sensorik.txt | Teilweise brauchbar | Mengenbereich bleibt offen und Hauptrechner wird erkannt. Mikrocontroller-Auswahl wird jedoch zu einer konkreten Instanz, Motorcontroller zum Aktor; I²C/WLAN bleiben ungeklärt, die strukturierte Funktionsliste ist leer. |

## Tatsächlich ausgeführt

Am 15.10.2026 von 06:36 bis 07:11 Uhr Europe/Berlin: zwölf echte Modellaufrufe mit dem lokal installierten `qwen3.8:27b` (Familie qwen35, 27,3B, Q4_K_M), insgesamt 7603 erzeugte Tokens und rund 34,9 Minuten. Modell-Digest: `22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643`.

Alle sieben Originaldateien wurden unverändert geprüft. Der unabhängige Abgleich bestätigt bytegleiche Originalkopien und die vollständige Übertragung jedes Dokuments in den tatsächlichen Modellanfragen, einschließlich der beiden Abschnitte des ausführlichen Roboters. Die Korrekturen erhielten dieselben Quellen mit Validierungsfeedback. Es wurden keine Modellantworten simuliert oder wiederverwendet. Die Dokumentauswertung lief lokal ohne ChatGPT-/Cloud-Inferenz.

Die beiden geprüften Anwendungsmodule stimmen per SHA-256 mit der laufenden Produktivversion überein. Die Fehler sind somit auch im produktiven Code vorhanden. Kein Anwendungscode, kanonisches Modell oder Produktivdatensatz wurde geändert. Eine neue Auslieferung war für diesen Prüfauftrag nicht erforderlich und wurde nicht vorgenommen.

## Konsequenz

Die Korrektur muss allgemein an Quellenbindung und fachlicher Validierung ansetzen: mehrere exakt belegte Aussagen innerhalb einer Zeile zulassen, identische Geräte weiterhin gegen Duplikate schützen, Kategorien und Alternativen von Instanzen trennen, zusammengesetzte Controllerbezeichnungen richtig prüfen und Schreibweisen sowie Einschränkungen von Protokollen erhalten. Die vollständige Funktionsbeschreibung darf trotz begrenzter Ausgabelisten nicht unbemerkt verloren gehen. Anschließend sind dieselben Dateien erneut mit echtem Qwen zu prüfen. Eine Sonderbehandlung einzelner Dateinamen oder eine bloße Lockerung des Validators würde den Befund nicht lösen.

Diese Prüfung deckt Dokumentaufnahme und Vorschlagsqualität ab. Sie belegt keine vollständige Wizard-Ausführung, Simulation, technische Freigabe oder EIP-Integration. Die Prüfung ist abgeschlossen; die allgemeine fachliche Anforderung bleibt mit den beschriebenen Produktbefunden offen. Reparaturen wurden in diesem zusätzlichen Testauftrag nicht umgesetzt.

Nachweise: [Vorab-Kriterien](acceptance.md), [detaillierte Befunde](findings.md), [Integritätsprüfung und Ergebniszahlen](audit.json), [Dateihashes und Laufzeiten](manifest.json), [produktive Codehashes](production-code-observation.json), [Laufprotokoll](native-run.log). Die Dateien `*-wire.json` enthalten alle echten Anfragen und Antworten; `*-proposal.json` enthalten ausschließlich tatsächlich zurückgegebene Vorschläge.
