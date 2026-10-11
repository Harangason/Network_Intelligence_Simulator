// 0031d4fae0c668257f534e182d0140619d87b05b
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
async function repeatParameterReturn(page, project, proposalId, scenarios) {
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
    for (const [cycle, seed] of [41, 43, 42].entries()) {
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
    if (beforeProposalReview) await beforeProposalReview(proposalId, candidate.data.proposal_type);
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
test('exact confirmed 50/250/250 request completes through real wizard review @large', async ({
  page
}, testInfo) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const project = 'nis-e2e-large-' + randomUUID();
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
  const parameterReturnReviews = [];
  const continuity = await completeThroughWizard(page, project, false, [], true, baseline.signals, undefined, false, async (proposalId, proposalType) => {
    if (!['WIZARD_ENGINEERING_MODEL', 'WIZARD_ROUTING', 'WIZARD_NETWORK_TOPOLOGY'].includes(proposalType)) return;
    await repeatParameterReturn(page, project, proposalId, [{
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
    }]);
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
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmVhZEZpbGUiLCJyYW5kb21VVUlEIiwiZXhlY0ZpbGVTeW5jIiwiV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyIsIldJWkFSRF9TVEVQUyIsIldJWkFSRF9ET05FIiwicmV2aWV3VmlydHVhbFRyYW5zcG9ydHMiLCJzdGVwcyIsImRvbmUiLCJ3cml0ZVRpbWluZ3MiLCJNYXAiLCJ3b3JrZmxvd1BhZ2VGYWlsdXJlcyIsIldlYWtNYXAiLCJwcm9ncmVzc01pbGVzdG9uZXMiLCJiZWZvcmVFYWNoIiwicGFnZSIsImluZm8iLCJyb3dzIiwic2V0IiwidGVzdElkIiwicmVxdWVzdHMiLCJvbiIsInJlcXVlc3QiLCJpbmNsdWRlcyIsIm1ldGhvZCIsInJvdyIsInVybCIsInN0YXJ0ZWQiLCJEYXRlIiwibm93IiwicHVzaCIsInJlc3BvbnNlIiwiZ2V0Iiwic3RhdHVzIiwiVVJMIiwicGF0aG5hbWUiLCJkdXJhdGlvbl9tcyIsIl9yZXF1ZXN0JGZhaWx1cmUiLCJmYWlsdXJlIiwiZXJyb3JUZXh0IiwiYWZ0ZXJFYWNoIiwiYXR0YWNoIiwiYm9keSIsIkpTT04iLCJzdHJpbmdpZnkiLCJjb250ZW50VHlwZSIsImRlbGV0ZSIsInRvRXF1YWwiLCJnZXRCeVJvbGUiLCJuYW1lIiwiZXhhY3QiLCJub3QiLCJ0b0JlVmlzaWJsZSIsImFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkiLCJnZXRCeVRleHQiLCJpc1Zpc2libGUiLCJ0b0JlIiwicmVhZFByb2plY3QiLCJwcm9qZWN0IiwicGF0aCIsInJlc3VsdCIsImhlYWRlcnMiLCJ0aW1lb3V0Iiwib2siLCJFcnJvciIsInRleHQiLCJzbGljZSIsImpzb24iLCJkaXNwb3NlIiwicmVhZFdhcm5pbmdSZXZpZXdTdGF0ZSIsIl92ZXJpZmllZCRjb250ZXh0JGFnZTIiLCJfdmVyaWZpZWQkY29udGV4dCRhZ2UzIiwiYXV0aG9yaXR5IiwicGFyYW1ldGVycyIsInZlcmlmaWVkIiwicHJvamVjdF9pZCIsImZpZWxkIiwiX3ZlcmlmaWVkJGNvbnRleHQkYWdlIiwiX2F1dGhvcml0eSRjb250ZXh0JGFnIiwiY29udGV4dCIsImFnZW50X2V4ZWN1dGlvbiIsInN0YXR1c2VzIiwicnVuX2lkIiwicmVxdWVzdF9yZXZpc2lvbiIsInByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsIiwib3BlbldpemFyZCIsImdvdG8iLCJ3YWl0VW50aWwiLCJkaWFsb2ciLCJzdGVwIiwibG9jYXRvciIsInN0ZXBXaWR0aCIsImV2YWx1YXRlIiwiZWxlbWVudCIsImdldEJvdW5kaW5nQ2xpZW50UmVjdCIsIndpZHRoIiwiY2FyZHMiLCJhbGwiLCJ0b0hhdmVMZW5ndGgiLCJjYXJkIiwidG9CZUdyZWF0ZXJUaGFuIiwiYWxsT2JqZWN0cyIsInJlc291cmNlIiwiaXRlbXMiLCJvZmZzZXQiLCJsZW5ndGgiLCJyZXN0YXJ0QXBwbGljYXRpb24iLCJjcmFzaCIsImNvbnRhaW5lciIsInByb2Nlc3MiLCJlbnYiLCJOSVNfRTJFX0FQUF9DT05UQUlORVIiLCJ0b01hdGNoIiwiZG9ja2VyIiwiTklTX1RFU1RfRE9DS0VSIiwibGFiZWwiLCJlbmNvZGluZyIsInRyaW0iLCJwb2xsIiwidmVyaWZ5U2lnbmFsQ29udHJhY3RzIiwiZXhwZWN0ZWQiLCJoYXJkd2FyZSIsImZ1bmN0aW9ucyIsIm1lc3NhZ2VzIiwic2lnbmFscyIsIlByb21pc2UiLCJtYXAiLCJub2RlcyIsIml0ZW0iLCJpZCIsImZ1bmN0aW9uc0J5SWQiLCJtZXNzYWdlc0J5SWQiLCJjb250cmFjdHMiLCJzaWduYWwiLCJfcmVmIiwiX3NpZ25hbCRkYXRhJGVudW1fdmFsIiwiX3NpZ25hbCRkYXRhIiwiX3NpZ25hbCRzZW1hbnRpYyRzZW1hIiwiX3NpZ25hbCRzZW1hbnRpYyIsIl9zaWduYWwkY29uZmlndXJhdGlvbiIsIl9zaWduYWwkY29uZmlndXJhdGlvbjIiLCJtZXNzYWdlIiwibWVzc2FnZV9pZCIsInRvQmVUcnV0aHkiLCJyZWZlcmVuY2UiLCJjb25maWd1cmF0aW9uIiwiY29tbXVuaWNhdGlvbl9jb250cmFjdCIsInByb2R1Y2VyX3JlZiIsImZuIiwib3duZXIiLCJoYXJkd2FyZV9ub2RlX2lkIiwicHJvZHVjZXIiLCJkZXZpY2VfdHlwZSIsImtleSIsImpvaW4iLCJ0b0JlVW5kZWZpbmVkIiwiT2JqZWN0IiwiZnJvbUVudHJpZXMiLCJfc2lnbmFsJGZpZWxkIiwiZW51bV92YWx1ZXMiLCJkYXRhIiwic2VtYW50aWNfdHlwZSIsInNlbWFudGljIiwiZ2VuZXJhdGlvbl9yb2xlIiwidmVyaWZ5QXJ0aWZhY3RzIiwibWluaW11bUNhbm9uaWNhbFNpZ25hbHMiLCJpbnRlcm5hbENvbnRyb2xsZXIiLCJleHBlY3RlZFBhcmFtZXRlcnMiLCJleHBlY3RlZE5hdGl2ZVJhdGVzIiwiX2Fzc2Vzc21lbnQkc2NvcGVfY292Iiwid29ya2Zsb3ciLCJqb2JMaXN0Iiwic25hcHNob3RzIiwia2V5cyIsInNvcnQiLCJoYXMiLCJqb2JzIiwic25hcHNob3QiLCJzaW11bGF0aW9ucyIsImZpbmQiLCJqb2JfaWQiLCJmdWxsIiwiZGF0YV9iaXRyYXRlIiwiY2FuX2ZkX2RhdGFfcHJlc2NhbGVyIiwicnVudGltZVBhcmFtZXRlcnMiLCJ0b01hdGNoT2JqZWN0IiwiY2FuRmROZXR3b3JrcyIsIm5ldHdvcmtzIiwiZmlsdGVyIiwibmV0d29yayIsInRlY2hub2xvZ3kiLCJyYXRlcyIsImVudHJpZXMiLCJhc3Nlc3NtZW50Iiwic2NvcGVfY292ZXJhZ2UiLCJzY29wZV9tb2RlIiwiY29tcGxldGUiLCJjb25mb3JtYW5jZSIsImZhaWxlZF9yb3V0ZV9jb3VudCIsInRvQmVHcmVhdGVyVGhhbk9yRXF1YWwiLCJleGNsdWRlZCIsInRyYW5zcG9ydF9leGNsdXNpb25zIiwicm91dGluZyIsImVuYWJsZWQiLCJjb250cmFjdCIsImNvbnN1bWVyX3JlZnMiLCJyZWFzb25fY29kZSIsInJvbGUiLCJjb250cm9sbGVyIiwic2NvcGUiLCJleGNsdWRlZFNpZ25hbHMiLCJTZXQiLCJmbGF0TWFwIiwic2lnbmFsX2lkcyIsIm9ic2VydmVkX3NpZ25hbF9jb3VudCIsInNpemUiLCJ0cmFjZSIsImNvdW50IiwiZXZlbnRzIiwic29tZSIsImpvYiIsInBhcmFtZXRlcl9wcm9vZiIsInNhdmVkIiwic2ltdWxhdGlvbl9yYXRlcyIsImJpdHJhdGUiLCJhcmJpdHJhdGlvbl9iaXRyYXRlIiwiaGFyZHdhcmVfZXZpZGVuY2UiLCJ1bmRlZmluZWQiLCJyZXBlYXRQYXJhbWV0ZXJSZXR1cm4iLCJwcm9wb3NhbElkIiwic2NlbmFyaW9zIiwiYmVmb3JlIiwiaWRlbnRpdHkiLCJub2RlSWRzIiwic3RhcnRzIiwidHJhY2tTdGFydHMiLCJfcmVxdWVzdCRwb3N0RGF0YUpTT04iLCJlbmRzV2l0aCIsInBvc3REYXRhSlNPTiIsIndpemFyZF9jb21tYW5kIiwiYWN0aW9uIiwiZXZpZGVuY2UiLCJ3aXphcmQiLCJjbGljayIsImN5Y2xlIiwic2VlZCIsInNjZW5hcmlvIiwiX3NhdmVkJHBhcmFtZXRlcnMkc2ltIiwiZW5jb2RlVVJJQ29tcG9uZW50IiwiY29tbW9uIiwidmFsdWUiLCJmaWVsZHMiLCJfc2NlbmFyaW8kZWRpdEZpZWxkcyIsImlucHV0IiwiZGV0YWlscyIsImdldEF0dHJpYnV0ZSIsImVkaXRGaWVsZHMiLCJmaWxsIiwidG9IYXZlVmFsdWUiLCJTdHJpbmciLCJzY29wZWQiLCJ0ZWNobm9sb2d5X3BhcmFtZXRlcnMiLCJhc3N1bWVkIiwic2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnMiLCJ2YWx1ZXMiLCJuYXRpdmVWYWx1ZXMiLCJuYXRpdmUiLCJjb25maXJtZWQiLCJoYXNPd24iLCJwcm92ZW5hbmNlIiwic291cmNlIiwidXNlclZhbHVlcyIsInZhbHVlX29yaWdpbiIsInRlY2hub2xvZ3lfZGVmYXVsdHMiLCJzdGFsZSIsImNhbm9uaWNhbElkcyIsImNhbm9uaWNhbF9pZHMiLCJyZWxvYWQiLCJyZXN1bWVSZXN0b3JlIiwicmVzdG9yZVBhdXNlIiwicmVzb2x2ZSIsImRlbGF5UmVzdG9yZSIsInJvdXRlIiwiY29udGludWUiLCJkZWxheWVkIiwidG9Db250YWluVGV4dCIsInVucm91dGVBbGwiLCJiZWhhdmlvciIsInJlc3RvcmVkIiwic3RhdGUiLCJjb252ZXJzYXRpb24iLCJhY3RpdmVfcHJvcG9zYWwiLCJmcmVzaCIsImFmdGVyIiwicHJvcG9zYWxfaWQiLCJzYXZlZF92YWx1ZXMiLCJhc3N1bXB0aW9ucyIsInJlc3RvcmVkX3N0YXR1cyIsIm9mZiIsImNvbXBsZXRlVGhyb3VnaFdpemFyZCIsInJlc3RhcnQiLCJleHBlY3RlZEhhcmR3YXJlIiwiY3Jhc2hTaW11bGF0aW9uIiwiZXhwZWN0ZWRTaWduYWxzIiwiYWZ0ZXJGaXJzdE1vZGVsQXBwbGllZCIsInN0b3BPbkV2aWRlbmNlQmxvY2siLCJiZWZvcmVQcm9wb3NhbFJldmlldyIsInJldmlld0NvdW50IiwicnVuSWQiLCJyZXZpZXdlZCIsInJlc3RhcnRlZEpvYklkIiwid2F0Y2hkb2ciLCJwZXJmb3JtYW5jZSIsImNoZWNrcG9pbnQiLCJfd29ya2Zsb3ckY29udGV4dCRhZ2UiLCJfd29ya2Zsb3ckY29udGV4dCRhZ2UyIiwiX2V4ZWN1dGlvbiRibG9ja2luZ19mIiwiX2V4ZWN1dGlvbiRtZXNzYWdlIiwicmVhZHlWZXJzaW9uIiwicmVhZHlTaW5jZSIsImlzQ2hlY2twb2ludCIsInJlbWFpbmluZyIsInByb2dyZXNzIiwib2JzZXJ2ZSIsImFkdmFuY2VkIiwiYXQiLCJ0b0lTT1N0cmluZyIsImZyb250aWVyIiwiY29tcGxldGVkVGhyb3VnaCIsImV4ZWN1dGlvbiIsInZhbGlkYXRpb24iLCJydW5uaW5nIiwiZXZlcnkiLCJCb29sZWFuIiwicmVjb3ZlcmFibGUiLCJ1cGRhdGVkX2F0IiwiYnV0dG9uIiwiZXZhbHVhdGVBbGwiLCJidXR0b25zIiwiZGlzYWJsZWQiLCJnZXRDbGllbnRSZWN0cyIsImdldENvbXB1dGVkU3R5bGUiLCJ2aXNpYmlsaXR5IiwiYXR0ZW1wdCIsIndhaXRGb3JUaW1lb3V0IiwiTWF0aCIsIm1pbiIsImJsb2NraW5nX2ZpbmRpbmdzIiwiYmVmb3JlUmV2aWV3IiwicHJlZmxpZ2h0Iiwid2FybmluZ3MiLCJmaXJzdCIsInN0YXJ0ZWRXYWxsIiwiYXBwcm92YWxSZXNwb25zZSIsIndhaXRGb3JSZXNwb25zZSIsImFwcHJvdmVkIiwicmVjZWlwdCIsImFmdGVyUmV2aWV3IiwicHJvb2YiLCJzbmFwc2hvdElkIiwicmVxdWVzdFByb2plY3QiLCJzdWJtaXR0ZWQiLCJmaW5pc2hlZFdhbGwiLCJjb21taXR0ZWRBdCIsImNvbW1pdHRlZCIsImNvbW1pdFdhcm5pbmdSZXZpZXciLCJtYW51YWxXYXJuaW5nQXBwcm92YWwiLCJhcHByb3ZhbElkZW50aXR5IiwiYXBwcm92YWwiLCJfYXdhaXQkcmVhZFByb2plY3QkY28iLCJfY29udmVyc2F0aW9uJGRhdGEiLCJfcHJvcG9zYWwkZGF0YSIsInByb3Bvc2FsIiwidmFsaWRhdGlvbl9yZXN1bHQiLCJ2aXNpYmxlIiwiaW5uZXJUZXh0IiwiZXJyb3IiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQiLCJsYXRlc3QiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQyIiwiX2xhdGVzdCRjb250ZXh0JGFnZW50MyIsIl9sYXRlc3Qkc3RhdHVzZXMiLCJjYW5kaWRhdGUiLCJwcm9wb3NhbF90eXBlIiwiY2hhbmdlcyIsImNoYW5nZSIsIm9iamVjdF90eXBlIiwiYXJyYXlDb250YWluaW5nIiwiYXBwbHlSZXNwb25zZSIsInRvQmVFbmFibGVkIiwiYXBwbGllZCIsImFkZCIsIl9hbWVuZGVkJGNvbnRleHQkYWdlbiIsImFtZW5kZWQiLCJfY3VycmVudCRjb250ZXh0JGFnZW4iLCJjdXJyZW50IiwiZnVsZmlsbCIsImdldEJ5VGl0bGUiLCJnZXRCeUxhYmVsIiwidG9CZURpc2FibGVkIiwidW5yb3V0ZSIsInRvSGF2ZUNvdW50IiwiY2F0YWxvZyIsInRlY2hub2xvZ3lfY291bnQiLCJ0ZXN0SW5mbyIsImVycm9ycyIsInN0YXJ0UmVxdWVzdCIsIndhaXRGb3JSZXF1ZXN0IiwiX3JlcXVlc3QkcG9zdERhdGFKU09OMiIsInN1Ym1pdCIsInJlcXVlc3RlZCIsIndpemFyZF9jb250ZXh0IiwidGVjaG5vbG9naWVzIiwiX2F3YWl0JHJlYWRQcm9qZWN0JGNvMiIsInBlbmRpbmciLCJjb250aW51aXR5IiwiYXJ0aWZhY3RzIiwiZmluaXNoZWQiLCJjaGVjayIsInNlbGVjdE9wdGlvbiIsInJlamVjdHMiLCJ0b1Rocm93IiwiZmluZGluZ3MiLCJjb2RlIiwidG9Db250YWluIiwiYXJ0aWZhY3RfY2hlY2tzIiwicmVxdWlyZWQiLCJwcm9maWxlX3ZhbHVlcyIsImRldmljZVNvdXJjZSIsInRvSGF2ZVByb3BlcnR5IiwibmF0aXZlVGVjaG5vbG9neSIsInByb2ZpbGVfZmluZGluZ3MiLCJmaW5kaW5nIiwiZXZpZGVuY2VSZXZpZXciLCJ0b0hhdmVBdHRyaWJ1dGUiLCJSZWdFeHAiLCJzaW11bGF0aW9uIiwicmF0ZV9yZXZpZXdfcHJvcG9zYWxzIiwiaTJjIiwicGFyYW1ldGVyX3Byb3ZlbmFuY2UiLCJpbnRlcmZhY2VzIiwiZG9tYWluIiwidW5pdCIsIm9yaWdpbmFsIiwiaW1wb3J0IiwibWV0YSIsIm1ldGFkYXRhIiwicGFyc2UiLCJiYXNlbGluZSIsInByb21wdCIsInJlcGxhY2UiLCJwb3N0Iiwib3BlcmF0aW9uX2lkIiwidGFyZ2V0IiwicGFyYW1ldGVyUmV0dXJuUmV2aWV3cyIsInByb3Bvc2FsVHlwZSIsImxpbl9iaXRyYXRlX2JwcyIsImxpbiIsImNhbl9mZCIsImV0aGVybmV0IiwiZXhjbHVkZWRTaWduYWxJZHMiLCJmaXh0dXJlIiwicmVxdWVzdF9zaGEyNTYiLCJncmFwaCIsImNsdXN0ZXJfaWQiLCJuZXR3b3JrX2lkIiwibmV0d29ya19sYWJlbCIsImJ1c19uYW1lIiwiY29udHJvbGxlcnMiLCJlY3UiLCJzZW5zb3JzIiwiYWN0dWF0b3JzIiwiaG1pX3JvdXRlcyIsInByb2plY3RfbmFtZSIsInNjb3BlX2lkcyIsIm1vZGUiLCJwcm9jZXNzX2lkcyIsInRhc2siLCJvcmlnaW5hbE5ldHdvcmtzIiwiYW1lbmQiLCJleHBhbmQiLCJzeXN0ZW1fb3duZXJfaWQiLCJzZW5zb3JOZXR3b3JrIiwidG9wb2xvZ3kiLCJsb2NhbEVkZ2UiLCJlZGdlcyIsImVkZ2UiLCJwaHlzaWNhbE5ldHdvcmtJZCIsImJ1cyIsInJvdXRpbmdNZXRhZGF0YSIsInRvQ29udGFpbkVxdWFsIiwib2JqZWN0Q29udGFpbmluZyIsImFwcHJvdmFsU3RhdGUiLCJwcm90b2NvbCIsInNpZGUiLCJoYXJkd2FyZUlkIiwibm9kZSIsImVuZ2luZWVyaW5nSWQiLCJwb3J0cyIsInR4cngiLCJoYXNUZXh0Iiwic2VsZWN0ZWQiLCJ0b0JlQ2hlY2tlZCIsInVuY2hlY2siLCJfcmVxdWVzdCRwb3N0RGF0YUpTT04zIiwic3lzdGVtX2NsdXN0ZXJfYXNzaWdubWVudHMiLCJjbHVzdGVyIiwiX2NsdXN0ZXIkZnVuY3Rpb25hbF9yIiwiZnVuY3Rpb25hbF9yb3V0ZXMiLCJleGNsdWRlZF9zaWduYWxzIiwicmV2aWV3IiwiYXBwbHkiLCJnZWFyYm94IiwiZW1vdG9yIl0sInNvdXJjZXMiOlsid2l6YXJkLnNwZWMudHMiXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgdGVzdCwgZXhwZWN0LCB0eXBlIFBhZ2UgfSBmcm9tICdwbGF5d3JpZ2h0L3Rlc3QnO1xyXG5pbXBvcnQgeyByZWFkRmlsZSB9IGZyb20gJ25vZGU6ZnMvcHJvbWlzZXMnO1xyXG5pbXBvcnQgeyByYW5kb21VVUlEIH0gZnJvbSAnbm9kZTpjcnlwdG8nO1xyXG5pbXBvcnQgeyBleGVjRmlsZVN5bmMgfSBmcm9tICdub2RlOmNoaWxkX3Byb2Nlc3MnO1xyXG5pbXBvcnQgeyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nLCBXSVpBUkRfU1RFUFMsIFdJWkFSRF9ET05FIH0gZnJvbSAnLi9zdXBwb3J0L3dpemFyZC1wcm9ncmVzcy13YXRjaGRvZyc7XHJcbmltcG9ydCB7IHJldmlld1ZpcnR1YWxUcmFuc3BvcnRzIH0gZnJvbSAnLi9zdXBwb3J0L25hdGl2ZS10cmFuc3BvcnQtZml4dHVyZXMnO1xyXG5cclxuY29uc3Qgc3RlcHMgPSBXSVpBUkRfU1RFUFM7XHJcbmNvbnN0IGRvbmUgPSBXSVpBUkRfRE9ORTtcclxudHlwZSBXcml0ZVRpbWluZyA9IHsgdXJsOiBzdHJpbmc7IHN0YXJ0ZWQ6IG51bWJlcjsgZHVyYXRpb25fbXM/OiBudW1iZXI7IHN0YXR1cz86IG51bWJlcjsgZmFpbHVyZT86IHN0cmluZyB9O1xyXG5jb25zdCB3cml0ZVRpbWluZ3MgPSBuZXcgTWFwPHN0cmluZywgV3JpdGVUaW1pbmdbXT4oKTtcclxuY29uc3Qgd29ya2Zsb3dQYWdlRmFpbHVyZXMgPSBuZXcgV2Vha01hcDxQYWdlLCBzdHJpbmdbXT4oKTtcclxuY29uc3QgcHJvZ3Jlc3NNaWxlc3RvbmVzID0gbmV3IE1hcDxzdHJpbmcsIHVua25vd25bXT4oKTtcclxuXHJcbnRlc3QuYmVmb3JlRWFjaChhc3luYyAoeyBwYWdlIH0sIGluZm8pID0+IHtcclxuICBjb25zdCByb3dzOiBXcml0ZVRpbWluZ1tdID0gW107XHJcbiAgd3JpdGVUaW1pbmdzLnNldChpbmZvLnRlc3RJZCwgcm93cyk7XHJcbiAgd29ya2Zsb3dQYWdlRmFpbHVyZXMuc2V0KHBhZ2UsIFtdKTtcclxuICBwcm9ncmVzc01pbGVzdG9uZXMuc2V0KGluZm8udGVzdElkLCBbXSk7XHJcbiAgY29uc3QgcmVxdWVzdHMgPSBuZXcgTWFwPG9iamVjdCwgV3JpdGVUaW1pbmc+KCk7XHJcbiAgcGFnZS5vbigncmVxdWVzdCcsIHJlcXVlc3QgPT4ge1xyXG4gICAgaWYgKCFbJ1BPU1QnLCAnUFVUJywgJ1BBVENIJywgJ0RFTEVURSddLmluY2x1ZGVzKHJlcXVlc3QubWV0aG9kKCkpKSByZXR1cm47XHJcbiAgICBjb25zdCByb3cgPSB7IHVybDogcmVxdWVzdC51cmwoKSwgc3RhcnRlZDogRGF0ZS5ub3coKSB9O1xyXG4gICAgcm93cy5wdXNoKHJvdyk7IHJlcXVlc3RzLnNldChyZXF1ZXN0LCByb3cpO1xyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3Jlc3BvbnNlJywgcmVzcG9uc2UgPT4ge1xyXG4gICAgY29uc3Qgcm93ID0gcmVxdWVzdHMuZ2V0KHJlc3BvbnNlLnJlcXVlc3QoKSk7XHJcbiAgICBpZiAocm93KSByb3cuc3RhdHVzID0gcmVzcG9uc2Uuc3RhdHVzKCk7XHJcbiAgICBpZiAocmVzcG9uc2Uuc3RhdHVzKCkgPT09IDQxMyAmJiAvXlxcL2FwaVxcL2VuZ2luZWVyaW5nXFwvd29ya2Zsb3coPzpcXC98JCkvLnRlc3QobmV3IFVSTChyZXNwb25zZS51cmwoKSkucGF0aG5hbWUpKSB7XHJcbiAgICAgIHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSEucHVzaChgSFRUUCA0MTM6ICR7cmVzcG9uc2UudXJsKCl9YCk7XHJcbiAgICB9XHJcbiAgfSk7XHJcbiAgcGFnZS5vbigncmVxdWVzdGZpbmlzaGVkJywgcmVxdWVzdCA9PiB7XHJcbiAgICBjb25zdCByb3cgPSByZXF1ZXN0cy5nZXQocmVxdWVzdCk7XHJcbiAgICBpZiAocm93KSByb3cuZHVyYXRpb25fbXMgPSBEYXRlLm5vdygpIC0gcm93LnN0YXJ0ZWQ7XHJcbiAgfSk7XHJcbiAgcGFnZS5vbigncmVxdWVzdGZhaWxlZCcsIHJlcXVlc3QgPT4ge1xyXG4gICAgY29uc3Qgcm93ID0gcmVxdWVzdHMuZ2V0KHJlcXVlc3QpO1xyXG4gICAgaWYgKHJvdykgeyByb3cuZHVyYXRpb25fbXMgPSBEYXRlLm5vdygpIC0gcm93LnN0YXJ0ZWQ7IHJvdy5mYWlsdXJlID0gcmVxdWVzdC5mYWlsdXJlKCk/LmVycm9yVGV4dDsgfVxyXG4gIH0pO1xyXG59KTtcclxuXHJcbnRlc3QuYWZ0ZXJFYWNoKGFzeW5jICh7IHBhZ2UgfSwgaW5mbykgPT4ge1xuICBhd2FpdCBpbmZvLmF0dGFjaCgnd3JpdGUtcmVxdWVzdC10aW1pbmdzJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh3cml0ZVRpbWluZ3MuZ2V0KGluZm8udGVzdElkKSB8fCBbXSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgYXdhaXQgaW5mby5hdHRhY2goJ3dvcmtmbG93LXByb2dyZXNzLWJvdW5kYXJpZXMnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHByb2dyZXNzTWlsZXN0b25lcy5nZXQoaW5mby50ZXN0SWQpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd29ya2Zsb3ctcGFnZS1mYWlsdXJlcycsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICB3cml0ZVRpbWluZ3MuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBwcm9ncmVzc01pbGVzdG9uZXMuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBleHBlY3Qod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpLCAnVGhlIHVuZGVybHlpbmcgZW5naW5lZXJpbmcgcGFnZSBtdXN0IHJlbWFpbiByZWFkYWJsZSB0aHJvdWdob3V0IHJlbG9hZCBhbmQgcmVjb3ZlcnkuJykudG9FcXVhbChbXSk7XG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnaGVhZGluZycsIHtuYW1lOiAnRGllIEFuc2ljaHQga29ubnRlIG5pY2h0IGdlbGFkZW4gd2VyZGVuLicsIGV4YWN0OiB0cnVlfSksXG4gICAgJ0EgY3Jhc2hlZCBwYXJhbWV0ZXIgb3IgZW5naW5lZXJpbmcgcGFnZSBtdXN0IG5ldmVyIGNvdW50IGFzIGEgc3VjY2Vzc2Z1bCB3aXphcmQgZGV0b3VyLicpLm5vdC50b0JlVmlzaWJsZSgpO1xufSk7XHJcblxyXG5hc3luYyBmdW5jdGlvbiBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2U6IFBhZ2UpIHtcbiAgZXhwZWN0KHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSwgJ0Egd29ya2luZyB3aXphcmQgb3ZlcmxheSBtdXN0IG5vdCBjb25jZWFsIGEgd29ya2Zsb3cgSFRUUCA0MTMuJykudG9FcXVhbChbXSk7XHJcbiAgZXhwZWN0KGF3YWl0IHBhZ2UuZ2V0QnlUZXh0KCdFbmdpbmVlcmluZy1BUEkgbmljaHQgZXJyZWljaGJhcicsIHsgZXhhY3Q6IHRydWUgfSkuaXNWaXNpYmxlKCksXG4gICAgJ1RoZSB1bmRlcmx5aW5nIGVuZ2luZWVyaW5nIHBhZ2UgbXVzdCBub3Qgc2hvdyBpdHMgQVBJIGVycm9yIHZpZXcuJykudG9CZShmYWxzZSk7XG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnaGVhZGluZycsIHtuYW1lOiAnRGllIEFuc2ljaHQga29ubnRlIG5pY2h0IGdlbGFkZW4gd2VyZGVuLicsIGV4YWN0OiB0cnVlfSkpLm5vdC50b0JlVmlzaWJsZSgpO1xufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVhZFByb2plY3QocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBwYXRoOiBzdHJpbmcpIHtcclxuICBjb25zdCByZXN1bHQgPSBhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KHBhdGgsIHsgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiA2MF8wMDAgfSk7XHJcbiAgdHJ5IHtcclxuICAgIGlmICghcmVzdWx0Lm9rKCkpIHRocm93IG5ldyBFcnJvcihgJHtwYXRofTogSFRUUCAke3Jlc3VsdC5zdGF0dXMoKX0gJHsoYXdhaXQgcmVzdWx0LnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgICByZXR1cm4gYXdhaXQgcmVzdWx0Lmpzb24oKTtcclxuICB9IGZpbmFsbHkge1xyXG4gICAgLy8gUGxheXdyaWdodCBvdGhlcndpc2UgcmV0YWlucyBldmVyeSBwb2xsZWQgcmVzcG9uc2UgdW50aWwgY29udGV4dCB0ZWFyZG93bi5cclxuICAgIC8vIEtlZXAgdGhlIHBhcnNlZCBldmlkZW5jZSwgcmVsZWFzZSBpdHMgZHVwbGljYXRlIHRyYW5zcG9ydCBib2R5IGltbWVkaWF0ZWx5LlxyXG4gICAgYXdhaXQgcmVzdWx0LmRpc3Bvc2UoKTtcclxuICB9XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHJlYWRXYXJuaW5nUmV2aWV3U3RhdGUocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nKSB7XHJcbiAgY29uc3QgYXV0aG9yaXR5ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgY29uc3QgcGFyYW1ldGVycyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnKTtcclxuICBjb25zdCB2ZXJpZmllZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gIGV4cGVjdChwYXJhbWV0ZXJzLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgZXhwZWN0KGF1dGhvcml0eS5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xyXG4gIGV4cGVjdCh2ZXJpZmllZC5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xyXG4gIGZvciAoY29uc3QgZmllbGQgb2YgWydydW5faWQnLCAncmVxdWVzdF9yZXZpc2lvbiddKVxyXG4gICAgZXhwZWN0KHZlcmlmaWVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5bZmllbGRdKS50b0JlKGF1dGhvcml0eS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uW2ZpZWxkXSk7XHJcbiAgcmV0dXJuIHsgcHJvamVjdF9pZDogdmVyaWZpZWQucHJvamVjdF9pZCwgc3RhdHVzZXM6IHZlcmlmaWVkLnN0YXR1c2VzLFxyXG4gICAgY29udGV4dDogeyBhZ2VudF9leGVjdXRpb246IHsgcnVuX2lkOiB2ZXJpZmllZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkLFxyXG4gICAgICByZXF1ZXN0X3JldmlzaW9uOiB2ZXJpZmllZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucmVxdWVzdF9yZXZpc2lvbiB9IH0sXHJcbiAgICBwYXJhbWV0ZXJzOiB7IHByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsOiBwYXJhbWV0ZXJzLnBhcmFtZXRlcnMucHJlZmxpZ2h0X3dhcm5pbmdfYXBwcm92YWwgfSB9O1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiBvcGVuV2l6YXJkKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZykge1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9lbmdpbmVlcmluZz9hc3Npc3RhbnQ9cHJvamVjdCZwcm9qZWN0PSR7cHJvamVjdH1gLCB7IHdhaXRVbnRpbDogJ2xvYWQnIH0pO1xyXG4gIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZykudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2UpO1xyXG4gIHJldHVybiBkaWFsb2c7XHJcbn1cclxuXHJcbnRlc3QoJ3Byb2plY3QgbmFtaW5nIGZvcm0gY2FyZHMgdXNlIHRoZSBmdWxsIHdpemFyZCB3aWR0aCBAbGF5b3V0JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCAnbmlzLWUyZS1wcm9qZWN0LW5hbWUtbGF5b3V0LScgKyByYW5kb21VVUlEKCkpO1xyXG4gIGNvbnN0IHN0ZXAgPSBkaWFsb2cubG9jYXRvcignZmllbGRzZXQuYWdlbnQtcHJvamVjdC1uYW1lLXN0ZXAnKTtcclxuICBhd2FpdCBleHBlY3Qoc3RlcCkudG9CZVZpc2libGUoKTtcclxuICBjb25zdCBzdGVwV2lkdGggPSBhd2FpdCBzdGVwLmV2YWx1YXRlKGVsZW1lbnQgPT4gZWxlbWVudC5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKS53aWR0aCk7XHJcbiAgY29uc3QgY2FyZHMgPSBhd2FpdCBzdGVwLmxvY2F0b3IoJzpzY29wZSA+IGxhYmVsJykuYWxsKCk7XHJcbiAgZXhwZWN0KGNhcmRzKS50b0hhdmVMZW5ndGgoNCk7XHJcbiAgZm9yIChjb25zdCBjYXJkIG9mIGNhcmRzKSB7XHJcbiAgICBjb25zdCB3aWR0aCA9IGF3YWl0IGNhcmQuZXZhbHVhdGUoZWxlbWVudCA9PiBlbGVtZW50LmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpLndpZHRoKTtcclxuICAgIGV4cGVjdCh3aWR0aCkudG9CZUdyZWF0ZXJUaGFuKHN0ZXBXaWR0aCAqIDAuODUpO1xyXG4gIH1cclxufSk7XHJcblxyXG5hc3luYyBmdW5jdGlvbiBhbGxPYmplY3RzKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcmVzb3VyY2U6IHN0cmluZykge1xyXG4gIGNvbnN0IGl0ZW1zOiBhbnlbXSA9IFtdO1xyXG4gIGZvciAobGV0IG9mZnNldCA9IDA7IDsgb2Zmc2V0ICs9IDUwMCkge1xyXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy8ke3Jlc291cmNlfT9saW1pdD01MDAmb2Zmc2V0PSR7b2Zmc2V0fWApO1xyXG4gICAgaXRlbXMucHVzaCguLi5yZXNwb25zZS5pdGVtcyk7XHJcbiAgICBpZiAocmVzcG9uc2UuaXRlbXMubGVuZ3RoIDwgNTAwKSByZXR1cm4gaXRlbXM7XHJcbiAgfVxyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiByZXN0YXJ0QXBwbGljYXRpb24ocGFnZTogUGFnZSwgY3Jhc2ggPSBmYWxzZSkge1xyXG4gIGNvbnN0IGNvbnRhaW5lciA9IHByb2Nlc3MuZW52Lk5JU19FMkVfQVBQX0NPTlRBSU5FUiE7XHJcbiAgZXhwZWN0KGNvbnRhaW5lcikudG9NYXRjaCgvXm5pcy1lMmUtYXBwLVthLWYwLTldKyQvKTtcclxuICBjb25zdCBkb2NrZXIgPSBwcm9jZXNzLmVudi5OSVNfVEVTVF9ET0NLRVIgfHwgJ2RvY2tlcic7XHJcbiAgY29uc3QgbGFiZWwgPSBleGVjRmlsZVN5bmMoZG9ja2VyLCBbJ2luc3BlY3QnLCBjb250YWluZXIsICctLWZvcm1hdCcsICd7e2luZGV4IC5Db25maWcuTGFiZWxzIFwibmV0d29ya2lzLnRlc3RcIn19J10sIHsgZW5jb2Rpbmc6ICd1dGY4JyB9KS50cmltKCk7XHJcbiAgZXhwZWN0KGxhYmVsKS50b0JlKCdkaXNwb3NhYmxlJyk7XHJcbiAgZXhlY0ZpbGVTeW5jKGRvY2tlciwgWydyZXN0YXJ0JywgLi4uKGNyYXNoID8gWyctdCcsICcwJ10gOiBbXSksIGNvbnRhaW5lcl0sIHsgdGltZW91dDogNjBfMDAwIH0pO1xyXG4gIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcclxuICAgIHRyeSB7IHJldHVybiAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9yZWFkeScsIHsgdGltZW91dDogMjAwMCB9KSkub2soKTsgfSBjYXRjaCB7IHJldHVybiBmYWxzZTsgfVxyXG4gIH0sIHsgdGltZW91dDogMTIwXzAwMCB9KS50b0JlKHRydWUpO1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBleHBlY3RlZDogUmVjb3JkPHN0cmluZywgdW5rbm93bj4pIHtcclxuICBjb25zdCBbaGFyZHdhcmUsIGZ1bmN0aW9ucywgbWVzc2FnZXMsIHNpZ25hbHNdID0gYXdhaXQgUHJvbWlzZS5hbGwoXHJcbiAgICBbJ2hhcmR3YXJlLW5vZGVzJywgJ2Z1bmN0aW9ucycsICdtZXNzYWdlcycsICdzaWduYWxzJ10ubWFwKHJlc291cmNlID0+IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgcmVzb3VyY2UpKSk7XHJcbiAgY29uc3Qgbm9kZXMgPSBuZXcgTWFwKGhhcmR3YXJlLm1hcChpdGVtID0+IFtpdGVtLmlkLCBpdGVtXSkpO1xyXG4gIGNvbnN0IGZ1bmN0aW9uc0J5SWQgPSBuZXcgTWFwKGZ1bmN0aW9ucy5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBtZXNzYWdlc0J5SWQgPSBuZXcgTWFwKG1lc3NhZ2VzLm1hcChpdGVtID0+IFtpdGVtLmlkLCBpdGVtXSkpO1xyXG4gIGNvbnN0IGNvbnRyYWN0czogUmVjb3JkPHN0cmluZywgdW5rbm93bj4gPSB7fTtcclxuICBmb3IgKGNvbnN0IHNpZ25hbCBvZiBzaWduYWxzKSB7XHJcbiAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXNCeUlkLmdldChzaWduYWwubWVzc2FnZV9pZCk7XHJcbiAgICBleHBlY3QobWVzc2FnZSkudG9CZVRydXRoeSgpO1xyXG4gICAgY29uc3QgcmVmZXJlbmNlID0gbWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QucHJvZHVjZXJfcmVmO1xyXG4gICAgY29uc3QgZm4gPSBmdW5jdGlvbnNCeUlkLmdldChyZWZlcmVuY2UpO1xyXG4gICAgY29uc3Qgb3duZXIgPSBub2Rlcy5nZXQocmVmZXJlbmNlKSB8fCAoZm4gJiYgbm9kZXMuZ2V0KGZuLmhhcmR3YXJlX25vZGVfaWQpKTtcclxuICAgIGNvbnN0IHByb2R1Y2VyID0gb3duZXI/LmRldmljZV90eXBlID09PSAnR2F0ZXdheScgPyAnJGdhdGV3YXknIDogKG5vZGVzLmdldChyZWZlcmVuY2UpIHx8IGZuKT8ubmFtZTtcclxuICAgIGV4cGVjdChwcm9kdWNlcikudG9CZVRydXRoeSgpO1xyXG4gICAgY29uc3Qga2V5ID0gW3Byb2R1Y2VyLCBtZXNzYWdlLm5hbWUsIHNpZ25hbC5uYW1lXS5qb2luKCcgOjogJyk7XHJcbiAgICBleHBlY3QoY29udHJhY3RzW2tleV0sICdTZW1hbnRpYyBzaWduYWwgaWRlbnRpdHkgbXVzdCBiZSB1bmlxdWU6ICcgKyBrZXkpLnRvQmVVbmRlZmluZWQoKTtcclxuICAgIGNvbnRyYWN0c1trZXldID0ge1xyXG4gICAgICAuLi5PYmplY3QuZnJvbUVudHJpZXMoWydzdGFydF9iaXQnLCAnbGVuZ3RoX2JpdHMnLCAnZGF0YV90eXBlJywgJ2ZhY3RvcicsICdvZmZzZXRfdmFsdWUnLFxyXG4gICAgICAgICd1bml0JywgJ21pbl92YWx1ZScsICdtYXhfdmFsdWUnLCAnYnl0ZV9vcmRlciddLm1hcChmaWVsZCA9PiBbZmllbGQsIHNpZ25hbFtmaWVsZF0gPz8gbnVsbF0pKSxcclxuICAgICAgZW51bV92YWx1ZXM6IHNpZ25hbC5kYXRhPy5lbnVtX3ZhbHVlcyA/PyBudWxsLFxyXG4gICAgICBzZW1hbnRpY190eXBlOiBzaWduYWwuc2VtYW50aWM/LnNlbWFudGljX3R5cGUgPz8gbnVsbCxcclxuICAgICAgZ2VuZXJhdGlvbl9yb2xlOiBzaWduYWwuY29uZmlndXJhdGlvbj8uZ2VuZXJhdGlvbl9yb2xlID8/IG51bGwsXHJcbiAgICB9O1xyXG4gIH1cclxuICBleHBlY3QoY29udHJhY3RzLCAnRXZlcnkgb3JpZ2luYWwgc2lnbmFsIGFuZCBpdHMgZXhwbGljaXQgZW5jb2RpbmcgbXVzdCBzdXJ2aXZlIGdlbmVyYXRpb24uJykudG9FcXVhbChleHBlY3RlZCk7XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHZlcmlmeUFydGlmYWN0cyhwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIG1pbmltdW1DYW5vbmljYWxTaWduYWxzOiBudW1iZXIsIGludGVybmFsQ29udHJvbGxlcj86IHN0cmluZyxcbiAgZXhwZWN0ZWRQYXJhbWV0ZXJzPzogUmVjb3JkPHN0cmluZywgdW5rbm93bj4sIGV4cGVjdGVkTmF0aXZlUmF0ZXM/OiBSZWNvcmQ8c3RyaW5nLCBSZWNvcmQ8c3RyaW5nLCBudW1iZXI+Pikge1xuICAvLyBUaGUgY29tcGxldGVkIG1vZGVsIGlzIHN0YWJsZTsgdGhlc2UgaW5kZXBlbmRlbnQgcmVhZHMgbmVlZCBubyBzZXJpYWwgd2FpdHMuXHJcbiAgY29uc3QgW3dvcmtmbG93LCBqb2JMaXN0LCBzbmFwc2hvdHMsIHNpZ25hbHMsIG1lc3NhZ2VzXSA9IGF3YWl0IFByb21pc2UuYWxsKFtcclxuICAgIHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpLFxyXG4gICAgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSxcclxuICAgIHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3NuYXBzaG90cycpLFxyXG4gICAgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnc2lnbmFscycpLFxyXG4gICAgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnbWVzc2FnZXMnKSxcclxuICBdKTtcclxuICBleHBlY3QoT2JqZWN0LmtleXMod29ya2Zsb3cuc3RhdHVzZXMpLnNvcnQoKSkudG9FcXVhbChbLi4uc3RlcHNdLnNvcnQoKSk7XHJcbiAgZm9yIChjb25zdCBzdGVwIG9mIHN0ZXBzKSBleHBlY3QoZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXNbc3RlcF0pLCBgJHtzdGVwfTogJHt3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXX1gKS50b0JlVHJ1dGh5KCk7XHJcbiAgY29uc3Qgam9icyA9IGpvYkxpc3Quam9icztcclxuICBleHBlY3Qoam9icykudG9IYXZlTGVuZ3RoKDEpO1xyXG4gIGV4cGVjdChqb2JzWzBdLnN0YXR1cykudG9CZSgnY29tcGxldGVkJyk7XHJcbiAgY29uc3Qgc25hcHNob3QgPSBzbmFwc2hvdHMuc2ltdWxhdGlvbnMuZmluZCgoaXRlbTogeyBqb2JfaWQ6IHN0cmluZyB9KSA9PiBpdGVtLmpvYl9pZCA9PT0gam9ic1swXS5pZCk7XHJcbiAgZXhwZWN0KHNuYXBzaG90KS50b0JlVHJ1dGh5KCk7XHJcbiAgY29uc3QgZnVsbCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3NpbXVsYXRpb24tc25hcHNob3RzLyR7c25hcHNob3QuaWR9YCk7XHJcbiAgaWYgKGV4cGVjdGVkUGFyYW1ldGVycykge1xuICAgIGNvbnN0IHsgZGF0YV9iaXRyYXRlLCBjYW5fZmRfZGF0YV9wcmVzY2FsZXIsIC4uLnJ1bnRpbWVQYXJhbWV0ZXJzIH0gPSBleHBlY3RlZFBhcmFtZXRlcnM7XHJcbiAgICBleHBlY3QoZnVsbC5jb25maWd1cmF0aW9uLnBhcmFtZXRlcnMpLnRvTWF0Y2hPYmplY3QocnVudGltZVBhcmFtZXRlcnMpO1xyXG4gICAgY29uc3QgY2FuRmROZXR3b3JrcyA9IGZ1bGwuY29uZmlndXJhdGlvbi5uZXR3b3Jrcy5maWx0ZXIoKG5ldHdvcms6IGFueSkgPT4gbmV0d29yay50ZWNobm9sb2d5ID09PSAnY2FuX2ZkJyk7XHJcbiAgICBleHBlY3QoY2FuRmROZXR3b3Jrcy5sZW5ndGgsICdUaGUgZWRpdGVkIENBTi1GRCBjb25maWd1cmF0aW9uIG11c3QgcmVhY2ggYSBwaHlzaWNhbCBzaW11bGF0aW9uIG5ldHdvcmsuJykudG9CZUdyZWF0ZXJUaGFuKDApO1xyXG4gICAgZm9yIChjb25zdCBuZXR3b3JrIG9mIGNhbkZkTmV0d29ya3MpIGV4cGVjdChuZXR3b3JrKS50b01hdGNoT2JqZWN0KHsgZGF0YV9iaXRyYXRlLCBjYW5fZmRfZGF0YV9wcmVzY2FsZXIgfSk7XG4gIH1cbiAgaWYgKGV4cGVjdGVkTmF0aXZlUmF0ZXMpIHtcbiAgICBmb3IgKGNvbnN0IFt0ZWNobm9sb2d5LCByYXRlc10gb2YgT2JqZWN0LmVudHJpZXMoZXhwZWN0ZWROYXRpdmVSYXRlcykpIHtcbiAgICAgIGNvbnN0IG5ldHdvcmtzID0gZnVsbC5jb25maWd1cmF0aW9uLm5ldHdvcmtzLmZpbHRlcigobmV0d29yazogYW55KSA9PiBuZXR3b3JrLnRlY2hub2xvZ3kgPT09IHRlY2hub2xvZ3kpO1xuICAgICAgZXhwZWN0KG5ldHdvcmtzLmxlbmd0aCwgYFNhdmVkICR7dGVjaG5vbG9neX0gcmF0ZXMgbXVzdCByZWFjaCB0aGUgZnJvemVuIHNpbXVsYXRpb24uYCkudG9CZUdyZWF0ZXJUaGFuKDApO1xuICAgICAgZm9yIChjb25zdCBuZXR3b3JrIG9mIG5ldHdvcmtzKSBleHBlY3QobmV0d29yaykudG9NYXRjaE9iamVjdChyYXRlcyk7XG4gICAgfVxuICB9XG4gIGNvbnN0IGFzc2Vzc21lbnQgPSBmdWxsLnJlc3VsdC5hc3Nlc3NtZW50O1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnNjb3BlX21vZGUpLnRvQmUoJ0FMTCcpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLmNvbXBsZXRlKS50b0JlKHRydWUpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LmNvbmZvcm1hbmNlKS50b0JlKCdQQVNTJyk7XHJcbiAgZXhwZWN0KGFzc2Vzc21lbnQuZmFpbGVkX3JvdXRlX2NvdW50KS50b0JlKDApO1xyXG4gIGV4cGVjdChzaWduYWxzLmxlbmd0aCwgJ1RoZSBmdWxsIGNhbm9uaWNhbCBzaWduYWwgaW52ZW50b3J5IG11c3Qgc3Vydml2ZSBnZW5lcmF0aW9uLicpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwobWluaW11bUNhbm9uaWNhbFNpZ25hbHMpO1xyXG4gIGNvbnN0IGV4Y2x1ZGVkID0gYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS50cmFuc3BvcnRfZXhjbHVzaW9ucyA/PyBbXTtcclxuICBmb3IgKGNvbnN0IGl0ZW0gb2YgZXhjbHVkZWQpIHtcclxuICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKHJvdyA9PiByb3cuaWQgPT09IGl0ZW0ubWVzc2FnZV9pZCk7XHJcbiAgICBleHBlY3QobWVzc2FnZSwgYEV4Y2x1ZGVkIG1lc3NhZ2UgJHtpdGVtLm1lc3NhZ2VfaWR9IG11c3QgZXhpc3QuYCkudG9CZVRydXRoeSgpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5yb3V0aW5nLmVuYWJsZWQpLnRvQmUoZmFsc2UpO1xyXG4gICAgY29uc3QgY29udHJhY3QgPSBtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdDtcclxuICAgIGV4cGVjdChjb250cmFjdC5jb25zdW1lcl9yZWZzKS50b0VxdWFsKFtdKTtcclxuICAgIGV4cGVjdChpdGVtLnJlYXNvbl9jb2RlKS50b0JlKGNvbnRyYWN0LnJvbGUgPT09ICdJTlRFUk5BTF9TVEFURSdcclxuICAgICAgPyAnSU5URVJOQUxfU1RBVEVfTk9UX1JPVVRFRCcgOiAnRVhQTElDSVRfRlVOQ1RJT05fT1VUUFVUX05PVF9ST1VURUQnKTtcclxuICB9XHJcbiAgaWYgKGludGVybmFsQ29udHJvbGxlcikge1xyXG4gICAgY29uc3Qgbm9kZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gICAgY29uc3QgY29udHJvbGxlciA9IG5vZGVzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09IGludGVybmFsQ29udHJvbGxlcik7XHJcbiAgICBleHBlY3QoZXhjbHVkZWQubGVuZ3RoKS50b0JlR3JlYXRlclRoYW4oMCk7XHJcbiAgICBmb3IgKGNvbnN0IGl0ZW0gb2YgZXhjbHVkZWQpIHtcclxuICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzLmZpbmQocm93ID0+IHJvdy5pZCA9PT0gaXRlbS5tZXNzYWdlX2lkKTtcclxuICAgICAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0KS50b01hdGNoT2JqZWN0KHsgcm9sZTogJ0lOVEVSTkFMX1NUQVRFJywgc2NvcGU6ICdJTlRFUk5BTCcsIHByb2R1Y2VyX3JlZjogY29udHJvbGxlci5pZCwgY29uc3VtZXJfcmVmczogW10gfSk7XHJcbiAgICB9XHJcbiAgfVxyXG4gIGNvbnN0IGV4Y2x1ZGVkU2lnbmFscyA9IG5ldyBTZXQoZXhjbHVkZWQuZmxhdE1hcCgoaXRlbTogeyBzaWduYWxfaWRzOiBzdHJpbmdbXSB9KSA9PiBpdGVtLnNpZ25hbF9pZHMpKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQsICdBTEwgbXVzdCBvYnNlcnZlIGV2ZXJ5IGNhbm9uaWNhbCBzaWduYWwgd2l0aCBhIHRyYW5zcG9ydCBvYmxpZ2F0aW9uLicpLnRvQmUoc2lnbmFscy5sZW5ndGggLSBleGNsdWRlZFNpZ25hbHMuc2l6ZSk7XHJcbiAgZm9yIChjb25zdCBrZXkgb2YgWydtaXNzaW5nX29ic2VydmVkX3NpZ25hbF9pZHMnLCAnbWlzc2luZ19vYnNlcnZlZF9yb3V0ZV9pZHMnLCAnbWlzc2luZ19vYnNlcnZlZF9uZXR3b3JrX2lkcyddKSBleHBlY3QoYXNzZXNzbWVudFtrZXldKS50b0VxdWFsKFtdKTtcclxuICBjb25zdCB0cmFjZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL3NpbXVsYXRpb25zLyR7am9ic1swXS5pZH0vdHJhY2Utd2luZG93P2xpbWl0PTEwYCk7XHJcbiAgZXhwZWN0KHRyYWNlLmNvdW50KS50b0JlR3JlYXRlclRoYW4oMCk7XHJcbiAgZXhwZWN0KHRyYWNlLmV2ZW50cy5zb21lKChpdGVtOiB7IHNpZ25hbHM/OiB1bmtub3duW10gfSkgPT4gaXRlbS5zaWduYWxzICYmIE9iamVjdC5rZXlzKGl0ZW0uc2lnbmFscykubGVuZ3RoKSkudG9CZVRydXRoeSgpO1xyXG4gIHJldHVybiB7IHdvcmtmbG93LCBqb2I6IGpvYnNbMF0uaWQsIGFzc2Vzc21lbnQsIHBhcmFtZXRlcl9wcm9vZjogZXhwZWN0ZWRQYXJhbWV0ZXJzID8ge1xyXG4gICAgc2F2ZWQ6IGV4cGVjdGVkUGFyYW1ldGVycywgc2ltdWxhdGlvbl9yYXRlczogZnVsbC5jb25maWd1cmF0aW9uLm5ldHdvcmtzLm1hcCgobmV0d29yazogYW55KSA9PiAoe1xyXG4gICAgICB0ZWNobm9sb2d5OiBuZXR3b3JrLnRlY2hub2xvZ3ksIGJpdHJhdGU6IG5ldHdvcmsuYml0cmF0ZSxcclxuICAgICAgYXJiaXRyYXRpb25fYml0cmF0ZTogbmV0d29yay5hcmJpdHJhdGlvbl9iaXRyYXRlLCBkYXRhX2JpdHJhdGU6IG5ldHdvcmsuZGF0YV9iaXRyYXRlLFxyXG4gICAgICBoYXJkd2FyZV9ldmlkZW5jZTogbmV0d29yay5oYXJkd2FyZV9ldmlkZW5jZSxcclxuICAgIH0pKSxcclxuICB9IDogdW5kZWZpbmVkIH07XHJcbn1cclxuXHJcbnR5cGUgUGFyYW1ldGVyUmV0dXJuU2NlbmFyaW8gPSB7XG4gIHRlY2hub2xvZ3k6IHN0cmluZztcbiAgZmllbGRzOiBSZWNvcmQ8c3RyaW5nLCBzdHJpbmc+O1xuICBuYXRpdmU6IFJlY29yZDxzdHJpbmcsIG51bWJlcj47XG4gIGVkaXRGaWVsZHM/OiBzdHJpbmdbXTtcbn07XG5cbi8vIEV4ZXJjaXNlIHRoZSB1c2VyJ3MgZGV0b3VyLCBpbmNsdWRpbmcgcmVwZWF0ZWQgc2F2ZXMgaW4gYW4gZXhpc3RpbmcgcnVuLlxuLy8gUmVhZHMgaW5zcGVjdCByZWFsIHBlcnNpc3RlZCBzdGF0ZTsgd3JpdGVzIGFuZCByZXR1cm4gbmF2aWdhdGlvbiB1c2UgdGhlIFVJLlxuYXN5bmMgZnVuY3Rpb24gcmVwZWF0UGFyYW1ldGVyUmV0dXJuKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcHJvcG9zYWxJZDogc3RyaW5nLFxuICBzY2VuYXJpb3M6IFBhcmFtZXRlclJldHVyblNjZW5hcmlvW10pIHtcbiAgY29uc3QgYmVmb3JlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XG4gIGNvbnN0IGlkZW50aXR5ID0gYmVmb3JlLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uO1xuICBleHBlY3QoaWRlbnRpdHkucnVuX2lkKS50b0JlVHJ1dGh5KCk7XG4gIGNvbnN0IG5vZGVJZHMgPSAoYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKSkubWFwKGl0ZW0gPT4gaXRlbS5pZCkuc29ydCgpO1xuICBjb25zdCBzdGFydHM6IHVua25vd25bXSA9IFtdO1xuICBjb25zdCB0cmFja1N0YXJ0cyA9IChyZXF1ZXN0OiBpbXBvcnQoJ3BsYXl3cmlnaHQvdGVzdCcpLlJlcXVlc3QpID0+IHtcbiAgICBpZiAocmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JykgJiYgcmVxdWVzdC5tZXRob2QoKSA9PT0gJ1BPU1QnXG4gICAgICAmJiByZXF1ZXN0LnBvc3REYXRhSlNPTigpPy53aXphcmRfY29tbWFuZD8uYWN0aW9uID09PSAnU1RBUlQnKSBzdGFydHMucHVzaChyZXF1ZXN0LnBvc3REYXRhSlNPTigpKTtcbiAgfTtcbiAgY29uc3QgZXZpZGVuY2U6IHVua25vd25bXSA9IFtdO1xuICBwYWdlLm9uKCdyZXF1ZXN0JywgdHJhY2tTdGFydHMpO1xuICB0cnkge1xuICAgIGNvbnN0IHdpemFyZCA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7bmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJ30pO1xuICAgIGlmIChhd2FpdCB3aXphcmQuaXNWaXNpYmxlKCkpIHtcbiAgICAgIC8vIEEgY2FwdHVyZWQgQVBJIFNUQVJUIGRvZXMgbm90IGFjdGl2YXRlIGEgYnJvd3NlciB3aXphcmQgc2Vzc2lvbi4gRW50ZXJcbiAgICAgIC8vIHBhcmFtZXRlcnMgdGhyb3VnaCB0aGUgYWN0dWFsIHdvcmtmbG93IGNhcmQsIGp1c3QgYXMgYSB1c2VyIGRvZXMuXG4gICAgICBhd2FpdCB3aXphcmQubG9jYXRvcignLmFnZW50LXdpemFyZC1wcm9ncmVzcy1jYXJkW2hyZWYqPVwibW9kZT1wYXJhbWV0ZXJzXCJdJykuY2xpY2soKTtcbiAgICAgIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywge25hbWU6ICdadXLDvGNrIHp1bSBBdWZ0cmFnJywgZXhhY3Q6IHRydWV9KSkudG9CZVZpc2libGUoKTtcbiAgICB9XG4gICAgZm9yIChjb25zdCBbY3ljbGUsIHNlZWRdIG9mIFs0MSwgNDMsIDQyXS5lbnRyaWVzKCkpIHtcbiAgICAgIGZvciAoY29uc3Qgc2NlbmFyaW8gb2Ygc2NlbmFyaW9zKSB7XG4gICAgICAgIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke2VuY29kZVVSSUNvbXBvbmVudChwcm9qZWN0KX0mdGVjaG5vbG9neT0ke3NjZW5hcmlvLnRlY2hub2xvZ3l9JnByb3Bvc2FsPSR7cHJvcG9zYWxJZH0jcGFyYW1ldGVyLWZpbmRpbmdzYCk7XG4gICAgICAgIGF3YWl0IGFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkocGFnZSk7XG4gICAgICAgIGNvbnN0IGNvbW1vbiA9IHBhZ2UubG9jYXRvcignLnBhcmFtZXRlci1ncm91cC1jb21tb24nKTtcbiAgICAgICAgZm9yIChjb25zdCBbZmllbGQsIHZhbHVlXSBvZiBPYmplY3QuZW50cmllcyhzY2VuYXJpby5maWVsZHMpKSB7XG4gICAgICAgICAgY29uc3QgaW5wdXQgPSBwYWdlLmxvY2F0b3IoYCMke2ZpZWxkfWApO1xuICAgICAgICAgIGNvbnN0IGRldGFpbHMgPSBpbnB1dC5sb2NhdG9yKCd4cGF0aD1hbmNlc3Rvcjo6ZGV0YWlsc1sxXScpO1xuICAgICAgICAgIGlmIChhd2FpdCBkZXRhaWxzLmNvdW50KCkgJiYgYXdhaXQgZGV0YWlscy5nZXRBdHRyaWJ1dGUoJ29wZW4nKSA9PT0gbnVsbClcbiAgICAgICAgICAgIGF3YWl0IGRldGFpbHMubG9jYXRvcignOnNjb3BlID4gc3VtbWFyeScpLmNsaWNrKCk7XG4gICAgICAgICAgaWYgKHNjZW5hcmlvLmVkaXRGaWVsZHM/LmluY2x1ZGVzKGZpZWxkKSkgYXdhaXQgaW5wdXQuZmlsbCh2YWx1ZSk7XG4gICAgICAgICAgZWxzZSBhd2FpdCBleHBlY3QoaW5wdXQpLnRvSGF2ZVZhbHVlKHZhbHVlKTtcbiAgICAgICAgfVxuICAgICAgICBhd2FpdCBjb21tb24ubG9jYXRvcignI3NlZWQnKS5maWxsKFN0cmluZyhzZWVkKSk7XG4gICAgICAgIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7bmFtZTogJ1BhcmFtZXRlciBzcGVpY2hlcm4g4oaSJywgZXhhY3Q6IHRydWV9KS5jbGljaygpO1xuICAgICAgICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ1RlY2hub2xvZ2llLSB1bmQgVGltaW5nLVBhcmFtZXRlciBnZXNwZWljaGVydC4nKSkudG9CZVZpc2libGUoKTtcbiAgICAgICAgY29uc3Qgc2F2ZWQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyk7XG4gICAgICAgIGV4cGVjdChzYXZlZC5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xuICAgICAgICBjb25zdCBzY29wZWQgPSBzYXZlZC5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfcGFyYW1ldGVyc1tzY2VuYXJpby50ZWNobm9sb2d5XTtcbiAgICAgICAgY29uc3QgYXNzdW1lZCA9IHNhdmVkLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnM/LltzY2VuYXJpby50ZWNobm9sb2d5XTtcbiAgICAgICAgZXhwZWN0KHNjb3BlZC52YWx1ZXMuc2VlZCkudG9CZShzZWVkKTtcbiAgICAgICAgY29uc3QgbmF0aXZlVmFsdWVzID0gey4uLmFzc3VtZWQ/LnZhbHVlcywgLi4uc2NvcGVkLnZhbHVlc307XG4gICAgICAgIGV4cGVjdChuYXRpdmVWYWx1ZXMpLnRvTWF0Y2hPYmplY3Qoc2NlbmFyaW8ubmF0aXZlKTtcbiAgICAgICAgZm9yIChjb25zdCBba2V5LCB2YWx1ZV0gb2YgT2JqZWN0LmVudHJpZXMoc2NlbmFyaW8ubmF0aXZlKSkge1xuICAgICAgICAgIGNvbnN0IGNvbmZpcm1lZCA9IE9iamVjdC5oYXNPd24oc2NvcGVkLnZhbHVlcywga2V5KTtcbiAgICAgICAgICBleHBlY3QoKGNvbmZpcm1lZCA/IHNjb3BlZCA6IGFzc3VtZWQpLnByb3ZlbmFuY2Vba2V5XSkudG9NYXRjaE9iamVjdChjb25maXJtZWRcbiAgICAgICAgICAgID8ge3NvdXJjZTogJ1VTRVJfQ09ORklSTUVEJywgc3RhdHVzOiAnQ09ORklSTUVEJywgdmFsdWV9XG4gICAgICAgICAgICA6IHtzb3VyY2U6ICdOSVNfU0lNVUxBVElPTl9BU1NVTVBUSU9OJywgc3RhdHVzOiAnQVNTVU1FRCcsIHRlY2hub2xvZ3k6IHNjZW5hcmlvLnRlY2hub2xvZ3ksIGhhcmR3YXJlX2V2aWRlbmNlOiBmYWxzZSwgdmFsdWV9KTtcbiAgICAgICAgfVxuICAgICAgICBjb25zdCB1c2VyVmFsdWVzID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycy91c2VyLWRlZmluZWQtdmFsdWVzJyk7XG4gICAgICAgIGV4cGVjdCh1c2VyVmFsdWVzLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XG4gICAgICAgIGV4cGVjdCh1c2VyVmFsdWVzLnZhbHVlX29yaWdpbikudG9CZSgnVVNFUl9ERUZJTkVEX1ZBTFVFJyk7XG4gICAgICAgIGV4cGVjdCh1c2VyVmFsdWVzLnBhcmFtZXRlcnMudGVjaG5vbG9neV9kZWZhdWx0cykudG9CZVVuZGVmaW5lZCgpO1xuICAgICAgICBleHBlY3QodXNlclZhbHVlcy5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfcGFyYW1ldGVyc1tzY2VuYXJpby50ZWNobm9sb2d5XSkudG9FcXVhbChzY29wZWQpO1xuICAgICAgICBjb25zdCBzdGFsZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3Byb3Bvc2FsSWR9P3ZpZXc9c3RhdHVzYCk7XG4gICAgICAgIGV4cGVjdChzdGFsZS5kYXRhLnN0YXR1cykudG9CZSgnT1VUREFURUQnKTtcbiAgICAgICAgY29uc3QgY2Fub25pY2FsSWRzID0gc3RhbGUuZGF0YS5jYW5vbmljYWxfaWRzO1xuICAgICAgICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xuICAgICAgICBhd2FpdCBleHBlY3QoY29tbW9uLmxvY2F0b3IoJyNzZWVkJykpLnRvSGF2ZVZhbHVlKFN0cmluZyhzZWVkKSk7XG4gICAgICAgIGZvciAoY29uc3QgW2ZpZWxkLCB2YWx1ZV0gb2YgT2JqZWN0LmVudHJpZXMoc2NlbmFyaW8uZmllbGRzKSkge1xuICAgICAgICAgIGNvbnN0IGlucHV0ID0gcGFnZS5sb2NhdG9yKGAjJHtmaWVsZH1gKTtcbiAgICAgICAgICBjb25zdCBkZXRhaWxzID0gaW5wdXQubG9jYXRvcigneHBhdGg9YW5jZXN0b3I6OmRldGFpbHNbMV0nKTtcbiAgICAgICAgICBpZiAoYXdhaXQgZGV0YWlscy5jb3VudCgpICYmIGF3YWl0IGRldGFpbHMuZ2V0QXR0cmlidXRlKCdvcGVuJykgPT09IG51bGwpXG4gICAgICAgICAgICBhd2FpdCBkZXRhaWxzLmxvY2F0b3IoJzpzY29wZSA+IHN1bW1hcnknKS5jbGljaygpO1xuICAgICAgICAgIGF3YWl0IGV4cGVjdChpbnB1dCkudG9IYXZlVmFsdWUodmFsdWUpO1xuICAgICAgICB9XG4gICAgICAgIC8vIEtlZXAgdGhlIGV4aXN0aW5nIGRlbGF5ZWQtcmVzdG9yZSByZWdyZXNzaW9uLCB1c2luZyByZWFsIHJlc3BvbnNlcy5cbiAgICAgICAgbGV0IHJlc3VtZVJlc3RvcmUhOiAoKSA9PiB2b2lkO1xuICAgICAgICBjb25zdCByZXN0b3JlUGF1c2UgPSBuZXcgUHJvbWlzZTx2b2lkPihyZXNvbHZlID0+IHsgcmVzdW1lUmVzdG9yZSA9IHJlc29sdmU7IH0pO1xuICAgICAgICBjb25zdCBkZWxheVJlc3RvcmUgPSBhc3luYyAocm91dGU6IGltcG9ydCgncGxheXdyaWdodC90ZXN0JykuUm91dGUpID0+IHtcbiAgICAgICAgICBhd2FpdCByZXN0b3JlUGF1c2U7IGF3YWl0IHJvdXRlLmNvbnRpbnVlKCk7XG4gICAgICAgIH07XG4gICAgICAgIGNvbnN0IGRlbGF5ZWQgPSBjeWNsZSA9PT0gMCAmJiBzY2VuYXJpbyA9PT0gc2NlbmFyaW9zWzBdO1xuICAgICAgICBpZiAoZGVsYXllZCkgYXdhaXQgcGFnZS5yb3V0ZSgnKiovYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScsIGRlbGF5UmVzdG9yZSk7XG4gICAgICAgIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7bmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJ30pO1xuICAgICAgICB0cnkge1xuICAgICAgICAgIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7bmFtZTogJ1p1csO8Y2sgenVtIEF1ZnRyYWcnLCBleGFjdDogdHJ1ZX0pLmNsaWNrKCk7XG4gICAgICAgICAgaWYgKGRlbGF5ZWQpIHtcbiAgICAgICAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7bmFtZTogJ0dlc3BlaWNoZXJ0ZW4gQXVmdHJhZyB3aWVkZXJoZXJzdGVsbGVuJ30pKS50b0JlVmlzaWJsZSgpO1xuICAgICAgICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZykubm90LnRvQ29udGFpblRleHQoJ1Byb2pla3RuYW1lOiBTY2hyaXR0IDEnKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZmluYWxseSB7XG4gICAgICAgICAgcmVzdW1lUmVzdG9yZSgpO1xuICAgICAgICAgIGlmIChkZWxheWVkKSBhd2FpdCBwYWdlLnVucm91dGVBbGwoe2JlaGF2aW9yOiAnd2FpdCd9KTtcbiAgICAgICAgfVxuICAgICAgICAvLyBNYXRjaCB0aGUgZXhpc3RpbmcgcHJvcG9zYWwtcmV2aWV3IHJlYWRpbmVzcyBidWRnZXQgYmVsb3cuIFRoZSBuZXdcbiAgICAgICAgLy8gcmV0dXJuIGFzc2VydGlvbiBtdXN0IG5vdCBpbXBvc2UgYSBzaG9ydGVyIGxpbWl0IG9uIHRoZSBsYXJnZSBtb2RlbC5cbiAgICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHtuYW1lOiAnRW5naW5lZXJpbmctVm9yc2NobGFnJ30pKVxuICAgICAgICAgIC50b0NvbnRhaW5UZXh0KCdHZXByw7xmdCDCtyBGcmVpZ2FiZSBvZmZlbicsIHt0aW1lb3V0OiA2MF8wMDB9KTtcbiAgICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZykudG9Db250YWluVGV4dCgnU3RhdHVzw7xiZXJzaWNodDogU2Nocml0dCA1IHZvbiA1Jyk7XG4gICAgICAgIGNvbnN0IHJlc3RvcmVkID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XG4gICAgICAgIGV4cGVjdChyZXN0b3JlZC5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xuICAgICAgICBleHBlY3QocmVzdG9yZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24ucnVuX2lkKS50b0JlKGlkZW50aXR5LnJ1bl9pZCk7XG4gICAgICAgIGV4cGVjdChyZXN0b3JlZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbi5yZXF1ZXN0X3JldmlzaW9uKS50b0JlKGlkZW50aXR5LnJlcXVlc3RfcmV2aXNpb24pO1xuICAgICAgICBleHBlY3QocmVzdG9yZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24uc3RhdGUpLnRvQmUoJ1JFVklFV19SRVFVSVJFRCcpO1xuICAgICAgICBleHBlY3QocmVzdG9yZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24uc3RlcCkudG9CZShpZGVudGl0eS5zdGVwKTtcbiAgICAgICAgZm9yIChjb25zdCBzdGVwIG9mIHN0ZXBzKSBpZiAoZG9uZS5oYXMoYmVmb3JlLnN0YXR1c2VzW3N0ZXBdKSlcbiAgICAgICAgICBleHBlY3QoZG9uZS5oYXMocmVzdG9yZWQuc3RhdHVzZXNbc3RlcF0pLCBgUmV0dXJuaW5nIG11c3QgcHJlc2VydmUgY29tcGxldGVkIHN0YWdlICR7c3RlcH0uYCkudG9CZSh0cnVlKTtcbiAgICAgICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XG4gICAgICAgIGV4cGVjdChjb252ZXJzYXRpb24uZGF0YS5hY3RpdmVfcHJvcG9zYWwpLnRvQmUocHJvcG9zYWxJZCk7XG4gICAgICAgIGNvbnN0IGZyZXNoID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7cHJvcG9zYWxJZH0/dmlldz1zdGF0dXNgKTtcbiAgICAgICAgZXhwZWN0KGZyZXNoLmRhdGEuc3RhdHVzKS50b0JlKCdWQUxJREFURUQnKTtcbiAgICAgICAgZXhwZWN0KGZyZXNoLmRhdGEuY2Fub25pY2FsX2lkcykudG9FcXVhbChjYW5vbmljYWxJZHMpO1xuICAgICAgICBleHBlY3QoKGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJykpLm1hcChpdGVtID0+IGl0ZW0uaWQpLnNvcnQoKSkudG9FcXVhbChub2RlSWRzKTtcbiAgICAgICAgY29uc3QgYWZ0ZXIgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyk7XG4gICAgICAgIGV4cGVjdChhZnRlci5wYXJhbWV0ZXJzKS50b0VxdWFsKHNhdmVkLnBhcmFtZXRlcnMpO1xuICAgICAgICBleHBlY3Qoc3RhcnRzLCAnUmV0dXJuaW5nIGZyb20gcGFyYW1ldGVycyBtdXN0IG5ldmVyIHJlc3RhcnQgdGhpcyBydW4uJykudG9FcXVhbChbXSk7XG4gICAgICAgIGV2aWRlbmNlLnB1c2goe2N5Y2xlOiBjeWNsZSArIDEsIHRlY2hub2xvZ3k6IHNjZW5hcmlvLnRlY2hub2xvZ3ksIHNlZWQsIHJ1bl9pZDogaWRlbnRpdHkucnVuX2lkLFxuICAgICAgICAgIHByb3Bvc2FsX2lkOiBwcm9wb3NhbElkLCBzYXZlZF92YWx1ZXM6IHNjb3BlZCwgYXNzdW1wdGlvbnM6IGFzc3VtZWQsXG4gICAgICAgICAgcmVzdG9yZWRfc3RhdHVzOiBmcmVzaC5kYXRhLnN0YXR1cywgY2Fub25pY2FsX2lkczogY2Fub25pY2FsSWRzfSk7XG4gICAgICB9XG4gICAgfVxuICB9IGZpbmFsbHkge1xuICAgIHBhZ2Uub2ZmKCdyZXF1ZXN0JywgdHJhY2tTdGFydHMpO1xuICAgIGF3YWl0IHRlc3QuaW5mbygpLmF0dGFjaCgncmVwZWF0ZWQtcGFyYW1ldGVyLXJldHVybicsIHtib2R5OiBKU09OLnN0cmluZ2lmeShldmlkZW5jZSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbid9KTtcbiAgfVxufVxuXG5hc3luYyBmdW5jdGlvbiBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCByZXN0YXJ0OiBib29sZWFuLCBleHBlY3RlZEhhcmR3YXJlOiBzdHJpbmdbXSA9IFtdLCBjcmFzaFNpbXVsYXRpb24gPSBmYWxzZSxcbiAgZXhwZWN0ZWRTaWduYWxzPzogUmVjb3JkPHN0cmluZywgdW5rbm93bj4sIGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQ/OiAoKSA9PiBQcm9taXNlPHZvaWQ+LCBzdG9wT25FdmlkZW5jZUJsb2NrID0gZmFsc2UsXG4gIGJlZm9yZVByb3Bvc2FsUmV2aWV3PzogKHByb3Bvc2FsSWQ6IHN0cmluZywgcHJvcG9zYWxUeXBlOiBzdHJpbmcpID0+IFByb21pc2U8dm9pZD4pIHtcbiAgbGV0IHJldmlld0NvdW50ID0gMDtcclxuICBsZXQgcnVuSWQ6IHN0cmluZyB8IHVuZGVmaW5lZDtcclxuICBjb25zdCByZXZpZXdlZCA9IG5ldyBTZXQ8c3RyaW5nPigpO1xyXG4gIGxldCByZXN0YXJ0ZWRKb2JJZDogc3RyaW5nIHwgdW5kZWZpbmVkO1xyXG4gIGxldCB3YXRjaGRvZyA9IG5ldyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nKHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICBmb3IgKGxldCBjaGVja3BvaW50ID0gMDsgY2hlY2twb2ludCA8IDE2OyBjaGVja3BvaW50KyspIHtcclxuICAgIGxldCB3b3JrZmxvdzogYW55O1xyXG4gICAgbGV0IHByb3Bvc2FsSWQgPSAnJztcclxuICAgIGxldCByZWFkeVZlcnNpb24gPSAnJztcclxuICAgIGxldCByZWFkeVNpbmNlID0gMDtcclxuICAgIGNvbnN0IGlzQ2hlY2twb2ludCA9IGFzeW5jICgpID0+IHtcclxuICAgICAgd2F0Y2hkb2cucmVtYWluaW5nKHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICAgICAgYXdhaXQgYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeShwYWdlKTtcclxuICAgICAgd29ya2Zsb3cgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgY29uc3QgcHJvZ3Jlc3MgPSB3YXRjaGRvZy5vYnNlcnZlKHdvcmtmbG93LCBwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgICAgIGlmIChwcm9ncmVzcy5hZHZhbmNlZCkgcHJvZ3Jlc3NNaWxlc3RvbmVzLmdldCh0ZXN0LmluZm8oKS50ZXN0SWQpIS5wdXNoKHtcclxuICAgICAgICBhdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLCBmcm9udGllcjogcHJvZ3Jlc3MuZnJvbnRpZXIsXHJcbiAgICAgICAgY29tcGxldGVkVGhyb3VnaDogc3RlcHNbcHJvZ3Jlc3MuZnJvbnRpZXIgLSAxXSxcclxuICAgICAgICBwcm9qZWN0OiB3b3JrZmxvdy5wcm9qZWN0X2lkLCBleGVjdXRpb246IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLFxyXG4gICAgICB9KTtcclxuICAgICAgaWYgKGNyYXNoU2ltdWxhdGlvbiAmJiAhcmVzdGFydGVkSm9iSWQgJiYgZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXMudmFsaWRhdGlvbikpIHtcclxuICAgICAgICBjb25zdCBqb2JzID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnM7XHJcbiAgICAgICAgY29uc3QgcnVubmluZyA9IGpvYnMuZmluZCgoam9iOiB7IHN0YXR1czogc3RyaW5nIH0pID0+IGpvYi5zdGF0dXMgPT09ICdydW5uaW5nJyk7XHJcbiAgICAgICAgaWYgKHJ1bm5pbmcpIHtcclxuICAgICAgICAgIHJlc3RhcnRlZEpvYklkID0gcnVubmluZy5pZDtcclxuICAgICAgICAgIGF3YWl0IHJlc3RhcnRBcHBsaWNhdGlvbihwYWdlLCB0cnVlKTtcclxuICAgICAgICAgIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgICAgICAgICByZXR1cm4gZmFsc2U7XHJcbiAgICAgICAgfVxyXG4gICAgICB9XHJcbiAgICAgIGlmIChzdGVwcy5ldmVyeShzdGVwID0+IGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzW3N0ZXBdKSkpIHJldHVybiB0cnVlO1xyXG4gICAgICBjb25zdCBleGVjdXRpb24gPSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbjtcclxuICAgICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdSRVZJRVdfUkVRVUlSRUQnKSB7XHJcbiAgICAgICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XHJcbiAgICAgICAgcHJvcG9zYWxJZCA9IGNvbnZlcnNhdGlvbi5kYXRhLmFjdGl2ZV9wcm9wb3NhbDtcclxuICAgICAgICAvLyBQb2xsaW5nIG1heSBzdGlsbCBleHBvc2UgdGhlIGp1c3QtYXBwbGllZCByZXZpZXcgd2hpbGUgdGhlIFVJIHN0YXJ0c1xyXG4gICAgICAgIC8vIGl0cyBkdXJhYmxlIGNvbnRpbnVhdGlvbi4gV2FpdCBmb3IgYSBkaXN0aW5jdCBwcm9wb3NhbCwgbm90IGl0cyBsYWJlbC5cclxuICAgICAgICByZXR1cm4gQm9vbGVhbihwcm9wb3NhbElkKSAmJiAhcmV2aWV3ZWQuaGFzKHByb3Bvc2FsSWQpO1xyXG4gICAgICB9XHJcbiAgICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnUkVBRFlfVE9fQ09OVElOVUUnIHx8IChleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLnJlY292ZXJhYmxlID09PSB0cnVlKSkge1xyXG4gICAgICAgIGlmIChyZWFkeVZlcnNpb24gIT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0KSB7XHJcbiAgICAgICAgICByZWFkeVZlcnNpb24gPSBleGVjdXRpb24udXBkYXRlZF9hdDsgcmVhZHlTaW5jZSA9IERhdGUubm93KCk7XHJcbiAgICAgICAgfVxyXG4gICAgICAgIC8vIFdoaWxlIGEgbGFyZ2UgY29udGludWF0aW9uIGlzIGdlbmVyYXRpbmcsIHRoZSBsYXN0IGNvbW1pdHRlZCBzZXJ2ZXJcclxuICAgICAgICAvLyBjaGVja3BvaW50IGNhbiBzdGlsbCBiZSBSRUFEWS4gQWN0IG9ubHkgd2hlbiB0aGUgVUkgb2ZmZXJzIGl0IHRvby5cclxuICAgICAgICBjb25zdCBidXR0b24gPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pXHJcbiAgICAgICAgICAuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBdWZ0cmFnIGZvcnRzZXR6ZW4nLCBleGFjdDogdHJ1ZSB9KTtcclxuICAgICAgICByZXR1cm4gRGF0ZS5ub3coKSAtIHJlYWR5U2luY2UgPiA1MDAwICYmIGF3YWl0IGJ1dHRvbi5ldmFsdWF0ZUFsbChidXR0b25zID0+IGJ1dHRvbnMuc29tZShidXR0b24gPT4gIShidXR0b24gYXMgSFRNTEJ1dHRvbkVsZW1lbnQpLmRpc2FibGVkICYmIGJ1dHRvbi5nZXRDbGllbnRSZWN0cygpLmxlbmd0aCA+IDAgJiYgZ2V0Q29tcHV0ZWRTdHlsZShidXR0b24pLnZpc2liaWxpdHkgIT09IFwiaGlkZGVuXCIpKTtcclxuICAgICAgfVxyXG4gICAgICByZXR1cm4gWydCTE9DS0VEJywgJ0ZBSUxFRCcsICdJTkNPTVBMRVRFJ10uaW5jbHVkZXMoZXhlY3V0aW9uPy5zdGF0ZSk7XHJcbiAgICB9O1xyXG4gICAgLy8gQSBzaW5nbGUgcG9sbCBwcmV2aW91c2x5IHRpbWVkIGFsbCBvZiBDYXBhY2l0eSAtPiBJbnRlbGxpZ2VuY2UgdG9nZXRoZXIuXHJcbiAgICAvLyBCb3VuZCBlYWNoIGdlbnVpbmUgc3RhZ2UgYWR2YW5jZSwgd2hpbGUgcmV0cmllcyBhbmQgcmVzdGFydHMgcmV0YWluIHRoZWlyXHJcbiAgICAvLyByZW1haW5pbmcgZGVhZGxpbmUuIFRoZSBpbmRlcGVuZGVudCAyMC1taW51dGUgdGVzdCB0aW1lb3V0IGlzIHVuY2hhbmdlZC5cclxuICAgIGxldCBhdHRlbXB0ID0gMDtcclxuICAgIHdoaWxlICghYXdhaXQgaXNDaGVja3BvaW50KCkpIHtcclxuICAgICAgY29uc3QgcmVtYWluaW5nID0gd2F0Y2hkb2cucmVtYWluaW5nKHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICAgICAgYXdhaXQgcGFnZS53YWl0Rm9yVGltZW91dChNYXRoLm1pbihbNTAwLCAxMDAwLCAyMDAwXVtNYXRoLm1pbihhdHRlbXB0KyssIDIpXSwgcmVtYWluaW5nKSk7XHJcbiAgICB9XHJcbiAgICBydW5JZCA/Pz0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZDtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkKS50b0JlKHJ1bklkKTtcclxuICAgIGlmIChzdGVwcy5ldmVyeShzdGVwID0+IGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzW3N0ZXBdKSkpIHtcclxuICAgICAgaWYgKGNyYXNoU2ltdWxhdGlvbikgZXhwZWN0KHJlc3RhcnRlZEpvYklkLCAnQSByZWFsIHJ1bm5pbmcgc2ltdWxhdGlvbiBtdXN0IGJlIG9ic2VydmVkIGFuZCBpbnRlcnJ1cHRlZC4nKS50b0JlVHJ1dGh5KCk7XHJcbiAgICAgIHJldHVybiB7IHJ1bklkLCByZXZpZXdlZDogWy4uLnJldmlld2VkXSwgcmVzdGFydGVkSm9iSWQgfTtcclxuICAgIH1cclxuICAgIGNvbnN0IGV4ZWN1dGlvbiA9IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uO1xyXG4gICAgY29uc3QgZGlhbG9nID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KTtcclxuICAgIGlmIChzdG9wT25FdmlkZW5jZUJsb2NrICYmIGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24uYmxvY2tpbmdfZmluZGluZ3M/Lmxlbmd0aCkge1xyXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoYFdpemFyZCBCTE9DS0VEIGF0ICR7ZXhlY3V0aW9uLnN0ZXB9OiAke2V4ZWN1dGlvbi5tZXNzYWdlfWApO1xyXG4gICAgfVxyXG4gICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24ubWVzc2FnZT8uaW5jbHVkZXMoJ1JFQURZX1dJVEhfV0FSTklOR1MnKSkge1xyXG4gICAgICBjb25zdCBiZWZvcmVSZXZpZXcgPSBhd2FpdCByZWFkV2FybmluZ1Jldmlld1N0YXRlKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgICBjb25zdCBwcmVmbGlnaHQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9wcmVmbGlnaHQnKTtcclxuICAgICAgY29uc3Qgd2FybmluZ3MgPSBkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdQcmVmbGlnaHQtV2FybnVuZ2VuJyB9KTtcclxuICAgICAgYXdhaXQgZXhwZWN0KHdhcm5pbmdzLmdldEJ5Um9sZSgnbGlzdGl0ZW0nKS5maXJzdCgpKS50b0JlVmlzaWJsZSgpO1xyXG4gICAgICBjb25zdCBzdGFydGVkID0gcGVyZm9ybWFuY2Uubm93KCksIHN0YXJ0ZWRXYWxsID0gRGF0ZS5ub3coKTtcclxuICAgICAgd2F0Y2hkb2cucmVtYWluaW5nKHN0YXJ0ZWQpO1xyXG4gICAgICBjb25zdCBhcHByb3ZhbFJlc3BvbnNlID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4gbmV3IFVSTChyZXNwb25zZS51cmwoKSkucGF0aG5hbWUgPT09ICcvYXBpL2VuZ2luZWVyaW5nL3ByZWZsaWdodC93YXJuaW5ncy9hcHByb3ZlJ1xyXG4gICAgICAgICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnLCB7IHRpbWVvdXQ6IDE4MF8wMDAgfSk7XHJcbiAgICAgIGF3YWl0IHdhcm5pbmdzLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnV2FybnVuZ2VuIGZyZWlnZWJlbiB1bmQgZm9ydHNldHplbicgfSkuY2xpY2soKTtcclxuICAgICAgY29uc3QgYXBwcm92ZWQgPSBhd2FpdCBhcHByb3ZhbFJlc3BvbnNlO1xyXG4gICAgICBjb25zdCByZWNlaXB0ID0gYXdhaXQgYXBwcm92ZWQuanNvbigpO1xyXG4gICAgICBjb25zdCBhZnRlclJldmlldyA9IGF3YWl0IHJlYWRXYXJuaW5nUmV2aWV3U3RhdGUocGFnZSwgcHJvamVjdCk7XHJcbiAgICAgIGNvbnN0IHByb29mID0geyBiZWZvcmU6IGJlZm9yZVJldmlldywgYWZ0ZXI6IGFmdGVyUmV2aWV3LCBzbmFwc2hvdElkOiBwcmVmbGlnaHQuaWQsXHJcbiAgICAgICAgcmVxdWVzdFByb2plY3Q6IGFwcHJvdmVkLnJlcXVlc3QoKS5oZWFkZXJzKClbJ3gtcHJvamVjdC1pZCddLCBzdWJtaXR0ZWQ6IGFwcHJvdmVkLnJlcXVlc3QoKS5wb3N0RGF0YUpTT04oKSxcclxuICAgICAgICBzdGF0dXM6IGFwcHJvdmVkLnN0YXR1cygpLCByZXNwb25zZTogcmVjZWlwdCwgc3RhcnRlZCwgc3RhcnRlZFdhbGwsIGZpbmlzaGVkV2FsbDogRGF0ZS5ub3coKSB9O1xyXG4gICAgICBjb25zdCBjb21taXR0ZWRBdCA9IHBlcmZvcm1hbmNlLm5vdygpO1xyXG4gICAgICBjb25zdCBjb21taXR0ZWQgPSB3YXRjaGRvZy5jb21taXRXYXJuaW5nUmV2aWV3KHByb29mLCBjb21taXR0ZWRBdCk7XHJcbiAgICAgIGF3YWl0IHRlc3QuaW5mbygpLmF0dGFjaCgndmVyaWZpZWQtd2FybmluZy1yZXZpZXctcHJvb2YnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvb2YsIGNvbW1pdHRlZEF0LCBjb21taXR0ZWQgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgICAgIHByb2dyZXNzTWlsZXN0b25lcy5nZXQodGVzdC5pbmZvKCkudGVzdElkKSEucHVzaCh7IGF0OiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksIG1hbnVhbFdhcm5pbmdBcHByb3ZhbDogY29tbWl0dGVkLmFwcHJvdmFsSWRlbnRpdHksXHJcbiAgICAgICAgZnJvbnRpZXI6IGNvbW1pdHRlZC5mcm9udGllciwgcHJvamVjdCwgZXhlY3V0aW9uOiBhZnRlclJldmlldy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbiwgYXBwcm92YWw6IHJlY2VpcHQuYXBwcm92YWwgfSk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKSkuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQsXHJcbiAgICAgICAgeyB0aW1lb3V0OiBleHBlY3RlZEhhcmR3YXJlLmxlbmd0aCA+IDEwMCA/IDE4MF8wMDAgOiA2MF8wMDAgfSkubm90LnRvQmUoZXhlY3V0aW9uLnVwZGF0ZWRfYXQpO1xyXG4gICAgICBjb250aW51ZTtcclxuICAgIH1cclxuICAgIGlmIChbJ0JMT0NLRUQnLCAnRkFJTEVEJywgJ0lOQ09NUExFVEUnXS5pbmNsdWRlcyhleGVjdXRpb24/LnN0YXRlKSAmJiBleGVjdXRpb24ucmVjb3ZlcmFibGUgIT09IHRydWUpIHtcclxuICAgICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XHJcbiAgICAgIGNvbnN0IGlkID0gY29udmVyc2F0aW9uLmRhdGE/LmFjdGl2ZV9wcm9wb3NhbDtcclxuICAgICAgY29uc3QgcHJvcG9zYWwgPSBpZCA/IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke2lkfWApIDogbnVsbDtcclxuICAgICAgYXdhaXQgdGVzdC5pbmZvKCkuYXR0YWNoKCd3aXphcmQtYmxvY2tlcicsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBleGVjdXRpb24sXHJcbiAgICAgICAgcHJvcG9zYWw6IHByb3Bvc2FsPy5kYXRhPy52YWxpZGF0aW9uX3Jlc3VsdCwgdmlzaWJsZTogYXdhaXQgZGlhbG9nLmlubmVyVGV4dCgpIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoYFdpemFyZCAke2V4ZWN1dGlvbi5zdGF0ZX0gYXQgJHtleGVjdXRpb24uc3RlcH06ICR7ZXhlY3V0aW9uLm1lc3NhZ2V9YCk7XHJcbiAgICB9XHJcbiAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JFQURZX1RPX0NPTlRJTlVFJyB8fCAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5yZWNvdmVyYWJsZSA9PT0gdHJ1ZSkpIHtcclxuICAgICAgY29uc3QgYnV0dG9uID0gZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQXVmdHJhZyBmb3J0c2V0emVuJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgICAgIHRyeSB7XHJcbiAgICAgICAgYXdhaXQgYnV0dG9uLmNsaWNrKHsgdGltZW91dDogMjAwMCB9KTtcclxuICAgICAgfSBjYXRjaCAoZXJyb3IpIHtcclxuICAgICAgICBjb25zdCBsYXRlc3QgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgICBpZiAobGF0ZXN0LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0ID09PSBleGVjdXRpb24udXBkYXRlZF9hdCAmJiBhd2FpdCBidXR0b24uZXZhbHVhdGVBbGwoYnV0dG9ucyA9PiBidXR0b25zLnNvbWUoYnV0dG9uID0+ICEoYnV0dG9uIGFzIEhUTUxCdXR0b25FbGVtZW50KS5kaXNhYmxlZCAmJiBidXR0b24uZ2V0Q2xpZW50UmVjdHMoKS5sZW5ndGggPiAwICYmIGdldENvbXB1dGVkU3R5bGUoYnV0dG9uKS52aXNpYmlsaXR5ICE9PSBcImhpZGRlblwiKSkpIHRocm93IGVycm9yO1xyXG4gICAgICAgIGNvbnRpbnVlO1xyXG4gICAgICB9XHJcbiAgICAgIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcclxuICAgICAgICBjb25zdCBsYXRlc3QgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgICByZXR1cm4gbGF0ZXN0LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0ICE9PSBleGVjdXRpb24udXBkYXRlZF9hdFxyXG4gICAgICAgICAgfHwgbGF0ZXN0LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JVTk5JTkcnXHJcbiAgICAgICAgICB8fCBsYXRlc3Quc3RhdHVzZXM/LltleGVjdXRpb24uc3RlcF0gPT09ICdJTl9QUk9HUkVTUyc7XHJcbiAgICAgIH0sIHsgdGltZW91dDogNjBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbiAgICAgIGNvbnRpbnVlO1xyXG4gICAgfVxyXG4gICAgY29uc3QgY2FuZGlkYXRlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7cHJvcG9zYWxJZH1gKTtcclxuICAgIGlmIChjYW5kaWRhdGUuZGF0YS5wcm9wb3NhbF90eXBlID09PSAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJyAmJiByZXZpZXdDb3VudCA9PT0gMCAmJiBleHBlY3RlZEhhcmR3YXJlLmxlbmd0aCkge1xyXG4gICAgICBjb25zdCBoYXJkd2FyZSA9IGNhbmRpZGF0ZS5kYXRhLmNoYW5nZXNcclxuICAgICAgICAuZmlsdGVyKChjaGFuZ2U6IHsgb2JqZWN0X3R5cGU6IHN0cmluZyB9KSA9PiBjaGFuZ2Uub2JqZWN0X3R5cGUgPT09ICdIYXJkd2FyZU5vZGUnKVxyXG4gICAgICAgIC5tYXAoKGNoYW5nZTogeyBkYXRhOiB7IG5hbWU6IHN0cmluZyB9IH0pID0+IGNoYW5nZS5kYXRhLm5hbWUpO1xyXG4gICAgICBleHBlY3QoaGFyZHdhcmUsICdUaGUgVUkgbXVzdCBwcmVzZXJ2ZSB0aGUgaGFyZHdhcmUgZXhwbGljaXRseSBuYW1lZCBpbiB0aGUgdXNlciByZXF1ZXN0LicpXHJcbiAgICAgICAgLnRvRXF1YWwoZXhwZWN0LmFycmF5Q29udGFpbmluZyhleHBlY3RlZEhhcmR3YXJlKSk7XHJcbiAgICB9XHJcbiAgICBleHBlY3QocmV2aWV3ZWQuaGFzKHByb3Bvc2FsSWQpLCAnVGhlIHNhbWUgcHJvcG9zYWwgbXVzdCBub3QgcmVxdWVzdCByZXZpZXcgdHdpY2UuJykudG9CZShmYWxzZSk7XG4gICAgaWYgKGJlZm9yZVByb3Bvc2FsUmV2aWV3KSBhd2FpdCBiZWZvcmVQcm9wb3NhbFJldmlldyhwcm9wb3NhbElkLCBjYW5kaWRhdGUuZGF0YS5wcm9wb3NhbF90eXBlKTtcbiAgICBjb25zdCBhcHBseVJlc3BvbnNlID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4gcmVzcG9uc2UudXJsKCkuaW5jbHVkZXMoYC9wcm9wb3NhbHMvJHtwcm9wb3NhbElkfS9hcHByb3ZlLWFwcGx5YCkgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcsIHsgdGltZW91dDogMTgwXzAwMCB9KTtcclxuICAgIGNvbnN0IGFwcHJvdmFsID0gZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAvXihGcmVpZ2ViZW4sIMO8YmVybmVobWVuICYgZm9ydGZhaHJlbnzDnGJlcm5laG1lbiAmIGZvcnRmYWhyZW4pJC8gfSk7XHJcbiAgICBhd2FpdCBleHBlY3QoYXBwcm92YWwpLnRvQmVFbmFibGVkKHsgdGltZW91dDogNjBfMDAwIH0pO1xyXG4gICAgYXdhaXQgYXBwcm92YWwuY2xpY2soKTtcclxuICAgIGNvbnN0IGFwcGxpZWQgPSBhd2FpdCBhcHBseVJlc3BvbnNlO1xyXG4gICAgaWYgKCFhcHBsaWVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke2FwcGxpZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBhcHBsaWVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgICBleHBlY3QoKGF3YWl0IGFwcGxpZWQuanNvbigpKS5kYXRhLnN0YXR1cykudG9CZSgnQVBQTElFRCcpO1xyXG4gICAgcmV2aWV3ZWQuYWRkKHByb3Bvc2FsSWQpOyByZXZpZXdDb3VudCsrO1xyXG4gICAgLy8gQSBkaXN0aW5jdCwgYWN0dWFsbHkgY29tbWl0dGVkIG1hbnVhbCByZXZpZXcgc3RhcnRzIHRoZSBuZXh0IGF1dG9tYXRpY1xyXG4gICAgLy8gc2VjdGlvbi4gSXRzIHdyaXRlIHN0aWxsIGhhcyB0aGUgc2VwYXJhdGUgdW5jaGFuZ2VkIDE4MC1zZWNvbmQgbGltaXQuXHJcbiAgICB3YXRjaGRvZyA9IG5ldyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nKHBlcmZvcm1hbmNlLm5vdygpLCB3b3JrZmxvdyk7XHJcbiAgICBpZiAoY2FuZGlkYXRlLmRhdGEucHJvcG9zYWxfdHlwZSA9PT0gJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcgJiYgZXhwZWN0ZWRTaWduYWxzKSB7XHJcbiAgICAgIGF3YWl0IHZlcmlmeVNpZ25hbENvbnRyYWN0cyhwYWdlLCBwcm9qZWN0LCBleHBlY3RlZFNpZ25hbHMpO1xyXG4gICAgfVxyXG4gICAgaWYgKHJldmlld0NvdW50ID09PSAxICYmIGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQpIHtcclxuICAgICAgYXdhaXQgYWZ0ZXJGaXJzdE1vZGVsQXBwbGllZCgpO1xyXG4gICAgICAvLyBUaGlzIG9uZSB0ZXN0IGV4cGxpY2l0bHkgc3VibWl0cyBBTUVORCBhbmQgd2FpdHMgZm9yIGl0cyByZWNlaXB0LiBPbmx5XHJcbiAgICAgIC8vIHRoYXQgZGVsaWJlcmF0ZSBhY3Rpb24gcGVybWl0cyBiaW5kaW5nIGl0cyBuZXcgcmVxdWVzdCByZXZpc2lvbi5cclxuICAgICAgY29uc3QgYW1lbmRlZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICBleHBlY3QoYW1lbmRlZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkKS50b0JlKHJ1bklkKTtcclxuICAgICAgd2F0Y2hkb2cgPSBuZXcgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyhwZXJmb3JtYW5jZS5ub3coKSwgYW1lbmRlZCk7XHJcbiAgICB9XHJcbiAgICBpZiAocmV2aWV3Q291bnQgPT09IDEpIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7IC8vIER1cmFibGUgcmVsb2FkIGFmdGVyIGEgcmVhbCBjb21taXQuXHJcbiAgICBpZiAocmVzdGFydCAmJiByZXZpZXdDb3VudCA9PT0gMikge1xyXG4gICAgICBhd2FpdCByZXN0YXJ0QXBwbGljYXRpb24ocGFnZSk7XHJcbiAgICAgIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgICB9XHJcbiAgICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICAgIGNvbnN0IGN1cnJlbnQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgcmV0dXJuIGN1cnJlbnQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQgIT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0O1xyXG4gICAgfSwgeyB0aW1lb3V0OiA2MF8wMDAgfSkudG9CZSh0cnVlKTtcclxuICB9XHJcbiAgdGhyb3cgbmV3IEVycm9yKCdXaXphcmQgZXhjZWVkZWQgMTYgcmV2aWV3L2NvbnRpbnVhdGlvbiBjaGVja3BvaW50cy4nKTtcclxufVxyXG5cclxudGVzdCgnd2l6YXJkIHJlZnVzZXMgYW4gdW5hdmFpbGFibGUgY2F0YWxvZyBhbmQgcmVjb3ZlcnMgdXNpbmcgdGhlIHJlYWwgcmVnaXN0cnkgQGNhdGFsb2ctcmVjb3ZlcnknLCBhc3luYyAoe3BhZ2V9KSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWNhdGFsb2ctcmVjb3ZlcnktJyArIHJhbmRvbVVVSUQoKTtcclxuICBhd2FpdCBwYWdlLnJvdXRlKCcqKi9hcGkvdGVjaG5vbG9naWVzJywgcm91dGUgPT4gcm91dGUuZnVsZmlsbCh7c3RhdHVzOjUwMyxcclxuICAgIGNvbnRlbnRUeXBlOidhcHBsaWNhdGlvbi9qc29uJyxib2R5OkpTT04uc3RyaW5naWZ5KHtlcnJvcjonRGVyIHZvbGxzdMOkbmRpZ2UgVGVjaG5vbG9naWVrYXRhbG9nIGlzdCBkZXJ6ZWl0IG5pY2h0IGVycmVpY2hiYXIuJ30pfSkpO1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2FsZXJ0JykpLnRvQ29udGFpblRleHQoJ1RlY2hub2xvZ2lla2F0YWxvZycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdQcm9qZWt0bmFtZScsIHtleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cubG9jYXRvcignI2VuZ2luZWVyaW5nLXByb2plY3QtbmFtZScpLmZpbGwoJ0NhdGFsb2cgcmV0cnknKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHtleGFjdDp0cnVlfSkuZmlsbCgnZWluIEFrdG9yIHp1bSBwcm9wb3J0aW9uYWwgc2NobGllw59lbiBlaW5lcyBWZW50aWwnKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKSkudG9CZURpc2FibGVkKCk7XHJcbiAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzKS50b0hhdmVMZW5ndGgoMCk7XHJcbiAgYXdhaXQgcGFnZS51bnJvdXRlKCcqKi9hcGkvdGVjaG5vbG9naWVzJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonVGVjaG5vbG9naWVrYXRhbG9nIGVybmV1dCBsYWRlbid9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdhbGVydCcpKS50b0hhdmVDb3VudCgwKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKSkudG9CZUVuYWJsZWQoKTtcclxuICBjb25zdCBjYXRhbG9nID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvdGVjaG5vbG9naWVzJykpLmpzb24oKTtcclxuICBleHBlY3QoY2F0YWxvZy50ZWNobm9sb2d5X2NvdW50KS50b0JlKDEyNSk7XHJcbn0pO1xyXG5cclxudGVzdCgnbmV3IHNtYWxsIHdpemFyZCB0cmF2ZXJzZXMgYWxsIG5pbmUgc3RhZ2VzIGFuZCBzdXJ2aXZlcyByZWxvYWQvcmVzdGFydCBAc21hbGwnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgZXJyb3JzOiBzdHJpbmdbXSA9IFtdOyBwYWdlLm9uKCdwYWdlZXJyb3InLCBlcnJvciA9PiBlcnJvcnMucHVzaChlcnJvci5tZXNzYWdlKSk7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXNtYWxsLScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdFMkUgc21hbGwnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCgnRXJ6ZXVnZSBlaW4gQXV0b21vdGl2ZSBDQU4tRkQgTmV0endlcmsgbWl0IGVpbmVtIEdhdGV3YXkgU3lzdGVtLCBkZW4gRUNVcyBNb3RvcnN0ZXVlcnVuZyB1bmQgQW56ZWlnZSwgZWluZW0gU2Vuc29yIE1vdG9yVGVtcGVyYXR1cmUgdW5kIGVpbmVtIEFrdG9yIE1vdG9yVmFsdmUuIE1vdG9yVGVtcGVyYXR1cmUgd2lyZCB2b24gTW90b3JzdGV1ZXJ1bmcgYXVzZ2V3ZXJ0ZXQuIE1vdG9yc3RldWVydW5nIHN0ZXVlcnQgTW90b3JWYWx2ZS4gQ29udHJvbGxlcnN0YXR1cyBibGVpYnQgYmlzIHp1ciBBdXN3YWhsIGtvbmtyZXRlciBFbXBmw6RuZ2VyIHVuZCBTaWduYWxlIGludGVybi4gUHLDvGZlIHVuZCBhcmJlaXRlIGJpcyBEYXRhIFNjaWVuY2UgJiBJbnRlbGxpZ2VuY2UuXFxuQ0FOLUZEOiA1MDAga2JpdC9zIGFyYml0cmF0aW9uLCAyIE1iaXQvcyBkYXRhXFxuQ0FOOiA1MDAga2JpdC9zJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1dlaXRlcmUgSGlud2Vpc2UnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwoJy0gQWt0b3ItQmVmZWhsZToge1wiTW90b3JWYWx2ZVwiOntcImxlbmd0aF9iaXRzXCI6MSxcImRhdGFfdHlwZVwiOlwiYm9vbGVhblwiLFwiZmFjdG9yXCI6MSxcInVuaXRcIjpcImNvZGVcIixcIm1pbl92YWx1ZVwiOjAsXCJtYXhfdmFsdWVcIjoxLFwic2VtYW50aWNcIjp7XCJzZW1hbnRpY190eXBlXCI6XCJCT09MRUFOXCJ9LFwiZGF0YVwiOntcImVudW1fdmFsdWVzXCI6e1wiQ0xPU0VcIjowLFwiT1BFTlwiOjF9fX19Jyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ0dlcsOkdGV1bWZhbmcnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgZm9yIChjb25zdCBbbGFiZWwsIHZhbHVlXSBvZiBbWydHYXRld2F5cycsICcxJ10sIFsnQ29udHJvbGxlcicsICcyJ10sIFsnU2Vuc29yZW4nLCAnMSddLCBbJ0FrdG9yZW4nLCAnMSddXSkgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoYCR7bGFiZWx9OiB2ZXJiaW5kbGljaGUgQW56YWhsYCwgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHZhbHVlKTtcclxuICBjb25zdCBzdGFydFJlcXVlc3QgPSBwYWdlLndhaXRGb3JSZXF1ZXN0KHJlcXVlc3QgPT4gcmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JylcclxuICAgICYmIHJlcXVlc3QubWV0aG9kKCkgPT09ICdQT1NUJyAmJiByZXF1ZXN0LnBvc3REYXRhSlNPTigpPy53aXphcmRfY29tbWFuZD8uYWN0aW9uID09PSAnU1RBUlQnKTtcclxuICAvLyBVc2UgdGhlIHNhbWUgdmlzaWJsZSBxdWVzdGlvbm5haXJlIG5hdmlnYXRpb24gYSB1c2VyIHVzZXM7IG5ldmVyIGluamVjdCBnZW5lcmF0ZWQgbW9kZWwgcm93cy5cclxuICBmb3IgKGxldCBzdGVwID0gMDsgc3RlcCA8IDEwOyBzdGVwKyspIHtcclxuICAgIGNvbnN0IHN1Ym1pdCA9IGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJyk7XHJcbiAgICBhd2FpdCBleHBlY3Qoc3VibWl0KS50b0JlRW5hYmxlZCgpO1xyXG4gICAgY29uc3QgbmFtZSA9IGF3YWl0IHN1Ym1pdC5pbm5lclRleHQoKTtcclxuICAgIGF3YWl0IHN1Ym1pdC5jbGljaygpO1xyXG4gICAgaWYgKG5hbWUgPT09ICfDnGJlcm5laG1lbicpIGJyZWFrO1xyXG4gICAgaWYgKHN0ZXAgPT09IDkpIHRocm93IG5ldyBFcnJvcignUXVlc3Rpb25uYWlyZSBkaWQgbm90IG9mZmVyIHN1Ym1pdC4nKTtcclxuICB9XHJcbiAgY29uc3QgcmVxdWVzdGVkID0gKGF3YWl0IHN0YXJ0UmVxdWVzdCkucG9zdERhdGFKU09OKCkud2l6YXJkX2NvbW1hbmQud2l6YXJkX2NvbnRleHQ7XHJcbiAgZXhwZWN0KHJlcXVlc3RlZC50ZWNobm9sb2dpZXMsICdBbiBleHBsaWNpdCBDQU4tRkQgdGFzayBtdXN0IG5vdCBzaWxlbnRseSByZXF1ZXN0IExJTiBhbmQgU09NRS9JUC4nKS50b0VxdWFsKFsnQ0FOLUZEIChjYW5fZmQpJ10pO1xyXG4gIC8vIFByZXNlcnZlIGEgcmVhbCBwZW5kaW5nIG1vZGVsIHRocm91Z2ggcGFyYW1ldGVyIHNhdmUgYW5kIHJlbmV3ZWQgcmV2aWV3LlxyXG4gIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IChhd2FpdCByZWFkUHJvamVjdChwYWdlLHByb2plY3QsJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5JykpLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5zdGF0ZSxcclxuICAgIHt0aW1lb3V0OjE4MDAwMH0pLnRvQmUoJ1JFVklFV19SRVFVSVJFRCcpO1xyXG4gIGNvbnN0IHBlbmRpbmcgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSxwcm9qZWN0LCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpKS5kYXRhLmFjdGl2ZV9wcm9wb3NhbDtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8/bW9kZT1wYXJhbWV0ZXJzJnByb2plY3Q9JHtwcm9qZWN0fSZ0ZWNobm9sb2d5PWNhbl9mZCZwcm9wb3NhbD0ke3BlbmRpbmd9I3BhcmFtZXRlci1maW5kaW5nc2ApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgncmVnaW9uJyx7bmFtZTonQWt0dWVsbGUgUGFyYW1ldGVyYmVmdW5kZSd9KSkudG9Db250YWluVGV4dCgnbm9jaCBuaWNodCDDvGJlcm5vbW1lbmVuIFZvcnNjaGxhZ3MnKTtcclxuICBjb25zdCBjb21tb24gPSBwYWdlLmxvY2F0b3IoJy5wYXJhbWV0ZXItZ3JvdXAtY29tbW9uJyk7XHJcbiAgYXdhaXQgZXhwZWN0KGNvbW1vbi5sb2NhdG9yKCcjYXJiaXRyYXRpb25fYml0cmF0ZScpKS50b0hhdmVWYWx1ZSgnNTAwIGtiaXQvcycpO1xyXG4gIGF3YWl0IGV4cGVjdChjb21tb24ubG9jYXRvcignI2RhdGFfYml0cmF0ZScpKS50b0hhdmVWYWx1ZSgnMiBNYml0L3MnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcucGFyYW1ldGVyLWRldGFpbHNbb3Blbl0nKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgYXdhaXQgcmVwZWF0UGFyYW1ldGVyUmV0dXJuKHBhZ2UsIHByb2plY3QsIHBlbmRpbmcsIFt7dGVjaG5vbG9neTogJ2Nhbl9mZCcsXG4gICAgZmllbGRzOiB7YXJiaXRyYXRpb25fYml0cmF0ZTogJzUwMCBrYml0L3MnLCBkYXRhX2JpdHJhdGU6ICcxIE1iaXQvcycsIGNhbl9mZF9kYXRhX3ByZXNjYWxlcjogJzInfSxcbiAgICBuYXRpdmU6IHthcmJpdHJhdGlvbl9iaXRyYXRlOiA1MDBfMDAwLCBkYXRhX2JpdHJhdGU6IDFfMDAwXzAwMCwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyOiAyfSxcbiAgICBlZGl0RmllbGRzOiBbJ2RhdGFfYml0cmF0ZScsICdjYW5fZmRfZGF0YV9wcmVzY2FsZXInXX1dKTtcbiAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLHByb2plY3QsYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7cGVuZGluZ30/dmlldz1zdGF0dXNgKSkuZGF0YS5jYW5vbmljYWxfaWRzKS50b0VxdWFsKFtdKTtcbiAgZXhwZWN0KChhd2FpdCBhbGxPYmplY3RzKHBhZ2UscHJvamVjdCwnaGFyZHdhcmUtbm9kZXMnKSkpLnRvSGF2ZUxlbmd0aCgwKTtcbiAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCB0cnVlLFxyXG4gICAgWydTeXN0ZW0nLCAnTW90b3JzdGV1ZXJ1bmcnLCAnQW56ZWlnZScsICdNb3RvclRlbXBlcmF0dXJlJywgJ01vdG9yVmFsdmUnXSk7XHJcbiAgY29uc3QgYXJ0aWZhY3RzID0gYXdhaXQgdmVyaWZ5QXJ0aWZhY3RzKHBhZ2UsIHByb2plY3QsIDUsIHVuZGVmaW5lZCwge1xyXG4gICAgc2VlZDogNDIsIGRhdGFfYml0cmF0ZTogMV8wMDBfMDAwLCBjYW5fZmRfZGF0YV9wcmVzY2FsZXI6IDIsXHJcbiAgfSk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50Lm9ic2VydmVkX3NpZ25hbF9jb3VudCkudG9CZUdyZWF0ZXJUaGFuT3JFcXVhbCgzKTtcclxuICBleHBlY3QoYXJ0aWZhY3RzLmFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UudHJhbnNwb3J0X2V4Y2x1c2lvbnMpLnRvSGF2ZUxlbmd0aCgzKTtcclxuICBjb25zdCBmaW5pc2hlZCA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IHJlc3BvbnNlLnVybCgpLmluY2x1ZGVzKGAvcnVucy8ke2NvbnRpbnVpdHkucnVuSWR9L2ZpbmlzaGApXHJcbiAgICAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRmVydGlnIHN0ZWxsZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGV4cGVjdCgoYXdhaXQgZmluaXNoZWQpLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZykubm90LnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBleHBlY3QoKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnMpLnRvSGF2ZUxlbmd0aCgxKTtcclxuICBleHBlY3QoZXJyb3JzKS50b0VxdWFsKFtdKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2V2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIC4uLmNvbnRpbnVpdHksIC4uLmFydGlmYWN0cyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxufSk7XHJcblxyXG5mb3IgKGNvbnN0IHRlY2hub2xvZ3kgb2YgWydJMkMnLCAnTW9kYnVzIFJUVSddKSB7XHJcbiAgdGVzdChgUmFzcGJlcnJ5IFBpICR7dGVjaG5vbG9neX0gcHJvamVjdCByZXRhaW5zIG1vZGVsIGFuZCBibG9ja3MgaW5jb25zaXN0ZW50IG5hdGl2ZSBwYXJhbWV0ZXJzIEBub25hdXRvbW90aXZlYCwgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gICAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWVtYmVkZGVkLScgKyByYW5kb21VVUlEKCk7XHJcbiAgICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdUZW1wZXJhdHVycmVnZWx1bmcnKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdQcm9qZWt0YmVzY2hyZWlidW5nJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHRlY2hub2xvZ3kgPT09ICdJMkMnXHJcbiAgICAgID8gJzIgQWt0b3JlbiBmw7xyIFZlbnRpbGUsIDQgU2Vuc29yZW4gZsO8ciBUZW1wZXJhdHVyZW4sIHVuZCBlaW4gUmFzcGJlcnJ5UGknXHJcbiAgICAgIDogYDIgQWt0b3JlbiBmw7xyIFZlbnRpbGUsIDQgU2Vuc29yZW4gZsO8ciBUZW1wZXJhdHVyZW4sIHVuZCBlaW4gUmFzcGJlcnJ5UGkuIEVtYmVkZGVkIFN5c3RlbXMuIEFsbGUgR2Vyw6R0ZSBrb21tdW5pemllcmVuIMO8YmVyICR7dGVjaG5vbG9neX0uIFByw7xmZSB1bmQgYXJiZWl0ZSBiaXMgRGF0YSBTY2llbmNlICYgSW50ZWxsaWdlbmNlLmApO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ05ldHphcmNoaXRla3R1cicsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ3JhZGlvJywgeyBuYW1lOiAvVmFyaWFudGUgMC8gfSkuY2hlY2soKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdHZXLDpHRldW1mYW5nJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Jhc3BiZXJyeVBpOiBBbnNjaGx1c3MnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignSTJDJyk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlMYWJlbCgnVGVtcGVyYXR1cnNlbnNvcjE6IEFuc2NobHVzcycsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZVZhbHVlKCcnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgICBmb3IgKGNvbnN0IG5hbWUgb2YgWydSYXNwYmVycnlQaScsICdUZW1wZXJhdHVyc2Vuc29yMScsICdUZW1wZXJhdHVyc2Vuc29yMicsICdUZW1wZXJhdHVyc2Vuc29yMycsICdUZW1wZXJhdHVyc2Vuc29yNCcsICdWZW50aWxha3RvcjEnLCAnVmVudGlsYWt0b3IyJ10pIHtcclxuICAgICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbChgJHtuYW1lfTogQW5zY2hsdXNzYCwgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ0kyQycpO1xyXG4gICAgICB9XHJcbiAgICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdTZW5zb3IgMTogTWVzc2dyw7bDn2UnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignc3BlZWQnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeUxhYmVsKCdUZW1wZXJhdHVyc2Vuc29yMTogQW5zY2hsdXNzJywgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoJ0kyQycpO1xyXG4gICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnU2Vuc29yIDE6IE1lc3NncsO2w59lJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ3RlbXBlcmF0dXJlJyk7XHJcbiAgICB9XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnVmVudGlsYWt0b3IxOiBTdGVsbGJlZmVobCcsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdPUEVOX0NMT1NFJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMjogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnVmVudGlsYWt0b3IyOiBTdGVsbGJlZmVobCcsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdPUEVOX0NMT1NFJyk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBleHBlY3QoY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIHRydWUsIFsnUmFzcGJlcnJ5UGknLCAnVGVtcGVyYXR1cnNlbnNvcjEnLCAnVGVtcGVyYXR1cnNlbnNvcjInLCAnVGVtcGVyYXR1cnNlbnNvcjMnLCAnVGVtcGVyYXR1cnNlbnNvcjQnLCAnVmVudGlsYWt0b3IxJywgJ1ZlbnRpbGFrdG9yMiddLCBmYWxzZSwgdW5kZWZpbmVkLCB1bmRlZmluZWQsIHRydWUpKVxyXG4gICAgICAucmVqZWN0cy50b1Rocm93KC9XaXphcmQgQkxPQ0tFRCBhdCBwYXJhbWV0ZXJzOi4qYmVzdMOkdGlndGUgQW5nYWJlbi8pO1xyXG4gICAgY29uc3Qgd29ya2Zsb3cgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpO1xyXG4gICAgY29uc3QgZmluZGluZ3MgPSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbi5ibG9ja2luZ19maW5kaW5ncyBhcyB7IGNvZGU6IHN0cmluZyB9W107XHJcbiAgICBleHBlY3QoZmluZGluZ3MubWFwKGl0ZW0gPT4gaXRlbS5jb2RlKSkudG9Db250YWluKCdURUNITk9MT0dZX1BBUkFNRVRFUl9ERVBFTkRFTkNZX01JU01BVENIJyk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuc3RhdHVzZXMucGFyYW1ldGVycykudG9CZSgnSU5fUFJPR1JFU1MnKTtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5hcnRpZmFjdF9jaGVja3MucGFyYW1ldGVycy5jb21wbGV0ZSkudG9CZShmYWxzZSk7XHJcbiAgICBjb25zdCByZXF1aXJlZCA9IHdvcmtmbG93LmFydGlmYWN0X2NoZWNrcy5wYXJhbWV0ZXJzLnJlcXVpcmVkO1xyXG4gICAgZXhwZWN0KHJlcXVpcmVkLnByb2ZpbGVfdmFsdWVzKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IGRldmljZVNvdXJjZSA9IHRlY2hub2xvZ3kgPT09ICdJMkMnID8gJ2kyY19kZXZpY2Vfc291cmNlJyA6ICdtcl9kZXZpY2Vfc291cmNlJztcclxuICAgIC8vIFRoZXNlIHNjZW5hcmlvcyByZW1haW4gYmxvY2tlZCBieSByZWFsIG5hdGl2ZSBkZXBlbmRlbmNpZXMsIG5vdCBieSB0aGVcclxuICAgIC8vIGFic2VuY2Ugb2YgYSByZWFsIGRldmljZSBxdWFsaWZpY2F0aW9uIG9yIGZhYnJpY2F0ZWQgc291cmNlIGlkZW50aWZpZXIuXHJcbiAgICBleHBlY3QocmVxdWlyZWQpLm5vdC50b0hhdmVQcm9wZXJ0eShkZXZpY2VTb3VyY2UsIGZhbHNlKTtcclxuICAgIGNvbnN0IG5hdGl2ZVRlY2hub2xvZ3kgPSB0ZWNobm9sb2d5ID09PSAnSTJDJyA/ICdpMmMnIDogJ21vZGJ1c19ydHUnO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnNbbmF0aXZlVGVjaG5vbG9neV0udmFsdWVzKVxyXG4gICAgICAubm90LnRvSGF2ZVByb3BlcnR5KGRldmljZVNvdXJjZSk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuYXJ0aWZhY3RfY2hlY2tzLnBhcmFtZXRlcnMucHJvZmlsZV9maW5kaW5ncy5zb21lKChmaW5kaW5nOiB7Y29kZTogc3RyaW5nfSkgPT5cclxuICAgICAgZmluZGluZy5jb2RlID09PSAnVEVDSE5PTE9HWV9QQVJBTUVURVJfREVQRU5ERU5DWV9NSVNNQVRDSCcpKS50b0JlKHRydWUpO1xyXG4gICAgY29uc3QgZXZpZGVuY2VSZXZpZXcgPSBkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7bmFtZTogJ0Jsb2NraWVyZW5kZSBQcmVmbGlnaHQtQmVmdW5kZSd9KTtcclxuICAgIGF3YWl0IGV4cGVjdChldmlkZW5jZVJldmlldykudG9Db250YWluVGV4dCh0ZWNobm9sb2d5ID09PSAnSTJDJyA/ICdpMmNfcHVsbHVwX29obXMnIDogJ21yX3BkdV9ieXRlcycpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGV2aWRlbmNlUmV2aWV3LmdldEJ5Um9sZSgnbGluaycsIHtuYW1lOiAnQmV0cm9mZmVuZSBBbmdhYmVuIGJlYXJiZWl0ZW4nfSkuZmlyc3QoKSlcclxuICAgICAgLnRvSGF2ZUF0dHJpYnV0ZSgnaHJlZicsIG5ldyBSZWdFeHAoYG1vZGU9cGFyYW1ldGVycy4qcHJvamVjdD0ke3Byb2plY3R9YCkpO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LnN0YXR1c2VzLnNpbXVsYXRpb24pLnRvQmUoJ0VNUFRZJyk7XHJcbiAgICBpZiAodGVjaG5vbG9neSA9PT0gJ0kyQycpIHtcclxuICAgICAgZXhwZWN0KHdvcmtmbG93LnBhcmFtZXRlcnMucmF0ZV9yZXZpZXdfcHJvcG9zYWxzLmkyYy5zdGF0dXMpLnRvQmUoJ1JFVklFV19SRVFVSVJFRCcpO1xyXG4gICAgICBleHBlY3Qod29ya2Zsb3cucGFyYW1ldGVycy5wYXJhbWV0ZXJfcHJvdmVuYW5jZS5iaXRyYXRlLnNvdXJjZSkudG9CZSgnVEVDSE5PTE9HWV9QUk9GSUxFX1JFVklFV19QUk9QT1NBTCcpO1xyXG4gICAgfVxyXG4gICAgY29uc3QgaW50ZXJmYWNlcyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLWludGVyZmFjZXMnKTtcclxuICAgIGV4cGVjdChpbnRlcmZhY2VzLmxlbmd0aCkudG9CZUdyZWF0ZXJUaGFuT3JFcXVhbCg3KTtcclxuICAgIGV4cGVjdChpbnRlcmZhY2VzLmV2ZXJ5KGl0ZW0gPT4gIS9hdXRvbW90aXZlfGNhbnxsaW4vaS50ZXN0KGl0ZW0udGVjaG5vbG9neSkpKS50b0JlKHRydWUpO1xyXG4gICAgY29uc3QgaGFyZHdhcmUgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gICAgZXhwZWN0KGhhcmR3YXJlLmV2ZXJ5KGl0ZW0gPT4gaXRlbS5kb21haW4gIT09ICdhdXRvbW90aXZlJykpLnRvQmUodHJ1ZSk7XHJcbiAgICBpZiAodGVjaG5vbG9neSA9PT0gJ0kyQycpIHtcclxuICAgICAgY29uc3Qgc2lnbmFscyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ3NpZ25hbHMnKTtcclxuICAgICAgZXhwZWN0KHNpZ25hbHMuc29tZShpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ1RlbXBlcmF0dXJfVGVtcGVyYXR1cnNlbnNvcjEnICYmIGl0ZW0udW5pdCA9PT0gJ2RlZ0MnKSkudG9CZSh0cnVlKTtcclxuICAgIH1cclxuICAgIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icykudG9IYXZlTGVuZ3RoKDApO1xyXG4gICAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdub25hdXRvbW90aXZlLWV2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIHRlY2hub2xvZ3ksIGZpbmRpbmdzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gIH0pO1xyXG59XHJcblxyXG50ZXN0KCdleGFjdCBjb25maXJtZWQgNTAvMjUwLzI1MCByZXF1ZXN0IGNvbXBsZXRlcyB0aHJvdWdoIHJlYWwgd2l6YXJkIHJldmlldyBAbGFyZ2UnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XG4gIGNvbnN0IGVycm9yczogc3RyaW5nW10gPSBbXTsgcGFnZS5vbigncGFnZWVycm9yJywgZXJyb3IgPT4gZXJyb3JzLnB1c2goZXJyb3IubWVzc2FnZSkpO1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1sYXJnZS0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IHJ1bklkID0gcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IG9yaWdpbmFsID0gYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2UtNTAtMjUwLTI1MC50eHQnLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpO1xyXG4gIGNvbnN0IG1ldGFkYXRhID0gSlNPTi5wYXJzZShhd2FpdCByZWFkRmlsZShuZXcgVVJMKCcuL2ZpeHR1cmVzL3dpemFyZC1sYXJnZS01MC0yNTAtMjUwLmpzb24nLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpKTtcclxuICBjb25zdCBiYXNlbGluZSA9IEpTT04ucGFyc2UoYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2Utc2lnbmFsLWNvbnRyYWN0cy5qc29uJywgaW1wb3J0Lm1ldGEudXJsKSwgJ3V0ZjgnKSk7XHJcbiAgY29uc3QgcHJvbXB0ID0gb3JpZ2luYWwucmVwbGFjZSgvXi0gTGF1Zi1JRDouKiQvbSwgJy0gTGF1Zi1JRDogJyArIHJ1bklkKTtcclxuICBhd2FpdCByZXZpZXdWaXJ0dWFsVHJhbnNwb3J0cyhwYWdlLCBwcm9qZWN0LCB0cnVlKTtcbiAgLy8gUmVwbGF5IHRoZSBjYXB0dXJlZCwgYWxyZWFkeSBjb25maXJtZWQgaW5wdXQgdGhyb3VnaCB0aGUgbm9ybWFsIFNUQVJUIEFQSS5cclxuICAvLyBBbGwgcHJvcG9zYWwgaW5zcGVjdGlvbiwgYXBwcm92YWwsIGNvbnRpbnVhdGlvbiBhbmQgcmVsb2FkcyBiZWxvdyB1c2UgVUkuXHJcbiAgY29uc3Qgc3RhcnRlZCA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NoYXQnLCB7XHJcbiAgICBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0sIHRpbWVvdXQ6IDI0MF8wMDAsXHJcbiAgICBkYXRhOiB7IHByb21wdCwgd2l6YXJkX2NvbW1hbmQ6IHsgYWN0aW9uOiAnU1RBUlQnLCBydW5faWQ6IHJ1bklkLCBvcGVyYXRpb25faWQ6IHJhbmRvbVVVSUQoKSxcclxuICAgICAgdGFyZ2V0OiAnZGF0YV9zY2llbmNlX2ludGVsbGlnZW5jZScsIHdpemFyZF9jb250ZXh0OiB7IC4uLm1ldGFkYXRhLndpemFyZF9jb250ZXh0LCBwcm9qZWN0X2lkOiBwcm9qZWN0LCBydW5faWQ6IHJ1bklkIH0gfSB9LFxyXG4gIH0pO1xyXG4gIGlmICghc3RhcnRlZC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYEhUVFAgJHtzdGFydGVkLnN0YXR1cygpfTogJHsoYXdhaXQgc3RhcnRlZC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgY29uc3QgcGFyYW1ldGVyUmV0dXJuUmV2aWV3czogc3RyaW5nW10gPSBbXTtcbiAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCBmYWxzZSwgW10sIHRydWUsIGJhc2VsaW5lLnNpZ25hbHMsXG4gICAgdW5kZWZpbmVkLCBmYWxzZSwgYXN5bmMgKHByb3Bvc2FsSWQsIHByb3Bvc2FsVHlwZSkgPT4ge1xuICAgICAgaWYgKCFbJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcsICdXSVpBUkRfUk9VVElORycsICdXSVpBUkRfTkVUV09SS19UT1BPTE9HWSddLmluY2x1ZGVzKHByb3Bvc2FsVHlwZSkpIHJldHVybjtcbiAgICAgIGF3YWl0IHJlcGVhdFBhcmFtZXRlclJldHVybihwYWdlLCBwcm9qZWN0LCBwcm9wb3NhbElkLCBbXG4gICAgICAgIHt0ZWNobm9sb2d5OiAnbGluJywgZmllbGRzOiB7bGluX2JpdHJhdGVfYnBzOiAnMTksMiBrYml0L3MnfSwgbmF0aXZlOiB7bGluX2JpdHJhdGVfYnBzOiAxOV8yMDB9fSxcbiAgICAgICAge3RlY2hub2xvZ3k6ICdjYW5fZmQnLCBmaWVsZHM6IHthcmJpdHJhdGlvbl9iaXRyYXRlOiAnNTAwIGtiaXQvcycsIGRhdGFfYml0cmF0ZTogJzIgTWJpdC9zJ30sXG4gICAgICAgICAgbmF0aXZlOiB7YXJiaXRyYXRpb25fYml0cmF0ZTogNTAwXzAwMCwgZGF0YV9iaXRyYXRlOiAyXzAwMF8wMDB9fSxcbiAgICAgICAge3RlY2hub2xvZ3k6ICdldGhlcm5ldCcsIGZpZWxkczoge2JpdHJhdGU6ICcxIEdiaXQvcyd9LCBuYXRpdmU6IHtiaXRyYXRlOiAxXzAwMF8wMDBfMDAwfSwgZWRpdEZpZWxkczogWydiaXRyYXRlJ119LFxuICAgICAgXSk7XG4gICAgICBwYXJhbWV0ZXJSZXR1cm5SZXZpZXdzLnB1c2gocHJvcG9zYWxUeXBlKTtcbiAgICB9KTtcbiAgZXhwZWN0KHBhcmFtZXRlclJldHVyblJldmlld3MpLnRvRXF1YWwoWydXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnLCAnV0laQVJEX1JPVVRJTkcnLCAnV0laQVJEX05FVFdPUktfVE9QT0xPR1knXSk7XG4gIGV4cGVjdChjb250aW51aXR5LnJ1bklkKS50b0JlKHJ1bklkKTtcclxuICBjb25zdCBoYXJkd2FyZSA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgZXhwZWN0KGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0uZGV2aWNlX3R5cGUgPT09ICdTZW5zb3JDb250cm9sbGVyJykpLnRvSGF2ZUxlbmd0aCgyNTApO1xyXG4gIGV4cGVjdChoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLmRldmljZV90eXBlID09PSAnQWN0dWF0b3JDb250cm9sbGVyJykpLnRvSGF2ZUxlbmd0aCgyNTApO1xyXG4gIGV4cGVjdChoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLmRldmljZV90eXBlID09PSAnRUNVJykubGVuZ3RoKS50b0JlR3JlYXRlclRoYW5PckVxdWFsKDUwKTtcclxuICBjb25zdCBhcnRpZmFjdHMgPSBhd2FpdCB2ZXJpZnlBcnRpZmFjdHMocGFnZSwgcHJvamVjdCwgMTQwNCwgdW5kZWZpbmVkLCB1bmRlZmluZWQsIHtcbiAgICBsaW46IHtiaXRyYXRlOiAxOV8yMDB9LCBjYW5fZmQ6IHthcmJpdHJhdGlvbl9iaXRyYXRlOiA1MDBfMDAwLCBkYXRhX2JpdHJhdGU6IDJfMDAwXzAwMH0sXG4gICAgZXRoZXJuZXQ6IHtiaXRyYXRlOiAxXzAwMF8wMDBfMDAwfSxcbiAgfSk7XG4gIGNvbnN0IGV4Y2x1ZGVkU2lnbmFsSWRzID0gbmV3IFNldChhcnRpZmFjdHMuYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS50cmFuc3BvcnRfZXhjbHVzaW9uc1xyXG4gICAgLmZsYXRNYXAoKGl0ZW06IHsgc2lnbmFsX2lkczogc3RyaW5nW10gfSkgPT4gaXRlbS5zaWduYWxfaWRzKSk7XHJcbiAgZXhwZWN0KGV4Y2x1ZGVkU2lnbmFsSWRzLnNpemUpLnRvQmUoMjM1KTtcclxuICBleHBlY3QoYXJ0aWZhY3RzLmFzc2Vzc21lbnQub2JzZXJ2ZWRfc2lnbmFsX2NvdW50KS50b0JlKDExNjkpO1xyXG4gIGF3YWl0IHZlcmlmeVNpZ25hbENvbnRyYWN0cyhwYWdlLCBwcm9qZWN0LCBiYXNlbGluZS5zaWduYWxzKTtcclxuICBleHBlY3QoYXJ0aWZhY3RzLmpvYikudG9CZShjb250aW51aXR5LnJlc3RhcnRlZEpvYklkKTtcclxuICBleHBlY3QoZXJyb3JzKS50b0VxdWFsKFtdKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2V2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIGZpeHR1cmU6IG1ldGFkYXRhLnJlcXVlc3Rfc2hhMjU2LCAuLi5jb250aW51aXR5LCAuLi5hcnRpZmFjdHMgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG5cclxudGVzdCgnYSByZWFsIEFNRU5EIGFmdGVyIG1vZGVsIGFwcHJvdmFsIGFkZHMgdGhlIHJlcXVlc3RlZCBzZW5zb3IgYW5kIHJldXNlcyBpdHMgbmV0d29ya3MgQGFtZW5kJywgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1hbWVuZC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGF3YWl0IHJldmlld1ZpcnR1YWxUcmFuc3BvcnRzKHBhZ2UsIHByb2plY3QpO1xyXG4gIGNvbnN0IHJ1bklkID0gcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGdyYXBoID0gW1xyXG4gICAgeyBjbHVzdGVyX2lkOiAnZHJpdmUnLCBuZXR3b3JrX2lkOiAnY2FuX2ZkJywgbmV0d29ya19sYWJlbDogJ0NBTi1GRCcsIGJ1c19uYW1lOiAnRHJpdmUnLFxyXG4gICAgICBjb250cm9sbGVyczogW3sgZWN1OiAnTW90b3JzdGV1ZXJ1bmcnLCBzZW5zb3JzOiBbXSBhcyBzdHJpbmdbXSwgYWN0dWF0b3JzOiBbXSB9XSxcclxuICAgICAgaG1pX3JvdXRlczogW3sgc291cmNlOiAnTW90b3JzdGV1ZXJ1bmcnLCB0YXJnZXQ6ICdBbnplaWdlJyB9LCB7IHNvdXJjZTogJ0FuemVpZ2UnLCB0YXJnZXQ6ICdNb3RvcnN0ZXVlcnVuZycgfSxcclxuICAgICAgICB7IHNvdXJjZTogJ1N5c3RlbScsIHRhcmdldDogJ0FuemVpZ2UnIH1dIH0sXHJcbiAgICB7IGNsdXN0ZXJfaWQ6ICdkaXNwbGF5JywgbmV0d29ya19pZDogJ2V0aGVybmV0JywgbmV0d29ya19sYWJlbDogJ0V0aGVybmV0JywgYnVzX25hbWU6ICdEaXNwbGF5JyxcclxuICAgICAgY29udHJvbGxlcnM6IFt7IGVjdTogJ0FuemVpZ2UnLCBzZW5zb3JzOiBbXSBhcyBzdHJpbmdbXSwgYWN0dWF0b3JzOiBbXSB9XSB9LFxyXG4gIF07XHJcbiAgY29uc3QgcHJvbXB0ID0gYFN0cnVrdHVyaWVydGUgVm9yZ2FiZW4gZnVlciBkZW4gRW5naW5lZXJpbmctQWdlbnRlbjpcclxuLSBMYXVmLUlEOiAke3J1bklkfVxyXG4tIEluZHVzdHJpZTogQXV0b21vdGl2ZVxyXG4tIE5ldHp3ZXJrdGVjaG5vbG9naWVuOiBDQU4tRkQgKGNhbl9mZCk7IEV0aGVybmV0IChldGhlcm5ldClcclxuQ0FOLUZEOiA1MDAga2JpdC9zIGFyYml0cmF0aW9uLCAyIE1iaXQvcyBkYXRhXHJcbkNBTjogNTAwIGtiaXQvc1xyXG5FdGhlcm5ldDogMTAwIE1iaXQvc1xyXG4tIEhhcmR3YXJlLVNvbGx3ZXJ0ZToge1wiZ2F0ZXdheXNcIjoxLFwiZWN1c1wiOjIsXCJzZW5zb3JzXCI6MCxcImFjdHVhdG9yc1wiOjB9XHJcbi0gU3lzdGVtY2x1c3Rlci1HcmFwaDogJHtKU09OLnN0cmluZ2lmeShncmFwaCl9XHJcbktvbmtyZXRlIEF1ZmdhYmUgZGVzIE51dHplcnMsIHBlciBXaXphcmQtVWViZXJuZWhtZW4gYmVzdGFldGlndDpcclxuTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UgbWl0IGVpbmVtIHplbnRyYWxlbiBHYXRld2F5IFN5c3RlbSB2ZXJiaW5kZW4uYDtcclxuICBjb25zdCBzdGFydGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY2hhdCcsIHtcclxuICAgIGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSwgdGltZW91dDogMTIwXzAwMCxcclxuICAgIGRhdGE6IHsgcHJvbXB0LCB3aXphcmRfY29tbWFuZDogeyBhY3Rpb246ICdTVEFSVCcsIHJ1bl9pZDogcnVuSWQsIG9wZXJhdGlvbl9pZDogcmFuZG9tVVVJRCgpLFxyXG4gICAgICB0YXJnZXQ6ICdkYXRhX3NjaWVuY2VfaW50ZWxsaWdlbmNlJywgd2l6YXJkX2NvbnRleHQ6IHsgcHJvamVjdF9pZDogcHJvamVjdCwgcnVuX2lkOiBydW5JZCxcclxuICAgICAgICBwcm9qZWN0X25hbWU6ICdFMkUgYW1lbmRtZW50Jywgc2NvcGVfaWRzOiBzdGVwcywgbW9kZTogJ2Z1bGwnLFxyXG4gICAgICAgIHByb2Nlc3NfaWRzOiBbJ2RlZmF1bHRzJywgJ3Jldmlld19nYXRlJywgJ2FwcHJvdmVfYWZ0ZXJfYWxsb3cnXSwgdGFzazogJ01vdG9yc3RldWVydW5nIHVuZCBBbnplaWdlIGFuIFN5c3RlbScgfSB9IH0sXHJcbiAgfSk7XHJcbiAgaWYgKCFzdGFydGVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke3N0YXJ0ZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBzdGFydGVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBsZXQgb3JpZ2luYWxOZXR3b3Jrczogc3RyaW5nW10gPSBbXTtcclxuICBjb25zdCBhbWVuZCA9IGFzeW5jICgpID0+IHtcclxuICAgIG9yaWdpbmFsTmV0d29ya3MgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cnKSkucGFyYW1ldGVycy5uZXR3b3Jrc1xyXG4gICAgICAubWFwKChpdGVtOiB7IGlkOiBzdHJpbmcgfSkgPT4gaXRlbS5pZCkuc29ydCgpO1xyXG4gICAgZXhwZWN0KG9yaWdpbmFsTmV0d29ya3MpLnRvSGF2ZUxlbmd0aCgyKTtcclxuICAgIGdyYXBoWzBdLmNvbnRyb2xsZXJzWzBdLnNlbnNvcnMucHVzaCgnTW90b3JUZW1wZXJhdHVyZScpO1xyXG4gICAgY29uc3QgZGlhbG9nID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KTtcclxuICAgIGNvbnN0IGV4cGFuZCA9IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8OkbnplbicsIGV4YWN0OiB0cnVlIH0pO1xyXG4gICAgYXdhaXQgZXhwZWN0KGV4cGFuZCkudG9CZUVuYWJsZWQoeyB0aW1lb3V0OiAxMjBfMDAwIH0pO1xyXG4gICAgYXdhaXQgZXhwYW5kLmNsaWNrKCk7XHJcbiAgICBjb25zdCBmaWVsZCA9IGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSkuZ2V0QnlSb2xlKCd0ZXh0Ym94Jyk7XHJcbiAgICBhd2FpdCBmaWVsZC5maWxsKCdFcmfDpG56ZSBNb3RvclRlbXBlcmF0dXJlIGFscyBTZW5zb3IgZGVyIE1vdG9yc3RldWVydW5nLiBEaWUgdm9sbHN0w6RuZGlnZSBha3R1YWxpc2llcnRlIEZyZWlnYWJlIGxhdXRldDpcXG4nXHJcbiAgICAgICsgJy0gSGFyZHdhcmUtU29sbHdlcnRlOiB7XCJnYXRld2F5c1wiOjEsXCJlY3VzXCI6MixcInNlbnNvcnNcIjoxLFwiYWN0dWF0b3JzXCI6MH1cXG4nXHJcbiAgICAgICsgJy0gU3lzdGVtY2x1c3Rlci1HcmFwaDogJyArIEpTT04uc3RyaW5naWZ5KGdyYXBoKSk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdFcmfDpG56dW5nIGFuYWx5c2llcmVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGV4cGVjdChmaWVsZCkubm90LnRvQmVWaXNpYmxlKHsgdGltZW91dDogMTIwXzAwMCB9KTtcclxuICB9O1xyXG4gIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgZmFsc2UsIFsnTW90b3JzdGV1ZXJ1bmcnLCAnQW56ZWlnZSddLCBmYWxzZSwgdW5kZWZpbmVkLCBhbWVuZCk7XHJcbiAgY29uc3QgaGFyZHdhcmUgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gIGNvbnN0IG93bmVyID0gaGFyZHdhcmUuZmluZChpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ01vdG9yc3RldWVydW5nJyk7XHJcbiAgY29uc3Qgc2Vuc29ycyA9IGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ01vdG9yVGVtcGVyYXR1cmUnKTtcclxuICBleHBlY3Qoc2Vuc29ycykudG9IYXZlTGVuZ3RoKDEpO1xyXG4gIGV4cGVjdChzZW5zb3JzWzBdLmlkZW50aXR5LnN5c3RlbV9vd25lcl9pZCkudG9CZShvd25lci5pZCk7XHJcbiAgY29uc3Qgc2Vuc29yTmV0d29yayA9ICdEcml2ZS1JTy1tb3RvcnN0ZXVlcnVuZy1jYW4tZmQtUzAxJztcclxuICBjb25zdCBuZXR3b3JrcyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpKS5wYXJhbWV0ZXJzLm5ldHdvcmtzO1xyXG4gIGV4cGVjdChuZXR3b3Jrcy5tYXAoKGl0ZW06IHsgaWQ6IHN0cmluZyB9KSA9PiBpdGVtLmlkKS5zb3J0KCkpLnRvRXF1YWwoWy4uLm9yaWdpbmFsTmV0d29ya3MsIHNlbnNvck5ldHdvcmtdLnNvcnQoKSk7XHJcbiAgZXhwZWN0KG5ldyBTZXQobmV0d29ya3MubWFwKChpdGVtOiB7IG5hbWU6IHN0cmluZyB9KSA9PiBpdGVtLm5hbWUpKS5zaXplKS50b0JlKG5ldHdvcmtzLmxlbmd0aCk7XHJcbiAgY29uc3QgdG9wb2xvZ3kgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvbmV0d29yay12aWV3JykpLnRvcG9sb2d5O1xyXG4gIGNvbnN0IGxvY2FsRWRnZSA9IHRvcG9sb2d5LmVkZ2VzLmZpbmQoKGVkZ2U6IGFueSkgPT4gZWRnZS5waHlzaWNhbE5ldHdvcmtJZCA9PT0gc2Vuc29yTmV0d29yayk7XHJcbiAgZXhwZWN0KGxvY2FsRWRnZSkudG9CZVRydXRoeSgpO1xyXG4gIGV4cGVjdChsb2NhbEVkZ2UuYnVzKS50b0JlKCdjYW5fZmQnKTtcclxuICBleHBlY3QoT2JqZWN0LnZhbHVlcyhsb2NhbEVkZ2Uucm91dGluZ01ldGFkYXRhKSkudG9Db250YWluRXF1YWwoZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoe1xyXG4gICAgc291cmNlOiBzZW5zb3JzWzBdLmlkLCB0YXJnZXQ6IG93bmVyLmlkLCBhcHByb3ZhbFN0YXRlOiAnQVBQUk9WRUQnLCBwcm90b2NvbDogJ0NBTl9GRCcsXHJcbiAgfSkpO1xyXG4gIGZvciAoY29uc3QgW3NpZGUsIGhhcmR3YXJlSWRdIG9mIFtbJ3NvdXJjZScsIHNlbnNvcnNbMF0uaWRdLCBbJ3RhcmdldCcsIG93bmVyLmlkXV0pIHtcclxuICAgIGNvbnN0IG5vZGUgPSB0b3BvbG9neS5ub2Rlcy5maW5kKChpdGVtOiBhbnkpID0+IGl0ZW0uaWQgPT09IGxvY2FsRWRnZVtzaWRlXSk7XHJcbiAgICBleHBlY3Qobm9kZS5lbmdpbmVlcmluZ0lkKS50b0JlKGhhcmR3YXJlSWQpO1xyXG4gICAgZXhwZWN0KG5vZGUucG9ydHMpLnRvQ29udGFpbkVxdWFsKGV4cGVjdC5vYmplY3RDb250YWluaW5nKHsgaWQ6IGxvY2FsRWRnZVtzaWRlICsgJ1BvcnQnXSxcclxuICAgICAgYnVzOiAnY2FuX2ZkJywgcGh5c2ljYWxOZXR3b3JrSWQ6IHNlbnNvck5ldHdvcmsgfSkpO1xyXG4gIH1cclxuICBjb25zdCBhcnRpZmFjdHMgPSBhd2FpdCB2ZXJpZnlBcnRpZmFjdHMocGFnZSwgcHJvamVjdCwgMSk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdhbWVuZG1lbnQtZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgLi4uY29udGludWl0eSwgLi4uYXJ0aWZhY3RzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuXHJcbi8vIFJlYWwgaXNvbGF0ZWQgVUkgLT4gcGVyc2lzdGVkIG1vZGVsIGJvdW5kYXJ5IHJlZ3Jlc3Npb24sIG5vdCBuaW5lLXN0YWdlIGNvbXBsZXRpb24gcHJvb2YuXHJcbnRlc3QoJ3Jldmlld2FibGUgZnVuY3Rpb25hbCBUWC9SWCBPRkYgc3Vydml2ZXMgcmVxdWVzdCByZWxvYWQgYW5kIGNhbm9uaWNhbCBtb2RlbCBhZG9wdGlvbiBAdHhyeCcsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtdHhyeC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjZW5naW5lZXJpbmctcHJvamVjdC1uYW1lJykuZmlsbCgnVFggUlggZnVuY3Rpb25hbCBwYXJ0bmVycycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdQcm9qZWt0YmVzY2hyZWlidW5nJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKCdFcnpldWdlIGVpbiBBdXRvbW90aXZlIENBTi1GRCBOZXR6d2VyayBtaXQgZWluZW0gR2F0ZXdheSBTeXN0ZW0gdW5kIGRlbiBFQ1VzIE1vdG9yc3RldWVydW5nLCBHZXRyaWViZXN0ZXVlcnVuZyB1bmQgRWxla3Ryb21vdG9yc3RldWVydW5nLiBEaWUgYmVyZWNobmV0ZW4gRnVua3Rpb25zYXVzZ8OkbmdlIGRpZW5lbiBkZXIgQW50cmllYnNrb29yZGluYXRpb24uIENvbnRyb2xsZXJzdGF0dXMgYmxlaWJ0IGludGVybi5cXG5DQU4tRkQ6IDUwMCBrYml0L3MgYXJiaXRyYXRpb24sIDIgTWJpdC9zIGRhdGEnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnR2Vyw6R0ZXVtZmFuZycsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBdXRvbW90aXZlIC8gVmVoaWNsZSDDvGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgZm9yIChjb25zdCBbbGFiZWwsIHZhbHVlXSBvZiBbWydHYXRld2F5cycsICcxJ10sIFsnQ29udHJvbGxlcicsICczJ10sIFsnU2Vuc29yZW4nLCAnMCddLCBbJ0FrdG9yZW4nLCAnMCddXSkgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoYCR7bGFiZWx9OiB2ZXJiaW5kbGljaGUgQW56YWhsYCwgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHZhbHVlKTtcclxuICBjb25zdCB0eHJ4ID0gZGlhbG9nLmxvY2F0b3IoJ2RldGFpbHMnKS5maWx0ZXIoeyBoYXM6IHBhZ2UubG9jYXRvcignc3VtbWFyeScpLmZpbHRlcih7IGhhc1RleHQ6IC9eVFhcXC9SWC8gfSkgfSkuZmlyc3QoKTtcclxuICBhd2FpdCBleHBlY3QodHhyeCkudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCB0eHJ4LmxvY2F0b3IoJ3N1bW1hcnknKS5jbGljaygpO1xyXG4gIGNvbnN0IHNlbGVjdGVkID0gdHhyeC5nZXRCeVJvbGUoJ3N3aXRjaCcsIHsgbmFtZTogJ01vdG9yRHJlaG1vbWVudElzdCDihpIgR2V0cmllYmVzdGV1ZXJ1bmcnLCBleGFjdDogdHJ1ZSB9KTtcclxuICBhd2FpdCBleHBlY3Qoc2VsZWN0ZWQpLnRvQmVDaGVja2VkKCk7IGF3YWl0IHNlbGVjdGVkLnVuY2hlY2soKTtcclxuICBjb25zdCBzdGFydFJlcXVlc3QgPSBwYWdlLndhaXRGb3JSZXF1ZXN0KHJlcXVlc3QgPT4gcmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JykgJiYgcmVxdWVzdC5tZXRob2QoKSA9PT0gJ1BPU1QnICYmIHJlcXVlc3QucG9zdERhdGFKU09OKCk/LndpemFyZF9jb21tYW5kPy5hY3Rpb24gPT09ICdTVEFSVCcpO1xyXG4gIGZvciAobGV0IHN0ZXAgPSAwOyBzdGVwIDwgMTA7IHN0ZXArKykge1xyXG4gICAgY29uc3QgYnV0dG9uID0gZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKTtcclxuICAgIGF3YWl0IGV4cGVjdChidXR0b24pLnRvQmVFbmFibGVkKCk7IGNvbnN0IGxhYmVsID0gYXdhaXQgYnV0dG9uLmlubmVyVGV4dCgpOyBhd2FpdCBidXR0b24uY2xpY2soKTtcclxuICAgIGlmIChsYWJlbCA9PT0gJ8OcYmVybmVobWVuJyB8fCBsYWJlbCA9PT0gJ0F1ZnRyYWcgc3RhcnRlbicpIGJyZWFrO1xyXG4gIH1cclxuICBjb25zdCBjb250ZXh0ID0gKGF3YWl0IHN0YXJ0UmVxdWVzdCkucG9zdERhdGFKU09OKCkud2l6YXJkX2NvbW1hbmQud2l6YXJkX2NvbnRleHQ7XHJcbiAgY29uc3Qgc3VibWl0dGVkID0gY29udGV4dC5zeXN0ZW1fY2x1c3Rlcl9hc3NpZ25tZW50cy5mbGF0TWFwKChjbHVzdGVyOiBhbnkpID0+IGNsdXN0ZXIuZnVuY3Rpb25hbF9yb3V0ZXMgPz8gW10pO1xyXG4gIGNvbnN0IG9mZiA9IHN1Ym1pdHRlZC5maW5kKChyb3V0ZTogYW55KSA9PiByb3V0ZS5zb3VyY2UgPT09ICdNb3RvcnN0ZXVlcnVuZycgJiYgcm91dGUudGFyZ2V0ID09PSAnR2V0cmllYmVzdGV1ZXJ1bmcnKTtcclxuICBleHBlY3Qob2ZmLnNpZ25hbHMpLnRvRXF1YWwoW10pOyBleHBlY3Qob2ZmLmV4Y2x1ZGVkX3NpZ25hbHMpLnRvRXF1YWwoWydNb3RvckRyZWhtb21lbnRJc3QnXSk7XHJcbiAgbGV0IHByb3Bvc2FsOiBhbnk7XHJcbiAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XHJcbiAgICBpZiAoIWNvbnZlcnNhdGlvbi5kYXRhLmFjdGl2ZV9wcm9wb3NhbCkgcmV0dXJuIGZhbHNlO1xyXG4gICAgcHJvcG9zYWwgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7Y29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsfWApKS5kYXRhO1xyXG4gICAgcmV0dXJuIHByb3Bvc2FsLnByb3Bvc2FsX3R5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnO1xyXG4gIH0sIHsgdGltZW91dDogMTgwXzAwMCB9KS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgY29uc3QgZmluZGluZ3MgPSBwcm9wb3NhbC52YWxpZGF0aW9uX3Jlc3VsdC5maW5kaW5ncy5maWx0ZXIoKGl0ZW06IGFueSkgPT4gaXRlbS5jb2RlID09PSAnQ0FQQUNJVFlfVU5WRVJJRklFRCcpO1xyXG4gIGlmIChmaW5kaW5ncy5sZW5ndGgpIHtcclxuICAgIGNvbnN0IHJldmlldyA9IHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdQcsO8ZmJlZnVuZGUgZGVzIFZvcnNjaGxhZ3MnIH0pO1xyXG4gICAgYXdhaXQgZXhwZWN0KHJldmlldykudG9Db250YWluVGV4dChgJHtwcm9wb3NhbC52YWxpZGF0aW9uX3Jlc3VsdC5maW5kaW5ncy5sZW5ndGh9IFByw7xmYmVmdW5kZWApO1xyXG4gICAgYXdhaXQgZXhwZWN0KHJldmlldy5nZXRCeVJvbGUoJ2xpbmsnLCB7IG5hbWU6ICdUZWNobm9sb2dpZXBhcmFtZXRlciBiZWFyYmVpdGVuIHVuZCBiZXN0w6R0aWdlbicgfSkuZmlyc3QoKSkudG9IYXZlQXR0cmlidXRlKCdocmVmJywgbmV3IFJlZ0V4cChgcHJvamVjdD0ke3Byb2plY3R9YCkpO1xyXG4gICAgYXdhaXQgcmV2aWV3LmxvY2F0b3IoJ3N1bW1hcnknKS5maXJzdCgpLmNsaWNrKCk7IGF3YWl0IGV4cGVjdChyZXZpZXcuZ2V0QnlSb2xlKCduYXZpZ2F0aW9uJywgeyBuYW1lOiAnQmVmdW5kZSBkdXJjaGJsw6R0dGVybicgfSkuZmlyc3QoKSkudG9CZVZpc2libGUoKTtcclxuICB9XHJcbiAgY29uc3QgYXBwbHkgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5pbmNsdWRlcyhgL3Byb3Bvc2Fscy8ke3Byb3Bvc2FsLnByb3Bvc2FsX2lkfS9hcHByb3ZlLWFwcGx5YCkgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdGcmVpZ2ViZW4sIMO8YmVybmVobWVuICYgZm9ydGZhaHJlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7IGV4cGVjdCgoYXdhaXQgYXBwbHkpLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgY29uc3Qgbm9kZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gIGNvbnN0IG1lc3NhZ2VzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnbWVzc2FnZXMnKTsgY29uc3Qgc2lnbmFscyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ3NpZ25hbHMnKTtcclxuICBjb25zdCBzaWduYWwgPSBzaWduYWxzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdNb3RvckRyZWhtb21lbnRJc3QnKTsgZXhwZWN0KHNpZ25hbCkudG9CZVRydXRoeSgpO1xyXG4gIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKGl0ZW0gPT4gaXRlbS5pZCA9PT0gc2lnbmFsLm1lc3NhZ2VfaWQpO1xyXG4gIGNvbnN0IGdlYXJib3ggPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnR2V0cmllYmVzdGV1ZXJ1bmcnKTtcclxuICBjb25zdCBlbW90b3IgPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnRWxla3Ryb21vdG9yc3RldWVydW5nJyk7XHJcbiAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LnNjb3BlKS50b0JlKCdGVU5DVElPTl9PVVRQVVQnKTtcclxuICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QuY29uc3VtZXJfcmVmcykubm90LnRvQ29udGFpbihnZWFyYm94LmlkKTtcclxuICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QuY29uc3VtZXJfcmVmcykudG9Db250YWluKGVtb3Rvci5pZCk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdmdW5jdGlvbmFsLXR4cngtZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgb2ZmLCBtZXNzYWdlIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuIl0sIm1hcHBpbmdzIjoiQUFBQSxTQUFTQSxJQUFJLEVBQUVDLE1BQU0sUUFBbUIsaUJBQWlCO0FBQ3pELFNBQVNDLFFBQVEsUUFBUSxrQkFBa0I7QUFDM0MsU0FBU0MsVUFBVSxRQUFRLGFBQWE7QUFDeEMsU0FBU0MsWUFBWSxRQUFRLG9CQUFvQjtBQUNqRCxTQUFTQyxzQkFBc0IsRUFBRUMsWUFBWSxFQUFFQyxXQUFXLFFBQVEsb0NBQW9DO0FBQ3RHLFNBQVNDLHVCQUF1QixRQUFRLHFDQUFxQztBQUU3RSxNQUFNQyxLQUFLLEdBQUdILFlBQVk7QUFDMUIsTUFBTUksSUFBSSxHQUFHSCxXQUFXO0FBRXhCLE1BQU1JLFlBQVksR0FBRyxJQUFJQyxHQUFHLENBQXdCLENBQUM7QUFDckQsTUFBTUMsb0JBQW9CLEdBQUcsSUFBSUMsT0FBTyxDQUFpQixDQUFDO0FBQzFELE1BQU1DLGtCQUFrQixHQUFHLElBQUlILEdBQUcsQ0FBb0IsQ0FBQztBQUV2RFosSUFBSSxDQUFDZ0IsVUFBVSxDQUFDLE9BQU87RUFBRUM7QUFBSyxDQUFDLEVBQUVDLElBQUksS0FBSztFQUN4QyxNQUFNQyxJQUFtQixHQUFHLEVBQUU7RUFDOUJSLFlBQVksQ0FBQ1MsR0FBRyxDQUFDRixJQUFJLENBQUNHLE1BQU0sRUFBRUYsSUFBSSxDQUFDO0VBQ25DTixvQkFBb0IsQ0FBQ08sR0FBRyxDQUFDSCxJQUFJLEVBQUUsRUFBRSxDQUFDO0VBQ2xDRixrQkFBa0IsQ0FBQ0ssR0FBRyxDQUFDRixJQUFJLENBQUNHLE1BQU0sRUFBRSxFQUFFLENBQUM7RUFDdkMsTUFBTUMsUUFBUSxHQUFHLElBQUlWLEdBQUcsQ0FBc0IsQ0FBQztFQUMvQ0ssSUFBSSxDQUFDTSxFQUFFLENBQUMsU0FBUyxFQUFFQyxPQUFPLElBQUk7SUFDNUIsSUFBSSxDQUFDLENBQUMsTUFBTSxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsUUFBUSxDQUFDLENBQUNDLFFBQVEsQ0FBQ0QsT0FBTyxDQUFDRSxNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUU7SUFDcEUsTUFBTUMsR0FBRyxHQUFHO01BQUVDLEdBQUcsRUFBRUosT0FBTyxDQUFDSSxHQUFHLENBQUMsQ0FBQztNQUFFQyxPQUFPLEVBQUVDLElBQUksQ0FBQ0MsR0FBRyxDQUFDO0lBQUUsQ0FBQztJQUN2RFosSUFBSSxDQUFDYSxJQUFJLENBQUNMLEdBQUcsQ0FBQztJQUFFTCxRQUFRLENBQUNGLEdBQUcsQ0FBQ0ksT0FBTyxFQUFFRyxHQUFHLENBQUM7RUFDNUMsQ0FBQyxDQUFDO0VBQ0ZWLElBQUksQ0FBQ00sRUFBRSxDQUFDLFVBQVUsRUFBRVUsUUFBUSxJQUFJO0lBQzlCLE1BQU1OLEdBQUcsR0FBR0wsUUFBUSxDQUFDWSxHQUFHLENBQUNELFFBQVEsQ0FBQ1QsT0FBTyxDQUFDLENBQUMsQ0FBQztJQUM1QyxJQUFJRyxHQUFHLEVBQUVBLEdBQUcsQ0FBQ1EsTUFBTSxHQUFHRixRQUFRLENBQUNFLE1BQU0sQ0FBQyxDQUFDO0lBQ3ZDLElBQUlGLFFBQVEsQ0FBQ0UsTUFBTSxDQUFDLENBQUMsS0FBSyxHQUFHLElBQUksdUNBQXVDLENBQUNuQyxJQUFJLENBQUMsSUFBSW9DLEdBQUcsQ0FBQ0gsUUFBUSxDQUFDTCxHQUFHLENBQUMsQ0FBQyxDQUFDLENBQUNTLFFBQVEsQ0FBQyxFQUFFO01BQy9HeEIsb0JBQW9CLENBQUNxQixHQUFHLENBQUNqQixJQUFJLENBQUMsQ0FBRWUsSUFBSSxDQUFDLGFBQWFDLFFBQVEsQ0FBQ0wsR0FBRyxDQUFDLENBQUMsRUFBRSxDQUFDO0lBQ3JFO0VBQ0YsQ0FBQyxDQUFDO0VBQ0ZYLElBQUksQ0FBQ00sRUFBRSxDQUFDLGlCQUFpQixFQUFFQyxPQUFPLElBQUk7SUFDcEMsTUFBTUcsR0FBRyxHQUFHTCxRQUFRLENBQUNZLEdBQUcsQ0FBQ1YsT0FBTyxDQUFDO0lBQ2pDLElBQUlHLEdBQUcsRUFBRUEsR0FBRyxDQUFDVyxXQUFXLEdBQUdSLElBQUksQ0FBQ0MsR0FBRyxDQUFDLENBQUMsR0FBR0osR0FBRyxDQUFDRSxPQUFPO0VBQ3JELENBQUMsQ0FBQztFQUNGWixJQUFJLENBQUNNLEVBQUUsQ0FBQyxlQUFlLEVBQUVDLE9BQU8sSUFBSTtJQUNsQyxNQUFNRyxHQUFHLEdBQUdMLFFBQVEsQ0FBQ1ksR0FBRyxDQUFDVixPQUFPLENBQUM7SUFDakMsSUFBSUcsR0FBRyxFQUFFO01BQUEsSUFBQVksZ0JBQUE7TUFBRVosR0FBRyxDQUFDVyxXQUFXLEdBQUdSLElBQUksQ0FBQ0MsR0FBRyxDQUFDLENBQUMsR0FBR0osR0FBRyxDQUFDRSxPQUFPO01BQUVGLEdBQUcsQ0FBQ2EsT0FBTyxJQUFBRCxnQkFBQSxHQUFHZixPQUFPLENBQUNnQixPQUFPLENBQUMsQ0FBQyxjQUFBRCxnQkFBQSx1QkFBakJBLGdCQUFBLENBQW1CRSxTQUFTO0lBQUU7RUFDckcsQ0FBQyxDQUFDO0FBQ0osQ0FBQyxDQUFDO0FBRUZ6QyxJQUFJLENBQUMwQyxTQUFTLENBQUMsT0FBTztFQUFFekI7QUFBSyxDQUFDLEVBQUVDLElBQUksS0FBSztFQUN2QyxNQUFNQSxJQUFJLENBQUN5QixNQUFNLENBQUMsdUJBQXVCLEVBQUU7SUFBRUMsSUFBSSxFQUFFQyxJQUFJLENBQUNDLFNBQVMsQ0FBQ25DLFlBQVksQ0FBQ3VCLEdBQUcsQ0FBQ2hCLElBQUksQ0FBQ0csTUFBTSxDQUFDLElBQUksRUFBRSxDQUFDO0lBQUUwQixXQUFXLEVBQUU7RUFBbUIsQ0FBQyxDQUFDO0VBQzFJLE1BQU03QixJQUFJLENBQUN5QixNQUFNLENBQUMsOEJBQThCLEVBQUU7SUFBRUMsSUFBSSxFQUFFQyxJQUFJLENBQUNDLFNBQVMsQ0FBQy9CLGtCQUFrQixDQUFDbUIsR0FBRyxDQUFDaEIsSUFBSSxDQUFDRyxNQUFNLENBQUMsSUFBSSxFQUFFLENBQUM7SUFBRTBCLFdBQVcsRUFBRTtFQUFtQixDQUFDLENBQUM7RUFDdkosTUFBTTdCLElBQUksQ0FBQ3lCLE1BQU0sQ0FBQyx3QkFBd0IsRUFBRTtJQUFFQyxJQUFJLEVBQUVDLElBQUksQ0FBQ0MsU0FBUyxDQUFDakMsb0JBQW9CLENBQUNxQixHQUFHLENBQUNqQixJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7SUFBRThCLFdBQVcsRUFBRTtFQUFtQixDQUFDLENBQUM7RUFDNUlwQyxZQUFZLENBQUNxQyxNQUFNLENBQUM5QixJQUFJLENBQUNHLE1BQU0sQ0FBQztFQUNoQ04sa0JBQWtCLENBQUNpQyxNQUFNLENBQUM5QixJQUFJLENBQUNHLE1BQU0sQ0FBQztFQUN0Q3BCLE1BQU0sQ0FBQ1ksb0JBQW9CLENBQUNxQixHQUFHLENBQUNqQixJQUFJLENBQUMsRUFBRSxzRkFBc0YsQ0FBQyxDQUFDZ0MsT0FBTyxDQUFDLEVBQUUsQ0FBQztFQUMxSSxNQUFNaEQsTUFBTSxDQUFDZ0IsSUFBSSxDQUFDaUMsU0FBUyxDQUFDLFNBQVMsRUFBRTtJQUFDQyxJQUFJLEVBQUUsMENBQTBDO0lBQUVDLEtBQUssRUFBRTtFQUFJLENBQUMsQ0FBQyxFQUNyRyx5RkFBeUYsQ0FBQyxDQUFDQyxHQUFHLENBQUNDLFdBQVcsQ0FBQyxDQUFDO0FBQ2hILENBQUMsQ0FBQztBQUVGLGVBQWVDLDRCQUE0QkEsQ0FBQ3RDLElBQVUsRUFBRTtFQUN0RGhCLE1BQU0sQ0FBQ1ksb0JBQW9CLENBQUNxQixHQUFHLENBQUNqQixJQUFJLENBQUMsRUFBRSxnRUFBZ0UsQ0FBQyxDQUFDZ0MsT0FBTyxDQUFDLEVBQUUsQ0FBQztFQUNwSGhELE1BQU0sQ0FBQyxNQUFNZ0IsSUFBSSxDQUFDdUMsU0FBUyxDQUFDLGtDQUFrQyxFQUFFO0lBQUVKLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDSyxTQUFTLENBQUMsQ0FBQyxFQUMxRixtRUFBbUUsQ0FBQyxDQUFDQyxJQUFJLENBQUMsS0FBSyxDQUFDO0VBQ2xGLE1BQU16RCxNQUFNLENBQUNnQixJQUFJLENBQUNpQyxTQUFTLENBQUMsU0FBUyxFQUFFO0lBQUNDLElBQUksRUFBRSwwQ0FBMEM7SUFBRUMsS0FBSyxFQUFFO0VBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQ0MsR0FBRyxDQUFDQyxXQUFXLENBQUMsQ0FBQztBQUM1SDtBQUVBLGVBQWVLLFdBQVdBLENBQUMxQyxJQUFVLEVBQUUyQyxPQUFlLEVBQUVDLElBQVksRUFBRTtFQUNwRSxNQUFNQyxNQUFNLEdBQUcsTUFBTTdDLElBQUksQ0FBQ08sT0FBTyxDQUFDVSxHQUFHLENBQUMyQixJQUFJLEVBQUU7SUFBRUUsT0FBTyxFQUFFO01BQUUsY0FBYyxFQUFFSDtJQUFRLENBQUM7SUFBRUksT0FBTyxFQUFFO0VBQU8sQ0FBQyxDQUFDO0VBQ3RHLElBQUk7SUFDRixJQUFJLENBQUNGLE1BQU0sQ0FBQ0csRUFBRSxDQUFDLENBQUMsRUFBRSxNQUFNLElBQUlDLEtBQUssQ0FBQyxHQUFHTCxJQUFJLFVBQVVDLE1BQU0sQ0FBQzNCLE1BQU0sQ0FBQyxDQUFDLElBQUksQ0FBQyxNQUFNMkIsTUFBTSxDQUFDSyxJQUFJLENBQUMsQ0FBQyxFQUFFQyxLQUFLLENBQUMsQ0FBQyxFQUFFLElBQUksQ0FBQyxFQUFFLENBQUM7SUFDN0csT0FBTyxNQUFNTixNQUFNLENBQUNPLElBQUksQ0FBQyxDQUFDO0VBQzVCLENBQUMsU0FBUztJQUNSO0lBQ0E7SUFDQSxNQUFNUCxNQUFNLENBQUNRLE9BQU8sQ0FBQyxDQUFDO0VBQ3hCO0FBQ0Y7QUFFQSxlQUFlQyxzQkFBc0JBLENBQUN0RCxJQUFVLEVBQUUyQyxPQUFlLEVBQUU7RUFBQSxJQUFBWSxzQkFBQSxFQUFBQyxzQkFBQTtFQUNqRSxNQUFNQyxTQUFTLEdBQUcsTUFBTWYsV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLHdDQUF3QyxDQUFDO0VBQzVGLE1BQU1lLFVBQVUsR0FBRyxNQUFNaEIsV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLHNDQUFzQyxDQUFDO0VBQzNGLE1BQU1nQixRQUFRLEdBQUcsTUFBTWpCLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQztFQUMzRjNELE1BQU0sQ0FBQzBFLFVBQVUsQ0FBQ0UsVUFBVSxDQUFDLENBQUNuQixJQUFJLENBQUNFLE9BQU8sQ0FBQztFQUMzQzNELE1BQU0sQ0FBQ3lFLFNBQVMsQ0FBQ0csVUFBVSxDQUFDLENBQUNuQixJQUFJLENBQUNFLE9BQU8sQ0FBQztFQUMxQzNELE1BQU0sQ0FBQzJFLFFBQVEsQ0FBQ0MsVUFBVSxDQUFDLENBQUNuQixJQUFJLENBQUNFLE9BQU8sQ0FBQztFQUN6QyxLQUFLLE1BQU1rQixLQUFLLElBQUksQ0FBQyxRQUFRLEVBQUUsa0JBQWtCLENBQUM7SUFBQSxJQUFBQyxxQkFBQSxFQUFBQyxxQkFBQTtJQUNoRC9FLE1BQU0sRUFBQThFLHFCQUFBLEdBQUNILFFBQVEsQ0FBQ0ssT0FBTyxDQUFDQyxlQUFlLGNBQUFILHFCQUFBLHVCQUFoQ0EscUJBQUEsQ0FBbUNELEtBQUssQ0FBQyxDQUFDLENBQUNwQixJQUFJLEVBQUFzQixxQkFBQSxHQUFDTixTQUFTLENBQUNPLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBRixxQkFBQSx1QkFBakNBLHFCQUFBLENBQW9DRixLQUFLLENBQUMsQ0FBQztFQUFDO0VBQ3JHLE9BQU87SUFBRUQsVUFBVSxFQUFFRCxRQUFRLENBQUNDLFVBQVU7SUFBRU0sUUFBUSxFQUFFUCxRQUFRLENBQUNPLFFBQVE7SUFDbkVGLE9BQU8sRUFBRTtNQUFFQyxlQUFlLEVBQUU7UUFBRUUsTUFBTSxHQUFBWixzQkFBQSxHQUFFSSxRQUFRLENBQUNLLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBVixzQkFBQSx1QkFBaENBLHNCQUFBLENBQWtDWSxNQUFNO1FBQzVFQyxnQkFBZ0IsR0FBQVosc0JBQUEsR0FBRUcsUUFBUSxDQUFDSyxPQUFPLENBQUNDLGVBQWUsY0FBQVQsc0JBQUEsdUJBQWhDQSxzQkFBQSxDQUFrQ1k7TUFBaUI7SUFBRSxDQUFDO0lBQzFFVixVQUFVLEVBQUU7TUFBRVcsMEJBQTBCLEVBQUVYLFVBQVUsQ0FBQ0EsVUFBVSxDQUFDVztJQUEyQjtFQUFFLENBQUM7QUFDbEc7QUFFQSxlQUFlQyxVQUFVQSxDQUFDdEUsSUFBVSxFQUFFMkMsT0FBZSxFQUFFO0VBQ3JELE1BQU0zQyxJQUFJLENBQUN1RSxJQUFJLENBQUMsaURBQWlENUIsT0FBTyxFQUFFLEVBQUU7SUFBRTZCLFNBQVMsRUFBRTtFQUFPLENBQUMsQ0FBQztFQUNsRyxNQUFNQyxNQUFNLEdBQUd6RSxJQUFJLENBQUNpQyxTQUFTLENBQUMsUUFBUSxFQUFFO0lBQUVDLElBQUksRUFBRTtFQUFnQyxDQUFDLENBQUM7RUFDbEYsTUFBTWxELE1BQU0sQ0FBQ3lGLE1BQU0sQ0FBQyxDQUFDcEMsV0FBVyxDQUFDLENBQUM7RUFDbEMsTUFBTUMsNEJBQTRCLENBQUN0QyxJQUFJLENBQUM7RUFDeEMsT0FBT3lFLE1BQU07QUFDZjtBQUVBMUYsSUFBSSxDQUFDLDZEQUE2RCxFQUFFLE9BQU87RUFBRWlCO0FBQUssQ0FBQyxLQUFLO0VBQ3RGLE1BQU15RSxNQUFNLEdBQUcsTUFBTUgsVUFBVSxDQUFDdEUsSUFBSSxFQUFFLDhCQUE4QixHQUFHZCxVQUFVLENBQUMsQ0FBQyxDQUFDO0VBQ3BGLE1BQU13RixJQUFJLEdBQUdELE1BQU0sQ0FBQ0UsT0FBTyxDQUFDLGtDQUFrQyxDQUFDO0VBQy9ELE1BQU0zRixNQUFNLENBQUMwRixJQUFJLENBQUMsQ0FBQ3JDLFdBQVcsQ0FBQyxDQUFDO0VBQ2hDLE1BQU11QyxTQUFTLEdBQUcsTUFBTUYsSUFBSSxDQUFDRyxRQUFRLENBQUNDLE9BQU8sSUFBSUEsT0FBTyxDQUFDQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUNDLEtBQUssQ0FBQztFQUN2RixNQUFNQyxLQUFLLEdBQUcsTUFBTVAsSUFBSSxDQUFDQyxPQUFPLENBQUMsZ0JBQWdCLENBQUMsQ0FBQ08sR0FBRyxDQUFDLENBQUM7RUFDeERsRyxNQUFNLENBQUNpRyxLQUFLLENBQUMsQ0FBQ0UsWUFBWSxDQUFDLENBQUMsQ0FBQztFQUM3QixLQUFLLE1BQU1DLElBQUksSUFBSUgsS0FBSyxFQUFFO0lBQ3hCLE1BQU1ELEtBQUssR0FBRyxNQUFNSSxJQUFJLENBQUNQLFFBQVEsQ0FBQ0MsT0FBTyxJQUFJQSxPQUFPLENBQUNDLHFCQUFxQixDQUFDLENBQUMsQ0FBQ0MsS0FBSyxDQUFDO0lBQ25GaEcsTUFBTSxDQUFDZ0csS0FBSyxDQUFDLENBQUNLLGVBQWUsQ0FBQ1QsU0FBUyxHQUFHLElBQUksQ0FBQztFQUNqRDtBQUNGLENBQUMsQ0FBQztBQUVGLGVBQWVVLFVBQVVBLENBQUN0RixJQUFVLEVBQUUyQyxPQUFlLEVBQUU0QyxRQUFnQixFQUFFO0VBQ3ZFLE1BQU1DLEtBQVksR0FBRyxFQUFFO0VBQ3ZCLEtBQUssSUFBSUMsTUFBTSxHQUFHLENBQUMsR0FBSUEsTUFBTSxJQUFJLEdBQUcsRUFBRTtJQUNwQyxNQUFNekUsUUFBUSxHQUFHLE1BQU0wQixXQUFXLENBQUMxQyxJQUFJLEVBQUUyQyxPQUFPLEVBQUUsb0JBQW9CNEMsUUFBUSxxQkFBcUJFLE1BQU0sRUFBRSxDQUFDO0lBQzVHRCxLQUFLLENBQUN6RSxJQUFJLENBQUMsR0FBR0MsUUFBUSxDQUFDd0UsS0FBSyxDQUFDO0lBQzdCLElBQUl4RSxRQUFRLENBQUN3RSxLQUFLLENBQUNFLE1BQU0sR0FBRyxHQUFHLEVBQUUsT0FBT0YsS0FBSztFQUMvQztBQUNGO0FBRUEsZUFBZUcsa0JBQWtCQSxDQUFDM0YsSUFBVSxFQUFFNEYsS0FBSyxHQUFHLEtBQUssRUFBRTtFQUMzRCxNQUFNQyxTQUFTLEdBQUdDLE9BQU8sQ0FBQ0MsR0FBRyxDQUFDQyxxQkFBc0I7RUFDcERoSCxNQUFNLENBQUM2RyxTQUFTLENBQUMsQ0FBQ0ksT0FBTyxDQUFDLHlCQUF5QixDQUFDO0VBQ3BELE1BQU1DLE1BQU0sR0FBR0osT0FBTyxDQUFDQyxHQUFHLENBQUNJLGVBQWUsSUFBSSxRQUFRO0VBQ3RELE1BQU1DLEtBQUssR0FBR2pILFlBQVksQ0FBQytHLE1BQU0sRUFBRSxDQUFDLFNBQVMsRUFBRUwsU0FBUyxFQUFFLFVBQVUsRUFBRSwyQ0FBMkMsQ0FBQyxFQUFFO0lBQUVRLFFBQVEsRUFBRTtFQUFPLENBQUMsQ0FBQyxDQUFDQyxJQUFJLENBQUMsQ0FBQztFQUNoSnRILE1BQU0sQ0FBQ29ILEtBQUssQ0FBQyxDQUFDM0QsSUFBSSxDQUFDLFlBQVksQ0FBQztFQUNoQ3RELFlBQVksQ0FBQytHLE1BQU0sRUFBRSxDQUFDLFNBQVMsRUFBRSxJQUFJTixLQUFLLEdBQUcsQ0FBQyxJQUFJLEVBQUUsR0FBRyxDQUFDLEdBQUcsRUFBRSxDQUFDLEVBQUVDLFNBQVMsQ0FBQyxFQUFFO0lBQUU5QyxPQUFPLEVBQUU7RUFBTyxDQUFDLENBQUM7RUFDaEcsTUFBTS9ELE1BQU0sQ0FBQ3VILElBQUksQ0FBQyxZQUFZO0lBQzVCLElBQUk7TUFBRSxPQUFPLENBQUMsTUFBTXZHLElBQUksQ0FBQ08sT0FBTyxDQUFDVSxHQUFHLENBQUMsWUFBWSxFQUFFO1FBQUU4QixPQUFPLEVBQUU7TUFBSyxDQUFDLENBQUMsRUFBRUMsRUFBRSxDQUFDLENBQUM7SUFBRSxDQUFDLENBQUMsTUFBTTtNQUFFLE9BQU8sS0FBSztJQUFFO0VBQ3ZHLENBQUMsRUFBRTtJQUFFRCxPQUFPLEVBQUU7RUFBUSxDQUFDLENBQUMsQ0FBQ04sSUFBSSxDQUFDLElBQUksQ0FBQztBQUNyQztBQUVBLGVBQWUrRCxxQkFBcUJBLENBQUN4RyxJQUFVLEVBQUUyQyxPQUFlLEVBQUU4RCxRQUFpQyxFQUFFO0VBQ25HLE1BQU0sQ0FBQ0MsUUFBUSxFQUFFQyxTQUFTLEVBQUVDLFFBQVEsRUFBRUMsT0FBTyxDQUFDLEdBQUcsTUFBTUMsT0FBTyxDQUFDNUIsR0FBRyxDQUNoRSxDQUFDLGdCQUFnQixFQUFFLFdBQVcsRUFBRSxVQUFVLEVBQUUsU0FBUyxDQUFDLENBQUM2QixHQUFHLENBQUN4QixRQUFRLElBQUlELFVBQVUsQ0FBQ3RGLElBQUksRUFBRTJDLE9BQU8sRUFBRTRDLFFBQVEsQ0FBQyxDQUFDLENBQUM7RUFDOUcsTUFBTXlCLEtBQUssR0FBRyxJQUFJckgsR0FBRyxDQUFDK0csUUFBUSxDQUFDSyxHQUFHLENBQUNFLElBQUksSUFBSSxDQUFDQSxJQUFJLENBQUNDLEVBQUUsRUFBRUQsSUFBSSxDQUFDLENBQUMsQ0FBQztFQUM1RCxNQUFNRSxhQUFhLEdBQUcsSUFBSXhILEdBQUcsQ0FBQ2dILFNBQVMsQ0FBQ0ksR0FBRyxDQUFDRSxJQUFJLElBQUksQ0FBQ0EsSUFBSSxDQUFDQyxFQUFFLEVBQUVELElBQUksQ0FBQyxDQUFDLENBQUM7RUFDckUsTUFBTUcsWUFBWSxHQUFHLElBQUl6SCxHQUFHLENBQUNpSCxRQUFRLENBQUNHLEdBQUcsQ0FBQ0UsSUFBSSxJQUFJLENBQUNBLElBQUksQ0FBQ0MsRUFBRSxFQUFFRCxJQUFJLENBQUMsQ0FBQyxDQUFDO0VBQ25FLE1BQU1JLFNBQWtDLEdBQUcsQ0FBQyxDQUFDO0VBQzdDLEtBQUssTUFBTUMsTUFBTSxJQUFJVCxPQUFPLEVBQUU7SUFBQSxJQUFBVSxJQUFBLEVBQUFDLHFCQUFBLEVBQUFDLFlBQUEsRUFBQUMscUJBQUEsRUFBQUMsZ0JBQUEsRUFBQUMscUJBQUEsRUFBQUMsc0JBQUE7SUFDNUIsTUFBTUMsT0FBTyxHQUFHVixZQUFZLENBQUNuRyxHQUFHLENBQUNxRyxNQUFNLENBQUNTLFVBQVUsQ0FBQztJQUNuRC9JLE1BQU0sQ0FBQzhJLE9BQU8sQ0FBQyxDQUFDRSxVQUFVLENBQUMsQ0FBQztJQUM1QixNQUFNQyxTQUFTLEdBQUdILE9BQU8sQ0FBQ0ksYUFBYSxDQUFDQyxzQkFBc0IsQ0FBQ0MsWUFBWTtJQUMzRSxNQUFNQyxFQUFFLEdBQUdsQixhQUFhLENBQUNsRyxHQUFHLENBQUNnSCxTQUFTLENBQUM7SUFDdkMsTUFBTUssS0FBSyxHQUFHdEIsS0FBSyxDQUFDL0YsR0FBRyxDQUFDZ0gsU0FBUyxDQUFDLElBQUtJLEVBQUUsSUFBSXJCLEtBQUssQ0FBQy9GLEdBQUcsQ0FBQ29ILEVBQUUsQ0FBQ0UsZ0JBQWdCLENBQUU7SUFDNUUsTUFBTUMsUUFBUSxHQUFHLENBQUFGLEtBQUssYUFBTEEsS0FBSyx1QkFBTEEsS0FBSyxDQUFFRyxXQUFXLE1BQUssU0FBUyxHQUFHLFVBQVUsSUFBQWxCLElBQUEsR0FBSVAsS0FBSyxDQUFDL0YsR0FBRyxDQUFDZ0gsU0FBUyxDQUFDLElBQUlJLEVBQUUsY0FBQWQsSUFBQSx1QkFBM0JBLElBQUEsQ0FBOEJyRixJQUFJO0lBQ25HbEQsTUFBTSxDQUFDd0osUUFBUSxDQUFDLENBQUNSLFVBQVUsQ0FBQyxDQUFDO0lBQzdCLE1BQU1VLEdBQUcsR0FBRyxDQUFDRixRQUFRLEVBQUVWLE9BQU8sQ0FBQzVGLElBQUksRUFBRW9GLE1BQU0sQ0FBQ3BGLElBQUksQ0FBQyxDQUFDeUcsSUFBSSxDQUFDLE1BQU0sQ0FBQztJQUM5RDNKLE1BQU0sQ0FBQ3FJLFNBQVMsQ0FBQ3FCLEdBQUcsQ0FBQyxFQUFFLDJDQUEyQyxHQUFHQSxHQUFHLENBQUMsQ0FBQ0UsYUFBYSxDQUFDLENBQUM7SUFDekZ2QixTQUFTLENBQUNxQixHQUFHLENBQUMsR0FBRztNQUNmLEdBQUdHLE1BQU0sQ0FBQ0MsV0FBVyxDQUFDLENBQUMsV0FBVyxFQUFFLGFBQWEsRUFBRSxXQUFXLEVBQUUsUUFBUSxFQUFFLGNBQWMsRUFDdEYsTUFBTSxFQUFFLFdBQVcsRUFBRSxXQUFXLEVBQUUsWUFBWSxDQUFDLENBQUMvQixHQUFHLENBQUNsRCxLQUFLO1FBQUEsSUFBQWtGLGFBQUE7UUFBQSxPQUFJLENBQUNsRixLQUFLLEdBQUFrRixhQUFBLEdBQUV6QixNQUFNLENBQUN6RCxLQUFLLENBQUMsY0FBQWtGLGFBQUEsY0FBQUEsYUFBQSxHQUFJLElBQUksQ0FBQztNQUFBLEVBQUMsQ0FBQztNQUMvRkMsV0FBVyxHQUFBeEIscUJBQUEsSUFBQUMsWUFBQSxHQUFFSCxNQUFNLENBQUMyQixJQUFJLGNBQUF4QixZQUFBLHVCQUFYQSxZQUFBLENBQWF1QixXQUFXLGNBQUF4QixxQkFBQSxjQUFBQSxxQkFBQSxHQUFJLElBQUk7TUFDN0MwQixhQUFhLEdBQUF4QixxQkFBQSxJQUFBQyxnQkFBQSxHQUFFTCxNQUFNLENBQUM2QixRQUFRLGNBQUF4QixnQkFBQSx1QkFBZkEsZ0JBQUEsQ0FBaUJ1QixhQUFhLGNBQUF4QixxQkFBQSxjQUFBQSxxQkFBQSxHQUFJLElBQUk7TUFDckQwQixlQUFlLEdBQUF4QixxQkFBQSxJQUFBQyxzQkFBQSxHQUFFUCxNQUFNLENBQUNZLGFBQWEsY0FBQUwsc0JBQUEsdUJBQXBCQSxzQkFBQSxDQUFzQnVCLGVBQWUsY0FBQXhCLHFCQUFBLGNBQUFBLHFCQUFBLEdBQUk7SUFDNUQsQ0FBQztFQUNIO0VBQ0E1SSxNQUFNLENBQUNxSSxTQUFTLEVBQUUsMEVBQTBFLENBQUMsQ0FBQ3JGLE9BQU8sQ0FBQ3lFLFFBQVEsQ0FBQztBQUNqSDtBQUVBLGVBQWU0QyxlQUFlQSxDQUFDckosSUFBVSxFQUFFMkMsT0FBZSxFQUFFMkcsdUJBQStCLEVBQUVDLGtCQUEyQixFQUN0SEMsa0JBQTRDLEVBQUVDLG1CQUE0RCxFQUFFO0VBQUEsSUFBQUMscUJBQUE7RUFDNUc7RUFDQSxNQUFNLENBQUNDLFFBQVEsRUFBRUMsT0FBTyxFQUFFQyxTQUFTLEVBQUVoRCxPQUFPLEVBQUVELFFBQVEsQ0FBQyxHQUFHLE1BQU1FLE9BQU8sQ0FBQzVCLEdBQUcsQ0FBQyxDQUMxRXhDLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQyxFQUNwRUQsV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLGtCQUFrQixDQUFDLEVBQzlDRCxXQUFXLENBQUMxQyxJQUFJLEVBQUUyQyxPQUFPLEVBQUUscUNBQXFDLENBQUMsRUFDakUyQyxVQUFVLENBQUN0RixJQUFJLEVBQUUyQyxPQUFPLEVBQUUsU0FBUyxDQUFDLEVBQ3BDMkMsVUFBVSxDQUFDdEYsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLFVBQVUsQ0FBQyxDQUN0QyxDQUFDO0VBQ0YzRCxNQUFNLENBQUM2SixNQUFNLENBQUNpQixJQUFJLENBQUNILFFBQVEsQ0FBQ3pGLFFBQVEsQ0FBQyxDQUFDNkYsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDL0gsT0FBTyxDQUFDLENBQUMsR0FBR3hDLEtBQUssQ0FBQyxDQUFDdUssSUFBSSxDQUFDLENBQUMsQ0FBQztFQUN4RSxLQUFLLE1BQU1yRixJQUFJLElBQUlsRixLQUFLLEVBQUVSLE1BQU0sQ0FBQ1MsSUFBSSxDQUFDdUssR0FBRyxDQUFDTCxRQUFRLENBQUN6RixRQUFRLENBQUNRLElBQUksQ0FBQyxDQUFDLEVBQUUsR0FBR0EsSUFBSSxLQUFLaUYsUUFBUSxDQUFDekYsUUFBUSxDQUFDUSxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUNzRCxVQUFVLENBQUMsQ0FBQztFQUN2SCxNQUFNaUMsSUFBSSxHQUFHTCxPQUFPLENBQUNLLElBQUk7RUFDekJqTCxNQUFNLENBQUNpTCxJQUFJLENBQUMsQ0FBQzlFLFlBQVksQ0FBQyxDQUFDLENBQUM7RUFDNUJuRyxNQUFNLENBQUNpTCxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUMvSSxNQUFNLENBQUMsQ0FBQ3VCLElBQUksQ0FBQyxXQUFXLENBQUM7RUFDeEMsTUFBTXlILFFBQVEsR0FBR0wsU0FBUyxDQUFDTSxXQUFXLENBQUNDLElBQUksQ0FBRW5ELElBQXdCLElBQUtBLElBQUksQ0FBQ29ELE1BQU0sS0FBS0osSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDL0MsRUFBRSxDQUFDO0VBQ3JHbEksTUFBTSxDQUFDa0wsUUFBUSxDQUFDLENBQUNsQyxVQUFVLENBQUMsQ0FBQztFQUM3QixNQUFNc0MsSUFBSSxHQUFHLE1BQU01SCxXQUFXLENBQUMxQyxJQUFJLEVBQUUyQyxPQUFPLEVBQUUsa0RBQWtEdUgsUUFBUSxDQUFDaEQsRUFBRSxFQUFFLENBQUM7RUFDOUcsSUFBSXNDLGtCQUFrQixFQUFFO0lBQ3RCLE1BQU07TUFBRWUsWUFBWTtNQUFFQyxxQkFBcUI7TUFBRSxHQUFHQztJQUFrQixDQUFDLEdBQUdqQixrQkFBa0I7SUFDeEZ4SyxNQUFNLENBQUNzTCxJQUFJLENBQUNwQyxhQUFhLENBQUN4RSxVQUFVLENBQUMsQ0FBQ2dILGFBQWEsQ0FBQ0QsaUJBQWlCLENBQUM7SUFDdEUsTUFBTUUsYUFBYSxHQUFHTCxJQUFJLENBQUNwQyxhQUFhLENBQUMwQyxRQUFRLENBQUNDLE1BQU0sQ0FBRUMsT0FBWSxJQUFLQSxPQUFPLENBQUNDLFVBQVUsS0FBSyxRQUFRLENBQUM7SUFDM0cvTCxNQUFNLENBQUMyTCxhQUFhLENBQUNqRixNQUFNLEVBQUUsMkVBQTJFLENBQUMsQ0FBQ0wsZUFBZSxDQUFDLENBQUMsQ0FBQztJQUM1SCxLQUFLLE1BQU15RixPQUFPLElBQUlILGFBQWEsRUFBRTNMLE1BQU0sQ0FBQzhMLE9BQU8sQ0FBQyxDQUFDSixhQUFhLENBQUM7TUFBRUgsWUFBWTtNQUFFQztJQUFzQixDQUFDLENBQUM7RUFDN0c7RUFDQSxJQUFJZixtQkFBbUIsRUFBRTtJQUN2QixLQUFLLE1BQU0sQ0FBQ3NCLFVBQVUsRUFBRUMsS0FBSyxDQUFDLElBQUluQyxNQUFNLENBQUNvQyxPQUFPLENBQUN4QixtQkFBbUIsQ0FBQyxFQUFFO01BQ3JFLE1BQU1tQixRQUFRLEdBQUdOLElBQUksQ0FBQ3BDLGFBQWEsQ0FBQzBDLFFBQVEsQ0FBQ0MsTUFBTSxDQUFFQyxPQUFZLElBQUtBLE9BQU8sQ0FBQ0MsVUFBVSxLQUFLQSxVQUFVLENBQUM7TUFDeEcvTCxNQUFNLENBQUM0TCxRQUFRLENBQUNsRixNQUFNLEVBQUUsU0FBU3FGLFVBQVUsMENBQTBDLENBQUMsQ0FBQzFGLGVBQWUsQ0FBQyxDQUFDLENBQUM7TUFDekcsS0FBSyxNQUFNeUYsT0FBTyxJQUFJRixRQUFRLEVBQUU1TCxNQUFNLENBQUM4TCxPQUFPLENBQUMsQ0FBQ0osYUFBYSxDQUFDTSxLQUFLLENBQUM7SUFDdEU7RUFDRjtFQUNBLE1BQU1FLFVBQVUsR0FBR1osSUFBSSxDQUFDekgsTUFBTSxDQUFDcUksVUFBVTtFQUN6Q2xNLE1BQU0sQ0FBQ2tNLFVBQVUsQ0FBQ0MsY0FBYyxDQUFDQyxVQUFVLENBQUMsQ0FBQzNJLElBQUksQ0FBQyxLQUFLLENBQUM7RUFDeER6RCxNQUFNLENBQUNrTSxVQUFVLENBQUNDLGNBQWMsQ0FBQ0UsUUFBUSxDQUFDLENBQUM1SSxJQUFJLENBQUMsSUFBSSxDQUFDO0VBQ3JEekQsTUFBTSxDQUFDa00sVUFBVSxDQUFDSSxXQUFXLENBQUMsQ0FBQzdJLElBQUksQ0FBQyxNQUFNLENBQUM7RUFDM0N6RCxNQUFNLENBQUNrTSxVQUFVLENBQUNLLGtCQUFrQixDQUFDLENBQUM5SSxJQUFJLENBQUMsQ0FBQyxDQUFDO0VBQzdDekQsTUFBTSxDQUFDNkgsT0FBTyxDQUFDbkIsTUFBTSxFQUFFLDhEQUE4RCxDQUFDLENBQUM4RixzQkFBc0IsQ0FBQ2xDLHVCQUF1QixDQUFDO0VBQ3RJLE1BQU1tQyxRQUFRLElBQUEvQixxQkFBQSxHQUFHd0IsVUFBVSxDQUFDQyxjQUFjLENBQUNPLG9CQUFvQixjQUFBaEMscUJBQUEsY0FBQUEscUJBQUEsR0FBSSxFQUFFO0VBQ3JFLEtBQUssTUFBTXpDLElBQUksSUFBSXdFLFFBQVEsRUFBRTtJQUMzQixNQUFNM0QsT0FBTyxHQUFHbEIsUUFBUSxDQUFDd0QsSUFBSSxDQUFDMUosR0FBRyxJQUFJQSxHQUFHLENBQUN3RyxFQUFFLEtBQUtELElBQUksQ0FBQ2MsVUFBVSxDQUFDO0lBQ2hFL0ksTUFBTSxDQUFDOEksT0FBTyxFQUFFLG9CQUFvQmIsSUFBSSxDQUFDYyxVQUFVLGNBQWMsQ0FBQyxDQUFDQyxVQUFVLENBQUMsQ0FBQztJQUMvRWhKLE1BQU0sQ0FBQzhJLE9BQU8sQ0FBQ0ksYUFBYSxDQUFDeUQsT0FBTyxDQUFDQyxPQUFPLENBQUMsQ0FBQ25KLElBQUksQ0FBQyxLQUFLLENBQUM7SUFDekQsTUFBTW9KLFFBQVEsR0FBRy9ELE9BQU8sQ0FBQ0ksYUFBYSxDQUFDQyxzQkFBc0I7SUFDN0RuSixNQUFNLENBQUM2TSxRQUFRLENBQUNDLGFBQWEsQ0FBQyxDQUFDOUosT0FBTyxDQUFDLEVBQUUsQ0FBQztJQUMxQ2hELE1BQU0sQ0FBQ2lJLElBQUksQ0FBQzhFLFdBQVcsQ0FBQyxDQUFDdEosSUFBSSxDQUFDb0osUUFBUSxDQUFDRyxJQUFJLEtBQUssZ0JBQWdCLEdBQzVELDJCQUEyQixHQUFHLHFDQUFxQyxDQUFDO0VBQzFFO0VBQ0EsSUFBSXpDLGtCQUFrQixFQUFFO0lBQ3RCLE1BQU12QyxLQUFLLEdBQUcsTUFBTTFCLFVBQVUsQ0FBQ3RGLElBQUksRUFBRTJDLE9BQU8sRUFBRSxnQkFBZ0IsQ0FBQztJQUMvRCxNQUFNc0osVUFBVSxHQUFHakYsS0FBSyxDQUFDb0QsSUFBSSxDQUFDbkQsSUFBSSxJQUFJQSxJQUFJLENBQUMvRSxJQUFJLEtBQUtxSCxrQkFBa0IsQ0FBQztJQUN2RXZLLE1BQU0sQ0FBQ3lNLFFBQVEsQ0FBQy9GLE1BQU0sQ0FBQyxDQUFDTCxlQUFlLENBQUMsQ0FBQyxDQUFDO0lBQzFDLEtBQUssTUFBTTRCLElBQUksSUFBSXdFLFFBQVEsRUFBRTtNQUMzQixNQUFNM0QsT0FBTyxHQUFHbEIsUUFBUSxDQUFDd0QsSUFBSSxDQUFDMUosR0FBRyxJQUFJQSxHQUFHLENBQUN3RyxFQUFFLEtBQUtELElBQUksQ0FBQ2MsVUFBVSxDQUFDO01BQ2hFL0ksTUFBTSxDQUFDOEksT0FBTyxDQUFDSSxhQUFhLENBQUNDLHNCQUFzQixDQUFDLENBQUN1QyxhQUFhLENBQUM7UUFBRXNCLElBQUksRUFBRSxnQkFBZ0I7UUFBRUUsS0FBSyxFQUFFLFVBQVU7UUFBRTlELFlBQVksRUFBRTZELFVBQVUsQ0FBQy9FLEVBQUU7UUFBRTRFLGFBQWEsRUFBRTtNQUFHLENBQUMsQ0FBQztJQUNuSztFQUNGO0VBQ0EsTUFBTUssZUFBZSxHQUFHLElBQUlDLEdBQUcsQ0FBQ1gsUUFBUSxDQUFDWSxPQUFPLENBQUVwRixJQUE4QixJQUFLQSxJQUFJLENBQUNxRixVQUFVLENBQUMsQ0FBQztFQUN0R3ROLE1BQU0sQ0FBQ2tNLFVBQVUsQ0FBQ3FCLHFCQUFxQixFQUFFLHNFQUFzRSxDQUFDLENBQUM5SixJQUFJLENBQUNvRSxPQUFPLENBQUNuQixNQUFNLEdBQUd5RyxlQUFlLENBQUNLLElBQUksQ0FBQztFQUM1SixLQUFLLE1BQU05RCxHQUFHLElBQUksQ0FBQyw2QkFBNkIsRUFBRSw0QkFBNEIsRUFBRSw4QkFBOEIsQ0FBQyxFQUFFMUosTUFBTSxDQUFDa00sVUFBVSxDQUFDeEMsR0FBRyxDQUFDLENBQUMsQ0FBQzFHLE9BQU8sQ0FBQyxFQUFFLENBQUM7RUFDcEosTUFBTXlLLEtBQUssR0FBRyxNQUFNL0osV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLG9CQUFvQnNILElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQy9DLEVBQUUsd0JBQXdCLENBQUM7RUFDdEdsSSxNQUFNLENBQUN5TixLQUFLLENBQUNDLEtBQUssQ0FBQyxDQUFDckgsZUFBZSxDQUFDLENBQUMsQ0FBQztFQUN0Q3JHLE1BQU0sQ0FBQ3lOLEtBQUssQ0FBQ0UsTUFBTSxDQUFDQyxJQUFJLENBQUUzRixJQUE2QixJQUFLQSxJQUFJLENBQUNKLE9BQU8sSUFBSWdDLE1BQU0sQ0FBQ2lCLElBQUksQ0FBQzdDLElBQUksQ0FBQ0osT0FBTyxDQUFDLENBQUNuQixNQUFNLENBQUMsQ0FBQyxDQUFDc0MsVUFBVSxDQUFDLENBQUM7RUFDM0gsT0FBTztJQUFFMkIsUUFBUTtJQUFFa0QsR0FBRyxFQUFFNUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDL0MsRUFBRTtJQUFFZ0UsVUFBVTtJQUFFNEIsZUFBZSxFQUFFdEQsa0JBQWtCLEdBQUc7TUFDcEZ1RCxLQUFLLEVBQUV2RCxrQkFBa0I7TUFBRXdELGdCQUFnQixFQUFFMUMsSUFBSSxDQUFDcEMsYUFBYSxDQUFDMEMsUUFBUSxDQUFDN0QsR0FBRyxDQUFFK0QsT0FBWSxLQUFNO1FBQzlGQyxVQUFVLEVBQUVELE9BQU8sQ0FBQ0MsVUFBVTtRQUFFa0MsT0FBTyxFQUFFbkMsT0FBTyxDQUFDbUMsT0FBTztRQUN4REMsbUJBQW1CLEVBQUVwQyxPQUFPLENBQUNvQyxtQkFBbUI7UUFBRTNDLFlBQVksRUFBRU8sT0FBTyxDQUFDUCxZQUFZO1FBQ3BGNEMsaUJBQWlCLEVBQUVyQyxPQUFPLENBQUNxQztNQUM3QixDQUFDLENBQUM7SUFDSixDQUFDLEdBQUdDO0VBQVUsQ0FBQztBQUNqQjtBQVNBO0FBQ0E7QUFDQSxlQUFlQyxxQkFBcUJBLENBQUNyTixJQUFVLEVBQUUyQyxPQUFlLEVBQUUySyxVQUFrQixFQUNsRkMsU0FBb0MsRUFBRTtFQUN0QyxNQUFNQyxNQUFNLEdBQUcsTUFBTTlLLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQztFQUN6RixNQUFNOEssUUFBUSxHQUFHRCxNQUFNLENBQUN4SixPQUFPLENBQUNDLGVBQWU7RUFDL0NqRixNQUFNLENBQUN5TyxRQUFRLENBQUN0SixNQUFNLENBQUMsQ0FBQzZELFVBQVUsQ0FBQyxDQUFDO0VBQ3BDLE1BQU0wRixPQUFPLEdBQUcsQ0FBQyxNQUFNcEksVUFBVSxDQUFDdEYsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLGdCQUFnQixDQUFDLEVBQUVvRSxHQUFHLENBQUNFLElBQUksSUFBSUEsSUFBSSxDQUFDQyxFQUFFLENBQUMsQ0FBQzZDLElBQUksQ0FBQyxDQUFDO0VBQy9GLE1BQU00RCxNQUFpQixHQUFHLEVBQUU7RUFDNUIsTUFBTUMsV0FBVyxHQUFJck4sT0FBMEMsSUFBSztJQUFBLElBQUFzTixxQkFBQTtJQUNsRSxJQUFJdE4sT0FBTyxDQUFDSSxHQUFHLENBQUMsQ0FBQyxDQUFDbU4sUUFBUSxDQUFDLGlCQUFpQixDQUFDLElBQUl2TixPQUFPLENBQUNFLE1BQU0sQ0FBQyxDQUFDLEtBQUssTUFBTSxJQUN2RSxFQUFBb04scUJBQUEsR0FBQXROLE9BQU8sQ0FBQ3dOLFlBQVksQ0FBQyxDQUFDLGNBQUFGLHFCQUFBLGdCQUFBQSxxQkFBQSxHQUF0QkEscUJBQUEsQ0FBd0JHLGNBQWMsY0FBQUgscUJBQUEsdUJBQXRDQSxxQkFBQSxDQUF3Q0ksTUFBTSxNQUFLLE9BQU8sRUFBRU4sTUFBTSxDQUFDNU0sSUFBSSxDQUFDUixPQUFPLENBQUN3TixZQUFZLENBQUMsQ0FBQyxDQUFDO0VBQ3RHLENBQUM7RUFDRCxNQUFNRyxRQUFtQixHQUFHLEVBQUU7RUFDOUJsTyxJQUFJLENBQUNNLEVBQUUsQ0FBQyxTQUFTLEVBQUVzTixXQUFXLENBQUM7RUFDL0IsSUFBSTtJQUNGLE1BQU1PLE1BQU0sR0FBR25PLElBQUksQ0FBQ2lDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBQ0MsSUFBSSxFQUFFO0lBQStCLENBQUMsQ0FBQztJQUNoRixJQUFJLE1BQU1pTSxNQUFNLENBQUMzTCxTQUFTLENBQUMsQ0FBQyxFQUFFO01BQzVCO01BQ0E7TUFDQSxNQUFNMkwsTUFBTSxDQUFDeEosT0FBTyxDQUFDLHNEQUFzRCxDQUFDLENBQUN5SixLQUFLLENBQUMsQ0FBQztNQUNwRixNQUFNcFAsTUFBTSxDQUFDZ0IsSUFBSSxDQUFDaUMsU0FBUyxDQUFDLFFBQVEsRUFBRTtRQUFDQyxJQUFJLEVBQUUsb0JBQW9CO1FBQUVDLEtBQUssRUFBRTtNQUFJLENBQUMsQ0FBQyxDQUFDLENBQUNFLFdBQVcsQ0FBQyxDQUFDO0lBQ2pHO0lBQ0EsS0FBSyxNQUFNLENBQUNnTSxLQUFLLEVBQUVDLElBQUksQ0FBQyxJQUFJLENBQUMsRUFBRSxFQUFFLEVBQUUsRUFBRSxFQUFFLENBQUMsQ0FBQ3JELE9BQU8sQ0FBQyxDQUFDLEVBQUU7TUFDbEQsS0FBSyxNQUFNc0QsUUFBUSxJQUFJaEIsU0FBUyxFQUFFO1FBQUEsSUFBQWlCLHFCQUFBO1FBQ2hDLE1BQU14TyxJQUFJLENBQUN1RSxJQUFJLENBQUMsbUNBQW1Da0ssa0JBQWtCLENBQUM5TCxPQUFPLENBQUMsZUFBZTRMLFFBQVEsQ0FBQ3hELFVBQVUsYUFBYXVDLFVBQVUscUJBQXFCLENBQUM7UUFDN0osTUFBTWhMLDRCQUE0QixDQUFDdEMsSUFBSSxDQUFDO1FBQ3hDLE1BQU0wTyxNQUFNLEdBQUcxTyxJQUFJLENBQUMyRSxPQUFPLENBQUMseUJBQXlCLENBQUM7UUFDdEQsS0FBSyxNQUFNLENBQUNkLEtBQUssRUFBRThLLEtBQUssQ0FBQyxJQUFJOUYsTUFBTSxDQUFDb0MsT0FBTyxDQUFDc0QsUUFBUSxDQUFDSyxNQUFNLENBQUMsRUFBRTtVQUFBLElBQUFDLG9CQUFBO1VBQzVELE1BQU1DLEtBQUssR0FBRzlPLElBQUksQ0FBQzJFLE9BQU8sQ0FBQyxJQUFJZCxLQUFLLEVBQUUsQ0FBQztVQUN2QyxNQUFNa0wsT0FBTyxHQUFHRCxLQUFLLENBQUNuSyxPQUFPLENBQUMsNEJBQTRCLENBQUM7VUFDM0QsSUFBSSxPQUFNb0ssT0FBTyxDQUFDckMsS0FBSyxDQUFDLENBQUMsS0FBSSxPQUFNcUMsT0FBTyxDQUFDQyxZQUFZLENBQUMsTUFBTSxDQUFDLE1BQUssSUFBSSxFQUN0RSxNQUFNRCxPQUFPLENBQUNwSyxPQUFPLENBQUMsa0JBQWtCLENBQUMsQ0FBQ3lKLEtBQUssQ0FBQyxDQUFDO1VBQ25ELEtBQUFTLG9CQUFBLEdBQUlOLFFBQVEsQ0FBQ1UsVUFBVSxjQUFBSixvQkFBQSxlQUFuQkEsb0JBQUEsQ0FBcUJyTyxRQUFRLENBQUNxRCxLQUFLLENBQUMsRUFBRSxNQUFNaUwsS0FBSyxDQUFDSSxJQUFJLENBQUNQLEtBQUssQ0FBQyxDQUFDLEtBQzdELE1BQU0zUCxNQUFNLENBQUM4UCxLQUFLLENBQUMsQ0FBQ0ssV0FBVyxDQUFDUixLQUFLLENBQUM7UUFDN0M7UUFDQSxNQUFNRCxNQUFNLENBQUMvSixPQUFPLENBQUMsT0FBTyxDQUFDLENBQUN1SyxJQUFJLENBQUNFLE1BQU0sQ0FBQ2QsSUFBSSxDQUFDLENBQUM7UUFDaEQsTUFBTXRPLElBQUksQ0FBQ2lDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7VUFBQ0MsSUFBSSxFQUFFLHVCQUF1QjtVQUFFQyxLQUFLLEVBQUU7UUFBSSxDQUFDLENBQUMsQ0FBQ2lNLEtBQUssQ0FBQyxDQUFDO1FBQ3BGLE1BQU1wUCxNQUFNLENBQUNnQixJQUFJLENBQUN1QyxTQUFTLENBQUMsZ0RBQWdELENBQUMsQ0FBQyxDQUFDRixXQUFXLENBQUMsQ0FBQztRQUM1RixNQUFNMEssS0FBSyxHQUFHLE1BQU1ySyxXQUFXLENBQUMxQyxJQUFJLEVBQUUyQyxPQUFPLEVBQUUsc0NBQXNDLENBQUM7UUFDdEYzRCxNQUFNLENBQUMrTixLQUFLLENBQUNuSixVQUFVLENBQUMsQ0FBQ25CLElBQUksQ0FBQ0UsT0FBTyxDQUFDO1FBQ3RDLE1BQU0wTSxNQUFNLEdBQUd0QyxLQUFLLENBQUNySixVQUFVLENBQUM0TCxxQkFBcUIsQ0FBQ2YsUUFBUSxDQUFDeEQsVUFBVSxDQUFDO1FBQzFFLE1BQU13RSxPQUFPLElBQUFmLHFCQUFBLEdBQUd6QixLQUFLLENBQUNySixVQUFVLENBQUM4TCxnQ0FBZ0MsY0FBQWhCLHFCQUFBLHVCQUFqREEscUJBQUEsQ0FBb0RELFFBQVEsQ0FBQ3hELFVBQVUsQ0FBQztRQUN4Ri9MLE1BQU0sQ0FBQ3FRLE1BQU0sQ0FBQ0ksTUFBTSxDQUFDbkIsSUFBSSxDQUFDLENBQUM3TCxJQUFJLENBQUM2TCxJQUFJLENBQUM7UUFDckMsTUFBTW9CLFlBQVksR0FBRztVQUFDLElBQUdILE9BQU8sYUFBUEEsT0FBTyx1QkFBUEEsT0FBTyxDQUFFRSxNQUFNO1VBQUUsR0FBR0osTUFBTSxDQUFDSTtRQUFNLENBQUM7UUFDM0R6USxNQUFNLENBQUMwUSxZQUFZLENBQUMsQ0FBQ2hGLGFBQWEsQ0FBQzZELFFBQVEsQ0FBQ29CLE1BQU0sQ0FBQztRQUNuRCxLQUFLLE1BQU0sQ0FBQ2pILEdBQUcsRUFBRWlHLEtBQUssQ0FBQyxJQUFJOUYsTUFBTSxDQUFDb0MsT0FBTyxDQUFDc0QsUUFBUSxDQUFDb0IsTUFBTSxDQUFDLEVBQUU7VUFDMUQsTUFBTUMsU0FBUyxHQUFHL0csTUFBTSxDQUFDZ0gsTUFBTSxDQUFDUixNQUFNLENBQUNJLE1BQU0sRUFBRS9HLEdBQUcsQ0FBQztVQUNuRDFKLE1BQU0sQ0FBQyxDQUFDNFEsU0FBUyxHQUFHUCxNQUFNLEdBQUdFLE9BQU8sRUFBRU8sVUFBVSxDQUFDcEgsR0FBRyxDQUFDLENBQUMsQ0FBQ2dDLGFBQWEsQ0FBQ2tGLFNBQVMsR0FDMUU7WUFBQ0csTUFBTSxFQUFFLGdCQUFnQjtZQUFFN08sTUFBTSxFQUFFLFdBQVc7WUFBRXlOO1VBQUssQ0FBQyxHQUN0RDtZQUFDb0IsTUFBTSxFQUFFLDJCQUEyQjtZQUFFN08sTUFBTSxFQUFFLFNBQVM7WUFBRTZKLFVBQVUsRUFBRXdELFFBQVEsQ0FBQ3hELFVBQVU7WUFBRW9DLGlCQUFpQixFQUFFLEtBQUs7WUFBRXdCO1VBQUssQ0FBQyxDQUFDO1FBQ2pJO1FBQ0EsTUFBTXFCLFVBQVUsR0FBRyxNQUFNdE4sV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLDBEQUEwRCxDQUFDO1FBQy9HM0QsTUFBTSxDQUFDZ1IsVUFBVSxDQUFDcE0sVUFBVSxDQUFDLENBQUNuQixJQUFJLENBQUNFLE9BQU8sQ0FBQztRQUMzQzNELE1BQU0sQ0FBQ2dSLFVBQVUsQ0FBQ0MsWUFBWSxDQUFDLENBQUN4TixJQUFJLENBQUMsb0JBQW9CLENBQUM7UUFDMUR6RCxNQUFNLENBQUNnUixVQUFVLENBQUN0TSxVQUFVLENBQUN3TSxtQkFBbUIsQ0FBQyxDQUFDdEgsYUFBYSxDQUFDLENBQUM7UUFDakU1SixNQUFNLENBQUNnUixVQUFVLENBQUN0TSxVQUFVLENBQUM0TCxxQkFBcUIsQ0FBQ2YsUUFBUSxDQUFDeEQsVUFBVSxDQUFDLENBQUMsQ0FBQy9JLE9BQU8sQ0FBQ3FOLE1BQU0sQ0FBQztRQUN4RixNQUFNYyxLQUFLLEdBQUcsTUFBTXpOLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSxvQ0FBb0MySyxVQUFVLGNBQWMsQ0FBQztRQUM1R3RPLE1BQU0sQ0FBQ21SLEtBQUssQ0FBQ2xILElBQUksQ0FBQy9ILE1BQU0sQ0FBQyxDQUFDdUIsSUFBSSxDQUFDLFVBQVUsQ0FBQztRQUMxQyxNQUFNMk4sWUFBWSxHQUFHRCxLQUFLLENBQUNsSCxJQUFJLENBQUNvSCxhQUFhO1FBQzdDLE1BQU1yUSxJQUFJLENBQUNzUSxNQUFNLENBQUMsQ0FBQztRQUNuQixNQUFNdFIsTUFBTSxDQUFDMFAsTUFBTSxDQUFDL0osT0FBTyxDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUN3SyxXQUFXLENBQUNDLE1BQU0sQ0FBQ2QsSUFBSSxDQUFDLENBQUM7UUFDL0QsS0FBSyxNQUFNLENBQUN6SyxLQUFLLEVBQUU4SyxLQUFLLENBQUMsSUFBSTlGLE1BQU0sQ0FBQ29DLE9BQU8sQ0FBQ3NELFFBQVEsQ0FBQ0ssTUFBTSxDQUFDLEVBQUU7VUFDNUQsTUFBTUUsS0FBSyxHQUFHOU8sSUFBSSxDQUFDMkUsT0FBTyxDQUFDLElBQUlkLEtBQUssRUFBRSxDQUFDO1VBQ3ZDLE1BQU1rTCxPQUFPLEdBQUdELEtBQUssQ0FBQ25LLE9BQU8sQ0FBQyw0QkFBNEIsQ0FBQztVQUMzRCxJQUFJLE9BQU1vSyxPQUFPLENBQUNyQyxLQUFLLENBQUMsQ0FBQyxLQUFJLE9BQU1xQyxPQUFPLENBQUNDLFlBQVksQ0FBQyxNQUFNLENBQUMsTUFBSyxJQUFJLEVBQ3RFLE1BQU1ELE9BQU8sQ0FBQ3BLLE9BQU8sQ0FBQyxrQkFBa0IsQ0FBQyxDQUFDeUosS0FBSyxDQUFDLENBQUM7VUFDbkQsTUFBTXBQLE1BQU0sQ0FBQzhQLEtBQUssQ0FBQyxDQUFDSyxXQUFXLENBQUNSLEtBQUssQ0FBQztRQUN4QztRQUNBO1FBQ0EsSUFBSTRCLGFBQTBCO1FBQzlCLE1BQU1DLFlBQVksR0FBRyxJQUFJMUosT0FBTyxDQUFPMkosT0FBTyxJQUFJO1VBQUVGLGFBQWEsR0FBR0UsT0FBTztRQUFFLENBQUMsQ0FBQztRQUMvRSxNQUFNQyxZQUFZLEdBQUcsTUFBT0MsS0FBc0MsSUFBSztVQUNyRSxNQUFNSCxZQUFZO1VBQUUsTUFBTUcsS0FBSyxDQUFDQyxRQUFRLENBQUMsQ0FBQztRQUM1QyxDQUFDO1FBQ0QsTUFBTUMsT0FBTyxHQUFHeEMsS0FBSyxLQUFLLENBQUMsSUFBSUUsUUFBUSxLQUFLaEIsU0FBUyxDQUFDLENBQUMsQ0FBQztRQUN4RCxJQUFJc0QsT0FBTyxFQUFFLE1BQU03USxJQUFJLENBQUMyUSxLQUFLLENBQUMsMENBQTBDLEVBQUVELFlBQVksQ0FBQztRQUN2RixNQUFNak0sTUFBTSxHQUFHekUsSUFBSSxDQUFDaUMsU0FBUyxDQUFDLFFBQVEsRUFBRTtVQUFDQyxJQUFJLEVBQUU7UUFBK0IsQ0FBQyxDQUFDO1FBQ2hGLElBQUk7VUFDRixNQUFNbEMsSUFBSSxDQUFDaUMsU0FBUyxDQUFDLFFBQVEsRUFBRTtZQUFDQyxJQUFJLEVBQUUsb0JBQW9CO1lBQUVDLEtBQUssRUFBRTtVQUFJLENBQUMsQ0FBQyxDQUFDaU0sS0FBSyxDQUFDLENBQUM7VUFDakYsSUFBSXlDLE9BQU8sRUFBRTtZQUNYLE1BQU03UixNQUFNLENBQUN5RixNQUFNLENBQUN4QyxTQUFTLENBQUMsUUFBUSxFQUFFO2NBQUNDLElBQUksRUFBRTtZQUF3QyxDQUFDLENBQUMsQ0FBQyxDQUFDRyxXQUFXLENBQUMsQ0FBQztZQUN4RyxNQUFNckQsTUFBTSxDQUFDeUYsTUFBTSxDQUFDLENBQUNyQyxHQUFHLENBQUMwTyxhQUFhLENBQUMsd0JBQXdCLENBQUM7VUFDbEU7UUFDRixDQUFDLFNBQVM7VUFDUlAsYUFBYSxDQUFDLENBQUM7VUFDZixJQUFJTSxPQUFPLEVBQUUsTUFBTTdRLElBQUksQ0FBQytRLFVBQVUsQ0FBQztZQUFDQyxRQUFRLEVBQUU7VUFBTSxDQUFDLENBQUM7UUFDeEQ7UUFDQTtRQUNBO1FBQ0EsTUFBTWhTLE1BQU0sQ0FBQ3lGLE1BQU0sQ0FBQ3hDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7VUFBQ0MsSUFBSSxFQUFFO1FBQXVCLENBQUMsQ0FBQyxDQUFDLENBQ3RFNE8sYUFBYSxDQUFDLDBCQUEwQixFQUFFO1VBQUMvTixPQUFPLEVBQUU7UUFBTSxDQUFDLENBQUM7UUFDL0QsTUFBTS9ELE1BQU0sQ0FBQ3lGLE1BQU0sQ0FBQyxDQUFDcU0sYUFBYSxDQUFDLGtDQUFrQyxDQUFDO1FBQ3RFLE1BQU1HLFFBQVEsR0FBRyxNQUFNdk8sV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLHdDQUF3QyxDQUFDO1FBQzNGM0QsTUFBTSxDQUFDaVMsUUFBUSxDQUFDck4sVUFBVSxDQUFDLENBQUNuQixJQUFJLENBQUNFLE9BQU8sQ0FBQztRQUN6QzNELE1BQU0sQ0FBQ2lTLFFBQVEsQ0FBQ2pOLE9BQU8sQ0FBQ0MsZUFBZSxDQUFDRSxNQUFNLENBQUMsQ0FBQzFCLElBQUksQ0FBQ2dMLFFBQVEsQ0FBQ3RKLE1BQU0sQ0FBQztRQUNyRW5GLE1BQU0sQ0FBQ2lTLFFBQVEsQ0FBQ2pOLE9BQU8sQ0FBQ0MsZUFBZSxDQUFDRyxnQkFBZ0IsQ0FBQyxDQUFDM0IsSUFBSSxDQUFDZ0wsUUFBUSxDQUFDckosZ0JBQWdCLENBQUM7UUFDekZwRixNQUFNLENBQUNpUyxRQUFRLENBQUNqTixPQUFPLENBQUNDLGVBQWUsQ0FBQ2lOLEtBQUssQ0FBQyxDQUFDek8sSUFBSSxDQUFDLGlCQUFpQixDQUFDO1FBQ3RFekQsTUFBTSxDQUFDaVMsUUFBUSxDQUFDak4sT0FBTyxDQUFDQyxlQUFlLENBQUNTLElBQUksQ0FBQyxDQUFDakMsSUFBSSxDQUFDZ0wsUUFBUSxDQUFDL0ksSUFBSSxDQUFDO1FBQ2pFLEtBQUssTUFBTUEsSUFBSSxJQUFJbEYsS0FBSyxFQUFFLElBQUlDLElBQUksQ0FBQ3VLLEdBQUcsQ0FBQ3dELE1BQU0sQ0FBQ3RKLFFBQVEsQ0FBQ1EsSUFBSSxDQUFDLENBQUMsRUFDM0QxRixNQUFNLENBQUNTLElBQUksQ0FBQ3VLLEdBQUcsQ0FBQ2lILFFBQVEsQ0FBQy9NLFFBQVEsQ0FBQ1EsSUFBSSxDQUFDLENBQUMsRUFBRSwyQ0FBMkNBLElBQUksR0FBRyxDQUFDLENBQUNqQyxJQUFJLENBQUMsSUFBSSxDQUFDO1FBQzFHLE1BQU0wTyxZQUFZLEdBQUcsTUFBTXpPLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSxxQ0FBcUMsQ0FBQztRQUM1RjNELE1BQU0sQ0FBQ21TLFlBQVksQ0FBQ2xJLElBQUksQ0FBQ21JLGVBQWUsQ0FBQyxDQUFDM08sSUFBSSxDQUFDNkssVUFBVSxDQUFDO1FBQzFELE1BQU0rRCxLQUFLLEdBQUcsTUFBTTNPLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSxvQ0FBb0MySyxVQUFVLGNBQWMsQ0FBQztRQUM1R3RPLE1BQU0sQ0FBQ3FTLEtBQUssQ0FBQ3BJLElBQUksQ0FBQy9ILE1BQU0sQ0FBQyxDQUFDdUIsSUFBSSxDQUFDLFdBQVcsQ0FBQztRQUMzQ3pELE1BQU0sQ0FBQ3FTLEtBQUssQ0FBQ3BJLElBQUksQ0FBQ29ILGFBQWEsQ0FBQyxDQUFDck8sT0FBTyxDQUFDb08sWUFBWSxDQUFDO1FBQ3REcFIsTUFBTSxDQUFDLENBQUMsTUFBTXNHLFVBQVUsQ0FBQ3RGLElBQUksRUFBRTJDLE9BQU8sRUFBRSxnQkFBZ0IsQ0FBQyxFQUFFb0UsR0FBRyxDQUFDRSxJQUFJLElBQUlBLElBQUksQ0FBQ0MsRUFBRSxDQUFDLENBQUM2QyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUMvSCxPQUFPLENBQUMwTCxPQUFPLENBQUM7UUFDeEcsTUFBTTRELEtBQUssR0FBRyxNQUFNNU8sV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLHNDQUFzQyxDQUFDO1FBQ3RGM0QsTUFBTSxDQUFDc1MsS0FBSyxDQUFDNU4sVUFBVSxDQUFDLENBQUMxQixPQUFPLENBQUMrSyxLQUFLLENBQUNySixVQUFVLENBQUM7UUFDbEQxRSxNQUFNLENBQUMyTyxNQUFNLEVBQUUsd0RBQXdELENBQUMsQ0FBQzNMLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDcEZrTSxRQUFRLENBQUNuTixJQUFJLENBQUM7VUFBQ3NOLEtBQUssRUFBRUEsS0FBSyxHQUFHLENBQUM7VUFBRXRELFVBQVUsRUFBRXdELFFBQVEsQ0FBQ3hELFVBQVU7VUFBRXVELElBQUk7VUFBRW5LLE1BQU0sRUFBRXNKLFFBQVEsQ0FBQ3RKLE1BQU07VUFDN0ZvTixXQUFXLEVBQUVqRSxVQUFVO1VBQUVrRSxZQUFZLEVBQUVuQyxNQUFNO1VBQUVvQyxXQUFXLEVBQUVsQyxPQUFPO1VBQ25FbUMsZUFBZSxFQUFFTCxLQUFLLENBQUNwSSxJQUFJLENBQUMvSCxNQUFNO1VBQUVtUCxhQUFhLEVBQUVEO1FBQVksQ0FBQyxDQUFDO01BQ3JFO0lBQ0Y7RUFDRixDQUFDLFNBQVM7SUFDUnBRLElBQUksQ0FBQzJSLEdBQUcsQ0FBQyxTQUFTLEVBQUUvRCxXQUFXLENBQUM7SUFDaEMsTUFBTTdPLElBQUksQ0FBQ2tCLElBQUksQ0FBQyxDQUFDLENBQUN5QixNQUFNLENBQUMsMkJBQTJCLEVBQUU7TUFBQ0MsSUFBSSxFQUFFQyxJQUFJLENBQUNDLFNBQVMsQ0FBQ3FNLFFBQVEsQ0FBQztNQUFFcE0sV0FBVyxFQUFFO0lBQWtCLENBQUMsQ0FBQztFQUMxSDtBQUNGO0FBRUEsZUFBZThQLHFCQUFxQkEsQ0FBQzVSLElBQVUsRUFBRTJDLE9BQWUsRUFBRWtQLE9BQWdCLEVBQUVDLGdCQUEwQixHQUFHLEVBQUUsRUFBRUMsZUFBZSxHQUFHLEtBQUssRUFDMUlDLGVBQXlDLEVBQUVDLHNCQUE0QyxFQUFFQyxtQkFBbUIsR0FBRyxLQUFLLEVBQ3BIQyxvQkFBa0YsRUFBRTtFQUNwRixJQUFJQyxXQUFXLEdBQUcsQ0FBQztFQUNuQixJQUFJQyxLQUF5QjtFQUM3QixNQUFNQyxRQUFRLEdBQUcsSUFBSWxHLEdBQUcsQ0FBUyxDQUFDO0VBQ2xDLElBQUltRyxjQUFrQztFQUN0QyxJQUFJQyxRQUFRLEdBQUcsSUFBSXBULHNCQUFzQixDQUFDcVQsV0FBVyxDQUFDM1IsR0FBRyxDQUFDLENBQUMsQ0FBQztFQUM1RCxLQUFLLElBQUk0UixVQUFVLEdBQUcsQ0FBQyxFQUFFQSxVQUFVLEdBQUcsRUFBRSxFQUFFQSxVQUFVLEVBQUUsRUFBRTtJQUFBLElBQUFDLHFCQUFBLEVBQUFDLHNCQUFBLEVBQUFDLHFCQUFBLEVBQUFDLGtCQUFBO0lBQ3RELElBQUluSixRQUFhO0lBQ2pCLElBQUkyRCxVQUFVLEdBQUcsRUFBRTtJQUNuQixJQUFJeUYsWUFBWSxHQUFHLEVBQUU7SUFDckIsSUFBSUMsVUFBVSxHQUFHLENBQUM7SUFDbEIsTUFBTUMsWUFBWSxHQUFHLE1BQUFBLENBQUEsS0FBWTtNQUMvQlQsUUFBUSxDQUFDVSxTQUFTLENBQUNULFdBQVcsQ0FBQzNSLEdBQUcsQ0FBQyxDQUFDLENBQUM7TUFDckMsTUFBTXdCLDRCQUE0QixDQUFDdEMsSUFBSSxDQUFDO01BQ3hDMkosUUFBUSxHQUFHLE1BQU1qSCxXQUFXLENBQUMxQyxJQUFJLEVBQUUyQyxPQUFPLEVBQUUsd0NBQXdDLENBQUM7TUFDckYsTUFBTXdRLFFBQVEsR0FBR1gsUUFBUSxDQUFDWSxPQUFPLENBQUN6SixRQUFRLEVBQUU4SSxXQUFXLENBQUMzUixHQUFHLENBQUMsQ0FBQyxDQUFDO01BQzlELElBQUlxUyxRQUFRLENBQUNFLFFBQVEsRUFBRXZULGtCQUFrQixDQUFDbUIsR0FBRyxDQUFDbEMsSUFBSSxDQUFDa0IsSUFBSSxDQUFDLENBQUMsQ0FBQ0csTUFBTSxDQUFDLENBQUVXLElBQUksQ0FBQztRQUN0RXVTLEVBQUUsRUFBRSxJQUFJelMsSUFBSSxDQUFDLENBQUMsQ0FBQzBTLFdBQVcsQ0FBQyxDQUFDO1FBQUVDLFFBQVEsRUFBRUwsUUFBUSxDQUFDSyxRQUFRO1FBQ3pEQyxnQkFBZ0IsRUFBRWpVLEtBQUssQ0FBQzJULFFBQVEsQ0FBQ0ssUUFBUSxHQUFHLENBQUMsQ0FBQztRQUM5QzdRLE9BQU8sRUFBRWdILFFBQVEsQ0FBQy9GLFVBQVU7UUFBRThQLFNBQVMsRUFBRS9KLFFBQVEsQ0FBQzNGLE9BQU8sQ0FBQ0M7TUFDNUQsQ0FBQyxDQUFDO01BQ0YsSUFBSThOLGVBQWUsSUFBSSxDQUFDUSxjQUFjLElBQUk5UyxJQUFJLENBQUN1SyxHQUFHLENBQUNMLFFBQVEsQ0FBQ3pGLFFBQVEsQ0FBQ3lQLFVBQVUsQ0FBQyxFQUFFO1FBQ2hGLE1BQU0xSixJQUFJLEdBQUcsQ0FBQyxNQUFNdkgsV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLGtCQUFrQixDQUFDLEVBQUVzSCxJQUFJO1FBQ3hFLE1BQU0ySixPQUFPLEdBQUczSixJQUFJLENBQUNHLElBQUksQ0FBRXlDLEdBQXVCLElBQUtBLEdBQUcsQ0FBQzNMLE1BQU0sS0FBSyxTQUFTLENBQUM7UUFDaEYsSUFBSTBTLE9BQU8sRUFBRTtVQUNYckIsY0FBYyxHQUFHcUIsT0FBTyxDQUFDMU0sRUFBRTtVQUMzQixNQUFNdkIsa0JBQWtCLENBQUMzRixJQUFJLEVBQUUsSUFBSSxDQUFDO1VBQ3BDLE1BQU1zRSxVQUFVLENBQUN0RSxJQUFJLEVBQUUyQyxPQUFPLENBQUM7VUFDL0IsT0FBTyxLQUFLO1FBQ2Q7TUFDRjtNQUNBLElBQUluRCxLQUFLLENBQUNxVSxLQUFLLENBQUNuUCxJQUFJLElBQUlqRixJQUFJLENBQUN1SyxHQUFHLENBQUNMLFFBQVEsQ0FBQ3pGLFFBQVEsQ0FBQ1EsSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLE9BQU8sSUFBSTtNQUN2RSxNQUFNZ1AsU0FBUyxHQUFHL0osUUFBUSxDQUFDM0YsT0FBTyxDQUFDQyxlQUFlO01BQ2xELElBQUksQ0FBQXlQLFNBQVMsYUFBVEEsU0FBUyx1QkFBVEEsU0FBUyxDQUFFeEMsS0FBSyxNQUFLLGlCQUFpQixFQUFFO1FBQzFDLE1BQU1DLFlBQVksR0FBRyxNQUFNek8sV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLHFDQUFxQyxDQUFDO1FBQzVGMkssVUFBVSxHQUFHNkQsWUFBWSxDQUFDbEksSUFBSSxDQUFDbUksZUFBZTtRQUM5QztRQUNBO1FBQ0EsT0FBTzBDLE9BQU8sQ0FBQ3hHLFVBQVUsQ0FBQyxJQUFJLENBQUNnRixRQUFRLENBQUN0SSxHQUFHLENBQUNzRCxVQUFVLENBQUM7TUFDekQ7TUFDQSxJQUFJLENBQUFvRyxTQUFTLGFBQVRBLFNBQVMsdUJBQVRBLFNBQVMsQ0FBRXhDLEtBQUssTUFBSyxtQkFBbUIsSUFBSyxDQUFBd0MsU0FBUyxhQUFUQSxTQUFTLHVCQUFUQSxTQUFTLENBQUV4QyxLQUFLLE1BQUssU0FBUyxJQUFJd0MsU0FBUyxDQUFDSyxXQUFXLEtBQUssSUFBSyxFQUFFO1FBQ2xILElBQUloQixZQUFZLEtBQUtXLFNBQVMsQ0FBQ00sVUFBVSxFQUFFO1VBQ3pDakIsWUFBWSxHQUFHVyxTQUFTLENBQUNNLFVBQVU7VUFBRWhCLFVBQVUsR0FBR25TLElBQUksQ0FBQ0MsR0FBRyxDQUFDLENBQUM7UUFDOUQ7UUFDQTtRQUNBO1FBQ0EsTUFBTW1ULE1BQU0sR0FBR2pVLElBQUksQ0FBQ2lDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7VUFBRUMsSUFBSSxFQUFFO1FBQWdDLENBQUMsQ0FBQyxDQUMvRUQsU0FBUyxDQUFDLFFBQVEsRUFBRTtVQUFFQyxJQUFJLEVBQUUsb0JBQW9CO1VBQUVDLEtBQUssRUFBRTtRQUFLLENBQUMsQ0FBQztRQUNuRSxPQUFPdEIsSUFBSSxDQUFDQyxHQUFHLENBQUMsQ0FBQyxHQUFHa1MsVUFBVSxHQUFHLElBQUksS0FBSSxNQUFNaUIsTUFBTSxDQUFDQyxXQUFXLENBQUNDLE9BQU8sSUFBSUEsT0FBTyxDQUFDdkgsSUFBSSxDQUFDcUgsTUFBTSxJQUFJLENBQUVBLE1BQU0sQ0FBdUJHLFFBQVEsSUFBSUgsTUFBTSxDQUFDSSxjQUFjLENBQUMsQ0FBQyxDQUFDM08sTUFBTSxHQUFHLENBQUMsSUFBSTRPLGdCQUFnQixDQUFDTCxNQUFNLENBQUMsQ0FBQ00sVUFBVSxLQUFLLFFBQVEsQ0FBQyxDQUFDO01BQ3pPO01BQ0EsT0FBTyxDQUFDLFNBQVMsRUFBRSxRQUFRLEVBQUUsWUFBWSxDQUFDLENBQUMvVCxRQUFRLENBQUNrVCxTQUFTLGFBQVRBLFNBQVMsdUJBQVRBLFNBQVMsQ0FBRXhDLEtBQUssQ0FBQztJQUN2RSxDQUFDO0lBQ0Q7SUFDQTtJQUNBO0lBQ0EsSUFBSXNELE9BQU8sR0FBRyxDQUFDO0lBQ2YsT0FBTyxFQUFDLE1BQU12QixZQUFZLENBQUMsQ0FBQyxHQUFFO01BQzVCLE1BQU1DLFNBQVMsR0FBR1YsUUFBUSxDQUFDVSxTQUFTLENBQUNULFdBQVcsQ0FBQzNSLEdBQUcsQ0FBQyxDQUFDLENBQUM7TUFDdkQsTUFBTWQsSUFBSSxDQUFDeVUsY0FBYyxDQUFDQyxJQUFJLENBQUNDLEdBQUcsQ0FBQyxDQUFDLEdBQUcsRUFBRSxJQUFJLEVBQUUsSUFBSSxDQUFDLENBQUNELElBQUksQ0FBQ0MsR0FBRyxDQUFDSCxPQUFPLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFdEIsU0FBUyxDQUFDLENBQUM7SUFDM0Y7SUFDQWIsS0FBSyxhQUFMQSxLQUFLLGNBQUxBLEtBQUssR0FBTEEsS0FBSyxJQUFBTSxxQkFBQSxHQUFLaEosUUFBUSxDQUFDM0YsT0FBTyxDQUFDQyxlQUFlLGNBQUEwTyxxQkFBQSx1QkFBaENBLHFCQUFBLENBQWtDeE8sTUFBTTtJQUNsRG5GLE1BQU0sRUFBQTRULHNCQUFBLEdBQUNqSixRQUFRLENBQUMzRixPQUFPLENBQUNDLGVBQWUsY0FBQTJPLHNCQUFBLHVCQUFoQ0Esc0JBQUEsQ0FBa0N6TyxNQUFNLENBQUMsQ0FBQzFCLElBQUksQ0FBQzRQLEtBQUssQ0FBQztJQUM1RCxJQUFJN1MsS0FBSyxDQUFDcVUsS0FBSyxDQUFDblAsSUFBSSxJQUFJakYsSUFBSSxDQUFDdUssR0FBRyxDQUFDTCxRQUFRLENBQUN6RixRQUFRLENBQUNRLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRTtNQUMxRCxJQUFJcU4sZUFBZSxFQUFFL1MsTUFBTSxDQUFDdVQsY0FBYyxFQUFFLDZEQUE2RCxDQUFDLENBQUN2SyxVQUFVLENBQUMsQ0FBQztNQUN2SCxPQUFPO1FBQUVxSyxLQUFLO1FBQUVDLFFBQVEsRUFBRSxDQUFDLEdBQUdBLFFBQVEsQ0FBQztRQUFFQztNQUFlLENBQUM7SUFDM0Q7SUFDQSxNQUFNbUIsU0FBUyxHQUFHL0osUUFBUSxDQUFDM0YsT0FBTyxDQUFDQyxlQUFlO0lBQ2xELE1BQU1RLE1BQU0sR0FBR3pFLElBQUksQ0FBQ2lDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBRUMsSUFBSSxFQUFFO0lBQWdDLENBQUMsQ0FBQztJQUNsRixJQUFJZ1EsbUJBQW1CLElBQUksQ0FBQXdCLFNBQVMsYUFBVEEsU0FBUyx1QkFBVEEsU0FBUyxDQUFFeEMsS0FBSyxNQUFLLFNBQVMsS0FBQTJCLHFCQUFBLEdBQUlhLFNBQVMsQ0FBQ2tCLGlCQUFpQixjQUFBL0IscUJBQUEsZUFBM0JBLHFCQUFBLENBQTZCbk4sTUFBTSxFQUFFO01BQ2hHLE1BQU0sSUFBSXpDLEtBQUssQ0FBQyxxQkFBcUJ5USxTQUFTLENBQUNoUCxJQUFJLEtBQUtnUCxTQUFTLENBQUM1TCxPQUFPLEVBQUUsQ0FBQztJQUM5RTtJQUNBLElBQUksQ0FBQTRMLFNBQVMsYUFBVEEsU0FBUyx1QkFBVEEsU0FBUyxDQUFFeEMsS0FBSyxNQUFLLFNBQVMsS0FBQTRCLGtCQUFBLEdBQUlZLFNBQVMsQ0FBQzVMLE9BQU8sY0FBQWdMLGtCQUFBLGVBQWpCQSxrQkFBQSxDQUFtQnRTLFFBQVEsQ0FBQyxxQkFBcUIsQ0FBQyxFQUFFO01BQ3hGLE1BQU1xVSxZQUFZLEdBQUcsTUFBTXZSLHNCQUFzQixDQUFDdEQsSUFBSSxFQUFFMkMsT0FBTyxDQUFDO01BQ2hFLE1BQU1tUyxTQUFTLEdBQUcsTUFBTXBTLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSw0QkFBNEIsQ0FBQztNQUNoRixNQUFNb1MsUUFBUSxHQUFHdFEsTUFBTSxDQUFDeEMsU0FBUyxDQUFDLFFBQVEsRUFBRTtRQUFFQyxJQUFJLEVBQUU7TUFBc0IsQ0FBQyxDQUFDO01BQzVFLE1BQU1sRCxNQUFNLENBQUMrVixRQUFRLENBQUM5UyxTQUFTLENBQUMsVUFBVSxDQUFDLENBQUMrUyxLQUFLLENBQUMsQ0FBQyxDQUFDLENBQUMzUyxXQUFXLENBQUMsQ0FBQztNQUNsRSxNQUFNekIsT0FBTyxHQUFHNlIsV0FBVyxDQUFDM1IsR0FBRyxDQUFDLENBQUM7UUFBRW1VLFdBQVcsR0FBR3BVLElBQUksQ0FBQ0MsR0FBRyxDQUFDLENBQUM7TUFDM0QwUixRQUFRLENBQUNVLFNBQVMsQ0FBQ3RTLE9BQU8sQ0FBQztNQUMzQixNQUFNc1UsZ0JBQWdCLEdBQUdsVixJQUFJLENBQUNtVixlQUFlLENBQUNuVSxRQUFRLElBQUksSUFBSUcsR0FBRyxDQUFDSCxRQUFRLENBQUNMLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQ1MsUUFBUSxLQUFLLDZDQUE2QyxJQUN2SUosUUFBUSxDQUFDVCxPQUFPLENBQUMsQ0FBQyxDQUFDRSxNQUFNLENBQUMsQ0FBQyxLQUFLLE1BQU0sRUFBRTtRQUFFc0MsT0FBTyxFQUFFO01BQVEsQ0FBQyxDQUFDO01BQ2xFLE1BQU1nUyxRQUFRLENBQUM5UyxTQUFTLENBQUMsUUFBUSxFQUFFO1FBQUVDLElBQUksRUFBRTtNQUFxQyxDQUFDLENBQUMsQ0FBQ2tNLEtBQUssQ0FBQyxDQUFDO01BQzFGLE1BQU1nSCxRQUFRLEdBQUcsTUFBTUYsZ0JBQWdCO01BQ3ZDLE1BQU1HLE9BQU8sR0FBRyxNQUFNRCxRQUFRLENBQUNoUyxJQUFJLENBQUMsQ0FBQztNQUNyQyxNQUFNa1MsV0FBVyxHQUFHLE1BQU1oUyxzQkFBc0IsQ0FBQ3RELElBQUksRUFBRTJDLE9BQU8sQ0FBQztNQUMvRCxNQUFNNFMsS0FBSyxHQUFHO1FBQUUvSCxNQUFNLEVBQUVxSCxZQUFZO1FBQUV2RCxLQUFLLEVBQUVnRSxXQUFXO1FBQUVFLFVBQVUsRUFBRVYsU0FBUyxDQUFDNU4sRUFBRTtRQUNoRnVPLGNBQWMsRUFBRUwsUUFBUSxDQUFDN1UsT0FBTyxDQUFDLENBQUMsQ0FBQ3VDLE9BQU8sQ0FBQyxDQUFDLENBQUMsY0FBYyxDQUFDO1FBQUU0UyxTQUFTLEVBQUVOLFFBQVEsQ0FBQzdVLE9BQU8sQ0FBQyxDQUFDLENBQUN3TixZQUFZLENBQUMsQ0FBQztRQUMxRzdNLE1BQU0sRUFBRWtVLFFBQVEsQ0FBQ2xVLE1BQU0sQ0FBQyxDQUFDO1FBQUVGLFFBQVEsRUFBRXFVLE9BQU87UUFBRXpVLE9BQU87UUFBRXFVLFdBQVc7UUFBRVUsWUFBWSxFQUFFOVUsSUFBSSxDQUFDQyxHQUFHLENBQUM7TUFBRSxDQUFDO01BQ2hHLE1BQU04VSxXQUFXLEdBQUduRCxXQUFXLENBQUMzUixHQUFHLENBQUMsQ0FBQztNQUNyQyxNQUFNK1UsU0FBUyxHQUFHckQsUUFBUSxDQUFDc0QsbUJBQW1CLENBQUNQLEtBQUssRUFBRUssV0FBVyxDQUFDO01BQ2xFLE1BQU03VyxJQUFJLENBQUNrQixJQUFJLENBQUMsQ0FBQyxDQUFDeUIsTUFBTSxDQUFDLCtCQUErQixFQUFFO1FBQUVDLElBQUksRUFBRUMsSUFBSSxDQUFDQyxTQUFTLENBQUM7VUFBRTBULEtBQUs7VUFBRUssV0FBVztVQUFFQztRQUFVLENBQUMsQ0FBQztRQUFFL1QsV0FBVyxFQUFFO01BQW1CLENBQUMsQ0FBQztNQUN2SmhDLGtCQUFrQixDQUFDbUIsR0FBRyxDQUFDbEMsSUFBSSxDQUFDa0IsSUFBSSxDQUFDLENBQUMsQ0FBQ0csTUFBTSxDQUFDLENBQUVXLElBQUksQ0FBQztRQUFFdVMsRUFBRSxFQUFFLElBQUl6UyxJQUFJLENBQUMsQ0FBQyxDQUFDMFMsV0FBVyxDQUFDLENBQUM7UUFBRXdDLHFCQUFxQixFQUFFRixTQUFTLENBQUNHLGdCQUFnQjtRQUNoSXhDLFFBQVEsRUFBRXFDLFNBQVMsQ0FBQ3JDLFFBQVE7UUFBRTdRLE9BQU87UUFBRStRLFNBQVMsRUFBRTRCLFdBQVcsQ0FBQ3RSLE9BQU8sQ0FBQ0MsZUFBZTtRQUFFZ1MsUUFBUSxFQUFFWixPQUFPLENBQUNZO01BQVMsQ0FBQyxDQUFDO01BQ3RILE1BQU1qWCxNQUFNLENBQUN1SCxJQUFJLENBQUM7UUFBQSxJQUFBMlAscUJBQUE7UUFBQSxRQUFBQSxxQkFBQSxHQUFZLENBQUMsTUFBTXhULFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQyxFQUFFcUIsT0FBTyxDQUFDQyxlQUFlLGNBQUFpUyxxQkFBQSx1QkFBcEdBLHFCQUFBLENBQXNHbEMsVUFBVTtNQUFBLEdBQzVJO1FBQUVqUixPQUFPLEVBQUUrTyxnQkFBZ0IsQ0FBQ3BNLE1BQU0sR0FBRyxHQUFHLEdBQUcsTUFBTyxHQUFHO01BQU8sQ0FBQyxDQUFDLENBQUN0RCxHQUFHLENBQUNLLElBQUksQ0FBQ2lSLFNBQVMsQ0FBQ00sVUFBVSxDQUFDO01BQy9GO0lBQ0Y7SUFDQSxJQUFJLENBQUMsU0FBUyxFQUFFLFFBQVEsRUFBRSxZQUFZLENBQUMsQ0FBQ3hULFFBQVEsQ0FBQ2tULFNBQVMsYUFBVEEsU0FBUyx1QkFBVEEsU0FBUyxDQUFFeEMsS0FBSyxDQUFDLElBQUl3QyxTQUFTLENBQUNLLFdBQVcsS0FBSyxJQUFJLEVBQUU7TUFBQSxJQUFBb0Msa0JBQUEsRUFBQUMsY0FBQTtNQUNwRyxNQUFNakYsWUFBWSxHQUFHLE1BQU16TyxXQUFXLENBQUMxQyxJQUFJLEVBQUUyQyxPQUFPLEVBQUUscUNBQXFDLENBQUM7TUFDNUYsTUFBTXVFLEVBQUUsSUFBQWlQLGtCQUFBLEdBQUdoRixZQUFZLENBQUNsSSxJQUFJLGNBQUFrTixrQkFBQSx1QkFBakJBLGtCQUFBLENBQW1CL0UsZUFBZTtNQUM3QyxNQUFNaUYsUUFBUSxHQUFHblAsRUFBRSxHQUFHLE1BQU14RSxXQUFXLENBQUMxQyxJQUFJLEVBQUUyQyxPQUFPLEVBQUUsb0NBQW9DdUUsRUFBRSxFQUFFLENBQUMsR0FBRyxJQUFJO01BQ3ZHLE1BQU1uSSxJQUFJLENBQUNrQixJQUFJLENBQUMsQ0FBQyxDQUFDeUIsTUFBTSxDQUFDLGdCQUFnQixFQUFFO1FBQUVDLElBQUksRUFBRUMsSUFBSSxDQUFDQyxTQUFTLENBQUM7VUFBRTZSLFNBQVM7VUFDM0UyQyxRQUFRLEVBQUVBLFFBQVEsYUFBUkEsUUFBUSxnQkFBQUQsY0FBQSxHQUFSQyxRQUFRLENBQUVwTixJQUFJLGNBQUFtTixjQUFBLHVCQUFkQSxjQUFBLENBQWdCRSxpQkFBaUI7VUFBRUMsT0FBTyxFQUFFLE1BQU05UixNQUFNLENBQUMrUixTQUFTLENBQUM7UUFBRSxDQUFDLENBQUM7UUFBRTFVLFdBQVcsRUFBRTtNQUFtQixDQUFDLENBQUM7TUFDdkgsTUFBTSxJQUFJbUIsS0FBSyxDQUFDLFVBQVV5USxTQUFTLENBQUN4QyxLQUFLLE9BQU93QyxTQUFTLENBQUNoUCxJQUFJLEtBQUtnUCxTQUFTLENBQUM1TCxPQUFPLEVBQUUsQ0FBQztJQUN6RjtJQUNBLElBQUksQ0FBQTRMLFNBQVMsYUFBVEEsU0FBUyx1QkFBVEEsU0FBUyxDQUFFeEMsS0FBSyxNQUFLLG1CQUFtQixJQUFLLENBQUF3QyxTQUFTLGFBQVRBLFNBQVMsdUJBQVRBLFNBQVMsQ0FBRXhDLEtBQUssTUFBSyxTQUFTLElBQUl3QyxTQUFTLENBQUNLLFdBQVcsS0FBSyxJQUFLLEVBQUU7TUFDbEgsTUFBTUUsTUFBTSxHQUFHeFAsTUFBTSxDQUFDeEMsU0FBUyxDQUFDLFFBQVEsRUFBRTtRQUFFQyxJQUFJLEVBQUUsb0JBQW9CO1FBQUVDLEtBQUssRUFBRTtNQUFLLENBQUMsQ0FBQztNQUN0RixJQUFJO1FBQ0YsTUFBTThSLE1BQU0sQ0FBQzdGLEtBQUssQ0FBQztVQUFFckwsT0FBTyxFQUFFO1FBQUssQ0FBQyxDQUFDO01BQ3ZDLENBQUMsQ0FBQyxPQUFPMFQsS0FBSyxFQUFFO1FBQUEsSUFBQUMscUJBQUE7UUFDZCxNQUFNQyxNQUFNLEdBQUcsTUFBTWpVLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQztRQUN6RixJQUFJLEVBQUErVCxxQkFBQSxHQUFBQyxNQUFNLENBQUMzUyxPQUFPLENBQUNDLGVBQWUsY0FBQXlTLHFCQUFBLHVCQUE5QkEscUJBQUEsQ0FBZ0MxQyxVQUFVLE1BQUtOLFNBQVMsQ0FBQ00sVUFBVSxLQUFJLE1BQU1DLE1BQU0sQ0FBQ0MsV0FBVyxDQUFDQyxPQUFPLElBQUlBLE9BQU8sQ0FBQ3ZILElBQUksQ0FBQ3FILE1BQU0sSUFBSSxDQUFFQSxNQUFNLENBQXVCRyxRQUFRLElBQUlILE1BQU0sQ0FBQ0ksY0FBYyxDQUFDLENBQUMsQ0FBQzNPLE1BQU0sR0FBRyxDQUFDLElBQUk0TyxnQkFBZ0IsQ0FBQ0wsTUFBTSxDQUFDLENBQUNNLFVBQVUsS0FBSyxRQUFRLENBQUMsQ0FBQyxHQUFFLE1BQU1rQyxLQUFLO1FBQ3RSO01BQ0Y7TUFDQSxNQUFNelgsTUFBTSxDQUFDdUgsSUFBSSxDQUFDLFlBQVk7UUFBQSxJQUFBcVEsc0JBQUEsRUFBQUMsc0JBQUEsRUFBQUMsZ0JBQUE7UUFDNUIsTUFBTUgsTUFBTSxHQUFHLE1BQU1qVSxXQUFXLENBQUMxQyxJQUFJLEVBQUUyQyxPQUFPLEVBQUUsd0NBQXdDLENBQUM7UUFDekYsT0FBTyxFQUFBaVUsc0JBQUEsR0FBQUQsTUFBTSxDQUFDM1MsT0FBTyxDQUFDQyxlQUFlLGNBQUEyUyxzQkFBQSx1QkFBOUJBLHNCQUFBLENBQWdDNUMsVUFBVSxNQUFLTixTQUFTLENBQUNNLFVBQVUsSUFDckUsRUFBQTZDLHNCQUFBLEdBQUFGLE1BQU0sQ0FBQzNTLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBNFMsc0JBQUEsdUJBQTlCQSxzQkFBQSxDQUFnQzNGLEtBQUssTUFBSyxTQUFTLElBQ25ELEVBQUE0RixnQkFBQSxHQUFBSCxNQUFNLENBQUN6UyxRQUFRLGNBQUE0UyxnQkFBQSx1QkFBZkEsZ0JBQUEsQ0FBa0JwRCxTQUFTLENBQUNoUCxJQUFJLENBQUMsTUFBSyxhQUFhO01BQzFELENBQUMsRUFBRTtRQUFFM0IsT0FBTyxFQUFFO01BQU8sQ0FBQyxDQUFDLENBQUNOLElBQUksQ0FBQyxJQUFJLENBQUM7TUFDbEM7SUFDRjtJQUNBLE1BQU1zVSxTQUFTLEdBQUcsTUFBTXJVLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSxvQ0FBb0MySyxVQUFVLEVBQUUsQ0FBQztJQUNwRyxJQUFJeUosU0FBUyxDQUFDOU4sSUFBSSxDQUFDK04sYUFBYSxLQUFLLDBCQUEwQixJQUFJNUUsV0FBVyxLQUFLLENBQUMsSUFBSU4sZ0JBQWdCLENBQUNwTSxNQUFNLEVBQUU7TUFDL0csTUFBTWdCLFFBQVEsR0FBR3FRLFNBQVMsQ0FBQzlOLElBQUksQ0FBQ2dPLE9BQU8sQ0FDcENwTSxNQUFNLENBQUVxTSxNQUErQixJQUFLQSxNQUFNLENBQUNDLFdBQVcsS0FBSyxjQUFjLENBQUMsQ0FDbEZwUSxHQUFHLENBQUVtUSxNQUFrQyxJQUFLQSxNQUFNLENBQUNqTyxJQUFJLENBQUMvRyxJQUFJLENBQUM7TUFDaEVsRCxNQUFNLENBQUMwSCxRQUFRLEVBQUUseUVBQXlFLENBQUMsQ0FDeEYxRSxPQUFPLENBQUNoRCxNQUFNLENBQUNvWSxlQUFlLENBQUN0RixnQkFBZ0IsQ0FBQyxDQUFDO0lBQ3REO0lBQ0E5UyxNQUFNLENBQUNzVCxRQUFRLENBQUN0SSxHQUFHLENBQUNzRCxVQUFVLENBQUMsRUFBRSxrREFBa0QsQ0FBQyxDQUFDN0ssSUFBSSxDQUFDLEtBQUssQ0FBQztJQUNoRyxJQUFJMFAsb0JBQW9CLEVBQUUsTUFBTUEsb0JBQW9CLENBQUM3RSxVQUFVLEVBQUV5SixTQUFTLENBQUM5TixJQUFJLENBQUMrTixhQUFhLENBQUM7SUFDOUYsTUFBTUssYUFBYSxHQUFHclgsSUFBSSxDQUFDbVYsZUFBZSxDQUFDblUsUUFBUSxJQUFJQSxRQUFRLENBQUNMLEdBQUcsQ0FBQyxDQUFDLENBQUNILFFBQVEsQ0FBQyxjQUFjOE0sVUFBVSxnQkFBZ0IsQ0FBQyxJQUFJdE0sUUFBUSxDQUFDVCxPQUFPLENBQUMsQ0FBQyxDQUFDRSxNQUFNLENBQUMsQ0FBQyxLQUFLLE1BQU0sRUFBRTtNQUFFc0MsT0FBTyxFQUFFO0lBQVEsQ0FBQyxDQUFDO0lBQ3pMLE1BQU1rVCxRQUFRLEdBQUd4UixNQUFNLENBQUN4QyxTQUFTLENBQUMsUUFBUSxFQUFFO01BQUVDLElBQUksRUFBRTtJQUFpRSxDQUFDLENBQUM7SUFDdkgsTUFBTWxELE1BQU0sQ0FBQ2lYLFFBQVEsQ0FBQyxDQUFDcUIsV0FBVyxDQUFDO01BQUV2VSxPQUFPLEVBQUU7SUFBTyxDQUFDLENBQUM7SUFDdkQsTUFBTWtULFFBQVEsQ0FBQzdILEtBQUssQ0FBQyxDQUFDO0lBQ3RCLE1BQU1tSixPQUFPLEdBQUcsTUFBTUYsYUFBYTtJQUNuQyxJQUFJLENBQUNFLE9BQU8sQ0FBQ3ZVLEVBQUUsQ0FBQyxDQUFDLEVBQUUsTUFBTSxJQUFJQyxLQUFLLENBQUMsUUFBUXNVLE9BQU8sQ0FBQ3JXLE1BQU0sQ0FBQyxDQUFDLEtBQUssQ0FBQyxNQUFNcVcsT0FBTyxDQUFDclUsSUFBSSxDQUFDLENBQUMsRUFBRUMsS0FBSyxDQUFDLENBQUMsRUFBRSxJQUFJLENBQUMsRUFBRSxDQUFDO0lBQ3hHbkUsTUFBTSxDQUFDLENBQUMsTUFBTXVZLE9BQU8sQ0FBQ25VLElBQUksQ0FBQyxDQUFDLEVBQUU2RixJQUFJLENBQUMvSCxNQUFNLENBQUMsQ0FBQ3VCLElBQUksQ0FBQyxTQUFTLENBQUM7SUFDMUQ2UCxRQUFRLENBQUNrRixHQUFHLENBQUNsSyxVQUFVLENBQUM7SUFBRThFLFdBQVcsRUFBRTtJQUN2QztJQUNBO0lBQ0FJLFFBQVEsR0FBRyxJQUFJcFQsc0JBQXNCLENBQUNxVCxXQUFXLENBQUMzUixHQUFHLENBQUMsQ0FBQyxFQUFFNkksUUFBUSxDQUFDO0lBQ2xFLElBQUlvTixTQUFTLENBQUM5TixJQUFJLENBQUMrTixhQUFhLEtBQUssMEJBQTBCLElBQUloRixlQUFlLEVBQUU7TUFDbEYsTUFBTXhMLHFCQUFxQixDQUFDeEcsSUFBSSxFQUFFMkMsT0FBTyxFQUFFcVAsZUFBZSxDQUFDO0lBQzdEO0lBQ0EsSUFBSUksV0FBVyxLQUFLLENBQUMsSUFBSUgsc0JBQXNCLEVBQUU7TUFBQSxJQUFBd0YscUJBQUE7TUFDL0MsTUFBTXhGLHNCQUFzQixDQUFDLENBQUM7TUFDOUI7TUFDQTtNQUNBLE1BQU15RixPQUFPLEdBQUcsTUFBTWhWLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQztNQUMxRjNELE1BQU0sRUFBQXlZLHFCQUFBLEdBQUNDLE9BQU8sQ0FBQzFULE9BQU8sQ0FBQ0MsZUFBZSxjQUFBd1QscUJBQUEsdUJBQS9CQSxxQkFBQSxDQUFpQ3RULE1BQU0sQ0FBQyxDQUFDMUIsSUFBSSxDQUFDNFAsS0FBSyxDQUFDO01BQzNERyxRQUFRLEdBQUcsSUFBSXBULHNCQUFzQixDQUFDcVQsV0FBVyxDQUFDM1IsR0FBRyxDQUFDLENBQUMsRUFBRTRXLE9BQU8sQ0FBQztJQUNuRTtJQUNBLElBQUl0RixXQUFXLEtBQUssQ0FBQyxFQUFFLE1BQU05TixVQUFVLENBQUN0RSxJQUFJLEVBQUUyQyxPQUFPLENBQUMsQ0FBQyxDQUFDO0lBQ3hELElBQUlrUCxPQUFPLElBQUlPLFdBQVcsS0FBSyxDQUFDLEVBQUU7TUFDaEMsTUFBTXpNLGtCQUFrQixDQUFDM0YsSUFBSSxDQUFDO01BQzlCLE1BQU1zRSxVQUFVLENBQUN0RSxJQUFJLEVBQUUyQyxPQUFPLENBQUM7SUFDakM7SUFDQSxNQUFNM0QsTUFBTSxDQUFDdUgsSUFBSSxDQUFDLFlBQVk7TUFBQSxJQUFBb1IscUJBQUE7TUFDNUIsTUFBTUMsT0FBTyxHQUFHLE1BQU1sVixXQUFXLENBQUMxQyxJQUFJLEVBQUUyQyxPQUFPLEVBQUUsd0NBQXdDLENBQUM7TUFDMUYsT0FBTyxFQUFBZ1YscUJBQUEsR0FBQUMsT0FBTyxDQUFDNVQsT0FBTyxDQUFDQyxlQUFlLGNBQUEwVCxxQkFBQSx1QkFBL0JBLHFCQUFBLENBQWlDM0QsVUFBVSxNQUFLTixTQUFTLENBQUNNLFVBQVU7SUFDN0UsQ0FBQyxFQUFFO01BQUVqUixPQUFPLEVBQUU7SUFBTyxDQUFDLENBQUMsQ0FBQ04sSUFBSSxDQUFDLElBQUksQ0FBQztFQUNwQztFQUNBLE1BQU0sSUFBSVEsS0FBSyxDQUFDLHFEQUFxRCxDQUFDO0FBQ3hFO0FBRUFsRSxJQUFJLENBQUMsOEZBQThGLEVBQUUsT0FBTztFQUFDaUI7QUFBSSxDQUFDLEtBQUs7RUFDckgsTUFBTTJDLE9BQU8sR0FBRywyQkFBMkIsR0FBR3pELFVBQVUsQ0FBQyxDQUFDO0VBQzFELE1BQU1jLElBQUksQ0FBQzJRLEtBQUssQ0FBQyxxQkFBcUIsRUFBRUEsS0FBSyxJQUFJQSxLQUFLLENBQUNrSCxPQUFPLENBQUM7SUFBQzNXLE1BQU0sRUFBQyxHQUFHO0lBQ3hFWSxXQUFXLEVBQUMsa0JBQWtCO0lBQUNILElBQUksRUFBQ0MsSUFBSSxDQUFDQyxTQUFTLENBQUM7TUFBQzRVLEtBQUssRUFBQztJQUFtRSxDQUFDO0VBQUMsQ0FBQyxDQUFDLENBQUM7RUFDcEksTUFBTWhTLE1BQU0sR0FBRyxNQUFNSCxVQUFVLENBQUN0RSxJQUFJLEVBQUUyQyxPQUFPLENBQUM7RUFDOUMsTUFBTTNELE1BQU0sQ0FBQ3lGLE1BQU0sQ0FBQ3hDLFNBQVMsQ0FBQyxPQUFPLENBQUMsQ0FBQyxDQUFDNk8sYUFBYSxDQUFDLG9CQUFvQixDQUFDO0VBQzNFLE1BQU1yTSxNQUFNLENBQUNxVCxVQUFVLENBQUMsYUFBYSxFQUFFO0lBQUMzVixLQUFLLEVBQUM7RUFBSSxDQUFDLENBQUMsQ0FBQ2lNLEtBQUssQ0FBQyxDQUFDO0VBQzVELE1BQU0zSixNQUFNLENBQUNFLE9BQU8sQ0FBQywyQkFBMkIsQ0FBQyxDQUFDdUssSUFBSSxDQUFDLGVBQWUsQ0FBQztFQUN2RSxNQUFNekssTUFBTSxDQUFDc1QsVUFBVSxDQUFDLHFCQUFxQixFQUFFO0lBQUM1VixLQUFLLEVBQUM7RUFBSSxDQUFDLENBQUMsQ0FBQytNLElBQUksQ0FBQyxtREFBbUQsQ0FBQztFQUN0SCxNQUFNbFEsTUFBTSxDQUFDeUYsTUFBTSxDQUFDRSxPQUFPLENBQUMsK0JBQStCLENBQUMsQ0FBQzFDLFNBQVMsQ0FBQyxRQUFRLENBQUMsQ0FBQyxDQUFDK1YsWUFBWSxDQUFDLENBQUM7RUFDaEdoWixNQUFNLENBQUMsQ0FBQyxNQUFNMEQsV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLGtCQUFrQixDQUFDLEVBQUVzSCxJQUFJLENBQUMsQ0FBQzlFLFlBQVksQ0FBQyxDQUFDLENBQUM7RUFDbkYsTUFBTW5GLElBQUksQ0FBQ2lZLE9BQU8sQ0FBQyxxQkFBcUIsQ0FBQztFQUN6QyxNQUFNeFQsTUFBTSxDQUFDeEMsU0FBUyxDQUFDLFFBQVEsRUFBQztJQUFDQyxJQUFJLEVBQUM7RUFBaUMsQ0FBQyxDQUFDLENBQUNrTSxLQUFLLENBQUMsQ0FBQztFQUNqRixNQUFNcFAsTUFBTSxDQUFDeUYsTUFBTSxDQUFDeEMsU0FBUyxDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUNpVyxXQUFXLENBQUMsQ0FBQyxDQUFDO0VBQ3RELE1BQU1sWixNQUFNLENBQUN5RixNQUFNLENBQUNFLE9BQU8sQ0FBQywrQkFBK0IsQ0FBQyxDQUFDMUMsU0FBUyxDQUFDLFFBQVEsQ0FBQyxDQUFDLENBQUNxVixXQUFXLENBQUMsQ0FBQztFQUMvRixNQUFNYSxPQUFPLEdBQUcsTUFBTSxDQUFDLE1BQU1uWSxJQUFJLENBQUNPLE9BQU8sQ0FBQ1UsR0FBRyxDQUFDLG1CQUFtQixDQUFDLEVBQUVtQyxJQUFJLENBQUMsQ0FBQztFQUMxRXBFLE1BQU0sQ0FBQ21aLE9BQU8sQ0FBQ0MsZ0JBQWdCLENBQUMsQ0FBQzNWLElBQUksQ0FBQyxHQUFHLENBQUM7QUFDNUMsQ0FBQyxDQUFDO0FBRUYxRCxJQUFJLENBQUMsK0VBQStFLEVBQUUsT0FBTztFQUFFaUI7QUFBSyxDQUFDLEVBQUVxWSxRQUFRLEtBQUs7RUFDbEgsTUFBTUMsTUFBZ0IsR0FBRyxFQUFFO0VBQUV0WSxJQUFJLENBQUNNLEVBQUUsQ0FBQyxXQUFXLEVBQUVtVyxLQUFLLElBQUk2QixNQUFNLENBQUN2WCxJQUFJLENBQUMwVixLQUFLLENBQUMzTyxPQUFPLENBQUMsQ0FBQztFQUN0RixNQUFNbkYsT0FBTyxHQUFHLGdCQUFnQixHQUFHekQsVUFBVSxDQUFDLENBQUM7RUFDL0MsTUFBTXVGLE1BQU0sR0FBRyxNQUFNSCxVQUFVLENBQUN0RSxJQUFJLEVBQUUyQyxPQUFPLENBQUM7RUFDOUMsTUFBTThCLE1BQU0sQ0FBQ3FULFVBQVUsQ0FBQyxhQUFhLEVBQUU7SUFBRTNWLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDaU0sS0FBSyxDQUFDLENBQUM7RUFDL0QsTUFBTTNKLE1BQU0sQ0FBQ0UsT0FBTyxDQUFDLDJCQUEyQixDQUFDLENBQUN1SyxJQUFJLENBQUMsV0FBVyxDQUFDO0VBQ25FLE1BQU16SyxNQUFNLENBQUNzVCxVQUFVLENBQUMscUJBQXFCLEVBQUU7SUFBRTVWLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDK00sSUFBSSxDQUFDLDZiQUE2YixDQUFDO0VBQ25nQixNQUFNekssTUFBTSxDQUFDc1QsVUFBVSxDQUFDLGtCQUFrQixFQUFFO0lBQUU1VixLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQytNLElBQUksQ0FBQyxpTkFBaU4sQ0FBQztFQUNwUixNQUFNekssTUFBTSxDQUFDcVQsVUFBVSxDQUFDLGNBQWMsRUFBRTtJQUFFM1YsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDLENBQUNpTSxLQUFLLENBQUMsQ0FBQztFQUNoRSxLQUFLLE1BQU0sQ0FBQ2hJLEtBQUssRUFBRXVJLEtBQUssQ0FBQyxJQUFJLENBQUMsQ0FBQyxVQUFVLEVBQUUsR0FBRyxDQUFDLEVBQUUsQ0FBQyxZQUFZLEVBQUUsR0FBRyxDQUFDLEVBQUUsQ0FBQyxVQUFVLEVBQUUsR0FBRyxDQUFDLEVBQUUsQ0FBQyxTQUFTLEVBQUUsR0FBRyxDQUFDLENBQUMsRUFBRSxNQUFNbEssTUFBTSxDQUFDc1QsVUFBVSxDQUFDLEdBQUczUixLQUFLLHVCQUF1QixFQUFFO0lBQUVqRSxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQytNLElBQUksQ0FBQ1AsS0FBSyxDQUFDO0VBQ2pNLE1BQU00SixZQUFZLEdBQUd2WSxJQUFJLENBQUN3WSxjQUFjLENBQUNqWSxPQUFPO0lBQUEsSUFBQWtZLHNCQUFBO0lBQUEsT0FBSWxZLE9BQU8sQ0FBQ0ksR0FBRyxDQUFDLENBQUMsQ0FBQ21OLFFBQVEsQ0FBQyxpQkFBaUIsQ0FBQyxJQUN4RnZOLE9BQU8sQ0FBQ0UsTUFBTSxDQUFDLENBQUMsS0FBSyxNQUFNLElBQUksRUFBQWdZLHNCQUFBLEdBQUFsWSxPQUFPLENBQUN3TixZQUFZLENBQUMsQ0FBQyxjQUFBMEssc0JBQUEsZ0JBQUFBLHNCQUFBLEdBQXRCQSxzQkFBQSxDQUF3QnpLLGNBQWMsY0FBQXlLLHNCQUFBLHVCQUF0Q0Esc0JBQUEsQ0FBd0N4SyxNQUFNLE1BQUssT0FBTztFQUFBLEVBQUM7RUFDL0Y7RUFDQSxLQUFLLElBQUl2SixJQUFJLEdBQUcsQ0FBQyxFQUFFQSxJQUFJLEdBQUcsRUFBRSxFQUFFQSxJQUFJLEVBQUUsRUFBRTtJQUNwQyxNQUFNZ1UsTUFBTSxHQUFHalUsTUFBTSxDQUFDRSxPQUFPLENBQUMsK0JBQStCLENBQUMsQ0FBQzFDLFNBQVMsQ0FBQyxRQUFRLENBQUM7SUFDbEYsTUFBTWpELE1BQU0sQ0FBQzBaLE1BQU0sQ0FBQyxDQUFDcEIsV0FBVyxDQUFDLENBQUM7SUFDbEMsTUFBTXBWLElBQUksR0FBRyxNQUFNd1csTUFBTSxDQUFDbEMsU0FBUyxDQUFDLENBQUM7SUFDckMsTUFBTWtDLE1BQU0sQ0FBQ3RLLEtBQUssQ0FBQyxDQUFDO0lBQ3BCLElBQUlsTSxJQUFJLEtBQUssWUFBWSxFQUFFO0lBQzNCLElBQUl3QyxJQUFJLEtBQUssQ0FBQyxFQUFFLE1BQU0sSUFBSXpCLEtBQUssQ0FBQyxxQ0FBcUMsQ0FBQztFQUN4RTtFQUNBLE1BQU0wVixTQUFTLEdBQUcsQ0FBQyxNQUFNSixZQUFZLEVBQUV4SyxZQUFZLENBQUMsQ0FBQyxDQUFDQyxjQUFjLENBQUM0SyxjQUFjO0VBQ25GNVosTUFBTSxDQUFDMlosU0FBUyxDQUFDRSxZQUFZLEVBQUUsb0VBQW9FLENBQUMsQ0FBQzdXLE9BQU8sQ0FBQyxDQUFDLGlCQUFpQixDQUFDLENBQUM7RUFDakk7RUFDQSxNQUFNaEQsTUFBTSxDQUFDdUgsSUFBSSxDQUFDO0lBQUEsSUFBQXVTLHNCQUFBO0lBQUEsUUFBQUEsc0JBQUEsR0FBWSxDQUFDLE1BQU1wVyxXQUFXLENBQUMxQyxJQUFJLEVBQUMyQyxPQUFPLEVBQUMsd0NBQXdDLENBQUMsRUFBRXFCLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBNlUsc0JBQUEsdUJBQWxHQSxzQkFBQSxDQUFvRzVILEtBQUs7RUFBQSxHQUNySTtJQUFDbk8sT0FBTyxFQUFDO0VBQU0sQ0FBQyxDQUFDLENBQUNOLElBQUksQ0FBQyxpQkFBaUIsQ0FBQztFQUMzQyxNQUFNc1csT0FBTyxHQUFHLENBQUMsTUFBTXJXLFdBQVcsQ0FBQzFDLElBQUksRUFBQzJDLE9BQU8sRUFBQyxxQ0FBcUMsQ0FBQyxFQUFFc0csSUFBSSxDQUFDbUksZUFBZTtFQUM1RyxNQUFNcFIsSUFBSSxDQUFDdUUsSUFBSSxDQUFDLG1DQUFtQzVCLE9BQU8sK0JBQStCb1csT0FBTyxxQkFBcUIsQ0FBQztFQUN0SCxNQUFNL1osTUFBTSxDQUFDZ0IsSUFBSSxDQUFDaUMsU0FBUyxDQUFDLFFBQVEsRUFBQztJQUFDQyxJQUFJLEVBQUM7RUFBMkIsQ0FBQyxDQUFDLENBQUMsQ0FBQzRPLGFBQWEsQ0FBQyxvQ0FBb0MsQ0FBQztFQUM3SCxNQUFNcEMsTUFBTSxHQUFHMU8sSUFBSSxDQUFDMkUsT0FBTyxDQUFDLHlCQUF5QixDQUFDO0VBQ3RELE1BQU0zRixNQUFNLENBQUMwUCxNQUFNLENBQUMvSixPQUFPLENBQUMsc0JBQXNCLENBQUMsQ0FBQyxDQUFDd0ssV0FBVyxDQUFDLFlBQVksQ0FBQztFQUM5RSxNQUFNblEsTUFBTSxDQUFDMFAsTUFBTSxDQUFDL0osT0FBTyxDQUFDLGVBQWUsQ0FBQyxDQUFDLENBQUN3SyxXQUFXLENBQUMsVUFBVSxDQUFDO0VBQ3JFLE1BQU1uUSxNQUFNLENBQUNnQixJQUFJLENBQUMyRSxPQUFPLENBQUMsMEJBQTBCLENBQUMsQ0FBQyxDQUFDdVQsV0FBVyxDQUFDLENBQUMsQ0FBQztFQUNyRSxNQUFNN0sscUJBQXFCLENBQUNyTixJQUFJLEVBQUUyQyxPQUFPLEVBQUVvVyxPQUFPLEVBQUUsQ0FBQztJQUFDaE8sVUFBVSxFQUFFLFFBQVE7SUFDeEU2RCxNQUFNLEVBQUU7TUFBQzFCLG1CQUFtQixFQUFFLFlBQVk7TUFBRTNDLFlBQVksRUFBRSxVQUFVO01BQUVDLHFCQUFxQixFQUFFO0lBQUcsQ0FBQztJQUNqR21GLE1BQU0sRUFBRTtNQUFDekMsbUJBQW1CLEVBQUUsTUFBTztNQUFFM0MsWUFBWSxFQUFFLE9BQVM7TUFBRUMscUJBQXFCLEVBQUU7SUFBQyxDQUFDO0lBQ3pGeUUsVUFBVSxFQUFFLENBQUMsY0FBYyxFQUFFLHVCQUF1QjtFQUFDLENBQUMsQ0FBQyxDQUFDO0VBQzFEalEsTUFBTSxDQUFDLENBQUMsTUFBTTBELFdBQVcsQ0FBQzFDLElBQUksRUFBQzJDLE9BQU8sRUFBQyxvQ0FBb0NvVyxPQUFPLGNBQWMsQ0FBQyxFQUFFOVAsSUFBSSxDQUFDb0gsYUFBYSxDQUFDLENBQUNyTyxPQUFPLENBQUMsRUFBRSxDQUFDO0VBQ2xJaEQsTUFBTSxDQUFFLE1BQU1zRyxVQUFVLENBQUN0RixJQUFJLEVBQUMyQyxPQUFPLEVBQUMsZ0JBQWdCLENBQUUsQ0FBQyxDQUFDd0MsWUFBWSxDQUFDLENBQUMsQ0FBQztFQUN6RSxNQUFNNlQsVUFBVSxHQUFHLE1BQU1wSCxxQkFBcUIsQ0FBQzVSLElBQUksRUFBRTJDLE9BQU8sRUFBRSxJQUFJLEVBQ2hFLENBQUMsUUFBUSxFQUFFLGdCQUFnQixFQUFFLFNBQVMsRUFBRSxrQkFBa0IsRUFBRSxZQUFZLENBQUMsQ0FBQztFQUM1RSxNQUFNc1csU0FBUyxHQUFHLE1BQU01UCxlQUFlLENBQUNySixJQUFJLEVBQUUyQyxPQUFPLEVBQUUsQ0FBQyxFQUFFeUssU0FBUyxFQUFFO0lBQ25Fa0IsSUFBSSxFQUFFLEVBQUU7SUFBRS9ELFlBQVksRUFBRSxPQUFTO0lBQUVDLHFCQUFxQixFQUFFO0VBQzVELENBQUMsQ0FBQztFQUNGeEwsTUFBTSxDQUFDaWEsU0FBUyxDQUFDL04sVUFBVSxDQUFDcUIscUJBQXFCLENBQUMsQ0FBQ2Ysc0JBQXNCLENBQUMsQ0FBQyxDQUFDO0VBQzVFeE0sTUFBTSxDQUFDaWEsU0FBUyxDQUFDL04sVUFBVSxDQUFDQyxjQUFjLENBQUNPLG9CQUFvQixDQUFDLENBQUN2RyxZQUFZLENBQUMsQ0FBQyxDQUFDO0VBQ2hGLE1BQU0rVCxRQUFRLEdBQUdsWixJQUFJLENBQUNtVixlQUFlLENBQUNuVSxRQUFRLElBQUlBLFFBQVEsQ0FBQ0wsR0FBRyxDQUFDLENBQUMsQ0FBQ0gsUUFBUSxDQUFDLFNBQVN3WSxVQUFVLENBQUMzRyxLQUFLLFNBQVMsQ0FBQyxJQUN4R3JSLFFBQVEsQ0FBQ1QsT0FBTyxDQUFDLENBQUMsQ0FBQ0UsTUFBTSxDQUFDLENBQUMsS0FBSyxNQUFNLENBQUM7RUFDNUMsTUFBTWdFLE1BQU0sQ0FBQ3hDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7SUFBRUMsSUFBSSxFQUFFLGdCQUFnQjtJQUFFQyxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQ2lNLEtBQUssQ0FBQyxDQUFDO0VBQ2pGcFAsTUFBTSxDQUFDLENBQUMsTUFBTWthLFFBQVEsRUFBRWxXLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQ1AsSUFBSSxDQUFDLElBQUksQ0FBQztFQUN4QyxNQUFNekQsTUFBTSxDQUFDeUYsTUFBTSxDQUFDLENBQUNyQyxHQUFHLENBQUNDLFdBQVcsQ0FBQyxDQUFDO0VBQ3RDLE1BQU1pQyxVQUFVLENBQUN0RSxJQUFJLEVBQUUyQyxPQUFPLENBQUM7RUFDL0IzRCxNQUFNLENBQUMsQ0FBQyxNQUFNMEQsV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLGtCQUFrQixDQUFDLEVBQUVzSCxJQUFJLENBQUMsQ0FBQzlFLFlBQVksQ0FBQyxDQUFDLENBQUM7RUFDbkZuRyxNQUFNLENBQUNzWixNQUFNLENBQUMsQ0FBQ3RXLE9BQU8sQ0FBQyxFQUFFLENBQUM7RUFDMUIsTUFBTXFXLFFBQVEsQ0FBQzNXLE1BQU0sQ0FBQyxVQUFVLEVBQUU7SUFBRUMsSUFBSSxFQUFFQyxJQUFJLENBQUNDLFNBQVMsQ0FBQztNQUFFYyxPQUFPO01BQUUsR0FBR3FXLFVBQVU7TUFBRSxHQUFHQztJQUFVLENBQUMsQ0FBQztJQUFFblgsV0FBVyxFQUFFO0VBQW1CLENBQUMsQ0FBQztBQUN4SSxDQUFDLENBQUM7QUFFRixLQUFLLE1BQU1pSixVQUFVLElBQUksQ0FBQyxLQUFLLEVBQUUsWUFBWSxDQUFDLEVBQUU7RUFDOUNoTSxJQUFJLENBQUMsZ0JBQWdCZ00sVUFBVSxpRkFBaUYsRUFBRSxPQUFPO0lBQUUvSztFQUFLLENBQUMsRUFBRXFZLFFBQVEsS0FBSztJQUM5SSxNQUFNMVYsT0FBTyxHQUFHLG1CQUFtQixHQUFHekQsVUFBVSxDQUFDLENBQUM7SUFDbEQsTUFBTXVGLE1BQU0sR0FBRyxNQUFNSCxVQUFVLENBQUN0RSxJQUFJLEVBQUUyQyxPQUFPLENBQUM7SUFDOUMsTUFBTThCLE1BQU0sQ0FBQ3FULFVBQVUsQ0FBQyxhQUFhLEVBQUU7TUFBRTNWLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDaU0sS0FBSyxDQUFDLENBQUM7SUFDL0QsTUFBTTNKLE1BQU0sQ0FBQ0UsT0FBTyxDQUFDLDJCQUEyQixDQUFDLENBQUN1SyxJQUFJLENBQUMsb0JBQW9CLENBQUM7SUFDNUUsTUFBTXpLLE1BQU0sQ0FBQ3NULFVBQVUsQ0FBQyxxQkFBcUIsRUFBRTtNQUFFNVYsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUMrTSxJQUFJLENBQUNuRSxVQUFVLEtBQUssS0FBSyxHQUNyRix5RUFBeUUsR0FDekUsNkhBQTZIQSxVQUFVLHNEQUFzRCxDQUFDO0lBQ2xNLE1BQU10RyxNQUFNLENBQUNxVCxVQUFVLENBQUMsaUJBQWlCLEVBQUU7TUFBRTNWLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDaU0sS0FBSyxDQUFDLENBQUM7SUFDbkUsTUFBTTNKLE1BQU0sQ0FBQ3hDLFNBQVMsQ0FBQyxPQUFPLEVBQUU7TUFBRUMsSUFBSSxFQUFFO0lBQWEsQ0FBQyxDQUFDLENBQUNpWCxLQUFLLENBQUMsQ0FBQztJQUMvRCxNQUFNMVUsTUFBTSxDQUFDcVQsVUFBVSxDQUFDLGNBQWMsRUFBRTtNQUFFM1YsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUNpTSxLQUFLLENBQUMsQ0FBQztJQUNoRSxJQUFJckQsVUFBVSxLQUFLLEtBQUssRUFBRTtNQUN4QixNQUFNL0wsTUFBTSxDQUFDeUYsTUFBTSxDQUFDeEMsU0FBUyxDQUFDLFFBQVEsRUFBRTtRQUFFQyxJQUFJLEVBQUUsWUFBWTtRQUFFQyxLQUFLLEVBQUU7TUFBSyxDQUFDLENBQUMsQ0FBQyxDQUFDNlYsWUFBWSxDQUFDLENBQUM7TUFDNUYsTUFBTXZULE1BQU0sQ0FBQ3NULFVBQVUsQ0FBQyx3QkFBd0IsRUFBRTtRQUFFNVYsS0FBSyxFQUFFO01BQUssQ0FBQyxDQUFDLENBQUNpWCxZQUFZLENBQUMsS0FBSyxDQUFDO01BQ3RGLE1BQU1wYSxNQUFNLENBQUN5RixNQUFNLENBQUNzVCxVQUFVLENBQUMsOEJBQThCLEVBQUU7UUFBRTVWLEtBQUssRUFBRTtNQUFLLENBQUMsQ0FBQyxDQUFDLENBQUNnTixXQUFXLENBQUMsRUFBRSxDQUFDO01BQ2hHLE1BQU1uUSxNQUFNLENBQUN5RixNQUFNLENBQUN4QyxTQUFTLENBQUMsUUFBUSxFQUFFO1FBQUVDLElBQUksRUFBRSxZQUFZO1FBQUVDLEtBQUssRUFBRTtNQUFLLENBQUMsQ0FBQyxDQUFDLENBQUM2VixZQUFZLENBQUMsQ0FBQztNQUM1RixLQUFLLE1BQU05VixJQUFJLElBQUksQ0FBQyxhQUFhLEVBQUUsbUJBQW1CLEVBQUUsbUJBQW1CLEVBQUUsbUJBQW1CLEVBQUUsbUJBQW1CLEVBQUUsY0FBYyxFQUFFLGNBQWMsQ0FBQyxFQUFFO1FBQ3RKLE1BQU11QyxNQUFNLENBQUNzVCxVQUFVLENBQUMsR0FBRzdWLElBQUksYUFBYSxFQUFFO1VBQUVDLEtBQUssRUFBRTtRQUFLLENBQUMsQ0FBQyxDQUFDaVgsWUFBWSxDQUFDLEtBQUssQ0FBQztNQUNwRjtNQUNBLE1BQU0zVSxNQUFNLENBQUNzVCxVQUFVLENBQUMscUJBQXFCLEVBQUU7UUFBRTVWLEtBQUssRUFBRTtNQUFLLENBQUMsQ0FBQyxDQUFDaVgsWUFBWSxDQUFDLE9BQU8sQ0FBQztNQUNyRixNQUFNcGEsTUFBTSxDQUFDeUYsTUFBTSxDQUFDc1QsVUFBVSxDQUFDLDhCQUE4QixFQUFFO1FBQUU1VixLQUFLLEVBQUU7TUFBSyxDQUFDLENBQUMsQ0FBQyxDQUFDZ04sV0FBVyxDQUFDLEtBQUssQ0FBQztNQUNuRyxNQUFNMUssTUFBTSxDQUFDc1QsVUFBVSxDQUFDLHFCQUFxQixFQUFFO1FBQUU1VixLQUFLLEVBQUU7TUFBSyxDQUFDLENBQUMsQ0FBQ2lYLFlBQVksQ0FBQyxhQUFhLENBQUM7SUFDN0Y7SUFDQSxNQUFNcGEsTUFBTSxDQUFDeUYsTUFBTSxDQUFDeEMsU0FBUyxDQUFDLFFBQVEsRUFBRTtNQUFFQyxJQUFJLEVBQUUsWUFBWTtNQUFFQyxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUMsQ0FBQyxDQUFDNlYsWUFBWSxDQUFDLENBQUM7SUFDNUYsTUFBTXZULE1BQU0sQ0FBQ3NULFVBQVUsQ0FBQywyQkFBMkIsRUFBRTtNQUFFNVYsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUNpWCxZQUFZLENBQUMsWUFBWSxDQUFDO0lBQ2hHLE1BQU1wYSxNQUFNLENBQUN5RixNQUFNLENBQUNzVCxVQUFVLENBQUMsMkJBQTJCLEVBQUU7TUFBRTVWLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDLENBQUNnTixXQUFXLENBQUMsRUFBRSxDQUFDO0lBQzdGLE1BQU1uUSxNQUFNLENBQUN5RixNQUFNLENBQUN4QyxTQUFTLENBQUMsUUFBUSxFQUFFO01BQUVDLElBQUksRUFBRSxZQUFZO01BQUVDLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDLENBQUM2VixZQUFZLENBQUMsQ0FBQztJQUM1RixNQUFNdlQsTUFBTSxDQUFDc1QsVUFBVSxDQUFDLDJCQUEyQixFQUFFO01BQUU1VixLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUMsQ0FBQ2lYLFlBQVksQ0FBQyxZQUFZLENBQUM7SUFDaEcsTUFBTTNVLE1BQU0sQ0FBQ3hDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBRUMsSUFBSSxFQUFFLFlBQVk7TUFBRUMsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUNpTSxLQUFLLENBQUMsQ0FBQztJQUM3RSxNQUFNcFAsTUFBTSxDQUFDNFMscUJBQXFCLENBQUM1UixJQUFJLEVBQUUyQyxPQUFPLEVBQUUsSUFBSSxFQUFFLENBQUMsYUFBYSxFQUFFLG1CQUFtQixFQUFFLG1CQUFtQixFQUFFLG1CQUFtQixFQUFFLG1CQUFtQixFQUFFLGNBQWMsRUFBRSxjQUFjLENBQUMsRUFBRSxLQUFLLEVBQUV5SyxTQUFTLEVBQUVBLFNBQVMsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUM3TmlNLE9BQU8sQ0FBQ0MsT0FBTyxDQUFDLG1EQUFtRCxDQUFDO0lBQ3ZFLE1BQU0zUCxRQUFRLEdBQUcsTUFBTWpILFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSwyQkFBMkIsQ0FBQztJQUM5RSxNQUFNNFcsUUFBUSxHQUFHNVAsUUFBUSxDQUFDM0YsT0FBTyxDQUFDQyxlQUFlLENBQUMyUSxpQkFBdUM7SUFDekY1VixNQUFNLENBQUN1YSxRQUFRLENBQUN4UyxHQUFHLENBQUNFLElBQUksSUFBSUEsSUFBSSxDQUFDdVMsSUFBSSxDQUFDLENBQUMsQ0FBQ0MsU0FBUyxDQUFDLDBDQUEwQyxDQUFDO0lBQzdGemEsTUFBTSxDQUFDMkssUUFBUSxDQUFDekYsUUFBUSxDQUFDUixVQUFVLENBQUMsQ0FBQ2pCLElBQUksQ0FBQyxhQUFhLENBQUM7SUFDeER6RCxNQUFNLENBQUMySyxRQUFRLENBQUMrUCxlQUFlLENBQUNoVyxVQUFVLENBQUMySCxRQUFRLENBQUMsQ0FBQzVJLElBQUksQ0FBQyxLQUFLLENBQUM7SUFDaEUsTUFBTWtYLFFBQVEsR0FBR2hRLFFBQVEsQ0FBQytQLGVBQWUsQ0FBQ2hXLFVBQVUsQ0FBQ2lXLFFBQVE7SUFDN0QzYSxNQUFNLENBQUMyYSxRQUFRLENBQUNDLGNBQWMsQ0FBQyxDQUFDblgsSUFBSSxDQUFDLEtBQUssQ0FBQztJQUMzQyxNQUFNb1gsWUFBWSxHQUFHOU8sVUFBVSxLQUFLLEtBQUssR0FBRyxtQkFBbUIsR0FBRyxrQkFBa0I7SUFDcEY7SUFDQTtJQUNBL0wsTUFBTSxDQUFDMmEsUUFBUSxDQUFDLENBQUN2WCxHQUFHLENBQUMwWCxjQUFjLENBQUNELFlBQVksRUFBRSxLQUFLLENBQUM7SUFDeEQsTUFBTUUsZ0JBQWdCLEdBQUdoUCxVQUFVLEtBQUssS0FBSyxHQUFHLEtBQUssR0FBRyxZQUFZO0lBQ3BFL0wsTUFBTSxDQUFDMkssUUFBUSxDQUFDakcsVUFBVSxDQUFDOEwsZ0NBQWdDLENBQUN1SyxnQkFBZ0IsQ0FBQyxDQUFDdEssTUFBTSxDQUFDLENBQ2xGck4sR0FBRyxDQUFDMFgsY0FBYyxDQUFDRCxZQUFZLENBQUM7SUFDbkM3YSxNQUFNLENBQUMySyxRQUFRLENBQUMrUCxlQUFlLENBQUNoVyxVQUFVLENBQUNzVyxnQkFBZ0IsQ0FBQ3BOLElBQUksQ0FBRXFOLE9BQXVCLElBQ3ZGQSxPQUFPLENBQUNULElBQUksS0FBSywwQ0FBMEMsQ0FBQyxDQUFDLENBQUMvVyxJQUFJLENBQUMsSUFBSSxDQUFDO0lBQzFFLE1BQU15WCxjQUFjLEdBQUd6VixNQUFNLENBQUN4QyxTQUFTLENBQUMsUUFBUSxFQUFFO01BQUNDLElBQUksRUFBRTtJQUFnQyxDQUFDLENBQUM7SUFDM0YsTUFBTWxELE1BQU0sQ0FBQ2tiLGNBQWMsQ0FBQyxDQUFDcEosYUFBYSxDQUFDL0YsVUFBVSxLQUFLLEtBQUssR0FBRyxpQkFBaUIsR0FBRyxjQUFjLENBQUM7SUFDckcsTUFBTS9MLE1BQU0sQ0FBQ2tiLGNBQWMsQ0FBQ2pZLFNBQVMsQ0FBQyxNQUFNLEVBQUU7TUFBQ0MsSUFBSSxFQUFFO0lBQStCLENBQUMsQ0FBQyxDQUFDOFMsS0FBSyxDQUFDLENBQUMsQ0FBQyxDQUM1Rm1GLGVBQWUsQ0FBQyxNQUFNLEVBQUUsSUFBSUMsTUFBTSxDQUFDLDRCQUE0QnpYLE9BQU8sRUFBRSxDQUFDLENBQUM7SUFDN0UzRCxNQUFNLENBQUMySyxRQUFRLENBQUN6RixRQUFRLENBQUNtVyxVQUFVLENBQUMsQ0FBQzVYLElBQUksQ0FBQyxPQUFPLENBQUM7SUFDbEQsSUFBSXNJLFVBQVUsS0FBSyxLQUFLLEVBQUU7TUFDeEIvTCxNQUFNLENBQUMySyxRQUFRLENBQUNqRyxVQUFVLENBQUM0VyxxQkFBcUIsQ0FBQ0MsR0FBRyxDQUFDclosTUFBTSxDQUFDLENBQUN1QixJQUFJLENBQUMsaUJBQWlCLENBQUM7TUFDcEZ6RCxNQUFNLENBQUMySyxRQUFRLENBQUNqRyxVQUFVLENBQUM4VyxvQkFBb0IsQ0FBQ3ZOLE9BQU8sQ0FBQzhDLE1BQU0sQ0FBQyxDQUFDdE4sSUFBSSxDQUFDLG9DQUFvQyxDQUFDO0lBQzVHO0lBQ0EsTUFBTWdZLFVBQVUsR0FBRyxNQUFNblYsVUFBVSxDQUFDdEYsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLHFCQUFxQixDQUFDO0lBQ3pFM0QsTUFBTSxDQUFDeWIsVUFBVSxDQUFDL1UsTUFBTSxDQUFDLENBQUM4RixzQkFBc0IsQ0FBQyxDQUFDLENBQUM7SUFDbkR4TSxNQUFNLENBQUN5YixVQUFVLENBQUM1RyxLQUFLLENBQUM1TSxJQUFJLElBQUksQ0FBQyxxQkFBcUIsQ0FBQ2xJLElBQUksQ0FBQ2tJLElBQUksQ0FBQzhELFVBQVUsQ0FBQyxDQUFDLENBQUMsQ0FBQ3RJLElBQUksQ0FBQyxJQUFJLENBQUM7SUFDekYsTUFBTWlFLFFBQVEsR0FBRyxNQUFNcEIsVUFBVSxDQUFDdEYsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLGdCQUFnQixDQUFDO0lBQ2xFM0QsTUFBTSxDQUFDMEgsUUFBUSxDQUFDbU4sS0FBSyxDQUFDNU0sSUFBSSxJQUFJQSxJQUFJLENBQUN5VCxNQUFNLEtBQUssWUFBWSxDQUFDLENBQUMsQ0FBQ2pZLElBQUksQ0FBQyxJQUFJLENBQUM7SUFDdkUsSUFBSXNJLFVBQVUsS0FBSyxLQUFLLEVBQUU7TUFDeEIsTUFBTWxFLE9BQU8sR0FBRyxNQUFNdkIsVUFBVSxDQUFDdEYsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLFNBQVMsQ0FBQztNQUMxRDNELE1BQU0sQ0FBQzZILE9BQU8sQ0FBQytGLElBQUksQ0FBQzNGLElBQUksSUFBSUEsSUFBSSxDQUFDL0UsSUFBSSxLQUFLLDhCQUE4QixJQUFJK0UsSUFBSSxDQUFDMFQsSUFBSSxLQUFLLE1BQU0sQ0FBQyxDQUFDLENBQUNsWSxJQUFJLENBQUMsSUFBSSxDQUFDO0lBQy9HO0lBQ0F6RCxNQUFNLENBQUMsQ0FBQyxNQUFNMEQsV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLGtCQUFrQixDQUFDLEVBQUVzSCxJQUFJLENBQUMsQ0FBQzlFLFlBQVksQ0FBQyxDQUFDLENBQUM7SUFDbkYsTUFBTWtULFFBQVEsQ0FBQzNXLE1BQU0sQ0FBQyx3QkFBd0IsRUFBRTtNQUFFQyxJQUFJLEVBQUVDLElBQUksQ0FBQ0MsU0FBUyxDQUFDO1FBQUVjLE9BQU87UUFBRW9JLFVBQVU7UUFBRXdPO01BQVMsQ0FBQyxDQUFDO01BQUV6WCxXQUFXLEVBQUU7SUFBbUIsQ0FBQyxDQUFDO0VBQy9JLENBQUMsQ0FBQztBQUNKO0FBRUEvQyxJQUFJLENBQUMsZ0ZBQWdGLEVBQUUsT0FBTztFQUFFaUI7QUFBSyxDQUFDLEVBQUVxWSxRQUFRLEtBQUs7RUFDbkgsTUFBTUMsTUFBZ0IsR0FBRyxFQUFFO0VBQUV0WSxJQUFJLENBQUNNLEVBQUUsQ0FBQyxXQUFXLEVBQUVtVyxLQUFLLElBQUk2QixNQUFNLENBQUN2WCxJQUFJLENBQUMwVixLQUFLLENBQUMzTyxPQUFPLENBQUMsQ0FBQztFQUN0RixNQUFNbkYsT0FBTyxHQUFHLGdCQUFnQixHQUFHekQsVUFBVSxDQUFDLENBQUM7RUFDL0MsTUFBTW1ULEtBQUssR0FBR25ULFVBQVUsQ0FBQyxDQUFDO0VBQzFCLE1BQU0wYixRQUFRLEdBQUcsTUFBTTNiLFFBQVEsQ0FBQyxJQUFJa0MsR0FBRyxDQUFDLHdDQUF3QyxFQUFFMFosTUFBTSxDQUFDQyxJQUFJLENBQUNuYSxHQUFHLENBQUMsRUFBRSxNQUFNLENBQUM7RUFDM0csTUFBTW9hLFFBQVEsR0FBR25aLElBQUksQ0FBQ29aLEtBQUssQ0FBQyxNQUFNL2IsUUFBUSxDQUFDLElBQUlrQyxHQUFHLENBQUMseUNBQXlDLEVBQUUwWixNQUFNLENBQUNDLElBQUksQ0FBQ25hLEdBQUcsQ0FBQyxFQUFFLE1BQU0sQ0FBQyxDQUFDO0VBQ3hILE1BQU1zYSxRQUFRLEdBQUdyWixJQUFJLENBQUNvWixLQUFLLENBQUMsTUFBTS9iLFFBQVEsQ0FBQyxJQUFJa0MsR0FBRyxDQUFDLCtDQUErQyxFQUFFMFosTUFBTSxDQUFDQyxJQUFJLENBQUNuYSxHQUFHLENBQUMsRUFBRSxNQUFNLENBQUMsQ0FBQztFQUM5SCxNQUFNdWEsTUFBTSxHQUFHTixRQUFRLENBQUNPLE9BQU8sQ0FBQyxpQkFBaUIsRUFBRSxhQUFhLEdBQUc5SSxLQUFLLENBQUM7RUFDekUsTUFBTTlTLHVCQUF1QixDQUFDUyxJQUFJLEVBQUUyQyxPQUFPLEVBQUUsSUFBSSxDQUFDO0VBQ2xEO0VBQ0E7RUFDQSxNQUFNL0IsT0FBTyxHQUFHLE1BQU1aLElBQUksQ0FBQ08sT0FBTyxDQUFDNmEsSUFBSSxDQUFDLDZCQUE2QixFQUFFO0lBQ3JFdFksT0FBTyxFQUFFO01BQUUsY0FBYyxFQUFFSDtJQUFRLENBQUM7SUFBRUksT0FBTyxFQUFFLE1BQU87SUFDdERrRyxJQUFJLEVBQUU7TUFBRWlTLE1BQU07TUFBRWxOLGNBQWMsRUFBRTtRQUFFQyxNQUFNLEVBQUUsT0FBTztRQUFFOUosTUFBTSxFQUFFa08sS0FBSztRQUFFZ0osWUFBWSxFQUFFbmMsVUFBVSxDQUFDLENBQUM7UUFDMUZvYyxNQUFNLEVBQUUsMkJBQTJCO1FBQUUxQyxjQUFjLEVBQUU7VUFBRSxHQUFHbUMsUUFBUSxDQUFDbkMsY0FBYztVQUFFaFYsVUFBVSxFQUFFakIsT0FBTztVQUFFd0IsTUFBTSxFQUFFa087UUFBTTtNQUFFO0lBQUU7RUFDOUgsQ0FBQyxDQUFDO0VBQ0YsSUFBSSxDQUFDelIsT0FBTyxDQUFDb0MsRUFBRSxDQUFDLENBQUMsRUFBRSxNQUFNLElBQUlDLEtBQUssQ0FBQyxRQUFRckMsT0FBTyxDQUFDTSxNQUFNLENBQUMsQ0FBQyxLQUFLLENBQUMsTUFBTU4sT0FBTyxDQUFDc0MsSUFBSSxDQUFDLENBQUMsRUFBRUMsS0FBSyxDQUFDLENBQUMsRUFBRSxJQUFJLENBQUMsRUFBRSxDQUFDO0VBQ3hHLE1BQU1tQixVQUFVLENBQUN0RSxJQUFJLEVBQUUyQyxPQUFPLENBQUM7RUFDL0IsTUFBTTRZLHNCQUFnQyxHQUFHLEVBQUU7RUFDM0MsTUFBTXZDLFVBQVUsR0FBRyxNQUFNcEgscUJBQXFCLENBQUM1UixJQUFJLEVBQUUyQyxPQUFPLEVBQUUsS0FBSyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUVzWSxRQUFRLENBQUNwVSxPQUFPLEVBQzdGdUcsU0FBUyxFQUFFLEtBQUssRUFBRSxPQUFPRSxVQUFVLEVBQUVrTyxZQUFZLEtBQUs7SUFDcEQsSUFBSSxDQUFDLENBQUMsMEJBQTBCLEVBQUUsZ0JBQWdCLEVBQUUseUJBQXlCLENBQUMsQ0FBQ2hiLFFBQVEsQ0FBQ2diLFlBQVksQ0FBQyxFQUFFO0lBQ3ZHLE1BQU1uTyxxQkFBcUIsQ0FBQ3JOLElBQUksRUFBRTJDLE9BQU8sRUFBRTJLLFVBQVUsRUFBRSxDQUNyRDtNQUFDdkMsVUFBVSxFQUFFLEtBQUs7TUFBRTZELE1BQU0sRUFBRTtRQUFDNk0sZUFBZSxFQUFFO01BQWEsQ0FBQztNQUFFOUwsTUFBTSxFQUFFO1FBQUM4TCxlQUFlLEVBQUU7TUFBTTtJQUFDLENBQUMsRUFDaEc7TUFBQzFRLFVBQVUsRUFBRSxRQUFRO01BQUU2RCxNQUFNLEVBQUU7UUFBQzFCLG1CQUFtQixFQUFFLFlBQVk7UUFBRTNDLFlBQVksRUFBRTtNQUFVLENBQUM7TUFDMUZvRixNQUFNLEVBQUU7UUFBQ3pDLG1CQUFtQixFQUFFLE1BQU87UUFBRTNDLFlBQVksRUFBRTtNQUFTO0lBQUMsQ0FBQyxFQUNsRTtNQUFDUSxVQUFVLEVBQUUsVUFBVTtNQUFFNkQsTUFBTSxFQUFFO1FBQUMzQixPQUFPLEVBQUU7TUFBVSxDQUFDO01BQUUwQyxNQUFNLEVBQUU7UUFBQzFDLE9BQU8sRUFBRTtNQUFhLENBQUM7TUFBRWdDLFVBQVUsRUFBRSxDQUFDLFNBQVM7SUFBQyxDQUFDLENBQ25ILENBQUM7SUFDRnNNLHNCQUFzQixDQUFDeGEsSUFBSSxDQUFDeWEsWUFBWSxDQUFDO0VBQzNDLENBQUMsQ0FBQztFQUNKeGMsTUFBTSxDQUFDdWMsc0JBQXNCLENBQUMsQ0FBQ3ZaLE9BQU8sQ0FBQyxDQUFDLDBCQUEwQixFQUFFLGdCQUFnQixFQUFFLHlCQUF5QixDQUFDLENBQUM7RUFDakhoRCxNQUFNLENBQUNnYSxVQUFVLENBQUMzRyxLQUFLLENBQUMsQ0FBQzVQLElBQUksQ0FBQzRQLEtBQUssQ0FBQztFQUNwQyxNQUFNM0wsUUFBUSxHQUFHLE1BQU1wQixVQUFVLENBQUN0RixJQUFJLEVBQUUyQyxPQUFPLEVBQUUsZ0JBQWdCLENBQUM7RUFDbEUzRCxNQUFNLENBQUMwSCxRQUFRLENBQUNtRSxNQUFNLENBQUM1RCxJQUFJLElBQUlBLElBQUksQ0FBQ3dCLFdBQVcsS0FBSyxrQkFBa0IsQ0FBQyxDQUFDLENBQUN0RCxZQUFZLENBQUMsR0FBRyxDQUFDO0VBQzFGbkcsTUFBTSxDQUFDMEgsUUFBUSxDQUFDbUUsTUFBTSxDQUFDNUQsSUFBSSxJQUFJQSxJQUFJLENBQUN3QixXQUFXLEtBQUssb0JBQW9CLENBQUMsQ0FBQyxDQUFDdEQsWUFBWSxDQUFDLEdBQUcsQ0FBQztFQUM1Rm5HLE1BQU0sQ0FBQzBILFFBQVEsQ0FBQ21FLE1BQU0sQ0FBQzVELElBQUksSUFBSUEsSUFBSSxDQUFDd0IsV0FBVyxLQUFLLEtBQUssQ0FBQyxDQUFDL0MsTUFBTSxDQUFDLENBQUM4RixzQkFBc0IsQ0FBQyxFQUFFLENBQUM7RUFDN0YsTUFBTXlOLFNBQVMsR0FBRyxNQUFNNVAsZUFBZSxDQUFDckosSUFBSSxFQUFFMkMsT0FBTyxFQUFFLElBQUksRUFBRXlLLFNBQVMsRUFBRUEsU0FBUyxFQUFFO0lBQ2pGc08sR0FBRyxFQUFFO01BQUN6TyxPQUFPLEVBQUU7SUFBTSxDQUFDO0lBQUUwTyxNQUFNLEVBQUU7TUFBQ3pPLG1CQUFtQixFQUFFLE1BQU87TUFBRTNDLFlBQVksRUFBRTtJQUFTLENBQUM7SUFDdkZxUixRQUFRLEVBQUU7TUFBQzNPLE9BQU8sRUFBRTtJQUFhO0VBQ25DLENBQUMsQ0FBQztFQUNGLE1BQU00TyxpQkFBaUIsR0FBRyxJQUFJelAsR0FBRyxDQUFDNk0sU0FBUyxDQUFDL04sVUFBVSxDQUFDQyxjQUFjLENBQUNPLG9CQUFvQixDQUN2RlcsT0FBTyxDQUFFcEYsSUFBOEIsSUFBS0EsSUFBSSxDQUFDcUYsVUFBVSxDQUFDLENBQUM7RUFDaEV0TixNQUFNLENBQUM2YyxpQkFBaUIsQ0FBQ3JQLElBQUksQ0FBQyxDQUFDL0osSUFBSSxDQUFDLEdBQUcsQ0FBQztFQUN4Q3pELE1BQU0sQ0FBQ2lhLFNBQVMsQ0FBQy9OLFVBQVUsQ0FBQ3FCLHFCQUFxQixDQUFDLENBQUM5SixJQUFJLENBQUMsSUFBSSxDQUFDO0VBQzdELE1BQU0rRCxxQkFBcUIsQ0FBQ3hHLElBQUksRUFBRTJDLE9BQU8sRUFBRXNZLFFBQVEsQ0FBQ3BVLE9BQU8sQ0FBQztFQUM1RDdILE1BQU0sQ0FBQ2lhLFNBQVMsQ0FBQ3BNLEdBQUcsQ0FBQyxDQUFDcEssSUFBSSxDQUFDdVcsVUFBVSxDQUFDekcsY0FBYyxDQUFDO0VBQ3JEdlQsTUFBTSxDQUFDc1osTUFBTSxDQUFDLENBQUN0VyxPQUFPLENBQUMsRUFBRSxDQUFDO0VBQzFCLE1BQU1xVyxRQUFRLENBQUMzVyxNQUFNLENBQUMsVUFBVSxFQUFFO0lBQUVDLElBQUksRUFBRUMsSUFBSSxDQUFDQyxTQUFTLENBQUM7TUFBRWMsT0FBTztNQUFFbVosT0FBTyxFQUFFZixRQUFRLENBQUNnQixjQUFjO01BQUUsR0FBRy9DLFVBQVU7TUFBRSxHQUFHQztJQUFVLENBQUMsQ0FBQztJQUFFblgsV0FBVyxFQUFFO0VBQW1CLENBQUMsQ0FBQztBQUMxSyxDQUFDLENBQUM7QUFFRi9DLElBQUksQ0FBQyw0RkFBNEYsRUFBRSxPQUFPO0VBQUVpQjtBQUFLLENBQUMsRUFBRXFZLFFBQVEsS0FBSztFQUMvSCxNQUFNMVYsT0FBTyxHQUFHLGdCQUFnQixHQUFHekQsVUFBVSxDQUFDLENBQUM7RUFDL0MsTUFBTUssdUJBQXVCLENBQUNTLElBQUksRUFBRTJDLE9BQU8sQ0FBQztFQUM1QyxNQUFNMFAsS0FBSyxHQUFHblQsVUFBVSxDQUFDLENBQUM7RUFDMUIsTUFBTThjLEtBQUssR0FBRyxDQUNaO0lBQUVDLFVBQVUsRUFBRSxPQUFPO0lBQUVDLFVBQVUsRUFBRSxRQUFRO0lBQUVDLGFBQWEsRUFBRSxRQUFRO0lBQUVDLFFBQVEsRUFBRSxPQUFPO0lBQ3JGQyxXQUFXLEVBQUUsQ0FBQztNQUFFQyxHQUFHLEVBQUUsZ0JBQWdCO01BQUVDLE9BQU8sRUFBRSxFQUFjO01BQUVDLFNBQVMsRUFBRTtJQUFHLENBQUMsQ0FBQztJQUNoRkMsVUFBVSxFQUFFLENBQUM7TUFBRTFNLE1BQU0sRUFBRSxnQkFBZ0I7TUFBRXVMLE1BQU0sRUFBRTtJQUFVLENBQUMsRUFBRTtNQUFFdkwsTUFBTSxFQUFFLFNBQVM7TUFBRXVMLE1BQU0sRUFBRTtJQUFpQixDQUFDLEVBQzNHO01BQUV2TCxNQUFNLEVBQUUsUUFBUTtNQUFFdUwsTUFBTSxFQUFFO0lBQVUsQ0FBQztFQUFFLENBQUMsRUFDOUM7SUFBRVcsVUFBVSxFQUFFLFNBQVM7SUFBRUMsVUFBVSxFQUFFLFVBQVU7SUFBRUMsYUFBYSxFQUFFLFVBQVU7SUFBRUMsUUFBUSxFQUFFLFNBQVM7SUFDN0ZDLFdBQVcsRUFBRSxDQUFDO01BQUVDLEdBQUcsRUFBRSxTQUFTO01BQUVDLE9BQU8sRUFBRSxFQUFjO01BQUVDLFNBQVMsRUFBRTtJQUFHLENBQUM7RUFBRSxDQUFDLENBQzlFO0VBQ0QsTUFBTXRCLE1BQU0sR0FBRztBQUNqQixhQUFhN0ksS0FBSztBQUNsQjtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQSx5QkFBeUJ6USxJQUFJLENBQUNDLFNBQVMsQ0FBQ21hLEtBQUssQ0FBQztBQUM5QztBQUNBLHlFQUF5RTtFQUN2RSxNQUFNcGIsT0FBTyxHQUFHLE1BQU1aLElBQUksQ0FBQ08sT0FBTyxDQUFDNmEsSUFBSSxDQUFDLDZCQUE2QixFQUFFO0lBQ3JFdFksT0FBTyxFQUFFO01BQUUsY0FBYyxFQUFFSDtJQUFRLENBQUM7SUFBRUksT0FBTyxFQUFFLE1BQU87SUFDdERrRyxJQUFJLEVBQUU7TUFBRWlTLE1BQU07TUFBRWxOLGNBQWMsRUFBRTtRQUFFQyxNQUFNLEVBQUUsT0FBTztRQUFFOUosTUFBTSxFQUFFa08sS0FBSztRQUFFZ0osWUFBWSxFQUFFbmMsVUFBVSxDQUFDLENBQUM7UUFDMUZvYyxNQUFNLEVBQUUsMkJBQTJCO1FBQUUxQyxjQUFjLEVBQUU7VUFBRWhWLFVBQVUsRUFBRWpCLE9BQU87VUFBRXdCLE1BQU0sRUFBRWtPLEtBQUs7VUFDdkZxSyxZQUFZLEVBQUUsZUFBZTtVQUFFQyxTQUFTLEVBQUVuZCxLQUFLO1VBQUVvZCxJQUFJLEVBQUUsTUFBTTtVQUM3REMsV0FBVyxFQUFFLENBQUMsVUFBVSxFQUFFLGFBQWEsRUFBRSxxQkFBcUIsQ0FBQztVQUFFQyxJQUFJLEVBQUU7UUFBdUM7TUFBRTtJQUFFO0VBQ3hILENBQUMsQ0FBQztFQUNGLElBQUksQ0FBQ2xjLE9BQU8sQ0FBQ29DLEVBQUUsQ0FBQyxDQUFDLEVBQUUsTUFBTSxJQUFJQyxLQUFLLENBQUMsUUFBUXJDLE9BQU8sQ0FBQ00sTUFBTSxDQUFDLENBQUMsS0FBSyxDQUFDLE1BQU1OLE9BQU8sQ0FBQ3NDLElBQUksQ0FBQyxDQUFDLEVBQUVDLEtBQUssQ0FBQyxDQUFDLEVBQUUsSUFBSSxDQUFDLEVBQUUsQ0FBQztFQUN4RyxNQUFNbUIsVUFBVSxDQUFDdEUsSUFBSSxFQUFFMkMsT0FBTyxDQUFDO0VBQy9CLElBQUlvYSxnQkFBMEIsR0FBRyxFQUFFO0VBQ25DLE1BQU1DLEtBQUssR0FBRyxNQUFBQSxDQUFBLEtBQVk7SUFDeEJELGdCQUFnQixHQUFHLENBQUMsTUFBTXJhLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSwyQkFBMkIsQ0FBQyxFQUFFZSxVQUFVLENBQUNrSCxRQUFRLENBQ25HN0QsR0FBRyxDQUFFRSxJQUFvQixJQUFLQSxJQUFJLENBQUNDLEVBQUUsQ0FBQyxDQUFDNkMsSUFBSSxDQUFDLENBQUM7SUFDaEQvSyxNQUFNLENBQUMrZCxnQkFBZ0IsQ0FBQyxDQUFDNVgsWUFBWSxDQUFDLENBQUMsQ0FBQztJQUN4QzZXLEtBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQ0ssV0FBVyxDQUFDLENBQUMsQ0FBQyxDQUFDRSxPQUFPLENBQUN4YixJQUFJLENBQUMsa0JBQWtCLENBQUM7SUFDeEQsTUFBTTBELE1BQU0sR0FBR3pFLElBQUksQ0FBQ2lDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBRUMsSUFBSSxFQUFFO0lBQWdDLENBQUMsQ0FBQztJQUNsRixNQUFNK2EsTUFBTSxHQUFHeFksTUFBTSxDQUFDeEMsU0FBUyxDQUFDLFFBQVEsRUFBRTtNQUFFQyxJQUFJLEVBQUUsVUFBVTtNQUFFQyxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUM7SUFDNUUsTUFBTW5ELE1BQU0sQ0FBQ2llLE1BQU0sQ0FBQyxDQUFDM0YsV0FBVyxDQUFDO01BQUV2VSxPQUFPLEVBQUU7SUFBUSxDQUFDLENBQUM7SUFDdEQsTUFBTWthLE1BQU0sQ0FBQzdPLEtBQUssQ0FBQyxDQUFDO0lBQ3BCLE1BQU12SyxLQUFLLEdBQUdZLE1BQU0sQ0FBQ3hDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBRUMsSUFBSSxFQUFFLDhCQUE4QjtNQUFFQyxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUMsQ0FBQ0YsU0FBUyxDQUFDLFNBQVMsQ0FBQztJQUNwSCxNQUFNNEIsS0FBSyxDQUFDcUwsSUFBSSxDQUFDLDJHQUEyRyxHQUN4SCwyRUFBMkUsR0FDM0UseUJBQXlCLEdBQUd0TixJQUFJLENBQUNDLFNBQVMsQ0FBQ21hLEtBQUssQ0FBQyxDQUFDO0lBQ3RELE1BQU12WCxNQUFNLENBQUN4QyxTQUFTLENBQUMsUUFBUSxFQUFFO01BQUVDLElBQUksRUFBRSx1QkFBdUI7TUFBRUMsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUNpTSxLQUFLLENBQUMsQ0FBQztJQUN4RixNQUFNcFAsTUFBTSxDQUFDNkUsS0FBSyxDQUFDLENBQUN6QixHQUFHLENBQUNDLFdBQVcsQ0FBQztNQUFFVSxPQUFPLEVBQUU7SUFBUSxDQUFDLENBQUM7RUFDM0QsQ0FBQztFQUNELE1BQU1pVyxVQUFVLEdBQUcsTUFBTXBILHFCQUFxQixDQUFDNVIsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLEtBQUssRUFBRSxDQUFDLGdCQUFnQixFQUFFLFNBQVMsQ0FBQyxFQUFFLEtBQUssRUFBRXlLLFNBQVMsRUFBRTRQLEtBQUssQ0FBQztFQUM1SCxNQUFNdFcsUUFBUSxHQUFHLE1BQU1wQixVQUFVLENBQUN0RixJQUFJLEVBQUUyQyxPQUFPLEVBQUUsZ0JBQWdCLENBQUM7RUFDbEUsTUFBTTJGLEtBQUssR0FBRzVCLFFBQVEsQ0FBQzBELElBQUksQ0FBQ25ELElBQUksSUFBSUEsSUFBSSxDQUFDL0UsSUFBSSxLQUFLLGdCQUFnQixDQUFDO0VBQ25FLE1BQU1xYSxPQUFPLEdBQUc3VixRQUFRLENBQUNtRSxNQUFNLENBQUM1RCxJQUFJLElBQUlBLElBQUksQ0FBQy9FLElBQUksS0FBSyxrQkFBa0IsQ0FBQztFQUN6RWxELE1BQU0sQ0FBQ3VkLE9BQU8sQ0FBQyxDQUFDcFgsWUFBWSxDQUFDLENBQUMsQ0FBQztFQUMvQm5HLE1BQU0sQ0FBQ3VkLE9BQU8sQ0FBQyxDQUFDLENBQUMsQ0FBQzlPLFFBQVEsQ0FBQ3lQLGVBQWUsQ0FBQyxDQUFDemEsSUFBSSxDQUFDNkYsS0FBSyxDQUFDcEIsRUFBRSxDQUFDO0VBQzFELE1BQU1pVyxhQUFhLEdBQUcsb0NBQW9DO0VBQzFELE1BQU12UyxRQUFRLEdBQUcsQ0FBQyxNQUFNbEksV0FBVyxDQUFDMUMsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLDJCQUEyQixDQUFDLEVBQUVlLFVBQVUsQ0FBQ2tILFFBQVE7RUFDcEc1TCxNQUFNLENBQUM0TCxRQUFRLENBQUM3RCxHQUFHLENBQUVFLElBQW9CLElBQUtBLElBQUksQ0FBQ0MsRUFBRSxDQUFDLENBQUM2QyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUMvSCxPQUFPLENBQUMsQ0FBQyxHQUFHK2EsZ0JBQWdCLEVBQUVJLGFBQWEsQ0FBQyxDQUFDcFQsSUFBSSxDQUFDLENBQUMsQ0FBQztFQUNuSC9LLE1BQU0sQ0FBQyxJQUFJb04sR0FBRyxDQUFDeEIsUUFBUSxDQUFDN0QsR0FBRyxDQUFFRSxJQUFzQixJQUFLQSxJQUFJLENBQUMvRSxJQUFJLENBQUMsQ0FBQyxDQUFDc0ssSUFBSSxDQUFDLENBQUMvSixJQUFJLENBQUNtSSxRQUFRLENBQUNsRixNQUFNLENBQUM7RUFDL0YsTUFBTTBYLFFBQVEsR0FBRyxDQUFDLE1BQU0xYSxXQUFXLENBQUMxQyxJQUFJLEVBQUUyQyxPQUFPLEVBQUUsd0NBQXdDLENBQUMsRUFBRXlhLFFBQVE7RUFDdEcsTUFBTUMsU0FBUyxHQUFHRCxRQUFRLENBQUNFLEtBQUssQ0FBQ2xULElBQUksQ0FBRW1ULElBQVMsSUFBS0EsSUFBSSxDQUFDQyxpQkFBaUIsS0FBS0wsYUFBYSxDQUFDO0VBQzlGbmUsTUFBTSxDQUFDcWUsU0FBUyxDQUFDLENBQUNyVixVQUFVLENBQUMsQ0FBQztFQUM5QmhKLE1BQU0sQ0FBQ3FlLFNBQVMsQ0FBQ0ksR0FBRyxDQUFDLENBQUNoYixJQUFJLENBQUMsUUFBUSxDQUFDO0VBQ3BDekQsTUFBTSxDQUFDNkosTUFBTSxDQUFDNEcsTUFBTSxDQUFDNE4sU0FBUyxDQUFDSyxlQUFlLENBQUMsQ0FBQyxDQUFDQyxjQUFjLENBQUMzZSxNQUFNLENBQUM0ZSxnQkFBZ0IsQ0FBQztJQUN0RjdOLE1BQU0sRUFBRXdNLE9BQU8sQ0FBQyxDQUFDLENBQUMsQ0FBQ3JWLEVBQUU7SUFBRW9VLE1BQU0sRUFBRWhULEtBQUssQ0FBQ3BCLEVBQUU7SUFBRTJXLGFBQWEsRUFBRSxVQUFVO0lBQUVDLFFBQVEsRUFBRTtFQUNoRixDQUFDLENBQUMsQ0FBQztFQUNILEtBQUssTUFBTSxDQUFDQyxJQUFJLEVBQUVDLFVBQVUsQ0FBQyxJQUFJLENBQUMsQ0FBQyxRQUFRLEVBQUV6QixPQUFPLENBQUMsQ0FBQyxDQUFDLENBQUNyVixFQUFFLENBQUMsRUFBRSxDQUFDLFFBQVEsRUFBRW9CLEtBQUssQ0FBQ3BCLEVBQUUsQ0FBQyxDQUFDLEVBQUU7SUFDbEYsTUFBTStXLElBQUksR0FBR2IsUUFBUSxDQUFDcFcsS0FBSyxDQUFDb0QsSUFBSSxDQUFFbkQsSUFBUyxJQUFLQSxJQUFJLENBQUNDLEVBQUUsS0FBS21XLFNBQVMsQ0FBQ1UsSUFBSSxDQUFDLENBQUM7SUFDNUUvZSxNQUFNLENBQUNpZixJQUFJLENBQUNDLGFBQWEsQ0FBQyxDQUFDemIsSUFBSSxDQUFDdWIsVUFBVSxDQUFDO0lBQzNDaGYsTUFBTSxDQUFDaWYsSUFBSSxDQUFDRSxLQUFLLENBQUMsQ0FBQ1IsY0FBYyxDQUFDM2UsTUFBTSxDQUFDNGUsZ0JBQWdCLENBQUM7TUFBRTFXLEVBQUUsRUFBRW1XLFNBQVMsQ0FBQ1UsSUFBSSxHQUFHLE1BQU0sQ0FBQztNQUN0Rk4sR0FBRyxFQUFFLFFBQVE7TUFBRUQsaUJBQWlCLEVBQUVMO0lBQWMsQ0FBQyxDQUFDLENBQUM7RUFDdkQ7RUFDQSxNQUFNbEUsU0FBUyxHQUFHLE1BQU01UCxlQUFlLENBQUNySixJQUFJLEVBQUUyQyxPQUFPLEVBQUUsQ0FBQyxDQUFDO0VBQ3pELE1BQU0wVixRQUFRLENBQUMzVyxNQUFNLENBQUMsb0JBQW9CLEVBQUU7SUFBRUMsSUFBSSxFQUFFQyxJQUFJLENBQUNDLFNBQVMsQ0FBQztNQUFFYyxPQUFPO01BQUUsR0FBR3FXLFVBQVU7TUFBRSxHQUFHQztJQUFVLENBQUMsQ0FBQztJQUFFblgsV0FBVyxFQUFFO0VBQW1CLENBQUMsQ0FBQztBQUNsSixDQUFDLENBQUM7O0FBRUY7QUFDQS9DLElBQUksQ0FBQyw0RkFBNEYsRUFBRSxPQUFPO0VBQUVpQjtBQUFLLENBQUMsRUFBRXFZLFFBQVEsS0FBSztFQUMvSCxNQUFNMVYsT0FBTyxHQUFHLGVBQWUsR0FBR3pELFVBQVUsQ0FBQyxDQUFDO0VBQzlDLE1BQU11RixNQUFNLEdBQUcsTUFBTUgsVUFBVSxDQUFDdEUsSUFBSSxFQUFFMkMsT0FBTyxDQUFDO0VBQzlDLE1BQU04QixNQUFNLENBQUNxVCxVQUFVLENBQUMsYUFBYSxFQUFFO0lBQUUzVixLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQ2lNLEtBQUssQ0FBQyxDQUFDO0VBQy9ELE1BQU0zSixNQUFNLENBQUNFLE9BQU8sQ0FBQywyQkFBMkIsQ0FBQyxDQUFDdUssSUFBSSxDQUFDLDJCQUEyQixDQUFDO0VBQ25GLE1BQU16SyxNQUFNLENBQUNzVCxVQUFVLENBQUMscUJBQXFCLEVBQUU7SUFBRTVWLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDK00sSUFBSSxDQUFDLDZSQUE2UixDQUFDO0VBQ25XLE1BQU16SyxNQUFNLENBQUNxVCxVQUFVLENBQUMsY0FBYyxFQUFFO0lBQUUzVixLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQ2lNLEtBQUssQ0FBQyxDQUFDO0VBQ2hFLE1BQU0zSixNQUFNLENBQUN4QyxTQUFTLENBQUMsUUFBUSxFQUFFO0lBQUVDLElBQUksRUFBRSxpQ0FBaUM7SUFBRUMsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDLENBQUNpTSxLQUFLLENBQUMsQ0FBQztFQUNsRyxLQUFLLE1BQU0sQ0FBQ2hJLEtBQUssRUFBRXVJLEtBQUssQ0FBQyxJQUFJLENBQUMsQ0FBQyxVQUFVLEVBQUUsR0FBRyxDQUFDLEVBQUUsQ0FBQyxZQUFZLEVBQUUsR0FBRyxDQUFDLEVBQUUsQ0FBQyxVQUFVLEVBQUUsR0FBRyxDQUFDLEVBQUUsQ0FBQyxTQUFTLEVBQUUsR0FBRyxDQUFDLENBQUMsRUFBRSxNQUFNbEssTUFBTSxDQUFDc1QsVUFBVSxDQUFDLEdBQUczUixLQUFLLHVCQUF1QixFQUFFO0lBQUVqRSxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQytNLElBQUksQ0FBQ1AsS0FBSyxDQUFDO0VBQ2pNLE1BQU15UCxJQUFJLEdBQUczWixNQUFNLENBQUNFLE9BQU8sQ0FBQyxTQUFTLENBQUMsQ0FBQ2tHLE1BQU0sQ0FBQztJQUFFYixHQUFHLEVBQUVoSyxJQUFJLENBQUMyRSxPQUFPLENBQUMsU0FBUyxDQUFDLENBQUNrRyxNQUFNLENBQUM7TUFBRXdULE9BQU8sRUFBRTtJQUFVLENBQUM7RUFBRSxDQUFDLENBQUMsQ0FBQ3JKLEtBQUssQ0FBQyxDQUFDO0VBQ3RILE1BQU1oVyxNQUFNLENBQUNvZixJQUFJLENBQUMsQ0FBQy9iLFdBQVcsQ0FBQyxDQUFDO0VBQ2hDLE1BQU0rYixJQUFJLENBQUN6WixPQUFPLENBQUMsU0FBUyxDQUFDLENBQUN5SixLQUFLLENBQUMsQ0FBQztFQUNyQyxNQUFNa1EsUUFBUSxHQUFHRixJQUFJLENBQUNuYyxTQUFTLENBQUMsUUFBUSxFQUFFO0lBQUVDLElBQUksRUFBRSx3Q0FBd0M7SUFBRUMsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDO0VBQzFHLE1BQU1uRCxNQUFNLENBQUNzZixRQUFRLENBQUMsQ0FBQ0MsV0FBVyxDQUFDLENBQUM7RUFBRSxNQUFNRCxRQUFRLENBQUNFLE9BQU8sQ0FBQyxDQUFDO0VBQzlELE1BQU1qRyxZQUFZLEdBQUd2WSxJQUFJLENBQUN3WSxjQUFjLENBQUNqWSxPQUFPO0lBQUEsSUFBQWtlLHNCQUFBO0lBQUEsT0FBSWxlLE9BQU8sQ0FBQ0ksR0FBRyxDQUFDLENBQUMsQ0FBQ21OLFFBQVEsQ0FBQyxpQkFBaUIsQ0FBQyxJQUFJdk4sT0FBTyxDQUFDRSxNQUFNLENBQUMsQ0FBQyxLQUFLLE1BQU0sSUFBSSxFQUFBZ2Usc0JBQUEsR0FBQWxlLE9BQU8sQ0FBQ3dOLFlBQVksQ0FBQyxDQUFDLGNBQUEwUSxzQkFBQSxnQkFBQUEsc0JBQUEsR0FBdEJBLHNCQUFBLENBQXdCelEsY0FBYyxjQUFBeVEsc0JBQUEsdUJBQXRDQSxzQkFBQSxDQUF3Q3hRLE1BQU0sTUFBSyxPQUFPO0VBQUEsRUFBQztFQUMzTCxLQUFLLElBQUl2SixJQUFJLEdBQUcsQ0FBQyxFQUFFQSxJQUFJLEdBQUcsRUFBRSxFQUFFQSxJQUFJLEVBQUUsRUFBRTtJQUNwQyxNQUFNdVAsTUFBTSxHQUFHeFAsTUFBTSxDQUFDRSxPQUFPLENBQUMsK0JBQStCLENBQUMsQ0FBQzFDLFNBQVMsQ0FBQyxRQUFRLENBQUM7SUFDbEYsTUFBTWpELE1BQU0sQ0FBQ2lWLE1BQU0sQ0FBQyxDQUFDcUQsV0FBVyxDQUFDLENBQUM7SUFBRSxNQUFNbFIsS0FBSyxHQUFHLE1BQU02TixNQUFNLENBQUN1QyxTQUFTLENBQUMsQ0FBQztJQUFFLE1BQU12QyxNQUFNLENBQUM3RixLQUFLLENBQUMsQ0FBQztJQUNoRyxJQUFJaEksS0FBSyxLQUFLLFlBQVksSUFBSUEsS0FBSyxLQUFLLGlCQUFpQixFQUFFO0VBQzdEO0VBQ0EsTUFBTXBDLE9BQU8sR0FBRyxDQUFDLE1BQU11VSxZQUFZLEVBQUV4SyxZQUFZLENBQUMsQ0FBQyxDQUFDQyxjQUFjLENBQUM0SyxjQUFjO0VBQ2pGLE1BQU1sRCxTQUFTLEdBQUcxUixPQUFPLENBQUMwYSwwQkFBMEIsQ0FBQ3JTLE9BQU8sQ0FBRXNTLE9BQVk7SUFBQSxJQUFBQyxxQkFBQTtJQUFBLFFBQUFBLHFCQUFBLEdBQUtELE9BQU8sQ0FBQ0UsaUJBQWlCLGNBQUFELHFCQUFBLGNBQUFBLHFCQUFBLEdBQUksRUFBRTtFQUFBLEVBQUM7RUFDL0csTUFBTWpOLEdBQUcsR0FBRytELFNBQVMsQ0FBQ3RMLElBQUksQ0FBRXVHLEtBQVUsSUFBS0EsS0FBSyxDQUFDWixNQUFNLEtBQUssZ0JBQWdCLElBQUlZLEtBQUssQ0FBQzJLLE1BQU0sS0FBSyxtQkFBbUIsQ0FBQztFQUNySHRjLE1BQU0sQ0FBQzJTLEdBQUcsQ0FBQzlLLE9BQU8sQ0FBQyxDQUFDN0UsT0FBTyxDQUFDLEVBQUUsQ0FBQztFQUFFaEQsTUFBTSxDQUFDMlMsR0FBRyxDQUFDbU4sZ0JBQWdCLENBQUMsQ0FBQzljLE9BQU8sQ0FBQyxDQUFDLG9CQUFvQixDQUFDLENBQUM7RUFDN0YsSUFBSXFVLFFBQWE7RUFDakIsTUFBTXJYLE1BQU0sQ0FBQ3VILElBQUksQ0FBQyxZQUFZO0lBQzVCLE1BQU00SyxZQUFZLEdBQUcsTUFBTXpPLFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSxxQ0FBcUMsQ0FBQztJQUM1RixJQUFJLENBQUN3TyxZQUFZLENBQUNsSSxJQUFJLENBQUNtSSxlQUFlLEVBQUUsT0FBTyxLQUFLO0lBQ3BEaUYsUUFBUSxHQUFHLENBQUMsTUFBTTNULFdBQVcsQ0FBQzFDLElBQUksRUFBRTJDLE9BQU8sRUFBRSxvQ0FBb0N3TyxZQUFZLENBQUNsSSxJQUFJLENBQUNtSSxlQUFlLEVBQUUsQ0FBQyxFQUFFbkksSUFBSTtJQUMzSCxPQUFPb04sUUFBUSxDQUFDVyxhQUFhLEtBQUssMEJBQTBCO0VBQzlELENBQUMsRUFBRTtJQUFFalUsT0FBTyxFQUFFO0VBQVEsQ0FBQyxDQUFDLENBQUNOLElBQUksQ0FBQyxJQUFJLENBQUM7RUFDbkMsTUFBTXpDLElBQUksQ0FBQ3NRLE1BQU0sQ0FBQyxDQUFDO0VBQUUsTUFBTWhNLFVBQVUsQ0FBQ3RFLElBQUksRUFBRTJDLE9BQU8sQ0FBQztFQUNwRCxNQUFNNFcsUUFBUSxHQUFHbEQsUUFBUSxDQUFDQyxpQkFBaUIsQ0FBQ2lELFFBQVEsQ0FBQzFPLE1BQU0sQ0FBRTVELElBQVMsSUFBS0EsSUFBSSxDQUFDdVMsSUFBSSxLQUFLLHFCQUFxQixDQUFDO0VBQy9HLElBQUlELFFBQVEsQ0FBQzdULE1BQU0sRUFBRTtJQUNuQixNQUFNcVosTUFBTSxHQUFHL2UsSUFBSSxDQUFDaUMsU0FBUyxDQUFDLFFBQVEsRUFBRTtNQUFFQyxJQUFJLEVBQUU7SUFBNkIsQ0FBQyxDQUFDO0lBQy9FLE1BQU1sRCxNQUFNLENBQUMrZixNQUFNLENBQUMsQ0FBQ2pPLGFBQWEsQ0FBQyxHQUFHdUYsUUFBUSxDQUFDQyxpQkFBaUIsQ0FBQ2lELFFBQVEsQ0FBQzdULE1BQU0sY0FBYyxDQUFDO0lBQy9GLE1BQU0xRyxNQUFNLENBQUMrZixNQUFNLENBQUM5YyxTQUFTLENBQUMsTUFBTSxFQUFFO01BQUVDLElBQUksRUFBRTtJQUFpRCxDQUFDLENBQUMsQ0FBQzhTLEtBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQ21GLGVBQWUsQ0FBQyxNQUFNLEVBQUUsSUFBSUMsTUFBTSxDQUFDLFdBQVd6WCxPQUFPLEVBQUUsQ0FBQyxDQUFDO0lBQ3BLLE1BQU1vYyxNQUFNLENBQUNwYSxPQUFPLENBQUMsU0FBUyxDQUFDLENBQUNxUSxLQUFLLENBQUMsQ0FBQyxDQUFDNUcsS0FBSyxDQUFDLENBQUM7SUFBRSxNQUFNcFAsTUFBTSxDQUFDK2YsTUFBTSxDQUFDOWMsU0FBUyxDQUFDLFlBQVksRUFBRTtNQUFFQyxJQUFJLEVBQUU7SUFBd0IsQ0FBQyxDQUFDLENBQUM4UyxLQUFLLENBQUMsQ0FBQyxDQUFDLENBQUMzUyxXQUFXLENBQUMsQ0FBQztFQUN4SjtFQUNBLE1BQU0yYyxLQUFLLEdBQUdoZixJQUFJLENBQUNtVixlQUFlLENBQUNuVSxRQUFRLElBQUlBLFFBQVEsQ0FBQ0wsR0FBRyxDQUFDLENBQUMsQ0FBQ0gsUUFBUSxDQUFDLGNBQWM2VixRQUFRLENBQUM5RSxXQUFXLGdCQUFnQixDQUFDLElBQUl2USxRQUFRLENBQUNULE9BQU8sQ0FBQyxDQUFDLENBQUNFLE1BQU0sQ0FBQyxDQUFDLEtBQUssTUFBTSxDQUFDO0VBQ3JLLE1BQU1ULElBQUksQ0FBQ2lDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7SUFBRUMsSUFBSSxFQUFFLG9DQUFvQztJQUFFQyxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQ2lNLEtBQUssQ0FBQyxDQUFDO0VBQUVwUCxNQUFNLENBQUMsQ0FBQyxNQUFNZ2dCLEtBQUssRUFBRWhjLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQ1AsSUFBSSxDQUFDLElBQUksQ0FBQztFQUMxSSxNQUFNdUUsS0FBSyxHQUFHLE1BQU0xQixVQUFVLENBQUN0RixJQUFJLEVBQUUyQyxPQUFPLEVBQUUsZ0JBQWdCLENBQUM7RUFDL0QsTUFBTWlFLFFBQVEsR0FBRyxNQUFNdEIsVUFBVSxDQUFDdEYsSUFBSSxFQUFFMkMsT0FBTyxFQUFFLFVBQVUsQ0FBQztFQUFFLE1BQU1rRSxPQUFPLEdBQUcsTUFBTXZCLFVBQVUsQ0FBQ3RGLElBQUksRUFBRTJDLE9BQU8sRUFBRSxTQUFTLENBQUM7RUFDeEgsTUFBTTJFLE1BQU0sR0FBR1QsT0FBTyxDQUFDdUQsSUFBSSxDQUFDbkQsSUFBSSxJQUFJQSxJQUFJLENBQUMvRSxJQUFJLEtBQUssb0JBQW9CLENBQUM7RUFBRWxELE1BQU0sQ0FBQ3NJLE1BQU0sQ0FBQyxDQUFDVSxVQUFVLENBQUMsQ0FBQztFQUNwRyxNQUFNRixPQUFPLEdBQUdsQixRQUFRLENBQUN3RCxJQUFJLENBQUNuRCxJQUFJLElBQUlBLElBQUksQ0FBQ0MsRUFBRSxLQUFLSSxNQUFNLENBQUNTLFVBQVUsQ0FBQztFQUNwRSxNQUFNa1gsT0FBTyxHQUFHalksS0FBSyxDQUFDb0QsSUFBSSxDQUFDbkQsSUFBSSxJQUFJQSxJQUFJLENBQUMvRSxJQUFJLEtBQUssbUJBQW1CLENBQUM7RUFDckUsTUFBTWdkLE1BQU0sR0FBR2xZLEtBQUssQ0FBQ29ELElBQUksQ0FBQ25ELElBQUksSUFBSUEsSUFBSSxDQUFDL0UsSUFBSSxLQUFLLHVCQUF1QixDQUFDO0VBQ3hFbEQsTUFBTSxDQUFDOEksT0FBTyxDQUFDSSxhQUFhLENBQUNDLHNCQUFzQixDQUFDK0QsS0FBSyxDQUFDLENBQUN6SixJQUFJLENBQUMsaUJBQWlCLENBQUM7RUFDbEZ6RCxNQUFNLENBQUM4SSxPQUFPLENBQUNJLGFBQWEsQ0FBQ0Msc0JBQXNCLENBQUMyRCxhQUFhLENBQUMsQ0FBQzFKLEdBQUcsQ0FBQ3FYLFNBQVMsQ0FBQ3dGLE9BQU8sQ0FBQy9YLEVBQUUsQ0FBQztFQUM1RmxJLE1BQU0sQ0FBQzhJLE9BQU8sQ0FBQ0ksYUFBYSxDQUFDQyxzQkFBc0IsQ0FBQzJELGFBQWEsQ0FBQyxDQUFDMk4sU0FBUyxDQUFDeUYsTUFBTSxDQUFDaFksRUFBRSxDQUFDO0VBQ3ZGLE1BQU1tUixRQUFRLENBQUMzVyxNQUFNLENBQUMsMEJBQTBCLEVBQUU7SUFBRUMsSUFBSSxFQUFFQyxJQUFJLENBQUNDLFNBQVMsQ0FBQztNQUFFYyxPQUFPO01BQUVnUCxHQUFHO01BQUU3SjtJQUFRLENBQUMsQ0FBQztJQUFFaEcsV0FBVyxFQUFFO0VBQW1CLENBQUMsQ0FBQztBQUN6SSxDQUFDLENBQUMiLCJpZ25vcmVMaXN0IjpbXX0=