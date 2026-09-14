import { chromium } from 'playwright';
import assert from 'node:assert/strict';

// Read-only UI smoke only: writes are suppressed below. This does not execute
// the nine stages and is not release evidence. See frontend/e2e for real E2E.
const projectId = process.env.NIS_PROJECT_ID || 'network-project-20260914053234318-2da25012';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1383, height: 1272 } });
let failed = false;
const pending = new Set();
const pageErrors = [];
page.on('pageerror', error => { pageErrors.push(error.message); console.error('Browser error:', error.message); });
page.on('request', request => pending.add(request.url()));
page.on('requestfinished', request => pending.delete(request.url()));
page.on('requestfailed', request => pending.delete(request.url()));
try {
  page.setDefaultTimeout(15000);
  const hydrated = page.waitForResponse(response => response.url().includes('/api/engineering/') && response.request().method() === 'GET', { timeout: 30000 });
  const workflowLoaded = page.waitForResponse(response => response.url().includes('/api/engineering/workflow?view=summary') && response.ok());
  await page.goto(`http://127.0.0.1:13500/studio/engineering?project=${projectId.replace(/^network-project-/, '')}`, { waitUntil: 'load', timeout: 30000 });
  await hydrated;
  await workflowLoaded;
  await page.route('**/api/**', route => route.request().method() === 'GET' || route.request().url().endsWith('/equipment-assignment-learning/retrieve')
    ? route.continue() : route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }));
  await page.evaluate(projectId => {
    sessionStorage.setItem('networkis:pending-engineering-wizard', JSON.stringify({ projectId, createdAt: Date.now() }));
    window.dispatchEvent(new CustomEvent('engineering-agent:wizard-open', { detail: { projectId } }));
  }, projectId);
  const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  await dialog.waitFor();
  const status = dialog.getByRole('region', { name: 'Statusübersicht des Engineering-Auftrags' });
  await dialog.getByText('Engineering-Modell', { exact: true }).first().waitFor({ timeout: 15000 });
  await dialog.getByText('Modellvorschlag wird geladen …', { exact: true }).waitFor({ state: 'hidden', timeout: 30000 });
  const body = await dialog.innerText();
  assert.ok(!body.includes('Kein Modellvorschlag für diesen Lauf verfügbar.'));
  assert.ok(!body.includes('Modellvorschlag konnte nicht geladen werden.')); 
  for (const label of ['Engineering-Modell', 'Routing-Tabelle', 'Netzwerk-Editor', 'Parameter', 'Capacity & Timing', 'Validation / Preflight', 'Simulation', 'Results / Analysis', 'Data Science & Intelligence']) assert.ok(body.includes(label), label);
  await page.screenshot({ path: '../backend/runtime/wizard-continuity-live.png' });
  assert.deepEqual(pageErrors, [], 'Browser errors invalidate the UI smoke.');
  console.log(JSON.stringify({ passed: true, scope: 'read-only-ui-smoke', nineStagesExecuted: false,
    writeResponsesMocked: true, nineStepsVisible: true, reviewVisible: /Freigabe|Vorschlag/.test(body) }));
} catch (error) {
  failed = true;
  console.error(error);
  console.error('Pending requests:', [...pending]);
  console.error((await page.locator('body').innerText()).slice(-6500));
  await page.screenshot({ path: '../backend/runtime/hmi-switches-failure.png' });
} finally {
  const session = await browser.newBrowserCDPSession();
  await Promise.race([session.send('Browser.close').catch(() => {}), new Promise(resolve => setTimeout(resolve, 2000))]);
  process.exit(failed ? 1 : 0);
}
