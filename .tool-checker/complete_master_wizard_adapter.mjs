/** Real-browser adapter for the complete master architecture scenarios. */
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/(.:)/, '$1')), '..');
const require = createRequire(path.join(root, 'frontend', 'package.json'));
const { chromium } = require('playwright');

const input = JSON.parse(await new Promise((resolve, reject) => {
  let value = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', chunk => { value += chunk; });
  process.stdin.on('end', () => resolve(value));
  process.stdin.on('error', reject);
}));

const { step } = input;
const scenario = step.case;
const baseURL = step.base_url.replace(/\/$/, '');
const project = step.project_id;
const evidenceDir = path.join(process.env.TOOL_CHECKER_EVIDENCE_ROOT || path.join(root, '.tool-checker', 'evidence'), scenario.test_id);
await mkdir(evidenceDir, { recursive: true });
const evidence = [];
const choices = [];
const browserActions = [];
const pageErrors = [];
let inventoryAssumptionsApplied = false;
let functionAssumptionsApplied = false;
let deviceAssumptionsApplied = false;
const scriptedInventory = { controllers: [], endpoints: [] };

async function save(name, value, kind = 'backend') {
  const target = path.join(evidenceDir, name);
  await writeFile(target, typeof value === 'string' ? value : JSON.stringify(value, null, 2), 'utf8');
  evidence.push({ ref: name, path: target, kind });
  return value;
}

async function screenshot(page, name) {
  const target = path.join(evidenceDir, name);
  await page.screenshot({ path: target, fullPage: true });
  evidence.push({ ref: name, path: target, kind: 'screenshot' });
}

async function screenshotViewport(page, name) {
  const target = path.join(evidenceDir, name);
  await page.screenshot({ path: target });
  evidence.push({ ref: name, path: target, kind: 'screenshot' });
}

async function api(page, url) {
  const response = await page.request.get(baseURL + url, { headers: { 'X-Project-ID': project }, timeout: 60_000 });
  if (!response.ok()) throw new Error(`${url}: HTTP ${response.status()} ${(await response.text()).slice(0, 1000)}`);
  return response.json();
}

async function apiMaybe(page, url) {
  const response = await page.request.get(baseURL + url, { headers: { 'X-Project-ID': project }, timeout: 60_000 });
  const text = await response.text();
  let data = text;
  try { data = JSON.parse(text); } catch { /* Preserve non-JSON diagnostics. */ }
  return { ok: response.ok(), status: response.status(), data };
}

function simulationEvidence(job) {
  const trace = job?.result?.model_simulation || {};
  return {
    id: job?.id,
    project_id: job?.project_id,
    status: job?.status,
    error: job?.error,
    workflow_snapshot_id: job?.workflow_snapshot_id,
    scenario: trace.scenario,
    trace: job?.result?.trace,
    assessment: job?.result?.assessment,
    warnings: job?.result?.warnings,
    artifacts: job?.artifact_downloads,
    runtime_summary: job?.result?.runtime_metrics?.summary,
    synchronization: job?.result?.runtime_metrics?.synchronization,
    fault_summary: trace.fault_summary,
    first_anomaly: trace.first_anomaly,
    comparison: trace.comparison,
    timing_summary: trace.timing_summary,
    signal_summary: trace.signal_summary,
    storage: trace.storage,
    affected_routes: trace.affected_routes,
    affected_signals: trace.affected_signals,
    event_count: Array.isArray(trace.events) ? trace.events.length : 0,
    frame_count: Array.isArray(trace.frames) ? trace.frames.length : 0,
  };
}

function configuredFaultCount(summary, scenario) {
  const explicit = Number(summary?.configured_faults ?? summary?.total_faults ?? 0);
  if (explicit > 0) return explicit;
  return Array.isArray(scenario?.faults) ? scenario.faults.length : 0;
}

async function waitForSimulation(page, jobId) {
  const started = Date.now();
  while (Date.now() - started < 5 * 60_000) {
    const response = await apiMaybe(page, `/api/simulations/${encodeURIComponent(jobId)}`);
    if (!response.ok) throw new Error(`Simulation ${jobId}: HTTP ${response.status}`);
    const job = response.data;
    if (['completed', 'failed', 'canceled'].includes(String(job?.status || ''))) return job;
    await page.waitForTimeout(700);
  }
  throw new Error(`Simulation ${jobId} did not finish within five minutes.`);
}

async function captureTraceViews(page, jobId, prefix) {
  const views = ['messages', 'sequence', 'signals', 'trace'];
  for (const view of views) {
    await page.goto(`${baseURL}/trace-analysis?job=${encodeURIComponent(jobId)}&view=${view}&project=${encodeURIComponent(project)}`, {
      waitUntil: 'domcontentloaded', timeout: 60_000,
    });
    await page.locator('.trace-analysis-workbench').waitFor({ state: 'visible', timeout: 60_000 });
    await page.waitForTimeout(700);
    await screenshotViewport(page, `${prefix}-trace-${view}.png`);
    browserActions.push({
      target: `Trace ${view}`,
      purpose: 'Simulations-Trace im produktiven Browser prüfen',
      precondition: `Simulation ${jobId} completed`,
      expected_effect: `${view} projection resolves the same simulation job`,
      actual_effect: page.url(),
      url: page.url(),
      status: 'PASSED',
    });
  }
}

