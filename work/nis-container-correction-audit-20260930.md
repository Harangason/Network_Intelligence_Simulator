# NIS: Abgleich der markierten E2E-Container mit dem produktiven Build

Stand: 30.09.2026. Bezugsprojekt: `20260930050829705-c5f86f1d`.

## Identität und Umfang

- Im Screenshot sind neun gestoppte `nis-e2e-app-*` und ihre neun `nis-e2e-db-*`-Partner zu sehen. Die DB-Container enthalten isolierte Testdaten, keinen Anwendungscode; sie wurden weder gestartet noch verändert. Der unten sichtbare laufende `nis-test-db-5c08…` war ebenfalls eine Wegwerf-Testdatenbank und wurde vom isolierten Testlauf inzwischen entfernt.
- Die App-Container sind ältere, isolierte Teststände vom 25. bis 29.09.2026. Der produktive Container `NetworkIS` verwendete zu Beginn der Prüfung `sha256:2563b194bce5247c7cb06e183e79d51a6d52eb569286375b12157eb46625ddb4` (Build `4dd05b68dd4e`).
- Alle neun App-Dateisysteme wurden lesend inventarisiert. Bei sechs älteren Containern sind die ursprünglichen Image-IDs nicht mehr als eigenständige Docker-Images vorhanden; die Dateien im gestoppten Container blieben lesbar. Es wurde kein Container oder Image gelöscht.
- `f19e524288a5` ist ein `PREPARED`-Entwicklungskandidat mit Quell-ID `df80c791c23a`; die übrigen markierten App-Container sind ebenfalls mit `networkis.test=disposable` gekennzeichnet. Ein Testcontainer ist kein produktives Release-Receipt.

## Korrekturen, die vor diesem Auftrag im Produkt fehlten

Die folgenden vorhandenen Korrekturen waren im kanonischen Quellbaum, aber nicht im laufenden Image `4dd05b68dd4e`. Die ersten sieben Bereiche sind auch in mindestens einem markierten App-Container nachweisbar:

| Bereich | Vorhandene Lösung | Bestehender Nachweis |
| --- | --- | --- |
| Assistenten-Fähigkeiten | Stabile Wizard-Fähigkeits-IDs und Ausführungsverträge | `backend/tests/test_assistant_capabilities.py` |
| Kapazitätsvorschlag | Mehrere Netzwerkänderungen im selben Vorschlag gemeinsam speichern | `backend/engineering/agent_tools/proposal_service.py`; vollständiges Release-Gate PASS |
| CAN-FD-Textvorgaben | Nominal- und Datenrate auch bei Zeilenumbruch lesen | `backend/tests/test_wizard_generation.py` |
| Direkte I/O-Signale | Gebundene direkte I/O ohne erfundene Netzwerkroute im Transport-Preflight behandeln, funktionale Simulation weiter getrennt prüfen | `backend/tests/test_simulation_coverage.py`, `backend/tests/test_workflow.py` |
| Modellkonsistenz | Vom Netzwerkeditor erzeugte Kommunikationsfunktion nicht als unerwartete Nutzerfunktion melden | `backend/tests/test_wizard_generation.py` |
| Parameter-Wizard | Ladefehler und nicht auflösbare Branchen-/Technologiezuordnung konkret anzeigen | `frontend/src/components/simulation-wizard.tsx`; Typecheck und vollständiges Release-Gate PASS |
| Projektanlage nach verlorener Antwort | Dieselbe Projekt-ID nach Reload wieder aufnehmen und vor erneutem Anlegen den bestätigten Serverstand prüfen | `frontend/src/lib/project-creation-recovery.test.mjs` |

Der letzte Punkt stammt aus dem aktuellen kanonischen Quellbaum und war in den älteren markierten Test-Images noch nicht vorhanden. Zusätzlich war der vorhandene Test `scripts/tests/test_release_and_deploy.py` im alten Release-Worktree ausgelassen. Beide sind jetzt Teil des neuen Kandidaten.

## Nicht übernommene ältere Varianten

