import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';

test('native wizard preserves its complete source while adopting an edited shared draft @project-draft', async ({ page }) => {
  const project = 'nis-e2e-shared-native-' + randomUUID();
  const run = randomUUID();
  const graph = [{ cluster_id: 'drive', label: 'Regelung', network_id: 'can_fd', network_label: 'CAN-FD', bus_name: 'Regelung',
    controllers: [{ ecu: 'Motorsteuerung', sensors: [], actuators: [] }, { ecu: 'Anzeige', sensors: [], actuators: [] }] }];
  const prompt = `Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: ${run}
- Industrie: Automotive
- Netzwerktechnologien: CAN-FD (can_fd)
- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":0,"actuators":0}
- Systemcluster-Graph: ${JSON.stringify(graph)}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge Motorsteuerung und Anzeige mit einem Gateway System.`;
  const started = await page.request.post('/api/engineering/agent/chat', { headers: { 'X-Project-ID': project }, timeout: 120_000,
    data: { prompt, wizard_command: { action: 'START', run_id: run, operation_id: randomUUID(), target: 'engineering_model',
      wizard_context: { project_id: project, run_id: run, project_name: 'Gemeinsamer nativer Auftrag', scope_ids: ['engineering_model'],
        mode: 'full', process_ids: ['defaults', 'review_gate'], task: 'Motorsteuerung und Anzeige an System' } } } });
  expect(started.ok(), await started.text()).toBe(true);
  const initial = await (await page.request.get('/api/engineering/agent/project-draft', { headers: { 'X-Project-ID': project } })).json();
  expect(initial.data.source_format).toBe('WIZARD_V2');
  expect(initial.data.structured_source.prompt).toBe(prompt);
  await page.goto(`/studio/engineering?assistant=project&project=${project}`);
  const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  await dialog.getByRole('button', { name: 'Ergänzen', exact: true }).click();
  await dialog.getByText('Gemeinsamen Projektentwurf bearbeiten', { exact: true }).click();
  const editor = dialog.getByRole('region', { name: 'Gespeicherter Projektentwurf' });
  await expect(editor.getByRole('textbox', { name: 'Projektbeschreibung', exact: true })).toHaveValue(prompt);
  await editor.getByRole('textbox', { name: 'Anforderung ergänzen', exact: true }).fill('Die Modellbeschreibung soll den lokalen Regelungszweck dokumentieren.');
  await editor.getByRole('button', { name: 'Ergänzung speichern', exact: true }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await dialog.getByRole('button', { name: 'Gespeicherten Entwurf im Auftrag übernehmen', exact: true }).click();
  await expect(editor).not.toBeVisible({ timeout: 120_000 });
  const persisted = await (await page.request.get('/api/engineering/workflow', { headers: { 'X-Project-ID': project } })).json();
  const state = persisted.context ?? persisted.data?.context;
  expect(state.agent_wizard_status.run_id).toBe(run);
  expect(state.agent_wizard_status.engineering_draft_ref).toEqual({ draft_id: initial.data.draft_id, revision: 2 });
  expect(state.wizard_request.prompt).toContain(JSON.stringify(graph));
  await page.reload();
  await expect(page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })).toBeVisible();
});

test('conflicting edits retain input and load the current revision without overwriting it @project-draft', async ({ page }) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', { name: 'Nachricht an den Engineering-Assistenten' }).fill('Erstelle ein Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', { name: 'Senden', exact: true }).click();
  const editor = page.getByRole('region', { name: 'Gespeicherter Projektentwurf' });
  await expect(editor).toContainText('Revision 1');
  await editor.getByRole('textbox', { name: 'Name', exact: true }).first().fill('MeineRegelung');
  const session = await (await page.request.get('/api/engineering/agent/review-session')).json();
  const remote = await page.request.post('/api/engineering/agent/project-draft', { headers: {
    'X-Project-ID': project, 'X-Human-Review': 'confirmed', 'X-Review-CSRF': session.csrf_token,
  }, data: { action: 'RESOLVE', operation_id: randomUUID(), revision: 1, industry: 'building_automation' } });
  expect(remote.ok()).toBe(true);
  await editor.getByRole('button', { name: 'Angaben speichern', exact: true }).click();
  await expect(editor.getByRole('region', { name: 'Entwurfskonflikt' })).toContainText('Revision 2');
  await expect(editor.getByRole('textbox', { name: 'Name', exact: true }).first()).toHaveValue('MeineRegelung');
  await editor.getByRole('button', { name: 'Aktuellen Stand laden und Eingabekopie behalten', exact: true }).click();
  await expect(editor.getByRole('textbox', { name: 'Einsatzbereich', exact: true })).toHaveValue('building_automation');
  await expect(editor.getByRole('textbox', { name: 'Name', exact: true }).first()).toHaveValue('RaspberryPi');
  await expect(editor.getByRole('textbox', { name: 'Erhaltene Eingaben vor dem Konflikt', exact: true })).toHaveValue(/MeineRegelung/);
  await editor.getByRole('textbox', { name: 'Name', exact: true }).first().fill('MeineRegelung');
  await editor.getByRole('button', { name: 'Angaben speichern', exact: true }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 3 gespeichert');
});

