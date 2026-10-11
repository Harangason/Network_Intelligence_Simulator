// a84a4385a904727920ae2b3417f0ca688911043b
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
  await expect(common.locator('#arbitration_bitrate')).toHaveValue('500000');
  await expect(common.locator('#data_bitrate')).toHaveValue('2000000');
  await expect(page.locator('.parameter-details[open]')).toHaveCount(0);
  await common.locator('#seed').fill('42');
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
  await page.getByRole('link', {
    name: 'Zur Vorschlagsprüfung zurück →',
    exact: true
  }).click();
  await expect(dialog).toBeVisible();
  const review = dialog.getByRole('region', {
    name: 'Engineering-Vorschlag'
  });
  await expect(review).toContainText('Modellstand geändert');
  await expect(review.getByRole('button', {
    name: 'Freigeben, übernehmen & fortfahren',
    exact: true
  })).toHaveCount(0);
  await review.getByRole('button', {
    name: 'Erneut prüfen',
    exact: true
  }).click();
  await expect(review).toContainText('Geprüft · Freigabe offen');
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
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmVhZEZpbGUiLCJyYW5kb21VVUlEIiwiZXhlY0ZpbGVTeW5jIiwiV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyIsIldJWkFSRF9TVEVQUyIsIldJWkFSRF9ET05FIiwicmV2aWV3VmlydHVhbFRyYW5zcG9ydHMiLCJzdGVwcyIsImRvbmUiLCJ3cml0ZVRpbWluZ3MiLCJNYXAiLCJ3b3JrZmxvd1BhZ2VGYWlsdXJlcyIsIldlYWtNYXAiLCJwcm9ncmVzc01pbGVzdG9uZXMiLCJiZWZvcmVFYWNoIiwicGFnZSIsImluZm8iLCJyb3dzIiwic2V0IiwidGVzdElkIiwicmVxdWVzdHMiLCJvbiIsInJlcXVlc3QiLCJpbmNsdWRlcyIsIm1ldGhvZCIsInJvdyIsInVybCIsInN0YXJ0ZWQiLCJEYXRlIiwibm93IiwicHVzaCIsInJlc3BvbnNlIiwiZ2V0Iiwic3RhdHVzIiwiVVJMIiwicGF0aG5hbWUiLCJkdXJhdGlvbl9tcyIsIl9yZXF1ZXN0JGZhaWx1cmUiLCJmYWlsdXJlIiwiZXJyb3JUZXh0IiwiYWZ0ZXJFYWNoIiwiYXR0YWNoIiwiYm9keSIsIkpTT04iLCJzdHJpbmdpZnkiLCJjb250ZW50VHlwZSIsImRlbGV0ZSIsInRvRXF1YWwiLCJhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5IiwiZ2V0QnlUZXh0IiwiZXhhY3QiLCJpc1Zpc2libGUiLCJ0b0JlIiwicmVhZFByb2plY3QiLCJwcm9qZWN0IiwicGF0aCIsInJlc3VsdCIsImhlYWRlcnMiLCJ0aW1lb3V0Iiwib2siLCJFcnJvciIsInRleHQiLCJzbGljZSIsImpzb24iLCJkaXNwb3NlIiwicmVhZFdhcm5pbmdSZXZpZXdTdGF0ZSIsIl92ZXJpZmllZCRjb250ZXh0JGFnZTIiLCJfdmVyaWZpZWQkY29udGV4dCRhZ2UzIiwiYXV0aG9yaXR5IiwicGFyYW1ldGVycyIsInZlcmlmaWVkIiwicHJvamVjdF9pZCIsImZpZWxkIiwiX3ZlcmlmaWVkJGNvbnRleHQkYWdlIiwiX2F1dGhvcml0eSRjb250ZXh0JGFnIiwiY29udGV4dCIsImFnZW50X2V4ZWN1dGlvbiIsInN0YXR1c2VzIiwicnVuX2lkIiwicmVxdWVzdF9yZXZpc2lvbiIsInByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsIiwib3BlbldpemFyZCIsImdvdG8iLCJ3YWl0VW50aWwiLCJkaWFsb2ciLCJnZXRCeVJvbGUiLCJuYW1lIiwidG9CZVZpc2libGUiLCJzdGVwIiwibG9jYXRvciIsInN0ZXBXaWR0aCIsImV2YWx1YXRlIiwiZWxlbWVudCIsImdldEJvdW5kaW5nQ2xpZW50UmVjdCIsIndpZHRoIiwiY2FyZHMiLCJhbGwiLCJ0b0hhdmVMZW5ndGgiLCJjYXJkIiwidG9CZUdyZWF0ZXJUaGFuIiwiYWxsT2JqZWN0cyIsInJlc291cmNlIiwiaXRlbXMiLCJvZmZzZXQiLCJsZW5ndGgiLCJyZXN0YXJ0QXBwbGljYXRpb24iLCJjcmFzaCIsImNvbnRhaW5lciIsInByb2Nlc3MiLCJlbnYiLCJOSVNfRTJFX0FQUF9DT05UQUlORVIiLCJ0b01hdGNoIiwiZG9ja2VyIiwiTklTX1RFU1RfRE9DS0VSIiwibGFiZWwiLCJlbmNvZGluZyIsInRyaW0iLCJwb2xsIiwidmVyaWZ5U2lnbmFsQ29udHJhY3RzIiwiZXhwZWN0ZWQiLCJoYXJkd2FyZSIsImZ1bmN0aW9ucyIsIm1lc3NhZ2VzIiwic2lnbmFscyIsIlByb21pc2UiLCJtYXAiLCJub2RlcyIsIml0ZW0iLCJpZCIsImZ1bmN0aW9uc0J5SWQiLCJtZXNzYWdlc0J5SWQiLCJjb250cmFjdHMiLCJzaWduYWwiLCJfcmVmIiwiX3NpZ25hbCRkYXRhJGVudW1fdmFsIiwiX3NpZ25hbCRkYXRhIiwiX3NpZ25hbCRzZW1hbnRpYyRzZW1hIiwiX3NpZ25hbCRzZW1hbnRpYyIsIl9zaWduYWwkY29uZmlndXJhdGlvbiIsIl9zaWduYWwkY29uZmlndXJhdGlvbjIiLCJtZXNzYWdlIiwibWVzc2FnZV9pZCIsInRvQmVUcnV0aHkiLCJyZWZlcmVuY2UiLCJjb25maWd1cmF0aW9uIiwiY29tbXVuaWNhdGlvbl9jb250cmFjdCIsInByb2R1Y2VyX3JlZiIsImZuIiwib3duZXIiLCJoYXJkd2FyZV9ub2RlX2lkIiwicHJvZHVjZXIiLCJkZXZpY2VfdHlwZSIsImtleSIsImpvaW4iLCJ0b0JlVW5kZWZpbmVkIiwiT2JqZWN0IiwiZnJvbUVudHJpZXMiLCJfc2lnbmFsJGZpZWxkIiwiZW51bV92YWx1ZXMiLCJkYXRhIiwic2VtYW50aWNfdHlwZSIsInNlbWFudGljIiwiZ2VuZXJhdGlvbl9yb2xlIiwidmVyaWZ5QXJ0aWZhY3RzIiwibWluaW11bUNhbm9uaWNhbFNpZ25hbHMiLCJpbnRlcm5hbENvbnRyb2xsZXIiLCJfYXNzZXNzbWVudCRzY29wZV9jb3YiLCJ3b3JrZmxvdyIsImpvYkxpc3QiLCJzbmFwc2hvdHMiLCJrZXlzIiwic29ydCIsImhhcyIsImpvYnMiLCJzbmFwc2hvdCIsInNpbXVsYXRpb25zIiwiZmluZCIsImpvYl9pZCIsImZ1bGwiLCJhc3Nlc3NtZW50Iiwic2NvcGVfY292ZXJhZ2UiLCJzY29wZV9tb2RlIiwiY29tcGxldGUiLCJjb25mb3JtYW5jZSIsImZhaWxlZF9yb3V0ZV9jb3VudCIsInRvQmVHcmVhdGVyVGhhbk9yRXF1YWwiLCJleGNsdWRlZCIsInRyYW5zcG9ydF9leGNsdXNpb25zIiwicm91dGluZyIsImVuYWJsZWQiLCJjb250cmFjdCIsImNvbnN1bWVyX3JlZnMiLCJyZWFzb25fY29kZSIsInJvbGUiLCJjb250cm9sbGVyIiwidG9NYXRjaE9iamVjdCIsInNjb3BlIiwiZXhjbHVkZWRTaWduYWxzIiwiU2V0IiwiZmxhdE1hcCIsInNpZ25hbF9pZHMiLCJvYnNlcnZlZF9zaWduYWxfY291bnQiLCJzaXplIiwidHJhY2UiLCJjb3VudCIsImV2ZW50cyIsInNvbWUiLCJqb2IiLCJjb21wbGV0ZVRocm91Z2hXaXphcmQiLCJyZXN0YXJ0IiwiZXhwZWN0ZWRIYXJkd2FyZSIsImNyYXNoU2ltdWxhdGlvbiIsImV4cGVjdGVkU2lnbmFscyIsImFmdGVyRmlyc3RNb2RlbEFwcGxpZWQiLCJzdG9wT25FdmlkZW5jZUJsb2NrIiwicmV2aWV3Q291bnQiLCJydW5JZCIsInJldmlld2VkIiwicmVzdGFydGVkSm9iSWQiLCJ3YXRjaGRvZyIsInBlcmZvcm1hbmNlIiwiY2hlY2twb2ludCIsIl93b3JrZmxvdyRjb250ZXh0JGFnZSIsIl93b3JrZmxvdyRjb250ZXh0JGFnZTIiLCJfZXhlY3V0aW9uJGJsb2NraW5nX2YiLCJfZXhlY3V0aW9uJG1lc3NhZ2UiLCJwcm9wb3NhbElkIiwicmVhZHlWZXJzaW9uIiwicmVhZHlTaW5jZSIsImlzQ2hlY2twb2ludCIsInJlbWFpbmluZyIsInByb2dyZXNzIiwib2JzZXJ2ZSIsImFkdmFuY2VkIiwiYXQiLCJ0b0lTT1N0cmluZyIsImZyb250aWVyIiwiY29tcGxldGVkVGhyb3VnaCIsImV4ZWN1dGlvbiIsInZhbGlkYXRpb24iLCJydW5uaW5nIiwiZXZlcnkiLCJzdGF0ZSIsImNvbnZlcnNhdGlvbiIsImFjdGl2ZV9wcm9wb3NhbCIsIkJvb2xlYW4iLCJyZWNvdmVyYWJsZSIsInVwZGF0ZWRfYXQiLCJidXR0b24iLCJldmFsdWF0ZUFsbCIsImJ1dHRvbnMiLCJkaXNhYmxlZCIsImdldENsaWVudFJlY3RzIiwiZ2V0Q29tcHV0ZWRTdHlsZSIsInZpc2liaWxpdHkiLCJhdHRlbXB0Iiwid2FpdEZvclRpbWVvdXQiLCJNYXRoIiwibWluIiwiYmxvY2tpbmdfZmluZGluZ3MiLCJiZWZvcmVSZXZpZXciLCJwcmVmbGlnaHQiLCJ3YXJuaW5ncyIsImZpcnN0Iiwic3RhcnRlZFdhbGwiLCJhcHByb3ZhbFJlc3BvbnNlIiwid2FpdEZvclJlc3BvbnNlIiwiY2xpY2siLCJhcHByb3ZlZCIsInJlY2VpcHQiLCJhZnRlclJldmlldyIsInByb29mIiwiYmVmb3JlIiwiYWZ0ZXIiLCJzbmFwc2hvdElkIiwicmVxdWVzdFByb2plY3QiLCJzdWJtaXR0ZWQiLCJwb3N0RGF0YUpTT04iLCJmaW5pc2hlZFdhbGwiLCJjb21taXR0ZWRBdCIsImNvbW1pdHRlZCIsImNvbW1pdFdhcm5pbmdSZXZpZXciLCJtYW51YWxXYXJuaW5nQXBwcm92YWwiLCJhcHByb3ZhbElkZW50aXR5IiwiYXBwcm92YWwiLCJfYXdhaXQkcmVhZFByb2plY3QkY28iLCJub3QiLCJfY29udmVyc2F0aW9uJGRhdGEiLCJfcHJvcG9zYWwkZGF0YSIsInByb3Bvc2FsIiwidmFsaWRhdGlvbl9yZXN1bHQiLCJ2aXNpYmxlIiwiaW5uZXJUZXh0IiwiZXJyb3IiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQiLCJsYXRlc3QiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQyIiwiX2xhdGVzdCRjb250ZXh0JGFnZW50MyIsIl9sYXRlc3Qkc3RhdHVzZXMiLCJjYW5kaWRhdGUiLCJwcm9wb3NhbF90eXBlIiwiY2hhbmdlcyIsImZpbHRlciIsImNoYW5nZSIsIm9iamVjdF90eXBlIiwiYXJyYXlDb250YWluaW5nIiwiYXBwbHlSZXNwb25zZSIsInRvQmVFbmFibGVkIiwiYXBwbGllZCIsImFkZCIsIl9hbWVuZGVkJGNvbnRleHQkYWdlbiIsImFtZW5kZWQiLCJfY3VycmVudCRjb250ZXh0JGFnZW4iLCJjdXJyZW50Iiwicm91dGUiLCJmdWxmaWxsIiwidG9Db250YWluVGV4dCIsImdldEJ5VGl0bGUiLCJmaWxsIiwiZ2V0QnlMYWJlbCIsInRvQmVEaXNhYmxlZCIsInVucm91dGUiLCJ0b0hhdmVDb3VudCIsImNhdGFsb2ciLCJ0ZWNobm9sb2d5X2NvdW50IiwidGVzdEluZm8iLCJlcnJvcnMiLCJ2YWx1ZSIsInN0YXJ0UmVxdWVzdCIsIndhaXRGb3JSZXF1ZXN0IiwiX3JlcXVlc3QkcG9zdERhdGFKU09OIiwiZW5kc1dpdGgiLCJ3aXphcmRfY29tbWFuZCIsImFjdGlvbiIsInN1Ym1pdCIsInJlcXVlc3RlZCIsIndpemFyZF9jb250ZXh0IiwidGVjaG5vbG9naWVzIiwiX2F3YWl0JHJlYWRQcm9qZWN0JGNvMiIsInBlbmRpbmciLCJjb21tb24iLCJ0b0hhdmVWYWx1ZSIsInN0YWxlIiwiY2Fub25pY2FsX2lkcyIsInJlbG9hZCIsInJldmlldyIsImNvbnRpbnVpdHkiLCJhcnRpZmFjdHMiLCJmaW5pc2hlZCIsInRlY2hub2xvZ3kiLCJjaGVjayIsInNlbGVjdE9wdGlvbiIsInVuZGVmaW5lZCIsInJlamVjdHMiLCJ0b1Rocm93IiwiZmluZGluZ3MiLCJjb2RlIiwidG9Db250YWluIiwiYXJ0aWZhY3RfY2hlY2tzIiwicmVxdWlyZWQiLCJldmlkZW5jZVJldmlldyIsInRvSGF2ZUF0dHJpYnV0ZSIsIlJlZ0V4cCIsInNpbXVsYXRpb24iLCJyYXRlX3Jldmlld19wcm9wb3NhbHMiLCJpMmMiLCJwYXJhbWV0ZXJfcHJvdmVuYW5jZSIsImJpdHJhdGUiLCJzb3VyY2UiLCJpbnRlcmZhY2VzIiwiZG9tYWluIiwidW5pdCIsIm9yaWdpbmFsIiwiaW1wb3J0IiwibWV0YSIsIm1ldGFkYXRhIiwicGFyc2UiLCJiYXNlbGluZSIsInByb21wdCIsInJlcGxhY2UiLCJwb3N0Iiwib3BlcmF0aW9uX2lkIiwidGFyZ2V0IiwiZXhjbHVkZWRTaWduYWxJZHMiLCJmaXh0dXJlIiwicmVxdWVzdF9zaGEyNTYiLCJncmFwaCIsImNsdXN0ZXJfaWQiLCJuZXR3b3JrX2lkIiwibmV0d29ya19sYWJlbCIsImJ1c19uYW1lIiwiY29udHJvbGxlcnMiLCJlY3UiLCJzZW5zb3JzIiwiYWN0dWF0b3JzIiwiaG1pX3JvdXRlcyIsInByb2plY3RfbmFtZSIsInNjb3BlX2lkcyIsIm1vZGUiLCJwcm9jZXNzX2lkcyIsInRhc2siLCJvcmlnaW5hbE5ldHdvcmtzIiwiYW1lbmQiLCJuZXR3b3JrcyIsImV4cGFuZCIsImlkZW50aXR5Iiwic3lzdGVtX293bmVyX2lkIiwic2Vuc29yTmV0d29yayIsInRvcG9sb2d5IiwibG9jYWxFZGdlIiwiZWRnZXMiLCJlZGdlIiwicGh5c2ljYWxOZXR3b3JrSWQiLCJidXMiLCJ2YWx1ZXMiLCJyb3V0aW5nTWV0YWRhdGEiLCJ0b0NvbnRhaW5FcXVhbCIsIm9iamVjdENvbnRhaW5pbmciLCJhcHByb3ZhbFN0YXRlIiwicHJvdG9jb2wiLCJzaWRlIiwiaGFyZHdhcmVJZCIsIm5vZGUiLCJlbmdpbmVlcmluZ0lkIiwicG9ydHMiLCJ0eHJ4IiwiaGFzVGV4dCIsInNlbGVjdGVkIiwidG9CZUNoZWNrZWQiLCJ1bmNoZWNrIiwiX3JlcXVlc3QkcG9zdERhdGFKU09OMiIsInN5c3RlbV9jbHVzdGVyX2Fzc2lnbm1lbnRzIiwiY2x1c3RlciIsIl9jbHVzdGVyJGZ1bmN0aW9uYWxfciIsImZ1bmN0aW9uYWxfcm91dGVzIiwib2ZmIiwiZXhjbHVkZWRfc2lnbmFscyIsImFwcGx5IiwicHJvcG9zYWxfaWQiLCJnZWFyYm94IiwiZW1vdG9yIl0sInNvdXJjZXMiOlsid2l6YXJkLnNwZWMudHMiXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgdGVzdCwgZXhwZWN0LCB0eXBlIFBhZ2UgfSBmcm9tICdwbGF5d3JpZ2h0L3Rlc3QnO1xyXG5pbXBvcnQgeyByZWFkRmlsZSB9IGZyb20gJ25vZGU6ZnMvcHJvbWlzZXMnO1xyXG5pbXBvcnQgeyByYW5kb21VVUlEIH0gZnJvbSAnbm9kZTpjcnlwdG8nO1xyXG5pbXBvcnQgeyBleGVjRmlsZVN5bmMgfSBmcm9tICdub2RlOmNoaWxkX3Byb2Nlc3MnO1xyXG5pbXBvcnQgeyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nLCBXSVpBUkRfU1RFUFMsIFdJWkFSRF9ET05FIH0gZnJvbSAnLi9zdXBwb3J0L3dpemFyZC1wcm9ncmVzcy13YXRjaGRvZyc7XHJcbmltcG9ydCB7IHJldmlld1ZpcnR1YWxUcmFuc3BvcnRzIH0gZnJvbSAnLi9zdXBwb3J0L25hdGl2ZS10cmFuc3BvcnQtZml4dHVyZXMnO1xyXG5cclxuY29uc3Qgc3RlcHMgPSBXSVpBUkRfU1RFUFM7XHJcbmNvbnN0IGRvbmUgPSBXSVpBUkRfRE9ORTtcclxudHlwZSBXcml0ZVRpbWluZyA9IHsgdXJsOiBzdHJpbmc7IHN0YXJ0ZWQ6IG51bWJlcjsgZHVyYXRpb25fbXM/OiBudW1iZXI7IHN0YXR1cz86IG51bWJlcjsgZmFpbHVyZT86IHN0cmluZyB9O1xyXG5jb25zdCB3cml0ZVRpbWluZ3MgPSBuZXcgTWFwPHN0cmluZywgV3JpdGVUaW1pbmdbXT4oKTtcclxuY29uc3Qgd29ya2Zsb3dQYWdlRmFpbHVyZXMgPSBuZXcgV2Vha01hcDxQYWdlLCBzdHJpbmdbXT4oKTtcclxuY29uc3QgcHJvZ3Jlc3NNaWxlc3RvbmVzID0gbmV3IE1hcDxzdHJpbmcsIHVua25vd25bXT4oKTtcclxuXHJcbnRlc3QuYmVmb3JlRWFjaChhc3luYyAoeyBwYWdlIH0sIGluZm8pID0+IHtcclxuICBjb25zdCByb3dzOiBXcml0ZVRpbWluZ1tdID0gW107XHJcbiAgd3JpdGVUaW1pbmdzLnNldChpbmZvLnRlc3RJZCwgcm93cyk7XHJcbiAgd29ya2Zsb3dQYWdlRmFpbHVyZXMuc2V0KHBhZ2UsIFtdKTtcclxuICBwcm9ncmVzc01pbGVzdG9uZXMuc2V0KGluZm8udGVzdElkLCBbXSk7XHJcbiAgY29uc3QgcmVxdWVzdHMgPSBuZXcgTWFwPG9iamVjdCwgV3JpdGVUaW1pbmc+KCk7XHJcbiAgcGFnZS5vbigncmVxdWVzdCcsIHJlcXVlc3QgPT4ge1xyXG4gICAgaWYgKCFbJ1BPU1QnLCAnUFVUJywgJ1BBVENIJywgJ0RFTEVURSddLmluY2x1ZGVzKHJlcXVlc3QubWV0aG9kKCkpKSByZXR1cm47XHJcbiAgICBjb25zdCByb3cgPSB7IHVybDogcmVxdWVzdC51cmwoKSwgc3RhcnRlZDogRGF0ZS5ub3coKSB9O1xyXG4gICAgcm93cy5wdXNoKHJvdyk7IHJlcXVlc3RzLnNldChyZXF1ZXN0LCByb3cpO1xyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3Jlc3BvbnNlJywgcmVzcG9uc2UgPT4ge1xyXG4gICAgY29uc3Qgcm93ID0gcmVxdWVzdHMuZ2V0KHJlc3BvbnNlLnJlcXVlc3QoKSk7XHJcbiAgICBpZiAocm93KSByb3cuc3RhdHVzID0gcmVzcG9uc2Uuc3RhdHVzKCk7XHJcbiAgICBpZiAocmVzcG9uc2Uuc3RhdHVzKCkgPT09IDQxMyAmJiAvXlxcL2FwaVxcL2VuZ2luZWVyaW5nXFwvd29ya2Zsb3coPzpcXC98JCkvLnRlc3QobmV3IFVSTChyZXNwb25zZS51cmwoKSkucGF0aG5hbWUpKSB7XHJcbiAgICAgIHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSEucHVzaChgSFRUUCA0MTM6ICR7cmVzcG9uc2UudXJsKCl9YCk7XHJcbiAgICB9XHJcbiAgfSk7XHJcbiAgcGFnZS5vbigncmVxdWVzdGZpbmlzaGVkJywgcmVxdWVzdCA9PiB7XHJcbiAgICBjb25zdCByb3cgPSByZXF1ZXN0cy5nZXQocmVxdWVzdCk7XHJcbiAgICBpZiAocm93KSByb3cuZHVyYXRpb25fbXMgPSBEYXRlLm5vdygpIC0gcm93LnN0YXJ0ZWQ7XHJcbiAgfSk7XHJcbiAgcGFnZS5vbigncmVxdWVzdGZhaWxlZCcsIHJlcXVlc3QgPT4ge1xyXG4gICAgY29uc3Qgcm93ID0gcmVxdWVzdHMuZ2V0KHJlcXVlc3QpO1xyXG4gICAgaWYgKHJvdykgeyByb3cuZHVyYXRpb25fbXMgPSBEYXRlLm5vdygpIC0gcm93LnN0YXJ0ZWQ7IHJvdy5mYWlsdXJlID0gcmVxdWVzdC5mYWlsdXJlKCk/LmVycm9yVGV4dDsgfVxyXG4gIH0pO1xyXG59KTtcclxuXHJcbnRlc3QuYWZ0ZXJFYWNoKGFzeW5jICh7IHBhZ2UgfSwgaW5mbykgPT4ge1xyXG4gIGF3YWl0IGluZm8uYXR0YWNoKCd3cml0ZS1yZXF1ZXN0LXRpbWluZ3MnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHdyaXRlVGltaW5ncy5nZXQoaW5mby50ZXN0SWQpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd29ya2Zsb3ctcHJvZ3Jlc3MtYm91bmRhcmllcycsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkocHJvZ3Jlc3NNaWxlc3RvbmVzLmdldChpbmZvLnRlc3RJZCkgfHwgW10pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gIGF3YWl0IGluZm8uYXR0YWNoKCd3b3JrZmxvdy1wYWdlLWZhaWx1cmVzJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh3b3JrZmxvd1BhZ2VGYWlsdXJlcy5nZXQocGFnZSkgfHwgW10pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gIHdyaXRlVGltaW5ncy5kZWxldGUoaW5mby50ZXN0SWQpO1xyXG4gIHByb2dyZXNzTWlsZXN0b25lcy5kZWxldGUoaW5mby50ZXN0SWQpO1xyXG4gIGV4cGVjdCh3b3JrZmxvd1BhZ2VGYWlsdXJlcy5nZXQocGFnZSksICdUaGUgdW5kZXJseWluZyBlbmdpbmVlcmluZyBwYWdlIG11c3QgcmVtYWluIHJlYWRhYmxlIHRocm91Z2hvdXQgcmVsb2FkIGFuZCByZWNvdmVyeS4nKS50b0VxdWFsKFtdKTtcclxufSk7XHJcblxyXG5hc3luYyBmdW5jdGlvbiBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2U6IFBhZ2UpIHtcclxuICBleHBlY3Qod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpLCAnQSB3b3JraW5nIHdpemFyZCBvdmVybGF5IG11c3Qgbm90IGNvbmNlYWwgYSB3b3JrZmxvdyBIVFRQIDQxMy4nKS50b0VxdWFsKFtdKTtcclxuICBleHBlY3QoYXdhaXQgcGFnZS5nZXRCeVRleHQoJ0VuZ2luZWVyaW5nLUFQSSBuaWNodCBlcnJlaWNoYmFyJywgeyBleGFjdDogdHJ1ZSB9KS5pc1Zpc2libGUoKSxcclxuICAgICdUaGUgdW5kZXJseWluZyBlbmdpbmVlcmluZyBwYWdlIG11c3Qgbm90IHNob3cgaXRzIEFQSSBlcnJvciB2aWV3LicpLnRvQmUoZmFsc2UpO1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiByZWFkUHJvamVjdChwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIHBhdGg6IHN0cmluZykge1xyXG4gIGNvbnN0IHJlc3VsdCA9IGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQocGF0aCwgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0sIHRpbWVvdXQ6IDYwXzAwMCB9KTtcclxuICB0cnkge1xyXG4gICAgaWYgKCFyZXN1bHQub2soKSkgdGhyb3cgbmV3IEVycm9yKGAke3BhdGh9OiBIVFRQICR7cmVzdWx0LnN0YXR1cygpfSAkeyhhd2FpdCByZXN1bHQudGV4dCgpKS5zbGljZSgwLCA0MDAwKX1gKTtcclxuICAgIHJldHVybiBhd2FpdCByZXN1bHQuanNvbigpO1xyXG4gIH0gZmluYWxseSB7XHJcbiAgICAvLyBQbGF5d3JpZ2h0IG90aGVyd2lzZSByZXRhaW5zIGV2ZXJ5IHBvbGxlZCByZXNwb25zZSB1bnRpbCBjb250ZXh0IHRlYXJkb3duLlxyXG4gICAgLy8gS2VlcCB0aGUgcGFyc2VkIGV2aWRlbmNlLCByZWxlYXNlIGl0cyBkdXBsaWNhdGUgdHJhbnNwb3J0IGJvZHkgaW1tZWRpYXRlbHkuXHJcbiAgICBhd2FpdCByZXN1bHQuZGlzcG9zZSgpO1xyXG4gIH1cclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVhZFdhcm5pbmdSZXZpZXdTdGF0ZShwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcpIHtcclxuICBjb25zdCBhdXRob3JpdHkgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICBjb25zdCBwYXJhbWV0ZXJzID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycpO1xyXG4gIGNvbnN0IHZlcmlmaWVkID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgZXhwZWN0KHBhcmFtZXRlcnMucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcclxuICBleHBlY3QoYXV0aG9yaXR5LnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgZXhwZWN0KHZlcmlmaWVkLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBbJ3J1bl9pZCcsICdyZXF1ZXN0X3JldmlzaW9uJ10pXHJcbiAgICBleHBlY3QodmVyaWZpZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LltmaWVsZF0pLnRvQmUoYXV0aG9yaXR5LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5bZmllbGRdKTtcclxuICByZXR1cm4geyBwcm9qZWN0X2lkOiB2ZXJpZmllZC5wcm9qZWN0X2lkLCBzdGF0dXNlczogdmVyaWZpZWQuc3RhdHVzZXMsXHJcbiAgICBjb250ZXh0OiB7IGFnZW50X2V4ZWN1dGlvbjogeyBydW5faWQ6IHZlcmlmaWVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQsXHJcbiAgICAgIHJlcXVlc3RfcmV2aXNpb246IHZlcmlmaWVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5yZXF1ZXN0X3JldmlzaW9uIH0gfSxcclxuICAgIHBhcmFtZXRlcnM6IHsgcHJlZmxpZ2h0X3dhcm5pbmdfYXBwcm92YWw6IHBhcmFtZXRlcnMucGFyYW1ldGVycy5wcmVmbGlnaHRfd2FybmluZ19hcHByb3ZhbCB9IH07XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIG9wZW5XaXphcmQocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nKSB7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvL2VuZ2luZWVyaW5nP2Fzc2lzdGFudD1wcm9qZWN0JnByb2plY3Q9JHtwcm9qZWN0fWAsIHsgd2FpdFVudGlsOiAnbG9hZCcgfSk7XHJcbiAgY29uc3QgZGlhbG9nID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IGFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkocGFnZSk7XHJcbiAgcmV0dXJuIGRpYWxvZztcclxufVxyXG5cclxudGVzdCgncHJvamVjdCBuYW1pbmcgZm9ybSBjYXJkcyB1c2UgdGhlIGZ1bGwgd2l6YXJkIHdpZHRoIEBsYXlvdXQnLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcclxuICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsICduaXMtZTJlLXByb2plY3QtbmFtZS1sYXlvdXQtJyArIHJhbmRvbVVVSUQoKSk7XHJcbiAgY29uc3Qgc3RlcCA9IGRpYWxvZy5sb2NhdG9yKCdmaWVsZHNldC5hZ2VudC1wcm9qZWN0LW5hbWUtc3RlcCcpO1xyXG4gIGF3YWl0IGV4cGVjdChzdGVwKS50b0JlVmlzaWJsZSgpO1xyXG4gIGNvbnN0IHN0ZXBXaWR0aCA9IGF3YWl0IHN0ZXAuZXZhbHVhdGUoZWxlbWVudCA9PiBlbGVtZW50LmdldEJvdW5kaW5nQ2xpZW50UmVjdCgpLndpZHRoKTtcclxuICBjb25zdCBjYXJkcyA9IGF3YWl0IHN0ZXAubG9jYXRvcignOnNjb3BlID4gbGFiZWwnKS5hbGwoKTtcclxuICBleHBlY3QoY2FyZHMpLnRvSGF2ZUxlbmd0aCg0KTtcclxuICBmb3IgKGNvbnN0IGNhcmQgb2YgY2FyZHMpIHtcclxuICAgIGNvbnN0IHdpZHRoID0gYXdhaXQgY2FyZC5ldmFsdWF0ZShlbGVtZW50ID0+IGVsZW1lbnQuZ2V0Qm91bmRpbmdDbGllbnRSZWN0KCkud2lkdGgpO1xyXG4gICAgZXhwZWN0KHdpZHRoKS50b0JlR3JlYXRlclRoYW4oc3RlcFdpZHRoICogMC44NSk7XHJcbiAgfVxyXG59KTtcclxuXHJcbmFzeW5jIGZ1bmN0aW9uIGFsbE9iamVjdHMocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCByZXNvdXJjZTogc3RyaW5nKSB7XHJcbiAgY29uc3QgaXRlbXM6IGFueVtdID0gW107XHJcbiAgZm9yIChsZXQgb2Zmc2V0ID0gMDsgOyBvZmZzZXQgKz0gNTAwKSB7XHJcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL2VuZ2luZWVyaW5nLyR7cmVzb3VyY2V9P2xpbWl0PTUwMCZvZmZzZXQ9JHtvZmZzZXR9YCk7XHJcbiAgICBpdGVtcy5wdXNoKC4uLnJlc3BvbnNlLml0ZW1zKTtcclxuICAgIGlmIChyZXNwb25zZS5pdGVtcy5sZW5ndGggPCA1MDApIHJldHVybiBpdGVtcztcclxuICB9XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHJlc3RhcnRBcHBsaWNhdGlvbihwYWdlOiBQYWdlLCBjcmFzaCA9IGZhbHNlKSB7XHJcbiAgY29uc3QgY29udGFpbmVyID0gcHJvY2Vzcy5lbnYuTklTX0UyRV9BUFBfQ09OVEFJTkVSITtcclxuICBleHBlY3QoY29udGFpbmVyKS50b01hdGNoKC9ebmlzLWUyZS1hcHAtW2EtZjAtOV0rJC8pO1xyXG4gIGNvbnN0IGRvY2tlciA9IHByb2Nlc3MuZW52Lk5JU19URVNUX0RPQ0tFUiB8fCAnZG9ja2VyJztcclxuICBjb25zdCBsYWJlbCA9IGV4ZWNGaWxlU3luYyhkb2NrZXIsIFsnaW5zcGVjdCcsIGNvbnRhaW5lciwgJy0tZm9ybWF0JywgJ3t7aW5kZXggLkNvbmZpZy5MYWJlbHMgXCJuZXR3b3JraXMudGVzdFwifX0nXSwgeyBlbmNvZGluZzogJ3V0ZjgnIH0pLnRyaW0oKTtcclxuICBleHBlY3QobGFiZWwpLnRvQmUoJ2Rpc3Bvc2FibGUnKTtcclxuICBleGVjRmlsZVN5bmMoZG9ja2VyLCBbJ3Jlc3RhcnQnLCAuLi4oY3Jhc2ggPyBbJy10JywgJzAnXSA6IFtdKSwgY29udGFpbmVyXSwgeyB0aW1lb3V0OiA2MF8wMDAgfSk7XHJcbiAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgdHJ5IHsgcmV0dXJuIChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL3JlYWR5JywgeyB0aW1lb3V0OiAyMDAwIH0pKS5vaygpOyB9IGNhdGNoIHsgcmV0dXJuIGZhbHNlOyB9XHJcbiAgfSwgeyB0aW1lb3V0OiAxMjBfMDAwIH0pLnRvQmUodHJ1ZSk7XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHZlcmlmeVNpZ25hbENvbnRyYWN0cyhwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIGV4cGVjdGVkOiBSZWNvcmQ8c3RyaW5nLCB1bmtub3duPikge1xyXG4gIGNvbnN0IFtoYXJkd2FyZSwgZnVuY3Rpb25zLCBtZXNzYWdlcywgc2lnbmFsc10gPSBhd2FpdCBQcm9taXNlLmFsbChcclxuICAgIFsnaGFyZHdhcmUtbm9kZXMnLCAnZnVuY3Rpb25zJywgJ21lc3NhZ2VzJywgJ3NpZ25hbHMnXS5tYXAocmVzb3VyY2UgPT4gYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCByZXNvdXJjZSkpKTtcclxuICBjb25zdCBub2RlcyA9IG5ldyBNYXAoaGFyZHdhcmUubWFwKGl0ZW0gPT4gW2l0ZW0uaWQsIGl0ZW1dKSk7XHJcbiAgY29uc3QgZnVuY3Rpb25zQnlJZCA9IG5ldyBNYXAoZnVuY3Rpb25zLm1hcChpdGVtID0+IFtpdGVtLmlkLCBpdGVtXSkpO1xyXG4gIGNvbnN0IG1lc3NhZ2VzQnlJZCA9IG5ldyBNYXAobWVzc2FnZXMubWFwKGl0ZW0gPT4gW2l0ZW0uaWQsIGl0ZW1dKSk7XHJcbiAgY29uc3QgY29udHJhY3RzOiBSZWNvcmQ8c3RyaW5nLCB1bmtub3duPiA9IHt9O1xyXG4gIGZvciAoY29uc3Qgc2lnbmFsIG9mIHNpZ25hbHMpIHtcclxuICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlc0J5SWQuZ2V0KHNpZ25hbC5tZXNzYWdlX2lkKTtcclxuICAgIGV4cGVjdChtZXNzYWdlKS50b0JlVHJ1dGh5KCk7XHJcbiAgICBjb25zdCByZWZlcmVuY2UgPSBtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdC5wcm9kdWNlcl9yZWY7XHJcbiAgICBjb25zdCBmbiA9IGZ1bmN0aW9uc0J5SWQuZ2V0KHJlZmVyZW5jZSk7XHJcbiAgICBjb25zdCBvd25lciA9IG5vZGVzLmdldChyZWZlcmVuY2UpIHx8IChmbiAmJiBub2Rlcy5nZXQoZm4uaGFyZHdhcmVfbm9kZV9pZCkpO1xyXG4gICAgY29uc3QgcHJvZHVjZXIgPSBvd25lcj8uZGV2aWNlX3R5cGUgPT09ICdHYXRld2F5JyA/ICckZ2F0ZXdheScgOiAobm9kZXMuZ2V0KHJlZmVyZW5jZSkgfHwgZm4pPy5uYW1lO1xyXG4gICAgZXhwZWN0KHByb2R1Y2VyKS50b0JlVHJ1dGh5KCk7XHJcbiAgICBjb25zdCBrZXkgPSBbcHJvZHVjZXIsIG1lc3NhZ2UubmFtZSwgc2lnbmFsLm5hbWVdLmpvaW4oJyA6OiAnKTtcclxuICAgIGV4cGVjdChjb250cmFjdHNba2V5XSwgJ1NlbWFudGljIHNpZ25hbCBpZGVudGl0eSBtdXN0IGJlIHVuaXF1ZTogJyArIGtleSkudG9CZVVuZGVmaW5lZCgpO1xyXG4gICAgY29udHJhY3RzW2tleV0gPSB7XHJcbiAgICAgIC4uLk9iamVjdC5mcm9tRW50cmllcyhbJ3N0YXJ0X2JpdCcsICdsZW5ndGhfYml0cycsICdkYXRhX3R5cGUnLCAnZmFjdG9yJywgJ29mZnNldF92YWx1ZScsXHJcbiAgICAgICAgJ3VuaXQnLCAnbWluX3ZhbHVlJywgJ21heF92YWx1ZScsICdieXRlX29yZGVyJ10ubWFwKGZpZWxkID0+IFtmaWVsZCwgc2lnbmFsW2ZpZWxkXSA/PyBudWxsXSkpLFxyXG4gICAgICBlbnVtX3ZhbHVlczogc2lnbmFsLmRhdGE/LmVudW1fdmFsdWVzID8/IG51bGwsXHJcbiAgICAgIHNlbWFudGljX3R5cGU6IHNpZ25hbC5zZW1hbnRpYz8uc2VtYW50aWNfdHlwZSA/PyBudWxsLFxyXG4gICAgICBnZW5lcmF0aW9uX3JvbGU6IHNpZ25hbC5jb25maWd1cmF0aW9uPy5nZW5lcmF0aW9uX3JvbGUgPz8gbnVsbCxcclxuICAgIH07XHJcbiAgfVxyXG4gIGV4cGVjdChjb250cmFjdHMsICdFdmVyeSBvcmlnaW5hbCBzaWduYWwgYW5kIGl0cyBleHBsaWNpdCBlbmNvZGluZyBtdXN0IHN1cnZpdmUgZ2VuZXJhdGlvbi4nKS50b0VxdWFsKGV4cGVjdGVkKTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gdmVyaWZ5QXJ0aWZhY3RzKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgbWluaW11bUNhbm9uaWNhbFNpZ25hbHM6IG51bWJlciwgaW50ZXJuYWxDb250cm9sbGVyPzogc3RyaW5nKSB7XHJcbiAgLy8gVGhlIGNvbXBsZXRlZCBtb2RlbCBpcyBzdGFibGU7IHRoZXNlIGluZGVwZW5kZW50IHJlYWRzIG5lZWQgbm8gc2VyaWFsIHdhaXRzLlxyXG4gIGNvbnN0IFt3b3JrZmxvdywgam9iTGlzdCwgc25hcHNob3RzLCBzaWduYWxzLCBtZXNzYWdlc10gPSBhd2FpdCBQcm9taXNlLmFsbChbXHJcbiAgICByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKSxcclxuICAgIHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJyksXHJcbiAgICByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9zbmFwc2hvdHMnKSxcclxuICAgIGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ3NpZ25hbHMnKSxcclxuICAgIGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ21lc3NhZ2VzJyksXHJcbiAgXSk7XHJcbiAgZXhwZWN0KE9iamVjdC5rZXlzKHdvcmtmbG93LnN0YXR1c2VzKS5zb3J0KCkpLnRvRXF1YWwoWy4uLnN0ZXBzXS5zb3J0KCkpO1xyXG4gIGZvciAoY29uc3Qgc3RlcCBvZiBzdGVwcykgZXhwZWN0KGRvbmUuaGFzKHdvcmtmbG93LnN0YXR1c2VzW3N0ZXBdKSwgYCR7c3RlcH06ICR7d29ya2Zsb3cuc3RhdHVzZXNbc3RlcF19YCkudG9CZVRydXRoeSgpO1xyXG4gIGNvbnN0IGpvYnMgPSBqb2JMaXN0LmpvYnM7XHJcbiAgZXhwZWN0KGpvYnMpLnRvSGF2ZUxlbmd0aCgxKTtcclxuICBleHBlY3Qoam9ic1swXS5zdGF0dXMpLnRvQmUoJ2NvbXBsZXRlZCcpO1xyXG4gIGNvbnN0IHNuYXBzaG90ID0gc25hcHNob3RzLnNpbXVsYXRpb25zLmZpbmQoKGl0ZW06IHsgam9iX2lkOiBzdHJpbmcgfSkgPT4gaXRlbS5qb2JfaWQgPT09IGpvYnNbMF0uaWQpO1xyXG4gIGV4cGVjdChzbmFwc2hvdCkudG9CZVRydXRoeSgpO1xyXG4gIGNvbnN0IGZ1bGwgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9zaW11bGF0aW9uLXNuYXBzaG90cy8ke3NuYXBzaG90LmlkfWApO1xyXG4gIGNvbnN0IGFzc2Vzc21lbnQgPSBmdWxsLnJlc3VsdC5hc3Nlc3NtZW50O1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnNjb3BlX21vZGUpLnRvQmUoJ0FMTCcpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLmNvbXBsZXRlKS50b0JlKHRydWUpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LmNvbmZvcm1hbmNlKS50b0JlKCdQQVNTJyk7XHJcbiAgZXhwZWN0KGFzc2Vzc21lbnQuZmFpbGVkX3JvdXRlX2NvdW50KS50b0JlKDApO1xyXG4gIGV4cGVjdChzaWduYWxzLmxlbmd0aCwgJ1RoZSBmdWxsIGNhbm9uaWNhbCBzaWduYWwgaW52ZW50b3J5IG11c3Qgc3Vydml2ZSBnZW5lcmF0aW9uLicpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwobWluaW11bUNhbm9uaWNhbFNpZ25hbHMpO1xyXG4gIGNvbnN0IGV4Y2x1ZGVkID0gYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS50cmFuc3BvcnRfZXhjbHVzaW9ucyA/PyBbXTtcclxuICBmb3IgKGNvbnN0IGl0ZW0gb2YgZXhjbHVkZWQpIHtcclxuICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKHJvdyA9PiByb3cuaWQgPT09IGl0ZW0ubWVzc2FnZV9pZCk7XHJcbiAgICBleHBlY3QobWVzc2FnZSwgYEV4Y2x1ZGVkIG1lc3NhZ2UgJHtpdGVtLm1lc3NhZ2VfaWR9IG11c3QgZXhpc3QuYCkudG9CZVRydXRoeSgpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5yb3V0aW5nLmVuYWJsZWQpLnRvQmUoZmFsc2UpO1xyXG4gICAgY29uc3QgY29udHJhY3QgPSBtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdDtcclxuICAgIGV4cGVjdChjb250cmFjdC5jb25zdW1lcl9yZWZzKS50b0VxdWFsKFtdKTtcclxuICAgIGV4cGVjdChpdGVtLnJlYXNvbl9jb2RlKS50b0JlKGNvbnRyYWN0LnJvbGUgPT09ICdJTlRFUk5BTF9TVEFURSdcclxuICAgICAgPyAnSU5URVJOQUxfU1RBVEVfTk9UX1JPVVRFRCcgOiAnRVhQTElDSVRfRlVOQ1RJT05fT1VUUFVUX05PVF9ST1VURUQnKTtcclxuICB9XHJcbiAgaWYgKGludGVybmFsQ29udHJvbGxlcikge1xyXG4gICAgY29uc3Qgbm9kZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gICAgY29uc3QgY29udHJvbGxlciA9IG5vZGVzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09IGludGVybmFsQ29udHJvbGxlcik7XHJcbiAgICBleHBlY3QoZXhjbHVkZWQubGVuZ3RoKS50b0JlR3JlYXRlclRoYW4oMCk7XHJcbiAgICBmb3IgKGNvbnN0IGl0ZW0gb2YgZXhjbHVkZWQpIHtcclxuICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzLmZpbmQocm93ID0+IHJvdy5pZCA9PT0gaXRlbS5tZXNzYWdlX2lkKTtcclxuICAgICAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0KS50b01hdGNoT2JqZWN0KHsgcm9sZTogJ0lOVEVSTkFMX1NUQVRFJywgc2NvcGU6ICdJTlRFUk5BTCcsIHByb2R1Y2VyX3JlZjogY29udHJvbGxlci5pZCwgY29uc3VtZXJfcmVmczogW10gfSk7XHJcbiAgICB9XHJcbiAgfVxyXG4gIGNvbnN0IGV4Y2x1ZGVkU2lnbmFscyA9IG5ldyBTZXQoZXhjbHVkZWQuZmxhdE1hcCgoaXRlbTogeyBzaWduYWxfaWRzOiBzdHJpbmdbXSB9KSA9PiBpdGVtLnNpZ25hbF9pZHMpKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQsICdBTEwgbXVzdCBvYnNlcnZlIGV2ZXJ5IGNhbm9uaWNhbCBzaWduYWwgd2l0aCBhIHRyYW5zcG9ydCBvYmxpZ2F0aW9uLicpLnRvQmUoc2lnbmFscy5sZW5ndGggLSBleGNsdWRlZFNpZ25hbHMuc2l6ZSk7XHJcbiAgZm9yIChjb25zdCBrZXkgb2YgWydtaXNzaW5nX29ic2VydmVkX3NpZ25hbF9pZHMnLCAnbWlzc2luZ19vYnNlcnZlZF9yb3V0ZV9pZHMnLCAnbWlzc2luZ19vYnNlcnZlZF9uZXR3b3JrX2lkcyddKSBleHBlY3QoYXNzZXNzbWVudFtrZXldKS50b0VxdWFsKFtdKTtcclxuICBjb25zdCB0cmFjZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL3NpbXVsYXRpb25zLyR7am9ic1swXS5pZH0vdHJhY2Utd2luZG93P2xpbWl0PTEwYCk7XHJcbiAgZXhwZWN0KHRyYWNlLmNvdW50KS50b0JlR3JlYXRlclRoYW4oMCk7XHJcbiAgZXhwZWN0KHRyYWNlLmV2ZW50cy5zb21lKChpdGVtOiB7IHNpZ25hbHM/OiB1bmtub3duW10gfSkgPT4gaXRlbS5zaWduYWxzICYmIE9iamVjdC5rZXlzKGl0ZW0uc2lnbmFscykubGVuZ3RoKSkudG9CZVRydXRoeSgpO1xyXG4gIHJldHVybiB7IHdvcmtmbG93LCBqb2I6IGpvYnNbMF0uaWQsIGFzc2Vzc21lbnQgfTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcmVzdGFydDogYm9vbGVhbiwgZXhwZWN0ZWRIYXJkd2FyZTogc3RyaW5nW10gPSBbXSwgY3Jhc2hTaW11bGF0aW9uID0gZmFsc2UsXHJcbiAgZXhwZWN0ZWRTaWduYWxzPzogUmVjb3JkPHN0cmluZywgdW5rbm93bj4sIGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQ/OiAoKSA9PiBQcm9taXNlPHZvaWQ+LCBzdG9wT25FdmlkZW5jZUJsb2NrID0gZmFsc2UpIHtcclxuICBsZXQgcmV2aWV3Q291bnQgPSAwO1xyXG4gIGxldCBydW5JZDogc3RyaW5nIHwgdW5kZWZpbmVkO1xyXG4gIGNvbnN0IHJldmlld2VkID0gbmV3IFNldDxzdHJpbmc+KCk7XHJcbiAgbGV0IHJlc3RhcnRlZEpvYklkOiBzdHJpbmcgfCB1bmRlZmluZWQ7XHJcbiAgbGV0IHdhdGNoZG9nID0gbmV3IFdpemFyZFByb2dyZXNzV2F0Y2hkb2cocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gIGZvciAobGV0IGNoZWNrcG9pbnQgPSAwOyBjaGVja3BvaW50IDwgMTY7IGNoZWNrcG9pbnQrKykge1xyXG4gICAgbGV0IHdvcmtmbG93OiBhbnk7XHJcbiAgICBsZXQgcHJvcG9zYWxJZCA9ICcnO1xyXG4gICAgbGV0IHJlYWR5VmVyc2lvbiA9ICcnO1xyXG4gICAgbGV0IHJlYWR5U2luY2UgPSAwO1xyXG4gICAgY29uc3QgaXNDaGVja3BvaW50ID0gYXN5bmMgKCkgPT4ge1xyXG4gICAgICB3YXRjaGRvZy5yZW1haW5pbmcocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gICAgICBhd2FpdCBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2UpO1xyXG4gICAgICB3b3JrZmxvdyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICBjb25zdCBwcm9ncmVzcyA9IHdhdGNoZG9nLm9ic2VydmUod29ya2Zsb3csIHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICAgICAgaWYgKHByb2dyZXNzLmFkdmFuY2VkKSBwcm9ncmVzc01pbGVzdG9uZXMuZ2V0KHRlc3QuaW5mbygpLnRlc3RJZCkhLnB1c2goe1xyXG4gICAgICAgIGF0OiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksIGZyb250aWVyOiBwcm9ncmVzcy5mcm9udGllcixcclxuICAgICAgICBjb21wbGV0ZWRUaHJvdWdoOiBzdGVwc1twcm9ncmVzcy5mcm9udGllciAtIDFdLFxyXG4gICAgICAgIHByb2plY3Q6IHdvcmtmbG93LnByb2plY3RfaWQsIGV4ZWN1dGlvbjogd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24sXHJcbiAgICAgIH0pO1xyXG4gICAgICBpZiAoY3Jhc2hTaW11bGF0aW9uICYmICFyZXN0YXJ0ZWRKb2JJZCAmJiBkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlcy52YWxpZGF0aW9uKSkge1xyXG4gICAgICAgIGNvbnN0IGpvYnMgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icztcclxuICAgICAgICBjb25zdCBydW5uaW5nID0gam9icy5maW5kKChqb2I6IHsgc3RhdHVzOiBzdHJpbmcgfSkgPT4gam9iLnN0YXR1cyA9PT0gJ3J1bm5pbmcnKTtcclxuICAgICAgICBpZiAocnVubmluZykge1xyXG4gICAgICAgICAgcmVzdGFydGVkSm9iSWQgPSBydW5uaW5nLmlkO1xyXG4gICAgICAgICAgYXdhaXQgcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2UsIHRydWUpO1xyXG4gICAgICAgICAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICAgICAgICAgIHJldHVybiBmYWxzZTtcclxuICAgICAgICB9XHJcbiAgICAgIH1cclxuICAgICAgaWYgKHN0ZXBzLmV2ZXJ5KHN0ZXAgPT4gZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXNbc3RlcF0pKSkgcmV0dXJuIHRydWU7XHJcbiAgICAgIGNvbnN0IGV4ZWN1dGlvbiA9IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uO1xyXG4gICAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JFVklFV19SRVFVSVJFRCcpIHtcclxuICAgICAgICBjb25zdCBjb252ZXJzYXRpb24gPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKTtcclxuICAgICAgICBwcm9wb3NhbElkID0gY29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsO1xyXG4gICAgICAgIC8vIFBvbGxpbmcgbWF5IHN0aWxsIGV4cG9zZSB0aGUganVzdC1hcHBsaWVkIHJldmlldyB3aGlsZSB0aGUgVUkgc3RhcnRzXHJcbiAgICAgICAgLy8gaXRzIGR1cmFibGUgY29udGludWF0aW9uLiBXYWl0IGZvciBhIGRpc3RpbmN0IHByb3Bvc2FsLCBub3QgaXRzIGxhYmVsLlxyXG4gICAgICAgIHJldHVybiBCb29sZWFuKHByb3Bvc2FsSWQpICYmICFyZXZpZXdlZC5oYXMocHJvcG9zYWxJZCk7XHJcbiAgICAgIH1cclxuICAgICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdSRUFEWV9UT19DT05USU5VRScgfHwgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24ucmVjb3ZlcmFibGUgPT09IHRydWUpKSB7XHJcbiAgICAgICAgaWYgKHJlYWR5VmVyc2lvbiAhPT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQpIHtcclxuICAgICAgICAgIHJlYWR5VmVyc2lvbiA9IGV4ZWN1dGlvbi51cGRhdGVkX2F0OyByZWFkeVNpbmNlID0gRGF0ZS5ub3coKTtcclxuICAgICAgICB9XHJcbiAgICAgICAgLy8gV2hpbGUgYSBsYXJnZSBjb250aW51YXRpb24gaXMgZ2VuZXJhdGluZywgdGhlIGxhc3QgY29tbWl0dGVkIHNlcnZlclxyXG4gICAgICAgIC8vIGNoZWNrcG9pbnQgY2FuIHN0aWxsIGJlIFJFQURZLiBBY3Qgb25seSB3aGVuIHRoZSBVSSBvZmZlcnMgaXQgdG9vLlxyXG4gICAgICAgIGNvbnN0IGJ1dHRvbiA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSlcclxuICAgICAgICAgIC5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1ZnRyYWcgZm9ydHNldHplbicsIGV4YWN0OiB0cnVlIH0pO1xyXG4gICAgICAgIHJldHVybiBEYXRlLm5vdygpIC0gcmVhZHlTaW5jZSA+IDUwMDAgJiYgYXdhaXQgYnV0dG9uLmV2YWx1YXRlQWxsKGJ1dHRvbnMgPT4gYnV0dG9ucy5zb21lKGJ1dHRvbiA9PiAhKGJ1dHRvbiBhcyBIVE1MQnV0dG9uRWxlbWVudCkuZGlzYWJsZWQgJiYgYnV0dG9uLmdldENsaWVudFJlY3RzKCkubGVuZ3RoID4gMCAmJiBnZXRDb21wdXRlZFN0eWxlKGJ1dHRvbikudmlzaWJpbGl0eSAhPT0gXCJoaWRkZW5cIikpO1xyXG4gICAgICB9XHJcbiAgICAgIHJldHVybiBbJ0JMT0NLRUQnLCAnRkFJTEVEJywgJ0lOQ09NUExFVEUnXS5pbmNsdWRlcyhleGVjdXRpb24/LnN0YXRlKTtcclxuICAgIH07XHJcbiAgICAvLyBBIHNpbmdsZSBwb2xsIHByZXZpb3VzbHkgdGltZWQgYWxsIG9mIENhcGFjaXR5IC0+IEludGVsbGlnZW5jZSB0b2dldGhlci5cclxuICAgIC8vIEJvdW5kIGVhY2ggZ2VudWluZSBzdGFnZSBhZHZhbmNlLCB3aGlsZSByZXRyaWVzIGFuZCByZXN0YXJ0cyByZXRhaW4gdGhlaXJcclxuICAgIC8vIHJlbWFpbmluZyBkZWFkbGluZS4gVGhlIGluZGVwZW5kZW50IDIwLW1pbnV0ZSB0ZXN0IHRpbWVvdXQgaXMgdW5jaGFuZ2VkLlxyXG4gICAgbGV0IGF0dGVtcHQgPSAwO1xyXG4gICAgd2hpbGUgKCFhd2FpdCBpc0NoZWNrcG9pbnQoKSkge1xyXG4gICAgICBjb25zdCByZW1haW5pbmcgPSB3YXRjaGRvZy5yZW1haW5pbmcocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gICAgICBhd2FpdCBwYWdlLndhaXRGb3JUaW1lb3V0KE1hdGgubWluKFs1MDAsIDEwMDAsIDIwMDBdW01hdGgubWluKGF0dGVtcHQrKywgMildLCByZW1haW5pbmcpKTtcclxuICAgIH1cclxuICAgIHJ1bklkID8/PSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQpLnRvQmUocnVuSWQpO1xyXG4gICAgaWYgKHN0ZXBzLmV2ZXJ5KHN0ZXAgPT4gZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXNbc3RlcF0pKSkge1xyXG4gICAgICBpZiAoY3Jhc2hTaW11bGF0aW9uKSBleHBlY3QocmVzdGFydGVkSm9iSWQsICdBIHJlYWwgcnVubmluZyBzaW11bGF0aW9uIG11c3QgYmUgb2JzZXJ2ZWQgYW5kIGludGVycnVwdGVkLicpLnRvQmVUcnV0aHkoKTtcclxuICAgICAgcmV0dXJuIHsgcnVuSWQsIHJldmlld2VkOiBbLi4ucmV2aWV3ZWRdLCByZXN0YXJ0ZWRKb2JJZCB9O1xyXG4gICAgfVxyXG4gICAgY29uc3QgZXhlY3V0aW9uID0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb247XHJcbiAgICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pO1xyXG4gICAgaWYgKHN0b3BPbkV2aWRlbmNlQmxvY2sgJiYgZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5ibG9ja2luZ19maW5kaW5ncz8ubGVuZ3RoKSB7XHJcbiAgICAgIHRocm93IG5ldyBFcnJvcihgV2l6YXJkIEJMT0NLRUQgYXQgJHtleGVjdXRpb24uc3RlcH06ICR7ZXhlY3V0aW9uLm1lc3NhZ2V9YCk7XHJcbiAgICB9XHJcbiAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5tZXNzYWdlPy5pbmNsdWRlcygnUkVBRFlfV0lUSF9XQVJOSU5HUycpKSB7XHJcbiAgICAgIGNvbnN0IGJlZm9yZVJldmlldyA9IGF3YWl0IHJlYWRXYXJuaW5nUmV2aWV3U3RhdGUocGFnZSwgcHJvamVjdCk7XHJcbiAgICAgIGNvbnN0IHByZWZsaWdodCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3ByZWZsaWdodCcpO1xyXG4gICAgICBjb25zdCB3YXJuaW5ncyA9IGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ1ByZWZsaWdodC1XYXJudW5nZW4nIH0pO1xyXG4gICAgICBhd2FpdCBleHBlY3Qod2FybmluZ3MuZ2V0QnlSb2xlKCdsaXN0aXRlbScpLmZpcnN0KCkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgICAgIGNvbnN0IHN0YXJ0ZWQgPSBwZXJmb3JtYW5jZS5ub3coKSwgc3RhcnRlZFdhbGwgPSBEYXRlLm5vdygpO1xyXG4gICAgICB3YXRjaGRvZy5yZW1haW5pbmcoc3RhcnRlZCk7XHJcbiAgICAgIGNvbnN0IGFwcHJvdmFsUmVzcG9uc2UgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiBuZXcgVVJMKHJlc3BvbnNlLnVybCgpKS5wYXRobmFtZSA9PT0gJy9hcGkvZW5naW5lZXJpbmcvcHJlZmxpZ2h0L3dhcm5pbmdzL2FwcHJvdmUnXHJcbiAgICAgICAgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcsIHsgdGltZW91dDogMTgwXzAwMCB9KTtcclxuICAgICAgYXdhaXQgd2FybmluZ3MuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdXYXJudW5nZW4gZnJlaWdlYmVuIHVuZCBmb3J0c2V0emVuJyB9KS5jbGljaygpO1xyXG4gICAgICBjb25zdCBhcHByb3ZlZCA9IGF3YWl0IGFwcHJvdmFsUmVzcG9uc2U7XHJcbiAgICAgIGNvbnN0IHJlY2VpcHQgPSBhd2FpdCBhcHByb3ZlZC5qc29uKCk7XHJcbiAgICAgIGNvbnN0IGFmdGVyUmV2aWV3ID0gYXdhaXQgcmVhZFdhcm5pbmdSZXZpZXdTdGF0ZShwYWdlLCBwcm9qZWN0KTtcclxuICAgICAgY29uc3QgcHJvb2YgPSB7IGJlZm9yZTogYmVmb3JlUmV2aWV3LCBhZnRlcjogYWZ0ZXJSZXZpZXcsIHNuYXBzaG90SWQ6IHByZWZsaWdodC5pZCxcclxuICAgICAgICByZXF1ZXN0UHJvamVjdDogYXBwcm92ZWQucmVxdWVzdCgpLmhlYWRlcnMoKVsneC1wcm9qZWN0LWlkJ10sIHN1Ym1pdHRlZDogYXBwcm92ZWQucmVxdWVzdCgpLnBvc3REYXRhSlNPTigpLFxyXG4gICAgICAgIHN0YXR1czogYXBwcm92ZWQuc3RhdHVzKCksIHJlc3BvbnNlOiByZWNlaXB0LCBzdGFydGVkLCBzdGFydGVkV2FsbCwgZmluaXNoZWRXYWxsOiBEYXRlLm5vdygpIH07XHJcbiAgICAgIGNvbnN0IGNvbW1pdHRlZEF0ID0gcGVyZm9ybWFuY2Uubm93KCk7XHJcbiAgICAgIGNvbnN0IGNvbW1pdHRlZCA9IHdhdGNoZG9nLmNvbW1pdFdhcm5pbmdSZXZpZXcocHJvb2YsIGNvbW1pdHRlZEF0KTtcclxuICAgICAgYXdhaXQgdGVzdC5pbmZvKCkuYXR0YWNoKCd2ZXJpZmllZC13YXJuaW5nLXJldmlldy1wcm9vZicsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9vZiwgY29tbWl0dGVkQXQsIGNvbW1pdHRlZCB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICAgICAgcHJvZ3Jlc3NNaWxlc3RvbmVzLmdldCh0ZXN0LmluZm8oKS50ZXN0SWQpIS5wdXNoKHsgYXQ6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSwgbWFudWFsV2FybmluZ0FwcHJvdmFsOiBjb21taXR0ZWQuYXBwcm92YWxJZGVudGl0eSxcclxuICAgICAgICBmcm9udGllcjogY29tbWl0dGVkLmZyb250aWVyLCBwcm9qZWN0LCBleGVjdXRpb246IGFmdGVyUmV2aWV3LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLCBhcHByb3ZhbDogcmVjZWlwdC5hcHByb3ZhbCB9KTtcclxuICAgICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpKS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCxcclxuICAgICAgICB7IHRpbWVvdXQ6IGV4cGVjdGVkSGFyZHdhcmUubGVuZ3RoID4gMTAwID8gMTgwXzAwMCA6IDYwXzAwMCB9KS5ub3QudG9CZShleGVjdXRpb24udXBkYXRlZF9hdCk7XHJcbiAgICAgIGNvbnRpbnVlO1xyXG4gICAgfVxyXG4gICAgaWYgKFsnQkxPQ0tFRCcsICdGQUlMRUQnLCAnSU5DT01QTEVURSddLmluY2x1ZGVzKGV4ZWN1dGlvbj8uc3RhdGUpICYmIGV4ZWN1dGlvbi5yZWNvdmVyYWJsZSAhPT0gdHJ1ZSkge1xyXG4gICAgICBjb25zdCBjb252ZXJzYXRpb24gPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKTtcclxuICAgICAgY29uc3QgaWQgPSBjb252ZXJzYXRpb24uZGF0YT8uYWN0aXZlX3Byb3Bvc2FsO1xyXG4gICAgICBjb25zdCBwcm9wb3NhbCA9IGlkID8gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7aWR9YCkgOiBudWxsO1xyXG4gICAgICBhd2FpdCB0ZXN0LmluZm8oKS5hdHRhY2goJ3dpemFyZC1ibG9ja2VyJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IGV4ZWN1dGlvbixcclxuICAgICAgICBwcm9wb3NhbDogcHJvcG9zYWw/LmRhdGE/LnZhbGlkYXRpb25fcmVzdWx0LCB2aXNpYmxlOiBhd2FpdCBkaWFsb2cuaW5uZXJUZXh0KCkgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgICAgIHRocm93IG5ldyBFcnJvcihgV2l6YXJkICR7ZXhlY3V0aW9uLnN0YXRlfSBhdCAke2V4ZWN1dGlvbi5zdGVwfTogJHtleGVjdXRpb24ubWVzc2FnZX1gKTtcclxuICAgIH1cclxuICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnUkVBRFlfVE9fQ09OVElOVUUnIHx8IChleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLnJlY292ZXJhYmxlID09PSB0cnVlKSkge1xyXG4gICAgICBjb25zdCBidXR0b24gPSBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBdWZ0cmFnIGZvcnRzZXR6ZW4nLCBleGFjdDogdHJ1ZSB9KTtcclxuICAgICAgdHJ5IHtcclxuICAgICAgICBhd2FpdCBidXR0b24uY2xpY2soeyB0aW1lb3V0OiAyMDAwIH0pO1xyXG4gICAgICB9IGNhdGNoIChlcnJvcikge1xyXG4gICAgICAgIGNvbnN0IGxhdGVzdCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICAgIGlmIChsYXRlc3QuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQgPT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0ICYmIGF3YWl0IGJ1dHRvbi5ldmFsdWF0ZUFsbChidXR0b25zID0+IGJ1dHRvbnMuc29tZShidXR0b24gPT4gIShidXR0b24gYXMgSFRNTEJ1dHRvbkVsZW1lbnQpLmRpc2FibGVkICYmIGJ1dHRvbi5nZXRDbGllbnRSZWN0cygpLmxlbmd0aCA+IDAgJiYgZ2V0Q29tcHV0ZWRTdHlsZShidXR0b24pLnZpc2liaWxpdHkgIT09IFwiaGlkZGVuXCIpKSkgdGhyb3cgZXJyb3I7XHJcbiAgICAgICAgY29udGludWU7XHJcbiAgICAgIH1cclxuICAgICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgICAgIGNvbnN0IGxhdGVzdCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICAgIHJldHVybiBsYXRlc3QuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQgIT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0XHJcbiAgICAgICAgICB8fCBsYXRlc3QuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnN0YXRlID09PSAnUlVOTklORydcclxuICAgICAgICAgIHx8IGxhdGVzdC5zdGF0dXNlcz8uW2V4ZWN1dGlvbi5zdGVwXSA9PT0gJ0lOX1BST0dSRVNTJztcclxuICAgICAgfSwgeyB0aW1lb3V0OiA2MF8wMDAgfSkudG9CZSh0cnVlKTtcclxuICAgICAgY29udGludWU7XHJcbiAgICB9XHJcbiAgICBjb25zdCBjYW5kaWRhdGUgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtwcm9wb3NhbElkfWApO1xyXG4gICAgaWYgKGNhbmRpZGF0ZS5kYXRhLnByb3Bvc2FsX3R5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnICYmIHJldmlld0NvdW50ID09PSAwICYmIGV4cGVjdGVkSGFyZHdhcmUubGVuZ3RoKSB7XHJcbiAgICAgIGNvbnN0IGhhcmR3YXJlID0gY2FuZGlkYXRlLmRhdGEuY2hhbmdlc1xyXG4gICAgICAgIC5maWx0ZXIoKGNoYW5nZTogeyBvYmplY3RfdHlwZTogc3RyaW5nIH0pID0+IGNoYW5nZS5vYmplY3RfdHlwZSA9PT0gJ0hhcmR3YXJlTm9kZScpXHJcbiAgICAgICAgLm1hcCgoY2hhbmdlOiB7IGRhdGE6IHsgbmFtZTogc3RyaW5nIH0gfSkgPT4gY2hhbmdlLmRhdGEubmFtZSk7XHJcbiAgICAgIGV4cGVjdChoYXJkd2FyZSwgJ1RoZSBVSSBtdXN0IHByZXNlcnZlIHRoZSBoYXJkd2FyZSBleHBsaWNpdGx5IG5hbWVkIGluIHRoZSB1c2VyIHJlcXVlc3QuJylcclxuICAgICAgICAudG9FcXVhbChleHBlY3QuYXJyYXlDb250YWluaW5nKGV4cGVjdGVkSGFyZHdhcmUpKTtcclxuICAgIH1cclxuICAgIGV4cGVjdChyZXZpZXdlZC5oYXMocHJvcG9zYWxJZCksICdUaGUgc2FtZSBwcm9wb3NhbCBtdXN0IG5vdCByZXF1ZXN0IHJldmlldyB0d2ljZS4nKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IGFwcGx5UmVzcG9uc2UgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5pbmNsdWRlcyhgL3Byb3Bvc2Fscy8ke3Byb3Bvc2FsSWR9L2FwcHJvdmUtYXBwbHlgKSAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJywgeyB0aW1lb3V0OiAxODBfMDAwIH0pO1xyXG4gICAgY29uc3QgYXBwcm92YWwgPSBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6IC9eKEZyZWlnZWJlbiwgw7xiZXJuZWhtZW4gJiBmb3J0ZmFocmVufMOcYmVybmVobWVuICYgZm9ydGZhaHJlbikkLyB9KTtcclxuICAgIGF3YWl0IGV4cGVjdChhcHByb3ZhbCkudG9CZUVuYWJsZWQoeyB0aW1lb3V0OiA2MF8wMDAgfSk7XHJcbiAgICBhd2FpdCBhcHByb3ZhbC5jbGljaygpO1xyXG4gICAgY29uc3QgYXBwbGllZCA9IGF3YWl0IGFwcGx5UmVzcG9uc2U7XHJcbiAgICBpZiAoIWFwcGxpZWQub2soKSkgdGhyb3cgbmV3IEVycm9yKGBIVFRQICR7YXBwbGllZC5zdGF0dXMoKX06ICR7KGF3YWl0IGFwcGxpZWQudGV4dCgpKS5zbGljZSgwLCA0MDAwKX1gKTtcclxuICAgIGV4cGVjdCgoYXdhaXQgYXBwbGllZC5qc29uKCkpLmRhdGEuc3RhdHVzKS50b0JlKCdBUFBMSUVEJyk7XHJcbiAgICByZXZpZXdlZC5hZGQocHJvcG9zYWxJZCk7IHJldmlld0NvdW50Kys7XHJcbiAgICAvLyBBIGRpc3RpbmN0LCBhY3R1YWxseSBjb21taXR0ZWQgbWFudWFsIHJldmlldyBzdGFydHMgdGhlIG5leHQgYXV0b21hdGljXHJcbiAgICAvLyBzZWN0aW9uLiBJdHMgd3JpdGUgc3RpbGwgaGFzIHRoZSBzZXBhcmF0ZSB1bmNoYW5nZWQgMTgwLXNlY29uZCBsaW1pdC5cclxuICAgIHdhdGNoZG9nID0gbmV3IFdpemFyZFByb2dyZXNzV2F0Y2hkb2cocGVyZm9ybWFuY2Uubm93KCksIHdvcmtmbG93KTtcclxuICAgIGlmIChjYW5kaWRhdGUuZGF0YS5wcm9wb3NhbF90eXBlID09PSAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJyAmJiBleHBlY3RlZFNpZ25hbHMpIHtcclxuICAgICAgYXdhaXQgdmVyaWZ5U2lnbmFsQ29udHJhY3RzKHBhZ2UsIHByb2plY3QsIGV4cGVjdGVkU2lnbmFscyk7XHJcbiAgICB9XHJcbiAgICBpZiAocmV2aWV3Q291bnQgPT09IDEgJiYgYWZ0ZXJGaXJzdE1vZGVsQXBwbGllZCkge1xyXG4gICAgICBhd2FpdCBhZnRlckZpcnN0TW9kZWxBcHBsaWVkKCk7XHJcbiAgICAgIC8vIFRoaXMgb25lIHRlc3QgZXhwbGljaXRseSBzdWJtaXRzIEFNRU5EIGFuZCB3YWl0cyBmb3IgaXRzIHJlY2VpcHQuIE9ubHlcclxuICAgICAgLy8gdGhhdCBkZWxpYmVyYXRlIGFjdGlvbiBwZXJtaXRzIGJpbmRpbmcgaXRzIG5ldyByZXF1ZXN0IHJldmlzaW9uLlxyXG4gICAgICBjb25zdCBhbWVuZGVkID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgIGV4cGVjdChhbWVuZGVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQpLnRvQmUocnVuSWQpO1xyXG4gICAgICB3YXRjaGRvZyA9IG5ldyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nKHBlcmZvcm1hbmNlLm5vdygpLCBhbWVuZGVkKTtcclxuICAgIH1cclxuICAgIGlmIChyZXZpZXdDb3VudCA9PT0gMSkgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTsgLy8gRHVyYWJsZSByZWxvYWQgYWZ0ZXIgYSByZWFsIGNvbW1pdC5cclxuICAgIGlmIChyZXN0YXJ0ICYmIHJldmlld0NvdW50ID09PSAyKSB7XHJcbiAgICAgIGF3YWl0IHJlc3RhcnRBcHBsaWNhdGlvbihwYWdlKTtcclxuICAgICAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICAgIH1cclxuICAgIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcclxuICAgICAgY29uc3QgY3VycmVudCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICByZXR1cm4gY3VycmVudC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCAhPT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQ7XHJcbiAgICB9LCB7IHRpbWVvdXQ6IDYwXzAwMCB9KS50b0JlKHRydWUpO1xyXG4gIH1cclxuICB0aHJvdyBuZXcgRXJyb3IoJ1dpemFyZCBleGNlZWRlZCAxNiByZXZpZXcvY29udGludWF0aW9uIGNoZWNrcG9pbnRzLicpO1xyXG59XHJcblxyXG50ZXN0KCd3aXphcmQgcmVmdXNlcyBhbiB1bmF2YWlsYWJsZSBjYXRhbG9nIGFuZCByZWNvdmVycyB1c2luZyB0aGUgcmVhbCByZWdpc3RyeSBAY2F0YWxvZy1yZWNvdmVyeScsIGFzeW5jICh7cGFnZX0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtY2F0YWxvZy1yZWNvdmVyeS0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGF3YWl0IHBhZ2Uucm91dGUoJyoqL2FwaS90ZWNobm9sb2dpZXMnLCByb3V0ZSA9PiByb3V0ZS5mdWxmaWxsKHtzdGF0dXM6NTAzLFxyXG4gICAgY29udGVudFR5cGU6J2FwcGxpY2F0aW9uL2pzb24nLGJvZHk6SlNPTi5zdHJpbmdpZnkoe2Vycm9yOidEZXIgdm9sbHN0w6RuZGlnZSBUZWNobm9sb2dpZWthdGFsb2cgaXN0IGRlcnplaXQgbmljaHQgZXJyZWljaGJhci4nfSl9KSk7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYWxlcnQnKSkudG9Db250YWluVGV4dCgnVGVjaG5vbG9naWVrYXRhbG9nJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywge2V4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjZW5naW5lZXJpbmctcHJvamVjdC1uYW1lJykuZmlsbCgnQ2F0YWxvZyByZXRyeScpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdQcm9qZWt0YmVzY2hyZWlidW5nJywge2V4YWN0OnRydWV9KS5maWxsKCdlaW4gQWt0b3IgenVtIHByb3BvcnRpb25hbCBzY2hsaWXDn2VuIGVpbmVzIFZlbnRpbCcpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cubG9jYXRvcignLmVuZy1hZ2VudC1xdWVzdGlvbm5haXJlLWhlYWQnKS5nZXRCeVJvbGUoJ2J1dHRvbicpKS50b0JlRGlzYWJsZWQoKTtcclxuICBleHBlY3QoKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnMpLnRvSGF2ZUxlbmd0aCgwKTtcclxuICBhd2FpdCBwYWdlLnVucm91dGUoJyoqL2FwaS90ZWNobm9sb2dpZXMnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidUZWNobm9sb2dpZWthdGFsb2cgZXJuZXV0IGxhZGVuJ30pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2FsZXJ0JykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cubG9jYXRvcignLmVuZy1hZ2VudC1xdWVzdGlvbm5haXJlLWhlYWQnKS5nZXRCeVJvbGUoJ2J1dHRvbicpKS50b0JlRW5hYmxlZCgpO1xyXG4gIGNvbnN0IGNhdGFsb2cgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS90ZWNobm9sb2dpZXMnKSkuanNvbigpO1xyXG4gIGV4cGVjdChjYXRhbG9nLnRlY2hub2xvZ3lfY291bnQpLnRvQmUoMTI1KTtcclxufSk7XHJcblxyXG50ZXN0KCduZXcgc21hbGwgd2l6YXJkIHRyYXZlcnNlcyBhbGwgbmluZSBzdGFnZXMgYW5kIHN1cnZpdmVzIHJlbG9hZC9yZXN0YXJ0IEBzbWFsbCcsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICBjb25zdCBlcnJvcnM6IHN0cmluZ1tdID0gW107IHBhZ2Uub24oJ3BhZ2VlcnJvcicsIGVycm9yID0+IGVycm9ycy5wdXNoKGVycm9yLm1lc3NhZ2UpKTtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtc21hbGwtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdQcm9qZWt0bmFtZScsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cubG9jYXRvcignI2VuZ2luZWVyaW5nLXByb2plY3QtbmFtZScpLmZpbGwoJ0UyRSBzbWFsbCcpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdQcm9qZWt0YmVzY2hyZWlidW5nJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKCdFcnpldWdlIGVpbiBBdXRvbW90aXZlIENBTi1GRCBOZXR6d2VyayBtaXQgZWluZW0gR2F0ZXdheSBTeXN0ZW0sIGRlbiBFQ1VzIE1vdG9yc3RldWVydW5nIHVuZCBBbnplaWdlLCBlaW5lbSBTZW5zb3IgTW90b3JUZW1wZXJhdHVyZSB1bmQgZWluZW0gQWt0b3IgTW90b3JWYWx2ZS4gTW90b3JUZW1wZXJhdHVyZSB3aXJkIHZvbiBNb3RvcnN0ZXVlcnVuZyBhdXNnZXdlcnRldC4gTW90b3JzdGV1ZXJ1bmcgc3RldWVydCBNb3RvclZhbHZlLiBDb250cm9sbGVyc3RhdHVzIGJsZWlidCBiaXMgenVyIEF1c3dhaGwga29ua3JldGVyIEVtcGbDpG5nZXIgdW5kIFNpZ25hbGUgaW50ZXJuLiBQcsO8ZmUgdW5kIGFyYmVpdGUgYmlzIERhdGEgU2NpZW5jZSAmIEludGVsbGlnZW5jZS5cXG5DQU4tRkQ6IDUwMCBrYml0L3MgYXJiaXRyYXRpb24sIDIgTWJpdC9zIGRhdGFcXG5DQU46IDUwMCBrYml0L3MnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnV2VpdGVyZSBIaW53ZWlzZScsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCgnLSBBa3Rvci1CZWZlaGxlOiB7XCJNb3RvclZhbHZlXCI6e1wibGVuZ3RoX2JpdHNcIjoxLFwiZGF0YV90eXBlXCI6XCJib29sZWFuXCIsXCJmYWN0b3JcIjoxLFwidW5pdFwiOlwiY29kZVwiLFwibWluX3ZhbHVlXCI6MCxcIm1heF92YWx1ZVwiOjEsXCJzZW1hbnRpY1wiOntcInNlbWFudGljX3R5cGVcIjpcIkJPT0xFQU5cIn0sXCJkYXRhXCI6e1wiZW51bV92YWx1ZXNcIjp7XCJDTE9TRVwiOjAsXCJPUEVOXCI6MX19fX0nKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnR2Vyw6R0ZXVtZmFuZycsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBmb3IgKGNvbnN0IFtsYWJlbCwgdmFsdWVdIG9mIFtbJ0dhdGV3YXlzJywgJzEnXSwgWydDb250cm9sbGVyJywgJzInXSwgWydTZW5zb3JlbicsICcxJ10sIFsnQWt0b3JlbicsICcxJ11dKSBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbChgJHtsYWJlbH06IHZlcmJpbmRsaWNoZSBBbnphaGxgLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwodmFsdWUpO1xyXG4gIGNvbnN0IHN0YXJ0UmVxdWVzdCA9IHBhZ2Uud2FpdEZvclJlcXVlc3QocmVxdWVzdCA9PiByZXF1ZXN0LnVybCgpLmVuZHNXaXRoKCcvYXBpL2FnZW50L2NoYXQnKVxyXG4gICAgJiYgcmVxdWVzdC5tZXRob2QoKSA9PT0gJ1BPU1QnICYmIHJlcXVlc3QucG9zdERhdGFKU09OKCk/LndpemFyZF9jb21tYW5kPy5hY3Rpb24gPT09ICdTVEFSVCcpO1xyXG4gIC8vIFVzZSB0aGUgc2FtZSB2aXNpYmxlIHF1ZXN0aW9ubmFpcmUgbmF2aWdhdGlvbiBhIHVzZXIgdXNlczsgbmV2ZXIgaW5qZWN0IGdlbmVyYXRlZCBtb2RlbCByb3dzLlxyXG4gIGZvciAobGV0IHN0ZXAgPSAwOyBzdGVwIDwgMTA7IHN0ZXArKykge1xyXG4gICAgY29uc3Qgc3VibWl0ID0gZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKTtcclxuICAgIGF3YWl0IGV4cGVjdChzdWJtaXQpLnRvQmVFbmFibGVkKCk7XHJcbiAgICBjb25zdCBuYW1lID0gYXdhaXQgc3VibWl0LmlubmVyVGV4dCgpO1xyXG4gICAgYXdhaXQgc3VibWl0LmNsaWNrKCk7XHJcbiAgICBpZiAobmFtZSA9PT0gJ8OcYmVybmVobWVuJykgYnJlYWs7XHJcbiAgICBpZiAoc3RlcCA9PT0gOSkgdGhyb3cgbmV3IEVycm9yKCdRdWVzdGlvbm5haXJlIGRpZCBub3Qgb2ZmZXIgc3VibWl0LicpO1xyXG4gIH1cclxuICBjb25zdCByZXF1ZXN0ZWQgPSAoYXdhaXQgc3RhcnRSZXF1ZXN0KS5wb3N0RGF0YUpTT04oKS53aXphcmRfY29tbWFuZC53aXphcmRfY29udGV4dDtcclxuICBleHBlY3QocmVxdWVzdGVkLnRlY2hub2xvZ2llcywgJ0FuIGV4cGxpY2l0IENBTi1GRCB0YXNrIG11c3Qgbm90IHNpbGVudGx5IHJlcXVlc3QgTElOIGFuZCBTT01FL0lQLicpLnRvRXF1YWwoWydDQU4tRkQgKGNhbl9mZCknXSk7XHJcbiAgLy8gUHJlc2VydmUgYSByZWFsIHBlbmRpbmcgbW9kZWwgdGhyb3VnaCBwYXJhbWV0ZXIgc2F2ZSBhbmQgcmVuZXdlZCByZXZpZXcuXHJcbiAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UscHJvamVjdCwnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKSkuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnN0YXRlLFxyXG4gICAge3RpbWVvdXQ6MTgwMDAwfSkudG9CZSgnUkVWSUVXX1JFUVVJUkVEJyk7XHJcbiAgY29uc3QgcGVuZGluZyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLHByb2plY3QsJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJykpLmRhdGEuYWN0aXZlX3Byb3Bvc2FsO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke3Byb2plY3R9JnRlY2hub2xvZ3k9Y2FuX2ZkJnByb3Bvc2FsPSR7cGVuZGluZ30jcGFyYW1ldGVyLWZpbmRpbmdzYCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLHtuYW1lOidBa3R1ZWxsZSBQYXJhbWV0ZXJiZWZ1bmRlJ30pKS50b0NvbnRhaW5UZXh0KCdub2NoIG5pY2h0IMO8YmVybm9tbWVuZW4gVm9yc2NobGFncycpO1xyXG4gIGNvbnN0IGNvbW1vbiA9IHBhZ2UubG9jYXRvcignLnBhcmFtZXRlci1ncm91cC1jb21tb24nKTtcclxuICBhd2FpdCBleHBlY3QoY29tbW9uLmxvY2F0b3IoJyNhcmJpdHJhdGlvbl9iaXRyYXRlJykpLnRvSGF2ZVZhbHVlKCc1MDAwMDAnKTtcclxuICBhd2FpdCBleHBlY3QoY29tbW9uLmxvY2F0b3IoJyNkYXRhX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzIwMDAwMDAnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcucGFyYW1ldGVyLWRldGFpbHNbb3Blbl0nKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgYXdhaXQgY29tbW9uLmxvY2F0b3IoJyNzZWVkJykuZmlsbCgnNDInKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonUGFyYW1ldGVyIHNwZWljaGVybiDihpInLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnVGVjaG5vbG9naWUtIHVuZCBUaW1pbmctUGFyYW1ldGVyIGdlc3BlaWNoZXJ0LicpKS50b0JlVmlzaWJsZSgpO1xyXG4gIGNvbnN0IHN0YWxlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSxwcm9qZWN0LGAvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb3Bvc2Fscy8ke3BlbmRpbmd9P3ZpZXc9c3RhdHVzYCk7XHJcbiAgZXhwZWN0KHN0YWxlLmRhdGEuc3RhdHVzKS50b0JlKCdPVVREQVRFRCcpO1xyXG4gIGV4cGVjdChzdGFsZS5kYXRhLmNhbm9uaWNhbF9pZHMpLnRvRXF1YWwoW10pO1xyXG4gIGV4cGVjdCgoYXdhaXQgYWxsT2JqZWN0cyhwYWdlLHByb2plY3QsJ2hhcmR3YXJlLW5vZGVzJykpKS50b0hhdmVMZW5ndGgoMCk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjc2VlZCcpKS50b0hhdmVWYWx1ZSgnNDInKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnbGluaycse25hbWU6J1p1ciBWb3JzY2hsYWdzcHLDvGZ1bmcgenVyw7xjayDihpInLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cpLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3QgcmV2aWV3ID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJyx7bmFtZTonRW5naW5lZXJpbmctVm9yc2NobGFnJ30pO1xyXG4gIGF3YWl0IGV4cGVjdChyZXZpZXcpLnRvQ29udGFpblRleHQoJ01vZGVsbHN0YW5kIGdlw6RuZGVydCcpO1xyXG4gIGF3YWl0IGV4cGVjdChyZXZpZXcuZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidGcmVpZ2ViZW4sIMO8YmVybmVobWVuICYgZm9ydGZhaHJlbicsZXhhY3Q6dHJ1ZX0pKS50b0hhdmVDb3VudCgwKTtcclxuICBhd2FpdCByZXZpZXcuZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidFcm5ldXQgcHLDvGZlbicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHJldmlldykudG9Db250YWluVGV4dCgnR2VwcsO8ZnQgwrcgRnJlaWdhYmUgb2ZmZW4nKTtcclxuICBjb25zdCBjb250aW51aXR5ID0gYXdhaXQgY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIHRydWUsXHJcbiAgICBbJ1N5c3RlbScsICdNb3RvcnN0ZXVlcnVuZycsICdBbnplaWdlJywgJ01vdG9yVGVtcGVyYXR1cmUnLCAnTW90b3JWYWx2ZSddKTtcclxuICBjb25zdCBhcnRpZmFjdHMgPSBhd2FpdCB2ZXJpZnlBcnRpZmFjdHMocGFnZSwgcHJvamVjdCwgNSk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50Lm9ic2VydmVkX3NpZ25hbF9jb3VudCkudG9CZUdyZWF0ZXJUaGFuT3JFcXVhbCgzKTtcclxuICBleHBlY3QoYXJ0aWZhY3RzLmFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UudHJhbnNwb3J0X2V4Y2x1c2lvbnMpLnRvSGF2ZUxlbmd0aCgzKTtcclxuICBjb25zdCBmaW5pc2hlZCA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IHJlc3BvbnNlLnVybCgpLmluY2x1ZGVzKGAvcnVucy8ke2NvbnRpbnVpdHkucnVuSWR9L2ZpbmlzaGApXHJcbiAgICAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRmVydGlnIHN0ZWxsZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGV4cGVjdCgoYXdhaXQgZmluaXNoZWQpLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZykubm90LnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBleHBlY3QoKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnMpLnRvSGF2ZUxlbmd0aCgxKTtcclxuICBleHBlY3QoZXJyb3JzKS50b0VxdWFsKFtdKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2V2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIC4uLmNvbnRpbnVpdHksIC4uLmFydGlmYWN0cyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxufSk7XHJcblxyXG5mb3IgKGNvbnN0IHRlY2hub2xvZ3kgb2YgWydJMkMnLCAnTW9kYnVzIFJUVSddKSB7XHJcbiAgdGVzdChgUmFzcGJlcnJ5IFBpICR7dGVjaG5vbG9neX0gcHJvamVjdCByZXRhaW5zIG1vZGVsIGFuZCByZXF1ZXN0cyBtaXNzaW5nIGNhcGFjaXR5IGV2aWRlbmNlIEBub25hdXRvbW90aXZlYCwgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gICAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWVtYmVkZGVkLScgKyByYW5kb21VVUlEKCk7XHJcbiAgICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdUZW1wZXJhdHVycmVnZWx1bmcnKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdQcm9qZWt0YmVzY2hyZWlidW5nJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHRlY2hub2xvZ3kgPT09ICdJMkMnXHJcbiAgICAgID8gJzIgQWt0b3JlbiBmw7xyIFZlbnRpbGUsIDQgU2Vuc29yZW4gZsO8ciBUZW1wZXJhdHVyZW4sIHVuZCBlaW4gUmFzcGJlcnJ5UGknXHJcbiAgICAgIDogYDIgQWt0b3JlbiBmw7xyIFZlbnRpbGUsIDQgU2Vuc29yZW4gZsO8ciBUZW1wZXJhdHVyZW4sIHVuZCBlaW4gUmFzcGJlcnJ5UGkuIEVtYmVkZGVkIFN5c3RlbXMuIEFsbGUgR2Vyw6R0ZSBrb21tdW5pemllcmVuIMO8YmVyICR7dGVjaG5vbG9neX0uIFByw7xmZSB1bmQgYXJiZWl0ZSBiaXMgRGF0YSBTY2llbmNlICYgSW50ZWxsaWdlbmNlLmApO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ05ldHphcmNoaXRla3R1cicsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ3JhZGlvJywgeyBuYW1lOiAvVmFyaWFudGUgMC8gfSkuY2hlY2soKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdHZXLDpHRldW1mYW5nJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1Jhc3BiZXJyeVBpOiBBbnNjaGx1c3MnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignSTJDJyk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlMYWJlbCgnVGVtcGVyYXR1cnNlbnNvcjE6IEFuc2NobHVzcycsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZVZhbHVlKCcnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgICBmb3IgKGNvbnN0IG5hbWUgb2YgWydSYXNwYmVycnlQaScsICdUZW1wZXJhdHVyc2Vuc29yMScsICdUZW1wZXJhdHVyc2Vuc29yMicsICdUZW1wZXJhdHVyc2Vuc29yMycsICdUZW1wZXJhdHVyc2Vuc29yNCcsICdWZW50aWxha3RvcjEnLCAnVmVudGlsYWt0b3IyJ10pIHtcclxuICAgICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbChgJHtuYW1lfTogQW5zY2hsdXNzYCwgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ0kyQycpO1xyXG4gICAgICB9XHJcbiAgICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdTZW5zb3IgMTogTWVzc2dyw7bDn2UnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignc3BlZWQnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeUxhYmVsKCdUZW1wZXJhdHVyc2Vuc29yMTogQW5zY2hsdXNzJywgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoJ0kyQycpO1xyXG4gICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnU2Vuc29yIDE6IE1lc3NncsO2w59lJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ3RlbXBlcmF0dXJlJyk7XHJcbiAgICB9XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnVmVudGlsYWt0b3IxOiBTdGVsbGJlZmVobCcsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdPUEVOX0NMT1NFJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMjogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnVmVudGlsYWt0b3IyOiBTdGVsbGJlZmVobCcsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdPUEVOX0NMT1NFJyk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBleHBlY3QoY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIHRydWUsIFsnUmFzcGJlcnJ5UGknLCAnVGVtcGVyYXR1cnNlbnNvcjEnLCAnVGVtcGVyYXR1cnNlbnNvcjInLCAnVGVtcGVyYXR1cnNlbnNvcjMnLCAnVGVtcGVyYXR1cnNlbnNvcjQnLCAnVmVudGlsYWt0b3IxJywgJ1ZlbnRpbGFrdG9yMiddLCBmYWxzZSwgdW5kZWZpbmVkLCB1bmRlZmluZWQsIHRydWUpKVxyXG4gICAgICAucmVqZWN0cy50b1Rocm93KC9XaXphcmQgQkxPQ0tFRCBhdCBwYXJhbWV0ZXJzOi4qYmVzdMOkdGlndGUgQW5nYWJlbi8pO1xyXG4gICAgY29uc3Qgd29ya2Zsb3cgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpO1xyXG4gICAgY29uc3QgZmluZGluZ3MgPSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbi5ibG9ja2luZ19maW5kaW5ncyBhcyB7IGNvZGU6IHN0cmluZyB9W107XHJcbiAgICBleHBlY3QoZmluZGluZ3MubWFwKGl0ZW0gPT4gaXRlbS5jb2RlKSkudG9Db250YWluKCdURUNITk9MT0dZX1BBUkFNRVRFUl9NSVNTSU5HJyk7XHJcbiAgICBleHBlY3Qod29ya2Zsb3cuc3RhdHVzZXMucGFyYW1ldGVycykudG9CZSgnSU5fUFJPR1JFU1MnKTtcclxuICAgIGV4cGVjdCh3b3JrZmxvdy5hcnRpZmFjdF9jaGVja3MucGFyYW1ldGVycy5jb21wbGV0ZSkudG9CZShmYWxzZSk7XHJcbiAgICBjb25zdCByZXF1aXJlZCA9IHdvcmtmbG93LmFydGlmYWN0X2NoZWNrcy5wYXJhbWV0ZXJzLnJlcXVpcmVkO1xyXG4gICAgZXhwZWN0KHJlcXVpcmVkW3RlY2hub2xvZ3kgPT09ICdJMkMnID8gJ2kyY19kZXZpY2Vfc291cmNlJyA6ICdtcl9kZXZpY2Vfc291cmNlJ10pLnRvQmUoZmFsc2UpO1xyXG4gICAgY29uc3QgZXZpZGVuY2VSZXZpZXcgPSBkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7bmFtZTogJ0Jsb2NraWVyZW5kZSBQcmVmbGlnaHQtQmVmdW5kZSd9KTtcclxuICAgIGF3YWl0IGV4cGVjdChldmlkZW5jZVJldmlldykudG9Db250YWluVGV4dCh0ZWNobm9sb2d5ID09PSAnSTJDJyA/ICdpMmNfZGV2aWNlX3NvdXJjZScgOiAnbXJfZGV2aWNlX3NvdXJjZScpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGV2aWRlbmNlUmV2aWV3LmdldEJ5Um9sZSgnbGluaycsIHtuYW1lOiAnQmV0cm9mZmVuZSBBbmdhYmVuIGJlYXJiZWl0ZW4nfSkuZmlyc3QoKSlcclxuICAgICAgLnRvSGF2ZUF0dHJpYnV0ZSgnaHJlZicsIG5ldyBSZWdFeHAoYG1vZGU9cGFyYW1ldGVycy4qcHJvamVjdD0ke3Byb2plY3R9YCkpO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LnN0YXR1c2VzLnNpbXVsYXRpb24pLnRvQmUoJ0VNUFRZJyk7XHJcbiAgICBpZiAodGVjaG5vbG9neSA9PT0gJ0kyQycpIHtcclxuICAgICAgZXhwZWN0KHdvcmtmbG93LnBhcmFtZXRlcnMucmF0ZV9yZXZpZXdfcHJvcG9zYWxzLmkyYy5zdGF0dXMpLnRvQmUoJ1JFVklFV19SRVFVSVJFRCcpO1xyXG4gICAgICBleHBlY3Qod29ya2Zsb3cucGFyYW1ldGVycy5wYXJhbWV0ZXJfcHJvdmVuYW5jZS5iaXRyYXRlLnNvdXJjZSkudG9CZSgnVEVDSE5PTE9HWV9QUk9GSUxFX1JFVklFV19QUk9QT1NBTCcpO1xyXG4gICAgfVxyXG4gICAgY29uc3QgaW50ZXJmYWNlcyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLWludGVyZmFjZXMnKTtcclxuICAgIGV4cGVjdChpbnRlcmZhY2VzLmxlbmd0aCkudG9CZUdyZWF0ZXJUaGFuT3JFcXVhbCg3KTtcclxuICAgIGV4cGVjdChpbnRlcmZhY2VzLmV2ZXJ5KGl0ZW0gPT4gIS9hdXRvbW90aXZlfGNhbnxsaW4vaS50ZXN0KGl0ZW0udGVjaG5vbG9neSkpKS50b0JlKHRydWUpO1xyXG4gICAgY29uc3QgaGFyZHdhcmUgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gICAgZXhwZWN0KGhhcmR3YXJlLmV2ZXJ5KGl0ZW0gPT4gaXRlbS5kb21haW4gIT09ICdhdXRvbW90aXZlJykpLnRvQmUodHJ1ZSk7XHJcbiAgICBpZiAodGVjaG5vbG9neSA9PT0gJ0kyQycpIHtcclxuICAgICAgY29uc3Qgc2lnbmFscyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ3NpZ25hbHMnKTtcclxuICAgICAgZXhwZWN0KHNpZ25hbHMuc29tZShpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ1RlbXBlcmF0dXJfVGVtcGVyYXR1cnNlbnNvcjEnICYmIGl0ZW0udW5pdCA9PT0gJ2RlZ0MnKSkudG9CZSh0cnVlKTtcclxuICAgIH1cclxuICAgIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icykudG9IYXZlTGVuZ3RoKDApO1xyXG4gICAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdub25hdXRvbW90aXZlLWV2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIHRlY2hub2xvZ3ksIGZpbmRpbmdzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gIH0pO1xyXG59XHJcblxyXG50ZXN0KCdleGFjdCBjb25maXJtZWQgNTAvMjUwLzI1MCByZXF1ZXN0IGNvbXBsZXRlcyB0aHJvdWdoIHJlYWwgd2l6YXJkIHJldmlldyBAbGFyZ2UnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgZXJyb3JzOiBzdHJpbmdbXSA9IFtdOyBwYWdlLm9uKCdwYWdlZXJyb3InLCBlcnJvciA9PiBlcnJvcnMucHVzaChlcnJvci5tZXNzYWdlKSk7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWxhcmdlLScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgcnVuSWQgPSByYW5kb21VVUlEKCk7XHJcbiAgY29uc3Qgb3JpZ2luYWwgPSBhd2FpdCByZWFkRmlsZShuZXcgVVJMKCcuL2ZpeHR1cmVzL3dpemFyZC1sYXJnZS01MC0yNTAtMjUwLnR4dCcsIGltcG9ydC5tZXRhLnVybCksICd1dGY4Jyk7XHJcbiAgY29uc3QgbWV0YWRhdGEgPSBKU09OLnBhcnNlKGF3YWl0IHJlYWRGaWxlKG5ldyBVUkwoJy4vZml4dHVyZXMvd2l6YXJkLWxhcmdlLTUwLTI1MC0yNTAuanNvbicsIGltcG9ydC5tZXRhLnVybCksICd1dGY4JykpO1xyXG4gIGNvbnN0IGJhc2VsaW5lID0gSlNPTi5wYXJzZShhd2FpdCByZWFkRmlsZShuZXcgVVJMKCcuL2ZpeHR1cmVzL3dpemFyZC1sYXJnZS1zaWduYWwtY29udHJhY3RzLmpzb24nLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpKTtcclxuICBjb25zdCBwcm9tcHQgPSBvcmlnaW5hbC5yZXBsYWNlKC9eLSBMYXVmLUlEOi4qJC9tLCAnLSBMYXVmLUlEOiAnICsgcnVuSWQpO1xyXG4gIGF3YWl0IHJldmlld1ZpcnR1YWxUcmFuc3BvcnRzKHBhZ2UsIHByb2plY3QpO1xyXG4gIC8vIFJlcGxheSB0aGUgY2FwdHVyZWQsIGFscmVhZHkgY29uZmlybWVkIGlucHV0IHRocm91Z2ggdGhlIG5vcm1hbCBTVEFSVCBBUEkuXHJcbiAgLy8gQWxsIHByb3Bvc2FsIGluc3BlY3Rpb24sIGFwcHJvdmFsLCBjb250aW51YXRpb24gYW5kIHJlbG9hZHMgYmVsb3cgdXNlIFVJLlxyXG4gIGNvbnN0IHN0YXJ0ZWQgPSBhd2FpdCBwYWdlLnJlcXVlc3QucG9zdCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jaGF0Jywge1xyXG4gICAgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiAyNDBfMDAwLFxyXG4gICAgZGF0YTogeyBwcm9tcHQsIHdpemFyZF9jb21tYW5kOiB7IGFjdGlvbjogJ1NUQVJUJywgcnVuX2lkOiBydW5JZCwgb3BlcmF0aW9uX2lkOiByYW5kb21VVUlEKCksXHJcbiAgICAgIHRhcmdldDogJ2RhdGFfc2NpZW5jZV9pbnRlbGxpZ2VuY2UnLCB3aXphcmRfY29udGV4dDogeyAuLi5tZXRhZGF0YS53aXphcmRfY29udGV4dCwgcHJvamVjdF9pZDogcHJvamVjdCwgcnVuX2lkOiBydW5JZCB9IH0gfSxcclxuICB9KTtcclxuICBpZiAoIXN0YXJ0ZWQub2soKSkgdGhyb3cgbmV3IEVycm9yKGBIVFRQICR7c3RhcnRlZC5zdGF0dXMoKX06ICR7KGF3YWl0IHN0YXJ0ZWQudGV4dCgpKS5zbGljZSgwLCA0MDAwKX1gKTtcclxuICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgZmFsc2UsIFtdLCB0cnVlLCBiYXNlbGluZS5zaWduYWxzKTtcclxuICBleHBlY3QoY29udGludWl0eS5ydW5JZCkudG9CZShydW5JZCk7XHJcbiAgY29uc3QgaGFyZHdhcmUgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gIGV4cGVjdChoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLmRldmljZV90eXBlID09PSAnU2Vuc29yQ29udHJvbGxlcicpKS50b0hhdmVMZW5ndGgoMjUwKTtcclxuICBleHBlY3QoaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5kZXZpY2VfdHlwZSA9PT0gJ0FjdHVhdG9yQ29udHJvbGxlcicpKS50b0hhdmVMZW5ndGgoMjUwKTtcclxuICBleHBlY3QoaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5kZXZpY2VfdHlwZSA9PT0gJ0VDVScpLmxlbmd0aCkudG9CZUdyZWF0ZXJUaGFuT3JFcXVhbCg1MCk7XHJcbiAgY29uc3QgYXJ0aWZhY3RzID0gYXdhaXQgdmVyaWZ5QXJ0aWZhY3RzKHBhZ2UsIHByb2plY3QsIDE0MDQpO1xyXG4gIGNvbnN0IGV4Y2x1ZGVkU2lnbmFsSWRzID0gbmV3IFNldChhcnRpZmFjdHMuYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS50cmFuc3BvcnRfZXhjbHVzaW9uc1xyXG4gICAgLmZsYXRNYXAoKGl0ZW06IHsgc2lnbmFsX2lkczogc3RyaW5nW10gfSkgPT4gaXRlbS5zaWduYWxfaWRzKSk7XHJcbiAgZXhwZWN0KGV4Y2x1ZGVkU2lnbmFsSWRzLnNpemUpLnRvQmUoMjM1KTtcclxuICBleHBlY3QoYXJ0aWZhY3RzLmFzc2Vzc21lbnQub2JzZXJ2ZWRfc2lnbmFsX2NvdW50KS50b0JlKDExNjkpO1xyXG4gIGF3YWl0IHZlcmlmeVNpZ25hbENvbnRyYWN0cyhwYWdlLCBwcm9qZWN0LCBiYXNlbGluZS5zaWduYWxzKTtcclxuICBleHBlY3QoYXJ0aWZhY3RzLmpvYikudG9CZShjb250aW51aXR5LnJlc3RhcnRlZEpvYklkKTtcclxuICBleHBlY3QoZXJyb3JzKS50b0VxdWFsKFtdKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2V2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIGZpeHR1cmU6IG1ldGFkYXRhLnJlcXVlc3Rfc2hhMjU2LCAuLi5jb250aW51aXR5LCAuLi5hcnRpZmFjdHMgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG5cclxudGVzdCgnYSByZWFsIEFNRU5EIGFmdGVyIG1vZGVsIGFwcHJvdmFsIGFkZHMgdGhlIHJlcXVlc3RlZCBzZW5zb3IgYW5kIHJldXNlcyBpdHMgbmV0d29ya3MgQGFtZW5kJywgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1hbWVuZC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGF3YWl0IHJldmlld1ZpcnR1YWxUcmFuc3BvcnRzKHBhZ2UsIHByb2plY3QpO1xyXG4gIGNvbnN0IHJ1bklkID0gcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGdyYXBoID0gW1xyXG4gICAgeyBjbHVzdGVyX2lkOiAnZHJpdmUnLCBuZXR3b3JrX2lkOiAnY2FuX2ZkJywgbmV0d29ya19sYWJlbDogJ0NBTi1GRCcsIGJ1c19uYW1lOiAnRHJpdmUnLFxyXG4gICAgICBjb250cm9sbGVyczogW3sgZWN1OiAnTW90b3JzdGV1ZXJ1bmcnLCBzZW5zb3JzOiBbXSBhcyBzdHJpbmdbXSwgYWN0dWF0b3JzOiBbXSB9XSxcclxuICAgICAgaG1pX3JvdXRlczogW3sgc291cmNlOiAnTW90b3JzdGV1ZXJ1bmcnLCB0YXJnZXQ6ICdBbnplaWdlJyB9LCB7IHNvdXJjZTogJ0FuemVpZ2UnLCB0YXJnZXQ6ICdNb3RvcnN0ZXVlcnVuZycgfSxcclxuICAgICAgICB7IHNvdXJjZTogJ1N5c3RlbScsIHRhcmdldDogJ0FuemVpZ2UnIH1dIH0sXHJcbiAgICB7IGNsdXN0ZXJfaWQ6ICdkaXNwbGF5JywgbmV0d29ya19pZDogJ2V0aGVybmV0JywgbmV0d29ya19sYWJlbDogJ0V0aGVybmV0JywgYnVzX25hbWU6ICdEaXNwbGF5JyxcclxuICAgICAgY29udHJvbGxlcnM6IFt7IGVjdTogJ0FuemVpZ2UnLCBzZW5zb3JzOiBbXSBhcyBzdHJpbmdbXSwgYWN0dWF0b3JzOiBbXSB9XSB9LFxyXG4gIF07XHJcbiAgY29uc3QgcHJvbXB0ID0gYFN0cnVrdHVyaWVydGUgVm9yZ2FiZW4gZnVlciBkZW4gRW5naW5lZXJpbmctQWdlbnRlbjpcclxuLSBMYXVmLUlEOiAke3J1bklkfVxyXG4tIEluZHVzdHJpZTogQXV0b21vdGl2ZVxyXG4tIE5ldHp3ZXJrdGVjaG5vbG9naWVuOiBDQU4tRkQgKGNhbl9mZCk7IEV0aGVybmV0IChldGhlcm5ldClcclxuQ0FOLUZEOiA1MDAga2JpdC9zIGFyYml0cmF0aW9uLCAyIE1iaXQvcyBkYXRhXHJcbkNBTjogNTAwIGtiaXQvc1xyXG5FdGhlcm5ldDogMTAwIE1iaXQvc1xyXG4tIEhhcmR3YXJlLVNvbGx3ZXJ0ZToge1wiZ2F0ZXdheXNcIjoxLFwiZWN1c1wiOjIsXCJzZW5zb3JzXCI6MCxcImFjdHVhdG9yc1wiOjB9XHJcbi0gU3lzdGVtY2x1c3Rlci1HcmFwaDogJHtKU09OLnN0cmluZ2lmeShncmFwaCl9XHJcbktvbmtyZXRlIEF1ZmdhYmUgZGVzIE51dHplcnMsIHBlciBXaXphcmQtVWViZXJuZWhtZW4gYmVzdGFldGlndDpcclxuTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UgbWl0IGVpbmVtIHplbnRyYWxlbiBHYXRld2F5IFN5c3RlbSB2ZXJiaW5kZW4uYDtcclxuICBjb25zdCBzdGFydGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY2hhdCcsIHtcclxuICAgIGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSwgdGltZW91dDogMTIwXzAwMCxcclxuICAgIGRhdGE6IHsgcHJvbXB0LCB3aXphcmRfY29tbWFuZDogeyBhY3Rpb246ICdTVEFSVCcsIHJ1bl9pZDogcnVuSWQsIG9wZXJhdGlvbl9pZDogcmFuZG9tVVVJRCgpLFxyXG4gICAgICB0YXJnZXQ6ICdkYXRhX3NjaWVuY2VfaW50ZWxsaWdlbmNlJywgd2l6YXJkX2NvbnRleHQ6IHsgcHJvamVjdF9pZDogcHJvamVjdCwgcnVuX2lkOiBydW5JZCxcclxuICAgICAgICBwcm9qZWN0X25hbWU6ICdFMkUgYW1lbmRtZW50Jywgc2NvcGVfaWRzOiBzdGVwcywgbW9kZTogJ2Z1bGwnLFxyXG4gICAgICAgIHByb2Nlc3NfaWRzOiBbJ2RlZmF1bHRzJywgJ3Jldmlld19nYXRlJywgJ2FwcHJvdmVfYWZ0ZXJfYWxsb3cnXSwgdGFzazogJ01vdG9yc3RldWVydW5nIHVuZCBBbnplaWdlIGFuIFN5c3RlbScgfSB9IH0sXHJcbiAgfSk7XHJcbiAgaWYgKCFzdGFydGVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke3N0YXJ0ZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBzdGFydGVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBsZXQgb3JpZ2luYWxOZXR3b3Jrczogc3RyaW5nW10gPSBbXTtcclxuICBjb25zdCBhbWVuZCA9IGFzeW5jICgpID0+IHtcclxuICAgIG9yaWdpbmFsTmV0d29ya3MgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cnKSkucGFyYW1ldGVycy5uZXR3b3Jrc1xyXG4gICAgICAubWFwKChpdGVtOiB7IGlkOiBzdHJpbmcgfSkgPT4gaXRlbS5pZCkuc29ydCgpO1xyXG4gICAgZXhwZWN0KG9yaWdpbmFsTmV0d29ya3MpLnRvSGF2ZUxlbmd0aCgyKTtcclxuICAgIGdyYXBoWzBdLmNvbnRyb2xsZXJzWzBdLnNlbnNvcnMucHVzaCgnTW90b3JUZW1wZXJhdHVyZScpO1xyXG4gICAgY29uc3QgZGlhbG9nID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KTtcclxuICAgIGNvbnN0IGV4cGFuZCA9IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8OkbnplbicsIGV4YWN0OiB0cnVlIH0pO1xyXG4gICAgYXdhaXQgZXhwZWN0KGV4cGFuZCkudG9CZUVuYWJsZWQoeyB0aW1lb3V0OiAxMjBfMDAwIH0pO1xyXG4gICAgYXdhaXQgZXhwYW5kLmNsaWNrKCk7XHJcbiAgICBjb25zdCBmaWVsZCA9IGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSkuZ2V0QnlSb2xlKCd0ZXh0Ym94Jyk7XHJcbiAgICBhd2FpdCBmaWVsZC5maWxsKCdFcmfDpG56ZSBNb3RvclRlbXBlcmF0dXJlIGFscyBTZW5zb3IgZGVyIE1vdG9yc3RldWVydW5nLiBEaWUgdm9sbHN0w6RuZGlnZSBha3R1YWxpc2llcnRlIEZyZWlnYWJlIGxhdXRldDpcXG4nXHJcbiAgICAgICsgJy0gSGFyZHdhcmUtU29sbHdlcnRlOiB7XCJnYXRld2F5c1wiOjEsXCJlY3VzXCI6MixcInNlbnNvcnNcIjoxLFwiYWN0dWF0b3JzXCI6MH1cXG4nXHJcbiAgICAgICsgJy0gU3lzdGVtY2x1c3Rlci1HcmFwaDogJyArIEpTT04uc3RyaW5naWZ5KGdyYXBoKSk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdFcmfDpG56dW5nIGFuYWx5c2llcmVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGV4cGVjdChmaWVsZCkubm90LnRvQmVWaXNpYmxlKHsgdGltZW91dDogMTIwXzAwMCB9KTtcclxuICB9O1xyXG4gIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgZmFsc2UsIFsnTW90b3JzdGV1ZXJ1bmcnLCAnQW56ZWlnZSddLCBmYWxzZSwgdW5kZWZpbmVkLCBhbWVuZCk7XHJcbiAgY29uc3QgaGFyZHdhcmUgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gIGNvbnN0IG93bmVyID0gaGFyZHdhcmUuZmluZChpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ01vdG9yc3RldWVydW5nJyk7XHJcbiAgY29uc3Qgc2Vuc29ycyA9IGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0ubmFtZSA9PT0gJ01vdG9yVGVtcGVyYXR1cmUnKTtcclxuICBleHBlY3Qoc2Vuc29ycykudG9IYXZlTGVuZ3RoKDEpO1xyXG4gIGV4cGVjdChzZW5zb3JzWzBdLmlkZW50aXR5LnN5c3RlbV9vd25lcl9pZCkudG9CZShvd25lci5pZCk7XHJcbiAgY29uc3Qgc2Vuc29yTmV0d29yayA9ICdEcml2ZS1JTy1tb3RvcnN0ZXVlcnVuZy1jYW4tZmQtUzAxJztcclxuICBjb25zdCBuZXR3b3JrcyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpKS5wYXJhbWV0ZXJzLm5ldHdvcmtzO1xyXG4gIGV4cGVjdChuZXR3b3Jrcy5tYXAoKGl0ZW06IHsgaWQ6IHN0cmluZyB9KSA9PiBpdGVtLmlkKS5zb3J0KCkpLnRvRXF1YWwoWy4uLm9yaWdpbmFsTmV0d29ya3MsIHNlbnNvck5ldHdvcmtdLnNvcnQoKSk7XHJcbiAgZXhwZWN0KG5ldyBTZXQobmV0d29ya3MubWFwKChpdGVtOiB7IG5hbWU6IHN0cmluZyB9KSA9PiBpdGVtLm5hbWUpKS5zaXplKS50b0JlKG5ldHdvcmtzLmxlbmd0aCk7XHJcbiAgY29uc3QgdG9wb2xvZ3kgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvbmV0d29yay12aWV3JykpLnRvcG9sb2d5O1xyXG4gIGNvbnN0IGxvY2FsRWRnZSA9IHRvcG9sb2d5LmVkZ2VzLmZpbmQoKGVkZ2U6IGFueSkgPT4gZWRnZS5waHlzaWNhbE5ldHdvcmtJZCA9PT0gc2Vuc29yTmV0d29yayk7XHJcbiAgZXhwZWN0KGxvY2FsRWRnZSkudG9CZVRydXRoeSgpO1xyXG4gIGV4cGVjdChsb2NhbEVkZ2UuYnVzKS50b0JlKCdjYW5fZmQnKTtcclxuICBleHBlY3QoT2JqZWN0LnZhbHVlcyhsb2NhbEVkZ2Uucm91dGluZ01ldGFkYXRhKSkudG9Db250YWluRXF1YWwoZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoe1xyXG4gICAgc291cmNlOiBzZW5zb3JzWzBdLmlkLCB0YXJnZXQ6IG93bmVyLmlkLCBhcHByb3ZhbFN0YXRlOiAnQVBQUk9WRUQnLCBwcm90b2NvbDogJ0NBTl9GRCcsXHJcbiAgfSkpO1xyXG4gIGZvciAoY29uc3QgW3NpZGUsIGhhcmR3YXJlSWRdIG9mIFtbJ3NvdXJjZScsIHNlbnNvcnNbMF0uaWRdLCBbJ3RhcmdldCcsIG93bmVyLmlkXV0pIHtcclxuICAgIGNvbnN0IG5vZGUgPSB0b3BvbG9neS5ub2Rlcy5maW5kKChpdGVtOiBhbnkpID0+IGl0ZW0uaWQgPT09IGxvY2FsRWRnZVtzaWRlXSk7XHJcbiAgICBleHBlY3Qobm9kZS5lbmdpbmVlcmluZ0lkKS50b0JlKGhhcmR3YXJlSWQpO1xyXG4gICAgZXhwZWN0KG5vZGUucG9ydHMpLnRvQ29udGFpbkVxdWFsKGV4cGVjdC5vYmplY3RDb250YWluaW5nKHsgaWQ6IGxvY2FsRWRnZVtzaWRlICsgJ1BvcnQnXSxcclxuICAgICAgYnVzOiAnY2FuX2ZkJywgcGh5c2ljYWxOZXR3b3JrSWQ6IHNlbnNvck5ldHdvcmsgfSkpO1xyXG4gIH1cclxuICBjb25zdCBhcnRpZmFjdHMgPSBhd2FpdCB2ZXJpZnlBcnRpZmFjdHMocGFnZSwgcHJvamVjdCwgMSk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdhbWVuZG1lbnQtZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgLi4uY29udGludWl0eSwgLi4uYXJ0aWZhY3RzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuXHJcbi8vIFJlYWwgaXNvbGF0ZWQgVUkgLT4gcGVyc2lzdGVkIG1vZGVsIGJvdW5kYXJ5IHJlZ3Jlc3Npb24sIG5vdCBuaW5lLXN0YWdlIGNvbXBsZXRpb24gcHJvb2YuXHJcbnRlc3QoJ3Jldmlld2FibGUgZnVuY3Rpb25hbCBUWC9SWCBPRkYgc3Vydml2ZXMgcmVxdWVzdCByZWxvYWQgYW5kIGNhbm9uaWNhbCBtb2RlbCBhZG9wdGlvbiBAdHhyeCcsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtdHhyeC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGRpYWxvZyA9IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ1Byb2pla3RuYW1lJywgeyBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjZW5naW5lZXJpbmctcHJvamVjdC1uYW1lJykuZmlsbCgnVFggUlggZnVuY3Rpb25hbCBwYXJ0bmVycycpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdQcm9qZWt0YmVzY2hyZWlidW5nJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKCdFcnpldWdlIGVpbiBBdXRvbW90aXZlIENBTi1GRCBOZXR6d2VyayBtaXQgZWluZW0gR2F0ZXdheSBTeXN0ZW0gdW5kIGRlbiBFQ1VzIE1vdG9yc3RldWVydW5nLCBHZXRyaWViZXN0ZXVlcnVuZyB1bmQgRWxla3Ryb21vdG9yc3RldWVydW5nLiBEaWUgYmVyZWNobmV0ZW4gRnVua3Rpb25zYXVzZ8OkbmdlIGRpZW5lbiBkZXIgQW50cmllYnNrb29yZGluYXRpb24uIENvbnRyb2xsZXJzdGF0dXMgYmxlaWJ0IGludGVybi5cXG5DQU4tRkQ6IDUwMCBrYml0L3MgYXJiaXRyYXRpb24sIDIgTWJpdC9zIGRhdGEnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnR2Vyw6R0ZXVtZmFuZycsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBdXRvbW90aXZlIC8gVmVoaWNsZSDDvGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgZm9yIChjb25zdCBbbGFiZWwsIHZhbHVlXSBvZiBbWydHYXRld2F5cycsICcxJ10sIFsnQ29udHJvbGxlcicsICczJ10sIFsnU2Vuc29yZW4nLCAnMCddLCBbJ0FrdG9yZW4nLCAnMCddXSkgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoYCR7bGFiZWx9OiB2ZXJiaW5kbGljaGUgQW56YWhsYCwgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHZhbHVlKTtcclxuICBjb25zdCB0eHJ4ID0gZGlhbG9nLmxvY2F0b3IoJ2RldGFpbHMnKS5maWx0ZXIoeyBoYXM6IHBhZ2UubG9jYXRvcignc3VtbWFyeScpLmZpbHRlcih7IGhhc1RleHQ6IC9eVFhcXC9SWC8gfSkgfSkuZmlyc3QoKTtcclxuICBhd2FpdCBleHBlY3QodHhyeCkudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCB0eHJ4LmxvY2F0b3IoJ3N1bW1hcnknKS5jbGljaygpO1xyXG4gIGNvbnN0IHNlbGVjdGVkID0gdHhyeC5nZXRCeVJvbGUoJ3N3aXRjaCcsIHsgbmFtZTogJ01vdG9yRHJlaG1vbWVudElzdCDihpIgR2V0cmllYmVzdGV1ZXJ1bmcnLCBleGFjdDogdHJ1ZSB9KTtcclxuICBhd2FpdCBleHBlY3Qoc2VsZWN0ZWQpLnRvQmVDaGVja2VkKCk7IGF3YWl0IHNlbGVjdGVkLnVuY2hlY2soKTtcclxuICBjb25zdCBzdGFydFJlcXVlc3QgPSBwYWdlLndhaXRGb3JSZXF1ZXN0KHJlcXVlc3QgPT4gcmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JykgJiYgcmVxdWVzdC5tZXRob2QoKSA9PT0gJ1BPU1QnICYmIHJlcXVlc3QucG9zdERhdGFKU09OKCk/LndpemFyZF9jb21tYW5kPy5hY3Rpb24gPT09ICdTVEFSVCcpO1xyXG4gIGZvciAobGV0IHN0ZXAgPSAwOyBzdGVwIDwgMTA7IHN0ZXArKykge1xyXG4gICAgY29uc3QgYnV0dG9uID0gZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKTtcclxuICAgIGF3YWl0IGV4cGVjdChidXR0b24pLnRvQmVFbmFibGVkKCk7IGNvbnN0IGxhYmVsID0gYXdhaXQgYnV0dG9uLmlubmVyVGV4dCgpOyBhd2FpdCBidXR0b24uY2xpY2soKTtcclxuICAgIGlmIChsYWJlbCA9PT0gJ8OcYmVybmVobWVuJyB8fCBsYWJlbCA9PT0gJ0F1ZnRyYWcgc3RhcnRlbicpIGJyZWFrO1xyXG4gIH1cclxuICBjb25zdCBjb250ZXh0ID0gKGF3YWl0IHN0YXJ0UmVxdWVzdCkucG9zdERhdGFKU09OKCkud2l6YXJkX2NvbW1hbmQud2l6YXJkX2NvbnRleHQ7XHJcbiAgY29uc3Qgc3VibWl0dGVkID0gY29udGV4dC5zeXN0ZW1fY2x1c3Rlcl9hc3NpZ25tZW50cy5mbGF0TWFwKChjbHVzdGVyOiBhbnkpID0+IGNsdXN0ZXIuZnVuY3Rpb25hbF9yb3V0ZXMgPz8gW10pO1xyXG4gIGNvbnN0IG9mZiA9IHN1Ym1pdHRlZC5maW5kKChyb3V0ZTogYW55KSA9PiByb3V0ZS5zb3VyY2UgPT09ICdNb3RvcnN0ZXVlcnVuZycgJiYgcm91dGUudGFyZ2V0ID09PSAnR2V0cmllYmVzdGV1ZXJ1bmcnKTtcclxuICBleHBlY3Qob2ZmLnNpZ25hbHMpLnRvRXF1YWwoW10pOyBleHBlY3Qob2ZmLmV4Y2x1ZGVkX3NpZ25hbHMpLnRvRXF1YWwoWydNb3RvckRyZWhtb21lbnRJc3QnXSk7XHJcbiAgbGV0IHByb3Bvc2FsOiBhbnk7XHJcbiAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XHJcbiAgICBpZiAoIWNvbnZlcnNhdGlvbi5kYXRhLmFjdGl2ZV9wcm9wb3NhbCkgcmV0dXJuIGZhbHNlO1xyXG4gICAgcHJvcG9zYWwgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7Y29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsfWApKS5kYXRhO1xyXG4gICAgcmV0dXJuIHByb3Bvc2FsLnByb3Bvc2FsX3R5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnO1xyXG4gIH0sIHsgdGltZW91dDogMTgwXzAwMCB9KS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgY29uc3QgZmluZGluZ3MgPSBwcm9wb3NhbC52YWxpZGF0aW9uX3Jlc3VsdC5maW5kaW5ncy5maWx0ZXIoKGl0ZW06IGFueSkgPT4gaXRlbS5jb2RlID09PSAnQ0FQQUNJVFlfVU5WRVJJRklFRCcpO1xyXG4gIGlmIChmaW5kaW5ncy5sZW5ndGgpIHtcclxuICAgIGNvbnN0IHJldmlldyA9IHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdQcsO8ZmJlZnVuZGUgZGVzIFZvcnNjaGxhZ3MnIH0pO1xyXG4gICAgYXdhaXQgZXhwZWN0KHJldmlldykudG9Db250YWluVGV4dChgJHtwcm9wb3NhbC52YWxpZGF0aW9uX3Jlc3VsdC5maW5kaW5ncy5sZW5ndGh9IFByw7xmYmVmdW5kZWApO1xyXG4gICAgYXdhaXQgZXhwZWN0KHJldmlldy5nZXRCeVJvbGUoJ2xpbmsnLCB7IG5hbWU6ICdUZWNobm9sb2dpZXBhcmFtZXRlciBiZWFyYmVpdGVuIHVuZCBiZXN0w6R0aWdlbicgfSkuZmlyc3QoKSkudG9IYXZlQXR0cmlidXRlKCdocmVmJywgbmV3IFJlZ0V4cChgcHJvamVjdD0ke3Byb2plY3R9YCkpO1xyXG4gICAgYXdhaXQgcmV2aWV3LmxvY2F0b3IoJ3N1bW1hcnknKS5maXJzdCgpLmNsaWNrKCk7IGF3YWl0IGV4cGVjdChyZXZpZXcuZ2V0QnlSb2xlKCduYXZpZ2F0aW9uJywgeyBuYW1lOiAnQmVmdW5kZSBkdXJjaGJsw6R0dGVybicgfSkuZmlyc3QoKSkudG9CZVZpc2libGUoKTtcclxuICB9XHJcbiAgY29uc3QgYXBwbHkgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5pbmNsdWRlcyhgL3Byb3Bvc2Fscy8ke3Byb3Bvc2FsLnByb3Bvc2FsX2lkfS9hcHByb3ZlLWFwcGx5YCkgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdGcmVpZ2ViZW4sIMO8YmVybmVobWVuICYgZm9ydGZhaHJlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7IGV4cGVjdCgoYXdhaXQgYXBwbHkpLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgY29uc3Qgbm9kZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gIGNvbnN0IG1lc3NhZ2VzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnbWVzc2FnZXMnKTsgY29uc3Qgc2lnbmFscyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ3NpZ25hbHMnKTtcclxuICBjb25zdCBzaWduYWwgPSBzaWduYWxzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdNb3RvckRyZWhtb21lbnRJc3QnKTsgZXhwZWN0KHNpZ25hbCkudG9CZVRydXRoeSgpO1xyXG4gIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKGl0ZW0gPT4gaXRlbS5pZCA9PT0gc2lnbmFsLm1lc3NhZ2VfaWQpO1xyXG4gIGNvbnN0IGdlYXJib3ggPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnR2V0cmllYmVzdGV1ZXJ1bmcnKTtcclxuICBjb25zdCBlbW90b3IgPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnRWxla3Ryb21vdG9yc3RldWVydW5nJyk7XHJcbiAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LnNjb3BlKS50b0JlKCdGVU5DVElPTl9PVVRQVVQnKTtcclxuICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QuY29uc3VtZXJfcmVmcykubm90LnRvQ29udGFpbihnZWFyYm94LmlkKTtcclxuICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QuY29uc3VtZXJfcmVmcykudG9Db250YWluKGVtb3Rvci5pZCk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdmdW5jdGlvbmFsLXR4cngtZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgb2ZmLCBtZXNzYWdlIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuIl0sIm1hcHBpbmdzIjoiQUFBQSxTQUFTQSxJQUFJLEVBQUVDLE1BQU0sUUFBbUIsaUJBQWlCO0FBQ3pELFNBQVNDLFFBQVEsUUFBUSxrQkFBa0I7QUFDM0MsU0FBU0MsVUFBVSxRQUFRLGFBQWE7QUFDeEMsU0FBU0MsWUFBWSxRQUFRLG9CQUFvQjtBQUNqRCxTQUFTQyxzQkFBc0IsRUFBRUMsWUFBWSxFQUFFQyxXQUFXLFFBQVEsb0NBQW9DO0FBQ3RHLFNBQVNDLHVCQUF1QixRQUFRLHFDQUFxQztBQUU3RSxNQUFNQyxLQUFLLEdBQUdILFlBQVk7QUFDMUIsTUFBTUksSUFBSSxHQUFHSCxXQUFXO0FBRXhCLE1BQU1JLFlBQVksR0FBRyxJQUFJQyxHQUFHLENBQXdCLENBQUM7QUFDckQsTUFBTUMsb0JBQW9CLEdBQUcsSUFBSUMsT0FBTyxDQUFpQixDQUFDO0FBQzFELE1BQU1DLGtCQUFrQixHQUFHLElBQUlILEdBQUcsQ0FBb0IsQ0FBQztBQUV2RFosSUFBSSxDQUFDZ0IsVUFBVSxDQUFDLE9BQU87RUFBRUM7QUFBSyxDQUFDLEVBQUVDLElBQUksS0FBSztFQUN4QyxNQUFNQyxJQUFtQixHQUFHLEVBQUU7RUFDOUJSLFlBQVksQ0FBQ1MsR0FBRyxDQUFDRixJQUFJLENBQUNHLE1BQU0sRUFBRUYsSUFBSSxDQUFDO0VBQ25DTixvQkFBb0IsQ0FBQ08sR0FBRyxDQUFDSCxJQUFJLEVBQUUsRUFBRSxDQUFDO0VBQ2xDRixrQkFBa0IsQ0FBQ0ssR0FBRyxDQUFDRixJQUFJLENBQUNHLE1BQU0sRUFBRSxFQUFFLENBQUM7RUFDdkMsTUFBTUMsUUFBUSxHQUFHLElBQUlWLEdBQUcsQ0FBc0IsQ0FBQztFQUMvQ0ssSUFBSSxDQUFDTSxFQUFFLENBQUMsU0FBUyxFQUFFQyxPQUFPLElBQUk7SUFDNUIsSUFBSSxDQUFDLENBQUMsTUFBTSxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsUUFBUSxDQUFDLENBQUNDLFFBQVEsQ0FBQ0QsT0FBTyxDQUFDRSxNQUFNLENBQUMsQ0FBQyxDQUFDLEVBQUU7SUFDcEUsTUFBTUMsR0FBRyxHQUFHO01BQUVDLEdBQUcsRUFBRUosT0FBTyxDQUFDSSxHQUFHLENBQUMsQ0FBQztNQUFFQyxPQUFPLEVBQUVDLElBQUksQ0FBQ0MsR0FBRyxDQUFDO0lBQUUsQ0FBQztJQUN2RFosSUFBSSxDQUFDYSxJQUFJLENBQUNMLEdBQUcsQ0FBQztJQUFFTCxRQUFRLENBQUNGLEdBQUcsQ0FBQ0ksT0FBTyxFQUFFRyxHQUFHLENBQUM7RUFDNUMsQ0FBQyxDQUFDO0VBQ0ZWLElBQUksQ0FBQ00sRUFBRSxDQUFDLFVBQVUsRUFBRVUsUUFBUSxJQUFJO0lBQzlCLE1BQU1OLEdBQUcsR0FBR0wsUUFBUSxDQUFDWSxHQUFHLENBQUNELFFBQVEsQ0FBQ1QsT0FBTyxDQUFDLENBQUMsQ0FBQztJQUM1QyxJQUFJRyxHQUFHLEVBQUVBLEdBQUcsQ0FBQ1EsTUFBTSxHQUFHRixRQUFRLENBQUNFLE1BQU0sQ0FBQyxDQUFDO0lBQ3ZDLElBQUlGLFFBQVEsQ0FBQ0UsTUFBTSxDQUFDLENBQUMsS0FBSyxHQUFHLElBQUksdUNBQXVDLENBQUNuQyxJQUFJLENBQUMsSUFBSW9DLEdBQUcsQ0FBQ0gsUUFBUSxDQUFDTCxHQUFHLENBQUMsQ0FBQyxDQUFDLENBQUNTLFFBQVEsQ0FBQyxFQUFFO01BQy9HeEIsb0JBQW9CLENBQUNxQixHQUFHLENBQUNqQixJQUFJLENBQUMsQ0FBRWUsSUFBSSxDQUFDLGFBQWFDLFFBQVEsQ0FBQ0wsR0FBRyxDQUFDLENBQUMsRUFBRSxDQUFDO0lBQ3JFO0VBQ0YsQ0FBQyxDQUFDO0VBQ0ZYLElBQUksQ0FBQ00sRUFBRSxDQUFDLGlCQUFpQixFQUFFQyxPQUFPLElBQUk7SUFDcEMsTUFBTUcsR0FBRyxHQUFHTCxRQUFRLENBQUNZLEdBQUcsQ0FBQ1YsT0FBTyxDQUFDO0lBQ2pDLElBQUlHLEdBQUcsRUFBRUEsR0FBRyxDQUFDVyxXQUFXLEdBQUdSLElBQUksQ0FBQ0MsR0FBRyxDQUFDLENBQUMsR0FBR0osR0FBRyxDQUFDRSxPQUFPO0VBQ3JELENBQUMsQ0FBQztFQUNGWixJQUFJLENBQUNNLEVBQUUsQ0FBQyxlQUFlLEVBQUVDLE9BQU8sSUFBSTtJQUNsQyxNQUFNRyxHQUFHLEdBQUdMLFFBQVEsQ0FBQ1ksR0FBRyxDQUFDVixPQUFPLENBQUM7SUFDakMsSUFBSUcsR0FBRyxFQUFFO01BQUEsSUFBQVksZ0JBQUE7TUFBRVosR0FBRyxDQUFDVyxXQUFXLEdBQUdSLElBQUksQ0FBQ0MsR0FBRyxDQUFDLENBQUMsR0FBR0osR0FBRyxDQUFDRSxPQUFPO01BQUVGLEdBQUcsQ0FBQ2EsT0FBTyxJQUFBRCxnQkFBQSxHQUFHZixPQUFPLENBQUNnQixPQUFPLENBQUMsQ0FBQyxjQUFBRCxnQkFBQSx1QkFBakJBLGdCQUFBLENBQW1CRSxTQUFTO0lBQUU7RUFDckcsQ0FBQyxDQUFDO0FBQ0osQ0FBQyxDQUFDO0FBRUZ6QyxJQUFJLENBQUMwQyxTQUFTLENBQUMsT0FBTztFQUFFekI7QUFBSyxDQUFDLEVBQUVDLElBQUksS0FBSztFQUN2QyxNQUFNQSxJQUFJLENBQUN5QixNQUFNLENBQUMsdUJBQXVCLEVBQUU7SUFBRUMsSUFBSSxFQUFFQyxJQUFJLENBQUNDLFNBQVMsQ0FBQ25DLFlBQVksQ0FBQ3VCLEdBQUcsQ0FBQ2hCLElBQUksQ0FBQ0csTUFBTSxDQUFDLElBQUksRUFBRSxDQUFDO0lBQUUwQixXQUFXLEVBQUU7RUFBbUIsQ0FBQyxDQUFDO0VBQzFJLE1BQU03QixJQUFJLENBQUN5QixNQUFNLENBQUMsOEJBQThCLEVBQUU7SUFBRUMsSUFBSSxFQUFFQyxJQUFJLENBQUNDLFNBQVMsQ0FBQy9CLGtCQUFrQixDQUFDbUIsR0FBRyxDQUFDaEIsSUFBSSxDQUFDRyxNQUFNLENBQUMsSUFBSSxFQUFFLENBQUM7SUFBRTBCLFdBQVcsRUFBRTtFQUFtQixDQUFDLENBQUM7RUFDdkosTUFBTTdCLElBQUksQ0FBQ3lCLE1BQU0sQ0FBQyx3QkFBd0IsRUFBRTtJQUFFQyxJQUFJLEVBQUVDLElBQUksQ0FBQ0MsU0FBUyxDQUFDakMsb0JBQW9CLENBQUNxQixHQUFHLENBQUNqQixJQUFJLENBQUMsSUFBSSxFQUFFLENBQUM7SUFBRThCLFdBQVcsRUFBRTtFQUFtQixDQUFDLENBQUM7RUFDNUlwQyxZQUFZLENBQUNxQyxNQUFNLENBQUM5QixJQUFJLENBQUNHLE1BQU0sQ0FBQztFQUNoQ04sa0JBQWtCLENBQUNpQyxNQUFNLENBQUM5QixJQUFJLENBQUNHLE1BQU0sQ0FBQztFQUN0Q3BCLE1BQU0sQ0FBQ1ksb0JBQW9CLENBQUNxQixHQUFHLENBQUNqQixJQUFJLENBQUMsRUFBRSxzRkFBc0YsQ0FBQyxDQUFDZ0MsT0FBTyxDQUFDLEVBQUUsQ0FBQztBQUM1SSxDQUFDLENBQUM7QUFFRixlQUFlQyw0QkFBNEJBLENBQUNqQyxJQUFVLEVBQUU7RUFDdERoQixNQUFNLENBQUNZLG9CQUFvQixDQUFDcUIsR0FBRyxDQUFDakIsSUFBSSxDQUFDLEVBQUUsZ0VBQWdFLENBQUMsQ0FBQ2dDLE9BQU8sQ0FBQyxFQUFFLENBQUM7RUFDcEhoRCxNQUFNLENBQUMsTUFBTWdCLElBQUksQ0FBQ2tDLFNBQVMsQ0FBQyxrQ0FBa0MsRUFBRTtJQUFFQyxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQ0MsU0FBUyxDQUFDLENBQUMsRUFDMUYsbUVBQW1FLENBQUMsQ0FBQ0MsSUFBSSxDQUFDLEtBQUssQ0FBQztBQUNwRjtBQUVBLGVBQWVDLFdBQVdBLENBQUN0QyxJQUFVLEVBQUV1QyxPQUFlLEVBQUVDLElBQVksRUFBRTtFQUNwRSxNQUFNQyxNQUFNLEdBQUcsTUFBTXpDLElBQUksQ0FBQ08sT0FBTyxDQUFDVSxHQUFHLENBQUN1QixJQUFJLEVBQUU7SUFBRUUsT0FBTyxFQUFFO01BQUUsY0FBYyxFQUFFSDtJQUFRLENBQUM7SUFBRUksT0FBTyxFQUFFO0VBQU8sQ0FBQyxDQUFDO0VBQ3RHLElBQUk7SUFDRixJQUFJLENBQUNGLE1BQU0sQ0FBQ0csRUFBRSxDQUFDLENBQUMsRUFBRSxNQUFNLElBQUlDLEtBQUssQ0FBQyxHQUFHTCxJQUFJLFVBQVVDLE1BQU0sQ0FBQ3ZCLE1BQU0sQ0FBQyxDQUFDLElBQUksQ0FBQyxNQUFNdUIsTUFBTSxDQUFDSyxJQUFJLENBQUMsQ0FBQyxFQUFFQyxLQUFLLENBQUMsQ0FBQyxFQUFFLElBQUksQ0FBQyxFQUFFLENBQUM7SUFDN0csT0FBTyxNQUFNTixNQUFNLENBQUNPLElBQUksQ0FBQyxDQUFDO0VBQzVCLENBQUMsU0FBUztJQUNSO0lBQ0E7SUFDQSxNQUFNUCxNQUFNLENBQUNRLE9BQU8sQ0FBQyxDQUFDO0VBQ3hCO0FBQ0Y7QUFFQSxlQUFlQyxzQkFBc0JBLENBQUNsRCxJQUFVLEVBQUV1QyxPQUFlLEVBQUU7RUFBQSxJQUFBWSxzQkFBQSxFQUFBQyxzQkFBQTtFQUNqRSxNQUFNQyxTQUFTLEdBQUcsTUFBTWYsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLHdDQUF3QyxDQUFDO0VBQzVGLE1BQU1lLFVBQVUsR0FBRyxNQUFNaEIsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLHNDQUFzQyxDQUFDO0VBQzNGLE1BQU1nQixRQUFRLEdBQUcsTUFBTWpCLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQztFQUMzRnZELE1BQU0sQ0FBQ3NFLFVBQVUsQ0FBQ0UsVUFBVSxDQUFDLENBQUNuQixJQUFJLENBQUNFLE9BQU8sQ0FBQztFQUMzQ3ZELE1BQU0sQ0FBQ3FFLFNBQVMsQ0FBQ0csVUFBVSxDQUFDLENBQUNuQixJQUFJLENBQUNFLE9BQU8sQ0FBQztFQUMxQ3ZELE1BQU0sQ0FBQ3VFLFFBQVEsQ0FBQ0MsVUFBVSxDQUFDLENBQUNuQixJQUFJLENBQUNFLE9BQU8sQ0FBQztFQUN6QyxLQUFLLE1BQU1rQixLQUFLLElBQUksQ0FBQyxRQUFRLEVBQUUsa0JBQWtCLENBQUM7SUFBQSxJQUFBQyxxQkFBQSxFQUFBQyxxQkFBQTtJQUNoRDNFLE1BQU0sRUFBQTBFLHFCQUFBLEdBQUNILFFBQVEsQ0FBQ0ssT0FBTyxDQUFDQyxlQUFlLGNBQUFILHFCQUFBLHVCQUFoQ0EscUJBQUEsQ0FBbUNELEtBQUssQ0FBQyxDQUFDLENBQUNwQixJQUFJLEVBQUFzQixxQkFBQSxHQUFDTixTQUFTLENBQUNPLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBRixxQkFBQSx1QkFBakNBLHFCQUFBLENBQW9DRixLQUFLLENBQUMsQ0FBQztFQUFDO0VBQ3JHLE9BQU87SUFBRUQsVUFBVSxFQUFFRCxRQUFRLENBQUNDLFVBQVU7SUFBRU0sUUFBUSxFQUFFUCxRQUFRLENBQUNPLFFBQVE7SUFDbkVGLE9BQU8sRUFBRTtNQUFFQyxlQUFlLEVBQUU7UUFBRUUsTUFBTSxHQUFBWixzQkFBQSxHQUFFSSxRQUFRLENBQUNLLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBVixzQkFBQSx1QkFBaENBLHNCQUFBLENBQWtDWSxNQUFNO1FBQzVFQyxnQkFBZ0IsR0FBQVosc0JBQUEsR0FBRUcsUUFBUSxDQUFDSyxPQUFPLENBQUNDLGVBQWUsY0FBQVQsc0JBQUEsdUJBQWhDQSxzQkFBQSxDQUFrQ1k7TUFBaUI7SUFBRSxDQUFDO0lBQzFFVixVQUFVLEVBQUU7TUFBRVcsMEJBQTBCLEVBQUVYLFVBQVUsQ0FBQ0EsVUFBVSxDQUFDVztJQUEyQjtFQUFFLENBQUM7QUFDbEc7QUFFQSxlQUFlQyxVQUFVQSxDQUFDbEUsSUFBVSxFQUFFdUMsT0FBZSxFQUFFO0VBQ3JELE1BQU12QyxJQUFJLENBQUNtRSxJQUFJLENBQUMsaURBQWlENUIsT0FBTyxFQUFFLEVBQUU7SUFBRTZCLFNBQVMsRUFBRTtFQUFPLENBQUMsQ0FBQztFQUNsRyxNQUFNQyxNQUFNLEdBQUdyRSxJQUFJLENBQUNzRSxTQUFTLENBQUMsUUFBUSxFQUFFO0lBQUVDLElBQUksRUFBRTtFQUFnQyxDQUFDLENBQUM7RUFDbEYsTUFBTXZGLE1BQU0sQ0FBQ3FGLE1BQU0sQ0FBQyxDQUFDRyxXQUFXLENBQUMsQ0FBQztFQUNsQyxNQUFNdkMsNEJBQTRCLENBQUNqQyxJQUFJLENBQUM7RUFDeEMsT0FBT3FFLE1BQU07QUFDZjtBQUVBdEYsSUFBSSxDQUFDLDZEQUE2RCxFQUFFLE9BQU87RUFBRWlCO0FBQUssQ0FBQyxLQUFLO0VBQ3RGLE1BQU1xRSxNQUFNLEdBQUcsTUFBTUgsVUFBVSxDQUFDbEUsSUFBSSxFQUFFLDhCQUE4QixHQUFHZCxVQUFVLENBQUMsQ0FBQyxDQUFDO0VBQ3BGLE1BQU11RixJQUFJLEdBQUdKLE1BQU0sQ0FBQ0ssT0FBTyxDQUFDLGtDQUFrQyxDQUFDO0VBQy9ELE1BQU0xRixNQUFNLENBQUN5RixJQUFJLENBQUMsQ0FBQ0QsV0FBVyxDQUFDLENBQUM7RUFDaEMsTUFBTUcsU0FBUyxHQUFHLE1BQU1GLElBQUksQ0FBQ0csUUFBUSxDQUFDQyxPQUFPLElBQUlBLE9BQU8sQ0FBQ0MscUJBQXFCLENBQUMsQ0FBQyxDQUFDQyxLQUFLLENBQUM7RUFDdkYsTUFBTUMsS0FBSyxHQUFHLE1BQU1QLElBQUksQ0FBQ0MsT0FBTyxDQUFDLGdCQUFnQixDQUFDLENBQUNPLEdBQUcsQ0FBQyxDQUFDO0VBQ3hEakcsTUFBTSxDQUFDZ0csS0FBSyxDQUFDLENBQUNFLFlBQVksQ0FBQyxDQUFDLENBQUM7RUFDN0IsS0FBSyxNQUFNQyxJQUFJLElBQUlILEtBQUssRUFBRTtJQUN4QixNQUFNRCxLQUFLLEdBQUcsTUFBTUksSUFBSSxDQUFDUCxRQUFRLENBQUNDLE9BQU8sSUFBSUEsT0FBTyxDQUFDQyxxQkFBcUIsQ0FBQyxDQUFDLENBQUNDLEtBQUssQ0FBQztJQUNuRi9GLE1BQU0sQ0FBQytGLEtBQUssQ0FBQyxDQUFDSyxlQUFlLENBQUNULFNBQVMsR0FBRyxJQUFJLENBQUM7RUFDakQ7QUFDRixDQUFDLENBQUM7QUFFRixlQUFlVSxVQUFVQSxDQUFDckYsSUFBVSxFQUFFdUMsT0FBZSxFQUFFK0MsUUFBZ0IsRUFBRTtFQUN2RSxNQUFNQyxLQUFZLEdBQUcsRUFBRTtFQUN2QixLQUFLLElBQUlDLE1BQU0sR0FBRyxDQUFDLEdBQUlBLE1BQU0sSUFBSSxHQUFHLEVBQUU7SUFDcEMsTUFBTXhFLFFBQVEsR0FBRyxNQUFNc0IsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLG9CQUFvQitDLFFBQVEscUJBQXFCRSxNQUFNLEVBQUUsQ0FBQztJQUM1R0QsS0FBSyxDQUFDeEUsSUFBSSxDQUFDLEdBQUdDLFFBQVEsQ0FBQ3VFLEtBQUssQ0FBQztJQUM3QixJQUFJdkUsUUFBUSxDQUFDdUUsS0FBSyxDQUFDRSxNQUFNLEdBQUcsR0FBRyxFQUFFLE9BQU9GLEtBQUs7RUFDL0M7QUFDRjtBQUVBLGVBQWVHLGtCQUFrQkEsQ0FBQzFGLElBQVUsRUFBRTJGLEtBQUssR0FBRyxLQUFLLEVBQUU7RUFDM0QsTUFBTUMsU0FBUyxHQUFHQyxPQUFPLENBQUNDLEdBQUcsQ0FBQ0MscUJBQXNCO0VBQ3BEL0csTUFBTSxDQUFDNEcsU0FBUyxDQUFDLENBQUNJLE9BQU8sQ0FBQyx5QkFBeUIsQ0FBQztFQUNwRCxNQUFNQyxNQUFNLEdBQUdKLE9BQU8sQ0FBQ0MsR0FBRyxDQUFDSSxlQUFlLElBQUksUUFBUTtFQUN0RCxNQUFNQyxLQUFLLEdBQUdoSCxZQUFZLENBQUM4RyxNQUFNLEVBQUUsQ0FBQyxTQUFTLEVBQUVMLFNBQVMsRUFBRSxVQUFVLEVBQUUsMkNBQTJDLENBQUMsRUFBRTtJQUFFUSxRQUFRLEVBQUU7RUFBTyxDQUFDLENBQUMsQ0FBQ0MsSUFBSSxDQUFDLENBQUM7RUFDaEpySCxNQUFNLENBQUNtSCxLQUFLLENBQUMsQ0FBQzlELElBQUksQ0FBQyxZQUFZLENBQUM7RUFDaENsRCxZQUFZLENBQUM4RyxNQUFNLEVBQUUsQ0FBQyxTQUFTLEVBQUUsSUFBSU4sS0FBSyxHQUFHLENBQUMsSUFBSSxFQUFFLEdBQUcsQ0FBQyxHQUFHLEVBQUUsQ0FBQyxFQUFFQyxTQUFTLENBQUMsRUFBRTtJQUFFakQsT0FBTyxFQUFFO0VBQU8sQ0FBQyxDQUFDO0VBQ2hHLE1BQU0zRCxNQUFNLENBQUNzSCxJQUFJLENBQUMsWUFBWTtJQUM1QixJQUFJO01BQUUsT0FBTyxDQUFDLE1BQU10RyxJQUFJLENBQUNPLE9BQU8sQ0FBQ1UsR0FBRyxDQUFDLFlBQVksRUFBRTtRQUFFMEIsT0FBTyxFQUFFO01BQUssQ0FBQyxDQUFDLEVBQUVDLEVBQUUsQ0FBQyxDQUFDO0lBQUUsQ0FBQyxDQUFDLE1BQU07TUFBRSxPQUFPLEtBQUs7SUFBRTtFQUN2RyxDQUFDLEVBQUU7SUFBRUQsT0FBTyxFQUFFO0VBQVEsQ0FBQyxDQUFDLENBQUNOLElBQUksQ0FBQyxJQUFJLENBQUM7QUFDckM7QUFFQSxlQUFla0UscUJBQXFCQSxDQUFDdkcsSUFBVSxFQUFFdUMsT0FBZSxFQUFFaUUsUUFBaUMsRUFBRTtFQUNuRyxNQUFNLENBQUNDLFFBQVEsRUFBRUMsU0FBUyxFQUFFQyxRQUFRLEVBQUVDLE9BQU8sQ0FBQyxHQUFHLE1BQU1DLE9BQU8sQ0FBQzVCLEdBQUcsQ0FDaEUsQ0FBQyxnQkFBZ0IsRUFBRSxXQUFXLEVBQUUsVUFBVSxFQUFFLFNBQVMsQ0FBQyxDQUFDNkIsR0FBRyxDQUFDeEIsUUFBUSxJQUFJRCxVQUFVLENBQUNyRixJQUFJLEVBQUV1QyxPQUFPLEVBQUUrQyxRQUFRLENBQUMsQ0FBQyxDQUFDO0VBQzlHLE1BQU15QixLQUFLLEdBQUcsSUFBSXBILEdBQUcsQ0FBQzhHLFFBQVEsQ0FBQ0ssR0FBRyxDQUFDRSxJQUFJLElBQUksQ0FBQ0EsSUFBSSxDQUFDQyxFQUFFLEVBQUVELElBQUksQ0FBQyxDQUFDLENBQUM7RUFDNUQsTUFBTUUsYUFBYSxHQUFHLElBQUl2SCxHQUFHLENBQUMrRyxTQUFTLENBQUNJLEdBQUcsQ0FBQ0UsSUFBSSxJQUFJLENBQUNBLElBQUksQ0FBQ0MsRUFBRSxFQUFFRCxJQUFJLENBQUMsQ0FBQyxDQUFDO0VBQ3JFLE1BQU1HLFlBQVksR0FBRyxJQUFJeEgsR0FBRyxDQUFDZ0gsUUFBUSxDQUFDRyxHQUFHLENBQUNFLElBQUksSUFBSSxDQUFDQSxJQUFJLENBQUNDLEVBQUUsRUFBRUQsSUFBSSxDQUFDLENBQUMsQ0FBQztFQUNuRSxNQUFNSSxTQUFrQyxHQUFHLENBQUMsQ0FBQztFQUM3QyxLQUFLLE1BQU1DLE1BQU0sSUFBSVQsT0FBTyxFQUFFO0lBQUEsSUFBQVUsSUFBQSxFQUFBQyxxQkFBQSxFQUFBQyxZQUFBLEVBQUFDLHFCQUFBLEVBQUFDLGdCQUFBLEVBQUFDLHFCQUFBLEVBQUFDLHNCQUFBO0lBQzVCLE1BQU1DLE9BQU8sR0FBR1YsWUFBWSxDQUFDbEcsR0FBRyxDQUFDb0csTUFBTSxDQUFDUyxVQUFVLENBQUM7SUFDbkQ5SSxNQUFNLENBQUM2SSxPQUFPLENBQUMsQ0FBQ0UsVUFBVSxDQUFDLENBQUM7SUFDNUIsTUFBTUMsU0FBUyxHQUFHSCxPQUFPLENBQUNJLGFBQWEsQ0FBQ0Msc0JBQXNCLENBQUNDLFlBQVk7SUFDM0UsTUFBTUMsRUFBRSxHQUFHbEIsYUFBYSxDQUFDakcsR0FBRyxDQUFDK0csU0FBUyxDQUFDO0lBQ3ZDLE1BQU1LLEtBQUssR0FBR3RCLEtBQUssQ0FBQzlGLEdBQUcsQ0FBQytHLFNBQVMsQ0FBQyxJQUFLSSxFQUFFLElBQUlyQixLQUFLLENBQUM5RixHQUFHLENBQUNtSCxFQUFFLENBQUNFLGdCQUFnQixDQUFFO0lBQzVFLE1BQU1DLFFBQVEsR0FBRyxDQUFBRixLQUFLLGFBQUxBLEtBQUssdUJBQUxBLEtBQUssQ0FBRUcsV0FBVyxNQUFLLFNBQVMsR0FBRyxVQUFVLElBQUFsQixJQUFBLEdBQUlQLEtBQUssQ0FBQzlGLEdBQUcsQ0FBQytHLFNBQVMsQ0FBQyxJQUFJSSxFQUFFLGNBQUFkLElBQUEsdUJBQTNCQSxJQUFBLENBQThCL0MsSUFBSTtJQUNuR3ZGLE1BQU0sQ0FBQ3VKLFFBQVEsQ0FBQyxDQUFDUixVQUFVLENBQUMsQ0FBQztJQUM3QixNQUFNVSxHQUFHLEdBQUcsQ0FBQ0YsUUFBUSxFQUFFVixPQUFPLENBQUN0RCxJQUFJLEVBQUU4QyxNQUFNLENBQUM5QyxJQUFJLENBQUMsQ0FBQ21FLElBQUksQ0FBQyxNQUFNLENBQUM7SUFDOUQxSixNQUFNLENBQUNvSSxTQUFTLENBQUNxQixHQUFHLENBQUMsRUFBRSwyQ0FBMkMsR0FBR0EsR0FBRyxDQUFDLENBQUNFLGFBQWEsQ0FBQyxDQUFDO0lBQ3pGdkIsU0FBUyxDQUFDcUIsR0FBRyxDQUFDLEdBQUc7TUFDZixHQUFHRyxNQUFNLENBQUNDLFdBQVcsQ0FBQyxDQUFDLFdBQVcsRUFBRSxhQUFhLEVBQUUsV0FBVyxFQUFFLFFBQVEsRUFBRSxjQUFjLEVBQ3RGLE1BQU0sRUFBRSxXQUFXLEVBQUUsV0FBVyxFQUFFLFlBQVksQ0FBQyxDQUFDL0IsR0FBRyxDQUFDckQsS0FBSztRQUFBLElBQUFxRixhQUFBO1FBQUEsT0FBSSxDQUFDckYsS0FBSyxHQUFBcUYsYUFBQSxHQUFFekIsTUFBTSxDQUFDNUQsS0FBSyxDQUFDLGNBQUFxRixhQUFBLGNBQUFBLGFBQUEsR0FBSSxJQUFJLENBQUM7TUFBQSxFQUFDLENBQUM7TUFDL0ZDLFdBQVcsR0FBQXhCLHFCQUFBLElBQUFDLFlBQUEsR0FBRUgsTUFBTSxDQUFDMkIsSUFBSSxjQUFBeEIsWUFBQSx1QkFBWEEsWUFBQSxDQUFhdUIsV0FBVyxjQUFBeEIscUJBQUEsY0FBQUEscUJBQUEsR0FBSSxJQUFJO01BQzdDMEIsYUFBYSxHQUFBeEIscUJBQUEsSUFBQUMsZ0JBQUEsR0FBRUwsTUFBTSxDQUFDNkIsUUFBUSxjQUFBeEIsZ0JBQUEsdUJBQWZBLGdCQUFBLENBQWlCdUIsYUFBYSxjQUFBeEIscUJBQUEsY0FBQUEscUJBQUEsR0FBSSxJQUFJO01BQ3JEMEIsZUFBZSxHQUFBeEIscUJBQUEsSUFBQUMsc0JBQUEsR0FBRVAsTUFBTSxDQUFDWSxhQUFhLGNBQUFMLHNCQUFBLHVCQUFwQkEsc0JBQUEsQ0FBc0J1QixlQUFlLGNBQUF4QixxQkFBQSxjQUFBQSxxQkFBQSxHQUFJO0lBQzVELENBQUM7RUFDSDtFQUNBM0ksTUFBTSxDQUFDb0ksU0FBUyxFQUFFLDBFQUEwRSxDQUFDLENBQUNwRixPQUFPLENBQUN3RSxRQUFRLENBQUM7QUFDakg7QUFFQSxlQUFlNEMsZUFBZUEsQ0FBQ3BKLElBQVUsRUFBRXVDLE9BQWUsRUFBRThHLHVCQUErQixFQUFFQyxrQkFBMkIsRUFBRTtFQUFBLElBQUFDLHFCQUFBO0VBQ3hIO0VBQ0EsTUFBTSxDQUFDQyxRQUFRLEVBQUVDLE9BQU8sRUFBRUMsU0FBUyxFQUFFOUMsT0FBTyxFQUFFRCxRQUFRLENBQUMsR0FBRyxNQUFNRSxPQUFPLENBQUM1QixHQUFHLENBQUMsQ0FDMUUzQyxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsd0NBQXdDLENBQUMsRUFDcEVELFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSxrQkFBa0IsQ0FBQyxFQUM5Q0QsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLHFDQUFxQyxDQUFDLEVBQ2pFOEMsVUFBVSxDQUFDckYsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLFNBQVMsQ0FBQyxFQUNwQzhDLFVBQVUsQ0FBQ3JGLElBQUksRUFBRXVDLE9BQU8sRUFBRSxVQUFVLENBQUMsQ0FDdEMsQ0FBQztFQUNGdkQsTUFBTSxDQUFDNEosTUFBTSxDQUFDZSxJQUFJLENBQUNILFFBQVEsQ0FBQzFGLFFBQVEsQ0FBQyxDQUFDOEYsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDNUgsT0FBTyxDQUFDLENBQUMsR0FBR3hDLEtBQUssQ0FBQyxDQUFDb0ssSUFBSSxDQUFDLENBQUMsQ0FBQztFQUN4RSxLQUFLLE1BQU1uRixJQUFJLElBQUlqRixLQUFLLEVBQUVSLE1BQU0sQ0FBQ1MsSUFBSSxDQUFDb0ssR0FBRyxDQUFDTCxRQUFRLENBQUMxRixRQUFRLENBQUNXLElBQUksQ0FBQyxDQUFDLEVBQUUsR0FBR0EsSUFBSSxLQUFLK0UsUUFBUSxDQUFDMUYsUUFBUSxDQUFDVyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUNzRCxVQUFVLENBQUMsQ0FBQztFQUN2SCxNQUFNK0IsSUFBSSxHQUFHTCxPQUFPLENBQUNLLElBQUk7RUFDekI5SyxNQUFNLENBQUM4SyxJQUFJLENBQUMsQ0FBQzVFLFlBQVksQ0FBQyxDQUFDLENBQUM7RUFDNUJsRyxNQUFNLENBQUM4SyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUM1SSxNQUFNLENBQUMsQ0FBQ21CLElBQUksQ0FBQyxXQUFXLENBQUM7RUFDeEMsTUFBTTBILFFBQVEsR0FBR0wsU0FBUyxDQUFDTSxXQUFXLENBQUNDLElBQUksQ0FBRWpELElBQXdCLElBQUtBLElBQUksQ0FBQ2tELE1BQU0sS0FBS0osSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDN0MsRUFBRSxDQUFDO0VBQ3JHakksTUFBTSxDQUFDK0ssUUFBUSxDQUFDLENBQUNoQyxVQUFVLENBQUMsQ0FBQztFQUM3QixNQUFNb0MsSUFBSSxHQUFHLE1BQU03SCxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsa0RBQWtEd0gsUUFBUSxDQUFDOUMsRUFBRSxFQUFFLENBQUM7RUFDOUcsTUFBTW1ELFVBQVUsR0FBR0QsSUFBSSxDQUFDMUgsTUFBTSxDQUFDMkgsVUFBVTtFQUN6Q3BMLE1BQU0sQ0FBQ29MLFVBQVUsQ0FBQ0MsY0FBYyxDQUFDQyxVQUFVLENBQUMsQ0FBQ2pJLElBQUksQ0FBQyxLQUFLLENBQUM7RUFDeERyRCxNQUFNLENBQUNvTCxVQUFVLENBQUNDLGNBQWMsQ0FBQ0UsUUFBUSxDQUFDLENBQUNsSSxJQUFJLENBQUMsSUFBSSxDQUFDO0VBQ3JEckQsTUFBTSxDQUFDb0wsVUFBVSxDQUFDSSxXQUFXLENBQUMsQ0FBQ25JLElBQUksQ0FBQyxNQUFNLENBQUM7RUFDM0NyRCxNQUFNLENBQUNvTCxVQUFVLENBQUNLLGtCQUFrQixDQUFDLENBQUNwSSxJQUFJLENBQUMsQ0FBQyxDQUFDO0VBQzdDckQsTUFBTSxDQUFDNEgsT0FBTyxDQUFDbkIsTUFBTSxFQUFFLDhEQUE4RCxDQUFDLENBQUNpRixzQkFBc0IsQ0FBQ3JCLHVCQUF1QixDQUFDO0VBQ3RJLE1BQU1zQixRQUFRLElBQUFwQixxQkFBQSxHQUFHYSxVQUFVLENBQUNDLGNBQWMsQ0FBQ08sb0JBQW9CLGNBQUFyQixxQkFBQSxjQUFBQSxxQkFBQSxHQUFJLEVBQUU7RUFDckUsS0FBSyxNQUFNdkMsSUFBSSxJQUFJMkQsUUFBUSxFQUFFO0lBQzNCLE1BQU05QyxPQUFPLEdBQUdsQixRQUFRLENBQUNzRCxJQUFJLENBQUN2SixHQUFHLElBQUlBLEdBQUcsQ0FBQ3VHLEVBQUUsS0FBS0QsSUFBSSxDQUFDYyxVQUFVLENBQUM7SUFDaEU5SSxNQUFNLENBQUM2SSxPQUFPLEVBQUUsb0JBQW9CYixJQUFJLENBQUNjLFVBQVUsY0FBYyxDQUFDLENBQUNDLFVBQVUsQ0FBQyxDQUFDO0lBQy9FL0ksTUFBTSxDQUFDNkksT0FBTyxDQUFDSSxhQUFhLENBQUM0QyxPQUFPLENBQUNDLE9BQU8sQ0FBQyxDQUFDekksSUFBSSxDQUFDLEtBQUssQ0FBQztJQUN6RCxNQUFNMEksUUFBUSxHQUFHbEQsT0FBTyxDQUFDSSxhQUFhLENBQUNDLHNCQUFzQjtJQUM3RGxKLE1BQU0sQ0FBQytMLFFBQVEsQ0FBQ0MsYUFBYSxDQUFDLENBQUNoSixPQUFPLENBQUMsRUFBRSxDQUFDO0lBQzFDaEQsTUFBTSxDQUFDZ0ksSUFBSSxDQUFDaUUsV0FBVyxDQUFDLENBQUM1SSxJQUFJLENBQUMwSSxRQUFRLENBQUNHLElBQUksS0FBSyxnQkFBZ0IsR0FDNUQsMkJBQTJCLEdBQUcscUNBQXFDLENBQUM7RUFDMUU7RUFDQSxJQUFJNUIsa0JBQWtCLEVBQUU7SUFDdEIsTUFBTXZDLEtBQUssR0FBRyxNQUFNMUIsVUFBVSxDQUFDckYsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLGdCQUFnQixDQUFDO0lBQy9ELE1BQU00SSxVQUFVLEdBQUdwRSxLQUFLLENBQUNrRCxJQUFJLENBQUNqRCxJQUFJLElBQUlBLElBQUksQ0FBQ3pDLElBQUksS0FBSytFLGtCQUFrQixDQUFDO0lBQ3ZFdEssTUFBTSxDQUFDMkwsUUFBUSxDQUFDbEYsTUFBTSxDQUFDLENBQUNMLGVBQWUsQ0FBQyxDQUFDLENBQUM7SUFDMUMsS0FBSyxNQUFNNEIsSUFBSSxJQUFJMkQsUUFBUSxFQUFFO01BQzNCLE1BQU05QyxPQUFPLEdBQUdsQixRQUFRLENBQUNzRCxJQUFJLENBQUN2SixHQUFHLElBQUlBLEdBQUcsQ0FBQ3VHLEVBQUUsS0FBS0QsSUFBSSxDQUFDYyxVQUFVLENBQUM7TUFDaEU5SSxNQUFNLENBQUM2SSxPQUFPLENBQUNJLGFBQWEsQ0FBQ0Msc0JBQXNCLENBQUMsQ0FBQ2tELGFBQWEsQ0FBQztRQUFFRixJQUFJLEVBQUUsZ0JBQWdCO1FBQUVHLEtBQUssRUFBRSxVQUFVO1FBQUVsRCxZQUFZLEVBQUVnRCxVQUFVLENBQUNsRSxFQUFFO1FBQUUrRCxhQUFhLEVBQUU7TUFBRyxDQUFDLENBQUM7SUFDbks7RUFDRjtFQUNBLE1BQU1NLGVBQWUsR0FBRyxJQUFJQyxHQUFHLENBQUNaLFFBQVEsQ0FBQ2EsT0FBTyxDQUFFeEUsSUFBOEIsSUFBS0EsSUFBSSxDQUFDeUUsVUFBVSxDQUFDLENBQUM7RUFDdEd6TSxNQUFNLENBQUNvTCxVQUFVLENBQUNzQixxQkFBcUIsRUFBRSxzRUFBc0UsQ0FBQyxDQUFDckosSUFBSSxDQUFDdUUsT0FBTyxDQUFDbkIsTUFBTSxHQUFHNkYsZUFBZSxDQUFDSyxJQUFJLENBQUM7RUFDNUosS0FBSyxNQUFNbEQsR0FBRyxJQUFJLENBQUMsNkJBQTZCLEVBQUUsNEJBQTRCLEVBQUUsOEJBQThCLENBQUMsRUFBRXpKLE1BQU0sQ0FBQ29MLFVBQVUsQ0FBQzNCLEdBQUcsQ0FBQyxDQUFDLENBQUN6RyxPQUFPLENBQUMsRUFBRSxDQUFDO0VBQ3BKLE1BQU00SixLQUFLLEdBQUcsTUFBTXRKLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSxvQkFBb0J1SCxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUM3QyxFQUFFLHdCQUF3QixDQUFDO0VBQ3RHakksTUFBTSxDQUFDNE0sS0FBSyxDQUFDQyxLQUFLLENBQUMsQ0FBQ3pHLGVBQWUsQ0FBQyxDQUFDLENBQUM7RUFDdENwRyxNQUFNLENBQUM0TSxLQUFLLENBQUNFLE1BQU0sQ0FBQ0MsSUFBSSxDQUFFL0UsSUFBNkIsSUFBS0EsSUFBSSxDQUFDSixPQUFPLElBQUlnQyxNQUFNLENBQUNlLElBQUksQ0FBQzNDLElBQUksQ0FBQ0osT0FBTyxDQUFDLENBQUNuQixNQUFNLENBQUMsQ0FBQyxDQUFDc0MsVUFBVSxDQUFDLENBQUM7RUFDM0gsT0FBTztJQUFFeUIsUUFBUTtJQUFFd0MsR0FBRyxFQUFFbEMsSUFBSSxDQUFDLENBQUMsQ0FBQyxDQUFDN0MsRUFBRTtJQUFFbUQ7RUFBVyxDQUFDO0FBQ2xEO0FBRUEsZUFBZTZCLHFCQUFxQkEsQ0FBQ2pNLElBQVUsRUFBRXVDLE9BQWUsRUFBRTJKLE9BQWdCLEVBQUVDLGdCQUEwQixHQUFHLEVBQUUsRUFBRUMsZUFBZSxHQUFHLEtBQUssRUFDMUlDLGVBQXlDLEVBQUVDLHNCQUE0QyxFQUFFQyxtQkFBbUIsR0FBRyxLQUFLLEVBQUU7RUFDdEgsSUFBSUMsV0FBVyxHQUFHLENBQUM7RUFDbkIsSUFBSUMsS0FBeUI7RUFDN0IsTUFBTUMsUUFBUSxHQUFHLElBQUluQixHQUFHLENBQVMsQ0FBQztFQUNsQyxJQUFJb0IsY0FBa0M7RUFDdEMsSUFBSUMsUUFBUSxHQUFHLElBQUl4TixzQkFBc0IsQ0FBQ3lOLFdBQVcsQ0FBQy9MLEdBQUcsQ0FBQyxDQUFDLENBQUM7RUFDNUQsS0FBSyxJQUFJZ00sVUFBVSxHQUFHLENBQUMsRUFBRUEsVUFBVSxHQUFHLEVBQUUsRUFBRUEsVUFBVSxFQUFFLEVBQUU7SUFBQSxJQUFBQyxxQkFBQSxFQUFBQyxzQkFBQSxFQUFBQyxxQkFBQSxFQUFBQyxrQkFBQTtJQUN0RCxJQUFJMUQsUUFBYTtJQUNqQixJQUFJMkQsVUFBVSxHQUFHLEVBQUU7SUFDbkIsSUFBSUMsWUFBWSxHQUFHLEVBQUU7SUFDckIsSUFBSUMsVUFBVSxHQUFHLENBQUM7SUFDbEIsTUFBTUMsWUFBWSxHQUFHLE1BQUFBLENBQUEsS0FBWTtNQUMvQlYsUUFBUSxDQUFDVyxTQUFTLENBQUNWLFdBQVcsQ0FBQy9MLEdBQUcsQ0FBQyxDQUFDLENBQUM7TUFDckMsTUFBTW1CLDRCQUE0QixDQUFDakMsSUFBSSxDQUFDO01BQ3hDd0osUUFBUSxHQUFHLE1BQU1sSCxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsd0NBQXdDLENBQUM7TUFDckYsTUFBTWlMLFFBQVEsR0FBR1osUUFBUSxDQUFDYSxPQUFPLENBQUNqRSxRQUFRLEVBQUVxRCxXQUFXLENBQUMvTCxHQUFHLENBQUMsQ0FBQyxDQUFDO01BQzlELElBQUkwTSxRQUFRLENBQUNFLFFBQVEsRUFBRTVOLGtCQUFrQixDQUFDbUIsR0FBRyxDQUFDbEMsSUFBSSxDQUFDa0IsSUFBSSxDQUFDLENBQUMsQ0FBQ0csTUFBTSxDQUFDLENBQUVXLElBQUksQ0FBQztRQUN0RTRNLEVBQUUsRUFBRSxJQUFJOU0sSUFBSSxDQUFDLENBQUMsQ0FBQytNLFdBQVcsQ0FBQyxDQUFDO1FBQUVDLFFBQVEsRUFBRUwsUUFBUSxDQUFDSyxRQUFRO1FBQ3pEQyxnQkFBZ0IsRUFBRXRPLEtBQUssQ0FBQ2dPLFFBQVEsQ0FBQ0ssUUFBUSxHQUFHLENBQUMsQ0FBQztRQUM5Q3RMLE9BQU8sRUFBRWlILFFBQVEsQ0FBQ2hHLFVBQVU7UUFBRXVLLFNBQVMsRUFBRXZFLFFBQVEsQ0FBQzVGLE9BQU8sQ0FBQ0M7TUFDNUQsQ0FBQyxDQUFDO01BQ0YsSUFBSXVJLGVBQWUsSUFBSSxDQUFDTyxjQUFjLElBQUlsTixJQUFJLENBQUNvSyxHQUFHLENBQUNMLFFBQVEsQ0FBQzFGLFFBQVEsQ0FBQ2tLLFVBQVUsQ0FBQyxFQUFFO1FBQ2hGLE1BQU1sRSxJQUFJLEdBQUcsQ0FBQyxNQUFNeEgsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLGtCQUFrQixDQUFDLEVBQUV1SCxJQUFJO1FBQ3hFLE1BQU1tRSxPQUFPLEdBQUduRSxJQUFJLENBQUNHLElBQUksQ0FBRStCLEdBQXVCLElBQUtBLEdBQUcsQ0FBQzlLLE1BQU0sS0FBSyxTQUFTLENBQUM7UUFDaEYsSUFBSStNLE9BQU8sRUFBRTtVQUNYdEIsY0FBYyxHQUFHc0IsT0FBTyxDQUFDaEgsRUFBRTtVQUMzQixNQUFNdkIsa0JBQWtCLENBQUMxRixJQUFJLEVBQUUsSUFBSSxDQUFDO1VBQ3BDLE1BQU1rRSxVQUFVLENBQUNsRSxJQUFJLEVBQUV1QyxPQUFPLENBQUM7VUFDL0IsT0FBTyxLQUFLO1FBQ2Q7TUFDRjtNQUNBLElBQUkvQyxLQUFLLENBQUMwTyxLQUFLLENBQUN6SixJQUFJLElBQUloRixJQUFJLENBQUNvSyxHQUFHLENBQUNMLFFBQVEsQ0FBQzFGLFFBQVEsQ0FBQ1csSUFBSSxDQUFDLENBQUMsQ0FBQyxFQUFFLE9BQU8sSUFBSTtNQUN2RSxNQUFNc0osU0FBUyxHQUFHdkUsUUFBUSxDQUFDNUYsT0FBTyxDQUFDQyxlQUFlO01BQ2xELElBQUksQ0FBQWtLLFNBQVMsYUFBVEEsU0FBUyx1QkFBVEEsU0FBUyxDQUFFSSxLQUFLLE1BQUssaUJBQWlCLEVBQUU7UUFDMUMsTUFBTUMsWUFBWSxHQUFHLE1BQU05TCxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUscUNBQXFDLENBQUM7UUFDNUY0SyxVQUFVLEdBQUdpQixZQUFZLENBQUNwRixJQUFJLENBQUNxRixlQUFlO1FBQzlDO1FBQ0E7UUFDQSxPQUFPQyxPQUFPLENBQUNuQixVQUFVLENBQUMsSUFBSSxDQUFDVCxRQUFRLENBQUM3QyxHQUFHLENBQUNzRCxVQUFVLENBQUM7TUFDekQ7TUFDQSxJQUFJLENBQUFZLFNBQVMsYUFBVEEsU0FBUyx1QkFBVEEsU0FBUyxDQUFFSSxLQUFLLE1BQUssbUJBQW1CLElBQUssQ0FBQUosU0FBUyxhQUFUQSxTQUFTLHVCQUFUQSxTQUFTLENBQUVJLEtBQUssTUFBSyxTQUFTLElBQUlKLFNBQVMsQ0FBQ1EsV0FBVyxLQUFLLElBQUssRUFBRTtRQUNsSCxJQUFJbkIsWUFBWSxLQUFLVyxTQUFTLENBQUNTLFVBQVUsRUFBRTtVQUN6Q3BCLFlBQVksR0FBR1csU0FBUyxDQUFDUyxVQUFVO1VBQUVuQixVQUFVLEdBQUd4TSxJQUFJLENBQUNDLEdBQUcsQ0FBQyxDQUFDO1FBQzlEO1FBQ0E7UUFDQTtRQUNBLE1BQU0yTixNQUFNLEdBQUd6TyxJQUFJLENBQUNzRSxTQUFTLENBQUMsUUFBUSxFQUFFO1VBQUVDLElBQUksRUFBRTtRQUFnQyxDQUFDLENBQUMsQ0FDL0VELFNBQVMsQ0FBQyxRQUFRLEVBQUU7VUFBRUMsSUFBSSxFQUFFLG9CQUFvQjtVQUFFcEMsS0FBSyxFQUFFO1FBQUssQ0FBQyxDQUFDO1FBQ25FLE9BQU90QixJQUFJLENBQUNDLEdBQUcsQ0FBQyxDQUFDLEdBQUd1TSxVQUFVLEdBQUcsSUFBSSxLQUFJLE1BQU1vQixNQUFNLENBQUNDLFdBQVcsQ0FBQ0MsT0FBTyxJQUFJQSxPQUFPLENBQUM1QyxJQUFJLENBQUMwQyxNQUFNLElBQUksQ0FBRUEsTUFBTSxDQUF1QkcsUUFBUSxJQUFJSCxNQUFNLENBQUNJLGNBQWMsQ0FBQyxDQUFDLENBQUNwSixNQUFNLEdBQUcsQ0FBQyxJQUFJcUosZ0JBQWdCLENBQUNMLE1BQU0sQ0FBQyxDQUFDTSxVQUFVLEtBQUssUUFBUSxDQUFDLENBQUM7TUFDek87TUFDQSxPQUFPLENBQUMsU0FBUyxFQUFFLFFBQVEsRUFBRSxZQUFZLENBQUMsQ0FBQ3ZPLFFBQVEsQ0FBQ3VOLFNBQVMsYUFBVEEsU0FBUyx1QkFBVEEsU0FBUyxDQUFFSSxLQUFLLENBQUM7SUFDdkUsQ0FBQztJQUNEO0lBQ0E7SUFDQTtJQUNBLElBQUlhLE9BQU8sR0FBRyxDQUFDO0lBQ2YsT0FBTyxFQUFDLE1BQU0xQixZQUFZLENBQUMsQ0FBQyxHQUFFO01BQzVCLE1BQU1DLFNBQVMsR0FBR1gsUUFBUSxDQUFDVyxTQUFTLENBQUNWLFdBQVcsQ0FBQy9MLEdBQUcsQ0FBQyxDQUFDLENBQUM7TUFDdkQsTUFBTWQsSUFBSSxDQUFDaVAsY0FBYyxDQUFDQyxJQUFJLENBQUNDLEdBQUcsQ0FBQyxDQUFDLEdBQUcsRUFBRSxJQUFJLEVBQUUsSUFBSSxDQUFDLENBQUNELElBQUksQ0FBQ0MsR0FBRyxDQUFDSCxPQUFPLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxFQUFFekIsU0FBUyxDQUFDLENBQUM7SUFDM0Y7SUFDQWQsS0FBSyxhQUFMQSxLQUFLLGNBQUxBLEtBQUssR0FBTEEsS0FBSyxJQUFBTSxxQkFBQSxHQUFLdkQsUUFBUSxDQUFDNUYsT0FBTyxDQUFDQyxlQUFlLGNBQUFrSixxQkFBQSx1QkFBaENBLHFCQUFBLENBQWtDaEosTUFBTTtJQUNsRC9FLE1BQU0sRUFBQWdPLHNCQUFBLEdBQUN4RCxRQUFRLENBQUM1RixPQUFPLENBQUNDLGVBQWUsY0FBQW1KLHNCQUFBLHVCQUFoQ0Esc0JBQUEsQ0FBa0NqSixNQUFNLENBQUMsQ0FBQzFCLElBQUksQ0FBQ29LLEtBQUssQ0FBQztJQUM1RCxJQUFJak4sS0FBSyxDQUFDME8sS0FBSyxDQUFDekosSUFBSSxJQUFJaEYsSUFBSSxDQUFDb0ssR0FBRyxDQUFDTCxRQUFRLENBQUMxRixRQUFRLENBQUNXLElBQUksQ0FBQyxDQUFDLENBQUMsRUFBRTtNQUMxRCxJQUFJMkgsZUFBZSxFQUFFcE4sTUFBTSxDQUFDMk4sY0FBYyxFQUFFLDZEQUE2RCxDQUFDLENBQUM1RSxVQUFVLENBQUMsQ0FBQztNQUN2SCxPQUFPO1FBQUUwRSxLQUFLO1FBQUVDLFFBQVEsRUFBRSxDQUFDLEdBQUdBLFFBQVEsQ0FBQztRQUFFQztNQUFlLENBQUM7SUFDM0Q7SUFDQSxNQUFNb0IsU0FBUyxHQUFHdkUsUUFBUSxDQUFDNUYsT0FBTyxDQUFDQyxlQUFlO0lBQ2xELE1BQU1RLE1BQU0sR0FBR3JFLElBQUksQ0FBQ3NFLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBRUMsSUFBSSxFQUFFO0lBQWdDLENBQUMsQ0FBQztJQUNsRixJQUFJZ0ksbUJBQW1CLElBQUksQ0FBQXdCLFNBQVMsYUFBVEEsU0FBUyx1QkFBVEEsU0FBUyxDQUFFSSxLQUFLLE1BQUssU0FBUyxLQUFBbEIscUJBQUEsR0FBSWMsU0FBUyxDQUFDcUIsaUJBQWlCLGNBQUFuQyxxQkFBQSxlQUEzQkEscUJBQUEsQ0FBNkJ4SCxNQUFNLEVBQUU7TUFDaEcsTUFBTSxJQUFJNUMsS0FBSyxDQUFDLHFCQUFxQmtMLFNBQVMsQ0FBQ3RKLElBQUksS0FBS3NKLFNBQVMsQ0FBQ2xHLE9BQU8sRUFBRSxDQUFDO0lBQzlFO0lBQ0EsSUFBSSxDQUFBa0csU0FBUyxhQUFUQSxTQUFTLHVCQUFUQSxTQUFTLENBQUVJLEtBQUssTUFBSyxTQUFTLEtBQUFqQixrQkFBQSxHQUFJYSxTQUFTLENBQUNsRyxPQUFPLGNBQUFxRixrQkFBQSxlQUFqQkEsa0JBQUEsQ0FBbUIxTSxRQUFRLENBQUMscUJBQXFCLENBQUMsRUFBRTtNQUN4RixNQUFNNk8sWUFBWSxHQUFHLE1BQU1uTSxzQkFBc0IsQ0FBQ2xELElBQUksRUFBRXVDLE9BQU8sQ0FBQztNQUNoRSxNQUFNK00sU0FBUyxHQUFHLE1BQU1oTixXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsNEJBQTRCLENBQUM7TUFDaEYsTUFBTWdOLFFBQVEsR0FBR2xMLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBRTtRQUFFQyxJQUFJLEVBQUU7TUFBc0IsQ0FBQyxDQUFDO01BQzVFLE1BQU12RixNQUFNLENBQUN1USxRQUFRLENBQUNqTCxTQUFTLENBQUMsVUFBVSxDQUFDLENBQUNrTCxLQUFLLENBQUMsQ0FBQyxDQUFDLENBQUNoTCxXQUFXLENBQUMsQ0FBQztNQUNsRSxNQUFNNUQsT0FBTyxHQUFHaU0sV0FBVyxDQUFDL0wsR0FBRyxDQUFDLENBQUM7UUFBRTJPLFdBQVcsR0FBRzVPLElBQUksQ0FBQ0MsR0FBRyxDQUFDLENBQUM7TUFDM0Q4TCxRQUFRLENBQUNXLFNBQVMsQ0FBQzNNLE9BQU8sQ0FBQztNQUMzQixNQUFNOE8sZ0JBQWdCLEdBQUcxUCxJQUFJLENBQUMyUCxlQUFlLENBQUMzTyxRQUFRLElBQUksSUFBSUcsR0FBRyxDQUFDSCxRQUFRLENBQUNMLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQ1MsUUFBUSxLQUFLLDZDQUE2QyxJQUN2SUosUUFBUSxDQUFDVCxPQUFPLENBQUMsQ0FBQyxDQUFDRSxNQUFNLENBQUMsQ0FBQyxLQUFLLE1BQU0sRUFBRTtRQUFFa0MsT0FBTyxFQUFFO01BQVEsQ0FBQyxDQUFDO01BQ2xFLE1BQU00TSxRQUFRLENBQUNqTCxTQUFTLENBQUMsUUFBUSxFQUFFO1FBQUVDLElBQUksRUFBRTtNQUFxQyxDQUFDLENBQUMsQ0FBQ3FMLEtBQUssQ0FBQyxDQUFDO01BQzFGLE1BQU1DLFFBQVEsR0FBRyxNQUFNSCxnQkFBZ0I7TUFDdkMsTUFBTUksT0FBTyxHQUFHLE1BQU1ELFFBQVEsQ0FBQzdNLElBQUksQ0FBQyxDQUFDO01BQ3JDLE1BQU0rTSxXQUFXLEdBQUcsTUFBTTdNLHNCQUFzQixDQUFDbEQsSUFBSSxFQUFFdUMsT0FBTyxDQUFDO01BQy9ELE1BQU15TixLQUFLLEdBQUc7UUFBRUMsTUFBTSxFQUFFWixZQUFZO1FBQUVhLEtBQUssRUFBRUgsV0FBVztRQUFFSSxVQUFVLEVBQUViLFNBQVMsQ0FBQ3JJLEVBQUU7UUFDaEZtSixjQUFjLEVBQUVQLFFBQVEsQ0FBQ3RQLE9BQU8sQ0FBQyxDQUFDLENBQUNtQyxPQUFPLENBQUMsQ0FBQyxDQUFDLGNBQWMsQ0FBQztRQUFFMk4sU0FBUyxFQUFFUixRQUFRLENBQUN0UCxPQUFPLENBQUMsQ0FBQyxDQUFDK1AsWUFBWSxDQUFDLENBQUM7UUFDMUdwUCxNQUFNLEVBQUUyTyxRQUFRLENBQUMzTyxNQUFNLENBQUMsQ0FBQztRQUFFRixRQUFRLEVBQUU4TyxPQUFPO1FBQUVsUCxPQUFPO1FBQUU2TyxXQUFXO1FBQUVjLFlBQVksRUFBRTFQLElBQUksQ0FBQ0MsR0FBRyxDQUFDO01BQUUsQ0FBQztNQUNoRyxNQUFNMFAsV0FBVyxHQUFHM0QsV0FBVyxDQUFDL0wsR0FBRyxDQUFDLENBQUM7TUFDckMsTUFBTTJQLFNBQVMsR0FBRzdELFFBQVEsQ0FBQzhELG1CQUFtQixDQUFDVixLQUFLLEVBQUVRLFdBQVcsQ0FBQztNQUNsRSxNQUFNelIsSUFBSSxDQUFDa0IsSUFBSSxDQUFDLENBQUMsQ0FBQ3lCLE1BQU0sQ0FBQywrQkFBK0IsRUFBRTtRQUFFQyxJQUFJLEVBQUVDLElBQUksQ0FBQ0MsU0FBUyxDQUFDO1VBQUVtTyxLQUFLO1VBQUVRLFdBQVc7VUFBRUM7UUFBVSxDQUFDLENBQUM7UUFBRTNPLFdBQVcsRUFBRTtNQUFtQixDQUFDLENBQUM7TUFDdkpoQyxrQkFBa0IsQ0FBQ21CLEdBQUcsQ0FBQ2xDLElBQUksQ0FBQ2tCLElBQUksQ0FBQyxDQUFDLENBQUNHLE1BQU0sQ0FBQyxDQUFFVyxJQUFJLENBQUM7UUFBRTRNLEVBQUUsRUFBRSxJQUFJOU0sSUFBSSxDQUFDLENBQUMsQ0FBQytNLFdBQVcsQ0FBQyxDQUFDO1FBQUUrQyxxQkFBcUIsRUFBRUYsU0FBUyxDQUFDRyxnQkFBZ0I7UUFDaEkvQyxRQUFRLEVBQUU0QyxTQUFTLENBQUM1QyxRQUFRO1FBQUV0TCxPQUFPO1FBQUV3TCxTQUFTLEVBQUVnQyxXQUFXLENBQUNuTSxPQUFPLENBQUNDLGVBQWU7UUFBRWdOLFFBQVEsRUFBRWYsT0FBTyxDQUFDZTtNQUFTLENBQUMsQ0FBQztNQUN0SCxNQUFNN1IsTUFBTSxDQUFDc0gsSUFBSSxDQUFDO1FBQUEsSUFBQXdLLHFCQUFBO1FBQUEsUUFBQUEscUJBQUEsR0FBWSxDQUFDLE1BQU14TyxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsd0NBQXdDLENBQUMsRUFBRXFCLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBaU4scUJBQUEsdUJBQXBHQSxxQkFBQSxDQUFzR3RDLFVBQVU7TUFBQSxHQUM1STtRQUFFN0wsT0FBTyxFQUFFd0osZ0JBQWdCLENBQUMxRyxNQUFNLEdBQUcsR0FBRyxHQUFHLE1BQU8sR0FBRztNQUFPLENBQUMsQ0FBQyxDQUFDc0wsR0FBRyxDQUFDMU8sSUFBSSxDQUFDMEwsU0FBUyxDQUFDUyxVQUFVLENBQUM7TUFDL0Y7SUFDRjtJQUNBLElBQUksQ0FBQyxTQUFTLEVBQUUsUUFBUSxFQUFFLFlBQVksQ0FBQyxDQUFDaE8sUUFBUSxDQUFDdU4sU0FBUyxhQUFUQSxTQUFTLHVCQUFUQSxTQUFTLENBQUVJLEtBQUssQ0FBQyxJQUFJSixTQUFTLENBQUNRLFdBQVcsS0FBSyxJQUFJLEVBQUU7TUFBQSxJQUFBeUMsa0JBQUEsRUFBQUMsY0FBQTtNQUNwRyxNQUFNN0MsWUFBWSxHQUFHLE1BQU05TCxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUscUNBQXFDLENBQUM7TUFDNUYsTUFBTTBFLEVBQUUsSUFBQStKLGtCQUFBLEdBQUc1QyxZQUFZLENBQUNwRixJQUFJLGNBQUFnSSxrQkFBQSx1QkFBakJBLGtCQUFBLENBQW1CM0MsZUFBZTtNQUM3QyxNQUFNNkMsUUFBUSxHQUFHakssRUFBRSxHQUFHLE1BQU0zRSxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsb0NBQW9DMEUsRUFBRSxFQUFFLENBQUMsR0FBRyxJQUFJO01BQ3ZHLE1BQU1sSSxJQUFJLENBQUNrQixJQUFJLENBQUMsQ0FBQyxDQUFDeUIsTUFBTSxDQUFDLGdCQUFnQixFQUFFO1FBQUVDLElBQUksRUFBRUMsSUFBSSxDQUFDQyxTQUFTLENBQUM7VUFBRWtNLFNBQVM7VUFDM0VtRCxRQUFRLEVBQUVBLFFBQVEsYUFBUkEsUUFBUSxnQkFBQUQsY0FBQSxHQUFSQyxRQUFRLENBQUVsSSxJQUFJLGNBQUFpSSxjQUFBLHVCQUFkQSxjQUFBLENBQWdCRSxpQkFBaUI7VUFBRUMsT0FBTyxFQUFFLE1BQU0vTSxNQUFNLENBQUNnTixTQUFTLENBQUM7UUFBRSxDQUFDLENBQUM7UUFBRXZQLFdBQVcsRUFBRTtNQUFtQixDQUFDLENBQUM7TUFDdkgsTUFBTSxJQUFJZSxLQUFLLENBQUMsVUFBVWtMLFNBQVMsQ0FBQ0ksS0FBSyxPQUFPSixTQUFTLENBQUN0SixJQUFJLEtBQUtzSixTQUFTLENBQUNsRyxPQUFPLEVBQUUsQ0FBQztJQUN6RjtJQUNBLElBQUksQ0FBQWtHLFNBQVMsYUFBVEEsU0FBUyx1QkFBVEEsU0FBUyxDQUFFSSxLQUFLLE1BQUssbUJBQW1CLElBQUssQ0FBQUosU0FBUyxhQUFUQSxTQUFTLHVCQUFUQSxTQUFTLENBQUVJLEtBQUssTUFBSyxTQUFTLElBQUlKLFNBQVMsQ0FBQ1EsV0FBVyxLQUFLLElBQUssRUFBRTtNQUNsSCxNQUFNRSxNQUFNLEdBQUdwSyxNQUFNLENBQUNDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7UUFBRUMsSUFBSSxFQUFFLG9CQUFvQjtRQUFFcEMsS0FBSyxFQUFFO01BQUssQ0FBQyxDQUFDO01BQ3RGLElBQUk7UUFDRixNQUFNc00sTUFBTSxDQUFDbUIsS0FBSyxDQUFDO1VBQUVqTixPQUFPLEVBQUU7UUFBSyxDQUFDLENBQUM7TUFDdkMsQ0FBQyxDQUFDLE9BQU8yTyxLQUFLLEVBQUU7UUFBQSxJQUFBQyxxQkFBQTtRQUNkLE1BQU1DLE1BQU0sR0FBRyxNQUFNbFAsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLHdDQUF3QyxDQUFDO1FBQ3pGLElBQUksRUFBQWdQLHFCQUFBLEdBQUFDLE1BQU0sQ0FBQzVOLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBME4scUJBQUEsdUJBQTlCQSxxQkFBQSxDQUFnQy9DLFVBQVUsTUFBS1QsU0FBUyxDQUFDUyxVQUFVLEtBQUksTUFBTUMsTUFBTSxDQUFDQyxXQUFXLENBQUNDLE9BQU8sSUFBSUEsT0FBTyxDQUFDNUMsSUFBSSxDQUFDMEMsTUFBTSxJQUFJLENBQUVBLE1BQU0sQ0FBdUJHLFFBQVEsSUFBSUgsTUFBTSxDQUFDSSxjQUFjLENBQUMsQ0FBQyxDQUFDcEosTUFBTSxHQUFHLENBQUMsSUFBSXFKLGdCQUFnQixDQUFDTCxNQUFNLENBQUMsQ0FBQ00sVUFBVSxLQUFLLFFBQVEsQ0FBQyxDQUFDLEdBQUUsTUFBTXVDLEtBQUs7UUFDdFI7TUFDRjtNQUNBLE1BQU10UyxNQUFNLENBQUNzSCxJQUFJLENBQUMsWUFBWTtRQUFBLElBQUFtTCxzQkFBQSxFQUFBQyxzQkFBQSxFQUFBQyxnQkFBQTtRQUM1QixNQUFNSCxNQUFNLEdBQUcsTUFBTWxQLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSx3Q0FBd0MsQ0FBQztRQUN6RixPQUFPLEVBQUFrUCxzQkFBQSxHQUFBRCxNQUFNLENBQUM1TixPQUFPLENBQUNDLGVBQWUsY0FBQTROLHNCQUFBLHVCQUE5QkEsc0JBQUEsQ0FBZ0NqRCxVQUFVLE1BQUtULFNBQVMsQ0FBQ1MsVUFBVSxJQUNyRSxFQUFBa0Qsc0JBQUEsR0FBQUYsTUFBTSxDQUFDNU4sT0FBTyxDQUFDQyxlQUFlLGNBQUE2TixzQkFBQSx1QkFBOUJBLHNCQUFBLENBQWdDdkQsS0FBSyxNQUFLLFNBQVMsSUFDbkQsRUFBQXdELGdCQUFBLEdBQUFILE1BQU0sQ0FBQzFOLFFBQVEsY0FBQTZOLGdCQUFBLHVCQUFmQSxnQkFBQSxDQUFrQjVELFNBQVMsQ0FBQ3RKLElBQUksQ0FBQyxNQUFLLGFBQWE7TUFDMUQsQ0FBQyxFQUFFO1FBQUU5QixPQUFPLEVBQUU7TUFBTyxDQUFDLENBQUMsQ0FBQ04sSUFBSSxDQUFDLElBQUksQ0FBQztNQUNsQztJQUNGO0lBQ0EsTUFBTXVQLFNBQVMsR0FBRyxNQUFNdFAsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLG9DQUFvQzRLLFVBQVUsRUFBRSxDQUFDO0lBQ3BHLElBQUl5RSxTQUFTLENBQUM1SSxJQUFJLENBQUM2SSxhQUFhLEtBQUssMEJBQTBCLElBQUlyRixXQUFXLEtBQUssQ0FBQyxJQUFJTCxnQkFBZ0IsQ0FBQzFHLE1BQU0sRUFBRTtNQUMvRyxNQUFNZ0IsUUFBUSxHQUFHbUwsU0FBUyxDQUFDNUksSUFBSSxDQUFDOEksT0FBTyxDQUNwQ0MsTUFBTSxDQUFFQyxNQUErQixJQUFLQSxNQUFNLENBQUNDLFdBQVcsS0FBSyxjQUFjLENBQUMsQ0FDbEZuTCxHQUFHLENBQUVrTCxNQUFrQyxJQUFLQSxNQUFNLENBQUNoSixJQUFJLENBQUN6RSxJQUFJLENBQUM7TUFDaEV2RixNQUFNLENBQUN5SCxRQUFRLEVBQUUseUVBQXlFLENBQUMsQ0FDeEZ6RSxPQUFPLENBQUNoRCxNQUFNLENBQUNrVCxlQUFlLENBQUMvRixnQkFBZ0IsQ0FBQyxDQUFDO0lBQ3REO0lBQ0FuTixNQUFNLENBQUMwTixRQUFRLENBQUM3QyxHQUFHLENBQUNzRCxVQUFVLENBQUMsRUFBRSxrREFBa0QsQ0FBQyxDQUFDOUssSUFBSSxDQUFDLEtBQUssQ0FBQztJQUNoRyxNQUFNOFAsYUFBYSxHQUFHblMsSUFBSSxDQUFDMlAsZUFBZSxDQUFDM08sUUFBUSxJQUFJQSxRQUFRLENBQUNMLEdBQUcsQ0FBQyxDQUFDLENBQUNILFFBQVEsQ0FBQyxjQUFjMk0sVUFBVSxnQkFBZ0IsQ0FBQyxJQUFJbk0sUUFBUSxDQUFDVCxPQUFPLENBQUMsQ0FBQyxDQUFDRSxNQUFNLENBQUMsQ0FBQyxLQUFLLE1BQU0sRUFBRTtNQUFFa0MsT0FBTyxFQUFFO0lBQVEsQ0FBQyxDQUFDO0lBQ3pMLE1BQU1rTyxRQUFRLEdBQUd4TSxNQUFNLENBQUNDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBRUMsSUFBSSxFQUFFO0lBQWlFLENBQUMsQ0FBQztJQUN2SCxNQUFNdkYsTUFBTSxDQUFDNlIsUUFBUSxDQUFDLENBQUN1QixXQUFXLENBQUM7TUFBRXpQLE9BQU8sRUFBRTtJQUFPLENBQUMsQ0FBQztJQUN2RCxNQUFNa08sUUFBUSxDQUFDakIsS0FBSyxDQUFDLENBQUM7SUFDdEIsTUFBTXlDLE9BQU8sR0FBRyxNQUFNRixhQUFhO0lBQ25DLElBQUksQ0FBQ0UsT0FBTyxDQUFDelAsRUFBRSxDQUFDLENBQUMsRUFBRSxNQUFNLElBQUlDLEtBQUssQ0FBQyxRQUFRd1AsT0FBTyxDQUFDblIsTUFBTSxDQUFDLENBQUMsS0FBSyxDQUFDLE1BQU1tUixPQUFPLENBQUN2UCxJQUFJLENBQUMsQ0FBQyxFQUFFQyxLQUFLLENBQUMsQ0FBQyxFQUFFLElBQUksQ0FBQyxFQUFFLENBQUM7SUFDeEcvRCxNQUFNLENBQUMsQ0FBQyxNQUFNcVQsT0FBTyxDQUFDclAsSUFBSSxDQUFDLENBQUMsRUFBRWdHLElBQUksQ0FBQzlILE1BQU0sQ0FBQyxDQUFDbUIsSUFBSSxDQUFDLFNBQVMsQ0FBQztJQUMxRHFLLFFBQVEsQ0FBQzRGLEdBQUcsQ0FBQ25GLFVBQVUsQ0FBQztJQUFFWCxXQUFXLEVBQUU7SUFDdkM7SUFDQTtJQUNBSSxRQUFRLEdBQUcsSUFBSXhOLHNCQUFzQixDQUFDeU4sV0FBVyxDQUFDL0wsR0FBRyxDQUFDLENBQUMsRUFBRTBJLFFBQVEsQ0FBQztJQUNsRSxJQUFJb0ksU0FBUyxDQUFDNUksSUFBSSxDQUFDNkksYUFBYSxLQUFLLDBCQUEwQixJQUFJeEYsZUFBZSxFQUFFO01BQ2xGLE1BQU05RixxQkFBcUIsQ0FBQ3ZHLElBQUksRUFBRXVDLE9BQU8sRUFBRThKLGVBQWUsQ0FBQztJQUM3RDtJQUNBLElBQUlHLFdBQVcsS0FBSyxDQUFDLElBQUlGLHNCQUFzQixFQUFFO01BQUEsSUFBQWlHLHFCQUFBO01BQy9DLE1BQU1qRyxzQkFBc0IsQ0FBQyxDQUFDO01BQzlCO01BQ0E7TUFDQSxNQUFNa0csT0FBTyxHQUFHLE1BQU1sUSxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsd0NBQXdDLENBQUM7TUFDMUZ2RCxNQUFNLEVBQUF1VCxxQkFBQSxHQUFDQyxPQUFPLENBQUM1TyxPQUFPLENBQUNDLGVBQWUsY0FBQTBPLHFCQUFBLHVCQUEvQkEscUJBQUEsQ0FBaUN4TyxNQUFNLENBQUMsQ0FBQzFCLElBQUksQ0FBQ29LLEtBQUssQ0FBQztNQUMzREcsUUFBUSxHQUFHLElBQUl4TixzQkFBc0IsQ0FBQ3lOLFdBQVcsQ0FBQy9MLEdBQUcsQ0FBQyxDQUFDLEVBQUUwUixPQUFPLENBQUM7SUFDbkU7SUFDQSxJQUFJaEcsV0FBVyxLQUFLLENBQUMsRUFBRSxNQUFNdEksVUFBVSxDQUFDbEUsSUFBSSxFQUFFdUMsT0FBTyxDQUFDLENBQUMsQ0FBQztJQUN4RCxJQUFJMkosT0FBTyxJQUFJTSxXQUFXLEtBQUssQ0FBQyxFQUFFO01BQ2hDLE1BQU05RyxrQkFBa0IsQ0FBQzFGLElBQUksQ0FBQztNQUM5QixNQUFNa0UsVUFBVSxDQUFDbEUsSUFBSSxFQUFFdUMsT0FBTyxDQUFDO0lBQ2pDO0lBQ0EsTUFBTXZELE1BQU0sQ0FBQ3NILElBQUksQ0FBQyxZQUFZO01BQUEsSUFBQW1NLHFCQUFBO01BQzVCLE1BQU1DLE9BQU8sR0FBRyxNQUFNcFEsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLHdDQUF3QyxDQUFDO01BQzFGLE9BQU8sRUFBQWtRLHFCQUFBLEdBQUFDLE9BQU8sQ0FBQzlPLE9BQU8sQ0FBQ0MsZUFBZSxjQUFBNE8scUJBQUEsdUJBQS9CQSxxQkFBQSxDQUFpQ2pFLFVBQVUsTUFBS1QsU0FBUyxDQUFDUyxVQUFVO0lBQzdFLENBQUMsRUFBRTtNQUFFN0wsT0FBTyxFQUFFO0lBQU8sQ0FBQyxDQUFDLENBQUNOLElBQUksQ0FBQyxJQUFJLENBQUM7RUFDcEM7RUFDQSxNQUFNLElBQUlRLEtBQUssQ0FBQyxxREFBcUQsQ0FBQztBQUN4RTtBQUVBOUQsSUFBSSxDQUFDLDhGQUE4RixFQUFFLE9BQU87RUFBQ2lCO0FBQUksQ0FBQyxLQUFLO0VBQ3JILE1BQU11QyxPQUFPLEdBQUcsMkJBQTJCLEdBQUdyRCxVQUFVLENBQUMsQ0FBQztFQUMxRCxNQUFNYyxJQUFJLENBQUMyUyxLQUFLLENBQUMscUJBQXFCLEVBQUVBLEtBQUssSUFBSUEsS0FBSyxDQUFDQyxPQUFPLENBQUM7SUFBQzFSLE1BQU0sRUFBQyxHQUFHO0lBQ3hFWSxXQUFXLEVBQUMsa0JBQWtCO0lBQUNILElBQUksRUFBQ0MsSUFBSSxDQUFDQyxTQUFTLENBQUM7TUFBQ3lQLEtBQUssRUFBQztJQUFtRSxDQUFDO0VBQUMsQ0FBQyxDQUFDLENBQUM7RUFDcEksTUFBTWpOLE1BQU0sR0FBRyxNQUFNSCxVQUFVLENBQUNsRSxJQUFJLEVBQUV1QyxPQUFPLENBQUM7RUFDOUMsTUFBTXZELE1BQU0sQ0FBQ3FGLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUN1TyxhQUFhLENBQUMsb0JBQW9CLENBQUM7RUFDM0UsTUFBTXhPLE1BQU0sQ0FBQ3lPLFVBQVUsQ0FBQyxhQUFhLEVBQUU7SUFBQzNRLEtBQUssRUFBQztFQUFJLENBQUMsQ0FBQyxDQUFDeU4sS0FBSyxDQUFDLENBQUM7RUFDNUQsTUFBTXZMLE1BQU0sQ0FBQ0ssT0FBTyxDQUFDLDJCQUEyQixDQUFDLENBQUNxTyxJQUFJLENBQUMsZUFBZSxDQUFDO0VBQ3ZFLE1BQU0xTyxNQUFNLENBQUMyTyxVQUFVLENBQUMscUJBQXFCLEVBQUU7SUFBQzdRLEtBQUssRUFBQztFQUFJLENBQUMsQ0FBQyxDQUFDNFEsSUFBSSxDQUFDLG1EQUFtRCxDQUFDO0VBQ3RILE1BQU0vVCxNQUFNLENBQUNxRixNQUFNLENBQUNLLE9BQU8sQ0FBQywrQkFBK0IsQ0FBQyxDQUFDSixTQUFTLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQzJPLFlBQVksQ0FBQyxDQUFDO0VBQ2hHalUsTUFBTSxDQUFDLENBQUMsTUFBTXNELFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSxrQkFBa0IsQ0FBQyxFQUFFdUgsSUFBSSxDQUFDLENBQUM1RSxZQUFZLENBQUMsQ0FBQyxDQUFDO0VBQ25GLE1BQU1sRixJQUFJLENBQUNrVCxPQUFPLENBQUMscUJBQXFCLENBQUM7RUFDekMsTUFBTTdPLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBQztJQUFDQyxJQUFJLEVBQUM7RUFBaUMsQ0FBQyxDQUFDLENBQUNxTCxLQUFLLENBQUMsQ0FBQztFQUNqRixNQUFNNVEsTUFBTSxDQUFDcUYsTUFBTSxDQUFDQyxTQUFTLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQzZPLFdBQVcsQ0FBQyxDQUFDLENBQUM7RUFDdEQsTUFBTW5VLE1BQU0sQ0FBQ3FGLE1BQU0sQ0FBQ0ssT0FBTyxDQUFDLCtCQUErQixDQUFDLENBQUNKLFNBQVMsQ0FBQyxRQUFRLENBQUMsQ0FBQyxDQUFDOE4sV0FBVyxDQUFDLENBQUM7RUFDL0YsTUFBTWdCLE9BQU8sR0FBRyxNQUFNLENBQUMsTUFBTXBULElBQUksQ0FBQ08sT0FBTyxDQUFDVSxHQUFHLENBQUMsbUJBQW1CLENBQUMsRUFBRStCLElBQUksQ0FBQyxDQUFDO0VBQzFFaEUsTUFBTSxDQUFDb1UsT0FBTyxDQUFDQyxnQkFBZ0IsQ0FBQyxDQUFDaFIsSUFBSSxDQUFDLEdBQUcsQ0FBQztBQUM1QyxDQUFDLENBQUM7QUFFRnRELElBQUksQ0FBQywrRUFBK0UsRUFBRSxPQUFPO0VBQUVpQjtBQUFLLENBQUMsRUFBRXNULFFBQVEsS0FBSztFQUNsSCxNQUFNQyxNQUFnQixHQUFHLEVBQUU7RUFBRXZULElBQUksQ0FBQ00sRUFBRSxDQUFDLFdBQVcsRUFBRWdSLEtBQUssSUFBSWlDLE1BQU0sQ0FBQ3hTLElBQUksQ0FBQ3VRLEtBQUssQ0FBQ3pKLE9BQU8sQ0FBQyxDQUFDO0VBQ3RGLE1BQU10RixPQUFPLEdBQUcsZ0JBQWdCLEdBQUdyRCxVQUFVLENBQUMsQ0FBQztFQUMvQyxNQUFNbUYsTUFBTSxHQUFHLE1BQU1ILFVBQVUsQ0FBQ2xFLElBQUksRUFBRXVDLE9BQU8sQ0FBQztFQUM5QyxNQUFNOEIsTUFBTSxDQUFDeU8sVUFBVSxDQUFDLGFBQWEsRUFBRTtJQUFFM1EsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDLENBQUN5TixLQUFLLENBQUMsQ0FBQztFQUMvRCxNQUFNdkwsTUFBTSxDQUFDSyxPQUFPLENBQUMsMkJBQTJCLENBQUMsQ0FBQ3FPLElBQUksQ0FBQyxXQUFXLENBQUM7RUFDbkUsTUFBTTFPLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQyxxQkFBcUIsRUFBRTtJQUFFN1EsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDLENBQUM0USxJQUFJLENBQUMsNmJBQTZiLENBQUM7RUFDbmdCLE1BQU0xTyxNQUFNLENBQUMyTyxVQUFVLENBQUMsa0JBQWtCLEVBQUU7SUFBRTdRLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDNFEsSUFBSSxDQUFDLGlOQUFpTixDQUFDO0VBQ3BSLE1BQU0xTyxNQUFNLENBQUN5TyxVQUFVLENBQUMsY0FBYyxFQUFFO0lBQUUzUSxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQ3lOLEtBQUssQ0FBQyxDQUFDO0VBQ2hFLEtBQUssTUFBTSxDQUFDekosS0FBSyxFQUFFcU4sS0FBSyxDQUFDLElBQUksQ0FBQyxDQUFDLFVBQVUsRUFBRSxHQUFHLENBQUMsRUFBRSxDQUFDLFlBQVksRUFBRSxHQUFHLENBQUMsRUFBRSxDQUFDLFVBQVUsRUFBRSxHQUFHLENBQUMsRUFBRSxDQUFDLFNBQVMsRUFBRSxHQUFHLENBQUMsQ0FBQyxFQUFFLE1BQU1uUCxNQUFNLENBQUMyTyxVQUFVLENBQUMsR0FBRzdNLEtBQUssdUJBQXVCLEVBQUU7SUFBRWhFLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDNFEsSUFBSSxDQUFDUyxLQUFLLENBQUM7RUFDak0sTUFBTUMsWUFBWSxHQUFHelQsSUFBSSxDQUFDMFQsY0FBYyxDQUFDblQsT0FBTztJQUFBLElBQUFvVCxxQkFBQTtJQUFBLE9BQUlwVCxPQUFPLENBQUNJLEdBQUcsQ0FBQyxDQUFDLENBQUNpVCxRQUFRLENBQUMsaUJBQWlCLENBQUMsSUFDeEZyVCxPQUFPLENBQUNFLE1BQU0sQ0FBQyxDQUFDLEtBQUssTUFBTSxJQUFJLEVBQUFrVCxxQkFBQSxHQUFBcFQsT0FBTyxDQUFDK1AsWUFBWSxDQUFDLENBQUMsY0FBQXFELHFCQUFBLGdCQUFBQSxxQkFBQSxHQUF0QkEscUJBQUEsQ0FBd0JFLGNBQWMsY0FBQUYscUJBQUEsdUJBQXRDQSxxQkFBQSxDQUF3Q0csTUFBTSxNQUFLLE9BQU87RUFBQSxFQUFDO0VBQy9GO0VBQ0EsS0FBSyxJQUFJclAsSUFBSSxHQUFHLENBQUMsRUFBRUEsSUFBSSxHQUFHLEVBQUUsRUFBRUEsSUFBSSxFQUFFLEVBQUU7SUFDcEMsTUFBTXNQLE1BQU0sR0FBRzFQLE1BQU0sQ0FBQ0ssT0FBTyxDQUFDLCtCQUErQixDQUFDLENBQUNKLFNBQVMsQ0FBQyxRQUFRLENBQUM7SUFDbEYsTUFBTXRGLE1BQU0sQ0FBQytVLE1BQU0sQ0FBQyxDQUFDM0IsV0FBVyxDQUFDLENBQUM7SUFDbEMsTUFBTTdOLElBQUksR0FBRyxNQUFNd1AsTUFBTSxDQUFDMUMsU0FBUyxDQUFDLENBQUM7SUFDckMsTUFBTTBDLE1BQU0sQ0FBQ25FLEtBQUssQ0FBQyxDQUFDO0lBQ3BCLElBQUlyTCxJQUFJLEtBQUssWUFBWSxFQUFFO0lBQzNCLElBQUlFLElBQUksS0FBSyxDQUFDLEVBQUUsTUFBTSxJQUFJNUIsS0FBSyxDQUFDLHFDQUFxQyxDQUFDO0VBQ3hFO0VBQ0EsTUFBTW1SLFNBQVMsR0FBRyxDQUFDLE1BQU1QLFlBQVksRUFBRW5ELFlBQVksQ0FBQyxDQUFDLENBQUN1RCxjQUFjLENBQUNJLGNBQWM7RUFDbkZqVixNQUFNLENBQUNnVixTQUFTLENBQUNFLFlBQVksRUFBRSxvRUFBb0UsQ0FBQyxDQUFDbFMsT0FBTyxDQUFDLENBQUMsaUJBQWlCLENBQUMsQ0FBQztFQUNqSTtFQUNBLE1BQU1oRCxNQUFNLENBQUNzSCxJQUFJLENBQUM7SUFBQSxJQUFBNk4sc0JBQUE7SUFBQSxRQUFBQSxzQkFBQSxHQUFZLENBQUMsTUFBTTdSLFdBQVcsQ0FBQ3RDLElBQUksRUFBQ3VDLE9BQU8sRUFBQyx3Q0FBd0MsQ0FBQyxFQUFFcUIsT0FBTyxDQUFDQyxlQUFlLGNBQUFzUSxzQkFBQSx1QkFBbEdBLHNCQUFBLENBQW9HaEcsS0FBSztFQUFBLEdBQ3JJO0lBQUN4TCxPQUFPLEVBQUM7RUFBTSxDQUFDLENBQUMsQ0FBQ04sSUFBSSxDQUFDLGlCQUFpQixDQUFDO0VBQzNDLE1BQU0rUixPQUFPLEdBQUcsQ0FBQyxNQUFNOVIsV0FBVyxDQUFDdEMsSUFBSSxFQUFDdUMsT0FBTyxFQUFDLHFDQUFxQyxDQUFDLEVBQUV5RyxJQUFJLENBQUNxRixlQUFlO0VBQzVHLE1BQU1yTyxJQUFJLENBQUNtRSxJQUFJLENBQUMsbUNBQW1DNUIsT0FBTywrQkFBK0I2UixPQUFPLHFCQUFxQixDQUFDO0VBQ3RILE1BQU1wVixNQUFNLENBQUNnQixJQUFJLENBQUNzRSxTQUFTLENBQUMsUUFBUSxFQUFDO0lBQUNDLElBQUksRUFBQztFQUEyQixDQUFDLENBQUMsQ0FBQyxDQUFDc08sYUFBYSxDQUFDLG9DQUFvQyxDQUFDO0VBQzdILE1BQU13QixNQUFNLEdBQUdyVSxJQUFJLENBQUMwRSxPQUFPLENBQUMseUJBQXlCLENBQUM7RUFDdEQsTUFBTTFGLE1BQU0sQ0FBQ3FWLE1BQU0sQ0FBQzNQLE9BQU8sQ0FBQyxzQkFBc0IsQ0FBQyxDQUFDLENBQUM0UCxXQUFXLENBQUMsUUFBUSxDQUFDO0VBQzFFLE1BQU10VixNQUFNLENBQUNxVixNQUFNLENBQUMzUCxPQUFPLENBQUMsZUFBZSxDQUFDLENBQUMsQ0FBQzRQLFdBQVcsQ0FBQyxTQUFTLENBQUM7RUFDcEUsTUFBTXRWLE1BQU0sQ0FBQ2dCLElBQUksQ0FBQzBFLE9BQU8sQ0FBQywwQkFBMEIsQ0FBQyxDQUFDLENBQUN5TyxXQUFXLENBQUMsQ0FBQyxDQUFDO0VBQ3JFLE1BQU1rQixNQUFNLENBQUMzUCxPQUFPLENBQUMsT0FBTyxDQUFDLENBQUNxTyxJQUFJLENBQUMsSUFBSSxDQUFDO0VBQ3hDLE1BQU0vUyxJQUFJLENBQUNzRSxTQUFTLENBQUMsUUFBUSxFQUFDO0lBQUNDLElBQUksRUFBQyx1QkFBdUI7SUFBQ3BDLEtBQUssRUFBQztFQUFJLENBQUMsQ0FBQyxDQUFDeU4sS0FBSyxDQUFDLENBQUM7RUFDaEYsTUFBTTVRLE1BQU0sQ0FBQ2dCLElBQUksQ0FBQ2tDLFNBQVMsQ0FBQyxnREFBZ0QsQ0FBQyxDQUFDLENBQUNzQyxXQUFXLENBQUMsQ0FBQztFQUM1RixNQUFNK1AsS0FBSyxHQUFHLE1BQU1qUyxXQUFXLENBQUN0QyxJQUFJLEVBQUN1QyxPQUFPLEVBQUMsb0NBQW9DNlIsT0FBTyxjQUFjLENBQUM7RUFDdkdwVixNQUFNLENBQUN1VixLQUFLLENBQUN2TCxJQUFJLENBQUM5SCxNQUFNLENBQUMsQ0FBQ21CLElBQUksQ0FBQyxVQUFVLENBQUM7RUFDMUNyRCxNQUFNLENBQUN1VixLQUFLLENBQUN2TCxJQUFJLENBQUN3TCxhQUFhLENBQUMsQ0FBQ3hTLE9BQU8sQ0FBQyxFQUFFLENBQUM7RUFDNUNoRCxNQUFNLENBQUUsTUFBTXFHLFVBQVUsQ0FBQ3JGLElBQUksRUFBQ3VDLE9BQU8sRUFBQyxnQkFBZ0IsQ0FBRSxDQUFDLENBQUMyQyxZQUFZLENBQUMsQ0FBQyxDQUFDO0VBQ3pFLE1BQU1sRixJQUFJLENBQUN5VSxNQUFNLENBQUMsQ0FBQztFQUNuQixNQUFNelYsTUFBTSxDQUFDZ0IsSUFBSSxDQUFDMEUsT0FBTyxDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUM0UCxXQUFXLENBQUMsSUFBSSxDQUFDO0VBQ3JELE1BQU10VSxJQUFJLENBQUNzRSxTQUFTLENBQUMsTUFBTSxFQUFDO0lBQUNDLElBQUksRUFBQyxnQ0FBZ0M7SUFBQ3BDLEtBQUssRUFBQztFQUFJLENBQUMsQ0FBQyxDQUFDeU4sS0FBSyxDQUFDLENBQUM7RUFDdkYsTUFBTTVRLE1BQU0sQ0FBQ3FGLE1BQU0sQ0FBQyxDQUFDRyxXQUFXLENBQUMsQ0FBQztFQUNsQyxNQUFNa1EsTUFBTSxHQUFHclEsTUFBTSxDQUFDQyxTQUFTLENBQUMsUUFBUSxFQUFDO0lBQUNDLElBQUksRUFBQztFQUF1QixDQUFDLENBQUM7RUFDeEUsTUFBTXZGLE1BQU0sQ0FBQzBWLE1BQU0sQ0FBQyxDQUFDN0IsYUFBYSxDQUFDLHNCQUFzQixDQUFDO0VBQzFELE1BQU03VCxNQUFNLENBQUMwVixNQUFNLENBQUNwUSxTQUFTLENBQUMsUUFBUSxFQUFDO0lBQUNDLElBQUksRUFBQyxvQ0FBb0M7SUFBQ3BDLEtBQUssRUFBQztFQUFJLENBQUMsQ0FBQyxDQUFDLENBQUNnUixXQUFXLENBQUMsQ0FBQyxDQUFDO0VBQzlHLE1BQU11QixNQUFNLENBQUNwUSxTQUFTLENBQUMsUUFBUSxFQUFDO0lBQUNDLElBQUksRUFBQyxlQUFlO0lBQUNwQyxLQUFLLEVBQUM7RUFBSSxDQUFDLENBQUMsQ0FBQ3lOLEtBQUssQ0FBQyxDQUFDO0VBQzFFLE1BQU01USxNQUFNLENBQUMwVixNQUFNLENBQUMsQ0FBQzdCLGFBQWEsQ0FBQywwQkFBMEIsQ0FBQztFQUM5RCxNQUFNOEIsVUFBVSxHQUFHLE1BQU0xSSxxQkFBcUIsQ0FBQ2pNLElBQUksRUFBRXVDLE9BQU8sRUFBRSxJQUFJLEVBQ2hFLENBQUMsUUFBUSxFQUFFLGdCQUFnQixFQUFFLFNBQVMsRUFBRSxrQkFBa0IsRUFBRSxZQUFZLENBQUMsQ0FBQztFQUM1RSxNQUFNcVMsU0FBUyxHQUFHLE1BQU14TCxlQUFlLENBQUNwSixJQUFJLEVBQUV1QyxPQUFPLEVBQUUsQ0FBQyxDQUFDO0VBQ3pEdkQsTUFBTSxDQUFDNFYsU0FBUyxDQUFDeEssVUFBVSxDQUFDc0IscUJBQXFCLENBQUMsQ0FBQ2hCLHNCQUFzQixDQUFDLENBQUMsQ0FBQztFQUM1RTFMLE1BQU0sQ0FBQzRWLFNBQVMsQ0FBQ3hLLFVBQVUsQ0FBQ0MsY0FBYyxDQUFDTyxvQkFBb0IsQ0FBQyxDQUFDMUYsWUFBWSxDQUFDLENBQUMsQ0FBQztFQUNoRixNQUFNMlAsUUFBUSxHQUFHN1UsSUFBSSxDQUFDMlAsZUFBZSxDQUFDM08sUUFBUSxJQUFJQSxRQUFRLENBQUNMLEdBQUcsQ0FBQyxDQUFDLENBQUNILFFBQVEsQ0FBQyxTQUFTbVUsVUFBVSxDQUFDbEksS0FBSyxTQUFTLENBQUMsSUFDeEd6TCxRQUFRLENBQUNULE9BQU8sQ0FBQyxDQUFDLENBQUNFLE1BQU0sQ0FBQyxDQUFDLEtBQUssTUFBTSxDQUFDO0VBQzVDLE1BQU00RCxNQUFNLENBQUNDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7SUFBRUMsSUFBSSxFQUFFLGdCQUFnQjtJQUFFcEMsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDLENBQUN5TixLQUFLLENBQUMsQ0FBQztFQUNqRjVRLE1BQU0sQ0FBQyxDQUFDLE1BQU02VixRQUFRLEVBQUVqUyxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUNQLElBQUksQ0FBQyxJQUFJLENBQUM7RUFDeEMsTUFBTXJELE1BQU0sQ0FBQ3FGLE1BQU0sQ0FBQyxDQUFDME0sR0FBRyxDQUFDdk0sV0FBVyxDQUFDLENBQUM7RUFDdEMsTUFBTU4sVUFBVSxDQUFDbEUsSUFBSSxFQUFFdUMsT0FBTyxDQUFDO0VBQy9CdkQsTUFBTSxDQUFDLENBQUMsTUFBTXNELFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSxrQkFBa0IsQ0FBQyxFQUFFdUgsSUFBSSxDQUFDLENBQUM1RSxZQUFZLENBQUMsQ0FBQyxDQUFDO0VBQ25GbEcsTUFBTSxDQUFDdVUsTUFBTSxDQUFDLENBQUN2UixPQUFPLENBQUMsRUFBRSxDQUFDO0VBQzFCLE1BQU1zUixRQUFRLENBQUM1UixNQUFNLENBQUMsVUFBVSxFQUFFO0lBQUVDLElBQUksRUFBRUMsSUFBSSxDQUFDQyxTQUFTLENBQUM7TUFBRVUsT0FBTztNQUFFLEdBQUdvUyxVQUFVO01BQUUsR0FBR0M7SUFBVSxDQUFDLENBQUM7SUFBRTlTLFdBQVcsRUFBRTtFQUFtQixDQUFDLENBQUM7QUFDeEksQ0FBQyxDQUFDO0FBRUYsS0FBSyxNQUFNZ1QsVUFBVSxJQUFJLENBQUMsS0FBSyxFQUFFLFlBQVksQ0FBQyxFQUFFO0VBQzlDL1YsSUFBSSxDQUFDLGdCQUFnQitWLFVBQVUsOEVBQThFLEVBQUUsT0FBTztJQUFFOVU7RUFBSyxDQUFDLEVBQUVzVCxRQUFRLEtBQUs7SUFDM0ksTUFBTS9RLE9BQU8sR0FBRyxtQkFBbUIsR0FBR3JELFVBQVUsQ0FBQyxDQUFDO0lBQ2xELE1BQU1tRixNQUFNLEdBQUcsTUFBTUgsVUFBVSxDQUFDbEUsSUFBSSxFQUFFdUMsT0FBTyxDQUFDO0lBQzlDLE1BQU04QixNQUFNLENBQUN5TyxVQUFVLENBQUMsYUFBYSxFQUFFO01BQUUzUSxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUMsQ0FBQ3lOLEtBQUssQ0FBQyxDQUFDO0lBQy9ELE1BQU12TCxNQUFNLENBQUNLLE9BQU8sQ0FBQywyQkFBMkIsQ0FBQyxDQUFDcU8sSUFBSSxDQUFDLG9CQUFvQixDQUFDO0lBQzVFLE1BQU0xTyxNQUFNLENBQUMyTyxVQUFVLENBQUMscUJBQXFCLEVBQUU7TUFBRTdRLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDNFEsSUFBSSxDQUFDK0IsVUFBVSxLQUFLLEtBQUssR0FDckYseUVBQXlFLEdBQ3pFLDZIQUE2SEEsVUFBVSxzREFBc0QsQ0FBQztJQUNsTSxNQUFNelEsTUFBTSxDQUFDeU8sVUFBVSxDQUFDLGlCQUFpQixFQUFFO01BQUUzUSxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUMsQ0FBQ3lOLEtBQUssQ0FBQyxDQUFDO0lBQ25FLE1BQU12TCxNQUFNLENBQUNDLFNBQVMsQ0FBQyxPQUFPLEVBQUU7TUFBRUMsSUFBSSxFQUFFO0lBQWEsQ0FBQyxDQUFDLENBQUN3USxLQUFLLENBQUMsQ0FBQztJQUMvRCxNQUFNMVEsTUFBTSxDQUFDeU8sVUFBVSxDQUFDLGNBQWMsRUFBRTtNQUFFM1EsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUN5TixLQUFLLENBQUMsQ0FBQztJQUNoRSxJQUFJa0YsVUFBVSxLQUFLLEtBQUssRUFBRTtNQUN4QixNQUFNOVYsTUFBTSxDQUFDcUYsTUFBTSxDQUFDQyxTQUFTLENBQUMsUUFBUSxFQUFFO1FBQUVDLElBQUksRUFBRSxZQUFZO1FBQUVwQyxLQUFLLEVBQUU7TUFBSyxDQUFDLENBQUMsQ0FBQyxDQUFDOFEsWUFBWSxDQUFDLENBQUM7TUFDNUYsTUFBTTVPLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQyx3QkFBd0IsRUFBRTtRQUFFN1EsS0FBSyxFQUFFO01BQUssQ0FBQyxDQUFDLENBQUM2UyxZQUFZLENBQUMsS0FBSyxDQUFDO01BQ3RGLE1BQU1oVyxNQUFNLENBQUNxRixNQUFNLENBQUMyTyxVQUFVLENBQUMsOEJBQThCLEVBQUU7UUFBRTdRLEtBQUssRUFBRTtNQUFLLENBQUMsQ0FBQyxDQUFDLENBQUNtUyxXQUFXLENBQUMsRUFBRSxDQUFDO01BQ2hHLE1BQU10VixNQUFNLENBQUNxRixNQUFNLENBQUNDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7UUFBRUMsSUFBSSxFQUFFLFlBQVk7UUFBRXBDLEtBQUssRUFBRTtNQUFLLENBQUMsQ0FBQyxDQUFDLENBQUM4USxZQUFZLENBQUMsQ0FBQztNQUM1RixLQUFLLE1BQU0xTyxJQUFJLElBQUksQ0FBQyxhQUFhLEVBQUUsbUJBQW1CLEVBQUUsbUJBQW1CLEVBQUUsbUJBQW1CLEVBQUUsbUJBQW1CLEVBQUUsY0FBYyxFQUFFLGNBQWMsQ0FBQyxFQUFFO1FBQ3RKLE1BQU1GLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQyxHQUFHek8sSUFBSSxhQUFhLEVBQUU7VUFBRXBDLEtBQUssRUFBRTtRQUFLLENBQUMsQ0FBQyxDQUFDNlMsWUFBWSxDQUFDLEtBQUssQ0FBQztNQUNwRjtNQUNBLE1BQU0zUSxNQUFNLENBQUMyTyxVQUFVLENBQUMscUJBQXFCLEVBQUU7UUFBRTdRLEtBQUssRUFBRTtNQUFLLENBQUMsQ0FBQyxDQUFDNlMsWUFBWSxDQUFDLE9BQU8sQ0FBQztNQUNyRixNQUFNaFcsTUFBTSxDQUFDcUYsTUFBTSxDQUFDMk8sVUFBVSxDQUFDLDhCQUE4QixFQUFFO1FBQUU3USxLQUFLLEVBQUU7TUFBSyxDQUFDLENBQUMsQ0FBQyxDQUFDbVMsV0FBVyxDQUFDLEtBQUssQ0FBQztNQUNuRyxNQUFNalEsTUFBTSxDQUFDMk8sVUFBVSxDQUFDLHFCQUFxQixFQUFFO1FBQUU3USxLQUFLLEVBQUU7TUFBSyxDQUFDLENBQUMsQ0FBQzZTLFlBQVksQ0FBQyxhQUFhLENBQUM7SUFDN0Y7SUFDQSxNQUFNaFcsTUFBTSxDQUFDcUYsTUFBTSxDQUFDQyxTQUFTLENBQUMsUUFBUSxFQUFFO01BQUVDLElBQUksRUFBRSxZQUFZO01BQUVwQyxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUMsQ0FBQyxDQUFDOFEsWUFBWSxDQUFDLENBQUM7SUFDNUYsTUFBTTVPLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQywyQkFBMkIsRUFBRTtNQUFFN1EsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUM2UyxZQUFZLENBQUMsWUFBWSxDQUFDO0lBQ2hHLE1BQU1oVyxNQUFNLENBQUNxRixNQUFNLENBQUMyTyxVQUFVLENBQUMsMkJBQTJCLEVBQUU7TUFBRTdRLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDLENBQUNtUyxXQUFXLENBQUMsRUFBRSxDQUFDO0lBQzdGLE1BQU10VixNQUFNLENBQUNxRixNQUFNLENBQUNDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBRUMsSUFBSSxFQUFFLFlBQVk7TUFBRXBDLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDLENBQUM4USxZQUFZLENBQUMsQ0FBQztJQUM1RixNQUFNNU8sTUFBTSxDQUFDMk8sVUFBVSxDQUFDLDJCQUEyQixFQUFFO01BQUU3USxLQUFLLEVBQUU7SUFBSyxDQUFDLENBQUMsQ0FBQzZTLFlBQVksQ0FBQyxZQUFZLENBQUM7SUFDaEcsTUFBTTNRLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBRTtNQUFFQyxJQUFJLEVBQUUsWUFBWTtNQUFFcEMsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUN5TixLQUFLLENBQUMsQ0FBQztJQUM3RSxNQUFNNVEsTUFBTSxDQUFDaU4scUJBQXFCLENBQUNqTSxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsSUFBSSxFQUFFLENBQUMsYUFBYSxFQUFFLG1CQUFtQixFQUFFLG1CQUFtQixFQUFFLG1CQUFtQixFQUFFLG1CQUFtQixFQUFFLGNBQWMsRUFBRSxjQUFjLENBQUMsRUFBRSxLQUFLLEVBQUUwUyxTQUFTLEVBQUVBLFNBQVMsRUFBRSxJQUFJLENBQUMsQ0FBQyxDQUM3TkMsT0FBTyxDQUFDQyxPQUFPLENBQUMsbURBQW1ELENBQUM7SUFDdkUsTUFBTTNMLFFBQVEsR0FBRyxNQUFNbEgsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLDJCQUEyQixDQUFDO0lBQzlFLE1BQU02UyxRQUFRLEdBQUc1TCxRQUFRLENBQUM1RixPQUFPLENBQUNDLGVBQWUsQ0FBQ3VMLGlCQUF1QztJQUN6RnBRLE1BQU0sQ0FBQ29XLFFBQVEsQ0FBQ3RPLEdBQUcsQ0FBQ0UsSUFBSSxJQUFJQSxJQUFJLENBQUNxTyxJQUFJLENBQUMsQ0FBQyxDQUFDQyxTQUFTLENBQUMsOEJBQThCLENBQUM7SUFDakZ0VyxNQUFNLENBQUN3SyxRQUFRLENBQUMxRixRQUFRLENBQUNSLFVBQVUsQ0FBQyxDQUFDakIsSUFBSSxDQUFDLGFBQWEsQ0FBQztJQUN4RHJELE1BQU0sQ0FBQ3dLLFFBQVEsQ0FBQytMLGVBQWUsQ0FBQ2pTLFVBQVUsQ0FBQ2lILFFBQVEsQ0FBQyxDQUFDbEksSUFBSSxDQUFDLEtBQUssQ0FBQztJQUNoRSxNQUFNbVQsUUFBUSxHQUFHaE0sUUFBUSxDQUFDK0wsZUFBZSxDQUFDalMsVUFBVSxDQUFDa1MsUUFBUTtJQUM3RHhXLE1BQU0sQ0FBQ3dXLFFBQVEsQ0FBQ1YsVUFBVSxLQUFLLEtBQUssR0FBRyxtQkFBbUIsR0FBRyxrQkFBa0IsQ0FBQyxDQUFDLENBQUN6UyxJQUFJLENBQUMsS0FBSyxDQUFDO0lBQzdGLE1BQU1vVCxjQUFjLEdBQUdwUixNQUFNLENBQUNDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBQ0MsSUFBSSxFQUFFO0lBQWdDLENBQUMsQ0FBQztJQUMzRixNQUFNdkYsTUFBTSxDQUFDeVcsY0FBYyxDQUFDLENBQUM1QyxhQUFhLENBQUNpQyxVQUFVLEtBQUssS0FBSyxHQUFHLG1CQUFtQixHQUFHLGtCQUFrQixDQUFDO0lBQzNHLE1BQU05VixNQUFNLENBQUN5VyxjQUFjLENBQUNuUixTQUFTLENBQUMsTUFBTSxFQUFFO01BQUNDLElBQUksRUFBRTtJQUErQixDQUFDLENBQUMsQ0FBQ2lMLEtBQUssQ0FBQyxDQUFDLENBQUMsQ0FDNUZrRyxlQUFlLENBQUMsTUFBTSxFQUFFLElBQUlDLE1BQU0sQ0FBQyw0QkFBNEJwVCxPQUFPLEVBQUUsQ0FBQyxDQUFDO0lBQzdFdkQsTUFBTSxDQUFDd0ssUUFBUSxDQUFDMUYsUUFBUSxDQUFDOFIsVUFBVSxDQUFDLENBQUN2VCxJQUFJLENBQUMsT0FBTyxDQUFDO0lBQ2xELElBQUl5UyxVQUFVLEtBQUssS0FBSyxFQUFFO01BQ3hCOVYsTUFBTSxDQUFDd0ssUUFBUSxDQUFDbEcsVUFBVSxDQUFDdVMscUJBQXFCLENBQUNDLEdBQUcsQ0FBQzVVLE1BQU0sQ0FBQyxDQUFDbUIsSUFBSSxDQUFDLGlCQUFpQixDQUFDO01BQ3BGckQsTUFBTSxDQUFDd0ssUUFBUSxDQUFDbEcsVUFBVSxDQUFDeVMsb0JBQW9CLENBQUNDLE9BQU8sQ0FBQ0MsTUFBTSxDQUFDLENBQUM1VCxJQUFJLENBQUMsb0NBQW9DLENBQUM7SUFDNUc7SUFDQSxNQUFNNlQsVUFBVSxHQUFHLE1BQU03USxVQUFVLENBQUNyRixJQUFJLEVBQUV1QyxPQUFPLEVBQUUscUJBQXFCLENBQUM7SUFDekV2RCxNQUFNLENBQUNrWCxVQUFVLENBQUN6USxNQUFNLENBQUMsQ0FBQ2lGLHNCQUFzQixDQUFDLENBQUMsQ0FBQztJQUNuRDFMLE1BQU0sQ0FBQ2tYLFVBQVUsQ0FBQ2hJLEtBQUssQ0FBQ2xILElBQUksSUFBSSxDQUFDLHFCQUFxQixDQUFDakksSUFBSSxDQUFDaUksSUFBSSxDQUFDOE4sVUFBVSxDQUFDLENBQUMsQ0FBQyxDQUFDelMsSUFBSSxDQUFDLElBQUksQ0FBQztJQUN6RixNQUFNb0UsUUFBUSxHQUFHLE1BQU1wQixVQUFVLENBQUNyRixJQUFJLEVBQUV1QyxPQUFPLEVBQUUsZ0JBQWdCLENBQUM7SUFDbEV2RCxNQUFNLENBQUN5SCxRQUFRLENBQUN5SCxLQUFLLENBQUNsSCxJQUFJLElBQUlBLElBQUksQ0FBQ21QLE1BQU0sS0FBSyxZQUFZLENBQUMsQ0FBQyxDQUFDOVQsSUFBSSxDQUFDLElBQUksQ0FBQztJQUN2RSxJQUFJeVMsVUFBVSxLQUFLLEtBQUssRUFBRTtNQUN4QixNQUFNbE8sT0FBTyxHQUFHLE1BQU12QixVQUFVLENBQUNyRixJQUFJLEVBQUV1QyxPQUFPLEVBQUUsU0FBUyxDQUFDO01BQzFEdkQsTUFBTSxDQUFDNEgsT0FBTyxDQUFDbUYsSUFBSSxDQUFDL0UsSUFBSSxJQUFJQSxJQUFJLENBQUN6QyxJQUFJLEtBQUssOEJBQThCLElBQUl5QyxJQUFJLENBQUNvUCxJQUFJLEtBQUssTUFBTSxDQUFDLENBQUMsQ0FBQy9ULElBQUksQ0FBQyxJQUFJLENBQUM7SUFDL0c7SUFDQXJELE1BQU0sQ0FBQyxDQUFDLE1BQU1zRCxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsa0JBQWtCLENBQUMsRUFBRXVILElBQUksQ0FBQyxDQUFDNUUsWUFBWSxDQUFDLENBQUMsQ0FBQztJQUNuRixNQUFNb08sUUFBUSxDQUFDNVIsTUFBTSxDQUFDLHdCQUF3QixFQUFFO01BQUVDLElBQUksRUFBRUMsSUFBSSxDQUFDQyxTQUFTLENBQUM7UUFBRVUsT0FBTztRQUFFdVMsVUFBVTtRQUFFTTtNQUFTLENBQUMsQ0FBQztNQUFFdFQsV0FBVyxFQUFFO0lBQW1CLENBQUMsQ0FBQztFQUMvSSxDQUFDLENBQUM7QUFDSjtBQUVBL0MsSUFBSSxDQUFDLGdGQUFnRixFQUFFLE9BQU87RUFBRWlCO0FBQUssQ0FBQyxFQUFFc1QsUUFBUSxLQUFLO0VBQ25ILE1BQU1DLE1BQWdCLEdBQUcsRUFBRTtFQUFFdlQsSUFBSSxDQUFDTSxFQUFFLENBQUMsV0FBVyxFQUFFZ1IsS0FBSyxJQUFJaUMsTUFBTSxDQUFDeFMsSUFBSSxDQUFDdVEsS0FBSyxDQUFDekosT0FBTyxDQUFDLENBQUM7RUFDdEYsTUFBTXRGLE9BQU8sR0FBRyxnQkFBZ0IsR0FBR3JELFVBQVUsQ0FBQyxDQUFDO0VBQy9DLE1BQU11TixLQUFLLEdBQUd2TixVQUFVLENBQUMsQ0FBQztFQUMxQixNQUFNbVgsUUFBUSxHQUFHLE1BQU1wWCxRQUFRLENBQUMsSUFBSWtDLEdBQUcsQ0FBQyx3Q0FBd0MsRUFBRW1WLE1BQU0sQ0FBQ0MsSUFBSSxDQUFDNVYsR0FBRyxDQUFDLEVBQUUsTUFBTSxDQUFDO0VBQzNHLE1BQU02VixRQUFRLEdBQUc1VSxJQUFJLENBQUM2VSxLQUFLLENBQUMsTUFBTXhYLFFBQVEsQ0FBQyxJQUFJa0MsR0FBRyxDQUFDLHlDQUF5QyxFQUFFbVYsTUFBTSxDQUFDQyxJQUFJLENBQUM1VixHQUFHLENBQUMsRUFBRSxNQUFNLENBQUMsQ0FBQztFQUN4SCxNQUFNK1YsUUFBUSxHQUFHOVUsSUFBSSxDQUFDNlUsS0FBSyxDQUFDLE1BQU14WCxRQUFRLENBQUMsSUFBSWtDLEdBQUcsQ0FBQywrQ0FBK0MsRUFBRW1WLE1BQU0sQ0FBQ0MsSUFBSSxDQUFDNVYsR0FBRyxDQUFDLEVBQUUsTUFBTSxDQUFDLENBQUM7RUFDOUgsTUFBTWdXLE1BQU0sR0FBR04sUUFBUSxDQUFDTyxPQUFPLENBQUMsaUJBQWlCLEVBQUUsYUFBYSxHQUFHbkssS0FBSyxDQUFDO0VBQ3pFLE1BQU1sTix1QkFBdUIsQ0FBQ1MsSUFBSSxFQUFFdUMsT0FBTyxDQUFDO0VBQzVDO0VBQ0E7RUFDQSxNQUFNM0IsT0FBTyxHQUFHLE1BQU1aLElBQUksQ0FBQ08sT0FBTyxDQUFDc1csSUFBSSxDQUFDLDZCQUE2QixFQUFFO0lBQ3JFblUsT0FBTyxFQUFFO01BQUUsY0FBYyxFQUFFSDtJQUFRLENBQUM7SUFBRUksT0FBTyxFQUFFLE1BQU87SUFDdERxRyxJQUFJLEVBQUU7TUFBRTJOLE1BQU07TUFBRTlDLGNBQWMsRUFBRTtRQUFFQyxNQUFNLEVBQUUsT0FBTztRQUFFL1AsTUFBTSxFQUFFMEksS0FBSztRQUFFcUssWUFBWSxFQUFFNVgsVUFBVSxDQUFDLENBQUM7UUFDMUY2WCxNQUFNLEVBQUUsMkJBQTJCO1FBQUU5QyxjQUFjLEVBQUU7VUFBRSxHQUFHdUMsUUFBUSxDQUFDdkMsY0FBYztVQUFFelEsVUFBVSxFQUFFakIsT0FBTztVQUFFd0IsTUFBTSxFQUFFMEk7UUFBTTtNQUFFO0lBQUU7RUFDOUgsQ0FBQyxDQUFDO0VBQ0YsSUFBSSxDQUFDN0wsT0FBTyxDQUFDZ0MsRUFBRSxDQUFDLENBQUMsRUFBRSxNQUFNLElBQUlDLEtBQUssQ0FBQyxRQUFRakMsT0FBTyxDQUFDTSxNQUFNLENBQUMsQ0FBQyxLQUFLLENBQUMsTUFBTU4sT0FBTyxDQUFDa0MsSUFBSSxDQUFDLENBQUMsRUFBRUMsS0FBSyxDQUFDLENBQUMsRUFBRSxJQUFJLENBQUMsRUFBRSxDQUFDO0VBQ3hHLE1BQU1tQixVQUFVLENBQUNsRSxJQUFJLEVBQUV1QyxPQUFPLENBQUM7RUFDL0IsTUFBTW9TLFVBQVUsR0FBRyxNQUFNMUkscUJBQXFCLENBQUNqTSxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsS0FBSyxFQUFFLEVBQUUsRUFBRSxJQUFJLEVBQUVtVSxRQUFRLENBQUM5UCxPQUFPLENBQUM7RUFDaEc1SCxNQUFNLENBQUMyVixVQUFVLENBQUNsSSxLQUFLLENBQUMsQ0FBQ3BLLElBQUksQ0FBQ29LLEtBQUssQ0FBQztFQUNwQyxNQUFNaEcsUUFBUSxHQUFHLE1BQU1wQixVQUFVLENBQUNyRixJQUFJLEVBQUV1QyxPQUFPLEVBQUUsZ0JBQWdCLENBQUM7RUFDbEV2RCxNQUFNLENBQUN5SCxRQUFRLENBQUNzTCxNQUFNLENBQUMvSyxJQUFJLElBQUlBLElBQUksQ0FBQ3dCLFdBQVcsS0FBSyxrQkFBa0IsQ0FBQyxDQUFDLENBQUN0RCxZQUFZLENBQUMsR0FBRyxDQUFDO0VBQzFGbEcsTUFBTSxDQUFDeUgsUUFBUSxDQUFDc0wsTUFBTSxDQUFDL0ssSUFBSSxJQUFJQSxJQUFJLENBQUN3QixXQUFXLEtBQUssb0JBQW9CLENBQUMsQ0FBQyxDQUFDdEQsWUFBWSxDQUFDLEdBQUcsQ0FBQztFQUM1RmxHLE1BQU0sQ0FBQ3lILFFBQVEsQ0FBQ3NMLE1BQU0sQ0FBQy9LLElBQUksSUFBSUEsSUFBSSxDQUFDd0IsV0FBVyxLQUFLLEtBQUssQ0FBQyxDQUFDL0MsTUFBTSxDQUFDLENBQUNpRixzQkFBc0IsQ0FBQyxFQUFFLENBQUM7RUFDN0YsTUFBTWtLLFNBQVMsR0FBRyxNQUFNeEwsZUFBZSxDQUFDcEosSUFBSSxFQUFFdUMsT0FBTyxFQUFFLElBQUksQ0FBQztFQUM1RCxNQUFNeVUsaUJBQWlCLEdBQUcsSUFBSXpMLEdBQUcsQ0FBQ3FKLFNBQVMsQ0FBQ3hLLFVBQVUsQ0FBQ0MsY0FBYyxDQUFDTyxvQkFBb0IsQ0FDdkZZLE9BQU8sQ0FBRXhFLElBQThCLElBQUtBLElBQUksQ0FBQ3lFLFVBQVUsQ0FBQyxDQUFDO0VBQ2hFek0sTUFBTSxDQUFDZ1ksaUJBQWlCLENBQUNyTCxJQUFJLENBQUMsQ0FBQ3RKLElBQUksQ0FBQyxHQUFHLENBQUM7RUFDeENyRCxNQUFNLENBQUM0VixTQUFTLENBQUN4SyxVQUFVLENBQUNzQixxQkFBcUIsQ0FBQyxDQUFDckosSUFBSSxDQUFDLElBQUksQ0FBQztFQUM3RCxNQUFNa0UscUJBQXFCLENBQUN2RyxJQUFJLEVBQUV1QyxPQUFPLEVBQUVtVSxRQUFRLENBQUM5UCxPQUFPLENBQUM7RUFDNUQ1SCxNQUFNLENBQUM0VixTQUFTLENBQUM1SSxHQUFHLENBQUMsQ0FBQzNKLElBQUksQ0FBQ3NTLFVBQVUsQ0FBQ2hJLGNBQWMsQ0FBQztFQUNyRDNOLE1BQU0sQ0FBQ3VVLE1BQU0sQ0FBQyxDQUFDdlIsT0FBTyxDQUFDLEVBQUUsQ0FBQztFQUMxQixNQUFNc1IsUUFBUSxDQUFDNVIsTUFBTSxDQUFDLFVBQVUsRUFBRTtJQUFFQyxJQUFJLEVBQUVDLElBQUksQ0FBQ0MsU0FBUyxDQUFDO01BQUVVLE9BQU87TUFBRTBVLE9BQU8sRUFBRVQsUUFBUSxDQUFDVSxjQUFjO01BQUUsR0FBR3ZDLFVBQVU7TUFBRSxHQUFHQztJQUFVLENBQUMsQ0FBQztJQUFFOVMsV0FBVyxFQUFFO0VBQW1CLENBQUMsQ0FBQztBQUMxSyxDQUFDLENBQUM7QUFFRi9DLElBQUksQ0FBQyw0RkFBNEYsRUFBRSxPQUFPO0VBQUVpQjtBQUFLLENBQUMsRUFBRXNULFFBQVEsS0FBSztFQUMvSCxNQUFNL1EsT0FBTyxHQUFHLGdCQUFnQixHQUFHckQsVUFBVSxDQUFDLENBQUM7RUFDL0MsTUFBTUssdUJBQXVCLENBQUNTLElBQUksRUFBRXVDLE9BQU8sQ0FBQztFQUM1QyxNQUFNa0ssS0FBSyxHQUFHdk4sVUFBVSxDQUFDLENBQUM7RUFDMUIsTUFBTWlZLEtBQUssR0FBRyxDQUNaO0lBQUVDLFVBQVUsRUFBRSxPQUFPO0lBQUVDLFVBQVUsRUFBRSxRQUFRO0lBQUVDLGFBQWEsRUFBRSxRQUFRO0lBQUVDLFFBQVEsRUFBRSxPQUFPO0lBQ3JGQyxXQUFXLEVBQUUsQ0FBQztNQUFFQyxHQUFHLEVBQUUsZ0JBQWdCO01BQUVDLE9BQU8sRUFBRSxFQUFjO01BQUVDLFNBQVMsRUFBRTtJQUFHLENBQUMsQ0FBQztJQUNoRkMsVUFBVSxFQUFFLENBQUM7TUFBRTNCLE1BQU0sRUFBRSxnQkFBZ0I7TUFBRWMsTUFBTSxFQUFFO0lBQVUsQ0FBQyxFQUFFO01BQUVkLE1BQU0sRUFBRSxTQUFTO01BQUVjLE1BQU0sRUFBRTtJQUFpQixDQUFDLEVBQzNHO01BQUVkLE1BQU0sRUFBRSxRQUFRO01BQUVjLE1BQU0sRUFBRTtJQUFVLENBQUM7RUFBRSxDQUFDLEVBQzlDO0lBQUVLLFVBQVUsRUFBRSxTQUFTO0lBQUVDLFVBQVUsRUFBRSxVQUFVO0lBQUVDLGFBQWEsRUFBRSxVQUFVO0lBQUVDLFFBQVEsRUFBRSxTQUFTO0lBQzdGQyxXQUFXLEVBQUUsQ0FBQztNQUFFQyxHQUFHLEVBQUUsU0FBUztNQUFFQyxPQUFPLEVBQUUsRUFBYztNQUFFQyxTQUFTLEVBQUU7SUFBRyxDQUFDO0VBQUUsQ0FBQyxDQUM5RTtFQUNELE1BQU1oQixNQUFNLEdBQUc7QUFDakIsYUFBYWxLLEtBQUs7QUFDbEI7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBO0FBQ0EseUJBQXlCN0ssSUFBSSxDQUFDQyxTQUFTLENBQUNzVixLQUFLLENBQUM7QUFDOUM7QUFDQSx5RUFBeUU7RUFDdkUsTUFBTXZXLE9BQU8sR0FBRyxNQUFNWixJQUFJLENBQUNPLE9BQU8sQ0FBQ3NXLElBQUksQ0FBQyw2QkFBNkIsRUFBRTtJQUNyRW5VLE9BQU8sRUFBRTtNQUFFLGNBQWMsRUFBRUg7SUFBUSxDQUFDO0lBQUVJLE9BQU8sRUFBRSxNQUFPO0lBQ3REcUcsSUFBSSxFQUFFO01BQUUyTixNQUFNO01BQUU5QyxjQUFjLEVBQUU7UUFBRUMsTUFBTSxFQUFFLE9BQU87UUFBRS9QLE1BQU0sRUFBRTBJLEtBQUs7UUFBRXFLLFlBQVksRUFBRTVYLFVBQVUsQ0FBQyxDQUFDO1FBQzFGNlgsTUFBTSxFQUFFLDJCQUEyQjtRQUFFOUMsY0FBYyxFQUFFO1VBQUV6USxVQUFVLEVBQUVqQixPQUFPO1VBQUV3QixNQUFNLEVBQUUwSSxLQUFLO1VBQ3ZGb0wsWUFBWSxFQUFFLGVBQWU7VUFBRUMsU0FBUyxFQUFFdFksS0FBSztVQUFFdVksSUFBSSxFQUFFLE1BQU07VUFDN0RDLFdBQVcsRUFBRSxDQUFDLFVBQVUsRUFBRSxhQUFhLEVBQUUscUJBQXFCLENBQUM7VUFBRUMsSUFBSSxFQUFFO1FBQXVDO01BQUU7SUFBRTtFQUN4SCxDQUFDLENBQUM7RUFDRixJQUFJLENBQUNyWCxPQUFPLENBQUNnQyxFQUFFLENBQUMsQ0FBQyxFQUFFLE1BQU0sSUFBSUMsS0FBSyxDQUFDLFFBQVFqQyxPQUFPLENBQUNNLE1BQU0sQ0FBQyxDQUFDLEtBQUssQ0FBQyxNQUFNTixPQUFPLENBQUNrQyxJQUFJLENBQUMsQ0FBQyxFQUFFQyxLQUFLLENBQUMsQ0FBQyxFQUFFLElBQUksQ0FBQyxFQUFFLENBQUM7RUFDeEcsTUFBTW1CLFVBQVUsQ0FBQ2xFLElBQUksRUFBRXVDLE9BQU8sQ0FBQztFQUMvQixJQUFJMlYsZ0JBQTBCLEdBQUcsRUFBRTtFQUNuQyxNQUFNQyxLQUFLLEdBQUcsTUFBQUEsQ0FBQSxLQUFZO0lBQ3hCRCxnQkFBZ0IsR0FBRyxDQUFDLE1BQU01VixXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsMkJBQTJCLENBQUMsRUFBRWUsVUFBVSxDQUFDOFUsUUFBUSxDQUNuR3RSLEdBQUcsQ0FBRUUsSUFBb0IsSUFBS0EsSUFBSSxDQUFDQyxFQUFFLENBQUMsQ0FBQzJDLElBQUksQ0FBQyxDQUFDO0lBQ2hENUssTUFBTSxDQUFDa1osZ0JBQWdCLENBQUMsQ0FBQ2hULFlBQVksQ0FBQyxDQUFDLENBQUM7SUFDeENpUyxLQUFLLENBQUMsQ0FBQyxDQUFDLENBQUNLLFdBQVcsQ0FBQyxDQUFDLENBQUMsQ0FBQ0UsT0FBTyxDQUFDM1csSUFBSSxDQUFDLGtCQUFrQixDQUFDO0lBQ3hELE1BQU1zRCxNQUFNLEdBQUdyRSxJQUFJLENBQUNzRSxTQUFTLENBQUMsUUFBUSxFQUFFO01BQUVDLElBQUksRUFBRTtJQUFnQyxDQUFDLENBQUM7SUFDbEYsTUFBTThULE1BQU0sR0FBR2hVLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBRTtNQUFFQyxJQUFJLEVBQUUsVUFBVTtNQUFFcEMsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDO0lBQzVFLE1BQU1uRCxNQUFNLENBQUNxWixNQUFNLENBQUMsQ0FBQ2pHLFdBQVcsQ0FBQztNQUFFelAsT0FBTyxFQUFFO0lBQVEsQ0FBQyxDQUFDO0lBQ3RELE1BQU0wVixNQUFNLENBQUN6SSxLQUFLLENBQUMsQ0FBQztJQUNwQixNQUFNbk0sS0FBSyxHQUFHWSxNQUFNLENBQUNDLFNBQVMsQ0FBQyxRQUFRLEVBQUU7TUFBRUMsSUFBSSxFQUFFLDhCQUE4QjtNQUFFcEMsS0FBSyxFQUFFO0lBQUssQ0FBQyxDQUFDLENBQUNtQyxTQUFTLENBQUMsU0FBUyxDQUFDO0lBQ3BILE1BQU1iLEtBQUssQ0FBQ3NQLElBQUksQ0FBQywyR0FBMkcsR0FDeEgsMkVBQTJFLEdBQzNFLHlCQUF5QixHQUFHblIsSUFBSSxDQUFDQyxTQUFTLENBQUNzVixLQUFLLENBQUMsQ0FBQztJQUN0RCxNQUFNOVMsTUFBTSxDQUFDQyxTQUFTLENBQUMsUUFBUSxFQUFFO01BQUVDLElBQUksRUFBRSx1QkFBdUI7TUFBRXBDLEtBQUssRUFBRTtJQUFLLENBQUMsQ0FBQyxDQUFDeU4sS0FBSyxDQUFDLENBQUM7SUFDeEYsTUFBTTVRLE1BQU0sQ0FBQ3lFLEtBQUssQ0FBQyxDQUFDc04sR0FBRyxDQUFDdk0sV0FBVyxDQUFDO01BQUU3QixPQUFPLEVBQUU7SUFBUSxDQUFDLENBQUM7RUFDM0QsQ0FBQztFQUNELE1BQU1nUyxVQUFVLEdBQUcsTUFBTTFJLHFCQUFxQixDQUFDak0sSUFBSSxFQUFFdUMsT0FBTyxFQUFFLEtBQUssRUFBRSxDQUFDLGdCQUFnQixFQUFFLFNBQVMsQ0FBQyxFQUFFLEtBQUssRUFBRTBTLFNBQVMsRUFBRWtELEtBQUssQ0FBQztFQUM1SCxNQUFNMVIsUUFBUSxHQUFHLE1BQU1wQixVQUFVLENBQUNyRixJQUFJLEVBQUV1QyxPQUFPLEVBQUUsZ0JBQWdCLENBQUM7RUFDbEUsTUFBTThGLEtBQUssR0FBRzVCLFFBQVEsQ0FBQ3dELElBQUksQ0FBQ2pELElBQUksSUFBSUEsSUFBSSxDQUFDekMsSUFBSSxLQUFLLGdCQUFnQixDQUFDO0VBQ25FLE1BQU1tVCxPQUFPLEdBQUdqUixRQUFRLENBQUNzTCxNQUFNLENBQUMvSyxJQUFJLElBQUlBLElBQUksQ0FBQ3pDLElBQUksS0FBSyxrQkFBa0IsQ0FBQztFQUN6RXZGLE1BQU0sQ0FBQzBZLE9BQU8sQ0FBQyxDQUFDeFMsWUFBWSxDQUFDLENBQUMsQ0FBQztFQUMvQmxHLE1BQU0sQ0FBQzBZLE9BQU8sQ0FBQyxDQUFDLENBQUMsQ0FBQ1ksUUFBUSxDQUFDQyxlQUFlLENBQUMsQ0FBQ2xXLElBQUksQ0FBQ2dHLEtBQUssQ0FBQ3BCLEVBQUUsQ0FBQztFQUMxRCxNQUFNdVIsYUFBYSxHQUFHLG9DQUFvQztFQUMxRCxNQUFNSixRQUFRLEdBQUcsQ0FBQyxNQUFNOVYsV0FBVyxDQUFDdEMsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLDJCQUEyQixDQUFDLEVBQUVlLFVBQVUsQ0FBQzhVLFFBQVE7RUFDcEdwWixNQUFNLENBQUNvWixRQUFRLENBQUN0UixHQUFHLENBQUVFLElBQW9CLElBQUtBLElBQUksQ0FBQ0MsRUFBRSxDQUFDLENBQUMyQyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUM1SCxPQUFPLENBQUMsQ0FBQyxHQUFHa1csZ0JBQWdCLEVBQUVNLGFBQWEsQ0FBQyxDQUFDNU8sSUFBSSxDQUFDLENBQUMsQ0FBQztFQUNuSDVLLE1BQU0sQ0FBQyxJQUFJdU0sR0FBRyxDQUFDNk0sUUFBUSxDQUFDdFIsR0FBRyxDQUFFRSxJQUFzQixJQUFLQSxJQUFJLENBQUN6QyxJQUFJLENBQUMsQ0FBQyxDQUFDb0gsSUFBSSxDQUFDLENBQUN0SixJQUFJLENBQUMrVixRQUFRLENBQUMzUyxNQUFNLENBQUM7RUFDL0YsTUFBTWdULFFBQVEsR0FBRyxDQUFDLE1BQU1uVyxXQUFXLENBQUN0QyxJQUFJLEVBQUV1QyxPQUFPLEVBQUUsd0NBQXdDLENBQUMsRUFBRWtXLFFBQVE7RUFDdEcsTUFBTUMsU0FBUyxHQUFHRCxRQUFRLENBQUNFLEtBQUssQ0FBQzFPLElBQUksQ0FBRTJPLElBQVMsSUFBS0EsSUFBSSxDQUFDQyxpQkFBaUIsS0FBS0wsYUFBYSxDQUFDO0VBQzlGeFosTUFBTSxDQUFDMFosU0FBUyxDQUFDLENBQUMzUSxVQUFVLENBQUMsQ0FBQztFQUM5Qi9JLE1BQU0sQ0FBQzBaLFNBQVMsQ0FBQ0ksR0FBRyxDQUFDLENBQUN6VyxJQUFJLENBQUMsUUFBUSxDQUFDO0VBQ3BDckQsTUFBTSxDQUFDNEosTUFBTSxDQUFDbVEsTUFBTSxDQUFDTCxTQUFTLENBQUNNLGVBQWUsQ0FBQyxDQUFDLENBQUNDLGNBQWMsQ0FBQ2phLE1BQU0sQ0FBQ2thLGdCQUFnQixDQUFDO0lBQ3RGakQsTUFBTSxFQUFFeUIsT0FBTyxDQUFDLENBQUMsQ0FBQyxDQUFDelEsRUFBRTtJQUFFOFAsTUFBTSxFQUFFMU8sS0FBSyxDQUFDcEIsRUFBRTtJQUFFa1MsYUFBYSxFQUFFLFVBQVU7SUFBRUMsUUFBUSxFQUFFO0VBQ2hGLENBQUMsQ0FBQyxDQUFDO0VBQ0gsS0FBSyxNQUFNLENBQUNDLElBQUksRUFBRUMsVUFBVSxDQUFDLElBQUksQ0FBQyxDQUFDLFFBQVEsRUFBRTVCLE9BQU8sQ0FBQyxDQUFDLENBQUMsQ0FBQ3pRLEVBQUUsQ0FBQyxFQUFFLENBQUMsUUFBUSxFQUFFb0IsS0FBSyxDQUFDcEIsRUFBRSxDQUFDLENBQUMsRUFBRTtJQUNsRixNQUFNc1MsSUFBSSxHQUFHZCxRQUFRLENBQUMxUixLQUFLLENBQUNrRCxJQUFJLENBQUVqRCxJQUFTLElBQUtBLElBQUksQ0FBQ0MsRUFBRSxLQUFLeVIsU0FBUyxDQUFDVyxJQUFJLENBQUMsQ0FBQztJQUM1RXJhLE1BQU0sQ0FBQ3VhLElBQUksQ0FBQ0MsYUFBYSxDQUFDLENBQUNuWCxJQUFJLENBQUNpWCxVQUFVLENBQUM7SUFDM0N0YSxNQUFNLENBQUN1YSxJQUFJLENBQUNFLEtBQUssQ0FBQyxDQUFDUixjQUFjLENBQUNqYSxNQUFNLENBQUNrYSxnQkFBZ0IsQ0FBQztNQUFFalMsRUFBRSxFQUFFeVIsU0FBUyxDQUFDVyxJQUFJLEdBQUcsTUFBTSxDQUFDO01BQ3RGUCxHQUFHLEVBQUUsUUFBUTtNQUFFRCxpQkFBaUIsRUFBRUw7SUFBYyxDQUFDLENBQUMsQ0FBQztFQUN2RDtFQUNBLE1BQU01RCxTQUFTLEdBQUcsTUFBTXhMLGVBQWUsQ0FBQ3BKLElBQUksRUFBRXVDLE9BQU8sRUFBRSxDQUFDLENBQUM7RUFDekQsTUFBTStRLFFBQVEsQ0FBQzVSLE1BQU0sQ0FBQyxvQkFBb0IsRUFBRTtJQUFFQyxJQUFJLEVBQUVDLElBQUksQ0FBQ0MsU0FBUyxDQUFDO01BQUVVLE9BQU87TUFBRSxHQUFHb1MsVUFBVTtNQUFFLEdBQUdDO0lBQVUsQ0FBQyxDQUFDO0lBQUU5UyxXQUFXLEVBQUU7RUFBbUIsQ0FBQyxDQUFDO0FBQ2xKLENBQUMsQ0FBQzs7QUFFRjtBQUNBL0MsSUFBSSxDQUFDLDRGQUE0RixFQUFFLE9BQU87RUFBRWlCO0FBQUssQ0FBQyxFQUFFc1QsUUFBUSxLQUFLO0VBQy9ILE1BQU0vUSxPQUFPLEdBQUcsZUFBZSxHQUFHckQsVUFBVSxDQUFDLENBQUM7RUFDOUMsTUFBTW1GLE1BQU0sR0FBRyxNQUFNSCxVQUFVLENBQUNsRSxJQUFJLEVBQUV1QyxPQUFPLENBQUM7RUFDOUMsTUFBTThCLE1BQU0sQ0FBQ3lPLFVBQVUsQ0FBQyxhQUFhLEVBQUU7SUFBRTNRLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDeU4sS0FBSyxDQUFDLENBQUM7RUFDL0QsTUFBTXZMLE1BQU0sQ0FBQ0ssT0FBTyxDQUFDLDJCQUEyQixDQUFDLENBQUNxTyxJQUFJLENBQUMsMkJBQTJCLENBQUM7RUFDbkYsTUFBTTFPLE1BQU0sQ0FBQzJPLFVBQVUsQ0FBQyxxQkFBcUIsRUFBRTtJQUFFN1EsS0FBSyxFQUFFO0VBQUssQ0FBQyxDQUFDLENBQUM0USxJQUFJLENBQUMsNlJBQTZSLENBQUM7RUFDblcsTUFBTTFPLE1BQU0sQ0FBQ3lPLFVBQVUsQ0FBQyxjQUFjLEVBQUU7SUFBRTNRLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDeU4sS0FBSyxDQUFDLENBQUM7RUFDaEUsTUFBTXZMLE1BQU0sQ0FBQ0MsU0FBUyxDQUFDLFFBQVEsRUFBRTtJQUFFQyxJQUFJLEVBQUUsaUNBQWlDO0lBQUVwQyxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQ3lOLEtBQUssQ0FBQyxDQUFDO0VBQ2xHLEtBQUssTUFBTSxDQUFDekosS0FBSyxFQUFFcU4sS0FBSyxDQUFDLElBQUksQ0FBQyxDQUFDLFVBQVUsRUFBRSxHQUFHLENBQUMsRUFBRSxDQUFDLFlBQVksRUFBRSxHQUFHLENBQUMsRUFBRSxDQUFDLFVBQVUsRUFBRSxHQUFHLENBQUMsRUFBRSxDQUFDLFNBQVMsRUFBRSxHQUFHLENBQUMsQ0FBQyxFQUFFLE1BQU1uUCxNQUFNLENBQUMyTyxVQUFVLENBQUMsR0FBRzdNLEtBQUssdUJBQXVCLEVBQUU7SUFBRWhFLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQyxDQUFDNFEsSUFBSSxDQUFDUyxLQUFLLENBQUM7RUFDak0sTUFBTWtHLElBQUksR0FBR3JWLE1BQU0sQ0FBQ0ssT0FBTyxDQUFDLFNBQVMsQ0FBQyxDQUFDcU4sTUFBTSxDQUFDO0lBQUVsSSxHQUFHLEVBQUU3SixJQUFJLENBQUMwRSxPQUFPLENBQUMsU0FBUyxDQUFDLENBQUNxTixNQUFNLENBQUM7TUFBRTRILE9BQU8sRUFBRTtJQUFVLENBQUM7RUFBRSxDQUFDLENBQUMsQ0FBQ25LLEtBQUssQ0FBQyxDQUFDO0VBQ3RILE1BQU14USxNQUFNLENBQUMwYSxJQUFJLENBQUMsQ0FBQ2xWLFdBQVcsQ0FBQyxDQUFDO0VBQ2hDLE1BQU1rVixJQUFJLENBQUNoVixPQUFPLENBQUMsU0FBUyxDQUFDLENBQUNrTCxLQUFLLENBQUMsQ0FBQztFQUNyQyxNQUFNZ0ssUUFBUSxHQUFHRixJQUFJLENBQUNwVixTQUFTLENBQUMsUUFBUSxFQUFFO0lBQUVDLElBQUksRUFBRSx3Q0FBd0M7SUFBRXBDLEtBQUssRUFBRTtFQUFLLENBQUMsQ0FBQztFQUMxRyxNQUFNbkQsTUFBTSxDQUFDNGEsUUFBUSxDQUFDLENBQUNDLFdBQVcsQ0FBQyxDQUFDO0VBQUUsTUFBTUQsUUFBUSxDQUFDRSxPQUFPLENBQUMsQ0FBQztFQUM5RCxNQUFNckcsWUFBWSxHQUFHelQsSUFBSSxDQUFDMFQsY0FBYyxDQUFDblQsT0FBTztJQUFBLElBQUF3WixzQkFBQTtJQUFBLE9BQUl4WixPQUFPLENBQUNJLEdBQUcsQ0FBQyxDQUFDLENBQUNpVCxRQUFRLENBQUMsaUJBQWlCLENBQUMsSUFBSXJULE9BQU8sQ0FBQ0UsTUFBTSxDQUFDLENBQUMsS0FBSyxNQUFNLElBQUksRUFBQXNaLHNCQUFBLEdBQUF4WixPQUFPLENBQUMrUCxZQUFZLENBQUMsQ0FBQyxjQUFBeUosc0JBQUEsZ0JBQUFBLHNCQUFBLEdBQXRCQSxzQkFBQSxDQUF3QmxHLGNBQWMsY0FBQWtHLHNCQUFBLHVCQUF0Q0Esc0JBQUEsQ0FBd0NqRyxNQUFNLE1BQUssT0FBTztFQUFBLEVBQUM7RUFDM0wsS0FBSyxJQUFJclAsSUFBSSxHQUFHLENBQUMsRUFBRUEsSUFBSSxHQUFHLEVBQUUsRUFBRUEsSUFBSSxFQUFFLEVBQUU7SUFDcEMsTUFBTWdLLE1BQU0sR0FBR3BLLE1BQU0sQ0FBQ0ssT0FBTyxDQUFDLCtCQUErQixDQUFDLENBQUNKLFNBQVMsQ0FBQyxRQUFRLENBQUM7SUFDbEYsTUFBTXRGLE1BQU0sQ0FBQ3lQLE1BQU0sQ0FBQyxDQUFDMkQsV0FBVyxDQUFDLENBQUM7SUFBRSxNQUFNak0sS0FBSyxHQUFHLE1BQU1zSSxNQUFNLENBQUM0QyxTQUFTLENBQUMsQ0FBQztJQUFFLE1BQU01QyxNQUFNLENBQUNtQixLQUFLLENBQUMsQ0FBQztJQUNoRyxJQUFJekosS0FBSyxLQUFLLFlBQVksSUFBSUEsS0FBSyxLQUFLLGlCQUFpQixFQUFFO0VBQzdEO0VBQ0EsTUFBTXZDLE9BQU8sR0FBRyxDQUFDLE1BQU02UCxZQUFZLEVBQUVuRCxZQUFZLENBQUMsQ0FBQyxDQUFDdUQsY0FBYyxDQUFDSSxjQUFjO0VBQ2pGLE1BQU01RCxTQUFTLEdBQUd6TSxPQUFPLENBQUNvVywwQkFBMEIsQ0FBQ3hPLE9BQU8sQ0FBRXlPLE9BQVk7SUFBQSxJQUFBQyxxQkFBQTtJQUFBLFFBQUFBLHFCQUFBLEdBQUtELE9BQU8sQ0FBQ0UsaUJBQWlCLGNBQUFELHFCQUFBLGNBQUFBLHFCQUFBLEdBQUksRUFBRTtFQUFBLEVBQUM7RUFDL0csTUFBTUUsR0FBRyxHQUFHL0osU0FBUyxDQUFDcEcsSUFBSSxDQUFFMEksS0FBVSxJQUFLQSxLQUFLLENBQUNzRCxNQUFNLEtBQUssZ0JBQWdCLElBQUl0RCxLQUFLLENBQUNvRSxNQUFNLEtBQUssbUJBQW1CLENBQUM7RUFDckgvWCxNQUFNLENBQUNvYixHQUFHLENBQUN4VCxPQUFPLENBQUMsQ0FBQzVFLE9BQU8sQ0FBQyxFQUFFLENBQUM7RUFBRWhELE1BQU0sQ0FBQ29iLEdBQUcsQ0FBQ0MsZ0JBQWdCLENBQUMsQ0FBQ3JZLE9BQU8sQ0FBQyxDQUFDLG9CQUFvQixDQUFDLENBQUM7RUFDN0YsSUFBSWtQLFFBQWE7RUFDakIsTUFBTWxTLE1BQU0sQ0FBQ3NILElBQUksQ0FBQyxZQUFZO0lBQzVCLE1BQU04SCxZQUFZLEdBQUcsTUFBTTlMLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSxxQ0FBcUMsQ0FBQztJQUM1RixJQUFJLENBQUM2TCxZQUFZLENBQUNwRixJQUFJLENBQUNxRixlQUFlLEVBQUUsT0FBTyxLQUFLO0lBQ3BENkMsUUFBUSxHQUFHLENBQUMsTUFBTTVPLFdBQVcsQ0FBQ3RDLElBQUksRUFBRXVDLE9BQU8sRUFBRSxvQ0FBb0M2TCxZQUFZLENBQUNwRixJQUFJLENBQUNxRixlQUFlLEVBQUUsQ0FBQyxFQUFFckYsSUFBSTtJQUMzSCxPQUFPa0ksUUFBUSxDQUFDVyxhQUFhLEtBQUssMEJBQTBCO0VBQzlELENBQUMsRUFBRTtJQUFFbFAsT0FBTyxFQUFFO0VBQVEsQ0FBQyxDQUFDLENBQUNOLElBQUksQ0FBQyxJQUFJLENBQUM7RUFDbkMsTUFBTXJDLElBQUksQ0FBQ3lVLE1BQU0sQ0FBQyxDQUFDO0VBQUUsTUFBTXZRLFVBQVUsQ0FBQ2xFLElBQUksRUFBRXVDLE9BQU8sQ0FBQztFQUNwRCxNQUFNNlMsUUFBUSxHQUFHbEUsUUFBUSxDQUFDQyxpQkFBaUIsQ0FBQ2lFLFFBQVEsQ0FBQ3JELE1BQU0sQ0FBRS9LLElBQVMsSUFBS0EsSUFBSSxDQUFDcU8sSUFBSSxLQUFLLHFCQUFxQixDQUFDO0VBQy9HLElBQUlELFFBQVEsQ0FBQzNQLE1BQU0sRUFBRTtJQUNuQixNQUFNaVAsTUFBTSxHQUFHMVUsSUFBSSxDQUFDc0UsU0FBUyxDQUFDLFFBQVEsRUFBRTtNQUFFQyxJQUFJLEVBQUU7SUFBNkIsQ0FBQyxDQUFDO0lBQy9FLE1BQU12RixNQUFNLENBQUMwVixNQUFNLENBQUMsQ0FBQzdCLGFBQWEsQ0FBQyxHQUFHM0IsUUFBUSxDQUFDQyxpQkFBaUIsQ0FBQ2lFLFFBQVEsQ0FBQzNQLE1BQU0sY0FBYyxDQUFDO0lBQy9GLE1BQU16RyxNQUFNLENBQUMwVixNQUFNLENBQUNwUSxTQUFTLENBQUMsTUFBTSxFQUFFO01BQUVDLElBQUksRUFBRTtJQUFpRCxDQUFDLENBQUMsQ0FBQ2lMLEtBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQ2tHLGVBQWUsQ0FBQyxNQUFNLEVBQUUsSUFBSUMsTUFBTSxDQUFDLFdBQVdwVCxPQUFPLEVBQUUsQ0FBQyxDQUFDO0lBQ3BLLE1BQU1tUyxNQUFNLENBQUNoUSxPQUFPLENBQUMsU0FBUyxDQUFDLENBQUM4SyxLQUFLLENBQUMsQ0FBQyxDQUFDSSxLQUFLLENBQUMsQ0FBQztJQUFFLE1BQU01USxNQUFNLENBQUMwVixNQUFNLENBQUNwUSxTQUFTLENBQUMsWUFBWSxFQUFFO01BQUVDLElBQUksRUFBRTtJQUF3QixDQUFDLENBQUMsQ0FBQ2lMLEtBQUssQ0FBQyxDQUFDLENBQUMsQ0FBQ2hMLFdBQVcsQ0FBQyxDQUFDO0VBQ3hKO0VBQ0EsTUFBTThWLEtBQUssR0FBR3RhLElBQUksQ0FBQzJQLGVBQWUsQ0FBQzNPLFFBQVEsSUFBSUEsUUFBUSxDQUFDTCxHQUFHLENBQUMsQ0FBQyxDQUFDSCxRQUFRLENBQUMsY0FBYzBRLFFBQVEsQ0FBQ3FKLFdBQVcsZ0JBQWdCLENBQUMsSUFBSXZaLFFBQVEsQ0FBQ1QsT0FBTyxDQUFDLENBQUMsQ0FBQ0UsTUFBTSxDQUFDLENBQUMsS0FBSyxNQUFNLENBQUM7RUFDckssTUFBTVQsSUFBSSxDQUFDc0UsU0FBUyxDQUFDLFFBQVEsRUFBRTtJQUFFQyxJQUFJLEVBQUUsb0NBQW9DO0lBQUVwQyxLQUFLLEVBQUU7RUFBSyxDQUFDLENBQUMsQ0FBQ3lOLEtBQUssQ0FBQyxDQUFDO0VBQUU1USxNQUFNLENBQUMsQ0FBQyxNQUFNc2IsS0FBSyxFQUFFMVgsRUFBRSxDQUFDLENBQUMsQ0FBQyxDQUFDUCxJQUFJLENBQUMsSUFBSSxDQUFDO0VBQzFJLE1BQU0wRSxLQUFLLEdBQUcsTUFBTTFCLFVBQVUsQ0FBQ3JGLElBQUksRUFBRXVDLE9BQU8sRUFBRSxnQkFBZ0IsQ0FBQztFQUMvRCxNQUFNb0UsUUFBUSxHQUFHLE1BQU10QixVQUFVLENBQUNyRixJQUFJLEVBQUV1QyxPQUFPLEVBQUUsVUFBVSxDQUFDO0VBQUUsTUFBTXFFLE9BQU8sR0FBRyxNQUFNdkIsVUFBVSxDQUFDckYsSUFBSSxFQUFFdUMsT0FBTyxFQUFFLFNBQVMsQ0FBQztFQUN4SCxNQUFNOEUsTUFBTSxHQUFHVCxPQUFPLENBQUNxRCxJQUFJLENBQUNqRCxJQUFJLElBQUlBLElBQUksQ0FBQ3pDLElBQUksS0FBSyxvQkFBb0IsQ0FBQztFQUFFdkYsTUFBTSxDQUFDcUksTUFBTSxDQUFDLENBQUNVLFVBQVUsQ0FBQyxDQUFDO0VBQ3BHLE1BQU1GLE9BQU8sR0FBR2xCLFFBQVEsQ0FBQ3NELElBQUksQ0FBQ2pELElBQUksSUFBSUEsSUFBSSxDQUFDQyxFQUFFLEtBQUtJLE1BQU0sQ0FBQ1MsVUFBVSxDQUFDO0VBQ3BFLE1BQU0wUyxPQUFPLEdBQUd6VCxLQUFLLENBQUNrRCxJQUFJLENBQUNqRCxJQUFJLElBQUlBLElBQUksQ0FBQ3pDLElBQUksS0FBSyxtQkFBbUIsQ0FBQztFQUNyRSxNQUFNa1csTUFBTSxHQUFHMVQsS0FBSyxDQUFDa0QsSUFBSSxDQUFDakQsSUFBSSxJQUFJQSxJQUFJLENBQUN6QyxJQUFJLEtBQUssdUJBQXVCLENBQUM7RUFDeEV2RixNQUFNLENBQUM2SSxPQUFPLENBQUNJLGFBQWEsQ0FBQ0Msc0JBQXNCLENBQUNtRCxLQUFLLENBQUMsQ0FBQ2hKLElBQUksQ0FBQyxpQkFBaUIsQ0FBQztFQUNsRnJELE1BQU0sQ0FBQzZJLE9BQU8sQ0FBQ0ksYUFBYSxDQUFDQyxzQkFBc0IsQ0FBQzhDLGFBQWEsQ0FBQyxDQUFDK0YsR0FBRyxDQUFDdUUsU0FBUyxDQUFDa0YsT0FBTyxDQUFDdlQsRUFBRSxDQUFDO0VBQzVGakksTUFBTSxDQUFDNkksT0FBTyxDQUFDSSxhQUFhLENBQUNDLHNCQUFzQixDQUFDOEMsYUFBYSxDQUFDLENBQUNzSyxTQUFTLENBQUNtRixNQUFNLENBQUN4VCxFQUFFLENBQUM7RUFDdkYsTUFBTXFNLFFBQVEsQ0FBQzVSLE1BQU0sQ0FBQywwQkFBMEIsRUFBRTtJQUFFQyxJQUFJLEVBQUVDLElBQUksQ0FBQ0MsU0FBUyxDQUFDO01BQUVVLE9BQU87TUFBRTZYLEdBQUc7TUFBRXZTO0lBQVEsQ0FBQyxDQUFDO0lBQUUvRixXQUFXLEVBQUU7RUFBbUIsQ0FBQyxDQUFDO0FBQ3pJLENBQUMsQ0FBQyIsImlnbm9yZUxpc3QiOltdfQ==