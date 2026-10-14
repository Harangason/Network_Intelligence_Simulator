# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: wizard.spec.ts >> new small wizard traverses all nine stages and survives reload/restart @small
- Location: e2e\wizard.spec.ts:590:1

# Error details

```
Error: locator.click: Error: strict mode violation: getByRole('button', { name: 'Ansicht zurücksetzen', exact: true }) resolved to 2 elements:
    1) <button type="button" class="button secondary">Ansicht zurücksetzen</button> aka locator('form').getByRole('button', { name: 'Ansicht zurücksetzen' })
    2) <button type="button" class="button primary">Ansicht zurücksetzen</button> aka getByRole('alertdialog').getByRole('button', { name: 'Ansicht zurücksetzen' })

Call log:
  - waiting for getByRole('button', { name: 'Ansicht zurücksetzen', exact: true })

```

# Page snapshot

```yaml
- generic [active] [ref=f11e1]:
  - main [ref=f11e2]:
    - generic [ref=f11e3]:
      - link "Communication Simulator Network trace studio" [ref=f11e4] [cursor=pointer]:
        - /url: /?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
        - generic [aria-hidden] [ref=f11e5]: CS
        - generic [ref=f11e6]:
          - strong [ref=f11e7]: Communication Simulator
          - generic [ref=f11e8]: Network trace studio
      - generic [ref=f11e9]:
        - generic [ref=f11e10]:
          - button "Clear" [ref=f11e11] [cursor=pointer]
          - button "Speichern" [ref=f11e12] [cursor=pointer]
          - button "Öffnen" [ref=f11e13] [cursor=pointer]
        - button "Importieren" [ref=f11e14] [cursor=pointer]
        - group "Erscheinungsbild" [ref=f11e15]:
          - button "Hell" [ref=f11e16] [cursor=pointer]
          - button "Dunkel" [pressed] [ref=f11e17] [cursor=pointer]
        - link "Einstellungen" [ref=f11e18] [cursor=pointer]:
          - /url: /studio/settings?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
        - generic "Backend-Build a1aeaee791e6; Frontend und Backend stimmen überein." [ref=f11e19]:
          - text: Python engine
          - generic [ref=f11e21]: · a1aeaee791e6
    - region "Verbindlicher Engineering-Workflow" [ref=f11e22]:
      - generic [ref=f11e23]:
        - generic [ref=f11e24]:
          - generic [ref=f11e25]: Project workflow
          - strong [ref=f11e26]: Define → Route → Connect → Configure → Calculate → Validate → Simulate → Analyze → Assess
        - 'generic "Technische Projekt-ID: nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696" [ref=f11e28]': "Projekt: E2E small"
      - navigation [ref=f11e29]:
        - link "1 Engineering-Modell Vollständig" [ref=f11e30] [cursor=pointer]:
          - /url: /studio/engineering?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
          - generic [ref=f11e31]: "1"
          - generic [ref=f11e32]:
            - strong [ref=f11e33]: Engineering-Modell
            - generic [ref=f11e34]: Vollständig
        - link "2 Routing-Tabelle Freigegeben" [ref=f11e36] [cursor=pointer]:
          - /url: /studio/routing?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
          - generic [ref=f11e37]: "2"
          - generic [ref=f11e38]:
            - strong [ref=f11e39]: Routing-Tabelle
            - generic [ref=f11e40]: Freigegeben
        - link "3 Netzwerk-Editor Vollständig" [ref=f11e42] [cursor=pointer]:
          - /url: /studio?mode=network&project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
          - generic [ref=f11e43]: "3"
          - generic [ref=f11e44]:
            - strong [ref=f11e45]: Netzwerk-Editor
            - generic [ref=f11e46]: Vollständig
        - link "4 Parameter Freigegeben" [ref=f11e48] [cursor=pointer]:
          - /url: /studio?mode=parameters&project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
          - generic [ref=f11e49]: "4"
          - generic [ref=f11e50]:
            - strong [ref=f11e51]: Parameter
            - generic [ref=f11e52]: Freigegeben
        - link "5 Capacity & Timing Vollständig" [ref=f11e54] [cursor=pointer]:
          - /url: /studio/capacity?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
          - generic [ref=f11e55]: "5"
          - generic [ref=f11e56]:
            - strong [ref=f11e57]: Capacity & Timing
            - generic [ref=f11e58]: Vollständig
        - link "6 Validation / Preflight Freigegeben" [ref=f11e60] [cursor=pointer]:
          - /url: /studio/validation?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
          - generic [ref=f11e61]: "6"
          - generic [ref=f11e62]:
            - strong [ref=f11e63]: Validation / Preflight
            - generic [ref=f11e64]: Freigegeben
        - link "7 Simulation Vollständig" [ref=f11e66] [cursor=pointer]:
          - /url: /studio/simulation?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
          - generic [ref=f11e67]: "7"
          - generic [ref=f11e68]:
            - strong [ref=f11e69]: Simulation
            - generic [ref=f11e70]: Vollständig
        - link "8 Results / Analysis Vollständig" [ref=f11e72] [cursor=pointer]:
          - /url: /studio/results?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
          - generic [ref=f11e73]: "8"
          - generic [ref=f11e74]:
            - strong [ref=f11e75]: Results / Analysis
            - generic [ref=f11e76]: Vollständig
        - link "9 Data Science & Intelligence Warnung" [ref=f11e78] [cursor=pointer]:
          - /url: /studio/intelligence?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
          - generic [ref=f11e79]: "9"
          - generic [ref=f11e80]:
            - strong [ref=f11e81]: Data Science & Intelligence
            - generic [ref=f11e82]: Warnung
    - generic [ref=f11e84]:
      - generic [ref=f11e85]:
        - paragraph [ref=f11e86]: Workflow 07
        - heading "Signale und Kommunikation gemeinsam simulieren." [level=1] [ref=f11e87]
      - button "Übersicht aufklappen" [ref=f11e88] [cursor=pointer]:
        - generic [aria-hidden] [ref=f11e90]: ⌄
    - generic [ref=f11e91]:
      - generic [ref=f11e92]:
        - tablist [ref=f11e93]:
          - tab "NETWORK / ECU" [ref=f11e94] [cursor=pointer]
          - tab "SEQUENCE" [ref=f11e95] [cursor=pointer]
          - tab "SIGNALS" [selected] [ref=f11e96] [cursor=pointer]
          - tab "BUS LOAD" [ref=f11e97] [cursor=pointer]
          - tab "EVENTS" [ref=f11e98] [cursor=pointer]
        - button "Steuerung" [ref=f11e99] [cursor=pointer]
      - text: ▸ ▸ ▸ ▸
      - generic [ref=f11e100]:
        - generic [ref=f11e101]:
          - generic [ref=f11e102]:
            - button "Wiedergabe" [ref=f11e103] [cursor=pointer]
            - button "Stopp" [ref=f11e104] [cursor=pointer]
          - generic [ref=f11e105]: PAUSIERT
          - slider "Simulationszeit" [ref=f11e106]: "1"
          - strong [ref=f11e107]: 1.000 / 1.000 s
        - generic [ref=f11e108]:
          - generic [ref=f11e109]:
            - generic [ref=f11e110]:
              - generic [ref=f11e111]:
                - generic [ref=f11e112]: Suche
                - textbox "Signale durchsuchen" [ref=f11e113]:
                  - /placeholder: Signal, Einheit oder Modell suchen …
              - generic [ref=f11e114]:
                - generic [ref=f11e115]: Verlauf
                - combobox "Dynamik filtern" [ref=f11e116]:
                  - option "Alle Verläufe" [selected]
                  - option "Nur dynamisch"
                  - option "Nur statisch"
              - generic [ref=f11e117]:
                - generic [ref=f11e118]: Signaltyp
                - combobox "Signaltyp filtern" [ref=f11e119]:
                  - option "Alle Typen" [selected]
                  - option "Zustände"
                  - option "Physikalisch"
                  - option "Weitere"
              - button "Signale auswählen" [ref=f11e120] [cursor=pointer]
            - generic [ref=f11e121]:
              - generic [ref=f11e122]:
                - button "Treffer wählen" [ref=f11e123] [cursor=pointer]
                - button "Treffer abwählen" [ref=f11e124] [cursor=pointer]
                - button "Detailansicht" [ref=f11e125] [cursor=pointer]
              - status [ref=f11e126]: 3 dargestellt 3 im Filter gewählt 3 gesamt
              - generic [ref=f11e129]:
                - generic [ref=f11e130]:
                  - generic [ref=f11e131]: Zoom 1.0x
                  - slider "Zoom 1.0x" [ref=f11e132]: "1"
                - generic [ref=f11e133]:
                  - generic [ref=f11e134]: Pan
                  - slider "Pan" [disabled] [ref=f11e135]: "0"
          - generic [ref=f11e136]:
            - article [ref=f11e137]:
              - generic [ref=f11e138]:
                - generic [ref=f11e139]:
                  - button "MotorValveSollwert" [ref=f11e140] [cursor=pointer]
                  - generic [ref=f11e141]: STATE_MACHINE · Regelbasiert
                - 'generic "Rohwert: 0" [ref=f11e142]': FALSE (0) code
              - generic [ref=f11e143]:
                - img "MotorValveSollwert Signalverlauf" [ref=f11e144]
                - generic [ref=f11e145]: "1"
                - generic [ref=f11e146]: "0"
            - article [ref=f11e147]:
              - generic [ref=f11e148]:
                - generic [ref=f11e149]:
                  - button "Temperatur_MotorTemperature" [ref=f11e150] [cursor=pointer]
                  - generic [ref=f11e151]: PHYSICS_MODEL · Physikbasiert
                - 'generic "Rohwert: 46.900000000000006" [ref=f11e152]': 46.900000000000006 (46.9) degC
              - generic [ref=f11e153]:
                - img "Temperatur_MotorTemperature Signalverlauf" [ref=f11e154]
                - generic [ref=f11e157]: "215"
                - generic [ref=f11e158]: "-40"
            - article [ref=f11e159]:
              - generic [ref=f11e160]:
                - generic [ref=f11e161]:
                  - button "MotorValveStatus" [ref=f11e162] [cursor=pointer]
                  - generic [ref=f11e163]: STATE_MACHINE · Regelbasiert
                - 'generic "Rohwert: 6" [ref=f11e164]': STANDBY (6)
              - generic [ref=f11e165]:
                - img "MotorValveStatus Signalverlauf" [ref=f11e166]
                - generic [ref=f11e169]: "100"
                - generic [ref=f11e170]: "0"
      - generic [ref=f11e171]:
        - generic [ref=f11e172]:
          - generic [ref=f11e173]:
            - paragraph [ref=f11e174]: Simulation job
            - heading "Simulation abgeschlossen" [level=2] [ref=f11e175]
          - generic [ref=f11e176]:
            - generic [ref=f11e177]: completed
            - link "Trace direkt analysieren" [ref=f11e178] [cursor=pointer]:
              - /url: /trace-analysis?job=b0768d92a94a446db3e948207d880a57&view=signals&project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
        - generic [ref=f11e179]:
          - generic [ref=f11e180]:
            - generic [ref=f11e181]: Trace events
            - strong [ref=f11e182]: "303"
          - generic [ref=f11e183]:
            - generic [ref=f11e184]: Validierung
            - strong [ref=f11e185]: Bestanden
          - generic [ref=f11e186]:
            - generic [ref=f11e187]: Artefakte
            - strong [ref=f11e188]: "6"
        - generic [ref=f11e189]:
          - heading "Erzeugte Artefakte" [level=3] [ref=f11e190]
          - generic [ref=f11e191]:
            - link "↓ universal_trace.jsonl Herunterladen" [ref=f11e192] [cursor=pointer]:
              - /url: /api/simulations/b0768d92a94a446db3e948207d880a57/artifacts/0?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
              - generic [ref=f11e193]: ↓
              - generic [ref=f11e194]:
                - strong [ref=f11e195]: universal_trace.jsonl
                - generic [ref=f11e196]: Herunterladen
            - link "↓ universal_trace.csv Herunterladen" [ref=f11e197] [cursor=pointer]:
              - /url: /api/simulations/b0768d92a94a446db3e948207d880a57/artifacts/1?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
              - generic [ref=f11e198]: ↓
              - generic [ref=f11e199]:
                - strong [ref=f11e200]: universal_trace.csv
                - generic [ref=f11e201]: Herunterladen
            - link "↓ model_trace.json Herunterladen" [ref=f11e202] [cursor=pointer]:
              - /url: /api/simulations/b0768d92a94a446db3e948207d880a57/artifacts/2?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
              - generic [ref=f11e203]: ↓
              - generic [ref=f11e204]:
                - strong [ref=f11e205]: model_trace.json
                - generic [ref=f11e206]: Herunterladen
            - link "↓ golden_trace.jsonl Herunterladen" [ref=f11e207] [cursor=pointer]:
              - /url: /api/simulations/b0768d92a94a446db3e948207d880a57/artifacts/3?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
              - generic [ref=f11e208]: ↓
              - generic [ref=f11e209]:
                - strong [ref=f11e210]: golden_trace.jsonl
                - generic [ref=f11e211]: Herunterladen
            - link "↓ generation_manifest.json Herunterladen" [ref=f11e212] [cursor=pointer]:
              - /url: /api/simulations/b0768d92a94a446db3e948207d880a57/artifacts/4?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
              - generic [ref=f11e213]: ↓
              - generic [ref=f11e214]:
                - strong [ref=f11e215]: generation_manifest.json
                - generic [ref=f11e216]: Herunterladen
            - link "↓ simulation_result.json Herunterladen" [ref=f11e217] [cursor=pointer]:
              - /url: /api/simulations/b0768d92a94a446db3e948207d880a57/artifacts/5?project=nis-e2e-small-ed588ab2-9321-4e73-b4d6-1ff3b350e696
              - generic [ref=f11e218]: ↓
              - generic [ref=f11e219]:
                - strong [ref=f11e220]: simulation_result.json
                - generic [ref=f11e221]: Herunterladen
  - complementary "Engineering-Assistent":
    - button "AI Assistant öffnen" [ref=f11e222] [cursor=pointer]
  - alert [ref=f11e224]
```