test('draft recovers a lost save response and survives application restart @project-draft', async ({ page }) => {
  const container = process.env.NIS_E2E_APP_CONTAINER!;
  expect(container).toMatch(/^nis-e2e-app-[a-f0-9]+$/);
  const docker = process.env.NIS_TEST_DOCKER || 'docker';
  expect(execFileSync(docker, ['inspect', container, '--format', '{{index .Config.Labels "networkis.test"}}'], { encoding: 'utf8' }).trim()).toBe('disposable');
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', { name: 'Nachricht an den Engineering-Assistenten' }).fill('Erstelle ein Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', { name: 'Senden', exact: true }).click();
  const editor = page.getByRole('region', { name: 'Gespeicherter Projektentwurf' });
  await expect(editor).toContainText('4 Geräte');
  await editor.getByRole('textbox', { name: 'Anschlusstechnologie', exact: true }).first().fill('ethernet');
  let dropped = false;
  await page.route('**/api/engineering/agent/project-draft', async route => {
    if (route.request().method() !== 'POST' || dropped) return route.continue();
    // Execute the real server write, but lose its transport response.
    const response = await route.fetch();
    expect(response.ok()).toBe(true);
    dropped = true;
    await route.abort('connectionreset');
  });
  await editor.getByRole('button', { name: 'Angaben speichern', exact: true }).click();
  await expect(editor.getByRole('alert')).toBeVisible();
  await expect(editor.getByRole('textbox', { name: 'Anschlusstechnologie', exact: true }).first()).toHaveValue('ethernet');
  const read = async () => (await (await page.request.get('/api/engineering/agent/project-draft', { headers: { 'X-Project-ID': project } })).json()).data;
  const accepted = await read();
  expect(accepted.revision).toBe(2);
  await editor.getByRole('button', { name: 'Angaben speichern', exact: true }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  expect(await read()).toEqual(accepted);
  execFileSync(docker, ['restart', container], { timeout: 60_000 });
  await expect.poll(async () => {
    try { return (await page.request.get('/api/ready', { timeout: 2000 })).ok(); } catch { return false; }
  }, { timeout: 120_000 }).toBe(true);
  await page.reload();
  await expect(editor).toContainText('Revision 2');
  expect(await read()).toEqual(accepted);
});

test('removing a draft device survives save, amendment and reload @project-draft', async ({ page }) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', { name: 'Nachricht an den Engineering-Assistenten' }).fill('Erstelle ein Projekt mit einem Raspberry Pi und drei Temperatursensoren.');
  const send = page.locator('.eng-agent-composer').getByRole('button', { name: 'Senden', exact: true });
  await expect(send).toBeEnabled({ timeout: 120_000 });
  await send.click();
  const editor = page.getByRole('region', { name: 'Gespeicherter Projektentwurf' });
  await expect(editor).toContainText('4 Geräte');
  await editor.getByRole('group', { name: 'Temperatursensor3 · SENSOR', exact: true })
    .getByRole('button', { name: 'Aus Entwurf entfernen', exact: true }).click();
  await editor.getByRole('button', { name: 'Angaben speichern', exact: true }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await editor.getByRole('textbox', { name: 'Anforderung ergänzen', exact: true }).fill('Zusätzlich zwei Drucksensoren.');
  await editor.getByRole('button', { name: 'Ergänzung speichern', exact: true }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 3 gespeichert');
  await page.reload();
  await expect(editor).toContainText('5 Geräte');
  await expect(editor.getByRole('group', { name: 'Temperatursensor3 · SENSOR', exact: true })).toHaveCount(0);
  await expect(editor.getByRole('group', { name: 'Drucksensor2 · SENSOR', exact: true })).toBeVisible();
});

for (const mode of ['chat', 'wizard']) test(`missing controller can be added in ${mode} and the requirement remains editable @project-draft`, async ({ page }) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  const input = page.getByRole('textbox', { name: 'Nachricht an den Engineering-Assistenten' });
  await input.fill('Ein neues Projekt mit drei Sensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', { name: 'Senden', exact: true }).click();
  let editor = page.getByRole('region', { name: 'Gespeicherter Projektentwurf' }).last();
  await expect(editor).toContainText('3 Geräte');
  await editor.getByText('Offene Angaben', { exact: false }).click();
  await expect(editor).toContainText('Controller ergänzen');
  if (mode === 'wizard') {
    await page.getByRole('button', { name: /Im Wizard bearbeiten/ }).click();
    await expect(page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })).toBeVisible();
    editor = page.getByRole('region', { name: 'Gespeicherter Projektentwurf' }).last();
    await expect(page.getByRole('button', { name: 'Auftrag starten', exact: true })).toBeDisabled();
    await editor.getByRole('textbox', { name: 'Anforderung ergänzen', exact: true }).fill('Ergänze einen Raspberry Pi.');
    await editor.getByRole('button', { name: 'Ergänzung speichern', exact: true }).click();
  } else {
    await input.fill('Ergänze einen Raspberry Pi.');
    await page.locator('.eng-agent-composer').getByRole('button', { name: 'Senden', exact: true }).click();
  }
  await expect(editor).toContainText('4 Geräte');
  await page.reload();
  editor = page.getByRole('region', { name: 'Gespeicherter Projektentwurf' }).last();
  await expect(editor).toContainText('Revision 2');
  const owners = editor.getByRole('combobox', { name: 'Verarbeitender Controller', exact: true });
  await expect(owners).toHaveCount(3);
  for (const field of await owners.all()) await field.selectOption({ label: 'RaspberryPi' });
  const tasks = editor.getByRole('textbox', { name: 'Messgröße oder Geräteaufgabe', exact: true });
  await expect(tasks).toHaveCount(4);
  for (let index = 1; index < 4; index++) await tasks.nth(index).fill('Temperatur messen');
  for (const field of await editor.getByRole('textbox', { name: 'Anschlusstechnologie', exact: true }).all()) await field.fill('ethernet');
  await editor.getByRole('combobox', { name: 'Technische Parameter', exact: true }).selectOption('defaults');
  await editor.getByRole('button', { name: 'Angaben speichern', exact: true }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 3 gespeichert');
  const response = await page.request.get('/api/engineering/agent/project-draft', { headers: { 'X-Project-ID': project } });
  const draft = (await response.json()).data;
  expect(draft.devices.map((device: { name: string }) => device.name).sort()).toEqual(['RaspberryPi', 'Sensor1', 'Sensor2', 'Sensor3']);
  expect(draft.issues).toEqual([]);
  expect(draft.original_requirement).toBe('Ein neues Projekt mit drei Sensoren.');
  await expect(page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })).toHaveCount(mode === 'wizard' ? 1 : 0);
});

