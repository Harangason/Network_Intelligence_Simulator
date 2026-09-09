import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { readFile, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const base = 'http://127.0.0.1:13500';
const evidence = 'docs/implementation_audit/verification/';
const smoke = JSON.parse(await readFile(process.argv[2] || evidence + '2026-09-09-nine-step-smoke.json', 'utf8'));
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1647, height: 1272 } });
page.setDefaultTimeout(30000);
const report = { pages: [], progress: [], errors: [] };
page.on('pageerror', error => report.errors.push(String(error)));
const paths = ['/studio/engineering', '/studio/routing', '/studio?mode=network',
  '/studio?mode=parameters', '/studio/capacity', '/studio/validation',
  '/studio/simulation', '/studio/results', '/studio/intelligence'];
try {
  for (const [index, path] of paths.entries()) {
    const response = await page.goto(`${base}${path}${path.includes('?') ? '&' : '?'}project=${smoke.project}`, { waitUntil: 'domcontentloaded' });
    assert.equal(response.status(), 200);
    await page.locator('main').waitFor();
    await page.waitForFunction(() => document.querySelector('main')?.innerText.length > 100);
    report.pages.push({ step: index + 1, path, loaded: true, heading: await page.locator('main h1, main h2').allTextContents() });
  }
  const project = process.env.NIS_PROGRESS_PROJECT || 'network-project-20260909142156009-65a06f78';
  const response = await page.request.get(`${base}/api/engineering/workflow?view=summary`, { headers: { 'X-Project-ID': project } });
  const source = await response.json();
  let mock;
  await page.route('**/api/engineering/workflow*', async route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/engineering/workflow' && route.request().method() === 'GET') return route.fulfill({ json: mock });
    return route.continue();
  });
  await page.addInitScript(() => {
    window.parameterSamples = [];
    setInterval(() => {
      const bar = document.querySelectorAll('.agent-wizard-progress-card progress')[3];
      if (bar) window.parameterSamples.push(bar.value);
    }, 20);
  });
  for (const [step, state] of [['engineering_model', 'RUNNING'], ['parameters', 'RUNNING'], ['capacity_timing', 'RUNNING'], ['parameters', 'BLOCKED']]) {
    mock = structuredClone(source);
    mock.context.agent_execution = { ...mock.context.agent_execution, step, state, updated_at: new Date().toISOString() };
    mock.statuses.parameters = 'IN_PROGRESS';
    mock.steps = mock.steps.map(item => ({ ...item, status: item.id === 'parameters' ? 'IN_PROGRESS' : 'EMPTY' }));
    await page.goto(`${base}/studio/engineering?project=${project}`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: 'Agent-Auftrag', exact: true }).click();
    await page.locator('.agent-wizard-progress-card').nth(3).waitFor();
    await page.waitForFunction(() => window.parameterSamples.length >= 90);
    const samples = await page.evaluate(() => [...new Set(window.parameterSamples)]);
    if (step === 'parameters' && state === 'RUNNING') {
      assert(samples.some(value => value > 0 && value < 90), JSON.stringify(samples));
      assert.equal(samples.at(-1), 90);
    } else {
      assert(samples.every(value => value === 0 || value === samples.at(-1)), JSON.stringify(samples));
    }
    report.progress.push({ step, state, values: samples });
  }
  await page.screenshot({ path: evidence + '2026-09-09-nine-step-progress.png' });
  assert.deepEqual(report.errors, []);
} finally {
  await writeFile(evidence + '2026-09-09-nine-step-browser.json', JSON.stringify(report, null, 2));
  await browser.close();
}
console.log(JSON.stringify(report));
