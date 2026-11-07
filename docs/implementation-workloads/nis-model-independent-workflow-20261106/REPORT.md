# Modellunabhängige lokale NIS-Anbindung – 6. November 2026

Status: Im aktuellen Auftrag abgeschlossen und produktiv. Vollständiges Releasegate PASS; exakt getestetes Image ausgeliefert, Laufidentität und Gesundheit unabhängig geprüft. Echte Funktionsprobe mit dem tatsächlich aktivierten Llama 3.1 8B im ausgelieferten Image bestanden. Diese Komponentenproben belegen keine vollständige historische Originalabnahme.

## Änderung und Grenzen

Der gemeinsame reine Validator prüft die ausdrücklich ausgewählte lokale Modellidentität. Weitere GGUF-Sprachmodellfamilien und Aliase benötigen positive endliche Parameterzahl und explizite Completion-Fähigkeit. QWEN-/LLAMA-Herkunft bleibt für historische Artefakte erhalten; Cloud-/Embeddingmodelle und unpassende bekannte Familienidentitäten bleiben gesperrt. Neue generische Artefakte tragen LOCAL_LLM und exaktes Modell/Digest, gespeicherte geprüfte Metadaten sowie vollständige passende Providerantwort. Die neue Datei ist kanonisch mit ihren drei tatsächlich gescannten Verbrauchern in der vorhandenen Strukturzuordnung registriert.

Die vorhandene Prüfung unabhängig gelieferter Sollwerte weist nun auch Quellenbezeichnungen zurück, die dem erzeugenden Llama/generischen Modell, dessen Autorlabel oder Familie zugeordnet sind. Unabhängige Fälle und menschliches Review bleiben notwendig; der Modellname beweist keine fachliche Richtigkeit.

Eine ausdrückliche HTTP400-Ablehnung nativer Tools führt zu einer schema-gebundenen Werkzeugentscheidung auf demselben Modell. Verlauf und Argumentverträge bleiben erhalten; unvollständige Antworten, andere Modelle, fremde Tools und verletzte Argumentgrenzen werden abgewiesen. Andere Providerfehler starten keine Protokollanpassung. Erfolgreiche Antworten ohne Anpassungsbedarf benötigen keine zusätzlichen Fehlerstatusattribute. Normale MCP-Rechte, Validierung, Review/Apply und Revisionen bleiben zuständig.

AST-/Literalvergleich belegt unveränderte vollständige Dokument-/Referenzverarbeitung, Quellen-/Kontexthelfer, Kontext-/Ausgabe-/Zeitgrenzen, Codevertrag, begrenzten Interpreter, ECU-Laufzeit und Logikfallprüfung. Es wurden weder Originaltexte noch kanonische Geräte/Signale/Routen/Parameter manuell geändert.

## Nachweise

* Ursprüngliche reine Identitätsgegenprobe und RED:5 fehlgeschlagene positive Modell-/Aliasfälle,36 weitere Fälle bestanden. Zusätzliche Unabhängigkeits-/Kompatibilitätsgegenproben mit eigenem RED-XML erhalten.
* Erste angrenzende Runde:335PASS/48FAIL, alle48 wegen zusätzlich verlangtem Formatfeld in älteren erfolgreichen Testmetadaten; historische Qwen-/Llama-Kompatibilität wiederhergestellt, neue generische Identitäten bleiben strikt. Danach431 Fälle im betroffenen Dokument-/Referenz-/Funktions-/Logikbereich bestanden.
* Protokoll-/Chatprüfung101PASS; danach vollständige Backendrunde2FAIL/22667PASS/2SKIP/56SubtestsPASS in3354.23s. Die zwei Integrationslücken waren unnötige Statusabfrage bei erfolgreichem Transport und fehlende Strukturzeile. Original-FAIL-Receipt und Rohlog unverändert erhalten, kein Image gebaut. Nach Korrektur139 gezielte räumliche/strukturelle/Modell-/Chatfälle bestanden. Diese überlappenden Sätze nicht addieren.
* Alle217 registrierten Werkzeugschemas statisch im neuen Protokollpfad geprüft:0 ungelöste Referenzen, keine Inferenz oder Projektänderung; DB-Ziel deaktivierter Loopback-Port1.
* Echte lokale Llama3.1:8b-Proben: zwei vollständig quellengebundene kleine Dokumente (Temperatursensor/Robotergreifer), tatsächlicher erzeugter Funktionscode mit fünf separat vorgegebenen Grenzwertfällen und begrenzter Laufzeitausführung; normaler nativer lesender Werkzeugvorschlag mit unverändertem131072-Kontext. Keine vorgeschlagenen Werkzeuge tatsächlich ausgeführt.
* Echte finale schema-gebundene Llama-Antwort13.08s: ausschließlich die erste Capability-Ablehnung wurde simuliert; danach genau eine echte Ollama-Completion, gleiches Modell, unverändert131072/1600. Andere Familien wurden mit kontrollierten Metadaten/Providerantworten geprüft und nicht aktiviert.

