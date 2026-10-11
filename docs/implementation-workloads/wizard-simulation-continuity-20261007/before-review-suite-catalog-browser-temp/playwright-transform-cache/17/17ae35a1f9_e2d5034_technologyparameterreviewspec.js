// b3908d194891b9b174e55db2a76f0e77980cdeb8
import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';
async function revealParameter(page, key) {
  const group = page.locator(`#parameter-field-${key}`).locator('xpath=ancestor::details[1]');
  if ((await group.count()) && (await group.getAttribute('open')) === null) await group.locator(':scope > summary').click();
}
for (const scenario of [{
  technology: 'LIN',
  id: 'lin',
  rate: '19200',
  key: 'lin_bitrate_bps'
}, {
  technology: 'CAN_FD',
  id: 'can_fd',
  rate: '500000',
  key: 'arbitration_bitrate',
  data: '2000000'
}, {
  technology: 'Ethernet',
  id: 'ethernet',
  rate: '1000000000',
  key: 'bitrate'
}]) test(`manual ${scenario.technology} port creation uses its native defaults and preserves edited assumptions @technology-review`, async ({
  page
}) => {
  const project = 'nis-e2e-create-rates-' + randomUUID(),
    headers = {
      'X-Project-ID': project
    };
  const nodeResponse = await page.request.post('/api/engineering/hardware-nodes', {
    headers,
    data: {
      name: 'Native default controller',
      device_type: 'EmbeddedController'
    }
  });
  expect(nodeResponse.ok(), await nodeResponse.text()).toBe(true);
  const node = await nodeResponse.json(),
    name = 'Native ' + scenario.technology + ' port';
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&parent=${node.id}&create=1`);
  const dialog = page.locator('form.eng-object-wizard');
  await expect(dialog).toBeVisible();
  await dialog.locator('#name').fill(name);
  await dialog.getByRole('button', {
    name: 'Weiter',
    exact: true
  }).click();
  await dialog.locator('#technology').selectOption(scenario.technology);
  await expect(dialog.getByRole('button', {
    name: 'Weiter',
    exact: true
  })).toBeEnabled();
  await dialog.getByRole('button', {
    name: 'Weiter',
    exact: true
  }).click();
  await expect(dialog.locator('#bitrate')).toHaveValue(scenario.rate);
  if (scenario.data) await expect(dialog.locator('#data_bitrate')).toHaveValue(scenario.data);else await expect(dialog.locator('#data_bitrate')).toHaveCount(0);
  await dialog.getByRole('button', {
    name: 'Weiter',
    exact: true
  }).click();
  await expect(dialog.locator('.proposal-wizard-review').getByText(/SIMULATIONSANNAHME/)).toBeVisible();
  const createdResponse = page.waitForResponse(response => response.url().endsWith('/api/engineering/hardware-interfaces') && response.request().method() === 'POST');
  await dialog.getByRole('button', {
    name: 'Objekt anlegen',
    exact: true
  }).click();
  const response = await createdResponse;
  expect(response.ok(), await response.text()).toBe(true);
  const port = await response.json();
  expect(port.bitrate).toBeNull();
  expect(port.data_bitrate).toBeNull();
  const group = port.capabilities.simulation_parameter_assumptions[scenario.id];
  expect(group.values[scenario.key]).toBe(Number(scenario.rate));
  expect(group.provenance[scenario.key]).toMatchObject({
    source: 'NIS_SIMULATION_ASSUMPTION',
    technology: scenario.id,
    hardware_evidence: false
  });
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await expect(page.locator('#edit_bitrate')).toHaveValue(scenario.rate);
  if (scenario.id === 'lin') {
    await page.locator('#edit_bitrate').fill('9600');
    await page.getByRole('button', {
      name: 'Änderungen speichern',
      exact: true
    }).click();
    await expect(page.locator('#edit_technology')).toHaveCount(0);
    await page.reload();
    await expect(page.locator('#edit_bitrate')).toHaveValue('9600');
    const saved = await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`, {
      headers
    })).json();
    expect(saved.bitrate).toBeNull();
    expect(saved.capabilities.simulation_parameter_assumptions.lin.values.lin_bitrate_bps).toBe(9600);
  }
});
test('native simulation rates load and persist without manual rate entry or central-default writes @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-native-defaults-' + randomUUID();
  const headers = {
    'X-Project-ID': project
  };
  const before = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  const setup = await page.request.patch('/api/engineering/workflow/parameters', {
    headers,
    data: {
      expected_token: before.edit_token,
      parameters: {
        industry: 'automotive',
        technology: 'can_fd',
        networks: [{
          id: 'lin-default',
          technology: 'LIN'
        }, {
          id: 'can-default',
          technology: 'CAN_FD'
        }, {
          id: 'eth-default',
          technology: 'ETHERNET'
        }]
      }
    }
  });
  expect(setup.ok()).toBe(true);
  let catalogReads = 0;
  await page.route('**/api/technologies', async route => {
    catalogReads += 1;
    if (catalogReads === 1) await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{"domains":['
    });else await route.continue();
  });
  await page.goto(`/studio?mode=parameters&project=${project}&technology=lin`);
  await expect(page.locator('input[name="lin_bitrate_bps"]')).toHaveValue('19,2 kbit/s');
  expect(catalogReads).toBe(2);
  await page.unrouteAll({
    behavior: 'wait'
  });
  await expect(page.getByRole('region', {
    name: 'Aktuelle Parameterbefunde'
  })).toBeVisible();
  const defaultSave = page.waitForResponse(response => response.url().endsWith('/api/engineering/workflow/parameters/defaults') && response.request().method() === 'POST');
  await page.getByRole('button', {
    name: 'Fehlende Simulationsvorgaben im Projekt speichern',
    exact: true
  }).click();
  const defaultResponse = await defaultSave;
  expect(defaultResponse.ok(), await defaultResponse.text()).toBe(true);
  await expect(page.getByText(/Parameterherkunft · [1-9]\d* gespeicherte Simulationsannahmen/)).toBeVisible();
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  const assumptions = saved.parameters.simulation_parameter_assumptions;
  expect(assumptions.lin.values.lin_bitrate_bps).toBe(19200);
  expect(assumptions.can_fd.values.arbitration_bitrate).toBe(500000);
  expect(assumptions.can_fd.values.data_bitrate).toBe(2000000);
  expect(assumptions.can_fd.values.can_fd_brs).toBe(true);
  expect(assumptions.ethernet.values.bitrate).toBe(1000000000);
  expect(assumptions.can_fd.provenance.data_bitrate.hardware_evidence).toBe(false);
  expect(saved.parameter_storage.source).toBe('PROJECT_USER_DEFINED_VALUES');
  const stored = await page.request.get('/api/engineering/workflow/parameters/user-defined-values', {
    headers
  });
  expect(stored.ok()).toBe(true);
  await page.goto(`/studio?mode=parameters&project=${project}&technology=can_fd`);
  await expect(page.locator('input[name="arbitration_bitrate"]')).toHaveValue('500 kbit/s');
  await expect(page.locator('input[name="data_bitrate"]')).toHaveValue('2 Mbit/s');
  await expect(page.locator('input[name="can_fd_brs"]')).toBeChecked();
  await page.reload();
  await expect(page.locator('input[name="data_bitrate"]')).toHaveValue('2 Mbit/s');
  await page.goto(`/studio?mode=parameters&project=${project}&technology=ethernet`);
  await expect(page.locator('input[name="bitrate"]')).toHaveValue('1 Gbit/s');
  await page.locator('input[name="bitrate"]').fill('0,1 Gbit/s');
  const saveRate = page.waitForResponse(r => r.url().endsWith('/api/engineering/workflow/parameters') && r.request().method() === 'PATCH');
  await page.getByRole('button', {
    name: 'Parameter speichern →',
    exact: true
  }).click();
  expect((await saveRate).ok()).toBe(true);
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  const edited = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  expect(edited.parameters.simulation_parameter_assumptions.ethernet.values.bitrate).toBe(100000000);
  expect(edited.parameters.simulation_parameter_assumptions.lin.values.lin_bitrate_bps).toBe(19200);
  expect(edited.parameters.simulation_parameter_assumptions.can_fd.values.data_bitrate).toBe(2000000);
  await page.reload();
  await expect(page.locator('input[name="bitrate"]')).toHaveValue('100 Mbit/s');
  // Invalid reads must expose a recovery action and preserve real saved data.
  let invalidReads = 0;
  await page.route('**/api/technologies', async route => {
    invalidReads += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{}'
    });
  });
  await page.reload();
  await expect(page.getByRole('alert').filter({
    hasText: 'Technologieprofile konnten nicht geladen werden'
  })).toBeVisible();
  expect(invalidReads).toBe(2);
  await page.unrouteAll({
    behavior: 'wait'
  });
  await page.getByRole('button', {
    name: 'Technologieprofile erneut laden',
    exact: true
  }).click();
  await expect(page.locator('input[name="bitrate"]')).toHaveValue('100 Mbit/s');
  expect((await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json()).parameters).toEqual(edited.parameters);
});

