# Qwen: allgemeine Dokumentkorrektur

Sieben unveränderte Originaldateien wurden mit demselben Anwendungsstand und echtem lokalem Qwen erneut geprüft. Keine Dateinamen-Sonderlogik, kein Cloud-Fallback, keine kanonischen Modelländerungen.

| Projekt | Ergebnis | Abschnitte | Modellaufrufe | Sekunden |
|---|---|---:|---:|---:|
| Intelligentes HLK-Regelsystem.txt | bestanden | 1 | 1 | 176.26 |
| Chemieanlagen-Modul.txt | bestanden | 1 | 1 | 150.26 |
| Kollaborativer Roboterarm.txt | bestanden | 1 | 1 | 142.93 |
| Infusionspumpe.txt | bestanden | 1 | 1 | 148.39 |
| 5G-RAN-Komponente.txt | bestanden | 1 | 1 | 148.27 |
| Satelliten-Avionik.txt | bestanden | 1 | 1 | 184.51 |
| Mobiler Service‑Roboter mit Greifarm und 360°‑Sensorik.txt | bestanden | 2 | 3 | 932.13 |

Modell: `qwen3.8:27b`, 9 echte Aufrufe, 6358 Ausgabetokens. Original- und übertragene Quellen sind vollständig und hashgeprüft. 1 automatische lokale Korrektur innerhalb der bestehenden Quellenprüfung; keine manuell ersetzte Modellantwort.

Abnahme: Gerätearten und konkrete Instanzen getrennt; Controllerrollen erhalten; Sensorik/Aktorik und Funktionsgruppen vollständig; sämtliche expliziten Anforderungen erhalten; offene Protokollfamilien bleiben klärungsbedürftig. 121 gezielte Regressionstests bestanden.

Dies prüft Dokumentaufnahme und Vorschlagserstellung. Es sind keine sieben vollständigen Engineering-Workflows mit neun Stufen. Release und Produktivprüfung werden separat nachgewiesen.

Zusätzlicher Release-Befund: Kurzzeitige Windows-Sperren beim atomaren Speichern konnten echte Schreibvorgänge mit HTTP503 abbrechen. Der zentrale Speicherhelper wiederholt ausschließlich Windows-Zugriffs-/Sharing-Sperren begrenzt (höchstens1,575s); atomarer Austausch, bisherige Inhalte, Bereinigung und dauerhafte Fehler bleiben abgesichert. 185 gezielte Speicher-/API-/Zielausführungs-/Simulations-/Dokumenttests bestanden, einschließlich9 neuer Regressionen. Die sieben nativen Dateien wurden danach vollständig auf diesem finalen Gesamtstand wiederholt. Alle fachlichen Ergebnisse sind identisch mit der bereits geprüften Abnahme (v6-v5-review-comparison.json).

## Produktivnachweis

Der vollständige Release wurde mit PASS abgeschlossen und exakt das geprüfte Image `sha256:96998221884773057e89efa677a8d234067cef829b9d9e92cd11084c4062e44a` produktiv bereitgestellt. Laufende Identität, Readiness und Quellhash wurden abgeglichen.

Die geänderte Dokumentfunktion wurde anschließend mit einem echten lokalen Qwen-Aufruf innerhalb des produktiven Containers erneut geprüft, ohne Datenbank- oder Modelländerung. Die Modulhashes stimmen mit dem siebenfach geprüften Stand überein.

Die Frontend-Technologieprojektion wurde über den vorhandenen Generator aus den zentralen Profilen synchronisiert (I²C/WLAN). 41 zusätzliche Projektions-/Registry-/Wizardtests bestanden. Die vier nativen Qwen-Modulhashes blieben dabei identisch.

- frontend-tests: # tests 643; # pass 643; # fail 0
- backend-tests: 21984 passed, 2 skipped, 1 warning, 56 subtests passed in 1822.70s (0:30:22)
- browser-e2e:   117 passed (54.4m)
- small-http: PASS laut vollständigem Receipt
- large-http: PASS laut vollständigem Receipt

Zusätzliche Abnahme: 185 aktuelle gezielte Regressionen; sämtliche 117 Browserfälle jeweils im ersten Versuch, ohne Skip/Retry; neun reale Parameterspeicherungen mit HTTP200 in4,0–14,0s. Beide HTTP-Workloads simuliert und bewertet:6/6 bzw.766/766Routen, keine fehlenden beobachteten Routen/Signale, ConformancePASS. Vorhandene fachliche Warnungen bleiben in full-http-audit.json sichtbar; dies ist keine reale Hardwarequalifikation.

Der vorangegangene Browser-FAIL durch ERR_NO_BUFFER_SPACE beim Laden eines JavaScript-Teils bleibt dokumentiert. Derselbe Ethernetfall bestand danach unverändert im frischen Browser und im vollständigen Release. Keine Produktsonderlogik, keine gelockerten Assertions oder Zeitgrenzen, keine automatischen Test-Retries.

Lokaler und LAN/VPN-Projektzugriff nach DeploymentHTTP200 und Ready; anschließend ein echter lokalerQwen-Produktivaufruf mit geprüften Modulhashes und ohne kanonische Modelländerungen.
