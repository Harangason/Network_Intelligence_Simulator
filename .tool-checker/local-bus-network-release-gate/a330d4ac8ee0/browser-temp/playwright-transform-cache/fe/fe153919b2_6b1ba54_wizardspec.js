// 2959d1da21013f3cb2aa8b29ae85006daefa76ff
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
async function verifyArtifacts(page, project, minimumSignals, internalController) {
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
  expect(assessment.observed_signal_count).toBeGreaterThanOrEqual(minimumSignals);
  const signals = await allObjects(page, project, 'signals');
  const excluded = (_assessment$scope_cov = assessment.scope_coverage.transport_exclusions) !== null && _assessment$scope_cov !== void 0 ? _assessment$scope_cov : [];
  if (internalController) {
    const nodes = await allObjects(page, project, 'hardware-nodes');
    const controller = nodes.find(item => item.name === internalController);
    const messages = await allObjects(page, project, 'messages');
    expect(excluded.length).toBeGreaterThan(0);
    for (const item of excluded) {
      const message = messages.find(row => row.id === item.message_id);
      expect(item.reason_code).toBe('EXPLICIT_FUNCTION_OUTPUT_NOT_ROUTED');
      expect(message.configuration.routing.enabled).toBe(false);
      expect(message.configuration.communication_contract).toMatchObject({
        role: 'INTERNAL_STATE',
        scope: 'FUNCTION_OUTPUT',
        producer_ref: controller.id,
        consumer_refs: []
      });
    }
  } else expect(excluded).toHaveLength(0);
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
async function completeThroughWizard(page, project, restart, expectedHardware = [], crashSimulation = false, expectedSignals, afterFirstModelApplied) {
  let reviewCount = 0;
  let runId;
  const reviewed = new Set();
  let restartedJobId;
  let watchdog = new WizardProgressWatchdog(performance.now());
  for (let checkpoint = 0; checkpoint < 16; checkpoint++) {
    var _workflow$context$age, _workflow$context$age2;
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
        var _await$readProject$co;
        return (_await$readProject$co = (await readProject(page, project, '/api/engineering/workflow?view=summary')).context.agent_execution) === null || _await$readProject$co === void 0 ? void 0 : _await$readProject$co.updated_at;
      }, {
        timeout: 60000
      }).not.toBe(execution.updated_at);
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
  await dialog.getByTitle('Aufgabe', {
    exact: true
  }).click();
  await dialog.getByLabel('Aufgabentext', {
    exact: true
  }).fill('Erzeuge ein Automotive CAN-FD Netzwerk mit einem Gateway System, den ECUs Motorsteuerung und Anzeige, einem Sensor MotorTemperature und einem Aktor MotorValve. MotorTemperature wird von Motorsteuerung ausgewertet. Motorsteuerung steuert MotorValve. Statuswerte werden an Anzeige und System übermittelt. Prüfe und arbeite bis Data Science & Intelligence.');
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
  test(`Raspberry Pi temperature and valve project completes all nine stages using ${technology} @nonautomotive`, async ({
    page
  }, testInfo) => {
    const project = 'nis-e2e-embedded-' + randomUUID();
    const dialog = await openWizard(page, project);
    await dialog.getByTitle('Projektname', {
      exact: true
    }).click();
    await dialog.locator('#engineering-project-name').fill('Temperaturregelung');
    await dialog.getByTitle('Aufgabe', {
      exact: true
    }).click();
    await dialog.getByLabel('Aufgabentext', {
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
    const continuity = await completeThroughWizard(page, project, true, ['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4', 'Ventilaktor1', 'Ventilaktor2']);
    const artifacts = await verifyArtifacts(page, project, 7, 'RaspberryPi');
    const interfaces = await allObjects(page, project, 'hardware-interfaces');
    expect(interfaces.length).toBeGreaterThanOrEqual(7);
    expect(interfaces.every(item => !/automotive|can|lin/i.test(item.technology))).toBe(true);
    const hardware = await allObjects(page, project, 'hardware-nodes');
    expect(hardware.every(item => item.domain !== 'automotive')).toBe(true);
    if (technology === 'I2C') {
      const signals = await allObjects(page, project, 'signals');
      expect(signals.some(item => item.name === 'Temperatur_Temperatursensor1' && item.unit === 'degC')).toBe(true);
    }
    const finished = page.waitForResponse(response => response.url().includes(`/runs/${continuity.runId}/finish`) && response.request().method() === 'POST');
    await dialog.getByRole('button', {
      name: 'Fertig stellen',
      exact: true
    }).click();
    expect((await finished).ok()).toBe(true);
    await expect(dialog).not.toBeVisible();
    await openWizard(page, project);
    expect((await readProject(page, project, '/api/simulations')).jobs).toHaveLength(1);
    await testInfo.attach('nonautomotive-evidence', {
      body: JSON.stringify({
        project,
        technology,
        ...continuity,
        ...artifacts
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
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmVhZEZpbGUiLCJyYW5kb21VVUlEIiwiZXhlY0ZpbGVTeW5jIiwiV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyIsIldJWkFSRF9TVEVQUyIsIldJWkFSRF9ET05FIiwic3RlcHMiLCJkb25lIiwid3JpdGVUaW1pbmdzIiwiTWFwIiwid29ya2Zsb3dQYWdlRmFpbHVyZXMiLCJXZWFrTWFwIiwicHJvZ3Jlc3NNaWxlc3RvbmVzIiwiYmVmb3JlRWFjaCIsInBhZ2UiLCJpbmZvIiwicm93cyIsInNldCIsInRlc3RJZCIsInJlcXVlc3RzIiwib24iLCJyZXF1ZXN0IiwiaW5jbHVkZXMiLCJtZXRob2QiLCJyb3ciLCJ1cmwiLCJzdGFydGVkIiwiRGF0ZSIsIm5vdyIsInB1c2giLCJyZXNwb25zZSIsImdldCIsInN0YXR1cyIsIlVSTCIsInBhdGhuYW1lIiwiZHVyYXRpb25fbXMiLCJfcmVxdWVzdCRmYWlsdXJlIiwiZmFpbHVyZSIsImVycm9yVGV4dCIsImFmdGVyRWFjaCIsImF0dGFjaCIsImJvZHkiLCJKU09OIiwic3RyaW5naWZ5IiwiY29udGVudFR5cGUiLCJkZWxldGUiLCJ0b0VxdWFsIiwiYXNzZXJ0RW5naW5lZXJpbmdQYWdlSGVhbHRoeSIsImdldEJ5VGV4dCIsImV4YWN0IiwiaXNWaXNpYmxlIiwidG9CZSIsInJlYWRQcm9qZWN0IiwicHJvamVjdCIsInBhdGgiLCJyZXN1bHQiLCJoZWFkZXJzIiwidGltZW91dCIsIm9rIiwiRXJyb3IiLCJ0ZXh0Iiwic2xpY2UiLCJqc29uIiwib3BlbldpemFyZCIsImdvdG8iLCJ3YWl0VW50aWwiLCJkaWFsb2ciLCJnZXRCeVJvbGUiLCJuYW1lIiwidG9CZVZpc2libGUiLCJhbGxPYmplY3RzIiwicmVzb3VyY2UiLCJpdGVtcyIsIm9mZnNldCIsImxlbmd0aCIsInJlc3RhcnRBcHBsaWNhdGlvbiIsImNyYXNoIiwiY29udGFpbmVyIiwicHJvY2VzcyIsImVudiIsIk5JU19FMkVfQVBQX0NPTlRBSU5FUiIsInRvTWF0Y2giLCJkb2NrZXIiLCJOSVNfVEVTVF9ET0NLRVIiLCJsYWJlbCIsImVuY29kaW5nIiwidHJpbSIsInBvbGwiLCJ2ZXJpZnlTaWduYWxDb250cmFjdHMiLCJleHBlY3RlZCIsImhhcmR3YXJlIiwiZnVuY3Rpb25zIiwibWVzc2FnZXMiLCJzaWduYWxzIiwiUHJvbWlzZSIsImFsbCIsIm1hcCIsIm5vZGVzIiwiaXRlbSIsImlkIiwiZnVuY3Rpb25zQnlJZCIsIm1lc3NhZ2VzQnlJZCIsImNvbnRyYWN0cyIsInNpZ25hbCIsIl9yZWYiLCJfc2lnbmFsJGRhdGEkZW51bV92YWwiLCJfc2lnbmFsJGRhdGEiLCJfc2lnbmFsJHNlbWFudGljJHNlbWEiLCJfc2lnbmFsJHNlbWFudGljIiwiX3NpZ25hbCRjb25maWd1cmF0aW9uIiwiX3NpZ25hbCRjb25maWd1cmF0aW9uMiIsIm1lc3NhZ2UiLCJtZXNzYWdlX2lkIiwidG9CZVRydXRoeSIsInJlZmVyZW5jZSIsImNvbmZpZ3VyYXRpb24iLCJjb21tdW5pY2F0aW9uX2NvbnRyYWN0IiwicHJvZHVjZXJfcmVmIiwiZm4iLCJvd25lciIsImhhcmR3YXJlX25vZGVfaWQiLCJwcm9kdWNlciIsImRldmljZV90eXBlIiwia2V5Iiwiam9pbiIsInRvQmVVbmRlZmluZWQiLCJPYmplY3QiLCJmcm9tRW50cmllcyIsImZpZWxkIiwiX3NpZ25hbCRmaWVsZCIsImVudW1fdmFsdWVzIiwiZGF0YSIsInNlbWFudGljX3R5cGUiLCJzZW1hbnRpYyIsImdlbmVyYXRpb25fcm9sZSIsInZlcmlmeUFydGlmYWN0cyIsIm1pbmltdW1TaWduYWxzIiwiaW50ZXJuYWxDb250cm9sbGVyIiwiX2Fzc2Vzc21lbnQkc2NvcGVfY292Iiwid29ya2Zsb3ciLCJrZXlzIiwic3RhdHVzZXMiLCJzb3J0Iiwic3RlcCIsImhhcyIsImpvYnMiLCJ0b0hhdmVMZW5ndGgiLCJzbmFwc2hvdHMiLCJzbmFwc2hvdCIsInNpbXVsYXRpb25zIiwiZmluZCIsImpvYl9pZCIsImZ1bGwiLCJhc3Nlc3NtZW50Iiwic2NvcGVfY292ZXJhZ2UiLCJzY29wZV9tb2RlIiwiY29tcGxldGUiLCJjb25mb3JtYW5jZSIsImZhaWxlZF9yb3V0ZV9jb3VudCIsIm9ic2VydmVkX3NpZ25hbF9jb3VudCIsInRvQmVHcmVhdGVyVGhhbk9yRXF1YWwiLCJleGNsdWRlZCIsInRyYW5zcG9ydF9leGNsdXNpb25zIiwiY29udHJvbGxlciIsInRvQmVHcmVhdGVyVGhhbiIsInJlYXNvbl9jb2RlIiwicm91dGluZyIsImVuYWJsZWQiLCJ0b01hdGNoT2JqZWN0Iiwicm9sZSIsInNjb3BlIiwiY29uc3VtZXJfcmVmcyIsImV4Y2x1ZGVkU2lnbmFscyIsIlNldCIsImZsYXRNYXAiLCJzaWduYWxfaWRzIiwic2l6ZSIsInRyYWNlIiwiY291bnQiLCJldmVudHMiLCJzb21lIiwiam9iIiwiY29tcGxldGVUaHJvdWdoV2l6YXJkIiwicmVzdGFydCIsImV4cGVjdGVkSGFyZHdhcmUiLCJjcmFzaFNpbXVsYXRpb24iLCJleHBlY3RlZFNpZ25hbHMiLCJhZnRlckZpcnN0TW9kZWxBcHBsaWVkIiwicmV2aWV3Q291bnQiLCJydW5JZCIsInJldmlld2VkIiwicmVzdGFydGVkSm9iSWQiLCJ3YXRjaGRvZyIsInBlcmZvcm1hbmNlIiwiY2hlY2twb2ludCIsIl93b3JrZmxvdyRjb250ZXh0JGFnZSIsIl93b3JrZmxvdyRjb250ZXh0JGFnZTIiLCJwcm9wb3NhbElkIiwicmVhZHlWZXJzaW9uIiwicmVhZHlTaW5jZSIsImlzQ2hlY2twb2ludCIsInJlbWFpbmluZyIsInByb2dyZXNzIiwib2JzZXJ2ZSIsImFkdmFuY2VkIiwiYXQiLCJ0b0lTT1N0cmluZyIsImZyb250aWVyIiwiY29tcGxldGVkVGhyb3VnaCIsInByb2plY3RfaWQiLCJleGVjdXRpb24iLCJjb250ZXh0IiwiYWdlbnRfZXhlY3V0aW9uIiwidmFsaWRhdGlvbiIsInJ1bm5pbmciLCJldmVyeSIsInN0YXRlIiwiY29udmVyc2F0aW9uIiwiYWN0aXZlX3Byb3Bvc2FsIiwiQm9vbGVhbiIsInJlY292ZXJhYmxlIiwidXBkYXRlZF9hdCIsImJ1dHRvbiIsImV2YWx1YXRlQWxsIiwiYnV0dG9ucyIsImRpc2FibGVkIiwiZ2V0Q2xpZW50UmVjdHMiLCJnZXRDb21wdXRlZFN0eWxlIiwidmlzaWJpbGl0eSIsImF0dGVtcHQiLCJ3YWl0Rm9yVGltZW91dCIsIk1hdGgiLCJtaW4iLCJydW5faWQiLCJfY29udmVyc2F0aW9uJGRhdGEiLCJfcHJvcG9zYWwkZGF0YSIsInByb3Bvc2FsIiwidmFsaWRhdGlvbl9yZXN1bHQiLCJ2aXNpYmxlIiwiaW5uZXJUZXh0IiwiY2xpY2siLCJlcnJvciIsIl9sYXRlc3QkY29udGV4dCRhZ2VudCIsImxhdGVzdCIsIl9hd2FpdCRyZWFkUHJvamVjdCRjbyIsIm5vdCIsImNhbmRpZGF0ZSIsInByb3Bvc2FsX3R5cGUiLCJjaGFuZ2VzIiwiZmlsdGVyIiwiY2hhbmdlIiwib2JqZWN0X3R5cGUiLCJhcnJheUNvbnRhaW5pbmciLCJhcHBseVJlc3BvbnNlIiwid2FpdEZvclJlc3BvbnNlIiwiYXBwcm92YWwiLCJ0b0JlRW5hYmxlZCIsImFwcGxpZWQiLCJhZGQiLCJfYW1lbmRlZCRjb250ZXh0JGFnZW4iLCJhbWVuZGVkIiwiX2N1cnJlbnQkY29udGV4dCRhZ2VuIiwiY3VycmVudCIsInRlc3RJbmZvIiwiZXJyb3JzIiwiZ2V0QnlUaXRsZSIsImxvY2F0b3IiLCJmaWxsIiwiZ2V0QnlMYWJlbCIsInZhbHVlIiwic3RhcnRSZXF1ZXN0Iiwid2FpdEZvclJlcXVlc3QiLCJfcmVxdWVzdCRwb3N0RGF0YUpTT04iLCJlbmRzV2l0aCIsInBvc3REYXRhSlNPTiIsIndpemFyZF9jb21tYW5kIiwiYWN0aW9uIiwic3VibWl0IiwicmVxdWVzdGVkIiwid2l6YXJkX2NvbnRleHQiLCJ0ZWNobm9sb2dpZXMiLCJjb250aW51aXR5IiwiYXJ0aWZhY3RzIiwiZmluaXNoZWQiLCJ0ZWNobm9sb2d5IiwiY2hlY2siLCJ0b0JlRGlzYWJsZWQiLCJzZWxlY3RPcHRpb24iLCJ0b0hhdmVWYWx1ZSIsImludGVyZmFjZXMiLCJkb21haW4iLCJ1bml0Iiwib3JpZ2luYWwiLCJpbXBvcnQiLCJtZXRhIiwibWV0YWRhdGEiLCJwYXJzZSIsImJhc2VsaW5lIiwicHJvbXB0IiwicmVwbGFjZSIsInBvc3QiLCJvcGVyYXRpb25faWQiLCJ0YXJnZXQiLCJmaXh0dXJlIiwicmVxdWVzdF9zaGEyNTYiLCJncmFwaCIsImNsdXN0ZXJfaWQiLCJuZXR3b3JrX2lkIiwibmV0d29ya19sYWJlbCIsImJ1c19uYW1lIiwiY29udHJvbGxlcnMiLCJlY3UiLCJzZW5zb3JzIiwiYWN0dWF0b3JzIiwiaG1pX3JvdXRlcyIsInNvdXJjZSIsInByb2plY3RfbmFtZSIsInNjb3BlX2lkcyIsIm1vZGUiLCJwcm9jZXNzX2lkcyIsInRhc2siLCJvcmlnaW5hbE5ldHdvcmtzIiwiYW1lbmQiLCJwYXJhbWV0ZXJzIiwibmV0d29ya3MiLCJleHBhbmQiLCJ1bmRlZmluZWQiLCJpZGVudGl0eSIsInN5c3RlbV9vd25lcl9pZCIsInNlbnNvck5ldHdvcmsiLCJ0b3BvbG9neSIsImxvY2FsRWRnZSIsImVkZ2VzIiwiZWRnZSIsInBoeXNpY2FsTmV0d29ya0lkIiwiYnVzIiwidmFsdWVzIiwicm91dGluZ01ldGFkYXRhIiwidG9Db250YWluRXF1YWwiLCJvYmplY3RDb250YWluaW5nIiwiYXBwcm92YWxTdGF0ZSIsInByb3RvY29sIiwic2lkZSIsImhhcmR3YXJlSWQiLCJub2RlIiwiZW5naW5lZXJpbmdJZCIsInBvcnRzIl0sInNvdXJjZXMiOlsid2l6YXJkLnNwZWMudHMiXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgdGVzdCwgZXhwZWN0LCB0eXBlIFBhZ2UgfSBmcm9tICdwbGF5d3JpZ2h0L3Rlc3QnO1xyXG5pbXBvcnQgeyByZWFkRmlsZSB9IGZyb20gJ25vZGU6ZnMvcHJvbWlzZXMnO1xyXG5pbXBvcnQgeyByYW5kb21VVUlEIH0gZnJvbSAnbm9kZTpjcnlwdG8nO1xyXG5pbXBvcnQgeyBleGVjRmlsZVN5bmMgfSBmcm9tICdub2RlOmNoaWxkX3Byb2Nlc3MnO1xyXG5pbXBvcnQgeyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nLCBXSVpBUkRfU1RFUFMsIFdJWkFSRF9ET05FIH0gZnJvbSAnLi9zdXBwb3J0L3dpemFyZC1wcm9ncmVzcy13YXRjaGRvZyc7XHJcblxyXG5jb25zdCBzdGVwcyA9IFdJWkFSRF9TVEVQUztcclxuY29uc3QgZG9uZSA9IFdJWkFSRF9ET05FO1xyXG50eXBlIFdyaXRlVGltaW5nID0geyB1cmw6IHN0cmluZzsgc3RhcnRlZDogbnVtYmVyOyBkdXJhdGlvbl9tcz86IG51bWJlcjsgc3RhdHVzPzogbnVtYmVyOyBmYWlsdXJlPzogc3RyaW5nIH07XHJcbmNvbnN0IHdyaXRlVGltaW5ncyA9IG5ldyBNYXA8c3RyaW5nLCBXcml0ZVRpbWluZ1tdPigpO1xyXG5jb25zdCB3b3JrZmxvd1BhZ2VGYWlsdXJlcyA9IG5ldyBXZWFrTWFwPFBhZ2UsIHN0cmluZ1tdPigpO1xyXG5jb25zdCBwcm9ncmVzc01pbGVzdG9uZXMgPSBuZXcgTWFwPHN0cmluZywgdW5rbm93bltdPigpO1xyXG5cclxudGVzdC5iZWZvcmVFYWNoKGFzeW5jICh7IHBhZ2UgfSwgaW5mbykgPT4ge1xyXG4gIGNvbnN0IHJvd3M6IFdyaXRlVGltaW5nW10gPSBbXTtcclxuICB3cml0ZVRpbWluZ3Muc2V0KGluZm8udGVzdElkLCByb3dzKTtcclxuICB3b3JrZmxvd1BhZ2VGYWlsdXJlcy5zZXQocGFnZSwgW10pO1xyXG4gIHByb2dyZXNzTWlsZXN0b25lcy5zZXQoaW5mby50ZXN0SWQsIFtdKTtcclxuICBjb25zdCByZXF1ZXN0cyA9IG5ldyBNYXA8b2JqZWN0LCBXcml0ZVRpbWluZz4oKTtcclxuICBwYWdlLm9uKCdyZXF1ZXN0JywgcmVxdWVzdCA9PiB7XHJcbiAgICBpZiAoIVsnUE9TVCcsICdQVVQnLCAnUEFUQ0gnLCAnREVMRVRFJ10uaW5jbHVkZXMocmVxdWVzdC5tZXRob2QoKSkpIHJldHVybjtcclxuICAgIGNvbnN0IHJvdyA9IHsgdXJsOiByZXF1ZXN0LnVybCgpLCBzdGFydGVkOiBEYXRlLm5vdygpIH07XHJcbiAgICByb3dzLnB1c2gocm93KTsgcmVxdWVzdHMuc2V0KHJlcXVlc3QsIHJvdyk7XHJcbiAgfSk7XHJcbiAgcGFnZS5vbigncmVzcG9uc2UnLCByZXNwb25zZSA9PiB7XHJcbiAgICBjb25zdCByb3cgPSByZXF1ZXN0cy5nZXQocmVzcG9uc2UucmVxdWVzdCgpKTtcclxuICAgIGlmIChyb3cpIHJvdy5zdGF0dXMgPSByZXNwb25zZS5zdGF0dXMoKTtcclxuICAgIGlmIChyZXNwb25zZS5zdGF0dXMoKSA9PT0gNDEzICYmIC9eXFwvYXBpXFwvZW5naW5lZXJpbmdcXC93b3JrZmxvdyg/OlxcL3wkKS8udGVzdChuZXcgVVJMKHJlc3BvbnNlLnVybCgpKS5wYXRobmFtZSkpIHtcclxuICAgICAgd29ya2Zsb3dQYWdlRmFpbHVyZXMuZ2V0KHBhZ2UpIS5wdXNoKGBIVFRQIDQxMzogJHtyZXNwb25zZS51cmwoKX1gKTtcclxuICAgIH1cclxuICB9KTtcclxuICBwYWdlLm9uKCdyZXF1ZXN0ZmluaXNoZWQnLCByZXF1ZXN0ID0+IHtcclxuICAgIGNvbnN0IHJvdyA9IHJlcXVlc3RzLmdldChyZXF1ZXN0KTtcclxuICAgIGlmIChyb3cpIHJvdy5kdXJhdGlvbl9tcyA9IERhdGUubm93KCkgLSByb3cuc3RhcnRlZDtcclxuICB9KTtcclxuICBwYWdlLm9uKCdyZXF1ZXN0ZmFpbGVkJywgcmVxdWVzdCA9PiB7XHJcbiAgICBjb25zdCByb3cgPSByZXF1ZXN0cy5nZXQocmVxdWVzdCk7XHJcbiAgICBpZiAocm93KSB7IHJvdy5kdXJhdGlvbl9tcyA9IERhdGUubm93KCkgLSByb3cuc3RhcnRlZDsgcm93LmZhaWx1cmUgPSByZXF1ZXN0LmZhaWx1cmUoKT8uZXJyb3JUZXh0OyB9XHJcbiAgfSk7XHJcbn0pO1xyXG5cclxudGVzdC5hZnRlckVhY2goYXN5bmMgKHsgcGFnZSB9LCBpbmZvKSA9PiB7XHJcbiAgYXdhaXQgaW5mby5hdHRhY2goJ3dyaXRlLXJlcXVlc3QtdGltaW5ncycsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkod3JpdGVUaW1pbmdzLmdldChpbmZvLnRlc3RJZCkgfHwgW10pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG4gIGF3YWl0IGluZm8uYXR0YWNoKCd3b3JrZmxvdy1wcm9ncmVzcy1ib3VuZGFyaWVzJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeShwcm9ncmVzc01pbGVzdG9uZXMuZ2V0KGluZm8udGVzdElkKSB8fCBbXSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgYXdhaXQgaW5mby5hdHRhY2goJ3dvcmtmbG93LXBhZ2UtZmFpbHVyZXMnLCB7IGJvZHk6IEpTT04uc3RyaW5naWZ5KHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSB8fCBbXSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgd3JpdGVUaW1pbmdzLmRlbGV0ZShpbmZvLnRlc3RJZCk7XHJcbiAgcHJvZ3Jlc3NNaWxlc3RvbmVzLmRlbGV0ZShpbmZvLnRlc3RJZCk7XHJcbiAgZXhwZWN0KHdvcmtmbG93UGFnZUZhaWx1cmVzLmdldChwYWdlKSwgJ1RoZSB1bmRlcmx5aW5nIGVuZ2luZWVyaW5nIHBhZ2UgbXVzdCByZW1haW4gcmVhZGFibGUgdGhyb3VnaG91dCByZWxvYWQgYW5kIHJlY292ZXJ5LicpLnRvRXF1YWwoW10pO1xyXG59KTtcclxuXHJcbmFzeW5jIGZ1bmN0aW9uIGFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkocGFnZTogUGFnZSkge1xyXG4gIGV4cGVjdCh3b3JrZmxvd1BhZ2VGYWlsdXJlcy5nZXQocGFnZSksICdBIHdvcmtpbmcgd2l6YXJkIG92ZXJsYXkgbXVzdCBub3QgY29uY2VhbCBhIHdvcmtmbG93IEhUVFAgNDEzLicpLnRvRXF1YWwoW10pO1xyXG4gIGV4cGVjdChhd2FpdCBwYWdlLmdldEJ5VGV4dCgnRW5naW5lZXJpbmctQVBJIG5pY2h0IGVycmVpY2hiYXInLCB7IGV4YWN0OiB0cnVlIH0pLmlzVmlzaWJsZSgpLFxyXG4gICAgJ1RoZSB1bmRlcmx5aW5nIGVuZ2luZWVyaW5nIHBhZ2UgbXVzdCBub3Qgc2hvdyBpdHMgQVBJIGVycm9yIHZpZXcuJykudG9CZShmYWxzZSk7XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHJlYWRQcm9qZWN0KHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgcGF0aDogc3RyaW5nKSB7XHJcbiAgY29uc3QgcmVzdWx0ID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldChwYXRoLCB7IGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSwgdGltZW91dDogNjBfMDAwIH0pO1xyXG4gIGlmICghcmVzdWx0Lm9rKCkpIHRocm93IG5ldyBFcnJvcihgJHtwYXRofTogSFRUUCAke3Jlc3VsdC5zdGF0dXMoKX0gJHsoYXdhaXQgcmVzdWx0LnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgcmV0dXJuIHJlc3VsdC5qc29uKCk7XHJcbn1cclxuXHJcbmFzeW5jIGZ1bmN0aW9uIG9wZW5XaXphcmQocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nKSB7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvL2VuZ2luZWVyaW5nP2Fzc2lzdGFudD1wcm9qZWN0JnByb2plY3Q9JHtwcm9qZWN0fWAsIHsgd2FpdFVudGlsOiAnbG9hZCcgfSk7XHJcbiAgY29uc3QgZGlhbG9nID0gcGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IGFzc2VydEVuZ2luZWVyaW5nUGFnZUhlYWx0aHkocGFnZSk7XHJcbiAgcmV0dXJuIGRpYWxvZztcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gYWxsT2JqZWN0cyhwYWdlOiBQYWdlLCBwcm9qZWN0OiBzdHJpbmcsIHJlc291cmNlOiBzdHJpbmcpIHtcclxuICBjb25zdCBpdGVtczogYW55W10gPSBbXTtcclxuICBmb3IgKGxldCBvZmZzZXQgPSAwOyA7IG9mZnNldCArPSA1MDApIHtcclxuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvJHtyZXNvdXJjZX0/bGltaXQ9NTAwJm9mZnNldD0ke29mZnNldH1gKTtcclxuICAgIGl0ZW1zLnB1c2goLi4ucmVzcG9uc2UuaXRlbXMpO1xyXG4gICAgaWYgKHJlc3BvbnNlLml0ZW1zLmxlbmd0aCA8IDUwMCkgcmV0dXJuIGl0ZW1zO1xyXG4gIH1cclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2U6IFBhZ2UsIGNyYXNoID0gZmFsc2UpIHtcclxuICBjb25zdCBjb250YWluZXIgPSBwcm9jZXNzLmVudi5OSVNfRTJFX0FQUF9DT05UQUlORVIhO1xyXG4gIGV4cGVjdChjb250YWluZXIpLnRvTWF0Y2goL15uaXMtZTJlLWFwcC1bYS1mMC05XSskLyk7XHJcbiAgY29uc3QgZG9ja2VyID0gcHJvY2Vzcy5lbnYuTklTX1RFU1RfRE9DS0VSIHx8ICdkb2NrZXInO1xyXG4gIGNvbnN0IGxhYmVsID0gZXhlY0ZpbGVTeW5jKGRvY2tlciwgWydpbnNwZWN0JywgY29udGFpbmVyLCAnLS1mb3JtYXQnLCAne3tpbmRleCAuQ29uZmlnLkxhYmVscyBcIm5ldHdvcmtpcy50ZXN0XCJ9fSddLCB7IGVuY29kaW5nOiAndXRmOCcgfSkudHJpbSgpO1xyXG4gIGV4cGVjdChsYWJlbCkudG9CZSgnZGlzcG9zYWJsZScpO1xyXG4gIGV4ZWNGaWxlU3luYyhkb2NrZXIsIFsncmVzdGFydCcsIC4uLihjcmFzaCA/IFsnLXQnLCAnMCddIDogW10pLCBjb250YWluZXJdLCB7IHRpbWVvdXQ6IDYwXzAwMCB9KTtcclxuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICB0cnkgeyByZXR1cm4gKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvcmVhZHknLCB7IHRpbWVvdXQ6IDIwMDAgfSkpLm9rKCk7IH0gY2F0Y2ggeyByZXR1cm4gZmFsc2U7IH1cclxuICB9LCB7IHRpbWVvdXQ6IDEyMF8wMDAgfSkudG9CZSh0cnVlKTtcclxufVxyXG5cclxuYXN5bmMgZnVuY3Rpb24gdmVyaWZ5U2lnbmFsQ29udHJhY3RzKHBhZ2U6IFBhZ2UsIHByb2plY3Q6IHN0cmluZywgZXhwZWN0ZWQ6IFJlY29yZDxzdHJpbmcsIHVua25vd24+KSB7XHJcbiAgY29uc3QgW2hhcmR3YXJlLCBmdW5jdGlvbnMsIG1lc3NhZ2VzLCBzaWduYWxzXSA9IGF3YWl0IFByb21pc2UuYWxsKFxyXG4gICAgWydoYXJkd2FyZS1ub2RlcycsICdmdW5jdGlvbnMnLCAnbWVzc2FnZXMnLCAnc2lnbmFscyddLm1hcChyZXNvdXJjZSA9PiBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsIHJlc291cmNlKSkpO1xyXG4gIGNvbnN0IG5vZGVzID0gbmV3IE1hcChoYXJkd2FyZS5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBmdW5jdGlvbnNCeUlkID0gbmV3IE1hcChmdW5jdGlvbnMubWFwKGl0ZW0gPT4gW2l0ZW0uaWQsIGl0ZW1dKSk7XHJcbiAgY29uc3QgbWVzc2FnZXNCeUlkID0gbmV3IE1hcChtZXNzYWdlcy5tYXAoaXRlbSA9PiBbaXRlbS5pZCwgaXRlbV0pKTtcclxuICBjb25zdCBjb250cmFjdHM6IFJlY29yZDxzdHJpbmcsIHVua25vd24+ID0ge307XHJcbiAgZm9yIChjb25zdCBzaWduYWwgb2Ygc2lnbmFscykge1xyXG4gICAgY29uc3QgbWVzc2FnZSA9IG1lc3NhZ2VzQnlJZC5nZXQoc2lnbmFsLm1lc3NhZ2VfaWQpO1xyXG4gICAgZXhwZWN0KG1lc3NhZ2UpLnRvQmVUcnV0aHkoKTtcclxuICAgIGNvbnN0IHJlZmVyZW5jZSA9IG1lc3NhZ2UuY29uZmlndXJhdGlvbi5jb21tdW5pY2F0aW9uX2NvbnRyYWN0LnByb2R1Y2VyX3JlZjtcclxuICAgIGNvbnN0IGZuID0gZnVuY3Rpb25zQnlJZC5nZXQocmVmZXJlbmNlKTtcclxuICAgIGNvbnN0IG93bmVyID0gbm9kZXMuZ2V0KHJlZmVyZW5jZSkgfHwgKGZuICYmIG5vZGVzLmdldChmbi5oYXJkd2FyZV9ub2RlX2lkKSk7XHJcbiAgICBjb25zdCBwcm9kdWNlciA9IG93bmVyPy5kZXZpY2VfdHlwZSA9PT0gJ0dhdGV3YXknID8gJyRnYXRld2F5JyA6IChub2Rlcy5nZXQocmVmZXJlbmNlKSB8fCBmbik/Lm5hbWU7XHJcbiAgICBleHBlY3QocHJvZHVjZXIpLnRvQmVUcnV0aHkoKTtcclxuICAgIGNvbnN0IGtleSA9IFtwcm9kdWNlciwgbWVzc2FnZS5uYW1lLCBzaWduYWwubmFtZV0uam9pbignIDo6ICcpO1xyXG4gICAgZXhwZWN0KGNvbnRyYWN0c1trZXldLCAnU2VtYW50aWMgc2lnbmFsIGlkZW50aXR5IG11c3QgYmUgdW5pcXVlOiAnICsga2V5KS50b0JlVW5kZWZpbmVkKCk7XHJcbiAgICBjb250cmFjdHNba2V5XSA9IHtcclxuICAgICAgLi4uT2JqZWN0LmZyb21FbnRyaWVzKFsnc3RhcnRfYml0JywgJ2xlbmd0aF9iaXRzJywgJ2RhdGFfdHlwZScsICdmYWN0b3InLCAnb2Zmc2V0X3ZhbHVlJyxcclxuICAgICAgICAndW5pdCcsICdtaW5fdmFsdWUnLCAnbWF4X3ZhbHVlJywgJ2J5dGVfb3JkZXInXS5tYXAoZmllbGQgPT4gW2ZpZWxkLCBzaWduYWxbZmllbGRdID8/IG51bGxdKSksXHJcbiAgICAgIGVudW1fdmFsdWVzOiBzaWduYWwuZGF0YT8uZW51bV92YWx1ZXMgPz8gbnVsbCxcclxuICAgICAgc2VtYW50aWNfdHlwZTogc2lnbmFsLnNlbWFudGljPy5zZW1hbnRpY190eXBlID8/IG51bGwsXHJcbiAgICAgIGdlbmVyYXRpb25fcm9sZTogc2lnbmFsLmNvbmZpZ3VyYXRpb24/LmdlbmVyYXRpb25fcm9sZSA/PyBudWxsLFxyXG4gICAgfTtcclxuICB9XHJcbiAgZXhwZWN0KGNvbnRyYWN0cywgJ0V2ZXJ5IG9yaWdpbmFsIHNpZ25hbCBhbmQgaXRzIGV4cGxpY2l0IGVuY29kaW5nIG11c3Qgc3Vydml2ZSBnZW5lcmF0aW9uLicpLnRvRXF1YWwoZXhwZWN0ZWQpO1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiB2ZXJpZnlBcnRpZmFjdHMocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCBtaW5pbXVtU2lnbmFsczogbnVtYmVyLCBpbnRlcm5hbENvbnRyb2xsZXI/OiBzdHJpbmcpIHtcbiAgY29uc3Qgd29ya2Zsb3cgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICBleHBlY3QoT2JqZWN0LmtleXMod29ya2Zsb3cuc3RhdHVzZXMpLnNvcnQoKSkudG9FcXVhbChbLi4uc3RlcHNdLnNvcnQoKSk7XHJcbiAgZm9yIChjb25zdCBzdGVwIG9mIHN0ZXBzKSBleHBlY3QoZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXNbc3RlcF0pLCBgJHtzdGVwfTogJHt3b3JrZmxvdy5zdGF0dXNlc1tzdGVwXX1gKS50b0JlVHJ1dGh5KCk7XHJcbiAgY29uc3Qgam9icyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9zaW11bGF0aW9ucycpKS5qb2JzO1xyXG4gIGV4cGVjdChqb2JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KGpvYnNbMF0uc3RhdHVzKS50b0JlKCdjb21wbGV0ZWQnKTtcclxuICBjb25zdCBzbmFwc2hvdHMgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9zbmFwc2hvdHMnKTtcclxuICBjb25zdCBzbmFwc2hvdCA9IHNuYXBzaG90cy5zaW11bGF0aW9ucy5maW5kKChpdGVtOiB7IGpvYl9pZDogc3RyaW5nIH0pID0+IGl0ZW0uam9iX2lkID09PSBqb2JzWzBdLmlkKTtcclxuICBleHBlY3Qoc25hcHNob3QpLnRvQmVUcnV0aHkoKTtcclxuICBjb25zdCBmdWxsID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvc2ltdWxhdGlvbi1zbmFwc2hvdHMvJHtzbmFwc2hvdC5pZH1gKTtcclxuICBjb25zdCBhc3Nlc3NtZW50ID0gZnVsbC5yZXN1bHQuYXNzZXNzbWVudDtcclxuICBleHBlY3QoYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS5zY29wZV9tb2RlKS50b0JlKCdBTEwnKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5zY29wZV9jb3ZlcmFnZS5jb21wbGV0ZSkudG9CZSh0cnVlKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5jb25mb3JtYW5jZSkudG9CZSgnUEFTUycpO1xyXG4gIGV4cGVjdChhc3Nlc3NtZW50LmZhaWxlZF9yb3V0ZV9jb3VudCkudG9CZSgwKTtcclxuICBleHBlY3QoYXNzZXNzbWVudC5vYnNlcnZlZF9zaWduYWxfY291bnQpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwobWluaW11bVNpZ25hbHMpO1xyXG4gIGNvbnN0IHNpZ25hbHMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdzaWduYWxzJyk7XHJcbiAgY29uc3QgZXhjbHVkZWQgPSBhc3Nlc3NtZW50LnNjb3BlX2NvdmVyYWdlLnRyYW5zcG9ydF9leGNsdXNpb25zID8/IFtdO1xuICBpZiAoaW50ZXJuYWxDb250cm9sbGVyKSB7XG4gICAgY29uc3Qgbm9kZXMgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xuICAgIGNvbnN0IGNvbnRyb2xsZXIgPSBub2Rlcy5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSBpbnRlcm5hbENvbnRyb2xsZXIpO1xuICAgIGNvbnN0IG1lc3NhZ2VzID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnbWVzc2FnZXMnKTtcbiAgICBleHBlY3QoZXhjbHVkZWQubGVuZ3RoKS50b0JlR3JlYXRlclRoYW4oMCk7XG4gICAgZm9yIChjb25zdCBpdGVtIG9mIGV4Y2x1ZGVkKSB7XG4gICAgICBjb25zdCBtZXNzYWdlID0gbWVzc2FnZXMuZmluZChyb3cgPT4gcm93LmlkID09PSBpdGVtLm1lc3NhZ2VfaWQpO1xuICAgICAgZXhwZWN0KGl0ZW0ucmVhc29uX2NvZGUpLnRvQmUoJ0VYUExJQ0lUX0ZVTkNUSU9OX09VVFBVVF9OT1RfUk9VVEVEJyk7XG4gICAgICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLnJvdXRpbmcuZW5hYmxlZCkudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QobWVzc2FnZS5jb25maWd1cmF0aW9uLmNvbW11bmljYXRpb25fY29udHJhY3QpLnRvTWF0Y2hPYmplY3QoeyByb2xlOiAnSU5URVJOQUxfU1RBVEUnLCBzY29wZTogJ0ZVTkNUSU9OX09VVFBVVCcsIHByb2R1Y2VyX3JlZjogY29udHJvbGxlci5pZCwgY29uc3VtZXJfcmVmczogW10gfSk7XG4gICAgfVxuICB9IGVsc2UgZXhwZWN0KGV4Y2x1ZGVkKS50b0hhdmVMZW5ndGgoMCk7XG4gIGNvbnN0IGV4Y2x1ZGVkU2lnbmFscyA9IG5ldyBTZXQoZXhjbHVkZWQuZmxhdE1hcCgoaXRlbTogeyBzaWduYWxfaWRzOiBzdHJpbmdbXSB9KSA9PiBpdGVtLnNpZ25hbF9pZHMpKTtcbiAgZXhwZWN0KGFzc2Vzc21lbnQub2JzZXJ2ZWRfc2lnbmFsX2NvdW50LCAnQUxMIG11c3Qgb2JzZXJ2ZSBldmVyeSBjYW5vbmljYWwgc2lnbmFsIHdpdGggYSB0cmFuc3BvcnQgb2JsaWdhdGlvbi4nKS50b0JlKHNpZ25hbHMubGVuZ3RoIC0gZXhjbHVkZWRTaWduYWxzLnNpemUpO1xuICBmb3IgKGNvbnN0IGtleSBvZiBbJ21pc3Npbmdfb2JzZXJ2ZWRfc2lnbmFsX2lkcycsICdtaXNzaW5nX29ic2VydmVkX3JvdXRlX2lkcycsICdtaXNzaW5nX29ic2VydmVkX25ldHdvcmtfaWRzJ10pIGV4cGVjdChhc3Nlc3NtZW50W2tleV0pLnRvRXF1YWwoW10pO1xyXG4gIGNvbnN0IHRyYWNlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvc2ltdWxhdGlvbnMvJHtqb2JzWzBdLmlkfS90cmFjZS13aW5kb3c/bGltaXQ9MTBgKTtcclxuICBleHBlY3QodHJhY2UuY291bnQpLnRvQmVHcmVhdGVyVGhhbigwKTtcclxuICBleHBlY3QodHJhY2UuZXZlbnRzLnNvbWUoKGl0ZW06IHsgc2lnbmFscz86IHVua25vd25bXSB9KSA9PiBpdGVtLnNpZ25hbHMgJiYgT2JqZWN0LmtleXMoaXRlbS5zaWduYWxzKS5sZW5ndGgpKS50b0JlVHJ1dGh5KCk7XHJcbiAgcmV0dXJuIHsgd29ya2Zsb3csIGpvYjogam9ic1swXS5pZCwgYXNzZXNzbWVudCB9O1xyXG59XHJcblxyXG5hc3luYyBmdW5jdGlvbiBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZTogUGFnZSwgcHJvamVjdDogc3RyaW5nLCByZXN0YXJ0OiBib29sZWFuLCBleHBlY3RlZEhhcmR3YXJlOiBzdHJpbmdbXSA9IFtdLCBjcmFzaFNpbXVsYXRpb24gPSBmYWxzZSxcclxuICBleHBlY3RlZFNpZ25hbHM/OiBSZWNvcmQ8c3RyaW5nLCB1bmtub3duPiwgYWZ0ZXJGaXJzdE1vZGVsQXBwbGllZD86ICgpID0+IFByb21pc2U8dm9pZD4pIHtcclxuICBsZXQgcmV2aWV3Q291bnQgPSAwO1xyXG4gIGxldCBydW5JZDogc3RyaW5nIHwgdW5kZWZpbmVkO1xyXG4gIGNvbnN0IHJldmlld2VkID0gbmV3IFNldDxzdHJpbmc+KCk7XHJcbiAgbGV0IHJlc3RhcnRlZEpvYklkOiBzdHJpbmcgfCB1bmRlZmluZWQ7XHJcbiAgbGV0IHdhdGNoZG9nID0gbmV3IFdpemFyZFByb2dyZXNzV2F0Y2hkb2cocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gIGZvciAobGV0IGNoZWNrcG9pbnQgPSAwOyBjaGVja3BvaW50IDwgMTY7IGNoZWNrcG9pbnQrKykge1xyXG4gICAgbGV0IHdvcmtmbG93OiBhbnk7XHJcbiAgICBsZXQgcHJvcG9zYWxJZCA9ICcnO1xyXG4gICAgbGV0IHJlYWR5VmVyc2lvbiA9ICcnO1xyXG4gICAgbGV0IHJlYWR5U2luY2UgPSAwO1xyXG4gICAgY29uc3QgaXNDaGVja3BvaW50ID0gYXN5bmMgKCkgPT4ge1xyXG4gICAgICB3YXRjaGRvZy5yZW1haW5pbmcocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gICAgICBhd2FpdCBhc3NlcnRFbmdpbmVlcmluZ1BhZ2VIZWFsdGh5KHBhZ2UpO1xyXG4gICAgICB3b3JrZmxvdyA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICBjb25zdCBwcm9ncmVzcyA9IHdhdGNoZG9nLm9ic2VydmUod29ya2Zsb3csIHBlcmZvcm1hbmNlLm5vdygpKTtcclxuICAgICAgaWYgKHByb2dyZXNzLmFkdmFuY2VkKSBwcm9ncmVzc01pbGVzdG9uZXMuZ2V0KHRlc3QuaW5mbygpLnRlc3RJZCkhLnB1c2goe1xyXG4gICAgICAgIGF0OiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksIGZyb250aWVyOiBwcm9ncmVzcy5mcm9udGllcixcclxuICAgICAgICBjb21wbGV0ZWRUaHJvdWdoOiBzdGVwc1twcm9ncmVzcy5mcm9udGllciAtIDFdLFxyXG4gICAgICAgIHByb2plY3Q6IHdvcmtmbG93LnByb2plY3RfaWQsIGV4ZWN1dGlvbjogd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb24sXHJcbiAgICAgIH0pO1xyXG4gICAgICBpZiAoY3Jhc2hTaW11bGF0aW9uICYmICFyZXN0YXJ0ZWRKb2JJZCAmJiBkb25lLmhhcyh3b3JrZmxvdy5zdGF0dXNlcy52YWxpZGF0aW9uKSkge1xyXG4gICAgICAgIGNvbnN0IGpvYnMgPSAoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icztcclxuICAgICAgICBjb25zdCBydW5uaW5nID0gam9icy5maW5kKChqb2I6IHsgc3RhdHVzOiBzdHJpbmcgfSkgPT4gam9iLnN0YXR1cyA9PT0gJ3J1bm5pbmcnKTtcclxuICAgICAgICBpZiAocnVubmluZykge1xyXG4gICAgICAgICAgcmVzdGFydGVkSm9iSWQgPSBydW5uaW5nLmlkO1xyXG4gICAgICAgICAgYXdhaXQgcmVzdGFydEFwcGxpY2F0aW9uKHBhZ2UsIHRydWUpO1xyXG4gICAgICAgICAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICAgICAgICAgIHJldHVybiBmYWxzZTtcclxuICAgICAgICB9XHJcbiAgICAgIH1cclxuICAgICAgaWYgKHN0ZXBzLmV2ZXJ5KHN0ZXAgPT4gZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXNbc3RlcF0pKSkgcmV0dXJuIHRydWU7XHJcbiAgICAgIGNvbnN0IGV4ZWN1dGlvbiA9IHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uO1xyXG4gICAgICBpZiAoZXhlY3V0aW9uPy5zdGF0ZSA9PT0gJ1JFVklFV19SRVFVSVJFRCcpIHtcclxuICAgICAgICBjb25zdCBjb252ZXJzYXRpb24gPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKTtcclxuICAgICAgICBwcm9wb3NhbElkID0gY29udmVyc2F0aW9uLmRhdGEuYWN0aXZlX3Byb3Bvc2FsO1xyXG4gICAgICAgIC8vIFBvbGxpbmcgbWF5IHN0aWxsIGV4cG9zZSB0aGUganVzdC1hcHBsaWVkIHJldmlldyB3aGlsZSB0aGUgVUkgc3RhcnRzXHJcbiAgICAgICAgLy8gaXRzIGR1cmFibGUgY29udGludWF0aW9uLiBXYWl0IGZvciBhIGRpc3RpbmN0IHByb3Bvc2FsLCBub3QgaXRzIGxhYmVsLlxyXG4gICAgICAgIHJldHVybiBCb29sZWFuKHByb3Bvc2FsSWQpICYmICFyZXZpZXdlZC5oYXMocHJvcG9zYWxJZCk7XHJcbiAgICAgIH1cclxuICAgICAgaWYgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdSRUFEWV9UT19DT05USU5VRScgfHwgKGV4ZWN1dGlvbj8uc3RhdGUgPT09ICdCTE9DS0VEJyAmJiBleGVjdXRpb24ucmVjb3ZlcmFibGUgPT09IHRydWUpKSB7XHJcbiAgICAgICAgaWYgKHJlYWR5VmVyc2lvbiAhPT0gZXhlY3V0aW9uLnVwZGF0ZWRfYXQpIHtcclxuICAgICAgICAgIHJlYWR5VmVyc2lvbiA9IGV4ZWN1dGlvbi51cGRhdGVkX2F0OyByZWFkeVNpbmNlID0gRGF0ZS5ub3coKTtcclxuICAgICAgICB9XHJcbiAgICAgICAgLy8gV2hpbGUgYSBsYXJnZSBjb250aW51YXRpb24gaXMgZ2VuZXJhdGluZywgdGhlIGxhc3QgY29tbWl0dGVkIHNlcnZlclxyXG4gICAgICAgIC8vIGNoZWNrcG9pbnQgY2FuIHN0aWxsIGJlIFJFQURZLiBBY3Qgb25seSB3aGVuIHRoZSBVSSBvZmZlcnMgaXQgdG9vLlxyXG4gICAgICAgIGNvbnN0IGJ1dHRvbiA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSlcclxuICAgICAgICAgIC5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1ZnRyYWcgZm9ydHNldHplbicsIGV4YWN0OiB0cnVlIH0pO1xyXG4gICAgICAgIHJldHVybiBEYXRlLm5vdygpIC0gcmVhZHlTaW5jZSA+IDUwMDAgJiYgYXdhaXQgYnV0dG9uLmV2YWx1YXRlQWxsKGJ1dHRvbnMgPT4gYnV0dG9ucy5zb21lKGJ1dHRvbiA9PiAhKGJ1dHRvbiBhcyBIVE1MQnV0dG9uRWxlbWVudCkuZGlzYWJsZWQgJiYgYnV0dG9uLmdldENsaWVudFJlY3RzKCkubGVuZ3RoID4gMCAmJiBnZXRDb21wdXRlZFN0eWxlKGJ1dHRvbikudmlzaWJpbGl0eSAhPT0gXCJoaWRkZW5cIikpO1xyXG4gICAgICB9XHJcbiAgICAgIHJldHVybiBbJ0JMT0NLRUQnLCAnRkFJTEVEJywgJ0lOQ09NUExFVEUnXS5pbmNsdWRlcyhleGVjdXRpb24/LnN0YXRlKTtcclxuICAgIH07XHJcbiAgICAvLyBBIHNpbmdsZSBwb2xsIHByZXZpb3VzbHkgdGltZWQgYWxsIG9mIENhcGFjaXR5IC0+IEludGVsbGlnZW5jZSB0b2dldGhlci5cclxuICAgIC8vIEJvdW5kIGVhY2ggZ2VudWluZSBzdGFnZSBhZHZhbmNlLCB3aGlsZSByZXRyaWVzIGFuZCByZXN0YXJ0cyByZXRhaW4gdGhlaXJcclxuICAgIC8vIHJlbWFpbmluZyBkZWFkbGluZS4gVGhlIGluZGVwZW5kZW50IDIwLW1pbnV0ZSB0ZXN0IHRpbWVvdXQgaXMgdW5jaGFuZ2VkLlxyXG4gICAgbGV0IGF0dGVtcHQgPSAwO1xyXG4gICAgd2hpbGUgKCFhd2FpdCBpc0NoZWNrcG9pbnQoKSkge1xyXG4gICAgICBjb25zdCByZW1haW5pbmcgPSB3YXRjaGRvZy5yZW1haW5pbmcocGVyZm9ybWFuY2Uubm93KCkpO1xyXG4gICAgICBhd2FpdCBwYWdlLndhaXRGb3JUaW1lb3V0KE1hdGgubWluKFs1MDAsIDEwMDAsIDIwMDBdW01hdGgubWluKGF0dGVtcHQrKywgMildLCByZW1haW5pbmcpKTtcclxuICAgIH1cclxuICAgIHJ1bklkID8/PSB3b3JrZmxvdy5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkO1xyXG4gICAgZXhwZWN0KHdvcmtmbG93LmNvbnRleHQuYWdlbnRfZXhlY3V0aW9uPy5ydW5faWQpLnRvQmUocnVuSWQpO1xyXG4gICAgaWYgKHN0ZXBzLmV2ZXJ5KHN0ZXAgPT4gZG9uZS5oYXMod29ya2Zsb3cuc3RhdHVzZXNbc3RlcF0pKSkge1xyXG4gICAgICBpZiAoY3Jhc2hTaW11bGF0aW9uKSBleHBlY3QocmVzdGFydGVkSm9iSWQsICdBIHJlYWwgcnVubmluZyBzaW11bGF0aW9uIG11c3QgYmUgb2JzZXJ2ZWQgYW5kIGludGVycnVwdGVkLicpLnRvQmVUcnV0aHkoKTtcclxuICAgICAgcmV0dXJuIHsgcnVuSWQsIHJldmlld2VkOiBbLi4ucmV2aWV3ZWRdLCByZXN0YXJ0ZWRKb2JJZCB9O1xyXG4gICAgfVxyXG4gICAgY29uc3QgZXhlY3V0aW9uID0gd29ya2Zsb3cuY29udGV4dC5hZ2VudF9leGVjdXRpb247XHJcbiAgICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pO1xyXG4gICAgaWYgKFsnQkxPQ0tFRCcsICdGQUlMRUQnLCAnSU5DT01QTEVURSddLmluY2x1ZGVzKGV4ZWN1dGlvbj8uc3RhdGUpICYmIGV4ZWN1dGlvbi5yZWNvdmVyYWJsZSAhPT0gdHJ1ZSkge1xyXG4gICAgICBjb25zdCBjb252ZXJzYXRpb24gPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jb252ZXJzYXRpb24nKTtcclxuICAgICAgY29uc3QgaWQgPSBjb252ZXJzYXRpb24uZGF0YT8uYWN0aXZlX3Byb3Bvc2FsO1xyXG4gICAgICBjb25zdCBwcm9wb3NhbCA9IGlkID8gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7aWR9YCkgOiBudWxsO1xyXG4gICAgICBhd2FpdCB0ZXN0LmluZm8oKS5hdHRhY2goJ3dpemFyZC1ibG9ja2VyJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IGV4ZWN1dGlvbixcclxuICAgICAgICBwcm9wb3NhbDogcHJvcG9zYWw/LmRhdGE/LnZhbGlkYXRpb25fcmVzdWx0LCB2aXNpYmxlOiBhd2FpdCBkaWFsb2cuaW5uZXJUZXh0KCkgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbiAgICAgIHRocm93IG5ldyBFcnJvcihgV2l6YXJkICR7ZXhlY3V0aW9uLnN0YXRlfSBhdCAke2V4ZWN1dGlvbi5zdGVwfTogJHtleGVjdXRpb24ubWVzc2FnZX1gKTtcclxuICAgIH1cclxuICAgIGlmIChleGVjdXRpb24/LnN0YXRlID09PSAnUkVBRFlfVE9fQ09OVElOVUUnIHx8IChleGVjdXRpb24/LnN0YXRlID09PSAnQkxPQ0tFRCcgJiYgZXhlY3V0aW9uLnJlY292ZXJhYmxlID09PSB0cnVlKSkge1xyXG4gICAgICBjb25zdCBidXR0b24gPSBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBdWZ0cmFnIGZvcnRzZXR6ZW4nLCBleGFjdDogdHJ1ZSB9KTtcclxuICAgICAgdHJ5IHtcclxuICAgICAgICBhd2FpdCBidXR0b24uY2xpY2soeyB0aW1lb3V0OiAyMDAwIH0pO1xyXG4gICAgICB9IGNhdGNoIChlcnJvcikge1xyXG4gICAgICAgIGNvbnN0IGxhdGVzdCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICAgIGlmIChsYXRlc3QuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQgPT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0ICYmIGF3YWl0IGJ1dHRvbi5ldmFsdWF0ZUFsbChidXR0b25zID0+IGJ1dHRvbnMuc29tZShidXR0b24gPT4gIShidXR0b24gYXMgSFRNTEJ1dHRvbkVsZW1lbnQpLmRpc2FibGVkICYmIGJ1dHRvbi5nZXRDbGllbnRSZWN0cygpLmxlbmd0aCA+IDAgJiYgZ2V0Q29tcHV0ZWRTdHlsZShidXR0b24pLnZpc2liaWxpdHkgIT09IFwiaGlkZGVuXCIpKSkgdGhyb3cgZXJyb3I7XHJcbiAgICAgICAgY29udGludWU7XHJcbiAgICAgIH1cclxuICAgICAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpKS5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8udXBkYXRlZF9hdCxcclxuICAgICAgICB7IHRpbWVvdXQ6IDYwXzAwMCB9KS5ub3QudG9CZShleGVjdXRpb24udXBkYXRlZF9hdCk7XHJcbiAgICAgIGNvbnRpbnVlO1xyXG4gICAgfVxyXG4gICAgY29uc3QgY2FuZGlkYXRlID0gYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgYC9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvcG9zYWxzLyR7cHJvcG9zYWxJZH1gKTtcclxuICAgIGlmIChjYW5kaWRhdGUuZGF0YS5wcm9wb3NhbF90eXBlID09PSAnV0laQVJEX0VOR0lORUVSSU5HX01PREVMJyAmJiByZXZpZXdDb3VudCA9PT0gMCAmJiBleHBlY3RlZEhhcmR3YXJlLmxlbmd0aCkge1xyXG4gICAgICBjb25zdCBoYXJkd2FyZSA9IGNhbmRpZGF0ZS5kYXRhLmNoYW5nZXNcclxuICAgICAgICAuZmlsdGVyKChjaGFuZ2U6IHsgb2JqZWN0X3R5cGU6IHN0cmluZyB9KSA9PiBjaGFuZ2Uub2JqZWN0X3R5cGUgPT09ICdIYXJkd2FyZU5vZGUnKVxyXG4gICAgICAgIC5tYXAoKGNoYW5nZTogeyBkYXRhOiB7IG5hbWU6IHN0cmluZyB9IH0pID0+IGNoYW5nZS5kYXRhLm5hbWUpO1xyXG4gICAgICBleHBlY3QoaGFyZHdhcmUsICdUaGUgVUkgbXVzdCBwcmVzZXJ2ZSB0aGUgaGFyZHdhcmUgZXhwbGljaXRseSBuYW1lZCBpbiB0aGUgdXNlciByZXF1ZXN0LicpXHJcbiAgICAgICAgLnRvRXF1YWwoZXhwZWN0LmFycmF5Q29udGFpbmluZyhleHBlY3RlZEhhcmR3YXJlKSk7XHJcbiAgICB9XHJcbiAgICBleHBlY3QocmV2aWV3ZWQuaGFzKHByb3Bvc2FsSWQpLCAnVGhlIHNhbWUgcHJvcG9zYWwgbXVzdCBub3QgcmVxdWVzdCByZXZpZXcgdHdpY2UuJykudG9CZShmYWxzZSk7XHJcbiAgICBjb25zdCBhcHBseVJlc3BvbnNlID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4gcmVzcG9uc2UudXJsKCkuaW5jbHVkZXMoYC9wcm9wb3NhbHMvJHtwcm9wb3NhbElkfS9hcHByb3ZlLWFwcGx5YCkgJiYgcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUE9TVCcsIHsgdGltZW91dDogMTgwXzAwMCB9KTtcclxuICAgIGNvbnN0IGFwcHJvdmFsID0gZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAvXihGcmVpZ2ViZW4sIMO8YmVybmVobWVuICYgZm9ydGZhaHJlbnzDnGJlcm5laG1lbiAmIGZvcnRmYWhyZW4pJC8gfSk7XHJcbiAgICBhd2FpdCBleHBlY3QoYXBwcm92YWwpLnRvQmVFbmFibGVkKHsgdGltZW91dDogNjBfMDAwIH0pO1xyXG4gICAgYXdhaXQgYXBwcm92YWwuY2xpY2soKTtcclxuICAgIGNvbnN0IGFwcGxpZWQgPSBhd2FpdCBhcHBseVJlc3BvbnNlO1xyXG4gICAgaWYgKCFhcHBsaWVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke2FwcGxpZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBhcHBsaWVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgICBleHBlY3QoKGF3YWl0IGFwcGxpZWQuanNvbigpKS5kYXRhLnN0YXR1cykudG9CZSgnQVBQTElFRCcpO1xyXG4gICAgcmV2aWV3ZWQuYWRkKHByb3Bvc2FsSWQpOyByZXZpZXdDb3VudCsrO1xyXG4gICAgLy8gQSBkaXN0aW5jdCwgYWN0dWFsbHkgY29tbWl0dGVkIG1hbnVhbCByZXZpZXcgc3RhcnRzIHRoZSBuZXh0IGF1dG9tYXRpY1xyXG4gICAgLy8gc2VjdGlvbi4gSXRzIHdyaXRlIHN0aWxsIGhhcyB0aGUgc2VwYXJhdGUgdW5jaGFuZ2VkIDE4MC1zZWNvbmQgbGltaXQuXHJcbiAgICB3YXRjaGRvZyA9IG5ldyBXaXphcmRQcm9ncmVzc1dhdGNoZG9nKHBlcmZvcm1hbmNlLm5vdygpLCB3b3JrZmxvdyk7XHJcbiAgICBpZiAoY2FuZGlkYXRlLmRhdGEucHJvcG9zYWxfdHlwZSA9PT0gJ1dJWkFSRF9FTkdJTkVFUklOR19NT0RFTCcgJiYgZXhwZWN0ZWRTaWduYWxzKSB7XHJcbiAgICAgIGF3YWl0IHZlcmlmeVNpZ25hbENvbnRyYWN0cyhwYWdlLCBwcm9qZWN0LCBleHBlY3RlZFNpZ25hbHMpO1xyXG4gICAgfVxyXG4gICAgaWYgKHJldmlld0NvdW50ID09PSAxICYmIGFmdGVyRmlyc3RNb2RlbEFwcGxpZWQpIHtcclxuICAgICAgYXdhaXQgYWZ0ZXJGaXJzdE1vZGVsQXBwbGllZCgpO1xyXG4gICAgICAvLyBUaGlzIG9uZSB0ZXN0IGV4cGxpY2l0bHkgc3VibWl0cyBBTUVORCBhbmQgd2FpdHMgZm9yIGl0cyByZWNlaXB0LiBPbmx5XHJcbiAgICAgIC8vIHRoYXQgZGVsaWJlcmF0ZSBhY3Rpb24gcGVybWl0cyBiaW5kaW5nIGl0cyBuZXcgcmVxdWVzdCByZXZpc2lvbi5cclxuICAgICAgY29uc3QgYW1lbmRlZCA9IGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3ZpZXc9c3VtbWFyeScpO1xyXG4gICAgICBleHBlY3QoYW1lbmRlZC5jb250ZXh0LmFnZW50X2V4ZWN1dGlvbj8ucnVuX2lkKS50b0JlKHJ1bklkKTtcclxuICAgICAgd2F0Y2hkb2cgPSBuZXcgV2l6YXJkUHJvZ3Jlc3NXYXRjaGRvZyhwZXJmb3JtYW5jZS5ub3coKSwgYW1lbmRlZCk7XHJcbiAgICB9XHJcbiAgICBpZiAocmV2aWV3Q291bnQgPT09IDEpIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7IC8vIER1cmFibGUgcmVsb2FkIGFmdGVyIGEgcmVhbCBjb21taXQuXHJcbiAgICBpZiAocmVzdGFydCAmJiByZXZpZXdDb3VudCA9PT0gMikge1xyXG4gICAgICBhd2FpdCByZXN0YXJ0QXBwbGljYXRpb24ocGFnZSk7XHJcbiAgICAgIGF3YWl0IG9wZW5XaXphcmQocGFnZSwgcHJvamVjdCk7XHJcbiAgICB9XHJcbiAgICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XHJcbiAgICAgIGNvbnN0IGN1cnJlbnQgPSBhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdz92aWV3PXN1bW1hcnknKTtcclxuICAgICAgcmV0dXJuIGN1cnJlbnQuY29udGV4dC5hZ2VudF9leGVjdXRpb24/LnVwZGF0ZWRfYXQgIT09IGV4ZWN1dGlvbi51cGRhdGVkX2F0O1xyXG4gICAgfSwgeyB0aW1lb3V0OiA2MF8wMDAgfSkudG9CZSh0cnVlKTtcclxuICB9XHJcbiAgdGhyb3cgbmV3IEVycm9yKCdXaXphcmQgZXhjZWVkZWQgMTYgcmV2aWV3L2NvbnRpbnVhdGlvbiBjaGVja3BvaW50cy4nKTtcclxufVxyXG5cclxudGVzdCgnbmV3IHNtYWxsIHdpemFyZCB0cmF2ZXJzZXMgYWxsIG5pbmUgc3RhZ2VzIGFuZCBzdXJ2aXZlcyByZWxvYWQvcmVzdGFydCBAc21hbGwnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XHJcbiAgY29uc3QgZXJyb3JzOiBzdHJpbmdbXSA9IFtdOyBwYWdlLm9uKCdwYWdlZXJyb3InLCBlcnJvciA9PiBlcnJvcnMucHVzaChlcnJvci5tZXNzYWdlKSk7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXNtYWxsLScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdFMkUgc21hbGwnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnQXVmZ2FiZScsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnQXVmZ2FiZW50ZXh0JywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKCdFcnpldWdlIGVpbiBBdXRvbW90aXZlIENBTi1GRCBOZXR6d2VyayBtaXQgZWluZW0gR2F0ZXdheSBTeXN0ZW0sIGRlbiBFQ1VzIE1vdG9yc3RldWVydW5nIHVuZCBBbnplaWdlLCBlaW5lbSBTZW5zb3IgTW90b3JUZW1wZXJhdHVyZSB1bmQgZWluZW0gQWt0b3IgTW90b3JWYWx2ZS4gTW90b3JUZW1wZXJhdHVyZSB3aXJkIHZvbiBNb3RvcnN0ZXVlcnVuZyBhdXNnZXdlcnRldC4gTW90b3JzdGV1ZXJ1bmcgc3RldWVydCBNb3RvclZhbHZlLiBTdGF0dXN3ZXJ0ZSB3ZXJkZW4gYW4gQW56ZWlnZSB1bmQgU3lzdGVtIMO8YmVybWl0dGVsdC4gUHLDvGZlIHVuZCBhcmJlaXRlIGJpcyBEYXRhIFNjaWVuY2UgJiBJbnRlbGxpZ2VuY2UuJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1dlaXRlcmUgSGlud2Vpc2UnLCB7IGV4YWN0OiB0cnVlIH0pLmZpbGwoJy0gQWt0b3ItQmVmZWhsZToge1wiTW90b3JWYWx2ZVwiOntcImxlbmd0aF9iaXRzXCI6MSxcImRhdGFfdHlwZVwiOlwiYm9vbGVhblwiLFwiZmFjdG9yXCI6MSxcInVuaXRcIjpcImNvZGVcIixcIm1pbl92YWx1ZVwiOjAsXCJtYXhfdmFsdWVcIjoxLFwic2VtYW50aWNcIjp7XCJzZW1hbnRpY190eXBlXCI6XCJCT09MRUFOXCJ9LFwiZGF0YVwiOntcImVudW1fdmFsdWVzXCI6e1wiQ0xPU0VcIjowLFwiT1BFTlwiOjF9fX19Jyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ0dlcsOkdGV1bWZhbmcnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgZm9yIChjb25zdCBbbGFiZWwsIHZhbHVlXSBvZiBbWydHYXRld2F5cycsICcxJ10sIFsnQ29udHJvbGxlcicsICcyJ10sIFsnU2Vuc29yZW4nLCAnMSddLCBbJ0FrdG9yZW4nLCAnMSddXSkgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoYCR7bGFiZWx9OiB2ZXJiaW5kbGljaGUgQW56YWhsYCwgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHZhbHVlKTtcclxuICBjb25zdCBzdGFydFJlcXVlc3QgPSBwYWdlLndhaXRGb3JSZXF1ZXN0KHJlcXVlc3QgPT4gcmVxdWVzdC51cmwoKS5lbmRzV2l0aCgnL2FwaS9hZ2VudC9jaGF0JylcclxuICAgICYmIHJlcXVlc3QubWV0aG9kKCkgPT09ICdQT1NUJyAmJiByZXF1ZXN0LnBvc3REYXRhSlNPTigpPy53aXphcmRfY29tbWFuZD8uYWN0aW9uID09PSAnU1RBUlQnKTtcclxuICAvLyBVc2UgdGhlIHNhbWUgdmlzaWJsZSBxdWVzdGlvbm5haXJlIG5hdmlnYXRpb24gYSB1c2VyIHVzZXM7IG5ldmVyIGluamVjdCBnZW5lcmF0ZWQgbW9kZWwgcm93cy5cclxuICBmb3IgKGxldCBzdGVwID0gMDsgc3RlcCA8IDEwOyBzdGVwKyspIHtcclxuICAgIGNvbnN0IHN1Ym1pdCA9IGRpYWxvZy5sb2NhdG9yKCcuZW5nLWFnZW50LXF1ZXN0aW9ubmFpcmUtaGVhZCcpLmdldEJ5Um9sZSgnYnV0dG9uJyk7XHJcbiAgICBhd2FpdCBleHBlY3Qoc3VibWl0KS50b0JlRW5hYmxlZCgpO1xyXG4gICAgY29uc3QgbmFtZSA9IGF3YWl0IHN1Ym1pdC5pbm5lclRleHQoKTtcclxuICAgIGF3YWl0IHN1Ym1pdC5jbGljaygpO1xyXG4gICAgaWYgKG5hbWUgPT09ICfDnGJlcm5laG1lbicpIGJyZWFrO1xyXG4gICAgaWYgKHN0ZXAgPT09IDkpIHRocm93IG5ldyBFcnJvcignUXVlc3Rpb25uYWlyZSBkaWQgbm90IG9mZmVyIHN1Ym1pdC4nKTtcclxuICB9XHJcbiAgY29uc3QgcmVxdWVzdGVkID0gKGF3YWl0IHN0YXJ0UmVxdWVzdCkucG9zdERhdGFKU09OKCkud2l6YXJkX2NvbW1hbmQud2l6YXJkX2NvbnRleHQ7XHJcbiAgZXhwZWN0KHJlcXVlc3RlZC50ZWNobm9sb2dpZXMsICdBbiBleHBsaWNpdCBDQU4tRkQgdGFzayBtdXN0IG5vdCBzaWxlbnRseSByZXF1ZXN0IExJTiBhbmQgU09NRS9JUC4nKS50b0VxdWFsKFsnQ0FOLUZEIChjYW5fZmQpJ10pO1xyXG4gIGNvbnN0IGNvbnRpbnVpdHkgPSBhd2FpdCBjb21wbGV0ZVRocm91Z2hXaXphcmQocGFnZSwgcHJvamVjdCwgdHJ1ZSxcclxuICAgIFsnU3lzdGVtJywgJ01vdG9yc3RldWVydW5nJywgJ0FuemVpZ2UnLCAnTW90b3JUZW1wZXJhdHVyZScsICdNb3RvclZhbHZlJ10pO1xyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCA1KTtcclxuICBjb25zdCBmaW5pc2hlZCA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlID0+IHJlc3BvbnNlLnVybCgpLmluY2x1ZGVzKGAvcnVucy8ke2NvbnRpbnVpdHkucnVuSWR9L2ZpbmlzaGApXHJcbiAgICAmJiByZXNwb25zZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQT1NUJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRmVydGlnIHN0ZWxsZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGV4cGVjdCgoYXdhaXQgZmluaXNoZWQpLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZykubm90LnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBleHBlY3QoKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL3NpbXVsYXRpb25zJykpLmpvYnMpLnRvSGF2ZUxlbmd0aCgxKTtcclxuICBleHBlY3QoZXJyb3JzKS50b0VxdWFsKFtdKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2V2aWRlbmNlJywgeyBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHByb2plY3QsIC4uLmNvbnRpbnVpdHksIC4uLmFydGlmYWN0cyB9KSwgY29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyB9KTtcclxufSk7XHJcblxyXG5mb3IgKGNvbnN0IHRlY2hub2xvZ3kgb2YgWydJMkMnLCAnTW9kYnVzIFJUVSddKSB7XG4gIHRlc3QoYFJhc3BiZXJyeSBQaSB0ZW1wZXJhdHVyZSBhbmQgdmFsdmUgcHJvamVjdCBjb21wbGV0ZXMgYWxsIG5pbmUgc3RhZ2VzIHVzaW5nICR7dGVjaG5vbG9neX0gQG5vbmF1dG9tb3RpdmVgLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XG4gICAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWVtYmVkZGVkLScgKyByYW5kb21VVUlEKCk7XG4gICAgY29uc3QgZGlhbG9nID0gYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnUHJvamVrdG5hbWUnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gICAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNlbmdpbmVlcmluZy1wcm9qZWN0LW5hbWUnKS5maWxsKCdUZW1wZXJhdHVycmVnZWx1bmcnKTtcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlUaXRsZSgnQXVmZ2FiZScsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnQXVmZ2FiZW50ZXh0JywgeyBleGFjdDogdHJ1ZSB9KS5maWxsKHRlY2hub2xvZ3kgPT09ICdJMkMnXG4gICAgICA/ICcyIEFrdG9yZW4gZsO8ciBWZW50aWxlLCA0IFNlbnNvcmVuIGbDvHIgVGVtcGVyYXR1cmVuLCB1bmQgZWluIFJhc3BiZXJyeVBpJ1xuICAgICAgOiBgMiBBa3RvcmVuIGbDvHIgVmVudGlsZSwgNCBTZW5zb3JlbiBmw7xyIFRlbXBlcmF0dXJlbiwgdW5kIGVpbiBSYXNwYmVycnlQaS4gRW1iZWRkZWQgU3lzdGVtcy4gQWxsZSBHZXLDpHRlIGtvbW11bml6aWVyZW4gw7xiZXIgJHt0ZWNobm9sb2d5fS4gUHLDvGZlIHVuZCBhcmJlaXRlIGJpcyBEYXRhIFNjaWVuY2UgJiBJbnRlbGxpZ2VuY2UuYCk7XG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ05ldHphcmNoaXRla3R1cicsIHsgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdyYWRpbycsIHsgbmFtZTogL1ZhcmlhbnRlIDAvIH0pLmNoZWNrKCk7XG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5VGl0bGUoJ0dlcsOkdGV1bWZhbmcnLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gICAgaWYgKHRlY2hub2xvZ3kgPT09ICdJMkMnKSB7XG4gICAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XG4gICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbCgnUmFzcGJlcnJ5UGk6IEFuc2NobHVzcycsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdJMkMnKTtcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlMYWJlbCgnVGVtcGVyYXR1cnNlbnNvcjE6IEFuc2NobHVzcycsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZVZhbHVlKCcnKTtcbiAgICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICfDnGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcbiAgICAgIGZvciAoY29uc3QgbmFtZSBvZiBbJ1Jhc3BiZXJyeVBpJywgJ1RlbXBlcmF0dXJzZW5zb3IxJywgJ1RlbXBlcmF0dXJzZW5zb3IyJywgJ1RlbXBlcmF0dXJzZW5zb3IzJywgJ1RlbXBlcmF0dXJzZW5zb3I0JywgJ1ZlbnRpbGFrdG9yMScsICdWZW50aWxha3RvcjInXSkge1xuICAgICAgICBhd2FpdCBkaWFsb2cuZ2V0QnlMYWJlbChgJHtuYW1lfTogQW5zY2hsdXNzYCwgeyBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ0kyQycpO1xuICAgICAgfVxuICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1NlbnNvciAxOiBNZXNzZ3LDtsOfZScsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdzcGVlZCcpO1xuICAgICAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeUxhYmVsKCdUZW1wZXJhdHVyc2Vuc29yMTogQW5zY2hsdXNzJywgeyBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoJ0kyQycpO1xuICAgICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1NlbnNvciAxOiBNZXNzZ3LDtsOfZScsIHsgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCd0ZW1wZXJhdHVyZScpO1xuICAgIH1cbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMTogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignT1BFTl9DTE9TRScpO1xuICAgIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlMYWJlbCgnVmVudGlsYWt0b3IyOiBTdGVsbGJlZmVobCcsIHsgZXhhY3Q6IHRydWUgfSkpLnRvSGF2ZVZhbHVlKCcnKTtcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnw5xiZXJuZWhtZW4nLCBleGFjdDogdHJ1ZSB9KSkudG9CZURpc2FibGVkKCk7XG4gICAgYXdhaXQgZGlhbG9nLmdldEJ5TGFiZWwoJ1ZlbnRpbGFrdG9yMjogU3RlbGxiZWZlaGwnLCB7IGV4YWN0OiB0cnVlIH0pLnNlbGVjdE9wdGlvbignT1BFTl9DTE9TRScpO1xuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ8OcYmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgICBjb25zdCBjb250aW51aXR5ID0gYXdhaXQgY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIHRydWUsIFsnUmFzcGJlcnJ5UGknLCAnVGVtcGVyYXR1cnNlbnNvcjEnLCAnVGVtcGVyYXR1cnNlbnNvcjInLCAnVGVtcGVyYXR1cnNlbnNvcjMnLCAnVGVtcGVyYXR1cnNlbnNvcjQnLCAnVmVudGlsYWt0b3IxJywgJ1ZlbnRpbGFrdG9yMiddKTtcbiAgICBjb25zdCBhcnRpZmFjdHMgPSBhd2FpdCB2ZXJpZnlBcnRpZmFjdHMocGFnZSwgcHJvamVjdCwgNywgJ1Jhc3BiZXJyeVBpJyk7XG4gICAgY29uc3QgaW50ZXJmYWNlcyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLWludGVyZmFjZXMnKTtcbiAgICBleHBlY3QoaW50ZXJmYWNlcy5sZW5ndGgpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoNyk7XG4gICAgZXhwZWN0KGludGVyZmFjZXMuZXZlcnkoaXRlbSA9PiAhL2F1dG9tb3RpdmV8Y2FufGxpbi9pLnRlc3QoaXRlbS50ZWNobm9sb2d5KSkpLnRvQmUodHJ1ZSk7XG4gICAgY29uc3QgaGFyZHdhcmUgPSBhd2FpdCBhbGxPYmplY3RzKHBhZ2UsIHByb2plY3QsICdoYXJkd2FyZS1ub2RlcycpO1xuICAgIGV4cGVjdChoYXJkd2FyZS5ldmVyeShpdGVtID0+IGl0ZW0uZG9tYWluICE9PSAnYXV0b21vdGl2ZScpKS50b0JlKHRydWUpO1xuICAgIGlmICh0ZWNobm9sb2d5ID09PSAnSTJDJykge1xuICAgICAgY29uc3Qgc2lnbmFscyA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ3NpZ25hbHMnKTtcbiAgICAgIGV4cGVjdChzaWduYWxzLnNvbWUoaXRlbSA9PiBpdGVtLm5hbWUgPT09ICdUZW1wZXJhdHVyX1RlbXBlcmF0dXJzZW5zb3IxJyAmJiBpdGVtLnVuaXQgPT09ICdkZWdDJykpLnRvQmUodHJ1ZSk7XG4gICAgfVxuICAgIGNvbnN0IGZpbmlzaGVkID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2UgPT4gcmVzcG9uc2UudXJsKCkuaW5jbHVkZXMoYC9ydW5zLyR7Y29udGludWl0eS5ydW5JZH0vZmluaXNoYClcbiAgICAgICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnKTtcbiAgICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdGZXJ0aWcgc3RlbGxlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gICAgZXhwZWN0KChhd2FpdCBmaW5pc2hlZCkub2soKSkudG9CZSh0cnVlKTtcbiAgICBhd2FpdCBleHBlY3QoZGlhbG9nKS5ub3QudG9CZVZpc2libGUoKTtcbiAgICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xuICAgIGV4cGVjdCgoYXdhaXQgcmVhZFByb2plY3QocGFnZSwgcHJvamVjdCwgJy9hcGkvc2ltdWxhdGlvbnMnKSkuam9icykudG9IYXZlTGVuZ3RoKDEpO1xuICAgIGF3YWl0IHRlc3RJbmZvLmF0dGFjaCgnbm9uYXV0b21vdGl2ZS1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCB0ZWNobm9sb2d5LCAuLi5jb250aW51aXR5LCAuLi5hcnRpZmFjdHMgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XG4gIH0pO1xufVxuXG50ZXN0KCdleGFjdCBjb25maXJtZWQgNTAvMjUwLzI1MCByZXF1ZXN0IGNvbXBsZXRlcyB0aHJvdWdoIHJlYWwgd2l6YXJkIHJldmlldyBAbGFyZ2UnLCBhc3luYyAoeyBwYWdlIH0sIHRlc3RJbmZvKSA9PiB7XG4gIGNvbnN0IGVycm9yczogc3RyaW5nW10gPSBbXTsgcGFnZS5vbigncGFnZWVycm9yJywgZXJyb3IgPT4gZXJyb3JzLnB1c2goZXJyb3IubWVzc2FnZSkpO1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1sYXJnZS0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IHJ1bklkID0gcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IG9yaWdpbmFsID0gYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2UtNTAtMjUwLTI1MC50eHQnLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpO1xyXG4gIGNvbnN0IG1ldGFkYXRhID0gSlNPTi5wYXJzZShhd2FpdCByZWFkRmlsZShuZXcgVVJMKCcuL2ZpeHR1cmVzL3dpemFyZC1sYXJnZS01MC0yNTAtMjUwLmpzb24nLCBpbXBvcnQubWV0YS51cmwpLCAndXRmOCcpKTtcclxuICBjb25zdCBiYXNlbGluZSA9IEpTT04ucGFyc2UoYXdhaXQgcmVhZEZpbGUobmV3IFVSTCgnLi9maXh0dXJlcy93aXphcmQtbGFyZ2Utc2lnbmFsLWNvbnRyYWN0cy5qc29uJywgaW1wb3J0Lm1ldGEudXJsKSwgJ3V0ZjgnKSk7XHJcbiAgY29uc3QgcHJvbXB0ID0gb3JpZ2luYWwucmVwbGFjZSgvXi0gTGF1Zi1JRDouKiQvbSwgJy0gTGF1Zi1JRDogJyArIHJ1bklkKTtcclxuICAvLyBSZXBsYXkgdGhlIGNhcHR1cmVkLCBhbHJlYWR5IGNvbmZpcm1lZCBpbnB1dCB0aHJvdWdoIHRoZSBub3JtYWwgU1RBUlQgQVBJLlxyXG4gIC8vIEFsbCBwcm9wb3NhbCBpbnNwZWN0aW9uLCBhcHByb3ZhbCwgY29udGludWF0aW9uIGFuZCByZWxvYWRzIGJlbG93IHVzZSBVSS5cclxuICBjb25zdCBzdGFydGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY2hhdCcsIHtcclxuICAgIGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSwgdGltZW91dDogMjQwXzAwMCxcclxuICAgIGRhdGE6IHsgcHJvbXB0LCB3aXphcmRfY29tbWFuZDogeyBhY3Rpb246ICdTVEFSVCcsIHJ1bl9pZDogcnVuSWQsIG9wZXJhdGlvbl9pZDogcmFuZG9tVVVJRCgpLFxyXG4gICAgICB0YXJnZXQ6ICdkYXRhX3NjaWVuY2VfaW50ZWxsaWdlbmNlJywgd2l6YXJkX2NvbnRleHQ6IHsgLi4ubWV0YWRhdGEud2l6YXJkX2NvbnRleHQsIHByb2plY3RfaWQ6IHByb2plY3QsIHJ1bl9pZDogcnVuSWQgfSB9IH0sXHJcbiAgfSk7XHJcbiAgaWYgKCFzdGFydGVkLm9rKCkpIHRocm93IG5ldyBFcnJvcihgSFRUUCAke3N0YXJ0ZWQuc3RhdHVzKCl9OiAkeyhhd2FpdCBzdGFydGVkLnRleHQoKSkuc2xpY2UoMCwgNDAwMCl9YCk7XHJcbiAgYXdhaXQgb3BlbldpemFyZChwYWdlLCBwcm9qZWN0KTtcclxuICBjb25zdCBjb250aW51aXR5ID0gYXdhaXQgY29tcGxldGVUaHJvdWdoV2l6YXJkKHBhZ2UsIHByb2plY3QsIGZhbHNlLCBbXSwgdHJ1ZSwgYmFzZWxpbmUuc2lnbmFscyk7XHJcbiAgZXhwZWN0KGNvbnRpbnVpdHkucnVuSWQpLnRvQmUocnVuSWQpO1xyXG4gIGNvbnN0IGhhcmR3YXJlID0gYXdhaXQgYWxsT2JqZWN0cyhwYWdlLCBwcm9qZWN0LCAnaGFyZHdhcmUtbm9kZXMnKTtcclxuICBleHBlY3QoaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5kZXZpY2VfdHlwZSA9PT0gJ1NlbnNvckNvbnRyb2xsZXInKSkudG9IYXZlTGVuZ3RoKDI1MCk7XHJcbiAgZXhwZWN0KGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0uZGV2aWNlX3R5cGUgPT09ICdBY3R1YXRvckNvbnRyb2xsZXInKSkudG9IYXZlTGVuZ3RoKDI1MCk7XHJcbiAgZXhwZWN0KGhhcmR3YXJlLmZpbHRlcihpdGVtID0+IGl0ZW0uZGV2aWNlX3R5cGUgPT09ICdFQ1UnKS5sZW5ndGgpLnRvQmVHcmVhdGVyVGhhbk9yRXF1YWwoNTApO1xyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCAxNDA0KTtcclxuICBhd2FpdCB2ZXJpZnlTaWduYWxDb250cmFjdHMocGFnZSwgcHJvamVjdCwgYmFzZWxpbmUuc2lnbmFscyk7XHJcbiAgZXhwZWN0KGFydGlmYWN0cy5qb2IpLnRvQmUoY29udGludWl0eS5yZXN0YXJ0ZWRKb2JJZCk7XHJcbiAgZXhwZWN0KGVycm9ycykudG9FcXVhbChbXSk7XHJcbiAgYXdhaXQgdGVzdEluZm8uYXR0YWNoKCdldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCBmaXh0dXJlOiBtZXRhZGF0YS5yZXF1ZXN0X3NoYTI1NiwgLi4uY29udGludWl0eSwgLi4uYXJ0aWZhY3RzIH0pLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nIH0pO1xyXG59KTtcclxuXHJcbnRlc3QoJ2EgcmVhbCBBTUVORCBhZnRlciBtb2RlbCBhcHByb3ZhbCBhZGRzIHRoZSByZXF1ZXN0ZWQgc2Vuc29yIGFuZCByZXVzZXMgaXRzIG5ldHdvcmtzIEBhbWVuZCcsIGFzeW5jICh7IHBhZ2UgfSwgdGVzdEluZm8pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtYW1lbmQtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBydW5JZCA9IHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBncmFwaCA9IFtcclxuICAgIHsgY2x1c3Rlcl9pZDogJ2RyaXZlJywgbmV0d29ya19pZDogJ2Nhbl9mZCcsIG5ldHdvcmtfbGFiZWw6ICdDQU4tRkQnLCBidXNfbmFtZTogJ0RyaXZlJyxcclxuICAgICAgY29udHJvbGxlcnM6IFt7IGVjdTogJ01vdG9yc3RldWVydW5nJywgc2Vuc29yczogW10gYXMgc3RyaW5nW10sIGFjdHVhdG9yczogW10gfV0sXHJcbiAgICAgIGhtaV9yb3V0ZXM6IFt7IHNvdXJjZTogJ01vdG9yc3RldWVydW5nJywgdGFyZ2V0OiAnQW56ZWlnZScgfSwgeyBzb3VyY2U6ICdBbnplaWdlJywgdGFyZ2V0OiAnTW90b3JzdGV1ZXJ1bmcnIH0sXHJcbiAgICAgICAgeyBzb3VyY2U6ICdTeXN0ZW0nLCB0YXJnZXQ6ICdBbnplaWdlJyB9XSB9LFxyXG4gICAgeyBjbHVzdGVyX2lkOiAnZGlzcGxheScsIG5ldHdvcmtfaWQ6ICdldGhlcm5ldCcsIG5ldHdvcmtfbGFiZWw6ICdFdGhlcm5ldCcsIGJ1c19uYW1lOiAnRGlzcGxheScsXHJcbiAgICAgIGNvbnRyb2xsZXJzOiBbeyBlY3U6ICdBbnplaWdlJywgc2Vuc29yczogW10gYXMgc3RyaW5nW10sIGFjdHVhdG9yczogW10gfV0gfSxcclxuICBdO1xyXG4gIGNvbnN0IHByb21wdCA9IGBTdHJ1a3R1cmllcnRlIFZvcmdhYmVuIGZ1ZXIgZGVuIEVuZ2luZWVyaW5nLUFnZW50ZW46XHJcbi0gTGF1Zi1JRDogJHtydW5JZH1cclxuLSBJbmR1c3RyaWU6IEF1dG9tb3RpdmVcclxuLSBOZXR6d2Vya3RlY2hub2xvZ2llbjogQ0FOLUZEIChjYW5fZmQpOyBFdGhlcm5ldCAoZXRoZXJuZXQpXHJcbi0gSGFyZHdhcmUtU29sbHdlcnRlOiB7XCJnYXRld2F5c1wiOjEsXCJlY3VzXCI6MixcInNlbnNvcnNcIjowLFwiYWN0dWF0b3JzXCI6MH1cclxuLSBTeXN0ZW1jbHVzdGVyLUdyYXBoOiAke0pTT04uc3RyaW5naWZ5KGdyYXBoKX1cclxuS29ua3JldGUgQXVmZ2FiZSBkZXMgTnV0emVycywgcGVyIFdpemFyZC1VZWJlcm5laG1lbiBiZXN0YWV0aWd0OlxyXG5Nb3RvcnN0ZXVlcnVuZyB1bmQgQW56ZWlnZSBtaXQgZWluZW0gemVudHJhbGVuIEdhdGV3YXkgU3lzdGVtIHZlcmJpbmRlbi5gO1xyXG4gIGNvbnN0IHN0YXJ0ZWQgPSBhd2FpdCBwYWdlLnJlcXVlc3QucG9zdCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9jaGF0Jywge1xyXG4gICAgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiAxMjBfMDAwLFxyXG4gICAgZGF0YTogeyBwcm9tcHQsIHdpemFyZF9jb21tYW5kOiB7IGFjdGlvbjogJ1NUQVJUJywgcnVuX2lkOiBydW5JZCwgb3BlcmF0aW9uX2lkOiByYW5kb21VVUlEKCksXHJcbiAgICAgIHRhcmdldDogJ2RhdGFfc2NpZW5jZV9pbnRlbGxpZ2VuY2UnLCB3aXphcmRfY29udGV4dDogeyBwcm9qZWN0X2lkOiBwcm9qZWN0LCBydW5faWQ6IHJ1bklkLFxyXG4gICAgICAgIHByb2plY3RfbmFtZTogJ0UyRSBhbWVuZG1lbnQnLCBzY29wZV9pZHM6IHN0ZXBzLCBtb2RlOiAnZnVsbCcsXHJcbiAgICAgICAgcHJvY2Vzc19pZHM6IFsnZGVmYXVsdHMnLCAncmV2aWV3X2dhdGUnLCAnYXBwcm92ZV9hZnRlcl9hbGxvdyddLCB0YXNrOiAnTW90b3JzdGV1ZXJ1bmcgdW5kIEFuemVpZ2UgYW4gU3lzdGVtJyB9IH0gfSxcclxuICB9KTtcclxuICBpZiAoIXN0YXJ0ZWQub2soKSkgdGhyb3cgbmV3IEVycm9yKGBIVFRQICR7c3RhcnRlZC5zdGF0dXMoKX06ICR7KGF3YWl0IHN0YXJ0ZWQudGV4dCgpKS5zbGljZSgwLCA0MDAwKX1gKTtcclxuICBhd2FpdCBvcGVuV2l6YXJkKHBhZ2UsIHByb2plY3QpO1xyXG4gIGxldCBvcmlnaW5hbE5ldHdvcmtzOiBzdHJpbmdbXSA9IFtdO1xyXG4gIGNvbnN0IGFtZW5kID0gYXN5bmMgKCkgPT4ge1xyXG4gICAgb3JpZ2luYWxOZXR3b3JrcyA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdycpKS5wYXJhbWV0ZXJzLm5ldHdvcmtzXHJcbiAgICAgIC5tYXAoKGl0ZW06IHsgaWQ6IHN0cmluZyB9KSA9PiBpdGVtLmlkKS5zb3J0KCk7XHJcbiAgICBleHBlY3Qob3JpZ2luYWxOZXR3b3JrcykudG9IYXZlTGVuZ3RoKDIpO1xyXG4gICAgZ3JhcGhbMF0uY29udHJvbGxlcnNbMF0uc2Vuc29ycy5wdXNoKCdNb3RvclRlbXBlcmF0dXJlJyk7XHJcbiAgICBjb25zdCBkaWFsb2cgPSBwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pO1xyXG4gICAgY29uc3QgZXhwYW5kID0gZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSk7XHJcbiAgICBhd2FpdCBleHBlY3QoZXhwYW5kKS50b0JlRW5hYmxlZCh7IHRpbWVvdXQ6IDEyMF8wMDAgfSk7XHJcbiAgICBhd2FpdCBleHBhbmQuY2xpY2soKTtcclxuICAgIGNvbnN0IGZpZWxkID0gZGlhbG9nLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcmfDpG56ZW4nLCBleGFjdDogdHJ1ZSB9KS5nZXRCeVJvbGUoJ3RleHRib3gnKTtcclxuICAgIGF3YWl0IGZpZWxkLmZpbGwoJ0VyZ8OkbnplIE1vdG9yVGVtcGVyYXR1cmUgYWxzIFNlbnNvciBkZXIgTW90b3JzdGV1ZXJ1bmcuIERpZSB2b2xsc3TDpG5kaWdlIGFrdHVhbGlzaWVydGUgRnJlaWdhYmUgbGF1dGV0OlxcbidcclxuICAgICAgKyAnLSBIYXJkd2FyZS1Tb2xsd2VydGU6IHtcImdhdGV3YXlzXCI6MSxcImVjdXNcIjoyLFwic2Vuc29yc1wiOjEsXCJhY3R1YXRvcnNcIjowfVxcbidcclxuICAgICAgKyAnLSBTeXN0ZW1jbHVzdGVyLUdyYXBoOiAnICsgSlNPTi5zdHJpbmdpZnkoZ3JhcGgpKTtcclxuICAgIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8Okbnp1bmcgYW5hbHlzaWVyZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZXhwZWN0KGZpZWxkKS5ub3QudG9CZVZpc2libGUoeyB0aW1lb3V0OiAxMjBfMDAwIH0pO1xyXG4gIH07XHJcbiAgY29uc3QgY29udGludWl0eSA9IGF3YWl0IGNvbXBsZXRlVGhyb3VnaFdpemFyZChwYWdlLCBwcm9qZWN0LCBmYWxzZSwgWydNb3RvcnN0ZXVlcnVuZycsICdBbnplaWdlJ10sIGZhbHNlLCB1bmRlZmluZWQsIGFtZW5kKTtcclxuICBjb25zdCBoYXJkd2FyZSA9IGF3YWl0IGFsbE9iamVjdHMocGFnZSwgcHJvamVjdCwgJ2hhcmR3YXJlLW5vZGVzJyk7XHJcbiAgY29uc3Qgb3duZXIgPSBoYXJkd2FyZS5maW5kKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnTW90b3JzdGV1ZXJ1bmcnKTtcclxuICBjb25zdCBzZW5zb3JzID0gaGFyZHdhcmUuZmlsdGVyKGl0ZW0gPT4gaXRlbS5uYW1lID09PSAnTW90b3JUZW1wZXJhdHVyZScpO1xyXG4gIGV4cGVjdChzZW5zb3JzKS50b0hhdmVMZW5ndGgoMSk7XHJcbiAgZXhwZWN0KHNlbnNvcnNbMF0uaWRlbnRpdHkuc3lzdGVtX293bmVyX2lkKS50b0JlKG93bmVyLmlkKTtcclxuICBjb25zdCBzZW5zb3JOZXR3b3JrID0gJ0RyaXZlLUlPLW1vdG9yc3RldWVydW5nLWNhbi1mZC1TMDEnO1xyXG4gIGNvbnN0IG5ldHdvcmtzID0gKGF3YWl0IHJlYWRQcm9qZWN0KHBhZ2UsIHByb2plY3QsICcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93JykpLnBhcmFtZXRlcnMubmV0d29ya3M7XHJcbiAgZXhwZWN0KG5ldHdvcmtzLm1hcCgoaXRlbTogeyBpZDogc3RyaW5nIH0pID0+IGl0ZW0uaWQpLnNvcnQoKSkudG9FcXVhbChbLi4ub3JpZ2luYWxOZXR3b3Jrcywgc2Vuc29yTmV0d29ya10uc29ydCgpKTtcclxuICBleHBlY3QobmV3IFNldChuZXR3b3Jrcy5tYXAoKGl0ZW06IHsgbmFtZTogc3RyaW5nIH0pID0+IGl0ZW0ubmFtZSkpLnNpemUpLnRvQmUobmV0d29ya3MubGVuZ3RoKTtcclxuICBjb25zdCB0b3BvbG9neSA9IChhd2FpdCByZWFkUHJvamVjdChwYWdlLCBwcm9qZWN0LCAnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9uZXR3b3JrLXZpZXcnKSkudG9wb2xvZ3k7XHJcbiAgY29uc3QgbG9jYWxFZGdlID0gdG9wb2xvZ3kuZWRnZXMuZmluZCgoZWRnZTogYW55KSA9PiBlZGdlLnBoeXNpY2FsTmV0d29ya0lkID09PSBzZW5zb3JOZXR3b3JrKTtcclxuICBleHBlY3QobG9jYWxFZGdlKS50b0JlVHJ1dGh5KCk7XHJcbiAgZXhwZWN0KGxvY2FsRWRnZS5idXMpLnRvQmUoJ2Nhbl9mZCcpO1xyXG4gIGV4cGVjdChPYmplY3QudmFsdWVzKGxvY2FsRWRnZS5yb3V0aW5nTWV0YWRhdGEpKS50b0NvbnRhaW5FcXVhbChleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7XHJcbiAgICBzb3VyY2U6IHNlbnNvcnNbMF0uaWQsIHRhcmdldDogb3duZXIuaWQsIGFwcHJvdmFsU3RhdGU6ICdBUFBST1ZFRCcsIHByb3RvY29sOiAnQ0FOX0ZEJyxcclxuICB9KSk7XHJcbiAgZm9yIChjb25zdCBbc2lkZSwgaGFyZHdhcmVJZF0gb2YgW1snc291cmNlJywgc2Vuc29yc1swXS5pZF0sIFsndGFyZ2V0Jywgb3duZXIuaWRdXSkge1xyXG4gICAgY29uc3Qgbm9kZSA9IHRvcG9sb2d5Lm5vZGVzLmZpbmQoKGl0ZW06IGFueSkgPT4gaXRlbS5pZCA9PT0gbG9jYWxFZGdlW3NpZGVdKTtcclxuICAgIGV4cGVjdChub2RlLmVuZ2luZWVyaW5nSWQpLnRvQmUoaGFyZHdhcmVJZCk7XHJcbiAgICBleHBlY3Qobm9kZS5wb3J0cykudG9Db250YWluRXF1YWwoZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoeyBpZDogbG9jYWxFZGdlW3NpZGUgKyAnUG9ydCddLFxyXG4gICAgICBidXM6ICdjYW5fZmQnLCBwaHlzaWNhbE5ldHdvcmtJZDogc2Vuc29yTmV0d29yayB9KSk7XHJcbiAgfVxyXG4gIGNvbnN0IGFydGlmYWN0cyA9IGF3YWl0IHZlcmlmeUFydGlmYWN0cyhwYWdlLCBwcm9qZWN0LCAxKTtcclxuICBhd2FpdCB0ZXN0SW5mby5hdHRhY2goJ2FtZW5kbWVudC1ldmlkZW5jZScsIHsgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBwcm9qZWN0LCAuLi5jb250aW51aXR5LCAuLi5hcnRpZmFjdHMgfSksIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicgfSk7XHJcbn0pO1xyXG4iXSwibWFwcGluZ3MiOiJBQUFBLFNBQVNBLElBQUksRUFBRUMsTUFBTSxRQUFtQixpQkFBaUI7QUFDekQsU0FBU0MsUUFBUSxRQUFRLGtCQUFrQjtBQUMzQyxTQUFTQyxVQUFVLFFBQVEsYUFBYTtBQUN4QyxTQUFTQyxZQUFZLFFBQVEsb0JBQW9CO0FBQ2pELFNBQVNDLHNCQUFzQixFQUFFQyxZQUFZLEVBQUVDLFdBQVcsUUFBUSxvQ0FBb0M7QUFFdEcsTUFBTUMsS0FBSyxHQUFHRixZQUFZO0FBQzFCLE1BQU1HLElBQUksR0FBR0YsV0FBVztBQUV4QixNQUFNRyxZQUFZLEdBQUcsSUFBSUMsR0FBRyxDQUF3QixDQUFDO0FBQ3JELE1BQU1DLG9CQUFvQixHQUFHLElBQUlDLE9BQU8sQ0FBaUIsQ0FBQztBQUMxRCxNQUFNQyxrQkFBa0IsR0FBRyxJQUFJSCxHQUFHLENBQW9CLENBQUM7QUFFdkRYLElBQUksQ0FBQ2UsVUFBVSxDQUFDLE9BQU87RUFBRUM7QUFBSyxDQUFDLEVBQUVDLElBQUksS0FBSztFQUN4QyxNQUFNQyxJQUFtQixHQUFHLEVBQUU7RUFDOUJSLFlBQVksQ0FBQ1MsR0FBRyxDQUFDRixJQUFJLENBQUNHLE1BQU0sRUFBRUYsSUFBSSxDQUFDO0VBQ25DTixvQkFBb0IsQ0FBQ08sR0FBRyxDQUFDSCxJQUFJLEVBQUUsRUFBRSxDQUFDO0VBQ2xDRixrQkFBa0IsQ0FBQ0ss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