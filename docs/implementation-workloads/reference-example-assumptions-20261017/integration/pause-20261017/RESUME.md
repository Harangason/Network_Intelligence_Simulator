# Sicherung am Tagesende — 17.10.2026

Vom Nutzer ausdrücklich beendet: „beende für heute die arbeiten, sichere sie“. Keine automatische Fortsetzung und keine neuen Tests/Inference/Build/Deployment bis zu einer neuen Nutzeranweisung.

## Gesicherter Stand

- Kanonischer Code unverändert seit 159 Backend-/143 Frontend-Tests und Typecheck-PASS. Source `2d0d2b566456e5a8614b4cace16380ec0a3cb73525076fcf510ca8b0b538f0bd`, HEAD `70f0c160bc4f08bd23437f6b3c175523d1e5859c`.
- Exakt autorisierter Kandidat 66a892b0b219 entfernt; vollständiges geprüftes Archiv erhalten, keine weitere Löschfreigabe nötig für diese bereits abgeschlossene Aktion.
- Neuer normaler Produktionskandidat `networkis:candidate-d851f62a961b`, Image `sha256:0a191a95598704d2dc1c0f1a7060665b8c896bfdf8d36ec8a43a5daa1a6a5d74`, PREPARED-Beleg `backend/test-output/release-gates/reference-example-native-2d0d2b566456/d851f62a961b/receipt.json`. PREPARED ist kein vollständiger PASS.
- Neues tatsächlich von NIS angelegtes Fahrzeug-Testprojekt `20261017190202251-60e9cb65` / intern `network-project-20261017190202251-60e9cb65`, Name „TEST · Fahrzeug komplett · Referenzprüfung 2026-10-17“. Vollständiger Originalupload: 19.088 Zeichen, SHA `86865975c689643d9b07ea73e21d68fa6f4a3a8770402ffb537dba2d7ecdf4d7`. Native Qwen-Auswertung wurde gestartet, aber beim Stop keine fertige Modell-/Simulationsprüfung behauptet.
- GET-Snapshots von Workflow, Conversation, ReferenceRecord und Jobs sowie letzte App-Logs sind in diesem Verzeichnis gespeichert.
- Kandidaten-App `nis-e2e-app-d851f62a961b` gestoppt, dadurch keine weitere NIS-Inferenzanforderung aus diesem Prozess. Datenbank `nis-e2e-db-d851f62a961b` erst nach Backup gestoppt.
- Datenbank-Backup `candidate-database.dump`, SHA `66447085f307c4d22c20fcdeb21ea4fbb27105fe6a2c54471999473594bc788e`, 140.875 Bytes. Native `pg_dump --format=custom`; `pg_restore --list` erfolgreich geprüft, keine Restore-Prüfung ausgeführt. Laufzeitvolume `nis-e2e-runtime-d851f62a961b` bleibt erhalten.
- Produktion `NetworkIS` bleibt beim Image `sha256:3792d2e086e43af616d9fb63fd371c352fe101db5136b84f381cd9999363785b`. Keine neue Produktivübernahme.

## Nur nach ausdrücklicher Fortsetzung

1. Sicherungsdateihash und echte Container-/Imageidentität prüfen. Keine doppelten Prüfungen oder Inferenzläufe starten.
2. Die Testdatenbank verwendet tmpfs: vor Start der Test-App zuerst nur `nis-e2e-db-d851f62a961b` starten, PostgreSQL-Bereitschaft abwarten, den Custom-Dump in den Testcontainer kopieren und ausschließlich in `nis_test_e2e` mit dem nativen `pg_restore` wiederherstellen. Produktion niemals als Restore-Ziel verwenden.
3. Erst nach erfolgreicher Wiederherstellung die bestehende Kandidaten-App starten. Fester bisheriger Port 62721; tatsächliche Veröffentlichung und `/api/ready` prüfen. Lokaler Qwen-Endpunkt `http://host.docker.internal:11434/v1`, Modell `qwen3.8:27b`, Cloud-Fallback im Kandidaten deaktiviert.
4. Browser-Tab 5 gegebenenfalls noch vorhanden. Falls der nicht übernommene Dokumentbefund beim Stop verloren ging, die unveränderte Originaldatei im normalen NIS-Wizard erneut auswerten; niemals alte handgeschriebene Modell-/Referenz-JSON injizieren.
5. Beide Originale über NIS-generierte Referenzannahmen und normale Vorschlagsprüfung bis zu gespeicherter Simulation durchführen. `neu 9.txt` ausschließlich rollengetrennt als ergänzende Referenz, keine Übernahme ihrer Stückzahlen. Menschliche HMI-/Mindestsensoranforderungen liegen in den Vorläufer-Nachweisen.
6. Danach vollständiger Release-Gate am exakt gleichen Image, dann `scripts/release-and-deploy.py` mit dessen vollständigem PASS-Beleg und Produktionsprüfung. Kein Erfolg behaupten, solange Original-Modelle/Simulationen oder Gate/Produktivübernahme fehlen.
