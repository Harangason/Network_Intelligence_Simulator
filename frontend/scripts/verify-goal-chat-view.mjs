import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-20260910042736034-d11591d0';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [], legacyRequests = [], blockedWrites = [];
let data = { id: 'goal-ui-progress', type: 'PROGRESS', text: 'Controller und Kanalgrenzen prüfen',
  created_at: new Date().toISOString(), status: 'RUNNING',
  workload: { workload_id: 'goal-ui-verification', goal: 'ParkAssist verbinden', status: 'RUNNING', completed: 2, total: 23 },
  progress: [{ label: 'Modellrevision geprüft', status: 'done' }, { label: 'Controller prüfen', status: 'active' }] };
page.on('pageerror', error => errors.push(error.message));
await page.route('**/api/**', async route => {
  const request = route.request();
  if (request.url().includes('/workloads/goal-')) legacyRequests.push(request.url());
  if (!['GET', 'HEAD'].includes(request.method())) {
    blockedWrites.push(new URL(request.url()).pathname);
    return route.fulfill({ json: { success: true, data: {}, ok: true } });
  }
  return route.continue();
});
await page.route('**/api/agent/history**', route => route.fulfill({ json: { updatedAt: Date.now(),
  messages: [{ id: 'goal-ui-message', role: 'assistant', parts: [{ type: 'data-engineering', data }] }] } }));
await page.route('**/api/engineering/agent/conversation', route => route.fulfill({ json: { success: true,
  data: { questions: {}, decisions: {}, findings: {}, selected_context: { active_view: '/studio/engineering', selected_object_refs: [] } } } }));
await fs.writeFile('../backend/runtime/goal-execution-chat.json', JSON.stringify({passed: false, status: 'RUNNING'}));
try {
  await page.goto(`http://127.0.0.1:13500/studio/engineering?project=${project}`);
  await page.getByRole('button', { name: 'AI Assistant öffnen', exact: true }).click();
  const panel = page.locator('.agent-widget-panel');
  await panel.getByText(data.text, { exact: true }).waitFor();
  await panel.getByText('Arbeitsauftrag im Detail', { exact: true }).click();
  await panel.getByText('goal-ui-verification', { exact: true }).waitFor();
  assert.equal(legacyRequests.length, 0, 'Goal details must not request the legacy signal-workload API');
  await page.setViewportSize({ width: 390, height: 844 });
  await panel.getByText('goal-ui-verification', { exact: true }).waitFor();
  assert.deepEqual(errors, []);
  await page.screenshot({ path: '../backend/runtime/goal-execution-chat.png' });
  // Missing hardware facts remain a structured, project-scoped human input.
  data = {id: 'goal-facts', type: 'RESULT', status: 'BLOCKED', text: 'Bestätigte Controllerdaten fehlen.', created_at: new Date().toISOString(),
    workload: {workload_id: 'goal-ui-verification', status: 'BLOCKED'}, metadata: {hardware_facts_required: true}};
  let capturedFacts;
  await page.route('**/api/engineering/agent/execution-goals/goal-ui-verification/hardware-facts', route => {
    assert.equal(route.request().headers()['x-project-id'], project);
    if (route.request().method() === 'POST') {
      capturedFacts = route.request().postDataJSON();
      return route.fulfill({json: {success: true, data: {status: 'PLAN_STALE'}}});
    }
    return route.fulfill({json: {success: true, data: {model_revision: 'verified-revision', status: 'BLOCKED', technologies: ['CAN_FD'], hardware: [
      {id: 'test-hardware', name: 'ChassisController', capabilities: [], controllers: [], interfaces: [
        {id: 'test-port', name: 'Chassis CAN', technology: 'CAN_FD', network_ref: 'chassis-can'}]},
    ]}}});
  });
  await page.route('**/api/engineering/agent/review-session', route => route.fulfill({json: {csrf_token: 'test-review'}}));
  await page.reload();
  if (!await panel.isVisible()) await page.getByRole('button', {name: 'AI Assistant öffnen', exact: true}).click();
  await panel.getByRole('button', {name: 'Fehlende Hardwaredaten ergänzen', exact: true}).click();
  await panel.getByLabel('Technologie unterstützt').selectOption('true');
  await panel.getByLabel('Controller maximal', {exact: true}).fill('1');
  await panel.getByLabel('Kanäle insgesamt', {exact: true}).fill('2');
  await panel.getByLabel('Physische Ports maximal', {exact: true}).fill('2');
  await panel.getByLabel('Unterstützte Bitraten in bit/s', {exact: true}).fill('500000');
  await panel.getByRole('button', {name: 'Vorhandenen Controller erfassen', exact: true}).click();
  await panel.getByLabel('Kanäle maximal', {exact: true}).fill('2');
  await panel.getByLabel(/^Controller für Chassis CAN/).selectOption({index: 1});
  await panel.getByLabel('Kanal für Chassis CAN', {exact: true}).fill('1');
  await panel.getByLabel('Nachweis / Quelle').fill('Geprüftes Datenblatt Revision 3');
  await panel.getByLabel('Die Angaben beschreiben die geprüfte tatsächliche Hardware.').check();
  await panel.getByRole('button', {name: 'Hardwaredaten bestätigen & Auftrag fortsetzen', exact: true}).click();
  await page.waitForFunction(() => ![...document.querySelectorAll('button')].some(b => b.textContent === 'Hardwaredaten bestätigen & Auftrag fortsetzen'));
  assert.equal(capturedFacts.expected_revision, 'verified-revision');
  assert.equal(capturedFacts.capability.hardware_node_ref, 'test-hardware');
  assert.equal(capturedFacts.controllers[0].max_channels, 2);
  assert.equal(capturedFacts.assignments[0].channel_index, 1);
  assert.equal(capturedFacts.assignments[0].controller_ref, capturedFacts.controllers[0].id);

  // A completed background job must replace the visible running response.
  data = {id: 'goal-running', type: 'RESULT', status: 'SIMULATION_RUNNING', text: 'Simulation läuft noch.', created_at: new Date().toISOString(),
    workload: {workload_id: 'goal-ui-verification', status: 'SIMULATION_RUNNING'}};
  await page.route('**/api/engineering/agent/execution-goals/goal-ui-verification/response', route => route.fulfill({json: {success: true,
    data: {agent_response: {...data, id: 'goal-complete', status: 'COMPLETE', text: 'Kommunikation im Trace nachgewiesen.'}}}}));
  await page.reload();
  if (!await panel.isVisible()) await page.getByRole('button', {name: 'AI Assistant öffnen', exact: true}).click();
  await panel.getByText('Kommunikation im Trace nachgewiesen.', {exact: true}).waitFor();
  assert.deepEqual(errors, []);
  const report = { passed: true, fixture: 'Stored progress, hardware-fact and follow-up responses mocked; all model writes intercepted',
    hardwareFacts: 'Explicit controller/channel facts submitted in 390×844 view', followup: 'Running result replaced by durable completion', errors, legacyRequests, blockedWrites };
  await fs.writeFile('../backend/runtime/goal-execution-chat.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} catch (error) {
  await page.screenshot({path: '../backend/runtime/goal-execution-chat-failure.png'});
  await fs.writeFile('../backend/runtime/goal-execution-chat.json', JSON.stringify({passed: false, error: String(error), errors}));
  throw error;
} finally { await browser.close(); }
