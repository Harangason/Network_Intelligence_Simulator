// 60966f2bf5e9381976c0e0be25c4857d4c5caa5b
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
});
async function assertEngineeringPageHealthy(page) {
  expect(workflowPageFailures.get(page), 'A working wizard overlay must not conceal a workflow HTTP 413.').toEqual([]);
  expect(await page.getByText('Engineering-API nicht erreichbar', {
    exact: true
  }).isVisible(), 'The underlying engineering page must not show its API error view.').toBe(false);
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
async function verifyArtifacts(page, project, minimumCanonicalSignals, internalController, expectedParameters) {
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
async function completeThroughWizard(page, project, restart, expectedHardware = [], crashSimulation = false, expectedSignals, afterFirstModelApplied, stopOnEvidenceBlock = false) {
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
    var _request$postDataJSON;
    return request.url().endsWith('/api/agent/chat') && request.method() === 'POST' && ((_request$postDataJSON = request.postDataJSON()) === null || _request$postDataJSON === void 0 || (_request$postDataJSON = _request$postDataJSON.wizard_command) === null || _request$postDataJSON === void 0 ? void 0 : _request$postDataJSON.action) === 'START';
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
  await common.locator('#seed').fill('42');
  await common.locator('#data_bitrate').fill('1 Mbit/s');
  const dataPrescaler = page.locator('#can_fd_data_prescaler');
  const dataDetails = dataPrescaler.locator('xpath=ancestor::details');
  await dataDetails.locator(':scope > summary').click();
  await dataPrescaler.fill('2');
  await page.getByRole('button', {
    name: 'Parameter speichern →',
    exact: true
  }).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  const stale = await readProject(page, project, `/api/engineering/agent/proposals/${pending}?view=status`);
  expect(stale.data.status).toBe('OUTDATED');
  expect(stale.data.canonical_ids).toEqual([]);
  expect(await allObjects(page, project, 'hardware-nodes')).toHaveLength(0);
  await page.reload();
  await expect(page.locator('#seed')).toHaveValue('42');
  await expect(page.locator('#data_bitrate')).toHaveValue('1 Mbit/s');
  const runBeforeReturn = (await readProject(page, project, '/api/engineering/workflow?view=summary')).context.agent_wizard_status.run_id;
  const starts = [];
  const trackStarts = request => {
    var _request$postDataJSON2;
    if (request.url().endsWith('/api/agent/chat') && request.method() === 'POST' && ((_request$postDataJSON2 = request.postDataJSON()) === null || _request$postDataJSON2 === void 0 || (_request$postDataJSON2 = _request$postDataJSON2.wizard_command) === null || _request$postDataJSON2 === void 0 ? void 0 : _request$postDataJSON2.action) === 'START') starts.push(request.postDataJSON());
  };
  page.on('request', trackStarts);
  let resumeRestore;
  const restorePause = new Promise(resolve => {
    resumeRestore = resolve;
  });
  const delayRestore = async route => {
    await restorePause;
    await route.continue();
  };
  await page.route('**/api/engineering/workflow?view=summary', delayRestore);
  await page.getByRole('button', {
    name: 'Zurück zum Auftrag',
    exact: true
  }).click();
  await expect(dialog).toBeVisible();
  try {
    await expect(dialog.getByRole('region', {
      name: 'Gespeicherten Auftrag wiederherstellen'
    })).toBeVisible();
    await expect(dialog).not.toContainText('Projektname: Schritt 1');
  } finally {
    resumeRestore();
  }
  await page.unrouteAll({
    behavior: 'wait'
  });
  const review = dialog.getByRole('region', {
    name: 'Engineering-Vorschlag'
  });
  await expect(review).toContainText('Geprüft · Freigabe offen');
  await expect(dialog).toContainText('Statusübersicht: Schritt 5 von 5');
  expect((await readProject(page, project, '/api/engineering/workflow?view=summary')).context.agent_wizard_status.run_id).toBe(runBeforeReturn);
  expect(await allObjects(page, project, 'hardware-nodes')).toHaveLength(0);
  expect(starts).toEqual([]);
  page.off('request', trackStarts);
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
  await reviewVirtualTransports(page, project);
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
  const continuity = await completeThroughWizard(page, project, false, [], true, baseline.signals);
  expect(continuity.runId).toBe(runId);
  const hardware = await allObjects(page, project, 'hardware-nodes');
  expect(hardware.filter(item => item.device_type === 'SensorController')).toHaveLength(250);
  expect(hardware.filter(item => item.device_type === 'ActuatorController')).toHaveLength(250);
  expect(hardware.filter(item => item.device_type === 'ECU').length).toBeGreaterThanOrEqual(50);
  const artifacts = await verifyArtifacts(page, project, 1404);
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
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmVhZEZpbGUiLCJyYW5kb21VVUlEIiwiZXhlY0ZpbGVTeW5jIiwiV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyIsIldJWkFSRF9TVEVQUyIsIldJWkFSRF9ET05FIiwicmV2aWV3VmlydHVhbFRyYW5zcG9ydHMiLCJzdGVwcyIsImRvbmUiLCJ3cml0ZVRpbWluZ3MiLCJNYXAiLCJ3b3JrZmxvd1BhZ2VGYWlsdXJlcyIsIldlYWtNYXAiLCJwcm9ncmVzc01pbGVzdG9uZXMiLCJiZWZvcmVFYWNoIiwicGFnZSIsImluZm8iLCJyb3dzIiwic2V0IiwidGVzdElkIiwicmVxdWVzdHMiLCJvbiIsInJlcXVlc3QiLCJpbmNsdWRlcyIsIm1ldGhvZCIsInJvdyIsInVybCIsInN0YXJ0ZWQiLCJEYXRlIiwibm93IiwicHVzaCIsInJlc3BvbnNlIiwiZ2V0Iiwic3RhdHVzIiwiVVJMIiwicGF0aG5hbWUiLCJkdXJhdGlvbl9tcyIsIl9yZXF1ZXN0JGZhaWx1cmUiLCJmYWlsdXJlIiwiZXJyb3JUZXh0IiwiYWZ0ZXJFYWNoIiwiYXR0YWNoIiwiYm9keSIsIkpTT04iLCJzdHJpbmdpZnkiLCJjb250ZW50VHlwZSIsImRlbGV0ZSIsInRvRXF1YWwiLCJhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5IiwiZ2V0QnlUZXh0IiwiZXhhY3QiLCJpc1Zpc2libGUiLCJ0b0JlIiwicmVhZFByb2plY3QiLCJwcm9qZWN0IiwicGF0aCIsInJlc3VsdCIsImhlYWRlcnMiLCJ0aW1lb3V0Iiwib2siLCJFcnJvciIsInRleHQiLCJzbGljZSIsImpzb24iLCJkaXNwb3NlIiwicmVhZFdhcm5pbmdSZXZpZXdTdGF0ZSIsIl92ZXJpZmllZCRjb250ZXh0JGFnZTIiLCJfdmVyaWZpZWQkY29udGV4dCRhZ2UzIiwiYXV0aG9yaXR5IiwicGFyYW1ldGVycyIsInZlcmlmaWVkIiwicHJvamVjdF9pZCIsImZpZWxkIiwiX3ZlcmlmaWVkJGNvbnRleHQkYWdlIiwiX2F1dGhvcml0eSRjb250ZXh0JGFnIiwiY29udGV4dCIsImFnZW50X2V4ZWN1dGlvbiIsInN0YXR1c2VzIiwicnVuX2lkIiwicmVxdWVzdF9yZXZpc2lvbiIsInByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsIiwib3BlbldpemFyZCIsImdvdG8iLCJ3YWl0VW50aWwiLCJkaWFsb2ciLCJnZXRCeVJvbGUiLCJuYW1lIiwidG9CZVZpc2libGUiLCJzdGVwIiwibG9jYXRvciIsInN0ZXBXaWR0aCIsImV2YWx1YXRlIiwiZWxlbWVudCIsImdldEJvdW5kaW5nQ2xpZW50UmVjdCIsIndpZHRoIiwiY2FyZHMiLCJhbGwiLCJ0b0hhdmVMZW5ndGgiLCJjYXJkIiwidG9CZUdyZWF0ZXJUaGFuIiwiYWxsT2JqZWN0cyIsInJlc291cmNlIiwiaXRlbXMiLCJvZmZzZXQiLCJsZW5ndGgiLCJyZXN0YXJ0QXBwbGljYXRpb24iLCJjcmFzaCIsImNvbnRhaW5lciIsInByb2Nlc3MiLCJlbnYiLCJOSVNfRTJFX0FQUF9DT05UQUlORVIiLCJ0b01hdGNoIiwiZG9ja2VyIiwiTklTX1RFU1RfRE9DS0VSIiwibGFiZWwiLCJlbmNvZGluZyIsInRyaW0iLCJwb2xsIiwidmVyaWZ5U2lnbmFsQ29udHJhY3RzIiwiZXhwZWN0ZWQiLCJoYXJkd2FyZSIsImZ1bmN0aW9ucyIsIm1lc3NhZ2VzIiwic2lnbmFscyIsIlByb21pc2UiLCJtYXAiLCJub2RlcyIsIml0ZW0iLCJpZCIsImZ1bmN0aW9uc0J5SWQiLCJtZXNzYWdlc0J5SWQiLCJjb250cmFjdHMiLCJzaWduYWwiLCJfcmVmIiwiX3NpZ25hbCRkYXRhJGVudW1fdmFsIiwiX3NpZ25hbCRkYXRhIiwiX3NpZ25hbCRzZW1hbnRpYyRzZW1hIiwiX3NpZ25hbCRzZW1hbnRpYyIsIl9zaWduYWwkY29uZmlndXJhdGlvbiIsIl9zaWduYWwkY29uZmlndXJhdGlvbjIiLCJtZXNzYWdlIiwibWVzc2FnZV9pZCIsInRvQmVUcnV0aHkiLCJyZWZlcmVuY2UiLCJjb25maWd1cmF0aW9uIiwiY29tbXVuaWNhdGlvbl9jb250cmFjdCIsInByb2R1Y2VyX3JlZiIsImZuIiwib3duZXIiLCJoYXJkd2FyZV9ub2RlX2lkIiwicHJvZHVjZXIiLCJkZXZpY2VfdHlwZSIsImtleSIsImpvaW4iLCJ0b0JlVW5kZWZpbmVkIiwiT2JqZWN0IiwiZnJvbUVudHJpZXMiLCJfc2lnbmFsJGZpZWxkIiwiZW51bV92YWx1ZXMiLCJkYXRhIiwic2VtYW50aWNfdHlwZSIsInNlbWFudGljIiwiZ2VuZXJhdGlvbl9yb2xlIiwidmVyaWZ5QXJ0aWZhY3RzIiwibWluaW11bUNhbm9uaWNhbFNpZ25hbHMiLCJpbnRlcm5hbENvbnRyb2xsZXIiLCJleHBlY3RlZFBhcmFtZXRlcnMiLCJfYXNzZXNzbWVudCRzY29wZV9jb3YiLCJ3b3JrZmxvdyIsImpvYkxpc3QiLCJzbmFwc2hvdHMiLCJrZXlzIiwic29ydCIsImhhcyIsImpvYnMiLCJzbmFwc2hvdCIsInNpbXVsYXRpb25zIiwiZmluZCIsImpvYl9pZCIsImZ1bGwiLCJkYXRhX2JpdHJhdGUiLCJjYW5fZmRfZGF0YV9wcmVzY2FsZXIiLCJydW50aW1lUGFyYW1ldGVycyIsInRvTWF0Y2hPYmplY3QiLCJjYW5GZE5ldHdvcmtzIiwibmV0d29ya3MiLCJmaWx0ZXIiLCJuZXR3b3JrIiwidGVjaG5vbG9neSIsImFzc2Vzc21lbnQiLCJzY29wZV9jb3ZlcmFnZSIsInNjb3BlX21vZGUiLCJjb21wbGV0ZSIsImNvbmZvcm1hbmNlIiwiZmFpbGVkX3JvdXRlX2NvdW50IiwidG9CZUdyZWF0ZXJUaGFuT3JFcXVhbCIsImV4Y2x1ZGVkIiwidHJhbnNwb3J0X2V4Y2x1c2lvbnMiLCJyb3V0aW5nIiwiZW5hYmxlZCIsImNvbnRyYWN0IiwiY29uc3VtZXJfcmVmcyIsInJlYXNvbl9jb2RlIiwicm9sZSIsImNvbnRyb2xsZXIiLCJzY29wZSIsImV4Y2x1ZGVkU2lnbmFscyIsIlNldCIsImZsYXRNYXAiLCJzaWduYWxfaWRzIiwib2JzZXJ2ZWRfc2lnbmFsX2NvdW50Iiwic2l6ZSIsInRyYWNlIiwiY291bnQiLCJldmVudHMiLCJzb21lIiwiam9iIiwicGFyYW1ldGVyX3Byb29mIiwic2F2ZWQiLCJzaW11bGF0aW9uX3JhdGVzIiwiYml0cmF0ZSIsImFyYml0cmF0aW9uX2JpdHJhdGUiLCJoYXJkd2FyZV9ldmlkZW5jZSIsInVuZGVmaW5lZCIsImNvbXBsZXRlVGhyb3VnaFdpemFyZCIsInJlc3RhcnQiLCJleHBlY3RlZEhhcmR3YXJlIiwiY3Jhc2hTaW11bGF0aW9uIiwiZXhwZWN0ZWRTaWduYWxzIiwiYWZ0ZXJGaXJzdE1vZGVsQXBwbGllZCIsInN0b3BPbkV2aWRlbmNlQmxvY2siLCJyZXZpZXdDb3VudCIsInJ1bklkIiwicmV2aWV3ZWQiLCJyZXN0YXJ0ZWRKb2JJZCIsIndhdGNoZG9nIiwicGVyZm9ybWFuY2UiLCJjaGVja3BvaW50IiwiX3dvcmtmbG93JGNvbnRleHQkYWdlIiwiX3dvcmtmbG93JGNvbnRleHQkYWdlMiIsIl9leGVjdXRpb24kYmxvY2tpbmdfZiIsIl9leGVjdXRpb24kbWVzc2FnZSIsInByb3Bvc2FsSWQiLCJyZWFkeVZlcnNpb24iLCJyZWFkeVNpbmNlIiwiaXNDaGVja3BvaW50IiwicmVtYWluaW5nIiwicHJvZ3Jlc3MiLCJvYnNlcnZlIiwiYWR2YW5jZWQiLCJhdCIsInRvSVNPU3RyaW5nIiwiZnJvbnRpZXIiLCJjb21wbGV0ZWRUaHJvdWdoIiwiZXhlY3V0aW9uIiwidmFsaWRhdGlvbiIsInJ1bm5pbmciLCJldmVyeSIsInN0YXRlIiwiY29udmVyc2F0aW9uIiwiYWN0aXZlX3Byb3Bvc2FsIiwiQm9vbGVhbiIsInJlY292ZXJhYmxlIiwidXBkYXRlZF9hdCIsImJ1dHRvbiIsImV2YWx1YXRlQWxsIiwiYnV0dG9ucyIsImRpc2FibGVkIiwiZ2V0Q2xpZW50UmVjdHMiLCJnZXRDb21wdXRlZFN0eWxlIiwidmlzaWJpbGl0eSIsImF0dGVtcHQiLCJ3YWl0Rm9yVGltZW91dCIsIk1hdGgiLCJtaW4iLCJibG9ja2luZ19maW5kaW5ncyIsImJlZm9yZVJldmlldyIsInByZWZsaWdodCIsIndhcm5pbmdzIiwiZmlyc3QiLCJzdGFydGVkV2FsbCIsImFwcHJvdmFsUmVzcG9uc2UiLCJ3YWl0Rm9yUmVzcG9uc2UiLCJjbGljayIsImFwcHJvdmVkIiwicmVjZWlwdCIsImFmdGVyUmV2aWV3IiwicHJvb2YiLCJiZWZvcmUiLCJhZnRlciIsInNuYXBzaG90SWQiLCJyZXF1ZXN0UHJvamVjdCIsInN1Ym1pdHRlZCIsInBvc3REYXRhSlNPTiIsImZpbmlzaGVkV2FsbCIsImNvbW1pdHRlZEF0IiwiY29tbWl0dGVkIiwiY29tbWl0V2FybmluZ1JldmlldyIsIm1hbnVhbFdhcm5pbmdBcHByb3ZhbCIsImFwcHJvdmFsSWRlbnRpdHkiLCJhcHByb3ZhbCIsIl9hd2FpdCRyZWFkUHJvamVjdCRjbyIsIm5vdCIsIl9jb252ZXJzYXRpb24kZGF0YSIsIl9wcm9wb3NhbCRkYXRhIiwicHJvcG9zYWwiLCJ2YWxpZGF0aW9uX3Jlc3VsdCIsInZpc2libGUiLCJpbm5lclRleHQiLCJlcnJvciIsIl9sYXRlc3QkY29udGV4dCRhZ2VudCIsImxhdGVzdCIsIl9sYXRlc3QkY29udGV4dCRhZ2VudDIiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQzIiwiX2xhdGVzdCRzdGF0dXNlcyIsImNhbmRpZGF0ZSIsInByb3Bvc2FsX3R5cGUiLCJjaGFuZ2VzIiwiY2hhbmdlIiwib2JqZWN0X3R5cGUiLCJhcnJheUNvbnRhaW5pbmciLCJhcHBseVJlc3BvbnNlIiwidG9CZUVuYWJsZWQiLCJhcHBsaWVkIiwiYWRkIiwiX2FtZW5kZWQkY29udGV4dCRhZ2VuIiwiYW1lbmRlZCIsIl9jdXJyZW50JGNvbnRleHQkYWdlbiIsImN1cnJlbnQiLCJyb3V0ZSIsImZ1bGZpbGwiLCJ0b0NvbnRhaW5UZXh0IiwiZ2V0QnlUaXRsZSIsImZpbGwiLCJnZXRCeUxhYmVsIiwidG9CZURpc2FibGVkIiwidW5yb3V0ZSIsInRvSGF2ZUNvdW50IiwiY2F0YWxvZyIsInRlY2hub2xvZ3lfY291bnQiLCJ0ZXN0SW5mbyIsImVycm9ycyIsInZhbHVlIiwic3RhcnRSZXF1ZXN0Iiwid2FpdEZvclJlcXVlc3QiLCJfcmVxdWVzdCRwb3N0RGF0YUpTT04iLCJlbmRzV2l0aCIsIndpemFyZF9jb21tYW5kIiwiYWN0aW9uIiwic3VibWl0IiwicmVxdWVzdGVkIiwid2l6YXJkX2NvbnRleHQiLCJ0ZWNobm9sb2dpZXMiLCJfYXdhaXQkcmVhZFByb2plY3QkY28yIiwicGVuZGluZyIsImNvbW1vbiIsInRvSGF2ZVZhbHVlIiwiZGF0YVByZXNjYWxlciIsImRhdGFEZXRhaWxzIiwic3RhbGUiLCJjYW5vbmljYWxfaWRzIiwicmVsb2FkIiwicnVuQmVmb3JlUmV0dXJuIiwiYWdlbnRfd2l6YXJkX3N0YXR1cyIsInN0YXJ0cyIsInRyYWNrU3RhcnRzIiwiX3JlcXVlc3QkcG9zdERhdGFKU09OMiIsInJlc3VtZVJlc3RvcmUiLCJyZXN0b3JlUGF1c2UiLCJyZXNvbHZlIiwiZGVsYXlSZXN0b3JlIiwiY29udGludWUiLCJ1bnJvdXRlQWxsIiwiYmVoYXZpb3IiLCJyZXZpZXciLCJvZmYiLCJjb250aW51aXR5IiwiYXJ0aWZhY3RzIiwic2VlZCIsImZpbmlzaGVkIiwiY2hlY2siLCJzZWxlY3RPcHRpb24iLCJyZWplY3RzIiwidG9UaHJvdyIsImZpbmRpbmdzIiwiY29kZSIsInRvQ29udGFpbiIsImFydGlmYWN0X2NoZWNrcyIsInJlcXVpcmVkIiwicHJvZmlsZV92YWx1ZXMiLCJkZXZpY2VTb3VyY2UiLCJ0b0hhdmVQcm9wZXJ0eSIsIm5hdGl2ZVRlY2hub2xvZ3kiLCJzaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucyIsInZhbHVlcyIsInByb2ZpbGVfZmluZGluZ3MiLCJmaW5kaW5nIiwiZXZpZGVuY2VSZXZpZXciLCJ0b0hhdmVBdHRyaWJ1dGUiLCJSZWdFeHAiLCJzaW11bGF0aW9uIiwicmF0ZV9yZXZpZXdfcHJvcG9zYWxzIiwiaTJjIiwicGFyYW1ldGVyX3Byb3ZlbmFuY2UiLCJzb3VyY2UiLCJpbnRlcmZhY2VzIiwiZG9tYWluIiwidW5pdCIsIm9yaWdpbmFsIiwiaW1wb3J0IiwibWV0YSIsIm1ldGFkYXRhIiwicGFyc2UiLCJiYXNlbGluZSIsInByb21wdCIsInJlcGxhY2UiLCJwb3N0Iiwib3BlcmF0aW9uX2lkIiwidGFyZ2V0IiwiZXhjbHVkZWRTaWduYWxJZHMiLCJmaXh0dXJlIiwicmVxdWVzdF9zaGEyNTYiLCJncmFwaCIsImNsdXN0ZXJfaWQiLCJuZXR3b3JrX2lkIiwibmV0d29ya19sYWJlbCIsImJ1c19uYW1lIiwiY29udHJvbGxlcnMiLCJlY3UiLCJzZW5zb3JzIiwiYWN0dWF0b3JzIiwiaG1pX3JvdXRlcyIsInByb2plY3RfbmFtZSIsInNjb3BlX2lkcyIsIm1vZGUiLCJwcm9jZXNzX2lkcyIsInRhc2siLCJvcmlnaW5hbE5ldHdvcmtzIiwiYW1lbmQiLCJleHBhbmQiLCJpZGVudGl0eSIsInN5c3RlbV9vd25lcl9pZCIsInNlbnNvck5ldHdvcmsiLCJ0b3BvbG9neSIsImxvY2FsRWRnZSIsImVkZ2VzIiwiZWRnZSIsInBoeXNpY2FsTmV0d29ya0lkIiwiYnVzIiwicm91dGluZ01ldGFkYXRhIiwidG9Db250YWluRXF1YWwiLCJvYmplY3RDb250YWluaW5nIiwiYXBwcm92YWxTdGF0ZSIsInByb3RvY29sIiwic2lkZSIsImhhcmR3YXJlSWQiLCJub2RlIiwiZW5naW5lZXJpbmdJZCIsInBvcnRzIiwidHhyeCIsImhhc1RleHQiLCJzZWxlY3RlZCIsInRvQmVDaGVja2VkIiwidW5jaGVjayIsIl9yZXF1ZXN0JHBvc3REYXRhSlNPTjMiLCJzeXN0ZW1fY2x1c3Rlcl9hc3NpZ25tZW50cyIsImNsdXN0ZXIiLCJfY2x1c3RlciRmdW5jdGlvbmFsX3IiLCJmdW5jdGlvbmFsX3JvdXRlcyIsImV4Y2x1ZGVkX3NpZ25hbHMiLCJhcHBseSIsInByb3Bvc2FsX2lkIiwiZ2VhcmJveCIsImVtb3RvciJdLCJzb3VyY2VzIjpbIndpemFyZC5zcGVjLnRzIl0sInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHRlc3QsIGV4cGVjdCwgdHlwZSBQYWdlIH0gZnJvbSAncGxheXdyaWdodC90ZXN0JztcclxuaW1wb3J0IHsgcmVhZEZpbGUgfSBmcm9tICdub2RlOmZzL3Byb21pc2VzJztcclxuaW1wb3J0IHsgcmFuZG9tVVVJRCB9IGZyb20gJ25vZGU6Y3J5cHRvJztcclxuaW1wb3J0IHsgZXhlY0ZpbGVTeW5jIH0gZnJvbSAnbm9kZTpjaGlsZF9wcm9jZXNzJztcclxuaW1wb3J0IHsgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZywgV0laQVJEX1NURVBTLCBXSVpBUkRfRE9ORSB9IGZyb20gJy4vc3VwcG9ydC93aXphcmQtcHJvZ3Jlc3Mtd2F0Y2hkb2cnO1xyXG5pbXBvcnQgeyByZXZpZXdWaXJ0dWFsVHJhbnNwb3J0cyB9IGZyb20gJy4vc3VwcG9ydC9uYXRpdmUtdHJhbnNwb3J0LWZpeHR1cmVzJztcclxuXHJcbmNvbnN0IHN0ZXBzID0gV0laQVJEX1NURVBTO1xyXG5jb25zdCBkb25lID0gV0laQVJEX0RPTkU7XHJcbnR5cGUgV3JpdGVUaW1pbmcgPSB7IHVybDogc3RyaW5nOyBzdGFydGVkOiBudW1iZXI7IGR1cmF0aW9uX21zPzogbnVtYmVyOyBzdGF0dXM/OiBudW1iZXI7IGZhaWx1cmU/OiBzdHJpbmcgfTtcclxuY29uc3Qgd3JpdGVUaW1pbmdzID0gbmV3IE1hcDxzdHJpbmcsIFdyaXRlVGltaW5nW10+KCk7XHJcbmNvbnN0IHdvcmtmbG93UGFnZUZhaWx1cmVzID0gbmV3IFdlYWtNYXA8UGFnZSwgc3RyaW5nW10+KCk7XHJcbmNvbnN0IHByb2dyZXNzTWlsZXN0b25lcyA9IG5ldyBNYXA8c3RyaW5nLCB1bmtub3duW10+KCk7XHJcblxyXG50ZXN0LmJlZm9yZUVhY2goYXN5bmMgKHsgcGFnZSB9LCBpbmZvKSA9PiB7XHJcbiAgY29uc3Qgcm93czogV3JpdGVUaW1pbmdbXSA9IFtdO1xyXG4gIHdyaXRlVGltaW5ncy5zZXQoaW5mby50ZXN0SWQsIHJvd3MpO1xyXG4gIHdvcmtmbG93UGFnZUZhaWx1cmVzLnNldChwYWdlLCBbXSk7XHJcbiAgcHJvZ3Jlc3NNaWxlc3RvbmVzLnNldChpbmZvLnRlc3RJZCwgW10pO1xyXG4gIGNvbnN0IHJlcXVlc3RzID0gbmV3IE1hcDxvYmplY3QsIFdyaXRlVGltaW5nPigpO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3QnLCByZXF1ZXN0ID0+IHtcclxuICAgIGlmICghWydQT1NUJywgJ1BVVCcsICdQQVRDSCcsICdERUxFVEUnXS5pbmNsdWRlcyhyZXF1ZXN0Lm1ldGhvZCgpKSkgcmV0dXJuO1xyXG4gICAgY29uc3Qgcm93ID0geyB1cmw6IHJlcXVlc3QudXJsKCksIHN0YXJ0ZWQ6IERhdGUubm93KCkgfTtcclxuICAgIHJvd3MucHVzaChyb3cpOyByZXF1ZXN0cy5zZXQocmVxdWVzdCwgcm93KTtcclxuICB9KTtcclxuICBwYWdlLm9uKCdyZXNwb25zZScsIHJlc3BvbnNlID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXNwb25zZS5yZXF1ZXN0KCkpO1xyXG4gICAgaWYgKHJvdykgcm93LnN0YXR1cyA9IHJlc3BvbnNlLnN0YXR1cygpO1xyXG4gICAgaWYgKHJlc3BvbnNlLnN0YXR1cygpID09PSA0MTMgJiYgL15cXC9hcGlcXC9lbmdpbmVlcmluZ1xcL3dvcmtmbG93KD86XFwvfCQpLy50ZXN0KG5ldyBVUkwocmVzcG9uc2UudXJsKCkpLnBhdGhuYW1lKSkge1xyXG4gICAgICB3b3JrZmxvd1BhZ2VGYWlsdXJlcy5nZXQocGFnZSkhLnB1c2goYEhUVFAgNDEzOiAke3Jlc3BvbnNlLnVybCgpfWApO1xyXG4gICAgfVxyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3RmaW5pc2hlZCcsIHJlcXVlc3QgPT4ge1xyXG4gICAgY29uc3Qgcm93ID0gcmVxdWVzdHMuZ2V0KHJlcXVlc3QpO1xyXG4gICAgaWYgKHJvdykgcm93LmR1cmF0aW9uX21zID0gRGF0ZS5ub3coKSAtIHJvdy5zdGFydGVkO1xyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3RmYWlsZWQnLCByZXF1ZXN0ID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXF1ZXN0KTtcclxuICAgIGlmIChyb3cpIHsgcm93LmR1cmF0aW9uX21zID0gRGF0ZS5ub3coKSAtIHJvdy5zdGFydGVkOyByb3cuZmFpbHVyZSA9IHJlcXVlc3QuZmFpbHVyZSgpPy5lcnJvclRleHQ7IH1cclxuICB9KTtcclxufSk7XHJcblxyXG50ZXN0LmFmdGVyRWFjaChhc3luYyAoeyBwYWdlIH0sIGluZm8pID0+IHtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd3JpdGUtcmVxdWVzdC10aW1pbmdzJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh3cml0ZVRpbWluZ3MuZ2V0KGluZm8udGVzdElkKSB8fCBbXSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgYXdhaXQgaW5mby5hdHRhY2goJ3dvcmtmbG93LXByb2dyZXNzLWJvdW5kYXJpZXMnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHByb2dyZXNzTWlsZXN0b25lcy5nZXQoaW5mby50ZXN0SWQpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd29ya2Zsb3ctcGFnZS1mYWlsdXJlcycsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICB3cml0ZVRpbWluZ3MuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBwcm9ncmVzc01pbGVzdG9uZXMuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBleHBlY3Qod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpLCAnVGhlIHVuZGVybHlpbmcgZW5naW5lZXJpbmcgcGFnZSBtdXN0IHJlbWFpbiByZWFkYWJsZSB0aHJvdWdob3V0IHJlbG9hZCBhbmQgcmVjb3ZlcnkuJykudG9FcXVhbChbXSk7XHJcbn0pO1xyXG5cclxuYXN5bmMgZnVuY3Rpb24gYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeShwYWdlOiBQYWdlKSB7XHJcbiAgZXhwZWN0KHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSwgJ0Egd29ya2luZyB3aXphcmQgb3ZlcmxheSBtdXN0IG5vdCBjb25jZWFsIGEgd29ya2Zsb3cgSFRUUCA0MTMuJykudG9FcXVhbChbXSk7XHJcbiAgZXhwZWN0KGF3YWl0IHBhZ2UuZ2V0QnlUZXh0KCdFbmdpbmVlcmluZy1BUEkgbmljaHQgZXJyZWljaGJhcicsIHsgZXhhY3Q6IHRydWUgfSkuaXNWaXNpYmxlKCksXHJcbiAgICAnVGhlIHVuZGVybHlpbmcgZW5naW5lZXJpbmcgcGFnZSBtdXN0IG5vdCBzaG93IGl0cyBBUEkgZXJyb3Igdmlldy4nKS50b0JlKGZhbHNlKTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVhZFByb2plY3QocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBwYXRoOiBzdHJpbmcpIHtcclxuICBjb25zdCByZXN1bHQgPSBhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KHBhdGgsIHsgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiA2MF8wMDAgfSk7XHJcbiAgdHJ5IHtcclxuICAgIGlmICghcmVzdWx0Lm9rKCkpIHRocm93IG5ldyBFcnJvcihgJHtwYXRofTogSFRUUCAke3Jlc3VsdC5zdGF0dXMoKX0gJHsoYXdhaXQgcmVzdWx0LnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgICByZXR1cm4gYXdhaXQgcmVzdWx0Lmpzb24oKTtcclxuICB9IGZpbmFsbHkge1xyXG4gICAgLy8gUGxheXdyaWdodCBvdGhlcndpc2UgcmV0YWlucyBldmVyeSBwb2xsZWQgcmVzcG9uc2UgdW50aWwgY29udGV4dCB0ZWFyZG93bi5cclxuICAgIC8vIEtlZXAgdGhlIHBhcnNlZCBldmlkZW5jZSwgcmVsZWFzZSBpdHMgZHVwbGljYXRlIHRyYW5zcG9ydCBib2R5IGltbWVkaWF0ZWx5LlxyXG4gICAgYXdhaXQgcmVzdWx0LmRpc3Bvc2UoKTtcclxuICB9XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHJlYWRXYXJuaW5nUmV2aWV3U3RhdGUocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nKSB7XHJcbiAgY29uc3QgYXV0aG9yaXR5ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgY29uc3QgcGFyYW1ldGVycyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnKTtcclxuICBjb25zdCB2ZXJpZmllZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gIGV4cGVjdChwYXJhbWV0ZXJzLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgZXhwZWN0KGF1dGhvcml0eS5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xyXG4gIGV4cGVjdCh2ZXJpZmllZC5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xyXG4gIGZvciAoY29uc3QgZmllbGQgb2YgWydydW5faWQnLCAncmVxdWVzdF9yZXZpc2lvbiddKVxyXG4gICAgZXhwZWN0KHZlcmlmaWVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5bZmllbGRdKS50b0JlKGF1dGhvcml0eS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uW2ZpZWxkXSk7XHJcbiAgcmV0dXJuIHsgcHJvamVjdF9pZDogdmVyaWZpZWQucHJvamVjdF9pZCwgc3RhdHVzZXM6IHZlcmlmaWVkLnN0YXR1c2VzLFxyXG4gICAgY29udGV4dDogeyBhZ2VudF9leGVjdXRpb246IHsgcnVuX2lkOiB2ZXJpZmllZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkLFxyXG4gICAgICByZXF1ZXN0X3JldmlzaW9uOiB2ZXJpZmllZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucmVxdWVzdF9yZXZpc2lvbiB9IH0sXHJcbiAgICBwYXJhbWV0ZXJzOiB7IHByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsOiBwYXJhbWV0ZXJzLnBhcmFtZXRlcnMucHJlZmxpZ2h0X3dhcm5pbmdfYXBwcm92YWwgfSB9O1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiBvcGVuV2l6YXJkKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZykge1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9lbmdpbmVlcmluZz9hc3Npc3RhbnQ9cHJvamVjdCZwcm9qZWN0PSR7cHJvamVjdH1gLCB7IHdhaXRVbnRpbDogJ2xvYWQnIH0pO1xyXG4gIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZykudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2UpO1xyXG4gIHJldHVybiBkaWFsb2c7XHJcbn1cclxuXHJcbnRlc3QoJ3Byb2plY3QgbmFtaW5nIGZvcm0gY2FyZHMgdXNlIHRoZSBmdWxsIHdpemFyZCB3aWR0aCBAbGF5b3V0JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCAnbmlzLWUyZS1wcm9qZWN0LW5hbWUtbGF5b3V0LScgKyByYW5kb21VVUlEKCkpO1xyXG4gIGNvbnN0IHN0ZXAgPSBkaWFsb2cubG9jYXRvcignZmllbGRzZXQuYWdlbnQtcHJvamVjdC1uYW1lLXN0ZXAnKTtcclxuICBhd2FpdCBleHBlY3Qoc3RlcCkudG9CZVZpc2libGUoKTtcclxuICBjb25zdCBzdGVwV2lkdGggPSBhd2FpdCBzdGVwLmV2YWx1YXRlKGVsZW1lbnQgPT4gZWxlbWVudC5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKS53aWR0aCk7XHJcbiAgY29uc3QgY2FyZHMgPSBhd2FpdCBzdGVwLmxvY2F0b3IoJzpzY29wZSA+IGxhYmVsJykuYWxsKCk7XHJcbiAgZXhwZWN0KGNhcmRzKS50b0hhdmVMZW5ndGgoNCk7XHJcbiAgZm9yIChjb25zdCBjYXJkIG9mIGNhcmRzKSB7XHJcbiAgICBjb25zdCB3aWR0aCA9IGF3YWl0IGNhcmQuZXZhbHVhdGUoZWxlbWVudCA9PiBlbGVtZW50LmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpLndpZHRoKTtcclxuICAgIGV4cGVjdCh3aWR0aCkudG9CZUdyZWF0ZXJUaGFuKHN0ZXBXaWR0aCAqIDAuODUpO1xyXG4gIH1cclxufSk7XHJcblxyXG5hc3luYyBmdW5jdGlvbiBhbGxPYmplY3RzKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcmVzb3VyY2U6IHN0cmluZykge1xyXG4gIGNvbnN0IGl0ZW1zOiBhbnlbXSA9IFtdO1xyXG4gIGZvciAobGV0IG9mZnNldCA9IDA7IDsgb2Zmc2V0ICs9IDUwMCkge1xyXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy8ke3Jlc291cmNlfT9saW1pdD01MDAmb2Zmc2V0PSR7b2Zmc2V0fWApO1xyXG4gICAgaXRlbXMucHVzaCguLi5yZXNwb25zZS5pdGVtcyk7XHJcbiAgICBpZiAocmVzcG9uc2UuaXRlbXMubGVuZ3RoIDwgNTAwKSByZXR1cm4gaXRlbXM7XHJcbiAgfVxyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiByZXN0YXJ0QXBwbGljYXRpb24ocGFnZTogUGFnZSwgY3Jhc2ggPSBmYWxzZSkge1xyXG4gIGNvbnN0IGNvbnRhaW5lciA9IHByb2Nlc3MuZW52Lk5JU19FMkVfQVBQX0NPTlRBSU5FUiE7XHJcbiAgZXhwZWN0KGNvbnRhaW5lcikudG9NYXRjaCgvXm5pcy1lMmUtYXBwLVthLWYwLTldKyQvKTtcclxuICBjb25zdCBkb2NrZXIgPSBwcm9jZXNzLmVudi5OSVNfVEVTVF9ET0NLRVIgfHwgJ2RvY2tlcic7XHJcbiAgY29uc3QgbGFiZWwgPSBleGVjRmlsZVN5bmMoZG9ja2VyLCBbJ2luc3BlY3QnLCBjb250YWluZXIsICctLWZvcm1hdCcsICd7e2luZGV4IC5Db25maWcuTGFiZWxzIFwibmV0d29ya2lzLnRlc3RcIn19J10sIHsgZW5jb2Rpbmc6ICd1dGY4JyB9KS50cmltKCk7XHJcbiAgZXhwZWN0KGxhYmVsKS50b0JlKCdkaXNwb3NhYmxlJyk7XHJcbiAgZXhlY0ZpbGVTeW5jKGRvY2tlciwgWydyZXN0YXJ0JywgLi4uKGNyYXNoID8gWyctdCcsICcwJ10gOiBbXSksIGNvbnRhaW5lcl0sIHsgdGltZW91dDogNjBfMDAwIH0pO1xyXG4gIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcclxuICAgIHRyeSB7IHJldHVybiAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9yZWFkeScsIHsgdGltZW91dDogMjAwMCB9KSkub2soKTsgfSBjYXRjaCB7IHJldHVybiBmYWxzZTsgfVxyXG4gIH0sIHsgdGltZW91dDogMTIwXzAwMCB9KS50b0JlKHRydWUpO1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBleHBlY3RlZDogUmVjb3JkPHN0cmluZywgdW5rbm93bj4pIHtcclxuICBjb25zdCBbaGFyZHdhcmUsIGZ1bmN0aW9ucywgbWVzc2FnZXMsIHNpZ25hbHNdID0gYXdhaXQgUHJvbWlzZS5hbGwoXHJcbiAgICBbJ2hhcmR3YXJlLW5vZGVzJywgJ2Z1bmN0aW9ucycsICdtZXNzYWdlcycsICdzaWduYWxzJ10ubWFwKHJlc291cmNlID0+IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgcmVzb3VyY2UpKSk7XHJcbiAgY29uc3Qgbm9kZXMgPSBuZXcgTWFwKGhhcmR3YXJlLm1hcChpdGVtID0+IFtpdGVtLmlkLCBpdGVtXSkpO1xyXG4gIGNvbnN0IGZ1bmN0aW9uc0J5SWQgPSBuZXcgTWFwKGZ1bmN0aW9ucy5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBtZXNzYWdlc0J5SWQgPSBuZXcgTWFwKG1lc3NhZ2VzLm1hcChpdGVtID0+IFtpdGVtLmlkLCBpdGVtXSkpO1xyXG4gIGNvbnN0IGNvbnRyYWN0czogUmVjb3JkPHN0cmluZywgdW5rbm93bj4gPSB7fTtcclxuICBmb3IgKGNvbnN0IHNpZ25hbCBvZiBzaWduYWxzKSB7XHJcbiAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXNCeUlkLmdldChzaWduYWwubWVzc2FnZV9pZCk7XHJcbiAgICBleHBlY3QobWVzc2FnZSkudG9CZVRydXRoeSgpO1xyXG4gICAgY29uc3QgcmVmZXJlbmNlID0gbWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QucHJvZHVjZXJfcmVmO1xyXG4gICAgY29uc3QgZm4gPSBmdW5jdGlvbnNCeUlkLmdldChyZWZlcmVuY2UpO1xyXG4gICAgY29uc3Qgb3duZXIgPSBub2Rlcy5nZXQocmVmZXJlbmNlKSB8fCAoZm4gJiYgbm9kZXMuZ2V0KGZuLmhhcmR3YXJlX25vZGVfaWQpKTtcclxuICAgIGNvbnN0IHByb2R1Y2VyID0gb3duZXI/LmRldmljZV90eXBlID09PSAnR2F0ZXdheScgPyAnJGdhdGV3YXknIDogKG5vZGVzLmdldChyZWZlcmVuY2UpIHx8IGZuKT8ubmFtZTtcclxuICAgIGV4cGVjdChwcm9kdWNlcikudG9CZVRydXRoeSgpO1xyXG4gICAgY29uc3Qga2V5ID0gW3Byb2R1Y2VyLCBtZXNzYWdlLm5hbWUsIHNpZ25hbC5uYW1lXS5qb2luKCcgOjogJyk7XHJcbiAgICBleHBlY3QoY29udHJhY3RzW2tleV0sICdTZW1hbnRpYyBzaWduYWwgaWRlbnRpdHkgbXVzdCBiZSB1bmlxdWU6ICcgKyBrZXkpLnRvQmVVbmRlZmluZWQoKTtcclxuICAgIGNvbnRyYWN0c1trZXldID0ge1xyXG4gICAgICAuLi5PYmplY3QuZnJvbUVudHJpZXMoWydzdGFydF9iaXQnLCAnbGVuZ3RoX2JpdHMnLCAnZGF0YV90eXBlJywgJ2ZhY3RvcicsICdvZmZzZXRfdmFsdWUnLFxyXG4gICAgICAgICd1bml0JywgJ21pbl92YWx1ZScsICdtYXhfdmFsdWUnLCAnYnl0ZV9vcmRlciddLm1hcChmaWVsZCA9PiBbZmllbGQsIHNpZ25hbFtmaWVsZF0gPz8gbnVsbF0pKSxcclxuICAgICAgZW51bV92YWx1ZXM6IHNpZ25hbC5kYXRhPy5lbnVtX3ZhbHVlcyA/PyBudWxsLFxyXG4gICAgICBzZW1hbnRpY190eXBlOiBzaWduYWwuc2VtYW50aWM/LnNlbWFudGljX3R5cGUgPz8gbnVsbCxcclxuICAgICAgZ2VuZXJhdGlvbl9yb2xlOiBzaWduYWwuY29uZmlndXJhdGlvbj8uZ2VuZXJhdGlvbl9yb2xlID8/IG51bGwsXHJcbiAgICB9O1xyXG4gIH1cclxuICBleHBlY3QoY29udHJhY3RzLCAnRXZlcnkgb3JpZ2luYWwgc2lnbmFsIGFuZCBpdHMgZXhwbGljaXQgZW5jb2RpbmcgbXVzdCBzdXJ2aXZlIGdlbmVyYXRpb24uJykudG9FcXVhbChleHBlY3RlZCk7XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHZlcmlmeUFydGlmYWN0cyhwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIG1pbmltdW1DYW5vbmljYWxTaWduYWxzOiBudW1iZXIsIGludGVybmFsQ29udHJvbGxlcj86IHN0cmluZyxcclxuICBleHBlY3RlZFBhcmFtZXRlcnM/OiBSZWNvcmQ8c3RyaW5nLCB1bmtub3duPikge1xyXG4gIC8vIFRoZSBjb21wbGV0ZWQgbW9kZWwgaXMgc3RhYmxlOyB0aGVzZSBpbmRlcGVuZGVudCByZWFkcyBuZWVkIG5vIHNlcmlhbCB3YWl0cy5cclxuICBjb25zdCBbd29ya2Zsb3csIGpvYkxpc3QsIHNuYXBzaG90cywgc2lnbmFscywgbWVzc2FnZXNdID0gYXdhaXQgUHJvbWlzZS5hbGwoW1xyXG4gICAgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5JyksXHJcbiAgICByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpLFxyXG4gICAgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvc25hcHNob3RzJyksXHJcbiAgICBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyksXHJcbiAgICBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdtZXNzYWdlcycpLFxyXG4gIF0pO1xyXG4gIGV4cGVjdChPYmplY3Qua2V5cyh3b3JrZmxvdy5zdGF0dXNlcykuc29ydCgpKS50b0VxdWFsKFsuLi5zdGVwc10uc29ydCgpKTtcclxuICBmb3IgKGNvbnN0IHN0ZXAgb2Ygc3RlcHMpIGV4cGVjdChkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXSksIGAke3N0ZXB9OiAke3dvcmtmbG93LnN0YXR1c2VzW3N0ZXBdfWApLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBqb2JzID0gam9iTGlzdC5qb2JzO1xyXG4gIGV4cGVjdChqb2JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KGpvYnNbMF0uc3RhdHVzKS50b0JlKCdjb21wbGV0ZWQnKTtcclxuICBjb25zdCBzbmFwc2hvdCA9IHNuYXBzaG90cy5zaW11bGF0aW9ucy5maW5kKChpdGVtOiB7IGpvYl9pZDogc3RyaW5nIH0pID0+IGl0ZW0uam9iX2lkID09PSBqb2JzWzBdLmlkKTtcclxuICBleHBlY3Qoc25hcHNob3QpLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBmdWxsID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvc2ltdWxhdGlvbi1zbmFwc2hvdHMvJHtzbmFwc2hvdC5pZH1gKTtcclxuICBpZiAoZXhwZWN0ZWRQYXJhbWV0ZXJzKSB7XHJcbiAgICBjb25zdCB7IGRhdGFfYml0cmF0ZSwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyLCAuLi5ydW50aW1lUGFyYW1ldGVycyB9ID0gZXhwZWN0ZWRQYXJhbWV0ZXJzO1xyXG4gICAgZXhwZWN0KGZ1bGwuY29uZmlndXJhdGlvbi5wYXJhbWV0ZXJzKS50b01hdGNoT2JqZWN0KHJ1bnRpbWVQYXJhbWV0ZXJzKTtcclxuICAgIGNvbnN0IGNhbkZkTmV0d29ya3MgPSBmdWxsLmNvbmZpZ3VyYXRpb24ubmV0d29ya3MuZmlsdGVyKChuZXR3b3JrOiBhbnkpID0+IG5ldHdvcmsudGVjaG5vbG9neSA9PT0gJ2Nhbl9mZCcpO1xyXG4gICAgZXhwZWN0KGNhbkZkTmV0d29ya3MubGVuZ3RoLCAnVGhlIGVkaXRlZCBDQU4tRkQgY29uZmlndXJhdGlvbiBtdXN0IHJlYWNoIGEgcGh5c2ljYWwgc2ltdWxhdGlvbiBuZXR3b3JrLicpLnRvQmVHcmVhdGVyVGhhbigwKTtcclxuICAgIGZvciAoY29uc3QgbmV0d29yayBvZiBjYW5GZE5ldHdvcmtzKSBleHBlY3QobmV0d29yaykudG9NYXRjaE9iamVjdCh7IGRhdGFfYml0cmF0ZSwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyIH0pO1xyXG4gIH1cclxuICBjb25zdCBhc3Nlc3NtZW50ID0gZnVsbC5yZXN1bHQuYXNzZXNzbWVudDtcclxuICBleHBlY3QoYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS5zY29wZV9tb2RlKS50b0JlKCdBTEwnKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS5jb21wbGV0ZSkudG9CZSh0cnVlKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5jb25mb3JtYW5jZSkudG9CZSgnUEFTUycpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LmZhaWxlZF9yb3V0ZV9jb3VudCkudG9CZSgwKTtcclxuICBleHBlY3Qoc2lnbmFscy5sZW5ndGgsICdUaGUgZnVsbCBjYW5vbmljYWwgc2lnbmFsIGludmVudG9yeSBtdXN0IHN1cnZpdmUgZ2VuZXJhdGlvbi4nKS50b0JlR3JlYXRlclRoYW5PckVxdWFsKG1pbmltdW1DYW5vbmljYWxTaWduYWxzKTtcclxuICBjb25zdCBleGNsdWRlZCA9IGFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UudHJhbnNwb3J0X2V4Y2x1c2lvbnMgPz8gW107XHJcbiAgZm9yIChjb25zdCBpdGVtIG9mIGV4Y2x1ZGVkKSB7XHJcbiAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXMuZmluZChyb3cgPT4gcm93LmlkID09PSBpdGVtLm1lc3NhZ2VfaWQpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UsIGBFeGNsdWRlZCBtZXNzYWdlICR7aXRlbS5tZXNzYWdlX2lkfSBtdXN0IGV4aXN0LmApLnRvQmVUcnV0aHkoKTtcclxuICAgIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24ucm91dGluZy5lbmFibGVkKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IGNvbnRyYWN0ID0gbWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3Q7XHJcbiAgICBleHBlY3QoY29udHJhY3QuY29uc3VtZXJfcmVmcykudG9FcXVhbChbXSk7XHJcbiAgICBleHBlY3QoaXRlbS5yZWFzb25fY29kZSkudG9CZShjb250cmFjdC5yb2xlID09PSAnSU5URVJOQUxfU1RBVEUnXHJcbiAgICAgID8gJ0lOVEVSTkFMX1NUQVRFX05PVF9ST1VURUQnIDogJ0VYUExJQ0lUX0ZVTkNUSU9OX09VVFBVVF9OT1RfUk9VVEVEJyk7XHJcbiAgfVxyXG4gIGlmIChpbnRlcm5hbENvbnRyb2xsZXIpIHtcclxuICAgIGNvbnN0IG5vZGVzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICAgIGNvbnN0IGNvbnRyb2xsZXIgPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSBpbnRlcm5hbENvbnRyb2xsZXIpO1xyXG4gICAgZXhwZWN0KGV4Y2x1ZGVkLmxlbmd0aCkudG9CZUdyZWF0ZXJUaGFuKDApO1xyXG4gICAgZm9yIChjb25zdCBpdGVtIG9mIGV4Y2x1ZGVkKSB7XHJcbiAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKHJvdyA9PiByb3cuaWQgPT09IGl0ZW0ubWVzc2FnZV9pZCk7XHJcbiAgICAgIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdCkudG9NYXRjaE9iamVjdCh7IHJvbGU6ICdJTlRFUk5BTF9TVEFURScsIHNjb3BlOiAnSU5URVJOQUwnLCBwcm9kdWNlcl9yZWY6IGNvbnRyb2xsZXIuaWQsIGNvbnN1bWVyX3JlZnM6IFtdIH0pO1xyXG4gICAgfVxyXG4gIH1cclxuICBjb25zdCBleGNsdWRlZFNpZ25hbHMgPSBuZXcgU2V0KGV4Y2x1ZGVkLmZsYXRNYXAoKGl0ZW06IHsgc2lnbmFsX2lkczogc3RyaW5nW10gfSkgPT4gaXRlbS5zaWduYWxfaWRzKSk7XHJcbiAgZXhwZWN0KGFzc2Vzc21lbnQub2JzZXJ2ZWRfc2lnbmFsX2NvdW50LCAnQUxMIG11c3Qgb2JzZXJ2ZSBldmVyeSBjYW5vbmljYWwgc2lnbmFsIHdpdGggYSB0cmFuc3BvcnQgb2JsaWdhdGlvbi4nKS50b0JlKHNpZ25hbHMubGVuZ3RoIC0gZXhjbHVkZWRTaWduYWxzLnNpemUpO1xyXG4gIGZvciAoY29uc3Qga2V5IG9mIFsnbWlzc2luZ19vYnNlcnZlZF9zaWduYWxfaWRzJywgJ21pc3Npbmdfb2JzZXJ2ZWRfcm91dGVfaWRzJywgJ21pc3Npbmdfb2JzZXJ2ZWRfbmV0d29ya19pZHMnXSkgZXhwZWN0KGFzc2Vzc21lbnRba2V5XSkudG9FcXVhbChbXSk7XHJcbiAgY29uc3QgdHJhY2UgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9zaW11bGF0aW9ucy8ke2pvYnNbMF0uaWR9L3RyYWNlLXdpbmRvdz9saW1pdD0xMGApO1xyXG4gIGV4cGVjdCh0cmFjZS5jb3VudCkudG9CZUdyZWF0ZXJUaGFuKDApO1xyXG4gIGV4cGVjdCh0cmFjZS5ldmVudHMuc29tZSgoaXRlbTogeyBzaWduYWxzPzogdW5rbm93bltdIH0pID0+IGl0ZW0uc2lnbmFscyAmJiBPYmplY3Qua2V5cyhpdGVtLnNpZ25hbHMpLmxlbmd0aCkpLnRvQmVUcnV0aHkoKTtcclxuICByZXR1cm4geyB3b3JrZmxvdywgam9iOiBqb2JzWzBdLmlkLCBhc3Nlc3NtZW50LCBwYXJhbWV0ZXJfcHJvb2Y6IGV4cGVjdGVkUGFyYW1ldGVycyA/IHtcclxuICAgIHNhdmVkOiBleHBlY3RlZFBhcmFtZXRlcnMsIHNpbXVsYXRpb25fcmF0ZXM6IGZ1bGwuY29uZmlndXJhdGlvbi5uZXR3b3Jrcy5tYXAoKG5ldHdvcms6IGFueSkgPT4gKHtcclxuICAgICAgdGVjaG5vbG9neTogbmV0d29yay50ZWNobm9sb2d5LCBiaXRyYXRlOiBuZXR3b3JrLmJpdHJhdGUsXHJcbiAgICAgIGFyYml0cmF0aW9uX2JpdHJhdGU6IG5ldHdvcmsuYXJiaXRyYXRpb25fYml0cmF0ZSwgZGF0YV9iaXRyYXRlOiBuZXR3b3JrLmRhdGFfYml0cmF0ZSxcclxuICAgICAgaGFyZHdhcmVfZXZpZGVuY2U6IG5ldHdvcmsuaGFyZHdhcmVfZXZpZGVuY2UsXHJcbiAgICB9KSksXHJcbiAgfSA6IHVuZGVmaW5lZCB9O1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCByZXN0YXJ0OiBib29sZWFuLCBleHBlY3RlZEhhcmR3YXJlOiBzdHJpbmdbXSA9IFtdLCBjcmFzaFNpbXVsYXRpb24gPSBmYWxzZSxcclxuICBleHBlY3RlZFNpZ25hbHM/OiBSZWNvcmQ8c3RyaW5nLCB1bmtub3duPiwgYWZ0ZXJGaXJzdE1vZGVsQXBwbGllZD86ICgpID0+IFByb21pc2U8dm9pZD4sIHN0b3BPbkV2aWRlbmNlQmxvY2sgPSBmYWxzZSkge1xyXG4gIGxldCByZXZpZXdDb3VudCA9IDA7XHJcbiAgbGV0IHJ1bklkOiBzdHJpbmcgfCB1bmRlZmluZWQ7XHJcbiAgY29uc3QgcmV2aWV3ZWQgPSBuZXcgU2V0PHN0cmluZz4oKTtcclxuICBsZXQgcmVzdGFydGVkSm9iSWQ6IHN0cmluZyB8IHVuZGVmaW5lZDtcclxuICBsZXQgd2F0Y2hkb2cgPSBuZXcgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyhwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgZm9yIChsZXQgY2hlY2twb2ludCA9IDA7IGNoZWNrcG9pbnQgPCAxNjsgY2hlY2twb2ludCsrKSB7XHJcbiAgICBsZXQgd29ya2Zsb3c6IGFueTtcclxuICAgIGxldCBwcm9wb3NhbElkID0gJyc7XHJcbiAgICBsZXQgcmVhZHlWZXJzaW9uID0gJyc7XHJcbiAgICBsZXQgcmVhZHlTaW5jZSA9IDA7XHJcbiAgICBjb25zdCBpc0NoZWNrcG9pbnQgPSBhc3luYyAoKSA9PiB7XHJcbiAgICAgIHdhdGNoZG9nLnJlbWFpbmluZyhwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgICAgIGF3YWl0IGFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkocGFnZSk7XHJcbiAgICAgIHdvcmtmbG93ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgIGNvbnN0IHByb2dyZXNzID0gd2F0Y2hkb2cub2JzZXJ2ZSh3b3JrZmxvdywgcGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gICAgICBpZiAocHJvZ3Jlc3MuYWR2YW5jZWQpIHByb2dyZXNzTWlsZXN0b25lcy5nZXQodGVzdC5pbmZvKCkudGVzdElkKSEucHVzaCh7XHJcbiAgICAgICAgYXQ6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSwgZnJvbnRpZXI6IHByb2dyZXNzLmZyb250aWVyLFxyXG4gICAgICAgIGNvbXBsZXRlZFRocm91Z2g6IHN0ZXBzW3Byb2dyZXNzLmZyb250aWVyIC0gMV0sXHJcbiAgICAgICAgcHJvamVjdDogd29ya2Zsb3cucHJvamVjdF9pZCwgZXhlY3V0aW9uOiB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbixcclxuICAgICAgfSk7XHJcbiAgICAgIGlmIChjcmFzaFNpbXVsYXRpb24gJiYgIXJlc3RhcnRlZEpvYklkICYmIGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzLnZhbGlkYXRpb24pKSB7XHJcbiAgICAgICAgY29uc3Qgam9icyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzO1xyXG4gICAgICAgIGNvbnN0IHJ1bm5pbmcgPSBqb2JzLmZpbmQoKGpvYjogeyBzdGF0dXM6IHN0cmluZyB9KSA9PiBqb2Iuc3RhdHVzID09PSAncnVubmluZycpO1xyXG4gICAgICAgIGlmIChydW5uaW5nKSB7XHJcbiAgICAgICAgICByZXN0YXJ0ZWRKb2JJZCA9IHJ1bm5pbmcuaWQ7XHJcbiAgICAgICAgICBhd2FpdCByZXN0YXJ0QXBwbGljYXRpb24ocGFnZSwgdHJ1ZSk7XHJcbiAgICAgICAgICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgICAgICAgcmV0dXJuIGZhbHNlO1xyXG4gICAgICAgIH1cclxuICAgICAgfVxyXG4gICAgICBpZiAoc3RlcHMuZXZlcnkoc3RlcCA9PiBkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXSkpKSByZXR1cm4gdHJ1ZTtcclxuICAgICAgY29uc3QgZXhlY3V0aW9uID0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb247XHJcbiAgICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnUkVWSUVXX1JFUVVJUkVEJykge1xyXG4gICAgICAgIGNvbnN0IGNvbnZlcnNhdGlvbiA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpO1xyXG4gICAgICAgIHByb3Bvc2FsSWQgPSBjb252ZXJzYXRpb24uZGF0YS5hY3RpdmVfcHJvcG9zYWw7XHJcbiAgICAgICAgLy8gUG9sbGluZyBtYXkgc3RpbGwgZXhwb3NlIHRoZSBqdXN0LWFwcGxpZWQgcmV2aWV3IHdoaWxlIHRoZSBVSSBzdGFydHNcclxuICAgICAgICAvLyBpdHMgZHVyYWJsZSBjb250aW51YXRpb24uIFdhaXQgZm9yIGEgZGlzdGluY3QgcHJvcG9zYWwsIG5vdCBpdHMgbGFiZWwuXHJcbiAgICAgICAgcmV0dXJuIEJvb2xlYW4ocHJvcG9zYWxJZCkgJiYgIXJldmlld2VkLmhhcyhwcm9wb3NhbElkKTtcclxuICAgICAgfVxyXG4gICAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JFQURZX1RPX0NPTlRJTlVFJyB8fCAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5yZWNvdmVyYWJsZSA9PT0gdHJ1ZSkpIHtcclxuICAgICAgICBpZiAocmVhZHlWZXJzaW9uICE9PSBleGVjdXRpb24udXBkYXRlZF9hdCkge1xyXG4gICAgICAgICAgcmVhZHlWZXJzaW9uID0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQ7IHJlYWR5U2luY2UgPSBEYXRlLm5vdygpO1xyXG4gICAgICAgIH1cclxuICAgICAgICAvLyBXaGlsZSBhIGxhcmdlIGNvbnRpbnVhdGlvbiBpcyBnZW5lcmF0aW5nLCB0aGUgbGFzdCBjb21taXR0ZWQgc2VydmVyXHJcbiAgICAgICAgLy8gY2hlY2twb2ludCBjYW4gc3RpbGwgYmUgUkVBRFkuIEFjdCBvbmx5IHdoZW4gdGhlIFVJIG9mZmVycyBpdCB0b28uXHJcbiAgICAgICAgY29uc3QgYnV0dG9uID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KVxyXG4gICAgICAgICAgLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQXVmdHJhZyBmb3J0c2V0emVuJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgICAgICAgcmV0dXJuIERhdGUubm93KCkgLSByZWFkeVNpbmNlID4gNTAwMCAmJiBhd2FpdCBidXR0b24uZXZhbHVhdGVBbGwoYnV0dG9ucyA9PiBidXR0b25zLnNvbWUoYnV0dG9uID0+ICEoYnV0dG9uIGFzIEhUTUxCdXR0b25FbGVtZW50KS5kaXNhYmxlZCAmJiBidXR0b24uZ2V0Q2xpZW50UmVjdHMoKS5sZW5ndGggPiAwICYmIGdldENvbXB1dGVkU3R5bGUoYnV0dG9uKS52aXNpYmlsaXR5ICE9PSBcImhpZGRlblwiKSk7XHJcbiAgICAgIH1cclxuICAgICAgcmV0dXJuIFsnQkxPQ0tFRCcsICdGQUlMRUQnLCAnSU5DT01QTEVURSddLmluY2x1ZGVzKGV4ZWN1dGlvbj8uc3RhdGUpO1xyXG4gICAgfTtcclxuICAgIC8vIEEgc2luZ2xlIHBvbGwgcHJldmlvdXNseSB0aW1lZCBhbGwgb2YgQ2FwYWNpdHkgLT4gSW50ZWxsaWdlbmNlIHRvZ2V0aGVyLlxyXG4gICAgLy8gQm91bmQgZWFjaCBnZW51aW5lIHN0YWdlIGFkdmFuY2UsIHdoaWxlIHJldHJpZXMgYW5kIHJlc3RhcnRzIHJldGFpbiB0aGVpclxyXG4gICAgLy8gcmVtYWluaW5nIGRlYWRsaW5lLiBUaGUgaW5kZXBlbmRlbnQgMjAtbWludXRlIHRlc3QgdGltZW91dCBpcyB1bmNoYW5nZWQuXHJcbiAgICBsZXQgYXR0ZW1wdCA9IDA7XHJcbiAgICB3aGlsZSAoIWF3YWl0IGlzQ2hlY2twb2ludCgpKSB7XHJcbiAgICAgIGNvbnN0IHJlbWFpbmluZyA9IHdhdGNoZG9nLnJlbWFpbmluZyhwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgICAgIGF3YWl0IHBhZ2Uud2FpdEZvclRpbWVvdXQoTWF0aC5taW4oWzUwMCwgMTAwMCwgMjAwMF1bTWF0aC5taW4oYXR0ZW1wdCsrLCAyKV0sIHJlbWFpbmluZykpO1xyXG4gICAgfVxyXG4gICAgcnVuSWQgPz89IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQ7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZCkudG9CZShydW5JZCk7XHJcbiAgICBpZiAoc3RlcHMuZXZlcnkoc3RlcCA9PiBkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXSkpKSB7XHJcbiAgICAgIGlmIChjcmFzaFNpbXVsYXRpb24pIGV4cGVjdChyZXN0YXJ0ZWRKb2JJZCwgJ0EgcmVhbCBydW5uaW5nIHNpbXVsYXRpb24gbXVzdCBiZSBvYnNlcnZlZCBhbmQgaW50ZXJydXB0ZWQuJykudG9CZVRydXRoeSgpO1xyXG4gICAgICByZXR1cm4geyBydW5JZCwgcmV2aWV3ZWQ6IFsuLi5yZXZpZXdlZF0sIHJlc3RhcnRlZEpvYklkIH07XHJcbiAgICB9XHJcbiAgICBjb25zdCBleGVjdXRpb24gPSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbjtcclxuICAgIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XHJcbiAgICBpZiAoc3RvcE9uRXZpZGVuY2VCbG9jayAmJiBleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLmJsb2NraW5nX2ZpbmRpbmdzPy5sZW5ndGgpIHtcclxuICAgICAgdGhyb3cgbmV3IEVycm9yKGBXaXphcmQgQkxPQ0tFRCBhdCAke2V4ZWN1dGlvbi5zdGVwfTogJHtleGVjdXRpb24ubWVzc2FnZX1gKTtcclxuICAgIH1cclxuICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLm1lc3NhZ2U/LmluY2x1ZGVzKCdSRUFEWV9XSVRIX1dBUk5JTkdTJykpIHtcclxuICAgICAgY29uc3QgYmVmb3JlUmV2aWV3ID0gYXdhaXQgcmVhZFdhcm5pbmdSZXZpZXdTdGF0ZShwYWdlLCBwcm9qZWN0KTtcclxuICAgICAgY29uc3QgcHJlZmxpZ2h0ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvcHJlZmxpZ2h0Jyk7XHJcbiAgICAgIGNvbnN0IHdhcm5pbmdzID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnUHJlZmxpZ2h0LVdhcm51bmdlbicgfSk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdCh3YXJuaW5ncy5nZXRCeVJvbGUoJ2xpc3RpdGVtJykuZmlyc3QoKSkudG9CZVZpc2libGUoKTtcclxuICAgICAgY29uc3Qgc3RhcnRlZCA9IHBlcmZvcm1hbmNlLm5vdygpLCBzdGFydGVkV2FsbCA9IERhdGUubm93KCk7XHJcbiAgICAgIHdhdGNoZG9nLnJlbWFpbmluZyhzdGFydGVkKTtcclxuICAgICAgY29uc3QgYXBwcm92YWxSZXNwb25zZSA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IG5ldyBVUkwocmVzcG9uc2UudXJsKCkpLnBhdGhuYW1lID09PSAnL2FwaS9lbmdpbmVlcmluZy9wcmVmbGlnaHQvd2FybmluZ3MvYXBwcm92ZSdcclxuICAgICAgICAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJywgeyB0aW1lb3V0OiAxODBfMDAwIH0pO1xyXG4gICAgICBhd2FpdCB3YXJuaW5ncy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ1dhcm51bmdlbiBmcmVpZ2ViZW4gdW5kIGZvcnRzZXR6ZW4nIH0pLmNsaWNrKCk7XHJcbiAgICAgIGNvbnN0IGFwcHJvdmVkID0gYXdhaXQgYXBwcm92YWxSZXNwb25zZTtcclxuICAgICAgY29uc3QgcmVjZWlwdCA9IGF3YWl0IGFwcHJvdmVkLmpzb24oKTtcclxuICAgICAgY29uc3QgYWZ0ZXJSZXZpZXcgPSBhd2FpdCByZWFkV2FybmluZ1Jldmlld1N0YXRlKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgICBjb25zdCBwcm9vZiA9IHsgYmVmb3JlOiBiZWZvcmVSZXZpZXcsIGFmdGVyOiBhZnRlclJldmlldywgc25hcHNob3RJZDogcHJlZmxpZ2h0LmlkLFxyXG4gICAgICAgIHJlcXVlc3RQcm9qZWN0OiBhcHByb3ZlZC5yZXF1ZXN0KCkuaGVhZGVycygpWyd4LXByb2plY3QtaWQnXSwgc3VibWl0dGVkOiBhcHByb3ZlZC5yZXF1ZXN0KCkucG9zdERhdGFKU09OKCksXHJcbiAgICAgICAgc3RhdHVzOiBhcHByb3ZlZC5zdGF0dXMoKSwgcmVzcG9uc2U6IHJlY2VpcHQsIHN0YXJ0ZWQsIHN0YXJ0ZWRXYWxsLCBmaW5pc2hlZFdhbGw6IERhdGUubm93KCkgfTtcclxuICAgICAgY29uc3QgY29tbWl0dGVkQXQgPSBwZXJmb3JtYW5jZS5ub3coKTtcclxuICAgICAgY29uc3QgY29tbWl0dGVkID0gd2F0Y2hkb2cuY29tbWl0V2FybmluZ1Jldmlldyhwcm9vZiwgY29tbWl0dGVkQXQpO1xyXG4gICAgICBhd2FpdCB0ZXN0LmluZm8oKS5hdHRhY2goJ3ZlcmlmaWVkLXdhcm5pbmctcmV2aWV3LXByb29mJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb29mLCBjb21taXR0ZWRBdCwgY29tbWl0dGVkIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gICAgICBwcm9ncmVzc01pbGVzdG9uZXMuZ2V0KHRlc3QuaW5mbygpLnRlc3RJZCkhLnB1c2goeyBhdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLCBtYW51YWxXYXJuaW5nQXBwcm92YWw6IGNvbW1pdHRlZC5hcHByb3ZhbElkZW50aXR5LFxyXG4gICAgICAgIGZyb250aWVyOiBjb21taXR0ZWQuZnJvbnRpZXIsIHByb2plY3QsIGV4ZWN1dGlvbjogYWZ0ZXJSZXZpZXcuY29udGV4dC5hZ2VudF9leGVjdXRpb24sIGFwcHJvdmFsOiByZWNlaXB0LmFwcHJvdmFsIH0pO1xyXG4gICAgICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5JykpLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0LFxyXG4gICAgICAgIHsgdGltZW91dDogZXhwZWN0ZWRIYXJkd2FyZS5sZW5ndGggPiAxMDAgPyAxODBfMDAwIDogNjBfMDAwIH0pLm5vdC50b0JlKGV4ZWN1dGlvbi51cGRhdGVkX2F0KTtcclxuICAgICAgY29udGludWU7XHJcbiAgICB9XHJcbiAgICBpZiAoWydCTE9DS0VEJywgJ0ZBSUxFRCcsICdJTkNPTVBMRVRFJ10uaW5jbHVkZXMoZXhlY3V0aW9uPy5zdGF0ZSkgJiYgZXhlY3V0aW9uLnJlY292ZXJhYmxlICE9PSB0cnVlKSB7XHJcbiAgICAgIGNvbnN0IGNvbnZlcnNhdGlvbiA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpO1xyXG4gICAgICBjb25zdCBpZCA9IGNvbnZlcnNhdGlvbi5kYXRhPy5hY3RpdmVfcHJvcG9zYWw7XHJcbiAgICAgIGNvbnN0IHByb3Bvc2FsID0gaWQgPyBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtpZH1gKSA6IG51bGw7XHJcbiAgICAgIGF3YWl0IHRlc3QuaW5mbygpLmF0dGFjaCgnd2l6YXJkLWJsb2NrZXInLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgZXhlY3V0aW9uLFxyXG4gICAgICAgIHByb3Bvc2FsOiBwcm9wb3NhbD8uZGF0YT8udmFsaWRhdGlvbl9yZXN1bHQsIHZpc2libGU6IGF3YWl0IGRpYWxvZy5pbm5lclRleHQoKSB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICAgICAgdGhyb3cgbmV3IEVycm9yKGBXaXphcmQgJHtleGVjdXRpb24uc3RhdGV9IGF0ICR7ZXhlY3V0aW9uLnN0ZXB9OiAke2V4ZWN1dGlvbi5tZXNzYWdlfWApO1xyXG4gICAgfVxyXG4gICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdSRUFEWV9UT19DT05USU5VRScgfHwgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24ucmVjb3ZlcmFibGUgPT09IHRydWUpKSB7XHJcbiAgICAgIGNvbnN0IGJ1dHRvbiA9IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1ZnRyYWcgZm9ydHNldHplbicsIGV4YWN0OiB0cnVlIH0pO1xyXG4gICAgICB0cnkge1xyXG4gICAgICAgIGF3YWl0IGJ1dHRvbi5jbGljayh7IHRpbWVvdXQ6IDIwMDAgfSk7XHJcbiAgICAgIH0gY2F0Y2ggKGVycm9yKSB7XHJcbiAgICAgICAgY29uc3QgbGF0ZXN0ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgICAgaWYgKGxhdGVzdC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCA9PT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQgJiYgYXdhaXQgYnV0dG9uLmV2YWx1YXRlQWxsKGJ1dHRvbnMgPT4gYnV0dG9ucy5zb21lKGJ1dHRvbiA9PiAhKGJ1dHRvbiBhcyBIVE1MQnV0dG9uRWxlbWVudCkuZGlzYWJsZWQgJiYgYnV0dG9uLmdldENsaWVudFJlY3RzKCkubGVuZ3RoID4gMCAmJiBnZXRDb21wdXRlZFN0eWxlKGJ1dHRvbikudmlzaWJpbGl0eSAhPT0gXCJoaWRkZW5cIikpKSB0aHJvdyBlcnJvcjtcclxuICAgICAgICBjb250aW51ZTtcclxuICAgICAgfVxyXG4gICAgICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICAgICAgY29uc3QgbGF0ZXN0ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgICAgcmV0dXJuIGxhdGVzdC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCAhPT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXRcclxuICAgICAgICAgIHx8IGxhdGVzdC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uc3RhdGUgPT09ICdSVU5OSU5HJ1xyXG4gICAgICAgICAgfHwgbGF0ZXN0LnN0YXR1c2VzPy5bZXhlY3V0aW9uLnN0ZXBdID09PSAnSU5fUFJPR1JFU1MnO1xyXG4gICAgICB9LCB7IHRpbWVvdXQ6IDYwXzAwMCB9KS50b0JlKHRydWUpO1xyXG4gICAgICBjb250aW51ZTtcclxuICAgIH1cclxuICAgIGNvbnN0IGNhbmRpZGF0ZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3Byb3Bvc2FsSWR9YCk7XHJcbiAgICBpZiAoY2FuZGlkYXRlLmRhdGEucHJvcG9zYWxfdHlwZSA9PT0gJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcgJiYgcmV2aWV3Q291bnQgPT09IDAgJiYgZXhwZWN0ZWRIYXJkd2FyZS5sZW5ndGgpIHtcclxuICAgICAgY29uc3QgaGFyZHdhcmUgPSBjYW5kaWRhdGUuZGF0YS5jaGFuZ2VzXHJcbiAgICAgICAgLmZpbHRlcigoY2hhbmdlOiB7IG9iamVjdF90eXBlOiBzdHJpbmcgfSkgPT4gY2hhbmdlLm9iamVjdF90eXBlID09PSAnSGFyZHdhcmVOb2RlJylcclxuICAgICAgICAubWFwKChjaGFuZ2U6IHsgZGF0YTogeyBuYW1lOiBzdHJpbmcgfSB9KSA9PiBjaGFuZ2UuZGF0YS5uYW1lKTtcclxuICAgICAgZXhwZWN0KGhhcmR3YXJlLCAnVGhlIFVJIG11c3QgcHJlc2VydmUgdGhlIGhhcmR3YXJlIGV4cGxpY2l0bHkgbmFtZWQgaW4gdGhlIHVzZXIgcmVxdWVzdC4nKVxyXG4gICAgICAgIC50b0VxdWFsKGV4cGVjdC5hcnJheUNvbnRhaW5pbmcoZXhwZWN0ZWRIYXJkd2FyZSkpO1xyXG4gICAgfVxyXG4gICAgZXhwZWN0KHJldmlld2VkLmhhcyhwcm9wb3NhbElkKSwgJ1RoZSBzYW1lIHByb3Bvc2FsIG11c3Qgbm90IHJlcXVlc3QgcmV2aWV3IHR3aWNlLicpLnRvQmUoZmFsc2UpO1xyXG4gICAgY29uc3QgYXBwbHlSZXNwb25zZSA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IHJlc3BvbnNlLnVybCgpLmluY2x1ZGVzKGAvcHJvcG9zYWxzLyR7cHJvcG9zYWxJZH0vYXBwcm92ZS1hcHBseWApICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnLCB7IHRpbWVvdXQ6IDE4MF8wMDAgfSk7XHJcbiAgICBjb25zdCBhcHByb3ZhbCA9IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogL14oRnJlaWdlYmVuLCDDvGJlcm5laG1lbiAmIGZvcnRmYWhyZW58w5xiZXJuZWhtZW4gJiBmb3J0ZmFocmVuKSQvIH0pO1xyXG4gICAgYXdhaXQgZXhwZWN0KGFwcHJvdmFsKS50b0JlRW5hYmxlZCh7IHRpbWVvdXQ6IDYwXzAwMCB9KTtcclxuICAgIGF3YWl0IGFwcHJvdmFsLmNsaWNrKCk7XHJcbiAgICBjb25zdCBhcHBsaWVkID0gYXdhaXQgYXBwbHlSZXNwb25zZTtcclxuICAgIGlmICghYXBwbGllZC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYEhUVFAgJHthcHBsaWVkLnN0YXR1cygpfTogJHsoYXdhaXQgYXBwbGllZC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gICAgZXhwZWN0KChhd2FpdCBhcHBsaWVkLmpzb24oKSkuZGF0YS5zdGF0dXMpLnRvQmUoJ0FQUExJRUQnKTtcclxuICAgIHJldmlld2VkLmFkZChwcm9wb3NhbElkKTsgcmV2aWV3Q291bnQrKztcclxuICAgIC8vIEEgZGlzdGluY3QsIGFjdHVhbGx5IGNvbW1pdHRlZCBtYW51YWwgcmV2aWV3IHN0YXJ0cyB0aGUgbmV4dCBhdXRvbWF0aWNcclxuICAgIC8vIHNlY3Rpb24uIEl0cyB3cml0ZSBzdGlsbCBoYXMgdGhlIHNlcGFyYXRlIHVuY2hhbmdlZCAxODAtc2Vjb25kIGxpbWl0LlxyXG4gICAgd2F0Y2hkb2cgPSBuZXcgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyhwZXJmb3JtYW5jZS5ub3coKSwgd29ya2Zsb3cpO1xyXG4gICAgaWYgKGNhbmRpZGF0ZS5kYXRhLnByb3Bvc2FsX3R5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnICYmIGV4cGVjdGVkU2lnbmFscykge1xyXG4gICAgICBhd2FpdCB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZSwgcHJvamVjdCwgZXhwZWN0ZWRTaWduYWxzKTtcclxuICAgIH1cclxuICAgIGlmIChyZXZpZXdDb3VudCA9PT0gMSAmJiBhZnRlckZpcnN0TW9kZWxBcHBsaWVkKSB7XHJcbiAgICAgIGF3YWl0IGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQoKTtcclxuICAgICAgLy8gVGhpcyBvbmUgdGVzdCBleHBsaWNpdGx5IHN1Ym1pdHMgQU1FTkQgYW5kIHdhaXRzIGZvciBpdHMgcmVjZWlwdC4gT25seVxyXG4gICAgICAvLyB0aGF0IGRlbGliZXJhdGUgYWN0aW9uIHBlcm1pdHMgYmluZGluZyBpdHMgbmV3IHJlcXVlc3QgcmV2aXNpb24uXHJcbiAgICAgIGNvbnN0IGFtZW5kZWQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgZXhwZWN0KGFtZW5kZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZCkudG9CZShydW5JZCk7XHJcbiAgICAgIHdhdGNoZG9nID0gbmV3IFdpemFyZFByb2dyZXNzV2F0Y2hkb2cocGVyZm9ybWFuY2Uubm93KCksIGFtZW5kZWQpO1xyXG4gICAgfVxyXG4gICAgaWYgKHJldmlld0NvdW50ID09PSAxKSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpOyAvLyBEdXJhYmxlIHJlbG9hZCBhZnRlciBhIHJlYWwgY29tbWl0LlxyXG4gICAgaWYgKHJlc3RhcnQgJiYgcmV2aWV3Q291bnQgPT09IDIpIHtcclxuICAgICAgYXdhaXQgcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2UpO1xyXG4gICAgICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgfVxyXG4gICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgICBjb25zdCBjdXJyZW50ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgIHJldHVybiBjdXJyZW50LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0ICE9PSBleGVjdXRpb24udXBkYXRlZF9hdDtcclxuICAgIH0sIHsgdGltZW91dDogNjBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbiAgfVxyXG4gIHRocm93IG5ldyBFcnJvcignV2l6YXJkIGV4Y2VlZGVkIDE2IHJldmlldy9jb250aW51YXRpb24gY2hlY2twb2ludHMuJyk7XHJcbn1cclxuXHJcbnRlc3QoJ3dpemFyZCByZWZ1c2VzIGFuIHVuYXZhaWxhYmxlIGNhdGFsb2cgYW5kIHJlY292ZXJzIHVzaW5nIHRoZSByZWFsIHJlZ2lzdHJ5IEBjYXRhbG9nLXJlY292ZXJ5JywgYXN5bmMgKHtwYWdlfSkgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1jYXRhbG9nLXJlY292ZXJ5LScgKyByYW5kb21VVUlEKCk7XHJcbiAgYXdhaXQgcGFnZS5yb3V0ZSgnKiovYXBpL3RlY2hub2xvZ2llcycsIHJvdXRlID0+IHJvdXRlLmZ1bGZpbGwoe3N0YXR1czo1MDMsXHJcbiAgICBjb250ZW50VHlwZTonYXBwbGljYXRpb24vanNvbicsYm9keTpKU09OLnN0cmluZ2lmeSh7ZXJyb3I6J0RlciB2b2xsc3TDpG5kaWdlIFRlY2hub2xvZ2lla2F0YWxvZyBpc3QgZGVyemVpdCBuaWNodCBlcnJlaWNoYmFyLid9KX0pKTtcclxuICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdhbGVydCcpKS50b0NvbnRhaW5UZXh0KCdUZWNobm9sb2dpZWthdGFsb2cnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7ZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdDYXRhbG9nIHJldHJ5Jyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7ZXhhY3Q6dHJ1ZX0pLmZpbGwoJ2VpbiBBa3RvciB6dW0gcHJvcG9ydGlvbmFsIHNjaGxpZcOfZW4gZWluZXMgVmVudGlsJyk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJykpLnRvQmVEaXNhYmxlZCgpO1xyXG4gIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icykudG9IYXZlTGVuZ3RoKDApO1xyXG4gIGF3YWl0IHBhZ2UudW5yb3V0ZSgnKiovYXBpL3RlY2hub2xvZ2llcycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6J1RlY2hub2xvZ2lla2F0YWxvZyBlcm5ldXQgbGFkZW4nfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYWxlcnQnKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJykpLnRvQmVFbmFibGVkKCk7XHJcbiAgY29uc3QgY2F0YWxvZyA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL3RlY2hub2xvZ2llcycpKS5qc29uKCk7XHJcbiAgZXhwZWN0KGNhdGFsb2cudGVjaG5vbG9neV9jb3VudCkudG9CZSgxMjUpO1xyXG59KTtcclxuXHJcbnRlc3QoJ25ldyBzbWFsbCB3aXphcmQgdHJhdmVyc2VzIGFsbCBuaW5lIHN0YWdlcyBhbmQgc3Vydml2ZXMgcmVsb2FkL3Jlc3RhcnQgQHNtYWxsJywgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IGVycm9yczogc3RyaW5nW10gPSBbXTsgcGFnZS5vbigncGFnZWVycm9yJywgZXJyb3IgPT4gZXJyb3JzLnB1c2goZXJyb3IubWVzc2FnZSkpO1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1zbWFsbC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjZW5naW5lZXJpbmctcHJvamVjdC1uYW1lJykuZmlsbCgnRTJFIHNtYWxsJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwoJ0VyemV1Z2UgZWluIEF1dG9tb3RpdmUgQ0FOLUZEIE5ldHp3ZXJrIG1pdCBlaW5lbSBHYXRld2F5IFN5c3RlbSwgZGVuIEVDVXMgTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UsIGVpbmVtIFNlbnNvciBNb3RvclRlbXBlcmF0dXJlIHVuZCBlaW5lbSBBa3RvciBNb3RvclZhbHZlLiBNb3RvclRlbXBlcmF0dXJlIHdpcmQgdm9uIE1vdG9yc3RldWVydW5nIGF1c2dld2VydGV0LiBNb3RvcnN0ZXVlcnVuZyBzdGV1ZXJ0IE1vdG9yVmFsdmUuIENvbnRyb2xsZXJzdGF0dXMgYmxlaWJ0IGJpcyB6dXIgQXVzd2FobCBrb25rcmV0ZXIgRW1wZsOkbmdlciB1bmQgU2lnbmFsZSBpbnRlcm4uIFByw7xmZSB1bmQgYXJiZWl0ZSBiaXMgRGF0YSBTY2llbmNlICYgSW50ZWxsaWdlbmNlLlxcbkNBTi1GRDogNTAwIGtiaXQvcyBhcmJpdHJhdGlvbiwgMiBNYml0L3MgZGF0YVxcbkNBTjogNTAwIGtiaXQvcycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdXZWl0ZXJlIEhpbndlaXNlJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKCctIEFrdG9yLUJlZmVobGU6IHtcIk1vdG9yVmFsdmVcIjp7XCJsZW5ndGhfYml0c1wiOjEsXCJkYXRhX3R5cGVcIjpcImJvb2xlYW5cIixcImZhY3RvclwiOjEsXCJ1bml0XCI6XCJjb2RlXCIsXCJtaW5fdmFsdWVcIjowLFwibWF4X3ZhbHVlXCI6MSxcInNlbWFudGljXCI6e1wic2VtYW50aWNfdHlwZVwiOlwiQk9PTEVBTlwifSxcImRhdGFcIjp7XCJlbnVtX3ZhbHVlc1wiOntcIkNMT1NFXCI6MCxcIk9QRU5cIjoxfX19fScpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdHZXLDpHRldW1mYW5nJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGZvciAoY29uc3QgW2xhYmVsLCB2YWx1ZV0gb2YgW1snR2F0ZXdheXMnLCAnMSddLCBbJ0NvbnRyb2xsZXInLCAnMiddLCBbJ1NlbnNvcmVuJywgJzEnXSwgWydBa3RvcmVuJywgJzEnXV0pIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKGAke2xhYmVsfTogdmVyYmluZGxpY2hlIEFuemFobGAsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCh2YWx1ZSk7XHJcbiAgY29uc3Qgc3RhcnRSZXF1ZXN0ID0gcGFnZS53YWl0Rm9yUmVxdWVzdChyZXF1ZXN0ID0+IHJlcXVlc3QudXJsKCkuZW5kc1dpdGgoJy9hcGkvYWdlbnQvY2hhdCcpXHJcbiAgICAmJiByZXF1ZXN0Lm1ldGhvZCgpID09PSAnUE9TVCcgJiYgcmVxdWVzdC5wb3N0RGF0YUpTT04oKT8ud2l6YXJkX2NvbW1hbmQ/LmFjdGlvbiA9PT0gJ1NUQVJUJyk7XHJcbiAgLy8gVXNlIHRoZSBzYW1lIHZpc2libGUgcXVlc3Rpb25uYWlyZSBuYXZpZ2F0aW9uIGEgdXNlciB1c2VzOyBuZXZlciBpbmplY3QgZ2VuZXJhdGVkIG1vZGVsIHJvd3MuXHJcbiAgZm9yIChsZXQgc3RlcCA9IDA7IHN0ZXAgPCAxMDsgc3RlcCsrKSB7XHJcbiAgICBjb25zdCBzdWJtaXQgPSBkaWFsb2cubG9jYXRvcignLmVuZy1hZ2VudC1xdWVzdGlvbm5haXJlLWhlYWQnKS5nZXRCeVJvbGUoJ2J1dHRvbicpO1xyXG4gICAgYXdhaXQgZXhwZWN0KHN1Ym1pdCkudG9CZUVuYWJsZWQoKTtcclxuICAgIGNvbnN0IG5hbWUgPSBhd2FpdCBzdWJtaXQuaW5uZXJUZXh0KCk7XHJcbiAgICBhd2FpdCBzdWJtaXQuY2xpY2soKTtcclxuICAgIGlmIChuYW1lID09PSAnw5xiZXJuZWhtZW4nKSBicmVhaztcclxuICAgIGlmIChzdGVwID09PSA5KSB0aHJvdyBuZXcgRXJyb3IoJ1F1ZXN0aW9ubmFpcmUgZGlkIG5vdCBvZmZlciBzdWJtaXQuJyk7XHJcbiAgfVxyXG4gIGNvbnN0IHJlcXVlc3RlZCA9IChhd2FpdCBzdGFydFJlcXVlc3QpLnBvc3REYXRhSlNPTigpLndpemFyZF9jb21tYW5kLndpemFyZF9jb250ZXh0O1xyXG4gIGV4cGVjdChyZXF1ZXN0ZWQudGVjaG5vbG9naWVzLCAnQW4gZXhwbGljaXQgQ0FOLUZEIHRhc2sgbXVzdCBub3Qgc2lsZW50bHkgcmVxdWVzdCBMSU4gYW5kIFNPTUUvSVAuJykudG9FcXVhbChbJ0NBTi1GRCAoY2FuX2ZkKSddKTtcclxuICAvLyBQcmVzZXJ2ZSBhIHJlYWwgcGVuZGluZyBtb2RlbCB0aHJvdWdoIHBhcmFtZXRlciBzYXZlIGFuZCByZW5ld2VkIHJldmlldy5cclxuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiAoYXdhaXQgcmVhZFByb2plY3QocGFnZSxwcm9qZWN0LCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpKS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uc3RhdGUsXHJcbiAgICB7dGltZW91dDoxODAwMDB9KS50b0JlKCdSRVZJRVdfUkVRVUlSRUQnKTtcclxuICBjb25zdCBwZW5kaW5nID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UscHJvamVjdCwnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKSkuZGF0YS5hY3RpdmVfcHJvcG9zYWw7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7cHJvamVjdH0mdGVjaG5vbG9neT1jYW5fZmQmcHJvcG9zYWw9JHtwZW5kaW5nfSNwYXJhbWV0ZXItZmluZGluZ3NgKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicse25hbWU6J0FrdHVlbGxlIFBhcmFtZXRlcmJlZnVuZGUnfSkpLnRvQ29udGFpblRleHQoJ25vY2ggbmljaHQgw7xiZXJub21tZW5lbiBWb3JzY2hsYWdzJyk7XHJcbiAgY29uc3QgY29tbW9uID0gcGFnZS5sb2NhdG9yKCcucGFyYW1ldGVyLWdyb3VwLWNvbW1vbicpO1xyXG4gIGF3YWl0IGV4cGVjdChjb21tb24ubG9jYXRvcignI2FyYml0cmF0aW9uX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzUwMCBrYml0L3MnKTtcclxuICBhd2FpdCBleHBlY3QoY29tbW9uLmxvY2F0b3IoJyNkYXRhX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzIgTWJpdC9zJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignLnBhcmFtZXRlci1kZXRhaWxzW29wZW5dJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IGNvbW1vbi5sb2NhdG9yKCcjc2VlZCcpLmZpbGwoJzQyJyk7XHJcbiAgYXdhaXQgY29tbW9uLmxvY2F0b3IoJyNkYXRhX2JpdHJhdGUnKS5maWxsKCcxIE1iaXQvcycpO1xyXG4gIGNvbnN0IGRhdGFQcmVzY2FsZXIgPSBwYWdlLmxvY2F0b3IoJyNjYW5fZmRfZGF0YV9wcmVzY2FsZXInKTtcclxuICBjb25zdCBkYXRhRGV0YWlscyA9IGRhdGFQcmVzY2FsZXIubG9jYXRvcigneHBhdGg9YW5jZXN0b3I6OmRldGFpbHMnKTtcclxuICBhd2FpdCBkYXRhRGV0YWlscy5sb2NhdG9yKCc6c2NvcGUgPiBzdW1tYXJ5JykuY2xpY2soKTtcclxuICBhd2FpdCBkYXRhUHJlc2NhbGVyLmZpbGwoJzInKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonUGFyYW1ldGVyIHNwZWljaGVybiDihpInLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnVGVjaG5vbG9naWUtIHVuZCBUaW1pbmctUGFyYW1ldGVyIGdlc3BlaWNoZXJ0LicpKS50b0JlVmlzaWJsZSgpO1xyXG4gIGNvbnN0IHN0YWxlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSxwcm9qZWN0LGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3BlbmRpbmd9P3ZpZXc9c3RhdHVzYCk7XHJcbiAgZXhwZWN0KHN0YWxlLmRhdGEuc3RhdHVzKS50b0JlKCdPVVREQVRFRCcpO1xyXG4gIGV4cGVjdChzdGFsZS5kYXRhLmNhbm9uaWNhbF9pZHMpLnRvRXF1YWwoW10pO1xyXG4gIGV4cGVjdCgoYXdhaXQgYWxsT2JqZWN0cyhwYWdlLHByb2plY3QsJ2hhcmR3YXJlLW5vZGVzJykpKS50b0hhdmVMZW5ndGgoMCk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjc2VlZCcpKS50b0hhdmVWYWx1ZSgnNDInKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZGF0YV9iaXRyYXRlJykpLnRvSGF2ZVZhbHVlKCcxIE1iaXQvcycpO1xyXG4gIGNvbnN0IHJ1bkJlZm9yZVJldHVybiA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLHByb2plY3QsJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5JykpLmNvbnRleHQuYWdlbnRfd2l6YXJkX3N0YXR1cy5ydW5faWQ7XHJcbiAgY29uc3Qgc3RhcnRzOiB1bmtub3duW10gPSBbXTtcclxuICBjb25zdCB0cmFja1N0YXJ0cyA9IChyZXF1ZXN0OiBpbXBvcnQoJ0BwbGF5d3JpZ2h0L3Rlc3QnKS5SZXF1ZXN0KSA9PiB7XHJcbiAgICBpZiAocmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JykgJiYgcmVxdWVzdC5tZXRob2QoKSA9PT0gJ1BPU1QnXHJcbiAgICAgICYmIHJlcXVlc3QucG9zdERhdGFKU09OKCk/LndpemFyZF9jb21tYW5kPy5hY3Rpb24gPT09ICdTVEFSVCcpIHN0YXJ0cy5wdXNoKHJlcXVlc3QucG9zdERhdGFKU09OKCkpO1xyXG4gIH07XHJcbiAgcGFnZS5vbigncmVxdWVzdCcsIHRyYWNrU3RhcnRzKTtcclxuICBsZXQgcmVzdW1lUmVzdG9yZSE6ICgpID0+IHZvaWQ7XHJcbiAgY29uc3QgcmVzdG9yZVBhdXNlID0gbmV3IFByb21pc2U8dm9pZD4ocmVzb2x2ZSA9PiB7IHJlc3VtZVJlc3RvcmUgPSByZXNvbHZlOyB9KTtcclxuICBjb25zdCBkZWxheVJlc3RvcmUgPSBhc3luYyAocm91dGU6IGltcG9ydCgnQHBsYXl3cmlnaHQvdGVzdCcpLlJvdXRlKSA9PiB7XHJcbiAgICBhd2FpdCByZXN0b3JlUGF1c2U7XHJcbiAgICBhd2FpdCByb3V0ZS5jb250aW51ZSgpO1xyXG4gIH07XHJcbiAgYXdhaXQgcGFnZS5yb3V0ZSgnKiovYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScsIGRlbGF5UmVzdG9yZSk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6J1p1csO8Y2sgenVtIEF1ZnRyYWcnLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cpLnRvQmVWaXNpYmxlKCk7XHJcbiAgdHJ5IHtcclxuICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7bmFtZTonR2VzcGVpY2hlcnRlbiBBdWZ0cmFnIHdpZWRlcmhlcnN0ZWxsZW4nfSkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nKS5ub3QudG9Db250YWluVGV4dCgnUHJvamVrdG5hbWU6IFNjaHJpdHQgMScpO1xyXG4gIH0gZmluYWxseSB7XHJcbiAgICByZXN1bWVSZXN0b3JlKCk7XHJcbiAgfVxyXG4gIGF3YWl0IHBhZ2UudW5yb3V0ZUFsbCh7IGJlaGF2aW9yOiAnd2FpdCcgfSk7XHJcbiAgY29uc3QgcmV2aWV3ID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJyx7bmFtZTonRW5naW5lZXJpbmctVm9yc2NobGFnJ30pO1xyXG4gIGF3YWl0IGV4cGVjdChyZXZpZXcpLnRvQ29udGFpblRleHQoJ0dlcHLDvGZ0IMK3IEZyZWlnYWJlIG9mZmVuJyk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZykudG9Db250YWluVGV4dCgnU3RhdHVzw7xiZXJzaWNodDogU2Nocml0dCA1IHZvbiA1Jyk7XHJcbiAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLHByb2plY3QsJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5JykpLmNvbnRleHQuYWdlbnRfd2l6YXJkX3N0YXR1cy5ydW5faWQpLnRvQmUocnVuQmVmb3JlUmV0dXJuKTtcclxuICBleHBlY3QoKGF3YWl0IGFsbE9iamVjdHMocGFnZSxwcm9qZWN0LCdoYXJkd2FyZS1ub2RlcycpKSkudG9IYXZlTGVuZ3RoKDApO1xyXG4gIGV4cGVjdChzdGFydHMpLnRvRXF1YWwoW10pO1xyXG4gIHBhZ2Uub2ZmKCdyZXF1ZXN0JywgdHJhY2tTdGFydHMpO1xyXG4gIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgdHJ1ZSxcclxuICAgIFsnU3lzdGVtJywgJ01vdG9yc3RldWVydW5nJywgJ0FuemVpZ2UnLCAnTW90b3JUZW1wZXJhdHVyZScsICdNb3RvclZhbHZlJ10pO1xyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCA1LCB1bmRlZmluZWQsIHtcclxuICAgIHNlZWQ6IDQyLCBkYXRhX2JpdHJhdGU6IDFfMDAwXzAwMCwgY2FuX2ZkX2RhdGFfcHJlc2NhbGVyOiAyLFxyXG4gIH0pO1xyXG4gIGV4cGVjdChhcnRpZmFjdHMuYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoMyk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnRyYW5zcG9ydF9leGNsdXNpb25zKS50b0hhdmVMZW5ndGgoMyk7XHJcbiAgY29uc3QgZmluaXNoZWQgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5pbmNsdWRlcyhgL3J1bnMvJHtjb250aW51aXR5LnJ1bklkfS9maW5pc2hgKVxyXG4gICAgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0ZlcnRpZyBzdGVsbGVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBleHBlY3QoKGF3YWl0IGZpbmlzaGVkKS5vaygpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cpLm5vdC50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KGVycm9ycykudG9FcXVhbChbXSk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCAuLi5jb250aW51aXR5LCAuLi5hcnRpZmFjdHMgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG5cclxuZm9yIChjb25zdCB0ZWNobm9sb2d5IG9mIFsnSTJDJywgJ01vZGJ1cyBSVFUnXSkge1xyXG4gIHRlc3QoYFJhc3BiZXJyeSBQaSAke3RlY2hub2xvZ3l9IHByb2plY3QgcmV0YWlucyBtb2RlbCBhbmQgYmxvY2tzIGluY29uc2lzdGVudCBuYXRpdmUgcGFyYW1ldGVycyBAbm9uYXV0b21vdGl2ZWAsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICAgIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1lbWJlZGRlZC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gICAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdQcm9qZWt0bmFtZScsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjZW5naW5lZXJpbmctcHJvamVjdC1uYW1lJykuZmlsbCgnVGVtcGVyYXR1cnJlZ2VsdW5nJyk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCh0ZWNobm9sb2d5ID09PSAnSTJDJ1xyXG4gICAgICA/ICcyIEFrdG9yZW4gZsO8ciBWZW50aWxlLCA0IFNlbnNvcmVuIGbDvHIgVGVtcGVyYXR1cmVuLCB1bmQgZWluIFJhc3BiZXJyeVBpJ1xyXG4gICAgICA6IGAyIEFrdG9yZW4gZsO8ciBWZW50aWxlLCA0IFNlbnNvcmVuIGbDvHIgVGVtcGVyYXR1cmVuLCB1bmQgZWluIFJhc3BiZXJyeVBpLiBFbWJlZGRlZCBTeXN0ZW1zLiBBbGxlIEdlcsOkdGUga29tbXVuaXppZXJlbiDDvGJlciAke3RlY2hub2xvZ3l9LiBQcsO8ZmUgdW5kIGFyYmVpdGUgYmlzIERhdGEgU2NpZW5jZSAmIEludGVsbGlnZW5jZS5gKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdOZXR6YXJjaGl0ZWt0dXInLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdyYWRpbycsIHsgbmFtZTogL1ZhcmlhbnRlIDAvIH0pLmNoZWNrKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnR2Vyw6R0ZXVtZmFuZycsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGlmICh0ZWNobm9sb2d5ID09PSAnSTJDJykge1xyXG4gICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdSYXNwYmVycnlQaTogQW5zY2hsdXNzJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ0kyQycpO1xyXG4gICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5TGFiZWwoJ1RlbXBlcmF0dXJzZW5zb3IxOiBBbnNjaGx1c3MnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgICAgZm9yIChjb25zdCBuYW1lIG9mIFsnUmFzcGJlcnJ5UGknLCAnVGVtcGVyYXR1cnNlbnNvcjEnLCAnVGVtcGVyYXR1cnNlbnNvcjInLCAnVGVtcGVyYXR1cnNlbnNvcjMnLCAnVGVtcGVyYXR1cnNlbnNvcjQnLCAnVmVudGlsYWt0b3IxJywgJ1ZlbnRpbGFrdG9yMiddKSB7XHJcbiAgICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoYCR7bmFtZX06IEFuc2NobHVzc2AsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdJMkMnKTtcclxuICAgICAgfVxyXG4gICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnU2Vuc29yIDE6IE1lc3NncsO2w59lJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ3NwZWVkJyk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlMYWJlbCgnVGVtcGVyYXR1cnNlbnNvcjE6IEFuc2NobHVzcycsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZVZhbHVlKCdJMkMnKTtcclxuICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1NlbnNvciAxOiBNZXNzZ3LDtsOfZScsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCd0ZW1wZXJhdHVyZScpO1xyXG4gICAgfVxyXG4gICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMTogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignT1BFTl9DTE9TRScpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeUxhYmVsKCdWZW50aWxha3RvcjI6IFN0ZWxsYmVmZWhsJywgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoJycpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMjogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignT1BFTl9DTE9TRScpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCB0cnVlLCBbJ1Jhc3BiZXJyeVBpJywgJ1RlbXBlcmF0dXJzZW5zb3IxJywgJ1RlbXBlcmF0dXJzZW5zb3IyJywgJ1RlbXBlcmF0dXJzZW5zb3IzJywgJ1RlbXBlcmF0dXJzZW5zb3I0JywgJ1ZlbnRpbGFrdG9yMScsICdWZW50aWxha3RvcjInXSwgZmFsc2UsIHVuZGVmaW5lZCwgdW5kZWZpbmVkLCB0cnVlKSlcclxuICAgICAgLnJlamVjdHMudG9UaHJvdygvV2l6YXJkIEJMT0NLRUQgYXQgcGFyYW1ldGVyczouKmJlc3TDpHRpZ3RlIEFuZ2FiZW4vKTtcclxuICAgIGNvbnN0IHdvcmtmbG93ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cnKTtcclxuICAgIGNvbnN0IGZpbmRpbmdzID0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24uYmxvY2tpbmdfZmluZGluZ3MgYXMgeyBjb2RlOiBzdHJpbmcgfVtdO1xyXG4gICAgZXhwZWN0KGZpbmRpbmdzLm1hcChpdGVtID0+IGl0ZW0uY29kZSkpLnRvQ29udGFpbignVEVDSE5PTE9HWV9QQVJBTUVURVJfREVQRU5ERU5DWV9NSVNNQVRDSCcpO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LnN0YXR1c2VzLnBhcmFtZXRlcnMpLnRvQmUoJ0lOX1BST0dSRVNTJyk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuYXJ0aWZhY3RfY2hlY2tzLnBhcmFtZXRlcnMuY29tcGxldGUpLnRvQmUoZmFsc2UpO1xyXG4gICAgY29uc3QgcmVxdWlyZWQgPSB3b3JrZmxvdy5hcnRpZmFjdF9jaGVja3MucGFyYW1ldGVycy5yZXF1aXJlZDtcclxuICAgIGV4cGVjdChyZXF1aXJlZC5wcm9maWxlX3ZhbHVlcykudG9CZShmYWxzZSk7XHJcbiAgICBjb25zdCBkZXZpY2VTb3VyY2UgPSB0ZWNobm9sb2d5ID09PSAnSTJDJyA/ICdpMmNfZGV2aWNlX3NvdXJjZScgOiAnbXJfZGV2aWNlX3NvdXJjZSc7XHJcbiAgICAvLyBUaGVzZSBzY2VuYXJpb3MgcmVtYWluIGJsb2NrZWQgYnkgcmVhbCBuYXRpdmUgZGVwZW5kZW5jaWVzLCBub3QgYnkgdGhlXHJcbiAgICAvLyBhYnNlbmNlIG9mIGEgcmVhbCBkZXZpY2UgcXVhbGlmaWNhdGlvbiBvciBmYWJyaWNhdGVkIHNvdXJjZSBpZGVudGlmaWVyLlxyXG4gICAgZXhwZWN0KHJlcXVpcmVkKS5ub3QudG9IYXZlUHJvcGVydHkoZGV2aWNlU291cmNlLCBmYWxzZSk7XHJcbiAgICBjb25zdCBuYXRpdmVUZWNobm9sb2d5ID0gdGVjaG5vbG9neSA9PT0gJ0kyQycgPyAnaTJjJyA6ICdtb2RidXNfcnR1JztcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5wYXJhbWV0ZXJzLnNpbXVsYXRpb25fcGFyYW1ldGVyX2Fzc3VtcHRpb25zW25hdGl2ZVRlY2hub2xvZ3ldLnZhbHVlcylcclxuICAgICAgLm5vdC50b0hhdmVQcm9wZXJ0eShkZXZpY2VTb3VyY2UpO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LmFydGlmYWN0X2NoZWNrcy5wYXJhbWV0ZXJzLnByb2ZpbGVfZmluZGluZ3Muc29tZSgoZmluZGluZzoge2NvZGU6IHN0cmluZ30pID0+XHJcbiAgICAgIGZpbmRpbmcuY29kZSA9PT0gJ1RFQ0hOT0xPR1lfUEFSQU1FVEVSX0RFUEVOREVOQ1lfTUlTTUFUQ0gnKSkudG9CZSh0cnVlKTtcclxuICAgIGNvbnN0IGV2aWRlbmNlUmV2aWV3ID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywge25hbWU6ICdCbG9ja2llcmVuZGUgUHJlZmxpZ2h0LUJlZnVuZGUnfSk7XHJcbiAgICBhd2FpdCBleHBlY3QoZXZpZGVuY2VSZXZpZXcpLnRvQ29udGFpblRleHQodGVjaG5vbG9neSA9PT0gJ0kyQycgPyAnaTJjX3B1bGx1cF9vaG1zJyA6ICdtcl9wZHVfYnl0ZXMnKTtcclxuICAgIGF3YWl0IGV4cGVjdChldmlkZW5jZVJldmlldy5nZXRCeVJvbGUoJ2xpbmsnLCB7bmFtZTogJ0JldHJvZmZlbmUgQW5nYWJlbiBiZWFyYmVpdGVuJ30pLmZpcnN0KCkpXHJcbiAgICAgIC50b0hhdmVBdHRyaWJ1dGUoJ2hyZWYnLCBuZXcgUmVnRXhwKGBtb2RlPXBhcmFtZXRlcnMuKnByb2plY3Q9JHtwcm9qZWN0fWApKTtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5zdGF0dXNlcy5zaW11bGF0aW9uKS50b0JlKCdFTVBUWScpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGV4cGVjdCh3b3JrZmxvdy5wYXJhbWV0ZXJzLnJhdGVfcmV2aWV3X3Byb3Bvc2Fscy5pMmMuc3RhdHVzKS50b0JlKCdSRVZJRVdfUkVRVUlSRUQnKTtcclxuICAgICAgZXhwZWN0KHdvcmtmbG93LnBhcmFtZXRlcnMucGFyYW1ldGVyX3Byb3ZlbmFuY2UuYml0cmF0ZS5zb3VyY2UpLnRvQmUoJ1RFQ0hOT0xPR1lfUFJPRklMRV9SRVZJRVdfUFJPUE9TQUwnKTtcclxuICAgIH1cclxuICAgIGNvbnN0IGludGVyZmFjZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1pbnRlcmZhY2VzJyk7XHJcbiAgICBleHBlY3QoaW50ZXJmYWNlcy5sZW5ndGgpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoNyk7XHJcbiAgICBleHBlY3QoaW50ZXJmYWNlcy5ldmVyeShpdGVtID0+ICEvYXV0b21vdGl2ZXxjYW58bGluL2kudGVzdChpdGVtLnRlY2hub2xvZ3kpKSkudG9CZSh0cnVlKTtcclxuICAgIGNvbnN0IGhhcmR3YXJlID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICAgIGV4cGVjdChoYXJkd2FyZS5ldmVyeShpdGVtID0+IGl0ZW0uZG9tYWluICE9PSAnYXV0b21vdGl2ZScpKS50b0JlKHRydWUpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGNvbnN0IHNpZ25hbHMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyk7XHJcbiAgICAgIGV4cGVjdChzaWduYWxzLnNvbWUoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdUZW1wZXJhdHVyX1RlbXBlcmF0dXJzZW5zb3IxJyAmJiBpdGVtLnVuaXQgPT09ICdkZWdDJykpLnRvQmUodHJ1ZSk7XHJcbiAgICB9XHJcbiAgICBleHBlY3QoKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnMpLnRvSGF2ZUxlbmd0aCgwKTtcclxuICAgIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnbm9uYXV0b21vdGl2ZS1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCB0ZWNobm9sb2d5LCBmaW5kaW5ncyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICB9KTtcclxufVxyXG5cclxudGVzdCgnZXhhY3QgY29uZmlybWVkIDUwLzI1MC8yNTAgcmVxdWVzdCBjb21wbGV0ZXMgdGhyb3VnaCByZWFsIHdpemFyZCByZXZpZXcgQGxhcmdlJywgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IGVycm9yczogc3RyaW5nW10gPSBbXTsgcGFnZS5vbigncGFnZWVycm9yJywgZXJyb3IgPT4gZXJyb3JzLnB1c2goZXJyb3IubWVzc2FnZSkpO1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1sYXJnZS0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IHJ1bklkID0gcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IG9yaWdpbmFsID0gYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2UtNTAtMjUwLTI1MC50eHQnLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpO1xyXG4gIGNvbnN0IG1ldGFkYXRhID0gSlNPTi5wYXJzZShhd2FpdCByZWFkRmlsZShuZXcgVVJMKCcuL2ZpeHR1cmVzL3dpemFyZC1sYXJnZS01MC0yNTAtMjUwLmpzb24nLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpKTtcclxuICBjb25zdCBiYXNlbGluZSA9IEpTT04ucGFyc2UoYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2Utc2lnbmFsLWNvbnRyYWN0cy5qc29uJywgaW1wb3J0Lm1ldGEudXJsKSwgJ3V0ZjgnKSk7XHJcbiAgY29uc3QgcHJvbXB0ID0gb3JpZ2luYWwucmVwbGFjZSgvXi0gTGF1Zi1JRDouKiQvbSwgJy0gTGF1Zi1JRDogJyArIHJ1bklkKTtcclxuICBhd2FpdCByZXZpZXdWaXJ0dWFsVHJhbnNwb3J0cyhwYWdlLCBwcm9qZWN0KTtcclxuICAvLyBSZXBsYXkgdGhlIGNhcHR1cmVkLCBhbHJlYWR5IGNvbmZpcm1lZCBpbnB1dCB0aHJvdWdoIHRoZSBub3JtYWwgU1RBUlQgQVBJLlxyXG4gIC8vIEFsbCBwcm9wb3NhbCBpbnNwZWN0aW9uLCBhcHByb3ZhbCwgY29udGludWF0aW9uIGFuZCByZWxvYWRzIGJlbG93IHVzZSBVSS5cclxuICBjb25zdCBzdGFydGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY2hhdCcsIHtcclxuICAgIGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSwgdGltZW91dDogMjQwXzAwMCxcclxuICAgIGRhdGE6IHsgcHJvbXB0LCB3aXphcmRfY29tbWFuZDogeyBhY3Rpb246ICdTVEFSVCcsIHJ1bl9pZDogcnVuSWQsIG9wZXJhdGlvbl9pZDogcmFuZG9tVVVJRCgpLFxyXG4gICAgICB0YXJnZXQ6ICdkYXRhX3NjaWVuY2VfaW50ZWxsaWdlbmNlJywgd2l6YXJkX2NvbnRleHQ6IHsgLi4ubWV0YWRhdGEud2l6YXJkX2NvbnRleHQsIHByb2plY3RfaWQ6IHByb2plY3QsIHJ1bl9pZDogcnVuSWQgfSB9IH0sXHJcbiAgfSk7XHJcbiAgaWYgKCFzdGFydGVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke3N0YXJ0ZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBzdGFydGVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBjb25zdCBjb250aW51aXR5ID0gYXdhaXQgY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIGZhbHNlLCBbXSwgdHJ1ZSwgYmFzZWxpbmUuc2lnbmFscyk7XHJcbiAgZXhwZWN0KGNvbnRpbnVpdHkucnVuSWQpLnRvQmUocnVuSWQpO1xyXG4gIGNvbnN0IGhhcmR3YXJlID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICBleHBlY3QoaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5kZXZpY2VfdHlwZSA9PT0gJ1NlbnNvckNvbnRyb2xsZXInKSkudG9IYXZlTGVuZ3RoKDI1MCk7XHJcbiAgZXhwZWN0KGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0uZGV2aWNlX3R5cGUgPT09ICdBY3R1YXRvckNvbnRyb2xsZXInKSkudG9IYXZlTGVuZ3RoKDI1MCk7XHJcbiAgZXhwZWN0KGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0uZGV2aWNlX3R5cGUgPT09ICdFQ1UnKS5sZW5ndGgpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoNTApO1xyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCAxNDA0KTtcclxuICBjb25zdCBleGNsdWRlZFNpZ25hbElkcyA9IG5ldyBTZXQoYXJ0aWZhY3RzLmFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UudHJhbnNwb3J0X2V4Y2x1c2lvbnNcclxuICAgIC5mbGF0TWFwKChpdGVtOiB7IHNpZ25hbF9pZHM6IHN0cmluZ1tdIH0pID0+IGl0ZW0uc2lnbmFsX2lkcykpO1xyXG4gIGV4cGVjdChleGNsdWRlZFNpZ25hbElkcy5zaXplKS50b0JlKDIzNSk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50Lm9ic2VydmVkX3NpZ25hbF9jb3VudCkudG9CZSgxMTY5KTtcclxuICBhd2FpdCB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZSwgcHJvamVjdCwgYmFzZWxpbmUuc2lnbmFscyk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5qb2IpLnRvQmUoY29udGludWl0eS5yZXN0YXJ0ZWRKb2JJZCk7XHJcbiAgZXhwZWN0KGVycm9ycykudG9FcXVhbChbXSk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCBmaXh0dXJlOiBtZXRhZGF0YS5yZXF1ZXN0X3NoYTI1NiwgLi4uY29udGludWl0eSwgLi4uYXJ0aWZhY3RzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuXHJcbnRlc3QoJ2EgcmVhbCBBTUVORCBhZnRlciBtb2RlbCBhcHByb3ZhbCBhZGRzIHRoZSByZXF1ZXN0ZWQgc2Vuc29yIGFuZCByZXVzZXMgaXRzIG5ldHdvcmtzIEBhbWVuZCcsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtYW1lbmQtJyArIHJhbmRvbVVVSUQoKTtcclxuICBhd2FpdCByZXZpZXdWaXJ0dWFsVHJhbnNwb3J0cyhwYWdlLCBwcm9qZWN0KTtcclxuICBjb25zdCBydW5JZCA9IHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBncmFwaCA9IFtcclxuICAgIHsgY2x1c3Rlcl9pZDogJ2RyaXZlJywgbmV0d29ya19pZDogJ2Nhbl9mZCcsIG5ldHdvcmtfbGFiZWw6ICdDQU4tRkQnLCBidXNfbmFtZTogJ0RyaXZlJyxcclxuICAgICAgY29udHJvbGxlcnM6IFt7IGVjdTogJ01vdG9yc3RldWVydW5nJywgc2Vuc29yczogW10gYXMgc3RyaW5nW10sIGFjdHVhdG9yczogW10gfV0sXHJcbiAgICAgIGhtaV9yb3V0ZXM6IFt7IHNvdXJjZTogJ01vdG9yc3RldWVydW5nJywgdGFyZ2V0OiAnQW56ZWlnZScgfSwgeyBzb3VyY2U6ICdBbnplaWdlJywgdGFyZ2V0OiAnTW90b3JzdGV1ZXJ1bmcnIH0sXHJcbiAgICAgICAgeyBzb3VyY2U6ICdTeXN0ZW0nLCB0YXJnZXQ6ICdBbnplaWdlJyB9XSB9LFxyXG4gICAgeyBjbHVzdGVyX2lkOiAnZGlzcGxheScsIG5ldHdvcmtfaWQ6ICdldGhlcm5ldCcsIG5ldHdvcmtfbGFiZWw6ICdFdGhlcm5ldCcsIGJ1c19uYW1lOiAnRGlzcGxheScsXHJcbiAgICAgIGNvbnRyb2xsZXJzOiBbeyBlY3U6ICdBbnplaWdlJywgc2Vuc29yczogW10gYXMgc3RyaW5nW10sIGFjdHVhdG9yczogW10gfV0gfSxcclxuICBdO1xyXG4gIGNvbnN0IHByb21wdCA9IGBTdHJ1a3R1cmllcnRlIFZvcmdhYmVuIGZ1ZXIgZGVuIEVuZ2luZWVyaW5nLUFnZW50ZW46XHJcbi0gTGF1Zi1JRDogJHtydW5JZH1cclxuLSBJbmR1c3RyaWU6IEF1dG9tb3RpdmVcclxuLSBOZXR6d2Vya3RlY2hub2xvZ2llbjogQ0FOLUZEIChjYW5fZmQpOyBFdGhlcm5ldCAoZXRoZXJuZXQpXHJcbkNBTi1GRDogNTAwIGtiaXQvcyBhcmJpdHJhdGlvbiwgMiBNYml0L3MgZGF0YVxyXG5DQU46IDUwMCBrYml0L3NcclxuRXRoZXJuZXQ6IDEwMCBNYml0L3NcclxuLSBIYXJkd2FyZS1Tb2xsd2VydGU6IHtcImdhdGV3YXlzXCI6MSxcImVjdXNcIjoyLFwic2Vuc29yc1wiOjAsXCJhY3R1YXRvcnNcIjowfVxyXG4tIFN5c3RlbWNsdXN0ZXItR3JhcGg6ICR7SlNPTi5zdHJpbmdpZnkoZ3JhcGgpfVxyXG5Lb25rcmV0ZSBBdWZnYWJlIGRlcyBOdXR6ZXJzLCBwZXIgV2l6YXJkLVVlYmVybmVobWVuIGJlc3RhZXRpZ3Q6XHJcbk1vdG9yc3RldWVydW5nIHVuZCBBbnplaWdlIG1pdCBlaW5lbSB6ZW50cmFsZW4gR2F0ZXdheSBTeXN0ZW0gdmVyYmluZGVuLmA7XHJcbiAgY29uc3Qgc3RhcnRlZCA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NoYXQnLCB7XHJcbiAgICBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0sIHRpbWVvdXQ6IDEyMF8wMDAsXHJcbiAgICBkYXRhOiB7IHByb21wdCwgd2l6YXJkX2NvbW1hbmQ6IHsgYWN0aW9uOiAnU1RBUlQnLCBydW5faWQ6IHJ1bklkLCBvcGVyYXRpb25faWQ6IHJhbmRvbVVVSUQoKSxcclxuICAgICAgdGFyZ2V0OiAnZGF0YV9zY2llbmNlX2ludGVsbGlnZW5jZScsIHdpemFyZF9jb250ZXh0OiB7IHByb2plY3RfaWQ6IHByb2plY3QsIHJ1bl9pZDogcnVuSWQsXHJcbiAgICAgICAgcHJvamVjdF9uYW1lOiAnRTJFIGFtZW5kbWVudCcsIHNjb3BlX2lkczogc3RlcHMsIG1vZGU6ICdmdWxsJyxcclxuICAgICAgICBwcm9jZXNzX2lkczogWydkZWZhdWx0cycsICdyZXZpZXdfZ2F0ZScsICdhcHByb3ZlX2FmdGVyX2FsbG93J10sIHRhc2s6ICdNb3RvcnN0ZXVlcnVuZyB1bmQgQW56ZWlnZSBhbiBTeXN0ZW0nIH0gfSB9LFxyXG4gIH0pO1xyXG4gIGlmICghc3RhcnRlZC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYEhUVFAgJHtzdGFydGVkLnN0YXR1cygpfTogJHsoYXdhaXQgc3RhcnRlZC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgbGV0IG9yaWdpbmFsTmV0d29ya3M6IHN0cmluZ1tdID0gW107XHJcbiAgY29uc3QgYW1lbmQgPSBhc3luYyAoKSA9PiB7XHJcbiAgICBvcmlnaW5hbE5ldHdvcmtzID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93JykpLnBhcmFtZXRlcnMubmV0d29ya3NcclxuICAgICAgLm1hcCgoaXRlbTogeyBpZDogc3RyaW5nIH0pID0+IGl0ZW0uaWQpLnNvcnQoKTtcclxuICAgIGV4cGVjdChvcmlnaW5hbE5ldHdvcmtzKS50b0hhdmVMZW5ndGgoMik7XHJcbiAgICBncmFwaFswXS5jb250cm9sbGVyc1swXS5zZW5zb3JzLnB1c2goJ01vdG9yVGVtcGVyYXR1cmUnKTtcclxuICAgIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XHJcbiAgICBjb25zdCBleHBhbmQgPSBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdFcmfDpG56ZW4nLCBleGFjdDogdHJ1ZSB9KTtcclxuICAgIGF3YWl0IGV4cGVjdChleHBhbmQpLnRvQmVFbmFibGVkKHsgdGltZW91dDogMTIwXzAwMCB9KTtcclxuICAgIGF3YWl0IGV4cGFuZC5jbGljaygpO1xyXG4gICAgY29uc3QgZmllbGQgPSBkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyZ8OkbnplbicsIGV4YWN0OiB0cnVlIH0pLmdldEJ5Um9sZSgndGV4dGJveCcpO1xyXG4gICAgYXdhaXQgZmllbGQuZmlsbCgnRXJnw6RuemUgTW90b3JUZW1wZXJhdHVyZSBhbHMgU2Vuc29yIGRlciBNb3RvcnN0ZXVlcnVuZy4gRGllIHZvbGxzdMOkbmRpZ2UgYWt0dWFsaXNpZXJ0ZSBGcmVpZ2FiZSBsYXV0ZXQ6XFxuJ1xyXG4gICAgICArICctIEhhcmR3YXJlLVNvbGx3ZXJ0ZToge1wiZ2F0ZXdheXNcIjoxLFwiZWN1c1wiOjIsXCJzZW5zb3JzXCI6MSxcImFjdHVhdG9yc1wiOjB9XFxuJ1xyXG4gICAgICArICctIFN5c3RlbWNsdXN0ZXItR3JhcGg6ICcgKyBKU09OLnN0cmluZ2lmeShncmFwaCkpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRXJnw6RuenVuZyBhbmFseXNpZXJlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBleHBlY3QoZmllbGQpLm5vdC50b0JlVmlzaWJsZSh7IHRpbWVvdXQ6IDEyMF8wMDAgfSk7XHJcbiAgfTtcclxuICBjb25zdCBjb250aW51aXR5ID0gYXdhaXQgY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIGZhbHNlLCBbJ01vdG9yc3RldWVydW5nJywgJ0FuemVpZ2UnXSwgZmFsc2UsIHVuZGVmaW5lZCwgYW1lbmQpO1xyXG4gIGNvbnN0IGhhcmR3YXJlID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICBjb25zdCBvd25lciA9IGhhcmR3YXJlLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdNb3RvcnN0ZXVlcnVuZycpO1xyXG4gIGNvbnN0IHNlbnNvcnMgPSBoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdNb3RvclRlbXBlcmF0dXJlJyk7XHJcbiAgZXhwZWN0KHNlbnNvcnMpLnRvSGF2ZUxlbmd0aCgxKTtcclxuICBleHBlY3Qoc2Vuc29yc1swXS5pZGVudGl0eS5zeXN0ZW1fb3duZXJfaWQpLnRvQmUob3duZXIuaWQpO1xyXG4gIGNvbnN0IHNlbnNvck5ldHdvcmsgPSAnRHJpdmUtSU8tbW90b3JzdGV1ZXJ1bmctY2FuLWZkLVMwMSc7XHJcbiAgY29uc3QgbmV0d29ya3MgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cnKSkucGFyYW1ldGVycy5uZXR3b3JrcztcclxuICBleHBlY3QobmV0d29ya3MubWFwKChpdGVtOiB7IGlkOiBzdHJpbmcgfSkgPT4gaXRlbS5pZCkuc29ydCgpKS50b0VxdWFsKFsuLi5vcmlnaW5hbE5ldHdvcmtzLCBzZW5zb3JOZXR3b3JrXS5zb3J0KCkpO1xyXG4gIGV4cGVjdChuZXcgU2V0KG5ldHdvcmtzLm1hcCgoaXRlbTogeyBuYW1lOiBzdHJpbmcgfSkgPT4gaXRlbS5uYW1lKSkuc2l6ZSkudG9CZShuZXR3b3Jrcy5sZW5ndGgpO1xyXG4gIGNvbnN0IHRvcG9sb2d5ID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L25ldHdvcmstdmlldycpKS50b3BvbG9neTtcclxuICBjb25zdCBsb2NhbEVkZ2UgPSB0b3BvbG9neS5lZGdlcy5maW5kKChlZGdlOiBhbnkpID0+IGVkZ2UucGh5c2ljYWxOZXR3b3JrSWQgPT09IHNlbnNvck5ldHdvcmspO1xyXG4gIGV4cGVjdChsb2NhbEVkZ2UpLnRvQmVUcnV0aHkoKTtcclxuICBleHBlY3QobG9jYWxFZGdlLmJ1cykudG9CZSgnY2FuX2ZkJyk7XHJcbiAgZXhwZWN0KE9iamVjdC52YWx1ZXMobG9jYWxFZGdlLnJvdXRpbmdNZXRhZGF0YSkpLnRvQ29udGFpbkVxdWFsKGV4cGVjdC5vYmplY3RDb250YWluaW5nKHtcclxuICAgIHNvdXJjZTogc2Vuc29yc1swXS5pZCwgdGFyZ2V0OiBvd25lci5pZCwgYXBwcm92YWxTdGF0ZTogJ0FQUFJPVkVEJywgcHJvdG9jb2w6ICdDQU5fRkQnLFxyXG4gIH0pKTtcclxuICBmb3IgKGNvbnN0IFtzaWRlLCBoYXJkd2FyZUlkXSBvZiBbWydzb3VyY2UnLCBzZW5zb3JzWzBdLmlkXSwgWyd0YXJnZXQnLCBvd25lci5pZF1dKSB7XHJcbiAgICBjb25zdCBub2RlID0gdG9wb2xvZ3kubm9kZXMuZmluZCgoaXRlbTogYW55KSA9PiBpdGVtLmlkID09PSBsb2NhbEVkZ2Vbc2lkZV0pO1xyXG4gICAgZXhwZWN0KG5vZGUuZW5naW5lZXJpbmdJZCkudG9CZShoYXJkd2FyZUlkKTtcclxuICAgIGV4cGVjdChub2RlLnBvcnRzKS50b0NvbnRhaW5FcXVhbChleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7IGlkOiBsb2NhbEVkZ2Vbc2lkZSArICdQb3J0J10sXHJcbiAgICAgIGJ1czogJ2Nhbl9mZCcsIHBoeXNpY2FsTmV0d29ya0lkOiBzZW5zb3JOZXR3b3JrIH0pKTtcclxuICB9XHJcbiAgY29uc3QgYXJ0aWZhY3RzID0gYXdhaXQgdmVyaWZ5QXJ0aWZhY3RzKHBhZ2UsIHByb2plY3QsIDEpO1xyXG4gIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnYW1lbmRtZW50LWV2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIC4uLmNvbnRpbnVpdHksIC4uLmFydGlmYWN0cyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxufSk7XHJcblxyXG4vLyBSZWFsIGlzb2xhdGVkIFVJIC0+IHBlcnNpc3RlZCBtb2RlbCBib3VuZGFyeSByZWdyZXNzaW9uLCBub3QgbmluZS1zdGFnZSBjb21wbGV0aW9uIHByb29mLlxyXG50ZXN0KCdyZXZpZXdhYmxlIGZ1bmN0aW9uYWwgVFgvUlggT0ZGIHN1cnZpdmVzIHJlcXVlc3QgcmVsb2FkIGFuZCBjYW5vbmljYWwgbW9kZWwgYWRvcHRpb24gQHR4cngnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXR4cngtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdQcm9qZWt0bmFtZScsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cubG9jYXRvcignI2VuZ2luZWVyaW5nLXByb2plY3QtbmFtZScpLmZpbGwoJ1RYIFJYIGZ1bmN0aW9uYWwgcGFydG5lcnMnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCgnRXJ6ZXVnZSBlaW4gQXV0b21vdGl2ZSBDQU4tRkQgTmV0endlcmsgbWl0IGVpbmVtIEdhdGV3YXkgU3lzdGVtIHVuZCBkZW4gRUNVcyBNb3RvcnN0ZXVlcnVuZywgR2V0cmllYmVzdGV1ZXJ1bmcgdW5kIEVsZWt0cm9tb3RvcnN0ZXVlcnVuZy4gRGllIGJlcmVjaG5ldGVuIEZ1bmt0aW9uc2F1c2fDpG5nZSBkaWVuZW4gZGVyIEFudHJpZWJza29vcmRpbmF0aW9uLiBDb250cm9sbGVyc3RhdHVzIGJsZWlidCBpbnRlcm4uXFxuQ0FOLUZEOiA1MDAga2JpdC9zIGFyYml0cmF0aW9uLCAyIE1iaXQvcyBkYXRhJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ0dlcsOkdGV1bWZhbmcnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQXV0b21vdGl2ZSAvIFZlaGljbGUgw7xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGZvciAoY29uc3QgW2xhYmVsLCB2YWx1ZV0gb2YgW1snR2F0ZXdheXMnLCAnMSddLCBbJ0NvbnRyb2xsZXInLCAnMyddLCBbJ1NlbnNvcmVuJywgJzAnXSwgWydBa3RvcmVuJywgJzAnXV0pIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKGAke2xhYmVsfTogdmVyYmluZGxpY2hlIEFuemFobGAsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCh2YWx1ZSk7XHJcbiAgY29uc3QgdHhyeCA9IGRpYWxvZy5sb2NhdG9yKCdkZXRhaWxzJykuZmlsdGVyKHsgaGFzOiBwYWdlLmxvY2F0b3IoJ3N1bW1hcnknKS5maWx0ZXIoeyBoYXNUZXh0OiAvXlRYXFwvUlgvIH0pIH0pLmZpcnN0KCk7XHJcbiAgYXdhaXQgZXhwZWN0KHR4cngpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgdHhyeC5sb2NhdG9yKCdzdW1tYXJ5JykuY2xpY2soKTtcclxuICBjb25zdCBzZWxlY3RlZCA9IHR4cnguZ2V0QnlSb2xlKCdzd2l0Y2gnLCB7IG5hbWU6ICdNb3RvckRyZWhtb21lbnRJc3Qg4oaSIEdldHJpZWJlc3RldWVydW5nJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgYXdhaXQgZXhwZWN0KHNlbGVjdGVkKS50b0JlQ2hlY2tlZCgpOyBhd2FpdCBzZWxlY3RlZC51bmNoZWNrKCk7XHJcbiAgY29uc3Qgc3RhcnRSZXF1ZXN0ID0gcGFnZS53YWl0Rm9yUmVxdWVzdChyZXF1ZXN0ID0+IHJlcXVlc3QudXJsKCkuZW5kc1dpdGgoJy9hcGkvYWdlbnQvY2hhdCcpICYmIHJlcXVlc3QubWV0aG9kKCkgPT09ICdQT1NUJyAmJiByZXF1ZXN0LnBvc3REYXRhSlNPTigpPy53aXphcmRfY29tbWFuZD8uYWN0aW9uID09PSAnU1RBUlQnKTtcclxuICBmb3IgKGxldCBzdGVwID0gMDsgc3RlcCA8IDEwOyBzdGVwKyspIHtcclxuICAgIGNvbnN0IGJ1dHRvbiA9IGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoYnV0dG9uKS50b0JlRW5hYmxlZCgpOyBjb25zdCBsYWJlbCA9IGF3YWl0IGJ1dHRvbi5pbm5lclRleHQoKTsgYXdhaXQgYnV0dG9uLmNsaWNrKCk7XHJcbiAgICBpZiAobGFiZWwgPT09ICfDnGJlcm5laG1lbicgfHwgbGFiZWwgPT09ICdBdWZ0cmFnIHN0YXJ0ZW4nKSBicmVhaztcclxuICB9XHJcbiAgY29uc3QgY29udGV4dCA9IChhd2FpdCBzdGFydFJlcXVlc3QpLnBvc3REYXRhSlNPTigpLndpemFyZF9jb21tYW5kLndpemFyZF9jb250ZXh0O1xyXG4gIGNvbnN0IHN1Ym1pdHRlZCA9IGNvbnRleHQuc3lzdGVtX2NsdXN0ZXJfYXNzaWdubWVudHMuZmxhdE1hcCgoY2x1c3RlcjogYW55KSA9PiBjbHVzdGVyLmZ1bmN0aW9uYWxfcm91dGVzID8/IFtdKTtcclxuICBjb25zdCBvZmYgPSBzdWJtaXR0ZWQuZmluZCgocm91dGU6IGFueSkgPT4gcm91dGUuc291cmNlID09PSAnTW90b3JzdGV1ZXJ1bmcnICYmIHJvdXRlLnRhcmdldCA9PT0gJ0dldHJpZWJlc3RldWVydW5nJyk7XHJcbiAgZXhwZWN0KG9mZi5zaWduYWxzKS50b0VxdWFsKFtdKTsgZXhwZWN0KG9mZi5leGNsdWRlZF9zaWduYWxzKS50b0VxdWFsKFsnTW90b3JEcmVobW9tZW50SXN0J10pO1xyXG4gIGxldCBwcm9wb3NhbDogYW55O1xyXG4gIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcclxuICAgIGNvbnN0IGNvbnZlcnNhdGlvbiA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NvbnZlcnNhdGlvbicpO1xyXG4gICAgaWYgKCFjb252ZXJzYXRpb24uZGF0YS5hY3RpdmVfcHJvcG9zYWwpIHJldHVybiBmYWxzZTtcclxuICAgIHByb3Bvc2FsID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke2NvbnZlcnNhdGlvbi5kYXRhLmFjdGl2ZV9wcm9wb3NhbH1gKSkuZGF0YTtcclxuICAgIHJldHVybiBwcm9wb3NhbC5wcm9wb3NhbF90eXBlID09PSAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJztcclxuICB9LCB7IHRpbWVvdXQ6IDE4MF8wMDAgfSkudG9CZSh0cnVlKTtcclxuICBhd2FpdCBwYWdlLnJlbG9hZCgpOyBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGNvbnN0IGZpbmRpbmdzID0gcHJvcG9zYWwudmFsaWRhdGlvbl9yZXN1bHQuZmluZGluZ3MuZmlsdGVyKChpdGVtOiBhbnkpID0+IGl0ZW0uY29kZSA9PT0gJ0NBUEFDSVRZX1VOVkVSSUZJRUQnKTtcclxuICBpZiAoZmluZGluZ3MubGVuZ3RoKSB7XHJcbiAgICBjb25zdCByZXZpZXcgPSBwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnUHLDvGZiZWZ1bmRlIGRlcyBWb3JzY2hsYWdzJyB9KTtcclxuICAgIGF3YWl0IGV4cGVjdChyZXZpZXcpLnRvQ29udGFpblRleHQoYCR7cHJvcG9zYWwudmFsaWRhdGlvbl9yZXN1bHQuZmluZGluZ3MubGVuZ3RofSBQcsO8ZmJlZnVuZGVgKTtcclxuICAgIGF3YWl0IGV4cGVjdChyZXZpZXcuZ2V0QnlSb2xlKCdsaW5rJywgeyBuYW1lOiAnVGVjaG5vbG9naWVwYXJhbWV0ZXIgYmVhcmJlaXRlbiB1bmQgYmVzdMOkdGlnZW4nIH0pLmZpcnN0KCkpLnRvSGF2ZUF0dHJpYnV0ZSgnaHJlZicsIG5ldyBSZWdFeHAoYHByb2plY3Q9JHtwcm9qZWN0fWApKTtcclxuICAgIGF3YWl0IHJldmlldy5sb2NhdG9yKCdzdW1tYXJ5JykuZmlyc3QoKS5jbGljaygpOyBhd2FpdCBleHBlY3QocmV2aWV3LmdldEJ5Um9sZSgnbmF2aWdhdGlvbicsIHsgbmFtZTogJ0JlZnVuZGUgZHVyY2hibMOkdHRlcm4nIH0pLmZpcnN0KCkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgfVxyXG4gIGNvbnN0IGFwcGx5ID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4gcmVzcG9uc2UudXJsKCkuaW5jbHVkZXMoYC9wcm9wb3NhbHMvJHtwcm9wb3NhbC5wcm9wb3NhbF9pZH0vYXBwcm92ZS1hcHBseWApICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRnJlaWdlYmVuLCDDvGJlcm5laG1lbiAmIGZvcnRmYWhyZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpOyBleHBlY3QoKGF3YWl0IGFwcGx5KS5vaygpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IG5vZGVzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICBjb25zdCBtZXNzYWdlcyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ21lc3NhZ2VzJyk7IGNvbnN0IHNpZ25hbHMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyk7XHJcbiAgY29uc3Qgc2lnbmFsID0gc2lnbmFscy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnTW90b3JEcmVobW9tZW50SXN0Jyk7IGV4cGVjdChzaWduYWwpLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXMuZmluZChpdGVtID0+IGl0ZW0uaWQgPT09IHNpZ25hbC5tZXNzYWdlX2lkKTtcclxuICBjb25zdCBnZWFyYm94ID0gbm9kZXMuZmluZChpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ0dldHJpZWJlc3RldWVydW5nJyk7XHJcbiAgY29uc3QgZW1vdG9yID0gbm9kZXMuZmluZChpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ0VsZWt0cm9tb3RvcnN0ZXVlcnVuZycpO1xyXG4gIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdC5zY29wZSkudG9CZSgnRlVOQ1RJT05fT1VUUFVUJyk7XHJcbiAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LmNvbnN1bWVyX3JlZnMpLm5vdC50b0NvbnRhaW4oZ2VhcmJveC5pZCk7XHJcbiAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LmNvbnN1bWVyX3JlZnMpLnRvQ29udGFpbihlbW90b3IuaWQpO1xyXG4gIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnZnVuY3Rpb25hbC10eHJ4LWV2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIG9mZiwgbWVzc2FnZSB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxufSk7XHJcbiJdLCJtYXBwaW5ncyI6IkFBQUEsU0FBU0EsSUFBSSxFQUFFQyxNQUFNLFFBQW1CLGlCQUFpQjtBQUN6RCxTQUFTQyxRQUFRLFFBQVEsa0JBQWtCO0FBQzNDLFNBQVNDLFVBQVUsUUFBUSxhQUFhO0FBQ3hDLFNBQVNDLFlBQVksUUFBUSxvQkFBb0I7QUFDakQsU0FBU0Msc0JBQXNCLEVBQUVDLFlBQVksRUFBRUMsV0FBVyxRQUFRLG9DQUFvQztBQUN0RyxTQUFTQyx1QkFBdUIsUUFBUSxxQ0FBcUM7QUFFN0UsTUFBTUMsS0FBSyxHQUFHSCxZQUFZO0FBQzFCLE1BQU1JLElBQUksR0FBR0gsV0FBVztBQUV4QixNQUFNSSxZQUFZLEdBQUcsSUFBSUMsR0FBRyxDQUF3QixDQUFDO0FBQ3JELE1BQU1DLG9CQUFvQixHQUFHLElBQUlDLE9BQU8sQ0FBaUIsQ0FBQztBQUMxRCxNQUFNQyxrQkFBa0IsR0FBRyxJQUFJSCxHQUFHLENBQW9CLENBQUM7QUFFdkRaLElBQUksQ0FBQ2dCLFVBQVUsQ0FBQyxPQUFPO0VBQUVDO0FBQUssQ0FBQyxFQUFFQyxJQUFJLEtBQUs7RUFD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