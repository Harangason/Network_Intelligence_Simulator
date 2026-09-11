import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';
import { communicationWarnings } from '../src/lib/communication-warnings.ts';

const project = 'network-project-20260910042736034-d11591d0';
const resources = ['hardware-nodes', 'hardware-interfaces', 'functions', 'interfaces', 'messages', 'signals'];
async function api(path) {
  const response = await fetch('http://127.0.0.1:15050/api/engineering' + path, { headers: { 'X-Project-ID': project } });
  assert.ok(response.ok, `${path}: ${response.status}`);
  return response.json();
}
async function all(resource) {
  const items = [];
  for (let offset = 0; ; offset += 500) {
    const page = await api(`/${resource}?limit=500&offset=${offset}`);
    items.push(...page.items);
    if (page.items.length < 500) return items;
  }
}
const [groups, routes, view, parameters] = await Promise.all([
  Promise.all(resources.map(all)), all('routing'), api('/workflow/network-view'), api('/workflow/parameters'),
]);
const objects = groups.flat();
const warnings = communicationWarnings(objects, routes, parameters.parameters.networks, view.topology);
const message = objects.find(item => item.id === '7712a7b0-ec11-4af8-88d7-e3221925c495');
const signal = objects.find(item => item.message_id === message.id);
const iface = objects.find(item => item.id === message.interface_id);
const fn = objects.find(item => item.id === iface.function_id);
const port = objects.find(item => item.id === message.hardware_interface_id);
const hardware = objects.find(item => item.id === fn.hardware_node_id);
assert.ok(warnings.has(message.id), 'The reported disconnected camera message must be detected');
const targets = [hardware, port, fn, iface, message, signal];
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1371, height: 1272 } });
const errors = [];
page.on('pageerror', error => errors.push(error.message));
let failed = false;
try {
  for (let i = 0; i < resources.length; i++) {
    const resource = resources[i], item = targets[i];
    await page.goto(`http://127.0.0.1:13500/studio/engineering?project=${project}&resource=${resource}&object=${item.id}`);
    const table = page.locator(`table.eng-table.${resource}`);
    await table.locator('tbody tr.selected').waitFor();
    const headers = await table.locator('thead tr').first().locator('th button').allTextContents();
    assert.match(headers.at(-2), /Beschreibung/);
    assert.match(headers.at(-1), /Warnung/);
    const row = table.locator('tbody tr.selected');
    await row.getByRole('button', { name: `Kommunikationswarnungen für ${item.name}`, exact: true }).click();
    const dialog = page.getByRole('dialog', { name: `Kommunikationswarnungen: ${item.name}`, exact: true });
    await dialog.waitFor();
    assert.match(await dialog.innerText(), /keinem Bus zugeordnet/);
    assert.match(await dialog.innerText(), /Betroffen:.*Buszuordnung/);
    if (resource === 'signals') {
      assert.match(await dialog.innerText(), /RT-D81ECD53/);
      await page.screenshot({ path: '../backend/runtime/communication-warning-detail.png' });
    }
    await page.keyboard.press('Escape');
    await dialog.waitFor({ state: 'hidden' });
    await table.getByRole('searchbox', { name: 'Warnung filtern', exact: true }).fill('keinem Bus zugeordnet');
    await table.locator('tbody tr.eng-object-surface').first().waitFor();
    const triangles = table.locator('tbody tr.eng-object-surface .eng-communication-warning');
    assert.equal(await triangles.count(), await table.locator('tbody tr.eng-object-surface').count());
    if (resource === 'signals') {
      await table.getByRole('searchbox', { name: 'Name filtern', exact: true }).fill('Kameraverarbeitung');
      await page.screenshot({ path: '../backend/runtime/communication-warning-signals.png' });
    }
    console.log(`PASS ${resource}: column order, triangle, explanation and filtering`);
  }
  // A healthy neighboring message must remain unmarked.
  const healthy = groups[4].find(item => !warnings.has(item.id));
  assert.ok(healthy);
  await page.goto(`http://127.0.0.1:13500/studio/engineering?project=${project}&resource=messages&object=${healthy.id}`);
  const healthyRow = page.locator('table.eng-table.messages tbody tr.selected');
  await healthyRow.waitFor();
  assert.equal(await healthyRow.locator('.eng-communication-warning').count(), 0);
  await page.getByRole('tab', { name: 'Structure Tree', exact: true }).click();
  await page.locator('.structure-tree-root').waitFor();
  await page.getByRole('searchbox', { name: 'Baum filtern' }).fill(signal.name);
  const marker = page.locator('.structure-tree-root').getByRole('button', { name: `Kommunikationswarnungen für ${signal.name}`, exact: true });
  await marker.waitFor();
  await marker.click();
  const treeDialog = page.getByRole('dialog', { name: `Kommunikationswarnungen: ${signal.name}`, exact: true });
  assert.match(await treeDialog.innerText(), /RT-D81ECD53/);
  await treeDialog.getByRole('button', { name: 'Warnungen schließen' }).click();
  await page.screenshot({ path: '../backend/runtime/communication-warning-tree.png' });
  const cameraRows = page.locator('.structure-tree-row').filter({ hasText: 'Kameraverarbeitung' });
  assert.ok(await cameraRows.count() >= 5, 'signal, message, interface, function and hardware remain visible');
  for (const row of await cameraRows.all()) assert.ok(await row.locator('.eng-communication-warning').count() > 0);
  assert.deepEqual((await api('/workflow/network-view')).topology, view.topology);
  assert.deepEqual((await api('/workflow/parameters')).parameters, parameters.parameters);
  assert.deepEqual(await all('routing'), routes);
  assert.deepEqual(await Promise.all(resources.map(all)), groups);
  assert.deepEqual(errors, []);
  const evidence = { project, warningsByResource: groups.map((group, i) => ({ resource: resources[i], affected: group.filter(item => warnings.has(item.id)).length })), verified: targets.map(item => ({ id: item.id, name: item.name })), modelUnchanged: true, errors };
  await fs.writeFile('../backend/runtime/communication-warnings-verified.json', JSON.stringify(evidence, null, 2));
  console.log('PASS structure tree propagation, healthy neighbor and unchanged model');
} catch (error) {
  failed = true;
  console.error(error);
  await page.screenshot({ path: '../backend/runtime/communication-warnings-failure.png' });
} finally {
  const cdp = await browser.newBrowserCDPSession();
  await Promise.race([cdp.send('Browser.close').catch(() => {}), new Promise(resolve => setTimeout(resolve, 2000))]);
  process.exit(failed ? 1 : 0);
}
