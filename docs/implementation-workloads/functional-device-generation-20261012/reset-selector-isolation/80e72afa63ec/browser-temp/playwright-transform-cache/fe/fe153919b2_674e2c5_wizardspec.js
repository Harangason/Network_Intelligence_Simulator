// e2118985332c42edb1a195d0bf5e7565afdf7d02
import { test, expect } from 'playwright/test';
import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { WizardProgressWatchdog, WIZARD_STEPS, WIZARD_DONE } from './support/wizard-progress-watchdog';
import { reviewVirtualTransports } from './support/native-transport-fixtures';
const steps = WIZARD_STEPS;
const done = WIZARD_DONE;
async function openSimulationRun(page) {
  const controls = page.locator('[aria-controls="simulation-controls"]');
  if ((await controls.getAttribute('aria-expanded')) === 'false') await controls.click();
  const panel = page.locator('.simulation-command-panel');
  if ((await panel.getAttribute('open')) === null) await panel.locator(':scope > summary').click();
}
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
  // Recover only a peer connection reset on this idempotent read. HTTP errors,
  // malformed data and all continuity assertions remain failures within 60s.
  const result = await page.request.get(path, {
    headers: {
      'X-Project-ID': project
    },
    timeout: 60000,
    maxRetries: 2
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
        // Observe only the new document's real UI review: an old review can
        // finish during reload, after its response body has been discarded.
        let reloadedDocumentAt = Infinity;
        const markReloadedDocument = frame => {
          if (frame === page.mainFrame()) reloadedDocumentAt = Date.now();
        };
        page.on('framenavigated', markReloadedDocument);
        const reviewResponse = page.waitForResponse(response => {
          const url = new URL(response.url());
          return url.pathname === '/api/engineering/workflow/parameters/review' && url.searchParams.get('proposal') === proposalId && response.request().method() === 'GET' && response.request().headers()['x-project-id'] === project && response.request().timing().startTime >= reloadedDocumentAt;
        }, {
          timeout: 60000
        });
        try {
          await page.reload();
        } finally {
          page.off('framenavigated', markReloadedDocument);
        }
        const actualReviewResponse = await reviewResponse;
        expect(actualReviewResponse.ok(), await actualReviewResponse.text()).toBe(true);
        const review = await actualReviewResponse.json();
        expect(review.edit_token).toBe(saved.edit_token);
        await expect(common.locator('#seed')).toHaveValue(String(seed));
        for (const [field, value] of Object.entries(scenario.fields)) {
          const input = page.locator(`#${field}`);
          const details = input.locator('xpath=ancestor::details[1]');
          if ((await details.count()) && (await details.getAttribute('open')) === null) await details.locator(':scope > summary').click();
          await expect(input).toHaveValue(value);
        }
        const selectedFindings = review.findings.filter(finding => finding.technology === scenario.technology);
        if (selectedFindings.length && selectedFindings.every(finding => finding.code === 'CAPACITY_DEVICE_EVIDENCE_MISSING')) {
          await expect(page.locator('#parameter-findings form')).toHaveCount(0);
          await expect(page.locator('#parameter-findings [role="alert"]')).toHaveCount(0);
          await expect(page.locator('#parameter-findings')).toContainText('kein Simulationsblocker');
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
  let restartedJob = null;
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
    // A completed historical run must not block the current approved preflight.
    await openSimulationRun(fresh);
    await expect(fresh.getByRole('button', {
      name: 'Lauf starten',
      exact: true
    })).toBeEnabled();
    await fresh.locator('.simulation-command-bar').getByRole('button', {
      name: 'Ansicht zurücksetzen',
      exact: true
    }).click();
    await fresh.getByRole('alertdialog').getByRole('button', {
      name: 'Ansicht zurücksetzen',
      exact: true
    }).click();
    await expect(freshRunner).not.toHaveAttribute('data-job-id');
    await fresh.reload();
    await openSimulationRun(fresh);
    await expect(fresh.getByRole('button', {
      name: 'Lauf starten',
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
    // Actual normal START, without resetting/deleting the restored completed run.
    await fresh.goto(`/studio/simulation?project=${project}&snapshot=${artifacts.snapshot}`);
    await expect(freshRunner).toHaveAttribute('data-job-id', artifacts.job);
    await openSimulationRun(fresh);
    await fresh.getByRole('button', {
      name: 'Lauf starten',
      exact: true
    }).click();
    await expect.poll(async () => {
      restartedJob = await freshRunner.getAttribute('data-job-id');
      return Boolean(restartedJob && restartedJob !== artifacts.job);
    }).toBe(true);
    await expect.poll(async () => (await readProject(fresh, project, `/api/simulations/${restartedJob}`)).status, {
      timeout: 180000
    }).toBe('completed');
    const preserved = await readProject(fresh, project, `/api/engineering/workflow/simulation-snapshots/${artifacts.snapshot}`);
    expect(preserved.job_id).toBe(artifacts.job);
    expect(preserved.result.trace.events).toBe(artifacts.trace_events);
    await fresh.reload();
    await expect(freshRunner).toHaveAttribute('data-job-id', restartedJob);
    await fresh.goto(`/studio/results?project=${project}-other&snapshot=${artifacts.snapshot}`);
    await expect(fresh.getByText('Dieser Simulationslauf ist in diesem Projekt nicht verfügbar.', {
      exact: true
    })).toBeVisible();
    await expect(fresh.locator('.result-run-list button.active')).toHaveCount(0);
  } finally {
    await freshContext.close();
  }
  await openWizard(page, project);
  expect((await readProject(page, project, '/api/simulations')).jobs.map(job => job.id).sort()).toEqual([artifacts.job, restartedJob].sort());
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
    // Rechecking persisted findings must use the existing request, and must
    // never release unchanged invalid native values or invent device evidence.
    const continued = page.waitForRequest(request => {
      var _request$postDataJSON3;
      return new URL(request.url()).pathname === '/api/agent/chat' && request.method() === 'POST' && ((_request$postDataJSON3 = request.postDataJSON()) === null || _request$postDataJSON3 === void 0 || (_request$postDataJSON3 = _request$postDataJSON3.wizard_command) === null || _request$postDataJSON3 === void 0 ? void 0 : _request$postDataJSON3.action) === 'CONTINUE';
    });
    await evidenceReview.getByRole('button', {
      name: 'Gespeicherte Angaben erneut prüfen & fortsetzen',
      exact: true
    }).click();
    const command = (await continued).postDataJSON().wizard_command;
    expect(command.run_id).toBe(workflow.context.agent_execution.run_id);
    expect(command.request_revision).toBe(workflow.context.agent_execution.request_revision);
    await expect.poll(async () => {
      const next = await readProject(page, project, '/api/engineering/workflow?view=summary');
      return next.context.agent_execution.state === 'BLOCKED' && next.context.agent_execution.updated_at !== workflow.context.agent_execution.updated_at;
    }, {
      timeout: 60000
    }).toBe(true);
    const rechecked = await readProject(page, project, '/api/engineering/workflow');
    expect(rechecked.context.agent_execution.run_id).toBe(command.run_id);
    expect(rechecked.context.agent_execution.request_revision).toBe(command.request_revision);
    expect(rechecked.context.agent_execution.blocking_findings.map(item => item.code)).toContain('TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH');
    expect(rechecked.parameters).toEqual(workflow.parameters);
    expect(rechecked.statuses.parameters).toBe('IN_PROGRESS');
    await expect(dialog.getByRole('button', {
      name: 'Fertig stellen',
      exact: true
    })).toBeDisabled();
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
    var _request$postDataJSON4;
    return request.url().endsWith('/api/agent/chat') && request.method() === 'POST' && ((_request$postDataJSON4 = request.postDataJSON()) === null || _request$postDataJSON4 === void 0 || (_request$postDataJSON4 = _request$postDataJSON4.wizard_command) === null || _request$postDataJSON4 === void 0 ? void 0 : _request$postDataJSON4.action) === 'START';
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
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmVhZEZpbGUiLCJyYW5kb21VVUlEIiwiZXhlY0ZpbGVTeW5jIiwiV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyIsIldJWkFSRF9TVEVQUyIsIldJWkFSRF9ET05FIiwicmV2aWV3VmlydHVhbFRyYW5zcG9ydHMiLCJzdGVwcyIsImRvbmUiLCJvcGVuU2ltdWxhdGlvblJ1biIsInBhZ2UiLCJjb250cm9scyIsImxvY2F0b3IiLCJnZXRBdHRyaWJ1dGUiLCJjbGljayIsInBhbmVsIiwid3JpdGVUaW1pbmdzIiwiTWFwIiwid29ya2Zsb3dQYWdlRmFpbHVyZXMiLCJXZWFrTWFwIiwicHJvZ3Jlc3NNaWxlc3RvbmVzIiwiYmVmb3JlRWFjaCIsImluZm8iLCJyb3dzIiwic2V0IiwidGVzdElkIiwicmVxdWVzdHMiLCJvbiIsInJlcXVlc3QiLCJpbmNsdWRlcyIsIm1ldGhvZCIsInJvdyIsInVybCIsInN0YXJ0ZWQiLCJEYXRlIiwibm93IiwicHVzaCIsInJlc3BvbnNlIiwiZ2V0Iiwic3RhdHVzIiwiVVJMIiwicGF0aG5hbWUiLCJkdXJhdGlvbl9tcyIsIl9yZXF1ZXN0JGZhaWx1cmUiLCJmYWlsdXJlIiwiZXJyb3JUZXh0IiwiYWZ0ZXJFYWNoIiwiYXR0YWNoIiwiYm9keSIsIkpTT04iLCJzdHJpbmdpZnkiLCJjb250ZW50VHlwZSIsImRlbGV0ZSIsInRvRXF1YWwiLCJnZXRCeVJvbGUiLCJuYW1lIiwiZXhhY3QiLCJub3QiLCJ0b0JlVmlzaWJsZSIsImFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkiLCJnZXRCeVRleHQiLCJpc1Zpc2libGUiLCJ0b0JlIiwicmVhZFByb2plY3QiLCJwcm9qZWN0IiwicGF0aCIsInJlc3VsdCIsImhlYWRlcnMiLCJ0aW1lb3V0IiwibWF4UmV0cmllcyIsIm9rIiwiRXJyb3IiLCJ0ZXh0Iiwic2xpY2UiLCJqc29uIiwiZGlzcG9zZSIsInJlYWRXYXJuaW5nUmV2aWV3U3RhdGUiLCJfdmVyaWZpZWQkY29udGV4dCRhZ2UyIiwiX3ZlcmlmaWVkJGNvbnRleHQkYWdlMyIsImF1dGhvcml0eSIsInBhcmFtZXRlcnMiLCJ2ZXJpZmllZCIsInByb2plY3RfaWQiLCJmaWVsZCIsIl92ZXJpZmllZCRjb250ZXh0JGFnZSIsIl9hdXRob3JpdHkkY29udGV4dCRhZyIsImNvbnRleHQiLCJhZ2VudF9leGVjdXRpb24iLCJzdGF0dXNlcyIsInJ1bl9pZCIsInJlcXVlc3RfcmV2aXNpb24iLCJwcmVmbGlnaHRfd2FybmluZ19hcHByb3ZhbCIsIm9wZW5XaXphcmQiLCJnb3RvIiwid2FpdFVudGlsIiwiZGlhbG9nIiwic3RlcCIsInN0ZXBXaWR0aCIsImV2YWx1YXRlIiwiZWxlbWVudCIsImdldEJvdW5kaW5nQ2xpZW50UmVjdCIsIndpZHRoIiwiY2FyZHMiLCJhbGwiLCJ0b0hhdmVMZW5ndGgiLCJjYXJkIiwidG9CZUdyZWF0ZXJUaGFuIiwiYWxsT2JqZWN0cyIsInJlc291cmNlIiwiaXRlbXMiLCJvZmZzZXQiLCJsZW5ndGgiLCJyZXN0YXJ0QXBwbGljYXRpb24iLCJjcmFzaCIsImNvbnRhaW5lciIsInByb2Nlc3MiLCJlbnYiLCJOSVNfRTJFX0FQUF9DT05UQUlORVIiLCJ0b01hdGNoIiwiZG9ja2VyIiwiTklTX1RFU1RfRE9DS0VSIiwibGFiZWwiLCJlbmNvZGluZyIsInRyaW0iLCJwb2xsIiwidmVyaWZ5U2lnbmFsQ29udHJhY3RzIiwiZXhwZWN0ZWQiLCJoYXJkd2FyZSIsImZ1bmN0aW9ucyIsIm1lc3NhZ2VzIiwic2lnbmFscyIsIlByb21pc2UiLCJtYXAiLCJub2RlcyIsIml0ZW0iLCJpZCIsImZ1bmN0aW9uc0J5SWQiLCJtZXNzYWdlc0J5SWQiLCJjb250cmFjdHMiLCJzaWduYWwiLCJfcmVmIiwiX3NpZ25hbCRkYXRhJGVudW1fdmFsIiwiX3NpZ25hbCRkYXRhIiwiX3NpZ25hbCRzZW1hbnRpYyRzZW1hIiwiX3NpZ25hbCRzZW1hbnRpYyIsIl9zaWduYWwkY29uZmlndXJhdGlvbiIsIl9zaWduYWwkY29uZmlndXJhdGlvbjIiLCJtZXNzYWdlIiwibWVzc2FnZV9pZCIsInRvQmVUcnV0aHkiLCJyZWZlcmVuY2UiLCJjb25maWd1cmF0aW9uIiwiY29tbXVuaWNhdGlvbl9jb250cmFjdCIsInByb2R1Y2VyX3JlZiIsImZuIiwib3duZXIiLCJoYXJkd2FyZV9ub2RlX2lkIiwicHJvZHVjZXIiLCJkZXZpY2VfdHlwZSIsImtleSIsImpvaW4iLCJ0b0JlVW5kZWZpbmVkIiwiT2JqZWN0IiwiZnJvbUVudHJpZXMiLCJfc2lnbmFsJGZpZWxkIiwiZW51bV92YWx1ZXMiLCJkYXRhIiwic2VtYW50aWNfdHlwZSIsInNlbWFudGljIiwiZ2VuZXJhdGlvbl9yb2xlIiwidmVyaWZ5QXJ0aWZhY3RzIiwibWluaW11bUNhbm9uaWNhbFNpZ25hbHMiLCJpbnRlcm5hbENvbnRyb2xsZXIiLCJleHBlY3RlZFBhcmFtZXRlcnMiLCJleHBlY3RlZE5hdGl2ZVJhdGVzIiwiX2Fzc2Vzc21lbnQkc2NvcGVfY292Iiwid29ya2Zsb3ciLCJqb2JMaXN0Iiwic25hcHNob3RzIiwia2V5cyIsInNvcnQiLCJoYXMiLCJqb2JzIiwic25hcHNob3QiLCJzaW11bGF0aW9ucyIsImZpbmQiLCJqb2JfaWQiLCJmdWxsIiwiZGF0YV9iaXRyYXRlIiwiY2FuX2ZkX2RhdGFfcHJlc2NhbGVyIiwicnVudGltZVBhcmFtZXRlcnMiLCJ0b01hdGNoT2JqZWN0IiwiY2FuRmROZXR3b3JrcyIsIm5ldHdvcmtzIiwiZmlsdGVyIiwibmV0d29yayIsInRlY2hub2xvZ3kiLCJyYXRlcyIsImVudHJpZXMiLCJhc3Nlc3NtZW50Iiwic2NvcGVfY292ZXJhZ2UiLCJzY29wZV9tb2RlIiwiY29tcGxldGUiLCJjb25mb3JtYW5jZSIsImZhaWxlZF9yb3V0ZV9jb3VudCIsInRvQmVHcmVhdGVyVGhhbk9yRXF1YWwiLCJleGNsdWRlZCIsInRyYW5zcG9ydF9leGNsdXNpb25zIiwicm91dGluZyIsImVuYWJsZWQiLCJjb250cmFjdCIsImNvbnN1bWVyX3JlZnMiLCJyZWFzb25fY29kZSIsInJvbGUiLCJjb250cm9sbGVyIiwic2NvcGUiLCJleGNsdWRlZFNpZ25hbHMiLCJTZXQiLCJmbGF0TWFwIiwic2lnbmFsX2lkcyIsIm9ic2VydmVkX3NpZ25hbF9jb3VudCIsInNpemUiLCJ0cmFjZSIsImNvdW50IiwiZXZlbnRzIiwic29tZSIsImpvYiIsInRyYWNlX2V2ZW50cyIsInBhcmFtZXRlcl9wcm9vZiIsInNhdmVkIiwic2ltdWxhdGlvbl9yYXRlcyIsImJpdHJhdGUiLCJhcmJpdHJhdGlvbl9iaXRyYXRlIiwiaGFyZHdhcmVfZXZpZGVuY2UiLCJ1bmRlZmluZWQiLCJyZXBlYXRQYXJhbWV0ZXJSZXR1cm4iLCJwcm9wb3NhbElkIiwic2NlbmFyaW9zIiwic2VlZHMiLCJiZWZvcmUiLCJpZGVudGl0eSIsIm5vZGVJZHMiLCJzdGFydHMiLCJ0cmFja1N0YXJ0cyIsIl9yZXF1ZXN0JHBvc3REYXRhSlNPTiIsImVuZHNXaXRoIiwicG9zdERhdGFKU09OIiwid2l6YXJkX2NvbW1hbmQiLCJhY3Rpb24iLCJldmlkZW5jZSIsIndpemFyZCIsImN5Y2xlIiwic2VlZCIsInNjZW5hcmlvIiwiX3NhdmVkJHBhcmFtZXRlcnMkc2ltIiwiZW5jb2RlVVJJQ29tcG9uZW50IiwiY29tbW9uIiwidmFsdWUiLCJmaWVsZHMiLCJfc2NlbmFyaW8kZWRpdEZpZWxkcyIsImlucHV0IiwiZGV0YWlscyIsImVkaXRGaWVsZHMiLCJmaWxsIiwidG9IYXZlVmFsdWUiLCJTdHJpbmciLCJwYXJhbWV0ZXJfcHJvdmVuYW5jZSIsImR1cmF0aW9uX3MiLCJzb3VyY2UiLCJzY29wZWQiLCJ0ZWNobm9sb2d5X3BhcmFtZXRlcnMiLCJhc3N1bWVkIiwic2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnMiLCJ2YWx1ZXMiLCJuYXRpdmVWYWx1ZXMiLCJuYXRpdmUiLCJjb25maXJtZWQiLCJoYXNPd24iLCJwcm92ZW5hbmNlIiwidXNlclZhbHVlcyIsInZhbHVlX29yaWdpbiIsInRlY2hub2xvZ3lfZGVmYXVsdHMiLCJzdGFsZSIsImNhbm9uaWNhbElkcyIsImNhbm9uaWNhbF9pZHMiLCJyZWxvYWRlZERvY3VtZW50QXQiLCJJbmZpbml0eSIsIm1hcmtSZWxvYWRlZERvY3VtZW50IiwiZnJhbWUiLCJtYWluRnJhbWUiLCJyZXZpZXdSZXNwb25zZSIsIndhaXRGb3JSZXNwb25zZSIsInNlYXJjaFBhcmFtcyIsInRpbWluZyIsInN0YXJ0VGltZSIsInJlbG9hZCIsIm9mZiIsImFjdHVhbFJldmlld1Jlc3BvbnNlIiwicmV2aWV3IiwiZWRpdF90b2tlbiIsInNlbGVjdGVkRmluZGluZ3MiLCJmaW5kaW5ncyIsImZpbmRpbmciLCJldmVyeSIsImNvZGUiLCJ0b0hhdmVDb3VudCIsInRvQ29udGFpblRleHQiLCJyZXN1bWVSZXN0b3JlIiwicmVzdG9yZVBhdXNlIiwicmVzb2x2ZSIsImRlbGF5UmVzdG9yZSIsInJvdXRlIiwiY29udGludWUiLCJkZWxheWVkIiwidW5yb3V0ZUFsbCIsImJlaGF2aW9yIiwicmVzdG9yZWQiLCJzdGF0ZSIsImNvbnZlcnNhdGlvbiIsImFjdGl2ZV9wcm9wb3NhbCIsImZyZXNoIiwiYWZ0ZXIiLCJwcm9wb3NhbF9pZCIsInNhdmVkX3ZhbHVlcyIsImFzc3VtcHRpb25zIiwicmVzdG9yZWRfc3RhdHVzIiwiY29tcGxldGVUaHJvdWdoV2l6YXJkIiwicmVzdGFydCIsImV4cGVjdGVkSGFyZHdhcmUiLCJjcmFzaFNpbXVsYXRpb24iLCJleHBlY3RlZFNpZ25hbHMiLCJhZnRlckZpcnN0TW9kZWxBcHBsaWVkIiwic3RvcE9uRXZpZGVuY2VCbG9jayIsImJlZm9yZVByb3Bvc2FsUmV2aWV3IiwicmV2aWV3Q291bnQiLCJydW5JZCIsInJldmlld2VkIiwicmVzdGFydGVkSm9iSWQiLCJ3YXRjaGRvZyIsInBlcmZvcm1hbmNlIiwiY2hlY2twb2ludCIsIl93b3JrZmxvdyRjb250ZXh0JGFnZSIsIl93b3JrZmxvdyRjb250ZXh0JGFnZTIiLCJfZXhlY3V0aW9uJGJsb2NraW5nX2YiLCJfZXhlY3V0aW9uJG1lc3NhZ2UiLCJyZWFkeVZlcnNpb24iLCJyZWFkeVNpbmNlIiwiaXNDaGVja3BvaW50IiwicmVtYWluaW5nIiwicHJvZ3Jlc3MiLCJvYnNlcnZlIiwiYWR2YW5jZWQiLCJhdCIsInRvSVNPU3RyaW5nIiwiZnJvbnRpZXIiLCJjb21wbGV0ZWRUaHJvdWdoIiwiZXhlY3V0aW9uIiwidmFsaWRhdGlvbiIsInJ1bm5pbmciLCJCb29sZWFuIiwicmVjb3ZlcmFibGUiLCJ1cGRhdGVkX2F0IiwiYnV0dG9uIiwiZXZhbHVhdGVBbGwiLCJidXR0b25zIiwiZGlzYWJsZWQiLCJnZXRDbGllbnRSZWN0cyIsImdldENvbXB1dGVkU3R5bGUiLCJ2aXNpYmlsaXR5IiwiYXR0ZW1wdCIsIndhaXRGb3JUaW1lb3V0IiwiTWF0aCIsIm1pbiIsImJsb2NraW5nX2ZpbmRpbmdzIiwiYmVmb3JlUmV2aWV3IiwicHJlZmxpZ2h0Iiwid2FybmluZ3MiLCJmaXJzdCIsInN0YXJ0ZWRXYWxsIiwiYXBwcm92YWxSZXNwb25zZSIsImFwcHJvdmVkIiwicmVjZWlwdCIsImFmdGVyUmV2aWV3IiwicHJvb2YiLCJzbmFwc2hvdElkIiwicmVxdWVzdFByb2plY3QiLCJzdWJtaXR0ZWQiLCJmaW5pc2hlZFdhbGwiLCJjb21taXR0ZWRBdCIsImNvbW1pdHRlZCIsImNvbW1pdFdhcm5pbmdSZXZpZXciLCJtYW51YWxXYXJuaW5nQXBwcm92YWwiLCJhcHByb3ZhbElkZW50aXR5IiwiYXBwcm92YWwiLCJfYXdhaXQkcmVhZFByb2plY3QkY28iLCJfY29udmVyc2F0aW9uJGRhdGEiLCJfcHJvcG9zYWwkZGF0YSIsInByb3Bvc2FsIiwidmFsaWRhdGlvbl9yZXN1bHQiLCJ2aXNpYmxlIiwiaW5uZXJUZXh0IiwiZXJyb3IiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQiLCJsYXRlc3QiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQyIiwiX2xhdGVzdCRjb250ZXh0JGFnZW50MyIsIl9sYXRlc3Qkc3RhdHVzZXMiLCJjYW5kaWRhdGUiLCJwcm9wb3NhbF90eXBlIiwiY2hhbmdlcyIsImNoYW5nZSIsIm9iamVjdF90eXBlIiwiYXJyYXlDb250YWluaW5nIiwicmV2aWV3QWN0aW9uIiwicmV2aWV3T25seSIsInByb3Bvc2FsVHlwZSIsImFwcGx5UmVzcG9uc2UiLCJ0b0JlRW5hYmxlZCIsImFwcGxpZWQiLCJhZGQiLCJfYW1lbmRlZCRjb250ZXh0JGFnZW4iLCJhbWVuZGVkIiwiX2N1cnJlbnQkY29udGV4dCRhZ2VuIiwiY3VycmVudCIsImZ1bGZpbGwiLCJnZXRCeVRpdGxlIiwiZ2V0QnlMYWJlbCIsInRvQmVEaXNhYmxlZCIsInVucm91dGUiLCJjYXRhbG9nIiwidGVjaG5vbG9neV9jb3VudCIsImJyb3dzZXIiLCJ0ZXN0SW5mbyIsImVycm9ycyIsInN0YXJ0UmVxdWVzdCIsIndhaXRGb3JSZXF1ZXN0IiwiX3JlcXVlc3QkcG9zdERhdGFKU09OMiIsInN1Ym1pdCIsInJlcXVlc3RlZCIsIndpemFyZF9jb250ZXh0IiwidGVjaG5vbG9naWVzIiwiX2F3YWl0JHJlYWRQcm9qZWN0JGNvMiIsInBlbmRpbmciLCJjb250aW51aXR5IiwiYXJ0aWZhY3RzIiwiZmluaXNoZWQiLCJ0b0hhdmVVUkwiLCJSZWdFeHAiLCJzZWxlY3RlZFJ1biIsInRvSGF2ZUNsYXNzIiwidG9Mb2NhbGVTdHJpbmciLCJydW5uZXIiLCJ0b0hhdmVBdHRyaWJ1dGUiLCJmcmVzaENvbnRleHQiLCJuZXdDb250ZXh0IiwiYmFzZVVSTCIsIm9yaWdpbiIsInJlc3RhcnRlZEpvYiIsIm5ld1BhZ2UiLCJmcmVzaFJ1bm5lciIsInNjcmVlbnNob3QiLCJwcmVzZXJ2ZWQiLCJjbG9zZSIsImNoZWNrIiwic2VsZWN0T3B0aW9uIiwicmVqZWN0cyIsInRvVGhyb3ciLCJ0b0NvbnRhaW4iLCJhcnRpZmFjdF9jaGVja3MiLCJyZXF1aXJlZCIsInByb2ZpbGVfdmFsdWVzIiwiZGV2aWNlU291cmNlIiwidG9IYXZlUHJvcGVydHkiLCJuYXRpdmVUZWNobm9sb2d5IiwicHJvZmlsZV9maW5kaW5ncyIsImV2aWRlbmNlUmV2aWV3IiwiY29udGludWVkIiwiX3JlcXVlc3QkcG9zdERhdGFKU09OMyIsImNvbW1hbmQiLCJuZXh0IiwicmVjaGVja2VkIiwic2ltdWxhdGlvbiIsInJhdGVfcmV2aWV3X3Byb3Bvc2FscyIsImkyYyIsImludGVyZmFjZXMiLCJkb21haW4iLCJ1bml0Iiwic3RhcnRDYXB0dXJlZExhcmdlV2l6YXJkIiwib3JpZ2luYWwiLCJpbXBvcnQiLCJtZXRhIiwibWV0YWRhdGEiLCJwYXJzZSIsImJhc2VsaW5lIiwicHJvbXB0IiwicmVwbGFjZSIsInBvc3QiLCJvcGVyYXRpb25faWQiLCJ0YXJnZXQiLCJsYXJnZVBhcmFtZXRlclNjZW5hcmlvcyIsImxpbl9iaXRyYXRlX2JwcyIsInBhcmFtZXRlclJldHVyblJldmlld3MiLCJyZXZpZXdTZWVkIiwibGluIiwiY2FuX2ZkIiwiZXRoZXJuZXQiLCJleGNsdWRlZFNpZ25hbElkcyIsImZpeHR1cmUiLCJyZXF1ZXN0X3NoYTI1NiIsInR5cGUiLCJfY29udGludWl0eSRyZXZpZXdPbmwiLCJjb3ZlcmFnZSIsImN5Y2xlcyIsImdyYXBoIiwiY2x1c3Rlcl9pZCIsIm5ldHdvcmtfaWQiLCJuZXR3b3JrX2xhYmVsIiwiYnVzX25hbWUiLCJjb250cm9sbGVycyIsImVjdSIsInNlbnNvcnMiLCJhY3R1YXRvcnMiLCJobWlfcm91dGVzIiwicHJvamVjdF9uYW1lIiwic2NvcGVfaWRzIiwibW9kZSIsInByb2Nlc3NfaWRzIiwidGFzayIsIm9yaWdpbmFsTmV0d29ya3MiLCJhbWVuZCIsImV4cGFuZCIsInN5c3RlbV9vd25lcl9pZCIsInNlbnNvck5ldHdvcmsiLCJ0b3BvbG9neSIsImxvY2FsRWRnZSIsImVkZ2VzIiwiZWRnZSIsInBoeXNpY2FsTmV0d29ya0lkIiwiYnVzIiwicm91dGluZ01ldGFkYXRhIiwidG9Db250YWluRXF1YWwiLCJvYmplY3RDb250YWluaW5nIiwiYXBwcm92YWxTdGF0ZSIsInByb3RvY29sIiwic2lkZSIsImhhcmR3YXJlSWQiLCJub2RlIiwiZW5naW5lZXJpbmdJZCIsInBvcnRzIiwidHhyeCIsImhhc1RleHQiLCJzZWxlY3RlZCIsInRvQmVDaGVja2VkIiwidW5jaGVjayIsIl9yZXF1ZXN0JHBvc3REYXRhSlNPTjQiLCJzeXN0ZW1fY2x1c3Rlcl9hc3NpZ25tZW50cyIsImNsdXN0ZXIiLCJfY2x1c3RlciRmdW5jdGlvbmFsX3IiLCJmdW5jdGlvbmFsX3JvdXRlcyIsImV4Y2x1ZGVkX3NpZ25hbHMiLCJhcHBseSIsImdlYXJib3giLCJlbW90b3IiXSwic291cmNlcyI6WyJ3aXphcmQuc3BlYy50cyJdLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyB0ZXN0LCBleHBlY3QsIHR5cGUgUGFnZSB9IGZyb20gJ3BsYXl3cmlnaHQvdGVzdCc7XHJcbmltcG9ydCB7IHJlYWRGaWxlIH0gZnJvbSAnbm9kZTpmcy9wcm9taXNlcyc7XHJcbmltcG9ydCB7IHJhbmRvbVVVSUQgfSBmcm9tICdub2RlOmNyeXB0byc7XHJcbmltcG9ydCB7IGV4ZWNGaWxlU3luYyB9IGZyb20gJ25vZGU6Y2hpbGRfcHJvY2Vzcyc7XHJcbmltcG9ydCB7IFdpemFyZFByb2dyZXNzV2F0Y2hkb2csIFdJWkFSRF9TVEVQUywgV0laQVJEX0RPTkUgfSBmcm9tICcuL3N1cHBvcnQvd2l6YXJkLXByb2dyZXNzLXdhdGNoZG9nJztcclxuaW1wb3J0IHsgcmV2aWV3VmlydHVhbFRyYW5zcG9ydHMgfSBmcm9tICcuL3N1cHBvcnQvbmF0aXZlLXRyYW5zcG9ydC1maXh0dXJlcyc7XHJcblxyXG5jb25zdCBzdGVwcyA9IFdJWkFSRF9TVEVQUztcclxuY29uc3QgZG9uZSA9IFdJWkFSRF9ET05FO1xyXG5cclxuYXN5bmMgZnVuY3Rpb24gb3BlblNpbXVsYXRpb25SdW4ocGFnZTogUGFnZSkge1xyXG4gIGNvbnN0IGNvbnRyb2xzID0gcGFnZS5sb2NhdG9yKCdbYXJpYS1jb250cm9scz1cInNpbXVsYXRpb24tY29udHJvbHNcIl0nKTtcclxuICBpZiAoYXdhaXQgY29udHJvbHMuZ2V0QXR0cmlidXRlKCdhcmlhLWV4cGFuZGVkJykgPT09ICdmYWxzZScpIGF3YWl0IGNvbnRyb2xzLmNsaWNrKCk7XHJcbiAgY29uc3QgcGFuZWwgPSBwYWdlLmxvY2F0b3IoJy5zaW11bGF0aW9uLWNvbW1hbmQtcGFuZWwnKTtcclxuICBpZiAoYXdhaXQgcGFuZWwuZ2V0QXR0cmlidXRlKCdvcGVuJykgPT09IG51bGwpIGF3YWl0IHBhbmVsLmxvY2F0b3IoJzpzY29wZSA+IHN1bW1hcnknKS5jbGljaygpO1xyXG59XHJcbnR5cGUgV3JpdGVUaW1pbmcgPSB7IHVybDogc3RyaW5nOyBzdGFydGVkOiBudW1iZXI7IGR1cmF0aW9uX21zPzogbnVtYmVyOyBzdGF0dXM/OiBudW1iZXI7IGZhaWx1cmU/OiBzdHJpbmcgfTtcclxuY29uc3Qgd3JpdGVUaW1pbmdzID0gbmV3IE1hcDxzdHJpbmcsIFdyaXRlVGltaW5nW10+KCk7XHJcbmNvbnN0IHdvcmtmbG93UGFnZUZhaWx1cmVzID0gbmV3IFdlYWtNYXA8UGFnZSwgc3RyaW5nW10+KCk7XHJcbmNvbnN0IHByb2dyZXNzTWlsZXN0b25lcyA9IG5ldyBNYXA8c3RyaW5nLCB1bmtub3duW10+KCk7XHJcblxyXG50ZXN0LmJlZm9yZUVhY2goYXN5bmMgKHsgcGFnZSB9LCBpbmZvKSA9PiB7XHJcbiAgY29uc3Qgcm93czogV3JpdGVUaW1pbmdbXSA9IFtdO1xyXG4gIHdyaXRlVGltaW5ncy5zZXQoaW5mby50ZXN0SWQsIHJvd3MpO1xyXG4gIHdvcmtmbG93UGFnZUZhaWx1cmVzLnNldChwYWdlLCBbXSk7XHJcbiAgcHJvZ3Jlc3NNaWxlc3RvbmVzLnNldChpbmZvLnRlc3RJZCwgW10pO1xyXG4gIGNvbnN0IHJlcXVlc3RzID0gbmV3IE1hcDxvYmplY3QsIFdyaXRlVGltaW5nPigpO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3QnLCByZXF1ZXN0ID0+IHtcclxuICAgIGlmICghWydQT1NUJywgJ1BVVCcsICdQQVRDSCcsICdERUxFVEUnXS5pbmNsdWRlcyhyZXF1ZXN0Lm1ldGhvZCgpKSkgcmV0dXJuO1xyXG4gICAgY29uc3Qgcm93ID0geyB1cmw6IHJlcXVlc3QudXJsKCksIHN0YXJ0ZWQ6IERhdGUubm93KCkgfTtcclxuICAgIHJvd3MucHVzaChyb3cpOyByZXF1ZXN0cy5zZXQocmVxdWVzdCwgcm93KTtcclxuICB9KTtcclxuICBwYWdlLm9uKCdyZXNwb25zZScsIHJlc3BvbnNlID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXNwb25zZS5yZXF1ZXN0KCkpO1xyXG4gICAgaWYgKHJvdykgcm93LnN0YXR1cyA9IHJlc3BvbnNlLnN0YXR1cygpO1xyXG4gICAgaWYgKHJlc3BvbnNlLnN0YXR1cygpID09PSA0MTMgJiYgL15cXC9hcGlcXC9lbmdpbmVlcmluZ1xcL3dvcmtmbG93KD86XFwvfCQpLy50ZXN0KG5ldyBVUkwocmVzcG9uc2UudXJsKCkpLnBhdGhuYW1lKSkge1xyXG4gICAgICB3b3JrZmxvd1BhZ2VGYWlsdXJlcy5nZXQocGFnZSkhLnB1c2goYEhUVFAgNDEzOiAke3Jlc3BvbnNlLnVybCgpfWApO1xyXG4gICAgfVxyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3RmaW5pc2hlZCcsIHJlcXVlc3QgPT4ge1xyXG4gICAgY29uc3Qgcm93ID0gcmVxdWVzdHMuZ2V0KHJlcXVlc3QpO1xyXG4gICAgaWYgKHJvdykgcm93LmR1cmF0aW9uX21zID0gRGF0ZS5ub3coKSAtIHJvdy5zdGFydGVkO1xyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3RmYWlsZWQnLCByZXF1ZXN0ID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXF1ZXN0KTtcclxuICAgIGlmIChyb3cpIHsgcm93LmR1cmF0aW9uX21zID0gRGF0ZS5ub3coKSAtIHJvdy5zdGFydGVkOyByb3cuZmFpbHVyZSA9IHJlcXVlc3QuZmFpbHVyZSgpPy5lcnJvclRleHQ7IH1cclxuICB9KTtcclxufSk7XHJcblxyXG50ZXN0LmFmdGVyRWFjaChhc3luYyAoeyBwYWdlIH0sIGluZm8pID0+IHtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd3JpdGUtcmVxdWVzdC10aW1pbmdzJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh3cml0ZVRpbWluZ3MuZ2V0KGluZm8udGVzdElkKSB8fCBbXSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgYXdhaXQgaW5mby5hdHRhY2goJ3dvcmtmbG93LXByb2dyZXNzLWJvdW5kYXJpZXMnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHByb2dyZXNzTWlsZXN0b25lcy5nZXQoaW5mby50ZXN0SWQpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd29ya2Zsb3ctcGFnZS1mYWlsdXJlcycsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICB3cml0ZVRpbWluZ3MuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBwcm9ncmVzc01pbGVzdG9uZXMuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBleHBlY3Qod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpLCAnVGhlIHVuZGVybHlpbmcgZW5naW5lZXJpbmcgcGFnZSBtdXN0IHJlbWFpbiByZWFkYWJsZSB0aHJvdWdob3V0IHJlbG9hZCBhbmQgcmVjb3ZlcnkuJykudG9FcXVhbChbXSk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdoZWFkaW5nJywge25hbWU6ICdEaWUgQW5zaWNodCBrb25udGUgbmljaHQgZ2VsYWRlbiB3ZXJkZW4uJywgZXhhY3Q6IHRydWV9KSxcclxuICAgICdBIGNyYXNoZWQgcGFyYW1ldGVyIG9yIGVuZ2luZWVyaW5nIHBhZ2UgbXVzdCBuZXZlciBjb3VudCBhcyBhIHN1Y2Nlc3NmdWwgd2l6YXJkIGRldG91ci4nKS5ub3QudG9CZVZpc2libGUoKTtcclxufSk7XHJcblxyXG5hc3luYyBmdW5jdGlvbiBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2U6IFBhZ2UpIHtcclxuICBleHBlY3Qod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpLCAnQSB3b3JraW5nIHdpemFyZCBvdmVybGF5IG11c3Qgbm90IGNvbmNlYWwgYSB3b3JrZmxvdyBIVFRQIDQxMy4nKS50b0VxdWFsKFtdKTtcclxuICBleHBlY3QoYXdhaXQgcGFnZS5nZXRCeVRleHQoJ0VuZ2luZWVyaW5nLUFQSSBuaWNodCBlcnJlaWNoYmFyJywgeyBleGFjdDogdHJ1ZSB9KS5pc1Zpc2libGUoKSxcclxuICAgICdUaGUgdW5kZXJseWluZyBlbmdpbmVlcmluZyBwYWdlIG11c3Qgbm90IHNob3cgaXRzIEFQSSBlcnJvciB2aWV3LicpLnRvQmUoZmFsc2UpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnaGVhZGluZycsIHtuYW1lOiAnRGllIEFuc2ljaHQga29ubnRlIG5pY2h0IGdlbGFkZW4gd2VyZGVuLicsIGV4YWN0OiB0cnVlfSkpLm5vdC50b0JlVmlzaWJsZSgpO1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiByZWFkUHJvamVjdChwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIHBhdGg6IHN0cmluZykge1xyXG4gIC8vIFJlY292ZXIgb25seSBhIHBlZXIgY29ubmVjdGlvbiByZXNldCBvbiB0aGlzIGlkZW1wb3RlbnQgcmVhZC4gSFRUUCBlcnJvcnMsXHJcbiAgLy8gbWFsZm9ybWVkIGRhdGEgYW5kIGFsbCBjb250aW51aXR5IGFzc2VydGlvbnMgcmVtYWluIGZhaWx1cmVzIHdpdGhpbiA2MHMuXHJcbiAgY29uc3QgcmVzdWx0ID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldChwYXRoLCB7IGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSwgdGltZW91dDogNjBfMDAwLCBtYXhSZXRyaWVzOiAyIH0pO1xyXG4gIHRyeSB7XHJcbiAgICBpZiAoIXJlc3VsdC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYCR7cGF0aH06IEhUVFAgJHtyZXN1bHQuc3RhdHVzKCl9ICR7KGF3YWl0IHJlc3VsdC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gICAgcmV0dXJuIGF3YWl0IHJlc3VsdC5qc29uKCk7XHJcbiAgfSBmaW5hbGx5IHtcclxuICAgIC8vIFBsYXl3cmlnaHQgb3RoZXJ3aXNlIHJldGFpbnMgZXZlcnkgcG9sbGVkIHJlc3BvbnNlIHVudGlsIGNvbnRleHQgdGVhcmRvd24uXHJcbiAgICAvLyBLZWVwIHRoZSBwYXJzZWQgZXZpZGVuY2UsIHJlbGVhc2UgaXRzIGR1cGxpY2F0ZSB0cmFuc3BvcnQgYm9keSBpbW1lZGlhdGVseS5cclxuICAgIGF3YWl0IHJlc3VsdC5kaXNwb3NlKCk7XHJcbiAgfVxyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiByZWFkV2FybmluZ1Jldmlld1N0YXRlKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZykge1xyXG4gIGNvbnN0IGF1dGhvcml0eSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gIGNvbnN0IHBhcmFtZXRlcnMgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyk7XHJcbiAgY29uc3QgdmVyaWZpZWQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICBleHBlY3QocGFyYW1ldGVycy5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xyXG4gIGV4cGVjdChhdXRob3JpdHkucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcclxuICBleHBlY3QodmVyaWZpZWQucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcclxuICBmb3IgKGNvbnN0IGZpZWxkIG9mIFsncnVuX2lkJywgJ3JlcXVlc3RfcmV2aXNpb24nXSlcclxuICAgIGV4cGVjdCh2ZXJpZmllZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uW2ZpZWxkXSkudG9CZShhdXRob3JpdHkuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LltmaWVsZF0pO1xyXG4gIHJldHVybiB7IHByb2plY3RfaWQ6IHZlcmlmaWVkLnByb2plY3RfaWQsIHN0YXR1c2VzOiB2ZXJpZmllZC5zdGF0dXNlcyxcclxuICAgIGNvbnRleHQ6IHsgYWdlbnRfZXhlY3V0aW9uOiB7IHJ1bl9pZDogdmVyaWZpZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZCxcclxuICAgICAgcmVxdWVzdF9yZXZpc2lvbjogdmVyaWZpZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJlcXVlc3RfcmV2aXNpb24gfSB9LFxyXG4gICAgcGFyYW1ldGVyczogeyBwcmVmbGlnaHRfd2FybmluZ19hcHByb3ZhbDogcGFyYW1ldGVycy5wYXJhbWV0ZXJzLnByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsIH0gfTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gb3BlbldpemFyZChwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcpIHtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vZW5naW5lZXJpbmc/YXNzaXN0YW50PXByb2plY3QmcHJvamVjdD0ke3Byb2plY3R9YCwgeyB3YWl0VW50aWw6ICdsb2FkJyB9KTtcclxuICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeShwYWdlKTtcclxuICByZXR1cm4gZGlhbG9nO1xyXG59XHJcblxyXG50ZXN0KCdwcm9qZWN0IG5hbWluZyBmb3JtIGNhcmRzIHVzZSB0aGUgZnVsbCB3aXphcmQgd2lkdGggQGxheW91dCcsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgJ25pcy1lMmUtcHJvamVjdC1uYW1lLWxheW91dC0nICsgcmFuZG9tVVVJRCgpKTtcclxuICBjb25zdCBzdGVwID0gZGlhbG9nLmxvY2F0b3IoJ2ZpZWxkc2V0LmFnZW50LXByb2plY3QtbmFtZS1zdGVwJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHN0ZXApLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3Qgc3RlcFdpZHRoID0gYXdhaXQgc3RlcC5ldmFsdWF0ZShlbGVtZW50ID0+IGVsZW1lbnQuZ2V0Qm91bmRpbmdDbGllbnRSZWN0KCkud2lkdGgpO1xyXG4gIGNvbnN0IGNhcmRzID0gYXdhaXQgc3RlcC5sb2NhdG9yKCc6c2NvcGUgPiBsYWJlbCcpLmFsbCgpO1xyXG4gIGV4cGVjdChjYXJkcykudG9IYXZlTGVuZ3RoKDQpO1xyXG4gIGZvciAoY29uc3QgY2FyZCBvZiBjYXJkcykge1xyXG4gICAgY29uc3Qgd2lkdGggPSBhd2FpdCBjYXJkLmV2YWx1YXRlKGVsZW1lbnQgPT4gZWxlbWVudC5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKS53aWR0aCk7XHJcbiAgICBleHBlY3Qod2lkdGgpLnRvQmVHcmVhdGVyVGhhbihzdGVwV2lkdGggKiAwLjg1KTtcclxuICB9XHJcbn0pO1xyXG5cclxuYXN5bmMgZnVuY3Rpb24gYWxsT2JqZWN0cyhwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIHJlc291cmNlOiBzdHJpbmcpIHtcclxuICBjb25zdCBpdGVtczogYW55W10gPSBbXTtcclxuICBmb3IgKGxldCBvZmZzZXQgPSAwOyA7IG9mZnNldCArPSA1MDApIHtcclxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvJHtyZXNvdXJjZX0/bGltaXQ9NTAwJm9mZnNldD0ke29mZnNldH1gKTtcclxuICAgIGl0ZW1zLnB1c2goLi4ucmVzcG9uc2UuaXRlbXMpO1xyXG4gICAgaWYgKHJlc3BvbnNlLml0ZW1zLmxlbmd0aCA8IDUwMCkgcmV0dXJuIGl0ZW1zO1xyXG4gIH1cclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2U6IFBhZ2UsIGNyYXNoID0gZmFsc2UpIHtcclxuICBjb25zdCBjb250YWluZXIgPSBwcm9jZXNzLmVudi5OSVNfRTJFX0FQUF9DT05UQUlORVIhO1xyXG4gIGV4cGVjdChjb250YWluZXIpLnRvTWF0Y2goL15uaXMtZTJlLWFwcC1bYS1mMC05XSskLyk7XHJcbiAgY29uc3QgZG9ja2VyID0gcHJvY2Vzcy5lbnYuTklTX1RFU1RfRE9DS0VSIHx8ICdkb2NrZXInO1xyXG4gIGNvbnN0IGxhYmVsID0gZXhlY0ZpbGVTeW5jKGRvY2tlciwgWydpbnNwZWN0JywgY29udGFpbmVyLCAnLS1mb3JtYXQnLCAne3tpbmRleCAuQ29uZmlnLkxhYmVscyBcIm5ldHdvcmtpcy50ZXN0XCJ9fSddLCB7IGVuY29kaW5nOiAndXRmOCcgfSkudHJpbSgpO1xyXG4gIGV4cGVjdChsYWJlbCkudG9CZSgnZGlzcG9zYWJsZScpO1xyXG4gIGV4ZWNGaWxlU3luYyhkb2NrZXIsIFsncmVzdGFydCcsIC4uLihjcmFzaCA/IFsnLXQnLCAnMCddIDogW10pLCBjb250YWluZXJdLCB7IHRpbWVvdXQ6IDYwXzAwMCB9KTtcclxuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICB0cnkgeyByZXR1cm4gKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvcmVhZHknLCB7IHRpbWVvdXQ6IDIwMDAgfSkpLm9rKCk7IH0gY2F0Y2ggeyByZXR1cm4gZmFsc2U7IH1cclxuICB9LCB7IHRpbWVvdXQ6IDEyMF8wMDAgfSkudG9CZSh0cnVlKTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gdmVyaWZ5U2lnbmFsQ29udHJhY3RzKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgZXhwZWN0ZWQ6IFJlY29yZDxzdHJpbmcsIHVua25vd24+KSB7XHJcbiAgY29uc3QgW2hhcmR3YXJlLCBmdW5jdGlvbnMsIG1lc3NhZ2VzLCBzaWduYWxzXSA9IGF3YWl0IFByb21pc2UuYWxsKFxyXG4gICAgWydoYXJkd2FyZS1ub2RlcycsICdmdW5jdGlvbnMnLCAnbWVzc2FnZXMnLCAnc2lnbmFscyddLm1hcChyZXNvdXJjZSA9PiBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsIHJlc291cmNlKSkpO1xyXG4gIGNvbnN0IG5vZGVzID0gbmV3IE1hcChoYXJkd2FyZS5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBmdW5jdGlvbnNCeUlkID0gbmV3IE1hcChmdW5jdGlvbnMubWFwKGl0ZW0gPT4gW2l0ZW0uaWQsIGl0ZW1dKSk7XHJcbiAgY29uc3QgbWVzc2FnZXNCeUlkID0gbmV3IE1hcChtZXNzYWdlcy5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBjb250cmFjdHM6IFJlY29yZDxzdHJpbmcsIHVua25vd24+ID0ge307XHJcbiAgZm9yIChjb25zdCBzaWduYWwgb2Ygc2lnbmFscykge1xyXG4gICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzQnlJZC5nZXQoc2lnbmFsLm1lc3NhZ2VfaWQpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UpLnRvQmVUcnV0aHkoKTtcclxuICAgIGNvbnN0IHJlZmVyZW5jZSA9IG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LnByb2R1Y2VyX3JlZjtcclxuICAgIGNvbnN0IGZuID0gZnVuY3Rpb25zQnlJZC5nZXQocmVmZXJlbmNlKTtcclxuICAgIGNvbnN0IG93bmVyID0gbm9kZXMuZ2V0KHJlZmVyZW5jZSkgfHwgKGZuICYmIG5vZGVzLmdldChmbi5oYXJkd2FyZV9ub2RlX2lkKSk7XHJcbiAgICBjb25zdCBwcm9kdWNlciA9IG93bmVyPy5kZXZpY2VfdHlwZSA9PT0gJ0dhdGV3YXknID8gJyRnYXRld2F5JyA6IChub2Rlcy5nZXQocmVmZXJlbmNlKSB8fCBmbik/Lm5hbWU7XHJcbiAgICBleHBlY3QocHJvZHVjZXIpLnRvQmVUcnV0aHkoKTtcclxuICAgIGNvbnN0IGtleSA9IFtwcm9kdWNlciwgbWVzc2FnZS5uYW1lLCBzaWduYWwubmFtZV0uam9pbignIDo6ICcpO1xyXG4gICAgZXhwZWN0KGNvbnRyYWN0c1trZXldLCAnU2VtYW50aWMgc2lnbmFsIGlkZW50aXR5IG11c3QgYmUgdW5pcXVlOiAnICsga2V5KS50b0JlVW5kZWZpbmVkKCk7XHJcbiAgICBjb250cmFjdHNba2V5XSA9IHtcclxuICAgICAgLi4uT2JqZWN0LmZyb21FbnRyaWVzKFsnc3RhcnRfYml0JywgJ2xlbmd0aF9iaXRzJywgJ2RhdGFfdHlwZScsICdmYWN0b3InLCAnb2Zmc2V0X3ZhbHVlJyxcclxuICAgICAgICAndW5pdCcsICdtaW5fdmFsdWUnLCAnbWF4X3ZhbHVlJywgJ2J5dGVfb3JkZXInXS5tYXAoZmllbGQgPT4gW2ZpZWxkLCBzaWduYWxbZmllbGRdID8/IG51bGxdKSksXHJcbiAgICAgIGVudW1fdmFsdWVzOiBzaWduYWwuZGF0YT8uZW51bV92YWx1ZXMgPz8gbnVsbCxcclxuICAgICAgc2VtYW50aWNfdHlwZTogc2lnbmFsLnNlbWFudGljPy5zZW1hbnRpY190eXBlID8/IG51bGwsXHJcbiAgICAgIGdlbmVyYXRpb25fcm9sZTogc2lnbmFsLmNvbmZpZ3VyYXRpb24/LmdlbmVyYXRpb25fcm9sZSA/PyBudWxsLFxyXG4gICAgfTtcclxuICB9XHJcbiAgZXhwZWN0KGNvbnRyYWN0cywgJ0V2ZXJ5IG9yaWdpbmFsIHNpZ25hbCBhbmQgaXRzIGV4cGxpY2l0IGVuY29kaW5nIG11c3Qgc3Vydml2ZSBnZW5lcmF0aW9uLicpLnRvRXF1YWwoZXhwZWN0ZWQpO1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiB2ZXJpZnlBcnRpZmFjdHMocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBtaW5pbXVtQ2Fub25pY2FsU2lnbmFsczogbnVtYmVyLCBpbnRlcm5hbENvbnRyb2xsZXI/OiBzdHJpbmcsXHJcbiAgZXhwZWN0ZWRQYXJhbWV0ZXJzPzogUmVjb3JkPHN0cmluZywgdW5rbm93bj4sIGV4cGVjdGVkTmF0aXZlUmF0ZXM/OiBSZWNvcmQ8c3RyaW5nLCBSZWNvcmQ8c3RyaW5nLCBudW1iZXI+Pikge1xyXG4gIC8vIFRoZSBjb21wbGV0ZWQgbW9kZWwgaXMgc3RhYmxlOyB0aGVzZSBpbmRlcGVuZGVudCByZWFkcyBuZWVkIG5vIHNlcmlhbCB3YWl0cy5cclxuICBjb25zdCBbd29ya2Zsb3csIGpvYkxpc3QsIHNuYXBzaG90cywgc2lnbmFscywgbWVzc2FnZXNdID0gYXdhaXQgUHJvbWlzZS5hbGwoW1xyXG4gICAgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5JyksXHJcbiAgICByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpLFxyXG4gICAgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvc25hcHNob3RzJyksXHJcbiAgICBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyksXHJcbiAgICBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdtZXNzYWdlcycpLFxyXG4gIF0pO1xyXG4gIGV4cGVjdChPYmplY3Qua2V5cyh3b3JrZmxvdy5zdGF0dXNlcykuc29ydCgpKS50b0VxdWFsKFsuLi5zdGVwc10uc29ydCgpKTtcclxuICBmb3IgKGNvbnN0IHN0ZXAgb2Ygc3RlcHMpIGV4cGVjdChkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXSksIGAke3N0ZXB9OiAke3dvcmtmbG93LnN0YXR1c2VzW3N0ZXBdfWApLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBqb2JzID0gam9iTGlzdC5qb2JzO1xyXG4gIGV4cGVjdChqb2JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KGpvYnNbMF0uc3RhdHVzKS50b0JlKCdjb21wbGV0ZWQnKTtcclxuICBjb25zdCBzbmFwc2hvdCA9IHNuYXBzaG90cy5zaW11bGF0aW9ucy5maW5kKChpdGVtOiB7IGpvYl9pZDogc3RyaW5nIH0pID0+IGl0ZW0uam9iX2lkID09PSBqb2JzWzBdLmlkKTtcclxuICBleHBlY3Qoc25hcHNob3QpLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBmdWxsID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvc2ltdWxhdGlvbi1zbmFwc2hvdHMvJHtzbmFwc2hvdC5pZH1gKTtcclxuICBpZiAoZXhwZWN0ZWRQYXJhbWV0ZXJzKSB7XHJcbiAgICBjb25zdCB7IGRhdGFfYml0cmF0ZSwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyLCAuLi5ydW50aW1lUGFyYW1ldGVycyB9ID0gZXhwZWN0ZWRQYXJhbWV0ZXJzO1xyXG4gICAgZXhwZWN0KGZ1bGwuY29uZmlndXJhdGlvbi5wYXJhbWV0ZXJzKS50b01hdGNoT2JqZWN0KHJ1bnRpbWVQYXJhbWV0ZXJzKTtcclxuICAgIGNvbnN0IGNhbkZkTmV0d29ya3MgPSBmdWxsLmNvbmZpZ3VyYXRpb24ubmV0d29ya3MuZmlsdGVyKChuZXR3b3JrOiBhbnkpID0+IG5ldHdvcmsudGVjaG5vbG9neSA9PT0gJ2Nhbl9mZCcpO1xyXG4gICAgZXhwZWN0KGNhbkZkTmV0d29ya3MubGVuZ3RoLCAnVGhlIGVkaXRlZCBDQU4tRkQgY29uZmlndXJhdGlvbiBtdXN0IHJlYWNoIGEgcGh5c2ljYWwgc2ltdWxhdGlvbiBuZXR3b3JrLicpLnRvQmVHcmVhdGVyVGhhbigwKTtcclxuICAgIGZvciAoY29uc3QgbmV0d29yayBvZiBjYW5GZE5ldHdvcmtzKSBleHBlY3QobmV0d29yaykudG9NYXRjaE9iamVjdCh7IGRhdGFfYml0cmF0ZSwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyIH0pO1xyXG4gIH1cclxuICBpZiAoZXhwZWN0ZWROYXRpdmVSYXRlcykge1xyXG4gICAgZm9yIChjb25zdCBbdGVjaG5vbG9neSwgcmF0ZXNdIG9mIE9iamVjdC5lbnRyaWVzKGV4cGVjdGVkTmF0aXZlUmF0ZXMpKSB7XHJcbiAgICAgIGNvbnN0IG5ldHdvcmtzID0gZnVsbC5jb25maWd1cmF0aW9uLm5ldHdvcmtzLmZpbHRlcigobmV0d29yazogYW55KSA9PiBuZXR3b3JrLnRlY2hub2xvZ3kgPT09IHRlY2hub2xvZ3kpO1xyXG4gICAgICBleHBlY3QobmV0d29ya3MubGVuZ3RoLCBgU2F2ZWQgJHt0ZWNobm9sb2d5fSByYXRlcyBtdXN0IHJlYWNoIHRoZSBmcm96ZW4gc2ltdWxhdGlvbi5gKS50b0JlR3JlYXRlclRoYW4oMCk7XHJcbiAgICAgIGZvciAoY29uc3QgbmV0d29yayBvZiBuZXR3b3JrcykgZXhwZWN0KG5ldHdvcmspLnRvTWF0Y2hPYmplY3QocmF0ZXMpO1xyXG4gICAgfVxyXG4gIH1cclxuICBjb25zdCBhc3Nlc3NtZW50ID0gZnVsbC5yZXN1bHQuYXNzZXNzbWVudDtcclxuICBleHBlY3QoYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS5zY29wZV9tb2RlKS50b0JlKCdBTEwnKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS5jb21wbGV0ZSkudG9CZSh0cnVlKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5jb25mb3JtYW5jZSkudG9CZSgnUEFTUycpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LmZhaWxlZF9yb3V0ZV9jb3VudCkudG9CZSgwKTtcclxuICBleHBlY3Qoc2lnbmFscy5sZW5ndGgsICdUaGUgZnVsbCBjYW5vbmljYWwgc2lnbmFsIGludmVudG9yeSBtdXN0IHN1cnZpdmUgZ2VuZXJhdGlvbi4nKS50b0JlR3JlYXRlclRoYW5PckVxdWFsKG1pbmltdW1DYW5vbmljYWxTaWduYWxzKTtcclxuICBjb25zdCBleGNsdWRlZCA9IGFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UudHJhbnNwb3J0X2V4Y2x1c2lvbnMgPz8gW107XHJcbiAgZm9yIChjb25zdCBpdGVtIG9mIGV4Y2x1ZGVkKSB7XHJcbiAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXMuZmluZChyb3cgPT4gcm93LmlkID09PSBpdGVtLm1lc3NhZ2VfaWQpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UsIGBFeGNsdWRlZCBtZXNzYWdlICR7aXRlbS5tZXNzYWdlX2lkfSBtdXN0IGV4aXN0LmApLnRvQmVUcnV0aHkoKTtcclxuICAgIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24ucm91dGluZy5lbmFibGVkKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IGNvbnRyYWN0ID0gbWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3Q7XHJcbiAgICBleHBlY3QoY29udHJhY3QuY29uc3VtZXJfcmVmcykudG9FcXVhbChbXSk7XHJcbiAgICBleHBlY3QoaXRlbS5yZWFzb25fY29kZSkudG9CZShjb250cmFjdC5yb2xlID09PSAnSU5URVJOQUxfU1RBVEUnXHJcbiAgICAgID8gJ0lOVEVSTkFMX1NUQVRFX05PVF9ST1VURUQnIDogJ0VYUExJQ0lUX0ZVTkNUSU9OX09VVFBVVF9OT1RfUk9VVEVEJyk7XHJcbiAgfVxyXG4gIGlmIChpbnRlcm5hbENvbnRyb2xsZXIpIHtcclxuICAgIGNvbnN0IG5vZGVzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICAgIGNvbnN0IGNvbnRyb2xsZXIgPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSBpbnRlcm5hbENvbnRyb2xsZXIpO1xyXG4gICAgZXhwZWN0KGV4Y2x1ZGVkLmxlbmd0aCkudG9CZUdyZWF0ZXJUaGFuKDApO1xyXG4gICAgZm9yIChjb25zdCBpdGVtIG9mIGV4Y2x1ZGVkKSB7XHJcbiAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKHJvdyA9PiByb3cuaWQgPT09IGl0ZW0ubWVzc2FnZV9pZCk7XHJcbiAgICAgIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdCkudG9NYXRjaE9iamVjdCh7IHJvbGU6ICdJTlRFUk5BTF9TVEFURScsIHNjb3BlOiAnSU5URVJOQUwnLCBwcm9kdWNlcl9yZWY6IGNvbnRyb2xsZXIuaWQsIGNvbnN1bWVyX3JlZnM6IFtdIH0pO1xyXG4gICAgfVxyXG4gIH1cclxuICBjb25zdCBleGNsdWRlZFNpZ25hbHMgPSBuZXcgU2V0KGV4Y2x1ZGVkLmZsYXRNYXAoKGl0ZW06IHsgc2lnbmFsX2lkczogc3RyaW5nW10gfSkgPT4gaXRlbS5zaWduYWxfaWRzKSk7XHJcbiAgZXhwZWN0KGFzc2Vzc21lbnQub2JzZXJ2ZWRfc2lnbmFsX2NvdW50LCAnQUxMIG11c3Qgb2JzZXJ2ZSBldmVyeSBjYW5vbmljYWwgc2lnbmFsIHdpdGggYSB0cmFuc3BvcnQgb2JsaWdhdGlvbi4nKS50b0JlKHNpZ25hbHMubGVuZ3RoIC0gZXhjbHVkZWRTaWduYWxzLnNpemUpO1xyXG4gIGZvciAoY29uc3Qga2V5IG9mIFsnbWlzc2luZ19vYnNlcnZlZF9zaWduYWxfaWRzJywgJ21pc3Npbmdfb2JzZXJ2ZWRfcm91dGVfaWRzJywgJ21pc3Npbmdfb2JzZXJ2ZWRfbmV0d29ya19pZHMnXSkgZXhwZWN0KGFzc2Vzc21lbnRba2V5XSkudG9FcXVhbChbXSk7XHJcbiAgY29uc3QgdHJhY2UgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9zaW11bGF0aW9ucy8ke2pvYnNbMF0uaWR9L3RyYWNlLXdpbmRvdz9saW1pdD0xMGApO1xyXG4gIGV4cGVjdCh0cmFjZS5jb3VudCkudG9CZUdyZWF0ZXJUaGFuKDApO1xyXG4gIGV4cGVjdCh0cmFjZS5ldmVudHMuc29tZSgoaXRlbTogeyBzaWduYWxzPzogdW5rbm93bltdIH0pID0+IGl0ZW0uc2lnbmFscyAmJiBPYmplY3Qua2V5cyhpdGVtLnNpZ25hbHMpLmxlbmd0aCkpLnRvQmVUcnV0aHkoKTtcclxuICByZXR1cm4geyB3b3JrZmxvdywgam9iOiBqb2JzWzBdLmlkLCBzbmFwc2hvdDogc25hcHNob3QuaWQsIHRyYWNlX2V2ZW50czogZnVsbC5yZXN1bHQudHJhY2UuZXZlbnRzLCBhc3Nlc3NtZW50LCBwYXJhbWV0ZXJfcHJvb2Y6IGV4cGVjdGVkUGFyYW1ldGVycyA/IHtcclxuICAgIHNhdmVkOiBleHBlY3RlZFBhcmFtZXRlcnMsIHNpbXVsYXRpb25fcmF0ZXM6IGZ1bGwuY29uZmlndXJhdGlvbi5uZXR3b3Jrcy5tYXAoKG5ldHdvcms6IGFueSkgPT4gKHtcclxuICAgICAgdGVjaG5vbG9neTogbmV0d29yay50ZWNobm9sb2d5LCBiaXRyYXRlOiBuZXR3b3JrLmJpdHJhdGUsXHJcbiAgICAgIGFyYml0cmF0aW9uX2JpdHJhdGU6IG5ldHdvcmsuYXJiaXRyYXRpb25fYml0cmF0ZSwgZGF0YV9iaXRyYXRlOiBuZXR3b3JrLmRhdGFfYml0cmF0ZSxcclxuICAgICAgaGFyZHdhcmVfZXZpZGVuY2U6IG5ldHdvcmsuaGFyZHdhcmVfZXZpZGVuY2UsXHJcbiAgICB9KSksXHJcbiAgfSA6IHVuZGVmaW5lZCB9O1xyXG59XHJcblxyXG50eXBlIFBhcmFtZXRlclJldHVyblNjZW5hcmlvID0ge1xyXG4gIHRlY2hub2xvZ3k6IHN0cmluZztcclxuICBmaWVsZHM6IFJlY29yZDxzdHJpbmcsIHN0cmluZz47XHJcbiAgbmF0aXZlOiBSZWNvcmQ8c3RyaW5nLCBudW1iZXI+O1xyXG4gIGVkaXRGaWVsZHM/OiBzdHJpbmdbXTtcclxufTtcclxuXHJcbi8vIEV4ZXJjaXNlIHRoZSB1c2VyJ3MgZGV0b3VyLCBpbmNsdWRpbmcgcmVwZWF0ZWQgc2F2ZXMgaW4gYW4gZXhpc3RpbmcgcnVuLlxyXG4vLyBSZWFkcyBpbnNwZWN0IHJlYWwgcGVyc2lzdGVkIHN0YXRlOyB3cml0ZXMgYW5kIHJldHVybiBuYXZpZ2F0aW9uIHVzZSB0aGUgVUkuXHJcbmFzeW5jIGZ1bmN0aW9uIHJlcGVhdFBhcmFtZXRlclJldHVybihwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIHByb3Bvc2FsSWQ6IHN0cmluZyxcclxuICBzY2VuYXJpb3M6IFBhcmFtZXRlclJldHVyblNjZW5hcmlvW10sIHNlZWRzID0gWzQxLCA0MywgNDJdKSB7XHJcbiAgY29uc3QgYmVmb3JlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgY29uc3QgaWRlbnRpdHkgPSBiZWZvcmUuY29udGV4dC5hZ2VudF9leGVjdXRpb247XHJcbiAgZXhwZWN0KGlkZW50aXR5LnJ1bl9pZCkudG9CZVRydXRoeSgpO1xyXG4gIGNvbnN0IG5vZGVJZHMgPSAoYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKSkubWFwKGl0ZW0gPT4gaXRlbS5pZCkuc29ydCgpO1xyXG4gIGNvbnN0IHN0YXJ0czogdW5rbm93bltdID0gW107XHJcbiAgY29uc3QgdHJhY2tTdGFydHMgPSAocmVxdWVzdDogaW1wb3J0KCdwbGF5d3JpZ2h0L3Rlc3QnKS5SZXF1ZXN0KSA9PiB7XHJcbiAgICBpZiAocmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JykgJiYgcmVxdWVzdC5tZXRob2QoKSA9PT0gJ1BPU1QnXHJcbiAgICAgICYmIHJlcXVlc3QucG9zdERhdGFKU09OKCk/LndpemFyZF9jb21tYW5kPy5hY3Rpb24gPT09ICdTVEFSVCcpIHN0YXJ0cy5wdXNoKHJlcXVlc3QucG9zdERhdGFKU09OKCkpO1xyXG4gIH07XHJcbiAgY29uc3QgZXZpZGVuY2U6IHVua25vd25bXSA9IFtdO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3QnLCB0cmFja1N0YXJ0cyk7XHJcbiAgdHJ5IHtcclxuICAgIGNvbnN0IHdpemFyZCA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7bmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJ30pO1xyXG4gICAgaWYgKGF3YWl0IHdpemFyZC5pc1Zpc2libGUoKSkge1xyXG4gICAgICAvLyBBIGNhcHR1cmVkIEFQSSBTVEFSVCBkb2VzIG5vdCBhY3RpdmF0ZSBhIGJyb3dzZXIgd2l6YXJkIHNlc3Npb24uIEVudGVyXHJcbiAgICAgIC8vIHBhcmFtZXRlcnMgdGhyb3VnaCB0aGUgYWN0dWFsIHdvcmtmbG93IGNhcmQsIGp1c3QgYXMgYSB1c2VyIGRvZXMuXHJcbiAgICAgIGF3YWl0IHdpemFyZC5sb2NhdG9yKCcuYWdlbnQtd2l6YXJkLXByb2dyZXNzLWNhcmRbaHJlZio9XCJtb2RlPXBhcmFtZXRlcnNcIl0nKS5jbGljaygpO1xyXG4gICAgICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHtuYW1lOiAnWnVyw7xjayB6dW0gQXVmdHJhZycsIGV4YWN0OiB0cnVlfSkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgICB9XHJcbiAgICBmb3IgKGNvbnN0IFtjeWNsZSwgc2VlZF0gb2Ygc2VlZHMuZW50cmllcygpKSB7XHJcbiAgICAgIGZvciAoY29uc3Qgc2NlbmFyaW8gb2Ygc2NlbmFyaW9zKSB7XHJcbiAgICAgICAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7ZW5jb2RlVVJJQ29tcG9uZW50KHByb2plY3QpfSZ0ZWNobm9sb2d5PSR7c2NlbmFyaW8udGVjaG5vbG9neX0mcHJvcG9zYWw9JHtwcm9wb3NhbElkfSNwYXJhbWV0ZXItZmluZGluZ3NgKTtcclxuICAgICAgICBhd2FpdCBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2UpO1xyXG4gICAgICAgIGNvbnN0IGNvbW1vbiA9IHBhZ2UubG9jYXRvcignLnBhcmFtZXRlci1ncm91cC1jb21tb24nKTtcclxuICAgICAgICBmb3IgKGNvbnN0IFtmaWVsZCwgdmFsdWVdIG9mIE9iamVjdC5lbnRyaWVzKHNjZW5hcmlvLmZpZWxkcykpIHtcclxuICAgICAgICAgIGNvbnN0IGlucHV0ID0gcGFnZS5sb2NhdG9yKGAjJHtmaWVsZH1gKTtcclxuICAgICAgICAgIGNvbnN0IGRldGFpbHMgPSBpbnB1dC5sb2NhdG9yKCd4cGF0aD1hbmNlc3Rvcjo6ZGV0YWlsc1sxXScpO1xyXG4gICAgICAgICAgaWYgKGF3YWl0IGRldGFpbHMuY291bnQoKSAmJiBhd2FpdCBkZXRhaWxzLmdldEF0dHJpYnV0ZSgnb3BlbicpID09PSBudWxsKVxyXG4gICAgICAgICAgICBhd2FpdCBkZXRhaWxzLmxvY2F0b3IoJzpzY29wZSA+IHN1bW1hcnknKS5jbGljaygpO1xyXG4gICAgICAgICAgaWYgKHNjZW5hcmlvLmVkaXRGaWVsZHM/LmluY2x1ZGVzKGZpZWxkKSkgYXdhaXQgaW5wdXQuZmlsbCh2YWx1ZSk7XHJcbiAgICAgICAgICBlbHNlIGF3YWl0IGV4cGVjdChpbnB1dCkudG9IYXZlVmFsdWUodmFsdWUpO1xyXG4gICAgICAgIH1cclxuICAgICAgICBhd2FpdCBjb21tb24ubG9jYXRvcignI3NlZWQnKS5maWxsKFN0cmluZyhzZWVkKSk7XHJcbiAgICAgICAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHtuYW1lOiAnUGFyYW1ldGVyIHNwZWljaGVybiDihpInLCBleGFjdDogdHJ1ZX0pLmNsaWNrKCk7XHJcbiAgICAgICAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdUZWNobm9sb2dpZS0gdW5kIFRpbWluZy1QYXJhbWV0ZXIgZ2VzcGVpY2hlcnQuJykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgICAgICAgY29uc3Qgc2F2ZWQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyk7XHJcbiAgICAgICAgZXhwZWN0KHNhdmVkLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgICAgICAgZXhwZWN0KHNhdmVkLnBhcmFtZXRlcnMucGFyYW1ldGVyX3Byb3ZlbmFuY2UuZHVyYXRpb25fcykudG9FcXVhbCh7c291cmNlOidURUNITk9MT0dZX0RFRkFVTFQnLHZhbHVlOjF9KTtcclxuICAgICAgICBjb25zdCBzY29wZWQgPSBzYXZlZC5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfcGFyYW1ldGVyc1tzY2VuYXJpby50ZWNobm9sb2d5XTtcclxuICAgICAgICBjb25zdCBhc3N1bWVkID0gc2F2ZWQucGFyYW1ldGVycy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucz8uW3NjZW5hcmlvLnRlY2hub2xvZ3ldO1xyXG4gICAgICAgIGV4cGVjdChzY29wZWQudmFsdWVzLnNlZWQpLnRvQmUoc2VlZCk7XHJcbiAgICAgICAgY29uc3QgbmF0aXZlVmFsdWVzID0gey4uLmFzc3VtZWQ/LnZhbHVlcywgLi4uc2NvcGVkLnZhbHVlc307XHJcbiAgICAgICAgZXhwZWN0KG5hdGl2ZVZhbHVlcykudG9NYXRjaE9iamVjdChzY2VuYXJpby5uYXRpdmUpO1xyXG4gICAgICAgIGZvciAoY29uc3QgW2tleSwgdmFsdWVdIG9mIE9iamVjdC5lbnRyaWVzKHNjZW5hcmlvLm5hdGl2ZSkpIHtcclxuICAgICAgICAgIGNvbnN0IGNvbmZpcm1lZCA9IE9iamVjdC5oYXNPd24oc2NvcGVkLnZhbHVlcywga2V5KTtcclxuICAgICAgICAgIGV4cGVjdCgoY29uZmlybWVkID8gc2NvcGVkIDogYXNzdW1lZCkucHJvdmVuYW5jZVtrZXldKS50b01hdGNoT2JqZWN0KGNvbmZpcm1lZFxyXG4gICAgICAgICAgICA/IHtzb3VyY2U6ICdVU0VSX0NPTkZJUk1FRCcsIHN0YXR1czogJ0NPTkZJUk1FRCcsIHZhbHVlfVxyXG4gICAgICAgICAgICA6IHtzb3VyY2U6ICdOSVNfU0lNVUxBVElPTl9BU1NVTVBUSU9OJywgc3RhdHVzOiAnQVNTVU1FRCcsIHRlY2hub2xvZ3k6IHNjZW5hcmlvLnRlY2hub2xvZ3ksIGhhcmR3YXJlX2V2aWRlbmNlOiBmYWxzZSwgdmFsdWV9KTtcclxuICAgICAgICB9XHJcbiAgICAgICAgY29uc3QgdXNlclZhbHVlcyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMvdXNlci1kZWZpbmVkLXZhbHVlcycpO1xyXG4gICAgICAgIGV4cGVjdCh1c2VyVmFsdWVzLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgICAgICAgZXhwZWN0KHVzZXJWYWx1ZXMudmFsdWVfb3JpZ2luKS50b0JlKCdVU0VSX0RFRklORURfVkFMVUUnKTtcclxuICAgICAgICBleHBlY3QodXNlclZhbHVlcy5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfZGVmYXVsdHMpLnRvQmVVbmRlZmluZWQoKTtcclxuICAgICAgICBleHBlY3QodXNlclZhbHVlcy5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfcGFyYW1ldGVyc1tzY2VuYXJpby50ZWNobm9sb2d5XSkudG9FcXVhbChzY29wZWQpO1xyXG4gICAgICAgIGNvbnN0IHN0YWxlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7cHJvcG9zYWxJZH0/dmlldz1zdGF0dXNgKTtcclxuICAgICAgICBleHBlY3Qoc3RhbGUuZGF0YS5zdGF0dXMpLnRvQmUoJ09VVERBVEVEJyk7XHJcbiAgICAgICAgY29uc3QgY2Fub25pY2FsSWRzID0gc3RhbGUuZGF0YS5jYW5vbmljYWxfaWRzO1xyXG4gICAgICAgIC8vIE9ic2VydmUgb25seSB0aGUgbmV3IGRvY3VtZW50J3MgcmVhbCBVSSByZXZpZXc6IGFuIG9sZCByZXZpZXcgY2FuXHJcbiAgICAgICAgLy8gZmluaXNoIGR1cmluZyByZWxvYWQsIGFmdGVyIGl0cyByZXNwb25zZSBib2R5IGhhcyBiZWVuIGRpc2NhcmRlZC5cclxuICAgICAgICBsZXQgcmVsb2FkZWREb2N1bWVudEF0ID0gSW5maW5pdHk7XHJcbiAgICAgICAgY29uc3QgbWFya1JlbG9hZGVkRG9jdW1lbnQgPSAoZnJhbWU6IGltcG9ydCgncGxheXdyaWdodC90ZXN0JykuRnJhbWUpID0+IHtcclxuICAgICAgICAgIGlmIChmcmFtZSA9PT0gcGFnZS5tYWluRnJhbWUoKSkgcmVsb2FkZWREb2N1bWVudEF0ID0gRGF0ZS5ub3coKTtcclxuICAgICAgICB9O1xyXG4gICAgICAgIHBhZ2Uub24oJ2ZyYW1lbmF2aWdhdGVkJywgbWFya1JlbG9hZGVkRG9jdW1lbnQpO1xyXG4gICAgICAgIGNvbnN0IHJldmlld1Jlc3BvbnNlID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4ge1xyXG4gICAgICAgICAgY29uc3QgdXJsID0gbmV3IFVSTChyZXNwb25zZS51cmwoKSk7XHJcbiAgICAgICAgICByZXR1cm4gdXJsLnBhdGhuYW1lID09PSAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzL3JldmlldydcclxuICAgICAgICAgICAgJiYgdXJsLnNlYXJjaFBhcmFtcy5nZXQoJ3Byb3Bvc2FsJykgPT09IHByb3Bvc2FsSWRcclxuICAgICAgICAgICAgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnR0VUJ1xyXG4gICAgICAgICAgICAmJiByZXNwb25zZS5yZXF1ZXN0KCkuaGVhZGVycygpWyd4LXByb2plY3QtaWQnXSA9PT0gcHJvamVjdFxyXG4gICAgICAgICAgICAmJiByZXNwb25zZS5yZXF1ZXN0KCkudGltaW5nKCkuc3RhcnRUaW1lID49IHJlbG9hZGVkRG9jdW1lbnRBdDtcclxuICAgICAgICB9LCB7dGltZW91dDogNjBfMDAwfSk7XHJcbiAgICAgICAgdHJ5IHtcclxuICAgICAgICAgIGF3YWl0IHBhZ2UucmVsb2FkKCk7XHJcbiAgICAgICAgfSBmaW5hbGx5IHtcclxuICAgICAgICAgIHBhZ2Uub2ZmKCdmcmFtZW5hdmlnYXRlZCcsIG1hcmtSZWxvYWRlZERvY3VtZW50KTtcclxuICAgICAgICB9XHJcbiAgICAgICAgY29uc3QgYWN0dWFsUmV2aWV3UmVzcG9uc2UgPSBhd2FpdCByZXZpZXdSZXNwb25zZTtcclxuICAgICAgICBleHBlY3QoYWN0dWFsUmV2aWV3UmVzcG9uc2Uub2soKSwgYXdhaXQgYWN0dWFsUmV2aWV3UmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gICAgICAgIGNvbnN0IHJldmlldyA9IGF3YWl0IGFjdHVhbFJldmlld1Jlc3BvbnNlLmpzb24oKTtcclxuICAgICAgICBleHBlY3QocmV2aWV3LmVkaXRfdG9rZW4pLnRvQmUoc2F2ZWQuZWRpdF90b2tlbik7XHJcbiAgICAgICAgYXdhaXQgZXhwZWN0KGNvbW1vbi5sb2NhdG9yKCcjc2VlZCcpKS50b0hhdmVWYWx1ZShTdHJpbmcoc2VlZCkpO1xyXG4gICAgICAgIGZvciAoY29uc3QgW2ZpZWxkLCB2YWx1ZV0gb2YgT2JqZWN0LmVudHJpZXMoc2NlbmFyaW8uZmllbGRzKSkge1xyXG4gICAgICAgICAgY29uc3QgaW5wdXQgPSBwYWdlLmxvY2F0b3IoYCMke2ZpZWxkfWApO1xyXG4gICAgICAgICAgY29uc3QgZGV0YWlscyA9IGlucHV0LmxvY2F0b3IoJ3hwYXRoPWFuY2VzdG9yOjpkZXRhaWxzWzFdJyk7XHJcbiAgICAgICAgICBpZiAoYXdhaXQgZGV0YWlscy5jb3VudCgpICYmIGF3YWl0IGRldGFpbHMuZ2V0QXR0cmlidXRlKCdvcGVuJykgPT09IG51bGwpXHJcbiAgICAgICAgICAgIGF3YWl0IGRldGFpbHMubG9jYXRvcignOnNjb3BlID4gc3VtbWFyeScpLmNsaWNrKCk7XHJcbiAgICAgICAgICBhd2FpdCBleHBlY3QoaW5wdXQpLnRvSGF2ZVZhbHVlKHZhbHVlKTtcclxuICAgICAgICB9XHJcbiAgICAgICAgY29uc3Qgc2VsZWN0ZWRGaW5kaW5ncyA9IHJldmlldy5maW5kaW5ncy5maWx0ZXIoKGZpbmRpbmc6IHt0ZWNobm9sb2d5OnN0cmluZ30pID0+IGZpbmRpbmcudGVjaG5vbG9neSA9PT0gc2NlbmFyaW8udGVjaG5vbG9neSk7XHJcbiAgICAgICAgaWYgKHNlbGVjdGVkRmluZGluZ3MubGVuZ3RoICYmIHNlbGVjdGVkRmluZGluZ3MuZXZlcnkoKGZpbmRpbmc6IHtjb2RlOnN0cmluZ30pID0+IGZpbmRpbmcuY29kZSA9PT0gJ0NBUEFDSVRZX0RFVklDRV9FVklERU5DRV9NSVNTSU5HJykpIHtcclxuICAgICAgICAgIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNwYXJhbWV0ZXItZmluZGluZ3MgZm9ybScpKS50b0hhdmVDb3VudCgwKTtcclxuICAgICAgICAgIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNwYXJhbWV0ZXItZmluZGluZ3MgW3JvbGU9XCJhbGVydFwiXScpKS50b0hhdmVDb3VudCgwKTtcclxuICAgICAgICAgIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNwYXJhbWV0ZXItZmluZGluZ3MnKSkudG9Db250YWluVGV4dCgna2VpbiBTaW11bGF0aW9uc2Jsb2NrZXInKTtcclxuICAgICAgICB9XHJcbiAgICAgICAgLy8gS2VlcCB0aGUgZXhpc3RpbmcgZGVsYXllZC1yZXN0b3JlIHJlZ3Jlc3Npb24sIHVzaW5nIHJlYWwgcmVzcG9uc2VzLlxyXG4gICAgICAgIGxldCByZXN1bWVSZXN0b3JlITogKCkgPT4gdm9pZDtcclxuICAgICAgICBjb25zdCByZXN0b3JlUGF1c2UgPSBuZXcgUHJvbWlzZTx2b2lkPihyZXNvbHZlID0+IHsgcmVzdW1lUmVzdG9yZSA9IHJlc29sdmU7IH0pO1xyXG4gICAgICAgIGNvbnN0IGRlbGF5UmVzdG9yZSA9IGFzeW5jIChyb3V0ZTogaW1wb3J0KCdwbGF5d3JpZ2h0L3Rlc3QnKS5Sb3V0ZSkgPT4ge1xyXG4gICAgICAgICAgYXdhaXQgcmVzdG9yZVBhdXNlOyBhd2FpdCByb3V0ZS5jb250aW51ZSgpO1xyXG4gICAgICAgIH07XHJcbiAgICAgICAgY29uc3QgZGVsYXllZCA9IGN5Y2xlID09PSAwICYmIHNjZW5hcmlvID09PSBzY2VuYXJpb3NbMF07XHJcbiAgICAgICAgaWYgKGRlbGF5ZWQpIGF3YWl0IHBhZ2Uucm91dGUoJyoqL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknLCBkZWxheVJlc3RvcmUpO1xyXG4gICAgICAgIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7bmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJ30pO1xyXG4gICAgICAgIHRyeSB7XHJcbiAgICAgICAgICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywge25hbWU6ICdadXLDvGNrIHp1bSBBdWZ0cmFnJywgZXhhY3Q6IHRydWV9KS5jbGljaygpO1xyXG4gICAgICAgICAgaWYgKGRlbGF5ZWQpIHtcclxuICAgICAgICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHtuYW1lOiAnR2VzcGVpY2hlcnRlbiBBdWZ0cmFnIHdpZWRlcmhlcnN0ZWxsZW4nfSkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgICAgICAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cpLm5vdC50b0NvbnRhaW5UZXh0KCdQcm9qZWt0bmFtZTogU2Nocml0dCAxJyk7XHJcbiAgICAgICAgICB9XHJcbiAgICAgICAgfSBmaW5hbGx5IHtcclxuICAgICAgICAgIHJlc3VtZVJlc3RvcmUoKTtcclxuICAgICAgICAgIGlmIChkZWxheWVkKSBhd2FpdCBwYWdlLnVucm91dGVBbGwoe2JlaGF2aW9yOiAnd2FpdCd9KTtcclxuICAgICAgICB9XHJcbiAgICAgICAgLy8gTWF0Y2ggdGhlIGV4aXN0aW5nIHByb3Bvc2FsLXJldmlldyByZWFkaW5lc3MgYnVkZ2V0IGJlbG93LiBUaGUgbmV3XHJcbiAgICAgICAgLy8gcmV0dXJuIGFzc2VydGlvbiBtdXN0IG5vdCBpbXBvc2UgYSBzaG9ydGVyIGxpbWl0IG9uIHRoZSBsYXJnZSBtb2RlbC5cclxuICAgICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywge25hbWU6ICdFbmdpbmVlcmluZy1Wb3JzY2hsYWcnfSkpXHJcbiAgICAgICAgICAudG9Db250YWluVGV4dCgnR2VwcsO8ZnQgwrcgRnJlaWdhYmUgb2ZmZW4nLCB7dGltZW91dDogNjBfMDAwfSk7XHJcbiAgICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZykudG9Db250YWluVGV4dCgnU3RhdHVzw7xiZXJzaWNodDogU2Nocml0dCA1IHZvbiA1Jyk7XHJcbiAgICAgICAgY29uc3QgcmVzdG9yZWQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgICBleHBlY3QocmVzdG9yZWQucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcclxuICAgICAgICBleHBlY3QocmVzdG9yZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24ucnVuX2lkKS50b0JlKGlkZW50aXR5LnJ1bl9pZCk7XHJcbiAgICAgICAgZXhwZWN0KHJlc3RvcmVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnJlcXVlc3RfcmV2aXNpb24pLnRvQmUoaWRlbnRpdHkucmVxdWVzdF9yZXZpc2lvbik7XHJcbiAgICAgICAgZXhwZWN0KHJlc3RvcmVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnN0YXRlKS50b0JlKCdSRVZJRVdfUkVRVUlSRUQnKTtcclxuICAgICAgICBleHBlY3QocmVzdG9yZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24uc3RlcCkudG9CZShpZGVudGl0eS5zdGVwKTtcclxuICAgICAgICBmb3IgKGNvbnN0IHN0ZXAgb2Ygc3RlcHMpIGlmIChkb25lLmhhcyhiZWZvcmUuc3RhdHVzZXNbc3RlcF0pKVxyXG4gICAgICAgICAgZXhwZWN0KGRvbmUuaGFzKHJlc3RvcmVkLnN0YXR1c2VzW3N0ZXBdKSwgYFJldHVybmluZyBtdXN0IHByZXNlcnZlIGNvbXBsZXRlZCBzdGFnZSAke3N0ZXB9LmApLnRvQmUodHJ1ZSk7XHJcbiAgICAgICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XHJcbiAgICAgICAgZXhwZWN0KGNvbnZlcnNhdGlvbi5kYXRhLmFjdGl2ZV9wcm9wb3NhbCkudG9CZShwcm9wb3NhbElkKTtcclxuICAgICAgICBjb25zdCBmcmVzaCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3Byb3Bvc2FsSWR9P3ZpZXc9c3RhdHVzYCk7XHJcbiAgICAgICAgZXhwZWN0KGZyZXNoLmRhdGEuc3RhdHVzKS50b0JlKCdWQUxJREFURUQnKTtcclxuICAgICAgICBleHBlY3QoZnJlc2guZGF0YS5jYW5vbmljYWxfaWRzKS50b0VxdWFsKGNhbm9uaWNhbElkcyk7XHJcbiAgICAgICAgZXhwZWN0KChhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpKS5tYXAoaXRlbSA9PiBpdGVtLmlkKS5zb3J0KCkpLnRvRXF1YWwobm9kZUlkcyk7XHJcbiAgICAgICAgY29uc3QgYWZ0ZXIgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyk7XHJcbiAgICAgICAgZXhwZWN0KGFmdGVyLnBhcmFtZXRlcnMpLnRvRXF1YWwoc2F2ZWQucGFyYW1ldGVycyk7XHJcbiAgICAgICAgZXhwZWN0KHN0YXJ0cywgJ1JldHVybmluZyBmcm9tIHBhcmFtZXRlcnMgbXVzdCBuZXZlciByZXN0YXJ0IHRoaXMgcnVuLicpLnRvRXF1YWwoW10pO1xyXG4gICAgICAgIGV2aWRlbmNlLnB1c2goe2N5Y2xlOiBjeWNsZSArIDEsIHRlY2hub2xvZ3k6IHNjZW5hcmlvLnRlY2hub2xvZ3ksIHNlZWQsIHJ1bl9pZDogaWRlbnRpdHkucnVuX2lkLFxyXG4gICAgICAgICAgcHJvcG9zYWxfaWQ6IHByb3Bvc2FsSWQsIHNhdmVkX3ZhbHVlczogc2NvcGVkLCBhc3N1bXB0aW9uczogYXNzdW1lZCxcclxuICAgICAgICAgIHJlc3RvcmVkX3N0YXR1czogZnJlc2guZGF0YS5zdGF0dXMsIGNhbm9uaWNhbF9pZHM6IGNhbm9uaWNhbElkc30pO1xyXG4gICAgICB9XHJcbiAgICB9XHJcbiAgfSBmaW5hbGx5IHtcclxuICAgIHBhZ2Uub2ZmKCdyZXF1ZXN0JywgdHJhY2tTdGFydHMpO1xyXG4gICAgYXdhaXQgdGVzdC5pbmZvKCkuYXR0YWNoKCdyZXBlYXRlZC1wYXJhbWV0ZXItcmV0dXJuJywge2JvZHk6IEpTT04uc3RyaW5naWZ5KGV2aWRlbmNlKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJ30pO1xyXG4gIH1cclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcmVzdGFydDogYm9vbGVhbiwgZXhwZWN0ZWRIYXJkd2FyZTogc3RyaW5nW10gPSBbXSwgY3Jhc2hTaW11bGF0aW9uID0gZmFsc2UsXHJcbiAgZXhwZWN0ZWRTaWduYWxzPzogUmVjb3JkPHN0cmluZywgdW5rbm93bj4sIGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQ/OiAoKSA9PiBQcm9taXNlPHZvaWQ+LCBzdG9wT25FdmlkZW5jZUJsb2NrID0gZmFsc2UsXHJcbiAgYmVmb3JlUHJvcG9zYWxSZXZpZXc/OiAocHJvcG9zYWxJZDogc3RyaW5nLCBwcm9wb3NhbFR5cGU6IHN0cmluZykgPT4gUHJvbWlzZTx2b2lkIHwgJ1NUT1BfQUZURVJfUkVWSUVXJz4pIHtcclxuICBsZXQgcmV2aWV3Q291bnQgPSAwO1xyXG4gIGxldCBydW5JZDogc3RyaW5nIHwgdW5kZWZpbmVkO1xyXG4gIGNvbnN0IHJldmlld2VkID0gbmV3IFNldDxzdHJpbmc+KCk7XHJcbiAgbGV0IHJlc3RhcnRlZEpvYklkOiBzdHJpbmcgfCB1bmRlZmluZWQ7XHJcbiAgbGV0IHdhdGNoZG9nID0gbmV3IFdpemFyZFByb2dyZXNzV2F0Y2hkb2cocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gIGZvciAobGV0IGNoZWNrcG9pbnQgPSAwOyBjaGVja3BvaW50IDwgMTY7IGNoZWNrcG9pbnQrKykge1xyXG4gICAgbGV0IHdvcmtmbG93OiBhbnk7XHJcbiAgICBsZXQgcHJvcG9zYWxJZCA9ICcnO1xyXG4gICAgbGV0IHJlYWR5VmVyc2lvbiA9ICcnO1xyXG4gICAgbGV0IHJlYWR5U2luY2UgPSAwO1xyXG4gICAgY29uc3QgaXNDaGVja3BvaW50ID0gYXN5bmMgKCkgPT4ge1xyXG4gICAgICB3YXRjaGRvZy5yZW1haW5pbmcocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gICAgICBhd2FpdCBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2UpO1xyXG4gICAgICB3b3JrZmxvdyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICBjb25zdCBwcm9ncmVzcyA9IHdhdGNoZG9nLm9ic2VydmUod29ya2Zsb3csIHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICAgICAgaWYgKHByb2dyZXNzLmFkdmFuY2VkKSBwcm9ncmVzc01pbGVzdG9uZXMuZ2V0KHRlc3QuaW5mbygpLnRlc3RJZCkhLnB1c2goe1xyXG4gICAgICAgIGF0OiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksIGZyb250aWVyOiBwcm9ncmVzcy5mcm9udGllcixcclxuICAgICAgICBjb21wbGV0ZWRUaHJvdWdoOiBzdGVwc1twcm9ncmVzcy5mcm9udGllciAtIDFdLFxyXG4gICAgICAgIHByb2plY3Q6IHdvcmtmbG93LnByb2plY3RfaWQsIGV4ZWN1dGlvbjogd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24sXHJcbiAgICAgIH0pO1xyXG4gICAgICBpZiAoY3Jhc2hTaW11bGF0aW9uICYmICFyZXN0YXJ0ZWRKb2JJZCAmJiBkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlcy52YWxpZGF0aW9uKSkge1xyXG4gICAgICAgIGNvbnN0IGpvYnMgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icztcclxuICAgICAgICBjb25zdCBydW5uaW5nID0gam9icy5maW5kKChqb2I6IHsgc3RhdHVzOiBzdHJpbmcgfSkgPT4gam9iLnN0YXR1cyA9PT0gJ3J1bm5pbmcnKTtcclxuICAgICAgICBpZiAocnVubmluZykge1xyXG4gICAgICAgICAgcmVzdGFydGVkSm9iSWQgPSBydW5uaW5nLmlkO1xyXG4gICAgICAgICAgYXdhaXQgcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2UsIHRydWUpO1xyXG4gICAgICAgICAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICAgICAgICAgIHJldHVybiBmYWxzZTtcclxuICAgICAgICB9XHJcbiAgICAgIH1cclxuICAgICAgaWYgKHN0ZXBzLmV2ZXJ5KHN0ZXAgPT4gZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXNbc3RlcF0pKSkgcmV0dXJuIHRydWU7XHJcbiAgICAgIGNvbnN0IGV4ZWN1dGlvbiA9IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uO1xyXG4gICAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JFVklFV19SRVFVSVJFRCcpIHtcclxuICAgICAgICBjb25zdCBjb252ZXJzYXRpb24gPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKTtcclxuICAgICAgICBwcm9wb3NhbElkID0gY29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsO1xyXG4gICAgICAgIC8vIFBvbGxpbmcgbWF5IHN0aWxsIGV4cG9zZSB0aGUganVzdC1hcHBsaWVkIHJldmlldyB3aGlsZSB0aGUgVUkgc3RhcnRzXHJcbiAgICAgICAgLy8gaXRzIGR1cmFibGUgY29udGludWF0aW9uLiBXYWl0IGZvciBhIGRpc3RpbmN0IHByb3Bvc2FsLCBub3QgaXRzIGxhYmVsLlxyXG4gICAgICAgIHJldHVybiBCb29sZWFuKHByb3Bvc2FsSWQpICYmICFyZXZpZXdlZC5oYXMocHJvcG9zYWxJZCk7XHJcbiAgICAgIH1cclxuICAgICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdSRUFEWV9UT19DT05USU5VRScgfHwgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24ucmVjb3ZlcmFibGUgPT09IHRydWUpKSB7XHJcbiAgICAgICAgaWYgKHJlYWR5VmVyc2lvbiAhPT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQpIHtcclxuICAgICAgICAgIHJlYWR5VmVyc2lvbiA9IGV4ZWN1dGlvbi51cGRhdGVkX2F0OyByZWFkeVNpbmNlID0gRGF0ZS5ub3coKTtcclxuICAgICAgICB9XHJcbiAgICAgICAgLy8gV2hpbGUgYSBsYXJnZSBjb250aW51YXRpb24gaXMgZ2VuZXJhdGluZywgdGhlIGxhc3QgY29tbWl0dGVkIHNlcnZlclxyXG4gICAgICAgIC8vIGNoZWNrcG9pbnQgY2FuIHN0aWxsIGJlIFJFQURZLiBBY3Qgb25seSB3aGVuIHRoZSBVSSBvZmZlcnMgaXQgdG9vLlxyXG4gICAgICAgIGNvbnN0IGJ1dHRvbiA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSlcclxuICAgICAgICAgIC5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1ZnRyYWcgZm9ydHNldHplbicsIGV4YWN0OiB0cnVlIH0pO1xyXG4gICAgICAgIHJldHVybiBEYXRlLm5vdygpIC0gcmVhZHlTaW5jZSA+IDUwMDAgJiYgYXdhaXQgYnV0dG9uLmV2YWx1YXRlQWxsKGJ1dHRvbnMgPT4gYnV0dG9ucy5zb21lKGJ1dHRvbiA9PiAhKGJ1dHRvbiBhcyBIVE1MQnV0dG9uRWxlbWVudCkuZGlzYWJsZWQgJiYgYnV0dG9uLmdldENsaWVudFJlY3RzKCkubGVuZ3RoID4gMCAmJiBnZXRDb21wdXRlZFN0eWxlKGJ1dHRvbikudmlzaWJpbGl0eSAhPT0gXCJoaWRkZW5cIikpO1xyXG4gICAgICB9XHJcbiAgICAgIHJldHVybiBbJ0JMT0NLRUQnLCAnRkFJTEVEJywgJ0lOQ09NUExFVEUnXS5pbmNsdWRlcyhleGVjdXRpb24/LnN0YXRlKTtcclxuICAgIH07XHJcbiAgICAvLyBBIHNpbmdsZSBwb2xsIHByZXZpb3VzbHkgdGltZWQgYWxsIG9mIENhcGFjaXR5IC0+IEludGVsbGlnZW5jZSB0b2dldGhlci5cclxuICAgIC8vIEJvdW5kIGVhY2ggZ2VudWluZSBzdGFnZSBhZHZhbmNlLCB3aGlsZSByZXRyaWVzIGFuZCByZXN0YXJ0cyByZXRhaW4gdGhlaXJcclxuICAgIC8vIHJlbWFpbmluZyBkZWFkbGluZS4gVGhlIGluZGVwZW5kZW50IDIwLW1pbnV0ZSB0ZXN0IHRpbWVvdXQgaXMgdW5jaGFuZ2VkLlxyXG4gICAgbGV0IGF0dGVtcHQgPSAwO1xyXG4gICAgd2hpbGUgKCFhd2FpdCBpc0NoZWNrcG9pbnQoKSkge1xyXG4gICAgICBjb25zdCByZW1haW5pbmcgPSB3YXRjaGRvZy5yZW1haW5pbmcocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gICAgICBhd2FpdCBwYWdlLndhaXRGb3JUaW1lb3V0KE1hdGgubWluKFs1MDAsIDEwMDAsIDIwMDBdW01hdGgubWluKGF0dGVtcHQrKywgMildLCByZW1haW5pbmcpKTtcclxuICAgIH1cclxuICAgIHJ1bklkID8/PSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQpLnRvQmUocnVuSWQpO1xyXG4gICAgaWYgKHN0ZXBzLmV2ZXJ5KHN0ZXAgPT4gZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXNbc3RlcF0pKSkge1xyXG4gICAgICBpZiAoY3Jhc2hTaW11bGF0aW9uKSBleHBlY3QocmVzdGFydGVkSm9iSWQsICdBIHJlYWwgcnVubmluZyBzaW11bGF0aW9uIG11c3QgYmUgb2JzZXJ2ZWQgYW5kIGludGVycnVwdGVkLicpLnRvQmVUcnV0aHkoKTtcclxuICAgICAgcmV0dXJuIHsgcnVuSWQsIHJldmlld2VkOiBbLi4ucmV2aWV3ZWRdLCByZXN0YXJ0ZWRKb2JJZCB9O1xyXG4gICAgfVxyXG4gICAgY29uc3QgZXhlY3V0aW9uID0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb247XHJcbiAgICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pO1xyXG4gICAgaWYgKHN0b3BPbkV2aWRlbmNlQmxvY2sgJiYgZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5ibG9ja2luZ19maW5kaW5ncz8ubGVuZ3RoKSB7XHJcbiAgICAgIHRocm93IG5ldyBFcnJvcihgV2l6YXJkIEJMT0NLRUQgYXQgJHtleGVjdXRpb24uc3RlcH06ICR7ZXhlY3V0aW9uLm1lc3NhZ2V9YCk7XHJcbiAgICB9XHJcbiAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5tZXNzYWdlPy5pbmNsdWRlcygnUkVBRFlfV0lUSF9XQVJOSU5HUycpKSB7XHJcbiAgICAgIGNvbnN0IGJlZm9yZVJldmlldyA9IGF3YWl0IHJlYWRXYXJuaW5nUmV2aWV3U3RhdGUocGFnZSwgcHJvamVjdCk7XHJcbiAgICAgIGNvbnN0IHByZWZsaWdodCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3ByZWZsaWdodCcpO1xyXG4gICAgICBjb25zdCB3YXJuaW5ncyA9IGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ1ByZWZsaWdodC1XYXJudW5nZW4nIH0pO1xyXG4gICAgICBhd2FpdCBleHBlY3Qod2FybmluZ3MuZ2V0QnlSb2xlKCdsaXN0aXRlbScpLmZpcnN0KCkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgICAgIGNvbnN0IHN0YXJ0ZWQgPSBwZXJmb3JtYW5jZS5ub3coKSwgc3RhcnRlZFdhbGwgPSBEYXRlLm5vdygpO1xyXG4gICAgICB3YXRjaGRvZy5yZW1haW5pbmcoc3RhcnRlZCk7XHJcbiAgICAgIGNvbnN0IGFwcHJvdmFsUmVzcG9uc2UgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiBuZXcgVVJMKHJlc3BvbnNlLnVybCgpKS5wYXRobmFtZSA9PT0gJy9hcGkvZW5naW5lZXJpbmcvcHJlZmxpZ2h0L3dhcm5pbmdzL2FwcHJvdmUnXHJcbiAgICAgICAgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcsIHsgdGltZW91dDogMTgwXzAwMCB9KTtcclxuICAgICAgYXdhaXQgd2FybmluZ3MuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdXYXJudW5nZW4gZnJlaWdlYmVuIHVuZCBmb3J0c2V0emVuJyB9KS5jbGljaygpO1xyXG4gICAgICBjb25zdCBhcHByb3ZlZCA9IGF3YWl0IGFwcHJvdmFsUmVzcG9uc2U7XHJcbiAgICAgIGNvbnN0IHJlY2VpcHQgPSBhd2FpdCBhcHByb3ZlZC5qc29uKCk7XHJcbiAgICAgIGNvbnN0IGFmdGVyUmV2aWV3ID0gYXdhaXQgcmVhZFdhcm5pbmdSZXZpZXdTdGF0ZShwYWdlLCBwcm9qZWN0KTtcclxuICAgICAgY29uc3QgcHJvb2YgPSB7IGJlZm9yZTogYmVmb3JlUmV2aWV3LCBhZnRlcjogYWZ0ZXJSZXZpZXcsIHNuYXBzaG90SWQ6IHByZWZsaWdodC5pZCxcclxuICAgICAgICByZXF1ZXN0UHJvamVjdDogYXBwcm92ZWQucmVxdWVzdCgpLmhlYWRlcnMoKVsneC1wcm9qZWN0LWlkJ10sIHN1Ym1pdHRlZDogYXBwcm92ZWQucmVxdWVzdCgpLnBvc3REYXRhSlNPTigpLFxyXG4gICAgICAgIHN0YXR1czogYXBwcm92ZWQuc3RhdHVzKCksIHJlc3BvbnNlOiByZWNlaXB0LCBzdGFydGVkLCBzdGFydGVkV2FsbCwgZmluaXNoZWRXYWxsOiBEYXRlLm5vdygpIH07XHJcbiAgICAgIGNvbnN0IGNvbW1pdHRlZEF0ID0gcGVyZm9ybWFuY2Uubm93KCk7XHJcbiAgICAgIGNvbnN0IGNvbW1pdHRlZCA9IHdhdGNoZG9nLmNvbW1pdFdhcm5pbmdSZXZpZXcocHJvb2YsIGNvbW1pdHRlZEF0KTtcclxuICAgICAgYXdhaXQgdGVzdC5pbmZvKCkuYXR0YWNoKCd2ZXJpZmllZC13YXJuaW5nLXJldmlldy1wcm9vZicsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9vZiwgY29tbWl0dGVkQXQsIGNvbW1pdHRlZCB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICAgICAgcHJvZ3Jlc3NNaWxlc3RvbmVzLmdldCh0ZXN0LmluZm8oKS50ZXN0SWQpIS5wdXNoKHsgYXQ6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSwgbWFudWFsV2FybmluZ0FwcHJvdmFsOiBjb21taXR0ZWQuYXBwcm92YWxJZGVudGl0eSxcclxuICAgICAgICBmcm9udGllcjogY29tbWl0dGVkLmZyb250aWVyLCBwcm9qZWN0LCBleGVjdXRpb246IGFmdGVyUmV2aWV3LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLCBhcHByb3ZhbDogcmVjZWlwdC5hcHByb3ZhbCB9KTtcclxuICAgICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpKS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCxcclxuICAgICAgICB7IHRpbWVvdXQ6IGV4cGVjdGVkSGFyZHdhcmUubGVuZ3RoID4gMTAwID8gMTgwXzAwMCA6IDYwXzAwMCB9KS5ub3QudG9CZShleGVjdXRpb24udXBkYXRlZF9hdCk7XHJcbiAgICAgIGNvbnRpbnVlO1xyXG4gICAgfVxyXG4gICAgaWYgKFsnQkxPQ0tFRCcsICdGQUlMRUQnLCAnSU5DT01QTEVURSddLmluY2x1ZGVzKGV4ZWN1dGlvbj8uc3RhdGUpICYmIGV4ZWN1dGlvbi5yZWNvdmVyYWJsZSAhPT0gdHJ1ZSkge1xyXG4gICAgICBjb25zdCBjb252ZXJzYXRpb24gPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKTtcclxuICAgICAgY29uc3QgaWQgPSBjb252ZXJzYXRpb24uZGF0YT8uYWN0aXZlX3Byb3Bvc2FsO1xyXG4gICAgICBjb25zdCBwcm9wb3NhbCA9IGlkID8gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7aWR9YCkgOiBudWxsO1xyXG4gICAgICBhd2FpdCB0ZXN0LmluZm8oKS5hdHRhY2goJ3dpemFyZC1ibG9ja2VyJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IGV4ZWN1dGlvbixcclxuICAgICAgICBwcm9wb3NhbDogcHJvcG9zYWw/LmRhdGE/LnZhbGlkYXRpb25fcmVzdWx0LCB2aXNpYmxlOiBhd2FpdCBkaWFsb2cuaW5uZXJUZXh0KCkgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgICAgIHRocm93IG5ldyBFcnJvcihgV2l6YXJkICR7ZXhlY3V0aW9uLnN0YXRlfSBhdCAke2V4ZWN1dGlvbi5zdGVwfTogJHtleGVjdXRpb24ubWVzc2FnZX1gKTtcclxuICAgIH1cclxuICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnUkVBRFlfVE9fQ09OVElOVUUnIHx8IChleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLnJlY292ZXJhYmxlID09PSB0cnVlKSkge1xyXG4gICAgICBjb25zdCBidXR0b24gPSBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBdWZ0cmFnIGZvcnRzZXR6ZW4nLCBleGFjdDogdHJ1ZSB9KTtcclxuICAgICAgdHJ5IHtcclxuICAgICAgICBhd2FpdCBidXR0b24uY2xpY2soeyB0aW1lb3V0OiAyMDAwIH0pO1xyXG4gICAgICB9IGNhdGNoIChlcnJvcikge1xyXG4gICAgICAgIGNvbnN0IGxhdGVzdCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICAgIGlmIChsYXRlc3QuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQgPT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0ICYmIGF3YWl0IGJ1dHRvbi5ldmFsdWF0ZUFsbChidXR0b25zID0+IGJ1dHRvbnMuc29tZShidXR0b24gPT4gIShidXR0b24gYXMgSFRNTEJ1dHRvbkVsZW1lbnQpLmRpc2FibGVkICYmIGJ1dHRvbi5nZXRDbGllbnRSZWN0cygpLmxlbmd0aCA+IDAgJiYgZ2V0Q29tcHV0ZWRTdHlsZShidXR0b24pLnZpc2liaWxpdHkgIT09IFwiaGlkZGVuXCIpKSkgdGhyb3cgZXJyb3I7XHJcbiAgICAgICAgY29udGludWU7XHJcbiAgICAgIH1cclxuICAgICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgICAgIGNvbnN0IGxhdGVzdCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICAgIHJldHVybiBsYXRlc3QuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQgIT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0XHJcbiAgICAgICAgICB8fCBsYXRlc3QuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnN0YXRlID09PSAnUlVOTklORydcclxuICAgICAgICAgIHx8IGxhdGVzdC5zdGF0dXNlcz8uW2V4ZWN1dGlvbi5zdGVwXSA9PT0gJ0lOX1BST0dSRVNTJztcclxuICAgICAgfSwgeyB0aW1lb3V0OiA2MF8wMDAgfSkudG9CZSh0cnVlKTtcclxuICAgICAgY29udGludWU7XHJcbiAgICB9XHJcbiAgICBjb25zdCBjYW5kaWRhdGUgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtwcm9wb3NhbElkfWApO1xyXG4gICAgaWYgKGNhbmRpZGF0ZS5kYXRhLnByb3Bvc2FsX3R5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnICYmIHJldmlld0NvdW50ID09PSAwICYmIGV4cGVjdGVkSGFyZHdhcmUubGVuZ3RoKSB7XHJcbiAgICAgIGNvbnN0IGhhcmR3YXJlID0gY2FuZGlkYXRlLmRhdGEuY2hhbmdlc1xyXG4gICAgICAgIC5maWx0ZXIoKGNoYW5nZTogeyBvYmplY3RfdHlwZTogc3RyaW5nIH0pID0+IGNoYW5nZS5vYmplY3RfdHlwZSA9PT0gJ0hhcmR3YXJlTm9kZScpXHJcbiAgICAgICAgLm1hcCgoY2hhbmdlOiB7IGRhdGE6IHsgbmFtZTogc3RyaW5nIH0gfSkgPT4gY2hhbmdlLmRhdGEubmFtZSk7XHJcbiAgICAgIGV4cGVjdChoYXJkd2FyZSwgJ1RoZSBVSSBtdXN0IHByZXNlcnZlIHRoZSBoYXJkd2FyZSBleHBsaWNpdGx5IG5hbWVkIGluIHRoZSB1c2VyIHJlcXVlc3QuJylcclxuICAgICAgICAudG9FcXVhbChleHBlY3QuYXJyYXlDb250YWluaW5nKGV4cGVjdGVkSGFyZHdhcmUpKTtcclxuICAgIH1cclxuICAgIGV4cGVjdChyZXZpZXdlZC5oYXMocHJvcG9zYWxJZCksICdUaGUgc2FtZSBwcm9wb3NhbCBtdXN0IG5vdCByZXF1ZXN0IHJldmlldyB0d2ljZS4nKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IHJldmlld0FjdGlvbiA9IGF3YWl0IGJlZm9yZVByb3Bvc2FsUmV2aWV3Py4ocHJvcG9zYWxJZCwgY2FuZGlkYXRlLmRhdGEucHJvcG9zYWxfdHlwZSk7XHJcbiAgICBpZiAocmV2aWV3QWN0aW9uID09PSAnU1RPUF9BRlRFUl9SRVZJRVcnKSB7XHJcbiAgICAgIC8vIEV4cGxpY2l0IHRhcmdldGVkIGNvdmVyYWdlOiB0aGUgc2VsZWN0ZWQgcGVuZGluZyBwcm9wb3NhbCBoYXMgYmVlblxyXG4gICAgICAvLyBleGVyY2lzZWQgYnV0IGlzIG5vdCBhcHBsaWVkIGFuZCB0aGlzIGlzIG5vdCBuaW5lLXN0YWdlIGNvbXBsZXRpb24uXHJcbiAgICAgIHJldHVybiB7IHJ1bklkLCByZXZpZXdlZDogWy4uLnJldmlld2VkXSwgcmVzdGFydGVkSm9iSWQsXHJcbiAgICAgICAgcmV2aWV3T25seTogeyBwcm9wb3NhbElkLCBwcm9wb3NhbFR5cGU6IGNhbmRpZGF0ZS5kYXRhLnByb3Bvc2FsX3R5cGUgfSB9O1xyXG4gICAgfVxyXG4gICAgY29uc3QgYXBwbHlSZXNwb25zZSA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IHJlc3BvbnNlLnVybCgpLmluY2x1ZGVzKGAvcHJvcG9zYWxzLyR7cHJvcG9zYWxJZH0vYXBwcm92ZS1hcHBseWApICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnLCB7IHRpbWVvdXQ6IDE4MF8wMDAgfSk7XHJcbiAgICBjb25zdCBhcHByb3ZhbCA9IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogL14oRnJlaWdlYmVuLCDDvGJlcm5laG1lbiAmIGZvcnRmYWhyZW58w5xiZXJuZWhtZW4gJiBmb3J0ZmFocmVuKSQvIH0pO1xyXG4gICAgYXdhaXQgZXhwZWN0KGFwcHJvdmFsKS50b0JlRW5hYmxlZCh7IHRpbWVvdXQ6IDYwXzAwMCB9KTtcclxuICAgIGF3YWl0IGFwcHJvdmFsLmNsaWNrKCk7XHJcbiAgICBjb25zdCBhcHBsaWVkID0gYXdhaXQgYXBwbHlSZXNwb25zZTtcclxuICAgIGlmICghYXBwbGllZC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYEhUVFAgJHthcHBsaWVkLnN0YXR1cygpfTogJHsoYXdhaXQgYXBwbGllZC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gICAgZXhwZWN0KChhd2FpdCBhcHBsaWVkLmpzb24oKSkuZGF0YS5zdGF0dXMpLnRvQmUoJ0FQUExJRUQnKTtcclxuICAgIHJldmlld2VkLmFkZChwcm9wb3NhbElkKTsgcmV2aWV3Q291bnQrKztcclxuICAgIC8vIEEgZGlzdGluY3QsIGFjdHVhbGx5IGNvbW1pdHRlZCBtYW51YWwgcmV2aWV3IHN0YXJ0cyB0aGUgbmV4dCBhdXRvbWF0aWNcclxuICAgIC8vIHNlY3Rpb24uIEl0cyB3cml0ZSBzdGlsbCBoYXMgdGhlIHNlcGFyYXRlIHVuY2hhbmdlZCAxODAtc2Vjb25kIGxpbWl0LlxyXG4gICAgd2F0Y2hkb2cgPSBuZXcgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyhwZXJmb3JtYW5jZS5ub3coKSwgd29ya2Zsb3cpO1xyXG4gICAgaWYgKGNhbmRpZGF0ZS5kYXRhLnByb3Bvc2FsX3R5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnICYmIGV4cGVjdGVkU2lnbmFscykge1xyXG4gICAgICBhd2FpdCB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZSwgcHJvamVjdCwgZXhwZWN0ZWRTaWduYWxzKTtcclxuICAgIH1cclxuICAgIGlmIChyZXZpZXdDb3VudCA9PT0gMSAmJiBhZnRlckZpcnN0TW9kZWxBcHBsaWVkKSB7XHJcbiAgICAgIGF3YWl0IGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQoKTtcclxuICAgICAgLy8gVGhpcyBvbmUgdGVzdCBleHBsaWNpdGx5IHN1Ym1pdHMgQU1FTkQgYW5kIHdhaXRzIGZvciBpdHMgcmVjZWlwdC4gT25seVxyXG4gICAgICAvLyB0aGF0IGRlbGliZXJhdGUgYWN0aW9uIHBlcm1pdHMgYmluZGluZyBpdHMgbmV3IHJlcXVlc3QgcmV2aXNpb24uXHJcbiAgICAgIGNvbnN0IGFtZW5kZWQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgZXhwZWN0KGFtZW5kZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZCkudG9CZShydW5JZCk7XHJcbiAgICAgIHdhdGNoZG9nID0gbmV3IFdpemFyZFByb2dyZXNzV2F0Y2hkb2cocGVyZm9ybWFuY2Uubm93KCksIGFtZW5kZWQpO1xyXG4gICAgfVxyXG4gICAgaWYgKHJldmlld0NvdW50ID09PSAxKSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpOyAvLyBEdXJhYmxlIHJlbG9hZCBhZnRlciBhIHJlYWwgY29tbWl0LlxyXG4gICAgaWYgKHJlc3RhcnQgJiYgcmV2aWV3Q291bnQgPT09IDIpIHtcclxuICAgICAgYXdhaXQgcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2UpO1xyXG4gICAgICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgfVxyXG4gICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgICBjb25zdCBjdXJyZW50ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgIHJldHVybiBjdXJyZW50LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0ICE9PSBleGVjdXRpb24udXBkYXRlZF9hdDtcclxuICAgIH0sIHsgdGltZW91dDogNjBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbiAgfVxyXG4gIHRocm93IG5ldyBFcnJvcignV2l6YXJkIGV4Y2VlZGVkIDE2IHJldmlldy9jb250aW51YXRpb24gY2hlY2twb2ludHMuJyk7XHJcbn1cclxuXHJcbnRlc3QoJ3dpemFyZCByZWZ1c2VzIGFuIHVuYXZhaWxhYmxlIGNhdGFsb2cgYW5kIHJlY292ZXJzIHVzaW5nIHRoZSByZWFsIHJlZ2lzdHJ5IEBjYXRhbG9nLXJlY292ZXJ5JywgYXN5bmMgKHtwYWdlfSkgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1jYXRhbG9nLXJlY292ZXJ5LScgKyByYW5kb21VVUlEKCk7XHJcbiAgYXdhaXQgcGFnZS5yb3V0ZSgnKiovYXBpL3RlY2hub2xvZ2llcycsIHJvdXRlID0+IHJvdXRlLmZ1bGZpbGwoe3N0YXR1czo1MDMsXHJcbiAgICBjb250ZW50VHlwZTonYXBwbGljYXRpb24vanNvbicsYm9keTpKU09OLnN0cmluZ2lmeSh7ZXJyb3I6J0RlciB2b2xsc3TDpG5kaWdlIFRlY2hub2xvZ2lla2F0YWxvZyBpc3QgZGVyemVpdCBuaWNodCBlcnJlaWNoYmFyLid9KX0pKTtcclxuICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdhbGVydCcpKS50b0NvbnRhaW5UZXh0KCdUZWNobm9sb2dpZWthdGFsb2cnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7ZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdDYXRhbG9nIHJldHJ5Jyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7ZXhhY3Q6dHJ1ZX0pLmZpbGwoJ2VpbiBBa3RvciB6dW0gcHJvcG9ydGlvbmFsIHNjaGxpZcOfZW4gZWluZXMgVmVudGlsJyk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJykpLnRvQmVEaXNhYmxlZCgpO1xyXG4gIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icykudG9IYXZlTGVuZ3RoKDApO1xyXG4gIGF3YWl0IHBhZ2UudW5yb3V0ZSgnKiovYXBpL3RlY2hub2xvZ2llcycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6J1RlY2hub2xvZ2lla2F0YWxvZyBlcm5ldXQgbGFkZW4nfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYWxlcnQnKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJykpLnRvQmVFbmFibGVkKCk7XHJcbiAgY29uc3QgY2F0YWxvZyA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL3RlY2hub2xvZ2llcycpKS5qc29uKCk7XHJcbiAgZXhwZWN0KGNhdGFsb2cudGVjaG5vbG9neV9jb3VudCkudG9CZSgxMjUpO1xyXG59KTtcclxuXHJcbnRlc3QoJ25ldyBzbWFsbCB3aXphcmQgdHJhdmVyc2VzIGFsbCBuaW5lIHN0YWdlcyBhbmQgc3Vydml2ZXMgcmVsb2FkL3Jlc3RhcnQgQHNtYWxsJywgYXN5bmMgKHsgcGFnZSwgYnJvd3NlciB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IGVycm9yczogc3RyaW5nW10gPSBbXTsgcGFnZS5vbigncGFnZWVycm9yJywgZXJyb3IgPT4gZXJyb3JzLnB1c2goZXJyb3IubWVzc2FnZSkpO1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1zbWFsbC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjZW5naW5lZXJpbmctcHJvamVjdC1uYW1lJykuZmlsbCgnRTJFIHNtYWxsJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwoJ0VyemV1Z2UgZWluIEF1dG9tb3RpdmUgQ0FOLUZEIE5ldHp3ZXJrIG1pdCBlaW5lbSBHYXRld2F5IFN5c3RlbSwgZGVuIEVDVXMgTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UsIGVpbmVtIFNlbnNvciBNb3RvclRlbXBlcmF0dXJlIHVuZCBlaW5lbSBBa3RvciBNb3RvclZhbHZlLiBNb3RvclRlbXBlcmF0dXJlIHdpcmQgdm9uIE1vdG9yc3RldWVydW5nIGF1c2dld2VydGV0LiBNb3RvcnN0ZXVlcnVuZyBzdGV1ZXJ0IE1vdG9yVmFsdmUuIENvbnRyb2xsZXJzdGF0dXMgYmxlaWJ0IGJpcyB6dXIgQXVzd2FobCBrb25rcmV0ZXIgRW1wZsOkbmdlciB1bmQgU2lnbmFsZSBpbnRlcm4uIFByw7xmZSB1bmQgYXJiZWl0ZSBiaXMgRGF0YSBTY2llbmNlICYgSW50ZWxsaWdlbmNlLlxcbkNBTi1GRDogNTAwIGtiaXQvcyBhcmJpdHJhdGlvbiwgMiBNYml0L3MgZGF0YVxcbkNBTjogNTAwIGtiaXQvcycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdXZWl0ZXJlIEhpbndlaXNlJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKCctIEFrdG9yLUJlZmVobGU6IHtcIk1vdG9yVmFsdmVcIjp7XCJsZW5ndGhfYml0c1wiOjEsXCJkYXRhX3R5cGVcIjpcImJvb2xlYW5cIixcImZhY3RvclwiOjEsXCJ1bml0XCI6XCJjb2RlXCIsXCJtaW5fdmFsdWVcIjowLFwibWF4X3ZhbHVlXCI6MSxcInNlbWFudGljXCI6e1wic2VtYW50aWNfdHlwZVwiOlwiQk9PTEVBTlwifSxcImRhdGFcIjp7XCJlbnVtX3ZhbHVlc1wiOntcIkNMT1NFXCI6MCxcIk9QRU5cIjoxfX19fScpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdHZXLDpHRldW1mYW5nJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGZvciAoY29uc3QgW2xhYmVsLCB2YWx1ZV0gb2YgW1snR2F0ZXdheXMnLCAnMSddLCBbJ0NvbnRyb2xsZXInLCAnMiddLCBbJ1NlbnNvcmVuJywgJzEnXSwgWydBa3RvcmVuJywgJzEnXV0pIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKGAke2xhYmVsfTogdmVyYmluZGxpY2hlIEFuemFobGAsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCh2YWx1ZSk7XHJcbiAgY29uc3Qgc3RhcnRSZXF1ZXN0ID0gcGFnZS53YWl0Rm9yUmVxdWVzdChyZXF1ZXN0ID0+IHJlcXVlc3QudXJsKCkuZW5kc1dpdGgoJy9hcGkvYWdlbnQvY2hhdCcpXHJcbiAgICAmJiByZXF1ZXN0Lm1ldGhvZCgpID09PSAnUE9TVCcgJiYgcmVxdWVzdC5wb3N0RGF0YUpTT04oKT8ud2l6YXJkX2NvbW1hbmQ/LmFjdGlvbiA9PT0gJ1NUQVJUJyk7XHJcbiAgLy8gVXNlIHRoZSBzYW1lIHZpc2libGUgcXVlc3Rpb25uYWlyZSBuYXZpZ2F0aW9uIGEgdXNlciB1c2VzOyBuZXZlciBpbmplY3QgZ2VuZXJhdGVkIG1vZGVsIHJvd3MuXHJcbiAgZm9yIChsZXQgc3RlcCA9IDA7IHN0ZXAgPCAxMDsgc3RlcCsrKSB7XHJcbiAgICBjb25zdCBzdWJtaXQgPSBkaWFsb2cubG9jYXRvcignLmVuZy1hZ2VudC1xdWVzdGlvbm5haXJlLWhlYWQnKS5nZXRCeVJvbGUoJ2J1dHRvbicpO1xyXG4gICAgYXdhaXQgZXhwZWN0KHN1Ym1pdCkudG9CZUVuYWJsZWQoKTtcclxuICAgIGNvbnN0IG5hbWUgPSBhd2FpdCBzdWJtaXQuaW5uZXJUZXh0KCk7XHJcbiAgICBhd2FpdCBzdWJtaXQuY2xpY2soKTtcclxuICAgIGlmIChuYW1lID09PSAnw5xiZXJuZWhtZW4nKSBicmVhaztcclxuICAgIGlmIChzdGVwID09PSA5KSB0aHJvdyBuZXcgRXJyb3IoJ1F1ZXN0aW9ubmFpcmUgZGlkIG5vdCBvZmZlciBzdWJtaXQuJyk7XHJcbiAgfVxyXG4gIGNvbnN0IHJlcXVlc3RlZCA9IChhd2FpdCBzdGFydFJlcXVlc3QpLnBvc3REYXRhSlNPTigpLndpemFyZF9jb21tYW5kLndpemFyZF9jb250ZXh0O1xyXG4gIGV4cGVjdChyZXF1ZXN0ZWQudGVjaG5vbG9naWVzLCAnQW4gZXhwbGljaXQgQ0FOLUZEIHRhc2sgbXVzdCBub3Qgc2lsZW50bHkgcmVxdWVzdCBMSU4gYW5kIFNPTUUvSVAuJykudG9FcXVhbChbJ0NBTi1GRCAoY2FuX2ZkKSddKTtcclxuICAvLyBQcmVzZXJ2ZSBhIHJlYWwgcGVuZGluZyBtb2RlbCB0aHJvdWdoIHBhcmFtZXRlciBzYXZlIGFuZCByZW5ld2VkIHJldmlldy5cclxuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiAoYXdhaXQgcmVhZFByb2plY3QocGFnZSxwcm9qZWN0LCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpKS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uc3RhdGUsXHJcbiAgICB7dGltZW91dDoxODAwMDB9KS50b0JlKCdSRVZJRVdfUkVRVUlSRUQnKTtcclxuICBjb25zdCBwZW5kaW5nID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UscHJvamVjdCwnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKSkuZGF0YS5hY3RpdmVfcHJvcG9zYWw7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7cHJvamVjdH0mdGVjaG5vbG9neT1jYW5fZmQmcHJvcG9zYWw9JHtwZW5kaW5nfSNwYXJhbWV0ZXItZmluZGluZ3NgKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicse25hbWU6J0FrdHVlbGxlIFBhcmFtZXRlcmJlZnVuZGUnfSkpLnRvQ29udGFpblRleHQoJ25vY2ggbmljaHQgw7xiZXJub21tZW5lbiBWb3JzY2hsYWdzJyk7XHJcbiAgY29uc3QgY29tbW9uID0gcGFnZS5sb2NhdG9yKCcucGFyYW1ldGVyLWdyb3VwLWNvbW1vbicpO1xyXG4gIGF3YWl0IGV4cGVjdChjb21tb24ubG9jYXRvcignI2FyYml0cmF0aW9uX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzUwMCBrYml0L3MnKTtcclxuICBhd2FpdCBleHBlY3QoY29tbW9uLmxvY2F0b3IoJyNkYXRhX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzIgTWJpdC9zJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignLnBhcmFtZXRlci1kZXRhaWxzW29wZW5dJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IHJlcGVhdFBhcmFtZXRlclJldHVybihwYWdlLCBwcm9qZWN0LCBwZW5kaW5nLCBbe3RlY2hub2xvZ3k6ICdjYW5fZmQnLFxyXG4gICAgZmllbGRzOiB7YXJiaXRyYXRpb25fYml0cmF0ZTogJzUwMCBrYml0L3MnLCBkYXRhX2JpdHJhdGU6ICcxIE1iaXQvcycsIGNhbl9mZF9kYXRhX3ByZXNjYWxlcjogJzInfSxcclxuICAgIG5hdGl2ZToge2FyYml0cmF0aW9uX2JpdHJhdGU6IDUwMF8wMDAsIGRhdGFfYml0cmF0ZTogMV8wMDBfMDAwLCBjYW5fZmRfZGF0YV9wcmVzY2FsZXI6IDJ9LFxyXG4gICAgZWRpdEZpZWxkczogWydkYXRhX2JpdHJhdGUnLCAnY2FuX2ZkX2RhdGFfcHJlc2NhbGVyJ119XSk7XHJcbiAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLHByb2plY3QsYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7cGVuZGluZ30/dmlldz1zdGF0dXNgKSkuZGF0YS5jYW5vbmljYWxfaWRzKS50b0VxdWFsKFtdKTtcclxuICBleHBlY3QoKGF3YWl0IGFsbE9iamVjdHMocGFnZSxwcm9qZWN0LCdoYXJkd2FyZS1ub2RlcycpKSkudG9IYXZlTGVuZ3RoKDApO1xyXG4gIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgdHJ1ZSxcclxuICAgIFsnU3lzdGVtJywgJ01vdG9yc3RldWVydW5nJywgJ0FuemVpZ2UnLCAnTW90b3JUZW1wZXJhdHVyZScsICdNb3RvclZhbHZlJ10pO1xyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCA1LCB1bmRlZmluZWQsIHtcclxuICAgIHNlZWQ6IDQyLCBkYXRhX2JpdHJhdGU6IDFfMDAwXzAwMCwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyOiAyLFxyXG4gIH0pO1xyXG4gIGV4cGVjdChhcnRpZmFjdHMuYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoMyk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnRyYW5zcG9ydF9leGNsdXNpb25zKS50b0hhdmVMZW5ndGgoMyk7XHJcbiAgY29uc3QgZmluaXNoZWQgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5pbmNsdWRlcyhgL3J1bnMvJHtjb250aW51aXR5LnJ1bklkfS9maW5pc2hgKVxyXG4gICAgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0ZlcnRpZyBzdGVsbGVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBleHBlY3QoKGF3YWl0IGZpbmlzaGVkKS5vaygpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cpLm5vdC50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlKS50b0hhdmVVUkwobmV3IFJlZ0V4cChgL3N0dWRpby9yZXN1bHRzXFxcXD9zbmFwc2hvdD0ke2FydGlmYWN0cy5zbmFwc2hvdH0mcHJvamVjdD0ke3Byb2plY3R9JGApKTtcclxuICBjb25zdCBzZWxlY3RlZFJ1biA9IHBhZ2UubG9jYXRvcihgLnJlc3VsdC1ydW4tbGlzdCBidXR0b25bZGF0YS1zbmFwc2hvdC1pZD1cIiR7YXJ0aWZhY3RzLnNuYXBzaG90fVwiXWApO1xyXG4gIGF3YWl0IGV4cGVjdChzZWxlY3RlZFJ1bikudG9IYXZlQ2xhc3MoJ2FjdGl2ZScpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnQW5mb3JkZXJ1bmdzZXJmw7xsbHVuZzogQmVzdGFuZGVuJywgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcubWV0cmljJykuZmlsdGVyKHsgaGFzOiBwYWdlLmdldEJ5VGV4dCgnVHJhY2UgRXZlbnRzJywgeyBleGFjdDogdHJ1ZSB9KSB9KSlcclxuICAgIC50b0NvbnRhaW5UZXh0KGFydGlmYWN0cy50cmFjZV9ldmVudHMudG9Mb2NhbGVTdHJpbmcoJ2RlLURFJykpO1xyXG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHNlbGVjdGVkUnVuKS50b0hhdmVDbGFzcygnYWN0aXZlJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdBbmZvcmRlcnVuZ3NlcmbDvGxsdW5nOiBCZXN0YW5kZW4nLCB7IGV4YWN0OiB0cnVlIH0pKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdsaW5rJywgeyBuYW1lOiAnU2ltdWxhdGlvbiDDtmZmbmVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBjb25zdCBydW5uZXIgPSBwYWdlLmxvY2F0b3IoJy5tb2RlbC1zaW11bGF0aW9uLXJ1bm5lcicpO1xyXG4gIGF3YWl0IGV4cGVjdChydW5uZXIpLnRvSGF2ZUF0dHJpYnV0ZSgnZGF0YS1qb2ItaWQnLCBhcnRpZmFjdHMuam9iKTtcclxuICBhd2FpdCBleHBlY3QocnVubmVyKS50b0hhdmVBdHRyaWJ1dGUoJ2RhdGEtc25hcHNob3QtaWQnLCBhcnRpZmFjdHMuc25hcHNob3QpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnaGVhZGluZycsIHsgbmFtZTogJ1NpbXVsYXRpb24gYWJnZXNjaGxvc3NlbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHJ1bm5lcikudG9IYXZlQXR0cmlidXRlKCdkYXRhLWpvYi1pZCcsIGFydGlmYWN0cy5qb2IpO1xyXG4gIC8vIEEgbmV3IGJyb3dzZXIgY29udGV4dCBoYXMgbm8gc2Vzc2lvbiBrZXkgZnJvbSBlaXRoZXIgd2l6YXJkIG9yIHNpbXVsYXRpb24gVUkuXHJcbiAgY29uc3QgZnJlc2hDb250ZXh0ID0gYXdhaXQgYnJvd3Nlci5uZXdDb250ZXh0KHsgYmFzZVVSTDogbmV3IFVSTChwYWdlLnVybCgpKS5vcmlnaW4gfSk7XHJcbiAgbGV0IHJlc3RhcnRlZEpvYjogc3RyaW5nIHwgbnVsbCA9IG51bGw7XHJcbiAgdHJ5IHtcclxuICAgIGNvbnN0IGZyZXNoID0gYXdhaXQgZnJlc2hDb250ZXh0Lm5ld1BhZ2UoKTtcclxuICAgIGF3YWl0IGZyZXNoLmdvdG8oYC9zdHVkaW8vc2ltdWxhdGlvbj9wcm9qZWN0PSR7cHJvamVjdH1gKTtcclxuICAgIGNvbnN0IGZyZXNoUnVubmVyID0gZnJlc2gubG9jYXRvcignLm1vZGVsLXNpbXVsYXRpb24tcnVubmVyJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZnJlc2hSdW5uZXIpLnRvSGF2ZUF0dHJpYnV0ZSgnZGF0YS1qb2ItaWQnLCBhcnRpZmFjdHMuam9iKTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaFJ1bm5lcikudG9IYXZlQXR0cmlidXRlKCdkYXRhLXNuYXBzaG90LWlkJywgYXJ0aWZhY3RzLnNuYXBzaG90KTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaC5nZXRCeVJvbGUoJ2hlYWRpbmcnLCB7IG5hbWU6ICdTaW11bGF0aW9uIGFiZ2VzY2hsb3NzZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKTtcclxuICAgIC8vIEEgY29tcGxldGVkIGhpc3RvcmljYWwgcnVuIG11c3Qgbm90IGJsb2NrIHRoZSBjdXJyZW50IGFwcHJvdmVkIHByZWZsaWdodC5cclxuICAgIGF3YWl0IG9wZW5TaW11bGF0aW9uUnVuKGZyZXNoKTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaC5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0xhdWYgc3RhcnRlbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRW5hYmxlZCgpO1xyXG4gICAgYXdhaXQgZnJlc2gubG9jYXRvcignLnNpbXVsYXRpb24tY29tbWFuZC1iYXInKS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0Fuc2ljaHQgenVyw7xja3NldHplbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBmcmVzaC5nZXRCeVJvbGUoJ2FsZXJ0ZGlhbG9nJykuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBbnNpY2h0IHp1csO8Y2tzZXR6ZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGZyZXNoUnVubmVyKS5ub3QudG9IYXZlQXR0cmlidXRlKCdkYXRhLWpvYi1pZCcpO1xyXG4gICAgYXdhaXQgZnJlc2gucmVsb2FkKCk7XHJcbiAgICBhd2FpdCBvcGVuU2ltdWxhdGlvblJ1bihmcmVzaCk7XHJcbiAgICBhd2FpdCBleHBlY3QoZnJlc2guZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdMYXVmIHN0YXJ0ZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZUVuYWJsZWQoKTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaFJ1bm5lcikubm90LnRvSGF2ZUF0dHJpYnV0ZSgnZGF0YS1qb2ItaWQnKTtcclxuICAgIGF3YWl0IGZyZXNoLmdvdG8oYC9zdHVkaW8vcmVzdWx0cz9wcm9qZWN0PSR7cHJvamVjdH0mc25hcHNob3Q9JHthcnRpZmFjdHMuc25hcHNob3R9YCk7XHJcbiAgICBhd2FpdCBleHBlY3QoZnJlc2gubG9jYXRvcignLnJlc3VsdC1ydW4tbGlzdCBidXR0b24uYWN0aXZlJykpLnRvSGF2ZUF0dHJpYnV0ZSgnZGF0YS1zbmFwc2hvdC1pZCcsIGFydGlmYWN0cy5zbmFwc2hvdCk7XHJcbiAgICBhd2FpdCBleHBlY3QoZnJlc2guZ2V0QnlUZXh0KCdBbmZvcmRlcnVuZ3NlcmbDvGxsdW5nOiBCZXN0YW5kZW4nLCB7IGV4YWN0OiB0cnVlIH0pKS50b0JlVmlzaWJsZSgpO1xyXG4gICAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCd3aXphcmQtcmVzdWx0LXJlc3RvcmF0aW9uJywgeyBib2R5OiBhd2FpdCBmcmVzaC5zY3JlZW5zaG90KCksIGNvbnRlbnRUeXBlOiAnaW1hZ2UvcG5nJyB9KTtcclxuICAgIC8vIEFjdHVhbCBub3JtYWwgU1RBUlQsIHdpdGhvdXQgcmVzZXR0aW5nL2RlbGV0aW5nIHRoZSByZXN0b3JlZCBjb21wbGV0ZWQgcnVuLlxyXG4gICAgYXdhaXQgZnJlc2guZ290byhgL3N0dWRpby9zaW11bGF0aW9uP3Byb2plY3Q9JHtwcm9qZWN0fSZzbmFwc2hvdD0ke2FydGlmYWN0cy5zbmFwc2hvdH1gKTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaFJ1bm5lcikudG9IYXZlQXR0cmlidXRlKCdkYXRhLWpvYi1pZCcsIGFydGlmYWN0cy5qb2IpO1xyXG4gICAgYXdhaXQgb3BlblNpbXVsYXRpb25SdW4oZnJlc2gpO1xyXG4gICAgYXdhaXQgZnJlc2guZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdMYXVmIHN0YXJ0ZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgICByZXN0YXJ0ZWRKb2IgPSBhd2FpdCBmcmVzaFJ1bm5lci5nZXRBdHRyaWJ1dGUoJ2RhdGEtam9iLWlkJyk7XHJcbiAgICAgIHJldHVybiBCb29sZWFuKHJlc3RhcnRlZEpvYiAmJiByZXN0YXJ0ZWRKb2IgIT09IGFydGlmYWN0cy5qb2IpO1xyXG4gICAgfSkudG9CZSh0cnVlKTtcclxuICAgIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IChhd2FpdCByZWFkUHJvamVjdChmcmVzaCwgcHJvamVjdCwgYC9hcGkvc2ltdWxhdGlvbnMvJHtyZXN0YXJ0ZWRKb2J9YCkpLnN0YXR1cyxcclxuICAgICAgeyB0aW1lb3V0OiAxODBfMDAwIH0pLnRvQmUoJ2NvbXBsZXRlZCcpO1xyXG4gICAgY29uc3QgcHJlc2VydmVkID0gYXdhaXQgcmVhZFByb2plY3QoZnJlc2gsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3NpbXVsYXRpb24tc25hcHNob3RzLyR7YXJ0aWZhY3RzLnNuYXBzaG90fWApO1xyXG4gICAgZXhwZWN0KHByZXNlcnZlZC5qb2JfaWQpLnRvQmUoYXJ0aWZhY3RzLmpvYik7XHJcbiAgICBleHBlY3QocHJlc2VydmVkLnJlc3VsdC50cmFjZS5ldmVudHMpLnRvQmUoYXJ0aWZhY3RzLnRyYWNlX2V2ZW50cyk7XHJcbiAgICBhd2FpdCBmcmVzaC5yZWxvYWQoKTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaFJ1bm5lcikudG9IYXZlQXR0cmlidXRlKCdkYXRhLWpvYi1pZCcsIHJlc3RhcnRlZEpvYiEpO1xyXG4gICAgYXdhaXQgZnJlc2guZ290byhgL3N0dWRpby9yZXN1bHRzP3Byb2plY3Q9JHtwcm9qZWN0fS1vdGhlciZzbmFwc2hvdD0ke2FydGlmYWN0cy5zbmFwc2hvdH1gKTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaC5nZXRCeVRleHQoJ0RpZXNlciBTaW11bGF0aW9uc2xhdWYgaXN0IGluIGRpZXNlbSBQcm9qZWt0IG5pY2h0IHZlcmbDvGdiYXIuJywgeyBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKTtcclxuICAgIGF3YWl0IGV4cGVjdChmcmVzaC5sb2NhdG9yKCcucmVzdWx0LXJ1bi1saXN0IGJ1dHRvbi5hY3RpdmUnKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgfSBmaW5hbGx5IHtcclxuICAgIGF3YWl0IGZyZXNoQ29udGV4dC5jbG9zZSgpO1xyXG4gIH1cclxuICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icy5tYXAoKGpvYjogeyBpZDogc3RyaW5nIH0pID0+IGpvYi5pZCkuc29ydCgpKVxyXG4gICAgLnRvRXF1YWwoW2FydGlmYWN0cy5qb2IsIHJlc3RhcnRlZEpvYl0uc29ydCgpKTtcclxuICBleHBlY3QoZXJyb3JzKS50b0VxdWFsKFtdKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2V2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIC4uLmNvbnRpbnVpdHksIC4uLmFydGlmYWN0cyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxufSk7XHJcblxyXG5mb3IgKGNvbnN0IHRlY2hub2xvZ3kgb2YgWydJMkMnLCAnTW9kYnVzIFJUVSddKSB7XHJcbiAgdGVzdChgUmFzcGJlcnJ5IFBpICR7dGVjaG5vbG9neX0gcHJvamVjdCByZXRhaW5zIG1vZGVsIGFuZCBibG9ja3MgaW5jb25zaXN0ZW50IG5hdGl2ZSBwYXJhbWV0ZXJzIEBub25hdXRvbW90aXZlYCwgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gICAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWVtYmVkZGVkLScgKyByYW5kb21VVUlEKCk7XHJcbiAgICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdUZW1wZXJhdHVycmVnZWx1bmcnKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdQcm9qZWt0YmVzY2hyZWlidW5nJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHRlY2hub2xvZ3kgPT09ICdJMkMnXHJcbiAgICAgID8gJzIgQWt0b3JlbiBmw7xyIFZlbnRpbGUsIDQgU2Vuc29yZW4gZsO8ciBUZW1wZXJhdHVyZW4sIHVuZCBlaW4gUmFzcGJlcnJ5UGknXHJcbiAgICAgIDogYDIgQWt0b3JlbiBmw7xyIFZlbnRpbGUsIDQgU2Vuc29yZW4gZsO8ciBUZW1wZXJhdHVyZW4sIHVuZCBlaW4gUmFzcGJlcnJ5UGkuIEVtYmVkZGVkIFN5c3RlbXMuIEFsbGUgR2Vyw6R0ZSBrb21tdW5pemllcmVuIMO8YmVyICR7dGVjaG5vbG9neX0uIFByw7xmZSB1bmQgYXJiZWl0ZSBiaXMgRGF0YSBTY2llbmNlICYgSW50ZWxsaWdlbmNlLmApO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ05ldHphcmNoaXRla3R1cicsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ3JhZGlvJywgeyBuYW1lOiAvVmFyaWFudGUgMC8gfSkuY2hlY2soKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdHZXLDpHRldW1mYW5nJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Jhc3BiZXJyeVBpOiBBbnNjaGx1c3MnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignSTJDJyk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlMYWJlbCgnVGVtcGVyYXR1cnNlbnNvcjE6IEFuc2NobHVzcycsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZVZhbHVlKCcnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgICBmb3IgKGNvbnN0IG5hbWUgb2YgWydSYXNwYmVycnlQaScsICdUZW1wZXJhdHVyc2Vuc29yMScsICdUZW1wZXJhdHVyc2Vuc29yMicsICdUZW1wZXJhdHVyc2Vuc29yMycsICdUZW1wZXJhdHVyc2Vuc29yNCcsICdWZW50aWxha3RvcjEnLCAnVmVudGlsYWt0b3IyJ10pIHtcclxuICAgICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbChgJHtuYW1lfTogQW5zY2hsdXNzYCwgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ0kyQycpO1xyXG4gICAgICB9XHJcbiAgICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdTZW5zb3IgMTogTWVzc2dyw7bDn2UnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignc3BlZWQnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeUxhYmVsKCdUZW1wZXJhdHVyc2Vuc29yMTogQW5zY2hsdXNzJywgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoJ0kyQycpO1xyXG4gICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnU2Vuc29yIDE6IE1lc3NncsO2w59lJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ3RlbXBlcmF0dXJlJyk7XHJcbiAgICB9XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnVmVudGlsYWt0b3IxOiBTdGVsbGJlZmVobCcsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdPUEVOX0NMT1NFJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMjogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnVmVudGlsYWt0b3IyOiBTdGVsbGJlZmVobCcsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdPUEVOX0NMT1NFJyk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBleHBlY3QoY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIHRydWUsIFsnUmFzcGJlcnJ5UGknLCAnVGVtcGVyYXR1cnNlbnNvcjEnLCAnVGVtcGVyYXR1cnNlbnNvcjInLCAnVGVtcGVyYXR1cnNlbnNvcjMnLCAnVGVtcGVyYXR1cnNlbnNvcjQnLCAnVmVudGlsYWt0b3IxJywgJ1ZlbnRpbGFrdG9yMiddLCBmYWxzZSwgdW5kZWZpbmVkLCB1bmRlZmluZWQsIHRydWUpKVxyXG4gICAgICAucmVqZWN0cy50b1Rocm93KC9XaXphcmQgQkxPQ0tFRCBhdCBwYXJhbWV0ZXJzOi4qYmVzdMOkdGlndGUgQW5nYWJlbi8pO1xyXG4gICAgY29uc3Qgd29ya2Zsb3cgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpO1xyXG4gICAgY29uc3QgZmluZGluZ3MgPSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbi5ibG9ja2luZ19maW5kaW5ncyBhcyB7IGNvZGU6IHN0cmluZyB9W107XHJcbiAgICBleHBlY3QoZmluZGluZ3MubWFwKGl0ZW0gPT4gaXRlbS5jb2RlKSkudG9Db250YWluKCdURUNITk9MT0dZX1BBUkFNRVRFUl9ERVBFTkRFTkNZX01JU01BVENIJyk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuc3RhdHVzZXMucGFyYW1ldGVycykudG9CZSgnSU5fUFJPR1JFU1MnKTtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5hcnRpZmFjdF9jaGVja3MucGFyYW1ldGVycy5jb21wbGV0ZSkudG9CZShmYWxzZSk7XHJcbiAgICBjb25zdCByZXF1aXJlZCA9IHdvcmtmbG93LmFydGlmYWN0X2NoZWNrcy5wYXJhbWV0ZXJzLnJlcXVpcmVkO1xyXG4gICAgZXhwZWN0KHJlcXVpcmVkLnByb2ZpbGVfdmFsdWVzKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IGRldmljZVNvdXJjZSA9IHRlY2hub2xvZ3kgPT09ICdJMkMnID8gJ2kyY19kZXZpY2Vfc291cmNlJyA6ICdtcl9kZXZpY2Vfc291cmNlJztcclxuICAgIC8vIFRoZXNlIHNjZW5hcmlvcyByZW1haW4gYmxvY2tlZCBieSByZWFsIG5hdGl2ZSBkZXBlbmRlbmNpZXMsIG5vdCBieSB0aGVcclxuICAgIC8vIGFic2VuY2Ugb2YgYSByZWFsIGRldmljZSBxdWFsaWZpY2F0aW9uIG9yIGZhYnJpY2F0ZWQgc291cmNlIGlkZW50aWZpZXIuXHJcbiAgICBleHBlY3QocmVxdWlyZWQpLm5vdC50b0hhdmVQcm9wZXJ0eShkZXZpY2VTb3VyY2UsIGZhbHNlKTtcclxuICAgIGNvbnN0IG5hdGl2ZVRlY2hub2xvZ3kgPSB0ZWNobm9sb2d5ID09PSAnSTJDJyA/ICdpMmMnIDogJ21vZGJ1c19ydHUnO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnNbbmF0aXZlVGVjaG5vbG9neV0udmFsdWVzKVxyXG4gICAgICAubm90LnRvSGF2ZVByb3BlcnR5KGRldmljZVNvdXJjZSk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuYXJ0aWZhY3RfY2hlY2tzLnBhcmFtZXRlcnMucHJvZmlsZV9maW5kaW5ncy5zb21lKChmaW5kaW5nOiB7Y29kZTogc3RyaW5nfSkgPT5cclxuICAgICAgZmluZGluZy5jb2RlID09PSAnVEVDSE5PTE9HWV9QQVJBTUVURVJfREVQRU5ERU5DWV9NSVNNQVRDSCcpKS50b0JlKHRydWUpO1xyXG4gICAgY29uc3QgZXZpZGVuY2VSZXZpZXcgPSBkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7bmFtZTogJ0Jsb2NraWVyZW5kZSBQcmVmbGlnaHQtQmVmdW5kZSd9KTtcclxuICAgIGF3YWl0IGV4cGVjdChldmlkZW5jZVJldmlldykudG9Db250YWluVGV4dCh0ZWNobm9sb2d5ID09PSAnSTJDJyA/ICdpMmNfcHVsbHVwX29obXMnIDogJ21yX3BkdV9ieXRlcycpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGV2aWRlbmNlUmV2aWV3LmdldEJ5Um9sZSgnbGluaycsIHtuYW1lOiAnQmV0cm9mZmVuZSBBbmdhYmVuIGJlYXJiZWl0ZW4nfSkuZmlyc3QoKSlcclxuICAgICAgLnRvSGF2ZUF0dHJpYnV0ZSgnaHJlZicsIG5ldyBSZWdFeHAoYG1vZGU9cGFyYW1ldGVycy4qcHJvamVjdD0ke3Byb2plY3R9YCkpO1xyXG4gICAgLy8gUmVjaGVja2luZyBwZXJzaXN0ZWQgZmluZGluZ3MgbXVzdCB1c2UgdGhlIGV4aXN0aW5nIHJlcXVlc3QsIGFuZCBtdXN0XHJcbiAgICAvLyBuZXZlciByZWxlYXNlIHVuY2hhbmdlZCBpbnZhbGlkIG5hdGl2ZSB2YWx1ZXMgb3IgaW52ZW50IGRldmljZSBldmlkZW5jZS5cclxuICAgIGNvbnN0IGNvbnRpbnVlZCA9IHBhZ2Uud2FpdEZvclJlcXVlc3QocmVxdWVzdCA9PiBuZXcgVVJMKHJlcXVlc3QudXJsKCkpLnBhdGhuYW1lID09PSAnL2FwaS9hZ2VudC9jaGF0J1xyXG4gICAgICAmJiByZXF1ZXN0Lm1ldGhvZCgpID09PSAnUE9TVCcgJiYgcmVxdWVzdC5wb3N0RGF0YUpTT04oKT8ud2l6YXJkX2NvbW1hbmQ/LmFjdGlvbiA9PT0gJ0NPTlRJTlVFJyk7XHJcbiAgICBhd2FpdCBldmlkZW5jZVJldmlldy5nZXRCeVJvbGUoJ2J1dHRvbicsIHtuYW1lOiAnR2VzcGVpY2hlcnRlIEFuZ2FiZW4gZXJuZXV0IHByw7xmZW4gJiBmb3J0c2V0emVuJywgZXhhY3Q6IHRydWV9KS5jbGljaygpO1xyXG4gICAgY29uc3QgY29tbWFuZCA9IChhd2FpdCBjb250aW51ZWQpLnBvc3REYXRhSlNPTigpLndpemFyZF9jb21tYW5kO1xyXG4gICAgZXhwZWN0KGNvbW1hbmQucnVuX2lkKS50b0JlKHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnJ1bl9pZCk7XHJcbiAgICBleHBlY3QoY29tbWFuZC5yZXF1ZXN0X3JldmlzaW9uKS50b0JlKHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnJlcXVlc3RfcmV2aXNpb24pO1xyXG4gICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgICBjb25zdCBuZXh0ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgIHJldHVybiBuZXh0LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnN0YXRlID09PSAnQkxPQ0tFRCdcclxuICAgICAgICAmJiBuZXh0LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnVwZGF0ZWRfYXQgIT09IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnVwZGF0ZWRfYXQ7XHJcbiAgICB9LCB7dGltZW91dDogNjBfMDAwfSkudG9CZSh0cnVlKTtcclxuICAgIGNvbnN0IHJlY2hlY2tlZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93Jyk7XHJcbiAgICBleHBlY3QocmVjaGVja2VkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnJ1bl9pZCkudG9CZShjb21tYW5kLnJ1bl9pZCk7XHJcbiAgICBleHBlY3QocmVjaGVja2VkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLnJlcXVlc3RfcmV2aXNpb24pLnRvQmUoY29tbWFuZC5yZXF1ZXN0X3JldmlzaW9uKTtcclxuICAgIGV4cGVjdChyZWNoZWNrZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24uYmxvY2tpbmdfZmluZGluZ3MubWFwKChpdGVtOiB7Y29kZTogc3RyaW5nfSkgPT4gaXRlbS5jb2RlKSlcclxuICAgICAgLnRvQ29udGFpbignVEVDSE5PTE9HWV9QQVJBTUVURVJfREVQRU5ERU5DWV9NSVNNQVRDSCcpO1xyXG4gICAgZXhwZWN0KHJlY2hlY2tlZC5wYXJhbWV0ZXJzKS50b0VxdWFsKHdvcmtmbG93LnBhcmFtZXRlcnMpO1xyXG4gICAgZXhwZWN0KHJlY2hlY2tlZC5zdGF0dXNlcy5wYXJhbWV0ZXJzKS50b0JlKCdJTl9QUk9HUkVTUycpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHtuYW1lOiAnRmVydGlnIHN0ZWxsZW4nLCBleGFjdDogdHJ1ZX0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5zdGF0dXNlcy5zaW11bGF0aW9uKS50b0JlKCdFTVBUWScpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGV4cGVjdCh3b3JrZmxvdy5wYXJhbWV0ZXJzLnJhdGVfcmV2aWV3X3Byb3Bvc2Fscy5pMmMuc3RhdHVzKS50b0JlKCdSRVZJRVdfUkVRVUlSRUQnKTtcclxuICAgICAgZXhwZWN0KHdvcmtmbG93LnBhcmFtZXRlcnMucGFyYW1ldGVyX3Byb3ZlbmFuY2UuYml0cmF0ZS5zb3VyY2UpLnRvQmUoJ1RFQ0hOT0xPR1lfUFJPRklMRV9SRVZJRVdfUFJPUE9TQUwnKTtcclxuICAgIH1cclxuICAgIGNvbnN0IGludGVyZmFjZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1pbnRlcmZhY2VzJyk7XHJcbiAgICBleHBlY3QoaW50ZXJmYWNlcy5sZW5ndGgpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoNyk7XHJcbiAgICBleHBlY3QoaW50ZXJmYWNlcy5ldmVyeShpdGVtID0+ICEvYXV0b21vdGl2ZXxjYW58bGluL2kudGVzdChpdGVtLnRlY2hub2xvZ3kpKSkudG9CZSh0cnVlKTtcclxuICAgIGNvbnN0IGhhcmR3YXJlID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICAgIGV4cGVjdChoYXJkd2FyZS5ldmVyeShpdGVtID0+IGl0ZW0uZG9tYWluICE9PSAnYXV0b21vdGl2ZScpKS50b0JlKHRydWUpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGNvbnN0IHNpZ25hbHMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyk7XHJcbiAgICAgIGV4cGVjdChzaWduYWxzLnNvbWUoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdUZW1wZXJhdHVyX1RlbXBlcmF0dXJzZW5zb3IxJyAmJiBpdGVtLnVuaXQgPT09ICdkZWdDJykpLnRvQmUodHJ1ZSk7XHJcbiAgICB9XHJcbiAgICBleHBlY3QoKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnMpLnRvSGF2ZUxlbmd0aCgwKTtcclxuICAgIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnbm9uYXV0b21vdGl2ZS1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCB0ZWNobm9sb2d5LCBmaW5kaW5ncyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICB9KTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gc3RhcnRDYXB0dXJlZExhcmdlV2l6YXJkKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZykge1xyXG4gIGNvbnN0IHJ1bklkID0gcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IG9yaWdpbmFsID0gYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2UtNTAtMjUwLTI1MC50eHQnLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpO1xyXG4gIGNvbnN0IG1ldGFkYXRhID0gSlNPTi5wYXJzZShhd2FpdCByZWFkRmlsZShuZXcgVVJMKCcuL2ZpeHR1cmVzL3dpemFyZC1sYXJnZS01MC0yNTAtMjUwLmpzb24nLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpKTtcclxuICBjb25zdCBiYXNlbGluZSA9IEpTT04ucGFyc2UoYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2Utc2lnbmFsLWNvbnRyYWN0cy5qc29uJywgaW1wb3J0Lm1ldGEudXJsKSwgJ3V0ZjgnKSk7XHJcbiAgY29uc3QgcHJvbXB0ID0gb3JpZ2luYWwucmVwbGFjZSgvXi0gTGF1Zi1JRDouKiQvbSwgJy0gTGF1Zi1JRDogJyArIHJ1bklkKTtcclxuICBhd2FpdCByZXZpZXdWaXJ0dWFsVHJhbnNwb3J0cyhwYWdlLCBwcm9qZWN0LCB0cnVlKTtcclxuICAvLyBSZXBsYXkgdGhlIGNhcHR1cmVkLCBhbHJlYWR5IGNvbmZpcm1lZCBpbnB1dCB0aHJvdWdoIHRoZSBub3JtYWwgU1RBUlQgQVBJLlxyXG4gIC8vIEFsbCBwcm9wb3NhbCBpbnNwZWN0aW9uLCBhcHByb3ZhbCwgY29udGludWF0aW9uIGFuZCByZWxvYWRzIGJlbG93IHVzZSBVSS5cclxuICBjb25zdCBzdGFydGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY2hhdCcsIHtcclxuICAgIGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSwgdGltZW91dDogMjQwXzAwMCxcclxuICAgIGRhdGE6IHsgcHJvbXB0LCB3aXphcmRfY29tbWFuZDogeyBhY3Rpb246ICdTVEFSVCcsIHJ1bl9pZDogcnVuSWQsIG9wZXJhdGlvbl9pZDogcmFuZG9tVVVJRCgpLFxyXG4gICAgICB0YXJnZXQ6ICdkYXRhX3NjaWVuY2VfaW50ZWxsaWdlbmNlJywgd2l6YXJkX2NvbnRleHQ6IHsgLi4ubWV0YWRhdGEud2l6YXJkX2NvbnRleHQsIHByb2plY3RfaWQ6IHByb2plY3QsIHJ1bl9pZDogcnVuSWQgfSB9IH0sXHJcbiAgfSk7XHJcbiAgaWYgKCFzdGFydGVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke3N0YXJ0ZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBzdGFydGVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICByZXR1cm4geyBydW5JZCwgbWV0YWRhdGEsIGJhc2VsaW5lIH07XHJcbn1cclxuXHJcbmZ1bmN0aW9uIGxhcmdlUGFyYW1ldGVyU2NlbmFyaW9zKCk6IFBhcmFtZXRlclJldHVyblNjZW5hcmlvW10ge1xyXG4gIHJldHVybiBbXHJcbiAgICB7dGVjaG5vbG9neTogJ2xpbicsIGZpZWxkczoge2xpbl9iaXRyYXRlX2JwczogJzE5LDIga2JpdC9zJ30sIG5hdGl2ZToge2xpbl9iaXRyYXRlX2JwczogMTlfMjAwfX0sXHJcbiAgICB7dGVjaG5vbG9neTogJ2Nhbl9mZCcsIGZpZWxkczoge2FyYml0cmF0aW9uX2JpdHJhdGU6ICc1MDAga2JpdC9zJywgZGF0YV9iaXRyYXRlOiAnMiBNYml0L3MnfSxcclxuICAgICAgbmF0aXZlOiB7YXJiaXRyYXRpb25fYml0cmF0ZTogNTAwXzAwMCwgZGF0YV9iaXRyYXRlOiAyXzAwMF8wMDB9fSxcclxuICAgIC8vIE1hdGNoIHRoZSB1bmNoYW5nZWQgY2FwdHVyZWQgMTAwLU1iaXQvcyByZXF1ZXN0IGFuZCBnZW51aW5lbHkgY2hhbmdlXHJcbiAgICAvLyB0aGUgMS1HYml0L3MgcHJvZmlsZSBzZWVkLCBzbyBzYXZpbmcgZXhlcmNpc2VzIHVzZXItdmFsdWUgcHJvdmVuYW5jZS5cclxuICAgIHt0ZWNobm9sb2d5OiAnZXRoZXJuZXQnLCBmaWVsZHM6IHtiaXRyYXRlOiAnMTAwIE1iaXQvcyd9LCBuYXRpdmU6IHtiaXRyYXRlOiAxMDBfMDAwXzAwMH0sIGVkaXRGaWVsZHM6IFsnYml0cmF0ZSddfSxcclxuICBdO1xyXG59XHJcblxyXG50ZXN0KCdleGFjdCBjb25maXJtZWQgNTAvMjUwLzI1MCByZXF1ZXN0IGNvbXBsZXRlcyB0aHJvdWdoIHJlYWwgd2l6YXJkIHJldmlldyBAbGFyZ2UnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgZXJyb3JzOiBzdHJpbmdbXSA9IFtdOyBwYWdlLm9uKCdwYWdlZXJyb3InLCBlcnJvciA9PiBlcnJvcnMucHVzaChlcnJvci5tZXNzYWdlKSk7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWxhcmdlLScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgeyBydW5JZCwgbWV0YWRhdGEsIGJhc2VsaW5lIH0gPSBhd2FpdCBzdGFydENhcHR1cmVkTGFyZ2VXaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgY29uc3QgcGFyYW1ldGVyUmV0dXJuUmV2aWV3czogc3RyaW5nW10gPSBbXTtcclxuICBjb25zdCBjb250aW51aXR5ID0gYXdhaXQgY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIGZhbHNlLCBbXSwgdHJ1ZSwgYmFzZWxpbmUuc2lnbmFscyxcclxuICAgIHVuZGVmaW5lZCwgZmFsc2UsIGFzeW5jIChwcm9wb3NhbElkLCBwcm9wb3NhbFR5cGUpID0+IHtcclxuICAgICAgaWYgKCFbJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcsICdXSVpBUkRfUk9VVElORycsICdXSVpBUkRfTkVUV09SS19UT1BPTE9HWSddLmluY2x1ZGVzKHByb3Bvc2FsVHlwZSkpIHJldHVybjtcclxuICAgICAgLy8gT25lIGZ1bGwgdGhyZWUtYnVzIGN5Y2xlIHJlbWFpbnMgaW50ZWdyYXRlZCBhdCBldmVyeSByZXZpZXcgc3RhZ2UuXHJcbiAgICAgIC8vIFJlcGVhdGVkIHRocmVlLXNlZWQgY292ZXJhZ2UgaGFzIGl0cyBvd24gcmVhbCBsYXJnZSBjYXNlcyBiZWxvdyxcclxuICAgICAgLy8gcHJlc2VydmluZyB0aGUgY29udHJhY3R1YWwgMjAtbWludXRlIHdob2xlLXdvcmtmbG93IGNhc2UgbGltaXQuXHJcbiAgICAgIC8vIEVhY2ggcGhhc2UgbXVzdCByZWFsbHkgZWRpdCB0aGUgc2VlZDogYW4gaWRlbnRpY2FsIHNhdmUgY29ycmVjdGx5XHJcbiAgICAgIC8vIGxlYXZlcyB0aGUgZXhpc3RpbmcgcHJvcG9zYWwgVkFMSURBVEVEIGluc3RlYWQgb2YgbWFraW5nIGl0IE9VVERBVEVELlxyXG4gICAgICBjb25zdCByZXZpZXdTZWVkID0gcHJvcG9zYWxUeXBlID09PSAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJyA/IDQxXHJcbiAgICAgICAgOiBwcm9wb3NhbFR5cGUgPT09ICdXSVpBUkRfUk9VVElORycgPyA0MyA6IDQyO1xyXG4gICAgICBhd2FpdCByZXBlYXRQYXJhbWV0ZXJSZXR1cm4ocGFnZSwgcHJvamVjdCwgcHJvcG9zYWxJZCwgbGFyZ2VQYXJhbWV0ZXJTY2VuYXJpb3MoKSwgW3Jldmlld1NlZWRdKTtcclxuICAgICAgcGFyYW1ldGVyUmV0dXJuUmV2aWV3cy5wdXNoKHByb3Bvc2FsVHlwZSk7XHJcbiAgICB9KTtcclxuICBleHBlY3QocGFyYW1ldGVyUmV0dXJuUmV2aWV3cykudG9FcXVhbChbJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcsICdXSVpBUkRfUk9VVElORycsICdXSVpBUkRfTkVUV09SS19UT1BPTE9HWSddKTtcclxuICBleHBlY3QoY29udGludWl0eS5ydW5JZCkudG9CZShydW5JZCk7XHJcbiAgY29uc3QgaGFyZHdhcmUgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gIGV4cGVjdChoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLmRldmljZV90eXBlID09PSAnU2Vuc29yQ29udHJvbGxlcicpKS50b0hhdmVMZW5ndGgoMjUwKTtcclxuICBleHBlY3QoaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5kZXZpY2VfdHlwZSA9PT0gJ0FjdHVhdG9yQ29udHJvbGxlcicpKS50b0hhdmVMZW5ndGgoMjUwKTtcclxuICBleHBlY3QoaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5kZXZpY2VfdHlwZSA9PT0gJ0VDVScpLmxlbmd0aCkudG9CZUdyZWF0ZXJUaGFuT3JFcXVhbCg1MCk7XHJcbiAgY29uc3QgYXJ0aWZhY3RzID0gYXdhaXQgdmVyaWZ5QXJ0aWZhY3RzKHBhZ2UsIHByb2plY3QsIDE0MDQsIHVuZGVmaW5lZCwgdW5kZWZpbmVkLCB7XHJcbiAgICBsaW46IHtiaXRyYXRlOiAxOV8yMDB9LCBjYW5fZmQ6IHthcmJpdHJhdGlvbl9iaXRyYXRlOiA1MDBfMDAwLCBkYXRhX2JpdHJhdGU6IDJfMDAwXzAwMH0sXHJcbiAgICBldGhlcm5ldDoge2JpdHJhdGU6IDEwMF8wMDBfMDAwfSxcclxuICB9KTtcclxuICBjb25zdCBleGNsdWRlZFNpZ25hbElkcyA9IG5ldyBTZXQoYXJ0aWZhY3RzLmFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UudHJhbnNwb3J0X2V4Y2x1c2lvbnNcclxuICAgIC5mbGF0TWFwKChpdGVtOiB7IHNpZ25hbF9pZHM6IHN0cmluZ1tdIH0pID0+IGl0ZW0uc2lnbmFsX2lkcykpO1xyXG4gIGV4cGVjdChleGNsdWRlZFNpZ25hbElkcy5zaXplKS50b0JlKDIzNSk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50Lm9ic2VydmVkX3NpZ25hbF9jb3VudCkudG9CZSgxMTY5KTtcclxuICBhd2FpdCB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZSwgcHJvamVjdCwgYmFzZWxpbmUuc2lnbmFscyk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5qb2IpLnRvQmUoY29udGludWl0eS5yZXN0YXJ0ZWRKb2JJZCk7XHJcbiAgZXhwZWN0KGVycm9ycykudG9FcXVhbChbXSk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCBmaXh0dXJlOiBtZXRhZGF0YS5yZXF1ZXN0X3NoYTI1NiwgLi4uY29udGludWl0eSwgLi4uYXJ0aWZhY3RzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuXHJcbmZvciAoY29uc3QgdGFyZ2V0IG9mIFtcclxuICB7IGxhYmVsOiAnbW9kZWwnLCB0eXBlOiAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJywgc3RlcDogJ2VuZ2luZWVyaW5nX21vZGVsJyB9LFxyXG4gIHsgbGFiZWw6ICdyb3V0aW5nJywgdHlwZTogJ1dJWkFSRF9ST1VUSU5HJywgc3RlcDogJ3JvdXRpbmcnIH0sXHJcbiAgeyBsYWJlbDogJ3RvcG9sb2d5JywgdHlwZTogJ1dJWkFSRF9ORVRXT1JLX1RPUE9MT0dZJywgc3RlcDogJ25ldHdvcmtfZWRpdG9yJyB9LFxyXG5dKSB7XHJcbiAgdGVzdChgZXhhY3QgY29uZmlybWVkIDUwLzI1MC8yNTAgJHt0YXJnZXQubGFiZWx9IHBhcmFtZXRlciByZXR1cm4gcmV2aWV3IG9ubHkgQGxhcmdlLXJldHVybmAsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICAgIGNvbnN0IGVycm9yczogc3RyaW5nW10gPSBbXTsgcGFnZS5vbigncGFnZWVycm9yJywgZXJyb3IgPT4gZXJyb3JzLnB1c2goZXJyb3IubWVzc2FnZSkpO1xyXG4gICAgY29uc3QgcHJvamVjdCA9IGBuaXMtZTJlLWxhcmdlLXJldHVybi0ke3RhcmdldC5sYWJlbH0tYCArIHJhbmRvbVVVSUQoKTtcclxuICAgIGNvbnN0IHsgcnVuSWQsIG1ldGFkYXRhLCBiYXNlbGluZSB9ID0gYXdhaXQgc3RhcnRDYXB0dXJlZExhcmdlV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCBmYWxzZSwgW10sIGZhbHNlLCBiYXNlbGluZS5zaWduYWxzLFxyXG4gICAgICB1bmRlZmluZWQsIGZhbHNlLCBhc3luYyAocHJvcG9zYWxJZCwgcHJvcG9zYWxUeXBlKSA9PiB7XHJcbiAgICAgICAgaWYgKHByb3Bvc2FsVHlwZSAhPT0gdGFyZ2V0LnR5cGUpIHJldHVybjtcclxuICAgICAgICBhd2FpdCByZXBlYXRQYXJhbWV0ZXJSZXR1cm4ocGFnZSwgcHJvamVjdCwgcHJvcG9zYWxJZCwgbGFyZ2VQYXJhbWV0ZXJTY2VuYXJpb3MoKSk7XHJcbiAgICAgICAgcmV0dXJuICdTVE9QX0FGVEVSX1JFVklFVyc7XHJcbiAgICAgIH0pO1xyXG4gICAgZXhwZWN0KGNvbnRpbnVpdHkucnVuSWQpLnRvQmUocnVuSWQpO1xyXG4gICAgZXhwZWN0KGNvbnRpbnVpdHkucmV2aWV3T25seT8ucHJvcG9zYWxUeXBlKS50b0JlKHRhcmdldC50eXBlKTtcclxuICAgIGNvbnN0IHdvcmtmbG93ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24pLnRvTWF0Y2hPYmplY3QoeyBydW5faWQ6IHJ1bklkLCBzdGF0ZTogJ1JFVklFV19SRVFVSVJFRCcsIHN0ZXA6IHRhcmdldC5zdGVwIH0pO1xyXG4gICAgZXhwZWN0KGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzLnNpbXVsYXRpb24pKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IHByb3Bvc2FsID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7Y29udGludWl0eS5yZXZpZXdPbmx5IS5wcm9wb3NhbElkfT92aWV3PXN0YXR1c2ApO1xyXG4gICAgZXhwZWN0KHByb3Bvc2FsLmRhdGEuc3RhdHVzKS50b0JlKCdWQUxJREFURUQnKTtcclxuICAgIGV4cGVjdChlcnJvcnMpLnRvRXF1YWwoW10pO1xyXG4gICAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdyZXZpZXctb25seS1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCBmaXh0dXJlOiBtZXRhZGF0YS5yZXF1ZXN0X3NoYTI1NixcclxuICAgICAgY292ZXJhZ2U6ICdSRVZJRVdfQ09OVElOVUlUWV9PTkxZJywgY3ljbGVzOiAzLCB0ZWNobm9sb2dpZXM6IFsnbGluJywgJ2Nhbl9mZCcsICdldGhlcm5ldCddLCAuLi5jb250aW51aXR5IH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gIH0pO1xyXG59XHJcblxyXG50ZXN0KCdhIHJlYWwgQU1FTkQgYWZ0ZXIgbW9kZWwgYXBwcm92YWwgYWRkcyB0aGUgcmVxdWVzdGVkIHNlbnNvciBhbmQgcmV1c2VzIGl0cyBuZXR3b3JrcyBAYW1lbmQnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWFtZW5kLScgKyByYW5kb21VVUlEKCk7XHJcbiAgYXdhaXQgcmV2aWV3VmlydHVhbFRyYW5zcG9ydHMocGFnZSwgcHJvamVjdCk7XHJcbiAgY29uc3QgcnVuSWQgPSByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgZ3JhcGggPSBbXHJcbiAgICB7IGNsdXN0ZXJfaWQ6ICdkcml2ZScsIG5ldHdvcmtfaWQ6ICdjYW5fZmQnLCBuZXR3b3JrX2xhYmVsOiAnQ0FOLUZEJywgYnVzX25hbWU6ICdEcml2ZScsXHJcbiAgICAgIGNvbnRyb2xsZXJzOiBbeyBlY3U6ICdNb3RvcnN0ZXVlcnVuZycsIHNlbnNvcnM6IFtdIGFzIHN0cmluZ1tdLCBhY3R1YXRvcnM6IFtdIH1dLFxyXG4gICAgICBobWlfcm91dGVzOiBbeyBzb3VyY2U6ICdNb3RvcnN0ZXVlcnVuZycsIHRhcmdldDogJ0FuemVpZ2UnIH0sIHsgc291cmNlOiAnQW56ZWlnZScsIHRhcmdldDogJ01vdG9yc3RldWVydW5nJyB9LFxyXG4gICAgICAgIHsgc291cmNlOiAnU3lzdGVtJywgdGFyZ2V0OiAnQW56ZWlnZScgfV0gfSxcclxuICAgIHsgY2x1c3Rlcl9pZDogJ2Rpc3BsYXknLCBuZXR3b3JrX2lkOiAnZXRoZXJuZXQnLCBuZXR3b3JrX2xhYmVsOiAnRXRoZXJuZXQnLCBidXNfbmFtZTogJ0Rpc3BsYXknLFxyXG4gICAgICBjb250cm9sbGVyczogW3sgZWN1OiAnQW56ZWlnZScsIHNlbnNvcnM6IFtdIGFzIHN0cmluZ1tdLCBhY3R1YXRvcnM6IFtdIH1dIH0sXHJcbiAgXTtcclxuICBjb25zdCBwcm9tcHQgPSBgU3RydWt0dXJpZXJ0ZSBWb3JnYWJlbiBmdWVyIGRlbiBFbmdpbmVlcmluZy1BZ2VudGVuOlxyXG4tIExhdWYtSUQ6ICR7cnVuSWR9XHJcbi0gSW5kdXN0cmllOiBBdXRvbW90aXZlXHJcbi0gTmV0endlcmt0ZWNobm9sb2dpZW46IENBTi1GRCAoY2FuX2ZkKTsgRXRoZXJuZXQgKGV0aGVybmV0KVxyXG5DQU4tRkQ6IDUwMCBrYml0L3MgYXJiaXRyYXRpb24sIDIgTWJpdC9zIGRhdGFcclxuQ0FOOiA1MDAga2JpdC9zXHJcbkV0aGVybmV0OiAxMDAgTWJpdC9zXHJcbi0gSGFyZHdhcmUtU29sbHdlcnRlOiB7XCJnYXRld2F5c1wiOjEsXCJlY3VzXCI6MixcInNlbnNvcnNcIjowLFwiYWN0dWF0b3JzXCI6MH1cclxuLSBTeXN0ZW1jbHVzdGVyLUdyYXBoOiAke0pTT04uc3RyaW5naWZ5KGdyYXBoKX1cclxuS29ua3JldGUgQXVmZ2FiZSBkZXMgTnV0emVycywgcGVyIFdpemFyZC1VZWJlcm5laG1lbiBiZXN0YWV0aWd0OlxyXG5Nb3RvcnN0ZXVlcnVuZyB1bmQgQW56ZWlnZSBtaXQgZWluZW0gemVudHJhbGVuIEdhdGV3YXkgU3lzdGVtIHZlcmJpbmRlbi5gO1xyXG4gIGNvbnN0IHN0YXJ0ZWQgPSBhd2FpdCBwYWdlLnJlcXVlc3QucG9zdCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jaGF0Jywge1xyXG4gICAgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiAxMjBfMDAwLFxyXG4gICAgZGF0YTogeyBwcm9tcHQsIHdpemFyZF9jb21tYW5kOiB7IGFjdGlvbjogJ1NUQVJUJywgcnVuX2lkOiBydW5JZCwgb3BlcmF0aW9uX2lkOiByYW5kb21VVUlEKCksXHJcbiAgICAgIHRhcmdldDogJ2RhdGFfc2NpZW5jZV9pbnRlbGxpZ2VuY2UnLCB3aXphcmRfY29udGV4dDogeyBwcm9qZWN0X2lkOiBwcm9qZWN0LCBydW5faWQ6IHJ1bklkLFxyXG4gICAgICAgIHByb2plY3RfbmFtZTogJ0UyRSBhbWVuZG1lbnQnLCBzY29wZV9pZHM6IHN0ZXBzLCBtb2RlOiAnZnVsbCcsXHJcbiAgICAgICAgcHJvY2Vzc19pZHM6IFsnZGVmYXVsdHMnLCAncmV2aWV3X2dhdGUnLCAnYXBwcm92ZV9hZnRlcl9hbGxvdyddLCB0YXNrOiAnTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UgYW4gU3lzdGVtJyB9IH0gfSxcclxuICB9KTtcclxuICBpZiAoIXN0YXJ0ZWQub2soKSkgdGhyb3cgbmV3IEVycm9yKGBIVFRQICR7c3RhcnRlZC5zdGF0dXMoKX06ICR7KGF3YWl0IHN0YXJ0ZWQudGV4dCgpKS5zbGljZSgwLCA0MDAwKX1gKTtcclxuICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGxldCBvcmlnaW5hbE5ldHdvcmtzOiBzdHJpbmdbXSA9IFtdO1xyXG4gIGNvbnN0IGFtZW5kID0gYXN5bmMgKCkgPT4ge1xyXG4gICAgb3JpZ2luYWxOZXR3b3JrcyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpKS5wYXJhbWV0ZXJzLm5ldHdvcmtzXHJcbiAgICAgIC5tYXAoKGl0ZW06IHsgaWQ6IHN0cmluZyB9KSA9PiBpdGVtLmlkKS5zb3J0KCk7XHJcbiAgICBleHBlY3Qob3JpZ2luYWxOZXR3b3JrcykudG9IYXZlTGVuZ3RoKDIpO1xyXG4gICAgZ3JhcGhbMF0uY29udHJvbGxlcnNbMF0uc2Vuc29ycy5wdXNoKCdNb3RvclRlbXBlcmF0dXJlJyk7XHJcbiAgICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pO1xyXG4gICAgY29uc3QgZXhwYW5kID0gZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgICBhd2FpdCBleHBlY3QoZXhwYW5kKS50b0JlRW5hYmxlZCh7IHRpbWVvdXQ6IDEyMF8wMDAgfSk7XHJcbiAgICBhd2FpdCBleHBhbmQuY2xpY2soKTtcclxuICAgIGNvbnN0IGZpZWxkID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcmfDpG56ZW4nLCBleGFjdDogdHJ1ZSB9KS5nZXRCeVJvbGUoJ3RleHRib3gnKTtcclxuICAgIGF3YWl0IGZpZWxkLmZpbGwoJ0VyZ8OkbnplIE1vdG9yVGVtcGVyYXR1cmUgYWxzIFNlbnNvciBkZXIgTW90b3JzdGV1ZXJ1bmcuIERpZSB2b2xsc3TDpG5kaWdlIGFrdHVhbGlzaWVydGUgRnJlaWdhYmUgbGF1dGV0OlxcbidcclxuICAgICAgKyAnLSBIYXJkd2FyZS1Tb2xsd2VydGU6IHtcImdhdGV3YXlzXCI6MSxcImVjdXNcIjoyLFwic2Vuc29yc1wiOjEsXCJhY3R1YXRvcnNcIjowfVxcbidcclxuICAgICAgKyAnLSBTeXN0ZW1jbHVzdGVyLUdyYXBoOiAnICsgSlNPTi5zdHJpbmdpZnkoZ3JhcGgpKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8Okbnp1bmcgYW5hbHlzaWVyZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGZpZWxkKS5ub3QudG9CZVZpc2libGUoeyB0aW1lb3V0OiAxMjBfMDAwIH0pO1xyXG4gIH07XHJcbiAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCBmYWxzZSwgWydNb3RvcnN0ZXVlcnVuZycsICdBbnplaWdlJ10sIGZhbHNlLCB1bmRlZmluZWQsIGFtZW5kKTtcclxuICBjb25zdCBoYXJkd2FyZSA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgY29uc3Qgb3duZXIgPSBoYXJkd2FyZS5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnTW90b3JzdGV1ZXJ1bmcnKTtcclxuICBjb25zdCBzZW5zb3JzID0gaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnTW90b3JUZW1wZXJhdHVyZScpO1xyXG4gIGV4cGVjdChzZW5zb3JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KHNlbnNvcnNbMF0uaWRlbnRpdHkuc3lzdGVtX293bmVyX2lkKS50b0JlKG93bmVyLmlkKTtcclxuICBjb25zdCBzZW5zb3JOZXR3b3JrID0gJ0RyaXZlLUlPLW1vdG9yc3RldWVydW5nLWNhbi1mZC1TMDEnO1xyXG4gIGNvbnN0IG5ldHdvcmtzID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93JykpLnBhcmFtZXRlcnMubmV0d29ya3M7XHJcbiAgZXhwZWN0KG5ldHdvcmtzLm1hcCgoaXRlbTogeyBpZDogc3RyaW5nIH0pID0+IGl0ZW0uaWQpLnNvcnQoKSkudG9FcXVhbChbLi4ub3JpZ2luYWxOZXR3b3Jrcywgc2Vuc29yTmV0d29ya10uc29ydCgpKTtcclxuICBleHBlY3QobmV3IFNldChuZXR3b3Jrcy5tYXAoKGl0ZW06IHsgbmFtZTogc3RyaW5nIH0pID0+IGl0ZW0ubmFtZSkpLnNpemUpLnRvQmUobmV0d29ya3MubGVuZ3RoKTtcclxuICBjb25zdCB0b3BvbG9neSA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9uZXR3b3JrLXZpZXcnKSkudG9wb2xvZ3k7XHJcbiAgY29uc3QgbG9jYWxFZGdlID0gdG9wb2xvZ3kuZWRnZXMuZmluZCgoZWRnZTogYW55KSA9PiBlZGdlLnBoeXNpY2FsTmV0d29ya0lkID09PSBzZW5zb3JOZXR3b3JrKTtcclxuICBleHBlY3QobG9jYWxFZGdlKS50b0JlVHJ1dGh5KCk7XHJcbiAgZXhwZWN0KGxvY2FsRWRnZS5idXMpLnRvQmUoJ2Nhbl9mZCcpO1xyXG4gIGV4cGVjdChPYmplY3QudmFsdWVzKGxvY2FsRWRnZS5yb3V0aW5nTWV0YWRhdGEpKS50b0NvbnRhaW5FcXVhbChleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7XHJcbiAgICBzb3VyY2U6IHNlbnNvcnNbMF0uaWQsIHRhcmdldDogb3duZXIuaWQsIGFwcHJvdmFsU3RhdGU6ICdBUFBST1ZFRCcsIHByb3RvY29sOiAnQ0FOX0ZEJyxcclxuICB9KSk7XHJcbiAgZm9yIChjb25zdCBbc2lkZSwgaGFyZHdhcmVJZF0gb2YgW1snc291cmNlJywgc2Vuc29yc1swXS5pZF0sIFsndGFyZ2V0Jywgb3duZXIuaWRdXSkge1xyXG4gICAgY29uc3Qgbm9kZSA9IHRvcG9sb2d5Lm5vZGVzLmZpbmQoKGl0ZW06IGFueSkgPT4gaXRlbS5pZCA9PT0gbG9jYWxFZGdlW3NpZGVdKTtcclxuICAgIGV4cGVjdChub2RlLmVuZ2luZWVyaW5nSWQpLnRvQmUoaGFyZHdhcmVJZCk7XHJcbiAgICBleHBlY3Qobm9kZS5wb3J0cykudG9Db250YWluRXF1YWwoZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoeyBpZDogbG9jYWxFZGdlW3NpZGUgKyAnUG9ydCddLFxyXG4gICAgICBidXM6ICdjYW5fZmQnLCBwaHlzaWNhbE5ldHdvcmtJZDogc2Vuc29yTmV0d29yayB9KSk7XHJcbiAgfVxyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCAxKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2FtZW5kbWVudC1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCAuLi5jb250aW51aXR5LCAuLi5hcnRpZmFjdHMgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG5cclxuLy8gUmVhbCBpc29sYXRlZCBVSSAtPiBwZXJzaXN0ZWQgbW9kZWwgYm91bmRhcnkgcmVncmVzc2lvbiwgbm90IG5pbmUtc3RhZ2UgY29tcGxldGlvbiBwcm9vZi5cclxudGVzdCgncmV2aWV3YWJsZSBmdW5jdGlvbmFsIFRYL1JYIE9GRiBzdXJ2aXZlcyByZXF1ZXN0IHJlbG9hZCBhbmQgY2Fub25pY2FsIG1vZGVsIGFkb3B0aW9uIEB0eHJ4JywgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS10eHJ4LScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdUWCBSWCBmdW5jdGlvbmFsIHBhcnRuZXJzJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwoJ0VyemV1Z2UgZWluIEF1dG9tb3RpdmUgQ0FOLUZEIE5ldHp3ZXJrIG1pdCBlaW5lbSBHYXRld2F5IFN5c3RlbSB1bmQgZGVuIEVDVXMgTW90b3JzdGV1ZXJ1bmcsIEdldHJpZWJlc3RldWVydW5nIHVuZCBFbGVrdHJvbW90b3JzdGV1ZXJ1bmcuIERpZSBiZXJlY2huZXRlbiBGdW5rdGlvbnNhdXNnw6RuZ2UgZGllbmVuIGRlciBBbnRyaWVic2tvb3JkaW5hdGlvbi4gQ29udHJvbGxlcnN0YXR1cyBibGVpYnQgaW50ZXJuLlxcbkNBTi1GRDogNTAwIGtiaXQvcyBhcmJpdHJhdGlvbiwgMiBNYml0L3MgZGF0YScpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdHZXLDpHRldW1mYW5nJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1dG9tb3RpdmUgLyBWZWhpY2xlIMO8YmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBmb3IgKGNvbnN0IFtsYWJlbCwgdmFsdWVdIG9mIFtbJ0dhdGV3YXlzJywgJzEnXSwgWydDb250cm9sbGVyJywgJzMnXSwgWydTZW5zb3JlbicsICcwJ10sIFsnQWt0b3JlbicsICcwJ11dKSBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbChgJHtsYWJlbH06IHZlcmJpbmRsaWNoZSBBbnphaGxgLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwodmFsdWUpO1xyXG4gIGNvbnN0IHR4cnggPSBkaWFsb2cubG9jYXRvcignZGV0YWlscycpLmZpbHRlcih7IGhhczogcGFnZS5sb2NhdG9yKCdzdW1tYXJ5JykuZmlsdGVyKHsgaGFzVGV4dDogL15UWFxcL1JYLyB9KSB9KS5maXJzdCgpO1xyXG4gIGF3YWl0IGV4cGVjdCh0eHJ4KS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IHR4cngubG9jYXRvcignc3VtbWFyeScpLmNsaWNrKCk7XHJcbiAgY29uc3Qgc2VsZWN0ZWQgPSB0eHJ4LmdldEJ5Um9sZSgnc3dpdGNoJywgeyBuYW1lOiAnTW90b3JEcmVobW9tZW50SXN0IOKGkiBHZXRyaWViZXN0ZXVlcnVuZycsIGV4YWN0OiB0cnVlIH0pO1xyXG4gIGF3YWl0IGV4cGVjdChzZWxlY3RlZCkudG9CZUNoZWNrZWQoKTsgYXdhaXQgc2VsZWN0ZWQudW5jaGVjaygpO1xyXG4gIGNvbnN0IHN0YXJ0UmVxdWVzdCA9IHBhZ2Uud2FpdEZvclJlcXVlc3QocmVxdWVzdCA9PiByZXF1ZXN0LnVybCgpLmVuZHNXaXRoKCcvYXBpL2FnZW50L2NoYXQnKSAmJiByZXF1ZXN0Lm1ldGhvZCgpID09PSAnUE9TVCcgJiYgcmVxdWVzdC5wb3N0RGF0YUpTT04oKT8ud2l6YXJkX2NvbW1hbmQ/LmFjdGlvbiA9PT0gJ1NUQVJUJyk7XHJcbiAgZm9yIChsZXQgc3RlcCA9IDA7IHN0ZXAgPCAxMDsgc3RlcCsrKSB7XHJcbiAgICBjb25zdCBidXR0b24gPSBkaWFsb2cubG9jYXRvcignLmVuZy1hZ2VudC1xdWVzdGlvbm5haXJlLWhlYWQnKS5nZXRCeVJvbGUoJ2J1dHRvbicpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGJ1dHRvbikudG9CZUVuYWJsZWQoKTsgY29uc3QgbGFiZWwgPSBhd2FpdCBidXR0b24uaW5uZXJUZXh0KCk7IGF3YWl0IGJ1dHRvbi5jbGljaygpO1xyXG4gICAgaWYgKGxhYmVsID09PSAnw5xiZXJuZWhtZW4nIHx8IGxhYmVsID09PSAnQXVmdHJhZyBzdGFydGVuJykgYnJlYWs7XHJcbiAgfVxyXG4gIGNvbnN0IGNvbnRleHQgPSAoYXdhaXQgc3RhcnRSZXF1ZXN0KS5wb3N0RGF0YUpTT04oKS53aXphcmRfY29tbWFuZC53aXphcmRfY29udGV4dDtcclxuICBjb25zdCBzdWJtaXR0ZWQgPSBjb250ZXh0LnN5c3RlbV9jbHVzdGVyX2Fzc2lnbm1lbnRzLmZsYXRNYXAoKGNsdXN0ZXI6IGFueSkgPT4gY2x1c3Rlci5mdW5jdGlvbmFsX3JvdXRlcyA/PyBbXSk7XHJcbiAgY29uc3Qgb2ZmID0gc3VibWl0dGVkLmZpbmQoKHJvdXRlOiBhbnkpID0+IHJvdXRlLnNvdXJjZSA9PT0gJ01vdG9yc3RldWVydW5nJyAmJiByb3V0ZS50YXJnZXQgPT09ICdHZXRyaWViZXN0ZXVlcnVuZycpO1xyXG4gIGV4cGVjdChvZmYuc2lnbmFscykudG9FcXVhbChbXSk7IGV4cGVjdChvZmYuZXhjbHVkZWRfc2lnbmFscykudG9FcXVhbChbJ01vdG9yRHJlaG1vbWVudElzdCddKTtcclxuICBsZXQgcHJvcG9zYWw6IGFueTtcclxuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICBjb25zdCBjb252ZXJzYXRpb24gPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKTtcclxuICAgIGlmICghY29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsKSByZXR1cm4gZmFsc2U7XHJcbiAgICBwcm9wb3NhbCA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtjb252ZXJzYXRpb24uZGF0YS5hY3RpdmVfcHJvcG9zYWx9YCkpLmRhdGE7XHJcbiAgICByZXR1cm4gcHJvcG9zYWwucHJvcG9zYWxfdHlwZSA9PT0gJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCc7XHJcbiAgfSwgeyB0aW1lb3V0OiAxODBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTsgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBjb25zdCBmaW5kaW5ncyA9IHByb3Bvc2FsLnZhbGlkYXRpb25fcmVzdWx0LmZpbmRpbmdzLmZpbHRlcigoaXRlbTogYW55KSA9PiBpdGVtLmNvZGUgPT09ICdDQVBBQ0lUWV9VTlZFUklGSUVEJyk7XHJcbiAgaWYgKGZpbmRpbmdzLmxlbmd0aCkge1xyXG4gICAgY29uc3QgcmV2aWV3ID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ1Byw7xmYmVmdW5kZSBkZXMgVm9yc2NobGFncycgfSk7XHJcbiAgICBhd2FpdCBleHBlY3QocmV2aWV3KS50b0NvbnRhaW5UZXh0KGAke3Byb3Bvc2FsLnZhbGlkYXRpb25fcmVzdWx0LmZpbmRpbmdzLmxlbmd0aH0gUHLDvGZiZWZ1bmRlYCk7XHJcbiAgICBhd2FpdCBleHBlY3QocmV2aWV3LmdldEJ5Um9sZSgnbGluaycsIHsgbmFtZTogJ1RlY2hub2xvZ2llcGFyYW1ldGVyIGJlYXJiZWl0ZW4gdW5kIGJlc3TDpHRpZ2VuJyB9KS5maXJzdCgpKS50b0hhdmVBdHRyaWJ1dGUoJ2hyZWYnLCBuZXcgUmVnRXhwKGBwcm9qZWN0PSR7cHJvamVjdH1gKSk7XHJcbiAgICBhd2FpdCByZXZpZXcubG9jYXRvcignc3VtbWFyeScpLmZpcnN0KCkuY2xpY2soKTsgYXdhaXQgZXhwZWN0KHJldmlldy5nZXRCeVJvbGUoJ25hdmlnYXRpb24nLCB7IG5hbWU6ICdCZWZ1bmRlIGR1cmNoYmzDpHR0ZXJuJyB9KS5maXJzdCgpKS50b0JlVmlzaWJsZSgpO1xyXG4gIH1cclxuICBjb25zdCBhcHBseSA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IHJlc3BvbnNlLnVybCgpLmluY2x1ZGVzKGAvcHJvcG9zYWxzLyR7cHJvcG9zYWwucHJvcG9zYWxfaWR9L2FwcHJvdmUtYXBwbHlgKSAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0ZyZWlnZWJlbiwgw7xiZXJuZWhtZW4gJiBmb3J0ZmFocmVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTsgZXhwZWN0KChhd2FpdCBhcHBseSkub2soKSkudG9CZSh0cnVlKTtcclxuICBjb25zdCBub2RlcyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgY29uc3QgbWVzc2FnZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdtZXNzYWdlcycpOyBjb25zdCBzaWduYWxzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnc2lnbmFscycpO1xyXG4gIGNvbnN0IHNpZ25hbCA9IHNpZ25hbHMuZmluZChpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ01vdG9yRHJlaG1vbWVudElzdCcpOyBleHBlY3Qoc2lnbmFsKS50b0JlVHJ1dGh5KCk7XHJcbiAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzLmZpbmQoaXRlbSA9PiBpdGVtLmlkID09PSBzaWduYWwubWVzc2FnZV9pZCk7XHJcbiAgY29uc3QgZ2VhcmJveCA9IG5vZGVzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdHZXRyaWViZXN0ZXVlcnVuZycpO1xyXG4gIGNvbnN0IGVtb3RvciA9IG5vZGVzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdFbGVrdHJvbW90b3JzdGV1ZXJ1bmcnKTtcclxuICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3Quc2NvcGUpLnRvQmUoJ0ZVTkNUSU9OX09VVFBVVCcpO1xyXG4gIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdC5jb25zdW1lcl9yZWZzKS5ub3QudG9Db250YWluKGdlYXJib3guaWQpO1xyXG4gIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdC5jb25zdW1lcl9yZWZzKS50b0NvbnRhaW4oZW1vdG9yLmlkKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2Z1bmN0aW9uYWwtdHhyeC1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCBvZmYsIG1lc3NhZ2UgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG4iXSwibWFwcGluZ3MiOiJBQUFBLFNBQVNBLElBQUksRUFBRUMsTUFBTSxRQUFtQixpQkFBaUI7QUFDekQsU0FBU0MsUUFBUSxRQUFRLGtCQUFrQjtBQUMzQyxTQUFTQyxVQUFVLFFBQVEsYUFBYTtBQUN4QyxTQUFTQyxZQUFZLFFBQVEsb0JBQW9CO0FBQ2pELFNBQVNDLHNCQUFzQixFQUFFQyxZQUFZLEVBQUVDLFdBQVcsUUFBUSxvQ0FBb0M7QUFDdEcsU0FBU0MsdUJBQXVCLFFBQVEscUNBQXFDO0FBRTdFLE1BQU1DLEtBQUssR0FBR0gsWUFBWTtBQUMxQixNQUFNSSxJQUFJLEdBQUdILFdBQVc7QUFFeEIsZUFBZUksaUJBQWlCQSxDQUFDQyxJQUFVLEVBQUU7RUFDM0MsTUFBTUMsUUFBUSxHQUFHRCxJQUFJLENBQUNFLE9BQU8sQ0FBQyx1Q0FBdUMsQ0FBQztFQUN0RSxJQUFJLE9BQU1ELFFBQVEsQ0FBQ0UsWUFBWSxDQUFDLGVBQWUsQ0FBQyxNQUFLLE9BQU8sRUFBRSxNQUFNRixRQUFRLENBQUNHLEtBQUssQ0FBQyxDQUFDO0VBQ3BGLE1BQU1DLEtBQUssR0FBR0wsSUFBSSxDQUFDRSxPQUFPLENBQUMsMkJBQTJCLENBQUM7RUFDdkQsSUFBSSxPQUFNRyxLQUFLLENBQUNGLFlBQVksQ0FBQyxNQUFNLENBQUMsTUFBSyxJQUFJLEVBQUUsTUFBTUUsS0FBSyxDQUFDSCxPQUFPLENBQUMsa0JBQWtCLENBQUMsQ0FBQ0UsS0FBSyxDQUFDLENBQUM7QUFDaEc7QUFF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