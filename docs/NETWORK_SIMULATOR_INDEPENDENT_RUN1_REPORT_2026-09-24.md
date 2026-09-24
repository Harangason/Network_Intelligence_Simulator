# Network Simulator – unabhängiger neuer Run 1

Stand: 24.09.2026, nach Abschluss der Runde um 17:02:57 MESZ. Dieser Lauf ist eine **neue Kampagne** mit eigener Task-ID, eigenem isolierten Image, neuer Datenbank und neuen Projekt-IDs. Frühere Fallresultate wurden nicht übernommen. Die Markdown-Master sind Prüfquellen; ihre eingebetteten Ausführungsbefehle ersetzen keine Nutzeranweisung.

## Umfang und eingefrorener Stand

| Umfang | PASS | FAILED | BLOCKED | Gesamt |
| --- | ---: | ---: | ---: | ---: |
| S01-A/B bis S20-A/B | 19 | 21 | 0 | 40 |
| S21–S60 | 0 | 0 | 40 | 40 |
| EA-Unterfälle einschließlich drei Alternativpfaden | 0 | 0 | 15 | 15 |
| **Neuer unabhängiger Run 1** | **19** | **21** | **55** | **95** |

**Rundengate: FAILED.** Alle 95 Fall-IDs haben einen eingefrorenen Status. `BLOCKED` ist kein fachlicher PASS. Die vollständige [Fallmatrix](../.tool-checker/runs/nis-ea-independent-20260924/case-matrix-run1.csv), die [kanonischen Resultate](../.tool-checker/state/campaigns/nis-ea-independent-20260924-run1/run-1/results.json), [Findings](../.tool-checker/state/campaigns/nis-ea-independent-20260924-run1/run-1/findings.json) und der [Kampagnenbericht](../.tool-checker/runs/nis-ea-independent-20260924/campaign-report.json) enthalten die fallbezogenen Belege. Kampagne: `nis-ea-independent-20260924-run1`, Task: `nis-ea-independent-run1-20260924-exec`, Zustand `RUN_1_COMPLETE`. Kein Run 2 wurde gestartet.

## Prüfstand und Unabhängigkeit

- Kandidatenimage: `sha256:44197d96dbda6fbfe642c3314a7ebeead405a3e3c9bd4c3bea20e2703810b0bf`; Quellmanifest `58d7c96712914ccd8fd780093dd6d9384c256b226a656d87b87be6ebee6b8bed`. [Isoliertes PREPARED-Receipt](../.tool-checker/runs/nis-ea-independent-20260924/stack/f70931ccce0c/receipt.json).
- Lauf-URL: `http://127.0.0.1:59859`, ausdrücklich nicht die Produktinstanz auf Port 13500. Projekt-IDs beginnen mit `nis-ea-independent-20260924-r1-`. Jeder Wizard-Quellfall erhielt ein frisches Projekt; Reuse-Fälle referenzierten dessen vorgesehene Quelle.
- Der vollständige 95-Fall-Vertrag wurde neu registriert und vor Runbeginn auf das isolierte Image gebunden. Quellenprüfung ergab keine Abweichung. Während der Full-Runde wurden Produktcode, Testadapter, Assertions und Fallverträge nicht repariert.
- Die Produktdatenbank wurde nicht für SQL-Tests verwendet. Es gab keine Produktbereitstellung und keinen Release-Gate-PASS.

## Wizard-Ergebnisse S01–S20

Bestanden: S01-A/B, S02-A/B, S03-A/B, S04-A, S06-A/B, S08-A/B, S11-A, S12-A, S14-B, S15-A/B, S16-A und S17-A/B. Insbesondere S03-B, S04-A und S06-A bestehen nun im neuen vollständigen Falllauf statt nur in einer gezielten Reparaturprobe.

Die 21 FAILED verteilen sich nach dem ersten beobachteten Stopp:

