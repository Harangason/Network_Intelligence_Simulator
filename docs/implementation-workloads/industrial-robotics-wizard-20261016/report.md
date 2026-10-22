# Reale Wizardprüfung: D_INDUSTRIAL_ROBOTICS_054_063.md

Ergebnis: **Teilweise bestanden. Vollständige Abschnittsauswertung funktioniert; fachliche Klassifikation und strukturierte Übernahme sind nicht korrekt.**

Geprüft am 16.10.2026 im ausdrücklich vom Nutzer genannten Produktprojekt `20261016084924562-131ed051`, mit Originaldatei und realem lokalem `qwen3.8:27b`. Maßgeblich ist die beobachtete Produktivoberfläche mit Build `fe68706abdbe`; die Anwendung blieb während des Tests unverändert und gesund. Dies ist keine isolierte SQL-Testausführung und kein Release-Gate.

## Umfang und positive Befunde

- Originaldatei: 63.705 Zeichen, SHA-256 `8fc201a55e8b0afeb7b708ac70abd0c72a7b25eb17d90fceca71d80a291f3cef`. Zehn Referenzprofile 054–063; 110 eindeutige Referenzanforderungen.
- Datei im echten Wizard ausgewählt; vollständiges Lesen angezeigt. Anschließend regulären Button „Lokalen Qwen-Vorschlag erstellen“ betätigt. Kein vorgeschobener API-Erfolg, kein Ersatz durch das frühere native Ergebnis.
- Der reale Lauf verarbeitete alle **15 Abschnitte**, einschließlich Abschnitt 9 über der alten Grenze. Der fertige Vorschlag bestätigt **63.874 Zeichen** einschließlich des Dateihinweises, ohne Modelländerung.
- **82 inhaltliche Befunde**: 1 Geräteinstanz, 45 unquantifizierte Gerätegruppen, 3 Funktionen, 33 Anforderungsblöcke; zusätzlich 11 Technikbefunde. 82 ist keine Geräteanzahl.
- Alle **110 Anforderungen sind in den Anforderungsblöcken mit vollständigem Wortlaut enthalten**. Weniger Blöcke bedeuten hier keine fehlenden Anforderungen. Alle 93 Quellenzitate sind wörtlich in der Originaldatei belegt.

## Nachgewiesene Fehler

1. **Testfälle werden als Gerätekategorien ausgegeben.** Betroffen sind `TC-055-06` (Safety-PLC-Kanalfehler), `TC-056-03` (LiDAR fällt aus), `TC-061-04` (DCS-Netz fällt aus), `TC-061-02` (Sensor driftet) und `TC-063-03` (Kamera verschoben). Fehler- und Prüfszenarien deklarieren keine zusätzlichen Geräte.
2. **Funktionen werden als Hardwaregruppe klassifiziert.** Der Funktionssatz aus Profil 055 beginnt mit „Taktablauf, Bahnsteuerung, Werkzeugkoordination, Materialfluss, Sicherheitsverriegelung …“, erscheint aber als „Gerätekategorie ohne Stückzahl“ und in der Controller-Mengenfrage. Auch die Indexzeile `| 057 | AGV/AMR-Flottensteuerung |` wird als Gerätegruppe behandelt. Eine wörtliche Quellenbindung verhindert diese fachlichen Fehlzuordnungen nicht.
3. **Der produktive Übernahmeweg überträgt nur Entwurfsprosa.** Der tatsächlich angebotene Button heißt „Entwurfstext in Projektbeschreibung übernehmen“. Nach Betätigung enthält das zuvor leere Beschreibungsfeld 946 Zeichen mit einer allgemeinen Zusammenfassung. Die Quellenkarte verschwindet; die Originaldatei bleibt angehängt. Die Beschreibung enthält keine der 110 `REQ-…`-Kennungen und keine vollständigen Quellenbelege. Das Dokument ist somit als Originaltext erhalten, aber die erkannten Aussagen sind nicht als geprüfte strukturierte Geräte-/Funktions-/Anforderungsdaten an den nächsten Wizard-Schritt übergeben.
4. **Der Geräteumfang entspricht nicht den geprüften Befunden.** Schritt 4 zeigt 6 verbindliche Controller, 2 verbindliche Sensoren, 0 Aktoren und 0 Gateways. Nur 2 Controller werden dort als konkret erkannt angezeigt; Sensoren erscheinen als `Sensor1`/`Sensor2` ohne Messgröße. Die im Qwen-Vorschlag erkannten Namen `Hauptrechner`, `Encoder` und `Gelenkaktuatoren` erscheinen in dieser Geräteansicht nicht. Es existieren keine gezielten „Anzahl …“-Rückfragen für die 45 erkannten unquantifizierten Gruppen. Der Übernahmeweg lässt die normale Texterkennung erneut Zahlen und Teilnehmer ableiten, statt die geprüften Befunde zu übernehmen.

