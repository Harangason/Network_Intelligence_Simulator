import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const base = process.env.NIS_REVIEW_URL ?? 'http://127.0.0.1:13509';
const output = new URL('../docs/implementation_audit/verification/', import.meta.url);
const browser = await chromium.launch({ headless: true, channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1668, height: 1272 } });
const full = { proposal_id: 'browser-review-fixture', proposal_type: 'MODEL_UPDATE', revision: 'r1',
  status: 'VALIDATED', rationale: 'Browserprüfung: 3000 Änderungen', assumptions: [],
  validation_result: { valid: true }, canonical_ids: [],
  changes: Array.from({ length: 3000 }, (_, i) => ({ action: 'CREATE', object_type: 'Signal',
    local_ref: `signal-${i}`, data: { name: `ReviewSignal-${i}` } })) };
const reference = { ...full, content_state: 'REFERENCE', change_count: 3000, changes: [] };
const history = { updatedAt: Date.now(), messages: [{ id: 'review-fixture-message', role: 'assistant', parts: [
  { type: 'data-engineering', data: { id: 'review-fixture-event', type: 'APPROVAL',
    created_at: new Date().toISOString(), proposal: reference } },
] }] };
let failFull = false, fullReads = 0;
await page.route('**/api/agent/history?*', route => route.fulfill({ json: history }));
await page.route('**/api/engineering/agent/proposals/browser-review-fixture*', route => {
  assert.equal(route.request().method(), 'GET', 'Browser acceptance does not approve fixture data');
  if (route.request().url().includes('view=status')) return route.fulfill({ json: { success: true, data: {
    proposal_id: full.proposal_id, proposal_type: full.proposal_type, revision: full.revision,
    status: full.status, change_count: 3000, canonical_count: 0,
  } } });
  fullReads++;
  return route.fulfill({ status: failFull ? 503 : 200, json: failFull ? { error: 'Temporary fixture failure' } : { success: true, data: full } });
});
const report = { base, fixture_changes: 3000, checks: [] };
try {
  await page.goto(base + '/studio/agent?project=nis-correction-review', { waitUntil: 'domcontentloaded' });
  const open = page.getByRole('button', { name: 'AI Assistant öffnen', exact: true });
  await open.click();
  await page.getByText('3000 Änderungen', { exact: true }).waitFor({ timeout: 30000 });
  await page.getByText('Änderungen prüfen', { exact: true }).click();
  await page.getByText('ReviewSignal-0', { exact: true }).waitFor();
  for (let i = 1; i < 60; i++) {
    await page.getByRole('navigation', { name: 'Änderungen durchblättern' }).getByRole('button', { name: 'Weiter', exact: true }).click();
  }
  await page.getByText('ReviewSignal-2999', { exact: true }).waitFor();
  report.checks.push('All 3000 changes reachable through 60 real UI pages');
  await mkdir(output, { recursive: true });
  await page.screenshot({ path: new URL('2026-09-09-review-page60.png', output).pathname.replace(/^\/(.:)/, '$1') });
  const beforeReload = fullReads;
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.getByText('Änderungen prüfen', { exact: true }).waitFor();
  assert.ok(fullReads > beforeReload);
  report.checks.push('Reload resolves the same revision from canonical full proposal');
  failFull = true;
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.getByText('3000 Änderungen', { exact: true }).waitFor();
  await page.getByRole('alert').filter({ hasText: 'Temporary fixture failure' }).waitFor();
  const review = page.getByRole('region', { name: 'Engineering-Vorschlag' });
  const actions = review.getByRole('button').filter({ hasText: /Freigeben|Genehmigen|Übernehmen/i });
  assert.ok(await actions.count() > 0);
  for (const button of await actions.all()) assert.ok(await button.isDisabled());
  report.checks.push('Full proposal read failure disables every approval/apply action');
  await page.screenshot({ path: new URL('2026-09-09-review-read-failure.png', output).pathname.replace(/^\/(.:)/, '$1') });
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL'; report.error = String(error);
  await writeFile(new URL('2026-09-09-review-browser-failure.txt', output), await page.locator('body').innerText());
  throw error;
} finally {
  report.full_reads = fullReads;
  await writeFile(new URL('2026-09-09-review-browser.json', output), JSON.stringify(report, null, 2));
  await browser.close();
}
console.log(JSON.stringify(report));
