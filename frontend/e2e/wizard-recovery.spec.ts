import { test, expect, type Route } from 'playwright/test';
import { randomUUID } from 'node:crypto';

// These tests inject failed transport only. The backend, persisted operations,
// proposal generation and accepted responses are real; no success is mocked.
test('AMEND survives HTTP failure and recovers an accepted response loss @recovery', async ({ page }, testInfo) => {
  const project = 'nis-e2e-recovery-' + randomUUID();
  const runId = randomUUID();
  const prompt = `Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: ${runId}
- Industrie: Automotive
- Netzwerktechnologien: CAN-FD (can_fd)
- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":0,"actuators":0}
- Systemcluster-Graph: [{"cluster_id":"drive","label":"Motor","network_id":"can_fd","network_label":"CAN-FD","bus_name":"Drive","controllers":[{"ecu":"Motorsteuerung","sensors":[],"actuators":[]},{"ecu":"Anzeige","sensors":[],"actuators":[]}]}]
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge Motorsteuerung und Anzeige mit einem Gateway System.`;
  const started = await page.request.post('/api/engineering/agent/chat', {
    headers: { 'X-Project-ID': project }, timeout: 120_000,
    data: { prompt, wizard_command: { action: 'START', run_id: runId, operation_id: randomUUID(),
      target: 'engineering_model', wizard_context: { project_id: project, run_id: runId,
        project_name: 'E2E transport recovery', scope_ids: ['engineering_model'], mode: 'full',
        process_ids: ['defaults', 'review_gate'], task: 'Motorsteuerung und Anzeige an System' } } },
  });
  if (!started.ok()) throw new Error(`HTTP ${started.status()}: ${(await started.text()).slice(0, 4000)}`);
  await page.goto(`/studio/engineering?assistant=project&project=${project}`);
  const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  const operations: string[] = [];
  page.on('request', request => {
    if (!request.url().endsWith('/api/agent/chat') || request.method() !== 'POST') return;
    const command = request.postDataJSON()?.wizard_command;
    if (command?.action === 'AMEND') operations.push(command.operation_id);
  });
  const input = dialog.getByRole('region', { name: 'Engineering-Auftrag ergänzen', exact: true }).getByRole('textbox');
  const submit = dialog.getByRole('button', { name: 'Ergänzung analysieren', exact: true });
  await dialog.getByRole('button', { name: 'Ergänzen', exact: true }).click();
  const addition = 'Beschreibung ergänzen: Der Status der Motorsteuerung dient der Anzeige.';
  await input.fill(addition);
  const outage = async (route: Route) => {
    if (route.request().postDataJSON()?.wizard_command?.action === 'AMEND') {
      await route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"E2E transport outage"}' });
    } else await route.continue();
  };
  await page.route('**/api/agent/chat', outage);
  await submit.click();
  await expect(submit).toBeEnabled();
  await expect(input).toHaveValue(addition);
  expect(operations).toHaveLength(1);
  await page.unroute('**/api/agent/chat', outage);
  await submit.click();
  await expect(input).not.toBeVisible({ timeout: 120_000 });
  expect(operations).toHaveLength(2);
  expect(operations[1]).toBe(operations[0]);

  await dialog.getByRole('button', { name: 'Ergänzen', exact: true }).click();
  await input.fill('Beschreibung ergänzen: Die Anzeige zeigt ausschließlich ausgewählte Funktionsausgänge.');
  const lostResponse = async (route: Route) => {
    if (route.request().postDataJSON()?.wizard_command?.action !== 'AMEND') return route.continue();
    const response = await route.fetch({ timeout: 120_000 });
    if (!response.ok()) throw new Error(`HTTP ${response.status()}: ${(await response.text()).slice(0, 4000)}`);
    // The operation committed, but its response never reaches the UI.
    await route.abort('connectionreset');
  };
  await page.route('**/api/agent/chat', lostResponse);
  await submit.click();
  await expect(input).not.toBeVisible({ timeout: 120_000 });
  await page.unroute('**/api/agent/chat', lostResponse);
  expect(operations).toHaveLength(3);
  expect(operations[2]).not.toBe(operations[1]);
  const saved = await page.request.get('/api/engineering/agent/conversation', { headers: { 'X-Project-ID': project } });
  expect(saved.ok()).toBe(true);
  const history = (await saved.json()).data;
  expect(history.wizard_request.run_id).toBe(runId);
  expect(history.wizard_operations[operations[2]].accepted).toBe(true);

  // A second client commits between the browser's revision read and its write.
  // The resulting real 409 must preserve text, then retry with a NEW operation
  // against the fresh revision, never replay the permanently rejected command.
  await dialog.getByRole('button', { name: 'Ergänzen', exact: true }).click();
  const conflictingText = 'Beschreibung ergänzen: Anzeigezustände sind nachvollziehbar dokumentiert.';
  await input.fill(conflictingText);
  let conflictEvent: string | undefined;
  const competingClient = async (route: Route) => {
    const command = route.request().postDataJSON()?.wizard_command;
    if (command?.action !== 'AMEND') return route.continue();
    const competing = await page.request.post('/api/engineering/agent/chat', {
      headers: { 'X-Project-ID': project }, timeout: 120_000,
      data: { prompt: 'Beschreibung ergänzen: Zweiter Bearbeiter dokumentiert den Statuspfad.',
        wizard_command: { ...command, operation_id: randomUUID() } },
    });
    if (!competing.ok()) throw new Error(`HTTP ${competing.status()}: ${(await competing.text()).slice(0, 4000)}`);
    const stale = await page.request.post('/api/engineering/agent/chat', {
      headers: { 'X-Project-ID': project }, timeout: 120_000,
      data: route.request().postDataJSON(),
    });
    expect(stale.status()).toBe(409);
    await testInfo.attach('backend-revision-conflict', { body: await stale.body(), contentType: 'application/json' });
    // Read the actual SDK response before delivering it to the browser. Chromium
    // may discard its response body during the UI's subsequent navigation.
    // Forward the unchanged server response; no successful write is fabricated.
    const response = await route.fetch({ timeout: 120_000 });
    conflictEvent = await response.text();
    await route.fulfill({ response });
  };
  await page.route('**/api/agent/chat', competingClient);
  // The UI SDK transport wraps backend failures in an HTTP-200 SSE error event.
  await submit.click();
  await expect.poll(() => conflictEvent, { timeout: 120_000 }).toBeDefined();
  expect(conflictEvent).toContain('"type":"error"');
  expect(conflictEvent).toContain('Auftragsrevision');
  await expect(submit).toBeEnabled();
  await expect(input).toHaveValue(conflictingText);
  await page.unroute('**/api/agent/chat', competingClient);
  expect(operations).toHaveLength(4);
  await submit.click();
  await expect(input).not.toBeVisible({ timeout: 120_000 });
  expect(operations).toHaveLength(5);
  expect(operations[4]).not.toBe(operations[3]);
});
