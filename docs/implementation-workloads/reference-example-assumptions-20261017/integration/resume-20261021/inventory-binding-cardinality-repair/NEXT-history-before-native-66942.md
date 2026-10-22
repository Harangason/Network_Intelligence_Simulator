## Verwaiste Ressourcen vollständig gesichert und stillgelegt

32 Runtimevolumes (25.025.054.720 Archivbytes, vollständige Dateihashes) und3 leere Testnetze sind nach frischem Referenz-/Identitätsabgleich einzeln entfernt. Kein Image wurde dabei entfernt. Archivierung60762 stoppte nach fertigen Sicherungen vor jeder Entfernung an einem Metadatenfeld; geprüfte Fortsetzung20657 endete mit Exit0 und vollständigem Retirementbeleg. Produktion/DB/Rollback und Receipts unverändert. Normale Vorbereitung99722 läuft jetzt; kein zweiter Prepare/Build. Details: orphan-retirement-result.json.

## Fortsetzung: reguläre Vorbereitung99722 läuft

Die gezielten103+155=258 verschiedenen Fälle aus zwei Läufen sind bestanden.
Die getrennte Hostbereinigung ist abgeschlossen:26 alte vollständig archivierte
PREPARED-Images und28 gestoppte Testcontainer entfernt,73 Images geschützt.
Die38 Hostwerkzeugfälle und die echte lesende Wiederverwendung/Sperrprüfung
sind bestanden. Diese38 sind keine zusätzlichen Original-/Modellfälle.

Der eigene überholte6d6-Teststack wurde danach vollständig gesichert und exakt
stillgelegt. Frischer Custom-Dump149254Bytes mit geprüftem Inhaltsverzeichnis,
Laufzeitvolume mit Dateihashes, Logs, normale Exporte beider Projekte und ein
vollständiges23Blob-Imagearchiv liegen recoverbar vor. Das6d6-Image und sein
ursprünglichesPREPARED-Receipt sind erhalten. Produktion3792, Produktdatenbank
und Rückfallimage blieben identisch. Siehe retire-6d6-stack/retirement.json.

Die vorherige Vorbereitung90140 stoppte vor jedem Build wegen der geänderten
Host-Verification. Originalfreeze113c bleibt separat erhalten; die unveränderte
Quelle61c7649a933d/HEAD70f ist mit den38 geprüften Hostwerkzeugfällen an
Verification6a937cf1717f gebunden, ohne Budget-/Gate-/Sperrumgehung. Siehe
host-verification-reconciliation.json. Keine neue menschliche Freigabe fehlt.

Aktuell läuft genau eine normale Vorbereitung:Session99722, prepare_candidate.py,
offizielles scripts/run-release-gate.py --prepare. Freeze/log/result stehen hier,
Ausgabe backend/test-output/release-gates/joint-single-inventory-originals-61c7649a933d.
Keinen weiteren Build/Prepare/Test/Originalrequest parallel starten. Zuerst
Prozess und candidate-prepare-result.json sowie das tatsächliche Receipt prüfen.
Nur terminales Ergebnis samt Prozessende zählt. Vor Folgearbeit Monitor pausieren.
Ein PREPARED-Ergebnis ist weiterhin kein vollständigerPASS.

Danach den bestehenden Source-only-API-Transfer mit --inventory-cardinality-repair-dir
auf das tatsächliche neue Receipt ausführen;16Antworten/2Importrequests unabhängig
hashen und die Child-Operator-Evidence sichern. NeueStates native-single-choice-*
behalten die unveränderten Originale und die tatsächliche historische36f-Qwen-
Intakeherkunft. Erst nach neuer EIP-/Provider-/Produktqueue-Prüfung echte frische
Originalreferenzoperationen beginnen; keine Wiederaufnahme interner Inventare.
Dann beide vollständigen Modelle/ALL-Simulationen und alle15/15 Pflichtziele,
vollständiges finales Releasegate und exakt getestete produktive Übernahme.

## Aktueller Fortsetzungspunkt: Sicherung verwaister Testressourcen60762

103+155=258 verschiedene gezielte Fälle aus zwei Läufen bestanden; beide
vollständigen Originalabnahmen/Modelle/ALL-Simulationen und volle Lieferung offen.
Die Hostbereinigung und38 Hosttoolprüfungen sind abgeschlossen. Der eigene6d6-
Teststack ist vollständig gesichert und exakt stillgelegt, Image/Receipt erhalten.
Verification wurde ohne App-/Gitänderung nachvollziehbar auf6a937cf1717f gebunden.

Die anschließende normale Vorbereitung57322 endete mit Exit1 vor jedem Build:
Die neue Schutzprüfung erkannte weitere verwaiste Ressourcen ohne Container.
Alle drei Dateien der Vorbereitung sind unverändert in prepare-attempt-57322
gesichert. Keine neue61c-Kandidatenimageidentität und keinPREPARED/PASS behaupten.

