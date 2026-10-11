// fae20c1551d5a92379485b74a4a7d85c3d390abd
import { test, expect } from 'playwright/test';
import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { WizardProgressWatchdog, WIZARD_STEPS, WIZARD_DONE } from './support/wizard-progress-watchdog';
import { reviewVirtualTransports } from './support/native-transport-fixtures';
const steps = WIZARD_STEPS;
const done = WIZARD_DONE;
const writeTimings = new Map();
const workflowPageFailures = new WeakMap();
const progressMilestones = new Map();
test.beforeEach(async ({
  page
}, info) => {
  const rows = [];
  writeTimings.set(info.testId, rows);
  workflowPageFailures.set(page, []);
  progressMilestones.set(info.testId, []);
  const requests = new Map();
  page.on('request', request => {
    if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) return;
    const row = {
      url: request.url(),
      started: Date.now()
    };
    rows.push(row);
    requests.set(request, row);
  });
  page.on('response', response => {
    const row = requests.get(response.request());
    if (row) row.status = response.status();
    if (response.status() === 413 && /^\/api\/engineering\/workflow(?:\/|$)/.test(new URL(response.url()).pathname)) {
      workflowPageFailures.get(page).push(`HTTP 413: ${response.url()}`);
    }
  });
  page.on('requestfinished', request => {
    const row = requests.get(request);
    if (row) row.duration_ms = Date.now() - row.started;
  });
  page.on('requestfailed', request => {
    const row = requests.get(request);
    if (row) {
      var _request$failure;
      row.duration_ms = Date.now() - row.started;
      row.failure = (_request$failure = request.failure()) === null || _request$failure === void 0 ? void 0 : _request$failure.errorText;
    }
  });
});
test.afterEach(async ({
  page
}, info) => {
  await info.attach('write-request-timings', {
    body: JSON.stringify(writeTimings.get(info.testId) || []),
    contentType: 'application/json'
  });
  await info.attach('workflow-progress-boundaries', {
    body: JSON.stringify(progressMilestones.get(info.testId) || []),
    contentType: 'application/json'
  });
  await info.attach('workflow-page-failures', {
    body: JSON.stringify(workflowPageFailures.get(page) || []),
    contentType: 'application/json'
  });
  writeTimings.delete(info.testId);
  progressMilestones.delete(info.testId);
  expect(workflowPageFailures.get(page), 'The underlying engineering page must remain readable throughout reload and recovery.').toEqual([]);
  await expect(page.getByRole('heading', {
    name: 'Die Ansicht konnte nicht geladen werden.',
    exact: true
  }), 'A crashed parameter or engineering page must never count as a successful wizard detour.').not.toBeVisible();
});
async function assertEngineeringPageHealthy(page) {
  expect(workflowPageFailures.get(page), 'A working wizard overlay must not conceal a workflow HTTP 413.').toEqual([]);
  expect(await page.getByText('Engineering-API nicht erreichbar', {
    exact: true
  }).isVisible(), 'The underlying engineering page must not show its API error view.').toBe(false);
  await expect(page.getByRole('heading', {
    name: 'Die Ansicht konnte nicht geladen werden.',
    exact: true
  })).not.toBeVisible();
}
async function readProject(page, project, path) {
  const result = await page.request.get(path, {
    headers: {
      'X-Project-ID': project
    },
    timeout: 60000
  });
  try {
    if (!result.ok()) throw new Error(`${path}: HTTP ${result.status()} ${(await result.text()).slice(0, 4000)}`);
    return await result.json();
  } finally {
    // Playwright otherwise retains every polled response until context teardown.
    // Keep the parsed evidence, release its duplicate transport body immediately.
    await result.dispose();
  }
}
async function readWarningReviewState(page, project) {
  var _verified$context$age2, _verified$context$age3;
  const authority = await readProject(page, project, '/api/engineering/workflow?view=summary');
  const parameters = await readProject(page, project, '/api/engineering/workflow/parameters');
  const verified = await readProject(page, project, '/api/engineering/workflow?view=summary');
  expect(parameters.project_id).toBe(project);
  expect(authority.project_id).toBe(project);
  expect(verified.project_id).toBe(project);
  for (const field of ['run_id', 'request_revision']) {
    var _verified$context$age, _authority$context$ag;
    expect((_verified$context$age = verified.context.agent_execution) === null || _verified$context$age === void 0 ? void 0 : _verified$context$age[field]).toBe((_authority$context$ag = authority.context.agent_execution) === null || _authority$context$ag === void 0 ? void 0 : _authority$context$ag[field]);
  }
  return {
    project_id: verified.project_id,
    statuses: verified.statuses,
    context: {
      agent_execution: {
        run_id: (_verified$context$age2 = verified.context.agent_execution) === null || _verified$context$age2 === void 0 ? void 0 : _verified$context$age2.run_id,
        request_revision: (_verified$context$age3 = verified.context.agent_execution) === null || _verified$context$age3 === void 0 ? void 0 : _verified$context$age3.request_revision
      }
    },
    parameters: {
      preflight_warning_approval: parameters.parameters.preflight_warning_approval
    }
  };
}
async function openWizard(page, project) {
  await page.goto(`/studio/engineering?assistant=project&project=${project}`, {
    waitUntil: 'load'
  });
  const dialog = page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  });
  await expect(dialog).toBeVisible();
  await assertEngineeringPageHealthy(page);
  return dialog;
}
test('project naming form cards use the full wizard width @layout', async ({
  page
}) => {
  const dialog = await openWizard(page, 'nis-e2e-project-name-layout-' + randomUUID());
  const step = dialog.locator('fieldset.agent-project-name-step');
  await expect(step).toBeVisible();
  const stepWidth = await step.evaluate(element => element.getBoundingClientRect().width);
  const cards = await step.locator(':scope > label').all();
  expect(cards).toHaveLength(4);
  for (const card of cards) {
    const width = await card.evaluate(element => element.getBoundingClientRect().width);
    expect(width).toBeGreaterThan(stepWidth * 0.85);
  }
});
async function allObjects(page, project, resource) {
  const items = [];
  for (let offset = 0;; offset += 500) {
    const response = await readProject(page, project, `/api/engineering/${resource}?limit=500&offset=${offset}`);
    items.push(...response.items);
    if (response.items.length < 500) return items;
  }
}
async function restartApplication(page, crash = false) {
  const container = process.env.NIS_E2E_APP_CONTAINER;
  expect(container).toMatch(/^nis-e2e-app-[a-f0-9]+$/);
  const docker = process.env.NIS_TEST_DOCKER || 'docker';
  const label = execFileSync(docker, ['inspect', container, '--format', '{{index .Config.Labels "networkis.test"}}'], {
    encoding: 'utf8'
  }).trim();
  expect(label).toBe('disposable');
  execFileSync(docker, ['restart', ...(crash ? ['-t', '0'] : []), container], {
    timeout: 60000
  });
  await expect.poll(async () => {
    try {
      return (await page.request.get('/api/ready', {
        timeout: 2000
      })).ok();
    } catch {
      return false;
    }
  }, {
    timeout: 120000
  }).toBe(true);
}
async function verifySignalContracts(page, project, expected) {
  const [hardware, functions, messages, signals] = await Promise.all(['hardware-nodes', 'functions', 'messages', 'signals'].map(resource => allObjects(page, project, resource)));
  const nodes = new Map(hardware.map(item => [item.id, item]));
  const functionsById = new Map(functions.map(item => [item.id, item]));
  const messagesById = new Map(messages.map(item => [item.id, item]));
  const contracts = {};
  for (const signal of signals) {
    var _ref, _signal$data$enum_val, _signal$data, _signal$semantic$sema, _signal$semantic, _signal$configuration, _signal$configuration2;
    const message = messagesById.get(signal.message_id);
    expect(message).toBeTruthy();
    const reference = message.configuration.communication_contract.producer_ref;
    const fn = functionsById.get(reference);
    const owner = nodes.get(reference) || fn && nodes.get(fn.hardware_node_id);
    const producer = (owner === null || owner === void 0 ? void 0 : owner.device_type) === 'Gateway' ? '$gateway' : (_ref = nodes.get(reference) || fn) === null || _ref === void 0 ? void 0 : _ref.name;
    expect(producer).toBeTruthy();
    const key = [producer, message.name, signal.name].join(' :: ');
    expect(contracts[key], 'Semantic signal identity must be unique: ' + key).toBeUndefined();
    contracts[key] = {
      ...Object.fromEntries(['start_bit', 'length_bits', 'data_type', 'factor', 'offset_value', 'unit', 'min_value', 'max_value', 'byte_order'].map(field => {
        var _signal$field;
        return [field, (_signal$field = signal[field]) !== null && _signal$field !== void 0 ? _signal$field : null];
      })),
      enum_values: (_signal$data$enum_val = (_signal$data = signal.data) === null || _signal$data === void 0 ? void 0 : _signal$data.enum_values) !== null && _signal$data$enum_val !== void 0 ? _signal$data$enum_val : null,
      semantic_type: (_signal$semantic$sema = (_signal$semantic = signal.semantic) === null || _signal$semantic === void 0 ? void 0 : _signal$semantic.semantic_type) !== null && _signal$semantic$sema !== void 0 ? _signal$semantic$sema : null,
      generation_role: (_signal$configuration = (_signal$configuration2 = signal.configuration) === null || _signal$configuration2 === void 0 ? void 0 : _signal$configuration2.generation_role) !== null && _signal$configuration !== void 0 ? _signal$configuration : null
    };
  }
  expect(contracts, 'Every original signal and its explicit encoding must survive generation.').toEqual(expected);
}
async function verifyArtifacts(page, project, minimumCanonicalSignals, internalController, expectedParameters, expectedNativeRates) {
  var _assessment$scope_cov;
  // The completed model is stable; these independent reads need no serial waits.
  const [workflow, jobList, snapshots, signals, messages] = await Promise.all([readProject(page, project, '/api/engineering/workflow?view=summary'), readProject(page, project, '/api/simulations'), readProject(page, project, '/api/engineering/workflow/snapshots'), allObjects(page, project, 'signals'), allObjects(page, project, 'messages')]);
  expect(Object.keys(workflow.statuses).sort()).toEqual([...steps].sort());
  for (const step of steps) expect(done.has(workflow.statuses[step]), `${step}: ${workflow.statuses[step]}`).toBeTruthy();
  const jobs = jobList.jobs;
  expect(jobs).toHaveLength(1);
  expect(jobs[0].status).toBe('completed');
  const snapshot = snapshots.simulations.find(item => item.job_id === jobs[0].id);
  expect(snapshot).toBeTruthy();
  const full = await readProject(page, project, `/api/engineering/workflow/simulation-snapshots/${snapshot.id}`);
  if (expectedParameters) {
    const {
      data_bitrate,
      can_fd_data_prescaler,
      ...runtimeParameters
    } = expectedParameters;
    expect(full.configuration.parameters).toMatchObject(runtimeParameters);
    const canFdNetworks = full.configuration.networks.filter(network => network.technology === 'can_fd');
    expect(canFdNetworks.length, 'The edited CAN-FD configuration must reach a physical simulation network.').toBeGreaterThan(0);
    for (const network of canFdNetworks) expect(network).toMatchObject({
      data_bitrate,
      can_fd_data_prescaler
    });
  }
  if (expectedNativeRates) {
    for (const [technology, rates] of Object.entries(expectedNativeRates)) {
      const networks = full.configuration.networks.filter(network => network.technology === technology);
      expect(networks.length, `Saved ${technology} rates must reach the frozen simulation.`).toBeGreaterThan(0);
      for (const network of networks) expect(network).toMatchObject(rates);
    }
  }
  const assessment = full.result.assessment;
  expect(assessment.scope_coverage.scope_mode).toBe('ALL');
  expect(assessment.scope_coverage.complete).toBe(true);
  expect(assessment.conformance).toBe('PASS');
  expect(assessment.failed_route_count).toBe(0);
  expect(signals.length, 'The full canonical signal inventory must survive generation.').toBeGreaterThanOrEqual(minimumCanonicalSignals);
  const excluded = (_assessment$scope_cov = assessment.scope_coverage.transport_exclusions) !== null && _assessment$scope_cov !== void 0 ? _assessment$scope_cov : [];
  for (const item of excluded) {
    const message = messages.find(row => row.id === item.message_id);
    expect(message, `Excluded message ${item.message_id} must exist.`).toBeTruthy();
    expect(message.configuration.routing.enabled).toBe(false);
    const contract = message.configuration.communication_contract;
    expect(contract.consumer_refs).toEqual([]);
    expect(item.reason_code).toBe(contract.role === 'INTERNAL_STATE' ? 'INTERNAL_STATE_NOT_ROUTED' : 'EXPLICIT_FUNCTION_OUTPUT_NOT_ROUTED');
  }
  if (internalController) {
    const nodes = await allObjects(page, project, 'hardware-nodes');
    const controller = nodes.find(item => item.name === internalController);
    expect(excluded.length).toBeGreaterThan(0);
    for (const item of excluded) {
      const message = messages.find(row => row.id === item.message_id);
      expect(message.configuration.communication_contract).toMatchObject({
        role: 'INTERNAL_STATE',
        scope: 'INTERNAL',
        producer_ref: controller.id,
        consumer_refs: []
      });
    }
  }
  const excludedSignals = new Set(excluded.flatMap(item => item.signal_ids));
  expect(assessment.observed_signal_count, 'ALL must observe every canonical signal with a transport obligation.').toBe(signals.length - excludedSignals.size);
  for (const key of ['missing_observed_signal_ids', 'missing_observed_route_ids', 'missing_observed_network_ids']) expect(assessment[key]).toEqual([]);
  const trace = await readProject(page, project, `/api/simulations/${jobs[0].id}/trace-window?limit=10`);
  expect(trace.count).toBeGreaterThan(0);
  expect(trace.events.some(item => item.signals && Object.keys(item.signals).length)).toBeTruthy();
  return {
    workflow,
    job: jobs[0].id,
    assessment,
    parameter_proof: expectedParameters ? {
      saved: expectedParameters,
      simulation_rates: full.configuration.networks.map(network => ({
        technology: network.technology,
        bitrate: network.bitrate,
        arbitration_bitrate: network.arbitration_bitrate,
        data_bitrate: network.data_bitrate,
        hardware_evidence: network.hardware_evidence
      }))
    } : undefined
  };
}
// Exercise the user's detour, including repeated saves in an existing run.
// Reads inspect real persisted state; writes and return navigation use the UI.
async function repeatParameterReturn(page, project, proposalId, scenarios, seeds = [41, 43, 42]) {
  const before = await readProject(page, project, '/api/engineering/workflow?view=summary');
  const identity = before.context.agent_execution;
  expect(identity.run_id).toBeTruthy();
  const nodeIds = (await allObjects(page, project, 'hardware-nodes')).map(item => item.id).sort();
  const starts = [];
  const trackStarts = request => {
    var _request$postDataJSON;
    if (request.url().endsWith('/api/agent/chat') && request.method() === 'POST' && ((_request$postDataJSON = request.postDataJSON()) === null || _request$postDataJSON === void 0 || (_request$postDataJSON = _request$postDataJSON.wizard_command) === null || _request$postDataJSON === void 0 ? void 0 : _request$postDataJSON.action) === 'START') starts.push(request.postDataJSON());
  };
  const evidence = [];
  page.on('request', trackStarts);
  try {
    const wizard = page.getByRole('dialog', {
      name: 'Engineering-Auftrag erstellen'
    });
    if (await wizard.isVisible()) {
      // A captured API START does not activate a browser wizard session. Enter
      // parameters through the actual workflow card, just as a user does.
      await wizard.locator('.agent-wizard-progress-card[href*="mode=parameters"]').click();
      await expect(page.getByRole('button', {
        name: 'Zurück zum Auftrag',
        exact: true
      })).toBeVisible();
    }
    for (const [cycle, seed] of seeds.entries()) {
      for (const scenario of scenarios) {
        var _saved$parameters$sim;
        await page.goto(`/studio?mode=parameters&project=${encodeURIComponent(project)}&technology=${scenario.technology}&proposal=${proposalId}#parameter-findings`);
        await assertEngineeringPageHealthy(page);
        const common = page.locator('.parameter-group-common');
        for (const [field, value] of Object.entries(scenario.fields)) {
          var _scenario$editFields;
          const input = page.locator(`#${field}`);
          const details = input.locator('xpath=ancestor::details[1]');
          if ((await details.count()) && (await details.getAttribute('open')) === null) await details.locator(':scope > summary').click();
          if ((_scenario$editFields = scenario.editFields) !== null && _scenario$editFields !== void 0 && _scenario$editFields.includes(field)) await input.fill(value);else await expect(input).toHaveValue(value);
        }
        await common.locator('#seed').fill(String(seed));
        await page.getByRole('button', {
          name: 'Parameter speichern →',
          exact: true
        }).click();
        await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
        const saved = await readProject(page, project, '/api/engineering/workflow/parameters');
        expect(saved.project_id).toBe(project);
        const scoped = saved.parameters.technology_parameters[scenario.technology];
        const assumed = (_saved$parameters$sim = saved.parameters.simulation_parameter_assumptions) === null || _saved$parameters$sim === void 0 ? void 0 : _saved$parameters$sim[scenario.technology];
        expect(scoped.values.seed).toBe(seed);
        const nativeValues = {
          ...(assumed === null || assumed === void 0 ? void 0 : assumed.values),
          ...scoped.values
        };
        expect(nativeValues).toMatchObject(scenario.native);
        for (const [key, value] of Object.entries(scenario.native)) {
          const confirmed = Object.hasOwn(scoped.values, key);
          expect((confirmed ? scoped : assumed).provenance[key]).toMatchObject(confirmed ? {
            source: 'USER_CONFIRMED',
            status: 'CONFIRMED',
            value
          } : {
            source: 'NIS_SIMULATION_ASSUMPTION',
            status: 'ASSUMED',
            technology: scenario.technology,
            hardware_evidence: false,
            value
          });
        }
        const userValues = await readProject(page, project, '/api/engineering/workflow/parameters/user-defined-values');
        expect(userValues.project_id).toBe(project);
        expect(userValues.value_origin).toBe('USER_DEFINED_VALUE');
        expect(userValues.parameters.technology_defaults).toBeUndefined();
        expect(userValues.parameters.technology_parameters[scenario.technology]).toEqual(scoped);
        const stale = await readProject(page, project, `/api/engineering/agent/proposals/${proposalId}?view=status`);
        expect(stale.data.status).toBe('OUTDATED');
        const canonicalIds = stale.data.canonical_ids;
        await page.reload();
        await expect(common.locator('#seed')).toHaveValue(String(seed));
        for (const [field, value] of Object.entries(scenario.fields)) {
          const input = page.locator(`#${field}`);
          const details = input.locator('xpath=ancestor::details[1]');
          if ((await details.count()) && (await details.getAttribute('open')) === null) await details.locator(':scope > summary').click();
          await expect(input).toHaveValue(value);
        }
        // Keep the existing delayed-restore regression, using real responses.
        let resumeRestore;
        const restorePause = new Promise(resolve => {
          resumeRestore = resolve;
        });
        const delayRestore = async route => {
          await restorePause;
          await route.continue();
        };
        const delayed = cycle === 0 && scenario === scenarios[0];
        if (delayed) await page.route('**/api/engineering/workflow?view=summary', delayRestore);
        const dialog = page.getByRole('dialog', {
          name: 'Engineering-Auftrag erstellen'
        });
        try {
          await page.getByRole('button', {
            name: 'Zurück zum Auftrag',
            exact: true
          }).click();
          if (delayed) {
            await expect(dialog.getByRole('region', {
              name: 'Gespeicherten Auftrag wiederherstellen'
            })).toBeVisible();
            await expect(dialog).not.toContainText('Projektname: Schritt 1');
          }
        } finally {
          resumeRestore();
          if (delayed) await page.unrouteAll({
            behavior: 'wait'
          });
        }
        // Match the existing proposal-review readiness budget below. The new
        // return assertion must not impose a shorter limit on the large model.
        await expect(dialog.getByRole('region', {
          name: 'Engineering-Vorschlag'
        })).toContainText('Geprüft · Freigabe offen', {
          timeout: 60000
        });
        await expect(dialog).toContainText('Statusübersicht: Schritt 5 von 5');
        const restored = await readProject(page, project, '/api/engineering/workflow?view=summary');
        expect(restored.project_id).toBe(project);
        expect(restored.context.agent_execution.run_id).toBe(identity.run_id);
        expect(restored.context.agent_execution.request_revision).toBe(identity.request_revision);
        expect(restored.context.agent_execution.state).toBe('REVIEW_REQUIRED');
        expect(restored.context.agent_execution.step).toBe(identity.step);
        for (const step of steps) if (done.has(before.statuses[step])) expect(done.has(restored.statuses[step]), `Returning must preserve completed stage ${step}.`).toBe(true);
        const conversation = await readProject(page, project, '/api/engineering/agent/conversation');
        expect(conversation.data.active_proposal).toBe(proposalId);
        const fresh = await readProject(page, project, `/api/engineering/agent/proposals/${proposalId}?view=status`);
        expect(fresh.data.status).toBe('VALIDATED');
        expect(fresh.data.canonical_ids).toEqual(canonicalIds);
        expect((await allObjects(page, project, 'hardware-nodes')).map(item => item.id).sort()).toEqual(nodeIds);
        const after = await readProject(page, project, '/api/engineering/workflow/parameters');
        expect(after.parameters).toEqual(saved.parameters);
        expect(starts, 'Returning from parameters must never restart this run.').toEqual([]);
        evidence.push({
          cycle: cycle + 1,
          technology: scenario.technology,
          seed,
          run_id: identity.run_id,
          proposal_id: proposalId,
          saved_values: scoped,
          assumptions: assumed,
          restored_status: fresh.data.status,
          canonical_ids: canonicalIds
        });
      }
    }
  } finally {
    page.off('request', trackStarts);
    await test.info().attach('repeated-parameter-return', {
      body: JSON.stringify(evidence),
      contentType: 'application/json'
    });
  }
}
async function completeThroughWizard(page, project, restart, expectedHardware = [], crashSimulation = false, expectedSignals, afterFirstModelApplied, stopOnEvidenceBlock = false, beforeProposalReview) {
  let reviewCount = 0;
  let runId;
  const reviewed = new Set();
  let restartedJobId;
  let watchdog = new WizardProgressWatchdog(performance.now());
  for (let checkpoint = 0; checkpoint < 16; checkpoint++) {
    var _workflow$context$age, _workflow$context$age2, _execution$blocking_f, _execution$message;
    let workflow;
    let proposalId = '';
    let readyVersion = '';
    let readySince = 0;
    const isCheckpoint = async () => {
      watchdog.remaining(performance.now());
      await assertEngineeringPageHealthy(page);
      workflow = await readProject(page, project, '/api/engineering/workflow?view=summary');
      const progress = watchdog.observe(workflow, performance.now());
      if (progress.advanced) progressMilestones.get(test.info().testId).push({
        at: new Date().toISOString(),
        frontier: progress.frontier,
        completedThrough: steps[progress.frontier - 1],
        project: workflow.project_id,
        execution: workflow.context.agent_execution
      });
      if (crashSimulation && !restartedJobId && done.has(workflow.statuses.validation)) {
        const jobs = (await readProject(page, project, '/api/simulations')).jobs;
        const running = jobs.find(job => job.status === 'running');
        if (running) {
          restartedJobId = running.id;
          await restartApplication(page, true);
          await openWizard(page, project);
          return false;
        }
      }
      if (steps.every(step => done.has(workflow.statuses[step]))) return true;
      const execution = workflow.context.agent_execution;
      if ((execution === null || execution === void 0 ? void 0 : execution.state) === 'REVIEW_REQUIRED') {
        const conversation = await readProject(page, project, '/api/engineering/agent/conversation');
        proposalId = conversation.data.active_proposal;
        // Polling may still expose the just-applied review while the UI starts
        // its durable continuation. Wait for a distinct proposal, not its label.
        return Boolean(proposalId) && !reviewed.has(proposalId);
      }
      if ((execution === null || execution === void 0 ? void 0 : execution.state) === 'READY_TO_CONTINUE' || (execution === null || execution === void 0 ? void 0 : execution.state) === 'BLOCKED' && execution.recoverable === true) {
        if (readyVersion !== execution.updated_at) {
          readyVersion = execution.updated_at;
          readySince = Date.now();
        }
        // While a large continuation is generating, the last committed server
        // checkpoint can still be READY. Act only when the UI offers it too.
        const button = page.getByRole('dialog', {
          name: 'Engineering-Auftrag erstellen'
        }).getByRole('button', {
          name: 'Auftrag fortsetzen',
          exact: true
        });
        return Date.now() - readySince > 5000 && (await button.evaluateAll(buttons => buttons.some(button => !button.disabled && button.getClientRects().length > 0 && getComputedStyle(button).visibility !== "hidden")));
      }
      return ['BLOCKED', 'FAILED', 'INCOMPLETE'].includes(execution === null || execution === void 0 ? void 0 : execution.state);
    };
    // A single poll previously timed all of Capacity -> Intelligence together.
    // Bound each genuine stage advance, while retries and restarts retain their
    // remaining deadline. The independent 20-minute test timeout is unchanged.
    let attempt = 0;
    while (!(await isCheckpoint())) {
      const remaining = watchdog.remaining(performance.now());
      await page.waitForTimeout(Math.min([500, 1000, 2000][Math.min(attempt++, 2)], remaining));
    }
    runId !== null && runId !== void 0 ? runId : runId = (_workflow$context$age = workflow.context.agent_execution) === null || _workflow$context$age === void 0 ? void 0 : _workflow$context$age.run_id;
    expect((_workflow$context$age2 = workflow.context.agent_execution) === null || _workflow$context$age2 === void 0 ? void 0 : _workflow$context$age2.run_id).toBe(runId);
    if (steps.every(step => done.has(workflow.statuses[step]))) {
      if (crashSimulation) expect(restartedJobId, 'A real running simulation must be observed and interrupted.').toBeTruthy();
      return {
        runId,
        reviewed: [...reviewed],
        restartedJobId
      };
    }
    const execution = workflow.context.agent_execution;
    const dialog = page.getByRole('dialog', {
      name: 'Engineering-Auftrag erstellen'
    });
    if (stopOnEvidenceBlock && (execution === null || execution === void 0 ? void 0 : execution.state) === 'BLOCKED' && (_execution$blocking_f = execution.blocking_findings) !== null && _execution$blocking_f !== void 0 && _execution$blocking_f.length) {
      throw new Error(`Wizard BLOCKED at ${execution.step}: ${execution.message}`);
    }
    if ((execution === null || execution === void 0 ? void 0 : execution.state) === 'BLOCKED' && (_execution$message = execution.message) !== null && _execution$message !== void 0 && _execution$message.includes('READY_WITH_WARNINGS')) {
      const beforeReview = await readWarningReviewState(page, project);
      const preflight = await readProject(page, project, '/api/engineering/preflight');
      const warnings = dialog.getByRole('region', {
        name: 'Preflight-Warnungen'
      });
      await expect(warnings.getByRole('listitem').first()).toBeVisible();
      const started = performance.now(),
        startedWall = Date.now();
      watchdog.remaining(started);
      const approvalResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/engineering/preflight/warnings/approve' && response.request().method() === 'POST', {
        timeout: 180000
      });
      await warnings.getByRole('button', {
        name: 'Warnungen freigeben und fortsetzen'
      }).click();
      const approved = await approvalResponse;
      const receipt = await approved.json();
      const afterReview = await readWarningReviewState(page, project);
      const proof = {
        before: beforeReview,
        after: afterReview,
        snapshotId: preflight.id,
        requestProject: approved.request().headers()['x-project-id'],
        submitted: approved.request().postDataJSON(),
        status: approved.status(),
        response: receipt,
        started,
        startedWall,
        finishedWall: Date.now()
      };
      const committedAt = performance.now();
      const committed = watchdog.commitWarningReview(proof, committedAt);
      await test.info().attach('verified-warning-review-proof', {
        body: JSON.stringify({
          proof,
          committedAt,
          committed
        }),
        contentType: 'application/json'
      });
      progressMilestones.get(test.info().testId).push({
        at: new Date().toISOString(),
        manualWarningApproval: committed.approvalIdentity,
        frontier: committed.frontier,
        project,
        execution: afterReview.context.agent_execution,
        approval: receipt.approval
      });
      await expect.poll(async () => {
        var _await$readProject$co;
        return (_await$readProject$co = (await readProject(page, project, '/api/engineering/workflow?view=summary')).context.agent_execution) === null || _await$readProject$co === void 0 ? void 0 : _await$readProject$co.updated_at;
      }, {
        timeout: expectedHardware.length > 100 ? 180000 : 60000
      }).not.toBe(execution.updated_at);
      continue;
    }
    if (['BLOCKED', 'FAILED', 'INCOMPLETE'].includes(execution === null || execution === void 0 ? void 0 : execution.state) && execution.recoverable !== true) {
      var _conversation$data, _proposal$data;
      const conversation = await readProject(page, project, '/api/engineering/agent/conversation');
      const id = (_conversation$data = conversation.data) === null || _conversation$data === void 0 ? void 0 : _conversation$data.active_proposal;
      const proposal = id ? await readProject(page, project, `/api/engineering/agent/proposals/${id}`) : null;
      await test.info().attach('wizard-blocker', {
        body: JSON.stringify({
          execution,
          proposal: proposal === null || proposal === void 0 || (_proposal$data = proposal.data) === null || _proposal$data === void 0 ? void 0 : _proposal$data.validation_result,
          visible: await dialog.innerText()
        }),
        contentType: 'application/json'
      });
      throw new Error(`Wizard ${execution.state} at ${execution.step}: ${execution.message}`);
    }
    if ((execution === null || execution === void 0 ? void 0 : execution.state) === 'READY_TO_CONTINUE' || (execution === null || execution === void 0 ? void 0 : execution.state) === 'BLOCKED' && execution.recoverable === true) {
      const button = dialog.getByRole('button', {
        name: 'Auftrag fortsetzen',
        exact: true
      });
      try {
        await button.click({
          timeout: 2000
        });
      } catch (error) {
        var _latest$context$agent;
        const latest = await readProject(page, project, '/api/engineering/workflow?view=summary');
        if (((_latest$context$agent = latest.context.agent_execution) === null || _latest$context$agent === void 0 ? void 0 : _latest$context$agent.updated_at) === execution.updated_at && (await button.evaluateAll(buttons => buttons.some(button => !button.disabled && button.getClientRects().length > 0 && getComputedStyle(button).visibility !== "hidden")))) throw error;
        continue;
      }
      await expect.poll(async () => {
        var _latest$context$agent2, _latest$context$agent3, _latest$statuses;
        const latest = await readProject(page, project, '/api/engineering/workflow?view=summary');
        return ((_latest$context$agent2 = latest.context.agent_execution) === null || _latest$context$agent2 === void 0 ? void 0 : _latest$context$agent2.updated_at) !== execution.updated_at || ((_latest$context$agent3 = latest.context.agent_execution) === null || _latest$context$agent3 === void 0 ? void 0 : _latest$context$agent3.state) === 'RUNNING' || ((_latest$statuses = latest.statuses) === null || _latest$statuses === void 0 ? void 0 : _latest$statuses[execution.step]) === 'IN_PROGRESS';
      }, {
        timeout: 60000
      }).toBe(true);
      continue;
    }
    const candidate = await readProject(page, project, `/api/engineering/agent/proposals/${proposalId}`);
    if (candidate.data.proposal_type === 'WIZARD_ENGINEERING_MODEL' && reviewCount === 0 && expectedHardware.length) {
      const hardware = candidate.data.changes.filter(change => change.object_type === 'HardwareNode').map(change => change.data.name);
      expect(hardware, 'The UI must preserve the hardware explicitly named in the user request.').toEqual(expect.arrayContaining(expectedHardware));
    }
    expect(reviewed.has(proposalId), 'The same proposal must not request review twice.').toBe(false);
    const reviewAction = await (beforeProposalReview === null || beforeProposalReview === void 0 ? void 0 : beforeProposalReview(proposalId, candidate.data.proposal_type));
    if (reviewAction === 'STOP_AFTER_REVIEW') {
      // Explicit targeted coverage: the selected pending proposal has been
      // exercised but is not applied and this is not nine-stage completion.
      return {
        runId,
        reviewed: [...reviewed],
        restartedJobId,
        reviewOnly: {
          proposalId,
          proposalType: candidate.data.proposal_type
        }
      };
    }
    const applyResponse = page.waitForResponse(response => response.url().includes(`/proposals/${proposalId}/approve-apply`) && response.request().method() === 'POST', {
      timeout: 180000
    });
    const approval = dialog.getByRole('button', {
      name: /^(Freigeben, übernehmen & fortfahren|Übernehmen & fortfahren)$/
    });
    await expect(approval).toBeEnabled({
      timeout: 60000
    });
    await approval.click();
    const applied = await applyResponse;
    if (!applied.ok()) throw new Error(`HTTP ${applied.status()}: ${(await applied.text()).slice(0, 4000)}`);
    expect((await applied.json()).data.status).toBe('APPLIED');
    reviewed.add(proposalId);
    reviewCount++;
    // A distinct, actually committed manual review starts the next automatic
    // section. Its write still has the separate unchanged 180-second limit.
    watchdog = new WizardProgressWatchdog(performance.now(), workflow);
    if (candidate.data.proposal_type === 'WIZARD_ENGINEERING_MODEL' && expectedSignals) {
      await verifySignalContracts(page, project, expectedSignals);
    }
    if (reviewCount === 1 && afterFirstModelApplied) {
      var _amended$context$agen;
      await afterFirstModelApplied();
      // This one test explicitly submits AMEND and waits for its receipt. Only
      // that deliberate action permits binding its new request revision.
      const amended = await readProject(page, project, '/api/engineering/workflow?view=summary');
      expect((_amended$context$agen = amended.context.agent_execution) === null || _amended$context$agen === void 0 ? void 0 : _amended$context$agen.run_id).toBe(runId);
      watchdog = new WizardProgressWatchdog(performance.now(), amended);
    }
    if (reviewCount === 1) await openWizard(page, project); // Durable reload after a real commit.
    if (restart && reviewCount === 2) {
      await restartApplication(page);
      await openWizard(page, project);
    }
    await expect.poll(async () => {
      var _current$context$agen;
      const current = await readProject(page, project, '/api/engineering/workflow?view=summary');
      return ((_current$context$agen = current.context.agent_execution) === null || _current$context$agen === void 0 ? void 0 : _current$context$agen.updated_at) !== execution.updated_at;
    }, {
      timeout: 60000
    }).toBe(true);
  }
  throw new Error('Wizard exceeded 16 review/continuation checkpoints.');
}
test('wizard refuses an unavailable catalog and recovers using the real registry @catalog-recovery', async ({
  page
}) => {
  const project = 'nis-e2e-catalog-recovery-' + randomUUID();
  await page.route('**/api/technologies', route => route.fulfill({
    status: 503,
    contentType: 'application/json',
    body: JSON.stringify({
      error: 'Der vollständige Technologiekatalog ist derzeit nicht erreichbar.'
    })
  }));
  const dialog = await openWizard(page, project);
  await expect(dialog.getByRole('alert')).toContainText('Technologiekatalog');
  await dialog.getByTitle('Projektname', {
    exact: true
  }).click();
  await dialog.locator('#engineering-project-name').fill('Catalog retry');
  await dialog.getByLabel('Projektbeschreibung', {
    exact: true
  }).fill('ein Aktor zum proportional schließen eines Ventil');
  await expect(dialog.locator('.eng-agent-questionnaire-head').getByRole('button')).toBeDisabled();
  expect((await readProject(page, project, '/api/simulations')).jobs).toHaveLength(0);
  await page.unroute('**/api/technologies');
  await dialog.getByRole('button', {
    name: 'Technologiekatalog erneut laden'
  }).click();
  await expect(dialog.getByRole('alert')).toHaveCount(0);
  await expect(dialog.locator('.eng-agent-questionnaire-head').getByRole('button')).toBeEnabled();
  const catalog = await (await page.request.get('/api/technologies')).json();
  expect(catalog.technology_count).toBe(125);
});
test('new small wizard traverses all nine stages and survives reload/restart @small', async ({
  page
}, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const project = 'nis-e2e-small-' + randomUUID();
  const dialog = await openWizard(page, project);
  await dialog.getByTitle('Projektname', {
    exact: true
  }).click();
  await dialog.locator('#engineering-project-name').fill('E2E small');
  await dialog.getByLabel('Projektbeschreibung', {
    exact: true
  }).fill('Erzeuge ein Automotive CAN-FD Netzwerk mit einem Gateway System, den ECUs Motorsteuerung und Anzeige, einem Sensor MotorTemperature und einem Aktor MotorValve. MotorTemperature wird von Motorsteuerung ausgewertet. Motorsteuerung steuert MotorValve. Controllerstatus bleibt bis zur Auswahl konkreter Empfänger und Signale intern. Prüfe und arbeite bis Data Science & Intelligence.\nCAN-FD: 500 kbit/s arbitration, 2 Mbit/s data\nCAN: 500 kbit/s');
  await dialog.getByLabel('Weitere Hinweise', {
    exact: true
  }).fill('- Aktor-Befehle: {"MotorValve":{"length_bits":1,"data_type":"boolean","factor":1,"unit":"code","min_value":0,"max_value":1,"semantic":{"semantic_type":"BOOLEAN"},"data":{"enum_values":{"CLOSE":0,"OPEN":1}}}}');
  await dialog.getByTitle('Geräteumfang', {
    exact: true
  }).click();
  for (const [label, value] of [['Gateways', '1'], ['Controller', '2'], ['Sensoren', '1'], ['Aktoren', '1']]) await dialog.getByLabel(`${label}: verbindliche Anzahl`, {
    exact: true
  }).fill(value);
  const startRequest = page.waitForRequest(request => {
    var _request$postDataJSON2;
    return request.url().endsWith('/api/agent/chat') && request.method() === 'POST' && ((_request$postDataJSON2 = request.postDataJSON()) === null || _request$postDataJSON2 === void 0 || (_request$postDataJSON2 = _request$postDataJSON2.wizard_command) === null || _request$postDataJSON2 === void 0 ? void 0 : _request$postDataJSON2.action) === 'START';
  });
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
  // Preserve a real pending model through parameter save and renewed review.
  await expect.poll(async () => {
    var _await$readProject$co2;
    return (_await$readProject$co2 = (await readProject(page, project, '/api/engineering/workflow?view=summary')).context.agent_execution) === null || _await$readProject$co2 === void 0 ? void 0 : _await$readProject$co2.state;
  }, {
    timeout: 180000
  }).toBe('REVIEW_REQUIRED');
  const pending = (await readProject(page, project, '/api/engineering/agent/conversation')).data.active_proposal;
  await page.goto(`/studio?mode=parameters&project=${project}&technology=can_fd&proposal=${pending}#parameter-findings`);
  await expect(page.getByRole('region', {
    name: 'Aktuelle Parameterbefunde'
  })).toContainText('noch nicht übernommenen Vorschlags');
  const common = page.locator('.parameter-group-common');
  await expect(common.locator('#arbitration_bitrate')).toHaveValue('500 kbit/s');
  await expect(common.locator('#data_bitrate')).toHaveValue('2 Mbit/s');
  await expect(page.locator('.parameter-details[open]')).toHaveCount(0);
  await repeatParameterReturn(page, project, pending, [{
    technology: 'can_fd',
    fields: {
      arbitration_bitrate: '500 kbit/s',
      data_bitrate: '1 Mbit/s',
      can_fd_data_prescaler: '2'
    },
    native: {
      arbitration_bitrate: 500000,
      data_bitrate: 1000000,
      can_fd_data_prescaler: 2
    },
    editFields: ['data_bitrate', 'can_fd_data_prescaler']
  }]);
  expect((await readProject(page, project, `/api/engineering/agent/proposals/${pending}?view=status`)).data.canonical_ids).toEqual([]);
  expect(await allObjects(page, project, 'hardware-nodes')).toHaveLength(0);
  const continuity = await completeThroughWizard(page, project, true, ['System', 'Motorsteuerung', 'Anzeige', 'MotorTemperature', 'MotorValve']);
  const artifacts = await verifyArtifacts(page, project, 5, undefined, {
    seed: 42,
    data_bitrate: 1000000,
    can_fd_data_prescaler: 2
  });
  expect(artifacts.assessment.observed_signal_count).toBeGreaterThanOrEqual(3);
  expect(artifacts.assessment.scope_coverage.transport_exclusions).toHaveLength(3);
  const finished = page.waitForResponse(response => response.url().includes(`/runs/${continuity.runId}/finish`) && response.request().method() === 'POST');
  await dialog.getByRole('button', {
    name: 'Fertig stellen',
    exact: true
  }).click();
  expect((await finished).ok()).toBe(true);
  await expect(dialog).not.toBeVisible();
  await openWizard(page, project);
  expect((await readProject(page, project, '/api/simulations')).jobs).toHaveLength(1);
  expect(errors).toEqual([]);
  await testInfo.attach('evidence', {
    body: JSON.stringify({
      project,
      ...continuity,
      ...artifacts
    }),
    contentType: 'application/json'
  });
});
for (const technology of ['I2C', 'Modbus RTU']) {
  test(`Raspberry Pi ${technology} project retains model and blocks inconsistent native parameters @nonautomotive`, async ({
    page
  }, testInfo) => {
    const project = 'nis-e2e-embedded-' + randomUUID();
    const dialog = await openWizard(page, project);
    await dialog.getByTitle('Projektname', {
      exact: true
    }).click();
    await dialog.locator('#engineering-project-name').fill('Temperaturregelung');
    await dialog.getByLabel('Projektbeschreibung', {
      exact: true
    }).fill(technology === 'I2C' ? '2 Aktoren für Ventile, 4 Sensoren für Temperaturen, und ein RaspberryPi' : `2 Aktoren für Ventile, 4 Sensoren für Temperaturen, und ein RaspberryPi. Embedded Systems. Alle Geräte kommunizieren über ${technology}. Prüfe und arbeite bis Data Science & Intelligence.`);
    await dialog.getByTitle('Netzarchitektur', {
      exact: true
    }).click();
    await dialog.getByRole('radio', {
      name: /Variante 0/
    }).check();
    await dialog.getByTitle('Geräteumfang', {
      exact: true
    }).click();
    if (technology === 'I2C') {
      await expect(dialog.getByRole('button', {
        name: 'Übernehmen',
        exact: true
      })).toBeDisabled();
      await dialog.getByLabel('RaspberryPi: Anschluss', {
        exact: true
      }).selectOption('I2C');
      await expect(dialog.getByLabel('Temperatursensor1: Anschluss', {
        exact: true
      })).toHaveValue('');
      await expect(dialog.getByRole('button', {
        name: 'Übernehmen',
        exact: true
      })).toBeDisabled();
      for (const name of ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4', 'Ventilaktor1', 'Ventilaktor2']) {
        await dialog.getByLabel(`${name}: Anschluss`, {
          exact: true
        }).selectOption('I2C');
      }
      await dialog.getByLabel('Sensor 1: Messgröße', {
        exact: true
      }).selectOption('speed');
      await expect(dialog.getByLabel('Temperatursensor1: Anschluss', {
        exact: true
      })).toHaveValue('I2C');
      await dialog.getByLabel('Sensor 1: Messgröße', {
        exact: true
      }).selectOption('temperature');
    }
    await expect(dialog.getByRole('button', {
      name: 'Übernehmen',
      exact: true
    })).toBeDisabled();
    await dialog.getByLabel('Ventilaktor1: Stellbefehl', {
      exact: true
    }).selectOption('OPEN_CLOSE');
    await expect(dialog.getByLabel('Ventilaktor2: Stellbefehl', {
      exact: true
    })).toHaveValue('');
    await expect(dialog.getByRole('button', {
      name: 'Übernehmen',
      exact: true
    })).toBeDisabled();
    await dialog.getByLabel('Ventilaktor2: Stellbefehl', {
      exact: true
    }).selectOption('OPEN_CLOSE');
    await dialog.getByRole('button', {
      name: 'Übernehmen',
      exact: true
    }).click();
    await expect(completeThroughWizard(page, project, true, ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4', 'Ventilaktor1', 'Ventilaktor2'], false, undefined, undefined, true)).rejects.toThrow(/Wizard BLOCKED at parameters:.*bestätigte Angaben/);
    const workflow = await readProject(page, project, '/api/engineering/workflow');
    const findings = workflow.context.agent_execution.blocking_findings;
    expect(findings.map(item => item.code)).toContain('TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH');
    expect(workflow.statuses.parameters).toBe('IN_PROGRESS');
    expect(workflow.artifact_checks.parameters.complete).toBe(false);
    const required = workflow.artifact_checks.parameters.required;
    expect(required.profile_values).toBe(false);
    const deviceSource = technology === 'I2C' ? 'i2c_device_source' : 'mr_device_source';
    // These scenarios remain blocked by real native dependencies, not by the
    // absence of a real device qualification or fabricated source identifier.
    expect(required).not.toHaveProperty(deviceSource, false);
    const nativeTechnology = technology === 'I2C' ? 'i2c' : 'modbus_rtu';
    expect(workflow.parameters.simulation_parameter_assumptions[nativeTechnology].values).not.toHaveProperty(deviceSource);
    expect(workflow.artifact_checks.parameters.profile_findings.some(finding => finding.code === 'TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH')).toBe(true);
    const evidenceReview = dialog.getByRole('region', {
      name: 'Blockierende Preflight-Befunde'
    });
    await expect(evidenceReview).toContainText(technology === 'I2C' ? 'i2c_pullup_ohms' : 'mr_pdu_bytes');
    await expect(evidenceReview.getByRole('link', {
      name: 'Betroffene Angaben bearbeiten'
    }).first()).toHaveAttribute('href', new RegExp(`mode=parameters.*project=${project}`));
    expect(workflow.statuses.simulation).toBe('EMPTY');
    if (technology === 'I2C') {
      expect(workflow.parameters.rate_review_proposals.i2c.status).toBe('REVIEW_REQUIRED');
      expect(workflow.parameters.parameter_provenance.bitrate.source).toBe('TECHNOLOGY_PROFILE_REVIEW_PROPOSAL');
    }
    const interfaces = await allObjects(page, project, 'hardware-interfaces');
    expect(interfaces.length).toBeGreaterThanOrEqual(7);
    expect(interfaces.every(item => !/automotive|can|lin/i.test(item.technology))).toBe(true);
    const hardware = await allObjects(page, project, 'hardware-nodes');
    expect(hardware.every(item => item.domain !== 'automotive')).toBe(true);
    if (technology === 'I2C') {
      const signals = await allObjects(page, project, 'signals');
      expect(signals.some(item => item.name === 'Temperatur_Temperatursensor1' && item.unit === 'degC')).toBe(true);
    }
    expect((await readProject(page, project, '/api/simulations')).jobs).toHaveLength(0);
    await testInfo.attach('nonautomotive-evidence', {
      body: JSON.stringify({
        project,
        technology,
        findings
      }),
      contentType: 'application/json'
    });
  });
}
async function startCapturedLargeWizard(page, project) {
  const runId = randomUUID();
  const original = await readFile(new URL('./fixtures/wizard-large-50-250-250.txt', import.meta.url), 'utf8');
  const metadata = JSON.parse(await readFile(new URL('./fixtures/wizard-large-50-250-250.json', import.meta.url), 'utf8'));
  const baseline = JSON.parse(await readFile(new URL('./fixtures/wizard-large-signal-contracts.json', import.meta.url), 'utf8'));
  const prompt = original.replace(/^- Lauf-ID:.*$/m, '- Lauf-ID: ' + runId);
  await reviewVirtualTransports(page, project, true);
  // Replay the captured, already confirmed input through the normal START API.
  // All proposal inspection, approval, continuation and reloads below use UI.
  const started = await page.request.post('/api/engineering/agent/chat', {
    headers: {
      'X-Project-ID': project
    },
    timeout: 240000,
    data: {
      prompt,
      wizard_command: {
        action: 'START',
        run_id: runId,
        operation_id: randomUUID(),
        target: 'data_science_intelligence',
        wizard_context: {
          ...metadata.wizard_context,
          project_id: project,
          run_id: runId
        }
      }
    }
  });
  if (!started.ok()) throw new Error(`HTTP ${started.status()}: ${(await started.text()).slice(0, 4000)}`);
  await openWizard(page, project);
  return {
    runId,
    metadata,
    baseline
  };
}
function largeParameterScenarios() {
  return [{
    technology: 'lin',
    fields: {
      lin_bitrate_bps: '19,2 kbit/s'
    },
    native: {
      lin_bitrate_bps: 19200
    }
  }, {
    technology: 'can_fd',
    fields: {
      arbitration_bitrate: '500 kbit/s',
      data_bitrate: '2 Mbit/s'
    },
    native: {
      arbitration_bitrate: 500000,
      data_bitrate: 2000000
    }
  }, {
    technology: 'ethernet',
    fields: {
      bitrate: '1 Gbit/s'
    },
    native: {
      bitrate: 1000000000
    },
    editFields: ['bitrate']
  }];
}
test('exact confirmed 50/250/250 request completes through real wizard review @large', async ({
  page
}, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const project = 'nis-e2e-large-' + randomUUID();
  const {
    runId,
    metadata,
    baseline
  } = await startCapturedLargeWizard(page, project);
  const parameterReturnReviews = [];
  const continuity = await completeThroughWizard(page, project, false, [], true, baseline.signals, undefined, false, async (proposalId, proposalType) => {
    if (!['WIZARD_ENGINEERING_MODEL', 'WIZARD_ROUTING', 'WIZARD_NETWORK_TOPOLOGY'].includes(proposalType)) return;
    // One full three-bus cycle remains integrated at every review stage.
    // Repeated three-seed coverage has its own real large cases below,
    // preserving the contractual 20-minute whole-workflow case limit.
    await repeatParameterReturn(page, project, proposalId, largeParameterScenarios(), [42]);
    parameterReturnReviews.push(proposalType);
  });
  expect(parameterReturnReviews).toEqual(['WIZARD_ENGINEERING_MODEL', 'WIZARD_ROUTING', 'WIZARD_NETWORK_TOPOLOGY']);
  expect(continuity.runId).toBe(runId);
  const hardware = await allObjects(page, project, 'hardware-nodes');
  expect(hardware.filter(item => item.device_type === 'SensorController')).toHaveLength(250);
  expect(hardware.filter(item => item.device_type === 'ActuatorController')).toHaveLength(250);
  expect(hardware.filter(item => item.device_type === 'ECU').length).toBeGreaterThanOrEqual(50);
  const artifacts = await verifyArtifacts(page, project, 1404, undefined, undefined, {
    lin: {
      bitrate: 19200
    },
    can_fd: {
      arbitration_bitrate: 500000,
      data_bitrate: 2000000
    },
    ethernet: {
      bitrate: 1000000000
    }
  });
  const excludedSignalIds = new Set(artifacts.assessment.scope_coverage.transport_exclusions.flatMap(item => item.signal_ids));
  expect(excludedSignalIds.size).toBe(235);
  expect(artifacts.assessment.observed_signal_count).toBe(1169);
  await verifySignalContracts(page, project, baseline.signals);
  expect(artifacts.job).toBe(continuity.restartedJobId);
  expect(errors).toEqual([]);
  await testInfo.attach('evidence', {
    body: JSON.stringify({
      project,
      fixture: metadata.request_sha256,
      ...continuity,
      ...artifacts
    }),
    contentType: 'application/json'
  });
});
for (const target of [{
  label: 'model',
  type: 'WIZARD_ENGINEERING_MODEL',
  step: 'engineering_model'
}, {
  label: 'routing',
  type: 'WIZARD_ROUTING',
  step: 'routing'
}, {
  label: 'topology',
  type: 'WIZARD_NETWORK_TOPOLOGY',
  step: 'network_editor'
}]) {
  test(`exact confirmed 50/250/250 ${target.label} parameter return review only @large-return`, async ({
    page
  }, testInfo) => {
    var _continuity$reviewOnl;
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const project = `nis-e2e-large-return-${target.label}-` + randomUUID();
    const {
      runId,
      metadata,
      baseline
    } = await startCapturedLargeWizard(page, project);
    const continuity = await completeThroughWizard(page, project, false, [], false, baseline.signals, undefined, false, async (proposalId, proposalType) => {
      if (proposalType !== target.type) return;
      await repeatParameterReturn(page, project, proposalId, largeParameterScenarios());
      return 'STOP_AFTER_REVIEW';
    });
    expect(continuity.runId).toBe(runId);
    expect((_continuity$reviewOnl = continuity.reviewOnly) === null || _continuity$reviewOnl === void 0 ? void 0 : _continuity$reviewOnl.proposalType).toBe(target.type);
    const workflow = await readProject(page, project, '/api/engineering/workflow?view=summary');
    expect(workflow.context.agent_execution).toMatchObject({
      run_id: runId,
      state: 'REVIEW_REQUIRED',
      step: target.step
    });
    expect(done.has(workflow.statuses.simulation)).toBe(false);
    const proposal = await readProject(page, project, `/api/engineering/agent/proposals/${continuity.reviewOnly.proposalId}?view=status`);
    expect(proposal.data.status).toBe('VALIDATED');
    expect(errors).toEqual([]);
    await testInfo.attach('review-only-evidence', {
      body: JSON.stringify({
        project,
        fixture: metadata.request_sha256,
        coverage: 'REVIEW_CONTINUITY_ONLY',
        cycles: 3,
        technologies: ['lin', 'can_fd', 'ethernet'],
        ...continuity
      }),
      contentType: 'application/json'
    });
  });
}
test('a real AMEND after model approval adds the requested sensor and reuses its networks @amend', async ({
  page
}, testInfo) => {
  const project = 'nis-e2e-amend-' + randomUUID();
  await reviewVirtualTransports(page, project);
  const runId = randomUUID();
  const graph = [{
    cluster_id: 'drive',
    network_id: 'can_fd',
    network_label: 'CAN-FD',
    bus_name: 'Drive',
    controllers: [{
      ecu: 'Motorsteuerung',
      sensors: [],
      actuators: []
    }],
    hmi_routes: [{
      source: 'Motorsteuerung',
      target: 'Anzeige'
    }, {
      source: 'Anzeige',
      target: 'Motorsteuerung'
    }, {
      source: 'System',
      target: 'Anzeige'
    }]
  }, {
    cluster_id: 'display',
    network_id: 'ethernet',
    network_label: 'Ethernet',
    bus_name: 'Display',
    controllers: [{
      ecu: 'Anzeige',
      sensors: [],
      actuators: []
    }]
  }];
  const prompt = `Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: ${runId}
- Industrie: Automotive
- Netzwerktechnologien: CAN-FD (can_fd); Ethernet (ethernet)
CAN-FD: 500 kbit/s arbitration, 2 Mbit/s data
CAN: 500 kbit/s
Ethernet: 100 Mbit/s
- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":0,"actuators":0}
- Systemcluster-Graph: ${JSON.stringify(graph)}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Motorsteuerung und Anzeige mit einem zentralen Gateway System verbinden.`;
  const started = await page.request.post('/api/engineering/agent/chat', {
    headers: {
      'X-Project-ID': project
    },
    timeout: 120000,
    data: {
      prompt,
      wizard_command: {
        action: 'START',
        run_id: runId,
        operation_id: randomUUID(),
        target: 'data_science_intelligence',
        wizard_context: {
          project_id: project,
          run_id: runId,
          project_name: 'E2E amendment',
          scope_ids: steps,
          mode: 'full',
          process_ids: ['defaults', 'review_gate', 'approve_after_allow'],
          task: 'Motorsteuerung und Anzeige an System'
        }
      }
    }
  });
  if (!started.ok()) throw new Error(`HTTP ${started.status()}: ${(await started.text()).slice(0, 4000)}`);
  await openWizard(page, project);
  let originalNetworks = [];
  const amend = async () => {
    originalNetworks = (await readProject(page, project, '/api/engineering/workflow')).parameters.networks.map(item => item.id).sort();
    expect(originalNetworks).toHaveLength(2);
    graph[0].controllers[0].sensors.push('MotorTemperature');
    const dialog = page.getByRole('dialog', {
      name: 'Engineering-Auftrag erstellen'
    });
    const expand = dialog.getByRole('button', {
      name: 'Ergänzen',
      exact: true
    });
    await expect(expand).toBeEnabled({
      timeout: 120000
    });
    await expand.click();
    const field = dialog.getByRole('region', {
      name: 'Engineering-Auftrag ergänzen',
      exact: true
    }).getByRole('textbox');
    await field.fill('Ergänze MotorTemperature als Sensor der Motorsteuerung. Die vollständige aktualisierte Freigabe lautet:\n' + '- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":1,"actuators":0}\n' + '- Systemcluster-Graph: ' + JSON.stringify(graph));
    await dialog.getByRole('button', {
      name: 'Ergänzung analysieren',
      exact: true
    }).click();
    await expect(field).not.toBeVisible({
      timeout: 120000
    });
  };
  const continuity = await completeThroughWizard(page, project, false, ['Motorsteuerung', 'Anzeige'], false, undefined, amend);
  const hardware = await allObjects(page, project, 'hardware-nodes');
  const owner = hardware.find(item => item.name === 'Motorsteuerung');
  const sensors = hardware.filter(item => item.name === 'MotorTemperature');
  expect(sensors).toHaveLength(1);
  expect(sensors[0].identity.system_owner_id).toBe(owner.id);
  const sensorNetwork = 'Drive-IO-motorsteuerung-can-fd-S01';
  const networks = (await readProject(page, project, '/api/engineering/workflow')).parameters.networks;
  expect(networks.map(item => item.id).sort()).toEqual([...originalNetworks, sensorNetwork].sort());
  expect(new Set(networks.map(item => item.name)).size).toBe(networks.length);
  const topology = (await readProject(page, project, '/api/engineering/workflow/network-view')).topology;
  const localEdge = topology.edges.find(edge => edge.physicalNetworkId === sensorNetwork);
  expect(localEdge).toBeTruthy();
  expect(localEdge.bus).toBe('can_fd');
  expect(Object.values(localEdge.routingMetadata)).toContainEqual(expect.objectContaining({
    source: sensors[0].id,
    target: owner.id,
    approvalState: 'APPROVED',
    protocol: 'CAN_FD'
  }));
  for (const [side, hardwareId] of [['source', sensors[0].id], ['target', owner.id]]) {
    const node = topology.nodes.find(item => item.id === localEdge[side]);
    expect(node.engineeringId).toBe(hardwareId);
    expect(node.ports).toContainEqual(expect.objectContaining({
      id: localEdge[side + 'Port'],
      bus: 'can_fd',
      physicalNetworkId: sensorNetwork
    }));
  }
  const artifacts = await verifyArtifacts(page, project, 1);
  await testInfo.attach('amendment-evidence', {
    body: JSON.stringify({
      project,
      ...continuity,
      ...artifacts
    }),
    contentType: 'application/json'
  });
});

// Real isolated UI -> persisted model boundary regression, not nine-stage completion proof.
test('reviewable functional TX/RX OFF survives request reload and canonical model adoption @txrx', async ({
  page
}, testInfo) => {
  const project = 'nis-e2e-txrx-' + randomUUID();
  const dialog = await openWizard(page, project);
  await dialog.getByTitle('Projektname', {
    exact: true
  }).click();
  await dialog.locator('#engineering-project-name').fill('TX RX functional partners');
  await dialog.getByLabel('Projektbeschreibung', {
    exact: true
  }).fill('Erzeuge ein Automotive CAN-FD Netzwerk mit einem Gateway System und den ECUs Motorsteuerung, Getriebesteuerung und Elektromotorsteuerung. Die berechneten Funktionsausgänge dienen der Antriebskoordination. Controllerstatus bleibt intern.\nCAN-FD: 500 kbit/s arbitration, 2 Mbit/s data');
  await dialog.getByTitle('Geräteumfang', {
    exact: true
  }).click();
  await dialog.getByRole('button', {
    name: 'Automotive / Vehicle übernehmen',
    exact: true
  }).click();
  for (const [label, value] of [['Gateways', '1'], ['Controller', '3'], ['Sensoren', '0'], ['Aktoren', '0']]) await dialog.getByLabel(`${label}: verbindliche Anzahl`, {
    exact: true
  }).fill(value);
  const txrx = dialog.locator('details').filter({
    has: page.locator('summary').filter({
      hasText: /^TX\/RX/
    })
  }).first();
  await expect(txrx).toBeVisible();
  await txrx.locator('summary').click();
  const selected = txrx.getByRole('switch', {
    name: 'MotorDrehmomentIst → Getriebesteuerung',
    exact: true
  });
  await expect(selected).toBeChecked();
  await selected.uncheck();
  const startRequest = page.waitForRequest(request => {
    var _request$postDataJSON3;
    return request.url().endsWith('/api/agent/chat') && request.method() === 'POST' && ((_request$postDataJSON3 = request.postDataJSON()) === null || _request$postDataJSON3 === void 0 || (_request$postDataJSON3 = _request$postDataJSON3.wizard_command) === null || _request$postDataJSON3 === void 0 ? void 0 : _request$postDataJSON3.action) === 'START';
  });
  for (let step = 0; step < 10; step++) {
    const button = dialog.locator('.eng-agent-questionnaire-head').getByRole('button');
    await expect(button).toBeEnabled();
    const label = await button.innerText();
    await button.click();
    if (label === 'Übernehmen' || label === 'Auftrag starten') break;
  }
  const context = (await startRequest).postDataJSON().wizard_command.wizard_context;
  const submitted = context.system_cluster_assignments.flatMap(cluster => {
    var _cluster$functional_r;
    return (_cluster$functional_r = cluster.functional_routes) !== null && _cluster$functional_r !== void 0 ? _cluster$functional_r : [];
  });
  const off = submitted.find(route => route.source === 'Motorsteuerung' && route.target === 'Getriebesteuerung');
  expect(off.signals).toEqual([]);
  expect(off.excluded_signals).toEqual(['MotorDrehmomentIst']);
  let proposal;
  await expect.poll(async () => {
    const conversation = await readProject(page, project, '/api/engineering/agent/conversation');
    if (!conversation.data.active_proposal) return false;
    proposal = (await readProject(page, project, `/api/engineering/agent/proposals/${conversation.data.active_proposal}`)).data;
    return proposal.proposal_type === 'WIZARD_ENGINEERING_MODEL';
  }, {
    timeout: 180000
  }).toBe(true);
  await page.reload();
  await openWizard(page, project);
  const findings = proposal.validation_result.findings.filter(item => item.code === 'CAPACITY_UNVERIFIED');
  if (findings.length) {
    const review = page.getByRole('region', {
      name: 'Prüfbefunde des Vorschlags'
    });
    await expect(review).toContainText(`${proposal.validation_result.findings.length} Prüfbefunde`);
    await expect(review.getByRole('link', {
      name: 'Technologieparameter bearbeiten und bestätigen'
    }).first()).toHaveAttribute('href', new RegExp(`project=${project}`));
    await review.locator('summary').first().click();
    await expect(review.getByRole('navigation', {
      name: 'Befunde durchblättern'
    }).first()).toBeVisible();
  }
  const apply = page.waitForResponse(response => response.url().includes(`/proposals/${proposal.proposal_id}/approve-apply`) && response.request().method() === 'POST');
  await page.getByRole('button', {
    name: 'Freigeben, übernehmen & fortfahren',
    exact: true
  }).click();
  expect((await apply).ok()).toBe(true);
  const nodes = await allObjects(page, project, 'hardware-nodes');
  const messages = await allObjects(page, project, 'messages');
  const signals = await allObjects(page, project, 'signals');
  const signal = signals.find(item => item.name === 'MotorDrehmomentIst');
  expect(signal).toBeTruthy();
  const message = messages.find(item => item.id === signal.message_id);
  const gearbox = nodes.find(item => item.name === 'Getriebesteuerung');
  const emotor = nodes.find(item => item.name === 'Elektromotorsteuerung');
  expect(message.configuration.communication_contract.scope).toBe('FUNCTION_OUTPUT');
  expect(message.configuration.communication_contract.consumer_refs).not.toContain(gearbox.id);
  expect(message.configuration.communication_contract.consumer_refs).toContain(emotor.id);
  await testInfo.attach('functional-txrx-evidence', {
    body: JSON.stringify({
      project,
      off,
      message
    }),
    contentType: 'application/json'
  });
});
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmVhZEZpbGUiLCJyYW5kb21VVUlEIiwiZXhlY0ZpbGVTeW5jIiwiV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyIsIldJWkFSRF9TVEVQUyIsIldJWkFSRF9ET05FIiwicmV2aWV3VmlydHVhbFRyYW5zcG9ydHMiLCJzdGVwcyIsImRvbmUiLCJ3cml0ZVRpbWluZ3MiLCJNYXAiLCJ3b3JrZmxvd1BhZ2VGYWlsdXJlcyIsIldlYWtNYXAiLCJwcm9ncmVzc01pbGVzdG9uZXMiLCJiZWZvcmVFYWNoIiwicGFnZSIsImluZm8iLCJyb3dzIiwic2V0IiwidGVzdElkIiwicmVxdWVzdHMiLCJvbiIsInJlcXVlc3QiLCJpbmNsdWRlcyIsIm1ldGhvZCIsInJvdyIsInVybCIsInN0YXJ0ZWQiLCJEYXRlIiwibm93IiwicHVzaCIsInJlc3BvbnNlIiwiZ2V0Iiwic3RhdHVzIiwiVVJMIiwicGF0aG5hbWUiLCJkdXJhdGlvbl9tcyIsIl9yZXF1ZXN0JGZhaWx1cmUiLCJmYWlsdXJlIiwiZXJyb3JUZXh0IiwiYWZ0ZXJFYWNoIiwiYXR0YWNoIiwiYm9keSIsIkpTT04iLCJzdHJpbmdpZnkiLCJjb250ZW50VHlwZSIsImRlbGV0ZSIsInRvRXF1YWwiLCJnZXRCeVJvbGUiLCJuYW1lIiwiZXhhY3QiLCJub3QiLCJ0b0JlVmlzaWJsZSIsImFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkiLCJnZXRCeVRleHQiLCJpc1Zpc2libGUiLCJ0b0JlIiwicmVhZFByb2plY3QiLCJwcm9qZWN0IiwicGF0aCIsInJlc3VsdCIsImhlYWRlcnMiLCJ0aW1lb3V0Iiwib2siLCJFcnJvciIsInRleHQiLCJzbGljZSIsImpzb24iLCJkaXNwb3NlIiwicmVhZFdhcm5pbmdSZXZpZXdTdGF0ZSIsIl92ZXJpZmllZCRjb250ZXh0JGFnZTIiLCJfdmVyaWZpZWQkY29udGV4dCRhZ2UzIiwiYXV0aG9yaXR5IiwicGFyYW1ldGVycyIsInZlcmlmaWVkIiwicHJvamVjdF9pZCIsImZpZWxkIiwiX3ZlcmlmaWVkJGNvbnRleHQkYWdlIiwiX2F1dGhvcml0eSRjb250ZXh0JGFnIiwiY29udGV4dCIsImFnZW50X2V4ZWN1dGlvbiIsInN0YXR1c2VzIiwicnVuX2lkIiwicmVxdWVzdF9yZXZpc2lvbiIsInByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsIiwib3BlbldpemFyZCIsImdvdG8iLCJ3YWl0VW50aWwiLCJkaWFsb2ciLCJzdGVwIiwibG9jYXRvciIsInN0ZXBXaWR0aCIsImV2YWx1YXRlIiwiZWxlbWVudCIsImdldEJvdW5kaW5nQ2xpZW50UmVjdCIsIndpZHRoIiwiY2FyZHMiLCJhbGwiLCJ0b0hhdmVMZW5ndGgiLCJjYXJkIiwidG9CZUdyZWF0ZXJUaGFuIiwiYWxsT2JqZWN0cyIsInJlc291cmNlIiwiaXRlbXMiLCJvZmZzZXQiLCJsZW5ndGgiLCJyZXN0YXJ0QXBwbGljYXRpb24iLCJjcmFzaCIsImNvbnRhaW5lciIsInByb2Nlc3MiLCJlbnYiLCJOSVNfRTJFX0FQUF9DT05UQUlORVIiLCJ0b01hdGNoIiwiZG9ja2VyIiwiTklTX1RFU1RfRE9DS0VSIiwibGFiZWwiLCJlbmNvZGluZyIsInRyaW0iLCJwb2xsIiwidmVyaWZ5U2lnbmFsQ29udHJhY3RzIiwiZXhwZWN0ZWQiLCJoYXJkd2FyZSIsImZ1bmN0aW9ucyIsIm1lc3NhZ2VzIiwic2lnbmFscyIsIlByb21pc2UiLCJtYXAiLCJub2RlcyIsIml0ZW0iLCJpZCIsImZ1bmN0aW9uc0J5SWQiLCJtZXNzYWdlc0J5SWQiLCJjb250cmFjdHMiLCJzaWduYWwiLCJfcmVmIiwiX3NpZ25hbCRkYXRhJGVudW1fdmFsIiwiX3NpZ25hbCRkYXRhIiwiX3NpZ25hbCRzZW1hbnRpYyRzZW1hIiwiX3NpZ25hbCRzZW1hbnRpYyIsIl9zaWduYWwkY29uZmlndXJhdGlvbiIsIl9zaWduYWwkY29uZmlndXJhdGlvbjIiLCJtZXNzYWdlIiwibWVzc2FnZV9pZCIsInRvQmVUcnV0aHkiLCJyZWZlcmVuY2UiLCJjb25maWd1cmF0aW9uIiwiY29tbXVuaWNhdGlvbl9jb250cmFjdCIsInByb2R1Y2VyX3JlZiIsImZuIiwib3duZXIiLCJoYXJkd2FyZV9ub2RlX2lkIiwicHJvZHVjZXIiLCJkZXZpY2VfdHlwZSIsImtleSIsImpvaW4iLCJ0b0JlVW5kZWZpbmVkIiwiT2JqZWN0IiwiZnJvbUVudHJpZXMiLCJfc2lnbmFsJGZpZWxkIiwiZW51bV92YWx1ZXMiLCJkYXRhIiwic2VtYW50aWNfdHlwZSIsInNlbWFudGljIiwiZ2VuZXJhdGlvbl9yb2xlIiwidmVyaWZ5QXJ0aWZhY3RzIiwibWluaW11bUNhbm9uaWNhbFNpZ25hbHMiLCJpbnRlcm5hbENvbnRyb2xsZXIiLCJleHBlY3RlZFBhcmFtZXRlcnMiLCJleHBlY3RlZE5hdGl2ZVJhdGVzIiwiX2Fzc2Vzc21lbnQkc2NvcGVfY292Iiwid29ya2Zsb3ciLCJqb2JMaXN0Iiwic25hcHNob3RzIiwia2V5cyIsInNvcnQiLCJoYXMiLCJqb2JzIiwic25hcHNob3QiLCJzaW11bGF0aW9ucyIsImZpbmQiLCJqb2JfaWQiLCJmdWxsIiwiZGF0YV9iaXRyYXRlIiwiY2FuX2ZkX2RhdGFfcHJlc2NhbGVyIiwicnVudGltZVBhcmFtZXRlcnMiLCJ0b01hdGNoT2JqZWN0IiwiY2FuRmROZXR3b3JrcyIsIm5ldHdvcmtzIiwiZmlsdGVyIiwibmV0d29yayIsInRlY2hub2xvZ3kiLCJyYXRlcyIsImVudHJpZXMiLCJhc3Nlc3NtZW50Iiwic2NvcGVfY292ZXJhZ2UiLCJzY29wZV9tb2RlIiwiY29tcGxldGUiLCJjb25mb3JtYW5jZSIsImZhaWxlZF9yb3V0ZV9jb3VudCIsInRvQmVHcmVhdGVyVGhhbk9yRXF1YWwiLCJleGNsdWRlZCIsInRyYW5zcG9ydF9leGNsdXNpb25zIiwicm91dGluZyIsImVuYWJsZWQiLCJjb250cmFjdCIsImNvbnN1bWVyX3JlZnMiLCJyZWFzb25fY29kZSIsInJvbGUiLCJjb250cm9sbGVyIiwic2NvcGUiLCJleGNsdWRlZFNpZ25hbHMiLCJTZXQiLCJmbGF0TWFwIiwic2lnbmFsX2lkcyIsIm9ic2VydmVkX3NpZ25hbF9jb3VudCIsInNpemUiLCJ0cmFjZSIsImNvdW50IiwiZXZlbnRzIiwic29tZSIsImpvYiIsInBhcmFtZXRlcl9wcm9vZiIsInNhdmVkIiwic2ltdWxhdGlvbl9yYXRlcyIsImJpdHJhdGUiLCJhcmJpdHJhdGlvbl9iaXRyYXRlIiwiaGFyZHdhcmVfZXZpZGVuY2UiLCJ1bmRlZmluZWQiLCJyZXBlYXRQYXJhbWV0ZXJSZXR1cm4iLCJwcm9wb3NhbElkIiwic2NlbmFyaW9zIiwic2VlZHMiLCJiZWZvcmUiLCJpZGVudGl0eSIsIm5vZGVJZHMiLCJzdGFydHMiLCJ0cmFja1N0YXJ0cyIsIl9yZXF1ZXN0JHBvc3REYXRhSlNPTiIsImVuZHNXaXRoIiwicG9zdERhdGFKU09OIiwid2l6YXJkX2NvbW1hbmQiLCJhY3Rpb24iLCJldmlkZW5jZSIsIndpemFyZCIsImNsaWNrIiwiY3ljbGUiLCJzZWVkIiwic2NlbmFyaW8iLCJfc2F2ZWQkcGFyYW1ldGVycyRzaW0iLCJlbmNvZGVVUklDb21wb25lbnQiLCJjb21tb24iLCJ2YWx1ZSIsImZpZWxkcyIsIl9zY2VuYXJpbyRlZGl0RmllbGRzIiwiaW5wdXQiLCJkZXRhaWxzIiwiZ2V0QXR0cmlidXRlIiwiZWRpdEZpZWxkcyIsImZpbGwiLCJ0b0hhdmVWYWx1ZSIsIlN0cmluZyIsInNjb3BlZCIsInRlY2hub2xvZ3lfcGFyYW1ldGVycyIsImFzc3VtZWQiLCJzaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucyIsInZhbHVlcyIsIm5hdGl2ZVZhbHVlcyIsIm5hdGl2ZSIsImNvbmZpcm1lZCIsImhhc093biIsInByb3ZlbmFuY2UiLCJzb3VyY2UiLCJ1c2VyVmFsdWVzIiwidmFsdWVfb3JpZ2luIiwidGVjaG5vbG9neV9kZWZhdWx0cyIsInN0YWxlIiwiY2Fub25pY2FsSWRzIiwiY2Fub25pY2FsX2lkcyIsInJlbG9hZCIsInJlc3VtZVJlc3RvcmUiLCJyZXN0b3JlUGF1c2UiLCJyZXNvbHZlIiwiZGVsYXlSZXN0b3JlIiwicm91dGUiLCJjb250aW51ZSIsImRlbGF5ZWQiLCJ0b0NvbnRhaW5UZXh0IiwidW5yb3V0ZUFsbCIsImJlaGF2aW9yIiwicmVzdG9yZWQiLCJzdGF0ZSIsImNvbnZlcnNhdGlvbiIsImFjdGl2ZV9wcm9wb3NhbCIsImZyZXNoIiwiYWZ0ZXIiLCJwcm9wb3NhbF9pZCIsInNhdmVkX3ZhbHVlcyIsImFzc3VtcHRpb25zIiwicmVzdG9yZWRfc3RhdHVzIiwib2ZmIiwiY29tcGxldGVUaHJvdWdoV2l6YXJkIiwicmVzdGFydCIsImV4cGVjdGVkSGFyZHdhcmUiLCJjcmFzaFNpbXVsYXRpb24iLCJleHBlY3RlZFNpZ25hbHMiLCJhZnRlckZpcnN0TW9kZWxBcHBsaWVkIiwic3RvcE9uRXZpZGVuY2VCbG9jayIsImJlZm9yZVByb3Bvc2FsUmV2aWV3IiwicmV2aWV3Q291bnQiLCJydW5JZCIsInJldmlld2VkIiwicmVzdGFydGVkSm9iSWQiLCJ3YXRjaGRvZyIsInBlcmZvcm1hbmNlIiwiY2hlY2twb2ludCIsIl93b3JrZmxvdyRjb250ZXh0JGFnZSIsIl93b3JrZmxvdyRjb250ZXh0JGFnZTIiLCJfZXhlY3V0aW9uJGJsb2NraW5nX2YiLCJfZXhlY3V0aW9uJG1lc3NhZ2UiLCJyZWFkeVZlcnNpb24iLCJyZWFkeVNpbmNlIiwiaXNDaGVja3BvaW50IiwicmVtYWluaW5nIiwicHJvZ3Jlc3MiLCJvYnNlcnZlIiwiYWR2YW5jZWQiLCJhdCIsInRvSVNPU3RyaW5nIiwiZnJvbnRpZXIiLCJjb21wbGV0ZWRUaHJvdWdoIiwiZXhlY3V0aW9uIiwidmFsaWRhdGlvbiIsInJ1bm5pbmciLCJldmVyeSIsIkJvb2xlYW4iLCJyZWNvdmVyYWJsZSIsInVwZGF0ZWRfYXQiLCJidXR0b24iLCJldmFsdWF0ZUFsbCIsImJ1dHRvbnMiLCJkaXNhYmxlZCIsImdldENsaWVudFJlY3RzIiwiZ2V0Q29tcHV0ZWRTdHlsZSIsInZpc2liaWxpdHkiLCJhdHRlbXB0Iiwid2FpdEZvclRpbWVvdXQiLCJNYXRoIiwibWluIiwiYmxvY2tpbmdfZmluZGluZ3MiLCJiZWZvcmVSZXZpZXciLCJwcmVmbGlnaHQiLCJ3YXJuaW5ncyIsImZpcnN0Iiwic3RhcnRlZFdhbGwiLCJhcHByb3ZhbFJlc3BvbnNlIiwid2FpdEZvclJlc3BvbnNlIiwiYXBwcm92ZWQiLCJyZWNlaXB0IiwiYWZ0ZXJSZXZpZXciLCJwcm9vZiIsInNuYXBzaG90SWQiLCJyZXF1ZXN0UHJvamVjdCIsInN1Ym1pdHRlZCIsImZpbmlzaGVkV2FsbCIsImNvbW1pdHRlZEF0IiwiY29tbWl0dGVkIiwiY29tbWl0V2FybmluZ1JldmlldyIsIm1hbnVhbFdhcm5pbmdBcHByb3ZhbCIsImFwcHJvdmFsSWRlbnRpdHkiLCJhcHByb3ZhbCIsIl9hd2FpdCRyZWFkUHJvamVjdCRjbyIsIl9jb252ZXJzYXRpb24kZGF0YSIsIl9wcm9wb3NhbCRkYXRhIiwicHJvcG9zYWwiLCJ2YWxpZGF0aW9uX3Jlc3VsdCIsInZpc2libGUiLCJpbm5lclRleHQiLCJlcnJvciIsIl9sYXRlc3QkY29udGV4dCRhZ2VudCIsImxhdGVzdCIsIl9sYXRlc3QkY29udGV4dCRhZ2VudDIiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQzIiwiX2xhdGVzdCRzdGF0dXNlcyIsImNhbmRpZGF0ZSIsInByb3Bvc2FsX3R5cGUiLCJjaGFuZ2VzIiwiY2hhbmdlIiwib2JqZWN0X3R5cGUiLCJhcnJheUNvbnRhaW5pbmciLCJyZXZpZXdBY3Rpb24iLCJyZXZpZXdPbmx5IiwicHJvcG9zYWxUeXBlIiwiYXBwbHlSZXNwb25zZSIsInRvQmVFbmFibGVkIiwiYXBwbGllZCIsImFkZCIsIl9hbWVuZGVkJGNvbnRleHQkYWdlbiIsImFtZW5kZWQiLCJfY3VycmVudCRjb250ZXh0JGFnZW4iLCJjdXJyZW50IiwiZnVsZmlsbCIsImdldEJ5VGl0bGUiLCJnZXRCeUxhYmVsIiwidG9CZURpc2FibGVkIiwidW5yb3V0ZSIsInRvSGF2ZUNvdW50IiwiY2F0YWxvZyIsInRlY2hub2xvZ3lfY291bnQiLCJ0ZXN0SW5mbyIsImVycm9ycyIsInN0YXJ0UmVxdWVzdCIsIndhaXRGb3JSZXF1ZXN0IiwiX3JlcXVlc3QkcG9zdERhdGFKU09OMiIsInN1Ym1pdCIsInJlcXVlc3RlZCIsIndpemFyZF9jb250ZXh0IiwidGVjaG5vbG9naWVzIiwiX2F3YWl0JHJlYWRQcm9qZWN0JGNvMiIsInBlbmRpbmciLCJjb250aW51aXR5IiwiYXJ0aWZhY3RzIiwiZmluaXNoZWQiLCJjaGVjayIsInNlbGVjdE9wdGlvbiIsInJlamVjdHMiLCJ0b1Rocm93IiwiZmluZGluZ3MiLCJjb2RlIiwidG9Db250YWluIiwiYXJ0aWZhY3RfY2hlY2tzIiwicmVxdWlyZWQiLCJwcm9maWxlX3ZhbHVlcyIsImRldmljZVNvdXJjZSIsInRvSGF2ZVByb3BlcnR5IiwibmF0aXZlVGVjaG5vbG9neSIsInByb2ZpbGVfZmluZGluZ3MiLCJmaW5kaW5nIiwiZXZpZGVuY2VSZXZpZXciLCJ0b0hhdmVBdHRyaWJ1dGUiLCJSZWdFeHAiLCJzaW11bGF0aW9uIiwicmF0ZV9yZXZpZXdfcHJvcG9zYWxzIiwiaTJjIiwicGFyYW1ldGVyX3Byb3ZlbmFuY2UiLCJpbnRlcmZhY2VzIiwiZG9tYWluIiwidW5pdCIsInN0YXJ0Q2FwdHVyZWRMYXJnZVdpemFyZCIsIm9yaWdpbmFsIiwiaW1wb3J0IiwibWV0YSIsIm1ldGFkYXRhIiwicGFyc2UiLCJiYXNlbGluZSIsInByb21wdCIsInJlcGxhY2UiLCJwb3N0Iiwib3BlcmF0aW9uX2lkIiwidGFyZ2V0IiwibGFyZ2VQYXJhbWV0ZXJTY2VuYXJpb3MiLCJsaW5fYml0cmF0ZV9icHMiLCJwYXJhbWV0ZXJSZXR1cm5SZXZpZXdzIiwibGluIiwiY2FuX2ZkIiwiZXRoZXJuZXQiLCJleGNsdWRlZFNpZ25hbElkcyIsImZpeHR1cmUiLCJyZXF1ZXN0X3NoYTI1NiIsInR5cGUiLCJfY29udGludWl0eSRyZXZpZXdPbmwiLCJjb3ZlcmFnZSIsImN5Y2xlcyIsImdyYXBoIiwiY2x1c3Rlcl9pZCIsIm5ldHdvcmtfaWQiLCJuZXR3b3JrX2xhYmVsIiwiYnVzX25hbWUiLCJjb250cm9sbGVycyIsImVjdSIsInNlbnNvcnMiLCJhY3R1YXRvcnMiLCJobWlfcm91dGVzIiwicHJvamVjdF9uYW1lIiwic2NvcGVfaWRzIiwibW9kZSIsInByb2Nlc3NfaWRzIiwidGFzayIsIm9yaWdpbmFsTmV0d29ya3MiLCJhbWVuZCIsImV4cGFuZCIsInN5c3RlbV9vd25lcl9pZCIsInNlbnNvck5ldHdvcmsiLCJ0b3BvbG9neSIsImxvY2FsRWRnZSIsImVkZ2VzIiwiZWRnZSIsInBoeXNpY2FsTmV0d29ya0lkIiwiYnVzIiwicm91dGluZ01ldGFkYXRhIiwidG9Db250YWluRXF1YWwiLCJvYmplY3RDb250YWluaW5nIiwiYXBwcm92YWxTdGF0ZSIsInByb3RvY29sIiwic2lkZSIsImhhcmR3YXJlSWQiLCJub2RlIiwiZW5naW5lZXJpbmdJZCIsInBvcnRzIiwidHhyeCIsImhhc1RleHQiLCJzZWxlY3RlZCIsInRvQmVDaGVja2VkIiwidW5jaGVjayIsIl9yZXF1ZXN0JHBvc3REYXRhSlNPTjMiLCJzeXN0ZW1fY2x1c3Rlcl9hc3NpZ25tZW50cyIsImNsdXN0ZXIiLCJfY2x1c3RlciRmdW5jdGlvbmFsX3IiLCJmdW5jdGlvbmFsX3JvdXRlcyIsImV4Y2x1ZGVkX3NpZ25hbHMiLCJyZXZpZXciLCJhcHBseSIsImdlYXJib3giLCJlbW90b3IiXSwic291cmNlcyI6WyJ3aXphcmQuc3BlYy50cyJdLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyB0ZXN0LCBleHBlY3QsIHR5cGUgUGFnZSB9IGZyb20gJ3BsYXl3cmlnaHQvdGVzdCc7XHJcbmltcG9ydCB7IHJlYWRGaWxlIH0gZnJvbSAnbm9kZTpmcy9wcm9taXNlcyc7XHJcbmltcG9ydCB7IHJhbmRvbVVVSUQgfSBmcm9tICdub2RlOmNyeXB0byc7XHJcbmltcG9ydCB7IGV4ZWNGaWxlU3luYyB9IGZyb20gJ25vZGU6Y2hpbGRfcHJvY2Vzcyc7XHJcbmltcG9ydCB7IFdpemFyZFByb2dyZXNzV2F0Y2hkb2csIFdJWkFSRF9TVEVQUywgV0laQVJEX0RPTkUgfSBmcm9tICcuL3N1cHBvcnQvd2l6YXJkLXByb2dyZXNzLXdhdGNoZG9nJztcclxuaW1wb3J0IHsgcmV2aWV3VmlydHVhbFRyYW5zcG9ydHMgfSBmcm9tICcuL3N1cHBvcnQvbmF0aXZlLXRyYW5zcG9ydC1maXh0dXJlcyc7XHJcblxyXG5jb25zdCBzdGVwcyA9IFdJWkFSRF9TVEVQUztcclxuY29uc3QgZG9uZSA9IFdJWkFSRF9ET05FO1xyXG50eXBlIFdyaXRlVGltaW5nID0geyB1cmw6IHN0cmluZzsgc3RhcnRlZDogbnVtYmVyOyBkdXJhdGlvbl9tcz86IG51bWJlcjsgc3RhdHVzPzogbnVtYmVyOyBmYWlsdXJlPzogc3RyaW5nIH07XHJcbmNvbnN0IHdyaXRlVGltaW5ncyA9IG5ldyBNYXA8c3RyaW5nLCBXcml0ZVRpbWluZ1tdPigpO1xyXG5jb25zdCB3b3JrZmxvd1BhZ2VGYWlsdXJlcyA9IG5ldyBXZWFrTWFwPFBhZ2UsIHN0cmluZ1tdPigpO1xyXG5jb25zdCBwcm9ncmVzc01pbGVzdG9uZXMgPSBuZXcgTWFwPHN0cmluZywgdW5rbm93bltdPigpO1xyXG5cclxudGVzdC5iZWZvcmVFYWNoKGFzeW5jICh7IHBhZ2UgfSwgaW5mbykgPT4ge1xyXG4gIGNvbnN0IHJvd3M6IFdyaXRlVGltaW5nW10gPSBbXTtcclxuICB3cml0ZVRpbWluZ3Muc2V0KGluZm8udGVzdElkLCByb3dzKTtcclxuICB3b3JrZmxvd1BhZ2VGYWlsdXJlcy5zZXQocGFnZSwgW10pO1xyXG4gIHByb2dyZXNzTWlsZXN0b25lcy5zZXQoaW5mby50ZXN0SWQsIFtdKTtcclxuICBjb25zdCByZXF1ZXN0cyA9IG5ldyBNYXA8b2JqZWN0LCBXcml0ZVRpbWluZz4oKTtcclxuICBwYWdlLm9uKCdyZXF1ZXN0JywgcmVxdWVzdCA9PiB7XHJcbiAgICBpZiAoIVsnUE9TVCcsICdQVVQnLCAnUEFUQ0gnLCAnREVMRVRFJ10uaW5jbHVkZXMocmVxdWVzdC5tZXRob2QoKSkpIHJldHVybjtcclxuICAgIGNvbnN0IHJvdyA9IHsgdXJsOiByZXF1ZXN0LnVybCgpLCBzdGFydGVkOiBEYXRlLm5vdygpIH07XHJcbiAgICByb3dzLnB1c2gocm93KTsgcmVxdWVzdHMuc2V0KHJlcXVlc3QsIHJvdyk7XHJcbiAgfSk7XHJcbiAgcGFnZS5vbigncmVzcG9uc2UnLCByZXNwb25zZSA9PiB7XHJcbiAgICBjb25zdCByb3cgPSByZXF1ZXN0cy5nZXQocmVzcG9uc2UucmVxdWVzdCgpKTtcclxuICAgIGlmIChyb3cpIHJvdy5zdGF0dXMgPSByZXNwb25zZS5zdGF0dXMoKTtcclxuICAgIGlmIChyZXNwb25zZS5zdGF0dXMoKSA9PT0gNDEzICYmIC9eXFwvYXBpXFwvZW5naW5lZXJpbmdcXC93b3JrZmxvdyg/OlxcL3wkKS8udGVzdChuZXcgVVJMKHJlc3BvbnNlLnVybCgpKS5wYXRobmFtZSkpIHtcclxuICAgICAgd29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpIS5wdXNoKGBIVFRQIDQxMzogJHtyZXNwb25zZS51cmwoKX1gKTtcclxuICAgIH1cclxuICB9KTtcclxuICBwYWdlLm9uKCdyZXF1ZXN0ZmluaXNoZWQnLCByZXF1ZXN0ID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXF1ZXN0KTtcclxuICAgIGlmIChyb3cpIHJvdy5kdXJhdGlvbl9tcyA9IERhdGUubm93KCkgLSByb3cuc3RhcnRlZDtcclxuICB9KTtcclxuICBwYWdlLm9uKCdyZXF1ZXN0ZmFpbGVkJywgcmVxdWVzdCA9PiB7XHJcbiAgICBjb25zdCByb3cgPSByZXF1ZXN0cy5nZXQocmVxdWVzdCk7XHJcbiAgICBpZiAocm93KSB7IHJvdy5kdXJhdGlvbl9tcyA9IERhdGUubm93KCkgLSByb3cuc3RhcnRlZDsgcm93LmZhaWx1cmUgPSByZXF1ZXN0LmZhaWx1cmUoKT8uZXJyb3JUZXh0OyB9XHJcbiAgfSk7XHJcbn0pO1xyXG5cclxudGVzdC5hZnRlckVhY2goYXN5bmMgKHsgcGFnZSB9LCBpbmZvKSA9PiB7XG4gIGF3YWl0IGluZm8uYXR0YWNoKCd3cml0ZS1yZXF1ZXN0LXRpbWluZ3MnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHdyaXRlVGltaW5ncy5nZXQoaW5mby50ZXN0SWQpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd29ya2Zsb3ctcHJvZ3Jlc3MtYm91bmRhcmllcycsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkocHJvZ3Jlc3NNaWxlc3RvbmVzLmdldChpbmZvLnRlc3RJZCkgfHwgW10pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gIGF3YWl0IGluZm8uYXR0YWNoKCd3b3JrZmxvdy1wYWdlLWZhaWx1cmVzJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh3b3JrZmxvd1BhZ2VGYWlsdXJlcy5nZXQocGFnZSkgfHwgW10pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gIHdyaXRlVGltaW5ncy5kZWxldGUoaW5mby50ZXN0SWQpO1xyXG4gIHByb2dyZXNzTWlsZXN0b25lcy5kZWxldGUoaW5mby50ZXN0SWQpO1xyXG4gIGV4cGVjdCh3b3JrZmxvd1BhZ2VGYWlsdXJlcy5nZXQocGFnZSksICdUaGUgdW5kZXJseWluZyBlbmdpbmVlcmluZyBwYWdlIG11c3QgcmVtYWluIHJlYWRhYmxlIHRocm91Z2hvdXQgcmVsb2FkIGFuZCByZWNvdmVyeS4nKS50b0VxdWFsKFtdKTtcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdoZWFkaW5nJywge25hbWU6ICdEaWUgQW5zaWNodCBrb25udGUgbmljaHQgZ2VsYWRlbiB3ZXJkZW4uJywgZXhhY3Q6IHRydWV9KSxcbiAgICAnQSBjcmFzaGVkIHBhcmFtZXRlciBvciBlbmdpbmVlcmluZyBwYWdlIG11c3QgbmV2ZXIgY291bnQgYXMgYSBzdWNjZXNzZnVsIHdpemFyZCBkZXRvdXIuJykubm90LnRvQmVWaXNpYmxlKCk7XG59KTtcclxuXHJcbmFzeW5jIGZ1bmN0aW9uIGFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkocGFnZTogUGFnZSkge1xuICBleHBlY3Qod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpLCAnQSB3b3JraW5nIHdpemFyZCBvdmVybGF5IG11c3Qgbm90IGNvbmNlYWwgYSB3b3JrZmxvdyBIVFRQIDQxMy4nKS50b0VxdWFsKFtdKTtcclxuICBleHBlY3QoYXdhaXQgcGFnZS5nZXRCeVRleHQoJ0VuZ2luZWVyaW5nLUFQSSBuaWNodCBlcnJlaWNoYmFyJywgeyBleGFjdDogdHJ1ZSB9KS5pc1Zpc2libGUoKSxcbiAgICAnVGhlIHVuZGVybHlpbmcgZW5naW5lZXJpbmcgcGFnZSBtdXN0IG5vdCBzaG93IGl0cyBBUEkgZXJyb3Igdmlldy4nKS50b0JlKGZhbHNlKTtcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdoZWFkaW5nJywge25hbWU6ICdEaWUgQW5zaWNodCBrb25udGUgbmljaHQgZ2VsYWRlbiB3ZXJkZW4uJywgZXhhY3Q6IHRydWV9KSkubm90LnRvQmVWaXNpYmxlKCk7XG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiByZWFkUHJvamVjdChwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIHBhdGg6IHN0cmluZykge1xyXG4gIGNvbnN0IHJlc3VsdCA9IGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQocGF0aCwgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0sIHRpbWVvdXQ6IDYwXzAwMCB9KTtcclxuICB0cnkge1xyXG4gICAgaWYgKCFyZXN1bHQub2soKSkgdGhyb3cgbmV3IEVycm9yKGAke3BhdGh9OiBIVFRQICR7cmVzdWx0LnN0YXR1cygpfSAkeyhhd2FpdCByZXN1bHQudGV4dCgpKS5zbGljZSgwLCA0MDAwKX1gKTtcclxuICAgIHJldHVybiBhd2FpdCByZXN1bHQuanNvbigpO1xyXG4gIH0gZmluYWxseSB7XHJcbiAgICAvLyBQbGF5d3JpZ2h0IG90aGVyd2lzZSByZXRhaW5zIGV2ZXJ5IHBvbGxlZCByZXNwb25zZSB1bnRpbCBjb250ZXh0IHRlYXJkb3duLlxyXG4gICAgLy8gS2VlcCB0aGUgcGFyc2VkIGV2aWRlbmNlLCByZWxlYXNlIGl0cyBkdXBsaWNhdGUgdHJhbnNwb3J0IGJvZHkgaW1tZWRpYXRlbHkuXHJcbiAgICBhd2FpdCByZXN1bHQuZGlzcG9zZSgpO1xyXG4gIH1cclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVhZFdhcm5pbmdSZXZpZXdTdGF0ZShwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcpIHtcclxuICBjb25zdCBhdXRob3JpdHkgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICBjb25zdCBwYXJhbWV0ZXJzID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycpO1xyXG4gIGNvbnN0IHZlcmlmaWVkID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgZXhwZWN0KHBhcmFtZXRlcnMucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcclxuICBleHBlY3QoYXV0aG9yaXR5LnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgZXhwZWN0KHZlcmlmaWVkLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBbJ3J1bl9pZCcsICdyZXF1ZXN0X3JldmlzaW9uJ10pXHJcbiAgICBleHBlY3QodmVyaWZpZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LltmaWVsZF0pLnRvQmUoYXV0aG9yaXR5LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5bZmllbGRdKTtcclxuICByZXR1cm4geyBwcm9qZWN0X2lkOiB2ZXJpZmllZC5wcm9qZWN0X2lkLCBzdGF0dXNlczogdmVyaWZpZWQuc3RhdHVzZXMsXHJcbiAgICBjb250ZXh0OiB7IGFnZW50X2V4ZWN1dGlvbjogeyBydW5faWQ6IHZlcmlmaWVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQsXHJcbiAgICAgIHJlcXVlc3RfcmV2aXNpb246IHZlcmlmaWVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5yZXF1ZXN0X3JldmlzaW9uIH0gfSxcclxuICAgIHBhcmFtZXRlcnM6IHsgcHJlZmxpZ2h0X3dhcm5pbmdfYXBwcm92YWw6IHBhcmFtZXRlcnMucGFyYW1ldGVycy5wcmVmbGlnaHRfd2FybmluZ19hcHByb3ZhbCB9IH07XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIG9wZW5XaXphcmQocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nKSB7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvL2VuZ2luZWVyaW5nP2Fzc2lzdGFudD1wcm9qZWN0JnByb2plY3Q9JHtwcm9qZWN0fWAsIHsgd2FpdFVudGlsOiAnbG9hZCcgfSk7XHJcbiAgY29uc3QgZGlhbG9nID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IGFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkocGFnZSk7XHJcbiAgcmV0dXJuIGRpYWxvZztcclxufVxyXG5cclxudGVzdCgncHJvamVjdCBuYW1pbmcgZm9ybSBjYXJkcyB1c2UgdGhlIGZ1bGwgd2l6YXJkIHdpZHRoIEBsYXlvdXQnLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcclxuICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsICduaXMtZTJlLXByb2plY3QtbmFtZS1sYXlvdXQtJyArIHJhbmRvbVVVSUQoKSk7XHJcbiAgY29uc3Qgc3RlcCA9IGRpYWxvZy5sb2NhdG9yKCdmaWVsZHNldC5hZ2VudC1wcm9qZWN0LW5hbWUtc3RlcCcpO1xyXG4gIGF3YWl0IGV4cGVjdChzdGVwKS50b0JlVmlzaWJsZSgpO1xyXG4gIGNvbnN0IHN0ZXBXaWR0aCA9IGF3YWl0IHN0ZXAuZXZhbHVhdGUoZWxlbWVudCA9PiBlbGVtZW50LmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpLndpZHRoKTtcclxuICBjb25zdCBjYXJkcyA9IGF3YWl0IHN0ZXAubG9jYXRvcignOnNjb3BlID4gbGFiZWwnKS5hbGwoKTtcclxuICBleHBlY3QoY2FyZHMpLnRvSGF2ZUxlbmd0aCg0KTtcclxuICBmb3IgKGNvbnN0IGNhcmQgb2YgY2FyZHMpIHtcclxuICAgIGNvbnN0IHdpZHRoID0gYXdhaXQgY2FyZC5ldmFsdWF0ZShlbGVtZW50ID0+IGVsZW1lbnQuZ2V0Qm91bmRpbmdDbGllbnRSZWN0KCkud2lkdGgpO1xyXG4gICAgZXhwZWN0KHdpZHRoKS50b0JlR3JlYXRlclRoYW4oc3RlcFdpZHRoICogMC44NSk7XHJcbiAgfVxyXG59KTtcclxuXHJcbmFzeW5jIGZ1bmN0aW9uIGFsbE9iamVjdHMocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCByZXNvdXJjZTogc3RyaW5nKSB7XHJcbiAgY29uc3QgaXRlbXM6IGFueVtdID0gW107XHJcbiAgZm9yIChsZXQgb2Zmc2V0ID0gMDsgOyBvZmZzZXQgKz0gNTAwKSB7XHJcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nLyR7cmVzb3VyY2V9P2xpbWl0PTUwMCZvZmZzZXQ9JHtvZmZzZXR9YCk7XHJcbiAgICBpdGVtcy5wdXNoKC4uLnJlc3BvbnNlLml0ZW1zKTtcclxuICAgIGlmIChyZXNwb25zZS5pdGVtcy5sZW5ndGggPCA1MDApIHJldHVybiBpdGVtcztcclxuICB9XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHJlc3RhcnRBcHBsaWNhdGlvbihwYWdlOiBQYWdlLCBjcmFzaCA9IGZhbHNlKSB7XHJcbiAgY29uc3QgY29udGFpbmVyID0gcHJvY2Vzcy5lbnYuTklTX0UyRV9BUFBfQ09OVEFJTkVSITtcclxuICBleHBlY3QoY29udGFpbmVyKS50b01hdGNoKC9ebmlzLWUyZS1hcHAtW2EtZjAtOV0rJC8pO1xyXG4gIGNvbnN0IGRvY2tlciA9IHByb2Nlc3MuZW52Lk5JU19URVNUX0RPQ0tFUiB8fCAnZG9ja2VyJztcclxuICBjb25zdCBsYWJlbCA9IGV4ZWNGaWxlU3luYyhkb2NrZXIsIFsnaW5zcGVjdCcsIGNvbnRhaW5lciwgJy0tZm9ybWF0JywgJ3t7aW5kZXggLkNvbmZpZy5MYWJlbHMgXCJuZXR3b3JraXMudGVzdFwifX0nXSwgeyBlbmNvZGluZzogJ3V0ZjgnIH0pLnRyaW0oKTtcclxuICBleHBlY3QobGFiZWwpLnRvQmUoJ2Rpc3Bvc2FibGUnKTtcclxuICBleGVjRmlsZVN5bmMoZG9ja2VyLCBbJ3Jlc3RhcnQnLCAuLi4oY3Jhc2ggPyBbJy10JywgJzAnXSA6IFtdKSwgY29udGFpbmVyXSwgeyB0aW1lb3V0OiA2MF8wMDAgfSk7XHJcbiAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgdHJ5IHsgcmV0dXJuIChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL3JlYWR5JywgeyB0aW1lb3V0OiAyMDAwIH0pKS5vaygpOyB9IGNhdGNoIHsgcmV0dXJuIGZhbHNlOyB9XHJcbiAgfSwgeyB0aW1lb3V0OiAxMjBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHZlcmlmeVNpZ25hbENvbnRyYWN0cyhwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIGV4cGVjdGVkOiBSZWNvcmQ8c3RyaW5nLCB1bmtub3duPikge1xyXG4gIGNvbnN0IFtoYXJkd2FyZSwgZnVuY3Rpb25zLCBtZXNzYWdlcywgc2lnbmFsc10gPSBhd2FpdCBQcm9taXNlLmFsbChcclxuICAgIFsnaGFyZHdhcmUtbm9kZXMnLCAnZnVuY3Rpb25zJywgJ21lc3NhZ2VzJywgJ3NpZ25hbHMnXS5tYXAocmVzb3VyY2UgPT4gYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCByZXNvdXJjZSkpKTtcclxuICBjb25zdCBub2RlcyA9IG5ldyBNYXAoaGFyZHdhcmUubWFwKGl0ZW0gPT4gW2l0ZW0uaWQsIGl0ZW1dKSk7XHJcbiAgY29uc3QgZnVuY3Rpb25zQnlJZCA9IG5ldyBNYXAoZnVuY3Rpb25zLm1hcChpdGVtID0+IFtpdGVtLmlkLCBpdGVtXSkpO1xyXG4gIGNvbnN0IG1lc3NhZ2VzQnlJZCA9IG5ldyBNYXAobWVzc2FnZXMubWFwKGl0ZW0gPT4gW2l0ZW0uaWQsIGl0ZW1dKSk7XHJcbiAgY29uc3QgY29udHJhY3RzOiBSZWNvcmQ8c3RyaW5nLCB1bmtub3duPiA9IHt9O1xyXG4gIGZvciAoY29uc3Qgc2lnbmFsIG9mIHNpZ25hbHMpIHtcclxuICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlc0J5SWQuZ2V0KHNpZ25hbC5tZXNzYWdlX2lkKTtcclxuICAgIGV4cGVjdChtZXNzYWdlKS50b0JlVHJ1dGh5KCk7XHJcbiAgICBjb25zdCByZWZlcmVuY2UgPSBtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdC5wcm9kdWNlcl9yZWY7XHJcbiAgICBjb25zdCBmbiA9IGZ1bmN0aW9uc0J5SWQuZ2V0KHJlZmVyZW5jZSk7XHJcbiAgICBjb25zdCBvd25lciA9IG5vZGVzLmdldChyZWZlcmVuY2UpIHx8IChmbiAmJiBub2Rlcy5nZXQoZm4uaGFyZHdhcmVfbm9kZV9pZCkpO1xyXG4gICAgY29uc3QgcHJvZHVjZXIgPSBvd25lcj8uZGV2aWNlX3R5cGUgPT09ICdHYXRld2F5JyA/ICckZ2F0ZXdheScgOiAobm9kZXMuZ2V0KHJlZmVyZW5jZSkgfHwgZm4pPy5uYW1lO1xyXG4gICAgZXhwZWN0KHByb2R1Y2VyKS50b0JlVHJ1dGh5KCk7XHJcbiAgICBjb25zdCBrZXkgPSBbcHJvZHVjZXIsIG1lc3NhZ2UubmFtZSwgc2lnbmFsLm5hbWVdLmpvaW4oJyA6OiAnKTtcclxuICAgIGV4cGVjdChjb250cmFjdHNba2V5XSwgJ1NlbWFudGljIHNpZ25hbCBpZGVudGl0eSBtdXN0IGJlIHVuaXF1ZTogJyArIGtleSkudG9CZVVuZGVmaW5lZCgpO1xyXG4gICAgY29udHJhY3RzW2tleV0gPSB7XHJcbiAgICAgIC4uLk9iamVjdC5mcm9tRW50cmllcyhbJ3N0YXJ0X2JpdCcsICdsZW5ndGhfYml0cycsICdkYXRhX3R5cGUnLCAnZmFjdG9yJywgJ29mZnNldF92YWx1ZScsXHJcbiAgICAgICAgJ3VuaXQnLCAnbWluX3ZhbHVlJywgJ21heF92YWx1ZScsICdieXRlX29yZGVyJ10ubWFwKGZpZWxkID0+IFtmaWVsZCwgc2lnbmFsW2ZpZWxkXSA/PyBudWxsXSkpLFxyXG4gICAgICBlbnVtX3ZhbHVlczogc2lnbmFsLmRhdGE/LmVudW1fdmFsdWVzID8/IG51bGwsXHJcbiAgICAgIHNlbWFudGljX3R5cGU6IHNpZ25hbC5zZW1hbnRpYz8uc2VtYW50aWNfdHlwZSA/PyBudWxsLFxyXG4gICAgICBnZW5lcmF0aW9uX3JvbGU6IHNpZ25hbC5jb25maWd1cmF0aW9uPy5nZW5lcmF0aW9uX3JvbGUgPz8gbnVsbCxcclxuICAgIH07XHJcbiAgfVxyXG4gIGV4cGVjdChjb250cmFjdHMsICdFdmVyeSBvcmlnaW5hbCBzaWduYWwgYW5kIGl0cyBleHBsaWNpdCBlbmNvZGluZyBtdXN0IHN1cnZpdmUgZ2VuZXJhdGlvbi4nKS50b0VxdWFsKGV4cGVjdGVkKTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gdmVyaWZ5QXJ0aWZhY3RzKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgbWluaW11bUNhbm9uaWNhbFNpZ25hbHM6IG51bWJlciwgaW50ZXJuYWxDb250cm9sbGVyPzogc3RyaW5nLFxuICBleHBlY3RlZFBhcmFtZXRlcnM/OiBSZWNvcmQ8c3RyaW5nLCB1bmtub3duPiwgZXhwZWN0ZWROYXRpdmVSYXRlcz86IFJlY29yZDxzdHJpbmcsIFJlY29yZDxzdHJpbmcsIG51bWJlcj4+KSB7XG4gIC8vIFRoZSBjb21wbGV0ZWQgbW9kZWwgaXMgc3RhYmxlOyB0aGVzZSBpbmRlcGVuZGVudCByZWFkcyBuZWVkIG5vIHNlcmlhbCB3YWl0cy5cclxuICBjb25zdCBbd29ya2Zsb3csIGpvYkxpc3QsIHNuYXBzaG90cywgc2lnbmFscywgbWVzc2FnZXNdID0gYXdhaXQgUHJvbWlzZS5hbGwoW1xyXG4gICAgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5JyksXHJcbiAgICByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpLFxyXG4gICAgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvc25hcHNob3RzJyksXHJcbiAgICBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyksXHJcbiAgICBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdtZXNzYWdlcycpLFxyXG4gIF0pO1xyXG4gIGV4cGVjdChPYmplY3Qua2V5cyh3b3JrZmxvdy5zdGF0dXNlcykuc29ydCgpKS50b0VxdWFsKFsuLi5zdGVwc10uc29ydCgpKTtcclxuICBmb3IgKGNvbnN0IHN0ZXAgb2Ygc3RlcHMpIGV4cGVjdChkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXSksIGAke3N0ZXB9OiAke3dvcmtmbG93LnN0YXR1c2VzW3N0ZXBdfWApLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBqb2JzID0gam9iTGlzdC5qb2JzO1xyXG4gIGV4cGVjdChqb2JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KGpvYnNbMF0uc3RhdHVzKS50b0JlKCdjb21wbGV0ZWQnKTtcclxuICBjb25zdCBzbmFwc2hvdCA9IHNuYXBzaG90cy5zaW11bGF0aW9ucy5maW5kKChpdGVtOiB7IGpvYl9pZDogc3RyaW5nIH0pID0+IGl0ZW0uam9iX2lkID09PSBqb2JzWzBdLmlkKTtcclxuICBleHBlY3Qoc25hcHNob3QpLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBmdWxsID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvc2ltdWxhdGlvbi1zbmFwc2hvdHMvJHtzbmFwc2hvdC5pZH1gKTtcclxuICBpZiAoZXhwZWN0ZWRQYXJhbWV0ZXJzKSB7XG4gICAgY29uc3QgeyBkYXRhX2JpdHJhdGUsIGNhbl9mZF9kYXRhX3ByZXNjYWxlciwgLi4ucnVudGltZVBhcmFtZXRlcnMgfSA9IGV4cGVjdGVkUGFyYW1ldGVycztcclxuICAgIGV4cGVjdChmdWxsLmNvbmZpZ3VyYXRpb24ucGFyYW1ldGVycykudG9NYXRjaE9iamVjdChydW50aW1lUGFyYW1ldGVycyk7XHJcbiAgICBjb25zdCBjYW5GZE5ldHdvcmtzID0gZnVsbC5jb25maWd1cmF0aW9uLm5ldHdvcmtzLmZpbHRlcigobmV0d29yazogYW55KSA9PiBuZXR3b3JrLnRlY2hub2xvZ3kgPT09ICdjYW5fZmQnKTtcclxuICAgIGV4cGVjdChjYW5GZE5ldHdvcmtzLmxlbmd0aCwgJ1RoZSBlZGl0ZWQgQ0FOLUZEIGNvbmZpZ3VyYXRpb24gbXVzdCByZWFjaCBhIHBoeXNpY2FsIHNpbXVsYXRpb24gbmV0d29yay4nKS50b0JlR3JlYXRlclRoYW4oMCk7XHJcbiAgICBmb3IgKGNvbnN0IG5ldHdvcmsgb2YgY2FuRmROZXR3b3JrcykgZXhwZWN0KG5ldHdvcmspLnRvTWF0Y2hPYmplY3QoeyBkYXRhX2JpdHJhdGUsIGNhbl9mZF9kYXRhX3ByZXNjYWxlciB9KTtcbiAgfVxuICBpZiAoZXhwZWN0ZWROYXRpdmVSYXRlcykge1xuICAgIGZvciAoY29uc3QgW3RlY2hub2xvZ3ksIHJhdGVzXSBvZiBPYmplY3QuZW50cmllcyhleHBlY3RlZE5hdGl2ZVJhdGVzKSkge1xuICAgICAgY29uc3QgbmV0d29ya3MgPSBmdWxsLmNvbmZpZ3VyYXRpb24ubmV0d29ya3MuZmlsdGVyKChuZXR3b3JrOiBhbnkpID0+IG5ldHdvcmsudGVjaG5vbG9neSA9PT0gdGVjaG5vbG9neSk7XG4gICAgICBleHBlY3QobmV0d29ya3MubGVuZ3RoLCBgU2F2ZWQgJHt0ZWNobm9sb2d5fSByYXRlcyBtdXN0IHJlYWNoIHRoZSBmcm96ZW4gc2ltdWxhdGlvbi5gKS50b0JlR3JlYXRlclRoYW4oMCk7XG4gICAgICBmb3IgKGNvbnN0IG5ldHdvcmsgb2YgbmV0d29ya3MpIGV4cGVjdChuZXR3b3JrKS50b01hdGNoT2JqZWN0KHJhdGVzKTtcbiAgICB9XG4gIH1cbiAgY29uc3QgYXNzZXNzbWVudCA9IGZ1bGwucmVzdWx0LmFzc2Vzc21lbnQ7XHJcbiAgZXhwZWN0KGFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2Uuc2NvcGVfbW9kZSkudG9CZSgnQUxMJyk7XHJcbiAgZXhwZWN0KGFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UuY29tcGxldGUpLnRvQmUodHJ1ZSk7XHJcbiAgZXhwZWN0KGFzc2Vzc21lbnQuY29uZm9ybWFuY2UpLnRvQmUoJ1BBU1MnKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5mYWlsZWRfcm91dGVfY291bnQpLnRvQmUoMCk7XHJcbiAgZXhwZWN0KHNpZ25hbHMubGVuZ3RoLCAnVGhlIGZ1bGwgY2Fub25pY2FsIHNpZ25hbCBpbnZlbnRvcnkgbXVzdCBzdXJ2aXZlIGdlbmVyYXRpb24uJykudG9CZUdyZWF0ZXJUaGFuT3JFcXVhbChtaW5pbXVtQ2Fub25pY2FsU2lnbmFscyk7XHJcbiAgY29uc3QgZXhjbHVkZWQgPSBhc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnRyYW5zcG9ydF9leGNsdXNpb25zID8/IFtdO1xyXG4gIGZvciAoY29uc3QgaXRlbSBvZiBleGNsdWRlZCkge1xyXG4gICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzLmZpbmQocm93ID0+IHJvdy5pZCA9PT0gaXRlbS5tZXNzYWdlX2lkKTtcclxuICAgIGV4cGVjdChtZXNzYWdlLCBgRXhjbHVkZWQgbWVzc2FnZSAke2l0ZW0ubWVzc2FnZV9pZH0gbXVzdCBleGlzdC5gKS50b0JlVHJ1dGh5KCk7XHJcbiAgICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLnJvdXRpbmcuZW5hYmxlZCkudG9CZShmYWxzZSk7XHJcbiAgICBjb25zdCBjb250cmFjdCA9IG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0O1xyXG4gICAgZXhwZWN0KGNvbnRyYWN0LmNvbnN1bWVyX3JlZnMpLnRvRXF1YWwoW10pO1xyXG4gICAgZXhwZWN0KGl0ZW0ucmVhc29uX2NvZGUpLnRvQmUoY29udHJhY3Qucm9sZSA9PT0gJ0lOVEVSTkFMX1NUQVRFJ1xyXG4gICAgICA/ICdJTlRFUk5BTF9TVEFURV9OT1RfUk9VVEVEJyA6ICdFWFBMSUNJVF9GVU5DVElPTl9PVVRQVVRfTk9UX1JPVVRFRCcpO1xyXG4gIH1cclxuICBpZiAoaW50ZXJuYWxDb250cm9sbGVyKSB7XHJcbiAgICBjb25zdCBub2RlcyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgICBjb25zdCBjb250cm9sbGVyID0gbm9kZXMuZmluZChpdGVtID0+IGl0ZW0ubmFtZSA9PT0gaW50ZXJuYWxDb250cm9sbGVyKTtcclxuICAgIGV4cGVjdChleGNsdWRlZC5sZW5ndGgpLnRvQmVHcmVhdGVyVGhhbigwKTtcclxuICAgIGZvciAoY29uc3QgaXRlbSBvZiBleGNsdWRlZCkge1xyXG4gICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXMuZmluZChyb3cgPT4gcm93LmlkID09PSBpdGVtLm1lc3NhZ2VfaWQpO1xyXG4gICAgICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QpLnRvTWF0Y2hPYmplY3QoeyByb2xlOiAnSU5URVJOQUxfU1RBVEUnLCBzY29wZTogJ0lOVEVSTkFMJywgcHJvZHVjZXJfcmVmOiBjb250cm9sbGVyLmlkLCBjb25zdW1lcl9yZWZzOiBbXSB9KTtcclxuICAgIH1cclxuICB9XHJcbiAgY29uc3QgZXhjbHVkZWRTaWduYWxzID0gbmV3IFNldChleGNsdWRlZC5mbGF0TWFwKChpdGVtOiB7IHNpZ25hbF9pZHM6IHN0cmluZ1tdIH0pID0+IGl0ZW0uc2lnbmFsX2lkcykpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50Lm9ic2VydmVkX3NpZ25hbF9jb3VudCwgJ0FMTCBtdXN0IG9ic2VydmUgZXZlcnkgY2Fub25pY2FsIHNpZ25hbCB3aXRoIGEgdHJhbnNwb3J0IG9ibGlnYXRpb24uJykudG9CZShzaWduYWxzLmxlbmd0aCAtIGV4Y2x1ZGVkU2lnbmFscy5zaXplKTtcclxuICBmb3IgKGNvbnN0IGtleSBvZiBbJ21pc3Npbmdfb2JzZXJ2ZWRfc2lnbmFsX2lkcycsICdtaXNzaW5nX29ic2VydmVkX3JvdXRlX2lkcycsICdtaXNzaW5nX29ic2VydmVkX25ldHdvcmtfaWRzJ10pIGV4cGVjdChhc3Nlc3NtZW50W2tleV0pLnRvRXF1YWwoW10pO1xyXG4gIGNvbnN0IHRyYWNlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvc2ltdWxhdGlvbnMvJHtqb2JzWzBdLmlkfS90cmFjZS13aW5kb3c/bGltaXQ9MTBgKTtcclxuICBleHBlY3QodHJhY2UuY291bnQpLnRvQmVHcmVhdGVyVGhhbigwKTtcclxuICBleHBlY3QodHJhY2UuZXZlbnRzLnNvbWUoKGl0ZW06IHsgc2lnbmFscz86IHVua25vd25bXSB9KSA9PiBpdGVtLnNpZ25hbHMgJiYgT2JqZWN0LmtleXMoaXRlbS5zaWduYWxzKS5sZW5ndGgpKS50b0JlVHJ1dGh5KCk7XHJcbiAgcmV0dXJuIHsgd29ya2Zsb3csIGpvYjogam9ic1swXS5pZCwgYXNzZXNzbWVudCwgcGFyYW1ldGVyX3Byb29mOiBleHBlY3RlZFBhcmFtZXRlcnMgPyB7XHJcbiAgICBzYXZlZDogZXhwZWN0ZWRQYXJhbWV0ZXJzLCBzaW11bGF0aW9uX3JhdGVzOiBmdWxsLmNvbmZpZ3VyYXRpb24ubmV0d29ya3MubWFwKChuZXR3b3JrOiBhbnkpID0+ICh7XHJcbiAgICAgIHRlY2hub2xvZ3k6IG5ldHdvcmsudGVjaG5vbG9neSwgYml0cmF0ZTogbmV0d29yay5iaXRyYXRlLFxyXG4gICAgICBhcmJpdHJhdGlvbl9iaXRyYXRlOiBuZXR3b3JrLmFyYml0cmF0aW9uX2JpdHJhdGUsIGRhdGFfYml0cmF0ZTogbmV0d29yay5kYXRhX2JpdHJhdGUsXHJcbiAgICAgIGhhcmR3YXJlX2V2aWRlbmNlOiBuZXR3b3JrLmhhcmR3YXJlX2V2aWRlbmNlLFxyXG4gICAgfSkpLFxyXG4gIH0gOiB1bmRlZmluZWQgfTtcclxufVxyXG5cclxudHlwZSBQYXJhbWV0ZXJSZXR1cm5TY2VuYXJpbyA9IHtcbiAgdGVjaG5vbG9neTogc3RyaW5nO1xuICBmaWVsZHM6IFJlY29yZDxzdHJpbmcsIHN0cmluZz47XG4gIG5hdGl2ZTogUmVjb3JkPHN0cmluZywgbnVtYmVyPjtcbiAgZWRpdEZpZWxkcz86IHN0cmluZ1tdO1xufTtcblxuLy8gRXhlcmNpc2UgdGhlIHVzZXIncyBkZXRvdXIsIGluY2x1ZGluZyByZXBlYXRlZCBzYXZlcyBpbiBhbiBleGlzdGluZyBydW4uXG4vLyBSZWFkcyBpbnNwZWN0IHJlYWwgcGVyc2lzdGVkIHN0YXRlOyB3cml0ZXMgYW5kIHJldHVybiBuYXZpZ2F0aW9uIHVzZSB0aGUgVUkuXG5hc3luYyBmdW5jdGlvbiByZXBlYXRQYXJhbWV0ZXJSZXR1cm4ocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBwcm9wb3NhbElkOiBzdHJpbmcsXG4gIHNjZW5hcmlvczogUGFyYW1ldGVyUmV0dXJuU2NlbmFyaW9bXSwgc2VlZHMgPSBbNDEsIDQzLCA0Ml0pIHtcclxuICBjb25zdCBiZWZvcmUgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcbiAgY29uc3QgaWRlbnRpdHkgPSBiZWZvcmUuY29udGV4dC5hZ2VudF9leGVjdXRpb247XG4gIGV4cGVjdChpZGVudGl0eS5ydW5faWQpLnRvQmVUcnV0aHkoKTtcbiAgY29uc3Qgbm9kZUlkcyA9IChhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpKS5tYXAoaXRlbSA9PiBpdGVtLmlkKS5zb3J0KCk7XG4gIGNvbnN0IHN0YXJ0czogdW5rbm93bltdID0gW107XG4gIGNvbnN0IHRyYWNrU3RhcnRzID0gKHJlcXVlc3Q6IGltcG9ydCgncGxheXdyaWdodC90ZXN0JykuUmVxdWVzdCkgPT4ge1xuICAgIGlmIChyZXF1ZXN0LnVybCgpLmVuZHNXaXRoKCcvYXBpL2FnZW50L2NoYXQnKSAmJiByZXF1ZXN0Lm1ldGhvZCgpID09PSAnUE9TVCdcbiAgICAgICYmIHJlcXVlc3QucG9zdERhdGFKU09OKCk/LndpemFyZF9jb21tYW5kPy5hY3Rpb24gPT09ICdTVEFSVCcpIHN0YXJ0cy5wdXNoKHJlcXVlc3QucG9zdERhdGFKU09OKCkpO1xuICB9O1xuICBjb25zdCBldmlkZW5jZTogdW5rbm93bltdID0gW107XG4gIHBhZ2Uub24oJ3JlcXVlc3QnLCB0cmFja1N0YXJ0cyk7XG4gIHRyeSB7XG4gICAgY29uc3Qgd2l6YXJkID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHtuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nfSk7XG4gICAgaWYgKGF3YWl0IHdpemFyZC5pc1Zpc2libGUoKSkge1xuICAgICAgLy8gQSBjYXB0dXJlZCBBUEkgU1RBUlQgZG9lcyBub3QgYWN0aXZhdGUgYSBicm93c2VyIHdpemFyZCBzZXNzaW9uLiBFbnRlclxuICAgICAgLy8gcGFyYW1ldGVycyB0aHJvdWdoIHRoZSBhY3R1YWwgd29ya2Zsb3cgY2FyZCwganVzdCBhcyBhIHVzZXIgZG9lcy5cbiAgICAgIGF3YWl0IHdpemFyZC5sb2NhdG9yKCcuYWdlbnQtd2l6YXJkLXByb2dyZXNzLWNhcmRbaHJlZio9XCJtb2RlPXBhcmFtZXRlcnNcIl0nKS5jbGljaygpO1xuICAgICAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7bmFtZTogJ1p1csO8Y2sgenVtIEF1ZnRyYWcnLCBleGFjdDogdHJ1ZX0pKS50b0JlVmlzaWJsZSgpO1xuICAgIH1cbiAgICBmb3IgKGNvbnN0IFtjeWNsZSwgc2VlZF0gb2Ygc2VlZHMuZW50cmllcygpKSB7XHJcbiAgICAgIGZvciAoY29uc3Qgc2NlbmFyaW8gb2Ygc2NlbmFyaW9zKSB7XG4gICAgICAgIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke2VuY29kZVVSSUNvbXBvbmVudChwcm9qZWN0KX0mdGVjaG5vbG9neT0ke3NjZW5hcmlvLnRlY2hub2xvZ3l9JnByb3Bvc2FsPSR7cHJvcG9zYWxJZH0jcGFyYW1ldGVyLWZpbmRpbmdzYCk7XG4gICAgICAgIGF3YWl0IGFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkocGFnZSk7XG4gICAgICAgIGNvbnN0IGNvbW1vbiA9IHBhZ2UubG9jYXRvcignLnBhcmFtZXRlci1ncm91cC1jb21tb24nKTtcbiAgICAgICAgZm9yIChjb25zdCBbZmllbGQsIHZhbHVlXSBvZiBPYmplY3QuZW50cmllcyhzY2VuYXJpby5maWVsZHMpKSB7XG4gICAgICAgICAgY29uc3QgaW5wdXQgPSBwYWdlLmxvY2F0b3IoYCMke2ZpZWxkfWApO1xuICAgICAgICAgIGNvbnN0IGRldGFpbHMgPSBpbnB1dC5sb2NhdG9yKCd4cGF0aD1hbmNlc3Rvcjo6ZGV0YWlsc1sxXScpO1xuICAgICAgICAgIGlmIChhd2FpdCBkZXRhaWxzLmNvdW50KCkgJiYgYXdhaXQgZGV0YWlscy5nZXRBdHRyaWJ1dGUoJ29wZW4nKSA9PT0gbnVsbClcbiAgICAgICAgICAgIGF3YWl0IGRldGFpbHMubG9jYXRvcignOnNjb3BlID4gc3VtbWFyeScpLmNsaWNrKCk7XG4gICAgICAgICAgaWYgKHNjZW5hcmlvLmVkaXRGaWVsZHM/LmluY2x1ZGVzKGZpZWxkKSkgYXdhaXQgaW5wdXQuZmlsbCh2YWx1ZSk7XG4gICAgICAgICAgZWxzZSBhd2FpdCBleHBlY3QoaW5wdXQpLnRvSGF2ZVZhbHVlKHZhbHVlKTtcbiAgICAgICAgfVxuICAgICAgICBhd2FpdCBjb21tb24ubG9jYXRvcignI3NlZWQnKS5maWxsKFN0cmluZyhzZWVkKSk7XG4gICAgICAgIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7bmFtZTogJ1BhcmFtZXRlciBzcGVpY2hlcm4g4oaSJywgZXhhY3Q6IHRydWV9KS5jbGljaygpO1xuICAgICAgICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ1RlY2hub2xvZ2llLSB1bmQgVGltaW5nLVBhcmFtZXRlciBnZXNwZWljaGVydC4nKSkudG9CZVZpc2libGUoKTtcbiAgICAgICAgY29uc3Qgc2F2ZWQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyk7XG4gICAgICAgIGV4cGVjdChzYXZlZC5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xuICAgICAgICBjb25zdCBzY29wZWQgPSBzYXZlZC5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfcGFyYW1ldGVyc1tzY2VuYXJpby50ZWNobm9sb2d5XTtcbiAgICAgICAgY29uc3QgYXNzdW1lZCA9IHNhdmVkLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnM/LltzY2VuYXJpby50ZWNobm9sb2d5XTtcbiAgICAgICAgZXhwZWN0KHNjb3BlZC52YWx1ZXMuc2VlZCkudG9CZShzZWVkKTtcbiAgICAgICAgY29uc3QgbmF0aXZlVmFsdWVzID0gey4uLmFzc3VtZWQ/LnZhbHVlcywgLi4uc2NvcGVkLnZhbHVlc307XG4gICAgICAgIGV4cGVjdChuYXRpdmVWYWx1ZXMpLnRvTWF0Y2hPYmplY3Qoc2NlbmFyaW8ubmF0aXZlKTtcbiAgICAgICAgZm9yIChjb25zdCBba2V5LCB2YWx1ZV0gb2YgT2JqZWN0LmVudHJpZXMoc2NlbmFyaW8ubmF0aXZlKSkge1xuICAgICAgICAgIGNvbnN0IGNvbmZpcm1lZCA9IE9iamVjdC5oYXNPd24oc2NvcGVkLnZhbHVlcywga2V5KTtcbiAgICAgICAgICBleHBlY3QoKGNvbmZpcm1lZCA/IHNjb3BlZCA6IGFzc3VtZWQpLnByb3ZlbmFuY2Vba2V5XSkudG9NYXRjaE9iamVjdChjb25maXJtZWRcbiAgICAgICAgICAgID8ge3NvdXJjZTogJ1VTRVJfQ09ORklSTUVEJywgc3RhdHVzOiAnQ09ORklSTUVEJywgdmFsdWV9XG4gICAgICAgICAgICA6IHtzb3VyY2U6ICdOSVNfU0lNVUxBVElPTl9BU1NVTVBUSU9OJywgc3RhdHVzOiAnQVNTVU1FRCcsIHRlY2hub2xvZ3k6IHNjZW5hcmlvLnRlY2hub2xvZ3ksIGhhcmR3YXJlX2V2aWRlbmNlOiBmYWxzZSwgdmFsdWV9KTtcbiAgICAgICAgfVxuICAgICAgICBjb25zdCB1c2VyVmFsdWVzID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycy91c2VyLWRlZmluZWQtdmFsdWVzJyk7XG4gICAgICAgIGV4cGVjdCh1c2VyVmFsdWVzLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XG4gICAgICAgIGV4cGVjdCh1c2VyVmFsdWVzLnZhbHVlX29yaWdpbikudG9CZSgnVVNFUl9ERUZJTkVEX1ZBTFVFJyk7XG4gICAgICAgIGV4cGVjdCh1c2VyVmFsdWVzLnBhcmFtZXRlcnMudGVjaG5vbG9neV9kZWZhdWx0cykudG9CZVVuZGVmaW5lZCgpO1xuICAgICAgICBleHBlY3QodXNlclZhbHVlcy5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfcGFyYW1ldGVyc1tzY2VuYXJpby50ZWNobm9sb2d5XSkudG9FcXVhbChzY29wZWQpO1xuICAgICAgICBjb25zdCBzdGFsZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3Byb3Bvc2FsSWR9P3ZpZXc9c3RhdHVzYCk7XG4gICAgICAgIGV4cGVjdChzdGFsZS5kYXRhLnN0YXR1cykudG9CZSgnT1VUREFURUQnKTtcbiAgICAgICAgY29uc3QgY2Fub25pY2FsSWRzID0gc3RhbGUuZGF0YS5jYW5vbmljYWxfaWRzO1xuICAgICAgICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xuICAgICAgICBhd2FpdCBleHBlY3QoY29tbW9uLmxvY2F0b3IoJyNzZWVkJykpLnRvSGF2ZVZhbHVlKFN0cmluZyhzZWVkKSk7XG4gICAgICAgIGZvciAoY29uc3QgW2ZpZWxkLCB2YWx1ZV0gb2YgT2JqZWN0LmVudHJpZXMoc2NlbmFyaW8uZmllbGRzKSkge1xuICAgICAgICAgIGNvbnN0IGlucHV0ID0gcGFnZS5sb2NhdG9yKGAjJHtmaWVsZH1gKTtcbiAgICAgICAgICBjb25zdCBkZXRhaWxzID0gaW5wdXQubG9jYXRvcigneHBhdGg9YW5jZXN0b3I6OmRldGFpbHNbMV0nKTtcbiAgICAgICAgICBpZiAoYXdhaXQgZGV0YWlscy5jb3VudCgpICYmIGF3YWl0IGRldGFpbHMuZ2V0QXR0cmlidXRlKCdvcGVuJykgPT09IG51bGwpXG4gICAgICAgICAgICBhd2FpdCBkZXRhaWxzLmxvY2F0b3IoJzpzY29wZSA+IHN1bW1hcnknKS5jbGljaygpO1xuICAgICAgICAgIGF3YWl0IGV4cGVjdChpbnB1dCkudG9IYXZlVmFsdWUodmFsdWUpO1xuICAgICAgICB9XG4gICAgICAgIC8vIEtlZXAgdGhlIGV4aXN0aW5nIGRlbGF5ZWQtcmVzdG9yZSByZWdyZXNzaW9uLCB1c2luZyByZWFsIHJlc3BvbnNlcy5cbiAgICAgICAgbGV0IHJlc3VtZVJlc3RvcmUhOiAoKSA9PiB2b2lkO1xuICAgICAgICBjb25zdCByZXN0b3JlUGF1c2UgPSBuZXcgUHJvbWlzZTx2b2lkPihyZXNvbHZlID0+IHsgcmVzdW1lUmVzdG9yZSA9IHJlc29sdmU7IH0pO1xuICAgICAgICBjb25zdCBkZWxheVJlc3RvcmUgPSBhc3luYyAocm91dGU6IGltcG9ydCgncGxheXdyaWdodC90ZXN0JykuUm91dGUpID0+IHtcbiAgICAgICAgICBhd2FpdCByZXN0b3JlUGF1c2U7IGF3YWl0IHJvdXRlLmNvbnRpbnVlKCk7XG4gICAgICAgIH07XG4gICAgICAgIGNvbnN0IGRlbGF5ZWQgPSBjeWNsZSA9PT0gMCAmJiBzY2VuYXJpbyA9PT0gc2NlbmFyaW9zWzBdO1xuICAgICAgICBpZiAoZGVsYXllZCkgYXdhaXQgcGFnZS5yb3V0ZSgnKiovYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScsIGRlbGF5UmVzdG9yZSk7XG4gICAgICAgIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7bmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJ30pO1xuICAgICAgICB0cnkge1xuICAgICAgICAgIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7bmFtZTogJ1p1csO8Y2sgenVtIEF1ZnRyYWcnLCBleGFjdDogdHJ1ZX0pLmNsaWNrKCk7XG4gICAgICAgICAgaWYgKGRlbGF5ZWQpIHtcbiAgICAgICAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7bmFtZTogJ0dlc3BlaWNoZXJ0ZW4gQXVmdHJhZyB3aWVkZXJoZXJzdGVsbGVuJ30pKS50b0JlVmlzaWJsZSgpO1xuICAgICAgICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZykubm90LnRvQ29udGFpblRleHQoJ1Byb2pla3RuYW1lOiBTY2hyaXR0IDEnKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZmluYWxseSB7XG4gICAgICAgICAgcmVzdW1lUmVzdG9yZSgpO1xuICAgICAgICAgIGlmIChkZWxheWVkKSBhd2FpdCBwYWdlLnVucm91dGVBbGwoe2JlaGF2aW9yOiAnd2FpdCd9KTtcbiAgICAgICAgfVxuICAgICAgICAvLyBNYXRjaCB0aGUgZXhpc3RpbmcgcHJvcG9zYWwtcmV2aWV3IHJlYWRpbmVzcyBidWRnZXQgYmVsb3cuIFRoZSBuZXdcbiAgICAgICAgLy8gcmV0dXJuIGFzc2VydGlvbiBtdXN0IG5vdCBpbXBvc2UgYSBzaG9ydGVyIGxpbWl0IG9uIHRoZSBsYXJnZSBtb2RlbC5cbiAgICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHtuYW1lOiAnRW5naW5lZXJpbmctVm9yc2NobGFnJ30pKVxuICAgICAgICAgIC50b0NvbnRhaW5UZXh0KCdHZXByw7xmdCDCtyBGcmVpZ2FiZSBvZmZlbicsIHt0aW1lb3V0OiA2MF8wMDB9KTtcbiAgICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZykudG9Db250YWluVGV4dCgnU3RhdHVzw7xiZXJzaWNodDogU2Nocml0dCA1IHZvbiA1Jyk7XG4gICAgICAgIGNvbnN0IHJlc3RvcmVkID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XG4gICAgICAgIGV4cGVjdChyZXN0b3JlZC5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xuICAgICAgICBleHBlY3QocmVzdG9yZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24ucnVuX2lkKS50b0JlKGlkZW50aXR5LnJ1bl9pZCk7XG4gICAgICAgIGV4cGVjdChyZXN0b3JlZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbi5yZXF1ZXN0X3JldmlzaW9uKS50b0JlKGlkZW50aXR5LnJlcXVlc3RfcmV2aXNpb24pO1xuICAgICAgICBleHBlY3QocmVzdG9yZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24uc3RhdGUpLnRvQmUoJ1JFVklFV19SRVFVSVJFRCcpO1xuICAgICAgICBleHBlY3QocmVzdG9yZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24uc3RlcCkudG9CZShpZGVudGl0eS5zdGVwKTtcbiAgICAgICAgZm9yIChjb25zdCBzdGVwIG9mIHN0ZXBzKSBpZiAoZG9uZS5oYXMoYmVmb3JlLnN0YXR1c2VzW3N0ZXBdKSlcbiAgICAgICAgICBleHBlY3QoZG9uZS5oYXMocmVzdG9yZWQuc3RhdHVzZXNbc3RlcF0pLCBgUmV0dXJuaW5nIG11c3QgcHJlc2VydmUgY29tcGxldGVkIHN0YWdlICR7c3RlcH0uYCkudG9CZSh0cnVlKTtcbiAgICAgICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XG4gICAgICAgIGV4cGVjdChjb252ZXJzYXRpb24uZGF0YS5hY3RpdmVfcHJvcG9zYWwpLnRvQmUocHJvcG9zYWxJZCk7XG4gICAgICAgIGNvbnN0IGZyZXNoID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7cHJvcG9zYWxJZH0/dmlldz1zdGF0dXNgKTtcbiAgICAgICAgZXhwZWN0KGZyZXNoLmRhdGEuc3RhdHVzKS50b0JlKCdWQUxJREFURUQnKTtcbiAgICAgICAgZXhwZWN0KGZyZXNoLmRhdGEuY2Fub25pY2FsX2lkcykudG9FcXVhbChjYW5vbmljYWxJZHMpO1xuICAgICAgICBleHBlY3QoKGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJykpLm1hcChpdGVtID0+IGl0ZW0uaWQpLnNvcnQoKSkudG9FcXVhbChub2RlSWRzKTtcbiAgICAgICAgY29uc3QgYWZ0ZXIgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyk7XG4gICAgICAgIGV4cGVjdChhZnRlci5wYXJhbWV0ZXJzKS50b0VxdWFsKHNhdmVkLnBhcmFtZXRlcnMpO1xuICAgICAgICBleHBlY3Qoc3RhcnRzLCAnUmV0dXJuaW5nIGZyb20gcGFyYW1ldGVycyBtdXN0IG5ldmVyIHJlc3RhcnQgdGhpcyBydW4uJykudG9FcXVhbChbXSk7XG4gICAgICAgIGV2aWRlbmNlLnB1c2goe2N5Y2xlOiBjeWNsZSArIDEsIHRlY2hub2xvZ3k6IHNjZW5hcmlvLnRlY2hub2xvZ3ksIHNlZWQsIHJ1bl9pZDogaWRlbnRpdHkucnVuX2lkLFxuICAgICAgICAgIHByb3Bvc2FsX2lkOiBwcm9wb3NhbElkLCBzYXZlZF92YWx1ZXM6IHNjb3BlZCwgYXNzdW1wdGlvbnM6IGFzc3VtZWQsXG4gICAgICAgICAgcmVzdG9yZWRfc3RhdHVzOiBmcmVzaC5kYXRhLnN0YXR1cywgY2Fub25pY2FsX2lkczogY2Fub25pY2FsSWRzfSk7XG4gICAgICB9XG4gICAgfVxuICB9IGZpbmFsbHkge1xuICAgIHBhZ2Uub2ZmKCdyZXF1ZXN0JywgdHJhY2tTdGFydHMpO1xuICAgIGF3YWl0IHRlc3QuaW5mbygpLmF0dGFjaCgncmVwZWF0ZWQtcGFyYW1ldGVyLXJldHVybicsIHtib2R5OiBKU09OLnN0cmluZ2lmeShldmlkZW5jZSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbid9KTtcbiAgfVxufVxuXG5hc3luYyBmdW5jdGlvbiBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCByZXN0YXJ0OiBib29sZWFuLCBleHBlY3RlZEhhcmR3YXJlOiBzdHJpbmdbXSA9IFtdLCBjcmFzaFNpbXVsYXRpb24gPSBmYWxzZSxcbiAgZXhwZWN0ZWRTaWduYWxzPzogUmVjb3JkPHN0cmluZywgdW5rbm93bj4sIGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQ/OiAoKSA9PiBQcm9taXNlPHZvaWQ+LCBzdG9wT25FdmlkZW5jZUJsb2NrID0gZmFsc2UsXG4gIGJlZm9yZVByb3Bvc2FsUmV2aWV3PzogKHByb3Bvc2FsSWQ6IHN0cmluZywgcHJvcG9zYWxUeXBlOiBzdHJpbmcpID0+IFByb21pc2U8dm9pZCB8ICdTVE9QX0FGVEVSX1JFVklFVyc+KSB7XHJcbiAgbGV0IHJldmlld0NvdW50ID0gMDtcclxuICBsZXQgcnVuSWQ6IHN0cmluZyB8IHVuZGVmaW5lZDtcclxuICBjb25zdCByZXZpZXdlZCA9IG5ldyBTZXQ8c3RyaW5nPigpO1xyXG4gIGxldCByZXN0YXJ0ZWRKb2JJZDogc3RyaW5nIHwgdW5kZWZpbmVkO1xyXG4gIGxldCB3YXRjaGRvZyA9IG5ldyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nKHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICBmb3IgKGxldCBjaGVja3BvaW50ID0gMDsgY2hlY2twb2ludCA8IDE2OyBjaGVja3BvaW50KyspIHtcclxuICAgIGxldCB3b3JrZmxvdzogYW55O1xyXG4gICAgbGV0IHByb3Bvc2FsSWQgPSAnJztcclxuICAgIGxldCByZWFkeVZlcnNpb24gPSAnJztcclxuICAgIGxldCByZWFkeVNpbmNlID0gMDtcclxuICAgIGNvbnN0IGlzQ2hlY2twb2ludCA9IGFzeW5jICgpID0+IHtcclxuICAgICAgd2F0Y2hkb2cucmVtYWluaW5nKHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICAgICAgYXdhaXQgYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeShwYWdlKTtcclxuICAgICAgd29ya2Zsb3cgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgY29uc3QgcHJvZ3Jlc3MgPSB3YXRjaGRvZy5vYnNlcnZlKHdvcmtmbG93LCBwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgICAgIGlmIChwcm9ncmVzcy5hZHZhbmNlZCkgcHJvZ3Jlc3NNaWxlc3RvbmVzLmdldCh0ZXN0LmluZm8oKS50ZXN0SWQpIS5wdXNoKHtcclxuICAgICAgICBhdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLCBmcm9udGllcjogcHJvZ3Jlc3MuZnJvbnRpZXIsXHJcbiAgICAgICAgY29tcGxldGVkVGhyb3VnaDogc3RlcHNbcHJvZ3Jlc3MuZnJvbnRpZXIgLSAxXSxcclxuICAgICAgICBwcm9qZWN0OiB3b3JrZmxvdy5wcm9qZWN0X2lkLCBleGVjdXRpb246IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLFxyXG4gICAgICB9KTtcclxuICAgICAgaWYgKGNyYXNoU2ltdWxhdGlvbiAmJiAhcmVzdGFydGVkSm9iSWQgJiYgZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXMudmFsaWRhdGlvbikpIHtcclxuICAgICAgICBjb25zdCBqb2JzID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnM7XHJcbiAgICAgICAgY29uc3QgcnVubmluZyA9IGpvYnMuZmluZCgoam9iOiB7IHN0YXR1czogc3RyaW5nIH0pID0+IGpvYi5zdGF0dXMgPT09ICdydW5uaW5nJyk7XHJcbiAgICAgICAgaWYgKHJ1bm5pbmcpIHtcclxuICAgICAgICAgIHJlc3RhcnRlZEpvYklkID0gcnVubmluZy5pZDtcclxuICAgICAgICAgIGF3YWl0IHJlc3RhcnRBcHBsaWNhdGlvbihwYWdlLCB0cnVlKTtcclxuICAgICAgICAgIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgICAgICAgICByZXR1cm4gZmFsc2U7XHJcbiAgICAgICAgfVxyXG4gICAgICB9XHJcbiAgICAgIGlmIChzdGVwcy5ldmVyeShzdGVwID0+IGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzW3N0ZXBdKSkpIHJldHVybiB0cnVlO1xyXG4gICAgICBjb25zdCBleGVjdXRpb24gPSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbjtcclxuICAgICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdSRVZJRVdfUkVRVUlSRUQnKSB7XHJcbiAgICAgICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XHJcbiAgICAgICAgcHJvcG9zYWxJZCA9IGNvbnZlcnNhdGlvbi5kYXRhLmFjdGl2ZV9wcm9wb3NhbDtcclxuICAgICAgICAvLyBQb2xsaW5nIG1heSBzdGlsbCBleHBvc2UgdGhlIGp1c3QtYXBwbGllZCByZXZpZXcgd2hpbGUgdGhlIFVJIHN0YXJ0c1xyXG4gICAgICAgIC8vIGl0cyBkdXJhYmxlIGNvbnRpbnVhdGlvbi4gV2FpdCBmb3IgYSBkaXN0aW5jdCBwcm9wb3NhbCwgbm90IGl0cyBsYWJlbC5cclxuICAgICAgICByZXR1cm4gQm9vbGVhbihwcm9wb3NhbElkKSAmJiAhcmV2aWV3ZWQuaGFzKHByb3Bvc2FsSWQpO1xyXG4gICAgICB9XHJcbiAgICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnUkVBRFlfVE9fQ09OVElOVUUnIHx8IChleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLnJlY292ZXJhYmxlID09PSB0cnVlKSkge1xyXG4gICAgICAgIGlmIChyZWFkeVZlcnNpb24gIT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0KSB7XHJcbiAgICAgICAgICByZWFkeVZlcnNpb24gPSBleGVjdXRpb24udXBkYXRlZF9hdDsgcmVhZHlTaW5jZSA9IERhdGUubm93KCk7XHJcbiAgICAgICAgfVxyXG4gICAgICAgIC8vIFdoaWxlIGEgbGFyZ2UgY29udGludWF0aW9uIGlzIGdlbmVyYXRpbmcsIHRoZSBsYXN0IGNvbW1pdHRlZCBzZXJ2ZXJcclxuICAgICAgICAvLyBjaGVja3BvaW50IGNhbiBzdGlsbCBiZSBSRUFEWS4gQWN0IG9ubHkgd2hlbiB0aGUgVUkgb2ZmZXJzIGl0IHRvby5cclxuICAgICAgICBjb25zdCBidXR0b24gPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pXHJcbiAgICAgICAgICAuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBdWZ0cmFnIGZvcnRzZXR6ZW4nLCBleGFjdDogdHJ1ZSB9KTtcclxuICAgICAgICByZXR1cm4gRGF0ZS5ub3coKSAtIHJlYWR5U2luY2UgPiA1MDAwICYmIGF3YWl0IGJ1dHRvbi5ldmFsdWF0ZUFsbChidXR0b25zID0+IGJ1dHRvbnMuc29tZShidXR0b24gPT4gIShidXR0b24gYXMgSFRNTEJ1dHRvbkVsZW1lbnQpLmRpc2FibGVkICYmIGJ1dHRvbi5nZXRDbGllbnRSZWN0cygpLmxlbmd0aCA+IDAgJiYgZ2V0Q29tcHV0ZWRTdHlsZShidXR0b24pLnZpc2liaWxpdHkgIT09IFwiaGlkZGVuXCIpKTtcclxuICAgICAgfVxyXG4gICAgICByZXR1cm4gWydCTE9DS0VEJywgJ0ZBSUxFRCcsICdJTkNPTVBMRVRFJ10uaW5jbHVkZXMoZXhlY3V0aW9uPy5zdGF0ZSk7XHJcbiAgICB9O1xyXG4gICAgLy8gQSBzaW5nbGUgcG9sbCBwcmV2aW91c2x5IHRpbWVkIGFsbCBvZiBDYXBhY2l0eSAtPiBJbnRlbGxpZ2VuY2UgdG9nZXRoZXIuXHJcbiAgICAvLyBCb3VuZCBlYWNoIGdlbnVpbmUgc3RhZ2UgYWR2YW5jZSwgd2hpbGUgcmV0cmllcyBhbmQgcmVzdGFydHMgcmV0YWluIHRoZWlyXHJcbiAgICAvLyByZW1haW5pbmcgZGVhZGxpbmUuIFRoZSBpbmRlcGVuZGVudCAyMC1taW51dGUgdGVzdCB0aW1lb3V0IGlzIHVuY2hhbmdlZC5cclxuICAgIGxldCBhdHRlbXB0ID0gMDtcclxuICAgIHdoaWxlICghYXdhaXQgaXNDaGVja3BvaW50KCkpIHtcclxuICAgICAgY29uc3QgcmVtYWluaW5nID0gd2F0Y2hkb2cucmVtYWluaW5nKHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICAgICAgYXdhaXQgcGFnZS53YWl0Rm9yVGltZW91dChNYXRoLm1pbihbNTAwLCAxMDAwLCAyMDAwXVtNYXRoLm1pbihhdHRlbXB0KyssIDIpXSwgcmVtYWluaW5nKSk7XHJcbiAgICB9XHJcbiAgICBydW5JZCA/Pz0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZDtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkKS50b0JlKHJ1bklkKTtcclxuICAgIGlmIChzdGVwcy5ldmVyeShzdGVwID0+IGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzW3N0ZXBdKSkpIHtcclxuICAgICAgaWYgKGNyYXNoU2ltdWxhdGlvbikgZXhwZWN0KHJlc3RhcnRlZEpvYklkLCAnQSByZWFsIHJ1bm5pbmcgc2ltdWxhdGlvbiBtdXN0IGJlIG9ic2VydmVkIGFuZCBpbnRlcnJ1cHRlZC4nKS50b0JlVHJ1dGh5KCk7XHJcbiAgICAgIHJldHVybiB7IHJ1bklkLCByZXZpZXdlZDogWy4uLnJldmlld2VkXSwgcmVzdGFydGVkSm9iSWQgfTtcclxuICAgIH1cclxuICAgIGNvbnN0IGV4ZWN1dGlvbiA9IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uO1xyXG4gICAgY29uc3QgZGlhbG9nID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KTtcclxuICAgIGlmIChzdG9wT25FdmlkZW5jZUJsb2NrICYmIGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24uYmxvY2tpbmdfZmluZGluZ3M/Lmxlbmd0aCkge1xyXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoYFdpemFyZCBCTE9DS0VEIGF0ICR7ZXhlY3V0aW9uLnN0ZXB9OiAke2V4ZWN1dGlvbi5tZXNzYWdlfWApO1xyXG4gICAgfVxyXG4gICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24ubWVzc2FnZT8uaW5jbHVkZXMoJ1JFQURZX1dJVEhfV0FSTklOR1MnKSkge1xyXG4gICAgICBjb25zdCBiZWZvcmVSZXZpZXcgPSBhd2FpdCByZWFkV2FybmluZ1Jldmlld1N0YXRlKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgICBjb25zdCBwcmVmbGlnaHQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9wcmVmbGlnaHQnKTtcclxuICAgICAgY29uc3Qgd2FybmluZ3MgPSBkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdQcmVmbGlnaHQtV2FybnVuZ2VuJyB9KTtcclxuICAgICAgYXdhaXQgZXhwZWN0KHdhcm5pbmdzLmdldEJ5Um9sZSgnbGlzdGl0ZW0nKS5maXJzdCgpKS50b0JlVmlzaWJsZSgpO1xyXG4gICAgICBjb25zdCBzdGFydGVkID0gcGVyZm9ybWFuY2Uubm93KCksIHN0YXJ0ZWRXYWxsID0gRGF0ZS5ub3coKTtcclxuICAgICAgd2F0Y2hkb2cucmVtYWluaW5nKHN0YXJ0ZWQpO1xyXG4gICAgICBjb25zdCBhcHByb3ZhbFJlc3BvbnNlID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4gbmV3IFVSTChyZXNwb25zZS51cmwoKSkucGF0aG5hbWUgPT09ICcvYXBpL2VuZ2luZWVyaW5nL3ByZWZsaWdodC93YXJuaW5ncy9hcHByb3ZlJ1xyXG4gICAgICAgICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnLCB7IHRpbWVvdXQ6IDE4MF8wMDAgfSk7XHJcbiAgICAgIGF3YWl0IHdhcm5pbmdzLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnV2FybnVuZ2VuIGZyZWlnZWJlbiB1bmQgZm9ydHNldHplbicgfSkuY2xpY2soKTtcclxuICAgICAgY29uc3QgYXBwcm92ZWQgPSBhd2FpdCBhcHByb3ZhbFJlc3BvbnNlO1xyXG4gICAgICBjb25zdCByZWNlaXB0ID0gYXdhaXQgYXBwcm92ZWQuanNvbigpO1xyXG4gICAgICBjb25zdCBhZnRlclJldmlldyA9IGF3YWl0IHJlYWRXYXJuaW5nUmV2aWV3U3RhdGUocGFnZSwgcHJvamVjdCk7XHJcbiAgICAgIGNvbnN0IHByb29mID0geyBiZWZvcmU6IGJlZm9yZVJldmlldywgYWZ0ZXI6IGFmdGVyUmV2aWV3LCBzbmFwc2hvdElkOiBwcmVmbGlnaHQuaWQsXHJcbiAgICAgICAgcmVxdWVzdFByb2plY3Q6IGFwcHJvdmVkLnJlcXVlc3QoKS5oZWFkZXJzKClbJ3gtcHJvamVjdC1pZCddLCBzdWJtaXR0ZWQ6IGFwcHJvdmVkLnJlcXVlc3QoKS5wb3N0RGF0YUpTT04oKSxcclxuICAgICAgICBzdGF0dXM6IGFwcHJvdmVkLnN0YXR1cygpLCByZXNwb25zZTogcmVjZWlwdCwgc3RhcnRlZCwgc3RhcnRlZFdhbGwsIGZpbmlzaGVkV2FsbDogRGF0ZS5ub3coKSB9O1xyXG4gICAgICBjb25zdCBjb21taXR0ZWRBdCA9IHBlcmZvcm1hbmNlLm5vdygpO1xyXG4gICAgICBjb25zdCBjb21taXR0ZWQgPSB3YXRjaGRvZy5jb21taXRXYXJuaW5nUmV2aWV3KHByb29mLCBjb21taXR0ZWRBdCk7XHJcbiAgICAgIGF3YWl0IHRlc3QuaW5mbygpLmF0dGFjaCgndmVyaWZpZWQtd2FybmluZy1yZXZpZXctcHJvb2YnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvb2YsIGNvbW1pdHRlZEF0LCBjb21taXR0ZWQgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgICAgIHByb2dyZXNzTWlsZXN0b25lcy5nZXQodGVzdC5pbmZvKCkudGVzdElkKSEucHVzaCh7IGF0OiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksIG1hbnVhbFdhcm5pbmdBcHByb3ZhbDogY29tbWl0dGVkLmFwcHJvdmFsSWRlbnRpdHksXHJcbiAgICAgICAgZnJvbnRpZXI6IGNvbW1pdHRlZC5mcm9udGllciwgcHJvamVjdCwgZXhlY3V0aW9uOiBhZnRlclJldmlldy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbiwgYXBwcm92YWw6IHJlY2VpcHQuYXBwcm92YWwgfSk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKSkuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQsXHJcbiAgICAgICAgeyB0aW1lb3V0OiBleHBlY3RlZEhhcmR3YXJlLmxlbmd0aCA+IDEwMCA/IDE4MF8wMDAgOiA2MF8wMDAgfSkubm90LnRvQmUoZXhlY3V0aW9uLnVwZGF0ZWRfYXQpO1xyXG4gICAgICBjb250aW51ZTtcclxuICAgIH1cclxuICAgIGlmIChbJ0JMT0NLRUQnLCAnRkFJTEVEJywgJ0lOQ09NUExFVEUnXS5pbmNsdWRlcyhleGVjdXRpb24/LnN0YXRlKSAmJiBleGVjdXRpb24ucmVjb3ZlcmFibGUgIT09IHRydWUpIHtcclxuICAgICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XHJcbiAgICAgIGNvbnN0IGlkID0gY29udmVyc2F0aW9uLmRhdGE/LmFjdGl2ZV9wcm9wb3NhbDtcclxuICAgICAgY29uc3QgcHJvcG9zYWwgPSBpZCA/IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke2lkfWApIDogbnVsbDtcclxuICAgICAgYXdhaXQgdGVzdC5pbmZvKCkuYXR0YWNoKCd3aXphcmQtYmxvY2tlcicsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBleGVjdXRpb24sXHJcbiAgICAgICAgcHJvcG9zYWw6IHByb3Bvc2FsPy5kYXRhPy52YWxpZGF0aW9uX3Jlc3VsdCwgdmlzaWJsZTogYXdhaXQgZGlhbG9nLmlubmVyVGV4dCgpIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoYFdpemFyZCAke2V4ZWN1dGlvbi5zdGF0ZX0gYXQgJHtleGVjdXRpb24uc3RlcH06ICR7ZXhlY3V0aW9uLm1lc3NhZ2V9YCk7XHJcbiAgICB9XHJcbiAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JFQURZX1RPX0NPTlRJTlVFJyB8fCAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5yZWNvdmVyYWJsZSA9PT0gdHJ1ZSkpIHtcclxuICAgICAgY29uc3QgYnV0dG9uID0gZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQXVmdHJhZyBmb3J0c2V0emVuJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgICAgIHRyeSB7XHJcbiAgICAgICAgYXdhaXQgYnV0dG9uLmNsaWNrKHsgdGltZW91dDogMjAwMCB9KTtcclxuICAgICAgfSBjYXRjaCAoZXJyb3IpIHtcclxuICAgICAgICBjb25zdCBsYXRlc3QgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgICBpZiAobGF0ZXN0LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0ID09PSBleGVjdXRpb24udXBkYXRlZF9hdCAmJiBhd2FpdCBidXR0b24uZXZhbHVhdGVBbGwoYnV0dG9ucyA9PiBidXR0b25zLnNvbWUoYnV0dG9uID0+ICEoYnV0dG9uIGFzIEhUTUxCdXR0b25FbGVtZW50KS5kaXNhYmxlZCAmJiBidXR0b24uZ2V0Q2xpZW50UmVjdHMoKS5sZW5ndGggPiAwICYmIGdldENvbXB1dGVkU3R5bGUoYnV0dG9uKS52aXNpYmlsaXR5ICE9PSBcImhpZGRlblwiKSkpIHRocm93IGVycm9yO1xyXG4gICAgICAgIGNvbnRpbnVlO1xyXG4gICAgICB9XHJcbiAgICAgIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcclxuICAgICAgICBjb25zdCBsYXRlc3QgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgICByZXR1cm4gbGF0ZXN0LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0ICE9PSBleGVjdXRpb24udXBkYXRlZF9hdFxyXG4gICAgICAgICAgfHwgbGF0ZXN0LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JVTk5JTkcnXHJcbiAgICAgICAgICB8fCBsYXRlc3Quc3RhdHVzZXM/LltleGVjdXRpb24uc3RlcF0gPT09ICdJTl9QUk9HUkVTUyc7XHJcbiAgICAgIH0sIHsgdGltZW91dDogNjBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbiAgICAgIGNvbnRpbnVlO1xyXG4gICAgfVxyXG4gICAgY29uc3QgY2FuZGlkYXRlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7cHJvcG9zYWxJZH1gKTtcclxuICAgIGlmIChjYW5kaWRhdGUuZGF0YS5wcm9wb3NhbF90eXBlID09PSAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJyAmJiByZXZpZXdDb3VudCA9PT0gMCAmJiBleHBlY3RlZEhhcmR3YXJlLmxlbmd0aCkge1xyXG4gICAgICBjb25zdCBoYXJkd2FyZSA9IGNhbmRpZGF0ZS5kYXRhLmNoYW5nZXNcclxuICAgICAgICAuZmlsdGVyKChjaGFuZ2U6IHsgb2JqZWN0X3R5cGU6IHN0cmluZyB9KSA9PiBjaGFuZ2Uub2JqZWN0X3R5cGUgPT09ICdIYXJkd2FyZU5vZGUnKVxyXG4gICAgICAgIC5tYXAoKGNoYW5nZTogeyBkYXRhOiB7IG5hbWU6IHN0cmluZyB9IH0pID0+IGNoYW5nZS5kYXRhLm5hbWUpO1xyXG4gICAgICBleHBlY3QoaGFyZHdhcmUsICdUaGUgVUkgbXVzdCBwcmVzZXJ2ZSB0aGUgaGFyZHdhcmUgZXhwbGljaXRseSBuYW1lZCBpbiB0aGUgdXNlciByZXF1ZXN0LicpXHJcbiAgICAgICAgLnRvRXF1YWwoZXhwZWN0LmFycmF5Q29udGFpbmluZyhleHBlY3RlZEhhcmR3YXJlKSk7XHJcbiAgICB9XHJcbiAgICBleHBlY3QocmV2aWV3ZWQuaGFzKHByb3Bvc2FsSWQpLCAnVGhlIHNhbWUgcHJvcG9zYWwgbXVzdCBub3QgcmVxdWVzdCByZXZpZXcgdHdpY2UuJykudG9CZShmYWxzZSk7XG4gICAgY29uc3QgcmV2aWV3QWN0aW9uID0gYXdhaXQgYmVmb3JlUHJvcG9zYWxSZXZpZXc/Lihwcm9wb3NhbElkLCBjYW5kaWRhdGUuZGF0YS5wcm9wb3NhbF90eXBlKTtcclxuICAgIGlmIChyZXZpZXdBY3Rpb24gPT09ICdTVE9QX0FGVEVSX1JFVklFVycpIHtcclxuICAgICAgLy8gRXhwbGljaXQgdGFyZ2V0ZWQgY292ZXJhZ2U6IHRoZSBzZWxlY3RlZCBwZW5kaW5nIHByb3Bvc2FsIGhhcyBiZWVuXHJcbiAgICAgIC8vIGV4ZXJjaXNlZCBidXQgaXMgbm90IGFwcGxpZWQgYW5kIHRoaXMgaXMgbm90IG5pbmUtc3RhZ2UgY29tcGxldGlvbi5cclxuICAgICAgcmV0dXJuIHsgcnVuSWQsIHJldmlld2VkOiBbLi4ucmV2aWV3ZWRdLCByZXN0YXJ0ZWRKb2JJZCxcclxuICAgICAgICByZXZpZXdPbmx5OiB7IHByb3Bvc2FsSWQsIHByb3Bvc2FsVHlwZTogY2FuZGlkYXRlLmRhdGEucHJvcG9zYWxfdHlwZSB9IH07XHJcbiAgICB9XHJcbiAgICBjb25zdCBhcHBseVJlc3BvbnNlID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4gcmVzcG9uc2UudXJsKCkuaW5jbHVkZXMoYC9wcm9wb3NhbHMvJHtwcm9wb3NhbElkfS9hcHByb3ZlLWFwcGx5YCkgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcsIHsgdGltZW91dDogMTgwXzAwMCB9KTtcclxuICAgIGNvbnN0IGFwcHJvdmFsID0gZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAvXihGcmVpZ2ViZW4sIMO8YmVybmVobWVuICYgZm9ydGZhaHJlbnzDnGJlcm5laG1lbiAmIGZvcnRmYWhyZW4pJC8gfSk7XHJcbiAgICBhd2FpdCBleHBlY3QoYXBwcm92YWwpLnRvQmVFbmFibGVkKHsgdGltZW91dDogNjBfMDAwIH0pO1xyXG4gICAgYXdhaXQgYXBwcm92YWwuY2xpY2soKTtcclxuICAgIGNvbnN0IGFwcGxpZWQgPSBhd2FpdCBhcHBseVJlc3BvbnNlO1xyXG4gICAgaWYgKCFhcHBsaWVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke2FwcGxpZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBhcHBsaWVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgICBleHBlY3QoKGF3YWl0IGFwcGxpZWQuanNvbigpKS5kYXRhLnN0YXR1cykudG9CZSgnQVBQTElFRCcpO1xyXG4gICAgcmV2aWV3ZWQuYWRkKHByb3Bvc2FsSWQpOyByZXZpZXdDb3VudCsrO1xyXG4gICAgLy8gQSBkaXN0aW5jdCwgYWN0dWFsbHkgY29tbWl0dGVkIG1hbnVhbCByZXZpZXcgc3RhcnRzIHRoZSBuZXh0IGF1dG9tYXRpY1xyXG4gICAgLy8gc2VjdGlvbi4gSXRzIHdyaXRlIHN0aWxsIGhhcyB0aGUgc2VwYXJhdGUgdW5jaGFuZ2VkIDE4MC1zZWNvbmQgbGltaXQuXHJcbiAgICB3YXRjaGRvZyA9IG5ldyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nKHBlcmZvcm1hbmNlLm5vdygpLCB3b3JrZmxvdyk7XHJcbiAgICBpZiAoY2FuZGlkYXRlLmRhdGEucHJvcG9zYWxfdHlwZSA9PT0gJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcgJiYgZXhwZWN0ZWRTaWduYWxzKSB7XHJcbiAgICAgIGF3YWl0IHZlcmlmeVNpZ25hbENvbnRyYWN0cyhwYWdlLCBwcm9qZWN0LCBleHBlY3RlZFNpZ25hbHMpO1xyXG4gICAgfVxyXG4gICAgaWYgKHJldmlld0NvdW50ID09PSAxICYmIGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQpIHtcclxuICAgICAgYXdhaXQgYWZ0ZXJGaXJzdE1vZGVsQXBwbGllZCgpO1xyXG4gICAgICAvLyBUaGlzIG9uZSB0ZXN0IGV4cGxpY2l0bHkgc3VibWl0cyBBTUVORCBhbmQgd2FpdHMgZm9yIGl0cyByZWNlaXB0LiBPbmx5XHJcbiAgICAgIC8vIHRoYXQgZGVsaWJlcmF0ZSBhY3Rpb24gcGVybWl0cyBiaW5kaW5nIGl0cyBuZXcgcmVxdWVzdCByZXZpc2lvbi5cclxuICAgICAgY29uc3QgYW1lbmRlZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICBleHBlY3QoYW1lbmRlZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkKS50b0JlKHJ1bklkKTtcclxuICAgICAgd2F0Y2hkb2cgPSBuZXcgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyhwZXJmb3JtYW5jZS5ub3coKSwgYW1lbmRlZCk7XHJcbiAgICB9XHJcbiAgICBpZiAocmV2aWV3Q291bnQgPT09IDEpIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7IC8vIER1cmFibGUgcmVsb2FkIGFmdGVyIGEgcmVhbCBjb21taXQuXHJcbiAgICBpZiAocmVzdGFydCAmJiByZXZpZXdDb3VudCA9PT0gMikge1xyXG4gICAgICBhd2FpdCByZXN0YXJ0QXBwbGljYXRpb24ocGFnZSk7XHJcbiAgICAgIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgICB9XHJcbiAgICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICAgIGNvbnN0IGN1cnJlbnQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgcmV0dXJuIGN1cnJlbnQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQgIT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0O1xyXG4gICAgfSwgeyB0aW1lb3V0OiA2MF8wMDAgfSkudG9CZSh0cnVlKTtcclxuICB9XHJcbiAgdGhyb3cgbmV3IEVycm9yKCdXaXphcmQgZXhjZWVkZWQgMTYgcmV2aWV3L2NvbnRpbnVhdGlvbiBjaGVja3BvaW50cy4nKTtcclxufVxyXG5cclxudGVzdCgnd2l6YXJkIHJlZnVzZXMgYW4gdW5hdmFpbGFibGUgY2F0YWxvZyBhbmQgcmVjb3ZlcnMgdXNpbmcgdGhlIHJlYWwgcmVnaXN0cnkgQGNhdGFsb2ctcmVjb3ZlcnknLCBhc3luYyAoe3BhZ2V9KSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWNhdGFsb2ctcmVjb3ZlcnktJyArIHJhbmRvbVVVSUQoKTtcclxuICBhd2FpdCBwYWdlLnJvdXRlKCcqKi9hcGkvdGVjaG5vbG9naWVzJywgcm91dGUgPT4gcm91dGUuZnVsZmlsbCh7c3RhdHVzOjUwMyxcclxuICAgIGNvbnRlbnRUeXBlOidhcHBsaWNhdGlvbi9qc29uJyxib2R5OkpTT04uc3RyaW5naWZ5KHtlcnJvcjonRGVyIHZvbGxzdMOkbmRpZ2UgVGVjaG5vbG9naWVrYXRhbG9nIGlzdCBkZXJ6ZWl0IG5pY2h0IGVycmVpY2hiYXIuJ30pfSkpO1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2FsZXJ0JykpLnRvQ29udGFpblRleHQoJ1RlY2hub2xvZ2lla2F0YWxvZycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdQcm9qZWt0bmFtZScsIHtleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cubG9jYXRvcignI2VuZ2luZWVyaW5nLXByb2plY3QtbmFtZScpLmZpbGwoJ0NhdGFsb2cgcmV0cnknKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHtleGFjdDp0cnVlfSkuZmlsbCgnZWluIEFrdG9yIHp1bSBwcm9wb3J0aW9uYWwgc2NobGllw59lbiBlaW5lcyBWZW50aWwnKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKSkudG9CZURpc2FibGVkKCk7XHJcbiAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzKS50b0hhdmVMZW5ndGgoMCk7XHJcbiAgYXdhaXQgcGFnZS51bnJvdXRlKCcqKi9hcGkvdGVjaG5vbG9naWVzJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonVGVjaG5vbG9naWVrYXRhbG9nIGVybmV1dCBsYWRlbid9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdhbGVydCcpKS50b0hhdmVDb3VudCgwKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKSkudG9CZUVuYWJsZWQoKTtcclxuICBjb25zdCBjYXRhbG9nID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvdGVjaG5vbG9naWVzJykpLmpzb24oKTtcclxuICBleHBlY3QoY2F0YWxvZy50ZWNobm9sb2d5X2NvdW50KS50b0JlKDEyNSk7XHJcbn0pO1xyXG5cclxudGVzdCgnbmV3IHNtYWxsIHdpemFyZCB0cmF2ZXJzZXMgYWxsIG5pbmUgc3RhZ2VzIGFuZCBzdXJ2aXZlcyByZWxvYWQvcmVzdGFydCBAc21hbGwnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgZXJyb3JzOiBzdHJpbmdbXSA9IFtdOyBwYWdlLm9uKCdwYWdlZXJyb3InLCBlcnJvciA9PiBlcnJvcnMucHVzaChlcnJvci5tZXNzYWdlKSk7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXNtYWxsLScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdFMkUgc21hbGwnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCgnRXJ6ZXVnZSBlaW4gQXV0b21vdGl2ZSBDQU4tRkQgTmV0endlcmsgbWl0IGVpbmVtIEdhdGV3YXkgU3lzdGVtLCBkZW4gRUNVcyBNb3RvcnN0ZXVlcnVuZyB1bmQgQW56ZWlnZSwgZWluZW0gU2Vuc29yIE1vdG9yVGVtcGVyYXR1cmUgdW5kIGVpbmVtIEFrdG9yIE1vdG9yVmFsdmUuIE1vdG9yVGVtcGVyYXR1cmUgd2lyZCB2b24gTW90b3JzdGV1ZXJ1bmcgYXVzZ2V3ZXJ0ZXQuIE1vdG9yc3RldWVydW5nIHN0ZXVlcnQgTW90b3JWYWx2ZS4gQ29udHJvbGxlcnN0YXR1cyBibGVpYnQgYmlzIHp1ciBBdXN3YWhsIGtvbmtyZXRlciBFbXBmw6RuZ2VyIHVuZCBTaWduYWxlIGludGVybi4gUHLDvGZlIHVuZCBhcmJlaXRlIGJpcyBEYXRhIFNjaWVuY2UgJiBJbnRlbGxpZ2VuY2UuXFxuQ0FOLUZEOiA1MDAga2JpdC9zIGFyYml0cmF0aW9uLCAyIE1iaXQvcyBkYXRhXFxuQ0FOOiA1MDAga2JpdC9zJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1dlaXRlcmUgSGlud2Vpc2UnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwoJy0gQWt0b3ItQmVmZWhsZToge1wiTW90b3JWYWx2ZVwiOntcImxlbmd0aF9iaXRzXCI6MSxcImRhdGFfdHlwZVwiOlwiYm9vbGVhblwiLFwiZmFjdG9yXCI6MSxcInVuaXRcIjpcImNvZGVcIixcIm1pbl92YWx1ZVwiOjAsXCJtYXhfdmFsdWVcIjoxLFwic2VtYW50aWNcIjp7XCJzZW1hbnRpY190eXBlXCI6XCJCT09MRUFOXCJ9LFwiZGF0YVwiOntcImVudW1fdmFsdWVzXCI6e1wiQ0xPU0VcIjowLFwiT1BFTlwiOjF9fX19Jyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ0dlcsOkdGV1bWZhbmcnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgZm9yIChjb25zdCBbbGFiZWwsIHZhbHVlXSBvZiBbWydHYXRld2F5cycsICcxJ10sIFsnQ29udHJvbGxlcicsICcyJ10sIFsnU2Vuc29yZW4nLCAnMSddLCBbJ0FrdG9yZW4nLCAnMSddXSkgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoYCR7bGFiZWx9OiB2ZXJiaW5kbGljaGUgQW56YWhsYCwgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHZhbHVlKTtcclxuICBjb25zdCBzdGFydFJlcXVlc3QgPSBwYWdlLndhaXRGb3JSZXF1ZXN0KHJlcXVlc3QgPT4gcmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JylcclxuICAgICYmIHJlcXVlc3QubWV0aG9kKCkgPT09ICdQT1NUJyAmJiByZXF1ZXN0LnBvc3REYXRhSlNPTigpPy53aXphcmRfY29tbWFuZD8uYWN0aW9uID09PSAnU1RBUlQnKTtcclxuICAvLyBVc2UgdGhlIHNhbWUgdmlzaWJsZSBxdWVzdGlvbm5haXJlIG5hdmlnYXRpb24gYSB1c2VyIHVzZXM7IG5ldmVyIGluamVjdCBnZW5lcmF0ZWQgbW9kZWwgcm93cy5cclxuICBmb3IgKGxldCBzdGVwID0gMDsgc3RlcCA8IDEwOyBzdGVwKyspIHtcclxuICAgIGNvbnN0IHN1Ym1pdCA9IGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJyk7XHJcbiAgICBhd2FpdCBleHBlY3Qoc3VibWl0KS50b0JlRW5hYmxlZCgpO1xyXG4gICAgY29uc3QgbmFtZSA9IGF3YWl0IHN1Ym1pdC5pbm5lclRleHQoKTtcclxuICAgIGF3YWl0IHN1Ym1pdC5jbGljaygpO1xyXG4gICAgaWYgKG5hbWUgPT09ICfDnGJlcm5laG1lbicpIGJyZWFrO1xyXG4gICAgaWYgKHN0ZXAgPT09IDkpIHRocm93IG5ldyBFcnJvcignUXVlc3Rpb25uYWlyZSBkaWQgbm90IG9mZmVyIHN1Ym1pdC4nKTtcclxuICB9XHJcbiAgY29uc3QgcmVxdWVzdGVkID0gKGF3YWl0IHN0YXJ0UmVxdWVzdCkucG9zdERhdGFKU09OKCkud2l6YXJkX2NvbW1hbmQud2l6YXJkX2NvbnRleHQ7XHJcbiAgZXhwZWN0KHJlcXVlc3RlZC50ZWNobm9sb2dpZXMsICdBbiBleHBsaWNpdCBDQU4tRkQgdGFzayBtdXN0IG5vdCBzaWxlbnRseSByZXF1ZXN0IExJTiBhbmQgU09NRS9JUC4nKS50b0VxdWFsKFsnQ0FOLUZEIChjYW5fZmQpJ10pO1xyXG4gIC8vIFByZXNlcnZlIGEgcmVhbCBwZW5kaW5nIG1vZGVsIHRocm91Z2ggcGFyYW1ldGVyIHNhdmUgYW5kIHJlbmV3ZWQgcmV2aWV3LlxyXG4gIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IChhd2FpdCByZWFkUHJvamVjdChwYWdlLHByb2plY3QsJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5JykpLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5zdGF0ZSxcclxuICAgIHt0aW1lb3V0OjE4MDAwMH0pLnRvQmUoJ1JFVklFV19SRVFVSVJFRCcpO1xyXG4gIGNvbnN0IHBlbmRpbmcgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSxwcm9qZWN0LCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpKS5kYXRhLmFjdGl2ZV9wcm9wb3NhbDtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8/bW9kZT1wYXJhbWV0ZXJzJnByb2plY3Q9JHtwcm9qZWN0fSZ0ZWNobm9sb2d5PWNhbl9mZCZwcm9wb3NhbD0ke3BlbmRpbmd9I3BhcmFtZXRlci1maW5kaW5nc2ApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgncmVnaW9uJyx7bmFtZTonQWt0dWVsbGUgUGFyYW1ldGVyYmVmdW5kZSd9KSkudG9Db250YWluVGV4dCgnbm9jaCBuaWNodCDDvGJlcm5vbW1lbmVuIFZvcnNjaGxhZ3MnKTtcclxuICBjb25zdCBjb21tb24gPSBwYWdlLmxvY2F0b3IoJy5wYXJhbWV0ZXItZ3JvdXAtY29tbW9uJyk7XHJcbiAgYXdhaXQgZXhwZWN0KGNvbW1vbi5sb2NhdG9yKCcjYXJiaXRyYXRpb25fYml0cmF0ZScpKS50b0hhdmVWYWx1ZSgnNTAwIGtiaXQvcycpO1xyXG4gIGF3YWl0IGV4cGVjdChjb21tb24ubG9jYXRvcignI2RhdGFfYml0cmF0ZScpKS50b0hhdmVWYWx1ZSgnMiBNYml0L3MnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcucGFyYW1ldGVyLWRldGFpbHNbb3Blbl0nKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgYXdhaXQgcmVwZWF0UGFyYW1ldGVyUmV0dXJuKHBhZ2UsIHByb2plY3QsIHBlbmRpbmcsIFt7dGVjaG5vbG9neTogJ2Nhbl9mZCcsXG4gICAgZmllbGRzOiB7YXJiaXRyYXRpb25fYml0cmF0ZTogJzUwMCBrYml0L3MnLCBkYXRhX2JpdHJhdGU6ICcxIE1iaXQvcycsIGNhbl9mZF9kYXRhX3ByZXNjYWxlcjogJzInfSxcbiAgICBuYXRpdmU6IHthcmJpdHJhdGlvbl9iaXRyYXRlOiA1MDBfMDAwLCBkYXRhX2JpdHJhdGU6IDFfMDAwXzAwMCwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyOiAyfSxcbiAgICBlZGl0RmllbGRzOiBbJ2RhdGFfYml0cmF0ZScsICdjYW5fZmRfZGF0YV9wcmVzY2FsZXInXX1dKTtcbiAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLHByb2plY3QsYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7cGVuZGluZ30/dmlldz1zdGF0dXNgKSkuZGF0YS5jYW5vbmljYWxfaWRzKS50b0VxdWFsKFtdKTtcbiAgZXhwZWN0KChhd2FpdCBhbGxPYmplY3RzKHBhZ2UscHJvamVjdCwnaGFyZHdhcmUtbm9kZXMnKSkpLnRvSGF2ZUxlbmd0aCgwKTtcbiAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCB0cnVlLFxyXG4gICAgWydTeXN0ZW0nLCAnTW90b3JzdGV1ZXJ1bmcnLCAnQW56ZWlnZScsICdNb3RvclRlbXBlcmF0dXJlJywgJ01vdG9yVmFsdmUnXSk7XHJcbiAgY29uc3QgYXJ0aWZhY3RzID0gYXdhaXQgdmVyaWZ5QXJ0aWZhY3RzKHBhZ2UsIHByb2plY3QsIDUsIHVuZGVmaW5lZCwge1xyXG4gICAgc2VlZDogNDIsIGRhdGFfYml0cmF0ZTogMV8wMDBfMDAwLCBjYW5fZmRfZGF0YV9wcmVzY2FsZXI6IDIsXHJcbiAgfSk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50Lm9ic2VydmVkX3NpZ25hbF9jb3VudCkudG9CZUdyZWF0ZXJUaGFuT3JFcXVhbCgzKTtcclxuICBleHBlY3QoYXJ0aWZhY3RzLmFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UudHJhbnNwb3J0X2V4Y2x1c2lvbnMpLnRvSGF2ZUxlbmd0aCgzKTtcclxuICBjb25zdCBmaW5pc2hlZCA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IHJlc3BvbnNlLnVybCgpLmluY2x1ZGVzKGAvcnVucy8ke2NvbnRpbnVpdHkucnVuSWR9L2ZpbmlzaGApXHJcbiAgICAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRmVydGlnIHN0ZWxsZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGV4cGVjdCgoYXdhaXQgZmluaXNoZWQpLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZykubm90LnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBleHBlY3QoKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnMpLnRvSGF2ZUxlbmd0aCgxKTtcclxuICBleHBlY3QoZXJyb3JzKS50b0VxdWFsKFtdKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2V2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIC4uLmNvbnRpbnVpdHksIC4uLmFydGlmYWN0cyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxufSk7XHJcblxyXG5mb3IgKGNvbnN0IHRlY2hub2xvZ3kgb2YgWydJMkMnLCAnTW9kYnVzIFJUVSddKSB7XHJcbiAgdGVzdChgUmFzcGJlcnJ5IFBpICR7dGVjaG5vbG9neX0gcHJvamVjdCByZXRhaW5zIG1vZGVsIGFuZCBibG9ja3MgaW5jb25zaXN0ZW50IG5hdGl2ZSBwYXJhbWV0ZXJzIEBub25hdXRvbW90aXZlYCwgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gICAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWVtYmVkZGVkLScgKyByYW5kb21VVUlEKCk7XHJcbiAgICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdUZW1wZXJhdHVycmVnZWx1bmcnKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdQcm9qZWt0YmVzY2hyZWlidW5nJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHRlY2hub2xvZ3kgPT09ICdJMkMnXHJcbiAgICAgID8gJzIgQWt0b3JlbiBmw7xyIFZlbnRpbGUsIDQgU2Vuc29yZW4gZsO8ciBUZW1wZXJhdHVyZW4sIHVuZCBlaW4gUmFzcGJlcnJ5UGknXHJcbiAgICAgIDogYDIgQWt0b3JlbiBmw7xyIFZlbnRpbGUsIDQgU2Vuc29yZW4gZsO8ciBUZW1wZXJhdHVyZW4sIHVuZCBlaW4gUmFzcGJlcnJ5UGkuIEVtYmVkZGVkIFN5c3RlbXMuIEFsbGUgR2Vyw6R0ZSBrb21tdW5pemllcmVuIMO8YmVyICR7dGVjaG5vbG9neX0uIFByw7xmZSB1bmQgYXJiZWl0ZSBiaXMgRGF0YSBTY2llbmNlICYgSW50ZWxsaWdlbmNlLmApO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ05ldHphcmNoaXRla3R1cicsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ3JhZGlvJywgeyBuYW1lOiAvVmFyaWFudGUgMC8gfSkuY2hlY2soKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdHZXLDpHRldW1mYW5nJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Jhc3BiZXJyeVBpOiBBbnNjaGx1c3MnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignSTJDJyk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlMYWJlbCgnVGVtcGVyYXR1cnNlbnNvcjE6IEFuc2NobHVzcycsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZVZhbHVlKCcnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgICBmb3IgKGNvbnN0IG5hbWUgb2YgWydSYXNwYmVycnlQaScsICdUZW1wZXJhdHVyc2Vuc29yMScsICdUZW1wZXJhdHVyc2Vuc29yMicsICdUZW1wZXJhdHVyc2Vuc29yMycsICdUZW1wZXJhdHVyc2Vuc29yNCcsICdWZW50aWxha3RvcjEnLCAnVmVudGlsYWt0b3IyJ10pIHtcclxuICAgICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbChgJHtuYW1lfTogQW5zY2hsdXNzYCwgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ0kyQycpO1xyXG4gICAgICB9XHJcbiAgICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdTZW5zb3IgMTogTWVzc2dyw7bDn2UnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignc3BlZWQnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeUxhYmVsKCdUZW1wZXJhdHVyc2Vuc29yMTogQW5zY2hsdXNzJywgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoJ0kyQycpO1xyXG4gICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnU2Vuc29yIDE6IE1lc3NncsO2w59lJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ3RlbXBlcmF0dXJlJyk7XHJcbiAgICB9XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnVmVudGlsYWt0b3IxOiBTdGVsbGJlZmVobCcsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdPUEVOX0NMT1NFJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMjogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnVmVudGlsYWt0b3IyOiBTdGVsbGJlZmVobCcsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdPUEVOX0NMT1NFJyk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBleHBlY3QoY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIHRydWUsIFsnUmFzcGJlcnJ5UGknLCAnVGVtcGVyYXR1cnNlbnNvcjEnLCAnVGVtcGVyYXR1cnNlbnNvcjInLCAnVGVtcGVyYXR1cnNlbnNvcjMnLCAnVGVtcGVyYXR1cnNlbnNvcjQnLCAnVmVudGlsYWt0b3IxJywgJ1ZlbnRpbGFrdG9yMiddLCBmYWxzZSwgdW5kZWZpbmVkLCB1bmRlZmluZWQsIHRydWUpKVxyXG4gICAgICAucmVqZWN0cy50b1Rocm93KC9XaXphcmQgQkxPQ0tFRCBhdCBwYXJhbWV0ZXJzOi4qYmVzdMOkdGlndGUgQW5nYWJlbi8pO1xyXG4gICAgY29uc3Qgd29ya2Zsb3cgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpO1xyXG4gICAgY29uc3QgZmluZGluZ3MgPSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbi5ibG9ja2luZ19maW5kaW5ncyBhcyB7IGNvZGU6IHN0cmluZyB9W107XHJcbiAgICBleHBlY3QoZmluZGluZ3MubWFwKGl0ZW0gPT4gaXRlbS5jb2RlKSkudG9Db250YWluKCdURUNITk9MT0dZX1BBUkFNRVRFUl9ERVBFTkRFTkNZX01JU01BVENIJyk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuc3RhdHVzZXMucGFyYW1ldGVycykudG9CZSgnSU5fUFJPR1JFU1MnKTtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5hcnRpZmFjdF9jaGVja3MucGFyYW1ldGVycy5jb21wbGV0ZSkudG9CZShmYWxzZSk7XHJcbiAgICBjb25zdCByZXF1aXJlZCA9IHdvcmtmbG93LmFydGlmYWN0X2NoZWNrcy5wYXJhbWV0ZXJzLnJlcXVpcmVkO1xyXG4gICAgZXhwZWN0KHJlcXVpcmVkLnByb2ZpbGVfdmFsdWVzKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IGRldmljZVNvdXJjZSA9IHRlY2hub2xvZ3kgPT09ICdJMkMnID8gJ2kyY19kZXZpY2Vfc291cmNlJyA6ICdtcl9kZXZpY2Vfc291cmNlJztcclxuICAgIC8vIFRoZXNlIHNjZW5hcmlvcyByZW1haW4gYmxvY2tlZCBieSByZWFsIG5hdGl2ZSBkZXBlbmRlbmNpZXMsIG5vdCBieSB0aGVcclxuICAgIC8vIGFic2VuY2Ugb2YgYSByZWFsIGRldmljZSBxdWFsaWZpY2F0aW9uIG9yIGZhYnJpY2F0ZWQgc291cmNlIGlkZW50aWZpZXIuXHJcbiAgICBleHBlY3QocmVxdWlyZWQpLm5vdC50b0hhdmVQcm9wZXJ0eShkZXZpY2VTb3VyY2UsIGZhbHNlKTtcclxuICAgIGNvbnN0IG5hdGl2ZVRlY2hub2xvZ3kgPSB0ZWNobm9sb2d5ID09PSAnSTJDJyA/ICdpMmMnIDogJ21vZGJ1c19ydHUnO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnNbbmF0aXZlVGVjaG5vbG9neV0udmFsdWVzKVxyXG4gICAgICAubm90LnRvSGF2ZVByb3BlcnR5KGRldmljZVNvdXJjZSk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuYXJ0aWZhY3RfY2hlY2tzLnBhcmFtZXRlcnMucHJvZmlsZV9maW5kaW5ncy5zb21lKChmaW5kaW5nOiB7Y29kZTogc3RyaW5nfSkgPT5cclxuICAgICAgZmluZGluZy5jb2RlID09PSAnVEVDSE5PTE9HWV9QQVJBTUVURVJfREVQRU5ERU5DWV9NSVNNQVRDSCcpKS50b0JlKHRydWUpO1xyXG4gICAgY29uc3QgZXZpZGVuY2VSZXZpZXcgPSBkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7bmFtZTogJ0Jsb2NraWVyZW5kZSBQcmVmbGlnaHQtQmVmdW5kZSd9KTtcclxuICAgIGF3YWl0IGV4cGVjdChldmlkZW5jZVJldmlldykudG9Db250YWluVGV4dCh0ZWNobm9sb2d5ID09PSAnSTJDJyA/ICdpMmNfcHVsbHVwX29obXMnIDogJ21yX3BkdV9ieXRlcycpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGV2aWRlbmNlUmV2aWV3LmdldEJ5Um9sZSgnbGluaycsIHtuYW1lOiAnQmV0cm9mZmVuZSBBbmdhYmVuIGJlYXJiZWl0ZW4nfSkuZmlyc3QoKSlcclxuICAgICAgLnRvSGF2ZUF0dHJpYnV0ZSgnaHJlZicsIG5ldyBSZWdFeHAoYG1vZGU9cGFyYW1ldGVycy4qcHJvamVjdD0ke3Byb2plY3R9YCkpO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LnN0YXR1c2VzLnNpbXVsYXRpb24pLnRvQmUoJ0VNUFRZJyk7XHJcbiAgICBpZiAodGVjaG5vbG9neSA9PT0gJ0kyQycpIHtcclxuICAgICAgZXhwZWN0KHdvcmtmbG93LnBhcmFtZXRlcnMucmF0ZV9yZXZpZXdfcHJvcG9zYWxzLmkyYy5zdGF0dXMpLnRvQmUoJ1JFVklFV19SRVFVSVJFRCcpO1xyXG4gICAgICBleHBlY3Qod29ya2Zsb3cucGFyYW1ldGVycy5wYXJhbWV0ZXJfcHJvdmVuYW5jZS5iaXRyYXRlLnNvdXJjZSkudG9CZSgnVEVDSE5PTE9HWV9QUk9GSUxFX1JFVklFV19QUk9QT1NBTCcpO1xyXG4gICAgfVxyXG4gICAgY29uc3QgaW50ZXJmYWNlcyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLWludGVyZmFjZXMnKTtcclxuICAgIGV4cGVjdChpbnRlcmZhY2VzLmxlbmd0aCkudG9CZUdyZWF0ZXJUaGFuT3JFcXVhbCg3KTtcclxuICAgIGV4cGVjdChpbnRlcmZhY2VzLmV2ZXJ5KGl0ZW0gPT4gIS9hdXRvbW90aXZlfGNhbnxsaW4vaS50ZXN0KGl0ZW0udGVjaG5vbG9neSkpKS50b0JlKHRydWUpO1xyXG4gICAgY29uc3QgaGFyZHdhcmUgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gICAgZXhwZWN0KGhhcmR3YXJlLmV2ZXJ5KGl0ZW0gPT4gaXRlbS5kb21haW4gIT09ICdhdXRvbW90aXZlJykpLnRvQmUodHJ1ZSk7XHJcbiAgICBpZiAodGVjaG5vbG9neSA9PT0gJ0kyQycpIHtcclxuICAgICAgY29uc3Qgc2lnbmFscyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ3NpZ25hbHMnKTtcclxuICAgICAgZXhwZWN0KHNpZ25hbHMuc29tZShpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ1RlbXBlcmF0dXJfVGVtcGVyYXR1cnNlbnNvcjEnICYmIGl0ZW0udW5pdCA9PT0gJ2RlZ0MnKSkudG9CZSh0cnVlKTtcclxuICAgIH1cclxuICAgIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icykudG9IYXZlTGVuZ3RoKDApO1xyXG4gICAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdub25hdXRvbW90aXZlLWV2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIHRlY2hub2xvZ3ksIGZpbmRpbmdzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gIH0pO1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiBzdGFydENhcHR1cmVkTGFyZ2VXaXphcmQocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nKSB7XHJcbiAgY29uc3QgcnVuSWQgPSByYW5kb21VVUlEKCk7XHJcbiAgY29uc3Qgb3JpZ2luYWwgPSBhd2FpdCByZWFkRmlsZShuZXcgVVJMKCcuL2ZpeHR1cmVzL3dpemFyZC1sYXJnZS01MC0yNTAtMjUwLnR4dCcsIGltcG9ydC5tZXRhLnVybCksICd1dGY4Jyk7XHJcbiAgY29uc3QgbWV0YWRhdGEgPSBKU09OLnBhcnNlKGF3YWl0IHJlYWRGaWxlKG5ldyBVUkwoJy4vZml4dHVyZXMvd2l6YXJkLWxhcmdlLTUwLTI1MC0yNTAuanNvbicsIGltcG9ydC5tZXRhLnVybCksICd1dGY4JykpO1xyXG4gIGNvbnN0IGJhc2VsaW5lID0gSlNPTi5wYXJzZShhd2FpdCByZWFkRmlsZShuZXcgVVJMKCcuL2ZpeHR1cmVzL3dpemFyZC1sYXJnZS1zaWduYWwtY29udHJhY3RzLmpzb24nLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpKTtcclxuICBjb25zdCBwcm9tcHQgPSBvcmlnaW5hbC5yZXBsYWNlKC9eLSBMYXVmLUlEOi4qJC9tLCAnLSBMYXVmLUlEOiAnICsgcnVuSWQpO1xyXG4gIGF3YWl0IHJldmlld1ZpcnR1YWxUcmFuc3BvcnRzKHBhZ2UsIHByb2plY3QsIHRydWUpO1xuICAvLyBSZXBsYXkgdGhlIGNhcHR1cmVkLCBhbHJlYWR5IGNvbmZpcm1lZCBpbnB1dCB0aHJvdWdoIHRoZSBub3JtYWwgU1RBUlQgQVBJLlxyXG4gIC8vIEFsbCBwcm9wb3NhbCBpbnNwZWN0aW9uLCBhcHByb3ZhbCwgY29udGludWF0aW9uIGFuZCByZWxvYWRzIGJlbG93IHVzZSBVSS5cclxuICBjb25zdCBzdGFydGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY2hhdCcsIHtcclxuICAgIGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSwgdGltZW91dDogMjQwXzAwMCxcclxuICAgIGRhdGE6IHsgcHJvbXB0LCB3aXphcmRfY29tbWFuZDogeyBhY3Rpb246ICdTVEFSVCcsIHJ1bl9pZDogcnVuSWQsIG9wZXJhdGlvbl9pZDogcmFuZG9tVVVJRCgpLFxyXG4gICAgICB0YXJnZXQ6ICdkYXRhX3NjaWVuY2VfaW50ZWxsaWdlbmNlJywgd2l6YXJkX2NvbnRleHQ6IHsgLi4ubWV0YWRhdGEud2l6YXJkX2NvbnRleHQsIHByb2plY3RfaWQ6IHByb2plY3QsIHJ1bl9pZDogcnVuSWQgfSB9IH0sXHJcbiAgfSk7XHJcbiAgaWYgKCFzdGFydGVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke3N0YXJ0ZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBzdGFydGVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICByZXR1cm4geyBydW5JZCwgbWV0YWRhdGEsIGJhc2VsaW5lIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGxhcmdlUGFyYW1ldGVyU2NlbmFyaW9zKCk6IFBhcmFtZXRlclJldHVyblNjZW5hcmlvW10ge1xyXG4gIHJldHVybiBbXHJcbiAgICB7dGVjaG5vbG9neTogJ2xpbicsIGZpZWxkczoge2xpbl9iaXRyYXRlX2JwczogJzE5LDIga2JpdC9zJ30sIG5hdGl2ZToge2xpbl9iaXRyYXRlX2JwczogMTlfMjAwfX0sXHJcbiAgICB7dGVjaG5vbG9neTogJ2Nhbl9mZCcsIGZpZWxkczoge2FyYml0cmF0aW9uX2JpdHJhdGU6ICc1MDAga2JpdC9zJywgZGF0YV9iaXRyYXRlOiAnMiBNYml0L3MnfSxcclxuICAgICAgbmF0aXZlOiB7YXJiaXRyYXRpb25fYml0cmF0ZTogNTAwXzAwMCwgZGF0YV9iaXRyYXRlOiAyXzAwMF8wMDB9fSxcclxuICAgIHt0ZWNobm9sb2d5OiAnZXRoZXJuZXQnLCBmaWVsZHM6IHtiaXRyYXRlOiAnMSBHYml0L3MnfSwgbmF0aXZlOiB7Yml0cmF0ZTogMV8wMDBfMDAwXzAwMH0sIGVkaXRGaWVsZHM6IFsnYml0cmF0ZSddfSxcclxuICBdO1xyXG59XHJcblxyXG50ZXN0KCdleGFjdCBjb25maXJtZWQgNTAvMjUwLzI1MCByZXF1ZXN0IGNvbXBsZXRlcyB0aHJvdWdoIHJlYWwgd2l6YXJkIHJldmlldyBAbGFyZ2UnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgZXJyb3JzOiBzdHJpbmdbXSA9IFtdOyBwYWdlLm9uKCdwYWdlZXJyb3InLCBlcnJvciA9PiBlcnJvcnMucHVzaChlcnJvci5tZXNzYWdlKSk7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWxhcmdlLScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgeyBydW5JZCwgbWV0YWRhdGEsIGJhc2VsaW5lIH0gPSBhd2FpdCBzdGFydENhcHR1cmVkTGFyZ2VXaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgY29uc3QgcGFyYW1ldGVyUmV0dXJuUmV2aWV3czogc3RyaW5nW10gPSBbXTtcbiAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCBmYWxzZSwgW10sIHRydWUsIGJhc2VsaW5lLnNpZ25hbHMsXG4gICAgdW5kZWZpbmVkLCBmYWxzZSwgYXN5bmMgKHByb3Bvc2FsSWQsIHByb3Bvc2FsVHlwZSkgPT4ge1xuICAgICAgaWYgKCFbJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcsICdXSVpBUkRfUk9VVElORycsICdXSVpBUkRfTkVUV09SS19UT1BPTE9HWSddLmluY2x1ZGVzKHByb3Bvc2FsVHlwZSkpIHJldHVybjtcbiAgICAgIC8vIE9uZSBmdWxsIHRocmVlLWJ1cyBjeWNsZSByZW1haW5zIGludGVncmF0ZWQgYXQgZXZlcnkgcmV2aWV3IHN0YWdlLlxyXG4gICAgICAvLyBSZXBlYXRlZCB0aHJlZS1zZWVkIGNvdmVyYWdlIGhhcyBpdHMgb3duIHJlYWwgbGFyZ2UgY2FzZXMgYmVsb3csXHJcbiAgICAgIC8vIHByZXNlcnZpbmcgdGhlIGNvbnRyYWN0dWFsIDIwLW1pbnV0ZSB3aG9sZS13b3JrZmxvdyBjYXNlIGxpbWl0LlxyXG4gICAgICBhd2FpdCByZXBlYXRQYXJhbWV0ZXJSZXR1cm4ocGFnZSwgcHJvamVjdCwgcHJvcG9zYWxJZCwgbGFyZ2VQYXJhbWV0ZXJTY2VuYXJpb3MoKSwgWzQyXSk7XHJcbiAgICAgIHBhcmFtZXRlclJldHVyblJldmlld3MucHVzaChwcm9wb3NhbFR5cGUpO1xuICAgIH0pO1xuICBleHBlY3QocGFyYW1ldGVyUmV0dXJuUmV2aWV3cykudG9FcXVhbChbJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcsICdXSVpBUkRfUk9VVElORycsICdXSVpBUkRfTkVUV09SS19UT1BPTE9HWSddKTtcbiAgZXhwZWN0KGNvbnRpbnVpdHkucnVuSWQpLnRvQmUocnVuSWQpO1xyXG4gIGNvbnN0IGhhcmR3YXJlID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICBleHBlY3QoaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5kZXZpY2VfdHlwZSA9PT0gJ1NlbnNvckNvbnRyb2xsZXInKSkudG9IYXZlTGVuZ3RoKDI1MCk7XHJcbiAgZXhwZWN0KGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0uZGV2aWNlX3R5cGUgPT09ICdBY3R1YXRvckNvbnRyb2xsZXInKSkudG9IYXZlTGVuZ3RoKDI1MCk7XHJcbiAgZXhwZWN0KGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0uZGV2aWNlX3R5cGUgPT09ICdFQ1UnKS5sZW5ndGgpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoNTApO1xyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCAxNDA0LCB1bmRlZmluZWQsIHVuZGVmaW5lZCwge1xuICAgIGxpbjoge2JpdHJhdGU6IDE5XzIwMH0sIGNhbl9mZDoge2FyYml0cmF0aW9uX2JpdHJhdGU6IDUwMF8wMDAsIGRhdGFfYml0cmF0ZTogMl8wMDBfMDAwfSxcbiAgICBldGhlcm5ldDoge2JpdHJhdGU6IDFfMDAwXzAwMF8wMDB9LFxuICB9KTtcbiAgY29uc3QgZXhjbHVkZWRTaWduYWxJZHMgPSBuZXcgU2V0KGFydGlmYWN0cy5hc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnRyYW5zcG9ydF9leGNsdXNpb25zXHJcbiAgICAuZmxhdE1hcCgoaXRlbTogeyBzaWduYWxfaWRzOiBzdHJpbmdbXSB9KSA9PiBpdGVtLnNpZ25hbF9pZHMpKTtcclxuICBleHBlY3QoZXhjbHVkZWRTaWduYWxJZHMuc2l6ZSkudG9CZSgyMzUpO1xyXG4gIGV4cGVjdChhcnRpZmFjdHMuYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQpLnRvQmUoMTE2OSk7XHJcbiAgYXdhaXQgdmVyaWZ5U2lnbmFsQ29udHJhY3RzKHBhZ2UsIHByb2plY3QsIGJhc2VsaW5lLnNpZ25hbHMpO1xyXG4gIGV4cGVjdChhcnRpZmFjdHMuam9iKS50b0JlKGNvbnRpbnVpdHkucmVzdGFydGVkSm9iSWQpO1xyXG4gIGV4cGVjdChlcnJvcnMpLnRvRXF1YWwoW10pO1xyXG4gIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgZml4dHVyZTogbWV0YWRhdGEucmVxdWVzdF9zaGEyNTYsIC4uLmNvbnRpbnVpdHksIC4uLmFydGlmYWN0cyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxufSk7XHJcblxyXG5mb3IgKGNvbnN0IHRhcmdldCBvZiBbXHJcbiAgeyBsYWJlbDogJ21vZGVsJywgdHlwZTogJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcsIHN0ZXA6ICdlbmdpbmVlcmluZ19tb2RlbCcgfSxcclxuICB7IGxhYmVsOiAncm91dGluZycsIHR5cGU6ICdXSVpBUkRfUk9VVElORycsIHN0ZXA6ICdyb3V0aW5nJyB9LFxyXG4gIHsgbGFiZWw6ICd0b3BvbG9neScsIHR5cGU6ICdXSVpBUkRfTkVUV09SS19UT1BPTE9HWScsIHN0ZXA6ICduZXR3b3JrX2VkaXRvcicgfSxcclxuXSkge1xyXG4gIHRlc3QoYGV4YWN0IGNvbmZpcm1lZCA1MC8yNTAvMjUwICR7dGFyZ2V0LmxhYmVsfSBwYXJhbWV0ZXIgcmV0dXJuIHJldmlldyBvbmx5IEBsYXJnZS1yZXR1cm5gLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgICBjb25zdCBlcnJvcnM6IHN0cmluZ1tdID0gW107IHBhZ2Uub24oJ3BhZ2VlcnJvcicsIGVycm9yID0+IGVycm9ycy5wdXNoKGVycm9yLm1lc3NhZ2UpKTtcclxuICAgIGNvbnN0IHByb2plY3QgPSBgbmlzLWUyZS1sYXJnZS1yZXR1cm4tJHt0YXJnZXQubGFiZWx9LWAgKyByYW5kb21VVUlEKCk7XHJcbiAgICBjb25zdCB7IHJ1bklkLCBtZXRhZGF0YSwgYmFzZWxpbmUgfSA9IGF3YWl0IHN0YXJ0Q2FwdHVyZWRMYXJnZVdpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICAgIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgZmFsc2UsIFtdLCBmYWxzZSwgYmFzZWxpbmUuc2lnbmFscyxcclxuICAgICAgdW5kZWZpbmVkLCBmYWxzZSwgYXN5bmMgKHByb3Bvc2FsSWQsIHByb3Bvc2FsVHlwZSkgPT4ge1xyXG4gICAgICAgIGlmIChwcm9wb3NhbFR5cGUgIT09IHRhcmdldC50eXBlKSByZXR1cm47XHJcbiAgICAgICAgYXdhaXQgcmVwZWF0UGFyYW1ldGVyUmV0dXJuKHBhZ2UsIHByb2plY3QsIHByb3Bvc2FsSWQsIGxhcmdlUGFyYW1ldGVyU2NlbmFyaW9zKCkpO1xyXG4gICAgICAgIHJldHVybiAnU1RPUF9BRlRFUl9SRVZJRVcnO1xyXG4gICAgICB9KTtcclxuICAgIGV4cGVjdChjb250aW51aXR5LnJ1bklkKS50b0JlKHJ1bklkKTtcclxuICAgIGV4cGVjdChjb250aW51aXR5LnJldmlld09ubHk/LnByb3Bvc2FsVHlwZSkudG9CZSh0YXJnZXQudHlwZSk7XHJcbiAgICBjb25zdCB3b3JrZmxvdyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uKS50b01hdGNoT2JqZWN0KHsgcnVuX2lkOiBydW5JZCwgc3RhdGU6ICdSRVZJRVdfUkVRVUlSRUQnLCBzdGVwOiB0YXJnZXQuc3RlcCB9KTtcclxuICAgIGV4cGVjdChkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlcy5zaW11bGF0aW9uKSkudG9CZShmYWxzZSk7XHJcbiAgICBjb25zdCBwcm9wb3NhbCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke2NvbnRpbnVpdHkucmV2aWV3T25seSEucHJvcG9zYWxJZH0/dmlldz1zdGF0dXNgKTtcclxuICAgIGV4cGVjdChwcm9wb3NhbC5kYXRhLnN0YXR1cykudG9CZSgnVkFMSURBVEVEJyk7XHJcbiAgICBleHBlY3QoZXJyb3JzKS50b0VxdWFsKFtdKTtcclxuICAgIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgncmV2aWV3LW9ubHktZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgZml4dHVyZTogbWV0YWRhdGEucmVxdWVzdF9zaGEyNTYsXHJcbiAgICAgIGNvdmVyYWdlOiAnUkVWSUVXX0NPTlRJTlVJVFlfT05MWScsIGN5Y2xlczogMywgdGVjaG5vbG9naWVzOiBbJ2xpbicsICdjYW5fZmQnLCAnZXRoZXJuZXQnXSwgLi4uY29udGludWl0eSB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICB9KTtcclxufVxyXG5cclxudGVzdCgnYSByZWFsIEFNRU5EIGFmdGVyIG1vZGVsIGFwcHJvdmFsIGFkZHMgdGhlIHJlcXVlc3RlZCBzZW5zb3IgYW5kIHJldXNlcyBpdHMgbmV0d29ya3MgQGFtZW5kJywgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1hbWVuZC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGF3YWl0IHJldmlld1ZpcnR1YWxUcmFuc3BvcnRzKHBhZ2UsIHByb2plY3QpO1xyXG4gIGNvbnN0IHJ1bklkID0gcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGdyYXBoID0gW1xyXG4gICAgeyBjbHVzdGVyX2lkOiAnZHJpdmUnLCBuZXR3b3JrX2lkOiAnY2FuX2ZkJywgbmV0d29ya19sYWJlbDogJ0NBTi1GRCcsIGJ1c19uYW1lOiAnRHJpdmUnLFxyXG4gICAgICBjb250cm9sbGVyczogW3sgZWN1OiAnTW90b3JzdGV1ZXJ1bmcnLCBzZW5zb3JzOiBbXSBhcyBzdHJpbmdbXSwgYWN0dWF0b3JzOiBbXSB9XSxcclxuICAgICAgaG1pX3JvdXRlczogW3sgc291cmNlOiAnTW90b3JzdGV1ZXJ1bmcnLCB0YXJnZXQ6ICdBbnplaWdlJyB9LCB7IHNvdXJjZTogJ0FuemVpZ2UnLCB0YXJnZXQ6ICdNb3RvcnN0ZXVlcnVuZycgfSxcclxuICAgICAgICB7IHNvdXJjZTogJ1N5c3RlbScsIHRhcmdldDogJ0FuemVpZ2UnIH1dIH0sXHJcbiAgICB7IGNsdXN0ZXJfaWQ6ICdkaXNwbGF5JywgbmV0d29ya19pZDogJ2V0aGVybmV0JywgbmV0d29ya19sYWJlbDogJ0V0aGVybmV0JywgYnVzX25hbWU6ICdEaXNwbGF5JyxcclxuICAgICAgY29udHJvbGxlcnM6IFt7IGVjdTogJ0FuemVpZ2UnLCBzZW5zb3JzOiBbXSBhcyBzdHJpbmdbXSwgYWN0dWF0b3JzOiBbXSB9XSB9LFxyXG4gIF07XHJcbiAgY29uc3QgcHJvbXB0ID0gYFN0cnVrdHVyaWVydGUgVm9yZ2FiZW4gZnVlciBkZW4gRW5naW5lZXJpbmctQWdlbnRlbjpcclxuLSBMYXVmLUlEOiAke3J1bklkfVxyXG4tIEluZHVzdHJpZTogQXV0b21vdGl2ZVxyXG4tIE5ldHp3ZXJrdGVjaG5vbG9naWVuOiBDQU4tRkQgKGNhbl9mZCk7IEV0aGVybmV0IChldGhlcm5ldClcclxuQ0FOLUZEOiA1MDAga2JpdC9zIGFyYml0cmF0aW9uLCAyIE1iaXQvcyBkYXRhXHJcbkNBTjogNTAwIGtiaXQvc1xyXG5FdGhlcm5ldDogMTAwIE1iaXQvc1xyXG4tIEhhcmR3YXJlLVNvbGx3ZXJ0ZToge1wiZ2F0ZXdheXNcIjoxLFwiZWN1c1wiOjIsXCJzZW5zb3JzXCI6MCxcImFjdHVhdG9yc1wiOjB9XHJcbi0gU3lzdGVtY2x1c3Rlci1HcmFwaDogJHtKU09OLnN0cmluZ2lmeShncmFwaCl9XHJcbktvbmtyZXRlIEF1ZmdhYmUgZGVzIE51dHplcnMsIHBlciBXaXphcmQtVWViZXJuZWhtZW4gYmVzdGFldGlndDpcclxuTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UgbWl0IGVpbmVtIHplbnRyYWxlbiBHYXRld2F5IFN5c3RlbSB2ZXJiaW5kZW4uYDtcclxuICBjb25zdCBzdGFydGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY2hhdCcsIHtcclxuICAgIGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSwgdGltZW91dDogMTIwXzAwMCxcclxuICAgIGRhdGE6IHsgcHJvbXB0LCB3aXphcmRfY29tbWFuZDogeyBhY3Rpb246ICdTVEFSVCcsIHJ1bl9pZDogcnVuSWQsIG9wZXJhdGlvbl9pZDogcmFuZG9tVVVJRCgpLFxyXG4gICAgICB0YXJnZXQ6ICdkYXRhX3NjaWVuY2VfaW50ZWxsaWdlbmNlJywgd2l6YXJkX2NvbnRleHQ6IHsgcHJvamVjdF9pZDogcHJvamVjdCwgcnVuX2lkOiBydW5JZCxcclxuICAgICAgICBwcm9qZWN0X25hbWU6ICdFMkUgYW1lbmRtZW50Jywgc2NvcGVfaWRzOiBzdGVwcywgbW9kZTogJ2Z1bGwnLFxyXG4gICAgICAgIHByb2Nlc3NfaWRzOiBbJ2RlZmF1bHRzJywgJ3Jldmlld19nYXRlJywgJ2FwcHJvdmVfYWZ0ZXJfYWxsb3cnXSwgdGFzazogJ01vdG9yc3RldWVydW5nIHVuZCBBbnplaWdlIGFuIFN5c3RlbScgfSB9IH0sXHJcbiAgfSk7XHJcbiAgaWYgKCFzdGFydGVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke3N0YXJ0ZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBzdGFydGVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBsZXQgb3JpZ2luYWxOZXR3b3Jrczogc3RyaW5nW10gPSBbXTtcclxuICBjb25zdCBhbWVuZCA9IGFzeW5jICgpID0+IHtcclxuICAgIG9yaWdpbmFsTmV0d29ya3MgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cnKSkucGFyYW1ldGVycy5uZXR3b3Jrc1xyXG4gICAgICAubWFwKChpdGVtOiB7IGlkOiBzdHJpbmcgfSkgPT4gaXRlbS5pZCkuc29ydCgpO1xyXG4gICAgZXhwZWN0KG9yaWdpbmFsTmV0d29ya3MpLnRvSGF2ZUxlbmd0aCgyKTtcclxuICAgIGdyYXBoWzBdLmNvbnRyb2xsZXJzWzBdLnNlbnNvcnMucHVzaCgnTW90b3JUZW1wZXJhdHVyZScpO1xyXG4gICAgY29uc3QgZGlhbG9nID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KTtcclxuICAgIGNvbnN0IGV4cGFuZCA9IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8OkbnplbicsIGV4YWN0OiB0cnVlIH0pO1xyXG4gICAgYXdhaXQgZXhwZWN0KGV4cGFuZCkudG9CZUVuYWJsZWQoeyB0aW1lb3V0OiAxMjBfMDAwIH0pO1xyXG4gICAgYXdhaXQgZXhwYW5kLmNsaWNrKCk7XHJcbiAgICBjb25zdCBmaWVsZCA9IGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSkuZ2V0QnlSb2xlKCd0ZXh0Ym94Jyk7XHJcbiAgICBhd2FpdCBmaWVsZC5maWxsKCdFcmfDpG56ZSBNb3RvclRlbXBlcmF0dXJlIGFscyBTZW5zb3IgZGVyIE1vdG9yc3RldWVydW5nLiBEaWUgdm9sbHN0w6RuZGlnZSBha3R1YWxpc2llcnRlIEZyZWlnYWJlIGxhdXRldDpcXG4nXHJcbiAgICAgICsgJy0gSGFyZHdhcmUtU29sbHdlcnRlOiB7XCJnYXRld2F5c1wiOjEsXCJlY3VzXCI6MixcInNlbnNvcnNcIjoxLFwiYWN0dWF0b3JzXCI6MH1cXG4nXHJcbiAgICAgICsgJy0gU3lzdGVtY2x1c3Rlci1HcmFwaDogJyArIEpTT04uc3RyaW5naWZ5KGdyYXBoKSk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdFcmfDpG56dW5nIGFuYWx5c2llcmVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGV4cGVjdChmaWVsZCkubm90LnRvQmVWaXNpYmxlKHsgdGltZW91dDogMTIwXzAwMCB9KTtcclxuICB9O1xyXG4gIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgZmFsc2UsIFsnTW90b3JzdGV1ZXJ1bmcnLCAnQW56ZWlnZSddLCBmYWxzZSwgdW5kZWZpbmVkLCBhbWVuZCk7XHJcbiAgY29uc3QgaGFyZHdhcmUgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gIGNvbnN0IG93bmVyID0gaGFyZHdhcmUuZmluZChpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ01vdG9yc3RldWVydW5nJyk7XHJcbiAgY29uc3Qgc2Vuc29ycyA9IGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ01vdG9yVGVtcGVyYXR1cmUnKTtcclxuICBleHBlY3Qoc2Vuc29ycykudG9IYXZlTGVuZ3RoKDEpO1xyXG4gIGV4cGVjdChzZW5zb3JzWzBdLmlkZW50aXR5LnN5c3RlbV9vd25lcl9pZCkudG9CZShvd25lci5pZCk7XHJcbiAgY29uc3Qgc2Vuc29yTmV0d29yayA9ICdEcml2ZS1JTy1tb3RvcnN0ZXVlcnVuZy1jYW4tZmQtUzAxJztcclxuICBjb25zdCBuZXR3b3JrcyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpKS5wYXJhbWV0ZXJzLm5ldHdvcmtzO1xyXG4gIGV4cGVjdChuZXR3b3Jrcy5tYXAoKGl0ZW06IHsgaWQ6IHN0cmluZyB9KSA9PiBpdGVtLmlkKS5zb3J0KCkpLnRvRXF1YWwoWy4uLm9yaWdpbmFsTmV0d29ya3MsIHNlbnNvck5ldHdvcmtdLnNvcnQoKSk7XHJcbiAgZXhwZWN0KG5ldyBTZXQobmV0d29ya3MubWFwKChpdGVtOiB7IG5hbWU6IHN0cmluZyB9KSA9PiBpdGVtLm5hbWUpKS5zaXplKS50b0JlKG5ldHdvcmtzLmxlbmd0aCk7XHJcbiAgY29uc3QgdG9wb2xvZ3kgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvbmV0d29yay12aWV3JykpLnRvcG9sb2d5O1xyXG4gIGNvbnN0IGxvY2FsRWRnZSA9IHRvcG9sb2d5LmVkZ2VzLmZpbmQoKGVkZ2U6IGFueSkgPT4gZWRnZS5waHlzaWNhbE5ldHdvcmtJZCA9PT0gc2Vuc29yTmV0d29yayk7XHJcbiAgZXhwZWN0KGxvY2FsRWRnZSkudG9CZVRydXRoeSgpO1xyXG4gIGV4cGVjdChsb2NhbEVkZ2UuYnVzKS50b0JlKCdjYW5fZmQnKTtcclxuICBleHBlY3QoT2JqZWN0LnZhbHVlcyhsb2NhbEVkZ2Uucm91dGluZ01ldGFkYXRhKSkudG9Db250YWluRXF1YWwoZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoe1xyXG4gICAgc291cmNlOiBzZW5zb3JzWzBdLmlkLCB0YXJnZXQ6IG93bmVyLmlkLCBhcHByb3ZhbFN0YXRlOiAnQVBQUk9WRUQnLCBwcm90b2NvbDogJ0NBTl9GRCcsXHJcbiAgfSkpO1xyXG4gIGZvciAoY29uc3QgW3NpZGUsIGhhcmR3YXJlSWRdIG9mIFtbJ3NvdXJjZScsIHNlbnNvcnNbMF0uaWRdLCBbJ3RhcmdldCcsIG93bmVyLmlkXV0pIHtcclxuICAgIGNvbnN0IG5vZGUgPSB0b3BvbG9neS5ub2Rlcy5maW5kKChpdGVtOiBhbnkpID0+IGl0ZW0uaWQgPT09IGxvY2FsRWRnZVtzaWRlXSk7XHJcbiAgICBleHBlY3Qobm9kZS5lbmdpbmVlcmluZ0lkKS50b0JlKGhhcmR3YXJlSWQpO1xyXG4gICAgZXhwZWN0KG5vZGUucG9ydHMpLnRvQ29udGFpbkVxdWFsKGV4cGVjdC5vYmplY3RDb250YWluaW5nKHsgaWQ6IGxvY2FsRWRnZVtzaWRlICsgJ1BvcnQnXSxcclxuICAgICAgYnVzOiAnY2FuX2ZkJywgcGh5c2ljYWxOZXR3b3JrSWQ6IHNlbnNvck5ldHdvcmsgfSkpO1xyXG4gIH1cclxuICBjb25zdCBhcnRpZmFjdHMgPSBhd2FpdCB2ZXJpZnlBcnRpZmFjdHMocGFnZSwgcHJvamVjdCwgMSk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdhbWVuZG1lbnQtZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgLi4uY29udGludWl0eSwgLi4uYXJ0aWZhY3RzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuXHJcbi8vIFJlYWwgaXNvbGF0ZWQgVUkgLT4gcGVyc2lzdGVkIG1vZGVsIGJvdW5kYXJ5IHJlZ3Jlc3Npb24sIG5vdCBuaW5lLXN0YWdlIGNvbXBsZXRpb24gcHJvb2YuXHJcbnRlc3QoJ3Jldmlld2FibGUgZnVuY3Rpb25hbCBUWC9SWCBPRkYgc3Vydml2ZXMgcmVxdWVzdCByZWxvYWQgYW5kIGNhbm9uaWNhbCBtb2RlbCBhZG9wdGlvbiBAdHhyeCcsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtdHhyeC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjZW5naW5lZXJpbmctcHJvamVjdC1uYW1lJykuZmlsbCgnVFggUlggZnVuY3Rpb25hbCBwYXJ0bmVycycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdQcm9qZWt0YmVzY2hyZWlidW5nJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKCdFcnpldWdlIGVpbiBBdXRvbW90aXZlIENBTi1GRCBOZXR6d2VyayBtaXQgZWluZW0gR2F0ZXdheSBTeXN0ZW0gdW5kIGRlbiBFQ1VzIE1vdG9yc3RldWVydW5nLCBHZXRyaWViZXN0ZXVlcnVuZyB1bmQgRWxla3Ryb21vdG9yc3RldWVydW5nLiBEaWUgYmVyZWNobmV0ZW4gRnVua3Rpb25zYXVzZ8OkbmdlIGRpZW5lbiBkZXIgQW50cmllYnNrb29yZGluYXRpb24uIENvbnRyb2xsZXJzdGF0dXMgYmxlaWJ0IGludGVybi5cXG5DQU4tRkQ6IDUwMCBrYml0L3MgYXJiaXRyYXRpb24sIDIgTWJpdC9zIGRhdGEnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnR2Vyw6R0ZXVtZmFuZycsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBdXRvbW90aXZlIC8gVmVoaWNsZSDDvGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgZm9yIChjb25zdCBbbGFiZWwsIHZhbHVlXSBvZiBbWydHYXRld2F5cycsICcxJ10sIFsnQ29udHJvbGxlcicsICczJ10sIFsnU2Vuc29yZW4nLCAnMCddLCBbJ0FrdG9yZW4nLCAnMCddXSkgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoYCR7bGFiZWx9OiB2ZXJiaW5kbGljaGUgQW56YWhsYCwgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHZhbHVlKTtcclxuICBjb25zdCB0eHJ4ID0gZGlhbG9nLmxvY2F0b3IoJ2RldGFpbHMnKS5maWx0ZXIoeyBoYXM6IHBhZ2UubG9jYXRvcignc3VtbWFyeScpLmZpbHRlcih7IGhhc1RleHQ6IC9eVFhcXC9SWC8gfSkgfSkuZmlyc3QoKTtcclxuICBhd2FpdCBleHBlY3QodHhyeCkudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCB0eHJ4LmxvY2F0b3IoJ3N1bW1hcnknKS5jbGljaygpO1xyXG4gIGNvbnN0IHNlbGVjdGVkID0gdHhyeC5nZXRCeVJvbGUoJ3N3aXRjaCcsIHsgbmFtZTogJ01vdG9yRHJlaG1vbWVudElzdCDihpIgR2V0cmllYmVzdGV1ZXJ1bmcnLCBleGFjdDogdHJ1ZSB9KTtcclxuICBhd2FpdCBleHBlY3Qoc2VsZWN0ZWQpLnRvQmVDaGVja2VkKCk7IGF3YWl0IHNlbGVjdGVkLnVuY2hlY2soKTtcclxuICBjb25zdCBzdGFydFJlcXVlc3QgPSBwYWdlLndhaXRGb3JSZXF1ZXN0KHJlcXVlc3QgPT4gcmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JykgJiYgcmVxdWVzdC5tZXRob2QoKSA9PT0gJ1BPU1QnICYmIHJlcXVlc3QucG9zdERhdGFKU09OKCk/LndpemFyZF9jb21tYW5kPy5hY3Rpb24gPT09ICdTVEFSVCcpO1xyXG4gIGZvciAobGV0IHN0ZXAgPSAwOyBzdGVwIDwgMTA7IHN0ZXArKykge1xyXG4gICAgY29uc3QgYnV0dG9uID0gZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKTtcclxuICAgIGF3YWl0IGV4cGVjdChidXR0b24pLnRvQmVFbmFibGVkKCk7IGNvbnN0IGxhYmVsID0gYXdhaXQgYnV0dG9uLmlubmVyVGV4dCgpOyBhd2FpdCBidXR0b24uY2xpY2soKTtcclxuICAgIGlmIChsYWJlbCA9PT0gJ8OcYmVybmVobWVuJyB8fCBsYWJlbCA9PT0gJ0F1ZnRyYWcgc3RhcnRlbicpIGJyZWFrO1xyXG4gIH1cclxuICBjb25zdCBjb250ZXh0ID0gKGF3YWl0IHN0YXJ0UmVxdWVzdCkucG9zdERhdGFKU09OKCkud2l6YXJkX2NvbW1hbmQud2l6YXJkX2NvbnRleHQ7XHJcbiAgY29uc3Qgc3VibWl0dGVkID0gY29udGV4dC5zeXN0ZW1fY2x1c3Rlcl9hc3NpZ25tZW50cy5mbGF0TWFwKChjbHVzdGVyOiBhbnkpID0+IGNsdXN0ZXIuZnVuY3Rpb25hbF9yb3V0ZXMgPz8gW10pO1xyXG4gIGNvbnN0IG9mZiA9IHN1Ym1pdHRlZC5maW5kKChyb3V0ZTogYW55KSA9PiByb3V0ZS5zb3VyY2UgPT09ICdNb3RvcnN0ZXVlcnVuZycgJiYgcm91dGUudGFyZ2V0ID09PSAnR2V0cmllYmVzdGV1ZXJ1bmcnKTtcclxuICBleHBlY3Qob2ZmLnNpZ25hbHMpLnRvRXF1YWwoW10pOyBleHBlY3Qob2ZmLmV4Y2x1ZGVkX3NpZ25hbHMpLnRvRXF1YWwoWydNb3RvckRyZWhtb21lbnRJc3QnXSk7XHJcbiAgbGV0IHByb3Bvc2FsOiBhbnk7XHJcbiAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XHJcbiAgICBpZiAoIWNvbnZlcnNhdGlvbi5kYXRhLmFjdGl2ZV9wcm9wb3NhbCkgcmV0dXJuIGZhbHNlO1xyXG4gICAgcHJvcG9zYWwgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7Y29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsfWApKS5kYXRhO1xyXG4gICAgcmV0dXJuIHByb3Bvc2FsLnByb3Bvc2FsX3R5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnO1xyXG4gIH0sIHsgdGltZW91dDogMTgwXzAwMCB9KS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgY29uc3QgZmluZGluZ3MgPSBwcm9wb3NhbC52YWxpZGF0aW9uX3Jlc3VsdC5maW5kaW5ncy5maWx0ZXIoKGl0ZW06IGFueSkgPT4gaXRlbS5jb2RlID09PSAnQ0FQQUNJVFlfVU5WRVJJRklFRCcpO1xyXG4gIGlmIChmaW5kaW5ncy5sZW5ndGgpIHtcclxuICAgIGNvbnN0IHJldmlldyA9IHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdQcsO8ZmJlZnVuZGUgZGVzIFZvcnNjaGxhZ3MnIH0pO1xyXG4gICAgYXdhaXQgZXhwZWN0KHJldmlldykudG9Db250YWluVGV4dChgJHtwcm9wb3NhbC52YWxpZGF0aW9uX3Jlc3VsdC5maW5kaW5ncy5sZW5ndGh9IFByw7xmYmVmdW5kZWApO1xyXG4gICAgYXdhaXQgZXhwZWN0KHJldmlldy5nZXRCeVJvbGUoJ2xpbmsnLCB7IG5hbWU6ICdUZWNobm9sb2dpZXBhcmFtZXRlciBiZWFyYmVpdGVuIHVuZCBiZXN0w6R0aWdlbicgfSkuZmlyc3QoKSkudG9IYXZlQXR0cmlidXRlKCdocmVmJywgbmV3IFJlZ0V4cChgcHJvamVjdD0ke3Byb2plY3R9YCkpO1xyXG4gICAgYXdhaXQgcmV2aWV3LmxvY2F0b3IoJ3N1bW1hcnknKS5maXJzdCgpLmNsaWNrKCk7IGF3YWl0IGV4cGVjdChyZXZpZXcuZ2V0QnlSb2xlKCduYXZpZ2F0aW9uJywgeyBuYW1lOiAnQmVmdW5kZSBkdXJjaGJsw6R0dGVybicgfSkuZmlyc3QoKSkudG9CZVZpc2libGUoKTtcclxuICB9XHJcbiAgY29uc3QgYXBwbHkgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5pbmNsdWRlcyhgL3Byb3Bvc2Fscy8ke3Byb3Bvc2FsLnByb3Bvc2FsX2lkfS9hcHByb3ZlLWFwcGx5YCkgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdGcmVpZ2ViZW4sIMO8YmVybmVobWVuICYgZm9ydGZhaHJlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7IGV4cGVjdCgoYXdhaXQgYXBwbHkpLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgY29uc3Qgbm9kZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gIGNvbnN0IG1lc3NhZ2VzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnbWVzc2FnZXMnKTsgY29uc3Qgc2lnbmFscyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ3NpZ25hbHMnKTtcclxuICBjb25zdCBzaWduYWwgPSBzaWduYWxzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdNb3RvckRyZWhtb21lbnRJc3QnKTsgZXhwZWN0KHNpZ25hbCkudG9CZVRydXRoeSgpO1xyXG4gIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKGl0ZW0gPT4gaXRlbS5pZCA9PT0gc2lnbmFsLm1lc3NhZ2VfaWQpO1xyXG4gIGNvbnN0IGdlYXJib3ggPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnR2V0cmllYmVzdGV1ZXJ1bmcnKTtcclxuICBjb25zdCBlbW90b3IgPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnRWxla3Ryb21vdG9yc3RldWVydW5nJyk7XHJcbiAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LnNjb3BlKS50b0JlKCdGVU5DVElPTl9PVVRQVVQnKTtcclxuICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QuY29uc3VtZXJfcmVmcykubm90LnRvQ29udGFpbihnZWFyYm94LmlkKTtcclxuICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QuY29uc3VtZXJfcmVmcykudG9Db250YWluKGVtb3Rvci5pZCk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdmdW5jdGlvbmFsLXR4cngtZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgb2ZmLCBtZXNzYWdlIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuIl0sIm1hcHBpbmdzIjoiQUFBQSxTQUFTQSxJQUFJLEVBQUVDLE1BQU0sUUFBbUIsaUJBQWlCO0FBQ3pELFNBQVNDLFFBQVEsUUFBUSxrQkFBa0I7QUFDM0MsU0FBU0MsVUFBVSxRQUFRLGFBQWE7QUFDeEMsU0FBU0MsWUFBWSxRQUFRLG9CQUFvQjtBQUNqRCxTQUFTQyxzQkFBc0IsRUFBRUMsWUFBWSxFQUFFQyxXQUFXLFFBQVEsb0NBQW9DO0FBQ3RHLFNBQVNDLHVCQUF1QixRQUFRLHFDQUFxQztBQUU3RSxNQUFNQyxLQUFLLEdBQUdILFlBQVk7QUFDMUIsTUFBTUksSUFBSSxHQUFHSCxXQUFXO0FBRXhCLE1BQU1JLFlBQVksR0FBRyxJQUFJQyxHQUFHLENBQXdCLENBQUM7QUFDckQsTUFBTUMsb0JBQW9CLEdBQUcsSUFBSUMsT0FBTyxDQUFpQixDQUFDO0FBQzFELE1BQU1DLGtCQUFrQixHQUFHLElBQUlILEdBQUcsQ0FBb0IsQ0FBQztBQUV2RFosSUFBSSxDQUFDZ0IsVUFBVSxDQUFDLE9B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