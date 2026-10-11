// 04a9641d4572d3540005c5e1efefd1d06b6a00cf
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
    snapshot: snapshot.id,
    trace_events: full.result.trace.events,
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
        expect(saved.parameters.parameter_provenance.duration_s).toEqual({
          source: 'TECHNOLOGY_DEFAULT',
          value: 1
        });
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
  page,
  browser
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
  await expect(page).toHaveURL(new RegExp(`/studio/results\\?snapshot=${artifacts.snapshot}&project=${project}$`));
  const selectedRun = page.locator(`.result-run-list button[data-snapshot-id="${artifacts.snapshot}"]`);
  await expect(selectedRun).toHaveClass('active');
  await expect(page.getByText('Anforderungserfüllung: Bestanden', {
    exact: true
  })).toBeVisible();
  await expect(page.locator('.metric').filter({
    has: page.getByText('Trace Events', {
      exact: true
    })
  })).toContainText(artifacts.trace_events.toLocaleString('de-DE'));
  await page.reload();
  await expect(selectedRun).toHaveClass('active');
  await expect(page.getByText('Anforderungserfüllung: Bestanden', {
    exact: true
  })).toBeVisible();
  await page.getByRole('link', {
    name: 'Simulation öffnen',
    exact: true
  }).click();
  const runner = page.locator('.model-simulation-runner');
  await expect(runner).toHaveAttribute('data-job-id', artifacts.job);
  await expect(runner).toHaveAttribute('data-snapshot-id', artifacts.snapshot);
  await expect(page.getByRole('heading', {
    name: 'Simulation abgeschlossen',
    exact: true
  })).toBeVisible();
  await page.reload();
  await expect(runner).toHaveAttribute('data-job-id', artifacts.job);
  // A new browser context has no session key from either wizard or simulation UI.
  const freshContext = await browser.newContext({
    baseURL: new URL(page.url()).origin
  });
  try {
    const fresh = await freshContext.newPage();
    await fresh.goto(`/studio/simulation?project=${project}`);
    const freshRunner = fresh.locator('.model-simulation-runner');
    await expect(freshRunner).toHaveAttribute('data-job-id', artifacts.job);
    await expect(freshRunner).toHaveAttribute('data-snapshot-id', artifacts.snapshot);
    await expect(fresh.getByRole('heading', {
      name: 'Simulation abgeschlossen',
      exact: true
    })).toBeVisible();
    await fresh.getByRole('button', {
      name: 'Reset',
      exact: true
    }).click();
    await fresh.getByRole('button', {
      name: 'Ansicht zurücksetzen',
      exact: true
    }).click();
    await expect(freshRunner).not.toHaveAttribute('data-job-id');
    await fresh.reload();
    await expect(fresh.getByRole('button', {
      name: 'Start',
      exact: true
    })).toBeEnabled();
    await expect(freshRunner).not.toHaveAttribute('data-job-id');
    await fresh.goto(`/studio/results?project=${project}&snapshot=${artifacts.snapshot}`);
    await expect(fresh.locator('.result-run-list button.active')).toHaveAttribute('data-snapshot-id', artifacts.snapshot);
    await expect(fresh.getByText('Anforderungserfüllung: Bestanden', {
      exact: true
    })).toBeVisible();
    await testInfo.attach('wizard-result-restoration', {
      body: await fresh.screenshot(),
      contentType: 'image/png'
    });
    await fresh.goto(`/studio/results?project=${project}-other&snapshot=${artifacts.snapshot}`);
    await expect(fresh.getByText('Dieser Simulationslauf ist in diesem Projekt nicht verfügbar.', {
      exact: true
    })).toBeVisible();
    await expect(fresh.locator('.result-run-list button.active')).toHaveCount(0);
  } finally {
    await freshContext.close();
  }
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
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmVhZEZpbGUiLCJyYW5kb21VVUlEIiwiZXhlY0ZpbGVTeW5jIiwiV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyIsIldJWkFSRF9TVEVQUyIsIldJWkFSRF9ET05FIiwicmV2aWV3VmlydHVhbFRyYW5zcG9ydHMiLCJzdGVwcyIsImRvbmUiLCJ3cml0ZVRpbWluZ3MiLCJNYXAiLCJ3b3JrZmxvd1BhZ2VGYWlsdXJlcyIsIldlYWtNYXAiLCJwcm9ncmVzc01pbGVzdG9uZXMiLCJiZWZvcmVFYWNoIiwicGFnZSIsImluZm8iLCJyb3dzIiwic2V0IiwidGVzdElkIiwicmVxdWVzdHMiLCJvbiIsInJlcXVlc3QiLCJpbmNsdWRlcyIsIm1ldGhvZCIsInJvdyIsInVybCIsInN0YXJ0ZWQiLCJEYXRlIiwibm93IiwicHVzaCIsInJlc3BvbnNlIiwiZ2V0Iiwic3RhdHVzIiwiVVJMIiwicGF0aG5hbWUiLCJkdXJhdGlvbl9tcyIsIl9yZXF1ZXN0JGZhaWx1cmUiLCJmYWlsdXJlIiwiZXJyb3JUZXh0IiwiYWZ0ZXJFYWNoIiwiYXR0YWNoIiwiYm9keSIsIkpTT04iLCJzdHJpbmdpZnkiLCJjb250ZW50VHlwZSIsImRlbGV0ZSIsInRvRXF1YWwiLCJnZXRCeVJvbGUiLCJuYW1lIiwiZXhhY3QiLCJub3QiLCJ0b0JlVmlzaWJsZSIsImFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkiLCJnZXRCeVRleHQiLCJpc1Zpc2libGUiLCJ0b0JlIiwicmVhZFByb2plY3QiLCJwcm9qZWN0IiwicGF0aCIsInJlc3VsdCIsImhlYWRlcnMiLCJ0aW1lb3V0Iiwib2siLCJFcnJvciIsInRleHQiLCJzbGljZSIsImpzb24iLCJkaXNwb3NlIiwicmVhZFdhcm5pbmdSZXZpZXdTdGF0ZSIsIl92ZXJpZmllZCRjb250ZXh0JGFnZTIiLCJfdmVyaWZpZWQkY29udGV4dCRhZ2UzIiwiYXV0aG9yaXR5IiwicGFyYW1ldGVycyIsInZlcmlmaWVkIiwicHJvamVjdF9pZCIsImZpZWxkIiwiX3ZlcmlmaWVkJGNvbnRleHQkYWdlIiwiX2F1dGhvcml0eSRjb250ZXh0JGFnIiwiY29udGV4dCIsImFnZW50X2V4ZWN1dGlvbiIsInN0YXR1c2VzIiwicnVuX2lkIiwicmVxdWVzdF9yZXZpc2lvbiIsInByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsIiwib3BlbldpemFyZCIsImdvdG8iLCJ3YWl0VW50aWwiLCJkaWFsb2ciLCJzdGVwIiwibG9jYXRvciIsInN0ZXBXaWR0aCIsImV2YWx1YXRlIiwiZWxlbWVudCIsImdldEJvdW5kaW5nQ2xpZW50UmVjdCIsIndpZHRoIiwiY2FyZHMiLCJhbGwiLCJ0b0hhdmVMZW5ndGgiLCJjYXJkIiwidG9CZUdyZWF0ZXJUaGFuIiwiYWxsT2JqZWN0cyIsInJlc291cmNlIiwiaXRlbXMiLCJvZmZzZXQiLCJsZW5ndGgiLCJyZXN0YXJ0QXBwbGljYXRpb24iLCJjcmFzaCIsImNvbnRhaW5lciIsInByb2Nlc3MiLCJlbnYiLCJOSVNfRTJFX0FQUF9DT05UQUlORVIiLCJ0b01hdGNoIiwiZG9ja2VyIiwiTklTX1RFU1RfRE9DS0VSIiwibGFiZWwiLCJlbmNvZGluZyIsInRyaW0iLCJwb2xsIiwidmVyaWZ5U2lnbmFsQ29udHJhY3RzIiwiZXhwZWN0ZWQiLCJoYXJkd2FyZSIsImZ1bmN0aW9ucyIsIm1lc3NhZ2VzIiwic2lnbmFscyIsIlByb21pc2UiLCJtYXAiLCJub2RlcyIsIml0ZW0iLCJpZCIsImZ1bmN0aW9uc0J5SWQiLCJtZXNzYWdlc0J5SWQiLCJjb250cmFjdHMiLCJzaWduYWwiLCJfcmVmIiwiX3NpZ25hbCRkYXRhJGVudW1fdmFsIiwiX3NpZ25hbCRkYXRhIiwiX3NpZ25hbCRzZW1hbnRpYyRzZW1hIiwiX3NpZ25hbCRzZW1hbnRpYyIsIl9zaWduYWwkY29uZmlndXJhdGlvbiIsIl9zaWduYWwkY29uZmlndXJhdGlvbjIiLCJtZXNzYWdlIiwibWVzc2FnZV9pZCIsInRvQmVUcnV0aHkiLCJyZWZlcmVuY2UiLCJjb25maWd1cmF0aW9uIiwiY29tbXVuaWNhdGlvbl9jb250cmFjdCIsInByb2R1Y2VyX3JlZiIsImZuIiwib3duZXIiLCJoYXJkd2FyZV9ub2RlX2lkIiwicHJvZHVjZXIiLCJkZXZpY2VfdHlwZSIsImtleSIsImpvaW4iLCJ0b0JlVW5kZWZpbmVkIiwiT2JqZWN0IiwiZnJvbUVudHJpZXMiLCJfc2lnbmFsJGZpZWxkIiwiZW51bV92YWx1ZXMiLCJkYXRhIiwic2VtYW50aWNfdHlwZSIsInNlbWFudGljIiwiZ2VuZXJhdGlvbl9yb2xlIiwidmVyaWZ5QXJ0aWZhY3RzIiwibWluaW11bUNhbm9uaWNhbFNpZ25hbHMiLCJpbnRlcm5hbENvbnRyb2xsZXIiLCJleHBlY3RlZFBhcmFtZXRlcnMiLCJleHBlY3RlZE5hdGl2ZVJhdGVzIiwiX2Fzc2Vzc21lbnQkc2NvcGVfY292Iiwid29ya2Zsb3ciLCJqb2JMaXN0Iiwic25hcHNob3RzIiwia2V5cyIsInNvcnQiLCJoYXMiLCJqb2JzIiwic25hcHNob3QiLCJzaW11bGF0aW9ucyIsImZpbmQiLCJqb2JfaWQiLCJmdWxsIiwiZGF0YV9iaXRyYXRlIiwiY2FuX2ZkX2RhdGFfcHJlc2NhbGVyIiwicnVudGltZVBhcmFtZXRlcnMiLCJ0b01hdGNoT2JqZWN0IiwiY2FuRmROZXR3b3JrcyIsIm5ldHdvcmtzIiwiZmlsdGVyIiwibmV0d29yayIsInRlY2hub2xvZ3kiLCJyYXRlcyIsImVudHJpZXMiLCJhc3Nlc3NtZW50Iiwic2NvcGVfY292ZXJhZ2UiLCJzY29wZV9tb2RlIiwiY29tcGxldGUiLCJjb25mb3JtYW5jZSIsImZhaWxlZF9yb3V0ZV9jb3VudCIsInRvQmVHcmVhdGVyVGhhbk9yRXF1YWwiLCJleGNsdWRlZCIsInRyYW5zcG9ydF9leGNsdXNpb25zIiwicm91dGluZyIsImVuYWJsZWQiLCJjb250cmFjdCIsImNvbnN1bWVyX3JlZnMiLCJyZWFzb25fY29kZSIsInJvbGUiLCJjb250cm9sbGVyIiwic2NvcGUiLCJleGNsdWRlZFNpZ25hbHMiLCJTZXQiLCJmbGF0TWFwIiwic2lnbmFsX2lkcyIsIm9ic2VydmVkX3NpZ25hbF9jb3VudCIsInNpemUiLCJ0cmFjZSIsImNvdW50IiwiZXZlbnRzIiwic29tZSIsImpvYiIsInRyYWNlX2V2ZW50cyIsInBhcmFtZXRlcl9wcm9vZiIsInNhdmVkIiwic2ltdWxhdGlvbl9yYXRlcyIsImJpdHJhdGUiLCJhcmJpdHJhdGlvbl9iaXRyYXRlIiwiaGFyZHdhcmVfZXZpZGVuY2UiLCJ1bmRlZmluZWQiLCJyZXBlYXRQYXJhbWV0ZXJSZXR1cm4iLCJwcm9wb3NhbElkIiwic2NlbmFyaW9zIiwic2VlZHMiLCJiZWZvcmUiLCJpZGVudGl0eSIsIm5vZGVJZHMiLCJzdGFydHMiLCJ0cmFja1N0YXJ0cyIsIl9yZXF1ZXN0JHBvc3REYXRhSlNPTiIsImVuZHNXaXRoIiwicG9zdERhdGFKU09OIiwid2l6YXJkX2NvbW1hbmQiLCJhY3Rpb24iLCJldmlkZW5jZSIsIndpemFyZCIsImNsaWNrIiwiY3ljbGUiLCJzZWVkIiwic2NlbmFyaW8iLCJfc2F2ZWQkcGFyYW1ldGVycyRzaW0iLCJlbmNvZGVVUklDb21wb25lbnQiLCJjb21tb24iLCJ2YWx1ZSIsImZpZWxkcyIsIl9zY2VuYXJpbyRlZGl0RmllbGRzIiwiaW5wdXQiLCJkZXRhaWxzIiwiZ2V0QXR0cmlidXRlIiwiZWRpdEZpZWxkcyIsImZpbGwiLCJ0b0hhdmVWYWx1ZSIsIlN0cmluZyIsInBhcmFtZXRlcl9wcm92ZW5hbmNlIiwiZHVyYXRpb25fcyIsInNvdXJjZSIsInNjb3BlZCIsInRlY2hub2xvZ3lfcGFyYW1ldGVycyIsImFzc3VtZWQiLCJzaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucyIsInZhbHVlcyIsIm5hdGl2ZVZhbHVlcyIsIm5hdGl2ZSIsImNvbmZpcm1lZCIsImhhc093biIsInByb3ZlbmFuY2UiLCJ1c2VyVmFsdWVzIiwidmFsdWVfb3JpZ2luIiwidGVjaG5vbG9neV9kZWZhdWx0cyIsInN0YWxlIiwiY2Fub25pY2FsSWRzIiwiY2Fub25pY2FsX2lkcyIsInJlbG9hZCIsInJlc3VtZVJlc3RvcmUiLCJyZXN0b3JlUGF1c2UiLCJyZXNvbHZlIiwiZGVsYXlSZXN0b3JlIiwicm91dGUiLCJjb250aW51ZSIsImRlbGF5ZWQiLCJ0b0NvbnRhaW5UZXh0IiwidW5yb3V0ZUFsbCIsImJlaGF2aW9yIiwicmVzdG9yZWQiLCJzdGF0ZSIsImNvbnZlcnNhdGlvbiIsImFjdGl2ZV9wcm9wb3NhbCIsImZyZXNoIiwiYWZ0ZXIiLCJwcm9wb3NhbF9pZCIsInNhdmVkX3ZhbHVlcyIsImFzc3VtcHRpb25zIiwicmVzdG9yZWRfc3RhdHVzIiwib2ZmIiwiY29tcGxldGVUaHJvdWdoV2l6YXJkIiwicmVzdGFydCIsImV4cGVjdGVkSGFyZHdhcmUiLCJjcmFzaFNpbXVsYXRpb24iLCJleHBlY3RlZFNpZ25hbHMiLCJhZnRlckZpcnN0TW9kZWxBcHBsaWVkIiwic3RvcE9uRXZpZGVuY2VCbG9jayIsImJlZm9yZVByb3Bvc2FsUmV2aWV3IiwicmV2aWV3Q291bnQiLCJydW5JZCIsInJldmlld2VkIiwicmVzdGFydGVkSm9iSWQiLCJ3YXRjaGRvZyIsInBlcmZvcm1hbmNlIiwiY2hlY2twb2ludCIsIl93b3JrZmxvdyRjb250ZXh0JGFnZSIsIl93b3JrZmxvdyRjb250ZXh0JGFnZTIiLCJfZXhlY3V0aW9uJGJsb2NraW5nX2YiLCJfZXhlY3V0aW9uJG1lc3NhZ2UiLCJyZWFkeVZlcnNpb24iLCJyZWFkeVNpbmNlIiwiaXNDaGVja3BvaW50IiwicmVtYWluaW5nIiwicHJvZ3Jlc3MiLCJvYnNlcnZlIiwiYWR2YW5jZWQiLCJhdCIsInRvSVNPU3RyaW5nIiwiZnJvbnRpZXIiLCJjb21wbGV0ZWRUaHJvdWdoIiwiZXhlY3V0aW9uIiwidmFsaWRhdGlvbiIsInJ1bm5pbmciLCJldmVyeSIsIkJvb2xlYW4iLCJyZWNvdmVyYWJsZSIsInVwZGF0ZWRfYXQiLCJidXR0b24iLCJldmFsdWF0ZUFsbCIsImJ1dHRvbnMiLCJkaXNhYmxlZCIsImdldENsaWVudFJlY3RzIiwiZ2V0Q29tcHV0ZWRTdHlsZSIsInZpc2liaWxpdHkiLCJhdHRlbXB0Iiwid2FpdEZvclRpbWVvdXQiLCJNYXRoIiwibWluIiwiYmxvY2tpbmdfZmluZGluZ3MiLCJiZWZvcmVSZXZpZXciLCJwcmVmbGlnaHQiLCJ3YXJuaW5ncyIsImZpcnN0Iiwic3RhcnRlZFdhbGwiLCJhcHByb3ZhbFJlc3BvbnNlIiwid2FpdEZvclJlc3BvbnNlIiwiYXBwcm92ZWQiLCJyZWNlaXB0IiwiYWZ0ZXJSZXZpZXciLCJwcm9vZiIsInNuYXBzaG90SWQiLCJyZXF1ZXN0UHJvamVjdCIsInN1Ym1pdHRlZCIsImZpbmlzaGVkV2FsbCIsImNvbW1pdHRlZEF0IiwiY29tbWl0dGVkIiwiY29tbWl0V2FybmluZ1JldmlldyIsIm1hbnVhbFdhcm5pbmdBcHByb3ZhbCIsImFwcHJvdmFsSWRlbnRpdHkiLCJhcHByb3ZhbCIsIl9hd2FpdCRyZWFkUHJvamVjdCRjbyIsIl9jb252ZXJzYXRpb24kZGF0YSIsIl9wcm9wb3NhbCRkYXRhIiwicHJvcG9zYWwiLCJ2YWxpZGF0aW9uX3Jlc3VsdCIsInZpc2libGUiLCJpbm5lclRleHQiLCJlcnJvciIsIl9sYXRlc3QkY29udGV4dCRhZ2VudCIsImxhdGVzdCIsIl9sYXRlc3QkY29udGV4dCRhZ2VudDIiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQzIiwiX2xhdGVzdCRzdGF0dXNlcyIsImNhbmRpZGF0ZSIsInByb3Bvc2FsX3R5cGUiLCJjaGFuZ2VzIiwiY2hhbmdlIiwib2JqZWN0X3R5cGUiLCJhcnJheUNvbnRhaW5pbmciLCJyZXZpZXdBY3Rpb24iLCJyZXZpZXdPbmx5IiwicHJvcG9zYWxUeXBlIiwiYXBwbHlSZXNwb25zZSIsInRvQmVFbmFibGVkIiwiYXBwbGllZCIsImFkZCIsIl9hbWVuZGVkJGNvbnRleHQkYWdlbiIsImFtZW5kZWQiLCJfY3VycmVudCRjb250ZXh0JGFnZW4iLCJjdXJyZW50IiwiZnVsZmlsbCIsImdldEJ5VGl0bGUiLCJnZXRCeUxhYmVsIiwidG9CZURpc2FibGVkIiwidW5yb3V0ZSIsInRvSGF2ZUNvdW50IiwiY2F0YWxvZyIsInRlY2hub2xvZ3lfY291bnQiLCJicm93c2VyIiwidGVzdEluZm8iLCJlcnJvcnMiLCJzdGFydFJlcXVlc3QiLCJ3YWl0Rm9yUmVxdWVzdCIsIl9yZXF1ZXN0JHBvc3REYXRhSlNPTjIiLCJzdWJtaXQiLCJyZXF1ZXN0ZWQiLCJ3aXphcmRfY29udGV4dCIsInRlY2hub2xvZ2llcyIsIl9hd2FpdCRyZWFkUHJvamVjdCRjbzIiLCJwZW5kaW5nIiwiY29udGludWl0eSIsImFydGlmYWN0cyIsImZpbmlzaGVkIiwidG9IYXZlVVJMIiwiUmVnRXhwIiwic2VsZWN0ZWRSdW4iLCJ0b0hhdmVDbGFzcyIsInRvTG9jYWxlU3RyaW5nIiwicnVubmVyIiwidG9IYXZlQXR0cmlidXRlIiwiZnJlc2hDb250ZXh0IiwibmV3Q29udGV4dCIsImJhc2VVUkwiLCJvcmlnaW4iLCJuZXdQYWdlIiwiZnJlc2hSdW5uZXIiLCJzY3JlZW5zaG90IiwiY2xvc2UiLCJjaGVjayIsInNlbGVjdE9wdGlvbiIsInJlamVjdHMiLCJ0b1Rocm93IiwiZmluZGluZ3MiLCJjb2RlIiwidG9Db250YWluIiwiYXJ0aWZhY3RfY2hlY2tzIiwicmVxdWlyZWQiLCJwcm9maWxlX3ZhbHVlcyIsImRldmljZVNvdXJjZSIsInRvSGF2ZVByb3BlcnR5IiwibmF0aXZlVGVjaG5vbG9neSIsInByb2ZpbGVfZmluZGluZ3MiLCJmaW5kaW5nIiwiZXZpZGVuY2VSZXZpZXciLCJzaW11bGF0aW9uIiwicmF0ZV9yZXZpZXdfcHJvcG9zYWxzIiwiaTJjIiwiaW50ZXJmYWNlcyIsImRvbWFpbiIsInVuaXQiLCJzdGFydENhcHR1cmVkTGFyZ2VXaXphcmQiLCJvcmlnaW5hbCIsImltcG9ydCIsIm1ldGEiLCJtZXRhZGF0YSIsInBhcnNlIiwiYmFzZWxpbmUiLCJwcm9tcHQiLCJyZXBsYWNlIiwicG9zdCIsIm9wZXJhdGlvbl9pZCIsInRhcmdldCIsImxhcmdlUGFyYW1ldGVyU2NlbmFyaW9zIiwibGluX2JpdHJhdGVfYnBzIiwicGFyYW1ldGVyUmV0dXJuUmV2aWV3cyIsInJldmlld1NlZWQiLCJsaW4iLCJjYW5fZmQiLCJldGhlcm5ldCIsImV4Y2x1ZGVkU2lnbmFsSWRzIiwiZml4dHVyZSIsInJlcXVlc3Rfc2hhMjU2IiwidHlwZSIsIl9jb250aW51aXR5JHJldmlld09ubCIsImNvdmVyYWdlIiwiY3ljbGVzIiwiZ3JhcGgiLCJjbHVzdGVyX2lkIiwibmV0d29ya19pZCIsIm5ldHdvcmtfbGFiZWwiLCJidXNfbmFtZSIsImNvbnRyb2xsZXJzIiwiZWN1Iiwic2Vuc29ycyIsImFjdHVhdG9ycyIsImhtaV9yb3V0ZXMiLCJwcm9qZWN0X25hbWUiLCJzY29wZV9pZHMiLCJtb2RlIiwicHJvY2Vzc19pZHMiLCJ0YXNrIiwib3JpZ2luYWxOZXR3b3JrcyIsImFtZW5kIiwiZXhwYW5kIiwic3lzdGVtX293bmVyX2lkIiwic2Vuc29yTmV0d29yayIsInRvcG9sb2d5IiwibG9jYWxFZGdlIiwiZWRnZXMiLCJlZGdlIiwicGh5c2ljYWxOZXR3b3JrSWQiLCJidXMiLCJyb3V0aW5nTWV0YWRhdGEiLCJ0b0NvbnRhaW5FcXVhbCIsIm9iamVjdENvbnRhaW5pbmciLCJhcHByb3ZhbFN0YXRlIiwicHJvdG9jb2wiLCJzaWRlIiwiaGFyZHdhcmVJZCIsIm5vZGUiLCJlbmdpbmVlcmluZ0lkIiwicG9ydHMiLCJ0eHJ4IiwiaGFzVGV4dCIsInNlbGVjdGVkIiwidG9CZUNoZWNrZWQiLCJ1bmNoZWNrIiwiX3JlcXVlc3QkcG9zdERhdGFKU09OMyIsInN5c3RlbV9jbHVzdGVyX2Fzc2lnbm1lbnRzIiwiY2x1c3RlciIsIl9jbHVzdGVyJGZ1bmN0aW9uYWxfciIsImZ1bmN0aW9uYWxfcm91dGVzIiwiZXhjbHVkZWRfc2lnbmFscyIsInJldmlldyIsImFwcGx5IiwiZ2VhcmJveCIsImVtb3RvciJdLCJzb3VyY2VzIjpbIndpemFyZC5zcGVjLnRzIl0sInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHRlc3QsIGV4cGVjdCwgdHlwZSBQYWdlIH0gZnJvbSAncGxheXdyaWdodC90ZXN0JztcclxuaW1wb3J0IHsgcmVhZEZpbGUgfSBmcm9tICdub2RlOmZzL3Byb21pc2VzJztcclxuaW1wb3J0IHsgcmFuZG9tVVVJRCB9IGZyb20gJ25vZGU6Y3J5cHRvJztcclxuaW1wb3J0IHsgZXhlY0ZpbGVTeW5jIH0gZnJvbSAnbm9kZTpjaGlsZF9wcm9jZXNzJztcclxuaW1wb3J0IHsgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZywgV0laQVJEX1NURVBTLCBXSVpBUkRfRE9ORSB9IGZyb20gJy4vc3VwcG9ydC93aXphcmQtcHJvZ3Jlc3Mtd2F0Y2hkb2cnO1xyXG5pbXBvcnQgeyByZXZpZXdWaXJ0dWFsVHJhbnNwb3J0cyB9IGZyb20gJy4vc3VwcG9ydC9uYXRpdmUtdHJhbnNwb3J0LWZpeHR1cmVzJztcclxuXHJcbmNvbnN0IHN0ZXBzID0gV0laQVJEX1NURVBTO1xyXG5jb25zdCBkb25lID0gV0laQVJEX0RPTkU7XHJcbnR5cGUgV3JpdGVUaW1pbmcgPSB7IHVybDogc3RyaW5nOyBzdGFydGVkOiBudW1iZXI7IGR1cmF0aW9uX21zPzogbnVtYmVyOyBzdGF0dXM/OiBudW1iZXI7IGZhaWx1cmU/OiBzdHJpbmcgfTtcclxuY29uc3Qgd3JpdGVUaW1pbmdzID0gbmV3IE1hcDxzdHJpbmcsIFdyaXRlVGltaW5nW10+KCk7XHJcbmNvbnN0IHdvcmtmbG93UGFnZUZhaWx1cmVzID0gbmV3IFdlYWtNYXA8UGFnZSwgc3RyaW5nW10+KCk7XHJcbmNvbnN0IHByb2dyZXNzTWlsZXN0b25lcyA9IG5ldyBNYXA8c3RyaW5nLCB1bmtub3duW10+KCk7XHJcblxyXG50ZXN0LmJlZm9yZUVhY2goYXN5bmMgKHsgcGFnZSB9LCBpbmZvKSA9PiB7XHJcbiAgY29uc3Qgcm93czogV3JpdGVUaW1pbmdbXSA9IFtdO1xyXG4gIHdyaXRlVGltaW5ncy5zZXQoaW5mby50ZXN0SWQsIHJvd3MpO1xyXG4gIHdvcmtmbG93UGFnZUZhaWx1cmVzLnNldChwYWdlLCBbXSk7XHJcbiAgcHJvZ3Jlc3NNaWxlc3RvbmVzLnNldChpbmZvLnRlc3RJZCwgW10pO1xyXG4gIGNvbnN0IHJlcXVlc3RzID0gbmV3IE1hcDxvYmplY3QsIFdyaXRlVGltaW5nPigpO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3QnLCByZXF1ZXN0ID0+IHtcclxuICAgIGlmICghWydQT1NUJywgJ1BVVCcsICdQQVRDSCcsICdERUxFVEUnXS5pbmNsdWRlcyhyZXF1ZXN0Lm1ldGhvZCgpKSkgcmV0dXJuO1xyXG4gICAgY29uc3Qgcm93ID0geyB1cmw6IHJlcXVlc3QudXJsKCksIHN0YXJ0ZWQ6IERhdGUubm93KCkgfTtcclxuICAgIHJvd3MucHVzaChyb3cpOyByZXF1ZXN0cy5zZXQocmVxdWVzdCwgcm93KTtcclxuICB9KTtcclxuICBwYWdlLm9uKCdyZXNwb25zZScsIHJlc3BvbnNlID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXNwb25zZS5yZXF1ZXN0KCkpO1xyXG4gICAgaWYgKHJvdykgcm93LnN0YXR1cyA9IHJlc3BvbnNlLnN0YXR1cygpO1xyXG4gICAgaWYgKHJlc3BvbnNlLnN0YXR1cygpID09PSA0MTMgJiYgL15cXC9hcGlcXC9lbmdpbmVlcmluZ1xcL3dvcmtmbG93KD86XFwvfCQpLy50ZXN0KG5ldyBVUkwocmVzcG9uc2UudXJsKCkpLnBhdGhuYW1lKSkge1xyXG4gICAgICB3b3JrZmxvd1BhZ2VGYWlsdXJlcy5nZXQocGFnZSkhLnB1c2goYEhUVFAgNDEzOiAke3Jlc3BvbnNlLnVybCgpfWApO1xyXG4gICAgfVxyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3RmaW5pc2hlZCcsIHJlcXVlc3QgPT4ge1xyXG4gICAgY29uc3Qgcm93ID0gcmVxdWVzdHMuZ2V0KHJlcXVlc3QpO1xyXG4gICAgaWYgKHJvdykgcm93LmR1cmF0aW9uX21zID0gRGF0ZS5ub3coKSAtIHJvdy5zdGFydGVkO1xyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3RmYWlsZWQnLCByZXF1ZXN0ID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXF1ZXN0KTtcclxuICAgIGlmIChyb3cpIHsgcm93LmR1cmF0aW9uX21zID0gRGF0ZS5ub3coKSAtIHJvdy5zdGFydGVkOyByb3cuZmFpbHVyZSA9IHJlcXVlc3QuZmFpbHVyZSgpPy5lcnJvclRleHQ7IH1cclxuICB9KTtcclxufSk7XHJcblxyXG50ZXN0LmFmdGVyRWFjaChhc3luYyAoeyBwYWdlIH0sIGluZm8pID0+IHtcbiAgYXdhaXQgaW5mby5hdHRhY2goJ3dyaXRlLXJlcXVlc3QtdGltaW5ncycsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkod3JpdGVUaW1pbmdzLmdldChpbmZvLnRlc3RJZCkgfHwgW10pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gIGF3YWl0IGluZm8uYXR0YWNoKCd3b3JrZmxvdy1wcm9ncmVzcy1ib3VuZGFyaWVzJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeShwcm9ncmVzc01pbGVzdG9uZXMuZ2V0KGluZm8udGVzdElkKSB8fCBbXSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgYXdhaXQgaW5mby5hdHRhY2goJ3dvcmtmbG93LXBhZ2UtZmFpbHVyZXMnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSB8fCBbXSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgd3JpdGVUaW1pbmdzLmRlbGV0ZShpbmZvLnRlc3RJZCk7XHJcbiAgcHJvZ3Jlc3NNaWxlc3RvbmVzLmRlbGV0ZShpbmZvLnRlc3RJZCk7XHJcbiAgZXhwZWN0KHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSwgJ1RoZSB1bmRlcmx5aW5nIGVuZ2luZWVyaW5nIHBhZ2UgbXVzdCByZW1haW4gcmVhZGFibGUgdGhyb3VnaG91dCByZWxvYWQgYW5kIHJlY292ZXJ5LicpLnRvRXF1YWwoW10pO1xuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2hlYWRpbmcnLCB7bmFtZTogJ0RpZSBBbnNpY2h0IGtvbm50ZSBuaWNodCBnZWxhZGVuIHdlcmRlbi4nLCBleGFjdDogdHJ1ZX0pLFxuICAgICdBIGNyYXNoZWQgcGFyYW1ldGVyIG9yIGVuZ2luZWVyaW5nIHBhZ2UgbXVzdCBuZXZlciBjb3VudCBhcyBhIHN1Y2Nlc3NmdWwgd2l6YXJkIGRldG91ci4nKS5ub3QudG9CZVZpc2libGUoKTtcbn0pO1xyXG5cclxuYXN5bmMgZnVuY3Rpb24gYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeShwYWdlOiBQYWdlKSB7XG4gIGV4cGVjdCh3b3JrZmxvd1BhZ2VGYWlsdXJlcy5nZXQocGFnZSksICdBIHdvcmtpbmcgd2l6YXJkIG92ZXJsYXkgbXVzdCBub3QgY29uY2VhbCBhIHdvcmtmbG93IEhUVFAgNDEzLicpLnRvRXF1YWwoW10pO1xyXG4gIGV4cGVjdChhd2FpdCBwYWdlLmdldEJ5VGV4dCgnRW5naW5lZXJpbmctQVBJIG5pY2h0IGVycmVpY2hiYXInLCB7IGV4YWN0OiB0cnVlIH0pLmlzVmlzaWJsZSgpLFxuICAgICdUaGUgdW5kZXJseWluZyBlbmdpbmVlcmluZyBwYWdlIG11c3Qgbm90IHNob3cgaXRzIEFQSSBlcnJvciB2aWV3LicpLnRvQmUoZmFsc2UpO1xuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2hlYWRpbmcnLCB7bmFtZTogJ0RpZSBBbnNpY2h0IGtvbm50ZSBuaWNodCBnZWxhZGVuIHdlcmRlbi4nLCBleGFjdDogdHJ1ZX0pKS5ub3QudG9CZVZpc2libGUoKTtcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHJlYWRQcm9qZWN0KHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcGF0aDogc3RyaW5nKSB7XHJcbiAgY29uc3QgcmVzdWx0ID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldChwYXRoLCB7IGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSwgdGltZW91dDogNjBfMDAwIH0pO1xyXG4gIHRyeSB7XHJcbiAgICBpZiAoIXJlc3VsdC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYCR7cGF0aH06IEhUVFAgJHtyZXN1bHQuc3RhdHVzKCl9ICR7KGF3YWl0IHJlc3VsdC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gICAgcmV0dXJuIGF3YWl0IHJlc3VsdC5qc29uKCk7XHJcbiAgfSBmaW5hbGx5IHtcclxuICAgIC8vIFBsYXl3cmlnaHQgb3RoZXJ3aXNlIHJldGFpbnMgZXZlcnkgcG9sbGVkIHJlc3BvbnNlIHVudGlsIGNvbnRleHQgdGVhcmRvd24uXHJcbiAgICAvLyBLZWVwIHRoZSBwYXJzZWQgZXZpZGVuY2UsIHJlbGVhc2UgaXRzIGR1cGxpY2F0ZSB0cmFuc3BvcnQgYm9keSBpbW1lZGlhdGVseS5cclxuICAgIGF3YWl0IHJlc3VsdC5kaXNwb3NlKCk7XHJcbiAgfVxyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiByZWFkV2FybmluZ1Jldmlld1N0YXRlKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZykge1xyXG4gIGNvbnN0IGF1dGhvcml0eSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gIGNvbnN0IHBhcmFtZXRlcnMgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyk7XHJcbiAgY29uc3QgdmVyaWZpZWQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICBleHBlY3QocGFyYW1ldGVycy5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xyXG4gIGV4cGVjdChhdXRob3JpdHkucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcclxuICBleHBlY3QodmVyaWZpZWQucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcclxuICBmb3IgKGNvbnN0IGZpZWxkIG9mIFsncnVuX2lkJywgJ3JlcXVlc3RfcmV2aXNpb24nXSlcclxuICAgIGV4cGVjdCh2ZXJpZmllZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uW2ZpZWxkXSkudG9CZShhdXRob3JpdHkuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LltmaWVsZF0pO1xyXG4gIHJldHVybiB7IHByb2plY3RfaWQ6IHZlcmlmaWVkLnByb2plY3RfaWQsIHN0YXR1c2VzOiB2ZXJpZmllZC5zdGF0dXNlcyxcclxuICAgIGNvbnRleHQ6IHsgYWdlbnRfZXhlY3V0aW9uOiB7IHJ1bl9pZDogdmVyaWZpZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZCxcclxuICAgICAgcmVxdWVzdF9yZXZpc2lvbjogdmVyaWZpZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJlcXVlc3RfcmV2aXNpb24gfSB9LFxyXG4gICAgcGFyYW1ldGVyczogeyBwcmVmbGlnaHRfd2FybmluZ19hcHByb3ZhbDogcGFyYW1ldGVycy5wYXJhbWV0ZXJzLnByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsIH0gfTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gb3BlbldpemFyZChwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcpIHtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vZW5naW5lZXJpbmc/YXNzaXN0YW50PXByb2plY3QmcHJvamVjdD0ke3Byb2plY3R9YCwgeyB3YWl0VW50aWw6ICdsb2FkJyB9KTtcclxuICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeShwYWdlKTtcclxuICByZXR1cm4gZGlhbG9nO1xyXG59XHJcblxyXG50ZXN0KCdwcm9qZWN0IG5hbWluZyBmb3JtIGNhcmRzIHVzZSB0aGUgZnVsbCB3aXphcmQgd2lkdGggQGxheW91dCcsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgJ25pcy1lMmUtcHJvamVjdC1uYW1lLWxheW91dC0nICsgcmFuZG9tVVVJRCgpKTtcclxuICBjb25zdCBzdGVwID0gZGlhbG9nLmxvY2F0b3IoJ2ZpZWxkc2V0LmFnZW50LXByb2plY3QtbmFtZS1zdGVwJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHN0ZXApLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3Qgc3RlcFdpZHRoID0gYXdhaXQgc3RlcC5ldmFsdWF0ZShlbGVtZW50ID0+IGVsZW1lbnQuZ2V0Qm91bmRpbmdDbGllbnRSZWN0KCkud2lkdGgpO1xyXG4gIGNvbnN0IGNhcmRzID0gYXdhaXQgc3RlcC5sb2NhdG9yKCc6c2NvcGUgPiBsYWJlbCcpLmFsbCgpO1xyXG4gIGV4cGVjdChjYXJkcykudG9IYXZlTGVuZ3RoKDQpO1xyXG4gIGZvciAoY29uc3QgY2FyZCBvZiBjYXJkcykge1xyXG4gICAgY29uc3Qgd2lkdGggPSBhd2FpdCBjYXJkLmV2YWx1YXRlKGVsZW1lbnQgPT4gZWxlbWVudC5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKS53aWR0aCk7XHJcbiAgICBleHBlY3Qod2lkdGgpLnRvQmVHcmVhdGVyVGhhbihzdGVwV2lkdGggKiAwLjg1KTtcclxuICB9XHJcbn0pO1xyXG5cclxuYXN5bmMgZnVuY3Rpb24gYWxsT2JqZWN0cyhwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIHJlc291cmNlOiBzdHJpbmcpIHtcclxuICBjb25zdCBpdGVtczogYW55W10gPSBbXTtcclxuICBmb3IgKGxldCBvZmZzZXQgPSAwOyA7IG9mZnNldCArPSA1MDApIHtcclxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvJHtyZXNvdXJjZX0/bGltaXQ9NTAwJm9mZnNldD0ke29mZnNldH1gKTtcclxuICAgIGl0ZW1zLnB1c2goLi4ucmVzcG9uc2UuaXRlbXMpO1xyXG4gICAgaWYgKHJlc3BvbnNlLml0ZW1zLmxlbmd0aCA8IDUwMCkgcmV0dXJuIGl0ZW1zO1xyXG4gIH1cclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2U6IFBhZ2UsIGNyYXNoID0gZmFsc2UpIHtcclxuICBjb25zdCBjb250YWluZXIgPSBwcm9jZXNzLmVudi5OSVNfRTJFX0FQUF9DT05UQUlORVIhO1xyXG4gIGV4cGVjdChjb250YWluZXIpLnRvTWF0Y2goL15uaXMtZTJlLWFwcC1bYS1mMC05XSskLyk7XHJcbiAgY29uc3QgZG9ja2VyID0gcHJvY2Vzcy5lbnYuTklTX1RFU1RfRE9DS0VSIHx8ICdkb2NrZXInO1xyXG4gIGNvbnN0IGxhYmVsID0gZXhlY0ZpbGVTeW5jKGRvY2tlciwgWydpbnNwZWN0JywgY29udGFpbmVyLCAnLS1mb3JtYXQnLCAne3tpbmRleCAuQ29uZmlnLkxhYmVscyBcIm5ldHdvcmtpcy50ZXN0XCJ9fSddLCB7IGVuY29kaW5nOiAndXRmOCcgfSkudHJpbSgpO1xyXG4gIGV4cGVjdChsYWJlbCkudG9CZSgnZGlzcG9zYWJsZScpO1xyXG4gIGV4ZWNGaWxlU3luYyhkb2NrZXIsIFsncmVzdGFydCcsIC4uLihjcmFzaCA/IFsnLXQnLCAnMCddIDogW10pLCBjb250YWluZXJdLCB7IHRpbWVvdXQ6IDYwXzAwMCB9KTtcclxuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICB0cnkgeyByZXR1cm4gKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvcmVhZHknLCB7IHRpbWVvdXQ6IDIwMDAgfSkpLm9rKCk7IH0gY2F0Y2ggeyByZXR1cm4gZmFsc2U7IH1cclxuICB9LCB7IHRpbWVvdXQ6IDEyMF8wMDAgfSkudG9CZSh0cnVlKTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gdmVyaWZ5U2lnbmFsQ29udHJhY3RzKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgZXhwZWN0ZWQ6IFJlY29yZDxzdHJpbmcsIHVua25vd24+KSB7XHJcbiAgY29uc3QgW2hhcmR3YXJlLCBmdW5jdGlvbnMsIG1lc3NhZ2VzLCBzaWduYWxzXSA9IGF3YWl0IFByb21pc2UuYWxsKFxyXG4gICAgWydoYXJkd2FyZS1ub2RlcycsICdmdW5jdGlvbnMnLCAnbWVzc2FnZXMnLCAnc2lnbmFscyddLm1hcChyZXNvdXJjZSA9PiBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsIHJlc291cmNlKSkpO1xyXG4gIGNvbnN0IG5vZGVzID0gbmV3IE1hcChoYXJkd2FyZS5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBmdW5jdGlvbnNCeUlkID0gbmV3IE1hcChmdW5jdGlvbnMubWFwKGl0ZW0gPT4gW2l0ZW0uaWQsIGl0ZW1dKSk7XHJcbiAgY29uc3QgbWVzc2FnZXNCeUlkID0gbmV3IE1hcChtZXNzYWdlcy5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBjb250cmFjdHM6IFJlY29yZDxzdHJpbmcsIHVua25vd24+ID0ge307XHJcbiAgZm9yIChjb25zdCBzaWduYWwgb2Ygc2lnbmFscykge1xyXG4gICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzQnlJZC5nZXQoc2lnbmFsLm1lc3NhZ2VfaWQpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UpLnRvQmVUcnV0aHkoKTtcclxuICAgIGNvbnN0IHJlZmVyZW5jZSA9IG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LnByb2R1Y2VyX3JlZjtcclxuICAgIGNvbnN0IGZuID0gZnVuY3Rpb25zQnlJZC5nZXQocmVmZXJlbmNlKTtcclxuICAgIGNvbnN0IG93bmVyID0gbm9kZXMuZ2V0KHJlZmVyZW5jZSkgfHwgKGZuICYmIG5vZGVzLmdldChmbi5oYXJkd2FyZV9ub2RlX2lkKSk7XHJcbiAgICBjb25zdCBwcm9kdWNlciA9IG93bmVyPy5kZXZpY2VfdHlwZSA9PT0gJ0dhdGV3YXknID8gJyRnYXRld2F5JyA6IChub2Rlcy5nZXQocmVmZXJlbmNlKSB8fCBmbik/Lm5hbWU7XHJcbiAgICBleHBlY3QocHJvZHVjZXIpLnRvQmVUcnV0aHkoKTtcclxuICAgIGNvbnN0IGtleSA9IFtwcm9kdWNlciwgbWVzc2FnZS5uYW1lLCBzaWduYWwubmFtZV0uam9pbignIDo6ICcpO1xyXG4gICAgZXhwZWN0KGNvbnRyYWN0c1trZXldLCAnU2VtYW50aWMgc2lnbmFsIGlkZW50aXR5IG11c3QgYmUgdW5pcXVlOiAnICsga2V5KS50b0JlVW5kZWZpbmVkKCk7XHJcbiAgICBjb250cmFjdHNba2V5XSA9IHtcclxuICAgICAgLi4uT2JqZWN0LmZyb21FbnRyaWVzKFsnc3RhcnRfYml0JywgJ2xlbmd0aF9iaXRzJywgJ2RhdGFfdHlwZScsICdmYWN0b3InLCAnb2Zmc2V0X3ZhbHVlJyxcclxuICAgICAgICAndW5pdCcsICdtaW5fdmFsdWUnLCAnbWF4X3ZhbHVlJywgJ2J5dGVfb3JkZXInXS5tYXAoZmllbGQgPT4gW2ZpZWxkLCBzaWduYWxbZmllbGRdID8/IG51bGxdKSksXHJcbiAgICAgIGVudW1fdmFsdWVzOiBzaWduYWwuZGF0YT8uZW51bV92YWx1ZXMgPz8gbnVsbCxcclxuICAgICAgc2VtYW50aWNfdHlwZTogc2lnbmFsLnNlbWFudGljPy5zZW1hbnRpY190eXBlID8/IG51bGwsXHJcbiAgICAgIGdlbmVyYXRpb25fcm9sZTogc2lnbmFsLmNvbmZpZ3VyYXRpb24/LmdlbmVyYXRpb25fcm9sZSA/PyBudWxsLFxyXG4gICAgfTtcclxuICB9XHJcbiAgZXhwZWN0KGNvbnRyYWN0cywgJ0V2ZXJ5IG9yaWdpbmFsIHNpZ25hbCBhbmQgaXRzIGV4cGxpY2l0IGVuY29kaW5nIG11c3Qgc3Vydml2ZSBnZW5lcmF0aW9uLicpLnRvRXF1YWwoZXhwZWN0ZWQpO1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiB2ZXJpZnlBcnRpZmFjdHMocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBtaW5pbXVtQ2Fub25pY2FsU2lnbmFsczogbnVtYmVyLCBpbnRlcm5hbENvbnRyb2xsZXI/OiBzdHJpbmcsXG4gIGV4cGVjdGVkUGFyYW1ldGVycz86IFJlY29yZDxzdHJpbmcsIHVua25vd24+LCBleHBlY3RlZE5hdGl2ZVJhdGVzPzogUmVjb3JkPHN0cmluZywgUmVjb3JkPHN0cmluZywgbnVtYmVyPj4pIHtcbiAgLy8gVGhlIGNvbXBsZXRlZCBtb2RlbCBpcyBzdGFibGU7IHRoZXNlIGluZGVwZW5kZW50IHJlYWRzIG5lZWQgbm8gc2VyaWFsIHdhaXRzLlxyXG4gIGNvbnN0IFt3b3JrZmxvdywgam9iTGlzdCwgc25hcHNob3RzLCBzaWduYWxzLCBtZXNzYWdlc10gPSBhd2FpdCBQcm9taXNlLmFsbChbXHJcbiAgICByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKSxcclxuICAgIHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJyksXHJcbiAgICByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9zbmFwc2hvdHMnKSxcclxuICAgIGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ3NpZ25hbHMnKSxcclxuICAgIGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ21lc3NhZ2VzJyksXHJcbiAgXSk7XHJcbiAgZXhwZWN0KE9iamVjdC5rZXlzKHdvcmtmbG93LnN0YXR1c2VzKS5zb3J0KCkpLnRvRXF1YWwoWy4uLnN0ZXBzXS5zb3J0KCkpO1xyXG4gIGZvciAoY29uc3Qgc3RlcCBvZiBzdGVwcykgZXhwZWN0KGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzW3N0ZXBdKSwgYCR7c3RlcH06ICR7d29ya2Zsb3cuc3RhdHVzZXNbc3RlcF19YCkudG9CZVRydXRoeSgpO1xyXG4gIGNvbnN0IGpvYnMgPSBqb2JMaXN0LmpvYnM7XHJcbiAgZXhwZWN0KGpvYnMpLnRvSGF2ZUxlbmd0aCgxKTtcclxuICBleHBlY3Qoam9ic1swXS5zdGF0dXMpLnRvQmUoJ2NvbXBsZXRlZCcpO1xyXG4gIGNvbnN0IHNuYXBzaG90ID0gc25hcHNob3RzLnNpbXVsYXRpb25zLmZpbmQoKGl0ZW06IHsgam9iX2lkOiBzdHJpbmcgfSkgPT4gaXRlbS5qb2JfaWQgPT09IGpvYnNbMF0uaWQpO1xyXG4gIGV4cGVjdChzbmFwc2hvdCkudG9CZVRydXRoeSgpO1xyXG4gIGNvbnN0IGZ1bGwgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9zaW11bGF0aW9uLXNuYXBzaG90cy8ke3NuYXBzaG90LmlkfWApO1xyXG4gIGlmIChleHBlY3RlZFBhcmFtZXRlcnMpIHtcbiAgICBjb25zdCB7IGRhdGFfYml0cmF0ZSwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyLCAuLi5ydW50aW1lUGFyYW1ldGVycyB9ID0gZXhwZWN0ZWRQYXJhbWV0ZXJzO1xyXG4gICAgZXhwZWN0KGZ1bGwuY29uZmlndXJhdGlvbi5wYXJhbWV0ZXJzKS50b01hdGNoT2JqZWN0KHJ1bnRpbWVQYXJhbWV0ZXJzKTtcclxuICAgIGNvbnN0IGNhbkZkTmV0d29ya3MgPSBmdWxsLmNvbmZpZ3VyYXRpb24ubmV0d29ya3MuZmlsdGVyKChuZXR3b3JrOiBhbnkpID0+IG5ldHdvcmsudGVjaG5vbG9neSA9PT0gJ2Nhbl9mZCcpO1xyXG4gICAgZXhwZWN0KGNhbkZkTmV0d29ya3MubGVuZ3RoLCAnVGhlIGVkaXRlZCBDQU4tRkQgY29uZmlndXJhdGlvbiBtdXN0IHJlYWNoIGEgcGh5c2ljYWwgc2ltdWxhdGlvbiBuZXR3b3JrLicpLnRvQmVHcmVhdGVyVGhhbigwKTtcclxuICAgIGZvciAoY29uc3QgbmV0d29yayBvZiBjYW5GZE5ldHdvcmtzKSBleHBlY3QobmV0d29yaykudG9NYXRjaE9iamVjdCh7IGRhdGFfYml0cmF0ZSwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyIH0pO1xuICB9XG4gIGlmIChleHBlY3RlZE5hdGl2ZVJhdGVzKSB7XG4gICAgZm9yIChjb25zdCBbdGVjaG5vbG9neSwgcmF0ZXNdIG9mIE9iamVjdC5lbnRyaWVzKGV4cGVjdGVkTmF0aXZlUmF0ZXMpKSB7XG4gICAgICBjb25zdCBuZXR3b3JrcyA9IGZ1bGwuY29uZmlndXJhdGlvbi5uZXR3b3Jrcy5maWx0ZXIoKG5ldHdvcms6IGFueSkgPT4gbmV0d29yay50ZWNobm9sb2d5ID09PSB0ZWNobm9sb2d5KTtcbiAgICAgIGV4cGVjdChuZXR3b3Jrcy5sZW5ndGgsIGBTYXZlZCAke3RlY2hub2xvZ3l9IHJhdGVzIG11c3QgcmVhY2ggdGhlIGZyb3plbiBzaW11bGF0aW9uLmApLnRvQmVHcmVhdGVyVGhhbigwKTtcbiAgICAgIGZvciAoY29uc3QgbmV0d29yayBvZiBuZXR3b3JrcykgZXhwZWN0KG5ldHdvcmspLnRvTWF0Y2hPYmplY3QocmF0ZXMpO1xuICAgIH1cbiAgfVxuICBjb25zdCBhc3Nlc3NtZW50ID0gZnVsbC5yZXN1bHQuYXNzZXNzbWVudDtcclxuICBleHBlY3QoYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS5zY29wZV9tb2RlKS50b0JlKCdBTEwnKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS5jb21wbGV0ZSkudG9CZSh0cnVlKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5jb25mb3JtYW5jZSkudG9CZSgnUEFTUycpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LmZhaWxlZF9yb3V0ZV9jb3VudCkudG9CZSgwKTtcclxuICBleHBlY3Qoc2lnbmFscy5sZW5ndGgsICdUaGUgZnVsbCBjYW5vbmljYWwgc2lnbmFsIGludmVudG9yeSBtdXN0IHN1cnZpdmUgZ2VuZXJhdGlvbi4nKS50b0JlR3JlYXRlclRoYW5PckVxdWFsKG1pbmltdW1DYW5vbmljYWxTaWduYWxzKTtcclxuICBjb25zdCBleGNsdWRlZCA9IGFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UudHJhbnNwb3J0X2V4Y2x1c2lvbnMgPz8gW107XHJcbiAgZm9yIChjb25zdCBpdGVtIG9mIGV4Y2x1ZGVkKSB7XHJcbiAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXMuZmluZChyb3cgPT4gcm93LmlkID09PSBpdGVtLm1lc3NhZ2VfaWQpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UsIGBFeGNsdWRlZCBtZXNzYWdlICR7aXRlbS5tZXNzYWdlX2lkfSBtdXN0IGV4aXN0LmApLnRvQmVUcnV0aHkoKTtcclxuICAgIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24ucm91dGluZy5lbmFibGVkKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IGNvbnRyYWN0ID0gbWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3Q7XHJcbiAgICBleHBlY3QoY29udHJhY3QuY29uc3VtZXJfcmVmcykudG9FcXVhbChbXSk7XHJcbiAgICBleHBlY3QoaXRlbS5yZWFzb25fY29kZSkudG9CZShjb250cmFjdC5yb2xlID09PSAnSU5URVJOQUxfU1RBVEUnXHJcbiAgICAgID8gJ0lOVEVSTkFMX1NUQVRFX05PVF9ST1VURUQnIDogJ0VYUExJQ0lUX0ZVTkNUSU9OX09VVFBVVF9OT1RfUk9VVEVEJyk7XHJcbiAgfVxyXG4gIGlmIChpbnRlcm5hbENvbnRyb2xsZXIpIHtcclxuICAgIGNvbnN0IG5vZGVzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICAgIGNvbnN0IGNvbnRyb2xsZXIgPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSBpbnRlcm5hbENvbnRyb2xsZXIpO1xyXG4gICAgZXhwZWN0KGV4Y2x1ZGVkLmxlbmd0aCkudG9CZUdyZWF0ZXJUaGFuKDApO1xyXG4gICAgZm9yIChjb25zdCBpdGVtIG9mIGV4Y2x1ZGVkKSB7XHJcbiAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKHJvdyA9PiByb3cuaWQgPT09IGl0ZW0ubWVzc2FnZV9pZCk7XHJcbiAgICAgIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdCkudG9NYXRjaE9iamVjdCh7IHJvbGU6ICdJTlRFUk5BTF9TVEFURScsIHNjb3BlOiAnSU5URVJOQUwnLCBwcm9kdWNlcl9yZWY6IGNvbnRyb2xsZXIuaWQsIGNvbnN1bWVyX3JlZnM6IFtdIH0pO1xyXG4gICAgfVxyXG4gIH1cclxuICBjb25zdCBleGNsdWRlZFNpZ25hbHMgPSBuZXcgU2V0KGV4Y2x1ZGVkLmZsYXRNYXAoKGl0ZW06IHsgc2lnbmFsX2lkczogc3RyaW5nW10gfSkgPT4gaXRlbS5zaWduYWxfaWRzKSk7XHJcbiAgZXhwZWN0KGFzc2Vzc21lbnQub2JzZXJ2ZWRfc2lnbmFsX2NvdW50LCAnQUxMIG11c3Qgb2JzZXJ2ZSBldmVyeSBjYW5vbmljYWwgc2lnbmFsIHdpdGggYSB0cmFuc3BvcnQgb2JsaWdhdGlvbi4nKS50b0JlKHNpZ25hbHMubGVuZ3RoIC0gZXhjbHVkZWRTaWduYWxzLnNpemUpO1xyXG4gIGZvciAoY29uc3Qga2V5IG9mIFsnbWlzc2luZ19vYnNlcnZlZF9zaWduYWxfaWRzJywgJ21pc3Npbmdfb2JzZXJ2ZWRfcm91dGVfaWRzJywgJ21pc3Npbmdfb2JzZXJ2ZWRfbmV0d29ya19pZHMnXSkgZXhwZWN0KGFzc2Vzc21lbnRba2V5XSkudG9FcXVhbChbXSk7XHJcbiAgY29uc3QgdHJhY2UgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9zaW11bGF0aW9ucy8ke2pvYnNbMF0uaWR9L3RyYWNlLXdpbmRvdz9saW1pdD0xMGApO1xyXG4gIGV4cGVjdCh0cmFjZS5jb3VudCkudG9CZUdyZWF0ZXJUaGFuKDApO1xyXG4gIGV4cGVjdCh0cmFjZS5ldmVudHMuc29tZSgoaXRlbTogeyBzaWduYWxzPzogdW5rbm93bltdIH0pID0+IGl0ZW0uc2lnbmFscyAmJiBPYmplY3Qua2V5cyhpdGVtLnNpZ25hbHMpLmxlbmd0aCkpLnRvQmVUcnV0aHkoKTtcclxuICByZXR1cm4geyB3b3JrZmxvdywgam9iOiBqb2JzWzBdLmlkLCBzbmFwc2hvdDogc25hcHNob3QuaWQsIHRyYWNlX2V2ZW50czogZnVsbC5yZXN1bHQudHJhY2UuZXZlbnRzLCBhc3Nlc3NtZW50LCBwYXJhbWV0ZXJfcHJvb2Y6IGV4cGVjdGVkUGFyYW1ldGVycyA/IHtcclxuICAgIHNhdmVkOiBleHBlY3RlZFBhcmFtZXRlcnMsIHNpbXVsYXRpb25fcmF0ZXM6IGZ1bGwuY29uZmlndXJhdGlvbi5uZXR3b3Jrcy5tYXAoKG5ldHdvcms6IGFueSkgPT4gKHtcclxuICAgICAgdGVjaG5vbG9neTogbmV0d29yay50ZWNobm9sb2d5LCBiaXRyYXRlOiBuZXR3b3JrLmJpdHJhdGUsXHJcbiAgICAgIGFyYml0cmF0aW9uX2JpdHJhdGU6IG5ldHdvcmsuYXJiaXRyYXRpb25fYml0cmF0ZSwgZGF0YV9iaXRyYXRlOiBuZXR3b3JrLmRhdGFfYml0cmF0ZSxcclxuICAgICAgaGFyZHdhcmVfZXZpZGVuY2U6IG5ldHdvcmsuaGFyZHdhcmVfZXZpZGVuY2UsXHJcbiAgICB9KSksXHJcbiAgfSA6IHVuZGVmaW5lZCB9O1xyXG59XHJcblxyXG50eXBlIFBhcmFtZXRlclJldHVyblNjZW5hcmlvID0ge1xuICB0ZWNobm9sb2d5OiBzdHJpbmc7XG4gIGZpZWxkczogUmVjb3JkPHN0cmluZywgc3RyaW5nPjtcbiAgbmF0aXZlOiBSZWNvcmQ8c3RyaW5nLCBudW1iZXI+O1xuICBlZGl0RmllbGRzPzogc3RyaW5nW107XG59O1xuXG4vLyBFeGVyY2lzZSB0aGUgdXNlcidzIGRldG91ciwgaW5jbHVkaW5nIHJlcGVhdGVkIHNhdmVzIGluIGFuIGV4aXN0aW5nIHJ1bi5cbi8vIFJlYWRzIGluc3BlY3QgcmVhbCBwZXJzaXN0ZWQgc3RhdGU7IHdyaXRlcyBhbmQgcmV0dXJuIG5hdmlnYXRpb24gdXNlIHRoZSBVSS5cbmFzeW5jIGZ1bmN0aW9uIHJlcGVhdFBhcmFtZXRlclJldHVybihwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIHByb3Bvc2FsSWQ6IHN0cmluZyxcbiAgc2NlbmFyaW9zOiBQYXJhbWV0ZXJSZXR1cm5TY2VuYXJpb1tdLCBzZWVkcyA9IFs0MSwgNDMsIDQyXSkge1xyXG4gIGNvbnN0IGJlZm9yZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xuICBjb25zdCBpZGVudGl0eSA9IGJlZm9yZS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbjtcbiAgZXhwZWN0KGlkZW50aXR5LnJ1bl9pZCkudG9CZVRydXRoeSgpO1xuICBjb25zdCBub2RlSWRzID0gKGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJykpLm1hcChpdGVtID0+IGl0ZW0uaWQpLnNvcnQoKTtcbiAgY29uc3Qgc3RhcnRzOiB1bmtub3duW10gPSBbXTtcbiAgY29uc3QgdHJhY2tTdGFydHMgPSAocmVxdWVzdDogaW1wb3J0KCdwbGF5d3JpZ2h0L3Rlc3QnKS5SZXF1ZXN0KSA9PiB7XG4gICAgaWYgKHJlcXVlc3QudXJsKCkuZW5kc1dpdGgoJy9hcGkvYWdlbnQvY2hhdCcpICYmIHJlcXVlc3QubWV0aG9kKCkgPT09ICdQT1NUJ1xuICAgICAgJiYgcmVxdWVzdC5wb3N0RGF0YUpTT04oKT8ud2l6YXJkX2NvbW1hbmQ/LmFjdGlvbiA9PT0gJ1NUQVJUJykgc3RhcnRzLnB1c2gocmVxdWVzdC5wb3N0RGF0YUpTT04oKSk7XG4gIH07XG4gIGNvbnN0IGV2aWRlbmNlOiB1bmtub3duW10gPSBbXTtcbiAgcGFnZS5vbigncmVxdWVzdCcsIHRyYWNrU3RhcnRzKTtcbiAgdHJ5IHtcbiAgICBjb25zdCB3aXphcmQgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywge25hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbid9KTtcbiAgICBpZiAoYXdhaXQgd2l6YXJkLmlzVmlzaWJsZSgpKSB7XG4gICAgICAvLyBBIGNhcHR1cmVkIEFQSSBTVEFSVCBkb2VzIG5vdCBhY3RpdmF0ZSBhIGJyb3dzZXIgd2l6YXJkIHNlc3Npb24uIEVudGVyXG4gICAgICAvLyBwYXJhbWV0ZXJzIHRocm91Z2ggdGhlIGFjdHVhbCB3b3JrZmxvdyBjYXJkLCBqdXN0IGFzIGEgdXNlciBkb2VzLlxuICAgICAgYXdhaXQgd2l6YXJkLmxvY2F0b3IoJy5hZ2VudC13aXphcmQtcHJvZ3Jlc3MtY2FyZFtocmVmKj1cIm1vZGU9cGFyYW1ldGVyc1wiXScpLmNsaWNrKCk7XG4gICAgICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHtuYW1lOiAnWnVyw7xjayB6dW0gQXVmdHJhZycsIGV4YWN0OiB0cnVlfSkpLnRvQmVWaXNpYmxlKCk7XG4gICAgfVxuICAgIGZvciAoY29uc3QgW2N5Y2xlLCBzZWVkXSBvZiBzZWVkcy5lbnRyaWVzKCkpIHtcclxuICAgICAgZm9yIChjb25zdCBzY2VuYXJpbyBvZiBzY2VuYXJpb3MpIHtcbiAgICAgICAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7ZW5jb2RlVVJJQ29tcG9uZW50KHByb2plY3QpfSZ0ZWNobm9sb2d5PSR7c2NlbmFyaW8udGVjaG5vbG9neX0mcHJvcG9zYWw9JHtwcm9wb3NhbElkfSNwYXJhbWV0ZXItZmluZGluZ3NgKTtcbiAgICAgICAgYXdhaXQgYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeShwYWdlKTtcbiAgICAgICAgY29uc3QgY29tbW9uID0gcGFnZS5sb2NhdG9yKCcucGFyYW1ldGVyLWdyb3VwLWNvbW1vbicpO1xuICAgICAgICBmb3IgKGNvbnN0IFtmaWVsZCwgdmFsdWVdIG9mIE9iamVjdC5lbnRyaWVzKHNjZW5hcmlvLmZpZWxkcykpIHtcbiAgICAgICAgICBjb25zdCBpbnB1dCA9IHBhZ2UubG9jYXRvcihgIyR7ZmllbGR9YCk7XG4gICAgICAgICAgY29uc3QgZGV0YWlscyA9IGlucHV0LmxvY2F0b3IoJ3hwYXRoPWFuY2VzdG9yOjpkZXRhaWxzWzFdJyk7XG4gICAgICAgICAgaWYgKGF3YWl0IGRldGFpbHMuY291bnQoKSAmJiBhd2FpdCBkZXRhaWxzLmdldEF0dHJpYnV0ZSgnb3BlbicpID09PSBudWxsKVxuICAgICAgICAgICAgYXdhaXQgZGV0YWlscy5sb2NhdG9yKCc6c2NvcGUgPiBzdW1tYXJ5JykuY2xpY2soKTtcbiAgICAgICAgICBpZiAoc2NlbmFyaW8uZWRpdEZpZWxkcz8uaW5jbHVkZXMoZmllbGQpKSBhd2FpdCBpbnB1dC5maWxsKHZhbHVlKTtcbiAgICAgICAgICBlbHNlIGF3YWl0IGV4cGVjdChpbnB1dCkudG9IYXZlVmFsdWUodmFsdWUpO1xuICAgICAgICB9XG4gICAgICAgIGF3YWl0IGNvbW1vbi5sb2NhdG9yKCcjc2VlZCcpLmZpbGwoU3RyaW5nKHNlZWQpKTtcbiAgICAgICAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHtuYW1lOiAnUGFyYW1ldGVyIHNwZWljaGVybiDihpInLCBleGFjdDogdHJ1ZX0pLmNsaWNrKCk7XG4gICAgICAgIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnVGVjaG5vbG9naWUtIHVuZCBUaW1pbmctUGFyYW1ldGVyIGdlc3BlaWNoZXJ0LicpKS50b0JlVmlzaWJsZSgpO1xuICAgICAgICBjb25zdCBzYXZlZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnKTtcbiAgICAgICAgZXhwZWN0KHNhdmVkLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XG4gICAgICAgIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLnBhcmFtZXRlcl9wcm92ZW5hbmNlLmR1cmF0aW9uX3MpLnRvRXF1YWwoe3NvdXJjZTonVEVDSE5PTE9HWV9ERUZBVUxUJyx2YWx1ZToxfSk7XHJcbiAgICAgICAgY29uc3Qgc2NvcGVkID0gc2F2ZWQucGFyYW1ldGVycy50ZWNobm9sb2d5X3BhcmFtZXRlcnNbc2NlbmFyaW8udGVjaG5vbG9neV07XG4gICAgICAgIGNvbnN0IGFzc3VtZWQgPSBzYXZlZC5wYXJhbWV0ZXJzLnNpbXVsYXRpb25fcGFyYW1ldGVyX2Fzc3VtcHRpb25zPy5bc2NlbmFyaW8udGVjaG5vbG9neV07XG4gICAgICAgIGV4cGVjdChzY29wZWQudmFsdWVzLnNlZWQpLnRvQmUoc2VlZCk7XG4gICAgICAgIGNvbnN0IG5hdGl2ZVZhbHVlcyA9IHsuLi5hc3N1bWVkPy52YWx1ZXMsIC4uLnNjb3BlZC52YWx1ZXN9O1xuICAgICAgICBleHBlY3QobmF0aXZlVmFsdWVzKS50b01hdGNoT2JqZWN0KHNjZW5hcmlvLm5hdGl2ZSk7XG4gICAgICAgIGZvciAoY29uc3QgW2tleSwgdmFsdWVdIG9mIE9iamVjdC5lbnRyaWVzKHNjZW5hcmlvLm5hdGl2ZSkpIHtcbiAgICAgICAgICBjb25zdCBjb25maXJtZWQgPSBPYmplY3QuaGFzT3duKHNjb3BlZC52YWx1ZXMsIGtleSk7XG4gICAgICAgICAgZXhwZWN0KChjb25maXJtZWQgPyBzY29wZWQgOiBhc3N1bWVkKS5wcm92ZW5hbmNlW2tleV0pLnRvTWF0Y2hPYmplY3QoY29uZmlybWVkXG4gICAgICAgICAgICA/IHtzb3VyY2U6ICdVU0VSX0NPTkZJUk1FRCcsIHN0YXR1czogJ0NPTkZJUk1FRCcsIHZhbHVlfVxuICAgICAgICAgICAgOiB7c291cmNlOiAnTklTX1NJTVVMQVRJT05fQVNTVU1QVElPTicsIHN0YXR1czogJ0FTU1VNRUQnLCB0ZWNobm9sb2d5OiBzY2VuYXJpby50ZWNobm9sb2d5LCBoYXJkd2FyZV9ldmlkZW5jZTogZmFsc2UsIHZhbHVlfSk7XG4gICAgICAgIH1cbiAgICAgICAgY29uc3QgdXNlclZhbHVlcyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMvdXNlci1kZWZpbmVkLXZhbHVlcycpO1xuICAgICAgICBleHBlY3QodXNlclZhbHVlcy5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xuICAgICAgICBleHBlY3QodXNlclZhbHVlcy52YWx1ZV9vcmlnaW4pLnRvQmUoJ1VTRVJfREVGSU5FRF9WQUxVRScpO1xuICAgICAgICBleHBlY3QodXNlclZhbHVlcy5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfZGVmYXVsdHMpLnRvQmVVbmRlZmluZWQoKTtcbiAgICAgICAgZXhwZWN0KHVzZXJWYWx1ZXMucGFyYW1ldGVycy50ZWNobm9sb2d5X3BhcmFtZXRlcnNbc2NlbmFyaW8udGVjaG5vbG9neV0pLnRvRXF1YWwoc2NvcGVkKTtcbiAgICAgICAgY29uc3Qgc3RhbGUgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtwcm9wb3NhbElkfT92aWV3PXN0YXR1c2ApO1xuICAgICAgICBleHBlY3Qoc3RhbGUuZGF0YS5zdGF0dXMpLnRvQmUoJ09VVERBVEVEJyk7XG4gICAgICAgIGNvbnN0IGNhbm9uaWNhbElkcyA9IHN0YWxlLmRhdGEuY2Fub25pY2FsX2lkcztcbiAgICAgICAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcbiAgICAgICAgYXdhaXQgZXhwZWN0KGNvbW1vbi5sb2NhdG9yKCcjc2VlZCcpKS50b0hhdmVWYWx1ZShTdHJpbmcoc2VlZCkpO1xuICAgICAgICBmb3IgKGNvbnN0IFtmaWVsZCwgdmFsdWVdIG9mIE9iamVjdC5lbnRyaWVzKHNjZW5hcmlvLmZpZWxkcykpIHtcbiAgICAgICAgICBjb25zdCBpbnB1dCA9IHBhZ2UubG9jYXRvcihgIyR7ZmllbGR9YCk7XG4gICAgICAgICAgY29uc3QgZGV0YWlscyA9IGlucHV0LmxvY2F0b3IoJ3hwYXRoPWFuY2VzdG9yOjpkZXRhaWxzWzFdJyk7XG4gICAgICAgICAgaWYgKGF3YWl0IGRldGFpbHMuY291bnQoKSAmJiBhd2FpdCBkZXRhaWxzLmdldEF0dHJpYnV0ZSgnb3BlbicpID09PSBudWxsKVxuICAgICAgICAgICAgYXdhaXQgZGV0YWlscy5sb2NhdG9yKCc6c2NvcGUgPiBzdW1tYXJ5JykuY2xpY2soKTtcbiAgICAgICAgICBhd2FpdCBleHBlY3QoaW5wdXQpLnRvSGF2ZVZhbHVlKHZhbHVlKTtcbiAgICAgICAgfVxuICAgICAgICAvLyBLZWVwIHRoZSBleGlzdGluZyBkZWxheWVkLXJlc3RvcmUgcmVncmVzc2lvbiwgdXNpbmcgcmVhbCByZXNwb25zZXMuXG4gICAgICAgIGxldCByZXN1bWVSZXN0b3JlITogKCkgPT4gdm9pZDtcbiAgICAgICAgY29uc3QgcmVzdG9yZVBhdXNlID0gbmV3IFByb21pc2U8dm9pZD4ocmVzb2x2ZSA9PiB7IHJlc3VtZVJlc3RvcmUgPSByZXNvbHZlOyB9KTtcbiAgICAgICAgY29uc3QgZGVsYXlSZXN0b3JlID0gYXN5bmMgKHJvdXRlOiBpbXBvcnQoJ3BsYXl3cmlnaHQvdGVzdCcpLlJvdXRlKSA9PiB7XG4gICAgICAgICAgYXdhaXQgcmVzdG9yZVBhdXNlOyBhd2FpdCByb3V0ZS5jb250aW51ZSgpO1xuICAgICAgICB9O1xuICAgICAgICBjb25zdCBkZWxheWVkID0gY3ljbGUgPT09IDAgJiYgc2NlbmFyaW8gPT09IHNjZW5hcmlvc1swXTtcbiAgICAgICAgaWYgKGRlbGF5ZWQpIGF3YWl0IHBhZ2Uucm91dGUoJyoqL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknLCBkZWxheVJlc3RvcmUpO1xuICAgICAgICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywge25hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbid9KTtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywge25hbWU6ICdadXLDvGNrIHp1bSBBdWZ0cmFnJywgZXhhY3Q6IHRydWV9KS5jbGljaygpO1xuICAgICAgICAgIGlmIChkZWxheWVkKSB7XG4gICAgICAgICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywge25hbWU6ICdHZXNwZWljaGVydGVuIEF1ZnRyYWcgd2llZGVyaGVyc3RlbGxlbid9KSkudG9CZVZpc2libGUoKTtcbiAgICAgICAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cpLm5vdC50b0NvbnRhaW5UZXh0KCdQcm9qZWt0bmFtZTogU2Nocml0dCAxJyk7XG4gICAgICAgICAgfVxuICAgICAgICB9IGZpbmFsbHkge1xuICAgICAgICAgIHJlc3VtZVJlc3RvcmUoKTtcbiAgICAgICAgICBpZiAoZGVsYXllZCkgYXdhaXQgcGFnZS51bnJvdXRlQWxsKHtiZWhhdmlvcjogJ3dhaXQnfSk7XG4gICAgICAgIH1cbiAgICAgICAgLy8gTWF0Y2ggdGhlIGV4aXN0aW5nIHByb3Bvc2FsLXJldmlldyByZWFkaW5lc3MgYnVkZ2V0IGJlbG93LiBUaGUgbmV3XG4gICAgICAgIC8vIHJldHVybiBhc3NlcnRpb24gbXVzdCBub3QgaW1wb3NlIGEgc2hvcnRlciBsaW1pdCBvbiB0aGUgbGFyZ2UgbW9kZWwuXG4gICAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7bmFtZTogJ0VuZ2luZWVyaW5nLVZvcnNjaGxhZyd9KSlcbiAgICAgICAgICAudG9Db250YWluVGV4dCgnR2VwcsO8ZnQgwrcgRnJlaWdhYmUgb2ZmZW4nLCB7dGltZW91dDogNjBfMDAwfSk7XG4gICAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cpLnRvQ29udGFpblRleHQoJ1N0YXR1c8O8YmVyc2ljaHQ6IFNjaHJpdHQgNSB2b24gNScpO1xuICAgICAgICBjb25zdCByZXN0b3JlZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xuICAgICAgICBleHBlY3QocmVzdG9yZWQucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcbiAgICAgICAgZXhwZWN0KHJlc3RvcmVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnJ1bl9pZCkudG9CZShpZGVudGl0eS5ydW5faWQpO1xuICAgICAgICBleHBlY3QocmVzdG9yZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24ucmVxdWVzdF9yZXZpc2lvbikudG9CZShpZGVudGl0eS5yZXF1ZXN0X3JldmlzaW9uKTtcbiAgICAgICAgZXhwZWN0KHJlc3RvcmVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnN0YXRlKS50b0JlKCdSRVZJRVdfUkVRVUlSRUQnKTtcbiAgICAgICAgZXhwZWN0KHJlc3RvcmVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnN0ZXApLnRvQmUoaWRlbnRpdHkuc3RlcCk7XG4gICAgICAgIGZvciAoY29uc3Qgc3RlcCBvZiBzdGVwcykgaWYgKGRvbmUuaGFzKGJlZm9yZS5zdGF0dXNlc1tzdGVwXSkpXG4gICAgICAgICAgZXhwZWN0KGRvbmUuaGFzKHJlc3RvcmVkLnN0YXR1c2VzW3N0ZXBdKSwgYFJldHVybmluZyBtdXN0IHByZXNlcnZlIGNvbXBsZXRlZCBzdGFnZSAke3N0ZXB9LmApLnRvQmUodHJ1ZSk7XG4gICAgICAgIGNvbnN0IGNvbnZlcnNhdGlvbiA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpO1xuICAgICAgICBleHBlY3QoY29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsKS50b0JlKHByb3Bvc2FsSWQpO1xuICAgICAgICBjb25zdCBmcmVzaCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3Byb3Bvc2FsSWR9P3ZpZXc9c3RhdHVzYCk7XG4gICAgICAgIGV4cGVjdChmcmVzaC5kYXRhLnN0YXR1cykudG9CZSgnVkFMSURBVEVEJyk7XG4gICAgICAgIGV4cGVjdChmcmVzaC5kYXRhLmNhbm9uaWNhbF9pZHMpLnRvRXF1YWwoY2Fub25pY2FsSWRzKTtcbiAgICAgICAgZXhwZWN0KChhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpKS5tYXAoaXRlbSA9PiBpdGVtLmlkKS5zb3J0KCkpLnRvRXF1YWwobm9kZUlkcyk7XG4gICAgICAgIGNvbnN0IGFmdGVyID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycpO1xuICAgICAgICBleHBlY3QoYWZ0ZXIucGFyYW1ldGVycykudG9FcXVhbChzYXZlZC5wYXJhbWV0ZXJzKTtcbiAgICAgICAgZXhwZWN0KHN0YXJ0cywgJ1JldHVybmluZyBmcm9tIHBhcmFtZXRlcnMgbXVzdCBuZXZlciByZXN0YXJ0IHRoaXMgcnVuLicpLnRvRXF1YWwoW10pO1xuICAgICAgICBldmlkZW5jZS5wdXNoKHtjeWNsZTogY3ljbGUgKyAxLCB0ZWNobm9sb2d5OiBzY2VuYXJpby50ZWNobm9sb2d5LCBzZWVkLCBydW5faWQ6IGlkZW50aXR5LnJ1bl9pZCxcbiAgICAgICAgICBwcm9wb3NhbF9pZDogcHJvcG9zYWxJZCwgc2F2ZWRfdmFsdWVzOiBzY29wZWQsIGFzc3VtcHRpb25zOiBhc3N1bWVkLFxuICAgICAgICAgIHJlc3RvcmVkX3N0YXR1czogZnJlc2guZGF0YS5zdGF0dXMsIGNhbm9uaWNhbF9pZHM6IGNhbm9uaWNhbElkc30pO1xuICAgICAgfVxuICAgIH1cbiAgfSBmaW5hbGx5IHtcbiAgICBwYWdlLm9mZigncmVxdWVzdCcsIHRyYWNrU3RhcnRzKTtcbiAgICBhd2FpdCB0ZXN0LmluZm8oKS5hdHRhY2goJ3JlcGVhdGVkLXBhcmFtZXRlci1yZXR1cm4nLCB7Ym9keTogSlNPTi5zdHJpbmdpZnkoZXZpZGVuY2UpLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nfSk7XG4gIH1cbn1cblxuYXN5bmMgZnVuY3Rpb24gY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcmVzdGFydDogYm9vbGVhbiwgZXhwZWN0ZWRIYXJkd2FyZTogc3RyaW5nW10gPSBbXSwgY3Jhc2hTaW11bGF0aW9uID0gZmFsc2UsXG4gIGV4cGVjdGVkU2lnbmFscz86IFJlY29yZDxzdHJpbmcsIHVua25vd24+LCBhZnRlckZpcnN0TW9kZWxBcHBsaWVkPzogKCkgPT4gUHJvbWlzZTx2b2lkPiwgc3RvcE9uRXZpZGVuY2VCbG9jayA9IGZhbHNlLFxuICBiZWZvcmVQcm9wb3NhbFJldmlldz86IChwcm9wb3NhbElkOiBzdHJpbmcsIHByb3Bvc2FsVHlwZTogc3RyaW5nKSA9PiBQcm9taXNlPHZvaWQgfCAnU1RPUF9BRlRFUl9SRVZJRVcnPikge1xyXG4gIGxldCByZXZpZXdDb3VudCA9IDA7XHJcbiAgbGV0IHJ1bklkOiBzdHJpbmcgfCB1bmRlZmluZWQ7XHJcbiAgY29uc3QgcmV2aWV3ZWQgPSBuZXcgU2V0PHN0cmluZz4oKTtcclxuICBsZXQgcmVzdGFydGVkSm9iSWQ6IHN0cmluZyB8IHVuZGVmaW5lZDtcclxuICBsZXQgd2F0Y2hkb2cgPSBuZXcgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyhwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgZm9yIChsZXQgY2hlY2twb2ludCA9IDA7IGNoZWNrcG9pbnQgPCAxNjsgY2hlY2twb2ludCsrKSB7XHJcbiAgICBsZXQgd29ya2Zsb3c6IGFueTtcclxuICAgIGxldCBwcm9wb3NhbElkID0gJyc7XHJcbiAgICBsZXQgcmVhZHlWZXJzaW9uID0gJyc7XHJcbiAgICBsZXQgcmVhZHlTaW5jZSA9IDA7XHJcbiAgICBjb25zdCBpc0NoZWNrcG9pbnQgPSBhc3luYyAoKSA9PiB7XHJcbiAgICAgIHdhdGNoZG9nLnJlbWFpbmluZyhwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgICAgIGF3YWl0IGFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkocGFnZSk7XHJcbiAgICAgIHdvcmtmbG93ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgIGNvbnN0IHByb2dyZXNzID0gd2F0Y2hkb2cub2JzZXJ2ZSh3b3JrZmxvdywgcGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gICAgICBpZiAocHJvZ3Jlc3MuYWR2YW5jZWQpIHByb2dyZXNzTWlsZXN0b25lcy5nZXQodGVzdC5pbmZvKCkudGVzdElkKSEucHVzaCh7XHJcbiAgICAgICAgYXQ6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSwgZnJvbnRpZXI6IHByb2dyZXNzLmZyb250aWVyLFxyXG4gICAgICAgIGNvbXBsZXRlZFRocm91Z2g6IHN0ZXBzW3Byb2dyZXNzLmZyb250aWVyIC0gMV0sXHJcbiAgICAgICAgcHJvamVjdDogd29ya2Zsb3cucHJvamVjdF9pZCwgZXhlY3V0aW9uOiB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbixcclxuICAgICAgfSk7XHJcbiAgICAgIGlmIChjcmFzaFNpbXVsYXRpb24gJiYgIXJlc3RhcnRlZEpvYklkICYmIGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzLnZhbGlkYXRpb24pKSB7XHJcbiAgICAgICAgY29uc3Qgam9icyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzO1xyXG4gICAgICAgIGNvbnN0IHJ1bm5pbmcgPSBqb2JzLmZpbmQoKGpvYjogeyBzdGF0dXM6IHN0cmluZyB9KSA9PiBqb2Iuc3RhdHVzID09PSAncnVubmluZycpO1xyXG4gICAgICAgIGlmIChydW5uaW5nKSB7XHJcbiAgICAgICAgICByZXN0YXJ0ZWRKb2JJZCA9IHJ1bm5pbmcuaWQ7XHJcbiAgICAgICAgICBhd2FpdCByZXN0YXJ0QXBwbGljYXRpb24ocGFnZSwgdHJ1ZSk7XHJcbiAgICAgICAgICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgICAgICAgcmV0dXJuIGZhbHNlO1xyXG4gICAgICAgIH1cclxuICAgICAgfVxyXG4gICAgICBpZiAoc3RlcHMuZXZlcnkoc3RlcCA9PiBkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXSkpKSByZXR1cm4gdHJ1ZTtcclxuICAgICAgY29uc3QgZXhlY3V0aW9uID0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb247XHJcbiAgICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnUkVWSUVXX1JFUVVJUkVEJykge1xyXG4gICAgICAgIGNvbnN0IGNvbnZlcnNhdGlvbiA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpO1xyXG4gICAgICAgIHByb3Bvc2FsSWQgPSBjb252ZXJzYXRpb24uZGF0YS5hY3RpdmVfcHJvcG9zYWw7XHJcbiAgICAgICAgLy8gUG9sbGluZyBtYXkgc3RpbGwgZXhwb3NlIHRoZSBqdXN0LWFwcGxpZWQgcmV2aWV3IHdoaWxlIHRoZSBVSSBzdGFydHNcclxuICAgICAgICAvLyBpdHMgZHVyYWJsZSBjb250aW51YXRpb24uIFdhaXQgZm9yIGEgZGlzdGluY3QgcHJvcG9zYWwsIG5vdCBpdHMgbGFiZWwuXHJcbiAgICAgICAgcmV0dXJuIEJvb2xlYW4ocHJvcG9zYWxJZCkgJiYgIXJldmlld2VkLmhhcyhwcm9wb3NhbElkKTtcclxuICAgICAgfVxyXG4gICAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JFQURZX1RPX0NPTlRJTlVFJyB8fCAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5yZWNvdmVyYWJsZSA9PT0gdHJ1ZSkpIHtcclxuICAgICAgICBpZiAocmVhZHlWZXJzaW9uICE9PSBleGVjdXRpb24udXBkYXRlZF9hdCkge1xyXG4gICAgICAgICAgcmVhZHlWZXJzaW9uID0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQ7IHJlYWR5U2luY2UgPSBEYXRlLm5vdygpO1xyXG4gICAgICAgIH1cclxuICAgICAgICAvLyBXaGlsZSBhIGxhcmdlIGNvbnRpbnVhdGlvbiBpcyBnZW5lcmF0aW5nLCB0aGUgbGFzdCBjb21taXR0ZWQgc2VydmVyXHJcbiAgICAgICAgLy8gY2hlY2twb2ludCBjYW4gc3RpbGwgYmUgUkVBRFkuIEFjdCBvbmx5IHdoZW4gdGhlIFVJIG9mZmVycyBpdCB0b28uXHJcbiAgICAgICAgY29uc3QgYnV0dG9uID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KVxyXG4gICAgICAgICAgLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQXVmdHJhZyBmb3J0c2V0emVuJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgICAgICAgcmV0dXJuIERhdGUubm93KCkgLSByZWFkeVNpbmNlID4gNTAwMCAmJiBhd2FpdCBidXR0b24uZXZhbHVhdGVBbGwoYnV0dG9ucyA9PiBidXR0b25zLnNvbWUoYnV0dG9uID0+ICEoYnV0dG9uIGFzIEhUTUxCdXR0b25FbGVtZW50KS5kaXNhYmxlZCAmJiBidXR0b24uZ2V0Q2xpZW50UmVjdHMoKS5sZW5ndGggPiAwICYmIGdldENvbXB1dGVkU3R5bGUoYnV0dG9uKS52aXNpYmlsaXR5ICE9PSBcImhpZGRlblwiKSk7XHJcbiAgICAgIH1cclxuICAgICAgcmV0dXJuIFsnQkxPQ0tFRCcsICdGQUlMRUQnLCAnSU5DT01QTEVURSddLmluY2x1ZGVzKGV4ZWN1dGlvbj8uc3RhdGUpO1xyXG4gICAgfTtcclxuICAgIC8vIEEgc2luZ2xlIHBvbGwgcHJldmlvdXNseSB0aW1lZCBhbGwgb2YgQ2FwYWNpdHkgLT4gSW50ZWxsaWdlbmNlIHRvZ2V0aGVyLlxyXG4gICAgLy8gQm91bmQgZWFjaCBnZW51aW5lIHN0YWdlIGFkdmFuY2UsIHdoaWxlIHJldHJpZXMgYW5kIHJlc3RhcnRzIHJldGFpbiB0aGVpclxyXG4gICAgLy8gcmVtYWluaW5nIGRlYWRsaW5lLiBUaGUgaW5kZXBlbmRlbnQgMjAtbWludXRlIHRlc3QgdGltZW91dCBpcyB1bmNoYW5nZWQuXHJcbiAgICBsZXQgYXR0ZW1wdCA9IDA7XHJcbiAgICB3aGlsZSAoIWF3YWl0IGlzQ2hlY2twb2ludCgpKSB7XHJcbiAgICAgIGNvbnN0IHJlbWFpbmluZyA9IHdhdGNoZG9nLnJlbWFpbmluZyhwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgICAgIGF3YWl0IHBhZ2Uud2FpdEZvclRpbWVvdXQoTWF0aC5taW4oWzUwMCwgMTAwMCwgMjAwMF1bTWF0aC5taW4oYXR0ZW1wdCsrLCAyKV0sIHJlbWFpbmluZykpO1xyXG4gICAgfVxyXG4gICAgcnVuSWQgPz89IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQ7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZCkudG9CZShydW5JZCk7XHJcbiAgICBpZiAoc3RlcHMuZXZlcnkoc3RlcCA9PiBkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXSkpKSB7XHJcbiAgICAgIGlmIChjcmFzaFNpbXVsYXRpb24pIGV4cGVjdChyZXN0YXJ0ZWRKb2JJZCwgJ0EgcmVhbCBydW5uaW5nIHNpbXVsYXRpb24gbXVzdCBiZSBvYnNlcnZlZCBhbmQgaW50ZXJydXB0ZWQuJykudG9CZVRydXRoeSgpO1xyXG4gICAgICByZXR1cm4geyBydW5JZCwgcmV2aWV3ZWQ6IFsuLi5yZXZpZXdlZF0sIHJlc3RhcnRlZEpvYklkIH07XHJcbiAgICB9XHJcbiAgICBjb25zdCBleGVjdXRpb24gPSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbjtcclxuICAgIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XHJcbiAgICBpZiAoc3RvcE9uRXZpZGVuY2VCbG9jayAmJiBleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLmJsb2NraW5nX2ZpbmRpbmdzPy5sZW5ndGgpIHtcclxuICAgICAgdGhyb3cgbmV3IEVycm9yKGBXaXphcmQgQkxPQ0tFRCBhdCAke2V4ZWN1dGlvbi5zdGVwfTogJHtleGVjdXRpb24ubWVzc2FnZX1gKTtcclxuICAgIH1cclxuICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLm1lc3NhZ2U/LmluY2x1ZGVzKCdSRUFEWV9XSVRIX1dBUk5JTkdTJykpIHtcclxuICAgICAgY29uc3QgYmVmb3JlUmV2aWV3ID0gYXdhaXQgcmVhZFdhcm5pbmdSZXZpZXdTdGF0ZShwYWdlLCBwcm9qZWN0KTtcclxuICAgICAgY29uc3QgcHJlZmxpZ2h0ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvcHJlZmxpZ2h0Jyk7XHJcbiAgICAgIGNvbnN0IHdhcm5pbmdzID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnUHJlZmxpZ2h0LVdhcm51bmdlbicgfSk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdCh3YXJuaW5ncy5nZXRCeVJvbGUoJ2xpc3RpdGVtJykuZmlyc3QoKSkudG9CZVZpc2libGUoKTtcclxuICAgICAgY29uc3Qgc3RhcnRlZCA9IHBlcmZvcm1hbmNlLm5vdygpLCBzdGFydGVkV2FsbCA9IERhdGUubm93KCk7XHJcbiAgICAgIHdhdGNoZG9nLnJlbWFpbmluZyhzdGFydGVkKTtcclxuICAgICAgY29uc3QgYXBwcm92YWxSZXNwb25zZSA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IG5ldyBVUkwocmVzcG9uc2UudXJsKCkpLnBhdGhuYW1lID09PSAnL2FwaS9lbmdpbmVlcmluZy9wcmVmbGlnaHQvd2FybmluZ3MvYXBwcm92ZSdcclxuICAgICAgICAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJywgeyB0aW1lb3V0OiAxODBfMDAwIH0pO1xyXG4gICAgICBhd2FpdCB3YXJuaW5ncy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ1dhcm51bmdlbiBmcmVpZ2ViZW4gdW5kIGZvcnRzZXR6ZW4nIH0pLmNsaWNrKCk7XHJcbiAgICAgIGNvbnN0IGFwcHJvdmVkID0gYXdhaXQgYXBwcm92YWxSZXNwb25zZTtcclxuICAgICAgY29uc3QgcmVjZWlwdCA9IGF3YWl0IGFwcHJvdmVkLmpzb24oKTtcclxuICAgICAgY29uc3QgYWZ0ZXJSZXZpZXcgPSBhd2FpdCByZWFkV2FybmluZ1Jldmlld1N0YXRlKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgICBjb25zdCBwcm9vZiA9IHsgYmVmb3JlOiBiZWZvcmVSZXZpZXcsIGFmdGVyOiBhZnRlclJldmlldywgc25hcHNob3RJZDogcHJlZmxpZ2h0LmlkLFxyXG4gICAgICAgIHJlcXVlc3RQcm9qZWN0OiBhcHByb3ZlZC5yZXF1ZXN0KCkuaGVhZGVycygpWyd4LXByb2plY3QtaWQnXSwgc3VibWl0dGVkOiBhcHByb3ZlZC5yZXF1ZXN0KCkucG9zdERhdGFKU09OKCksXHJcbiAgICAgICAgc3RhdHVzOiBhcHByb3ZlZC5zdGF0dXMoKSwgcmVzcG9uc2U6IHJlY2VpcHQsIHN0YXJ0ZWQsIHN0YXJ0ZWRXYWxsLCBmaW5pc2hlZFdhbGw6IERhdGUubm93KCkgfTtcclxuICAgICAgY29uc3QgY29tbWl0dGVkQXQgPSBwZXJmb3JtYW5jZS5ub3coKTtcclxuICAgICAgY29uc3QgY29tbWl0dGVkID0gd2F0Y2hkb2cuY29tbWl0V2FybmluZ1Jldmlldyhwcm9vZiwgY29tbWl0dGVkQXQpO1xyXG4gICAgICBhd2FpdCB0ZXN0LmluZm8oKS5hdHRhY2goJ3ZlcmlmaWVkLXdhcm5pbmctcmV2aWV3LXByb29mJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb29mLCBjb21taXR0ZWRBdCwgY29tbWl0dGVkIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gICAgICBwcm9ncmVzc01pbGVzdG9uZXMuZ2V0KHRlc3QuaW5mbygpLnRlc3RJZCkhLnB1c2goeyBhdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLCBtYW51YWxXYXJuaW5nQXBwcm92YWw6IGNvbW1pdHRlZC5hcHByb3ZhbElkZW50aXR5LFxyXG4gICAgICAgIGZyb250aWVyOiBjb21taXR0ZWQuZnJvbnRpZXIsIHByb2plY3QsIGV4ZWN1dGlvbjogYWZ0ZXJSZXZpZXcuY29udGV4dC5hZ2VudF9leGVjdXRpb24sIGFwcHJvdmFsOiByZWNlaXB0LmFwcHJvdmFsIH0pO1xyXG4gICAgICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5JykpLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0LFxyXG4gICAgICAgIHsgdGltZW91dDogZXhwZWN0ZWRIYXJkd2FyZS5sZW5ndGggPiAxMDAgPyAxODBfMDAwIDogNjBfMDAwIH0pLm5vdC50b0JlKGV4ZWN1dGlvbi51cGRhdGVkX2F0KTtcclxuICAgICAgY29udGludWU7XHJcbiAgICB9XHJcbiAgICBpZiAoWydCTE9DS0VEJywgJ0ZBSUxFRCcsICdJTkNPTVBMRVRFJ10uaW5jbHVkZXMoZXhlY3V0aW9uPy5zdGF0ZSkgJiYgZXhlY3V0aW9uLnJlY292ZXJhYmxlICE9PSB0cnVlKSB7XHJcbiAgICAgIGNvbnN0IGNvbnZlcnNhdGlvbiA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpO1xyXG4gICAgICBjb25zdCBpZCA9IGNvbnZlcnNhdGlvbi5kYXRhPy5hY3RpdmVfcHJvcG9zYWw7XHJcbiAgICAgIGNvbnN0IHByb3Bvc2FsID0gaWQgPyBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtpZH1gKSA6IG51bGw7XHJcbiAgICAgIGF3YWl0IHRlc3QuaW5mbygpLmF0dGFjaCgnd2l6YXJkLWJsb2NrZXInLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgZXhlY3V0aW9uLFxyXG4gICAgICAgIHByb3Bvc2FsOiBwcm9wb3NhbD8uZGF0YT8udmFsaWRhdGlvbl9yZXN1bHQsIHZpc2libGU6IGF3YWl0IGRpYWxvZy5pbm5lclRleHQoKSB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICAgICAgdGhyb3cgbmV3IEVycm9yKGBXaXphcmQgJHtleGVjdXRpb24uc3RhdGV9IGF0ICR7ZXhlY3V0aW9uLnN0ZXB9OiAke2V4ZWN1dGlvbi5tZXNzYWdlfWApO1xyXG4gICAgfVxyXG4gICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdSRUFEWV9UT19DT05USU5VRScgfHwgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24ucmVjb3ZlcmFibGUgPT09IHRydWUpKSB7XHJcbiAgICAgIGNvbnN0IGJ1dHRvbiA9IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1ZnRyYWcgZm9ydHNldHplbicsIGV4YWN0OiB0cnVlIH0pO1xyXG4gICAgICB0cnkge1xyXG4gICAgICAgIGF3YWl0IGJ1dHRvbi5jbGljayh7IHRpbWVvdXQ6IDIwMDAgfSk7XHJcbiAgICAgIH0gY2F0Y2ggKGVycm9yKSB7XHJcbiAgICAgICAgY29uc3QgbGF0ZXN0ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgICAgaWYgKGxhdGVzdC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCA9PT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQgJiYgYXdhaXQgYnV0dG9uLmV2YWx1YXRlQWxsKGJ1dHRvbnMgPT4gYnV0dG9ucy5zb21lKGJ1dHRvbiA9PiAhKGJ1dHRvbiBhcyBIVE1MQnV0dG9uRWxlbWVudCkuZGlzYWJsZWQgJiYgYnV0dG9uLmdldENsaWVudFJlY3RzKCkubGVuZ3RoID4gMCAmJiBnZXRDb21wdXRlZFN0eWxlKGJ1dHRvbikudmlzaWJpbGl0eSAhPT0gXCJoaWRkZW5cIikpKSB0aHJvdyBlcnJvcjtcclxuICAgICAgICBjb250aW51ZTtcclxuICAgICAgfVxyXG4gICAgICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICAgICAgY29uc3QgbGF0ZXN0ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgICAgcmV0dXJuIGxhdGVzdC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCAhPT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXRcclxuICAgICAgICAgIHx8IGxhdGVzdC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uc3RhdGUgPT09ICdSVU5OSU5HJ1xyXG4gICAgICAgICAgfHwgbGF0ZXN0LnN0YXR1c2VzPy5bZXhlY3V0aW9uLnN0ZXBdID09PSAnSU5fUFJPR1JFU1MnO1xyXG4gICAgICB9LCB7IHRpbWVvdXQ6IDYwXzAwMCB9KS50b0JlKHRydWUpO1xyXG4gICAgICBjb250aW51ZTtcclxuICAgIH1cclxuICAgIGNvbnN0IGNhbmRpZGF0ZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3Byb3Bvc2FsSWR9YCk7XHJcbiAgICBpZiAoY2FuZGlkYXRlLmRhdGEucHJvcG9zYWxfdHlwZSA9PT0gJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcgJiYgcmV2aWV3Q291bnQgPT09IDAgJiYgZXhwZWN0ZWRIYXJkd2FyZS5sZW5ndGgpIHtcclxuICAgICAgY29uc3QgaGFyZHdhcmUgPSBjYW5kaWRhdGUuZGF0YS5jaGFuZ2VzXHJcbiAgICAgICAgLmZpbHRlcigoY2hhbmdlOiB7IG9iamVjdF90eXBlOiBzdHJpbmcgfSkgPT4gY2hhbmdlLm9iamVjdF90eXBlID09PSAnSGFyZHdhcmVOb2RlJylcclxuICAgICAgICAubWFwKChjaGFuZ2U6IHsgZGF0YTogeyBuYW1lOiBzdHJpbmcgfSB9KSA9PiBjaGFuZ2UuZGF0YS5uYW1lKTtcclxuICAgICAgZXhwZWN0KGhhcmR3YXJlLCAnVGhlIFVJIG11c3QgcHJlc2VydmUgdGhlIGhhcmR3YXJlIGV4cGxpY2l0bHkgbmFtZWQgaW4gdGhlIHVzZXIgcmVxdWVzdC4nKVxyXG4gICAgICAgIC50b0VxdWFsKGV4cGVjdC5hcnJheUNvbnRhaW5pbmcoZXhwZWN0ZWRIYXJkd2FyZSkpO1xyXG4gICAgfVxyXG4gICAgZXhwZWN0KHJldmlld2VkLmhhcyhwcm9wb3NhbElkKSwgJ1RoZSBzYW1lIHByb3Bvc2FsIG11c3Qgbm90IHJlcXVlc3QgcmV2aWV3IHR3aWNlLicpLnRvQmUoZmFsc2UpO1xuICAgIGNvbnN0IHJldmlld0FjdGlvbiA9IGF3YWl0IGJlZm9yZVByb3Bvc2FsUmV2aWV3Py4ocHJvcG9zYWxJZCwgY2FuZGlkYXRlLmRhdGEucHJvcG9zYWxfdHlwZSk7XHJcbiAgICBpZiAocmV2aWV3QWN0aW9uID09PSAnU1RPUF9BRlRFUl9SRVZJRVcnKSB7XHJcbiAgICAgIC8vIEV4cGxpY2l0IHRhcmdldGVkIGNvdmVyYWdlOiB0aGUgc2VsZWN0ZWQgcGVuZGluZyBwcm9wb3NhbCBoYXMgYmVlblxyXG4gICAgICAvLyBleGVyY2lzZWQgYnV0IGlzIG5vdCBhcHBsaWVkIGFuZCB0aGlzIGlzIG5vdCBuaW5lLXN0YWdlIGNvbXBsZXRpb24uXHJcbiAgICAgIHJldHVybiB7IHJ1bklkLCByZXZpZXdlZDogWy4uLnJldmlld2VkXSwgcmVzdGFydGVkSm9iSWQsXHJcbiAgICAgICAgcmV2aWV3T25seTogeyBwcm9wb3NhbElkLCBwcm9wb3NhbFR5cGU6IGNhbmRpZGF0ZS5kYXRhLnByb3Bvc2FsX3R5cGUgfSB9O1xyXG4gICAgfVxyXG4gICAgY29uc3QgYXBwbHlSZXNwb25zZSA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IHJlc3BvbnNlLnVybCgpLmluY2x1ZGVzKGAvcHJvcG9zYWxzLyR7cHJvcG9zYWxJZH0vYXBwcm92ZS1hcHBseWApICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnLCB7IHRpbWVvdXQ6IDE4MF8wMDAgfSk7XHJcbiAgICBjb25zdCBhcHByb3ZhbCA9IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogL14oRnJlaWdlYmVuLCDDvGJlcm5laG1lbiAmIGZvcnRmYWhyZW58w5xiZXJuZWhtZW4gJiBmb3J0ZmFocmVuKSQvIH0pO1xyXG4gICAgYXdhaXQgZXhwZWN0KGFwcHJvdmFsKS50b0JlRW5hYmxlZCh7IHRpbWVvdXQ6IDYwXzAwMCB9KTtcclxuICAgIGF3YWl0IGFwcHJvdmFsLmNsaWNrKCk7XHJcbiAgICBjb25zdCBhcHBsaWVkID0gYXdhaXQgYXBwbHlSZXNwb25zZTtcclxuICAgIGlmICghYXBwbGllZC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYEhUVFAgJHthcHBsaWVkLnN0YXR1cygpfTogJHsoYXdhaXQgYXBwbGllZC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gICAgZXhwZWN0KChhd2FpdCBhcHBsaWVkLmpzb24oKSkuZGF0YS5zdGF0dXMpLnRvQmUoJ0FQUExJRUQnKTtcclxuICAgIHJldmlld2VkLmFkZChwcm9wb3NhbElkKTsgcmV2aWV3Q291bnQrKztcclxuICAgIC8vIEEgZGlzdGluY3QsIGFjdHVhbGx5IGNvbW1pdHRlZCBtYW51YWwgcmV2aWV3IHN0YXJ0cyB0aGUgbmV4dCBhdXRvbWF0aWNcclxuICAgIC8vIHNlY3Rpb24uIEl0cyB3cml0ZSBzdGlsbCBoYXMgdGhlIHNlcGFyYXRlIHVuY2hhbmdlZCAxODAtc2Vjb25kIGxpbWl0LlxyXG4gICAgd2F0Y2hkb2cgPSBuZXcgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyhwZXJmb3JtYW5jZS5ub3coKSwgd29ya2Zsb3cpO1xyXG4gICAgaWYgKGNhbmRpZGF0ZS5kYXRhLnByb3Bvc2FsX3R5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnICYmIGV4cGVjdGVkU2lnbmFscykge1xyXG4gICAgICBhd2FpdCB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZSwgcHJvamVjdCwgZXhwZWN0ZWRTaWduYWxzKTtcclxuICAgIH1cclxuICAgIGlmIChyZXZpZXdDb3VudCA9PT0gMSAmJiBhZnRlckZpcnN0TW9kZWxBcHBsaWVkKSB7XHJcbiAgICAgIGF3YWl0IGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQoKTtcclxuICAgICAgLy8gVGhpcyBvbmUgdGVzdCBleHBsaWNpdGx5IHN1Ym1pdHMgQU1FTkQgYW5kIHdhaXRzIGZvciBpdHMgcmVjZWlwdC4gT25seVxyXG4gICAgICAvLyB0aGF0IGRlbGliZXJhdGUgYWN0aW9uIHBlcm1pdHMgYmluZGluZyBpdHMgbmV3IHJlcXVlc3QgcmV2aXNpb24uXHJcbiAgICAgIGNvbnN0IGFtZW5kZWQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgZXhwZWN0KGFtZW5kZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZCkudG9CZShydW5JZCk7XHJcbiAgICAgIHdhdGNoZG9nID0gbmV3IFdpemFyZFByb2dyZXNzV2F0Y2hkb2cocGVyZm9ybWFuY2Uubm93KCksIGFtZW5kZWQpO1xyXG4gICAgfVxyXG4gICAgaWYgKHJldmlld0NvdW50ID09PSAxKSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpOyAvLyBEdXJhYmxlIHJlbG9hZCBhZnRlciBhIHJlYWwgY29tbWl0LlxyXG4gICAgaWYgKHJlc3RhcnQgJiYgcmV2aWV3Q291bnQgPT09IDIpIHtcclxuICAgICAgYXdhaXQgcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2UpO1xyXG4gICAgICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgfVxyXG4gICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgICBjb25zdCBjdXJyZW50ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgIHJldHVybiBjdXJyZW50LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0ICE9PSBleGVjdXRpb24udXBkYXRlZF9hdDtcclxuICAgIH0sIHsgdGltZW91dDogNjBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbiAgfVxyXG4gIHRocm93IG5ldyBFcnJvcignV2l6YXJkIGV4Y2VlZGVkIDE2IHJldmlldy9jb250aW51YXRpb24gY2hlY2twb2ludHMuJyk7XHJcbn1cclxuXHJcbnRlc3QoJ3dpemFyZCByZWZ1c2VzIGFuIHVuYXZhaWxhYmxlIGNhdGFsb2cgYW5kIHJlY292ZXJzIHVzaW5nIHRoZSByZWFsIHJlZ2lzdHJ5IEBjYXRhbG9nLXJlY292ZXJ5JywgYXN5bmMgKHtwYWdlfSkgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1jYXRhbG9nLXJlY292ZXJ5LScgKyByYW5kb21VVUlEKCk7XHJcbiAgYXdhaXQgcGFnZS5yb3V0ZSgnKiovYXBpL3RlY2hub2xvZ2llcycsIHJvdXRlID0+IHJvdXRlLmZ1bGZpbGwoe3N0YXR1czo1MDMsXHJcbiAgICBjb250ZW50VHlwZTonYXBwbGljYXRpb24vanNvbicsYm9keTpKU09OLnN0cmluZ2lmeSh7ZXJyb3I6J0RlciB2b2xsc3TDpG5kaWdlIFRlY2hub2xvZ2lla2F0YWxvZyBpc3QgZGVyemVpdCBuaWNodCBlcnJlaWNoYmFyLid9KX0pKTtcclxuICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdhbGVydCcpKS50b0NvbnRhaW5UZXh0KCdUZWNobm9sb2dpZWthdGFsb2cnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7ZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdDYXRhbG9nIHJldHJ5Jyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7ZXhhY3Q6dHJ1ZX0pLmZpbGwoJ2VpbiBBa3RvciB6dW0gcHJvcG9ydGlvbmFsIHNjaGxpZcOfZW4gZWluZXMgVmVudGlsJyk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJykpLnRvQmVEaXNhYmxlZCgpO1xyXG4gIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icykudG9IYXZlTGVuZ3RoKDApO1xyXG4gIGF3YWl0IHBhZ2UudW5yb3V0ZSgnKiovYXBpL3RlY2hub2xvZ2llcycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6J1RlY2hub2xvZ2lla2F0YWxvZyBlcm5ldXQgbGFkZW4nfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYWxlcnQnKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJykpLnRvQmVFbmFibGVkKCk7XHJcbiAgY29uc3QgY2F0YWxvZyA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL3RlY2hub2xvZ2llcycpKS5qc29uKCk7XHJcbiAgZXhwZWN0KGNhdGFsb2cudGVjaG5vbG9neV9jb3VudCkudG9CZSgxMjUpO1xyXG59KTtcclxuXHJcbnRlc3QoJ25ldyBzbWFsbCB3aXphcmQgdHJhdmVyc2VzIGFsbCBuaW5lIHN0YWdlcyBhbmQgc3Vydml2ZXMgcmVsb2FkL3Jlc3RhcnQgQHNtYWxsJywgYXN5bmMgKHsgcGFnZSwgYnJvd3NlciB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IGVycm9yczogc3RyaW5nW10gPSBbXTsgcGFnZS5vbigncGFnZWVycm9yJywgZXJyb3IgPT4gZXJyb3JzLnB1c2goZXJyb3IubWVzc2FnZSkpO1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1zbWFsbC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjZW5naW5lZXJpbmctcHJvamVjdC1uYW1lJykuZmlsbCgnRTJFIHNtYWxsJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwoJ0VyemV1Z2UgZWluIEF1dG9tb3RpdmUgQ0FOLUZEIE5ldHp3ZXJrIG1pdCBlaW5lbSBHYXRld2F5IFN5c3RlbSwgZGVuIEVDVXMgTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UsIGVpbmVtIFNlbnNvciBNb3RvclRlbXBlcmF0dXJlIHVuZCBlaW5lbSBBa3RvciBNb3RvclZhbHZlLiBNb3RvclRlbXBlcmF0dXJlIHdpcmQgdm9uIE1vdG9yc3RldWVydW5nIGF1c2dld2VydGV0LiBNb3RvcnN0ZXVlcnVuZyBzdGV1ZXJ0IE1vdG9yVmFsdmUuIENvbnRyb2xsZXJzdGF0dXMgYmxlaWJ0IGJpcyB6dXIgQXVzd2FobCBrb25rcmV0ZXIgRW1wZsOkbmdlciB1bmQgU2lnbmFsZSBpbnRlcm4uIFByw7xmZSB1bmQgYXJiZWl0ZSBiaXMgRGF0YSBTY2llbmNlICYgSW50ZWxsaWdlbmNlLlxcbkNBTi1GRDogNTAwIGtiaXQvcyBhcmJpdHJhdGlvbiwgMiBNYml0L3MgZGF0YVxcbkNBTjogNTAwIGtiaXQvcycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdXZWl0ZXJlIEhpbndlaXNlJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKCctIEFrdG9yLUJlZmVobGU6IHtcIk1vdG9yVmFsdmVcIjp7XCJsZW5ndGhfYml0c1wiOjEsXCJkYXRhX3R5cGVcIjpcImJvb2xlYW5cIixcImZhY3RvclwiOjEsXCJ1bml0XCI6XCJjb2RlXCIsXCJtaW5fdmFsdWVcIjowLFwibWF4X3ZhbHVlXCI6MSxcInNlbWFudGljXCI6e1wic2VtYW50aWNfdHlwZVwiOlwiQk9PTEVBTlwifSxcImRhdGFcIjp7XCJlbnVtX3ZhbHVlc1wiOntcIkNMT1NFXCI6MCxcIk9QRU5cIjoxfX19fScpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdHZXLDpHRldW1mYW5nJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGZvciAoY29uc3QgW2xhYmVsLCB2YWx1ZV0gb2YgW1snR2F0ZXdheXMnLCAnMSddLCBbJ0NvbnRyb2xsZXInLCAnMiddLCBbJ1NlbnNvcmVuJywgJzEnXSwgWydBa3RvcmVuJywgJzEnXV0pIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKGAke2xhYmVsfTogdmVyYmluZGxpY2hlIEFuemFobGAsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCh2YWx1ZSk7XHJcbiAgY29uc3Qgc3RhcnRSZXF1ZXN0ID0gcGFnZS53YWl0Rm9yUmVxdWVzdChyZXF1ZXN0ID0+IHJlcXVlc3QudXJsKCkuZW5kc1dpdGgoJy9hcGkvYWdlbnQvY2hhdCcpXHJcbiAgICAmJiByZXF1ZXN0Lm1ldGhvZCgpID09PSAnUE9TVCcgJiYgcmVxdWVzdC5wb3N0RGF0YUpTT04oKT8ud2l6YXJkX2NvbW1hbmQ/LmFjdGlvbiA9PT0gJ1NUQVJUJyk7XHJcbiAgLy8gVXNlIHRoZSBzYW1lIHZpc2libGUgcXVlc3Rpb25uYWlyZSBuYXZpZ2F0aW9uIGEgdXNlciB1c2VzOyBuZXZlciBpbmplY3QgZ2VuZXJhdGVkIG1vZGVsIHJvd3MuXHJcbiAgZm9yIChsZXQgc3RlcCA9IDA7IHN0ZXAgPCAxMDsgc3RlcCsrKSB7XHJcbiAgICBjb25zdCBzdWJtaXQgPSBkaWFsb2cubG9jYXRvcignLmVuZy1hZ2VudC1xdWVzdGlvbm5haXJlLWhlYWQnKS5nZXRCeVJvbGUoJ2J1dHRvbicpO1xyXG4gICAgYXdhaXQgZXhwZWN0KHN1Ym1pdCkudG9CZUVuYWJsZWQoKTtcclxuICAgIGNvbnN0IG5hbWUgPSBhd2FpdCBzdWJtaXQuaW5uZXJUZXh0KCk7XHJcbiAgICBhd2FpdCBzdWJtaXQuY2xpY2soKTtcclxuICAgIGlmIChuYW1lID09PSAnw5xiZXJuZWhtZW4nKSBicmVhaztcclxuICAgIGlmIChzdGVwID09PSA5KSB0aHJvdyBuZXcgRXJyb3IoJ1F1ZXN0aW9ubmFpcmUgZGlkIG5vdCBvZmZlciBzdWJtaXQuJyk7XHJcbiAgfVxyXG4gIGNvbnN0IHJlcXVlc3RlZCA9IChhd2FpdCBzdGFydFJlcXVlc3QpLnBvc3REYXRhSlNPTigpLndpemFyZF9jb21tYW5kLndpemFyZF9jb250ZXh0O1xyXG4gIGV4cGVjdChyZXF1ZXN0ZWQudGVjaG5vbG9naWVzLCAnQW4gZXhwbGljaXQgQ0FOLUZEIHRhc2sgbXVzdCBub3Qgc2lsZW50bHkgcmVxdWVzdCBMSU4gYW5kIFNPTUUvSVAuJykudG9FcXVhbChbJ0NBTi1GRCAoY2FuX2ZkKSddKTtcclxuICAvLyBQcmVzZXJ2ZSBhIHJlYWwgcGVuZGluZyBtb2RlbCB0aHJvdWdoIHBhcmFtZXRlciBzYXZlIGFuZCByZW5ld2VkIHJldmlldy5cclxuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiAoYXdhaXQgcmVhZFByb2plY3QocGFnZSxwcm9qZWN0LCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpKS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uc3RhdGUsXHJcbiAgICB7dGltZW91dDoxODAwMDB9KS50b0JlKCdSRVZJRVdfUkVRVUlSRUQnKTtcclxuICBjb25zdCBwZW5kaW5nID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UscHJvamVjdCwnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKSkuZGF0YS5hY3RpdmVfcHJvcG9zYWw7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7cHJvamVjdH0mdGVjaG5vbG9neT1jYW5fZmQmcHJvcG9zYWw9JHtwZW5kaW5nfSNwYXJhbWV0ZXItZmluZGluZ3NgKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicse25hbWU6J0FrdHVlbGxlIFBhcmFtZXRlcmJlZnVuZGUnfSkpLnRvQ29udGFpblRleHQoJ25vY2ggbmljaHQgw7xiZXJub21tZW5lbiBWb3JzY2hsYWdzJyk7XHJcbiAgY29uc3QgY29tbW9uID0gcGFnZS5sb2NhdG9yKCcucGFyYW1ldGVyLWdyb3VwLWNvbW1vbicpO1xyXG4gIGF3YWl0IGV4cGVjdChjb21tb24ubG9jYXRvcignI2FyYml0cmF0aW9uX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzUwMCBrYml0L3MnKTtcclxuICBhd2FpdCBleHBlY3QoY29tbW9uLmxvY2F0b3IoJyNkYXRhX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzIgTWJpdC9zJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignLnBhcmFtZXRlci1kZXRhaWxzW29wZW5dJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IHJlcGVhdFBhcmFtZXRlclJldHVybihwYWdlLCBwcm9qZWN0LCBwZW5kaW5nLCBbe3RlY2hub2xvZ3k6ICdjYW5fZmQnLFxuICAgIGZpZWxkczoge2FyYml0cmF0aW9uX2JpdHJhdGU6ICc1MDAga2JpdC9zJywgZGF0YV9iaXRyYXRlOiAnMSBNYml0L3MnLCBjYW5fZmRfZGF0YV9wcmVzY2FsZXI6ICcyJ30sXG4gICAgbmF0aXZlOiB7YXJiaXRyYXRpb25fYml0cmF0ZTogNTAwXzAwMCwgZGF0YV9iaXRyYXRlOiAxXzAwMF8wMDAsIGNhbl9mZF9kYXRhX3ByZXNjYWxlcjogMn0sXG4gICAgZWRpdEZpZWxkczogWydkYXRhX2JpdHJhdGUnLCAnY2FuX2ZkX2RhdGFfcHJlc2NhbGVyJ119XSk7XG4gIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSxwcm9qZWN0LGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3BlbmRpbmd9P3ZpZXc9c3RhdHVzYCkpLmRhdGEuY2Fub25pY2FsX2lkcykudG9FcXVhbChbXSk7XG4gIGV4cGVjdCgoYXdhaXQgYWxsT2JqZWN0cyhwYWdlLHByb2plY3QsJ2hhcmR3YXJlLW5vZGVzJykpKS50b0hhdmVMZW5ndGgoMCk7XG4gIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgdHJ1ZSxcclxuICAgIFsnU3lzdGVtJywgJ01vdG9yc3RldWVydW5nJywgJ0FuemVpZ2UnLCAnTW90b3JUZW1wZXJhdHVyZScsICdNb3RvclZhbHZlJ10pO1xyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCA1LCB1bmRlZmluZWQsIHtcclxuICAgIHNlZWQ6IDQyLCBkYXRhX2JpdHJhdGU6IDFfMDAwXzAwMCwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyOiAyLFxyXG4gIH0pO1xyXG4gIGV4cGVjdChhcnRpZmFjdHMuYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoMyk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnRyYW5zcG9ydF9leGNsdXNpb25zKS50b0hhdmVMZW5ndGgoMyk7XHJcbiAgY29uc3QgZmluaXNoZWQgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5pbmNsdWRlcyhgL3J1bnMvJHtjb250aW51aXR5LnJ1bklkfS9maW5pc2hgKVxyXG4gICAgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0ZlcnRpZyBzdGVsbGVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBleHBlY3QoKGF3YWl0IGZpbmlzaGVkKS5vaygpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cpLm5vdC50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlKS50b0hhdmVVUkwobmV3IFJlZ0V4cChgL3N0dWRpby9yZXN1bHRzXFxcXD9zbmFwc2hvdD0ke2FydGlmYWN0cy5zbmFwc2hvdH0mcHJvamVjdD0ke3Byb2plY3R9JGApKTtcclxuICBjb25zdCBzZWxlY3RlZFJ1biA9IHBhZ2UubG9jYXRvcihgLnJlc3VsdC1ydW4tbGlzdCBidXR0b25bZGF0YS1zbmFwc2hvdC1pZD1cIiR7YXJ0aWZhY3RzLnNuYXBzaG90fVwiXWApO1xyXG4gIGF3YWl0IGV4cGVjdChzZWxlY3RlZFJ1bikudG9IYXZlQ2xhc3MoJ2FjdGl2ZScpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnQW5mb3JkZXJ1bmdzZXJmw7xsbHVuZzogQmVzdGFuZGVuJywgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcubWV0cmljJykuZmlsdGVyKHsgaGFzOiBwYWdlLmdldEJ5VGV4dCgnVHJhY2UgRXZlbnRzJywgeyBleGFjdDogdHJ1ZSB9KSB9KSlcclxuICAgIC50b0NvbnRhaW5UZXh0KGFydGlmYWN0cy50cmFjZV9ldmVudHMudG9Mb2NhbGVTdHJpbmcoJ2RlLURFJykpO1xyXG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHNlbGVjdGVkUnVuKS50b0hhdmVDbGFzcygnYWN0aXZlJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdBbmZvcmRlcnVuZ3NlcmbDvGxsdW5nOiBCZXN0YW5kZW4nLCB7IGV4YWN0OiB0cnVlIH0pKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdsaW5rJywgeyBuYW1lOiAnU2ltdWxhdGlvbiDDtmZmbmVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBjb25zdCBydW5uZXIgPSBwYWdlLmxvY2F0b3IoJy5tb2RlbC1zaW11bGF0aW9uLXJ1bm5lcicpO1xyXG4gIGF3YWl0IGV4cGVjdChydW5uZXIpLnRvSGF2ZUF0dHJpYnV0ZSgnZGF0YS1qb2ItaWQnLCBhcnRpZmFjdHMuam9iKTtcclxuICBhd2FpdCBleHBlY3QocnVubmVyKS50b0hhdmVBdHRyaWJ1dGUoJ2RhdGEtc25hcHNob3QtaWQnLCBhcnRpZmFjdHMuc25hcHNob3QpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnaGVhZGluZycsIHsgbmFtZTogJ1NpbXVsYXRpb24gYWJnZXNjaGxvc3NlbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHJ1bm5lcikudG9IYXZlQXR0cmlidXRlKCdkYXRhLWpvYi1pZCcsIGFydGlmYWN0cy5qb2IpO1xyXG4gIC8vIEEgbmV3IGJyb3dzZXIgY29udGV4dCBoYXMgbm8gc2Vzc2lvbiBrZXkgZnJvbSBlaXRoZXIgd2l6YXJkIG9yIHNpbXVsYXRpb24gVUkuXHJcbiAgY29uc3QgZnJlc2hDb250ZXh0ID0gYXdhaXQgYnJvd3Nlci5uZXdDb250ZXh0KHsgYmFzZVVSTDogbmV3IFVSTChwYWdlLnVybCgpKS5vcmlnaW4gfSk7XHJcbiAgdHJ5IHtcclxuICAgIGNvbnN0IGZyZXNoID0gYXdhaXQgZnJlc2hDb250ZXh0Lm5ld1BhZ2UoKTtcclxuICAgIGF3YWl0IGZyZXNoLmdvdG8oYC9zdHVkaW8vc2ltdWxhdGlvbj9wcm9qZWN0PSR7cHJvamVjdH1gKTtcclxuICAgIGNvbnN0IGZyZXNoUnVubmVyID0gZnJlc2gubG9jYXRvcignLm1vZGVsLXNpbXVsYXRpb24tcnVubmVyJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZnJlc2hSdW5uZXIpLnRvSGF2ZUF0dHJpYnV0ZSgnZGF0YS1qb2ItaWQnLCBhcnRpZmFjdHMuam9iKTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaFJ1bm5lcikudG9IYXZlQXR0cmlidXRlKCdkYXRhLXNuYXBzaG90LWlkJywgYXJ0aWZhY3RzLnNuYXBzaG90KTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaC5nZXRCeVJvbGUoJ2hlYWRpbmcnLCB7IG5hbWU6ICdTaW11bGF0aW9uIGFiZ2VzY2hsb3NzZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKTtcclxuICAgIGF3YWl0IGZyZXNoLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnUmVzZXQnLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZnJlc2guZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBbnNpY2h0IHp1csO8Y2tzZXR6ZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGZyZXNoUnVubmVyKS5ub3QudG9IYXZlQXR0cmlidXRlKCdkYXRhLWpvYi1pZCcpO1xyXG4gICAgYXdhaXQgZnJlc2gucmVsb2FkKCk7XHJcbiAgICBhd2FpdCBleHBlY3QoZnJlc2guZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdTdGFydCcsIGV4YWN0OiB0cnVlIH0pKS50b0JlRW5hYmxlZCgpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGZyZXNoUnVubmVyKS5ub3QudG9IYXZlQXR0cmlidXRlKCdkYXRhLWpvYi1pZCcpO1xyXG4gICAgYXdhaXQgZnJlc2guZ290byhgL3N0dWRpby9yZXN1bHRzP3Byb2plY3Q9JHtwcm9qZWN0fSZzbmFwc2hvdD0ke2FydGlmYWN0cy5zbmFwc2hvdH1gKTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaC5sb2NhdG9yKCcucmVzdWx0LXJ1bi1saXN0IGJ1dHRvbi5hY3RpdmUnKSkudG9IYXZlQXR0cmlidXRlKCdkYXRhLXNuYXBzaG90LWlkJywgYXJ0aWZhY3RzLnNuYXBzaG90KTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaC5nZXRCeVRleHQoJ0FuZm9yZGVydW5nc2VyZsO8bGx1bmc6IEJlc3RhbmRlbicsIHsgZXhhY3Q6IHRydWUgfSkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ3dpemFyZC1yZXN1bHQtcmVzdG9yYXRpb24nLCB7IGJvZHk6IGF3YWl0IGZyZXNoLnNjcmVlbnNob3QoKSwgY29udGVudFR5cGU6ICdpbWFnZS9wbmcnIH0pO1xyXG4gICAgYXdhaXQgZnJlc2guZ290byhgL3N0dWRpby9yZXN1bHRzP3Byb2plY3Q9JHtwcm9qZWN0fS1vdGhlciZzbmFwc2hvdD0ke2FydGlmYWN0cy5zbmFwc2hvdH1gKTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaC5nZXRCeVRleHQoJ0RpZXNlciBTaW11bGF0aW9uc2xhdWYgaXN0IGluIGRpZXNlbSBQcm9qZWt0IG5pY2h0IHZlcmbDvGdiYXIuJywgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaC5sb2NhdG9yKCcucmVzdWx0LXJ1bi1saXN0IGJ1dHRvbi5hY3RpdmUnKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgfSBmaW5hbGx5IHtcclxuICAgIGF3YWl0IGZyZXNoQ29udGV4dC5jbG9zZSgpO1xyXG4gIH1cclxuICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icykudG9IYXZlTGVuZ3RoKDEpO1xyXG4gIGV4cGVjdChlcnJvcnMpLnRvRXF1YWwoW10pO1xyXG4gIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgLi4uY29udGludWl0eSwgLi4uYXJ0aWZhY3RzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuXHJcbmZvciAoY29uc3QgdGVjaG5vbG9neSBvZiBbJ0kyQycsICdNb2RidXMgUlRVJ10pIHtcclxuICB0ZXN0KGBSYXNwYmVycnkgUGkgJHt0ZWNobm9sb2d5fSBwcm9qZWN0IHJldGFpbnMgbW9kZWwgYW5kIGJsb2NrcyBpbmNvbnNpc3RlbnQgbmF0aXZlIHBhcmFtZXRlcnMgQG5vbmF1dG9tb3RpdmVgLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtZW1iZWRkZWQtJyArIHJhbmRvbVVVSUQoKTtcclxuICAgIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cubG9jYXRvcignI2VuZ2luZWVyaW5nLXByb2plY3QtbmFtZScpLmZpbGwoJ1RlbXBlcmF0dXJyZWdlbHVuZycpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwodGVjaG5vbG9neSA9PT0gJ0kyQydcclxuICAgICAgPyAnMiBBa3RvcmVuIGbDvHIgVmVudGlsZSwgNCBTZW5zb3JlbiBmw7xyIFRlbXBlcmF0dXJlbiwgdW5kIGVpbiBSYXNwYmVycnlQaSdcclxuICAgICAgOiBgMiBBa3RvcmVuIGbDvHIgVmVudGlsZSwgNCBTZW5zb3JlbiBmw7xyIFRlbXBlcmF0dXJlbiwgdW5kIGVpbiBSYXNwYmVycnlQaS4gRW1iZWRkZWQgU3lzdGVtcy4gQWxsZSBHZXLDpHRlIGtvbW11bml6aWVyZW4gw7xiZXIgJHt0ZWNobm9sb2d5fS4gUHLDvGZlIHVuZCBhcmJlaXRlIGJpcyBEYXRhIFNjaWVuY2UgJiBJbnRlbGxpZ2VuY2UuYCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnTmV0emFyY2hpdGVrdHVyJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgncmFkaW8nLCB7IG5hbWU6IC9WYXJpYW50ZSAwLyB9KS5jaGVjaygpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ0dlcsOkdGV1bWZhbmcnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBpZiAodGVjaG5vbG9neSA9PT0gJ0kyQycpIHtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUmFzcGJlcnJ5UGk6IEFuc2NobHVzcycsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdJMkMnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeUxhYmVsKCdUZW1wZXJhdHVyc2Vuc29yMTogQW5zY2hsdXNzJywgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoJycpO1xyXG4gICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICAgIGZvciAoY29uc3QgbmFtZSBvZiBbJ1Jhc3BiZXJyeVBpJywgJ1RlbXBlcmF0dXJzZW5zb3IxJywgJ1RlbXBlcmF0dXJzZW5zb3IyJywgJ1RlbXBlcmF0dXJzZW5zb3IzJywgJ1RlbXBlcmF0dXJzZW5zb3I0JywgJ1ZlbnRpbGFrdG9yMScsICdWZW50aWxha3RvcjInXSkge1xyXG4gICAgICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKGAke25hbWV9OiBBbnNjaGx1c3NgLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignSTJDJyk7XHJcbiAgICAgIH1cclxuICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1NlbnNvciAxOiBNZXNzZ3LDtsOfZScsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdzcGVlZCcpO1xyXG4gICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5TGFiZWwoJ1RlbXBlcmF0dXJzZW5zb3IxOiBBbnNjaGx1c3MnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZSgnSTJDJyk7XHJcbiAgICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdTZW5zb3IgMTogTWVzc2dyw7bDn2UnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbigndGVtcGVyYXR1cmUnKTtcclxuICAgIH1cclxuICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdWZW50aWxha3RvcjE6IFN0ZWxsYmVmZWhsJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ09QRU5fQ0xPU0UnKTtcclxuICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlMYWJlbCgnVmVudGlsYWt0b3IyOiBTdGVsbGJlZmVobCcsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZVZhbHVlKCcnKTtcclxuICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdWZW50aWxha3RvcjI6IFN0ZWxsYmVmZWhsJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ09QRU5fQ0xPU0UnKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGV4cGVjdChjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgdHJ1ZSwgWydSYXNwYmVycnlQaScsICdUZW1wZXJhdHVyc2Vuc29yMScsICdUZW1wZXJhdHVyc2Vuc29yMicsICdUZW1wZXJhdHVyc2Vuc29yMycsICdUZW1wZXJhdHVyc2Vuc29yNCcsICdWZW50aWxha3RvcjEnLCAnVmVudGlsYWt0b3IyJ10sIGZhbHNlLCB1bmRlZmluZWQsIHVuZGVmaW5lZCwgdHJ1ZSkpXHJcbiAgICAgIC5yZWplY3RzLnRvVGhyb3coL1dpemFyZCBCTE9DS0VEIGF0IHBhcmFtZXRlcnM6LipiZXN0w6R0aWd0ZSBBbmdhYmVuLyk7XHJcbiAgICBjb25zdCB3b3JrZmxvdyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93Jyk7XHJcbiAgICBjb25zdCBmaW5kaW5ncyA9IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLmJsb2NraW5nX2ZpbmRpbmdzIGFzIHsgY29kZTogc3RyaW5nIH1bXTtcclxuICAgIGV4cGVjdChmaW5kaW5ncy5tYXAoaXRlbSA9PiBpdGVtLmNvZGUpKS50b0NvbnRhaW4oJ1RFQ0hOT0xPR1lfUEFSQU1FVEVSX0RFUEVOREVOQ1lfTUlTTUFUQ0gnKTtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5zdGF0dXNlcy5wYXJhbWV0ZXJzKS50b0JlKCdJTl9QUk9HUkVTUycpO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LmFydGlmYWN0X2NoZWNrcy5wYXJhbWV0ZXJzLmNvbXBsZXRlKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IHJlcXVpcmVkID0gd29ya2Zsb3cuYXJ0aWZhY3RfY2hlY2tzLnBhcmFtZXRlcnMucmVxdWlyZWQ7XHJcbiAgICBleHBlY3QocmVxdWlyZWQucHJvZmlsZV92YWx1ZXMpLnRvQmUoZmFsc2UpO1xyXG4gICAgY29uc3QgZGV2aWNlU291cmNlID0gdGVjaG5vbG9neSA9PT0gJ0kyQycgPyAnaTJjX2RldmljZV9zb3VyY2UnIDogJ21yX2RldmljZV9zb3VyY2UnO1xyXG4gICAgLy8gVGhlc2Ugc2NlbmFyaW9zIHJlbWFpbiBibG9ja2VkIGJ5IHJlYWwgbmF0aXZlIGRlcGVuZGVuY2llcywgbm90IGJ5IHRoZVxyXG4gICAgLy8gYWJzZW5jZSBvZiBhIHJlYWwgZGV2aWNlIHF1YWxpZmljYXRpb24gb3IgZmFicmljYXRlZCBzb3VyY2UgaWRlbnRpZmllci5cclxuICAgIGV4cGVjdChyZXF1aXJlZCkubm90LnRvSGF2ZVByb3BlcnR5KGRldmljZVNvdXJjZSwgZmFsc2UpO1xyXG4gICAgY29uc3QgbmF0aXZlVGVjaG5vbG9neSA9IHRlY2hub2xvZ3kgPT09ICdJMkMnID8gJ2kyYycgOiAnbW9kYnVzX3J0dSc7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cucGFyYW1ldGVycy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9uc1tuYXRpdmVUZWNobm9sb2d5XS52YWx1ZXMpXHJcbiAgICAgIC5ub3QudG9IYXZlUHJvcGVydHkoZGV2aWNlU291cmNlKTtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5hcnRpZmFjdF9jaGVja3MucGFyYW1ldGVycy5wcm9maWxlX2ZpbmRpbmdzLnNvbWUoKGZpbmRpbmc6IHtjb2RlOiBzdHJpbmd9KSA9PlxyXG4gICAgICBmaW5kaW5nLmNvZGUgPT09ICdURUNITk9MT0dZX1BBUkFNRVRFUl9ERVBFTkRFTkNZX01JU01BVENIJykpLnRvQmUodHJ1ZSk7XHJcbiAgICBjb25zdCBldmlkZW5jZVJldmlldyA9IGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHtuYW1lOiAnQmxvY2tpZXJlbmRlIFByZWZsaWdodC1CZWZ1bmRlJ30pO1xyXG4gICAgYXdhaXQgZXhwZWN0KGV2aWRlbmNlUmV2aWV3KS50b0NvbnRhaW5UZXh0KHRlY2hub2xvZ3kgPT09ICdJMkMnID8gJ2kyY19wdWxsdXBfb2htcycgOiAnbXJfcGR1X2J5dGVzJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZXZpZGVuY2VSZXZpZXcuZ2V0QnlSb2xlKCdsaW5rJywge25hbWU6ICdCZXRyb2ZmZW5lIEFuZ2FiZW4gYmVhcmJlaXRlbid9KS5maXJzdCgpKVxyXG4gICAgICAudG9IYXZlQXR0cmlidXRlKCdocmVmJywgbmV3IFJlZ0V4cChgbW9kZT1wYXJhbWV0ZXJzLipwcm9qZWN0PSR7cHJvamVjdH1gKSk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuc3RhdHVzZXMuc2ltdWxhdGlvbikudG9CZSgnRU1QVFknKTtcclxuICAgIGlmICh0ZWNobm9sb2d5ID09PSAnSTJDJykge1xyXG4gICAgICBleHBlY3Qod29ya2Zsb3cucGFyYW1ldGVycy5yYXRlX3Jldmlld19wcm9wb3NhbHMuaTJjLnN0YXR1cykudG9CZSgnUkVWSUVXX1JFUVVJUkVEJyk7XHJcbiAgICAgIGV4cGVjdCh3b3JrZmxvdy5wYXJhbWV0ZXJzLnBhcmFtZXRlcl9wcm92ZW5hbmNlLmJpdHJhdGUuc291cmNlKS50b0JlKCdURUNITk9MT0dZX1BST0ZJTEVfUkVWSUVXX1BST1BPU0FMJyk7XHJcbiAgICB9XHJcbiAgICBjb25zdCBpbnRlcmZhY2VzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtaW50ZXJmYWNlcycpO1xyXG4gICAgZXhwZWN0KGludGVyZmFjZXMubGVuZ3RoKS50b0JlR3JlYXRlclRoYW5PckVxdWFsKDcpO1xyXG4gICAgZXhwZWN0KGludGVyZmFjZXMuZXZlcnkoaXRlbSA9PiAhL2F1dG9tb3RpdmV8Y2FufGxpbi9pLnRlc3QoaXRlbS50ZWNobm9sb2d5KSkpLnRvQmUodHJ1ZSk7XHJcbiAgICBjb25zdCBoYXJkd2FyZSA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgICBleHBlY3QoaGFyZHdhcmUuZXZlcnkoaXRlbSA9PiBpdGVtLmRvbWFpbiAhPT0gJ2F1dG9tb3RpdmUnKSkudG9CZSh0cnVlKTtcclxuICAgIGlmICh0ZWNobm9sb2d5ID09PSAnSTJDJykge1xyXG4gICAgICBjb25zdCBzaWduYWxzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnc2lnbmFscycpO1xyXG4gICAgICBleHBlY3Qoc2lnbmFscy5zb21lKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnVGVtcGVyYXR1cl9UZW1wZXJhdHVyc2Vuc29yMScgJiYgaXRlbS51bml0ID09PSAnZGVnQycpKS50b0JlKHRydWUpO1xyXG4gICAgfVxyXG4gICAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzKS50b0hhdmVMZW5ndGgoMCk7XHJcbiAgICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ25vbmF1dG9tb3RpdmUtZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgdGVjaG5vbG9neSwgZmluZGluZ3MgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgfSk7XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHN0YXJ0Q2FwdHVyZWRMYXJnZVdpemFyZChwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcpIHtcclxuICBjb25zdCBydW5JZCA9IHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBvcmlnaW5hbCA9IGF3YWl0IHJlYWRGaWxlKG5ldyBVUkwoJy4vZml4dHVyZXMvd2l6YXJkLWxhcmdlLTUwLTI1MC0yNTAudHh0JywgaW1wb3J0Lm1ldGEudXJsKSwgJ3V0ZjgnKTtcclxuICBjb25zdCBtZXRhZGF0YSA9IEpTT04ucGFyc2UoYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2UtNTAtMjUwLTI1MC5qc29uJywgaW1wb3J0Lm1ldGEudXJsKSwgJ3V0ZjgnKSk7XHJcbiAgY29uc3QgYmFzZWxpbmUgPSBKU09OLnBhcnNlKGF3YWl0IHJlYWRGaWxlKG5ldyBVUkwoJy4vZml4dHVyZXMvd2l6YXJkLWxhcmdlLXNpZ25hbC1jb250cmFjdHMuanNvbicsIGltcG9ydC5tZXRhLnVybCksICd1dGY4JykpO1xyXG4gIGNvbnN0IHByb21wdCA9IG9yaWdpbmFsLnJlcGxhY2UoL14tIExhdWYtSUQ6LiokL20sICctIExhdWYtSUQ6ICcgKyBydW5JZCk7XHJcbiAgYXdhaXQgcmV2aWV3VmlydHVhbFRyYW5zcG9ydHMocGFnZSwgcHJvamVjdCwgdHJ1ZSk7XG4gIC8vIFJlcGxheSB0aGUgY2FwdHVyZWQsIGFscmVhZHkgY29uZmlybWVkIGlucHV0IHRocm91Z2ggdGhlIG5vcm1hbCBTVEFSVCBBUEkuXHJcbiAgLy8gQWxsIHByb3Bvc2FsIGluc3BlY3Rpb24sIGFwcHJvdmFsLCBjb250aW51YXRpb24gYW5kIHJlbG9hZHMgYmVsb3cgdXNlIFVJLlxyXG4gIGNvbnN0IHN0YXJ0ZWQgPSBhd2FpdCBwYWdlLnJlcXVlc3QucG9zdCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jaGF0Jywge1xyXG4gICAgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiAyNDBfMDAwLFxyXG4gICAgZGF0YTogeyBwcm9tcHQsIHdpemFyZF9jb21tYW5kOiB7IGFjdGlvbjogJ1NUQVJUJywgcnVuX2lkOiBydW5JZCwgb3BlcmF0aW9uX2lkOiByYW5kb21VVUlEKCksXHJcbiAgICAgIHRhcmdldDogJ2RhdGFfc2NpZW5jZV9pbnRlbGxpZ2VuY2UnLCB3aXphcmRfY29udGV4dDogeyAuLi5tZXRhZGF0YS53aXphcmRfY29udGV4dCwgcHJvamVjdF9pZDogcHJvamVjdCwgcnVuX2lkOiBydW5JZCB9IH0gfSxcclxuICB9KTtcclxuICBpZiAoIXN0YXJ0ZWQub2soKSkgdGhyb3cgbmV3IEVycm9yKGBIVFRQICR7c3RhcnRlZC5zdGF0dXMoKX06ICR7KGF3YWl0IHN0YXJ0ZWQudGV4dCgpKS5zbGljZSgwLCA0MDAwKX1gKTtcclxuICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIHJldHVybiB7IHJ1bklkLCBtZXRhZGF0YSwgYmFzZWxpbmUgfTtcclxufVxyXG5cclxuZnVuY3Rpb24gbGFyZ2VQYXJhbWV0ZXJTY2VuYXJpb3MoKTogUGFyYW1ldGVyUmV0dXJuU2NlbmFyaW9bXSB7XHJcbiAgcmV0dXJuIFtcclxuICAgIHt0ZWNobm9sb2d5OiAnbGluJywgZmllbGRzOiB7bGluX2JpdHJhdGVfYnBzOiAnMTksMiBrYml0L3MnfSwgbmF0aXZlOiB7bGluX2JpdHJhdGVfYnBzOiAxOV8yMDB9fSxcclxuICAgIHt0ZWNobm9sb2d5OiAnY2FuX2ZkJywgZmllbGRzOiB7YXJiaXRyYXRpb25fYml0cmF0ZTogJzUwMCBrYml0L3MnLCBkYXRhX2JpdHJhdGU6ICcyIE1iaXQvcyd9LFxyXG4gICAgICBuYXRpdmU6IHthcmJpdHJhdGlvbl9iaXRyYXRlOiA1MDBfMDAwLCBkYXRhX2JpdHJhdGU6IDJfMDAwXzAwMH19LFxyXG4gICAgLy8gTWF0Y2ggdGhlIHVuY2hhbmdlZCBjYXB0dXJlZCAxMDAtTWJpdC9zIHJlcXVlc3QgYW5kIGdlbnVpbmVseSBjaGFuZ2VcclxuICAgIC8vIHRoZSAxLUdiaXQvcyBwcm9maWxlIHNlZWQsIHNvIHNhdmluZyBleGVyY2lzZXMgdXNlci12YWx1ZSBwcm92ZW5hbmNlLlxyXG4gICAge3RlY2hub2xvZ3k6ICdldGhlcm5ldCcsIGZpZWxkczoge2JpdHJhdGU6ICcxMDAgTWJpdC9zJ30sIG5hdGl2ZToge2JpdHJhdGU6IDEwMF8wMDBfMDAwfSwgZWRpdEZpZWxkczogWydiaXRyYXRlJ119LFxyXG4gIF07XHJcbn1cclxuXHJcbnRlc3QoJ2V4YWN0IGNvbmZpcm1lZCA1MC8yNTAvMjUwIHJlcXVlc3QgY29tcGxldGVzIHRocm91Z2ggcmVhbCB3aXphcmQgcmV2aWV3IEBsYXJnZScsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICBjb25zdCBlcnJvcnM6IHN0cmluZ1tdID0gW107IHBhZ2Uub24oJ3BhZ2VlcnJvcicsIGVycm9yID0+IGVycm9ycy5wdXNoKGVycm9yLm1lc3NhZ2UpKTtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtbGFyZ2UtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCB7IHJ1bklkLCBtZXRhZGF0YSwgYmFzZWxpbmUgfSA9IGF3YWl0IHN0YXJ0Q2FwdHVyZWRMYXJnZVdpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBjb25zdCBwYXJhbWV0ZXJSZXR1cm5SZXZpZXdzOiBzdHJpbmdbXSA9IFtdO1xuICBjb25zdCBjb250aW51aXR5ID0gYXdhaXQgY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIGZhbHNlLCBbXSwgdHJ1ZSwgYmFzZWxpbmUuc2lnbmFscyxcbiAgICB1bmRlZmluZWQsIGZhbHNlLCBhc3luYyAocHJvcG9zYWxJZCwgcHJvcG9zYWxUeXBlKSA9PiB7XG4gICAgICBpZiAoIVsnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJywgJ1dJWkFSRF9ST1VUSU5HJywgJ1dJWkFSRF9ORVRXT1JLX1RPUE9MT0dZJ10uaW5jbHVkZXMocHJvcG9zYWxUeXBlKSkgcmV0dXJuO1xuICAgICAgLy8gT25lIGZ1bGwgdGhyZWUtYnVzIGN5Y2xlIHJlbWFpbnMgaW50ZWdyYXRlZCBhdCBldmVyeSByZXZpZXcgc3RhZ2UuXHJcbiAgICAgIC8vIFJlcGVhdGVkIHRocmVlLXNlZWQgY292ZXJhZ2UgaGFzIGl0cyBvd24gcmVhbCBsYXJnZSBjYXNlcyBiZWxvdyxcclxuICAgICAgLy8gcHJlc2VydmluZyB0aGUgY29udHJhY3R1YWwgMjAtbWludXRlIHdob2xlLXdvcmtmbG93IGNhc2UgbGltaXQuXHJcbiAgICAgIC8vIEVhY2ggcGhhc2UgbXVzdCByZWFsbHkgZWRpdCB0aGUgc2VlZDogYW4gaWRlbnRpY2FsIHNhdmUgY29ycmVjdGx5XHJcbiAgICAgIC8vIGxlYXZlcyB0aGUgZXhpc3RpbmcgcHJvcG9zYWwgVkFMSURBVEVEIGluc3RlYWQgb2YgbWFraW5nIGl0IE9VVERBVEVELlxyXG4gICAgICBjb25zdCByZXZpZXdTZWVkID0gcHJvcG9zYWxUeXBlID09PSAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJyA/IDQxXHJcbiAgICAgICAgOiBwcm9wb3NhbFR5cGUgPT09ICdXSVpBUkRfUk9VVElORycgPyA0MyA6IDQyO1xyXG4gICAgICBhd2FpdCByZXBlYXRQYXJhbWV0ZXJSZXR1cm4ocGFnZSwgcHJvamVjdCwgcHJvcG9zYWxJZCwgbGFyZ2VQYXJhbWV0ZXJTY2VuYXJpb3MoKSwgW3Jldmlld1NlZWRdKTtcclxuICAgICAgcGFyYW1ldGVyUmV0dXJuUmV2aWV3cy5wdXNoKHByb3Bvc2FsVHlwZSk7XG4gICAgfSk7XG4gIGV4cGVjdChwYXJhbWV0ZXJSZXR1cm5SZXZpZXdzKS50b0VxdWFsKFsnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJywgJ1dJWkFSRF9ST1VUSU5HJywgJ1dJWkFSRF9ORVRXT1JLX1RPUE9MT0dZJ10pO1xuICBleHBlY3QoY29udGludWl0eS5ydW5JZCkudG9CZShydW5JZCk7XHJcbiAgY29uc3QgaGFyZHdhcmUgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gIGV4cGVjdChoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLmRldmljZV90eXBlID09PSAnU2Vuc29yQ29udHJvbGxlcicpKS50b0hhdmVMZW5ndGgoMjUwKTtcclxuICBleHBlY3QoaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5kZXZpY2VfdHlwZSA9PT0gJ0FjdHVhdG9yQ29udHJvbGxlcicpKS50b0hhdmVMZW5ndGgoMjUwKTtcclxuICBleHBlY3QoaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5kZXZpY2VfdHlwZSA9PT0gJ0VDVScpLmxlbmd0aCkudG9CZUdyZWF0ZXJUaGFuT3JFcXVhbCg1MCk7XHJcbiAgY29uc3QgYXJ0aWZhY3RzID0gYXdhaXQgdmVyaWZ5QXJ0aWZhY3RzKHBhZ2UsIHByb2plY3QsIDE0MDQsIHVuZGVmaW5lZCwgdW5kZWZpbmVkLCB7XG4gICAgbGluOiB7Yml0cmF0ZTogMTlfMjAwfSwgY2FuX2ZkOiB7YXJiaXRyYXRpb25fYml0cmF0ZTogNTAwXzAwMCwgZGF0YV9iaXRyYXRlOiAyXzAwMF8wMDB9LFxuICAgIGV0aGVybmV0OiB7Yml0cmF0ZTogMTAwXzAwMF8wMDB9LFxyXG4gIH0pO1xuICBjb25zdCBleGNsdWRlZFNpZ25hbElkcyA9IG5ldyBTZXQoYXJ0aWZhY3RzLmFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UudHJhbnNwb3J0X2V4Y2x1c2lvbnNcclxuICAgIC5mbGF0TWFwKChpdGVtOiB7IHNpZ25hbF9pZHM6IHN0cmluZ1tdIH0pID0+IGl0ZW0uc2lnbmFsX2lkcykpO1xyXG4gIGV4cGVjdChleGNsdWRlZFNpZ25hbElkcy5zaXplKS50b0JlKDIzNSk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50Lm9ic2VydmVkX3NpZ25hbF9jb3VudCkudG9CZSgxMTY5KTtcclxuICBhd2FpdCB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZSwgcHJvamVjdCwgYmFzZWxpbmUuc2lnbmFscyk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5qb2IpLnRvQmUoY29udGludWl0eS5yZXN0YXJ0ZWRKb2JJZCk7XHJcbiAgZXhwZWN0KGVycm9ycykudG9FcXVhbChbXSk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCBmaXh0dXJlOiBtZXRhZGF0YS5yZXF1ZXN0X3NoYTI1NiwgLi4uY29udGludWl0eSwgLi4uYXJ0aWZhY3RzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuXHJcbmZvciAoY29uc3QgdGFyZ2V0IG9mIFtcclxuICB7IGxhYmVsOiAnbW9kZWwnLCB0eXBlOiAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJywgc3RlcDogJ2VuZ2luZWVyaW5nX21vZGVsJyB9LFxyXG4gIHsgbGFiZWw6ICdyb3V0aW5nJywgdHlwZTogJ1dJWkFSRF9ST1VUSU5HJywgc3RlcDogJ3JvdXRpbmcnIH0sXHJcbiAgeyBsYWJlbDogJ3RvcG9sb2d5JywgdHlwZTogJ1dJWkFSRF9ORVRXT1JLX1RPUE9MT0dZJywgc3RlcDogJ25ldHdvcmtfZWRpdG9yJyB9LFxyXG5dKSB7XHJcbiAgdGVzdChgZXhhY3QgY29uZmlybWVkIDUwLzI1MC8yNTAgJHt0YXJnZXQubGFiZWx9IHBhcmFtZXRlciByZXR1cm4gcmV2aWV3IG9ubHkgQGxhcmdlLXJldHVybmAsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICAgIGNvbnN0IGVycm9yczogc3RyaW5nW10gPSBbXTsgcGFnZS5vbigncGFnZWVycm9yJywgZXJyb3IgPT4gZXJyb3JzLnB1c2goZXJyb3IubWVzc2FnZSkpO1xyXG4gICAgY29uc3QgcHJvamVjdCA9IGBuaXMtZTJlLWxhcmdlLXJldHVybi0ke3RhcmdldC5sYWJlbH0tYCArIHJhbmRvbVVVSUQoKTtcclxuICAgIGNvbnN0IHsgcnVuSWQsIG1ldGFkYXRhLCBiYXNlbGluZSB9ID0gYXdhaXQgc3RhcnRDYXB0dXJlZExhcmdlV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCBmYWxzZSwgW10sIGZhbHNlLCBiYXNlbGluZS5zaWduYWxzLFxyXG4gICAgICB1bmRlZmluZWQsIGZhbHNlLCBhc3luYyAocHJvcG9zYWxJZCwgcHJvcG9zYWxUeXBlKSA9PiB7XHJcbiAgICAgICAgaWYgKHByb3Bvc2FsVHlwZSAhPT0gdGFyZ2V0LnR5cGUpIHJldHVybjtcclxuICAgICAgICBhd2FpdCByZXBlYXRQYXJhbWV0ZXJSZXR1cm4ocGFnZSwgcHJvamVjdCwgcHJvcG9zYWxJZCwgbGFyZ2VQYXJhbWV0ZXJTY2VuYXJpb3MoKSk7XHJcbiAgICAgICAgcmV0dXJuICdTVE9QX0FGVEVSX1JFVklFVyc7XHJcbiAgICAgIH0pO1xyXG4gICAgZXhwZWN0KGNvbnRpbnVpdHkucnVuSWQpLnRvQmUocnVuSWQpO1xyXG4gICAgZXhwZWN0KGNvbnRpbnVpdHkucmV2aWV3T25seT8ucHJvcG9zYWxUeXBlKS50b0JlKHRhcmdldC50eXBlKTtcclxuICAgIGNvbnN0IHdvcmtmbG93ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24pLnRvTWF0Y2hPYmplY3QoeyBydW5faWQ6IHJ1bklkLCBzdGF0ZTogJ1JFVklFV19SRVFVSVJFRCcsIHN0ZXA6IHRhcmdldC5zdGVwIH0pO1xyXG4gICAgZXhwZWN0KGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzLnNpbXVsYXRpb24pKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IHByb3Bvc2FsID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7Y29udGludWl0eS5yZXZpZXdPbmx5IS5wcm9wb3NhbElkfT92aWV3PXN0YXR1c2ApO1xyXG4gICAgZXhwZWN0KHByb3Bvc2FsLmRhdGEuc3RhdHVzKS50b0JlKCdWQUxJREFURUQnKTtcclxuICAgIGV4cGVjdChlcnJvcnMpLnRvRXF1YWwoW10pO1xyXG4gICAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdyZXZpZXctb25seS1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCBmaXh0dXJlOiBtZXRhZGF0YS5yZXF1ZXN0X3NoYTI1NixcclxuICAgICAgY292ZXJhZ2U6ICdSRVZJRVdfQ09OVElOVUlUWV9PTkxZJywgY3ljbGVzOiAzLCB0ZWNobm9sb2dpZXM6IFsnbGluJywgJ2Nhbl9mZCcsICdldGhlcm5ldCddLCAuLi5jb250aW51aXR5IH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gIH0pO1xyXG59XHJcblxyXG50ZXN0KCdhIHJlYWwgQU1FTkQgYWZ0ZXIgbW9kZWwgYXBwcm92YWwgYWRkcyB0aGUgcmVxdWVzdGVkIHNlbnNvciBhbmQgcmV1c2VzIGl0cyBuZXR3b3JrcyBAYW1lbmQnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWFtZW5kLScgKyByYW5kb21VVUlEKCk7XHJcbiAgYXdhaXQgcmV2aWV3VmlydHVhbFRyYW5zcG9ydHMocGFnZSwgcHJvamVjdCk7XHJcbiAgY29uc3QgcnVuSWQgPSByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgZ3JhcGggPSBbXHJcbiAgICB7IGNsdXN0ZXJfaWQ6ICdkcml2ZScsIG5ldHdvcmtfaWQ6ICdjYW5fZmQnLCBuZXR3b3JrX2xhYmVsOiAnQ0FOLUZEJywgYnVzX25hbWU6ICdEcml2ZScsXHJcbiAgICAgIGNvbnRyb2xsZXJzOiBbeyBlY3U6ICdNb3RvcnN0ZXVlcnVuZycsIHNlbnNvcnM6IFtdIGFzIHN0cmluZ1tdLCBhY3R1YXRvcnM6IFtdIH1dLFxyXG4gICAgICBobWlfcm91dGVzOiBbeyBzb3VyY2U6ICdNb3RvcnN0ZXVlcnVuZycsIHRhcmdldDogJ0FuemVpZ2UnIH0sIHsgc291cmNlOiAnQW56ZWlnZScsIHRhcmdldDogJ01vdG9yc3RldWVydW5nJyB9LFxyXG4gICAgICAgIHsgc291cmNlOiAnU3lzdGVtJywgdGFyZ2V0OiAnQW56ZWlnZScgfV0gfSxcclxuICAgIHsgY2x1c3Rlcl9pZDogJ2Rpc3BsYXknLCBuZXR3b3JrX2lkOiAnZXRoZXJuZXQnLCBuZXR3b3JrX2xhYmVsOiAnRXRoZXJuZXQnLCBidXNfbmFtZTogJ0Rpc3BsYXknLFxyXG4gICAgICBjb250cm9sbGVyczogW3sgZWN1OiAnQW56ZWlnZScsIHNlbnNvcnM6IFtdIGFzIHN0cmluZ1tdLCBhY3R1YXRvcnM6IFtdIH1dIH0sXHJcbiAgXTtcclxuICBjb25zdCBwcm9tcHQgPSBgU3RydWt0dXJpZXJ0ZSBWb3JnYWJlbiBmdWVyIGRlbiBFbmdpbmVlcmluZy1BZ2VudGVuOlxyXG4tIExhdWYtSUQ6ICR7cnVuSWR9XHJcbi0gSW5kdXN0cmllOiBBdXRvbW90aXZlXHJcbi0gTmV0endlcmt0ZWNobm9sb2dpZW46IENBTi1GRCAoY2FuX2ZkKTsgRXRoZXJuZXQgKGV0aGVybmV0KVxyXG5DQU4tRkQ6IDUwMCBrYml0L3MgYXJiaXRyYXRpb24sIDIgTWJpdC9zIGRhdGFcclxuQ0FOOiA1MDAga2JpdC9zXHJcbkV0aGVybmV0OiAxMDAgTWJpdC9zXHJcbi0gSGFyZHdhcmUtU29sbHdlcnRlOiB7XCJnYXRld2F5c1wiOjEsXCJlY3VzXCI6MixcInNlbnNvcnNcIjowLFwiYWN0dWF0b3JzXCI6MH1cclxuLSBTeXN0ZW1jbHVzdGVyLUdyYXBoOiAke0pTT04uc3RyaW5naWZ5KGdyYXBoKX1cclxuS29ua3JldGUgQXVmZ2FiZSBkZXMgTnV0emVycywgcGVyIFdpemFyZC1VZWJlcm5laG1lbiBiZXN0YWV0aWd0OlxyXG5Nb3RvcnN0ZXVlcnVuZyB1bmQgQW56ZWlnZSBtaXQgZWluZW0gemVudHJhbGVuIEdhdGV3YXkgU3lzdGVtIHZlcmJpbmRlbi5gO1xyXG4gIGNvbnN0IHN0YXJ0ZWQgPSBhd2FpdCBwYWdlLnJlcXVlc3QucG9zdCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jaGF0Jywge1xyXG4gICAgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiAxMjBfMDAwLFxyXG4gICAgZGF0YTogeyBwcm9tcHQsIHdpemFyZF9jb21tYW5kOiB7IGFjdGlvbjogJ1NUQVJUJywgcnVuX2lkOiBydW5JZCwgb3BlcmF0aW9uX2lkOiByYW5kb21VVUlEKCksXHJcbiAgICAgIHRhcmdldDogJ2RhdGFfc2NpZW5jZV9pbnRlbGxpZ2VuY2UnLCB3aXphcmRfY29udGV4dDogeyBwcm9qZWN0X2lkOiBwcm9qZWN0LCBydW5faWQ6IHJ1bklkLFxyXG4gICAgICAgIHByb2plY3RfbmFtZTogJ0UyRSBhbWVuZG1lbnQnLCBzY29wZV9pZHM6IHN0ZXBzLCBtb2RlOiAnZnVsbCcsXHJcbiAgICAgICAgcHJvY2Vzc19pZHM6IFsnZGVmYXVsdHMnLCAncmV2aWV3X2dhdGUnLCAnYXBwcm92ZV9hZnRlcl9hbGxvdyddLCB0YXNrOiAnTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UgYW4gU3lzdGVtJyB9IH0gfSxcclxuICB9KTtcclxuICBpZiAoIXN0YXJ0ZWQub2soKSkgdGhyb3cgbmV3IEVycm9yKGBIVFRQICR7c3RhcnRlZC5zdGF0dXMoKX06ICR7KGF3YWl0IHN0YXJ0ZWQudGV4dCgpKS5zbGljZSgwLCA0MDAwKX1gKTtcclxuICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGxldCBvcmlnaW5hbE5ldHdvcmtzOiBzdHJpbmdbXSA9IFtdO1xyXG4gIGNvbnN0IGFtZW5kID0gYXN5bmMgKCkgPT4ge1xyXG4gICAgb3JpZ2luYWxOZXR3b3JrcyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpKS5wYXJhbWV0ZXJzLm5ldHdvcmtzXHJcbiAgICAgIC5tYXAoKGl0ZW06IHsgaWQ6IHN0cmluZyB9KSA9PiBpdGVtLmlkKS5zb3J0KCk7XHJcbiAgICBleHBlY3Qob3JpZ2luYWxOZXR3b3JrcykudG9IYXZlTGVuZ3RoKDIpO1xyXG4gICAgZ3JhcGhbMF0uY29udHJvbGxlcnNbMF0uc2Vuc29ycy5wdXNoKCdNb3RvclRlbXBlcmF0dXJlJyk7XHJcbiAgICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pO1xyXG4gICAgY29uc3QgZXhwYW5kID0gZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgICBhd2FpdCBleHBlY3QoZXhwYW5kKS50b0JlRW5hYmxlZCh7IHRpbWVvdXQ6IDEyMF8wMDAgfSk7XHJcbiAgICBhd2FpdCBleHBhbmQuY2xpY2soKTtcclxuICAgIGNvbnN0IGZpZWxkID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcmfDpG56ZW4nLCBleGFjdDogdHJ1ZSB9KS5nZXRCeVJvbGUoJ3RleHRib3gnKTtcclxuICAgIGF3YWl0IGZpZWxkLmZpbGwoJ0VyZ8OkbnplIE1vdG9yVGVtcGVyYXR1cmUgYWxzIFNlbnNvciBkZXIgTW90b3JzdGV1ZXJ1bmcuIERpZSB2b2xsc3TDpG5kaWdlIGFrdHVhbGlzaWVydGUgRnJlaWdhYmUgbGF1dGV0OlxcbidcclxuICAgICAgKyAnLSBIYXJkd2FyZS1Tb2xsd2VydGU6IHtcImdhdGV3YXlzXCI6MSxcImVjdXNcIjoyLFwic2Vuc29yc1wiOjEsXCJhY3R1YXRvcnNcIjowfVxcbidcclxuICAgICAgKyAnLSBTeXN0ZW1jbHVzdGVyLUdyYXBoOiAnICsgSlNPTi5zdHJpbmdpZnkoZ3JhcGgpKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8Okbnp1bmcgYW5hbHlzaWVyZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGZpZWxkKS5ub3QudG9CZVZpc2libGUoeyB0aW1lb3V0OiAxMjBfMDAwIH0pO1xyXG4gIH07XHJcbiAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCBmYWxzZSwgWydNb3RvcnN0ZXVlcnVuZycsICdBbnplaWdlJ10sIGZhbHNlLCB1bmRlZmluZWQsIGFtZW5kKTtcclxuICBjb25zdCBoYXJkd2FyZSA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgY29uc3Qgb3duZXIgPSBoYXJkd2FyZS5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnTW90b3JzdGV1ZXJ1bmcnKTtcclxuICBjb25zdCBzZW5zb3JzID0gaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnTW90b3JUZW1wZXJhdHVyZScpO1xyXG4gIGV4cGVjdChzZW5zb3JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KHNlbnNvcnNbMF0uaWRlbnRpdHkuc3lzdGVtX293bmVyX2lkKS50b0JlKG93bmVyLmlkKTtcclxuICBjb25zdCBzZW5zb3JOZXR3b3JrID0gJ0RyaXZlLUlPLW1vdG9yc3RldWVydW5nLWNhbi1mZC1TMDEnO1xyXG4gIGNvbnN0IG5ldHdvcmtzID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93JykpLnBhcmFtZXRlcnMubmV0d29ya3M7XHJcbiAgZXhwZWN0KG5ldHdvcmtzLm1hcCgoaXRlbTogeyBpZDogc3RyaW5nIH0pID0+IGl0ZW0uaWQpLnNvcnQoKSkudG9FcXVhbChbLi4ub3JpZ2luYWxOZXR3b3Jrcywgc2Vuc29yTmV0d29ya10uc29ydCgpKTtcclxuICBleHBlY3QobmV3IFNldChuZXR3b3Jrcy5tYXAoKGl0ZW06IHsgbmFtZTogc3RyaW5nIH0pID0+IGl0ZW0ubmFtZSkpLnNpemUpLnRvQmUobmV0d29ya3MubGVuZ3RoKTtcclxuICBjb25zdCB0b3BvbG9neSA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9uZXR3b3JrLXZpZXcnKSkudG9wb2xvZ3k7XHJcbiAgY29uc3QgbG9jYWxFZGdlID0gdG9wb2xvZ3kuZWRnZXMuZmluZCgoZWRnZTogYW55KSA9PiBlZGdlLnBoeXNpY2FsTmV0d29ya0lkID09PSBzZW5zb3JOZXR3b3JrKTtcclxuICBleHBlY3QobG9jYWxFZGdlKS50b0JlVHJ1dGh5KCk7XHJcbiAgZXhwZWN0KGxvY2FsRWRnZS5idXMpLnRvQmUoJ2Nhbl9mZCcpO1xyXG4gIGV4cGVjdChPYmplY3QudmFsdWVzKGxvY2FsRWRnZS5yb3V0aW5nTWV0YWRhdGEpKS50b0NvbnRhaW5FcXVhbChleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7XHJcbiAgICBzb3VyY2U6IHNlbnNvcnNbMF0uaWQsIHRhcmdldDogb3duZXIuaWQsIGFwcHJvdmFsU3RhdGU6ICdBUFBST1ZFRCcsIHByb3RvY29sOiAnQ0FOX0ZEJyxcclxuICB9KSk7XHJcbiAgZm9yIChjb25zdCBbc2lkZSwgaGFyZHdhcmVJZF0gb2YgW1snc291cmNlJywgc2Vuc29yc1swXS5pZF0sIFsndGFyZ2V0Jywgb3duZXIuaWRdXSkge1xyXG4gICAgY29uc3Qgbm9kZSA9IHRvcG9sb2d5Lm5vZGVzLmZpbmQoKGl0ZW06IGFueSkgPT4gaXRlbS5pZCA9PT0gbG9jYWxFZGdlW3NpZGVdKTtcclxuICAgIGV4cGVjdChub2RlLmVuZ2luZWVyaW5nSWQpLnRvQmUoaGFyZHdhcmVJZCk7XHJcbiAgICBleHBlY3Qobm9kZS5wb3J0cykudG9Db250YWluRXF1YWwoZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoeyBpZDogbG9jYWxFZGdlW3NpZGUgKyAnUG9ydCddLFxyXG4gICAgICBidXM6ICdjYW5fZmQnLCBwaHlzaWNhbE5ldHdvcmtJZDogc2Vuc29yTmV0d29yayB9KSk7XHJcbiAgfVxyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCAxKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2FtZW5kbWVudC1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCAuLi5jb250aW51aXR5LCAuLi5hcnRpZmFjdHMgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG5cclxuLy8gUmVhbCBpc29sYXRlZCBVSSAtPiBwZXJzaXN0ZWQgbW9kZWwgYm91bmRhcnkgcmVncmVzc2lvbiwgbm90IG5pbmUtc3RhZ2UgY29tcGxldGlvbiBwcm9vZi5cclxudGVzdCgncmV2aWV3YWJsZSBmdW5jdGlvbmFsIFRYL1JYIE9GRiBzdXJ2aXZlcyByZXF1ZXN0IHJlbG9hZCBhbmQgY2Fub25pY2FsIG1vZGVsIGFkb3B0aW9uIEB0eHJ4JywgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS10eHJ4LScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdUWCBSWCBmdW5jdGlvbmFsIHBhcnRuZXJzJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwoJ0VyemV1Z2UgZWluIEF1dG9tb3RpdmUgQ0FOLUZEIE5ldHp3ZXJrIG1pdCBlaW5lbSBHYXRld2F5IFN5c3RlbSB1bmQgZGVuIEVDVXMgTW90b3JzdGV1ZXJ1bmcsIEdldHJpZWJlc3RldWVydW5nIHVuZCBFbGVrdHJvbW90b3JzdGV1ZXJ1bmcuIERpZSBiZXJlY2huZXRlbiBGdW5rdGlvbnNhdXNnw6RuZ2UgZGllbmVuIGRlciBBbnRyaWVic2tvb3JkaW5hdGlvbi4gQ29udHJvbGxlcnN0YXR1cyBibGVpYnQgaW50ZXJuLlxcbkNBTi1GRDogNTAwIGtiaXQvcyBhcmJpdHJhdGlvbiwgMiBNYml0L3MgZGF0YScpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdHZXLDpHRldW1mYW5nJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1dG9tb3RpdmUgLyBWZWhpY2xlIMO8YmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBmb3IgKGNvbnN0IFtsYWJlbCwgdmFsdWVdIG9mIFtbJ0dhdGV3YXlzJywgJzEnXSwgWydDb250cm9sbGVyJywgJzMnXSwgWydTZW5zb3JlbicsICcwJ10sIFsnQWt0b3JlbicsICcwJ11dKSBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbChgJHtsYWJlbH06IHZlcmJpbmRsaWNoZSBBbnphaGxgLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwodmFsdWUpO1xyXG4gIGNvbnN0IHR4cnggPSBkaWFsb2cubG9jYXRvcignZGV0YWlscycpLmZpbHRlcih7IGhhczogcGFnZS5sb2NhdG9yKCdzdW1tYXJ5JykuZmlsdGVyKHsgaGFzVGV4dDogL15UWFxcL1JYLyB9KSB9KS5maXJzdCgpO1xyXG4gIGF3YWl0IGV4cGVjdCh0eHJ4KS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IHR4cngubG9jYXRvcignc3VtbWFyeScpLmNsaWNrKCk7XHJcbiAgY29uc3Qgc2VsZWN0ZWQgPSB0eHJ4LmdldEJ5Um9sZSgnc3dpdGNoJywgeyBuYW1lOiAnTW90b3JEcmVobW9tZW50SXN0IOKGkiBHZXRyaWViZXN0ZXVlcnVuZycsIGV4YWN0OiB0cnVlIH0pO1xyXG4gIGF3YWl0IGV4cGVjdChzZWxlY3RlZCkudG9CZUNoZWNrZWQoKTsgYXdhaXQgc2VsZWN0ZWQudW5jaGVjaygpO1xyXG4gIGNvbnN0IHN0YXJ0UmVxdWVzdCA9IHBhZ2Uud2FpdEZvclJlcXVlc3QocmVxdWVzdCA9PiByZXF1ZXN0LnVybCgpLmVuZHNXaXRoKCcvYXBpL2FnZW50L2NoYXQnKSAmJiByZXF1ZXN0Lm1ldGhvZCgpID09PSAnUE9TVCcgJiYgcmVxdWVzdC5wb3N0RGF0YUpTT04oKT8ud2l6YXJkX2NvbW1hbmQ/LmFjdGlvbiA9PT0gJ1NUQVJUJyk7XHJcbiAgZm9yIChsZXQgc3RlcCA9IDA7IHN0ZXAgPCAxMDsgc3RlcCsrKSB7XHJcbiAgICBjb25zdCBidXR0b24gPSBkaWFsb2cubG9jYXRvcignLmVuZy1hZ2VudC1xdWVzdGlvbm5haXJlLWhlYWQnKS5nZXRCeVJvbGUoJ2J1dHRvbicpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGJ1dHRvbikudG9CZUVuYWJsZWQoKTsgY29uc3QgbGFiZWwgPSBhd2FpdCBidXR0b24uaW5uZXJUZXh0KCk7IGF3YWl0IGJ1dHRvbi5jbGljaygpO1xyXG4gICAgaWYgKGxhYmVsID09PSAnw5xiZXJuZWhtZW4nIHx8IGxhYmVsID09PSAnQXVmdHJhZyBzdGFydGVuJykgYnJlYWs7XHJcbiAgfVxyXG4gIGNvbnN0IGNvbnRleHQgPSAoYXdhaXQgc3RhcnRSZXF1ZXN0KS5wb3N0RGF0YUpTT04oKS53aXphcmRfY29tbWFuZC53aXphcmRfY29udGV4dDtcclxuICBjb25zdCBzdWJtaXR0ZWQgPSBjb250ZXh0LnN5c3RlbV9jbHVzdGVyX2Fzc2lnbm1lbnRzLmZsYXRNYXAoKGNsdXN0ZXI6IGFueSkgPT4gY2x1c3Rlci5mdW5jdGlvbmFsX3JvdXRlcyA/PyBbXSk7XHJcbiAgY29uc3Qgb2ZmID0gc3VibWl0dGVkLmZpbmQoKHJvdXRlOiBhbnkpID0+IHJvdXRlLnNvdXJjZSA9PT0gJ01vdG9yc3RldWVydW5nJyAmJiByb3V0ZS50YXJnZXQgPT09ICdHZXRyaWViZXN0ZXVlcnVuZycpO1xyXG4gIGV4cGVjdChvZmYuc2lnbmFscykudG9FcXVhbChbXSk7IGV4cGVjdChvZmYuZXhjbHVkZWRfc2lnbmFscykudG9FcXVhbChbJ01vdG9yRHJlaG1vbWVudElzdCddKTtcclxuICBsZXQgcHJvcG9zYWw6IGFueTtcclxuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICBjb25zdCBjb252ZXJzYXRpb24gPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKTtcclxuICAgIGlmICghY29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsKSByZXR1cm4gZmFsc2U7XHJcbiAgICBwcm9wb3NhbCA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtjb252ZXJzYXRpb24uZGF0YS5hY3RpdmVfcHJvcG9zYWx9YCkpLmRhdGE7XHJcbiAgICByZXR1cm4gcHJvcG9zYWwucHJvcG9zYWxfdHlwZSA9PT0gJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCc7XHJcbiAgfSwgeyB0aW1lb3V0OiAxODBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTsgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBjb25zdCBmaW5kaW5ncyA9IHByb3Bvc2FsLnZhbGlkYXRpb25fcmVzdWx0LmZpbmRpbmdzLmZpbHRlcigoaXRlbTogYW55KSA9PiBpdGVtLmNvZGUgPT09ICdDQVBBQ0lUWV9VTlZFUklGSUVEJyk7XHJcbiAgaWYgKGZpbmRpbmdzLmxlbmd0aCkge1xyXG4gICAgY29uc3QgcmV2aWV3ID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ1Byw7xmYmVmdW5kZSBkZXMgVm9yc2NobGFncycgfSk7XHJcbiAgICBhd2FpdCBleHBlY3QocmV2aWV3KS50b0NvbnRhaW5UZXh0KGAke3Byb3Bvc2FsLnZhbGlkYXRpb25fcmVzdWx0LmZpbmRpbmdzLmxlbmd0aH0gUHLDvGZiZWZ1bmRlYCk7XHJcbiAgICBhd2FpdCBleHBlY3QocmV2aWV3LmdldEJ5Um9sZSgnbGluaycsIHsgbmFtZTogJ1RlY2hub2xvZ2llcGFyYW1ldGVyIGJlYXJiZWl0ZW4gdW5kIGJlc3TDpHRpZ2VuJyB9KS5maXJzdCgpKS50b0hhdmVBdHRyaWJ1dGUoJ2hyZWYnLCBuZXcgUmVnRXhwKGBwcm9qZWN0PSR7cHJvamVjdH1gKSk7XHJcbiAgICBhd2FpdCByZXZpZXcubG9jYXRvcignc3VtbWFyeScpLmZpcnN0KCkuY2xpY2soKTsgYXdhaXQgZXhwZWN0KHJldmlldy5nZXRCeVJvbGUoJ25hdmlnYXRpb24nLCB7IG5hbWU6ICdCZWZ1bmRlIGR1cmNoYmzDpHR0ZXJuJyB9KS5maXJzdCgpKS50b0JlVmlzaWJsZSgpO1xyXG4gIH1cclxuICBjb25zdCBhcHBseSA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IHJlc3BvbnNlLnVybCgpLmluY2x1ZGVzKGAvcHJvcG9zYWxzLyR7cHJvcG9zYWwucHJvcG9zYWxfaWR9L2FwcHJvdmUtYXBwbHlgKSAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0ZyZWlnZWJlbiwgw7xiZXJuZWhtZW4gJiBmb3J0ZmFocmVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTsgZXhwZWN0KChhd2FpdCBhcHBseSkub2soKSkudG9CZSh0cnVlKTtcclxuICBjb25zdCBub2RlcyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgY29uc3QgbWVzc2FnZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdtZXNzYWdlcycpOyBjb25zdCBzaWduYWxzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnc2lnbmFscycpO1xyXG4gIGNvbnN0IHNpZ25hbCA9IHNpZ25hbHMuZmluZChpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ01vdG9yRHJlaG1vbWVudElzdCcpOyBleHBlY3Qoc2lnbmFsKS50b0JlVHJ1dGh5KCk7XHJcbiAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzLmZpbmQoaXRlbSA9PiBpdGVtLmlkID09PSBzaWduYWwubWVzc2FnZV9pZCk7XHJcbiAgY29uc3QgZ2VhcmJveCA9IG5vZGVzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdHZXRyaWViZXN0ZXVlcnVuZycpO1xyXG4gIGNvbnN0IGVtb3RvciA9IG5vZGVzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdFbGVrdHJvbW90b3JzdGV1ZXJ1bmcnKTtcclxuICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3Quc2NvcGUpLnRvQmUoJ0ZVTkNUSU9OX09VVFBVVCcpO1xyXG4gIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdC5jb25zdW1lcl9yZWZzKS5ub3QudG9Db250YWluKGdlYXJib3guaWQpO1xyXG4gIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdC5jb25zdW1lcl9yZWZzKS50b0NvbnRhaW4oZW1vdG9yLmlkKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2Z1bmN0aW9uYWwtdHhyeC1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCBvZmYsIG1lc3NhZ2UgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xy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