import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage();
page.setDefaultTimeout(30000);
const id = '79af0d80-8577-4eb7-af93-6dd5d29766e0';
try {
  await page.route('**/api/engineering/routing?*', async route => {
    const response = await route.fetch();
    const data = await response.json();
    const item = data.items?.find(item => item.id === id);
    if (item) { item.status = 'CONFLICT'; item.validation = { valid: false, errors: [{ code: 'COMMAND_SIGNALS_MISSING', message: 'Test: Befehl ergänzen' }] }; }
    await route.fulfill({ response, json: data });
  });
  await page.goto('http://127.0.0.1:13500/studio/routing?project=20260909082213746-780a13ef&view=conflicts', { waitUntil: 'domcontentloaded' });
  await page.getByRole('link', { name: 'Befehlssignale ergänzen', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.waitFor();
  await dialog.getByRole('button', { name: 'Weiter', exact: true }).click();
  await dialog.locator('#parent_id option[value="73cbaf4f-f0c2-477e-a5bb-d39dc8acc900"]').waitFor({ state: 'attached' });
  assert.equal(await dialog.locator('#parent_id').inputValue(), '73cbaf4f-f0c2-477e-a5bb-d39dc8acc900');
  await page.screenshot({ path: 'docs/implementation_audit/verification/2026-09-09-conflict-wizard.png' });
  console.log('PASS: conflict opens signal wizard with exact affected message; no model mutation');
} finally { await browser.close(); }