Jetzt läuft ausschließlich Session60762, retire_orphan_resources.py:
32 exakt inventarisierte unbenutzte disposable-Testvolumes und
3 leere Testnetzwerke. Alle Volumes werden erst vollständig
aufF archiviert und pro Datei gehasht; vor jeder Einzelentfernung erneut alle
laufenden/gestoppten Referenzen, Identität/Erstellzeit, Labels und Schutzobjekte
prüfen. Keine Images oder fremden Ressourcen werden entfernt. Der Operator
hält die kanonische Gatesperre; kein zweiter Archivierer/Test/Build/Originalrequest.
Fortschritt, geringeCPU oder fehlender Toolhandle beweisen kein Ende.

Zuerst kompakt tatsächlichen Prozess60762 und retire-orphan-resources/retirement.json
prüfen. Terminaler Beleg, tatsächliches Prozessende und normaler Exit müssen passen.
Bei normalem Ende Monitor vor Folgearbeit pausieren. Bei Fehler zuerst tatsächliche
Teiloperationen/Archive/Identitäten abgleichen, keinen unkontrollierten Neustart.
Details und Hashbelege: checkpoint-orphan-retirement.json.

Nach geprüftem Ende:57322-Versuch erhalten, nur dessen bereits archivierten
alten candidate-prepare-result.json-Marker entfernen und einmal die bestehende
prepare_candidate.py normal aufrufen, falls kein neuer Prozess/Output besteht.
Kein neuer Outputpfad, Developmentbase oder Umgehen der Schutzprüfung.
Danach der bekannte Source-only-API-Transfer auf das tatsächliche neue Receipt,
16Antwort-/2Importrequesthashes und tatsächliche36f-Intakeherkunft, frische EIP/
Provider-/Produktqueueprüfung und echte neue native Originaloperationen.
Alle15Outcomes/15Validations und beide vollständigen Originale bleiben Pflicht;
erst vollständige Modelle/ALL-Simulationen, vollständiges finales Releasegate
und exakt getestete produktive Übernahme, dann Abschluss und Automationen löschen.
Produktion3792 enthält die neuen Korrekturen weiterhin nicht.

## Aktueller Stand nach den gezielten Regressionen

103 Reasonerfälle (Session63080) und155 angrenzende Referenzfälle
(Session64221) bestanden jeweils mit Exit0 und finalem XML;258 verschiedene
Fälle in zwei getrennten Läufen. Beide Originalabnahmen, gespeicherte Modelle,
ALL-Simulationen und vollständiges Releasegate sind weiter offen.

Die normale Vorbereitung90140 endete mit Exit1 vor jedem Build: Die
Anwendungsquelle61c7649a933d und HEAD70f sind unverändert, die parallel
überarbeiteten Host-Releasewerkzeuge änderten jedoch die Verification-Identität.
Der strikte Freeze hat das korrekt erkannt. Der ursprüngliche Freeze bleibt
erhalten. Keine neue Kandidatenvorbereitung, doppelte Bereinigung oder Umgehung
der neuen Stack-/Sperrregeln. Zuerst die laufende, getrennt belegte Bereinigung
test-stack-retention-20261021 abschließen lassen und deren Ergebnis prüfen;
danach den überholten6d6-Teststack vollständig sichern und exakt stilllegen,
die Host-Verification nachvollziehbar neu einfrieren und einmal normal vorbereiten.

Die konkrete75ccb-Entfernung ist bereits vollständig belegt und abgeschlossen;
sie ist keine ausstehende Nutzerentscheidung. Produktion3792 enthält die neue
Korrektur weiterhin nicht. Details: candidate-prepare-identity-stop.json.

# Continue after adjacent reference regressions

Only this NIS chat, no new chats/subagents; archived peers remain resting. Canonical root I:/PycharmProjects/My_first_Network_Simulator. Read AGENTS.md, parentTODO/integration/workload.json (all15outcomes/15validations), thisworkload.json, REPORT.md, checkpoint.json and parentintegration/resume-20261021/checkpoint.json. Do not lower gates or alter configured model/context/output/time limits.

Actual vehicle61930 is naturally terminal INVALID_INPUT (trace be55620d-8148-49e0-8db9-c8e386efe4a9), driver exit1 and both processes ended. Native failure is inventory binding uniqueness, not yesterday usercancel89974 or contextfailure50908. Complete raw final choices were not retained: exact duplicate-versus-unknown native key is unproved. Normal postfailureGETcapture vehicle/terminal-61930 confirms empty canonical tables/no jobs. No originalmodel or simulation succeeded.

General private decoder cardinality mismatch reproduced independently: authored fixture repeats existingID, decoder accepts, strict expander rejects sameerrorfamily. Five new cases were RED. Fix emits atmostone native choice per response; unchanged normal continuation still covers all source/function/requirement scopes and additional devices. Specific unknown/duplicate-ID retry feedback, public/merge/identity validators unchanged. source-scope-proof.json proves all other top-level AST and whole reasoner class except intended prompt text unchanged; no model/provider/context/output/time/gate changes. Native effectiveness not yet proved.

