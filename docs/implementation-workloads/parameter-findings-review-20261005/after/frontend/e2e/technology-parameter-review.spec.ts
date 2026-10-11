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
  // HTML bounds alone do not establish the mode/rate relationship: STANDARD
  // at 400 kbit/s must be rejected by the native profile without persistence.
  const beforeInvalid = await (await page.request.get('/api/engineering/workflow/parameters', { headers })).json();
  const invalidResponse = page.waitForResponse(r => r.url().includes('/api/engineering/workflow/parameters') && r.request().method() === 'PATCH');
  await page.getByRole('button', { name: 'Parameter speichern →', exact: true }).click();
  const rejected = await invalidResponse;
  expect(rejected.status()).toBe(400);
  expect(JSON.stringify(await rejected.json())).toContain('TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH');
  await expect(page.locator('.notice.error')).toContainText('TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH');
  const afterInvalid = await (await page.request.get('/api/engineering/workflow/parameters', { headers })).json();
  expect(afterInvalid.parameters).toEqual(beforeInvalid.parameters);
  expect(afterInvalid.edit_token).toBe(beforeInvalid.edit_token);
  await page.locator('select[name="i2c_mode"]').selectOption('FAST');
  await page.getByRole('button', { name: 'Parameter speichern →', exact: true }).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', { headers })).json();
  expect(saved.parameters.industry).toBe('custom');
  expect(saved.parameters.technology).toBe('i2c');
  expect(saved.parameters.target_bus_load_percent).toBe(60);
  expect(saved.parameters.technology_parameters.i2c.values).toMatchObject({i2c_mode:'FAST', bitrate:400000});
  await page.reload();
  await expect(page.locator('#domain')).toHaveValue('custom');
  await expect(page.locator('#technology')).toHaveValue('i2c');
  await expect(page.locator('select[name="i2c_mode"]')).toHaveValue('FAST');
  await expect(clock).toHaveValue('400000');
});