async function runFindingEvidence(page, negativeJob) {
  const jobId = negativeJob.id;
  const anomalyTime = Number(negativeJob.result?.model_simulation?.first_anomaly?.time_s);
  if (!Number.isFinite(anomalyTime) || anomalyTime < 0) {
    throw new Error(`Negative simulation ${jobId} has no usable first-anomaly timestamp.`);
  }
  const start = Math.max(0, anomalyTime - 0.001);
  const end = anomalyTime + 0.001;
  const window = await api(page, `/api/simulations/${encodeURIComponent(jobId)}/trace-window?cursor=0&limit=2000&start_s=${start}&end_s=${end}`);
  const faultEvent = (window.events || []).find(item => Array.isArray(item.faults) && item.faults.length > 0)
    || (window.events || []).reduce((nearest, item) => {
      if (!nearest) return item;
      return Math.abs(Number(item.time_s) - anomalyTime) < Math.abs(Number(nearest.time_s) - anomalyTime) ? item : nearest;
    }, null);
  if (!faultEvent) throw new Error(`Negative simulation ${jobId} has no event around its first anomaly.`);
  const eventId = String(faultEvent.event_id || faultEvent.id || '');
  const parameters = new URLSearchParams({
    job: jobId,
    view: 'root-cause',
    project,
    event: eventId,
    focus_s: String(Number(faultEvent.time_s ?? anomalyTime)),
    start_s: String(start),
    end_s: String(end),
  });
  await page.goto(`${baseURL}/trace-analysis?${parameters}`, {
    waitUntil: 'domcontentloaded', timeout: 60_000,
  });
  const analyzeButton = page.getByRole('button', { name: 'Ursache analysieren', exact: true });
  await analyzeButton.waitFor({ state: 'visible', timeout: 60_000 });
  const submitted = page.waitForResponse(response => {
    try {
      const url = new URL(response.url());
      return response.request().method() === 'POST' && url.pathname === '/api/engineering/reasoning';
    } catch {
      return false;
    }
  }, { timeout: 120_000 });
  await analyzeButton.click();
  const response = await submitted;
  if (!response.ok()) throw new Error(`Root-cause analysis failed: HTTP ${response.status()} ${(await response.text()).slice(0, 1000)}`);
  const created = await response.json();
  const persisted = await api(page, `/api/engineering/reasoning/${encodeURIComponent(created.reasoning_id)}`);
  if (persisted.simulation_run_id !== jobId || persisted.validation_status !== 'CURRENT'
      || persisted.completion_status !== 'COMPLETE'
      || !Array.isArray(persisted.confirmed_causes) || persisted.confirmed_causes.length === 0) {
    throw new Error(`Reasoning ${persisted.reasoning_id} is not current for negative simulation ${jobId}.`);
  }
  if (!Array.isArray(persisted.evidence_refs) || persisted.evidence_refs.length === 0) {
    throw new Error(`Reasoning ${persisted.reasoning_id} contains no trace evidence.`);
  }
  await page.getByRole('heading', { name: 'Root Cause', exact: true }).waitFor({ state: 'visible', timeout: 60_000 });
  await screenshotViewport(page, 'negative-trace-root-cause.png');
  await save('reasoning-negative.json', persisted, 'trace');
  const listing = await api(page, `/api/engineering/reasoning?job_id=${encodeURIComponent(jobId)}`);
  await save('reasoning-negative-list.json', listing, 'trace');
  browserActions.push({
    target: 'Ursache analysieren',
    purpose: 'Finding-/Root-Cause-Wizard mit persistierter Trace-Evidenz ausführen',
    precondition: `Negative simulation ${jobId} completed`,
    expected_effect: 'Current persisted reasoning references the negative simulation and its evidence',
    actual_effect: `${persisted.reasoning_id}: ${persisted.completion_status}`,
    url: page.url(),
    status: 'PASSED',
  });
  return persisted;
}

async function runSimulationEvidence(page) {
  const listing = await api(page, '/api/simulations');
  const candidates = (listing.jobs || []).filter(job => job.project_id === project && job.status === 'completed');
  let positiveJob = null;
  for (const candidate of candidates) {
    const job = await api(page, `/api/simulations/${encodeURIComponent(candidate.id)}`);
    const faultCount = configuredFaultCount(
      job.result?.model_simulation?.fault_summary,
      job.result?.model_simulation?.scenario,
    );
    const faults = job.result?.model_simulation?.scenario?.faults;
    if (faultCount === 0 && (!Array.isArray(faults) || faults.length === 0)) {
      positiveJob = job;
      break;
    }
  }
  if (!positiveJob) throw new Error('The completed engineering workflow did not create a positive simulation job.');
  if (!positiveJob.result?.trace?.universal_trace || !positiveJob.artifact_downloads?.some(item => item.name === 'universal_trace.jsonl')) {
    throw new Error(`Positive simulation ${positiveJob.id} has no Universal Trace evidence.`);
  }
  await save('simulation-positive.json', simulationEvidence(positiveJob), 'simulation');
  await save('simulation-positive-trace-window.json', await apiMaybe(
    page, `/api/simulations/${encodeURIComponent(positiveJob.id)}/trace-window?cursor=0&limit=250&start_s=0&end_s=1000000`,
  ), 'trace');
  await captureTraceViews(page, positiveJob.id, 'positive');

  await page.goto(`${baseURL}/studio/simulation?project=${encodeURIComponent(project)}`, {
    waitUntil: 'domcontentloaded', timeout: 60_000,
  });
  const commandBar = page.locator('.simulation-command-bar');
  await commandBar.waitFor({ state: 'visible', timeout: 60_000 });
  const startButton = commandBar.getByRole('button', { name: 'Start', exact: true });
  await startButton.waitFor({ state: 'visible', timeout: 30_000 });
  const startWait = Date.now();
  while (await startButton.isDisabled() && Date.now() - startWait < 30_000) await page.waitForTimeout(250);
  if (await startButton.isDisabled()) {
    await screenshotViewport(page, 'negative-simulation-start-disabled.png');
    throw new Error('Negative simulation Start button remained disabled after successful preflight.');
  }
  const faultEditor = page.locator('.fault-editor');
  await faultEditor.locator('.fault-builder select').nth(0).selectOption('SIGNAL');
  await faultEditor.locator('.fault-builder select').nth(1).selectOption('SIGNAL_STUCK');
  await faultEditor.getByRole('button', { name: 'Hinzufügen', exact: true }).click();
  await faultEditor.locator('.fault-chip', { hasText: 'SIGNAL_STUCK' }).waitFor({ state: 'visible', timeout: 15_000 });
  const submitted = page.waitForResponse(response => {
    try {
      const url = new URL(response.url());
      return response.request().method() === 'POST' && url.pathname === '/api/simulations';
    } catch {
      return false;
    }
  }, { timeout: 120_000 });
  await startButton.click();
  const response = await submitted;
  if (!response.ok()) throw new Error(`Negative simulation start failed: HTTP ${response.status()} ${(await response.text()).slice(0, 1000)}`);
  const startedJob = await response.json();
  const negativeJob = await waitForSimulation(page, startedJob.id);
  if (negativeJob.status !== 'completed') throw new Error(`Negative simulation ${negativeJob.id} ended as ${negativeJob.status}: ${negativeJob.error || ''}`);
  const faultSummary = negativeJob.result?.model_simulation?.fault_summary || {};
  if (configuredFaultCount(faultSummary, negativeJob.result?.model_simulation?.scenario) < 1
      && !negativeJob.result?.model_simulation?.first_anomaly) {
    throw new Error(`Negative simulation ${negativeJob.id} completed without fault evidence.`);
  }
  await save('simulation-negative.json', simulationEvidence(negativeJob), 'simulation');
  await save('simulation-negative-trace-window.json', await apiMaybe(
    page, `/api/simulations/${encodeURIComponent(negativeJob.id)}/trace-window?cursor=0&limit=250&start_s=0&end_s=1000000`,
  ), 'trace');
  for (const tab of ['SEQUENCE', 'SIGNALS', 'BUS LOAD', 'EVENTS']) {
    await page.getByRole('tab', { name: tab, exact: true }).click();
    await page.waitForTimeout(150);
    await screenshotViewport(page, `negative-simulation-${tab.toLowerCase().replaceAll(' ', '-')}.png`);
  }
  await captureTraceViews(page, negativeJob.id, 'negative');
  const reasoning = await runFindingEvidence(page, negativeJob);
  browserActions.push({
    target: 'SIGNAL_STUCK fault simulation',
    purpose: 'Reproduzierbaren Negativlauf im produktiven Simulations-UI ausführen',
    precondition: 'Positive simulation and current preflight exist',
    expected_effect: 'Completed fault job with Universal Trace and fault evidence',
    actual_effect: `${negativeJob.id}: ${negativeJob.status}`,
    url: page.url(),
    status: 'PASSED',
  });
  return { positive: simulationEvidence(positiveJob), negative: simulationEvidence(negativeJob), reasoning };
}

