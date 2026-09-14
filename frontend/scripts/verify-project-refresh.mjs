import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';
const project = 'network-project-20260910042736034-d11591d0';
const read = async path => {
  const response = await fetch('http://127.0.0.1:15050/api/engineering/' + path, { headers: { 'X-Project-ID': project } });
  assert.ok(response.ok); return response.json();
};
const before = await read('routing?limit=500');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1688, height: 1272 } });
page.setDefaultTimeout(20000);
const calls = [], errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => { if (request.url().endsWith('/workflow/refresh-project')) calls.push(request.headers()['x-project-id']); });
try {
  await page.goto(`http://127.0.0.1:13500/studio/capacity?project=${project}`);
  assert.equal(await page.getByRole('button', { name: 'Projektlink', exact: true }).count(), 0);
  const responsePromise = page.waitForResponse(response => response.url().endsWith('/workflow/refresh-project'), { timeout: 120000 });
  await page.getByRole('button', { name: 'Projekt aktualisieren', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Projekt aktualisieren', exact: true });
  await dialog.waitFor();
  assert.ok(await page.getByRole('button', { name: 'Projekt wird geprüft …' }).isDisabled());
  const response = await responsePromise;
  const report = await response.json();
  assert.ok(response.ok(), JSON.stringify(report));
  await dialog.getByText('NIS Projekt 1', { exact: true }).waitFor();
  assert.ok((await dialog.innerText()).includes(`${report.error_count} Fehler · ${report.warning_count} Warnungen`));
  assert.ok(report.error_count > 0);
  await dialog.locator('summary').filter({ hasText: /^Routing/ }).click();
  await page.screenshot({ path: '../backend/runtime/project-refresh.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  const bounds = await dialog.boundingBox();
  assert.ok(bounds.width <= 390 && bounds.height <= 844);
  const link = await dialog.getByRole('link', { name: 'Prüfbericht öffnen' }).getAttribute('href');
  assert.ok(link.includes('20260910042736034-d11591d0'));
  await page.screenshot({ path: '../backend/runtime/project-refresh-small.png' });
  assert.deepEqual(calls, [project]);
  assert.deepEqual((await read('routing?limit=500')).items, before.items);
  assert.deepEqual(errors, []);
  await fs.writeFile('../backend/runtime/project-refresh-ui.json', JSON.stringify({ passed: true, project, checkedRoutes: report.checked_routes, errors: report.error_count, warnings: report.warning_count, routeDefinitionsAndApprovalsUnchanged: true, smallViewport: true, browserErrors: errors }, null, 2));
} catch (error) {
  await page.screenshot({ path: '../backend/runtime/project-refresh-failure.png' }); console.error(error); process.exitCode = 1;
} finally {
  const session = await browser.newBrowserCDPSession();
  await Promise.race([session.send('Browser.close').catch(() => {}), new Promise(resolve => setTimeout(resolve, 2000))]);
  process.exit(process.exitCode ?? 0);
}
