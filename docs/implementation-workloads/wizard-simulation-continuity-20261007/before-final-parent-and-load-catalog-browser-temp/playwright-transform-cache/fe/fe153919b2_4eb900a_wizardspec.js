// 26b590cd671b0b35a92fd5bf352c2fe0a3528f8e
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
  },
  // Match the unchanged captured 100-Mbit/s request and genuinely change
  // the 1-Gbit/s profile seed, so saving exercises user-value provenance.
  {
    technology: 'ethernet',
    fields: {
      bitrate: '100 Mbit/s'
    },
    native: {
      bitrate: 100000000
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
    // Each phase must really edit the seed: an identical save correctly
    // leaves the existing proposal VALIDATED instead of making it OUTDATED.
    const reviewSeed = proposalType === 'WIZARD_ENGINEERING_MODEL' ? 41 : proposalType === 'WIZARD_ROUTING' ? 43 : 42;
    await repeatParameterReturn(page, project, proposalId, largeParameterScenarios(), [reviewSeed]);
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
      bitrate: 100000000
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
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmVhZEZpbGUiLCJyYW5kb21VVUlEIiwiZXhlY0ZpbGVTeW5jIiwiV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyIsIldJWkFSRF9TVEVQUyIsIldJWkFSRF9ET05FIiwicmV2aWV3VmlydHVhbFRyYW5zcG9ydHMiLCJzdGVwcyIsImRvbmUiLCJ3cml0ZVRpbWluZ3MiLCJNYXAiLCJ3b3JrZmxvd1BhZ2VGYWlsdXJlcyIsIldlYWtNYXAiLCJwcm9ncmVzc01pbGVzdG9uZXMiLCJiZWZvcmVFYWNoIiwicGFnZSIsImluZm8iLCJyb3dzIiwic2V0IiwidGVzdElkIiwicmVxdWVzdHMiLCJvbiIsInJlcXVlc3QiLCJpbmNsdWRlcyIsIm1ldGhvZCIsInJvdyIsInVybCIsInN0YXJ0ZWQiLCJEYXRlIiwibm93IiwicHVzaCIsInJlc3BvbnNlIiwiZ2V0Iiwic3RhdHVzIiwiVVJMIiwicGF0aG5hbWUiLCJkdXJhdGlvbl9tcyIsIl9yZXF1ZXN0JGZhaWx1cmUiLCJmYWlsdXJlIiwiZXJyb3JUZXh0IiwiYWZ0ZXJFYWNoIiwiYXR0YWNoIiwiYm9keSIsIkpTT04iLCJzdHJpbmdpZnkiLCJjb250ZW50VHlwZSIsImRlbGV0ZSIsInRvRXF1YWwiLCJnZXRCeVJvbGUiLCJuYW1lIiwiZXhhY3QiLCJub3QiLCJ0b0JlVmlzaWJsZSIsImFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkiLCJnZXRCeVRleHQiLCJpc1Zpc2libGUiLCJ0b0JlIiwicmVhZFByb2plY3QiLCJwcm9qZWN0IiwicGF0aCIsInJlc3VsdCIsImhlYWRlcnMiLCJ0aW1lb3V0Iiwib2siLCJFcnJvciIsInRleHQiLCJzbGljZSIsImpzb24iLCJkaXNwb3NlIiwicmVhZFdhcm5pbmdSZXZpZXdTdGF0ZSIsIl92ZXJpZmllZCRjb250ZXh0JGFnZTIiLCJfdmVyaWZpZWQkY29udGV4dCRhZ2UzIiwiYXV0aG9yaXR5IiwicGFyYW1ldGVycyIsInZlcmlmaWVkIiwicHJvamVjdF9pZCIsImZpZWxkIiwiX3ZlcmlmaWVkJGNvbnRleHQkYWdlIiwiX2F1dGhvcml0eSRjb250ZXh0JGFnIiwiY29udGV4dCIsImFnZW50X2V4ZWN1dGlvbiIsInN0YXR1c2VzIiwicnVuX2lkIiwicmVxdWVzdF9yZXZpc2lvbiIsInByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsIiwib3BlbldpemFyZCIsImdvdG8iLCJ3YWl0VW50aWwiLCJkaWFsb2ciLCJzdGVwIiwibG9jYXRvciIsInN0ZXBXaWR0aCIsImV2YWx1YXRlIiwiZWxlbWVudCIsImdldEJvdW5kaW5nQ2xpZW50UmVjdCIsIndpZHRoIiwiY2FyZHMiLCJhbGwiLCJ0b0hhdmVMZW5ndGgiLCJjYXJkIiwidG9CZUdyZWF0ZXJUaGFuIiwiYWxsT2JqZWN0cyIsInJlc291cmNlIiwiaXRlbXMiLCJvZmZzZXQiLCJsZW5ndGgiLCJyZXN0YXJ0QXBwbGljYXRpb24iLCJjcmFzaCIsImNvbnRhaW5lciIsInByb2Nlc3MiLCJlbnYiLCJOSVNfRTJFX0FQUF9DT05UQUlORVIiLCJ0b01hdGNoIiwiZG9ja2VyIiwiTklTX1RFU1RfRE9DS0VSIiwibGFiZWwiLCJlbmNvZGluZyIsInRyaW0iLCJwb2xsIiwidmVyaWZ5U2lnbmFsQ29udHJhY3RzIiwiZXhwZWN0ZWQiLCJoYXJkd2FyZSIsImZ1bmN0aW9ucyIsIm1lc3NhZ2VzIiwic2lnbmFscyIsIlByb21pc2UiLCJtYXAiLCJub2RlcyIsIml0ZW0iLCJpZCIsImZ1bmN0aW9uc0J5SWQiLCJtZXNzYWdlc0J5SWQiLCJjb250cmFjdHMiLCJzaWduYWwiLCJfcmVmIiwiX3NpZ25hbCRkYXRhJGVudW1fdmFsIiwiX3NpZ25hbCRkYXRhIiwiX3NpZ25hbCRzZW1hbnRpYyRzZW1hIiwiX3NpZ25hbCRzZW1hbnRpYyIsIl9zaWduYWwkY29uZmlndXJhdGlvbiIsIl9zaWduYWwkY29uZmlndXJhdGlvbjIiLCJtZXNzYWdlIiwibWVzc2FnZV9pZCIsInRvQmVUcnV0aHkiLCJyZWZlcmVuY2UiLCJjb25maWd1cmF0aW9uIiwiY29tbXVuaWNhdGlvbl9jb250cmFjdCIsInByb2R1Y2VyX3JlZiIsImZuIiwib3duZXIiLCJoYXJkd2FyZV9ub2RlX2lkIiwicHJvZHVjZXIiLCJkZXZpY2VfdHlwZSIsImtleSIsImpvaW4iLCJ0b0JlVW5kZWZpbmVkIiwiT2JqZWN0IiwiZnJvbUVudHJpZXMiLCJfc2lnbmFsJGZpZWxkIiwiZW51bV92YWx1ZXMiLCJkYXRhIiwic2VtYW50aWNfdHlwZSIsInNlbWFudGljIiwiZ2VuZXJhdGlvbl9yb2xlIiwidmVyaWZ5QXJ0aWZhY3RzIiwibWluaW11bUNhbm9uaWNhbFNpZ25hbHMiLCJpbnRlcm5hbENvbnRyb2xsZXIiLCJleHBlY3RlZFBhcmFtZXRlcnMiLCJleHBlY3RlZE5hdGl2ZVJhdGVzIiwiX2Fzc2Vzc21lbnQkc2NvcGVfY292Iiwid29ya2Zsb3ciLCJqb2JMaXN0Iiwic25hcHNob3RzIiwia2V5cyIsInNvcnQiLCJoYXMiLCJqb2JzIiwic25hcHNob3QiLCJzaW11bGF0aW9ucyIsImZpbmQiLCJqb2JfaWQiLCJmdWxsIiwiZGF0YV9iaXRyYXRlIiwiY2FuX2ZkX2RhdGFfcHJlc2NhbGVyIiwicnVudGltZVBhcmFtZXRlcnMiLCJ0b01hdGNoT2JqZWN0IiwiY2FuRmROZXR3b3JrcyIsIm5ldHdvcmtzIiwiZmlsdGVyIiwibmV0d29yayIsInRlY2hub2xvZ3kiLCJyYXRlcyIsImVudHJpZXMiLCJhc3Nlc3NtZW50Iiwic2NvcGVfY292ZXJhZ2UiLCJzY29wZV9tb2RlIiwiY29tcGxldGUiLCJjb25mb3JtYW5jZSIsImZhaWxlZF9yb3V0ZV9jb3VudCIsInRvQmVHcmVhdGVyVGhhbk9yRXF1YWwiLCJleGNsdWRlZCIsInRyYW5zcG9ydF9leGNsdXNpb25zIiwicm91dGluZyIsImVuYWJsZWQiLCJjb250cmFjdCIsImNvbnN1bWVyX3JlZnMiLCJyZWFzb25fY29kZSIsInJvbGUiLCJjb250cm9sbGVyIiwic2NvcGUiLCJleGNsdWRlZFNpZ25hbHMiLCJTZXQiLCJmbGF0TWFwIiwic2lnbmFsX2lkcyIsIm9ic2VydmVkX3NpZ25hbF9jb3VudCIsInNpemUiLCJ0cmFjZSIsImNvdW50IiwiZXZlbnRzIiwic29tZSIsImpvYiIsInBhcmFtZXRlcl9wcm9vZiIsInNhdmVkIiwic2ltdWxhdGlvbl9yYXRlcyIsImJpdHJhdGUiLCJhcmJpdHJhdGlvbl9iaXRyYXRlIiwiaGFyZHdhcmVfZXZpZGVuY2UiLCJ1bmRlZmluZWQiLCJyZXBlYXRQYXJhbWV0ZXJSZXR1cm4iLCJwcm9wb3NhbElkIiwic2NlbmFyaW9zIiwic2VlZHMiLCJiZWZvcmUiLCJpZGVudGl0eSIsIm5vZGVJZHMiLCJzdGFydHMiLCJ0cmFja1N0YXJ0cyIsIl9yZXF1ZXN0JHBvc3REYXRhSlNPTiIsImVuZHNXaXRoIiwicG9zdERhdGFKU09OIiwid2l6YXJkX2NvbW1hbmQiLCJhY3Rpb24iLCJldmlkZW5jZSIsIndpemFyZCIsImNsaWNrIiwiY3ljbGUiLCJzZWVkIiwic2NlbmFyaW8iLCJfc2F2ZWQkcGFyYW1ldGVycyRzaW0iLCJlbmNvZGVVUklDb21wb25lbnQiLCJjb21tb24iLCJ2YWx1ZSIsImZpZWxkcyIsIl9zY2VuYXJpbyRlZGl0RmllbGRzIiwiaW5wdXQiLCJkZXRhaWxzIiwiZ2V0QXR0cmlidXRlIiwiZWRpdEZpZWxkcyIsImZpbGwiLCJ0b0hhdmVWYWx1ZSIsIlN0cmluZyIsInNjb3BlZCIsInRlY2hub2xvZ3lfcGFyYW1ldGVycyIsImFzc3VtZWQiLCJzaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucyIsInZhbHVlcyIsIm5hdGl2ZVZhbHVlcyIsIm5hdGl2ZSIsImNvbmZpcm1lZCIsImhhc093biIsInByb3ZlbmFuY2UiLCJzb3VyY2UiLCJ1c2VyVmFsdWVzIiwidmFsdWVfb3JpZ2luIiwidGVjaG5vbG9neV9kZWZhdWx0cyIsInN0YWxlIiwiY2Fub25pY2FsSWRzIiwiY2Fub25pY2FsX2lkcyIsInJlbG9hZCIsInJlc3VtZVJlc3RvcmUiLCJyZXN0b3JlUGF1c2UiLCJyZXNvbHZlIiwiZGVsYXlSZXN0b3JlIiwicm91dGUiLCJjb250aW51ZSIsImRlbGF5ZWQiLCJ0b0NvbnRhaW5UZXh0IiwidW5yb3V0ZUFsbCIsImJlaGF2aW9yIiwicmVzdG9yZWQiLCJzdGF0ZSIsImNvbnZlcnNhdGlvbiIsImFjdGl2ZV9wcm9wb3NhbCIsImZyZXNoIiwiYWZ0ZXIiLCJwcm9wb3NhbF9pZCIsInNhdmVkX3ZhbHVlcyIsImFzc3VtcHRpb25zIiwicmVzdG9yZWRfc3RhdHVzIiwib2ZmIiwiY29tcGxldGVUaHJvdWdoV2l6YXJkIiwicmVzdGFydCIsImV4cGVjdGVkSGFyZHdhcmUiLCJjcmFzaFNpbXVsYXRpb24iLCJleHBlY3RlZFNpZ25hbHMiLCJhZnRlckZpcnN0TW9kZWxBcHBsaWVkIiwic3RvcE9uRXZpZGVuY2VCbG9jayIsImJlZm9yZVByb3Bvc2FsUmV2aWV3IiwicmV2aWV3Q291bnQiLCJydW5JZCIsInJldmlld2VkIiwicmVzdGFydGVkSm9iSWQiLCJ3YXRjaGRvZyIsInBlcmZvcm1hbmNlIiwiY2hlY2twb2ludCIsIl93b3JrZmxvdyRjb250ZXh0JGFnZSIsIl93b3JrZmxvdyRjb250ZXh0JGFnZTIiLCJfZXhlY3V0aW9uJGJsb2NraW5nX2YiLCJfZXhlY3V0aW9uJG1lc3NhZ2UiLCJyZWFkeVZlcnNpb24iLCJyZWFkeVNpbmNlIiwiaXNDaGVja3BvaW50IiwicmVtYWluaW5nIiwicHJvZ3Jlc3MiLCJvYnNlcnZlIiwiYWR2YW5jZWQiLCJhdCIsInRvSVNPU3RyaW5nIiwiZnJvbnRpZXIiLCJjb21wbGV0ZWRUaHJvdWdoIiwiZXhlY3V0aW9uIiwidmFsaWRhdGlvbiIsInJ1bm5pbmciLCJldmVyeSIsIkJvb2xlYW4iLCJyZWNvdmVyYWJsZSIsInVwZGF0ZWRfYXQiLCJidXR0b24iLCJldmFsdWF0ZUFsbCIsImJ1dHRvbnMiLCJkaXNhYmxlZCIsImdldENsaWVudFJlY3RzIiwiZ2V0Q29tcHV0ZWRTdHlsZSIsInZpc2liaWxpdHkiLCJhdHRlbXB0Iiwid2FpdEZvclRpbWVvdXQiLCJNYXRoIiwibWluIiwiYmxvY2tpbmdfZmluZGluZ3MiLCJiZWZvcmVSZXZpZXciLCJwcmVmbGlnaHQiLCJ3YXJuaW5ncyIsImZpcnN0Iiwic3RhcnRlZFdhbGwiLCJhcHByb3ZhbFJlc3BvbnNlIiwid2FpdEZvclJlc3BvbnNlIiwiYXBwcm92ZWQiLCJyZWNlaXB0IiwiYWZ0ZXJSZXZpZXciLCJwcm9vZiIsInNuYXBzaG90SWQiLCJyZXF1ZXN0UHJvamVjdCIsInN1Ym1pdHRlZCIsImZpbmlzaGVkV2FsbCIsImNvbW1pdHRlZEF0IiwiY29tbWl0dGVkIiwiY29tbWl0V2FybmluZ1JldmlldyIsIm1hbnVhbFdhcm5pbmdBcHByb3ZhbCIsImFwcHJvdmFsSWRlbnRpdHkiLCJhcHByb3ZhbCIsIl9hd2FpdCRyZWFkUHJvamVjdCRjbyIsIl9jb252ZXJzYXRpb24kZGF0YSIsIl9wcm9wb3NhbCRkYXRhIiwicHJvcG9zYWwiLCJ2YWxpZGF0aW9uX3Jlc3VsdCIsInZpc2libGUiLCJpbm5lclRleHQiLCJlcnJvciIsIl9sYXRlc3QkY29udGV4dCRhZ2VudCIsImxhdGVzdCIsIl9sYXRlc3QkY29udGV4dCRhZ2VudDIiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQzIiwiX2xhdGVzdCRzdGF0dXNlcyIsImNhbmRpZGF0ZSIsInByb3Bvc2FsX3R5cGUiLCJjaGFuZ2VzIiwiY2hhbmdlIiwib2JqZWN0X3R5cGUiLCJhcnJheUNvbnRhaW5pbmciLCJyZXZpZXdBY3Rpb24iLCJyZXZpZXdPbmx5IiwicHJvcG9zYWxUeXBlIiwiYXBwbHlSZXNwb25zZSIsInRvQmVFbmFibGVkIiwiYXBwbGllZCIsImFkZCIsIl9hbWVuZGVkJGNvbnRleHQkYWdlbiIsImFtZW5kZWQiLCJfY3VycmVudCRjb250ZXh0JGFnZW4iLCJjdXJyZW50IiwiZnVsZmlsbCIsImdldEJ5VGl0bGUiLCJnZXRCeUxhYmVsIiwidG9CZURpc2FibGVkIiwidW5yb3V0ZSIsInRvSGF2ZUNvdW50IiwiY2F0YWxvZyIsInRlY2hub2xvZ3lfY291bnQiLCJ0ZXN0SW5mbyIsImVycm9ycyIsInN0YXJ0UmVxdWVzdCIsIndhaXRGb3JSZXF1ZXN0IiwiX3JlcXVlc3QkcG9zdERhdGFKU09OMiIsInN1Ym1pdCIsInJlcXVlc3RlZCIsIndpemFyZF9jb250ZXh0IiwidGVjaG5vbG9naWVzIiwiX2F3YWl0JHJlYWRQcm9qZWN0JGNvMiIsInBlbmRpbmciLCJjb250aW51aXR5IiwiYXJ0aWZhY3RzIiwiZmluaXNoZWQiLCJjaGVjayIsInNlbGVjdE9wdGlvbiIsInJlamVjdHMiLCJ0b1Rocm93IiwiZmluZGluZ3MiLCJjb2RlIiwidG9Db250YWluIiwiYXJ0aWZhY3RfY2hlY2tzIiwicmVxdWlyZWQiLCJwcm9maWxlX3ZhbHVlcyIsImRldmljZVNvdXJjZSIsInRvSGF2ZVByb3BlcnR5IiwibmF0aXZlVGVjaG5vbG9neSIsInByb2ZpbGVfZmluZGluZ3MiLCJmaW5kaW5nIiwiZXZpZGVuY2VSZXZpZXciLCJ0b0hhdmVBdHRyaWJ1dGUiLCJSZWdFeHAiLCJzaW11bGF0aW9uIiwicmF0ZV9yZXZpZXdfcHJvcG9zYWxzIiwiaTJjIiwicGFyYW1ldGVyX3Byb3ZlbmFuY2UiLCJpbnRlcmZhY2VzIiwiZG9tYWluIiwidW5pdCIsInN0YXJ0Q2FwdHVyZWRMYXJnZVdpemFyZCIsIm9yaWdpbmFsIiwiaW1wb3J0IiwibWV0YSIsIm1ldGFkYXRhIiwicGFyc2UiLCJiYXNlbGluZSIsInByb21wdCIsInJlcGxhY2UiLCJwb3N0Iiwib3BlcmF0aW9uX2lkIiwidGFyZ2V0IiwibGFyZ2VQYXJhbWV0ZXJTY2VuYXJpb3MiLCJsaW5fYml0cmF0ZV9icHMiLCJwYXJhbWV0ZXJSZXR1cm5SZXZpZXdzIiwicmV2aWV3U2VlZCIsImxpbiIsImNhbl9mZCIsImV0aGVybmV0IiwiZXhjbHVkZWRTaWduYWxJZHMiLCJmaXh0dXJlIiwicmVxdWVzdF9zaGEyNTYiLCJ0eXBlIiwiX2NvbnRpbnVpdHkkcmV2aWV3T25sIiwiY292ZXJhZ2UiLCJjeWNsZXMiLCJncmFwaCIsImNsdXN0ZXJfaWQiLCJuZXR3b3JrX2lkIiwibmV0d29ya19sYWJlbCIsImJ1c19uYW1lIiwiY29udHJvbGxlcnMiLCJlY3UiLCJzZW5zb3JzIiwiYWN0dWF0b3JzIiwiaG1pX3JvdXRlcyIsInByb2plY3RfbmFtZSIsInNjb3BlX2lkcyIsIm1vZGUiLCJwcm9jZXNzX2lkcyIsInRhc2siLCJvcmlnaW5hbE5ldHdvcmtzIiwiYW1lbmQiLCJleHBhbmQiLCJzeXN0ZW1fb3duZXJfaWQiLCJzZW5zb3JOZXR3b3JrIiwidG9wb2xvZ3kiLCJsb2NhbEVkZ2UiLCJlZGdlcyIsImVkZ2UiLCJwaHlzaWNhbE5ldHdvcmtJZCIsImJ1cyIsInJvdXRpbmdNZXRhZGF0YSIsInRvQ29udGFpbkVxdWFsIiwib2JqZWN0Q29udGFpbmluZyIsImFwcHJvdmFsU3RhdGUiLCJwcm90b2NvbCIsInNpZGUiLCJoYXJkd2FyZUlkIiwibm9kZSIsImVuZ2luZWVyaW5nSWQiLCJwb3J0cyIsInR4cngiLCJoYXNUZXh0Iiwic2VsZWN0ZWQiLCJ0b0JlQ2hlY2tlZCIsInVuY2hlY2siLCJfcmVxdWVzdCRwb3N0RGF0YUpTT04zIiwic3lzdGVtX2NsdXN0ZXJfYXNzaWdubWVudHMiLCJjbHVzdGVyIiwiX2NsdXN0ZXIkZnVuY3Rpb25hbF9yIiwiZnVuY3Rpb25hbF9yb3V0ZXMiLCJleGNsdWRlZF9zaWduYWxzIiwicmV2aWV3IiwiYXBwbHkiLCJnZWFyYm94IiwiZW1vdG9yIl0sInNvdXJjZXMiOlsid2l6YXJkLnNwZWMudHMiXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgdGVzdCwgZXhwZWN0LCB0eXBlIFBhZ2UgfSBmcm9tICdwbGF5d3JpZ2h0L3Rlc3QnO1xyXG5pbXBvcnQgeyByZWFkRmlsZSB9IGZyb20gJ25vZGU6ZnMvcHJvbWlzZXMnO1xyXG5pbXBvcnQgeyByYW5kb21VVUlEIH0gZnJvbSAnbm9kZTpjcnlwdG8nO1xyXG5pbXBvcnQgeyBleGVjRmlsZVN5bmMgfSBmcm9tICdub2RlOmNoaWxkX3Byb2Nlc3MnO1xyXG5pbXBvcnQgeyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nLCBXSVpBUkRfU1RFUFMsIFdJWkFSRF9ET05FIH0gZnJvbSAnLi9zdXBwb3J0L3dpemFyZC1wcm9ncmVzcy13YXRjaGRvZyc7XHJcbmltcG9ydCB7IHJldmlld1ZpcnR1YWxUcmFuc3BvcnRzIH0gZnJvbSAnLi9zdXBwb3J0L25hdGl2ZS10cmFuc3BvcnQtZml4dHVyZXMnO1xyXG5cclxuY29uc3Qgc3RlcHMgPSBXSVpBUkRfU1RFUFM7XHJcbmNvbnN0IGRvbmUgPSBXSVpBUkRfRE9ORTtcclxudHlwZSBXcml0ZVRpbWluZyA9IHsgdXJsOiBzdHJpbmc7IHN0YXJ0ZWQ6IG51bWJlcjsgZHVyYXRpb25fbXM/OiBudW1iZXI7IHN0YXR1cz86IG51bWJlcjsgZmFpbHVyZT86IHN0cmluZyB9O1xyXG5jb25zdCB3cml0ZVRpbWluZ3MgPSBuZXcgTWFwPHN0cmluZywgV3JpdGVUaW1pbmdbXT4oKTtcclxuY29uc3Qgd29ya2Zsb3dQYWdlRmFpbHVyZXMgPSBuZXcgV2Vha01hcDxQYWdlLCBzdHJpbmdbXT4oKTtcclxuY29uc3QgcHJvZ3Jlc3NNaWxlc3RvbmVzID0gbmV3IE1hcDxzdHJpbmcsIHVua25vd25bXT4oKTtcclxuXHJcbnRlc3QuYmVmb3JlRWFjaChhc3luYyAoeyBwYWdlIH0sIGluZm8pID0+IHtcclxuICBjb25zdCByb3dzOiBXcml0ZVRpbWluZ1tdID0gW107XHJcbiAgd3JpdGVUaW1pbmdzLnNldChpbmZvLnRlc3RJZCwgcm93cyk7XHJcbiAgd29ya2Zsb3dQYWdlRmFpbHVyZXMuc2V0KHBhZ2UsIFtdKTtcclxuICBwcm9ncmVzc01pbGVzdG9uZXMuc2V0KGluZm8udGVzdElkLCBbXSk7XHJcbiAgY29uc3QgcmVxdWVzdHMgPSBuZXcgTWFwPG9iamVjdCwgV3JpdGVUaW1pbmc+KCk7XHJcbiAgcGFnZS5vbigncmVxdWVzdCcsIHJlcXVlc3QgPT4ge1xyXG4gICAgaWYgKCFbJ1BPU1QnLCAnUFVUJywgJ1BBVENIJywgJ0RFTEVURSddLmluY2x1ZGVzKHJlcXVlc3QubWV0aG9kKCkpKSByZXR1cm47XHJcbiAgICBjb25zdCByb3cgPSB7IHVybDogcmVxdWVzdC51cmwoKSwgc3RhcnRlZDogRGF0ZS5ub3coKSB9O1xyXG4gICAgcm93cy5wdXNoKHJvdyk7IHJlcXVlc3RzLnNldChyZXF1ZXN0LCByb3cpO1xyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3Jlc3BvbnNlJywgcmVzcG9uc2UgPT4ge1xyXG4gICAgY29uc3Qgcm93ID0gcmVxdWVzdHMuZ2V0KHJlc3BvbnNlLnJlcXVlc3QoKSk7XHJcbiAgICBpZiAocm93KSByb3cuc3RhdHVzID0gcmVzcG9uc2Uuc3RhdHVzKCk7XHJcbiAgICBpZiAocmVzcG9uc2Uuc3RhdHVzKCkgPT09IDQxMyAmJiAvXlxcL2FwaVxcL2VuZ2luZWVyaW5nXFwvd29ya2Zsb3coPzpcXC98JCkvLnRlc3QobmV3IFVSTChyZXNwb25zZS51cmwoKSkucGF0aG5hbWUpKSB7XHJcbiAgICAgIHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSEucHVzaChgSFRUUCA0MTM6ICR7cmVzcG9uc2UudXJsKCl9YCk7XHJcbiAgICB9XHJcbiAgfSk7XHJcbiAgcGFnZS5vbigncmVxdWVzdGZpbmlzaGVkJywgcmVxdWVzdCA9PiB7XHJcbiAgICBjb25zdCByb3cgPSByZXF1ZXN0cy5nZXQocmVxdWVzdCk7XHJcbiAgICBpZiAocm93KSByb3cuZHVyYXRpb25fbXMgPSBEYXRlLm5vdygpIC0gcm93LnN0YXJ0ZWQ7XHJcbiAgfSk7XHJcbiAgcGFnZS5vbigncmVxdWVzdGZhaWxlZCcsIHJlcXVlc3QgPT4ge1xyXG4gICAgY29uc3Qgcm93ID0gcmVxdWVzdHMuZ2V0KHJlcXVlc3QpO1xyXG4gICAgaWYgKHJvdykgeyByb3cuZHVyYXRpb25fbXMgPSBEYXRlLm5vdygpIC0gcm93LnN0YXJ0ZWQ7IHJvdy5mYWlsdXJlID0gcmVxdWVzdC5mYWlsdXJlKCk/LmVycm9yVGV4dDsgfVxyXG4gIH0pO1xyXG59KTtcclxuXHJcbnRlc3QuYWZ0ZXJFYWNoKGFzeW5jICh7IHBhZ2UgfSwgaW5mbykgPT4ge1xuICBhd2FpdCBpbmZvLmF0dGFjaCgnd3JpdGUtcmVxdWVzdC10aW1pbmdzJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh3cml0ZVRpbWluZ3MuZ2V0KGluZm8udGVzdElkKSB8fCBbXSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgYXdhaXQgaW5mby5hdHRhY2goJ3dvcmtmbG93LXByb2dyZXNzLWJvdW5kYXJpZXMnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHByb2dyZXNzTWlsZXN0b25lcy5nZXQoaW5mby50ZXN0SWQpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd29ya2Zsb3ctcGFnZS1mYWlsdXJlcycsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICB3cml0ZVRpbWluZ3MuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBwcm9ncmVzc01pbGVzdG9uZXMuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBleHBlY3Qod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpLCAnVGhlIHVuZGVybHlpbmcgZW5naW5lZXJpbmcgcGFnZSBtdXN0IHJlbWFpbiByZWFkYWJsZSB0aHJvdWdob3V0IHJlbG9hZCBhbmQgcmVjb3ZlcnkuJykudG9FcXVhbChbXSk7XG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnaGVhZGluZycsIHtuYW1lOiAnRGllIEFuc2ljaHQga29ubnRlIG5pY2h0IGdlbGFkZW4gd2VyZGVuLicsIGV4YWN0OiB0cnVlfSksXG4gICAgJ0EgY3Jhc2hlZCBwYXJhbWV0ZXIgb3IgZW5naW5lZXJpbmcgcGFnZSBtdXN0IG5ldmVyIGNvdW50IGFzIGEgc3VjY2Vzc2Z1bCB3aXphcmQgZGV0b3VyLicpLm5vdC50b0JlVmlzaWJsZSgpO1xufSk7XHJcblxyXG5hc3luYyBmdW5jdGlvbiBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2U6IFBhZ2UpIHtcbiAgZXhwZWN0KHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSwgJ0Egd29ya2luZyB3aXphcmQgb3ZlcmxheSBtdXN0IG5vdCBjb25jZWFsIGEgd29ya2Zsb3cgSFRUUCA0MTMuJykudG9FcXVhbChbXSk7XHJcbiAgZXhwZWN0KGF3YWl0IHBhZ2UuZ2V0QnlUZXh0KCdFbmdpbmVlcmluZy1BUEkgbmljaHQgZXJyZWljaGJhcicsIHsgZXhhY3Q6IHRydWUgfSkuaXNWaXNpYmxlKCksXG4gICAgJ1RoZSB1bmRlcmx5aW5nIGVuZ2luZWVyaW5nIHBhZ2UgbXVzdCBub3Qgc2hvdyBpdHMgQVBJIGVycm9yIHZpZXcuJykudG9CZShmYWxzZSk7XG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnaGVhZGluZycsIHtuYW1lOiAnRGllIEFuc2ljaHQga29ubnRlIG5pY2h0IGdlbGFkZW4gd2VyZGVuLicsIGV4YWN0OiB0cnVlfSkpLm5vdC50b0JlVmlzaWJsZSgpO1xufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVhZFByb2plY3QocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBwYXRoOiBzdHJpbmcpIHtcclxuICBjb25zdCByZXN1bHQgPSBhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KHBhdGgsIHsgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiA2MF8wMDAgfSk7XHJcbiAgdHJ5IHtcclxuICAgIGlmICghcmVzdWx0Lm9rKCkpIHRocm93IG5ldyBFcnJvcihgJHtwYXRofTogSFRUUCAke3Jlc3VsdC5zdGF0dXMoKX0gJHsoYXdhaXQgcmVzdWx0LnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgICByZXR1cm4gYXdhaXQgcmVzdWx0Lmpzb24oKTtcclxuICB9IGZpbmFsbHkge1xyXG4gICAgLy8gUGxheXdyaWdodCBvdGhlcndpc2UgcmV0YWlucyBldmVyeSBwb2xsZWQgcmVzcG9uc2UgdW50aWwgY29udGV4dCB0ZWFyZG93bi5cclxuICAgIC8vIEtlZXAgdGhlIHBhcnNlZCBldmlkZW5jZSwgcmVsZWFzZSBpdHMgZHVwbGljYXRlIHRyYW5zcG9ydCBib2R5IGltbWVkaWF0ZWx5LlxyXG4gICAgYXdhaXQgcmVzdWx0LmRpc3Bvc2UoKTtcclxuICB9XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHJlYWRXYXJuaW5nUmV2aWV3U3RhdGUocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nKSB7XHJcbiAgY29uc3QgYXV0aG9yaXR5ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgY29uc3QgcGFyYW1ldGVycyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnKTtcclxuICBjb25zdCB2ZXJpZmllZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gIGV4cGVjdChwYXJhbWV0ZXJzLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgZXhwZWN0KGF1dGhvcml0eS5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xyXG4gIGV4cGVjdCh2ZXJpZmllZC5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xyXG4gIGZvciAoY29uc3QgZmllbGQgb2YgWydydW5faWQnLCAncmVxdWVzdF9yZXZpc2lvbiddKVxyXG4gICAgZXhwZWN0KHZlcmlmaWVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5bZmllbGRdKS50b0JlKGF1dGhvcml0eS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uW2ZpZWxkXSk7XHJcbiAgcmV0dXJuIHsgcHJvamVjdF9pZDogdmVyaWZpZWQucHJvamVjdF9pZCwgc3RhdHVzZXM6IHZlcmlmaWVkLnN0YXR1c2VzLFxyXG4gICAgY29udGV4dDogeyBhZ2VudF9leGVjdXRpb246IHsgcnVuX2lkOiB2ZXJpZmllZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkLFxyXG4gICAgICByZXF1ZXN0X3JldmlzaW9uOiB2ZXJpZmllZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucmVxdWVzdF9yZXZpc2lvbiB9IH0sXHJcbiAgICBwYXJhbWV0ZXJzOiB7IHByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsOiBwYXJhbWV0ZXJzLnBhcmFtZXRlcnMucHJlZmxpZ2h0X3dhcm5pbmdfYXBwcm92YWwgfSB9O1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiBvcGVuV2l6YXJkKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZykge1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9lbmdpbmVlcmluZz9hc3Npc3RhbnQ9cHJvamVjdCZwcm9qZWN0PSR7cHJvamVjdH1gLCB7IHdhaXRVbnRpbDogJ2xvYWQnIH0pO1xyXG4gIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZykudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2UpO1xyXG4gIHJldHVybiBkaWFsb2c7XHJcbn1cclxuXHJcbnRlc3QoJ3Byb2plY3QgbmFtaW5nIGZvcm0gY2FyZHMgdXNlIHRoZSBmdWxsIHdpemFyZCB3aWR0aCBAbGF5b3V0JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCAnbmlzLWUyZS1wcm9qZWN0LW5hbWUtbGF5b3V0LScgKyByYW5kb21VVUlEKCkpO1xyXG4gIGNvbnN0IHN0ZXAgPSBkaWFsb2cubG9jYXRvcignZmllbGRzZXQuYWdlbnQtcHJvamVjdC1uYW1lLXN0ZXAnKTtcclxuICBhd2FpdCBleHBlY3Qoc3RlcCkudG9CZVZpc2libGUoKTtcclxuICBjb25zdCBzdGVwV2lkdGggPSBhd2FpdCBzdGVwLmV2YWx1YXRlKGVsZW1lbnQgPT4gZWxlbWVudC5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKS53aWR0aCk7XHJcbiAgY29uc3QgY2FyZHMgPSBhd2FpdCBzdGVwLmxvY2F0b3IoJzpzY29wZSA+IGxhYmVsJykuYWxsKCk7XHJcbiAgZXhwZWN0KGNhcmRzKS50b0hhdmVMZW5ndGgoNCk7XHJcbiAgZm9yIChjb25zdCBjYXJkIG9mIGNhcmRzKSB7XHJcbiAgICBjb25zdCB3aWR0aCA9IGF3YWl0IGNhcmQuZXZhbHVhdGUoZWxlbWVudCA9PiBlbGVtZW50LmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpLndpZHRoKTtcclxuICAgIGV4cGVjdCh3aWR0aCkudG9CZUdyZWF0ZXJUaGFuKHN0ZXBXaWR0aCAqIDAuODUpO1xyXG4gIH1cclxufSk7XHJcblxyXG5hc3luYyBmdW5jdGlvbiBhbGxPYmplY3RzKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcmVzb3VyY2U6IHN0cmluZykge1xyXG4gIGNvbnN0IGl0ZW1zOiBhbnlbXSA9IFtdO1xyXG4gIGZvciAobGV0IG9mZnNldCA9IDA7IDsgb2Zmc2V0ICs9IDUwMCkge1xyXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy8ke3Jlc291cmNlfT9saW1pdD01MDAmb2Zmc2V0PSR7b2Zmc2V0fWApO1xyXG4gICAgaXRlbXMucHVzaCguLi5yZXNwb25zZS5pdGVtcyk7XHJcbiAgICBpZiAocmVzcG9uc2UuaXRlbXMubGVuZ3RoIDwgNTAwKSByZXR1cm4gaXRlbXM7XHJcbiAgfVxyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiByZXN0YXJ0QXBwbGljYXRpb24ocGFnZTogUGFnZSwgY3Jhc2ggPSBmYWxzZSkge1xyXG4gIGNvbnN0IGNvbnRhaW5lciA9IHByb2Nlc3MuZW52Lk5JU19FMkVfQVBQX0NPTlRBSU5FUiE7XHJcbiAgZXhwZWN0KGNvbnRhaW5lcikudG9NYXRjaCgvXm5pcy1lMmUtYXBwLVthLWYwLTldKyQvKTtcclxuICBjb25zdCBkb2NrZXIgPSBwcm9jZXNzLmVudi5OSVNfVEVTVF9ET0NLRVIgfHwgJ2RvY2tlcic7XHJcbiAgY29uc3QgbGFiZWwgPSBleGVjRmlsZVN5bmMoZG9ja2VyLCBbJ2luc3BlY3QnLCBjb250YWluZXIsICctLWZvcm1hdCcsICd7e2luZGV4IC5Db25maWcuTGFiZWxzIFwibmV0d29ya2lzLnRlc3RcIn19J10sIHsgZW5jb2Rpbmc6ICd1dGY4JyB9KS50cmltKCk7XHJcbiAgZXhwZWN0KGxhYmVsKS50b0JlKCdkaXNwb3NhYmxlJyk7XHJcbiAgZXhlY0ZpbGVTeW5jKGRvY2tlciwgWydyZXN0YXJ0JywgLi4uKGNyYXNoID8gWyctdCcsICcwJ10gOiBbXSksIGNvbnRhaW5lcl0sIHsgdGltZW91dDogNjBfMDAwIH0pO1xyXG4gIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcclxuICAgIHRyeSB7IHJldHVybiAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9yZWFkeScsIHsgdGltZW91dDogMjAwMCB9KSkub2soKTsgfSBjYXRjaCB7IHJldHVybiBmYWxzZTsgfVxyXG4gIH0sIHsgdGltZW91dDogMTIwXzAwMCB9KS50b0JlKHRydWUpO1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBleHBlY3RlZDogUmVjb3JkPHN0cmluZywgdW5rbm93bj4pIHtcclxuICBjb25zdCBbaGFyZHdhcmUsIGZ1bmN0aW9ucywgbWVzc2FnZXMsIHNpZ25hbHNdID0gYXdhaXQgUHJvbWlzZS5hbGwoXHJcbiAgICBbJ2hhcmR3YXJlLW5vZGVzJywgJ2Z1bmN0aW9ucycsICdtZXNzYWdlcycsICdzaWduYWxzJ10ubWFwKHJlc291cmNlID0+IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgcmVzb3VyY2UpKSk7XHJcbiAgY29uc3Qgbm9kZXMgPSBuZXcgTWFwKGhhcmR3YXJlLm1hcChpdGVtID0+IFtpdGVtLmlkLCBpdGVtXSkpO1xyXG4gIGNvbnN0IGZ1bmN0aW9uc0J5SWQgPSBuZXcgTWFwKGZ1bmN0aW9ucy5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBtZXNzYWdlc0J5SWQgPSBuZXcgTWFwKG1lc3NhZ2VzLm1hcChpdGVtID0+IFtpdGVtLmlkLCBpdGVtXSkpO1xyXG4gIGNvbnN0IGNvbnRyYWN0czogUmVjb3JkPHN0cmluZywgdW5rbm93bj4gPSB7fTtcclxuICBmb3IgKGNvbnN0IHNpZ25hbCBvZiBzaWduYWxzKSB7XHJcbiAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXNCeUlkLmdldChzaWduYWwubWVzc2FnZV9pZCk7XHJcbiAgICBleHBlY3QobWVzc2FnZSkudG9CZVRydXRoeSgpO1xyXG4gICAgY29uc3QgcmVmZXJlbmNlID0gbWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QucHJvZHVjZXJfcmVmO1xyXG4gICAgY29uc3QgZm4gPSBmdW5jdGlvbnNCeUlkLmdldChyZWZlcmVuY2UpO1xyXG4gICAgY29uc3Qgb3duZXIgPSBub2Rlcy5nZXQocmVmZXJlbmNlKSB8fCAoZm4gJiYgbm9kZXMuZ2V0KGZuLmhhcmR3YXJlX25vZGVfaWQpKTtcclxuICAgIGNvbnN0IHByb2R1Y2VyID0gb3duZXI/LmRldmljZV90eXBlID09PSAnR2F0ZXdheScgPyAnJGdhdGV3YXknIDogKG5vZGVzLmdldChyZWZlcmVuY2UpIHx8IGZuKT8ubmFtZTtcclxuICAgIGV4cGVjdChwcm9kdWNlcikudG9CZVRydXRoeSgpO1xyXG4gICAgY29uc3Qga2V5ID0gW3Byb2R1Y2VyLCBtZXNzYWdlLm5hbWUsIHNpZ25hbC5uYW1lXS5qb2luKCcgOjogJyk7XHJcbiAgICBleHBlY3QoY29udHJhY3RzW2tleV0sICdTZW1hbnRpYyBzaWduYWwgaWRlbnRpdHkgbXVzdCBiZSB1bmlxdWU6ICcgKyBrZXkpLnRvQmVVbmRlZmluZWQoKTtcclxuICAgIGNvbnRyYWN0c1trZXldID0ge1xyXG4gICAgICAuLi5PYmplY3QuZnJvbUVudHJpZXMoWydzdGFydF9iaXQnLCAnbGVuZ3RoX2JpdHMnLCAnZGF0YV90eXBlJywgJ2ZhY3RvcicsICdvZmZzZXRfdmFsdWUnLFxyXG4gICAgICAgICd1bml0JywgJ21pbl92YWx1ZScsICdtYXhfdmFsdWUnLCAnYnl0ZV9vcmRlciddLm1hcChmaWVsZCA9PiBbZmllbGQsIHNpZ25hbFtmaWVsZF0gPz8gbnVsbF0pKSxcclxuICAgICAgZW51bV92YWx1ZXM6IHNpZ25hbC5kYXRhPy5lbnVtX3ZhbHVlcyA/PyBudWxsLFxyXG4gICAgICBzZW1hbnRpY190eXBlOiBzaWduYWwuc2VtYW50aWM/LnNlbWFudGljX3R5cGUgPz8gbnVsbCxcclxuICAgICAgZ2VuZXJhdGlvbl9yb2xlOiBzaWduYWwuY29uZmlndXJhdGlvbj8uZ2VuZXJhdGlvbl9yb2xlID8/IG51bGwsXHJcbiAgICB9O1xyXG4gIH1cclxuICBleHBlY3QoY29udHJhY3RzLCAnRXZlcnkgb3JpZ2luYWwgc2lnbmFsIGFuZCBpdHMgZXhwbGljaXQgZW5jb2RpbmcgbXVzdCBzdXJ2aXZlIGdlbmVyYXRpb24uJykudG9FcXVhbChleHBlY3RlZCk7XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHZlcmlmeUFydGlmYWN0cyhwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIG1pbmltdW1DYW5vbmljYWxTaWduYWxzOiBudW1iZXIsIGludGVybmFsQ29udHJvbGxlcj86IHN0cmluZyxcbiAgZXhwZWN0ZWRQYXJhbWV0ZXJzPzogUmVjb3JkPHN0cmluZywgdW5rbm93bj4sIGV4cGVjdGVkTmF0aXZlUmF0ZXM/OiBSZWNvcmQ8c3RyaW5nLCBSZWNvcmQ8c3RyaW5nLCBudW1iZXI+Pikge1xuICAvLyBUaGUgY29tcGxldGVkIG1vZGVsIGlzIHN0YWJsZTsgdGhlc2UgaW5kZXBlbmRlbnQgcmVhZHMgbmVlZCBubyBzZXJpYWwgd2FpdHMuXHJcbiAgY29uc3QgW3dvcmtmbG93LCBqb2JMaXN0LCBzbmFwc2hvdHMsIHNpZ25hbHMsIG1lc3NhZ2VzXSA9IGF3YWl0IFByb21pc2UuYWxsKFtcclxuICAgIHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpLFxyXG4gICAgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSxcclxuICAgIHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3NuYXBzaG90cycpLFxyXG4gICAgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnc2lnbmFscycpLFxyXG4gICAgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnbWVzc2FnZXMnKSxcclxuICBdKTtcclxuICBleHBlY3QoT2JqZWN0LmtleXMod29ya2Zsb3cuc3RhdHVzZXMpLnNvcnQoKSkudG9FcXVhbChbLi4uc3RlcHNdLnNvcnQoKSk7XHJcbiAgZm9yIChjb25zdCBzdGVwIG9mIHN0ZXBzKSBleHBlY3QoZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXNbc3RlcF0pLCBgJHtzdGVwfTogJHt3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXX1gKS50b0JlVHJ1dGh5KCk7XHJcbiAgY29uc3Qgam9icyA9IGpvYkxpc3Quam9icztcclxuICBleHBlY3Qoam9icykudG9IYXZlTGVuZ3RoKDEpO1xyXG4gIGV4cGVjdChqb2JzWzBdLnN0YXR1cykudG9CZSgnY29tcGxldGVkJyk7XHJcbiAgY29uc3Qgc25hcHNob3QgPSBzbmFwc2hvdHMuc2ltdWxhdGlvbnMuZmluZCgoaXRlbTogeyBqb2JfaWQ6IHN0cmluZyB9KSA9PiBpdGVtLmpvYl9pZCA9PT0gam9ic1swXS5pZCk7XHJcbiAgZXhwZWN0KHNuYXBzaG90KS50b0JlVHJ1dGh5KCk7XHJcbiAgY29uc3QgZnVsbCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3NpbXVsYXRpb24tc25hcHNob3RzLyR7c25hcHNob3QuaWR9YCk7XHJcbiAgaWYgKGV4cGVjdGVkUGFyYW1ldGVycykge1xuICAgIGNvbnN0IHsgZGF0YV9iaXRyYXRlLCBjYW5fZmRfZGF0YV9wcmVzY2FsZXIsIC4uLnJ1bnRpbWVQYXJhbWV0ZXJzIH0gPSBleHBlY3RlZFBhcmFtZXRlcnM7XHJcbiAgICBleHBlY3QoZnVsbC5jb25maWd1cmF0aW9uLnBhcmFtZXRlcnMpLnRvTWF0Y2hPYmplY3QocnVudGltZVBhcmFtZXRlcnMpO1xyXG4gICAgY29uc3QgY2FuRmROZXR3b3JrcyA9IGZ1bGwuY29uZmlndXJhdGlvbi5uZXR3b3Jrcy5maWx0ZXIoKG5ldHdvcms6IGFueSkgPT4gbmV0d29yay50ZWNobm9sb2d5ID09PSAnY2FuX2ZkJyk7XHJcbiAgICBleHBlY3QoY2FuRmROZXR3b3Jrcy5sZW5ndGgsICdUaGUgZWRpdGVkIENBTi1GRCBjb25maWd1cmF0aW9uIG11c3QgcmVhY2ggYSBwaHlzaWNhbCBzaW11bGF0aW9uIG5ldHdvcmsuJykudG9CZUdyZWF0ZXJUaGFuKDApO1xyXG4gICAgZm9yIChjb25zdCBuZXR3b3JrIG9mIGNhbkZkTmV0d29ya3MpIGV4cGVjdChuZXR3b3JrKS50b01hdGNoT2JqZWN0KHsgZGF0YV9iaXRyYXRlLCBjYW5fZmRfZGF0YV9wcmVzY2FsZXIgfSk7XG4gIH1cbiAgaWYgKGV4cGVjdGVkTmF0aXZlUmF0ZXMpIHtcbiAgICBmb3IgKGNvbnN0IFt0ZWNobm9sb2d5LCByYXRlc10gb2YgT2JqZWN0LmVudHJpZXMoZXhwZWN0ZWROYXRpdmVSYXRlcykpIHtcbiAgICAgIGNvbnN0IG5ldHdvcmtzID0gZnVsbC5jb25maWd1cmF0aW9uLm5ldHdvcmtzLmZpbHRlcigobmV0d29yazogYW55KSA9PiBuZXR3b3JrLnRlY2hub2xvZ3kgPT09IHRlY2hub2xvZ3kpO1xuICAgICAgZXhwZWN0KG5ldHdvcmtzLmxlbmd0aCwgYFNhdmVkICR7dGVjaG5vbG9neX0gcmF0ZXMgbXVzdCByZWFjaCB0aGUgZnJvemVuIHNpbXVsYXRpb24uYCkudG9CZUdyZWF0ZXJUaGFuKDApO1xuICAgICAgZm9yIChjb25zdCBuZXR3b3JrIG9mIG5ldHdvcmtzKSBleHBlY3QobmV0d29yaykudG9NYXRjaE9iamVjdChyYXRlcyk7XG4gICAgfVxuICB9XG4gIGNvbnN0IGFzc2Vzc21lbnQgPSBmdWxsLnJlc3VsdC5hc3Nlc3NtZW50O1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnNjb3BlX21vZGUpLnRvQmUoJ0FMTCcpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLmNvbXBsZXRlKS50b0JlKHRydWUpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LmNvbmZvcm1hbmNlKS50b0JlKCdQQVNTJyk7XHJcbiAgZXhwZWN0KGFzc2Vzc21lbnQuZmFpbGVkX3JvdXRlX2NvdW50KS50b0JlKDApO1xyXG4gIGV4cGVjdChzaWduYWxzLmxlbmd0aCwgJ1RoZSBmdWxsIGNhbm9uaWNhbCBzaWduYWwgaW52ZW50b3J5IG11c3Qgc3Vydml2ZSBnZW5lcmF0aW9uLicpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwobWluaW11bUNhbm9uaWNhbFNpZ25hbHMpO1xyXG4gIGNvbnN0IGV4Y2x1ZGVkID0gYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS50cmFuc3BvcnRfZXhjbHVzaW9ucyA/PyBbXTtcclxuICBmb3IgKGNvbnN0IGl0ZW0gb2YgZXhjbHVkZWQpIHtcclxuICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKHJvdyA9PiByb3cuaWQgPT09IGl0ZW0ubWVzc2FnZV9pZCk7XHJcbiAgICBleHBlY3QobWVzc2FnZSwgYEV4Y2x1ZGVkIG1lc3NhZ2UgJHtpdGVtLm1lc3NhZ2VfaWR9IG11c3QgZXhpc3QuYCkudG9CZVRydXRoeSgpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5yb3V0aW5nLmVuYWJsZWQpLnRvQmUoZmFsc2UpO1xyXG4gICAgY29uc3QgY29udHJhY3QgPSBtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdDtcclxuICAgIGV4cGVjdChjb250cmFjdC5jb25zdW1lcl9yZWZzKS50b0VxdWFsKFtdKTtcclxuICAgIGV4cGVjdChpdGVtLnJlYXNvbl9jb2RlKS50b0JlKGNvbnRyYWN0LnJvbGUgPT09ICdJTlRFUk5BTF9TVEFURSdcclxuICAgICAgPyAnSU5URVJOQUxfU1RBVEVfTk9UX1JPVVRFRCcgOiAnRVhQTElDSVRfRlVOQ1RJT05fT1VUUFVUX05PVF9ST1VURUQnKTtcclxuICB9XHJcbiAgaWYgKGludGVybmFsQ29udHJvbGxlcikge1xyXG4gICAgY29uc3Qgbm9kZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gICAgY29uc3QgY29udHJvbGxlciA9IG5vZGVzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09IGludGVybmFsQ29udHJvbGxlcik7XHJcbiAgICBleHBlY3QoZXhjbHVkZWQubGVuZ3RoKS50b0JlR3JlYXRlclRoYW4oMCk7XHJcbiAgICBmb3IgKGNvbnN0IGl0ZW0gb2YgZXhjbHVkZWQpIHtcclxuICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzLmZpbmQocm93ID0+IHJvdy5pZCA9PT0gaXRlbS5tZXNzYWdlX2lkKTtcclxuICAgICAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0KS50b01hdGNoT2JqZWN0KHsgcm9sZTogJ0lOVEVSTkFMX1NUQVRFJywgc2NvcGU6ICdJTlRFUk5BTCcsIHByb2R1Y2VyX3JlZjogY29udHJvbGxlci5pZCwgY29uc3VtZXJfcmVmczogW10gfSk7XHJcbiAgICB9XHJcbiAgfVxyXG4gIGNvbnN0IGV4Y2x1ZGVkU2lnbmFscyA9IG5ldyBTZXQoZXhjbHVkZWQuZmxhdE1hcCgoaXRlbTogeyBzaWduYWxfaWRzOiBzdHJpbmdbXSB9KSA9PiBpdGVtLnNpZ25hbF9pZHMpKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQsICdBTEwgbXVzdCBvYnNlcnZlIGV2ZXJ5IGNhbm9uaWNhbCBzaWduYWwgd2l0aCBhIHRyYW5zcG9ydCBvYmxpZ2F0aW9uLicpLnRvQmUoc2lnbmFscy5sZW5ndGggLSBleGNsdWRlZFNpZ25hbHMuc2l6ZSk7XHJcbiAgZm9yIChjb25zdCBrZXkgb2YgWydtaXNzaW5nX29ic2VydmVkX3NpZ25hbF9pZHMnLCAnbWlzc2luZ19vYnNlcnZlZF9yb3V0ZV9pZHMnLCAnbWlzc2luZ19vYnNlcnZlZF9uZXR3b3JrX2lkcyddKSBleHBlY3QoYXNzZXNzbWVudFtrZXldKS50b0VxdWFsKFtdKTtcclxuICBjb25zdCB0cmFjZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL3NpbXVsYXRpb25zLyR7am9ic1swXS5pZH0vdHJhY2Utd2luZG93P2xpbWl0PTEwYCk7XHJcbiAgZXhwZWN0KHRyYWNlLmNvdW50KS50b0JlR3JlYXRlclRoYW4oMCk7XHJcbiAgZXhwZWN0KHRyYWNlLmV2ZW50cy5zb21lKChpdGVtOiB7IHNpZ25hbHM/OiB1bmtub3duW10gfSkgPT4gaXRlbS5zaWduYWxzICYmIE9iamVjdC5rZXlzKGl0ZW0uc2lnbmFscykubGVuZ3RoKSkudG9CZVRydXRoeSgpO1xyXG4gIHJldHVybiB7IHdvcmtmbG93LCBqb2I6IGpvYnNbMF0uaWQsIGFzc2Vzc21lbnQsIHBhcmFtZXRlcl9wcm9vZjogZXhwZWN0ZWRQYXJhbWV0ZXJzID8ge1xyXG4gICAgc2F2ZWQ6IGV4cGVjdGVkUGFyYW1ldGVycywgc2ltdWxhdGlvbl9yYXRlczogZnVsbC5jb25maWd1cmF0aW9uLm5ldHdvcmtzLm1hcCgobmV0d29yazogYW55KSA9PiAoe1xyXG4gICAgICB0ZWNobm9sb2d5OiBuZXR3b3JrLnRlY2hub2xvZ3ksIGJpdHJhdGU6IG5ldHdvcmsuYml0cmF0ZSxcclxuICAgICAgYXJiaXRyYXRpb25fYml0cmF0ZTogbmV0d29yay5hcmJpdHJhdGlvbl9iaXRyYXRlLCBkYXRhX2JpdHJhdGU6IG5ldHdvcmsuZGF0YV9iaXRyYXRlLFxyXG4gICAgICBoYXJkd2FyZV9ldmlkZW5jZTogbmV0d29yay5oYXJkd2FyZV9ldmlkZW5jZSxcclxuICAgIH0pKSxcclxuICB9IDogdW5kZWZpbmVkIH07XHJcbn1cclxuXHJcbnR5cGUgUGFyYW1ldGVyUmV0dXJuU2NlbmFyaW8gPSB7XG4gIHRlY2hub2xvZ3k6IHN0cmluZztcbiAgZmllbGRzOiBSZWNvcmQ8c3RyaW5nLCBzdHJpbmc+O1xuICBuYXRpdmU6IFJlY29yZDxzdHJpbmcsIG51bWJlcj47XG4gIGVkaXRGaWVsZHM/OiBzdHJpbmdbXTtcbn07XG5cbi8vIEV4ZXJjaXNlIHRoZSB1c2VyJ3MgZGV0b3VyLCBpbmNsdWRpbmcgcmVwZWF0ZWQgc2F2ZXMgaW4gYW4gZXhpc3RpbmcgcnVuLlxuLy8gUmVhZHMgaW5zcGVjdCByZWFsIHBlcnNpc3RlZCBzdGF0ZTsgd3JpdGVzIGFuZCByZXR1cm4gbmF2aWdhdGlvbiB1c2UgdGhlIFVJLlxuYXN5bmMgZnVuY3Rpb24gcmVwZWF0UGFyYW1ldGVyUmV0dXJuKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcHJvcG9zYWxJZDogc3RyaW5nLFxuICBzY2VuYXJpb3M6IFBhcmFtZXRlclJldHVyblNjZW5hcmlvW10sIHNlZWRzID0gWzQxLCA0MywgNDJdKSB7XHJcbiAgY29uc3QgYmVmb3JlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XG4gIGNvbnN0IGlkZW50aXR5ID0gYmVmb3JlLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uO1xuICBleHBlY3QoaWRlbnRpdHkucnVuX2lkKS50b0JlVHJ1dGh5KCk7XG4gIGNvbnN0IG5vZGVJZHMgPSAoYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKSkubWFwKGl0ZW0gPT4gaXRlbS5pZCkuc29ydCgpO1xuICBjb25zdCBzdGFydHM6IHVua25vd25bXSA9IFtdO1xuICBjb25zdCB0cmFja1N0YXJ0cyA9IChyZXF1ZXN0OiBpbXBvcnQoJ3BsYXl3cmlnaHQvdGVzdCcpLlJlcXVlc3QpID0+IHtcbiAgICBpZiAocmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JykgJiYgcmVxdWVzdC5tZXRob2QoKSA9PT0gJ1BPU1QnXG4gICAgICAmJiByZXF1ZXN0LnBvc3REYXRhSlNPTigpPy53aXphcmRfY29tbWFuZD8uYWN0aW9uID09PSAnU1RBUlQnKSBzdGFydHMucHVzaChyZXF1ZXN0LnBvc3REYXRhSlNPTigpKTtcbiAgfTtcbiAgY29uc3QgZXZpZGVuY2U6IHVua25vd25bXSA9IFtdO1xuICBwYWdlLm9uKCdyZXF1ZXN0JywgdHJhY2tTdGFydHMpO1xuICB0cnkge1xuICAgIGNvbnN0IHdpemFyZCA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7bmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJ30pO1xuICAgIGlmIChhd2FpdCB3aXphcmQuaXNWaXNpYmxlKCkpIHtcbiAgICAgIC8vIEEgY2FwdHVyZWQgQVBJIFNUQVJUIGRvZXMgbm90IGFjdGl2YXRlIGEgYnJvd3NlciB3aXphcmQgc2Vzc2lvbi4gRW50ZXJcbiAgICAgIC8vIHBhcmFtZXRlcnMgdGhyb3VnaCB0aGUgYWN0dWFsIHdvcmtmbG93IGNhcmQsIGp1c3QgYXMgYSB1c2VyIGRvZXMuXG4gICAgICBhd2FpdCB3aXphcmQubG9jYXRvcignLmFnZW50LXdpemFyZC1wcm9ncmVzcy1jYXJkW2hyZWYqPVwibW9kZT1wYXJhbWV0ZXJzXCJdJykuY2xpY2soKTtcbiAgICAgIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywge25hbWU6ICdadXLDvGNrIHp1bSBBdWZ0cmFnJywgZXhhY3Q6IHRydWV9KSkudG9CZVZpc2libGUoKTtcbiAgICB9XG4gICAgZm9yIChjb25zdCBbY3ljbGUsIHNlZWRdIG9mIHNlZWRzLmVudHJpZXMoKSkge1xyXG4gICAgICBmb3IgKGNvbnN0IHNjZW5hcmlvIG9mIHNjZW5hcmlvcykge1xuICAgICAgICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8/bW9kZT1wYXJhbWV0ZXJzJnByb2plY3Q9JHtlbmNvZGVVUklDb21wb25lbnQocHJvamVjdCl9JnRlY2hub2xvZ3k9JHtzY2VuYXJpby50ZWNobm9sb2d5fSZwcm9wb3NhbD0ke3Byb3Bvc2FsSWR9I3BhcmFtZXRlci1maW5kaW5nc2ApO1xuICAgICAgICBhd2FpdCBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2UpO1xuICAgICAgICBjb25zdCBjb21tb24gPSBwYWdlLmxvY2F0b3IoJy5wYXJhbWV0ZXItZ3JvdXAtY29tbW9uJyk7XG4gICAgICAgIGZvciAoY29uc3QgW2ZpZWxkLCB2YWx1ZV0gb2YgT2JqZWN0LmVudHJpZXMoc2NlbmFyaW8uZmllbGRzKSkge1xuICAgICAgICAgIGNvbnN0IGlucHV0ID0gcGFnZS5sb2NhdG9yKGAjJHtmaWVsZH1gKTtcbiAgICAgICAgICBjb25zdCBkZXRhaWxzID0gaW5wdXQubG9jYXRvcigneHBhdGg9YW5jZXN0b3I6OmRldGFpbHNbMV0nKTtcbiAgICAgICAgICBpZiAoYXdhaXQgZGV0YWlscy5jb3VudCgpICYmIGF3YWl0IGRldGFpbHMuZ2V0QXR0cmlidXRlKCdvcGVuJykgPT09IG51bGwpXG4gICAgICAgICAgICBhd2FpdCBkZXRhaWxzLmxvY2F0b3IoJzpzY29wZSA+IHN1bW1hcnknKS5jbGljaygpO1xuICAgICAgICAgIGlmIChzY2VuYXJpby5lZGl0RmllbGRzPy5pbmNsdWRlcyhmaWVsZCkpIGF3YWl0IGlucHV0LmZpbGwodmFsdWUpO1xuICAgICAgICAgIGVsc2UgYXdhaXQgZXhwZWN0KGlucHV0KS50b0hhdmVWYWx1ZSh2YWx1ZSk7XG4gICAgICAgIH1cbiAgICAgICAgYXdhaXQgY29tbW9uLmxvY2F0b3IoJyNzZWVkJykuZmlsbChTdHJpbmcoc2VlZCkpO1xuICAgICAgICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywge25hbWU6ICdQYXJhbWV0ZXIgc3BlaWNoZXJuIOKGkicsIGV4YWN0OiB0cnVlfSkuY2xpY2soKTtcbiAgICAgICAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdUZWNobm9sb2dpZS0gdW5kIFRpbWluZy1QYXJhbWV0ZXIgZ2VzcGVpY2hlcnQuJykpLnRvQmVWaXNpYmxlKCk7XG4gICAgICAgIGNvbnN0IHNhdmVkID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycpO1xuICAgICAgICBleHBlY3Qoc2F2ZWQucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcbiAgICAgICAgY29uc3Qgc2NvcGVkID0gc2F2ZWQucGFyYW1ldGVycy50ZWNobm9sb2d5X3BhcmFtZXRlcnNbc2NlbmFyaW8udGVjaG5vbG9neV07XG4gICAgICAgIGNvbnN0IGFzc3VtZWQgPSBzYXZlZC5wYXJhbWV0ZXJzLnNpbXVsYXRpb25fcGFyYW1ldGVyX2Fzc3VtcHRpb25zPy5bc2NlbmFyaW8udGVjaG5vbG9neV07XG4gICAgICAgIGV4cGVjdChzY29wZWQudmFsdWVzLnNlZWQpLnRvQmUoc2VlZCk7XG4gICAgICAgIGNvbnN0IG5hdGl2ZVZhbHVlcyA9IHsuLi5hc3N1bWVkPy52YWx1ZXMsIC4uLnNjb3BlZC52YWx1ZXN9O1xuICAgICAgICBleHBlY3QobmF0aXZlVmFsdWVzKS50b01hdGNoT2JqZWN0KHNjZW5hcmlvLm5hdGl2ZSk7XG4gICAgICAgIGZvciAoY29uc3QgW2tleSwgdmFsdWVdIG9mIE9iamVjdC5lbnRyaWVzKHNjZW5hcmlvLm5hdGl2ZSkpIHtcbiAgICAgICAgICBjb25zdCBjb25maXJtZWQgPSBPYmplY3QuaGFzT3duKHNjb3BlZC52YWx1ZXMsIGtleSk7XG4gICAgICAgICAgZXhwZWN0KChjb25maXJtZWQgPyBzY29wZWQgOiBhc3N1bWVkKS5wcm92ZW5hbmNlW2tleV0pLnRvTWF0Y2hPYmplY3QoY29uZmlybWVkXG4gICAgICAgICAgICA/IHtzb3VyY2U6ICdVU0VSX0NPTkZJUk1FRCcsIHN0YXR1czogJ0NPTkZJUk1FRCcsIHZhbHVlfVxuICAgICAgICAgICAgOiB7c291cmNlOiAnTklTX1NJTVVMQVRJT05fQVNTVU1QVElPTicsIHN0YXR1czogJ0FTU1VNRUQnLCB0ZWNobm9sb2d5OiBzY2VuYXJpby50ZWNobm9sb2d5LCBoYXJkd2FyZV9ldmlkZW5jZTogZmFsc2UsIHZhbHVlfSk7XG4gICAgICAgIH1cbiAgICAgICAgY29uc3QgdXNlclZhbHVlcyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMvdXNlci1kZWZpbmVkLXZhbHVlcycpO1xuICAgICAgICBleHBlY3QodXNlclZhbHVlcy5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xuICAgICAgICBleHBlY3QodXNlclZhbHVlcy52YWx1ZV9vcmlnaW4pLnRvQmUoJ1VTRVJfREVGSU5FRF9WQUxVRScpO1xuICAgICAgICBleHBlY3QodXNlclZhbHVlcy5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfZGVmYXVsdHMpLnRvQmVVbmRlZmluZWQoKTtcbiAgICAgICAgZXhwZWN0KHVzZXJWYWx1ZXMucGFyYW1ldGVycy50ZWNobm9sb2d5X3BhcmFtZXRlcnNbc2NlbmFyaW8udGVjaG5vbG9neV0pLnRvRXF1YWwoc2NvcGVkKTtcbiAgICAgICAgY29uc3Qgc3RhbGUgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtwcm9wb3NhbElkfT92aWV3PXN0YXR1c2ApO1xuICAgICAgICBleHBlY3Qoc3RhbGUuZGF0YS5zdGF0dXMpLnRvQmUoJ09VVERBVEVEJyk7XG4gICAgICAgIGNvbnN0IGNhbm9uaWNhbElkcyA9IHN0YWxlLmRhdGEuY2Fub25pY2FsX2lkcztcbiAgICAgICAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcbiAgICAgICAgYXdhaXQgZXhwZWN0KGNvbW1vbi5sb2NhdG9yKCcjc2VlZCcpKS50b0hhdmVWYWx1ZShTdHJpbmcoc2VlZCkpO1xuICAgICAgICBmb3IgKGNvbnN0IFtmaWVsZCwgdmFsdWVdIG9mIE9iamVjdC5lbnRyaWVzKHNjZW5hcmlvLmZpZWxkcykpIHtcbiAgICAgICAgICBjb25zdCBpbnB1dCA9IHBhZ2UubG9jYXRvcihgIyR7ZmllbGR9YCk7XG4gICAgICAgICAgY29uc3QgZGV0YWlscyA9IGlucHV0LmxvY2F0b3IoJ3hwYXRoPWFuY2VzdG9yOjpkZXRhaWxzWzFdJyk7XG4gICAgICAgICAgaWYgKGF3YWl0IGRldGFpbHMuY291bnQoKSAmJiBhd2FpdCBkZXRhaWxzLmdldEF0dHJpYnV0ZSgnb3BlbicpID09PSBudWxsKVxuICAgICAgICAgICAgYXdhaXQgZGV0YWlscy5sb2NhdG9yKCc6c2NvcGUgPiBzdW1tYXJ5JykuY2xpY2soKTtcbiAgICAgICAgICBhd2FpdCBleHBlY3QoaW5wdXQpLnRvSGF2ZVZhbHVlKHZhbHVlKTtcbiAgICAgICAgfVxuICAgICAgICAvLyBLZWVwIHRoZSBleGlzdGluZyBkZWxheWVkLXJlc3RvcmUgcmVncmVzc2lvbiwgdXNpbmcgcmVhbCByZXNwb25zZXMuXG4gICAgICAgIGxldCByZXN1bWVSZXN0b3JlITogKCkgPT4gdm9pZDtcbiAgICAgICAgY29uc3QgcmVzdG9yZVBhdXNlID0gbmV3IFByb21pc2U8dm9pZD4ocmVzb2x2ZSA9PiB7IHJlc3VtZVJlc3RvcmUgPSByZXNvbHZlOyB9KTtcbiAgICAgICAgY29uc3QgZGVsYXlSZXN0b3JlID0gYXN5bmMgKHJvdXRlOiBpbXBvcnQoJ3BsYXl3cmlnaHQvdGVzdCcpLlJvdXRlKSA9PiB7XG4gICAgICAgICAgYXdhaXQgcmVzdG9yZVBhdXNlOyBhd2FpdCByb3V0ZS5jb250aW51ZSgpO1xuICAgICAgICB9O1xuICAgICAgICBjb25zdCBkZWxheWVkID0gY3ljbGUgPT09IDAgJiYgc2NlbmFyaW8gPT09IHNjZW5hcmlvc1swXTtcbiAgICAgICAgaWYgKGRlbGF5ZWQpIGF3YWl0IHBhZ2Uucm91dGUoJyoqL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknLCBkZWxheVJlc3RvcmUpO1xuICAgICAgICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywge25hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbid9KTtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywge25hbWU6ICdadXLDvGNrIHp1bSBBdWZ0cmFnJywgZXhhY3Q6IHRydWV9KS5jbGljaygpO1xuICAgICAgICAgIGlmIChkZWxheWVkKSB7XG4gICAgICAgICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywge25hbWU6ICdHZXNwZWljaGVydGVuIEF1ZnRyYWcgd2llZGVyaGVyc3RlbGxlbid9KSkudG9CZVZpc2libGUoKTtcbiAgICAgICAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cpLm5vdC50b0NvbnRhaW5UZXh0KCdQcm9qZWt0bmFtZTogU2Nocml0dCAxJyk7XG4gICAgICAgICAgfVxuICAgICAgICB9IGZpbmFsbHkge1xuICAgICAgICAgIHJlc3VtZVJlc3RvcmUoKTtcbiAgICAgICAgICBpZiAoZGVsYXllZCkgYXdhaXQgcGFnZS51bnJvdXRlQWxsKHtiZWhhdmlvcjogJ3dhaXQnfSk7XG4gICAgICAgIH1cbiAgICAgICAgLy8gTWF0Y2ggdGhlIGV4aXN0aW5nIHByb3Bvc2FsLXJldmlldyByZWFkaW5lc3MgYnVkZ2V0IGJlbG93LiBUaGUgbmV3XG4gICAgICAgIC8vIHJldHVybiBhc3NlcnRpb24gbXVzdCBub3QgaW1wb3NlIGEgc2hvcnRlciBsaW1pdCBvbiB0aGUgbGFyZ2UgbW9kZWwuXG4gICAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7bmFtZTogJ0VuZ2luZWVyaW5nLVZvcnNjaGxhZyd9KSlcbiAgICAgICAgICAudG9Db250YWluVGV4dCgnR2VwcsO8ZnQgwrcgRnJlaWdhYmUgb2ZmZW4nLCB7dGltZW91dDogNjBfMDAwfSk7XG4gICAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cpLnRvQ29udGFpblRleHQoJ1N0YXR1c8O8YmVyc2ljaHQ6IFNjaHJpdHQgNSB2b24gNScpO1xuICAgICAgICBjb25zdCByZXN0b3JlZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xuICAgICAgICBleHBlY3QocmVzdG9yZWQucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcbiAgICAgICAgZXhwZWN0KHJlc3RvcmVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnJ1bl9pZCkudG9CZShpZGVudGl0eS5ydW5faWQpO1xuICAgICAgICBleHBlY3QocmVzdG9yZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24ucmVxdWVzdF9yZXZpc2lvbikudG9CZShpZGVudGl0eS5yZXF1ZXN0X3JldmlzaW9uKTtcbiAgICAgICAgZXhwZWN0KHJlc3RvcmVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnN0YXRlKS50b0JlKCdSRVZJRVdfUkVRVUlSRUQnKTtcbiAgICAgICAgZXhwZWN0KHJlc3RvcmVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnN0ZXApLnRvQmUoaWRlbnRpdHkuc3RlcCk7XG4gICAgICAgIGZvciAoY29uc3Qgc3RlcCBvZiBzdGVwcykgaWYgKGRvbmUuaGFzKGJlZm9yZS5zdGF0dXNlc1tzdGVwXSkpXG4gICAgICAgICAgZXhwZWN0KGRvbmUuaGFzKHJlc3RvcmVkLnN0YXR1c2VzW3N0ZXBdKSwgYFJldHVybmluZyBtdXN0IHByZXNlcnZlIGNvbXBsZXRlZCBzdGFnZSAke3N0ZXB9LmApLnRvQmUodHJ1ZSk7XG4gICAgICAgIGNvbnN0IGNvbnZlcnNhdGlvbiA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpO1xuICAgICAgICBleHBlY3QoY29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsKS50b0JlKHByb3Bvc2FsSWQpO1xuICAgICAgICBjb25zdCBmcmVzaCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3Byb3Bvc2FsSWR9P3ZpZXc9c3RhdHVzYCk7XG4gICAgICAgIGV4cGVjdChmcmVzaC5kYXRhLnN0YXR1cykudG9CZSgnVkFMSURBVEVEJyk7XG4gICAgICAgIGV4cGVjdChmcmVzaC5kYXRhLmNhbm9uaWNhbF9pZHMpLnRvRXF1YWwoY2Fub25pY2FsSWRzKTtcbiAgICAgICAgZXhwZWN0KChhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpKS5tYXAoaXRlbSA9PiBpdGVtLmlkKS5zb3J0KCkpLnRvRXF1YWwobm9kZUlkcyk7XG4gICAgICAgIGNvbnN0IGFmdGVyID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycpO1xuICAgICAgICBleHBlY3QoYWZ0ZXIucGFyYW1ldGVycykudG9FcXVhbChzYXZlZC5wYXJhbWV0ZXJzKTtcbiAgICAgICAgZXhwZWN0KHN0YXJ0cywgJ1JldHVybmluZyBmcm9tIHBhcmFtZXRlcnMgbXVzdCBuZXZlciByZXN0YXJ0IHRoaXMgcnVuLicpLnRvRXF1YWwoW10pO1xuICAgICAgICBldmlkZW5jZS5wdXNoKHtjeWNsZTogY3ljbGUgKyAxLCB0ZWNobm9sb2d5OiBzY2VuYXJpby50ZWNobm9sb2d5LCBzZWVkLCBydW5faWQ6IGlkZW50aXR5LnJ1bl9pZCxcbiAgICAgICAgICBwcm9wb3NhbF9pZDogcHJvcG9zYWxJZCwgc2F2ZWRfdmFsdWVzOiBzY29wZWQsIGFzc3VtcHRpb25zOiBhc3N1bWVkLFxuICAgICAgICAgIHJlc3RvcmVkX3N0YXR1czogZnJlc2guZGF0YS5zdGF0dXMsIGNhbm9uaWNhbF9pZHM6IGNhbm9uaWNhbElkc30pO1xuICAgICAgfVxuICAgIH1cbiAgfSBmaW5hbGx5IHtcbiAgICBwYWdlLm9mZigncmVxdWVzdCcsIHRyYWNrU3RhcnRzKTtcbiAgICBhd2FpdCB0ZXN0LmluZm8oKS5hdHRhY2goJ3JlcGVhdGVkLXBhcmFtZXRlci1yZXR1cm4nLCB7Ym9keTogSlNPTi5zdHJpbmdpZnkoZXZpZGVuY2UpLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nfSk7XG4gIH1cbn1cblxuYXN5bmMgZnVuY3Rpb24gY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcmVzdGFydDogYm9vbGVhbiwgZXhwZWN0ZWRIYXJkd2FyZTogc3RyaW5nW10gPSBbXSwgY3Jhc2hTaW11bGF0aW9uID0gZmFsc2UsXG4gIGV4cGVjdGVkU2lnbmFscz86IFJlY29yZDxzdHJpbmcsIHVua25vd24+LCBhZnRlckZpcnN0TW9kZWxBcHBsaWVkPzogKCkgPT4gUHJvbWlzZTx2b2lkPiwgc3RvcE9uRXZpZGVuY2VCbG9jayA9IGZhbHNlLFxuICBiZWZvcmVQcm9wb3NhbFJldmlldz86IChwcm9wb3NhbElkOiBzdHJpbmcsIHByb3Bvc2FsVHlwZTogc3RyaW5nKSA9PiBQcm9taXNlPHZvaWQgfCAnU1RPUF9BRlRFUl9SRVZJRVcnPikge1xyXG4gIGxldCByZXZpZXdDb3VudCA9IDA7XHJcbiAgbGV0IHJ1bklkOiBzdHJpbmcgfCB1bmRlZmluZWQ7XHJcbiAgY29uc3QgcmV2aWV3ZWQgPSBuZXcgU2V0PHN0cmluZz4oKTtcclxuICBsZXQgcmVzdGFydGVkSm9iSWQ6IHN0cmluZyB8IHVuZGVmaW5lZDtcclxuICBsZXQgd2F0Y2hkb2cgPSBuZXcgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyhwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgZm9yIChsZXQgY2hlY2twb2ludCA9IDA7IGNoZWNrcG9pbnQgPCAxNjsgY2hlY2twb2ludCsrKSB7XHJcbiAgICBsZXQgd29ya2Zsb3c6IGFueTtcclxuICAgIGxldCBwcm9wb3NhbElkID0gJyc7XHJcbiAgICBsZXQgcmVhZHlWZXJzaW9uID0gJyc7XHJcbiAgICBsZXQgcmVhZHlTaW5jZSA9IDA7XHJcbiAgICBjb25zdCBpc0NoZWNrcG9pbnQgPSBhc3luYyAoKSA9PiB7XHJcbiAgICAgIHdhdGNoZG9nLnJlbWFpbmluZyhwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgICAgIGF3YWl0IGFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkocGFnZSk7XHJcbiAgICAgIHdvcmtmbG93ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgIGNvbnN0IHByb2dyZXNzID0gd2F0Y2hkb2cub2JzZXJ2ZSh3b3JrZmxvdywgcGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gICAgICBpZiAocHJvZ3Jlc3MuYWR2YW5jZWQpIHByb2dyZXNzTWlsZXN0b25lcy5nZXQodGVzdC5pbmZvKCkudGVzdElkKSEucHVzaCh7XHJcbiAgICAgICAgYXQ6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSwgZnJvbnRpZXI6IHByb2dyZXNzLmZyb250aWVyLFxyXG4gICAgICAgIGNvbXBsZXRlZFRocm91Z2g6IHN0ZXBzW3Byb2dyZXNzLmZyb250aWVyIC0gMV0sXHJcbiAgICAgICAgcHJvamVjdDogd29ya2Zsb3cucHJvamVjdF9pZCwgZXhlY3V0aW9uOiB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbixcclxuICAgICAgfSk7XHJcbiAgICAgIGlmIChjcmFzaFNpbXVsYXRpb24gJiYgIXJlc3RhcnRlZEpvYklkICYmIGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzLnZhbGlkYXRpb24pKSB7XHJcbiAgICAgICAgY29uc3Qgam9icyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzO1xyXG4gICAgICAgIGNvbnN0IHJ1bm5pbmcgPSBqb2JzLmZpbmQoKGpvYjogeyBzdGF0dXM6IHN0cmluZyB9KSA9PiBqb2Iuc3RhdHVzID09PSAncnVubmluZycpO1xyXG4gICAgICAgIGlmIChydW5uaW5nKSB7XHJcbiAgICAgICAgICByZXN0YXJ0ZWRKb2JJZCA9IHJ1bm5pbmcuaWQ7XHJcbiAgICAgICAgICBhd2FpdCByZXN0YXJ0QXBwbGljYXRpb24ocGFnZSwgdHJ1ZSk7XHJcbiAgICAgICAgICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgICAgICAgcmV0dXJuIGZhbHNlO1xyXG4gICAgICAgIH1cclxuICAgICAgfVxyXG4gICAgICBpZiAoc3RlcHMuZXZlcnkoc3RlcCA9PiBkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXSkpKSByZXR1cm4gdHJ1ZTtcclxuICAgICAgY29uc3QgZXhlY3V0aW9uID0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb247XHJcbiAgICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnUkVWSUVXX1JFUVVJUkVEJykge1xyXG4gICAgICAgIGNvbnN0IGNvbnZlcnNhdGlvbiA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpO1xyXG4gICAgICAgIHByb3Bvc2FsSWQgPSBjb252ZXJzYXRpb24uZGF0YS5hY3RpdmVfcHJvcG9zYWw7XHJcbiAgICAgICAgLy8gUG9sbGluZyBtYXkgc3RpbGwgZXhwb3NlIHRoZSBqdXN0LWFwcGxpZWQgcmV2aWV3IHdoaWxlIHRoZSBVSSBzdGFydHNcclxuICAgICAgICAvLyBpdHMgZHVyYWJsZSBjb250aW51YXRpb24uIFdhaXQgZm9yIGEgZGlzdGluY3QgcHJvcG9zYWwsIG5vdCBpdHMgbGFiZWwuXHJcbiAgICAgICAgcmV0dXJuIEJvb2xlYW4ocHJvcG9zYWxJZCkgJiYgIXJldmlld2VkLmhhcyhwcm9wb3NhbElkKTtcclxuICAgICAgfVxyXG4gICAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JFQURZX1RPX0NPTlRJTlVFJyB8fCAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5yZWNvdmVyYWJsZSA9PT0gdHJ1ZSkpIHtcclxuICAgICAgICBpZiAocmVhZHlWZXJzaW9uICE9PSBleGVjdXRpb24udXBkYXRlZF9hdCkge1xyXG4gICAgICAgICAgcmVhZHlWZXJzaW9uID0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQ7IHJlYWR5U2luY2UgPSBEYXRlLm5vdygpO1xyXG4gICAgICAgIH1cclxuICAgICAgICAvLyBXaGlsZSBhIGxhcmdlIGNvbnRpbnVhdGlvbiBpcyBnZW5lcmF0aW5nLCB0aGUgbGFzdCBjb21taXR0ZWQgc2VydmVyXHJcbiAgICAgICAgLy8gY2hlY2twb2ludCBjYW4gc3RpbGwgYmUgUkVBRFkuIEFjdCBvbmx5IHdoZW4gdGhlIFVJIG9mZmVycyBpdCB0b28uXHJcbiAgICAgICAgY29uc3QgYnV0dG9uID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KVxyXG4gICAgICAgICAgLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQXVmdHJhZyBmb3J0c2V0emVuJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgICAgICAgcmV0dXJuIERhdGUubm93KCkgLSByZWFkeVNpbmNlID4gNTAwMCAmJiBhd2FpdCBidXR0b24uZXZhbHVhdGVBbGwoYnV0dG9ucyA9PiBidXR0b25zLnNvbWUoYnV0dG9uID0+ICEoYnV0dG9uIGFzIEhUTUxCdXR0b25FbGVtZW50KS5kaXNhYmxlZCAmJiBidXR0b24uZ2V0Q2xpZW50UmVjdHMoKS5sZW5ndGggPiAwICYmIGdldENvbXB1dGVkU3R5bGUoYnV0dG9uKS52aXNpYmlsaXR5ICE9PSBcImhpZGRlblwiKSk7XHJcbiAgICAgIH1cclxuICAgICAgcmV0dXJuIFsnQkxPQ0tFRCcsICdGQUlMRUQnLCAnSU5DT01QTEVURSddLmluY2x1ZGVzKGV4ZWN1dGlvbj8uc3RhdGUpO1xyXG4gICAgfTtcclxuICAgIC8vIEEgc2luZ2xlIHBvbGwgcHJldmlvdXNseSB0aW1lZCBhbGwgb2YgQ2FwYWNpdHkgLT4gSW50ZWxsaWdlbmNlIHRvZ2V0aGVyLlxyXG4gICAgLy8gQm91bmQgZWFjaCBnZW51aW5lIHN0YWdlIGFkdmFuY2UsIHdoaWxlIHJldHJpZXMgYW5kIHJlc3RhcnRzIHJldGFpbiB0aGVpclxyXG4gICAgLy8gcmVtYWluaW5nIGRlYWRsaW5lLiBUaGUgaW5kZXBlbmRlbnQgMjAtbWludXRlIHRlc3QgdGltZW91dCBpcyB1bmNoYW5nZWQuXHJcbiAgICBsZXQgYXR0ZW1wdCA9IDA7XHJcbiAgICB3aGlsZSAoIWF3YWl0IGlzQ2hlY2twb2ludCgpKSB7XHJcbiAgICAgIGNvbnN0IHJlbWFpbmluZyA9IHdhdGNoZG9nLnJlbWFpbmluZyhwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgICAgIGF3YWl0IHBhZ2Uud2FpdEZvclRpbWVvdXQoTWF0aC5taW4oWzUwMCwgMTAwMCwgMjAwMF1bTWF0aC5taW4oYXR0ZW1wdCsrLCAyKV0sIHJlbWFpbmluZykpO1xyXG4gICAgfVxyXG4gICAgcnVuSWQgPz89IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQ7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZCkudG9CZShydW5JZCk7XHJcbiAgICBpZiAoc3RlcHMuZXZlcnkoc3RlcCA9PiBkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXSkpKSB7XHJcbiAgICAgIGlmIChjcmFzaFNpbXVsYXRpb24pIGV4cGVjdChyZXN0YXJ0ZWRKb2JJZCwgJ0EgcmVhbCBydW5uaW5nIHNpbXVsYXRpb24gbXVzdCBiZSBvYnNlcnZlZCBhbmQgaW50ZXJydXB0ZWQuJykudG9CZVRydXRoeSgpO1xyXG4gICAgICByZXR1cm4geyBydW5JZCwgcmV2aWV3ZWQ6IFsuLi5yZXZpZXdlZF0sIHJlc3RhcnRlZEpvYklkIH07XHJcbiAgICB9XHJcbiAgICBjb25zdCBleGVjdXRpb24gPSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbjtcclxuICAgIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XHJcbiAgICBpZiAoc3RvcE9uRXZpZGVuY2VCbG9jayAmJiBleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLmJsb2NraW5nX2ZpbmRpbmdzPy5sZW5ndGgpIHtcclxuICAgICAgdGhyb3cgbmV3IEVycm9yKGBXaXphcmQgQkxPQ0tFRCBhdCAke2V4ZWN1dGlvbi5zdGVwfTogJHtleGVjdXRpb24ubWVzc2FnZX1gKTtcclxuICAgIH1cclxuICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLm1lc3NhZ2U/LmluY2x1ZGVzKCdSRUFEWV9XSVRIX1dBUk5JTkdTJykpIHtcclxuICAgICAgY29uc3QgYmVmb3JlUmV2aWV3ID0gYXdhaXQgcmVhZFdhcm5pbmdSZXZpZXdTdGF0ZShwYWdlLCBwcm9qZWN0KTtcclxuICAgICAgY29uc3QgcHJlZmxpZ2h0ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvcHJlZmxpZ2h0Jyk7XHJcbiAgICAgIGNvbnN0IHdhcm5pbmdzID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnUHJlZmxpZ2h0LVdhcm51bmdlbicgfSk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdCh3YXJuaW5ncy5nZXRCeVJvbGUoJ2xpc3RpdGVtJykuZmlyc3QoKSkudG9CZVZpc2libGUoKTtcclxuICAgICAgY29uc3Qgc3RhcnRlZCA9IHBlcmZvcm1hbmNlLm5vdygpLCBzdGFydGVkV2FsbCA9IERhdGUubm93KCk7XHJcbiAgICAgIHdhdGNoZG9nLnJlbWFpbmluZyhzdGFydGVkKTtcclxuICAgICAgY29uc3QgYXBwcm92YWxSZXNwb25zZSA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IG5ldyBVUkwocmVzcG9uc2UudXJsKCkpLnBhdGhuYW1lID09PSAnL2FwaS9lbmdpbmVlcmluZy9wcmVmbGlnaHQvd2FybmluZ3MvYXBwcm92ZSdcclxuICAgICAgICAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJywgeyB0aW1lb3V0OiAxODBfMDAwIH0pO1xyXG4gICAgICBhd2FpdCB3YXJuaW5ncy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ1dhcm51bmdlbiBmcmVpZ2ViZW4gdW5kIGZvcnRzZXR6ZW4nIH0pLmNsaWNrKCk7XHJcbiAgICAgIGNvbnN0IGFwcHJvdmVkID0gYXdhaXQgYXBwcm92YWxSZXNwb25zZTtcclxuICAgICAgY29uc3QgcmVjZWlwdCA9IGF3YWl0IGFwcHJvdmVkLmpzb24oKTtcclxuICAgICAgY29uc3QgYWZ0ZXJSZXZpZXcgPSBhd2FpdCByZWFkV2FybmluZ1Jldmlld1N0YXRlKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgICBjb25zdCBwcm9vZiA9IHsgYmVmb3JlOiBiZWZvcmVSZXZpZXcsIGFmdGVyOiBhZnRlclJldmlldywgc25hcHNob3RJZDogcHJlZmxpZ2h0LmlkLFxyXG4gICAgICAgIHJlcXVlc3RQcm9qZWN0OiBhcHByb3ZlZC5yZXF1ZXN0KCkuaGVhZGVycygpWyd4LXByb2plY3QtaWQnXSwgc3VibWl0dGVkOiBhcHByb3ZlZC5yZXF1ZXN0KCkucG9zdERhdGFKU09OKCksXHJcbiAgICAgICAgc3RhdHVzOiBhcHByb3ZlZC5zdGF0dXMoKSwgcmVzcG9uc2U6IHJlY2VpcHQsIHN0YXJ0ZWQsIHN0YXJ0ZWRXYWxsLCBmaW5pc2hlZFdhbGw6IERhdGUubm93KCkgfTtcclxuICAgICAgY29uc3QgY29tbWl0dGVkQXQgPSBwZXJmb3JtYW5jZS5ub3coKTtcclxuICAgICAgY29uc3QgY29tbWl0dGVkID0gd2F0Y2hkb2cuY29tbWl0V2FybmluZ1Jldmlldyhwcm9vZiwgY29tbWl0dGVkQXQpO1xyXG4gICAgICBhd2FpdCB0ZXN0LmluZm8oKS5hdHRhY2goJ3ZlcmlmaWVkLXdhcm5pbmctcmV2aWV3LXByb29mJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb29mLCBjb21taXR0ZWRBdCwgY29tbWl0dGVkIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gICAgICBwcm9ncmVzc01pbGVzdG9uZXMuZ2V0KHRlc3QuaW5mbygpLnRlc3RJZCkhLnB1c2goeyBhdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLCBtYW51YWxXYXJuaW5nQXBwcm92YWw6IGNvbW1pdHRlZC5hcHByb3ZhbElkZW50aXR5LFxyXG4gICAgICAgIGZyb250aWVyOiBjb21taXR0ZWQuZnJvbnRpZXIsIHByb2plY3QsIGV4ZWN1dGlvbjogYWZ0ZXJSZXZpZXcuY29udGV4dC5hZ2VudF9leGVjdXRpb24sIGFwcHJvdmFsOiByZWNlaXB0LmFwcHJvdmFsIH0pO1xyXG4gICAgICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5JykpLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0LFxyXG4gICAgICAgIHsgdGltZW91dDogZXhwZWN0ZWRIYXJkd2FyZS5sZW5ndGggPiAxMDAgPyAxODBfMDAwIDogNjBfMDAwIH0pLm5vdC50b0JlKGV4ZWN1dGlvbi51cGRhdGVkX2F0KTtcclxuICAgICAgY29udGludWU7XHJcbiAgICB9XHJcbiAgICBpZiAoWydCTE9DS0VEJywgJ0ZBSUxFRCcsICdJTkNPTVBMRVRFJ10uaW5jbHVkZXMoZXhlY3V0aW9uPy5zdGF0ZSkgJiYgZXhlY3V0aW9uLnJlY292ZXJhYmxlICE9PSB0cnVlKSB7XHJcbiAgICAgIGNvbnN0IGNvbnZlcnNhdGlvbiA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpO1xyXG4gICAgICBjb25zdCBpZCA9IGNvbnZlcnNhdGlvbi5kYXRhPy5hY3RpdmVfcHJvcG9zYWw7XHJcbiAgICAgIGNvbnN0IHByb3Bvc2FsID0gaWQgPyBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtpZH1gKSA6IG51bGw7XHJcbiAgICAgIGF3YWl0IHRlc3QuaW5mbygpLmF0dGFjaCgnd2l6YXJkLWJsb2NrZXInLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgZXhlY3V0aW9uLFxyXG4gICAgICAgIHByb3Bvc2FsOiBwcm9wb3NhbD8uZGF0YT8udmFsaWRhdGlvbl9yZXN1bHQsIHZpc2libGU6IGF3YWl0IGRpYWxvZy5pbm5lclRleHQoKSB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICAgICAgdGhyb3cgbmV3IEVycm9yKGBXaXphcmQgJHtleGVjdXRpb24uc3RhdGV9IGF0ICR7ZXhlY3V0aW9uLnN0ZXB9OiAke2V4ZWN1dGlvbi5tZXNzYWdlfWApO1xyXG4gICAgfVxyXG4gICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdSRUFEWV9UT19DT05USU5VRScgfHwgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24ucmVjb3ZlcmFibGUgPT09IHRydWUpKSB7XHJcbiAgICAgIGNvbnN0IGJ1dHRvbiA9IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1ZnRyYWcgZm9ydHNldHplbicsIGV4YWN0OiB0cnVlIH0pO1xyXG4gICAgICB0cnkge1xyXG4gICAgICAgIGF3YWl0IGJ1dHRvbi5jbGljayh7IHRpbWVvdXQ6IDIwMDAgfSk7XHJcbiAgICAgIH0gY2F0Y2ggKGVycm9yKSB7XHJcbiAgICAgICAgY29uc3QgbGF0ZXN0ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgICAgaWYgKGxhdGVzdC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCA9PT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQgJiYgYXdhaXQgYnV0dG9uLmV2YWx1YXRlQWxsKGJ1dHRvbnMgPT4gYnV0dG9ucy5zb21lKGJ1dHRvbiA9PiAhKGJ1dHRvbiBhcyBIVE1MQnV0dG9uRWxlbWVudCkuZGlzYWJsZWQgJiYgYnV0dG9uLmdldENsaWVudFJlY3RzKCkubGVuZ3RoID4gMCAmJiBnZXRDb21wdXRlZFN0eWxlKGJ1dHRvbikudmlzaWJpbGl0eSAhPT0gXCJoaWRkZW5cIikpKSB0aHJvdyBlcnJvcjtcclxuICAgICAgICBjb250aW51ZTtcclxuICAgICAgfVxyXG4gICAgICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICAgICAgY29uc3QgbGF0ZXN0ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgICAgcmV0dXJuIGxhdGVzdC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCAhPT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXRcclxuICAgICAgICAgIHx8IGxhdGVzdC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uc3RhdGUgPT09ICdSVU5OSU5HJ1xyXG4gICAgICAgICAgfHwgbGF0ZXN0LnN0YXR1c2VzPy5bZXhlY3V0aW9uLnN0ZXBdID09PSAnSU5fUFJPR1JFU1MnO1xyXG4gICAgICB9LCB7IHRpbWVvdXQ6IDYwXzAwMCB9KS50b0JlKHRydWUpO1xyXG4gICAgICBjb250aW51ZTtcclxuICAgIH1cclxuICAgIGNvbnN0IGNhbmRpZGF0ZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3Byb3Bvc2FsSWR9YCk7XHJcbiAgICBpZiAoY2FuZGlkYXRlLmRhdGEucHJvcG9zYWxfdHlwZSA9PT0gJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcgJiYgcmV2aWV3Q291bnQgPT09IDAgJiYgZXhwZWN0ZWRIYXJkd2FyZS5sZW5ndGgpIHtcclxuICAgICAgY29uc3QgaGFyZHdhcmUgPSBjYW5kaWRhdGUuZGF0YS5jaGFuZ2VzXHJcbiAgICAgICAgLmZpbHRlcigoY2hhbmdlOiB7IG9iamVjdF90eXBlOiBzdHJpbmcgfSkgPT4gY2hhbmdlLm9iamVjdF90eXBlID09PSAnSGFyZHdhcmVOb2RlJylcclxuICAgICAgICAubWFwKChjaGFuZ2U6IHsgZGF0YTogeyBuYW1lOiBzdHJpbmcgfSB9KSA9PiBjaGFuZ2UuZGF0YS5uYW1lKTtcclxuICAgICAgZXhwZWN0KGhhcmR3YXJlLCAnVGhlIFVJIG11c3QgcHJlc2VydmUgdGhlIGhhcmR3YXJlIGV4cGxpY2l0bHkgbmFtZWQgaW4gdGhlIHVzZXIgcmVxdWVzdC4nKVxyXG4gICAgICAgIC50b0VxdWFsKGV4cGVjdC5hcnJheUNvbnRhaW5pbmcoZXhwZWN0ZWRIYXJkd2FyZSkpO1xyXG4gICAgfVxyXG4gICAgZXhwZWN0KHJldmlld2VkLmhhcyhwcm9wb3NhbElkKSwgJ1RoZSBzYW1lIHByb3Bvc2FsIG11c3Qgbm90IHJlcXVlc3QgcmV2aWV3IHR3aWNlLicpLnRvQmUoZmFsc2UpO1xuICAgIGNvbnN0IHJldmlld0FjdGlvbiA9IGF3YWl0IGJlZm9yZVByb3Bvc2FsUmV2aWV3Py4ocHJvcG9zYWxJZCwgY2FuZGlkYXRlLmRhdGEucHJvcG9zYWxfdHlwZSk7XHJcbiAgICBpZiAocmV2aWV3QWN0aW9uID09PSAnU1RPUF9BRlRFUl9SRVZJRVcnKSB7XHJcbiAgICAgIC8vIEV4cGxpY2l0IHRhcmdldGVkIGNvdmVyYWdlOiB0aGUgc2VsZWN0ZWQgcGVuZGluZyBwcm9wb3NhbCBoYXMgYmVlblxyXG4gICAgICAvLyBleGVyY2lzZWQgYnV0IGlzIG5vdCBhcHBsaWVkIGFuZCB0aGlzIGlzIG5vdCBuaW5lLXN0YWdlIGNvbXBsZXRpb24uXHJcbiAgICAgIHJldHVybiB7IHJ1bklkLCByZXZpZXdlZDogWy4uLnJldmlld2VkXSwgcmVzdGFydGVkSm9iSWQsXHJcbiAgICAgICAgcmV2aWV3T25seTogeyBwcm9wb3NhbElkLCBwcm9wb3NhbFR5cGU6IGNhbmRpZGF0ZS5kYXRhLnByb3Bvc2FsX3R5cGUgfSB9O1xyXG4gICAgfVxyXG4gICAgY29uc3QgYXBwbHlSZXNwb25zZSA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IHJlc3BvbnNlLnVybCgpLmluY2x1ZGVzKGAvcHJvcG9zYWxzLyR7cHJvcG9zYWxJZH0vYXBwcm92ZS1hcHBseWApICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnLCB7IHRpbWVvdXQ6IDE4MF8wMDAgfSk7XHJcbiAgICBjb25zdCBhcHByb3ZhbCA9IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogL14oRnJlaWdlYmVuLCDDvGJlcm5laG1lbiAmIGZvcnRmYWhyZW58w5xiZXJuZWhtZW4gJiBmb3J0ZmFocmVuKSQvIH0pO1xyXG4gICAgYXdhaXQgZXhwZWN0KGFwcHJvdmFsKS50b0JlRW5hYmxlZCh7IHRpbWVvdXQ6IDYwXzAwMCB9KTtcclxuICAgIGF3YWl0IGFwcHJvdmFsLmNsaWNrKCk7XHJcbiAgICBjb25zdCBhcHBsaWVkID0gYXdhaXQgYXBwbHlSZXNwb25zZTtcclxuICAgIGlmICghYXBwbGllZC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYEhUVFAgJHthcHBsaWVkLnN0YXR1cygpfTogJHsoYXdhaXQgYXBwbGllZC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gICAgZXhwZWN0KChhd2FpdCBhcHBsaWVkLmpzb24oKSkuZGF0YS5zdGF0dXMpLnRvQmUoJ0FQUExJRUQnKTtcclxuICAgIHJldmlld2VkLmFkZChwcm9wb3NhbElkKTsgcmV2aWV3Q291bnQrKztcclxuICAgIC8vIEEgZGlzdGluY3QsIGFjdHVhbGx5IGNvbW1pdHRlZCBtYW51YWwgcmV2aWV3IHN0YXJ0cyB0aGUgbmV4dCBhdXRvbWF0aWNcclxuICAgIC8vIHNlY3Rpb24uIEl0cyB3cml0ZSBzdGlsbCBoYXMgdGhlIHNlcGFyYXRlIHVuY2hhbmdlZCAxODAtc2Vjb25kIGxpbWl0LlxyXG4gICAgd2F0Y2hkb2cgPSBuZXcgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyhwZXJmb3JtYW5jZS5ub3coKSwgd29ya2Zsb3cpO1xyXG4gICAgaWYgKGNhbmRpZGF0ZS5kYXRhLnByb3Bvc2FsX3R5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnICYmIGV4cGVjdGVkU2lnbmFscykge1xyXG4gICAgICBhd2FpdCB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZSwgcHJvamVjdCwgZXhwZWN0ZWRTaWduYWxzKTtcclxuICAgIH1cclxuICAgIGlmIChyZXZpZXdDb3VudCA9PT0gMSAmJiBhZnRlckZpcnN0TW9kZWxBcHBsaWVkKSB7XHJcbiAgICAgIGF3YWl0IGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQoKTtcclxuICAgICAgLy8gVGhpcyBvbmUgdGVzdCBleHBsaWNpdGx5IHN1Ym1pdHMgQU1FTkQgYW5kIHdhaXRzIGZvciBpdHMgcmVjZWlwdC4gT25seVxyXG4gICAgICAvLyB0aGF0IGRlbGliZXJhdGUgYWN0aW9uIHBlcm1pdHMgYmluZGluZyBpdHMgbmV3IHJlcXVlc3QgcmV2aXNpb24uXHJcbiAgICAgIGNvbnN0IGFtZW5kZWQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgZXhwZWN0KGFtZW5kZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZCkudG9CZShydW5JZCk7XHJcbiAgICAgIHdhdGNoZG9nID0gbmV3IFdpemFyZFByb2dyZXNzV2F0Y2hkb2cocGVyZm9ybWFuY2Uubm93KCksIGFtZW5kZWQpO1xyXG4gICAgfVxyXG4gICAgaWYgKHJldmlld0NvdW50ID09PSAxKSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpOyAvLyBEdXJhYmxlIHJlbG9hZCBhZnRlciBhIHJlYWwgY29tbWl0LlxyXG4gICAgaWYgKHJlc3RhcnQgJiYgcmV2aWV3Q291bnQgPT09IDIpIHtcclxuICAgICAgYXdhaXQgcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2UpO1xyXG4gICAgICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgfVxyXG4gICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgICBjb25zdCBjdXJyZW50ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgIHJldHVybiBjdXJyZW50LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0ICE9PSBleGVjdXRpb24udXBkYXRlZF9hdDtcclxuICAgIH0sIHsgdGltZW91dDogNjBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbiAgfVxyXG4gIHRocm93IG5ldyBFcnJvcignV2l6YXJkIGV4Y2VlZGVkIDE2IHJldmlldy9jb250aW51YXRpb24gY2hlY2twb2ludHMuJyk7XHJcbn1cclxuXHJcbnRlc3QoJ3dpemFyZCByZWZ1c2VzIGFuIHVuYXZhaWxhYmxlIGNhdGFsb2cgYW5kIHJlY292ZXJzIHVzaW5nIHRoZSByZWFsIHJlZ2lzdHJ5IEBjYXRhbG9nLXJlY292ZXJ5JywgYXN5bmMgKHtwYWdlfSkgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1jYXRhbG9nLXJlY292ZXJ5LScgKyByYW5kb21VVUlEKCk7XHJcbiAgYXdhaXQgcGFnZS5yb3V0ZSgnKiovYXBpL3RlY2hub2xvZ2llcycsIHJvdXRlID0+IHJvdXRlLmZ1bGZpbGwoe3N0YXR1czo1MDMsXHJcbiAgICBjb250ZW50VHlwZTonYXBwbGljYXRpb24vanNvbicsYm9keTpKU09OLnN0cmluZ2lmeSh7ZXJyb3I6J0RlciB2b2xsc3TDpG5kaWdlIFRlY2hub2xvZ2lla2F0YWxvZyBpc3QgZGVyemVpdCBuaWNodCBlcnJlaWNoYmFyLid9KX0pKTtcclxuICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdhbGVydCcpKS50b0NvbnRhaW5UZXh0KCdUZWNobm9sb2dpZWthdGFsb2cnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7ZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdDYXRhbG9nIHJldHJ5Jyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7ZXhhY3Q6dHJ1ZX0pLmZpbGwoJ2VpbiBBa3RvciB6dW0gcHJvcG9ydGlvbmFsIHNjaGxpZcOfZW4gZWluZXMgVmVudGlsJyk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJykpLnRvQmVEaXNhYmxlZCgpO1xyXG4gIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icykudG9IYXZlTGVuZ3RoKDApO1xyXG4gIGF3YWl0IHBhZ2UudW5yb3V0ZSgnKiovYXBpL3RlY2hub2xvZ2llcycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6J1RlY2hub2xvZ2lla2F0YWxvZyBlcm5ldXQgbGFkZW4nfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYWxlcnQnKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJykpLnRvQmVFbmFibGVkKCk7XHJcbiAgY29uc3QgY2F0YWxvZyA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL3RlY2hub2xvZ2llcycpKS5qc29uKCk7XHJcbiAgZXhwZWN0KGNhdGFsb2cudGVjaG5vbG9neV9jb3VudCkudG9CZSgxMjUpO1xyXG59KTtcclxuXHJcbnRlc3QoJ25ldyBzbWFsbCB3aXphcmQgdHJhdmVyc2VzIGFsbCBuaW5lIHN0YWdlcyBhbmQgc3Vydml2ZXMgcmVsb2FkL3Jlc3RhcnQgQHNtYWxsJywgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IGVycm9yczogc3RyaW5nW10gPSBbXTsgcGFnZS5vbigncGFnZWVycm9yJywgZXJyb3IgPT4gZXJyb3JzLnB1c2goZXJyb3IubWVzc2FnZSkpO1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1zbWFsbC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjZW5naW5lZXJpbmctcHJvamVjdC1uYW1lJykuZmlsbCgnRTJFIHNtYWxsJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwoJ0VyemV1Z2UgZWluIEF1dG9tb3RpdmUgQ0FOLUZEIE5ldHp3ZXJrIG1pdCBlaW5lbSBHYXRld2F5IFN5c3RlbSwgZGVuIEVDVXMgTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UsIGVpbmVtIFNlbnNvciBNb3RvclRlbXBlcmF0dXJlIHVuZCBlaW5lbSBBa3RvciBNb3RvclZhbHZlLiBNb3RvclRlbXBlcmF0dXJlIHdpcmQgdm9uIE1vdG9yc3RldWVydW5nIGF1c2dld2VydGV0LiBNb3RvcnN0ZXVlcnVuZyBzdGV1ZXJ0IE1vdG9yVmFsdmUuIENvbnRyb2xsZXJzdGF0dXMgYmxlaWJ0IGJpcyB6dXIgQXVzd2FobCBrb25rcmV0ZXIgRW1wZsOkbmdlciB1bmQgU2lnbmFsZSBpbnRlcm4uIFByw7xmZSB1bmQgYXJiZWl0ZSBiaXMgRGF0YSBTY2llbmNlICYgSW50ZWxsaWdlbmNlLlxcbkNBTi1GRDogNTAwIGtiaXQvcyBhcmJpdHJhdGlvbiwgMiBNYml0L3MgZGF0YVxcbkNBTjogNTAwIGtiaXQvcycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdXZWl0ZXJlIEhpbndlaXNlJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKCctIEFrdG9yLUJlZmVobGU6IHtcIk1vdG9yVmFsdmVcIjp7XCJsZW5ndGhfYml0c1wiOjEsXCJkYXRhX3R5cGVcIjpcImJvb2xlYW5cIixcImZhY3RvclwiOjEsXCJ1bml0XCI6XCJjb2RlXCIsXCJtaW5fdmFsdWVcIjowLFwibWF4X3ZhbHVlXCI6MSxcInNlbWFudGljXCI6e1wic2VtYW50aWNfdHlwZVwiOlwiQk9PTEVBTlwifSxcImRhdGFcIjp7XCJlbnVtX3ZhbHVlc1wiOntcIkNMT1NFXCI6MCxcIk9QRU5cIjoxfX19fScpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdHZXLDpHRldW1mYW5nJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGZvciAoY29uc3QgW2xhYmVsLCB2YWx1ZV0gb2YgW1snR2F0ZXdheXMnLCAnMSddLCBbJ0NvbnRyb2xsZXInLCAnMiddLCBbJ1NlbnNvcmVuJywgJzEnXSwgWydBa3RvcmVuJywgJzEnXV0pIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKGAke2xhYmVsfTogdmVyYmluZGxpY2hlIEFuemFobGAsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCh2YWx1ZSk7XHJcbiAgY29uc3Qgc3RhcnRSZXF1ZXN0ID0gcGFnZS53YWl0Rm9yUmVxdWVzdChyZXF1ZXN0ID0+IHJlcXVlc3QudXJsKCkuZW5kc1dpdGgoJy9hcGkvYWdlbnQvY2hhdCcpXHJcbiAgICAmJiByZXF1ZXN0Lm1ldGhvZCgpID09PSAnUE9TVCcgJiYgcmVxdWVzdC5wb3N0RGF0YUpTT04oKT8ud2l6YXJkX2NvbW1hbmQ/LmFjdGlvbiA9PT0gJ1NUQVJUJyk7XHJcbiAgLy8gVXNlIHRoZSBzYW1lIHZpc2libGUgcXVlc3Rpb25uYWlyZSBuYXZpZ2F0aW9uIGEgdXNlciB1c2VzOyBuZXZlciBpbmplY3QgZ2VuZXJhdGVkIG1vZGVsIHJvd3MuXHJcbiAgZm9yIChsZXQgc3RlcCA9IDA7IHN0ZXAgPCAxMDsgc3RlcCsrKSB7XHJcbiAgICBjb25zdCBzdWJtaXQgPSBkaWFsb2cubG9jYXRvcignLmVuZy1hZ2VudC1xdWVzdGlvbm5haXJlLWhlYWQnKS5nZXRCeVJvbGUoJ2J1dHRvbicpO1xyXG4gICAgYXdhaXQgZXhwZWN0KHN1Ym1pdCkudG9CZUVuYWJsZWQoKTtcclxuICAgIGNvbnN0IG5hbWUgPSBhd2FpdCBzdWJtaXQuaW5uZXJUZXh0KCk7XHJcbiAgICBhd2FpdCBzdWJtaXQuY2xpY2soKTtcclxuICAgIGlmIChuYW1lID09PSAnw5xiZXJuZWhtZW4nKSBicmVhaztcclxuICAgIGlmIChzdGVwID09PSA5KSB0aHJvdyBuZXcgRXJyb3IoJ1F1ZXN0aW9ubmFpcmUgZGlkIG5vdCBvZmZlciBzdWJtaXQuJyk7XHJcbiAgfVxyXG4gIGNvbnN0IHJlcXVlc3RlZCA9IChhd2FpdCBzdGFydFJlcXVlc3QpLnBvc3REYXRhSlNPTigpLndpemFyZF9jb21tYW5kLndpemFyZF9jb250ZXh0O1xyXG4gIGV4cGVjdChyZXF1ZXN0ZWQudGVjaG5vbG9naWVzLCAnQW4gZXhwbGljaXQgQ0FOLUZEIHRhc2sgbXVzdCBub3Qgc2lsZW50bHkgcmVxdWVzdCBMSU4gYW5kIFNPTUUvSVAuJykudG9FcXVhbChbJ0NBTi1GRCAoY2FuX2ZkKSddKTtcclxuICAvLyBQcmVzZXJ2ZSBhIHJlYWwgcGVuZGluZyBtb2RlbCB0aHJvdWdoIHBhcmFtZXRlciBzYXZlIGFuZCByZW5ld2VkIHJldmlldy5cclxuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiAoYXdhaXQgcmVhZFByb2plY3QocGFnZSxwcm9qZWN0LCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpKS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uc3RhdGUsXHJcbiAgICB7dGltZW91dDoxODAwMDB9KS50b0JlKCdSRVZJRVdfUkVRVUlSRUQnKTtcclxuICBjb25zdCBwZW5kaW5nID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UscHJvamVjdCwnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKSkuZGF0YS5hY3RpdmVfcHJvcG9zYWw7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7cHJvamVjdH0mdGVjaG5vbG9neT1jYW5fZmQmcHJvcG9zYWw9JHtwZW5kaW5nfSNwYXJhbWV0ZXItZmluZGluZ3NgKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicse25hbWU6J0FrdHVlbGxlIFBhcmFtZXRlcmJlZnVuZGUnfSkpLnRvQ29udGFpblRleHQoJ25vY2ggbmljaHQgw7xiZXJub21tZW5lbiBWb3JzY2hsYWdzJyk7XHJcbiAgY29uc3QgY29tbW9uID0gcGFnZS5sb2NhdG9yKCcucGFyYW1ldGVyLWdyb3VwLWNvbW1vbicpO1xyXG4gIGF3YWl0IGV4cGVjdChjb21tb24ubG9jYXRvcignI2FyYml0cmF0aW9uX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzUwMCBrYml0L3MnKTtcclxuICBhd2FpdCBleHBlY3QoY29tbW9uLmxvY2F0b3IoJyNkYXRhX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzIgTWJpdC9zJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignLnBhcmFtZXRlci1kZXRhaWxzW29wZW5dJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IHJlcGVhdFBhcmFtZXRlclJldHVybihwYWdlLCBwcm9qZWN0LCBwZW5kaW5nLCBbe3RlY2hub2xvZ3k6ICdjYW5fZmQnLFxuICAgIGZpZWxkczoge2FyYml0cmF0aW9uX2JpdHJhdGU6ICc1MDAga2JpdC9zJywgZGF0YV9iaXRyYXRlOiAnMSBNYml0L3MnLCBjYW5fZmRfZGF0YV9wcmVzY2FsZXI6ICcyJ30sXG4gICAgbmF0aXZlOiB7YXJiaXRyYXRpb25fYml0cmF0ZTogNTAwXzAwMCwgZGF0YV9iaXRyYXRlOiAxXzAwMF8wMDAsIGNhbl9mZF9kYXRhX3ByZXNjYWxlcjogMn0sXG4gICAgZWRpdEZpZWxkczogWydkYXRhX2JpdHJhdGUnLCAnY2FuX2ZkX2RhdGFfcHJlc2NhbGVyJ119XSk7XG4gIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSxwcm9qZWN0LGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3BlbmRpbmd9P3ZpZXc9c3RhdHVzYCkpLmRhdGEuY2Fub25pY2FsX2lkcykudG9FcXVhbChbXSk7XG4gIGV4cGVjdCgoYXdhaXQgYWxsT2JqZWN0cyhwYWdlLHByb2plY3QsJ2hhcmR3YXJlLW5vZGVzJykpKS50b0hhdmVMZW5ndGgoMCk7XG4gIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgdHJ1ZSxcclxuICAgIFsnU3lzdGVtJywgJ01vdG9yc3RldWVydW5nJywgJ0FuemVpZ2UnLCAnTW90b3JUZW1wZXJhdHVyZScsICdNb3RvclZhbHZlJ10pO1xyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCA1LCB1bmRlZmluZWQsIHtcclxuICAgIHNlZWQ6IDQyLCBkYXRhX2JpdHJhdGU6IDFfMDAwXzAwMCwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyOiAyLFxyXG4gIH0pO1xyXG4gIGV4cGVjdChhcnRpZmFjdHMuYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoMyk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnRyYW5zcG9ydF9leGNsdXNpb25zKS50b0hhdmVMZW5ndGgoMyk7XHJcbiAgY29uc3QgZmluaXNoZWQgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5pbmNsdWRlcyhgL3J1bnMvJHtjb250aW51aXR5LnJ1bklkfS9maW5pc2hgKVxyXG4gICAgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0ZlcnRpZyBzdGVsbGVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBleHBlY3QoKGF3YWl0IGZpbmlzaGVkKS5vaygpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cpLm5vdC50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KGVycm9ycykudG9FcXVhbChbXSk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCAuLi5jb250aW51aXR5LCAuLi5hcnRpZmFjdHMgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG5cclxuZm9yIChjb25zdCB0ZWNobm9sb2d5IG9mIFsnSTJDJywgJ01vZGJ1cyBSVFUnXSkge1xyXG4gIHRlc3QoYFJhc3BiZXJyeSBQaSAke3RlY2hub2xvZ3l9IHByb2plY3QgcmV0YWlucyBtb2RlbCBhbmQgYmxvY2tzIGluY29uc2lzdGVudCBuYXRpdmUgcGFyYW1ldGVycyBAbm9uYXV0b21vdGl2ZWAsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICAgIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1lbWJlZGRlZC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gICAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdQcm9qZWt0bmFtZScsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjZW5naW5lZXJpbmctcHJvamVjdC1uYW1lJykuZmlsbCgnVGVtcGVyYXR1cnJlZ2VsdW5nJyk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCh0ZWNobm9sb2d5ID09PSAnSTJDJ1xyXG4gICAgICA/ICcyIEFrdG9yZW4gZsO8ciBWZW50aWxlLCA0IFNlbnNvcmVuIGbDvHIgVGVtcGVyYXR1cmVuLCB1bmQgZWluIFJhc3BiZXJyeVBpJ1xyXG4gICAgICA6IGAyIEFrdG9yZW4gZsO8ciBWZW50aWxlLCA0IFNlbnNvcmVuIGbDvHIgVGVtcGVyYXR1cmVuLCB1bmQgZWluIFJhc3BiZXJyeVBpLiBFbWJlZGRlZCBTeXN0ZW1zLiBBbGxlIEdlcsOkdGUga29tbXVuaXppZXJlbiDDvGJlciAke3RlY2hub2xvZ3l9LiBQcsO8ZmUgdW5kIGFyYmVpdGUgYmlzIERhdGEgU2NpZW5jZSAmIEludGVsbGlnZW5jZS5gKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdOZXR6YXJjaGl0ZWt0dXInLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdyYWRpbycsIHsgbmFtZTogL1ZhcmlhbnRlIDAvIH0pLmNoZWNrKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnR2Vyw6R0ZXVtZmFuZycsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGlmICh0ZWNobm9sb2d5ID09PSAnSTJDJykge1xyXG4gICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdSYXNwYmVycnlQaTogQW5zY2hsdXNzJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ0kyQycpO1xyXG4gICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5TGFiZWwoJ1RlbXBlcmF0dXJzZW5zb3IxOiBBbnNjaGx1c3MnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgICAgZm9yIChjb25zdCBuYW1lIG9mIFsnUmFzcGJlcnJ5UGknLCAnVGVtcGVyYXR1cnNlbnNvcjEnLCAnVGVtcGVyYXR1cnNlbnNvcjInLCAnVGVtcGVyYXR1cnNlbnNvcjMnLCAnVGVtcGVyYXR1cnNlbnNvcjQnLCAnVmVudGlsYWt0b3IxJywgJ1ZlbnRpbGFrdG9yMiddKSB7XHJcbiAgICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoYCR7bmFtZX06IEFuc2NobHVzc2AsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdJMkMnKTtcclxuICAgICAgfVxyXG4gICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnU2Vuc29yIDE6IE1lc3NncsO2w59lJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ3NwZWVkJyk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlMYWJlbCgnVGVtcGVyYXR1cnNlbnNvcjE6IEFuc2NobHVzcycsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZVZhbHVlKCdJMkMnKTtcclxuICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1NlbnNvciAxOiBNZXNzZ3LDtsOfZScsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCd0ZW1wZXJhdHVyZScpO1xyXG4gICAgfVxyXG4gICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMTogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignT1BFTl9DTE9TRScpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeUxhYmVsKCdWZW50aWxha3RvcjI6IFN0ZWxsYmVmZWhsJywgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoJycpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMjogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignT1BFTl9DTE9TRScpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCB0cnVlLCBbJ1Jhc3BiZXJyeVBpJywgJ1RlbXBlcmF0dXJzZW5zb3IxJywgJ1RlbXBlcmF0dXJzZW5zb3IyJywgJ1RlbXBlcmF0dXJzZW5zb3IzJywgJ1RlbXBlcmF0dXJzZW5zb3I0JywgJ1ZlbnRpbGFrdG9yMScsICdWZW50aWxha3RvcjInXSwgZmFsc2UsIHVuZGVmaW5lZCwgdW5kZWZpbmVkLCB0cnVlKSlcclxuICAgICAgLnJlamVjdHMudG9UaHJvdygvV2l6YXJkIEJMT0NLRUQgYXQgcGFyYW1ldGVyczouKmJlc3TDpHRpZ3RlIEFuZ2FiZW4vKTtcclxuICAgIGNvbnN0IHdvcmtmbG93ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cnKTtcclxuICAgIGNvbnN0IGZpbmRpbmdzID0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24uYmxvY2tpbmdfZmluZGluZ3MgYXMgeyBjb2RlOiBzdHJpbmcgfVtdO1xyXG4gICAgZXhwZWN0KGZpbmRpbmdzLm1hcChpdGVtID0+IGl0ZW0uY29kZSkpLnRvQ29udGFpbignVEVDSE5PTE9HWV9QQVJBTUVURVJfREVQRU5ERU5DWV9NSVNNQVRDSCcpO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LnN0YXR1c2VzLnBhcmFtZXRlcnMpLnRvQmUoJ0lOX1BST0dSRVNTJyk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuYXJ0aWZhY3RfY2hlY2tzLnBhcmFtZXRlcnMuY29tcGxldGUpLnRvQmUoZmFsc2UpO1xyXG4gICAgY29uc3QgcmVxdWlyZWQgPSB3b3JrZmxvdy5hcnRpZmFjdF9jaGVja3MucGFyYW1ldGVycy5yZXF1aXJlZDtcclxuICAgIGV4cGVjdChyZXF1aXJlZC5wcm9maWxlX3ZhbHVlcykudG9CZShmYWxzZSk7XHJcbiAgICBjb25zdCBkZXZpY2VTb3VyY2UgPSB0ZWNobm9sb2d5ID09PSAnSTJDJyA/ICdpMmNfZGV2aWNlX3NvdXJjZScgOiAnbXJfZGV2aWNlX3NvdXJjZSc7XHJcbiAgICAvLyBUaGVzZSBzY2VuYXJpb3MgcmVtYWluIGJsb2NrZWQgYnkgcmVhbCBuYXRpdmUgZGVwZW5kZW5jaWVzLCBub3QgYnkgdGhlXHJcbiAgICAvLyBhYnNlbmNlIG9mIGEgcmVhbCBkZXZpY2UgcXVhbGlmaWNhdGlvbiBvciBmYWJyaWNhdGVkIHNvdXJjZSBpZGVudGlmaWVyLlxyXG4gICAgZXhwZWN0KHJlcXVpcmVkKS5ub3QudG9IYXZlUHJvcGVydHkoZGV2aWNlU291cmNlLCBmYWxzZSk7XHJcbiAgICBjb25zdCBuYXRpdmVUZWNobm9sb2d5ID0gdGVjaG5vbG9neSA9PT0gJ0kyQycgPyAnaTJjJyA6ICdtb2RidXNfcnR1JztcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5wYXJhbWV0ZXJzLnNpbXVsYXRpb25fcGFyYW1ldGVyX2Fzc3VtcHRpb25zW25hdGl2ZVRlY2hub2xvZ3ldLnZhbHVlcylcclxuICAgICAgLm5vdC50b0hhdmVQcm9wZXJ0eShkZXZpY2VTb3VyY2UpO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LmFydGlmYWN0X2NoZWNrcy5wYXJhbWV0ZXJzLnByb2ZpbGVfZmluZGluZ3Muc29tZSgoZmluZGluZzoge2NvZGU6IHN0cmluZ30pID0+XHJcbiAgICAgIGZpbmRpbmcuY29kZSA9PT0gJ1RFQ0hOT0xPR1lfUEFSQU1FVEVSX0RFUEVOREVOQ1lfTUlTTUFUQ0gnKSkudG9CZSh0cnVlKTtcclxuICAgIGNvbnN0IGV2aWRlbmNlUmV2aWV3ID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywge25hbWU6ICdCbG9ja2llcmVuZGUgUHJlZmxpZ2h0LUJlZnVuZGUnfSk7XHJcbiAgICBhd2FpdCBleHBlY3QoZXZpZGVuY2VSZXZpZXcpLnRvQ29udGFpblRleHQodGVjaG5vbG9neSA9PT0gJ0kyQycgPyAnaTJjX3B1bGx1cF9vaG1zJyA6ICdtcl9wZHVfYnl0ZXMnKTtcclxuICAgIGF3YWl0IGV4cGVjdChldmlkZW5jZVJldmlldy5nZXRCeVJvbGUoJ2xpbmsnLCB7bmFtZTogJ0JldHJvZmZlbmUgQW5nYWJlbiBiZWFyYmVpdGVuJ30pLmZpcnN0KCkpXHJcbiAgICAgIC50b0hhdmVBdHRyaWJ1dGUoJ2hyZWYnLCBuZXcgUmVnRXhwKGBtb2RlPXBhcmFtZXRlcnMuKnByb2plY3Q9JHtwcm9qZWN0fWApKTtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5zdGF0dXNlcy5zaW11bGF0aW9uKS50b0JlKCdFTVBUWScpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGV4cGVjdCh3b3JrZmxvdy5wYXJhbWV0ZXJzLnJhdGVfcmV2aWV3X3Byb3Bvc2Fscy5pMmMuc3RhdHVzKS50b0JlKCdSRVZJRVdfUkVRVUlSRUQnKTtcclxuICAgICAgZXhwZWN0KHdvcmtmbG93LnBhcmFtZXRlcnMucGFyYW1ldGVyX3Byb3ZlbmFuY2UuYml0cmF0ZS5zb3VyY2UpLnRvQmUoJ1RFQ0hOT0xPR1lfUFJPRklMRV9SRVZJRVdfUFJPUE9TQUwnKTtcclxuICAgIH1cclxuICAgIGNvbnN0IGludGVyZmFjZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1pbnRlcmZhY2VzJyk7XHJcbiAgICBleHBlY3QoaW50ZXJmYWNlcy5sZW5ndGgpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoNyk7XHJcbiAgICBleHBlY3QoaW50ZXJmYWNlcy5ldmVyeShpdGVtID0+ICEvYXV0b21vdGl2ZXxjYW58bGluL2kudGVzdChpdGVtLnRlY2hub2xvZ3kpKSkudG9CZSh0cnVlKTtcclxuICAgIGNvbnN0IGhhcmR3YXJlID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICAgIGV4cGVjdChoYXJkd2FyZS5ldmVyeShpdGVtID0+IGl0ZW0uZG9tYWluICE9PSAnYXV0b21vdGl2ZScpKS50b0JlKHRydWUpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGNvbnN0IHNpZ25hbHMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyk7XHJcbiAgICAgIGV4cGVjdChzaWduYWxzLnNvbWUoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdUZW1wZXJhdHVyX1RlbXBlcmF0dXJzZW5zb3IxJyAmJiBpdGVtLnVuaXQgPT09ICdkZWdDJykpLnRvQmUodHJ1ZSk7XHJcbiAgICB9XHJcbiAgICBleHBlY3QoKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnMpLnRvSGF2ZUxlbmd0aCgwKTtcclxuICAgIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnbm9uYXV0b21vdGl2ZS1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCB0ZWNobm9sb2d5LCBmaW5kaW5ncyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICB9KTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gc3RhcnRDYXB0dXJlZExhcmdlV2l6YXJkKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZykge1xyXG4gIGNvbnN0IHJ1bklkID0gcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IG9yaWdpbmFsID0gYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2UtNTAtMjUwLTI1MC50eHQnLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpO1xyXG4gIGNvbnN0IG1ldGFkYXRhID0gSlNPTi5wYXJzZShhd2FpdCByZWFkRmlsZShuZXcgVVJMKCcuL2ZpeHR1cmVzL3dpemFyZC1sYXJnZS01MC0yNTAtMjUwLmpzb24nLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpKTtcclxuICBjb25zdCBiYXNlbGluZSA9IEpTT04ucGFyc2UoYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2Utc2lnbmFsLWNvbnRyYWN0cy5qc29uJywgaW1wb3J0Lm1ldGEudXJsKSwgJ3V0ZjgnKSk7XHJcbiAgY29uc3QgcHJvbXB0ID0gb3JpZ2luYWwucmVwbGFjZSgvXi0gTGF1Zi1JRDouKiQvbSwgJy0gTGF1Zi1JRDogJyArIHJ1bklkKTtcclxuICBhd2FpdCByZXZpZXdWaXJ0dWFsVHJhbnNwb3J0cyhwYWdlLCBwcm9qZWN0LCB0cnVlKTtcbiAgLy8gUmVwbGF5IHRoZSBjYXB0dXJlZCwgYWxyZWFkeSBjb25maXJtZWQgaW5wdXQgdGhyb3VnaCB0aGUgbm9ybWFsIFNUQVJUIEFQSS5cclxuICAvLyBBbGwgcHJvcG9zYWwgaW5zcGVjdGlvbiwgYXBwcm92YWwsIGNvbnRpbnVhdGlvbiBhbmQgcmVsb2FkcyBiZWxvdyB1c2UgVUkuXHJcbiAgY29uc3Qgc3RhcnRlZCA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NoYXQnLCB7XHJcbiAgICBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0sIHRpbWVvdXQ6IDI0MF8wMDAsXHJcbiAgICBkYXRhOiB7IHByb21wdCwgd2l6YXJkX2NvbW1hbmQ6IHsgYWN0aW9uOiAnU1RBUlQnLCBydW5faWQ6IHJ1bklkLCBvcGVyYXRpb25faWQ6IHJhbmRvbVVVSUQoKSxcclxuICAgICAgdGFyZ2V0OiAnZGF0YV9zY2llbmNlX2ludGVsbGlnZW5jZScsIHdpemFyZF9jb250ZXh0OiB7IC4uLm1ldGFkYXRhLndpemFyZF9jb250ZXh0LCBwcm9qZWN0X2lkOiBwcm9qZWN0LCBydW5faWQ6IHJ1bklkIH0gfSB9LFxyXG4gIH0pO1xyXG4gIGlmICghc3RhcnRlZC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYEhUVFAgJHtzdGFydGVkLnN0YXR1cygpfTogJHsoYXdhaXQgc3RhcnRlZC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgcmV0dXJuIHsgcnVuSWQsIG1ldGFkYXRhLCBiYXNlbGluZSB9O1xyXG59XHJcblxyXG5mdW5jdGlvbiBsYXJnZVBhcmFtZXRlclNjZW5hcmlvcygpOiBQYXJhbWV0ZXJSZXR1cm5TY2VuYXJpb1tdIHtcclxuICByZXR1cm4gW1xyXG4gICAge3RlY2hub2xvZ3k6ICdsaW4nLCBmaWVsZHM6IHtsaW5fYml0cmF0ZV9icHM6ICcxOSwyIGtiaXQvcyd9LCBuYXRpdmU6IHtsaW5fYml0cmF0ZV9icHM6IDE5XzIwMH19LFxyXG4gICAge3RlY2hub2xvZ3k6ICdjYW5fZmQnLCBmaWVsZHM6IHthcmJpdHJhdGlvbl9iaXRyYXRlOiAnNTAwIGtiaXQvcycsIGRhdGFfYml0cmF0ZTogJzIgTWJpdC9zJ30sXHJcbiAgICAgIG5hdGl2ZToge2FyYml0cmF0aW9uX2JpdHJhdGU6IDUwMF8wMDAsIGRhdGFfYml0cmF0ZTogMl8wMDBfMDAwfX0sXHJcbiAgICAvLyBNYXRjaCB0aGUgdW5jaGFuZ2VkIGNhcHR1cmVkIDEwMC1NYml0L3MgcmVxdWVzdCBhbmQgZ2VudWluZWx5IGNoYW5nZVxyXG4gICAgLy8gdGhlIDEtR2JpdC9zIHByb2ZpbGUgc2VlZCwgc28gc2F2aW5nIGV4ZXJjaXNlcyB1c2VyLXZhbHVlIHByb3ZlbmFuY2UuXHJcbiAgICB7dGVjaG5vbG9neTogJ2V0aGVybmV0JywgZmllbGRzOiB7Yml0cmF0ZTogJzEwMCBNYml0L3MnfSwgbmF0aXZlOiB7Yml0cmF0ZTogMTAwXzAwMF8wMDB9LCBlZGl0RmllbGRzOiBbJ2JpdHJhdGUnXX0sXHJcbiAgXTtcclxufVxyXG5cclxudGVzdCgnZXhhY3QgY29uZmlybWVkIDUwLzI1MC8yNTAgcmVxdWVzdCBjb21wbGV0ZXMgdGhyb3VnaCByZWFsIHdpemFyZCByZXZpZXcgQGxhcmdlJywgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IGVycm9yczogc3RyaW5nW10gPSBbXTsgcGFnZS5vbigncGFnZWVycm9yJywgZXJyb3IgPT4gZXJyb3JzLnB1c2goZXJyb3IubWVzc2FnZSkpO1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1sYXJnZS0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IHsgcnVuSWQsIG1ldGFkYXRhLCBiYXNlbGluZSB9ID0gYXdhaXQgc3RhcnRDYXB0dXJlZExhcmdlV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGNvbnN0IHBhcmFtZXRlclJldHVyblJldmlld3M6IHN0cmluZ1tdID0gW107XG4gIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgZmFsc2UsIFtdLCB0cnVlLCBiYXNlbGluZS5zaWduYWxzLFxuICAgIHVuZGVmaW5lZCwgZmFsc2UsIGFzeW5jIChwcm9wb3NhbElkLCBwcm9wb3NhbFR5cGUpID0+IHtcbiAgICAgIGlmICghWydXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnLCAnV0laQVJEX1JPVVRJTkcnLCAnV0laQVJEX05FVFdPUktfVE9QT0xPR1knXS5pbmNsdWRlcyhwcm9wb3NhbFR5cGUpKSByZXR1cm47XG4gICAgICAvLyBPbmUgZnVsbCB0aHJlZS1idXMgY3ljbGUgcmVtYWlucyBpbnRlZ3JhdGVkIGF0IGV2ZXJ5IHJldmlldyBzdGFnZS5cclxuICAgICAgLy8gUmVwZWF0ZWQgdGhyZWUtc2VlZCBjb3ZlcmFnZSBoYXMgaXRzIG93biByZWFsIGxhcmdlIGNhc2VzIGJlbG93LFxyXG4gICAgICAvLyBwcmVzZXJ2aW5nIHRoZSBjb250cmFjdHVhbCAyMC1taW51dGUgd2hvbGUtd29ya2Zsb3cgY2FzZSBsaW1pdC5cclxuICAgICAgLy8gRWFjaCBwaGFzZSBtdXN0IHJlYWxseSBlZGl0IHRoZSBzZWVkOiBhbiBpZGVudGljYWwgc2F2ZSBjb3JyZWN0bHlcclxuICAgICAgLy8gbGVhdmVzIHRoZSBleGlzdGluZyBwcm9wb3NhbCBWQUxJREFURUQgaW5zdGVhZCBvZiBtYWtpbmcgaXQgT1VUREFURUQuXHJcbiAgICAgIGNvbnN0IHJldmlld1NlZWQgPSBwcm9wb3NhbFR5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnID8gNDFcclxuICAgICAgICA6IHByb3Bvc2FsVHlwZSA9PT0gJ1dJWkFSRF9ST1VUSU5HJyA/IDQzIDogNDI7XHJcbiAgICAgIGF3YWl0IHJlcGVhdFBhcmFtZXRlclJldHVybihwYWdlLCBwcm9qZWN0LCBwcm9wb3NhbElkLCBsYXJnZVBhcmFtZXRlclNjZW5hcmlvcygpLCBbcmV2aWV3U2VlZF0pO1xyXG4gICAgICBwYXJhbWV0ZXJSZXR1cm5SZXZpZXdzLnB1c2gocHJvcG9zYWxUeXBlKTtcbiAgICB9KTtcbiAgZXhwZWN0KHBhcmFtZXRlclJldHVyblJldmlld3MpLnRvRXF1YWwoWydXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnLCAnV0laQVJEX1JPVVRJTkcnLCAnV0laQVJEX05FVFdPUktfVE9QT0xPR1knXSk7XG4gIGV4cGVjdChjb250aW51aXR5LnJ1bklkKS50b0JlKHJ1bklkKTtcclxuICBjb25zdCBoYXJkd2FyZSA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgZXhwZWN0KGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0uZGV2aWNlX3R5cGUgPT09ICdTZW5zb3JDb250cm9sbGVyJykpLnRvSGF2ZUxlbmd0aCgyNTApO1xyXG4gIGV4cGVjdChoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLmRldmljZV90eXBlID09PSAnQWN0dWF0b3JDb250cm9sbGVyJykpLnRvSGF2ZUxlbmd0aCgyNTApO1xyXG4gIGV4cGVjdChoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLmRldmljZV90eXBlID09PSAnRUNVJykubGVuZ3RoKS50b0JlR3JlYXRlclRoYW5PckVxdWFsKDUwKTtcclxuICBjb25zdCBhcnRpZmFjdHMgPSBhd2FpdCB2ZXJpZnlBcnRpZmFjdHMocGFnZSwgcHJvamVjdCwgMTQwNCwgdW5kZWZpbmVkLCB1bmRlZmluZWQsIHtcbiAgICBsaW46IHtiaXRyYXRlOiAxOV8yMDB9LCBjYW5fZmQ6IHthcmJpdHJhdGlvbl9iaXRyYXRlOiA1MDBfMDAwLCBkYXRhX2JpdHJhdGU6IDJfMDAwXzAwMH0sXG4gICAgZXRoZXJuZXQ6IHtiaXRyYXRlOiAxMDBfMDAwXzAwMH0sXHJcbiAgfSk7XG4gIGNvbnN0IGV4Y2x1ZGVkU2lnbmFsSWRzID0gbmV3IFNldChhcnRpZmFjdHMuYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS50cmFuc3BvcnRfZXhjbHVzaW9uc1xyXG4gICAgLmZsYXRNYXAoKGl0ZW06IHsgc2lnbmFsX2lkczogc3RyaW5nW10gfSkgPT4gaXRlbS5zaWduYWxfaWRzKSk7XHJcbiAgZXhwZWN0KGV4Y2x1ZGVkU2lnbmFsSWRzLnNpemUpLnRvQmUoMjM1KTtcclxuICBleHBlY3QoYXJ0aWZhY3RzLmFzc2Vzc21lbnQub2JzZXJ2ZWRfc2lnbmFsX2NvdW50KS50b0JlKDExNjkpO1xyXG4gIGF3YWl0IHZlcmlmeVNpZ25hbENvbnRyYWN0cyhwYWdlLCBwcm9qZWN0LCBiYXNlbGluZS5zaWduYWxzKTtcclxuICBleHBlY3QoYXJ0aWZhY3RzLmpvYikudG9CZShjb250aW51aXR5LnJlc3RhcnRlZEpvYklkKTtcclxuICBleHBlY3QoZXJyb3JzKS50b0VxdWFsKFtdKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2V2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIGZpeHR1cmU6IG1ldGFkYXRhLnJlcXVlc3Rfc2hhMjU2LCAuLi5jb250aW51aXR5LCAuLi5hcnRpZmFjdHMgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG5cclxuZm9yIChjb25zdCB0YXJnZXQgb2YgW1xyXG4gIHsgbGFiZWw6ICdtb2RlbCcsIHR5cGU6ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnLCBzdGVwOiAnZW5naW5lZXJpbmdfbW9kZWwnIH0sXHJcbiAgeyBsYWJlbDogJ3JvdXRpbmcnLCB0eXBlOiAnV0laQVJEX1JPVVRJTkcnLCBzdGVwOiAncm91dGluZycgfSxcclxuICB7IGxhYmVsOiAndG9wb2xvZ3knLCB0eXBlOiAnV0laQVJEX05FVFdPUktfVE9QT0xPR1knLCBzdGVwOiAnbmV0d29ya19lZGl0b3InIH0sXHJcbl0pIHtcclxuICB0ZXN0KGBleGFjdCBjb25maXJtZWQgNTAvMjUwLzI1MCAke3RhcmdldC5sYWJlbH0gcGFyYW1ldGVyIHJldHVybiByZXZpZXcgb25seSBAbGFyZ2UtcmV0dXJuYCwgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gICAgY29uc3QgZXJyb3JzOiBzdHJpbmdbXSA9IFtdOyBwYWdlLm9uKCdwYWdlZXJyb3InLCBlcnJvciA9PiBlcnJvcnMucHVzaChlcnJvci5tZXNzYWdlKSk7XHJcbiAgICBjb25zdCBwcm9qZWN0ID0gYG5pcy1lMmUtbGFyZ2UtcmV0dXJuLSR7dGFyZ2V0LmxhYmVsfS1gICsgcmFuZG9tVVVJRCgpO1xyXG4gICAgY29uc3QgeyBydW5JZCwgbWV0YWRhdGEsIGJhc2VsaW5lIH0gPSBhd2FpdCBzdGFydENhcHR1cmVkTGFyZ2VXaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgICBjb25zdCBjb250aW51aXR5ID0gYXdhaXQgY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIGZhbHNlLCBbXSwgZmFsc2UsIGJhc2VsaW5lLnNpZ25hbHMsXHJcbiAgICAgIHVuZGVmaW5lZCwgZmFsc2UsIGFzeW5jIChwcm9wb3NhbElkLCBwcm9wb3NhbFR5cGUpID0+IHtcclxuICAgICAgICBpZiAocHJvcG9zYWxUeXBlICE9PSB0YXJnZXQudHlwZSkgcmV0dXJuO1xyXG4gICAgICAgIGF3YWl0IHJlcGVhdFBhcmFtZXRlclJldHVybihwYWdlLCBwcm9qZWN0LCBwcm9wb3NhbElkLCBsYXJnZVBhcmFtZXRlclNjZW5hcmlvcygpKTtcclxuICAgICAgICByZXR1cm4gJ1NUT1BfQUZURVJfUkVWSUVXJztcclxuICAgICAgfSk7XHJcbiAgICBleHBlY3QoY29udGludWl0eS5ydW5JZCkudG9CZShydW5JZCk7XHJcbiAgICBleHBlY3QoY29udGludWl0eS5yZXZpZXdPbmx5Py5wcm9wb3NhbFR5cGUpLnRvQmUodGFyZ2V0LnR5cGUpO1xyXG4gICAgY29uc3Qgd29ya2Zsb3cgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbikudG9NYXRjaE9iamVjdCh7IHJ1bl9pZDogcnVuSWQsIHN0YXRlOiAnUkVWSUVXX1JFUVVJUkVEJywgc3RlcDogdGFyZ2V0LnN0ZXAgfSk7XHJcbiAgICBleHBlY3QoZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXMuc2ltdWxhdGlvbikpLnRvQmUoZmFsc2UpO1xyXG4gICAgY29uc3QgcHJvcG9zYWwgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtjb250aW51aXR5LnJldmlld09ubHkhLnByb3Bvc2FsSWR9P3ZpZXc9c3RhdHVzYCk7XHJcbiAgICBleHBlY3QocHJvcG9zYWwuZGF0YS5zdGF0dXMpLnRvQmUoJ1ZBTElEQVRFRCcpO1xyXG4gICAgZXhwZWN0KGVycm9ycykudG9FcXVhbChbXSk7XHJcbiAgICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ3Jldmlldy1vbmx5LWV2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIGZpeHR1cmU6IG1ldGFkYXRhLnJlcXVlc3Rfc2hhMjU2LFxyXG4gICAgICBjb3ZlcmFnZTogJ1JFVklFV19DT05USU5VSVRZX09OTFknLCBjeWNsZXM6IDMsIHRlY2hub2xvZ2llczogWydsaW4nLCAnY2FuX2ZkJywgJ2V0aGVybmV0J10sIC4uLmNvbnRpbnVpdHkgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgfSk7XHJcbn1cclxuXHJcbnRlc3QoJ2EgcmVhbCBBTUVORCBhZnRlciBtb2RlbCBhcHByb3ZhbCBhZGRzIHRoZSByZXF1ZXN0ZWQgc2Vuc29yIGFuZCByZXVzZXMgaXRzIG5ldHdvcmtzIEBhbWVuZCcsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtYW1lbmQtJyArIHJhbmRvbVVVSUQoKTtcclxuICBhd2FpdCByZXZpZXdWaXJ0dWFsVHJhbnNwb3J0cyhwYWdlLCBwcm9qZWN0KTtcclxuICBjb25zdCBydW5JZCA9IHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBncmFwaCA9IFtcclxuICAgIHsgY2x1c3Rlcl9pZDogJ2RyaXZlJywgbmV0d29ya19pZDogJ2Nhbl9mZCcsIG5ldHdvcmtfbGFiZWw6ICdDQU4tRkQnLCBidXNfbmFtZTogJ0RyaXZlJyxcclxuICAgICAgY29udHJvbGxlcnM6IFt7IGVjdTogJ01vdG9yc3RldWVydW5nJywgc2Vuc29yczogW10gYXMgc3RyaW5nW10sIGFjdHVhdG9yczogW10gfV0sXHJcbiAgICAgIGhtaV9yb3V0ZXM6IFt7IHNvdXJjZTogJ01vdG9yc3RldWVydW5nJywgdGFyZ2V0OiAnQW56ZWlnZScgfSwgeyBzb3VyY2U6ICdBbnplaWdlJywgdGFyZ2V0OiAnTW90b3JzdGV1ZXJ1bmcnIH0sXHJcbiAgICAgICAgeyBzb3VyY2U6ICdTeXN0ZW0nLCB0YXJnZXQ6ICdBbnplaWdlJyB9XSB9LFxyXG4gICAgeyBjbHVzdGVyX2lkOiAnZGlzcGxheScsIG5ldHdvcmtfaWQ6ICdldGhlcm5ldCcsIG5ldHdvcmtfbGFiZWw6ICdFdGhlcm5ldCcsIGJ1c19uYW1lOiAnRGlzcGxheScsXHJcbiAgICAgIGNvbnRyb2xsZXJzOiBbeyBlY3U6ICdBbnplaWdlJywgc2Vuc29yczogW10gYXMgc3RyaW5nW10sIGFjdHVhdG9yczogW10gfV0gfSxcclxuICBdO1xyXG4gIGNvbnN0IHByb21wdCA9IGBTdHJ1a3R1cmllcnRlIFZvcmdhYmVuIGZ1ZXIgZGVuIEVuZ2luZWVyaW5nLUFnZW50ZW46XHJcbi0gTGF1Zi1JRDogJHtydW5JZH1cclxuLSBJbmR1c3RyaWU6IEF1dG9tb3RpdmVcclxuLSBOZXR6d2Vya3RlY2hub2xvZ2llbjogQ0FOLUZEIChjYW5fZmQpOyBFdGhlcm5ldCAoZXRoZXJuZXQpXHJcbkNBTi1GRDogNTAwIGtiaXQvcyBhcmJpdHJhdGlvbiwgMiBNYml0L3MgZGF0YVxyXG5DQU46IDUwMCBrYml0L3NcclxuRXRoZXJuZXQ6IDEwMCBNYml0L3NcclxuLSBIYXJkd2FyZS1Tb2xsd2VydGU6IHtcImdhdGV3YXlzXCI6MSxcImVjdXNcIjoyLFwic2Vuc29yc1wiOjAsXCJhY3R1YXRvcnNcIjowfVxyXG4tIFN5c3RlbWNsdXN0ZXItR3JhcGg6ICR7SlNPTi5zdHJpbmdpZnkoZ3JhcGgpfVxyXG5Lb25rcmV0ZSBBdWZnYWJlIGRlcyBOdXR6ZXJzLCBwZXIgV2l6YXJkLVVlYmVybmVobWVuIGJlc3RhZXRpZ3Q6XHJcbk1vdG9yc3RldWVydW5nIHVuZCBBbnplaWdlIG1pdCBlaW5lbSB6ZW50cmFsZW4gR2F0ZXdheSBTeXN0ZW0gdmVyYmluZGVuLmA7XHJcbiAgY29uc3Qgc3RhcnRlZCA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NoYXQnLCB7XHJcbiAgICBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0sIHRpbWVvdXQ6IDEyMF8wMDAsXHJcbiAgICBkYXRhOiB7IHByb21wdCwgd2l6YXJkX2NvbW1hbmQ6IHsgYWN0aW9uOiAnU1RBUlQnLCBydW5faWQ6IHJ1bklkLCBvcGVyYXRpb25faWQ6IHJhbmRvbVVVSUQoKSxcclxuICAgICAgdGFyZ2V0OiAnZGF0YV9zY2llbmNlX2ludGVsbGlnZW5jZScsIHdpemFyZF9jb250ZXh0OiB7IHByb2plY3RfaWQ6IHByb2plY3QsIHJ1bl9pZDogcnVuSWQsXHJcbiAgICAgICAgcHJvamVjdF9uYW1lOiAnRTJFIGFtZW5kbWVudCcsIHNjb3BlX2lkczogc3RlcHMsIG1vZGU6ICdmdWxsJyxcclxuICAgICAgICBwcm9jZXNzX2lkczogWydkZWZhdWx0cycsICdyZXZpZXdfZ2F0ZScsICdhcHByb3ZlX2FmdGVyX2FsbG93J10sIHRhc2s6ICdNb3RvcnN0ZXVlcnVuZyB1bmQgQW56ZWlnZSBhbiBTeXN0ZW0nIH0gfSB9LFxyXG4gIH0pO1xyXG4gIGlmICghc3RhcnRlZC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYEhUVFAgJHtzdGFydGVkLnN0YXR1cygpfTogJHsoYXdhaXQgc3RhcnRlZC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgbGV0IG9yaWdpbmFsTmV0d29ya3M6IHN0cmluZ1tdID0gW107XHJcbiAgY29uc3QgYW1lbmQgPSBhc3luYyAoKSA9PiB7XHJcbiAgICBvcmlnaW5hbE5ldHdvcmtzID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93JykpLnBhcmFtZXRlcnMubmV0d29ya3NcclxuICAgICAgLm1hcCgoaXRlbTogeyBpZDogc3RyaW5nIH0pID0+IGl0ZW0uaWQpLnNvcnQoKTtcclxuICAgIGV4cGVjdChvcmlnaW5hbE5ldHdvcmtzKS50b0hhdmVMZW5ndGgoMik7XHJcbiAgICBncmFwaFswXS5jb250cm9sbGVyc1swXS5zZW5zb3JzLnB1c2goJ01vdG9yVGVtcGVyYXR1cmUnKTtcclxuICAgIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XHJcbiAgICBjb25zdCBleHBhbmQgPSBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdFcmfDpG56ZW4nLCBleGFjdDogdHJ1ZSB9KTtcclxuICAgIGF3YWl0IGV4cGVjdChleHBhbmQpLnRvQmVFbmFibGVkKHsgdGltZW91dDogMTIwXzAwMCB9KTtcclxuICAgIGF3YWl0IGV4cGFuZC5jbGljaygpO1xyXG4gICAgY29uc3QgZmllbGQgPSBkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyZ8OkbnplbicsIGV4YWN0OiB0cnVlIH0pLmdldEJ5Um9sZSgndGV4dGJveCcpO1xyXG4gICAgYXdhaXQgZmllbGQuZmlsbCgnRXJnw6RuemUgTW90b3JUZW1wZXJhdHVyZSBhbHMgU2Vuc29yIGRlciBNb3RvcnN0ZXVlcnVuZy4gRGllIHZvbGxzdMOkbmRpZ2UgYWt0dWFsaXNpZXJ0ZSBGcmVpZ2FiZSBsYXV0ZXQ6XFxuJ1xyXG4gICAgICArICctIEhhcmR3YXJlLVNvbGx3ZXJ0ZToge1wiZ2F0ZXdheXNcIjoxLFwiZWN1c1wiOjIsXCJzZW5zb3JzXCI6MSxcImFjdHVhdG9yc1wiOjB9XFxuJ1xyXG4gICAgICArICctIFN5c3RlbWNsdXN0ZXItR3JhcGg6ICcgKyBKU09OLnN0cmluZ2lmeShncmFwaCkpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRXJnw6RuenVuZyBhbmFseXNpZXJlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBleHBlY3QoZmllbGQpLm5vdC50b0JlVmlzaWJsZSh7IHRpbWVvdXQ6IDEyMF8wMDAgfSk7XHJcbiAgfTtcclxuICBjb25zdCBjb250aW51aXR5ID0gYXdhaXQgY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIGZhbHNlLCBbJ01vdG9yc3RldWVydW5nJywgJ0FuemVpZ2UnXSwgZmFsc2UsIHVuZGVmaW5lZCwgYW1lbmQpO1xyXG4gIGNvbnN0IGhhcmR3YXJlID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICBjb25zdCBvd25lciA9IGhhcmR3YXJlLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdNb3RvcnN0ZXVlcnVuZycpO1xyXG4gIGNvbnN0IHNlbnNvcnMgPSBoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdNb3RvclRlbXBlcmF0dXJlJyk7XHJcbiAgZXhwZWN0KHNlbnNvcnMpLnRvSGF2ZUxlbmd0aCgxKTtcclxuICBleHBlY3Qoc2Vuc29yc1swXS5pZGVudGl0eS5zeXN0ZW1fb3duZXJfaWQpLnRvQmUob3duZXIuaWQpO1xyXG4gIGNvbnN0IHNlbnNvck5ldHdvcmsgPSAnRHJpdmUtSU8tbW90b3JzdGV1ZXJ1bmctY2FuLWZkLVMwMSc7XHJcbiAgY29uc3QgbmV0d29ya3MgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cnKSkucGFyYW1ldGVycy5uZXR3b3JrcztcclxuICBleHBlY3QobmV0d29ya3MubWFwKChpdGVtOiB7IGlkOiBzdHJpbmcgfSkgPT4gaXRlbS5pZCkuc29ydCgpKS50b0VxdWFsKFsuLi5vcmlnaW5hbE5ldHdvcmtzLCBzZW5zb3JOZXR3b3JrXS5zb3J0KCkpO1xyXG4gIGV4cGVjdChuZXcgU2V0KG5ldHdvcmtzLm1hcCgoaXRlbTogeyBuYW1lOiBzdHJpbmcgfSkgPT4gaXRlbS5uYW1lKSkuc2l6ZSkudG9CZShuZXR3b3Jrcy5sZW5ndGgpO1xyXG4gIGNvbnN0IHRvcG9sb2d5ID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L25ldHdvcmstdmlldycpKS50b3BvbG9neTtcclxuICBjb25zdCBsb2NhbEVkZ2UgPSB0b3BvbG9neS5lZGdlcy5maW5kKChlZGdlOiBhbnkpID0+IGVkZ2UucGh5c2ljYWxOZXR3b3JrSWQgPT09IHNlbnNvck5ldHdvcmspO1xyXG4gIGV4cGVjdChsb2NhbEVkZ2UpLnRvQmVUcnV0aHkoKTtcclxuICBleHBlY3QobG9jYWxFZGdlLmJ1cykudG9CZSgnY2FuX2ZkJyk7XHJcbiAgZXhwZWN0KE9iamVjdC52YWx1ZXMobG9jYWxFZGdlLnJvdXRpbmdNZXRhZGF0YSkpLnRvQ29udGFpbkVxdWFsKGV4cGVjdC5vYmplY3RDb250YWluaW5nKHtcclxuICAgIHNvdXJjZTogc2Vuc29yc1swXS5pZCwgdGFyZ2V0OiBvd25lci5pZCwgYXBwcm92YWxTdGF0ZTogJ0FQUFJPVkVEJywgcHJvdG9jb2w6ICdDQU5fRkQnLFxyXG4gIH0pKTtcclxuICBmb3IgKGNvbnN0IFtzaWRlLCBoYXJkd2FyZUlkXSBvZiBbWydzb3VyY2UnLCBzZW5zb3JzWzBdLmlkXSwgWyd0YXJnZXQnLCBvd25lci5pZF1dKSB7XHJcbiAgICBjb25zdCBub2RlID0gdG9wb2xvZ3kubm9kZXMuZmluZCgoaXRlbTogYW55KSA9PiBpdGVtLmlkID09PSBsb2NhbEVkZ2Vbc2lkZV0pO1xyXG4gICAgZXhwZWN0KG5vZGUuZW5naW5lZXJpbmdJZCkudG9CZShoYXJkd2FyZUlkKTtcclxuICAgIGV4cGVjdChub2RlLnBvcnRzKS50b0NvbnRhaW5FcXVhbChleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7IGlkOiBsb2NhbEVkZ2Vbc2lkZSArICdQb3J0J10sXHJcbiAgICAgIGJ1czogJ2Nhbl9mZCcsIHBoeXNpY2FsTmV0d29ya0lkOiBzZW5zb3JOZXR3b3JrIH0pKTtcclxuICB9XHJcbiAgY29uc3QgYXJ0aWZhY3RzID0gYXdhaXQgdmVyaWZ5QXJ0aWZhY3RzKHBhZ2UsIHByb2plY3QsIDEpO1xyXG4gIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnYW1lbmRtZW50LWV2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIC4uLmNvbnRpbnVpdHksIC4uLmFydGlmYWN0cyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxufSk7XHJcblxyXG4vLyBSZWFsIGlzb2xhdGVkIFVJIC0+IHBlcnNpc3RlZCBtb2RlbCBib3VuZGFyeSByZWdyZXNzaW9uLCBub3QgbmluZS1zdGFnZSBjb21wbGV0aW9uIHByb29mLlxyXG50ZXN0KCdyZXZpZXdhYmxlIGZ1bmN0aW9uYWwgVFgvUlggT0ZGIHN1cnZpdmVzIHJlcXVlc3QgcmVsb2FkIGFuZCBjYW5vbmljYWwgbW9kZWwgYWRvcHRpb24gQHR4cngnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXR4cngtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdQcm9qZWt0bmFtZScsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cubG9jYXRvcignI2VuZ2luZWVyaW5nLXByb2plY3QtbmFtZScpLmZpbGwoJ1RYIFJYIGZ1bmN0aW9uYWwgcGFydG5lcnMnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCgnRXJ6ZXVnZSBlaW4gQXV0b21vdGl2ZSBDQU4tRkQgTmV0endlcmsgbWl0IGVpbmVtIEdhdGV3YXkgU3lzdGVtIHVuZCBkZW4gRUNVcyBNb3RvcnN0ZXVlcnVuZywgR2V0cmllYmVzdGV1ZXJ1bmcgdW5kIEVsZWt0cm9tb3RvcnN0ZXVlcnVuZy4gRGllIGJlcmVjaG5ldGVuIEZ1bmt0aW9uc2F1c2fDpG5nZSBkaWVuZW4gZGVyIEFudHJpZWJza29vcmRpbmF0aW9uLiBDb250cm9sbGVyc3RhdHVzIGJsZWlidCBpbnRlcm4uXFxuQ0FOLUZEOiA1MDAga2JpdC9zIGFyYml0cmF0aW9uLCAyIE1iaXQvcyBkYXRhJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ0dlcsOkdGV1bWZhbmcnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQXV0b21vdGl2ZSAvIFZlaGljbGUgw7xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGZvciAoY29uc3QgW2xhYmVsLCB2YWx1ZV0gb2YgW1snR2F0ZXdheXMnLCAnMSddLCBbJ0NvbnRyb2xsZXInLCAnMyddLCBbJ1NlbnNvcmVuJywgJzAnXSwgWydBa3RvcmVuJywgJzAnXV0pIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKGAke2xhYmVsfTogdmVyYmluZGxpY2hlIEFuemFobGAsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCh2YWx1ZSk7XHJcbiAgY29uc3QgdHhyeCA9IGRpYWxvZy5sb2NhdG9yKCdkZXRhaWxzJykuZmlsdGVyKHsgaGFzOiBwYWdlLmxvY2F0b3IoJ3N1bW1hcnknKS5maWx0ZXIoeyBoYXNUZXh0OiAvXlRYXFwvUlgvIH0pIH0pLmZpcnN0KCk7XHJcbiAgYXdhaXQgZXhwZWN0KHR4cngpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgdHhyeC5sb2NhdG9yKCdzdW1tYXJ5JykuY2xpY2soKTtcclxuICBjb25zdCBzZWxlY3RlZCA9IHR4cnguZ2V0QnlSb2xlKCdzd2l0Y2gnLCB7IG5hbWU6ICdNb3RvckRyZWhtb21lbnRJc3Qg4oaSIEdldHJpZWJlc3RldWVydW5nJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgYXdhaXQgZXhwZWN0KHNlbGVjdGVkKS50b0JlQ2hlY2tlZCgpOyBhd2FpdCBzZWxlY3RlZC51bmNoZWNrKCk7XHJcbiAgY29uc3Qgc3RhcnRSZXF1ZXN0ID0gcGFnZS53YWl0Rm9yUmVxdWVzdChyZXF1ZXN0ID0+IHJlcXVlc3QudXJsKCkuZW5kc1dpdGgoJy9hcGkvYWdlbnQvY2hhdCcpICYmIHJlcXVlc3QubWV0aG9kKCkgPT09ICdQT1NUJyAmJiByZXF1ZXN0LnBvc3REYXRhSlNPTigpPy53aXphcmRfY29tbWFuZD8uYWN0aW9uID09PSAnU1RBUlQnKTtcclxuICBmb3IgKGxldCBzdGVwID0gMDsgc3RlcCA8IDEwOyBzdGVwKyspIHtcclxuICAgIGNvbnN0IGJ1dHRvbiA9IGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoYnV0dG9uKS50b0JlRW5hYmxlZCgpOyBjb25zdCBsYWJlbCA9IGF3YWl0IGJ1dHRvbi5pbm5lclRleHQoKTsgYXdhaXQgYnV0dG9uLmNsaWNrKCk7XHJcbiAgICBpZiAobGFiZWwgPT09ICfDnGJlcm5laG1lbicgfHwgbGFiZWwgPT09ICdBdWZ0cmFnIHN0YXJ0ZW4nKSBicmVhaztcclxuICB9XHJcbiAgY29uc3QgY29udGV4dCA9IChhd2FpdCBzdGFydFJlcXVlc3QpLnBvc3REYXRhSlNPTigpLndpemFyZF9jb21tYW5kLndpemFyZF9jb250ZXh0O1xyXG4gIGNvbnN0IHN1Ym1pdHRlZCA9IGNvbnRleHQuc3lzdGVtX2NsdXN0ZXJfYXNzaWdubWVudHMuZmxhdE1hcCgoY2x1c3RlcjogYW55KSA9PiBjbHVzdGVyLmZ1bmN0aW9uYWxfcm91dGVzID8/IFtdKTtcclxuICBjb25zdCBvZmYgPSBzdWJtaXR0ZWQuZmluZCgocm91dGU6IGFueSkgPT4gcm91dGUuc291cmNlID09PSAnTW90b3JzdGV1ZXJ1bmcnICYmIHJvdXRlLnRhcmdldCA9PT0gJ0dldHJpZWJlc3RldWVydW5nJyk7XHJcbiAgZXhwZWN0KG9mZi5zaWduYWxzKS50b0VxdWFsKFtdKTsgZXhwZWN0KG9mZi5leGNsdWRlZF9zaWduYWxzKS50b0VxdWFsKFsnTW90b3JEcmVobW9tZW50SXN0J10pO1xyXG4gIGxldCBwcm9wb3NhbDogYW55O1xyXG4gIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcclxuICAgIGNvbnN0IGNvbnZlcnNhdGlvbiA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpO1xyXG4gICAgaWYgKCFjb252ZXJzYXRpb24uZGF0YS5hY3RpdmVfcHJvcG9zYWwpIHJldHVybiBmYWxzZTtcclxuICAgIHByb3Bvc2FsID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke2NvbnZlcnNhdGlvbi5kYXRhLmFjdGl2ZV9wcm9wb3NhbH1gKSkuZGF0YTtcclxuICAgIHJldHVybiBwcm9wb3NhbC5wcm9wb3NhbF90eXBlID09PSAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJztcclxuICB9LCB7IHRpbWVvdXQ6IDE4MF8wMDAgfSkudG9CZSh0cnVlKTtcclxuICBhd2FpdCBwYWdlLnJlbG9hZCgpOyBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGNvbnN0IGZpbmRpbmdzID0gcHJvcG9zYWwudmFsaWRhdGlvbl9yZXN1bHQuZmluZGluZ3MuZmlsdGVyKChpdGVtOiBhbnkpID0+IGl0ZW0uY29kZSA9PT0gJ0NBUEFDSVRZX1VOVkVSSUZJRUQnKTtcclxuICBpZiAoZmluZGluZ3MubGVuZ3RoKSB7XHJcbiAgICBjb25zdCByZXZpZXcgPSBwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnUHLDvGZiZWZ1bmRlIGRlcyBWb3JzY2hsYWdzJyB9KTtcclxuICAgIGF3YWl0IGV4cGVjdChyZXZpZXcpLnRvQ29udGFpblRleHQoYCR7cHJvcG9zYWwudmFsaWRhdGlvbl9yZXN1bHQuZmluZGluZ3MubGVuZ3RofSBQcsO8ZmJlZnVuZGVgKTtcclxuICAgIGF3YWl0IGV4cGVjdChyZXZpZXcuZ2V0QnlSb2xlKCdsaW5rJywgeyBuYW1lOiAnVGVjaG5vbG9naWVwYXJhbWV0ZXIgYmVhcmJlaXRlbiB1bmQgYmVzdMOkdGlnZW4nIH0pLmZpcnN0KCkpLnRvSGF2ZUF0dHJpYnV0ZSgnaHJlZicsIG5ldyBSZWdFeHAoYHByb2plY3Q9JHtwcm9qZWN0fWApKTtcclxuICAgIGF3YWl0IHJldmlldy5sb2NhdG9yKCdzdW1tYXJ5JykuZmlyc3QoKS5jbGljaygpOyBhd2FpdCBleHBlY3QocmV2aWV3LmdldEJ5Um9sZSgnbmF2aWdhdGlvbicsIHsgbmFtZTogJ0JlZnVuZGUgZHVyY2hibMOkdHRlcm4nIH0pLmZpcnN0KCkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgfVxyXG4gIGNvbnN0IGFwcGx5ID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4gcmVzcG9uc2UudXJsKCkuaW5jbHVkZXMoYC9wcm9wb3NhbHMvJHtwcm9wb3NhbC5wcm9wb3NhbF9pZH0vYXBwcm92ZS1hcHBseWApICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRnJlaWdlYmVuLCDDvGJlcm5laG1lbiAmIGZvcnRmYWhyZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpOyBleHBlY3QoKGF3YWl0IGFwcGx5KS5vaygpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IG5vZGVzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICBjb25zdCBtZXNzYWdlcyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ21lc3NhZ2VzJyk7IGNvbnN0IHNpZ25hbHMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyk7XHJcbiAgY29uc3Qgc2lnbmFsID0gc2lnbmFscy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnTW90b3JEcmVobW9tZW50SXN0Jyk7IGV4cGVjdChzaWduYWwpLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXMuZmluZChpdGVtID0+IGl0ZW0uaWQgPT09IHNpZ25hbC5tZXNzYWdlX2lkKTtcclxuICBjb25zdCBnZWFyYm94ID0gbm9kZXMuZmluZChpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ0dldHJpZWJlc3RldWVydW5nJyk7XHJcbiAgY29uc3QgZW1vdG9yID0gbm9kZXMuZmluZChpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ0VsZWt0cm9tb3RvcnN0ZXVlcnVuZycpO1xyXG4gIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdC5zY29wZSkudG9CZSgnRlVOQ1RJT05fT1VUUFVUJyk7XHJcbiAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LmNvbnN1bWVyX3JlZnMpLm5vdC50b0NvbnRhaW4oZ2VhcmJveC5pZCk7XHJcbiAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LmNvbnN1bWVyX3JlZnMpLnRvQ29udGFpbihlbW90b3IuaWQpO1xyXG4gIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnZnVuY3Rpb25hbC10eHJ4LWV2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIG9mZiwgbWVzc2FnZSB9KSwgY29udGVudFR5cGU6ICdhcHBs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