// Real isolated persistence and parameter-view regressions; not nine-stage completion proof.
test('unconfirmed project can select every registered bus without an Automotive fallback @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-catalog-' + randomUUID();
  const headers = {
    'X-Project-ID': project
  };
  const catalog = await (await page.request.get('/api/technologies')).json();
  await page.goto(`/studio?mode=parameters&project=${project}`);
  await expect(page.getByRole('heading', {
    name: 'Branche und Technologie auswählen'
  })).toBeVisible();
  await expect(page.getByLabel('Anwendungsbereich auswählen')).toHaveValue('');
  const bus = page.getByLabel('Bus / Protokoll auswählen');
  await expect(bus.locator('option')).toHaveCount(catalog.technology_count + 1);
  const search = page.getByRole('searchbox', {
    name: 'Bus / Protokoll suchen'
  });
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
  await expect(clock).toHaveValue('100 kbit/s');
  await expect(page.getByText('UNVERIFIED · Profilvorschlag').first()).toBeVisible();
  await expect(page.getByText(/Referenz-Obergrenzen, keine bestätigte Busfrequenz: Standard ≤ 100 kbit\/s/)).toBeVisible();
  expect(await clock.evaluate(input => input.checkValidity())).toBe(true);
  await clock.fill('0');
  expect(await clock.evaluate(input => input.checkValidity())).toBe(false);
  await clock.fill('400000');
  const invalid = await page.locator('form.config-panel').evaluate(form => [...form.elements].filter(element => element instanceof HTMLInputElement && !element.checkValidity()).map(element => element.name));
  expect(invalid).toEqual([]);
  // HTML bounds alone do not establish the mode/rate relationship: STANDARD
  // at 400 kbit/s must be rejected by the native profile without persistence.
  const beforeInvalid = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  const invalidResponse = page.waitForResponse(r => r.url().includes('/api/engineering/workflow/parameters') && r.request().method() === 'PATCH');
  await page.getByRole('button', {
    name: 'Parameter speichern →',
    exact: true
  }).click();
  const rejected = await invalidResponse;
  expect(rejected.status()).toBe(400);
  expect(JSON.stringify(await rejected.json())).toContain('TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH');
  await expect(page.locator('.notice.error')).toContainText('TECHNOLOGY_PARAMETER_DEPENDENCY_MISMATCH');
  const afterInvalid = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  expect(afterInvalid.parameters).toEqual(beforeInvalid.parameters);
  expect(afterInvalid.edit_token).toBe(beforeInvalid.edit_token);
  await revealParameter(page, 'i2c_mode');
  await page.locator('select[name="i2c_mode"]').selectOption('FAST');
  await page.getByRole('button', {
    name: 'Parameter speichern →',
    exact: true
  }).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  expect(saved.parameters.industry).toBe('custom');
  expect(saved.parameters.technology).toBe('i2c');
  expect(saved.parameters.target_bus_load_percent).toBe(60);
  expect(saved.parameters.technology_parameters.i2c.values).toMatchObject({
    i2c_mode: 'FAST',
    bitrate: 400000
  });
  await page.reload();
  await expect(page.locator('#domain')).toHaveValue('custom');
  await expect(page.locator('#technology')).toHaveValue('i2c');
  await expect(page.locator('select[name="i2c_mode"]')).toHaveValue('FAST');
  await expect(clock).toHaveValue('400 kbit/s');
});
test('CAN-FD scenario defaults survive real save and reload without hardware confirmation @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-simulation-defaults-' + randomUUID();
  const headers = {
    'X-Project-ID': project
  };
  const legacy = await page.request.patch('/api/engineering/workflow/parameters', {
    headers,
    data: {
      parameters: {
        can_clock_hz: 40000000,
        parameter_provenance: {
          can_clock_hz: {
            source: 'TECHNOLOGY_DEFAULT',
            status: 'REVIEW_REQUIRED',
            value: 40000000
          }
        }
      }
    }
  });
  expect(legacy.ok(), await legacy.text()).toBe(true);
  await page.goto(`/studio?mode=parameters&project=${project}`);
  await page.getByLabel('Bus / Protokoll auswählen').selectOption('can_fd');
  await page.getByLabel('Anwendungsbereich auswählen').selectOption('automotive');
  await expect(page.locator('[name="arbitration_bitrate"]')).toHaveValue('500 kbit/s');
  await expect(page.locator('[name="data_bitrate"]')).toHaveValue('2 Mbit/s');
  await expect(page.locator('[name="payload_bytes"]')).toHaveValue('8');
  const clock = page.locator('[name="can_clock_hz"]');
  await expect(clock).toHaveValue('40000000');
  await expect(page.getByText('SIMULATIONSANNAHME · Kein Gerätenachweis').first()).toBeVisible();
  await page.getByRole('button', {
    name: 'Parameter speichern →',
    exact: true
  }).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  const assumptions = saved.parameters.simulation_parameter_assumptions.can_fd;
  expect(assumptions.values).toMatchObject({
    arbitration_bitrate: 500000,
    data_bitrate: 2000000,
    can_clock_hz: 40000000,
    payload_bytes: 8
  });
  expect(assumptions.provenance.can_clock_hz).toMatchObject({
    source: 'NIS_SIMULATION_ASSUMPTION',
    status: 'ASSUMED',
    technology: 'can_fd',
    hardware_evidence: false,
    value: 40000000
  });
  expect(saved.parameters.technology_parameters.can_fd.values.can_clock_hz).toBeUndefined();
  expect(saved.parameters.can_clock_hz).toBeUndefined();
  await page.reload();
  await expect(clock).toHaveValue('40000000');
  await revealParameter(page, 'can_clock_hz');
  await clock.fill('80000000');
  await page.getByRole('button', {
    name: 'Parameter speichern →',
    exact: true
  }).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  await page.reload();
  await expect(clock).toHaveValue('80000000');
  const updated = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  expect(updated.parameters.simulation_parameter_assumptions.can_fd.provenance.can_clock_hz.hardware_evidence).toBe(false);
  expect(updated.parameter_storage.source).toBe('PROJECT_USER_DEFINED_VALUES');
  const userValues = await (await page.request.get('/api/engineering/workflow/parameters/user-defined-values', {
    headers
  })).json();
  expect(userValues.project_id).toBe(project);
  expect(userValues.value_origin).toBe('USER_DEFINED_VALUE');
  expect(userValues.parameters.simulation_parameter_assumptions.can_fd.values.can_clock_hz).toBe(80000000);
  expect(userValues.parameters.technology_defaults).toBeUndefined();
  expect(userValues.parameters.defaults_source).toBeUndefined();
});
test('saved confirmed wizard context proposes its bus without inventing parameter confirmation @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-wizard-bus-' + randomUUID();
  const headers = {
    'X-Project-ID': project
  };
  const seeded = await page.request.patch('/api/engineering/workflow/context?view=summary', {
    headers,
    data: {
      agent_wizard_status: {
        confirmed_at: '2026-09-30T11:32:50Z',
        model_type: 'custom',
        communication_system_counts: [{
          id: 'i2c',
          count: 1
        }]
      }
    }
  });
  expect(seeded.ok(), await seeded.text()).toBe(true);
  await page.goto(`/studio?mode=parameters&project=${project}`);
  await expect(page.locator('#domain')).toHaveValue('custom');
  await expect(page.locator('#technology')).toHaveValue('i2c');
  await expect(page.getByText('UNVERIFIED · Keine bestätigte Technologieauswahl')).toBeVisible();
  const parameters = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  expect(parameters.parameters.technology).toBeUndefined();
});
test('mixed project shows exact LIN profile, rejects 2M and preserves CAN-FD while saving LIN @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-rate-' + randomUUID();
  const headers = {
    'X-Project-ID': project
  };
  const initial = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  const parameters = {
    ...initial.parameters,
    industry: 'automotive',
    technology: 'can_fd',
    defaults_source: 'technology-registry',
    bitrate: 2000000,
    arbitration_bitrate: 500000,
    data_bitrate: 2000000,
    networks: [{
      id: 'lin-one',
      technology: 'LIN',
      name: 'LIN Test'
    }, {
      id: 'can-one',
      technology: 'CAN_FD',
      name: 'CAN Test'
    }]
  };
  const seeded = await page.request.patch('/api/engineering/workflow/parameters', {
    headers,
    data: {
      parameters,
      expected_token: initial.edit_token
    }
  });
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
  await expect(page.locator('.parameter-group-common #lin_bitrate_bps')).toBeVisible();
  await expect(page.locator('#lin_registered_source')).toHaveValue('');
  await expect(page.locator('#lin_registered_source')).not.toBeVisible();
  await page.getByRole('button', {
    name: 'Parameter speichern →',
    exact: true
  }).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  const noFakeSources = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  expect(noFakeSources.parameters.simulation_parameter_assumptions.lin.values.lin_registered_source).toBeUndefined();
  expect(noFakeSources.parameters.simulation_parameter_assumptions.lin.values.lin_commander_node_id).toBeUndefined();
  await page.locator('.parameter-details').filter({
    has: page.locator('#lin_registered_source')
  }).locator(':scope > summary').click();
  await expect(page.getByLabel('Profilquelle', {
    exact: true
  })).toHaveValue('');
  await page.getByLabel('Profilquelle', {
    exact: true
  }).fill('project:reviewed-lin-profile');
  await page.getByRole('button', {
    name: 'Parameter speichern →',
    exact: true
  }).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  await page.reload();
  await expect(page.locator('#technology')).toHaveValue('can_fd');
  await page.locator('#technology').selectOption('lin');
  await expect(page.locator('#lin_registered_source')).toHaveValue('project:reviewed-lin-profile');
  await expect(page.locator('.parameter-details[open]')).toHaveCount(0);
  await revealParameter(page, 'lin_edition');
  await page.locator('select[name="lin_edition"]').selectOption('LIN_2_2A_2010');
  await revealParameter(page, 'lin_physical_profile');
  await page.locator('select[name="lin_physical_profile"]').selectOption('LIN_2_2A_SINGLE_WIRE');
  await page.locator('#parameter-field-lin_bitrate_bps .parameter-default-details > summary').click();
  await page.locator('div[title]').filter({
    has: page.locator('#lin_bitrate_bps')
  }).getByRole('button', {
    name: 'Bedingten Standardwert übernehmen',
    exact: true
  }).click();
  await expect(page.locator('input[name="lin_bitrate_bps"]')).toHaveValue('19,2 kbit/s');
  await expect(page.locator('input[name="data_bitrate"]')).toHaveCount(0);
  const invalid = await page.request.patch('/api/engineering/workflow/parameters', {
    headers,
    data: {
      parameters: {
        ...parameters,
        technology_parameters: {
          lin: {
            values: {
              lin_edition: 'LIN_2_2A_2010',
              lin_physical_profile: 'LIN_2_2A_SINGLE_WIRE',
              lin_bitrate_bps: 2000000
            },
            provenance: Object.fromEntries(Object.entries({
              lin_edition: 'LIN_2_2A_2010',
              lin_physical_profile: 'LIN_2_2A_SINGLE_WIRE',
              lin_bitrate_bps: 2000000
            }).map(([key, value]) => [key, {
              source: 'USER_CONFIRMED',
              status: 'CONFIRMED',
              value
            }]))
          }
        }
      }
    }
  });
  expect(invalid.status()).toBe(400);
  await page.locator('input[name="lin_bitrate_bps"]').fill('9,6 kbit/s');
  const response = page.waitForResponse(r => r.url().includes('/api/engineering/workflow/parameters') && r.request().method() === 'PATCH');
  await page.getByRole('button', {
    name: 'Parameter speichern →',
    exact: true
  }).click();
  expect((await response).ok()).toBe(true);
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  expect(saved.parameters.networks).toEqual(parameters.networks);
  expect(saved.parameters.technology).toBe('can_fd');
  expect(saved.parameters.data_bitrate).toBe(2000000);
  expect(saved.parameters.simulation_parameter_assumptions.lin.values.lin_bitrate_bps).toBe(9600);
  expect(saved.parameters.simulation_parameter_assumptions.lin.provenance.lin_bitrate_bps).toMatchObject({
    status: 'ASSUMED',
    hardware_evidence: false
  });
  await page.reload();
  await expect(page.locator('#technology')).toHaveValue('can_fd');
  await page.locator('#technology').selectOption('lin');
  await expect(page.locator('input[name="lin_bitrate_bps"]')).toHaveValue('9,6 kbit/s');
  await page.locator('#technology').selectOption('can_fd');
  await expect(page.locator('input[name="data_bitrate"]')).toHaveValue('2 Mbit/s');
});
test('stale parameter revision rejects the real write and preserves confirmed rates @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-rate-conflict-' + randomUUID();
  const headers = {
    'X-Project-ID': project
  };
  const first = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  const parameters = {
    ...first.parameters,
    technology: 'lin',
    bitrate: 19200
  };
  const saved = await page.request.patch('/api/engineering/workflow/parameters', {
    headers,
    data: {
      parameters,
      expected_token: first.edit_token
    }
  });
  expect(saved.ok(), await saved.text()).toBe(true);
  const conflict = await page.request.patch('/api/engineering/workflow/parameters', {
    headers,
    data: {
      parameters: {
        ...parameters,
        bitrate: 9600
      },
      expected_token: first.edit_token
    }
  });
  expect(conflict.status()).toBe(409);
  const current = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  expect(current.parameters.bitrate).toBe(19200);
});
test('every bus exposes its own server defaults in the actual parameter form @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-catalog-defaults-' + randomUUID();
  const catalog = await (await page.request.get('/api/technologies')).json();
  const profiles = new Map(catalog.domains.flatMap(domain => domain.technologies).map(profile => [profile.id, profile]));
  expect(profiles.size).toBe(catalog.technology_count);
  await page.goto(`/studio?mode=parameters&project=${project}`);
  const initialBus = page.getByLabel('Bus / Protokoll auswählen');
  await expect(initialBus.locator('option[value="i2c"]')).toHaveCount(1);
  await initialBus.selectOption('i2c');
  await page.getByLabel('Anwendungsbereich auswählen').selectOption('custom');
  for (const [id, profile] of profiles) {
    await page.locator('#technology').selectOption(id);
    for (const field of profile.parameter_schema.filter(item => ['bitrate', 'arbitration_bitrate', 'data_bitrate'].includes(item.key))) {
      const input = page.locator(`input[name="${field.key}"]`);
      await expect(input, `${id}/${field.key}`).not.toHaveValue('');
      expect(await input.evaluate(el => el.checkValidity()), `${id}/${field.key}`).toBe(true);
    }
    const empty = await page.locator('form.config-panel .parameter-groups').evaluate(groups => [...groups.querySelectorAll('input,select,textarea')].filter(element => (element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement) && element.type !== 'checkbox' && element.value === '').map(element => element.name));
    const references = profile.parameter_schema.filter(field => field.value_role && field.value_role !== 'CONFIGURATION' && field.simulation_default === null).map(field => field.key);
    expect(empty.filter(key => !references.includes(key)), id).toEqual([]);
    for (const key of references) {
      const control = page.locator(`[name="${key}"]`);
      if (await control.count()) await expect(control).toHaveValue('');else await expect(page.locator(`#parameter-field-${key}`)).toContainText('Nicht zutreffend für die gewählte Protokollkonfiguration.');
    }
    if (id === 'nmea2000') {
      await expect(page.locator('input[name="bitrate"]')).toHaveValue('250 kbit/s');
      await expect(page.locator('input[name="mtu_bytes"]')).toHaveCount(0);
    }
  }
  // Switching through the entire catalog is a review, not a persistence action.
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers: {
      'X-Project-ID': project
    }
  })).json();
  expect(saved.parameters.technology).toBeUndefined();
});
test('hardware editor uses the selected profile and saves proposals without inventing device confirmation @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-device-profile-' + randomUUID();
  const headers = {
    'X-Project-ID': project
  };
  const nodeResponse = await page.request.post('/api/engineering/hardware-nodes', {
    headers,
    data: {
      name: 'Review Controller',
      device_type: 'EmbeddedController',
      domain: 'embedded_systems'
    }
  });
  expect(nodeResponse.ok(), await nodeResponse.text()).toBe(true);
  const node = await nodeResponse.json();
  const portResponse = await page.request.post('/api/engineering/hardware-interfaces', {
    headers,
    data: {
      name: 'Device Review Port',
      hardware_node_id: node.id,
      technology: 'I2C',
      capabilities: {
        local_timing_evidence: {
          slave_address: '',
          confirmed: false
        }
      }
    }
  });
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
  await expect(page.locator('#edit_data_bitrate')).toHaveValue('2000000');
  await expect(page.locator('[name="edit_local_confirmed"]')).toHaveCount(0);
  await page.locator('#edit_technology').selectOption('I2C');
  await page.getByRole('button', {
    name: 'Änderungen speichern',
    exact: true
  }).click();
  await expect(page.locator('#edit_technology')).toHaveCount(0);
  const saved = await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`, {
    headers
  })).json();
  expect(saved.bitrate).toBe(100000);
  expect(saved.data_bitrate).toBeNull();
  expect(saved.capabilities.local_timing_evidence).toMatchObject({
    technology: 'I2C',
    i2c_mode: 'STANDARD',
    bitrate_bps: 100000,
    confirmed: false
  });
  expect(saved.capabilities.local_timing_evidence.slave_address).toBeNull();
  expect(saved.capabilities.simulation_parameter_assumptions.i2c.provenance.slave_address.hardware_evidence).toBe(false);
  // Existing verified device facts outrank standard proposals. A changed
  // device setting cannot silently reuse the old confirmation.
  const actual = await page.request.patch(`/api/engineering/hardware-interfaces/${port.id}`, {
    headers,
    data: {
      bitrate: 400000,
      capabilities: {
        ...saved.capabilities,
        local_timing_evidence: {
          evidence_scope: 'CONTROLLER_PORT',
          master_node_id: node.id,
          i2c_mode: 'FAST',
          bitrate_bps: 400000,
          confirmed: true,
          source: 'isolated-virtual-fixture:explicit-FAST-controller-port'
        }
      }
    }
  });
  expect(actual.ok(), await actual.text()).toBe(true);
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await expect(page.locator('#edit_local_i2c_mode')).toHaveValue('FAST');
  await expect(page.locator('#edit_local_bitrate_bps')).toHaveValue('400000');
  await expect(page.locator('[name="edit_local_confirmed"]')).toBeChecked();
  await page.getByRole('button', {
    name: 'Änderungen speichern',
    exact: true
  }).click();
  await expect(page.locator('#edit_technology')).toHaveCount(0);
  const preserved = await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`, {
    headers
  })).json();
  expect(preserved.capabilities.local_timing_evidence).toMatchObject({
    i2c_mode: 'FAST',
    bitrate_bps: 400000,
    confirmed: true
  });
  expect(preserved.capabilities.local_timing_evidence.slave_address).toBeNull();
  expect(preserved.capabilities.simulation_parameter_assumptions.i2c.provenance.slave_address.hardware_evidence).toBe(false);
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await page.locator('#edit_local_i2c_mode').selectOption('FAST_PLUS');
  await expect(page.locator('[name="edit_local_confirmed"]')).not.toBeChecked();
  await page.getByRole('button', {
    name: 'Änderungen speichern',
    exact: true
  }).click();
  await expect(page.locator('#edit_technology')).toHaveCount(0);
  const changed = await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`, {
    headers
  })).json();
  expect(changed.capabilities.local_timing_evidence).toMatchObject({
    i2c_mode: 'FAST_PLUS',
    confirmed: false
  });
});
test('CAN-FD device editor retains changed simulation rates separately from actual hardware @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-device-assumptions-' + randomUUID();
  const headers = {
    'X-Project-ID': project
  };
  const nodeResponse = await page.request.post('/api/engineering/hardware-nodes', {
    headers,
    data: {
      name: 'Scenario Controller',
      device_type: 'EmbeddedController'
    }
  });
  expect(nodeResponse.ok(), await nodeResponse.text()).toBe(true);
  const node = await nodeResponse.json();
  const portResponse = await page.request.post('/api/engineering/hardware-interfaces', {
    headers,
    data: {
      name: 'Scenario CAN Port',
      hardware_node_id: node.id,
      technology: 'CAN_FD'
    }
  });
  expect(portResponse.ok(), await portResponse.text()).toBe(true);
  const port = await portResponse.json();
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await expect(page.locator('#edit_bitrate')).toHaveValue('500000');
  await expect(page.locator('#edit_data_bitrate')).toHaveValue('2000000');
  await page.locator('#edit_bitrate').fill('250000');
  await page.locator('#edit_data_bitrate').fill('250000');
  await page.getByRole('button', {
    name: 'Änderungen speichern',
    exact: true
  }).click();
  await expect(page.locator('#edit_technology')).toHaveCount(0);
  const saved = await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`, {
    headers
  })).json();
  expect(saved.bitrate).toBeNull();
  expect(saved.data_bitrate).toBeNull();
  expect(saved.capabilities.simulation_parameter_assumptions.can_fd.values).toMatchObject({
    arbitration_bitrate: 250000,
    data_bitrate: 250000
  });
  expect(saved.capabilities.simulation_parameter_assumptions.can_fd.provenance.data_bitrate.hardware_evidence).toBe(false);
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await expect(page.locator('#edit_bitrate')).toHaveValue('250000');
  await expect(page.locator('#edit_data_bitrate')).toHaveValue('250000');
});
test('PWM device editor offers no retired transaction proof and preserves native driver configuration @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-pwm-editor-' + randomUUID();
  const headers = {
    'X-Project-ID': project
  };
  const nodeResponse = await page.request.post('/api/engineering/hardware-nodes', {
    headers,
    data: {
      name: 'PWM Review Controller',
      device_type: 'EmbeddedController',
      domain: 'embedded_systems'
    }
  });
  expect(nodeResponse.ok(), await nodeResponse.text()).toBe(true);
  const node = await nodeResponse.json();
  const portResponse = await page.request.post('/api/engineering/hardware-interfaces', {
    headers,
    data: {
      name: 'PWM Output',
      hardware_node_id: node.id,
      technology: 'PWM',
      capabilities: {
        technology_parameters: {
          pwm_profile: 'LINUX_STATE_6_18',
          pwm_period_ns: 2000000,
          pwm_duty_ns: 700000,
          pwm_polarity: 'INVERSED',
          pwm_enabled: true,
          pwm_device_source: 'isolated-virtual-PWM-driver'
        }
      }
    }
  });
  expect(portResponse.ok(), await portResponse.text()).toBe(true);
  const port = await portResponse.json();
  await page.goto(`/studio/engineering?project=${project}&resource=hardware-interfaces&object=${port.id}&edit=1`);
  await expect(page.locator('#edit_technology')).toHaveValue('PWM');
  // Wait for the selected profile, not only the initial editor skeleton.
  const catalog = await (await page.request.get('/api/technologies')).json();
  expect(catalog.domains.flatMap(domain => domain.technologies).find(profile => profile.id === 'pwm').local_timing_schema).toEqual([]);
  for (const field of ['pwm_frequency_hz', 'update_bound_ms', 'capture_bound_ms']) await expect(page.locator(`#edit_local_${field}`)).toHaveCount(0);
  await expect(page.locator('#edit_bitrate')).toHaveCount(0);
  await expect(page.locator('#edit_data_bitrate')).toHaveCount(0);
  await expect(page.locator('[name="edit_local_confirmed"]')).toHaveCount(0);
  await page.locator('#edit_name').fill('Reviewed PWM Output');
  await page.getByRole('button', {
    name: 'Änderungen speichern',
    exact: true
  }).click();
  await expect(page.locator('#edit_technology')).toHaveCount(0);
  const saved = await (await page.request.get(`/api/engineering/hardware-interfaces/${port.id}`, {
    headers
  })).json();
  expect(saved.name).toBe('Reviewed PWM Output');
  expect(saved.capabilities).toEqual(port.capabilities);
  expect(saved.capabilities.local_timing_evidence).toBeUndefined();
  expect(saved.bitrate).toBeNull();
  expect(saved.data_bitrate).toBeNull();
});
test('actual uint64 protocol value survives legacy numeric JSON, form edit, SQL persistence and reload @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-uint64-' + randomUUID();
  const headers = {
    'X-Project-ID': project,
    'Content-Type': 'application/json'
  };
  const initial = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  const maximum = '18446744073709551615';
  const seed = JSON.stringify({
    parameters: {
      industry: 'custom',
      technology: 'sparkplug_b',
      spb_alias: '__EXACT_INTEGER__',
      parameter_provenance: {
        spb_alias: {
          value: '__EXACT_INTEGER__',
          source: 'USER_CONFIRMED',
          status: 'CONFIRMED'
        }
      }
    },
    expected_token: initial.edit_token
  }).replaceAll('"__EXACT_INTEGER__"', maximum);
  const seeded = await page.request.patch('/api/engineering/workflow/parameters', {
    headers,
    data: seed
  });
  expect(seeded.ok(), await seeded.text()).toBe(true);
  await page.goto(`/studio?mode=parameters&project=${project}`);
  await expect(page.locator('#technology')).toHaveValue('sparkplug_b');
  await expect(page.locator('#spb_alias')).toHaveAttribute('type', 'text');
  await expect(page.locator('#spb_alias')).toHaveValue(maximum);
  const catalog = await (await page.request.get('/api/technologies')).json();
  const profile = catalog.domains.flatMap(d => d.technologies).find(p => p.id === 'sparkplug_b');
  for (const field of profile.parameter_schema.filter(f => f.required && f.type === 'text')) {
    await revealParameter(page, field.key);
    await page.locator(`[name="${field.key}"]`).fill('isolated-test-source');
  }
  const edited = '18446744073709551614';
  await revealParameter(page, 'spb_alias');
  await page.locator('#spb_alias').fill(edited);
  await page.getByRole('button', {
    name: 'Parameter speichern →',
    exact: true
  }).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  expect(saved.parameters.technology_parameters.sparkplug_b.values.spb_alias).toBe(edited);
  expect(saved.parameters.technology_parameters.sparkplug_b.provenance.spb_alias.value).toBe(edited);
  await page.reload();
  await expect(page.locator('#spb_alias')).toHaveValue(edited);
});
test('proposal parameter link selects its technology and live findings highlight only affected fields @technology-review', async ({
  page
}) => {
  const project = 'nis-e2e-current-parameter-review-' + randomUUID();
  const headers = {
    'X-Project-ID': project
  };
  const networks = [{
    id: 'can-local',
    name: 'CAN Local',
    technology: 'CAN_FD'
  }, {
    id: 'lin-local',
    name: 'LIN Local',
    technology: 'LIN'
  }];
  const seed = await page.request.patch('/api/engineering/workflow/parameters', {
    headers,
    data: {
      parameters: {
        industry: 'custom',
        technology: 'can_fd',
        defaults_source: 'technology-registry',
        networks,
        formats: ['universal-jsonl']
      }
    }
  });
  expect(seed.ok(), await seed.text()).toBe(true);
  async function create(resource, data) {
    const response = await page.request.post('/api/engineering/' + resource, {
      headers,
      data
    });
    expect(response.ok(), await response.text()).toBe(true);
    return response.json();
  }
  const node = await create('hardware-nodes', {
    name: 'Review ECU',
    device_type: 'EmbeddedController'
  });
  for (const network of networks) {
    const port = await create('hardware-interfaces', {
      name: network.name,
      hardware_node_id: node.id,
      technology: network.technology,
      network_ref: network.id,
      bitrate: null,
      data_bitrate: null
    });
    const logical = await create('interfaces', {
      name: network.name,
      hardware_node_id: node.id,
      interface_type: network.technology
    });
    await create('messages', {
      name: network.name + ' Status',
      interface_id: logical.id,
      hardware_interface_id: port.id,
      dlc: 1,
      cycle_ms: 100,
      direction: 'tx'
    });
  }
  const before = await (await page.request.get('/api/engineering/workflow/parameters/review', {
    headers
  })).json();
  expect(before.source).toBe('CURRENT_CANONICAL_MODEL');
  expect(before.findings.filter(f => f.technology === 'can_fd')).toHaveLength(1);
  await page.goto(`/studio?mode=parameters&project=${project}&technology=lin#parameter-findings`);
  await expect(page.locator('#technology')).toHaveValue('lin');
  await expect(page.getByRole('region', {
    name: 'Aktuelle Parameterbefunde'
  })).toContainText('1 für LIN');
  await expect(page.locator('#parameter-field-lin_bitrate_bps')).toHaveClass(/parameter-field-finding/);
  await expect(page.locator('#parameter-field-lin_device_source')).toHaveClass(/parameter-field-finding/);
  await page.getByRole('navigation', {
    name: 'Technologien mit Parameterbefunden'
  }).getByRole('button', {
    name: /CAN-FD/
  }).click();
  await expect(page.locator('#technology')).toHaveValue('can_fd');
  await expect(page.locator('#parameter-field-arbitration_bitrate')).toHaveClass(/parameter-field-finding/);
  await expect(page.locator('#parameter-field-data_bitrate')).toHaveClass(/parameter-field-finding/);
  await expect(page.locator('#parameter-field-can_clock_hz')).not.toHaveClass(/parameter-field-finding/);
  const confirm = page.getByRole('form', {
    name: 'CAN-FD-Netze bestätigen'
  });
  await revealParameter(page, 'can_clock_hz');
  await page.locator('[name="can_clock_hz"]').fill('80000000');
  await expect(confirm.getByRole('button', {
    name: 'Für 1 Netze bestätigen & erneut prüfen',
    exact: true
  })).toBeDisabled();
  await expect(page.getByRole('region', {
    name: 'Aktuelle Parameterbefunde'
  })).toContainText('Speichere zuerst die Änderungen');
  await page.getByRole('button', {
    name: 'Parameter speichern →',
    exact: true
  }).click();
  await expect(confirm.getByRole('button', {
    name: 'Für 1 Netze bestätigen & erneut prüfen',
    exact: true
  })).toBeEnabled();
  // Saving a marked scenario must remove false missing-rate highlights without
  // inventing a device qualification or requiring a separate rate confirmation.
  await expect(page.locator('#parameter-field-arbitration_bitrate')).not.toHaveClass(/parameter-field-finding/);
  await expect(page.locator('#parameter-field-data_bitrate')).not.toHaveClass(/parameter-field-finding/);
  await expect(page.getByRole('region', {
    name: 'Auslegung mit gespeicherten Simulationswerten'
  })).toContainText('1 von 1');
  const scenarioReview = await (await page.request.get('/api/engineering/workflow/parameters/review', {
    headers
  })).json();
  const canScenario = scenarioReview.simulation_capacity.find(row => row.technology === 'can_fd');
  expect(canScenario).toMatchObject({
    status: 'FEASIBLE_UNDER_ASSUMPTIONS',
    hardware_evidence: false,
    functional_timing_accepted: false,
    rates: {
      arbitration_bitrate: 500000,
      data_bitrate: 2000000
    }
  });
  expect(canScenario.load_percent).toBeGreaterThan(0);
  expect(scenarioReview.findings.find(row => row.technology === 'can_fd')).toMatchObject({
    code: 'CAPACITY_DEVICE_EVIDENCE_MISSING',
    severity: 'INFO',
    simulation_parameters_usable: true,
    hardware_evidence: false
  });
  await expect(page.getByText(/Hinweis · .*offenem Gerätenachweis · kein Simulationsblocker/)).toBeVisible();
  await page.goto(`/studio?mode=parameters&project=${project}&technology=can_fd#parameter-findings`);
  await expect(page.locator('#parameter-field-arbitration_bitrate')).not.toHaveClass(/parameter-field-finding/);
  await expect(page.getByRole('region', {
    name: 'Auslegung mit gespeicherten Simulationswerten'
  })).toContainText('1 von 1');
  const repeated = await (await page.request.get('/api/engineering/workflow/parameters/review', {
    headers
  })).json();
  expect(repeated.simulation_capacity).toEqual(scenarioReview.simulation_capacity);
  await confirm.getByRole('spinbutton', {
    name: /Nominal Bitrate/
  }).fill('500000');
  await confirm.getByRole('spinbutton', {
    name: /Data Bitrate/
  }).fill('2000000');
  await confirm.getByRole('button', {
    name: 'Für 1 Netze bestätigen & erneut prüfen',
    exact: true
  }).click();
  await expect(page.getByRole('region', {
    name: 'Aktuelle Parameterbefunde'
  })).toContainText('0 für CAN-FD');
  await expect(page.locator('#parameter-field-arbitration_bitrate')).not.toHaveClass(/parameter-field-finding/);
  const after = await (await page.request.get('/api/engineering/workflow/parameters/review', {
    headers
  })).json();
  expect(after.findings.some(f => f.technology === 'can_fd')).toBe(false);
  expect(after.findings.some(f => f.technology === 'lin')).toBe(true);
  const saved = await (await page.request.get('/api/engineering/workflow/parameters', {
    headers
  })).json();
  expect(saved.parameters.networks.find(n => n.id === 'lin-local')).toEqual(networks[1]);
  expect(saved.parameters.simulation_parameter_assumptions.can_fd.values.can_clock_hz).toBe(80000000);
  await page.getByRole('navigation', {
    name: 'Technologien mit Parameterbefunden'
  }).getByRole('button', {
    name: /LIN/
  }).click();
  const linConfirm = page.getByRole('form', {
    name: 'LIN-Netze bestätigen'
  });
  await linConfirm.getByRole('spinbutton', {
    name: /bit.*rate/i
  }).fill('19200');
  await linConfirm.getByRole('button', {
    name: 'Für 1 Netze bestätigen & erneut prüfen',
    exact: true
  }).click();
  await expect(page.locator('#parameter-field-lin_bitrate_bps')).not.toHaveClass(/parameter-field-finding/);
  await expect(page.locator('#parameter-field-lin_device_source')).toHaveClass(/parameter-field-finding/);
  await expect(page.getByRole('region', {
    name: 'Aktuelle Parameterbefunde'
  })).toContainText('1 für LIN');
  await expect(linConfirm).toHaveCount(0);
  await expect(page.getByText('Die Rate fehlt als bestätigter Projektwert.', {
    exact: false
  })).toHaveCount(0);
  const foreign = await (await page.request.get('/api/engineering/workflow/parameters/review', {
    headers: {
      'X-Project-ID': 'nis-e2e-other-' + randomUUID()
    }
  })).json();
  expect(foreign.findings).toEqual([]);
});
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmFuZG9tVVVJRCIsInJldmVhbFBhcmFtZXRlciIsInBhZ2UiLCJrZXkiLCJncm91cCIsImxvY2F0b3IiLCJjb3VudCIsImdldEF0dHJpYnV0ZSIsImNsaWNrIiwic2NlbmFyaW8iLCJ0ZWNobm9sb2d5IiwiaWQiLCJyYXRlIiwiZGF0YSIsInByb2plY3QiLCJoZWFkZXJzIiwibm9kZVJlc3BvbnNlIiwicmVxdWVzdCIsInBvc3QiLCJuYW1lIiwiZGV2aWNlX3R5cGUiLCJvayIsInRleHQiLCJ0b0JlIiwibm9kZSIsImpzb24iLCJnb3RvIiwiZGlhbG9nIiwidG9CZVZpc2libGUiLCJmaWxsIiwiZ2V0QnlSb2xlIiwiZXhhY3QiLCJzZWxlY3RPcHRpb24iLCJ0b0JlRW5hYmxlZCIsInRvSGF2ZVZhbHVlIiwidG9IYXZlQ291bnQiLCJnZXRCeVRleHQiLCJjcmVhdGVkUmVzcG9uc2UiLCJ3YWl0Rm9yUmVzcG9uc2UiLCJyZXNwb25zZSIsInVybCIsImVuZHNXaXRoIiwibWV0aG9kIiwicG9ydCIsImJpdHJhdGUiLCJ0b0JlTnVsbCIsImRhdGFfYml0cmF0ZSIsImNhcGFiaWxpdGllcyIsInNpbXVsYXRpb25fcGFyYW1ldGVyX2Fzc3VtcHRpb25zIiwidmFsdWVzIiwiTnVtYmVyIiwicHJvdmVuYW5jZSIsInRvTWF0Y2hPYmplY3QiLCJzb3VyY2UiLCJoYXJkd2FyZV9ldmlkZW5jZSIsInJlbG9hZCIsInNhdmVkIiwiZ2V0IiwibGluIiwibGluX2JpdHJhdGVfYnBzIiwiYmVmb3JlIiwic2V0dXAiLCJwYXRjaCIsImV4cGVjdGVkX3Rva2VuIiwiZWRpdF90b2tlbiIsInBhcmFtZXRlcnMiLCJpbmR1c3RyeSIsIm5ldHdvcmtzIiwiY2F0YWxvZ1JlYWRzIiwicm91dGUiLCJmdWxmaWxsIiwic3RhdHVzIiwiY29udGVudFR5cGUiLCJib2R5IiwiY29udGludWUiLCJ1bnJvdXRlQWxsIiwiYmVoYXZpb3IiLCJkZWZhdWx0U2F2ZSIsImRlZmF1bHRSZXNwb25zZSIsImFzc3VtcHRpb25zIiwiY2FuX2ZkIiwiYXJiaXRyYXRpb25fYml0cmF0ZSIsImNhbl9mZF9icnMiLCJldGhlcm5ldCIsInBhcmFtZXRlcl9zdG9yYWdlIiwic3RvcmVkIiwidG9CZUNoZWNrZWQiLCJzYXZlUmF0ZSIsInIiLCJlZGl0ZWQiLCJpbnZhbGlkUmVhZHMiLCJmaWx0ZXIiLCJoYXNUZXh0IiwidG9FcXVhbCIsImNhdGFsb2ciLCJnZXRCeUxhYmVsIiwiYnVzIiwidGVjaG5vbG9neV9jb3VudCIsInNlYXJjaCIsImNsZWFyIiwic2VsZWN0ZWRCdXMiLCJzZWxlY3RCb3giLCJib3VuZGluZ0JveCIsInNlYXJjaEJveCIsIngiLCJ3aWR0aCIsImNsb2NrIiwiZmlyc3QiLCJldmFsdWF0ZSIsImlucHV0IiwiY2hlY2tWYWxpZGl0eSIsImludmFsaWQiLCJmb3JtIiwiZWxlbWVudHMiLCJlbGVtZW50IiwiSFRNTElucHV0RWxlbWVudCIsIm1hcCIsImJlZm9yZUludmFsaWQiLCJpbnZhbGlkUmVzcG9uc2UiLCJpbmNsdWRlcyIsInJlamVjdGVkIiwiSlNPTiIsInN0cmluZ2lmeSIsInRvQ29udGFpbiIsInRvQ29udGFpblRleHQiLCJhZnRlckludmFsaWQiLCJ0YXJnZXRfYnVzX2xvYWRfcGVyY2VudCIsInRlY2hub2xvZ3lfcGFyYW1ldGVycyIsImkyYyIsImkyY19tb2RlIiwibGVnYWN5IiwiY2FuX2Nsb2NrX2h6IiwicGFyYW1ldGVyX3Byb3ZlbmFuY2UiLCJ2YWx1ZSIsInBheWxvYWRfYnl0ZXMiLCJ0b0JlVW5kZWZpbmVkIiwidXBkYXRlZCIsInVzZXJWYWx1ZXMiLCJwcm9qZWN0X2lkIiwidmFsdWVfb3JpZ2luIiwidGVjaG5vbG9neV9kZWZhdWx0cyIsImRlZmF1bHRzX3NvdXJjZSIsInNlZWRlZCIsImFnZW50X3dpemFyZF9zdGF0dXMiLCJjb25maXJtZWRfYXQiLCJtb2RlbF90eXBlIiwiY29tbXVuaWNhdGlvbl9zeXN0ZW1fY291bnRzIiwiaW5pdGlhbCIsIlByb21pc2UiLCJyZXNvbHZlIiwic2V0VGltZW91dCIsIm5vdCIsIm5vRmFrZVNvdXJjZXMiLCJsaW5fcmVnaXN0ZXJlZF9zb3VyY2UiLCJsaW5fY29tbWFuZGVyX25vZGVfaWQiLCJoYXMiLCJsaW5fZWRpdGlvbiIsImxpbl9waHlzaWNhbF9wcm9maWxlIiwiT2JqZWN0IiwiZnJvbUVudHJpZXMiLCJlbnRyaWVzIiwiY29uZmxpY3QiLCJjdXJyZW50IiwicHJvZmlsZXMiLCJNYXAiLCJkb21haW5zIiwiZmxhdE1hcCIsImRvbWFpbiIsInRlY2hub2xvZ2llcyIsInByb2ZpbGUiLCJzaXplIiwiaW5pdGlhbEJ1cyIsImZpZWxkIiwicGFyYW1ldGVyX3NjaGVtYSIsIml0ZW0iLCJlbCIsImVtcHR5IiwiZ3JvdXBzIiwicXVlcnlTZWxlY3RvckFsbCIsIkhUTUxTZWxlY3RFbGVtZW50IiwiSFRNTFRleHRBcmVhRWxlbWVudCIsInR5cGUiLCJyZWZlcmVuY2VzIiwidmFsdWVfcm9sZSIsInNpbXVsYXRpb25fZGVmYXVsdCIsImNvbnRyb2wiLCJwb3J0UmVzcG9uc2UiLCJoYXJkd2FyZV9ub2RlX2lkIiwibG9jYWxfdGltaW5nX2V2aWRlbmNlIiwic2xhdmVfYWRkcmVzcyIsImNvbmZpcm1lZCIsImJpdHJhdGVfYnBzIiwiYWN0dWFsIiwiZXZpZGVuY2Vfc2NvcGUiLCJtYXN0ZXJfbm9kZV9pZCIsInByZXNlcnZlZCIsImNoYW5nZWQiLCJwd21fcHJvZmlsZSIsInB3bV9wZXJpb2RfbnMiLCJwd21fZHV0eV9ucyIsInB3bV9wb2xhcml0eSIsInB3bV9lbmFibGVkIiwicHdtX2RldmljZV9zb3VyY2UiLCJmaW5kIiwibG9jYWxfdGltaW5nX3NjaGVtYSIsIm1heGltdW0iLCJzZWVkIiwic3BiX2FsaWFzIiwicmVwbGFjZUFsbCIsInRvSGF2ZUF0dHJpYnV0ZSIsImQiLCJwIiwiZiIsInJlcXVpcmVkIiwic3BhcmtwbHVnX2IiLCJmb3JtYXRzIiwiY3JlYXRlIiwicmVzb3VyY2UiLCJuZXR3b3JrIiwibmV0d29ya19yZWYiLCJsb2dpY2FsIiwiaW50ZXJmYWNlX3R5cGUiLCJpbnRlcmZhY2VfaWQiLCJoYXJkd2FyZV9pbnRlcmZhY2VfaWQiLCJkbGMiLCJjeWNsZV9tcyIsImRpcmVjdGlvbiIsImZpbmRpbmdzIiwidG9IYXZlTGVuZ3RoIiwidG9IYXZlQ2xhc3MiLCJjb25maXJtIiwidG9CZURpc2FibGVkIiwic2NlbmFyaW9SZXZpZXciLCJjYW5TY2VuYXJpbyIsInNpbXVsYXRpb25fY2FwYWNpdHkiLCJyb3ciLCJmdW5jdGlvbmFsX3RpbWluZ19hY2NlcHRlZCIsInJhdGVzIiwibG9hZF9wZXJjZW50IiwidG9CZUdyZWF0ZXJUaGFuIiwiY29kZSIsInNldmVyaXR5Iiwic2ltdWxhdGlvbl9wYXJhbWV0ZXJzX3VzYWJsZSIsInJlcGVhdGVkIiwiYWZ0ZXIiLCJzb21lIiwibiIsImxpbkNvbmZpcm0iLCJmb3JlaWduIl0sInNvdXJjZXMiOlsidGVjaG5vbG9neS1wYXJhbWV0ZXItcmV2aWV3LnNwZWMudHMiXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgdGVzdCwgZXhwZWN0IH0gZnJvbSAncGxheXdyaWdodC90ZXN0JztcclxuaW1wb3J0IHsgcmFuZG9tVVVJRCB9IGZyb20gJ25vZGU6Y3J5cHRvJztcclxuaW1wb3J0IHR5cGUgeyBQYWdlIH0gZnJvbSAncGxheXdyaWdodC90ZXN0JztcclxuXHJcbmFzeW5jIGZ1bmN0aW9uIHJldmVhbFBhcmFtZXRlcihwYWdlOlBhZ2UsIGtleTpzdHJpbmcpIHtcclxuICBjb25zdCBncm91cCA9IHBhZ2UubG9jYXRvcihgI3BhcmFtZXRlci1maWVsZC0ke2tleX1gKS5sb2NhdG9yKCd4cGF0aD1hbmNlc3Rvcjo6ZGV0YWlsc1sxXScpO1xyXG4gIGlmIChhd2FpdCBncm91cC5jb3VudCgpICYmIGF3YWl0IGdyb3VwLmdldEF0dHJpYnV0ZSgnb3BlbicpID09PSBudWxsKSBhd2FpdCBncm91cC5sb2NhdG9yKCc6c2NvcGUgPiBzdW1tYXJ5JykuY2xpY2soKTtcclxufVxyXG5cclxuZm9yIChjb25zdCBzY2VuYXJpbyBvZiBbXHJcbiAge3RlY2hub2xvZ3k6J0xJTicsaWQ6J2xpbicscmF0ZTonMTkyMDAnLGtleTonbGluX2JpdHJhdGVfYnBzJ30sXHJcbiAge3RlY2hub2xvZ3k6J0NBTl9GRCcsaWQ6J2Nhbl9mZCcscmF0ZTonNTAwMDAwJyxrZXk6J2FyYml0cmF0aW9uX2JpdHJhdGUnLGRhdGE6JzIwMDAwMDAnfSxcclxuICB7dGVjaG5vbG9neTonRXRoZXJuZXQnLGlkOidldGhlcm5ldCcscmF0ZTonMTAwMDAwMDAwMCcsa2V5OidiaXRyYXRlJ30sXHJcbl0pIHRlc3QoYG1hbnVhbCAke3NjZW5hcmlvLnRlY2hub2xvZ3l9IHBvcnQgY3JlYXRpb24gdXNlcyBpdHMgbmF0aXZlIGRlZmF1bHRzIGFuZCBwcmVzZXJ2ZXMgZWRpdGVkIGFzc3VtcHRpb25zIEB0ZWNobm9sb2d5LXJldmlld2AsIGFzeW5jICh7cGFnZX0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0PSduaXMtZTJlLWNyZWF0ZS1yYXRlcy0nK3JhbmRvbVVVSUQoKSxoZWFkZXJzPXsnWC1Qcm9qZWN0LUlEJzpwcm9qZWN0fTtcclxuICBjb25zdCBub2RlUmVzcG9uc2U9YXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtbm9kZXMnLHtoZWFkZXJzLFxyXG4gICAgZGF0YTp7bmFtZTonTmF0aXZlIGRlZmF1bHQgY29udHJvbGxlcicsZGV2aWNlX3R5cGU6J0VtYmVkZGVkQ29udHJvbGxlcid9fSk7XHJcbiAgZXhwZWN0KG5vZGVSZXNwb25zZS5vaygpLGF3YWl0IG5vZGVSZXNwb25zZS50ZXh0KCkpLnRvQmUodHJ1ZSk7XHJcbiAgY29uc3Qgbm9kZT1hd2FpdCBub2RlUmVzcG9uc2UuanNvbigpLCBuYW1lPSdOYXRpdmUgJytzY2VuYXJpby50ZWNobm9sb2d5KycgcG9ydCc7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvL2VuZ2luZWVyaW5nP3Byb2plY3Q9JHtwcm9qZWN0fSZyZXNvdXJjZT1oYXJkd2FyZS1pbnRlcmZhY2VzJnBhcmVudD0ke25vZGUuaWR9JmNyZWF0ZT0xYCk7XHJcbiAgY29uc3QgZGlhbG9nPXBhZ2UubG9jYXRvcignZm9ybS5lbmctb2JqZWN0LXdpemFyZCcpO1xyXG4gIGF3YWl0IGV4cGVjdChkaWFsb2cpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmxvY2F0b3IoJyNuYW1lJykuZmlsbChuYW1lKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidXZWl0ZXInLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjdGVjaG5vbG9neScpLnNlbGVjdE9wdGlvbihzY2VuYXJpby50ZWNobm9sb2d5KTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonV2VpdGVyJyxleGFjdDp0cnVlfSkpLnRvQmVFbmFibGVkKCk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonV2VpdGVyJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmxvY2F0b3IoJyNiaXRyYXRlJykpLnRvSGF2ZVZhbHVlKHNjZW5hcmlvLnJhdGUpO1xyXG4gIGlmIChzY2VuYXJpby5kYXRhKSBhd2FpdCBleHBlY3QoZGlhbG9nLmxvY2F0b3IoJyNkYXRhX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoc2NlbmFyaW8uZGF0YSk7XHJcbiAgZWxzZSBhd2FpdCBleHBlY3QoZGlhbG9nLmxvY2F0b3IoJyNkYXRhX2JpdHJhdGUnKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonV2VpdGVyJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nLmxvY2F0b3IoJy5wcm9wb3NhbC13aXphcmQtcmV2aWV3JykuZ2V0QnlUZXh0KC9TSU1VTEFUSU9OU0FOTkFITUUvKSkudG9CZVZpc2libGUoKTtcclxuICBjb25zdCBjcmVhdGVkUmVzcG9uc2U9cGFnZS53YWl0Rm9yUmVzcG9uc2UocmVzcG9uc2U9PnJlc3BvbnNlLnVybCgpLmVuZHNXaXRoKCcvYXBpL2VuZ2luZWVyaW5nL2hhcmR3YXJlLWludGVyZmFjZXMnKSYmcmVzcG9uc2UucmVxdWVzdCgpLm1ldGhvZCgpPT09J1BPU1QnKTtcclxuICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidPYmpla3QgYW5sZWdlbicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgY29uc3QgcmVzcG9uc2U9YXdhaXQgY3JlYXRlZFJlc3BvbnNlO1xyXG4gIGV4cGVjdChyZXNwb25zZS5vaygpLGF3YWl0IHJlc3BvbnNlLnRleHQoKSkudG9CZSh0cnVlKTtcclxuICBjb25zdCBwb3J0PWF3YWl0IHJlc3BvbnNlLmpzb24oKTtcclxuICBleHBlY3QocG9ydC5iaXRyYXRlKS50b0JlTnVsbCgpO2V4cGVjdChwb3J0LmRhdGFfYml0cmF0ZSkudG9CZU51bGwoKTtcclxuICBjb25zdCBncm91cD1wb3J0LmNhcGFiaWxpdGllcy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9uc1tzY2VuYXJpby5pZF07XHJcbiAgZXhwZWN0KGdyb3VwLnZhbHVlc1tzY2VuYXJpby5rZXldKS50b0JlKE51bWJlcihzY2VuYXJpby5yYXRlKSk7XHJcbiAgZXhwZWN0KGdyb3VwLnByb3ZlbmFuY2Vbc2NlbmFyaW8ua2V5XSkudG9NYXRjaE9iamVjdCh7c291cmNlOidOSVNfU0lNVUxBVElPTl9BU1NVTVBUSU9OJyx0ZWNobm9sb2d5OnNjZW5hcmlvLmlkLGhhcmR3YXJlX2V2aWRlbmNlOmZhbHNlfSk7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvL2VuZ2luZWVyaW5nP3Byb2plY3Q9JHtwcm9qZWN0fSZyZXNvdXJjZT1oYXJkd2FyZS1pbnRlcmZhY2VzJm9iamVjdD0ke3BvcnQuaWR9JmVkaXQ9MWApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoc2NlbmFyaW8ucmF0ZSk7XHJcbiAgaWYgKHNjZW5hcmlvLmlkPT09J2xpbicpIHtcclxuICAgIGF3YWl0IHBhZ2UubG9jYXRvcignI2VkaXRfYml0cmF0ZScpLmZpbGwoJzk2MDAnKTtcclxuICAgIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOifDhG5kZXJ1bmdlbiBzcGVpY2hlcm4nLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gICAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfdGVjaG5vbG9neScpKS50b0hhdmVDb3VudCgwKTtcclxuICAgIGF3YWl0IHBhZ2UucmVsb2FkKCk7XHJcbiAgICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9iaXRyYXRlJykpLnRvSGF2ZVZhbHVlKCc5NjAwJyk7XHJcbiAgICBjb25zdCBzYXZlZD1hd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldChgL2FwaS9lbmdpbmVlcmluZy9oYXJkd2FyZS1pbnRlcmZhY2VzLyR7cG9ydC5pZH1gLHtoZWFkZXJzfSkpLmpzb24oKTtcclxuICAgIGV4cGVjdChzYXZlZC5iaXRyYXRlKS50b0JlTnVsbCgpO1xyXG4gICAgZXhwZWN0KHNhdmVkLmNhcGFiaWxpdGllcy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5saW4udmFsdWVzLmxpbl9iaXRyYXRlX2JwcykudG9CZSg5NjAwKTtcclxuICB9XHJcbn0pO1xyXG5cclxudGVzdCgnbmF0aXZlIHNpbXVsYXRpb24gcmF0ZXMgbG9hZCBhbmQgcGVyc2lzdCB3aXRob3V0IG1hbnVhbCByYXRlIGVudHJ5IG9yIGNlbnRyYWwtZGVmYXVsdCB3cml0ZXMgQHRlY2hub2xvZ3ktcmV2aWV3JywgYXN5bmMgKHtwYWdlfSkgPT4ge1xyXG4gIGNvbnN0IHByb2plY3Q9J25pcy1lMmUtbmF0aXZlLWRlZmF1bHRzLScrcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGhlYWRlcnM9eydYLVByb2plY3QtSUQnOnByb2plY3R9O1xyXG4gIGNvbnN0IGJlZm9yZT1hd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyx7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgY29uc3Qgc2V0dXA9YXdhaXQgcGFnZS5yZXF1ZXN0LnBhdGNoKCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLHtoZWFkZXJzLGRhdGE6e2V4cGVjdGVkX3Rva2VuOmJlZm9yZS5lZGl0X3Rva2VuLFxyXG4gICAgcGFyYW1ldGVyczp7aW5kdXN0cnk6J2F1dG9tb3RpdmUnLHRlY2hub2xvZ3k6J2Nhbl9mZCcsbmV0d29ya3M6W3tpZDonbGluLWRlZmF1bHQnLHRlY2hub2xvZ3k6J0xJTid9LFxyXG4gICAgICB7aWQ6J2Nhbi1kZWZhdWx0Jyx0ZWNobm9sb2d5OidDQU5fRkQnfSx7aWQ6J2V0aC1kZWZhdWx0Jyx0ZWNobm9sb2d5OidFVEhFUk5FVCd9XX19fSk7XHJcbiAgZXhwZWN0KHNldHVwLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgbGV0IGNhdGFsb2dSZWFkcyA9IDA7XHJcbiAgYXdhaXQgcGFnZS5yb3V0ZSgnKiovYXBpL3RlY2hub2xvZ2llcycsIGFzeW5jIHJvdXRlID0+IHtcclxuICAgIGNhdGFsb2dSZWFkcyArPSAxO1xyXG4gICAgaWYgKGNhdGFsb2dSZWFkcyA9PT0gMSkgYXdhaXQgcm91dGUuZnVsZmlsbCh7c3RhdHVzOiAyMDAsIGNvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicsIGJvZHk6ICd7XCJkb21haW5zXCI6Wyd9KTtcclxuICAgIGVsc2UgYXdhaXQgcm91dGUuY29udGludWUoKTtcclxuICB9KTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8/bW9kZT1wYXJhbWV0ZXJzJnByb2plY3Q9JHtwcm9qZWN0fSZ0ZWNobm9sb2d5PWxpbmApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJsaW5fYml0cmF0ZV9icHNcIl0nKSkudG9IYXZlVmFsdWUoJzE5LDIga2JpdC9zJyk7XHJcbiAgZXhwZWN0KGNhdGFsb2dSZWFkcykudG9CZSgyKTtcclxuICBhd2FpdCBwYWdlLnVucm91dGVBbGwoe2JlaGF2aW9yOiAnd2FpdCd9KTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicse25hbWU6J0FrdHVlbGxlIFBhcmFtZXRlcmJlZnVuZGUnfSkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3QgZGVmYXVsdFNhdmUgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5lbmRzV2l0aCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzL2RlZmF1bHRzJylcclxuICAgICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonRmVobGVuZGUgU2ltdWxhdGlvbnN2b3JnYWJlbiBpbSBQcm9qZWt0IHNwZWljaGVybicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgY29uc3QgZGVmYXVsdFJlc3BvbnNlID0gYXdhaXQgZGVmYXVsdFNhdmU7XHJcbiAgZXhwZWN0KGRlZmF1bHRSZXNwb25zZS5vaygpLCBhd2FpdCBkZWZhdWx0UmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgvUGFyYW1ldGVyaGVya3VuZnQgwrcgWzEtOV1cXGQqIGdlc3BlaWNoZXJ0ZSBTaW11bGF0aW9uc2FubmFobWVuLykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3Qgc2F2ZWQ9YXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGNvbnN0IGFzc3VtcHRpb25zPXNhdmVkLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnM7XHJcbiAgZXhwZWN0KGFzc3VtcHRpb25zLmxpbi52YWx1ZXMubGluX2JpdHJhdGVfYnBzKS50b0JlKDE5MjAwKTtcclxuICBleHBlY3QoYXNzdW1wdGlvbnMuY2FuX2ZkLnZhbHVlcy5hcmJpdHJhdGlvbl9iaXRyYXRlKS50b0JlKDUwMDAwMCk7XHJcbiAgZXhwZWN0KGFzc3VtcHRpb25zLmNhbl9mZC52YWx1ZXMuZGF0YV9iaXRyYXRlKS50b0JlKDIwMDAwMDApO1xyXG4gIGV4cGVjdChhc3N1bXB0aW9ucy5jYW5fZmQudmFsdWVzLmNhbl9mZF9icnMpLnRvQmUodHJ1ZSk7XHJcbiAgZXhwZWN0KGFzc3VtcHRpb25zLmV0aGVybmV0LnZhbHVlcy5iaXRyYXRlKS50b0JlKDEwMDAwMDAwMDApO1xyXG4gIGV4cGVjdChhc3N1bXB0aW9ucy5jYW5fZmQucHJvdmVuYW5jZS5kYXRhX2JpdHJhdGUuaGFyZHdhcmVfZXZpZGVuY2UpLnRvQmUoZmFsc2UpO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJfc3RvcmFnZS5zb3VyY2UpLnRvQmUoJ1BST0pFQ1RfVVNFUl9ERUZJTkVEX1ZBTFVFUycpO1xyXG4gIGNvbnN0IHN0b3JlZD1hd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMvdXNlci1kZWZpbmVkLXZhbHVlcycse2hlYWRlcnN9KTtcclxuICBleHBlY3Qoc3RvcmVkLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7cHJvamVjdH0mdGVjaG5vbG9neT1jYW5fZmRgKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCdpbnB1dFtuYW1lPVwiYXJiaXRyYXRpb25fYml0cmF0ZVwiXScpKS50b0hhdmVWYWx1ZSgnNTAwIGtiaXQvcycpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJkYXRhX2JpdHJhdGVcIl0nKSkudG9IYXZlVmFsdWUoJzIgTWJpdC9zJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cImNhbl9mZF9icnNcIl0nKSkudG9CZUNoZWNrZWQoKTtcclxuICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJkYXRhX2JpdHJhdGVcIl0nKSkudG9IYXZlVmFsdWUoJzIgTWJpdC9zJyk7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7cHJvamVjdH0mdGVjaG5vbG9neT1ldGhlcm5ldGApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJiaXRyYXRlXCJdJykpLnRvSGF2ZVZhbHVlKCcxIEdiaXQvcycpO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cImJpdHJhdGVcIl0nKS5maWxsKCcwLDEgR2JpdC9zJyk7XHJcbiAgY29uc3Qgc2F2ZVJhdGUgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyID0+IHIudXJsKCkuZW5kc1dpdGgoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycpICYmIHIucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUEFUQ0gnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonUGFyYW1ldGVyIHNwZWljaGVybiDihpInLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGV4cGVjdCgoYXdhaXQgc2F2ZVJhdGUpLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdUZWNobm9sb2dpZS0gdW5kIFRpbWluZy1QYXJhbWV0ZXIgZ2VzcGVpY2hlcnQuJykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3QgZWRpdGVkPWF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLHtoZWFkZXJzfSkpLmpzb24oKTtcclxuICBleHBlY3QoZWRpdGVkLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnMuZXRoZXJuZXQudmFsdWVzLmJpdHJhdGUpLnRvQmUoMTAwMDAwMDAwKTtcclxuICBleHBlY3QoZWRpdGVkLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnMubGluLnZhbHVlcy5saW5fYml0cmF0ZV9icHMpLnRvQmUoMTkyMDApO1xyXG4gIGV4cGVjdChlZGl0ZWQucGFyYW1ldGVycy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5jYW5fZmQudmFsdWVzLmRhdGFfYml0cmF0ZSkudG9CZSgyMDAwMDAwKTtcclxuICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJiaXRyYXRlXCJdJykpLnRvSGF2ZVZhbHVlKCcxMDAgTWJpdC9zJyk7XHJcbiAgLy8gSW52YWxpZCByZWFkcyBtdXN0IGV4cG9zZSBhIHJlY292ZXJ5IGFjdGlvbiBhbmQgcHJlc2VydmUgcmVhbCBzYXZlZCBkYXRhLlxyXG4gIGxldCBpbnZhbGlkUmVhZHMgPSAwO1xyXG4gIGF3YWl0IHBhZ2Uucm91dGUoJyoqL2FwaS90ZWNobm9sb2dpZXMnLCBhc3luYyByb3V0ZSA9PiB7XHJcbiAgICBpbnZhbGlkUmVhZHMgKz0gMTtcclxuICAgIGF3YWl0IHJvdXRlLmZ1bGZpbGwoe3N0YXR1czogMjAwLCBjb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLCBib2R5OiAne30nfSk7XHJcbiAgfSk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2FsZXJ0JykuZmlsdGVyKHtoYXNUZXh0OidUZWNobm9sb2dpZXByb2ZpbGUga29ubnRlbiBuaWNodCBnZWxhZGVuIHdlcmRlbid9KSkudG9CZVZpc2libGUoKTtcclxuICBleHBlY3QoaW52YWxpZFJlYWRzKS50b0JlKDIpO1xyXG4gIGF3YWl0IHBhZ2UudW5yb3V0ZUFsbCh7YmVoYXZpb3I6ICd3YWl0J30pO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7bmFtZTonVGVjaG5vbG9naWVwcm9maWxlIGVybmV1dCBsYWRlbicsIGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJiaXRyYXRlXCJdJykpLnRvSGF2ZVZhbHVlKCcxMDAgTWJpdC9zJyk7XHJcbiAgZXhwZWN0KChhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyx7aGVhZGVyc30pKS5qc29uKCkpLnBhcmFtZXRlcnMpXHJcbiAgICAudG9FcXVhbChlZGl0ZWQucGFyYW1ldGVycyk7XHJcbn0pO1xyXG5cclxuLy8gUmVhbCBpc29sYXRlZCBwZXJzaXN0ZW5jZSBhbmQgcGFyYW1ldGVyLXZpZXcgcmVncmVzc2lvbnM7IG5vdCBuaW5lLXN0YWdlIGNvbXBsZXRpb24gcHJvb2YuXHJcbnRlc3QoJ3VuY29uZmlybWVkIHByb2plY3QgY2FuIHNlbGVjdCBldmVyeSByZWdpc3RlcmVkIGJ1cyB3aXRob3V0IGFuIEF1dG9tb3RpdmUgZmFsbGJhY2sgQHRlY2hub2xvZ3ktcmV2aWV3JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWNhdGFsb2ctJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBoZWFkZXJzID0geyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9O1xyXG4gIGNvbnN0IGNhdGFsb2cgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS90ZWNobm9sb2dpZXMnKSkuanNvbigpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke3Byb2plY3R9YCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdoZWFkaW5nJywgeyBuYW1lOiAnQnJhbmNoZSB1bmQgVGVjaG5vbG9naWUgYXVzd8OkaGxlbicgfSkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlMYWJlbCgnQW53ZW5kdW5nc2JlcmVpY2ggYXVzd8OkaGxlbicpKS50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgY29uc3QgYnVzID0gcGFnZS5nZXRCeUxhYmVsKCdCdXMgLyBQcm90b2tvbGwgYXVzd8OkaGxlbicpO1xyXG4gIGF3YWl0IGV4cGVjdChidXMubG9jYXRvcignb3B0aW9uJykpLnRvSGF2ZUNvdW50KGNhdGFsb2cudGVjaG5vbG9neV9jb3VudCArIDEpO1xyXG4gIGNvbnN0IHNlYXJjaCA9IHBhZ2UuZ2V0QnlSb2xlKCdzZWFyY2hib3gnLCB7IG5hbWU6ICdCdXMgLyBQcm90b2tvbGwgc3VjaGVuJyB9KTtcclxuICBhd2FpdCBzZWFyY2guZmlsbCgnQ0FORkQnKTtcclxuICBhd2FpdCBleHBlY3QoYnVzLmxvY2F0b3IoJ29wdGlvblt2YWx1ZT1cImNhbl9mZFwiXScpKS50b0hhdmVDb3VudCgxKTtcclxuICBhd2FpdCBzZWFyY2guZmlsbCgncHJvZm5ldCcpO1xyXG4gIGF3YWl0IGV4cGVjdChidXMubG9jYXRvcignb3B0aW9uW3ZhbHVlPVwicHJvZmluZXRcIl0nKSkudG9IYXZlQ291bnQoMSk7XHJcbiAgYXdhaXQgc2VhcmNoLmNsZWFyKCk7XHJcbiAgYXdhaXQgZXhwZWN0KGJ1cy5sb2NhdG9yKCdvcHRpb24nKSkudG9IYXZlQ291bnQoY2F0YWxvZy50ZWNobm9sb2d5X2NvdW50ICsgMSk7XHJcbiAgYXdhaXQgYnVzLnNlbGVjdE9wdGlvbignaTJjJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeUxhYmVsKCdBbndlbmR1bmdzYmVyZWljaCBhdXN3w6RobGVuJykuc2VsZWN0T3B0aW9uKCdjdXN0b20nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZG9tYWluJykpLnRvSGF2ZVZhbHVlKCdjdXN0b20nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjdGVjaG5vbG9neScpKS50b0hhdmVWYWx1ZSgnaTJjJyk7XHJcbiAgY29uc3Qgc2VsZWN0ZWRCdXMgPSBwYWdlLmxvY2F0b3IoJyN0ZWNobm9sb2d5Jyk7XHJcbiAgY29uc3Qgc2VsZWN0Qm94ID0gYXdhaXQgc2VsZWN0ZWRCdXMuYm91bmRpbmdCb3goKTtcclxuICBjb25zdCBzZWFyY2hCb3ggPSBhd2FpdCBzZWFyY2guYm91bmRpbmdCb3goKTtcclxuICBleHBlY3Qoc2VsZWN0Qm94ICYmIHNlYXJjaEJveCAmJiBzZWFyY2hCb3gueCA+PSBzZWxlY3RCb3gueCArIHNlbGVjdEJveC53aWR0aCAtIDEpLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgc2VhcmNoLmZpbGwoJ3Byb2ZuZXQnKTtcclxuICBhd2FpdCBleHBlY3Qoc2VsZWN0ZWRCdXMubG9jYXRvcignb3B0aW9uW3ZhbHVlPVwicHJvZmluZXRcIl0nKSkudG9IYXZlQ291bnQoMSk7XHJcbiAgYXdhaXQgZXhwZWN0KHNlbGVjdGVkQnVzKS50b0hhdmVWYWx1ZSgnaTJjJyk7XHJcbiAgYXdhaXQgc2VhcmNoLmZpbGwoJ3p6enp6eicpO1xyXG4gIGF3YWl0IGV4cGVjdChzZWxlY3RlZEJ1cykudG9IYXZlVmFsdWUoJ2kyYycpO1xyXG4gIGF3YWl0IGV4cGVjdChzZWxlY3RlZEJ1cy5sb2NhdG9yKCdvcHRpb25bdmFsdWU9XCJfX25vX21hdGNoZXNcIl0nKSkudG9IYXZlQ291bnQoMSk7XHJcbiAgYXdhaXQgc2VhcmNoLmNsZWFyKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHNlbGVjdGVkQnVzLmxvY2F0b3IoJ29wdGlvbicpKS50b0hhdmVDb3VudChjYXRhbG9nLnRlY2hub2xvZ3lfY291bnQpO1xyXG4gIC8vIFRoZSBsb3dlc3QgcmVnaXN0ZXJlZCBJMkMgbW9kZSBpcyBzaG93biBhcyBhbiB1bmNvbmZpcm1lZCBwcm9wb3NhbC5cclxuICBjb25zdCBjbG9jayA9IHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cImJpdHJhdGVcIl0nKTtcclxuICBhd2FpdCBleHBlY3QoY2xvY2spLnRvSGF2ZVZhbHVlKCcxMDAga2JpdC9zJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdVTlZFUklGSUVEIMK3IFByb2ZpbHZvcnNjaGxhZycpLmZpcnN0KCkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KC9SZWZlcmVuei1PYmVyZ3Jlbnplbiwga2VpbmUgYmVzdMOkdGlndGUgQnVzZnJlcXVlbno6IFN0YW5kYXJkIOKJpCAxMDAga2JpdFxcL3MvKSkudG9CZVZpc2libGUoKTtcclxuICBleHBlY3QoYXdhaXQgY2xvY2suZXZhbHVhdGUoKGlucHV0OiBIVE1MSW5wdXRFbGVtZW50KSA9PiBpbnB1dC5jaGVja1ZhbGlkaXR5KCkpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IGNsb2NrLmZpbGwoJzAnKTtcclxuICBleHBlY3QoYXdhaXQgY2xvY2suZXZhbHVhdGUoKGlucHV0OiBIVE1MSW5wdXRFbGVtZW50KSA9PiBpbnB1dC5jaGVja1ZhbGlkaXR5KCkpKS50b0JlKGZhbHNlKTtcclxuICBhd2FpdCBjbG9jay5maWxsKCc0MDAwMDAnKTtcclxuICBjb25zdCBpbnZhbGlkID0gYXdhaXQgcGFnZS5sb2NhdG9yKCdmb3JtLmNvbmZpZy1wYW5lbCcpLmV2YWx1YXRlKGZvcm0gPT4gWy4uLihmb3JtIGFzIEhUTUxGb3JtRWxlbWVudCkuZWxlbWVudHNdXHJcbiAgICAuZmlsdGVyKGVsZW1lbnQgPT4gZWxlbWVudCBpbnN0YW5jZW9mIEhUTUxJbnB1dEVsZW1lbnQgJiYgIWVsZW1lbnQuY2hlY2tWYWxpZGl0eSgpKVxyXG4gICAgLm1hcChlbGVtZW50ID0+IChlbGVtZW50IGFzIEhUTUxJbnB1dEVsZW1lbnQpLm5hbWUpKTtcclxuICBleHBlY3QoaW52YWxpZCkudG9FcXVhbChbXSk7XHJcbiAgLy8gSFRNTCBib3VuZHMgYWxvbmUgZG8gbm90IGVzdGFibGlzaCB0aGUgbW9kZS9yYXRlIHJlbGF0aW9uc2hpcDogU1RBTkRBUkRcclxuICAvLyBhdCA0MDAga2JpdC9zIG11c3QgYmUgcmVqZWN0ZWQgYnkgdGhlIG5hdGl2ZSBwcm9maWxlIHdpdGhvdXQgcGVyc2lzdGVuY2UuXHJcbiAgY29uc3QgYmVmb3JlSW52YWxpZCA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLCB7IGhlYWRlcnMgfSkpLmpzb24oKTtcclxuICBjb25zdCBpbnZhbGlkUmVzcG9uc2UgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyID0+IHIudXJsKCkuaW5jbHVkZXMoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycpICYmIHIucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUEFUQ0gnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnUGFyYW1ldGVyIHNwZWljaGVybiDihpInLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xyXG4gIGNvbnN0IHJlamVjdGVkID0gYXdhaXQgaW52YWxpZFJlc3BvbnNlO1xyXG4gIGV4cGVjdChyZWplY3RlZC5zdGF0dXMoKSkudG9CZSg0MDApO1xyXG4gIGV4cGVjdChKU09OLnN0cmluZ2lmeShhd2FpdCByZWplY3RlZC5qc29uKCkpKS50b0NvbnRhaW4oJ1RFQ0hOT0xPR1lfUEFSQU1FVEVSX0RFUEVOREVOQ1lfTUlTTUFUQ0gnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcubm90aWNlLmVycm9yJykpLnRvQ29udGFpblRleHQoJ1RFQ0hOT0xPR1lfUEFSQU1FVEVSX0RFUEVOREVOQ1lfTUlTTUFUQ0gnKTtcclxuICBjb25zdCBhZnRlckludmFsaWQgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywgeyBoZWFkZXJzIH0pKS5qc29uKCk7XHJcbiAgZXhwZWN0KGFmdGVySW52YWxpZC5wYXJhbWV0ZXJzKS50b0VxdWFsKGJlZm9yZUludmFsaWQucGFyYW1ldGVycyk7XHJcbiAgZXhwZWN0KGFmdGVySW52YWxpZC5lZGl0X3Rva2VuKS50b0JlKGJlZm9yZUludmFsaWQuZWRpdF90b2tlbik7XHJcbiAgYXdhaXQgcmV2ZWFsUGFyYW1ldGVyKHBhZ2UsJ2kyY19tb2RlJyk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCdzZWxlY3RbbmFtZT1cImkyY19tb2RlXCJdJykuc2VsZWN0T3B0aW9uKCdGQVNUJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ1BhcmFtZXRlciBzcGVpY2hlcm4g4oaSJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ1RlY2hub2xvZ2llLSB1bmQgVGltaW5nLVBhcmFtZXRlciBnZXNwZWljaGVydC4nKSkudG9CZVZpc2libGUoKTtcclxuICBjb25zdCBzYXZlZCA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLCB7IGhlYWRlcnMgfSkpLmpzb24oKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy5pbmR1c3RyeSkudG9CZSgnY3VzdG9tJyk7XHJcbiAgZXhwZWN0KHNhdmVkLnBhcmFtZXRlcnMudGVjaG5vbG9neSkudG9CZSgnaTJjJyk7XHJcbiAgZXhwZWN0KHNhdmVkLnBhcmFtZXRlcnMudGFyZ2V0X2J1c19sb2FkX3BlcmNlbnQpLnRvQmUoNjApO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfcGFyYW1ldGVycy5pMmMudmFsdWVzKS50b01hdGNoT2JqZWN0KHtpMmNfbW9kZTonRkFTVCcsIGJpdHJhdGU6NDAwMDAwfSk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZG9tYWluJykpLnRvSGF2ZVZhbHVlKCdjdXN0b20nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjdGVjaG5vbG9neScpKS50b0hhdmVWYWx1ZSgnaTJjJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignc2VsZWN0W25hbWU9XCJpMmNfbW9kZVwiXScpKS50b0hhdmVWYWx1ZSgnRkFTVCcpO1xyXG4gIGF3YWl0IGV4cGVjdChjbG9jaykudG9IYXZlVmFsdWUoJzQwMCBrYml0L3MnKTtcclxufSk7XHJcblxyXG50ZXN0KCdDQU4tRkQgc2NlbmFyaW8gZGVmYXVsdHMgc3Vydml2ZSByZWFsIHNhdmUgYW5kIHJlbG9hZCB3aXRob3V0IGhhcmR3YXJlIGNvbmZpcm1hdGlvbiBAdGVjaG5vbG9neS1yZXZpZXcnLCBhc3luYyAoe3BhZ2V9KSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXNpbXVsYXRpb24tZGVmYXVsdHMtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBoZWFkZXJzID0geydYLVByb2plY3QtSUQnOnByb2plY3R9O1xyXG4gIGNvbnN0IGxlZ2FjeSA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wYXRjaCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyx7aGVhZGVycyxkYXRhOntwYXJhbWV0ZXJzOntjYW5fY2xvY2tfaHo6NDAwMDAwMDAsXHJcbiAgICBwYXJhbWV0ZXJfcHJvdmVuYW5jZTp7Y2FuX2Nsb2NrX2h6Ontzb3VyY2U6J1RFQ0hOT0xPR1lfREVGQVVMVCcsc3RhdHVzOidSRVZJRVdfUkVRVUlSRUQnLHZhbHVlOjQwMDAwMDAwfX19fX0pO1xyXG4gIGV4cGVjdChsZWdhY3kub2soKSxhd2FpdCBsZWdhY3kudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke3Byb2plY3R9YCk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeUxhYmVsKCdCdXMgLyBQcm90b2tvbGwgYXVzd8OkaGxlbicpLnNlbGVjdE9wdGlvbignY2FuX2ZkJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeUxhYmVsKCdBbndlbmR1bmdzYmVyZWljaCBhdXN3w6RobGVuJykuc2VsZWN0T3B0aW9uKCdhdXRvbW90aXZlJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignW25hbWU9XCJhcmJpdHJhdGlvbl9iaXRyYXRlXCJdJykpLnRvSGF2ZVZhbHVlKCc1MDAga2JpdC9zJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignW25hbWU9XCJkYXRhX2JpdHJhdGVcIl0nKSkudG9IYXZlVmFsdWUoJzIgTWJpdC9zJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignW25hbWU9XCJwYXlsb2FkX2J5dGVzXCJdJykpLnRvSGF2ZVZhbHVlKCc4Jyk7XHJcbiAgY29uc3QgY2xvY2sgPSBwYWdlLmxvY2F0b3IoJ1tuYW1lPVwiY2FuX2Nsb2NrX2h6XCJdJyk7XHJcbiAgYXdhaXQgZXhwZWN0KGNsb2NrKS50b0hhdmVWYWx1ZSgnNDAwMDAwMDAnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ1NJTVVMQVRJT05TQU5OQUhNRSDCtyBLZWluIEdlcsOkdGVuYWNod2VpcycpLmZpcnN0KCkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHtuYW1lOidQYXJhbWV0ZXIgc3BlaWNoZXJuIOKGkicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdUZWNobm9sb2dpZS0gdW5kIFRpbWluZy1QYXJhbWV0ZXIgZ2VzcGVpY2hlcnQuJykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3Qgc2F2ZWQgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyx7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgY29uc3QgYXNzdW1wdGlvbnMgPSBzYXZlZC5wYXJhbWV0ZXJzLnNpbXVsYXRpb25fcGFyYW1ldGVyX2Fzc3VtcHRpb25zLmNhbl9mZDtcclxuICBleHBlY3QoYXNzdW1wdGlvbnMudmFsdWVzKS50b01hdGNoT2JqZWN0KHthcmJpdHJhdGlvbl9iaXRyYXRlOjUwMDAwMCxkYXRhX2JpdHJhdGU6MjAwMDAwMCxjYW5fY2xvY2tfaHo6NDAwMDAwMDAscGF5bG9hZF9ieXRlczo4fSk7XHJcbiAgZXhwZWN0KGFzc3VtcHRpb25zLnByb3ZlbmFuY2UuY2FuX2Nsb2NrX2h6KS50b01hdGNoT2JqZWN0KHtzb3VyY2U6J05JU19TSU1VTEFUSU9OX0FTU1VNUFRJT04nLHN0YXR1czonQVNTVU1FRCcsdGVjaG5vbG9neTonY2FuX2ZkJyxoYXJkd2FyZV9ldmlkZW5jZTpmYWxzZSx2YWx1ZTo0MDAwMDAwMH0pO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfcGFyYW1ldGVycy5jYW5fZmQudmFsdWVzLmNhbl9jbG9ja19oeikudG9CZVVuZGVmaW5lZCgpO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLmNhbl9jbG9ja19oeikudG9CZVVuZGVmaW5lZCgpO1xyXG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XHJcbiAgYXdhaXQgZXhwZWN0KGNsb2NrKS50b0hhdmVWYWx1ZSgnNDAwMDAwMDAnKTtcclxuICBhd2FpdCByZXZlYWxQYXJhbWV0ZXIocGFnZSwnY2FuX2Nsb2NrX2h6Jyk7XHJcbiAgYXdhaXQgY2xvY2suZmlsbCgnODAwMDAwMDAnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywge25hbWU6J1BhcmFtZXRlciBzcGVpY2hlcm4g4oaSJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ1RlY2hub2xvZ2llLSB1bmQgVGltaW5nLVBhcmFtZXRlciBnZXNwZWljaGVydC4nKSkudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xyXG4gIGF3YWl0IGV4cGVjdChjbG9jaykudG9IYXZlVmFsdWUoJzgwMDAwMDAwJyk7XHJcbiAgY29uc3QgdXBkYXRlZCA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLHtoZWFkZXJzfSkpLmpzb24oKTtcclxuICBleHBlY3QodXBkYXRlZC5wYXJhbWV0ZXJzLnNpbXVsYXRpb25fcGFyYW1ldGVyX2Fzc3VtcHRpb25zLmNhbl9mZC5wcm92ZW5hbmNlLmNhbl9jbG9ja19oei5oYXJkd2FyZV9ldmlkZW5jZSkudG9CZShmYWxzZSk7XHJcbiAgZXhwZWN0KHVwZGF0ZWQucGFyYW1ldGVyX3N0b3JhZ2Uuc291cmNlKS50b0JlKCdQUk9KRUNUX1VTRVJfREVGSU5FRF9WQUxVRVMnKTtcclxuICBjb25zdCB1c2VyVmFsdWVzID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycy91c2VyLWRlZmluZWQtdmFsdWVzJyx7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgZXhwZWN0KHVzZXJWYWx1ZXMucHJvamVjdF9pZCkudG9CZShwcm9qZWN0KTtcclxuICBleHBlY3QodXNlclZhbHVlcy52YWx1ZV9vcmlnaW4pLnRvQmUoJ1VTRVJfREVGSU5FRF9WQUxVRScpO1xyXG4gIGV4cGVjdCh1c2VyVmFsdWVzLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnMuY2FuX2ZkLnZhbHVlcy5jYW5fY2xvY2tfaHopLnRvQmUoODAwMDAwMDApO1xyXG4gIGV4cGVjdCh1c2VyVmFsdWVzLnBhcmFtZXRlcnMudGVjaG5vbG9neV9kZWZhdWx0cykudG9CZVVuZGVmaW5lZCgpO1xyXG4gIGV4cGVjdCh1c2VyVmFsdWVzLnBhcmFtZXRlcnMuZGVmYXVsdHNfc291cmNlKS50b0JlVW5kZWZpbmVkKCk7XHJcbn0pO1xyXG5cclxudGVzdCgnc2F2ZWQgY29uZmlybWVkIHdpemFyZCBjb250ZXh0IHByb3Bvc2VzIGl0cyBidXMgd2l0aG91dCBpbnZlbnRpbmcgcGFyYW1ldGVyIGNvbmZpcm1hdGlvbiBAdGVjaG5vbG9neS1yZXZpZXcnLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtd2l6YXJkLWJ1cy0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGhlYWRlcnMgPSB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH07XHJcbiAgY29uc3Qgc2VlZGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBhdGNoKCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L2NvbnRleHQ/dmlldz1zdW1tYXJ5Jywge1xyXG4gICAgaGVhZGVycyxcclxuICAgIGRhdGE6IHsgYWdlbnRfd2l6YXJkX3N0YXR1czogeyBjb25maXJtZWRfYXQ6ICcyMDI2LTA5LTMwVDExOjMyOjUwWicsIG1vZGVsX3R5cGU6ICdjdXN0b20nLFxyXG4gICAgICBjb21tdW5pY2F0aW9uX3N5c3RlbV9jb3VudHM6IFt7IGlkOiAnaTJjJywgY291bnQ6IDEgfV0gfSB9LFxyXG4gIH0pO1xyXG4gIGV4cGVjdChzZWVkZWQub2soKSwgYXdhaXQgc2VlZGVkLnRleHQoKSkudG9CZSh0cnVlKTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8/bW9kZT1wYXJhbWV0ZXJzJnByb2plY3Q9JHtwcm9qZWN0fWApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNkb21haW4nKSkudG9IYXZlVmFsdWUoJ2N1c3RvbScpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyN0ZWNobm9sb2d5JykpLnRvSGF2ZVZhbHVlKCdpMmMnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ1VOVkVSSUZJRUQgwrcgS2VpbmUgYmVzdMOkdGlndGUgVGVjaG5vbG9naWVhdXN3YWhsJykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3QgcGFyYW1ldGVycyA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLCB7IGhlYWRlcnMgfSkpLmpzb24oKTtcclxuICBleHBlY3QocGFyYW1ldGVycy5wYXJhbWV0ZXJzLnRlY2hub2xvZ3kpLnRvQmVVbmRlZmluZWQoKTtcclxufSk7XHJcblxyXG50ZXN0KCdtaXhlZCBwcm9qZWN0IHNob3dzIGV4YWN0IExJTiBwcm9maWxlLCByZWplY3RzIDJNIGFuZCBwcmVzZXJ2ZXMgQ0FOLUZEIHdoaWxlIHNhdmluZyBMSU4gQHRlY2hub2xvZ3ktcmV2aWV3JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXJhdGUtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBoZWFkZXJzID0geyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9O1xyXG4gIGNvbnN0IGluaXRpYWwgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywgeyBoZWFkZXJzIH0pKS5qc29uKCk7XHJcbiAgY29uc3QgcGFyYW1ldGVycyA9IHsgLi4uaW5pdGlhbC5wYXJhbWV0ZXJzLCBpbmR1c3RyeTogJ2F1dG9tb3RpdmUnLCB0ZWNobm9sb2d5OiAnY2FuX2ZkJywgZGVmYXVsdHNfc291cmNlOiAndGVjaG5vbG9neS1yZWdpc3RyeScsXHJcbiAgICBiaXRyYXRlOiAyMDAwMDAwLCBhcmJpdHJhdGlvbl9iaXRyYXRlOiA1MDAwMDAsIGRhdGFfYml0cmF0ZTogMjAwMDAwMCxcclxuICAgIG5ldHdvcmtzOiBbeyBpZDonbGluLW9uZScsIHRlY2hub2xvZ3k6J0xJTicsIG5hbWU6J0xJTiBUZXN0JyB9LCB7aWQ6J2Nhbi1vbmUnLCB0ZWNobm9sb2d5OidDQU5fRkQnLG5hbWU6J0NBTiBUZXN0J31dIH07XHJcbiAgY29uc3Qgc2VlZGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBhdGNoKCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLCB7IGhlYWRlcnMsIGRhdGE6e3BhcmFtZXRlcnMsIGV4cGVjdGVkX3Rva2VuOmluaXRpYWwuZWRpdF90b2tlbn0gfSk7XHJcbiAgZXhwZWN0KHNlZWRlZC5vaygpLCBhd2FpdCBzZWVkZWQudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIC8vIERlbGF5IHRoZSByZWFsIHJlYWQ6IGNvbnRyb2xzIG11c3Qgbm90IHVzZSBkZWZhdWx0cyBhbmQgdGhlbiBvdmVyd3JpdGUgYSB1c2VyIHNlbGVjdGlvbi5cclxuICBhd2FpdCBwYWdlLnJvdXRlKCcqKi9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycsIGFzeW5jIHJvdXRlID0+IHtcclxuICAgIGlmIChyb3V0ZS5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdHRVQnKSBhd2FpdCBuZXcgUHJvbWlzZShyZXNvbHZlID0+IHNldFRpbWVvdXQocmVzb2x2ZSwgMzAwKSk7XHJcbiAgICBhd2FpdCByb3V0ZS5jb250aW51ZSgpO1xyXG4gIH0pO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke3Byb2plY3R9YCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3RlY2hub2xvZ3knKSkudG9IYXZlVmFsdWUoJ2Nhbl9mZCcpO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignI3RlY2hub2xvZ3knKS5zZWxlY3RPcHRpb24oJ2xpbicpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJsaW5fYml0cmF0ZV9icHNcIl0nKSkubm90LnRvSGF2ZVZhbHVlKCcnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcucGFyYW1ldGVyLWdyb3VwLWNvbW1vbiAjbGluX2JpdHJhdGVfYnBzJykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2xpbl9yZWdpc3RlcmVkX3NvdXJjZScpKS50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2xpbl9yZWdpc3RlcmVkX3NvdXJjZScpKS5ub3QudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonUGFyYW1ldGVyIHNwZWljaGVybiDihpInLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnVGVjaG5vbG9naWUtIHVuZCBUaW1pbmctUGFyYW1ldGVyIGdlc3BlaWNoZXJ0LicpKS50b0JlVmlzaWJsZSgpO1xyXG4gIGNvbnN0IG5vRmFrZVNvdXJjZXMgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyx7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgZXhwZWN0KG5vRmFrZVNvdXJjZXMucGFyYW1ldGVycy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5saW4udmFsdWVzLmxpbl9yZWdpc3RlcmVkX3NvdXJjZSkudG9CZVVuZGVmaW5lZCgpO1xyXG4gIGV4cGVjdChub0Zha2VTb3VyY2VzLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnMubGluLnZhbHVlcy5saW5fY29tbWFuZGVyX25vZGVfaWQpLnRvQmVVbmRlZmluZWQoKTtcclxuICBhd2FpdCBwYWdlLmxvY2F0b3IoJy5wYXJhbWV0ZXItZGV0YWlscycpLmZpbHRlcih7aGFzOnBhZ2UubG9jYXRvcignI2xpbl9yZWdpc3RlcmVkX3NvdXJjZScpfSkubG9jYXRvcignOnNjb3BlID4gc3VtbWFyeScpLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlMYWJlbCgnUHJvZmlscXVlbGxlJyx7ZXhhY3Q6dHJ1ZX0pKS50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeUxhYmVsKCdQcm9maWxxdWVsbGUnLHtleGFjdDp0cnVlfSkuZmlsbCgncHJvamVjdDpyZXZpZXdlZC1saW4tcHJvZmlsZScpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidQYXJhbWV0ZXIgc3BlaWNoZXJuIOKGkicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdUZWNobm9sb2dpZS0gdW5kIFRpbWluZy1QYXJhbWV0ZXIgZ2VzcGVpY2hlcnQuJykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjdGVjaG5vbG9neScpKS50b0hhdmVWYWx1ZSgnY2FuX2ZkJyk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjdGVjaG5vbG9neScpLnNlbGVjdE9wdGlvbignbGluJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2xpbl9yZWdpc3RlcmVkX3NvdXJjZScpKS50b0hhdmVWYWx1ZSgncHJvamVjdDpyZXZpZXdlZC1saW4tcHJvZmlsZScpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJy5wYXJhbWV0ZXItZGV0YWlsc1tvcGVuXScpKS50b0hhdmVDb3VudCgwKTtcclxuICBhd2FpdCByZXZlYWxQYXJhbWV0ZXIocGFnZSwnbGluX2VkaXRpb24nKTtcclxuICBhd2FpdCBwYWdlLmxvY2F0b3IoJ3NlbGVjdFtuYW1lPVwibGluX2VkaXRpb25cIl0nKS5zZWxlY3RPcHRpb24oJ0xJTl8yXzJBXzIwMTAnKTtcclxuICBhd2FpdCByZXZlYWxQYXJhbWV0ZXIocGFnZSwnbGluX3BoeXNpY2FsX3Byb2ZpbGUnKTtcclxuICBhd2FpdCBwYWdlLmxvY2F0b3IoJ3NlbGVjdFtuYW1lPVwibGluX3BoeXNpY2FsX3Byb2ZpbGVcIl0nKS5zZWxlY3RPcHRpb24oJ0xJTl8yXzJBX1NJTkdMRV9XSVJFJyk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjcGFyYW1ldGVyLWZpZWxkLWxpbl9iaXRyYXRlX2JwcyAucGFyYW1ldGVyLWRlZmF1bHQtZGV0YWlscyA+IHN1bW1hcnknKS5jbGljaygpO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignZGl2W3RpdGxlXScpLmZpbHRlcih7aGFzOnBhZ2UubG9jYXRvcignI2xpbl9iaXRyYXRlX2JwcycpfSlcclxuICAgIC5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6J0JlZGluZ3RlbiBTdGFuZGFyZHdlcnQgw7xiZXJuZWhtZW4nLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJsaW5fYml0cmF0ZV9icHNcIl0nKSkudG9IYXZlVmFsdWUoJzE5LDIga2JpdC9zJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cImRhdGFfYml0cmF0ZVwiXScpKS50b0hhdmVDb3VudCgwKTtcclxuICBjb25zdCBpbnZhbGlkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBhdGNoKCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLCB7aGVhZGVycyxcclxuICAgIGRhdGE6e3BhcmFtZXRlcnM6ey4uLnBhcmFtZXRlcnMsdGVjaG5vbG9neV9wYXJhbWV0ZXJzOntsaW46e3ZhbHVlczp7bGluX2VkaXRpb246J0xJTl8yXzJBXzIwMTAnLGxpbl9waHlzaWNhbF9wcm9maWxlOidMSU5fMl8yQV9TSU5HTEVfV0lSRScsbGluX2JpdHJhdGVfYnBzOjIwMDAwMDB9LFxyXG4gICAgICBwcm92ZW5hbmNlOk9iamVjdC5mcm9tRW50cmllcyhPYmplY3QuZW50cmllcyh7bGluX2VkaXRpb246J0xJTl8yXzJBXzIwMTAnLGxpbl9waHlzaWNhbF9wcm9maWxlOidMSU5fMl8yQV9TSU5HTEVfV0lSRScsbGluX2JpdHJhdGVfYnBzOjIwMDAwMDB9KVxyXG4gICAgICAgIC5tYXAoKFtrZXksdmFsdWVdKT0+W2tleSx7c291cmNlOidVU0VSX0NPTkZJUk1FRCcsc3RhdHVzOidDT05GSVJNRUQnLHZhbHVlfV0pKX19fX19KTtcclxuICBleHBlY3QoaW52YWxpZC5zdGF0dXMoKSkudG9CZSg0MDApO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cImxpbl9iaXRyYXRlX2Jwc1wiXScpLmZpbGwoJzksNiBrYml0L3MnKTtcclxuICBjb25zdCByZXNwb25zZSA9IHBhZ2Uud2FpdEZvclJlc3BvbnNlKHIgPT4gci51cmwoKS5pbmNsdWRlcygnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJykgJiYgci5yZXF1ZXN0KCkubWV0aG9kKCkgPT09ICdQQVRDSCcpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7bmFtZTonUGFyYW1ldGVyIHNwZWljaGVybiDihpInLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGV4cGVjdCgoYXdhaXQgcmVzcG9uc2UpLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgY29uc3Qgc2F2ZWQgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywge2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLm5ldHdvcmtzKS50b0VxdWFsKHBhcmFtZXRlcnMubmV0d29ya3MpO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLnRlY2hub2xvZ3kpLnRvQmUoJ2Nhbl9mZCcpO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLmRhdGFfYml0cmF0ZSkudG9CZSgyMDAwMDAwKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5saW4udmFsdWVzLmxpbl9iaXRyYXRlX2JwcykudG9CZSg5NjAwKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5saW4ucHJvdmVuYW5jZS5saW5fYml0cmF0ZV9icHMpLnRvTWF0Y2hPYmplY3Qoe3N0YXR1czonQVNTVU1FRCcsaGFyZHdhcmVfZXZpZGVuY2U6ZmFsc2V9KTtcclxuICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyN0ZWNobm9sb2d5JykpLnRvSGF2ZVZhbHVlKCdjYW5fZmQnKTtcclxuICBhd2FpdCBwYWdlLmxvY2F0b3IoJyN0ZWNobm9sb2d5Jykuc2VsZWN0T3B0aW9uKCdsaW4nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCdpbnB1dFtuYW1lPVwibGluX2JpdHJhdGVfYnBzXCJdJykpLnRvSGF2ZVZhbHVlKCc5LDYga2JpdC9zJyk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjdGVjaG5vbG9neScpLnNlbGVjdE9wdGlvbignY2FuX2ZkJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cImRhdGFfYml0cmF0ZVwiXScpKS50b0hhdmVWYWx1ZSgnMiBNYml0L3MnKTtcclxufSk7XHJcblxyXG50ZXN0KCdzdGFsZSBwYXJhbWV0ZXIgcmV2aXNpb24gcmVqZWN0cyB0aGUgcmVhbCB3cml0ZSBhbmQgcHJlc2VydmVzIGNvbmZpcm1lZCByYXRlcyBAdGVjaG5vbG9neS1yZXZpZXcnLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtcmF0ZS1jb25mbGljdC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGhlYWRlcnMgPSB7J1gtUHJvamVjdC1JRCc6cHJvamVjdH07XHJcbiAgY29uc3QgZmlyc3QgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywge2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGNvbnN0IHBhcmFtZXRlcnMgPSB7Li4uZmlyc3QucGFyYW1ldGVycywgdGVjaG5vbG9neTonbGluJywgYml0cmF0ZToxOTIwMH07XHJcbiAgY29uc3Qgc2F2ZWQgPSBhd2FpdCBwYWdlLnJlcXVlc3QucGF0Y2goJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycsIHtoZWFkZXJzLGRhdGE6e3BhcmFtZXRlcnMsZXhwZWN0ZWRfdG9rZW46Zmlyc3QuZWRpdF90b2tlbn19KTtcclxuICBleHBlY3Qoc2F2ZWQub2soKSwgYXdhaXQgc2F2ZWQudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IGNvbmZsaWN0ID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBhdGNoKCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLCB7aGVhZGVycyxkYXRhOntwYXJhbWV0ZXJzOnsuLi5wYXJhbWV0ZXJzLGJpdHJhdGU6OTYwMH0sZXhwZWN0ZWRfdG9rZW46Zmlyc3QuZWRpdF90b2tlbn19KTtcclxuICBleHBlY3QoY29uZmxpY3Quc3RhdHVzKCkpLnRvQmUoNDA5KTtcclxuICBjb25zdCBjdXJyZW50ID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChjdXJyZW50LnBhcmFtZXRlcnMuYml0cmF0ZSkudG9CZSgxOTIwMCk7XHJcbn0pO1xyXG5cclxudGVzdCgnZXZlcnkgYnVzIGV4cG9zZXMgaXRzIG93biBzZXJ2ZXIgZGVmYXVsdHMgaW4gdGhlIGFjdHVhbCBwYXJhbWV0ZXIgZm9ybSBAdGVjaG5vbG9neS1yZXZpZXcnLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtY2F0YWxvZy1kZWZhdWx0cy0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGNhdGFsb2cgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS90ZWNobm9sb2dpZXMnKSkuanNvbigpO1xyXG4gIGNvbnN0IHByb2ZpbGVzID0gbmV3IE1hcDxzdHJpbmcsIGFueT4oY2F0YWxvZy5kb21haW5zLmZsYXRNYXAoKGRvbWFpbjogYW55KSA9PiBkb21haW4udGVjaG5vbG9naWVzKS5tYXAoKHByb2ZpbGU6IGFueSkgPT4gW3Byb2ZpbGUuaWQsIHByb2ZpbGVdKSk7XHJcbiAgZXhwZWN0KHByb2ZpbGVzLnNpemUpLnRvQmUoY2F0YWxvZy50ZWNobm9sb2d5X2NvdW50KTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8/bW9kZT1wYXJhbWV0ZXJzJnByb2plY3Q9JHtwcm9qZWN0fWApO1xyXG4gIGNvbnN0IGluaXRpYWxCdXMgPSBwYWdlLmdldEJ5TGFiZWwoJ0J1cyAvIFByb3Rva29sbCBhdXN3w6RobGVuJyk7XHJcbiAgYXdhaXQgZXhwZWN0KGluaXRpYWxCdXMubG9jYXRvcignb3B0aW9uW3ZhbHVlPVwiaTJjXCJdJykpLnRvSGF2ZUNvdW50KDEpO1xyXG4gIGF3YWl0IGluaXRpYWxCdXMuc2VsZWN0T3B0aW9uKCdpMmMnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5TGFiZWwoJ0Fud2VuZHVuZ3NiZXJlaWNoIGF1c3fDpGhsZW4nKS5zZWxlY3RPcHRpb24oJ2N1c3RvbScpO1xyXG4gIGZvciAoY29uc3QgW2lkLCBwcm9maWxlXSBvZiBwcm9maWxlcykge1xyXG4gICAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjdGVjaG5vbG9neScpLnNlbGVjdE9wdGlvbihpZCk7XHJcbiAgICBmb3IgKGNvbnN0IGZpZWxkIG9mIHByb2ZpbGUucGFyYW1ldGVyX3NjaGVtYS5maWx0ZXIoKGl0ZW06IGFueSkgPT4gWydiaXRyYXRlJywgJ2FyYml0cmF0aW9uX2JpdHJhdGUnLCAnZGF0YV9iaXRyYXRlJ10uaW5jbHVkZXMoaXRlbS5rZXkpKSkge1xyXG4gICAgICBjb25zdCBpbnB1dCA9IHBhZ2UubG9jYXRvcihgaW5wdXRbbmFtZT1cIiR7ZmllbGQua2V5fVwiXWApO1xyXG4gICAgICBhd2FpdCBleHBlY3QoaW5wdXQsIGAke2lkfS8ke2ZpZWxkLmtleX1gKS5ub3QudG9IYXZlVmFsdWUoJycpO1xyXG4gICAgICBleHBlY3QoYXdhaXQgaW5wdXQuZXZhbHVhdGUoKGVsOiBIVE1MSW5wdXRFbGVtZW50KSA9PiBlbC5jaGVja1ZhbGlkaXR5KCkpLCBgJHtpZH0vJHtmaWVsZC5rZXl9YCkudG9CZSh0cnVlKTtcclxuICAgIH1cclxuICAgIGNvbnN0IGVtcHR5ID0gYXdhaXQgcGFnZS5sb2NhdG9yKCdmb3JtLmNvbmZpZy1wYW5lbCAucGFyYW1ldGVyLWdyb3VwcycpLmV2YWx1YXRlKGdyb3VwcyA9PlxyXG4gICAgICBbLi4uZ3JvdXBzLnF1ZXJ5U2VsZWN0b3JBbGwoJ2lucHV0LHNlbGVjdCx0ZXh0YXJlYScpXVxyXG4gICAgICAgIC5maWx0ZXIoZWxlbWVudCA9PiAoZWxlbWVudCBpbnN0YW5jZW9mIEhUTUxJbnB1dEVsZW1lbnQgfHwgZWxlbWVudCBpbnN0YW5jZW9mIEhUTUxTZWxlY3RFbGVtZW50IHx8IGVsZW1lbnQgaW5zdGFuY2VvZiBIVE1MVGV4dEFyZWFFbGVtZW50KVxyXG4gICAgICAgICAgJiYgZWxlbWVudC50eXBlICE9PSAnY2hlY2tib3gnICYmIGVsZW1lbnQudmFsdWUgPT09ICcnKVxyXG4gICAgICAgIC5tYXAoZWxlbWVudCA9PiAoZWxlbWVudCBhcyBIVE1MSW5wdXRFbGVtZW50KS5uYW1lKSk7XHJcbiAgICBjb25zdCByZWZlcmVuY2VzID0gcHJvZmlsZS5wYXJhbWV0ZXJfc2NoZW1hLmZpbHRlcigoZmllbGQ6YW55KSA9PiBmaWVsZC52YWx1ZV9yb2xlICYmIGZpZWxkLnZhbHVlX3JvbGUgIT09ICdDT05GSUdVUkFUSU9OJyAmJiBmaWVsZC5zaW11bGF0aW9uX2RlZmF1bHQgPT09IG51bGwpLm1hcCgoZmllbGQ6YW55KT0+ZmllbGQua2V5KTtcclxuICAgIGV4cGVjdChlbXB0eS5maWx0ZXIoKGtleTpzdHJpbmcpPT4hcmVmZXJlbmNlcy5pbmNsdWRlcyhrZXkpKSwgaWQpLnRvRXF1YWwoW10pO1xyXG4gICAgZm9yIChjb25zdCBrZXkgb2YgcmVmZXJlbmNlcykge1xyXG4gICAgICBjb25zdCBjb250cm9sID0gcGFnZS5sb2NhdG9yKGBbbmFtZT1cIiR7a2V5fVwiXWApO1xyXG4gICAgICBpZiAoYXdhaXQgY29udHJvbC5jb3VudCgpKSBhd2FpdCBleHBlY3QoY29udHJvbCkudG9IYXZlVmFsdWUoJycpO1xyXG4gICAgICBlbHNlIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoYCNwYXJhbWV0ZXItZmllbGQtJHtrZXl9YCkpLnRvQ29udGFpblRleHQoJ05pY2h0IHp1dHJlZmZlbmQgZsO8ciBkaWUgZ2V3w6RobHRlIFByb3Rva29sbGtvbmZpZ3VyYXRpb24uJyk7XHJcbiAgICB9XHJcbiAgICBpZiAoaWQgPT09ICdubWVhMjAwMCcpIHtcclxuICAgICAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cImJpdHJhdGVcIl0nKSkudG9IYXZlVmFsdWUoJzI1MCBrYml0L3MnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cIm10dV9ieXRlc1wiXScpKS50b0hhdmVDb3VudCgwKTtcclxuICAgIH1cclxuICB9XHJcbiAgLy8gU3dpdGNoaW5nIHRocm91Z2ggdGhlIGVudGlyZSBjYXRhbG9nIGlzIGEgcmV2aWV3LCBub3QgYSBwZXJzaXN0ZW5jZSBhY3Rpb24uXHJcbiAgY29uc3Qgc2F2ZWQgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywge2hlYWRlcnM6eydYLVByb2plY3QtSUQnOnByb2plY3R9fSkpLmpzb24oKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy50ZWNobm9sb2d5KS50b0JlVW5kZWZpbmVkKCk7XHJcbn0pO1xyXG5cclxudGVzdCgnaGFyZHdhcmUgZWRpdG9yIHVzZXMgdGhlIHNlbGVjdGVkIHByb2ZpbGUgYW5kIHNhdmVzIHByb3Bvc2FscyB3aXRob3V0IGludmVudGluZyBkZXZpY2UgY29uZmlybWF0aW9uIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1kZXZpY2UtcHJvZmlsZS0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGhlYWRlcnMgPSB7J1gtUHJvamVjdC1JRCc6IHByb2plY3R9O1xyXG4gIGNvbnN0IG5vZGVSZXNwb25zZSA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2hhcmR3YXJlLW5vZGVzJywge2hlYWRlcnMsIGRhdGE6e25hbWU6J1JldmlldyBDb250cm9sbGVyJywgZGV2aWNlX3R5cGU6J0VtYmVkZGVkQ29udHJvbGxlcicsIGRvbWFpbjonZW1iZWRkZWRfc3lzdGVtcyd9fSk7XHJcbiAgZXhwZWN0KG5vZGVSZXNwb25zZS5vaygpLCBhd2FpdCBub2RlUmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IG5vZGUgPSBhd2FpdCBub2RlUmVzcG9uc2UuanNvbigpO1xyXG4gIGNvbnN0IHBvcnRSZXNwb25zZSA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2hhcmR3YXJlLWludGVyZmFjZXMnLCB7aGVhZGVycywgZGF0YTp7bmFtZTonRGV2aWNlIFJldmlldyBQb3J0JywgaGFyZHdhcmVfbm9kZV9pZDpub2RlLmlkLCB0ZWNobm9sb2d5OidJMkMnLFxyXG4gICAgY2FwYWJpbGl0aWVzOntsb2NhbF90aW1pbmdfZXZpZGVuY2U6e3NsYXZlX2FkZHJlc3M6JycsY29uZmlybWVkOmZhbHNlfX19fSk7XHJcbiAgZXhwZWN0KHBvcnRSZXNwb25zZS5vaygpLCBhd2FpdCBwb3J0UmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IHBvcnQgPSBhd2FpdCBwb3J0UmVzcG9uc2UuanNvbigpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9lbmdpbmVlcmluZz9wcm9qZWN0PSR7cHJvamVjdH0mcmVzb3VyY2U9aGFyZHdhcmUtaW50ZXJmYWNlcyZvYmplY3Q9JHtwb3J0LmlkfSZlZGl0PTFgKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9sb2NhbF9pMmNfbW9kZScpKS50b0hhdmVWYWx1ZSgnU1RBTkRBUkQnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9sb2NhbF9iaXRyYXRlX2JwcycpKS50b0hhdmVWYWx1ZSgnMTAwMDAwJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfZGF0YV9iaXRyYXRlJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X2xvY2FsX3NsYXZlX2FkZHJlc3MnKSkubm90LnRvSGF2ZVZhbHVlKCcnKTtcclxuICBhd2FpdCBwYWdlLmxvY2F0b3IoJyNlZGl0X3RlY2hub2xvZ3knKS5zZWxlY3RPcHRpb24oJ1NQSScpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X2xvY2FsX2kyY19tb2RlJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X2xvY2FsX2NoaXBfc2VsZWN0JykpLm5vdC50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfbG9jYWxfYml0cmF0ZV9icHMnKSkubm90LnRvSGF2ZVZhbHVlKCcnKTtcclxuICBhd2FpdCBwYWdlLmxvY2F0b3IoJyNlZGl0X3RlY2hub2xvZ3knKS5zZWxlY3RPcHRpb24oJ0NBTl9GRCcpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X2xvY2FsX2NoaXBfc2VsZWN0JykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIC8vIEV4cGxpY2l0IHNjZW5hcmlvIHByb3Bvc2FscyBkbyBub3QgcmV1c2UgdGhlIHByZXZpb3VzIEkyQyBkZXZpY2Ugc2V0dGluZy5cclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9iaXRyYXRlJykpLnRvSGF2ZVZhbHVlKCc1MDAwMDAnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9kYXRhX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzIwMDAwMDAnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCdbbmFtZT1cImVkaXRfbG9jYWxfY29uZmlybWVkXCJdJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignI2VkaXRfdGVjaG5vbG9neScpLnNlbGVjdE9wdGlvbignSTJDJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHtuYW1lOifDhG5kZXJ1bmdlbiBzcGVpY2hlcm4nLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X3RlY2hub2xvZ3knKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgY29uc3Qgc2F2ZWQgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldChgL2FwaS9lbmdpbmVlcmluZy9oYXJkd2FyZS1pbnRlcmZhY2VzLyR7cG9ydC5pZH1gLCB7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgZXhwZWN0KHNhdmVkLmJpdHJhdGUpLnRvQmUoMTAwMDAwKTtcclxuICBleHBlY3Qoc2F2ZWQuZGF0YV9iaXRyYXRlKS50b0JlTnVsbCgpO1xyXG4gIGV4cGVjdChzYXZlZC5jYXBhYmlsaXRpZXMubG9jYWxfdGltaW5nX2V2aWRlbmNlKS50b01hdGNoT2JqZWN0KHt0ZWNobm9sb2d5OidJMkMnLCBpMmNfbW9kZTonU1RBTkRBUkQnLCBiaXRyYXRlX2JwczoxMDAwMDAsIGNvbmZpcm1lZDpmYWxzZX0pO1xyXG4gIGV4cGVjdChzYXZlZC5jYXBhYmlsaXRpZXMubG9jYWxfdGltaW5nX2V2aWRlbmNlLnNsYXZlX2FkZHJlc3MpLnRvQmVOdWxsKCk7XHJcbiAgZXhwZWN0KHNhdmVkLmNhcGFiaWxpdGllcy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5pMmMucHJvdmVuYW5jZS5zbGF2ZV9hZGRyZXNzLmhhcmR3YXJlX2V2aWRlbmNlKS50b0JlKGZhbHNlKTtcclxuICAvLyBFeGlzdGluZyB2ZXJpZmllZCBkZXZpY2UgZmFjdHMgb3V0cmFuayBzdGFuZGFyZCBwcm9wb3NhbHMuIEEgY2hhbmdlZFxyXG4gIC8vIGRldmljZSBzZXR0aW5nIGNhbm5vdCBzaWxlbnRseSByZXVzZSB0aGUgb2xkIGNvbmZpcm1hdGlvbi5cclxuICBjb25zdCBhY3R1YWwgPSBhd2FpdCBwYWdlLnJlcXVlc3QucGF0Y2goYC9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtaW50ZXJmYWNlcy8ke3BvcnQuaWR9YCwge2hlYWRlcnMsXHJcbiAgICBkYXRhOntiaXRyYXRlOjQwMDAwMCwgY2FwYWJpbGl0aWVzOnsuLi5zYXZlZC5jYXBhYmlsaXRpZXMsIGxvY2FsX3RpbWluZ19ldmlkZW5jZTp7XHJcbiAgICAgIGV2aWRlbmNlX3Njb3BlOidDT05UUk9MTEVSX1BPUlQnLCBtYXN0ZXJfbm9kZV9pZDpub2RlLmlkLCBpMmNfbW9kZTonRkFTVCcsIGJpdHJhdGVfYnBzOjQwMDAwMCxcclxuICAgICAgY29uZmlybWVkOnRydWUsIHNvdXJjZTonaXNvbGF0ZWQtdmlydHVhbC1maXh0dXJlOmV4cGxpY2l0LUZBU1QtY29udHJvbGxlci1wb3J0J319fX0pO1xyXG4gIGV4cGVjdChhY3R1YWwub2soKSwgYXdhaXQgYWN0dWFsLnRleHQoKSkudG9CZSh0cnVlKTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vZW5naW5lZXJpbmc/cHJvamVjdD0ke3Byb2plY3R9JnJlc291cmNlPWhhcmR3YXJlLWludGVyZmFjZXMmb2JqZWN0PSR7cG9ydC5pZH0mZWRpdD0xYCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfbG9jYWxfaTJjX21vZGUnKSkudG9IYXZlVmFsdWUoJ0ZBU1QnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9sb2NhbF9iaXRyYXRlX2JwcycpKS50b0hhdmVWYWx1ZSgnNDAwMDAwJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignW25hbWU9XCJlZGl0X2xvY2FsX2NvbmZpcm1lZFwiXScpKS50b0JlQ2hlY2tlZCgpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7bmFtZTonw4RuZGVydW5nZW4gc3BlaWNoZXJuJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF90ZWNobm9sb2d5JykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGNvbnN0IHByZXNlcnZlZCA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KGAvYXBpL2VuZ2luZWVyaW5nL2hhcmR3YXJlLWludGVyZmFjZXMvJHtwb3J0LmlkfWAsIHtoZWFkZXJzfSkpLmpzb24oKTtcclxuICBleHBlY3QocHJlc2VydmVkLmNhcGFiaWxpdGllcy5sb2NhbF90aW1pbmdfZXZpZGVuY2UpLnRvTWF0Y2hPYmplY3Qoe2kyY19tb2RlOidGQVNUJyxiaXRyYXRlX2Jwczo0MDAwMDAsY29uZmlybWVkOnRydWV9KTtcclxuICBleHBlY3QocHJlc2VydmVkLmNhcGFiaWxpdGllcy5sb2NhbF90aW1pbmdfZXZpZGVuY2Uuc2xhdmVfYWRkcmVzcykudG9CZU51bGwoKTtcclxuICBleHBlY3QocHJlc2VydmVkLmNhcGFiaWxpdGllcy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5pMmMucHJvdmVuYW5jZS5zbGF2ZV9hZGRyZXNzLmhhcmR3YXJlX2V2aWRlbmNlKS50b0JlKGZhbHNlKTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vZW5naW5lZXJpbmc/cHJvamVjdD0ke3Byb2plY3R9JnJlc291cmNlPWhhcmR3YXJlLWludGVyZmFjZXMmb2JqZWN0PSR7cG9ydC5pZH0mZWRpdD0xYCk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjZWRpdF9sb2NhbF9pMmNfbW9kZScpLnNlbGVjdE9wdGlvbignRkFTVF9QTFVTJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignW25hbWU9XCJlZGl0X2xvY2FsX2NvbmZpcm1lZFwiXScpKS5ub3QudG9CZUNoZWNrZWQoKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywge25hbWU6J8OEbmRlcnVuZ2VuIHNwZWljaGVybicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfdGVjaG5vbG9neScpKS50b0hhdmVDb3VudCgwKTtcclxuICBjb25zdCBjaGFuZ2VkID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoYC9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtaW50ZXJmYWNlcy8ke3BvcnQuaWR9YCwge2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChjaGFuZ2VkLmNhcGFiaWxpdGllcy5sb2NhbF90aW1pbmdfZXZpZGVuY2UpLnRvTWF0Y2hPYmplY3Qoe2kyY19tb2RlOidGQVNUX1BMVVMnLGNvbmZpcm1lZDpmYWxzZX0pO1xyXG59KTtcclxuXHJcblxyXG50ZXN0KCdDQU4tRkQgZGV2aWNlIGVkaXRvciByZXRhaW5zIGNoYW5nZWQgc2ltdWxhdGlvbiByYXRlcyBzZXBhcmF0ZWx5IGZyb20gYWN0dWFsIGhhcmR3YXJlIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7cGFnZX0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0PSduaXMtZTJlLWRldmljZS1hc3N1bXB0aW9ucy0nK3JhbmRvbVVVSUQoKTtcclxuICBjb25zdCBoZWFkZXJzPXsnWC1Qcm9qZWN0LUlEJzpwcm9qZWN0fTtcclxuICBjb25zdCBub2RlUmVzcG9uc2U9YXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtbm9kZXMnLHtoZWFkZXJzLGRhdGE6e25hbWU6J1NjZW5hcmlvIENvbnRyb2xsZXInLGRldmljZV90eXBlOidFbWJlZGRlZENvbnRyb2xsZXInfX0pO1xyXG4gIGV4cGVjdChub2RlUmVzcG9uc2Uub2soKSxhd2FpdCBub2RlUmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IG5vZGU9YXdhaXQgbm9kZVJlc3BvbnNlLmpzb24oKTtcclxuICBjb25zdCBwb3J0UmVzcG9uc2U9YXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtaW50ZXJmYWNlcycse2hlYWRlcnMsZGF0YTp7bmFtZTonU2NlbmFyaW8gQ0FOIFBvcnQnLGhhcmR3YXJlX25vZGVfaWQ6bm9kZS5pZCx0ZWNobm9sb2d5OidDQU5fRkQnfX0pO1xyXG4gIGV4cGVjdChwb3J0UmVzcG9uc2Uub2soKSxhd2FpdCBwb3J0UmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IHBvcnQ9YXdhaXQgcG9ydFJlc3BvbnNlLmpzb24oKTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vZW5naW5lZXJpbmc/cHJvamVjdD0ke3Byb2plY3R9JnJlc291cmNlPWhhcmR3YXJlLWludGVyZmFjZXMmb2JqZWN0PSR7cG9ydC5pZH0mZWRpdD0xYCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfYml0cmF0ZScpKS50b0hhdmVWYWx1ZSgnNTAwMDAwJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfZGF0YV9iaXRyYXRlJykpLnRvSGF2ZVZhbHVlKCcyMDAwMDAwJyk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjZWRpdF9iaXRyYXRlJykuZmlsbCgnMjUwMDAwJyk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjZWRpdF9kYXRhX2JpdHJhdGUnKS5maWxsKCcyNTAwMDAnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonw4RuZGVydW5nZW4gc3BlaWNoZXJuJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF90ZWNobm9sb2d5JykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGNvbnN0IHNhdmVkPWF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KGAvYXBpL2VuZ2luZWVyaW5nL2hhcmR3YXJlLWludGVyZmFjZXMvJHtwb3J0LmlkfWAse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChzYXZlZC5iaXRyYXRlKS50b0JlTnVsbCgpO1xyXG4gIGV4cGVjdChzYXZlZC5kYXRhX2JpdHJhdGUpLnRvQmVOdWxsKCk7XHJcbiAgZXhwZWN0KHNhdmVkLmNhcGFiaWxpdGllcy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5jYW5fZmQudmFsdWVzKS50b01hdGNoT2JqZWN0KHthcmJpdHJhdGlvbl9iaXRyYXRlOjI1MDAwMCxkYXRhX2JpdHJhdGU6MjUwMDAwfSk7XHJcbiAgZXhwZWN0KHNhdmVkLmNhcGFiaWxpdGllcy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5jYW5fZmQucHJvdmVuYW5jZS5kYXRhX2JpdHJhdGUuaGFyZHdhcmVfZXZpZGVuY2UpLnRvQmUoZmFsc2UpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9lbmdpbmVlcmluZz9wcm9qZWN0PSR7cHJvamVjdH0mcmVzb3VyY2U9aGFyZHdhcmUtaW50ZXJmYWNlcyZvYmplY3Q9JHtwb3J0LmlkfSZlZGl0PTFgKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9iaXRyYXRlJykpLnRvSGF2ZVZhbHVlKCcyNTAwMDAnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9kYXRhX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzI1MDAwMCcpO1xyXG59KTtcclxuXHJcbnRlc3QoJ1BXTSBkZXZpY2UgZWRpdG9yIG9mZmVycyBubyByZXRpcmVkIHRyYW5zYWN0aW9uIHByb29mIGFuZCBwcmVzZXJ2ZXMgbmF0aXZlIGRyaXZlciBjb25maWd1cmF0aW9uIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7cGFnZX0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtcHdtLWVkaXRvci0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGhlYWRlcnMgPSB7J1gtUHJvamVjdC1JRCc6cHJvamVjdH07XHJcbiAgY29uc3Qgbm9kZVJlc3BvbnNlID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtbm9kZXMnLCB7aGVhZGVycyxcclxuICAgIGRhdGE6e25hbWU6J1BXTSBSZXZpZXcgQ29udHJvbGxlcicsZGV2aWNlX3R5cGU6J0VtYmVkZGVkQ29udHJvbGxlcicsZG9tYWluOidlbWJlZGRlZF9zeXN0ZW1zJ319KTtcclxuICBleHBlY3Qobm9kZVJlc3BvbnNlLm9rKCksYXdhaXQgbm9kZVJlc3BvbnNlLnRleHQoKSkudG9CZSh0cnVlKTtcclxuICBjb25zdCBub2RlID0gYXdhaXQgbm9kZVJlc3BvbnNlLmpzb24oKTtcclxuICBjb25zdCBwb3J0UmVzcG9uc2UgPSBhd2FpdCBwYWdlLnJlcXVlc3QucG9zdCgnL2FwaS9lbmdpbmVlcmluZy9oYXJkd2FyZS1pbnRlcmZhY2VzJywge2hlYWRlcnMsXHJcbiAgICBkYXRhOntuYW1lOidQV00gT3V0cHV0JyxoYXJkd2FyZV9ub2RlX2lkOm5vZGUuaWQsdGVjaG5vbG9neTonUFdNJyxjYXBhYmlsaXRpZXM6e1xyXG4gICAgICB0ZWNobm9sb2d5X3BhcmFtZXRlcnM6e3B3bV9wcm9maWxlOidMSU5VWF9TVEFURV82XzE4Jyxwd21fcGVyaW9kX25zOjIwMDAwMDAscHdtX2R1dHlfbnM6NzAwMDAwLFxyXG4gICAgICAgIHB3bV9wb2xhcml0eTonSU5WRVJTRUQnLHB3bV9lbmFibGVkOnRydWUscHdtX2RldmljZV9zb3VyY2U6J2lzb2xhdGVkLXZpcnR1YWwtUFdNLWRyaXZlcid9fX19KTtcclxuICBleHBlY3QocG9ydFJlc3BvbnNlLm9rKCksYXdhaXQgcG9ydFJlc3BvbnNlLnRleHQoKSkudG9CZSh0cnVlKTtcclxuICBjb25zdCBwb3J0ID0gYXdhaXQgcG9ydFJlc3BvbnNlLmpzb24oKTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vZW5naW5lZXJpbmc/cHJvamVjdD0ke3Byb2plY3R9JnJlc291cmNlPWhhcmR3YXJlLWludGVyZmFjZXMmb2JqZWN0PSR7cG9ydC5pZH0mZWRpdD0xYCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfdGVjaG5vbG9neScpKS50b0hhdmVWYWx1ZSgnUFdNJyk7XHJcbiAgLy8gV2FpdCBmb3IgdGhlIHNlbGVjdGVkIHByb2ZpbGUsIG5vdCBvbmx5IHRoZSBpbml0aWFsIGVkaXRvciBza2VsZXRvbi5cclxuICBjb25zdCBjYXRhbG9nID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvdGVjaG5vbG9naWVzJykpLmpzb24oKTtcclxuICBleHBlY3QoY2F0YWxvZy5kb21haW5zLmZsYXRNYXAoKGRvbWFpbjphbnkpPT5kb21haW4udGVjaG5vbG9naWVzKS5maW5kKChwcm9maWxlOmFueSk9PnByb2ZpbGUuaWQ9PT0ncHdtJykubG9jYWxfdGltaW5nX3NjaGVtYSkudG9FcXVhbChbXSk7XHJcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBbJ3B3bV9mcmVxdWVuY3lfaHonLCd1cGRhdGVfYm91bmRfbXMnLCdjYXB0dXJlX2JvdW5kX21zJ10pXHJcbiAgICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKGAjZWRpdF9sb2NhbF8ke2ZpZWxkfWApKS50b0hhdmVDb3VudCgwKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9iaXRyYXRlJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X2RhdGFfYml0cmF0ZScpKS50b0hhdmVDb3VudCgwKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCdbbmFtZT1cImVkaXRfbG9jYWxfY29uZmlybWVkXCJdJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignI2VkaXRfbmFtZScpLmZpbGwoJ1Jldmlld2VkIFBXTSBPdXRwdXQnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonw4RuZGVydW5nZW4gc3BlaWNoZXJuJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF90ZWNobm9sb2d5JykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGNvbnN0IHNhdmVkID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoYC9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtaW50ZXJmYWNlcy8ke3BvcnQuaWR9YCx7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgZXhwZWN0KHNhdmVkLm5hbWUpLnRvQmUoJ1Jldmlld2VkIFBXTSBPdXRwdXQnKTtcclxuICBleHBlY3Qoc2F2ZWQuY2FwYWJpbGl0aWVzKS50b0VxdWFsKHBvcnQuY2FwYWJpbGl0aWVzKTtcclxuICBleHBlY3Qoc2F2ZWQuY2FwYWJpbGl0aWVzLmxvY2FsX3RpbWluZ19ldmlkZW5jZSkudG9CZVVuZGVmaW5lZCgpO1xyXG4gIGV4cGVjdChzYXZlZC5iaXRyYXRlKS50b0JlTnVsbCgpO1xyXG4gIGV4cGVjdChzYXZlZC5kYXRhX2JpdHJhdGUpLnRvQmVOdWxsKCk7XHJcbn0pO1xyXG5cclxudGVzdCgnYWN0dWFsIHVpbnQ2NCBwcm90b2NvbCB2YWx1ZSBzdXJ2aXZlcyBsZWdhY3kgbnVtZXJpYyBKU09OLCBmb3JtIGVkaXQsIFNRTCBwZXJzaXN0ZW5jZSBhbmQgcmVsb2FkIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7cGFnZX0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtdWludDY0LScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgaGVhZGVycyA9IHsnWC1Qcm9qZWN0LUlEJzpwcm9qZWN0LCdDb250ZW50LVR5cGUnOidhcHBsaWNhdGlvbi9qc29uJ307XHJcbiAgY29uc3QgaW5pdGlhbCA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLHtoZWFkZXJzfSkpLmpzb24oKTtcclxuICBjb25zdCBtYXhpbXVtID0gJzE4NDQ2NzQ0MDczNzA5NTUxNjE1JztcclxuICBjb25zdCBzZWVkID0gSlNPTi5zdHJpbmdpZnkoe3BhcmFtZXRlcnM6e2luZHVzdHJ5OidjdXN0b20nLHRlY2hub2xvZ3k6J3NwYXJrcGx1Z19iJyxzcGJfYWxpYXM6J19fRVhBQ1RfSU5URUdFUl9fJyxcclxuICAgIHBhcmFtZXRlcl9wcm92ZW5hbmNlOntzcGJfYWxpYXM6e3ZhbHVlOidfX0VYQUNUX0lOVEVHRVJfXycsc291cmNlOidVU0VSX0NPTkZJUk1FRCcsc3RhdHVzOidDT05GSVJNRUQnfX19LGV4cGVjdGVkX3Rva2VuOmluaXRpYWwuZWRpdF90b2tlbn0pXHJcbiAgICAucmVwbGFjZUFsbCgnXCJfX0VYQUNUX0lOVEVHRVJfX1wiJywgbWF4aW11bSk7XHJcbiAgY29uc3Qgc2VlZGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBhdGNoKCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLHtoZWFkZXJzLGRhdGE6c2VlZH0pO1xyXG4gIGV4cGVjdChzZWVkZWQub2soKSxhd2FpdCBzZWVkZWQudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke3Byb2plY3R9YCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3RlY2hub2xvZ3knKSkudG9IYXZlVmFsdWUoJ3NwYXJrcGx1Z19iJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3NwYl9hbGlhcycpKS50b0hhdmVBdHRyaWJ1dGUoJ3R5cGUnLCd0ZXh0Jyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3NwYl9hbGlhcycpKS50b0hhdmVWYWx1ZShtYXhpbXVtKTtcclxuICBjb25zdCBjYXRhbG9nID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvdGVjaG5vbG9naWVzJykpLmpzb24oKTtcclxuICBjb25zdCBwcm9maWxlID0gY2F0YWxvZy5kb21haW5zLmZsYXRNYXAoKGQ6e3RlY2hub2xvZ2llczpBcnJheTx7aWQ6c3RyaW5nfT59KT0+ZC50ZWNobm9sb2dpZXMpLmZpbmQoKHA6e2lkOnN0cmluZ30pPT5wLmlkPT09J3NwYXJrcGx1Z19iJyk7XHJcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBwcm9maWxlLnBhcmFtZXRlcl9zY2hlbWEuZmlsdGVyKChmOntyZXF1aXJlZD86Ym9vbGVhbix0eXBlOnN0cmluZ30pPT5mLnJlcXVpcmVkJiZmLnR5cGU9PT0ndGV4dCcpKSB7XHJcbiAgICBhd2FpdCByZXZlYWxQYXJhbWV0ZXIocGFnZSxmaWVsZC5rZXkpO1xyXG4gICAgYXdhaXQgcGFnZS5sb2NhdG9yKGBbbmFtZT1cIiR7ZmllbGQua2V5fVwiXWApLmZpbGwoJ2lzb2xhdGVkLXRlc3Qtc291cmNlJyk7XHJcbiAgfVxyXG4gIGNvbnN0IGVkaXRlZCA9ICcxODQ0Njc0NDA3MzcwOTU1MTYxNCc7XHJcbiAgYXdhaXQgcmV2ZWFsUGFyYW1ldGVyKHBhZ2UsJ3NwYl9hbGlhcycpO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignI3NwYl9hbGlhcycpLmZpbGwoZWRpdGVkKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonUGFyYW1ldGVyIHNwZWljaGVybiDihpInLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnVGVjaG5vbG9naWUtIHVuZCBUaW1pbmctUGFyYW1ldGVyIGdlc3BlaWNoZXJ0LicpKS50b0JlVmlzaWJsZSgpO1xyXG4gIGNvbnN0IHNhdmVkID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfcGFyYW1ldGVycy5zcGFya3BsdWdfYi52YWx1ZXMuc3BiX2FsaWFzKS50b0JlKGVkaXRlZCk7XHJcbiAgZXhwZWN0KHNhdmVkLnBhcmFtZXRlcnMudGVjaG5vbG9neV9wYXJhbWV0ZXJzLnNwYXJrcGx1Z19iLnByb3ZlbmFuY2Uuc3BiX2FsaWFzLnZhbHVlKS50b0JlKGVkaXRlZCk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjc3BiX2FsaWFzJykpLnRvSGF2ZVZhbHVlKGVkaXRlZCk7XHJcbn0pO1xyXG5cclxuXHJcbnRlc3QoJ3Byb3Bvc2FsIHBhcmFtZXRlciBsaW5rIHNlbGVjdHMgaXRzIHRlY2hub2xvZ3kgYW5kIGxpdmUgZmluZGluZ3MgaGlnaGxpZ2h0IG9ubHkgYWZmZWN0ZWQgZmllbGRzIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7cGFnZX0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0PSduaXMtZTJlLWN1cnJlbnQtcGFyYW1ldGVyLXJldmlldy0nK3JhbmRvbVVVSUQoKTtcclxuICBjb25zdCBoZWFkZXJzPXsnWC1Qcm9qZWN0LUlEJzpwcm9qZWN0fTtcclxuICBjb25zdCBuZXR3b3Jrcz1be2lkOidjYW4tbG9jYWwnLG5hbWU6J0NBTiBMb2NhbCcsdGVjaG5vbG9neTonQ0FOX0ZEJ30se2lkOidsaW4tbG9jYWwnLG5hbWU6J0xJTiBMb2NhbCcsdGVjaG5vbG9neTonTElOJ31dO1xyXG4gIGNvbnN0IHNlZWQ9YXdhaXQgcGFnZS5yZXF1ZXN0LnBhdGNoKCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLHtoZWFkZXJzLGRhdGE6e3BhcmFtZXRlcnM6e2luZHVzdHJ5OidjdXN0b20nLHRlY2hub2xvZ3k6J2Nhbl9mZCcsZGVmYXVsdHNfc291cmNlOid0ZWNobm9sb2d5LXJlZ2lzdHJ5JyxuZXR3b3Jrcyxmb3JtYXRzOlsndW5pdmVyc2FsLWpzb25sJ119fX0pO1xyXG4gIGV4cGVjdChzZWVkLm9rKCksYXdhaXQgc2VlZC50ZXh0KCkpLnRvQmUodHJ1ZSk7XHJcbiAgYXN5bmMgZnVuY3Rpb24gY3JlYXRlKHJlc291cmNlOnN0cmluZyxkYXRhOlJlY29yZDxzdHJpbmcsdW5rbm93bj4pIHtcclxuICAgIGNvbnN0IHJlc3BvbnNlPWF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nLycrcmVzb3VyY2Use2hlYWRlcnMsZGF0YX0pO1xyXG4gICAgZXhwZWN0KHJlc3BvbnNlLm9rKCksYXdhaXQgcmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpOyByZXR1cm4gcmVzcG9uc2UuanNvbigpO1xyXG4gIH1cclxuICBjb25zdCBub2RlPWF3YWl0IGNyZWF0ZSgnaGFyZHdhcmUtbm9kZXMnLHtuYW1lOidSZXZpZXcgRUNVJyxkZXZpY2VfdHlwZTonRW1iZWRkZWRDb250cm9sbGVyJ30pO1xyXG4gIGZvciAoY29uc3QgbmV0d29yayBvZiBuZXR3b3Jrcykge1xyXG4gICAgY29uc3QgcG9ydD1hd2FpdCBjcmVhdGUoJ2hhcmR3YXJlLWludGVyZmFjZXMnLHtuYW1lOm5ldHdvcmsubmFtZSxoYXJkd2FyZV9ub2RlX2lkOm5vZGUuaWQsdGVjaG5vbG9neTpuZXR3b3JrLnRlY2hub2xvZ3ksbmV0d29ya19yZWY6bmV0d29yay5pZCxiaXRyYXRlOm51bGwsZGF0YV9iaXRyYXRlOm51bGx9KTtcclxuICAgIGNvbnN0IGxvZ2ljYWw9YXdhaXQgY3JlYXRlKCdpbnRlcmZhY2VzJyx7bmFtZTpuZXR3b3JrLm5hbWUsaGFyZHdhcmVfbm9kZV9pZDpub2RlLmlkLGludGVyZmFjZV90eXBlOm5ldHdvcmsudGVjaG5vbG9neX0pO1xyXG4gICAgYXdhaXQgY3JlYXRlKCdtZXNzYWdlcycse25hbWU6bmV0d29yay5uYW1lKycgU3RhdHVzJyxpbnRlcmZhY2VfaWQ6bG9naWNhbC5pZCxoYXJkd2FyZV9pbnRlcmZhY2VfaWQ6cG9ydC5pZCxkbGM6MSxjeWNsZV9tczoxMDAsZGlyZWN0aW9uOid0eCd9KTtcclxuICB9XHJcbiAgY29uc3QgYmVmb3JlPWF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMvcmV2aWV3Jyx7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgZXhwZWN0KGJlZm9yZS5zb3VyY2UpLnRvQmUoJ0NVUlJFTlRfQ0FOT05JQ0FMX01PREVMJyk7XHJcbiAgZXhwZWN0KGJlZm9yZS5maW5kaW5ncy5maWx0ZXIoKGY6e3RlY2hub2xvZ3k6c3RyaW5nfSk9PmYudGVjaG5vbG9neT09PSdjYW5fZmQnKSkudG9IYXZlTGVuZ3RoKDEpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke3Byb2plY3R9JnRlY2hub2xvZ3k9bGluI3BhcmFtZXRlci1maW5kaW5nc2ApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyN0ZWNobm9sb2d5JykpLnRvSGF2ZVZhbHVlKCdsaW4nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicse25hbWU6J0FrdHVlbGxlIFBhcmFtZXRlcmJlZnVuZGUnfSkpLnRvQ29udGFpblRleHQoJzEgZsO8ciBMSU4nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjcGFyYW1ldGVyLWZpZWxkLWxpbl9iaXRyYXRlX2JwcycpKS50b0hhdmVDbGFzcygvcGFyYW1ldGVyLWZpZWxkLWZpbmRpbmcvKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjcGFyYW1ldGVyLWZpZWxkLWxpbl9kZXZpY2Vfc291cmNlJykpLnRvSGF2ZUNsYXNzKC9wYXJhbWV0ZXItZmllbGQtZmluZGluZy8pO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCduYXZpZ2F0aW9uJyx7bmFtZTonVGVjaG5vbG9naWVuIG1pdCBQYXJhbWV0ZXJiZWZ1bmRlbid9KS5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6L0NBTi1GRC99KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyN0ZWNobm9sb2d5JykpLnRvSGF2ZVZhbHVlKCdjYW5fZmQnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjcGFyYW1ldGVyLWZpZWxkLWFyYml0cmF0aW9uX2JpdHJhdGUnKSkudG9IYXZlQ2xhc3MoL3BhcmFtZXRlci1maWVsZC1maW5kaW5nLyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3BhcmFtZXRlci1maWVsZC1kYXRhX2JpdHJhdGUnKSkudG9IYXZlQ2xhc3MoL3BhcmFtZXRlci1maWVsZC1maW5kaW5nLyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3BhcmFtZXRlci1maWVsZC1jYW5fY2xvY2tfaHonKSkubm90LnRvSGF2ZUNsYXNzKC9wYXJhbWV0ZXItZmllbGQtZmluZGluZy8pO1xyXG4gIGNvbnN0IGNvbmZpcm09cGFnZS5nZXRCeVJvbGUoJ2Zvcm0nLHtuYW1lOidDQU4tRkQtTmV0emUgYmVzdMOkdGlnZW4nfSk7XHJcbiAgYXdhaXQgcmV2ZWFsUGFyYW1ldGVyKHBhZ2UsJ2Nhbl9jbG9ja19oeicpO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignW25hbWU9XCJjYW5fY2xvY2tfaHpcIl0nKS5maWxsKCc4MDAwMDAwMCcpO1xyXG4gIGF3YWl0IGV4cGVjdChjb25maXJtLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonRsO8ciAxIE5ldHplIGJlc3TDpHRpZ2VuICYgZXJuZXV0IHByw7xmZW4nLGV4YWN0OnRydWV9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLHtuYW1lOidBa3R1ZWxsZSBQYXJhbWV0ZXJiZWZ1bmRlJ30pKS50b0NvbnRhaW5UZXh0KCdTcGVpY2hlcmUgenVlcnN0IGRpZSDDhG5kZXJ1bmdlbicpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidQYXJhbWV0ZXIgc3BlaWNoZXJuIOKGkicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KGNvbmZpcm0uZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidGw7xyIDEgTmV0emUgYmVzdMOkdGlnZW4gJiBlcm5ldXQgcHLDvGZlbicsZXhhY3Q6dHJ1ZX0pKS50b0JlRW5hYmxlZCgpO1xyXG4gIC8vIFNhdmluZyBhIG1hcmtlZCBzY2VuYXJpbyBtdXN0IHJlbW92ZSBmYWxzZSBtaXNzaW5nLXJhdGUgaGlnaGxpZ2h0cyB3aXRob3V0XHJcbiAgLy8gaW52ZW50aW5nIGEgZGV2aWNlIHF1YWxpZmljYXRpb24gb3IgcmVxdWlyaW5nIGEgc2VwYXJhdGUgcmF0ZSBjb25maXJtYXRpb24uXHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3BhcmFtZXRlci1maWVsZC1hcmJpdHJhdGlvbl9iaXRyYXRlJykpLm5vdC50b0hhdmVDbGFzcygvcGFyYW1ldGVyLWZpZWxkLWZpbmRpbmcvKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjcGFyYW1ldGVyLWZpZWxkLWRhdGFfYml0cmF0ZScpKS5ub3QudG9IYXZlQ2xhc3MoL3BhcmFtZXRlci1maWVsZC1maW5kaW5nLyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLHtuYW1lOidBdXNsZWd1bmcgbWl0IGdlc3BlaWNoZXJ0ZW4gU2ltdWxhdGlvbnN3ZXJ0ZW4nfSkpLnRvQ29udGFpblRleHQoJzEgdm9uIDEnKTtcclxuICBjb25zdCBzY2VuYXJpb1Jldmlldz1hd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzL3Jldmlldycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGNvbnN0IGNhblNjZW5hcmlvPXNjZW5hcmlvUmV2aWV3LnNpbXVsYXRpb25fY2FwYWNpdHkuZmluZCgocm93Ont0ZWNobm9sb2d5OnN0cmluZ30pPT5yb3cudGVjaG5vbG9neT09PSdjYW5fZmQnKTtcclxuICBleHBlY3QoY2FuU2NlbmFyaW8pLnRvTWF0Y2hPYmplY3Qoe3N0YXR1czonRkVBU0lCTEVfVU5ERVJfQVNTVU1QVElPTlMnLGhhcmR3YXJlX2V2aWRlbmNlOmZhbHNlLGZ1bmN0aW9uYWxfdGltaW5nX2FjY2VwdGVkOmZhbHNlLFxyXG4gICAgcmF0ZXM6e2FyYml0cmF0aW9uX2JpdHJhdGU6NTAwMDAwLGRhdGFfYml0cmF0ZToyMDAwMDAwfX0pO1xyXG4gIGV4cGVjdChjYW5TY2VuYXJpby5sb2FkX3BlcmNlbnQpLnRvQmVHcmVhdGVyVGhhbigwKTtcclxuICBleHBlY3Qoc2NlbmFyaW9SZXZpZXcuZmluZGluZ3MuZmluZCgocm93Ont0ZWNobm9sb2d5OnN0cmluZ30pPT5yb3cudGVjaG5vbG9neT09PSdjYW5fZmQnKSkudG9NYXRjaE9iamVjdCh7XHJcbiAgICBjb2RlOidDQVBBQ0lUWV9ERVZJQ0VfRVZJREVOQ0VfTUlTU0lORycsc2V2ZXJpdHk6J0lORk8nLHNpbXVsYXRpb25fcGFyYW1ldGVyc191c2FibGU6dHJ1ZSxoYXJkd2FyZV9ldmlkZW5jZTpmYWxzZX0pO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgvSGlud2VpcyDCtyAuKm9mZmVuZW0gR2Vyw6R0ZW5hY2h3ZWlzIMK3IGtlaW4gU2ltdWxhdGlvbnNibG9ja2VyLykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7cHJvamVjdH0mdGVjaG5vbG9neT1jYW5fZmQjcGFyYW1ldGVyLWZpbmRpbmdzYCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3BhcmFtZXRlci1maWVsZC1hcmJpdHJhdGlvbl9iaXRyYXRlJykpLm5vdC50b0hhdmVDbGFzcygvcGFyYW1ldGVyLWZpZWxkLWZpbmRpbmcvKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicse25hbWU6J0F1c2xlZ3VuZyBtaXQgZ2VzcGVpY2hlcnRlbiBTaW11bGF0aW9uc3dlcnRlbid9KSkudG9Db250YWluVGV4dCgnMSB2b24gMScpO1xyXG4gIGNvbnN0IHJlcGVhdGVkPWF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMvcmV2aWV3Jyx7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgZXhwZWN0KHJlcGVhdGVkLnNpbXVsYXRpb25fY2FwYWNpdHkpLnRvRXF1YWwoc2NlbmFyaW9SZXZpZXcuc2ltdWxhdGlvbl9jYXBhY2l0eSk7XHJcbiAgYXdhaXQgY29uZmlybS5nZXRCeVJvbGUoJ3NwaW5idXR0b24nLHtuYW1lOi9Ob21pbmFsIEJpdHJhdGUvfSkuZmlsbCgnNTAwMDAwJyk7XHJcbiAgYXdhaXQgY29uZmlybS5nZXRCeVJvbGUoJ3NwaW5idXR0b24nLHtuYW1lOi9EYXRhIEJpdHJhdGUvfSkuZmlsbCgnMjAwMDAwMCcpO1xyXG4gIGF3YWl0IGNvbmZpcm0uZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidGw7xyIDEgTmV0emUgYmVzdMOkdGlnZW4gJiBlcm5ldXQgcHLDvGZlbicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLHtuYW1lOidBa3R1ZWxsZSBQYXJhbWV0ZXJiZWZ1bmRlJ30pKS50b0NvbnRhaW5UZXh0KCcwIGbDvHIgQ0FOLUZEJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3BhcmFtZXRlci1maWVsZC1hcmJpdHJhdGlvbl9iaXRyYXRlJykpLm5vdC50b0hhdmVDbGFzcygvcGFyYW1ldGVyLWZpZWxkLWZpbmRpbmcvKTtcclxuICBjb25zdCBhZnRlcj1hd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzL3Jldmlldycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChhZnRlci5maW5kaW5ncy5zb21lKChmOnt0ZWNobm9sb2d5OnN0cmluZ30pPT5mLnRlY2hub2xvZ3k9PT0nY2FuX2ZkJykpLnRvQmUoZmFsc2UpO1xyXG4gIGV4cGVjdChhZnRlci5maW5kaW5ncy5zb21lKChmOnt0ZWNobm9sb2d5OnN0cmluZ30pPT5mLnRlY2hub2xvZ3k9PT0nbGluJykpLnRvQmUodHJ1ZSk7XHJcbiAgY29uc3Qgc2F2ZWQ9YXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLm5ldHdvcmtzLmZpbmQoKG46e2lkOnN0cmluZ30pPT5uLmlkPT09J2xpbi1sb2NhbCcpKS50b0VxdWFsKG5ldHdvcmtzWzFdKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5jYW5fZmQudmFsdWVzLmNhbl9jbG9ja19oeikudG9CZSg4MDAwMDAwMCk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ25hdmlnYXRpb24nLHtuYW1lOidUZWNobm9sb2dpZW4gbWl0IFBhcmFtZXRlcmJlZnVuZGVuJ30pLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTovTElOL30pLmNsaWNrKCk7XHJcbiAgY29uc3QgbGluQ29uZmlybT1wYWdlLmdldEJ5Um9sZSgnZm9ybScse25hbWU6J0xJTi1OZXR6ZSBiZXN0w6R0aWdlbid9KTtcclxuICBhd2FpdCBsaW5Db25maXJtLmdldEJ5Um9sZSgnc3BpbmJ1dHRvbicse25hbWU6L2JpdC4qcmF0ZS9pfSkuZmlsbCgnMTkyMDAnKTtcclxuICBhd2FpdCBsaW5Db25maXJtLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonRsO8ciAxIE5ldHplIGJlc3TDpHRpZ2VuICYgZXJuZXV0IHByw7xmZW4nLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNwYXJhbWV0ZXItZmllbGQtbGluX2JpdHJhdGVfYnBzJykpLm5vdC50b0hhdmVDbGFzcygvcGFyYW1ldGVyLWZpZWxkLWZpbmRpbmcvKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjcGFyYW1ldGVyLWZpZWxkLWxpbl9kZXZpY2Vfc291cmNlJykpLnRvSGF2ZUNsYXNzKC9wYXJhbWV0ZXItZmllbGQtZmluZGluZy8pO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgncmVnaW9uJyx7bmFtZTonQWt0dWVsbGUgUGFyYW1ldGVyYmVmdW5kZSd9KSkudG9Db250YWluVGV4dCgnMSBmw7xyIExJTicpO1xyXG4gIGF3YWl0IGV4cGVjdChsaW5Db25maXJtKS50b0hhdmVDb3VudCgwKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ0RpZSBSYXRlIGZlaGx0IGFscyBiZXN0w6R0aWd0ZXIgUHJvamVrdHdlcnQuJyx7ZXhhY3Q6ZmFsc2V9KSkudG9IYXZlQ291bnQoMCk7XHJcbiAgY29uc3QgZm9yZWlnbj1hd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzL3Jldmlldycse2hlYWRlcnM6eydYLVByb2plY3QtSUQnOiduaXMtZTJlLW90aGVyLScrcmFuZG9tVVVJRCgpfX0pKS5qc29uKCk7XHJcbiAgZXhwZWN0KGZvcmVpZ24uZmluZGluZ3MpLnRvRXF1YWwoW10pO1xyXG59KTtcclxuIl0sIm1hcHBpbmdzIjoiQUFBQSxTQUFTQSxJQUFJLEVBQUVDLE1BQU0sUUFBUSxpQkFBaUI7QUFDOUMsU0FBU0MsVUFBVSxRQUFRLGFBQWE7QUFHeEMsZUFBZUMsZUFBZUEsQ0FBQ0MsSUFBUyxFQUFFQyxHQUFVLEVBQUU7RUFDcEQsTUFBTUMsS0FBSyxHQUFHRixJQUFJLENBQUNHLE9BQU8sQ0FBQyxvQkFBb0JGLEdBQUcsRUFBRSxDQUFDLENBQUNFLE9BQU8sQ0FBQyw0QkFBNEIsQ0FBQztFQUMzRixJQUFJLE9BQU1ELEtBQUssQ0FBQ0UsS0FBSyxDQUFDLENBQUMsS0FBSSxPQUFNRixLQUFLLENBQUNHLFlBQVksQ0FBQyxNQUFNLENBQUMsTUFBSyxJQUFJLEVBQUUsTUFBTUgsS0FBSyxDQUFDQyxPQUFPLENBQUMsa0JBQWtCLENBQUMsQ0FBQ0csS0FBSyxDQUFDLENBQUM7QUFDdkg7QUFFQSxLQUFLLE1BQU1DLFFBQVEsSUFBSSxDQUNyQjtFQUFDQyxVQUFVLEVBQUMsS0FBSztFQUFDQyxFQUFFLEVBQUMsS0FBSztFQUFDQyxJQUFJLEVBQUMsT0FBTztFQUFDVCxHQUFHLEVBQUM7QUFBaUIsQ0FBQyxFQUM5RDtFQUFDTyxVQUFVLEVBQUMsUUFBUTtFQUFDQyxFQUFFLEVBQUMsUUFBUTtFQUFDQyxJQUFJLEVBQUMsUUFBUTtFQUFD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