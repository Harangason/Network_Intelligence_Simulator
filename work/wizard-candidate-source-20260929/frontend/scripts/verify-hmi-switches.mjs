import { chromium } from 'playwright';
import assert from 'node:assert/strict';

// Isolated browser: do not submit an engineering order or mutate the project.
const projectId = process.env.NIS_PROJECT_ID || 'network-project-20260914043610181-7a1ce56e';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1383, height: 1272 } });
let failed = false;
const pending = new Set();
page.on('pageerror', error => console.error('Browser error:', error.message));
page.on('request', request => pending.add(request.url()));
page.on('requestfinished', request => pending.delete(request.url()));
page.on('requestfailed', request => pending.delete(request.url()));
try {
  page.setDefaultTimeout(15000);
  const hydrated = page.waitForResponse(response => response.url().includes('/api/engineering/') && response.request().method() === 'GET', { timeout: 30000 });
  await page.goto(`http://127.0.0.1:13500/studio/engineering?project=${projectId.replace(/^network-project-/, '')}`, { waitUntil: 'load', timeout: 30000 });
  await hydrated;
  await page.route('**/api/**', route => route.request().method() === 'GET' || route.request().url().endsWith('/equipment-assignment-learning/retrieve')
    ? route.continue() : route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }));
  await page.evaluate(projectId => {
    sessionStorage.setItem('networkis:pending-engineering-wizard', JSON.stringify({ projectId, createdAt: Date.now() }));
    window.dispatchEvent(new CustomEvent('engineering-agent:wizard-open', { detail: { projectId } }));
  }, projectId);
  const dialog = page.getByRole('dialog', { name: 'Engineering-Auftrag erstellen' });
  await dialog.waitFor();
  await dialog.getByTitle('Projektname', { exact: true }).click();
  await dialog.locator('#engineering-project-name').fill('HMI Layoutprüfung');
  await dialog.getByTitle('Aufgabe', { exact: true }).click();
  await dialog.getByLabel('Aufgabentext', { exact: true }).fill('Automotive Fahrzeug mit Motorsteuerung, Elektromotorsteuerung, Kombiinstrument, HeadUpDisplay, Infotainment, Sensoren und Aktoren.');
  await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  await dialog.getByLabel('Controller: verbindliche Anzahl', { exact: true }).fill('36');
  await dialog.getByLabel('Gateways: verbindliche Anzahl', { exact: true }).fill('1');
  const clusterSelector = dialog.locator('.agent-cluster-selector select');
  const powertrain = await clusterSelector.locator('option').evaluateAll(options => options.find(option => option.textContent.includes('Antriebsstrang'))?.value);
  assert.ok(powertrain);
  await clusterSelector.selectOption(powertrain);
  for (const label of ['Fahrwerk', 'Karosserie', 'Infotainment']) {
    const option = await clusterSelector.locator('option').evaluateAll((options, label) => options.find(option => option.textContent.includes(label))?.value, label);
    assert.ok(option, label);
    await clusterSelector.selectOption(option);
    assert.ok(await dialog.getByRole('switch').count() > 0, `${label}: HMI choices`);
    if (label === 'Infotainment') {
      assert.ok(await dialog.locator('.agent-controller-functions').count() > 0);
      await dialog.locator('.agent-controller-functions').first().scrollIntoViewIfNeeded();
      await page.screenshot({ path: '../backend/runtime/domain-functions-live.png' });
    }
  }
  await clusterSelector.selectOption(powertrain);
  const switches = dialog.getByRole('switch');
  await switches.first().waitFor();
  const name = await switches.first().getAttribute('aria-label');
  assert.equal(await switches.first().isChecked(), false);
  await switches.first().locator('..').click({ position: { x: 18, y: 15 } });
  assert.equal(await switches.first().isChecked(), true);
  assert.equal(await switches.nth(1).isChecked(), false);
  await dialog.getByTitle('Aufgabe', { exact: true }).click();
  await dialog.getByTitle('Geräteumfang', { exact: true }).click();
  assert.equal(await dialog.getByRole('switch', { name, exact: true }).isChecked(), true);
  await switches.first().scrollIntoViewIfNeeded();
  await page.screenshot({ path: '../backend/runtime/hmi-switches-live.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  await switches.first().scrollIntoViewIfNeeded();
  assert.equal(await dialog.evaluate(el => el.scrollWidth > el.clientWidth), false);
  await switches.first().locator('..').click({ position: { x: 18, y: 15 } });
  assert.equal(await switches.first().isChecked(), false);
  console.log(JSON.stringify({ passed: true, switches: await switches.count(), defaultOff: true, targetIsolation: true, navigationPreservesChoice: true, smallViewport: true }));
} catch (error) {
  failed = true;
  console.error(error);
  console.error('Pending requests:', [...pending]);
  console.error((await page.locator('body').innerText()).slice(-6500));
  await page.screenshot({ path: '../backend/runtime/hmi-switches-failure.png' });
} finally {
  const session = await browser.newBrowserCDPSession();
  await Promise.race([session.send('Browser.close').catch(() => {}), new Promise(resolve => setTimeout(resolve, 2000))]);
  process.exit(failed ? 1 : 0);
}