test('CAN-FD scenario defaults survive real save and reload without hardware confirmation @technology-review', async ({page}) => {
  const project = 'nis-e2e-simulation-defaults-' + randomUUID();
  const headers = {'X-Project-ID':project};
  const legacy = await page.request.patch('/api/engineering/workflow/parameters',{headers,data:{parameters:{can_clock_hz:40000000,
    parameter_provenance:{can_clock_hz:{source:'TECHNOLOGY_DEFAULT',status:'REVIEW_REQUIRED',value:40000000}}}}});
  expect(legacy.ok(),await legacy.text()).toBe(true);
  await page.goto(`/studio?mode=parameters&project=${project}`);
  await page.getByLabel('Bus / Protokoll auswählen').selectOption('can_fd');
  await page.getByLabel('Anwendungsbereich auswählen').selectOption('automotive');
  await expect(page.locator('[name="arbitration_bitrate"]')).toHaveValue('500000');
  await expect(page.locator('[name="data_bitrate"]')).toHaveValue('500000');
  await expect(page.locator('[name="payload_bytes"]')).toHaveValue('8');
  const clock = page.locator('[name="can_clock_hz"]');
  await expect(clock).toHaveValue('40000000');
  await expect(page.getByText('SIMULATIONSANNAHME · Kein Gerätenachweis').first()).toBeVisible();
  await page.getByRole('button', {name:'Parameter speichern →',exact:true}).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  const saved = await (await page.request.get('/api/engineering/workflow/parameters',{headers})).json();
  const assumptions = saved.parameters.simulation_parameter_assumptions.can_fd;
  expect(assumptions.values).toMatchObject({arbitration_bitrate:500000,data_bitrate:500000,can_clock_hz:40000000,payload_bytes:8});
  expect(assumptions.provenance.can_clock_hz).toMatchObject({source:'NIS_SIMULATION_ASSUMPTION',status:'ASSUMED',technology:'can_fd',hardware_evidence:false,value:40000000});
  expect(saved.parameters.technology_parameters.can_fd.values.can_clock_hz).toBeUndefined();
  expect(saved.parameters.can_clock_hz).toBeUndefined();
  await page.reload();
  await expect(clock).toHaveValue('40000000');
  await clock.fill('80000000');
  await page.getByRole('button', {name:'Parameter speichern →',exact:true}).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  await page.reload();
  await expect(clock).toHaveValue('80000000');
  const updated = await (await page.request.get('/api/engineering/workflow/parameters',{headers})).json();
  expect(updated.parameters.simulation_parameter_assumptions.can_fd.provenance.can_clock_hz.hardware_evidence).toBe(false);
  expect(updated.parameter_storage.source).toBe('PROJECT_USER_DEFINED_VALUES');
  const userValues = await (await page.request.get('/api/engineering/workflow/parameters/user-defined-values',{headers})).json();
  expect(userValues.project_id).toBe(project);
  expect(userValues.value_origin).toBe('USER_DEFINED_VALUE');
  expect(userValues.parameters.simulation_parameter_assumptions.can_fd.values.can_clock_hz).toBe(80000000);
  expect(userValues.parameters.technology_defaults).toBeUndefined();
  expect(userValues.parameters.defaults_source).toBeUndefined();
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
  await expect(page.locator('input[name="lin_bitrate_bps"]')).not.toHaveValue('');
  await page.locator('select[name="lin_edition"]').selectOption('LIN_2_2A_2010');
  await page.locator('select[name="lin_physical_profile"]').selectOption('LIN_2_2A_SINGLE_WIRE');
  await page.locator('div[title]').filter({has:page.locator('#lin_bitrate_bps')})
    .getByRole('button',{name:'Bedingten Standardwert übernehmen',exact:true}).click();
  await expect(page.locator('input[name="lin_bitrate_bps"]')).toHaveValue('1000');
  await expect(page.locator('input[name="data_bitrate"]')).toHaveCount(0);
  const invalid = await page.request.patch('/api/engineering/workflow/parameters', {headers,
    data:{parameters:{...parameters,technology_parameters:{lin:{values:{lin_edition:'LIN_2_2A_2010',lin_physical_profile:'LIN_2_2A_SINGLE_WIRE',lin_bitrate_bps:2000000},
      provenance:Object.fromEntries(Object.entries({lin_edition:'LIN_2_2A_2010',lin_physical_profile:'LIN_2_2A_SINGLE_WIRE',lin_bitrate_bps:2000000})
        .map(([key,value])=>[key,{source:'USER_CONFIRMED',status:'CONFIRMED',value}]))}}}}});
  expect(invalid.status()).toBe(400);
  await page.locator('input[name="lin_bitrate_bps"]').fill('9600');
  const response = page.waitForResponse(r => r.url().includes('/api/engineering/workflow/parameters') && r.request().method() === 'PATCH');
  await page.getByRole('button', {name:'Parameter speichern →',exact:true}).click();
  expect((await response).ok()).toBe(true);
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', {headers})).json();
  expect(saved.parameters.networks).toEqual(parameters.networks);
  expect(saved.parameters.technology).toBe('can_fd');
  expect(saved.parameters.data_bitrate).toBe(2000000);
  expect(saved.parameters.simulation_parameter_assumptions.lin.values.lin_bitrate_bps).toBe(9600);
  expect(saved.parameters.simulation_parameter_assumptions.lin.provenance.lin_bitrate_bps).toMatchObject({status:'ASSUMED',hardware_evidence:false});
  await page.reload();
  await expect(page.locator('#technology')).toHaveValue('can_fd');
  await page.locator('#technology').selectOption('lin');
  await expect(page.locator('input[name="lin_bitrate_bps"]')).toHaveValue('9600');
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

test('every bus exposes its own server defaults in the actual parameter form @technology-review', async ({ page }) => {
  const project = 'nis-e2e-catalog-defaults-' + randomUUID();
  const catalog = await (await page.request.get('/api/technologies')).json();
  const profiles = new Map<string, any>(catalog.domains.flatMap((domain: any) => domain.technologies).map((profile: any) => [profile.id, profile]));
  expect(profiles.size).toBe(catalog.technology_count);
  await page.goto(`/studio?mode=parameters&project=${project}`);
  const initialBus = page.getByLabel('Bus / Protokoll auswählen');
  await expect(initialBus.locator('option[value="i2c"]')).toHaveCount(1);
  await initialBus.selectOption('i2c');
  await page.getByLabel('Anwendungsbereich auswählen').selectOption('custom');
  for (const [id, profile] of profiles) {
    await page.locator('#technology').selectOption(id);
    for (const field of profile.parameter_schema.filter((item: any) => ['bitrate', 'arbitration_bitrate', 'data_bitrate'].includes(item.key))) {
      const input = page.locator(`input[name="${field.key}"]`);
      await expect(input, `${id}/${field.key}`).not.toHaveValue('');
      expect(await input.evaluate((el: HTMLInputElement) => el.checkValidity()), `${id}/${field.key}`).toBe(true);
    }
    const empty = await page.locator('form.config-panel .parameter-groups').evaluate(groups =>
      [...groups.querySelectorAll('input,select,textarea')]
        .filter(element => (element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement)
          && element.type !== 'checkbox' && element.value === '')
        .map(element => (element as HTMLInputElement).name));
    expect(empty, id).toEqual([]);
    if (id === 'nmea2000') {
      await expect(page.locator('input[name="bitrate"]')).toHaveValue('250000');
      await expect(page.locator('input[name="mtu_bytes"]')).toHaveCount(0);
    }
  }
  // Switching through the entire catalog is a review, not a persistence action.
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', {headers:{'X-Project-ID':project}})).json();
  expect(saved.parameters.technology).toBeUndefined();
});

test('hardware editor uses the selected profile and saves proposals without inventing device confirmation @technology-review', async ({ page }) => {
  const project = 'nis-e2e-device-profile-' + randomUUID();
  const headers = {'X-Project-ID': project};
  const nodeResponse = await page.request.post('/api/engineering/hardware-nodes', {headers, data:{name:'Review Controller', device_type:'EmbeddedController', domain:'embedded_systems'}});
  expect(nodeResponse.ok(), await nodeResponse.text()).toBe(true);
  const node = await nodeResponse.json();
  const portResponse = await page.request.post('/api/engineering/hardware-interfaces', {headers, data:{name:'Device Review Port', hardware_node_id:node.id, technology:'I2C',
    capabilities:{local_timing_evidence:{slave_address:'',confirmed:false}}}});
  expect(portResponse.ok(), await portResponse.text()).toBe(true);
  const port = await portResponse.json();
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await expect(page.locator('#edit_local_i2c_mode')).toHaveValue('STANDARD');
  await expect(page.locator('#edit_local_bitrate_bps')).toHaveValue('100000');
  await expect(page.locator('#edit_data_bitrate')).toHaveCount(0);
  await expect(page.locator('#edit_local_slave_address')).not.toHaveValue('');
  await page.locator('#edit_technology').selectOption('SPI');
  await expect(page.locator('#edit_local_i2c_mode')).toHaveCount(0);
  await expect(page.locator('#edit_local_chip_select')).not.toHaveValue('');
  await expect(page.locator('#edit_local_bitrate_bps')).not.toHaveValue('');
  await page.locator('#edit_technology').selectOption('CAN_FD');
  await expect(page.locator('#edit_local_chip_select')).toHaveCount(0);
  // Explicit scenario proposals do not reuse the previous I2C device setting.
  await expect(page.locator('#edit_bitrate')).toHaveValue('500000');
  await expect(page.locator('#edit_data_bitrate')).toHaveValue('500000');
  await expect(page.locator('[name="edit_local_confirmed"]')).toHaveCount(0);
  await page.locator('#edit_technology').selectOption('I2C');
  await page.getByRole('button', {name:'Änderungen speichern',exact:true}).click();
  await expect(page.locator('#edit_technology')).toHaveCount(0);
  const saved = await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`, {headers})).json();
  expect(saved.bitrate).toBe(100000);
  expect(saved.data_bitrate).toBeNull();
  expect(saved.capabilities.local_timing_evidence).toMatchObject({technology:'I2C', i2c_mode:'STANDARD', bitrate_bps:100000, confirmed:false});
  expect(saved.capabilities.local_timing_evidence.slave_address).toBeNull();
  expect(saved.capabilities.simulation_parameter_assumptions.i2c.provenance.slave_address.hardware_evidence).toBe(false);
  // Existing verified device facts outrank standard proposals. A changed
  // device setting cannot silently reuse the old confirmation.
  const actual = await page.request.patch(`/api/engineering/hardware-interfaces/${port.id}`, {headers,
    data:{bitrate:400000, capabilities:{...saved.capabilities, local_timing_evidence:{
      evidence_scope:'CONTROLLER_PORT', master_node_id:node.id, i2c_mode:'FAST', bitrate_bps:400000,
      confirmed:true, source:'isolated-virtual-fixture:explicit-FAST-controller-port'}}}});
  expect(actual.ok(), await actual.text()).toBe(true);
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await expect(page.locator('#edit_local_i2c_mode')).toHaveValue('FAST');
  await expect(page.locator('#edit_local_bitrate_bps')).toHaveValue('400000');
  await expect(page.locator('[name="edit_local_confirmed"]')).toBeChecked();
  await page.getByRole('button', {name:'Änderungen speichern',exact:true}).click();
  await expect(page.locator('#edit_technology')).toHaveCount(0);
  const preserved = await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`, {headers})).json();
  expect(preserved.capabilities.local_timing_evidence).toMatchObject({i2c_mode:'FAST',bitrate_bps:400000,confirmed:true});
  expect(preserved.capabilities.local_timing_evidence.slave_address).toBeNull();
  expect(preserved.capabilities.simulation_parameter_assumptions.i2c.provenance.slave_address.hardware_evidence).toBe(false);
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await page.locator('#edit_local_i2c_mode').selectOption('FAST_PLUS');
  await expect(page.locator('[name="edit_local_confirmed"]')).not.toBeChecked();
  await page.getByRole('button', {name:'Änderungen speichern',exact:true}).click();
  await expect(page.locator('#edit_technology')).toHaveCount(0);
  const changed = await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`, {headers})).json();
  expect(changed.capabilities.local_timing_evidence).toMatchObject({i2c_mode:'FAST_PLUS',confirmed:false});
});


test('CAN-FD device editor retains changed simulation rates separately from actual hardware @technology-review', async ({page}) => {
  const project='nis-e2e-device-assumptions-'+randomUUID();
  const headers={'X-Project-ID':project};
  const nodeResponse=await page.request.post('/api/engineering/hardware-nodes',{headers,data:{name:'Scenario Controller',device_type:'EmbeddedController'}});
  expect(nodeResponse.ok(),await nodeResponse.text()).toBe(true);
  const node=await nodeResponse.json();
  const portResponse=await page.request.post('/api/engineering/hardware-interfaces',{headers,data:{name:'Scenario CAN Port',hardware_node_id:node.id,technology:'CAN_FD'}});
  expect(portResponse.ok(),await portResponse.text()).toBe(true);
  const port=await portResponse.json();
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await expect(page.locator('#edit_bitrate')).toHaveValue('500000');
  await expect(page.locator('#edit_data_bitrate')).toHaveValue('500000');
  await page.locator('#edit_bitrate').fill('250000');
  await page.locator('#edit_data_bitrate').fill('250000');
  await page.getByRole('button',{name:'Änderungen speichern',exact:true}).click();
  await expect(page.locator('#edit_technology')).toHaveCount(0);
  const saved=await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`,{headers})).json();
  expect(saved.bitrate).toBeNull();
  expect(saved.data_bitrate).toBeNull();
  expect(saved.capabilities.simulation_parameter_assumptions.can_fd.values).toMatchObject({arbitration_bitrate:250000,data_bitrate:250000});
  expect(saved.capabilities.simulation_parameter_assumptions.can_fd.provenance.data_bitrate.hardware_evidence).toBe(false);
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await expect(page.locator('#edit_bitrate')).toHaveValue('250000');
  await expect(page.locator('#edit_data_bitrate')).toHaveValue('250000');
});

