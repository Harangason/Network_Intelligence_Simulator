import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-20260910042736034-d11591d0';
const read = async () => {
  const response = await fetch('http://127.0.0.1:15050/api/engineering/workflow/network-view', { headers: { 'X-Project-ID': project } });
  assert.ok(response.ok); return response.json();
};
const before = await read();
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1688, height: 1272 } });
page.setDefaultTimeout(25000);
const errors = [], writes = [], checks = [];
let failed = false;
page.on('pageerror', error => errors.push(error.message));
// Search must never save, generate, delete or move topology data.
await page.route('**/api/engineering/**', async handler => {
  const request = handler.request(), path = new URL(request.url()).pathname;
  if (!['GET', 'HEAD'].includes(request.method()) && !path.endsWith('/workflow/context')) {
    writes.push({ method: request.method(), path });
    return handler.fulfill({ status: 409, json: { error: 'Search verification blocks model writes.' } });
  }
  return handler.continue();
});
const search = () => page.getByRole('combobox', { name: 'Netzwerk durchsuchen' });
const options = () => page.getByRole('listbox', { name: 'Netzwerktreffer' });
const nodeElement = node => page.locator(`.net-node[data-node-id="${node.id}"]`);
const select = async (name, kind, id) => {
  await search().click();
  await search().fill(name);
  await options().locator(`[data-search-kind="${kind}"][data-search-id="${id}"]`).click();
};
const visibleCenter = async locator => {
  await locator.waitFor({ state: 'visible' });
  await page.waitForFunction(element => {
    if (!element) return false;
    const r = element.getBoundingClientRect();
    const surface = document.querySelector('.net-surface').getBoundingClientRect();
    const x = r.x + r.width / 2, y = r.y + r.height / 2;
    return x >= Math.max(0, surface.left) && x <= Math.min(innerWidth, surface.right)
      && y >= Math.max(0, surface.top) && y <= Math.min(innerHeight, surface.bottom);
  }, await locator.elementHandle());
};
try {
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);
  await search().waitFor();
  const rendered = await page.locator('.net-node').evaluateAll(nodes => nodes.map(node => node.dataset.nodeId));
  const far = before.topology.nodes.filter(node => !rendered.includes(node.id) && node.kind !== 'gateway')
    .sort((a, b) => b.x + b.y - a.x - a.y)[0];
  assert.ok(far, 'Live project has a node outside the virtualized viewport');
  await select(far.name, 'node', far.id);
  await nodeElement(far).filter({ has: page.locator('.net-node-name') }).waitFor();
  assert.match(await nodeElement(far).getAttribute('class'), /selected/);
  await visibleCenter(nodeElement(far));
  assert.equal(await options().count(), 0);
  await search().fill('ETH');
  await page.screenshot({ path: '../backend/runtime/network-search-results.png' });
  const pageY = await page.evaluate(() => window.scrollY);
  for (let i = 0; i < 12; i++) await search().press('ArrowDown');
  assert.ok(await options().evaluate(list => list.scrollTop) > 0, 'Arrow keys reveal results inside the list');
  assert.equal(await page.evaluate(() => window.scrollY), pageY, 'Navigating results must not scroll the page');
  const activeId = await search().getAttribute('aria-activedescendant');
  const chosen = await page.locator(`[id="${activeId}"]`).getAttribute('data-search-id');
  const chosenKind = await page.locator(`[id="${activeId}"]`).getAttribute('data-search-kind');
  await search().press('Enter');
  if (chosenKind === 'node') await visibleCenter(nodeElement({ id: chosen }));
  else await page.locator(`.net-physical-bus.selected[data-physical-network-id="${chosen}"]`).waitFor({ state: 'attached' });
  checks.push('Complete topology search finds and centers an initially unrendered node; keyboard navigation scrolls results only; Enter selects without saving');

  const bus = before.topology.scene.buses.find(bus => bus.name.startsWith('ETH_'));
  assert.ok(bus);
  await select(bus.name, 'bus', bus.id);
  await page.locator(`.net-physical-bus.selected[data-physical-network-id="${bus.id}"]`).waitFor({ state: 'attached' });
  const portNode = before.topology.nodes.find(node => node.kind !== 'gateway' && node.ports.some(port => port.name));
  await select(portNode.ports.find(port => port.name).name, 'node', portNode.id);
  await visibleCenter(nodeElement(portNode));
  await search().press('Home'); await search().press('Delete');
  await search().fill('definitely-no-network-result');
  assert.match(await page.locator('.net-search-popover [role="status"]').innerText(), /Keine Treffer/);
  await search().press('Enter');
  assert.equal(await page.getByRole('dialog').count(), 0);
  await search().press('Escape'); assert.equal(await options().count(), 0);
  await page.getByRole('button', { name: 'Netzwerksuche leeren' }).click(); assert.equal(await search().inputValue(), '');
  checks.push('Canonical bus names and port names are searchable; typing Delete and Enter in an empty result never mutates the model; Escape and clear work');

  await search().fill(far.name); await search().press('Escape');
  await page.getByRole('button', { name: 'Verkleinern', exact: true }).click();
  await page.getByRole('button', { name: 'Verkleinern', exact: true }).click();
  await search().click(); await search().press('Enter'); await visibleCenter(nodeElement(far));
  await page.getByRole('button', { name: 'Vollbild', exact: true }).click();
  await page.locator('.net-editor.fullscreen').waitFor();
  assert.equal(await search().inputValue(), far.name);
  await search().click(); await search().press('Escape');
  assert.equal(await page.locator('.net-editor.fullscreen').count(), 1, 'Search Escape must not close fullscreen');
  for (const size of [{ width: 1366, height: 768 }, { width: 640, height: 480 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(size);
    await select(far.name, 'node', far.id); await visibleCenter(nodeElement(far));
    await search().fill('ETH');
    const bounds = await page.locator('.net-search-popover').boundingBox();
    assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= size.width + 1, 'Search stays inside the viewport');
    assert.ok(bounds.y + Math.min(bounds.height, 80) < size.height, 'Results remain reachable');
    await page.screenshot({ path: `../backend/runtime/network-search-${size.width}.png` });
    await search().press('Escape');
  }
  checks.push('Centering works at 80% and fullscreen; search survives fullscreen switching and stays usable on 1366×768, 640×480 and 390×844');
  assert.deepEqual(writes, []); assert.deepEqual(errors, []);
  const after = await read();
  assert.deepEqual(after.topology, before.topology);
  const result = { status: 'passed', project, checks, errors, modelWrites: writes, topologyUnchanged: true };
  await fs.writeFile('../backend/runtime/network-search-browser.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} catch (error) { failed = true; console.error(error); await page.screenshot({ path: '../backend/runtime/network-search-failure.png' }); }
finally {
  const cdp = await page.context().newCDPSession(page);
  await Promise.race([cdp.send('Browser.close').catch(() => {}), new Promise(resolve => setTimeout(resolve, 1500))]);
  process.exit(failed ? 1 : 0);
}