# Test source

```ts
  571 | test('wizard refuses an unavailable catalog and recovers using the real registry @catalog-recovery', async ({page}) => {
  572 |   const project = 'nis-e2e-catalog-recovery-' + randomUUID();
  573 |   await page.route('**/api/technologies', route => route.fulfill({status:503,
  574 |     contentType:'application/json',body:JSON.stringify({error:'Der vollständige Technologiekatalog ist derzeit nicht erreichbar.'})}));
  575 |   const dialog = await openWizard(page, project);
  576 |   await expect(dialog.getByRole('alert')).toContainText('Technologiekatalog');
  577 |   await dialog.getByTitle('Projektname', {exact:true}).click();
  578 |   await dialog.locator('#engineering-project-name').fill('Catalog retry');
  579 |   await dialog.getByLabel('Projektbeschreibung', {exact:true}).fill('ein Aktor zum proportional schließen eines Ventil');
  580 |   await expect(dialog.locator('.eng-agent-questionnaire-head').getByRole('button')).toBeDisabled();
  581 |   expect((await readProject(page, project, '/api/simulations')).jobs).toHaveLength(0);
  582 |   await page.unroute('**/api/technologies');
  583 |   await dialog.getByRole('button',{name:'Technologiekatalog erneut laden'}).click();
  584 |   await expect(dialog.getByRole('alert')).toHaveCount(0);
  585 |   await expect(dialog.locator('.eng-agent-questionnaire-head').getByRole('button')).toBeEnabled();
  586 |   const catalog = await (await page.request.get('/api/technologies')).json();
  587 |   expect(catalog.technology_count).toBe(125);
  588 | });
  589 | 
  590 | test('new small wizard traverses all nine stages and survives reload/restart @small', async ({ page, browser }, testInfo) => {
  591 |   const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  592 |   const project = 'nis-e2e-small-' + randomUUID();
  593 |   const dialog = await openWizard(page, project);
  594 |   await dialog.getByTitle('Projektname', { exact: true }).click();
  595 |   await dialog.locator('#engineering-project-name').fill('E2E small');
  596 |   await dialog.getByLabel('Projektbeschreibung', { exact: true }).fill('Erzeuge ein Automotive CAN-FD Netzwerk mit einem Gateway System, den ECUs Motorsteuerung und Anzeige, einem Sensor MotorTemperature und einem Aktor MotorValve. MotorTemperature wird von Motorsteuerung ausgewertet. Motorsteuerung steuert MotorValve. Controllerstatus bleibt bis zur Auswahl konkreter Empfänger und Signale intern. Prüfe und arbeite bis Data Science & Intelligence.\nCAN-FD: 500 kbit/s arbitration, 2 Mbit/s data\nCAN: 500 kbit/s');
  597 |   await dialog.getByLabel('Weitere Hinweise', { exact: true }).fill('- Aktor-Befehle: {"MotorValve":{"length_bits":1,"data_type":"boolean","factor":1,"unit":"code","min_value":0,"max_value":1,"semantic":{"semantic_type":"BOOLEAN"},"data":{"enum_values":{"CLOSE":0,"OPEN":1}}}}');
  598 |   await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  599 |   for (const [label, value] of [['Gateways', '1'], ['Controller', '2'], ['Sensoren', '1'], ['Aktoren', '1']]) await dialog.getByLabel(`${label}: verbindliche Anzahl`, { exact: true }).fill(value);
  600 |   const startRequest = page.waitForRequest(request => request.url().endsWith('/api/agent/chat')
  601 |     && request.method() === 'POST' && request.postDataJSON()?.wizard_command?.action === 'START');
  602 |   // Use the same visible questionnaire navigation a user uses; never inject generated model rows.
  603 |   for (let step = 0; step < 10; step++) {
  604 |     const submit = dialog.locator('.eng-agent-questionnaire-head').getByRole('button');
  605 |     await expect(submit).toBeEnabled();
  606 |     const name = await submit.innerText();
  607 |     await submit.click();
  608 |     if (name === 'Übernehmen') break;
  609 |     if (step === 9) throw new Error('Questionnaire did not offer submit.');
  610 |   }
  611 |   const requested = (await startRequest).postDataJSON().wizard_command.wizard_context;
  612 |   expect(requested.technologies, 'An explicit CAN-FD task must not silently request LIN and SOME/IP.').toEqual(['CAN-FD (can_fd)']);
  613 |   // Preserve a real pending model through parameter save and renewed review.
  614 |   await expect.poll(async () => (await readProject(page,project,'/api/engineering/workflow?view=summary')).context.agent_execution?.state,
  615 |     {timeout:180000}).toBe('REVIEW_REQUIRED');
  616 |   const pending = (await readProject(page,project,'/api/engineering/agent/conversation')).data.active_proposal;
  617 |   await page.goto(`/studio?mode=parameters&project=${project}&technology=can_fd&proposal=${pending}#parameter-findings`);
  618 |   await expect(page.getByRole('region',{name:'Aktuelle Parameterbefunde'})).toContainText('noch nicht übernommenen Vorschlags');
  619 |   const common = page.locator('.parameter-group-common');
  620 |   await expect(common.locator('#arbitration_bitrate')).toHaveValue('500 kbit/s');
  621 |   await expect(common.locator('#data_bitrate')).toHaveValue('2 Mbit/s');
  622 |   await expect(page.locator('.parameter-details[open]')).toHaveCount(0);
  623 |   await repeatParameterReturn(page, project, pending, [{technology: 'can_fd',
  624 |     fields: {arbitration_bitrate: '500 kbit/s', data_bitrate: '1 Mbit/s', can_fd_data_prescaler: '2'},
  625 |     native: {arbitration_bitrate: 500_000, data_bitrate: 1_000_000, can_fd_data_prescaler: 2},
  626 |     editFields: ['data_bitrate', 'can_fd_data_prescaler']}]);
  627 |   expect((await readProject(page,project,`/api/engineering/agent/proposals/${pending}?view=status`)).data.canonical_ids).toEqual([]);
  628 |   expect((await allObjects(page,project,'hardware-nodes'))).toHaveLength(0);
  629 |   const continuity = await completeThroughWizard(page, project, true,
  630 |     ['System', 'Motorsteuerung', 'Anzeige', 'MotorTemperature', 'MotorValve']);
  631 |   const artifacts = await verifyArtifacts(page, project, 5, undefined, {
  632 |     seed: 42, data_bitrate: 1_000_000, can_fd_data_prescaler: 2,
  633 |   });
  634 |   expect(artifacts.assessment.observed_signal_count).toBeGreaterThanOrEqual(3);
  635 |   expect(artifacts.assessment.scope_coverage.transport_exclusions).toHaveLength(3);
  636 |   const finished = page.waitForResponse(response => response.url().includes(`/runs/${continuity.runId}/finish`)
  637 |     && response.request().method() === 'POST');
  638 |   await dialog.getByRole('button', { name: 'Fertig stellen', exact: true }).click();
  639 |   expect((await finished).ok()).toBe(true);
  640 |   await expect(dialog).not.toBeVisible();
  641 |   await expect(page).toHaveURL(new RegExp(`/studio/results\\?snapshot=${artifacts.snapshot}&project=${project}$`));
  642 |   const selectedRun = page.locator(`.result-run-list button[data-snapshot-id="${artifacts.snapshot}"]`);
  643 |   await expect(selectedRun).toHaveClass('active');
  644 |   await expect(page.getByText('Anforderungserfüllung: Bestanden', { exact: true })).toBeVisible();
  645 |   await expect(page.locator('.metric').filter({ has: page.getByText('Trace Events', { exact: true }) }))
  646 |     .toContainText(artifacts.trace_events.toLocaleString('de-DE'));
  647 |   await page.reload();
  648 |   await expect(selectedRun).toHaveClass('active');
  649 |   await expect(page.getByText('Anforderungserfüllung: Bestanden', { exact: true })).toBeVisible();
  650 |   await page.getByRole('link', { name: 'Simulation öffnen', exact: true }).click();
  651 |   const runner = page.locator('.model-simulation-runner');
  652 |   await expect(runner).toHaveAttribute('data-job-id', artifacts.job);
  653 |   await expect(runner).toHaveAttribute('data-snapshot-id', artifacts.snapshot);
  654 |   await expect(page.getByRole('heading', { name: 'Simulation abgeschlossen', exact: true })).toBeVisible();
  655 |   await page.reload();
  656 |   await expect(runner).toHaveAttribute('data-job-id', artifacts.job);
  657 |   // A new browser context has no session key from either wizard or simulation UI.
  658 |   const freshContext = await browser.newContext({ baseURL: new URL(page.url()).origin });
  659 |   let restartedJob: string | null = null;
  660 |   try {
  661 |     const fresh = await freshContext.newPage();
  662 |     await fresh.goto(`/studio/simulation?project=${project}`);
  663 |     const freshRunner = fresh.locator('.model-simulation-runner');
  664 |     await expect(freshRunner).toHaveAttribute('data-job-id', artifacts.job);
  665 |     await expect(freshRunner).toHaveAttribute('data-snapshot-id', artifacts.snapshot);
  666 |     await expect(fresh.getByRole('heading', { name: 'Simulation abgeschlossen', exact: true })).toBeVisible();
  667 |     // A completed historical run must not block the current approved preflight.
  668 |     await openSimulationRun(fresh);
  669 |     await expect(fresh.getByRole('button', { name: 'Lauf starten', exact: true })).toBeEnabled();
  670 |     await fresh.getByRole('button', { name: 'Ansicht zurücksetzen', exact: true }).click();
> 671 |     await fresh.getByRole('button', { name: 'Ansicht zurücksetzen', exact: true }).click();
      |                                                                                    ^ Error: locator.click: Error: strict mode violation: getByRole('button', { name: 'Ansicht zurücksetzen', exact: true }) resolved to 2 elements:
  672 |     await expect(freshRunner).not.toHaveAttribute('data-job-id');
  673 |     await fresh.reload();
  674 |     await openSimulationRun(fresh);
  675 |     await expect(fresh.getByRole('button', { name: 'Lauf starten', exact: true })).toBeEnabled();
  676 |     await expect(freshRunner).not.toHaveAttribute('data-job-id');
  677 |     await fresh.goto(`/studio/results?project=${project}&snapshot=${artifacts.snapshot}`);
  678 |     await expect(fresh.locator('.result-run-list button.active')).toHaveAttribute('data-snapshot-id', artifacts.snapshot);
  679 |     await expect(fresh.getByText('Anforderungserfüllung: Bestanden', { exact: true })).toBeVisible();
  680 |     await testInfo.attach('wizard-result-restoration', { body: await fresh.screenshot(), contentType: 'image/png' });
  681 |     // Actual normal START, without resetting/deleting the restored completed run.
  682 |     await fresh.goto(`/studio/simulation?project=${project}&snapshot=${artifacts.snapshot}`);
  683 |     await expect(freshRunner).toHaveAttribute('data-job-id', artifacts.job);
  684 |     await openSimulationRun(fresh);
  685 |     await fresh.getByRole('button', { name: 'Lauf starten', exact: true }).click();
  686 |     await expect.poll(async () => {
  687 |       restartedJob = await freshRunner.getAttribute('data-job-id');
  688 |       return Boolean(restartedJob && restartedJob !== artifacts.job);
  689 |     }).toBe(true);
  690 |     await expect.poll(async () => (await readProject(fresh, project, `/api/simulations/${restartedJob}`)).status,
  691 |       { timeout: 180_000 }).toBe('completed');
  692 |     const preserved = await readProject(fresh, project, `/api/engineering/workflow/simulation-snapshots/${artifacts.snapshot}`);
  693 |     expect(preserved.job_id).toBe(artifacts.job);
  694 |     expect(preserved.result.trace.events).toBe(artifacts.trace_events);
  695 |     await fresh.reload();
  696 |     await expect(freshRunner).toHaveAttribute('data-job-id', restartedJob!);
  697 |     await fresh.goto(`/studio/results?project=${project}-other&snapshot=${artifacts.snapshot}`);
  698 |     await expect(fresh.getByText('Dieser Simulationslauf ist in diesem Projekt nicht verfügbar.', { exact: true })).toBeVisible();
  699 |     await expect(fresh.locator('.result-run-list button.active')).toHaveCount(0);
  700 |   } finally {
  701 |     await freshContext.close();
  702 |   }
  703 |   await openWizard(page, project);
  704 |   expect((await readProject(page, project, '/api/simulations')).jobs.map((job: { id: string }) => job.id).sort())
  705 |     .toEqual([artifacts.job, restartedJob].sort());
  706 |   expect(errors).toEqual([]);
  707 |   await testInfo.attach('evidence', { body: JSON.stringify({ project, ...continuity, ...artifacts }), contentType: 'application/json' });
  708 | });
  709 | 
  710 | for (const technology of ['I2C', 'Modbus RTU']) {
  711 |   test(`Raspberry Pi ${technology} project retains model and blocks inconsistent native parameters @nonautomotive`, async ({ page }, testInfo) => {
  712 |     const project = 'nis-e2e-embedded-' + randomUUID();
  713 |     const dialog = await openWizard(page, project);
  714 |     await dialog.getByTitle('Projektname', { exact: true }).click();
  715 |     await dialog.locator('#engineering-project-name').fill('Temperaturregelung');
  716 |     await dialog.getByLabel('Projektbeschreibung', { exact: true }).fill(technology === 'I2C'
  717 |       ? '2 Aktoren für Ventile, 4 Sensoren für Temperaturen, und ein RaspberryPi'
  718 |       : `2 Aktoren für Ventile, 4 Sensoren für Temperaturen, und ein RaspberryPi. Embedded Systems. Alle Geräte kommunizieren über ${technology}. Prüfe und arbeite bis Data Science & Intelligence.`);
  719 |     await dialog.getByTitle('Netzarchitektur', { exact: true }).click();
  720 |     await dialog.getByRole('radio', { name: /Variante 0/ }).check();
  721 |     await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  722 |     if (technology === 'I2C') {
  723 |       await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  724 |       await dialog.getByLabel('RaspberryPi: Anschluss', { exact: true }).selectOption('I2C');
  725 |       await expect(dialog.getByLabel('Temperatursensor1: Anschluss', { exact: true })).toHaveValue('');
  726 |       await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  727 |       for (const name of ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4', 'Ventilaktor1', 'Ventilaktor2']) {
  728 |         await dialog.getByLabel(`${name}: Anschluss`, { exact: true }).selectOption('I2C');
  729 |       }
  730 |       await dialog.getByLabel('Sensor 1: Messgröße', { exact: true }).selectOption('speed');
  731 |       await expect(dialog.getByLabel('Temperatursensor1: Anschluss', { exact: true })).toHaveValue('I2C');
  732 |       await dialog.getByLabel('Sensor 1: Messgröße', { exact: true }).selectOption('temperature');
  733 |     }
  734 |     await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  735 |     await dialog.getByLabel('Ventilaktor1: Stellbefehl', { exact: true }).selectOption('OPEN_CLOSE');
  736 |     await expect(dialog.getByLabel('Ventilaktor2: Stellbefehl', { exact: true })).toHaveValue('');
  737 |     await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
  738 |     await dialog.getByLabel('Ventilaktor2: Stellbefehl', { exact: true }).selectOption('OPEN_CLOSE');
  739 |     await dialog.getByRole('button', { name: 'Übernehmen', exact: true }).click();
  740 |     await expect(completeThroughWizard(page, project, true, ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4', 'Ventilaktor1', 'Ventilaktor2'], false, undefined, undefined, true))
  741 |       .rejects.toThrow(/Wizard BLOCKED at parameters:.*bestätigte Angaben/);
  742 |     const workflow = await readProject(page, project, '/api/engineering/workflow');
  743 |     const findings = workflow.context.agent_execution.blocking_findings as { code: string }[];
  744 |     expect(findings.map(item => item.code)).toContain('TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH');
  745 |     expect(workflow.statuses.parameters).toBe('IN_PROGRESS');
  746 |     expect(workflow.artifact_checks.parameters.complete).toBe(false);
  747 |     const required = workflow.artifact_checks.parameters.required;
  748 |     expect(required.profile_values).toBe(false);
  749 |     const deviceSource = technology === 'I2C' ? 'i2c_device_source' : 'mr_device_source';
  750 |     // These scenarios remain blocked by real native dependencies, not by the
  751 |     // absence of a real device qualification or fabricated source identifier.
  752 |     expect(required).not.toHaveProperty(deviceSource, false);
  753 |     const nativeTechnology = technology === 'I2C' ? 'i2c' : 'modbus_rtu';
  754 |     expect(workflow.parameters.simulation_parameter_assumptions[nativeTechnology].values)
  755 |       .not.toHaveProperty(deviceSource);
  756 |     expect(workflow.artifact_checks.parameters.profile_findings.some((finding: {code: string}) =>
  757 |       finding.code === 'TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH')).toBe(true);
  758 |     const evidenceReview = dialog.getByRole('region', {name: 'Blockierende Preflight-Befunde'});
  759 |     await expect(evidenceReview).toContainText(technology === 'I2C' ? 'i2c_pullup_ohms' : 'mr_pdu_bytes');
  760 |     await expect(evidenceReview.getByRole('link', {name: 'Betroffene Angaben bearbeiten'}).first())
  761 |       .toHaveAttribute('href', new RegExp(`mode=parameters.*project=${project}`));
  762 |     // Rechecking persisted findings must use the existing request, and must
  763 |     // never release unchanged invalid native values or invent device evidence.
  764 |     const continued = page.waitForRequest(request => new URL(request.url()).pathname === '/api/agent/chat'
  765 |       && request.method() === 'POST' && request.postDataJSON()?.wizard_command?.action === 'CONTINUE');
  766 |     await evidenceReview.getByRole('button', {name: 'Gespeicherte Angaben erneut prüfen & fortsetzen', exact: true}).click();
  767 |     const command = (await continued).postDataJSON().wizard_command;
  768 |     expect(command.run_id).toBe(workflow.context.agent_execution.run_id);
  769 |     expect(command.request_revision).toBe(workflow.context.agent_execution.request_revision);
  770 |     await expect.poll(async () => {
  771 |       const next = await readProject(page, project, '/api/engineering/workflow?view=summary');
```