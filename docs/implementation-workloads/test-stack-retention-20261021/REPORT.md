# Sichere Teststack- und Kandidatenbereinigung, 21.10.2026

28 alte gestoppte Testcontainer, 13 zugehörige Netzwerke und 13 zuvor gesicherte
Laufzeitvolumes wurden entfernt. 26 alte ausschließlich PREPARED-belegte
Kandidaten wurden vollständig archiviert und danach exakt mit --no-prune
entfernt. 99 NIS-Images wurden dadurch auf 73 reduziert; nur der aktuelle
Teststack 6d6fe881f4bd bleibt erhalten. Keine Force-/Prune-Bereinigung.

Die Sicherung umfasst ein gemeinsames 16.870.832.640-Byte-Imagearchiv auf F,
270 vollständig gehashte Index-/Konfigurations-/Layerbestandteile,
13 Laufzeitvolume-Archive, 28 Containerlogs und die unveränderten Receipts.
SHA-256-Nachweise, genaue Einzeloperationen und Wiederherstellungshinweise
stehen in image-archive-audit.json, stack-backup-audit.json,
removal-result.json und RESTORE.md. Bereits vor der Bereinigung verlorene
tmpfs-Datenbankinhalte werden nicht als gesichert behauptet; bestehende frühere
Dumps und Projektexporte bleiben erhalten.

Produktion bleibt auf Image 3792d2e086e4, Rollback auf 09d1f624dfdd mit geprüftem
vollständigem PASS. Produktionscontainer, Produktdatenbank und ihre Speicher
bleiben unverändert und gesund. Alle 73 geschützten Images einschließlich aller
PASS-Images, ungeklärten Historien und des aktuellen Arbeitskandidaten samt Tags
sind nach der Bereinigung erneut geprüft. Keine fremden Projektobjekte entfernt.

Die kanonischen Hostskripte wählen auch PREPARED-Images für exakt dieselbe
Anwendungsquelle/Git-Revision wieder aus. Direkte Gates und Lieferungen halten
eine gemeinsame Betriebssystemsperre. Wiederholte Vorbereitung nutzt den
gesunden identischen Teststack; abweichende oder alte erhaltene Stacks und
verwaiste Ressourcen verhindern einen zweiten dauerhaften Stack vor dem Build.
--no-reuse erneuert Tests, erzwingt keinen Image-Neubau. Fehlgeschlagene
Bereinigung erzeugt FAIL und sperrt weitere Gates bis zur Klärung.
AGENTS.md und WIZARD_RELEASE_GATE.md halten die Vorgaben zusätzlich fest.

38 Tests des Releasewerkzeugs bestanden, einschließlich echter
Prozesskonkurrenz, Freigabe der Sperre nach Fehler, Wiederverwendung, fremder
Datenbank-/Image-/Quell-/AI-Konfiguration und Sperre nach Bereinigungsfehlern.
Der echte aktuelle Stack wurde anschließend rein lesend als wiederverwendbar
bestätigt; eine abweichende Quelle wird vor einem Build blockiert. Die
Containerliste blieb dabei unverändert. Produktions-Readiness und Build-Info
lieferten HTTP 200. Syntaxprüfung und Diffprüfung bestanden.

Es wurden ausschließlich Hostwerkzeuge, Tests und Dokumentation geändert.
Diese Änderungen sind lokal unmittelbar wirksam und gehören nicht zur
Anwendungsimage-Identität. Kein neuer Build, kein Produktionsneustart, keine
Anwendungsbereitstellung und kein vollständiger App-Releasegate-Lauf wurden
ausgeführt oder behauptet. Bestehende andere Arbeitsänderungen bleiben erhalten.
