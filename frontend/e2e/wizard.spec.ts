import { test, expect, type Page } from 'playwright/test';
import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { WizardProgressWatchdog, WIZARD_STEPS, WIZARD_DONE } from './support/wizard-progress-watchdog';

const steps = WIZARD_STEPS;
const done = WIZARD_DONE;
type WriteTiming = { url: string; started: number; duration_ms?: number; status?: number; failure?: string };
const writeTimings = new Map<string, WriteTiming[]>();
const workflowPageFailures = new WeakMap<Page, string[]>();
const progressMilestones = new Map<string, unknown[]>();

test.beforeEach(async ({ page }, info) => {
  const rows: WriteTiming[] = [];
  writeTimings.set(info.testId, rows);
  workflowPageFailures.set(page, []);
  progressMilestones.set(info.testId, []);
  const requests = new Map<object, WriteTiming>();
  page.on('request', request => {
    if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) return;
    const row = { url: request.url(), started: Date.now() };
    rows.push(row); requests.set(request, row);
  });
  page.on('response', response => {
    const row = requests.get(response.request());
    if (row) row.status = response.status();
    if (response.status() === 413 && /^\/api\/engineering\/workflow(?:\/|$)/.test(new URL(response.url()).pathname)) {
      workflowPageFailures.get(page)!.push(`HTTP 413: ${response.url()}`);
    }
  });
  page.on('requestfinished', request => {
    const row = requests.get(request);
    if (row) row.duration_ms = Date.now() - row.started;
  });
  page.on('requestfailed', request => {
    const row = requests.get(request);
    if (row) { row.duration_ms = Date.now() - row.started; row.failure = request.failure()?.errorText; }
  });
});

test.afterEach(async ({ page }, info) => {
  await info.attach('write-request-timings', { body: JSON.stringify(writeTimings.get(info.testId) || []), contentType: 'application/json' });
  await info.attach('workflow-progress-boundaries', { body: JSON.stringify(progressMilestones.get(info.testId) || []), contentType: 'application/json' });
  await info.attach('workflow-page-failures', { body: JSON.stringify(workflowPageFailures.get(page) || []), contentType: 'application/json' });
  writeTimings.delete(info.testId);
  progressMilestones.delete(info.testId);
  expect(workflowPageFailures.get(page), 'The underlying engineering page must remain readable throughout reload and recovery.').toEqual([]);
});

async function assertEngineeringPageHealthy(page: Page) {
  expect(workflowPageFailures.get(page), 'A working wizard overlay must not conceal a workflow HTTP 413.').toEqual([]);
  expect(await page.getByText('Engineering-API nicht erreichbar', { exact: true }).isVisible(),
    'The underlying engineering page must not show its API error view.').toBe(false);
}

async function readProject(page: Page, project: string, path: string) {
  const result = await page.request.get(path, { headers: { 'X-Project-ID': project }, timeout: 60_000 });
  if (!result.ok()) throw new Error(`${path}: HTTP ${result.status()} ${(await result.text()).slice(0, 4000)}`);
  return result.json();
}

async function openWizard(page: Page, project: string) {
  await page.goto(`/studio/engineering?assistant=project&project=${project}`, { waitUntil: 'load' });
  const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  await expect(dialog).toBeVisible();
  await assertEngineeringPageHealthy(page);
  return dialog;
}

async function allObjects(page: Page, project: string, resource: string) {
  const items: any[] = [];
  for (let offset = 0; ; offset += 500) {
    const response = await readProject(page, project, `/api/engineering/${resource}?limit=500&offset=${offset}`);
    items.push(...response.items);
    if (response.items.length < 500) return items;
  }
}

