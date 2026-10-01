import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { chromium } from 'playwright';

const project = 'network-project-20260910042736034-d11591d0';
const read = async () => {
  const r = await fetch('http://127.0.0.1:15050/api/engineering/routing?limit=500', { headers: { 'X-Project-ID': project } });
  assert.ok(r.ok); return (await r.json()).items;
};
const before = await read(), original = before.find(r => r.route_code === 'RT-17FAA9BD'); assert.ok(original);
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1688, height: 1272 } });
page.setDefaultTimeout(15000);
const writes = [], errors = [], checks = [];
let saved = null, failed = false;
page.on('pageerror', e => errors.push(e.message));
await page.route('**/api/engineering/routing**', async handler => {
  const request = handler.request(), url = new URL(request.url());
  if (['GET', 'HEAD'].includes(request.method())) {
    if (saved && url.pathname === '/api/engineering/routing') {
      const response = await handler.fetch(), data = await response.json();
      return handler.fulfill({ json: { ...data, items: data.items.map(r => r.id === saved.id ? saved : r) } });
    }
    return handler.continue();
  }
  writes.push({ method: request.method(), path: url.pathname, body: request.postDataJSON() });
  if (request.method() === 'PATCH') saved = { ...original, ...request.postDataJSON(), revision: original.revision + 1 };
  return handler.fulfill({ json: saved ?? original });
});
const dialog = page.locator('.routing-wizard-dialog');
const step = text => dialog.locator('.routing-wizard-steps').getByRole('button', { name: new RegExp(text, 'i') });
const open = async () => {
  await page.goto(`http://127.0.0.1:13500/studio/routing?project=${project}&route=${original.id}`);
  await page.locator('.routing-detail').filter({ hasText: original.route_code }).waitFor();
  const rail = page.locator('.routing-detail-rail'); if (await rail.count()) await rail.click();
  await page.getByRole('button', { name: 'Wizard', exact: true }).click();
};
try {
  await open(); await step('Prüfen').click();
  await dialog.locator('.routing-payload-review').getByRole('button').click();
  await dialog.getByRole('region', { name: 'Bearbeitbarer Payload-Entwurf' }).waitFor();
  await dialog.getByRole('button', { name: 'Entwurf verwerfen', exact: true }).click();
  const planner = dialog.getByRole('region', { name: 'Payload gemeinsam festlegen' });
  await planner.waitFor(); assert.equal(writes.length, 0);
  assert.match(await planner.getByRole('heading').first().innerText(), /Fahrerassistenz.*Kuehlkreislaufsteuerung/);
  const namedCards = planner.getByRole('article', { name: 'Payload-Vorschlag Kuehlkreislaufsteuerung', exact: true });
  // The live model may also contain a second message with the same display name.
  const selectedCards = namedCards.and(planner.locator('article.selected'));
  const card = (await selectedCards.count() ? selectedCards : namedCards).first();
  assert.equal(await card.locator('li').count(), 5);
  assert.match(await card.innerText(), /3 Byte · 20 ms/);
  assert.match(await card.innerText(), /OFF = 0/); assert.match(await card.innerText(), /ERROR = 5/);
  assert.equal(await planner.getByRole('article', { name: /LIN IO Befehl/ }).count(), 0);
  checks.push('Step 7 opens data questions; real message shows all five signals, meanings, codes and transport size');
  const input = planner.getByLabel('Benötigte Informationen', { exact: true });
  await input.fill('an, aus und Fehler');
  await planner.getByRole('checkbox', { name: 'Betriebszustand / Betriebsart', exact: true }).check();
  await planner.getByRole('checkbox', { name: 'Fehler / Gesundheit / Qualität', exact: true }).check();
  await card.getByRole('button', { name: 'Vorschlag übernehmen' }).click();
  const selection = planner.getByRole('region', { name: 'Gewählter Payload' });
  assert.equal(await selection.locator('input:checked').count(), 2);
  assert.match(await selection.locator('label').filter({ has: page.locator('input:checked') }).allTextContents().then(s => s.join(' ')), /Health.*Status|Status.*Health/);
  await step('Prüfen').click();
  assert.match(await dialog.locator('.routing-payload-review').innerText(), /an, aus und Fehler/);
  assert.equal(writes.length, 0);
  await step('Payload').click(); assert.equal(await input.inputValue(), 'an, aus und Fehler');
  checks.push('Need filters existing content; explicit adoption selects Health and Status; review/navigation retain the request');
  await input.fill('Temperatur');
  assert.equal(await planner.getByRole('article').count(), 0);
  assert.match(await planner.getByRole('status').innerText(), /Kein passender Inhalt/);
  const wizard = planner.getByRole('link', { name: 'Nachrichten-Wizard öffnen ↗' });
  const popupPromise = page.waitForEvent('popup'); await wizard.click(); const popup = await popupPromise;
  await popup.waitForURL(/resource=messages&create=1/);
  await popup.locator('.eng-object-wizard').waitFor();
  assert.equal(new URL(popup.url()).searchParams.get('project')?.replace(/^network-project-/, ''), project.replace(/^network-project-/, ''));
  await popup.close();
  assert.equal(await selection.locator('input:checked').count(), 2, 'Search does not erase the selected payload');
  checks.push('Missing data is explicit; real message-creation wizard opens in the same project without discarding the route');
  await input.fill('an, aus und Fehler');
  await page.screenshot({ path: '../backend/runtime/routing-payload-planner-desktop.png' });
  await page.setViewportSize({ width: 800, height: 1000 });
  const box = await dialog.boundingBox(); assert.ok(box.x >= 0 && box.x + box.width <= 801);
  await input.fill('an, aus und Fehler');
  await page.setViewportSize({ width: 1688, height: 1272 });
  await step('Prüfen').click(); await dialog.getByRole('button', { name: 'Speichern & validieren' }).click();
  await dialog.waitFor({ state: 'hidden' });
  assert.deepEqual(writes.map(w => w.method), ['PATCH', 'POST']);
  assert.equal(saved.payload.data_requirements.text, 'an, aus und Fehler');
  assert.deepEqual(saved.payload.data_requirements.categories, ['state', 'health']);
  assert.equal(saved.payload.signal_ids.length, 2);
  await open(); await step('Payload').click();
  assert.equal(await input.inputValue(), 'an, aus und Fehler');
  assert.equal(await selection.locator('input:checked').count(), 2);
  assert.deepEqual(await read(), before); assert.deepEqual(errors, []);
  checks.push('Explicit save carries data requirements and signal IDs; reopening restores them; live routes unchanged (save intercepted)');
  const result = { status: 'passed', checks, errors, liveRoutesUnchanged: true };
  await fs.writeFile('../backend/runtime/routing-payload-planner-browser.json', JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2));
} catch (error) {
  failed = true; console.error(error); console.error((await dialog.innerText().catch(() => '')).slice(-6500));
  await page.screenshot({ path: '../backend/runtime/routing-payload-planner-failure.png' });
} finally {
  const cdp = await page.context().newCDPSession(page);
  await Promise.race([cdp.send('Browser.close').catch(() => {}), new Promise(resolve => setTimeout(resolve, 1500))]);
  process.exit(failed ? 1 : 0);
}