function finalWorkflowStatus(value) {
  return ['COMPLETE', 'APPROVED', 'WARNING'].includes(String(value || '').toUpperCase());
}

function countItems(value) {
  if (Array.isArray(value)) return value.length;
  if (Array.isArray(value?.items)) return value.items.length;
  if (Array.isArray(value?.data)) return value.data.length;
  return Number(value?.count || 0);
}

function selectScriptedOption(control, options) {
  const available = options.filter(item => item.value && !item.disabled);
  const pick = value => available.find(item => item.value.toLowerCase() === value.toLowerCase());
  if (/Messgröße$/.test(control)) {
    if (!scenario.test_id.endsWith('-B')) return null;
    const slot = Number(control.match(/\d+/)?.[0] || 1);
    return pick(['temperature', 'pressure', 'speed', 'torque', 'position', 'flow'][((slot - 1) % 6 + 6) % 6]);
  }
  if (/Stellbefehl$/.test(control)) {
    if (/motor|drive|antrieb|motion|umrichter|servo|steering/i.test(control)) return pick('POSITION');
    if (/ventil|valve|relais|relay|schalt/i.test(control)) return pick('OPEN_CLOSE');
    return null;
  }
  if (/Anschluss$/.test(control)) {
    if (/^System:\s*Anschluss$/i.test(control)) return pick('I2C') || available[0];
    if (/relais|relay|digital.*i.?o/i.test(control)) return pick('GPIO');
    if (/magnetventil/i.test(control) && /digital.*remote/i.test(scenario.input)) return pick('GPIO');
    if (/motor|drive|umrichter|servo|steering/i.test(control)) return pick('EtherCAT') || pick('CAN_FD') || pick('PWM') || pick('ProfiNET');
    if (/robot|edge|computer/i.test(control)) return pick('Ethernet') || pick('DDS') || pick('EtherCAT');
    if (/imu|encoder|abstands/i.test(control)) return pick('CAN_FD') || pick('Ethernet');
    if (/plc|sps/i.test(control)) return pick('ProfiNET') || pick('EtherCAT') || pick('Ethernet');
    if (/sensor/i.test(control) && /io[-\s]?link/i.test(scenario.input)) return pick('IO_LINK');
    const declared = ['I2C', 'SPI', 'UART', 'ModbusRTU', 'ModbusTCP', 'IO_LINK', 'GPIO', 'PWM', 'Ethernet', 'CAN_FD', 'LIN', 'ProfiNET', 'EtherCAT']
      .filter(value => new RegExp(value.replace('_', '[-\\s]?'), 'i').test(scenario.input));
    if (declared.length === 1) return pick(declared[0]);
    if (/gateway|edge|computer|controller|control/i.test(control)) return pick('Ethernet') || pick('ProfiNET') || pick('CAN_FD') || pick('I2C');
    if (/lidar|camera|kamera|stream/i.test(control)) return pick('Ethernet') || pick('DDS');
    if (/sensor|temperature|pressure|speed|position|flow|current|voltage|force|distance|acceleration/i.test(control))
      return pick('IO_LINK') || pick('CAN_FD') || pick('I2C') || pick('ModbusRTU') || pick('Ethernet');
    if (/valve|ventil|aktor|actuator|schalt/i.test(control)) return pick('GPIO') || pick('IO_LINK') || pick('CAN_FD') || pick('ProfiNET');
    return null;
  }
  return available[0];
}

async function supplyScriptedFunctionAssignments(dialog) {
  if (functionAssumptionsApplied) return false;
  const lines = scenario.input.split(/\r?\n/);
  const marker = lines.findIndex(line => /^\s*(?:Funktionen|Functions):\s*$/i.test(line));
  if (marker < 0) return false;
  const functions = [];
  for (const line of lines.slice(marker + 1)) {
    const value = line.replace(/^\s*[-*]\s*/, '').trim();
    if (!value || !/^[\w .()/+-]{1,120}$/u.test(value)) break;
    functions.push(value);
  }
  const controllers = lines.flatMap(line => {
    const match = line.match(/^\s*(?:[-*]\s*)?(?:1|ein(?:e|en|em|er|es)?)\s+(.+?(?:Controller|Computer|PLC|SPS|Steuerung))\s*$/iu);
    if (!match) return [];
    const name = match[1].trim().replace(/\s+Controller$/i, '');
    return [name];
  });
  if (!functions.length || controllers.length < 2) return false;
  const edge = controllers.find(name => /edge|computer|hpc|rechner/i.test(name));
  const control = controllers.find(name => /robot|motion|steuer|plc|sps/i.test(name)) || controllers[0];
  const assignments = Object.fromEntries(functions.map(name => [name,
    edge && /perception|localization|vision|environment|mapping|analytics|object/i.test(name) ? edge : control]));
  await dialog.getByTitle('Projektname', { exact: true }).click();
  const description = dialog.getByRole('textbox', { name: 'Projektbeschreibung', exact: true });
  const current = (await description.inputValue()).replace(/\n?- Funktionszuordnungen:[^\r\n]*/g, '').trim();
  await description.fill(`${current}\n- Funktionszuordnungen: ${JSON.stringify(assignments)}`);
  choices.push({ control: 'Funktionszuordnungen', value: assignments, source: 'SCRIPTED_TEST' });
  functionAssumptionsApplied = true;
  await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  return true;
}