async function restartApplication(page: Page, crash = false) {
  const container = process.env.NIS_E2E_APP_CONTAINER!;
  expect(container).toMatch(/^nis-e2e-app-[a-f0-9]+$/);
  const docker = process.env.NIS_TEST_DOCKER || 'docker';
  const label = execFileSync(docker, ['inspect', container, '--format', '{{index .Config.Labels "networkis.test"}}'], { encoding: 'utf8' }).trim();
  expect(label).toBe('disposable');
  execFileSync(docker, ['restart', ...(crash ? ['-t', '0'] : []), container], { timeout: 60_000 });
  await expect.poll(async () => {
    try { return (await page.request.get('/api/ready', { timeout: 2000 })).ok(); } catch { return false; }
  }, { timeout: 120_000 }).toBe(true);
}

async function verifySignalContracts(page: Page, project: string, expected: Record<string, unknown>) {
  const [hardware, functions, messages, signals] = await Promise.all(
    ['hardware-nodes', 'functions', 'messages', 'signals'].map(resource => allObjects(page, project, resource)));
  const nodes = new Map(hardware.map(item => [item.id, item]));
  const functionsById = new Map(functions.map(item => [item.id, item]));
  const messagesById = new Map(messages.map(item => [item.id, item]));
  const contracts: Record<string, unknown> = {};
  for (const signal of signals) {
    const message = messagesById.get(signal.message_id);
    expect(message).toBeTruthy();
    const reference = message.configuration.communication_contract.producer_ref;
    const fn = functionsById.get(reference);
    const owner = nodes.get(reference) || (fn && nodes.get(fn.hardware_node_id));
    const producer = owner?.device_type === 'Gateway' ? '$gateway' : (nodes.get(reference) || fn)?.name;
    expect(producer).toBeTruthy();
    const key = [producer, message.name, signal.name].join(' :: ');
    expect(contracts[key], 'Semantic signal identity must be unique: ' + key).toBeUndefined();
    contracts[key] = {
      ...Object.fromEntries(['start_bit', 'length_bits', 'data_type', 'factor', 'offset_value',
        'unit', 'min_value', 'max_value', 'byte_order'].map(field => [field, signal[field] ?? null])),
      enum_values: signal.data?.enum_values ?? null,
      semantic_type: signal.semantic?.semantic_type ?? null,
      generation_role: signal.configuration?.generation_role ?? null,
    };
  }
  expect(contracts, 'Every original signal and its explicit encoding must survive generation.').toEqual(expected);
}

async function verifyArtifacts(page: Page, project: string, minimumSignals: number, internalController?: string) {
  const workflow = await readProject(page, project, '/api/engineering/workflow?view=summary');
  expect(Object.keys(workflow.statuses).sort()).toEqual([...steps].sort());
  for (const step of steps) expect(done.has(workflow.statuses[step]), `${step}: ${workflow.statuses[step]}`).toBeTruthy();
  const jobs = (await readProject(page, project, '/api/simulations')).jobs;
  expect(jobs).toHaveLength(1);
  expect(jobs[0].status).toBe('completed');
  const snapshots = await readProject(page, project, '/api/engineering/workflow/snapshots');
  const snapshot = snapshots.simulations.find((item: { job_id: string }) => item.job_id === jobs[0].id);
  expect(snapshot).toBeTruthy();
  const full = await readProject(page, project, `/api/engineering/workflow/simulation-snapshots/${snapshot.id}`);
  const assessment = full.result.assessment;
  expect(assessment.scope_coverage.scope_mode).toBe('ALL');
  expect(assessment.scope_coverage.complete).toBe(true);
  expect(assessment.conformance).toBe('PASS');
  expect(assessment.failed_route_count).toBe(0);
  expect(assessment.observed_signal_count).toBeGreaterThanOrEqual(minimumSignals);
  const signals = await allObjects(page, project, 'signals');
  const excluded = assessment.scope_coverage.transport_exclusions ?? [];
  if (internalController) {
    const nodes = await allObjects(page, project, 'hardware-nodes');
    const controller = nodes.find(item => item.name === internalController);
    const messages = await allObjects(page, project, 'messages');
    expect(excluded.length).toBeGreaterThan(0);
    for (const item of excluded) {
      const message = messages.find(row => row.id === item.message_id);
      expect(item.reason_code).toBe('EXPLICIT_FUNCTION_OUTPUT_NOT_ROUTED');
      expect(message.configuration.routing.enabled).toBe(false);
      expect(message.configuration.communication_contract).toMatchObject({ role: 'INTERNAL_STATE', scope: 'FUNCTION_OUTPUT', producer_ref: controller.id, consumer_refs: [] });
    }
  } else expect(excluded).toHaveLength(0);
  const excludedSignals = new Set(excluded.flatMap((item: { signal_ids: string[] }) => item.signal_ids));
  expect(assessment.observed_signal_count, 'ALL must observe every canonical signal with a transport obligation.').toBe(signals.length - excludedSignals.size);
  for (const key of ['missing_observed_signal_ids', 'missing_observed_route_ids', 'missing_observed_network_ids']) expect(assessment[key]).toEqual([]);
  const trace = await readProject(page, project, `/api/simulations/${jobs[0].id}/trace-window?limit=10`);
  expect(trace.count).toBeGreaterThan(0);
  expect(trace.events.some((item: { signals?: unknown[] }) => item.signals && Object.keys(item.signals).length)).toBeTruthy();
  return { workflow, job: jobs[0].id, assessment };
}

