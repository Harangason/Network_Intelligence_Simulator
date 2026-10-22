Aktualisierung: Eine der 16 offenen Zuordnungen ist bereits ausdrücklich in der Quelle belegt: Fahrdynamikregelung→CDC. Die allgemeine NIS-Korrektur ist lokal geprüft, aber noch nicht ausgeliefert. Details und neuer Release-/Speicherstand: ../document-function-owner-cross-reference-20261017/REPORT.md. Die bisherige Aussage einer reinen Eingabesperre ist dadurch überholt. Vorhandene physische Quellenanforderungen werden bewahrt; sie sind keine bestätigten Port-/Kodierungsentscheidungen.

# Fortsetzung: Produktiver NIS-Code fertig, Fahrzeugtest benötigt Fachangaben

- [x] Genau freigegebenes Image07cb57d47f91 nach frischem Audit entfernen; Vollarchiv behalten.
- [x] Originalfahrzeug und Originalrobotik auf unverändertembe823/EA-Image echt nativ prüfen und regulär übernehmen (isolierter gemeinsamer Prüfstack, danach nur eigene Ressourcen entfernt).
- [x] Vollständiger Gate-PASS b53e295b15bd:28Storage,Typecheck,673Frontend,22082Backend+56Untertests (2skip/1Warnung),119Browser,kleine/großeHTTP,finalerQuellenabgleich.
- [x] Genau getestetesImageeaab97030ad994dc8a00e8fc6f38ada67c38e915e316deda63d231902843537b produktiv übernehmen. Sourcebe82385a9aab125ae8a296d1f1df1698551e44241bf3d1c1984dc7837ecff897. Unabhängige eigene4undPeer16Datei-/Image-/Readyprüfungen PASSED.
- [x] Produktiver Originalfahrzeuglauf mit unveränderter19088ZeichenDatei undwörtlichemHuman-HMI-Zusatz: Native2voll14Abschnitte,80/80unchangedHandoff,168volleREQ/38Funktionen/5Controller/73Sourceunits. ErsteVariante mit eigener fälschlicher Metadatenüberschrift NICHTübernommen, Belege unverändert; nurCaptionnormalentfernt, keineModelldatenpatches.
- [x] NIS selbst22Sourcehosts übernehmen lassen (4ADC); nurHumanminimum1je6Sensor-/3Aktortyp plusMindestumfangflag,3NIS-Vorschläge bestehenderOverviewabdeckung bestätigen. Kein anonymer Zusatzcontroller.
- [ ] Offene physischeHMI-Stückliste/Integration beantworten lassen. HumanFunktionen sindbekannt,physischerUmfangunbekannt; bereitsgezielt gefragt.
- [ ] BestätigteI/O-/Funktions-/Referenzspezifikation klären:15nicht exakt belegteHosts plus eine belegte Produktlücke,12Anschlüsse,Radar/UltraschallMessgrößen,3Aktorkodierungen. PassendeZusatzdateiRechtslenkerliefertkeinefehlendenAngaben undistnichtübernommen. Quellen-/ReferenzfragebeimMenschenoffen.
- [ ] RegulärenNIS-Auftrag erstbei erfülltenGates starten. TatsächlichenAPPLIED-Modellvorschlag mitsource_versions/canonical_ids/Evidence exportieren; alle168OriginalREQ und38Funktionen/Geräte/Relationen im gespeichertenModell nachweisen. Aktuell0kanonischeObjekte/9EMPTY/0Jobs.
- [ ] Vollständiger normalerWorkflow Routing/Netzwerk/Physik/Parameterherkunft/Capacity/Preflight bisgespeicherterSimulation. ObjektdatenPosition/Geschwindigkeit/Klassifikation, fachlicheEmpfänger,StellbefehleundAktor beobachten; GatewayersetztkeinenEmpfänger; keineerfundenenDefaults.

AktuellerBericht: production-be82385-20261017-attempt2/report.md. Startsperre: workflow-blocker.json daneben. TatsächlichesProjekt20261016122109077-dc3a1aeb, Tab3imWizard bleibtzurFortsetzungerhalten. NativequellenevidenceistPASSED, Originalmodell-/SimulationsabnahmedagegenINPUT_REQUIRED. KeinGesamtCOMPLETED/SimPASS.

Qwen-Slot nachNative2explizit anChat01a143e7-705b-74f0-b43c-f7b2a1f9c707 zurückgegeben. PeerRobotikwartetebenfallsaufSource-/Menschenangaben undstartetkeineunklareNeuinferenz. VorweitererInferenz/abhängigemModelllauferneutSlotabstimmen. KeineApp-/Test-/MappingänderungseitSourcefreeze.