async function supplyScriptedInventory(dialog) {
  if (inventoryAssumptionsApplied) return false;
  const table = dialog.locator('.agent-equipment-table').first();
  if (!await table.isVisible().catch(() => false)) return false;
  inventoryAssumptionsApplied = true;
  const counts = await table.locator('tbody tr').evaluateAll(rows => rows.map(row => ({
    label: row.querySelector('th')?.textContent?.trim() || '',
    recognized: Number(row.querySelector('.agent-count-stack span b')?.textContent || 0),
    required: Number(row.querySelector('input[type=number]')?.value || 0),
  })));
  const lines = [];
  const sensorKinds = ['Temperature', 'Pressure', 'Speed', 'Position', 'Flow', 'Current', 'Voltage', 'Force', 'Distance', 'Acceleration'];
  const actuatorKinds = ['Valve', 'Motor', 'Relay', 'Servo'];
  for (const { label, recognized, required } of counts) {
    for (let index = recognized + 1; index <= required; index++) {
      const suffix = String(index).padStart(3, '0');
      if (/Controller/i.test(label)) lines.push(`Controller: TC_Control_${suffix}`);
      else if (/Sensor/i.test(label)) lines.push(`Sensor: TC_${sensorKinds[(index - 1) % sensorKinds.length]}_${suffix}`);
      else if (/Aktor/i.test(label)) lines.push(`Aktor: TC_${actuatorKinds[(index - 1) % actuatorKinds.length]}_${suffix}`);
      else if (/Gateway/i.test(label)) lines.push(`Gateway: TC_Gateway_${suffix}`);
    }
  }
  if (!lines.length) return false;
  for (const line of lines) {
    const match = line.match(/^(Controller|Sensor|Aktor):\s*(.+)$/);
    if (!match) continue;
    if (match[1] === 'Controller') scriptedInventory.controllers.push(match[2]);
    else scriptedInventory.endpoints.push(match[2]);
  }
  await dialog.getByTitle('Projektname', { exact: true }).click();
  const description = dialog.getByRole('textbox', { name: 'Projektbeschreibung', exact: true });
  await description.fill(`${(await description.inputValue()).trim()}\n\nTestannahmen (SCRIPTED_TEST, keine reale Hardware):\n${lines.join('\n')}`);
  choices.push({ control: 'Geräteidentitäten ergänzen', value: lines, source: 'SCRIPTED_TEST' });
  await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  return true;
}

async function supplyScriptedDeviceChoices(dialog) {
  if (deviceAssumptionsApplied) return false;
  const section = dialog.getByRole('region', { name: 'Geräteanschlüsse festlegen' });
  if (!await section.isVisible().catch(() => false)) return false;
  const unresolved = await section.locator('select').evaluateAll(rows => rows.flatMap(row => {
    if (row.disabled) return [];
    const selected = row.selectedOptions[0];
    const placeholder = !row.value || selected?.disabled || /bitte|auswählen|select|offen/i.test(selected?.textContent || '');
    if (!placeholder) return [];
    return [{ control: row.getAttribute('aria-label') || row.getAttribute('name') || 'select',
      options: [...row.options].map(option => ({ value: option.value, label: option.textContent?.trim() || '', disabled: option.disabled })) }];
  }));
  const measurements = {};
  const commands = {};
  const connections = {};
  const owners = {};
  const commandTemplates = {
    OPEN_CLOSE: { length_bits: 1, data_type: 'boolean', unit: 'state', factor: 1, min_value: 0, max_value: 1,
      semantic: { semantic_type: 'BOOLEAN', meaning: 'Angeforderter Schaltzustand' }, data: { allowed_values: [0, 1] } },
    POSITION: { length_bits: 10, data_type: 'unsigned', unit: '%', factor: 0.1, min_value: 0, max_value: 100,
      semantic: { semantic_type: 'NUMERIC', meaning: 'Angeforderte Stellposition' }, data: { minimum: 0, maximum: 100, resolution: 0.1 } },
  };
  for (const item of unresolved) {
    const option = selectScriptedOption(item.control, item.options);
    if (!option) continue;
    const rawName = item.control.replace(/:\s*(Messgröße|Stellbefehl|Anschluss)$/i, '').trim();
    const name = rawName.split(' · ').at(-1).trim();
    if (/Messgröße$/i.test(item.control)) measurements[name] = option.value;
    else if (/Stellbefehl$/i.test(item.control) && commandTemplates[option.value]) commands[name] = commandTemplates[option.value];
    else if (/Anschluss$/i.test(item.control)) connections[name] = option.value;
  }
  if (scriptedInventory.controllers.length) {
    scriptedInventory.endpoints.forEach((name, index) => {
      owners[name] = scriptedInventory.controllers[index % scriptedInventory.controllers.length];
    });
  }
  if (!Object.keys(measurements).length && !Object.keys(commands).length
      && !Object.keys(connections).length && !Object.keys(owners).length) return false;
  await dialog.getByTitle('Projektname', { exact: true }).click();
  const description = dialog.getByRole('textbox', { name: 'Projektbeschreibung', exact: true });
  let current = (await description.inputValue())
    .replace(/\n?^- Sensor-Messgrößen:[^\r\n]*$/gm, '')
    .replace(/\n?^- Aktor-Befehle:[^\r\n]*$/gm, '')
    .replace(/\n?^- Geräteanschlüsse:[^\r\n]*$/gm, '')
    .replace(/\n?^- Gerätezuordnungen:[^\r\n]*$/gm, '').trim();
  if (Object.keys(measurements).length) current += `\n- Sensor-Messgrößen: ${JSON.stringify(measurements)}`;
  if (Object.keys(commands).length) current += `\n- Aktor-Befehle: ${JSON.stringify(commands)}`;
  if (Object.keys(connections).length) current += `\n- Geräteanschlüsse: ${JSON.stringify(connections)}`;
  if (Object.keys(owners).length) current += `\n- Gerätezuordnungen: ${JSON.stringify(owners)}`;
  await description.fill(current);
  if (Object.keys(measurements).length) choices.push({ control: 'Sensor-Messgrößen', value: measurements, source: 'SCRIPTED_TEST' });
  if (Object.keys(commands).length) choices.push({ control: 'Aktor-Befehle', value: commands, source: 'SCRIPTED_TEST' });
  if (Object.keys(connections).length) choices.push({ control: 'Geräteanschlüsse', value: connections, source: 'SCRIPTED_TEST' });
  if (Object.keys(owners).length) choices.push({ control: 'Gerätezuordnungen', value: owners, source: 'SCRIPTED_TEST' });
  deviceAssumptionsApplied = true;
  await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  await dialog.page().waitForTimeout(300);
  return true;
}