async function completeThroughWizard(page: Page, project: string, restart: boolean, expectedHardware: string[] = [], crashSimulation = false,
  expectedSignals?: Record<string, unknown>, afterFirstModelApplied?: () => Promise<void>) {
  let reviewCount = 0;
  let runId: string | undefined;
  const reviewed = new Set<string>();
  let restartedJobId: string | undefined;
  let watchdog = new WizardProgressWatchdog(performance.now());
  for (let checkpoint = 0; checkpoint < 16; checkpoint++) {
    let workflow: any;
    let proposalId = '';
    let readyVersion = '';
    let readySince = 0;
    const isCheckpoint = async () => {
      watchdog.remaining(performance.now());
      await assertEngineeringPageHealthy(page);
      workflow = await readProject(page, project, '/api/engineering/workflow?view=summary');
      const progress = watchdog.observe(workflow, performance.now());
      if (progress.advanced) progressMilestones.get(test.info().testId)!.push({
        at: new Date().toISOString(), frontier: progress.frontier,
        completedThrough: steps[progress.frontier - 1],
        project: workflow.project_id, execution: workflow.context.agent_execution,
      });
      if (crashSimulation && !restartedJobId && done.has(workflow.statuses.validation)) {
        const jobs = (await readProject(page, project, '/api/simulations')).jobs;
        const running = jobs.find((job: { status: string }) => job.status === 'running');
        if (running) {
          restartedJobId = running.id;
          await restartApplication(page, true);
          await openWizard(page, project);
          return false;
        }
      }
      if (steps.every(step => done.has(workflow.statuses[step]))) return true;
      const execution = workflow.context.agent_execution;
      if (execution?.state === 'REVIEW_REQUIRED') {
        const conversation = await readProject(page, project, '/api/engineering/agent/conversation');
        proposalId = conversation.data.active_proposal;
        // Polling may still expose the just-applied review while the UI starts
        // its durable continuation. Wait for a distinct proposal, not its label.
        return Boolean(proposalId) && !reviewed.has(proposalId);
      }
      if (execution?.state === 'READY_TO_CONTINUE' || (execution?.state === 'BLOCKED' && execution.recoverable === true)) {
        if (readyVersion !== execution.updated_at) {
          readyVersion = execution.updated_at; readySince = Date.now();
        }
        // While a large continuation is generating, the last committed server
        // checkpoint can still be READY. Act only when the UI offers it too.
        const button = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' })
          .getByRole('button', { name: 'Auftrag fortsetzen', exact: true });
        return Date.now() - readySince > 5000 && await button.evaluateAll(buttons => buttons.some(button => !(button as HTMLButtonElement).disabled && button.getClientRects().length > 0 && getComputedStyle(button).visibility !== "hidden"));
      }
      return ['BLOCKED', 'FAILED', 'INCOMPLETE'].includes(execution?.state);
    };
    // A single poll previously timed all of Capacity -> Intelligence together.
    // Bound each genuine stage advance, while retries and restarts retain their
    // remaining deadline. The independent 20-minute test timeout is unchanged.
    let attempt = 0;
    while (!await isCheckpoint()) {
      const remaining = watchdog.remaining(performance.now());
      await page.waitForTimeout(Math.min([500, 1000, 2000][Math.min(attempt++, 2)], remaining));
    }
    runId ??= workflow.context.agent_execution?.run_id;
    expect(workflow.context.agent_execution?.run_id).toBe(runId);
    if (steps.every(step => done.has(workflow.statuses[step]))) {
      if (crashSimulation) expect(restartedJobId, 'A real running simulation must be observed and interrupted.').toBeTruthy();
      return { runId, reviewed: [...reviewed], restartedJobId };
    }
    const execution = workflow.context.agent_execution;
    const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
    if (['BLOCKED', 'FAILED', 'INCOMPLETE'].includes(execution?.state) && execution.recoverable !== true) {
      const conversation = await readProject(page, project, '/api/engineering/agent/conversation');
      const id = conversation.data?.active_proposal;
      const proposal = id ? await readProject(page, project, `/api/engineering/agent/proposals/${id}`) : null;
      await test.info().attach('wizard-blocker', { body: JSON.stringify({ execution,
        proposal: proposal?.data?.validation_result, visible: await dialog.innerText() }), contentType: 'application/json' });
      throw new Error(`Wizard ${execution.state} at ${execution.step}: ${execution.message}`);
    }
    if (execution?.state === 'READY_TO_CONTINUE' || (execution?.state === 'BLOCKED' && execution.recoverable === true)) {
      const button = dialog.getByRole('button', { name: 'Auftrag fortsetzen', exact: true });
      try {
        await button.click({ timeout: 2000 });
      } catch (error) {
        const latest = await readProject(page, project, '/api/engineering/workflow?view=summary');
        if (latest.context.agent_execution?.updated_at === execution.updated_at && await button.evaluateAll(buttons => buttons.some(button => !(button as HTMLButtonElement).disabled && button.getClientRects().length > 0 && getComputedStyle(button).visibility !== "hidden"))) throw error;
        continue;
      }
      await expect.poll(async () => (await readProject(page, project, '/api/engineering/workflow?view=summary')).context.agent_execution?.updated_at,
        { timeout: 60_000 }).not.toBe(execution.updated_at);
      continue;
    }
    const candidate = await readProject(page, project, `/api/engineering/agent/proposals/${proposalId}`);
    if (candidate.data.proposal_type === 'WIZARD_ENGINEERING_MODEL' && reviewCount === 0 && expectedHardware.length) {
      const hardware = candidate.data.changes
        .filter((change: { object_type: string }) => change.object_type === 'HardwareNode')
        .map((change: { data: { name: string } }) => change.data.name);
      expect(hardware, 'The UI must preserve the hardware explicitly named in the user request.')
        .toEqual(expect.arrayContaining(expectedHardware));
    }
    expect(reviewed.has(proposalId), 'The same proposal must not request review twice.').toBe(false);
    const applyResponse = page.waitForResponse(response => response.url().includes(`/proposals/${proposalId}/approve-apply`) && response.request().method() === 'POST', { timeout: 180_000 });
    const approval = dialog.getByRole('button', { name: /^(Freigeben, übernehmen & fortfahren|Übernehmen & fortfahren)$/ });
    await expect(approval).toBeEnabled({ timeout: 60_000 });
    await approval.click();
    const applied = await applyResponse;
    if (!applied.ok()) throw new Error(`HTTP ${applied.status()}: ${(await applied.text()).slice(0, 4000)}`);
    expect((await applied.json()).data.status).toBe('APPLIED');
    reviewed.add(proposalId); reviewCount++;
    // A distinct, actually committed manual review starts the next automatic
    // section. Its write still has the separate unchanged 180-second limit.
    watchdog = new WizardProgressWatchdog(performance.now(), workflow);
    if (candidate.data.proposal_type === 'WIZARD_ENGINEERING_MODEL' && expectedSignals) {
      await verifySignalContracts(page, project, expectedSignals);
    }
    if (reviewCount === 1 && afterFirstModelApplied) {
      await afterFirstModelApplied();
      // This one test explicitly submits AMEND and waits for its receipt. Only
      // that deliberate action permits binding its new request revision.
      const amended = await readProject(page, project, '/api/engineering/workflow?view=summary');
      expect(amended.context.agent_execution?.run_id).toBe(runId);
      watchdog = new WizardProgressWatchdog(performance.now(), amended);
    }
    if (reviewCount === 1) await openWizard(page, project); // Durable reload after a real commit.
    if (restart && reviewCount === 2) {
      await restartApplication(page);
      await openWizard(page, project);
    }
    await expect.poll(async () => {
      const current = await readProject(page, project, '/api/engineering/workflow?view=summary');
      return current.context.agent_execution?.updated_at !== execution.updated_at;
    }, { timeout: 60_000 }).toBe(true);
  }
  throw new Error('Wizard exceeded 16 review/continuation checkpoints.');
}