- Die älteren Images enthalten die frühere Wizard-Begrenzung `max-width: 720px`. Im produktiven Image ist die Korrektur `max-width: none` bereits enthalten; die alte CSS-Variante wird nicht übernommen.
- Der ältere Teststand `f19e524288a5` empfiehlt lokale I/O-Busse im Automotive-Katalog. Das widerspricht der Industrie-Neutralität und wird nicht übernommen. Der produktive und kanonische Katalog trennen Industrie und bestätigte Technik.
- Ältere Varianten der ECU-/Aktor-Erkennung, der Chat-Eingabe und der Sequenz-/Trace-Ansichten wurden durch den neueren produktiven und kanonischen Stand ersetzt. Die jüngsten Images zeigen hierzu ältere Dateiversionen, keine im kanonischen Quellbaum fehlende Lösung.
- Neun nur in alten Images vorhandene JSON-Dateien liegen unter `backend/simulator/physic_lib/PhysicalAI/Checks` und `Workflows` und heißen `generated_*`; sie sind erzeugte Prüfartefakte, keine Wizard-Implementierung.
- `backend/engineering/topology_removal.py` und sein Test waren inhaltlich gleich. Im kanonischen Quellbaum standen doppelte CR-Zeilenenden; diese wurden an den Release-Stand angeglichen.

## Zusammenführung und Prüfung

- Die vorhandenen Implementierungen und zugehörigen Tests wurden in den isolierten Release-Worktree übernommen. Die bislang produktiven Wizard-, ECU-, Chat- und Trace-Korrekturen blieben dort erhalten.
- Der gezielte isolierte Backendlauf bestand mit **112 Tests**. Der Frontendtest zur Projektanlage bestand mit **2 Tests**.
- Anschließend wurden die exakten Anwendungs- und Verifikationseingaben von kanonischem Quellbaum und Release-Worktree verglichen: **935 von 935 Source-Manifest-Dateien** mit gleicher Quell-ID `bc7ee79be331e8be3f293a23d03c2115dd4a7692eee29d38bfbb9fd063276e0a`; **239 von 239 Gate-Eingaben** mit gleichem Inhalt. Die Next-Konfiguration wurde an den bereits getesteten Produktstand angeglichen.
- `scripts/deploy-verified-release.py` vergleicht jetzt auch den aktuellen kanonischen Quellstand, die Gate-Eingaben und Git-Revision mit dem PASS-Receipt. Sechs Release-Auswahltests, darunter der neue Negativtest für diese Prüfung, bestanden.
- Das vollständige Gate `02f73c791176` ist **PASS**: 3038 Backend-Tests bestanden, 3 übersprungen; 74 Browserfälle sowie kleine und große HTTP-Abnahme bestanden. Receipt: `F:\CodexOrdner\worktrees\wizard-repair\My_first_Network_Simulator\backend\test-output\release-gates\02f73c791176\receipt.json`.
- Das exakt geprüfte Image `sha256:4e51c4392bb5c761e68c8c2c7ae1314e32cd966858aaaa0fac5b2cf3a9e2af46` wurde aus dem kanonischen Checkout produktiv bereitgestellt. `NetworkIS` meldet `running` und `healthy`; `/api/ready` meldet Datenbank und Speicher als verfügbar; Frontend- und Backend-Build lauten `bc7ee79be331`.
- Eine separate Produktbrowserprüfung für Projekt `20260930050829705-c5f86f1d` ergab 1147 px für das Wizard-Fieldset und jede der vier Formularkarten; `max-width: none`. Die produktive Fähigkeits-API meldet `architecture.create`, `signal.validate`, `trace.analyze` und `finding.review`. I2C, SPI, UART, GPIO, PWM, ADC und DAC sind registriert, stehen aber nicht in den Automotive-Empfehlungen.

Maschinenlesbare Hashinventare und Eingangsvergleiche stehen im Verzeichnis `work/container-audit-20260930/`. Die Quellvergleiche erfassen Anwendungssourcen und Gate-Eingaben, keine Fremdpakete oder Inhalte der Testdatenbank-Volumes.