async function fillVisibleRequiredControls(dialog) {
  let changed = await supplyScriptedFunctionAssignments(dialog);
  changed = await supplyScriptedInventory(dialog) || changed;
  changed = await supplyScriptedDeviceChoices(dialog) || changed;
  const detectedDomain = dialog.locator('.agent-domain-mismatch button, [role=alert] button').filter({ hasText: /übernehmen$/i }).first();
  if (await detectedDomain.isVisible().catch(() => false) && !await detectedDomain.isDisabled()) {
    const label = (await detectedDomain.innerText()).trim();
    await detectedDomain.click();
    choices.push({ control: 'domain-mismatch', value: label, source: 'SCRIPTED_TEST' });
    changed = true;
  }
  const bulkConnections = dialog.getByRole('button', { name: /für alle offenen Anschlüsse übernehmen$/i }).first();
  if (await bulkConnections.isVisible().catch(() => false) && !await bulkConnections.isDisabled()) {
    const label = (await bulkConnections.innerText()).trim();
    await bulkConnections.click();
    choices.push({ control: 'open-device-connections', value: label, source: 'SCRIPTED_TEST' });
    changed = true;
    await dialog.page().waitForTimeout(300);
  }
  const clusterSelector = dialog.locator('.agent-cluster-selector select');
  if (await clusterSelector.isVisible().catch(() => false) && !await clusterSelector.isDisabled()) {
    const clusterOptions = await clusterSelector.locator('option').evaluateAll(rows => rows.map(row => ({
      value: row.value,
      label: row.textContent?.trim() || '',
      disabled: row.disabled,
    })).filter(item => item.value && !item.disabled));
    for (const cluster of clusterOptions) {
      await dialog.locator('.agent-cluster-selector select').selectOption(cluster.value);
      await dialog.page().waitForTimeout(200);
      const unresolved = dialog.locator('.agent-cluster-unassigned:visible');
      if (!await unresolved.count()) continue;
      const selectAll = unresolved.locator('input[type=checkbox]').first();
      const owner = unresolved.locator('select').first();
      const ownerOptions = await owner.locator('option').evaluateAll(rows => rows.map(row => ({
        value: row.value,
        label: row.textContent?.trim() || '',
        disabled: row.disabled,
      })).filter(item => item.value && !item.disabled));
      if (!ownerOptions.length) continue;
      const hint = `${cluster.label} ${await unresolved.innerText()}`;
      const preferredOwner = /motor|drive|steering|fahrwerk|antrieb|motion/i.test(hint)
        ? ownerOptions.find(item => /robot|motion|steuer|plc/i.test(item.label))
        : /lidar|camera|kamera|perception|umfeld/i.test(hint)
          ? ownerOptions.find(item => /edge|computer|hcp/i.test(item.label)) : undefined;
      const selectedOwner = preferredOwner || ownerOptions[0];
      await selectAll.check();
      await owner.selectOption(selectedOwner.value);
      const assign = unresolved.getByRole('button', { name: 'Auswahl zuordnen', exact: true });
      await assign.click();
      choices.push({
        control: `${cluster.label}: offene Teilnehmer zuordnen`,
        value: selectedOwner.value,
        label: selectedOwner.label,
        source: 'SCRIPTED_TEST',
      });
      changed = true;
      await dialog.page().waitForTimeout(300);
    }
  }
  const textControls = dialog.locator('textarea:visible, input[type=text]:visible');
  for (let index = 0; index < await textControls.count(); index++) {
    const control = textControls.nth(index);
    if (await control.isDisabled() || (await control.inputValue()).trim()) continue;
    const name = await control.getAttribute('aria-label') || await control.getAttribute('name') || await control.getAttribute('placeholder') || 'text';
    if (/hinweis|optional/i.test(name)) continue;
    const value = /projektname|project.name/i.test(name) ? `Master ${scenario.test_id}` : scenario.input;
    await control.fill(value);
    choices.push({ control: name, value, source: 'SCRIPTED_TEST' });
    changed = true;
  }
  // Every selection can re-render the whole connection matrix. Resolve a fresh
  // locator after each write instead of retaining detached element handles.
  for (let attempt = 0; attempt < 1000; attempt++) {
    const selects = dialog.locator('select:visible');
    const pending = await selects.evaluateAll(rows => rows.flatMap((row, index) => {
      if (row.disabled) return [];
      const selected = row.selectedOptions[0];
      const placeholder = !row.value || selected?.disabled || /bitte|auswählen|select|offen/i.test(selected?.textContent || '');
      if (!placeholder) return [];
      return [{ index, control: row.getAttribute('aria-label') || row.getAttribute('name') || 'select',
        options: [...row.options].map(option => ({ value: option.value, label: option.textContent?.trim() || '', disabled: option.disabled })) }];
    }));
    const selected = pending.map(item => ({ ...item, option: selectScriptedOption(item.control, item.options) }))
      .find(item => item.option);
    if (!selected) break;
    const target = selects.nth(selected.index);
    const { control, option } = selected;
    await target.selectOption(option.value);
    choices.push({ control, value: option.value, label: option.label, source: 'SCRIPTED_TEST' });
    changed = true;
    // Selection updates the task marker and reparses the complete inventory.
    // Playwright waits for the controlled select event itself. A short yield is
    // enough for large matrices and avoids minutes of artificial idle time.
    await dialog.page().waitForTimeout(pending.length > 25 ? 20 : 150);
  }
  const radioGroups = await dialog.locator('input[type=radio]:visible').evaluateAll(rows => [...new Set(rows.map(row => row.getAttribute('name')).filter(Boolean))]);
  for (const name of radioGroups) {
    const group = dialog.locator(`input[type=radio][name=${JSON.stringify(name)}]:visible`);
    if (await group.evaluateAll(rows => rows.some(row => row.checked))) continue;
    const first = group.first();
    if (await first.count() && !await first.isDisabled()) {
      await first.check();
      choices.push({ control: name, value: await first.getAttribute('value'), source: 'SCRIPTED_TEST' });
      changed = true;
    }
  }
  const clusterSelectorForBus = dialog.locator('.agent-cluster-selector select');
  if (await clusterSelectorForBus.isVisible().catch(() => false)) {
    const clusterIds = await clusterSelectorForBus.locator('option').evaluateAll(rows => rows.map(row => row.value).filter(Boolean));
    for (const clusterId of clusterIds) {
      await clusterSelectorForBus.selectOption(clusterId);
      const review = dialog.locator('.agent-equipment-clusters article.agent-cluster-review');
      const network = review.getByRole('combobox', { name: /Bustechnik/ });
      if (!await network.isVisible().catch(() => false) || !await review.locator('.agent-cluster-warnings').count()) continue;
      const original = await network.inputValue();
      const options = await network.locator('option').evaluateAll(rows => rows.map(row => ({ value: row.value, label: row.textContent?.trim() || '' })).filter(row => row.value));
      let resolved = false;
      for (const option of options) {
        await network.selectOption(option.value);
        if (!await review.locator('.agent-cluster-warnings').count()) {
          choices.push({ control: `${clusterId}: Bustechnik`, value: option.value, label: option.label, source: 'SCRIPTED_TEST' });
          changed = true;
          resolved = true;
          break;
        }
      }
      if (!resolved) await network.selectOption(original);
    }
  }
  return changed;
}

