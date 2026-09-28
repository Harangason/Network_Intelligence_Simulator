// 08e4ef856d7cba3bd381e13ef69f12aa3c24d8fe
import { test, expect } from 'playwright/test';
import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { WizardProgressWatchdog, WIZARD_STEPS, WIZARD_DONE } from './support/wizard-progress-watchdog';
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
  if (!result.ok()) throw new Error(`${path}: HTTP ${result.status()} ${(await result.text()).slice(0, 4000)}`);
  return result.json();
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
  const workflow = await readProject(page, project, '/api/engineering/workflow?view=summary');
  expect(Object.keys(workflow.statuses).sort()).toEqual([...steps].sort());
  for (const step of steps) expect(done.has(workflow.statuses[step]), `${step}: ${workflow.statuses[step]}`).toBeTruthy();
  const jobs = (await readProject(page, project, '/api/simulations')).jobs;
  expect(jobs).toHaveLength(1);
  expect(jobs[0].status).toBe('completed');
  const snapshots = await readProject(page, project, '/api/engineering/workflow/snapshots');
  const snapshot = snapshots.simulations.find(item => item.job_id === jobs[0].id);
  expect(snapshot).toBeTruthy();
  const full = await readProject(page, project, `/api/engineering/workflow/simulation-snapshots/${snapshot.id}`);
  const assessment = full.result.assessment;
  expect(assessment.scope_coverage.scope_mode).toBe('ALL');
  expect(assessment.scope_coverage.complete).toBe(true);
  expect(assessment.conformance).toBe('PASS');
  expect(assessment.failed_route_count).toBe(0);
  const signals = await allObjects(page, project, 'signals');
  expect(signals.length, 'The full canonical signal inventory must survive generation.').toBeGreaterThanOrEqual(minimumCanonicalSignals);
  const excluded = (_assessment$scope_cov = assessment.scope_coverage.transport_exclusions) !== null && _assessment$scope_cov !== void 0 ? _assessment$scope_cov : [];
  const messages = await allObjects(page, project, 'messages');
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
    await expect(completeThroughWizard(page, project, true, ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4', 'Ventilaktor1', 'Ventilaktor2'], false, undefined, undefined, true)).rejects.toThrow(/Wizard BLOCKED at validation/);
    const workflow = await readProject(page, project, '/api/engineering/workflow');
    const findings = workflow.context.agent_execution.blocking_findings;
    expect(findings.map(item => item.code)).toContain(technology === 'I2C' ? 'COMMUNICATION_UNVERIFIED' : 'GENERIC_ESTIMATE');
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
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmVhZEZpbGUiLCJyYW5kb21VVUlEIiwiZXhlY0ZpbGVTeW5jIiwiV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyIsIldJWkFSRF9TVEVQUyIsIldJWkFSRF9ET05FIiwic3RlcHMiLCJkb25lIiwid3JpdGVUaW1pbmdzIiwiTWFwIiwid29ya2Zsb3dQYWdlRmFpbHVyZXMiLCJXZWFrTWFwIiwicHJvZ3Jlc3NNaWxlc3RvbmVzIiwiYmVmb3JlRWFjaCIsInBhZ2UiLCJpbmZvIiwicm93cyIsInNldCIsInRlc3RJZCIsInJlcXVlc3RzIiwib24iLCJyZXF1ZXN0IiwiaW5jbHVkZXMiLCJtZXRob2QiLCJyb3ciLCJ1cmwiLCJzdGFydGVkIiwiRGF0ZSIsIm5vdyIsInB1c2giLCJyZXNwb25zZSIsImdldCIsInN0YXR1cyIsIlVSTCIsInBhdGhuYW1lIiwiZHVyYXRpb25fbXMiLCJfcmVxdWVzdCRmYWlsdXJlIiwiZmFpbHVyZSIsImVycm9yVGV4dCIsImFmdGVyRWFjaCIsImF0dGFjaCIsImJvZHkiLCJKU09OIiwic3RyaW5naWZ5IiwiY29udGVudFR5cGUiLCJkZWxldGUiLCJ0b0VxdWFsIiwiYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeSIsImdldEJ5VGV4dCIsImV4YWN0IiwiaXNWaXNpYmxlIiwidG9CZSIsInJlYWRQcm9qZWN0IiwicHJvamVjdCIsInBhdGgiLCJyZXN1bHQiLCJoZWFkZXJzIiwidGltZW91dCIsIm9rIiwiRXJyb3IiLCJ0ZXh0Iiwic2xpY2UiLCJqc29uIiwicmVhZFdhcm5pbmdSZXZpZXdTdGF0ZSIsIl92ZXJpZmllZCRjb250ZXh0JGFnZTIiLCJfdmVyaWZpZWQkY29udGV4dCRhZ2UzIiwiYXV0aG9yaXR5IiwicGFyYW1ldGVycyIsInZlcmlmaWVkIiwicHJvamVjdF9pZCIsImZpZWxkIiwiX3ZlcmlmaWVkJGNvbnRleHQkYWdlIiwiX2F1dGhvcml0eSRjb250ZXh0JGFnIiwiY29udGV4dCIsImFnZW50X2V4ZWN1dGlvbiIsInN0YXR1c2VzIiwicnVuX2lkIiwicmVxdWVzdF9yZXZpc2lvbiIsInByZWZsaWdodF93YXJuaW5nX2FwcHJvdmFsIiwib3BlbldpemFyZCIsImdvdG8iLCJ3YWl0VW50aWwiLCJkaWFsb2ciLCJnZXRCeVJvbGUiLCJuYW1lIiwidG9CZVZpc2libGUiLCJhbGxPYmplY3RzIiwicmVzb3VyY2UiLCJpdGVtcyIsIm9mZnNldCIsImxlbmd0aCIsInJlc3RhcnRBcHBsaWNhdGlvbiIsImNyYXNoIiwiY29udGFpbmVyIiwicHJvY2VzcyIsImVudiIsIk5JU19FMkVfQVBQX0NPTlRBSU5FUiIsInRvTWF0Y2giLCJkb2NrZXIiLCJOSVNfVEVTVF9ET0NLRVIiLCJsYWJlbCIsImVuY29kaW5nIiwidHJpbSIsInBvbGwiLCJ2ZXJpZnlTaWduYWxDb250cmFjdHMiLCJleHBlY3RlZCIsImhhcmR3YXJlIiwiZnVuY3Rpb25zIiwibWVzc2FnZXMiLCJzaWduYWxzIiwiUHJvbWlzZSIsImFsbCIsIm1hcCIsIm5vZGVzIiwiaXRlbSIsImlkIiwiZnVuY3Rpb25zQnlJZCIsIm1lc3NhZ2VzQnlJZCIsImNvbnRyYWN0cyIsInNpZ25hbCIsIl9yZWYiLCJfc2lnbmFsJGRhdGEkZW51bV92YWwiLCJfc2lnbmFsJGRhdGEiLCJfc2lnbmFsJHNlbWFudGljJHNlbWEiLCJfc2lnbmFsJHNlbWFudGljIiwiX3NpZ25hbCRjb25maWd1cmF0aW9uIiwiX3NpZ25hbCRjb25maWd1cmF0aW9uMiIsIm1lc3NhZ2UiLCJtZXNzYWdlX2lkIiwidG9CZVRydXRoeSIsInJlZmVyZW5jZSIsImNvbmZpZ3VyYXRpb24iLCJjb21tdW5pY2F0aW9uX2NvbnRyYWN0IiwicHJvZHVjZXJfcmVmIiwiZm4iLCJvd25lciIsImhhcmR3YXJlX25vZGVfaWQiLCJwcm9kdWNlciIsImRldmljZV90eXBlIiwia2V5Iiwiam9pbiIsInRvQmVVbmRlZmluZWQiLCJPYmplY3QiLCJmcm9tRW50cmllcyIsIl9zaWduYWwkZmllbGQiLCJlbnVtX3ZhbHVlcyIsImRhdGEiLCJzZW1hbnRpY190eXBlIiwic2VtYW50aWMiLCJnZW5lcmF0aW9uX3JvbGUiLCJ2ZXJpZnlBcnRpZmFjdHMiLCJtaW5pbXVtQ2Fub25pY2FsU2lnbmFscyIsImludGVybmFsQ29udHJvbGxlciIsIl9hc3Nlc3NtZW50JHNjb3BlX2NvdiIsIndvcmtmbG93Iiwia2V5cyIsInNvcnQiLCJzdGVwIiwiaGFzIiwiam9icyIsInRvSGF2ZUxlbmd0aCIsInNuYXBzaG90cyIsInNuYXBzaG90Iiwic2ltdWxhdGlvbnMiLCJmaW5kIiwiam9iX2lkIiwiZnVsbCIsImFzc2Vzc21lbnQiLCJzY29wZV9jb3ZlcmFnZSIsInNjb3BlX21vZGUiLCJjb21wbGV0ZSIsImNvbmZvcm1hbmNlIiwiZmFpbGVkX3JvdXRlX2NvdW50IiwidG9CZUdyZWF0ZXJUaGFuT3JFcXVhbCIsImV4Y2x1ZGVkIiwidHJhbnNwb3J0X2V4Y2x1c2lvbnMiLCJyb3V0aW5nIiwiZW5hYmxlZCIsImNvbnRyYWN0IiwiY29uc3VtZXJfcmVmcyIsInJlYXNvbl9jb2RlIiwicm9sZSIsImNvbnRyb2xsZXIiLCJ0b0JlR3JlYXRlclRoYW4iLCJ0b01hdGNoT2JqZWN0Iiwic2NvcGUiLCJleGNsdWRlZFNpZ25hbHMiLCJTZXQiLCJmbGF0TWFwIiwic2lnbmFsX2lkcyIsIm9ic2VydmVkX3NpZ25hbF9jb3VudCIsInNpemUiLCJ0cmFjZSIsImNvdW50IiwiZXZlbnRzIiwic29tZSIsImpvYiIsImNvbXBsZXRlVGhyb3VnaFdpemFyZCIsInJlc3RhcnQiLCJleHBlY3RlZEhhcmR3YXJlIiwiY3Jhc2hTaW11bGF0aW9uIiwiZXhwZWN0ZWRTaWduYWxzIiwiYWZ0ZXJGaXJzdE1vZGVsQXBwbGllZCIsInN0b3BPbkV2aWRlbmNlQmxvY2siLCJyZXZpZXdDb3VudCIsInJ1bklkIiwicmV2aWV3ZWQiLCJyZXN0YXJ0ZWRKb2JJZCIsIndhdGNoZG9nIiwicGVyZm9ybWFuY2UiLCJjaGVja3BvaW50IiwiX3dvcmtmbG93JGNvbnRleHQkYWdlIiwiX3dvcmtmbG93JGNvbnRleHQkYWdlMiIsIl9leGVjdXRpb24kYmxvY2tpbmdfZiIsIl9leGVjdXRpb24kbWVzc2FnZSIsInByb3Bvc2FsSWQiLCJyZWFkeVZlcnNpb24iLCJyZWFkeVNpbmNlIiwiaXNDaGVja3BvaW50IiwicmVtYWluaW5nIiwicHJvZ3Jlc3MiLCJvYnNlcnZlIiwiYWR2YW5jZWQiLCJhdCIsInRvSVNPU3RyaW5nIiwiZnJvbnRpZXIiLCJjb21wbGV0ZWRUaHJvdWdoIiwiZXhlY3V0aW9uIiwidmFsaWRhdGlvbiIsInJ1bm5pbmciLCJldmVyeSIsInN0YXRlIiwiY29udmVyc2F0aW9uIiwiYWN0aXZlX3Byb3Bvc2FsIiwiQm9vbGVhbiIsInJlY292ZXJhYmxlIiwidXBkYXRlZF9hdCIsImJ1dHRvbiIsImV2YWx1YXRlQWxsIiwiYnV0dG9ucyIsImRpc2FibGVkIiwiZ2V0Q2xpZW50UmVjdHMiLCJnZXRDb21wdXRlZFN0eWxlIiwidmlzaWJpbGl0eSIsImF0dGVtcHQiLCJ3YWl0Rm9yVGltZW91dCIsIk1hdGgiLCJtaW4iLCJibG9ja2luZ19maW5kaW5ncyIsImJlZm9yZVJldmlldyIsInByZWZsaWdodCIsIndhcm5pbmdzIiwiZmlyc3QiLCJzdGFydGVkV2FsbCIsImFwcHJvdmFsUmVzcG9uc2UiLCJ3YWl0Rm9yUmVzcG9uc2UiLCJjbGljayIsImFwcHJvdmVkIiwicmVjZWlwdCIsImFmdGVyUmV2aWV3IiwicHJvb2YiLCJiZWZvcmUiLCJhZnRlciIsInNuYXBzaG90SWQiLCJyZXF1ZXN0UHJvamVjdCIsInN1Ym1pdHRlZCIsInBvc3REYXRhSlNPTiIsImZpbmlzaGVkV2FsbCIsImNvbW1pdHRlZEF0IiwiY29tbWl0dGVkIiwiY29tbWl0V2FybmluZ1JldmlldyIsIm1hbnVhbFdhcm5pbmdBcHByb3ZhbCIsImFwcHJvdmFsSWRlbnRpdHkiLCJhcHByb3ZhbCIsIl9hd2FpdCRyZWFkUHJvamVjdCRjbyIsIm5vdCIsIl9jb252ZXJzYXRpb24kZGF0YSIsIl9wcm9wb3NhbCRkYXRhIiwicHJvcG9zYWwiLCJ2YWxpZGF0aW9uX3Jlc3VsdCIsInZpc2libGUiLCJpbm5lclRleHQiLCJlcnJvciIsIl9sYXRlc3QkY29udGV4dCRhZ2VudCIsImxhdGVzdCIsIl9sYXRlc3QkY29udGV4dCRhZ2VudDIiLCJfbGF0ZXN0JGNvbnRleHQkYWdlbnQzIiwiX2xhdGVzdCRzdGF0dXNlcyIsImNhbmRpZGF0ZSIsInByb3Bvc2FsX3R5cGUiLCJjaGFuZ2VzIiwiZmlsdGVyIiwiY2hhbmdlIiwib2JqZWN0X3R5cGUiLCJhcnJheUNvbnRhaW5pbmciLCJhcHBseVJlc3BvbnNlIiwidG9CZUVuYWJsZWQiLCJhcHBsaWVkIiwiYWRkIiwiX2FtZW5kZWQkY29udGV4dCRhZ2VuIiwiYW1lbmRlZCIsIl9jdXJyZW50JGNvbnRleHQkYWdlbiIsImN1cnJlbnQiLCJ0ZXN0SW5mbyIsImVycm9ycyIsImdldEJ5VGl0bGUiLCJsb2NhdG9yIiwiZmlsbCIsImdldEJ5TGFiZWwiLCJ2YWx1ZSIsInN0YXJ0UmVxdWVzdCIsIndhaXRGb3JSZXF1ZXN0IiwiX3JlcXVlc3QkcG9zdERhdGFKU09OIiwiZW5kc1dpdGgiLCJ3aXphcmRfY29tbWFuZCIsImFjdGlvbiIsInN1Ym1pdCIsInJlcXVlc3RlZCIsIndpemFyZF9jb250ZXh0IiwidGVjaG5vbG9naWVzIiwiY29udGludWl0eSIsImFydGlmYWN0cyIsImZpbmlzaGVkIiwidGVjaG5vbG9neSIsImNoZWNrIiwidG9CZURpc2FibGVkIiwic2VsZWN0T3B0aW9uIiwidG9IYXZlVmFsdWUiLCJ1bmRlZmluZWQiLCJyZWplY3RzIiwidG9UaHJvdyIsImZpbmRpbmdzIiwiY29kZSIsInRvQ29udGFpbiIsInJhdGVfcmV2aWV3X3Byb3Bvc2FscyIsImkyYyIsInBhcmFtZXRlcl9wcm92ZW5hbmNlIiwiYml0cmF0ZSIsInNvdXJjZSIsImludGVyZmFjZXMiLCJkb21haW4iLCJ1bml0Iiwib3JpZ2luYWwiLCJpbXBvcnQiLCJtZXRhIiwibWV0YWRhdGEiLCJwYXJzZSIsImJhc2VsaW5lIiwicHJvbXB0IiwicmVwbGFjZSIsInBvc3QiLCJvcGVyYXRpb25faWQiLCJ0YXJnZXQiLCJleGNsdWRlZFNpZ25hbElkcyIsImZpeHR1cmUiLCJyZXF1ZXN0X3NoYTI1NiIsImdyYXBoIiwiY2x1c3Rlcl9pZCIsIm5ldHdvcmtfaWQiLCJuZXR3b3JrX2xhYmVsIiwiYnVzX25hbWUiLCJjb250cm9sbGVycyIsImVjdSIsInNlbnNvcnMiLCJhY3R1YXRvcnMiLCJobWlfcm91dGVzIiwicHJvamVjdF9uYW1lIiwic2NvcGVfaWRzIiwibW9kZSIsInByb2Nlc3NfaWRzIiwidGFzayIsIm9yaWdpbmFsTmV0d29ya3MiLCJhbWVuZCIsIm5ldHdvcmtzIiwiZXhwYW5kIiwiaWRlbnRpdHkiLCJzeXN0ZW1fb3duZXJfaWQiLCJzZW5zb3JOZXR3b3JrIiwidG9wb2xvZ3kiLCJsb2NhbEVkZ2UiLCJlZGdlcyIsImVkZ2UiLCJwaHlzaWNhbE5ldHdvcmtJZCIsImJ1cyIsInZhbHVlcyIsInJvdXRpbmdNZXRhZGF0YSIsInRvQ29udGFpbkVxdWFsIiwib2JqZWN0Q29udGFpbmluZyIsImFwcHJvdmFsU3RhdGUiLCJwcm90b2NvbCIsInNpZGUiLCJoYXJkd2FyZUlkIiwibm9kZSIsImVuZ2luZWVyaW5nSWQiLCJwb3J0cyIsInR4cngiLCJoYXNUZXh0Iiwic2VsZWN0ZWQiLCJ0b0JlQ2hlY2tlZCIsInVuY2hlY2siLCJfcmVxdWVzdCRwb3N0RGF0YUpTT04yIiwic3lzdGVtX2NsdXN0ZXJfYXNzaWdubWVudHMiLCJjbHVzdGVyIiwiX2NsdXN0ZXIkZnVuY3Rpb25hbF9yIiwiZnVuY3Rpb25hbF9yb3V0ZXMiLCJvZmYiLCJyb3V0ZSIsImV4Y2x1ZGVkX3NpZ25hbHMiLCJyZWxvYWQiLCJyZXZpZXciLCJ0b0NvbnRhaW5UZXh0IiwidG9IYXZlQXR0cmlidXRlIiwiUmVnRXhwIiwiYXBwbHkiLCJwcm9wb3NhbF9pZCIsImdlYXJib3giLCJlbW90b3IiXSwic291cmNlcyI6WyJ3aXphcmQuc3BlYy50cyJdLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyB0ZXN0LCBleHBlY3QsIHR5cGUgUGFnZSB9IGZyb20gJ3BsYXl3cmlnaHQvdGVzdCc7XHJcbmltcG9ydCB7IHJlYWRGaWxlIH0gZnJvbSAnbm9kZTpmcy9wcm9taXNlcyc7XHJcbmltcG9ydCB7IHJhbmRvbVVVSUQgfSBmcm9tICdub2RlOmNyeXB0byc7XHJcbmltcG9ydCB7IGV4ZWNGaWxlU3luYyB9IGZyb20gJ25vZGU6Y2hpbGRfcHJvY2Vzcyc7XHJcbmltcG9ydCB7IFdpemFyZFByb2dyZXNzV2F0Y2hkb2csIFdJWkFSRF9TVEVQUywgV0laQVJEX0RPTkUgfSBmcm9tICcuL3N1cHBvcnQvd2l6YXJkLXByb2dyZXNzLXdhdGNoZG9nJztcclxuXHJcbmNvbnN0IHN0ZXBzID0gV0laQVJEX1NURVBTO1xyXG5jb25zdCBkb25lID0gV0laQVJEX0RPTkU7XHJcbnR5cGUgV3JpdGVUaW1pbmcgPSB7IHVybDogc3RyaW5nOyBzdGFydGVkOiBudW1iZXI7IGR1cmF0aW9uX21zPzogbnVtYmVyOyBzdGF0dXM/OiBudW1iZXI7IGZhaWx1cmU/OiBzdHJpbmcgfTtcclxuY29uc3Qgd3JpdGVUaW1pbmdzID0gbmV3IE1hcDxzdHJpbmcsIFdyaXRlVGltaW5nW10+KCk7XHJcbmNvbnN0IHdvcmtmbG93UGFnZUZhaWx1cmVzID0gbmV3IFdlYWtNYXA8UGFnZSwgc3RyaW5nW10+KCk7XHJcbmNvbnN0IHByb2dyZXNzTWlsZXN0b25lcyA9IG5ldyBNYXA8c3RyaW5nLCB1bmtub3duW10+KCk7XHJcblxyXG50ZXN0LmJlZm9yZUVhY2goYXN5bmMgKHsgcGFnZSB9LCBpbmZvKSA9PiB7XHJcbiAgY29uc3Qgcm93czogV3JpdGVUaW1pbmdbXSA9IFtdO1xyXG4gIHdyaXRlVGltaW5ncy5zZXQoaW5mby50ZXN0SWQsIHJvd3MpO1xyXG4gIHdvcmtmbG93UGFnZUZhaWx1cmVzLnNldChwYWdlLCBbXSk7XHJcbiAgcHJvZ3Jlc3NNaWxlc3RvbmVzLnNldChpbmZvLnRlc3RJZCwgW10pO1xyXG4gIGNvbnN0IHJlcXVlc3RzID0gbmV3IE1hcDxvYmplY3QsIFdyaXRlVGltaW5nPigpO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3QnLCByZXF1ZXN0ID0+IHtcclxuICAgIGlmICghWydQT1NUJywgJ1BVVCcsICdQQVRDSCcsICdERUxFVEUnXS5pbmNsdWRlcyhyZXF1ZXN0Lm1ldGhvZCgpKSkgcmV0dXJuO1xyXG4gICAgY29uc3Qgcm93ID0geyB1cmw6IHJlcXVlc3QudXJsKCksIHN0YXJ0ZWQ6IERhdGUubm93KCkgfTtcclxuICAgIHJvd3MucHVzaChyb3cpOyByZXF1ZXN0cy5zZXQocmVxdWVzdCwgcm93KTtcclxuICB9KTtcclxuICBwYWdlLm9uKCdyZXNwb25zZScsIHJlc3BvbnNlID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXNwb25zZS5yZXF1ZXN0KCkpO1xyXG4gICAgaWYgKHJvdykgcm93LnN0YXR1cyA9IHJlc3BvbnNlLnN0YXR1cygpO1xyXG4gICAgaWYgKHJlc3BvbnNlLnN0YXR1cygpID09PSA0MTMgJiYgL15cXC9hcGlcXC9lbmdpbmVlcmluZ1xcL3dvcmtmbG93KD86XFwvfCQpLy50ZXN0KG5ldyBVUkwocmVzcG9uc2UudXJsKCkpLnBhdGhuYW1lKSkge1xyXG4gICAgICB3b3JrZmxvd1BhZ2VGYWlsdXJlcy5nZXQocGFnZSkhLnB1c2goYEhUVFAgNDEzOiAke3Jlc3BvbnNlLnVybCgpfWApO1xyXG4gICAgfVxyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3RmaW5pc2hlZCcsIHJlcXVlc3QgPT4ge1xyXG4gICAgY29uc3Qgcm93ID0gcmVxdWVzdHMuZ2V0KHJlcXVlc3QpO1xyXG4gICAgaWYgKHJvdykgcm93LmR1cmF0aW9uX21zID0gRGF0ZS5ub3coKSAtIHJvdy5zdGFydGVkO1xyXG4gIH0pO1xyXG4gIHBhZ2Uub24oJ3JlcXVlc3RmYWlsZWQnLCByZXF1ZXN0ID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXF1ZXN0KTtcclxuICAgIGlmIChyb3cpIHsgcm93LmR1cmF0aW9uX21zID0gRGF0ZS5ub3coKSAtIHJvdy5zdGFydGVkOyByb3cuZmFpbHVyZSA9IHJlcXVlc3QuZmFpbHVyZSgpPy5lcnJvclRleHQ7IH1cclxuICB9KTtcclxufSk7XHJcblxyXG50ZXN0LmFmdGVyRWFjaChhc3luYyAoeyBwYWdlIH0sIGluZm8pID0+IHtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd3JpdGUtcmVxdWVzdC10aW1pbmdzJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh3cml0ZVRpbWluZ3MuZ2V0KGluZm8udGVzdElkKSB8fCBbXSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgYXdhaXQgaW5mby5hdHRhY2goJ3dvcmtmbG93LXByb2dyZXNzLWJvdW5kYXJpZXMnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHByb2dyZXNzTWlsZXN0b25lcy5nZXQoaW5mby50ZXN0SWQpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICBhd2FpdCBpbmZvLmF0dGFjaCgnd29ya2Zsb3ctcGFnZS1mYWlsdXJlcycsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpIHx8IFtdKSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICB3cml0ZVRpbWluZ3MuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBwcm9ncmVzc01pbGVzdG9uZXMuZGVsZXRlKGluZm8udGVzdElkKTtcclxuICBleHBlY3Qod29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpLCAnVGhlIHVuZGVybHlpbmcgZW5naW5lZXJpbmcgcGFnZSBtdXN0IHJlbWFpbiByZWFkYWJsZSB0aHJvdWdob3V0IHJlbG9hZCBhbmQgcmVjb3ZlcnkuJykudG9FcXVhbChbXSk7XHJcbn0pO1xyXG5cclxuYXN5bmMgZnVuY3Rpb24gYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeShwYWdlOiBQYWdlKSB7XHJcbiAgZXhwZWN0KHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSwgJ0Egd29ya2luZyB3aXphcmQgb3ZlcmxheSBtdXN0IG5vdCBjb25jZWFsIGEgd29ya2Zsb3cgSFRUUCA0MTMuJykudG9FcXVhbChbXSk7XHJcbiAgZXhwZWN0KGF3YWl0IHBhZ2UuZ2V0QnlUZXh0KCdFbmdpbmVlcmluZy1BUEkgbmljaHQgZXJyZWljaGJhcicsIHsgZXhhY3Q6IHRydWUgfSkuaXNWaXNpYmxlKCksXHJcbiAgICAnVGhlIHVuZGVybHlpbmcgZW5naW5lZXJpbmcgcGFnZSBtdXN0IG5vdCBzaG93IGl0cyBBUEkgZXJyb3Igdmlldy4nKS50b0JlKGZhbHNlKTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVhZFByb2plY3QocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBwYXRoOiBzdHJpbmcpIHtcclxuICBjb25zdCByZXN1bHQgPSBhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KHBhdGgsIHsgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiA2MF8wMDAgfSk7XHJcbiAgaWYgKCFyZXN1bHQub2soKSkgdGhyb3cgbmV3IEVycm9yKGAke3BhdGh9OiBIVFRQICR7cmVzdWx0LnN0YXR1cygpfSAkeyhhd2FpdCByZXN1bHQudGV4dCgpKS5zbGljZSgwLCA0MDAwKX1gKTtcclxuICByZXR1cm4gcmVzdWx0Lmpzb24oKTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVhZFdhcm5pbmdSZXZpZXdTdGF0ZShwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcpIHtcclxuICBjb25zdCBhdXRob3JpdHkgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICBjb25zdCBwYXJhbWV0ZXJzID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycpO1xyXG4gIGNvbnN0IHZlcmlmaWVkID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgZXhwZWN0KHBhcmFtZXRlcnMucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcclxuICBleHBlY3QoYXV0aG9yaXR5LnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgZXhwZWN0KHZlcmlmaWVkLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBbJ3J1bl9pZCcsICdyZXF1ZXN0X3JldmlzaW9uJ10pXHJcbiAgICBleHBlY3QodmVyaWZpZWQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LltmaWVsZF0pLnRvQmUoYXV0aG9yaXR5LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5bZmllbGRdKTtcclxuICByZXR1cm4geyBwcm9qZWN0X2lkOiB2ZXJpZmllZC5wcm9qZWN0X2lkLCBzdGF0dXNlczogdmVyaWZpZWQuc3RhdHVzZXMsXHJcbiAgICBjb250ZXh0OiB7IGFnZW50X2V4ZWN1dGlvbjogeyBydW5faWQ6IHZlcmlmaWVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQsXHJcbiAgICAgIHJlcXVlc3RfcmV2aXNpb246IHZlcmlmaWVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5yZXF1ZXN0X3JldmlzaW9uIH0gfSxcclxuICAgIHBhcmFtZXRlcnM6IHsgcHJlZmxpZ2h0X3dhcm5pbmdfYXBwcm92YWw6IHBhcmFtZXRlcnMucGFyYW1ldGVycy5wcmVmbGlnaHRfd2FybmluZ19hcHByb3ZhbCB9IH07XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIG9wZW5XaXphcmQocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nKSB7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvL2VuZ2luZWVyaW5nP2Fzc2lzdGFudD1wcm9qZWN0JnByb2plY3Q9JHtwcm9qZWN0fWAsIHsgd2FpdFVudGlsOiAnbG9hZCcgfSk7XHJcbiAgY29uc3QgZGlhbG9nID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IGFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkocGFnZSk7XHJcbiAgcmV0dXJuIGRpYWxvZztcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gYWxsT2JqZWN0cyhwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIHJlc291cmNlOiBzdHJpbmcpIHtcclxuICBjb25zdCBpdGVtczogYW55W10gPSBbXTtcclxuICBmb3IgKGxldCBvZmZzZXQgPSAwOyA7IG9mZnNldCArPSA1MDApIHtcclxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvJHtyZXNvdXJjZX0/bGltaXQ9NTAwJm9mZnNldD0ke29mZnNldH1gKTtcclxuICAgIGl0ZW1zLnB1c2goLi4ucmVzcG9uc2UuaXRlbXMpO1xyXG4gICAgaWYgKHJlc3BvbnNlLml0ZW1zLmxlbmd0aCA8IDUwMCkgcmV0dXJuIGl0ZW1zO1xyXG4gIH1cclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2U6IFBhZ2UsIGNyYXNoID0gZmFsc2UpIHtcclxuICBjb25zdCBjb250YWluZXIgPSBwcm9jZXNzLmVudi5OSVNfRTJFX0FQUF9DT05UQUlORVIhO1xyXG4gIGV4cGVjdChjb250YWluZXIpLnRvTWF0Y2goL15uaXMtZTJlLWFwcC1bYS1mMC05XSskLyk7XHJcbiAgY29uc3QgZG9ja2VyID0gcHJvY2Vzcy5lbnYuTklTX1RFU1RfRE9DS0VSIHx8ICdkb2NrZXInO1xyXG4gIGNvbnN0IGxhYmVsID0gZXhlY0ZpbGVTeW5jKGRvY2tlciwgWydpbnNwZWN0JywgY29udGFpbmVyLCAnLS1mb3JtYXQnLCAne3tpbmRleCAuQ29uZmlnLkxhYmVscyBcIm5ldHdvcmtpcy50ZXN0XCJ9fSddLCB7IGVuY29kaW5nOiAndXRmOCcgfSkudHJpbSgpO1xyXG4gIGV4cGVjdChsYWJlbCkudG9CZSgnZGlzcG9zYWJsZScpO1xyXG4gIGV4ZWNGaWxlU3luYyhkb2NrZXIsIFsncmVzdGFydCcsIC4uLihjcmFzaCA/IFsnLXQnLCAnMCddIDogW10pLCBjb250YWluZXJdLCB7IHRpbWVvdXQ6IDYwXzAwMCB9KTtcclxuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICB0cnkgeyByZXR1cm4gKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvcmVhZHknLCB7IHRpbWVvdXQ6IDIwMDAgfSkpLm9rKCk7IH0gY2F0Y2ggeyByZXR1cm4gZmFsc2U7IH1cclxuICB9LCB7IHRpbWVvdXQ6IDEyMF8wMDAgfSkudG9CZSh0cnVlKTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gdmVyaWZ5U2lnbmFsQ29udHJhY3RzKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgZXhwZWN0ZWQ6IFJlY29yZDxzdHJpbmcsIHVua25vd24+KSB7XHJcbiAgY29uc3QgW2hhcmR3YXJlLCBmdW5jdGlvbnMsIG1lc3NhZ2VzLCBzaWduYWxzXSA9IGF3YWl0IFByb21pc2UuYWxsKFxyXG4gICAgWydoYXJkd2FyZS1ub2RlcycsICdmdW5jdGlvbnMnLCAnbWVzc2FnZXMnLCAnc2lnbmFscyddLm1hcChyZXNvdXJjZSA9PiBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsIHJlc291cmNlKSkpO1xyXG4gIGNvbnN0IG5vZGVzID0gbmV3IE1hcChoYXJkd2FyZS5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBmdW5jdGlvbnNCeUlkID0gbmV3IE1hcChmdW5jdGlvbnMubWFwKGl0ZW0gPT4gW2l0ZW0uaWQsIGl0ZW1dKSk7XHJcbiAgY29uc3QgbWVzc2FnZXNCeUlkID0gbmV3IE1hcChtZXNzYWdlcy5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBjb250cmFjdHM6IFJlY29yZDxzdHJpbmcsIHVua25vd24+ID0ge307XHJcbiAgZm9yIChjb25zdCBzaWduYWwgb2Ygc2lnbmFscykge1xyXG4gICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzQnlJZC5nZXQoc2lnbmFsLm1lc3NhZ2VfaWQpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UpLnRvQmVUcnV0aHkoKTtcclxuICAgIGNvbnN0IHJlZmVyZW5jZSA9IG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LnByb2R1Y2VyX3JlZjtcclxuICAgIGNvbnN0IGZuID0gZnVuY3Rpb25zQnlJZC5nZXQocmVmZXJlbmNlKTtcclxuICAgIGNvbnN0IG93bmVyID0gbm9kZXMuZ2V0KHJlZmVyZW5jZSkgfHwgKGZuICYmIG5vZGVzLmdldChmbi5oYXJkd2FyZV9ub2RlX2lkKSk7XHJcbiAgICBjb25zdCBwcm9kdWNlciA9IG93bmVyPy5kZXZpY2VfdHlwZSA9PT0gJ0dhdGV3YXknID8gJyRnYXRld2F5JyA6IChub2Rlcy5nZXQocmVmZXJlbmNlKSB8fCBmbik/Lm5hbWU7XHJcbiAgICBleHBlY3QocHJvZHVjZXIpLnRvQmVUcnV0aHkoKTtcclxuICAgIGNvbnN0IGtleSA9IFtwcm9kdWNlciwgbWVzc2FnZS5uYW1lLCBzaWduYWwubmFtZV0uam9pbignIDo6ICcpO1xyXG4gICAgZXhwZWN0KGNvbnRyYWN0c1trZXldLCAnU2VtYW50aWMgc2lnbmFsIGlkZW50aXR5IG11c3QgYmUgdW5pcXVlOiAnICsga2V5KS50b0JlVW5kZWZpbmVkKCk7XHJcbiAgICBjb250cmFjdHNba2V5XSA9IHtcclxuICAgICAgLi4uT2JqZWN0LmZyb21FbnRyaWVzKFsnc3RhcnRfYml0JywgJ2xlbmd0aF9iaXRzJywgJ2RhdGFfdHlwZScsICdmYWN0b3InLCAnb2Zmc2V0X3ZhbHVlJyxcclxuICAgICAgICAndW5pdCcsICdtaW5fdmFsdWUnLCAnbWF4X3ZhbHVlJywgJ2J5dGVfb3JkZXInXS5tYXAoZmllbGQgPT4gW2ZpZWxkLCBzaWduYWxbZmllbGRdID8/IG51bGxdKSksXHJcbiAgICAgIGVudW1fdmFsdWVzOiBzaWduYWwuZGF0YT8uZW51bV92YWx1ZXMgPz8gbnVsbCxcclxuICAgICAgc2VtYW50aWNfdHlwZTogc2lnbmFsLnNlbWFudGljPy5zZW1hbnRpY190eXBlID8/IG51bGwsXHJcbiAgICAgIGdlbmVyYXRpb25fcm9sZTogc2lnbmFsLmNvbmZpZ3VyYXRpb24/LmdlbmVyYXRpb25fcm9sZSA/PyBudWxsLFxyXG4gICAgfTtcclxuICB9XHJcbiAgZXhwZWN0KGNvbnRyYWN0cywgJ0V2ZXJ5IG9yaWdpbmFsIHNpZ25hbCBhbmQgaXRzIGV4cGxpY2l0IGVuY29kaW5nIG11c3Qgc3Vydml2ZSBnZW5lcmF0aW9uLicpLnRvRXF1YWwoZXhwZWN0ZWQpO1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiB2ZXJpZnlBcnRpZmFjdHMocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBtaW5pbXVtQ2Fub25pY2FsU2lnbmFsczogbnVtYmVyLCBpbnRlcm5hbENvbnRyb2xsZXI/OiBzdHJpbmcpIHtcclxuICBjb25zdCB3b3JrZmxvdyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gIGV4cGVjdChPYmplY3Qua2V5cyh3b3JrZmxvdy5zdGF0dXNlcykuc29ydCgpKS50b0VxdWFsKFsuLi5zdGVwc10uc29ydCgpKTtcclxuICBmb3IgKGNvbnN0IHN0ZXAgb2Ygc3RlcHMpIGV4cGVjdChkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXSksIGAke3N0ZXB9OiAke3dvcmtmbG93LnN0YXR1c2VzW3N0ZXBdfWApLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBqb2JzID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnM7XHJcbiAgZXhwZWN0KGpvYnMpLnRvSGF2ZUxlbmd0aCgxKTtcclxuICBleHBlY3Qoam9ic1swXS5zdGF0dXMpLnRvQmUoJ2NvbXBsZXRlZCcpO1xyXG4gIGNvbnN0IHNuYXBzaG90cyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3NuYXBzaG90cycpO1xyXG4gIGNvbnN0IHNuYXBzaG90ID0gc25hcHNob3RzLnNpbXVsYXRpb25zLmZpbmQoKGl0ZW06IHsgam9iX2lkOiBzdHJpbmcgfSkgPT4gaXRlbS5qb2JfaWQgPT09IGpvYnNbMF0uaWQpO1xyXG4gIGV4cGVjdChzbmFwc2hvdCkudG9CZVRydXRoeSgpO1xyXG4gIGNvbnN0IGZ1bGwgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9zaW11bGF0aW9uLXNuYXBzaG90cy8ke3NuYXBzaG90LmlkfWApO1xyXG4gIGNvbnN0IGFzc2Vzc21lbnQgPSBmdWxsLnJlc3VsdC5hc3Nlc3NtZW50O1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnNjb3BlX21vZGUpLnRvQmUoJ0FMTCcpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLmNvbXBsZXRlKS50b0JlKHRydWUpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LmNvbmZvcm1hbmNlKS50b0JlKCdQQVNTJyk7XHJcbiAgZXhwZWN0KGFzc2Vzc21lbnQuZmFpbGVkX3JvdXRlX2NvdW50KS50b0JlKDApO1xyXG4gIGNvbnN0IHNpZ25hbHMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyk7XHJcbiAgZXhwZWN0KHNpZ25hbHMubGVuZ3RoLCAnVGhlIGZ1bGwgY2Fub25pY2FsIHNpZ25hbCBpbnZlbnRvcnkgbXVzdCBzdXJ2aXZlIGdlbmVyYXRpb24uJykudG9CZUdyZWF0ZXJUaGFuT3JFcXVhbChtaW5pbXVtQ2Fub25pY2FsU2lnbmFscyk7XHJcbiAgY29uc3QgZXhjbHVkZWQgPSBhc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnRyYW5zcG9ydF9leGNsdXNpb25zID8/IFtdO1xyXG4gIGNvbnN0IG1lc3NhZ2VzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnbWVzc2FnZXMnKTtcclxuICBmb3IgKGNvbnN0IGl0ZW0gb2YgZXhjbHVkZWQpIHtcclxuICAgIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKHJvdyA9PiByb3cuaWQgPT09IGl0ZW0ubWVzc2FnZV9pZCk7XHJcbiAgICBleHBlY3QobWVzc2FnZSwgYEV4Y2x1ZGVkIG1lc3NhZ2UgJHtpdGVtLm1lc3NhZ2VfaWR9IG11c3QgZXhpc3QuYCkudG9CZVRydXRoeSgpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5yb3V0aW5nLmVuYWJsZWQpLnRvQmUoZmFsc2UpO1xyXG4gICAgY29uc3QgY29udHJhY3QgPSBtZXNzYWdlLmNvbmZpZ3VyYXRpb24uY29tbXVuaWNhdGlvbl9jb250cmFjdDtcclxuICAgIGV4cGVjdChjb250cmFjdC5jb25zdW1lcl9yZWZzKS50b0VxdWFsKFtdKTtcclxuICAgIGV4cGVjdChpdGVtLnJlYXNvbl9jb2RlKS50b0JlKGNvbnRyYWN0LnJvbGUgPT09ICdJTlRFUk5BTF9TVEFURSdcclxuICAgICAgPyAnSU5URVJOQUxfU1RBVEVfTk9UX1JPVVRFRCcgOiAnRVhQTElDSVRfRlVOQ1RJT05fT1VUUFVUX05PVF9ST1VURUQnKTtcclxuICB9XHJcbiAgaWYgKGludGVybmFsQ29udHJvbGxlcikge1xyXG4gICAgY29uc3Qgbm9kZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gICAgY29uc3QgY29udHJvbGxlciA9IG5vZGVzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09IGludGVybmFsQ29udHJvbGxlcik7XHJcbiAgICBleHBlY3QoZXhjbHVkZWQubGVuZ3RoKS50b0JlR3JlYXRlclRoYW4oMCk7XHJcbiAgICBmb3IgKGNvbnN0IGl0ZW0gb2YgZXhjbHVkZWQpIHtcclxuICAgICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzLmZpbmQocm93ID0+IHJvdy5pZCA9PT0gaXRlbS5tZXNzYWdlX2lkKTtcclxuICAgICAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0KS50b01hdGNoT2JqZWN0KHsgcm9sZTogJ0lOVEVSTkFMX1NUQVRFJywgc2NvcGU6ICdJTlRFUk5BTCcsIHByb2R1Y2VyX3JlZjogY29udHJvbGxlci5pZCwgY29uc3VtZXJfcmVmczogW10gfSk7XHJcbiAgICB9XHJcbiAgfVxyXG4gIGNvbnN0IGV4Y2x1ZGVkU2lnbmFscyA9IG5ldyBTZXQoZXhjbHVkZWQuZmxhdE1hcCgoaXRlbTogeyBzaWduYWxfaWRzOiBzdHJpbmdbXSB9KSA9PiBpdGVtLnNpZ25hbF9pZHMpKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQsICdBTEwgbXVzdCBvYnNlcnZlIGV2ZXJ5IGNhbm9uaWNhbCBzaWduYWwgd2l0aCBhIHRyYW5zcG9ydCBvYmxpZ2F0aW9uLicpLnRvQmUoc2lnbmFscy5sZW5ndGggLSBleGNsdWRlZFNpZ25hbHMuc2l6ZSk7XHJcbiAgZm9yIChjb25zdCBrZXkgb2YgWydtaXNzaW5nX29ic2VydmVkX3NpZ25hbF9pZHMnLCAnbWlzc2luZ19vYnNlcnZlZF9yb3V0ZV9pZHMnLCAnbWlzc2luZ19vYnNlcnZlZF9uZXR3b3JrX2lkcyddKSBleHBlY3QoYXNzZXNzbWVudFtrZXldKS50b0VxdWFsKFtdKTtcclxuICBjb25zdCB0cmFjZSA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsIGAvYXBpL3NpbXVsYXRpb25zLyR7am9ic1swXS5pZH0vdHJhY2Utd2luZG93P2xpbWl0PTEwYCk7XHJcbiAgZXhwZWN0KHRyYWNlLmNvdW50KS50b0JlR3JlYXRlclRoYW4oMCk7XHJcbiAgZXhwZWN0KHRyYWNlLmV2ZW50cy5zb21lKChpdGVtOiB7IHNpZ25hbHM/OiB1bmtub3duW10gfSkgPT4gaXRlbS5zaWduYWxzICYmIE9iamVjdC5rZXlzKGl0ZW0uc2lnbmFscykubGVuZ3RoKSkudG9CZVRydXRoeSgpO1xyXG4gIHJldHVybiB7IHdvcmtmbG93LCBqb2I6IGpvYnNbMF0uaWQsIGFzc2Vzc21lbnQgfTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcmVzdGFydDogYm9vbGVhbiwgZXhwZWN0ZWRIYXJkd2FyZTogc3RyaW5nW10gPSBbXSwgY3Jhc2hTaW11bGF0aW9uID0gZmFsc2UsXHJcbiAgZXhwZWN0ZWRTaWduYWxzPzogUmVjb3JkPHN0cmluZywgdW5rbm93bj4sIGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQ/OiAoKSA9PiBQcm9taXNlPHZvaWQ+LCBzdG9wT25FdmlkZW5jZUJsb2NrID0gZmFsc2UpIHtcclxuICBsZXQgcmV2aWV3Q291bnQgPSAwO1xyXG4gIGxldCBydW5JZDogc3RyaW5nIHwgdW5kZWZpbmVkO1xyXG4gIGNvbnN0IHJldmlld2VkID0gbmV3IFNldDxzdHJpbmc+KCk7XHJcbiAgbGV0IHJlc3RhcnRlZEpvYklkOiBzdHJpbmcgfCB1bmRlZmluZWQ7XHJcbiAgbGV0IHdhdGNoZG9nID0gbmV3IFdpemFyZFByb2dyZXNzV2F0Y2hkb2cocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gIGZvciAobGV0IGNoZWNrcG9pbnQgPSAwOyBjaGVja3BvaW50IDwgMTY7IGNoZWNrcG9pbnQrKykge1xyXG4gICAgbGV0IHdvcmtmbG93OiBhbnk7XHJcbiAgICBsZXQgcHJvcG9zYWxJZCA9ICcnO1xyXG4gICAgbGV0IHJlYWR5VmVyc2lvbiA9ICcnO1xyXG4gICAgbGV0IHJlYWR5U2luY2UgPSAwO1xyXG4gICAgY29uc3QgaXNDaGVja3BvaW50ID0gYXN5bmMgKCkgPT4ge1xyXG4gICAgICB3YXRjaGRvZy5yZW1haW5pbmcocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gICAgICBhd2FpdCBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2UpO1xyXG4gICAgICB3b3JrZmxvdyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICBjb25zdCBwcm9ncmVzcyA9IHdhdGNoZG9nLm9ic2VydmUod29ya2Zsb3csIHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICAgICAgaWYgKHByb2dyZXNzLmFkdmFuY2VkKSBwcm9ncmVzc01pbGVzdG9uZXMuZ2V0KHRlc3QuaW5mbygpLnRlc3RJZCkhLnB1c2goe1xyXG4gICAgICAgIGF0OiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksIGZyb250aWVyOiBwcm9ncmVzcy5mcm9udGllcixcclxuICAgICAgICBjb21wbGV0ZWRUaHJvdWdoOiBzdGVwc1twcm9ncmVzcy5mcm9udGllciAtIDFdLFxyXG4gICAgICAgIHByb2plY3Q6IHdvcmtmbG93LnByb2plY3RfaWQsIGV4ZWN1dGlvbjogd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24sXHJcbiAgICAgIH0pO1xyXG4gICAgICBpZiAoY3Jhc2hTaW11bGF0aW9uICYmICFyZXN0YXJ0ZWRKb2JJZCAmJiBkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlcy52YWxpZGF0aW9uKSkge1xyXG4gICAgICAgIGNvbnN0IGpvYnMgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icztcclxuICAgICAgICBjb25zdCBydW5uaW5nID0gam9icy5maW5kKChqb2I6IHsgc3RhdHVzOiBzdHJpbmcgfSkgPT4gam9iLnN0YXR1cyA9PT0gJ3J1bm5pbmcnKTtcclxuICAgICAgICBpZiAocnVubmluZykge1xyXG4gICAgICAgICAgcmVzdGFydGVkSm9iSWQgPSBydW5uaW5nLmlkO1xyXG4gICAgICAgICAgYXdhaXQgcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2UsIHRydWUpO1xyXG4gICAgICAgICAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICAgICAgICAgIHJldHVybiBmYWxzZTtcclxuICAgICAgICB9XHJcbiAgICAgIH1cclxuICAgICAgaWYgKHN0ZXBzLmV2ZXJ5KHN0ZXAgPT4gZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXNbc3RlcF0pKSkgcmV0dXJuIHRydWU7XHJcbiAgICAgIGNvbnN0IGV4ZWN1dGlvbiA9IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uO1xyXG4gICAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JFVklFV19SRVFVSVJFRCcpIHtcclxuICAgICAgICBjb25zdCBjb252ZXJzYXRpb24gPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKTtcclxuICAgICAgICBwcm9wb3NhbElkID0gY29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsO1xyXG4gICAgICAgIC8vIFBvbGxpbmcgbWF5IHN0aWxsIGV4cG9zZSB0aGUganVzdC1hcHBsaWVkIHJldmlldyB3aGlsZSB0aGUgVUkgc3RhcnRzXHJcbiAgICAgICAgLy8gaXRzIGR1cmFibGUgY29udGludWF0aW9uLiBXYWl0IGZvciBhIGRpc3RpbmN0IHByb3Bvc2FsLCBub3QgaXRzIGxhYmVsLlxyXG4gICAgICAgIHJldHVybiBCb29sZWFuKHByb3Bvc2FsSWQpICYmICFyZXZpZXdlZC5oYXMocHJvcG9zYWxJZCk7XHJcbiAgICAgIH1cclxuICAgICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdSRUFEWV9UT19DT05USU5VRScgfHwgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24ucmVjb3ZlcmFibGUgPT09IHRydWUpKSB7XHJcbiAgICAgICAgaWYgKHJlYWR5VmVyc2lvbiAhPT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQpIHtcclxuICAgICAgICAgIHJlYWR5VmVyc2lvbiA9IGV4ZWN1dGlvbi51cGRhdGVkX2F0OyByZWFkeVNpbmNlID0gRGF0ZS5ub3coKTtcclxuICAgICAgICB9XHJcbiAgICAgICAgLy8gV2hpbGUgYSBsYXJnZSBjb250aW51YXRpb24gaXMgZ2VuZXJhdGluZywgdGhlIGxhc3QgY29tbWl0dGVkIHNlcnZlclxyXG4gICAgICAgIC8vIGNoZWNrcG9pbnQgY2FuIHN0aWxsIGJlIFJFQURZLiBBY3Qgb25seSB3aGVuIHRoZSBVSSBvZmZlcnMgaXQgdG9vLlxyXG4gICAgICAgIGNvbnN0IGJ1dHRvbiA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSlcclxuICAgICAgICAgIC5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1ZnRyYWcgZm9ydHNldHplbicsIGV4YWN0OiB0cnVlIH0pO1xyXG4gICAgICAgIHJldHVybiBEYXRlLm5vdygpIC0gcmVhZHlTaW5jZSA+IDUwMDAgJiYgYXdhaXQgYnV0dG9uLmV2YWx1YXRlQWxsKGJ1dHRvbnMgPT4gYnV0dG9ucy5zb21lKGJ1dHRvbiA9PiAhKGJ1dHRvbiBhcyBIVE1MQnV0dG9uRWxlbWVudCkuZGlzYWJsZWQgJiYgYnV0dG9uLmdldENsaWVudFJlY3RzKCkubGVuZ3RoID4gMCAmJiBnZXRDb21wdXRlZFN0eWxlKGJ1dHRvbikudmlzaWJpbGl0eSAhPT0gXCJoaWRkZW5cIikpO1xyXG4gICAgICB9XHJcbiAgICAgIHJldHVybiBbJ0JMT0NLRUQnLCAnRkFJTEVEJywgJ0lOQ09NUExFVEUnXS5pbmNsdWRlcyhleGVjdXRpb24/LnN0YXRlKTtcclxuICAgIH07XHJcbiAgICAvLyBBIHNpbmdsZSBwb2xsIHByZXZpb3VzbHkgdGltZWQgYWxsIG9mIENhcGFjaXR5IC0+IEludGVsbGlnZW5jZSB0b2dldGhlci5cclxuICAgIC8vIEJvdW5kIGVhY2ggZ2VudWluZSBzdGFnZSBhZHZhbmNlLCB3aGlsZSByZXRyaWVzIGFuZCByZXN0YXJ0cyByZXRhaW4gdGhlaXJcclxuICAgIC8vIHJlbWFpbmluZyBkZWFkbGluZS4gVGhlIGluZGVwZW5kZW50IDIwLW1pbnV0ZSB0ZXN0IHRpbWVvdXQgaXMgdW5jaGFuZ2VkLlxyXG4gICAgbGV0IGF0dGVtcHQgPSAwO1xyXG4gICAgd2hpbGUgKCFhd2FpdCBpc0NoZWNrcG9pbnQoKSkge1xyXG4gICAgICBjb25zdCByZW1haW5pbmcgPSB3YXRjaGRvZy5yZW1haW5pbmcocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gICAgICBhd2FpdCBwYWdlLndhaXRGb3JUaW1lb3V0KE1hdGgubWluKFs1MDAsIDEwMDAsIDIwMDBdW01hdGgubWluKGF0dGVtcHQrKywgMildLCByZW1haW5pbmcpKTtcclxuICAgIH1cclxuICAgIHJ1bklkID8/PSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQpLnRvQmUocnVuSWQpO1xyXG4gICAgaWYgKHN0ZXBzLmV2ZXJ5KHN0ZXAgPT4gZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXNbc3RlcF0pKSkge1xyXG4gICAgICBpZiAoY3Jhc2hTaW11bGF0aW9uKSBleHBlY3QocmVzdGFydGVkSm9iSWQsICdBIHJlYWwgcnVubmluZyBzaW11bGF0aW9uIG11c3QgYmUgb2JzZXJ2ZWQgYW5kIGludGVycnVwdGVkLicpLnRvQmVUcnV0aHkoKTtcclxuICAgICAgcmV0dXJuIHsgcnVuSWQsIHJldmlld2VkOiBbLi4ucmV2aWV3ZWRdLCByZXN0YXJ0ZWRKb2JJZCB9O1xyXG4gICAgfVxyXG4gICAgY29uc3QgZXhlY3V0aW9uID0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb247XHJcbiAgICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pO1xyXG4gICAgaWYgKHN0b3BPbkV2aWRlbmNlQmxvY2sgJiYgZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5ibG9ja2luZ19maW5kaW5ncz8ubGVuZ3RoKSB7XHJcbiAgICAgIHRocm93IG5ldyBFcnJvcihgV2l6YXJkIEJMT0NLRUQgYXQgJHtleGVjdXRpb24uc3RlcH06ICR7ZXhlY3V0aW9uLm1lc3NhZ2V9YCk7XHJcbiAgICB9XHJcbiAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ0JMT0NLRUQnICYmIGV4ZWN1dGlvbi5tZXNzYWdlPy5pbmNsdWRlcygnUkVBRFlfV0lUSF9XQVJOSU5HUycpKSB7XHJcbiAgICAgIGNvbnN0IGJlZm9yZVJldmlldyA9IGF3YWl0IHJlYWRXYXJuaW5nUmV2aWV3U3RhdGUocGFnZSwgcHJvamVjdCk7XHJcbiAgICAgIGNvbnN0IHByZWZsaWdodCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3ByZWZsaWdodCcpO1xyXG4gICAgICBjb25zdCB3YXJuaW5ncyA9IGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ1ByZWZsaWdodC1XYXJudW5nZW4nIH0pO1xyXG4gICAgICBhd2FpdCBleHBlY3Qod2FybmluZ3MuZ2V0QnlSb2xlKCdsaXN0aXRlbScpLmZpcnN0KCkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgICAgIGNvbnN0IHN0YXJ0ZWQgPSBwZXJmb3JtYW5jZS5ub3coKSwgc3RhcnRlZFdhbGwgPSBEYXRlLm5vdygpO1xyXG4gICAgICB3YXRjaGRvZy5yZW1haW5pbmcoc3RhcnRlZCk7XHJcbiAgICAgIGNvbnN0IGFwcHJvdmFsUmVzcG9uc2UgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiBuZXcgVVJMKHJlc3BvbnNlLnVybCgpKS5wYXRobmFtZSA9PT0gJy9hcGkvZW5naW5lZXJpbmcvcHJlZmxpZ2h0L3dhcm5pbmdzL2FwcHJvdmUnXHJcbiAgICAgICAgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcsIHsgdGltZW91dDogMTgwXzAwMCB9KTtcclxuICAgICAgYXdhaXQgd2FybmluZ3MuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdXYXJudW5nZW4gZnJlaWdlYmVuIHVuZCBmb3J0c2V0emVuJyB9KS5jbGljaygpO1xyXG4gICAgICBjb25zdCBhcHByb3ZlZCA9IGF3YWl0IGFwcHJvdmFsUmVzcG9uc2U7XHJcbiAgICAgIGNvbnN0IHJlY2VpcHQgPSBhd2FpdCBhcHByb3ZlZC5qc29uKCk7XHJcbiAgICAgIGNvbnN0IGFmdGVyUmV2aWV3ID0gYXdhaXQgcmVhZFdhcm5pbmdSZXZpZXdTdGF0ZShwYWdlLCBwcm9qZWN0KTtcclxuICAgICAgY29uc3QgcHJvb2YgPSB7IGJlZm9yZTogYmVmb3JlUmV2aWV3LCBhZnRlcjogYWZ0ZXJSZXZpZXcsIHNuYXBzaG90SWQ6IHByZWZsaWdodC5pZCxcclxuICAgICAgICByZXF1ZXN0UHJvamVjdDogYXBwcm92ZWQucmVxdWVzdCgpLmhlYWRlcnMoKVsneC1wcm9qZWN0LWlkJ10sIHN1Ym1pdHRlZDogYXBwcm92ZWQucmVxdWVzdCgpLnBvc3REYXRhSlNPTigpLFxyXG4gICAgICAgIHN0YXR1czogYXBwcm92ZWQuc3RhdHVzKCksIHJlc3BvbnNlOiByZWNlaXB0LCBzdGFydGVkLCBzdGFydGVkV2FsbCwgZmluaXNoZWRXYWxsOiBEYXRlLm5vdygpIH07XHJcbiAgICAgIGNvbnN0IGNvbW1pdHRlZEF0ID0gcGVyZm9ybWFuY2Uubm93KCk7XHJcbiAgICAgIGNvbnN0IGNvbW1pdHRlZCA9IHdhdGNoZG9nLmNvbW1pdFdhcm5pbmdSZXZpZXcocHJvb2YsIGNvbW1pdHRlZEF0KTtcclxuICAgICAgYXdhaXQgdGVzdC5pbmZvKCkuYXR0YWNoKCd2ZXJpZmllZC13YXJuaW5nLXJldmlldy1wcm9vZicsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9vZiwgY29tbWl0dGVkQXQsIGNvbW1pdHRlZCB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICAgICAgcHJvZ3Jlc3NNaWxlc3RvbmVzLmdldCh0ZXN0LmluZm8oKS50ZXN0SWQpIS5wdXNoKHsgYXQ6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSwgbWFudWFsV2FybmluZ0FwcHJvdmFsOiBjb21taXR0ZWQuYXBwcm92YWxJZGVudGl0eSxcclxuICAgICAgICBmcm9udGllcjogY29tbWl0dGVkLmZyb250aWVyLCBwcm9qZWN0LCBleGVjdXRpb246IGFmdGVyUmV2aWV3LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uLCBhcHByb3ZhbDogcmVjZWlwdC5hcHByb3ZhbCB9KTtcclxuICAgICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpKS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCxcclxuICAgICAgICB7IHRpbWVvdXQ6IGV4cGVjdGVkSGFyZHdhcmUubGVuZ3RoID4gMTAwID8gMTgwXzAwMCA6IDYwXzAwMCB9KS5ub3QudG9CZShleGVjdXRpb24udXBkYXRlZF9hdCk7XHJcbiAgICAgIGNvbnRpbnVlO1xyXG4gICAgfVxyXG4gICAgaWYgKFsnQkxPQ0tFRCcsICdGQUlMRUQnLCAnSU5DT01QTEVURSddLmluY2x1ZGVzKGV4ZWN1dGlvbj8uc3RhdGUpICYmIGV4ZWN1dGlvbi5yZWNvdmVyYWJsZSAhPT0gdHJ1ZSkge1xyXG4gICAgICBjb25zdCBjb252ZXJzYXRpb24gPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKTtcclxuICAgICAgY29uc3QgaWQgPSBjb252ZXJzYXRpb24uZGF0YT8uYWN0aXZlX3Byb3Bvc2FsO1xyXG4gICAgICBjb25zdCBwcm9wb3NhbCA9IGlkID8gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7aWR9YCkgOiBudWxsO1xyXG4gICAgICBhd2FpdCB0ZXN0LmluZm8oKS5hdHRhY2goJ3dpemFyZC1ibG9ja2VyJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IGV4ZWN1dGlvbixcclxuICAgICAgICBwcm9wb3NhbDogcHJvcG9zYWw/LmRhdGE/LnZhbGlkYXRpb25fcmVzdWx0LCB2aXNpYmxlOiBhd2FpdCBkaWFsb2cuaW5uZXJUZXh0KCkgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgICAgIHRocm93IG5ldyBFcnJvcihgV2l6YXJkICR7ZXhlY3V0aW9uLnN0YXRlfSBhdCAke2V4ZWN1dGlvbi5zdGVwfTogJHtleGVjdXRpb24ubWVzc2FnZX1gKTtcclxuICAgIH1cclxuICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnUkVBRFlfVE9fQ09OVElOVUUnIHx8IChleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLnJlY292ZXJhYmxlID09PSB0cnVlKSkge1xyXG4gICAgICBjb25zdCBidXR0b24gPSBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBdWZ0cmFnIGZvcnRzZXR6ZW4nLCBleGFjdDogdHJ1ZSB9KTtcclxuICAgICAgdHJ5IHtcclxuICAgICAgICBhd2FpdCBidXR0b24uY2xpY2soeyB0aW1lb3V0OiAyMDAwIH0pO1xyXG4gICAgICB9IGNhdGNoIChlcnJvcikge1xyXG4gICAgICAgIGNvbnN0IGxhdGVzdCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICAgIGlmIChsYXRlc3QuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQgPT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0ICYmIGF3YWl0IGJ1dHRvbi5ldmFsdWF0ZUFsbChidXR0b25zID0+IGJ1dHRvbnMuc29tZShidXR0b24gPT4gIShidXR0b24gYXMgSFRNTEJ1dHRvbkVsZW1lbnQpLmRpc2FibGVkICYmIGJ1dHRvbi5nZXRDbGllbnRSZWN0cygpLmxlbmd0aCA+IDAgJiYgZ2V0Q29tcHV0ZWRTdHlsZShidXR0b24pLnZpc2liaWxpdHkgIT09IFwiaGlkZGVuXCIpKSkgdGhyb3cgZXJyb3I7XHJcbiAgICAgICAgY29udGludWU7XHJcbiAgICAgIH1cclxuICAgICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgICAgIGNvbnN0IGxhdGVzdCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICAgIHJldHVybiBsYXRlc3QuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQgIT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0XHJcbiAgICAgICAgICB8fCBsYXRlc3QuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnN0YXRlID09PSAnUlVOTklORydcclxuICAgICAgICAgIHx8IGxhdGVzdC5zdGF0dXNlcz8uW2V4ZWN1dGlvbi5zdGVwXSA9PT0gJ0lOX1BST0dSRVNTJztcclxuICAgICAgfSwgeyB0aW1lb3V0OiA2MF8wMDAgfSkudG9CZSh0cnVlKTtcclxuICAgICAgY29udGludWU7XHJcbiAgICB9XHJcbiAgICBjb25zdCBjYW5kaWRhdGUgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCBgL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9wb3NhbHMvJHtwcm9wb3NhbElkfWApO1xyXG4gICAgaWYgKGNhbmRpZGF0ZS5kYXRhLnByb3Bvc2FsX3R5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnICYmIHJldmlld0NvdW50ID09PSAwICYmIGV4cGVjdGVkSGFyZHdhcmUubGVuZ3RoKSB7XHJcbiAgICAgIGNvbnN0IGhhcmR3YXJlID0gY2FuZGlkYXRlLmRhdGEuY2hhbmdlc1xyXG4gICAgICAgIC5maWx0ZXIoKGNoYW5nZTogeyBvYmplY3RfdHlwZTogc3RyaW5nIH0pID0+IGNoYW5nZS5vYmplY3RfdHlwZSA9PT0gJ0hhcmR3YXJlTm9kZScpXHJcbiAgICAgICAgLm1hcCgoY2hhbmdlOiB7IGRhdGE6IHsgbmFtZTogc3RyaW5nIH0gfSkgPT4gY2hhbmdlLmRhdGEubmFtZSk7XHJcbiAgICAgIGV4cGVjdChoYXJkd2FyZSwgJ1RoZSBVSSBtdXN0IHByZXNlcnZlIHRoZSBoYXJkd2FyZSBleHBsaWNpdGx5IG5hbWVkIGluIHRoZSB1c2VyIHJlcXVlc3QuJylcclxuICAgICAgICAudG9FcXVhbChleHBlY3QuYXJyYXlDb250YWluaW5nKGV4cGVjdGVkSGFyZHdhcmUpKTtcclxuICAgIH1cclxuICAgIGV4cGVjdChyZXZpZXdlZC5oYXMocHJvcG9zYWxJZCksICdUaGUgc2FtZSBwcm9wb3NhbCBtdXN0IG5vdCByZXF1ZXN0IHJldmlldyB0d2ljZS4nKS50b0JlKGZhbHNlKTtcclxuICAgIGNvbnN0IGFwcGx5UmVzcG9uc2UgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5pbmNsdWRlcyhgL3Byb3Bvc2Fscy8ke3Byb3Bvc2FsSWR9L2FwcHJvdmUtYXBwbHlgKSAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJywgeyB0aW1lb3V0OiAxODBfMDAwIH0pO1xyXG4gICAgY29uc3QgYXBwcm92YWwgPSBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6IC9eKEZyZWlnZWJlbiwgw7xiZXJuZWhtZW4gJiBmb3J0ZmFocmVufMOcYmVybmVobWVuICYgZm9ydGZhaHJlbikkLyB9KTtcclxuICAgIGF3YWl0IGV4cGVjdChhcHByb3ZhbCkudG9CZUVuYWJsZWQoeyB0aW1lb3V0OiA2MF8wMDAgfSk7XHJcbiAgICBhd2FpdCBhcHByb3ZhbC5jbGljaygpO1xyXG4gICAgY29uc3QgYXBwbGllZCA9IGF3YWl0IGFwcGx5UmVzcG9uc2U7XHJcbiAgICBpZiAoIWFwcGxpZWQub2soKSkgdGhyb3cgbmV3IEVycm9yKGBIVFRQICR7YXBwbGllZC5zdGF0dXMoKX06ICR7KGF3YWl0IGFwcGxpZWQudGV4dCgpKS5zbGljZSgwLCA0MDAwKX1gKTtcclxuICAgIGV4cGVjdCgoYXdhaXQgYXBwbGllZC5qc29uKCkpLmRhdGEuc3RhdHVzKS50b0JlKCdBUFBMSUVEJyk7XHJcbiAgICByZXZpZXdlZC5hZGQocHJvcG9zYWxJZCk7IHJldmlld0NvdW50Kys7XHJcbiAgICAvLyBBIGRpc3RpbmN0LCBhY3R1YWxseSBjb21taXR0ZWQgbWFudWFsIHJldmlldyBzdGFydHMgdGhlIG5leHQgYXV0b21hdGljXHJcbiAgICAvLyBzZWN0aW9uLiBJdHMgd3JpdGUgc3RpbGwgaGFzIHRoZSBzZXBhcmF0ZSB1bmNoYW5nZWQgMTgwLXNlY29uZCBsaW1pdC5cclxuICAgIHdhdGNoZG9nID0gbmV3IFdpemFyZFByb2dyZXNzV2F0Y2hkb2cocGVyZm9ybWFuY2Uubm93KCksIHdvcmtmbG93KTtcclxuICAgIGlmIChjYW5kaWRhdGUuZGF0YS5wcm9wb3NhbF90eXBlID09PSAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJyAmJiBleHBlY3RlZFNpZ25hbHMpIHtcclxuICAgICAgYXdhaXQgdmVyaWZ5U2lnbmFsQ29udHJhY3RzKHBhZ2UsIHByb2plY3QsIGV4cGVjdGVkU2lnbmFscyk7XHJcbiAgICB9XHJcbiAgICBpZiAocmV2aWV3Q291bnQgPT09IDEgJiYgYWZ0ZXJGaXJzdE1vZGVsQXBwbGllZCkge1xyXG4gICAgICBhd2FpdCBhZnRlckZpcnN0TW9kZWxBcHBsaWVkKCk7XHJcbiAgICAgIC8vIFRoaXMgb25lIHRlc3QgZXhwbGljaXRseSBzdWJtaXRzIEFNRU5EIGFuZCB3YWl0cyBmb3IgaXRzIHJlY2VpcHQuIE9ubHlcclxuICAgICAgLy8gdGhhdCBkZWxpYmVyYXRlIGFjdGlvbiBwZXJtaXRzIGJpbmRpbmcgaXRzIG5ldyByZXF1ZXN0IHJldmlzaW9uLlxyXG4gICAgICBjb25zdCBhbWVuZGVkID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/dmlldz1zdW1tYXJ5Jyk7XHJcbiAgICAgIGV4cGVjdChhbWVuZGVkLmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQpLnRvQmUocnVuSWQpO1xyXG4gICAgICB3YXRjaGRvZyA9IG5ldyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nKHBlcmZvcm1hbmNlLm5vdygpLCBhbWVuZGVkKTtcclxuICAgIH1cclxuICAgIGlmIChyZXZpZXdDb3VudCA9PT0gMSkgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTsgLy8gRHVyYWJsZSByZWxvYWQgYWZ0ZXIgYSByZWFsIGNvbW1pdC5cclxuICAgIGlmIChyZXN0YXJ0ICYmIHJldmlld0NvdW50ID09PSAyKSB7XHJcbiAgICAgIGF3YWl0IHJlc3RhcnRBcHBsaWNhdGlvbihwYWdlKTtcclxuICAgICAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICAgIH1cclxuICAgIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcclxuICAgICAgY29uc3QgY3VycmVudCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICByZXR1cm4gY3VycmVudC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCAhPT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQ7XHJcbiAgICB9LCB7IHRpbWVvdXQ6IDYwXzAwMCB9KS50b0JlKHRydWUpO1xyXG4gIH1cclxuICB0aHJvdyBuZXcgRXJyb3IoJ1dpemFyZCBleGNlZWRlZCAxNiByZXZpZXcvY29udGludWF0aW9uIGNoZWNrcG9pbnRzLicpO1xyXG59XHJcblxyXG50ZXN0KCduZXcgc21hbGwgd2l6YXJkIHRyYXZlcnNlcyBhbGwgbmluZSBzdGFnZXMgYW5kIHN1cnZpdmVzIHJlbG9hZC9yZXN0YXJ0IEBzbWFsbCcsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICBjb25zdCBlcnJvcnM6IHN0cmluZ1tdID0gW107IHBhZ2Uub24oJ3BhZ2VlcnJvcicsIGVycm9yID0+IGVycm9ycy5wdXNoKGVycm9yLm1lc3NhZ2UpKTtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtc21hbGwtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdQcm9qZWt0bmFtZScsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cubG9jYXRvcignI2VuZ2luZWVyaW5nLXByb2plY3QtbmFtZScpLmZpbGwoJ0UyRSBzbWFsbCcpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdQcm9qZWt0YmVzY2hyZWlidW5nJywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKCdFcnpldWdlIGVpbiBBdXRvbW90aXZlIENBTi1GRCBOZXR6d2VyayBtaXQgZWluZW0gR2F0ZXdheSBTeXN0ZW0sIGRlbiBFQ1VzIE1vdG9yc3RldWVydW5nIHVuZCBBbnplaWdlLCBlaW5lbSBTZW5zb3IgTW90b3JUZW1wZXJhdHVyZSB1bmQgZWluZW0gQWt0b3IgTW90b3JWYWx2ZS4gTW90b3JUZW1wZXJhdHVyZSB3aXJkIHZvbiBNb3RvcnN0ZXVlcnVuZyBhdXNnZXdlcnRldC4gTW90b3JzdGV1ZXJ1bmcgc3RldWVydCBNb3RvclZhbHZlLiBDb250cm9sbGVyc3RhdHVzIGJsZWlidCBiaXMgenVyIEF1c3dhaGwga29ua3JldGVyIEVtcGbDpG5nZXIgdW5kIFNpZ25hbGUgaW50ZXJuLiBQcsO8ZmUgdW5kIGFyYmVpdGUgYmlzIERhdGEgU2NpZW5jZSAmIEludGVsbGlnZW5jZS5cXG5DQU4tRkQ6IDUwMCBrYml0L3MgYXJiaXRyYXRpb24sIDIgTWJpdC9zIGRhdGFcXG5DQU46IDUwMCBrYml0L3MnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnV2VpdGVyZSBIaW53ZWlzZScsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCgnLSBBa3Rvci1CZWZlaGxlOiB7XCJNb3RvclZhbHZlXCI6e1wibGVuZ3RoX2JpdHNcIjoxLFwiZGF0YV90eXBlXCI6XCJib29sZWFuXCIsXCJmYWN0b3JcIjoxLFwidW5pdFwiOlwiY29kZVwiLFwibWluX3ZhbHVlXCI6MCxcIm1heF92YWx1ZVwiOjEsXCJzZW1hbnRpY1wiOntcInNlbWFudGljX3R5cGVcIjpcIkJPT0xFQU5cIn0sXCJkYXRhXCI6e1wiZW51bV92YWx1ZXNcIjp7XCJDTE9TRVwiOjAsXCJPUEVOXCI6MX19fX0nKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnR2Vyw6R0ZXVtZmFuZycsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBmb3IgKGNvbnN0IFtsYWJlbCwgdmFsdWVdIG9mIFtbJ0dhdGV3YXlzJywgJzEnXSwgWydDb250cm9sbGVyJywgJzInXSwgWydTZW5zb3JlbicsICcxJ10sIFsnQWt0b3JlbicsICcxJ11dKSBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbChgJHtsYWJlbH06IHZlcmJpbmRsaWNoZSBBbnphaGxgLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwodmFsdWUpO1xyXG4gIGNvbnN0IHN0YXJ0UmVxdWVzdCA9IHBhZ2Uud2FpdEZvclJlcXVlc3QocmVxdWVzdCA9PiByZXF1ZXN0LnVybCgpLmVuZHNXaXRoKCcvYXBpL2FnZW50L2NoYXQnKVxyXG4gICAgJiYgcmVxdWVzdC5tZXRob2QoKSA9PT0gJ1BPU1QnICYmIHJlcXVlc3QucG9zdERhdGFKU09OKCk/LndpemFyZF9jb21tYW5kPy5hY3Rpb24gPT09ICdTVEFSVCcpO1xyXG4gIC8vIFVzZSB0aGUgc2FtZSB2aXNpYmxlIHF1ZXN0aW9ubmFpcmUgbmF2aWdhdGlvbiBhIHVzZXIgdXNlczsgbmV2ZXIgaW5qZWN0IGdlbmVyYXRlZCBtb2RlbCByb3dzLlxyXG4gIGZvciAobGV0IHN0ZXAgPSAwOyBzdGVwIDwgMTA7IHN0ZXArKykge1xyXG4gICAgY29uc3Qgc3VibWl0ID0gZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKTtcclxuICAgIGF3YWl0IGV4cGVjdChzdWJtaXQpLnRvQmVFbmFibGVkKCk7XHJcbiAgICBjb25zdCBuYW1lID0gYXdhaXQgc3VibWl0LmlubmVyVGV4dCgpO1xyXG4gICAgYXdhaXQgc3VibWl0LmNsaWNrKCk7XHJcbiAgICBpZiAobmFtZSA9PT0gJ8OcYmVybmVobWVuJykgYnJlYWs7XHJcbiAgICBpZiAoc3RlcCA9PT0gOSkgdGhyb3cgbmV3IEVycm9yKCdRdWVzdGlvbm5haXJlIGRpZCBub3Qgb2ZmZXIgc3VibWl0LicpO1xyXG4gIH1cclxuICBjb25zdCByZXF1ZXN0ZWQgPSAoYXdhaXQgc3RhcnRSZXF1ZXN0KS5wb3N0RGF0YUpTT04oKS53aXphcmRfY29tbWFuZC53aXphcmRfY29udGV4dDtcclxuICBleHBlY3QocmVxdWVzdGVkLnRlY2hub2xvZ2llcywgJ0FuIGV4cGxpY2l0IENBTi1GRCB0YXNrIG11c3Qgbm90IHNpbGVudGx5IHJlcXVlc3QgTElOIGFuZCBTT01FL0lQLicpLnRvRXF1YWwoWydDQU4tRkQgKGNhbl9mZCknXSk7XHJcbiAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCB0cnVlLFxyXG4gICAgWydTeXN0ZW0nLCAnTW90b3JzdGV1ZXJ1bmcnLCAnQW56ZWlnZScsICdNb3RvclRlbXBlcmF0dXJlJywgJ01vdG9yVmFsdmUnXSk7XHJcbiAgY29uc3QgYXJ0aWZhY3RzID0gYXdhaXQgdmVyaWZ5QXJ0aWZhY3RzKHBhZ2UsIHByb2plY3QsIDUpO1xyXG4gIGV4cGVjdChhcnRpZmFjdHMuYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoMyk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnRyYW5zcG9ydF9leGNsdXNpb25zKS50b0hhdmVMZW5ndGgoMyk7XHJcbiAgY29uc3QgZmluaXNoZWQgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5pbmNsdWRlcyhgL3J1bnMvJHtjb250aW51aXR5LnJ1bklkfS9maW5pc2hgKVxyXG4gICAgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0ZlcnRpZyBzdGVsbGVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBleHBlY3QoKGF3YWl0IGZpbmlzaGVkKS5vaygpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cpLm5vdC50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgZXhwZWN0KChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KGVycm9ycykudG9FcXVhbChbXSk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCAuLi5jb250aW51aXR5LCAuLi5hcnRpZmFjdHMgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG5cclxuZm9yIChjb25zdCB0ZWNobm9sb2d5IG9mIFsnSTJDJywgJ01vZGJ1cyBSVFUnXSkge1xyXG4gIHRlc3QoYFJhc3BiZXJyeSBQaSAke3RlY2hub2xvZ3l9IHByb2plY3QgcmV0YWlucyBtb2RlbCBhbmQgcmVxdWVzdHMgbWlzc2luZyBjYXBhY2l0eSBldmlkZW5jZSBAbm9uYXV0b21vdGl2ZWAsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICAgIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1lbWJlZGRlZC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gICAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdQcm9qZWt0bmFtZScsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjZW5naW5lZXJpbmctcHJvamVjdC1uYW1lJykuZmlsbCgnVGVtcGVyYXR1cnJlZ2VsdW5nJyk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCh0ZWNobm9sb2d5ID09PSAnSTJDJ1xyXG4gICAgICA/ICcyIEFrdG9yZW4gZsO8ciBWZW50aWxlLCA0IFNlbnNvcmVuIGbDvHIgVGVtcGVyYXR1cmVuLCB1bmQgZWluIFJhc3BiZXJyeVBpJ1xyXG4gICAgICA6IGAyIEFrdG9yZW4gZsO8ciBWZW50aWxlLCA0IFNlbnNvcmVuIGbDvHIgVGVtcGVyYXR1cmVuLCB1bmQgZWluIFJhc3BiZXJyeVBpLiBFbWJlZGRlZCBTeXN0ZW1zLiBBbGxlIEdlcsOkdGUga29tbXVuaXppZXJlbiDDvGJlciAke3RlY2hub2xvZ3l9LiBQcsO8ZmUgdW5kIGFyYmVpdGUgYmlzIERhdGEgU2NpZW5jZSAmIEludGVsbGlnZW5jZS5gKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdOZXR6YXJjaGl0ZWt0dXInLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdyYWRpbycsIHsgbmFtZTogL1ZhcmlhbnRlIDAvIH0pLmNoZWNrKCk7XHJcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnR2Vyw6R0ZXVtZmFuZycsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICAgIGlmICh0ZWNobm9sb2d5ID09PSAnSTJDJykge1xyXG4gICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgICAgIGF3YWl0IGRpYWxvZy5nZXRCeUxhYmVsKCdSYXNwYmVycnlQaTogQW5zY2hsdXNzJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ0kyQycpO1xyXG4gICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5TGFiZWwoJ1RlbXBlcmF0dXJzZW5zb3IxOiBBbnNjaGx1c3MnLCB7IGV4YWN0OiB0cnVlIH0pKS50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcclxuICAgICAgZm9yIChjb25zdCBuYW1lIG9mIFsnUmFzcGJlcnJ5UGknLCAnVGVtcGVyYXR1cnNlbnNvcjEnLCAnVGVtcGVyYXR1cnNlbnNvcjInLCAnVGVtcGVyYXR1cnNlbnNvcjMnLCAnVGVtcGVyYXR1cnNlbnNvcjQnLCAnVmVudGlsYWt0b3IxJywgJ1ZlbnRpbGFrdG9yMiddKSB7XHJcbiAgICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoYCR7bmFtZX06IEFuc2NobHVzc2AsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdJMkMnKTtcclxuICAgICAgfVxyXG4gICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnU2Vuc29yIDE6IE1lc3NncsO2w59lJywgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ3NwZWVkJyk7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlMYWJlbCgnVGVtcGVyYXR1cnNlbnNvcjE6IEFuc2NobHVzcycsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZVZhbHVlKCdJMkMnKTtcclxuICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1NlbnNvciAxOiBNZXNzZ3LDtsOfZScsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCd0ZW1wZXJhdHVyZScpO1xyXG4gICAgfVxyXG4gICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMTogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignT1BFTl9DTE9TRScpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeUxhYmVsKCdWZW50aWxha3RvcjI6IFN0ZWxsYmVmZWhsJywgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoJycpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkpLnRvQmVEaXNhYmxlZCgpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMjogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignT1BFTl9DTE9TRScpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCB0cnVlLCBbJ1Jhc3BiZXJyeVBpJywgJ1RlbXBlcmF0dXJzZW5zb3IxJywgJ1RlbXBlcmF0dXJzZW5zb3IyJywgJ1RlbXBlcmF0dXJzZW5zb3IzJywgJ1RlbXBlcmF0dXJzZW5zb3I0JywgJ1ZlbnRpbGFrdG9yMScsICdWZW50aWxha3RvcjInXSwgZmFsc2UsIHVuZGVmaW5lZCwgdW5kZWZpbmVkLCB0cnVlKSlcclxuICAgICAgLnJlamVjdHMudG9UaHJvdygvV2l6YXJkIEJMT0NLRUQgYXQgdmFsaWRhdGlvbi8pO1xyXG4gICAgY29uc3Qgd29ya2Zsb3cgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpO1xyXG4gICAgY29uc3QgZmluZGluZ3MgPSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbi5ibG9ja2luZ19maW5kaW5ncyBhcyB7IGNvZGU6IHN0cmluZyB9W107XHJcbiAgICBleHBlY3QoZmluZGluZ3MubWFwKGl0ZW0gPT4gaXRlbS5jb2RlKSkudG9Db250YWluKHRlY2hub2xvZ3kgPT09ICdJMkMnID8gJ0NPTU1VTklDQVRJT05fVU5WRVJJRklFRCcgOiAnR0VORVJJQ19FU1RJTUFURScpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGV4cGVjdCh3b3JrZmxvdy5wYXJhbWV0ZXJzLnJhdGVfcmV2aWV3X3Byb3Bvc2Fscy5pMmMuc3RhdHVzKS50b0JlKCdSRVZJRVdfUkVRVUlSRUQnKTtcclxuICAgICAgZXhwZWN0KHdvcmtmbG93LnBhcmFtZXRlcnMucGFyYW1ldGVyX3Byb3ZlbmFuY2UuYml0cmF0ZS5zb3VyY2UpLnRvQmUoJ1RFQ0hOT0xPR1lfUFJPRklMRV9SRVZJRVdfUFJPUE9TQUwnKTtcclxuICAgIH1cclxuICAgIGNvbnN0IGludGVyZmFjZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1pbnRlcmZhY2VzJyk7XHJcbiAgICBleHBlY3QoaW50ZXJmYWNlcy5sZW5ndGgpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoNyk7XHJcbiAgICBleHBlY3QoaW50ZXJmYWNlcy5ldmVyeShpdGVtID0+ICEvYXV0b21vdGl2ZXxjYW58bGluL2kudGVzdChpdGVtLnRlY2hub2xvZ3kpKSkudG9CZSh0cnVlKTtcclxuICAgIGNvbnN0IGhhcmR3YXJlID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICAgIGV4cGVjdChoYXJkd2FyZS5ldmVyeShpdGVtID0+IGl0ZW0uZG9tYWluICE9PSAnYXV0b21vdGl2ZScpKS50b0JlKHRydWUpO1xyXG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XHJcbiAgICAgIGNvbnN0IHNpZ25hbHMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyk7XHJcbiAgICAgIGV4cGVjdChzaWduYWxzLnNvbWUoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdUZW1wZXJhdHVyX1RlbXBlcmF0dXJzZW5zb3IxJyAmJiBpdGVtLnVuaXQgPT09ICdkZWdDJykpLnRvQmUodHJ1ZSk7XHJcbiAgICB9XHJcbiAgICBleHBlY3QoKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnMpLnRvSGF2ZUxlbmd0aCgwKTtcclxuICAgIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnbm9uYXV0b21vdGl2ZS1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCB0ZWNobm9sb2d5LCBmaW5kaW5ncyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxuICB9KTtcclxufVxyXG5cclxudGVzdCgnZXhhY3QgY29uZmlybWVkIDUwLzI1MC8yNTAgcmVxdWVzdCBjb21wbGV0ZXMgdGhyb3VnaCByZWFsIHdpemFyZCByZXZpZXcgQGxhcmdlJywgYXN5bmMgKHsgcGFnZSB9LCB0ZXN0SW5mbykgPT4ge1xyXG4gIGNvbnN0IGVycm9yczogc3RyaW5nW10gPSBbXTsgcGFnZS5vbigncGFnZWVycm9yJywgZXJyb3IgPT4gZXJyb3JzLnB1c2goZXJyb3IubWVzc2FnZSkpO1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1sYXJnZS0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IHJ1bklkID0gcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IG9yaWdpbmFsID0gYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2UtNTAtMjUwLTI1MC50eHQnLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpO1xyXG4gIGNvbnN0IG1ldGFkYXRhID0gSlNPTi5wYXJzZShhd2FpdCByZWFkRmlsZShuZXcgVVJMKCcuL2ZpeHR1cmVzL3dpemFyZC1sYXJnZS01MC0yNTAtMjUwLmpzb24nLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpKTtcclxuICBjb25zdCBiYXNlbGluZSA9IEpTT04ucGFyc2UoYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2Utc2lnbmFsLWNvbnRyYWN0cy5qc29uJywgaW1wb3J0Lm1ldGEudXJsKSwgJ3V0ZjgnKSk7XHJcbiAgY29uc3QgcHJvbXB0ID0gb3JpZ2luYWwucmVwbGFjZSgvXi0gTGF1Zi1JRDouKiQvbSwgJy0gTGF1Zi1JRDogJyArIHJ1bklkKTtcclxuICAvLyBSZXBsYXkgdGhlIGNhcHR1cmVkLCBhbHJlYWR5IGNvbmZpcm1lZCBpbnB1dCB0aHJvdWdoIHRoZSBub3JtYWwgU1RBUlQgQVBJLlxyXG4gIC8vIEFsbCBwcm9wb3NhbCBpbnNwZWN0aW9uLCBhcHByb3ZhbCwgY29udGludWF0aW9uIGFuZCByZWxvYWRzIGJlbG93IHVzZSBVSS5cclxuICBjb25zdCBzdGFydGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY2hhdCcsIHtcclxuICAgIGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSwgdGltZW91dDogMjQwXzAwMCxcclxuICAgIGRhdGE6IHsgcHJvbXB0LCB3aXphcmRfY29tbWFuZDogeyBhY3Rpb246ICdTVEFSVCcsIHJ1bl9pZDogcnVuSWQsIG9wZXJhdGlvbl9pZDogcmFuZG9tVVVJRCgpLFxyXG4gICAgICB0YXJnZXQ6ICdkYXRhX3NjaWVuY2VfaW50ZWxsaWdlbmNlJywgd2l6YXJkX2NvbnRleHQ6IHsgLi4ubWV0YWRhdGEud2l6YXJkX2NvbnRleHQsIHByb2plY3RfaWQ6IHByb2plY3QsIHJ1bl9pZDogcnVuSWQgfSB9IH0sXHJcbiAgfSk7XHJcbiAgaWYgKCFzdGFydGVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke3N0YXJ0ZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBzdGFydGVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBjb25zdCBjb250aW51aXR5ID0gYXdhaXQgY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIGZhbHNlLCBbXSwgdHJ1ZSwgYmFzZWxpbmUuc2lnbmFscyk7XHJcbiAgZXhwZWN0KGNvbnRpbnVpdHkucnVuSWQpLnRvQmUocnVuSWQpO1xyXG4gIGNvbnN0IGhhcmR3YXJlID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICBleHBlY3QoaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5kZXZpY2VfdHlwZSA9PT0gJ1NlbnNvckNvbnRyb2xsZXInKSkudG9IYXZlTGVuZ3RoKDI1MCk7XHJcbiAgZXhwZWN0KGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0uZGV2aWNlX3R5cGUgPT09ICdBY3R1YXRvckNvbnRyb2xsZXInKSkudG9IYXZlTGVuZ3RoKDI1MCk7XHJcbiAgZXhwZWN0KGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0uZGV2aWNlX3R5cGUgPT09ICdFQ1UnKS5sZW5ndGgpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoNTApO1xyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCAxNDA0KTtcclxuICBjb25zdCBleGNsdWRlZFNpZ25hbElkcyA9IG5ldyBTZXQoYXJ0aWZhY3RzLmFzc2Vzc21lbnQuc2NvcGVfY292ZXJhZ2UudHJhbnNwb3J0X2V4Y2x1c2lvbnNcclxuICAgIC5mbGF0TWFwKChpdGVtOiB7IHNpZ25hbF9pZHM6IHN0cmluZ1tdIH0pID0+IGl0ZW0uc2lnbmFsX2lkcykpO1xyXG4gIGV4cGVjdChleGNsdWRlZFNpZ25hbElkcy5zaXplKS50b0JlKDIzNSk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5hc3Nlc3NtZW50Lm9ic2VydmVkX3NpZ25hbF9jb3VudCkudG9CZSgxMTY5KTtcclxuICBhd2FpdCB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZSwgcHJvamVjdCwgYmFzZWxpbmUuc2lnbmFscyk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5qb2IpLnRvQmUoY29udGludWl0eS5yZXN0YXJ0ZWRKb2JJZCk7XHJcbiAgZXhwZWN0KGVycm9ycykudG9FcXVhbChbXSk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCBmaXh0dXJlOiBtZXRhZGF0YS5yZXF1ZXN0X3NoYTI1NiwgLi4uY29udGludWl0eSwgLi4uYXJ0aWZhY3RzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuXHJcbnRlc3QoJ2EgcmVhbCBBTUVORCBhZnRlciBtb2RlbCBhcHByb3ZhbCBhZGRzIHRoZSByZXF1ZXN0ZWQgc2Vuc29yIGFuZCByZXVzZXMgaXRzIG5ldHdvcmtzIEBhbWVuZCcsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtYW1lbmQtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBydW5JZCA9IHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBncmFwaCA9IFtcclxuICAgIHsgY2x1c3Rlcl9pZDogJ2RyaXZlJywgbmV0d29ya19pZDogJ2Nhbl9mZCcsIG5ldHdvcmtfbGFiZWw6ICdDQU4tRkQnLCBidXNfbmFtZTogJ0RyaXZlJyxcclxuICAgICAgY29udHJvbGxlcnM6IFt7IGVjdTogJ01vdG9yc3RldWVydW5nJywgc2Vuc29yczogW10gYXMgc3RyaW5nW10sIGFjdHVhdG9yczogW10gfV0sXHJcbiAgICAgIGhtaV9yb3V0ZXM6IFt7IHNvdXJjZTogJ01vdG9yc3RldWVydW5nJywgdGFyZ2V0OiAnQW56ZWlnZScgfSwgeyBzb3VyY2U6ICdBbnplaWdlJywgdGFyZ2V0OiAnTW90b3JzdGV1ZXJ1bmcnIH0sXHJcbiAgICAgICAgeyBzb3VyY2U6ICdTeXN0ZW0nLCB0YXJnZXQ6ICdBbnplaWdlJyB9XSB9LFxyXG4gICAgeyBjbHVzdGVyX2lkOiAnZGlzcGxheScsIG5ldHdvcmtfaWQ6ICdldGhlcm5ldCcsIG5ldHdvcmtfbGFiZWw6ICdFdGhlcm5ldCcsIGJ1c19uYW1lOiAnRGlzcGxheScsXHJcbiAgICAgIGNvbnRyb2xsZXJzOiBbeyBlY3U6ICdBbnplaWdlJywgc2Vuc29yczogW10gYXMgc3RyaW5nW10sIGFjdHVhdG9yczogW10gfV0gfSxcclxuICBdO1xyXG4gIGNvbnN0IHByb21wdCA9IGBTdHJ1a3R1cmllcnRlIFZvcmdhYmVuIGZ1ZXIgZGVuIEVuZ2luZWVyaW5nLUFnZW50ZW46XHJcbi0gTGF1Zi1JRDogJHtydW5JZH1cclxuLSBJbmR1c3RyaWU6IEF1dG9tb3RpdmVcclxuLSBOZXR6d2Vya3RlY2hub2xvZ2llbjogQ0FOLUZEIChjYW5fZmQpOyBFdGhlcm5ldCAoZXRoZXJuZXQpXHJcbkNBTi1GRDogNTAwIGtiaXQvcyBhcmJpdHJhdGlvbiwgMiBNYml0L3MgZGF0YVxyXG5DQU46IDUwMCBrYml0L3NcclxuRXRoZXJuZXQ6IDEwMCBNYml0L3NcclxuLSBIYXJkd2FyZS1Tb2xsd2VydGU6IHtcImdhdGV3YXlzXCI6MSxcImVjdXNcIjoyLFwic2Vuc29yc1wiOjAsXCJhY3R1YXRvcnNcIjowfVxyXG4tIFN5c3RlbWNsdXN0ZXItR3JhcGg6ICR7SlNPTi5zdHJpbmdpZnkoZ3JhcGgpfVxyXG5Lb25rcmV0ZSBBdWZnYWJlIGRlcyBOdXR6ZXJzLCBwZXIgV2l6YXJkLVVlYmVybmVobWVuIGJlc3RhZXRpZ3Q6XHJcbk1vdG9yc3RldWVydW5nIHVuZCBBbnplaWdlIG1pdCBlaW5lbSB6ZW50cmFsZW4gR2F0ZXdheSBTeXN0ZW0gdmVyYmluZGVuLmA7XHJcbiAgY29uc3Qgc3RhcnRlZCA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L2NoYXQnLCB7XHJcbiAgICBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0sIHRpbWVvdXQ6IDEyMF8wMDAsXHJcbiAgICBkYXRhOiB7IHByb21wdCwgd2l6YXJkX2NvbW1hbmQ6IHsgYWN0aW9uOiAnU1RBUlQnLCBydW5faWQ6IHJ1bklkLCBvcGVyYXRpb25faWQ6IHJhbmRvbVVVSUQoKSxcclxuICAgICAgdGFyZ2V0OiAnZGF0YV9zY2llbmNlX2ludGVsbGlnZW5jZScsIHdpemFyZF9jb250ZXh0OiB7IHByb2plY3RfaWQ6IHByb2plY3QsIHJ1bl9pZDogcnVuSWQsXHJcbiAgICAgICAgcHJvamVjdF9uYW1lOiAnRTJFIGFtZW5kbWVudCcsIHNjb3BlX2lkczogc3RlcHMsIG1vZGU6ICdmdWxsJyxcclxuICAgICAgICBwcm9jZXNzX2lkczogWydkZWZhdWx0cycsICdyZXZpZXdfZ2F0ZScsICdhcHByb3ZlX2FmdGVyX2FsbG93J10sIHRhc2s6ICdNb3RvcnN0ZXVlcnVuZyB1bmQgQW56ZWlnZSBhbiBTeXN0ZW0nIH0gfSB9LFxyXG4gIH0pO1xyXG4gIGlmICghc3RhcnRlZC5vaygpKSB0aHJvdyBuZXcgRXJyb3IoYEhUVFAgJHtzdGFydGVkLnN0YXR1cygpfTogJHsoYXdhaXQgc3RhcnRlZC50ZXh0KCkpLnNsaWNlKDAsIDQwMDApfWApO1xyXG4gIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgbGV0IG9yaWdpbmFsTmV0d29ya3M6IHN0cmluZ1tdID0gW107XHJcbiAgY29uc3QgYW1lbmQgPSBhc3luYyAoKSA9PiB7XHJcbiAgICBvcmlnaW5hbE5ldHdvcmtzID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93JykpLnBhcmFtZXRlcnMubmV0d29ya3NcclxuICAgICAgLm1hcCgoaXRlbTogeyBpZDogc3RyaW5nIH0pID0+IGl0ZW0uaWQpLnNvcnQoKTtcclxuICAgIGV4cGVjdChvcmlnaW5hbE5ldHdvcmtzKS50b0hhdmVMZW5ndGgoMik7XHJcbiAgICBncmFwaFswXS5jb250cm9sbGVyc1swXS5zZW5zb3JzLnB1c2goJ01vdG9yVGVtcGVyYXR1cmUnKTtcclxuICAgIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XHJcbiAgICBjb25zdCBleHBhbmQgPSBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdFcmfDpG56ZW4nLCBleGFjdDogdHJ1ZSB9KTtcclxuICAgIGF3YWl0IGV4cGVjdChleHBhbmQpLnRvQmVFbmFibGVkKHsgdGltZW91dDogMTIwXzAwMCB9KTtcclxuICAgIGF3YWl0IGV4cGFuZC5jbGljaygpO1xyXG4gICAgY29uc3QgZmllbGQgPSBkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyZ8OkbnplbicsIGV4YWN0OiB0cnVlIH0pLmdldEJ5Um9sZSgndGV4dGJveCcpO1xyXG4gICAgYXdhaXQgZmllbGQuZmlsbCgnRXJnw6RuemUgTW90b3JUZW1wZXJhdHVyZSBhbHMgU2Vuc29yIGRlciBNb3RvcnN0ZXVlcnVuZy4gRGllIHZvbGxzdMOkbmRpZ2UgYWt0dWFsaXNpZXJ0ZSBGcmVpZ2FiZSBsYXV0ZXQ6XFxuJ1xyXG4gICAgICArICctIEhhcmR3YXJlLVNvbGx3ZXJ0ZToge1wiZ2F0ZXdheXNcIjoxLFwiZWN1c1wiOjIsXCJzZW5zb3JzXCI6MSxcImFjdHVhdG9yc1wiOjB9XFxuJ1xyXG4gICAgICArICctIFN5c3RlbWNsdXN0ZXItR3JhcGg6ICcgKyBKU09OLnN0cmluZ2lmeShncmFwaCkpO1xyXG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRXJnw6RuenVuZyBhbmFseXNpZXJlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgICBhd2FpdCBleHBlY3QoZmllbGQpLm5vdC50b0JlVmlzaWJsZSh7IHRpbWVvdXQ6IDEyMF8wMDAgfSk7XHJcbiAgfTtcclxuICBjb25zdCBjb250aW51aXR5ID0gYXdhaXQgY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIGZhbHNlLCBbJ01vdG9yc3RldWVydW5nJywgJ0FuemVpZ2UnXSwgZmFsc2UsIHVuZGVmaW5lZCwgYW1lbmQpO1xyXG4gIGNvbnN0IGhhcmR3YXJlID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICBjb25zdCBvd25lciA9IGhhcmR3YXJlLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdNb3RvcnN0ZXVlcnVuZycpO1xyXG4gIGNvbnN0IHNlbnNvcnMgPSBoYXJkd2FyZS5maWx0ZXIoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdNb3RvclRlbXBlcmF0dXJlJyk7XHJcbiAgZXhwZWN0KHNlbnNvcnMpLnRvSGF2ZUxlbmd0aCgxKTtcclxuICBleHBlY3Qoc2Vuc29yc1swXS5pZGVudGl0eS5zeXN0ZW1fb3duZXJfaWQpLnRvQmUob3duZXIuaWQpO1xyXG4gIGNvbnN0IHNlbnNvck5ldHdvcmsgPSAnRHJpdmUtSU8tbW90b3JzdGV1ZXJ1bmctY2FuLWZkLVMwMSc7XHJcbiAgY29uc3QgbmV0d29ya3MgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cnKSkucGFyYW1ldGVycy5uZXR3b3JrcztcclxuICBleHBlY3QobmV0d29ya3MubWFwKChpdGVtOiB7IGlkOiBzdHJpbmcgfSkgPT4gaXRlbS5pZCkuc29ydCgpKS50b0VxdWFsKFsuLi5vcmlnaW5hbE5ldHdvcmtzLCBzZW5zb3JOZXR3b3JrXS5zb3J0KCkpO1xyXG4gIGV4cGVjdChuZXcgU2V0KG5ldHdvcmtzLm1hcCgoaXRlbTogeyBuYW1lOiBzdHJpbmcgfSkgPT4gaXRlbS5uYW1lKSkuc2l6ZSkudG9CZShuZXR3b3Jrcy5sZW5ndGgpO1xyXG4gIGNvbnN0IHRvcG9sb2d5ID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L25ldHdvcmstdmlldycpKS50b3BvbG9neTtcclxuICBjb25zdCBsb2NhbEVkZ2UgPSB0b3BvbG9neS5lZGdlcy5maW5kKChlZGdlOiBhbnkpID0+IGVkZ2UucGh5c2ljYWxOZXR3b3JrSWQgPT09IHNlbnNvck5ldHdvcmspO1xyXG4gIGV4cGVjdChsb2NhbEVkZ2UpLnRvQmVUcnV0aHkoKTtcclxuICBleHBlY3QobG9jYWxFZGdlLmJ1cykudG9CZSgnY2FuX2ZkJyk7XHJcbiAgZXhwZWN0KE9iamVjdC52YWx1ZXMobG9jYWxFZGdlLnJvdXRpbmdNZXRhZGF0YSkpLnRvQ29udGFpbkVxdWFsKGV4cGVjdC5vYmplY3RDb250YWluaW5nKHtcclxuICAgIHNvdXJjZTogc2Vuc29yc1swXS5pZCwgdGFyZ2V0OiBvd25lci5pZCwgYXBwcm92YWxTdGF0ZTogJ0FQUFJPVkVEJywgcHJvdG9jb2w6ICdDQU5fRkQnLFxyXG4gIH0pKTtcclxuICBmb3IgKGNvbnN0IFtzaWRlLCBoYXJkd2FyZUlkXSBvZiBbWydzb3VyY2UnLCBzZW5zb3JzWzBdLmlkXSwgWyd0YXJnZXQnLCBvd25lci5pZF1dKSB7XHJcbiAgICBjb25zdCBub2RlID0gdG9wb2xvZ3kubm9kZXMuZmluZCgoaXRlbTogYW55KSA9PiBpdGVtLmlkID09PSBsb2NhbEVkZ2Vbc2lkZV0pO1xyXG4gICAgZXhwZWN0KG5vZGUuZW5naW5lZXJpbmdJZCkudG9CZShoYXJkd2FyZUlkKTtcclxuICAgIGV4cGVjdChub2RlLnBvcnRzKS50b0NvbnRhaW5FcXVhbChleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7IGlkOiBsb2NhbEVkZ2Vbc2lkZSArICdQb3J0J10sXHJcbiAgICAgIGJ1czogJ2Nhbl9mZCcsIHBoeXNpY2FsTmV0d29ya0lkOiBzZW5zb3JOZXR3b3JrIH0pKTtcclxuICB9XHJcbiAgY29uc3QgYXJ0aWZhY3RzID0gYXdhaXQgdmVyaWZ5QXJ0aWZhY3RzKHBhZ2UsIHByb2plY3QsIDEpO1xyXG4gIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnYW1lbmRtZW50LWV2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIC4uLmNvbnRpbnVpdHksIC4uLmFydGlmYWN0cyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxufSk7XHJcblxyXG4vLyBSZWFsIGlzb2xhdGVkIFVJIC0+IHBlcnNpc3RlZCBtb2RlbCBib3VuZGFyeSByZWdyZXNzaW9uLCBub3QgbmluZS1zdGFnZSBjb21wbGV0aW9uIHByb29mLlxyXG50ZXN0KCdyZXZpZXdhYmxlIGZ1bmN0aW9uYWwgVFgvUlggT0ZGIHN1cnZpdmVzIHJlcXVlc3QgcmVsb2FkIGFuZCBjYW5vbmljYWwgbW9kZWwgYWRvcHRpb24gQHR4cngnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXR4cngtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBkaWFsb2cgPSBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRpdGxlKCdQcm9qZWt0bmFtZScsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cubG9jYXRvcignI2VuZ2luZWVyaW5nLXByb2plY3QtbmFtZScpLmZpbGwoJ1RYIFJYIGZ1bmN0aW9uYWwgcGFydG5lcnMnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUHJvamVrdGJlc2NocmVpYnVuZycsIHsgZXhhY3Q6IHRydWUgfSkuZmlsbCgnRXJ6ZXVnZSBlaW4gQXV0b21vdGl2ZSBDQU4tRkQgTmV0endlcmsgbWl0IGVpbmVtIEdhdGV3YXkgU3lzdGVtIHVuZCBkZW4gRUNVcyBNb3RvcnN0ZXVlcnVuZywgR2V0cmllYmVzdGV1ZXJ1bmcgdW5kIEVsZWt0cm9tb3RvcnN0ZXVlcnVuZy4gRGllIGJlcmVjaG5ldGVuIEZ1bmt0aW9uc2F1c2fDpG5nZSBkaWVuZW4gZGVyIEFudHJpZWJza29vcmRpbmF0aW9uLiBDb250cm9sbGVyc3RhdHVzIGJsZWlidCBpbnRlcm4uXFxuQ0FOLUZEOiA1MDAga2JpdC9zIGFyYml0cmF0aW9uLCAyIE1iaXQvcyBkYXRhJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ0dlcsOkdGV1bWZhbmcnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgZm9yIChjb25zdCBbbGFiZWwsIHZhbHVlXSBvZiBbWydHYXRld2F5cycsICcxJ10sIFsnQ29udHJvbGxlcicsICczJ10sIFsnU2Vuc29yZW4nLCAnMCddLCBbJ0FrdG9yZW4nLCAnMCddXSkgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoYCR7bGFiZWx9OiB2ZXJiaW5kbGljaGUgQW56YWhsYCwgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHZhbHVlKTtcclxuICBjb25zdCB0eHJ4ID0gZGlhbG9nLmxvY2F0b3IoJ2RldGFpbHMnKS5maWx0ZXIoeyBoYXM6IHBhZ2UubG9jYXRvcignc3VtbWFyeScpLmZpbHRlcih7IGhhc1RleHQ6IC9eVFhcXC9SWC8gfSkgfSkuZmlyc3QoKTtcclxuICBhd2FpdCBleHBlY3QodHhyeCkudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCB0eHJ4LmxvY2F0b3IoJ3N1bW1hcnknKS5jbGljaygpO1xyXG4gIGNvbnN0IHNlbGVjdGVkID0gdHhyeC5nZXRCeVJvbGUoJ3N3aXRjaCcsIHsgbmFtZTogJ01vdG9yRHJlaG1vbWVudElzdCDihpIgR2V0cmllYmVzdGV1ZXJ1bmcnLCBleGFjdDogdHJ1ZSB9KTtcclxuICBhd2FpdCBleHBlY3Qoc2VsZWN0ZWQpLnRvQmVDaGVja2VkKCk7IGF3YWl0IHNlbGVjdGVkLnVuY2hlY2soKTtcclxuICBjb25zdCBzdGFydFJlcXVlc3QgPSBwYWdlLndhaXRGb3JSZXF1ZXN0KHJlcXVlc3QgPT4gcmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JykgJiYgcmVxdWVzdC5tZXRob2QoKSA9PT0gJ1BPU1QnICYmIHJlcXVlc3QucG9zdERhdGFKU09OKCk/LndpemFyZF9jb21tYW5kPy5hY3Rpb24gPT09ICdTVEFSVCcpO1xyXG4gIGZvciAobGV0IHN0ZXAgPSAwOyBzdGVwIDwgMTA7IHN0ZXArKykge1xyXG4gICAgY29uc3QgYnV0dG9uID0gZGlhbG9nLmxvY2F0b3IoJy5lbmctYWdlbnQtcXVlc3Rpb25uYWlyZS1oZWFkJykuZ2V0QnlSb2xlKCdidXR0b24nKTtcclxuICAgIGF3YWl0IGV4cGVjdChidXR0b24pLnRvQmVFbmFibGVkKCk7IGNvbnN0IGxhYmVsID0gYXdhaXQgYnV0dG9uLmlubmVyVGV4dCgpOyBhd2FpdCBidXR0b24uY2xpY2soKTtcclxuICAgIGlmIChsYWJlbCA9PT0gJ8OcYmVybmVobWVuJyB8fCBsYWJlbCA9PT0gJ0F1ZnRyYWcgc3RhcnRlbicpIGJyZWFrO1xyXG4gIH1cclxuICBjb25zdCBjb250ZXh0ID0gKGF3YWl0IHN0YXJ0UmVxdWVzdCkucG9zdERhdGFKU09OKCkud2l6YXJkX2NvbW1hbmQud2l6YXJkX2NvbnRleHQ7XHJcbiAgY29uc3Qgc3VibWl0dGVkID0gY29udGV4dC5zeXN0ZW1fY2x1c3Rlcl9hc3NpZ25tZW50cy5mbGF0TWFwKChjbHVzdGVyOiBhbnkpID0+IGNsdXN0ZXIuZnVuY3Rpb25hbF9yb3V0ZXMgPz8gW10pO1xyXG4gIGNvbnN0IG9mZiA9IHN1Ym1pdHRlZC5maW5kKChyb3V0ZTogYW55KSA9PiByb3V0ZS5zb3VyY2UgPT09ICdNb3RvcnN0ZXVlcnVuZycgJiYgcm91dGUudGFyZ2V0ID09PSAnR2V0cmllYmVzdGV1ZXJ1bmcnKTtcclxuICBleHBlY3Qob2ZmLnNpZ25hbHMpLnRvRXF1YWwoW10pOyBleHBlY3Qob2ZmLmV4Y2x1ZGVkX3NpZ25hbHMpLnRvRXF1YWwoWydNb3RvckRyZWhtb21lbnRJc3QnXSk7XHJcbiAgbGV0IHByb3Bvc2FsOiBhbnk7XHJcbiAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xyXG4gICAgY29uc3QgY29udmVyc2F0aW9uID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY29udmVyc2F0aW9uJyk7XHJcbiAgICBpZiAoIWNvbnZlcnNhdGlvbi5kYXRhLmFjdGl2ZV9wcm9wb3NhbCkgcmV0dXJuIGZhbHNlO1xyXG4gICAgcHJvcG9zYWwgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7Y29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsfWApKS5kYXRhO1xyXG4gICAgcmV0dXJuIHByb3Bvc2FsLnByb3Bvc2FsX3R5cGUgPT09ICdXSVpBUkRfRU5HSU5FRVJJTkdfTU9ERUwnO1xyXG4gIH0sIHsgdGltZW91dDogMTgwXzAwMCB9KS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7IGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgY29uc3QgZmluZGluZ3MgPSBwcm9wb3NhbC52YWxpZGF0aW9uX3Jlc3VsdC5maW5kaW5ncy5maWx0ZXIoKGl0ZW06IGFueSkgPT4gaXRlbS5jb2RlID09PSAnQ0FQQUNJVFlfVU5WRVJJRklFRCcpO1xyXG4gIGlmIChmaW5kaW5ncy5sZW5ndGgpIHtcclxuICAgIGNvbnN0IHJldmlldyA9IHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdQcsO8ZmJlZnVuZGUgZGVzIFZvcnNjaGxhZ3MnIH0pO1xyXG4gICAgYXdhaXQgZXhwZWN0KHJldmlldykudG9Db250YWluVGV4dChgJHtwcm9wb3NhbC52YWxpZGF0aW9uX3Jlc3VsdC5maW5kaW5ncy5sZW5ndGh9IFByw7xmYmVmdW5kZWApO1xyXG4gICAgYXdhaXQgZXhwZWN0KHJldmlldy5nZXRCeVJvbGUoJ2xpbmsnLCB7IG5hbWU6ICdUZWNobm9sb2dpZXBhcmFtZXRlciBiZWFyYmVpdGVuIHVuZCBiZXN0w6R0aWdlbicgfSkuZmlyc3QoKSkudG9IYXZlQXR0cmlidXRlKCdocmVmJywgbmV3IFJlZ0V4cChgcHJvamVjdD0ke3Byb2plY3R9YCkpO1xyXG4gICAgYXdhaXQgcmV2aWV3LmxvY2F0b3IoJ3N1bW1hcnknKS5maXJzdCgpLmNsaWNrKCk7IGF3YWl0IGV4cGVjdChyZXZpZXcuZ2V0QnlSb2xlKCduYXZpZ2F0aW9uJywgeyBuYW1lOiAnQmVmdW5kZSBkdXJjaGJsw6R0dGVybicgfSkuZmlyc3QoKSkudG9CZVZpc2libGUoKTtcclxuICB9XHJcbiAgY29uc3QgYXBwbHkgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5pbmNsdWRlcyhgL3Byb3Bvc2Fscy8ke3Byb3Bvc2FsLnByb3Bvc2FsX2lkfS9hcHByb3ZlLWFwcGx5YCkgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdGcmVpZ2ViZW4sIMO8YmVybmVobWVuICYgZm9ydGZhaHJlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7IGV4cGVjdCgoYXdhaXQgYXBwbHkpLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgY29uc3Qgbm9kZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xyXG4gIGNvbnN0IG1lc3NhZ2VzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnbWVzc2FnZXMnKTsgY29uc3Qgc2lnbmFscyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ3NpZ25hbHMnKTtcclxuICBjb25zdCBzaWduYWwgPSBzaWduYWxzLmZpbmQoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdNb3RvckRyZWhtb21lbnRJc3QnKTsgZXhwZWN0KHNpZ25hbCkudG9CZVRydXRoeSgpO1xyXG4gIGNvbnN0IG1lc3NhZ2UgPSBtZXNzYWdlcy5maW5kKGl0ZW0gPT4gaXRlbS5pZCA9PT0gc2lnbmFsLm1lc3NhZ2VfaWQpO1xyXG4gIGNvbnN0IGdlYXJib3ggPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnR2V0cmllYmVzdGV1ZXJ1bmcnKTtcclxuICBjb25zdCBlbW90b3IgPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnRWxla3Ryb21vdG9yc3RldWVydW5nJyk7XHJcbiAgZXhwZWN0KG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LnNjb3BlKS50b0JlKCdGVU5DVElPTl9PVVRQVVQnKTtcclxuICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QuY29uc3VtZXJfcmVmcykubm90LnRvQ29udGFpbihnZWFyYm94LmlkKTtcclxuICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QuY29uc3VtZXJfcmVmcykudG9Db250YWluKGVtb3Rvci5pZCk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdmdW5jdGlvbmFsLXR4cngtZXZpZGVuY2UnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgcHJvamVjdCwgb2ZmLCBtZXNzYWdlIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuIl0sIm1hcHBpbmdzIjoiQUFBQSxTQUFTQSxJQUFJLEVBQUVDLE1BQU0sUUFBbUIsaUJBQWlCO0FBQ3pELFNBQVNDLFFBQVEsUUFBUSxrQkFBa0I7QUFDM0MsU0FBU0MsVUFBVSxRQUFRLGFBQWE7QUFDeEMsU0FBU0MsWUFBWSxRQUFRLG9CQUFvQjtBQUNqRCxTQUFTQyxzQkFBc0IsRUFBRUMsWUFBWSxFQUFFQyxXQUFXLFFBQVEsb0NBQW9DO0FBRXRHLE1BQU1DLEtBQUssR0FBR0YsWUFBWTtBQUMxQixNQUFNRyxJQUFJLEdBQUdGLFdBQVc7QUFFeEIsTUFBTUcsWUFBWSxHQUFHLElBQUlDLEdBQUcsQ0FBd0IsQ0FBQztBQUNyRCxNQUFNQyxvQkFBb0IsR0FBRyxJQUFJQyxPQUFPLENBQWlCLENBQUM7QUFDMUQsTUFBTUMsa0JBQWtCLEdBQUcsSUFBSUgsR0FBRyxDQUFvQixDQUFDO0FBRXZEWCxJQUFJLENBQUNlLFVBQVUsQ0FBQyxPQUFPO0VBQUVDO0FBQUssQ0FBQyxFQUFFQyxJQUFJLEtBQUs7RUFDeEMsTUFBTUMsSUFBbUIsR0FBRyxF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