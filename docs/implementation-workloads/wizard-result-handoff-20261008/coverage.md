# Ergebnisübergabe nach Wizard-Abschluss

Quelle: Nutzerauftrag vom 08.10.2026: bereits im Wizard ausgeführte Simulation nach Abschluss sichtbar halten.

Wiederverwendeter Testbestand: bestehender realer Neun-Stufen-Fall `new small wizard traverses all nine stages and survives reload/restart @small` in frontend/e2e/wizard.spec.ts. Keine zusätzliche Kampagne oder zweite Registry. Die registrierte Parameterrückkehr bleibt unverändert erhalten und wird um Assertions am bestehenden Abschluss erweitert.

| Kriterium | Quelle und Assertion | Prüfebene |
| --- | --- | --- |
| Erfolgreicher Abschluss öffnet genau den gespeicherten Snapshot | echte Finish-POST-Antwort, URL und aktiver Snapshot aus unabhängiger API | Browser/HTTP |
| Laufdaten bleiben sichtbar | Trace Events aus vollständigem Snapshot, PASS-Bewertung, Job und Snapshot-IDs in Simulation | Browser/HTTP |
| Reload benötigt keinen neuen Lauf | identische IDs und weiterhin genau ein Job | Browser/HTTP |
| Neue Browsersitzung ohne Session-Key | echter neuer Browsercontext öffnet Simulation ohne Snapshotquery | Browser |
| Reset leert nur die Ansicht | Reset/Reload: Start möglich, ursprünglicher Snapshot/Bewertung weiterhin in Results | Browser/HTTP |
| Keine projektfremden Ergebnisse | fremde explizite Snapshot-ID im anderen Projekt: verständlicher Fehler, kein aktiver Lauf | Browser |
| Historische Auswahl / Bewertung unverändert | explizite Auswahl, OUTDATED-Restoration, FAIL bleibt FAIL, Originalobjekt unverändert | Libraryregression |

Datenfluss: Finish-POST -> gespeicherter Workflowstatus -> projektgebundene Snapshot-Metadaten -> Ergebnis-URL mit Snapshot-ID -> vollständiger vorhandener Snapshot/Job -> Runtime/Bewertung/Trace -> Simulation-Link mit gleicher Snapshot-ID. Ohne Sitzungsdaten liest Simulation dieselben projektgebundenen Records; kein Create/Start-Aufruf. Project-ID wird über zusammengehörende Reads hinweg einmal erfasst.

Zu Beginn wartete der Nutzerauftrag 20261008035128534-d555f433 ohne Simulation auf Capacity-Review. Bei der Abschlusskontrolle war der Capacity-Vorschlag bereits übernommen und der Auftrag an sieben Ethernet-Preflight-Befunden in Validation angehalten. Es existieren weiterhin keine Simulationsjobs oder Snapshots in diesem Projekt. Der Auftrag wird nicht als abgeschlossener Live-Lauf ausgegeben. Die Prüfung hat ihn weder freigegeben noch als Prüfdatenbestand verändert. Die echte Neun-Stufen-Abnahme erfolgte isoliert; die Produktivprüfung blieb lesend.

Ausführungsstatus und Evidence werden in workload.json und dem vollständigen Release-Receipt festgehalten. Ein PREPARED-Stack oder gezielter Test ist kein Release-PASS und kein Kampagnenabschluss.

Abschluss: vollständiger Release-PASS für bd8d6bd22770, 593 Frontend-Tests, 21.726 Backend-Tests und 56 Untertests, 96 Browserfälle ohne Skip/Retry sowie kleine und große unabhängige HTTP-Abnahme. Zwei Backend-Tests sind übersprungen; eine vorhandene Pydantic-Warnung bleibt dokumentiert. Exakt dieses Image wurde an localhost:13500 ausgeliefert, Image-/Quellidentität und LAN-Erreichbarkeit bestätigt. Die Produktivoberfläche zeigt denselben gespeicherten Auftrag, freigegebene Parameter und den offenen Preflight-Stand. Results und Simulation wurden ohne neuen Job geöffnet. Abgeschlossene Laufanzeige/Reload/neue Sitzung wurden durch den echten isolierten Abschlussfall auf dem ausgelieferten Image geprüft. Die unabhängige Tool-Checker-Kampagne bleibt unverändert.
