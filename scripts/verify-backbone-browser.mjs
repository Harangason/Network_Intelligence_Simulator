import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1647, height: 1272 } });
const base = 'http://127.0.0.1:13500';
const project = 'network-project-20260909082213746-780a13ef';
const headers = { 'X-Project-ID': project };
const errors = [];
page.on('pageerror', error => errors.push(String(error)));
try {
  const routes = (await (await page.request.get(`${base}/api/engineering/routing?limit=500`, { headers })).json()).items;
  const route = routes.find(r => r.name === 'Abgasnachbehandlung → Motorsteuerung' && r.status === 'APPROVED');
  assert.ok(route);
  assert.equal(route.validation.valid, true);
  assert.equal(route.source.network_id, route.destinations[0].network_id);
  assert.equal(route.source.network_id, 'Antriebsstrang_01-S01');
  assert.equal(route.route.gateways.length, 0);
  await page.goto(`${base}/studio/routing?project=${project}`);
  await page.locator('.routing-main-panel').waitFor();
  const filters = page.locator('.routing-main-panel input');
  const textFilters = filters.filter({ visible: true });
  // The first table text field is the route-name filter.
  await page.locator('.routing-main-panel input:not([type=checkbox])').first().fill('Abgasnachbehandlung');
  await page.getByText('Abgasnachbehandlung → Motorsteuerung', { exact: true }).first().waitFor();
  await page.screenshot({ path: 'docs/implementation_audit/verification/2026-09-09-backbone-routing.png' });
  await page.goto(`${base}/studio?mode=network&project=${project}`);
  const node = page.locator('.net-node').filter({ has: page.locator('.net-node-name', { hasText: /^Motorsteuerung$/ }) });
  await node.waitFor({ timeout: 60000 });
  const port = node.getByRole('button', { name: /^Antrieb_36-Port/ });
  await port.waitFor();
  assert.match(await port.getAttribute('class'), /linked/);
  await node.scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'docs/implementation_audit/verification/2026-09-09-backbone-editor.png' });
  assert.deepEqual(errors, []);
  await writeFile('docs/implementation_audit/verification/2026-09-09-backbone-browser.json', JSON.stringify({ status: 'PASS', route: route.id, bus: 'Antrieb_36', gateway_required: false, motor_port_visible_and_linked: true, errors }, null, 2));
  console.log('PASS: direct route and linked motor backbone visible in browser');
} finally { await browser.close(); }
