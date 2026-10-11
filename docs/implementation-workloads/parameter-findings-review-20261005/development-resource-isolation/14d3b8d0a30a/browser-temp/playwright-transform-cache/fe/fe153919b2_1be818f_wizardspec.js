// 977c81f5c9ebf2c1c4de3ecdfb61548b280ee276
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
async function verifyArtifacts(page, project, minimumCanonicalSignals, internalController) {
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
    assessment
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
  const continuity = await completeThroughWizard(page, project, true, ['System', 'Motorsteuerung', 'Anzeige', 'MotorTemperature', 'MotorValve']);
  const artifacts = await verifyArtifacts(page, project, 5);
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
  test(`Raspberry Pi ${technology} project retains model and requests missing capacity evidence @nonautomotive`, async ({
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
    expect(findings.map(item => item.code)).toContain('TECHNOLOGY_PARAMETER_MISSING');
    expect(workflow.statuses.parameters).toBe('IN_PROGRESS');
    expect(workflow.artifact_checks.parameters.complete).toBe(false);
    const required = workflow.artifact_checks.parameters.required;
    expect(required[technology === 'I2C' ? 'i2c_device_source' : 'mr_device_source']).toBe(false);
    const evidenceReview = dialog.getByRole('region', {
      name: 'Blockierende Preflight-Befunde'
    });
    await expect(evidenceReview).toContainText(technology === 'I2C' ? 'i2c_device_source' : 'mr_device_source');
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
    var _request$postDataJSON2;
    return request.url().endsWith('/api/agent/chat') && request.method() === 'POST' && ((_request$postDataJSON2 = request.postDataJSON()) === null || _request$postDataJSON2 === void 0 || (_request$postDataJSON2 = _request$postDataJSON2.wizard_command) === null || _request$postDataJSON2 === void 0 ? void 0 : _request$postDataJSON2.action) === 'START';
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
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmVhZEZpbGUiLCJyYW5kb21VVUlEIiwiZXhlY0ZpbGVTeW5jIiwiV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyIsIldJWkFSRF9TVEVQUyIsIldJWkFSRF9ET05FIiwicmV2aWV3VmlydHVhbFRyYW5zcG9ydHMiLCJzdGVwcyIsImRvbmUiLCJ3cml0ZVRpbWluZ3MiLCJNYXAiLCJ3b3JrZmxvd1BhZ2VGYWlsdXJlcyIsIldlYWtNYXAiLCJwcm9ncmVzc01pbGVzdG9uZXMiLCJiZWZvcmVFYWNoIiwicGFnZSIsImluZm8iLCJyb3dzIiwic2V0IiwidGVzdElkIiwicmVxdWVzdHMiLCJvbiIsInJlcXVlc3QiLCJpbmNsdWRlcyIsIm1ldGhvZCIsInJvdyIsInVybCIsInN0YXJ0ZWQiLCJEYXRlIiwibm93IiwicHVzaCIsInJlc3BvbnNlIiwiZ2V0Iiwic3RhdHVzIiwiVVJMIiwicGF0aG5hbWUiLCJkdXJhdGlvbl9tcyIsIl9yZXF1ZXN0JGZhaWx1cmUiLCJmYWlsdXJlIiwiZXJyb3JUZXh0IiwiYWZ0ZXJFYWNoIiwiYXR0YWNoIiwiYm9keSIsIkpTT04iLCJzdHJpbmdpZnkiLCJjb250ZW50VHlwZSIsImRlbGV0ZSIsInRvRXF1YWwiLCJhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5IiwiZ2V0QnlUZXh0IiwiZXhhY3QiLCJpc1Zpc2libGUiLCJ0b0JlIiwicmVhZFByb2plY3QiLCJwcm9qZWN0IiwicGF0aCIsInJlc3VsdCIsImhlYWRlcnMiLCJ0aW1lb3V0Iiwib2siLCJFcnJvciIsInRleHQiLCJzbGljZSIsImpzb24iLCJkaXNwb3NlIiwicmVhZFdhcm5pbmdSZXZpZXdTdGF0ZSIsIl92ZXJpZmllZCRjb250ZXh0JGFnZTIiLCJfdmVyaWZpZWQkY29udGV4dCRhZ2UzIiwiYXV0aG9yaXR5IiwicGFyYW1ldGVycyIsInZlcmlmaWVkIiwicHJvamVjdF9pZCIsImZpZWxkIiwiX3ZlcmlmaWVkJGNvbnRleHQkYWdlIiwiX2F1dGhvcml0eSRjb250ZXh0JGFnIiwiY29udGV4dCIsImFnZW50X2V4ZWN1dGlvbiIsInN0YXR1c2VzIiwicnVuX2lkIiwicmVxdWVzdF9yZXZpc2lvbiIsInByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsIiwib3BlbldpemFyZCIsImdvdG8iLCJ3YWl0VW50aWwiLCJkaWFsb2ciLCJnZXRCeVJvbGUiLCJuYW1lIiwidG9CZVZpc2libGUiLCJzdGVwIiwibG9jYXRvciIsInN0ZXBXaWR0aCIsImV2YWx1YXRlIiwiZWxlbWVudCIsImdldEJvdW5kaW5nQ2xpZW50UmVjdCIsIndpZHRoIiwiY2FyZHMiLCJhbGwiLCJ0b0hhdmVMZW5ndGgiLCJjYXJkIiwidG9CZUdyZWF0ZXJUaGFuIiwiYWxsT2JqZWN0cyIsInJlc291cmNlIiwiaXRlbXMiLCJvZmZzZXQiLCJsZW5ndGgiLCJyZXN0YXJ0QXBwbGljYXRpb24iLCJjcmFzaCIsImNvbnRhaW5lciIsInByb2Nlc3MiLCJlbnYiLCJOSVNfRTJFX0FQUF9DT05UQUlORVIiLCJ0b01hdGNoIiwiZG9ja2VyIiwiTklTX1RFU1RfRE9DS0VSIiwibGFiZWwiLCJlbmNvZGluZyIsInRyaW0iLCJwb2xsIiwidmVyaWZ5U2lnbmFsQ29udHJhY3RzIiwiZXhwZWN0ZWQiLCJoYXJkd2FyZSIsImZ1bmN0aW9ucyIsIm1lc3NhZ2VzIiwic2lnbmFscyIsIlByb21pc2UiLCJtYXAiLCJub2RlcyIsIml0ZW0iLCJpZCIsImZ1bmN0aW9uc0J5SWQiLCJtZXNzYWdlc0J5SWQiLCJjb250cmFjdHMiLCJzaWduYWwiLCJfcmVmIiwiX3NpZ25hbCRkYXRhJGVudW1fdmFsIiwiX3NpZ25hbCRkYXRhIiwiX3NpZ25hbCRzZW1hbnRpYyRzZW1hIiwiX3NpZ25hbCRzZW1hbnRpYyIsIl9zaWduYWwkY29uZmlndXJhdGlvbiIsIl9zaWduYWwkY29uZmlndXJhdGlvbjIiLCJtZXNzYWdlIiwibWVzc2FnZV9pZCIsInRvQmVUcnV0aHkiLCJyZWZlcmVuY2UiLCJjb25maWd1cmF0aW9uIiwiY29tbXVuaWNhdGlvbl9jb250cmFjdCIsInByb2R1Y2VyX3JlZiIsImZuIiwib3duZXIiLCJoYXJkd2FyZV9ub2RlX2lkIiwicHJvZHVjZXIiLCJkZXZpY2VfdHlwZSIsImtleSIsImpvaW4iLCJ0b0JlVW5kZWZpbmVkIiwiT2JqZWN0IiwiZnJvbUVudHJpZXMiLCJfc2lnbmFsJGZpZWxkIiwiZW51bV92YWx1ZXMiLCJkYXRhIiwic2VtYW50aWNfdHlwZSIsInNlbWFudGljIiwiZ2VuZXJhdGlvbl9yb2xlIiwidmVyaWZ5QXJ0aWZhY3RzIiwibWluaW11bUNhbm9uaWNhbFNpZ25hbHMiLCJpbnRlcm5hbENvbnRyb2xsZXIiLCJfYXNzZXNzbWVudCRzY29wZV9jb3YiLCJ3b3JrZmxvdyIsImpvYkxpc3QiLCJzbmFwc2hvdHMiLCJrZXlzIiwic29ydCIsImhhcyIsImpvYnMiLCJzbmFwc2hvdCIsInNpbXVsYXRpb25zIiwiZmluZCIsImpvYl9pZCIsImZ1bGwiLCJhc3Nlc3NtZW50Iiwic2NvcGVfY292ZXJhZ2UiLCJzY29wZV9tb2RlIiwiY29tcGxldGUiLCJjb25mb3JtYW5jZSIsImZhaWxlZF9yb3V0ZV9jb3VudCIsInRvQmVHcmVhdGVyVGhhbk9yRXF1YWwiLCJleGNsdWRlZCIsInRyYW5zcG9ydF9leGNsdXNpb25zIiwicm91dGluZyIsImVuYWJsZWQiLCJjb250cmFjdCIsImNvbnN1bWVyX3JlZnMiLCJyZWFzb25fY29kZSIsInJvbGUiLCJjb250cm9sbGVyIiwidG9NYXRjaE9iamVjdCIsInNjb3BlIiwiZXhjbHVkZWRTaWduYWxzIiwiU2V0IiwiZmxhdE1hcCIsInNpZ25hbF9pZHMiLCJvYnNlcnZlZF9zaWduYWxfY291bnQiLCJzaXplIiwidHJhY2UiLCJjb3VudCIsImV2ZW50cyIsInNvbWUiLCJqb2IiLCJjb21wbGV0ZVRocm91Z2hXaXphcmQiLCJyZXN0YXJ0IiwiZXhwZWN0ZWRIYXJkd2FyZSIsImNyYXNoU2ltdWxhdGlvbiIsImV4cGVjdGVkU2lnbmFscyIsImFmdGVyRmlyc3RNb2RlbEFwcGxpZWQiLCJzdG9wT25FdmlkZW5jZUJsb2NrIiwicmV2aWV3Q291bnQiLCJydW5JZCIsInJldmlld2VkIiwicmVzdGFydGVkSm9iSWQiLCJ3YXRjaGRvZyIsInBlcmZvcm1hbmNlIiwiY2hlY2twb2ludCIsIl93b3JrZmxvdyRjb250ZXh0JGFnZSIsIl93b3JrZmxvdyRjb250ZXh0JGFnZTIiLCJfZXhlY3V0aW9uJGJsb2NraW5nX2YiLCJfZXhlY3V0aW9uJG1lc3NhZ2UiLCJwcm9wb3NhbElkIiwicmVhZHlWZXJzaW9uIiwicmVhZHlTaW5jZSIsImlzQ2hlY2twb2ludCIsInJlbWFpbmluZyIsInByb2dyZXNzIiwib2JzZXJ2ZSIsImFkdmFuY2VkIiwiYXQiLCJ0b0lTT1N0cmluZyIsImZyb250aWVyIiwiY29tcGxldGVkVGhyb3VnaCIsImV4ZWN1dGlvbiIsInZhbGlkYXRpb24iLCJydW5uaW5nIiwiZXZlcnkiLCJzdGF0ZSIsImNvbnZlcnNhdGlvbiIsImFjdGl2ZV9wcm9wb3NhbCIsIkJvb2xlYW4iLCJyZWNvdmVyYWJsZSIsInVwZGF0ZWRfYXQiLCJidXR0b24iLCJldmFsdWF0ZUFsbCIsImJ1dHRvbnMiLCJkaXNhYmxlZCIsImdldENsaWVudFJlY3RzIiwiZ2V0Q29tcHV0ZWRTdHlsZSIsInZpc2liaWxpdHkiLCJhdHRlbXB0Iiwid2FpdEZvclRpbWVvdXQiLCJNYXRoIiwibWluIiwiYmxvY2tpbmdfZmluZGluZ3MiLCJiZWZvcmVSZXZpZXciLCJwcmVmbGlnaHQiLCJ3YXJuaW5ncyIsImZpcnN0Iiwic3RhcnRlZFdhbGwiLCJhcHByb3ZhbFJlc3BvbnNlIiwid2FpdEZvclJlc3BvbnNlIiwiY2xpY2siLCJhcHByb3ZlZCIsInJlY2VpcHQiLCJhZnRlclJldmlldyIsInByb29mIiwiYmVmb3JlIiwiYWZ0ZXIiLCJzbmFwc2hvdElkIiwicmVxdWVzdFByb2plY3QiLCJzdWJtaXR0ZWQiLCJwb3N0RGF0YUpTT04iLCJmaW5pc2hlZFdhbGwiLCJjb21taXR0ZWRBdCIsImNvbW1pdHRlZCIsImNvbW1pdFdhcm5pbmdSZXZpZXciLCJtYW51YWxXYXJuaW5nQXBwcm92YWwiLCJhcHByb3ZhbElkZW50aXR5IiwiYXBwcm92YWwiLCJfYXdhaXQkcmVhZFByb2plY3QkY28iLCJub3QiLCJfY29udmVyc2F0aW9uJGRhdGEiLCJfcHJvcG9zYWwkZGF0YSIsInByb3Bvc2FsIiwidmFsaWRhdGlvbl9yZXN1bHQiLCJ2aXNpYmxlIiwiaW5uZXJUZXh0IiwiZXJyb3IiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQiLCJsYXRlc3QiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQyIiwiX2xhdGVzdCRjb250ZXh0JGFnZW50MyIsIl9sYXRlc3Qkc3RhdHVzZXMiLCJjYW5kaWRhdGUiLCJwcm9wb3NhbF90eXBlIiwiY2hhbmdlcyIsImZpbHRlciIsImNoYW5nZSIsIm9iamVjdF90eXBlIiwiYXJyYXlDb250YWluaW5nIiwiYXBwbHlSZXNwb25zZSIsInRvQmVFbmFibGVkIiwiYXBwbGllZCIsImFkZCIsIl9hbWVuZGVkJGNvbnRleHQkYWdlbiIsImFtZW5kZWQiLCJfY3VycmVudCRjb250ZXh0JGFnZW4iLCJjdXJyZW50Iiwicm91dGUiLCJmdWxmaWxsIiwidG9Db250YWluVGV4dCIsImdldEJ5VGl0bGUiLCJmaWxsIiwiZ2V0QnlMYWJlbCIsInRvQmVEaXNhYmxlZCIsInVucm91dGUiLCJ0b0hhdmVDb3VudCIsImNhdGFsb2ciLCJ0ZWNobm9sb2d5X2NvdW50IiwidGVzdEluZm8iLCJlcnJvcnMiLCJ2YWx1ZSIsInN0YXJ0UmVxdWVzdCIsIndhaXRGb3JSZXF1ZXN0IiwiX3JlcXVlc3QkcG9zdERhdGFKU09OIiwiZW5kc1dpdGgiLCJ3aXphcmRfY29tbWFuZCIsImFjdGlvbiIsInN1Ym1pdCIsInJlcXVlc3RlZCIsIndpemFyZF9jb250ZXh0IiwidGVjaG5vbG9naWVzIiwiY29udGludWl0eSIsImFydGlmYWN0cyIsImZpbmlzaGVkIiwidGVjaG5vbG9neSIsImNoZWNrIiwic2VsZWN0T3B0aW9uIiwidG9IYXZlVmFsdWUiLCJ1bmRlZmluZWQiLCJyZWplY3RzIiwidG9UaHJvdyIsImZpbmRpbmdzIiwiY29kZSIsInRvQ29udGFpbiIsImFydGlmYWN0X2NoZWNrcyIsInJlcXVpcmVkIiwiZXZpZGVuY2VSZXZpZXciLCJ0b0hhdmVBdHRyaWJ1dGUiLCJSZWdFeHAiLCJzaW11bGF0aW9uIiwicmF0ZV9yZXZpZXdfcHJvcG9zYWxzIiwiaTJjIiwicGFyYW1ldGVyX3Byb3ZlbmFuY2UiLCJiaXRyYXRlIiwic291cmNlIiwiaW50ZXJmYWNlcyIsImRvbWFpbiIsInVuaXQiLCJvcmlnaW5hbCIsImltcG9ydCIsIm1ldGEiLCJtZXRhZGF0YSIsInBhcnNlIiwiYmFzZWxpbmUiLCJwcm9tcHQiLCJyZXBsYWNlIiwicG9zdCIsIm9wZXJhdGlvbl9pZCIsInRhcmdldCIsImV4Y2x1ZGVkU2lnbmFsSWRzIiwiZml4dHVyZSIsInJlcXVlc3Rfc2hhMjU2IiwiZ3JhcGgiLCJjbHVzdGVyX2lkIiwibmV0d29ya19pZCIsIm5ldHdvcmtfbGFiZWwiLCJidXNfbmFtZSIsImNvbnRyb2xsZXJzIiwiZWN1Iiwic2Vuc29ycyIsImFjdHVhdG9ycyIsImhtaV9yb3V0ZXMiLCJwcm9qZWN0X25hbWUiLCJzY29wZV9pZHMiLCJtb2RlIiwicHJvY2Vzc19pZHMiLCJ0YXNrIiwib3JpZ2luYWxOZXR3b3JrcyIsImFtZW5kIiwibmV0d29ya3MiLCJleHBhbmQiLCJpZGVudGl0eSIsInN5c3RlbV9vd25lcl9pZCIsInNlbnNvck5ldHdvcmsiLCJ0b3BvbG9neSIsImxvY2FsRWRnZSIsImVkZ2VzIiwiZWRnZSIsInBoeXNpY2FsTmV0d29ya0lkIiwiYnVzIiwidmFsdWVzIiwicm91dGluZ01ldGFkYXRhIiwidG9Db250YWluRXF1YWwiLCJvYmplY3RDb250YWluaW5nIiwiYXBwcm92YWxTdGF0ZSIsInByb3RvY29sIiwic2lkZSIsImhhcmR3YXJlSWQiLCJub2RlIiwiZW5naW5lZXJpbmdJZCIsInBvcnRzIiwidHhyeCIsImhhc1RleHQiLCJzZWxlY3RlZCIsInRvQmVDaGVja2VkIiwidW5jaGVjayIsIl9yZXF1ZXN0JHBvc3REYXRhSlNPTjIiLCJzeXN0ZW1fY2x1c3Rlcl9hc3NpZ25tZW50cyIsImNsdXN0ZXIiLCJfY2x1c3RlciRmdW5jdGlvbmFsX3IiLCJmdW5jdGlvbmFsX3JvdXRlcyIsIm9mZiIsImV4Y2x1ZGVkX3NpZ25hbHMiLCJyZWxvYWQiLCJyZXZpZXciLCJhcHBseSIsInByb3Bvc2FsX2lkIiwiZ2VhcmJveCIsImVtb3RvciJdLCJzb3VyY2VzIjpbIndpemFyZC5zcGVjLnRzIl0sInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHRlc3QsIGV4cGVjdCwgdHlwZSBQYWdlIH0gZnJvbSAncGxheXdyaWdodC90ZXN0JztcclxuaW1wb3J0IHsgcmVhZEZpbGUgfSBmcm9tICdub2RlOmZzL3Byb21pc2VzJztcclxuaW1wb3J0IHsgcmFuZG9tVVVJRCB9IGZyb20gJ25vZGU6Y3J5cHRvJztcclxuaW1wb3J0IHsgZXhlY0ZpbGVTeW5jIH0gZnJvbSAnbm9kZTpjaGlsZF9wcm9jZXNzJztcclxuaW1wb3J0IHsgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZywgV0laQVJEX1NURVBTLCBXSVpBUkRfRE9ORSB9IGZyb20gJy4vc3VwcG9ydC93aXphcmQtcHJvZ3Jlc3Mtd2F0Y2hkb2cnO1xyXG5pbXBvcnQgeyByZXZpZXdWaXJ0dWFsVHJhbnNwb3J0cyB9IGZyb20gJy4vc3VwcG9ydC9uYXRpdmUtdHJhbnNwb3J0LWZpeHR1cmVzJztcclxuXHJcbmNvbnN0IHN0ZXBzID0gV0laQVJEX1NURVBTO1xyXG5jb25zdCBkb25lID0gV0laQVJEX0RPTkU7XHJcbnR5cGUgV3JpdGVUaW1pbmcgPSB7IHVybDogc3RyaW5nOyBzdGFydGVkOiBudW1iZXI7IGR1cmF0aW9uX21zPzogbnVtYmVyOyBzdGF0dXM/OiBudW1iZXI7IGZhaWx1cmU/OiBzdHJpbmcgfTtcclxuY29uc3Qgd3JpdGVUaW1pbmdzID0gbmV3IE1hcDxzdHJpbmcsIFdyaXRlVGltaW5nW10+KCk7XHJcbmNvbnN0IHdvcmtmbG93UGFnZUZhaWx1cmVzID0gbmV3IFdlYWtNYXA8UGFnZSwgc3RyaW5nW10+KCk7XHJcbmNvbnN0IHByb2dyZXNzTWlsZXN0b25lcyA9IG5ldyBNYXA8c3RyaW5nLCB1bmtub3duW10+KCk7XHJcblxyXG50ZXN0LmJlZm9yZUVhY2goYXN5bmMgKHsgcGFnZSB9LCBpbmZvKSA9PiB7XHJcbiAgY29uc3Qgcm93czogV3JpdGVUaW1pbmdbXSA9IFtdO1xyXG4gIHdyaXRlVGltaW5ncy5zZXQoaW5mby50ZXN0SWQsIHJvd3MpO1xyXG4gIHdvcmtmbG93UGFnZUZhaWx1cmVzLnNldChwYWdlLCBbXSk7XHJcbiAgcHJvZ3Jlc3NNaWxlc3RvbmVzLnNldChpbmZvLnRlc3RJZCwgW10pO1xyXG4gIGNvbnN0IHJlcXVlc3RzID0gbmV3IE1hcDxvYmplY3QsIFdyaXRlVGltaW5nPigpO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3QnLCByZXF1ZXN0ID0+IHtcclxuICAgIGlmICghWydQT1NUJywgJ1BVVCcsICdQQVRDSCcsICdERUxFVEUnXS5pbmNsdWRlcyhyZXF1ZXN0Lm1ldGhvZCgpKSkgcmV0dXJuO1xyXG4gICAgY29uc3Qgcm93ID0geyB1cmw6IHJlcXVlc3QudXJsKCksIHN0YXJ0ZWQ6IERhdGUubm93KCkgfTtcclxuICAgIHJvd3MucHVzaChyb3cpOyByZXF1ZXN0cy5zZXQocmVxdWVzdCwgcm93KTtcclxuICB9KTtcclxuICBwYWdlLm9uKCdyZXNwb25zZScsIHJlc3BvbnNlID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXNwb25zZS5yZXF1ZXN0KCkpO1xyXG4gICAgaWYgKHJvdykgcm93LnN0YXR1cyA9IHJlc3BvbnNlLnN0YXR1cygpO1xyXG4gICAgaWYgKHJlc3BvbnNlLnN0YXR1cygpID09PSA0MTMgJiYgL15cXC9hcGlcXC9lbmdpbmVlcmluZ1xcL3dvcmtmbG93KD86XFwvfCQpLy50ZXN0KG5ldyBVUkwocmVzcG9uc2UudXJsKCkpLnBhdGhuYW1lKSkge1xyXG4gICAgICB3b3JrZmxvd1BhZ2VGYWlsdXJlcy5nZXQocGFnZSkhLnB1c2goYEhUVFAgNDEzOiAke3Jlc3BvbnNlLnVybCgpfWApO1xyXG4gICAgfVxyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3RmaW5pc2hlZCcsIHJlcXVlc3QgPT4ge1xyXG4gICAgY29uc3Qgcm93ID0gcmVxdWVzdHMuZ2V0KHJlcXVlc3QpO1xyXG4gICAgaWYgKHJvdykgcm93LmR1cmF0aW9uX21zID0gRGF0ZS5ub3coKSAtIHJvdy5zdGFydGVkO1xyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3RmYWlsZWQnLCByZXF1ZXN0ID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXF1ZXN0KTtcclxuICAgIGlmIChyb3cpIHsgcm93LmR1cmF0aW9uX21zID0gRGF0ZS5ub3coKSAtIHJvdy5zdGFydGVkOyByb3cuZmFpbHVyZSA9IHJlcXVlc3QuZmFpbHVyZSgpPy5lcnJvclRleHQ7IH1cclxuICB9KTtcclxufSk7XHJcblxyXG50ZXN0LmFmdGVyRWFjaChhc3luYyAoeyBwYWdlIH0sIGluZm8pID0+IHtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd3JpdGUtcmVxdWVzdC10aW1pbmdzJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh3cml0ZVRpbWluZ3MuZ2V0KGluZm8udGVzdElkKSB8fCBbXSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgYXdhaXQgaW5mby5hdHRhY2goJ3dvcmtmbG93LXByb2dyZXNzLWJvdW5kYXJpZXMnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHByb2dyZXNzTWlsZXN0b25lcy5nZXQoaW5mby50ZXN0SWQpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd29ya2Zsb3ctcGFnZS1mYWlsdXJlcycsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICB3cml0ZVRpbWluZ3MuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBwcm9ncmVzc01pbGVzdG9uZXMuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBleHBlY3Qod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpLCAnVGhlIHVuZGVybHlpbmcgZW5naW5lZXJpbmcgcGFnZSBtdXN0IHJlbWFpbiByZWFkYWJsZSB0aHJvdWdob3V0IHJlbG9hZCBhbmQgcmVjb3ZlcnkuJykudG9FcXVhbChbXSk7XHJcbn0pO1xyXG5cclxuYXN5bmMgZnVuY3Rpb24gYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeShwYWdlOiBQYWdlKSB7XHJcbiAgZXhwZWN0KHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSwgJ0Egd29ya2luZyB3aXphcmQgb3ZlcmxheSBtdXN0IG5vdCBjb25jZWFsIGEgd29ya2Zsb3cgSFRUUCA0MTMuJykudG9FcXVhbChbXSk7XHJcbiAgZXhwZWN0KGF3YWl0IHBhZ2UuZ2V0QnlUZXh0KCdFbmdpbmVlcmluZy1BUEkgbmljaHQgZXJyZWljaGJhcicsIHsgZXhhY3Q6IHRydWUgfSkuaXNWaXNpYmxlKCksXHJcbiAgICAnVGhlIHVuZGVybHlpbmcgZW5naW5lZXJpbmcgcGFnZSBtdXN0IG5vdCBzaG93IGl0cyBBUEkgZXJyb3Igdmlldy4nKS50b0JlKGZhbHNlKTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVhZFByb2plY3QocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBwYXRoOiBzdHJpbmcpIHtcclxuICBjb25zdCByZXN1bHQgPSBhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KHBhdGgsIHsgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiA2MF8wMDAgfSk7XHJcbiAgdHJ5IHtcclxuICAgIGlmICghcmVzdWx0Lm9rKCkpIHRocm93IG5ldyBFcnJvcihgJHtwYXRofTogSFRUUCAke3Jlc3VsdC5zdGF0dXMoKX0gJHsoYXdhaXQgcmVzdWx0LnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgICByZXR1cm4gYXdhaXQgcmVzdWx0Lmpzb24oKTtcclxuICB9IGZpbmFsbHkge1xyXG4gICAgLy8gUGxheXdyaWdodCBvdGhlcndpc2UgcmV0YWlucyBldmVyeSBwb2xsZWQgcmVzcG9uc2UgdW50aWwgY29udGV4dCB0ZWFyZG93bi5cclxuICAgIC8vIEtlZXAgdGhlIHBhcnNlZCBldmlkZW5jZSwgcmVsZWFzZSBpdHMgZHVwbGljYXRlIHRyYW5zcG9ydCBib2R5IGltbWVkaWF0ZWx5LlxyXG4gICAgYXdhaXQgcmVzdWx0LmRpc3Bvc2UoKTtcclxuICB9XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHJlYWRXYXJuaW5nUmV2aWV3U3RhdGUocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nKSB7XHJcbiAgY29uc3QgYXV0aG9yaXR5ID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgY29uc3QgcGFyYW1ldGVycyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnKTtcclxuICBjb25zdCB2ZXJpZmllZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gIGV4cGVjdChwYXJhbWV0ZXJzLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgZXhwZWN0KGF1dGhvcml0eS5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xyXG4gIGV4cGVjdCh2ZXJpZmllZC5wcm9qZWN0X2lkKS50b0JlKHByb2plY3QpO1xyXG4gIGZvciAoY29uc3QgZmllbGQgb2YgWydydW5faWQnLCAncmVxdWVzdF9yZXZpc2lvbiddKVxyXG4gICAgZXhwZWN0KHZlcmlmaWVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5bZmllbGRdKS50b0JlKGF1dGhvcml0eS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8uW2ZpZWxkXSk7XHJcbiAgcmV0dXJuIHsgcHJvamVjdF9pZDogdmVyaWZpZWQucHJvamVjdF9pZCwgc3RhdHVzZXM6IHZlcmlmaWVkLnN0YXR1c2VzLFxyXG4gICAgY29udGV4dDogeyBhZ2VudF9leGVjdXRpb246IHsgcnVuX2lkOiB2ZXJpZmllZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkLFxyXG4gICAgICByZXF1ZXN0X3JldmlzaW9uOiB2ZXJpZmllZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucmVxdWVzdF9yZXZpc2lvbiB9IH0sXHJcbiAgICBwYXJhbWV0ZXJzOiB7IHByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsOiBwYXJhbWV0ZXJzLnBhcmFtZXRlcnMucHJlZmxpZ2h0X3dhcm5pbmdfYXBwcm92YWwgfSB9O1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiBvcGVuV2l6YXJkKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZykge1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9lbmdpbmVlcmluZz9hc3Npc3RhbnQ9cHJvamVjdCZwcm9qZWN0PSR7cHJvamVjdH1gLCB7IHdhaXRVbnRpbDogJ2xvYWQnIH0pO1xyXG4gIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZykudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2UpO1xyXG4gIHJldHVybiBkaWFsb2c7XHJcbn1cclxuXHJcbnRlc3QoJ3Byb2plY3QgbmFtaW5nIGZvcm0gY2FyZHMgdXNlIHRoZSBmdWxsIHdpemFyZCB3aWR0aCBAbGF5b3V0JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCAnbmlzLWUyZS1wcm9qZWN0LW5hbWUtbGF5b3V0LScgKyByYW5kb21VVUlEKCkpO1xyXG4gIGNvbnN0IHN0ZXAgPSBkaWFsb2cubG9jYXRvcignZmllbGRzZXQuYWdlbnQtcHJvamVjdC1uYW1lLXN0ZXAnKTtcclxuICBhd2FpdCBleHBlY3Qoc3RlcCkudG9CZVZpc2libGUoKTtcclxuICBjb25zdCBzdGVwV2lkdGggPSBhd2FpdCBzdGVwLmV2YWx1YXRlKGVsZW1lbnQgPT4gZWxlbWVudC5nZXRCb3VuZGluZ0NsaWVudFJlY3QoKS53aWR0aCk7XHJcbiAgY29uc3QgY2FyZHMgPSBhd2FpdCBzdGVwLmxvY2F0b3IoJzpzY29wZSA+IGxhYmVsJykuYWxsKCk7XHJcbiAgZXhwZWN0KGNhcmRzKS50b0hhdmVMZW5ndGgoNCk7XHJcbiAgZm9yIChjb25zdCBjYXJkIG9mIGNhcmRzKSB7XHJcbiAgICBjb25zdCB3aWR0aCA9IGF3YWl0IGNhcmQuZXZhbHVhdGUoZWxlbWVudCA9PiBlbGVtZW50LmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpLndpZHRoKTtcclxuICAgIGV4cGVjdCh3aWR0aCkudG9CZUdyZWF0ZXJUaGFuKHN0ZXBXaWR0aCAqIDAuODUpO1xyXG4gIH1cclxufSk7XHJcblxyXG5hc3luYyBmdW5jdGlvbiBhbGxPYmplY3RzKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcmVzb3VyY2U6IHN0cmluZykge1xyXG4gIGNvbnN0IGl0ZW1zOiBhbnlbXSA9IFtdO1xyXG4gIGZvciAobGV0IG9mZnNldCA9IDA7IDsgb2Zmc2V0ICs9IDUwMCkge1xyXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy8ke3Jlc291cmNlfT9saW1pdD01MDAmb2Zmc2V0PSR7b2Zmc2V0fWApO1xyXG4gICAgaXRlbXMucHVzaCguLi5yZXNwb25zZS5pdGVtcyk7XHJcbiAgICBpZiAocmVzcG9uc2UuaXRlbXMubGVuZ3RoIDwgNTAwKSByZXR1cm4gaXRlbXM7XHJcbiAgfVxyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiByZXN0YXJ0QXBwbGljYXRpb24ocGFnZTogUGFnZSwgY3Jhc2ggPSBmYWxzZSkge1xyXG4gIGNvbnN0IGNvbnRhaW5lciA9IHByb2Nlc3MuZW52Lk5JU19FMkVfQVBQX0NPTlRBSU5FUiE7XHJcbiAgZXhwZWN0KGNvbnRhaW5lcikudG9NYXRjaCgvXm5pcy1lMmUtYXBwLVthLWYwLTldKyQvKTtcclxuICBjb25zdCBkb2NrZXIgPSBwcm9jZXNzLmVudi5OSVNfVEVTVF9ET0NLRVIgfHwgJ2RvY2tlcic7XHJcbiAgY29uc3QgbGFiZWwgPSBleGVjRmlsZVN5bmMoZG9ja2VyLCBbJ2luc3BlY3QnLCBjb250YWluZXIsICctLWZvcm1hdCcsICd7e2luZGV4IC5Db25maWcuTGFiZWxzIFwibmV0d29ya2lzLnRlc3RcIn19J10sIHsgZW5jb2Rpbmc6ICd1dGY4JyB9KS50cmltKCk7XHJcbiAgZXhwZWN0KGxhYmVsKS50b0JlKCdkaXNwb3NhYmxlJyk7XHJcbiAgZXhlY0ZpbGVTeW5jKGRvY2tlciwgWydyZXN0YXJ0JywgLi4uKGNyYXNoID8gWyctdCcsICcwJ10gOiBbXSksIGNvbnRhaW5lcl0sIHsgdGltZW91dDogNjBfMDAwIH0pO1xyXG4gIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcclxuICAgIHRyeSB7IHJldHVybiAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9yZWFkeScsIHsgdGltZW91dDogMjAwMCB9KSkub2soKTsgfSBjYXRjaCB7IHJldHVybiBmYWxzZTsgfVxyXG4gIH0sIHsgdGltZW91dDogMTIwXzAwMCB9KS50b0JlKHRydWUpO1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBleHBlY3RlZDogUmVjb3JkPHN0cmluZywgdW5rbm93bj4pIHtcclxuICBjb25zdCBbaGFyZHdhcmUsIGZ1bmN0aW9ucywgbWVzc2FnZXMsIHNpZ25hbHNdID0gYXdhaXQgUHJvbWlzZS5hbGwoXHJcbiAgICBbJ2hhcmR3YXJlLW5vZGVzJywgJ2Z1bmN0aW9ucycsICdtZXNzYWdlcycsICdzaWduYWxzJ10ubWFwKHJlc291cmNlID0+IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgcmVzb3VyY2UpKSk7XHJcbiAgY29uc3Qgbm9kZXMgPSBuZXcgTWFwKGhhcmR3YXJlLm1hcChpdGVtID0+IFtpdGVtLmlkLCBpdGVtXSkpO1xyXG4gIGNvbnN0IGZ1bmN0aW9uc0J5SWQgPSBuZXcgTWFwKGZ1bmN0aW9ucy5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBtZXNzYWdlc0J5SWQgPSBuZXcgTWFwKG1lc3NhZ2VzLm1hcChpdGVtID0+IFtpdGVtLmlkLCBpdGVtXSkpO1xyXG4gIGNvbnN0IGNvbnRyYWN0czogUmVjb3JkPHN0cmluZywgdW5rbm93bj4gPSB7fTtcclxuICBmb3IgKGNvbnN0IHNpZ25hbCBvZiBzaWduYWxzKSB7XHJcbiAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXNCeUlkLmdldChzaWduYWwubWVzc2FnZV9pZCk7XHJcbiAgICBleHBlY3QobWVzc2FnZSkudG9CZVRydXRoeSgpO1xyXG4gICAgY29uc3QgcmVmZXJlbmNlID0gbWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QucHJvZHVjZXJfcmVmO1xyXG4gICAgY29uc3QgZm4gPSBmdW5jdGlvbnNCeUlkLmdldChyZWZlcmVuY2UpO1xyXG4gICAgY29uc3Qgb3duZXIgPSBub2Rlcy5nZXQocmVmZXJlbmNlKSB8fCAoZm4gJiYgbm9kZXMuZ2V0KGZuLmhhcmR3YXJlX25vZGVfaWQpKTtcclxuICAgIGNvbnN0IHByb2R1Y2VyID0gb3duZXI/LmRldmljZV90eXBlID09PSAnR2F0ZXdheScgPyAnJGdhdGV3YXknIDogKG5vZGVzLmdldChyZWZlcmVuY2UpIHx8IGZuKT8ubmFtZTtcclxuICAgIGV4cGVjdChwcm9kdWNlcikudG9CZVRydXRoeSgpO1xyXG4gICAgY29uc3Qga2V5ID0gW3Byb2R1Y2VyLCBtZXNzYWdlLm5hbWUsIHNpZ25hbC5uYW1lXS5qb2luKCcgOjogJyk7XHJcbiAgICBleHBlY3QoY29udHJhY3RzW2tleV0sICdTZW1hbnRpYyBzaWduYWwgaWRlbnRpdHkgbXVzdCBiZSB1bmlxdWU6ICcgKyBrZXkpLnRvQmVVbmRlZmluZWQoKTtcclxuICAgIGNvbnRyYWN0c1trZXldID0ge1xyXG4gICAgICAuLi5PYmplY3QuZnJvbUVudHJpZXMoWydzdGFydF9iaXQnLCAnbGVuZ3RoX2JpdHMnLCAnZGF0YV90eXBlJywgJ2ZhY3RvcicsICdvZmZzZXRfdmFsdWUnLFxyXG4gICAgICAgICd1bml0JywgJ21pbl92YWx1ZScsICdtYXhfdmFsdWUnLCAnYnl0ZV9vcmRlciddLm1hcChmaWVsZCA9PiBbZmllbGQsIHNpZ25hbFtmaWVsZF0gPz8gbnVsbF0pKSxcclxuICAgICAgZW51bV92YWx1ZXM6IHNpZ25hbC5kYXRhPy5lbnVtX3ZhbHVlcyA/PyBudWxsLFxyXG4gICAgICBzZW1hbnRpY190eXBlOiBzaWduYWwuc2VtYW50aWM/LnNlbWFudGljX3R5cGUgPz8gbnVsbCxcclxuICAgICAgZ2VuZXJhdGlvbl9yb2xlOiBzaWduYWwuY29uZmlndXJhdGlvbj8uZ2VuZXJhdGlvbl9yb2xlID8/IG51bGwsXHJcbiAgICB9O1xyXG4gIH1cclxuICBleHBlY3QoY29udHJhY3RzLCAnRXZlcnkgb3JpZ2luYWwgc2lnbmFsIGFuZCBpdHMgZXhwbGljaXQgZW5jb2RpbmcgbXVzdCBzdXJ2aXZlIGdlbmVyYXRpb24uJykudG9FcXVhbChleHBlY3RlZCk7XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHZlcmlmeUFydGlmYWN0cyhwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIG1pbmltdW1DYW5vbmljYWxTaWduYWxzOiBudW1iZXIsIGludGVybmFsQ29udHJvbGxlcj86IHN0cmluZykge1xyXG4gIC8vIFRoZSBjb21wbGV0ZWQgbW9kZWwgaXMgc3RhYmxlOyB0aGVzZSBpbmRlcGVuZGVudCByZWFkcyBuZWVkIG5vIHNlcmlhbCB3YWl0cy5cclxuICBjb25zdCBbd29ya2Zsb3csIGpvYkxpc3QsIHNuYXBzaG90cywgc2lnbmFscywgbWVzc2FnZXNdID0gYXdhaXQgUHJvbWlzZS5hbGwoW1xyXG4gICAgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5JyksXHJcbiAgICByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpLFxyXG4gICAgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvc25hcHNob3RzJyksXHJcbiAgICBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyksXHJcbiAgICBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdtZXNzYWdlcycpLFxyXG4gIF0pO1xyXG4gIGV4cGVjdChPYmplY3Qua2V5cyh3b3JrZmxvdy5zdGF0dXNlcykuc29ydCgpKS50b0VxdWFsKFsuLi5zdGVwc10uc29ydCgpKTtcclxuICBmb3IgKGNvbnN0IHN0ZXAgb2Ygc3RlcHMpIGV4cGVjdChkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXSksIGAke3N0ZXB9OiAke3dvcmtmbG93LnN0YXR1c2VzW3N0ZXBdfWApLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBqb2JzID0gam9iTGlzdC5qb2JzO1xyXG4gIGV4cGVjdChqb2JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KGpvYnNbMF0uc3RhdHVzKS50b0JlKCdjb21wbGV0ZWQnKTtcclxuICBjb25zdCBzbmFwc2hvdCA9IHNuYXBzaG90cy5zaW11bGF0aW9ucy5maW5kKChpdGVtOiB7IGpvYl9pZDogc3RyaW5nIH0pID0+IGl0ZW0uam9iX2lkID09PSBqb2JzWzBdLmlkKTtcclxuICBleHBlY3Qoc25hcHNob3QpLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBmdWxsID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvc2ltdWxhdGlvbi1zbmFwc2hvdHMvJHtzbmFwc2hvdC5pZH1gKTtcclxuICBjb25zdCBhc3Nlc3NtZW50ID0gZnVsbC5yZXN1bHQuYXNzZXNzbWVudDtcclxuICBleHBlY3QoYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS5zY29wZV9tb2RlKS50b0JlKCdBTEwnKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS5jb21wbGV0ZSkudG9CZSh0cnVlKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5jb25mb3JtYW5jZSkudG9CZSgnUEFTUycpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LmZhaWxlZF9yb3V0ZV9jb3VudCkudG9CZSgwKTtcclxuICBleHBlY3Qoc2lnbmFscy5sZW5ndGgsICdUaGUgZnVsbCBjYW5vbmljYWwgc2lnbmFsIGludmVudG9yeSBtdXN0IHN1cnZpdmUgZ2VuZXJhdGlvbi4nKS50b0JlR3JlYXRlclRoYW5PckVxdWFsKG1pbmltdW1DYW5vbmljYWxTaWduYWxzKTtcclxuICBjb25zdCBleGNsdWRlZCA9IGFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UudHJhbnNwb3J0X2V4Y2x1c2lvbnMgPz8gW107XHJcbiAgZm9yIChjb25zdCBpdGVtIG9mIGV4Y2x1ZGVkKSB7XHJcbiAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXMuZmluZChyb3cgPT4gcm93LmlkID09PSBpdGVtLm1lc3NhZ2VfaWQpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UsIGBFeGNsdWRlZCBtZXNzYWdlICR7aXRlbS5tZXNzYWdlX2lkfSBtdXN0IGV4aXN0LmApLnRvQmVUcnV0aHkoKTtcclxuICAgIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24ucm91dGluZy5lbmFibGVkKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IGNvbnRyYWN0ID0gbWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3Q7XHJcbiAgICBleHBlY3QoY29udHJhY3QuY29uc3VtZXJfcmVmcykudG9FcXVhbChbXSk7XHJcbiAgICBleHBlY3QoaXRlbS5yZWFzb25fY29kZSkudG9CZShjb250cmFjdC5yb2xlID09PSAnSU5URVJOQUxfU1RBVEUnXHJcbiAgICAgID8gJ0lOVEVSTkFMX1NUQVRFX05PVF9ST1VURUQnIDogJ0VYUExJQ0lUX0ZVTkNUSU9OX09VVFBVVF9OT1RfUk9VVEVEJyk7XHJcbiAgfVxyXG4gIGlmIChpbnRlcm5hbENvbnRyb2xsZXIpIHtcclxuICAgIGNvbnN0IG5vZGVzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICAgIGNvbnN0IGNvbnRyb2xsZXIgPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSBpbnRlcm5hbENvbnRyb2xsZXIpO1xyXG4gICAgZXhwZWN0KGV4Y2x1ZGVkLmxlbmd0aCkudG9CZUdyZWF0ZXJUaGFuKDApO1xyXG4gICAgZm9yIChjb25zdCBpdGVtIG9mIGV4Y2x1ZGVkKSB7XHJcbiAgICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKHJvdyA9PiByb3cuaWQgPT09IGl0ZW0ubWVzc2FnZV9pZCk7XHJcbiAgICAgIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdCkudG9NYXRjaE9iamVjdCh7IHJvbGU6ICdJTlRFUk5BTF9TVEFURScsIHNjb3BlOiAnSU5URVJOQUwnLCBwcm9kdWNlcl9yZWY6IGNvbnRyb2xsZXIuaWQsIGNvbnN1bWVyX3JlZnM6IFtdIH0pO1xyXG4gICAgfVxyXG4gIH1cclxuICBjb25zdCBleGNsdWRlZFNpZ25hbHMgPSBuZXcgU2V0KGV4Y2x1ZGVkLmZsYXRNYXAoKGl0ZW06IHsgc2lnbmFsX2lkczogc3RyaW5nW10gfSkgPT4gaXRlbS5zaWduYWxfaWRzKSk7XHJcbiAgZXhwZWN0KGFzc2Vzc21lbnQub2JzZXJ2ZWRfc2lnbmFsX2NvdW50LCAnQUxMIG11c3Qgb2JzZXJ2ZSBldmVyeSBjYW5vbmljYWwgc2lnbmFsIHdpdGggYSB0cmFuc3BvcnQgb2JsaWdhdGlvbi4nKS50b0JlKHNpZ25hbHMubGVuZ3RoIC0gZXhjbHVkZWRTaWduYWxzLnNpemUpO1xyXG4gIGZvciAoY29uc3Qga2V5IG9mIFsnbWlzc2luZ19vYnNlcnZlZF9zaWduYWxfaWRzJywgJ21pc3Npbmdfb2JzZXJ2ZWRfcm91dGVfaWRzJywgJ21pc3Npbmdfb2JzZXJ2ZWRfbmV0d29ya19pZHMnXSkgZXhwZWN0KGFzc2Vzc21lbnRba2V5XSkudG9FcXVhbChbXSk7XHJcbiAgY29uc3QgdHJhY2UgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9zaW11bGF0aW9ucy8ke2pvYnNbMF0uaWR9L3RyYWNlLXdpbmRvdz9saW1pdD0xMGApO1xyXG4gIGV4cGVjdCh0cmFjZS5jb3VudCkudG9CZUdyZWF0ZXJUaGFuKDApO1xyXG4gIGV4cGVjdCh0cmFjZS5ldmVudHMuc29tZSgoaXRlbTogeyBzaWduYWxzPzogdW5rbm93bltdIH0pID0+IGl0ZW0uc2lnbmFscyAmJiBPYmplY3Qua2V5cyhpdGVtLnNpZ25hbHMpLmxlbmd0aCkpLnRvQmVUcnV0aHkoKTtcclxuICByZXR1cm4geyB3b3JrZmxvdywgam9iOiBqb2JzWzBdLmlkLCBhc3Nlc3NtZW50IH07XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIHJlc3RhcnQ6IGJvb2xlYW4sIGV4cGVjdGVkSGFyZHdhcmU6IHN0cmluZ1tdID0gW10sIGNyYXNoU2ltdWxhdGlvbiA9IGZhbHNlLFxyXG4gIGV4cGVjdGVkU2lnbmFscz86IFJlY29yZDxzdHJpbmcsIHVua25vd24+LCBhZnRlckZpcnN0TW9kZWxBcHBsaWVkPzogKCkgPT4gUHJvbWlzZTx2b2lkPiwgc3RvcE9uRXZpZGVuY2VCbG9jayA9IGZhbHNlKSB7XHJcbiAgbGV0IHJldmlld0NvdW50ID0gMDtcclxuICBsZXQgcnVuSWQ6IHN0cmluZyB8IHVuZGVmaW5lZDtcclxuICBjb25zdCByZXZpZXdlZCA9IG5ldyBTZXQ8c3RyaW5nPigpO1xyXG4gIGxldCByZXN0YXJ0ZWRKb2JJZDogc3RyaW5nIHwgdW5kZWZpbmVkO1xyXG4gIGxldCB3YXRjaGRvZyA9IG5ldyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nKHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICBmb3IgKGxldCBjaGVja3BvaW50ID0gMDsgY2hlY2twb2ludCA8IDE2OyBjaGVja3BvaW50KyspIHtcclxuICAgIGxldCB3b3JrZmxvdzogYW55O1xyXG4gICAgbGV0IHByb3Bvc2FsSWQgPSAnJztcclxuICAgIGxldCByZWFkeVZlcnNpb24gPSAnJztcclxuICAgIGxldCByZWFkeVNpbmNlID0gMDtcclxuICAgIGNvbnN0IGlzQ2hlY2twb2ludCA9IGFzeW5jICgpID0+IHtcclxuICAgICAgd2F0Y2hkb2cucmVtYWluaW5nKHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICAgICAgYXdhaXQgYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeShwYWdlKTtcclxuICAgICAgd29ya2Zsb3cgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgY29uc3QgcHJvZ3Jlc3MgPSB3YXRjaGRvZy5vYnNlcnZlKHdvcmtmbG93LCBwZXJmb3JtYW5jZS5ub3coKSk7XHJcbiAgICAgIGlmIChwcm9ncmVzcy5hZHZhbmNlZCkgcHJvZ3Jlc3NNaWxlc3RvbmVzLmdldCh0ZXN0LmluZm8oKS50ZXN0SWQpIS5wdXNoKHtcclxuICAgICAgICBhdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLCBmcm9udGllcjogcHJvZ3Jlc3MuZnJvbnRpZXIsXHJcbiAgICAgICAgY29tcGxldGVkVGhyb3VnaDogc3RlcHNbcHJvZ3Jlc3MuZnJvbnRpZXIgLSAxXSxcclxuICAgICAgICBwcm9qZWN0OiB3b3JrZmxvdy5wcm9qZWN0X2lkLCBleGVjdXRpb246IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLFxyXG4gICAgICB9KTtcclxuICAgICAgaWYgKGNyYXNoU2ltdWxhdGlvbiAmJiAhcmVzdGFydGVkSm9iSWQgJiYgZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXMudmFsaWRhdGlvbikpIHtcclxuICAgICAgICBjb25zdCBqb2JzID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnM7XHJcbiAgICAgICAgY29uc3QgcnVubmluZyA9IGpvYnMuZmluZCgoam9iOiB7IHN0YXR1czogc3RyaW5nIH0pID0+IGpvYi5zdGF0dXMgPT09ICdydW5uaW5nJyk7XHJcbiAgICAgICAgaWYgKHJ1bm5pbmcpIHtcclxuICAgICAgICAgIHJlc3RhcnRlZEpvYklkID0gcnVubmluZy5pZDtcclxuICAgICAgICAgIGF3YWl0IHJlc3RhcnRBcHBsaWNhdGlvbihwYWdlLCB0cnVlKTtcclxuICAgICAgICAgIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgICAgICAgICByZXR1cm4gZmFsc2U7XHJcbiAgICAgICAgfVxyXG4gICAgICB9XHJcbiAgICAgIGlmIChzdGVwcy5ldmVyeShzdGVwID0+IGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzW3N0ZXBdKSkpIHJldHVybiB0cnVlO1xyXG4gICAgICBjb25zdCBleGVjdXRpb24gPSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbjtcclxuICAgICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdSRVZJRVdfUkVRVUlSRUQnKSB7XHJcbiAgICAgICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XHJcbiAgICAgICAgcHJvcG9zYWxJZCA9IGNvbnZlcnNhdGlvbi5kYXRhLmFjdGl2ZV9wcm9wb3NhbDtcclxuICAgICAgICAvLyBQb2xsaW5nIG1heSBzdGlsbCBleHBvc2UgdGhlIGp1c3QtYXBwbGllZCByZXZpZXcgd2hpbGUgdGhlIFVJIHN0YXJ0c1xyXG4gICAgICAgIC8vIGl0cyBkdXJhYmxlIGNvbnRpbnVhdGlvbi4gV2FpdCBmb3IgYSBkaXN0aW5jdCBwcm9wb3NhbCwgbm90IGl0cyBsYWJlbC5cclxuICAgICAgICByZXR1cm4gQm9vbGVhbihwcm9wb3NhbElkKSAmJiAhcmV2aWV3ZWQuaGFzKHByb3Bvc2FsSWQpO1xyXG4gICAgICB9XHJcbiAgICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnUkVBRFlfVE9fQ09OVElOVUUnIHx8IChleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLnJlY292ZXJhYmxlID09PSB0cnVlKSkge1xyXG4gICAgICAgIGlmIChyZWFkeVZlcnNpb24gIT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0KSB7XHJcbiAgICAgICAgICByZWFkeVZlcnNpb24gPSBleGVjdXRpb24udXBkYXRlZF9hdDsgcmVhZHlTaW5jZSA9IERhdGUubm93KCk7XHJcbiAgICAgICAgfVxyXG4gICAgICAgIC8vIFdoaWxlIGEgbGFyZ2UgY29udGludWF0aW9uIGlzIGdlbmVyYXRpbmcsIHRoZSBsYXN0IGNvbW1pdHRlZCBzZXJ2ZXJcclxuICAgICAgICAvLyBjaGVja3BvaW50IGNhbiBzdGlsbCBiZSBSRUFEWS4gQWN0IG9ubHkgd2hlbiB0aGUgVUkgb2ZmZXJzIGl0IHRvby5cclxuICAgICAgICBjb25zdCBidXR0b24gPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pXHJcbiAgICAgICAgICAuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBdWZ0cmFnIGZvcnRzZXR6ZW4nLCBleGFjdDogdHJ1ZSB9KTtcclxuICAgICAgICByZXR1cm4gRGF0ZS5ub3coKSAtIHJlYWR5U2luY2UgPiA1MDAwICYmIGF3YWl0IGJ1dHRvbi5ldmFsdWF0ZUFsbChidXR0b25zID0+IGJ1dHRvbnMuc29tZShidXR0b24gPT4gIShidXR0b24gYXMgSFRNTEJ1dHRvbkVsZW1lbnQpLmRpc2FibGVkICYmIGJ1dHRvbi5nZXRDbGllbnRSZWN0cygpLmxlbmd0aCA+IDAgJiYgZ2V0Q29tcHV0ZWRTdHlsZShidXR0b24pLnZpc2liaWxpdHkgIT09IFwiaGlkZGVuXCIpKTtcclxuICAgICAgfVxyXG4gICAgICByZXR1cm4gWydCTE9DS0VEJywgJ0ZBSUxFRCcsICdJTkNPTVBMRVRFJ10uaW5jbHVkZXMoZXhlY3V0aW9uPy5zdGF0ZSk7XHJcbiAgICB9O1xyXG4gICAgLy8gQSBzaW5nbGUgcG9sbCBwcmV2aW91c2x5IHRpbWVkIGFsbCBvZiBDYXBhY2l0eSAtPiBJbnRlbGxpZ2VuY2UgdG9nZXRoZXIuXHJcbiAgICAvLyBCb3VuZCBlYWNoIGdlbnVpbmUgc3RhZ2UgYWR2YW5jZSwgd2hpbGUgcmV0cmllcyBhbmQgcmVzdGFydHMgcmV0YWluIHRoZWlyXHJcbiAgICAvLyByZW1haW5pbmcgZGVhZGxpbmUuIFRoZSBpbmRlcGVuZGVudCAyMC1taW51dGUgdGVzdCB0aW1lb3V0IGlzIHVuY2hhbmdlZC5cclxuICAgIGxldCBhdHRlbXB0ID0gMDtcclxuICAgIHdoaWxlICghYXdhaXQgaXNDaGVja3BvaW50KCkpIHtcclxuICAgICAgY29uc3QgcmVtYWluaW5nID0gd2F0Y2hkb2cucmVtYWluaW5nKHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICAgICAgYXdhaXQgcGFnZS53YWl0Rm9yVGltZW91dChNYXRoLm1pbihbNTAwLCAxMDAwLCAyMDAwXVtNYXRoLm1pbihhdHRlbXB0KyssIDIpXSwgcmVtYWluaW5nKSk7XHJcbiAgICB9XHJcbiAgICBydW5JZCA/Pz0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnJ1bl9pZDtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkKS50b0JlKHJ1bklkKTtcclxuICAgIGlmIChzdGVwcy5ldmVyeShzdGVwID0+IGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzW3N0ZXBdKSkpIHtcclxuICAgICAgaWYgKGNyYXNoU2ltdWxhdGlvbikgZXhwZWN0KHJlc3RhcnRlZEpvYklkLCAnQSByZWFsIHJ1bm5pbmcgc2ltdWxhdGlvbiBtdXN0IGJlIG9ic2VydmVkIGFuZCBpbnRlcnJ1cHRlZC4nKS50b0JlVHJ1dGh5KCk7XHJcbiAgICAgIHJldHVybiB7IHJ1bklkLCByZXZpZXdlZDogWy4uLnJldmlld2VkXSwgcmVzdGFydGVkSm9iSWQgfTtcclxuICAgIH1cclxuICAgIGNvbnN0IGV4ZWN1dGlvbiA9IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uO1xyXG4gICAgY29uc3QgZGlhbG9nID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KTtcclxuICAgIGlmIChzdG9wT25FdmlkZW5jZUJsb2NrICYmIGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24uYmxvY2tpbmdfZmluZGluZ3M/Lmxlbmd0aCkge1xyXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoYFdpemFyZCBCTE9DS0VEIGF0ICR7ZXhlY3V0aW9uLnN0ZXB9OiAke2V4ZWN1dGlvbi5tZXNzYWdlfWApO1xyXG4gICAgfVxyXG4gICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24ubWVzc2FnZT8uaW5jbHVkZXMoJ1JFQURZX1dJVEhfV0FSTklOR1MnKSkge1xyXG4gICAgICBjb25zdCBiZWZvcmVSZXZpZXcgPSBhd2FpdCByZWFkV2FybmluZ1Jldmlld1N0YXRlKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgICBjb25zdCBwcmVmbGlnaHQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9wcmVmbGlnaHQnKTtcclxuICAgICAgY29uc3Qgd2FybmluZ3MgPSBkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdQcmVmbGlnaHQtV2FybnVuZ2VuJyB9KTtcclxuICAgICAgYXdhaXQgZXhwZWN0KHdhcm5pbmdzLmdldEJ5Um9sZSgnbGlzdGl0ZW0nKS5maXJzdCgpKS50b0JlVmlzaWJsZSgpO1xyXG4gICAgICBjb25zdCBzdGFydGVkID0gcGVyZm9ybWFuY2Uubm93KCksIHN0YXJ0ZWRXYWxsID0gRGF0ZS5ub3coKTtcclxuICAgICAgd2F0Y2hkb2cucmVtYWluaW5nKHN0YXJ0ZWQpO1xyXG4gICAgICBjb25zdCBhcHByb3ZhbFJlc3BvbnNlID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4gbmV3IFVSTChyZXNwb25zZS51cmwoKSkucGF0aG5hbWUgPT09ICcvYXBpL2VuZ2luZWVyaW5nL3ByZWZsaWdodC93YXJuaW5ncy9hcHByb3ZlJ1xyXG4gICAgICAgICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnLCB7IHRpbWVvdXQ6IDE4MF8wMDAgfSk7XHJcbiAgICAgIGF3YWl0IHdhcm5pbmdzLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnV2FybnVuZ2VuIGZyZWlnZWJlbiB1bmQgZm9ydHNldHplbicgfSkuY2xpY2soKTtcclxuICAgICAgY29uc3QgYXBwcm92ZWQgPSBhd2FpdCBhcHByb3ZhbFJlc3BvbnNlO1xyXG4gICAgICBjb25zdCByZWNlaXB0ID0gYXdhaXQgYXBwcm92ZWQuanNvbigpO1xyXG4gICAgICBjb25zdCBhZnRlclJldmlldyA9IGF3YWl0IHJlYWRXYXJuaW5nUmV2aWV3U3RhdGUocGFnZSwgcHJvamVjdCk7XHJcbiAgICAgIGNvbnN0IHByb29mID0geyBiZWZvcmU6IGJlZm9yZVJldmlldywgYWZ0ZXI6IGFmdGVyUmV2aWV3LCBzbmFwc2hvdElkOiBwcmVmbGlnaHQuaWQsXHJcbiAgICAgICAgcmVxdWVzdFByb2plY3Q6IGFwcHJvdmVkLnJlcXVlc3QoKS5oZWFkZXJzKClbJ3gtcHJvamVjdC1pZCddLCBzdWJtaXR0ZWQ6IGFwcHJvdmVkLnJlcXVlc3QoKS5wb3N0RGF0YUpTT04oKSxcclxuICAgICAgICBzdGF0dXM6IGFwcHJvdmVkLnN0YXR1cygpLCByZXNwb25zZTogcmVjZWlwdCwgc3RhcnRlZCwgc3RhcnRlZFdhbGwsIGZpbmlzaGVkV2FsbDogRGF0ZS5ub3coKSB9O1xyXG4gICAgICBjb25zdCBjb21taXR0ZWRBdCA9IHBlcmZvcm1hbmNlLm5vdygpO1xyXG4gICAgICBjb25zdCBjb21taXR0ZWQgPSB3YXRjaGRvZy5jb21taXRXYXJuaW5nUmV2aWV3KHByb29mLCBjb21taXR0ZWRBdCk7XHJcbiAgICAgIGF3YWl0IHRlc3QuaW5mbygpLmF0dGFjaCgndmVyaWZpZWQtd2FybmluZy1yZXZpZXctcHJvb2YnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvb2YsIGNvbW1pdHRlZEF0LCBjb21taXR0ZWQgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgICAgIHByb2dyZXNzTWlsZXN0b25lcy5nZXQodGVzdC5pbmZvKCkudGVzdElkKSEucHVzaCh7IGF0OiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksIG1hbnVhbFdhcm5pbmdBcHByb3ZhbDogY29tbWl0dGVkLmFwcHJvdmFsSWRlbnRpdHksXHJcbiAgICAgICAgZnJvbnRpZXI6IGNvbW1pdHRlZC5mcm9udGllciwgcHJvamVjdCwgZXhlY3V0aW9uOiBhZnRlclJldmlldy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbiwgYXBwcm92YWw6IHJlY2VpcHQuYXBwcm92YWwgfSk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKSkuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQsXHJcbiAgICAgICAgeyB0aW1lb3V0OiBleHBlY3RlZEhhcmR3YXJlLmxlbmd0aCA+IDEwMCA/IDE4MF8wMDAgOiA2MF8wMDAgfSkubm90LnRvQmUoZXhlY3V0aW9uLnVwZGF0ZWRfYXQpO1xyXG4gICAgICBjb250aW51ZTtcclxuICAgIH1cclxuICAgIGlmIChbJ0JMT0NLRUQnLCAnRkFJTEVEJywgJ0lOQ09NUExFVEUnXS5pbmNsdWRlcyhleGVjdXRpb24/LnN0YXRlKSAmJiBleGVjdXRpb24ucmVjb3ZlcmFibGUgIT09IHRydWUpIHtcclxuICAgICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XHJcbiAgICAgIGNvbnN0IGlkID0gY29udmVyc2F0aW9uLmRhdGE/LmFjdGl2ZV9wcm9wb3NhbDtcclxuICAgICAgY29uc3QgcHJvcG9zYWwgPSBpZCA/IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke2lkfWApIDogbnVsbDtcclxuICAgICAgYXdhaXQgdGVzdC5pbmZvKCkuYXR0YWNoKCd3aXphcmQtYmxvY2tlcicsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBleGVjdXRpb24sXHJcbiAgICAgICAgcHJvcG9zYWw6IHByb3Bvc2FsPy5kYXRhPy52YWxpZGF0aW9uX3Jlc3VsdCwgdmlzaWJsZTogYXdhaXQgZGlhbG9nLmlubmVyVGV4dCgpIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gICAgICB0aHJvdyBuZXcgRXJyb3IoYFdpemFyZCAke2V4ZWN1dGlvbi5zdGF0ZX0gYXQgJHtleGVjdXRpb24uc3RlcH06ICR7ZXhlY3V0aW9uLm1lc3NhZ2V9YCk7XHJcbiAgICB9XHJcbiAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JFQURZX1RPX0NPTlRJTlVFJyB8fCAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5yZWNvdmVyYWJsZSA9PT0gdHJ1ZSkpIHtcclxuICAgICAgY29uc3QgYnV0dG9uID0gZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQXVmdHJhZyBmb3J0c2V0emVuJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgICAgIHRyeSB7XHJcbiAgICAgICAgYXdhaXQgYnV0dG9uLmNsaWNrKHsgdGltZW91dDogMjAwMCB9KTtcclxuICAgICAgfSBjYXRjaCAoZXJyb3IpIHtcclxuICAgICAgICBjb25zdCBsYXRlc3QgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgICBpZiAobGF0ZXN0LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0ID09PSBleGVjdXRpb24udXBkYXRlZF9hdCAmJiBhd2FpdCBidXR0b24uZXZhbHVhdGVBbGwoYnV0dG9ucyA9PiBidXR0b25zLnNvbWUoYnV0dG9uID0+ICEoYnV0dG9uIGFzIEhUTUxCdXR0b25FbGVtZW50KS5kaXNhYmxlZCAmJiBidXR0b24uZ2V0Q2xpZW50UmVjdHMoKS5sZW5ndGggPiAwICYmIGdldENvbXB1dGVkU3R5bGUoYnV0dG9uKS52aXNpYmlsaXR5ICE9PSBcImhpZGRlblwiKSkpIHRocm93IGVycm9yO1xyXG4gICAgICAgIGNvbnRpbnVlO1xyXG4gICAgICB9XHJcbiAgICAgIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcclxuICAgICAgICBjb25zdCBsYXRlc3QgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgICByZXR1cm4gbGF0ZXN0LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy51cGRhdGVkX2F0ICE9PSBleGVjdXRpb24udXBkYXRlZF9hdFxyXG4gICAgICAgICAgfHwgbGF0ZXN0LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JVTk5JTkcnXHJcbiAgICAgICAgICB8fCBsYXRlc3Quc3RhdHVzZXM/LltleGVjdXRpb24uc3RlcF0gPT09ICdJTl9QUk9HUkVTUyc7XHJcbiAgICAgIH0sIHsgdGltZW91dDogNjBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbiAgICAgIGNvbnRpbnVlO1xyXG4gICAgfVxyXG4gICAgY29uc3QgY2FuZGlkYXRlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7cHJvcG9zYWxJZH1gKTtcclxuICAgIGlmIChjYW5kaWRhdGUuZGF0YS5wcm9wb3NhbF90eXBlID09PSAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJyAmJiByZXZpZXdDb3VudCA9PT0gMCAmJiBleHBlY3RlZEhhcmR3YXJlLmxlbmd0aCkge1xyXG4gICAgICBjb25zdCBoYXJkd2FyZSA9IGNhbmRpZGF0ZS5kYXRhLmNoYW5nZXNcclxuICAgICAgICAuZmlsdGVyKChjaGFuZ2U6IHsgb2JqZWN0X3R5cGU6IHN0cmluZyB9KSA9PiBjaGFuZ2Uub2JqZWN0X3R5cGUgPT09ICdIYXJkd2FyZU5vZGUnKVxyXG4gICAgICAgIC5tYXAoKGNoYW5nZTogeyBkYXRhOiB7IG5hbWU6IHN0cmluZyB9IH0pID0+IGNoYW5nZS5kYXRhLm5hbWUpO1xyXG4gICAgICBleHBlY3QoaGFyZHdhcmUsICdUaGUgVUkgbXVzdCBwcmVzZXJ2ZSB0aGUgaGFyZHdhcmUgZXhwbGljaXRseSBuYW1lZCBpbiB0aGUgdXNlciByZXF1ZXN0LicpXHJcbiAgICAgICAgLnRvRXF1YWwoZXhwZWN0LmFycmF5Q29udGFpbmluZyhleHBlY3RlZEhhcmR3YXJlKSk7XHJcbiAgICB9XHJcbiAgICBleHBlY3QocmV2aWV3ZWQuaGFzKHByb3Bvc2FsSWQpLCAnVGhlIHNhbWUgcHJvcG9zYWwgbXVzdCBub3QgcmVxdWVzdCByZXZpZXcgdHdpY2UuJykudG9CZShmYWxzZSk7XHJcbiAgICBjb25zdCBhcHBseVJlc3BvbnNlID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4gcmVzcG9uc2UudXJsKCkuaW5jbHVkZXMoYC9wcm9wb3NhbHMvJHtwcm9wb3NhbElkfS9hcHByb3ZlLWFwcGx5YCkgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcsIHsgdGltZW91dDogMTgwXzAwMCB9KTtcclxuICAgIGNvbnN0IGFwcHJvdmFsID0gZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAvXihGcmVpZ2ViZW4sIMO8YmVybmVobWVuICYgZm9ydGZhaHJlbnzDnGJlcm5laG1lbiAmIGZvcnRmYWhyZW4pJC8gfSk7XHJcbiAgICBhd2FpdCBleHBlY3QoYXBwcm92YWwpLnRvQmVFbmFibGVkKHsgdGltZW91dDogNjBfMDAwIH0pO1xyXG4gICAgYXdhaXQgYXBwcm92YWwuY2xpY2soKTtcclxuICAgIGNvbnN0IGFwcGxpZWQgPSBhd2FpdCBhcHBseVJlc3BvbnNlO1xyXG4gICAgaWYgKCFhcHBsaWVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke2FwcGxpZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBhcHBsaWVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgICBleHBlY3QoKGF3YWl0IGFwcGxpZWQuanNvbigpKS5kYXRhLnN0YXR1cykudG9CZSgnQVBQTElFRCcpO1xyXG4gICAgcmV2aWV3ZWQuYWRkKHByb3Bvc2FsSWQpOyByZXZpZXdDb3VudCsrO1xyXG4gICAgLy8gQSBkaXN0aW5jdCwgYWN0dWFsbHkgY29tbWl0dGVkIG1hbnVhbCByZXZpZXcgc3RhcnRzIHRoZSBuZXh0IGF1dG9tYXRpY1xyXG4gICAgLy8gc2VjdGlvbi4gSXRzIHdyaXRlIHN0aWxsIGhhcyB0aGUgc2VwYXJhdGUgdW5jaGFuZ2VkIDE4MC1zZWNvbmQgbGltaXQuXHJcbiAgICB3YXRjaGRvZyA9IG5ldyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nKHBlcmZvcm1hbmNlLm5vdygpLCB3b3JrZmxvdyk7XHJcbiAgICBpZiAoY2FuZGlkYXRlLmRhdGEucHJvcG9zYWxfdHlwZSA9PT0gJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcgJiYgZXhwZWN0ZWRTaWduYWxzKSB7XHJcbiAgICAgIGF3YWl0IHZlcmlmeVNpZ25hbENvbnRyYWN0cyhwYWdlLCBwcm9qZWN0LCBleHBlY3RlZFNpZ25hbHMpO1xyXG4gICAgfVxyXG4gICAgaWYgKHJldmlld0NvdW50ID09PSAxICYmIGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQpIHtcclxuICAgICAgYXdhaXQgYWZ0ZXJGaXJzdE1vZGVsQXBwbGllZCgpO1xyXG4gICAgICAvLyBUaGlzIG9uZSB0ZXN0IGV4cGxpY2l0bHkgc3VibWl0cyBBTUVORCBhbmQgd2FpdHMgZm9yIGl0cyByZWNlaXB0LiBPbmx5XHJcbiAgICAgIC8vIHRoYXQgZGVsaWJlcmF0ZSBhY3Rpb24gcGVybWl0cyBiaW5kaW5nIGl0cyBuZXcgcmVxdWVzdCByZXZpc2lvbi5cclxuICAgICAgY29uc3QgYW1lbmRlZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICBleHBlY3QoYW1lbmRlZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkKS50b0JlKHJ1bklkKTtcclxuICAgICAgd2F0Y2hkb2cgPSBuZXcgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyhwZXJmb3JtYW5jZS5ub3coKSwgYW1lbmRlZCk7XHJcbiAgICB9XHJcbiAgICBpZiAocmV2aWV3Q291bnQgPT09IDEpIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7IC8vIER1cmFibGUgcmVsb2FkIGFmdGVyIGEgcmVhbCBjb21taXQuXHJcbiAgICBpZiAocmVzdGFydCAmJiByZXZpZXdDb3VudCA9PT0gMikge1xyXG4gICAgICBhd2FpdCByZXN0YXJ0QXBwbGljYXRpb24ocGFnZSk7XHJcbiAgICAgIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgICB9XHJcbiAgICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICAgIGNvbnN0IGN1cnJlbnQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgcmV0dXJuIGN1cnJlbnQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQgIT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0O1xyXG4gICAgfSwgeyB0aW1lb3V0OiA2MF8wMDAgfSkudG9CZSh0cnVlKTtcclxuICB9XHJcbiAgdGhyb3cgbmV3IEVycm9yKCdXaXphcmQgZXhjZWVkZWQgMTYgcmV2aWV3L2NvbnRpbnVhdGlvbiBjaGVja3BvaW50cy4nKTtcclxufVxyXG5cclxudGVzdCgnd2l6YXJkIHJlZnVzZXMgYW4gdW5hdmFpbGFibGUgY2F0YWxvZyBhbmQgcmVjb3ZlcnMgdXNpbmcgdGhlIHJlYWwgcmVnaXN0cnkgQGNhdGFsb2ctcmVjb3ZlcnknLCBhc3luYyAoe3BhZ2V9KSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWNhdGFsb2ctcmVjb3ZlcnktJyArIHJhbmRvbVVVSUQoKTtcclxuICBhd2FpdCBwYWdlLnJvdXRlKCcqKi9hcGkvdGVjaG5vbG9naWVzJywgcm91dGUgPT4gcm91dGUuZnVsZmlsbCh7c3RhdHVzOjUwMyxcclxuICAgIGNvbnRlbnRUeXBlOidhcHBsaWNhdGlvbi9qc29uJyxib2R5OkpTT04uc3RyaW5naWZ5KHtlcnJvcjonRGVyIHZvbGxzdMOkbmRpZ2UgVGVjaG5vbG9naWVrYXRhbG9nIGlzdCBkZXJ6ZWl0IG5pY2h0IGVycmVpY2hiYXIuJ30pfSkpO1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2FsZXJ0JykpLnRvQ29udGFpblRleHQoJ1RlY2hub2xvZ2lla2F0YWxvZycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdQcm9qZWt0bmFtZScsIHtleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cubG9jYXRvcignI2VuZ2luZWVyaW5nLXByb2plY3QtbmFtZScpLmZpbGwoJ0NhdGFsb2cgcmV0cnknKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHtleGFjdDp0cnVlfSkuZmlsbCgnZWluIEFrdG9yIHp1bSBwcm9wb3J0aW9uYWwgc2NobGllw59lbiBlaW5lcyBWZW50aWwnKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKSkudG9CZURpc2FibGVkKCk7XHJcbiAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzKS50b0hhdmVMZW5ndGgoMCk7XHJcbiAgYXdhaXQgcGFnZS51bnJvdXRlKCcqKi9hcGkvdGVjaG5vbG9naWVzJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonVGVjaG5vbG9naWVrYXRhbG9nIGVybmV1dCBsYWRlbid9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdhbGVydCcpKS50b0hhdmVDb3VudCgwKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKSkudG9CZUVuYWJsZWQoKTtcclxuICBjb25zdCBjYXRhbG9nID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvdGVjaG5vbG9naWVzJykpLmpzb24oKTtcclxuICBleHBlY3QoY2F0YWxvZy50ZWNobm9sb2d5X2NvdW50KS50b0JlKDEyNSk7XHJcbn0pO1xyXG5cclxudGVzdCgnbmV3IHNtYWxsIHdpemFyZCB0cmF2ZXJzZXMgYWxsIG5pbmUgc3RhZ2VzIGFuZCBzdXJ2aXZlcyByZWxvYWQvcmVzdGFydCBAc21hbGwnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgZXJyb3JzOiBzdHJpbmdbXSA9IFtdOyBwYWdlLm9uKCdwYWdlZXJyb3InLCBlcnJvciA9PiBlcnJvcnMucHVzaChlcnJvci5tZXNzYWdlKSk7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXNtYWxsLScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdFMkUgc21hbGwnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCgnRXJ6ZXVnZSBlaW4gQXV0b21vdGl2ZSBDQU4tRkQgTmV0endlcmsgbWl0IGVpbmVtIEdhdGV3YXkgU3lzdGVtLCBkZW4gRUNVcyBNb3RvcnN0ZXVlcnVuZyB1bmQgQW56ZWlnZSwgZWluZW0gU2Vuc29yIE1vdG9yVGVtcGVyYXR1cmUgdW5kIGVpbmVtIEFrdG9yIE1vdG9yVmFsdmUuIE1vdG9yVGVtcGVyYXR1cmUgd2lyZCB2b24gTW90b3JzdGV1ZXJ1bmcgYXVzZ2V3ZXJ0ZXQuIE1vdG9yc3RldWVydW5nIHN0ZXVlcnQgTW90b3JWYWx2ZS4gQ29udHJvbGxlcnN0YXR1cyBibGVpYnQgYmlzIHp1ciBBdXN3YWhsIGtvbmtyZXRlciBFbXBmw6RuZ2VyIHVuZCBTaWduYWxlIGludGVybi4gUHLDvGZlIHVuZCBhcmJlaXRlIGJpcyBEYXRhIFNjaWVuY2UgJiBJbnRlbGxpZ2VuY2UuXFxuQ0FOLUZEOiA1MDAga2JpdC9zIGFyYml0cmF0aW9uLCAyIE1iaXQvcyBkYXRhXFxuQ0FOOiA1MDAga2JpdC9zJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1dlaXRlcmUgSGlud2Vpc2UnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwoJy0gQWt0b3ItQmVmZWhsZToge1wiTW90b3JWYWx2ZVwiOntcImxlbmd0aF9iaXRzXCI6MSxcImRhdGFfdHlwZVwiOlwiYm9vbGVhblwiLFwiZmFjdG9yXCI6MSxcInVuaXRcIjpcImNvZGVcIixcIm1pbl92YWx1ZVwiOjAsXCJtYXhfdmFsdWVcIjoxLFwic2VtYW50aWNcIjp7XCJzZW1hbnRpY190eXBlXCI6XCJCT09MRUFOXCJ9LFwiZGF0YVwiOntcImVudW1fdmFsdWVzXCI6e1wiQ0xPU0VcIjowLFwiT1BFTlwiOjF9fX19Jyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ0dlcsOkdGV1bWZhbmcnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgZm9yIChjb25zdCBbbGFiZWwsIHZhbHVlXSBvZiBbWydHYXRld2F5cycsICcxJ10sIFsnQ29udHJvbGxlcicsICcyJ10sIFsnU2Vuc29yZW4nLCAnMSddLCBbJ0FrdG9yZW4nLCAnMSddXSkgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoYCR7bGFiZWx9OiB2ZXJiaW5kbGljaGUgQW56YWhsYCwgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHZhbHVlKTtcclxuICBjb25zdCBzdGFydFJlcXVlc3QgPSBwYWdlLndhaXRGb3JSZXF1ZXN0KHJlcXVlc3QgPT4gcmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JylcclxuICAgICYmIHJlcXVlc3QubWV0aG9kKCkgPT09ICdQT1NUJyAmJiByZXF1ZXN0LnBvc3REYXRhSlNPTigpPy53aXphcmRfY29tbWFuZD8uYWN0aW9uID09PSAnU1RBUlQnKTtcclxuICAvLyBVc2UgdGhlIHNhbWUgdmlzaWJsZSBxdWVzdGlvbm5haXJlIG5hdmlnYXRpb24gYSB1c2VyIHVzZXM7IG5ldmVyIGluamVjdCBnZW5lcmF0ZWQgbW9kZWwgcm93cy5cclxuICBmb3IgKGxldCBzdGVwID0gMDsgc3RlcCA8IDEwOyBzdGVwKyspIHtcclxuICAgIGNvbnN0IHN1Ym1pdCA9IGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJyk7XHJcbiAgICBhd2FpdCBleHBlY3Qoc3VibWl0KS50b0JlRW5hYmxlZCgpO1xyXG4gICAgY29uc3QgbmFtZSA9IGF3YWl0IHN1Ym1pdC5pbm5lclRleHQoKTtcclxuICAgIGF3YWl0IHN1Ym1pdC5jbGljaygpO1xyXG4gICAgaWYgKG5hbWUgPT09ICfDnGJlcm5laG1lbicpIGJyZWFrO1xyXG4gICAgaWYgKHN0ZXAgPT09IDkpIHRocm93IG5ldyBFcnJvcignUXVlc3Rpb25uYWlyZSBkaWQgbm90IG9mZmVyIHN1Ym1pdC4nKTtcclxuICB9XHJcbiAgY29uc3QgcmVxdWVzdGVkID0gKGF3YWl0IHN0YXJ0UmVxdWVzdCkucG9zdERhdGFKU09OKCkud2l6YXJkX2NvbW1hbmQud2l6YXJkX2NvbnRleHQ7XHJcbiAgZXhwZWN0KHJlcXVlc3RlZC50ZWNobm9sb2dpZXMsICdBbiBleHBsaWNpdCBDQU4tRkQgdGFzayBtdXN0IG5vdCBzaWxlbnRseSByZXF1ZXN0IExJTiBhbmQgU09NRS9JUC4nKS50b0VxdWFsKFsnQ0FOLUZEIChjYW5fZmQpJ10pO1xyXG4gIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgdHJ1ZSxcclxuICAgIFsnU3lzdGVtJywgJ01vdG9yc3RldWVydW5nJywgJ0FuemVpZ2UnLCAnTW90b3JUZW1wZXJhdHVyZScsICdNb3RvclZhbHZlJ10pO1xyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCA1KTtcclxuICBleHBlY3QoYXJ0aWZhY3RzLmFzc2Vzc21lbnQub2JzZXJ2ZWRfc2lnbmFsX2NvdW50KS50b0JlR3JlYXRlclRoYW5PckVxdWFsKDMpO1xyXG4gIGV4cGVjdChhcnRpZmFjdHMuYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS50cmFuc3BvcnRfZXhjbHVzaW9ucykudG9IYXZlTGVuZ3RoKDMpO1xyXG4gIGNvbnN0IGZpbmlzaGVkID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4gcmVzcG9uc2UudXJsKCkuaW5jbHVkZXMoYC9ydW5zLyR7Y29udGludWl0eS5ydW5JZH0vZmluaXNoYClcclxuICAgICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdGZXJ0aWcgc3RlbGxlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgZXhwZWN0KChhd2FpdCBmaW5pc2hlZCkub2soKSkudG9CZSh0cnVlKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nKS5ub3QudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icykudG9IYXZlTGVuZ3RoKDEpO1xyXG4gIGV4cGVjdChlcnJvcnMpLnRvRXF1YWwoW10pO1xyXG4gIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgLi4uY29udGludWl0eSwgLi4uYXJ0aWZhY3RzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuXHJcbmZvciAoY29uc3QgdGVjaG5vbG9neSBvZiBbJ0kyQycsICdNb2RidXMgUlRVJ10pIHtcclxuICB0ZXN0KGBSYXNwYmVycnkgUGkgJHt0ZWNobm9sb2d5fSBwcm9qZWN0IHJldGFpbnMgbW9kZWwgYW5kIHJlcXVlc3RzIG1pc3NpbmcgY2FwYWNpdHkgZXZpZGVuY2UgQG5vbmF1dG9tb3RpdmVgLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtZW1iZWRkZWQtJyArIHJhbmRvbVVVSUQoKTtcclxuICAgIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cubG9jYXRvcignI2VuZ2luZWVyaW5nLXByb2plY3QtbmFtZScpLmZpbGwoJ1RlbXBlcmF0dXJyZWdlbHVuZycpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwodGVjaG5vbG9neSA9PT0gJ0kyQydcclxuICAgICAgPyAnMiBBa3RvcmVuIGbDvHIgVmVudGlsZSwgNCBTZW5zb3JlbiBmw7xyIFRlbXBlcmF0dXJlbiwgdW5kIGVpbiBSYXNwYmVycnlQaSdcclxuICAgICAgOiBgMiBBa3RvcmVuIGbDvHIgVmVudGlsZSwgNCBTZW5zb3JlbiBmw7xyIFRlbXBlcmF0dXJlbiwgdW5kIGVpbiBSYXNwYmVycnlQaS4gRW1iZWRkZWQgU3lzdGVtcy4gQWxsZSBHZXLDpHRlIGtvbW11bml6aWVyZW4gw7xiZXIgJHt0ZWNobm9sb2d5fS4gUHLDvGZlIHVuZCBhcmJlaXRlIGJpcyBEYXRhIFNjaWVuY2UgJiBJbnRlbGxpZ2VuY2UuYCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnTmV0emFyY2hpdGVrdHVyJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgncmFkaW8nLCB7IG5hbWU6IC9WYXJpYW50ZSAwLyB9KS5jaGVjaygpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ0dlcsOkdGV1bWZhbmcnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBpZiAodGVjaG5vbG9neSA9PT0gJ0kyQycpIHtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUmFzcGJlcnJ5UGk6IEFuc2NobHVzcycsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdJMkMnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeUxhYmVsKCdUZW1wZXJhdHVyc2Vuc29yMTogQW5zY2hsdXNzJywgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoJycpO1xyXG4gICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICAgIGZvciAoY29uc3QgbmFtZSBvZiBbJ1Jhc3BiZXJyeVBpJywgJ1RlbXBlcmF0dXJzZW5zb3IxJywgJ1RlbXBlcmF0dXJzZW5zb3IyJywgJ1RlbXBlcmF0dXJzZW5zb3IzJywgJ1RlbXBlcmF0dXJzZW5zb3I0JywgJ1ZlbnRpbGFrdG9yMScsICdWZW50aWxha3RvcjInXSkge1xyXG4gICAgICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKGAke25hbWV9OiBBbnNjaGx1c3NgLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignSTJDJyk7XHJcbiAgICAgIH1cclxuICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1NlbnNvciAxOiBNZXNzZ3LDtsOfZScsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdzcGVlZCcpO1xyXG4gICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5TGFiZWwoJ1RlbXBlcmF0dXJzZW5zb3IxOiBBbnNjaGx1c3MnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZSgnSTJDJyk7XHJcbiAgICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdTZW5zb3IgMTogTWVzc2dyw7bDn2UnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbigndGVtcGVyYXR1cmUnKTtcclxuICAgIH1cclxuICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdWZW50aWxha3RvcjE6IFN0ZWxsYmVmZWhsJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ09QRU5fQ0xPU0UnKTtcclxuICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlMYWJlbCgnVmVudGlsYWt0b3IyOiBTdGVsbGJlZmVobCcsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZVZhbHVlKCcnKTtcclxuICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdWZW50aWxha3RvcjI6IFN0ZWxsYmVmZWhsJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ09QRU5fQ0xPU0UnKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGV4cGVjdChjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgdHJ1ZSwgWydSYXNwYmVycnlQaScsICdUZW1wZXJhdHVyc2Vuc29yMScsICdUZW1wZXJhdHVyc2Vuc29yMicsICdUZW1wZXJhdHVyc2Vuc29yMycsICdUZW1wZXJhdHVyc2Vuc29yNCcsICdWZW50aWxha3RvcjEnLCAnVmVudGlsYWt0b3IyJ10sIGZhbHNlLCB1bmRlZmluZWQsIHVuZGVmaW5lZCwgdHJ1ZSkpXHJcbiAgICAgIC5yZWplY3RzLnRvVGhyb3coL1dpemFyZCBCTE9DS0VEIGF0IHBhcmFtZXRlcnM6LipiZXN0w6R0aWd0ZSBBbmdhYmVuLyk7XHJcbiAgICBjb25zdCB3b3JrZmxvdyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93Jyk7XHJcbiAgICBjb25zdCBmaW5kaW5ncyA9IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLmJsb2NraW5nX2ZpbmRpbmdzIGFzIHsgY29kZTogc3RyaW5nIH1bXTtcclxuICAgIGV4cGVjdChmaW5kaW5ncy5tYXAoaXRlbSA9PiBpdGVtLmNvZGUpKS50b0NvbnRhaW4oJ1RFQ0hOT0xPR1lfUEFSQU1FVEVSX01JU1NJTkcnKTtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5zdGF0dXNlcy5wYXJhbWV0ZXJzKS50b0JlKCdJTl9QUk9HUkVTUycpO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LmFydGlmYWN0X2NoZWNrcy5wYXJhbWV0ZXJzLmNvbXBsZXRlKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IHJlcXVpcmVkID0gd29ya2Zsb3cuYXJ0aWZhY3RfY2hlY2tzLnBhcmFtZXRlcnMucmVxdWlyZWQ7XHJcbiAgICBleHBlY3QocmVxdWlyZWRbdGVjaG5vbG9neSA9PT0gJ0kyQycgPyAnaTJjX2RldmljZV9zb3VyY2UnIDogJ21yX2RldmljZV9zb3VyY2UnXSkudG9CZShmYWxzZSk7XHJcbiAgICBjb25zdCBldmlkZW5jZVJldmlldyA9IGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHtuYW1lOiAnQmxvY2tpZXJlbmRlIFByZWZsaWdodC1CZWZ1bmRlJ30pO1xyXG4gICAgYXdhaXQgZXhwZWN0KGV2aWRlbmNlUmV2aWV3KS50b0NvbnRhaW5UZXh0KHRlY2hub2xvZ3kgPT09ICdJMkMnID8gJ2kyY19kZXZpY2Vfc291cmNlJyA6ICdtcl9kZXZpY2Vfc291cmNlJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZXZpZGVuY2VSZXZpZXcuZ2V0QnlSb2xlKCdsaW5rJywge25hbWU6ICdCZXRyb2ZmZW5lIEFuZ2FiZW4gYmVhcmJlaXRlbid9KS5maXJzdCgpKVxyXG4gICAgICAudG9IYXZlQXR0cmlidXRlKCdocmVmJywgbmV3IFJlZ0V4cChgbW9kZT1wYXJhbWV0ZXJzLipwcm9qZWN0PSR7cHJvamVjdH1gKSk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuc3RhdHVzZXMuc2ltdWxhdGlvbikudG9CZSgnRU1QVFknKTtcclxuICAgIGlmICh0ZWNobm9sb2d5ID09PSAnSTJDJykge1xyXG4gICAgICBleHBlY3Qod29ya2Zsb3cucGFyYW1ldGVycy5yYXRlX3Jldmlld19wcm9wb3NhbHMuaTJjLnN0YXR1cykudG9CZSgnUkVWSUVXX1JFUVVJUkVEJyk7XHJcbiAgICAgIGV4cGVjdCh3b3JrZmxvdy5wYXJhbWV0ZXJzLnBhcmFtZXRlcl9wcm92ZW5hbmNlLmJpdHJhdGUuc291cmNlKS50b0JlKCdURUNITk9MT0dZX1BST0ZJTEVfUkVWSUVXX1BST1BPU0FMJyk7XHJcbiAgICB9XHJcbiAgICBjb25zdCBpbnRlcmZhY2VzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtaW50ZXJmYWNlcycpO1xyXG4gICAgZXhwZWN0KGludGVyZmFjZXMubGVuZ3RoKS50b0JlR3JlYXRlclRoYW5PckVxdWFsKDcpO1xyXG4gICAgZXhwZWN0KGludGVyZmFjZXMuZXZlcnkoaXRlbSA9PiAhL2F1dG9tb3RpdmV8Y2FufGxpbi9pLnRlc3QoaXRlbS50ZWNobm9sb2d5KSkpLnRvQmUodHJ1ZSk7XHJcbiAgICBjb25zdCBoYXJkd2FyZSA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgICBleHBlY3QoaGFyZHdhcmUuZXZlcnkoaXRlbSA9PiBpdGVtLmRvbWFpbiAhPT0gJ2F1dG9tb3RpdmUnKSkudG9CZSh0cnVlKTtcclxuICAgIGlmICh0ZWNobm9sb2d5ID09PSAnSTJDJykge1xyXG4gICAgICBjb25zdCBzaWduYWxzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnc2lnbmFscycpO1xyXG4gICAgICBleHBlY3Qoc2lnbmFscy5zb21lKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnVGVtcGVyYXR1cl9UZW1wZXJhdHVyc2Vuc29yMScgJiYgaXRlbS51bml0ID09PSAnZGVnQycpKS50b0JlKHRydWUpO1xyXG4gICAgfVxyXG4gICAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzKS50b0hhdmVMZW5ndGgoMCk7XHJcbiAgICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ25vbmF1dG9tb3RpdmUtZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgdGVjaG5vbG9neSwgZmluZGluZ3MgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgfSk7XHJcbn1cclxuXHJcbnRlc3QoJ2V4YWN0IGNvbmZpcm1lZCA1MC8yNTAvMjUwIHJlcXVlc3QgY29tcGxldGVzIHRocm91Z2ggcmVhbCB3aXphcmQgcmV2aWV3IEBsYXJnZScsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICBjb25zdCBlcnJvcnM6IHN0cmluZ1tdID0gW107IHBhZ2Uub24oJ3BhZ2VlcnJvcicsIGVycm9yID0+IGVycm9ycy5wdXNoKGVycm9yLm1lc3NhZ2UpKTtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtbGFyZ2UtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBydW5JZCA9IHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBvcmlnaW5hbCA9IGF3YWl0IHJlYWRGaWxlKG5ldyBVUkwoJy4vZml4dHVyZXMvd2l6YXJkLWxhcmdlLTUwLTI1MC0yNTAudHh0JywgaW1wb3J0Lm1ldGEudXJsKSwgJ3V0ZjgnKTtcclxuICBjb25zdCBtZXRhZGF0YSA9IEpTT04ucGFyc2UoYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2UtNTAtMjUwLTI1MC5qc29uJywgaW1wb3J0Lm1ldGEudXJsKSwgJ3V0ZjgnKSk7XHJcbiAgY29uc3QgYmFzZWxpbmUgPSBKU09OLnBhcnNlKGF3YWl0IHJlYWRGaWxlKG5ldyBVUkwoJy4vZml4dHVyZXMvd2l6YXJkLWxhcmdlLXNpZ25hbC1jb250cmFjdHMuanNvbicsIGltcG9ydC5tZXRhLnVybCksICd1dGY4JykpO1xyXG4gIGNvbnN0IHByb21wdCA9IG9yaWdpbmFsLnJlcGxhY2UoL14tIExhdWYtSUQ6LiokL20sICctIExhdWYtSUQ6ICcgKyBydW5JZCk7XHJcbiAgYXdhaXQgcmV2aWV3VmlydHVhbFRyYW5zcG9ydHMocGFnZSwgcHJvamVjdCk7XHJcbiAgLy8gUmVwbGF5IHRoZSBjYXB0dXJlZCwgYWxyZWFkeSBjb25maXJtZWQgaW5wdXQgdGhyb3VnaCB0aGUgbm9ybWFsIFNUQVJUIEFQSS5cclxuICAvLyBBbGwgcHJvcG9zYWwgaW5zcGVjdGlvbiwgYXBwcm92YWwsIGNvbnRpbnVhdGlvbiBhbmQgcmVsb2FkcyBiZWxvdyB1c2UgVUkuXHJcbiAgY29uc3Qgc3RhcnRlZCA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NoYXQnLCB7XHJcbiAgICBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0sIHRpbWVvdXQ6IDI0MF8wMDAsXHJcbiAgICBkYXRhOiB7IHByb21wdCwgd2l6YXJkX2NvbW1hbmQ6IHsgYWN0aW9uOiAnU1RBUlQnLCBydW5faWQ6IHJ1bklkLCBvcGVyYXRpb25faWQ6IHJhbmRvbVVVSUQoKSxcclxuICAgICAgdGFyZ2V0OiAnZGF0YV9zY2llbmNlX2ludGVsbGlnZW5jZScsIHdpemFyZF9jb250ZXh0OiB7IC4uLm1ldGFkYXRhLndpemFyZF9jb250ZXh0LCBwcm9qZWN0X2lkOiBwcm9qZWN0LCBydW5faWQ6IHJ1bklkIH0gfSB9LFxyXG4gIH0pO1xyXG4gIGlmICghc3RhcnRlZC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYEhUVFAgJHtzdGFydGVkLnN0YXR1cygpfTogJHsoYXdhaXQgc3RhcnRlZC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCBmYWxzZSwgW10sIHRydWUsIGJhc2VsaW5lLnNpZ25hbHMpO1xyXG4gIGV4cGVjdChjb250aW51aXR5LnJ1bklkKS50b0JlKHJ1bklkKTtcclxuICBjb25zdCBoYXJkd2FyZSA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgZXhwZWN0KGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0uZGV2aWNlX3R5cGUgPT09ICdTZW5zb3JDb250cm9sbGVyJykpLnRvSGF2ZUxlbmd0aCgyNTApO1xyXG4gIGV4cGVjdChoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLmRldmljZV90eXBlID09PSAnQWN0dWF0b3JDb250cm9sbGVyJykpLnRvSGF2ZUxlbmd0aCgyNTApO1xyXG4gIGV4cGVjdChoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLmRldmljZV90eXBlID09PSAnRUNVJykubGVuZ3RoKS50b0JlR3JlYXRlclRoYW5PckVxdWFsKDUwKTtcclxuICBjb25zdCBhcnRpZmFjdHMgPSBhd2FpdCB2ZXJpZnlBcnRpZmFjdHMocGFnZSwgcHJvamVjdCwgMTQwNCk7XHJcbiAgY29uc3QgZXhjbHVkZWRTaWduYWxJZHMgPSBuZXcgU2V0KGFydGlmYWN0cy5hc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnRyYW5zcG9ydF9leGNsdXNpb25zXHJcbiAgICAuZmxhdE1hcCgoaXRlbTogeyBzaWduYWxfaWRzOiBzdHJpbmdbXSB9KSA9PiBpdGVtLnNpZ25hbF9pZHMpKTtcclxuICBleHBlY3QoZXhjbHVkZWRTaWduYWxJZHMuc2l6ZSkudG9CZSgyMzUpO1xyXG4gIGV4cGVjdChhcnRpZmFjdHMuYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQpLnRvQmUoMTE2OSk7XHJcbiAgYXdhaXQgdmVyaWZ5U2lnbmFsQ29udHJhY3RzKHBhZ2UsIHByb2plY3QsIGJhc2VsaW5lLnNpZ25hbHMpO1xyXG4gIGV4cGVjdChhcnRpZmFjdHMuam9iKS50b0JlKGNvbnRpbnVpdHkucmVzdGFydGVkSm9iSWQpO1xyXG4gIGV4cGVjdChlcnJvcnMpLnRvRXF1YWwoW10pO1xyXG4gIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgZml4dHVyZTogbWV0YWRhdGEucmVxdWVzdF9zaGEyNTYsIC4uLmNvbnRpbnVpdHksIC4uLmFydGlmYWN0cyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxufSk7XHJcblxyXG50ZXN0KCdhIHJlYWwgQU1FTkQgYWZ0ZXIgbW9kZWwgYXBwcm92YWwgYWRkcyB0aGUgcmVxdWVzdGVkIHNlbnNvciBhbmQgcmV1c2VzIGl0cyBuZXR3b3JrcyBAYW1lbmQnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWFtZW5kLScgKyByYW5kb21VVUlEKCk7XHJcbiAgYXdhaXQgcmV2aWV3VmlydHVhbFRyYW5zcG9ydHMocGFnZSwgcHJvamVjdCk7XHJcbiAgY29uc3QgcnVuSWQgPSByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgZ3JhcGggPSBbXHJcbiAgICB7IGNsdXN0ZXJfaWQ6ICdkcml2ZScsIG5ldHdvcmtfaWQ6ICdjYW5fZmQnLCBuZXR3b3JrX2xhYmVsOiAnQ0FOLUZEJywgYnVzX25hbWU6ICdEcml2ZScsXHJcbiAgICAgIGNvbnRyb2xsZXJzOiBbeyBlY3U6ICdNb3RvcnN0ZXVlcnVuZycsIHNlbnNvcnM6IFtdIGFzIHN0cmluZ1tdLCBhY3R1YXRvcnM6IFtdIH1dLFxyXG4gICAgICBobWlfcm91dGVzOiBbeyBzb3VyY2U6ICdNb3RvcnN0ZXVlcnVuZycsIHRhcmdldDogJ0FuemVpZ2UnIH0sIHsgc291cmNlOiAnQW56ZWlnZScsIHRhcmdldDogJ01vdG9yc3RldWVydW5nJyB9LFxyXG4gICAgICAgIHsgc291cmNlOiAnU3lzdGVtJywgdGFyZ2V0OiAnQW56ZWlnZScgfV0gfSxcclxuICAgIHsgY2x1c3Rlcl9pZDogJ2Rpc3BsYXknLCBuZXR3b3JrX2lkOiAnZXRoZXJuZXQnLCBuZXR3b3JrX2xhYmVsOiAnRXRoZXJuZXQnLCBidXNfbmFtZTogJ0Rpc3BsYXknLFxyXG4gICAgICBjb250cm9sbGVyczogW3sgZWN1OiAnQW56ZWlnZScsIHNlbnNvcnM6IFtdIGFzIHN0cmluZ1tdLCBhY3R1YXRvcnM6IFtdIH1dIH0sXHJcbiAgXTtcclxuICBjb25zdCBwcm9tcHQgPSBgU3RydWt0dXJpZXJ0ZSBWb3JnYWJlbiBmdWVyIGRlbiBFbmdpbmVlcmluZy1BZ2VudGVuOlxyXG4tIExhdWYtSUQ6ICR7cnVuSWR9XHJcbi0gSW5kdXN0cmllOiBBdXRvbW90aXZlXHJcbi0gTmV0endlcmt0ZWNobm9sb2dpZW46IENBTi1GRCAoY2FuX2ZkKTsgRXRoZXJuZXQgKGV0aGVybmV0KVxyXG5DQU4tRkQ6IDUwMCBrYml0L3MgYXJiaXRyYXRpb24sIDIgTWJpdC9zIGRhdGFcclxuQ0FOOiA1MDAga2JpdC9zXHJcbkV0aGVybmV0OiAxMDAgTWJpdC9zXHJcbi0gSGFyZHdhcmUtU29sbHdlcnRlOiB7XCJnYXRld2F5c1wiOjEsXCJlY3VzXCI6MixcInNlbnNvcnNcIjowLFwiYWN0dWF0b3JzXCI6MH1cclxuLSBTeXN0ZW1jbHVzdGVyLUdyYXBoOiAke0pTT04uc3RyaW5naWZ5KGdyYXBoKX1cclxuS29ua3JldGUgQXVmZ2FiZSBkZXMgTnV0emVycywgcGVyIFdpemFyZC1VZWJlcm5laG1lbiBiZXN0YWV0aWd0OlxyXG5Nb3RvcnN0ZXVlcnVuZyB1bmQgQW56ZWlnZSBtaXQgZWluZW0gemVudHJhbGVuIEdhdGV3YXkgU3lzdGVtIHZlcmJpbmRlbi5gO1xyXG4gIGNvbnN0IHN0YXJ0ZWQgPSBhd2FpdCBwYWdlLnJlcXVlc3QucG9zdCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jaGF0Jywge1xyXG4gICAgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiAxMjBfMDAwLFxyXG4gICAgZGF0YTogeyBwcm9tcHQsIHdpemFyZF9jb21tYW5kOiB7IGFjdGlvbjogJ1NUQVJUJywgcnVuX2lkOiBydW5JZCwgb3BlcmF0aW9uX2lkOiByYW5kb21VVUlEKCksXHJcbiAgICAgIHRhcmdldDogJ2RhdGFfc2NpZW5jZV9pbnRlbGxpZ2VuY2UnLCB3aXphcmRfY29udGV4dDogeyBwcm9qZWN0X2lkOiBwcm9qZWN0LCBydW5faWQ6IHJ1bklkLFxyXG4gICAgICAgIHByb2plY3RfbmFtZTogJ0UyRSBhbWVuZG1lbnQnLCBzY29wZV9pZHM6IHN0ZXBzLCBtb2RlOiAnZnVsbCcsXHJcbiAgICAgICAgcHJvY2Vzc19pZHM6IFsnZGVmYXVsdHMnLCAncmV2aWV3X2dhdGUnLCAnYXBwcm92ZV9hZnRlcl9hbGxvdyddLCB0YXNrOiAnTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UgYW4gU3lzdGVtJyB9IH0gfSxcclxuICB9KTtcclxuICBpZiAoIXN0YXJ0ZWQub2soKSkgdGhyb3cgbmV3IEVycm9yKGBIVFRQICR7c3RhcnRlZC5zdGF0dXMoKX06ICR7KGF3YWl0IHN0YXJ0ZWQudGV4dCgpKS5zbGljZSgwLCA0MDAwKX1gKTtcclxuICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGxldCBvcmlnaW5hbE5ldHdvcmtzOiBzdHJpbmdbXSA9IFtdO1xyXG4gIGNvbnN0IGFtZW5kID0gYXN5bmMgKCkgPT4ge1xyXG4gICAgb3JpZ2luYWxOZXR3b3JrcyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpKS5wYXJhbWV0ZXJzLm5ldHdvcmtzXHJcbiAgICAgIC5tYXAoKGl0ZW06IHsgaWQ6IHN0cmluZyB9KSA9PiBpdGVtLmlkKS5zb3J0KCk7XHJcbiAgICBleHBlY3Qob3JpZ2luYWxOZXR3b3JrcykudG9IYXZlTGVuZ3RoKDIpO1xyXG4gICAgZ3JhcGhbMF0uY29udHJvbGxlcnNbMF0uc2Vuc29ycy5wdXNoKCdNb3RvclRlbXBlcmF0dXJlJyk7XHJcbiAgICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pO1xyXG4gICAgY29uc3QgZXhwYW5kID0gZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgICBhd2FpdCBleHBlY3QoZXhwYW5kKS50b0JlRW5hYmxlZCh7IHRpbWVvdXQ6IDEyMF8wMDAgfSk7XHJcbiAgICBhd2FpdCBleHBhbmQuY2xpY2soKTtcclxuICAgIGNvbnN0IGZpZWxkID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcmfDpG56ZW4nLCBleGFjdDogdHJ1ZSB9KS5nZXRCeVJvbGUoJ3RleHRib3gnKTtcclxuICAgIGF3YWl0IGZpZWxkLmZpbGwoJ0VyZ8OkbnplIE1vdG9yVGVtcGVyYXR1cmUgYWxzIFNlbnNvciBkZXIgTW90b3JzdGV1ZXJ1bmcuIERpZSB2b2xsc3TDpG5kaWdlIGFrdHVhbGlzaWVydGUgRnJlaWdhYmUgbGF1dGV0OlxcbidcclxuICAgICAgKyAnLSBIYXJkd2FyZS1Tb2xsd2VydGU6IHtcImdhdGV3YXlzXCI6MSxcImVjdXNcIjoyLFwic2Vuc29yc1wiOjEsXCJhY3R1YXRvcnNcIjowfVxcbidcclxuICAgICAgKyAnLSBTeXN0ZW1jbHVzdGVyLUdyYXBoOiAnICsgSlNPTi5zdHJpbmdpZnkoZ3JhcGgpKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8Okbnp1bmcgYW5hbHlzaWVyZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGZpZWxkKS5ub3QudG9CZVZpc2libGUoeyB0aW1lb3V0OiAxMjBfMDAwIH0pO1xyXG4gIH07XHJcbiAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCBmYWxzZSwgWydNb3RvcnN0ZXVlcnVuZycsICdBbnplaWdlJ10sIGZhbHNlLCB1bmRlZmluZWQsIGFtZW5kKTtcclxuICBjb25zdCBoYXJkd2FyZSA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgY29uc3Qgb3duZXIgPSBoYXJkd2FyZS5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnTW90b3JzdGV1ZXJ1bmcnKTtcclxuICBjb25zdCBzZW5zb3JzID0gaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnTW90b3JUZW1wZXJhdHVyZScpO1xyXG4gIGV4cGVjdChzZW5zb3JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KHNlbnNvcnNbMF0uaWRlbnRpdHkuc3lzdGVtX293bmVyX2lkKS50b0JlKG93bmVyLmlkKTtcclxuICBjb25zdCBzZW5zb3JOZXR3b3JrID0gJ0RyaXZlLUlPLW1vdG9yc3RldWVydW5nLWNhbi1mZC1TMDEnO1xyXG4gIGNvbnN0IG5ldHdvcmtzID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93JykpLnBhcmFtZXRlcnMubmV0d29ya3M7XHJcbiAgZXhwZWN0KG5ldHdvcmtzLm1hcCgoaXRlbTogeyBpZDogc3RyaW5nIH0pID0+IGl0ZW0uaWQpLnNvcnQoKSkudG9FcXVhbChbLi4ub3JpZ2luYWxOZXR3b3Jrcywgc2Vuc29yTmV0d29ya10uc29ydCgpKTtcclxuICBleHBlY3QobmV3IFNldChuZXR3b3Jrcy5tYXAoKGl0ZW06IHsgbmFtZTogc3RyaW5nIH0pID0+IGl0ZW0ubmFtZSkpLnNpemUpLnRvQmUobmV0d29ya3MubGVuZ3RoKTtcclxuICBjb25zdCB0b3BvbG9neSA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9uZXR3b3JrLXZpZXcnKSkudG9wb2xvZ3k7XHJcbiAgY29uc3QgbG9jYWxFZGdlID0gdG9wb2xvZ3kuZWRnZXMuZmluZCgoZWRnZTogYW55KSA9PiBlZGdlLnBoeXNpY2FsTmV0d29ya0lkID09PSBzZW5zb3JOZXR3b3JrKTtcclxuICBleHBlY3QobG9jYWxFZGdlKS50b0JlVHJ1dGh5KCk7XHJcbiAgZXhwZWN0KGxvY2FsRWRnZS5idXMpLnRvQmUoJ2Nhbl9mZCcpO1xyXG4gIGV4cGVjdChPYmplY3QudmFsdWVzKGxvY2FsRWRnZS5yb3V0aW5nTWV0YWRhdGEpKS50b0NvbnRhaW5FcXVhbChleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7XHJcbiAgICBzb3VyY2U6IHNlbnNvcnNbMF0uaWQsIHRhcmdldDogb3duZXIuaWQsIGFwcHJvdmFsU3RhdGU6ICdBUFBST1ZFRCcsIHByb3RvY29sOiAnQ0FOX0ZEJyxcclxuICB9KSk7XHJcbiAgZm9yIChjb25zdCBbc2lkZSwgaGFyZHdhcmVJZF0gb2YgW1snc291cmNlJywgc2Vuc29yc1swXS5pZF0sIFsndGFyZ2V0Jywgb3duZXIuaWRdXSkge1xyXG4gICAgY29uc3Qgbm9kZSA9IHRvcG9sb2d5Lm5vZGVzLmZpbmQoKGl0ZW06IGFueSkgPT4gaXRlbS5pZCA9PT0gbG9jYWxFZGdlW3NpZGVdKTtcclxuICAgIGV4cGVjdChub2RlLmVuZ2luZWVyaW5nSWQpLnRvQmUoaGFyZHdhcmVJZCk7XHJcbiAgICBleHBlY3Qobm9kZS5wb3J0cykudG9Db250YWluRXF1YWwoZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoeyBpZDogbG9jYWxFZGdlW3NpZGUgKyAnUG9ydCddLFxyXG4gICAgICBidXM6ICdjYW5fZmQnLCBwaHlzaWNhbE5ldHdvcmtJZDogc2Vuc29yTmV0d29yayB9KSk7XHJcbiAgfVxyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCAxKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2FtZW5kbWVudC1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCAuLi5jb250aW51aXR5LCAuLi5hcnRpZmFjdHMgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG5cclxuLy8gUmVhbCBpc29sYXRlZCBVSSAtPiBwZXJzaXN0ZWQgbW9kZWwgYm91bmRhcnkgcmVncmVzc2lvbiwgbm90IG5pbmUtc3RhZ2UgY29tcGxldGlvbiBwcm9vZi5cclxudGVzdCgncmV2aWV3YWJsZSBmdW5jdGlvbmFsIFRYL1JYIE9GRiBzdXJ2aXZlcyByZXF1ZXN0IHJlbG9hZCBhbmQgY2Fub25pY2FsIG1vZGVsIGFkb3B0aW9uIEB0eHJ4JywgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS10eHJ4LScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdUWCBSWCBmdW5jdGlvbmFsIHBhcnRuZXJzJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwoJ0VyemV1Z2UgZWluIEF1dG9tb3RpdmUgQ0FOLUZEIE5ldHp3ZXJrIG1pdCBlaW5lbSBHYXRld2F5IFN5c3RlbSB1bmQgZGVuIEVDVXMgTW90b3JzdGV1ZXJ1bmcsIEdldHJpZWJlc3RldWVydW5nIHVuZCBFbGVrdHJvbW90b3JzdGV1ZXJ1bmcuIERpZSBiZXJlY2huZXRlbiBGdW5rdGlvbnNhdXNnw6RuZ2UgZGllbmVuIGRlciBBbnRyaWVic2tvb3JkaW5hdGlvbi4gQ29udHJvbGxlcnN0YXR1cyBibGVpYnQgaW50ZXJuLlxcbkNBTi1GRDogNTAwIGtiaXQvcyBhcmJpdHJhdGlvbiwgMiBNYml0L3MgZGF0YScpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdHZXLDpHRldW1mYW5nJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1dG9tb3RpdmUgLyBWZWhpY2xlIMO8YmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBmb3IgKGNvbnN0IFtsYWJlbCwgdmFsdWVdIG9mIFtbJ0dhdGV3YXlzJywgJzEnXSwgWydDb250cm9sbGVyJywgJzMnXSwgWydTZW5zb3JlbicsICcwJ10sIFsnQWt0b3JlbicsICcwJ11dKSBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbChgJHtsYWJlbH06IHZlcmJpbmRsaWNoZSBBbnphaGxgLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwodmFsdWUpO1xyXG4gIGNvbnN0IHR4cnggPSBkaWFsb2cubG9jYXRvcignZGV0YWlscycpLmZpbHRlcih7IGhhczogcGFnZS5sb2NhdG9yKCdzdW1tYXJ5JykuZmlsdGVyKHsgaGFzVGV4dDogL15UWFxcL1JYLyB9KSB9KS5maXJzdCgpO1xyXG4gIGF3YWl0IGV4cGVjdCh0eHJ4KS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IHR4cngubG9jYXRvcignc3VtbWFyeScpLmNsaWNrKCk7XHJcbiAgY29uc3Qgc2VsZWN0ZWQgPSB0eHJ4LmdldEJ5Um9sZSgnc3dpdGNoJywgeyBuYW1lOiAnTW90b3JEcmVobW9tZW50SXN0IOKGkiBHZXRyaWViZXN0ZXVlcnVuZycsIGV4YWN0OiB0cnVlIH0pO1xyXG4gIGF3YWl0IGV4cGVjdChzZWxlY3RlZCkudG9CZUNoZWNrZWQoKTsgYXdhaXQgc2VsZWN0ZWQudW5jaGVjaygpO1xyXG4gIGNvbnN0IHN0YXJ0UmVxdWVzdCA9IHBhZ2Uud2FpdEZvclJlcXVlc3QocmVxdWVzdCA9PiByZXF1ZXN0LnVybCgpLmVuZHNXaXRoKCcvYXBpL2FnZW50L2NoYXQnKSAmJiByZXF1ZXN0Lm1ldGhvZCgpID09PSAnUE9TVCcgJiYgcmVxdWVzdC5wb3N0RGF0YUpTT04oKT8ud2l6YXJkX2NvbW1hbmQ/LmFjdGlvbiA9PT0gJ1NUQVJUJyk7XHJcbiAgZm9yIChsZXQgc3RlcCA9IDA7IHN0ZXAgPCAxMDsgc3RlcCsrKSB7XHJcbiAgICBjb25zdCBidXR0b24gPSBkaWFsb2cubG9jYXRvcignLmVuZy1hZ2VudC1xdWVzdGlvbm5haXJlLWhlYWQnKS5nZXRCeVJvbGUoJ2J1dHRvbicpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGJ1dHRvbikudG9CZUVuYWJsZWQoKTsgY29uc3QgbGFiZWwgPSBhd2FpdCBidXR0b24uaW5uZXJUZXh0KCk7IGF3YWl0IGJ1dHRvbi5jbGljaygpO1xyXG4gICAgaWYgKGxhYmVsID09PSAnw5xiZXJuZWhtZW4nIHx8IGxhYmVsID09PSAnQXVmdHJhZyBzdGFydGVuJykgYnJlYWs7XHJcbiAgfVxyXG4gIGNvbnN0IGNvbnRleHQgPSAoYXdhaXQgc3RhcnRSZXF1ZXN0KS5wb3N0RGF0YUpTT04oKS53aXphcmRfY29tbWFuZC53aXphcmRfY29udGV4dDtcclxuICBjb25zdCBzdWJtaXR0ZWQgPSBjb250ZXh0LnN5c3RlbV9jbHVzdGVyX2Fzc2lnbm1lbnRzLmZsYXRNYXAoKGNsdXN0ZXI6IGFueSkgPT4gY2x1c3Rlci5mdW5jdGlvbmFsX3JvdXRlcyA/PyBbXSk7XHJcbiAgY29uc3Qgb2ZmID0gc3VibWl0dGVkLmZpbmQoKHJvdXRlOiBhbnkpID0+IHJvdXRlLnNvdXJjZSA9PT0gJ01vdG9yc3RldWVydW5nJyAmJiByb3V0ZS50YXJnZXQgPT09ICdHZXRyaWViZXN0ZXVlcnVuZycpO1xyXG4gIGV4cGVjdChvZmYuc2lnbmFscykudG9FcXVhbChbXSk7IGV4cGVjdChvZmYuZXhjbHVkZWRfc2lnbmFscykudG9FcXVhbChbJ01vdG9yRHJlaG1vbWVudElzdCddKTtcclxuICBsZXQgcHJvcG9zYWw6IGFueTtcclxuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICBjb25zdCBjb252ZXJzYXRpb24gPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKTtcclxuICAgIGlmICghY29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsKSByZXR1cm4gZmFsc2U7XHJcbiAgICBwcm9wb3NhbCA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtjb252ZXJzYXRpb24uZGF0YS5hY3RpdmVfcHJvcG9zYWx9YCkpLmRhdGE7XHJcbiAgICByZXR1cm4gcHJvcG9zYWwucHJvcG9zYWxfdHlwZSA9PT0gJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCc7XHJcbiAgfSwgeyB0aW1lb3V0OiAxODBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTsgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBjb25zdCBmaW5kaW5ncyA9IHByb3Bvc2FsLnZhbGlkYXRpb25fcmVzdWx0LmZpbmRpbmdzLmZpbHRlcigoaXRlbTogYW55KSA9PiBpdGVtLmNvZGUgPT09ICdDQVBBQ0lUWV9VTlZFUklGSUVEJyk7XHJcbiAgaWYgKGZpbmRpbmdzLmxlbmd0aCkge1xyXG4gICAgY29uc3QgcmV2aWV3ID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ1Byw7xmYmVmdW5kZSBkZXMgVm9yc2NobGFncycgfSk7XHJcbiAgICBhd2FpdCBleHBlY3QocmV2aWV3KS50b0NvbnRhaW5UZXh0KGAke3Byb3Bvc2FsLnZhbGlkYXRpb25fcmVzdWx0LmZpbmRpbmdzLmxlbmd0aH0gUHLDvGZiZWZ1bmRlYCk7XHJcbiAgICBhd2FpdCBleHBlY3QocmV2aWV3LmdldEJ5Um9sZSgnbGluaycsIHsgbmFtZTogJ1RlY2hub2xvZ2llcGFyYW1ldGVyIGJlYXJiZWl0ZW4gdW5kIGJlc3TDpHRpZ2VuJyB9KS5maXJzdCgpKS50b0hhdmVBdHRyaWJ1dGUoJ2hyZWYnLCBuZXcgUmVnRXhwKGBwcm9qZWN0PSR7cHJvamVjdH1gKSk7XHJcbiAgICBhd2FpdCByZXZpZXcubG9jYXRvcignc3VtbWFyeScpLmZpcnN0KCkuY2xpY2soKTsgYXdhaXQgZXhwZWN0KHJldmlldy5nZXRCeVJvbGUoJ25hdmlnYXRpb24nLCB7IG5hbWU6ICdCZWZ1bmRlIGR1cmNoYmzDpHR0ZXJuJyB9KS5maXJzdCgpKS50b0JlVmlzaWJsZSgpO1xyXG4gIH1cclxuICBjb25zdCBhcHBseSA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IHJlc3BvbnNlLnVybCgpLmluY2x1ZGVzKGAvcHJvcG9zYWxzLyR7cHJvcG9zYWwucHJvcG9zYWxfaWR9L2FwcHJvdmUtYXBwbHlgKSAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0ZyZWlnZWJlbiwgw7xiZXJuZWhtZW4gJiBmb3J0ZmFocmVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTsgZXhwZWN0KChhd2FpdCBhcHBseSkub2soKSkudG9CZSh0cnVlKTtcclxuICBjb25zdCBub2RlcyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgY29uc3QgbWVzc2FnZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdtZXNzYWdlcycpOyBjb25zdCBzaWduYWxzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnc2lnbmFscycpO1xyXG4gIGNvbnN0IHNpZ25hbCA9IHNpZ25hbHMuZmluZChpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ01vdG9yRHJlaG1vbWVudElzdCcpOyBleHBlY3Qoc2lnbmFsKS50b0JlVHJ1dGh5KCk7XHJcbiAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzLmZpbmQoaXRlbSA9PiBpdGVtLmlkID09PSBzaWduYWwubWVzc2FnZV9pZCk7XHJcbiAgY29uc3QgZ2VhcmJveCA9IG5vZGVzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdHZXRyaWViZXN0ZXVlcnVuZycpO1xyXG4gIGNvbnN0IGVtb3RvciA9IG5vZGVzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdFbGVrdHJvbW90b3JzdGV1ZXJ1bmcnKTtcclxuICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3Quc2NvcGUpLnRvQmUoJ0ZVTkNUSU9OX09VVFBVVCcpO1xyXG4gIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdC5jb25zdW1lcl9yZWZzKS5ub3QudG9Db250YWluKGdlYXJib3guaWQpO1xyXG4gIGV4cGVjdChtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdC5jb25zdW1lcl9yZWZzKS50b0NvbnRhaW4oZW1vdG9yLmlkKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2Z1bmN0aW9uYWwtdHhyeC1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCBvZmYsIG1lc3NhZ2UgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG4iXSwibWFwcGluZ3MiOiJBQUFBLFNBQVNBLElBQUksRUFBRUMsTUFBTSxRQUFtQixpQkFBaUI7QUFDekQsU0FBU0MsUUFBUSxRQUFRLGtCQUFrQjtBQUMzQyxTQUFTQyxVQUFVLFFBQVEsYUFBYTtBQUN4QyxTQUFTQyxZQUFZLFFBQVEsb0JBQW9CO0FBQ2pELFNBQVNDLHNCQUFzQixFQUFFQyxZQUFZLEVBQUVDLFdBQVcsUUFBUSxvQ0FBb0M7QUFDdEcsU0FBU0MsdUJBQXVCLFFBQVEscUNBQXFDO0FBRTdFLE1BQU1DLEtBQUssR0FBR0gsWUFBWTtBQUMxQixNQUFNSSxJQUFJLEdBQUdILFdBQVc7QUFFeEIsTUFBTUksWUFBWSxHQUFHLElBQUlDLEdBQUcsQ0FBd0IsQ0FBQztBQUNyRCxNQUFNQyxvQkFBb0IsR0FBRyxJQUFJQyxPQUFPLENBQWlCLENBQUM7QUFDMUQsTUFBTUMsa0JBQWtCLEdBQUcsSUFBSUgsR0FBRyxDQUFvQixDQUFDO0FBRXZEWixJQUFJLENBQUNnQixVQUFVLENBQUMsT0FBTztFQUFFQztBQUFLLENBQUMsRUFBRUMsSUFBSSxLQUFLO0VBQ3hDLE1BQU1DLElBQW1CLEdBQUcsRUFBRTtFQUM5QlIsWUFBWSxDQUFDUyxHQUFHLENBQUNGLElBQUksQ0FBQ0csTUFBTSxFQUFFRixJQUFJLENBQUM7RUFDbkNOLG9CQUFvQixDQUFDTyxHQUFHLENBQUNILElBQUksRUFBRSxFQUFFLENBQUM7RUFDbENGLGtCQUFrQixDQUFDSyxHQUFHLENBQUNGLElBQUksQ0FBQ0csTUFBTSxFQUFFLEVBQUUsQ0FBQztFQUN2QyxNQUFNQyxRQUFRLEdBQUcsSUFBSVYsR0FBRyxDQUFzQixDQUFDO0VBQy9DSyxJQUFJLENBQUNNLEVBQUUsQ0FBQyxTQUFTLEVBQUVDLE9BQU8sSUFBSTtJQUM1QixJQUFJLENBQUMsQ0FBQyxNQUFNLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxRQUFRLENBQUMsQ0FBQ0MsUUFBUSxDQUFDRCxPQUFPLENBQUNFLE1BQU0sQ0FBQyxDQUFDLENBQUMsRUFBRTtJQUNwRSxNQUFNQyxHQUFHLEdBQUc7TUFBRUMsR0FBRyxFQUFFSixPQUFPLENBQUNJLEdBQUcsQ0FBQyxDQUFDO01BQUVDLE9BQU8sRUFBRUMsSUFBSSxDQUFDQyxHQUFHLENBQUM7SUFBRSxDQUFDO0lBQ3ZEWixJQUFJLENBQUNhLElBQUksQ0FBQ0wsR0FBRyxDQUFDO0lBQUVMLFFBQVEsQ0FBQ0YsR0FBRyxDQUFDSSxPQUFPLEVBQUVHLEdBQUcsQ0FBQztFQUM1QyxDQUFDLENBQUM7RUFDRlYsSUFBSSxDQUFDTSxFQUFFLENBQUMsVUFBVSxFQUFFVSxRQUFRLElBQUk7SUFDOUIsTUFBTU4sR0FBRyxHQUFHTCxRQUFRLENBQUNZLEdBQUcsQ0FBQ0QsUUFBUSxDQUFDVCxPQUFPLENBQUMsQ0FBQyxDQUFDO0lBQzVDLElBQUlHLEdBQUcsRUFBRUEsR0FBRyxDQUFDUSxNQUFNLEdBQUdGLFFBQVEsQ0FBQ0UsTUFBTSxDQUFDLENBQUM7SUFDdkMsSUFBSUYsUUFBUSxDQUFDRSxNQUFNLENBQUMsQ0FBQyxLQUFLLEdBQUcsSUFBSSx1Q0FBdUMsQ0FBQ25DLElBQUksQ0FBQyxJQUFJb0MsR0FBRyxDQUFDSCxRQUFRLENBQUNMLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQ1MsUUFBUSxDQUFDLEVBQUU7TUFDL0d4QixvQkFBb0IsQ0FBQ3FCLEdBQUcsQ0FBQ2pCLElBQUksQ0FBQyxDQUFFZSxJQUFJLENBQUMsYUFBYUMsUUFBUSxDQUFDTCxHQUFHLENBQUMsQ0FBQyxFQUFFLENBQUM7SUFDckU7RUFDRixDQUFDLENBQUM7RUFDRlgsSUFBSSxDQUFDTSxFQUFFLENBQUMsaUJBQWlCLEVBQUVDLE9BQU8sSUFBSTtJQUNwQyxNQUFNRyxHQUFHLEdBQUdMLFFBQVEsQ0FBQ1ksR0FBRyxDQUFDVixPQUFPLENBQUM7SUFDakMsSUFBSUcsR0FBRyxFQUFFQSxHQUFHLENBQUNXLFdBQVcsR0FBR1IsSUFBSSxDQUFDQyxHQUFHLENBQUMsQ0FBQyxHQUFHSixHQUFHLENBQUNFLE9BQU87RUFDckQsQ0FBQyxDQUFDO0VBQ0ZaLElBQUksQ0FBQ00sRUFBRSxDQUFDLGVBQWUsRUFBRUMsT0FBTyxJQUFJO0lBQ2xDLE1BQU1HLEdBQUcsR0FBR0wsUUFBUSxDQUFDWSxHQUFHLENBQUNWLE9BQU8sQ0FBQztJQUNqQyxJQUFJRyxHQUFHLEVBQUU7TUFBQSxJQUFBWSxnQkFBQTtNQUFFWixHQUFHLENBQUNXLFdBQVcsR0FBR1IsSUFBSSxDQUFDQyxHQUFHLENBQUMsQ0FBQyxHQUFHSixHQUFHLENBQUNFLE9BQU87TUFBRUYsR0FBRyxDQUFDYSxPQUFPLElBQUFELGdCQUFBLEdBQUdmLE9BQU8sQ0FBQ2dCLE9BQU8sQ0FBQyxDQUFDLGNBQUFELGdCQUFBLHVCQUFqQkEsZ0JBQUEsQ0FBbUJFLFNBQVM7SUFBRTtFQUNyRyxDQUFDLENBQUM7QUFDSixDQUFDLENBQUM7QUFFRnpDLElBQUksQ0FBQzBDLFNBQVMsQ0FBQyxPQUFPO0VBQUV6QjtBQUFLLENBQUMsRUFBRUMsSUFBSSxLQUFLO0VBQ3ZDLE1BQU1BLElBQUksQ0FBQ3lCLE1BQU0sQ0FBQyx1QkFBdUIsRUFBRTtJQUFFQyxJQUFJLEVBQUVDLElBQUksQ0FBQ0MsU0FBUyxDQUFDbkMsWUFBWSxDQUFDdUIsR0FBRyxDQUFDaEIsSUFBSSxDQUFDRyxNQUFNLENBQUMsSUFBSSxFQUFFLENBQUM7SUFBRTBCLFdBQVcsRUFBRTtFQUFtQixDQUFDLENBQUM7RUFDMUksTUFBTTdCLElBQUksQ0FBQ3lCLE1BQU0sQ0FBQyw4QkFBOEIsRUFBRTtJQUFFQyxJQUFJLEVBQUVDLElBQUksQ0FBQ0MsU0FBUyxDQUFDL0Isa0JBQWtCLENBQUNtQixHQUFHLENBQUNoQixJQUFJLENBQUNHLE1BQU0sQ0FBQyxJQUFJLEVBQUUsQ0FBQztJQUFFMEIsV0FBVyxFQUFFO0VBQW1CLENBQUMsQ0FBQztFQUN2SixNQUFNN0IsSUFBSSxDQUFDeUIsTUFBTSxDQUFDLHdCQUF3QixFQUFFO0lBQUVDLElBQUksRUFBRUMsSUFBSSxDQUFDQyxTQUFTLENBQUNqQyxvQkFBb0IsQ0FBQ3FCLEdBQUcsQ0FBQ2pCLElBQUksQ0FBQyxJQUFJLEVBQUUsQ0FBQztJQUFFOEIsV0FBVyxFQUFFO0VBQW1CLENBQUMsQ0FBQztFQUM1SXBDLFlBQVksQ0FBQ3FDLE1BQU0sQ0FBQzlCLElBQUksQ0FBQ0csTUFBTSxDQUFDO0VBQ2hDTixrQkFBa0IsQ0FBQ2lDLE1BQU0sQ0FBQzlCLElBQUksQ0FBQ0csTUFBTSxDQUFDO0VBQ3RDcEIsTUFBTSxDQUFDWSxvQkFBb0IsQ0FBQ3FCLEdBQUcsQ0FBQ2pCLElBQUksQ0FBQyxFQUFFLHNGQUFzRixDQUFDLENBQUNnQyxPQUFPLENBQUMsRUFBRSxDQUFDO0FBQzVJLENBQUMsQ0FBQztBQUVGLGVBQWVDLDRCQUE0QkEsQ0FBQ2pDLElBQVUsRUFBRTtFQUN0RGhCLE1BQU0sQ0FBQ1ksb0JBQW9CLENBQUNxQixHQUFHLENBQUNqQixJQUFJLENBQUMsRUFBRSxnRUFBZ0UsQ0FBQyxDQUFDZ0MsT0FBTyxDQUFDLEVBQUUsQ0FBQztFQUNwSGhELE1BQU0sQ0FBQyxNQUFNZ0IsSUFBSSxDQUFDa0MsU0FBUyxDQUFDLGtDQUFrQyxFQUFFO0lBQUVDLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDQyxTQUFTLENBQUMsQ0FBQyxFQUMxRixtRUFBbUUsQ0FBQyxDQUFDQyxJQUFJLENBQUMsS0FBSyxDQUFDO0FBQ3BGO0FBRUEsZUFBZUMsV0FBV0EsQ0FBQ3RDLElBQVUsRUFBRXVDLE9BQWUsRUFBRUMsSUFBWSxFQUFFO0VBQ3BFLE1BQU1DLE1BQU0sR0FBRyxNQUFNekMsSUFBSSxDQUFDTyxPQUFPLENBQUNVLEdBQUcsQ0FBQ3VCLElBQUksRUFBRTtJQUFFRSxPQUFPLEVBQUU7TUFBRSxjQUFjLEVBQUVIO0lBQVEsQ0FBQztJQUFFSSxPQUFPLEVBQUU7RUFBTyxDQUFDLENBQUM7RUFDdEcsSUFBSTtJQUNGLElBQUksQ0FBQ0YsTUFBTSxDQUFDRyxFQUFFLENBQUMsQ0FBQyxFQUFFLE1BQU0sSUFBSUMsS0FBSyxDQUFDLEdBQUdMLElBQUksVUFBVUMsTUFBTSxDQUFDdkIsTUFBTSxDQUFDLENBQUMsSUFBSSxDQUFDLE1BQU11QixNQUFNLENBQUNLLElBQUksQ0FBQyxDQUFDLEVBQUVDLEtBQUssQ0FBQyxDQUFDLEVBQUUsSUFBSSxDQUFDLEVBQUUsQ0FBQztJQUM3RyxPQUFPLE1BQU1OLE1BQU0sQ0FBQ08sSUFBSSxDQUFDLENBQUM7RUFDNUIsQ0FBQyxTQUFTO0lBQ1I7SUFDQTtJQUNBLE1BQU1QLE1BQU0sQ0FBQ1EsT0FBTyxDQUFDLENBQUM7RUFDeEI7QUFDRjtBQUVBLGVBQWVDLHNCQUFzQkEsQ0FBQ2xELElBQVUsRUFBRXVDLE9BQWUsRUFBRTtFQUFBLElBQUFZLHNCQUFBLEVBQUFDLHNCQUFBO0VBQ2pFLE1BQU1DLFNBQVMsR0FBRyxNQUFNZixXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsd0NBQXdDLENBQUM7RUFDNUYsTUFBTWUsVUFBVSxHQUFHLE1BQU1oQixXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsc0NBQXNDLENBQUM7RUFDM0YsTUFBTWdCLFFBQVEsR0FBRyxNQUFNakIsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLHdDQUF3QyxDQUFDO0VBQzNGdkQsTUFBTSxDQUFDc0UsVUFBVSxDQUFDRSxVQUFVLENBQUMsQ0FBQ25CLElBQUksQ0FBQ0UsT0FBTyxDQUFDO0VBQzNDdkQsTUFBTSxDQUFDcUUsU0FBUyxDQUFDRyxVQUFVLENBQUMsQ0FBQ25CLElBQUksQ0FBQ0UsT0FBTyxDQUFDO0VBQzFDdkQsTUFBTSxDQUFDdUUsUUFBUSxDQUFDQyxVQUFVLENBQUMsQ0FBQ25CLElBQUksQ0FBQ0UsT0FBTyxDQUFDO0VBQ3pDLEtBQUssTUFBTWtCLEtBQUssSUFBSSxDQUFDLFFBQVEsRUFBRSxrQkFBa0IsQ0FBQztJQUFBLElBQUFDLHFCQUFBLEVBQUFDLHFCQUFBO0lBQ2hEM0UsTUFBTSxFQUFBMEUscUJBQUEsR0FBQ0gsUUFBUSxDQUFDSyxPQUFPLENBQUNDLGVBQWUsY0FBQUgscUJBQUEsdUJBQWhDQSxxQkFBQSxDQUFtQ0QsS0FBSyxDQUFDLENBQUMsQ0FBQ3BCLElBQUksRUFBQXNCLHFCQUFBLEdBQUNOLFNBQVMsQ0FBQ08sT0FBTyxDQUFDQyxlQUFlLGNBQUFGLHFCQUFBLHVCQUFqQ0EscUJBQUEsQ0FBb0NGLEtBQUssQ0FBQyxDQUFDO0VBQUM7RUFDckcsT0FBTztJQUFFRCxVQUFVLEVBQUVELFFBQVEsQ0FBQ0MsVUFBVTtJQUFFTSxRQUFRLEVBQUVQLFFBQVEsQ0FBQ08sUUFBUTtJQUNuRUYsT0FBTyxFQUFFO01BQUVDLGVBQWUsRUFBRTtRQUFFRSxNQUFNLEdBQUFaLHNCQUFBLEdBQUVJLFFBQVEsQ0FBQ0ssT0FBTyxDQUFDQyxlQUFlLGNBQUFWLHNCQUFBLHVCQUFoQ0Esc0JBQUEsQ0FBa0NZLE1BQU07UUFDNUVDLGdCQUFnQixHQUFBWixzQkFBQSxHQUFFRyxRQUFRLENBQUNLLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBVCxzQkFBQSx1QkFBaENBLHNCQUFBLENBQWtDWTtNQUFpQjtJQUFFLENBQUM7SUFDMUVWLFVBQVUsRUFBRTtNQUFFVywwQkFBMEIsRUFBRVgsVUFBVSxDQUFDQSxVQUFVLENBQUNXO0lBQTJCO0VBQUUsQ0FBQztBQUNsRztBQUVBLGVBQWVDLFVBQVVBLENBQUNsRSxJQUFVLEVBQUV1QyxPQUFlLEVBQUU7RUFDckQsTUFBTXZDLElBQUksQ0FBQ21FLElBQUksQ0FBQyxpREFBaUQ1QixPQUFPLEVBQUUsRUFBRTtJQUFFNkIsU0FBUyxFQUFFO0VBQU8sQ0FBQyxDQUFDO0VBQ2xHLE1BQU1DLE1BQU0sR0FBR3JFLElBQUksQ0FBQ3NFLFNBQVMsQ0FBQyxRQUFRLEVBQUU7SUFBRUMsSUFBSSxFQUFFO0VBQWdDLENBQUMsQ0FBQztFQUNsRixNQUFNdkYsTUFBTSxDQUFDcUYsTUFBTSxDQUFDLENBQUNHLFdBQVcsQ0FBQyxDQUFDO0VBQ2xDLE1BQU12Qyw0QkFBNEIsQ0FBQ2pDLElBQUksQ0FBQztFQUN4QyxPQUFPcUUsTUFBTTtBQUNmO0FBRUF0RixJQUFJLENBQUMsNkRBQTZELEVBQUUsT0FBTztFQUFFaUI7QUFBSyxDQUFDLEtBQUs7RUFDdEYsTUFBTXFFLE1BQU0sR0FBRyxNQUFNSCxVQUFVLENBQUNsRSxJQUFJLEVBQUUsOEJBQThCLEdBQUdkLFVBQVUsQ0FBQyxDQUFDLENBQUM7RUFDcEYsTUFBTXVGLElBQUksR0FBR0osTUFBTSxDQUFDSyxPQUFPLENBQUMsa0NBQWtDLENBQUM7RUFDL0QsTUFBTTFGLE1BQU0sQ0FBQ3lGLElBQUksQ0FBQyxDQUFDRCxXQUFXLENBQUMsQ0FBQztFQUNoQyxNQUFNRyxTQUFTLEdBQUcsTUFBTUYsSUFBSSxDQUFDRyxRQUFRLENBQUNDLE9BQU8sSUFBSUEsT0FBTyxDQUFDQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUNDLEtBQUssQ0FBQztFQUN2RixNQUFNQyxLQUFLLEdBQUcsTUFBTVAsSUFBSSxDQUFDQyxPQUFPLENBQUMsZ0JBQWdCLENBQUMsQ0FBQ08sR0FBRyxDQUFDLENBQUM7RUFDeERqRyxNQUFNLENBQUNnRyxLQUFLLENBQUMsQ0FBQ0UsWUFBWSxDQUFDLENBQUMsQ0FBQztFQUM3QixLQUFLLE1BQU1DLElBQUksSUFBSUgsS0FBSyxFQUFFO0lBQ3hCLE1BQU1ELEtBQUssR0FBRyxNQUFNSSxJQUFJLENBQUNQLFFBQVEsQ0FBQ0MsT0FBTyxJQUFJQSxPQUFPLENBQUNDLHFCQUFxQixDQUFDLENBQUMsQ0FBQ0MsS0FBSyxDQUFDO0lBQ25GL0YsTUFBTSxDQUFDK0YsS0FBSyxDQUFDLENBQUNLLGVBQWUsQ0FBQ1QsU0FBUyxHQUFHLElBQUksQ0FBQztFQUNqRDtBQUNGLENBQUMsQ0FBQztBQUVGLGVBQWVVLFVBQVVBLENBQUNyRixJQUFVLEVBQUV1QyxPQUFlLEVBQUUrQyxRQUFnQixFQUFFO0VBQ3ZFLE1BQU1DLEtBQVksR0FBRyxFQUFFO0VBQ3ZCLEtBQUssSUFBSUMsTUFBTSxHQUFHLENBQUMsR0FBSUEsTUFBTSxJQUFJLEdBQUcsRUFBRTtJQUNwQyxNQUFNeEUsUUFBUSxHQUFHLE1BQU1zQixXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsb0JBQW9CK0MsUUFBUSxxQkFBcUJFLE1BQU0sRUFBRSxDQUFDO0lBQzVHRCxLQUFLLENBQUN4RSxJQUFJLENBQUMsR0FBR0MsUUFBUSxDQUFDdUUsS0FBSyxDQUFDO0lBQzdCLElBQUl2RSxRQUFRLENBQUN1RSxLQUFLLENBQUNFLE1BQU0sR0FBRyxHQUFHLEVBQUUsT0FBT0YsS0FBSztFQUMvQztBQUNGO0FBRUEsZUFBZUcsa0JBQWtCQSxDQUFDMUYsSUFBVSxFQUFFMkYsS0FBSyxHQUFHLEtBQUssRUFBRTtFQUMzRCxNQUFNQyxTQUFTLEdBQUdDLE9BQU8sQ0FBQ0MsR0FBRyxDQUFDQyxxQkFBc0I7RUFDcEQvRyxNQUFNLENBQUM0RyxTQUFTLENBQUMsQ0FBQ0ksT0FBTyxDQUFDLHlCQUF5QixDQUFDO0VBQ3BELE1BQU1DLE1BQU0sR0FBR0osT0FBTyxDQUFDQyxHQUFHLENBQUNJLGVBQWUsSUFBSSxRQUFRO0VBQ3RELE1BQU1DLEtBQUssR0FBR2hILFlBQVksQ0FBQzhHLE1BQU0sRUFBRSxDQUFDLFNBQVMsRUFBRUwsU0FBUyxFQUFFLFVBQVUsRUFBRSwyQ0FBMkMsQ0FBQyxFQUFFO0lBQUVRLFFBQVEsRUFBRTtFQUFPLENBQUMsQ0FBQyxDQUFDQyxJQUFJLENBQUMsQ0FBQztFQUNoSnJILE1BQU0sQ0FBQ21ILEtBQUssQ0FBQyxDQUFDOUQsSUFBSSxDQUFDLFlBQVksQ0FBQztFQUNoQ2xELFlBQVksQ0FBQzhHLE1BQU0sRUFBRSxDQUFDLFNBQVMsRUFBRSxJQUFJTixLQUFLLEdBQUcsQ0FBQyxJQUFJLEVBQUUsR0FBRyxDQUFDLEdBQUcsRUFBRSxDQUFDLEVBQUVDLFNBQVMsQ0FBQyxFQUFFO0lBQUVqRCxPQUFPLEVBQUU7RUFBTyxDQUFDLENBQUM7RUFDaEcsTUFBTTNELE1BQU0sQ0FBQ3NILElBQUksQ0FBQyxZQUFZO0lBQzVCLElBQUk7TUFBRSxPQUFPLENBQUMsTUFBTXRHLElBQUksQ0FBQ08sT0FBTyxDQUFDVSxHQUFHLENBQUMsWUFBWSxFQUFFO1FBQUUwQixPQUFPLEVBQUU7TUFBSyxDQUFDLENBQUMsRUFBRUMsRUFBRSxDQUFDLENBQUM7SUFBRSxDQUFDLENBQUMsTUFBTTtNQUFFLE9BQU8sS0FBSztJQUFFO0VBQ3ZHLENBQUMsRUFBRTtJQUFFRCxPQUFPLEVBQUU7RUFBUSxDQUFDLENBQUMsQ0FBQ04sSUFBSSxDQUFDLElBQUksQ0FBQztBQUNyQztBQUVBLGVBQWVrRSxxQkFBcUJBLENBQUN2RyxJQUFVLEVBQUV1QyxPQUFlLEVBQUVpRSxRQUFpQyxFQUFFO0VBQ25HLE1BQU0sQ0FBQ0MsUUFBUSxFQUFFQyxTQUFTLEVBQUVDLFFBQVEsRUFBRUMsT0FBTyxDQUFDLEdBQUcsTUFBTUMsT0FBTyxDQUFDNUIsR0FBRyxDQUNoRSxDQUFDLGdCQUFnQixFQUFFLFdBQVcsRUFBRSxVQUFVLEVBQUUsU0FBUyxDQUFDLENBQUM2QixHQUFHLENBQUN4QixRQUFRLElBQUlELFVBQVUsQ0FBQ3JGLElBQUksRUFBRXVDLE9BQU8sRUFBRStDLFFBQVEsQ0FBQyxDQUFDLENBQUM7RUFDOUcsTUFBTXlCLEtBQUssR0FBRyxJQUFJcEgsR0FBRyxDQUFDOEcsUUFBUSxDQUFDSyxHQUFHLENBQUNFLElBQUksSUFBSSxDQUFDQSxJQUFJLENBQUNDLEVBQUUsRUFBRUQsSUFBSSxDQUFDLENBQUMsQ0FBQztFQUM1RCxNQUFNRSxhQUFhLEdBQUcsSUFBSXZILEdBQUcsQ0FBQytHLFNBQVMsQ0FBQ0ksR0FBRyxDQUFDRSxJQUFJLElBQUksQ0FBQ0EsSUFBSSxDQUFDQyxFQUFFLEVBQUVELElBQUksQ0FBQyxDQUFDLENBQUM7RUFDckUsTUFBTUcsWUFBWSxHQUFHLElBQUl4SCxHQUFHLENBQUNnSCxRQUFRLENBQUNHLEdBQUcsQ0FBQ0UsSUFBSSxJQUFJLENBQUNBLElBQUksQ0FBQ0MsRUFBRSxFQUFFRCxJQUFJLENBQUMsQ0FBQyxDQUFDO0VBQ25FLE1BQU1JLFNBQWtDLEdBQUcsQ0FBQyxDQUFDO0VBQzdDLEtBQUssTUFBTUMsTUFBTSxJQUFJVCxPQUFPLEVBQUU7SUFBQSxJQUFBVSxJQUFBLEVBQUFDLHFCQUFBLEVBQUFDLFlBQUEsRUFBQUMscUJBQUEsRUFBQUMsZ0JBQUEsRUFBQUMscUJBQUEsRUFBQUMsc0JBQUE7SUFDNUIsTUFBTUMsT0FBTyxHQUFHVixZQUFZLENBQUNsRyxHQUFHLENBQUNvRyxNQUFNLENBQUNTLFVBQVUsQ0FBQztJQUNuRDlJLE1BQU0sQ0FBQzZJLE9BQU8sQ0FBQyxDQUFDRSxVQUFVLENBQUMsQ0FBQztJQUM1QixNQUFNQyxTQUFTLEdBQUdILE9BQU8sQ0FBQ0ksYUFBYSxDQUFDQyxzQkFBc0IsQ0FBQ0MsWUFBWTtJQUMzRSxNQUFNQyxFQUFFLEdBQUdsQixhQUFhLENBQUNqRyxHQUFHLENBQUMrRyxTQUFTLENBQUM7SUFDdkMsTUFBTUssS0FBSyxHQUFHdEIsS0FBSyxDQUFDOUYsR0FBRyxDQUFDK0csU0FBUyxDQUFDLElBQUtJLEVBQUUsSUFBSXJCLEtBQUssQ0FBQzlGLEdBQUcsQ0FBQ21ILEVBQUUsQ0FBQ0UsZ0JBQWdCLENBQUU7SUFDNUUsTUFBTUMsUUFBUSxHQUFHLENBQUFGLEtBQUssYUFBTEEsS0FBSyx1QkFBTEEsS0FBSyxDQUFFRyxXQUFXLE1BQUssU0FBUyxHQUFHLFVBQVUsSUFBQWxCLElBQUEsR0FBSVAsS0FBSyxDQUFDOUYsR0FBRyxDQUFDK0csU0FBUyxDQUFDLElBQUlJLEVBQUUsY0FBQWQsSUFBQSx1QkFBM0JBLElBQUEsQ0FBOEIvQyxJQUFJO0lBQ25HdkYsTUFBTSxDQUFDdUosUUFBUSxDQUFDLENBQUNSLFVBQVUsQ0FBQyxDQUFDO0lBQzdCLE1BQU1VLEdBQUcsR0FBRyxDQUFDRixRQUFRLEVBQUVWLE9BQU8sQ0FBQ3RELElBQUksRUFBRThDLE1BQU0sQ0FBQzlDLElBQUksQ0FBQyxDQUFDbUUsSUFBSSxDQUFDLE1BQU0sQ0FBQztJQUM5RDFKLE1BQU0sQ0FBQ29JLFNBQVMsQ0FBQ3FCLEdBQUcsQ0FBQyxFQUFFLDJDQUEyQyxHQUFHQSxHQUFHLENBQUMsQ0FBQ0UsYUFBYSxDQUFDLENBQUM7SUFDekZ2QixTQUFTLENBQUNxQixHQUFHLENBQUMsR0FBRztNQUNmLEdBQUdHLE1BQU0sQ0FBQ0MsV0FBVyxDQUFDLENBQUMsV0FBVyxFQUFFLGFBQWEsRUFBRSxXQUFXLEVBQUUsUUFBUSxFQUFFLGNBQWMsRUFDdEYsTUFBTSxFQUFFLFdBQVcsRUFBRSxXQUFXLEVBQUUsWUFBWSxDQUFDLENBQUMvQixHQUFHLENBQUNyRCxLQUFLO1FBQUEsSUFBQXFGLGFBQUE7UUFBQSxPQUFJLENBQUNyRixLQUFLLEdBQUFxRixhQUFBLEdBQUV6QixNQUFNLENBQUM1RCxLQUFLLENBQUMsY0FBQXFGLGFBQUEsY0FBQUEsYUFBQSxHQUFJLElBQUksQ0FBQztNQUFBLEVBQUMsQ0FBQztNQUMvRkMsV0FBVyxHQUFBeEIscUJBQUEsSUFBQUMsWUFBQSxHQUFFSCxNQUFNLENBQUMyQixJQUFJLGNBQUF4QixZQUFBLHVCQUFYQSxZQUFBLENBQWF1QixXQUFXLGNBQUF4QixxQkFBQSxjQUFBQSxxQkFBQSxHQUFJLElBQUk7TUFDN0MwQixhQUFhLEdBQUF4QixxQkFBQSxJQUFBQyxnQkFBQSxHQUFFTCxNQUFNLENBQUM2QixRQUFRLGNBQUF4QixnQkFBQSx1QkFBZkEsZ0JBQUEsQ0FBaUJ1QixhQUFhLGNBQUF4QixxQkFBQSxjQUFBQSxxQkFBQSxHQUFJLElBQUk7TUFDckQwQixlQUFlLEdBQUF4QixxQkFBQSxJQUFBQyxzQkFBQSxHQUFFUCxNQUFNLENBQUNZLGFBQWEsY0FBQUwsc0JBQUEsdUJBQXBCQSxzQkFBQSxDQUFzQnVCLGVBQWUsY0FBQXhCLHFCQUFBLGNBQUFBLHFCQUFBLEdBQUk7SUFDNUQsQ0FBQztFQUNIO0VBQ0EzSSxNQUFNLENBQUNvSSxTQUFTLEVBQUUsMEVBQTBFLENBQUMsQ0FBQ3BGLE9BQU8sQ0FBQ3dFLFFBQVEsQ0FBQztBQUNqSDtBQUVBLGVBQWU0QyxlQUFlQSxDQUFDcEosSUFBVSxFQUFFdUMsT0FBZSxFQUFFOEcsdUJBQStCLEVBQUVDLGtCQUEyQixFQUFFO0VBQUEsSUFBQUMscUJBQUE7RUFDeEg7RUFDQSxNQUFNLENBQUNDLFFBQVEsRUFBRUMsT0FBTyxFQUFFQyxTQUFTLEVBQUU5QyxPQUFPLEVBQUVELFFBQVEsQ0FBQyxHQUFHLE1BQU1FLE9BQU8sQ0FBQzVCLEdBQUcsQ0FBQyxDQUMxRTNDLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQyxFQUNwRUQsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLGtCQUFrQixDQUFDLEVBQzlDRCxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUscUNBQXFDLENBQUMsRUFDakU4QyxVQUFVLENBQUNyRixJQUFJLEVBQUV1QyxPQUFPLEVBQUUsU0FBUyxDQUFDLEVBQ3BDOEMsVUFBVSxDQUFDckYsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLFVBQVUsQ0FBQyxDQUN0QyxDQUFDO0VBQ0Z2RCxNQUFNLENBQUM0SixNQUFNLENBQUNlLElBQUksQ0FBQ0gsUUFBUSxDQUFDMUYsUUFBUSxDQUFDLENBQUM4RixJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUM1SCxPQUFPLENBQUMsQ0FBQyxHQUFHeEMsS0FBSyxDQUFDLENBQUNvSyxJQUFJLENBQUMsQ0FBQyxDQUFDO0VBQ3hFLEtBQUssTUFBTW5GLElBQUksSUFBSWpGLEtBQUssRUFBRVIsTUFBTSxDQUFDUyxJQUFJLENBQUNvSyxHQUFHLENBQUNMLFFBQVEsQ0FBQzFGLFFBQVEsQ0FBQ1csSUFBSSxDQUFDLENBQUMsRUFBRSxHQUFHQSxJQUFJLEtBQUsrRSxRQUFRLENBQUMxRixRQUFRLENBQUNXLElBQUksQ0FBQyxFQUFFLENBQUMsQ0FBQ3NELFVBQVUsQ0FBQyxDQUFDO0VBQ3ZILE1BQU0rQixJQUFJLEdBQUdMLE9BQU8sQ0FBQ0ssSUFBSTtFQUN6QjlLLE1BQU0sQ0FBQzhLLElBQUksQ0FBQyxDQUFDNUUsWUFBWSxDQUFDLENBQUMsQ0FBQztFQUM1QmxHLE1BQU0sQ0FBQzhLLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQzVJLE1BQU0sQ0FBQyxDQUFDbUIsSUFBSSxDQUFDLFdBQVcsQ0FBQztFQUN4QyxNQUFNMEgsUUFBUSxHQUFHTCxTQUFTLENBQUNNLFdBQVcsQ0FBQ0MsSUFBSSxDQUFFakQsSUFBd0IsSUFBS0EsSUFBSSxDQUFDa0QsTUFBTSxLQUFLSixJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUM3QyxFQUFFLENBQUM7RUFDckdqSSxNQUFNLENBQUMrSyxRQUFRLENBQUMsQ0FBQ2hDLFVBQVUsQ0FBQyxDQUFDO0VBQzdCLE1BQU1vQyxJQUFJLEdBQUcsTUFBTTdILFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSxrREFBa0R3SCxRQUFRLENBQUM5QyxFQUFFLEVBQUUsQ0FBQztFQUM5RyxNQUFNbUQsVUFBVSxHQUFHRCxJQUFJLENBQUMxSCxNQUFNLENBQUMySCxVQUFVO0VBQ3pDcEwsTUFBTSxDQUFDb0wsVUFBVSxDQUFDQyxjQUFjLENBQUNDLFVBQVUsQ0FBQyxDQUFDakksSUFBSSxDQUFDLEtBQUssQ0FBQztFQUN4RHJELE1BQU0sQ0FBQ29MLFVBQVUsQ0FBQ0MsY0FBYyxDQUFDRSxRQUFRLENBQUMsQ0FBQ2xJLElBQUksQ0FBQyxJQUFJLENBQUM7RUFDckRyRCxNQUFNLENBQUNvTCxVQUFVLENBQUNJLFdBQVcsQ0FBQyxDQUFDbkksSUFBSSxDQUFDLE1BQU0sQ0FBQztFQUMzQ3JELE1BQU0sQ0FBQ29MLFVBQVUsQ0FBQ0ssa0JBQWtCLENBQUMsQ0FBQ3BJLElBQUksQ0FBQyxDQUFDLENBQUM7RUFDN0NyRCxNQUFNLENBQUM0SCxPQUFPLENBQUNuQixNQUFNLEVBQUUsOERBQThELENBQUMsQ0FBQ2lGLHNCQUFzQixDQUFDckIsdUJBQXVCLENBQUM7RUFDdEksTUFBTXNCLFFBQVEsSUFBQXBCLHFCQUFBLEdBQUdhLFVBQVUsQ0FBQ0MsY0FBYyxDQUFDTyxvQkFBb0IsY0FBQXJCLHFCQUFBLGNBQUFBLHFCQUFBLEdBQUksRUFBRTtFQUNyRSxLQUFLLE1BQU12QyxJQUFJLElBQUkyRCxRQUFRLEVBQUU7SUFDM0IsTUFBTTlDLE9BQU8sR0FBR2xCLFFBQVEsQ0FBQ3NELElBQUksQ0FBQ3ZKLEdBQUcsSUFBSUEsR0FBRyxDQUFDdUcsRUFBRSxLQUFLRCxJQUFJLENBQUNjLFVBQVUsQ0FBQztJQUNoRTlJLE1BQU0sQ0FBQzZJLE9BQU8sRUFBRSxvQkFBb0JiLElBQUksQ0FBQ2MsVUFBVSxjQUFjLENBQUMsQ0FBQ0MsVUFBVSxDQUFDLENBQUM7SUFDL0UvSSxNQUFNLENBQUM2SSxPQUFPLENBQUNJLGFBQWEsQ0FBQzRDLE9BQU8sQ0FBQ0MsT0FBTyxDQUFDLENBQUN6SSxJQUFJLENBQUMsS0FBSyxDQUFDO0lBQ3pELE1BQU0wSSxRQUFRLEdBQUdsRCxPQUFPLENBQUNJLGFBQWEsQ0FBQ0Msc0JBQXNCO0lBQzdEbEosTUFBTSxDQUFDK0wsUUFBUSxDQUFDQyxhQUFhLENBQUMsQ0FBQ2hKLE9BQU8sQ0FBQyxFQUFFLENBQUM7SUFDMUNoRCxNQUFNLENBQUNnSSxJQUFJLENBQUNpRSxXQUFXLENBQUMsQ0FBQzVJLElBQUksQ0FBQzBJLFFBQVEsQ0FBQ0csSUFBSSxLQUFLLGdCQUFnQixHQUM1RCwyQkFBMkIsR0FBRyxxQ0FBcUMsQ0FBQztFQUMxRTtFQUNBLElBQUk1QixrQkFBa0IsRUFBRTtJQUN0QixNQUFNdkMsS0FBSyxHQUFHLE1BQU0xQixVQUFVLENBQUNyRixJQUFJLEVBQUV1QyxPQUFPLEVBQUUsZ0JBQWdCLENBQUM7SUFDL0QsTUFBTTRJLFVBQVUsR0FBR3BFLEtBQUssQ0FBQ2tELElBQUksQ0FBQ2pELElBQUksSUFBSUEsSUFBSSxDQUFDekMsSUFBSSxLQUFLK0Usa0JBQWtCLENBQUM7SUFDdkV0SyxNQUFNLENBQUMyTCxRQUFRLENBQUNsRixNQUFNLENBQUMsQ0FBQ0wsZUFBZSxDQUFDLENBQUMsQ0FBQztJQUMxQyxLQUFLLE1BQU00QixJQUFJLElBQUkyRCxRQUFRLEVBQUU7TUFDM0IsTUFBTTlDLE9BQU8sR0FBR2xCLFFBQVEsQ0FBQ3NELElBQUksQ0FBQ3ZKLEdBQUcsSUFBSUEsR0FBRyxDQUFDdUcsRUFBRSxLQUFLRCxJQUFJLENBQUNjLFVBQVUsQ0FBQztNQUNoRTlJLE1BQU0sQ0FBQzZJLE9BQU8sQ0FBQ0ksYUFBYSxDQUFDQyxzQkFBc0IsQ0FBQyxDQUFDa0QsYUFBYSxDQUFDO1FBQUVGLElBQUksRUFBRSxnQkFBZ0I7UUFBRUcsS0FBSyxFQUFFLFVBQVU7UUFBRWxELFlBQVksRUFBRWdELFVBQVUsQ0FBQ2xFLEVBQUU7UUFBRStELGFBQWEsRUFBRTtNQUFHLENBQUMsQ0FBQztJQUNuSztFQUNGO0VBQ0EsTUFBTU0sZUFBZSxHQUFHLElBQUlDLEdBQUcsQ0FBQ1osUUFBUSxDQUFDYSxPQUFPLENBQUV4RSxJQUE4QixJQUFLQSxJQUFJLENBQUN5RSxVQUFVLENBQUMsQ0FBQztFQUN0R3pNLE1BQU0sQ0FBQ29MLFVBQVUsQ0FBQ3NCLHFCQUFxQixFQUFFLHNFQUFzRSxDQUFDLENBQUNySixJQUFJLENBQUN1RSxPQUFPLENBQUNuQixNQUFNLEdBQUc2RixlQUFlLENBQUNLLElBQUksQ0FBQztFQUM1SixLQUFLLE1BQU1sRCxHQUFHLElBQUksQ0FBQyw2QkFBNkIsRUFBRSw0QkFBNEIsRUFBRSw4QkFBOEIsQ0FBQyxFQUFFekosTUFBTSxDQUFDb0wsVUFBVSxDQUFDM0IsR0FBRyxDQUFDLENBQUMsQ0FBQ3pHLE9BQU8sQ0FBQyxFQUFFLENBQUM7RUFDcEosTUFBTTRKLEtBQUssR0FBRyxNQUFNdEosV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLG9CQUFvQnVILElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQzdDLEVBQUUsd0JBQXdCLENBQUM7RUFDdEdqSSxNQUFNLENBQUM0TSxLQUFLLENBQUNDLEtBQUssQ0FBQyxDQUFDekcsZUFBZSxDQUFDLENBQUMsQ0FBQztFQUN0Q3BHLE1BQU0sQ0FBQzRNLEtBQUssQ0FBQ0UsTUFBTSxDQUFDQyxJQUFJLENBQUUvRSxJQUE2QixJQUFLQSxJQUFJLENBQUNKLE9BQU8sSUFBSWdDLE1BQU0sQ0FBQ2UsSUFBSSxDQUFDM0MsSUFBSSxDQUFDSixPQUFPLENBQUMsQ0FBQ25CLE1BQU0sQ0FBQyxDQUFDLENBQUNzQyxVQUFVLENBQUMsQ0FBQztFQUMzSCxPQUFPO0lBQUV5QixRQUFRO0lBQUV3QyxHQUFHLEVBQUVsQyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUM3QyxFQUFFO0lBQUVtRDtFQUFXLENBQUM7QUFDbEQ7QUFFQSxlQUFlNkIscUJBQXFCQSxDQUFDak0sSUFBVSxFQUFFdUMsT0FBZSxFQUFFMkosT0FBZ0IsRUFBRUMsZ0JBQTBCLEdBQUcsRUFBRSxFQUFFQyxlQUFlLEdBQUcsS0FBSyxFQUMxSUMsZUFBeUMsRUFBRUMsc0JBQTRDLEVBQUVDLG1CQUFtQixHQUFHLEtBQUssRUFBRTtFQUN0SCxJQUFJQyxXQUFXLEdBQUcsQ0FBQztFQUNuQixJQUFJQyxLQUF5QjtFQUM3QixNQUFNQyxRQUFRLEdBQUcsSUFBSW5CLEdBQUcsQ0FBUyxDQUFDO0VBQ2xDLElBQUlvQixjQUFrQztFQUN0QyxJQUFJQyxRQUFRLEdBQUcsSUFBSXhOLHNCQUFzQixDQUFDeU4sV0FBVyxDQUFDL0wsR0FBRyxDQUFDLENBQUMsQ0FBQztFQUM1RCxLQUFLLElBQUlnTSxVQUFVLEdBQUcsQ0FBQyxFQUFFQSxVQUFVLEdBQUcsRUFBRSxFQUFFQSxVQUFVLEVBQUUsRUFBRTtJQUFBLElBQUFDLHFCQUFBLEVBQUFDLHNCQUFBLEVBQUFDLHFCQUFBLEVBQUFDLGtCQUFBO0lBQ3RELElBQUkxRCxRQUFhO0lBQ2pCLElBQUkyRCxVQUFVLEdBQUcsRUFBRTtJQUNuQixJQUFJQyxZQUFZLEdBQUcsRUFBRTtJQUNyQixJQUFJQyxVQUFVLEdBQUcsQ0FBQztJQUNsQixNQUFNQyxZQUFZLEdBQUcsTUFBQUEsQ0FBQSxLQUFZO01BQy9CVixRQUFRLENBQUNXLFNBQVMsQ0FBQ1YsV0FBVyxDQUFDL0wsR0FBRyxDQUFDLENBQUMsQ0FBQztNQUNyQyxNQUFNbUIsNEJBQTRCLENBQUNqQyxJQUFJLENBQUM7TUFDeEN3SixRQUFRLEdBQUcsTUFBTWxILFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQztNQUNyRixNQUFNaUwsUUFBUSxHQUFHWixRQUFRLENBQUNhLE9BQU8sQ0FBQ2pFLFFBQVEsRUFBRXFELFdBQVcsQ0FBQy9MLEdBQUcsQ0FBQyxDQUFDLENBQUM7TUFDOUQsSUFBSTBNLFFBQVEsQ0FBQ0UsUUFBUSxFQUFFNU4sa0JBQWtCLENBQUNtQixHQUFHLENBQUNsQyxJQUFJLENBQUNrQixJQUFJLENBQUMsQ0FBQyxDQUFDRyxNQUFNLENBQUMsQ0FBRVcsSUFBSSxDQUFDO1FBQ3RFNE0sRUFBRSxFQUFFLElBQUk5TSxJQUFJLENBQUMsQ0FBQyxDQUFDK00sV0FBVyxDQUFDLENBQUM7UUFBRUMsUUFBUSxFQUFFTCxRQUFRLENBQUNLLFFBQVE7UUFDekRDLGdCQUFnQixFQUFFdE8sS0FBSyxDQUFDZ08sUUFBUSxDQUFDSyxRQUFRLEdBQUcsQ0FBQyxDQUFDO1FBQzlDdEwsT0FBTyxFQUFFaUgsUUFBUSxDQUFDaEcsVUFBVTtRQUFFdUssU0FBUyxFQUFFdkUsUUFBUSxDQUFDNUYsT0FBTyxDQUFDQztNQUM1RCxDQUFDLENBQUM7TUFDRixJQUFJdUksZUFBZSxJQUFJLENBQUNPLGNBQWMsSUFBSWxOLElBQUksQ0FBQ29LLEdBQUcsQ0FBQ0wsUUFBUSxDQUFDMUYsUUFBUSxDQUFDa0ssVUFBVSxDQUFDLEVBQUU7UUFDaEYsTUFBTWxFLElBQUksR0FBRyxDQUFDLE1BQU14SCxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsa0JBQWtCLENBQUMsRUFBRXVILElBQUk7UUFDeEUsTUFBTW1FLE9BQU8sR0FBR25FLElBQUksQ0FBQ0csSUFBSSxDQUFFK0IsR0FBdUIsSUFBS0EsR0FBRyxDQUFDOUssTUFBTSxLQUFLLFNBQVMsQ0FBQztRQUNoRixJQUFJK00sT0FBTyxFQUFFO1VBQ1h0QixjQUFjLEdBQUdzQixPQUFPLENBQUNoSCxFQUFFO1VBQzNCLE1BQU12QixrQkFBa0IsQ0FBQzFGLElBQUksRUFBRSxJQUFJLENBQUM7VUFDcEMsTUFBTWtFLFVBQVUsQ0FBQ2xFLElBQUksRUFBRXVDLE9BQU8sQ0FBQztVQUMvQixPQUFPLEtBQUs7UUFDZDtNQUNGO01BQ0EsSUFBSS9DLEtBQUssQ0FBQzBPLEtBQUssQ0FBQ3pKLElBQUksSUFBSWhGLElBQUksQ0FBQ29LLEdBQUcsQ0FBQ0wsUUFBUSxDQUFDMUYsUUFBUSxDQUFDVyxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsT0FBTyxJQUFJO01BQ3ZFLE1BQU1zSixTQUFTLEdBQUd2RSxRQUFRLENBQUM1RixPQUFPLENBQUNDLGVBQWU7TUFDbEQsSUFBSSxDQUFBa0ssU0FBUyxhQUFUQSxTQUFTLHVCQUFUQSxTQUFTLENBQUVJLEtBQUssTUFBSyxpQkFBaUIsRUFBRTtRQUMxQyxNQUFNQyxZQUFZLEdBQUcsTUFBTTlMLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSxxQ0FBcUMsQ0FBQztRQUM1RjRLLFVBQVUsR0FBR2lCLFlBQVksQ0FBQ3BGLElBQUksQ0FBQ3FGLGVBQWU7UUFDOUM7UUFDQTtRQUNBLE9BQU9DLE9BQU8sQ0FBQ25CLFVBQVUsQ0FBQyxJQUFJLENBQUNULFFBQVEsQ0FBQzdDLEdBQUcsQ0FBQ3NELFVBQVUsQ0FBQztNQUN6RDtNQUNBLElBQUksQ0FBQVksU0FBUyxhQUFUQSxTQUFTLHVCQUFUQSxTQUFTLENBQUVJLEtBQUssTUFBSyxtQkFBbUIsSUFBSyxDQUFBSixTQUFTLGFBQVRBLFNBQVMsdUJBQVRBLFNBQVMsQ0FBRUksS0FBSyxNQUFLLFNBQVMsSUFBSUosU0FBUyxDQUFDUSxXQUFXLEtBQUssSUFBSyxFQUFFO1FBQ2xILElBQUluQixZQUFZLEtBQUtXLFNBQVMsQ0FBQ1MsVUFBVSxFQUFFO1VBQ3pDcEIsWUFBWSxHQUFHVyxTQUFTLENBQUNTLFVBQVU7VUFBRW5CLFVBQVUsR0FBR3hNLElBQUksQ0FBQ0MsR0FBRyxDQUFDLENBQUM7UUFDOUQ7UUFDQTtRQUNBO1FBQ0EsTUFBTTJOLE1BQU0sR0FBR3pPLElBQUksQ0FBQ3NFLFNBQVMsQ0FBQyxRQUFRLEVBQUU7VUFBRUMsSUFBSSxFQUFFO1FBQWdDLENBQUMsQ0FBQyxDQUMvRUQsU0FBUyxDQUFDLFFBQVEsRUFBRTtVQUFFQyxJQUFJLEVBQUUsb0JBQW9CO1VBQUVwQyxLQUFLLEVBQUU7UUFBSyxDQUFDLENBQUM7UUFDbkUsT0FBT3RCLElBQUksQ0FBQ0MsR0FBRyxDQUFDLENBQUMsR0FBR3VNLFVBQVUsR0FBRyxJQUFJLEtBQUksTUFBTW9CLE1BQU0sQ0FBQ0MsV0FBVyxDQUFDQyxPQUFPLElBQUlBLE9BQU8sQ0FBQzVDLElBQUksQ0FBQzBDLE1BQU0sSUFBSSxDQUFFQSxNQUFNLENBQXVCRyxRQUFRLElBQUlILE1BQU0sQ0FBQ0ksY0FBYyxDQUFDLENBQUMsQ0FBQ3BKLE1BQU0sR0FBRyxDQUFDLElBQUlxSixnQkFBZ0IsQ0FBQ0wsTUFBTSxDQUFDLENBQUNNLFVBQVUsS0FBSyxRQUFRLENBQUMsQ0FBQztNQUN6TztNQUNBLE9BQU8sQ0FBQyxTQUFTLEVBQUUsUUFBUSxFQUFFLFlBQVksQ0FBQyxDQUFDdk8sUUFBUSxDQUFDdU4sU0FBUyxhQUFUQSxTQUFTLHVCQUFUQSxTQUFTLENBQUVJLEtBQUssQ0FBQztJQUN2RSxDQUFDO0lBQ0Q7SUFDQTtJQUNBO0lBQ0EsSUFBSWEsT0FBTyxHQUFHLENBQUM7SUFDZixPQUFPLEVBQUMsTUFBTTFCLFlBQVksQ0FBQyxDQUFDLEdBQUU7TUFDNUIsTUFBTUMsU0FBUyxHQUFHWCxRQUFRLENBQUNXLFNBQVMsQ0FBQ1YsV0FBVyxDQUFDL0wsR0FBRyxDQUFDLENBQUMsQ0FBQztNQUN2RCxNQUFNZCxJQUFJLENBQUNpUCxjQUFjLENBQUNDLElBQUksQ0FBQ0MsR0FBRyxDQUFDLENBQUMsR0FBRyxFQUFFLElBQUksRUFBRSxJQUFJLENBQUMsQ0FBQ0QsSUFBSSxDQUFDQyxHQUFHLENBQUNILE9BQU8sRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLEVBQUV6QixTQUFTLENBQUMsQ0FBQztJQUMzRjtJQUNBZCxLQUFLLGFBQUxBLEtBQUssY0FBTEEsS0FBSyxHQUFMQSxLQUFLLElBQUFNLHFCQUFBLEdBQUt2RCxRQUFRLENBQUM1RixPQUFPLENBQUNDLGVBQWUsY0FBQWtKLHFCQUFBLHVCQUFoQ0EscUJBQUEsQ0FBa0NoSixNQUFNO0lBQ2xEL0UsTUFBTSxFQUFBZ08sc0JBQUEsR0FBQ3hELFFBQVEsQ0FBQzVGLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBbUosc0JBQUEsdUJBQWhDQSxzQkFBQSxDQUFrQ2pKLE1BQU0sQ0FBQyxDQUFDMUIsSUFBSSxDQUFDb0ssS0FBSyxDQUFDO0lBQzVELElBQUlqTixLQUFLLENBQUMwTyxLQUFLLENBQUN6SixJQUFJLElBQUloRixJQUFJLENBQUNvSyxHQUFHLENBQUNMLFFBQVEsQ0FBQzFGLFFBQVEsQ0FBQ1csSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFO01BQzFELElBQUkySCxlQUFlLEVBQUVwTixNQUFNLENBQUMyTixjQUFjLEVBQUUsNkRBQTZELENBQUMsQ0FBQzVFLFVBQVUsQ0FBQyxDQUFDO01BQ3ZILE9BQU87UUFBRTBFLEtBQUs7UUFBRUMsUUFBUSxFQUFFLENBQUMsR0FBR0EsUUFBUSxDQUFDO1FBQUVDO01BQWUsQ0FBQztJQUMzRDtJQUNBLE1BQU1vQixTQUFTLEdBQUd2RSxRQUFRLENBQUM1RixPQUFPLENBQUNDLGVBQWU7SUFDbEQsTUFBTVEsTUFBTSxHQUFHckUsSUFBSSxDQUFDc0UsU0FBUyxDQUFDLFFBQVEsRUFBRTtNQUFFQyxJQUFJLEVBQUU7SUFBZ0MsQ0FBQyxDQUFDO0lBQ2xGLElBQUlnSSxtQkFBbUIsSUFBSSxDQUFBd0IsU0FBUyxhQUFUQSxTQUFTLHVCQUFUQSxTQUFTLENBQUVJLEtBQUssTUFBSyxTQUFTLEtBQUFsQixxQkFBQSxHQUFJYyxTQUFTLENBQUNxQixpQkFBaUIsY0FBQW5DLHFCQUFBLGVBQTNCQSxxQkFBQSxDQUE2QnhILE1BQU0sRUFBRTtNQUNoRyxNQUFNLElBQUk1QyxLQUFLLENBQUMscUJBQXFCa0wsU0FBUyxDQUFDdEosSUFBSSxLQUFLc0osU0FBUyxDQUFDbEcsT0FBTyxFQUFFLENBQUM7SUFDOUU7SUFDQSxJQUFJLENBQUFrRyxTQUFTLGFBQVRBLFNBQVMsdUJBQVRBLFNBQVMsQ0FBRUksS0FBSyxNQUFLLFNBQVMsS0FBQWpCLGtCQUFBLEdBQUlhLFNBQVMsQ0FBQ2xHLE9BQU8sY0FBQXFGLGtCQUFBLGVBQWpCQSxrQkFBQSxDQUFtQjFNLFFBQVEsQ0FBQyxxQkFBcUIsQ0FBQyxFQUFFO01BQ3hGLE1BQU02TyxZQUFZLEdBQUcsTUFBTW5NLHNCQUFzQixDQUFDbEQsSUFBSSxFQUFFdUMsT0FBTyxDQUFDO01BQ2hFLE1BQU0rTSxTQUFTLEdBQUcsTUFBTWhOLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSw0QkFBNEIsQ0FBQztNQUNoRixNQUFNZ04sUUFBUSxHQUFHbEwsTUFBTSxDQUFDQyxTQUFTLENBQUMsUUFBUSxFQUFFO1FBQUVDLElBQUksRUFBRTtNQUFzQixDQUFDLENBQUM7TUFDNUUsTUFBTXZGLE1BQU0sQ0FBQ3VRLFFBQVEsQ0FBQ2pMLFNBQVMsQ0FBQyxVQUFVLENBQUMsQ0FBQ2tMLEtBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQ2hMLFdBQVcsQ0FBQyxDQUFDO01BQ2xFLE1BQU01RCxPQUFPLEdBQUdpTSxXQUFXLENBQUMvTCxHQUFHLENBQUMsQ0FBQztRQUFFMk8sV0FBVyxHQUFHNU8sSUFBSSxDQUFDQyxHQUFHLENBQUMsQ0FBQztNQUMzRDhMLFFBQVEsQ0FBQ1csU0FBUyxDQUFDM00sT0FBTyxDQUFDO01BQzNCLE1BQU04TyxnQkFBZ0IsR0FBRzFQLElBQUksQ0FBQzJQLGVBQWUsQ0FBQzNPLFFBQVEsSUFBSSxJQUFJRyxHQUFHLENBQUNILFFBQVEsQ0FBQ0wsR0FBRyxDQUFDLENBQUMsQ0FBQyxDQUFDUyxRQUFRLEtBQUssNkNBQTZDLElBQ3ZJSixRQUFRLENBQUNULE9BQU8sQ0FBQyxDQUFDLENBQUNFLE1BQU0sQ0FBQyxDQUFDLEtBQUssTUFBTSxFQUFFO1FBQUVrQyxPQUFPLEVBQUU7TUFBUSxDQUFDLENBQUM7TUFDbEUsTUFBTTRNLFFBQVEsQ0FBQ2pMLFNBQVMsQ0FBQyxRQUFRLEVBQUU7UUFBRUMsSUFBSSxFQUFFO01BQXFDLENBQUMsQ0FBQyxDQUFDcUwsS0FBSyxDQUFDLENBQUM7TUFDMUYsTUFBTUMsUUFBUSxHQUFHLE1BQU1ILGdCQUFnQjtNQUN2QyxNQUFNSSxPQUFPLEdBQUcsTUFBTUQsUUFBUSxDQUFDN00sSUFBSSxDQUFDLENBQUM7TUFDckMsTUFBTStNLFdBQVcsR0FBRyxNQUFNN00sc0JBQXNCLENBQUNsRCxJQUFJLEVBQUV1QyxPQUFPLENBQUM7TUFDL0QsTUFBTXlOLEtBQUssR0FBRztRQUFFQyxNQUFNLEVBQUVaLFlBQVk7UUFBRWEsS0FBSyxFQUFFSCxXQUFXO1FBQUVJLFVBQVUsRUFBRWIsU0FBUyxDQUFDckksRUFBRTtRQUNoRm1KLGNBQWMsRUFBRVAsUUFBUSxDQUFDdFAsT0FBTyxDQUFDLENBQUMsQ0FBQ21DLE9BQU8sQ0FBQyxDQUFDLENBQUMsY0FBYyxDQUFDO1FBQUUyTixTQUFTLEVBQUVSLFFBQVEsQ0FBQ3RQLE9BQU8sQ0FBQyxDQUFDLENBQUMrUCxZQUFZLENBQUMsQ0FBQztRQUMxR3BQLE1BQU0sRUFBRTJPLFFBQVEsQ0FBQzNPLE1BQU0sQ0FBQyxDQUFDO1FBQUVGLFFBQVEsRUFBRThPLE9BQU87UUFBRWxQLE9BQU87UUFBRTZPLFdBQVc7UUFBRWMsWUFBWSxFQUFFMVAsSUFBSSxDQUFDQyxHQUFHLENBQUM7TUFBRSxDQUFDO01BQ2hHLE1BQU0wUCxXQUFXLEdBQUczRCxXQUFXLENBQUMvTCxHQUFHLENBQUMsQ0FBQztNQUNyQyxNQUFNMlAsU0FBUyxHQUFHN0QsUUFBUSxDQUFDOEQsbUJBQW1CLENBQUNWLEtBQUssRUFBRVEsV0FBVyxDQUFDO01BQ2xFLE1BQU16UixJQUFJLENBQUNrQixJQUFJLENBQUMsQ0FBQyxDQUFDeUIsTUFBTSxDQUFDLCtCQUErQixFQUFFO1FBQUVDLElBQUksRUFBRUMsSUFBSSxDQUFDQyxTQUFTLENBQUM7VUFBRW1PLEtBQUs7VUFBRVEsV0FBVztVQUFFQztRQUFVLENBQUMsQ0FBQztRQUFFM08sV0FBVyxFQUFFO01BQW1CLENBQUMsQ0FBQztNQUN2SmhDLGtCQUFrQixDQUFDbUIsR0FBRyxDQUFDbEMsSUFBSSxDQUFDa0IsSUFBSSxDQUFDLENBQUMsQ0FBQ0csTUFBTSxDQUFDLENBQUVXLElBQUksQ0FBQztRQUFFNE0sRUFBRSxFQUFFLElBQUk5TSxJQUFJLENBQUMsQ0FBQyxDQUFDK00sV0FBVyxDQUFDLENBQUM7UUFBRStDLHFCQUFxQixFQUFFRixTQUFTLENBQUNHLGdCQUFnQjtRQUNoSS9DLFFBQVEsRUFBRTRDLFNBQVMsQ0FBQzVDLFFBQVE7UUFBRXRMLE9BQU87UUFBRXdMLFNBQVMsRUFBRWdDLFdBQVcsQ0FBQ25NLE9BQU8sQ0FBQ0MsZUFBZTtRQUFFZ04sUUFBUSxFQUFFZixPQUFPLENBQUNlO01BQVMsQ0FBQyxDQUFDO01BQ3RILE1BQU03UixNQUFNLENBQUNzSCxJQUFJLENBQUM7UUFBQSxJQUFBd0sscUJBQUE7UUFBQSxRQUFBQSxxQkFBQSxHQUFZLENBQUMsTUFBTXhPLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQyxFQUFFcUIsT0FBTyxDQUFDQyxlQUFlLGNBQUFpTixxQkFBQSx1QkFBcEdBLHFCQUFBLENBQXNHdEMsVUFBVTtNQUFBLEdBQzVJO1FBQUU3TCxPQUFPLEVBQUV3SixnQkFBZ0IsQ0FBQzFHLE1BQU0sR0FBRyxHQUFHLEdBQUcsTUFBTyxHQUFHO01BQU8sQ0FBQyxDQUFDLENBQUNzTCxHQUFHLENBQUMxTyxJQUFJLENBQUMwTCxTQUFTLENBQUNTLFVBQVUsQ0FBQztNQUMvRjtJQUNGO0lBQ0EsSUFBSSxDQUFDLFNBQVMsRUFBRSxRQUFRLEVBQUUsWUFBWSxDQUFDLENBQUNoTyxRQUFRLENBQUN1TixTQUFTLGFBQVRBLFNBQVMsdUJBQVRBLFNBQVMsQ0FBRUksS0FBSyxDQUFDLElBQUlKLFNBQVMsQ0FBQ1EsV0FBVyxLQUFLLElBQUksRUFBRTtNQUFBLElBQUF5QyxrQkFBQSxFQUFBQyxjQUFBO01BQ3BHLE1BQU03QyxZQUFZLEdBQUcsTUFBTTlMLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSxxQ0FBcUMsQ0FBQztNQUM1RixNQUFNMEUsRUFBRSxJQUFBK0osa0JBQUEsR0FBRzVDLFlBQVksQ0FBQ3BGLElBQUksY0FBQWdJLGtCQUFBLHVCQUFqQkEsa0JBQUEsQ0FBbUIzQyxlQUFlO01BQzdDLE1BQU02QyxRQUFRLEdBQUdqSyxFQUFFLEdBQUcsTUFBTTNFLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSxvQ0FBb0MwRSxFQUFFLEVBQUUsQ0FBQyxHQUFHLElBQUk7TUFDdkcsTUFBTWxJLElBQUksQ0FBQ2tCLElBQUksQ0FBQyxDQUFDLENBQUN5QixNQUFNLENBQUMsZ0JBQWdCLEVBQUU7UUFBRUMsSUFBSSxFQUFFQyxJQUFJLENBQUNDLFNBQVMsQ0FBQztVQUFFa00sU0FBUztVQUMzRW1ELFFBQVEsRUFBRUEsUUFBUSxhQUFSQSxRQUFRLGdCQUFBRCxjQUFBLEdBQVJDLFFBQVEsQ0FBRWxJLElBQUksY0FBQWlJLGNBQUEsdUJBQWRBLGNBQUEsQ0FBZ0JFLGlCQUFpQjtVQUFFQyxPQUFPLEVBQUUsTUFBTS9NLE1BQU0sQ0FBQ2dOLFNBQVMsQ0FBQztRQUFFLENBQUMsQ0FBQztRQUFFdlAsV0FBVyxFQUFFO01BQW1CLENBQUMsQ0FBQztNQUN2SCxNQUFNLElBQUllLEtBQUssQ0FBQyxVQUFVa0wsU0FBUyxDQUFDSSxLQUFLLE9BQU9KLFNBQVMsQ0FBQ3RKLElBQUksS0FBS3NKLFNBQVMsQ0FBQ2xHLE9BQU8sRUFBRSxDQUFDO0lBQ3pGO0lBQ0EsSUFBSSxDQUFBa0csU0FBUyxhQUFUQSxTQUFTLHVCQUFUQSxTQUFTLENBQUVJLEtBQUssTUFBSyxtQkFBbUIsSUFBSyxDQUFBSixTQUFTLGFBQVRBLFNBQVMsdUJBQVRBLFNBQVMsQ0FBRUksS0FBSyxNQUFLLFNBQVMsSUFBSUosU0FBUyxDQUFDUSxXQUFXLEtBQUssSUFBSyxFQUFFO01BQ2xILE1BQU1FLE1BQU0sR0FBR3BLLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBRTtRQUFFQyxJQUFJLEVBQUUsb0JBQW9CO1FBQUVwQyxLQUFLLEVBQUU7TUFBSyxDQUFDLENBQUM7TUFDdEYsSUFBSTtRQUNGLE1BQU1zTSxNQUFNLENBQUNtQixLQUFLLENBQUM7VUFBRWpOLE9BQU8sRUFBRTtRQUFLLENBQUMsQ0FBQztNQUN2QyxDQUFDLENBQUMsT0FBTzJPLEtBQUssRUFBRTtRQUFBLElBQUFDLHFCQUFBO1FBQ2QsTUFBTUMsTUFBTSxHQUFHLE1BQU1sUCxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsd0NBQXdDLENBQUM7UUFDekYsSUFBSSxFQUFBZ1AscUJBQUEsR0FBQUMsTUFBTSxDQUFDNU4sT0FBTyxDQUFDQyxlQUFlLGNBQUEwTixxQkFBQSx1QkFBOUJBLHFCQUFBLENBQWdDL0MsVUFBVSxNQUFLVCxTQUFTLENBQUNTLFVBQVUsS0FBSSxNQUFNQyxNQUFNLENBQUNDLFdBQVcsQ0FBQ0MsT0FBTyxJQUFJQSxPQUFPLENBQUM1QyxJQUFJLENBQUMwQyxNQUFNLElBQUksQ0FBRUEsTUFBTSxDQUF1QkcsUUFBUSxJQUFJSCxNQUFNLENBQUNJLGNBQWMsQ0FBQyxDQUFDLENBQUNwSixNQUFNLEdBQUcsQ0FBQyxJQUFJcUosZ0JBQWdCLENBQUNMLE1BQU0sQ0FBQyxDQUFDTSxVQUFVLEtBQUssUUFBUSxDQUFDLENBQUMsR0FBRSxNQUFNdUMsS0FBSztRQUN0UjtNQUNGO01BQ0EsTUFBTXRTLE1BQU0sQ0FBQ3NILElBQUksQ0FBQyxZQUFZO1FBQUEsSUFBQW1MLHNCQUFBLEVBQUFDLHNCQUFBLEVBQUFDLGdCQUFBO1FBQzVCLE1BQU1ILE1BQU0sR0FBRyxNQUFNbFAsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLHdDQUF3QyxDQUFDO1FBQ3pGLE9BQU8sRUFBQWtQLHNCQUFBLEdBQUFELE1BQU0sQ0FBQzVOLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBNE4sc0JBQUEsdUJBQTlCQSxzQkFBQSxDQUFnQ2pELFVBQVUsTUFBS1QsU0FBUyxDQUFDUyxVQUFVLElBQ3JFLEVBQUFrRCxzQkFBQSxHQUFBRixNQUFNLENBQUM1TixPQUFPLENBQUNDLGVBQWUsY0FBQTZOLHNCQUFBLHVCQUE5QkEsc0JBQUEsQ0FBZ0N2RCxLQUFLLE1BQUssU0FBUyxJQUNuRCxFQUFBd0QsZ0JBQUEsR0FBQUgsTUFBTSxDQUFDMU4sUUFBUSxjQUFBNk4sZ0JBQUEsdUJBQWZBLGdCQUFBLENBQWtCNUQsU0FBUyxDQUFDdEosSUFBSSxDQUFDLE1BQUssYUFBYTtNQUMxRCxDQUFDLEVBQUU7UUFBRTlCLE9BQU8sRUFBRTtNQUFPLENBQUMsQ0FBQyxDQUFDTixJQUFJLENBQUMsSUFBSSxDQUFDO01BQ2xDO0lBQ0Y7SUFDQSxNQUFNdVAsU0FBUyxHQUFHLE1BQU10UCxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsb0NBQW9DNEssVUFBVSxFQUFFLENBQUM7SUFDcEcsSUFBSXlFLFNBQVMsQ0FBQzVJLElBQUksQ0FBQzZJLGFBQWEsS0FBSywwQkFBMEIsSUFBSXJGLFdBQVcsS0FBSyxDQUFDLElBQUlMLGdCQUFnQixDQUFDMUcsTUFBTSxFQUFFO01BQy9HLE1BQU1nQixRQUFRLEdBQUdtTCxTQUFTLENBQUM1SSxJQUFJLENBQUM4SSxPQUFPLENBQ3BDQyxNQUFNLENBQUVDLE1BQStCLElBQUtBLE1BQU0sQ0FBQ0MsV0FBVyxLQUFLLGNBQWMsQ0FBQyxDQUNsRm5MLEdBQUcsQ0FBRWtMLE1BQWtDLElBQUtBLE1BQU0sQ0FBQ2hKLElBQUksQ0FBQ3pFLElBQUksQ0FBQztNQUNoRXZGLE1BQU0sQ0FBQ3lILFFBQVEsRUFBRSx5RUFBeUUsQ0FBQyxDQUN4RnpFLE9BQU8sQ0FBQ2hELE1BQU0sQ0FBQ2tULGVBQWUsQ0FBQy9GLGdCQUFnQixDQUFDLENBQUM7SUFDdEQ7SUFDQW5OLE1BQU0sQ0FBQzBOLFFBQVEsQ0FBQzdDLEdBQUcsQ0FBQ3NELFVBQVUsQ0FBQyxFQUFFLGtEQUFrRCxDQUFDLENBQUM5SyxJQUFJLENBQUMsS0FBSyxDQUFDO0lBQ2hHLE1BQU04UCxhQUFhLEdBQUduUyxJQUFJLENBQUMyUCxlQUFlLENBQUMzTyxRQUFRLElBQUlBLFFBQVEsQ0FBQ0wsR0FBRyxDQUFDLENBQUMsQ0FBQ0gsUUFBUSxDQUFDLGNBQWMyTSxVQUFVLGdCQUFnQixDQUFDLElBQUluTSxRQUFRLENBQUNULE9BQU8sQ0FBQyxDQUFDLENBQUNFLE1BQU0sQ0FBQyxDQUFDLEtBQUssTUFBTSxFQUFFO01BQUVrQyxPQUFPLEVBQUU7SUFBUSxDQUFDLENBQUM7SUFDekwsTUFBTWtPLFFBQVEsR0FBR3hNLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBRTtNQUFFQyxJQUFJLEVBQUU7SUFBaUUsQ0FBQyxDQUFDO0lBQ3ZILE1BQU12RixNQUFNLENBQUM2UixRQUFRLENBQUMsQ0FBQ3VCLFdBQVcsQ0FBQztNQUFFelAsT0FBTyxFQUFFO0lBQU8sQ0FBQyxDQUFDO0lBQ3ZELE1BQU1rTyxRQUFRLENBQUNqQixLQUFLLENBQUMsQ0FBQztJQUN0QixNQUFNeUMsT0FBTyxHQUFHLE1BQU1GLGFBQWE7SUFDbkMsSUFBSSxDQUFDRSxPQUFPLENBQUN6UCxFQUFFLENBQUMsQ0FBQyxFQUFFLE1BQU0sSUFBSUMsS0FBSyxDQUFDLFFBQVF3UCxPQUFPLENBQUNuUixNQUFNLENBQUMsQ0FBQyxLQUFLLENBQUMsTUFBTW1SLE9BQU8sQ0FBQ3ZQLElBQUksQ0FBQyxDQUFDLEVBQUVDLEtBQUssQ0FBQyxDQUFDLEVBQUUsSUFBSSxDQUFDLEVBQUUsQ0FBQztJQUN4Ry9ELE1BQU0sQ0FBQyxDQUFDLE1BQU1xVCxPQUFPLENBQUNyUCxJQUFJLENBQUMsQ0FBQyxFQUFFZ0csSUFBSSxDQUFDOUgsTUFBTSxDQUFDLENBQUNtQixJQUFJLENBQUMsU0FBUyxDQUFDO0lBQzFEcUssUUFBUSxDQUFDNEYsR0FBRyxDQUFDbkYsVUFBVSxDQUFDO0lBQUVYLFdBQVcsRUFBRTtJQUN2QztJQUNBO0lBQ0FJLFFBQVEsR0FBRyxJQUFJeE4sc0JBQXNCLENBQUN5TixXQUFXLENBQUMvTCxHQUFHLENBQUMsQ0FBQyxFQUFFMEksUUFBUSxDQUFDO0lBQ2xFLElBQUlvSSxTQUFTLENBQUM1SSxJQUFJLENBQUM2SSxhQUFhLEtBQUssMEJBQTBCLElBQUl4RixlQUFlLEVBQUU7TUFDbEYsTUFBTTlGLHFCQUFxQixDQUFDdkcsSUFBSSxFQUFFdUMsT0FBTyxFQUFFOEosZUFBZSxDQUFDO0lBQzdEO0lBQ0EsSUFBSUcsV0FBVyxLQUFLLENBQUMsSUFBSUYsc0JBQXNCLEVBQUU7TUFBQSxJQUFBaUcscUJBQUE7TUFDL0MsTUFBTWpHLHNCQUFzQixDQUFDLENBQUM7TUFDOUI7TUFDQTtNQUNBLE1BQU1rRyxPQUFPLEdBQUcsTUFBTWxRLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQztNQUMxRnZELE1BQU0sRUFBQXVULHFCQUFBLEdBQUNDLE9BQU8sQ0FBQzVPLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBME8scUJBQUEsdUJBQS9CQSxxQkFBQSxDQUFpQ3hPLE1BQU0sQ0FBQyxDQUFDMUIsSUFBSSxDQUFDb0ssS0FBSyxDQUFDO01BQzNERyxRQUFRLEdBQUcsSUFBSXhOLHNCQUFzQixDQUFDeU4sV0FBVyxDQUFDL0wsR0FBRyxDQUFDLENBQUMsRUFBRTBSLE9BQU8sQ0FBQztJQUNuRTtJQUNBLElBQUloRyxXQUFXLEtBQUssQ0FBQyxFQUFFLE1BQU10SSxVQUFVLENBQUNsRSxJQUFJLEVBQUV1QyxPQUFPLENBQUMsQ0FBQyxDQUFDO0lBQ3hELElBQUkySixPQUFPLElBQUlNLFdBQVcsS0FBSyxDQUFDLEVBQUU7TUFDaEMsTUFBTTlHLGtCQUFrQixDQUFDMUYsSUFBSSxDQUFDO01BQzlCLE1BQU1rRSxVQUFVLENBQUNsRSxJQUFJLEVBQUV1QyxPQUFPLENBQUM7SUFDakM7SUFDQSxNQUFNdkQsTUFBTSxDQUFDc0gsSUFBSSxDQUFDLFlBQVk7TUFBQSxJQUFBbU0scUJBQUE7TUFDNUIsTUFBTUMsT0FBTyxHQUFHLE1BQU1wUSxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsd0NBQXdDLENBQUM7TUFDMUYsT0FBTyxFQUFBa1EscUJBQUEsR0FBQUMsT0FBTyxDQUFDOU8sT0FBTyxDQUFDQyxlQUFlLGNBQUE0TyxxQkFBQSx1QkFBL0JBLHFCQUFBLENBQWlDakUsVUFBVSxNQUFLVCxTQUFTLENBQUNTLFVBQVU7SUFDN0UsQ0FBQyxFQUFFO01BQUU3TCxPQUFPLEVBQUU7SUFBTyxDQUFDLENBQUMsQ0FBQ04sSUFBSSxDQUFDLElBQUksQ0FBQztFQUNwQztFQUNBLE1BQU0sSUFBSVEsS0FBSyxDQUFDLHFEQUFxRCxDQUFDO0FBQ3hFO0FBRUE5RCxJQUFJLENBQUMsOEZBQThGLEVBQUUsT0FBTztFQUFDaUI7QUFBSSxDQUFDLEtBQUs7RUFDckgsTUFBTXVDLE9BQU8sR0FBRywyQkFBMkIsR0FBR3JELFVBQVUsQ0FBQyxDQUFDO0VBQzFELE1BQU1jLElBQUksQ0FBQzJTLEtBQUssQ0FBQyxxQkFBcUIsRUFBRUEsS0FBSyxJQUFJQSxLQUFLLENBQUNDLE9BQU8sQ0FBQztJQUFDMVIsTUFBTSxFQUFDLEdBQUc7SUFDeEVZLFdBQVcsRUFBQyxrQkFBa0I7SUFBQ0gsSUFBSSxFQUFDQyxJQUFJLENBQUNDLFNBQVMsQ0FBQztNQUFDeVAsS0FBSyxFQUFDO0lBQW1FLENBQUM7RUFBQyxDQUFDLENBQUMsQ0FBQztFQUNwSSxNQUFNak4sTUFBTSxHQUFHLE1BQU1ILFVBQVUsQ0FBQ2xFLElBQUksRUFBRXVDLE9BQU8sQ0FBQztFQUM5QyxNQUFNdkQsTUFBTSxDQUFDcUYsTUFBTSxDQUFDQyxTQUFTLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQ3VPLGFBQWEsQ0FBQyxvQkFBb0IsQ0FBQztFQUMzRSxNQUFNeE8sTUFBTSxDQUFDeU8sVUFBVSxDQUFDLGFBQWEsRUFBRTtJQUFDM1EsS0FBSyxFQUFDO0VBQUksQ0FBQyxDQUFDLENBQUN5TixLQUFLLENBQUMsQ0FBQztFQUM1RCxNQUFNdkwsTUFBTSxDQUFDSyxPQUFPLENBQUMsMkJBQTJCLENBQUMsQ0FBQ3FPLElBQUksQ0FBQyxlQUFlLENBQUM7RUFDdkUsTUFBTTFPLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQyxxQkFBcUIsRUFBRTtJQUFDN1EsS0FBSyxFQUFDO0VBQUksQ0FBQyxDQUFDLENBQUM0USxJQUFJLENBQUMsbURBQW1ELENBQUM7RUFDdEgsTUFBTS9ULE1BQU0sQ0FBQ3FGLE1BQU0sQ0FBQ0ssT0FBTyxDQUFDLCtCQUErQixDQUFDLENBQUNKLFNBQVMsQ0FBQyxRQUFRLENBQUMsQ0FBQyxDQUFDMk8sWUFBWSxDQUFDLENBQUM7RUFDaEdqVSxNQUFNLENBQUMsQ0FBQyxNQUFNc0QsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLGtCQUFrQixDQUFDLEVBQUV1SCxJQUFJLENBQUMsQ0FBQzVFLFlBQVksQ0FBQyxDQUFDLENBQUM7RUFDbkYsTUFBTWxGLElBQUksQ0FBQ2tULE9BQU8sQ0FBQyxxQkFBcUIsQ0FBQztFQUN6QyxNQUFNN08sTUFBTSxDQUFDQyxTQUFTLENBQUMsUUFBUSxFQUFDO0lBQUNDLElBQUksRUFBQztFQUFpQyxDQUFDLENBQUMsQ0FBQ3FMLEtBQUssQ0FBQyxDQUFDO0VBQ2pGLE1BQU01USxNQUFNLENBQUNxRixNQUFNLENBQUNDLFNBQVMsQ0FBQyxPQUFPLENBQUMsQ0FBQyxDQUFDNk8sV0FBVyxDQUFDLENBQUMsQ0FBQztFQUN0RCxNQUFNblUsTUFBTSxDQUFDcUYsTUFBTSxDQUFDSyxPQUFPLENBQUMsK0JBQStCLENBQUMsQ0FBQ0osU0FBUyxDQUFDLFFBQVEsQ0FBQyxDQUFDLENBQUM4TixXQUFXLENBQUMsQ0FBQztFQUMvRixNQUFNZ0IsT0FBTyxHQUFHLE1BQU0sQ0FBQyxNQUFNcFQsSUFBSSxDQUFDTyxPQUFPLENBQUNVLEdBQUcsQ0FBQyxtQkFBbUIsQ0FBQyxFQUFFK0IsSUFBSSxDQUFDLENBQUM7RUFDMUVoRSxNQUFNLENBQUNvVSxPQUFPLENBQUNDLGdCQUFnQixDQUFDLENBQUNoUixJQUFJLENBQUMsR0FBRyxDQUFDO0FBQzVDLENBQUMsQ0FBQztBQUVGdEQsSUFBSSxDQUFDLCtFQUErRSxFQUFFLE9BQU87RUFBRWlCO0FBQUssQ0FBQyxFQUFFc1QsUUFBUSxLQUFLO0VBQ2xILE1BQU1DLE1BQWdCLEdBQUcsRUFBRTtFQUFFdlQsSUFBSSxDQUFDTSxFQUFFLENBQUMsV0FBVyxFQUFFZ1IsS0FBSyxJQUFJaUMsTUFBTSxDQUFDeFMsSUFBSSxDQUFDdVEsS0FBSyxDQUFDekosT0FBTyxDQUFDLENBQUM7RUFDdEYsTUFBTXRGLE9BQU8sR0FBRyxnQkFBZ0IsR0FBR3JELFVBQVUsQ0FBQyxDQUFDO0VBQy9DLE1BQU1tRixNQUFNLEdBQUcsTUFBTUgsVUFBVSxDQUFDbEUsSUFBSSxFQUFFdUMsT0FBTyxDQUFDO0VBQzlDLE1BQU04QixNQUFNLENBQUN5TyxVQUFVLENBQUMsYUFBYSxFQUFFO0lBQUUzUSxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQ3lOLEtBQUssQ0FBQyxDQUFDO0VBQy9ELE1BQU12TCxNQUFNLENBQUNLLE9BQU8sQ0FBQywyQkFBMkIsQ0FBQyxDQUFDcU8sSUFBSSxDQUFDLFdBQVcsQ0FBQztFQUNuRSxNQUFNMU8sTUFBTSxDQUFDMk8sVUFBVSxDQUFDLHFCQUFxQixFQUFFO0lBQUU3USxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQzRRLElBQUksQ0FBQyw2YkFBNmIsQ0FBQztFQUNuZ0IsTUFBTTFPLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQyxrQkFBa0IsRUFBRTtJQUFFN1EsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDLENBQUM0USxJQUFJLENBQUMsaU5BQWlOLENBQUM7RUFDcFIsTUFBTTFPLE1BQU0sQ0FBQ3lPLFVBQVUsQ0FBQyxjQUFjLEVBQUU7SUFBRTNRLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDeU4sS0FBSyxDQUFDLENBQUM7RUFDaEUsS0FBSyxNQUFNLENBQUN6SixLQUFLLEVBQUVxTixLQUFLLENBQUMsSUFBSSxDQUFDLENBQUMsVUFBVSxFQUFFLEdBQUcsQ0FBQyxFQUFFLENBQUMsWUFBWSxFQUFFLEdBQUcsQ0FBQyxFQUFFLENBQUMsVUFBVSxFQUFFLEdBQUcsQ0FBQyxFQUFFLENBQUMsU0FBUyxFQUFFLEdBQUcsQ0FBQyxDQUFDLEVBQUUsTUFBTW5QLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQyxHQUFHN00sS0FBSyx1QkFBdUIsRUFBRTtJQUFFaEUsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDLENBQUM0USxJQUFJLENBQUNTLEtBQUssQ0FBQztFQUNqTSxNQUFNQyxZQUFZLEdBQUd6VCxJQUFJLENBQUMwVCxjQUFjLENBQUNuVCxPQUFPO0lBQUEsSUFBQW9ULHFCQUFBO0lBQUEsT0FBSXBULE9BQU8sQ0FBQ0ksR0FBRyxDQUFDLENBQUMsQ0FBQ2lULFFBQVEsQ0FBQyxpQkFBaUIsQ0FBQyxJQUN4RnJULE9BQU8sQ0FBQ0UsTUFBTSxDQUFDLENBQUMsS0FBSyxNQUFNLElBQUksRUFBQWtULHFCQUFBLEdBQUFwVCxPQUFPLENBQUMrUCxZQUFZLENBQUMsQ0FBQyxjQUFBcUQscUJBQUEsZ0JBQUFBLHFCQUFBLEdBQXRCQSxxQkFBQSxDQUF3QkUsY0FBYyxjQUFBRixxQkFBQSx1QkFBdENBLHFCQUFBLENBQXdDRyxNQUFNLE1BQUssT0FBTztFQUFBLEVBQUM7RUFDL0Y7RUFDQSxLQUFLLElBQUlyUCxJQUFJLEdBQUcsQ0FBQyxFQUFFQSxJQUFJLEdBQUcsRUFBRSxFQUFFQSxJQUFJLEVBQUUsRUFBRTtJQUNwQyxNQUFNc1AsTUFBTSxHQUFHMVAsTUFBTSxDQUFDSyxPQUFPLENBQUMsK0JBQStCLENBQUMsQ0FBQ0osU0FBUyxDQUFDLFFBQVEsQ0FBQztJQUNsRixNQUFNdEYsTUFBTSxDQUFDK1UsTUFBTSxDQUFDLENBQUMzQixXQUFXLENBQUMsQ0FBQztJQUNsQyxNQUFNN04sSUFBSSxHQUFHLE1BQU13UCxNQUFNLENBQUMxQyxTQUFTLENBQUMsQ0FBQztJQUNyQyxNQUFNMEMsTUFBTSxDQUFDbkUsS0FBSyxDQUFDLENBQUM7SUFDcEIsSUFBSXJMLElBQUksS0FBSyxZQUFZLEVBQUU7SUFDM0IsSUFBSUUsSUFBSSxLQUFLLENBQUMsRUFBRSxNQUFNLElBQUk1QixLQUFLLENBQUMscUNBQXFDLENBQUM7RUFDeEU7RUFDQSxNQUFNbVIsU0FBUyxHQUFHLENBQUMsTUFBTVAsWUFBWSxFQUFFbkQsWUFBWSxDQUFDLENBQUMsQ0FBQ3VELGNBQWMsQ0FBQ0ksY0FBYztFQUNuRmpWLE1BQU0sQ0FBQ2dWLFNBQVMsQ0FBQ0UsWUFBWSxFQUFFLG9FQUFvRSxDQUFDLENBQUNsUyxPQUFPLENBQUMsQ0FBQyxpQkFBaUIsQ0FBQyxDQUFDO0VBQ2pJLE1BQU1tUyxVQUFVLEdBQUcsTUFBTWxJLHFCQUFxQixDQUFDak0sSUFBSSxFQUFFdUMsT0FBTyxFQUFFLElBQUksRUFDaEUsQ0FBQyxRQUFRLEVBQUUsZ0JBQWdCLEVBQUUsU0FBUyxFQUFFLGtCQUFrQixFQUFFLFlBQVksQ0FBQyxDQUFDO0VBQzVFLE1BQU02UixTQUFTLEdBQUcsTUFBTWhMLGVBQWUsQ0FBQ3BKLElBQUksRUFBRXVDLE9BQU8sRUFBRSxDQUFDLENBQUM7RUFDekR2RCxNQUFNLENBQUNvVixTQUFTLENBQUNoSyxVQUFVLENBQUNzQixxQkFBcUIsQ0FBQyxDQUFDaEIsc0JBQXNCLENBQUMsQ0FBQyxDQUFDO0VBQzVFMUwsTUFBTSxDQUFDb1YsU0FBUyxDQUFDaEssVUFBVSxDQUFDQyxjQUFjLENBQUNPLG9CQUFvQixDQUFDLENBQUMxRixZQUFZLENBQUMsQ0FBQyxDQUFDO0VBQ2hGLE1BQU1tUCxRQUFRLEdBQUdyVSxJQUFJLENBQUMyUCxlQUFlLENBQUMzTyxRQUFRLElBQUlBLFFBQVEsQ0FBQ0wsR0FBRyxDQUFDLENBQUMsQ0FBQ0gsUUFBUSxDQUFDLFNBQVMyVCxVQUFVLENBQUMxSCxLQUFLLFNBQVMsQ0FBQyxJQUN4R3pMLFFBQVEsQ0FBQ1QsT0FBTyxDQUFDLENBQUMsQ0FBQ0UsTUFBTSxDQUFDLENBQUMsS0FBSyxNQUFNLENBQUM7RUFDNUMsTUFBTTRELE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBRTtJQUFFQyxJQUFJLEVBQUUsZ0JBQWdCO0lBQUVwQyxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQ3lOLEtBQUssQ0FBQyxDQUFDO0VBQ2pGNVEsTUFBTSxDQUFDLENBQUMsTUFBTXFWLFFBQVEsRUFBRXpSLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQ1AsSUFBSSxDQUFDLElBQUksQ0FBQztFQUN4QyxNQUFNckQsTUFBTSxDQUFDcUYsTUFBTSxDQUFDLENBQUMwTSxHQUFHLENBQUN2TSxXQUFXLENBQUMsQ0FBQztFQUN0QyxNQUFNTixVQUFVLENBQUNsRSxJQUFJLEVBQUV1QyxPQUFPLENBQUM7RUFDL0J2RCxNQUFNLENBQUMsQ0FBQyxNQUFNc0QsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLGtCQUFrQixDQUFDLEVBQUV1SCxJQUFJLENBQUMsQ0FBQzVFLFlBQVksQ0FBQyxDQUFDLENBQUM7RUFDbkZsRyxNQUFNLENBQUN1VSxNQUFNLENBQUMsQ0FBQ3ZSLE9BQU8sQ0FBQyxFQUFFLENBQUM7RUFDMUIsTUFBTXNSLFFBQVEsQ0FBQzVSLE1BQU0sQ0FBQyxVQUFVLEVBQUU7SUFBRUMsSUFBSSxFQUFFQyxJQUFJLENBQUNDLFNBQVMsQ0FBQztNQUFFVSxPQUFPO01BQUUsR0FBRzRSLFVBQVU7TUFBRSxHQUFHQztJQUFVLENBQUMsQ0FBQztJQUFFdFMsV0FBVyxFQUFFO0VBQW1CLENBQUMsQ0FBQztBQUN4SSxDQUFDLENBQUM7QUFFRixLQUFLLE1BQU13UyxVQUFVLElBQUksQ0FBQyxLQUFLLEVBQUUsWUFBWSxDQUFDLEVBQUU7RUFDOUN2VixJQUFJLENBQUMsZ0JBQWdCdVYsVUFBVSw4RUFBOEUsRUFBRSxPQUFPO0lBQUV0VTtFQUFLLENBQUMsRUFBRXNULFFBQVEsS0FBSztJQUMzSSxNQUFNL1EsT0FBTyxHQUFHLG1CQUFtQixHQUFHckQsVUFBVSxDQUFDLENBQUM7SUFDbEQsTUFBTW1GLE1BQU0sR0FBRyxNQUFNSCxVQUFVLENBQUNsRSxJQUFJLEVBQUV1QyxPQUFPLENBQUM7SUFDOUMsTUFBTThCLE1BQU0sQ0FBQ3lPLFVBQVUsQ0FBQyxhQUFhLEVBQUU7TUFBRTNRLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDeU4sS0FBSyxDQUFDLENBQUM7SUFDL0QsTUFBTXZMLE1BQU0sQ0FBQ0ssT0FBTyxDQUFDLDJCQUEyQixDQUFDLENBQUNxTyxJQUFJLENBQUMsb0JBQW9CLENBQUM7SUFDNUUsTUFBTTFPLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQyxxQkFBcUIsRUFBRTtNQUFFN1EsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUM0USxJQUFJLENBQUN1QixVQUFVLEtBQUssS0FBSyxHQUNyRix5RUFBeUUsR0FDekUsNkhBQTZIQSxVQUFVLHNEQUFzRCxDQUFDO0lBQ2xNLE1BQU1qUSxNQUFNLENBQUN5TyxVQUFVLENBQUMsaUJBQWlCLEVBQUU7TUFBRTNRLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDeU4sS0FBSyxDQUFDLENBQUM7SUFDbkUsTUFBTXZMLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLE9BQU8sRUFBRTtNQUFFQyxJQUFJLEVBQUU7SUFBYSxDQUFDLENBQUMsQ0FBQ2dRLEtBQUssQ0FBQyxDQUFDO0lBQy9ELE1BQU1sUSxNQUFNLENBQUN5TyxVQUFVLENBQUMsY0FBYyxFQUFFO01BQUUzUSxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUMsQ0FBQ3lOLEtBQUssQ0FBQyxDQUFDO0lBQ2hFLElBQUkwRSxVQUFVLEtBQUssS0FBSyxFQUFFO01BQ3hCLE1BQU10VixNQUFNLENBQUNxRixNQUFNLENBQUNDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7UUFBRUMsSUFBSSxFQUFFLFlBQVk7UUFBRXBDLEtBQUssRUFBRTtNQUFLLENBQUMsQ0FBQyxDQUFDLENBQUM4USxZQUFZLENBQUMsQ0FBQztNQUM1RixNQUFNNU8sTUFBTSxDQUFDMk8sVUFBVSxDQUFDLHdCQUF3QixFQUFFO1FBQUU3USxLQUFLLEVBQUU7TUFBSyxDQUFDLENBQUMsQ0FBQ3FTLFlBQVksQ0FBQyxLQUFLLENBQUM7TUFDdEYsTUFBTXhWLE1BQU0sQ0FBQ3FGLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQyw4QkFBOEIsRUFBRTtRQUFFN1EsS0FBSyxFQUFFO01BQUssQ0FBQyxDQUFDLENBQUMsQ0FBQ3NTLFdBQVcsQ0FBQyxFQUFFLENBQUM7TUFDaEcsTUFBTXpWLE1BQU0sQ0FBQ3FGLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBRTtRQUFFQyxJQUFJLEVBQUUsWUFBWTtRQUFFcEMsS0FBSyxFQUFFO01BQUssQ0FBQyxDQUFDLENBQUMsQ0FBQzhRLFlBQVksQ0FBQyxDQUFDO01BQzVGLEtBQUssTUFBTTFPLElBQUksSUFBSSxDQUFDLGFBQWEsRUFBRSxtQkFBbUIsRUFBRSxtQkFBbUIsRUFBRSxtQkFBbUIsRUFBRSxtQkFBbUIsRUFBRSxjQUFjLEVBQUUsY0FBYyxDQUFDLEVBQUU7UUFDdEosTUFBTUYsTUFBTSxDQUFDMk8sVUFBVSxDQUFDLEdBQUd6TyxJQUFJLGFBQWEsRUFBRTtVQUFFcEMsS0FBSyxFQUFFO1FBQUssQ0FBQyxDQUFDLENBQUNxUyxZQUFZLENBQUMsS0FBSyxDQUFDO01BQ3BGO01BQ0EsTUFBTW5RLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQyxxQkFBcUIsRUFBRTtRQUFFN1EsS0FBSyxFQUFFO01BQUssQ0FBQyxDQUFDLENBQUNxUyxZQUFZLENBQUMsT0FBTyxDQUFDO01BQ3JGLE1BQU14VixNQUFNLENBQUNxRixNQUFNLENBQUMyTyxVQUFVLENBQUMsOEJBQThCLEVBQUU7UUFBRTdRLEtBQUssRUFBRTtNQUFLLENBQUMsQ0FBQyxDQUFDLENBQUNzUyxXQUFXLENBQUMsS0FBSyxDQUFDO01BQ25HLE1BQU1wUSxNQUFNLENBQUMyTyxVQUFVLENBQUMscUJBQXFCLEVBQUU7UUFBRTdRLEtBQUssRUFBRTtNQUFLLENBQUMsQ0FBQyxDQUFDcVMsWUFBWSxDQUFDLGFBQWEsQ0FBQztJQUM3RjtJQUNBLE1BQU14VixNQUFNLENBQUNxRixNQUFNLENBQUNDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBRUMsSUFBSSxFQUFFLFlBQVk7TUFBRXBDLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDLENBQUM4USxZQUFZLENBQUMsQ0FBQztJQUM1RixNQUFNNU8sTUFBTSxDQUFDMk8sVUFBVSxDQUFDLDJCQUEyQixFQUFFO01BQUU3USxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUMsQ0FBQ3FTLFlBQVksQ0FBQyxZQUFZLENBQUM7SUFDaEcsTUFBTXhWLE1BQU0sQ0FBQ3FGLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQywyQkFBMkIsRUFBRTtNQUFFN1EsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQ3NTLFdBQVcsQ0FBQyxFQUFFLENBQUM7SUFDN0YsTUFBTXpWLE1BQU0sQ0FBQ3FGLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBRTtNQUFFQyxJQUFJLEVBQUUsWUFBWTtNQUFFcEMsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQzhRLFlBQVksQ0FBQyxDQUFDO0lBQzVGLE1BQU01TyxNQUFNLENBQUMyTyxVQUFVLENBQUMsMkJBQTJCLEVBQUU7TUFBRTdRLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDcVMsWUFBWSxDQUFDLFlBQVksQ0FBQztJQUNoRyxNQUFNblEsTUFBTSxDQUFDQyxTQUFTLENBQUMsUUFBUSxFQUFFO01BQUVDLElBQUksRUFBRSxZQUFZO01BQUVwQyxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUMsQ0FBQ3lOLEtBQUssQ0FBQyxDQUFDO0lBQzdFLE1BQU01USxNQUFNLENBQUNpTixxQkFBcUIsQ0FBQ2pNLElBQUksRUFBRXVDLE9BQU8sRUFBRSxJQUFJLEVBQUUsQ0FBQyxhQUFhLEVBQUUsbUJBQW1CLEVBQUUsbUJBQW1CLEVBQUUsbUJBQW1CLEVBQUUsbUJBQW1CLEVBQUUsY0FBYyxFQUFFLGNBQWMsQ0FBQyxFQUFFLEtBQUssRUFBRW1TLFNBQVMsRUFBRUEsU0FBUyxFQUFFLElBQUksQ0FBQyxDQUFDLENBQzdOQyxPQUFPLENBQUNDLE9BQU8sQ0FBQyxtREFBbUQsQ0FBQztJQUN2RSxNQUFNcEwsUUFBUSxHQUFHLE1BQU1sSCxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsMkJBQTJCLENBQUM7SUFDOUUsTUFBTXNTLFFBQVEsR0FBR3JMLFFBQVEsQ0FBQzVGLE9BQU8sQ0FBQ0MsZUFBZSxDQUFDdUwsaUJBQXVDO0lBQ3pGcFEsTUFBTSxDQUFDNlYsUUFBUSxDQUFDL04sR0FBRyxDQUFDRSxJQUFJLElBQUlBLElBQUksQ0FBQzhOLElBQUksQ0FBQyxDQUFDLENBQUNDLFNBQVMsQ0FBQyw4QkFBOEIsQ0FBQztJQUNqRi9WLE1BQU0sQ0FBQ3dLLFFBQVEsQ0FBQzFGLFFBQVEsQ0FBQ1IsVUFBVSxDQUFDLENBQUNqQixJQUFJLENBQUMsYUFBYSxDQUFDO0lBQ3hEckQsTUFBTSxDQUFDd0ssUUFBUSxDQUFDd0wsZUFBZSxDQUFDMVIsVUFBVSxDQUFDaUgsUUFBUSxDQUFDLENBQUNsSSxJQUFJLENBQUMsS0FBSyxDQUFDO0lBQ2hFLE1BQU00UyxRQUFRLEdBQUd6TCxRQUFRLENBQUN3TCxlQUFlLENBQUMxUixVQUFVLENBQUMyUixRQUFRO0lBQzdEalcsTUFBTSxDQUFDaVcsUUFBUSxDQUFDWCxVQUFVLEtBQUssS0FBSyxHQUFHLG1CQUFtQixHQUFHLGtCQUFrQixDQUFDLENBQUMsQ0FBQ2pTLElBQUksQ0FBQyxLQUFLLENBQUM7SUFDN0YsTUFBTTZTLGNBQWMsR0FBRzdRLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBRTtNQUFDQyxJQUFJLEVBQUU7SUFBZ0MsQ0FBQyxDQUFDO0lBQzNGLE1BQU12RixNQUFNLENBQUNrVyxjQUFjLENBQUMsQ0FBQ3JDLGFBQWEsQ0FBQ3lCLFVBQVUsS0FBSyxLQUFLLEdBQUcsbUJBQW1CLEdBQUcsa0JBQWtCLENBQUM7SUFDM0csTUFBTXRWLE1BQU0sQ0FBQ2tXLGNBQWMsQ0FBQzVRLFNBQVMsQ0FBQyxNQUFNLEVBQUU7TUFBQ0MsSUFBSSxFQUFFO0lBQStCLENBQUMsQ0FBQyxDQUFDaUwsS0FBSyxDQUFDLENBQUMsQ0FBQyxDQUM1RjJGLGVBQWUsQ0FBQyxNQUFNLEVBQUUsSUFBSUMsTUFBTSxDQUFDLDRCQUE0QjdTLE9BQU8sRUFBRSxDQUFDLENBQUM7SUFDN0V2RCxNQUFNLENBQUN3SyxRQUFRLENBQUMxRixRQUFRLENBQUN1UixVQUFVLENBQUMsQ0FBQ2hULElBQUksQ0FBQyxPQUFPLENBQUM7SUFDbEQsSUFBSWlTLFVBQVUsS0FBSyxLQUFLLEVBQUU7TUFDeEJ0VixNQUFNLENBQUN3SyxRQUFRLENBQUNsRyxVQUFVLENBQUNnUyxxQkFBcUIsQ0FBQ0MsR0FBRyxDQUFDclUsTUFBTSxDQUFDLENBQUNtQixJQUFJLENBQUMsaUJBQWlCLENBQUM7TUFDcEZyRCxNQUFNLENBQUN3SyxRQUFRLENBQUNsRyxVQUFVLENBQUNrUyxvQkFBb0IsQ0FBQ0MsT0FBTyxDQUFDQyxNQUFNLENBQUMsQ0FBQ3JULElBQUksQ0FBQyxvQ0FBb0MsQ0FBQztJQUM1RztJQUNBLE1BQU1zVCxVQUFVLEdBQUcsTUFBTXRRLFVBQVUsQ0FBQ3JGLElBQUksRUFBRXVDLE9BQU8sRUFBRSxxQkFBcUIsQ0FBQztJQUN6RXZELE1BQU0sQ0FBQzJXLFVBQVUsQ0FBQ2xRLE1BQU0sQ0FBQyxDQUFDaUYsc0JBQXNCLENBQUMsQ0FBQyxDQUFDO0lBQ25EMUwsTUFBTSxDQUFDMlcsVUFBVSxDQUFDekgsS0FBSyxDQUFDbEgsSUFBSSxJQUFJLENBQUMscUJBQXFCLENBQUNqSSxJQUFJLENBQUNpSSxJQUFJLENBQUNzTixVQUFVLENBQUMsQ0FBQyxDQUFDLENBQUNqUyxJQUFJLENBQUMsSUFBSSxDQUFDO0lBQ3pGLE1BQU1vRSxRQUFRLEdBQUcsTUFBTXBCLFVBQVUsQ0FBQ3JGLElBQUksRUFBRXVDLE9BQU8sRUFBRSxnQkFBZ0IsQ0FBQztJQUNsRXZELE1BQU0sQ0FBQ3lILFFBQVEsQ0FBQ3lILEtBQUssQ0FBQ2xILElBQUksSUFBSUEsSUFBSSxDQUFDNE8sTUFBTSxLQUFLLFlBQVksQ0FBQyxDQUFDLENBQUN2VCxJQUFJLENBQUMsSUFBSSxDQUFDO0lBQ3ZFLElBQUlpUyxVQUFVLEtBQUssS0FBSyxFQUFFO01BQ3hCLE1BQU0xTixPQUFPLEdBQUcsTUFBTXZCLFVBQVUsQ0FBQ3JGLElBQUksRUFBRXVDLE9BQU8sRUFBRSxTQUFTLENBQUM7TUFDMUR2RCxNQUFNLENBQUM0SCxPQUFPLENBQUNtRixJQUFJLENBQUMvRSxJQUFJLElBQUlBLElBQUksQ0FBQ3pDLElBQUksS0FBSyw4QkFBOEIsSUFBSXlDLElBQUksQ0FBQzZPLElBQUksS0FBSyxNQUFNLENBQUMsQ0FBQyxDQUFDeFQsSUFBSSxDQUFDLElBQUksQ0FBQztJQUMvRztJQUNBckQsTUFBTSxDQUFDLENBQUMsTUFBTXNELFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSxrQkFBa0IsQ0FBQyxFQUFFdUgsSUFBSSxDQUFDLENBQUM1RSxZQUFZLENBQUMsQ0FBQyxDQUFDO0lBQ25GLE1BQU1vTyxRQUFRLENBQUM1UixNQUFNLENBQUMsd0JBQXdCLEVBQUU7TUFBRUMsSUFBSSxFQUFFQyxJQUFJLENBQUNDLFNBQVMsQ0FBQztRQUFFVSxPQUFPO1FBQUUrUixVQUFVO1FBQUVPO01BQVMsQ0FBQyxDQUFDO01BQUUvUyxXQUFXLEVBQUU7SUFBbUIsQ0FBQyxDQUFDO0VBQy9JLENBQUMsQ0FBQztBQUNKO0FBRUEvQyxJQUFJLENBQUMsZ0ZBQWdGLEVBQUUsT0FBTztFQUFFaUI7QUFBSyxDQUFDLEVBQUVzVCxRQUFRLEtBQUs7RUFDbkgsTUFBTUMsTUFBZ0IsR0FBRyxFQUFFO0VBQUV2VCxJQUFJLENBQUNNLEVBQUUsQ0FBQyxXQUFXLEVBQUVnUixLQUFLLElBQUlpQyxNQUFNLENBQUN4UyxJQUFJLENBQUN1USxLQUFLLENBQUN6SixPQUFPLENBQUMsQ0FBQztFQUN0RixNQUFNdEYsT0FBTyxHQUFHLGdCQUFnQixHQUFHckQsVUFBVSxDQUFDLENBQUM7RUFDL0MsTUFBTXVOLEtBQUssR0FBR3ZOLFVBQVUsQ0FBQyxDQUFDO0VBQzFCLE1BQU00VyxRQUFRLEdBQUcsTUFBTTdXLFFBQVEsQ0FBQyxJQUFJa0MsR0FBRyxDQUFDLHdDQUF3QyxFQUFFNFUsTUFBTSxDQUFDQyxJQUFJLENBQUNyVixHQUFHLENBQUMsRUFBRSxNQUFNLENBQUM7RUFDM0csTUFBTXNWLFFBQVEsR0FBR3JVLElBQUksQ0FBQ3NVLEtBQUssQ0FBQyxNQUFNalgsUUFBUSxDQUFDLElBQUlrQyxHQUFHLENBQUMseUNBQXlDLEVBQUU0VSxNQUFNLENBQUNDLElBQUksQ0FBQ3JWLEdBQUcsQ0FBQyxFQUFFLE1BQU0sQ0FBQyxDQUFDO0VBQ3hILE1BQU13VixRQUFRLEdBQUd2VSxJQUFJLENBQUNzVSxLQUFLLENBQUMsTUFBTWpYLFFBQVEsQ0FBQyxJQUFJa0MsR0FBRyxDQUFDLCtDQUErQyxFQUFFNFUsTUFBTSxDQUFDQyxJQUFJLENBQUNyVixHQUFHLENBQUMsRUFBRSxNQUFNLENBQUMsQ0FBQztFQUM5SCxNQUFNeVYsTUFBTSxHQUFHTixRQUFRLENBQUNPLE9BQU8sQ0FBQyxpQkFBaUIsRUFBRSxhQUFhLEdBQUc1SixLQUFLLENBQUM7RUFDekUsTUFBTWxOLHVCQUF1QixDQUFDUyxJQUFJLEVBQUV1QyxPQUFPLENBQUM7RUFDNUM7RUFDQTtFQUNBLE1BQU0zQixPQUFPLEdBQUcsTUFBTVosSUFBSSxDQUFDTyxPQUFPLENBQUMrVixJQUFJLENBQUMsNkJBQTZCLEVBQUU7SUFDckU1VCxPQUFPLEVBQUU7TUFBRSxjQUFjLEVBQUVIO0lBQVEsQ0FBQztJQUFFSSxPQUFPLEVBQUUsTUFBTztJQUN0RHFHLElBQUksRUFBRTtNQUFFb04sTUFBTTtNQUFFdkMsY0FBYyxFQUFFO1FBQUVDLE1BQU0sRUFBRSxPQUFPO1FBQUUvUCxNQUFNLEVBQUUwSSxLQUFLO1FBQUU4SixZQUFZLEVBQUVyWCxVQUFVLENBQUMsQ0FBQztRQUMxRnNYLE1BQU0sRUFBRSwyQkFBMkI7UUFBRXZDLGNBQWMsRUFBRTtVQUFFLEdBQUdnQyxRQUFRLENBQUNoQyxjQUFjO1VBQUV6USxVQUFVLEVBQUVqQixPQUFPO1VBQUV3QixNQUFNLEVBQUUwSTtRQUFNO01BQUU7SUFBRTtFQUM5SCxDQUFDLENBQUM7RUFDRixJQUFJLENBQUM3TCxPQUFPLENBQUNnQyxFQUFFLENBQUMsQ0FBQyxFQUFFLE1BQU0sSUFBSUMsS0FBSyxDQUFDLFFBQVFqQyxPQUFPLENBQUNNLE1BQU0sQ0FBQyxDQUFDLEtBQUssQ0FBQyxNQUFNTixPQUFPLENBQUNrQyxJQUFJLENBQUMsQ0FBQyxFQUFFQyxLQUFLLENBQUMsQ0FBQyxFQUFFLElBQUksQ0FBQyxFQUFFLENBQUM7RUFDeEcsTUFBTW1CLFVBQVUsQ0FBQ2xFLElBQUksRUFBRXVDLE9BQU8sQ0FBQztFQUMvQixNQUFNNFIsVUFBVSxHQUFHLE1BQU1sSSxxQkFBcUIsQ0FBQ2pNLElBQUksRUFBRXVDLE9BQU8sRUFBRSxLQUFLLEVBQUUsRUFBRSxFQUFFLElBQUksRUFBRTRULFFBQVEsQ0FBQ3ZQLE9BQU8sQ0FBQztFQUNoRzVILE1BQU0sQ0FBQ21WLFVBQVUsQ0FBQzFILEtBQUssQ0FBQyxDQUFDcEssSUFBSSxDQUFDb0ssS0FBSyxDQUFDO0VBQ3BDLE1BQU1oRyxRQUFRLEdBQUcsTUFBTXBCLFVBQVUsQ0FBQ3JGLElBQUksRUFBRXVDLE9BQU8sRUFBRSxnQkFBZ0IsQ0FBQztFQUNsRXZELE1BQU0sQ0FBQ3lILFFBQVEsQ0FBQ3NMLE1BQU0sQ0FBQy9LLElBQUksSUFBSUEsSUFBSSxDQUFDd0IsV0FBVyxLQUFLLGtCQUFrQixDQUFDLENBQUMsQ0FBQ3RELFlBQVksQ0FBQyxHQUFHLENBQUM7RUFDMUZsRyxNQUFNLENBQUN5SCxRQUFRLENBQUNzTCxNQUFNLENBQUMvSyxJQUFJLElBQUlBLElBQUksQ0FBQ3dCLFdBQVcsS0FBSyxvQkFBb0IsQ0FBQyxDQUFDLENBQUN0RCxZQUFZLENBQUMsR0FBRyxDQUFDO0VBQzVGbEcsTUFBTSxDQUFDeUgsUUFBUSxDQUFDc0wsTUFBTSxDQUFDL0ssSUFBSSxJQUFJQSxJQUFJLENBQUN3QixXQUFXLEtBQUssS0FBSyxDQUFDLENBQUMvQyxNQUFNLENBQUMsQ0FBQ2lGLHNCQUFzQixDQUFDLEVBQUUsQ0FBQztFQUM3RixNQUFNMEosU0FBUyxHQUFHLE1BQU1oTCxlQUFlLENBQUNwSixJQUFJLEVBQUV1QyxPQUFPLEVBQUUsSUFBSSxDQUFDO0VBQzVELE1BQU1rVSxpQkFBaUIsR0FBRyxJQUFJbEwsR0FBRyxDQUFDNkksU0FBUyxDQUFDaEssVUFBVSxDQUFDQyxjQUFjLENBQUNPLG9CQUFvQixDQUN2RlksT0FBTyxDQUFFeEUsSUFBOEIsSUFBS0EsSUFBSSxDQUFDeUUsVUFBVSxDQUFDLENBQUM7RUFDaEV6TSxNQUFNLENBQUN5WCxpQkFBaUIsQ0FBQzlLLElBQUksQ0FBQyxDQUFDdEosSUFBSSxDQUFDLEdBQUcsQ0FBQztFQUN4Q3JELE1BQU0sQ0FBQ29WLFNBQVMsQ0FBQ2hLLFVBQVUsQ0FBQ3NCLHFCQUFxQixDQUFDLENBQUNySixJQUFJLENBQUMsSUFBSSxDQUFDO0VBQzdELE1BQU1rRSxxQkFBcUIsQ0FBQ3ZHLElBQUksRUFBRXVDLE9BQU8sRUFBRTRULFFBQVEsQ0FBQ3ZQLE9BQU8sQ0FBQztFQUM1RDVILE1BQU0sQ0FBQ29WLFNBQVMsQ0FBQ3BJLEdBQUcsQ0FBQyxDQUFDM0osSUFBSSxDQUFDOFIsVUFBVSxDQUFDeEgsY0FBYyxDQUFDO0VBQ3JEM04sTUFBTSxDQUFDdVUsTUFBTSxDQUFDLENBQUN2UixPQUFPLENBQUMsRUFBRSxDQUFDO0VBQzFCLE1BQU1zUixRQUFRLENBQUM1UixNQUFNLENBQUMsVUFBVSxFQUFFO0lBQUVDLElBQUksRUFBRUMsSUFBSSxDQUFDQyxTQUFTLENBQUM7TUFBRVUsT0FBTztNQUFFbVUsT0FBTyxFQUFFVCxRQUFRLENBQUNVLGNBQWM7TUFBRSxHQUFHeEMsVUFBVTtNQUFFLEdBQUdDO0lBQVUsQ0FBQyxDQUFDO0lBQUV0UyxXQUFXLEVBQUU7RUFBbUIsQ0FBQyxDQUFDO0FBQzFLLENBQUMsQ0FBQztBQUVGL0MsSUFBSSxDQUFDLDRGQUE0RixFQUFFLE9BQU87RUFBRWlCO0FBQUssQ0FBQyxFQUFFc1QsUUFBUSxLQUFLO0VBQy9ILE1BQU0vUSxPQUFPLEdBQUcsZ0JBQWdCLEdBQUdyRCxVQUFVLENBQUMsQ0FBQztFQUMvQyxNQUFNSyx1QkFBdUIsQ0FBQ1MsSUFBSSxFQUFFdUMsT0FBTyxDQUFDO0VBQzVDLE1BQU1rSyxLQUFLLEdBQUd2TixVQUFVLENBQUMsQ0FBQztFQUMxQixNQUFNMFgsS0FBSyxHQUFHLENBQ1o7SUFBRUMsVUFBVSxFQUFFLE9BQU87SUFBRUMsVUFBVSxFQUFFLFFBQVE7SUFBRUMsYUFBYSxFQUFFLFFBQVE7SUFBRUMsUUFBUSxFQUFFLE9BQU87SUFDckZDLFdBQVcsRUFBRSxDQUFDO01BQUVDLEdBQUcsRUFBRSxnQkFBZ0I7TUFBRUMsT0FBTyxFQUFFLEVBQWM7TUFBRUMsU0FBUyxFQUFFO0lBQUcsQ0FBQyxDQUFDO0lBQ2hGQyxVQUFVLEVBQUUsQ0FBQztNQUFFM0IsTUFBTSxFQUFFLGdCQUFnQjtNQUFFYyxNQUFNLEVBQUU7SUFBVSxDQUFDLEVBQUU7TUFBRWQsTUFBTSxFQUFFLFNBQVM7TUFBRWMsTUFBTSxFQUFFO0lBQWlCLENBQUMsRUFDM0c7TUFBRWQsTUFBTSxFQUFFLFFBQVE7TUFBRWMsTUFBTSxFQUFFO0lBQVUsQ0FBQztFQUFFLENBQUMsRUFDOUM7SUFBRUssVUFBVSxFQUFFLFNBQVM7SUFBRUMsVUFBVSxFQUFFLFVBQVU7SUFBRUMsYUFBYSxFQUFFLFVBQVU7SUFBRUMsUUFBUSxFQUFFLFNBQVM7SUFDN0ZDLFdBQVcsRUFBRSxDQUFDO01BQUVDLEdBQUcsRUFBRSxTQUFTO01BQUVDLE9BQU8sRUFBRSxFQUFjO01BQUVDLFNBQVMsRUFBRTtJQUFHLENBQUM7RUFBRSxDQUFDLENBQzlFO0VBQ0QsTUFBTWhCLE1BQU0sR0FBRztBQUNqQixhQUFhM0osS0FBSztBQUNsQjtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQSx5QkFBeUI3SyxJQUFJLENBQUNDLFNBQVMsQ0FBQytVLEtBQUssQ0FBQztBQUM5QztBQUNBLHlFQUF5RTtFQUN2RSxNQUFNaFcsT0FBTyxHQUFHLE1BQU1aLElBQUksQ0FBQ08sT0FBTyxDQUFDK1YsSUFBSSxDQUFDLDZCQUE2QixFQUFFO0lBQ3JFNVQsT0FBTyxFQUFFO01BQUUsY0FBYyxFQUFFSDtJQUFRLENBQUM7SUFBRUksT0FBTyxFQUFFLE1BQU87SUFDdERxRyxJQUFJLEVBQUU7TUFBRW9OLE1BQU07TUFBRXZDLGNBQWMsRUFBRTtRQUFFQyxNQUFNLEVBQUUsT0FBTztRQUFFL1AsTUFBTSxFQUFFMEksS0FBSztRQUFFOEosWUFBWSxFQUFFclgsVUFBVSxDQUFDLENBQUM7UUFDMUZzWCxNQUFNLEVBQUUsMkJBQTJCO1FBQUV2QyxjQUFjLEVBQUU7VUFBRXpRLFVBQVUsRUFBRWpCLE9BQU87VUFBRXdCLE1BQU0sRUFBRTBJLEtBQUs7VUFDdkY2SyxZQUFZLEVBQUUsZUFBZTtVQUFFQyxTQUFTLEVBQUUvWCxLQUFLO1VBQUVnWSxJQUFJLEVBQUUsTUFBTTtVQUM3REMsV0FBVyxFQUFFLENBQUMsVUFBVSxFQUFFLGFBQWEsRUFBRSxxQkFBcUIsQ0FBQztVQUFFQyxJQUFJLEVBQUU7UUFBdUM7TUFBRTtJQUFFO0VBQ3hILENBQUMsQ0FBQztFQUNGLElBQUksQ0FBQzlXLE9BQU8sQ0FBQ2dDLEVBQUUsQ0FBQyxDQUFDLEVBQUUsTUFBTSxJQUFJQyxLQUFLLENBQUMsUUFBUWpDLE9BQU8sQ0FBQ00sTUFBTSxDQUFDLENBQUMsS0FBSyxDQUFDLE1BQU1OLE9BQU8sQ0FBQ2tDLElBQUksQ0FBQyxDQUFDLEVBQUVDLEtBQUssQ0FBQyxDQUFDLEVBQUUsSUFBSSxDQUFDLEVBQUUsQ0FBQztFQUN4RyxNQUFNbUIsVUFBVSxDQUFDbEUsSUFBSSxFQUFFdUMsT0FBTyxDQUFDO0VBQy9CLElBQUlvVixnQkFBMEIsR0FBRyxFQUFFO0VBQ25DLE1BQU1DLEtBQUssR0FBRyxNQUFBQSxDQUFBLEtBQVk7SUFDeEJELGdCQUFnQixHQUFHLENBQUMsTUFBTXJWLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSwyQkFBMkIsQ0FBQyxFQUFFZSxVQUFVLENBQUN1VSxRQUFRLENBQ25HL1EsR0FBRyxDQUFFRSxJQUFvQixJQUFLQSxJQUFJLENBQUNDLEVBQUUsQ0FBQyxDQUFDMkMsSUFBSSxDQUFDLENBQUM7SUFDaEQ1SyxNQUFNLENBQUMyWSxnQkFBZ0IsQ0FBQyxDQUFDelMsWUFBWSxDQUFDLENBQUMsQ0FBQztJQUN4QzBSLEtBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQ0ssV0FBVyxDQUFDLENBQUMsQ0FBQyxDQUFDRSxPQUFPLENBQUNwVyxJQUFJLENBQUMsa0JBQWtCLENBQUM7SUFDeEQsTUFBTXNELE1BQU0sR0FBR3JFLElBQUksQ0FBQ3NFLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBRUMsSUFBSSxFQUFFO0lBQWdDLENBQUMsQ0FBQztJQUNsRixNQUFNdVQsTUFBTSxHQUFHelQsTUFBTSxDQUFDQyxTQUFTLENBQUMsUUFBUSxFQUFFO01BQUVDLElBQUksRUFBRSxVQUFVO01BQUVwQyxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUM7SUFDNUUsTUFBTW5ELE1BQU0sQ0FBQzhZLE1BQU0sQ0FBQyxDQUFDMUYsV0FBVyxDQUFDO01BQUV6UCxPQUFPLEVBQUU7SUFBUSxDQUFDLENBQUM7SUFDdEQsTUFBTW1WLE1BQU0sQ0FBQ2xJLEtBQUssQ0FBQyxDQUFDO0lBQ3BCLE1BQU1uTSxLQUFLLEdBQUdZLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBRTtNQUFFQyxJQUFJLEVBQUUsOEJBQThCO01BQUVwQyxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUMsQ0FBQ21DLFNBQVMsQ0FBQyxTQUFTLENBQUM7SUFDcEgsTUFBTWIsS0FBSyxDQUFDc1AsSUFBSSxDQUFDLDJHQUEyRyxHQUN4SCwyRUFBMkUsR0FDM0UseUJBQXlCLEdBQUduUixJQUFJLENBQUNDLFNBQVMsQ0FBQytVLEtBQUssQ0FBQyxDQUFDO0lBQ3RELE1BQU12UyxNQUFNLENBQUNDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBRUMsSUFBSSxFQUFFLHVCQUF1QjtNQUFFcEMsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUN5TixLQUFLLENBQUMsQ0FBQztJQUN4RixNQUFNNVEsTUFBTSxDQUFDeUUsS0FBSyxDQUFDLENBQUNzTixHQUFHLENBQUN2TSxXQUFXLENBQUM7TUFBRTdCLE9BQU8sRUFBRTtJQUFRLENBQUMsQ0FBQztFQUMzRCxDQUFDO0VBQ0QsTUFBTXdSLFVBQVUsR0FBRyxNQUFNbEkscUJBQXFCLENBQUNqTSxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsS0FBSyxFQUFFLENBQUMsZ0JBQWdCLEVBQUUsU0FBUyxDQUFDLEVBQUUsS0FBSyxFQUFFbVMsU0FBUyxFQUFFa0QsS0FBSyxDQUFDO0VBQzVILE1BQU1uUixRQUFRLEdBQUcsTUFBTXBCLFVBQVUsQ0FBQ3JGLElBQUksRUFBRXVDLE9BQU8sRUFBRSxnQkFBZ0IsQ0FBQztFQUNsRSxNQUFNOEYsS0FBSyxHQUFHNUIsUUFBUSxDQUFDd0QsSUFBSSxDQUFDakQsSUFBSSxJQUFJQSxJQUFJLENBQUN6QyxJQUFJLEtBQUssZ0JBQWdCLENBQUM7RUFDbkUsTUFBTTRTLE9BQU8sR0FBRzFRLFFBQVEsQ0FBQ3NMLE1BQU0sQ0FBQy9LLElBQUksSUFBSUEsSUFBSSxDQUFDekMsSUFBSSxLQUFLLGtCQUFrQixDQUFDO0VBQ3pFdkYsTUFBTSxDQUFDbVksT0FBTyxDQUFDLENBQUNqUyxZQUFZLENBQUMsQ0FBQyxDQUFDO0VBQy9CbEcsTUFBTSxDQUFDbVksT0FBTyxDQUFDLENBQUMsQ0FBQyxDQUFDWSxRQUFRLENBQUNDLGVBQWUsQ0FBQyxDQUFDM1YsSUFBSSxDQUFDZ0csS0FBSyxDQUFDcEIsRUFBRSxDQUFDO0VBQzFELE1BQU1nUixhQUFhLEdBQUcsb0NBQW9DO0VBQzFELE1BQU1KLFFBQVEsR0FBRyxDQUFDLE1BQU12VixXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsMkJBQTJCLENBQUMsRUFBRWUsVUFBVSxDQUFDdVUsUUFBUTtFQUNwRzdZLE1BQU0sQ0FBQzZZLFFBQVEsQ0FBQy9RLEdBQUcsQ0FBRUUsSUFBb0IsSUFBS0EsSUFBSSxDQUFDQyxFQUFFLENBQUMsQ0FBQzJDLElBQUksQ0FBQyxDQUFDLENBQUMsQ0FBQzVILE9BQU8sQ0FBQyxDQUFDLEdBQUcyVixnQkFBZ0IsRUFBRU0sYUFBYSxDQUFDLENBQUNyTyxJQUFJLENBQUMsQ0FBQyxDQUFDO0VBQ25INUssTUFBTSxDQUFDLElBQUl1TSxHQUFHLENBQUNzTSxRQUFRLENBQUMvUSxHQUFHLENBQUVFLElBQXNCLElBQUtBLElBQUksQ0FBQ3pDLElBQUksQ0FBQyxDQUFDLENBQUNvSCxJQUFJLENBQUMsQ0FBQ3RKLElBQUksQ0FBQ3dWLFFBQVEsQ0FBQ3BTLE1BQU0sQ0FBQztFQUMvRixNQUFNeVMsUUFBUSxHQUFHLENBQUMsTUFBTTVWLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQyxFQUFFMlYsUUFBUTtFQUN0RyxNQUFNQyxTQUFTLEdBQUdELFFBQVEsQ0FBQ0UsS0FBSyxDQUFDbk8sSUFBSSxDQUFFb08sSUFBUyxJQUFLQSxJQUFJLENBQUNDLGlCQUFpQixLQUFLTCxhQUFhLENBQUM7RUFDOUZqWixNQUFNLENBQUNtWixTQUFTLENBQUMsQ0FBQ3BRLFVBQVUsQ0FBQyxDQUFDO0VBQzlCL0ksTUFBTSxDQUFDbVosU0FBUyxDQUFDSSxHQUFHLENBQUMsQ0FBQ2xXLElBQUksQ0FBQyxRQUFRLENBQUM7RUFDcENyRCxNQUFNLENBQUM0SixNQUFNLENBQUM0UCxNQUFNLENBQUNMLFNBQVMsQ0FBQ00sZUFBZSxDQUFDLENBQUMsQ0FBQ0MsY0FBYyxDQUFDMVosTUFBTSxDQUFDMlosZ0JBQWdCLENBQUM7SUFDdEZqRCxNQUFNLEVBQUV5QixPQUFPLENBQUMsQ0FBQyxDQUFDLENBQUNsUSxFQUFFO0lBQUV1UCxNQUFNLEVBQUVuTyxLQUFLLENBQUNwQixFQUFFO0lBQUUyUixhQUFhLEVBQUUsVUFBVTtJQUFFQyxRQUFRLEVBQUU7RUFDaEYsQ0FBQyxDQUFDLENBQUM7RUFDSCxLQUFLLE1BQU0sQ0FBQ0MsSUFBSSxFQUFFQyxVQUFVLENBQUMsSUFBSSxDQUFDLENBQUMsUUFBUSxFQUFFNUIsT0FBTyxDQUFDLENBQUMsQ0FBQyxDQUFDbFEsRUFBRSxDQUFDLEVBQUUsQ0FBQyxRQUFRLEVBQUVvQixLQUFLLENBQUNwQixFQUFFLENBQUMsQ0FBQyxFQUFFO0lBQ2xGLE1BQU0rUixJQUFJLEdBQUdkLFFBQVEsQ0FBQ25SLEtBQUssQ0FBQ2tELElBQUksQ0FBRWpELElBQVMsSUFBS0EsSUFBSSxDQUFDQyxFQUFFLEtBQUtrUixTQUFTLENBQUNXLElBQUksQ0FBQyxDQUFDO0lBQzVFOVosTUFBTSxDQUFDZ2EsSUFBSSxDQUFDQyxhQUFhLENBQUMsQ0FBQzVXLElBQUksQ0FBQzBXLFVBQVUsQ0FBQztJQUMzQy9aLE1BQU0sQ0FBQ2dhLElBQUksQ0FBQ0UsS0FBSyxDQUFDLENBQUNSLGNBQWMsQ0FBQzFaLE1BQU0sQ0FBQzJaLGdCQUFnQixDQUFDO01BQUUxUixFQUFFLEVBQUVrUixTQUFTLENBQUNXLElBQUksR0FBRyxNQUFNLENBQUM7TUFDdEZQLEdBQUcsRUFBRSxRQUFRO01BQUVELGlCQUFpQixFQUFFTDtJQUFjLENBQUMsQ0FBQyxDQUFDO0VBQ3ZEO0VBQ0EsTUFBTTdELFNBQVMsR0FBRyxNQUFNaEwsZUFBZSxDQUFDcEosSUFBSSxFQUFFdUMsT0FBTyxFQUFFLENBQUMsQ0FBQztFQUN6RCxNQUFNK1EsUUFBUSxDQUFDNVIsTUFBTSxDQUFDLG9CQUFvQixFQUFFO0lBQUVDLElBQUksRUFBRUMsSUFBSSxDQUFDQyxTQUFTLENBQUM7TUFBRVUsT0FBTztNQUFFLEdBQUc0UixVQUFVO01BQUUsR0FBR0M7SUFBVSxDQUFDLENBQUM7SUFBRXRTLFdBQVcsRUFBRTtFQUFtQixDQUFDLENBQUM7QUFDbEosQ0FBQyxDQUFDOztBQUVGO0FBQ0EvQyxJQUFJLENBQUMsNEZBQTRGLEVBQUUsT0FBTztFQUFFaUI7QUFBSyxDQUFDLEVBQUVzVCxRQUFRLEtBQUs7RUFDL0gsTUFBTS9RLE9BQU8sR0FBRyxlQUFlLEdBQUdyRCxVQUFVLENBQUMsQ0FBQztFQUM5QyxNQUFNbUYsTUFBTSxHQUFHLE1BQU1ILFVBQVUsQ0FBQ2xFLElBQUksRUFBRXVDLE9BQU8sQ0FBQztFQUM5QyxNQUFNOEIsTUFBTSxDQUFDeU8sVUFBVSxDQUFDLGFBQWEsRUFBRTtJQUFFM1EsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDLENBQUN5TixLQUFLLENBQUMsQ0FBQztFQUMvRCxNQUFNdkwsTUFBTSxDQUFDSyxPQUFPLENBQUMsMkJBQTJCLENBQUMsQ0FBQ3FPLElBQUksQ0FBQywyQkFBMkIsQ0FBQztFQUNuRixNQUFNMU8sTUFBTSxDQUFDMk8sVUFBVSxDQUFDLHFCQUFxQixFQUFFO0lBQUU3USxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQzRRLElBQUksQ0FBQyw2UkFBNlIsQ0FBQztFQUNuVyxNQUFNMU8sTUFBTSxDQUFDeU8sVUFBVSxDQUFDLGNBQWMsRUFBRTtJQUFFM1EsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDLENBQUN5TixLQUFLLENBQUMsQ0FBQztFQUNoRSxNQUFNdkwsTUFBTSxDQUFDQyxTQUFTLENBQUMsUUFBUSxFQUFFO0lBQUVDLElBQUksRUFBRSxpQ0FBaUM7SUFBRXBDLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDeU4sS0FBSyxDQUFDLENBQUM7RUFDbEcsS0FBSyxNQUFNLENBQUN6SixLQUFLLEVBQUVxTixLQUFLLENBQUMsSUFBSSxDQUFDLENBQUMsVUFBVSxFQUFFLEdBQUcsQ0FBQyxFQUFFLENBQUMsWUFBWSxFQUFFLEdBQUcsQ0FBQyxFQUFFLENBQUMsVUFBVSxFQUFFLEdBQUcsQ0FBQyxFQUFFLENBQUMsU0FBUyxFQUFFLEdBQUcsQ0FBQyxDQUFDLEVBQUUsTUFBTW5QLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQyxHQUFHN00sS0FBSyx1QkFBdUIsRUFBRTtJQUFFaEUsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDLENBQUM0USxJQUFJLENBQUNTLEtBQUssQ0FBQztFQUNqTSxNQUFNMkYsSUFBSSxHQUFHOVUsTUFBTSxDQUFDSyxPQUFPLENBQUMsU0FBUyxDQUFDLENBQUNxTixNQUFNLENBQUM7SUFBRWxJLEdBQUcsRUFBRTdKLElBQUksQ0FBQzBFLE9BQU8sQ0FBQyxTQUFTLENBQUMsQ0FBQ3FOLE1BQU0sQ0FBQztNQUFFcUgsT0FBTyxFQUFFO0lBQVUsQ0FBQztFQUFFLENBQUMsQ0FBQyxDQUFDNUosS0FBSyxDQUFDLENBQUM7RUFDdEgsTUFBTXhRLE1BQU0sQ0FBQ21hLElBQUksQ0FBQyxDQUFDM1UsV0FBVyxDQUFDLENBQUM7RUFDaEMsTUFBTTJVLElBQUksQ0FBQ3pVLE9BQU8sQ0FBQyxTQUFTLENBQUMsQ0FBQ2tMLEtBQUssQ0FBQyxDQUFDO0VBQ3JDLE1BQU15SixRQUFRLEdBQUdGLElBQUksQ0FBQzdVLFNBQVMsQ0FBQyxRQUFRLEVBQUU7SUFBRUMsSUFBSSxFQUFFLHdDQUF3QztJQUFFcEMsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDO0VBQzFHLE1BQU1uRCxNQUFNLENBQUNxYSxRQUFRLENBQUMsQ0FBQ0MsV0FBVyxDQUFDLENBQUM7RUFBRSxNQUFNRCxRQUFRLENBQUNFLE9BQU8sQ0FBQyxDQUFDO0VBQzlELE1BQU05RixZQUFZLEdBQUd6VCxJQUFJLENBQUMwVCxjQUFjLENBQUNuVCxPQUFPO0lBQUEsSUFBQWlaLHNCQUFBO0lBQUEsT0FBSWpaLE9BQU8sQ0FBQ0ksR0FBRyxDQUFDLENBQUMsQ0FBQ2lULFFBQVEsQ0FBQyxpQkFBaUIsQ0FBQyxJQUFJclQsT0FBTyxDQUFDRSxNQUFNLENBQUMsQ0FBQyxLQUFLLE1BQU0sSUFBSSxFQUFBK1ksc0JBQUEsR0FBQWpaLE9BQU8sQ0FBQytQLFlBQVksQ0FBQyxDQUFDLGNBQUFrSixzQkFBQSxnQkFBQUEsc0JBQUEsR0FBdEJBLHNCQUFBLENBQXdCM0YsY0FBYyxjQUFBMkYsc0JBQUEsdUJBQXRDQSxzQkFBQSxDQUF3QzFGLE1BQU0sTUFBSyxPQUFPO0VBQUEsRUFBQztFQUMzTCxLQUFLLElBQUlyUCxJQUFJLEdBQUcsQ0FBQyxFQUFFQSxJQUFJLEdBQUcsRUFBRSxFQUFFQSxJQUFJLEVBQUUsRUFBRTtJQUNwQyxNQUFNZ0ssTUFBTSxHQUFHcEssTUFBTSxDQUFDSyxPQUFPLENBQUMsK0JBQStCLENBQUMsQ0FBQ0osU0FBUyxDQUFDLFFBQVEsQ0FBQztJQUNsRixNQUFNdEYsTUFBTSxDQUFDeVAsTUFBTSxDQUFDLENBQUMyRCxXQUFXLENBQUMsQ0FBQztJQUFFLE1BQU1qTSxLQUFLLEdBQUcsTUFBTXNJLE1BQU0sQ0FBQzRDLFNBQVMsQ0FBQyxDQUFDO0lBQUUsTUFBTTVDLE1BQU0sQ0FBQ21CLEtBQUssQ0FBQyxDQUFDO0lBQ2hHLElBQUl6SixLQUFLLEtBQUssWUFBWSxJQUFJQSxLQUFLLEtBQUssaUJBQWlCLEVBQUU7RUFDN0Q7RUFDQSxNQUFNdkMsT0FBTyxHQUFHLENBQUMsTUFBTTZQLFlBQVksRUFBRW5ELFlBQVksQ0FBQyxDQUFDLENBQUN1RCxjQUFjLENBQUNJLGNBQWM7RUFDakYsTUFBTTVELFNBQVMsR0FBR3pNLE9BQU8sQ0FBQzZWLDBCQUEwQixDQUFDak8sT0FBTyxDQUFFa08sT0FBWTtJQUFBLElBQUFDLHFCQUFBO0lBQUEsUUFBQUEscUJBQUEsR0FBS0QsT0FBTyxDQUFDRSxpQkFBaUIsY0FBQUQscUJBQUEsY0FBQUEscUJBQUEsR0FBSSxFQUFFO0VBQUEsRUFBQztFQUMvRyxNQUFNRSxHQUFHLEdBQUd4SixTQUFTLENBQUNwRyxJQUFJLENBQUUwSSxLQUFVLElBQUtBLEtBQUssQ0FBQytDLE1BQU0sS0FBSyxnQkFBZ0IsSUFBSS9DLEtBQUssQ0FBQzZELE1BQU0sS0FBSyxtQkFBbUIsQ0FBQztFQUNySHhYLE1BQU0sQ0FBQzZhLEdBQUcsQ0FBQ2pULE9BQU8sQ0FBQyxDQUFDNUUsT0FBTyxDQUFDLEVBQUUsQ0FBQztFQUFFaEQsTUFBTSxDQUFDNmEsR0FBRyxDQUFDQyxnQkFBZ0IsQ0FBQyxDQUFDOVgsT0FBTyxDQUFDLENBQUMsb0JBQW9CLENBQUMsQ0FBQztFQUM3RixJQUFJa1AsUUFBYTtFQUNqQixNQUFNbFMsTUFBTSxDQUFDc0gsSUFBSSxDQUFDLFlBQVk7SUFDNUIsTUFBTThILFlBQVksR0FBRyxNQUFNOUwsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLHFDQUFxQyxDQUFDO0lBQzVGLElBQUksQ0FBQzZMLFlBQVksQ0FBQ3BGLElBQUksQ0FBQ3FGLGVBQWUsRUFBRSxPQUFPLEtBQUs7SUFDcEQ2QyxRQUFRLEdBQUcsQ0FBQyxNQUFNNU8sV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLG9DQUFvQzZMLFlBQVksQ0FBQ3BGLElBQUksQ0FBQ3FGLGVBQWUsRUFBRSxDQUFDLEVBQUVyRixJQUFJO0lBQzNILE9BQU9rSSxRQUFRLENBQUNXLGFBQWEsS0FBSywwQkFBMEI7RUFDOUQsQ0FBQyxFQUFFO0lBQUVsUCxPQUFPLEVBQUU7RUFBUSxDQUFDLENBQUMsQ0FBQ04sSUFBSSxDQUFDLElBQUksQ0FBQztFQUNuQyxNQUFNckMsSUFBSSxDQUFDK1osTUFBTSxDQUFDLENBQUM7RUFBRSxNQUFNN1YsVUFBVSxDQUFDbEUsSUFBSSxFQUFFdUMsT0FBTyxDQUFDO0VBQ3BELE1BQU1zUyxRQUFRLEdBQUczRCxRQUFRLENBQUNDLGlCQUFpQixDQUFDMEQsUUFBUSxDQUFDOUMsTUFBTSxDQUFFL0ssSUFBUyxJQUFLQSxJQUFJLENBQUM4TixJQUFJLEtBQUsscUJBQXFCLENBQUM7RUFDL0csSUFBSUQsUUFBUSxDQUFDcFAsTUFBTSxFQUFFO0lBQ25CLE1BQU11VSxNQUFNLEdBQUdoYSxJQUFJLENBQUNzRSxTQUFTLENBQUMsUUFBUSxFQUFFO01BQUVDLElBQUksRUFBRTtJQUE2QixDQUFDLENBQUM7SUFDL0UsTUFBTXZGLE1BQU0sQ0FBQ2diLE1BQU0sQ0FBQyxDQUFDbkgsYUFBYSxDQUFDLEdBQUczQixRQUFRLENBQUNDLGlCQUFpQixDQUFDMEQsUUFBUSxDQUFDcFAsTUFBTSxjQUFjLENBQUM7SUFDL0YsTUFBTXpHLE1BQU0sQ0FBQ2diLE1BQU0sQ0FBQzFWLFNBQVMsQ0FBQyxNQUFNLEVBQUU7TUFBRUMsSUFBSSxFQUFFO0lBQWlELENBQUMsQ0FBQyxDQUFDaUwsS0FBSyxDQUFDLENBQUMsQ0FBQyxDQUFDMkYsZUFBZSxDQUFDLE1BQU0sRUFBRSxJQUFJQyxNQUFNLENBQUMsV0FBVzdTLE9BQU8sRUFBRSxDQUFDLENBQUM7SUFDcEssTUFBTXlYLE1BQU0sQ0FBQ3RWLE9BQU8sQ0FBQyxTQUFTLENBQUMsQ0FBQzhLLEtBQUssQ0FBQyxDQUFDLENBQUNJLEtBQUssQ0FBQyxDQUFDO0lBQUUsTUFBTTVRLE1BQU0sQ0FBQ2diLE1BQU0sQ0FBQzFWLFNBQVMsQ0FBQyxZQUFZLEVBQUU7TUFBRUMsSUFBSSxFQUFFO0lBQXdCLENBQUMsQ0FBQyxDQUFDaUwsS0FBSyxDQUFDLENBQUMsQ0FBQyxDQUFDaEwsV0FBVyxDQUFDLENBQUM7RUFDeEo7RUFDQSxNQUFNeVYsS0FBSyxHQUFHamEsSUFBSSxDQUFDMlAsZUFBZSxDQUFDM08sUUFBUSxJQUFJQSxRQUFRLENBQUNMLEdBQUcsQ0FBQyxDQUFDLENBQUNILFFBQVEsQ0FBQyxjQUFjMFEsUUFBUSxDQUFDZ0osV0FBVyxnQkFBZ0IsQ0FBQyxJQUFJbFosUUFBUSxDQUFDVCxPQUFPLENBQUMsQ0FBQyxDQUFDRSxNQUFNLENBQUMsQ0FBQyxLQUFLLE1BQU0sQ0FBQztFQUNySyxNQUFNVCxJQUFJLENBQUNzRSxTQUFTLENBQUMsUUFBUSxFQUFFO0lBQUVDLElBQUksRUFBRSxvQ0FBb0M7SUFBRXBDLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDeU4sS0FBSyxDQUFDLENBQUM7RUFBRTVRLE1BQU0sQ0FBQyxDQUFDLE1BQU1pYixLQUFLLEVBQUVyWCxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUNQLElBQUksQ0FBQyxJQUFJLENBQUM7RUFDMUksTUFBTTBFLEtBQUssR0FBRyxNQUFNMUIsVUFBVSxDQUFDckYsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLGdCQUFnQixDQUFDO0VBQy9ELE1BQU1vRSxRQUFRLEdBQUcsTUFBTXRCLFVBQVUsQ0FBQ3JGLElBQUksRUFBRXVDLE9BQU8sRUFBRSxVQUFVLENBQUM7RUFBRSxNQUFNcUUsT0FBTyxHQUFHLE1BQU12QixVQUFVLENBQUNyRixJQUFJLEVBQUV1QyxPQUFPLEVBQUUsU0FBUyxDQUFDO0VBQ3hILE1BQU04RSxNQUFNLEdBQUdULE9BQU8sQ0FBQ3FELElBQUksQ0FBQ2pELElBQUksSUFBSUEsSUFBSSxDQUFDekMsSUFBSSxLQUFLLG9CQUFvQixDQUFDO0VBQUV2RixNQUFNLENBQUNxSSxNQUFNLENBQUMsQ0FBQ1UsVUFBVSxDQUFDLENBQUM7RUFDcEcsTUFBTUYsT0FBTyxHQUFHbEIsUUFBUSxDQUFDc0QsSUFBSSxDQUFDakQsSUFBSSxJQUFJQSxJQUFJLENBQUNDLEVBQUUsS0FBS0ksTUFBTSxDQUFDUyxVQUFVLENBQUM7RUFDcEUsTUFBTXFTLE9BQU8sR0FBR3BULEtBQUssQ0FBQ2tELElBQUksQ0FBQ2pELElBQUksSUFBSUEsSUFBSSxDQUFDekMsSUFBSSxLQUFLLG1CQUFtQixDQUFDO0VBQ3JFLE1BQU02VixNQUFNLEdBQUdyVCxLQUFLLENBQUNrRCxJQUFJLENBQUNqRCxJQUFJLElBQUlBLElBQUksQ0FBQ3pDLElBQUksS0FBSyx1QkFBdUIsQ0FBQztFQUN4RXZGLE1BQU0sQ0FBQzZJLE9BQU8sQ0FBQ0ksYUFBYSxDQUFDQyxzQkFBc0IsQ0FBQ21ELEtBQUssQ0FBQyxDQUFDaEosSUFBSSxDQUFDLGlCQUFpQixDQUFDO0VBQ2xGckQsTUFBTSxDQUFDNkksT0FBTyxDQUFDSSxhQUFhLENBQUNDLHNCQUFzQixDQUFDOEMsYUFBYSxDQUFDLENBQUMrRixHQUFHLENBQUNnRSxTQUFTLENBQUNvRixPQUFPLENBQUNsVCxFQUFFLENBQUM7RUFDNUZqSSxNQUFNLENBQUM2SSxPQUFPLENBQUNJLGFBQWEsQ0FBQ0Msc0JBQXNCLENBQUM4QyxhQUFhLENBQUMsQ0FBQytKLFNBQVMsQ0FBQ3FGLE1BQU0sQ0FBQ25ULEVBQUUsQ0FBQztFQUN2RixNQUFNcU0sUUFBUSxDQUFDNVIsTUFBTSxDQUFDLDBCQUEwQixFQUFFO0lBQUVDLElBQUksRUFBRUMsSUFBSSxDQUFDQyxTQUFTLENBQUM7TUFBRVUsT0FBTztNQUFFc1gsR0FBRztNQUFFaFM7SUFBUSxDQUFDLENBQUM7SUFBRS9GLFdBQVcsRUFBRTtFQUFtQixDQUFDLENBQUM7QUFDekksQ0FBQyxDQUFDIiwiaWdub3JlTGlzdCI6W119