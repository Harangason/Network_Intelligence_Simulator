# Wizard-Schritt 1: Regressionsaudit vom 30.09.2026

## Beobachtung und Ursache

- Markierung: `Projekt benennen` im Projekt `20260930050829705-c5f86f1d`. Die vier Formular-Karten beanspruchen nur etwa 720 px der deutlich breiteren Wizard-Fläche.
- Im laufenden Image `sha256:d84b5612943f5616e6ca6a24485ce79829cb9694e102807aff1cd75c5d93660d` enthielt `frontend/src/app/globals.css` wieder `.agent-project-name-step > label { max-width: 720px; }`.
- Die bereits korrigierte kanonische CSS-Fassung setzt `min-width: 0; width: 100%; max-width: none`. Beim letzten isolierten Release wurde stattdessen das ältere CSS des Wizard-Kandidaten kopiert. Der zugehörige Browser-Breitentest war nicht im Release-Worktree. Das vollständige Gate konnte diese Regression daher nicht erkennen.
- Der Screenshot allein belegt keinen Verlust der Projektbeschreibung. Die API des markierten neuen Projekts enthält als Projektname `Neues Projekt`; ein bestätigter Wizard-Auftrag liegt noch nicht vor.

## Audit der zuvor behandelten Änderungen

| Bereich | Stand im letzten Produktimage / korrigierten Release-Worktree |
| --- | --- |
| Breite der vier Karten in Schritt 1 | Im letzten Produktimage rückläufig; CSS korrigiert und bestehender Playwright-Fall `project naming form cards use the full wizard width @layout` in den Release-Worktree übernommen. |
| ECU- und Aktor-Erkennung nach Textkorrektur | `engineering-specification.ts` im Release-Worktree identisch zum kanonischen korrigierten Quellstand. |
| Bewahrung geprüfter Geräteangaben, konkrete Fehlermeldung bei Katalogfehler | `agent-chat-core.tsx` und `agent-run-status.ts` im Release-Worktree identisch zum kanonischen korrigierten Quellstand. |
| Sequenzdiagramm, Trace-Ansicht, Next-Konfiguration aus dem vorherigen Produktimage | Die vier betroffenen Dateien sind gegenüber dem vorigen Produkt-Snapshot bytegleich. |
| Technologieprofile für SOME/IP sowie I2C/SPI | Waren im vorigen Produktimage noch nicht enthalten. Die branchenneutrale Formularlogik aus `backend/app/simulation_service.py` wurde in den neuen Kandidaten übernommen; 33 isolierte Zieltests bestanden. |
| Automotive-Empfehlung für lokale I/O-Busse | Die uncommittierte Änderung wurde nach Nutzerkorrektur im kanonischen Quellbaum entfernt und wird nicht in den Release-Worktree übernommen. Industrie und bestätigter Bustyp bleiben getrennte Entscheidungen gemäß `docs/GENERATION_RULE_MANAGER.md`. |

## Release und Produktprüfung

- Der erste Release-Versuch `aa12bfaa7db1` scheiterte an zwei Technologieprofiltests, weil deren Implementierung zunächst nicht mitkopiert war. Seine FAIL-Quittung wurde nicht deployt.
- Der anschließende vollständige Gate-Lauf `4cd07c194bc7` bestand alle acht Prüfungen. Sein Receipt liegt unter `F:\CodexOrdner\worktrees\wizard-repair\My_first_Network_Simulator\backend\test-output\release-gates\4cd07c194bc7\receipt.json`. Ergebnis: 3033 Backend-Tests bestanden, 3 übersprungen, 74 Browser-Tests bestanden; auch der Wizard-Breitentest bestand.
- Genau das geprüfte Image `sha256:2563b194bce5247c7cb06e183e79d51a6d52eb569286375b12157eb46625ddb4` wurde per PASS-Receipt produktiv gestartet. Laufendes Image, Build-ID `4dd05b68dd4e`, Health und `/api/ready` wurden abgeglichen.
- Eine separate Browserprüfung am produktiven Projekt `20260930050829705-c5f86f1d` ergab für das Fieldset und jede der vier Formularkarten 1147 px Breite; das berechnete `max-width` ist `none`. Der vorhandene Nutzertab blieb unberührt.
- Die produktive `/api/technologies`-Antwort enthält keinen der lokalen I/O-Busse I2C, SPI, UART, GPIO, PWM, ADC oder DAC in `automotive.recommended_technologies`.

## Nachweisgrenze

Die Dateivergleiche prüfen die benannten Bereiche, nicht jede historische Änderung im gesamten Repository. Der Release-Gate-PASS und die produktive Browserprüfung belegen den korrigierten Wizard im ausgelieferten Image; sie sind kein vollständiger Rückblick auf sämtliche früheren Repository-Änderungen.

## Nachtrag: Container-Abgleich und erneutes Release

Ein anschließender Abgleich aller neun im Docker-Screenshot markierten E2E-App-Container deckte weitere kanonische Korrekturen auf, die im Image `4dd05b68dd4e` noch fehlten. Diese wurden mit den vorhandenen Regressionstests in den Release-Worktree übernommen. Das neue Gate `02f73c791176` ist PASS; das getestete Image `sha256:4e51c4392bb5c761e68c8c2c7ae1314e32cd966858aaaa0fac5b2cf3a9e2af46` läuft produktiv. Der vollständige Abgleich steht in `work/nis-container-correction-audit-20260930.md`.
