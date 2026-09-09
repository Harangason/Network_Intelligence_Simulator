import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const base = process.env.NIS_RELEASE_URL ?? 'http://127.0.0.1:13500';
const project = '20260909082213746-780a13ef';
const output = new URL('../docs/implementation_audit/verification/', import.meta.url);
const manifest = JSON.parse(await readFile(new URL('../backend/app/build-info.json', import.meta.url), 'utf8'));
const migration = JSON.parse(await readFile(new URL('2026-09-09-live-route-migration.json', output), 'utf8'));
const browser = await chromium.launch({ headless: true, channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1668, height: 1272 } });
const report = { base, project, build_id: manifest.build_id, checks: [], page_errors: [] };
page.on('pageerror', error => report.page_errors.push(String(error)));
const screenshot = name => page.screenshot({ path: fileURLToPath(new URL(name, output)) });
try {
  await page.goto(`${base}/studio/engineering?project=${project}&resource=signals`, { waitUntil: 'domcontentloaded' });
  await page.locator('table.eng-table.signals thead input').nth(3).fill('AGRVentilstellung');
  const row = page.locator('table.eng-table.signals tbody tr').filter({ hasText: 'AGRVentilstellung' });
  await row.waitFor({ timeout: 30000 });
  assert.match(await row.innerText(), /Abgasnachbehandlung/);
  assert.match(await row.innerText(), /EGRValvePosition/);
  assert.match(await row.innerText(), /keine eigene Funktion erforderlich/);
  report.checks.push('AGRVentilstellung has system, source hardware and an explained optional function');
  await row.scrollIntoViewIfNeeded();
  await screenshot('2026-09-09-live-corrected-signals.png');

  await page.locator('.eng-structure-tree-tab').click();
  await page.getByPlaceholder('Name, Typ oder Wert', { exact: true }).fill('agr');
  await page.locator('.structure-tree-root').getByText('AGRVentilstellung', { exact: true }).waitFor();
  assert.equal(await page.locator('.structure-orphans').filter({ hasText: 'AGRVentilstellung' }).count(), 0);
  report.checks.push('Canonical tree keeps the direct hardware interface under its valid device');
  await page.getByRole('button', { name: 'Systemrahmen', exact: true }).click();
  await page.locator('.structure-tree-root').getByText('Systemrahmen Abgasnachbehandlung', { exact: true }).waitFor();
  await page.locator('.structure-tree-root').getByText('AGRVentilstellung', { exact: true }).waitFor();
  await screenshot('2026-09-09-live-corrected-system-owner.png');
  report.checks.push('System frame uses the confirmed Abgasnachbehandlung ownership');

  await page.goto(`${base}/studio/validation?project=${project}`, { waitUntil: 'domcontentloaded' });
  const gap = page.locator('.findings-list .finding').filter({ hasText: '47 Nachrichten und 235 Signale' });
  await gap.waitFor({ timeout: 30000 });
  await gap.click();
  const dialog = page.getByRole('dialog');
  await dialog.getByText('Nachrichten ohne ausführbaren Transport (47)', { exact: true }).waitFor();
  assert.equal(await dialog.locator('details').first().getByRole('link').count(), 47);
  assert.equal(await dialog.locator('details').nth(1).locator('a').count(), 235);
  for (const message of migration.unconfirmed_messages) {
    const link = dialog.getByRole('link', { name: message.name, exact: true });
    assert.equal(await link.count(), 1);
    assert.ok((await link.getAttribute('href')).includes(encodeURIComponent(message.message_id)));
  }
  await screenshot('2026-09-09-live-unconfirmed-messages.png');
  report.checks.push('Preflight blocks incomplete ALL coverage and links all 47 messages and 235 signals');

  await page.getByRole('button', { name: 'Dialog schließen', exact: true }).click();
  await page.locator('.system-state').getByText(manifest.build_id, { exact: false }).waitFor();
  assert.doesNotMatch(await page.locator('.system-state').innerText(), /Build-Abweichung/);
  await page.route('**/api/build-info', route => route.fulfill({ json: { build_id: 'different-server-build' } }));
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.locator('.system-state').getByText('Build-Abweichung', { exact: false }).waitFor();
  await page.unroute('**/api/build-info');
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.locator('.system-state').getByText(manifest.build_id, { exact: false }).waitFor();
  report.checks.push('Compiled frontend build matches the backend and detects a different server build');
  assert.deepEqual(report.page_errors, []);
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL'; report.error = String(error);
  await writeFile(new URL('2026-09-09-live-browser-failure.txt', output), await page.locator('body').innerText());
  await screenshot('2026-09-09-live-browser-failure.png');
  throw error;
} finally {
  await writeFile(new URL('2026-09-09-live-browser.json', output), JSON.stringify(report, null, 2));
  await browser.close();
}
console.log(JSON.stringify(report));
