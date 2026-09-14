import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-20260910042736034-d11591d0';
const get = async path => {
  const response = await fetch('http://127.0.0.1:15050/api/engineering/' + path, { headers: { 'X-Project-ID': project } });
  assert.ok(response.ok); return response.json();
};
const before = await get('workflow/network-view');
const routes = (await get('routing?limit=500')).items;
const route = routes.find(item => item.route_code === 'RT-29DE1132');
assert.ok(route, 'User route exists');
const destination = before.topology.nodes.find(node => node.engineeringId === route.destinations[0].node_id);
const frame = before.topology.scene.frames.find(frame => frame.memberIds.includes(destination.id));
assert.ok(frame);
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1688, height: 1272 } });
page.setDefaultTimeout(20000);
const errors = [], writes = [];
page.on('pageerror', error => errors.push(error.message));
await page.route('**/api/**', handler => {
  if (['GET', 'HEAD'].includes(handler.request().method())) return handler.continue();
  writes.push(handler.request().url());
  return handler.fulfill({ json: {} });
});
try {
  await page.goto(`http://127.0.0.1:13500/studio/routing?project=${project}&route=${route.id}`);
  await page.locator('.routing-detail-rail').waitFor();
  const rail = page.locator('.routing-detail-rail');
  if (await rail.count()) await rail.click();
  await page.getByRole('button', { name: 'Wizard', exact: true }).click();
  const dialog = page.locator('.routing-wizard-dialog');
  await dialog.locator('.routing-wizard-steps').getByRole('button', { name: /Ziele/ }).click();
  const preview = dialog.getByLabel('Systemrahmen des Empfängers');
  await preview.getByRole('img', { name: `Systemrahmen ${frame.label}, ausgewählt: ${destination.name}` }).waitFor();
  for (const member of before.topology.nodes.filter(node => frame.memberIds.includes(node.id))) {
    assert.ok((await preview.locator('li').allTextContents()).some(text => text.startsWith(member.name)));
  }
  await preview.getByText(`${destination.name} · Empfänger`, { exact: true }).waitFor();
  await preview.scrollIntoViewIfNeeded();
  await preview.screenshot({ path: '../backend/runtime/routing-system-frame.png' });
  await page.setViewportSize({ width: 640, height: 480 });
  await preview.scrollIntoViewIfNeeded();
  const body = await dialog.locator('.routing-wizard-body').evaluate(element => ({ width: element.clientWidth, scroll: element.scrollWidth }));
  assert.ok(body.scroll <= body.width + 1, JSON.stringify(body));
  await page.screenshot({ path: '../backend/runtime/routing-system-frame-small.png' });
  await dialog.locator('.routing-wizard-steps').getByRole('button', { name: /Payload/ }).click();
  await dialog.locator('.routing-wizard-steps').getByRole('button', { name: /Ziele/ }).click();
  await preview.waitFor();
  assert.deepEqual((await get('workflow/network-view')).topology, before.topology);
  assert.deepEqual((await get('routing?limit=500')).items, routes);
  assert.deepEqual(errors, []);
  await fs.writeFile('../backend/runtime/routing-system-frame-check.json', JSON.stringify({ passed: true, frame: frame.label, members: frame.memberIds.length, selected: destination.name, smallViewport: true, persistedDataUnchanged: true, errors, blockedWrites: writes }, null, 2));
} catch (error) {
  await page.screenshot({ path: '../backend/runtime/routing-system-frame-failure.png' });
  await fs.writeFile('../backend/runtime/routing-system-frame-failure.txt', String(error) + '\n' + JSON.stringify(errors) + '\n' + await page.locator('body').innerText());
  throw error;
} finally { await browser.close(); }
