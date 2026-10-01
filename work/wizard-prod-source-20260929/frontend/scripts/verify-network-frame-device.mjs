import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const {project} = JSON.parse(await fs.readFile('../backend/runtime/frame-create-test.json', 'utf8'));
assert.ok(project.startsWith('network-project-frame-create-test-'));
const api = async path => {
  const response = await fetch('http://127.0.0.1:15050/api/engineering' + path, {headers: {'X-Project-ID': project, Connection: 'close'}});
  assert.ok(response.ok, `${path}: ${response.status}`);
  return response.json();
};
const browser = await chromium.launch({channel: 'chrome', headless: true});
const page = await browser.newPage({viewport: {width: 1819, height: 1272}});
page.setDefaultTimeout(20000);
const errors = [];
page.on('pageerror', error => errors.push(error.message));
try {
  const before = await api('/workflow/network-view');
  const owner = before.topology.nodes.find(n => n.name === 'Fahrerassistenz');
  assert.ok(owner);
  const handle = page.getByRole('button', {name: 'Systemrahmen Fahrerassistenz verschieben', exact: true});
  const dialog = page.getByRole('dialog', {name: 'Gerät hinzufügen', exact: true});
  async function positionFrame() {
    const state = await api('/workflow/network-view');
    const frame = state.topology.scene.frames.find(f => f.id === owner.id);
    await page.locator('.net-surface').evaluate((surface, frame) => {
      surface.scrollTop = frame.top - 80;
      surface.scrollLeft = frame.left - 60;
    }, frame);
    await handle.waitFor({state: 'visible'});
  }
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);
  await page.locator('.net-editor.large-topology').waitFor();
  await positionFrame();
  await handle.dblclick();
  await dialog.waitFor();
  await page.screenshot({path: '../backend/runtime/frame-create-dialog.png'});
  for (const label of ['+ ECU', '+ Sensor', '+ Aktor']) assert.ok(await dialog.getByRole('button', {name: label, exact: true}).isVisible());
  await page.keyboard.press('Escape');
  await dialog.waitFor({state: 'hidden'});
  assert.deepEqual((await api('/workflow/network-view')).topology, before.topology, 'Doppelklick/Abbrechen verändert kein Layout');

  // The same handle still moves its whole system frame.
  const box = await handle.boundingBox();
  const savedLayout = page.waitForResponse(r => r.url().endsWith('/workflow/network-view') && r.request().method() === 'PUT');
  await page.mouse.move(box.x + 20, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + 70, box.y + box.height / 2 + 30, {steps: 10});
  await page.mouse.up();
  assert.equal((await savedLayout).status(), 200);
  await positionFrame();
  const moved = (await api('/workflow/network-view')).topology.nodes.find(n => n.id === owner.id);
  assert.ok(moved.x > owner.x && moved.y > owner.y);

  // Failed save keeps the dialog and input, without adding a ghost device.
  await handle.dblclick();
  await dialog.getByLabel('Gerätename').fill('FrameTestSensor');
  const reject = route => route.fulfill({status: 409, contentType: 'application/json', body: JSON.stringify({error: 'Test: Projektstand veraltet'})});
  await page.route('**/workflow/frame-device', reject);
  await dialog.getByRole('button', {name: 'Gerät anlegen', exact: true}).click();
  await dialog.getByRole('alert').waitFor();
  assert.equal((await api('/workflow/network-view')).topology.nodes.length, before.topology.nodes.length);
  assert.equal(await dialog.getByLabel('Gerätename').inputValue(), 'FrameTestSensor');
  await page.unroute('**/workflow/frame-device', reject);
  const added = [];
  for (const [label, kind, name] of [['Sensor', 'sensor', 'ZusatzTemperaturmessung'], ['ECU', 'ecu', 'ZusatzSignalverarbeitung'], ['Aktor', 'actuator', 'ZusatzVentil']]) {
    if (added.length) {await positionFrame(); await handle.dblclick();}
    await dialog.getByRole('button', {name: '+ ' + label, exact: true}).click();
    await dialog.getByLabel('Gerätename').fill(name);
    const response = page.waitForResponse(r => r.url().endsWith('/workflow/frame-device') && r.request().method() === 'POST');
    await dialog.getByRole('button', {name: 'Gerät anlegen', exact: true}).click();
    const result = await response;
    assert.equal(result.status(), 201, await result.text());
    const state = await result.json();
    await dialog.waitFor({state: 'hidden'});
    const node = state.created_device;
    assert.equal(node.kind, kind);
    assert.equal(node.systemOwnerId, owner.engineeringId);
    assert.ok(state.topology.scene.frames.find(f => f.id === owner.id).memberIds.includes(node.id));
    assert.deepEqual(state.topology.edges, before.topology.edges);
    const hardware = await api('/hardware-nodes/' + node.engineeringId);
    assert.equal(hardware.identity.system_owner_id, owner.engineeringId);
    added.push(node);
    console.log('Verified', label, node.id);
  }
  await page.reload();
  await page.locator('.net-editor.large-topology').waitFor();
  await positionFrame();
  const final = await api('/workflow/network-view');
  const frame = final.topology.scene.frames.find(f => f.id === owner.id);
  for (const node of added) assert.ok(frame.memberIds.includes(node.id));
  assert.equal(final.topology.nodes.length, before.topology.nodes.length + 3);
  assert.equal(final.topology.scene.frames.length, before.topology.scene.frames.length);
  await page.screenshot({path: '../backend/runtime/frame-create-verified.png'});
  assert.deepEqual(errors, []);
  await fs.writeFile('../backend/runtime/frame-create-browser-result.json', JSON.stringify({project, added, cancelled_unchanged:true, drag_preserved:true, failure_kept_input:true, reload_membership:true, page_errors:errors}, null, 2));
  console.log('PASS: all three kinds saved in target frame; drag, cancel, save failure and reload verified.');
} catch (error) {
  await page.screenshot({path: '../backend/runtime/frame-create-failure.png'});
  console.log(await dialogText(page));
  throw error;
} finally {
  await browser.close();
}
process.exit(0);

async function dialogText(page) {
  return page.locator('dialog').allTextContents();
}