test('new small wizard traverses all nine stages and survives reload/restart @small', async ({ page }, testInfo) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  const project = 'nis-e2e-small-' + randomUUID();
  const dialog = await openWizard(page, project);
  await dialog.getByTitle('Projektname', { exact: true }).click();
  await dialog.locator('#engineering-project-name').fill('E2E small');
  await dialog.getByTitle('Aufgabe', { exact: true }).click();
  await dialog.getByLabel('Aufgabentext', { exact: true }).fill('Erzeuge ein Automotive CAN-FD Netzwerk mit einem Gateway System, den ECUs Motorsteuerung und Anzeige, einem Sensor MotorTemperature und einem Aktor MotorValve. MotorTemperature wird von Motorsteuerung ausgewertet. Motorsteuerung steuert MotorValve. Statuswerte werden an Anzeige und System übermittelt. Prüfe und arbeite bis Data Science & Intelligence.');
  await dialog.getByLabel('Weitere Hinweise', { exact: true }).fill('- Aktor-Befehle: {"MotorValve":{"length_bits":1,"data_type":"boolean","factor":1,"unit":"code","min_value":0,"max_value":1,"semantic":{"semantic_type":"BOOLEAN"},"data":{"enum_values":{"CLOSE":0,"OPEN":1}}}}');
  await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  for (const [label, value] of [['Gateways', '1'], ['Controller', '2'], ['Sensoren', '1'], ['Aktoren', '1']]) await dialog.getByLabel(`${label}: verbindliche Anzahl`, { exact: true }).fill(value);
  const startRequest = page.waitForRequest(request => request.url().endsWith('/api/agent/chat')
    && request.method() === 'POST' && request.postDataJSON()?.wizard_command?.action === 'START');
  // Use the same visible questionnaire navigation a user uses; never inject generated model rows.
  for (let step = 0; step < 10; step++) {
    const submit = dialog.locator('.eng-agent-questionnaire-head').getByRole('button');
    await expect(submit).toBeEnabled();
    const name = await submit.innerText();
    await submit.click();
    if (name === 'Übernehmen') break;
    if (step === 9) throw new Error('Questionnaire did not offer submit.');
  }
  const requested = (await startRequest).postDataJSON().wizard_command.wizard_context;
  expect(requested.technologies, 'An explicit CAN-FD task must not silently request LIN and SOME/IP.').toEqual(['CAN-FD (can_fd)']);
  const continuity = await completeThroughWizard(page, project, true,
    ['System', 'Motorsteuerung', 'Anzeige', 'MotorTemperature', 'MotorValve']);
  const artifacts = await verifyArtifacts(page, project, 5);
  const finished = page.waitForResponse(response => response.url().includes(`/runs/${continuity.runId}/finish`)
    && response.request().method() === 'POST');
  await dialog.getByRole('button', { name: 'Fertig stellen', exact: true }).click();
  expect((await finished).ok()).toBe(true);
  await expect(dialog).not.toBeVisible();
  await openWizard(page, project);
  expect((await readProject(page, project, '/api/simulations')).jobs).toHaveLength(1);
  expect(errors).toEqual([]);
  await testInfo.attach('evidence', { body: JSON.stringify({ project, ...continuity, ...artifacts }), contentType: 'application/json' });
});

