import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const {project} = JSON.parse(await fs.readFile('../backend/runtime/port-menu-test.json', 'utf8'));
assert.ok(project.startsWith('network-project-port-menu-test-'), 'Only an isolated test project may be changed');
const base = 'http://127.0.0.1:13500';
const headers = {'X-Project-ID': project, Connection: 'close'};
const api = async path => {
  const response = await fetch(`http://127.0.0.1:15050/api/engineering${path}`, {headers});
  assert.ok(response.ok, `${path}: ${response.status}`);
  return response.json();
};
const browser = await chromium.launch({channel: 'chrome', headless: true});
const page = await browser.newPage({viewport: {width: 1819, height: 1272}});
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
  const before = await api('/workflow');
  const original = before.topology.nodes.find(n => n.name === 'Fahrerassistenz');
  assert.ok(original && before.topology.nodes.length > 48);
  const originalEdges = before.topology.edges.length;
  const selector = `.net-node[data-node-id="${original.id}"]`;
  await page.goto(`${base}/studio?mode=network&project=${project}`);
  await page.locator('.net-editor.large-topology').waitFor();
  async function selectDevice() {
    const current = (await api('/workflow')).topology.nodes.find(n => n.id === original.id);
    await page.locator('.net-surface').evaluate((surface, node) => {
      surface.scrollTop = Math.max(0, node.y - 120);
      surface.scrollLeft = Math.max(0, node.x - 120);
    }, current);
    await page.locator(selector).waitFor({state: 'visible'});
    await page.locator(selector).click({button: 'right', position: {x: 70, y: 40}});
    await page.getByRole('menu').filter({hasText: 'Port anlegen'}).waitFor();
  }
  // A failed canonical save must remain visible and must not add a local ghost port.
  await selectDevice();
  const rejectSave = route => route.fulfill({status: 409, contentType: 'application/json', body: JSON.stringify({error: 'Test: Projektstand veraltet'})});
  await page.route('**/api/engineering/workflow/topology', rejectSave);
  await page.getByRole('menuitem', {name: 'LIN', exact: true}).click();
  await page.getByRole('alert').filter({hasText: 'Port konnte nicht gespeichert'}).waitFor();
  assert.equal(await page.locator(`${selector} .net-port`).count(), original.ports.length);
  await page.unroute('**/api/engineering/workflow/topology', rejectSave);

  const added = [];
  for (const [label, bus] of [['LIN','lin'], ['CAN','can'], ['CAN FD','can_fd'], ['CAN-XL','can_xl'], ['Ethernet','automotive_ethernet'], ['FlexRay','flexray']]) {
    if (added.length) await selectDevice();
    const oldIds = new Set((await api('/workflow')).topology.nodes.find(n => n.id === original.id).ports.map(p => p.id));
    const savedResponse = page.waitForResponse(r => r.url().endsWith('/api/engineering/workflow/topology') && r.request().method() === 'PUT');
    await page.getByRole('menuitem', {name: label, exact: true}).click();
    const response = await savedResponse;
    assert.equal(response.status(), 200, await response.text());
    await page.getByRole('status').filter({hasText: `${label}-Port an „Fahrerassistenz“ gespeichert`}).waitFor();
    const state = await api('/workflow');
    const ports = state.topology.nodes.find(n => n.id === original.id).ports;
    const created = ports.filter(p => !oldIds.has(p.id));
    assert.equal(created.length, 1);
    assert.equal(created[0].bus, bus);
    assert.ok(created[0].hardwareInterfaceId);
    assert.deepEqual(state.topology.edges, before.topology.edges, 'Adding a port must preserve physical links and bus assignments');
    const port = page.locator(`${selector} [data-port-id="${created[0].id}"]`);
    await port.waitFor({state: 'visible'});
    const appearance = await port.evaluate(element => {
      const style = getComputedStyle(element);
      return {border: style.borderTopWidth, background: style.backgroundColor, containment: getComputedStyle(element.parentElement).contain};
    });
    assert.equal(appearance.border, '2px');
    assert.notEqual(appearance.background, 'rgba(0, 0, 0, 0)');
    assert.ok(!appearance.containment.includes('paint'), 'The card must not clip the outer half of its connectors');
    console.log('Verified', label);
    const physical = await api('/hardware-interfaces/' + created[0].hardwareInterfaceId);
    assert.equal(physical.hardware_node_id, original.engineeringId);
    added.push({bus, port: created[0], physical_id: physical.id});
  }
  await page.reload();
  await page.locator('.net-editor.large-topology').waitFor();
  await selectDevice();
  await page.keyboard.press('Escape');
  for (const {port} of added) {
    const handle = page.locator(`${selector} [data-port-id="${port.id}"]`);
    await handle.waitFor({state:'visible'});
    assert.ok(await handle.evaluate(element => {
      const rect = element.getBoundingClientRect();
      return document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2) === element;
    }), 'Every spare connector must be reachable without overlap');
  }
  // Deselecting the device must not hide spare connectors again.
  await page.locator('.net-surface').click({position:{x:10,y:10}});
  for (const {port} of added) await page.locator(`${selector} [data-port-id="${port.id}"]`).waitFor({state:'visible'});
  assert.equal(errors.length, 0, errors.join('\n'));
  await page.screenshot({path:'../backend/runtime/port-menu-verified.png'});
  await fs.writeFile('../backend/runtime/port-menu-browser-result.json', JSON.stringify({project, verified_bus_types:added.map(p=>p.bus), persisted_ports:added.length, save_failure_preserved_state:true, reload_preserved_ports:true, original_edges:originalEdges, page_errors:errors},null,2));
  console.log('PASS', project, '6 bus types: visible, canonically saved, reload stable; failed save and unchanged connections checked.');
} finally {
  await browser.close();
}
