import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

// Real isolated persistence and parameter-view regressions; not nine-stage completion proof.
test('unconfirmed project can select every registered bus without an Automotive fallback @technology-review', async ({ page }) => {
  const project = 'nis-e2e-catalog-' + randomUUID();
  const headers = { 'X-Project-ID': project };
  const catalog = await (await page.request.get('/api/technologies')).json();
  await page.goto(`/studio?mode=parameters&project=${project}`);
  await expect(page.getByRole('heading', { name: 'Branche und Technologie auswählen' })).toBeVisible();
  await expect(page.getByLabel('Anwendungsbereich auswählen')).toHaveValue('');
  const bus = page.getByLabel('Bus / Protokoll auswählen');
  await expect(bus.locator('option')).toHaveCount(catalog.technology_count + 1);
  const search = page.getByRole('searchbox', { name: 'Bus / Protokoll suchen' });
  await search.fill('CANFD');
  await expect(bus.locator('option[value="can_fd"]')).toHaveCount(1);
  await search.fill('profnet');
  await expect(bus.locator('option[value="profinet"]')).toHaveCount(1);
  await search.clear();
  await expect(bus.locator('option')).toHaveCount(catalog.technology_count + 1);
  await bus.selectOption('i2c');
  await page.getByLabel('Anwendungsbereich auswählen').selectOption('custom');
  await expect(page.locator('#domain')).toHaveValue('custom');
  await expect(page.locator('#technology')).toHaveValue('i2c');
  const selectedBus = page.locator('#technology');
  const selectBox = await selectedBus.boundingBox();
  const searchBox = await search.boundingBox();
  expect(selectBox && searchBox && searchBox.x >= selectBox.x + selectBox.width - 1).toBe(true);
  await search.fill('profnet');
  await expect(selectedBus.locator('option[value="profinet"]')).toHaveCount(1);
  await expect(selectedBus).toHaveValue('i2c');
  await search.fill('zzzzzz');
  await expect(selectedBus).toHaveValue('i2c');
  await expect(selectedBus.locator('option[value="__no_matches"]')).toHaveCount(1);
  await search.clear();
  await expect(selectedBus.locator('option')).toHaveCount(catalog.technology_count);
  // The lowest registered I2C mode is shown as an unconfirmed proposal.
  const clock = page.locator('input[name="bitrate"]');
  await expect(clock).toHaveValue('100000');
  await expect(page.getByText('UNVERIFIED · Profilvorschlag').first()).toBeVisible();
  await expect(page.getByText(/Referenz-Obergrenzen, keine bestätigte Busfrequenz: Standard ≤ 100\.000 bit\/s/)).toBeVisible();
  expect(await clock.evaluate((input: HTMLInputElement) => input.checkValidity())).toBe(true);
  await clock.fill('0');
  expect(await clock.evaluate((input: HTMLInputElement) => input.checkValidity())).toBe(false);
  await clock.fill('400000');
  const invalid = await page.locator('form.config-panel').evaluate(form => [...(form as HTMLFormElement).elements]
    .filter(element => element instanceof HTMLInputElement && !element.checkValidity())
    .map(element => (element as HTMLInputElement).name));
  expect(invalid).toEqual([]);
  await page.getByRole('button', { name: 'Parameter speichern →', exact: true }).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', { headers })).json();
  expect(saved.parameters.industry).toBe('custom');
  expect(saved.parameters.technology).toBe('i2c');
  expect(saved.parameters.target_bus_load_percent).toBe(60);
  await page.reload();
  await expect(page.locator('#domain')).toHaveValue('custom');
  await expect(page.locator('#technology')).toHaveValue('i2c');
});

test('saved confirmed wizard context proposes its bus without inventing parameter confirmation @technology-review', async ({ page }) => {
  const project = 'nis-e2e-wizard-bus-' + randomUUID();
  const headers = { 'X-Project-ID': project };
  const seeded = await page.request.patch('/api/engineering/workflow/context?view=summary', {
    headers,
    data: { agent_wizard_status: { confirmed_at: '2026-09-30T11:32:50Z', model_type: 'custom',
      communication_system_counts: [{ id: 'i2c', count: 1 }] } },
  });
  expect(seeded.ok(), await seeded.text()).toBe(true);
  await page.goto(`/studio?mode=parameters&project=${project}`);
  await expect(page.locator('#domain')).toHaveValue('custom');
  await expect(page.locator('#technology')).toHaveValue('i2c');
  await expect(page.getByText('UNVERIFIED · Keine bestätigte Technologieauswahl')).toBeVisible();
  const parameters = await (await page.request.get('/api/engineering/workflow/parameters', { headers })).json();
  expect(parameters.parameters.technology).toBeUndefined();
});

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
  await expect(page.locator('input[name="bitrate"]')).toHaveValue('9600');
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