for (const valveCount of [2, 5]) test(`chat creates and applies the real model with ${valveCount} valves without opening the wizard @project-draft`, async ({ page }) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', { name: 'Nachricht an den Engineering-Assistenten' }).fill(
    `Ich möchte ein kleines Projekt mit einem Raspberry-Pi, drei Temperatursensoren und ${valveCount} Ventilen.`);
  await page.locator('.eng-agent-composer').getByRole('button', { name: 'Senden', exact: true }).click();
  const editor = page.getByRole('region', { name: 'Gespeicherter Projektentwurf' });
  await expect(editor).toContainText(`${4 + valveCount} Geräte`);
  await expect(page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })).toHaveCount(0);
  const technologies = editor.getByRole('textbox', { name: 'Anschlusstechnologie', exact: true });
  const owners = editor.getByRole('combobox', { name: 'Verarbeitender Controller', exact: true });
  const commands = editor.getByRole('combobox', { name: 'Ventilbefehl', exact: true });
  await expect(technologies).toHaveCount(4 + valveCount);
  await expect(owners).toHaveCount(3 + valveCount);
  await expect(commands).toHaveCount(valveCount);
  for (const field of await technologies.all()) await field.fill('ethernet');
  for (const field of await owners.all()) await field.selectOption({ label: 'RaspberryPi' });
  for (const field of await commands.all()) await field.selectOption('OPEN_CLOSE');
  await editor.getByRole('combobox', { name: 'Technische Parameter', exact: true }).selectOption('defaults');
  await editor.getByRole('button', { name: 'Angaben speichern', exact: true }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await page.reload();
  await expect(editor).toContainText('Revision 2');
  await expect(editor.getByLabel('Anschlusstechnologie', { exact: true }).first()).toHaveValue('ethernet');
  await editor.getByRole('button', { name: 'Modellvorschlag erstellen', exact: true }).click();
  await page.getByRole('button', { name: 'Vorschlag freigeben', exact: true }).click();
  await page.getByRole('button', { name: 'Ins Modell übernehmen', exact: true }).click();
  await expect(page.getByText(/Modellobjekte bestätigt/)).toBeVisible();
  await expect(page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })).toHaveCount(0);
  const response = await page.request.get('/api/engineering/hardware-nodes', { headers: { 'X-Project-ID': project } });
  expect(response.ok()).toBe(true);
  const payload = await response.json();
  const nodes = Array.isArray(payload) ? payload : payload.items ?? payload.data ?? [];
  expect(nodes.map((node: { name: string }) => node.name).sort()).toEqual(
    ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3',
      ...Array.from({ length: valveCount }, (_, index) => `Ventilaktor${index + 1}`)].sort());
  const controller = nodes.find((node: { name: string }) => node.name === 'RaspberryPi');
  for (const node of nodes.filter((node: { id: string }) => node.id !== controller.id)) expect(node.identity.system_owner_id).toBe(controller.id);
  await page.reload();
  await expect(page.getByText(/Modellobjekte bestätigt/)).toBeVisible();
});

