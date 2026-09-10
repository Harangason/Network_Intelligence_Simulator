import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-20260910042736034-d11591d0';
const networkId = 'network-automotive_ethernet-7537dce901cb';
async function api(path) {
  const response = await fetch('http://127.0.0.1:15050/api/engineering' + path, { headers: { 'X-Project-ID': project } });
  assert.ok(response.ok, `${path}: ${response.status}`);
  return response.json();
}
const state = await api('/workflow');
const routes = (await api('/routing?limit=500')).items;
const expected = state.parameters.networks.find(network => network.id === networkId)?.name;
assert.ok(expected && expected !== networkId);
const route = routes.find(item => item.source.network_id === networkId);
assert.ok(route, 'The reported network must have a route');
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1835, height: 1272 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
let failed = false;
try {
  await page.goto(`http://127.0.0.1:13500/studio/routing?project=${project}&route=${route.id}`);
  await page.locator('.routing-detail-rail').filter({ hasText: route.route_code }).waitFor();
  const filter = page.getByRole('searchbox', { name: 'Network filtern', exact: true });
  await filter.fill(expected);
  const networkCells = page.locator('.routing-table tbody tr td:nth-child(8)');
  await networkCells.filter({ hasText: expected }).first().waitFor();
  const labels = await networkCells.allTextContents();
  assert.ok(labels.length > 0);
  assert.ok(labels.every(label => label === expected), JSON.stringify(labels));
  // The technical ID remains inspectable, but is no longer the displayed name.
  assert.equal(await networkCells.first().getAttribute('title'), networkId);
  await page.locator('.routing-detail-rail').click();
  const details = page.locator('.routing-detail-body dt').filter({ hasText: /^Network$/ }).locator('+ dd');
  await details.waitFor();
  const detailLabel = await details.innerText();
  assert.ok(detailLabel.includes(expected), detailLabel);
  assert.ok(!detailLabel.includes(networkId), detailLabel);
  await page.screenshot({ path: '../backend/runtime/routing-network-labels-table.png' });
  await filter.fill('no-matching-network-name-verified');
  await page.waitForFunction(() => document.querySelectorAll('.routing-table tbody tr').length === 0);
  await filter.fill('');
  await networkCells.first().waitFor();
  const restoredRows = await networkCells.count();
  assert.ok(restoredRows >= labels.length);
  await page.getByRole('tab', { name: 'Matrix', exact: true }).click();
  await page.getByRole('searchbox', { name: 'Matrix durchsuchen', exact: true }).fill(expected);
  const matrixCells = page.locator('.routing-matrix-cell-button').filter({ hasText: expected });
  await matrixCells.first().waitFor();
  const matrixLabels = await matrixCells.allTextContents();
  const matrixTitles = await matrixCells.evaluateAll(elements => elements.map(element => element.title));
  assert.ok(matrixTitles.every(title => title.includes(expected) && !title.includes(networkId)));
  await page.screenshot({ path: '../backend/runtime/routing-network-labels-matrix.png' });
  await page.reload();
  await page.locator('.routing-detail-rail').filter({ hasText: route.route_code }).waitFor();
  await page.getByRole('searchbox', { name: 'Network filtern', exact: true }).fill(expected);
  await page.locator('.routing-table tbody tr td:nth-child(8)').filter({ hasText: expected }).first().waitFor();
  const after = await api('/workflow');
  assert.deepEqual(after.parameters, state.parameters);
  assert.deepEqual(after.topology, state.topology);
  assert.deepEqual((await api('/routing?limit=500')).items, routes);
  assert.deepEqual(errors, []);
  const evidence = { project, networkId, expected, route: route.id, labels, detailLabel, restoredRows, matrixLabels, matrixTitles, reloadVerified: true, modelUnchanged: true, errors };
  await fs.writeFile('../backend/runtime/routing-network-labels-verified.json', JSON.stringify(evidence, null, 2));
  console.log('PASS routing table, filter, details, matrix search and reload:', expected);
} catch (error) {
  failed = true;
  console.error(error);
  await page.screenshot({ path: '../backend/runtime/routing-network-labels-failure.png' });
} finally {
  const cdp = await browser.newBrowserCDPSession();
  await Promise.race([cdp.send('Browser.close').catch(() => {}), new Promise(resolve => setTimeout(resolve, 2000))]);
  process.exit(failed ? 1 : 0);
}
