import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';
import { buildSequenceDiagram } from '../src/features/simulation/lib/e2e-sequence';

test('network tools remain grouped and usable at narrow and desktop widths @studio-controls', async ({ page }) => {
  const project = 'nis-e2e-toolbar-' + randomUUID();
  const headers = { 'X-Project-ID': project };
  const created = await page.request.post('/api/engineering/hardware-nodes', {
    headers, data: { name: 'Toolbar Controller', device_type: 'EmbeddedController' },
  });
  expect(created.ok(), await created.text()).toBe(true);
  const controller = await created.json();
  const view = await (await page.request.get('/api/engineering/workflow/topology', { headers })).json();
  const saved = await page.request.put('/api/engineering/workflow/topology', {
    headers, data: { expected_token: view.edit_token, topology: {
      nodes: [{ id: controller.id, engineeringId: controller.id, name: controller.name,
        kind: 'ecu', x: 100, y: 100, width: 210, height: 150, ports: [] }], edges: [],
    } },
  });
  expect(saved.ok(), await saved.text()).toBe(true);
  await page.goto(`/studio?mode=network&project=${project}`);
  await expect(page.getByRole('heading', { name: 'ECU-Netzwerk', exact: true })).toBeVisible();
  for (const width of [954, 390, 1417]) {
    await page.setViewportSize({ width, height: 1244 });
    const toolbar = page.locator('.net-toolbar');
    for (const name of ['Geräte hinzufügen', 'Netzwerkansicht', 'Auswahl bearbeiten']) {
      await expect(toolbar.getByRole('group', { name, exact: true })).toBeVisible();
    }
    expect(await toolbar.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
    const overflow = await toolbar.evaluate(element => {
      const bounds = element.getBoundingClientRect();
      return [...element.querySelectorAll('button, input')].filter(control => {
        const rect = control.getBoundingClientRect();
        return rect.width > 0 && (rect.left < bounds.left - 1 || rect.right > bounds.right + 1);
      }).map(control => control.textContent);
    });
    expect(overflow).toEqual([]);
    await toolbar.getByRole('button', { name: 'Vergrößern', exact: true }).click();
    await expect(toolbar.getByRole('button', { name: 'Zoom auf 100 Prozent zurücksetzen' })).not.toHaveText('100 %');
    await toolbar.getByRole('button', { name: 'Zoom auf 100 Prozent zurücksetzen' }).click();
    await expect(toolbar.getByRole('button', { name: 'Zoom auf 100 Prozent zurücksetzen' })).toHaveText('100 %');
    await toolbar.getByRole('button', { name: '+ ECU', exact: true }).click();
    await expect(page.getByRole('menu', { name: 'ECU auswählen' })).toBeVisible();
    await toolbar.getByRole('button', { name: '+ ECU', exact: true }).click();
  }
});

test('simulation trace controls expose every signal and event without opaque row overlays @studio-controls @simulation-display', async ({ page }, testInfo) => {
  // UI contract fixture only. Canonical generation/apply/persist is covered by wizard.spec.ts.
  const project = 'nis-e2e-display-' + randomUUID();
  const jobId = 'display-job';
  const versions = { engineering_model: 0, routing: 0, network_editor: 0, parameters: 0 };
  const workflow = { project_id: project, versions, edit_tokens: { parameters: 'p', topology: 't' },
    statuses: { validation: 'APPROVED' }, parameters: {}, topology: { nodes: [], edges: [] } };
  const signals = Array.from({ length: 125 }, (_, index) => ({
    signal_id: `signal-${index}`, signal: `Signal ${String(index).padStart(3, '0')}`, unit: '%',
    minimum: 0, maximum: 100, resolution: .1, behavior_type: 'PHYSICS_MODEL', model_label: 'PHYSICS_BASED',
    points: [{ time_s: 0, value: 10, golden_value: 10, faults: [] },
      { time_s: 1, value: index % 2 ? 20 : 10, golden_value: index % 2 ? 20 : 10, faults: [] }],
  }));
  const records = Array.from({ length: 405 }, (_, index) => ({ event_id: `event-${index}`, transaction_id: 'transaction',
    time_s: index / 1000, source: 'Source', destination: 'Target', route_name: `Route ${index}`, technology: 'ETHERNET', status: 'transmitted' }));
  const model = buildSequenceDiagram(records, 'SIMULATED');
  const trace = { scenario: { duration_s: 1 }, signals, frames: records, events: [], bus_load: [], comparison: { available: false } };
  const blockedRequests: string[] = [];
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let response: unknown;
    if (path === `/api/simulations/${jobId}`) response = { id: jobId, status: 'completed',
      result: { model_simulation: trace, runtime_metrics: { sequence_model: model } } };
    else if (path === '/api/technologies') response = { domains: [], formats: [] };
    else if (path.endsWith('/workflow/parameters')) response = { ...workflow, edit_token: 'p' };
    else if (path.endsWith('/workflow/topology')) response = { ...workflow, edit_token: 't' };
    else if (path.endsWith('/workflow/snapshots')) response = { simulations: [] };
    else if (path.endsWith('/workflow') || path.endsWith('/workflow/context')) response = workflow;
    else if (path.endsWith('/fault-proposals')) response = { items: [] };
    else { blockedRequests.push(path); response = {}; }
    await route.fulfill({ json: response });
  });
  await page.addInitScript(({ project, jobId }) => sessionStorage.setItem(`nis.active-simulation.${project}`, jobId), { project, jobId });
  await page.goto(`/studio/simulation?project=${project}`);
  await expect(page.getByLabel('Dynamik filtern')).toHaveValue('ALL');
  await expect(page.locator('.signal-filter-summary')).toContainText('125 im Filter gewählt');
  await expect(page.locator('.signal-lane')).toHaveCount(60);
  const signalPages = page.getByRole('navigation', { name: 'Signale durchblättern' });
  await signalPages.getByRole('button', { name: 'Weiter', exact: true }).click();
  await expect(page.locator('.signal-lane').first()).toContainText('Signal 060');
  await signalPages.getByLabel('Signale: Seite auswählen').selectOption('2');
  await expect(page.locator('.signal-lane')).toHaveCount(5);
  await expect(page.locator('.signal-lane').last()).toContainText('Signal 124');
  await page.getByLabel('Dynamik filtern').selectOption('STATIC');
  await expect(page.locator('.signal-lane').first()).toContainText('Signal 000');
  await expect(page.locator('.signal-filter-summary')).toContainText('63 im Filter gewählt');
  await page.getByLabel('Signale durchsuchen').fill('Signal 124');
  await expect(page.locator('.signal-lane')).toHaveCount(1);
  await page.getByRole('tab', { name: 'SEQUENCE', exact: true }).click();
  const sequence = page.getByLabel('E2E-Sequenzdiagramm', { exact: true });
  await expect(sequence.locator('.e2e-sequence-event')).toHaveCount(200);
  const first = sequence.locator('.e2e-sequence-event').first();
  await first.hover();
  const fillAlpha = await first.locator('.e2e-sequence-row-background').evaluate(element => {
    const fill = getComputedStyle(element).fill;
    return Number(fill.match(/\/\s*([.\d]+)\s*\)/)?.[1] ?? '1');
  });
  expect(fillAlpha).toBeGreaterThan(0);
  expect(fillAlpha).toBeLessThan(.15);
  await expect(sequence.locator('.e2e-sequence-message-label-bg')).toHaveCount(0);
  await expect(sequence.locator('.e2e-sequence-activation-svg')).toHaveCount(2);
  await sequence.locator('.e2e-sequence-scroll').screenshot({ path: testInfo.outputPath('sequence-highlight.png') });
  await first.focus();
  await first.press('Enter');
  await expect(sequence.getByLabel('Ausgewähltes Ereignis')).toContainText('Route 0');
  const pages = sequence.getByRole('navigation', { name: 'Ereignisse durchblättern' });
  await pages.getByRole('button', { name: 'Weiter', exact: true }).click();
  await expect(sequence.locator('.e2e-sequence-event').first()).toContainText('Route 200');
  await expect(sequence.locator('.e2e-sequence-event').first().locator('.e2e-sequence-delta-label')).toHaveText('Δ 1.00 ms');
  await pages.getByLabel('Ereignisse: Seite auswählen').selectOption('2');
  await expect(sequence.locator('.e2e-sequence-event')).toHaveCount(5);
  await expect(sequence.locator('.e2e-sequence-event').last()).toContainText('Route 404');
  await expect(pages.getByRole('button', { name: 'Weiter', exact: true })).toBeDisabled();
  await page.getByLabel('Sequenzereignisse suchen').fill('Route 404');
  await expect(sequence.locator('.e2e-sequence-event')).toHaveCount(1);
  await expect(sequence.locator('.e2e-sequence-event')).toContainText('Route 404');
  for (const width of [954, 390]) {
    await page.setViewportSize({ width, height: 1244 });
    await page.getByLabel('Sequenzereignisse suchen').fill('');
    const overflow = await pages.evaluate(element => {
      const bounds = element.getBoundingClientRect();
      return [...element.querySelectorAll('button, select, output')].some(control => {
        const rect = control.getBoundingClientRect();
        return rect.left < bounds.left - 1 || rect.right > bounds.right + 1;
      });
    });
    expect(overflow).toBe(false);
  }
  expect(blockedRequests.filter(path => /simulations\//.test(path))).toEqual([]);
});