## Produktive Auslieferung

Session 44777 ist regulär mit Exit 0 und DEPLOYED beendet. Receipt: `backend/test-output/release-gates/delivery-9ba63de4dd43/cd21261e671d/receipt.json`, vollständiger Status PASS. Quelle `c375c4eef57b0a202369f2b354737a8d4f705a38a9868228322c4d619a80fb8f`, Verification `b338f30edeb7e9f13f87fd1e47fc686895b2f36701b669382b3e26d3be266dc1`, Git-Basis `99f89a1eb177e6135c4a420a6f16c97bd751d40a`.

Der kanonische Befehl `scripts/release-and-deploy.py` hat das normale Image `sha256:3c7d7baac3403bdfa63cf02c7c0245551738ee570fb1d59fd2cb27439e36478c` übernommen. Der einzige neu gebaute Kandidat dieser erfolgreichen Runde wurde anschließend unverändert getestet und ausgeliefert. Die ursprünglichen FAIL-Nachweise bleiben erhalten; Images wurden nicht bereinigt.

Alle acht Gate-Schritte bestanden: 38 Speicher-/Releasewerkzeugtests, TypeScript, 721 Frontendtests, 22.670 Backendtests mit zwei übersprungenen Fällen und 56 bestandenen Subtests, Produktionsbuild, 121 Browserfälle sowie kleine und große HTTP-Prüfung. Die Backendrunde dauerte 3352,68 Sekunden, die Browserrunde 51,3 Minuten. Überlappende gezielte Prüfsätze werden nicht dazuaddiert.

Beide HTTP-Fälle haben gespeicherte ALL-Scope-Abdeckung, PASS-Konformität und null fehlgeschlagene Routen. Im großen Fall wurden 766 Routen und 1169 Signale bewertet; die vollständigen gespeicherten Transportausschlüsse und Warnungsfreigaben stehen im unveränderten `large-http.json`. Diese isolierten strukturierten Vorgaben sind keine Fahrzeug-/Robotik-Originalabnahme und keine Hardwarequalifikation.

Vor und nach der echten Modellprobe wurden dieselbe laufende Image-ID, Quelle, tatsächlich konfigurierte Haupt-/Fastmodelle `llama3.1:8b`, Readiness und Frontend lokal sowie über `192.168.178.10:13500` geprüft. Das registrierte Nutzerprojekt ist kanonisch `network-project-20261105153906213-bb2b7f6d`; die Browseradresse verwendet `project=20261105153906213-bb2b7f6d`.

Die echte Produktprobe dauerte 22,648 Sekunden: quellengebundene Dokumentinterpretation, nativer lesender Werkzeugvorschlag, erzeugter Funktionscode, fünf unabhängig vorgegebene Grenzwertfälle und begrenzte ECU-Laufzeitausführung bestanden. Die vorgeschlagenen Projektwerkzeuge wurden nicht ausgeführt; es wurden keine kanonischen Projektmodelle geschrieben. Rohantworten, Ausführungscode, regulärer Exit 0 und Hashbindungen sind in `production-probe.*` und `production-probe-process.json` gesichert. Andere Modellfamilien wurden mit kontrollierten Metadaten/Antworten geprüft, nicht real aktiviert; daraus folgt keine pauschale fachliche Garantie für jedes LLM.

Nach regulärem Anfrageende wurde der tatsächliche Haupt-Ollama PID 46668 mit seinem direkten Worker PID 26092 dynamisch ermittelt; dessen Slot auf Port 64201 war bei der Messung idle. Die Windows-Verbindungsabfrage hatte den Listener zuvor nicht aufgelistet; aus dieser fehlenden Auflistung wurde kein Prozessende abgeleitet. Es wurden keine privaten Provider abgefragt oder Prozesse verändert.

Alle acht eingefrorenen Änderungsdateien stimmen am ausgelieferten Abschluss weiterhin mit ihren Hashes überein. Die fünf Auftragsziele und fünf Validierungsanforderungen sind mit tatsächlichen Nachweisen im Workload belegt. Die abgesagte alte Originalkampagne bleibt davon getrennt. Kein Shutdown.
