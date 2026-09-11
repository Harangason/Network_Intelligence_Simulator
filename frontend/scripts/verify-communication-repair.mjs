import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-20260910042736034-d11591d0';
const endpoint = 'http://127.0.0.1:15050/api/engineering';
async function api(path, body) {
  const response = await fetch(endpoint + path, { method: body ? 'POST' : 'GET',
    headers: { 'X-Project-ID': project, 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  assert.ok(response.ok, path + ': ' + response.status);
  return response.json();
}
const before = await api('/workflow/network-view');
const livePlan = await api('/workflow/communication-repair/preview', {});
const group = livePlan.groups.find(g => g.options.some(o => o.action === 'adopt') && g.options.some(o => o.action === 'restore'));
assert.ok(group, 'Current broken communication must offer adoption and restoration');
assert.equal(group.status, 'QUESTION');
const adopt = group.options.find(o => o.action === 'adopt');
const restore = group.options.find(o => o.action === 'restore');
assert.ok(adopt.questions.some(q => q.includes('Weiterleitung')));
assert.ok(restore.questions.some(q => q.includes('Planungsbedarf')));
assert.ok(adopt.comparison.length && restore.comparison.length >= adopt.comparison.length);

// Actual project proposals; intercept every browser apply request.
// Canonical writes, rollback and revalidation are tested on isolated SQL copies.
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1688, height: 1272 } });
let failed = false, stale = false, previews = 0;
const writes = [], errors = [], reads = [];
page.on('pageerror', error => errors.push(error.message));
page.on('request', request => { if (request.method() === 'GET' && request.url().includes('/api/engineering/')) reads.push(request.url()); });
await page.route('**/api/engineering/workflow/communication-repair/**', async route => {
  if (route.request().url().endsWith('/preview')) {
    previews++;
    return route.fulfill({ json: livePlan });
  }
  const body = route.request().postDataJSON();
  writes.push(body);
  assert.equal(body.automatic, undefined);
  const chosen = group.options.find(o => body.choices?.[group.id] === o.id);
  assert.ok(chosen, 'An exact reviewed strategy must be submitted');
  return route.fulfill(stale ? { status: 409, json: { error: 'Das Modell wurde geändert. Bitte den Reparatur-Agenten erneut starten.' } }
    : { json: { applied: [{ id: group.id, label: chosen.label, routes: chosen.comparison.length, messages: 4 }], plan: { token: 'updated-version', groups: [] } } });
});
try {
  await page.goto('http://127.0.0.1:13500/studio/engineering?project=' + project + '&resource=messages&object=89320f39-10d5-46e7-a887-9987d4f2fb0f');
  await page.locator('table.eng-table tbody tr').first().waitFor();
  const button = page.getByRole('button', { name: 'Reparatur-Agent', exact: true });
  const dialog = page.getByRole('dialog', { name: 'Reparatur-Agent für Kommunikation' });
  await button.waitFor();
  assert.equal(previews, 0, 'Opening engineering must not start analysis');
  assert.equal(await page.getByRole('button', { name: 'Agent-Auftrag', exact: true }).count(), 0);
  await button.click();
  await dialog.getByRole('button', { name: 'Neue Führung übernehmen', exact: true }).first().waitFor();
  assert.equal(writes.length, 0);
  const options = dialog.locator('.eng-repair-option');
  assert.equal(await options.count(), group.options.length);
  assert.match(await options.first().innerText(), /Bisherige Führung/);
  assert.equal(await options.first().locator('tbody tr').count(), adopt.comparison.length);
  const restoreOption = options.filter({ has: page.getByRole('button', { name: 'Alte Führung wiederherstellen', exact: true }) });
  assert.equal(await restoreOption.locator('tbody tr').count(), restore.comparison.length);
  await page.screenshot({ path: '../backend/runtime/communication-repair-compare.png' });
  await dialog.getByRole('button', { name: 'Später entscheiden', exact: true }).first().click();
  assert.match(await dialog.innerText(), /Offen gelassen/);
  assert.equal(writes.length, 0, 'Deferring leaves routing untouched');
  await dialog.getByRole('button', { name: 'Schließen', exact: true }).click();
  await button.click();
  const beforeReads = reads.length;
  await dialog.getByRole('button', { name: 'Neue Führung übernehmen', exact: true }).first().click();
  await dialog.getByText('Verknüpfungen repariert', { exact: true }).waitFor();
  assert.deepEqual(writes.at(-1), { token: livePlan.token, choices: { [group.id]: adopt.id } });
  assert.ok(reads.length > beforeReads, 'Engineering tables refresh after repair');
  await dialog.getByRole('button', { name: 'Schließen', exact: true }).click();

  await page.goto('http://127.0.0.1:13500/studio/routing?project=' + project);
  await page.locator('table.routing-table tbody tr').first().waitFor();
  await button.click();
  await dialog.getByRole('button', { name: 'Alte Führung wiederherstellen', exact: true }).waitFor();
  const routingReads = reads.filter(u => /\/routing(?:\?|$)/.test(u)).length;
  await restoreOption.scrollIntoViewIfNeeded();
  await page.screenshot({ path: '../backend/runtime/communication-repair-routing-restore.png' });
  await dialog.getByRole('button', { name: 'Alte Führung wiederherstellen', exact: true }).click();
  await dialog.getByText('Verknüpfungen repariert', { exact: true }).waitFor();
  assert.deepEqual(writes.at(-1), { token: livePlan.token, choices: { [group.id]: restore.id } });
  assert.ok(reads.filter(u => /\/routing(?:\?|$)/.test(u)).length > routingReads, 'Routing table reloads canonical routes after repair');
  await dialog.getByRole('button', { name: 'Schließen', exact: true }).click();
  stale = true;
  await button.click();
  await dialog.getByRole('button', { name: 'Neue Führung übernehmen', exact: true }).first().click();
  await dialog.getByRole('alert').waitFor();
  assert.match(await dialog.getByRole('alert').innerText(), /Modell wurde geändert/);
  await page.keyboard.press('Escape');
  await dialog.waitFor({ state: 'hidden' });
  assert.deepEqual(errors, []);
  assert.deepEqual(await api('/workflow/network-view'), before, 'User topology remains untouched by verification');
  await fs.writeFile('../backend/runtime/communication-repair-verified.json', JSON.stringify({ project,
    liveComparison: { adopt: adopt.comparison.length, restore: restore.comparison.length },
    browser: { previews, mockedChoices: writes.length, noAutoApply: true, bothPages: true, errors }, projectTopologyUnchanged: true,
  }, null, 2));
  console.log('PASS: actual before/after proposals, both choices, no automatic apply, routing refresh, stale revision and unchanged user topology');
} catch (error) { failed = true; console.error(error); }
finally {
  const cdp = await browser.newBrowserCDPSession();
  await Promise.race([cdp.send('Browser.close').catch(() => {}), new Promise(resolve => setTimeout(resolve, 2000))]);
  process.exit(failed ? 1 : 0);
}