for (const technology of ['I2C', 'Modbus RTU']) {
  test(`Raspberry Pi temperature and valve project completes all nine stages using ${technology} @nonautomotive`, async ({ page }, testInfo) => {
    const project = 'nis-e2e-embedded-' + randomUUID();
    const dialog = await openWizard(page, project);
    await dialog.getByTitle('Projektname', { exact: true }).click();
    await dialog.locator('#engineering-project-name').fill('Temperaturregelung');
    await dialog.getByTitle('Aufgabe', { exact: true }).click();
    await dialog.getByLabel('Aufgabentext', { exact: true }).fill(technology === 'I2C'
      ? '2 Aktoren für Ventile, 4 Sensoren für Temperaturen, und ein RaspberryPi'
      : `2 Aktoren für Ventile, 4 Sensoren für Temperaturen, und ein RaspberryPi. Embedded Systems. Alle Geräte kommunizieren über ${technology}. Prüfe und arbeite bis Data Science & Intelligence.`);
    await dialog.getByLabel('Weitere Hinweise', { exact: true }).fill('- Aktor-Befehle: {"Ventilaktor1":{"length_bits":1,"data_type":"boolean","factor":1,"unit":"code","min_value":0,"max_value":1,"semantic":{"semantic_type":"BOOLEAN"},"data":{"enum_values":{"CLOSE":0,"OPEN":1}}},"Ventilaktor2":{"length_bits":1,"data_type":"boolean","factor":1,"unit":"code","min_value":0,"max_value":1,"semantic":{"semantic_type":"BOOLEAN"},"data":{"enum_values":{"CLOSE":0,"OPEN":1}}}}');
    await dialog.getByTitle('Netzarchitektur', { exact: true }).click();
    await dialog.getByRole('radio', { name: /Variante 0/ }).check();
    await dialog.getByTitle('Geräteumfang', { exact: true }).click();
    if (technology === 'I2C') {
      await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
      await dialog.getByLabel('RaspberryPi: Anschluss', { exact: true }).selectOption('I2C');
      await expect(dialog.getByLabel('Temperatursensor1: Anschluss', { exact: true })).toHaveValue('');
      await expect(dialog.getByRole('button', { name: 'Übernehmen', exact: true })).toBeDisabled();
      for (const name of ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4', 'Ventilaktor1', 'Ventilaktor2']) {
        await dialog.getByLabel(`${name}: Anschluss`, { exact: true }).selectOption('I2C');
      }
    }
    await dialog.getByRole('button', { name: 'Übernehmen', exact: true }).click();
    const continuity = await completeThroughWizard(page, project, true, ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4', 'Ventilaktor1', 'Ventilaktor2']);
    const artifacts = await verifyArtifacts(page, project, 7, 'RaspberryPi');
    const interfaces = await allObjects(page, project, 'hardware-interfaces');
    expect(interfaces.length).toBeGreaterThanOrEqual(7);
    expect(interfaces.every(item => !/automotive|can|lin/i.test(item.technology))).toBe(true);
    const hardware = await allObjects(page, project, 'hardware-nodes');
    expect(hardware.every(item => item.domain !== 'automotive')).toBe(true);
    const finished = page.waitForResponse(response => response.url().includes(`/runs/${continuity.runId}/finish`)
      && response.request().method() === 'POST');
    await dialog.getByRole('button', { name: 'Fertig stellen', exact: true }).click();
    expect((await finished).ok()).toBe(true);
    await expect(dialog).not.toBeVisible();
    await openWizard(page, project);
    expect((await readProject(page, project, '/api/simulations')).jobs).toHaveLength(1);
    await testInfo.attach('nonautomotive-evidence', { body: JSON.stringify({ project, technology, ...continuity, ...artifacts }), contentType: 'application/json' });
  });
}

test('exact confirmed 50/250/250 request completes through real wizard review @large', async ({ page }, testInfo) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message));
  const project = 'nis-e2e-large-' + randomUUID();
  const runId = randomUUID();
  const original = await readFile(new URL('./fixtures/wizard-large-50-250-250.txt', import.meta.url), 'utf8');
  const metadata = JSON.parse(await readFile(new URL('./fixtures/wizard-large-50-250-250.json', import.meta.url), 'utf8'));
  const baseline = JSON.parse(await readFile(new URL('./fixtures/wizard-large-signal-contracts.json', import.meta.url), 'utf8'));
  const prompt = original.replace(/^- Lauf-ID:.*$/m, '- Lauf-ID: ' + runId);
  // Replay the captured, already confirmed input through the normal START API.
  // All proposal inspection, approval, continuation and reloads below use UI.
  const started = await page.request.post('/api/engineering/agent/chat', {
    headers: { 'X-Project-ID': project }, timeout: 240_000,
    data: { prompt, wizard_command: { action: 'START', run_id: runId, operation_id: randomUUID(),
      target: 'data_science_intelligence', wizard_context: { ...metadata.wizard_context, project_id: project, run_id: runId } } },
  });
  if (!started.ok()) throw new Error(`HTTP ${started.status()}: ${(await started.text()).slice(0, 4000)}`);
  await openWizard(page, project);
  const continuity = await completeThroughWizard(page, project, false, [], true, baseline.signals);
  expect(continuity.runId).toBe(runId);
  const hardware = await allObjects(page, project, 'hardware-nodes');
  expect(hardware.filter(item => item.device_type === 'SensorController')).toHaveLength(250);
  expect(hardware.filter(item => item.device_type === 'ActuatorController')).toHaveLength(250);
  expect(hardware.filter(item => item.device_type === 'ECU').length).toBeGreaterThanOrEqual(50);
  const artifacts = await verifyArtifacts(page, project, 1404);
  await verifySignalContracts(page, project, baseline.signals);
  expect(artifacts.job).toBe(continuity.restartedJobId);
  expect(errors).toEqual([]);
  await testInfo.attach('evidence', { body: JSON.stringify({ project, fixture: metadata.request_sha256, ...continuity, ...artifacts }), contentType: 'application/json' });
});

