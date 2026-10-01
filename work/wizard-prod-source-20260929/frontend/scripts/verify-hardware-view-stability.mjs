import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';
import { buildHardwareGraph } from '../src/lib/hardware-graph.ts';

const project = 'network-project-20260910042736034-d11591d0';
const api = async path => {
  const response = await fetch(`http://127.0.0.1:15050/api/engineering${path}`, { headers: { 'X-Project-ID': project } });
  assert.ok(response.ok, path); return response.json();
};
const all = async path => {
  const items = [];
  for (let offset = 0; ; offset += 500) {
    const page = await api(`${path}?limit=500&offset=${offset}`);
    items.push(...page.items); if (page.items.length < 500) return items;
  }
};
const [before, routes, functions, interfaces, relations] = await Promise.all([
  api('/workflow/network-view'), all('/routing'), all('/functions'), all('/interfaces'), all('/relations'),
]);
const graph = buildHardwareGraph(before.topology, functions, 'hardware', { routes, interfaces, relations });
const links = graph.links.filter(l => l.kind === 'communication');
const motorKombi = links.find(l => graph.byId.get(l.source)?.name === 'Motorsteuerung' && graph.byId.get(l.target)?.name === 'Kombiinstrument');
assert.ok(motorKombi, 'Application communication exists in the complete graph before any filter');
const diagnostic = links.filter(l => /Diagnos/i.test(`${graph.byId.get(l.source)?.name} ${graph.byId.get(l.target)?.name}`));
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1688, height: 1272 }, reducedMotion: 'no-preference' });
const errors = [], writes = [], checks = [];
page.on('pageerror', e => errors.push(e.message));
page.on('request', r => {
  if (r.url().includes('/api/engineering/') && !['GET', 'HEAD'].includes(r.method())) writes.push({ method: r.method(), path: new URL(r.url()).pathname, body: r.postDataJSON() });
});
let failed = false;
try {
  await page.goto(`http://127.0.0.1:13500/studio?mode=network&project=${project}`);
  await page.getByRole('tab', { name: 'Hardware-Topologie', exact: true }).click();
  const view = page.locator('.hardware-explorer'), button = name => view.getByRole('button', { name, exact: true });
  const search = view.getByRole('searchbox', { name: 'Topologie durchsuchen' });
  const type = view.getByRole('combobox', { name: 'Knotentyp' }), bus = view.getByRole('combobox', { name: 'Bustyp filtern' });
  const canvas = view.locator('.hardware-three-host canvas');
  await page.waitForFunction(() => document.querySelectorAll('.hardware-explorer-edge.communication').length > 300);
  assert.equal(await view.locator('.hardware-explorer-edge.communication').count(), links.length);
  await view.locator('.hardware-communication-list summary').click();
  await view.locator('.hardware-communication-list button').filter({ hasText: /^Motorsteuerung → Kombiinstrument/ }).click();
  assert.ok((await view.locator('.hardware-explorer-details').innerText()).includes('RT-48BEDE64'));
  await search.fill('motor und kombi');
  const waitFlow = async dimension => {
    await page.waitForFunction(d => d === '2D'
      ? document.querySelectorAll('.hardware-communication-flow').length > 0
      : Number(document.querySelector('.hardware-three-host canvas')?.dataset.flowCount) > 0, dimension);
  };
  const moving2d = async () => {
    await waitFlow('2D');
    const flow = view.locator('.hardware-communication-flow').first();
    const offset = await flow.evaluate(p => getComputedStyle(p).strokeDashoffset);
    await page.waitForTimeout(170);
    assert.notEqual(await flow.evaluate(p => getComputedStyle(p).strokeDashoffset), offset);
  };
  // Every representation must retain the same search and still show its route.
  for (const mode of ['Functions', 'Combined', 'Hardware']) {
    await button(mode).click(); assert.equal(await search.inputValue(), 'motor und kombi');
    await moving2d();
    await button('3D').click(); await waitFlow('3D');
    assert.equal(await search.inputValue(), 'motor und kombi');
    await canvas.scrollIntoViewIfNeeded();
    const image = await canvas.screenshot(); await page.waitForTimeout(180);
    assert.notDeepEqual(image, await canvas.screenshot(), `${mode}: animation must advance without camera movement`);
    await button('2D').click(); await moving2d();
    checks.push(`${mode}: filter and animation in 2D/3D`);
  }
  // Retain all three fields even if a type is absent from another representation.
  await type.selectOption('ecu'); await bus.selectOption('can_fd');
  await button('Functions').click(); await button('3D').click();
  assert.equal(await search.inputValue(), 'motor und kombi');
  assert.equal(await type.inputValue(), 'ecu'); assert.equal(await bus.inputValue(), 'can_fd');
  await button('Hardware').click(); await type.selectOption(''); await bus.selectOption('');
  await waitFlow('3D');
  // Selecting a structure node must highlight, not switch off, communication.
  await view.locator('.hardware-explorer-results button').filter({ hasText: /^MotorsteuerungECU$/ }).click();
  const flows = await canvas.getAttribute('data-flow-count');
  await view.getByRole('navigation', { name: 'Zuordnungspfad' }).getByRole('button', { name: 'Projekt-Topologie', exact: true }).click();
  assert.equal(await canvas.getAttribute('data-flow-count'), flows);
  await button('Eigenschaften').click();
  await button('Datenfluss').click();
  assert.equal(await canvas.getAttribute('data-flow-count'), '0');
  await canvas.scrollIntoViewIfNeeded(); await page.waitForTimeout(120);
  const steady = await canvas.screenshot(); await page.waitForTimeout(180);
  assert.deepEqual(steady, await canvas.screenshot());
  const zoomWithoutScroll = async locator => {
    const box = await locator.boundingBox(); assert.ok(box);
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    const y = await page.evaluate(() => scrollY), image = await canvas.screenshot();
    await page.mouse.wheel(0, 160); await page.waitForTimeout(150);
    assert.equal(await page.evaluate(() => scrollY), y, 'Wheel must not scroll the document');
    assert.notDeepEqual(image, await canvas.screenshot(), 'Wheel must zoom the 3D graph');
  };
  await zoomWithoutScroll(canvas);
  await zoomWithoutScroll(view.locator('.hardware-three-labels button:not([hidden])').first());
  // A wheel event during pointer rotation must also stay inside the viewport.
  const box = await canvas.boundingBox(); await page.mouse.move(box.x + 20, box.y + 20);
  const scroll = await page.evaluate(() => scrollY);
  await page.mouse.down(); await page.mouse.wheel(0, 220); await page.mouse.up();
  await page.waitForTimeout(100); assert.equal(await page.evaluate(() => scrollY), scroll);
  await button('Datenfluss').click(); await waitFlow('3D');
  await page.evaluate(() => scrollTo(0, 0)); await page.waitForTimeout(150);
  await canvas.scrollIntoViewIfNeeded(); await page.waitForTimeout(100);
  const resumed = await canvas.screenshot(); await page.waitForTimeout(180);
  assert.notDeepEqual(resumed, await canvas.screenshot(), 'Animation resumes when viewport becomes visible');
  await view.screenshot({ path: '../backend/runtime/hardware-view-stability-3d.png' });
  await button('2D').click(); await moving2d();
  const stage = view.locator('.hardware-topology-stage'); await stage.scrollIntoViewIfNeeded();
  const stageBox = await stage.boundingBox(); await page.mouse.move(stageBox.x + 15, stageBox.y + 15);
  const y = await page.evaluate(() => scrollY), transform = await view.locator('[data-graph-transform]').getAttribute('transform');
  await page.mouse.wheel(0, -180); await page.waitForTimeout(100);
  assert.equal(await page.evaluate(() => scrollY), y);
  assert.notEqual(await view.locator('[data-graph-transform]').getAttribute('transform'), transform);
  const zoomed = await view.locator('[data-graph-transform]').getAttribute('transform');
  await button('Verbindungen').click(); assert.equal(await view.locator('[data-graph-transform]').getAttribute('transform'), zoomed);
  await button('Verbindungen').click();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.waitForFunction(() => document.querySelectorAll('.hardware-communication-flow').length === 0);
  assert.equal(await button('Datenfluss').isDisabled(), true);
  await page.emulateMedia({ reducedMotion: 'no-preference' }); await moving2d();
  await view.screenshot({ path: '../backend/runtime/hardware-view-stability-2d.png' });
  const after = await api('/workflow/network-view');
  assert.deepEqual(after.topology, before.topology); assert.deepEqual(after.edit_tokens, before.edit_tokens);
  assert.ok(writes.every(w => w.method === 'PATCH' && w.path === '/api/engineering/workflow/context' && Object.keys(w.body).length === 1 && w.body.active_workflow_step === 'network_editor'), JSON.stringify(writes));
  assert.deepEqual(errors, []);
  const result = { routes: routes.length, communicationPairs: links.length, diagnosisPairs: diagnostic.length, otherPairs: links.length - diagnostic.length, checks, allFiltersPreserved: true, selectionKeepsFlow: true, wheelOnCanvasAndLabels: true, wheelDuringDrag: true, visibilityResume: true, reducedMotion: true, canonicalUnchanged: true, errors };
  await fs.writeFile('../backend/runtime/hardware-view-stability.json', JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} catch (error) {
  failed = true; console.error(error); await page.screenshot({ path: '../backend/runtime/hardware-view-stability-failure.png' }).catch(() => {});
} finally {
  const cdp = await browser.newBrowserCDPSession();
  await Promise.race([cdp.send('Browser.close').catch(() => {}), new Promise(r => setTimeout(r, 2000))]);
}
process.exit(failed ? 1 : 0);
