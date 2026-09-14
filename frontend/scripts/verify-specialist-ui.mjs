import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-20260910042736034-d11591d0';
const browser = await chromium.launch({channel: 'chrome', headless: true});
const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
const errors = [], captured = [], writes = [];
page.on('pageerror', error => errors.push(error.message));
let releaseReview;
const pendingReview = new Promise(resolve => { releaseReview = resolve; });
const plan = {token: 'revision-1', workload_id: 'repair-' + 'a'.repeat(32), groups: [{id: 'group-a', status: 'QUESTION',
  reason: 'Die neue Hardware verbindet die bestehenden Funktionspartner.', connections: [{device: 'Klimatisierung', old_port: 'Alt'}],
  routes: [{id: 'route-a', name: 'Klima → ADAS', code: 'RT-A'}], messages: [{id: 'message-a', name: 'KlimaStatus'}],
  options: [{id: 'adopt-a', label: 'Klima → Gateway → ADAS', action: 'adopt', questions: [],
    comparison: [{id: 'route-a', code: 'RT-A', name: 'Klima → ADAS', before: 'Alter Bus', after: 'Neuer Bus'}]}]}]};
await page.route('**/api/**', async route => {
  const request = route.request(), path = new URL(request.url()).pathname;
  if (path.endsWith('/communication-repair/preview')) return route.fulfill({json: plan});
  if (path.endsWith('/communication-repair/review')) {
    await pendingReview;
    return route.fulfill({json: {...plan, agent_review: {status: 'REVIEWED', model: 'test-model', trace_id: 'test', gaps: [],
      decisions: [{id: 'group-a:adopt-a', recommended: true, reason: 'Die bisherigen Funktionspartner bleiben erhalten.'}]}}});
  }
  if (path.endsWith('/communication-repair/apply')) {
    captured.push({body: request.postDataJSON(), project: request.headers()['x-project-id']});
    return route.fulfill({json: {plan: {token: 'revision-2', groups: []}, applied: [{id: 'group-a', routes: 1, messages: 1, label: 'Neue Führung gespeichert'}]}});
  }
  if (path.includes('/trace-window')) return route.fulfill({json: {events: [
    {timestamp_s: .5, message_id: 'KlimaStatus', source: 'Klima', destination: 'ADAS', finding: 'Empfänger-Timeout', status: 'dropped', technology: 'CAN_FD'}], next_cursor: null}});
  if (!['GET', 'HEAD'].includes(request.method())) {
    writes.push(path);
    return route.fulfill({json: {success: true, data: {}, ok: true}});
  }
  return route.continue();
});
await fs.writeFile('../backend/runtime/specialist-ui.json', JSON.stringify({passed: false, status: 'RUNNING'}));
try {
  await page.goto(`http://127.0.0.1:13500/studio/engineering?assistant=repair&project=${project}`);
  const dialog = page.getByRole('dialog', {name: 'Reparatur-Agent für Kommunikation'});
  await dialog.getByText('Der lokale Fachagent bewertet die Vorschläge.', {exact: false}).waitFor();
  assert.equal(await dialog.getByRole('button', {name: 'Neue Führung übernehmen', exact: true}).isEnabled(), true);
  // A slow inference cannot disable the already reviewed technical strategy.
  await page.setViewportSize({width: 390, height: 844});
  const bounds = await dialog.boundingBox();
  assert.ok(bounds.width <= 390 && bounds.height <= 844, JSON.stringify(bounds));
  await dialog.getByRole('button', {name: 'Neue Führung übernehmen', exact: true}).click();
  await dialog.getByText('Verknüpfungen repariert', {exact: true}).waitFor();
  releaseReview();
  await page.waitForResponse(response => response.url().includes('/communication-repair/review'));
  assert.equal(await dialog.getByRole('button', {name: 'Neue Führung übernehmen', exact: true}).count(), 0,
    'Late model review must not resurrect an already applied plan');
  assert.deepEqual(captured, [{project, body: {workload_id: plan.workload_id, token: plan.token, choices: {'group-a': 'adopt-a'}}}]);
  await page.screenshot({path: '../backend/runtime/specialist-ui-mobile.png'});
  await dialog.getByRole('button', {name: 'Schließen', exact: true}).click();
  await page.setViewportSize({width: 1440, height: 1000});
  await page.goto(`http://127.0.0.1:13500/studio/trace-analysis?view=findings&job=${'b'.repeat(32)}&project=${project}`);
  await page.getByRole('button', {name: 'Ask AI', exact: true}).first().waitFor();
  await page.evaluate(() => window.addEventListener('engineering-agent:run-task', event => { window.__testAgentTask = event.detail; }));
  await page.getByRole('button', {name: 'Ask AI', exact: true}).first().click();
  const task = await page.evaluate(() => window.__testAgentTask);
  assert.equal(task.projectId, project);
  assert.ok(task.text.includes('Empfänger-Timeout') && task.text.includes('b'.repeat(32)));
  await page.locator('.agent-widget-panel').waitFor();
  assert.deepEqual(errors, []);
  await fs.writeFile('../backend/runtime/specialist-ui.json', JSON.stringify({passed: true, checks: [
    'repair preview before inference', 'mobile dialog', 'explicit repair choice with project', 'late response discarded', 'trace action dispatch with correct project and job'], errors, blockedWrites: writes}, null, 2));
} catch (error) {
  await page.screenshot({path: '../backend/runtime/specialist-ui-failure.png'});
  await fs.writeFile('../backend/runtime/specialist-ui.json', JSON.stringify({passed: false, error: String(error), errors}, null, 2));
  throw error;
} finally { releaseReview(); await browser.close(); }