test('a real AMEND after model approval adds the requested sensor and reuses its networks @amend', async ({ page }, testInfo) => {
  const project = 'nis-e2e-amend-' + randomUUID();
  const runId = randomUUID();
  const graph = [
    { cluster_id: 'drive', network_id: 'can_fd', network_label: 'CAN-FD', bus_name: 'Drive',
      controllers: [{ ecu: 'Motorsteuerung', sensors: [] as string[], actuators: [] }],
      hmi_routes: [{ source: 'Motorsteuerung', target: 'Anzeige' }, { source: 'Anzeige', target: 'Motorsteuerung' },
        { source: 'System', target: 'Anzeige' }] },
    { cluster_id: 'display', network_id: 'ethernet', network_label: 'Ethernet', bus_name: 'Display',
      controllers: [{ ecu: 'Anzeige', sensors: [] as string[], actuators: [] }] },
  ];
  const prompt = `Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: ${runId}
- Industrie: Automotive
- Netzwerktechnologien: CAN-FD (can_fd); Ethernet (ethernet)
- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":0,"actuators":0}
- Systemcluster-Graph: ${JSON.stringify(graph)}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Motorsteuerung und Anzeige mit einem zentralen Gateway System verbinden.`;
  const started = await page.request.post('/api/engineering/agent/chat', {
    headers: { 'X-Project-ID': project }, timeout: 120_000,
    data: { prompt, wizard_command: { action: 'START', run_id: runId, operation_id: randomUUID(),
      target: 'data_science_intelligence', wizard_context: { project_id: project, run_id: runId,
        project_name: 'E2E amendment', scope_ids: steps, mode: 'full',
        process_ids: ['defaults', 'review_gate', 'approve_after_allow'], task: 'Motorsteuerung und Anzeige an System' } } },
  });
  if (!started.ok()) throw new Error(`HTTP ${started.status()}: ${(await started.text()).slice(0, 4000)}`);
  await openWizard(page, project);
  let originalNetworks: string[] = [];
  const amend = async () => {
    originalNetworks = (await readProject(page, project, '/api/engineering/workflow')).parameters.networks
      .map((item: { id: string }) => item.id).sort();
    expect(originalNetworks).toHaveLength(2);
    graph[0].controllers[0].sensors.push('MotorTemperature');
    const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
    const expand = dialog.getByRole('button', { name: 'Ergänzen', exact: true });
    await expect(expand).toBeEnabled({ timeout: 120_000 });
    await expand.click();
    const field = dialog.getByRole('region', { name: 'Engineering-Auftrag ergänzen', exact: true }).getByRole('textbox');
    await field.fill('Ergänze MotorTemperature als Sensor der Motorsteuerung. Die vollständige aktualisierte Freigabe lautet:\n'
      + '- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":1,"actuators":0}\n'
      + '- Systemcluster-Graph: ' + JSON.stringify(graph));
    await dialog.getByRole('button', { name: 'Ergänzung analysieren', exact: true }).click();
    await expect(field).not.toBeVisible({ timeout: 120_000 });
  };
  const continuity = await completeThroughWizard(page, project, false, ['Motorsteuerung', 'Anzeige'], false, undefined, amend);
  const hardware = await allObjects(page, project, 'hardware-nodes');
  const owner = hardware.find(item => item.name === 'Motorsteuerung');
  const sensors = hardware.filter(item => item.name === 'MotorTemperature');
  expect(sensors).toHaveLength(1);
  expect(sensors[0].identity.system_owner_id).toBe(owner.id);
  const sensorNetwork = 'Drive-IO-motorsteuerung-can-fd-S01';
  const networks = (await readProject(page, project, '/api/engineering/workflow')).parameters.networks;
  expect(networks.map((item: { id: string }) => item.id).sort()).toEqual([...originalNetworks, sensorNetwork].sort());
  expect(new Set(networks.map((item: { name: string }) => item.name)).size).toBe(networks.length);
  const topology = (await readProject(page, project, '/api/engineering/workflow/network-view')).topology;
  const localEdge = topology.edges.find((edge: any) => edge.physicalNetworkId === sensorNetwork);
  expect(localEdge).toBeTruthy();
  expect(localEdge.bus).toBe('can_fd');
  expect(Object.values(localEdge.routingMetadata)).toContainEqual(expect.objectContaining({
    source: sensors[0].id, target: owner.id, approvalState: 'APPROVED', protocol: 'CAN_FD',
  }));
  for (const [side, hardwareId] of [['source', sensors[0].id], ['target', owner.id]]) {
    const node = topology.nodes.find((item: any) => item.id === localEdge[side]);
    expect(node.engineeringId).toBe(hardwareId);
    expect(node.ports).toContainEqual(expect.objectContaining({ id: localEdge[side + 'Port'],
      bus: 'can_fd', physicalNetworkId: sensorNetwork }));
  }
  const artifacts = await verifyArtifacts(page, project, 1);
  await testInfo.attach('amendment-evidence', { body: JSON.stringify({ project, ...continuity, ...artifacts }), contentType: 'application/json' });
});