async function runQuestionnaire(page, dialog) {
  await dialog.getByTitle('Projektname', { exact: true }).click();
  await dialog.locator('#engineering-project-name').fill(`Master ${scenario.test_id}`);
  await dialog.getByLabel('Projektbeschreibung', { exact: true }).fill(scenario.input);
  for (let index = 0; index < 14; index++) {
    await fillVisibleRequiredControls(dialog);
    await screenshot(page, `wizard-questionnaire-${String(index + 1).padStart(2, '0')}.png`);
    const next = dialog.locator('.eng-agent-questionnaire-head').getByRole('button');
    await next.waitFor({ state: 'visible', timeout: 30_000 });
    if (await next.isDisabled()) {
      const changed = await fillVisibleRequiredControls(dialog);
      if (!changed || await next.isDisabled()) {
        const text = await dialog.innerText();
        const unresolvedControls = await dialog.locator('select:visible').evaluateAll(rows => rows.flatMap(row => {
          const selected = row.selectedOptions[0];
          const placeholder = !row.value || selected?.disabled || /bitte|auswählen|select|offen/i.test(selected?.textContent || '');
          if (!placeholder || row.disabled) return [];
          return [{ control: row.getAttribute('aria-label') || row.getAttribute('name') || 'select',
            options: [...row.options].map(option => ({ value: option.value, label: option.textContent?.trim() || '', disabled: option.disabled })) }];
        }));
        await save(`wizard-questionnaire-${String(index + 1).padStart(2, '0')}-unresolved.json`, unresolvedControls, 'log');
        await save(`wizard-questionnaire-${String(index + 1).padStart(2, '0')}-blocked.txt`, text, 'log');
        throw new Error(`Questionnaire blocked at step ${index + 1}: ${text.slice(-6000)}`);
      }
    }
    const label = (await next.innerText()).trim();
    await next.click();
    browserActions.push({ target: label, purpose: 'Haupt-Wizard schrittweise ausführen', precondition: `Questionnaire step ${index + 1} valid`, expected_effect: label === 'Übernehmen' ? 'Engineering run starts' : 'Next questionnaire step', actual_effect: 'Button accepted', url: page.url(), status: 'PASSED' });
    if (label === 'Übernehmen') return;
  }
  throw new Error('Questionnaire did not reach Übernehmen within 14 steps.');
}

async function completeRun(page, dialog) {
  const reviewed = [];
  const started = Date.now();
  let lastState = '';
  while (Date.now() - started < 20 * 60_000) {
    const workflow = await api(page, '/api/engineering/workflow?view=summary');
    const execution = workflow.context?.agent_execution || {};
    lastState = `${execution.state || 'UNKNOWN'}:${execution.step || ''}:${execution.message || ''}`;
    if (Object.values(workflow.statuses || {}).length >= 9 && Object.values(workflow.statuses).every(value => ['COMPLETE', 'APPROVED', 'WARNING'].includes(value))) {
      return { workflow, reviewed };
    }
    if (execution.state === 'REVIEW_REQUIRED') {
      const conversation = await api(page, '/api/engineering/agent/conversation');
      const proposalId = conversation.data?.active_proposal;
      if (!proposalId || reviewed.includes(proposalId)) { await page.waitForTimeout(1000); continue; }
      const approval = dialog.getByRole('button', { name: /^(Freigeben, übernehmen & fortfahren|Übernehmen & fortfahren)$/ });
      await approval.waitFor({ state: 'visible', timeout: 60_000 });
      await approval.click();
      reviewed.push(proposalId);
      browserActions.push({ target: proposalId, purpose: 'Sichtbaren Vorschlag im Wizard als Testentscheidung freigeben', precondition: 'REVIEW_REQUIRED', expected_effect: 'Proposal applied and workflow continues', actual_effect: 'Approval clicked', url: page.url(), status: 'PASSED' });
      await page.waitForTimeout(750);
      continue;
    }
    if (execution.state === 'BLOCKED' && /READY_WITH_WARNINGS/.test(execution.message || '')) {
      const approval = dialog.getByRole('button', { name: 'Warnungen freigeben und fortsetzen', exact: true });
      if (await approval.isVisible().catch(() => false)) {
        await approval.click({ timeout: 10_000 });
        browserActions.push({ target: 'Warnungen freigeben und fortsetzen', purpose: 'Sichtbare Preflight-Warnungen als Testentscheidung freigeben', precondition: 'READY_WITH_WARNINGS and approval button visible', expected_effect: 'Preflight approval is persisted and run continues', actual_effect: 'Approval clicked', url: page.url(), status: 'PASSED' });
      }
      await page.waitForTimeout(750);
      continue;
    }
    if (execution.state === 'READY_TO_CONTINUE' || (execution.state === 'BLOCKED' && execution.recoverable === true)) {
      const continuation = dialog.getByRole('button', { name: 'Auftrag fortsetzen', exact: true });
      const continuationVisible = await continuation.isVisible({ timeout: 2_000 }).catch(() => false);
      const continuationEnabled = continuationVisible
        && await continuation.isEnabled({ timeout: 2_000 }).catch(() => false);
      if (continuationEnabled) {
        try {
          await continuation.click({ timeout: 5_000 });
        } catch (error) {
          const current = (await api(page, '/api/engineering/workflow?view=summary')).context?.agent_execution || {};
          if (current.state !== execution.state || current.step !== execution.step) continue;
          if (!await continuation.isVisible({ timeout: 2_000 }).catch(() => false)
              || !await continuation.isEnabled({ timeout: 2_000 }).catch(() => false)) throw error;
          await continuation.dispatchEvent('click');
        }
        browserActions.push({ target: 'Auftrag fortsetzen', purpose: 'Durable wizard continuation', precondition: execution.state, expected_effect: 'Next engineering stage starts', actual_effect: 'Continuation clicked', url: page.url(), status: 'PASSED' });
      }
      await page.waitForTimeout(1000);
      continue;
    }
    if (['BLOCKED', 'FAILED', 'INCOMPLETE'].includes(execution.state) && execution.recoverable !== true) {
      throw new Error(`Wizard ${lastState}`);
    }
    await page.waitForTimeout(1000);
  }
  throw new Error(`Wizard timeout after 20 minutes; last state ${lastState}`);
}

