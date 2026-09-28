import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

// Real isolated persistence and parameter-view regressions; not nine-stage completion proof.
test('mixed project shows exact LIN profile, rejects 2M and preserves CAN-FD while saving LIN @technology-review', async ({ page }) => {
  const project = 'nis-e2e-rate-' + randomUUID();
  const headers = { 'X-Project-ID': project };
  const initial = await (await page.request.get('/api/engineering/workflow/parameters', { headers })).json();
  const parameters = { ...initial.parameters, industry: 'automotive', technology: 'can_fd', defaults_source: 'technology-registry',
    bitrate: 2000000, arbitration_bitrate: 500000, data_bitrate: 2000000,
    networks: [{ id:'lin-one', technology:'LIN', name:'LIN Test' }, {id:'can-one', technology:'CAN_FD',name:'CAN Test'}] };
  const seeded = await page.request.patch('/api/engineering/workflow/parameters', { headers, data:{parameters, expected_token:initial.edit_token} });
  expect(seeded.ok(), await seeded.text()).toBe(true);
  // Delay the real read: controls must not use defaults and then overwrite a user selection.
  await page.route('**/api/engineering/workflow/parameters', async route => {
    if (route.request().method() === 'GET') await new Promise(resolve => setTimeout(resolve, 300));
    await route.continue();
  });
  await page.goto(`/studio?mode=parameters&project=${project}`);
  await expect(page.locator('#technology')).toHaveValue('can_fd');
  await page.locator('#technology').selectOption('lin');
  await expect(page.locator('input[name="bitrate"]')).toHaveValue('19200');
  await expect(page.locator('input[name="data_bitrate"]')).toHaveCount(0);
  await page.locator('input[name="bitrate"]').fill('2000000');
  expect(await page.locator('input[name="bitrate"]').evaluate((el: HTMLInputElement) => el.checkValidity())).toBe(false);
  await page.locator('input[name="bitrate"]').fill('9600');
  const response = page.waitForResponse(r => r.url().includes('/api/engineering/workflow/parameters') && r.request().method() === 'PATCH');
  await page.getByRole('button', {name:'Parameter speichern →',exact:true}).click();
  expect((await response).ok()).toBe(true);
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', {headers})).json();
  expect(saved.parameters.networks).toEqual(parameters.networks);
  expect(saved.parameters.technology).toBe('can_fd');
  expect(saved.parameters.data_bitrate).toBe(2000000);
  expect(saved.parameters.technology_parameters.lin.values.bitrate).toBe(9600);
  expect(saved.parameters.technology_parameters.lin.provenance.bitrate.status).toBe('CONFIRMED');
  await page.reload();
  await expect(page.locator('#technology')).toHaveValue('can_fd');
  await page.locator('#technology').selectOption('lin');
  await expect(page.locator('input[name="bitrate"]')).toHaveValue('9600');
  await page.locator('#technology').selectOption('can_fd');
  await expect(page.locator('input[name="data_bitrate"]')).toHaveValue('2000000');
});

test('stale parameter revision rejects the real write and preserves confirmed rates @technology-review', async ({ page }) => {
  const project = 'nis-e2e-rate-conflict-' + randomUUID();
  const headers = {'X-Project-ID':project};
  const first = await (await page.request.get('/api/engineering/workflow/parameters', {headers})).json();
  const parameters = {...first.parameters, technology:'lin', bitrate:19200};
  const saved = await page.request.patch('/api/engineering/workflow/parameters', {headers,data:{parameters,expected_token:first.edit_token}});
  expect(saved.ok(), await saved.text()).toBe(true);
  const conflict = await page.request.patch('/api/engineering/workflow/parameters', {headers,data:{parameters:{...parameters,bitrate:9600},expected_token:first.edit_token}});
  expect(conflict.status()).toBe(409);
  const current = await (await page.request.get('/api/engineering/workflow/parameters',{headers})).json();
  expect(current.parameters.bitrate).toBe(19200);
});