test('PWM device editor offers no retired transaction proof and preserves native driver configuration @technology-review', async ({page}) => {
  const project = 'nis-e2e-pwm-editor-' + randomUUID();
  const headers = {'X-Project-ID':project};
  const nodeResponse = await page.request.post('/api/engineering/hardware-nodes', {headers,
    data:{name:'PWM Review Controller',device_type:'EmbeddedController',domain:'embedded_systems'}});
  expect(nodeResponse.ok(),await nodeResponse.text()).toBe(true);
  const node = await nodeResponse.json();
  const portResponse = await page.request.post('/api/engineering/hardware-interfaces', {headers,
    data:{name:'PWM Output',hardware_node_id:node.id,technology:'PWM',capabilities:{
      technology_parameters:{pwm_profile:'LINUX_STATE_6_18',pwm_period_ns:2000000,pwm_duty_ns:700000,
        pwm_polarity:'INVERSED',pwm_enabled:true,pwm_device_source:'isolated-virtual-PWM-driver'}}}});
  expect(portResponse.ok(),await portResponse.text()).toBe(true);
  const port = await portResponse.json();
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await expect(page.locator('#edit_technology')).toHaveValue('PWM');
  // Wait for the selected profile, not only the initial editor skeleton.
  const catalog = await (await page.request.get('/api/technologies')).json();
  expect(catalog.domains.flatMap((domain:any)=>domain.technologies).find((profile:any)=>profile.id==='pwm').local_timing_schema).toEqual([]);
  for (const field of ['pwm_frequency_hz','update_bound_ms','capture_bound_ms'])
    await expect(page.locator(`#edit_local_${field}`)).toHaveCount(0);
  await expect(page.locator('#edit_bitrate')).toHaveCount(0);
  await expect(page.locator('#edit_data_bitrate')).toHaveCount(0);
  await expect(page.locator('[name="edit_local_confirmed"]')).toHaveCount(0);
  await page.locator('#edit_name').fill('Reviewed PWM Output');
  await page.getByRole('button',{name:'Änderungen speichern',exact:true}).click();
  await expect(page.locator('#edit_technology')).toHaveCount(0);
  const saved = await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`,{headers})).json();
  expect(saved.name).toBe('Reviewed PWM Output');
  expect(saved.capabilities).toEqual(port.capabilities);
  expect(saved.capabilities.local_timing_evidence).toBeUndefined();
  expect(saved.bitrate).toBeNull();
  expect(saved.data_bitrate).toBeNull();
});

test('actual uint64 protocol value survives legacy numeric JSON, form edit, SQL persistence and reload @technology-review', async ({page}) => {
  const project = 'nis-e2e-uint64-' + randomUUID();
  const headers = {'X-Project-ID':project,'Content-Type':'application/json'};
  const initial = await (await page.request.get('/api/engineering/workflow/parameters',{headers})).json();
  const maximum = '18446744073709551615';
  const seed = JSON.stringify({parameters:{industry:'custom',technology:'sparkplug_b',spb_alias:'__EXACT_INTEGER__',
    parameter_provenance:{spb_alias:{value:'__EXACT_INTEGER__',source:'USER_CONFIRMED',status:'CONFIRMED'}}},expected_token:initial.edit_token})
    .replaceAll('"__EXACT_INTEGER__"', maximum);
  const seeded = await page.request.patch('/api/engineering/workflow/parameters',{headers,data:seed});
  expect(seeded.ok(),await seeded.text()).toBe(true);
  await page.goto(`/studio?mode=parameters&project=${project}`);
  await expect(page.locator('#technology')).toHaveValue('sparkplug_b');
  await expect(page.locator('#spb_alias')).toHaveAttribute('type','text');
  await expect(page.locator('#spb_alias')).toHaveValue(maximum);
  const catalog = await (await page.request.get('/api/technologies')).json();
  const profile = catalog.domains.flatMap((d:{technologies:Array<{id:string}>})=>d.technologies).find((p:{id:string})=>p.id==='sparkplug_b');
  for (const field of profile.parameter_schema.filter((f:{required?:boolean,type:string})=>f.required&&f.type==='text')) {
    await page.locator(`[name="${field.key}"]`).fill('isolated-test-source');
  }
  const edited = '18446744073709551614';
  await page.locator('#spb_alias').fill(edited);
  await page.getByRole('button',{name:'Parameter speichern →',exact:true}).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  const saved = await (await page.request.get('/api/engineering/workflow/parameters',{headers})).json();
  expect(saved.parameters.technology_parameters.sparkplug_b.values.spb_alias).toBe(edited);
  expect(saved.parameters.technology_parameters.sparkplug_b.provenance.spb_alias.value).toBe(edited);
  await page.reload();
  await expect(page.locator('#spb_alias')).toHaveValue(edited);
});


test('proposal parameter link selects its technology and live findings highlight only affected fields @technology-review', async ({page}) => {
  const project='nis-e2e-current-parameter-review-'+randomUUID();
  const headers={'X-Project-ID':project};
  const networks=[{id:'can-local',name:'CAN Local',technology:'CAN_FD'},{id:'lin-local',name:'LIN Local',technology:'LIN'}];
  const seed=await page.request.patch('/api/engineering/workflow/parameters',{headers,data:{parameters:{industry:'custom',technology:'can_fd',defaults_source:'technology-registry',networks,formats:['universal-jsonl']}}});
  expect(seed.ok(),await seed.text()).toBe(true);
  async function create(resource:string,data:Record<string,unknown>) {
    const response=await page.request.post('/api/engineering/'+resource,{headers,data});
    expect(response.ok(),await response.text()).toBe(true); return response.json();
  }
  const node=await create('hardware-nodes',{name:'Review ECU',device_type:'EmbeddedController'});
  for (const network of networks) {
    const port=await create('hardware-interfaces',{name:network.name,hardware_node_id:node.id,technology:network.technology,network_ref:network.id,bitrate:null,data_bitrate:null});
    const logical=await create('interfaces',{name:network.name,hardware_node_id:node.id,interface_type:network.technology});
    await create('messages',{name:network.name+' Status',interface_id:logical.id,hardware_interface_id:port.id,dlc:1,cycle_ms:100,direction:'tx'});
  }
  const before=await (await page.request.get('/api/engineering/workflow/parameters/review',{headers})).json();
  expect(before.source).toBe('CURRENT_CANONICAL_MODEL');
  expect(before.findings.filter((f:{technology:string})=>f.technology==='can_fd')).toHaveLength(1);
  await page.goto(`/studio?mode=parameters&project=${project}&technology=lin&proposal=historical-review#parameter-findings`);
  await expect(page.locator('#technology')).toHaveValue('lin');
  await expect(page.getByRole('region',{name:'Aktuelle Parameterbefunde'})).toContainText('1 für LIN');
  await expect(page.locator('#parameter-field-lin_bitrate_bps')).toHaveClass(/parameter-field-finding/);
  await expect(page.locator('#parameter-field-lin_device_source')).toHaveClass(/parameter-field-finding/);
  await page.getByRole('navigation',{name:'Technologien mit Parameterbefunden'}).getByRole('button',{name:/CAN-FD/}).click();
  await expect(page.locator('#technology')).toHaveValue('can_fd');
  await expect(page.locator('#parameter-field-arbitration_bitrate')).toHaveClass(/parameter-field-finding/);
  await expect(page.locator('#parameter-field-data_bitrate')).toHaveClass(/parameter-field-finding/);
  await expect(page.locator('#parameter-field-can_clock_hz')).not.toHaveClass(/parameter-field-finding/);
  const confirm=page.getByRole('form',{name:'CAN-FD-Netze bestätigen'});
  await page.locator('[name="can_clock_hz"]').fill('80000000');
  await expect(confirm.getByRole('button',{name:'Für 1 Netze bestätigen & erneut prüfen',exact:true})).toBeDisabled();
  await expect(page.getByRole('region',{name:'Aktuelle Parameterbefunde'})).toContainText('Speichere zuerst die Änderungen');
  await page.getByRole('button',{name:'Parameter speichern →',exact:true}).click();
  await expect(confirm.getByRole('button',{name:'Für 1 Netze bestätigen & erneut prüfen',exact:true})).toBeEnabled();
  await confirm.getByRole('spinbutton',{name:/Nominal Bitrate/}).fill('500000');
  await confirm.getByRole('spinbutton',{name:/Data Bitrate/}).fill('2000000');
  await confirm.getByRole('button',{name:'Für 1 Netze bestätigen & erneut prüfen',exact:true}).click();
  await expect(page.getByRole('region',{name:'Aktuelle Parameterbefunde'})).toContainText('0 für CAN-FD');
  await expect(page.locator('#parameter-field-arbitration_bitrate')).not.toHaveClass(/parameter-field-finding/);
  const after=await (await page.request.get('/api/engineering/workflow/parameters/review',{headers})).json();
  expect(after.findings.some((f:{technology:string})=>f.technology==='can_fd')).toBe(false);
  expect(after.findings.some((f:{technology:string})=>f.technology==='lin')).toBe(true);
  const saved=await (await page.request.get('/api/engineering/workflow/parameters',{headers})).json();
  expect(saved.parameters.networks.find((n:{id:string})=>n.id==='lin-local')).toEqual(networks[1]);
  expect(saved.parameters.simulation_parameter_assumptions.can_fd.values.can_clock_hz).toBe(80000000);
  await page.getByRole('navigation',{name:'Technologien mit Parameterbefunden'}).getByRole('button',{name:/LIN/}).click();
  const linConfirm=page.getByRole('form',{name:'LIN-Netze bestätigen'});
  await linConfirm.getByRole('spinbutton',{name:/bit.*rate/i}).fill('19200');
  await linConfirm.getByRole('button',{name:'Für 1 Netze bestätigen & erneut prüfen',exact:true}).click();
  await expect(page.locator('#parameter-field-lin_bitrate_bps')).not.toHaveClass(/parameter-field-finding/);
  await expect(page.locator('#parameter-field-lin_device_source')).toHaveClass(/parameter-field-finding/);
  await expect(page.getByRole('region',{name:'Aktuelle Parameterbefunde'})).toContainText('1 für LIN');
  await expect(linConfirm).toHaveCount(0);
  await expect(page.getByText('Die Rate fehlt als bestätigter Projektwert.',{exact:false})).toHaveCount(0);
  const foreign=await (await page.request.get('/api/engineering/workflow/parameters/review',{headers:{'X-Project-ID':'nis-e2e-other-'+randomUUID()}})).json();
  expect(foreign.findings).toEqual([]);
});