test('new project is created from the saved draft without moving the original project @project-draft', async ({ page }) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const origin = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', { name: 'Nachricht an den Engineering-Assistenten' }).fill(
    'Ein neues Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', { name: 'Senden', exact: true }).click();
  const editor = page.getByRole('region', { name: 'Gespeicherter Projektentwurf' });
  await expect(editor).toContainText('4 Geräte');
  const before = await page.request.get('/api/engineering/agent/project-draft', { headers: { 'X-Project-ID': origin } });
  const originalDraft = (await before.json()).data;
  await editor.getByText('Als neues Projekt verwenden', { exact: true }).click();
  await editor.getByRole('textbox', { name: 'Neuer Projektname', exact: true }).fill('Temperaturregelung');
  await editor.getByRole('button', { name: 'Neues Projekt anlegen und öffnen', exact: true }).click();
  await expect(page).toHaveURL(/\/studio\/agent\?draft=.+&project=.+/);
  const target = new URL(page.url()).searchParams.get('project')!;
  expect(target.replace('network-project-', '')).not.toBe(compact);
  await expect(editor).toContainText('4 Geräte');
  await page.reload();
  await expect(editor).toContainText('4 Geräte');
  const after = await page.request.get('/api/engineering/agent/project-draft', { headers: { 'X-Project-ID': origin } });
  expect((await after.json()).data).toEqual(originalDraft);
  const targetResponse = await page.request.get('/api/engineering/agent/project-draft', {
    headers: { 'X-Project-ID': target.startsWith('network-project-') ? target : 'network-project-' + target },
  });
  const targetDraft = (await targetResponse.json()).data;
  expect(targetDraft.draft_id).not.toBe(originalDraft.draft_id);
  expect(targetDraft.devices).toEqual(originalDraft.devices);
});

test('the saved inline draft produces and applies a real model proposal @project-draft', async ({ page }) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', { name: 'Nachricht an den Engineering-Assistenten' }).fill(
    'Ein neues Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', { name: 'Senden', exact: true }).click();
  const editor = page.getByRole('region', { name: 'Gespeicherter Projektentwurf' });
  await expect(editor).toContainText('4 Geräte');
  for (const field of await editor.getByRole('textbox', { name: 'Anschlusstechnologie', exact: true }).all()) await field.fill('ethernet');
  for (const field of await editor.getByRole('combobox', { name: 'Verarbeitender Controller', exact: true }).all()) await field.selectOption({ label: 'RaspberryPi' });
  await editor.getByRole('combobox', { name: 'Technische Parameter', exact: true }).selectOption('defaults');
  await editor.getByRole('button', { name: 'Angaben speichern', exact: true }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await expect(editor).toContainText('Revision 2');
  await expect(page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })).toHaveCount(0);
  await editor.getByRole('button', { name: 'Modellvorschlag erstellen', exact: true }).click();
  const proposal = page.getByRole('region', { name: 'Engineering-Vorschlag' });
  await expect(proposal).toContainText('Freigabe offen');
  await proposal.getByRole('button', { name: 'Vorschlag freigeben', exact: true }).click();
  await proposal.getByRole('button', { name: 'Ins Modell übernehmen', exact: true }).click();
  await expect.poll(async () => {
    const response = await page.request.get('/api/engineering/hardware-nodes', { headers: { 'X-Project-ID': project } });
    expect(response.ok()).toBe(true);
    const payload = await response.json();
    const nodes = Array.isArray(payload) ? payload : payload.items ?? payload.data ?? [];
    return nodes.map((node: { name: string }) => node.name).sort();
  }).toEqual(['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3'].sort());
  await page.reload();
  await expect(editor).toContainText('Revision 2');
  await expect(page.getByText(/Modellobjekte bestätigt/)).toBeVisible();
});
