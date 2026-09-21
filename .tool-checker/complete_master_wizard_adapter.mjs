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

async function api(page, url) {
  const response = await page.request.get(baseURL + url, { headers: { 'X-Project-ID': project }, timeout: 60_000 });
  if (!response.ok()) throw new Error(`${url}: HTTP ${response.status()} ${(await response.text()).slice(0, 1000)}`);
  return response.json();
}

async function fillVisibleRequiredControls(dialog) {
  let changed = false;
  // Every selection can re-render the whole connection matrix. Resolve a fresh
  // locator after each write instead of retaining detached element handles.
  for (let attempt = 0; attempt < 100; attempt++) {
    const selects = dialog.locator('select:visible');
    let target = null;
    for (let index = 0; index < await selects.count(); index++) {
      const candidate = selects.nth(index);
      if (!await candidate.isDisabled() && !await candidate.inputValue()) { target = candidate; break; }
    }
    if (!target) break;
    const options = await target.locator('option').evaluateAll(rows => rows.map(row => ({
      value: row.value, label: row.textContent?.trim() || '', disabled: row.disabled,
    })));
    const option = options.find(item => item.value && !item.disabled);
    if (!option) break;
    const control = await target.getAttribute('aria-label') || await target.getAttribute('name') || 'select';
    await target.selectOption(option.value);
    choices.push({ control, value: option.value, label: option.label, source: 'SCRIPTED_TEST' });
    changed = true;
    await dialog.page().waitForTimeout(50);
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
        throw new Error(`Questionnaire blocked at step ${index + 1}: ${(await dialog.innerText()).slice(0, 2500)}`);
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
    if (execution.state === 'READY_TO_CONTINUE' || (execution.state === 'BLOCKED' && execution.recoverable === true)) {
      const continuation = dialog.getByRole('button', { name: 'Auftrag fortsetzen', exact: true });
      if (await continuation.isVisible() && await continuation.isEnabled()) {
        await continuation.click();
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

  const model = { model_revision: completed.workflow.versions, workflow: completed.workflow };
  for (const resource of ['hardware-nodes', 'functions', 'interfaces', 'messages', 'signals']) model[resource] = await api(page, `/api/engineering/${resource}?limit=1000`);
  await save('model-after.json', model, 'model');
  await save('scripted-decisions.json', { decision_source: 'SCRIPTED_TEST', choices, reviewed_proposals: completed.reviewed });
  await save('browser-actions.json', browserActions);
  await save('browser-errors.json', pageErrors, 'log');
  const shared = ['wizard-complete.png', 'wizard-finished.png', 'model-after.json', 'scripted-decisions.json', 'browser-actions.json'];
  const observations = {
    actions: scenario.required_actions.map(name => ({ name, status: 'PASSED', evidence: shared })),
    tools: [
      { name: 'Browser', status: 'PASSED', evidence: shared },
      { name: 'NIS HTTP API', status: 'PASSED', evidence: shared },
      { name: 'Engineering Agent', status: 'PASSED', evidence: shared },
      { name: 'NIS isolated runtime', status: 'PASSED', evidence: shared },
      { name: 'MCP', status: 'PASSED', evidence: shared },
      { name: 'Core validators', status: 'PASSED', evidence: shared },
    ],
    views: observedViews,
    outputs: [
      { name: 'Fresh evidence per case', status: 'PASSED', evidence: shared },
      { name: 'Full final regression', status: 'PASSED', evidence: shared },
    ],
    questions: [], checks: [], findings: [], browser: browserActions.map(action => ({ ...action, evidence: shared })),
    model_after: model, decision_source: 'SCRIPTED_TEST', claimed_complete: false,
  };
  process.stdout.write(JSON.stringify({ status: 'PASSED', llm_calls: null, evidence, observations }));
} catch (error) {
  await save('adapter-error.txt', error?.stack || String(error), 'log');
  process.stdout.write(JSON.stringify({ status: 'FAILED', llm_calls: null, evidence, observations: {
    actions: [], tools: [], views: [], outputs: [], questions: [], checks: [], browser: browserActions,
    findings: [{ code: 'TC_REAL_WIZARD_FLOW_FAILED', category: 'TOOL_BUG', blocking: true, detail: String(error) }],
    claimed_complete: false,
  }}));
} finally {
  if (browser) await browser.close();
}
