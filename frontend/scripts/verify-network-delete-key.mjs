import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {chromium} from 'playwright';

const {project} = JSON.parse(await fs.readFile('../backend/runtime/delete-key-test.json', 'utf8'));
assert.ok(project.startsWith('network-project-delete-key-test-'));
const api = async path => {
  const r = await fetch('http://127.0.0.1:15050/api/engineering' + path, {headers: {'X-Project-ID': project, Connection: 'close'}});
  assert.ok(r.ok, `${path}: ${r.status}`);
  return r.json();
};
const view = () => api('/workflow/network-view');
const browser = await chromium.launch({channel: 'chrome', headless: true});
const page = await browser.newPage({viewport: {width:1819, height:1272}});
page.setDefaultTimeout(25000);
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const saveResponse = () => page.waitForResponse(r => r.url().endsWith('/workflow/topology') && r.request().method() === 'PUT', {timeout: 90000});
try {
  const before = await view();
  const node = before.topology.nodes.find(n => n.name === 'Drehmomentkoordination');
  const edge = before.topology.edges.find(e => (e.source === node.id || e.target === node.id) && e.bus === 'can_fd');
  assert.ok(node && edge);
  await page.goto('http://127.0.0.1:13500/studio?mode=network&project=' + project);
  await page.locator('.net-editor.large-topology').waitFor();
  const nodeSelector = `.net-node[data-node-id="${node.id}"]`;
  async function positionNode(target = node) {
    await page.locator('.net-surface').evaluate((surface, n) => {surface.scrollLeft = Math.max(0, n.x - 550); surface.scrollTop = Math.max(0, n.y - 200);}, target);
    await page.locator(`.net-node[data-node-id="${target.id}"]`).waitFor({state:'visible'});
  }
  await positionNode();
  const branch = page.locator(`[data-connection-id="${edge.id}"][data-branch-node-id="${node.id}"] .net-wire-hit`);
  await branch.waitFor({state:'attached'});
  const point = await branch.evaluate(path => {
    const p = path.getPointAtLength(path.getTotalLength() * .65).matrixTransform(path.getScreenCTM());
    return {x: p.x, y:p.y};
  });
  await page.mouse.click(point.x, point.y);
  await page.locator(`[data-connection-id="${edge.id}"] .net-bus-branch.selected`).first().waitFor({state:'attached'});
  // A toolbar button has focus, while the connection remains selected.
  await page.getByRole('button', {name:'Vergrößern', exact:true}).focus();
  const reject = route => route.fulfill({status:409, contentType:'application/json', body:JSON.stringify({error:'Test: Projektstand veraltet'})});
  await page.route('**/workflow/topology', reject);
  await page.keyboard.press('Delete');
  await page.getByRole('alert').filter({hasText:'Löschung konnte nicht gespeichert'}).waitFor();
  assert.deepEqual((await view()).topology, before.topology);
  assert.ok(await page.locator(`[data-connection-id="${edge.id}"] .net-bus-branch.selected`).count());
  await page.unroute('**/workflow/topology', reject);
  let response = saveResponse();
  await page.keyboard.press('Delete');
  let saved = await response;
  assert.equal(saved.status(), 200, await saved.text());
  await page.getByRole('status').filter({hasText:'Verbindung aus der Netzwerktopologie gelöscht.'}).waitFor();
  let current = await view();
  assert.equal(current.topology.edges.length, before.topology.edges.length - 1);
  assert.ok(!current.topology.edges.some(e => e.id === edge.id));
  await page.reload();
  await page.locator('.net-editor.large-topology').waitFor();
  await positionNode(current.topology.nodes.find(n => n.id === node.id));
  assert.equal(await page.locator(`[data-connection-id="${edge.id}"]`).count(), 0);
  console.log('Connection: global Delete, failure retention, persisted removal and reload verified.');

  // Delete inside a text input or open dialog must not delete the selected device.
  await page.locator(nodeSelector).dblclick();
  const rename = page.getByRole('dialog', {name:'Gerät umbenennen'});
  const input = rename.locator('input');
  await input.fill('Temporary');
  await input.press('Home');
  await input.press('Delete');
  assert.equal(await input.inputValue(), 'emporary');
  assert.ok((await view()).topology.nodes.some(n => n.id === node.id));
  await rename.getByRole('button', {name:'Abbrechen'}).focus();
  await page.keyboard.press('Delete');
  assert.ok(await rename.isVisible());
  assert.ok((await view()).topology.nodes.some(n => n.id === node.id));
  await rename.getByRole('button', {name:'Abbrechen'}).click();
  await page.locator(nodeSelector).click();
  await page.getByRole('button', {name:'Vergrößern', exact:true}).focus();
  response = saveResponse();
  await page.keyboard.press('Delete');
  saved = await response;
  assert.equal(saved.status(), 200, await saved.text());
  await page.getByRole('status').filter({hasText:'aus der Netzwerktopologie entfernt.'}).waitFor();
  current = await view();
  assert.equal(current.topology.nodes.length, before.topology.nodes.length - 1);
  assert.ok(!current.topology.edges.some(e => e.source === node.id || e.target === node.id));
  await page.reload();
  await page.locator('.net-editor.large-topology').waitFor();
  assert.ok(!(await view()).topology.nodes.some(n => n.id === node.id));
  // The existing button's scope is topology deletion, not canonical object deletion.
  assert.equal((await api('/hardware-nodes/' + node.engineeringId)).id, node.engineeringId);
  assert.deepEqual(errors, []);
  await fs.writeFile('../backend/runtime/delete-key-browser-result.json', JSON.stringify({project, connection_deleted:edge.id, node_removed:node.id,
    toolbar_focus:true, text_field_protected:true, dialog_protected:true, failure_retained_selection:true, persisted_after_reload:true,
    canonical_hardware_preserved:true, page_errors:errors}, null, 2));
  console.log('PASS: Device Delete persisted, input/dialog protected, no dangling topology edges or page errors.');
} catch (error) {
  console.error(error);
  await page.screenshot({path:'../backend/runtime/delete-key-failure.png'});
  throw error;
} finally {
  await Promise.race([browser.close(), new Promise(resolve => setTimeout(resolve, 5000))]);
}
process.exit(0);
