// 55c9e904eebce35819ae0fdc68c0575f0c5156a1
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
  await page.goto(`/studio?mode=parameters&project=${project}&technology=lin`);
  await expect(page.locator('input[name="lin_bitrate_bps"]')).toHaveValue('19200');
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
  await expect(page.locator('input[name="arbitration_bitrate"]')).toHaveValue('500000');
  await expect(page.locator('input[name="data_bitrate"]')).toHaveValue('2000000');
  await expect(page.locator('input[name="can_fd_brs"]')).toBeChecked();
  await page.reload();
  await expect(page.locator('input[name="data_bitrate"]')).toHaveValue('2000000');
  await page.goto(`/studio?mode=parameters&project=${project}&technology=ethernet`);
  await expect(page.locator('input[name="bitrate"]')).toHaveValue('1000000000');
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
  await expect(clock).toHaveValue('100000');
  await expect(page.getByText('UNVERIFIED · Profilvorschlag').first()).toBeVisible();
  await expect(page.getByText(/Referenz-Obergrenzen, keine bestätigte Busfrequenz: Standard ≤ 100\.000 bit\/s/)).toBeVisible();
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
  await expect(clock).toHaveValue('400000');
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
  await expect(page.locator('[name="arbitration_bitrate"]')).toHaveValue('500000');
  await expect(page.locator('[name="data_bitrate"]')).toHaveValue('2000000');
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
  await expect(page.locator('input[name="lin_bitrate_bps"]')).toHaveValue('19200');
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
  await page.locator('input[name="lin_bitrate_bps"]').fill('9600');
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
  await expect(page.locator('input[name="lin_bitrate_bps"]')).toHaveValue('9600');
  await page.locator('#technology').selectOption('can_fd');
  await expect(page.locator('input[name="data_bitrate"]')).toHaveValue('2000000');
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
    for (const key of references) await expect(page.locator(`[name="${key}"]`)).toHaveValue('');
    if (id === 'nmea2000') {
      await expect(page.locator('input[name="bitrate"]')).toHaveValue('250000');
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
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmFuZG9tVVVJRCIsInJldmVhbFBhcmFtZXRlciIsInBhZ2UiLCJrZXkiLCJncm91cCIsImxvY2F0b3IiLCJjb3VudCIsImdldEF0dHJpYnV0ZSIsImNsaWNrIiwic2NlbmFyaW8iLCJ0ZWNobm9sb2d5IiwiaWQiLCJyYXRlIiwiZGF0YSIsInByb2plY3QiLCJoZWFkZXJzIiwibm9kZVJlc3BvbnNlIiwicmVxdWVzdCIsInBvc3QiLCJuYW1lIiwiZGV2aWNlX3R5cGUiLCJvayIsInRleHQiLCJ0b0JlIiwibm9kZSIsImpzb24iLCJnb3RvIiwiZGlhbG9nIiwidG9CZVZpc2libGUiLCJmaWxsIiwiZ2V0QnlSb2xlIiwiZXhhY3QiLCJzZWxlY3RPcHRpb24iLCJ0b0JlRW5hYmxlZCIsInRvSGF2ZVZhbHVlIiwidG9IYXZlQ291bnQiLCJnZXRCeVRleHQiLCJjcmVhdGVkUmVzcG9uc2UiLCJ3YWl0Rm9yUmVzcG9uc2UiLCJyZXNwb25zZSIsInVybCIsImVuZHNXaXRoIiwibWV0aG9kIiwicG9ydCIsImJpdHJhdGUiLCJ0b0JlTnVsbCIsImRhdGFfYml0cmF0ZSIsImNhcGFiaWxpdGllcyIsInNpbXVsYXRpb25fcGFyYW1ldGVyX2Fzc3VtcHRpb25zIiwidmFsdWVzIiwiTnVtYmVyIiwicHJvdmVuYW5jZSIsInRvTWF0Y2hPYmplY3QiLCJzb3VyY2UiLCJoYXJkd2FyZV9ldmlkZW5jZSIsInJlbG9hZCIsInNhdmVkIiwiZ2V0IiwibGluIiwibGluX2JpdHJhdGVfYnBzIiwiYmVmb3JlIiwic2V0dXAiLCJwYXRjaCIsImV4cGVjdGVkX3Rva2VuIiwiZWRpdF90b2tlbiIsInBhcmFtZXRlcnMiLCJpbmR1c3RyeSIsIm5ldHdvcmtzIiwiZGVmYXVsdFNhdmUiLCJkZWZhdWx0UmVzcG9uc2UiLCJhc3N1bXB0aW9ucyIsImNhbl9mZCIsImFyYml0cmF0aW9uX2JpdHJhdGUiLCJjYW5fZmRfYnJzIiwiZXRoZXJuZXQiLCJwYXJhbWV0ZXJfc3RvcmFnZSIsInN0b3JlZCIsInRvQmVDaGVja2VkIiwiY2F0YWxvZyIsImdldEJ5TGFiZWwiLCJidXMiLCJ0ZWNobm9sb2d5X2NvdW50Iiwic2VhcmNoIiwiY2xlYXIiLCJzZWxlY3RlZEJ1cyIsInNlbGVjdEJveCIsImJvdW5kaW5nQm94Iiwic2VhcmNoQm94IiwieCIsIndpZHRoIiwiY2xvY2siLCJmaXJzdCIsImV2YWx1YXRlIiwiaW5wdXQiLCJjaGVja1ZhbGlkaXR5IiwiaW52YWxpZCIsImZvcm0iLCJlbGVtZW50cyIsImZpbHRlciIsImVsZW1lbnQiLCJIVE1MSW5wdXRFbGVtZW50IiwibWFwIiwidG9FcXVhbCIsImJlZm9yZUludmFsaWQiLCJpbnZhbGlkUmVzcG9uc2UiLCJyIiwiaW5jbHVkZXMiLCJyZWplY3RlZCIsInN0YXR1cyIsIkpTT04iLCJzdHJpbmdpZnkiLCJ0b0NvbnRhaW4iLCJ0b0NvbnRhaW5UZXh0IiwiYWZ0ZXJJbnZhbGlkIiwidGFyZ2V0X2J1c19sb2FkX3BlcmNlbnQiLCJ0ZWNobm9sb2d5X3BhcmFtZXRlcnMiLCJpMmMiLCJpMmNfbW9kZSIsImxlZ2FjeSIsImNhbl9jbG9ja19oeiIsInBhcmFtZXRlcl9wcm92ZW5hbmNlIiwidmFsdWUiLCJwYXlsb2FkX2J5dGVzIiwidG9CZVVuZGVmaW5lZCIsInVwZGF0ZWQiLCJ1c2VyVmFsdWVzIiwicHJvamVjdF9pZCIsInZhbHVlX29yaWdpbiIsInRlY2hub2xvZ3lfZGVmYXVsdHMiLCJkZWZhdWx0c19zb3VyY2UiLCJzZWVkZWQiLCJhZ2VudF93aXphcmRfc3RhdHVzIiwiY29uZmlybWVkX2F0IiwibW9kZWxfdHlwZSIsImNvbW11bmljYXRpb25fc3lzdGVtX2NvdW50cyIsImluaXRpYWwiLCJyb3V0ZSIsIlByb21pc2UiLCJyZXNvbHZlIiwic2V0VGltZW91dCIsImNvbnRpbnVlIiwibm90Iiwibm9GYWtlU291cmNlcyIsImxpbl9yZWdpc3RlcmVkX3NvdXJjZSIsImxpbl9jb21tYW5kZXJfbm9kZV9pZCIsImhhcyIsImxpbl9lZGl0aW9uIiwibGluX3BoeXNpY2FsX3Byb2ZpbGUiLCJPYmplY3QiLCJmcm9tRW50cmllcyIsImVudHJpZXMiLCJjb25mbGljdCIsImN1cnJlbnQiLCJwcm9maWxlcyIsIk1hcCIsImRvbWFpbnMiLCJmbGF0TWFwIiwiZG9tYWluIiwidGVjaG5vbG9naWVzIiwicHJvZmlsZSIsInNpemUiLCJpbml0aWFsQnVzIiwiZmllbGQiLCJwYXJhbWV0ZXJfc2NoZW1hIiwiaXRlbSIsImVsIiwiZW1wdHkiLCJncm91cHMiLCJxdWVyeVNlbGVjdG9yQWxsIiwiSFRNTFNlbGVjdEVsZW1lbnQiLCJIVE1MVGV4dEFyZWFFbGVtZW50IiwidHlwZSIsInJlZmVyZW5jZXMiLCJ2YWx1ZV9yb2xlIiwic2ltdWxhdGlvbl9kZWZhdWx0IiwicG9ydFJlc3BvbnNlIiwiaGFyZHdhcmVfbm9kZV9pZCIsImxvY2FsX3RpbWluZ19ldmlkZW5jZSIsInNsYXZlX2FkZHJlc3MiLCJjb25maXJtZWQiLCJiaXRyYXRlX2JwcyIsImFjdHVhbCIsImV2aWRlbmNlX3Njb3BlIiwibWFzdGVyX25vZGVfaWQiLCJwcmVzZXJ2ZWQiLCJjaGFuZ2VkIiwicHdtX3Byb2ZpbGUiLCJwd21fcGVyaW9kX25zIiwicHdtX2R1dHlfbnMiLCJwd21fcG9sYXJpdHkiLCJwd21fZW5hYmxlZCIsInB3bV9kZXZpY2Vfc291cmNlIiwiZmluZCIsImxvY2FsX3RpbWluZ19zY2hlbWEiLCJtYXhpbXVtIiwic2VlZCIsInNwYl9hbGlhcyIsInJlcGxhY2VBbGwiLCJ0b0hhdmVBdHRyaWJ1dGUiLCJkIiwicCIsImYiLCJyZXF1aXJlZCIsImVkaXRlZCIsInNwYXJrcGx1Z19iIiwiZm9ybWF0cyIsImNyZWF0ZSIsInJlc291cmNlIiwibmV0d29yayIsIm5ldHdvcmtfcmVmIiwibG9naWNhbCIsImludGVyZmFjZV90eXBlIiwiaW50ZXJmYWNlX2lkIiwiaGFyZHdhcmVfaW50ZXJmYWNlX2lkIiwiZGxjIiwiY3ljbGVfbXMiLCJkaXJlY3Rpb24iLCJmaW5kaW5ncyIsInRvSGF2ZUxlbmd0aCIsInRvSGF2ZUNsYXNzIiwiY29uZmlybSIsInRvQmVEaXNhYmxlZCIsImFmdGVyIiwic29tZSIsIm4iLCJsaW5Db25maXJtIiwiZm9yZWlnbiJdLCJzb3VyY2VzIjpbInRlY2hub2xvZ3ktcGFyYW1ldGVyLXJldmlldy5zcGVjLnRzIl0sInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHRlc3QsIGV4cGVjdCB9IGZyb20gJ3BsYXl3cmlnaHQvdGVzdCc7XHJcbmltcG9ydCB7IHJhbmRvbVVVSUQgfSBmcm9tICdub2RlOmNyeXB0byc7XHJcbmltcG9ydCB0eXBlIHsgUGFnZSB9IGZyb20gJ3BsYXl3cmlnaHQvdGVzdCc7XHJcblxyXG5hc3luYyBmdW5jdGlvbiByZXZlYWxQYXJhbWV0ZXIocGFnZTpQYWdlLCBrZXk6c3RyaW5nKSB7XHJcbiAgY29uc3QgZ3JvdXAgPSBwYWdlLmxvY2F0b3IoYCNwYXJhbWV0ZXItZmllbGQtJHtrZXl9YCkubG9jYXRvcigneHBhdGg9YW5jZXN0b3I6OmRldGFpbHNbMV0nKTtcclxuICBpZiAoYXdhaXQgZ3JvdXAuY291bnQoKSAmJiBhd2FpdCBncm91cC5nZXRBdHRyaWJ1dGUoJ29wZW4nKSA9PT0gbnVsbCkgYXdhaXQgZ3JvdXAubG9jYXRvcignOnNjb3BlID4gc3VtbWFyeScpLmNsaWNrKCk7XHJcbn1cclxuXHJcbmZvciAoY29uc3Qgc2NlbmFyaW8gb2YgW1xyXG4gIHt0ZWNobm9sb2d5OidMSU4nLGlkOidsaW4nLHJhdGU6JzE5MjAwJyxrZXk6J2xpbl9iaXRyYXRlX2Jwcyd9LFxyXG4gIHt0ZWNobm9sb2d5OidDQU5fRkQnLGlkOidjYW5fZmQnLHJhdGU6JzUwMDAwMCcsa2V5OidhcmJpdHJhdGlvbl9iaXRyYXRlJyxkYXRhOicyMDAwMDAwJ30sXHJcbiAge3RlY2hub2xvZ3k6J0V0aGVybmV0JyxpZDonZXRoZXJuZXQnLHJhdGU6JzEwMDAwMDAwMDAnLGtleTonYml0cmF0ZSd9LFxyXG5dKSB0ZXN0KGBtYW51YWwgJHtzY2VuYXJpby50ZWNobm9sb2d5fSBwb3J0IGNyZWF0aW9uIHVzZXMgaXRzIG5hdGl2ZSBkZWZhdWx0cyBhbmQgcHJlc2VydmVzIGVkaXRlZCBhc3N1bXB0aW9ucyBAdGVjaG5vbG9neS1yZXZpZXdgLCBhc3luYyAoe3BhZ2V9KSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdD0nbmlzLWUyZS1jcmVhdGUtcmF0ZXMtJytyYW5kb21VVUlEKCksaGVhZGVycz17J1gtUHJvamVjdC1JRCc6cHJvamVjdH07XHJcbiAgY29uc3Qgbm9kZVJlc3BvbnNlPWF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2hhcmR3YXJlLW5vZGVzJyx7aGVhZGVycyxcclxuICAgIGRhdGE6e25hbWU6J05hdGl2ZSBkZWZhdWx0IGNvbnRyb2xsZXInLGRldmljZV90eXBlOidFbWJlZGRlZENvbnRyb2xsZXInfX0pO1xyXG4gIGV4cGVjdChub2RlUmVzcG9uc2Uub2soKSxhd2FpdCBub2RlUmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IG5vZGU9YXdhaXQgbm9kZVJlc3BvbnNlLmpzb24oKSwgbmFtZT0nTmF0aXZlICcrc2NlbmFyaW8udGVjaG5vbG9neSsnIHBvcnQnO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9lbmdpbmVlcmluZz9wcm9qZWN0PSR7cHJvamVjdH0mcmVzb3VyY2U9aGFyZHdhcmUtaW50ZXJmYWNlcyZwYXJlbnQ9JHtub2RlLmlkfSZjcmVhdGU9MWApO1xyXG4gIGNvbnN0IGRpYWxvZz1wYWdlLmxvY2F0b3IoJ2Zvcm0uZW5nLW9iamVjdC13aXphcmQnKTtcclxuICBhd2FpdCBleHBlY3QoZGlhbG9nKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IGRpYWxvZy5sb2NhdG9yKCcjbmFtZScpLmZpbGwobmFtZSk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonV2VpdGVyJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBkaWFsb2cubG9jYXRvcignI3RlY2hub2xvZ3knKS5zZWxlY3RPcHRpb24oc2NlbmFyaW8udGVjaG5vbG9neSk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6J1dlaXRlcicsZXhhY3Q6dHJ1ZX0pKS50b0JlRW5hYmxlZCgpO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6J1dlaXRlcicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcjYml0cmF0ZScpKS50b0hhdmVWYWx1ZShzY2VuYXJpby5yYXRlKTtcclxuICBpZiAoc2NlbmFyaW8uZGF0YSkgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcjZGF0YV9iaXRyYXRlJykpLnRvSGF2ZVZhbHVlKHNjZW5hcmlvLmRhdGEpO1xyXG4gIGVsc2UgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcjZGF0YV9iaXRyYXRlJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6J1dlaXRlcicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KGRpYWxvZy5sb2NhdG9yKCcucHJvcG9zYWwtd2l6YXJkLXJldmlldycpLmdldEJ5VGV4dCgvU0lNVUxBVElPTlNBTk5BSE1FLykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3QgY3JlYXRlZFJlc3BvbnNlPXBhZ2Uud2FpdEZvclJlc3BvbnNlKHJlc3BvbnNlPT5yZXNwb25zZS51cmwoKS5lbmRzV2l0aCgnL2FwaS9lbmdpbmVlcmluZy9oYXJkd2FyZS1pbnRlcmZhY2VzJykmJnJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKT09PSdQT1NUJyk7XHJcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonT2JqZWt0IGFubGVnZW4nLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGNvbnN0IHJlc3BvbnNlPWF3YWl0IGNyZWF0ZWRSZXNwb25zZTtcclxuICBleHBlY3QocmVzcG9uc2Uub2soKSxhd2FpdCByZXNwb25zZS50ZXh0KCkpLnRvQmUodHJ1ZSk7XHJcbiAgY29uc3QgcG9ydD1hd2FpdCByZXNwb25zZS5qc29uKCk7XHJcbiAgZXhwZWN0KHBvcnQuYml0cmF0ZSkudG9CZU51bGwoKTtleHBlY3QocG9ydC5kYXRhX2JpdHJhdGUpLnRvQmVOdWxsKCk7XHJcbiAgY29uc3QgZ3JvdXA9cG9ydC5jYXBhYmlsaXRpZXMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnNbc2NlbmFyaW8uaWRdO1xyXG4gIGV4cGVjdChncm91cC52YWx1ZXNbc2NlbmFyaW8ua2V5XSkudG9CZShOdW1iZXIoc2NlbmFyaW8ucmF0ZSkpO1xyXG4gIGV4cGVjdChncm91cC5wcm92ZW5hbmNlW3NjZW5hcmlvLmtleV0pLnRvTWF0Y2hPYmplY3Qoe3NvdXJjZTonTklTX1NJTVVMQVRJT05fQVNTVU1QVElPTicsdGVjaG5vbG9neTpzY2VuYXJpby5pZCxoYXJkd2FyZV9ldmlkZW5jZTpmYWxzZX0pO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9lbmdpbmVlcmluZz9wcm9qZWN0PSR7cHJvamVjdH0mcmVzb3VyY2U9aGFyZHdhcmUtaW50ZXJmYWNlcyZvYmplY3Q9JHtwb3J0LmlkfSZlZGl0PTFgKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9iaXRyYXRlJykpLnRvSGF2ZVZhbHVlKHNjZW5hcmlvLnJhdGUpO1xyXG4gIGlmIChzY2VuYXJpby5pZD09PSdsaW4nKSB7XHJcbiAgICBhd2FpdCBwYWdlLmxvY2F0b3IoJyNlZGl0X2JpdHJhdGUnKS5maWxsKCc5NjAwJyk7XHJcbiAgICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonw4RuZGVydW5nZW4gc3BlaWNoZXJuJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICAgIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X3RlY2hub2xvZ3knKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xyXG4gICAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfYml0cmF0ZScpKS50b0hhdmVWYWx1ZSgnOTYwMCcpO1xyXG4gICAgY29uc3Qgc2F2ZWQ9YXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoYC9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtaW50ZXJmYWNlcy8ke3BvcnQuaWR9YCx7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgICBleHBlY3Qoc2F2ZWQuYml0cmF0ZSkudG9CZU51bGwoKTtcclxuICAgIGV4cGVjdChzYXZlZC5jYXBhYmlsaXRpZXMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnMubGluLnZhbHVlcy5saW5fYml0cmF0ZV9icHMpLnRvQmUoOTYwMCk7XHJcbiAgfVxyXG59KTtcclxuXHJcbnRlc3QoJ25hdGl2ZSBzaW11bGF0aW9uIHJhdGVzIGxvYWQgYW5kIHBlcnNpc3Qgd2l0aG91dCBtYW51YWwgcmF0ZSBlbnRyeSBvciBjZW50cmFsLWRlZmF1bHQgd3JpdGVzIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7cGFnZX0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0PSduaXMtZTJlLW5hdGl2ZS1kZWZhdWx0cy0nK3JhbmRvbVVVSUQoKTtcclxuICBjb25zdCBoZWFkZXJzPXsnWC1Qcm9qZWN0LUlEJzpwcm9qZWN0fTtcclxuICBjb25zdCBiZWZvcmU9YXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGNvbnN0IHNldHVwPWF3YWl0IHBhZ2UucmVxdWVzdC5wYXRjaCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyx7aGVhZGVycyxkYXRhOntleHBlY3RlZF90b2tlbjpiZWZvcmUuZWRpdF90b2tlbixcclxuICAgIHBhcmFtZXRlcnM6e2luZHVzdHJ5OidhdXRvbW90aXZlJyx0ZWNobm9sb2d5OidjYW5fZmQnLG5ldHdvcmtzOlt7aWQ6J2xpbi1kZWZhdWx0Jyx0ZWNobm9sb2d5OidMSU4nfSxcclxuICAgICAge2lkOidjYW4tZGVmYXVsdCcsdGVjaG5vbG9neTonQ0FOX0ZEJ30se2lkOidldGgtZGVmYXVsdCcsdGVjaG5vbG9neTonRVRIRVJORVQnfV19fX0pO1xyXG4gIGV4cGVjdChzZXR1cC5vaygpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke3Byb2plY3R9JnRlY2hub2xvZ3k9bGluYCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cImxpbl9iaXRyYXRlX2Jwc1wiXScpKS50b0hhdmVWYWx1ZSgnMTkyMDAnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicse25hbWU6J0FrdHVlbGxlIFBhcmFtZXRlcmJlZnVuZGUnfSkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3QgZGVmYXVsdFNhdmUgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyZXNwb25zZSA9PiByZXNwb25zZS51cmwoKS5lbmRzV2l0aCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzL2RlZmF1bHRzJylcclxuICAgICYmIHJlc3BvbnNlLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BPU1QnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonRmVobGVuZGUgU2ltdWxhdGlvbnN2b3JnYWJlbiBpbSBQcm9qZWt0IHNwZWljaGVybicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgY29uc3QgZGVmYXVsdFJlc3BvbnNlID0gYXdhaXQgZGVmYXVsdFNhdmU7XHJcbiAgZXhwZWN0KGRlZmF1bHRSZXNwb25zZS5vaygpLCBhd2FpdCBkZWZhdWx0UmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgvUGFyYW1ldGVyaGVya3VuZnQgwrcgWzEtOV1cXGQqIGdlc3BlaWNoZXJ0ZSBTaW11bGF0aW9uc2FubmFobWVuLykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3Qgc2F2ZWQ9YXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGNvbnN0IGFzc3VtcHRpb25zPXNhdmVkLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnM7XHJcbiAgZXhwZWN0KGFzc3VtcHRpb25zLmxpbi52YWx1ZXMubGluX2JpdHJhdGVfYnBzKS50b0JlKDE5MjAwKTtcclxuICBleHBlY3QoYXNzdW1wdGlvbnMuY2FuX2ZkLnZhbHVlcy5hcmJpdHJhdGlvbl9iaXRyYXRlKS50b0JlKDUwMDAwMCk7XHJcbiAgZXhwZWN0KGFzc3VtcHRpb25zLmNhbl9mZC52YWx1ZXMuZGF0YV9iaXRyYXRlKS50b0JlKDIwMDAwMDApO1xyXG4gIGV4cGVjdChhc3N1bXB0aW9ucy5jYW5fZmQudmFsdWVzLmNhbl9mZF9icnMpLnRvQmUodHJ1ZSk7XHJcbiAgZXhwZWN0KGFzc3VtcHRpb25zLmV0aGVybmV0LnZhbHVlcy5iaXRyYXRlKS50b0JlKDEwMDAwMDAwMDApO1xyXG4gIGV4cGVjdChhc3N1bXB0aW9ucy5jYW5fZmQucHJvdmVuYW5jZS5kYXRhX2JpdHJhdGUuaGFyZHdhcmVfZXZpZGVuY2UpLnRvQmUoZmFsc2UpO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJfc3RvcmFnZS5zb3VyY2UpLnRvQmUoJ1BST0pFQ1RfVVNFUl9ERUZJTkVEX1ZBTFVFUycpO1xyXG4gIGNvbnN0IHN0b3JlZD1hd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMvdXNlci1kZWZpbmVkLXZhbHVlcycse2hlYWRlcnN9KTtcclxuICBleHBlY3Qoc3RvcmVkLm9rKCkpLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7cHJvamVjdH0mdGVjaG5vbG9neT1jYW5fZmRgKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCdpbnB1dFtuYW1lPVwiYXJiaXRyYXRpb25fYml0cmF0ZVwiXScpKS50b0hhdmVWYWx1ZSgnNTAwMDAwJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cImRhdGFfYml0cmF0ZVwiXScpKS50b0hhdmVWYWx1ZSgnMjAwMDAwMCcpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJjYW5fZmRfYnJzXCJdJykpLnRvQmVDaGVja2VkKCk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCdpbnB1dFtuYW1lPVwiZGF0YV9iaXRyYXRlXCJdJykpLnRvSGF2ZVZhbHVlKCcyMDAwMDAwJyk7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7cHJvamVjdH0mdGVjaG5vbG9neT1ldGhlcm5ldGApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJiaXRyYXRlXCJdJykpLnRvSGF2ZVZhbHVlKCcxMDAwMDAwMDAwJyk7XHJcbn0pO1xyXG5cclxuLy8gUmVhbCBpc29sYXRlZCBwZXJzaXN0ZW5jZSBhbmQgcGFyYW1ldGVyLXZpZXcgcmVncmVzc2lvbnM7IG5vdCBuaW5lLXN0YWdlIGNvbXBsZXRpb24gcHJvb2YuXHJcbnRlc3QoJ3VuY29uZmlybWVkIHByb2plY3QgY2FuIHNlbGVjdCBldmVyeSByZWdpc3RlcmVkIGJ1cyB3aXRob3V0IGFuIEF1dG9tb3RpdmUgZmFsbGJhY2sgQHRlY2hub2xvZ3ktcmV2aWV3JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLWNhdGFsb2ctJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBoZWFkZXJzID0geyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9O1xyXG4gIGNvbnN0IGNhdGFsb2cgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS90ZWNobm9sb2dpZXMnKSkuanNvbigpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke3Byb2plY3R9YCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdoZWFkaW5nJywgeyBuYW1lOiAnQnJhbmNoZSB1bmQgVGVjaG5vbG9naWUgYXVzd8OkaGxlbicgfSkpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlMYWJlbCgnQW53ZW5kdW5nc2JlcmVpY2ggYXVzd8OkaGxlbicpKS50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgY29uc3QgYnVzID0gcGFnZS5nZXRCeUxhYmVsKCdCdXMgLyBQcm90b2tvbGwgYXVzd8OkaGxlbicpO1xyXG4gIGF3YWl0IGV4cGVjdChidXMubG9jYXRvcignb3B0aW9uJykpLnRvSGF2ZUNvdW50KGNhdGFsb2cudGVjaG5vbG9neV9jb3VudCArIDEpO1xyXG4gIGNvbnN0IHNlYXJjaCA9IHBhZ2UuZ2V0QnlSb2xlKCdzZWFyY2hib3gnLCB7IG5hbWU6ICdCdXMgLyBQcm90b2tvbGwgc3VjaGVuJyB9KTtcclxuICBhd2FpdCBzZWFyY2guZmlsbCgnQ0FORkQnKTtcclxuICBhd2FpdCBleHBlY3QoYnVzLmxvY2F0b3IoJ29wdGlvblt2YWx1ZT1cImNhbl9mZFwiXScpKS50b0hhdmVDb3VudCgxKTtcclxuICBhd2FpdCBzZWFyY2guZmlsbCgncHJvZm5ldCcpO1xyXG4gIGF3YWl0IGV4cGVjdChidXMubG9jYXRvcignb3B0aW9uW3ZhbHVlPVwicHJvZmluZXRcIl0nKSkudG9IYXZlQ291bnQoMSk7XHJcbiAgYXdhaXQgc2VhcmNoLmNsZWFyKCk7XHJcbiAgYXdhaXQgZXhwZWN0KGJ1cy5sb2NhdG9yKCdvcHRpb24nKSkudG9IYXZlQ291bnQoY2F0YWxvZy50ZWNobm9sb2d5X2NvdW50ICsgMSk7XHJcbiAgYXdhaXQgYnVzLnNlbGVjdE9wdGlvbignaTJjJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeUxhYmVsKCdBbndlbmR1bmdzYmVyZWljaCBhdXN3w6RobGVuJykuc2VsZWN0T3B0aW9uKCdjdXN0b20nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZG9tYWluJykpLnRvSGF2ZVZhbHVlKCdjdXN0b20nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjdGVjaG5vbG9neScpKS50b0hhdmVWYWx1ZSgnaTJjJyk7XHJcbiAgY29uc3Qgc2VsZWN0ZWRCdXMgPSBwYWdlLmxvY2F0b3IoJyN0ZWNobm9sb2d5Jyk7XHJcbiAgY29uc3Qgc2VsZWN0Qm94ID0gYXdhaXQgc2VsZWN0ZWRCdXMuYm91bmRpbmdCb3goKTtcclxuICBjb25zdCBzZWFyY2hCb3ggPSBhd2FpdCBzZWFyY2guYm91bmRpbmdCb3goKTtcclxuICBleHBlY3Qoc2VsZWN0Qm94ICYmIHNlYXJjaEJveCAmJiBzZWFyY2hCb3gueCA+PSBzZWxlY3RCb3gueCArIHNlbGVjdEJveC53aWR0aCAtIDEpLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgc2VhcmNoLmZpbGwoJ3Byb2ZuZXQnKTtcclxuICBhd2FpdCBleHBlY3Qoc2VsZWN0ZWRCdXMubG9jYXRvcignb3B0aW9uW3ZhbHVlPVwicHJvZmluZXRcIl0nKSkudG9IYXZlQ291bnQoMSk7XHJcbiAgYXdhaXQgZXhwZWN0KHNlbGVjdGVkQnVzKS50b0hhdmVWYWx1ZSgnaTJjJyk7XHJcbiAgYXdhaXQgc2VhcmNoLmZpbGwoJ3p6enp6eicpO1xyXG4gIGF3YWl0IGV4cGVjdChzZWxlY3RlZEJ1cykudG9IYXZlVmFsdWUoJ2kyYycpO1xyXG4gIGF3YWl0IGV4cGVjdChzZWxlY3RlZEJ1cy5sb2NhdG9yKCdvcHRpb25bdmFsdWU9XCJfX25vX21hdGNoZXNcIl0nKSkudG9IYXZlQ291bnQoMSk7XHJcbiAgYXdhaXQgc2VhcmNoLmNsZWFyKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHNlbGVjdGVkQnVzLmxvY2F0b3IoJ29wdGlvbicpKS50b0hhdmVDb3VudChjYXRhbG9nLnRlY2hub2xvZ3lfY291bnQpO1xyXG4gIC8vIFRoZSBsb3dlc3QgcmVnaXN0ZXJlZCBJMkMgbW9kZSBpcyBzaG93biBhcyBhbiB1bmNvbmZpcm1lZCBwcm9wb3NhbC5cclxuICBjb25zdCBjbG9jayA9IHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cImJpdHJhdGVcIl0nKTtcclxuICBhd2FpdCBleHBlY3QoY2xvY2spLnRvSGF2ZVZhbHVlKCcxMDAwMDAnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ1VOVkVSSUZJRUQgwrcgUHJvZmlsdm9yc2NobGFnJykuZmlyc3QoKSkudG9CZVZpc2libGUoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoL1JlZmVyZW56LU9iZXJncmVuemVuLCBrZWluZSBiZXN0w6R0aWd0ZSBCdXNmcmVxdWVuejogU3RhbmRhcmQg4omkIDEwMFxcLjAwMCBiaXRcXC9zLykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgZXhwZWN0KGF3YWl0IGNsb2NrLmV2YWx1YXRlKChpbnB1dDogSFRNTElucHV0RWxlbWVudCkgPT4gaW5wdXQuY2hlY2tWYWxpZGl0eSgpKSkudG9CZSh0cnVlKTtcclxuICBhd2FpdCBjbG9jay5maWxsKCcwJyk7XHJcbiAgZXhwZWN0KGF3YWl0IGNsb2NrLmV2YWx1YXRlKChpbnB1dDogSFRNTElucHV0RWxlbWVudCkgPT4gaW5wdXQuY2hlY2tWYWxpZGl0eSgpKSkudG9CZShmYWxzZSk7XHJcbiAgYXdhaXQgY2xvY2suZmlsbCgnNDAwMDAwJyk7XHJcbiAgY29uc3QgaW52YWxpZCA9IGF3YWl0IHBhZ2UubG9jYXRvcignZm9ybS5jb25maWctcGFuZWwnKS5ldmFsdWF0ZShmb3JtID0+IFsuLi4oZm9ybSBhcyBIVE1MRm9ybUVsZW1lbnQpLmVsZW1lbnRzXVxyXG4gICAgLmZpbHRlcihlbGVtZW50ID0+IGVsZW1lbnQgaW5zdGFuY2VvZiBIVE1MSW5wdXRFbGVtZW50ICYmICFlbGVtZW50LmNoZWNrVmFsaWRpdHkoKSlcclxuICAgIC5tYXAoZWxlbWVudCA9PiAoZWxlbWVudCBhcyBIVE1MSW5wdXRFbGVtZW50KS5uYW1lKSk7XHJcbiAgZXhwZWN0KGludmFsaWQpLnRvRXF1YWwoW10pO1xyXG4gIC8vIEhUTUwgYm91bmRzIGFsb25lIGRvIG5vdCBlc3RhYmxpc2ggdGhlIG1vZGUvcmF0ZSByZWxhdGlvbnNoaXA6IFNUQU5EQVJEXHJcbiAgLy8gYXQgNDAwIGtiaXQvcyBtdXN0IGJlIHJlamVjdGVkIGJ5IHRoZSBuYXRpdmUgcHJvZmlsZSB3aXRob3V0IHBlcnNpc3RlbmNlLlxyXG4gIGNvbnN0IGJlZm9yZUludmFsaWQgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywgeyBoZWFkZXJzIH0pKS5qc29uKCk7XHJcbiAgY29uc3QgaW52YWxpZFJlc3BvbnNlID0gcGFnZS53YWl0Rm9yUmVzcG9uc2UociA9PiByLnVybCgpLmluY2x1ZGVzKCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnKSAmJiByLnJlcXVlc3QoKS5tZXRob2QoKSA9PT0gJ1BBVENIJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ1BhcmFtZXRlciBzcGVpY2hlcm4g4oaSJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcclxuICBjb25zdCByZWplY3RlZCA9IGF3YWl0IGludmFsaWRSZXNwb25zZTtcclxuICBleHBlY3QocmVqZWN0ZWQuc3RhdHVzKCkpLnRvQmUoNDAwKTtcclxuICBleHBlY3QoSlNPTi5zdHJpbmdpZnkoYXdhaXQgcmVqZWN0ZWQuanNvbigpKSkudG9Db250YWluKCdURUNITk9MT0dZX1BBUkFNRVRFUl9ERVBFTkRFTkNZX01JU01BVENIJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignLm5vdGljZS5lcnJvcicpKS50b0NvbnRhaW5UZXh0KCdURUNITk9MT0dZX1BBUkFNRVRFUl9ERVBFTkRFTkNZX01JU01BVENIJyk7XHJcbiAgY29uc3QgYWZ0ZXJJbnZhbGlkID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycsIHsgaGVhZGVycyB9KSkuanNvbigpO1xyXG4gIGV4cGVjdChhZnRlckludmFsaWQucGFyYW1ldGVycykudG9FcXVhbChiZWZvcmVJbnZhbGlkLnBhcmFtZXRlcnMpO1xyXG4gIGV4cGVjdChhZnRlckludmFsaWQuZWRpdF90b2tlbikudG9CZShiZWZvcmVJbnZhbGlkLmVkaXRfdG9rZW4pO1xyXG4gIGF3YWl0IHJldmVhbFBhcmFtZXRlcihwYWdlLCdpMmNfbW9kZScpO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignc2VsZWN0W25hbWU9XCJpMmNfbW9kZVwiXScpLnNlbGVjdE9wdGlvbignRkFTVCcpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdQYXJhbWV0ZXIgc3BlaWNoZXJuIOKGkicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdUZWNobm9sb2dpZS0gdW5kIFRpbWluZy1QYXJhbWV0ZXIgZ2VzcGVpY2hlcnQuJykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgY29uc3Qgc2F2ZWQgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywgeyBoZWFkZXJzIH0pKS5qc29uKCk7XHJcbiAgZXhwZWN0KHNhdmVkLnBhcmFtZXRlcnMuaW5kdXN0cnkpLnRvQmUoJ2N1c3RvbScpO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLnRlY2hub2xvZ3kpLnRvQmUoJ2kyYycpO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLnRhcmdldF9idXNfbG9hZF9wZXJjZW50KS50b0JlKDYwKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy50ZWNobm9sb2d5X3BhcmFtZXRlcnMuaTJjLnZhbHVlcykudG9NYXRjaE9iamVjdCh7aTJjX21vZGU6J0ZBU1QnLCBiaXRyYXRlOjQwMDAwMH0pO1xyXG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2RvbWFpbicpKS50b0hhdmVWYWx1ZSgnY3VzdG9tJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3RlY2hub2xvZ3knKSkudG9IYXZlVmFsdWUoJ2kyYycpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ3NlbGVjdFtuYW1lPVwiaTJjX21vZGVcIl0nKSkudG9IYXZlVmFsdWUoJ0ZBU1QnKTtcclxuICBhd2FpdCBleHBlY3QoY2xvY2spLnRvSGF2ZVZhbHVlKCc0MDAwMDAnKTtcclxufSk7XHJcblxyXG50ZXN0KCdDQU4tRkQgc2NlbmFyaW8gZGVmYXVsdHMgc3Vydml2ZSByZWFsIHNhdmUgYW5kIHJlbG9hZCB3aXRob3V0IGhhcmR3YXJlIGNvbmZpcm1hdGlvbiBAdGVjaG5vbG9neS1yZXZpZXcnLCBhc3luYyAoe3BhZ2V9KSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXNpbXVsYXRpb24tZGVmYXVsdHMtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBoZWFkZXJzID0geydYLVByb2plY3QtSUQnOnByb2plY3R9O1xyXG4gIGNvbnN0IGxlZ2FjeSA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wYXRjaCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyx7aGVhZGVycyxkYXRhOntwYXJhbWV0ZXJzOntjYW5fY2xvY2tfaHo6NDAwMDAwMDAsXHJcbiAgICBwYXJhbWV0ZXJfcHJvdmVuYW5jZTp7Y2FuX2Nsb2NrX2h6Ontzb3VyY2U6J1RFQ0hOT0xPR1lfREVGQVVMVCcsc3RhdHVzOidSRVZJRVdfUkVRVUlSRUQnLHZhbHVlOjQwMDAwMDAwfX19fX0pO1xyXG4gIGV4cGVjdChsZWdhY3kub2soKSxhd2FpdCBsZWdhY3kudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke3Byb2plY3R9YCk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeUxhYmVsKCdCdXMgLyBQcm90b2tvbGwgYXVzd8OkaGxlbicpLnNlbGVjdE9wdGlvbignY2FuX2ZkJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeUxhYmVsKCdBbndlbmR1bmdzYmVyZWljaCBhdXN3w6RobGVuJykuc2VsZWN0T3B0aW9uKCdhdXRvbW90aXZlJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignW25hbWU9XCJhcmJpdHJhdGlvbl9iaXRyYXRlXCJdJykpLnRvSGF2ZVZhbHVlKCc1MDAwMDAnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCdbbmFtZT1cImRhdGFfYml0cmF0ZVwiXScpKS50b0hhdmVWYWx1ZSgnMjAwMDAwMCcpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ1tuYW1lPVwicGF5bG9hZF9ieXRlc1wiXScpKS50b0hhdmVWYWx1ZSgnOCcpO1xyXG4gIGNvbnN0IGNsb2NrID0gcGFnZS5sb2NhdG9yKCdbbmFtZT1cImNhbl9jbG9ja19oelwiXScpO1xyXG4gIGF3YWl0IGV4cGVjdChjbG9jaykudG9IYXZlVmFsdWUoJzQwMDAwMDAwJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdTSU1VTEFUSU9OU0FOTkFITUUgwrcgS2VpbiBHZXLDpHRlbmFjaHdlaXMnKS5maXJzdCgpKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7bmFtZTonUGFyYW1ldGVyIHNwZWljaGVybiDihpInLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnVGVjaG5vbG9naWUtIHVuZCBUaW1pbmctUGFyYW1ldGVyIGdlc3BlaWNoZXJ0LicpKS50b0JlVmlzaWJsZSgpO1xyXG4gIGNvbnN0IHNhdmVkID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGNvbnN0IGFzc3VtcHRpb25zID0gc2F2ZWQucGFyYW1ldGVycy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5jYW5fZmQ7XHJcbiAgZXhwZWN0KGFzc3VtcHRpb25zLnZhbHVlcykudG9NYXRjaE9iamVjdCh7YXJiaXRyYXRpb25fYml0cmF0ZTo1MDAwMDAsZGF0YV9iaXRyYXRlOjIwMDAwMDAsY2FuX2Nsb2NrX2h6OjQwMDAwMDAwLHBheWxvYWRfYnl0ZXM6OH0pO1xyXG4gIGV4cGVjdChhc3N1bXB0aW9ucy5wcm92ZW5hbmNlLmNhbl9jbG9ja19oeikudG9NYXRjaE9iamVjdCh7c291cmNlOidOSVNfU0lNVUxBVElPTl9BU1NVTVBUSU9OJyxzdGF0dXM6J0FTU1VNRUQnLHRlY2hub2xvZ3k6J2Nhbl9mZCcsaGFyZHdhcmVfZXZpZGVuY2U6ZmFsc2UsdmFsdWU6NDAwMDAwMDB9KTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy50ZWNobm9sb2d5X3BhcmFtZXRlcnMuY2FuX2ZkLnZhbHVlcy5jYW5fY2xvY2tfaHopLnRvQmVVbmRlZmluZWQoKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy5jYW5fY2xvY2tfaHopLnRvQmVVbmRlZmluZWQoKTtcclxuICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xyXG4gIGF3YWl0IGV4cGVjdChjbG9jaykudG9IYXZlVmFsdWUoJzQwMDAwMDAwJyk7XHJcbiAgYXdhaXQgcmV2ZWFsUGFyYW1ldGVyKHBhZ2UsJ2Nhbl9jbG9ja19oeicpO1xyXG4gIGF3YWl0IGNsb2NrLmZpbGwoJzgwMDAwMDAwJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHtuYW1lOidQYXJhbWV0ZXIgc3BlaWNoZXJuIOKGkicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdUZWNobm9sb2dpZS0gdW5kIFRpbWluZy1QYXJhbWV0ZXIgZ2VzcGVpY2hlcnQuJykpLnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcclxuICBhd2FpdCBleHBlY3QoY2xvY2spLnRvSGF2ZVZhbHVlKCc4MDAwMDAwMCcpO1xyXG4gIGNvbnN0IHVwZGF0ZWQgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJyx7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgZXhwZWN0KHVwZGF0ZWQucGFyYW1ldGVycy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5jYW5fZmQucHJvdmVuYW5jZS5jYW5fY2xvY2tfaHouaGFyZHdhcmVfZXZpZGVuY2UpLnRvQmUoZmFsc2UpO1xyXG4gIGV4cGVjdCh1cGRhdGVkLnBhcmFtZXRlcl9zdG9yYWdlLnNvdXJjZSkudG9CZSgnUFJPSkVDVF9VU0VSX0RFRklORURfVkFMVUVTJyk7XHJcbiAgY29uc3QgdXNlclZhbHVlcyA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMvdXNlci1kZWZpbmVkLXZhbHVlcycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdCh1c2VyVmFsdWVzLnByb2plY3RfaWQpLnRvQmUocHJvamVjdCk7XHJcbiAgZXhwZWN0KHVzZXJWYWx1ZXMudmFsdWVfb3JpZ2luKS50b0JlKCdVU0VSX0RFRklORURfVkFMVUUnKTtcclxuICBleHBlY3QodXNlclZhbHVlcy5wYXJhbWV0ZXJzLnNpbXVsYXRpb25fcGFyYW1ldGVyX2Fzc3VtcHRpb25zLmNhbl9mZC52YWx1ZXMuY2FuX2Nsb2NrX2h6KS50b0JlKDgwMDAwMDAwKTtcclxuICBleHBlY3QodXNlclZhbHVlcy5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfZGVmYXVsdHMpLnRvQmVVbmRlZmluZWQoKTtcclxuICBleHBlY3QodXNlclZhbHVlcy5wYXJhbWV0ZXJzLmRlZmF1bHRzX3NvdXJjZSkudG9CZVVuZGVmaW5lZCgpO1xyXG59KTtcclxuXHJcbnRlc3QoJ3NhdmVkIGNvbmZpcm1lZCB3aXphcmQgY29udGV4dCBwcm9wb3NlcyBpdHMgYnVzIHdpdGhvdXQgaW52ZW50aW5nIHBhcmFtZXRlciBjb25maXJtYXRpb24gQHRlY2hub2xvZ3ktcmV2aWV3JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XHJcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXdpemFyZC1idXMtJyArIHJhbmRvbVVVSUQoKTtcclxuICBjb25zdCBoZWFkZXJzID0geyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9O1xyXG4gIGNvbnN0IHNlZWRlZCA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wYXRjaCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9jb250ZXh0P3ZpZXc9c3VtbWFyeScsIHtcclxuICAgIGhlYWRlcnMsXHJcbiAgICBkYXRhOiB7IGFnZW50X3dpemFyZF9zdGF0dXM6IHsgY29uZmlybWVkX2F0OiAnMjAyNi0wOS0zMFQxMTozMjo1MFonLCBtb2RlbF90eXBlOiAnY3VzdG9tJyxcclxuICAgICAgY29tbXVuaWNhdGlvbl9zeXN0ZW1fY291bnRzOiBbeyBpZDogJ2kyYycsIGNvdW50OiAxIH1dIH0gfSxcclxuICB9KTtcclxuICBleHBlY3Qoc2VlZGVkLm9rKCksIGF3YWl0IHNlZWRlZC50ZXh0KCkpLnRvQmUodHJ1ZSk7XHJcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvP21vZGU9cGFyYW1ldGVycyZwcm9qZWN0PSR7cHJvamVjdH1gKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZG9tYWluJykpLnRvSGF2ZVZhbHVlKCdjdXN0b20nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjdGVjaG5vbG9neScpKS50b0hhdmVWYWx1ZSgnaTJjJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdVTlZFUklGSUVEIMK3IEtlaW5lIGJlc3TDpHRpZ3RlIFRlY2hub2xvZ2llYXVzd2FobCcpKS50b0JlVmlzaWJsZSgpO1xyXG4gIGNvbnN0IHBhcmFtZXRlcnMgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywgeyBoZWFkZXJzIH0pKS5qc29uKCk7XHJcbiAgZXhwZWN0KHBhcmFtZXRlcnMucGFyYW1ldGVycy50ZWNobm9sb2d5KS50b0JlVW5kZWZpbmVkKCk7XHJcbn0pO1xyXG5cclxudGVzdCgnbWl4ZWQgcHJvamVjdCBzaG93cyBleGFjdCBMSU4gcHJvZmlsZSwgcmVqZWN0cyAyTSBhbmQgcHJlc2VydmVzIENBTi1GRCB3aGlsZSBzYXZpbmcgTElOIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1yYXRlLScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgaGVhZGVycyA9IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfTtcclxuICBjb25zdCBpbml0aWFsID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycsIHsgaGVhZGVycyB9KSkuanNvbigpO1xyXG4gIGNvbnN0IHBhcmFtZXRlcnMgPSB7IC4uLmluaXRpYWwucGFyYW1ldGVycywgaW5kdXN0cnk6ICdhdXRvbW90aXZlJywgdGVjaG5vbG9neTogJ2Nhbl9mZCcsIGRlZmF1bHRzX3NvdXJjZTogJ3RlY2hub2xvZ3ktcmVnaXN0cnknLFxyXG4gICAgYml0cmF0ZTogMjAwMDAwMCwgYXJiaXRyYXRpb25fYml0cmF0ZTogNTAwMDAwLCBkYXRhX2JpdHJhdGU6IDIwMDAwMDAsXHJcbiAgICBuZXR3b3JrczogW3sgaWQ6J2xpbi1vbmUnLCB0ZWNobm9sb2d5OidMSU4nLCBuYW1lOidMSU4gVGVzdCcgfSwge2lkOidjYW4tb25lJywgdGVjaG5vbG9neTonQ0FOX0ZEJyxuYW1lOidDQU4gVGVzdCd9XSB9O1xyXG4gIGNvbnN0IHNlZWRlZCA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wYXRjaCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywgeyBoZWFkZXJzLCBkYXRhOntwYXJhbWV0ZXJzLCBleHBlY3RlZF90b2tlbjppbml0aWFsLmVkaXRfdG9rZW59IH0pO1xyXG4gIGV4cGVjdChzZWVkZWQub2soKSwgYXdhaXQgc2VlZGVkLnRleHQoKSkudG9CZSh0cnVlKTtcclxuICAvLyBEZWxheSB0aGUgcmVhbCByZWFkOiBjb250cm9scyBtdXN0IG5vdCB1c2UgZGVmYXVsdHMgYW5kIHRoZW4gb3ZlcndyaXRlIGEgdXNlciBzZWxlY3Rpb24uXHJcbiAgYXdhaXQgcGFnZS5yb3V0ZSgnKiovYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLCBhc3luYyByb3V0ZSA9PiB7XHJcbiAgICBpZiAocm91dGUucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnR0VUJykgYXdhaXQgbmV3IFByb21pc2UocmVzb2x2ZSA9PiBzZXRUaW1lb3V0KHJlc29sdmUsIDMwMCkpO1xyXG4gICAgYXdhaXQgcm91dGUuY29udGludWUoKTtcclxuICB9KTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8/bW9kZT1wYXJhbWV0ZXJzJnByb2plY3Q9JHtwcm9qZWN0fWApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyN0ZWNobm9sb2d5JykpLnRvSGF2ZVZhbHVlKCdjYW5fZmQnKTtcclxuICBhd2FpdCBwYWdlLmxvY2F0b3IoJyN0ZWNobm9sb2d5Jykuc2VsZWN0T3B0aW9uKCdsaW4nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCdpbnB1dFtuYW1lPVwibGluX2JpdHJhdGVfYnBzXCJdJykpLm5vdC50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignLnBhcmFtZXRlci1ncm91cC1jb21tb24gI2xpbl9iaXRyYXRlX2JwcycpKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNsaW5fcmVnaXN0ZXJlZF9zb3VyY2UnKSkudG9IYXZlVmFsdWUoJycpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNsaW5fcmVnaXN0ZXJlZF9zb3VyY2UnKSkubm90LnRvQmVWaXNpYmxlKCk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6J1BhcmFtZXRlciBzcGVpY2hlcm4g4oaSJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVRleHQoJ1RlY2hub2xvZ2llLSB1bmQgVGltaW5nLVBhcmFtZXRlciBnZXNwZWljaGVydC4nKSkudG9CZVZpc2libGUoKTtcclxuICBjb25zdCBub0Zha2VTb3VyY2VzID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChub0Zha2VTb3VyY2VzLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnMubGluLnZhbHVlcy5saW5fcmVnaXN0ZXJlZF9zb3VyY2UpLnRvQmVVbmRlZmluZWQoKTtcclxuICBleHBlY3Qobm9GYWtlU291cmNlcy5wYXJhbWV0ZXJzLnNpbXVsYXRpb25fcGFyYW1ldGVyX2Fzc3VtcHRpb25zLmxpbi52YWx1ZXMubGluX2NvbW1hbmRlcl9ub2RlX2lkKS50b0JlVW5kZWZpbmVkKCk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcucGFyYW1ldGVyLWRldGFpbHMnKS5maWx0ZXIoe2hhczpwYWdlLmxvY2F0b3IoJyNsaW5fcmVnaXN0ZXJlZF9zb3VyY2UnKX0pLmxvY2F0b3IoJzpzY29wZSA+IHN1bW1hcnknKS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5TGFiZWwoJ1Byb2ZpbHF1ZWxsZScse2V4YWN0OnRydWV9KSkudG9IYXZlVmFsdWUoJycpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlMYWJlbCgnUHJvZmlscXVlbGxlJyx7ZXhhY3Q6dHJ1ZX0pLmZpbGwoJ3Byb2plY3Q6cmV2aWV3ZWQtbGluLXByb2ZpbGUnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonUGFyYW1ldGVyIHNwZWljaGVybiDihpInLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnVGVjaG5vbG9naWUtIHVuZCBUaW1pbmctUGFyYW1ldGVyIGdlc3BlaWNoZXJ0LicpKS50b0JlVmlzaWJsZSgpO1xyXG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3RlY2hub2xvZ3knKSkudG9IYXZlVmFsdWUoJ2Nhbl9mZCcpO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignI3RlY2hub2xvZ3knKS5zZWxlY3RPcHRpb24oJ2xpbicpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNsaW5fcmVnaXN0ZXJlZF9zb3VyY2UnKSkudG9IYXZlVmFsdWUoJ3Byb2plY3Q6cmV2aWV3ZWQtbGluLXByb2ZpbGUnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcucGFyYW1ldGVyLWRldGFpbHNbb3Blbl0nKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgYXdhaXQgcmV2ZWFsUGFyYW1ldGVyKHBhZ2UsJ2xpbl9lZGl0aW9uJyk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCdzZWxlY3RbbmFtZT1cImxpbl9lZGl0aW9uXCJdJykuc2VsZWN0T3B0aW9uKCdMSU5fMl8yQV8yMDEwJyk7XHJcbiAgYXdhaXQgcmV2ZWFsUGFyYW1ldGVyKHBhZ2UsJ2xpbl9waHlzaWNhbF9wcm9maWxlJyk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCdzZWxlY3RbbmFtZT1cImxpbl9waHlzaWNhbF9wcm9maWxlXCJdJykuc2VsZWN0T3B0aW9uKCdMSU5fMl8yQV9TSU5HTEVfV0lSRScpO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignI3BhcmFtZXRlci1maWVsZC1saW5fYml0cmF0ZV9icHMgLnBhcmFtZXRlci1kZWZhdWx0LWRldGFpbHMgPiBzdW1tYXJ5JykuY2xpY2soKTtcclxuICBhd2FpdCBwYWdlLmxvY2F0b3IoJ2Rpdlt0aXRsZV0nKS5maWx0ZXIoe2hhczpwYWdlLmxvY2F0b3IoJyNsaW5fYml0cmF0ZV9icHMnKX0pXHJcbiAgICAuZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidCZWRpbmd0ZW4gU3RhbmRhcmR3ZXJ0IMO8YmVybmVobWVuJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCdpbnB1dFtuYW1lPVwibGluX2JpdHJhdGVfYnBzXCJdJykpLnRvSGF2ZVZhbHVlKCcxOTIwMCcpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJkYXRhX2JpdHJhdGVcIl0nKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgY29uc3QgaW52YWxpZCA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wYXRjaCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywge2hlYWRlcnMsXHJcbiAgICBkYXRhOntwYXJhbWV0ZXJzOnsuLi5wYXJhbWV0ZXJzLHRlY2hub2xvZ3lfcGFyYW1ldGVyczp7bGluOnt2YWx1ZXM6e2xpbl9lZGl0aW9uOidMSU5fMl8yQV8yMDEwJyxsaW5fcGh5c2ljYWxfcHJvZmlsZTonTElOXzJfMkFfU0lOR0xFX1dJUkUnLGxpbl9iaXRyYXRlX2JwczoyMDAwMDAwfSxcclxuICAgICAgcHJvdmVuYW5jZTpPYmplY3QuZnJvbUVudHJpZXMoT2JqZWN0LmVudHJpZXMoe2xpbl9lZGl0aW9uOidMSU5fMl8yQV8yMDEwJyxsaW5fcGh5c2ljYWxfcHJvZmlsZTonTElOXzJfMkFfU0lOR0xFX1dJUkUnLGxpbl9iaXRyYXRlX2JwczoyMDAwMDAwfSlcclxuICAgICAgICAubWFwKChba2V5LHZhbHVlXSk9PltrZXkse3NvdXJjZTonVVNFUl9DT05GSVJNRUQnLHN0YXR1czonQ09ORklSTUVEJyx2YWx1ZX1dKSl9fX19fSk7XHJcbiAgZXhwZWN0KGludmFsaWQuc3RhdHVzKCkpLnRvQmUoNDAwKTtcclxuICBhd2FpdCBwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJsaW5fYml0cmF0ZV9icHNcIl0nKS5maWxsKCc5NjAwJyk7XHJcbiAgY29uc3QgcmVzcG9uc2UgPSBwYWdlLndhaXRGb3JSZXNwb25zZShyID0+IHIudXJsKCkuaW5jbHVkZXMoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycpICYmIHIucmVxdWVzdCgpLm1ldGhvZCgpID09PSAnUEFUQ0gnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywge25hbWU6J1BhcmFtZXRlciBzcGVpY2hlcm4g4oaSJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBleHBlY3QoKGF3YWl0IHJlc3BvbnNlKS5vaygpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IHNhdmVkID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycsIHtoZWFkZXJzfSkpLmpzb24oKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy5uZXR3b3JrcykudG9FcXVhbChwYXJhbWV0ZXJzLm5ldHdvcmtzKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy50ZWNobm9sb2d5KS50b0JlKCdjYW5fZmQnKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy5kYXRhX2JpdHJhdGUpLnRvQmUoMjAwMDAwMCk7XHJcbiAgZXhwZWN0KHNhdmVkLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnMubGluLnZhbHVlcy5saW5fYml0cmF0ZV9icHMpLnRvQmUoOTYwMCk7XHJcbiAgZXhwZWN0KHNhdmVkLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnMubGluLnByb3ZlbmFuY2UubGluX2JpdHJhdGVfYnBzKS50b01hdGNoT2JqZWN0KHtzdGF0dXM6J0FTU1VNRUQnLGhhcmR3YXJlX2V2aWRlbmNlOmZhbHNlfSk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjdGVjaG5vbG9neScpKS50b0hhdmVWYWx1ZSgnY2FuX2ZkJyk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjdGVjaG5vbG9neScpLnNlbGVjdE9wdGlvbignbGluJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cImxpbl9iaXRyYXRlX2Jwc1wiXScpKS50b0hhdmVWYWx1ZSgnOTYwMCcpO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignI3RlY2hub2xvZ3knKS5zZWxlY3RPcHRpb24oJ2Nhbl9mZCcpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJkYXRhX2JpdHJhdGVcIl0nKSkudG9IYXZlVmFsdWUoJzIwMDAwMDAnKTtcclxufSk7XHJcblxyXG50ZXN0KCdzdGFsZSBwYXJhbWV0ZXIgcmV2aXNpb24gcmVqZWN0cyB0aGUgcmVhbCB3cml0ZSBhbmQgcHJlc2VydmVzIGNvbmZpcm1lZCByYXRlcyBAdGVjaG5vbG9neS1yZXZpZXcnLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtcmF0ZS1jb25mbGljdC0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGhlYWRlcnMgPSB7J1gtUHJvamVjdC1JRCc6cHJvamVjdH07XHJcbiAgY29uc3QgZmlyc3QgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywge2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGNvbnN0IHBhcmFtZXRlcnMgPSB7Li4uZmlyc3QucGFyYW1ldGVycywgdGVjaG5vbG9neTonbGluJywgYml0cmF0ZToxOTIwMH07XHJcbiAgY29uc3Qgc2F2ZWQgPSBhd2FpdCBwYWdlLnJlcXVlc3QucGF0Y2goJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycsIHtoZWFkZXJzLGRhdGE6e3BhcmFtZXRlcnMsZXhwZWN0ZWRfdG9rZW46Zmlyc3QuZWRpdF90b2tlbn19KTtcclxuICBleHBlY3Qoc2F2ZWQub2soKSwgYXdhaXQgc2F2ZWQudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IGNvbmZsaWN0ID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBhdGNoKCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLCB7aGVhZGVycyxkYXRhOntwYXJhbWV0ZXJzOnsuLi5wYXJhbWV0ZXJzLGJpdHJhdGU6OTYwMH0sZXhwZWN0ZWRfdG9rZW46Zmlyc3QuZWRpdF90b2tlbn19KTtcclxuICBleHBlY3QoY29uZmxpY3Quc3RhdHVzKCkpLnRvQmUoNDA5KTtcclxuICBjb25zdCBjdXJyZW50ID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChjdXJyZW50LnBhcmFtZXRlcnMuYml0cmF0ZSkudG9CZSgxOTIwMCk7XHJcbn0pO1xyXG5cclxudGVzdCgnZXZlcnkgYnVzIGV4cG9zZXMgaXRzIG93biBzZXJ2ZXIgZGVmYXVsdHMgaW4gdGhlIGFjdHVhbCBwYXJhbWV0ZXIgZm9ybSBAdGVjaG5vbG9neS1yZXZpZXcnLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtY2F0YWxvZy1kZWZhdWx0cy0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGNhdGFsb2cgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS90ZWNobm9sb2dpZXMnKSkuanNvbigpO1xyXG4gIGNvbnN0IHByb2ZpbGVzID0gbmV3IE1hcDxzdHJpbmcsIGFueT4oY2F0YWxvZy5kb21haW5zLmZsYXRNYXAoKGRvbWFpbjogYW55KSA9PiBkb21haW4udGVjaG5vbG9naWVzKS5tYXAoKHByb2ZpbGU6IGFueSkgPT4gW3Byb2ZpbGUuaWQsIHByb2ZpbGVdKSk7XHJcbiAgZXhwZWN0KHByb2ZpbGVzLnNpemUpLnRvQmUoY2F0YWxvZy50ZWNobm9sb2d5X2NvdW50KTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8/bW9kZT1wYXJhbWV0ZXJzJnByb2plY3Q9JHtwcm9qZWN0fWApO1xyXG4gIGNvbnN0IGluaXRpYWxCdXMgPSBwYWdlLmdldEJ5TGFiZWwoJ0J1cyAvIFByb3Rva29sbCBhdXN3w6RobGVuJyk7XHJcbiAgYXdhaXQgZXhwZWN0KGluaXRpYWxCdXMubG9jYXRvcignb3B0aW9uW3ZhbHVlPVwiaTJjXCJdJykpLnRvSGF2ZUNvdW50KDEpO1xyXG4gIGF3YWl0IGluaXRpYWxCdXMuc2VsZWN0T3B0aW9uKCdpMmMnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5TGFiZWwoJ0Fud2VuZHVuZ3NiZXJlaWNoIGF1c3fDpGhsZW4nKS5zZWxlY3RPcHRpb24oJ2N1c3RvbScpO1xyXG4gIGZvciAoY29uc3QgW2lkLCBwcm9maWxlXSBvZiBwcm9maWxlcykge1xyXG4gICAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjdGVjaG5vbG9neScpLnNlbGVjdE9wdGlvbihpZCk7XHJcbiAgICBmb3IgKGNvbnN0IGZpZWxkIG9mIHByb2ZpbGUucGFyYW1ldGVyX3NjaGVtYS5maWx0ZXIoKGl0ZW06IGFueSkgPT4gWydiaXRyYXRlJywgJ2FyYml0cmF0aW9uX2JpdHJhdGUnLCAnZGF0YV9iaXRyYXRlJ10uaW5jbHVkZXMoaXRlbS5rZXkpKSkge1xyXG4gICAgICBjb25zdCBpbnB1dCA9IHBhZ2UubG9jYXRvcihgaW5wdXRbbmFtZT1cIiR7ZmllbGQua2V5fVwiXWApO1xyXG4gICAgICBhd2FpdCBleHBlY3QoaW5wdXQsIGAke2lkfS8ke2ZpZWxkLmtleX1gKS5ub3QudG9IYXZlVmFsdWUoJycpO1xyXG4gICAgICBleHBlY3QoYXdhaXQgaW5wdXQuZXZhbHVhdGUoKGVsOiBIVE1MSW5wdXRFbGVtZW50KSA9PiBlbC5jaGVja1ZhbGlkaXR5KCkpLCBgJHtpZH0vJHtmaWVsZC5rZXl9YCkudG9CZSh0cnVlKTtcclxuICAgIH1cclxuICAgIGNvbnN0IGVtcHR5ID0gYXdhaXQgcGFnZS5sb2NhdG9yKCdmb3JtLmNvbmZpZy1wYW5lbCAucGFyYW1ldGVyLWdyb3VwcycpLmV2YWx1YXRlKGdyb3VwcyA9PlxyXG4gICAgICBbLi4uZ3JvdXBzLnF1ZXJ5U2VsZWN0b3JBbGwoJ2lucHV0LHNlbGVjdCx0ZXh0YXJlYScpXVxyXG4gICAgICAgIC5maWx0ZXIoZWxlbWVudCA9PiAoZWxlbWVudCBpbnN0YW5jZW9mIEhUTUxJbnB1dEVsZW1lbnQgfHwgZWxlbWVudCBpbnN0YW5jZW9mIEhUTUxTZWxlY3RFbGVtZW50IHx8IGVsZW1lbnQgaW5zdGFuY2VvZiBIVE1MVGV4dEFyZWFFbGVtZW50KVxyXG4gICAgICAgICAgJiYgZWxlbWVudC50eXBlICE9PSAnY2hlY2tib3gnICYmIGVsZW1lbnQudmFsdWUgPT09ICcnKVxyXG4gICAgICAgIC5tYXAoZWxlbWVudCA9PiAoZWxlbWVudCBhcyBIVE1MSW5wdXRFbGVtZW50KS5uYW1lKSk7XHJcbiAgICBjb25zdCByZWZlcmVuY2VzID0gcHJvZmlsZS5wYXJhbWV0ZXJfc2NoZW1hLmZpbHRlcigoZmllbGQ6YW55KSA9PiBmaWVsZC52YWx1ZV9yb2xlICYmIGZpZWxkLnZhbHVlX3JvbGUgIT09ICdDT05GSUdVUkFUSU9OJyAmJiBmaWVsZC5zaW11bGF0aW9uX2RlZmF1bHQgPT09IG51bGwpLm1hcCgoZmllbGQ6YW55KT0+ZmllbGQua2V5KTtcclxuICAgIGV4cGVjdChlbXB0eS5maWx0ZXIoKGtleTpzdHJpbmcpPT4hcmVmZXJlbmNlcy5pbmNsdWRlcyhrZXkpKSwgaWQpLnRvRXF1YWwoW10pO1xyXG4gICAgZm9yIChjb25zdCBrZXkgb2YgcmVmZXJlbmNlcykgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcihgW25hbWU9XCIke2tleX1cIl1gKSkudG9IYXZlVmFsdWUoJycpO1xyXG4gICAgaWYgKGlkID09PSAnbm1lYTIwMDAnKSB7XHJcbiAgICAgIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJ2lucHV0W25hbWU9XCJiaXRyYXRlXCJdJykpLnRvSGF2ZVZhbHVlKCcyNTAwMDAnKTtcclxuICAgICAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignaW5wdXRbbmFtZT1cIm10dV9ieXRlc1wiXScpKS50b0hhdmVDb3VudCgwKTtcclxuICAgIH1cclxuICB9XHJcbiAgLy8gU3dpdGNoaW5nIHRocm91Z2ggdGhlIGVudGlyZSBjYXRhbG9nIGlzIGEgcmV2aWV3LCBub3QgYSBwZXJzaXN0ZW5jZSBhY3Rpb24uXHJcbiAgY29uc3Qgc2F2ZWQgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy93b3JrZmxvdy9wYXJhbWV0ZXJzJywge2hlYWRlcnM6eydYLVByb2plY3QtSUQnOnByb2plY3R9fSkpLmpzb24oKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy50ZWNobm9sb2d5KS50b0JlVW5kZWZpbmVkKCk7XHJcbn0pO1xyXG5cclxudGVzdCgnaGFyZHdhcmUgZWRpdG9yIHVzZXMgdGhlIHNlbGVjdGVkIHByb2ZpbGUgYW5kIHNhdmVzIHByb3Bvc2FscyB3aXRob3V0IGludmVudGluZyBkZXZpY2UgY29uZmlybWF0aW9uIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xyXG4gIGNvbnN0IHByb2plY3QgPSAnbmlzLWUyZS1kZXZpY2UtcHJvZmlsZS0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGhlYWRlcnMgPSB7J1gtUHJvamVjdC1JRCc6IHByb2plY3R9O1xyXG4gIGNvbnN0IG5vZGVSZXNwb25zZSA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2hhcmR3YXJlLW5vZGVzJywge2hlYWRlcnMsIGRhdGE6e25hbWU6J1JldmlldyBDb250cm9sbGVyJywgZGV2aWNlX3R5cGU6J0VtYmVkZGVkQ29udHJvbGxlcicsIGRvbWFpbjonZW1iZWRkZWRfc3lzdGVtcyd9fSk7XHJcbiAgZXhwZWN0KG5vZGVSZXNwb25zZS5vaygpLCBhd2FpdCBub2RlUmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IG5vZGUgPSBhd2FpdCBub2RlUmVzcG9uc2UuanNvbigpO1xyXG4gIGNvbnN0IHBvcnRSZXNwb25zZSA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2hhcmR3YXJlLWludGVyZmFjZXMnLCB7aGVhZGVycywgZGF0YTp7bmFtZTonRGV2aWNlIFJldmlldyBQb3J0JywgaGFyZHdhcmVfbm9kZV9pZDpub2RlLmlkLCB0ZWNobm9sb2d5OidJMkMnLFxyXG4gICAgY2FwYWJpbGl0aWVzOntsb2NhbF90aW1pbmdfZXZpZGVuY2U6e3NsYXZlX2FkZHJlc3M6JycsY29uZmlybWVkOmZhbHNlfX19fSk7XHJcbiAgZXhwZWN0KHBvcnRSZXNwb25zZS5vaygpLCBhd2FpdCBwb3J0UmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IHBvcnQgPSBhd2FpdCBwb3J0UmVzcG9uc2UuanNvbigpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9lbmdpbmVlcmluZz9wcm9qZWN0PSR7cHJvamVjdH0mcmVzb3VyY2U9aGFyZHdhcmUtaW50ZXJmYWNlcyZvYmplY3Q9JHtwb3J0LmlkfSZlZGl0PTFgKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9sb2NhbF9pMmNfbW9kZScpKS50b0hhdmVWYWx1ZSgnU1RBTkRBUkQnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9sb2NhbF9iaXRyYXRlX2JwcycpKS50b0hhdmVWYWx1ZSgnMTAwMDAwJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfZGF0YV9iaXRyYXRlJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X2xvY2FsX3NsYXZlX2FkZHJlc3MnKSkubm90LnRvSGF2ZVZhbHVlKCcnKTtcclxuICBhd2FpdCBwYWdlLmxvY2F0b3IoJyNlZGl0X3RlY2hub2xvZ3knKS5zZWxlY3RPcHRpb24oJ1NQSScpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X2xvY2FsX2kyY19tb2RlJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X2xvY2FsX2NoaXBfc2VsZWN0JykpLm5vdC50b0hhdmVWYWx1ZSgnJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfbG9jYWxfYml0cmF0ZV9icHMnKSkubm90LnRvSGF2ZVZhbHVlKCcnKTtcclxuICBhd2FpdCBwYWdlLmxvY2F0b3IoJyNlZGl0X3RlY2hub2xvZ3knKS5zZWxlY3RPcHRpb24oJ0NBTl9GRCcpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X2xvY2FsX2NoaXBfc2VsZWN0JykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIC8vIEV4cGxpY2l0IHNjZW5hcmlvIHByb3Bvc2FscyBkbyBub3QgcmV1c2UgdGhlIHByZXZpb3VzIEkyQyBkZXZpY2Ugc2V0dGluZy5cclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9iaXRyYXRlJykpLnRvSGF2ZVZhbHVlKCc1MDAwMDAnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9kYXRhX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzIwMDAwMDAnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCdbbmFtZT1cImVkaXRfbG9jYWxfY29uZmlybWVkXCJdJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignI2VkaXRfdGVjaG5vbG9neScpLnNlbGVjdE9wdGlvbignSTJDJyk7XHJcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHtuYW1lOifDhG5kZXJ1bmdlbiBzcGVpY2hlcm4nLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X3RlY2hub2xvZ3knKSkudG9IYXZlQ291bnQoMCk7XHJcbiAgY29uc3Qgc2F2ZWQgPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldChgL2FwaS9lbmdpbmVlcmluZy9oYXJkd2FyZS1pbnRlcmZhY2VzLyR7cG9ydC5pZH1gLCB7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgZXhwZWN0KHNhdmVkLmJpdHJhdGUpLnRvQmUoMTAwMDAwKTtcclxuICBleHBlY3Qoc2F2ZWQuZGF0YV9iaXRyYXRlKS50b0JlTnVsbCgpO1xyXG4gIGV4cGVjdChzYXZlZC5jYXBhYmlsaXRpZXMubG9jYWxfdGltaW5nX2V2aWRlbmNlKS50b01hdGNoT2JqZWN0KHt0ZWNobm9sb2d5OidJMkMnLCBpMmNfbW9kZTonU1RBTkRBUkQnLCBiaXRyYXRlX2JwczoxMDAwMDAsIGNvbmZpcm1lZDpmYWxzZX0pO1xyXG4gIGV4cGVjdChzYXZlZC5jYXBhYmlsaXRpZXMubG9jYWxfdGltaW5nX2V2aWRlbmNlLnNsYXZlX2FkZHJlc3MpLnRvQmVOdWxsKCk7XHJcbiAgZXhwZWN0KHNhdmVkLmNhcGFiaWxpdGllcy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5pMmMucHJvdmVuYW5jZS5zbGF2ZV9hZGRyZXNzLmhhcmR3YXJlX2V2aWRlbmNlKS50b0JlKGZhbHNlKTtcclxuICAvLyBFeGlzdGluZyB2ZXJpZmllZCBkZXZpY2UgZmFjdHMgb3V0cmFuayBzdGFuZGFyZCBwcm9wb3NhbHMuIEEgY2hhbmdlZFxyXG4gIC8vIGRldmljZSBzZXR0aW5nIGNhbm5vdCBzaWxlbnRseSByZXVzZSB0aGUgb2xkIGNvbmZpcm1hdGlvbi5cclxuICBjb25zdCBhY3R1YWwgPSBhd2FpdCBwYWdlLnJlcXVlc3QucGF0Y2goYC9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtaW50ZXJmYWNlcy8ke3BvcnQuaWR9YCwge2hlYWRlcnMsXHJcbiAgICBkYXRhOntiaXRyYXRlOjQwMDAwMCwgY2FwYWJpbGl0aWVzOnsuLi5zYXZlZC5jYXBhYmlsaXRpZXMsIGxvY2FsX3RpbWluZ19ldmlkZW5jZTp7XHJcbiAgICAgIGV2aWRlbmNlX3Njb3BlOidDT05UUk9MTEVSX1BPUlQnLCBtYXN0ZXJfbm9kZV9pZDpub2RlLmlkLCBpMmNfbW9kZTonRkFTVCcsIGJpdHJhdGVfYnBzOjQwMDAwMCxcclxuICAgICAgY29uZmlybWVkOnRydWUsIHNvdXJjZTonaXNvbGF0ZWQtdmlydHVhbC1maXh0dXJlOmV4cGxpY2l0LUZBU1QtY29udHJvbGxlci1wb3J0J319fX0pO1xyXG4gIGV4cGVjdChhY3R1YWwub2soKSwgYXdhaXQgYWN0dWFsLnRleHQoKSkudG9CZSh0cnVlKTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vZW5naW5lZXJpbmc/cHJvamVjdD0ke3Byb2plY3R9JnJlc291cmNlPWhhcmR3YXJlLWludGVyZmFjZXMmb2JqZWN0PSR7cG9ydC5pZH0mZWRpdD0xYCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfbG9jYWxfaTJjX21vZGUnKSkudG9IYXZlVmFsdWUoJ0ZBU1QnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9sb2NhbF9iaXRyYXRlX2JwcycpKS50b0hhdmVWYWx1ZSgnNDAwMDAwJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignW25hbWU9XCJlZGl0X2xvY2FsX2NvbmZpcm1lZFwiXScpKS50b0JlQ2hlY2tlZCgpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7bmFtZTonw4RuZGVydW5nZW4gc3BlaWNoZXJuJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF90ZWNobm9sb2d5JykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGNvbnN0IHByZXNlcnZlZCA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KGAvYXBpL2VuZ2luZWVyaW5nL2hhcmR3YXJlLWludGVyZmFjZXMvJHtwb3J0LmlkfWAsIHtoZWFkZXJzfSkpLmpzb24oKTtcclxuICBleHBlY3QocHJlc2VydmVkLmNhcGFiaWxpdGllcy5sb2NhbF90aW1pbmdfZXZpZGVuY2UpLnRvTWF0Y2hPYmplY3Qoe2kyY19tb2RlOidGQVNUJyxiaXRyYXRlX2Jwczo0MDAwMDAsY29uZmlybWVkOnRydWV9KTtcclxuICBleHBlY3QocHJlc2VydmVkLmNhcGFiaWxpdGllcy5sb2NhbF90aW1pbmdfZXZpZGVuY2Uuc2xhdmVfYWRkcmVzcykudG9CZU51bGwoKTtcclxuICBleHBlY3QocHJlc2VydmVkLmNhcGFiaWxpdGllcy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5pMmMucHJvdmVuYW5jZS5zbGF2ZV9hZGRyZXNzLmhhcmR3YXJlX2V2aWRlbmNlKS50b0JlKGZhbHNlKTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vZW5naW5lZXJpbmc/cHJvamVjdD0ke3Byb2plY3R9JnJlc291cmNlPWhhcmR3YXJlLWludGVyZmFjZXMmb2JqZWN0PSR7cG9ydC5pZH0mZWRpdD0xYCk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjZWRpdF9sb2NhbF9pMmNfbW9kZScpLnNlbGVjdE9wdGlvbignRkFTVF9QTFVTJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignW25hbWU9XCJlZGl0X2xvY2FsX2NvbmZpcm1lZFwiXScpKS5ub3QudG9CZUNoZWNrZWQoKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywge25hbWU6J8OEbmRlcnVuZ2VuIHNwZWljaGVybicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfdGVjaG5vbG9neScpKS50b0hhdmVDb3VudCgwKTtcclxuICBjb25zdCBjaGFuZ2VkID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoYC9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtaW50ZXJmYWNlcy8ke3BvcnQuaWR9YCwge2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChjaGFuZ2VkLmNhcGFiaWxpdGllcy5sb2NhbF90aW1pbmdfZXZpZGVuY2UpLnRvTWF0Y2hPYmplY3Qoe2kyY19tb2RlOidGQVNUX1BMVVMnLGNvbmZpcm1lZDpmYWxzZX0pO1xyXG59KTtcclxuXHJcblxyXG50ZXN0KCdDQU4tRkQgZGV2aWNlIGVkaXRvciByZXRhaW5zIGNoYW5nZWQgc2ltdWxhdGlvbiByYXRlcyBzZXBhcmF0ZWx5IGZyb20gYWN0dWFsIGhhcmR3YXJlIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7cGFnZX0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0PSduaXMtZTJlLWRldmljZS1hc3N1bXB0aW9ucy0nK3JhbmRvbVVVSUQoKTtcclxuICBjb25zdCBoZWFkZXJzPXsnWC1Qcm9qZWN0LUlEJzpwcm9qZWN0fTtcclxuICBjb25zdCBub2RlUmVzcG9uc2U9YXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtbm9kZXMnLHtoZWFkZXJzLGRhdGE6e25hbWU6J1NjZW5hcmlvIENvbnRyb2xsZXInLGRldmljZV90eXBlOidFbWJlZGRlZENvbnRyb2xsZXInfX0pO1xyXG4gIGV4cGVjdChub2RlUmVzcG9uc2Uub2soKSxhd2FpdCBub2RlUmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IG5vZGU9YXdhaXQgbm9kZVJlc3BvbnNlLmpzb24oKTtcclxuICBjb25zdCBwb3J0UmVzcG9uc2U9YXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtaW50ZXJmYWNlcycse2hlYWRlcnMsZGF0YTp7bmFtZTonU2NlbmFyaW8gQ0FOIFBvcnQnLGhhcmR3YXJlX25vZGVfaWQ6bm9kZS5pZCx0ZWNobm9sb2d5OidDQU5fRkQnfX0pO1xyXG4gIGV4cGVjdChwb3J0UmVzcG9uc2Uub2soKSxhd2FpdCBwb3J0UmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IHBvcnQ9YXdhaXQgcG9ydFJlc3BvbnNlLmpzb24oKTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vZW5naW5lZXJpbmc/cHJvamVjdD0ke3Byb2plY3R9JnJlc291cmNlPWhhcmR3YXJlLWludGVyZmFjZXMmb2JqZWN0PSR7cG9ydC5pZH0mZWRpdD0xYCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfYml0cmF0ZScpKS50b0hhdmVWYWx1ZSgnNTAwMDAwJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfZGF0YV9iaXRyYXRlJykpLnRvSGF2ZVZhbHVlKCcyMDAwMDAwJyk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjZWRpdF9iaXRyYXRlJykuZmlsbCgnMjUwMDAwJyk7XHJcbiAgYXdhaXQgcGFnZS5sb2NhdG9yKCcjZWRpdF9kYXRhX2JpdHJhdGUnKS5maWxsKCcyNTAwMDAnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonw4RuZGVydW5nZW4gc3BlaWNoZXJuJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF90ZWNobm9sb2d5JykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGNvbnN0IHNhdmVkPWF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KGAvYXBpL2VuZ2luZWVyaW5nL2hhcmR3YXJlLWludGVyZmFjZXMvJHtwb3J0LmlkfWAse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChzYXZlZC5iaXRyYXRlKS50b0JlTnVsbCgpO1xyXG4gIGV4cGVjdChzYXZlZC5kYXRhX2JpdHJhdGUpLnRvQmVOdWxsKCk7XHJcbiAgZXhwZWN0KHNhdmVkLmNhcGFiaWxpdGllcy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5jYW5fZmQudmFsdWVzKS50b01hdGNoT2JqZWN0KHthcmJpdHJhdGlvbl9iaXRyYXRlOjI1MDAwMCxkYXRhX2JpdHJhdGU6MjUwMDAwfSk7XHJcbiAgZXhwZWN0KHNhdmVkLmNhcGFiaWxpdGllcy5zaW11bGF0aW9uX3BhcmFtZXRlcl9hc3N1bXB0aW9ucy5jYW5fZmQucHJvdmVuYW5jZS5kYXRhX2JpdHJhdGUuaGFyZHdhcmVfZXZpZGVuY2UpLnRvQmUoZmFsc2UpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9lbmdpbmVlcmluZz9wcm9qZWN0PSR7cHJvamVjdH0mcmVzb3VyY2U9aGFyZHdhcmUtaW50ZXJmYWNlcyZvYmplY3Q9JHtwb3J0LmlkfSZlZGl0PTFgKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9iaXRyYXRlJykpLnRvSGF2ZVZhbHVlKCcyNTAwMDAnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9kYXRhX2JpdHJhdGUnKSkudG9IYXZlVmFsdWUoJzI1MDAwMCcpO1xyXG59KTtcclxuXHJcbnRlc3QoJ1BXTSBkZXZpY2UgZWRpdG9yIG9mZmVycyBubyByZXRpcmVkIHRyYW5zYWN0aW9uIHByb29mIGFuZCBwcmVzZXJ2ZXMgbmF0aXZlIGRyaXZlciBjb25maWd1cmF0aW9uIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7cGFnZX0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtcHdtLWVkaXRvci0nICsgcmFuZG9tVVVJRCgpO1xyXG4gIGNvbnN0IGhlYWRlcnMgPSB7J1gtUHJvamVjdC1JRCc6cHJvamVjdH07XHJcbiAgY29uc3Qgbm9kZVJlc3BvbnNlID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtbm9kZXMnLCB7aGVhZGVycyxcclxuICAgIGRhdGE6e25hbWU6J1BXTSBSZXZpZXcgQ29udHJvbGxlcicsZGV2aWNlX3R5cGU6J0VtYmVkZGVkQ29udHJvbGxlcicsZG9tYWluOidlbWJlZGRlZF9zeXN0ZW1zJ319KTtcclxuICBleHBlY3Qobm9kZVJlc3BvbnNlLm9rKCksYXdhaXQgbm9kZVJlc3BvbnNlLnRleHQoKSkudG9CZSh0cnVlKTtcclxuICBjb25zdCBub2RlID0gYXdhaXQgbm9kZVJlc3BvbnNlLmpzb24oKTtcclxuICBjb25zdCBwb3J0UmVzcG9uc2UgPSBhd2FpdCBwYWdlLnJlcXVlc3QucG9zdCgnL2FwaS9lbmdpbmVlcmluZy9oYXJkd2FyZS1pbnRlcmZhY2VzJywge2hlYWRlcnMsXHJcbiAgICBkYXRhOntuYW1lOidQV00gT3V0cHV0JyxoYXJkd2FyZV9ub2RlX2lkOm5vZGUuaWQsdGVjaG5vbG9neTonUFdNJyxjYXBhYmlsaXRpZXM6e1xyXG4gICAgICB0ZWNobm9sb2d5X3BhcmFtZXRlcnM6e3B3bV9wcm9maWxlOidMSU5VWF9TVEFURV82XzE4Jyxwd21fcGVyaW9kX25zOjIwMDAwMDAscHdtX2R1dHlfbnM6NzAwMDAwLFxyXG4gICAgICAgIHB3bV9wb2xhcml0eTonSU5WRVJTRUQnLHB3bV9lbmFibGVkOnRydWUscHdtX2RldmljZV9zb3VyY2U6J2lzb2xhdGVkLXZpcnR1YWwtUFdNLWRyaXZlcid9fX19KTtcclxuICBleHBlY3QocG9ydFJlc3BvbnNlLm9rKCksYXdhaXQgcG9ydFJlc3BvbnNlLnRleHQoKSkudG9CZSh0cnVlKTtcclxuICBjb25zdCBwb3J0ID0gYXdhaXQgcG9ydFJlc3BvbnNlLmpzb24oKTtcclxuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vZW5naW5lZXJpbmc/cHJvamVjdD0ke3Byb2plY3R9JnJlc291cmNlPWhhcmR3YXJlLWludGVyZmFjZXMmb2JqZWN0PSR7cG9ydC5pZH0mZWRpdD0xYCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI2VkaXRfdGVjaG5vbG9neScpKS50b0hhdmVWYWx1ZSgnUFdNJyk7XHJcbiAgLy8gV2FpdCBmb3IgdGhlIHNlbGVjdGVkIHByb2ZpbGUsIG5vdCBvbmx5IHRoZSBpbml0aWFsIGVkaXRvciBza2VsZXRvbi5cclxuICBjb25zdCBjYXRhbG9nID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvdGVjaG5vbG9naWVzJykpLmpzb24oKTtcclxuICBleHBlY3QoY2F0YWxvZy5kb21haW5zLmZsYXRNYXAoKGRvbWFpbjphbnkpPT5kb21haW4udGVjaG5vbG9naWVzKS5maW5kKChwcm9maWxlOmFueSk9PnByb2ZpbGUuaWQ9PT0ncHdtJykubG9jYWxfdGltaW5nX3NjaGVtYSkudG9FcXVhbChbXSk7XHJcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBbJ3B3bV9mcmVxdWVuY3lfaHonLCd1cGRhdGVfYm91bmRfbXMnLCdjYXB0dXJlX2JvdW5kX21zJ10pXHJcbiAgICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKGAjZWRpdF9sb2NhbF8ke2ZpZWxkfWApKS50b0hhdmVDb3VudCgwKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF9iaXRyYXRlJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNlZGl0X2RhdGFfYml0cmF0ZScpKS50b0hhdmVDb3VudCgwKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCdbbmFtZT1cImVkaXRfbG9jYWxfY29uZmlybWVkXCJdJykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignI2VkaXRfbmFtZScpLmZpbGwoJ1Jldmlld2VkIFBXTSBPdXRwdXQnKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonw4RuZGVydW5nZW4gc3BlaWNoZXJuJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjZWRpdF90ZWNobm9sb2d5JykpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGNvbnN0IHNhdmVkID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoYC9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtaW50ZXJmYWNlcy8ke3BvcnQuaWR9YCx7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgZXhwZWN0KHNhdmVkLm5hbWUpLnRvQmUoJ1Jldmlld2VkIFBXTSBPdXRwdXQnKTtcclxuICBleHBlY3Qoc2F2ZWQuY2FwYWJpbGl0aWVzKS50b0VxdWFsKHBvcnQuY2FwYWJpbGl0aWVzKTtcclxuICBleHBlY3Qoc2F2ZWQuY2FwYWJpbGl0aWVzLmxvY2FsX3RpbWluZ19ldmlkZW5jZSkudG9CZVVuZGVmaW5lZCgpO1xyXG4gIGV4cGVjdChzYXZlZC5iaXRyYXRlKS50b0JlTnVsbCgpO1xyXG4gIGV4cGVjdChzYXZlZC5kYXRhX2JpdHJhdGUpLnRvQmVOdWxsKCk7XHJcbn0pO1xyXG5cclxudGVzdCgnYWN0dWFsIHVpbnQ2NCBwcm90b2NvbCB2YWx1ZSBzdXJ2aXZlcyBsZWdhY3kgbnVtZXJpYyBKU09OLCBmb3JtIGVkaXQsIFNRTCBwZXJzaXN0ZW5jZSBhbmQgcmVsb2FkIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7cGFnZX0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0ID0gJ25pcy1lMmUtdWludDY0LScgKyByYW5kb21VVUlEKCk7XHJcbiAgY29uc3QgaGVhZGVycyA9IHsnWC1Qcm9qZWN0LUlEJzpwcm9qZWN0LCdDb250ZW50LVR5cGUnOidhcHBsaWNhdGlvbi9qc29uJ307XHJcbiAgY29uc3QgaW5pdGlhbCA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLHtoZWFkZXJzfSkpLmpzb24oKTtcclxuICBjb25zdCBtYXhpbXVtID0gJzE4NDQ2NzQ0MDczNzA5NTUxNjE1JztcclxuICBjb25zdCBzZWVkID0gSlNPTi5zdHJpbmdpZnkoe3BhcmFtZXRlcnM6e2luZHVzdHJ5OidjdXN0b20nLHRlY2hub2xvZ3k6J3NwYXJrcGx1Z19iJyxzcGJfYWxpYXM6J19fRVhBQ1RfSU5URUdFUl9fJyxcclxuICAgIHBhcmFtZXRlcl9wcm92ZW5hbmNlOntzcGJfYWxpYXM6e3ZhbHVlOidfX0VYQUNUX0lOVEVHRVJfXycsc291cmNlOidVU0VSX0NPTkZJUk1FRCcsc3RhdHVzOidDT05GSVJNRUQnfX19LGV4cGVjdGVkX3Rva2VuOmluaXRpYWwuZWRpdF90b2tlbn0pXHJcbiAgICAucmVwbGFjZUFsbCgnXCJfX0VYQUNUX0lOVEVHRVJfX1wiJywgbWF4aW11bSk7XHJcbiAgY29uc3Qgc2VlZGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBhdGNoKCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLHtoZWFkZXJzLGRhdGE6c2VlZH0pO1xyXG4gIGV4cGVjdChzZWVkZWQub2soKSxhd2FpdCBzZWVkZWQudGV4dCgpKS50b0JlKHRydWUpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke3Byb2plY3R9YCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3RlY2hub2xvZ3knKSkudG9IYXZlVmFsdWUoJ3NwYXJrcGx1Z19iJyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3NwYl9hbGlhcycpKS50b0hhdmVBdHRyaWJ1dGUoJ3R5cGUnLCd0ZXh0Jyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3NwYl9hbGlhcycpKS50b0hhdmVWYWx1ZShtYXhpbXVtKTtcclxuICBjb25zdCBjYXRhbG9nID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvdGVjaG5vbG9naWVzJykpLmpzb24oKTtcclxuICBjb25zdCBwcm9maWxlID0gY2F0YWxvZy5kb21haW5zLmZsYXRNYXAoKGQ6e3RlY2hub2xvZ2llczpBcnJheTx7aWQ6c3RyaW5nfT59KT0+ZC50ZWNobm9sb2dpZXMpLmZpbmQoKHA6e2lkOnN0cmluZ30pPT5wLmlkPT09J3NwYXJrcGx1Z19iJyk7XHJcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBwcm9maWxlLnBhcmFtZXRlcl9zY2hlbWEuZmlsdGVyKChmOntyZXF1aXJlZD86Ym9vbGVhbix0eXBlOnN0cmluZ30pPT5mLnJlcXVpcmVkJiZmLnR5cGU9PT0ndGV4dCcpKSB7XHJcbiAgICBhd2FpdCByZXZlYWxQYXJhbWV0ZXIocGFnZSxmaWVsZC5rZXkpO1xyXG4gICAgYXdhaXQgcGFnZS5sb2NhdG9yKGBbbmFtZT1cIiR7ZmllbGQua2V5fVwiXWApLmZpbGwoJ2lzb2xhdGVkLXRlc3Qtc291cmNlJyk7XHJcbiAgfVxyXG4gIGNvbnN0IGVkaXRlZCA9ICcxODQ0Njc0NDA3MzcwOTU1MTYxNCc7XHJcbiAgYXdhaXQgcmV2ZWFsUGFyYW1ldGVyKHBhZ2UsJ3NwYl9hbGlhcycpO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignI3NwYl9hbGlhcycpLmZpbGwoZWRpdGVkKTtcclxuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonUGFyYW1ldGVyIHNwZWljaGVybiDihpInLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5VGV4dCgnVGVjaG5vbG9naWUtIHVuZCBUaW1pbmctUGFyYW1ldGVyIGdlc3BlaWNoZXJ0LicpKS50b0JlVmlzaWJsZSgpO1xyXG4gIGNvbnN0IHNhdmVkID0gYXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycycse2hlYWRlcnN9KSkuanNvbigpO1xyXG4gIGV4cGVjdChzYXZlZC5wYXJhbWV0ZXJzLnRlY2hub2xvZ3lfcGFyYW1ldGVycy5zcGFya3BsdWdfYi52YWx1ZXMuc3BiX2FsaWFzKS50b0JlKGVkaXRlZCk7XHJcbiAgZXhwZWN0KHNhdmVkLnBhcmFtZXRlcnMudGVjaG5vbG9neV9wYXJhbWV0ZXJzLnNwYXJrcGx1Z19iLnByb3ZlbmFuY2Uuc3BiX2FsaWFzLnZhbHVlKS50b0JlKGVkaXRlZCk7XHJcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjc3BiX2FsaWFzJykpLnRvSGF2ZVZhbHVlKGVkaXRlZCk7XHJcbn0pO1xyXG5cclxuXHJcbnRlc3QoJ3Byb3Bvc2FsIHBhcmFtZXRlciBsaW5rIHNlbGVjdHMgaXRzIHRlY2hub2xvZ3kgYW5kIGxpdmUgZmluZGluZ3MgaGlnaGxpZ2h0IG9ubHkgYWZmZWN0ZWQgZmllbGRzIEB0ZWNobm9sb2d5LXJldmlldycsIGFzeW5jICh7cGFnZX0pID0+IHtcclxuICBjb25zdCBwcm9qZWN0PSduaXMtZTJlLWN1cnJlbnQtcGFyYW1ldGVyLXJldmlldy0nK3JhbmRvbVVVSUQoKTtcclxuICBjb25zdCBoZWFkZXJzPXsnWC1Qcm9qZWN0LUlEJzpwcm9qZWN0fTtcclxuICBjb25zdCBuZXR3b3Jrcz1be2lkOidjYW4tbG9jYWwnLG5hbWU6J0NBTiBMb2NhbCcsdGVjaG5vbG9neTonQ0FOX0ZEJ30se2lkOidsaW4tbG9jYWwnLG5hbWU6J0xJTiBMb2NhbCcsdGVjaG5vbG9neTonTElOJ31dO1xyXG4gIGNvbnN0IHNlZWQ9YXdhaXQgcGFnZS5yZXF1ZXN0LnBhdGNoKCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLHtoZWFkZXJzLGRhdGE6e3BhcmFtZXRlcnM6e2luZHVzdHJ5OidjdXN0b20nLHRlY2hub2xvZ3k6J2Nhbl9mZCcsZGVmYXVsdHNfc291cmNlOid0ZWNobm9sb2d5LXJlZ2lzdHJ5JyxuZXR3b3Jrcyxmb3JtYXRzOlsndW5pdmVyc2FsLWpzb25sJ119fX0pO1xyXG4gIGV4cGVjdChzZWVkLm9rKCksYXdhaXQgc2VlZC50ZXh0KCkpLnRvQmUodHJ1ZSk7XHJcbiAgYXN5bmMgZnVuY3Rpb24gY3JlYXRlKHJlc291cmNlOnN0cmluZyxkYXRhOlJlY29yZDxzdHJpbmcsdW5rbm93bj4pIHtcclxuICAgIGNvbnN0IHJlc3BvbnNlPWF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nLycrcmVzb3VyY2Use2hlYWRlcnMsZGF0YX0pO1xyXG4gICAgZXhwZWN0KHJlc3BvbnNlLm9rKCksYXdhaXQgcmVzcG9uc2UudGV4dCgpKS50b0JlKHRydWUpOyByZXR1cm4gcmVzcG9uc2UuanNvbigpO1xyXG4gIH1cclxuICBjb25zdCBub2RlPWF3YWl0IGNyZWF0ZSgnaGFyZHdhcmUtbm9kZXMnLHtuYW1lOidSZXZpZXcgRUNVJyxkZXZpY2VfdHlwZTonRW1iZWRkZWRDb250cm9sbGVyJ30pO1xyXG4gIGZvciAoY29uc3QgbmV0d29yayBvZiBuZXR3b3Jrcykge1xyXG4gICAgY29uc3QgcG9ydD1hd2FpdCBjcmVhdGUoJ2hhcmR3YXJlLWludGVyZmFjZXMnLHtuYW1lOm5ldHdvcmsubmFtZSxoYXJkd2FyZV9ub2RlX2lkOm5vZGUuaWQsdGVjaG5vbG9neTpuZXR3b3JrLnRlY2hub2xvZ3ksbmV0d29ya19yZWY6bmV0d29yay5pZCxiaXRyYXRlOm51bGwsZGF0YV9iaXRyYXRlOm51bGx9KTtcclxuICAgIGNvbnN0IGxvZ2ljYWw9YXdhaXQgY3JlYXRlKCdpbnRlcmZhY2VzJyx7bmFtZTpuZXR3b3JrLm5hbWUsaGFyZHdhcmVfbm9kZV9pZDpub2RlLmlkLGludGVyZmFjZV90eXBlOm5ldHdvcmsudGVjaG5vbG9neX0pO1xyXG4gICAgYXdhaXQgY3JlYXRlKCdtZXNzYWdlcycse25hbWU6bmV0d29yay5uYW1lKycgU3RhdHVzJyxpbnRlcmZhY2VfaWQ6bG9naWNhbC5pZCxoYXJkd2FyZV9pbnRlcmZhY2VfaWQ6cG9ydC5pZCxkbGM6MSxjeWNsZV9tczoxMDAsZGlyZWN0aW9uOid0eCd9KTtcclxuICB9XHJcbiAgY29uc3QgYmVmb3JlPWF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMvcmV2aWV3Jyx7aGVhZGVyc30pKS5qc29uKCk7XHJcbiAgZXhwZWN0KGJlZm9yZS5zb3VyY2UpLnRvQmUoJ0NVUlJFTlRfQ0FOT05JQ0FMX01PREVMJyk7XHJcbiAgZXhwZWN0KGJlZm9yZS5maW5kaW5ncy5maWx0ZXIoKGY6e3RlY2hub2xvZ3k6c3RyaW5nfSk9PmYudGVjaG5vbG9neT09PSdjYW5fZmQnKSkudG9IYXZlTGVuZ3RoKDEpO1xyXG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpbz9tb2RlPXBhcmFtZXRlcnMmcHJvamVjdD0ke3Byb2plY3R9JnRlY2hub2xvZ3k9bGluI3BhcmFtZXRlci1maW5kaW5nc2ApO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyN0ZWNobm9sb2d5JykpLnRvSGF2ZVZhbHVlKCdsaW4nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicse25hbWU6J0FrdHVlbGxlIFBhcmFtZXRlcmJlZnVuZGUnfSkpLnRvQ29udGFpblRleHQoJzEgZsO8ciBMSU4nKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjcGFyYW1ldGVyLWZpZWxkLWxpbl9iaXRyYXRlX2JwcycpKS50b0hhdmVDbGFzcygvcGFyYW1ldGVyLWZpZWxkLWZpbmRpbmcvKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjcGFyYW1ldGVyLWZpZWxkLWxpbl9kZXZpY2Vfc291cmNlJykpLnRvSGF2ZUNsYXNzKC9wYXJhbWV0ZXItZmllbGQtZmluZGluZy8pO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCduYXZpZ2F0aW9uJyx7bmFtZTonVGVjaG5vbG9naWVuIG1pdCBQYXJhbWV0ZXJiZWZ1bmRlbid9KS5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6L0NBTi1GRC99KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyN0ZWNobm9sb2d5JykpLnRvSGF2ZVZhbHVlKCdjYW5fZmQnKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjcGFyYW1ldGVyLWZpZWxkLWFyYml0cmF0aW9uX2JpdHJhdGUnKSkudG9IYXZlQ2xhc3MoL3BhcmFtZXRlci1maWVsZC1maW5kaW5nLyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3BhcmFtZXRlci1maWVsZC1kYXRhX2JpdHJhdGUnKSkudG9IYXZlQ2xhc3MoL3BhcmFtZXRlci1maWVsZC1maW5kaW5nLyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3BhcmFtZXRlci1maWVsZC1jYW5fY2xvY2tfaHonKSkubm90LnRvSGF2ZUNsYXNzKC9wYXJhbWV0ZXItZmllbGQtZmluZGluZy8pO1xyXG4gIGNvbnN0IGNvbmZpcm09cGFnZS5nZXRCeVJvbGUoJ2Zvcm0nLHtuYW1lOidDQU4tRkQtTmV0emUgYmVzdMOkdGlnZW4nfSk7XHJcbiAgYXdhaXQgcmV2ZWFsUGFyYW1ldGVyKHBhZ2UsJ2Nhbl9jbG9ja19oeicpO1xyXG4gIGF3YWl0IHBhZ2UubG9jYXRvcignW25hbWU9XCJjYW5fY2xvY2tfaHpcIl0nKS5maWxsKCc4MDAwMDAwMCcpO1xyXG4gIGF3YWl0IGV4cGVjdChjb25maXJtLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonRsO8ciAxIE5ldHplIGJlc3TDpHRpZ2VuICYgZXJuZXV0IHByw7xmZW4nLGV4YWN0OnRydWV9KSkudG9CZURpc2FibGVkKCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLHtuYW1lOidBa3R1ZWxsZSBQYXJhbWV0ZXJiZWZ1bmRlJ30pKS50b0NvbnRhaW5UZXh0KCdTcGVpY2hlcmUgenVlcnN0IGRpZSDDhG5kZXJ1bmdlbicpO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidQYXJhbWV0ZXIgc3BlaWNoZXJuIOKGkicsZXhhY3Q6dHJ1ZX0pLmNsaWNrKCk7XHJcbiAgYXdhaXQgZXhwZWN0KGNvbmZpcm0uZ2V0QnlSb2xlKCdidXR0b24nLHtuYW1lOidGw7xyIDEgTmV0emUgYmVzdMOkdGlnZW4gJiBlcm5ldXQgcHLDvGZlbicsZXhhY3Q6dHJ1ZX0pKS50b0JlRW5hYmxlZCgpO1xyXG4gIGF3YWl0IGNvbmZpcm0uZ2V0QnlSb2xlKCdzcGluYnV0dG9uJyx7bmFtZTovTm9taW5hbCBCaXRyYXRlL30pLmZpbGwoJzUwMDAwMCcpO1xyXG4gIGF3YWl0IGNvbmZpcm0uZ2V0QnlSb2xlKCdzcGluYnV0dG9uJyx7bmFtZTovRGF0YSBCaXRyYXRlL30pLmZpbGwoJzIwMDAwMDAnKTtcclxuICBhd2FpdCBjb25maXJtLmdldEJ5Um9sZSgnYnV0dG9uJyx7bmFtZTonRsO8ciAxIE5ldHplIGJlc3TDpHRpZ2VuICYgZXJuZXV0IHByw7xmZW4nLGV4YWN0OnRydWV9KS5jbGljaygpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgncmVnaW9uJyx7bmFtZTonQWt0dWVsbGUgUGFyYW1ldGVyYmVmdW5kZSd9KSkudG9Db250YWluVGV4dCgnMCBmw7xyIENBTi1GRCcpO1xyXG4gIGF3YWl0IGV4cGVjdChwYWdlLmxvY2F0b3IoJyNwYXJhbWV0ZXItZmllbGQtYXJiaXRyYXRpb25fYml0cmF0ZScpKS5ub3QudG9IYXZlQ2xhc3MoL3BhcmFtZXRlci1maWVsZC1maW5kaW5nLyk7XHJcbiAgY29uc3QgYWZ0ZXI9YXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycy9yZXZpZXcnLHtoZWFkZXJzfSkpLmpzb24oKTtcclxuICBleHBlY3QoYWZ0ZXIuZmluZGluZ3Muc29tZSgoZjp7dGVjaG5vbG9neTpzdHJpbmd9KT0+Zi50ZWNobm9sb2d5PT09J2Nhbl9mZCcpKS50b0JlKGZhbHNlKTtcclxuICBleHBlY3QoYWZ0ZXIuZmluZGluZ3Muc29tZSgoZjp7dGVjaG5vbG9neTpzdHJpbmd9KT0+Zi50ZWNobm9sb2d5PT09J2xpbicpKS50b0JlKHRydWUpO1xyXG4gIGNvbnN0IHNhdmVkPWF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93L3BhcmFtZXRlcnMnLHtoZWFkZXJzfSkpLmpzb24oKTtcclxuICBleHBlY3Qoc2F2ZWQucGFyYW1ldGVycy5uZXR3b3Jrcy5maW5kKChuOntpZDpzdHJpbmd9KT0+bi5pZD09PSdsaW4tbG9jYWwnKSkudG9FcXVhbChuZXR3b3Jrc1sxXSk7XHJcbiAgZXhwZWN0KHNhdmVkLnBhcmFtZXRlcnMuc2ltdWxhdGlvbl9wYXJhbWV0ZXJfYXNzdW1wdGlvbnMuY2FuX2ZkLnZhbHVlcy5jYW5fY2xvY2tfaHopLnRvQmUoODAwMDAwMDApO1xyXG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCduYXZpZ2F0aW9uJyx7bmFtZTonVGVjaG5vbG9naWVuIG1pdCBQYXJhbWV0ZXJiZWZ1bmRlbid9KS5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6L0xJTi99KS5jbGljaygpO1xyXG4gIGNvbnN0IGxpbkNvbmZpcm09cGFnZS5nZXRCeVJvbGUoJ2Zvcm0nLHtuYW1lOidMSU4tTmV0emUgYmVzdMOkdGlnZW4nfSk7XHJcbiAgYXdhaXQgbGluQ29uZmlybS5nZXRCeVJvbGUoJ3NwaW5idXR0b24nLHtuYW1lOi9iaXQuKnJhdGUvaX0pLmZpbGwoJzE5MjAwJyk7XHJcbiAgYXdhaXQgbGluQ29uZmlybS5nZXRCeVJvbGUoJ2J1dHRvbicse25hbWU6J0bDvHIgMSBOZXR6ZSBiZXN0w6R0aWdlbiAmIGVybmV1dCBwcsO8ZmVuJyxleGFjdDp0cnVlfSkuY2xpY2soKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5sb2NhdG9yKCcjcGFyYW1ldGVyLWZpZWxkLWxpbl9iaXRyYXRlX2JwcycpKS5ub3QudG9IYXZlQ2xhc3MoL3BhcmFtZXRlci1maWVsZC1maW5kaW5nLyk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UubG9jYXRvcignI3BhcmFtZXRlci1maWVsZC1saW5fZGV2aWNlX3NvdXJjZScpKS50b0hhdmVDbGFzcygvcGFyYW1ldGVyLWZpZWxkLWZpbmRpbmcvKTtcclxuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicse25hbWU6J0FrdHVlbGxlIFBhcmFtZXRlcmJlZnVuZGUnfSkpLnRvQ29udGFpblRleHQoJzEgZsO8ciBMSU4nKTtcclxuICBhd2FpdCBleHBlY3QobGluQ29uZmlybSkudG9IYXZlQ291bnQoMCk7XHJcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KCdEaWUgUmF0ZSBmZWhsdCBhbHMgYmVzdMOkdGlndGVyIFByb2pla3R3ZXJ0Licse2V4YWN0OmZhbHNlfSkpLnRvSGF2ZUNvdW50KDApO1xyXG4gIGNvbnN0IGZvcmVpZ249YXdhaXQgKGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3cvcGFyYW1ldGVycy9yZXZpZXcnLHtoZWFkZXJzOnsnWC1Qcm9qZWN0LUlEJzonbmlzLWUyZS1vdGhlci0nK3JhbmRvbVVVSUQoKX19KSkuanNvbigpO1xyXG4gIGV4cGVjdChmb3JlaWduLmZpbmRpbmdzKS50b0VxdWFsKFtdKTtcclxufSk7XHJcbiJdLCJtYXBwaW5ncyI6IkFBQUEsU0FBU0EsSUFBSSxFQUFFQyxNQUFNLFFBQVEsaUJBQWlCO0FBQzlDLFNBQVNDLFVBQVUsUUFBUSxhQUFhO0FBR3hDLGVBQWVDLGVBQWVBLENBQUNDLElBQVMsRUFBRUMsR0FBVSxFQUFFO0VBQ3BELE1BQU1DLEtBQUssR0FBR0YsSUFBSSxDQUFDRyxPQUFPLENBQUMsb0JBQW9CRixHQUFHLEVBQUUsQ0FBQyxDQUFDRSxPQUFPLENBQUMsNEJBQTRCLENBQUM7RUFDM0YsSUFBSSxPQUFNRCxLQUFLLENBQUNFLEtBQUssQ0FBQyxDQUFDLEtBQUksT0FBTUYsS0FBSyxDQUFDRyxZQUFZLENBQUMsTUFBTSxDQUFDLE1BQUssSUFBSSxFQUFFLE1BQU1ILEtBQUssQ0FBQ0MsT0FBTyxDQUFDLGtCQUFrQixDQUFDLENBQUNHLEtBQUssQ0FBQyxDQUFDO0FBQ3ZIO0FBRUEsS0FBSyxNQUFNQyxRQUFRLElBQUksQ0FDckI7RUFBQ0MsVUFBVSxFQUFDLEtBQUs7RUFBQ0MsRUFBRSxFQUFDLEtBQUs7RUFBQ0MsSUFBSSxFQUFDLE9BQU87RUFBQ1QsR0FBRyxFQUFDO0FBQWlCLENBQUMsRUFDOUQ7RUFBQ08sVUFBVSxFQUFDLFFBQVE7RUFBQ0MsRUFBRSxFQUFDLFFBQVE7RUFBQ0MsSUFBSSxFQUFDLFFBQVE7RUFBQ1QsR0FBRyxFQUFDLHFCQUFxQjtFQUFDVSxJQUFJLEVBQUM7QUFBUyxDQUFDLEVBQ3hGO0VBQUNILFVBQVUsRUFBQyxVQUFVO0VBQUNDLEVBQUUsRUFBQyxVQUFVO0VBQUNDLElBQUksRUFBQyxZQUFZO0VBQUNULEdBQUcsRUFBQztBQUFTLENBQUMsQ0FDdEUsRUFBRUwsSUFBSSxDQUFDLFVBQVVXLFFBQVEsQ0FBQ0MsVUFBVSw2RkFBNkYsRUFBRSxPQUFPO0VB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