// c50acddf796d4b47fe758b0ffc84b110938c7018
import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
test('native wizard preserves its complete source while adopting an edited shared draft @project-draft', async ({
  page
}) => {
  var _persisted$context, _persisted$data;
  const project = 'nis-e2e-shared-native-' + randomUUID();
  const run = randomUUID();
  const graph = [{
    cluster_id: 'drive',
    label: 'Regelung',
    network_id: 'can_fd',
    network_label: 'CAN-FD',
    bus_name: 'Regelung',
    controllers: [{
      ecu: 'Motorsteuerung',
      sensors: [],
      actuators: []
    }, {
      ecu: 'Anzeige',
      sensors: [],
      actuators: []
    }]
  }];
  const prompt = `Strukturierte Vorgaben fuer den Engineering-Agenten:
- Lauf-ID: ${run}
- Industrie: Automotive
- Netzwerktechnologien: CAN-FD (can_fd)
- Hardware-Sollwerte: {"gateways":1,"ecus":2,"sensors":0,"actuators":0}
- Systemcluster-Graph: ${JSON.stringify(graph)}
Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:
Erzeuge Motorsteuerung und Anzeige mit einem Gateway System.`;
  const started = await page.request.post('/api/engineering/agent/chat', {
    headers: {
      'X-Project-ID': project
    },
    timeout: 120000,
    data: {
      prompt,
      wizard_command: {
        action: 'START',
        run_id: run,
        operation_id: randomUUID(),
        target: 'engineering_model',
        wizard_context: {
          project_id: project,
          run_id: run,
          project_name: 'Gemeinsamer nativer Auftrag',
          scope_ids: ['engineering_model'],
          mode: 'full',
          process_ids: ['defaults', 'review_gate'],
          task: 'Motorsteuerung und Anzeige an System'
        }
      }
    }
  });
  expect(started.ok(), await started.text()).toBe(true);
  const initial = await (await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': project
    }
  })).json();
  expect(initial.data.source_format).toBe('WIZARD_V2');
  expect(initial.data.structured_source.prompt).toBe(prompt);
  await page.goto(`/studio/engineering?assistant=project&project=${project}`);
  const dialog = page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  });
  await dialog.getByRole('button', {
    name: 'Ergänzen',
    exact: true
  }).click();
  await dialog.getByText('Gemeinsamen Projektentwurf bearbeiten', {
    exact: true
  }).click();
  const editor = dialog.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor.getByRole('textbox', {
    name: 'Projektbeschreibung',
    exact: true
  })).toHaveValue(prompt);
  await editor.getByRole('textbox', {
    name: 'Anforderung ergänzen',
    exact: true
  }).fill('Die Modellbeschreibung soll den lokalen Regelungszweck dokumentieren.');
  await editor.getByRole('button', {
    name: 'Ergänzung speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await dialog.getByRole('button', {
    name: 'Gespeicherten Entwurf im Auftrag übernehmen',
    exact: true
  }).click();
  await expect(editor).not.toBeVisible({
    timeout: 120000
  });
  const persisted = await (await page.request.get('/api/engineering/workflow', {
    headers: {
      'X-Project-ID': project
    }
  })).json();
  const state = (_persisted$context = persisted.context) !== null && _persisted$context !== void 0 ? _persisted$context : (_persisted$data = persisted.data) === null || _persisted$data === void 0 ? void 0 : _persisted$data.context;
  expect(state.agent_wizard_status.run_id).toBe(run);
  expect(state.agent_wizard_status.engineering_draft_ref).toEqual({
    draft_id: initial.data.draft_id,
    revision: 2
  });
  expect(state.wizard_request.prompt).toContain(JSON.stringify(graph));
  await page.reload();
  await expect(page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  })).toBeVisible();
});
test('conflicting edits retain input and load the current revision without overwriting it @project-draft', async ({
  page
}) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill('Erstelle ein Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText('Revision 1');
  await editor.getByRole('textbox', {
    name: 'Name',
    exact: true
  }).first().fill('MeineRegelung');
  const session = await (await page.request.get('/api/engineering/agent/review-session')).json();
  const remote = await page.request.post('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': project,
      'X-Human-Review': 'confirmed',
      'X-Review-CSRF': session.csrf_token
    },
    data: {
      action: 'RESOLVE',
      operation_id: randomUUID(),
      revision: 1,
      industry: 'building_automation'
    }
  });
  expect(remote.ok()).toBe(true);
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('region', {
    name: 'Entwurfskonflikt'
  })).toContainText('Revision 2');
  await expect(editor.getByRole('textbox', {
    name: 'Name',
    exact: true
  }).first()).toHaveValue('MeineRegelung');
  await editor.getByRole('button', {
    name: 'Aktuellen Stand laden und Eingabekopie behalten',
    exact: true
  }).click();
  await expect(editor.getByRole('textbox', {
    name: 'Einsatzbereich',
    exact: true
  })).toHaveValue('building_automation');
  await expect(editor.getByRole('textbox', {
    name: 'Name',
    exact: true
  }).first()).toHaveValue('RaspberryPi');
  await expect(editor.getByRole('textbox', {
    name: 'Erhaltene Eingaben vor dem Konflikt',
    exact: true
  })).toHaveValue(/MeineRegelung/);
  await editor.getByRole('textbox', {
    name: 'Name',
    exact: true
  }).first().fill('MeineRegelung');
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 3 gespeichert');
});
test('draft recovers a lost save response and survives application restart @project-draft', async ({
  page
}) => {
  const container = process.env.NIS_E2E_APP_CONTAINER;
  expect(container).toMatch(/^nis-e2e-app-[a-f0-9]+$/);
  const docker = process.env.NIS_TEST_DOCKER || 'docker';
  expect(execFileSync(docker, ['inspect', container, '--format', '{{index .Config.Labels "networkis.test"}}'], {
    encoding: 'utf8'
  }).trim()).toBe('disposable');
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill('Erstelle ein Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText('4 Geräte');
  await editor.getByRole('textbox', {
    name: 'Anschlusstechnologie',
    exact: true
  }).first().fill('ethernet');
  let dropped = false;
  await page.route('**/api/engineering/agent/project-draft', async route => {
    if (route.request().method() !== 'POST' || dropped) return route.continue();
    // Execute the real server write, but lose its transport response.
    const response = await route.fetch();
    expect(response.ok()).toBe(true);
    dropped = true;
    await route.abort('connectionreset');
  });
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('alert')).toBeVisible();
  await expect(editor.getByRole('textbox', {
    name: 'Anschlusstechnologie',
    exact: true
  }).first()).toHaveValue('ethernet');
  const read = async () => (await (await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': project
    }
  })).json()).data;
  const accepted = await read();
  expect(accepted.revision).toBe(2);
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  expect(await read()).toEqual(accepted);
  execFileSync(docker, ['restart', container], {
    timeout: 60000
  });
  await expect.poll(async () => {
    try {
      return (await page.request.get('/api/ready', {
        timeout: 2000
      })).ok();
    } catch {
      return false;
    }
  }, {
    timeout: 120000
  }).toBe(true);
  await page.reload();
  await expect(editor).toContainText('Revision 2');
  expect(await read()).toEqual(accepted);
});
test('removing a draft device survives save, amendment and reload @project-draft', async ({
  page
}) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill('Erstelle ein Projekt mit einem Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText('4 Geräte');
  await editor.getByRole('group', {
    name: 'Temperatursensor3 · SENSOR',
    exact: true
  }).getByRole('button', {
    name: 'Aus Entwurf entfernen',
    exact: true
  }).click();
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await editor.getByRole('textbox', {
    name: 'Anforderung ergänzen',
    exact: true
  }).fill('Zusätzlich zwei Drucksensoren.');
  await editor.getByRole('button', {
    name: 'Ergänzung speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 3 gespeichert');
  await page.reload();
  await expect(editor).toContainText('5 Geräte');
  await expect(editor.getByRole('group', {
    name: 'Temperatursensor3 · SENSOR',
    exact: true
  })).toHaveCount(0);
  await expect(editor.getByRole('group', {
    name: 'Drucksensor2 · SENSOR',
    exact: true
  })).toBeVisible();
});
for (const mode of ['chat', 'wizard']) test(`missing controller can be added in ${mode} and the requirement remains editable @project-draft`, async ({
  page
}) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  const input = page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  });
  await input.fill('Ein neues Projekt mit drei Sensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  let editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  }).last();
  await expect(editor).toContainText('3 Geräte');
  await editor.getByText('Offene Angaben', {
    exact: false
  }).click();
  await expect(editor).toContainText('Controller ergänzen');
  if (mode === 'wizard') {
    await page.getByRole('button', {
      name: /Im Wizard bearbeiten/
    }).click();
    await expect(page.getByRole('dialog', {
      name: 'Engineering-Auftrag erstellen'
    })).toBeVisible();
    editor = page.getByRole('region', {
      name: 'Gespeicherter Projektentwurf'
    }).last();
    await expect(page.getByRole('button', {
      name: 'Auftrag starten',
      exact: true
    })).toBeDisabled();
    await editor.getByRole('textbox', {
      name: 'Anforderung ergänzen',
      exact: true
    }).fill('Ergänze einen Raspberry Pi.');
    await editor.getByRole('button', {
      name: 'Ergänzung speichern',
      exact: true
    }).click();
  } else {
    await input.fill('Ergänze einen Raspberry Pi.');
    await page.locator('.eng-agent-composer').getByRole('button', {
      name: 'Senden',
      exact: true
    }).click();
  }
  await expect(editor).toContainText('4 Geräte');
  await page.reload();
  editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  }).last();
  await expect(editor).toContainText('Revision 2');
  const owners = editor.getByRole('combobox', {
    name: 'Verarbeitender Controller',
    exact: true
  });
  await expect(owners).toHaveCount(3);
  for (const field of await owners.all()) await field.selectOption({
    label: 'RaspberryPi'
  });
  const tasks = editor.getByRole('textbox', {
    name: 'Messgröße oder Geräteaufgabe',
    exact: true
  });
  await expect(tasks).toHaveCount(4);
  for (let index = 1; index < 4; index++) await tasks.nth(index).fill('Temperatur messen');
  for (const field of await editor.getByRole('textbox', {
    name: 'Anschlusstechnologie',
    exact: true
  }).all()) await field.fill('ethernet');
  await editor.getByRole('combobox', {
    name: 'Technische Parameter',
    exact: true
  }).selectOption('defaults');
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 3 gespeichert');
  const response = await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': project
    }
  });
  const draft = (await response.json()).data;
  expect(draft.devices.map(device => device.name).sort()).toEqual(['RaspberryPi', 'Sensor1', 'Sensor2', 'Sensor3']);
  expect(draft.issues).toEqual([]);
  expect(draft.original_requirement).toBe('Ein neues Projekt mit drei Sensoren.');
  await expect(page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  })).toHaveCount(mode === 'wizard' ? 1 : 0);
});
for (const valveCount of [2, 5]) test(`chat creates and applies the real model with ${valveCount} valves without opening the wizard @project-draft`, async ({
  page
}) => {
  var _ref, _payload$items;
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill(`Ich möchte ein kleines Projekt mit einem Raspberry-Pi, drei Temperatursensoren und ${valveCount} Ventilen.`);
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText(`${4 + valveCount} Geräte`);
  await expect(page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  })).toHaveCount(0);
  const technologies = editor.getByRole('textbox', {
    name: 'Anschlusstechnologie',
    exact: true
  });
  const owners = editor.getByRole('combobox', {
    name: 'Verarbeitender Controller',
    exact: true
  });
  const commands = editor.getByRole('combobox', {
    name: 'Ventilbefehl',
    exact: true
  });
  await expect(technologies).toHaveCount(4 + valveCount);
  await expect(owners).toHaveCount(3 + valveCount);
  await expect(commands).toHaveCount(valveCount);
  for (const field of await technologies.all()) await field.fill('ethernet');
  for (const field of await owners.all()) await field.selectOption({
    label: 'RaspberryPi'
  });
  for (const field of await commands.all()) await field.selectOption('OPEN_CLOSE');
  await editor.getByRole('combobox', {
    name: 'Technische Parameter',
    exact: true
  }).selectOption('defaults');
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await page.reload();
  await expect(editor).toContainText('Revision 2');
  await expect(editor.getByLabel('Anschlusstechnologie', {
    exact: true
  }).first()).toHaveValue('ethernet');
  await editor.getByRole('button', {
    name: 'Modellvorschlag erstellen',
    exact: true
  }).click();
  await page.getByRole('button', {
    name: 'Vorschlag freigeben',
    exact: true
  }).click();
  await page.getByRole('button', {
    name: 'Ins Modell übernehmen',
    exact: true
  }).click();
  await expect(page.getByText(/Modellobjekte bestätigt/)).toBeVisible();
  await expect(page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  })).toHaveCount(0);
  const response = await page.request.get('/api/engineering/hardware-nodes', {
    headers: {
      'X-Project-ID': project
    }
  });
  expect(response.ok()).toBe(true);
  const payload = await response.json();
  const nodes = Array.isArray(payload) ? payload : (_ref = (_payload$items = payload.items) !== null && _payload$items !== void 0 ? _payload$items : payload.data) !== null && _ref !== void 0 ? _ref : [];
  expect(nodes.map(node => node.name).sort()).toEqual(['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', ...Array.from({
    length: valveCount
  }, (_, index) => `Ventilaktor${index + 1}`)].sort());
  const controller = nodes.find(node => node.name === 'RaspberryPi');
  for (const node of nodes.filter(node => node.id !== controller.id)) expect(node.identity.system_owner_id).toBe(controller.id);
  await page.reload();
  await expect(page.getByText(/Modellobjekte bestätigt/)).toBeVisible();
});
test('new project is created from the saved draft without moving the original project @project-draft', async ({
  page
}) => {
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const origin = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill('Ein neues Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText('4 Geräte');
  const before = await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': origin
    }
  });
  const originalDraft = (await before.json()).data;
  await editor.getByText('Als neues Projekt verwenden', {
    exact: true
  }).click();
  await editor.getByRole('textbox', {
    name: 'Neuer Projektname',
    exact: true
  }).fill('Temperaturregelung');
  await editor.getByRole('button', {
    name: 'Neues Projekt anlegen und öffnen',
    exact: true
  }).click();
  await expect(page).toHaveURL(/\/studio\/agent\?draft=.+&project=.+/);
  const target = new URL(page.url()).searchParams.get('project');
  expect(target.replace('network-project-', '')).not.toBe(compact);
  await expect(editor).toContainText('4 Geräte');
  await page.reload();
  await expect(editor).toContainText('4 Geräte');
  const after = await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': origin
    }
  });
  expect((await after.json()).data).toEqual(originalDraft);
  const targetResponse = await page.request.get('/api/engineering/agent/project-draft', {
    headers: {
      'X-Project-ID': target.startsWith('network-project-') ? target : 'network-project-' + target
    }
  });
  const targetDraft = (await targetResponse.json()).data;
  expect(targetDraft.draft_id).not.toBe(originalDraft.draft_id);
  expect(targetDraft.devices).toEqual(originalDraft.devices);
});
test('the wizard executes the same saved draft through the real review workflow @project-draft', async ({
  page
}) => {
  var _oldWorkflow$data$con, _oldWorkflow$data, _newWorkflow$data$con, _newWorkflow$data;
  const compact = '20260915000000000-' + randomUUID().replaceAll('-', '').slice(0, 8);
  const project = 'network-project-' + compact;
  await page.goto(`/studio/agent?project=${compact}`);
  await page.getByRole('textbox', {
    name: 'Nachricht an den Engineering-Assistenten'
  }).fill('Ein neues Projekt mit Raspberry Pi und drei Temperatursensoren.');
  await page.locator('.eng-agent-composer').getByRole('button', {
    name: 'Senden',
    exact: true
  }).click();
  const editor = page.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await expect(editor).toContainText('4 Geräte');
  for (const field of await editor.getByRole('textbox', {
    name: 'Anschlusstechnologie',
    exact: true
  }).all()) await field.fill('ethernet');
  for (const field of await editor.getByRole('combobox', {
    name: 'Verarbeitender Controller',
    exact: true
  }).all()) await field.selectOption({
    label: 'RaspberryPi'
  });
  await editor.getByRole('combobox', {
    name: 'Technische Parameter',
    exact: true
  }).selectOption('defaults');
  await editor.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(editor.getByRole('status')).toContainText('Revision 2 gespeichert');
  await page.getByRole('button', {
    name: /Im Wizard bearbeiten/
  }).click();
  const dialog = page.getByRole('dialog', {
    name: 'Engineering-Auftrag erstellen'
  });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  })).toContainText('Revision 2');
  await dialog.getByRole('textbox', {
    name: 'Projektname',
    exact: true
  }).fill('Gemeinsamer Entwurf');
  const scopes = dialog.getByRole('group', {
    name: 'Workflowumfang',
    exact: true
  }).getByRole('checkbox');
  await expect(scopes).toHaveCount(9);
  for (let index = 1; index < 9; index++) await scopes.nth(index).uncheck();
  await dialog.getByRole('button', {
    name: 'Auftrag starten',
    exact: true
  }).click();
  await dialog.getByRole('button', {
    name: 'Freigeben, übernehmen & fortfahren',
    exact: true
  }).click();
  await expect.poll(async () => {
    var _ref2, _payload$items2;
    const response = await page.request.get('/api/engineering/hardware-nodes', {
      headers: {
        'X-Project-ID': project
      }
    });
    expect(response.ok()).toBe(true);
    const payload = await response.json();
    const nodes = Array.isArray(payload) ? payload : (_ref2 = (_payload$items2 = payload.items) !== null && _payload$items2 !== void 0 ? _payload$items2 : payload.data) !== null && _ref2 !== void 0 ? _ref2 : [];
    return nodes.map(node => node.name).sort();
  }).toEqual(['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3'].sort());
  await dialog.getByRole('button', {
    name: 'Ergänzen',
    exact: true
  }).click();
  const supplement = dialog.getByRole('region', {
    name: 'Engineering-Auftrag ergänzen'
  });
  const revised = supplement.getByRole('region', {
    name: 'Gespeicherter Projektentwurf'
  });
  await revised.getByRole('textbox', {
    name: 'Anforderung ergänzen',
    exact: true
  }).fill('Vier Temperatursensoren statt drei.');
  await revised.getByRole('button', {
    name: 'Ergänzung speichern',
    exact: true
  }).click();
  await expect(revised).toContainText('Revision 3');
  await expect(revised).toContainText('5 Geräte');
  const fourth = revised.getByRole('group', {
    name: 'Temperatursensor4 · SENSOR',
    exact: true
  });
  await fourth.getByRole('textbox', {
    name: 'Anschlusstechnologie',
    exact: true
  }).fill('ethernet');
  await fourth.getByRole('combobox', {
    name: 'Verarbeitender Controller',
    exact: true
  }).selectOption({
    label: 'RaspberryPi'
  });
  await revised.getByRole('button', {
    name: 'Angaben speichern',
    exact: true
  }).click();
  await expect(revised.getByRole('status')).toContainText('Revision 4 gespeichert');
  const before = await page.request.get('/api/engineering/workflow?summary=1', {
    headers: {
      'X-Project-ID': project
    }
  });
  const oldWorkflow = await before.json();
  await supplement.getByRole('button', {
    name: 'Gespeicherten Entwurf im Auftrag übernehmen',
    exact: true
  }).click();
  await dialog.getByRole('button', {
    name: 'Freigeben, übernehmen & fortfahren',
    exact: true
  }).click();
  await expect.poll(async () => {
    var _ref3, _payload$items3;
    const response = await page.request.get('/api/engineering/hardware-nodes', {
      headers: {
        'X-Project-ID': project
      }
    });
    const payload = await response.json();
    const nodes = Array.isArray(payload) ? payload : (_ref3 = (_payload$items3 = payload.items) !== null && _payload$items3 !== void 0 ? _payload$items3 : payload.data) !== null && _ref3 !== void 0 ? _ref3 : [];
    return nodes.map(node => node.name).sort();
  }).toEqual(['RaspberryPi', 'Temperatursensor1', 'Temperatursensor2', 'Temperatursensor3', 'Temperatursensor4'].sort());
  const after = await page.request.get('/api/engineering/workflow?summary=1', {
    headers: {
      'X-Project-ID': project
    }
  });
  const newWorkflow = await after.json();
  const oldContext = (_oldWorkflow$data$con = (_oldWorkflow$data = oldWorkflow.data) === null || _oldWorkflow$data === void 0 ? void 0 : _oldWorkflow$data.context) !== null && _oldWorkflow$data$con !== void 0 ? _oldWorkflow$data$con : oldWorkflow.context;
  const newContext = (_newWorkflow$data$con = (_newWorkflow$data = newWorkflow.data) === null || _newWorkflow$data === void 0 ? void 0 : _newWorkflow$data.context) !== null && _newWorkflow$data$con !== void 0 ? _newWorkflow$data$con : newWorkflow.context;
  expect(newContext.wizard_request.run_id).toBe(oldContext.wizard_request.run_id);
  expect(newContext.wizard_request.revision).not.toBe(oldContext.wizard_request.revision);
  expect(newContext.agent_wizard_status.engineering_draft_ref.revision).toBe(4);
});
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJuYW1lcyI6WyJ0ZXN0IiwiZXhwZWN0IiwicmFuZG9tVVVJRCIsImV4ZWNGaWxlU3luYyIsInBhZ2UiLCJfcGVyc2lzdGVkJGNvbnRleHQiLCJfcGVyc2lzdGVkJGRhdGEiLCJwcm9qZWN0IiwicnVuIiwiZ3JhcGgiLCJjbHVzdGVyX2lkIiwibGFiZWwiLCJuZXR3b3JrX2lkIiwibmV0d29ya19sYWJlbCIsImJ1c19uYW1lIiwiY29udHJvbGxlcnMiLCJlY3UiLCJzZW5zb3JzIiwiYWN0dWF0b3JzIiwicHJvbXB0IiwiSlNPTiIsInN0cmluZ2lmeSIsInN0YXJ0ZWQiLCJyZXF1ZXN0IiwicG9zdCIsImhlYWRlcnMiLCJ0aW1lb3V0IiwiZGF0YSIsIndpemFyZF9jb21tYW5kIiwiYWN0aW9uIiwicnVuX2lkIiwib3BlcmF0aW9uX2lkIiwidGFyZ2V0Iiwid2l6YXJkX2NvbnRleHQiLCJwcm9qZWN0X2lkIiwicHJvamVjdF9uYW1lIiwic2NvcGVfaWRzIiwibW9kZSIsInByb2Nlc3NfaWRzIiwidGFzayIsIm9rIiwidGV4dCIsInRvQmUiLCJpbml0aWFsIiwiZ2V0IiwianNvbiIsInNvdXJjZV9mb3JtYXQiLCJzdHJ1Y3R1cmVkX3NvdXJjZSIsImdvdG8iLCJkaWFsb2ciLCJnZXRCeVJvbGUiLCJuYW1lIiwiZXhhY3QiLCJjbGljayIsImdldEJ5VGV4dCIsImVkaXRvciIsInRvSGF2ZVZhbHVlIiwiZmlsbCIsInRvQ29udGFpblRleHQiLCJub3QiLCJ0b0JlVmlzaWJsZSIsInBlcnNpc3RlZCIsInN0YXRlIiwiY29udGV4dCIsImFnZW50X3dpemFyZF9zdGF0dXMiLCJlbmdpbmVlcmluZ19kcmFmdF9yZWYiLCJ0b0VxdWFsIiwiZHJhZnRfaWQiLCJyZXZpc2lvbiIsIndpemFyZF9yZXF1ZXN0IiwidG9Db250YWluIiwicmVsb2FkIiwiY29tcGFjdCIsInJlcGxhY2VBbGwiLCJzbGljZSIsImxvY2F0b3IiLCJmaXJzdCIsInNlc3Npb24iLCJyZW1vdGUiLCJjc3JmX3Rva2VuIiwiaW5kdXN0cnkiLCJjb250YWluZXIiLCJwcm9jZXNzIiwiZW52IiwiTklTX0UyRV9BUFBfQ09OVEFJTkVSIiwidG9NYXRjaCIsImRvY2tlciIsIk5JU19URVNUX0RPQ0tFUiIsImVuY29kaW5nIiwidHJpbSIsImRyb3BwZWQiLCJyb3V0ZSIsIm1ldGhvZCIsImNvbnRpbnVlIiwicmVzcG9uc2UiLCJmZXRjaCIsImFib3J0IiwicmVhZCIsImFjY2VwdGVkIiwicG9sbCIsInRvSGF2ZUNvdW50IiwiaW5wdXQiLCJsYXN0IiwidG9CZURpc2FibGVkIiwib3duZXJzIiwiZmllbGQiLCJhbGwiLCJzZWxlY3RPcHRpb24iLCJ0YXNrcyIsImluZGV4IiwibnRoIiwiZHJhZnQiLCJkZXZpY2VzIiwibWFwIiwiZGV2aWNlIiwic29ydCIsImlzc3VlcyIsIm9yaWdpbmFsX3JlcXVpcmVtZW50IiwidmFsdmVDb3VudCIsIl9yZWYiLCJfcGF5bG9hZCRpdGVtcyIsInRlY2hub2xvZ2llcyIsImNvbW1hbmRzIiwiZ2V0QnlMYWJlbCIsInBheWxvYWQiLCJub2RlcyIsIkFycmF5IiwiaXNBcnJheSIsIml0ZW1zIiwibm9kZSIsImZyb20iLCJsZW5ndGgiLCJfIiwiY29udHJvbGxlciIsImZpbmQiLCJmaWx0ZXIiLCJpZCIsImlkZW50aXR5Iiwic3lzdGVtX293bmVyX2lkIiwib3JpZ2luIiwiYmVmb3JlIiwib3JpZ2luYWxEcmFmdCIsInRvSGF2ZVVSTCIsIlVSTCIsInVybCIsInNlYXJjaFBhcmFtcyIsInJlcGxhY2UiLCJhZnRlciIsInRhcmdldFJlc3BvbnNlIiwic3RhcnRzV2l0aCIsInRhcmdldERyYWZ0IiwiX29sZFdvcmtmbG93JGRhdGEkY29uIiwiX29sZFdvcmtmbG93JGRhdGEiLCJfbmV3V29ya2Zsb3ckZGF0YSRjb24iLCJfbmV3V29ya2Zsb3ckZGF0YSIsInNjb3BlcyIsInVuY2hlY2siLCJfcmVmMiIsIl9wYXlsb2FkJGl0ZW1zMiIsInN1cHBsZW1lbnQiLCJyZXZpc2VkIiwiZm91cnRoIiwib2xkV29ya2Zsb3ciLCJfcmVmMyIsIl9wYXlsb2FkJGl0ZW1zMyIsIm5ld1dvcmtmbG93Iiwib2xkQ29udGV4dCIsIm5ld0NvbnRleHQiXSwic291cmNlcyI6WyJwcm9qZWN0LWRyYWZ0LnNwZWMudHMiXSwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgdGVzdCwgZXhwZWN0IH0gZnJvbSAncGxheXdyaWdodC90ZXN0JztcbmltcG9ydCB7IHJhbmRvbVVVSUQgfSBmcm9tICdub2RlOmNyeXB0byc7XG5pbXBvcnQgeyBleGVjRmlsZVN5bmMgfSBmcm9tICdub2RlOmNoaWxkX3Byb2Nlc3MnO1xuXG50ZXN0KCduYXRpdmUgd2l6YXJkIHByZXNlcnZlcyBpdHMgY29tcGxldGUgc291cmNlIHdoaWxlIGFkb3B0aW5nIGFuIGVkaXRlZCBzaGFyZWQgZHJhZnQgQHByb2plY3QtZHJhZnQnLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcbiAgY29uc3QgcHJvamVjdCA9ICduaXMtZTJlLXNoYXJlZC1uYXRpdmUtJyArIHJhbmRvbVVVSUQoKTtcbiAgY29uc3QgcnVuID0gcmFuZG9tVVVJRCgpO1xuICBjb25zdCBncmFwaCA9IFt7IGNsdXN0ZXJfaWQ6ICdkcml2ZScsIGxhYmVsOiAnUmVnZWx1bmcnLCBuZXR3b3JrX2lkOiAnY2FuX2ZkJywgbmV0d29ya19sYWJlbDogJ0NBTi1GRCcsIGJ1c19uYW1lOiAnUmVnZWx1bmcnLFxuICAgIGNvbnRyb2xsZXJzOiBbeyBlY3U6ICdNb3RvcnN0ZXVlcnVuZycsIHNlbnNvcnM6IFtdLCBhY3R1YXRvcnM6IFtdIH0sIHsgZWN1OiAnQW56ZWlnZScsIHNlbnNvcnM6IFtdLCBhY3R1YXRvcnM6IFtdIH1dIH1dO1xuICBjb25zdCBwcm9tcHQgPSBgU3RydWt0dXJpZXJ0ZSBWb3JnYWJlbiBmdWVyIGRlbiBFbmdpbmVlcmluZy1BZ2VudGVuOlxuLSBMYXVmLUlEOiAke3J1bn1cbi0gSW5kdXN0cmllOiBBdXRvbW90aXZlXG4tIE5ldHp3ZXJrdGVjaG5vbG9naWVuOiBDQU4tRkQgKGNhbl9mZClcbi0gSGFyZHdhcmUtU29sbHdlcnRlOiB7XCJnYXRld2F5c1wiOjEsXCJlY3VzXCI6MixcInNlbnNvcnNcIjowLFwiYWN0dWF0b3JzXCI6MH1cbi0gU3lzdGVtY2x1c3Rlci1HcmFwaDogJHtKU09OLnN0cmluZ2lmeShncmFwaCl9XG5Lb25rcmV0ZSBBdWZnYWJlIGRlcyBOdXR6ZXJzLCBwZXIgV2l6YXJkLVVlYmVybmVobWVuIGJlc3RhZXRpZ3Q6XG5FcnpldWdlIE1vdG9yc3RldWVydW5nIHVuZCBBbnplaWdlIG1pdCBlaW5lbSBHYXRld2F5IFN5c3RlbS5gO1xuICBjb25zdCBzdGFydGVkID0gYXdhaXQgcGFnZS5yZXF1ZXN0LnBvc3QoJy9hcGkvZW5naW5lZXJpbmcvYWdlbnQvY2hhdCcsIHsgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9LCB0aW1lb3V0OiAxMjBfMDAwLFxuICAgIGRhdGE6IHsgcHJvbXB0LCB3aXphcmRfY29tbWFuZDogeyBhY3Rpb246ICdTVEFSVCcsIHJ1bl9pZDogcnVuLCBvcGVyYXRpb25faWQ6IHJhbmRvbVVVSUQoKSwgdGFyZ2V0OiAnZW5naW5lZXJpbmdfbW9kZWwnLFxuICAgICAgd2l6YXJkX2NvbnRleHQ6IHsgcHJvamVjdF9pZDogcHJvamVjdCwgcnVuX2lkOiBydW4sIHByb2plY3RfbmFtZTogJ0dlbWVpbnNhbWVyIG5hdGl2ZXIgQXVmdHJhZycsIHNjb3BlX2lkczogWydlbmdpbmVlcmluZ19tb2RlbCddLFxuICAgICAgICBtb2RlOiAnZnVsbCcsIHByb2Nlc3NfaWRzOiBbJ2RlZmF1bHRzJywgJ3Jldmlld19nYXRlJ10sIHRhc2s6ICdNb3RvcnN0ZXVlcnVuZyB1bmQgQW56ZWlnZSBhbiBTeXN0ZW0nIH0gfSB9IH0pO1xuICBleHBlY3Qoc3RhcnRlZC5vaygpLCBhd2FpdCBzdGFydGVkLnRleHQoKSkudG9CZSh0cnVlKTtcbiAgY29uc3QgaW5pdGlhbCA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb2plY3QtZHJhZnQnLCB7IGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSB9KSkuanNvbigpO1xuICBleHBlY3QoaW5pdGlhbC5kYXRhLnNvdXJjZV9mb3JtYXQpLnRvQmUoJ1dJWkFSRF9WMicpO1xuICBleHBlY3QoaW5pdGlhbC5kYXRhLnN0cnVjdHVyZWRfc291cmNlLnByb21wdCkudG9CZShwcm9tcHQpO1xuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vZW5naW5lZXJpbmc/YXNzaXN0YW50PXByb2plY3QmcHJvamVjdD0ke3Byb2plY3R9YCk7XG4gIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8OkbnplbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGRpYWxvZy5nZXRCeVRleHQoJ0dlbWVpbnNhbWVuIFByb2pla3RlbnR3dXJmIGJlYXJiZWl0ZW4nLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGNvbnN0IGVkaXRvciA9IGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0dlc3BlaWNoZXJ0ZXIgUHJvamVrdGVudHd1cmYnIH0pO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yLmdldEJ5Um9sZSgndGV4dGJveCcsIHsgbmFtZTogJ1Byb2pla3RiZXNjaHJlaWJ1bmcnLCBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUocHJvbXB0KTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgndGV4dGJveCcsIHsgbmFtZTogJ0FuZm9yZGVydW5nIGVyZ8OkbnplbicsIGV4YWN0OiB0cnVlIH0pLmZpbGwoJ0RpZSBNb2RlbGxiZXNjaHJlaWJ1bmcgc29sbCBkZW4gbG9rYWxlbiBSZWdlbHVuZ3N6d2VjayBkb2t1bWVudGllcmVuLicpO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdFcmfDpG56dW5nIHNwZWljaGVybicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCdzdGF0dXMnKSkudG9Db250YWluVGV4dCgnUmV2aXNpb24gMiBnZXNwZWljaGVydCcpO1xuICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdHZXNwZWljaGVydGVuIEVudHd1cmYgaW0gQXVmdHJhZyDDvGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IpLm5vdC50b0JlVmlzaWJsZSh7IHRpbWVvdXQ6IDEyMF8wMDAgfSk7XG4gIGNvbnN0IHBlcnNpc3RlZCA9IGF3YWl0IChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93JywgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0gfSkpLmpzb24oKTtcbiAgY29uc3Qgc3RhdGUgPSBwZXJzaXN0ZWQuY29udGV4dCA/PyBwZXJzaXN0ZWQuZGF0YT8uY29udGV4dDtcbiAgZXhwZWN0KHN0YXRlLmFnZW50X3dpemFyZF9zdGF0dXMucnVuX2lkKS50b0JlKHJ1bik7XG4gIGV4cGVjdChzdGF0ZS5hZ2VudF93aXphcmRfc3RhdHVzLmVuZ2luZWVyaW5nX2RyYWZ0X3JlZikudG9FcXVhbCh7IGRyYWZ0X2lkOiBpbml0aWFsLmRhdGEuZHJhZnRfaWQsIHJldmlzaW9uOiAyIH0pO1xuICBleHBlY3Qoc3RhdGUud2l6YXJkX3JlcXVlc3QucHJvbXB0KS50b0NvbnRhaW4oSlNPTi5zdHJpbmdpZnkoZ3JhcGgpKTtcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSkpLnRvQmVWaXNpYmxlKCk7XG59KTtcblxudGVzdCgnY29uZmxpY3RpbmcgZWRpdHMgcmV0YWluIGlucHV0IGFuZCBsb2FkIHRoZSBjdXJyZW50IHJldmlzaW9uIHdpdGhvdXQgb3ZlcndyaXRpbmcgaXQgQHByb2plY3QtZHJhZnQnLCBhc3luYyAoeyBwYWdlIH0pID0+IHtcbiAgY29uc3QgY29tcGFjdCA9ICcyMDI2MDkxNTAwMDAwMDAwMC0nICsgcmFuZG9tVVVJRCgpLnJlcGxhY2VBbGwoJy0nLCAnJykuc2xpY2UoMCwgOCk7XG4gIGNvbnN0IHByb2plY3QgPSAnbmV0d29yay1wcm9qZWN0LScgKyBjb21wYWN0O1xuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vYWdlbnQ/cHJvamVjdD0ke2NvbXBhY3R9YCk7XG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnTmFjaHJpY2h0IGFuIGRlbiBFbmdpbmVlcmluZy1Bc3Npc3RlbnRlbicgfSkuZmlsbCgnRXJzdGVsbGUgZWluIFByb2pla3QgbWl0IFJhc3BiZXJyeSBQaSB1bmQgZHJlaSBUZW1wZXJhdHVyc2Vuc29yZW4uJyk7XG4gIGF3YWl0IHBhZ2UubG9jYXRvcignLmVuZy1hZ2VudC1jb21wb3NlcicpLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnU2VuZGVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgY29uc3QgZWRpdG9yID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0dlc3BlaWNoZXJ0ZXIgUHJvamVrdGVudHd1cmYnIH0pO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAxJyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdOYW1lJywgZXhhY3Q6IHRydWUgfSkuZmlyc3QoKS5maWxsKCdNZWluZVJlZ2VsdW5nJyk7XG4gIGNvbnN0IHNlc3Npb24gPSBhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9yZXZpZXctc2Vzc2lvbicpKS5qc29uKCk7XG4gIGNvbnN0IHJlbW90ZSA9IGF3YWl0IHBhZ2UucmVxdWVzdC5wb3N0KCcvYXBpL2VuZ2luZWVyaW5nL2FnZW50L3Byb2plY3QtZHJhZnQnLCB7IGhlYWRlcnM6IHtcbiAgICAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCwgJ1gtSHVtYW4tUmV2aWV3JzogJ2NvbmZpcm1lZCcsICdYLVJldmlldy1DU1JGJzogc2Vzc2lvbi5jc3JmX3Rva2VuLFxuICB9LCBkYXRhOiB7IGFjdGlvbjogJ1JFU09MVkUnLCBvcGVyYXRpb25faWQ6IHJhbmRvbVVVSUQoKSwgcmV2aXNpb246IDEsIGluZHVzdHJ5OiAnYnVpbGRpbmdfYXV0b21hdGlvbicgfSB9KTtcbiAgZXhwZWN0KHJlbW90ZS5vaygpKS50b0JlKHRydWUpO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBbmdhYmVuIHNwZWljaGVybicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdFbnR3dXJmc2tvbmZsaWt0JyB9KSkudG9Db250YWluVGV4dCgnUmV2aXNpb24gMicpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yLmdldEJ5Um9sZSgndGV4dGJveCcsIHsgbmFtZTogJ05hbWUnLCBleGFjdDogdHJ1ZSB9KS5maXJzdCgpKS50b0hhdmVWYWx1ZSgnTWVpbmVSZWdlbHVuZycpO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBa3R1ZWxsZW4gU3RhbmQgbGFkZW4gdW5kIEVpbmdhYmVrb3BpZSBiZWhhbHRlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnRWluc2F0emJlcmVpY2gnLCBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoJ2J1aWxkaW5nX2F1dG9tYXRpb24nKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdOYW1lJywgZXhhY3Q6IHRydWUgfSkuZmlyc3QoKSkudG9IYXZlVmFsdWUoJ1Jhc3BiZXJyeVBpJyk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnRXJoYWx0ZW5lIEVpbmdhYmVuIHZvciBkZW0gS29uZmxpa3QnLCBleGFjdDogdHJ1ZSB9KSkudG9IYXZlVmFsdWUoL01laW5lUmVnZWx1bmcvKTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgndGV4dGJveCcsIHsgbmFtZTogJ05hbWUnLCBleGFjdDogdHJ1ZSB9KS5maXJzdCgpLmZpbGwoJ01laW5lUmVnZWx1bmcnKTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQW5nYWJlbiBzcGVpY2hlcm4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yLmdldEJ5Um9sZSgnc3RhdHVzJykpLnRvQ29udGFpblRleHQoJ1JldmlzaW9uIDMgZ2VzcGVpY2hlcnQnKTtcbn0pO1xuXG50ZXN0KCdkcmFmdCByZWNvdmVycyBhIGxvc3Qgc2F2ZSByZXNwb25zZSBhbmQgc3Vydml2ZXMgYXBwbGljYXRpb24gcmVzdGFydCBAcHJvamVjdC1kcmFmdCcsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xuICBjb25zdCBjb250YWluZXIgPSBwcm9jZXNzLmVudi5OSVNfRTJFX0FQUF9DT05UQUlORVIhO1xuICBleHBlY3QoY29udGFpbmVyKS50b01hdGNoKC9ebmlzLWUyZS1hcHAtW2EtZjAtOV0rJC8pO1xuICBjb25zdCBkb2NrZXIgPSBwcm9jZXNzLmVudi5OSVNfVEVTVF9ET0NLRVIgfHwgJ2RvY2tlcic7XG4gIGV4cGVjdChleGVjRmlsZVN5bmMoZG9ja2VyLCBbJ2luc3BlY3QnLCBjb250YWluZXIsICctLWZvcm1hdCcsICd7e2luZGV4IC5Db25maWcuTGFiZWxzIFwibmV0d29ya2lzLnRlc3RcIn19J10sIHsgZW5jb2Rpbmc6ICd1dGY4JyB9KS50cmltKCkpLnRvQmUoJ2Rpc3Bvc2FibGUnKTtcbiAgY29uc3QgY29tcGFjdCA9ICcyMDI2MDkxNTAwMDAwMDAwMC0nICsgcmFuZG9tVVVJRCgpLnJlcGxhY2VBbGwoJy0nLCAnJykuc2xpY2UoMCwgOCk7XG4gIGNvbnN0IHByb2plY3QgPSAnbmV0d29yay1wcm9qZWN0LScgKyBjb21wYWN0O1xuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vYWdlbnQ/cHJvamVjdD0ke2NvbXBhY3R9YCk7XG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnTmFjaHJpY2h0IGFuIGRlbiBFbmdpbmVlcmluZy1Bc3Npc3RlbnRlbicgfSkuZmlsbCgnRXJzdGVsbGUgZWluIFByb2pla3QgbWl0IFJhc3BiZXJyeSBQaSB1bmQgZHJlaSBUZW1wZXJhdHVyc2Vuc29yZW4uJyk7XG4gIGF3YWl0IHBhZ2UubG9jYXRvcignLmVuZy1hZ2VudC1jb21wb3NlcicpLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnU2VuZGVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgY29uc3QgZWRpdG9yID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0dlc3BlaWNoZXJ0ZXIgUHJvamVrdGVudHd1cmYnIH0pO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCc0IEdlcsOkdGUnKTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgndGV4dGJveCcsIHsgbmFtZTogJ0Fuc2NobHVzc3RlY2hub2xvZ2llJywgZXhhY3Q6IHRydWUgfSkuZmlyc3QoKS5maWxsKCdldGhlcm5ldCcpO1xuICBsZXQgZHJvcHBlZCA9IGZhbHNlO1xuICBhd2FpdCBwYWdlLnJvdXRlKCcqKi9hcGkvZW5naW5lZXJpbmcvYWdlbnQvcHJvamVjdC1kcmFmdCcsIGFzeW5jIHJvdXRlID0+IHtcbiAgICBpZiAocm91dGUucmVxdWVzdCgpLm1ldGhvZCgpICE9PSAnUE9TVCcgfHwgZHJvcHBlZCkgcmV0dXJuIHJvdXRlLmNvbnRpbnVlKCk7XG4gICAgLy8gRXhlY3V0ZSB0aGUgcmVhbCBzZXJ2ZXIgd3JpdGUsIGJ1dCBsb3NlIGl0cyB0cmFuc3BvcnQgcmVzcG9uc2UuXG4gICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCByb3V0ZS5mZXRjaCgpO1xuICAgIGV4cGVjdChyZXNwb25zZS5vaygpKS50b0JlKHRydWUpO1xuICAgIGRyb3BwZWQgPSB0cnVlO1xuICAgIGF3YWl0IHJvdXRlLmFib3J0KCdjb25uZWN0aW9ucmVzZXQnKTtcbiAgfSk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0FuZ2FiZW4gc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ2FsZXJ0JykpLnRvQmVWaXNpYmxlKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnQW5zY2hsdXNzdGVjaG5vbG9naWUnLCBleGFjdDogdHJ1ZSB9KS5maXJzdCgpKS50b0hhdmVWYWx1ZSgnZXRoZXJuZXQnKTtcbiAgY29uc3QgcmVhZCA9IGFzeW5jICgpID0+IChhd2FpdCAoYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9qZWN0LWRyYWZ0JywgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0gfSkpLmpzb24oKSkuZGF0YTtcbiAgY29uc3QgYWNjZXB0ZWQgPSBhd2FpdCByZWFkKCk7XG4gIGV4cGVjdChhY2NlcHRlZC5yZXZpc2lvbikudG9CZSgyKTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnQW5nYWJlbiBzcGVpY2hlcm4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yLmdldEJ5Um9sZSgnc3RhdHVzJykpLnRvQ29udGFpblRleHQoJ1JldmlzaW9uIDIgZ2VzcGVpY2hlcnQnKTtcbiAgZXhwZWN0KGF3YWl0IHJlYWQoKSkudG9FcXVhbChhY2NlcHRlZCk7XG4gIGV4ZWNGaWxlU3luYyhkb2NrZXIsIFsncmVzdGFydCcsIGNvbnRhaW5lcl0sIHsgdGltZW91dDogNjBfMDAwIH0pO1xuICBhd2FpdCBleHBlY3QucG9sbChhc3luYyAoKSA9PiB7XG4gICAgdHJ5IHsgcmV0dXJuIChhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL3JlYWR5JywgeyB0aW1lb3V0OiAyMDAwIH0pKS5vaygpOyB9IGNhdGNoIHsgcmV0dXJuIGZhbHNlOyB9XG4gIH0sIHsgdGltZW91dDogMTIwXzAwMCB9KS50b0JlKHRydWUpO1xuICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAyJyk7XG4gIGV4cGVjdChhd2FpdCByZWFkKCkpLnRvRXF1YWwoYWNjZXB0ZWQpO1xufSk7XG5cbnRlc3QoJ3JlbW92aW5nIGEgZHJhZnQgZGV2aWNlIHN1cnZpdmVzIHNhdmUsIGFtZW5kbWVudCBhbmQgcmVsb2FkIEBwcm9qZWN0LWRyYWZ0JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XG4gIGNvbnN0IGNvbXBhY3QgPSAnMjAyNjA5MTUwMDAwMDAwMDAtJyArIHJhbmRvbVVVSUQoKS5yZXBsYWNlQWxsKCctJywgJycpLnNsaWNlKDAsIDgpO1xuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vYWdlbnQ/cHJvamVjdD0ke2NvbXBhY3R9YCk7XG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnTmFjaHJpY2h0IGFuIGRlbiBFbmdpbmVlcmluZy1Bc3Npc3RlbnRlbicgfSkuZmlsbCgnRXJzdGVsbGUgZWluIFByb2pla3QgbWl0IGVpbmVtIFJhc3BiZXJyeSBQaSB1bmQgZHJlaSBUZW1wZXJhdHVyc2Vuc29yZW4uJyk7XG4gIGF3YWl0IHBhZ2UubG9jYXRvcignLmVuZy1hZ2VudC1jb21wb3NlcicpLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnU2VuZGVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgY29uc3QgZWRpdG9yID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0dlc3BlaWNoZXJ0ZXIgUHJvamVrdGVudHd1cmYnIH0pO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCc0IEdlcsOkdGUnKTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgnZ3JvdXAnLCB7IG5hbWU6ICdUZW1wZXJhdHVyc2Vuc29yMyDCtyBTRU5TT1InLCBleGFjdDogdHJ1ZSB9KVxuICAgIC5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1cyBFbnR3dXJmIGVudGZlcm5lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0FuZ2FiZW4gc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3N0YXR1cycpKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAyIGdlc3BlaWNoZXJ0Jyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdBbmZvcmRlcnVuZyBlcmfDpG56ZW4nLCBleGFjdDogdHJ1ZSB9KS5maWxsKCdadXPDpHR6bGljaCB6d2VpIERydWNrc2Vuc29yZW4uJyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8Okbnp1bmcgc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3N0YXR1cycpKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAzIGdlc3BlaWNoZXJ0Jyk7XG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IpLnRvQ29udGFpblRleHQoJzUgR2Vyw6R0ZScpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yLmdldEJ5Um9sZSgnZ3JvdXAnLCB7IG5hbWU6ICdUZW1wZXJhdHVyc2Vuc29yMyDCtyBTRU5TT1InLCBleGFjdDogdHJ1ZSB9KSkudG9IYXZlQ291bnQoMCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCdncm91cCcsIHsgbmFtZTogJ0RydWNrc2Vuc29yMiDCtyBTRU5TT1InLCBleGFjdDogdHJ1ZSB9KSkudG9CZVZpc2libGUoKTtcbn0pO1xuXG5mb3IgKGNvbnN0IG1vZGUgb2YgWydjaGF0JywgJ3dpemFyZCddKSB0ZXN0KGBtaXNzaW5nIGNvbnRyb2xsZXIgY2FuIGJlIGFkZGVkIGluICR7bW9kZX0gYW5kIHRoZSByZXF1aXJlbWVudCByZW1haW5zIGVkaXRhYmxlIEBwcm9qZWN0LWRyYWZ0YCwgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XG4gIGNvbnN0IGNvbXBhY3QgPSAnMjAyNjA5MTUwMDAwMDAwMDAtJyArIHJhbmRvbVVVSUQoKS5yZXBsYWNlQWxsKCctJywgJycpLnNsaWNlKDAsIDgpO1xuICBjb25zdCBwcm9qZWN0ID0gJ25ldHdvcmstcHJvamVjdC0nICsgY29tcGFjdDtcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvL2FnZW50P3Byb2plY3Q9JHtjb21wYWN0fWApO1xuICBjb25zdCBpbnB1dCA9IHBhZ2UuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnTmFjaHJpY2h0IGFuIGRlbiBFbmdpbmVlcmluZy1Bc3Npc3RlbnRlbicgfSk7XG4gIGF3YWl0IGlucHV0LmZpbGwoJ0VpbiBuZXVlcyBQcm9qZWt0IG1pdCBkcmVpIFNlbnNvcmVuLicpO1xuICBhd2FpdCBwYWdlLmxvY2F0b3IoJy5lbmctYWdlbnQtY29tcG9zZXInKS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ1NlbmRlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGxldCBlZGl0b3IgPSBwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnR2VzcGVpY2hlcnRlciBQcm9qZWt0ZW50d3VyZicgfSkubGFzdCgpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCczIEdlcsOkdGUnKTtcbiAgYXdhaXQgZWRpdG9yLmdldEJ5VGV4dCgnT2ZmZW5lIEFuZ2FiZW4nLCB7IGV4YWN0OiBmYWxzZSB9KS5jbGljaygpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCdDb250cm9sbGVyIGVyZ8OkbnplbicpO1xuICBpZiAobW9kZSA9PT0gJ3dpemFyZCcpIHtcbiAgICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAvSW0gV2l6YXJkIGJlYXJiZWl0ZW4vIH0pLmNsaWNrKCk7XG4gICAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSkpLnRvQmVWaXNpYmxlKCk7XG4gICAgZWRpdG9yID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0dlc3BlaWNoZXJ0ZXIgUHJvamVrdGVudHd1cmYnIH0pLmxhc3QoKTtcbiAgICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0F1ZnRyYWcgc3RhcnRlbicsIGV4YWN0OiB0cnVlIH0pKS50b0JlRGlzYWJsZWQoKTtcbiAgICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnQW5mb3JkZXJ1bmcgZXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSkuZmlsbCgnRXJnw6RuemUgZWluZW4gUmFzcGJlcnJ5IFBpLicpO1xuICAgIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0VyZ8Okbnp1bmcgc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgfSBlbHNlIHtcbiAgICBhd2FpdCBpbnB1dC5maWxsKCdFcmfDpG56ZSBlaW5lbiBSYXNwYmVycnkgUGkuJyk7XG4gICAgYXdhaXQgcGFnZS5sb2NhdG9yKCcuZW5nLWFnZW50LWNvbXBvc2VyJykuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdTZW5kZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICB9XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IpLnRvQ29udGFpblRleHQoJzQgR2Vyw6R0ZScpO1xuICBhd2FpdCBwYWdlLnJlbG9hZCgpO1xuICBlZGl0b3IgPSBwYWdlLmdldEJ5Um9sZSgncmVnaW9uJywgeyBuYW1lOiAnR2VzcGVpY2hlcnRlciBQcm9qZWt0ZW50d3VyZicgfSkubGFzdCgpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAyJyk7XG4gIGNvbnN0IG93bmVycyA9IGVkaXRvci5nZXRCeVJvbGUoJ2NvbWJvYm94JywgeyBuYW1lOiAnVmVyYXJiZWl0ZW5kZXIgQ29udHJvbGxlcicsIGV4YWN0OiB0cnVlIH0pO1xuICBhd2FpdCBleHBlY3Qob3duZXJzKS50b0hhdmVDb3VudCgzKTtcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBhd2FpdCBvd25lcnMuYWxsKCkpIGF3YWl0IGZpZWxkLnNlbGVjdE9wdGlvbih7IGxhYmVsOiAnUmFzcGJlcnJ5UGknIH0pO1xuICBjb25zdCB0YXNrcyA9IGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdNZXNzZ3LDtsOfZSBvZGVyIEdlcsOkdGVhdWZnYWJlJywgZXhhY3Q6IHRydWUgfSk7XG4gIGF3YWl0IGV4cGVjdCh0YXNrcykudG9IYXZlQ291bnQoNCk7XG4gIGZvciAobGV0IGluZGV4ID0gMTsgaW5kZXggPCA0OyBpbmRleCsrKSBhd2FpdCB0YXNrcy5udGgoaW5kZXgpLmZpbGwoJ1RlbXBlcmF0dXIgbWVzc2VuJyk7XG4gIGZvciAoY29uc3QgZmllbGQgb2YgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgndGV4dGJveCcsIHsgbmFtZTogJ0Fuc2NobHVzc3RlY2hub2xvZ2llJywgZXhhY3Q6IHRydWUgfSkuYWxsKCkpIGF3YWl0IGZpZWxkLmZpbGwoJ2V0aGVybmV0Jyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2NvbWJvYm94JywgeyBuYW1lOiAnVGVjaG5pc2NoZSBQYXJhbWV0ZXInLCBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ2RlZmF1bHRzJyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0FuZ2FiZW4gc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3N0YXR1cycpKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAzIGdlc3BlaWNoZXJ0Jyk7XG4gIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9qZWN0LWRyYWZ0JywgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0gfSk7XG4gIGNvbnN0IGRyYWZ0ID0gKGF3YWl0IHJlc3BvbnNlLmpzb24oKSkuZGF0YTtcbiAgZXhwZWN0KGRyYWZ0LmRldmljZXMubWFwKChkZXZpY2U6IHsgbmFtZTogc3RyaW5nIH0pID0+IGRldmljZS5uYW1lKS5zb3J0KCkpLnRvRXF1YWwoWydSYXNwYmVycnlQaScsICdTZW5zb3IxJywgJ1NlbnNvcjInLCAnU2Vuc29yMyddKTtcbiAgZXhwZWN0KGRyYWZ0Lmlzc3VlcykudG9FcXVhbChbXSk7XG4gIGV4cGVjdChkcmFmdC5vcmlnaW5hbF9yZXF1aXJlbWVudCkudG9CZSgnRWluIG5ldWVzIFByb2pla3QgbWl0IGRyZWkgU2Vuc29yZW4uJyk7XG4gIGF3YWl0IGV4cGVjdChwYWdlLmdldEJ5Um9sZSgnZGlhbG9nJywgeyBuYW1lOiAnRW5naW5lZXJpbmctQXVmdHJhZyBlcnN0ZWxsZW4nIH0pKS50b0hhdmVDb3VudChtb2RlID09PSAnd2l6YXJkJyA/IDEgOiAwKTtcbn0pO1xuXG5mb3IgKGNvbnN0IHZhbHZlQ291bnQgb2YgWzIsIDVdKSB0ZXN0KGBjaGF0IGNyZWF0ZXMgYW5kIGFwcGxpZXMgdGhlIHJlYWwgbW9kZWwgd2l0aCAke3ZhbHZlQ291bnR9IHZhbHZlcyB3aXRob3V0IG9wZW5pbmcgdGhlIHdpemFyZCBAcHJvamVjdC1kcmFmdGAsIGFzeW5jICh7IHBhZ2UgfSkgPT4ge1xuICBjb25zdCBjb21wYWN0ID0gJzIwMjYwOTE1MDAwMDAwMDAwLScgKyByYW5kb21VVUlEKCkucmVwbGFjZUFsbCgnLScsICcnKS5zbGljZSgwLCA4KTtcbiAgY29uc3QgcHJvamVjdCA9ICduZXR3b3JrLXByb2plY3QtJyArIGNvbXBhY3Q7XG4gIGF3YWl0IHBhZ2UuZ290byhgL3N0dWRpby9hZ2VudD9wcm9qZWN0PSR7Y29tcGFjdH1gKTtcbiAgYXdhaXQgcGFnZS5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdOYWNocmljaHQgYW4gZGVuIEVuZ2luZWVyaW5nLUFzc2lzdGVudGVuJyB9KS5maWxsKFxuICAgIGBJY2ggbcO2Y2h0ZSBlaW4ga2xlaW5lcyBQcm9qZWt0IG1pdCBlaW5lbSBSYXNwYmVycnktUGksIGRyZWkgVGVtcGVyYXR1cnNlbnNvcmVuIHVuZCAke3ZhbHZlQ291bnR9IFZlbnRpbGVuLmApO1xuICBhd2FpdCBwYWdlLmxvY2F0b3IoJy5lbmctYWdlbnQtY29tcG9zZXInKS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ1NlbmRlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGNvbnN0IGVkaXRvciA9IHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdHZXNwZWljaGVydGVyIFByb2pla3RlbnR3dXJmJyB9KTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvcikudG9Db250YWluVGV4dChgJHs0ICsgdmFsdmVDb3VudH0gR2Vyw6R0ZWApO1xuICBhd2FpdCBleHBlY3QocGFnZS5nZXRCeVJvbGUoJ2RpYWxvZycsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJzdGVsbGVuJyB9KSkudG9IYXZlQ291bnQoMCk7XG4gIGNvbnN0IHRlY2hub2xvZ2llcyA9IGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdBbnNjaGx1c3N0ZWNobm9sb2dpZScsIGV4YWN0OiB0cnVlIH0pO1xuICBjb25zdCBvd25lcnMgPSBlZGl0b3IuZ2V0QnlSb2xlKCdjb21ib2JveCcsIHsgbmFtZTogJ1ZlcmFyYmVpdGVuZGVyIENvbnRyb2xsZXInLCBleGFjdDogdHJ1ZSB9KTtcbiAgY29uc3QgY29tbWFuZHMgPSBlZGl0b3IuZ2V0QnlSb2xlKCdjb21ib2JveCcsIHsgbmFtZTogJ1ZlbnRpbGJlZmVobCcsIGV4YWN0OiB0cnVlIH0pO1xuICBhd2FpdCBleHBlY3QodGVjaG5vbG9naWVzKS50b0hhdmVDb3VudCg0ICsgdmFsdmVDb3VudCk7XG4gIGF3YWl0IGV4cGVjdChvd25lcnMpLnRvSGF2ZUNvdW50KDMgKyB2YWx2ZUNvdW50KTtcbiAgYXdhaXQgZXhwZWN0KGNvbW1hbmRzKS50b0hhdmVDb3VudCh2YWx2ZUNvdW50KTtcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBhd2FpdCB0ZWNobm9sb2dpZXMuYWxsKCkpIGF3YWl0IGZpZWxkLmZpbGwoJ2V0aGVybmV0Jyk7XG4gIGZvciAoY29uc3QgZmllbGQgb2YgYXdhaXQgb3duZXJzLmFsbCgpKSBhd2FpdCBmaWVsZC5zZWxlY3RPcHRpb24oeyBsYWJlbDogJ1Jhc3BiZXJyeVBpJyB9KTtcbiAgZm9yIChjb25zdCBmaWVsZCBvZiBhd2FpdCBjb21tYW5kcy5hbGwoKSkgYXdhaXQgZmllbGQuc2VsZWN0T3B0aW9uKCdPUEVOX0NMT1NFJyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2NvbWJvYm94JywgeyBuYW1lOiAnVGVjaG5pc2NoZSBQYXJhbWV0ZXInLCBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oJ2RlZmF1bHRzJyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0FuZ2FiZW4gc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeVJvbGUoJ3N0YXR1cycpKS50b0NvbnRhaW5UZXh0KCdSZXZpc2lvbiAyIGdlc3BlaWNoZXJ0Jyk7XG4gIGF3YWl0IHBhZ2UucmVsb2FkKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IpLnRvQ29udGFpblRleHQoJ1JldmlzaW9uIDInKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvci5nZXRCeUxhYmVsKCdBbnNjaGx1c3N0ZWNobm9sb2dpZScsIHsgZXhhY3Q6IHRydWUgfSkuZmlyc3QoKSkudG9IYXZlVmFsdWUoJ2V0aGVybmV0Jyk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ01vZGVsbHZvcnNjaGxhZyBlcnN0ZWxsZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnVm9yc2NobGFnIGZyZWlnZWJlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdJbnMgTW9kZWxsIMO8YmVybmVobWVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KC9Nb2RlbGxvYmpla3RlIGJlc3TDpHRpZ3QvKSkudG9CZVZpc2libGUoKTtcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSkpLnRvSGF2ZUNvdW50KDApO1xuICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtbm9kZXMnLCB7IGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSB9KTtcbiAgZXhwZWN0KHJlc3BvbnNlLm9rKCkpLnRvQmUodHJ1ZSk7XG4gIGNvbnN0IHBheWxvYWQgPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gIGNvbnN0IG5vZGVzID0gQXJyYXkuaXNBcnJheShwYXlsb2FkKSA/IHBheWxvYWQgOiBwYXlsb2FkLml0ZW1zID8/IHBheWxvYWQuZGF0YSA/PyBbXTtcbiAgZXhwZWN0KG5vZGVzLm1hcCgobm9kZTogeyBuYW1lOiBzdHJpbmcgfSkgPT4gbm9kZS5uYW1lKS5zb3J0KCkpLnRvRXF1YWwoXG4gICAgWydSYXNwYmVycnlQaScsICdUZW1wZXJhdHVyc2Vuc29yMScsICdUZW1wZXJhdHVyc2Vuc29yMicsICdUZW1wZXJhdHVyc2Vuc29yMycsXG4gICAgICAuLi5BcnJheS5mcm9tKHsgbGVuZ3RoOiB2YWx2ZUNvdW50IH0sIChfLCBpbmRleCkgPT4gYFZlbnRpbGFrdG9yJHtpbmRleCArIDF9YCldLnNvcnQoKSk7XG4gIGNvbnN0IGNvbnRyb2xsZXIgPSBub2Rlcy5maW5kKChub2RlOiB7IG5hbWU6IHN0cmluZyB9KSA9PiBub2RlLm5hbWUgPT09ICdSYXNwYmVycnlQaScpO1xuICBmb3IgKGNvbnN0IG5vZGUgb2Ygbm9kZXMuZmlsdGVyKChub2RlOiB7IGlkOiBzdHJpbmcgfSkgPT4gbm9kZS5pZCAhPT0gY29udHJvbGxlci5pZCkpIGV4cGVjdChub2RlLmlkZW50aXR5LnN5c3RlbV9vd25lcl9pZCkudG9CZShjb250cm9sbGVyLmlkKTtcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcbiAgYXdhaXQgZXhwZWN0KHBhZ2UuZ2V0QnlUZXh0KC9Nb2RlbGxvYmpla3RlIGJlc3TDpHRpZ3QvKSkudG9CZVZpc2libGUoKTtcbn0pO1xuXG50ZXN0KCduZXcgcHJvamVjdCBpcyBjcmVhdGVkIGZyb20gdGhlIHNhdmVkIGRyYWZ0IHdpdGhvdXQgbW92aW5nIHRoZSBvcmlnaW5hbCBwcm9qZWN0IEBwcm9qZWN0LWRyYWZ0JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XG4gIGNvbnN0IGNvbXBhY3QgPSAnMjAyNjA5MTUwMDAwMDAwMDAtJyArIHJhbmRvbVVVSUQoKS5yZXBsYWNlQWxsKCctJywgJycpLnNsaWNlKDAsIDgpO1xuICBjb25zdCBvcmlnaW4gPSAnbmV0d29yay1wcm9qZWN0LScgKyBjb21wYWN0O1xuICBhd2FpdCBwYWdlLmdvdG8oYC9zdHVkaW8vYWdlbnQ/cHJvamVjdD0ke2NvbXBhY3R9YCk7XG4gIGF3YWl0IHBhZ2UuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnTmFjaHJpY2h0IGFuIGRlbiBFbmdpbmVlcmluZy1Bc3Npc3RlbnRlbicgfSkuZmlsbChcbiAgICAnRWluIG5ldWVzIFByb2pla3QgbWl0IFJhc3BiZXJyeSBQaSB1bmQgZHJlaSBUZW1wZXJhdHVyc2Vuc29yZW4uJyk7XG4gIGF3YWl0IHBhZ2UubG9jYXRvcignLmVuZy1hZ2VudC1jb21wb3NlcicpLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnU2VuZGVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgY29uc3QgZWRpdG9yID0gcGFnZS5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0dlc3BlaWNoZXJ0ZXIgUHJvamVrdGVudHd1cmYnIH0pO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCc0IEdlcsOkdGUnKTtcbiAgY29uc3QgYmVmb3JlID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9qZWN0LWRyYWZ0JywgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBvcmlnaW4gfSB9KTtcbiAgY29uc3Qgb3JpZ2luYWxEcmFmdCA9IChhd2FpdCBiZWZvcmUuanNvbigpKS5kYXRhO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlUZXh0KCdBbHMgbmV1ZXMgUHJvamVrdCB2ZXJ3ZW5kZW4nLCB7IGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGVkaXRvci5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdOZXVlciBQcm9qZWt0bmFtZScsIGV4YWN0OiB0cnVlIH0pLmZpbGwoJ1RlbXBlcmF0dXJyZWdlbHVuZycpO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdOZXVlcyBQcm9qZWt0IGFubGVnZW4gdW5kIMO2ZmZuZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBhd2FpdCBleHBlY3QocGFnZSkudG9IYXZlVVJMKC9cXC9zdHVkaW9cXC9hZ2VudFxcP2RyYWZ0PS4rJnByb2plY3Q9LisvKTtcbiAgY29uc3QgdGFyZ2V0ID0gbmV3IFVSTChwYWdlLnVybCgpKS5zZWFyY2hQYXJhbXMuZ2V0KCdwcm9qZWN0JykhO1xuICBleHBlY3QodGFyZ2V0LnJlcGxhY2UoJ25ldHdvcmstcHJvamVjdC0nLCAnJykpLm5vdC50b0JlKGNvbXBhY3QpO1xuICBhd2FpdCBleHBlY3QoZWRpdG9yKS50b0NvbnRhaW5UZXh0KCc0IEdlcsOkdGUnKTtcbiAgYXdhaXQgcGFnZS5yZWxvYWQoKTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvcikudG9Db250YWluVGV4dCgnNCBHZXLDpHRlJyk7XG4gIGNvbnN0IGFmdGVyID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9qZWN0LWRyYWZ0JywgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBvcmlnaW4gfSB9KTtcbiAgZXhwZWN0KChhd2FpdCBhZnRlci5qc29uKCkpLmRhdGEpLnRvRXF1YWwob3JpZ2luYWxEcmFmdCk7XG4gIGNvbnN0IHRhcmdldFJlc3BvbnNlID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy9hZ2VudC9wcm9qZWN0LWRyYWZ0Jywge1xuICAgIGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHRhcmdldC5zdGFydHNXaXRoKCduZXR3b3JrLXByb2plY3QtJykgPyB0YXJnZXQgOiAnbmV0d29yay1wcm9qZWN0LScgKyB0YXJnZXQgfSxcbiAgfSk7XG4gIGNvbnN0IHRhcmdldERyYWZ0ID0gKGF3YWl0IHRhcmdldFJlc3BvbnNlLmpzb24oKSkuZGF0YTtcbiAgZXhwZWN0KHRhcmdldERyYWZ0LmRyYWZ0X2lkKS5ub3QudG9CZShvcmlnaW5hbERyYWZ0LmRyYWZ0X2lkKTtcbiAgZXhwZWN0KHRhcmdldERyYWZ0LmRldmljZXMpLnRvRXF1YWwob3JpZ2luYWxEcmFmdC5kZXZpY2VzKTtcbn0pO1xuXG50ZXN0KCd0aGUgd2l6YXJkIGV4ZWN1dGVzIHRoZSBzYW1lIHNhdmVkIGRyYWZ0IHRocm91Z2ggdGhlIHJlYWwgcmV2aWV3IHdvcmtmbG93IEBwcm9qZWN0LWRyYWZ0JywgYXN5bmMgKHsgcGFnZSB9KSA9PiB7XG4gIGNvbnN0IGNvbXBhY3QgPSAnMjAyNjA5MTUwMDAwMDAwMDAtJyArIHJhbmRvbVVVSUQoKS5yZXBsYWNlQWxsKCctJywgJycpLnNsaWNlKDAsIDgpO1xuICBjb25zdCBwcm9qZWN0ID0gJ25ldHdvcmstcHJvamVjdC0nICsgY29tcGFjdDtcbiAgYXdhaXQgcGFnZS5nb3RvKGAvc3R1ZGlvL2FnZW50P3Byb2plY3Q9JHtjb21wYWN0fWApO1xuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgndGV4dGJveCcsIHsgbmFtZTogJ05hY2hyaWNodCBhbiBkZW4gRW5naW5lZXJpbmctQXNzaXN0ZW50ZW4nIH0pLmZpbGwoXG4gICAgJ0VpbiBuZXVlcyBQcm9qZWt0IG1pdCBSYXNwYmVycnkgUGkgdW5kIGRyZWkgVGVtcGVyYXR1cnNlbnNvcmVuLicpO1xuICBhd2FpdCBwYWdlLmxvY2F0b3IoJy5lbmctYWdlbnQtY29tcG9zZXInKS5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ1NlbmRlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGNvbnN0IGVkaXRvciA9IHBhZ2UuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdHZXNwZWljaGVydGVyIFByb2pla3RlbnR3dXJmJyB9KTtcbiAgYXdhaXQgZXhwZWN0KGVkaXRvcikudG9Db250YWluVGV4dCgnNCBHZXLDpHRlJyk7XG4gIGZvciAoY29uc3QgZmllbGQgb2YgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgndGV4dGJveCcsIHsgbmFtZTogJ0Fuc2NobHVzc3RlY2hub2xvZ2llJywgZXhhY3Q6IHRydWUgfSkuYWxsKCkpIGF3YWl0IGZpZWxkLmZpbGwoJ2V0aGVybmV0Jyk7XG4gIGZvciAoY29uc3QgZmllbGQgb2YgYXdhaXQgZWRpdG9yLmdldEJ5Um9sZSgnY29tYm9ib3gnLCB7IG5hbWU6ICdWZXJhcmJlaXRlbmRlciBDb250cm9sbGVyJywgZXhhY3Q6IHRydWUgfSkuYWxsKCkpIGF3YWl0IGZpZWxkLnNlbGVjdE9wdGlvbih7IGxhYmVsOiAnUmFzcGJlcnJ5UGknIH0pO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCdjb21ib2JveCcsIHsgbmFtZTogJ1RlY2huaXNjaGUgUGFyYW1ldGVyJywgZXhhY3Q6IHRydWUgfSkuc2VsZWN0T3B0aW9uKCdkZWZhdWx0cycpO1xuICBhd2FpdCBlZGl0b3IuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBbmdhYmVuIHNwZWljaGVybicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGV4cGVjdChlZGl0b3IuZ2V0QnlSb2xlKCdzdGF0dXMnKSkudG9Db250YWluVGV4dCgnUmV2aXNpb24gMiBnZXNwZWljaGVydCcpO1xuICBhd2FpdCBwYWdlLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAvSW0gV2l6YXJkIGJlYXJiZWl0ZW4vIH0pLmNsaWNrKCk7XG4gIGNvbnN0IGRpYWxvZyA9IHBhZ2UuZ2V0QnlSb2xlKCdkaWFsb2cnLCB7IG5hbWU6ICdFbmdpbmVlcmluZy1BdWZ0cmFnIGVyc3RlbGxlbicgfSk7XG4gIGF3YWl0IGV4cGVjdChkaWFsb2cpLnRvQmVWaXNpYmxlKCk7XG4gIGF3YWl0IGV4cGVjdChkaWFsb2cuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdHZXNwZWljaGVydGVyIFByb2pla3RlbnR3dXJmJyB9KSkudG9Db250YWluVGV4dCgnUmV2aXNpb24gMicpO1xuICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnUHJvamVrdG5hbWUnLCBleGFjdDogdHJ1ZSB9KS5maWxsKCdHZW1laW5zYW1lciBFbnR3dXJmJyk7XG4gIGNvbnN0IHNjb3BlcyA9IGRpYWxvZy5nZXRCeVJvbGUoJ2dyb3VwJywgeyBuYW1lOiAnV29ya2Zsb3d1bWZhbmcnLCBleGFjdDogdHJ1ZSB9KS5nZXRCeVJvbGUoJ2NoZWNrYm94Jyk7XG4gIGF3YWl0IGV4cGVjdChzY29wZXMpLnRvSGF2ZUNvdW50KDkpO1xuICBmb3IgKGxldCBpbmRleCA9IDE7IGluZGV4IDwgOTsgaW5kZXgrKykgYXdhaXQgc2NvcGVzLm50aChpbmRleCkudW5jaGVjaygpO1xuICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdBdWZ0cmFnIHN0YXJ0ZW4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBhd2FpdCBkaWFsb2cuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdGcmVpZ2ViZW4sIMO8YmVybmVobWVuICYgZm9ydGZhaHJlbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGV4cGVjdC5wb2xsKGFzeW5jICgpID0+IHtcbiAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvaGFyZHdhcmUtbm9kZXMnLCB7IGhlYWRlcnM6IHsgJ1gtUHJvamVjdC1JRCc6IHByb2plY3QgfSB9KTtcbiAgICBleHBlY3QocmVzcG9uc2Uub2soKSkudG9CZSh0cnVlKTtcbiAgICBjb25zdCBwYXlsb2FkID0gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICAgIGNvbnN0IG5vZGVzID0gQXJyYXkuaXNBcnJheShwYXlsb2FkKSA/IHBheWxvYWQgOiBwYXlsb2FkLml0ZW1zID8/IHBheWxvYWQuZGF0YSA/PyBbXTtcbiAgICByZXR1cm4gbm9kZXMubWFwKChub2RlOiB7IG5hbWU6IHN0cmluZyB9KSA9PiBub2RlLm5hbWUpLnNvcnQoKTtcbiAgfSkudG9FcXVhbChbJ1Jhc3BiZXJyeVBpJywgJ1RlbXBlcmF0dXJzZW5zb3IxJywgJ1RlbXBlcmF0dXJzZW5zb3IyJywgJ1RlbXBlcmF0dXJzZW5zb3IzJ10uc29ydCgpKTtcbiAgYXdhaXQgZGlhbG9nLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRXJnw6RuemVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgY29uc3Qgc3VwcGxlbWVudCA9IGRpYWxvZy5nZXRCeVJvbGUoJ3JlZ2lvbicsIHsgbmFtZTogJ0VuZ2luZWVyaW5nLUF1ZnRyYWcgZXJnw6RuemVuJyB9KTtcbiAgY29uc3QgcmV2aXNlZCA9IHN1cHBsZW1lbnQuZ2V0QnlSb2xlKCdyZWdpb24nLCB7IG5hbWU6ICdHZXNwZWljaGVydGVyIFByb2pla3RlbnR3dXJmJyB9KTtcbiAgYXdhaXQgcmV2aXNlZC5nZXRCeVJvbGUoJ3RleHRib3gnLCB7IG5hbWU6ICdBbmZvcmRlcnVuZyBlcmfDpG56ZW4nLCBleGFjdDogdHJ1ZSB9KS5maWxsKCdWaWVyIFRlbXBlcmF0dXJzZW5zb3JlbiBzdGF0dCBkcmVpLicpO1xuICBhd2FpdCByZXZpc2VkLmdldEJ5Um9sZSgnYnV0dG9uJywgeyBuYW1lOiAnRXJnw6RuenVuZyBzcGVpY2hlcm4nLCBleGFjdDogdHJ1ZSB9KS5jbGljaygpO1xuICBhd2FpdCBleHBlY3QocmV2aXNlZCkudG9Db250YWluVGV4dCgnUmV2aXNpb24gMycpO1xuICBhd2FpdCBleHBlY3QocmV2aXNlZCkudG9Db250YWluVGV4dCgnNSBHZXLDpHRlJyk7XG4gIGNvbnN0IGZvdXJ0aCA9IHJldmlzZWQuZ2V0QnlSb2xlKCdncm91cCcsIHsgbmFtZTogJ1RlbXBlcmF0dXJzZW5zb3I0IMK3IFNFTlNPUicsIGV4YWN0OiB0cnVlIH0pO1xuICBhd2FpdCBmb3VydGguZ2V0QnlSb2xlKCd0ZXh0Ym94JywgeyBuYW1lOiAnQW5zY2hsdXNzdGVjaG5vbG9naWUnLCBleGFjdDogdHJ1ZSB9KS5maWxsKCdldGhlcm5ldCcpO1xuICBhd2FpdCBmb3VydGguZ2V0QnlSb2xlKCdjb21ib2JveCcsIHsgbmFtZTogJ1ZlcmFyYmVpdGVuZGVyIENvbnRyb2xsZXInLCBleGFjdDogdHJ1ZSB9KS5zZWxlY3RPcHRpb24oeyBsYWJlbDogJ1Jhc3BiZXJyeVBpJyB9KTtcbiAgYXdhaXQgcmV2aXNlZC5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0FuZ2FiZW4gc3BlaWNoZXJuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0KHJldmlzZWQuZ2V0QnlSb2xlKCdzdGF0dXMnKSkudG9Db250YWluVGV4dCgnUmV2aXNpb24gNCBnZXNwZWljaGVydCcpO1xuICBjb25zdCBiZWZvcmUgPSBhd2FpdCBwYWdlLnJlcXVlc3QuZ2V0KCcvYXBpL2VuZ2luZWVyaW5nL3dvcmtmbG93P3N1bW1hcnk9MScsIHsgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9IH0pO1xuICBjb25zdCBvbGRXb3JrZmxvdyA9IGF3YWl0IGJlZm9yZS5qc29uKCk7XG4gIGF3YWl0IHN1cHBsZW1lbnQuZ2V0QnlSb2xlKCdidXR0b24nLCB7IG5hbWU6ICdHZXNwZWljaGVydGVuIEVudHd1cmYgaW0gQXVmdHJhZyDDvGJlcm5laG1lbicsIGV4YWN0OiB0cnVlIH0pLmNsaWNrKCk7XG4gIGF3YWl0IGRpYWxvZy5nZXRCeVJvbGUoJ2J1dHRvbicsIHsgbmFtZTogJ0ZyZWlnZWJlbiwgw7xiZXJuZWhtZW4gJiBmb3J0ZmFocmVuJywgZXhhY3Q6IHRydWUgfSkuY2xpY2soKTtcbiAgYXdhaXQgZXhwZWN0LnBvbGwoYXN5bmMgKCkgPT4ge1xuICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgcGFnZS5yZXF1ZXN0LmdldCgnL2FwaS9lbmdpbmVlcmluZy9oYXJkd2FyZS1ub2RlcycsIHsgaGVhZGVyczogeyAnWC1Qcm9qZWN0LUlEJzogcHJvamVjdCB9IH0pO1xuICAgIGNvbnN0IHBheWxvYWQgPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gICAgY29uc3Qgbm9kZXMgPSBBcnJheS5pc0FycmF5KHBheWxvYWQpID8gcGF5bG9hZCA6IHBheWxvYWQuaXRlbXMgPz8gcGF5bG9hZC5kYXRhID8/IFtdO1xuICAgIHJldHVybiBub2Rlcy5tYXAoKG5vZGU6IHsgbmFtZTogc3RyaW5nIH0pID0+IG5vZGUubmFtZSkuc29ydCgpO1xuICB9KS50b0VxdWFsKFsnUmFzcGJlcnJ5UGknLCAnVGVtcGVyYXR1cnNlbnNvcjEnLCAnVGVtcGVyYXR1cnNlbnNvcjInLCAnVGVtcGVyYXR1cnNlbnNvcjMnLCAnVGVtcGVyYXR1cnNlbnNvcjQnXS5zb3J0KCkpO1xuICBjb25zdCBhZnRlciA9IGF3YWl0IHBhZ2UucmVxdWVzdC5nZXQoJy9hcGkvZW5naW5lZXJpbmcvd29ya2Zsb3c/c3VtbWFyeT0xJywgeyBoZWFkZXJzOiB7ICdYLVByb2plY3QtSUQnOiBwcm9qZWN0IH0gfSk7XG4gIGNvbnN0IG5ld1dvcmtmbG93ID0gYXdhaXQgYWZ0ZXIuanNvbigpO1xuICBjb25zdCBvbGRDb250ZXh0ID0gb2xkV29ya2Zsb3cuZGF0YT8uY29udGV4dCA/PyBvbGRXb3JrZmxvdy5jb250ZXh0O1xuICBjb25zdCBuZXdDb250ZXh0ID0gbmV3V29ya2Zsb3cuZGF0YT8uY29udGV4dCA/PyBuZXdXb3JrZmxvdy5jb250ZXh0O1xuICBleHBlY3QobmV3Q29udGV4dC53aXphcmRfcmVxdWVzdC5ydW5faWQpLnRvQmUob2xkQ29udGV4dC53aXphcmRfcmVxdWVzdC5ydW5faWQpO1xuICBleHBlY3QobmV3Q29udGV4dC53aXphcmRfcmVxdWVzdC5yZXZpc2lvbikubm90LnRvQmUob2xkQ29udGV4dC53aXphcmRfcmVxdWVzdC5yZXZpc2lvbik7XG4gIGV4cGVjdChuZXdDb250ZXh0LmFnZW50X3dpemFyZF9zdGF0dXMuZW5naW5lZXJpbmdfZHJhZnRfcmVmLnJldmlzaW9uKS50b0JlKDQpO1xufSk7XG4iXSwibWFwcGluZ3MiOiJBQUFBLFNBQVNBLElBQUksRUFBRUMsTUFBTSxRQUFRLGlCQUFpQjtBQUM5QyxTQUFTQyxVQUFVLFFBQVEsYUFBYTtBQUN4QyxTQUFTQyxZQUFZLFFBQVEsb0JBQW9CO0FBRWpESCxJQUFJLENBQUMsa0dBQWtHLEVBQUUsT0FBTztFQUFFSTtBQUFLLENBQUMsS0FBSztFQUFBLElBQUFDLGtCQUFBLEVBQUFDLGVBQUE7RUFDM0gsTUFBTUMsT0FBTyxHQUFHLHdCQUF3QixHQUFHTCxVQUFVLENBQUMsQ0FBQztFQUN2RCxNQUFNTSxHQUFHLEdBQUdOLFVBQVUsQ0FBQyxDQUFDO0VBQ3hCLE1BQU1PLEtBQUssR0FBRyxDQUFDO0lBQUVDLFVBQVUsRUFBRSxPQUFPO0lBQUVDLEtBQUssRUFBRSxVQUFVO0lBQUVDLFVBQVUsRUFBRSxRQUFRO0lBQUVDLGFBQWEsRUFBRSxRQUFRO0lBQUVDLFFBQVEsRUFBRSxVQUFVO0lBQzFIQyxXQUFXLEVBQUUsQ0FBQztNQUFFQyxHQUFHLEVBQUUsZ0JBQWdCO01BQUVDLE9BQU8sRUFBRSxFQUFFO01BQUVDLFNBQVMsRUFBRTtJQUFHLENBQUMsRUFBRTtNQUFFRixHQUFHLEVBQUUsU0FBUztNQUFFQyxPQUFPLEVBQUUsRUFBRTtNQUFFQyxTQUFTLEVBQUU7SUFBRyxDQUFDO0VBQUUsQ0FBQyxDQUFDO0VBQ3pILE1BQU1DLE1BQU0sR0FBRztBQUNqQixhQUFhWCxHQUFHO0FBQ2hCO0FBQ0E7QUFDQTtBQUNBLHlCQUF5QlksSUFBSSxDQUFDQyxTQUFTLENBQUNaLEtBQUssQ0FBQztBQUM5QztBQUNBLDZEQUE2RDtFQUMzRCxNQUFNYSxPQUFPLEdBQUcs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