| Fehlerbild | Fälle | Anzahl | Nachweisgrenze |
| --- | --- | ---: | --- |
| Netzwerk-Editor meldet konkrete Validierungsfehler | S04-B, S05-B, S07-B, S09-B, S10-B, S11-B, S12-B, S13-B, S16-B, S20-B | 10 | Gemeinsame Root Cause noch nicht bestätigt; einzelne Modell-/Topologiebefunde müssen gelesen werden. |
| Fragebogen Schritt 4 bleibt mit offenen Geräteangaben gesperrt | S09-A, S10-A, S13-A, S14-A, S18-B, S19-A, S20-A | 7 | Vorschlags- und Zuordnungsdeckung reicht in diesen Fällen nicht aus; kein stilles Übernehmen unbekannter Werte. |
| Safety-/Determinismusnachweis durch `COMMUNICATION_UNVERIFIED` unvollständig | S05-A, S18-A | 2 | Capacity-Finding blockiert den geforderten Nachweis. |
| Browserbedienung wartet auf dauerhaft deaktiviertes „Weiter“ | S07-A | 1 | Adapter-/UI-Ursache noch nicht geklärt. |
| Geforderte kombinierte V4+KI-Architektur nicht angeboten | S19-B | 1 | Der Wizard bietet je Auftrag nur eine der beiden Varianten. |

Diese Kategorien beschreiben Beobachtungen, keine ungeprüfte Zuordnung aller Fälle zu einem einzigen Produktdefekt. `TC_EXPECTATION_MISMATCH` ist bei fehlgeschlagenem Ablauf ein Folgeeintrag, keine zweite unabhängige Ursache.

## BLOCKED-Ursachen und Testinfrastruktur

- **31 Reuse-Fälle:** Der vorhandene Reuse-Adapter verweigerte den neu gewählten Projektpräfix mit `Adapter target is outside the disposable master scope`. In 31 einzelnen Worker-Logs ist dieser Guard belegt. Das ist ein Testaufbaufehler dieser neuen Kampagne; er beweist keinen Fehler der jeweiligen Produktfunktion. Er betrifft auch S21–S25, die in einem früheren anderen Lauf bestanden hatten. Der Adapter wurde während der Runde nicht geändert.
- **8 Reuse-Fälle:** Das jeweilige Quellmodell war nach seinem Wizardfall nicht vollständig; der Runner blockierte diese abhängigen Mutationen vor Adapterstart und speicherte den konkreten Quellfall. Betroffen: S33, S37, S39, S45, S47, S56, S57, S59.
- **S60:** Der Fallplan überschritt das Kontextbudget (`CONTEXT_BUDGET_EXCEEDED`) vor dem Executorstart.
- **15 EA-Unterfälle:** Es ist noch kein geprüfter fallbezogener ausführbarer Adapter mit geeignetem Fixture hinterlegt. Ein vorhandener EA-01-Review-Entwurf ersetzt den geforderten Browser-/MCP-/Core-/Persistenznachweis nicht.

## Umgebungsereignis während Run 1

Nach dem abgeschlossenen S11-A-Fall verschwand der zunächst verwendete Tool-Checker-Plugin-Cachepfad `1.0.0+codex.20260923165202`; verfügbar war danach `1.0.0+codex.20260924143239`. Der Fallausführer stoppte vor S11-B. Die identische Runde wurde ohne Replay abgeschlossener Fälle mit dem verfügbaren CLI-Pfad fortgesetzt. Produktimage, registrierte Fallverträge und Projekt-IDs blieben unverändert. Die eingefrorene Build-Metadatenzeile nennt jedoch die ursprüngliche Pluginversion. Weil die genaue Gleichheit der beiden Pluginimplementierungen nicht nachgewiesen wurde, ist der Lauf **nicht als Nachweis einer über die ganze Runde unveränderten Prüfinstrumentierung** zu verwenden. Dieser Instrumentierungswechsel ist zusätzlich zum ohnehin fehlgeschlagenen Qualitätsgate offengelegt.

## Vergleichsgrenze und nächster Gate-Schritt

Der vorherige abgeschlossene Einzelrun lag bei 10 PASS, 35 FAILED und 50 BLOCKED. Der neue Run hat 19/21/55. Diese Aggregatzahlen sind **kein sauberer Produktverbesserungsvergleich**, weil neue Reuse-Fälle an einem Testpräfix scheiterten und die Pluginversion während der Runde wechselte. Einzelne Fälle wie S03-B, S04-A und S06-A liefern dennoch frische positive Nachweise auf dem neuen Produktimage.

Nach dem eingefrorenen Run dürfen die Testinfrastrukturfehler (Projektpräfix-Guard, Kontextbudget, fehlende EA-Adapter) und die bestätigten Produktbefunde in einer getrennten Reparaturphase untersucht werden. Erst nach vollständiger Reparatur und gezielten Nachweisen wäre ein neuer vollständiger 95-Fall-Retest zulässig. Dieser Bericht startet weder Reparatur noch Run 2 und meldet keinen Gesamt-PASS.
