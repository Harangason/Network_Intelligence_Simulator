import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-20260910042736034-d11591d0';
const base = 'http://127.0.0.1:13500';
const read = async () => {
  const r = await fetch('http://127.0.0.1:15050/api/engineering/routing?limit=500', { headers: { 'X-Project-ID': project } });
  assert.ok(r.ok); return (await r.json()).items;
};
const before = await read();
const route = before.find(r => r.route_code === 'RT-E70EFC34'); assert.ok(route);
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1688, height: 1272 } });
page.setDefaultTimeout(10000);
const writes = [], errors = [], checks = [];
page.on('pageerror', e => errors.push(e.message));
// Exercise the real UI save path while keeping all project mutations in this test browser.
await page.route('**/api/engineering/routing/**', async handler => {
  const request = handler.request();
  if (['GET', 'HEAD'].includes(request.method())) return handler.continue();
  writes.push({ method: request.method(), path: new URL(request.url()).pathname, body: request.postDataJSON() });
  await new Promise(resolve => setTimeout(resolve, 250));
  await handler.fulfill({ json: { ...route, revision: route.revision + 1 } });
});
const dialog = page.locator('.routing-wizard-dialog');
const step = name => dialog.locator('.routing-wizard-steps').getByRole('button', { name: new RegExp(name, 'i') });
let failed = false;
try {
  await page.goto(`${base}/studio/routing?project=${project}&route=${route.id}`);
  await page.locator('.routing-detail').filter({ hasText: route.route_code }).waitFor();
  const rail = page.locator('.routing-detail-rail'); if (await rail.count()) await rail.click();
  await page.getByRole('button', { name: 'Wizard', exact: true }).click();
  await step('Timing').click();
  await dialog.getByRole('button', { name: 'Weiter', exact: true }).click();
  await page.waitForTimeout(500);
  assert.equal(writes.length, 0, 'Entering review through Weiter must not save');
  assert.ok(await dialog.locator('.routing-wizard-review').isVisible());
  checks.push('Single click on Weiter opens review without a write');
  await dialog.getByRole('button', { name: 'Zurück', exact: true }).click();
  await dialog.getByRole('button', { name: 'Weiter', exact: true }).dblclick();
  await page.waitForTimeout(350);
  assert.equal(writes.length, 0, 'Double-clicking Weiter must not become a save click');
  assert.ok(await dialog.locator('.routing-wizard-review').isVisible());
  checks.push('Double click on Weiter leaves the review open');
  await step('Timing').click();
  await dialog.locator('input[type=number]').first().press('Enter');
  await page.waitForTimeout(350); assert.equal(writes.length, 0, 'Enter in an input must not save');
  await step('Prüfen').click();
  await page.waitForTimeout(1200); assert.equal(writes.length, 0);
  assert.ok(await dialog.locator('.routing-wizard-review').isVisible());
  checks.push('Enter in timing and direct review-tab navigation do not save');
  await page.screenshot({ path: '../backend/runtime/routing-review-save.png' });
  const save = dialog.getByRole('button', { name: 'Speichern & validieren', exact: true });
  assert.ok(await save.isEnabled(), 'Fixture must have all required fields to exercise saving');
  await save.dblclick();
  await dialog.waitFor({ state: 'hidden' });
  assert.deepEqual(writes.map(w => w.method), ['PATCH', 'POST']);
  assert.equal(writes[0].path, `/api/engineering/routing/${route.id}`);
  assert.equal(writes[0].body.expected_revision, route.revision);
  assert.equal(writes[1].path, `/api/engineering/routing/${route.id}/validate`);
  assert.deepEqual(errors, []);
  assert.deepEqual(await read(), before);
  checks.push('Explicit save runs update and validation exactly once; live routes unchanged');
  const result = { status: 'passed', checks, pageErrors: errors, writesIntercepted: writes.length, liveRoutesUnchanged: true };
  await fs.writeFile('../backend/runtime/routing-review-save-browser.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} catch (e) {
  failed = true; console.error(e); console.error(JSON.stringify({ writes: writes.map(w => ({ method: w.method, path: w.path })), errors }));
  await page.screenshot({ path: '../backend/runtime/routing-review-save-failure.png' });
} finally {
  const cdp = await page.context().newCDPSession(page);
  await Promise.race([cdp.send('Browser.close').catch(() => {}), new Promise(resolve => setTimeout(resolve, 1500))]);
  process.exit(failed ? 1 : 0);
}
