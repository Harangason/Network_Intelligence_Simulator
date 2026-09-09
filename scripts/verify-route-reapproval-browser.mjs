import { chromium } from '../frontend/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage();
page.setDefaultTimeout(20000);
const project = 'network-project-20260909082213746-780a13ef';
const id = '79af0d80-8577-4eb7-af93-6dd5d29766e0';
let ready = false;
try {
  // UI regression only: simulate a successful revalidation without altering project data.
  await page.route('**/api/engineering/routing?*', async request => {
    const response = await request.fetch();
    const data = await response.json();
    const route = data.items?.find(item => item.id === id);
    if (route && ready) {
      route.status = 'READY_FOR_REVIEW';
      route.validation = { ...route.validation, valid: true, errors: [] };
      route.approval_state = 'APPROVED'; // Legacy stale flag must not disable review.
    }
    await request.fulfill({ response, json: data });
  });
  for (const corrected of [false, true]) {
    ready = corrected;
    await page.goto(`http://127.0.0.1:13500/studio/routing?project=${project}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.locator('.routing-main-panel input:not([type=checkbox])').first().fill('Abgasnachbehandlung');
    await page.locator('.routing-main-panel tr').filter({ hasText: 'RT-0EDA4C8D' }).click();
    const rail = page.locator('.routing-detail-rail');
    if (await rail.isVisible()) await rail.click();
    const approve = page.locator('.routing-detail').getByRole('button', { name: 'Approve', exact: true });
    await approve.waitFor();
    assert.equal(await approve.isEnabled(), corrected);
  }
  console.log(JSON.stringify({ invalid_disabled: true, corrected_enabled: true, legacy_approval_unblocked: true }));
} finally { await browser.close(); }