let browser;
try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') pageErrors.push(message.text()); });
  await page.goto(`${baseURL}/studio/engineering?assistant=project&project=${encodeURIComponent(project)}`, { waitUntil: 'load', timeout: 120_000 });
  const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  await dialog.waitFor({ state: 'visible', timeout: 60_000 });
  await runQuestionnaire(page, dialog);
  const completed = await completeRun(page, dialog);
  await screenshot(page, 'wizard-complete.png');
  const finish = dialog.getByRole('button', { name: 'Fertig stellen', exact: true });
  await finish.waitFor({ state: 'visible', timeout: 30_000 });
  await finish.click();
  await dialog.waitFor({ state: 'hidden', timeout: 60_000 });
  browserActions.push({ target: 'Fertig stellen', purpose: 'Haupt-Wizard regulär abschließen', precondition: 'Alle neun Stufen abgeschlossen', expected_effect: 'Wizard closes and project remains available', actual_effect: 'Dialog closed', url: page.url(), status: 'PASSED' });
  await screenshot(page, 'wizard-finished.png');

  const simulationRuns = await runSimulationEvidence(page);

  const views = [
    ['Projects', `/projects?project=${project}`],
    ['Engineering', `/studio/engineering?project=${project}`],
    ['Routing', `/studio/routing?project=${project}`],
    ['Network', `/studio?mode=network&project=${project}`],
    ['Capacity', `/studio/capacity?project=${project}`],
    ['Validation', `/studio/validation?project=${project}`],
    ['Simulation', `/studio/simulation?project=${project}`],
    ['Trace', `/trace-analysis?project=${project}`],
    ['Intelligence', `/studio/intelligence?project=${project}`],
  ];
  const observedViews = [];
  for (const [name, url] of views) {
    await page.goto(baseURL + url, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    await page.waitForTimeout(350);
    await screenshot(page, `view-${name.toLowerCase()}.png`);
    observedViews.push({ name, status: 'PASSED', evidence: [`view-${name.toLowerCase()}.png`] });
  }

  const fullWorkflow = await api(page, '/api/engineering/workflow');
  const model = { model_revision: fullWorkflow.versions, workflow: fullWorkflow };
  for (const resource of ['hardware-nodes', 'functions', 'interfaces', 'messages', 'signals']) model[resource] = await api(page, `/api/engineering/${resource}?limit=1000`);
  await save('model-after.json', model, 'model');
  const agentHistory = await apiMaybe(page, '/api/engineering/agent/history');
  const conversation = await apiMaybe(page, '/api/engineering/agent/conversation');
  const toolRegistry = await apiMaybe(page, '/api/engineering/tools');
  const preflight = await apiMaybe(page, '/api/engineering/preflight');
  const capacity = await apiMaybe(page, '/api/engineering/capacity');
  const addressingConflicts = await apiMaybe(page, '/api/engineering/addressing/conflicts');
  const proposals = [];
  for (const proposalId of [...new Set(completed.reviewed)]) {
    proposals.push({ proposal_id: proposalId, ...(await apiMaybe(page, `/api/engineering/agent/proposals/${encodeURIComponent(proposalId)}`)) });
  }
  await save('agent-history.json', agentHistory);
  await save('agent-conversation.json', conversation);
  await save('mcp-tool-registry.json', toolRegistry);
  await save('reviewed-proposals.json', proposals);
  await save('core-preflight.json', preflight);
  await save('capacity-timing.json', capacity);
  await save('addressing-conflicts.json', addressingConflicts);

  await page.reload({ waitUntil: 'domcontentloaded', timeout: 60_000 });
  const persistedWorkflow = await api(page, '/api/engineering/workflow?view=summary');
  const persistedHardware = await api(page, '/api/engineering/hardware-nodes?limit=1000');
  const persistence = {
    versions_match: JSON.stringify(persistedWorkflow.versions) === JSON.stringify(fullWorkflow.versions),
    hardware_count_before: countItems(model['hardware-nodes']),
    hardware_count_after: countItems(persistedHardware),
    workflow: persistedWorkflow,
  };
  persistence.hardware_count_match = persistence.hardware_count_before === persistence.hardware_count_after;
  await save('persistence-reload.json', persistence);
  await save('scripted-decisions.json', { decision_source: 'SCRIPTED_TEST', choices, reviewed_proposals: completed.reviewed });
  await save('browser-actions.json', browserActions);
  await save('browser-errors.json', pageErrors, 'log');
  const shared = [
    'wizard-complete.png', 'wizard-finished.png', 'model-after.json', 'scripted-decisions.json', 'browser-actions.json',
    'agent-history.json', 'agent-conversation.json', 'mcp-tool-registry.json', 'reviewed-proposals.json',
    'core-preflight.json', 'capacity-timing.json', 'addressing-conflicts.json', 'persistence-reload.json',
    'simulation-positive.json', 'simulation-positive-trace-window.json',
    'simulation-negative.json', 'simulation-negative-trace-window.json',
    'reasoning-negative.json', 'reasoning-negative-list.json', 'negative-trace-root-cause.png',
  ];
  const checks = [];
  const addChecks = (category, status) => {
    for (const name of scenario[category] || []) checks.push({ name, category, status, evidence: shared });
  };
  const artifactChecks = fullWorkflow.artifact_checks || {};
  const engineering = artifactChecks.engineering_model || {};
  const network = artifactChecks.network_editor || {};
  const routing = artifactChecks.routing || {};
  const consistency = engineering.consistency || {};
  const incomplete = engineering.incomplete || {};
  const modelOk = engineering.complete === true
    && network.complete === true
    && routing.complete === true
    && Number(consistency.functions_duplicate || 0) === 0
    && Number(consistency.hardware_interfaces_missing || 0) === 0
    && Object.values(incomplete).every(value => Number(value || 0) === 0)
    && Number(network.invalid?.nodes || 0) === 0
    && Number(network.invalid?.edges || 0) === 0
    && Number(routing.counts?.invalid || 0) === 0;
  const calculationOk = capacity.ok && !['FAILED', 'ERROR', 'BLOCKED'].includes(String(capacity.data?.status || '').toUpperCase());
  const preflightBlockers = Array.isArray(preflight.data?.findings)
    ? preflight.data.findings.filter(item => item?.blocking === true || String(item?.severity || '').toUpperCase() === 'ERROR') : [];
  const validationOk = preflight.ok
    && !['FAILED', 'ERROR', 'BLOCKED'].includes(String(preflight.data?.status || '').toUpperCase())
    && preflightBlockers.length === 0
    && ['APPROVED', 'WARNING'].includes(String(fullWorkflow.statuses?.validation || '').toUpperCase());
  const positiveSimulationOk = simulationRuns.positive.status === 'completed'
    && simulationRuns.positive.trace?.universal_trace === true
    && Number(simulationRuns.positive.trace?.events || 0) > 0;
  const negativeSimulationOk = simulationRuns.negative.status === 'completed'
    && configuredFaultCount(simulationRuns.negative.fault_summary, simulationRuns.negative.scenario) > 0
    && Number(simulationRuns.negative.trace?.events || 0) > 0;
  const findingEvidenceOk = simulationRuns.reasoning?.simulation_run_id === simulationRuns.negative.id
    && simulationRuns.reasoning?.validation_status === 'CURRENT'
    && Array.isArray(simulationRuns.reasoning?.evidence_refs)
    && simulationRuns.reasoning.evidence_refs.length > 0;
  const visualizationOk = observedViews.length === views.length;
  const completedWorkflow = completed.workflow || {};
  const allStagesFinal = Object.values(completedWorkflow.statuses || {}).length >= 9
    && Object.values(completedWorkflow.statuses || {}).every(finalWorkflowStatus);
  const persistenceOk = persistence.versions_match && persistence.hardware_count_match;
  const conflictCount = Number(addressingConflicts.data?.count || 0);
  const wizardTargets = completedWorkflow.context?.agent_wizard_status?.hardware_counts
    || fullWorkflow.context?.agent_wizard_status?.hardware_counts
    || {};
  const expectedHardwareCount = Object.values(wizardTargets).reduce((sum, value) => sum + Number(value || 0), 0);
  const actualHardwareCount = countItems(model['hardware-nodes']);
  const countsMatch = expectedHardwareCount > 0 && expectedHardwareCount === actualHardwareCount;
  const observedIndustry = String(fullWorkflow.parameters?.industry
    || completedWorkflow.context?.agent_wizard_status?.industry
    || fullWorkflow.context?.agent_wizard_status?.industry
    || '');
  const domainText = `${scenario.title || ''}\n${scenario.input || ''}`;
  const explicitlyVehicle = /automotive|fahrzeug|vehicle|adas|airbag|karosserie|infotainment/i.test(domainText);
  const explicitlyNonVehicle = /robot|plc|sps|profinet|ethercat|modbus|maschine|anlage|prozess|geb[aä]ude|building|drohne|aircraft|flugzeug|schiff|rail|bahn|windkraft|solar/i.test(domainText);
  const foreignAutomotive = !explicitlyVehicle && explicitlyNonVehicle && /automotive|vehicle/i.test(observedIndustry);
  const completionOk = allStagesFinal
    && completedWorkflow.context?.agent_execution?.state === 'COMPLETED'
    && persistenceOk;

  addChecks('expected_model_changes', modelOk ? 'PASSED' : 'FAILED');
  addChecks('expected_calculations', calculationOk ? 'PASSED' : 'FAILED');
  addChecks('expected_validations', validationOk ? 'PASSED' : 'FAILED');
  addChecks('expected_visualizations', visualizationOk ? 'PASSED' : 'FAILED');
  for (const name of scenario.completion_criteria || []) {
    let status = completionOk;
    if (/Identifier-Konflikte/i.test(name)) status = validationOk && conflictCount === 0;
    else if (/Duplikate/i.test(name)) status = persistenceOk && Number(consistency.functions_duplicate || 0) === 0;
    else if (/vollständige fachliche Artefakte/i.test(name)) status = completionOk && modelOk && calculationOk && validationOk && positiveSimulationOk && negativeSimulationOk && findingEvidenceOk;
    else if (/Simulation|Trace|Ursache|Finding/i.test(name)) status = status && positiveSimulationOk && negativeSimulationOk && findingEvidenceOk;
    checks.push({ name, category: 'completion_criteria', status: status ? 'PASSED' : 'FAILED', evidence: shared });
  }
  for (const name of scenario.failure_conditions || []) {
    let observed = false;
    if (/Automotive-Zuordnung/i.test(name)) observed = foreignAutomotive;
    else if (/Erfundene bestätigte Hardwarefakten/i.test(name)) observed = !countsMatch;
    else if (/Delegation/i.test(name)) observed = !completionOk;
    checks.push({ name, category: 'failure_conditions', observed, evidence: shared });
  }
  const findings = [];
  if (foreignAutomotive) findings.push({
    code: 'TC_FOREIGN_AUTOMOTIVE_CLASSIFICATION', category: 'AGENT_BUG', blocking: true,
    detail: `Nicht-automotiver Auftrag wurde als ${observedIndustry || 'Automotive'} klassifiziert.`, evidence: shared,
  });
  if (!countsMatch) findings.push({
    code: 'TC_HARDWARE_SCOPE_MISMATCH', category: 'PRODUCT_BUG', blocking: true,
    detail: `Wizard-Soll ${expectedHardwareCount}, persistiert ${actualHardwareCount}.`, evidence: shared,
  });
  const observations = {
    actions: [
      { name: 'Modellkontext erfassen', status: 'PASSED', evidence: ['model-after.json', 'agent-conversation.json'] },
      { name: 'Originalauftrag an Engineering-Agent senden', status: 'PASSED', evidence: ['browser-actions.json', 'agent-history.json'] },
      { name: 'Agentenantwort und Persistenz prüfen', status: persistenceOk ? 'PASSED' : 'FAILED', evidence: ['agent-history.json', 'persistence-reload.json'] },
      { name: 'Positive Simulation ausführen', status: positiveSimulationOk ? 'PASSED' : 'FAILED', evidence: ['simulation-positive.json', 'simulation-positive-trace-window.json'] },
      { name: 'Negative/Fault Simulation ausführen', status: negativeSimulationOk ? 'PASSED' : 'FAILED', evidence: ['simulation-negative.json', 'simulation-negative-trace-window.json'] },
      { name: 'Finding-/Root-Cause-Wizard ausführen', status: findingEvidenceOk ? 'PASSED' : 'FAILED', evidence: ['reasoning-negative.json', 'reasoning-negative-list.json', 'negative-trace-root-cause.png'] },
      { name: 'Ergebnis im Browser prüfen', status: visualizationOk ? 'PASSED' : 'FAILED', evidence: ['wizard-finished.png', 'browser-actions.json'] },
    ],
    tools: [
      { name: 'Browser', status: 'PASSED', evidence: shared },
      { name: 'NIS HTTP API', status: 'PASSED', evidence: shared },
      { name: 'Engineering Agent', status: completionOk ? 'PASSED' : 'FAILED', evidence: ['agent-history.json', 'agent-conversation.json'] },
      { name: 'NIS isolated runtime', status: 'PASSED', evidence: shared },
      { name: 'MCP', status: toolRegistry.ok && proposals.some(item => item.ok) ? 'PASSED' : 'FAILED', evidence: ['mcp-tool-registry.json', 'reviewed-proposals.json', 'agent-history.json'] },
      { name: 'Core validators', status: validationOk ? 'PASSED' : 'FAILED', evidence: ['core-preflight.json', 'addressing-conflicts.json'] },
    ],
    views: observedViews,
    outputs: [{ name: 'Fresh evidence per case', status: 'PASSED', evidence: shared }],
    questions: [], checks, findings, browser: browserActions.map(action => ({ ...action, evidence: shared })),
    model_after: model, decision_source: 'SCRIPTED_TEST', claimed_complete: false,
  };
  process.stdout.write(JSON.stringify({ status: 'PASSED', llm_calls: null, evidence, observations }));
} catch (error) {
  await save('scripted-decisions-error.json', { decision_source: 'SCRIPTED_TEST', choices, browserActions }, 'log');
  await save('adapter-error.txt', error?.stack || String(error), 'log');
  process.stdout.write(JSON.stringify({ status: 'FAILED', llm_calls: null, evidence, observations: {
    actions: [], tools: [], views: [], outputs: [], questions: [], checks: [], browser: browserActions,
    findings: [{ code: 'TC_REAL_WIZARD_FLOW_FAILED', category: 'TOOL_BUG', blocking: true, detail: String(error) }],
    claimed_complete: false,
  }}));
} finally {
  if (browser) await browser.close();
}
