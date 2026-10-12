// Short real-production functional check. No fixtures, model writes or design test suite.
import { chromium } from '../../../frontend/node_modules/playwright/index.mjs';
import { writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const base = 'http://127.0.0.1:13500';
const project = '20261009072206008-4bb505f1';
const evidence = { status: 'RUNNING', project, captured_at: new Date().toISOString(),
  scope: 'Real historical run: boolean search, syntax feedback, restoration and network pagination. No simulation started, no model writes, no additional design test suite.', observations: {} };
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1401, height: 1244 } });
  page.setDefaultTimeout(60000);
  await page.goto(`${base}/studio/simulation?project=${project}`);
  await page.getByRole('tab', { name: 'SEQUENCE', exact: true }).click();
  await page.locator('.e2e-sequence-context').waitFor();
  await page.waitForFunction(() => Number(document.querySelector('.e2e-sequence-context')?.textContent?.match(/^(\d+) Ereignisse/)?.[1]) > 0);
  // Restored completed traces autoplay. Compare counts only at the same final time.
  await page.waitForFunction(() => {
    const timeline = document.querySelector('.simulation-timeline');
    const range = timeline?.querySelector('input');
    return timeline?.querySelector('span')?.textContent === 'PAUSED'
      && range && Number(range.value) >= Number(range.max) - 0.001;
  });
  evidence.observations.time_basis = await page.locator('.simulation-timeline').innerText();
  const count = async () => Number((await page.locator('.e2e-sequence-context').innerText()).match(/^(\d+) Ereignisse/)?.[1]);
  const original = await count();
  const search = page.getByRole('textbox', { name: 'Sequenzereignisse suchen', exact: true });
  await search.fill('Kameraverarbeitung UND NICHT LIN');
  await page.waitForFunction(expected => { const n = Number(document.querySelector('.e2e-sequence-context')?.textContent?.match(/^(\d+) Ereignisse/)?.[1]); return n > 0 && n < expected; }, original);
  const filtered = await count();
  assert(filtered > 0 && filtered < original);
  await search.fill('Kameraverarbeitung UND');
  await page.locator('.e2e-sequence [role="alert"]').waitFor();
  const syntaxMessage = await page.locator('.e2e-sequence [role="alert"]').innerText();
  assert.equal(await count(), 0);
  assert.equal(await search.getAttribute('aria-invalid'), 'true');
  await search.fill('');
  await page.waitForFunction(expected => Number(document.querySelector('.e2e-sequence-context')?.textContent?.match(/^(\d+) Ereignisse/)?.[1]) === expected, original);
  evidence.observations.sequence_search = { original, query: 'Kameraverarbeitung UND NICHT LIN', filtered,
    invalid_query: 'Kameraverarbeitung UND', syntaxMessage, restored: await count() };

  await page.goto(`${base}/studio/results?project=${project}`);
  const networks = page.getByRole('table', { name: 'Runtime-Netze', exact: true });
  await networks.waitFor();
  const firstRows = await networks.locator('tbody tr').count();
  assert.equal(firstRows, 50);
  const pagination = page.getByRole('navigation', { name: 'Netze durchblättern', exact: true });
  const firstCaption = await pagination.locator('output').innerText();
  await pagination.getByRole('button', { name: 'Weiter', exact: true }).click();
  const secondCaption = await pagination.locator('output').innerText();
  const secondRows = await networks.locator('tbody tr').count();
  assert.equal(secondRows, 46);
  await pagination.getByRole('button', { name: 'Zurück', exact: true }).click();
  assert.equal(await networks.locator('tbody tr').count(), 50);
  evidence.observations.network_pagination = { firstRows, firstCaption, secondRows, secondCaption, restoredRows: 50 };
  // Capture the delivered charts without making geometric/design assertions.
  await page.locator('.runtime-charts').scrollIntoViewIfNeeded();
  await page.screenshot({ path: new URL('production-results.jpg', import.meta.url).pathname.replace(/^\/(\w:)/, '$1'), type: 'jpeg', quality: 85 });
  evidence.status = 'PASSED';
  await writeFile(new URL('production-functional.json', import.meta.url), JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence));
} finally {
  await browser.close();
}
