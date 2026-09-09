import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
const base = 'http://127.0.0.1:13500';
const project = 'network-project-20260909141231587-a29bc00f';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage();
const report = { routeRequests: 0, summaryRequests: 0, errors: [] };
page.on('pageerror', e => report.errors.push(String(e)));
const response = await page.request.get(`${base}/api/engineering/workflow?view=summary`, { headers: { 'X-Project-ID': project } });
const workflow = await response.json();
await page.route('**/api/engineering/workflow*', route => {
  const url = new URL(route.request().url());
  if (url.pathname === '/api/engineering/workflow' && route.request().method() === 'GET') {
    report.summaryRequests++;
    return route.fulfill({ json: workflow });
  }
  return route.continue();
});
page.on('request', request => {
  if (new URL(request.url()).pathname === '/api/engineering/routing') report.routeRequests++;
});
try {
  await page.goto(`${base}/studio/engineering?project=${project}`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Agent-Auftrag', exact: true }).click();
  await page.locator('.agent-wizard-progress-card').nth(8).waitFor();
  await page.waitForTimeout(12000);
  assert.equal(report.routeRequests, 1, JSON.stringify(report));
  const previousPolls = report.summaryRequests;
  workflow.versions.routing++;
  await page.waitForTimeout(6000);
  assert(report.summaryRequests > previousPolls);
  assert.equal(report.routeRequests, 2, JSON.stringify(report));
  assert.deepEqual(report.errors, []);
  report.stablePollingRequests = 1;
  report.changedRevisionReloaded = true;
} finally {
  await writeFile('docs/implementation_audit/verification/2026-09-09-wizard-performance-browser.json', JSON.stringify(report, null, 2));
  await browser.close();
}
console.log(JSON.stringify(report));