Fresh frozen Source61c7649a933dc0fae72c85586bb07db43a4875ec3ed0fc09a97cca52050b89fc, HEAD70f0c160bc4f08bd23437f6b3c175523d1e5859c, Verification113c1455b50a4c3ad3135bb18af17fb3e57b5a7500283c4f288c30aca05d43aa. All103reasoner cases PASS in session63080 exit0, reasoner-regressions.xml/result.json. Current ONLY active test session64221 runs scripts/run-isolated-tests.py on tests/test_reference_design.py, test_reference_design_integration.py, test_reference_model_persistence.py; expected155cases, XML remaining-reference-regressions.xml. First verify real process, finalXML, exitcode; never start duplicate tests. While running no new inference/build/release/source edits. On final success save exact counts/exit/hash with same keys as reasoner result in remaining-reference-regressions-result.json. Aggregate258distinct cases in TWO disjoint runs, not a single258/258run. On failure inspect and repair actual cause within authorized scope, no softened assertions.

Storage is resolved for one normal newcandidate: user answered call_a295ed36b3e640bea8bb3a1080cd2f81 with verbatim ja alle alten images. Exactly75ccb was freshly23-blob/archive/tag/all-container/production/rollback checked then removed with --no-prune. Archive retained onF, actual imagecount99, see archive-review-75ccb83f4e33/authorized-removal.json. Never repeat removal. User broader old-image cleanup instruction saved old-images-user-authorization.json; any further cleanup must remain audited/recoverable and protect production, rollback, containers and PASS/active/unknown status under AGENTS/release_storage. No force or bulk prune.

After completed155PASS and fresh unchanged source/identity, run existing local prepare_candidate.py ONCE. It validates103+155results and frozenhashes, then official scripts/run-release-gate.py --prepare with normalDockerfile, no developmentbase or modified source/runtime budgets. Output backend/test-output/release-gates/joint-single-inventory-originals-61c7649a933d; freeze/log/result in thisfolder. Inspect an existing prepare instead of duplicating. Disk20GiB and imagebudget gates must hold. If truly blocked report exact evidence, no workaround build. PREPARED is not fullgatePASS or delivery.

The existing normal source-only transfer helper is extended by an explicit evidence option; it retains all original isolation/model-empty/provenance assertions. Run integration/resume-20261020/document-stream-lifecycle-repair/transfer_waitress_source_only_projects.py --receipt <actual newPREPAREDreceipt> --inventory-cardinality-repair-dir <thisfolder> --destination-prefix native-single-choice. It binds current proof/freeze to exact preceding39fcontext before/after snapshots; public source/Intake dependencies remain verified. Save actual16response/2importrequest hashes and child transfer-operator-workload evidence; no forgedsuccess or modelrows. New states integration/native-single-choice-{vehicle,robot}/state.json preserve exactoriginalIDs/bytes and old36factualQwenintakeorigin, no freshfull61cintakeclaim. Never mutate existing user models or import generated replacement designs.

EIP explicitly returned inference today after canonical preload07:30:16; NIS owns it. Check newer messages/real provider activity before native requests. No privateEIPprovider/restarts. Direct coordination thread01a11fb3-c627-7580-8623-9220505981fd authorized. Only localqwen3.8:27b. Small grammar/compiler probes may be reused with exact current schema and explicitly fixture-only scope; never call those originalmodel/simulationPASS.

Then ordinary fresh native vehicle plan-reference via existing native_original_document_driver.py using newstate, retain oldfailedrequests as evidence. One modelrequest atatime. When request is long-running, update silent monitor to exact process/state and pause it before following terminal work. No partial-inventory resumption or fabricated accept. Inspect actual completed proposals fully, normal hashbound review/accept/start/apply/continue via native_original_workflow_driver.py; genuine unresolved decisions ask human and continue independent work. Both unchangedoriginals required: Fahrzeug komplett.txt project20261018160006106-ee6625c9 and D_INDUSTRIAL_ROBOTICS_054_063.md project20261018160157264-5f0fa2a4. Robot all10profiles/221reviewedfacts/110REQlines, corrected readonly root/verify_robot_saved_model.py with exact reviewed-intake/hash. Cameraobjects to realADAS, PDCmeasurement sources,HMI and completeSensor-Processing-Consumer-Control-Command-Actuator-Feedback. Gateway transport only. Neu9/useranswers fieldscoped, not primarycounts. No manualmodels/routes/signals/ports/parameters/SQL corrections or fabricated hardware/safety/WCET/timing evidence.

After both actual complete saved canonicalmodels/ALLScopeSimulation jobs/snapshots/PASSconformance/0failedroutes/fulltraces, run all mandatory checks/fullreleasegate on exactfinalnormalimage. Then scripts/release-and-deploy.py with complete matchingPASSreceipt until authorized productive delivery; verify running image, health and affectedfunction. Production3792 stillhealthyunchanged, repairs notproductive. Save all15/15 evidence/completionguard. Only then publishcompletion, endworkfor theday and delete continuationautomations. No PCshutdown withoutnew request. Only meaningfulnewerror/requiredhuman action/actualcompletion NOTIFY; unchanged active/waiting DONT_NOTIFY.