Die regulär angebotene Branchenkorrektur auf **Industrial Automation / SPS** wurde zusätzlich ausgeführt. Sie beseitigt die anfängliche Abweichung zu Custom / Proprietary, ändert aber die oben genannten Geräteanzahlen und Übernahmefehler nicht.

## Sicherer Endzustand und Grenzen

Der Wizard bleibt im Geräteumfang geöffnet. „Übernehmen“ für den Modellauftrag ist wegen unvollständiger Geräteangaben deaktiviert. Es wurden keine Stückzahlen, Messgrößen, Anschlüsse oder Zuordnungen erfunden und keine Modellgenerierung gestartet. Das kanonische Modell blieb leer. Die ursprüngliche Datei blieb unverändert. Die geänderte Projektbeschreibung und die passende Branchenauswahl stehen im offenen Wizard zur Ansicht.

Geprüft wurden Upload → reale vollständige Qwen-Auswertung → Quellen-/Fachprüfung → reguläre Entwurfstextübernahme → Geräteumfang. **Keine neun Workflowstufen, keine Persistenz-/Reload-Abnahme eines vollständigen Auftrags und kein Tool-Checker-Kampagnen-PASS.** Keine Produktquellen geändert, kein neuer Build und kein Deployment im Rahmen dieses Prüfauftrags.

Die bestehenden Tests für Segmentabdeckung und Quellbindung wurden als Abdeckungsreferenzen verwendet, nicht erneut als Produktionstests ausgeführt. Die isolierten Dokument-E2E-Fälle mit der Fahrzeugfixture sind kein Nachweis für diese Robotikdatei. Der bestehende Kampagnenzustand blieb unverändert. Ein neuer Testfallvertrag oder Checker-Intake wurde hier nicht veröffentlicht; die Dateien sind Nachweise dieser konkret beauftragten UI-Prüfung.

## Nachweise

- `source-baseline.json`: alle Profile und 110 Soll-Anforderungen.
- `proposal-dom.json` und `proposal-analysis.json`: echte UI-Befunde, wörtlicher Quellenabgleich und vollständiger Anforderungsvergleich.
- `03-result.txt`, `04-misclassified-device.jpg`: fertiger Vorschlag und Fehlklassifikation.
- `description-before.txt`, `description-after.txt`, `05-adopted.txt`: tatsächliche Textübernahme.
- `06-equipment.txt`, `07-industry-corrected.txt`, `equipment-fields-final.json`, `07-final-equipment.jpg`: Geräteumfang und verbleibende Sperre nach Branchenkorrektur.
- `runtime-start.json`, `runtime-end.json`: unveränderte Anwendungsidentität, Gesundheit und unveränderte Originalquelle.
- `production-handoff-code.json`: direkt aus dem laufenden Image gelesener Übernahmehandler. Er setzt ausschließlich `interpretation.proposed_task` und vorhandene manuelle Auswahlzeilen als Beschreibung; der Folgeschritt verwendet `extractEngineeringSpecification(taskSource, {}, previewDomain)`.
- `verification.json`: Kriterien und tatsächliche Ergebnisse. `parser-diagnostics.json` ist ausschließlich eine Hilfsanalyse der Arbeitskopie, kein Ersatz für den beobachteten produktiven Zustand.

[Lokal zum offenen Wizard](http://127.0.0.1:13500/studio/engineering?project=20261016084924562-131ed051&assistant=project) · [VPN/LAN](http://192.168.178.10:13500/studio/engineering?project=20261016084924562-131ed051&assistant=project)