for (const scenario of [
  { name: 'CAN', technologies: ['CAN_FD'], expected: ['BLF', 'DBC'] },
  { name: 'Ethernet', technologies: ['ETHERNET'], expected: ['PCAP'] },
  { name: 'mixed', technologies: ['CAN_FD', 'ETHERNET', 'LIN'], expected: ['BLF', 'DBC', 'PCAP'] },
]) test(`simulation selects real native defaults for ${scenario.name} and preserves manual choice @studio-controls`, async ({ page }) => {
  const project = 'nis-e2e-formats-' + randomUUID();
  const headers = { 'X-Project-ID': project };
  const initial = await (await page.request.get('/api/engineering/workflow/parameters', { headers })).json();
  const parameters = { industry: 'custom', technology: scenario.technologies[0].toLowerCase(),
    networks: scenario.technologies.map((technology, index) => ({ id: `bus-${index}`, name: `Bus ${index}`, technology })) };
  const saved = await page.request.patch('/api/engineering/workflow/parameters', {
    headers, data: { expected_token: initial.edit_token, parameters },
  });
  expect(saved.ok(), await saved.text()).toBe(true);
  await page.goto(`/studio/simulation?project=${project}`);
  const trigger = page.locator('.trace-format-trigger');
  await expect(trigger).toContainText(scenario.expected.join(', '));
  await expect(trigger.locator('strong')).toHaveText(String(scenario.expected.length));
  await trigger.click();
  const picker = page.getByRole('dialog', { name: 'Trace-Formate auswählen' });
  await expect(picker).toBeVisible();
  await expect(picker.getByRole('checkbox', { name: 'Universelle Tabellenablage', exact: false })).not.toBeChecked();
  const csv = picker.getByRole('checkbox', { name: 'Universelle Tabellenablage', exact: false });
  await csv.check();
  await page.evaluate(() => window.dispatchEvent(new Event('workflow:changed')));
  await expect(csv).toBeChecked();
  await expect(trigger.locator('strong')).toHaveText(String(scenario.expected.length + 1));
});
