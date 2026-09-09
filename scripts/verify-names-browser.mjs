import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
const output = new URL('../docs/implementation_audit/verification/', import.meta.url);
const migration = JSON.parse(await readFile(new URL('2026-09-09-names-live.json', output), 'utf8'));
const base = 'http://127.0.0.1:13500';
const projectId = migration.project_id;
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1647, height: 1272 } });
const report = { checks: [], errors: [], status: 'RUNNING' };
page.on('pageerror', error => report.errors.push(String(error)));
try {
  const examples = [
    ['Function', 'Allradsteuerung_Steuerung', 'functions'],
    ['Interface', 'RearLeftBrakeTemperature_1', 'interfaces'],
    ['Message', 'FrontRightBrakeTemperatureSensorErfassungData', 'messages'],
  ];
  for (const [kind, before, resource] of examples) {
    const change = migration.changes.find(c => c.object_type === kind && c.before === before);
    assert.ok(change, before);
    await page.goto(`${base}/studio/engineering?project=${projectId}&resource=${resource}&object=${change.id}`, { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: change.after, exact: true }).waitFor({ timeout: 30000 });
    report.checks.push({ before, after: change.after });
    if (kind === 'Interface') {
      const row = page.locator('table.eng-table.interfaces > tbody > tr').filter({ has: page.getByRole('cell', { name: change.after, exact: true }) });
      assert.ok((await row.innerText()).includes('CAN-FD'));
      assert.ok(!(await row.innerText()).includes('CAN_FD'));
      report.checks.push('Technology is shown as CAN-FD');
    }
    if (kind === 'Message') {
      const headers = { 'X-Project-ID': projectId };
      const message = await (await page.request.get(`${base}/api/engineering/messages/${change.id}`, { headers })).json();
      const port = await (await page.request.get(`${base}/api/engineering/hardware-interfaces/${message.hardware_interface_id}`, { headers })).json();
      const workflow = await (await page.request.get(`${base}/api/engineering/workflow`, { headers })).json();
      const bus = workflow.parameters.networks.find(n => n.id === port.network_ref).name;
      const row = page.locator('table.eng-table.messages > tbody > tr').filter({ has: page.getByRole('cell', { name: change.after, exact: true }) });
      assert.equal(await row.locator(':scope > td').nth(2).innerText(), bus);
      report.checks.push({ physical_bus: bus, bound_network_id: port.network_ref });
    }
    await page.screenshot({ path: fileURLToPath(new URL(`2026-09-09-names-${resource}.png`, output)) });
  }
  const physical = migration.changes.find(c => c.object_type === 'HardwareNetworkInterface' && c.before.startsWith('LIN Kanal 4') && c.before.includes('abgasnachbehandlung-lin-S02'));
  assert.ok(physical);
  await page.goto(`${base}/studio/engineering?project=${projectId}&resource=hardware-interfaces&object=${physical.id}`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: physical.after, exact: true }).waitFor({ timeout: 30000 });
  assert.match(physical.after, /^Antrieb_\d{2}$/);
  report.checks.push({ before: physical.before, after: physical.after });
  await page.screenshot({ path: fileURLToPath(new URL('2026-09-09-names-physical-bus.png', output)) });
  assert.deepEqual(report.errors, []);
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL'; report.error = String(error);
  await writeFile(new URL('2026-09-09-names-browser-failure.txt', output), await page.locator('body').innerText());
  throw error;
} finally {
  await writeFile(new URL('2026-09-09-names-browser.json', output), JSON.stringify(report, null, 2));
  await browser.close();
}
console.log(JSON.stringify(report));
